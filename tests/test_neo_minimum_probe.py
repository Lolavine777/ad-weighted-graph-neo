"""Independent route costs expose capped search without changing planner semantics."""

import pytest

from scripts.neo_minimum_probe import CASE_NAMES, run


@pytest.fixture(scope="module")
def experiment():
    return run()


def row(experiment, name, strategy, cap=1000):
    return next(
        r
        for r in experiment["rows"]
        if r["case"] == name
        and r["strategy"] == strategy
        and r["budget"] == {"max_paths": cap, "max_steps": 12, "max_expansions": 20000}
    )


@pytest.mark.parametrize("strategy", ["fifo", "neo_guided"])
def test_shorter_expensive_route_can_hide_a_cheaper_longer_route(experiment, strategy):
    first = row(experiment, "two_routes", strategy, 1)
    complete = row(experiment, "two_routes", strategy)
    assert first["C"] == 3 and first["first_C"] == 3
    assert first["best_steps"] == [
        "grant_new_object_right",
        "genericall_add_member",
        "propagate_group_entitlement",
    ]
    assert complete["C"] == 1 and complete["first_C"] == 3
    assert complete["best_steps"] == [
        "propagate_group_entitlement",
        "propagate_group_entitlement",
        "scenario_reset_password",
        "acquire_reset_identity",
        "propagate_group_entitlement",
    ]
    assert not first["minimum_proven"] and complete["minimum_proven"]


@pytest.mark.parametrize(
    "name,expected,proven",
    [
        ("two_routes", 1, True),
        ("reset_auth_false", 3, True),
        ("reset_auth_unknown", 3, False),
        ("free_membership", 0, True),
    ],
)
def test_finite_native_minimum_matches_independent_work_recipes(experiment, name, expected, proven):
    fifo = row(experiment, name, "fifo")
    guided = row(experiment, name, "neo_guided")
    assert fifo["program_set_sha256"] == guided["program_set_sha256"]
    for result in (fifo, guided):
        assert result["C"] == expected
        assert result["minimum_proven"] is proven
        assert not result["truncated"] and not result["rating_exclusions"]
        assert result["reference_routes_with_native_replay"]["certain"] >= 1
        assert bool(result["unknown_attempts"]) is (name == "reset_auth_unknown")


@pytest.mark.parametrize("name", CASE_NAMES)
def test_conditioned_dijkstra_is_valid_only_after_accounting_for_the_gate(experiment, name):
    reference = experiment["references"][name]
    oracle = experiment["oracles"][name]
    assert reference["certain"]["C"] == oracle["certain_minimum_C"]
    assert reference["possible"]["C"] == oracle["possible_minimum_C"]
    assert reference["minimum_provable"] == oracle["minimum_provable"]
    if name == "reset_auth_unknown":
        result = row(experiment, name, "neo_guided")
        assert result["reference_routes_with_native_replay"]["possible"] == 0
        assert reference["possible"]["C"] == 1 < result["C"]


def test_hop_minimum_and_effort_minimum_are_distinct_on_the_same_fixture(experiment):
    reference = experiment["references"]["two_routes"]["certain"]
    assert reference["hop_only"] == {"graph_hops": 1, "mapped_C": 3}
    assert reference["graph_hops"] == 4 and reference["C"] == 1


def test_step_and_expansion_caps_do_not_claim_minimum(experiment):
    capped = [
        r
        for r in experiment["rows"]
        if r["budget"]["max_steps"] == 3 or r["budget"]["max_expansions"] == 1
    ]
    assert len(capped) == 2
    assert all(r["truncated"] and not r["minimum_proven"] for r in capped)
    assert {r["truncation_reason"] for r in capped} == {
        "step_limit_reached",
        "expansion_limit_reached",
    }
