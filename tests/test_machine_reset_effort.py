"""Same reset operation price, explicit machine identity and independent work sets."""

import copy

import pytest
from test_computer_foothold_boundary import CASES, OTHER_USER, TECHNIQUES
from test_engine import ACTOR, GROUP, HOST, _edge
from test_machine_identity_profile import request, scenario

from src.engine.batch import BatchExecutionBudget, run_source_goal_batch
from src.engine.query import run_attack_query
from src.engine.query_cli import wire
from src.engine.ranking.reset_effort import (
    MACHINE_PROFILE_ID,
    PROFILE_ID,
    bind_reset_effort,
    load_reset_effort_profile,
)
from src.engine.semantics.credentials import replay_path


@pytest.mark.parametrize(
    "case", [c for c in CASES if c.name != "missing_context"], ids=lambda c: c.name
)
def test_machine_C_never_changes_capabilities_or_reachability(case):
    graph, query = scenario(case)
    before = run_attack_query(query, graph)
    bound = bind_reset_effort(query, graph, load_reset_effort_profile(MACHINE_PROFILE_ID))
    after = run_attack_query(bound, graph)
    assert wire(before.paths) == wire(after.paths)
    assert before.status == after.status and before.expansions == after.expansions
    assert bound["initial_state"] == query["initial_state"]
    if case.name == "explicit_machine_identity":
        assert after.min_effort["minimum_effort_value"] == 1
        assert bound["effort_profile_metadata"]["status"] == "bound"
    elif case.name == "explicit_user_switch":
        # The initial actor's price cannot silently cover a different controller.
        assert after.paths and after.min_effort is None
        assert bound["effort_profile_metadata"]["status"] == "not_applicable"
    else:
        assert not after.paths
        assert after.min_effort is None or after.min_effort["minimum_effort_value"] is None
    for path in after.paths:
        assert replay_path(path, graph) == path.final_state


def test_v1_keeps_its_original_machine_refusal_and_v2_reuses_prices():
    graph, query = scenario(CASES[2])
    old = load_reset_effort_profile(PROFILE_ID)
    new = load_reset_effort_profile(MACHINE_PROFILE_ID)
    assert old["classes"] == new["classes"] and old["sources"] == new["sources"]
    assert old["profile_id"] != new["profile_id"]
    compiled = bind_reset_effort(query, graph, old)
    assert compiled["effort_profile_metadata"]["status"] == "not_applicable"
    assert run_attack_query(compiled, graph).min_effort is None


def two_owner_inputs():
    graph, query = scenario(CASES[2])
    raw = graph.to_canonical()
    raw["edges"] += [_edge(HOST, OTHER_USER, "GenericAll"), _edge(OTHER_USER, GROUP, "MemberOf")]
    graph = type(graph).from_canonical(raw)
    query["assumptions"] += [
        {
            **f,
            "subject": OTHER_USER if f["subject"] == ACTOR else f["subject"],
            "target": OTHER_USER if f["target"] == ACTOR else f["target"],
        }
        for f in list(query["assumptions"])
        if ACTOR in (f["subject"], f["target"])
    ]
    query["budget"] = {"max_paths": 1000, "max_steps": 6, "max_expansions": 10000}
    return graph, query


def test_two_acquired_owners_use_independent_union_work_not_hop_count():
    graph, query = two_owner_inputs()
    result = run_attack_query(
        bind_reset_effort(query, graph, load_reset_effort_profile(MACHINE_PROFILE_ID)), graph
    )
    costs = set()
    for i, path in enumerate(result.paths, 1):
        resets, activations = set(), set()
        for step in path.transition_history:
            r = step.result.request
            if r.technique_id == "scenario_reset_password":
                assert r.actor == r.source == HOST
                resets.add((HOST, r.target, HOST))
            elif r.technique_id == "acquire_reset_identity":
                assert (HOST, r.actor, HOST) in resets and r.target == HOST
                activations.add((r.actor, HOST))
            elif r.technique_id == "propagate_group_entitlement":
                assert (r.actor, HOST) in activations
            else:
                raise AssertionError("No oracle price for this operation")
        expected = len(resets)
        native = result.rating_coverage["candidates"][f"generated_{i:04d}"]
        assert sum(u["cost"] for u in native["effort"]["units"].values()) == expected
        assert len(native["effort"]["units"]) == len(resets) + len(activations)
        summary = result.rating_coverage["candidate_summaries"][f"generated_{i:04d}"]
        assert summary["c_complete"] and not summary["p_complete"] and not summary["i_complete"]
        costs.add(expected)
        replay_path(path, graph)
    assert costs == {1, 2}


@pytest.mark.parametrize("worker", [False, True])
def test_machine_C_survives_batch_worker_resume_and_refuses_another_profile(tmp_path, worker):
    graph, query = scenario(CASES[2])
    req = request(graph, query)
    checkpoint = tmp_path / "C.json"
    options = {
        "allowed_techniques": TECHNIQUES,
        "effort_profile": MACHINE_PROFILE_ID,
        "checkpoint": checkpoint,
        "execution_budget": BatchExecutionBudget(per_query_seconds=10) if worker else None,
    }
    result = run_source_goal_batch(req, graph, **options)
    assert result.summary["effort_rated_cells"] == result.summary["successful_cells"] == 1
    assert result.summary["likelihood_rated_cells"] == 0
    resumed = run_source_goal_batch(req, graph, resume=True, **options)
    assert resumed.source_goal_matrix == result.source_goal_matrix
    assert resumed.reproducibility["runtime"]["reused_cells"] == 1
    with pytest.raises(ValueError, match="CHECKPOINT_SCOPE_MISMATCH"):
        run_source_goal_batch(req, graph, resume=True, **{**options, "effort_profile": PROFILE_ID})


def test_machine_C_records_keep_exact_context_owner_and_profile_authority():
    graph, query = scenario(CASES[2])
    profile = load_reset_effort_profile(MACHINE_PROFILE_ID)
    altered = copy.deepcopy(profile)
    altered["classes"]["scenario_reset_password"]["cost"] = 0
    with pytest.raises(ValueError, match="definition changed"):
        bind_reset_effort(query, graph, altered)
    compiled = bind_reset_effort(query, graph, profile)
    for record in compiled["rating_resolution"]["registries"]["effort"]["data"]:
        assert record["applicability"]["required_auth_context"] == HOST
        assert record["class_id"].startswith(MACHINE_PROFILE_ID + ":")
    assert compiled["rating_resolution"]["scope"]["policy_id"] == MACHINE_PROFILE_ID
