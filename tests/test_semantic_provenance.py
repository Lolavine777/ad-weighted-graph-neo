"""Issue #81 contracts for semantic evidence and observed telemetry provenance."""

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
import yaml

from scripts.check_contract import validate_graph
from src.data.manifest import generate_manifest, raw_file_reference
from src.engine.semantics import (
    ConfirmationBasis,
    CorrelationRecord,
    EvidenceContext,
    ObservedActivity,
    StructuralRelationship,
    TelemetryRecordLocator,
    TelemetryRecordRef,
    confirm_candidate,
    correlate_candidate,
    load_catalog,
    validate_telemetry_record_ref,
)

ROOT = Path(__file__).resolve().parents[1]


def telemetry_ref(source: Path, manifest: dict, row: int = 1) -> TelemetryRecordRef:
    return TelemetryRecordRef.from_manifest(
        manifest,
        "evtx_data.csv",
        TelemetryRecordLocator("csv_row", row),
        source=source,
    )


@pytest.fixture
def telemetry_snapshot(tmp_path: Path) -> tuple[Path, dict]:
    source = tmp_path / "telemetry"
    source.mkdir()
    (source / "evtx_data.csv").write_text(
        "EventID,Actor,Target\n4724,alice,target\n5136,alice,target\n",
        encoding="utf-8",
    )
    (source / "collector.json").write_text('{"collector":"synthetic"}\n', encoding="utf-8")
    manifest = generate_manifest(
        source,
        dataset_id="telemetry-test",
        collector_name="synthetic-telemetry",
        collector_version="1",
        collected_at="2026-09-21T00:00:00Z",
    )
    return source, manifest


@pytest.fixture
def catalog_document() -> dict:
    return yaml.safe_load((ROOT / "configs/attack_semantics.yml").read_text(encoding="utf-8"))


def test_normative_expected_telemetry_has_mapping_evidence_but_memberof_has_none():
    catalog = load_catalog()
    assert all(
        event.evidence_refs
        for technique in catalog
        if technique.expected_telemetry
        for event in technique.expected_telemetry
    )
    assert not next(t for t in catalog if t.relationship == "MemberOf").expected_telemetry


@pytest.mark.parametrize(
    "mutation",
    [
        lambda data: data["evidence_registry"].pop("ms-security-4724"),
        lambda data: data["techniques"][2]["expected_telemetry"][0]["evidence_refs"].append(
            "missing-evidence"
        ),
        lambda data: data["evidence_registry"]["ms-security-4724"].update(confidence="certain"),
    ],
)
def test_invalid_semantic_evidence_fails_catalog_validation(catalog_document, mutation):
    from src.engine.semantics import validate_catalog

    mutation(catalog_document)
    with pytest.raises(ValueError):
        validate_catalog(catalog_document)


def test_old_catalog_version_is_not_silently_interpreted(catalog_document):
    from src.engine.semantics import validate_catalog

    catalog_document["version"] = "0.1"
    with pytest.raises(ValueError, match="migrate to 0.5"):
        validate_catalog(catalog_document)


def test_observed_activity_resolves_manifest_file_and_record_locator(telemetry_snapshot):
    source, telemetry_manifest = telemetry_snapshot
    reference = telemetry_ref(source, telemetry_manifest, row=2)
    activity = ObservedActivity(
        "evtx-lab",
        "event-sids",
        datetime(2026, 9, 21, tzinfo=UTC),
        "alice",
        "target",
        "Microsoft-Windows-Security-Auditing",
        4724,
        reference,
    )
    validate_telemetry_record_ref(activity.provenance, telemetry_manifest, source=source)
    assert activity.provenance.raw_file == raw_file_reference(telemetry_manifest, "evtx_data.csv")
    assert activity.provenance.record_locator == TelemetryRecordLocator("csv_row", 2)


def test_observed_activity_rejects_missing_or_fake_provenance(telemetry_snapshot):
    source, telemetry_manifest = telemetry_snapshot
    with pytest.raises(TypeError):
        ObservedActivity(
            "evtx-lab",
            "event-sids",
            datetime(2026, 9, 21, tzinfo=UTC),
            "alice",
            "target",
            "Security",
            4724,
        )
    reference = telemetry_ref(source, telemetry_manifest)
    with pytest.raises(ValueError, match="does not match manifest"):
        validate_telemetry_record_ref(
            reference,
            {**telemetry_manifest, "dataset_id": "other-dataset"},
            source=source,
        )
    with pytest.raises(ValueError):
        TelemetryRecordLocator("content_hash", "generated")
    with pytest.raises(ValueError):
        ObservedActivity(
            "evtx-lab",
            "event-sids",
            datetime(2026, 9, 21, tzinfo=UTC),
            "alice",
            "target",
            "Security",
            4724,
            TelemetryRecordRef(
                "telemetry-raw-v1",
                telemetry_manifest["snapshot_id"],
                reference.raw_file,
                TelemetryRecordLocator("csv_row", 1),
            ),
        )
    with pytest.raises(ValueError, match="outside"):
        TelemetryRecordRef.from_manifest(
            telemetry_manifest,
            "evtx_data.csv",
            TelemetryRecordLocator("csv_row", 999999),
            source=source,
        )
    with pytest.raises(ValueError, match="unique verified record"):
        TelemetryRecordRef.from_manifest(
            telemetry_manifest,
            "evtx_data.csv",
            TelemetryRecordLocator("content_hash", "0" * 64),
            source=source,
        )
    with pytest.raises(ValueError):
        TelemetryRecordRef(
            "telemetry-raw-v1",
            telemetry_manifest["snapshot_id"],
            "unknown",
            TelemetryRecordLocator("csv_row", 1),
        )


def test_observed_activity_rejects_a_changed_whole_snapshot(telemetry_snapshot):
    source, telemetry_manifest = telemetry_snapshot
    (source / "collector.json").write_text('{"collector":"changed"}\n', encoding="utf-8")
    with pytest.raises(ValueError, match="snapshot differs"):
        telemetry_ref(source, telemetry_manifest)


def test_full_telemetry_provenance_cannot_be_attached_to_structural_edge():
    contract = yaml.safe_load((ROOT / "configs/contract.yml").read_text(encoding="utf-8"))
    graph = json.loads((ROOT / "data/samples/toy-graph.json").read_text(encoding="utf-8"))
    edge = graph["edges"][0]
    edge["provenance"][0].update(
        dataset_id="telemetry-raw-v1",
        snapshot_id="sha256:" + "0" * 64,
        record_locator={"kind": "csv_row", "row": 1},
    )
    with pytest.raises(ValueError, match="unsupported fields"):
        validate_graph(graph, contract)


def test_candidate_correlation_is_not_confirmation(telemetry_snapshot):
    source, telemetry_manifest = telemetry_snapshot
    activity = ObservedActivity(
        "lab-a",
        "event-sids",
        datetime(2026, 9, 21, tzinfo=UTC),
        "alice",
        "target",
        "Security",
        4724,
        telemetry_ref(source, telemetry_manifest),
    )
    context = EvidenceContext(
        "lab-a", "event-sids", datetime(2026, 9, 21, tzinfo=UTC), datetime(2026, 9, 22, tzinfo=UTC)
    )
    correlation = correlate_candidate(
        activity,
        context,
        "reset_target_password",
        StructuralRelationship("alice", "ForceChangePassword", "target"),
    )
    assert correlation.status == "candidate"
    assert not hasattr(correlation, "confirmed_attack")
    confirmed = confirm_candidate(
        correlation,
        ConfirmationBasis("independent_evidence", "case-1", "separate corroborating evidence"),
    )
    assert confirmed.confirmation.kind == "independent_evidence"


def test_public_candidate_record_cannot_bypass_correlation_invariants(telemetry_snapshot):
    source, telemetry_manifest = telemetry_snapshot
    activity = ObservedActivity(
        "lab-a",
        "event-sids",
        datetime(2026, 9, 21, tzinfo=UTC),
        "alice",
        "target",
        "Security",
        4724,
        telemetry_ref(source, telemetry_manifest),
    )
    context = EvidenceContext(
        "lab-a", "event-sids", datetime(2026, 9, 21, tzinfo=UTC), datetime(2026, 9, 22, tzinfo=UTC)
    )
    with pytest.raises(ValueError, match="unknown technique"):
        CorrelationRecord(
            "not-a-technique",
            StructuralRelationship("alice", "ForceChangePassword", "target"),
            activity,
            context,
            "candidate",
            "fabricated candidate",
        )
    with pytest.raises(ValueError, match="context"):
        CorrelationRecord(
            "reset_target_password",
            StructuralRelationship("alice", "ForceChangePassword", "target"),
            activity,
            EvidenceContext(
                "other-lab",
                "event-sids",
                datetime(2026, 9, 21, tzinfo=UTC),
                datetime(2026, 9, 22, tzinfo=UTC),
            ),
            "candidate",
            "fabricated candidate",
        )
    with pytest.raises(ValueError, match="unknown technique"):
        CorrelationRecord(
            "not-a-technique",
            StructuralRelationship("alice", "ForceChangePassword", "target"),
            activity,
            context,
            "rejected",
            "fabricated rejection",
        )
    with pytest.raises(ValueError, match="does not match"):
        CorrelationRecord(
            "reset_target_password",
            StructuralRelationship("alice", "CanRDP", "target"),
            activity,
            context,
            "rejected",
            "fabricated rejection",
        )
    with pytest.raises(ValueError, match="context"):
        CorrelationRecord(
            "reset_target_password",
            StructuralRelationship("alice", "ForceChangePassword", "target"),
            activity,
            EvidenceContext(
                "other-lab",
                "event-sids",
                datetime(2026, 9, 21, tzinfo=UTC),
                datetime(2026, 9, 22, tzinfo=UTC),
            ),
            "rejected",
            "fabricated rejection",
        )
    with pytest.raises(ValueError, match="must be candidate"):
        CorrelationRecord(
            "reset_target_password",
            StructuralRelationship("alice", "ForceChangePassword", "target"),
            activity,
            context,
            "rejected",
            "matching activity mislabeled as rejected",
        )

    rejected_activity = ObservedActivity(
        "lab-a",
        "event-sids",
        datetime(2026, 9, 21, tzinfo=UTC),
        "bob",
        "target",
        "Security",
        4724,
        telemetry_ref(source, telemetry_manifest, row=2),
    )
    rejected = CorrelationRecord(
        "reset_target_password",
        StructuralRelationship("alice", "ForceChangePassword", "target"),
        rejected_activity,
        context,
        "rejected",
        "activity actor does not match the structural relationship",
    )
    assert rejected.status == "rejected"


def test_correlation_requires_known_compatible_technique(telemetry_snapshot):
    source, telemetry_manifest = telemetry_snapshot
    activity = ObservedActivity(
        "lab-a",
        "event-sids",
        datetime(2026, 9, 21, tzinfo=UTC),
        "alice",
        "target",
        "Security",
        4724,
        telemetry_ref(source, telemetry_manifest),
    )
    context = EvidenceContext(
        "lab-a", "event-sids", datetime(2026, 9, 21, tzinfo=UTC), datetime(2026, 9, 22, tzinfo=UTC)
    )
    with pytest.raises(ValueError, match="unknown technique"):
        correlate_candidate(
            activity,
            context,
            "not-a-technique",
            StructuralRelationship("alice", "ForceChangePassword", "target"),
        )
    with pytest.raises(ValueError, match="does not match"):
        correlate_candidate(
            activity,
            context,
            "reset_target_password",
            StructuralRelationship("alice", "CanRDP", "target"),
        )


def test_catalog_mapping_evidence_is_not_observed_corpus_evidence(catalog_document):
    entry = catalog_document["evidence_registry"]["ms-security-4724"]
    assert entry["type"] != "corpus_observed_availability"
    assert entry["type"] == "authoritative_reference"


def test_group_membership_mapping_covers_all_declared_event_families(catalog_document):
    entry = next(
        technique
        for technique in catalog_document["techniques"]
        if technique["id"] == "genericall_add_member"
    )
    assert set(entry["expected_telemetry"][0]["evidence_refs"]) == {
        "ms-security-4728",
        "ms-security-group-membership",
        "ms-security-4756",
    }
    registry = catalog_document["evidence_registry"]
    group_management_locator = (
        "https://learn.microsoft.com/en-us/windows-server/identity/ad-ds/plan/"
        "security-best-practices/advanced-audit-policy-configuration"
    )
    assert {registry[ref]["locator"] for ref in ("ms-security-4728", "ms-security-4756")} == {
        group_management_locator
    }
