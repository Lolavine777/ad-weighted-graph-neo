"""Guided exploration uses real semantics, immutable scope and explicit prefixes."""

import copy
import json
from pathlib import Path

import pytest

from src.engine import EngineGraph, materialize_query, run_attack_query
from src.engine.exploration import (
    build_scenario_template,
    inspect_structural_edge,
    inspect_transition,
    query_with_proposals,
    scenario_proposals,
    structural_exploration,
)
from src.engine.semantics.transitions import TransitionRequest

ROOT = Path(__file__).resolve().parents[1]


def inputs():
    folder = ROOT / "tests/fixtures/asrep"
    graph = EngineGraph.from_snapshot((folder / "snapshot.json").read_text())
    assumed = json.loads((folder / "query.json").read_text())
    raw = {**assumed, "assumptions": [], "evaluation_mode": "evidence_only"}
    return graph, raw, assumed


def request(query, technique, *, actor=None, source=None, target=None):
    actor = actor or query["initial_actor"]
    victim = query["initial_state"]["known_identity"][0]
    return TransitionRequest(technique, actor, source or actor, target or victim)


def test_structural_routes_survive_zero_semantic_candidates_and_preserve_limits():
    graph, raw, _ = inputs()
    victim = raw["initial_state"]["known_identity"][0]
    query = {**raw, "initial_actor": victim, "source_foothold": victim}
    before = graph.to_canonical()
    result = run_attack_query(materialize_query(query, graph), graph)
    assert not result.paths
    structural = structural_exploration(query, graph)
    assert structural["paths"]
    assert structural["paths"][0]["nodes"][0] == victim
    assert structural["paths"][0]["nodes"][-1] == query["target"]
    assert structural["kind"] == "structural_only"
    assert graph.to_canonical() == before
    limited = {**query, "budget": {"max_paths": 10, "max_steps": 1, "max_expansions": 1}}
    capped = structural_exploration(limited, graph)
    assert capped["truncated"] and not capped["complete"]
    assert capped["expansions"] <= 1


def test_unknown_probe_does_not_grant_effects_or_probe_an_unreached_suffix():
    graph, raw, _ = inputs()
    first = request(raw, "asrep_request")
    probe = inspect_transition(raw, graph, first)
    action = probe["options"][0]
    assert action["status"] == "indeterminate"
    assert "asrep_request_accepted" in action["unknown"]
    assert action["before"] == action["after"]
    blocked = inspect_transition(raw, graph, request(raw, "recover_asrep_secret"), prefix=[first])
    assert blocked["prefix_status"] == "indeterminate"
    assert not blocked["options"]
    assert len(blocked["prefix"]) == 1


def test_explicit_applicable_prefix_unlocks_real_recovery_diagnostics():
    graph, raw, assumed = inputs()
    accepted_request = [
        f
        for f in assumed["assumptions"]
        if f["subject"] == raw["initial_actor"]
        and f["predicate"] in {"network_kdc_reachable", "asrep_request_accepted"}
    ]
    query = {**raw, "evaluation_mode": "scenario", "assumptions": accepted_request}
    probe = inspect_transition(
        query,
        graph,
        request(query, "recover_asrep_secret"),
        prefix=[request(query, "asrep_request")],
    )
    assert probe["prefix_status"] == "applicable"
    assert probe["prefix"][0]["after"]["asrep_material"]
    assert "recovery_success" in probe["options"][0]["unknown"]
    assert not probe["options"][0]["after"]["recovered_secret"]


def test_catalog_edge_options_are_at_exact_state_and_do_not_infer_asrep():
    graph, raw, _ = inputs()
    edge = next(e for e in graph.edges() if e["kind"] == "MemberOf")
    probe = inspect_structural_edge(raw, graph, edge["id"])
    assert probe["edge"]["id"] == edge["id"]
    assert probe["catalog_support"] == "direct_options"
    assert probe["options"]
    assert all(o["technique"]["relationship"] == "MemberOf" for o in probe["options"])
    assert all(o["request"]["technique_id"] != "asrep_request" for o in probe["options"])
    # No recovered identity/effective membership is fabricated for later edges.
    assert not probe["state"]["usable_identity"]
    assert any(o["failed"] for o in probe["options"])


def test_probe_budget_blocks_replay_without_any_evaluation():
    graph, raw, _ = inputs()
    query = {**raw, "budget": {"max_paths": 1, "max_steps": 1, "max_expansions": 1}}
    probe = inspect_transition(
        query,
        graph,
        request(query, "recover_asrep_secret"),
        prefix=[request(query, "asrep_request")],
    )
    assert probe["truncated"]
    assert probe["prefix_status"] == "not_evaluated"
    assert not probe["prefix"] and not probe["options"]


def test_genericall_lists_multiple_catalog_choices_without_selecting_asrep():
    graph = EngineGraph.from_canonical(
        (ROOT / "tests/fixtures/attack_scenarios/graphs/genericall-user.json").read_text()
    )
    edge = graph.edges()[0]
    query = {
        "source_foothold": edge["source"],
        "target": edge["target"],
        "target_goal": {
            "target": edge["target"],
            "required_state": {"reset_password_control": [edge["target"]]},
        },
        "initial_state": {"control": [edge["source"]]},
        "budget": {"max_paths": 10, "max_steps": 9, "max_expansions": 100},
    }
    before = graph.to_canonical()
    probe = inspect_structural_edge(query, graph, edge["id"])
    ids = {o["request"]["technique_id"] for o in probe["options"]}
    assert "genericall_reset_password" in ids
    assert "asrep_request" not in ids
    assert len(ids) > 1
    assert graph.to_canonical() == before


def test_template_selection_reruns_real_engine_and_retains_query_scope():
    graph, raw, assumed = inputs()
    before = copy.deepcopy(raw)
    template = build_scenario_template(raw, graph, assumed["assumptions"], template_id="asrep")
    choices = scenario_proposals(template, raw, graph)
    assert choices["kind"] == "scoped_template"
    assert all(not p["selected"] for p in choices["proposals"])
    empty = query_with_proposals(template, raw, graph, [])
    assert not run_attack_query(materialize_query(empty, graph), graph).final_goal_reached
    ids = [p["proposal_id"] for p in choices["proposals"]]
    updated = query_with_proposals(template, raw, graph, list(reversed(ids)))
    assert updated["assumptions"] == assumed["assumptions"]
    assert run_attack_query(materialize_query(updated, graph), graph).final_goal_reached
    assert {k: v for k, v in updated.items() if k not in {"assumptions", "evaluation_mode"}} == {
        k: v for k, v in raw.items() if k not in {"assumptions", "evaluation_mode"}
    }
    assert raw == before
    recovery_ids = [
        p["proposal_id"]
        for p in choices["proposals"]
        if p["assumption"]["predicate"] != "recovery_success"
    ]
    incomplete = query_with_proposals(template, raw, graph, recovery_ids)
    assert not run_attack_query(materialize_query(incomplete, graph), graph).final_goal_reached
    for invalid in (["unknown"], [ids[0], ids[0]]):
        with pytest.raises(ValueError, match="unique proposal IDs"):
            query_with_proposals(template, raw, graph, invalid)


@pytest.mark.parametrize(
    "field",
    [
        "source_foothold",
        "initial_actor",
        "target",
        "authentication_context",
        "budget",
        "initial_state",
    ],
)
def test_template_rejects_changed_query_scope(field):
    graph, raw, assumed = inputs()
    template = build_scenario_template(raw, graph, assumed["assumptions"], template_id="asrep")
    changed = copy.deepcopy(raw)
    changed[field] = "changed"
    with pytest.raises(ValueError, match="exact graph/query scope"):
        scenario_proposals(template, changed, graph)


def test_template_rejects_changed_snapshot_facts_even_with_same_topology():
    graph, raw, assumed = inputs()
    template = build_scenario_template(raw, graph, assumed["assumptions"], template_id="asrep")
    no_static_facts = EngineGraph.from_canonical(graph.to_canonical())
    with pytest.raises(ValueError, match="exact graph/query scope"):
        scenario_proposals(template, raw, no_static_facts)


def test_authoritative_false_veto_is_retained_in_proposals_and_rerun():
    graph, raw, assumed = inputs()
    fact = next(f for f in assumed["assumptions"] if f["predicate"] == "asrep_request_accepted")
    raw = {
        **raw,
        "runtime_facts": [{**fact, "value": False, "origin": "blocked_evidence"}],
    }
    template = build_scenario_template(raw, graph, assumed["assumptions"], template_id="veto")
    choices = scenario_proposals(template, raw, graph)
    assert any(r["reason"] == "known_false_veto" for r in choices["rejected_assumptions"])
    updated = query_with_proposals(
        template, raw, graph, [p["proposal_id"] for p in choices["proposals"]]
    )
    probe = inspect_transition(updated, graph, request(updated, "asrep_request"))
    assert probe["rejected_assumptions"]
    assert probe["options"][0]["status"] == "blocked"
    assert not probe["options"][0]["after"]["asrep_material"]
