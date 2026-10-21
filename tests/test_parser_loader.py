"""Acceptance tests for the manifest-backed raw parser boundary."""

import json
from pathlib import Path
from typing import get_args

import pytest
import yaml

from src.data import manifest as snapshot_manifest
from src.data.manifest import ManifestError, generate_manifest, raw_file_reference
from src.parser import (
    ErrorPolicy,
    ManifestRawDataLoader,
    RawProvenance,
    TimeProvenancePolicy,
    TimeProvenanceStatus,
    TimeProvenanceStatusLiteral,
)


def make_snapshot(
    tmp_path: Path,
    *envelopes: tuple[str, object],
    collected_at: str | None = "2026-01-01T00:00:00Z",
) -> tuple[Path, dict]:
    source = tmp_path / "snapshot"
    source.mkdir()
    for relative, payload in envelopes:
        path = source / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(payload, bytes):
            path.write_bytes(payload)
        else:
            path.write_text(json.dumps(payload), encoding="utf-8")
    manifest = generate_manifest(
        source,
        dataset_id="synthetic-loader",
        collector_name="synthetic",
        collector_version="1.0",
        collected_at=collected_at,
    )
    return source, manifest


def valid_envelope() -> dict:
    return {
        "meta": {"type": "users", "version": 5},
        "data": [
            {
                "ObjectIdentifier": "SYNTHETIC-USER",
                "Members": ["SYNTHETIC-GROUP"],
                "AllowedToDelegate": ["SYNTHETIC-SERVICE"],
                "collector_specific": {"source_flag": True},
            }
        ],
    }


def test_valid_snapshot_preserves_raw_record_and_execution_identity(tmp_path):
    source, manifest = make_snapshot(tmp_path, ("users.json", valid_envelope()))
    loader = ManifestRawDataLoader(
        manifest, contract_version="1.0.0", parser_version="loader-test-1"
    )

    records = list(loader.load(source, error_policy=ErrorPolicy.SKIP_RECORD))

    assert len(records) == 1
    assert records[0].kind == "users"
    assert records[0].data == valid_envelope()["data"][0]
    assert records[0].provenance == {
        "raw_file": raw_file_reference(manifest, "users.json"),
        "collector": "synthetic/1.0",
        "timestamp": "2026-01-01T00:00:00Z",
        "snapshot_id": manifest["snapshot_id"],
        "record_locator": "#/data/0",
        "record_id": "SYNTHETIC-USER",
        "time_provenance": "observed",
    }
    assert loader.execution_identity == {
        "snapshot_id": manifest["snapshot_id"],
        "dataset_id": "synthetic-loader",
        "collector_name": "synthetic",
        "collector_version": "1.0",
        "contract_version": "1.0.0",
        "parser_version": "loader-test-1",
    }


def test_v3_envelope_version_is_declared_raw_only_provenance(tmp_path):
    envelope = valid_envelope()
    envelope["meta"]["version"] = 3
    source, manifest = make_snapshot(tmp_path, ("users.json", envelope))
    record = next(ManifestRawDataLoader(manifest).load(source))
    contract = yaml.safe_load(
        (Path(__file__).resolve().parents[1] / "configs/contract.yml").read_text(encoding="utf-8")
    )
    schema = contract["schema"]["raw_provenance"]
    assert record.provenance["schema_version"] == "3"
    assert set(record.provenance) <= set(schema["required"] + schema["optional"])
    assert set(record.provenance) <= set(RawProvenance.__annotations__)


@pytest.mark.parametrize(
    "change",
    [
        lambda source: (source / "users.json").unlink(),
        lambda source: (source / "users.json").write_text(
            json.dumps({**valid_envelope(), "data": [{"changed": True}]}), encoding="utf-8"
        ),
        lambda source: (source / "extra.json").write_text(
            json.dumps(valid_envelope()), encoding="utf-8"
        ),
    ],
    ids=["missing-file", "modified-checksum", "unexpected-extra-file"],
)
def test_snapshot_integrity_failures_ignore_skip_record(tmp_path, change):
    source, manifest = make_snapshot(tmp_path, ("users.json", valid_envelope()))
    change(source)
    loader = ManifestRawDataLoader(manifest)

    with pytest.raises(ManifestError):
        list(loader.load(source, error_policy=ErrorPolicy.SKIP_RECORD))


@pytest.mark.parametrize(
    "payload",
    [b"{", {"meta": {"type": "users"}, "data": []}, {}],
    ids=["malformed-json", "empty-data", "empty-envelope"],
)
def test_malformed_or_empty_json_envelope_fails_before_first_yield(tmp_path, payload):
    source, manifest = make_snapshot(tmp_path, ("users.json", payload))
    loader = ManifestRawDataLoader(manifest)

    records = loader.load(source, error_policy=ErrorPolicy.SKIP_RECORD)
    with pytest.raises(ManifestError):
        next(records)


@pytest.mark.parametrize(
    "payload",
    [
        {"meta": {"type": "users"}, "extra": True},
        {"data": [{"ObjectIdentifier": "SYNTHETIC-USER"}], "extra": True},
    ],
    ids=["missing-data-with-extra", "missing-meta-with-extra"],
)
def test_missing_required_envelope_key_with_extra_fails_before_yield(tmp_path, payload):
    source, manifest = make_snapshot(tmp_path, ("users.json", payload))
    records = ManifestRawDataLoader(manifest).load(source, error_policy=ErrorPolicy.SKIP_RECORD)

    with pytest.raises(ManifestError):
        next(records)


def test_provenance_never_contains_absolute_source_path(tmp_path):
    source, manifest = make_snapshot(tmp_path, ("nested/users.json", valid_envelope()))
    record = next(ManifestRawDataLoader(manifest).load(source))

    assert record.provenance["raw_file"] == raw_file_reference(manifest, "nested/users.json")
    assert str(source) not in repr(record)
    assert not Path(record.provenance["raw_file"]).is_absolute()


def test_loader_parses_the_bytes_checked_by_manifest(tmp_path, monkeypatch):
    source, manifest = make_snapshot(tmp_path, ("users.json", valid_envelope()))
    original_read_bytes = Path.read_bytes

    def unexpected_path_read(path):
        if path == source / "users.json":
            return b"not the verified bytes"
        return original_read_bytes(path)

    monkeypatch.setattr(Path, "read_bytes", unexpected_path_read)

    records = list(ManifestRawDataLoader(manifest).load(source))

    assert records[0].data == valid_envelope()["data"][0]
    assert snapshot_manifest.read_verified_snapshot_file(
        source, manifest, raw_file_reference(manifest, "users.json")
    ) == original_read_bytes(source / "users.json")


def test_unknown_collection_timestamp_is_fatal_and_never_invented(tmp_path):
    source, manifest = make_snapshot(tmp_path, ("users.json", valid_envelope()), collected_at=None)

    with pytest.raises(ManifestError, match="timestamp"):
        next(ManifestRawDataLoader(manifest).load(source))


def test_all_envelopes_are_preflighted_before_first_record(tmp_path):
    source, manifest = make_snapshot(
        tmp_path,
        ("01-users.json", valid_envelope()),
        ("02-groups.json", b"not-json"),
    )
    loader = ManifestRawDataLoader(manifest)
    records = loader.load(source)

    with pytest.raises(ManifestError, match="02-groups.json"):
        next(records)


def test_loader_rejects_non_json_telemetry_snapshot_and_preserves_invariant(tmp_path):
    source = tmp_path / "telemetry_snapshot"
    source.mkdir()
    (source / "evtx_data.csv").write_text("dummy,csv,data\n", encoding="utf-8")
    manifest = generate_manifest(
        source,
        dataset_id="telemetry-test",
        collector_name="evtx-attack-samples",
        collector_version=None,
        collected_at=None,
    )
    loader = ManifestRawDataLoader(manifest)
    with pytest.raises(ManifestError, match="snapshot contains no JSON export envelopes"):
        next(loader.load(source))


def test_null_collected_at_with_fixed_policy_succeeds_and_marks_assumed(tmp_path):
    source, manifest = make_snapshot(tmp_path, ("users.json", valid_envelope()), collected_at=None)
    policy = TimeProvenancePolicy.fixed("2021-09-20T18:59:58Z", reason="known evaluation baseline")
    loader = ManifestRawDataLoader(manifest, time_policy=policy)

    records = list(loader.load(source))

    assert len(records) == 1
    assert records[0].provenance["timestamp"] == "2021-09-20T18:59:58Z"
    assert records[0].provenance["time_provenance"] == TimeProvenanceStatus.ASSUMED
    assert records[0].provenance["time_provenance"] != TimeProvenanceStatus.OBSERVED
    assert records[0].provenance["time_provenance_reason"] == "known evaluation baseline"
    assert (
        loader.execution_identity["time_policy"]
        == "fixed:assumed:2021-09-20T18:59:58Z:known evaluation baseline"
    )


def test_execution_identity_sensitive_to_policy_parameters(tmp_path):
    source, manifest = make_snapshot(tmp_path, ("users.json", valid_envelope()), collected_at=None)
    policy1 = TimeProvenancePolicy.fixed(
        "2021-01-01T00:00:00Z", status=TimeProvenanceStatus.ASSUMED, reason="run1"
    )
    policy2 = TimeProvenancePolicy.fixed(
        "2022-01-01T00:00:00Z", status=TimeProvenanceStatus.DERIVED, reason="run2"
    )
    loader1 = ManifestRawDataLoader(manifest, time_policy=policy1)
    loader2 = ManifestRawDataLoader(manifest, time_policy=policy2)

    assert loader1.execution_identity["time_policy"] != loader2.execution_identity["time_policy"]
    assert loader1.execution_identity["time_policy"] == "fixed:assumed:2021-01-01T00:00:00Z:run1"
    assert loader2.execution_identity["time_policy"] == "fixed:derived:2022-01-01T00:00:00Z:run2"


@pytest.mark.parametrize(
    "bad_status",
    [
        TimeProvenanceStatus.OBSERVED,
        "observed",
        "Observed",
        "OBSERVED",
        " observed ",
        "  oBseRved  ",
    ],
)
def test_policy_cannot_masquerade_as_observed(bad_status):
    with pytest.raises(ValueError, match="masquerade"):
        TimeProvenancePolicy.fixed("2021-09-20T18:59:58Z", status=bad_status)


def test_unsupported_status_string_rejected():
    with pytest.raises(ValueError, match="unsupported time provenance status"):
        TimeProvenancePolicy.fixed("2021-09-20T18:59:58Z", status="arbitrary_unapproved")  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "status",
    [
        TimeProvenanceStatus.EXTERNALLY_EVIDENCED,
        TimeProvenanceStatus.DERIVED,
        "externally_evidenced",
        "derived",
    ],
)
@pytest.mark.parametrize("empty_reason", [None, "", "   "])
def test_stronger_statuses_require_non_empty_reason(status, empty_reason):
    with pytest.raises(ValueError, match="requires a non-empty reason or evidence reference"):
        TimeProvenancePolicy.fixed("2021-09-20T18:59:58Z", status=status, reason=empty_reason)


def test_dedicated_factories_for_stronger_statuses():
    ev_policy = TimeProvenancePolicy.externally_evidenced(
        "2021-09-20T18:59:58Z", reason="dc_event_log_4624"
    )
    assert ev_policy.status == TimeProvenanceStatus.EXTERNALLY_EVIDENCED
    assert ev_policy.reason == "dc_event_log_4624"
    assert (
        ev_policy.identity_token
        == "fixed:externally_evidenced:2021-09-20T18:59:58Z:dc_event_log_4624"
    )

    der_policy = TimeProvenancePolicy.derived(
        "2021-09-20T18:59:58Z", reason="correlated_activity_baseline"
    )
    assert der_policy.status == TimeProvenanceStatus.DERIVED
    assert der_policy.reason == "correlated_activity_baseline"
    assert (
        der_policy.identity_token
        == "fixed:derived:2021-09-20T18:59:58Z:correlated_activity_baseline"
    )


def test_time_provenance_status_literal_matches_enum():
    assert set(get_args(TimeProvenanceStatusLiteral)) == {s.value for s in TimeProvenanceStatus}


def test_invalid_time_policy_type_raises_type_error(tmp_path):
    source, manifest = make_snapshot(tmp_path, ("users.json", valid_envelope()))
    with pytest.raises(TypeError, match="time_policy must be a TimeProvenancePolicy or None"):
        ManifestRawDataLoader(manifest, time_policy="not-a-policy")  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "bad_syntax",
    [
        "not-a-timestamp",
        "2021-09-20",
        "2021/09/20 18:59:58",
        "2021-09-20T18:59:58",
        "2021-09-20 18:59:58Z",
    ],
)
def test_malformed_timestamp_syntax_raises_value_error(bad_syntax):
    with pytest.raises(ValueError, match="format"):
        TimeProvenancePolicy.fixed(bad_syntax)


@pytest.mark.parametrize(
    "impossible_date",
    [
        "2021-02-30T25:99:99Z",
        "2021-02-29T12:00:00Z",  # 2021 is not a leap year
        "2021-04-31T00:00:00Z",  # April has 30 days
        "2021-13-01T00:00:00Z",  # Month 13
        "2021-01-32T00:00:00Z",  # Day 32
        "2021-01-01T24:00:00Z",  # Hour 24
        "2021-01-01T23:60:00Z",  # Minute 60
        "2021-01-01T23:59:60Z",  # Second 60
    ],
)
def test_syntactically_valid_but_impossible_calendar_timestamp_raises_value_error(impossible_date):
    with pytest.raises(ValueError, match="calendar"):
        TimeProvenancePolicy.fixed(impossible_date)


def test_malformed_timestamp_in_manifest_raises_manifest_error(tmp_path):
    source, manifest = make_snapshot(tmp_path, ("users.json", valid_envelope()))
    manifest["collected_at"] = "invalid-date"
    loader = ManifestRawDataLoader(manifest)
    with pytest.raises(ManifestError, match="collected_at"):
        next(loader.load(source))


def test_impossible_calendar_timestamp_in_manifest_raises_manifest_error(tmp_path):
    source, manifest = make_snapshot(tmp_path, ("users.json", valid_envelope()))
    manifest["collected_at"] = "2021-02-30T12:00:00Z"
    loader = ManifestRawDataLoader(manifest)
    with pytest.raises(ManifestError, match="collected_at"):
        next(loader.load(source))


def test_time_policy_is_deterministic(tmp_path):
    source, manifest = make_snapshot(tmp_path, ("users.json", valid_envelope()), collected_at=None)
    policy = TimeProvenancePolicy.fixed(
        "2021-09-20T18:59:58Z", status=TimeProvenanceStatus.ASSUMED, reason="test_det"
    )
    loader = ManifestRawDataLoader(manifest, time_policy=policy)

    first_run = [r.provenance for r in loader.load(source)]
    second_run = [r.provenance for r in loader.load(source)]

    assert first_run == second_run
    assert len(first_run) == 1


def test_bloodhound_v3_envelope_support_and_bom_tolerance(tmp_path):
    v3_envelope = {
        "meta": {"type": "computers", "count": 1, "version": 3},
        "computers": [{"ObjectIdentifier": "S-1-5-21-COMP-1", "Properties": {"name": "DC1"}}],
    }
    bom_payload = b"\xef\xbb\xbf" + json.dumps(v3_envelope).encode("utf-8")
    source, manifest = make_snapshot(
        tmp_path, ("20210920185958_computers.json", bom_payload), collected_at=None
    )
    policy = TimeProvenancePolicy.fixed("2021-09-20T18:59:58Z", status=TimeProvenanceStatus.ASSUMED)
    loader = ManifestRawDataLoader(manifest, time_policy=policy)

    records = list(loader.load(source))

    assert len(records) == 1
    assert records[0].kind == "computers"
    assert records[0].provenance["record_locator"] == "#/computers/0"
    assert records[0].provenance["record_id"] == "S-1-5-21-COMP-1"
    assert records[0].provenance["timestamp"] == "2021-09-20T18:59:58Z"
    assert records[0].provenance["time_provenance"] == TimeProvenanceStatus.ASSUMED


def test_seamless_snapshot_fails_closed_without_policy():
    source_path = Path("data/raw/SEAMLESS")
    if not source_path.exists():
        pytest.skip("Local SEAMLESS raw directory not present")
    manifest_path = Path("data/samples/manifests/seamless-raw-v1.json")
    manifest = snapshot_manifest.load_manifest(manifest_path)
    loader = ManifestRawDataLoader(manifest)

    with pytest.raises(ManifestError, match="missing collection timestamp"):
        next(loader.load(source_path))


def test_seamless_snapshot_manifest_to_raw_loader_integration_with_explicit_policy():
    """Verify manifest-to-loader integration for SEAMLESS using an explicit fixed policy."""
    source_path = Path("data/raw/SEAMLESS")
    if not source_path.exists():
        pytest.skip("Local SEAMLESS raw directory not present")
    manifest_path = Path("data/samples/manifests/seamless-raw-v1.json")
    manifest = snapshot_manifest.load_manifest(manifest_path)
    loader = ManifestRawDataLoader(
        manifest,
        time_policy=TimeProvenancePolicy.fixed(
            "2021-09-20T18:59:58Z",
            status=TimeProvenanceStatus.ASSUMED,
            reason="seamless_synthetic_baseline",
        ),
    )

    records = list(loader.load(source_path))

    assert len(records) == 3369
    kinds = {r.kind for r in records}
    assert kinds == {"computers", "domains", "gpos", "groups", "ous", "users"}
    assert all(r.provenance["timestamp"] == "2021-09-20T18:59:58Z" for r in records)
    assert all(r.provenance["time_provenance"] == TimeProvenanceStatus.ASSUMED for r in records)
    assert (
        loader.execution_identity["time_policy"]
        == "fixed:assumed:2021-09-20T18:59:58Z:seamless_synthetic_baseline"
    )
