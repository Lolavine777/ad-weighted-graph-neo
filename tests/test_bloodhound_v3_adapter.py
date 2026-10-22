from __future__ import annotations

from dataclasses import replace
from itertools import permutations

import pytest

from src.parser import DirectGraphBuilder, RawRecord, RecordError
from src.parser.adapters.bloodhound_v3 import (
    DomainScopeContext,
    adapt_bloodhound_v3_records,
    adapt_identifier,
    parse_qualified_sid,
)
from src.parser.normalizer import Normalizer

DOMAIN_SID_A = "S-1-5-21-111-222-333"
DOMAIN_SID_B = "S-1-5-21-444-555-666"
DOMAIN_GUID = "11111111-2222-3333-4444-555555555555"
HOST_GUID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
SNAPSHOT = "sha256:" + "e" * 64


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("SEAMLESS.INTERNAL-S-1-1-0", ("SEAMLESS.INTERNAL", "S-1-1-0")),
        ("SEAMLESS.INTERNAL-S-1-5-32-544", ("SEAMLESS.INTERNAL", "S-1-5-32-544")),
        (
            "DOMAIN.LOCAL-S-1-5-21-111-222-333-1001",
            ("DOMAIN.LOCAL", "S-1-5-21-111-222-333-1001"),
        ),
    ],
)
def test_parse_domain_qualified_sid(raw, expected):
    assert parse_qualified_sid(raw) == expected


def test_lowercase_qualified_sid_normalizes_before_adaptation():
    assert parse_qualified_sid("DOMAIN.LOCAL-s-1-5-32-544") == (
        "DOMAIN.LOCAL",
        "S-1-5-32-544",
    )
    assert adapt_identifier("DOMAIN.LOCAL-s-1-1-0", {}) == "S-1-1-0"


@pytest.mark.parametrize(
    "raw",
    ["SEAMLESS.INTERNAL-not-a-sid", "-S-1-5-32-544", "DOMAIN.LOCAL-S-x-y", "garbage"],
)
def test_reject_malformed_qualified_sid(raw):
    assert parse_qualified_sid(raw) is None


def _record(kind, data, *, record_id="record", provenance_snapshot=SNAPSHOT):
    return RawRecord(
        kind,
        data,
        {
            "raw_file": f"snapshot:{provenance_snapshot.removeprefix('sha256:')}/{kind}.json",
            "collector": "sharphound/3",
            "timestamp": "2021-09-20T18:59:58Z",
            "snapshot_id": provenance_snapshot,
            "record_locator": f"#/{kind}/0",
            "record_id": record_id,
            "time_provenance": "assumed",
            "schema_version": "3",
        },
    )


def _domain(name="DOMAIN.LOCAL", *, domain_sid=DOMAIN_SID_A, guid=None):
    properties = {"name": name, "domain": name}
    if domain_sid is not None:
        properties["objectid"] = domain_sid
    if guid is not None:
        properties["objectguid"] = guid
    data = {"Properties": properties}
    if domain_sid is not None or guid is not None:
        data["ObjectIdentifier"] = domain_sid or guid
    return _record("domains", data)


def _group(name, sid, *, members=None, aces=None, domain="DOMAIN.LOCAL"):
    return _record(
        "groups",
        {
            "ObjectIdentifier": sid,
            "Properties": {"name": name, "domain": domain},
            **({"Members": members} if members is not None else {}),
            **({"Aces": aces} if aces is not None else {}),
        },
        record_id=name,
    )


def test_modern_export_with_qualified_ids_uses_observed_domain_scope():
    records = [_domain(), _group("Admins", "DOMAIN.LOCAL-S-1-5-32-544")]
    records = [replace(r, provenance={**r.provenance, "schema_version": "6"}) for r in records]
    adapted = adapt_bloodhound_v3_records(records)
    assert adapted[1].data["ObjectIdentifier"] == f"domain:sid:{DOMAIN_SID_A}:S-1-5-32-544"
    assert records[1].data["ObjectIdentifier"] == "DOMAIN.LOCAL-S-1-5-32-544"


def test_global_and_domain_account_sids_remain_unscoped():
    context = {"domain.local": DomainScopeContext("domain.local", None, DOMAIN_SID_A)}
    assert adapt_identifier("DOMAIN.LOCAL-S-1-1-0", context) == "S-1-1-0"
    assert adapt_identifier("DOMAIN.LOCAL-S-1-5-21-111-222-333-1001", context) == (
        "S-1-5-21-111-222-333-1001"
    )


def test_domain_sid_scope_requires_observed_domain_group_identity():
    context = {"domain.local": DomainScopeContext("domain.local", None, DOMAIN_SID_A)}
    raw = "DOMAIN.LOCAL-S-1-5-32-544"
    assert adapt_identifier(raw, context) == raw  # DNS hint by itself is insufficient.
    canonical = adapt_identifier(
        raw,
        context,
        observed_domain_groups=frozenset({("domain.local", "S-1-5-32-544")}),
    )
    assert canonical == f"domain:sid:{DOMAIN_SID_A}:S-1-5-32-544"


def test_domain_guid_takes_precedence_independent_of_record_order():
    domain = _domain(guid=DOMAIN_GUID)
    group = _group("Administrators", "DOMAIN.LOCAL-S-1-5-32-544")
    for ordering in permutations((domain, group)):
        adapted = adapt_bloodhound_v3_records(ordering)
        adapted_group = next(item for item in adapted if item.kind == "groups")
        assert adapted_group.data["ObjectIdentifier"] == (f"domain:{DOMAIN_GUID}:S-1-5-32-544")


def test_domain_sid_fallback_when_domain_guid_is_missing():
    adapted = adapt_bloodhound_v3_records(
        (_domain(), _group("Administrators", "DOMAIN.LOCAL-S-1-5-32-544"))
    )
    group = next(item for item in adapted if item.kind == "groups")
    assert group.data["ObjectIdentifier"] == f"domain:sid:{DOMAIN_SID_A}:S-1-5-32-544"
    assert Normalizer().normalize(group).id == group.data["ObjectIdentifier"]


def test_missing_domain_guid_and_domain_sid_fails_closed():
    with pytest.raises(RecordError, match="no stable Domain GUID or Domain SID"):
        adapt_bloodhound_v3_records(
            (_domain(domain_sid=None), _group("Administrators", "DOMAIN.LOCAL-S-1-5-32-544"))
        )


@pytest.mark.parametrize("bad_sid", ["S-1-1-0", "S-1-5-32-544", "S-1-5-21-1-2", "not-a-sid"])
def test_invalid_domain_sid_on_domain_record_is_rejected(bad_sid):
    domain = _record(
        "domains",
        {
            "ObjectIdentifier": bad_sid,
            "Properties": {"name": "DOMAIN.LOCAL", "domain": "DOMAIN.LOCAL"},
        },
    )
    with pytest.raises(RecordError, match="Domain SID is not a valid AD domain SID"):
        adapt_bloodhound_v3_records((domain,))


def test_same_identifier_converts_on_node_member_reference_and_ace_reference():
    qualified = "DOMAIN.LOCAL-S-1-5-32-544"
    records = (
        _domain(),
        _group("Administrators", qualified),
        _group(
            "Account Operators",
            "DOMAIN.LOCAL-S-1-5-32-548",
            members=[{"MemberId": qualified, "MemberType": "Group"}],
            aces=[{"PrincipalSID": qualified, "PrincipalType": "Group", "RightName": "GenericAll"}],
        ),
    )
    adapted = adapt_bloodhound_v3_records(records)
    expected = f"domain:sid:{DOMAIN_SID_A}:S-1-5-32-544"
    parent = next(
        item
        for item in adapted
        if item.data.get("Properties", {}).get("name") == "Account Operators"
    )
    assert parent.data["Members"][0]["MemberId"] == expected
    assert parent.data["Aces"][0]["PrincipalSID"] == expected
    assert records[1].data["ObjectIdentifier"] == qualified  # Raw source remains unchanged.

    normalized = Normalizer().normalize_records(adapted)
    graph = DirectGraphBuilder(
        metadata={
            "contract_version": "1.3.0",
            "weight_profile": "unit",
            "snapshot_id": SNAPSHOT,
            "created_at": "2026-09-28T07:57:37Z",
            "code_version": "a" * 40,
        }
    ).build(normalized)
    assert expected in {node["id"] for node in graph["nodes"]}
    assert any(edge["kind"] == "MemberOf" and edge["source"] == expected for edge in graph["edges"])
    assert any(
        edge["kind"] == "GenericAll" and edge["source"] == expected for edge in graph["edges"]
    )
    assert all(
        "schema_version" not in provenance
        for edge in graph["edges"]
        for provenance in edge["provenance"]
    )


def test_multi_domain_builtin_group_ids_do_not_collide():
    records = (
        _domain("ALPHA.LOCAL", domain_sid=DOMAIN_SID_A),
        _group("Administrators Alpha", "ALPHA.LOCAL-S-1-5-32-544", domain="ALPHA.LOCAL"),
        _domain("BETA.LOCAL", domain_sid=DOMAIN_SID_B),
        _group("Administrators Beta", "BETA.LOCAL-S-1-5-32-544", domain="BETA.LOCAL"),
    )
    normalized = Normalizer().normalize_records(adapt_bloodhound_v3_records(records))
    assert {item.id for item in normalized if item.kind == "Group"} == {
        f"domain:sid:{DOMAIN_SID_A}:S-1-5-32-544",
        f"domain:sid:{DOMAIN_SID_B}:S-1-5-32-544",
    }


def test_host_local_sid_does_not_use_available_domain_sid():
    with pytest.raises(RecordError, match="Domain SID cannot be used as fallback"):
        adapt_bloodhound_v3_records(
            (
                _domain(),
                _record(
                    "users",
                    {"ObjectIdentifier": "DOMAIN.LOCAL-S-1-5-18", "Properties": {"name": "SYSTEM"}},
                ),
            )
        )


def test_host_scope_uses_computer_guid_when_observed():
    computer = _record(
        "computers",
        {
            "ObjectIdentifier": "S-1-5-21-111-222-333-1000",
            "ObjectGUID": HOST_GUID,
            "Properties": {"name": "HOST01.DOMAIN.LOCAL", "domain": "DOMAIN.LOCAL"},
        },
    )
    service = _record(
        "users",
        {"ObjectIdentifier": "HOST01.DOMAIN.LOCAL-S-1-5-18", "Properties": {"name": "SYSTEM"}},
    )
    adapted = adapt_bloodhound_v3_records((_domain(), computer, service))
    adapted_service = next(item for item in adapted if item is service or item.kind == "users")
    assert adapted_service.data["ObjectIdentifier"] == f"host:{HOST_GUID}:S-1-5-18"


def test_two_records_with_same_domain_sid_reconcile_and_different_sids_do_not():
    first = _record(
        "groups",
        {
            "ObjectIdentifier": "domain:sid:" + DOMAIN_SID_A + ":S-1-5-32-544",
            "scope": {"kind": "domain", "identity_type": "sid", "value": DOMAIN_SID_A},
            "Properties": {"name": "Administrators", "domain": "ALPHA.LOCAL"},
        },
        record_id="first",
    )
    duplicate = _record("groups", dict(first.data), record_id="duplicate")
    other = _record(
        "groups",
        {
            "ObjectIdentifier": "domain:sid:" + DOMAIN_SID_B + ":S-1-5-32-544",
            "Properties": {"name": "Administrators", "domain": "BETA.LOCAL"},
        },
        record_id="other",
    )
    normalized = Normalizer().normalize_records((first, duplicate, other))
    assert {item.id for item in normalized} == {
        f"domain:sid:{DOMAIN_SID_A}:S-1-5-32-544",
        f"domain:sid:{DOMAIN_SID_B}:S-1-5-32-544",
    }


def test_bloodhound_v3_adapter_adapts_primary_group_sid():
    domain = _domain("DOMAIN.LOCAL", domain_sid=DOMAIN_SID_A)
    user = _record(
        "users",
        {
            "ObjectIdentifier": f"{DOMAIN_SID_A}-1001",
            "PrimaryGroupSid": f"DOMAIN.LOCAL-{DOMAIN_SID_A}-513",
            "Properties": {"name": "alice@domain.local", "domain": "DOMAIN.LOCAL"},
        },
        record_id="alice",
    )
    adapted = adapt_bloodhound_v3_records((domain, user))
    adapted_user = next(r for r in adapted if r.kind == "users")
    assert adapted_user.data["PrimaryGroupSid"] == f"{DOMAIN_SID_A}-513"
