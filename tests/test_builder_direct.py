"""Direct M2-05 graph-builder acceptance coverage."""

from __future__ import annotations

from itertools import permutations

import pytest
import yaml

from scripts.check_contract import validate_graph
from src.parser import (
    DirectGraphBuilder,
    ErrorPolicy,
    IdentityNormalizer,
    NormalizedRecord,
    RawRecord,
    RecordError,
    deserialize_graph,
    serialize_graph,
)
from src.parser.builder import canonical_edge_id

SNAPSHOT = "sha256:" + "a" * 64
DOMAIN = "EXAMPLE.TEST"
CREATED = "2026-09-23T00:00:00Z"

IDS = {
    "user": "S-1-5-21-1000-2000-3000-1101",
    "disabled": "S-1-5-21-1000-2000-3000-1102",
    "group": "S-1-5-21-1000-2000-3000-2101",
    "nested": "S-1-5-21-1000-2000-3000-2102",
    "computer": "S-1-5-21-1000-2000-3000-3101",
    "target": "S-1-5-21-1000-2000-3000-1103",
}


def _raw(kind: str, data: dict, record_id: str, *, time_provenance: str | None = None) -> RawRecord:
    provenance = {
        "raw_file": f"snapshot:{SNAPSHOT.removeprefix('sha256:')}/{kind.lower()}.json",
        "collector": "synthetic/1.0",
        "timestamp": "2026-09-22T00:00:00Z",
        "snapshot_id": SNAPSHOT,
        "record_id": record_id,
        "record_locator": f"#/{kind.lower()}/{record_id}",
    }
    if time_provenance is not None:
        provenance["time_provenance"] = time_provenance
        if time_provenance in {"derived", "externally_evidenced"}:
            provenance["time_provenance_reason"] = "test evidence"
    return RawRecord(
        kind=kind,
        data=data,
        provenance=provenance,
    )


def _record(
    kind: str,
    identifier: str,
    *,
    data: dict | None = None,
    enabled: bool | None = None,
    time_provenance: str | None = None,
):
    properties = {"name": identifier, "domain": DOMAIN}
    if enabled is not None:
        properties["enabled"] = enabled
    payload = {"ObjectIdentifier": identifier, "Properties": properties}
    if data:
        payload.update(data)
    return NormalizedRecord(
        id=identifier,
        kind=kind,
        attributes={
            "id": identifier,
            "kind": kind,
            "label": identifier,
            "domain": DOMAIN,
            "is_boundary": False,
            **({"enabled": enabled} if enabled is not None else {}),
        },
        raw=_raw(kind, payload, identifier, time_provenance=time_provenance),
    )


def _builder() -> DirectGraphBuilder:
    return DirectGraphBuilder(
        metadata={
            "contract_version": "1.3.0",
            "weight_profile": "unit",
            "snapshot_id": SNAPSHOT,
            "created_at": CREATED,
            "code_version": "tests/direct-builder",
        }
    )


def _graph(records, **kwargs):
    return _builder().build(records, **kwargs)


def _edge(graph, source, target, kind):
    return next(
        edge
        for edge in graph["edges"]
        if edge["source"] == source and edge["target"] == target and edge["kind"] == kind
    )


@pytest.mark.parametrize("sid,label", [("S-1-5-4", "INTERACTIVE"), ("S-1-5-17", "IUSR")])
def test_well_known_boundary_group_is_global_and_deduplicated(sid, label):
    first = _record(
        "Group",
        IDS["group"],
        data={
            "Members": [
                {"MemberId": f"EXAMPLE.TEST-{sid}", "MemberType": "Group"},
                {"MemberId": f"example.test-s-1-5-{sid.rsplit('-', 1)[-1]}", "MemberType": "Group"},
            ]
        },
    )
    second = _record(
        "Group",
        IDS["nested"],
        data={
            "Members": [
                {"MemberId": sid, "MemberType": "Group"},
            ]
        },
    )
    graphs = [_graph(order) for order in ((first, second), (second, first))]
    assert serialize_graph(graphs[0]) == serialize_graph(graphs[1])
    graph = graphs[0]
    assert [node for node in graph["nodes"] if node["id"] == sid] == [
        {
            "id": sid,
            "kind": "Group",
            "label": label,
            "domain": "NT AUTHORITY",
            "is_boundary": True,
        }
    ]
    assert len([edge for edge in graph["edges"] if edge["source"] == sid]) == 2
    assert all(edge["provenance"] for edge in graph["edges"] if edge["source"] == sid)


def test_collected_well_known_group_takes_precedence():
    group = _record(
        "Group",
        IDS["group"],
        data={
            "Members": [
                {"MemberId": "EXAMPLE.TEST-S-1-5-4", "MemberType": "Group"},
            ]
        },
    )
    collected = _record("Group", "S-1-5-4")
    graph = _graph([group, collected])
    assert len([node for node in graph["nodes"] if node["id"] == "S-1-5-4"]) == 1
    assert next(node for node in graph["nodes"] if node["id"] == "S-1-5-4")["is_boundary"] is False


def test_iusr_boundary_group_is_not_inferred_from_acl_principal_type():
    target = _record(
        "Group",
        IDS["group"],
        data={
            "Aces": [
                {
                    "PrincipalSID": "EXAMPLE.TEST-S-1-5-17",
                    "PrincipalType": "Group",
                    "RightName": "GenericAll",
                }
            ]
        },
    )
    with pytest.raises(RecordError, match="IUSR boundary Group"):
        _graph([target])


def test_collected_iusr_group_can_resolve_acl_without_new_boundary():
    target = _record(
        "Group",
        IDS["group"],
        data={
            "Aces": [
                {
                    "PrincipalSID": "EXAMPLE.TEST-S-1-5-17",
                    "PrincipalType": "Group",
                    "RightName": "GenericAll",
                }
            ]
        },
    )
    graph = _graph([target, _record("Group", "S-1-5-17")])
    assert next(node for node in graph["nodes"] if node["id"] == "S-1-5-17")["is_boundary"] is False
    _edge(graph, "S-1-5-17", IDS["group"], "GenericAll")


@pytest.mark.parametrize(
    "reference,kind",
    [
        ("EXAMPLE.TEST-S-1-5-99", "Group"),
        ("EXAMPLE.TEST-S-1-5-32-544", "Group"),
        ("EXAMPLE.TEST-S-1-5-18", "Group"),
        ("EXAMPLE.TEST-S-1-5-19", "Group"),
        ("EXAMPLE.TEST-S-1-5-20", "Group"),
        ("EXAMPLE.TEST-S-1-5-4", "User"),
        ("EXAMPLE.TEST-S-1-5-17", "User"),
        ("EXAMPLE.TEST-S-1-5-4-bad", "Group"),
    ],
)
def test_boundary_resolution_fails_closed_for_unknown_or_conflicting_reference(reference, kind):
    group = _record(
        "Group",
        IDS["group"],
        data={
            "Members": [
                {"MemberId": reference, "MemberType": kind},
            ]
        },
    )
    with pytest.raises(RecordError):
        _graph([group])


def test_memberof_supports_user_group_and_computer_and_is_direct_only():
    records = [
        _record(
            "Group",
            IDS["group"],
            data={
                "Members": [
                    {"MemberId": IDS["user"], "MemberType": "User"},
                    {"MemberId": IDS["nested"], "MemberType": "Group"},
                    {"MemberId": IDS["computer"], "MemberType": "Computer"},
                ]
            },
        ),
        _record(
            "Group",
            IDS["nested"],
            data={"Members": [{"MemberId": IDS["user"], "MemberType": "User"}]},
        ),
        _record("User", IDS["user"]),
        _record("Computer", IDS["computer"]),
    ]
    graph = _graph(records)
    assert {(e["source"], e["target"], e["kind"]) for e in graph["edges"]} == {
        (IDS["user"], IDS["group"], "MemberOf"),
        (IDS["nested"], IDS["group"], "MemberOf"),
        (IDS["computer"], IDS["group"], "MemberOf"),
        (IDS["user"], IDS["nested"], "MemberOf"),
    }
    assert (IDS["user"], IDS["group"], "MemberOf") not in {
        (IDS["user"], IDS["group"], "DerivedMemberOf")
    }


def test_direct_acl_rights_preserve_direction_and_do_not_mutate_rights():
    records = [
        _record(
            "User",
            IDS["target"],
            data={
                "Aces": [
                    {
                        "PrincipalSID": IDS["user"],
                        "PrincipalType": "User",
                        "RightName": "GenericAll",
                    },
                    {
                        "PrincipalSID": IDS["disabled"],
                        "PrincipalType": "User",
                        "RightName": "WriteDacl",
                    },
                ]
            },
        ),
        _record(
            "User",
            IDS["user"],
            data={
                "Aces": [
                    {
                        "PrincipalSID": IDS["disabled"],
                        "PrincipalType": "User",
                        "RightName": "ForceChangePassword",
                    }
                ]
            },
        ),
        _record("User", IDS["disabled"], enabled=False),
    ]
    graph = _graph(records)
    assert {(e["source"], e["target"], e["kind"]) for e in graph["edges"]} == {
        (IDS["user"], IDS["target"], "GenericAll"),
        (IDS["disabled"], IDS["target"], "WriteDacl"),
        (IDS["disabled"], IDS["user"], "ForceChangePassword"),
    }
    assert not any(
        e["kind"] == "GenericAll"
        and e["source"] == IDS["disabled"]
        and e["target"] == IDS["target"]
        for e in graph["edges"]
    )


def test_hassession_is_computer_to_user_observation_only():
    computer = _record(
        "Computer",
        IDS["computer"],
        data={"Sessions": [{"UserSID": IDS["user"], "LogonType": 2}]},
    )
    graph = _graph([computer, _record("User", IDS["user"])])
    edge = _edge(graph, IDS["computer"], IDS["user"], "HasSession")
    assert edge["provenance"][0]["evidence_type"] == "positive"
    assert "technique" not in edge and "ObservedActivity" not in edge


def test_duplicate_evidence_aggregates_provenance_and_input_order_is_irrelevant():
    first = _record(
        "Group",
        IDS["group"],
        data={"Members": [{"MemberId": IDS["user"], "MemberType": "User"}]},
    )
    second = _record(
        "Group",
        IDS["group"],
        data={"Members": [{"MemberId": IDS["user"], "MemberType": "User"}]},
    )
    second = NormalizedRecord(
        id=second.id,
        kind=second.kind,
        attributes=second.attributes,
        raw=RawRecord(
            kind=second.raw.kind,
            data=second.raw.data,
            provenance={
                **second.raw.provenance,
                "raw_file": "snapshot:"
                + SNAPSHOT.removeprefix("sha256:")
                + "/groups-duplicate.json",
                "snapshot_id": SNAPSHOT,
            },
        ),
    )
    outputs = [
        _graph([_record("User", IDS["user"]), *_order]) for _order in permutations((first, second))
    ]
    assert outputs[0] == outputs[1]
    edge = _edge(outputs[0], IDS["user"], IDS["group"], "MemberOf")
    assert len(edge["provenance"]) == 2


def test_builder_consumes_normalizer_output_and_uses_evidence_lineage():
    group_data = {
        "ObjectIdentifier": IDS["group"],
        "Properties": {"name": "GROUP", "domain": DOMAIN},
        "Members": [{"MemberId": IDS["user"], "MemberType": "User"}],
    }
    first = _raw("Group", group_data, "group-occurrence-1")
    second = _raw("Group", group_data, "group-occurrence-2")
    user = _raw(
        "User",
        {"ObjectIdentifier": IDS["user"], "Properties": {"name": "USER", "domain": DOMAIN}},
        "user-occurrence",
    )

    normalized = IdentityNormalizer().normalize_records([first, second, user])
    graph = _graph(normalized)
    edge = _edge(graph, IDS["user"], IDS["group"], "MemberOf")

    assert {item["record_id"] for item in edge["provenance"]} == {
        "group-occurrence-1",
        "group-occurrence-2",
    }


def test_parallel_kinds_have_distinct_ids_and_graph_integrity():
    records = [
        _record(
            "User",
            IDS["target"],
            data={
                "Aces": [
                    {"PrincipalSID": IDS["user"], "RightName": "GenericAll"},
                    {"PrincipalSID": IDS["user"], "RightName": "WriteDacl"},
                ]
            },
        ),
        _record("User", IDS["user"]),
    ]
    graph = _graph(records)
    assert len({node["id"] for node in graph["nodes"]}) == len(graph["nodes"])
    assert len({edge["id"] for edge in graph["edges"]}) == len(graph["edges"])
    assert {edge["id"] for edge in graph["edges"]} == {
        canonical_edge_id(IDS["user"], IDS["target"], "GenericAll"),
        canonical_edge_id(IDS["user"], IDS["target"], "WriteDacl"),
    }
    contract = yaml.safe_load(open("configs/contract.yml", encoding="utf-8"))
    validate_graph(graph, contract)


@pytest.mark.parametrize("time_provenance", ["assumed", "derived", "externally_evidenced"])
def test_non_observed_time_provenance_is_preserved(time_provenance):
    group = _record(
        "Group",
        IDS["group"],
        data={"Members": [{"MemberId": IDS["user"], "MemberType": "User"}]},
        time_provenance=time_provenance,
    )
    graph = _graph([group, _record("User", IDS["user"])])
    evidence = _edge(graph, IDS["user"], IDS["group"], "MemberOf")["provenance"][0]
    assert evidence["timestamp_status"] == time_provenance


def test_non_observed_time_provenance_is_allowed_for_node_only_records():
    assert _graph([_record("User", IDS["user"], time_provenance="assumed")])["edges"] == []


@pytest.mark.parametrize(
    ("status", "reason"),
    [
        ("observed", None),
        ("assumed", "configured collection-time baseline"),
        ("derived", "deterministic source rule"),
        ("externally_evidenced", "collector audit record"),
        (None, None),
    ],
)
def test_collection_time_status_round_trips_without_masquerading(status, reason):
    group = _record(
        "Group",
        IDS["group"],
        data={"Members": [{"MemberId": IDS["user"], "MemberType": "User"}]},
        time_provenance=status,
    )
    if reason is not None:
        group.raw.provenance["time_provenance_reason"] = reason
    graph = _graph([group, _record("User", IDS["user"])])
    evidence = _edge(graph, IDS["user"], IDS["group"], "MemberOf")["provenance"][0]
    expected = status if status is not None else "unknown_legacy"
    assert evidence["timestamp_status"] == expected
    if reason is not None:
        assert evidence["time_provenance_reason"] == reason
    payload = serialize_graph(graph)
    reloaded = deserialize_graph(payload)
    assert reloaded == graph
    assert (
        _edge(reloaded, IDS["user"], IDS["group"], "MemberOf")["provenance"][0]["timestamp_status"]
        == expected
    )


def test_duplicate_edge_provenance_keeps_each_timestamp_status():
    observed = _record(
        "Group",
        IDS["group"],
        data={"Members": [{"MemberId": IDS["user"], "MemberType": "User"}]},
        time_provenance="observed",
    )
    assumed = _record(
        "Group",
        IDS["group"],
        data={"Members": [{"MemberId": IDS["user"], "MemberType": "User"}]},
        time_provenance="assumed",
    )
    normalized = IdentityNormalizer().normalize_records(
        [observed.raw, assumed.raw, _record("User", IDS["user"]).raw]
    )
    graph = _builder().build(normalized)
    provenance = _edge(graph, IDS["user"], IDS["group"], "MemberOf")["provenance"]
    assert {item["timestamp_status"] for item in provenance} == {"observed", "assumed"}


def test_results_container_session_lineage_only_names_supporting_occurrence():
    computer_data = {
        "ObjectIdentifier": IDS["computer"],
        "Properties": {"name": "COMPUTER", "domain": DOMAIN},
    }
    session = {"UserSID": IDS["user"], "LogonType": 2}
    supporting = _raw(
        "Computer",
        {**computer_data, "Sessions": {"Results": [session]}},
        "session-supporting-occurrence",
    )
    non_supporting = _raw(
        "Computer",
        {**computer_data, "Sessions": {"Results": []}},
        "session-empty-occurrence",
    )
    user = _raw(
        "User",
        {"ObjectIdentifier": IDS["user"], "Properties": {"name": "USER", "domain": DOMAIN}},
        "session-user-occurrence",
    )

    normalized = IdentityNormalizer().normalize_records([supporting, non_supporting, user])
    graph = _graph(normalized)
    edge = _edge(graph, IDS["computer"], IDS["user"], "HasSession")

    assert {item["record_id"] for item in edge["provenance"]} == {"session-supporting-occurrence"}


@pytest.mark.parametrize("session_field", ["Sessions", "PrivilegedSessions", "RegistrySessions"])
def test_results_container_session_evidence_unions_distinct_occurrences(session_field):
    computer_data = {
        "ObjectIdentifier": IDS["computer"],
        "Properties": {"name": "COMPUTER", "domain": DOMAIN},
    }
    first = _raw(
        "Computer",
        {
            **computer_data,
            session_field: {"Results": [{"UserSID": IDS["user"], "LogonType": 2}]},
        },
        "session-first-occurrence",
    )
    second = _raw(
        "Computer",
        {
            **computer_data,
            session_field: {"Results": [{"UserSID": IDS["target"], "LogonType": 2}]},
        },
        "session-second-occurrence",
    )
    user = _raw(
        "User",
        {"ObjectIdentifier": IDS["user"], "Properties": {"name": "USER", "domain": DOMAIN}},
        "session-user-occurrence",
    )
    target = _raw(
        "User",
        {
            "ObjectIdentifier": IDS["target"],
            "Properties": {"name": "TARGET", "domain": DOMAIN},
        },
        "session-target-occurrence",
    )

    normalized = IdentityNormalizer().normalize_records([first, second, user, target])
    graph = _graph(normalized)

    first_edge = _edge(graph, IDS["computer"], IDS["user"], "HasSession")
    second_edge = _edge(graph, IDS["computer"], IDS["target"], "HasSession")
    assert {item["record_id"] for item in first_edge["provenance"]} == {"session-first-occurrence"}
    assert {item["record_id"] for item in second_edge["provenance"]} == {
        "session-second-occurrence"
    }


def test_direct_builder_is_the_only_public_concrete_builder_for_this_slice():
    import src.parser as parser
    from src.parser import builder

    assert parser.DirectGraphBuilder is builder.DirectGraphBuilder
    assert "CanonicalGraphBuilder" not in parser.__all__
    assert "StructuralGraphBuilder" not in parser.__all__
    assert "CanonicalGraphBuilder" not in builder.__all__
    assert "StructuralGraphBuilder" not in builder.__all__
    assert not hasattr(parser, "CanonicalGraphBuilder")
    assert not hasattr(parser, "StructuralGraphBuilder")


def test_manifest_snapshot_reference_must_match_record_snapshot_id():
    group = _record(
        "Group",
        IDS["group"],
        data={"Members": [{"MemberId": IDS["user"], "MemberType": "User"}]},
    )
    group = NormalizedRecord(
        id=group.id,
        kind=group.kind,
        attributes=group.attributes,
        raw=RawRecord(
            kind=group.raw.kind,
            data=group.raw.data,
            provenance={
                **group.raw.provenance,
                "raw_file": "snapshot:" + "b" * 64 + "/groups.json",
            },
        ),
    )
    with pytest.raises(RecordError, match="does not match snapshot_id"):
        _graph([group, _record("User", IDS["user"])])


def test_graph_snapshot_metadata_must_match_manifest_record_snapshot():
    other_snapshot = "sha256:" + "b" * 64
    group = _record(
        "Group",
        IDS["group"],
        data={"Members": [{"MemberId": IDS["user"], "MemberType": "User"}]},
    )
    group = NormalizedRecord(
        id=group.id,
        kind=group.kind,
        attributes=group.attributes,
        raw=RawRecord(
            kind=group.raw.kind,
            data=group.raw.data,
            provenance={
                **group.raw.provenance,
                "raw_file": "snapshot:" + other_snapshot.removeprefix("sha256:") + "/groups.json",
                "snapshot_id": other_snapshot,
            },
        ),
    )
    with pytest.raises(ValueError, match="metadata.snapshot_id"):
        _graph([group, _record("User", IDS["user"])])


def test_code_version_must_be_explicit():
    builder = DirectGraphBuilder(
        metadata={
            "contract_version": "1.0.0",
            "weight_profile": "unit",
            "snapshot_id": SNAPSHOT,
            "created_at": CREATED,
        }
    )
    with pytest.raises(ValueError, match="metadata.code_version"):
        builder.build([_record("User", IDS["user"])])


@pytest.mark.parametrize("policy", ["skip_record", "log_warning"])
def test_unresolvable_relationship_is_atomic(policy, caplog):
    record = _record(
        "Group",
        IDS["group"],
        data={"Members": [{"MemberId": "S-1-5-21-999-999-999-999", "MemberType": "User"}]},
    )
    graph = _graph([record], error_policy=ErrorPolicy(policy))
    assert graph["nodes"] == []
    assert graph["edges"] == []


def test_host_access_arrays_use_evidence_backed_inference():
    record = _record(
        "Computer",
        IDS["computer"],
        data={
            "LocalAdmins": [{"MemberId": IDS["user"], "MemberType": "User"}],
            "RemoteDesktopUsers": [{"MemberId": IDS["user"], "MemberType": "User"}],
            "PSRemoteUsers": [{"MemberId": IDS["user"], "MemberType": "User"}],
        },
    )
    graph = _graph([record, _record("User", IDS["user"])])
    assert {(edge["kind"], edge["source"], edge["target"]) for edge in graph["edges"]} == {
        ("AdminTo", IDS["user"], IDS["computer"]),
        ("CanPSRemote", IDS["user"], IDS["computer"]),
    }
    assert not any(edge["kind"] == "CanRDP" for edge in graph["edges"])


def test_primary_group_sid_happy_path_user_and_computer():
    user = _record("User", IDS["user"], data={"PrimaryGroupSid": IDS["group"]})
    computer = _record("Computer", IDS["computer"], data={"PrimaryGroupSid": IDS["group"]})
    group = _record("Group", IDS["group"])
    graph = _graph([user, computer, group])
    edges = {(e["source"], e["target"], e["kind"]) for e in graph["edges"]}
    assert (IDS["user"], IDS["group"], "MemberOf") in edges
    assert (IDS["computer"], IDS["group"], "MemberOf") in edges
    user_edge = _edge(graph, IDS["user"], IDS["group"], "MemberOf")
    assert user_edge["provenance"][0]["attribute"] == "PrimaryGroupSid"
    assert user_edge["provenance"][0]["record_id"] == IDS["user"]
    comp_edge = _edge(graph, IDS["computer"], IDS["group"], "MemberOf")
    assert comp_edge["provenance"][0]["attribute"] == "PrimaryGroupSid"
    assert comp_edge["provenance"][0]["record_id"] == IDS["computer"]


def test_primary_group_sid_overlap_deduplication_preserves_provenance():
    user = _record("User", IDS["user"], data={"PrimaryGroupSid": IDS["group"]})
    group = _record(
        "Group",
        IDS["group"],
        data={"Members": [{"MemberId": IDS["user"], "MemberType": "User"}]},
    )
    graph = _graph([user, group])
    member_edges = [e for e in graph["edges"] if e["kind"] == "MemberOf"]
    assert len(member_edges) == 1
    edge = member_edges[0]
    assert edge["source"] == IDS["user"]
    assert edge["target"] == IDS["group"]
    attrs = {p["attribute"] for p in edge["provenance"]}
    assert attrs == {"Members[].MemberId", "PrimaryGroupSid"}
    record_ids = {p["record_id"] for p in edge["provenance"]}
    assert record_ids == {IDS["user"], IDS["group"]}


def test_primary_group_sid_null_or_absent_creates_no_edge():
    user = _record("User", IDS["user"], data={"PrimaryGroupSid": None})
    group = _record("Group", IDS["group"])
    graph = _graph([user, group])
    assert not any(e["kind"] == "MemberOf" for e in graph["edges"])


@pytest.mark.parametrize("policy", ["skip_record", "log_warning"])
def test_primary_group_sid_malformed_skipped_under_policy(policy):
    user = _record("User", IDS["user"], data={"PrimaryGroupSid": 513})
    group = _record("Group", IDS["group"])
    graph = _graph([user, group], error_policy=ErrorPolicy(policy))
    assert [n["id"] for n in graph["nodes"]] == [IDS["group"]]
    assert graph["edges"] == []


def test_primary_group_sid_malformed_fails_fast():
    user = _record("User", IDS["user"], data={"PrimaryGroupSid": 513})
    group = _record("Group", IDS["group"])
    with pytest.raises(RecordError, match="must be a SID string"):
        _graph([user, group], error_policy=ErrorPolicy.FAIL_FAST)

    user_invalid_str = _record("User", IDS["user"], data={"PrimaryGroupSid": "not-a-valid-sid"})
    with pytest.raises(RecordError, match="malformed PrimaryGroupSid SID format"):
        _graph([user_invalid_str, group], error_policy=ErrorPolicy.FAIL_FAST)


def test_primary_group_sid_on_group_or_domain_rejected():
    group_with_pg = _record("Group", IDS["group"], data={"PrimaryGroupSid": IDS["nested"]})
    nested = _record("Group", IDS["nested"])
    with pytest.raises(
        RecordError, match="PrimaryGroupSid evidence is only valid on User or Computer"
    ):
        _graph([group_with_pg, nested], error_policy=ErrorPolicy.FAIL_FAST)


def test_primary_group_sid_target_kind_mismatch():
    user = _record("User", IDS["user"], data={"PrimaryGroupSid": IDS["computer"]})
    computer = _record("Computer", IDS["computer"])
    with pytest.raises(RecordError, match="conflicts with collected node kind"):
        _graph([user, computer], error_policy=ErrorPolicy.FAIL_FAST)


def test_primary_group_sid_unresolvable_target_fails_fast_and_skips():
    user = _record("User", IDS["user"], data={"PrimaryGroupSid": "S-1-5-21-999-999-999-513"})
    with pytest.raises(RecordError, match="unresolvable Group reference"):
        _graph([user], error_policy=ErrorPolicy.FAIL_FAST)
    graph = _graph([user], error_policy=ErrorPolicy.SKIP_RECORD)
    assert graph["nodes"] == []
    assert graph["edges"] == []


def test_primary_group_sid_conflicting_fields_rejected():
    user = _record(
        "User",
        IDS["user"],
        data={
            "PrimaryGroupSid": IDS["group"],
            "primary_group_sid": IDS["nested"],
        },
    )
    group = _record("Group", IDS["group"])
    nested = _record("Group", IDS["nested"])
    with pytest.raises(RecordError, match="conflicting PrimaryGroupSid evidence"):
        _graph([user, group, nested], error_policy=ErrorPolicy.FAIL_FAST)


def test_primary_group_sid_root_null_nested_valid_creates_direct_edge():
    user = _record(
        "User",
        IDS["user"],
        data={
            "PrimaryGroupSid": None,
            "Properties": {"primarygroupsid": IDS["group"]},
        },
    )
    group = _record("Group", IDS["group"])
    graph = _graph([user, group])
    edge = _edge(graph, IDS["user"], IDS["group"], "MemberOf")
    assert edge["provenance"][0]["attribute"] == "Properties.primarygroupsid"
    assert edge["provenance"][0]["record_id"] == IDS["user"]


def test_primary_group_sid_root_valid_nested_conflicting_rejected():
    user = _record(
        "User",
        IDS["user"],
        data={
            "PrimaryGroupSid": IDS["group"],
            "Properties": {"primarygroupsid": IDS["nested"]},
        },
    )
    group = _record("Group", IDS["group"])
    nested = _record("Group", IDS["nested"])
    with pytest.raises(RecordError, match="conflicting PrimaryGroupSid evidence"):
        _graph([user, group, nested], error_policy=ErrorPolicy.FAIL_FAST)


def test_primary_group_sid_identical_root_and_nested_accepted_with_deterministic_provenance():
    user = _record(
        "User",
        IDS["user"],
        data={
            "PrimaryGroupSid": IDS["group"],
            "Properties": {"primarygroupsid": IDS["group"]},
        },
    )
    group = _record("Group", IDS["group"])
    graph = _graph([user, group])
    member_edges = [e for e in graph["edges"] if e["kind"] == "MemberOf"]
    assert len(member_edges) == 1
    edge = member_edges[0]
    assert edge["source"] == IDS["user"]
    assert edge["target"] == IDS["group"]
    assert edge["provenance"][0]["attribute"] == "PrimaryGroupSid"
    assert len(edge["provenance"]) == 1


def test_primary_group_sid_nested_on_group_rejected():
    group_with_nested_pg = _record(
        "Group",
        IDS["group"],
        data={"Properties": {"primarygroupsid": IDS["nested"]}},
    )
    nested = _record("Group", IDS["nested"])
    with pytest.raises(
        RecordError, match="PrimaryGroupSid evidence is only valid on User or Computer"
    ):
        _graph([group_with_nested_pg, nested], error_policy=ErrorPolicy.FAIL_FAST)
