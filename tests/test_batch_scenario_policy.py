"""Exercise the discovery compiler boundary against finite, independent goals.

Expected: Alice is a member of DA and local admin on HOST; Bob has neither.
The standard policy may condition gates, never create the missing relationships,
usable credentials, actor control or a positive gate contradicted by evidence.
"""

import copy
import json
import subprocess
import sys
from dataclasses import replace

import pytest
from test_exposure import ACTOR, BOB, GROUP, HOST, ROOT, TECHNIQUES, by_node, request
from test_exposure import graph as graph

from scripts.exposure import evaluate_interventions
from src.engine.batch import BatchExecutionBudget, run_source_goal_batch
from src.engine.graph import EngineGraph
from src.engine.query import materialize_query, run_attack_query
from src.engine.remediation import prepare_baseline, replay_baseline, request_for_baseline
from src.engine.remediation_runner import inventory_interventions, requests_from_inventory
from src.engine.semantics.scenario_policy import (
    FORBIDDEN_PREDICATES,
    SEAMLESS_SNAPSHOT_ID,
    SEAMLESS_STANDARD_PROFILE,
)


@pytest.fixture
def policy_graph(graph):
    raw = graph.to_canonical()
    raw["metadata"]["snapshot_id"] = SEAMLESS_SNAPSHOT_ID
    return EngineGraph.from_canonical(raw)


def run(graph, *, scenario=True, **kwargs):
    req = request(graph, evaluation_mode="scenario" if scenario else "evidence_only")
    result = run_source_goal_batch(
        req,
        graph,
        allowed_techniques=TECHNIQUES,
        scenario_policy="seamless-standard-v1" if scenario else None,
        **kwargs,
    )
    return req, result


def test_policy_discovery_has_independent_expected_goals_and_replay(policy_graph):
    req, result = run(policy_graph)
    assert by_node(result, req) == {(ACTOR, GROUP), (ACTOR, HOST)}
    assert not any(source == BOB for source, _ in by_node(result, req))
    inputs = result.reproducibility["inputs"]
    assert inputs["scenario_policy"]["digest"] == SEAMLESS_STANDARD_PROFILE.digest()
    for trace in inputs["public_queries"].values():
        query = trace["query"]
        assert (
            query["scenario_policy_metadata"]["profile_digest"]
            == inputs["scenario_policy"]["digest"]
        )
        assert not ({a["predicate"] for a in query["assumptions"]} & FORBIDDEN_PREDICATES)
        assert all(a["provenance_reference"] and a["rationale"] for a in query["assumptions"])
        replay = run_attack_query(materialize_query(query, policy_graph), policy_graph)
        assert replay.final_goal_reached == trace["result"]["final_goal_reached"]
        assert not trace["guarantees"]["is_minimum_proven_over_scope"]
    evidence_req, evidence = run(policy_graph, scenario=False)
    assert not by_node(evidence, evidence_req)
    assert "scenario_policy" not in evidence.reproducibility["inputs"]
    assert all(
        not t["query"]["assumptions"]
        for t in evidence.reproducibility["inputs"]["public_queries"].values()
    )


def test_observed_false_vetoes_policy_and_remains_in_public_trace(policy_graph):
    false = {
        "predicate": "admin_channel",
        "subject": ACTOR,
        "target": HOST,
        "value": False,
        "origin": "observed_evidence",
    }
    req, result = run(policy_graph, runtime_facts=[false])
    assert by_node(result, req) == {(ACTOR, GROUP)}
    queries = result.reproducibility["inputs"]["public_queries"].values()
    assert all(t["query"]["runtime_facts"] == [false] for t in queries)
    assert any(
        r["predicate"] == "admin_channel" and r["subject"] == ACTOR and r["target"] == HOST
        for t in queries
        for r in t["query"]["scenario_policy_metadata"]["rejected_assumptions"]
    )
    assert all(
        not any(
            a["predicate"] == "admin_channel" and a["subject"] == ACTOR and a["target"] == HOST
            for a in t["query"]["assumptions"]
        )
        for t in queries
    )


def test_profile_never_turns_leaked_material_into_identity(policy_graph):
    req = request(policy_graph, source_ids=[ACTOR], evaluation_mode="scenario")
    req["sources"][0]["profile_kind"] = "user_leaked_password"
    result = run_source_goal_batch(
        req, policy_graph, allowed_techniques=TECHNIQUES, scenario_policy="seamless-standard-v1"
    )
    assert not by_node(result, req)
    assert not result.summary["effort_rated_cells"]


@pytest.mark.parametrize("mismatch", ["mode", "snapshot"])
def test_profile_binding_refuses_before_executing(policy_graph, mismatch):
    req = request(
        policy_graph, evaluation_mode="evidence_only" if mismatch == "mode" else "scenario"
    )
    profile = SEAMLESS_STANDARD_PROFILE
    if mismatch == "snapshot":
        profile = replace(profile, bound_snapshot_id="sha256:" + "0" * 64)
    with pytest.raises(ValueError, match="SCENARIO_POLICY_.*_MISMATCH"):
        run_source_goal_batch(req, policy_graph, scenario_policy=profile)


def test_resolved_profile_contents_bind_checkpoint_not_alias(policy_graph, tmp_path):
    checkpoint = tmp_path / "checkpoint.json"
    req = request(policy_graph, source_ids=[BOB], evaluation_mode="scenario")
    result = run_source_goal_batch(
        req,
        policy_graph,
        allowed_techniques=TECHNIQUES,
        scenario_policy="standard",
        checkpoint=checkpoint,
    )
    resumed = run_source_goal_batch(
        req,
        policy_graph,
        allowed_techniques=TECHNIQUES,
        scenario_policy="seamless-standard-v1",
        checkpoint=checkpoint,
        resume=True,
    )
    assert resumed.reproducibility["runtime"]["reused_cells"] == result.summary["evaluated_cells"]
    before = checkpoint.read_bytes()
    changed = replace(SEAMLESS_STANDARD_PROFILE, description="same ID; different resolved profile")
    for profile in (changed, None):
        with pytest.raises(ValueError, match="CHECKPOINT_SCOPE_MISMATCH"):
            run_source_goal_batch(
                req,
                policy_graph,
                allowed_techniques=TECHNIQUES,
                scenario_policy=profile,
                checkpoint=checkpoint,
                resume=True,
            )
        assert checkpoint.read_bytes() == before


def test_worker_transports_exact_compiled_query_and_audit(policy_graph):
    req = request(policy_graph, source_ids=[ACTOR], evaluation_mode="scenario")
    req["target_goal_ids"] = [req["target_manifest"]["targets"][0]["goal_id"]]
    options = dict(allowed_techniques=TECHNIQUES, scenario_policy="seamless-standard-v1")
    direct = run_source_goal_batch(req, policy_graph, **options)
    worker = run_source_goal_batch(
        req, policy_graph, **options, execution_budget=BatchExecutionBudget(per_query_seconds=30)
    )
    assert (
        direct.reproducibility["inputs"]["public_queries"]
        == worker.reproducibility["inputs"]["public_queries"]
    )


def test_compiled_discovery_feeds_verified_intervention_without_new_rules(policy_graph, tmp_path):
    req, result = run(policy_graph)
    assert by_node(result, req) == {(ACTOR, GROUP), (ACTOR, HOST)}
    report = evaluate_interventions(
        policy_graph,
        result.to_dict(),
        limit=1,
        max_sources=0,
        max_targets=0,
        output_dir=tmp_path,
        execution_budget=BatchExecutionBudget(),
    )
    assert report["evaluated_interventions"] == 1


def test_mixed_context_runtime_candidates_remain_visible_and_cannot_run(policy_graph):
    from scripts.exposure import remediation_cells

    _, result = run(policy_graph)
    cells = remediation_cells(result.to_dict(), max_sources=0, max_targets=0)
    baseline = prepare_baseline(policy_graph, cells, run_id="mixed-context")
    inventory = inventory_interventions(policy_graph, baseline)
    refused = [
        c for c in inventory["candidates"] if "authentication context mismatch" in c["reason"]
    ]
    assert refused and all(c["status"] == "unsupported" for c in refused)
    selected = requests_from_inventory(baseline, inventory, limit=100)
    assert selected
    for candidate in refused:
        assert candidate["technical_edits"] and candidate["observed_bindings"]
        assert all(r["edits"] != candidate["technical_edits"] for r in selected)
        forged = request_for_baseline(baseline, candidate["technical_edits"], request_id="refused")
        with pytest.raises(ValueError, match="runtime authentication context mismatch"):
            replay_baseline(forged, policy_graph, baseline)


def test_cli_selected_policy_implies_scenario_and_preserves_policy_on_resume(
    policy_graph, tmp_path
):
    graph_path = tmp_path / "graph.json"
    graph_path.write_text(json.dumps(policy_graph.to_canonical()))
    output = tmp_path / "run"
    command = [
        sys.executable,
        "-m",
        "scripts.exposure",
        "--graph",
        str(graph_path),
        "--source",
        BOB,
        "--authentication-context",
        HOST,
        "--user-profile",
        "user_usable_identity",
        "--scenario-policy",
        "seamless-standard-v1",
        "--output-dir",
        str(output),
        "--max-cells",
        "1",
        "--target-scope",
        "all",
        "--technique",
        "propagate_group_entitlement",
    ]
    refused = subprocess.run(
        command + ["--evaluation-mode", "evidence_only"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert refused.returncode == 2 and "explicit --evaluation-mode" in refused.stderr
    assert not output.exists()
    subprocess.run(command, cwd=ROOT, capture_output=True, text=True, check=True)
    first = (output / "result.json").read_bytes()
    command += ["--resume"]
    subprocess.run(command, cwd=ROOT, capture_output=True, text=True, check=True)
    summary = json.loads((output / "summary.json").read_text())
    assert summary["evaluation_mode"] == "scenario"
    result = json.loads((output / "result.json").read_text())
    assert summary["scenario_policy"]["digest"] == SEAMLESS_STANDARD_PROFILE.digest()
    assert result["reproducibility"]["runtime"]["reused_cells"] == 1
    previous = next(
        p for p in summary["resume"]["previous_artifacts"] if p["original"] == "result.json"
    )
    assert (output / previous["archive"]).read_bytes() == first
    saved = (output / "result.json").read_bytes()
    no_policy = copy.copy(command)
    no_policy += ["--evaluation-mode", "scenario"]
    i = no_policy.index("--scenario-policy")
    del no_policy[i : i + 2]
    refused = subprocess.run(no_policy, cwd=ROOT, capture_output=True, text=True)
    assert refused.returncode == 2 and "CHECKPOINT_SCOPE_MISMATCH" in refused.stderr
    assert (output / "result.json").read_bytes() == saved
