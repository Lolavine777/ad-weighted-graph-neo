"""Identity normalization and duplicate reconciliation acceptance tests."""

from __future__ import annotations

from itertools import permutations
from pathlib import Path

import pytest
import yaml

from scripts.check_contract import validate_node
from src.parser import RawRecord, ReconciliationConflictError, RecordError
from src.parser.normalizer import Normalizer

DOMAIN_A = "10000000-0000-4000-8000-000000000001"
DOMAIN_B = "10000000-0000-4000-8000-000000000002"
HOST_A = "20000000-0000-4000-8000-000000000001"
DOMAIN_SID_A = "S-1-5-21-111-222-333"
DOMAIN_SID_B = "S-1-5-21-444-555-666"
SNAPSHOT = "sha256:normalizer-tests"


def raw(kind: str, data: dict, record_id: str = "record") -> RawRecord:
    return RawRecord(
        kind=kind,
        data=data,
        provenance={
            "raw_file": f"snapshot:{SNAPSHOT}/records.json",
            "collector": "synthetic/1.0",
            "timestamp": "2026-09-22T00:00:00Z",
            "snapshot_id": SNAPSHOT,
            "record_locator": f"#/records/{record_id}",
            "record_id": record_id,
        },
    )


def test_normalize_prefers_sid_and_lowercases_guid_fallback():
    normalizer = Normalizer()

    sid = normalizer.normalize(
        raw(
            "users",
            {
                "ObjectIdentifier": "S-1-5-21-1000-2000-3000-1101",
                "Properties": {
                    "name": "alice",
                    "domain": "EXAMPLE.TEST",
                    "enabled": True,
                },
            },
        )
    )
    guid = normalizer.normalize(
        raw(
            "computers",
            {
                "objectguid": "ABCDEFAB-CDEF-ABCD-EFAB-CDEFABCDEFAB",
                "name": "workstation",
                "domain": "EXAMPLE.TEST",
            },
        )
    )

    assert sid.id == "S-1-5-21-1000-2000-3000-1101"
    assert sid.attributes["label"] == "alice"
    assert sid.attributes["enabled"] is True
    assert guid.id == "abcdefab-cdef-abcd-efab-cdefabcdefab"


@pytest.mark.parametrize(
    ("scope", "expected"),
    [
        ({"kind": "domain", "guid": DOMAIN_A}, f"domain:{DOMAIN_A}:S-1-5-32-544"),
        ({"kind": "host", "guid": HOST_A.upper()}, f"host:{HOST_A}:S-1-5-32-544"),
    ],
)
def test_local_sid_is_scoped(scope, expected):
    record = raw(
        "groups",
        {
            "ObjectIdentifier": "S-1-5-32-544",
            "name": "Administrators",
            "domain": "EXAMPLE.TEST",
            "scope": scope,
        },
    )

    assert Normalizer().normalize(record).id == expected


def test_scope_can_be_supplied_by_explicit_fields_or_container_hierarchy():
    explicit = raw(
        "groups",
        {
            "ObjectIdentifier": "S-1-5-32-555",
            "name": "Remote Desktop Users",
            "domain": "EXAMPLE.TEST",
            "scope_kind": "host",
            "scope_guid": HOST_A.upper(),
        },
    )
    nested = raw(
        "groups",
        {
            "ObjectIdentifier": "S-1-5-32-580",
            "name": "Remote Management Users",
            "domain": "EXAMPLE.TEST",
            "computer": {"ObjectIdentifier": HOST_A},
        },
    )

    normalizer = Normalizer()
    assert normalizer.normalize(explicit).id == f"host:{HOST_A}:S-1-5-32-555"
    assert normalizer.normalize(nested).id == f"host:{HOST_A}:S-1-5-32-580"


def test_same_local_sid_in_two_scopes_never_collides():
    normalizer = Normalizer()
    records = [
        raw(
            "groups",
            {
                "ObjectIdentifier": "S-1-5-32-544",
                "name": "Administrators",
                "domain": domain,
                "scope": {"kind": "domain", "guid": scope},
            },
        )
        for scope, domain in ((DOMAIN_A, "ALPHA.TEST"), (DOMAIN_B, "BETA.TEST"))
    ]

    normalized = normalizer.normalize_records(records)
    assert [record.id for record in normalized] == [
        f"domain:{DOMAIN_A}:S-1-5-32-544",
        f"domain:{DOMAIN_B}:S-1-5-32-544",
    ]


def test_domain_sid_is_typed_stable_scope_and_separates_domains():
    records = [
        raw(
            "groups",
            {
                "ObjectIdentifier": "S-1-5-32-544",
                "name": "Administrators",
                "domain": domain,
                "scope": {"kind": "domain", "identity_type": "sid", "value": scope_sid},
            },
            record_id=domain,
        )
        for scope_sid, domain in ((DOMAIN_SID_A, "ALPHA.TEST"), (DOMAIN_SID_B, "BETA.TEST"))
    ]
    normalized = Normalizer().normalize_records(records)
    assert [record.id for record in normalized] == [
        f"domain:sid:{DOMAIN_SID_A}:S-1-5-32-544",
        f"domain:sid:{DOMAIN_SID_B}:S-1-5-32-544",
    ]


def test_domain_sid_scope_reconciles_duplicates_and_keeps_domains_separate():
    def record(record_id, domain_sid, domain):
        return raw(
            "groups",
            {
                "ObjectIdentifier": "S-1-5-32-544",
                "scope": {"kind": "domain", "identity_type": "sid", "value": domain_sid},
                "domain": domain,
                "name": "Administrators",
            },
            record_id=record_id,
        )

    first = record("one", DOMAIN_SID_A, "ALPHA.TEST")
    duplicate = record("two", DOMAIN_SID_A, "ALPHA.TEST")
    other_domain = record("three", DOMAIN_SID_B, "BETA.TEST")
    normalized = Normalizer().normalize_records([first, duplicate, other_domain])
    assert [item.id for item in normalized] == [
        f"domain:sid:{DOMAIN_SID_A}:S-1-5-32-544",
        f"domain:sid:{DOMAIN_SID_B}:S-1-5-32-544",
    ]
    assert normalized[0].raw_provenance == (first.provenance, duplicate.provenance)


def test_missing_local_scope_is_rejected_without_guessing():
    record = raw(
        "groups",
        {
            "ObjectIdentifier": "S-1-5-32-544",
            "name": "Administrators",
            "domain": "EXAMPLE.TEST",
        },
        record_id="missing-scope",
    )

    with pytest.raises(RecordError, match="stable domain or host identity") as caught:
        Normalizer().normalize(record)
    assert caught.value.stage == "normalize"
    assert caught.value.record_id == "missing-scope"


@pytest.mark.parametrize("kind", ["groups", "users"])
def test_generic_string_scope_override_is_ambiguous_for_principals(kind):
    record = raw(kind, {"ObjectIdentifier": "S-1-5-32-544", "domain": "EXAMPLE.TEST"})
    with pytest.raises(RecordError, match="explicit domain or host kind"):
        Normalizer(scope_context={"record": DOMAIN_A}).normalize(record)


@pytest.mark.parametrize(
    ("sid", "scope", "expected"),
    [
        ("s-1-5-21-111-222-333-1001", None, "S-1-5-21-111-222-333-1001"),
        ("s-1-5-18", {"kind": "host", "guid": HOST_A}, f"host:{HOST_A}:S-1-5-18"),
        ("s-1-5-19", {"kind": "host", "guid": HOST_A}, f"host:{HOST_A}:S-1-5-19"),
        ("s-1-5-20", {"kind": "host", "guid": HOST_A}, f"host:{HOST_A}:S-1-5-20"),
        (
            "s-1-5-32-544",
            {"kind": "domain", "identity_type": "sid", "value": DOMAIN_SID_A.lower()},
            f"domain:sid:{DOMAIN_SID_A}:S-1-5-32-544",
        ),
        (
            f"domain:sid:{DOMAIN_SID_A.lower()}:s-1-5-32-544",
            None,
            f"domain:sid:{DOMAIN_SID_A}:S-1-5-32-544",
        ),
        (f"host:{HOST_A}:s-1-5-18", None, f"host:{HOST_A}:S-1-5-18"),
    ],
)
def test_lowercase_sid_input_emits_canonical_case(sid, scope, expected):
    data = {"ObjectIdentifier": sid, "domain": "EXAMPLE.TEST"}
    if scope is not None:
        data["scope"] = scope
    normalized = Normalizer().normalize(raw("groups", data))
    assert normalized.id == expected
    contract = yaml.safe_load(
        (Path(__file__).resolve().parents[1] / "configs/contract.yml").read_text(encoding="utf-8")
    )
    validate_node(
        {"id": normalized.id, "kind": normalized.kind, **normalized.attributes},
        contract,
        contract_version="1.3.0",
    )


def test_lowercase_computer_builtin_still_requires_host_scope():
    record = raw(
        "computers",
        {
            "ObjectIdentifier": "s-1-5-32-544",
            "domain": "EXAMPLE.TEST",
            "scope": {"kind": "domain", "identity_type": "sid", "value": DOMAIN_SID_A},
        },
    )
    with pytest.raises(RecordError, match="computer-local built-in SID requires host scope"):
        Normalizer().normalize(record)


@pytest.mark.parametrize("sid", ["s-1-5-18", "s-1-5-19", "s-1-5-20"])
def test_prescoped_lowercase_local_service_sid_requires_host(sid):
    record = raw(
        "users",
        {"ObjectIdentifier": f"domain:sid:{DOMAIN_SID_A.lower()}:{sid}", "domain": "EXAMPLE.TEST"},
    )
    with pytest.raises(RecordError, match="local service SID requires stable host scope"):
        Normalizer().normalize(record)


def test_domain_sid_never_substitutes_for_host_scope():
    record = raw(
        "computers",
        {
            "ObjectIdentifier": "S-1-5-32-544",
            "domain_sid": DOMAIN_SID_A,
            "Properties": {"name": "HOST.EXAMPLE.TEST", "domain": "EXAMPLE.TEST"},
        },
    )
    with pytest.raises(RecordError, match="Domain SID cannot be used as host scope"):
        Normalizer().normalize(record)


@pytest.mark.parametrize("scope_sid", ["S-1-1-0", "S-1-5-32-544", "S-1-5-21-1-2", "not-a-sid"])
def test_invalid_domain_sid_scope_is_rejected(scope_sid):
    record = raw(
        "groups",
        {
            "ObjectIdentifier": "S-1-5-32-544",
            "scope": {"kind": "domain", "identity_type": "sid", "value": scope_sid},
        },
    )
    with pytest.raises(RecordError, match="scope SID must be a valid AD domain SID"):
        Normalizer().normalize(record)


def test_duplicate_merge_is_order_invariant_and_empty_stub_cannot_erase_data():
    rich = raw(
        "groups",
        {
            "ObjectIdentifier": "S-1-5-21-1000-2000-3000-1100",
            "name": "Helpdesk",
            "domain": "EXAMPLE.TEST",
            "Members": ["S-1-5-21-1000-2000-3000-1101"],
            "Aces": [{"PrincipalSID": "S-1-5-21-1000-2000-3000-1102", "RightName": "GenericAll"}],
            "Sessions": [{"UserSID": "S-1-5-21-1000-2000-3000-1103"}],
            "LocalGroups": [{"ObjectIdentifier": "S-1-5-32-544"}],
            "enabled": True,
        },
        record_id="rich",
    )
    second = raw(
        "groups",
        {
            "ObjectIdentifier": "S-1-5-21-1000-2000-3000-1100",
            "domain": "EXAMPLE.TEST",
            "Members": ["S-1-5-21-1000-2000-3000-1104"],
            "Aces": [{"PrincipalSID": "S-1-5-21-1000-2000-3000-1105", "RightName": "WriteDacl"}],
        },
        record_id="second",
    )
    stub = raw(
        "groups",
        {"ObjectIdentifier": "S-1-5-21-1000-2000-3000-1100", "domain": "EXAMPLE.TEST"},
        record_id="stub",
    )

    outputs = [
        Normalizer().normalize_records(order) for order in permutations((rich, second, stub))
    ]
    assert all(output == outputs[0] for output in outputs)
    merged = outputs[0][0]
    assert merged.attributes["label"] == "Helpdesk"
    assert merged.attributes["enabled"] is True
    assert merged.raw.data["Members"] == [
        "S-1-5-21-1000-2000-3000-1101",
        "S-1-5-21-1000-2000-3000-1104",
    ]
    assert len(merged.raw.data["Aces"]) == 2
    assert len(merged.raw.data["Sessions"]) == 1
    assert len(merged.raw.data["LocalGroups"]) == 1
    assert {item["record_locator"] for item in merged.raw_provenance} == {
        "#/records/rich",
        "#/records/second",
        "#/records/stub",
    }
    member_sources = {
        line.item: {source["record_locator"] for source in line.provenance}
        for line in merged.evidence_lineage
        if line.field == "Members"
    }
    ace_sources = {
        line.item["RightName"]: {source["record_locator"] for source in line.provenance}
        for line in merged.evidence_lineage
        if line.field == "Aces"
    }
    assert member_sources["S-1-5-21-1000-2000-3000-1101"] == {"#/records/rich"}
    assert member_sources["S-1-5-21-1000-2000-3000-1104"] == {"#/records/second"}
    assert ace_sources["GenericAll"] == {"#/records/rich"}
    assert ace_sources["WriteDacl"] == {"#/records/second"}


def test_normalizer_does_not_choose_a_scalar_conflict_winner():
    first = raw(
        "groups",
        {
            "ObjectIdentifier": "S-1-5-21-1000-2000-3000-1100",
            "name": "FIRST",
            "domain": "EXAMPLE.TEST",
        },
        record_id="first",
    )
    second = raw(
        "groups",
        {
            "ObjectIdentifier": "S-1-5-21-1000-2000-3000-1100",
            "name": "SECOND",
            "domain": "EXAMPLE.TEST",
        },
        record_id="second",
    )

    with pytest.raises(ReconciliationConflictError, match="Properties.name|name"):
        Normalizer().normalize_records([first, second])


def test_invalid_identifier_and_kind_are_record_errors():
    normalizer = Normalizer()
    with pytest.raises(RecordError, match="valid SID or GUID"):
        normalizer.normalize(raw("users", {"ObjectIdentifier": "display-name", "domain": "D"}))
    with pytest.raises(RecordError, match="unsupported record kind"):
        normalizer.normalize(
            raw("unknown", {"ObjectIdentifier": "S-1-5-21-1000-2000-3000-1101", "domain": "D"})
        )
