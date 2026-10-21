"""A-owned independent remediation acceptance, without a counterfactual executor."""

import copy
import json
from pathlib import Path

import pytest

from src.engine import run_attack_query
from src.engine.graph import EngineGraph

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "tests/fixtures/remediation"


def read(path):
    return json.loads(path.read_text())


def test_artifact_contracts_and_expected_outputs():
    from scripts.research.remediation_acceptance import check

    assert check() == {"status": "passed", "catalog_entries": 11, "oracle_cases": 8}


@pytest.mark.parametrize(
    "case", ["genuine_choke", "alternative_bypass", "ineffective_fix", "multiple_sources"]
)
def test_finite_public_query_oracles(case):
    oracle = read(FIX / "finite-v1.json")
    graph = EngineGraph.from_canonical(read(FIX / "graph.json"))
    canonical = graph.to_canonical()
    for source in oracle["sources"]:
        query = read(FIX / f"{source}-query.json")
        original = copy.deepcopy(query)
        before = run_attack_query(query, graph)
        expected = oracle["cases"][case]["cells"][source]
        assert before.complete and len(before.paths) == expected["before_programs"]
        expected_before = [
            oracle["expected_step_specs"][pid] for pid in expected["before_program_ids"]
        ]
        actual_before = [
            [
                {"request": vars(step.result.request), "edge_id": step.edge_id}
                for step in path.transition_history
            ]
            for path in before.paths
        ]
        assert sorted(json.dumps(v, sort_keys=True) for v in actual_before) == sorted(
            json.dumps(v, sort_keys=True) for v in expected_before
        )
        after_query = copy.deepcopy(query)
        after_query["runtime_facts"] += oracle["cases"][case]["runtime_controls"].get(source, [])
        after = run_attack_query(after_query, graph)
        assert after.complete and len(after.paths) == expected["after_programs"]
        expected_after = [
            oracle["expected_step_specs"][pid] for pid in expected["after_program_ids"]
        ]
        actual_after = [
            [
                {"request": vars(step.result.request), "edge_id": step.edge_id}
                for step in path.transition_history
            ]
            for path in after.paths
        ]
        assert sorted(json.dumps(v, sort_keys=True) for v in actual_after) == sorted(
            json.dumps(v, sort_keys=True) for v in expected_after
        )
        assert after.final_goal_reached == expected["reachable_after"]
        if case == "alternative_bypass" and source == "alice":
            assert [
                [s.result.request.technique_id for s in p.transition_history] for p in after.paths
            ] == [["obtain_admin_execution_on_host"]]
        if not expected["reachable_after"]:
            assert after.status == "blocked"
        assert graph.to_canonical() == canonical and query == original


@pytest.mark.parametrize("case", ["missing_evidence", "false_evidence", "search_truncation"])
def test_negative_or_unknown_never_becomes_a_safe_claim(case):
    oracle = read(FIX / "finite-v1.json")["cases"][case]
    graph = EngineGraph.from_canonical(read(FIX / "graph.json"))
    query = read(FIX / "alice-query.json")
    if case == "missing_evidence":
        query["assumptions"] = [
            f for f in query["assumptions"] if f["predicate"] != "admin_channel"
        ]
    elif case == "false_evidence":
        query["runtime_facts"] = oracle["runtime_controls"]["alice"]
    else:
        query["budget"]["max_steps"] = 1
    result = run_attack_query(query, graph)
    assert result.status == oracle["status"]
    assert result.truncated == oracle["truncated"]
    assert len(result.paths) == oracle["path_count"]
    if case == "false_evidence":
        assert "known_false_veto" in {
            r.reason for r in result.materialized_query.rejected_assumptions
        }
    if case == "search_truncation":
        assert result.final_goal_reached and not result.complete


def test_nonstructural_asrep_path_and_runtime_cut():
    from scripts.research.asrep_inputs import X, inputs

    graph, query = inputs()
    canonical, facts = graph.to_canonical(), graph.snapshot_facts
    before = run_attack_query(query, graph)
    expected = read(FIX / "finite-v1.json")["cases"]["nonstructural"]
    assert before.complete and len(before.paths) == 1
    assert [s.result.request.technique_id for s in before.paths[0].transition_history] == expected[
        "program"
    ]
    assert before.paths[0].transition_edge_ids[:3] == (None, None, None)
    assert not any(e["source"] == X for e in canonical["edges"])
    after_query = copy.deepcopy(query)
    fact = next(f for f in query["assumptions"] if f["predicate"] == "recovery_success")
    after_query["runtime_facts"] = [{**fact, "value": False, "origin": "blocked_evidence"}]
    after = run_attack_query(after_query, graph)
    assert after.complete and not after.paths and after.status == "blocked"
    assert graph.to_canonical() == canonical and graph.snapshot_facts == facts


@pytest.mark.parametrize(
    "bad", ["truncated_disconnect", "unrated_effort", "unrated_probability", "unresolved_overlay"]
)
def test_rejects_false_security_or_numeric_claims(bad):
    from scripts.research.remediation_acceptance import validate_result

    result = read(FIX / "result-v1.1.json")
    cell = result["cells"][0]
    if bad == "truncated_disconnect":
        cell["after"]["truncated"] = True
        cell["after"]["complete"] = False
    elif bad == "unrated_effort":
        cell["effort"]["delta"] = 1
    elif bad == "unrated_probability":
        cell["conditional_p"]["delta_interval"] = [0, 0]
    else:
        result["overlay_disposition"] = "unresolved"
    with pytest.raises(ValueError):
        validate_result(result)


@pytest.mark.parametrize(
    "bad", ["wrong_catalog", "duplicate", "wrong_gate", "wrong_before", "computed_gate", "spn_type"]
)
def test_overlay_validation_rejects_ambiguous_or_invalid_edits(bad):
    from scripts.research.remediation_acceptance import validate_request

    request = read(FIX / "request-v1.1.json")
    if bad == "wrong_catalog":
        request["catalog_digest"] = "sha256:" + "0" * 64
    elif bad == "duplicate":
        request["edits"].append(copy.deepcopy(request["edits"][0]))
    elif bad == "wrong_gate":
        request["edits"][0]["key"]["predicate"] = "rdp_available"
    elif bad == "computed_gate":
        request["edits"][0].update(catalog_entry_id="admin-revoke")
        request["edits"][0]["key"]["predicate"] = "source_authorized"
    elif bad == "wrong_before":
        request["edits"][0]["expected_before"] = False
    else:
        request["edits"] = [
            {
                "edit_id": "spn",
                "catalog_entry_id": "kerberoast-spn",
                "evidence_refs": ["synthetic://269/spn"],
                "rationale": "Decommissioned service",
                "kind": "snapshot_fact_replace",
                "subject": "user",
                "name": "has_spn",
                "expected_before": ["svc/host"],
                "after": [],
                "evidence_digest": "sha256:" + "0" * 64,
                "declaration": "counterfactual_intervention",
            }
        ]
    with pytest.raises(ValueError):
        validate_request(request)


def test_rated_effort_and_selected_conditional_p_have_independent_expected_changes():
    from test_public_rating_integration import rated_case

    query, graph = rated_case()
    before = run_attack_query(query, graph)
    actor, group = query["aliases"]["Alice"], query["aliases"]["Admins"]
    after_query = copy.deepcopy(query)
    after_query["runtime_facts"] += [
        {
            "predicate": "membership_usable",
            "subject": actor,
            "target": group,
            "value": False,
            "origin": "blocked_evidence",
            "provenance_reference": "synthetic://269/membership-control",
        }
    ]
    after = run_attack_query(after_query, graph)
    # C and P literals are defined by rated_case's synthetic registries, before execution.
    b = before.ranking_result["min_effort_to_da_baseline"]
    a = after.ranking_result["min_effort_to_da_baseline"]
    assert b["minimum_effort_value"] == 1 and a["minimum_effort_value"] == 4
    assert b["associated_likelihood_interval"] == ["3/4", "3/4"]
    assert a["associated_likelihood_interval"] == ["1/4", "1/4"]
    assert before.complete and after.complete and after.final_goal_reached
    after_query.pop("rating_resolution")
    unrated = run_attack_query(after_query, graph)
    assert unrated.final_goal_reached and unrated.ranking_result is None


@pytest.mark.parametrize(
    "family,gate",
    [
        ("kerberoasting", "recovery_success"),
        ("rbcd", "effective_descriptor_write"),
        ("rbcd", "delegation_policy_allows"),
    ],
)
def test_additional_technique_remediation_mappings(family, gate):
    if family == "kerberoasting":
        from scripts.research.kerberoasting_probe import synthetic as inputs
    else:
        from scripts.research.rbcd_inputs import inputs
    graph, query = inputs()
    before = run_attack_query(query, graph)
    assert before.complete and len(before.paths) == (1 if family == "kerberoasting" else 3)
    q = copy.deepcopy(query)
    denied = [f for f in q["assumptions"] if f["predicate"] == gate]
    assert denied
    q["runtime_facts"] = [{**f, "value": False, "origin": "blocked_evidence"} for f in denied]
    after = run_attack_query(q, graph)
    assert after.complete and not after.paths and after.status == "blocked"
    if gate == "effective_descriptor_write":
        assert any(a.additions.controlled_service for a in after.attempts)
        assert not any(a.additions.rbcd_descriptor for a in after.attempts)


def test_session_mapping_preserves_host_user_scope_and_material_boundary():
    from test_attack_semantics_transitions import graph_for

    from src.engine.semantics import AttackState, RuntimeContext, TransitionRequest, evaluate

    graph = graph_for("HasSession", "User", "Computer")
    state = AttackState(admin_control={"alice"})
    request = TransitionRequest("recover_session_credential_material", "alice", "alice", "target")
    facts = {
        (p, "alice", "target"): True
        for p in ("session_present", "session_fresh", "credential_accessible")
    }
    positive = evaluate(graph, state, request, RuntimeContext(facts))
    assert positive.additions.credential_material == {"target"}
    assert not positive.additions.usable_identity
    facts[("session_present", "alice", "target")] = False
    denied = evaluate(graph, state, request, RuntimeContext(facts))
    assert denied.status.value == "blocked" and not denied.additions.credential_material


def test_manifest_verified_seamless_runtime_controls():
    import os

    from scripts.research.asrep_inputs import seamless_inputs
    from src.data.manifest import (
        load_manifest,
        raw_file_reference,
        read_verified_snapshot_file,
        verify_manifest,
    )

    raw_dir = os.environ.get("REMEDIATION_SEAMLESS_RAW_DIR")
    if not raw_dir:
        pytest.skip("Set REMEDIATION_SEAMLESS_RAW_DIR to manifest-verified private inputs")
    spec = read(ROOT / "docs/research/scenarios/week4-seamless-v1.json")
    manifest_path = ROOT / "data/samples/manifests/seamless-raw-v1.json"
    manifest = load_manifest(manifest_path)
    assert verify_manifest(raw_dir, manifest) == []
    graph, base, _, evidence = seamless_inputs(raw_dir, "7368cac505b3d19331cb8a688114107e91134f25")
    computers = json.loads(
        read_verified_snapshot_file(
            Path(raw_dir), manifest, raw_file_reference(manifest, "20210920185958_computers.json")
        )
    )
    # Exact canonical identifier is checked against the graph, never guessed from a name.
    x = computers["computers"][1]["ObjectIdentifier"]
    assert graph.node(x)["kind"] == "Computer"
    ids = {
        "X": x,
        "V_A": base["initial_state"]["known_identity"][0],
        "C0": base["target"],
        "G_DA": base["checkpoint_goal"]["target"],
    }
    query = copy.deepcopy(base)
    query.update(
        source_foothold=x,
        initial_actor=x,
        authentication_context=x,
        allowed_techniques=spec["allowed_techniques"],
        budget=spec["budget"],
        scenario_reference="remediation269-seamless",
    )
    query["initial_state"] = {
        "control": [],
        "known_identity": [ids["V_A"]],
        "asrep_request_capability": [[x, x]],
    }
    query["assumptions"] = []
    for predicate, subject, target in spec["assumptions"]:
        metadata = {"declared_by": "269-independent-acceptance", "authentication_context": x}
        if predicate == "recovery_success":
            metadata.update(spec["recovery_metadata"])
        query["assumptions"].append(
            dict(
                predicate=predicate,
                subject=ids[subject],
                target=ids[target],
                value=True,
                scope="remediation269-seamless",
                rationale="Conditional prediction, not observed execution",
                provenance_reference="scenario://269/seamless",
                assumption_metadata=metadata,
            )
        )
    canonical, facts = graph.to_canonical(), graph.snapshot_facts
    assert facts.lookup(ids["V_A"], "dontreqpreauth").value is True
    assert evidence["preauth_evidence_count"] > 0
    summaries = {}
    expected = {
        "before": ("success", 1, False),
        "admin_channel_deny": ("blocked", 0, False),
        "membership_only": ("success", 1, False),
        "missing_recovery": ("indeterminate", 0, False),
        "step_cap": ("truncated", 0, True),
    }
    for case, (status, paths, truncated) in expected.items():
        q = copy.deepcopy(query)
        if case in {"admin_channel_deny", "membership_only"}:
            predicate = "admin_channel" if case == "admin_channel_deny" else "membership_usable"
            target = ids["C0"] if case == "admin_channel_deny" else ids["G_DA"]
            q["runtime_facts"] = [
                dict(
                    predicate=predicate,
                    subject=ids["V_A"],
                    target=target,
                    value=False,
                    origin="blocked_evidence",
                    rationale="Declared counterfactual control, not observed mitigation",
                    provenance_reference="scenario://269/seamless-negative",
                )
            ]
        elif case == "missing_recovery":
            q["assumptions"] = [f for f in q["assumptions"] if f["predicate"] != "recovery_success"]
        elif case == "step_cap":
            q["budget"]["max_steps"] = 3
        result = run_attack_query(q, graph)
        assert (result.status, len(result.paths), result.truncated) == (status, paths, truncated)
        assert result.ranking_result is None
        if paths:
            assert [
                s.result.request.technique_id for s in result.paths[0].transition_history
            ] == spec["allowed_techniques"]
        if case == "admin_channel_deny":
            assert result.complete and not result.checkpoint_reached
        summaries[case] = {
            "status": status,
            "programs": paths,
            "truncated": truncated,
            "complete": result.complete,
            "expansions": result.expansions,
        }
    assert graph.to_canonical() == canonical and graph.snapshot_facts == facts
    assert verify_manifest(raw_dir, manifest) == []
    from scripts.research.remediation_acceptance import sha

    admin_edges = [
        e
        for e in canonical["edges"]
        if (e["source"], e["target"], e["kind"]) == (ids["V_A"], ids["C0"], "AdminTo")
    ]
    assert len(admin_edges) == 1 and len(admin_edges[0]["provenance"]) == 2
    report = {
        "schema_version": "1.0.0",
        "engine_revision": "7368cac505b3d19331cb8a688114107e91134f25",
        "raw_manifest_sha256": sha(manifest_path),
        "semantic_catalog_sha256": sha(ROOT / "configs/attack_semantics.yml"),
        "evidence_ids": {
            "V_A_AdminTo_C0": admin_edges[0]["id"],
            "V_A_preauth": "20210920185958_users.json#/users/1700/Properties/dontreqpreauth",
        },
        "admin_support": [
            {k: p[k] for k in ("attribute", "record_locator") if k in p}
            for p in admin_edges[0]["provenance"]
        ],
        "snapshot_id": manifest["snapshot_id"],
        "verified_raw_files": len(manifest["files"]),
        "nodes": len(canonical["nodes"]),
        "edges": len(canonical["edges"]),
        "scope": (
            "one source X, one host goal C0, four-technique allow-list, eight explicit assumptions"
        ),
        "cases": summaries,
        "preauth_evidence_count": evidence["preauth_evidence_count"],
        "raw_graph_unchanged": True,
        "limitations": [
            "Conditional prediction; no observed attack or deployed remediation",
            "No counterfactual snapshot-fact or ACL executor yet",
            "No full-snapshot batch or DA/EA reachability claim",
            "No C/P adoption or risk reduction claim",
            "Missing recovery and step cap cannot prove disconnection",
        ],
    }
    folder = ROOT / "reports/generated/remediation269"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "seamless-summary.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n"
    )


@pytest.mark.parametrize(
    "bad",
    [
        "invented_program_fraction",
        "invented_disconnected_source",
        "exact_without_proof",
        "unreachable_effort",
        "nonexistent_p_program",
        "missing_cell",
        "wrong_exposure_set",
        "cut_without_trace",
    ],
)
def test_result_summary_and_numeric_statuses_are_fail_closed(bad):
    from scripts.research.remediation_acceptance import validate_result

    result = read(FIX / "result-v1.1.json")
    cell = result["cells"][0]
    if bad == "invented_program_fraction":
        result["summary"]["programs_cut"].update(numerator=100, denominator=100)
    elif bad == "invented_disconnected_source":
        result["summary"]["fully_disconnected_sources"] = ["unrequested-source"]
    elif bad == "exact_without_proof":
        cell["effort"].update(status="exact", before=1)
    elif bad == "unreachable_effort":
        cell["effort"].update(
            status="exact", before=1, after=0, delta=-1, unit="test", basis_refs=["test"]
        )
    elif bad == "nonexistent_p_program":
        cell["conditional_p"].update(
            status="comparable",
            before_interval=[1, 1],
            after_interval=[0, 0],
            delta_interval=[-1, -1],
            before_program_id="alice-D",
            after_program_id="nonexistent",
            comparison_scope_digest="sha256:" + "a" * 64,
            basis_refs=["test"],
        )
    elif bad == "missing_cell":
        result["cells"].pop()
    elif bad == "wrong_exposure_set":
        result["summary"]["exposed_sources_after"] = ["alice"]
    else:
        cell["replay_failures"] = []
    with pytest.raises(ValueError):
        validate_result(result)


def test_unresolved_overlay_cannot_disconnect_sources():
    from scripts.research.remediation_acceptance import validate_result

    result = read(FIX / "result-v1.1.json")
    result["overlay_disposition"] = "unresolved"
    for cell in result["cells"]:
        cell.update(
            affected=False,
            affected_program_ids=[],
            cut_program_ids=[],
            cut_route_ids=[],
            replay_failures=[],
            disconnected=False,
        )
    result["summary"].update(affected_sources=[], proven_disconnected_pairs=[])
    for name in ("programs_cut", "routes_cut", "pairs_disconnected"):
        result["summary"][name].update(numerator=0, percent=0, scope="observed_corpus_only")
    with pytest.raises(ValueError):
        validate_result(result)


def test_incomparable_p_cannot_manufacture_zero_on_disconnection():
    from scripts.research.remediation_acceptance import validate_result

    result = read(FIX / "result-v1.1.json")
    result["cells"][0]["conditional_p"].update(status="incomparable", after_interval=[0, 0])
    with pytest.raises(ValueError):
        validate_result(result)
