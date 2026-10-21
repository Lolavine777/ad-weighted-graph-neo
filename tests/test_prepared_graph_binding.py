"""Negative controls for public replay reuse with equal snapshot IDs (#297)."""

from dataclasses import replace
from unittest.mock import patch

import pytest

from scripts.research.asrep_inputs import V, inputs, ranking_inputs
from src.engine import EngineGraph, run_attack_query
from src.engine.ranking import RankingValidationError
from src.engine.ranking.adapter_145 import adapt_search_candidate
from src.engine.ranking.orchestration import evaluate_search_candidates
from src.engine.ranking.verification import verify_search_envelope
from src.engine.semantics.credentials import replay_path
from src.engine.semantics.evaluator import PreparedSemanticGraph
from src.parser.snapshot_facts import SnapshotFacts, graph_digest


@pytest.fixture
def sample():
    graph, query = inputs()
    payload, bindings = ranking_inputs(graph, query)
    path = run_attack_query(query, graph).paths[0]
    actions = [
        bindings[(r.technique_id, r.actor, r.source, r.target)]
        for r in (s.result.request for s in path.transition_history)
    ]
    candidate = dict(
        candidate_id="binding_probe",
        target_asset_id=query["target"],
        route_id="binding_route",
        action_mapping=actions,
        path_result=path,
    )
    metadata = {
        **payload["query_metadata"],
        "target_impact_assessments": payload.get("target_impact_assessments", {}),
    }
    envelope = adapt_search_candidate(
        path_result=path,
        candidate_id=candidate["candidate_id"],
        target_asset_id=query["target"],
        query_metadata=metadata,
        action_mapping=actions,
        route_id=candidate["route_id"],
        bound_actions_catalog=payload.get("bound_actions"),
    )
    return graph, payload, path, candidate, envelope


def changed_projection(graph, *, disable=False):
    canonical = graph.to_canonical()
    if disable:
        next(n for n in canonical["nodes"] if n["id"] == V)["enabled"] = False
    else:
        canonical["nodes"][0]["label"] += "-different-projection"
    return canonical


def test_schema_validated_graph_still_rejects_unbound_facts(sample):
    graph, *_ = sample
    changed = changed_projection(graph)
    assert graph_digest(changed) != graph.snapshot_facts.graph_sha256
    with pytest.raises(ValueError, match="snapshot facts do not match canonical graph"):
        EngineGraph.from_canonical(changed, snapshot_facts=graph.snapshot_facts, _validated=True)


def test_ranking_rejects_stale_facts_without_rejecting_matched_control(sample):
    graph, payload, _, candidate, _ = sample
    for canonical, accepted in [(graph.to_canonical(), 1), (changed_projection(graph), 0)]:
        result = evaluate_search_candidates(
            payload, [candidate], canonical_graph=canonical, snapshot_facts=graph.snapshot_facts
        )["roundtrip_result"]
        assert result["search_audit"]["candidates_adapted"] == accepted
        assert result["search_audit"]["candidates_rejected_by_adapter"] == 1 - accepted


def test_supplied_engine_rejects_different_canonical_projection(sample):
    graph, payload, _, candidate, _ = sample
    with pytest.raises(RankingValidationError, match="canonical_graph does not match"):
        evaluate_search_candidates(
            payload, [candidate], canonical_graph=changed_projection(graph), engine_graph=graph
        )


def test_supplied_engine_rejects_different_facts(sample):
    graph, payload, _, candidate, _ = sample
    stale = replace(graph.snapshot_facts, graph_sha256="sha256:" + "0" * 64)
    with pytest.raises(RankingValidationError, match="snapshot facts do not match"):
        evaluate_search_candidates(payload, [candidate], engine_graph=graph, snapshot_facts=stale)


def test_supplied_engine_and_matching_canonical_are_accepted(sample):
    graph, payload, _, candidate, _ = sample
    result = evaluate_search_candidates(
        payload,
        [candidate],
        canonical_graph=graph.to_canonical(),
        snapshot_facts=graph.snapshot_facts,
        engine_graph=graph,
        prepared=graph.to_prepared(),
    )["roundtrip_result"]
    assert result["search_audit"]["candidates_adapted"] == 1


@pytest.mark.parametrize("through_verifier", [False, True])
def test_foreign_prepared_cannot_replay_disabled_target(sample, through_verifier):
    graph, payload, path, _, envelope = sample
    disabled = changed_projection(graph, disable=True)
    facts = replace(graph.snapshot_facts, graph_sha256=graph_digest(disabled))
    other = EngineGraph.from_canonical(disabled, snapshot_facts=facts)
    assert other.metadata["snapshot_id"] == graph.metadata["snapshot_id"]
    with pytest.raises(ValueError, match="prepared graph does not match"):
        if through_verifier:
            verify_search_envelope(
                path, other, envelope, payload["query_metadata"], prepared=graph.to_prepared()
            )
        else:
            replay_path(path, other, prepared=graph.to_prepared())
    with pytest.raises(ValueError, match="semantic replay disagrees"):
        replay_path(path, other)


def test_equal_graph_with_different_fact_view_is_rejected(sample):
    graph, _, path, *_ = sample
    without_facts = PreparedSemanticGraph(graph.to_canonical())
    with pytest.raises(ValueError, match="prepared graph does not match"):
        replay_path(path, graph, prepared=without_facts)


@pytest.mark.parametrize("reverse_order", [False, True])
def test_equivalent_external_prepared_view_is_accepted(sample, reverse_order):
    graph, _, path, *_ = sample
    canonical = graph.to_canonical()
    if reverse_order:
        for name in ("nodes", "edges", "assessments"):
            canonical[name].reverse()
    supplied = PreparedSemanticGraph(canonical, snapshot_facts=graph.snapshot_facts)
    assert replay_path(path, graph, prepared=supplied) == path.final_state


def test_owned_replay_reuses_binding_without_revalidation(sample):
    graph, _, path, *_ = sample
    prepared = graph.to_prepared()
    with (
        patch.object(graph, "to_canonical", side_effect=AssertionError("full graph copy")),
        patch.object(SnapshotFacts, "validate_binding", side_effect=AssertionError("revalidation")),
    ):
        assert replay_path(path, graph, prepared=prepared) == path.final_state
        assert replay_path(path, graph) == path.final_state


def test_owned_prepared_public_indices_cannot_be_replaced_to_forge_replay(sample):
    graph, payload, path, _, envelope = sample
    disabled = changed_projection(graph, disable=True)
    facts = replace(graph.snapshot_facts, graph_sha256=graph_digest(disabled))
    other = EngineGraph.from_canonical(disabled, snapshot_facts=facts)
    prepared = other.to_prepared()
    # Canonical content remains disabled and correctly bound. Before this guard,
    # replacing only the public node index minted an invalid replay binding.
    for attribute in ("nodes_by_id", "relationships"):
        with pytest.raises(AttributeError):
            setattr(prepared, attribute, getattr(graph.to_prepared(), attribute))
    with pytest.raises(ValueError, match="semantic replay disagrees"):
        verify_search_envelope(path, other, envelope, payload["query_metadata"])
