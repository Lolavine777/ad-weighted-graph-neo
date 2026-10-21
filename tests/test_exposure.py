"""Snapshot discovery has independent finite expectations, not a search-generated oracle."""

import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest
from jsonschema.exceptions import ValidationError
from test_engine import ACTOR, GROUP, HOST, TOY, _edge

from scripts.exposure import (
    build_request,
    evaluate_interventions,
    inventory_exposure,
    remediation_cells,
)
from scripts.research.source_goal_batch import TargetManifest
from src.engine import batch as batch_module
from src.engine.batch import BatchExecutionBudget, run_source_goal_batch, validate_schema
from src.engine.graph import EngineGraph

ROOT = Path(__file__).resolve().parents[1]
DOMAIN = "S-1-5-21-1000-2000-3000"
BOB = DOMAIN + "-1102"
MARKER = DOMAIN + "-2104"
DC_GROUP = DOMAIN + "-516"
DC = "10000000-0000-4000-8000-000000000003"
TECHNIQUES = ["propagate_group_entitlement", "obtain_admin_execution_on_host"]


@pytest.fixture
def graph():
    raw = copy.deepcopy(TOY)
    raw["nodes"] = [n for n in raw["nodes"] if n["domain"] == "EXAMPLE.TEST"]
    template = copy.deepcopy(next(n for n in raw["nodes"] if n["id"] == ACTOR))
    template.update(id=BOB, label="Bob", enabled=True)
    raw["nodes"].append(template)
    template = copy.deepcopy(next(n for n in raw["nodes"] if n["id"] == GROUP))
    template.update(id=MARKER, label="Domain Admins", admincount=True)
    raw["nodes"].append(template)
    template = copy.deepcopy(template)
    template.update(id=DC_GROUP, label="Not a role name", admincount=False)
    raw["nodes"].append(template)
    template = copy.deepcopy(next(n for n in raw["nodes"] if n["id"] == HOST))
    template.update(id=DC, label="Ordinary host label", enabled=True)
    raw["nodes"].append(template)
    raw["nodes"].append(
        {
            "id": DOMAIN,
            "kind": "Domain",
            "domain": "EXAMPLE.TEST",
            "label": "EXAMPLE.TEST",
            "is_boundary": False,
        }
    )
    for node in raw["nodes"]:
        if node["id"] in (ACTOR, HOST):
            node["enabled"] = True
        if node["id"] == GROUP:
            node["label"] = "Renamed privileged group"
    raw["edges"] = [
        _edge(ACTOR, GROUP, "MemberOf"),
        _edge(ACTOR, HOST, "AdminTo"),
        _edge(GROUP, HOST, "AdminTo"),
        _edge(DC, DC_GROUP, "MemberOf"),
    ]
    return EngineGraph.from_canonical(raw)


def assumptions():
    return [
        {
            "predicate": p,
            "subject": ACTOR,
            "target": target,
            "value": True,
            "scope": HOST,
            "rationale": "Declared finite oracle fixture",
            "provenance_reference": "synthetic://exposure",
        }
        for p, target in (
            ("security_group", GROUP),
            ("membership_usable", GROUP),
            ("admin_channel", HOST),
            ("authentication_accepted", HOST),
        )
    ]


def request(graph, **kwargs):
    return build_request(
        graph,
        inventory_exposure(graph, target_scope="all"),
        authentication_context=HOST,
        user_profile="user_usable_identity",
        max_sources=0,
        max_targets=0,
        **kwargs,
    )[0]


def by_node(result, req):
    sources = {s["source_id"]: s["node_id"] for s in req["sources"]}
    goals = {g["goal_id"]: g["target_node_id"] for g in req["target_manifest"]["targets"]}
    return {
        (sources[s], goals[g])
        for s, row in result.source_goal_matrix.items()
        for g, c in row.items()
        if c.final_goal_reached
    }


def test_inventory_uses_observed_sids_and_markers_not_role_labels(graph):
    inventory = inventory_exposure(graph)
    selected = {t["goal"]["target_node_id"]: t for t in inventory["targets"]}
    assert set(selected) == {GROUP, MARKER, DC}
    assert selected[GROUP]["selection_reason"] == "well_known_privileged_group_sid"
    assert selected[DC]["supporting_edge_ids"] == [_edge(DC, DC_GROUP, "MemberOf")["id"]]
    assert selected[MARKER]["selection_reason"] == "admincount_marker_not_privilege_proof"
    assert all(t["goal"]["impact_rating"] == "Unknown" for t in selected.values())
    assert all(s["node_kind"] in {"User", "Computer"} for s in inventory["sources"])
    all_targets = inventory_exposure(graph, target_scope="all")
    assert {t["goal"]["target_node_id"] for t in all_targets["targets"]} == {
        n["id"]
        for n in graph.nodes()
        if n["kind"] in {"Group", "Computer"} and not n["is_boundary"]
    }


def test_schema_successor_preserves_legacy_and_unknown_is_not_low_risk(graph):
    req = request(graph, source_ids=[ACTOR], evaluation_mode="scenario", assumptions=assumptions())
    manifest = req["target_manifest"]
    assert manifest["schema_version"] == "target-manifest/1.2.0"
    assert TargetManifest.from_dict(manifest).to_dict() == manifest
    for legacy in ("target-manifest/1.0.0", "target-manifest/1.1.0"):
        with pytest.raises(ValidationError):
            validate_schema({**manifest, "schema_version": legacy}, "target-manifest")
    result = run_source_goal_batch(req, graph, allowed_techniques=TECHNIQUES)
    assert by_node(result, req) == {(ACTOR, GROUP), (ACTOR, HOST)}
    assert result.source_prioritization[0].priority_class == "Unknown"
    assert all(
        c.min_effort is None and c.likelihood_interval is None
        for row in result.source_goal_matrix.values()
        for c in row.values()
    )


def test_multi_source_matches_independent_unary_reachability_oracle_and_is_isolated(graph):
    req = request(
        graph, source_ids=[ACTOR, BOB], evaluation_mode="scenario", assumptions=assumptions()
    )
    result = run_source_goal_batch(req, graph, allowed_techniques=TECHNIQUES)
    # Manually grounded oracle: Alice has direct membership+AdminTo, Bob has no edges.
    assert by_node(result, req) == {(ACTOR, GROUP), (ACTOR, HOST)}
    assert all(not c.truncated for row in result.source_goal_matrix.values() for c in row.values())
    for source in req["sources"]:
        single = run_source_goal_batch(
            {**req, "sources": [source]}, graph, allowed_techniques=TECHNIQUES
        )
        assert (
            single.source_goal_matrix[source["source_id"]]
            == result.source_goal_matrix[source["source_id"]]
        )


def test_computer_control_does_not_grant_user_identity(graph):
    req = request(graph, source_ids=[HOST], computer_profile="computer_control_admin")
    result = run_source_goal_batch(req, graph, allowed_techniques=TECHNIQUES)
    assert by_node(result, req) == {(HOST, HOST)}
    cells = remediation_cells(result.to_dict())
    assert all(not c["query"]["initial_state"]["usable_identity"] for c in cells)


def test_caps_and_missing_evidence_never_become_safe_or_fake_zero_cost(graph):
    req = request(graph, source_ids=[ACTOR], evaluation_mode="scenario", assumptions=assumptions())
    capped = run_source_goal_batch(
        req,
        graph,
        allowed_techniques=TECHNIQUES,
        execution_budget=BatchExecutionBudget(max_cells=1),
    )
    assert capped.summary["not_run_cells"]
    assert remediation_cells(capped.to_dict()) == []
    assert capped.source_prioritization[0].disposition == "not_evaluated"
    unknown = request(graph, source_ids=[ACTOR])
    result = run_source_goal_batch(unknown, graph, allowed_techniques=TECHNIQUES)
    host_goal = next(
        g["goal_id"] for g in req["target_manifest"]["targets"] if g["target_node_id"] == HOST
    )
    cell = next(iter(result.source_goal_matrix.values()))[host_goal]
    assert not cell.final_goal_reached and cell.status == "indeterminate"
    assert cell.min_effort is None


def test_selection_is_deterministic_and_discloses_omissions_and_graph_binding(graph):
    inventory = inventory_exposure(graph, target_scope="all")
    req, selection = build_request(
        graph, inventory, authentication_context=HOST, max_sources=1, max_targets=1
    )
    assert selection["selected_pairs"] == 1
    assert (
        selection["inventory_pairs_outside_selected_cohort"]
        == inventory["counts"]["potential_pairs"] - 1
    )
    assert not selection["all_inventory_pairs_selected"]
    altered = graph.to_canonical()
    altered["nodes"][0]["label"] += " changed"
    with pytest.raises(ValueError, match="projection"):
        build_request(EngineGraph.from_canonical(altered), inventory)
    with pytest.raises(ValueError, match="eligible"):
        build_request(graph, inventory, source_ids=[GROUP])
    with pytest.raises(ValueError, match="authentication-context"):
        build_request(graph, inventory, source_ids=[ACTOR])
    assert (
        req
        == build_request(
            graph, inventory, authentication_context=HOST, max_sources=1, max_targets=1
        )[0]
    )


def test_complete_query_rows_export_same_queries_for_rectangular_remediation(graph):
    req = request(
        graph, source_ids=[ACTOR, BOB], evaluation_mode="scenario", assumptions=assumptions()
    )
    result = run_source_goal_batch(req, graph, allowed_techniques=TECHNIQUES).to_dict()
    cells = remediation_cells(result, max_sources=0)
    assert len(cells) == 2 * len(req["target_manifest"]["targets"])
    assert {c["query"]["target"] for c in cells} == {
        g["target_node_id"] for g in req["target_manifest"]["targets"]
    }


def test_observed_false_vetoes_positive_assumption_in_generated_queries(graph):
    req = request(graph, source_ids=[ACTOR], evaluation_mode="scenario", assumptions=assumptions())
    result = run_source_goal_batch(
        req,
        graph,
        allowed_techniques=TECHNIQUES,
        runtime_facts=[
            {
                "predicate": "admin_channel",
                "subject": ACTOR,
                "target": HOST,
                "value": False,
                "origin": "observed_evidence",
                "scope": HOST,
                "provenance_reference": "synthetic://observed-denial",
            }
        ],
    )
    assert by_node(result, req) == {(ACTOR, GROUP)}
    assert not any(
        cell.min_effort == 0 for row in result.source_goal_matrix.values() for cell in row.values()
    )


def test_disabled_boundary_and_foreign_domain_sources_are_visible_exclusions(graph):
    raw = graph.to_canonical()
    for node in raw["nodes"]:
        if node["id"] == BOB:
            node["enabled"] = False
        if node["id"] == HOST:
            node["is_boundary"] = True
    inv = inventory_exposure(EngineGraph.from_canonical(raw), target_scope="all")
    assert BOB not in {s["node_id"] for s in inv["sources"]}
    assert HOST not in {s["node_id"] for s in inv["sources"]}
    assert HOST not in {t["goal"]["target_node_id"] for t in inv["targets"]}
    assert inv["exclusions"]["source_disabled"] == 1
    with pytest.raises(ValueError, match="observed canonical Domain"):
        inventory_exposure(graph, domain_sid=DOMAIN + "-999")


def test_auto_candidates_counterfactual_distinguishes_bypass_and_pair_disconnection(
    graph, tmp_path
):
    req = request(
        graph, source_ids=[ACTOR, BOB], evaluation_mode="scenario", assumptions=assumptions()
    )
    req["target_manifest"]["targets"] = [
        g for g in req["target_manifest"]["targets"] if g["target_node_id"] == HOST
    ]
    result = run_source_goal_batch(req, graph, allowed_techniques=TECHNIQUES).to_dict()
    summary = evaluate_interventions(
        graph,
        result,
        limit=3,
        max_sources=0,
        output_dir=tmp_path,
        execution_budget=BatchExecutionBudget(),
    )
    assert summary["pairs"] == 2 and summary["evaluated_interventions"] == 3
    reports = [
        json.loads((tmp_path / p["path"]).read_text())["report"]["summary"]
        for p in summary["packages"]
    ]
    assert any(
        r["programs_cut"]["numerator"] > 0 and r["pairs_disconnected"]["numerator"] == 0
        for r in reports
    )
    assert any(r["pairs_disconnected"]["numerator"] == 1 for r in reports)
    assert summary["optimal_intervention_claim"] is False


def test_executable_cli_inventories_and_runs_without_handwritten_targets(tmp_path, graph):
    path = tmp_path / "graph.json"
    path.write_text(json.dumps(graph.to_canonical()))
    output = tmp_path / "output"
    command = [
        sys.executable,
        "-m",
        "scripts.exposure",
        "--graph",
        str(path),
        "--source",
        HOST,
        "--computer-profile",
        "computer_control_admin",
        "--target-scope",
        "all",
        "--output-dir",
        str(output),
        "--technique",
        "propagate_group_entitlement",
    ]
    subprocess.run(command, cwd=ROOT, capture_output=True, text=True, check=True)
    summary = json.loads((output / "summary.json").read_text())
    assert summary["batch"]["successful_cells"] == 1
    assert summary["selection"]["selected_targets"] > 3
    assert "chưa chấm" in (output / "overview.md").read_text()
    assert "không phải an toàn" in (output / "overview.md").read_text()
    assert "usable_identity đúng context" in (output / "overview.md").read_text()
    assert "chưa nối thành" in (output / "overview.md").read_text()
    process = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
    assert process.returncode == 2 and "preserve prior run" in process.stderr


def test_checkpoint_interval_preserves_all_decisions_and_reduces_whole_cache_writes(
    tmp_path, graph, monkeypatch
):
    req = request(
        graph, source_ids=[ACTOR, BOB], evaluation_mode="scenario", assumptions=assumptions()
    )
    original = batch_module._atomic_json
    writes = []

    def measured(path, data):
        writes.append(len(data["cells"]))
        return original(path, data)

    monkeypatch.setattr(batch_module, "_atomic_json", measured)
    before = run_source_goal_batch(
        req, graph, allowed_techniques=TECHNIQUES, checkpoint=tmp_path / "per-cell.json"
    ).to_dict()
    before_writes = list(writes)
    writes.clear()
    after = run_source_goal_batch(
        req,
        graph,
        allowed_techniques=TECHNIQUES,
        checkpoint=tmp_path / "grouped.json",
        checkpoint_interval=4,
    ).to_dict()
    assert before_writes[-1] == writes[-1]
    assert len(writes) < len(before_writes)
    for data in (before, after):
        data["reproducibility"]["runtime"].pop("elapsed_seconds")
        data["reproducibility"]["runtime"].pop("checkpoint_interval", None)
    assert before == after
    assert json.loads((tmp_path / "per-cell.json").read_text()) == json.loads(
        (tmp_path / "grouped.json").read_text()
    )


def test_checkpoint_interruption_resume_keeps_binding_and_missing_cells(
    tmp_path, graph, monkeypatch
):
    req = request(
        graph, source_ids=[ACTOR, BOB], evaluation_mode="scenario", assumptions=assumptions()
    )
    original = batch_module._execute
    calls = 0

    def interrupted(*args):
        nonlocal calls
        calls += 1
        if calls == 5:
            raise KeyboardInterrupt
        return original(*args)

    path = tmp_path / "partial.json"
    with monkeypatch.context() as m:
        m.setattr(batch_module, "_execute", interrupted)
        with pytest.raises(KeyboardInterrupt):
            run_source_goal_batch(
                req, graph, allowed_techniques=TECHNIQUES, checkpoint=path, checkpoint_interval=3
            )
    assert len(json.loads(path.read_text())["cells"]) == 3
    resumed = run_source_goal_batch(
        req,
        graph,
        allowed_techniques=TECHNIQUES,
        checkpoint=path,
        resume=True,
        checkpoint_interval=4,
    )
    fresh = run_source_goal_batch(req, graph, allowed_techniques=TECHNIQUES)
    assert resumed.source_goal_matrix == fresh.source_goal_matrix
    assert resumed.reproducibility["runtime"]["reused_cells"] == 3
    assert len(json.loads(path.read_text())["cells"]) == len(req["target_manifest"]["targets"]) * 2
    bad = copy.deepcopy(req)
    bad["sources"][0]["profile_kind"] = "user_leaked_password"
    with pytest.raises(ValueError, match="CHECKPOINT_SCOPE_MISMATCH"):
        run_source_goal_batch(
            bad, graph, allowed_techniques=TECHNIQUES, checkpoint=path, resume=True
        )


@pytest.mark.parametrize("value", [0, -1, True, 1.5])
def test_checkpoint_interval_rejects_invalid_values(graph, value):
    with pytest.raises(ValueError, match="positive integer"):
        run_source_goal_batch(request(graph, source_ids=[ACTOR]), graph, checkpoint_interval=value)


def test_cli_resume_advances_budget_without_losing_previous_reports(tmp_path, graph):
    path = tmp_path / "graph.json"
    path.write_text(json.dumps(graph.to_canonical()))
    output = tmp_path / "output"
    command = [
        sys.executable,
        "-m",
        "scripts.exposure",
        "--graph",
        str(path),
        "--source",
        HOST,
        "--computer-profile",
        "computer_control_admin",
        "--target-scope",
        "all",
        "--max-cells",
        "1",
        "--output-dir",
        str(output),
        "--technique",
        "propagate_group_entitlement",
    ]
    subprocess.run(command, cwd=ROOT, capture_output=True, text=True, check=True)
    first = (output / "result.json").read_bytes()
    command[command.index("--max-cells") + 1] = "100"
    command.append("--resume")
    subprocess.run(command, cwd=ROOT, capture_output=True, text=True, check=True)
    result = json.loads((output / "result.json").read_text())
    summary = json.loads((output / "summary.json").read_text())
    assert result["reproducibility"]["runtime"]["reused_cells"] == 1
    assert result["summary"]["successful_cells"] == 1
    assert not result["summary"]["not_run_cells"]
    archived = next(
        p for p in summary["resume"]["previous_artifacts"] if p["original"] == "result.json"
    )
    assert (output / archived["archive"]).read_bytes() == first
    before = (output / "result.json").read_bytes()
    command += ["--max-targets", "1"]
    refused = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
    assert refused.returncode == 2 and "Generated request changed" in refused.stderr
    assert (output / "result.json").read_bytes() == before
