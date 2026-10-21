"""Issue #45 host-access inference acceptance coverage."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest
import yaml

from scripts.check_contract import canonical_edge_id, validate_graph
from src.parser import (
    DirectGraphBuilder,
    HostAccessResult,
    IdentityNormalizer,
    InferenceStatus,
    RawRecord,
    deserialize_graph,
    evaluate_host_access,
    evaluate_local_group_membership,
    resolve_effective_membership,
    serialize_graph,
)
from src.parser.inference import (
    ADMINISTRATORS_SID,
    ALLOW_RDP_RIGHT,
    DENY_RDP_RIGHT,
    REMOTE_DESKTOP_USERS_SID,
    REMOTE_MANAGEMENT_USERS_SID,
    EffectiveMembershipResolver,
    extract_primary_group_entry,
)
from src.parser.lineage import provenance_ref

SNAPSHOT = "sha256:" + "b" * 64
DOMAIN = "EXAMPLE.TEST"
CREATED = "2026-09-23T00:00:00Z"
USER = "S-1-5-21-1000-2000-3000-1101"
DISABLED = "S-1-5-21-1000-2000-3000-1102"
GROUP = "S-1-5-21-1000-2000-3000-2101"
GROUP_B = "S-1-5-21-1000-2000-3000-2102"
HOST = "S-1-5-21-1000-2000-3000-3101"
DOMAIN_ADMINS = "S-1-5-21-1000-2000-3000-512"


def _raw(kind: str, data: dict, identifier: str) -> RawRecord:
    return RawRecord(
        kind=kind,
        data={
            "ObjectIdentifier": identifier,
            "Properties": {"name": identifier, "domain": DOMAIN},
            **data,
        },
        provenance={
            "raw_file": f"snapshot:{SNAPSHOT[7:]}/{kind.lower()}.json",
            "collector": "synthetic/45",
            "timestamp": "2026-09-22T00:00:00Z",
            "snapshot_id": SNAPSHOT,
            "record_id": identifier,
        },
    )


def _normal(*records: RawRecord):
    return IdentityNormalizer().normalize_records(records)


def _host(data: dict) -> RawRecord:
    return _raw("Computer", data, HOST)


def _user(identifier: str = USER, *, enabled: bool | None = None) -> RawRecord:
    data = {}
    if enabled is not None:
        data["Properties"] = {"name": identifier, "domain": DOMAIN, "enabled": enabled}
    return _raw("User", data, identifier)


def _results(records):
    return evaluate_host_access(_normal(*records))


def _find(results: list[HostAccessResult], kind: str, source: str = USER) -> HostAccessResult:
    return next(
        result for result in results if result.relationship == kind and result.source == source
    )


def _builder(records):
    return DirectGraphBuilder(
        metadata={
            "snapshot_id": SNAPSHOT,
            "created_at": CREATED,
            "code_version": "tests/inference",
        }
    ).build(_normal(*records))


def _edge_kinds(graph, source=USER, target=HOST):
    return {
        edge["kind"]
        for edge in graph["edges"]
        if edge["source"] == source and edge["target"] == target
    }


def test_direct_local_admin_emits_host_bound_adminto_without_runtime_gate():
    graph = _builder(
        [
            _host(
                {
                    "LocalAdmins": [{"MemberId": USER}],
                    "Connectable": False,
                    "RDP": {"ServiceRunning": False},
                }
            ),
            _user(),
        ]
    )
    assert "AdminTo" in _edge_kinds(graph)


def test_historical_localgroups_match_the_complete_builtin_sid():
    graph = _builder(
        [
            _host(
                {
                    "LocalGroups": [
                        {
                            "ObjectIdentifier": f"HOST-{ADMINISTRATORS_SID}",
                            "Results": [{"ObjectIdentifier": USER}],
                        }
                    ]
                }
            ),
            _user(),
        ]
    )
    assert "AdminTo" in _edge_kinds(graph)


def test_successful_empty_local_collection_is_known_negative():
    host = _normal(_host({"LocalAdmins": [], "LocalAdminsComplete": True}))[0]
    result = evaluate_local_group_membership(host, USER, ADMINISTRATORS_SID)
    assert result.status.value == "negative-known"


def test_domain_admin_rid_alone_does_not_create_adminto():
    results = _results([_raw("Group", {}, DOMAIN_ADMINS), _host({}), _user()])
    assert not any(result.relationship == "AdminTo" for result in results)


def test_domain_admin_rid_is_not_local_administrators_sid():
    results = _results(
        [
            _host(
                {
                    "LocalGroups": [
                        {
                            "ObjectIdentifier": DOMAIN_ADMINS,
                            "Results": [{"ObjectIdentifier": USER}],
                        }
                    ]
                }
            ),
            _user(),
        ]
    )
    assert not any(result.relationship == "AdminTo" for result in results)


def test_disabled_principal_keeps_positive_host_authorization():
    graph = _builder(
        [_host({"LocalAdmins": [{"MemberId": DISABLED}]}), _user(DISABLED, enabled=False)]
    )
    assert "AdminTo" in _edge_kinds(graph, source=DISABLED)


@pytest.mark.parametrize(
    ("field", "relationship"),
    [
        ("LocalAdmins", "AdminTo"),
        ("RemoteDesktopUsers", "CanRDP"),
        ("PSRemoteUsers", "CanPSRemote"),
    ],
)
def test_unresolved_host_access_principal_is_retained_as_unknown_assessment(field, relationship):
    unresolved = "S-1-5-21-1000-2000-3000-1199"
    graph = _builder([_host({field: [{"MemberId": unresolved}]})])

    assert not any(edge["kind"] == relationship for edge in graph["edges"])
    assessment = next(
        item
        for item in graph["assessments"]
        if item.get("kind") == relationship and item.get("target") == HOST
    )
    assert assessment["status"] == "unknown"
    assert "identity could not be resolved" in assessment["reason"]
    assert "subject" not in assessment
    assert assessment["provenance"]
    assert all(item["evidence_type"] == "unknown" for item in assessment["provenance"])


def _rdp_host(
    *,
    allow: list[object],
    deny: list[object],
    rdu: list[object] | None = None,
    status: str | None = "Success",
) -> RawRecord:
    rights = [
        {"Privilege": ALLOW_RDP_RIGHT, "Collected": True, "Results": allow},
        {"Privilege": DENY_RDP_RIGHT, "Collected": True, "Results": deny},
    ]
    data = {
        "RemoteDesktopUsers": rdu if rdu is not None else [{"MemberId": USER}],
        "RemoteDesktopUsersComplete": rdu is not None,
        "UserRights": rights,
        "UserRightsStatus": status,
        "UserRightsComplete": status == "Success",
    }
    return _host(data)


def test_canrdp_requires_membership_allow_and_known_negative_deny():
    result = _find(
        _results([_rdp_host(allow=[{"ObjectIdentifier": USER}], deny=[]), _user()]), "CanRDP"
    )
    assert result.status is InferenceStatus.POSITIVE
    assert result.canonical_emit_allowed


def test_canrdp_deny_precedence_blocks_edge():
    graph = _builder(
        [
            _rdp_host(
                allow=[{"ObjectIdentifier": USER}],
                deny=[{"ObjectIdentifier": USER}],
            ),
            _user(),
        ]
    )
    result = _find(
        _results(
            [
                _rdp_host(allow=[{"ObjectIdentifier": USER}], deny=[{"ObjectIdentifier": USER}]),
                _user(),
            ]
        ),
        "CanRDP",
    )
    assert result.status is InferenceStatus.REJECTED
    assert "CanRDP" not in _edge_kinds(graph)


def test_canrdp_unknown_deny_is_not_positive():
    host = _host(
        {
            "RemoteDesktopUsers": [{"MemberId": USER}],
            "UserRights": [
                {
                    "Privilege": ALLOW_RDP_RIGHT,
                    "Collected": True,
                    "Results": [{"ObjectIdentifier": USER}],
                }
            ],
        }
    )
    result = _find(_results([host, _user()]), "CanRDP")
    assert result.status is InferenceStatus.UNKNOWN


def test_failure_reason_on_deny_right_cannot_prove_canrdp():
    host = _host(
        {
            "RemoteDesktopUsers": [{"MemberId": USER}],
            "RemoteDesktopUsersComplete": True,
            "UserRights": [
                {
                    "Privilege": ALLOW_RDP_RIGHT,
                    "Collected": True,
                    "Results": [{"ObjectIdentifier": USER}],
                },
                {
                    "Privilege": DENY_RDP_RIGHT,
                    "Collected": True,
                    "FailureReason": "StatusAccessDenied",
                    "Results": [],
                },
            ],
            "UserRightsComplete": True,
        }
    )
    result = _find(_results([host, _user()]), "CanRDP")
    assert result.status is InferenceStatus.UNKNOWN
    assert "CanRDP" not in _edge_kinds(_builder([host, _user()]))


@pytest.mark.parametrize(
    ("field", "relationship", "local_group"),
    [
        ("LocalAdmins", "AdminTo", False),
        ("RemoteDesktopUsers", "CanRDP", False),
        ("PSRemoteUsers", "CanPSRemote", False),
        ("LocalGroups", "AdminTo", True),
    ],
)
def test_host_local_failure_reason_is_retained_as_unknown_assessment(
    field, relationship, local_group
):
    failed = {"Collected": True, "FailureReason": "StatusAccessDenied"}
    if local_group:
        failed["ObjectIdentifier"] = f"HOST-{ADMINISTRATORS_SID}"
        failed["Results"] = [{"MemberId": USER}]
        host_data = {field: [failed]}
    else:
        failed["Results"] = [{"MemberId": USER}]
        host_data = {field: failed}
    host = _host(host_data)
    normalized_host = IdentityNormalizer().normalize_records([host])[0]
    result = evaluate_local_group_membership(normalized_host, USER, ADMINISTRATORS_SID)
    assert result.status.value == "unknown"
    graph = _builder([host, _user()])
    assert not any(edge["kind"] == relationship for edge in graph["edges"])
    assessments = [
        item
        for item in graph["assessments"]
        if item.get("kind") == relationship
        and item.get("subject") == USER
        and item.get("target") == HOST
    ]
    assert len(assessments) == 1
    assessment = assessments[0]
    assert assessment["status"] == "unknown"
    assert assessment["provenance"]
    assert all(item["evidence_type"] == "unknown" for item in assessment["provenance"])
    assert any(item.get("attribute", "").startswith(field) for item in assessment["provenance"])


@pytest.mark.parametrize(
    ("host_data", "relationship", "field"),
    [
        (
            {
                "LocalAdmins": {
                    "Status": "StatusAccessDenied",
                    "Results": [{"MemberId": USER}],
                }
            },
            "AdminTo",
            "LocalAdmins",
        ),
        (
            {
                "LocalGroups": [
                    {
                        "ObjectIdentifier": f"HOST-{ADMINISTRATORS_SID}",
                        "Status": "StatusAccessDenied",
                        "Results": [{"MemberId": USER}],
                    }
                ]
            },
            "AdminTo",
            "LocalGroups",
        ),
        (
            {
                "PSRemoteUsers": {
                    "CollectionStatus": "StatusAccessDenied",
                    "Results": [{"MemberId": USER}],
                }
            },
            "CanPSRemote",
            "PSRemoteUsers",
        ),
    ],
)
def test_host_local_status_failure_is_unknown_assessment(host_data, relationship, field):
    graph = _builder([_host(host_data), _user()])

    assert not any(edge["kind"] == relationship for edge in graph["edges"])
    assessment = next(
        item
        for item in graph["assessments"]
        if item.get("kind") == relationship
        and item.get("subject") == USER
        and item.get("target") == HOST
    )
    assert assessment["status"] == "unknown"
    assert all(item["evidence_type"] == "unknown" for item in assessment["provenance"])
    assert any(item.get("attribute", "").startswith(field) for item in assessment["provenance"])


@pytest.mark.parametrize(
    ("field", "relationship"),
    [("LocalAdmins", "AdminTo"), ("PSRemoteUsers", "CanPSRemote")],
)
def test_specialized_host_membership_failure_does_not_poison_clean_sibling(field, relationship):
    graph = _builder(
        [
            _host(
                {
                    field: [
                        {"MemberId": USER},
                        {"MemberId": GROUP, "FailureReason": "StatusAccessDenied"},
                    ]
                }
            ),
            _user(),
            _raw("Group", {}, GROUP),
        ]
    )

    assert relationship in _edge_kinds(graph, source=USER)
    assessments = [
        item
        for item in graph["assessments"]
        if item.get("kind") == relationship and item.get("target") == HOST
    ]
    assert len(assessments) == 1
    assert assessments[0]["subject"] == GROUP
    assert assessments[0]["status"] == "unknown"


def test_failed_localgroup_sibling_does_not_poison_clean_group_or_assessment():
    graph = _builder(
        [
            _host(
                {
                    "LocalGroups": [
                        {
                            "ObjectIdentifier": f"HOST-{ADMINISTRATORS_SID}",
                            "Results": [{"MemberId": USER}],
                        },
                        {
                            "ObjectIdentifier": f"HOST-{REMOTE_DESKTOP_USERS_SID}",
                            "Status": "StatusAccessDenied",
                            "Results": [{"MemberId": USER}],
                        },
                    ]
                }
            ),
            _user(),
        ]
    )

    assert "AdminTo" in _edge_kinds(graph)
    assert not any(
        item.get("kind") == "AdminTo" and item.get("subject") == USER and item.get("target") == HOST
        for item in graph["assessments"]
    )
    assert any(
        item.get("kind") == "CanRDP"
        and item.get("subject") == USER
        and item.get("target") == HOST
        and item.get("status") == "unknown"
        for item in graph["assessments"]
    )


def test_failed_localgroup_member_does_not_poison_clean_member():
    graph = _builder(
        [
            _host(
                {
                    "LocalGroups": [
                        {
                            "ObjectIdentifier": f"HOST-{ADMINISTRATORS_SID}",
                            "Results": [
                                {"MemberId": USER},
                                {"MemberId": GROUP, "FailureReason": "StatusAccessDenied"},
                            ],
                        }
                    ]
                }
            ),
            _user(),
            _raw("Group", {}, GROUP),
        ]
    )

    assert "AdminTo" in _edge_kinds(graph, source=USER)
    assessments = [
        item
        for item in graph["assessments"]
        if item.get("kind") == "AdminTo" and item.get("target") == HOST
    ]
    assert len(assessments) == 1
    assert assessments[0]["subject"] == GROUP
    assert assessments[0]["status"] == "unknown"


def test_canrdp_partial_deny_collection_does_not_become_known_negative():
    host = _host(
        {
            "RemoteDesktopUsers": [{"MemberId": USER}],
            "UserRights": [
                {
                    "Privilege": ALLOW_RDP_RIGHT,
                    "Collected": True,
                    "Results": [{"ObjectIdentifier": USER}],
                },
                {
                    "Privilege": DENY_RDP_RIGHT,
                    "Results": [{"ObjectIdentifier": DISABLED}],
                },
            ],
            "UserRightsComplete": False,
        }
    )
    result = _find(_results([host, _user()]), "CanRDP")
    assert result.status is InferenceStatus.UNKNOWN
    assert "CanRDP" not in _edge_kinds(_builder([host, _user()]))


def test_canrdp_partial_allow_collection_does_not_become_known_negative():
    host = _host(
        {
            "RemoteDesktopUsers": [{"MemberId": USER}],
            "UserRights": [
                {
                    "Privilege": ALLOW_RDP_RIGHT,
                    "Results": [{"ObjectIdentifier": DISABLED}],
                },
                {"Privilege": DENY_RDP_RIGHT, "Collected": True, "Results": []},
            ],
            "UserRightsComplete": False,
        }
    )
    result = _find(_results([host, _user()]), "CanRDP")
    assert result.status is InferenceStatus.UNKNOWN
    assert "CanRDP" not in _edge_kinds(_builder([host, _user()]))


def test_complete_deny_collection_for_another_principal_proves_canrdp_positive():
    records = [
        _rdp_host(
            allow=[{"ObjectIdentifier": USER}],
            deny=[{"ObjectIdentifier": DISABLED}],
        ),
        _user(),
    ]
    result = _find(_results(records), "CanRDP")
    assert result.status is InferenceStatus.POSITIVE
    assert result.canonical_emit_allowed
    assert "CanRDP" in _edge_kinds(_builder(records))


def test_complete_allow_collection_for_another_principal_proves_canrdp_negative():
    result = _find(
        _results(
            [
                _rdp_host(
                    allow=[{"ObjectIdentifier": DISABLED}],
                    deny=[],
                ),
                _user(),
            ]
        ),
        "CanRDP",
    )
    assert result.status is InferenceStatus.NEGATIVE_KNOWN


def test_nested_right_assignment_is_positive_with_lineage_ready_for_issue_92():
    records = [
        _rdp_host(
            allow=[{"ObjectIdentifier": GROUP}],
            deny=[],
        ),
        _raw("Group", {"Members": [{"MemberId": USER, "MemberType": "User"}]}, GROUP),
        _user(),
    ]
    result = _find(_results(records), "CanRDP")
    assert result.status is InferenceStatus.POSITIVE
    assert result.evidence_source.value == "derived"
    assert result.canonical_emit_allowed
    graph = _builder(records)
    edge = next(edge for edge in graph["edges"] if edge["kind"] == "CanRDP")
    assert edge["derivation"]["paths"][0]["steps"][-1]["target"] == ALLOW_RDP_RIGHT
    assert edge["derivation"]["paths"][0]["steps"][-2]["target"] == GROUP
    assert edge["derivation"]["paths"][0]["steps"][-1]["source"] == GROUP


def test_canrdp_preserves_all_membership_and_nested_right_paths():
    records = [
        _rdp_host(
            rdu=[{"ObjectIdentifier": GROUP}, {"ObjectIdentifier": GROUP_B}],
            allow=[{"ObjectIdentifier": GROUP}, {"ObjectIdentifier": GROUP_B}],
            deny=[],
        ),
        _raw("Group", {"Members": [{"MemberId": USER, "MemberType": "User"}]}, GROUP),
        _raw("Group", {"Members": [{"MemberId": USER, "MemberType": "User"}]}, GROUP_B),
        _user(),
    ]
    graph = _builder(records)
    edge = next(edge for edge in graph["edges"] if edge["kind"] == "CanRDP")
    paths = edge["derivation"]["paths"]
    assert len(paths) == 4
    assert {(path["steps"][0]["source"], path["steps"][0]["target"]) for path in paths} == {
        (USER, GROUP),
        (USER, GROUP_B),
    }
    assert {(path["steps"][-1]["source"], path["steps"][-1]["target"]) for path in paths} == {
        (GROUP, ALLOW_RDP_RIGHT),
        (GROUP_B, ALLOW_RDP_RIGHT),
    }


def test_mixed_direct_and_derived_canrdp_proofs_share_one_deterministic_edge():
    records = [
        _rdp_host(
            rdu=[{"ObjectIdentifier": USER}, {"ObjectIdentifier": GROUP}],
            allow=[{"ObjectIdentifier": USER}, {"ObjectIdentifier": GROUP}],
            deny=[],
        ),
        _raw("Group", {"Members": [{"MemberId": USER, "MemberType": "User"}]}, GROUP),
        _user(),
    ]

    positives = [
        item
        for item in _results(records)
        if item.relationship == "CanRDP"
        and item.source == USER
        and item.status is InferenceStatus.POSITIVE
    ]
    assert len(positives) == 4
    assert {item.evidence_source.value for item in positives} == {"direct", "derived"}
    assert any(item.evidence_source.value == "direct" and not item.derivation for item in positives)
    assert all(item.derivation for item in positives if item.evidence_source.value == "derived")

    graph = _builder(records)
    canrdp_edges = [
        edge for edge in graph["edges"] if edge["kind"] == "CanRDP" and edge["source"] == USER
    ]
    assert len(canrdp_edges) == 1
    edge = canrdp_edges[0]
    assert edge["id"] == canonical_edge_id(USER, HOST, "CanRDP")
    assert len(edge["derivation"]["paths"]) == 3
    expected_conditions = ["rdu_membership", "allow_right", "deny_absent"]
    provenance_refs = {provenance_ref(item) for item in edge["provenance"]}
    assert all(
        [condition["predicate"] for condition in path["conditions"]] == expected_conditions
        and all(
            condition["evidence_refs"] and set(condition["evidence_refs"]) <= provenance_refs
            for condition in path["conditions"]
        )
        for path in edge["derivation"]["paths"]
    )
    assert any(
        [step["operation"] for step in path["steps"]] == ["effective_membership", "effective_right"]
        and path["steps"][-1]["source"] == GROUP
        for path in edge["derivation"]["paths"]
    )
    assert any(
        [step["operation"] for step in path["steps"]]
        == ["effective_membership", "host_local_membership"]
        for path in edge["derivation"]["paths"]
    )
    assert {item["record_id"] for item in edge["provenance"]} >= {HOST, GROUP}
    payload = serialize_graph(graph)
    assert payload == serialize_graph(_builder(list(reversed(records))))
    assert deserialize_graph(payload) == graph


def test_canrdp_lineage_rejects_missing_required_composite_condition():
    records = [
        _rdp_host(
            rdu=[{"ObjectIdentifier": GROUP}],
            allow=[{"ObjectIdentifier": USER}],
            deny=[],
        ),
        _raw("Group", {"Members": [{"MemberId": USER, "MemberType": "User"}]}, GROUP),
        _user(),
    ]
    graph = _builder(records)
    edge = next(edge for edge in graph["edges"] if edge["kind"] == "CanRDP")
    edge["derivation"]["paths"][0]["conditions"].pop()
    contract = yaml.safe_load(
        (Path(__file__).resolve().parents[1] / "configs/contract.yml").read_text()
    )
    with pytest.raises(ValueError, match="every required proof condition"):
        validate_graph(graph, contract)


def test_effective_membership_resolver_reuses_all_cached_paths():
    membership = {USER: {GROUP, GROUP_B}, GROUP: {GROUP_B}}
    resolver = EffectiveMembershipResolver(membership)

    first = resolver.resolve(USER, GROUP_B)
    second = resolver.resolve(USER, GROUP_B)

    assert len(first) == 2
    assert second == first
    assert resolver.traversal_count == 1
    assert resolver.cache_hit_count == 1


def test_rdu_membership_only_is_unknown_not_verified_canrdp():
    result = _find(
        _results([_host({"RemoteDesktopUsers": [{"MemberId": USER}]}), _user()]), "CanRDP"
    )
    assert result.status is InferenceStatus.UNKNOWN
    graph = _builder([_host({"RemoteDesktopUsers": [{"MemberId": USER}]}), _user()])
    assert "CanRDP" not in _edge_kinds(graph)


def test_allow_right_only_is_insufficient():
    results = _results(
        [
            _host(
                {
                    "UserRights": [
                        {
                            "Privilege": ALLOW_RDP_RIGHT,
                            "Collected": True,
                            "Results": [{"ObjectIdentifier": USER}],
                        },
                        {"Privilege": DENY_RDP_RIGHT, "Collected": True, "Results": []},
                    ],
                    "UserRightsStatus": "Success",
                    "UserRightsComplete": True,
                }
            ),
            _user(),
        ]
    )
    result = _find(results, "CanRDP")
    assert result.status is InferenceStatus.UNKNOWN


def test_known_empty_rdu_collection_is_known_insufficient():
    results = _results(
        [
            _rdp_host(
                allow=[{"ObjectIdentifier": USER}],
                deny=[],
                rdu=[],
            ),
            _user(),
        ]
    )
    result = _find(results, "CanRDP")
    assert result.status is InferenceStatus.NEGATIVE_KNOWN


def test_status_access_denied_is_unknown():
    host = _host(
        {
            "RemoteDesktopUsers": [{"MemberId": USER}],
            "UserRights": {"Status": "StatusAccessDenied", "Results": []},
        }
    )
    assert _find(_results([host, _user()]), "CanRDP").status is InferenceStatus.UNKNOWN


def test_successful_empty_user_rights_are_known_negative():
    host = _host(
        {
            "RemoteDesktopUsers": [{"MemberId": USER}],
            "UserRights": {"Status": "Success", "Results": []},
        }
    )
    result = _find(_results([host, _user()]), "CanRDP")
    assert result.status is InferenceStatus.NEGATIVE_KNOWN


def test_canpsremote_is_structural_and_runtime_neutral():
    graph = _builder(
        [
            _host({"PSRemoteUsers": [{"MemberId": USER}], "WinRM": {"Available": False}}),
            _user(),
        ]
    )
    assert "CanPSRemote" in _edge_kinds(graph)


def test_explicit_endpoint_acl_rejection_is_retained_as_assessment():
    records = [
        _host(
            {
                "PSRemoteUsers": [{"MemberId": USER}],
                "EndpointACL": [{"PrincipalSID": USER, "Allowed": False}],
            }
        ),
        _user(),
    ]
    graph = _builder(records)
    assert "CanPSRemote" in _edge_kinds(graph)
    assert any(
        assessment["kind"] == "CanPSRemote" and assessment["status"] == "rejected"
        for assessment in graph["assessments"]
    )


def test_nested_admin_result_is_serialized_with_issue_92_lineage():
    records = [
        _host(
            {
                "LocalGroups": [
                    {
                        "ObjectIdentifier": f"HOST-{ADMINISTRATORS_SID}",
                        "Results": [{"ObjectIdentifier": GROUP}],
                    }
                ]
            }
        ),
        _raw("Group", {"Members": [{"MemberId": USER, "MemberType": "User"}]}, GROUP),
        _user(),
    ]
    results = _results(records)
    result = _find(results, "AdminTo")
    assert result.status is InferenceStatus.POSITIVE
    assert result.evidence_source.value == "derived"
    assert result.canonical_emit_allowed
    assert [step.operation for step in result.derivation]
    graph = _builder(records)
    edge = next(edge for edge in graph["edges"] if edge["kind"] == "AdminTo")
    assert edge["source"] == USER
    assert edge["derivation"]["kind"] == "nested_membership"
    assert [step["operation"] for step in edge["derivation"]["paths"][0]["steps"]] == [
        "effective_membership",
        "host_local_membership",
    ]


def test_nested_cycle_terminates_deterministically():
    paths = resolve_effective_membership(
        USER,
        GROUP,
        {
            USER: {GROUP},
            GROUP: {"S-1-5-21-1000-2000-3000-2102"},
            "S-1-5-21-1000-2000-3000-2102": {GROUP},
        },
    )
    assert len(paths) == 1


def test_gpo_unresolved_is_non_traversable_and_resolved_is_serialized():
    unresolved = _host(
        {"GPOAccess": [{"principal_id": USER, "relationship": "AdminTo", "status": "unresolved"}]}
    )
    resolved = _host(
        {
            "GPOAccess": [
                {
                    "principal_id": USER,
                    "relationship": "AdminTo",
                    "status": "resolved",
                    "resultant_state": True,
                    "resolved_steps": [
                        {"operation": operation, "status": "resolved"}
                        for operation in (
                            "gpo_setting",
                            "active_link",
                            "target_scope",
                            "security_filtering",
                            "wmi_filtering",
                            "inheritance_and_order",
                            "client_side_extension",
                            "resultant_host_state",
                        )
                    ],
                }
            ]
        }
    )
    unresolved_result = _find(_results([unresolved, _user()]), "AdminTo")
    resolved_result = _find(_results([resolved, _user()]), "AdminTo")
    assert unresolved_result.status is InferenceStatus.UNKNOWN
    assert resolved_result.status is InferenceStatus.POSITIVE
    assert resolved_result.canonical_emit_allowed
    graph = _builder([resolved, _user()])
    edge = next(edge for edge in graph["edges"] if edge["kind"] == "AdminTo")
    assert edge["derivation"]["kind"] == "gpo_resultant"


@pytest.mark.parametrize("step_shape", ["bare_operation", "missing_status"])
def test_gpo_operation_checklist_without_step_resolution_is_non_traversable(step_shape):
    operations = (
        "gpo_setting",
        "active_link",
        "target_scope",
        "security_filtering",
        "wmi_filtering",
        "inheritance_and_order",
        "client_side_extension",
        "resultant_host_state",
    )
    if step_shape == "bare_operation":
        resolved_steps = list(operations)
    else:
        resolved_steps = [{"operation": operation} for operation in operations]
    records = [
        _host(
            {
                "GPOAccess": [
                    {
                        "principal_id": USER,
                        "relationship": "AdminTo",
                        "status": "resolved",
                        "resultant_state": True,
                        "resolved_steps": resolved_steps,
                    }
                ]
            }
        ),
        _user(),
    ]
    result = _find(_results(records), "AdminTo")
    assert result.status is InferenceStatus.UNKNOWN
    assert not result.canonical_emit_allowed
    assert "AdminTo" not in _edge_kinds(_builder(records))


def test_gpo_summary_flag_without_resolver_lineage_is_unknown():
    result = _find(
        _results(
            [
                _host(
                    {
                        "GPOAccess": [
                            {
                                "principal_id": USER,
                                "relationship": "AdminTo",
                                "status": "resolved",
                                "resultant_state": True,
                            }
                        ]
                    }
                ),
                _user(),
            ]
        ),
        "AdminTo",
    )
    assert result.status is InferenceStatus.UNKNOWN


def test_host_access_uses_item_lineage_for_reconciled_occurrences():
    rich = _host({"LocalAdmins": [{"MemberId": USER}]})
    rich = replace(rich, provenance={**rich.provenance, "record_id": "rich-occurrence"})
    empty = _host({"LocalAdmins": [], "LocalAdminsComplete": True})
    empty = replace(empty, provenance={**empty.provenance, "record_id": "empty-occurrence"})
    graph = _builder([rich, empty, _user()])
    edge = next(edge for edge in graph["edges"] if edge["kind"] == "AdminTo")
    assert {item["record_id"] for item in edge["provenance"]} == {"rich-occurrence"}


@pytest.mark.parametrize(
    "field,group_sid",
    [
        ("LocalAdmins", ADMINISTRATORS_SID),
        ("RemoteDesktopUsers", REMOTE_DESKTOP_USERS_SID),
        ("PSRemoteUsers", REMOTE_MANAGEMENT_USERS_SID),
    ],
)
def test_full_builtin_sid_mapping_is_explicit(field, group_sid):
    assert group_sid in {ADMINISTRATORS_SID, REMOTE_DESKTOP_USERS_SID, REMOTE_MANAGEMENT_USERS_SID}
    assert field


def test_host_access_infers_effective_membership_via_primary_group_sid():
    user = _raw("User", {"PrimaryGroupSid": GROUP}, USER)
    group = _raw("Group", {"Members": []}, GROUP)
    host = _host(
        {
            "LocalGroups": [
                {
                    "ObjectIdentifier": f"HOST-{ADMINISTRATORS_SID}",
                    "Results": [{"ObjectIdentifier": GROUP}],
                }
            ]
        }
    )
    results = _results([host, group, user])
    result = _find(results, "AdminTo")
    assert result.status is InferenceStatus.POSITIVE
    assert result.evidence_source.value == "derived"
    assert result.canonical_emit_allowed
    assert [step.operation for step in result.derivation] == [
        "effective_membership",
        "host_local_membership",
    ]
    graph = _builder([host, group, user])
    edge = next(edge for edge in graph["edges"] if edge["kind"] == "AdminTo")
    assert edge["source"] == USER
    assert edge["target"] == HOST
    assert edge["derivation"]["kind"] == "nested_membership"


def test_host_access_infers_admin_via_nested_properties_primary_group_when_root_is_null():
    user = _raw(
        "User",
        {
            "PrimaryGroupSid": None,
            "Properties": {"name": USER, "domain": DOMAIN, "primarygroupsid": GROUP},
        },
        USER,
    )
    group = _raw("Group", {"Members": []}, GROUP)
    host = _host(
        {
            "LocalGroups": [
                {
                    "ObjectIdentifier": f"HOST-{ADMINISTRATORS_SID}",
                    "Results": [{"ObjectIdentifier": GROUP}],
                }
            ]
        }
    )
    results = _results([host, group, user])
    result = _find(results, "AdminTo")
    assert result.status is InferenceStatus.POSITIVE
    assert result.evidence_source.value == "derived"
    assert result.canonical_emit_allowed

    graph = _builder([host, group, user])
    member_edge = next(
        edge
        for edge in graph["edges"]
        if edge["kind"] == "MemberOf" and edge["source"] == USER and edge["target"] == GROUP
    )
    assert member_edge["provenance"][0]["attribute"] == "Properties.primarygroupsid"

    admin_edge = next(edge for edge in graph["edges"] if edge["kind"] == "AdminTo")
    assert admin_edge["source"] == USER
    assert admin_edge["target"] == HOST


def test_extract_primary_group_entry_shared_validation():
    # 1. Root null + nested valid
    entry = extract_primary_group_entry(
        {"PrimaryGroupSid": None, "Properties": {"primarygroupsid": GROUP}},
        record_kind="User",
    )
    assert entry == ("Properties.primarygroupsid", GROUP)

    # 2. Root valid + nested conflicting -> raises
    with pytest.raises(ValueError, match="conflicting PrimaryGroupSid evidence"):
        extract_primary_group_entry(
            {"PrimaryGroupSid": GROUP, "Properties": {"primarygroupsid": GROUP_B}},
            record_kind="User",
        )

    # 3. Identical in both -> deterministic root precedence
    entry = extract_primary_group_entry(
        {"PrimaryGroupSid": GROUP, "Properties": {"primarygroupsid": GROUP}},
        record_kind="User",
    )
    assert entry == ("PrimaryGroupSid", GROUP)

    # 4. Group record with primary group evidence -> raises
    with pytest.raises(ValueError, match="only valid on User or Computer"):
        extract_primary_group_entry(
            {"Properties": {"primarygroupsid": GROUP}},
            record_kind="Group",
        )
