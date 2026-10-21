"""Synthetic-fixture tests for the manifest-backed SEAMLESS raw auditor."""

from __future__ import annotations

import json
from pathlib import Path

from scripts.audit_seamless_raw import audit_snapshot, write_report
from src.data.manifest import generate_manifest, write_manifest


def _write_envelope(root: Path, suffix: str, records: list[dict]) -> None:
    key = suffix.removesuffix(".json").split("_")[-1]
    (root / f"20210920185958_{key}.json").write_text(
        json.dumps({"meta": {"count": len(records), "type": key, "version": 3}, key: records}),
        encoding="utf-8",
    )


def _fixture(tmp_path: Path) -> tuple[Path, Path]:
    raw = tmp_path / "raw"
    raw.mkdir()
    user_id = "S-1-5-21-<fixture>-1001"
    group_id = "S-1-5-21-<fixture>-2001"
    _write_envelope(
        raw,
        "users.json",
        [
            {
                "ObjectIdentifier": user_id,
                "Properties": {
                    "name": "SYNTHETIC_USER_SHOULD_NOT_APPEAR",
                    "mixed": True,
                    "description": "SYNTHETIC_SECRET_SHOULD_NOT_APPEAR",
                    "optional": "present-on-one-record",
                },
                "Aces": [],
            },
            {
                "ObjectIdentifier": "S-1-5-21-<fixture>-1002",
                "Properties": {"name": "ANOTHER_SYNTHETIC_USER", "mixed": "text"},
                "Aces": [],
            },
            {
                "ObjectIdentifier": "S-1-5-21-<fixture>-1003",
                "Properties": {"name": "THIRD_SYNTHETIC_USER", "mixed": 7},
                "Aces": [],
            },
        ],
    )
    _write_envelope(
        raw,
        "groups.json",
        [
            {
                "ObjectIdentifier": group_id,
                "Properties": {"name": "SYNTHETIC_GROUP"},
                "Members": [
                    {"MemberId": user_id, "MemberType": "User"},
                    {"MemberId": "S-1-5-21-<fixture>-9999", "MemberType": "User"},
                ],
            },
            {"ObjectIdentifier": group_id, "Properties": {}, "Members": []},
        ],
    )
    _write_envelope(
        raw,
        "computers.json",
        [
            {
                "ObjectIdentifier": "S-1-5-21-<fixture>-3001",
                "Properties": {"name": "SYNTHETIC_COMPUTER"},
                "LocalAdmins": [],
                "Sessions": None,
                "PSRemoteUsers": [{"MemberId": user_id, "MemberType": "User"}],
                # RemoteDesktopUsers is deliberately missing.
            },
            {
                "ObjectIdentifier": "S-1-5-21-<fixture>-3002",
                "Properties": {"name": "SYNTHETIC_COMPUTER_TWO"},
                "LocalAdmins": [{"MemberId": user_id, "MemberType": "User"}],
                "Sessions": [],
                "PSRemoteUsers": [],
                "RemoteDesktopUsers": [{"MemberId": user_id, "MemberType": "User"}],
            },
        ],
    )
    _write_envelope(
        raw,
        "ous.json",
        [
            {
                "ObjectIdentifier": "GUID-OU",
                "Properties": {"name": "SYNTHETIC_OU"},
                "Users": [user_id],
                "ChildOus": [],
            }
        ],
    )
    _write_envelope(
        raw,
        "gpos.json",
        [
            {
                "ObjectIdentifier": "GUID-GPO",
                "Properties": {"name": "SYNTHETIC_GPO"},
                "Aces": [
                    {
                        "PrincipalSID": group_id,
                        "PrincipalType": "Group",
                        "RightName": "GenericAll",
                        "AceType": "All",
                    }
                ],
            }
        ],
    )
    _write_envelope(
        raw,
        "domains.json",
        [
            {
                "ObjectIdentifier": "SYNTHETIC.DOMAIN",
                "Properties": {"name": "SYNTHETIC.DOMAIN"},
                "Trusts": [],
            }
        ],
    )
    manifest = generate_manifest(
        raw,
        dataset_id="seamless-v1",
        collector_name="sharphound",
        collector_version=None,
        collected_at=None,
    )
    manifest_path = tmp_path / "manifest.json"
    write_manifest(manifest, manifest_path, source=raw)
    return raw, manifest_path


def _field(report: dict, object_kind: str, path: str) -> dict:
    return next(
        item
        for item in report["field_inventory"]
        if item["object_kind"] == object_kind and item["field_path"] == path
    )


def test_audit_is_deterministic_and_manifest_backed(tmp_path: Path) -> None:
    raw, manifest = _fixture(tmp_path)
    first = audit_snapshot(raw, manifest)
    second = audit_snapshot(raw, manifest)
    assert first == second

    first_path = tmp_path / "one.json"
    second_path = tmp_path / "two.json"
    write_report(first, first_path)
    write_report(second, second_path)
    assert first_path.read_bytes() == second_path.read_bytes()
    assert first["manifest_verification"]["status"] == "verified"


def test_present_missing_null_empty_and_nested_fields_are_distinct(tmp_path: Path) -> None:
    raw, manifest = _fixture(tmp_path)
    report = audit_snapshot(raw, manifest)

    local_admins = _field(report, "Computer", "LocalAdmins")
    assert (local_admins["present_count"], local_admins["missing_count"]) == (2, 0)
    assert (local_admins["empty_count"], local_admins["null_count"]) == (1, 0)

    local_admin_elements = _field(report, "Computer", "LocalAdmins[]")
    assert local_admin_elements["presence_scope"] == "parent_record"
    assert local_admin_elements["presence_denominator"] == 2
    assert (local_admin_elements["present_count"], local_admin_elements["missing_count"]) == (2, 0)
    assert (
        local_admin_elements["parent_records_with_elements"],
        local_admin_elements["parent_records_without_elements"],
    ) == (1, 1)

    remote_desktop_elements = _field(report, "Computer", "RemoteDesktopUsers[]")
    assert (remote_desktop_elements["present_count"], remote_desktop_elements["missing_count"]) == (
        1,
        1,
    )
    assert remote_desktop_elements["parent_records_missing"] == 1

    sessions = _field(report, "Computer", "Sessions")
    assert sessions["null_count"] == 1
    assert sessions["empty_count"] == 1

    optional = _field(report, "User", "Properties.optional")
    assert optional["present_count"] == 1
    assert optional["missing_count"] == 2

    member_id = _field(report, "Group", "Members[].MemberId")
    assert member_id["presence_scope"] == "array_element"
    assert member_id["presence_denominator"] == 2
    assert member_id["array_elements_examined"] == 2
    assert member_id["present_count"] == 2
    assert member_id["missing_count"] == 0
    assert member_id["parent_records_with_elements"] == 1
    assert member_id["parent_records_without_elements"] == 1
    assert _field(report, "GPO", "Aces[].PrincipalSID")["present_count"] == 1


def test_multiple_types_and_safe_shapes_are_reported_without_values(tmp_path: Path) -> None:
    raw, manifest = _fixture(tmp_path)
    report = audit_snapshot(raw, manifest)
    mixed = _field(report, "User", "Properties.mixed")
    assert mixed["observed_types"] == ["boolean", "integer", "string"]

    description = _field(report, "User", "Properties.description")
    assert description["representative_shapes"] == [{"count": 1, "shape": "string"}]
    ace_type = _field(report, "GPO", "Aces[].AceType")
    assert ace_type["categorical_values"] == [{"count": 1, "value": "All"}]
    report_text = json.dumps(report, sort_keys=True)
    for secret in (
        "SYNTHETIC_USER_SHOULD_NOT_APPEAR",
        "SYNTHETIC_SECRET_SHOULD_NOT_APPEAR",
        "S-1-5-21-<fixture>-9999",
    ):
        assert secret not in report_text


def test_duplicate_and_unresolved_reference_observations_are_reported(tmp_path: Path) -> None:
    raw, manifest = _fixture(tmp_path)
    report = audit_snapshot(raw, manifest)
    duplicates = report["duplicate_summary"]
    assert duplicates["duplicate_object_identifier_count"] == 1
    assert duplicates["duplicate_record_count"] == 1
    duplicate_group = duplicates["safe_duplicate_locators"][0]
    assert duplicate_group["representation_equivalent"] is False
    assert [
        item["record_anatomy"]["properties_key_set"] for item in duplicate_group["locations"]
    ] == [
        ["name"],
        [],
    ]

    references = report["reference_summary"]
    assert references["unresolved_reference_count"] == 1
    member_refs = next(
        item
        for item in references["by_field"]
        if item["object_kind"] == "Group" and item["field_path"] == "Members[].MemberId"
    )
    assert member_refs["resolved_count"] == 1
    assert member_refs["unresolved_count"] == 1
    assert references["unresolved_is_not_classified_as_boundary"] is True
