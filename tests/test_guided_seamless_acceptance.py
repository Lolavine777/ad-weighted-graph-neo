"""Optional real-data acceptance; never replace absent SEAMLESS with synthetic data."""

import os
from pathlib import Path

import pytest

from scripts.research.guided_exploration_acceptance import run_acceptance


def test_private_outputs_cannot_be_written_to_publishable_directory(tmp_path):
    with pytest.raises(ValueError, match="private output"):
        run_acceptance(tmp_path / "absent", tmp_path / "public")


def test_missing_dataset_is_blocked_without_synthetic_fallback(tmp_path):
    root = Path(__file__).resolve().parents[1]
    result = run_acceptance(
        tmp_path / "absent", root / "reports/generated/issue287/missing-input-test"
    )
    assert result["status"] == "BLOCKED"
    assert not result["cases"]
    assert result["matrix"][0]["status"] == "BLOCKED"


def test_manifest_verified_seamless_guided_exploration():
    raw_dir = os.environ.get("GUIDED_SEAMLESS_RAW_DIR")
    if not raw_dir:
        pytest.skip("Set GUIDED_SEAMLESS_RAW_DIR to authorized pinned SEAMLESS raw inputs")
    root = Path(__file__).resolve().parents[1]
    result = run_acceptance(Path(raw_dir), root / "reports/generated/issue287/pytest-final")
    assert result["status"] == "PASS", result["matrix"]
    assert all(row["status"] == "PASS" for row in result["matrix"])
    assert result["cases"]["A/full"]["final_goal_reached"]
    assert result["cases"]["A/full"]["ranking_disposition"] == "unrated"
    assert result["cases"]["B/structural"]["path_count"] > 0
