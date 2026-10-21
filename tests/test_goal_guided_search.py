"""Same finite programs and independent union-C oracle; scheduling is not scoring."""

import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest
from test_computer_foothold_boundary import CASES, TECHNIQUES
from test_machine_identity_profile import request, scenario
from test_machine_reset_effort import two_owner_inputs

from src.engine.batch import BatchExecutionBudget, run_source_goal_batch
from src.engine.program_identity import program_key
from src.engine.query import materialize_query, run_attack_query
from src.engine.query_cli import execute
from src.engine.ranking.reset_effort import bind_reset_effort, load_reset_effort_profile
from src.engine.remediation import prepare_baseline, replay_baseline
from src.engine.remediation_runner import inventory_interventions, requests_from_inventory
from src.engine.semantics.credentials import replay_path

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("cap", [1000, 1])
@pytest.mark.parametrize("search_order", ["goal_guided", "neo_guided"])
def test_two_owner_programs_c_actor_switch_and_native_replay(cap, search_order):
    graph, query = two_owner_inputs()
    query["budget"]["max_paths"] = cap
    query = bind_reset_effort(query, graph, load_reset_effort_profile("reset-activation-c-v2"))
    fifo = run_attack_query(query, graph)
    guided = run_attack_query({**query, "search_order": search_order}, graph)
    assert guided.final_goal_reached and guided.min_effort["minimum_effort_value"] == 1
    if cap == 1000:
        assert not fifo.truncated and not guided.truncated
        assert {program_key(p) for p in fifo.paths} == {program_key(p) for p in guided.paths}
        assert len(guided.paths) == len(fifo.paths)
    else:
        assert guided.truncated and not guided.is_minimum_proven_over_scope
    costs = set()
    for i, path in enumerate(guided.paths, 1):
        resets = {
            (s.result.request.actor, s.result.request.target)
            for s in path.transition_history
            if s.result.request.technique_id == "scenario_reset_password"
        }
        native = guided.rating_coverage["candidates"][f"generated_{i:04d}"]
        assert sum(u["cost"] for u in native["effort"]["units"].values()) == len(resets)
        costs.add(len(resets))
        assert replay_path(path, graph) == path.final_state
    assert costs == ({1, 2} if cap == 1000 else {1})
    assert (
        execute({**query, "search_order": search_order}, graph)["materialized"]["search_strategy"][
            "effective"
        ]
        == search_order
    )


@pytest.mark.parametrize(
    "case", [c for c in CASES if c.name != "missing_context"], ids=lambda c: c.name
)
@pytest.mark.parametrize("search_order", ["goal_guided", "neo_guided"])
def test_guidance_keeps_false_unknown_identity_and_context_boundaries(case, search_order):
    graph, query = scenario(case)
    fifo = run_attack_query(query, graph)
    guided = run_attack_query({**query, "search_order": search_order}, graph)
    assert guided.status == fifo.status
    assert {program_key(p) for p in guided.paths} == {program_key(p) for p in fifo.paths}
    assert (
        guided.materialized_query.initial_attack_state
        == fifo.materialized_query.initial_attack_state
    )


@pytest.mark.parametrize("order", [None, True, "astar", {}, []])
def test_invalid_search_order_rejected_at_public_boundary(order):
    graph, query = scenario(CASES[2])
    with pytest.raises(ValueError, match="search_order"):
        materialize_query({**query, "search_order": order}, graph)


def test_unsupported_catalog_and_goal_use_explicit_fifo_fallback():
    graph, query = scenario(CASES[2])
    query.pop("allowed_techniques")
    material = materialize_query({**query, "search_order": "goal_guided"}, graph)
    assert material.search_strategy["effective"] == "fifo"
    assert material.search_strategy["fallback_reason"] == "unsupported_goal_or_catalog"
    query["allowed_techniques"] = TECHNIQUES
    query["target_goal"] = {
        "target": query["target"],
        "required_state": {"control": [query["target"]]},
    }
    assert (
        materialize_query({**query, "search_order": "goal_guided"}, graph).search_strategy[
            "effective"
        ]
        == "fifo"
    )


@pytest.mark.parametrize("worker", [False, True])
@pytest.mark.parametrize("search_order", ["goal_guided", "neo_guided"])
def test_order_bound_to_cells_checkpoint_worker_and_progress_is_isolated(
    tmp_path, worker, search_order
):
    graph, query = scenario(CASES[2])
    req = request(graph, query)
    events = []

    def record(event):
        events.append(copy.deepcopy(event))
        event["witness"]["steps"].clear()
        event["search_strategy"]["effective"] = "forged"

    opts = dict(
        allowed_techniques=TECHNIQUES,
        effort_profile="reset-activation-c-v2",
        checkpoint=tmp_path / "checkpoint.json",
        execution_budget=BatchExecutionBudget(per_query_seconds=10) if worker else None,
    )
    first = run_source_goal_batch(req, graph, search_order=search_order, on_cell=record, **opts)
    assert len(events) == 1 and events[0]["C"] == 1
    trace = next(iter(first.reproducibility["inputs"]["public_queries"].values()))
    assert trace["query"]["search_order"] == search_order
    assert trace["materialized"]["search_strategy"]["effective"] == search_order
    resumed = run_source_goal_batch(req, graph, search_order=search_order, resume=True, **opts)
    assert resumed.source_goal_matrix == first.source_goal_matrix
    with pytest.raises(ValueError, match="CHECKPOINT_SCOPE_MISMATCH"):
        run_source_goal_batch(req, graph, search_order="fifo", resume=True, **opts)


@pytest.mark.parametrize("search_order", ["goal_guided", "neo_guided"])
def test_remediation_scope_binds_search_order(search_order):
    graph, query = scenario(CASES[2])
    cell = {
        "source_id": "source",
        "goal_id": "goal",
        "query": {**query, "search_order": search_order},
    }
    baseline = prepare_baseline(graph, [cell], run_id="guided")
    inventory = inventory_interventions(graph, baseline)
    intervention = requests_from_inventory(baseline, inventory, limit=1)[0]
    replay = replay_baseline(intervention, graph, baseline)
    assert replay
    forged = copy.deepcopy(cell)
    forged["query"]["search_order"] = "fifo"
    forged_baseline = prepare_baseline(graph, [forged], run_id="guided")
    assert baseline.scope["query_profile_digest"] != forged_baseline.scope["query_profile_digest"]
    with pytest.raises(ValueError, match="baseline|scope|query"):
        replay_baseline(intervention, graph, forged_baseline)


@pytest.mark.parametrize("search_order", ["goal_guided", "neo_guided"])
def test_cli_guided_progress_and_refused_resume_preserve_prior_output(tmp_path, search_order):
    graph, query = scenario(CASES[2])
    graph_path = tmp_path / "graph.json"
    graph_path.write_text(json.dumps(graph.to_canonical()))
    assumptions = tmp_path / "assumptions.json"
    assumptions.write_text(json.dumps(query["assumptions"]))
    source = query["initial_actor"]
    out = tmp_path / "run"
    command = [
        sys.executable,
        "-m",
        "scripts.exposure",
        "--graph",
        str(graph_path),
        "--source",
        source,
        "--authentication-context",
        source,
        "--computer-profile",
        "computer_usable_identity",
        "--machine-identity-provenance",
        "synthetic://queue",
        "--evaluation-mode",
        "scenario",
        "--assumptions",
        str(assumptions),
        "--effort-profile",
        "reset-activation-c-v2",
        "--search-order",
        search_order,
        "--output-dir",
        str(out),
        "--max-paths",
        "1",
    ]
    for technique in TECHNIQUES:
        command += ["--technique", technique]
    subprocess.run(command, cwd=ROOT, capture_output=True, text=True, check=True)
    progress = out / "discovery-progress.jsonl"
    previous = progress.read_bytes()
    events = [json.loads(line) for line in previous.decode().splitlines()]
    assert any(e["reached"] and e["C"] == 1 and e["witness"]["steps"] for e in events)
    assert (out / "defender-brief.md").exists()
    changed = list(command)
    changed[changed.index(search_order)] = "fifo"
    refused = subprocess.run(changed + ["--resume"], cwd=ROOT, capture_output=True, text=True)
    assert refused.returncode == 2 and "CHECKPOINT_SCOPE_MISMATCH" in refused.stderr
    assert progress.read_bytes() == previous
