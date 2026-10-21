"""Independent #218 RBCD projections; executable mapping for A review."""

import copy
import json
from dataclasses import asdict
from pathlib import Path

import pytest

from scripts.research.rbcd_inputs import (
    C_R,
    U_R,
    M,
    P,
    X,
    build_assumed_query,
    inputs,
    ranking_inputs,
)
from src.engine.query import materialize_query, run_attack_query
from src.engine.semantics import apply_transition
from src.engine.semantics.credentials import replay_path
from src.engine.semantics.rbcd_types import DelegationArtifact, DelegationBinding
from src.engine.semantics.transitions import Status
from src.parser.snapshot_facts import FactEvidence, SnapshotFact, SnapshotFacts

ORACLE = json.loads((Path(__file__).parent / "fixtures/rbcd/oracle.json").read_text())


def projected(state):
    res = []
    if state.rbcd_secret:
        res.append("reset_M")
    if state.controlled_service:
        res.append("service_M")
    if state.rbcd_descriptor:
        res.append("descriptor_M_C_R")
    if state.delegated_context:
        res.append("delegated_P_C_R")
    if state.admin_control:
        res.append("admin_C_R")
    return res


def program(path):
    return [s.result.request.technique_id for s in path.transition_history]


def test_positive_three_orderings_eight_projected_states_and_lineage():
    graph, q = inputs()
    original = copy.deepcopy(q)
    canonical = graph.to_canonical()
    facts = graph.snapshot_facts

    initial = materialize_query(q, graph).initial_attack_state
    assert not initial.rbcd_secret
    assert not initial.controlled_service
    assert not initial.rbcd_descriptor
    assert not initial.delegated_context
    assert not initial.admin_control

    result = run_attack_query(q, graph)
    assert result.final_goal_reached and result.complete
    assert len(result.paths) == 3

    actual_programs = [program(p) for p in result.paths]
    for expected_prog in ORACLE["programs"]:
        assert expected_prog in actual_programs

    # Verify all 8 reachable projected states
    all_states = set()
    for p in result.paths:
        cur = p.transition_history[0].result.before
        all_states.add(tuple(projected(cur)))
        for step in p.transition_history:
            cur = apply_transition(cur, step.result)
            all_states.add(tuple(projected(cur)))

    expected_states = {tuple(s) for s in ORACLE["states"]}
    assert all_states == expected_states
    assert len(all_states) == 8

    # Verify lineage: derived_from_step and edge_ids for each ordering
    for path in result.paths:
        assert replay_path(path, graph) == path.final_state
        prog = program(path)
        steps = path.transition_history
        if prog == ORACLE["programs"][0]:
            # R1, R2, R3, R4, R5
            assert steps[0].edge_id is not None and steps[0].derived_from_step is None
            assert steps[1].edge_id is None and steps[1].derived_from_step == 0
            assert steps[2].edge_id is not None and steps[2].derived_from_step is None
            assert steps[3].edge_id is None and steps[3].derived_from_step == 2
            assert steps[4].edge_id is None and steps[4].derived_from_step == 3
        elif prog == ORACLE["programs"][1]:
            # R1, R3, R2, R4, R5
            assert steps[0].edge_id is not None and steps[0].derived_from_step is None
            assert steps[1].edge_id is not None and steps[1].derived_from_step is None
            assert steps[2].edge_id is None and steps[2].derived_from_step == 0
            assert steps[3].edge_id is None and steps[3].derived_from_step == 2
            assert steps[4].edge_id is None and steps[4].derived_from_step == 3
        elif prog == ORACLE["programs"][2]:
            # R3, R1, R2, R4, R5
            assert steps[0].edge_id is not None and steps[0].derived_from_step is None
            assert steps[1].edge_id is not None and steps[1].derived_from_step is None
            assert steps[2].edge_id is None and steps[2].derived_from_step == 1
            assert steps[3].edge_id is None and steps[3].derived_from_step == 2
            assert steps[4].edge_id is None and steps[4].derived_from_step == 3

    # Canonical graph and snapshot facts immutability
    assert graph.to_canonical() == canonical and graph.snapshot_facts == facts and q == original


@pytest.mark.parametrize(
    "gate,expected_code",
    list(ORACLE["cutoffs"].items()),
)
@pytest.mark.parametrize("value,status", [(False, Status.BLOCKED), (None, Status.INDETERMINATE)])
def test_exact_cutoffs_and_independent_prefixes(gate, expected_code, value, status):
    graph, q = inputs()
    if gate == "has_spn":
        old = graph.snapshot_facts.lookup(M, "has_spn")
        evidence = (
            ()
            if value is None
            else tuple(FactEvidence(json.dumps(value), e.provenance) for e in old.evidence)
        )
        fact = SnapshotFact(M, "has_spn", "unknown" if value is None else "known", value, evidence)
        facts = SnapshotFacts(
            graph.snapshot_facts.snapshot_id, graph.snapshot_facts.graph_sha256, (fact,)
        )
        from src.engine.graph import EngineGraph
        from src.parser.snapshot_facts import serialize_snapshot

        graph = EngineGraph.from_snapshot(serialize_snapshot(graph.to_canonical(), facts))
    else:
        removed = [f for f in q["assumptions"] if f["predicate"] == gate]
        q["assumptions"] = [f for f in q["assumptions"] if f["predicate"] != gate]
        if value is False:
            q["runtime_facts"] = [{**f, "value": False} for f in removed]

    result = run_attack_query(q, graph)
    assert not result.final_goal_reached
    assert not result.paths

    applicable_attempts = [a for a in result.attempts if a.status == Status.APPLICABLE]
    applicable_techs = {a.request.technique_id for a in applicable_attempts}

    # Verify branch independence: when reset fails, descriptor is still configurable
    if gate == "effective_reset_right":
        assert "rbcd_configure_descriptor" in applicable_techs
        assert "rbcd_acquire_secret" not in applicable_techs
    # When descriptor write fails, secret & service preparation are still possible
    elif gate == "effective_descriptor_write":
        assert "rbcd_acquire_secret" in applicable_techs
        assert "rbcd_prepare_service" in applicable_techs
        assert "rbcd_configure_descriptor" not in applicable_techs
    # When SPN fails, reset and descriptor are still possible
    elif gate == "has_spn":
        assert "rbcd_acquire_secret" in applicable_techs
        assert "rbcd_configure_descriptor" in applicable_techs
        assert "rbcd_prepare_service" not in applicable_techs
    # When admin execution fails, delegation was still reached
    elif gate == "admin_execution_context":
        assert "rbcd_delegate_service" in applicable_techs
        assert "rbcd_service_admin" not in applicable_techs


def test_reuse_controlled_service_bypasses_acquisition_and_preparation():
    graph, q = inputs()
    binding = DelegationBinding(**q["rbcd_bindings"][0])
    artifact = DelegationArtifact(binding, ("synthetic://reuse-service-capability",))
    q["initial_state"]["controlled_service"] = [asdict(artifact)]

    result = run_attack_query(q, graph)
    assert result.final_goal_reached
    assert len(result.paths) == 1
    path = result.paths[0]
    assert program(path) == ORACLE["reuse_program"]
    assert len(path.transition_history) == 3


def test_scope_and_counterfactual_acl():
    # R-SCOPE: Target goal shifted to different host without delegation
    graph, q = inputs()
    c_other = X
    q["target"] = c_other
    q["target_goal"]["target"] = c_other
    q["target_goal"]["required_state"]["admin_control"] = [c_other]
    res_scope = run_attack_query(q, graph)
    assert not res_scope.final_goal_reached
    assert not res_scope.paths

    # R-CF-ACL: Withhold descriptor right edge GenericAll from U_R to C_R
    graph, q = inputs()
    q["withheld_relationships"] = [[U_R, "GenericAll", C_R]]
    res_acl = run_attack_query(q, graph)
    assert not res_acl.final_goal_reached
    applicable_techs = {
        a.request.technique_id for a in res_acl.attempts if a.status == Status.APPLICABLE
    }
    assert "rbcd_acquire_secret" in applicable_techs
    assert "rbcd_configure_descriptor" not in applicable_techs

    # R-EXT-OFF: RBCD techniques turned off
    graph, q = inputs()
    q["allowed_techniques"] = []
    res_off = run_attack_query(q, graph)
    assert not res_off.final_goal_reached
    assert not res_off.paths


def test_multiple_delegation_bindings_rejected():
    graph, q = inputs()
    binding2 = dict(q["rbcd_bindings"][0])
    binding2["spn"] = "http/computer28.example.test"
    q["rbcd_bindings"].append(binding2)

    with pytest.raises(ValueError, match="at most one delegation binding"):
        materialize_query(q, graph)


def test_replay_trust_boundary_fabricated_envelope_rejected():
    from src.engine.ranking import PathRankingEngine, RankingValidationError
    from src.engine.ranking.adapter_145 import adapt_search_candidate

    graph, q = inputs()
    payload, bindings = ranking_inputs(graph, q)
    result = run_attack_query(q, graph, action_bindings=bindings, ranking_query=payload)
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
    envelope = adapt_search_candidate(
        path_result=path,
        candidate_id="fabricated_rbcd",
        target_asset_id=C_R,
        query_metadata={
            **payload["query_metadata"],
            "target_impact_assessments": payload["target_impact_assessments"],
        },
        action_mapping=actions,
        route_id="fabricated",
        bound_actions_catalog=payload["bound_actions"],
    )

    with pytest.raises(RankingValidationError, match="verified|replay|binding"):
        PathRankingEngine().evaluate(payload, [envelope])


def test_positive_ranking_adaptation_and_unrated_effort():
    graph, q = inputs()
    payload, bindings = ranking_inputs(graph, q)
    result = run_attack_query(q, graph, action_bindings=bindings, ranking_query=payload)
    audit = result.ranking_result["search_audit"]
    assert audit["candidates_adapted"] == 3
    assert audit["candidates_rejected_by_adapter"] == 0
    assert not result.is_minimum_proven_over_scope

    diag = result.ranking_result["diagnostics"]
    for cid in ("generated_0001", "generated_0002", "generated_0003"):
        asm = diag[cid]["assessment"]
        assert asm["status"] == "feasible"
        assert asm["effort_status"] == "unrated" and asm["effort"] is None
        assert len(asm["program"]) == 5


@pytest.mark.parametrize("prefix,typed_admin", [(3, True), (4, True), (5, True), (3, False)])
def test_same_endpoint_rbcd_ranking_requires_exact_typed_goal_after_first_hit(prefix, typed_admin):
    from src.engine.query import SemanticGoalDescriptor
    from src.engine.ranking import RankingValidationError
    from src.engine.ranking.orchestration import evaluate_search_candidates
    from src.engine.semantics import AttackState

    graph, q = inputs()
    packet, bindings = ranking_inputs(graph, q)
    generated = run_attack_query(q, graph)
    path = next(p for p in generated.paths if program(p) == ORACLE["programs"][0])
    assert path.goal_target is None and path.nodes[-1] == C_R
    retained = path.transition_history[0].result.before
    for step in path.transition_history[:prefix]:
        retained = apply_transition(retained, step.result)
    assert generated.materialized_query.semantic_goal.matches(retained) is (prefix == 5)
    assert path.transition_history[prefix - 1].result.request.target == C_R
    packet["query_metadata"]["semantic_goal"] = generated.materialized_query.semantic_goal.to_dict()
    if not typed_admin:
        goal = SemanticGoalDescriptor(C_R, AttackState(rbcd_descriptor=retained.rbcd_descriptor))
        assert goal.matches(retained)
        packet["query_metadata"]["semantic_goal"] = goal.to_dict()
    packet["query_metadata"]["target_goal"]["required_predicates"] = [
        {3: "descriptor_M_C_R", 4: "delegated_P_C_R", 5: "admin_C_R"}[prefix]
    ]
    mapping = [
        bindings[(r.technique_id, r.actor, r.source, r.target)]
        for r in (s.result.request for s in path.transition_history)
    ]
    candidates = [
        {
            "candidate_id": "same-endpoint",
            "target_asset_id": C_R,
            "path_result": path,
            "action_mapping": mapping,
        }
    ]
    if prefix < 5 and typed_admin:
        with pytest.raises(RankingValidationError, match="executed prefix does not satisfy"):
            evaluate_search_candidates(
                packet,
                candidates,
                canonical_graph=graph.to_canonical(),
                snapshot_facts=graph.snapshot_facts,
            )
        with pytest.raises(RankingValidationError, match="executed prefix does not satisfy"):
            run_attack_query(q, graph, action_bindings=bindings, ranking_query=packet)
    else:
        output = evaluate_search_candidates(
            packet,
            candidates,
            canonical_graph=graph.to_canonical(),
            snapshot_facts=graph.snapshot_facts,
        )["roundtrip_result"]
        for diagnostic in output["diagnostics"].values():
            assert diagnostic["assessment"]["status"] == "feasible"
            assert len(diagnostic["assessment"]["bound_action_ids"]) == prefix
            assert diagnostic["search_trace"]["initial_actor_binding"] is not None


def test_same_endpoint_automatic_rbcd_packet_carries_goal_and_requires_native_proof():
    from src.engine.ranking import RankingValidationError, decode_ranking_query
    from src.engine.ranking.adapter_145 import adapt_search_candidate
    from src.engine.ranking.resolution_service import resolve_generated_rating_inputs
    from src.engine.ranking.validation import validate_candidate_envelope

    graph, q = inputs()
    materialized = materialize_query(q, graph)
    config = {
        "version": "public-rating-resolution/1.1.0",
        "mode": "automatic",
        "policy": "production",
        "registries": {},
        "scope": {
            "query_id": "same-endpoint-rbcd",
            "scenario_id": q["scenario_reference"],
            "scenario_version": "1.0.0",
            "snapshot_id": graph.metadata["snapshot_id"],
            "evaluation_mode": "scenario",
            "work_boundary": "scoped-rbcd-delegation",
            "foothold_node_id": materialized.initial_actor,
            "horizon": "24h",
            "active_work_budget": materialized.budget.max_steps,
            "target_goal": {
                "goal_id": "admin",
                "target_asset_id": C_R,
                "success_event": "admin_execution_on_C_R",
            },
        },
    }
    result = run_attack_query({**q, "rating_resolution": config}, graph)
    packet, candidates, _ = resolve_generated_rating_inputs(
        config, graph, result.materialized_query, result.search_result
    )
    assert packet["query_metadata"]["semantic_goal"] == materialized.semantic_goal.to_dict()
    candidate = candidates[0]
    assert candidate["path_result"].goal_target is None
    envelope = adapt_search_candidate(
        path_result=candidate["path_result"],
        candidate_id=candidate["candidate_id"],
        target_asset_id=C_R,
        query_metadata=packet["query_metadata"],
        action_mapping=candidate["action_mapping"],
        route_id=candidate["route_id"],
        bound_actions_catalog=packet["bound_actions"],
    )
    assert envelope["state_goal_binding"]["target_asset_id"] == C_R
    decoded = decode_ranking_query(packet)
    with pytest.raises(RankingValidationError, match="requires native semantic replay"):
        validate_candidate_envelope(envelope, decoded)
    envelope.pop("state_goal_binding")
    with pytest.raises(RankingValidationError, match="requires its typed state-goal binding"):
        validate_candidate_envelope(envelope, decoded)


@pytest.mark.parametrize("ranking_goal", ["descriptor_M_C_R", "admin_C_R"])
def test_manual_generation_wrapper_preserves_same_endpoint_typed_goal(ranking_goal):
    from src.engine.ranking import RankingValidationError
    from src.engine.ranking.orchestration import generate_and_evaluate_attack_paths

    graph, q = inputs()
    materialized = materialize_query(q, graph)
    packet, bindings = ranking_inputs(graph, q)
    packet["query_metadata"]["target_goal"]["required_predicates"] = [ranking_goal]

    def run():
        return generate_and_evaluate_attack_paths(
            packet,
            graph.to_canonical(),
            actor=materialized.initial_actor,
            initial_state=materialized.initial_attack_state,
            runtime_context=materialized.runtime_context,
            budget=materialized.budget,
            action_bindings=bindings,
            snapshot_facts=graph.snapshot_facts,
            catalog=materialized.catalog,
            scenario_reference=materialized.scenario_reference,
            success_state_predicate=lambda state: True,
            semantic_goal=materialized.semantic_goal,
        )

    if ranking_goal == "descriptor_M_C_R":
        with pytest.raises(RankingValidationError, match="executed prefix does not satisfy"):
            run()
    else:
        result = run()
        assert len(result["search_result"].paths) == 3
        assert all(
            materialized.semantic_goal.matches(p.final_state) for p in result["search_result"].paths
        )
        for diagnostic in result["roundtrip_result"]["diagnostics"].values():
            assert diagnostic["assessment"]["status"] == "feasible"
            assert len(diagnostic["assessment"]["bound_action_ids"]) == 5


def test_known_false_vetoes_optimistic_assumption():
    graph, q = inputs()
    q["runtime_facts"] = [
        {
            "predicate": "s4u_request_accepted",
            "subject": U_R,
            "target": C_R,
            "value": False,
            "provenance_reference": "synthetic://kdc-s4u-deny",
        }
    ]
    result = run_attack_query(q, graph)
    assert not result.final_goal_reached
    assert not result.paths
    failed_attempts = [
        a for a in result.attempts if a.request.technique_id == "rbcd_delegate_service"
    ]
    assert failed_attempts
    assert failed_attempts[0].status == Status.BLOCKED


def test_delegated_context_does_not_confer_domain_admin_or_global_identity():
    graph, q = inputs()
    result = run_attack_query(q, graph)
    assert result.final_goal_reached

    for path in result.paths:
        for step in path.transition_history:
            state = apply_transition(step.result.before, step.result)
            assert not state.control
            assert not state.effective_member


def test_cli_execution_deterministic():
    from src.engine.query_cli import execute

    graph, q = inputs()
    payload, bindings = ranking_inputs(graph, q)
    q["ranking_query"] = payload
    q["action_bindings"] = [[list(k), v] for k, v in bindings.items()]

    run1 = execute(copy.deepcopy(q), graph)
    run2 = execute(copy.deepcopy(q), graph)

    assert run1["final_goal_reached"] and run2["final_goal_reached"]
    assert run1["complete"] and run2["complete"]
    assert len(run1["candidates"]) == len(run2["candidates"]) == 3
    assert run1["ranking_result"]["search_audit"]["candidates_adapted"] == 3
    assert run2["ranking_result"]["search_audit"]["candidates_adapted"] == 3


def test_seamless_inputs_requires_verified_manifest(tmp_path):
    from scripts.research.rbcd_inputs import seamless_inputs

    with pytest.raises(FileNotFoundError, match="private"):
        seamless_inputs(tmp_path / "absent", "source-pin")
    with pytest.raises(ValueError, match="manifest"):
        seamless_inputs(tmp_path, "source-pin")


def test_rbcd_work_unit_event_bindings_explicit():
    graph, q = inputs()
    payload, _ = ranking_inputs(graph, q)
    units = payload["work_units_ledger"]

    assert set(units) == {
        "work_rbcd_acquire_secret",
        "work_rbcd_prepare_service",
        "work_rbcd_configure_descriptor",
        "work_rbcd_delegate_service",
        "work_rbcd_service_admin",
    }

    # R1: Acquire secret on M
    u1 = units["work_rbcd_acquire_secret"]
    assert u1["event_binding"]["owner"] == M
    assert u1["event_binding"]["authentication_context"] == X
    assert u1["event_binding"]["success_event"] == "rbcd_secret"

    # R2: Prepare service capability on M
    u2 = units["work_rbcd_prepare_service"]
    assert u2["event_binding"]["owner"] == M
    assert u2["event_binding"]["authentication_context"] == X
    assert u2["event_binding"]["success_event"] == "controlled_service"

    # R3: Configure descriptor on C_R
    u3 = units["work_rbcd_configure_descriptor"]
    assert u3["event_binding"]["owner"] == C_R
    assert u3["event_binding"]["authentication_context"] == X
    assert u3["event_binding"]["success_event"] == "rbcd_descriptor"

    # R4: Delegated service context for P on C_R
    u4 = units["work_rbcd_delegate_service"]
    assert u4["event_binding"]["owner"] == P
    assert u4["event_binding"]["authentication_context"] == C_R
    assert u4["event_binding"]["success_event"] == "delegated_service_context"

    # R5: Admin execution on C_R
    u5 = units["work_rbcd_service_admin"]
    assert u5["event_binding"]["owner"] == C_R
    assert u5["event_binding"]["authentication_context"] == C_R
    assert u5["event_binding"]["success_event"] == "admin_execution_on_C_R"

    for u in units.values():
        assert u["rating_status"] == "unrated"
        assert u["computed_cost"] is None
        assert u["effort_cost"] is None
        assert u["missing_basis_reasons"] == ["no_numeric_basis"]


def test_build_assumed_query_distinct_from_raw():
    graph, _ = inputs()
    raw_path = Path(__file__).parent / "fixtures/rbcd/query-raw.json"
    raw = json.loads(raw_path.read_text(encoding="utf-8"))
    assert raw["assumptions"] == []

    assumed = build_assumed_query(
        raw,
        scope="synthetic-229/assumed",
        rationale="Declared synthetic outcome; not observed success",
        provenance_reference="synthetic://229/outcomes",
    )
    assert assumed is not raw
    assert raw["assumptions"] == []
    for k in raw:
        if k != "assumptions":
            assert raw[k] == assumed[k]

    assert len(assumed["assumptions"]) == 20
    for asm in assumed["assumptions"]:
        assert asm["value"] is True
        assert asm["scope"] == "synthetic-229/assumed"
        assert asm["rationale"] == "Declared synthetic outcome; not observed success"
        assert asm["provenance_reference"] == "synthetic://229/outcomes"
        assert asm["assumption_metadata"]["controller"] == U_R
        assert asm["assumption_metadata"]["principal"] == M
        assert asm["assumption_metadata"]["impersonated"] == P
        assert asm["assumption_metadata"]["target"] == C_R

    # RAW query produces no paths under missing assumptions
    raw_res = run_attack_query(raw, graph)
    assert not raw_res.final_goal_reached
    assert len(raw_res.paths) == 0

    # ASSUMED query produces all 3 paths under declared assumptions
    assumed_res = run_attack_query(assumed, graph)
    assert assumed_res.final_goal_reached
    assert len(assumed_res.paths) == 3

    # Canonical graph remains identical
    assert graph.to_canonical() == inputs()[0].to_canonical()
