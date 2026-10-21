"""Independent #218 expectations mapped to the #216 API; no expected-from-actual oracle."""

import copy
from dataclasses import asdict, replace

import pytest

from scripts.research.kerberoasting_probe import PROGRAM, C, G, U, V, X, synthetic
from src.engine.query import materialize_query, run_attack_query
from src.engine.semantics import AttackState, apply_transition
from src.engine.semantics.credentials import OWNERS
from src.engine.semantics.evaluator import PreparedSemanticGraph, evaluate
from src.engine.semantics.state import CredentialArtifact
from src.engine.semantics.transitions import Status


def test_positive_public_query_and_independent_six_state_chain():
    graph, q = synthetic()
    before = graph.to_canonical()
    result = run_attack_query(q, graph)
    assert result.final_goal_reached and result.checkpoint_reached and not result.truncated
    assert len(result.paths) == 1
    path = result.paths[0]
    assert [s.result.request.technique_id for s in path.transition_history] == PROGRAM
    assert [s.result.request.actor for s in path.transition_history] == [U, U, V, V, V]
    assert path.transition_edge_ids[:3] == (None, None, None)
    assert [s.derived_from_step for s in path.transition_history[:3]] == [None, 0, 1]
    state = path.transition_history[0].result.before
    states = [state]
    prepared = PreparedSemanticGraph(before, snapshot_facts=graph.snapshot_facts)
    for step in path.transition_history:
        replayed = evaluate(prepared, state, step.result.request, path.runtime_context)
        assert replayed == step.result
        state = apply_transition(state, replayed)
        states.append(state)
    assert len(states) == 6
    assert states[1].service_ticket_material and not states[1].recovered_secret
    assert states[1].usable_identity == {(U, X)}
    assert states[2].recovered_secret and states[2].usable_identity == {(U, X)}
    assert states[3].usable_identity == {(U, X), (V, X)} and not states[3].effective_member
    assert states[4].effective_member == {(V, G)} and not states[4].admin_control
    assert states[5].admin_control == {C}
    assert not state.reset_password_control and not state.authentication_control
    assert not state.credential_material and state.control == {X}
    assert graph.to_canonical() == before
    assert any("Properties.hasspn" in p for p in next(iter(state.recovered_secret)).provenance)
    assert all(s.result.is_assumption_backed for s in path.transition_history)


@pytest.mark.parametrize(
    "spn,values,gate,status",
    [
        (False, ("HTTP/x",), "has_spn", Status.BLOCKED),
        (None, ("HTTP/x",), "has_spn", Status.INDETERMINATE),
        (True, None, "service_principal_names", Status.INDETERMINATE),
        (True, (), "service_principal_names", Status.BLOCKED),
    ],
)
def test_fact_api_policy(spn, values, gate, status):
    graph, q = synthetic(spn=spn, values=values)
    result = run_attack_query(q, graph)
    assert not result.final_goal_reached and len(result.attempts) == 1
    attempt = result.attempts[0]
    assert attempt.status == status
    assert gate in attempt.failed + attempt.unknown
    assert attempt.additions == AttackState()
    assert attempt.snapshot_evidence


@pytest.mark.parametrize(
    "predicate,subject,target,prefix",
    [
        ("kerberos_authentication_usable", U, X, 0),
        ("network_kdc_reachable", U, V, 0),
        ("service_ticket_request_accepted", U, V, 0),
        ("recovery_success", U, V, 1),
        ("secret_valid", V, X, 2),
        ("authentication_accepted", V, X, 2),
        ("admin_execution_context", V, C, 4),
    ],
)
@pytest.mark.parametrize("value,status", [(False, Status.BLOCKED), (None, Status.INDETERMINATE)])
def test_runtime_cutoffs_keep_successful_prefix_only(
    predicate, subject, target, prefix, value, status
):
    graph, q = synthetic()
    q["assumptions"] = [
        f
        for f in q["assumptions"]
        if (f["predicate"], f["subject"], f["target"]) != (predicate, subject, target)
    ]
    # Explicit missing gate: remove entry entirely (unknown recovery scope also audited).
    if value is False:
        q["runtime_facts"] = [
            {
                "predicate": predicate,
                "subject": subject,
                "target": target,
                "value": False,
                "provenance_reference": "synthetic://denied",
            }
        ]
    result = run_attack_query(q, graph)
    assert not result.final_goal_reached
    applicable = [a for a in result.attempts if a.status == Status.APPLICABLE]
    assert [a.request.technique_id for a in applicable] == PROGRAM[:prefix]
    blocked = result.attempts[-1]
    assert blocked.status == status and blocked.additions == AttackState()
    if prefix < 2:
        assert not blocked.before.recovered_secret
    if prefix < 3:
        assert (V, X) not in blocked.before.usable_identity
    if prefix == 4:
        assert result.checkpoint_reached


@pytest.mark.parametrize(
    "mode,expected",
    [
        ("absent", Status.BLOCKED),
        ("wrong_context", Status.BLOCKED),
        ("unknown", Status.INDETERMINATE),
    ],
)
def test_auth_state_is_not_seeded_from_foothold(mode, expected):
    graph, q = synthetic()
    q["initial_state"]["usable_identity"] = [[U, C]] if mode == "wrong_context" else []
    if mode == "unknown":
        q["initial_state"]["authentication_unknown"] = [[U, X]]
        q["initial_state"]["control"].append(U)  # query declaration, never usable credential
    else:
        q["initial_state"]["control"].append(U)
    result = run_attack_query(q, graph)
    assert result.attempts[0].status == expected
    assert result.attempts[0].additions == AttackState()


def test_known_false_veto_optimistic_assumption_and_rejected_ledger():
    graph, q = synthetic()
    q["runtime_facts"] = [
        {
            "predicate": "network_kdc_reachable",
            "subject": U,
            "target": V,
            "value": False,
            "provenance_reference": "synthetic://kdc-deny",
        }
    ]
    result = run_attack_query(q, graph)
    assert result.attempts[0].status == Status.BLOCKED
    assert result.materialized_query.rejected_assumptions
    assert not result.attempts[0].additions.service_ticket_material


@pytest.mark.parametrize(
    "initial,expected",
    [("material", PROGRAM[1:]), ("secret", PROGRAM[2:]), ("identity", PROGRAM[3:])],
)
def test_reuse_scope_skips_acquisition_and_charging(initial, expected):
    graph, q = synthetic()
    if initial == "identity":
        q["initial_state"]["usable_identity"].append([V, X])
    else:
        field, form = (
            ("service_ticket_material", "kerberos_service_ticket")
            if initial == "material"
            else ("recovered_secret", "password")
        )
        q["initial_state"][field] = [
            asdict(CredentialArtifact(V, X, form, ("synthetic://initial",)))
        ]
    result = run_attack_query(q, graph)
    assert [
        [s.result.request.technique_id for s in p.transition_history] for p in result.paths
    ] == [expected]
    assert not any(a.request.technique_id == "kerberoast_request" for a in result.attempts)


def test_branch_isolation_owner_scope_determinism_and_caps():
    graph, q = synthetic()
    original = copy.deepcopy(q)
    first = run_attack_query(q, graph)
    second = run_attack_query(q, graph)
    assert first.search_result == second.search_result and q == original
    q["allowed_techniques"] = [t for t in q["allowed_techniques"] if t not in OWNERS]
    off = run_attack_query(q, graph)
    assert not off.final_goal_reached
    assert not any(a.request.technique_id in OWNERS for a in off.attempts)
    q = copy.deepcopy(original)
    q["budget"]["max_steps"] = 1
    capped = run_attack_query(q, graph)
    assert capped.truncated and not capped.final_goal_reached
    assert not capped.attempts[0].before.service_ticket_material
    assert capped.attempts[0].additions.service_ticket_material
    assert not materialize_query(original, graph).initial_attack_state.service_ticket_material


def test_wrong_scope_artifact_and_recovery_metadata_do_not_activate():
    graph, q = synthetic()
    q["initial_state"]["recovered_secret"] = [
        asdict(CredentialArtifact(V, C, "password", ("synthetic://other",)))
    ]
    q["allowed_techniques"] = [
        "activate_recovered_identity",
        "propagate_group_entitlement",
        "scenario_winrm_admin",
    ]
    assert not run_attack_query(q, graph).paths
    graph, q = synthetic()
    for f in q["assumptions"]:
        if f["predicate"] == "recovery_success":
            f["assumption_metadata"].pop("horizon")
    result = run_attack_query(q, graph)
    assert "recovery_scope" in result.attempts[-1].unknown
    assert not result.attempts[-1].additions.recovered_secret


def test_disabled_owner_veto_and_no_reset_shortcut():
    graph, q = synthetic()
    positive = run_attack_query(q, graph)
    secret_state = positive.paths[0].transition_history[2].result.before
    request = positive.paths[0].transition_history[2].result.request
    canonical = graph.to_canonical()
    next(n for n in canonical["nodes"] if n["id"] == V)["enabled"] = False
    prepared = PreparedSemanticGraph(canonical)
    context = positive.materialized_query.runtime_context
    result = evaluate(prepared, secret_state, request, context)
    assert result.status == Status.BLOCKED and "actor_enabled" in result.failed
    assert not result.additions.usable_identity
    state = replace(
        secret_state,
        recovered_secret=frozenset(),
        credential_material={V},
        authentication_control={V},
    )
    assert evaluate(prepared, state, request, context).status == Status.BLOCKED


def test_reset_overlap_has_no_new_asset_coverage_claim():
    graph, q = synthetic(overlap=True)
    baseline = copy.deepcopy(q)
    baseline["allowed_techniques"] = [t for t in q["allowed_techniques"] if t not in OWNERS]
    b = run_attack_query(baseline, graph)
    e = run_attack_query(q, graph)
    assert b.final_goal_reached and e.final_goal_reached
    assert any(
        [s.result.request.technique_id for s in p.transition_history]
        == [
            "propagate_group_entitlement",
            "scenario_reset_password",
            "acquire_reset_identity",
            "propagate_group_entitlement",
            "scenario_winrm_admin",
        ]
        for p in b.paths
    )
    assert any(p.final_state.recovered_secret for p in e.paths)


def test_knowledge_is_explicit_and_catalog_off_blocks_all_producers():
    graph, q = synthetic()
    q["initial_state"]["known_identity"] = []
    result = run_attack_query(q, graph)
    assert not result.paths and not any(
        a.request.technique_id == "kerberoast_request" for a in result.attempts
    )
    q["allowed_techniques"] = []
    assert not run_attack_query(q, graph).attempts


@pytest.mark.parametrize(
    "reuse,work_count", [("none", 4), ("material", 3), ("secret", 2), ("identity", 1)]
)
def test_canonical_ranking_replay_lineage_unrated_and_reused_work(reuse, work_count):
    from scripts.research.kerberoasting_probe import rank_synthetic

    graph, q = synthetic()
    if reuse == "identity":
        q["initial_state"]["usable_identity"].append([V, X])
    elif reuse in {"material", "secret"}:
        field, form = (
            ("service_ticket_material", "kerberos_service_ticket")
            if reuse == "material"
            else ("recovered_secret", "password")
        )
        q["initial_state"][field] = [
            asdict(CredentialArtifact(V, X, form, ("synthetic://initial",)))
        ]
    ranked = rank_synthetic(graph, q)["result_payload"]
    assert ranked["search_audit"]["candidates_adapted"] == 1
    record = ranked["diagnostics"]["generated_0001"]
    assessment = record["assessment"]
    assert assessment["effort_status"] == "unrated" and assessment["effort"] is None
    assert assessment["likelihood_interval"] is None and assessment["impact"] is None
    assert len(assessment["program"]) == work_count
    assert (
        not ranked["eligible_candidates"]
        and ranked["min_effort_to_da_baseline"]["minimum_effort_value"] is None
    )
    if reuse == "identity":
        assert q["initial_actor"] == U
        assert ranked["query_id"] == "query-216"
        lineage = record["search_trace"]["transition_lineage"]
        assert lineage[0]["actor"] == V
        actor_binding = record["search_trace"]["initial_actor_binding"]
        assert actor_binding["foothold_node_id"] == U
        assert actor_binding["first_actor"] == V
        assert actor_binding["authentication_context"] == X
        assert actor_binding["declared_initial_actors"] == sorted([U, V])
        assert [step["technique_id"] for step in lineage] == PROGRAM[3:]
    if reuse == "none":
        lineage = record["search_trace"]["transition_lineage"]
        assert lineage[0]["origin"] == "snapshot_fact" and lineage[0]["snapshot_evidence"]
        assert lineage[1]["derived_from_step"] == 0 and lineage[2]["derived_from_step"] == 1
        assert all(lineage[i]["capability_provenance"] for i in range(3))


def test_replay_rejects_lost_sidecar_and_false_recovery_cannot_advance():
    from scripts.research.kerberoasting_probe import ranking_inputs
    from src.engine.ranking.adapter_145 import adapt_search_candidate
    from src.engine.ranking.orchestration import evaluate_search_candidates
    from src.engine.ranking.replay import replay_candidate_sequence
    from src.engine.ranking.validation import decode_ranking_query
    from src.engine.ranking.verification import verify_search_envelope

    graph, q = synthetic()
    path = run_attack_query(q, graph).paths[0]
    payload, bindings = ranking_inputs(graph, q)
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
    inputs = [
        {
            "candidate_id": "generated_0001",
            "target_asset_id": C,
            "path_result": path,
            "action_mapping": actions,
        }
    ]
    lost = evaluate_search_candidates(payload, inputs, canonical_graph=graph.to_canonical())
    assert lost["result_payload"]["search_audit"]["candidates_adapted"] == 0
    missing_graph = evaluate_search_candidates(payload, inputs, snapshot_facts=graph.snapshot_facts)
    assert missing_graph["result_payload"]["search_audit"]["candidates_adapted"] == 0
    envelope = adapt_search_candidate(
        path_result=path,
        candidate_id="generated_0001",
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
    for value, expected in [(False, "blocked"), (None, "unknown")]:
        modified = copy.deepcopy(payload)
        modified["facts_ledger"]["assumed_facts"] = [
            f for f in modified["facts_ledger"]["assumed_facts"] if f["predicate"] != "recovery_ok"
        ]
        if value is False:
            modified["facts_ledger"]["false_facts"].append(
                {
                    "predicate": "recovery_ok",
                    "layer": 3,
                    "truth_value": False,
                    "provenance_reference": "synthetic://recovery-deny",
                }
            )
        replayed = replay_candidate_sequence(
            decode_ranking_query(modified), envelope, semantic_binding=binding
        )
        assert replayed["gate_status"] == expected
        assert replayed["gates_evaluation"]["admin"] != "True"


def test_recovery_form_and_custom_recipe_are_fail_closed():
    from src.engine.semantics import load_catalog

    with pytest.raises(ValueError, match="typed artifacts"):
        AttackState(
            recovered_secret={
                CredentialArtifact(V, X, "kerberos_service_ticket", ("synthetic://x",))
            }
        )
    graph, q = synthetic()
    materialized = materialize_query(q, graph)
    owner = next(t for t in load_catalog() if t.id == "kerberoast_request")
    from src.engine.semantics.transitions import TransitionRequest

    request = TransitionRequest(owner.id, U, U, V)
    changed = replace(owner, prerequisites=owner.prerequisites + ("secret_valid",))
    with pytest.raises(ValueError, match="unsupported artifact recipe"):
        evaluate(
            PreparedSemanticGraph(graph.to_canonical(), snapshot_facts=graph.snapshot_facts),
            materialized.initial_attack_state,
            request,
            materialized.runtime_context,
            (changed,),
        )


def test_sanitized_executable_query_transport_matches_oracle():
    import json
    from pathlib import Path

    from src.engine.graph import EngineGraph

    folder = Path(__file__).parent / "fixtures" / "kerberoasting"
    graph = EngineGraph.from_snapshot((folder / "snapshot.json").read_text(encoding="utf-8"))
    query = json.loads((folder / "query.json").read_text(encoding="utf-8"))
    result = run_attack_query(query, graph)
    assert [
        [s.result.request.technique_id for s in p.transition_history] for p in result.paths
    ] == [PROGRAM]


@pytest.mark.parametrize("snapshot_support", ["missing", "false", "unknown"])
def test_generic_ranking_rejects_caller_asserted_spn_lineage(snapshot_support):
    from scripts.research.kerberoasting_probe import ranking_inputs
    from src.engine.ranking import PathRankingEngine, RankingValidationError
    from src.engine.ranking.adapter_145 import adapt_search_candidate
    from src.engine.ranking.orchestration import evaluate_search_candidates

    graph, q = synthetic()
    path = run_attack_query(q, graph).paths[0]
    payload, bindings = ranking_inputs(graph, q)
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
        candidate_id="forged",
        target_asset_id=C,
        query_metadata={
            **payload["query_metadata"],
            "target_impact_assessments": payload["target_impact_assessments"],
        },
        action_mapping=actions,
        route_id="route",
        bound_actions_catalog=payload["bound_actions"],
    )
    # Even complete inline SPN/evidence records cannot grant source verification.
    assert envelope["transition_lineage"][0]["snapshot_evidence"]
    with pytest.raises(RankingValidationError, match="verified semantic replay"):
        PathRankingEngine().evaluate(payload, [envelope])
    unsupported, _ = (
        synthetic(spn=False) if snapshot_support == "false" else synthetic(spn=None, values=None)
    )
    result = evaluate_search_candidates(
        payload,
        [
            {
                "candidate_id": "forged",
                "target_asset_id": C,
                "path_result": path,
                "action_mapping": actions,
            }
        ],
        canonical_graph=unsupported.to_canonical(),
        snapshot_facts=None if snapshot_support == "missing" else unsupported.snapshot_facts,
    )["result_payload"]
    assert result["search_audit"]["candidates_adapted"] == 0
    assert not result["eligible_candidates"]


def test_replay_binding_cannot_be_reused_after_lineage_or_scope_mutation():
    from scripts.research.kerberoasting_probe import ranking_inputs
    from src.engine.ranking import PathRankingEngine, RankingValidationError
    from src.engine.ranking.adapter_145 import adapt_search_candidate
    from src.engine.ranking.verification import verify_search_envelope

    graph, q = synthetic()
    path = run_attack_query(q, graph).paths[0]
    payload, bindings = ranking_inputs(graph, q)
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
    for mutation in ("lineage", "scope", "wire"):
        changed = copy.deepcopy(envelope)
        query = copy.deepcopy(payload)
        if mutation == "lineage":
            changed["transition_lineage"][0]["snapshot_evidence"][0] = "{}"
        elif mutation == "scope":
            query["query_metadata"]["query_id"] = "different-query"
            changed["scope_binding"]["query_id"] = "different-query"
        with pytest.raises(RankingValidationError):
            PathRankingEngine().evaluate(
                query,
                [changed],
                semantic_bindings={"verified": {} if mutation == "wire" else binding},
            )


def test_missing_enabled_is_unknown_audit_origin():
    from src.engine.semantics.models import FactOrigin

    graph, q = synthetic()
    path = run_attack_query(q, graph).paths[0]
    activation = path.transition_history[2].result
    canonical = graph.to_canonical()
    next(node for node in canonical["nodes"] if node["id"] == V).pop("enabled")
    result = evaluate(
        PreparedSemanticGraph(canonical),
        activation.before,
        activation.request,
        path.runtime_context,
    )
    assert result.status == Status.INDETERMINATE
    decision = next(d for d in result.decisions if d.predicate == "actor_enabled")
    assert decision.origin == FactOrigin.UNKNOWN
    assert not result.additions.usable_identity
