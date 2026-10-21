"""Tests for expert rating sheet reconciliation tool and CLI.

Verifies sheet validation, query scope matching, record binding alignment,
pending/unrated states, descriptive agreement metrics, overlap withholding,
path aliasing protections, and immutability of actual sheets.
"""

from __future__ import annotations

import copy
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from scripts.research.path_ranking_wire_adapter import PINNED_WORK_UNIT_CATALOG
from scripts.research.reconcile_rating_sheets import (
    GOVERNANCE_NOTICE,
    REPORT_SCHEMA_VERSION,
    check_path_aliasing,
    compute_catalog_digest,
    load_and_hash_json,
    reconcile_sheets,
)

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests/fixtures/ranking"
SYNTHETIC = FIXTURES / "synthetic"


def load_fixture(path: Path) -> dict[str, Any]:
    """Helper to load a JSON fixture."""
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.mark.parametrize("newline", [b"\n", b"\r\n"])
def test_actual_sheets_byte_for_byte_immutability(tmp_path: Path, newline: bytes):
    """Run the CLI on pending copies and compare environment-specific raw bytes."""
    copies = [tmp_path / f"sheet{i}.json" for i in (1, 2)]
    for i, path in enumerate(copies, 1):
        raw = (FIXTURES / f"seamless_rater_{i}.json").read_bytes()
        path.write_bytes(raw.replace(b"\r\n", b"\n").replace(b"\n", newline))
    before = [path.read_bytes() for path in copies]
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/research/reconcile_rating_sheets.py"),
            "--sheet1",
            str(copies[0]),
            "--sheet2",
            str(copies[1]),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report["coverage"]["pending_unrated_pairs_count"] == 21
    assert [path.read_bytes() for path in copies] == before
    for label, raw in zip(("sheet1", "sheet2"), before, strict=True):
        assert report["input_digests"][label]["digest"] == (
            "sha256:" + hashlib.sha256(raw).hexdigest()
        )


def test_reconcile_actual_pending_template_sheets():
    """Verify reconciliation of the actual pending templates produces an unreconciled report."""
    s1_path = FIXTURES / "seamless_rater_1.json"
    s2_path = FIXTURES / "seamless_rater_2.json"
    s1, d1 = load_and_hash_json(s1_path, "sheet1")
    s2, d2 = load_and_hash_json(s2_path, "sheet2")

    report = reconcile_sheets(
        sheet1=s1,
        sheet2=s2,
        sheet1_path=s1_path,
        sheet2_path=s2_path,
        sheet1_digest=d1,
        sheet2_digest=d2,
    )

    assert report["report_version"] == REPORT_SCHEMA_VERSION
    assert report["processing_status"] == "complete_with_pending_records"
    assert report["governance_notice"] == GOVERNANCE_NOTICE

    # Coverage verification
    cov = report["coverage"]
    assert cov["total_sheet1_records"] == 21
    assert cov["total_sheet2_records"] == 21
    assert cov["matched_pairs_count"] == 21
    assert cov["fully_rated_pairs_count"] == 0
    assert cov["pending_unrated_pairs_count"] == 21
    assert cov["unmatched_sheet1_count"] == 0
    assert cov["unmatched_sheet2_count"] == 0

    # Pinned catalog fallback provenance
    reg_prov = report["registry_provenance"]
    assert reg_prov["source"] == "pinned_catalog_fallback"
    assert reg_prov["digest"] == f"sha256:{compute_catalog_digest()}"
    assert reg_prov["catalog_size"] == len(PINNED_WORK_UNIT_CATALOG)

    # Aggregate metrics should truthfully indicate no rated pairs
    imp = report["aggregate_metrics"]["impact"]
    assert imp["status"] == "no_rated_pairs"
    assert imp["kappa"] is None
    assert imp["observed_agreement"] is None

    lh = report["aggregate_metrics"]["likelihood"]
    assert lh["rated_pair_count"] == 0
    assert lh["mean_inter_rater_iou"] is None

    eff = report["aggregate_metrics"]["effort"]
    assert eff["rated_pair_count"] == 0
    assert eff["max_cost_delta"] is None

    # All 21 items are pending human review
    assert len(report["decisions_pending_human_review"]) == 21


def test_reconcile_positive_synthetic_rated_sheets():
    """Verify reconciliation of positive synthetic rated sheets produces expected metrics."""
    s1_path = SYNTHETIC / "synthetic_rater_1_rated.json"
    s2_path = SYNTHETIC / "synthetic_rater_2_rated.json"
    s1, d1 = load_and_hash_json(s1_path, "sheet1")
    s2, d2 = load_and_hash_json(s2_path, "sheet2")

    report = reconcile_sheets(
        sheet1=s1,
        sheet2=s2,
        sheet1_path=s1_path,
        sheet2_path=s2_path,
        sheet1_digest=d1,
        sheet2_digest=d2,
    )

    cov = report["coverage"]
    assert cov["matched_pairs_count"] == 21
    assert cov["fully_rated_pairs_count"] == 21
    assert cov["pending_unrated_pairs_count"] == 0

    # Impact metrics: both chose 'Critical' -> degenerate_zero_variance with observed agreement 1.0
    imp = report["aggregate_metrics"]["impact"]
    assert imp["status"] == "degenerate_zero_variance"
    assert imp["observed_agreement"] == 1.0
    assert imp["kappa"] is None
    assert imp["small_sample_size_warning"] is True

    # Likelihood metrics: mean IoU is non-null and positive
    lh = report["aggregate_metrics"]["likelihood"]
    assert lh["rated_pair_count"] == 11
    assert lh["mean_inter_rater_iou"] is not None
    assert lh["mean_inter_rater_iou"] > 0.50
    assert lh["high_epistemic_uncertainty_count"] == 0

    # Effort metrics: all deltas <= 1
    eff = report["aggregate_metrics"]["effort"]
    assert eff["rated_pair_count"] == 9
    assert eff["max_cost_delta"] <= 1
    assert eff["cost_disagreement_count"] == 0
    assert eff["withheld_overlap_count"] == 0


def test_impact_and_likelihood_disagreements():
    """Verify impact and likelihood disagreements trigger reconciliation panel requirements."""
    s1_path = SYNTHETIC / "synthetic_rater_1_rated.json"
    s_dis_path = SYNTHETIC / "synthetic_rater_disagreement.json"
    s1, d1 = load_and_hash_json(s1_path, "sheet1")
    s_dis, d_dis = load_and_hash_json(s_dis_path, "sheet_dis")

    report = reconcile_sheets(
        sheet1=s1,
        sheet2=s_dis,
        sheet1_path=s1_path,
        sheet2_path=s_dis_path,
        sheet1_digest=d1,
        sheet2_digest=d_dis,
    )

    assert report["processing_status"] == "complete_with_disagreements"

    # Impact pair should be in disagreement (Critical vs Low)
    imp_pair = report["reconciled_pairs"]["impact"][0]
    assert imp_pair["status"] == "disagreement"
    assert imp_pair["consequence_rating"] is None
    assert imp_pair["proposal_verdict"] == "requires_reconciliation_panel"

    # Effort pairs should have cost delta > 1
    eff = report["aggregate_metrics"]["effort"]
    assert eff["cost_disagreement_count"] > 0
    assert eff["max_cost_delta"] > 1


def test_high_epistemic_uncertainty_warning():
    """Verify that broad intervals (width > 0.50) trigger epistemic uncertainty warnings."""
    s1 = load_fixture(SYNTHETIC / "synthetic_rater_1_rated.json")
    s2 = load_fixture(SYNTHETIC / "synthetic_rater_2_rated.json")

    # Set wide bounds on first likelihood question: [1/10, 8/10] (width 0.70)
    s1["likelihood_ratings"][0]["conditional_bounds"]["lower"] = "1/10"
    s1["likelihood_ratings"][0]["conditional_bounds"]["upper"] = "8/10"
    s2["likelihood_ratings"][0]["conditional_bounds"]["lower"] = "1/10"
    s2["likelihood_ratings"][0]["conditional_bounds"]["upper"] = "8/10"

    report = reconcile_sheets(
        sheet1=s1,
        sheet2=s2,
        sheet1_path=Path("s1.json"),
        sheet2_path=Path("s2.json"),
        sheet1_digest="sha256:dummy1",
        sheet2_digest="sha256:dummy2",
    )

    lh = report["aggregate_metrics"]["likelihood"]
    assert lh["high_epistemic_uncertainty_count"] >= 1
    assert "cand_seamless_01_direct_lidia:q1" in lh["high_epistemic_uncertainty_items"]


def test_effort_overlap_withheld():
    """Verify that is_independent=False on effort records marks overlap as withheld."""
    s1_path = SYNTHETIC / "synthetic_rater_1_rated.json"
    s_ov_path = SYNTHETIC / "synthetic_rater_overlap_withheld.json"
    s1, d1 = load_and_hash_json(s1_path, "sheet1")
    s_ov, d_ov = load_and_hash_json(s_ov_path, "sheet_ov")

    report = reconcile_sheets(
        sheet1=s1,
        sheet2=s_ov,
        sheet1_path=s1_path,
        sheet2_path=s_ov_path,
        sheet1_digest=d1,
        sheet2_digest=d_ov,
    )

    eff = report["aggregate_metrics"]["effort"]
    assert eff["withheld_overlap_count"] == 1

    # Find the withheld pair
    withheld_pairs = [
        p for p in report["reconciled_pairs"]["effort"] if p.get("status") == "overlap_withheld"
    ]
    assert len(withheld_pairs) == 1
    assert withheld_pairs[0]["proposal_verdict"] == "requires_reconciliation_panel"
    assert withheld_pairs[0]["overlap_status"] == "withheld_unresolved_overlap"


def test_unmatched_records_detection():
    """Verify that extra records in one sheet are reported in unmatched_records."""
    s1 = load_fixture(SYNTHETIC / "synthetic_rater_1_rated.json")
    s2 = load_fixture(SYNTHETIC / "synthetic_rater_2_rated.json")

    # Remove the last effort record from sheet 2
    removed_effort = s2["effort_ratings"].pop()

    report = reconcile_sheets(
        sheet1=s1,
        sheet2=s2,
        sheet1_path=Path("s1.json"),
        sheet2_path=Path("s2.json"),
        sheet1_digest="sha256:dummy1",
        sheet2_digest="sha256:dummy2",
    )

    assert report["processing_status"] == "complete_with_unmatched_records"
    assert report["coverage"]["unmatched_sheet1_count"] == 1
    assert report["coverage"]["unmatched_sheet2_count"] == 0
    assert (
        report["unmatched_records"]["sheet1"][0]["work_unit_id"] == removed_effort["work_unit_id"]
    )


def test_query_scope_mismatch_rejected():
    """Verify that mismatched query scope parameters are rejected fail-closed."""
    s1 = load_fixture(SYNTHETIC / "synthetic_rater_1_rated.json")
    s2 = load_fixture(SYNTHETIC / "synthetic_rater_2_rated.json")

    # Alter scenario_version in s2 query scope
    s2["query_scopes"][0]["scenario_version"] = "9.9.9"

    with pytest.raises(ValueError, match="Query scope .* field 'scenario_version' mismatch"):
        reconcile_sheets(
            sheet1=s1,
            sheet2=s2,
            sheet1_path=Path("s1.json"),
            sheet2_path=Path("s2.json"),
            sheet1_digest="sha256:dummy1",
            sheet2_digest="sha256:dummy2",
        )


def test_duplicate_records_in_sheet_rejected():
    """Verify that duplicate record keys within the same sheet are rejected."""
    s1 = load_fixture(SYNTHETIC / "synthetic_rater_1_rated.json")
    s2 = load_fixture(SYNTHETIC / "synthetic_rater_2_rated.json")

    # Duplicate first effort record in s1
    s1["effort_ratings"].append(copy.deepcopy(s1["effort_ratings"][0]))

    with pytest.raises(ValueError, match="Duplicate effort record with key"):
        reconcile_sheets(
            sheet1=s1,
            sheet2=s2,
            sheet1_path=Path("s1.json"),
            sheet2_path=Path("s2.json"),
            sheet1_digest="sha256:dummy1",
            sheet2_digest="sha256:dummy2",
        )


def test_evaluator_identity_mismatch_and_conflict():
    """Verify that identical evaluators on both sheets are rejected when rated."""
    s1 = load_fixture(SYNTHETIC / "synthetic_rater_1_rated.json")
    s2 = load_fixture(SYNTHETIC / "synthetic_rater_2_rated.json")

    # Set both sheets to use the exact same evaluator name
    same_evaluator = "single_evaluator_conflict"
    for sheet in (s1, s2):
        sheet["rater"]["evaluator"] = same_evaluator
        for group in ("impact_ratings", "likelihood_ratings", "effort_ratings"):
            for record in sheet[group]:
                record["evaluator"] = same_evaluator

    with pytest.raises(ValueError, match="Evaluators must be distinct independent raters"):
        reconcile_sheets(
            sheet1=s1,
            sheet2=s2,
            sheet1_path=Path("s1.json"),
            sheet2_path=Path("s2.json"),
            sheet1_digest="sha256:dummy1",
            sheet2_digest="sha256:dummy2",
        )


def test_invalid_rubric_types_rejected():
    """Verify that float or boolean rubric values are rejected."""
    s1 = load_fixture(SYNTHETIC / "synthetic_rater_1_rated.json")
    s2 = load_fixture(SYNTHETIC / "synthetic_rater_2_rated.json")

    # Boolean complexity
    s1_bad = copy.deepcopy(s1)
    s1_bad["effort_ratings"][0]["rubric_evaluation"]["t1_complexity"] = True

    with pytest.raises(TypeError, match="Rubric evaluation values must be integer"):
        reconcile_sheets(
            sheet1=s1_bad,
            sheet2=s2,
            sheet1_path=Path("s1.json"),
            sheet2_path=Path("s2.json"),
            sheet1_digest="sha256:dummy1",
            sheet2_digest="sha256:dummy2",
        )

    # Float complexity
    s1_float = copy.deepcopy(s1)
    s1_float["effort_ratings"][0]["rubric_evaluation"]["t1_complexity"] = 2.0

    with pytest.raises(TypeError, match="Rubric evaluation values must be integer"):
        reconcile_sheets(
            sheet1=s1_float,
            sheet2=s2,
            sheet1_path=Path("s1.json"),
            sheet2_path=Path("s2.json"),
            sheet1_digest="sha256:dummy1",
            sheet2_digest="sha256:dummy2",
        )


def test_invalid_likelihood_bounds_rejected():
    """Verify that inverted bounds or out-of-range bounds are rejected."""
    s1 = load_fixture(SYNTHETIC / "synthetic_rater_1_rated.json")
    s2 = load_fixture(SYNTHETIC / "synthetic_rater_2_rated.json")

    # Inverted bounds: lower 9/10 > upper 7/10
    s1_inv = copy.deepcopy(s1)
    s1_inv["likelihood_ratings"][0]["conditional_bounds"]["lower"] = "9/10"
    s1_inv["likelihood_ratings"][0]["conditional_bounds"]["upper"] = "7/10"

    with pytest.raises(ValueError, match="Conditional bounds out of range"):
        reconcile_sheets(
            sheet1=s1_inv,
            sheet2=s2,
            sheet1_path=Path("s1.json"),
            sheet2_path=Path("s2.json"),
            sheet1_digest="sha256:dummy1",
            sheet2_digest="sha256:dummy2",
        )


def test_path_aliasing_protection():
    """Verify that output aliasing input files or sheet1 == sheet2 is rejected."""
    f1 = FIXTURES / "seamless_rater_1.json"
    f2 = FIXTURES / "seamless_rater_2.json"

    # sheet1 == sheet2
    with pytest.raises(ValueError, match="Path aliasing detected.*same file"):
        check_path_aliasing(sheet1_path=f1, sheet2_path=f1, registry_path=None, output_path=None)

    # output == sheet1
    with pytest.raises(ValueError, match="cannot overwrite an input sheet"):
        check_path_aliasing(sheet1_path=f1, sheet2_path=f2, registry_path=None, output_path=f1)

    # output == sheet2
    with pytest.raises(ValueError, match="cannot overwrite an input sheet"):
        check_path_aliasing(sheet1_path=f1, sheet2_path=f2, registry_path=None, output_path=f2)


def test_cli_execution_with_atomic_output(tmp_path: Path):
    """Verify CLI writes report atomically to output file and exits cleanly."""
    out_file = tmp_path / "test_reconciliation_report.json"
    cmd = [
        sys.executable,
        "scripts/research/reconcile_rating_sheets.py",
        "--sheet1",
        str(SYNTHETIC / "synthetic_rater_1_rated.json"),
        "--sheet2",
        str(SYNTHETIC / "synthetic_rater_2_rated.json"),
        "--output",
        str(out_file),
        "--summary",
    ]

    res = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, check=False)
    assert res.returncode == 0
    assert out_file.exists()

    report = json.loads(out_file.read_text(encoding="utf-8"))
    assert report["report_version"] == REPORT_SCHEMA_VERSION
    assert report["coverage"]["matched_pairs_count"] == 21
    assert "EXPERT RATING SHEET RECONCILIATION SUMMARY" in res.stdout


def test_cli_summary_to_stderr_when_stdout_receives_json():
    """Verify that when --output is omitted, summary goes to stderr and stdout is pure JSON."""
    cmd = [
        sys.executable,
        "scripts/research/reconcile_rating_sheets.py",
        "--sheet1",
        str(SYNTHETIC / "synthetic_rater_1_rated.json"),
        "--sheet2",
        str(SYNTHETIC / "synthetic_rater_2_rated.json"),
        "--summary",
    ]

    res = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, check=False)
    assert res.returncode == 0

    # stdout must be valid JSON parseable directly
    stdout_report = json.loads(res.stdout)
    assert stdout_report["report_version"] == REPORT_SCHEMA_VERSION

    # stderr must contain the human-readable summary
    assert "EXPERT RATING SHEET RECONCILIATION SUMMARY" in res.stderr


def test_registry_file_option(tmp_path: Path):
    """Verify registry provenance when an explicit registry file is supplied."""
    reg_file = tmp_path / "custom_registry.json"
    reg_data = {
        "unit_custom_1": {
            "work_unit_id": "unit_custom_1",
            "technique": "custom_technique",
            "actor": "S-1-5-21-1271839998-3495686680-2211690266-4131",
            "target": "S-1-5-21-1271839998-3495686680-2211690266-1000",
        }
    }
    reg_file.write_text(json.dumps(reg_data), encoding="utf-8")

    out_file = tmp_path / "out.json"
    cmd = [
        sys.executable,
        "scripts/research/reconcile_rating_sheets.py",
        "--sheet1",
        str(SYNTHETIC / "synthetic_rater_1_rated.json"),
        "--sheet2",
        str(SYNTHETIC / "synthetic_rater_2_rated.json"),
        "--registry",
        str(reg_file),
        "--output",
        str(out_file),
    ]

    res = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, check=False)
    assert res.returncode == 0
    report = json.loads(out_file.read_text(encoding="utf-8"))
    reg_prov = report["registry_provenance"]
    assert reg_prov["source"] == "file"
    assert reg_prov["path"] == str(reg_file)
    assert reg_prov["digest"].startswith("sha256:")
    assert reg_prov["catalog_size"] == 1


def test_cli_failure_modes(tmp_path: Path):
    """Verify CLI exits with code 1 on nonexistent or malformed files."""
    # 1. Nonexistent file
    cmd_missing = [
        sys.executable,
        "scripts/research/reconcile_rating_sheets.py",
        "--sheet1",
        "nonexistent_sheet_file.json",
        "--sheet2",
        str(SYNTHETIC / "synthetic_rater_2_rated.json"),
    ]
    res_missing = subprocess.run(cmd_missing, cwd=ROOT, capture_output=True, text=True, check=False)
    assert res_missing.returncode == 1
    assert "not found" in res_missing.stderr

    # 2. Malformed JSON
    bad_json = tmp_path / "bad.json"
    bad_json.write_text("{ unclosed json", encoding="utf-8")
    cmd_bad = [
        sys.executable,
        "scripts/research/reconcile_rating_sheets.py",
        "--sheet1",
        str(bad_json),
        "--sheet2",
        str(SYNTHETIC / "synthetic_rater_2_rated.json"),
    ]
    res_bad = subprocess.run(cmd_bad, cwd=ROOT, capture_output=True, text=True, check=False)
    assert res_bad.returncode == 1
    assert "Invalid JSON" in res_bad.stderr


def test_invalid_impact_consequence_rejected():
    """Verify that consequence_rating not in the 4 canonical levels is rejected."""
    s1 = load_fixture(SYNTHETIC / "synthetic_rater_1_rated.json")
    s2 = load_fixture(SYNTHETIC / "synthetic_rater_2_rated.json")

    s1["impact_ratings"][0]["consequence_rating"] = "Catastrophic"

    with pytest.raises(ValueError, match="Invalid consequence_rating"):
        reconcile_sheets(
            sheet1=s1,
            sheet2=s2,
            sheet1_path=Path("s1.json"),
            sheet2_path=Path("s2.json"),
            sheet1_digest="sha256:dummy1",
            sheet2_digest="sha256:dummy2",
        )
