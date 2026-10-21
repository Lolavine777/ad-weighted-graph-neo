"""CLI regressions for PR #170, using disposable synthetic input copies."""

from __future__ import annotations

import copy
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

from scripts.research import reconcile_rating_sheets as tool

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests/fixtures/ranking"
SYNTHETIC = FIXTURES / "synthetic"
GROUPS = ("impact_ratings", "likelihood_ratings", "effort_ratings")


def sheets(*, pending=False, second="synthetic_rater_2_rated.json"):
    if pending:
        paths = [FIXTURES / f"seamless_rater_{i}.json" for i in (1, 2)]
    else:
        paths = [SYNTHETIC / "synthetic_rater_1_rated.json", SYNTHETIC / second]
    return [json.loads(p.read_bytes()) for p in paths]


def write_inputs(tmp_path, data):
    paths = [tmp_path / f"sheet{i}.json" for i in (1, 2)]
    for path, sheet in zip(paths, data, strict=True):
        path.write_text(json.dumps(sheet), encoding="utf-8")
    return paths


def cli(paths, output=None, registry=None):
    args = ["--sheet1", str(paths[0]), "--sheet2", str(paths[1])]
    if output is not None:
        args += ["--output", str(output)]
    if registry is not None:
        args += ["--registry", str(registry)]
    return args


def run_cli(paths, output=None, registry=None):
    return subprocess.run(
        [sys.executable, str(ROOT / "scripts/research/reconcile_rating_sheets.py")]
        + cli(paths, output, registry),
        capture_output=True,
        text=True,
        check=False,
    )


def assert_invalid(tmp_path, data, field, registry=None):
    paths = write_inputs(tmp_path, data)
    before = [p.read_bytes() for p in paths]
    output = tmp_path / "report.json"
    output.write_bytes(b"previous report\r\n")
    result = run_cli(paths, output, registry)
    assert result.returncode == 1, result.stdout
    assert field in result.stderr, result.stderr
    assert output.read_bytes() == b"previous report\r\n"
    assert [p.read_bytes() for p in paths] == before
    output.unlink()
    result = run_cli(paths, output, registry)
    assert result.returncode == 1
    assert not output.exists()


@pytest.mark.parametrize("collision", ["input", "sentinel", "symlink"])
def test_cli_does_not_touch_preexisting_predictable_temp_path(tmp_path, collision):
    paths = write_inputs(tmp_path, sheets())
    output = tmp_path / "report.json"
    legacy_temp = tmp_path / f".report.json.tmp.{os.getpid()}"
    if collision == "input":
        paths[0].rename(legacy_temp)
        paths[0] = legacy_temp
    elif collision == "sentinel":
        legacy_temp.write_bytes(b"unrelated file")
    else:
        try:
            legacy_temp.symlink_to(paths[0])
        except OSError:
            pytest.skip("Symlink creation unavailable on this platform")
    before = [p.read_bytes() for p in paths]
    temp_before = legacy_temp.read_bytes()
    assert tool.main(cli(paths, output)) == 0
    assert [p.read_bytes() for p in paths] == before
    assert legacy_temp.read_bytes() == temp_before
    assert not output.is_symlink()
    assert json.loads(output.read_bytes())["coverage"]["fully_rated_pairs_count"] == 21
    if collision == "symlink":
        assert legacy_temp.is_symlink()


@pytest.mark.parametrize("failure", ["create", "write", "replace"])
def test_cli_writer_failure_preserves_inputs_and_previous_report(tmp_path, monkeypatch, failure):
    paths = write_inputs(tmp_path, sheets())
    output = tmp_path / "report.json"
    output.write_bytes(b"previous report")
    sentinel = tmp_path / f".report.json.tmp.{os.getpid()}"
    sentinel.write_bytes(b"not owned by writer")
    before = {p: p.read_bytes() for p in [*paths, output, sentinel]}

    def fail(*args, **kwargs):
        raise OSError("synthetic disk failure")

    def partial_write(report, stream, **kwargs):
        stream.write('{"partial":')
        raise OSError("synthetic disk full")

    if failure == "create":
        monkeypatch.setattr(tempfile, "NamedTemporaryFile", fail)
    elif failure == "write":
        monkeypatch.setattr(json, "dump", partial_write)
    else:
        monkeypatch.setattr(Path, "replace", fail)
    assert tool.main(cli(paths, output)) == 1
    assert {p: p.read_bytes() for p in before} == before
    assert set(tmp_path.iterdir()) == set(before)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("schema_version", "99.0.0"),
        ("governance_version", "99.0.0"),
        ("rater", None),
        ("rater", []),
        ("status", "raetd"),
        ("status", "pending_independent_rating"),
    ],
)
def test_cli_rejects_invalid_sheet_envelope(tmp_path, field, value):
    data = sheets()
    if value is None:
        data[0].pop(field)
    else:
        data[0][field] = value
    assert_invalid(tmp_path, data, field)


@pytest.mark.parametrize(
    "field",
    ["evaluator", "name", "competence_and_scope", "independence_declaration", "rated_at"],
)
def test_cli_rejects_missing_rated_identity_metadata(tmp_path, field):
    data = sheets()
    data[0]["rater"][field] = None
    assert_invalid(tmp_path, data, field)


@pytest.mark.parametrize(
    "field", ["evaluator", "name", "competence_and_scope", "independence_declaration", "rated_at"]
)
def test_cli_pending_identity_fields_must_exist_but_may_be_null(tmp_path, field):
    data = sheets(pending=True)
    data[0]["rater"].pop(field)
    assert_invalid(tmp_path, data, field)


@pytest.mark.parametrize("value", ["", "PENDING", 42, "2026-99-99T00:00:00Z"])
def test_cli_rejects_invalid_rating_time(tmp_path, value):
    data = sheets()
    data[0]["rater"]["rated_at"] = value
    assert_invalid(tmp_path, data, "rated_at")


def test_cli_rejects_same_envelope_evaluator_before_record_pairing(tmp_path):
    data = sheets()
    for sheet in data:
        sheet["rater"]["evaluator"] = "synthetic_same"
    assert_invalid(tmp_path, data, "distinct")


@pytest.mark.parametrize("group", GROUPS)
@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("evaluator", None),
        ("evaluator", "synthetic_someone_else"),
        ("evaluator", "PENDING"),
        ("rating_status", "raetd"),
        ("rating_status", None),
        ("record_type", "unknown"),
    ],
)
def test_cli_rejects_malformed_record_identity_or_status(tmp_path, group, field, value):
    data = sheets()
    data[0][group][0][field] = value
    assert_invalid(tmp_path, data, field)


@pytest.mark.parametrize("group", GROUPS)
def test_cli_rejects_nonobject_records(tmp_path, group):
    data = sheets()
    data[0][group][0] = "not an object"
    assert_invalid(tmp_path, data, "object")


@pytest.mark.parametrize(
    ("group", "field", "value"),
    [
        ("impact_ratings", "business_rationale", None),
        ("impact_ratings", "affected_business_services", "not a list"),
        ("likelihood_ratings", "basis_category", None),
        ("likelihood_ratings", "source_references", []),
        ("likelihood_ratings", "source_references", [False]),
        ("likelihood_ratings", "uncertainty_rationale", None),
        ("effort_ratings", "effort_rationale", None),
        ("effort_ratings", "overlap_analysis", {"is_independent": True}),
    ],
)
def test_cli_rejects_rated_record_without_governance_basis(tmp_path, group, field, value):
    data = sheets()
    data[0][group][0][field] = value
    assert_invalid(tmp_path, data, field)


@pytest.mark.parametrize(
    ("group", "field", "value"),
    [
        (
            "impact_ratings",
            "business_rationale",
            "A pending migration leaves sign-ins dependent on this domain controller.",
        ),
        (
            "likelihood_ratings",
            "uncertainty_rationale",
            "A pending patch adds uncertainty about the retry policy.",
        ),
        ("likelihood_ratings", "source_references", ["https://example.org/pending-retry-policy"]),
        (
            "effort_ratings",
            "effort_rationale",
            "A pending migration adds friction to the declared preparation.",
        ),
    ],
)
def test_cli_accepts_truthful_freeform_basis_containing_pending(tmp_path, group, field, value):
    data = sheets()
    data[0][group][0][field] = value
    paths = write_inputs(tmp_path, data)
    result = run_cli(paths)
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    category = {
        "impact_ratings": "impact",
        "likelihood_ratings": "likelihood",
        "effort_ratings": "effort",
    }[group]
    assert any(
        pair["raw_records"][0][field] == value for pair in report["reconciled_pairs"][category]
    )


@pytest.mark.parametrize("field", ["competence_and_scope", "independence_declaration"])
def test_cli_accepts_truthful_rater_metadata_containing_pending(tmp_path, field):
    data = sheets()
    data[0]["rater"][field] = "AD assessment scope includes pending migration; no shared ratings."
    paths = write_inputs(tmp_path, data)
    result = run_cli(paths)
    assert result.returncode == 0, result.stderr
    assert (
        json.loads(result.stdout)["input_metadata"]["sheet1"]["rater"][field]
        == (data[0]["rater"][field])
    )


@pytest.mark.parametrize("pending", [False, True])
@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("scenario_version", None),
        ("scenario_version", "9.9.9"),
        ("quantity", "cumulative_path_probability"),
        ("outcome_work_unit_id", "other_unit"),
        ("conditioning_previous_successes", ["other_unit"]),
        ("conditioning_previous_successes", None),
        ("outcome_action_id", None),
        ("ordered_work_prefix", [42]),
        ("ordered_work_prefix", ["unknown_unit"]),
    ],
)
def test_cli_rejects_inconsistent_likelihood_binding_even_unmatched(
    tmp_path, pending, field, value
):
    data = sheets(pending=pending)
    data[0]["likelihood_ratings"][0][field] = value
    data[1]["likelihood_ratings"].pop(0)
    assert_invalid(tmp_path, data, field)


@pytest.mark.parametrize("pending", [False, True])
@pytest.mark.parametrize("field", ["context_scope", "boundary_scope", "ledger_version"])
def test_cli_rejects_effort_metadata_conflict_even_unmatched(tmp_path, pending, field):
    data = sheets(pending=pending)
    data[0]["effort_ratings"][0][field] = "conflicting_scope"
    data[1]["effort_ratings"].pop(0)
    assert_invalid(tmp_path, data, field)


@pytest.mark.parametrize("pending", [False, True])
def test_cli_rejects_registry_conflict_for_canonical_work_unit(tmp_path, pending):
    data = sheets(pending=pending)
    record = data[0]["effort_ratings"][0]
    definition = {
        "technique": record["technique_name"],
        "actor": record["actor_scope"],
        "target": record["target_scope"],
        "context": "conflicting_scope",
        "boundary": record["boundary_scope"],
        "ledger_version": record["ledger_version"],
    }
    registry = tmp_path / "registry.json"
    registry.write_text(json.dumps({record["work_unit_id"]: definition}), encoding="utf-8")
    before = registry.read_bytes()
    assert_invalid(tmp_path, data, "conflicts", registry)
    assert registry.read_bytes() == before


@pytest.mark.parametrize("pending", [False, True])
@pytest.mark.parametrize("component", ["context", "boundary", "ledger_version"])
def test_cli_rejects_incomplete_canonical_id_in_likelihood_prefix(tmp_path, pending, component):
    data = sheets(pending=pending)
    record = data[0]["likelihood_ratings"][0]
    parts = record["ordered_work_prefix"][0].split(":")
    parts[{"context": -3, "boundary": -2, "ledger_version": -1}[component]] = ""
    record["ordered_work_prefix"][0] = ":".join(parts)
    record["outcome_work_unit_id"] = record["ordered_work_prefix"][0]
    assert_invalid(tmp_path, data, "ordered_work_prefix")


@pytest.mark.parametrize("pending", [False, True])
@pytest.mark.parametrize(
    "field",
    [
        "technique_name",
        "actor_scope",
        "target_scope",
        "context_scope",
        "boundary_scope",
        "ledger_version",
    ],
)
def test_cli_rejects_opaque_effort_definition_mismatch(tmp_path, pending, field):
    data = sheets(pending=pending)
    original = data[0]["effort_ratings"][0]
    definition = {
        k: original[k]
        for k in (
            "technique_name",
            "actor_scope",
            "target_scope",
            "context_scope",
            "boundary_scope",
            "ledger_version",
        )
    }
    for sheet in data:
        sheet["effort_ratings"][0]["work_unit_id"] = "synthetic_opaque_unit"
        sheet["work_aliases"]["WU_RESET_LIDIA"] = "synthetic_opaque_unit"
    data[0]["effort_ratings"][0][field] = "conflicting_scope"
    registry = tmp_path / "registry.json"
    registry.write_text(json.dumps({"synthetic_opaque_unit": definition}), encoding="utf-8")
    assert_invalid(tmp_path, data, field, registry)


@pytest.mark.parametrize("field", ["version", "horizon", "snapshot_id", "scenario_version"])
def test_cli_rejects_malformed_query_context_in_both_sheets(tmp_path, field):
    data = sheets()
    for sheet in data:
        sheet["query_scopes"][0][field] = None
    assert_invalid(tmp_path, data, field)


@pytest.mark.parametrize(
    ("pending", "second", "unmatched"),
    [
        (False, "synthetic_rater_2_rated.json", False),
        (False, "synthetic_rater_disagreement.json", False),
        (False, "synthetic_rater_overlap_withheld.json", False),
        (True, None, False),
        (False, "synthetic_rater_2_rated.json", True),
        (True, None, True),
    ],
)
def test_cli_report_retains_lossless_audit_on_every_path(tmp_path, pending, second, unmatched):
    data = sheets(pending=pending, second=second)
    if unmatched:
        for group in GROUPS:
            data[1][group].pop(0)
    paths = write_inputs(tmp_path, data)
    result = run_cli(paths)
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report["scope_summary"]["query_scopes"] == data[0]["query_scopes"]
    for label, sheet in zip(("sheet1", "sheet2"), data, strict=True):
        assert report["input_metadata"][label] == {
            k: v for k, v in sheet.items() if k not in GROUPS
        }
    bindings = {
        "impact": ("target_asset_id", "success_event"),
        "likelihood": (
            "query_id",
            "scenario_version",
            "snapshot_id",
            "foothold_node_id",
            "quantity",
            "outcome_action_id",
            "outcome_work_unit_id",
            "conditioning_previous_successes",
            "ordered_work_prefix",
        ),
        "effort": (
            "work_unit_id",
            "technique_name",
            "actor_scope",
            "target_scope",
            "context_scope",
            "boundary_scope",
            "ledger_version",
        ),
    }
    for category, group in zip(("impact", "likelihood", "effort"), GROUPS, strict=True):
        recovered = {"sheet1": [], "sheet2": []}
        for pair in report["reconciled_pairs"][category]:
            for label, raw in zip(("sheet1", "sheet2"), pair["raw_records"], strict=True):
                recovered[label].append(raw)
                for field in bindings[category]:
                    assert pair["binding"][field] == raw[field]
        for label in recovered:
            recovered[label] += [
                item["record"]
                for item in report["unmatched_records"][label]
                if item["record_type"] == data[0][group][0]["record_type"]
            ]
        for label, sheet in zip(("sheet1", "sheet2"), data, strict=True):
            assert sorted(map(lambda r: json.dumps(r, sort_keys=True), recovered[label])) == sorted(
                json.dumps(r, sort_keys=True) for r in sheet[group]
            )
    assert "final_accepted" not in result.stdout


def test_report_audit_is_detached_from_caller_inputs(tmp_path):
    data = sheets()
    original = copy.deepcopy(data)
    report = tool.reconcile_sheets(*data, Path("s1"), Path("s2"), "d1", "d2")
    report["reconciled_pairs"]["effort"][0]["raw_records"][0]["effort_rationale"] = "changed"
    report["input_metadata"]["sheet1"]["rater"]["name"] = "changed"
    assert data == original


def test_cli_submitted_sheet_with_unrated_effort_keeps_pending_overlap(tmp_path):
    data = sheets()
    pending = sheets(pending=True)[0]["effort_ratings"][0]
    pending["overlap_analysis"]["is_independent"] = False
    pending["overlap_analysis"]["shared_preparation_tags"] = ["synthetic_shared_preparation"]
    pending["effort_rationale"] = "Synthetic unresolved preparation, points intentionally withheld"
    data[0]["effort_ratings"][0] = pending
    paths = write_inputs(tmp_path, data)
    result = run_cli(paths)
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report["coverage"]["pending_unrated_pairs_count"] == 1
    assert report["coverage"]["fully_rated_pairs_count"] == 20
    pair = next(
        p
        for p in report["reconciled_pairs"]["effort"]
        if p["binding"]["work_unit_id"] == pending["work_unit_id"]
    )
    assert pair["pair_status"] == "unreconciled_pending"
    assert pair["raw_records"][0] == pending
    assert pair["overlap_details"]["sheet1"] == pending["overlap_analysis"]
    assert report["human_acceptance"] == "pending"


def test_cli_complete_report_is_deterministic_and_does_not_claim_acceptance(tmp_path):
    paths = write_inputs(tmp_path, sheets())
    first = run_cli(paths)
    second = run_cli(paths)
    assert first.returncode == second.returncode == 0
    assert first.stdout == second.stdout
    report = json.loads(first.stdout)
    assert report["human_acceptance"] == "pending"
    assert report["coverage"]["fully_rated_pairs_count"] == 21
    assert report["coverage"]["proposed_consensus_count"] == 17


@pytest.mark.parametrize("newline", [b"\n", b"\r\n"])
def test_cli_preserves_raw_input_bytes_and_reports_environment_digest(tmp_path, newline):
    paths = write_inputs(tmp_path, sheets())
    for path in paths:
        raw = json.dumps(json.loads(path.read_bytes()), indent=2).encode() + b"\n"
        path.write_bytes(raw.replace(b"\n", newline))
    before = [p.read_bytes() for p in paths]
    result = run_cli(paths)
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    for label, raw in zip(("sheet1", "sheet2"), before, strict=True):
        assert (
            report["input_digests"][label]["digest"] == "sha256:" + hashlib.sha256(raw).hexdigest()
        )
    assert [p.read_bytes() for p in paths] == before
