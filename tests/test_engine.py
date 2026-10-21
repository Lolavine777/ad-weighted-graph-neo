"""Canonical graph, stateful semantic expansion, and reference search coverage."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from test_graph_lineage import _build, _records

from scripts.check_contract import canonical_edge_id
from src.engine import (
    EngineGraph,
    SearchBudget,
    StructuralSearchResult,
    evaluate_path,
    generate_attack_paths,
    generate_structural_paths,
    shortest_path,
    unit_cost,
)
from src.engine.semantics import (
    AttackState,
    FactOrigin,
    PrerequisiteDecision,
    RuntimeContext,
    RuntimeFact,
    Status,
    TransitionResult,
    apply_transition,
    load_catalog,
)
from src.engine.semantics import (
    evaluate as evaluate_transition,
)
from src.engine.semantics.models import StructuralRelationship
from src.engine.semantics.transitions import TransitionRequest

ROOT = Path(__file__).resolve().parents[1]
TOY = json.loads((ROOT / "data/samples/toy-graph.json").read_text(encoding="utf-8"))
ACTOR = "S-1-5-21-1000-2000-3000-1101"
GROUP = "S-1-5-21-1000-2000-3000-512"
HOST = "10000000-0000-4000-8000-000000000002"


def _edge(source: str, target: str, kind: str, *, weight: float = 1.0) -> dict:
    return {
        "id": canonical_edge_id(source, target, kind),
        "source": source,
        "target": target,
        "kind": kind,
        "weight": weight,
        "provenance": [
            {
                "raw_file": "synthetic://engine-test",
                "collector": "engine-test",
                "timestamp": "2026-09-29T00:00:00Z",
                "evidence_type": "positive",
            }
        ],
    }


def _graph(edges: list[dict], *, extra_nodes: list[dict] | None = None) -> EngineGraph:
    data = copy.deepcopy(TOY)
    if extra_nodes:
        data["nodes"].extend(copy.deepcopy(extra_nodes))
    data["edges"] = copy.deepcopy(edges)
    ids = {node["id"] for node in data["nodes"]}
    assert all(edge["source"] in ids and edge["target"] in ids for edge in edges)
    for node in data["nodes"]:
        if node["id"] == HOST:
            node["enabled"] = True
    return EngineGraph.from_canonical(data)


def _budget(*, paths=20, steps=6, expansions=2000):
    return SearchBudget(max_paths=paths, max_steps=steps, max_expansions=expansions)


def _membership_admin_graph():
    return _graph([_edge(ACTOR, GROUP, "GenericAll"), _edge(GROUP, HOST, "AdminTo")])


def _auditable_context(facts):
    return RuntimeContext(
        [
            RuntimeFact(
                predicate,
                subject,
                target,
                value,
                FactOrigin.DECLARED_ASSUMPTION,
                scope="engine-test",
                rationale="synthetic engine scenario fixture",
            )
            for (predicate, subject, target), value in facts.items()
        ]
    )


def _membership_admin_context(*, group_membership=True):
    facts = {
        ("security_group", ACTOR, GROUP): True,
        ("membership_change_allowed", ACTOR, GROUP): True,
        ("directory_write_allowed", ACTOR, GROUP): True,
        ("membership_usable", ACTOR, GROUP): group_membership,
        ("admin_channel", ACTOR, HOST): True,
        ("authentication_accepted", ACTOR, HOST): True,
    }
    return _auditable_context(facts)


def test_canonical_fixture_loads_and_preserves_direction_parallel_edges_and_provenance():
    engine = EngineGraph.from_canonical(TOY)
    user, group = TOY["edges"][1]["source"], TOY["edges"][1]["target"]
    assert engine.edges_between(user, group)[0]["id"] == TOY["edges"][1]["id"]
    assert engine.edges_between(group, user) == ()
    assert engine.edge(TOY["edges"][1]["id"])["provenance"] == TOY["edges"][1]["provenance"]
    assert engine.node(user)["id"] == user
    copied = engine.to_canonical()
    copied["edges"].clear()
    assert engine.edges()


def test_assessments_stay_separate_and_derivation_survives():
    graph = _build(_records(groups=("S-1-5-21-1000-2000-3000-2101",)))
    assert any("derivation" in edge for edge in graph["edges"])
    graph["assessments"] = [
        {
            "id": "unknown-check",
            "status": "unknown",
            "reason": "Not enough evidence",
            "provenance": [
                {
                    "raw_file": "synthetic://assessment",
                    "collector": "engine-test",
                    "timestamp": "2026-09-29T00:00:00Z",
                    "evidence_type": "unknown",
                    "timestamp_status": "observed",
                }
            ],
        }
    ]
    engine = EngineGraph.from_canonical(graph)
    assert engine.assessments[0]["status"] == "unknown"
    assert len(engine.edges()) == len(graph["edges"])
    derived = next(edge for edge in graph["edges"] if "derivation" in edge)
    assert engine.edge(derived["id"])["derivation"] == derived["derivation"]


def test_invalid_json_contract_graph_and_dangling_endpoint_fail_closed():
    with pytest.raises(ValueError, match="JSON is invalid"):
        EngineGraph.from_canonical("{")
    malformed = copy.deepcopy(TOY)
    malformed["metadata"]["contract_version"] = "99"
    with pytest.raises(ValueError, match="validation failed"):
        EngineGraph.from_canonical(malformed)
    malformed = copy.deepcopy(TOY)
    malformed["edges"][0]["source"] = "missing-node"
    malformed["edges"][0]["id"] = canonical_edge_id(
        malformed["edges"][0]["source"],
        malformed["edges"][0]["target"],
        malformed["edges"][0]["kind"],
    )
    with pytest.raises(ValueError, match="dangling endpoint"):
        EngineGraph.from_canonical(malformed)


def test_structural_queries_are_directed_deterministic_and_cycle_safe():
    a, b, c = (TOY["nodes"][i]["id"] for i in range(3))
    edges = [_edge(a, b, "MemberOf"), _edge(b, c, "GenericAll"), _edge(c, a, "WriteDacl")]
    engine = _graph(edges)
    assert engine.successors(a) == (b,)
    assert engine.predecessors(a) == (c,)
    assert engine.reachable(a, c) and engine.reachable(c, b)

    def target(node):
        return node["label"].endswith("TARGET")

    assert [node["id"] for node in engine.select_targets(target)] == [c]
    assert engine.edges(kind="GenericAll")[0]["target"] == c
    reversed_engine = _graph(list(reversed(edges)))
    assert engine.successors(a) == reversed_engine.successors(a)


def test_structural_paths_are_separate_from_semantics_and_bounded():
    a, b, c, d = (node["id"] for node in TOY["nodes"][:4])
    engine = _graph(
        [
            _edge(a, b, "MemberOf"),
            _edge(b, d, "GenericAll"),
            _edge(a, c, "WriteDacl"),
            _edge(c, d, "GenericAll"),
            _edge(b, a, "ForceChangePassword"),
        ]
    )
    paths = generate_structural_paths(engine, a, d, budget=_budget(paths=1))
    assert len(paths) == 1
    assert paths[0].nodes[0] == a and paths[0].nodes[-1] == d
    assert paths[0].final_state is None and not paths[0].transition_history
    assert paths.truncated is True
    assert paths.truncation_reason == "path_limit_reached"
    unreachable = generate_structural_paths(engine, c, b, budget=_budget())
    assert unreachable.paths == ()
    assert not unreachable
    assert len(unreachable) == 0
    assert unreachable.complete is True
    assert unreachable.truncated is False
    assert unreachable.truncation_reason is None
    with pytest.raises(ValueError, match="positive integers"):
        SearchBudget(max_paths=0, max_steps=1, max_expansions=1)


def test_shortest_path_uses_edge_local_additive_costs_and_exact_parallel_edge():
    a, b, c, d = (node["id"] for node in TOY["nodes"][:4])
    engine = _graph(
        [
            _edge(a, b, "MemberOf"),
            _edge(b, d, "GenericAll"),
            _edge(a, c, "GenericAll"),
            _edge(a, b, "WriteDacl"),
        ]
    )
    result = shortest_path(
        engine,
        a,
        d,
        cost_fn=lambda edge, _context: 5.0 if edge["kind"] == "WriteDacl" else 1.0,
    )
    assert result and result.nodes == (a, b, d) and result.cost == 2
    assert result.edges[0]["id"] == canonical_edge_id(a, b, "MemberOf")
    assert len(engine.edges_between(a, b)) == 2
    unit_result = shortest_path(engine, a, d, cost_fn=unit_cost)
    assert unit_result and unit_result.nodes == (a, b, d) and unit_result.cost == 2
    assert shortest_path(engine, c, d, cost_fn=unit_cost) is None


@pytest.mark.parametrize("bad", [-1, float("inf"), float("nan"), True])
def test_dijkstra_rejects_invalid_costs(bad):
    a, b = (node["id"] for node in TOY["nodes"][:2])
    engine = _graph([_edge(a, b, "MemberOf")])
    with pytest.raises(ValueError, match="finite non-negative"):
        shortest_path(engine, a, b, cost_fn=lambda _edge, _context: bad)


def test_existing_semantics_statuses_drive_candidate_expansion_without_adapter_drift():
    engine = _graph([_edge(ACTOR, HOST, "CanRDP")])
    initial = AttackState(control={ACTOR})

    def target(node):
        return node["id"] == HOST

    blocked_context = _auditable_context(
        {
            ("rdp_available", ACTOR, HOST): False,
            ("authentication_accepted", ACTOR, HOST): True,
        }
    )
    blocked = generate_attack_paths(
        engine,
        ACTOR,
        initial_state=initial,
        runtime_context=blocked_context,
        target_predicate=target,
        budget=_budget(),
    )
    assert not blocked.paths
    blocked_result = next(r for r in blocked.attempts if r.status is Status.BLOCKED)
    assert apply_transition(initial, blocked_result) == initial

    unknown = generate_attack_paths(
        engine,
        ACTOR,
        initial_state=initial,
        runtime_context=_auditable_context({("authentication_accepted", ACTOR, HOST): True}),
        target_predicate=target,
        budget=_budget(),
    )
    unknown_result = next(r for r in unknown.attempts if r.status is Status.INDETERMINATE)
    assert not unknown.paths and apply_transition(initial, unknown_result) == initial
    assert unknown_result.before == initial


def test_state_advances_by_apply_transition_and_derived_membership_unlocks_later_step():
    engine = _membership_admin_graph()
    canonical_before = engine.to_canonical()
    initial = AttackState(control={ACTOR})
    result = generate_attack_paths(
        engine,
        ACTOR,
        initial_state=initial,
        runtime_context=_membership_admin_context(),
        target_predicate=lambda node: node["id"] == HOST,
        budget=_budget(paths=5, steps=5),
        scenario_reference="scenario:synthetic",
    )
    path = next(
        candidate
        for candidate in result.paths
        if tuple(step.result.technique.id for step in candidate.transition_history[:3])
        == (
            "genericall_add_member",
            "propagate_group_entitlement",
            "obtain_admin_execution_on_host",
        )
    )
    assert path.nodes == (ACTOR, GROUP, GROUP, HOST)
    assert path.transition_history[-1].result.status is Status.APPLICABLE
    assert path.transition_history[1].result.before.effective_member == frozenset()
    assert path.transition_history[2].result.before.effective_member == {(ACTOR, GROUP)}
    assert path.final_state is not None and path.final_state.admin_control == {HOST}
    assert path.scenario_reference == "scenario:synthetic"
    assert path.transition_edge_ids == (
        canonical_edge_id(ACTOR, GROUP, "GenericAll"),
        None,
        canonical_edge_id(GROUP, HOST, "AdminTo"),
    )
    assert path.edges[0]["id"] == canonical_edge_id(ACTOR, GROUP, "GenericAll")
    assert path.edges[1]["id"] == canonical_edge_id(GROUP, HOST, "AdminTo")
    assert path.transition_history[1].derived_from_step == 0
    assert engine.to_canonical() == canonical_before
    assert initial.effective_member == frozenset()
    assert initial.admin_control == frozenset()


def test_known_false_snapshot_evidence_blocks_despite_optimistic_runtime_fact():
    edge = _edge(ACTOR, "S-1-5-21-1000-2000-3000-1102", "ForceChangePassword")
    disabled_user = copy.deepcopy(TOY["nodes"][1])
    disabled_user.update(
        id="S-1-5-21-1000-2000-3000-1102", label="SYNTHETIC-DISABLED", enabled=False
    )
    engine = _graph([edge], extra_nodes=[disabled_user])
    facts = {
        (name, ACTOR, disabled_user["id"]): True
        for name in ("target_enabled", "password_policy_accepts", "directory_write_allowed")
    }
    result = generate_attack_paths(
        engine,
        ACTOR,
        initial_state=AttackState(control={ACTOR}),
        runtime_context=_auditable_context(facts),
        target_predicate=lambda node: node["id"] == disabled_user["id"],
        budget=_budget(),
    )
    assert not result.paths
    assert any(
        transition.status is Status.BLOCKED and "target_enabled" in transition.failed
        for transition in result.attempts
    )


def test_semantic_branches_have_independent_immutable_states():
    second_group = "S-1-5-21-1000-2000-3000-2101"
    second_node = copy.deepcopy(next(node for node in TOY["nodes"] if node["kind"] == "Group"))
    second_node.update(id=second_group, label="SYNTHETIC-GROUP-B")
    engine = _graph(
        [_edge(ACTOR, GROUP, "GenericAll"), _edge(ACTOR, second_group, "GenericAll")],
        extra_nodes=[second_node],
    )
    facts = {
        (predicate, ACTOR, group): True
        for group in (GROUP, second_group)
        for predicate in ("security_group", "membership_change_allowed", "directory_write_allowed")
    }
    result = generate_attack_paths(
        engine,
        ACTOR,
        initial_state=AttackState(control={ACTOR}),
        runtime_context=_auditable_context(facts),
        target_predicate=lambda node: node["id"] in {GROUP, second_group},
        budget=_budget(paths=20),
    )
    add_member_paths = [
        path
        for path in result.paths
        if path.transition_history[0].result.technique.id == "genericall_add_member"
    ]
    assert {path.target for path in add_member_paths} == {GROUP, second_group}
    for path in add_member_paths:
        assert path.final_state is not None
        assert path.final_state.relationship_added == {
            StructuralRelationship(ACTOR, "MemberOf", path.target)
        }
    assert {edge["id"] for edge in engine.to_canonical()["edges"]} == {
        canonical_edge_id(ACTOR, GROUP, "GenericAll"),
        canonical_edge_id(ACTOR, second_group, "GenericAll"),
    }


def test_bounded_attack_generation_reports_truncation_and_no_applicable_path():
    engine = _membership_admin_graph()
    result = generate_attack_paths(
        engine,
        ACTOR,
        initial_state=AttackState(control={ACTOR}),
        runtime_context=_membership_admin_context(group_membership=False),
        target_predicate=lambda node: node["id"] == HOST,
        budget=_budget(paths=2, steps=1, expansions=2),
    )
    assert result.expansions <= 2
    assert not result.paths
    assert result.truncated


def test_semantic_cycle_is_finite_and_obeys_required_expansion_budget():
    engine = _graph(
        [
            _edge(ACTOR, GROUP, "MemberOf"),
            _edge(GROUP, GROUP, "MemberOf"),
            _edge(GROUP, HOST, "AdminTo"),
        ]
    )
    facts = {
        ("security_group", ACTOR, GROUP): True,
        ("membership_usable", ACTOR, GROUP): True,
        ("admin_channel", ACTOR, HOST): True,
        ("authentication_accepted", ACTOR, HOST): True,
    }
    budget = _budget(paths=10, steps=5, expansions=20)
    result = generate_attack_paths(
        engine,
        ACTOR,
        initial_state=AttackState(control={ACTOR}),
        runtime_context=_auditable_context(facts),
        target_predicate=lambda _node: False,
        budget=budget,
    )
    assert not result.paths
    assert result.expansions <= budget.max_expansions
    assert len(result.attempts) == result.expansions


def test_whole_path_evaluator_receives_stateful_path_and_returns_model_value_unchanged():
    engine = _membership_admin_graph()
    generated = generate_attack_paths(
        engine,
        ACTOR,
        initial_state=AttackState(control={ACTOR}),
        runtime_context=_membership_admin_context(),
        target_predicate=lambda node: node["id"] == HOST,
        budget=_budget(paths=5, steps=5),
    )
    path = next(path for path in generated.paths if len(path.transition_history) == 3)
    sentinel = object()
    seen = {}

    def evaluator(candidate, scenario, target):
        seen.update(path=candidate, scenario=scenario, target=target)
        candidate.edges[0]["kind"] = "mutated-copy"
        return sentinel

    assessment = evaluate_path(
        path,
        evaluator=evaluator,
        scenario_context={"window": "synthetic"},
        target_context={"target": HOST},
    )
    assert assessment is sentinel
    assert seen["scenario"] == {"window": "synthetic"}
    assert seen["target"] == {"target": HOST}
    assert seen["path"].final_state == path.final_state
    assert path.edges and path.edges[0]["kind"] == "GenericAll"


def test_existing_lineage_fixture_still_loads_without_engine_model_duplication():
    canonical = _build(_records(groups=("S-1-5-21-1000-2000-3000-2101",)))
    engine = EngineGraph.from_canonical(canonical)
    assert any(edge.get("derivation") for edge in engine.edges())


def test_structural_search_completeness_and_budget_truncation_reasons():
    """Verify StructuralSearchResult distinguishes unreachability from budget truncation."""
    a, b, c, d = (node["id"] for node in TOY["nodes"][:4])
    # a -> b -> d (2 steps) and a -> c -> d (2 steps)
    engine = _graph(
        [
            _edge(a, b, "MemberOf"),
            _edge(b, d, "GenericAll"),
            _edge(a, c, "WriteDacl"),
            _edge(c, d, "GenericAll"),
        ]
    )

    # 1. Unreachable target on complete search: c -> b has no path
    res_unreachable = generate_structural_paths(engine, c, b, budget=_budget())
    assert isinstance(res_unreachable, StructuralSearchResult)
    assert res_unreachable.paths == ()
    assert not res_unreachable
    assert len(res_unreachable) == 0
    assert res_unreachable.complete is True
    assert res_unreachable.truncated is False
    assert res_unreachable.truncation_reason is None

    # 2. Reachable target truncated by max_steps: needs 2 steps, but max_steps=1
    res_step_limit = generate_structural_paths(
        engine, a, d, budget=_budget(paths=5, steps=1, expansions=100)
    )
    assert res_step_limit.paths == ()
    assert not res_step_limit
    assert res_step_limit.complete is False
    assert res_step_limit.truncated is True
    assert res_step_limit.truncation_reason == "step_limit_reached"

    # 3. Reachable target truncated by max_expansions: max_expansions=1
    res_exp_limit = generate_structural_paths(
        engine, a, d, budget=_budget(paths=5, steps=5, expansions=1)
    )
    assert res_exp_limit.paths == ()
    assert res_exp_limit.complete is False
    assert res_exp_limit.truncated is True
    assert res_exp_limit.truncation_reason == "expansion_limit_reached"

    # 4. Target reachable with multiple paths, truncated by max_paths:
    res_path_limit = generate_structural_paths(
        engine, a, d, budget=_budget(paths=1, steps=5, expansions=100)
    )
    assert len(res_path_limit) == 1
    assert res_path_limit.complete is False
    assert res_path_limit.truncated is True
    assert res_path_limit.truncation_reason == "path_limit_reached"

    # 5. Normal complete search returning all paths:
    res_complete = generate_structural_paths(
        engine, a, d, budget=_budget(paths=10, steps=5, expansions=100)
    )
    assert len(res_complete) == 2
    assert res_complete.complete is True
    assert res_complete.truncated is False
    assert res_complete.truncation_reason is None

    # 6. Container protocol support: iteration, len, indexing, bool
    items = [p for p in res_complete]
    assert len(items) == 2
    assert res_complete[0].nodes == items[0].nodes
    assert bool(res_complete) is True
    assert bool(res_unreachable) is False


def test_typed_auditable_facts_and_transition_decisions():
    """Verify RuntimeFact, FactOrigin, and PrerequisiteDecision tracking in transitions."""
    engine = _membership_admin_graph()
    canonical = engine.to_canonical()
    state = AttackState(control={ACTOR})

    # Case A: Transition with OBSERVED_EVIDENCE
    observed_facts = [
        RuntimeFact(
            "security_group",
            ACTOR,
            GROUP,
            True,
            FactOrigin.OBSERVED_EVIDENCE,
            rationale="LDAP observed",
        ),
        RuntimeFact(
            "membership_change_allowed",
            ACTOR,
            GROUP,
            True,
            FactOrigin.OBSERVED_EVIDENCE,
            rationale="ACL observed",
        ),
        RuntimeFact(
            "directory_write_allowed",
            ACTOR,
            GROUP,
            True,
            FactOrigin.OBSERVED_EVIDENCE,
            rationale="ACL observed",
        ),
        RuntimeFact(
            "membership_usable",
            ACTOR,
            GROUP,
            True,
            FactOrigin.OBSERVED_EVIDENCE,
            rationale="AD rule",
        ),
    ]
    ctx_observed = RuntimeContext(observed_facts)
    req = TransitionRequest("genericall_add_member", ACTOR, ACTOR, GROUP)
    res_observed = evaluate_transition(canonical, state, req, ctx_observed)

    assert isinstance(res_observed, TransitionResult)
    assert res_observed.status is Status.APPLICABLE
    assert not res_observed.is_assumption_backed
    assert len(res_observed.assumption_backed_facts) == 0
    assert len(res_observed.evidence_backed_facts) > 0
    assert all(f.origin is FactOrigin.OBSERVED_EVIDENCE for f in res_observed.evidence_backed_facts)
    assert len(res_observed.decisions) > 0
    assert all(isinstance(d, PrerequisiteDecision) for d in res_observed.decisions)
    assert all(d.satisfied for d in res_observed.decisions)

    # Case B: Transition with DECLARED_ASSUMPTION
    assumed_facts = [
        RuntimeFact(
            "security_group",
            ACTOR,
            GROUP,
            True,
            FactOrigin.OBSERVED_EVIDENCE,
            rationale="LDAP observed",
        ),
        RuntimeFact(
            "membership_change_allowed",
            ACTOR,
            GROUP,
            True,
            FactOrigin.OBSERVED_EVIDENCE,
            rationale="ACL observed",
        ),
        RuntimeFact(
            "directory_write_allowed",
            ACTOR,
            GROUP,
            True,
            FactOrigin.DECLARED_ASSUMPTION,
            scope="domain-write",
            rationale="Operator assumption",
        ),
    ]
    ctx_assumed = RuntimeContext(assumed_facts)
    res_assumed = evaluate_transition(canonical, state, req, ctx_assumed)

    assert res_assumed.status is Status.APPLICABLE
    assert res_assumed.is_assumption_backed
    assert len(res_assumed.assumption_backed_facts) == 1
    assert res_assumed.assumption_backed_facts[0].predicate == "directory_write_allowed"
    assert res_assumed.assumption_backed_facts[0].origin is FactOrigin.DECLARED_ASSUMPTION

    # Check granular decision structure
    decision_map = {d.predicate: d for d in res_assumed.decisions}
    d_assumed = decision_map["directory_write_allowed"]
    assert d_assumed.origin is FactOrigin.DECLARED_ASSUMPTION
    assert d_assumed.satisfied is True
    assert d_assumed.rationale == "Operator assumption"


def test_known_false_snapshot_evidence_vetoes_assumptions_fail_closed():
    """Verify disabled account in snapshot cannot be overridden by assumption."""
    data = copy.deepcopy(TOY)
    # Ensure ACTOR is disabled in snapshot
    for node in data["nodes"]:
        if node["id"] == ACTOR:
            node["enabled"] = False
    data["edges"] = [_edge(ACTOR, HOST, "CanRDP")]
    canonical = data

    state = AttackState(control={ACTOR})
    # Attempt to declare actor_enabled=True via optimistic assumption
    ctx = RuntimeContext(
        [
            RuntimeFact(
                "actor_enabled",
                ACTOR,
                HOST,
                True,
                FactOrigin.DECLARED_ASSUMPTION,
                scope="account-status",
                rationale="optimistic bypass",
            ),
            RuntimeFact("rdp_available", ACTOR, HOST, True, FactOrigin.OBSERVED_EVIDENCE),
            RuntimeFact("authentication_accepted", ACTOR, HOST, True, FactOrigin.OBSERVED_EVIDENCE),
        ]
    )
    req = TransitionRequest("open_remote_interactive_session", ACTOR, ACTOR, HOST)
    res = evaluate_transition(canonical, state, req, ctx)

    # Must fail closed: BLOCKED, not APPLICABLE
    assert res.status is Status.BLOCKED
    assert "actor_enabled" in res.failed
    # Decision must record BLOCKED_EVIDENCE veto, NOT DECLARED_ASSUMPTION
    decision_map = {d.predicate: d for d in res.decisions}
    assert "actor_enabled" in decision_map
    d = decision_map["actor_enabled"]
    assert d.satisfied is False
    assert d.origin is FactOrigin.BLOCKED_EVIDENCE
    assert "known-false" in d.rationale.lower()


def test_missing_facts_produce_indeterminate_status_with_unknown_origin():
    """Verify absent prerequisites produce INDETERMINATE with FactOrigin.UNKNOWN decisions."""
    engine = _membership_admin_graph()
    canonical = engine.to_canonical()
    state = AttackState(control={ACTOR})
    # Provide no facts
    ctx = RuntimeContext({})
    req = TransitionRequest("genericall_add_member", ACTOR, ACTOR, GROUP)
    res = evaluate_transition(canonical, state, req, ctx)

    assert res.status is Status.INDETERMINATE
    assert len(res.unknown) > 0
    decision_map = {d.predicate: d for d in res.decisions}
    for pred in res.unknown:
        d = decision_map.get(pred)
        if d:
            assert d.satisfied is False
            assert d.origin is FactOrigin.UNKNOWN


def test_engine_graph_immutability_throughout_search_and_evaluation():
    """Verify structural EngineGraph is never mutated during search or state expansion."""
    engine = _membership_admin_graph()
    before_nodes = [dict(n) for n in engine.to_canonical()["nodes"]]
    before_edges = [dict(e) for e in engine.to_canonical()["edges"]]

    # Run structural paths
    _ = generate_structural_paths(engine, ACTOR, HOST, budget=_budget(paths=5))

    # Run stateful attack paths
    _ = generate_attack_paths(
        engine,
        ACTOR,
        initial_state=AttackState(control={ACTOR}),
        runtime_context=_membership_admin_context(),
        target_predicate=lambda n: n["id"] == HOST,
        budget=_budget(paths=5, steps=5),
    )

    after_nodes = [dict(n) for n in engine.to_canonical()["nodes"]]
    after_edges = [dict(e) for e in engine.to_canonical()["edges"]]

    assert before_nodes == after_nodes
    assert before_edges == after_edges
    assert len(engine.edges()) == 2


def test_structural_search_retains_target_on_final_expansion_boundary():
    """Finding 1 regression: Target discovered on final allowed expansion is retained."""
    a, b, c = (node["id"] for node in TOY["nodes"][:3])
    # 1. Direct single-edge graph with max_expansions=1
    engine_single = _graph([_edge(a, b, "MemberOf")])
    res_single = generate_structural_paths(
        engine_single, a, b, budget=SearchBudget(max_paths=1, max_steps=1, max_expansions=1)
    )
    assert len(res_single) == 1
    assert res_single[0].nodes == (a, b)
    assert res_single.expansions == 1
    assert res_single.complete is True
    assert res_single.truncated is False

    # 2. Multi-edge graph where target is discovered on the final allowed expansion
    engine_multi = _graph([_edge(a, b, "MemberOf"), _edge(a, c, "GenericAll")])
    res_multi = generate_structural_paths(
        engine_multi, a, b, budget=SearchBudget(max_paths=10, max_steps=5, max_expansions=1)
    )
    assert len(res_multi) == 1
    assert res_multi[0].nodes == (a, b)
    assert res_multi.expansions == 1
    # Edge a -> c could not be expanded due to max_expansions limit
    assert res_multi.truncated is True
    assert res_multi.truncation_reason == "expansion_limit_reached"


def test_semantic_search_detects_truncation_with_multiple_techniques_at_cap():
    """Finding 2 regression: Multiple techniques on relationship with cap flags truncation."""
    engine = _membership_admin_graph()
    # genericall_add_member on ACTOR -> GROUP, with target_predicate matching GROUP
    result = generate_attack_paths(
        engine,
        ACTOR,
        initial_state=AttackState(control={ACTOR}),
        runtime_context=_membership_admin_context(),
        target_predicate=lambda node: node["id"] == GROUP,
        budget=SearchBudget(max_paths=1, max_steps=5, max_expansions=1),
    )
    assert len(result.paths) == 1
    # Because ACTOR -> GROUP has other techniques (e.g. genericall_grant_write_dacl)
    # and GROUP -> HOST relationship in the graph, search must NOT falsely claim complete=True
    assert result.truncated is True
    assert result.complete is False
    assert result.truncation_reason in ("path_limit_reached", "expansion_limit_reached")


def test_semantic_step_limit_is_complete_when_only_action_is_already_used():
    """Step cap is not truncation when the branch has no unused compatible action."""
    engine = _graph([_edge(ACTOR, GROUP, "GenericAll")])
    context = _auditable_context(
        {
            ("security_group", ACTOR, GROUP): True,
            ("membership_change_allowed", ACTOR, GROUP): True,
            ("directory_write_allowed", ACTOR, GROUP): True,
        }
    )
    catalog = tuple(
        technique for technique in load_catalog() if technique.id == "genericall_add_member"
    )
    assert len(catalog) == 1

    result = generate_attack_paths(
        engine,
        ACTOR,
        initial_state=AttackState(control={ACTOR}),
        runtime_context=context,
        target_predicate=lambda _node: False,
        budget=SearchBudget(max_paths=5, max_steps=1, max_expansions=10),
        catalog=catalog,
    )

    assert result.expansions == 1
    assert result.paths == ()
    assert result.complete is True
    assert result.truncated is False
    assert result.truncation_reason is None


def test_legacy_boolean_facts_do_not_manufacture_evidence_provenance():
    """Finding 3 regression: Bare booleans get UNSPECIFIED origin without false evidence."""
    engine = _membership_admin_graph()
    canonical = engine.to_canonical()
    state = AttackState(control={ACTOR})

    # Pass bare boolean facts mapping
    ctx = RuntimeContext(
        {
            ("security_group", ACTOR, GROUP): True,
            ("membership_change_allowed", ACTOR, GROUP): True,
            ("directory_write_allowed", ACTOR, GROUP): True,
        }
    )
    req = TransitionRequest("genericall_add_member", ACTOR, ACTOR, GROUP)
    res = evaluate_transition(canonical, state, req, ctx)

    assert res.status is Status.APPLICABLE
    # Must NOT manufacture evidence or assumption provenance
    assert len(res.evidence_backed_facts) == 0
    assert len(res.assumption_backed_facts) == 0
    assert res.is_assumption_backed is False
    decision_map = {d.predicate: d for d in res.decisions}
    assert decision_map["security_group"].origin is FactOrigin.UNSPECIFIED

    # Direct semantic evaluation remains backward-compatible, but audited attack
    # search must not let unclassified legacy truth authorize traversal.
    with pytest.raises(ValueError, match="auditable typed runtime facts"):
        generate_attack_paths(
            engine,
            ACTOR,
            initial_state=state,
            runtime_context=ctx,
            target_predicate=lambda node: node["id"] == GROUP,
            budget=_budget(),
        )

    # Supported string forms are canonicalized to the StrEnum before the audited
    # search boundary checks identity, so "unspecified" cannot bypass fail-closed.
    string_origin_fact = RuntimeFact(
        "security_group",
        ACTOR,
        GROUP,
        True,
        "unspecified",
        rationale="legacy string origin",
    )
    assert string_origin_fact.origin is FactOrigin.UNSPECIFIED
    string_origin_ctx = RuntimeContext([string_origin_fact])
    with pytest.raises(ValueError, match="UNSPECIFIED facts are not authoritative"):
        generate_attack_paths(
            engine,
            ACTOR,
            initial_state=state,
            runtime_context=string_origin_ctx,
            target_predicate=lambda node: node["id"] == GROUP,
            budget=_budget(),
        )


def test_duplicate_runtime_facts_fail_closed_and_reject_contradictions():
    """Finding 4 regression: Contradictory duplicate facts are rejected fail-closed."""
    fact_blocked = RuntimeFact(
        "actor_enabled",
        ACTOR,
        HOST,
        False,
        FactOrigin.BLOCKED_EVIDENCE,
        rationale="Account is disabled",
    )
    fact_assumed = RuntimeFact(
        "actor_enabled",
        ACTOR,
        HOST,
        True,
        FactOrigin.DECLARED_ASSUMPTION,
        scope="account-policy",
        rationale="Optimistic bypass",
    )

    # Order A: [BLOCKED_EVIDENCE=False, DECLARED_ASSUMPTION=True]
    with pytest.raises(ValueError, match="contradictory runtime facts"):
        RuntimeContext([fact_blocked, fact_assumed])

    # Order B: [DECLARED_ASSUMPTION=True, BLOCKED_EVIDENCE=False]
    with pytest.raises(ValueError, match="contradictory runtime facts"):
        RuntimeContext([fact_assumed, fact_blocked])

    fact_unknown_true = RuntimeFact(
        "actor_enabled",
        ACTOR,
        HOST,
        True,
        FactOrigin.UNKNOWN,
        rationale="Source does not establish truth",
    )
    fact_assumed_true = RuntimeFact(
        "actor_enabled",
        ACTOR,
        HOST,
        True,
        FactOrigin.DECLARED_ASSUMPTION,
        scope="account-policy",
        rationale="Scenario assumes account enabled",
    )

    # Same truth value but different provenance must not be first-record-wins.
    for ordered in (
        [fact_unknown_true, fact_assumed_true],
        [fact_assumed_true, fact_unknown_true],
    ):
        with pytest.raises(ValueError, match="ambiguous duplicate runtime facts"):
            RuntimeContext(ordered)


def test_declared_assumption_ledger_shape_and_unknown_origin_invariant():
    """Finding 5 regression: DECLARED_ASSUMPTION requires scope; UNKNOWN origin never satisfies."""
    # 1. Missing scope on DECLARED_ASSUMPTION raises ValueError
    with pytest.raises(ValueError, match="non-empty scope"):
        RuntimeFact(
            "membership_usable",
            ACTOR,
            GROUP,
            True,
            FactOrigin.DECLARED_ASSUMPTION,
            rationale="Rationale only, no scope",
        )

    # 2. Missing rationale on DECLARED_ASSUMPTION raises ValueError
    with pytest.raises(ValueError, match="non-empty rationale"):
        RuntimeFact(
            "membership_usable",
            ACTOR,
            GROUP,
            True,
            FactOrigin.DECLARED_ASSUMPTION,
            scope="membership-scope",
        )

    # 3. UNKNOWN-origin fact with value=True cannot satisfy prerequisite
    engine = _membership_admin_graph()
    canonical = engine.to_canonical()
    state = AttackState(control={ACTOR})

    unknown_fact = RuntimeFact(
        "directory_write_allowed",
        ACTOR,
        GROUP,
        True,
        FactOrigin.UNKNOWN,
        rationale="Telemetrically unobserved",
    )
    ctx = RuntimeContext(
        [
            RuntimeFact("security_group", ACTOR, GROUP, True, FactOrigin.OBSERVED_EVIDENCE),
            RuntimeFact(
                "membership_change_allowed", ACTOR, GROUP, True, FactOrigin.OBSERVED_EVIDENCE
            ),
            unknown_fact,
        ]
    )
    req = TransitionRequest("genericall_add_member", ACTOR, ACTOR, GROUP)
    res = evaluate_transition(canonical, state, req, ctx)

    # Must remain INDETERMINATE, not APPLICABLE
    assert res.status is Status.INDETERMINATE
    assert "directory_write_allowed" in res.unknown
    decision_map = {d.predicate: d for d in res.decisions}
    d = decision_map["directory_write_allowed"]
    assert d.satisfied is False
    assert d.origin is FactOrigin.UNKNOWN


def test_attack_search_can_require_success_state_beyond_target_node_reachability():
    engine = _graph(
        [
            _edge(ACTOR, HOST, "CanPSRemote"),
            _edge(ACTOR, HOST, "AdminTo"),
        ]
    )
    context = _auditable_context(
        {
            ("winrm_available", ACTOR, HOST): True,
            ("authentication_accepted", ACTOR, HOST): True,
            ("admin_channel", ACTOR, HOST): True,
        }
    )
    catalog = tuple(
        item
        for item in load_catalog()
        if item.id in {"open_winrm_remote_session", "obtain_admin_execution_on_host"}
    )
    kwargs = {
        "graph": engine,
        "actor": ACTOR,
        "initial_state": AttackState(control={ACTOR}),
        "runtime_context": context,
        "target_predicate": lambda node: node["id"] == HOST,
        "budget": _budget(paths=10, steps=3, expansions=50),
        "catalog": catalog,
    }

    node_only = generate_attack_paths(**kwargs)
    assert any(
        len(path.transition_history) == 1
        and path.transition_history[0].result.technique.id == "open_winrm_remote_session"
        for path in node_only.paths
    )

    state_aware = generate_attack_paths(
        **kwargs,
        success_state_predicate=lambda state: HOST in state.admin_control,
    )
    assert state_aware.paths
    assert all(
        path.final_state is not None and HOST in path.final_state.admin_control
        for path in state_aware.paths
    )
    assert not any(
        len(path.transition_history) == 1
        and path.transition_history[0].result.technique.id == "open_winrm_remote_session"
        for path in state_aware.paths
    )
