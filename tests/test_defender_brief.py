"""Product output is grounded in native witnesses, not SID/hop descriptions."""

import copy

import pytest
from test_computer_foothold_boundary import CASES, TECHNIQUES
from test_engine import ACTOR, GROUP, HOST
from test_machine_identity_profile import request, scenario
from test_machine_reset_effort import two_owner_inputs

from scripts.defender_brief import build_defender_brief, render_defender_brief
from scripts.exposure import archive_outputs, evaluate_interventions, inventory_exposure
from src.engine.batch import BatchExecutionBudget, run_source_goal_batch
from src.engine.ranking.reset_effort import MACHINE_PROFILE_ID


def inputs(*, effort=True, cap=None):
    graph, query = scenario(CASES[2])
    if cap:
        graph, query = two_owner_inputs()
    req = request(graph, query)
    if cap:
        req["common_budget"]["max_paths"] = cap
    result = run_source_goal_batch(
        req,
        graph,
        allowed_techniques=TECHNIQUES,
        effort_profile=MACHINE_PROFILE_ID if effort else None,
    ).to_dict()
    return graph, req, result


def test_brief_retains_actor_switch_context_not_host_takeover_and_evidence():
    graph, req, result = inputs()
    original = copy.deepcopy(result)
    brief = build_defender_brief(graph, inventory_exposure(graph), req, result)
    row = brief["goals"][0]
    assert row["C"] == 1 and row["P"] is None and row["business_impact"] == "Unknown"
    assert row["minimum_proven"] and row["reached"]
    assert sum(u["cost"] for u in row["effort_units"]) == row["C"]
    assert {u["lookup"]["technique"]: u["cost"] for u in row["effort_units"]} == {
        "scenario_reset_password": 1,
        "acquire_reset_identity": 0,
    }
    assert all(u["numeric_basis_class"] == "estimated_expert_scenario" for u in row["effort_units"])
    assert [s["actor"]["id"] for s in row["steps"]] == [HOST, ACTOR, ACTOR]
    assert [s["target"]["id"] for s in row["steps"]] == [ACTOR, HOST, GROUP]
    assert set(row["steps"][1]["effects"]) == {"usable_identity"}
    assert row["steps"][1]["derived_from_step"] == 0
    assert (
        row["steps"][0]["edge_provenance"] == graph.edge(row["steps"][0]["edge_id"])["provenance"]
    )
    assert all(f["provenance_reference"] for f in row["conditions"])
    assert any(f["origin"] == "declared_assumption" for f in row["conditions"])
    assert result == original
    text = render_defender_brief(brief)
    assert graph.node(ACTOR)["label"] in text and graph.node(GROUP)["label"] in text
    assert "GenericAll" in text and "chưa phải bằng chứng cắt hết đường" in text
    assert "không tự cấp quyền admin" in text


@pytest.mark.parametrize("effort", [False, True])
def test_best_found_and_unrated_never_become_zero_or_minimum(effort):
    graph, req, result = inputs(effort=effort, cap=1)
    brief = build_defender_brief(graph, inventory_exposure(graph), req, result)
    row = brief["goals"][0]
    assert row["reached"] and row["truncated"] and not row["minimum_proven"]
    assert row["C"] == (1 if effort else None)
    if not effort:
        assert "chưa chấm" in render_defender_brief(brief)


def test_budget_not_run_stays_visible_as_unresolved():
    from test_exposure import assumptions, request
    from test_exposure import graph as graph_fixture

    graph = graph_fixture.__wrapped__()
    req = request(graph, source_ids=[ACTOR], evaluation_mode="scenario", assumptions=assumptions())
    result = run_source_goal_batch(
        req,
        graph,
        allowed_techniques=TECHNIQUES,
        execution_budget=BatchExecutionBudget(max_cells=1),
    ).to_dict()
    brief = build_defender_brief(graph, inventory_exposure(graph, target_scope="all"), req, result)
    coverage = brief["coverage"]
    assert coverage["evaluated_pairs"] == 1
    assert coverage["not_run_pairs"] == coverage["selected_pairs"] - 1
    assert coverage["unresolved_pairs"] >= coverage["not_run_pairs"]
    assert f"1/{coverage['selected_pairs']}" in render_defender_brief(brief)


def test_brief_refuses_a_different_snapshot_and_missing_claimed_witness():
    graph, req, result = inputs()
    altered = copy.deepcopy(result)
    altered["snapshot_id"] = "sha256:" + "0" * 64
    with pytest.raises(ValueError, match="same snapshot"):
        build_defender_brief(graph, inventory_exposure(graph), req, altered)
    for trace in altered["reproducibility"]["inputs"]["public_queries"].values():
        trace["result"]["paths"] = []
        trace["result"]["best_path"] = None
    altered["snapshot_id"] = result["snapshot_id"]
    with pytest.raises(ValueError, match="no native witness"):
        build_defender_brief(graph, inventory_exposure(graph), req, altered)


def test_resume_archives_existing_defender_outputs_by_hash(tmp_path):
    for name in ["defender-brief.json", "defender-brief.md"]:
        (tmp_path / name).write_text("previous defender decision\n")
    saved = archive_outputs(tmp_path)
    assert {r["original"] for r in saved} == {"defender-brief.json", "defender-brief.md"}
    assert all(
        (tmp_path / r["archive"]).read_text() == "previous defender decision\n" for r in saved
    )


def test_optional_verified_remediation_keeps_cut_programs_separate_from_disconnects(tmp_path):
    graph, req, result = inputs()
    remediation = evaluate_interventions(
        graph,
        result,
        limit=1,
        max_sources=1,
        max_targets=1,
        output_dir=tmp_path,
        execution_budget=BatchExecutionBudget(),
    )
    assert remediation["status"] == "executed" and remediation["evaluated_interventions"] == 1
    brief = build_defender_brief(
        graph, inventory_exposure(graph), req, result, remediation=remediation
    )
    text = render_defender_brief(brief)
    assert "Programs bị cắt" in text and "Cặp chứng minh ngắt" in text
    assert "cohort can thiệp đã chạy" in text
    assert remediation["outcomes"][0]["reachable_before"] == 1
    assert "**Đã thử:**" in text and "cặp còn reachable:" in text


def test_capped_remediation_brief_shows_new_bypass_despite_all_old_programs_cut(tmp_path):
    graph, req, result = inputs(cap=1)
    remediation = evaluate_interventions(
        graph,
        result,
        limit=1,
        max_sources=1,
        max_targets=1,
        output_dir=tmp_path,
        execution_budget=BatchExecutionBudget(),
    )
    outcome = remediation["outcomes"][0]
    assert outcome["programs_cut"]["percent"] == 100
    assert outcome["programs_cut"]["scope"] == "observed_corpus_only"
    assert outcome["reachable_before"] == outcome["reachable_after"] == 1
    assert outcome["pairs_disconnected"]["numerator"] == outcome["unresolved_after"] == 0
    assert outcome["new_after_programs"] == 1
    brief = build_defender_brief(
        graph, inventory_exposure(graph), req, result, remediation=remediation
    )
    text = render_defender_brief(brief)
    assert "Cắt 1/1 programs" in text and "**1 → 1**" in text
    assert "Chứng minh ngắt: 0/1" in text and "Tìm lại được 1 programs mới" in text
    assert "không phải toàn bộ đường có thể có" in text
    legacy = copy.deepcopy(brief)
    legacy["remediation"].pop("outcomes")
    assert "Programs bị cắt" in render_defender_brief(legacy)
