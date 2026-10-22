from __future__ import annotations

from copy import deepcopy

import pytest

from src.parser import (
    RawRecord,
    ReconciliationConflictError,
    RepresentationKind,
    reconcile_raw_records,
)
from src.parser.normalizer import Normalizer

SNAPSHOT = "sha256:synthetic"


def _record(
    data: dict,
    *,
    record_locator: str,
    raw_file: str = f"snapshot:{SNAPSHOT}/groups.json",
    snapshot_id: str = SNAPSHOT,
) -> RawRecord:
    return RawRecord(
        kind="Group",
        data=data,
        provenance={
            "raw_file": raw_file,
            "collector": "sharphound/3.0",
            "timestamp": "2026-09-21T00:00:00Z",
            "snapshot_id": snapshot_id,
            "record_locator": record_locator,
            "record_id": str(data.get("ObjectIdentifier", "missing")),
        },
    )


@pytest.fixture
def duplicate_representations() -> tuple[RawRecord, RawRecord]:
    # Both occurrences intentionally come from the same envelope and have the
    # same logical record_id. The locator is the only occurrence-level key.
    full = _record(
        {
            "ObjectIdentifier": "NORTH.LOCAL-S-1-5-32-568",
            "Properties": {
                "name": "Account Operators@NORTH.LOCAL",
                "domain": "NORTH.LOCAL",
            },
            "Members": [{"ObjectIdentifier": "S-1-5-21-100-101-102-1100", "ObjectType": "User"}],
            "Aces": [
                {
                    "PrincipalSID": "S-1-5-21-100-101-102-512",
                    "PrincipalType": "Group",
                    "RightName": "GenericAll",
                }
            ],
            "IsDeleted": False,
        },
        record_locator="#/data/0",
    )
    supplemental = _record(
        {
            "ObjectIdentifier": "NORTH.LOCAL-S-1-5-32-568",
            "Properties": {},
            "Members": [],
            "Aces": [],
            "reconcile": False,
        },
        record_locator="#/data/1",
    )
    return full, supplemental


def test_same_file_occurrences_are_individually_traceable(duplicate_representations):
    logical = reconcile_raw_records(duplicate_representations)[0]

    assert logical.raw_occurrence_count == 2
    assert [item.provenance["record_locator"] for item in logical.representations] == [
        "#/data/0",
        "#/data/1",
    ]
    first_file = logical.representations[0].provenance["raw_file"]
    second_file = logical.representations[1].provenance["raw_file"]
    assert first_file == second_file


def test_full_and_supplemental_records_reconcile_without_losing_evidence(
    duplicate_representations,
):
    logical = reconcile_raw_records(duplicate_representations)[0]

    assert logical.logical_key == ("Group", "north.local-s-1-5-32-568")
    assert logical.data["Properties"]["name"] == "Account Operators@NORTH.LOCAL"
    assert len(logical.data["Members"]) == 1
    assert len(logical.data["Aces"]) == 1
    assert [item.kind for item in logical.representations] == [
        RepresentationKind.FULL,
        RepresentationKind.SUPPLEMENTAL,
    ]
    member_lineage = next(line for line in logical.evidence_lineage if line.field == "Members")
    ace_lineage = next(line for line in logical.evidence_lineage if line.field == "Aces")
    assert {source["record_locator"] for source in member_lineage.provenance} == {"#/data/0"}
    assert {source["record_locator"] for source in ace_lineage.provenance} == {"#/data/0"}
    assert "reconcile" not in logical.data
    assert logical.duplicate_cause == "verified_supplemental"


def test_reconciliation_is_order_invariant_and_does_not_mutate_raw_records(
    duplicate_representations,
):
    before = [deepcopy(record.data) for record in duplicate_representations]
    forward = reconcile_raw_records(duplicate_representations)[0]
    reverse = reconcile_raw_records(reversed(duplicate_representations))[0]

    assert forward.data == reverse.data
    assert forward.logical_key == reverse.logical_key
    assert forward.provenance == reverse.provenance
    assert [record.data for record in duplicate_representations] == before


def test_supported_identifier_aliases_reconcile_before_normalization():
    first = _record(
        {
            "objectid": "S-1-5-21-1000-2000-3000-1200",
            "name": "Alias Group",
            "domain": "EXAMPLE.TEST",
            "Members": ["member-a"],
        },
        record_locator="#/data/0",
    )
    second = _record(
        {
            "ObjectId": "S-1-5-21-1000-2000-3000-1200",
            "domain": "EXAMPLE.TEST",
            "Members": ["member-b"],
        },
        record_locator="#/data/1",
    )

    reconciled = reconcile_raw_records([second, first])
    normalized = Normalizer().normalize_records([second, first])

    assert len(reconciled) == 1
    assert reconciled[0].data["Members"] == ["member-a", "member-b"]
    assert len(normalized) == 1
    assert normalized[0].id == "S-1-5-21-1000-2000-3000-1200"
    assert normalized[0].raw.data["Members"] == ["member-a", "member-b"]
    assert Normalizer().normalize_records([first, second]) == normalized


def test_non_empty_scalar_conflict_is_reported_instead_of_selected():
    first = _record(
        {"ObjectIdentifier": "G-CONFLICT", "Properties": {"name": "FIRST"}},
        record_locator="#/data/0",
    )
    second = _record(
        {"ObjectIdentifier": "G-CONFLICT", "Properties": {"name": "SECOND"}},
        record_locator="#/data/1",
    )

    with pytest.raises(
        ReconciliationConflictError,
        match="conflicting non-empty values for Properties.name",
    ):
        reconcile_raw_records([first, second])


def nested_default_stub(duplicate_representations):
    full, supplemental = duplicate_representations
    first, second = deepcopy(full.data), deepcopy(supplemental.data)
    first["IsACLProtected"] = True
    second.pop("reconcile")
    second.update(IsDeleted=False, IsACLProtected=False, ContainedBy=None)
    second["Properties"] = {**first["Properties"], "reconcile": False}
    return (
        _record(first, record_locator="#/data/0"),
        _record(second, record_locator="#/data/1"),
    )


def test_generated_group_default_does_not_override_full_acl_observation(duplicate_representations):
    full, stub = nested_default_stub(duplicate_representations)
    logical = reconcile_raw_records([full, stub])[0]
    assert logical.data["IsACLProtected"] is True
    assert logical.data["Members"] == full.data["Members"]
    assert logical.data["Aces"] == full.data["Aces"]
    assert logical.representations[1].kind is RepresentationKind.SUPPLEMENTAL
    assert logical.representations[1].record.data["IsACLProtected"] is False
    assert reconcile_raw_records([stub, full])[0] == logical


@pytest.mark.parametrize("change", ["missing_marker", "members", "extra_fact", "other_file"])
def test_acl_disagreement_requires_the_explicit_same_file_default_shape(
    duplicate_representations, change
):
    full, stub = nested_default_stub(duplicate_representations)
    data, raw_file = deepcopy(stub.data), stub.provenance["raw_file"]
    if change == "missing_marker":
        data["Properties"].pop("reconcile")
    elif change == "members":
        data["Members"] = full.data["Members"]
    elif change == "extra_fact":
        data["Properties"]["enabled"] = False
    else:
        raw_file += ".other"
    changed = _record(data, record_locator="#/data/1", raw_file=raw_file)
    with pytest.raises(ReconciliationConflictError, match="IsACLProtected"):
        reconcile_raw_records([full, changed])


def test_unknown_list_fields_do_not_gain_union_semantics():
    first = _record(
        {"ObjectIdentifier": "G-LIST", "UnknownValues": ["first"]},
        record_locator="#/data/0",
    )
    second = _record(
        {"ObjectIdentifier": "G-LIST", "UnknownValues": ["second"]},
        record_locator="#/data/1",
    )

    with pytest.raises(
        ReconciliationConflictError,
        match="conflicting non-empty values for UnknownValues",
    ):
        reconcile_raw_records([first, second])


def test_mixed_snapshot_input_is_rejected_before_merge():
    first = _record({"ObjectIdentifier": "G-MIXED"}, record_locator="#/data/0")
    second = _record(
        {"ObjectIdentifier": "G-MIXED"},
        record_locator="#/data/0",
        raw_file="snapshot:sha256:other/groups.json",
        snapshot_id="sha256:other",
    )

    with pytest.raises(ReconciliationConflictError, match="multiple snapshots"):
        reconcile_raw_records([first, second])


def test_partially_identified_snapshot_input_is_rejected():
    identified = _record({"ObjectIdentifier": "G-PARTIAL"}, record_locator="#/data/0")
    unidentified = _record(
        {"ObjectIdentifier": "G-PARTIAL"},
        record_locator="#/data/1",
        raw_file="groups.json",
        snapshot_id=None,
    )

    with pytest.raises(ReconciliationConflictError, match="missing from part"):
        reconcile_raw_records([identified, unidentified])


def test_multiple_records_without_snapshot_identity_fail_closed():
    first = _record(
        {"ObjectIdentifier": "G-NO-SNAPSHOT"},
        record_locator="#/data/0",
        raw_file="groups.json",
        snapshot_id=None,
    )
    second = _record(
        {"ObjectIdentifier": "G-NO-SNAPSHOT"},
        record_locator="#/data/1",
        raw_file="groups.json",
        snapshot_id=None,
    )

    with pytest.raises(ReconciliationConflictError, match="required to reconcile"):
        reconcile_raw_records([first, second])


def test_single_record_without_snapshot_identity_remains_processable():
    record = _record(
        {"ObjectIdentifier": "G-SINGLE"},
        record_locator="#/data/0",
        raw_file="groups.json",
        snapshot_id=None,
    )

    result = reconcile_raw_records([record])

    assert len(result) == 1
    assert result[0].logical_key == ("Group", "g-single")


def test_explicit_snapshot_boundary_allows_unidentified_records():
    first = _record(
        {"ObjectIdentifier": "G-EXPLICIT", "Members": ["member-a"]},
        record_locator="#/data/0",
        raw_file="groups.json",
        snapshot_id=None,
    )
    second = _record(
        {"ObjectIdentifier": "G-EXPLICIT", "Members": ["member-b"]},
        record_locator="#/data/1",
        raw_file="groups.json",
        snapshot_id=None,
    )

    result = reconcile_raw_records([first, second], snapshot_id=SNAPSHOT)

    assert len(result) == 1
    assert result[0].data["Members"] == ["member-a", "member-b"]


def test_explicit_snapshot_boundary_rejects_mismatched_records():
    record = _record(
        {"ObjectIdentifier": "G-WRONG-SNAPSHOT"},
        record_locator="#/data/0",
        raw_file="snapshot:sha256:other/groups.json",
        snapshot_id="sha256:other",
    )

    with pytest.raises(ReconciliationConflictError, match="requested snapshot"):
        reconcile_raw_records([record], snapshot_id=SNAPSHOT)


def test_reconcile_false_is_unknown_without_the_verified_dataset_shape():
    full = _record(
        {
            "ObjectIdentifier": "G-UNKNOWN-CAUSE",
            "Properties": {"name": "Group"},
            "Members": ["member-a"],
            "Aces": [{"RightName": "GenericAll"}],
        },
        record_locator="#/data/0",
    )
    supplemental = _record(
        {
            "ObjectIdentifier": "G-UNKNOWN-CAUSE",
            "domain": "EXAMPLE.TEST",
            "reconcile": False,
        },
        record_locator="#/data/1",
    )

    result = reconcile_raw_records([full, supplemental])

    assert result[0].duplicate_cause == "unknown"


@pytest.mark.parametrize("scope_key", ["scope_guid", "host_guid"])
def test_same_local_sid_is_grouped_only_with_matching_stable_scope(scope_key):
    first = _record(
        {"ObjectIdentifier": "S-1-5-32-544", scope_key: "00000000-0000-4000-8000-000000000001"},
        record_locator="#/data/0",
    )
    second = _record(
        {"ObjectIdentifier": "S-1-5-32-544", scope_key: "00000000-0000-4000-8000-000000000002"},
        record_locator="#/data/1",
    )

    result = reconcile_raw_records([first, second])

    assert len(result) == 2
    assert {item.logical_key for item in result} == {
        ("Group", "s-1-5-32-544", "scope:00000000-0000-4000-8000-000000000001"),
        ("Group", "s-1-5-32-544", "scope:00000000-0000-4000-8000-000000000002"),
    }


def test_unscoped_local_sid_is_not_irreversibly_grouped():
    first = _record({"ObjectIdentifier": "S-1-5-32-544"}, record_locator="#/data/0")
    second = _record({"ObjectIdentifier": "S-1-5-32-544"}, record_locator="#/data/1")

    result = reconcile_raw_records([first, second])

    assert len(result) == 2
    assert all(item.logical_key is None for item in result)


def test_records_without_identity_are_not_grouped():
    first = _record({"Properties": {"name": "A"}}, record_locator="#/data/0")
    second = _record({"Properties": {"name": "B"}}, record_locator="#/data/1")

    result = reconcile_raw_records([first, second])

    assert len(result) == 2
    assert all(item.logical_key is None for item in result)


def test_primary_group_sid_reconciles_cleanly():
    first = _record(
        {
            "ObjectIdentifier": "S-1-5-21-100-200-300-1001",
            "PrimaryGroupSid": "S-1-5-21-100-200-300-513",
        },
        record_locator="#/data/0",
    )
    second = _record(
        {
            "ObjectIdentifier": "S-1-5-21-100-200-300-1001",
            "PrimaryGroupSid": "S-1-5-21-100-200-300-513",
        },
        record_locator="#/data/1",
    )
    result = reconcile_raw_records([first, second])
    assert len(result) == 1
    assert result[0].data["PrimaryGroupSid"] == "S-1-5-21-100-200-300-513"


def test_primary_group_sid_merges_with_empty_or_none():
    first = _record(
        {
            "ObjectIdentifier": "S-1-5-21-100-200-300-1001",
            "PrimaryGroupSid": "S-1-5-21-100-200-300-513",
        },
        record_locator="#/data/0",
    )
    second = _record(
        {"ObjectIdentifier": "S-1-5-21-100-200-300-1001", "PrimaryGroupSid": None},
        record_locator="#/data/1",
    )
    result = reconcile_raw_records([first, second])
    assert len(result) == 1
    assert result[0].data["PrimaryGroupSid"] == "S-1-5-21-100-200-300-513"


def test_primary_group_sid_conflicts_raise_reconciliation_conflict_error():
    first = _record(
        {
            "ObjectIdentifier": "S-1-5-21-100-200-300-1001",
            "PrimaryGroupSid": "S-1-5-21-100-200-300-513",
        },
        record_locator="#/data/0",
    )
    second = _record(
        {
            "ObjectIdentifier": "S-1-5-21-100-200-300-1001",
            "PrimaryGroupSid": "S-1-5-21-100-200-300-512",
        },
        record_locator="#/data/1",
    )
    with pytest.raises(
        ReconciliationConflictError, match="conflicting non-empty values for PrimaryGroupSid"
    ):
        reconcile_raw_records([first, second])
