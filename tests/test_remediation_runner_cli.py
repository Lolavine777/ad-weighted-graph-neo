"""Actual CLI transport/export checks, without substituting fixture results."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.research.remediation_acceptance import validate_result

ROOT = Path(__file__).resolve().parents[1]


def test_finite_one_command_exports_strict_reports_and_native_proofs(tmp_path):
    process = subprocess.run(
        [
            sys.executable,
            "-m",
            "scripts.research.remediation_runner",
            "--finite",
            "--fix",
            "shared-channel",
            "--include-individuals",
            "--output-dir",
            str(tmp_path),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )
    evidence = json.loads(process.stdout)
    assert len(evidence["comparisons"]) == 3
    assert evidence["process_peak_rss_bytes"] > 0
    assert evidence["runtime_seconds"] > 0
    assert "S-1-5-21-" not in process.stdout
    reports = [
        json.loads(p.read_text(encoding="utf-8")) for p in sorted(tmp_path.glob("report-*.json"))
    ]
    assert sorted(r["summary"]["pairs_disconnected"]["numerator"] for r in reports) == [1, 1, 2]
    assert sorted(r["summary"]["programs_cut"]["numerator"] for r in reports) == [1, 3, 4]
    for report in reports:
        validate_result(report)
    packages = [json.loads(p.read_text(encoding="utf-8")) for p in tmp_path.glob("package-*.json")]
    assert all(p["artifacts"] and p["replay_ref"] for p in packages)
    assert "disconnected" in (tmp_path / "table.md").read_text(encoding="utf-8")


@pytest.mark.integration
def test_manifest_verified_seamless_bounded_pilot(tmp_path):
    raw = os.environ.get("REMEDIATION284_RUN_RAW_PILOT")
    if not raw:
        pytest.skip(
            "Set REMEDIATION284_RUN_RAW_PILOT to authorized manifest-verified raw directory"
        )
    process = subprocess.run(
        [
            sys.executable,
            "-m",
            "scripts.research.remediation_runner",
            "--seamless-raw-dir",
            raw,
            "--output-dir",
            str(tmp_path),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )
    evidence = json.loads(process.stdout)
    assert evidence["verified_raw_files"] == 6
    assert evidence["process_peak_rss_bytes"] > 0
    cases = {c["intervention"]: c for c in evidence["comparisons"]}
    assert cases["shared-channel"]["pairs_disconnected"]["numerator"] == 1
    assert cases["ineffective-membership-retained-bypass"]["remaining_bypasses"] == 1
    assert cases["ineffective-membership-retained-bypass"]["programs_cut"]["numerator"] == 0
    assert cases["missing-recovery-control"]["pairs_disconnected"]["numerator"] == 0
    assert cases["step-cap-control"]["pairs_disconnected"]["numerator"] == 0
    assert cases["step-cap-control"]["rediscovery"] == {"truncated": 1}
