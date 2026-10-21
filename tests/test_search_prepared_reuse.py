"""Shared search preparation preserves bindings and isolates public witnesses."""

from unittest.mock import patch

from test_engine import (
    ACTOR,
    HOST,
    _budget,
    _membership_admin_context,
    _membership_admin_graph,
)

from scripts.research.asrep_inputs import inputs
from src.engine.query import materialize_query
from src.engine.search import generate_attack_paths
from src.engine.semantics import AttackState
from src.parser.snapshot_facts import SnapshotFacts


def test_materialization_and_search_reuse_only_the_owned_prepared_graph():
    graph, query = inputs()
    prepared = graph.to_prepared()
    with (
        patch.object(graph, "to_canonical", side_effect=AssertionError("full graph copy")),
        patch.object(SnapshotFacts, "validate_binding", side_effect=AssertionError("rebinding")),
    ):
        for _ in range(2):
            result = materialize_query(query, graph).search(graph)
            assert result.paths
            assert graph.to_prepared() is prepared


def test_callbacks_and_witness_edges_cannot_mutate_the_shared_engine_graph():
    graph = _membership_admin_graph()
    before = graph.to_canonical()

    def target(node):
        node["label"] = "caller mutation"
        return node["id"] == HOST

    result = generate_attack_paths(
        graph,
        ACTOR,
        initial_state=AttackState(control={ACTOR}),
        runtime_context=_membership_admin_context(),
        target_predicate=target,
        success_state_predicate=lambda state: HOST in state.admin_control,
        budget=_budget(),
    )
    assert result.paths
    for path in result.paths:
        for edge in path.edges:
            edge["provenance"].clear()
            edge["weight"] = -1
    assert graph.to_canonical() == before
