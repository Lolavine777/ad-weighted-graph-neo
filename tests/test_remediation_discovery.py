"""Native inventory proposals are experiments, not reachability reduction claims."""

import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest
from test_remediation_runner import inputs, read

from src.engine.remediation_runner import (
    inventory_interventions,
    requests_from_inventory,
    run_remediation,
)

ROOT = Path(__file__).resolve().parents[1]


def test_mined_direct_right_removal_preserves_the_independent_group_bypass():
    graph, baseline, _ = inputs()
    inventory = inventory_interventions(graph, baseline)
    requests = requests_from_inventory(baseline, inventory, limit=100)
    direct_edge = read("request-acl-v1.1.json")["edits"][0]["edge_id"]
    direct = next(r for r in requests if r["edits"][0].get("edge_id") == direct_edge)
    report = run_remediation(direct, graph, baseline)["report"]
    # Alice has direct and group routes; Bob retains his independent group route.
    # Two ordered programs disappear, but both source/goal pairs remain reachable.
    assert report["summary"]["programs_cut"]["percent"] == 50
    assert report["summary"]["pairs_disconnected"]["percent"] == 0
    assert [c["after"]["reachability"] for c in report["cells"]] == ["reachable", "reachable"]


def test_selection_is_bounded_and_cannot_run_unsupported_or_foreign_scope():
    graph, baseline, _ = inputs()
    inventory = inventory_interventions(graph, baseline)
    ordered = requests_from_inventory(baseline, inventory, limit=2)
    assert len(ordered) == 2
    reverse = copy.deepcopy(inventory)
    reverse["candidates"].reverse()
    assert requests_from_inventory(baseline, reverse, limit=2) == ordered
    for candidate in reverse["candidates"]:
        candidate["status"] = "unsupported"
    assert requests_from_inventory(baseline, reverse, limit=100) == []
    reverse["comparison_scope_digest"] = "foreign"
    with pytest.raises(ValueError, match="scope differs"):
        requests_from_inventory(baseline, reverse, limit=1)
    for invalid in (0, -1, True):
        with pytest.raises(ValueError, match="positive integer"):
            requests_from_inventory(baseline, inventory, limit=invalid)


def test_cli_exports_evaluated_mined_candidates_with_explicit_remaining_scope(tmp_path):
    process = subprocess.run(
        [
            sys.executable,
            "-m",
            "scripts.research.remediation_runner",
            "--finite",
            "--fix",
            "direct-admin",
            "--discover-interventions",
            "2",
            "--output-dir",
            str(tmp_path),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    summary = json.loads(process.stdout)
    assert summary["discovery"]["evaluated_candidates"] == 2
    assert summary["discovery"]["not_selected_candidates"] == 6
    assert summary["discovery"]["optimal_intervention_claim"] is False
    assert len(summary["comparisons"]) == 3
    assert "S-1-5-21-" not in process.stdout
