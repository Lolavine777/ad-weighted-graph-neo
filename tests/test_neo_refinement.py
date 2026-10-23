"""Guided seed preservation, strict C improvement and a single shared budget."""

import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest
from test_neo_host_session import scenario

from scripts.neo_minimum_probe import (
    ACTOR,
    CASE_NAMES,
    GOAL,
    OWNER,
    edge,
    evaluate,
    fixture,
    oracle,
)
from src.engine.graph import EngineGraph
from src.engine.query import run_attack_query
from src.engine.query_cli import execute
from src.engine.ranking.effort_profiles import bind_effort_profile, load_effort_profile
from src.engine.ranking.resolution_service import canonical_digest
from src.engine.semantics.credentials import replay_path
from src.engine.semantics.transitions import Status


def bound(graph, query):
    return bind_effort_profile(query, graph, load_effort_profile("neo-c-v1"))


@pytest.mark.parametrize("name", CASE_NAMES)
def test_refinement_improves_or_keeps_the_feasible_seed_without_changing_gates(name):
    result = evaluate(name, "neo_refine", max_paths=1)
    assert result["C"] == oracle(name)["certain_minimum_C"]
    assert result["reached"] and not result["minimum_proven"]
    assert not result["rating_exclusions"]
    assert bool(result["unknown_attempts"]) == (name == "reset_auth_unknown")


@pytest.mark.parametrize("name", CASE_NAMES)
def test_exhaustive_seed_is_reused_with_identical_programs_costs_and_guarantees(name):
    guided = evaluate(name, "neo_guided")
    result = evaluate(name, "neo_refine")
    for field in ("C", "program_set_sha256", "expansions", "minimum_proven", "unknown_attempts"):
        assert result[field] == guided[field]


@pytest.mark.parametrize("budget", [1, 2, 3, 4, 8, 14, 15, 30])
def test_refinement_never_loses_a_seed_or_allocates_more_expansions(budget):
    guided = evaluate("two_routes", "neo_guided", max_paths=1, max_expansions=budget)
    result = evaluate("two_routes", "neo_refine", max_paths=1, max_expansions=budget)
    assert result["expansions"] <= budget
    if guided["reached"]:
        assert result["reached"] and result["C"] <= guided["C"]
    else:
        assert result["C"] is None
    if budget == 3:
        assert result["C"] == 3 and result["expansions"] == guided["expansions"]


@pytest.mark.parametrize(
    "lateral,mutate,C", [(False, False, 2), (True, False, 3), (False, True, 3)]
)
def test_host_session_witnesses_remain_C_rated_and_replayable(lateral, mutate, C):
    graph, query = scenario(lateral=lateral, mutate=mutate)
    guided = run_attack_query(query, graph)
    result = run_attack_query({**query, "search_order": "neo_refine"}, graph)
    assert result.status == "success" and result.final_goal_reached
    assert result.min_effort["minimum_effort_value"] == C
    assert result.expansions <= query["budget"]["max_expansions"]
    assert result.min_effort["minimum_effort_value"] <= guided.min_effort["minimum_effort_value"]
    for path in result.paths:
        assert replay_path(path, graph) == path.final_state


def test_zero_action_success_needs_no_refinement_or_extra_attempts():
    graph, query = fixture("two_routes")
    query["initial_state"]["effective_member"] = [[ACTOR, GOAL]]
    query["search_order"] = "neo_refine"
    result = run_attack_query(bound(graph, query), graph)
    assert result.expansions == 0 and not result.attempts
    assert result.min_effort["minimum_effort_value"] == 0 and result.complete


def test_multiple_strict_improvements_do_not_stop_at_the_first_cheaper_path():
    graph, query = fixture("two_routes")
    middle = "S-1-5-21-1000-2000-3000-1103"
    raw = graph.to_canonical()
    raw["nodes"].append({**copy.deepcopy(graph.node(OWNER)), "id": middle, "label": "Middle"})
    raw["edges"].extend([edge(ACTOR, middle, "GenericAll"), edge(middle, OWNER, "GenericAll")])
    raw["metadata"]["snapshot_id"] = canonical_digest([raw["nodes"], raw["edges"]])
    graph = EngineGraph.from_canonical(raw)
    for fact in list(query["assumptions"]):
        if fact["subject"] == OWNER:
            query["assumptions"].append({**fact, "subject": middle})
        if fact["target"] == OWNER:
            query["assumptions"].append({**fact, "target": middle})
        if fact["subject"] == OWNER and fact["target"] == OWNER:
            query["assumptions"].append({**fact, "subject": middle, "target": middle})
    query["budget"].update(max_paths=1, max_expansions=300)
    guided = run_attack_query(bound(graph, query), graph)
    result = run_attack_query(bound(graph, {**query, "search_order": "neo_refine"}), graph)
    assert guided.min_effort["minimum_effort_value"] == 3
    assert result.min_effort["minimum_effort_value"] == 1
    terminal = [
        a
        for a in result.attempts
        if a.status == Status.APPLICABLE and (OWNER, GOAL) in a.additions.effective_member
    ]
    assert any(middle in {u for u, _ in a.before.usable_identity} for a in terminal)
    assert any(middle not in {u for u, _ in a.before.usable_identity} for a in terminal)
    assert result.expansions <= 300
    assert replay_path(result.best_path, graph) == result.best_path.final_state


@pytest.mark.parametrize("change", ["missing", "cost", "preparation"])
def test_refinement_refuses_to_guess_costs_from_modified_or_missing_rules(change):
    graph, query = fixture("two_routes")
    query = bound(graph, query)
    query["search_order"] = "neo_refine"
    if change == "missing":
        del query["rating_resolution"]
    elif change == "cost":
        registry = query["rating_resolution"]["registries"]["effort"]
        registry["data"][0]["computed_cost"] = 0
        registry["sha256"] = canonical_digest(registry["data"])
    else:
        query["rating_resolution"]["registries"]["work"] = {"data": []}
    with pytest.raises(ValueError, match="unchanged bound neo-c-v1"):
        run_attack_query(query, graph)


def test_cli_representation_marks_guided_refinement_as_best_found_under_cap():
    graph, query = fixture("two_routes")
    query.update(search_order="neo_refine")
    query["budget"]["max_paths"] = 1
    package = execute(bound(graph, query), graph)
    assert package["min_effort"]["minimum_effort_value"] == 1
    assert package["materialized"]["search_strategy"]["version"] == "neo-guided-c-improvement/1"
    assert not package["materialized"]["search_strategy"]["priority_is_cost_lower_bound"]


def test_real_cli_override_runs_the_same_refinement_and_public_rating(tmp_path):
    graph, query = fixture("two_routes")
    query["budget"]["max_paths"] = 1
    query_path, graph_path = tmp_path / "query.json", tmp_path / "graph.json"
    query_path.write_text(json.dumps(bound(graph, query)))
    graph_path.write_text(json.dumps(graph.to_canonical()))
    output = subprocess.check_output(
        [
            sys.executable,
            "-m",
            "src.engine",
            "query",
            "--query",
            str(query_path),
            "--graph",
            str(graph_path),
            "--label",
            "synthetic",
            "--search-order",
            "neo_refine",
        ],
        cwd=Path(__file__).resolve().parents[1],
        text=True,
    )
    package = json.loads(output)["semantic"]
    assert package["final_goal_reached"] and package["min_effort"]["minimum_effort_value"] == 1
    assert package["materialized"]["search_strategy"]["effective"] == "neo_refine"
