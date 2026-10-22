"""Independent finite oracles for host compromise -> session identity -> AD rights."""

from dataclasses import replace

import pytest
from test_engine import ACTOR, GROUP, HOST, _edge
from test_exposure import BOB, DC
from test_exposure import graph as exposure_graph

from scripts.neo_domain import build_survey, scenario_profile, techniques_for
from src.engine.batch import _query_for_cell
from src.engine.graph import EngineGraph
from src.engine.query import run_attack_query
from src.engine.query_cli import wire
from src.engine.ranking.effort_profiles import load_effort_profile
from src.engine.semantics import AttackState, FactOrigin, RuntimeContext, RuntimeFact, Status
from src.engine.semantics.credentials import replay_path
from src.engine.semantics.evaluator import evaluate
from src.engine.semantics.transitions import TransitionRequest


def scenario(*, host_admin=True, lateral=False, mutate=False):
    raw = exposure_graph.__wrapped__().to_canonical()
    raw["edges"] = [e for e in raw["edges"] if e["source"] == DC] + [
        _edge(HOST, BOB, "HasSession"),
        _edge(BOB, GROUP, "GenericAll" if mutate else "MemberOf"),
    ]
    if lateral:
        raw["edges"].append(_edge(ACTOR, HOST, "AdminTo"))
    graph = EngineGraph.from_canonical(raw)
    _, request = build_survey(
        graph, scenario="host-compromise", source_ids=[ACTOR if lateral else HOST]
    )
    source = request.sources[0]
    if not host_admin and not lateral:
        source = replace(
            source,
            profile_kind="computer_usable_identity",
            authentication_context=DC,
            identity_provenance_reference="synthetic://machine-account-only",
        )
    query, error = _query_for_cell(
        request,
        source,
        request.resolve_target_goals()[0],
        graph,
        techniques_for("host-compromise"),
        request.common_budget,
        scenario_policy=scenario_profile(graph, "host-compromise"),
        effort_profile=load_effort_profile("neo-c-v1"),
        search_order="neo_guided",
    )
    assert error is None
    return graph, query


@pytest.mark.parametrize(
    "lateral,mutate,expected", [(False, False, 2), (True, False, 3), (False, True, 3)]
)
def test_automatic_host_session_chain_is_replayed_and_C_rated(lateral, mutate, expected):
    graph, query = scenario(lateral=lateral, mutate=mutate)
    result = run_attack_query(query, graph)
    assert result.final_goal_reached
    path = result.best_path
    assert path is not None
    assert replay_path(path, graph) == path.final_state
    assert result.min_effort["minimum_effort_value"] == expected
    assert any(
        s.result.request.technique_id == "use_session_identity" for s in path.transition_history
    )
    initial = path.transition_history[0].result.before
    assert BOB not in initial.control and all(u != BOB for u, _ in initial.usable_identity)
    assert all(u != ACTOR for u, _ in path.final_state.effective_member) if not lateral else True
    assert (BOB, GROUP) in path.final_state.effective_member
    if not lateral:
        assert initial.admin_control == {HOST} and not initial.usable_identity
    # Exhaustive small fixture: guidance changes neither supported programs nor costs.
    fifo = run_attack_query({**query, "search_order": "fifo"}, graph)
    assert fifo.final_goal_reached and fifo.min_effort["minimum_effort_value"] == expected


def test_machine_account_alone_cannot_use_host_session():
    graph, query = scenario(host_admin=False)
    result = run_attack_query(query, graph)
    assert not result.final_goal_reached
    assert not any(a.additions.usable_identity for a in result.attempts)


@pytest.mark.parametrize(
    "predicate",
    ["session_fresh", "session_present", "credential_accessible", "session_identity_usable"],
)
@pytest.mark.parametrize("value", [False, None])
def test_session_missing_or_negative_gate_never_becomes_identity(predicate, value):
    graph, query = scenario()
    result = run_attack_query(query, graph)
    path = result.best_path
    step = next(
        s
        for s in path.transition_history
        if s.result.request.technique_id == "use_session_identity"
    )
    facts = dict(path.runtime_context.facts)
    key = predicate, HOST, BOB
    facts.pop(key)
    if value is False:
        facts[key] = RuntimeFact(predicate, HOST, BOB, False, FactOrigin.OBSERVED_EVIDENCE)
    checked = evaluate(
        graph.to_prepared(),
        step.result.before,
        step.result.request,
        RuntimeContext(facts, authentication_context=HOST),
    )
    assert checked.status == (Status.BLOCKED if value is False else Status.INDETERMINATE)
    assert not checked.additions.usable_identity
    # Negative runtime evidence also vetoes the optimistic profile end to end.
    if value is False:
        query["runtime_facts"] = [wire(facts[key])]
        assert not run_attack_query(query, graph).final_goal_reached


def test_session_cannot_be_fabricated_or_used_from_another_host():
    graph, query = scenario()
    result = run_attack_query(query, graph)
    step = result.best_path.transition_history[0]
    assert step.result.request.technique_id == "use_session_identity"
    wrong_host = evaluate(
        graph.to_prepared(),
        AttackState(admin_control={DC}),
        step.result.request,
        result.best_path.runtime_context,
    )
    assert wrong_host.status == Status.BLOCKED
    raw = graph.to_canonical()
    raw["edges"] = [e for e in raw["edges"] if e["kind"] != "HasSession"]
    assert not run_attack_query(query, EngineGraph.from_canonical(raw)).final_goal_reached


@pytest.mark.parametrize("disabled,wrong_context", [(True, False), (False, True)])
def test_session_identity_respects_account_and_authentication_scope(disabled, wrong_context):
    graph, query = scenario()
    result = run_attack_query(query, graph)
    path = result.best_path
    step = path.transition_history[0]
    raw = graph.to_canonical()
    if disabled:
        next(n for n in raw["nodes"] if n["id"] == BOB)["enabled"] = False
    facts = dict(path.runtime_context.facts)
    if wrong_context:
        key = "session_identity_usable", HOST, BOB
        facts[key] = replace(facts[key], assumption_metadata={"authentication_context": DC})
    checked = evaluate(
        EngineGraph.from_canonical(raw).to_prepared(),
        step.result.before,
        step.result.request,
        RuntimeContext(facts, authentication_context=HOST),
    )
    assert checked.status != Status.APPLICABLE and not checked.additions.usable_identity


def test_host_scenario_is_explicit_and_single_source_selection_does_not_pool_capabilities():
    graph = exposure_graph.__wrapped__()
    _, old = build_survey(graph)
    _, host = build_survey(graph, scenario="host-compromise", source_ids=[HOST])
    assert len(host.sources) == 1 and host.sources[0].profile_kind == "computer_control_admin"
    assert host.sources[0].authentication_context == HOST
    assert all(s.profile_kind != "computer_control_admin" for s in old.sources)
    assert "use_session_identity" not in techniques_for("identity")
    with pytest.raises(ValueError, match="eligible"):
        build_survey(graph, source_ids=["unknown"])


def test_opaque_legacy_material_is_not_silently_promoted():
    graph, _ = scenario()
    result = evaluate(
        graph.to_prepared(),
        AttackState(credential_material={BOB}),
        TransitionRequest("use_session_identity", HOST, HOST, BOB),
        RuntimeContext(),
    )
    assert result.status != Status.APPLICABLE and not result.additions.usable_identity
