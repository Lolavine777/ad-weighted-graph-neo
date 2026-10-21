"""A confirmed target must not hide a different target's coverage limitation."""

import copy

import pytest
from test_engine import HOST
from test_session_material_boundary import batch_request

from src.engine.batch import BatchExecutionBudget, run_source_goal_batch


@pytest.mark.parametrize("worker", [False, True])
def test_confirmed_host_goal_keeps_witness_and_reports_other_goal_unsupported(worker):
    graph, request, techniques, group_goal = batch_request()
    host = copy.deepcopy(request["target_manifest"]["targets"][0])
    host.update(
        goal_id="already-declared-local-admin",
        category="tier_1_host",
        target_node_id=HOST,
        target_node_kind="Computer",
        display_name="Synthetic declared local host control",
        technical_consequence="host_administrative_takeover",
        impact_rating="High",
        required_control_level="host_admin_execution",
        required_state={"admin_control": [HOST]},
        checkpoint_goal=None,
    )
    host.pop("goal_kind", None)
    request["target_manifest"]["targets"].append(host)
    request["target_goal_ids"] = [group_goal, host["goal_id"]]
    result = run_source_goal_batch(
        request,
        graph,
        allowed_techniques=techniques,
        execution_budget=BatchExecutionBudget(per_query_seconds=10) if worker else None,
    )
    row = result.source_goal_matrix[request["sources"][0]["source_id"]]
    assert row[group_goal].status == "unsupported_semantics"
    assert row[host["goal_id"]].status == "complete_success"
    assert row[host["goal_id"]].final_goal_reached
    priority = result.source_prioritization[0]
    assert priority.reachable_goals_count == 1
    assert priority.highest_impact_reached == priority.priority_class == "High"
    assert priority.disposition == "unsupported_semantics"
    assert "coverage is incomplete" in priority.explainability
    assert result.schema_version == "batch-query-result/1.1.0"
