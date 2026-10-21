"""Native executor acceptance; frozen oracle JSON is only an independent expectation."""

import json
from dataclasses import replace
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from src.engine import run_attack_query
from src.engine.graph import EngineGraph
from src.engine.remediation import (
    DOC,
    UnsupportedIntervention,
    _digest,
    extract_witness,
    prepare_baseline,
    replay_baseline,
    request_for_baseline,
)

FIX = Path(__file__).parent / "fixtures/remediation"


def read(name):
    return json.loads((FIX / name).read_text(encoding="utf-8"))


def finite():
    graph = EngineGraph.from_canonical(read("graph.json"))
    cells = [
        {"source_id": s, "goal_id": "host", "query": read(f"{s}-query.json")}
        for s in ("alice", "bob")
    ]
    return graph, prepare_baseline(graph, cells, run_id="native-finite")


@pytest.mark.parametrize(
    "fixture,expected",
    [
        ("request-v1.1.json", [["cut"] * 3, ["cut"]]),
        ("request-bypass-v1.1.json", [["retained", "cut", "cut"], ["cut"]]),
        ("request-acl-v1.1.json", [["cut", "cut", "retained"], ["retained"]]),
    ],
)
def test_native_finite_replay(fixture, expected):
    graph, baseline = finite()
    before = graph.to_canonical()
    request = request_for_baseline(baseline, read(fixture)["edits"], request_id="test")
    artifact = replay_baseline(request, graph, baseline)
    actual = [[p["disposition"] for p in c["programs"]] for c in artifact["cells"]]
    assert [sorted(a) for a in actual] == [sorted(a) for a in expected]
    assert graph.to_canonical() == before
    assert artifact["baseline_input_digest_before"] == artifact["baseline_input_digest_after"]
    assert artifact["effort"] is artifact["conditional_p"] is None
    for cell in artifact["cells"]:
        assert cell["baseline_complete"] and cell["rediscovery"]["status"] == "not_run"
        for program in cell["programs"]:
            assert len(program["native_transition_history"]) == len(
                program["baseline"]["semantic_program"]
            )
            if program["disposition"] == "cut":
                assert program["failure"]["failed"]
                assert program["steps"][-1]["before"] == program["steps"][-1]["after"]
            for action in program["baseline"]["semantic_program"]:
                schema = json.loads((DOC / "result-v1.1.schema.json").read_text())
                Draft202012Validator(schema["$defs"]["semantic_action"]).validate(action)


@pytest.mark.parametrize(
    "pin",
    [
        "graph_digest",
        "snapshot_id",
        "source_manifest_digest",
        "goal_manifest_digest",
        "query_profile_digest",
        "snapshot_facts_digest",
        "rating_inputs_digest",
        "semantic_catalog_digest",
        "engine_revision",
        "search_budget",
    ],
)
def test_rejects_each_scope_mismatch(pin):
    graph, baseline = finite()
    request = request_for_baseline(baseline, read("request-v1.1.json")["edits"], request_id="test")
    if pin == "engine_revision":
        request["scope"][pin] = "0" * 40
    elif pin == "search_budget":
        request["scope"][pin]["max_steps"] += 1
    else:
        request["scope"][pin] = "sha256:" + "0" * 64
    with pytest.raises(ValueError, match="scope mismatch"):
        replay_baseline(request, graph, baseline)


def test_rejects_actual_input_and_native_cache_mismatch():
    graph, baseline = finite()
    request = request_for_baseline(baseline, read("request-v1.1.json")["edits"], request_id="test")
    with pytest.raises(ValueError, match="trace mismatch"):
        replay_baseline(request, graph, replace(baseline, native_digest="stale"))
    cells = json.loads(baseline.cells_json)
    cells[0]["query"]["budget"]["max_paths"] = 1
    with pytest.raises(ValueError):
        replay_baseline(request, graph, replace(baseline, cells_json=json.dumps(cells)))
    request["edits"][0]["expected_before"] = None
    with pytest.raises(ValueError, match="expected_before"):
        replay_baseline(request, graph, baseline)


def test_asrep_static_intervention_cuts_request_without_producing_material():
    from scripts.research.asrep_inputs import inputs

    graph, query = inputs()
    cells = [{"source_id": "requester", "goal_id": "host", "query": query}]
    baseline = prepare_baseline(graph, cells, run_id="asrep")
    fact = next(f for f in graph.snapshot_facts.facts if f.name == "dontreqpreauth")
    edits = [
        {
            "edit_id": "preauth",
            "catalog_entry_id": "asrep-preauth",
            "kind": "snapshot_fact_replace",
            "subject": fact.subject,
            "name": fact.name,
            "expected_before": True,
            "after": False,
            "evidence_digest": _digest(fact.evidence),
            "evidence_refs": ["synthetic://preauth"],
            "rationale": "require preauthentication",
            "declaration": "counterfactual_intervention",
        }
    ]
    original = graph.snapshot_facts
    request = request_for_baseline(baseline, edits, request_id="test")
    artifact = replay_baseline(request, graph, baseline)
    program = artifact["cells"][0]["programs"][0]
    assert program["disposition"] == "cut"
    assert program["failure"] == {"step_index": 0, "failed": ["dontreqpreauth"], "unknown": []}
    assert not program["final_state"]["asrep_material"]
    assert (
        graph.snapshot_facts == original and original.lookup(fact.subject, fact.name).value is True
    )
    request["edits"][0]["evidence_digest"] = "sha256:" + "0" * 64
    with pytest.raises(ValueError, match="evidence pin"):
        replay_baseline(request, graph, baseline)


def test_explicit_relationship_denial_and_preexisting_token_survives():
    graph, baseline = finite()
    member = next(
        e
        for e in graph.edges(kind="MemberOf")
        if e["source"] == read("alice-query.json")["initial_actor"]
    )
    edit = {
        "edit_id": "membership",
        "catalog_entry_id": "group-membership",
        "kind": "deny_relationship",
        "edge_id": member["id"],
        "relationship": {k: member[k] for k in ("source", "kind", "target")},
        "provenance_digest": _digest(member["provenance"]),
        "effective_right_verified": True,
        "evidence_refs": ["synthetic://membership"],
        "rationale": "remove effective membership",
    }
    artifact = replay_baseline(
        request_for_baseline(baseline, [edit], request_id="test"), graph, baseline
    )
    assert any(p["disposition"] == "retained" for p in artifact["cells"][0]["programs"])
    cells = json.loads(baseline.cells_json)[:1]
    cells[0]["query"]["initial_state"]["effective_member"] = [[member["source"], member["target"]]]
    baseline = prepare_baseline(graph, cells, run_id="token")
    artifact = replay_baseline(
        request_for_baseline(baseline, [edit], request_id="test"), graph, baseline
    )
    assert any(
        p["disposition"] == "retained" and p["final_state"]["effective_member"]
        for p in artifact["cells"][0]["programs"]
    )


def test_typed_unsupported_and_context_mismatch():
    graph, baseline = finite()
    edits = read("request-v1.1.json")["edits"]
    edits[0]["key"]["authentication_context"] = "other-host"
    request = request_for_baseline(baseline, edits, request_id="test")
    with pytest.raises(ValueError, match="context mismatch"):
        replay_baseline(request, graph, baseline)
    edits = read("request-acl-v1.1.json")["edits"]
    edits[0]["catalog_entry_id"] = "acl-revoke"
    edits[0]["relationship"]["kind"] = "GenericAll"
    request = request_for_baseline(baseline, edits, request_id="test")
    with pytest.raises(UnsupportedIntervention) as error:
        replay_baseline(request, graph, baseline)
    assert error.value.edit_id and error.value.reason


def test_native_witness_scope_history_and_zero_action():
    graph, baseline = finite()
    query = read("alice-query.json")
    result = run_attack_query(query, graph)
    witnesses = [
        extract_witness(
            p,
            result.materialized_query,
            graph,
            comparison_scope_digest=_digest(baseline.scope),
            source_id="alice",
            goal_id="host",
        )
        for p in result.paths
    ]
    assert len({w["semantic_identity"] for w in witnesses}) == 3
    query["initial_state"]["admin_control"] = [query["target"]]
    result = run_attack_query(query, graph)
    assert not result.paths[0].transition_history
    witness = extract_witness(
        result.paths[0],
        result.materialized_query,
        graph,
        comparison_scope_digest=_digest(baseline.scope),
        source_id="alice",
        goal_id="host",
    )
    assert witness["semantic_program"] == []
    other = extract_witness(
        result.paths[0],
        result.materialized_query,
        graph,
        comparison_scope_digest=_digest(baseline.scope),
        source_id="bob",
        goal_id="host",
    )
    assert witness["semantic_identity"] != other["semantic_identity"]


@pytest.mark.parametrize("mode,status", [("unknown", "indeterminate"), ("false", "blocked")])
def test_unknown_and_known_false_baselines_never_create_cuts(mode, status):
    graph, _ = finite()
    query = read("alice-query.json")
    if mode == "unknown":
        query["assumptions"] = [
            f for f in query["assumptions"] if f["predicate"] != "authentication_accepted"
        ]
    else:
        fact = next(f for f in query["assumptions"] if f["predicate"] == "authentication_accepted")
        query["runtime_facts"] = [{**fact, "value": False, "origin": "blocked_evidence"}]
    cells = [{"source_id": "alice", "goal_id": "host", "query": query}]
    baseline = prepare_baseline(graph, cells, run_id=mode)
    edit = read("request-bypass-v1.1.json")["edits"][:1]
    artifact = replay_baseline(
        request_for_baseline(baseline, edit, request_id=mode), graph, baseline
    )
    cell = artifact["cells"][0]
    assert cell["baseline_status"] == status and cell["programs"] == []
    assert cell["rediscovery"]["status"] == "not_run"


def test_one_source_overlay_does_not_leak_and_truncation_is_preserved():
    graph, baseline = finite()
    edit = read("request-v1.1.json")["edits"][:1]
    artifact = replay_baseline(
        request_for_baseline(baseline, edit, request_id="alice"), graph, baseline
    )
    bob = artifact["cells"][1]["programs"][0]
    assert bob["disposition"] == "retained"
    assert bob["steps"][0]["intervention_refs"] == []
    assert bob["steps"][0]["before"]["control"] == [read("bob-query.json")["initial_actor"]]
    cells = json.loads(baseline.cells_json)[:1]
    cells[0]["query"]["budget"]["max_paths"] = 1
    baseline = prepare_baseline(graph, cells, run_id="capped")
    artifact = replay_baseline(
        request_for_baseline(baseline, edit, request_id="capped"), graph, baseline
    )
    assert artifact["cells"][0]["baseline_truncated"]
    assert not artifact["cells"][0]["baseline_complete"]


@pytest.mark.parametrize("failure", ["unknown", "error"])
def test_replay_unknown_and_evaluator_error_are_not_cuts(monkeypatch, failure):
    import src.engine.remediation as executor
    from src.engine.semantics import AttackState
    from src.engine.semantics.transitions import Status

    graph, baseline = finite()
    native = executor.evaluate

    def injected(graph, state, request, context, catalog):
        if any(
            f.provenance_reference and f.provenance_reference.startswith("intervention:")
            for f in context.facts.values()
        ):
            if failure == "error":
                raise ValueError("injected evaluator error")
            return replace(
                native(graph, state, request, context, catalog),
                status=Status.INDETERMINATE,
                failed=(),
                unknown=("unresolved",),
                additions=AttackState(),
            )
        return native(graph, state, request, context, catalog)

    monkeypatch.setattr(executor, "evaluate", injected)
    request = request_for_baseline(baseline, read("request-v1.1.json")["edits"], request_id="test")
    artifact = replay_baseline(request, graph, baseline)
    assert {p["disposition"] for c in artifact["cells"] for p in c["programs"]} == {
        "error" if failure == "error" else "indeterminate"
    }


def test_witness_derived_lineage_and_native_tamper_rejection():
    from scripts.research.asrep_inputs import inputs

    graph, query = inputs()
    result = run_attack_query(query, graph)
    path = result.paths[0]
    witness = extract_witness(
        path,
        result.materialized_query,
        graph,
        comparison_scope_digest=_digest(query),
        source_id="source",
        goal_id="goal",
    )
    actions = witness["semantic_program"]
    assert witness["route_id"] == _digest([e for e in path.transition_edge_ids if e is not None])
    assert 0 in actions[1]["producer_action_indices"]
    assert 1 in actions[2]["producer_action_indices"]
    schema = json.loads((DOC / "result-v1.1.schema.json").read_text())
    for action in actions:
        Draft202012Validator(schema["$defs"]["semantic_action"]).validate(action)
    forged = replace(
        path,
        transition_history=(
            replace(
                path.transition_history[0],
                result=replace(path.transition_history[0].result, satisfied=("fake",)),
            ),
            *path.transition_history[1:],
        ),
    )
    with pytest.raises(ValueError, match="transition mismatch"):
        extract_witness(
            forged,
            result.materialized_query,
            graph,
            comparison_scope_digest=_digest(query),
            source_id="source",
            goal_id="goal",
        )


def test_manifest_verified_seamless_executor_replay():
    import os

    from scripts.research.remediation_replay_probe import seamless_probe

    raw_dir = os.environ.get("REMEDIATION_SEAMLESS_RAW_DIR")
    if not raw_dir:
        pytest.skip("Set REMEDIATION_SEAMLESS_RAW_DIR to manifest-verified private inputs")
    evidence = seamless_probe(Path(raw_dir))
    assert evidence["verified_raw_files"] == 6
    assert evidence["case"]["baseline_unchanged"]
    assert evidence["case"]["cells"][0]["replay"] == {"cut": 1}


def test_native_ids_are_observation_refs_and_evidence_changes_identity():
    from scripts.research.remediation_acceptance import normalized_program_identity

    graph, baseline = finite()
    request = request_for_baseline(baseline, read("request-v1.1.json")["edits"], request_id="test")
    artifact = replay_baseline(request, graph, baseline)
    trace = artifact["cells"][0]["programs"][0]["baseline"]
    assert trace["trace_ref"].startswith("native:native-finite/")
    cell, scope = {"source_id": "alice", "goal_id": "host"}, artifact["comparison_scope_digest"]
    churned = json.loads(json.dumps(trace))
    churned.update(program_id="reused-generated-id", trace_ref="another-observation")
    assert normalized_program_identity(cell, scope, churned) == trace["semantic_identity"]
    churned["semantic_program"][0]["evidence_bindings"][0]["reference"] = "other-initial-support"
    assert normalized_program_identity(cell, scope, churned) != trace["semantic_identity"]


def test_native_rbcd_participants_and_gates_are_bound():
    from scripts.research.rbcd_inputs import inputs

    graph, query = inputs()
    result = run_attack_query(query, graph)
    for path in result.paths:
        trace = extract_witness(
            path,
            result.materialized_query,
            graph,
            comparison_scope_digest=_digest(query),
            source_id="source",
            goal_id="goal",
            observation_id="rbcd",
        )
        for action in trace["semantic_program"]:
            if action["technique_id"].startswith("rbcd_"):
                assert set(action["participants"]) == {
                    "controller",
                    "principal",
                    "impersonated",
                    "target",
                    "authentication_context",
                    "service_context",
                    "service",
                    "spn",
                }
            schema = json.loads((DOC / "result-v1.1.schema.json").read_text())
            Draft202012Validator(schema["$defs"]["semantic_action"]).validate(action)


def test_wholly_nonstructural_route_is_explicitly_empty():
    from scripts.research.asrep_inputs import inputs

    graph, query = inputs()
    owner = query["initial_state"]["known_identity"][0]
    context = query["authentication_context"]
    query["target"] = context
    query["target_goal"] = {
        "target": context,
        "required_state": {"usable_identity": [[owner, context]]},
    }
    query.pop("checkpoint_goal", None)
    baseline = prepare_baseline(
        graph,
        [{"source_id": "requester", "goal_id": "identity", "query": query}],
        run_id="nonstructural",
    )
    fact = graph.snapshot_facts.lookup(owner, "dontreqpreauth")
    edit = {
        "edit_id": "preauth",
        "catalog_entry_id": "asrep-preauth",
        "kind": "snapshot_fact_replace",
        "subject": owner,
        "name": "dontreqpreauth",
        "expected_before": True,
        "after": False,
        "evidence_digest": _digest(fact.evidence),
        "evidence_refs": ["synthetic://preauth"],
        "rationale": "require preauthentication",
        "declaration": "counterfactual_intervention",
    }
    artifact = replay_baseline(
        request_for_baseline(baseline, [edit], request_id="test"), graph, baseline
    )
    program = artifact["cells"][0]["programs"][0]
    assert program["baseline"]["route_id"] == _digest([])
    assert program["observed_route"] == {"edge_ids": [], "kind": "empty_nonstructural"}
    assert len(program["baseline"]["semantic_program"]) == 3
