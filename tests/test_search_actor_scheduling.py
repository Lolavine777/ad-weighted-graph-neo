"""Regression suite for branch-local actor scheduling (Issue #294, Change 1).

Covers:
1. Confirmed cumulative-goal case (U:H1 -> V:H2 -> U:H3) with multiple usable identities.
2. Ordinary single-goal behavior preserving first-goal termination and direct paths.
3. Initially usable identities distinct from query initial_actor.
4. Returning to original actor after a real credential activation.
5. Negative wrong-context isolation: identity usable only in context Y cannot act in context X.
6. Negative uncontrolled-identity: non-usable, non-controlled node cannot act.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts.check_contract import canonical_edge_id
from src.engine import EngineGraph, materialize_query
from src.engine.semantics import AttackState, Status

ROOT = Path(__file__).resolve().parents[1]

IDS = {n: f"S-1-5-21-1000-2000-3000-{1101 + i}" for i, n in enumerate(("U", "V", "W", "G1", "G2"))}
IDS.update(
    {n: f"10000000-0000-4000-8000-{i:012d}" for i, n in enumerate(("X", "H1", "H2", "H3", "Y"), 1)}
)


def make_graph(
    name: str, edges: list[tuple[str, str, str]], extra: list[str] | None = None
) -> EngineGraph:
    names = set(extra or ()) | {n for s, _, t in edges for n in (s, t)} | {"U", "X"}
    toy = json.loads((ROOT / "data/samples/toy-graph.json").read_text())
    toy["metadata"].update(
        description=f"Actor scheduling test {name}", code_version="issue-294/test"
    )
    toy["assessments"] = []
    toy["nodes"] = [
        dict(
            id=IDS[n],
            label=n,
            kind=(
                "Computer"
                if n in {"X", "Y", "H1", "H2", "H3"}
                else "Group"
                if n.startswith("G")
                else "User"
            ),
            domain="EXAMPLE.TEST",
            is_boundary=False,
            enabled=True,
        )
        for n in sorted(names)
    ]
    toy["edges"] = [
        dict(
            id=canonical_edge_id(IDS[s], IDS[t], kind),
            source=IDS[s],
            target=IDS[t],
            kind=kind,
            weight=1.0,
            provenance=[
                dict(
                    raw_file=f"synthetic://test/{name}",
                    collector="test",
                    timestamp="2026-10-16T00:00:00Z",
                    evidence_type="positive",
                )
            ],
        )
        for s, kind, t in edges
    ]
    return EngineGraph.from_canonical(toy)


def fact(predicate: str, subject: str, target: str, value: bool = True) -> dict:
    return dict(
        predicate=predicate,
        subject=IDS.get(subject, subject),
        target=IDS.get(target, target),
        value=value,
        origin="declared_assumption",
        scope="issue-294/test",
        rationale="Declared test guard",
        provenance_reference="synthetic://test/guards",
    )


def facts(predicates: str, subject: str, target: str) -> list[dict]:
    return [fact(p, subject, target) for p in predicates.split()]


def test_cumulative_goal_two_usable_actors_scheduled_and_return():
    """U@X and V@X are both initially usable; goal requires admin on H1, H2, and H3."""
    edges = [("U", "AdminTo", "H1"), ("V", "AdminTo", "H2"), ("U", "AdminTo", "H3")]
    graph = make_graph("cumulative-actors", edges)
    runtime = sum((facts("admin_channel authentication_accepted", u, h) for u, _, h in edges), [])
    query = dict(
        source_foothold=IDS["X"],
        initial_actor=IDS["U"],
        authentication_context=IDS["X"],
        initial_state=dict(usable_identity=[[IDS["U"], IDS["X"]], [IDS["V"], IDS["X"]]]),
        target=IDS["H3"],
        target_goal=dict(
            target=IDS["H3"],
            required_state={"admin_control": [IDS["H1"], IDS["H2"], IDS["H3"]]},
        ),
        runtime_facts=runtime,
        allowed_techniques=["obtain_admin_execution_on_host"],
        scenario_reference="issue-294/cumulative",
        budget=dict(max_paths=100, max_steps=12, max_expansions=1000),
    )
    materialized = materialize_query(query, graph)
    result = materialized.run(graph)

    assert result.complete is True
    assert result.status == "success"
    assert result.truncated is False
    assert result.truncation_reason is None
    assert len(result.paths) >= 1

    traces = [
        [
            (s.result.request.actor, s.result.request.technique_id, s.result.request.target)
            for s in p.transition_history
        ]
        for p in result.paths
    ]
    # Check uniqueness of programs and initial source attribution
    assert len({tuple(t) for t in traces}) == len(result.paths)
    for p in result.paths:
        assert p.initial_actor == IDS["U"]

    # Assert the specific U:H1 -> V:H2 -> U:H3 ordering exists with exactly 3 existing actions
    expected_sequence = [
        (IDS["U"], "obtain_admin_execution_on_host", IDS["H1"]),
        (IDS["V"], "obtain_admin_execution_on_host", IDS["H2"]),
        (IDS["U"], "obtain_admin_execution_on_host", IDS["H3"]),
    ]
    assert expected_sequence in traces
    matching_path = next(
        p for p, t in zip(result.paths, traces, strict=True) if t == expected_sequence
    )
    assert len(matching_path.transition_history) == 3
    assert matching_path.final_state is not None
    assert {IDS["H1"], IDS["H2"], IDS["H3"]}.issubset(matching_path.final_state.admin_control)


def test_single_goal_with_multiple_usable_identities_terminates_at_first_goal():
    """When target H2 is reachable directly by V, search finds direct and composed paths."""
    edges = [("U", "AdminTo", "H1"), ("V", "AdminTo", "H2")]
    graph = make_graph("single-goal-multiple-actors", edges)
    runtime = sum((facts("admin_channel authentication_accepted", u, h) for u, _, h in edges), [])
    query = dict(
        source_foothold=IDS["X"],
        initial_actor=IDS["U"],
        authentication_context=IDS["X"],
        initial_state=dict(usable_identity=[[IDS["U"], IDS["X"]], [IDS["V"], IDS["X"]]]),
        target=IDS["H2"],
        target_goal=dict(target=IDS["H2"], required_state={"admin_control": [IDS["H2"]]}),
        runtime_facts=runtime,
        allowed_techniques=["obtain_admin_execution_on_host"],
        scenario_reference="issue-294/single-goal",
        budget=dict(max_paths=10, max_steps=6, max_expansions=100),
    )
    materialized = materialize_query(query, graph)
    result = materialized.run(graph)

    assert result.status == "success"
    assert result.complete is True
    assert len(result.paths) == 2
    traces = [
        [
            (s.result.request.actor, s.result.request.technique_id, s.result.request.target)
            for s in p.transition_history
        ]
        for p in result.paths
    ]
    assert [(IDS["V"], "obtain_admin_execution_on_host", IDS["H2"])] in traces
    assert [
        (IDS["U"], "obtain_admin_execution_on_host", IDS["H1"]),
        (IDS["V"], "obtain_admin_execution_on_host", IDS["H2"]),
    ] in traces
    for path in result.paths:
        assert path.transition_history[-1].result.request.target == IDS["H2"]
        assert path.initial_actor == IDS["U"]


def test_actor_switching_after_real_activation_and_return():
    """U activates V from recovered secret, V performs an action, then U performs an action."""
    edges = [("U", "AdminTo", "H1"), ("V", "AdminTo", "H2"), ("U", "AdminTo", "H3")]
    graph = make_graph("activation-and-return", edges)
    runtime = sum(
        (facts("admin_channel authentication_accepted", u, h) for u, _, h in edges), []
    ) + facts("secret_valid network_kdc_reachable authentication_accepted", "V", "X")
    initial_state = dict(
        usable_identity=[[IDS["U"], IDS["X"]]],
        recovered_secret=[
            dict(
                owner=IDS["V"],
                context=IDS["X"],
                form="password",
                provenance=["synthetic://test"],
            )
        ],
    )
    query = dict(
        source_foothold=IDS["X"],
        initial_actor=IDS["U"],
        authentication_context=IDS["X"],
        initial_state=initial_state,
        target=IDS["H3"],
        target_goal=dict(
            target=IDS["H3"],
            required_state={"admin_control": [IDS["H1"], IDS["H2"], IDS["H3"]]},
        ),
        runtime_facts=runtime,
        allowed_techniques=["activate_recovered_identity", "obtain_admin_execution_on_host"],
        scenario_reference="issue-294/activation-return",
        budget=dict(max_paths=100, max_steps=12, max_expansions=1000),
    )
    materialized = materialize_query(query, graph)
    result = materialized.run(graph)

    assert result.status == "success"
    assert result.complete is True
    assert len(result.paths) >= 1

    traces = [
        [
            (s.result.request.actor, s.result.request.technique_id, s.result.request.target)
            for s in p.transition_history
        ]
        for p in result.paths
    ]
    assert len({tuple(t) for t in traces}) == len(result.paths)
    for p in result.paths:
        assert p.initial_actor == IDS["U"]

    # Assert exact ordering containing real activation, V acting, then U acting again
    expected_sequence = [
        (IDS["U"], "obtain_admin_execution_on_host", IDS["H1"]),
        (IDS["V"], "activate_recovered_identity", IDS["X"]),
        (IDS["V"], "obtain_admin_execution_on_host", IDS["H2"]),
        (IDS["U"], "obtain_admin_execution_on_host", IDS["H3"]),
    ]
    assert expected_sequence in traces


def test_negative_wrong_context_usable_identity_cannot_act():
    """Identity V is usable in context Y, not context X; V cannot act in context X."""
    edges = [("U", "AdminTo", "H1"), ("V", "AdminTo", "H2")]
    graph = make_graph("wrong-context", edges, extra=["Y"])
    runtime = sum((facts("admin_channel authentication_accepted", u, h) for u, _, h in edges), [])
    query = dict(
        source_foothold=IDS["X"],
        initial_actor=IDS["U"],
        authentication_context=IDS["X"],
        # V is declared usable in context Y, NOT context X
        initial_state=dict(usable_identity=[[IDS["U"], IDS["X"]], [IDS["V"], IDS["Y"]]]),
        target=IDS["H2"],
        target_goal=dict(target=IDS["H2"], required_state={"admin_control": [IDS["H2"]]}),
        runtime_facts=runtime,
        allowed_techniques=["obtain_admin_execution_on_host"],
        scenario_reference="issue-294/wrong-context",
        budget=dict(max_paths=10, max_steps=6, max_expansions=100),
    )
    materialized = materialize_query(query, graph)
    result = materialized.run(graph)

    # V cannot act in context X, and U cannot reach H2; query should return no_path
    assert result.status == "no_path"
    assert len(result.paths) == 0
    assert result.complete


def test_negative_uncontrolled_identity_cannot_act():
    """Identity W exists in nodes but has no usable_identity and no control; W cannot act."""
    edges = [("U", "AdminTo", "H1"), ("W", "AdminTo", "H2")]
    graph = make_graph("uncontrolled-identity", edges)
    runtime = sum((facts("admin_channel authentication_accepted", u, h) for u, _, h in edges), [])
    query = dict(
        source_foothold=IDS["X"],
        initial_actor=IDS["U"],
        authentication_context=IDS["X"],
        # W is NOT in usable_identity and NOT in control
        initial_state=dict(usable_identity=[[IDS["U"], IDS["X"]]]),
        target=IDS["H2"],
        target_goal=dict(target=IDS["H2"], required_state={"admin_control": [IDS["H2"]]}),
        runtime_facts=runtime,
        allowed_techniques=["obtain_admin_execution_on_host"],
        scenario_reference="issue-294/uncontrolled",
        budget=dict(max_paths=10, max_steps=6, max_expansions=100),
    )
    materialized = materialize_query(query, graph)
    result = materialized.run(graph)

    assert result.status == "no_path"
    assert len(result.paths) == 0
    assert result.complete


def test_search_caps_path_limit_reported_accurately():
    """When max_paths is reached, search reports complete=False, truncated=True."""
    edges = [("U", "AdminTo", "H1"), ("V", "AdminTo", "H1")]
    graph = make_graph("caps-path-limit", edges)
    query = dict(
        source_foothold=IDS["X"],
        initial_actor=IDS["U"],
        authentication_context=IDS["X"],
        initial_state=dict(usable_identity=[[IDS["U"], IDS["X"]], [IDS["V"], IDS["X"]]]),
        target=IDS["H1"],
        target_goal=dict(target=IDS["H1"], required_state={"admin_control": [IDS["H1"]]}),
        runtime_facts=sum(
            (facts("admin_channel authentication_accepted", u, h) for u, _, h in edges), []
        ),
        allowed_techniques=["obtain_admin_execution_on_host"],
        scenario_reference="issue-294/caps-path-limit",
        budget=dict(max_paths=1, max_steps=5, max_expansions=100),
    )
    result = materialize_query(query, graph).run(graph)

    assert len(result.paths) == 1
    assert result.complete is False
    assert result.truncated is True
    assert result.truncation_reason == "path_limit_reached"


def test_search_caps_expansion_limit_reported_accurately():
    """When max_expansions is reached, search reports complete=False, truncated=True."""
    edges = [("U", "AdminTo", "H1"), ("V", "AdminTo", "H1")]
    graph = make_graph("caps-expansion-limit", edges)
    query = dict(
        source_foothold=IDS["X"],
        initial_actor=IDS["U"],
        authentication_context=IDS["X"],
        initial_state=dict(usable_identity=[[IDS["U"], IDS["X"]], [IDS["V"], IDS["X"]]]),
        target=IDS["H1"],
        target_goal=dict(target=IDS["H1"], required_state={"admin_control": [IDS["H1"]]}),
        runtime_facts=sum(
            (facts("admin_channel authentication_accepted", u, h) for u, _, h in edges), []
        ),
        allowed_techniques=["obtain_admin_execution_on_host"],
        scenario_reference="issue-294/caps-expansions-limit",
        budget=dict(max_paths=10, max_steps=5, max_expansions=1),
    )
    result = materialize_query(query, graph).run(graph)

    assert len(result.paths) == 1
    assert result.complete is False
    assert result.truncated is True
    assert result.truncation_reason == "expansion_limit_reached"
    assert result.expansions == 1


def test_withheld_session_on_admin_controlled_host_yields_indeterminate_not_no_path():
    """Withheld HasSession on an administratively controlled host is evaluated.

    Preserves the baseline diagnostic (status='indeterminate'), empty additions on
    indeterminate attempt, no paths, and prevents an incorrect no-path proof.
    """
    graph = make_graph("withheld-session", [], extra=["H1", "V"])
    query = dict(
        source_foothold=IDS["X"],
        initial_actor=IDS["U"],
        authentication_context=IDS["X"],
        initial_state=dict(usable_identity=[[IDS["U"], IDS["X"]]], admin_control=[IDS["H1"]]),
        target=IDS["V"],
        target_goal=dict(target=IDS["V"], required_state=dict(credential_material=[IDS["V"]])),
        runtime_facts=facts("session_fresh session_present credential_accessible", "H1", "V"),
        withheld_relationships=[[IDS["H1"], "HasSession", IDS["V"]]],
        allowed_techniques=["recover_session_credential_material"],
        scenario_reference="issue-294/withheld-session",
        budget=dict(max_paths=10, max_steps=5, max_expansions=100),
    )
    result = materialize_query(query, graph).run(graph)

    assert result.complete is True
    assert result.status == "indeterminate"
    assert len(result.paths) == 0
    assert len(result.attempts) == 1
    attempt = result.attempts[0]
    assert attempt.status == Status.INDETERMINATE
    assert attempt.technique.id == "recover_session_credential_material"
    assert attempt.request.actor == IDS["U"]
    assert attempt.request.source == IDS["H1"]
    assert attempt.request.target == IDS["V"]
    assert attempt.additions == AttackState()
