"""Portable CLI checks using manifest-bound synthetic CSV bytes."""

import csv
import json
import subprocess
import sys
from pathlib import Path

import pytest

from src.data.manifest import generate_manifest, write_manifest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize(
    "payload_field", ["ScriptBlockText", "CommandLine", "EventPayload", "AttributeValue"]
)
def test_cli_verifies_bytes_and_keeps_payload_values_private(tmp_path, payload_field):
    raw = tmp_path / "raw"
    raw.mkdir()
    csv_path = raw / "evtx_data.csv"
    fields = ["EventID", "ProviderName", "Channel", "EVTX_Tactic", payload_field]
    with csv_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(fields)
        writer.writerow(["4104", "SyntheticProvider", "SyntheticChannel", "label", "PRIVATE"])
    manifest = generate_manifest(
        raw,
        dataset_id="synthetic-telemetry",
        collector_name="synthetic",
        collector_version=None,
        collected_at=None,
    )
    manifest_path = tmp_path / "manifest.json"
    write_manifest(manifest, manifest_path, source=raw)
    output = tmp_path / "report.json"
    command = [
        sys.executable,
        str(ROOT / "scripts/audit_windows_telemetry_raw.py"),
        "--raw-dir",
        str(raw),
        "--manifest",
        str(manifest_path),
        "--output",
        str(output),
    ]
    result = subprocess.run(command, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    payload = output.read_bytes()
    report = json.loads(payload)
    assert report["csv"]["row_count"] == 1
    assert report["source"]["manifest_verified"] is True
    assert report["source"]["snapshot_id"] == manifest["snapshot_id"]
    assert report["selected_event_profiles"]["4104"]["nonempty_fields"][payload_field] == 1
    assert b"PRIVATE" not in payload
    assert b"\r\n" not in payload
    assert payload.endswith(b"\n")

    # A present but changed corpus must fail, not skip or silently replace the report.
    csv_path.write_bytes(csv_path.read_bytes() + b"tampered")
    result = subprocess.run(command, capture_output=True, text=True)
    assert result.returncode != 0
    assert "manifest verification" in result.stderr
    assert output.read_bytes() == payload


def _run_synthetic_cli(tmp_path, fields, row):
    raw = tmp_path / "raw"
    raw.mkdir()
    csv_path = raw / "evtx_data.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(fields)
        writer.writerow(row)
    manifest = generate_manifest(
        raw,
        dataset_id="synthetic-telemetry",
        collector_name="synthetic",
        collector_version=None,
        collected_at=None,
    )
    manifest_path = tmp_path / "manifest.json"
    write_manifest(manifest, manifest_path, source=raw)
    output = tmp_path / "report.json"
    command = [
        sys.executable,
        str(ROOT / "scripts/audit_windows_telemetry_raw.py"),
        "--raw-dir",
        str(raw),
        "--manifest",
        str(manifest_path),
        "--output",
        str(output),
    ]
    return subprocess.run(command, capture_output=True, text=True)


def test_cli_rejects_missing_required_columns(tmp_path):
    result = _run_synthetic_cli(
        tmp_path,
        ["EventID", "Channel", "EVTX_Tactic"],
        ["4624", "Security", "label"],
    )
    assert result.returncode != 0
    assert "missing required columns" in result.stderr


def test_cli_rejects_malformed_row_width(tmp_path):
    result = _run_synthetic_cli(
        tmp_path,
        ["EventID", "ProviderName", "Channel", "EVTX_Tactic"],
        ["4624", "SecurityProvider", "Security"],
    )
    assert result.returncode != 0
    assert "row width does not match header width" in result.stderr
