"""Bridge consumes the accepted #179 artifact pins and rejects fixture drift."""

import hashlib
import json
from copy import deepcopy
from pathlib import Path

import pytest

from scripts.research.week3_semantic_bridge_probe import PLAN, ROOT, load_acceptance_inputs


def inputs(tmp_path):
    plan = json.loads(PLAN.read_text(encoding="utf-8"))
    accepted_path = Path(plan["acceptance_manifest"]["accepted_plan_path"])
    accepted = json.loads((ROOT / accepted_path).read_text(encoding="utf-8"))
    manifest_path = Path(accepted["acceptance_manifest"]["path"])
    (tmp_path / accepted_path).parent.mkdir(parents=True)
    (tmp_path / accepted_path).write_text(json.dumps(accepted), encoding="utf-8")
    (tmp_path / manifest_path).parent.mkdir(parents=True)
    (tmp_path / manifest_path).write_bytes((ROOT / manifest_path).read_bytes())
    return plan, accepted, accepted_path, manifest_path


def test_bridge_consumes_current_accepted_pin_and_records_verified_inputs():
    plan = json.loads(PLAN.read_text(encoding="utf-8"))
    accepted_path = plan["acceptance_manifest"]["accepted_plan_path"]
    accepted = json.loads((ROOT / accepted_path).read_text(encoding="utf-8"))
    manifest, audit = load_acceptance_inputs(ROOT, plan)
    assert plan["acceptance_manifest"] == {"accepted_plan_path": accepted_path}
    assert audit["acceptance_manifest"]["blob_sha"] == accepted["acceptance_manifest"]["blob_sha"]
    assert (
        audit["acceptance_manifest"]["source_revision"]
        == accepted["acceptance_manifest"]["source_revision"]
    )
    assert (
        audit["accepted_plan"]["file_sha256"]
        == hashlib.sha256((ROOT / accepted_path).read_bytes()).hexdigest()
    )
    assert {case["case_id"] for case in manifest["cases"]} == set(plan["cases"])


def test_same_json_with_changed_bytes_fails_exact_blob_pin(tmp_path):
    plan, _, _, path = inputs(tmp_path)
    manifest = json.loads((tmp_path / path).read_text(encoding="utf-8"))
    (tmp_path / path).write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="blob pin mismatch"):
        load_acceptance_inputs(tmp_path, plan)


def test_corrupt_canonical_pin_fails_even_with_correct_blob(tmp_path):
    plan, accepted, path, _ = inputs(tmp_path)
    accepted["acceptance_manifest"]["canonical_digest"] = "sha256:" + "0" * 64
    (tmp_path / path).write_text(json.dumps(accepted), encoding="utf-8")
    with pytest.raises(ValueError, match="canonical pin mismatch"):
        load_acceptance_inputs(tmp_path, plan)


@pytest.mark.parametrize("field,value", [("blob_sha", "17a3fbe6"), ("source_revision", "85205866")])
def test_duplicate_stale_pins_are_rejected(tmp_path, field, value):
    plan, _, _, _ = inputs(tmp_path)
    plan["acceptance_manifest"][field] = value
    with pytest.raises(ValueError, match="not duplicate manifest pins"):
        load_acceptance_inputs(tmp_path, plan)


def test_accepted_plan_release_mismatch_fails_before_probe(tmp_path):
    plan, accepted, path, _ = inputs(tmp_path)
    accepted["release_digest"] = "sha256:" + "0" * 64
    (tmp_path / path).write_text(json.dumps(accepted), encoding="utf-8")
    with pytest.raises(ValueError, match="accepted plan release digest mismatch"):
        load_acceptance_inputs(tmp_path, plan)


def test_manifest_release_mismatch_fails_even_with_updated_content_pins(tmp_path):
    plan, accepted, accepted_path, manifest_path = inputs(tmp_path)
    manifest = json.loads((tmp_path / manifest_path).read_text(encoding="utf-8"))
    manifest["release"]["digest"] = "sha256:" + "0" * 64
    raw = json.dumps(manifest).encode()
    (tmp_path / manifest_path).write_bytes(raw)
    accepted["acceptance_manifest"]["blob_sha"] = hashlib.sha1(
        b"blob " + str(len(raw)).encode() + b"\0" + raw
    ).hexdigest()
    from src.engine.semantics.evidence_view import digest

    accepted["acceptance_manifest"]["canonical_digest"] = digest(manifest)
    (tmp_path / accepted_path).write_text(json.dumps(accepted), encoding="utf-8")
    with pytest.raises(ValueError, match="acceptance manifest release digest mismatch"):
        load_acceptance_inputs(tmp_path, plan)


def test_bridge_case_drift_fails_before_probe(tmp_path):
    plan, _, _, _ = inputs(tmp_path)
    plan = deepcopy(plan)
    plan["cases"].pop(next(iter(plan["cases"])))
    with pytest.raises(ValueError, match="case IDs differ"):
        load_acceptance_inputs(tmp_path, plan)


def test_main_rejects_fixture_drift_before_reading_raw_or_graph(tmp_path, monkeypatch):
    from scripts.research import week3_semantic_bridge_probe as probe

    plan, _, _, manifest_path = inputs(tmp_path)
    plan_path = tmp_path / "bridge-plan.json"
    plan_path.write_text(json.dumps(plan), encoding="utf-8")
    with (tmp_path / manifest_path).open("ab") as stream:
        stream.write(b"\n")
    monkeypatch.setattr(probe, "ROOT", tmp_path)
    monkeypatch.setattr(probe, "PLAN", plan_path)
    with pytest.raises(ValueError, match="blob pin mismatch"):
        probe.main(
            [
                "--graph",
                str(tmp_path / "absent-graph.json"),
                "--raw-dir",
                str(tmp_path / "absent-raw"),
                "--case-id",
                "w3-source-a-positive",
                "--output",
                str(tmp_path / "report.json"),
            ]
        )
    assert not (tmp_path / "report.json").exists()
