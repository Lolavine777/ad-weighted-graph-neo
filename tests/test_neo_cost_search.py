"""Cost order must agree with finite oracles, native gates and final public C."""

import pytest
from test_neo_host_session import scenario

from scripts.neo_minimum_probe import CASE_NAMES, evaluate, fixture, oracle
from src.engine.query import run_attack_query
from src.engine.query_cli import execute
from src.engine.ranking.effort_profiles import bind_effort_profile, load_effort_profile
from src.engine.ranking.resolution_service import canonical_digest
from src.engine.semantics.credentials import replay_path
from src.engine.top_k import effort_programs


@pytest.mark.parametrize("name", CASE_NAMES)
def test_first_cost_witness_matches_oracle_and_exhaustive_program_set(name):
    first = evaluate(name, "neo_cost", max_paths=1)
    full = evaluate(name, "neo_cost")
    fifo = evaluate(name, "fifo")
    expected = oracle(name)
    assert first["first_C"] == expected["certain_minimum_C"] == full["C"]
    assert not first["minimum_proven"]
    assert full["program_set_sha256"] == fifo["program_set_sha256"]
    assert full["minimum_proven"] == expected["minimum_provable"]
    assert full["expansions"] == fifo["expansions"]
    assert bool(full["unknown_attempts"]) == (name == "reset_auth_unknown")


def test_goals_are_popped_in_cost_order_instead_of_returned_on_generation():
    graph, query = fixture("two_routes")
    query["search_order"] = "neo_cost"
    bound = bind_effort_profile(query, graph, load_effort_profile("neo-c-v1"))
    result = run_attack_query(bound, graph)
    programs, exclusions = effort_programs(result)
    costs = {p["candidate_id"]: p["effort"] for p in programs}
    discovery = [costs[f"generated_{i:04d}"] for i in range(1, len(result.paths) + 1)]
    assert not exclusions and discovery == sorted(discovery)
    assert discovery[0] == 1 and 3 in discovery
    assert execute(bound, graph)["materialized"]["search_strategy"] == {
        "requested": "neo_cost",
        "effective": "neo_cost",
        "version": "neo-cost-work-union/1",
        "fallback_reason": None,
        "priority_is_cost_lower_bound": True,
    }


@pytest.mark.parametrize("expansions", [1, 4, 5])
def test_budget_still_applies_and_preserves_goal_generated_on_last_attempt(expansions):
    result = evaluate("two_routes", "neo_cost", max_paths=1, max_expansions=expansions)
    assert result["expansions"] <= expansions
    assert result["truncated"] and not result["minimum_proven"]
    assert result["C"] == (1 if expansions == 5 else None)


@pytest.mark.parametrize(
    "lateral,mutate,C", [(False, False, 2), (True, False, 3), (False, True, 3)]
)
def test_host_session_cost_uses_same_native_transitions(lateral, mutate, C):
    graph, query = scenario(lateral=lateral, mutate=mutate)
    result = run_attack_query({**query, "search_order": "neo_cost"}, graph)
    assert result.final_goal_reached and result.min_effort["minimum_effort_value"] == C
    for path in result.paths:
        assert replay_path(path, graph) == path.final_state


@pytest.mark.parametrize("change", ["missing", "cost", "preparation"])
def test_cost_order_refuses_unbound_or_modified_rating_rules(change):
    graph, query = fixture("two_routes")
    query = bind_effort_profile(query, graph, load_effort_profile("neo-c-v1"))
    query["search_order"] = "neo_cost"
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
