"""Domain denominators, independent sources, and resumable bounded observations."""

import copy
import json
from dataclasses import replace

import pytest
from test_engine import ACTOR, GROUP, _edge
from test_exposure import DC, DOMAIN
from test_exposure import graph as graph_fixture

from scripts import neo_domain
from src.engine.graph import EngineGraph
from src.engine.query import materialize_query, run_attack_query
from src.engine.ranking.resolution_service import canonical_digest
from src.engine.semantics.scenario_policy import NEO_STANDARD_PROFILE


@pytest.fixture
def graph():
    return graph_fixture.__wrapped__()


def survey_graph(graph):
    raw = graph.to_canonical()
    raw["nodes"].append({**copy.deepcopy(graph.node(GROUP)), "id": DOMAIN + "-519"})
    return EngineGraph.from_canonical(raw)


def test_all_eligible_sources_are_selected_without_reachability_filter(graph):
    graph = survey_graph(graph)
    inventory, request = neo_domain.build_survey(graph)
    assert {s.node_id for s in request.sources} == {s["node_id"] for s in inventory["sources"]}
    assert {g.target_node_id for g in request.resolve_target_goals()} == {
        DOMAIN + "-512",
        DOMAIN + "-519",
    }
    assert all(s.authentication_context == DC for s in request.sources)
    assert any(s.profile_kind == "computer_usable_identity" for s in request.sources)
    summary = neo_domain.summarize({}, request, 0)
    assert summary["declared_pairs"] == len(request.sources) * 2
    assert summary["not_run_pairs"] == summary["declared_pairs"]
    assert request.common_budget.max_steps == 12
    _, shallow = neo_domain.build_survey(graph, max_steps=5)
    assert shallow.common_budget.max_steps == 5


def test_child_domain_can_be_surveyed_without_an_enterprise_admins_group(graph):
    _, request = neo_domain.build_survey(graph, domain_sid=DOMAIN)
    assert [g.target_node_id for g in request.resolve_target_goals()] == [DOMAIN + "-512"]
    with pytest.raises(ValueError, match="observed canonical Domain"):
        neo_domain.build_survey(graph, domain_sid="S-1-5-21-9-8-7")


def test_snapshot_binding_does_not_change_neo_assumption_rules(graph):
    profile = neo_domain.scenario_profile(graph)
    original = NEO_STANDARD_PROFILE.canonical_dict()
    assert profile.canonical_dict() == {
        **original,
        "bound_snapshot_id": graph.metadata["snapshot_id"],
    }
    assert NEO_STANDARD_PROFILE.canonical_dict() == original


def test_no_session_input_is_explained_without_creating_session_or_identity(graph):
    _, request = neo_domain.build_survey(graph, scenario="host-compromise")
    before = graph.to_canonical()
    coverage = neo_domain.input_coverage(graph, request, "host-compromise")
    assert coverage["observed_session_edges"] == 0
    assert coverage["computer_initial_capability"] == "local_admin_only"
    assert any("không chứng minh máy an toàn" in n for n in coverage["notes"])
    assert graph.to_canonical() == before
    assert all(
        not s.to_foothold_profile(graph=graph).initial_attack_state.usable_identity
        for s in request.sources
        if s.node_kind == "Computer"
    )
    _, identity_request = neo_domain.build_survey(graph)
    identity = neo_domain.input_coverage(graph, identity_request, "identity")
    assert not identity["notes"] and identity["observed_session_edges"] == 0


def test_observed_session_is_counted_separately_from_declared_host_control(graph):
    raw = graph.to_canonical()
    raw["edges"].append(_edge(DC, ACTOR, "HasSession"))
    graph = EngineGraph.from_canonical(raw)
    _, request = neo_domain.build_survey(graph, scenario="host-compromise", source_ids=[DC])
    coverage = neo_domain.input_coverage(graph, request, "host-compromise")
    assert coverage["observed_session_edges"] == 1
    assert coverage["selected_computers_with_observed_session"] == 1
    assert not any("không có cạnh HasSession" in n for n in coverage["notes"])
    assert (
        not request.sources[0].to_foothold_profile(graph=graph).initial_attack_state.usable_identity
    )


def test_native_evaluation_preserves_independent_capabilities_and_replays_slice(graph, monkeypatch):
    graph = survey_graph(graph)
    _, request = neo_domain.build_survey(graph)
    monkeypatch.setattr(neo_domain, "_graph", graph, raising=False)
    monkeypatch.setattr(neo_domain, "_request", request, raising=False)
    monkeypatch.setattr(
        neo_domain, "_sources", {s.node_id: s for s in request.sources}, raising=False
    )
    monkeypatch.setattr(
        neo_domain,
        "_goals",
        {g.target_node_id: g for g in request.resolve_target_goals()},
        raising=False,
    )
    monkeypatch.setattr(
        neo_domain,
        "_policy",
        replace(NEO_STANDARD_PROFILE, bound_snapshot_id=graph.metadata["snapshot_id"]),
        raising=False,
    )
    monkeypatch.setattr(
        neo_domain, "_effort", neo_domain.load_effort_profile("neo-c-v1"), raising=False
    )
    row = neo_domain._evaluate((ACTOR, GROUP))
    assert row["reached"] and row["C"] == 0
    state = row["witness"]["transition_history"][0]["result"]["before"]
    assert state["control"] == [ACTOR]
    assert all(owner == ACTOR for owner, _ in state["usable_identity"])
    assert row["witness"]["final_state"]["effective_member"] == [[ACTOR, GROUP]]


def test_summary_keeps_truncation_unknown_error_and_not_run_distinct(graph):
    _, request = neo_domain.build_survey(survey_graph(graph))
    sources = list(request.sources)
    goals = request.resolve_target_goals()
    rows = {
        (sources[0].node_id, goals[0].target_node_id): {
            "status": "truncated",
            "truncated": True,
            "reached": False,
            "unknown": {"gate": 2},
        },
        (sources[1].node_id, goals[0].target_node_id): {"status": "error"},
    }
    summary = neo_domain.summarize(rows, request, 1)
    assert summary["truncated_pairs"] == 1 and summary["errors"] == 1
    assert summary["reached_pairs"] == summary["no_path_proven_pairs"] == 0
    assert summary["not_run_pairs"] == summary["declared_pairs"] - 2


def test_checkpoint_torn_tail_is_recoverable_but_tampering_is_not(tmp_path):
    path = tmp_path / "cells.jsonl"
    row = {"source": "a", "target": "b", "status": "truncated", "reached": False}
    packet = {"sha256": canonical_digest(row), "row": row}
    committed = json.dumps(packet).encode() + b"\n"
    path.write_bytes(committed + b'{"sha256":')
    rows, size = neo_domain.load_records(path)
    assert rows == {("a", "b"): row} and size == len(committed)
    packet["row"]["status"] = "success"
    path.write_text(json.dumps(packet) + "\n")
    with pytest.raises(ValueError, match="integrity"):
        neo_domain.load_records(path)


def test_policy_preparation_preserves_facts_without_full_graph_copy(graph, monkeypatch):
    graph = survey_graph(graph)
    profile = replace(NEO_STANDARD_PROFILE, bound_snapshot_id=graph.metadata["snapshot_id"])
    query = {
        "initial_actor": ACTOR,
        "initial_state": {"control": [ACTOR], "usable_identity": [[ACTOR, DC]]},
        "target": GROUP,
        "authentication_context": DC,
        "target_goal": {"target": GROUP, "kind": "usable_identity_entitlement"},
    }
    from src.engine.semantics.scenario_policy import apply_policy_to_query

    expected = apply_policy_to_query(query, graph.to_canonical(), profile)
    monkeypatch.setattr(graph, "to_canonical", lambda: pytest.fail("full graph copy"))
    actual = apply_policy_to_query(query, graph, profile)
    assert actual == expected
    assert run_attack_query(materialize_query(actual, graph), graph).paths
