"""Independent #218 AS-REP projections; executable mapping still awaits A review."""

import copy
import json
from dataclasses import asdict, replace
from pathlib import Path

import pytest

from scripts.research.asrep_inputs import C, G, V, X, inputs, ranking_inputs
from src.engine.query import materialize_query, run_attack_query
from src.engine.semantics import AttackState, apply_transition
from src.engine.semantics.credentials import replay_path
from src.engine.semantics.state import CredentialArtifact
from src.engine.semantics.transitions import Status
from src.parser.snapshot_facts import FactEvidence, SnapshotFact, SnapshotFacts

ORACLE = json.loads((Path(__file__).parent / "fixtures/asrep/oracle.json").read_text())


def projected(state):
    return [
        name
        for name, present in (
            ("material", bool(state.asrep_material)),
            ("secret", bool(state.recovered_secret)),
            ("usable", (V, X) in state.usable_identity),
            ("member", (V, G) in state.effective_member),
            ("admin", C in state.admin_control),
        )
        if present
    ]


def program(path):
    return [s.result.request.technique_id for s in path.transition_history]


def preauth(graph, value):
    old = graph.snapshot_facts.lookup(V, "dontreqpreauth")
    evidence = (
        ()
        if value is None
        else tuple(FactEvidence(json.dumps(value), e.provenance) for e in old.evidence)
    )
    fact = SnapshotFact(
        V, "dontreqpreauth", "unknown" if value is None else "known", value, evidence
    )
    facts = SnapshotFacts(
        graph.snapshot_facts.snapshot_id, graph.snapshot_facts.graph_sha256, (fact,)
    )
    # Explicit separate snapshot view; never edit bound input facts.
    from src.engine.graph import EngineGraph
    from src.parser.snapshot_facts import serialize_snapshot

    return EngineGraph.from_snapshot(serialize_snapshot(graph.to_canonical(), facts))


def test_positive_exact_program_six_states_and_immutable_boundaries():
    graph, q = inputs()
    original = copy.deepcopy(q)
    canonical = graph.to_canonical()
    facts = graph.snapshot_facts
    initial = materialize_query(q, graph).initial_attack_state
    assert not initial.control and not initial.usable_identity and not initial.recovered_secret
    assert graph.snapshot_facts.lookup(V, "has_spn").status == "unknown"
    result = run_attack_query(q, graph)
    assert result.final_goal_reached and result.checkpoint_reached and result.complete
    assert [program(p) for p in result.paths] == [ORACLE["program"]]
    path = result.paths[0]
    assert [s.result.request.actor for s in path.transition_history] == ORACLE["actors"]
    states = [path.transition_history[0].result.before]
    for step in path.transition_history:
        states.append(apply_transition(states[-1], step.result))
    assert [projected(s) for s in states] == ORACLE["states"]
    assert [s.derived_from_step for s in path.transition_history[:3]] == [None, 0, 1]
    assert path.transition_edge_ids[:3] == (None, None, None)
    assert replay_path(path, graph) == path.final_state
    for state in states:
        assert not state.control and not state.service_ticket_material
        assert not state.reset_password_control and not state.authentication_control
    assert next(iter(states[1].asrep_material)).form == "kerberos_asrep"
    assert any(
        "Properties.dontreqpreauth" in p for p in next(iter(states[2].recovered_secret)).provenance
    )
    assert graph.to_canonical() == canonical and graph.snapshot_facts == facts and q == original
    assert run_attack_query(q, graph).search_result == result.search_result


@pytest.mark.parametrize("gate,prefix", list(ORACLE["cutoffs"].items()))
@pytest.mark.parametrize("value,status", [(False, Status.BLOCKED), (None, Status.INDETERMINATE)])
def test_exact_cutoffs_and_success_prefixes(gate, prefix, value, status):
    graph, q = inputs()
    if gate == "dontreqpreauth":
        graph = preauth(graph, value)
    else:
        removed = [f for f in q["assumptions"] if f["predicate"] == gate]
        q["assumptions"] = [f for f in q["assumptions"] if f["predicate"] != gate]
        # Isolate request KDC; activation KDC remains available.
        if gate == "network_kdc_reachable":
            q["assumptions"] += [f for f in removed if f["subject"] != X]
            removed = [f for f in removed if f["subject"] == X]
        if value is False:
            q["runtime_facts"] = [{**f, "value": False} for f in removed]
    result = run_attack_query(q, graph)
    assert not result.paths and not result.final_goal_reached
    success = [a for a in result.attempts if a.status == Status.APPLICABLE]
    assert [a.request.technique_id for a in success] == ORACLE["program"][:prefix]
    attempt = result.attempts[-1]
    assert attempt.status == status and attempt.additions == AttackState()
    assert projected(attempt.before) == ORACLE["states"][prefix]
    assert result.checkpoint_reached == (prefix == 4)


@pytest.mark.parametrize("field", ["known_identity", "asrep_request_capability"])
def test_declared_knowledge_and_request_capability_required(field):
    graph, q = inputs()
    q["initial_state"][field] = []
    result = run_attack_query(q, graph)
    assert not result.final_goal_reached
    assert not any(a.additions.asrep_material for a in result.attempts)


def test_false_veto_material_only_recovery_scope_and_wrong_runtime_context():
    graph, q = inputs()
    q["runtime_facts"] = [
        {
            "predicate": "asrep_request_accepted",
            "subject": X,
            "target": V,
            "value": False,
            "provenance_reference": "synthetic://deny",
        }
    ]
    r = run_attack_query(q, graph)
    assert r.attempts[0].status == Status.BLOCKED
    assert r.materialized_query.rejected_assumptions and not r.attempts[0].additions.asrep_material
    for mode in ("missing_horizon", "wrong_context"):
        graph, q = inputs()
        recovery = next(f for f in q["assumptions"] if f["predicate"] == "recovery_success")
        if mode == "missing_horizon":
            recovery["assumption_metadata"].pop("horizon")
        else:
            recovery["assumption_metadata"]["authentication_context"] = C
        r = run_attack_query(q, graph)
        assert projected(r.attempts[-1].before) == ["material"]
        assert r.attempts[-1].status == Status.INDETERMINATE
        assert not r.attempts[-1].additions.recovered_secret


@pytest.mark.parametrize("enabled,status", [(False, Status.BLOCKED), (None, Status.INDETERMINATE)])
@pytest.mark.parametrize("reuse_secret", [False, True])
def test_request_and_activation_account_eligibility(enabled, status, reuse_secret):
    graph, q = inputs()
    from src.engine.graph import EngineGraph
    from src.parser.snapshot_facts import graph_digest, serialize_snapshot

    canonical = graph.to_canonical()
    node = next(n for n in canonical["nodes"] if n["id"] == V)
    if enabled is None:
        node.pop("enabled")
    else:
        node["enabled"] = enabled
    facts = replace(graph.snapshot_facts, graph_sha256=graph_digest(canonical))
    graph = EngineGraph.from_snapshot(serialize_snapshot(canonical, facts))
    if reuse_secret:
        q["initial_state"]["recovered_secret"] = [
            asdict(CredentialArtifact(V, X, "password", ("synthetic://reuse",)))
        ]
    r = run_attack_query(q, graph)
    assert len(r.attempts) == 1
    attempt = r.attempts[0]
    assert attempt.status == status
    assert attempt.request.technique_id == (
        "activate_recovered_identity" if reuse_secret else "asrep_request"
    )
    assert projected(attempt.before) == (["secret"] if reuse_secret else [])
    assert attempt.additions == AttackState()
    assert (
        "actor_enabled" in (attempt.failed + attempt.unknown)
        if reuse_secret
        else "target_enabled" in (attempt.failed + attempt.unknown)
    )


@pytest.mark.parametrize(
    "reuse,expected,work",
    [
        ("material", ORACLE["program"][1:], 3),
        ("secret", ORACLE["secret_program"], 2),
        ("identity", ORACLE["identity_program"], 1),
    ],
)
def test_reuse_original_query_actor_and_ranking(reuse, expected, work):
    graph, q = inputs()
    if reuse == "identity":
        q["initial_state"]["usable_identity"] = [[V, X]]
    else:
        field, form = (
            ("asrep_material", "kerberos_asrep")
            if reuse == "material"
            else ("recovered_secret", "password")
        )
        q["initial_state"][field] = [asdict(CredentialArtifact(V, X, form, ("synthetic://reuse",)))]
    payload, bindings = ranking_inputs(graph, q)
    result = run_attack_query(q, graph, action_bindings=bindings, ranking_query=payload)
    assert [program(p) for p in result.paths] == [expected]
    assert q["initial_actor"] == X
    assessment = result.ranking_result["diagnostics"]["generated_0001"]["assessment"]
    assert len(assessment["program"]) == work
    assert assessment["effort_status"] == "unrated" and assessment["effort"] is None
    assert assessment["likelihood_interval"] is None and assessment["impact"] is None
    assert not result.is_minimum_proven_over_scope


def test_extension_off_wrong_identity_context_and_caps():
    graph, q = inputs()
    on = run_attack_query(q, graph)
    off = copy.deepcopy(q)
    off["allowed_techniques"] = ORACLE["identity_program"]
    assert not run_attack_query(off, graph).final_goal_reached and on.final_goal_reached
    off["initial_state"]["usable_identity"] = [[V, C]]
    assert not run_attack_query(off, graph).final_goal_reached
    for budget in ({"max_steps": 1}, {"max_expansions": 1}, {"max_paths": 1}):
        capped = copy.deepcopy(q)
        capped["budget"].update(budget)
        result = run_attack_query(capped, graph)
        assert not result.is_minimum_proven_over_scope
        assert not result.is_no_path_proven_over_scope
        if "max_paths" in budget:
            # The independent fixture has one first-goal program. Exhausting it
            # at the path limit leaves no supported candidate or pending branch.
            assert result.complete and not result.truncated
            assert result.truncation_reason is None
            assert [program(p) for p in result.paths] == [ORACLE["program"]]
        else:
            assert result.truncated and not result.complete
            assert not result.paths
            assert [a.request.technique_id for a in result.attempts] == ORACLE["program"][:1]
            assert (
                projected(apply_transition(result.attempts[0].before, result.attempts[0]))
                == ORACLE["states"][1]
            )


def test_positive_ranking_and_fabricated_snapshot_lineage_rejected():
    from src.engine.ranking.orchestration import evaluate_search_candidates

    graph, q = inputs()
    payload, bindings = ranking_inputs(graph, q)
    result = run_attack_query(q, graph, action_bindings=bindings, ranking_query=payload)
    ranking = result.ranking_result
    assert ranking["search_audit"]["candidates_adapted"] == 1
    assert len(ranking["diagnostics"]["generated_0001"]["assessment"]["program"]) == 4
    path = result.paths[0]
    actions = [
        bindings[
            (
                s.result.request.technique_id,
                s.result.request.actor,
                s.result.request.source,
                s.result.request.target,
            )
        ]
        for s in path.transition_history
    ]
    supplied = [
        {
            "candidate_id": "generated_0001",
            "target_asset_id": C,
            "path_result": path,
            "action_mapping": actions,
        }
    ]
    lost = evaluate_search_candidates(payload, supplied, canonical_graph=graph.to_canonical())
    assert lost["result_payload"]["search_audit"]["candidates_adapted"] == 0
    from src.engine.ranking import PathRankingEngine
    from src.engine.ranking.adapter_145 import adapt_search_candidate

    envelope = adapt_search_candidate(
        path_result=path,
        candidate_id="generated_0001",
        target_asset_id=C,
        query_metadata={
            **payload["query_metadata"],
            "target_impact_assessments": payload["target_impact_assessments"],
        },
        action_mapping=actions,
        route_id="fabricated",
        bound_actions_catalog=payload["bound_actions"],
    )
    # Complete inline evidence still cannot manufacture the in-process verified binding.
    from src.engine.ranking.models import RankingValidationError

    with pytest.raises(RankingValidationError, match="verified|replay|binding"):
        PathRankingEngine().evaluate(payload, [envelope])


@pytest.mark.parametrize("value,status", [(False, Status.BLOCKED), (None, Status.INDETERMINATE)])
def test_activation_kdc_cutoff(value, status):
    graph, q = inputs()
    q["assumptions"] = [
        f
        for f in q["assumptions"]
        if (f["predicate"], f["subject"]) != ("network_kdc_reachable", V)
    ]
    if value is False:
        q["runtime_facts"] = [
            {
                "predicate": "network_kdc_reachable",
                "subject": V,
                "target": X,
                "value": False,
                "provenance_reference": "synthetic://activation-kdc-deny",
            }
        ]
    result = run_attack_query(q, graph)
    assert [a.request.technique_id for a in result.attempts] == ORACLE["program"][:3]
    assert projected(result.attempts[-1].before) == ORACLE["states"][2]
    assert result.attempts[-1].status == status and result.attempts[-1].additions == AttackState()


def test_independent_blocked_account_preserves_success_branch_and_input_facts():
    from src.engine.graph import EngineGraph
    from src.parser.snapshot_facts import graph_digest, serialize_snapshot

    graph, q = inputs()
    canonical = graph.to_canonical()
    other = "S-1-5-21-1000-2000-3000-1701"
    canonical["nodes"].append({**graph.node(V), "id": other})
    evidence = tuple(
        FactEvidence(
            "true", {**dict(e.provenance), "record_id": other, "record_locator": "#/User/" + other}
        )
        for e in graph.snapshot_facts.lookup(V, "dontreqpreauth").evidence
    )
    fact = SnapshotFact(other, "dontreqpreauth", "known", True, evidence)
    facts = replace(
        graph.snapshot_facts,
        graph_sha256=graph_digest(canonical),
        facts=graph.snapshot_facts.facts + (fact,),
    )
    graph = EngineGraph.from_snapshot(serialize_snapshot(canonical, facts))
    q["initial_state"]["known_identity"].append(other)
    q["runtime_facts"] = [
        {
            "predicate": "asrep_request_accepted",
            "subject": X,
            "target": other,
            "value": False,
            "provenance_reference": "synthetic://independent-deny",
        }
    ]
    before = graph.to_canonical()
    result = run_attack_query(q, graph)
    assert [program(p) for p in result.paths] == [ORACLE["program"]]
    assert any(a.request.target == other and a.status == Status.BLOCKED for a in result.attempts)
    assert all(not any(v.owner == other for v in a.before.asrep_material) for a in result.attempts)
    assert graph.to_canonical() == before and graph.snapshot_facts == facts


@pytest.mark.parametrize(
    "mutation", ["query", "snapshot", "target", "action", "context", "evidence"]
)
def test_verified_binding_rejects_changed_lineage(mutation):
    from src.engine.ranking import PathRankingEngine, RankingValidationError
    from src.engine.ranking.adapter_145 import adapt_search_candidate
    from src.engine.ranking.verification import verify_search_envelope

    graph, q = inputs()
    payload, bindings = ranking_inputs(graph, q)
    path = run_attack_query(q, graph).paths[0]
    actions = [
        bindings[
            (
                s.result.request.technique_id,
                s.result.request.actor,
                s.result.request.source,
                s.result.request.target,
            )
        ]
        for s in path.transition_history
    ]
    envelope = adapt_search_candidate(
        path_result=path,
        candidate_id="verified",
        target_asset_id=C,
        query_metadata={
            **payload["query_metadata"],
            "target_impact_assessments": payload["target_impact_assessments"],
        },
        action_mapping=actions,
        route_id="route",
        bound_actions_catalog=payload["bound_actions"],
    )
    binding = verify_search_envelope(path, graph, envelope, payload["query_metadata"])
    modified, scoring = copy.deepcopy(envelope), copy.deepcopy(payload)
    if mutation in {"query", "snapshot"}:
        field = "query_id" if mutation == "query" else "snapshot_id"
        scoring["query_metadata"][field] = "different"
        modified["scope_binding"][field] = "different"
    elif mutation == "target":
        modified["target_asset_id"] = X
    elif mutation == "action":
        modified["bound_action_ids"][0] = actions[1]
    elif mutation == "context":
        modified["transition_lineage"][2]["target"] = C
    else:
        modified["transition_lineage"][0]["snapshot_evidence"][0] = "{}"
    with pytest.raises(RankingValidationError):
        PathRankingEngine().evaluate(scoring, [modified], semantic_bindings={"verified": binding})


def test_adapter_exclusion_is_diagnostic_and_lowers_coverage():
    graph, q = inputs()
    payload, bindings = ranking_inputs(graph, q)
    bindings[("asrep_request", X, X, V)] = "unknown-action"
    result = run_attack_query(q, graph, action_bindings=bindings, ranking_query=payload)
    assert result.final_goal_reached and not result.is_minimum_proven_over_scope
    audit = result.ranking_result["search_audit"]
    assert audit["candidates_adapted"] == 0
    assert audit["candidates_received"] == 1
    assert audit["candidates_rejected_by_adapter"] == 1
    assert result.binding_diagnostics


def test_cli_result_package_reuses_existing_entry_point():
    from src.engine.query_cli import execute

    graph, q = inputs()
    payload, bindings = ranking_inputs(graph, q)
    q["ranking_query"] = payload
    q["action_bindings"] = [[list(k), v] for k, v in bindings.items()]
    result = execute(q, graph)
    assert result["final_goal_reached"] and result["complete"]
    assert result["ranking_result"]["search_audit"]["candidates_adapted"] == 1


@pytest.mark.parametrize("value,status", [(False, Status.BLOCKED), (None, Status.INDETERMINATE)])
def test_inline_preauth_assumptions_do_not_create_snapshot_authority(value, status):
    graph, q = inputs()
    graph = preauth(graph, value)
    q["assumptions"].append(
        {
            "predicate": "dontreqpreauth",
            "subject": X,
            "target": V,
            "value": True,
            "scope": "synthetic-228/H0",
            "rationale": "Optimistic caller claim",
            "provenance_reference": "synthetic://caller-preauth",
        }
    )
    result = run_attack_query(q, graph)
    assert result.attempts[0].status == status
    assert result.attempts[0].additions == AttackState()


def test_wrong_request_scope_and_secret_reuse_still_needs_activation():
    graph, q = inputs()
    q["initial_state"]["asrep_request_capability"] = [[X, C]]
    assert not run_attack_query(q, graph).final_goal_reached
    graph, q = inputs()
    q["initial_state"]["recovered_secret"] = [
        asdict(CredentialArtifact(V, X, "password", ("synthetic://valid-secret",)))
    ]
    q["assumptions"] = [f for f in q["assumptions"] if f["predicate"] != "authentication_accepted"]
    result = run_attack_query(q, graph)
    assert [a.request.technique_id for a in result.attempts] == ORACLE["program"][2:3]
    assert result.attempts[0].status == Status.INDETERMINATE
    assert (
        not result.attempts[0].before.asrep_material
        and not result.attempts[0].additions.usable_identity
    )


def test_asrep_and_service_ticket_artifacts_are_distinct():
    with pytest.raises(ValueError, match="typed artifacts"):
        AttackState(
            asrep_material={
                CredentialArtifact(V, X, "kerberos_service_ticket", ("synthetic://wrong-form",))
            }
        )
    graph, q = inputs()
    q["allowed_techniques"] = ORACLE["program"][1:]
    q["initial_state"]["service_ticket_material"] = [
        asdict(CredentialArtifact(V, X, "kerberos_service_ticket", ("synthetic://ticket",)))
    ]
    assert not run_attack_query(q, graph).attempts


def test_initial_asset_goal_uses_validated_zero_work_disposition():
    graph, q = inputs()
    q["initial_state"]["admin_control"] = [C]
    payload, bindings = ranking_inputs(graph, q)
    result = run_attack_query(q, graph, action_bindings=bindings, ranking_query=payload)
    assert result.final_goal_reached and result.paths[0].transition_history == ()
    assert result.min_effort["disposition"] == "semantic_initial_goal_zero_work"
    assert result.min_effort["ranking_status"] == "not_applicable"
    assert result.ranking_result["pareto_frontier"] == []
    assert result.ranking_result["eligible_candidates"] == {}
    assert result.ranking_result["min_effort_to_da_baseline"]["minimum_effort_value"] is None


def test_private_preparation_requires_manifest_inputs(tmp_path):
    from scripts.research.asrep_inputs import seamless_inputs

    with pytest.raises(FileNotFoundError, match="private"):
        seamless_inputs(tmp_path / "absent", "source-pin")
    with pytest.raises(ValueError, match="manifest"):
        seamless_inputs(tmp_path, "source-pin")


@pytest.mark.parametrize("reuse", [None, "material", "secret", "identity"])
def test_initial_declarations_never_become_observations(reuse):
    from src.engine.ranking.facts import resolve_facts_ledger

    graph, q = inputs()
    if reuse == "identity":
        q["initial_state"]["usable_identity"] = [[V, X]]
    elif reuse:
        field, form = (
            ("asrep_material", "kerberos_asrep")
            if reuse == "material"
            else ("recovered_secret", "password")
        )
        q["initial_state"][field] = [asdict(CredentialArtifact(V, X, form, ("synthetic://reuse",)))]
    payload, _ = ranking_inputs(graph, q)
    ledger = payload["facts_ledger"]
    declared = {"material", "secret", "usable", "member", "admin"}
    assert not declared.intersection(f["predicate"] for f in ledger["observed_facts"])
    assumptions = {f["predicate"]: f for f in ledger["assumed_facts"]}
    resolved = resolve_facts_ledger(ledger, "scenario")
    positive = {"identity": "usable"}.get(reuse, reuse)
    for predicate in declared:
        expected = predicate == positive
        assert assumptions[predicate]["truth_value"] is expected
        assert resolved[predicate]["disposition"] == (
            "permitted_runtime_assumption" if expected else "assumed_false"
        )
        assert "telemetry" not in resolved[predicate]["reason"]
        assert "snapshot" not in resolved[predicate]["reason"]
    evidence_only = resolve_facts_ledger(ledger, "evidence_only")
    assert all(evidence_only[p]["value"] == "Unknown" for p in declared)


def test_kerberoasting_shared_helper_preserves_reviewed_identifiers():
    from scripts.research.kerberoasting_probe import ranking_inputs, synthetic

    graph, q = synthetic()
    payload, _ = ranking_inputs(graph, q)
    assert payload["query_metadata"]["work_boundary"] == "216-scoped-password-recovery"
    assert payload["query_metadata"]["target_goal"]["goal_id"] == "admin-216"
    for bucket in ("observed_facts", "assumed_facts"):
        assert all(
            f["provenance_reference"] == "synthetic://216/binding"
            for f in payload["facts_ledger"][bucket]
        )
    assert all(
        u["technical_source"] == "synthetic://216/event-binding"
        for u in payload["work_units_ledger"].values()
    )
