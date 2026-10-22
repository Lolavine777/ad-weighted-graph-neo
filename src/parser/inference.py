"""Evidence-backed host-access inference.

The direct graph builder owns raw, source-backed edges.  This module owns the
small amount of domain logic needed to turn host-local membership and user
rights into ``AdminTo``, ``CanRDP`` and ``CanPSRemote`` decisions.

The important distinction here is that a primitive can be positive,
known-negative, or unknown.  A missing collection is never treated as an empty
collection.  Nested and GPO-derived results retain an ordered explanation, but
their canonical edge emission is controlled by the canonical lineage serializer.
"""

from __future__ import annotations

import json
from collections import defaultdict, deque
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from . import NormalizedRecord, RawProvenance
from .adapters.bloodhound_v3 import parse_qualified_sid
from .identity_fields import lookup_raw_identifier
from .scopes import is_valid_sid, parse_scoped_sid
from .well_known_principals import boundary_group

ADMINISTRATORS_SID = "S-1-5-32-544"
REMOTE_DESKTOP_USERS_SID = "S-1-5-32-555"
REMOTE_MANAGEMENT_USERS_SID = "S-1-5-32-580"
ALLOW_RDP_RIGHT = "SeRemoteInteractiveLogonRight"
DENY_RDP_RIGHT = "SeDenyRemoteInteractiveLogonRight"
GPO_OPERATIONS = (
    "gpo_setting",
    "active_link",
    "target_scope",
    "security_filtering",
    "wmi_filtering",
    "inheritance_and_order",
    "client_side_extension",
    "resultant_host_state",
)


def _lineage_key(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _lineage_field_key(field: str) -> str:
    return field.replace("[]", "")


class PrimitiveStatus(StrEnum):
    POSITIVE = "positive"
    NEGATIVE_KNOWN = "negative-known"
    UNKNOWN = "unknown"


class InferenceStatus(StrEnum):
    POSITIVE = "positive"
    NEGATIVE_KNOWN = "negative-known"
    UNKNOWN = "unknown"
    REJECTED = "rejected"


class EvidenceSource(StrEnum):
    DIRECT = "direct"
    DERIVED = "derived"
    UNKNOWN = "unknown"
    REJECTED = "rejected"


@dataclass(frozen=True)
class PrimitiveEvidence:
    """One primitive observation, including the record that supplied it."""

    status: PrimitiveStatus
    record: NormalizedRecord | None
    field: str
    item: object | None = None
    reason: str = ""
    resolved_reference: str | None = None

    @property
    def provenance(self) -> tuple[RawProvenance, ...]:
        if self.record is None:
            return ()
        if self.item is not None and self.record.evidence_lineage:
            item_key = _lineage_key(self.item)
            field_key = _lineage_field_key(self.field)
            sources = tuple(
                source
                for line in self.record.evidence_lineage
                if _lineage_field_key(line.field) == field_key and line.item_key == item_key
                for source in line.provenance
            )
            if sources:
                return sources
        return self.record.raw_provenance or (self.record.raw.provenance,)


@dataclass(frozen=True)
class DerivationStep:
    """An ordered, internal-only step in an effective-membership result."""

    operation: str
    source: str | None = None
    target: str | None = None
    evidence: tuple[PrimitiveEvidence, ...] = ()


@dataclass(frozen=True)
class DerivationConditionEvidence:
    """Evidence that satisfies one named predicate in a composite proof."""

    predicate: str
    evidence: tuple[PrimitiveEvidence, ...]


@dataclass(frozen=True)
class HostAccessResult:
    relationship: str
    source: str
    target: str
    status: InferenceStatus
    evidence_source: EvidenceSource
    primitive_evidence: tuple[PrimitiveEvidence, ...]
    derivation: tuple[DerivationStep, ...] = ()
    canonical_emit_allowed: bool = False
    reason: str = ""
    conditions: tuple[DerivationConditionEvidence, ...] = ()

    @property
    def positive(self) -> bool:
        return self.status is InferenceStatus.POSITIVE


@dataclass(frozen=True)
class _MembershipPath:
    principal: str
    group: str
    steps: tuple[DerivationStep, ...]
    evidence: tuple[PrimitiveEvidence, ...]

    @property
    def derived(self) -> bool:
        return len(self.steps) > 1


@dataclass(frozen=True)
class _RightCollection:
    status: PrimitiveStatus
    assigned: frozenset[str]
    evidence: tuple[PrimitiveEvidence, ...]
    assignments: tuple[tuple[str, PrimitiveEvidence], ...] = ()
    complete: bool = False


@dataclass(frozen=True)
class _RightPath:
    assigned_group: str
    steps: tuple[DerivationStep, ...]
    evidence: tuple[PrimitiveEvidence, ...]


@dataclass(frozen=True)
class _RightEvaluation:
    status: PrimitiveStatus
    evidence: tuple[PrimitiveEvidence, ...]
    paths: tuple[_RightPath, ...] = ()


def _items(value: object) -> tuple[object, ...]:
    if isinstance(value, list):
        return tuple(value)
    if isinstance(value, Mapping):
        result = value.get("Results")
        if isinstance(result, list):
            return tuple(result)
    return ()


def _first(data: Mapping[str, Any], *keys: str) -> object | None:
    for key in keys:
        if key in data and data[key] is not None:
            return data[key]
    folded = {key.casefold(): key for key in data if isinstance(key, str)}
    for key in keys:
        actual = folded.get(key.casefold())
        if actual is not None and data[actual] is not None:
            return data[actual]
    return None


def _reference(item: object) -> str | None:
    if isinstance(item, str) and item.strip():
        return item.strip()
    if not isinstance(item, Mapping):
        return None
    value = _first(
        item,
        "MemberId",
        "member_id",
        "PrincipalSID",
        "principal_sid",
        "ObjectIdentifier",
        "object_identifier",
        "UserSID",
        "UserSid",
        "UserId",
        "UserId",
    )
    return value.strip() if isinstance(value, str) and value.strip() else None


def _is_access_denied(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if not isinstance(value, str):
        return False
    return any(
        token in value.casefold().replace("_", " ")
        for token in ("access denied", "denied", "failed", "error", "not run")
    )


def _failure_reason_present(failure: object) -> bool:
    if failure is None or failure is False:
        return False
    if isinstance(failure, str):
        normalized = failure.strip().casefold().replace("_", " ")
        return normalized not in {"", "none", "null", "false", "no failure", "success"}
    return bool(failure)


def _own_failure_reason(value: object) -> bool:
    if not isinstance(value, Mapping):
        return False
    return _failure_reason_present(_first(value, "FailureReason", "failure_reason"))


def _has_failure_reason(value: object) -> bool:
    """Treat a populated collector FailureReason as failed primitive evidence."""

    if isinstance(value, Mapping):
        if _own_failure_reason(value):
            return True
        results = _first(value, "Results", "results")
        if isinstance(results, (list, Mapping)) and _has_failure_reason(results):
            return True
        return False
    if isinstance(value, list):
        return any(isinstance(item, Mapping) and _has_failure_reason(item) for item in value)
    return False


def _field_failure_reason(data: Mapping[str, Any], field: str) -> bool:
    explicit = _first(data, f"{field}FailureReason", f"{field}_FailureReason")
    return _own_failure_reason(data.get(field)) or _failure_reason_present(explicit)


def _status_failure(value: object) -> bool:
    if value is False:
        return True
    if not isinstance(value, str):
        return False
    normalized = value.strip().casefold().replace("_", " ").replace("-", " ")
    return _is_access_denied(value) or normalized in {
        "unknown",
        "incomplete",
        "not collected",
        "not run",
        "error",
        "failure",
        "failed",
    }


def _collection_failure(value: object) -> bool:
    """Identify failure metadata on this collection or primitive only.

    Child collection items have their own status scope. Callers inspect those
    items individually instead of allowing one failed child to invalidate its
    siblings.
    """

    if isinstance(value, Mapping):
        if _own_failure_reason(value):
            return True
        status = _first(
            value,
            "Status",
            "status",
            "CollectionStatus",
            "collection_status",
            "MethodStatus",
            "method_status",
        )
        if _status_failure(status):
            return True
        for key in ("Collected", "collected", "Complete", "complete", "Success", "success"):
            if key in value and value[key] is False:
                return True
    return False


def _field_collection_failure(data: Mapping[str, Any], field: str) -> bool:
    explicit_failure = _first(data, f"{field}FailureReason", f"{field}_FailureReason")
    explicit_status = _first(
        data,
        f"{field}Status",
        f"{field}_Status",
        f"{field}CollectionStatus",
        f"{field}_CollectionStatus",
    )
    return (
        _failure_reason_present(explicit_failure)
        or _status_failure(explicit_status)
        or _collection_failure(data.get(field))
    )


def _is_complete(value: object, data: Mapping[str, Any], field: str) -> bool:
    """Return whether an empty collection is an evidence-backed negative."""

    if _field_collection_failure(data, field):
        return False
    if isinstance(value, Mapping):
        status = _first(value, "Status", "status", "CollectionStatus", "collection_status")
        if status is not None:
            return not _is_access_denied(status) and str(status).casefold() not in {
                "unknown",
                "incomplete",
                "not_collected",
                "not-collected",
            }
        for key in ("Complete", "complete", "Collected", "collected", "Success", "success"):
            if key in value and type(value[key]) is bool:
                return bool(value[key])
    for key in (
        f"{field}Complete",
        f"{field}Completeness",
        f"{field}Collected",
        f"{field}Status",
        "CollectionComplete",
        "collection_complete",
    ):
        marker = _first(data, key)
        if marker is not None:
            if type(marker) is bool:
                return marker
            return not _is_access_denied(marker) and str(marker).casefold() in {
                "success",
                "complete",
                "collected",
                "ok",
                "true",
            }
    return False


def _resolve_reference(
    reference: str, aliases: Mapping[str, set[str]], records: Mapping[str, NormalizedRecord]
) -> str | None:
    if reference in records:
        return reference
    matches = aliases.get(reference.casefold(), set())
    if len(matches) == 1:
        return next(iter(matches))
    return reference if reference in records else None


def _aliases(records: Mapping[str, NormalizedRecord]) -> dict[str, set[str]]:
    result: defaultdict[str, set[str]] = defaultdict(set)
    for record_id, record in records.items():
        result[record_id.casefold()].add(record_id)
        distinguished_name = record.attributes.get("distinguishedname")
        if isinstance(distinguished_name, str) and distinguished_name.strip():
            result[distinguished_name.strip().casefold()].add(record_id)
        raw_identifier = lookup_raw_identifier(record.raw.data)
        if isinstance(raw_identifier, str) and raw_identifier.strip():
            result[raw_identifier.strip().casefold()].add(record_id)
        for container_name in ("Properties", "properties", "Attributes", "attributes"):
            container = record.raw.data.get(container_name)
            if isinstance(container, Mapping):
                nested = lookup_raw_identifier(container)
                if isinstance(nested, str) and nested.strip():
                    result[nested.strip().casefold()].add(record_id)
    return result


def _principal_kind(records: Mapping[str, NormalizedRecord], identifier: str) -> bool:
    record = records.get(identifier)
    return record is None or record.kind in {"User", "Group", "Computer"}


def _group_sid(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    candidate = value.strip()
    scoped = parse_scoped_sid(candidate)
    upper = scoped[1] if scoped is not None else candidate.upper()
    if upper in {
        ADMINISTRATORS_SID,
        REMOTE_DESKTOP_USERS_SID,
        REMOTE_MANAGEMENT_USERS_SID,
    }:
        return upper
    # Historical LocalGroups identifiers are commonly prefixed with a host or
    # domain identifier.  Require the complete well-known SID suffix; a bare
    # DOMAIN-SID-512 or DOMAIN-SID-544 is never treated as a builtin group.
    if upper.endswith(f"-{ADMINISTRATORS_SID}"):
        return ADMINISTRATORS_SID
    if upper.endswith(f"-{REMOTE_DESKTOP_USERS_SID}"):
        return REMOTE_DESKTOP_USERS_SID
    if upper.endswith(f"-{REMOTE_MANAGEMENT_USERS_SID}"):
        return REMOTE_MANAGEMENT_USERS_SID
    return None


def _local_group_sid(host: NormalizedRecord, group: Mapping[str, Any]) -> str | None:
    identifier = _first(group, "ObjectIdentifier")
    # The short form is relative to its owning Computer, not an arbitrary SID suffix.
    if (
        host.kind == "Computer"
        and is_valid_sid(host.id)
        and isinstance(identifier, str)
        and identifier.strip().upper() == f"{host.id.upper()}-544"
    ):
        return ADMINISTRATORS_SID
    return _group_sid(_first(group, "ObjectIdentifier", "GroupSID", "GroupSid", "SID", "Name"))


def _member_items(container: object) -> tuple[object, ...]:
    if isinstance(container, Mapping):
        for key in ("Results", "Members", "MemberIds", "MemberSIDs", "members"):
            value = container.get(key)
            if value is not None:
                return (
                    _items(value)
                    if isinstance(value, Mapping)
                    else tuple(value)
                    if isinstance(value, list)
                    else ()
                )
    return _items(container)


def _host_memberships(
    host: NormalizedRecord,
    aliases: Mapping[str, set[str]],
    records: Mapping[str, NormalizedRecord],
) -> dict[str, list[PrimitiveEvidence]]:
    """Return direct host-group membership evidence keyed by full builtin SID."""

    memberships: defaultdict[str, list[PrimitiveEvidence]] = defaultdict(list)
    data = host.raw.data
    specialized = {
        "LocalAdmins": ADMINISTRATORS_SID,
        "RemoteDesktopUsers": REMOTE_DESKTOP_USERS_SID,
        "PSRemoteUsers": REMOTE_MANAGEMENT_USERS_SID,
    }
    for field, group_sid in specialized.items():
        if field not in data:
            continue
        if _field_collection_failure(data, field):
            continue
        for item in _items(data[field]):
            if _collection_failure(item):
                continue
            ref = _reference(item)
            if ref is None:
                continue
            resolved = _resolve_reference(ref, aliases, records) or ref
            if _principal_kind(records, resolved):
                memberships[group_sid].append(
                    PrimitiveEvidence(
                        PrimitiveStatus.POSITIVE,
                        host,
                        f"{field}[]",
                        item,
                        resolved_reference=resolved,
                    )
                )

    if _field_collection_failure(data, "LocalGroups"):
        return memberships
    local_groups = data.get("LocalGroups")
    for group_item in _items(local_groups):
        if not isinstance(group_item, Mapping):
            continue
        if _collection_failure(group_item):
            continue
        group_sid = _local_group_sid(host, group_item)
        if group_sid is None:
            continue
        members = _member_items(group_item.get("Results", group_item))
        for item in members:
            if _collection_failure(item):
                continue
            ref = _reference(item)
            if ref is None:
                continue
            resolved = _resolve_reference(ref, aliases, records) or ref
            if _principal_kind(records, resolved):
                memberships[group_sid].append(
                    PrimitiveEvidence(
                        PrimitiveStatus.POSITIVE,
                        host,
                        "LocalGroups[].Results[]",
                        item,
                        resolved_reference=resolved,
                    )
                )
    return memberships


def _host_group_status(
    host: NormalizedRecord,
    group_sid: str,
    direct: Mapping[str, list[PrimitiveEvidence]],
) -> PrimitiveStatus:
    field = {
        ADMINISTRATORS_SID: "LocalAdmins",
        REMOTE_DESKTOP_USERS_SID: "RemoteDesktopUsers",
        REMOTE_MANAGEMENT_USERS_SID: "PSRemoteUsers",
    }.get(group_sid)
    if (
        field is not None
        and field in host.raw.data
        and _field_collection_failure(host.raw.data, field)
    ):
        return PrimitiveStatus.UNKNOWN
    if direct.get(group_sid):
        return PrimitiveStatus.POSITIVE
    if (
        field is not None
        and field in host.raw.data
        and (
            _field_collection_failure(host.raw.data, field)
            or _has_failure_reason(host.raw.data[field])
        )
    ):
        return PrimitiveStatus.UNKNOWN
    if "LocalGroups" in host.raw.data and _field_collection_failure(host.raw.data, "LocalGroups"):
        return PrimitiveStatus.UNKNOWN
    if "LocalGroups" in host.raw.data:
        failed_group = any(
            isinstance(group_item, Mapping)
            and _collection_failure(group_item)
            and _local_group_sid(host, group_item) == group_sid
            for group_item in _items(host.raw.data["LocalGroups"])
        )
        if failed_group:
            return PrimitiveStatus.UNKNOWN
    if field is not None and field in host.raw.data:
        return (
            PrimitiveStatus.NEGATIVE_KNOWN
            if _is_complete(host.raw.data[field], host.raw.data, field)
            else PrimitiveStatus.UNKNOWN
        )
    if "LocalGroups" in host.raw.data:
        return (
            PrimitiveStatus.NEGATIVE_KNOWN
            if _is_complete(host.raw.data["LocalGroups"], host.raw.data, "LocalGroups")
            else PrimitiveStatus.UNKNOWN
        )
    return PrimitiveStatus.UNKNOWN


def _failed_host_membership_results(
    host: NormalizedRecord,
    aliases: Mapping[str, set[str]],
    records: Mapping[str, NormalizedRecord],
) -> list[HostAccessResult]:
    """Retain failed host-local membership observations as unknown assessments."""

    relations = {
        "LocalAdmins": (ADMINISTRATORS_SID, "AdminTo"),
        "RemoteDesktopUsers": (REMOTE_DESKTOP_USERS_SID, "CanRDP"),
        "PSRemoteUsers": (REMOTE_MANAGEMENT_USERS_SID, "CanPSRemote"),
    }
    evidence_by_identity: defaultdict[tuple[str, str], list[PrimitiveEvidence]] = defaultdict(list)

    def record_failure(
        relationship: str,
        reference: str | None,
        evidence_field: str,
        evidence_item: object,
    ) -> None:
        if reference is None:
            return
        principal = _resolve_reference(reference, aliases, records) or reference
        if not _principal_kind(records, principal):
            return
        evidence_by_identity[(relationship, principal)].append(
            PrimitiveEvidence(
                PrimitiveStatus.UNKNOWN,
                host,
                evidence_field,
                evidence_item,
                reason="host-local membership collection failed",
                resolved_reference=principal,
            )
        )

    def members(container: object) -> tuple[object, ...]:
        nested = _member_items(container)
        return nested or ((container,) if _reference(container) is not None else ())

    data = host.raw.data
    for field, (_builtin_sid, relationship) in relations.items():
        if field not in data:
            continue
        raw = data[field]
        if _field_collection_failure(data, field):
            if isinstance(raw, Mapping):
                for item in members(raw):
                    record_failure(relationship, _reference(item), field, raw)
            else:
                for entry in _items(raw):
                    for item in members(entry):
                        record_failure(relationship, _reference(item), f"{field}[]", entry)
            continue
        for entry in _items(raw):
            if not isinstance(entry, Mapping):
                continue
            if _collection_failure(entry):
                for item in members(entry):
                    record_failure(relationship, _reference(item), f"{field}[]", entry)
                continue
            for item in _member_items(entry):
                if _collection_failure(item):
                    record_failure(
                        relationship,
                        _reference(item),
                        f"{field}[].Results[]",
                        item,
                    )

    local_groups = data.get("LocalGroups")
    field_failed = _field_collection_failure(data, "LocalGroups")
    for group_item in _items(local_groups):
        if not isinstance(group_item, Mapping):
            continue
        group_sid = _local_group_sid(host, group_item)
        relationship = next(
            (relation for sid, relation in relations.values() if sid == group_sid), None
        )
        if relationship is None:
            continue
        if field_failed or _collection_failure(group_item):
            for item in _member_items(group_item.get("Results", group_item)):
                record_failure(relationship, _reference(item), "LocalGroups[]", group_item)
            continue
        for item in _member_items(group_item.get("Results", group_item)):
            if _collection_failure(item):
                record_failure(
                    relationship,
                    _reference(item),
                    "LocalGroups[].Results[]",
                    item,
                )

    results: list[HostAccessResult] = []
    for (relationship, principal), evidence in sorted(evidence_by_identity.items()):
        unique = {(item.field, _lineage_key(item.item)): item for item in evidence}
        results.append(
            _result(
                relationship,
                principal,
                host.id,
                InferenceStatus.UNKNOWN,
                EvidenceSource.UNKNOWN,
                (unique[key] for key in sorted(unique)),
                reason=f"{relationship} host-local membership collection failed",
            )
        )
    return results


def _endpoint_rejection(
    host: NormalizedRecord,
    principal: str,
    aliases: Mapping[str, set[str]],
    records: Mapping[str, NormalizedRecord],
) -> PrimitiveEvidence | None:
    """Return explicit endpoint-ACL rejection without making it a runtime gate."""

    data = host.raw.data
    for field in (
        "EndpointACL",
        "EndpointAcl",
        "SessionConfigurationACL",
        "WinRMEndpointACL",
        "PSRemotingEndpointACL",
    ):
        raw = data.get(field)
        if raw is None:
            continue
        entries = _items(raw) or (raw,)
        for entry in entries:
            if not isinstance(entry, Mapping):
                continue
            ref = _reference(entry)
            if ref is not None:
                resolved = _resolve_reference(ref, aliases, records) or ref
                if resolved != principal and ref.casefold() != principal.casefold():
                    continue
            allowed = _first(entry, "Allowed", "allowed", "Access", "access")
            status = _first(entry, "Status", "status", "Decision", "decision")
            denied = (
                allowed is False
                or (isinstance(allowed, str) and _is_access_denied(allowed))
                or _is_access_denied(status)
            )
            if denied:
                return PrimitiveEvidence(
                    PrimitiveStatus.UNKNOWN,
                    host,
                    f"{field}[]",
                    entry,
                    "explicit endpoint ACL rejection",
                )
    return None


def evaluate_local_group_membership(
    host: NormalizedRecord, principal: str, group_sid: str
) -> PrimitiveEvidence:
    """Evaluate one direct local-group primitive without inferring completeness."""

    normalized = _group_sid(group_sid)
    if normalized is None:
        return PrimitiveEvidence(
            PrimitiveStatus.UNKNOWN, host, "LocalGroups", reason="invalid group SID"
        )
    records = {host.id: host}
    memberships = _host_memberships(host, _aliases(records), records)
    for evidence in memberships.get(normalized, []):
        if evidence.resolved_reference == principal or _reference(evidence.item) == principal:
            return evidence
    field_by_sid = {
        ADMINISTRATORS_SID: "LocalAdmins",
        REMOTE_DESKTOP_USERS_SID: "RemoteDesktopUsers",
        REMOTE_MANAGEMENT_USERS_SID: "PSRemoteUsers",
    }
    field = (
        "LocalGroups"
        if "LocalGroups" in host.raw.data
        else field_by_sid.get(normalized, normalized)
    )
    status = _host_group_status(host, normalized, memberships)
    if status is PrimitiveStatus.NEGATIVE_KNOWN:
        return PrimitiveEvidence(
            PrimitiveStatus.NEGATIVE_KNOWN,
            host,
            field,
            reason="successful complete collection",
        )
    return PrimitiveEvidence(
        PrimitiveStatus.UNKNOWN, host, field, reason="membership not collected completely"
    )


def _is_plausible_group_sid(value: str) -> bool:
    if is_valid_sid(value):
        return True
    if parse_scoped_sid(value) is not None:
        return True
    if boundary_group(value) is not None:
        return True
    if parse_qualified_sid(value) is not None:
        return True
    return False


def extract_primary_group_entry(
    data: Mapping[str, Any],
    *,
    record_kind: str | None = None,
) -> tuple[str, str] | None:
    root_keys = [
        k
        for k in data
        if isinstance(k, str) and k.casefold() in {"primarygroupsid", "primary_group_sid"}
    ]
    props = data.get("Properties")
    if not isinstance(props, Mapping):
        props = data.get("properties")
    props_map = props if isinstance(props, Mapping) else None
    props_keys = (
        [
            f"Properties.{k}"
            for k in props_map
            if isinstance(k, str) and k.casefold() in {"primarygroupsid", "primary_group_sid"}
        ]
        if props_map is not None
        else []
    )

    occurrences: list[tuple[str, Any]] = []
    for k in root_keys:
        occurrences.append((k, data[k]))
    if props_map is not None:
        for k in props_keys:
            raw_k = k.removeprefix("Properties.")
            occurrences.append((k, props_map[raw_k]))

    if not occurrences:
        return None

    if record_kind is not None and record_kind not in {"User", "Computer"}:
        raise ValueError("PrimaryGroupSid evidence is only valid on User or Computer records")

    non_null_entries = [(field, val) for field, val in occurrences if val is not None]
    if not non_null_entries:
        return None

    validated_values: list[tuple[str, str]] = []
    for field, val in non_null_entries:
        if not isinstance(val, str):
            raise ValueError(f"{field} evidence item must be a SID string")
        ref = val.strip()
        if not ref:
            raise ValueError(f"{field} evidence item must be a non-empty string")
        if not _is_plausible_group_sid(ref):
            raise ValueError(f"malformed {field} SID format: {ref!r}")
        validated_values.append((field, ref))

    distinct_refs = {ref for _, ref in validated_values}
    if len(distinct_refs) > 1:
        raise ValueError("conflicting PrimaryGroupSid evidence in record")

    chosen_ref = validated_values[0][1]
    root_entries = [f for f, _ in validated_values if not f.startswith("Properties.")]
    if root_entries:
        chosen_field = root_entries[0]
    else:
        chosen_field = validated_values[0][0]

    return chosen_field, chosen_ref


def _membership_graph(
    records: Mapping[str, NormalizedRecord], aliases: Mapping[str, set[str]]
) -> dict[str, set[str]]:
    graph: defaultdict[str, set[str]] = defaultdict(set)
    for record in records.values():
        if record.kind == "Group":
            for item in _items(record.raw.data.get("Members")):
                ref = _reference(item)
                if ref is None:
                    continue
                member = _resolve_reference(ref, aliases, records) or ref
                if _principal_kind(records, member):
                    graph[member].add(record.id)
        elif record.kind in {"User", "Computer"}:
            entry = extract_primary_group_entry(record.raw.data, record_kind=record.kind)
            if entry is not None:
                _, primary_ref = entry
                target = _resolve_reference(primary_ref, aliases, records) or primary_ref
                target_rec = records.get(target)
                if target_rec is None or target_rec.kind == "Group":
                    graph[record.id].add(target)
    return graph


def resolve_effective_membership(
    principal: str,
    group: str,
    memberships: Mapping[str, Iterable[str]],
    *,
    evidence: Mapping[tuple[str, str], tuple[PrimitiveEvidence, ...]] | None = None,
) -> tuple[_MembershipPath, ...]:
    """Resolve effective membership deterministically with a cycle guard.

    ``memberships`` is a direct ``member -> groups`` mapping.  The returned
    paths are ordered and retain every traversed group; no transitive graph edge
    is materialized by this function.
    """

    paths: list[_MembershipPath] = []
    queue: deque[tuple[str, tuple[str, ...], tuple[PrimitiveEvidence, ...]]] = deque(
        [(principal, (principal,), ())]
    )
    seen_paths: set[tuple[str, ...]] = set()
    while queue:
        current, path, path_evidence = queue.popleft()
        for parent in sorted(memberships.get(current, set())):
            if parent in path:
                continue
            next_path = (*path, parent)
            if next_path in seen_paths:
                continue
            seen_paths.add(next_path)
            edge_evidence = (evidence or {}).get((current, parent), ())
            combined = (*path_evidence, *edge_evidence)
            steps = tuple(
                DerivationStep(
                    "effective_membership",
                    source=left,
                    target=right,
                    evidence=(evidence or {}).get((left, right), ()),
                )
                for left, right in zip(next_path, next_path[1:], strict=False)
            )
            if parent == group:
                paths.append(_MembershipPath(principal, group, steps, combined))
            queue.append((parent, next_path, combined))
    return tuple(paths)


class EffectiveMembershipResolver:
    """Snapshot-local memoized resolver for the immutable direct membership graph."""

    def __init__(
        self,
        memberships: Mapping[str, Iterable[str]],
        evidence: Mapping[tuple[str, str], tuple[PrimitiveEvidence, ...]] | None = None,
    ) -> None:
        self._memberships = {member: frozenset(groups) for member, groups in memberships.items()}
        self._evidence = {key: tuple(value) for key, value in (evidence or {}).items()}
        self._cache: dict[tuple[str, str], tuple[_MembershipPath, ...]] = {}
        self.traversal_count = 0
        self.cache_hit_count = 0

    def resolve(self, principal: str, group: str) -> tuple[_MembershipPath, ...]:
        key = (principal, group)
        cached = self._cache.get(key)
        if cached is not None:
            self.cache_hit_count += 1
            return cached
        self.traversal_count += 1
        result = resolve_effective_membership(
            principal, group, self._memberships, evidence=self._evidence
        )
        self._cache[key] = result
        return result


def _right_collection(
    host: NormalizedRecord,
    right: str,
    aliases: Mapping[str, set[str]],
    records: Mapping[str, NormalizedRecord],
) -> _RightCollection:
    data = host.raw.data
    if "UserRights" not in data:
        return _RightCollection(PrimitiveStatus.UNKNOWN, frozenset(), ())
    raw = data["UserRights"]
    if _own_failure_reason(raw) or _failure_reason_present(
        _first(data, "UserRightsFailureReason", "UserRights_FailureReason")
    ):
        return _RightCollection(
            PrimitiveStatus.UNKNOWN,
            frozenset(),
            (
                PrimitiveEvidence(
                    PrimitiveStatus.UNKNOWN,
                    host,
                    "UserRights",
                    raw if isinstance(raw, Mapping) else None,
                    "right collection has a failure reason",
                ),
            ),
        )
    entries = _items(raw)
    complete = _is_complete(raw, data, "UserRights")
    found = False
    entry_complete = False
    assigned: set[str] = set()
    evidence: list[PrimitiveEvidence] = []
    assignments: list[tuple[str, PrimitiveEvidence]] = []
    for entry in entries:
        if not isinstance(entry, Mapping):
            continue
        name = _first(entry, "Privilege", "RightName", "Name", "right")
        if not isinstance(name, str) or name.casefold() != right.casefold():
            continue
        found = True
        if _own_failure_reason(entry):
            return _RightCollection(
                PrimitiveStatus.UNKNOWN,
                frozenset(),
                (
                    PrimitiveEvidence(
                        PrimitiveStatus.UNKNOWN,
                        host,
                        "UserRights[]",
                        entry,
                        "right entry has a failure reason",
                    ),
                ),
            )
        collected = _first(entry, "Collected", "collected", "Complete", "complete")
        if collected is not None and collected is not True:
            return _RightCollection(
                PrimitiveStatus.UNKNOWN,
                frozenset(),
                (
                    PrimitiveEvidence(
                        PrimitiveStatus.UNKNOWN, host, "UserRights", entry, "collection failed"
                    ),
                ),
            )
        if collected is True:
            entry_complete = True
        status = _first(entry, "Status", "status", "CollectionStatus", "collection_status")
        if _is_access_denied(status):
            return _RightCollection(
                PrimitiveStatus.UNKNOWN,
                frozenset(),
                (
                    PrimitiveEvidence(
                        PrimitiveStatus.UNKNOWN,
                        host,
                        "UserRights",
                        entry,
                        "collection access denied",
                    ),
                ),
            )
        entry_evidence = PrimitiveEvidence(
            PrimitiveStatus.POSITIVE,
            host,
            "UserRights[]",
            entry,
        )
        entry_assignments: list[str] = []
        for item in _member_items(entry):
            ref = _reference(item)
            if ref is not None:
                resolved = _resolve_reference(ref, aliases, records) or ref
                assigned.add(resolved)
                entry_assignments.append(resolved)
        if not entry_assignments:
            entry_evidence = PrimitiveEvidence(
                PrimitiveStatus.NEGATIVE_KNOWN,
                host,
                "UserRights[]",
                entry,
            )
        evidence.append(entry_evidence)
        assignments.extend((resolved, entry_evidence) for resolved in entry_assignments)
    if not found:
        if not complete:
            return _RightCollection(
                PrimitiveStatus.UNKNOWN,
                frozenset(),
                (
                    PrimitiveEvidence(
                        PrimitiveStatus.UNKNOWN,
                        host,
                        "UserRights",
                        reason="right collection incomplete",
                    ),
                ),
            )
        return _RightCollection(
            PrimitiveStatus.NEGATIVE_KNOWN,
            frozenset(),
            (
                PrimitiveEvidence(
                    PrimitiveStatus.NEGATIVE_KNOWN,
                    host,
                    "UserRights",
                    raw,
                    reason="successful complete collection",
                ),
            ),
            complete=True,
        )
    if not complete and not entry_complete:
        # A positive assignment is usable as positive evidence, but absence of
        # an assignment is not known-negative without a complete collection.
        return _RightCollection(
            PrimitiveStatus.POSITIVE if assigned else PrimitiveStatus.UNKNOWN,
            frozenset(assigned),
            tuple(evidence),
            tuple(assignments),
            complete=False,
        )
    return _RightCollection(
        PrimitiveStatus.POSITIVE if assigned else PrimitiveStatus.NEGATIVE_KNOWN,
        frozenset(assigned),
        tuple(evidence),
        tuple(assignments),
        complete=True,
    )


def _evaluate_user_right(
    host: NormalizedRecord,
    principal: str,
    right: str,
    memberships: Mapping[str, set[str]],
    aliases: Mapping[str, set[str]],
    records: Mapping[str, NormalizedRecord],
    evidence_map: Mapping[tuple[str, str], tuple[PrimitiveEvidence, ...]] | None = None,
    membership_resolver: EffectiveMembershipResolver | None = None,
) -> _RightEvaluation:
    """Evaluate a right and retain every effective membership path."""

    collection = _right_collection(host, right, aliases, records)
    if collection.status is PrimitiveStatus.UNKNOWN:
        return _RightEvaluation(
            PrimitiveStatus.UNKNOWN,
            collection.evidence
            or (
                PrimitiveEvidence(
                    PrimitiveStatus.UNKNOWN, host, "UserRights", reason="right collection unknown"
                ),
            ),
        )
    resolver = membership_resolver or EffectiveMembershipResolver(memberships, evidence_map)
    paths: list[_RightPath] = []
    for assigned, right_evidence in sorted(
        collection.assignments, key=lambda item: (item[0], _lineage_key(item[1].item))
    ):
        if assigned == principal:
            paths.append(_RightPath(principal, (), (right_evidence,)))
        for membership in resolver.resolve(principal, assigned):
            right_step = DerivationStep(
                "effective_right",
                source=assigned,
                target=right,
                evidence=(right_evidence,),
            )
            paths.append(
                _RightPath(
                    assigned,
                    (*membership.steps, right_step),
                    (*membership.evidence, right_evidence),
                )
            )
    if paths:
        paths.sort(
            key=lambda path: (
                path.assigned_group,
                tuple(
                    (step.operation, step.source or "", step.target or "") for step in path.steps
                ),
                tuple(
                    (item.field, _lineage_key(item.item), _lineage_key(item.provenance))
                    for item in path.evidence
                ),
            )
        )
        unique_paths: list[_RightPath] = []
        seen_paths: set[str] = set()
        for path in paths:
            path_key = _lineage_key(
                (
                    path.assigned_group,
                    tuple((step.operation, step.source, step.target) for step in path.steps),
                    tuple((item.field, item.item, item.provenance) for item in path.evidence),
                )
            )
            if path_key not in seen_paths:
                seen_paths.add(path_key)
                unique_paths.append(path)
        paths = unique_paths
        first = paths[0].evidence[-1]
        return _RightEvaluation(
            PrimitiveStatus.POSITIVE,
            (
                PrimitiveEvidence(
                    PrimitiveStatus.POSITIVE,
                    host,
                    "UserRights",
                    item=first.item,
                    reason="nested right assignment",
                ),
            ),
            tuple(paths),
        )
    if collection.complete:
        return _RightEvaluation(
            PrimitiveStatus.NEGATIVE_KNOWN,
            collection.evidence,
        )
    return _RightEvaluation(
        PrimitiveStatus.UNKNOWN,
        (
            PrimitiveEvidence(
                PrimitiveStatus.UNKNOWN,
                host,
                "UserRights",
                reason="incomplete collection cannot prove absent effective assignment",
            ),
        ),
    )


def evaluate_user_right(
    host: NormalizedRecord,
    principal: str,
    right: str,
    memberships: Mapping[str, set[str]],
    aliases: Mapping[str, set[str]],
    records: Mapping[str, NormalizedRecord],
) -> PrimitiveEvidence:
    """Evaluate one effective right, retaining the legacy summary API."""

    return _evaluate_user_right(host, principal, right, memberships, aliases, records).evidence[0]


def _result(
    relationship: str,
    principal: str,
    host: str,
    status: InferenceStatus,
    source: EvidenceSource,
    evidence: Iterable[PrimitiveEvidence],
    *,
    derivation: Iterable[DerivationStep] = (),
    conditions: Iterable[DerivationConditionEvidence] = (),
    reason: str,
) -> HostAccessResult:
    derivation_tuple = tuple(derivation)
    return HostAccessResult(
        relationship,
        principal,
        host,
        status,
        source,
        tuple(evidence),
        derivation_tuple,
        status is InferenceStatus.POSITIVE
        and source in {EvidenceSource.DIRECT, EvidenceSource.DERIVED},
        reason,
        tuple(conditions),
    )


def _all_effective_members(
    host: NormalizedRecord,
    group_sid: str,
    direct: Mapping[str, list[PrimitiveEvidence]],
    memberships: Mapping[str, set[str]],
    evidence_map: Mapping[tuple[str, str], tuple[PrimitiveEvidence, ...]],
    principals: Iterable[str],
    membership_resolver: EffectiveMembershipResolver,
) -> tuple[_MembershipPath, ...]:
    paths: list[_MembershipPath] = []
    for item in direct.get(group_sid, []):
        principal = item.resolved_reference or _reference(item.item)
        if principal is None:
            continue
        local_step = DerivationStep(
            "host_local_membership", source=principal, target=group_sid, evidence=(item,)
        )
        paths.append(_MembershipPath(principal, group_sid, (), (item,)))
        # The direct host assignment may name a security group.  Resolve
        # descendants of that group through direct MemberOf records, then
        # append the host-local assignment as the final ordered step.
        for candidate in sorted(set(principals)):
            if candidate == principal:
                continue
            for nested in membership_resolver.resolve(candidate, principal):
                paths.append(
                    _MembershipPath(
                        candidate,
                        group_sid,
                        (*nested.steps, local_step),
                        (*nested.evidence, item),
                    )
                )
    return tuple(paths)


def _host_results(
    host: NormalizedRecord,
    records: Mapping[str, NormalizedRecord],
    aliases: Mapping[str, set[str]],
    memberships: Mapping[str, set[str]],
    evidence_map: Mapping[tuple[str, str], tuple[PrimitiveEvidence, ...]],
    membership_resolver: EffectiveMembershipResolver,
) -> list[HostAccessResult]:
    direct = _host_memberships(host, aliases, records)
    results = _failed_host_membership_results(host, aliases, records)
    effective: dict[str, tuple[_MembershipPath, ...]] = {
        sid: _all_effective_members(
            host,
            sid,
            direct,
            memberships,
            evidence_map,
            records.keys(),
            membership_resolver,
        )
        for sid in (ADMINISTRATORS_SID, REMOTE_DESKTOP_USERS_SID, REMOTE_MANAGEMENT_USERS_SID)
    }
    for group_sid, relationship in (
        (ADMINISTRATORS_SID, "AdminTo"),
        (REMOTE_MANAGEMENT_USERS_SID, "CanPSRemote"),
    ):
        for path in sorted(
            effective[group_sid],
            key=lambda item: (
                item.principal,
                item.group,
                tuple(
                    (step.operation, step.source or "", step.target or "") for step in item.steps
                ),
            ),
        ):
            source = EvidenceSource.DERIVED if path.derived else EvidenceSource.DIRECT
            results.append(
                _result(
                    relationship,
                    path.principal,
                    host.id,
                    InferenceStatus.POSITIVE,
                    source,
                    path.evidence,
                    derivation=path.steps,
                    reason="effective host-local group membership",
                )
            )
            if relationship == "CanPSRemote":
                endpoint_rejection = _endpoint_rejection(host, path.principal, aliases, records)
                if endpoint_rejection is not None:
                    results.append(
                        _result(
                            relationship,
                            path.principal,
                            host.id,
                            InferenceStatus.REJECTED,
                            EvidenceSource.REJECTED,
                            (*path.evidence, endpoint_rejection),
                            derivation=path.steps,
                            reason="explicit endpoint ACL rejects the principal",
                        )
                    )

    candidates = {path.principal for path in effective[REMOTE_DESKTOP_USERS_SID]}
    rdu_status = _host_group_status(host, REMOTE_DESKTOP_USERS_SID, direct)
    # Include allow/deny-only principals so the evaluator can explicitly retain
    # an insufficient/unknown assessment without ever turning it into CanRDP.
    for right in (ALLOW_RDP_RIGHT, DENY_RDP_RIGHT):
        collection = _right_collection(host, right, aliases, records)
        candidates.update(collection.assigned)
    for principal in sorted(candidates):
        membership_paths = [
            p for p in effective[REMOTE_DESKTOP_USERS_SID] if p.principal == principal
        ]
        allow_eval = _evaluate_user_right(
            host,
            principal,
            ALLOW_RDP_RIGHT,
            memberships,
            aliases,
            records,
            evidence_map,
            membership_resolver,
        )
        deny_eval = _evaluate_user_right(
            host,
            principal,
            DENY_RDP_RIGHT,
            memberships,
            aliases,
            records,
            evidence_map,
            membership_resolver,
        )
        allow = allow_eval.evidence[0]
        deny = deny_eval.evidence[0]
        membership_evidence = tuple(
            evidence for membership in membership_paths for evidence in membership.evidence
        )
        evidence = (*membership_evidence, allow, deny)
        source = (
            EvidenceSource.DERIVED
            if any(path.derived for path in membership_paths)
            else EvidenceSource.DIRECT
        )
        representative_membership = membership_paths[0] if membership_paths else None
        representative_right = allow_eval.paths[0] if allow_eval.paths else None
        representative_derivation = (
            representative_membership.steps if representative_membership else ()
        ) + (representative_right.steps if representative_right else ())
        if not membership_paths:
            results.append(
                _result(
                    "CanRDP",
                    principal,
                    host.id,
                    InferenceStatus.NEGATIVE_KNOWN
                    if rdu_status is PrimitiveStatus.NEGATIVE_KNOWN
                    else InferenceStatus.UNKNOWN,
                    EvidenceSource.UNKNOWN,
                    evidence,
                    reason="RDU membership is not positive",
                )
            )
            continue
        if (
            allow_eval.status is PrimitiveStatus.UNKNOWN
            or deny_eval.status is PrimitiveStatus.UNKNOWN
        ):
            results.append(
                _result(
                    "CanRDP",
                    principal,
                    host.id,
                    InferenceStatus.UNKNOWN,
                    source,
                    evidence,
                    derivation=representative_derivation,
                    reason="required UserRights evidence is incomplete",
                )
            )
        elif deny_eval.status is PrimitiveStatus.POSITIVE:
            results.append(
                _result(
                    "CanRDP",
                    principal,
                    host.id,
                    InferenceStatus.REJECTED,
                    source,
                    evidence,
                    derivation=representative_derivation,
                    reason="effective deny right takes precedence",
                )
            )
        elif allow_eval.status is PrimitiveStatus.POSITIVE:
            allow_paths = allow_eval.paths or (_RightPath(principal, (), ()),)
            for membership in membership_paths:
                for right_path in allow_paths:
                    derivation = (*membership.steps, *right_path.steps)
                    proof_source = (
                        EvidenceSource.DERIVED
                        if membership.derived or right_path.steps
                        else EvidenceSource.DIRECT
                    )
                    conditions = (
                        DerivationConditionEvidence("rdu_membership", membership.evidence),
                        DerivationConditionEvidence("allow_right", right_path.evidence),
                        DerivationConditionEvidence("deny_absent", deny_eval.evidence),
                    )
                    results.append(
                        _result(
                            "CanRDP",
                            principal,
                            host.id,
                            InferenceStatus.POSITIVE,
                            proof_source,
                            (*membership.evidence, *right_path.evidence, *deny_eval.evidence),
                            derivation=derivation,
                            conditions=conditions if proof_source is EvidenceSource.DERIVED else (),
                            reason=(
                                "effective RDU membership and allow right with known-negative deny"
                            ),
                        )
                    )
        else:
            results.append(
                _result(
                    "CanRDP",
                    principal,
                    host.id,
                    InferenceStatus.NEGATIVE_KNOWN,
                    source,
                    evidence,
                    derivation=representative_derivation,
                    reason="allow right is known absent",
                )
            )
    return results


def evaluate_gpo_access(records: Iterable[NormalizedRecord]) -> list[HostAccessResult]:
    """Assess only GPO results with an explicit validated resolver lineage."""

    def resolved_step(step: object, expected_operation: str) -> bool:
        if not isinstance(step, Mapping):
            return False
        operation = _first(step, "operation", "kind", "step")
        state = _first(step, "status", "state", "result")
        successful = state is True or (
            isinstance(state, str)
            and state.casefold() in {"resolved", "positive", "effective", "success", "succeeded"}
        )
        return operation == expected_operation and successful

    def resolved_conditions(
        entry: Mapping[str, Any], record: NormalizedRecord, field: str
    ) -> tuple[DerivationConditionEvidence, ...]:
        expected = ("rdu_membership", "allow_right", "deny_absent")
        raw_conditions = _first(entry, "resolved_conditions")
        items = _items(raw_conditions)
        predicates = tuple(
            _first(item, "predicate", "condition") if isinstance(item, Mapping) else None
            for item in items
        )
        if predicates != expected:
            return ()
        results: list[DerivationConditionEvidence] = []
        for predicate, item in zip(expected, items, strict=True):
            if not isinstance(item, Mapping):
                return ()
            state = _first(item, "status", "state", "result")
            successful = state is True or (
                isinstance(state, str)
                and state.casefold()
                in {"resolved", "positive", "effective", "success", "succeeded"}
            )
            supporting_evidence = _first(item, "evidence", "evidence_ref", "source")
            if not successful or supporting_evidence in (None, "", [], {}):
                return ()
            evidence = PrimitiveEvidence(
                PrimitiveStatus.POSITIVE,
                record,
                f"{field}[].resolved_conditions[].{predicate}",
                item,
                reason="validated GPO composite condition",
            )
            results.append(DerivationConditionEvidence(predicate, (evidence,)))
        return tuple(results)

    results: list[HostAccessResult] = []
    for record in records:
        if record.kind != "Computer":
            continue
        data = record.raw.data
        gpo_field = next(
            (key for key in ("GPOAccess", "GPOHostAccess", "GPOAssessments") if key in data),
            None,
        )
        raw_entries = data.get(gpo_field) if gpo_field is not None else None
        for entry in _items(raw_entries):
            if not isinstance(entry, Mapping):
                continue
            principal = _first(entry, "principal", "principal_id", "MemberId", "PrincipalSID")
            relationship = _first(entry, "relationship", "kind")
            state = str(_first(entry, "status", "assessment", "result") or "unknown").casefold()
            if not isinstance(principal, str) or relationship not in {
                "AdminTo",
                "CanRDP",
                "CanPSRemote",
            }:
                continue
            evidence = PrimitiveEvidence(
                PrimitiveStatus.POSITIVE
                if state in {"resolved", "positive", "effective"}
                else PrimitiveStatus.UNKNOWN,
                record,
                f"{gpo_field}[]",
                entry,
            )
            if state in {"rejected", "excluded", "filtered"}:
                status = InferenceStatus.REJECTED
                source = EvidenceSource.REJECTED
                reason = "GPO applicability excludes the host"
            elif (
                state in {"resolved", "positive", "effective"}
                and _first(entry, "resultant_state", "resultant", "effective") is True
            ):
                raw_steps = _first(entry, "resolved_steps", "resultant_lineage", "lineage")
                step_items = _items(raw_steps)
                operations = tuple(
                    _first(step, "operation", "kind", "step") if isinstance(step, Mapping) else None
                    for step in step_items
                )
                valid_steps = (
                    len(step_items) == len(GPO_OPERATIONS)
                    and operations == GPO_OPERATIONS
                    and all(
                        resolved_step(step, operation)
                        for step, operation in zip(step_items, GPO_OPERATIONS, strict=True)
                    )
                )
                conditions = (
                    resolved_conditions(entry, record, gpo_field)
                    if relationship == "CanRDP"
                    else ()
                )
                if valid_steps and (relationship != "CanRDP" or conditions):
                    status = InferenceStatus.POSITIVE
                    source = EvidenceSource.DERIVED
                    reason = "fully resolved resultant GPO state"
                else:
                    status = InferenceStatus.UNKNOWN
                    source = EvidenceSource.UNKNOWN
                    reason = (
                        "GPO CanRDP composite conditions are incomplete"
                        if valid_steps and relationship == "CanRDP"
                        else "GPO resolver lineage is incomplete"
                    )
            else:
                status = InferenceStatus.UNKNOWN
                source = EvidenceSource.UNKNOWN
                reason = "GPO applicability or resultant state is unresolved"
            if status is InferenceStatus.POSITIVE:
                steps = tuple(
                    DerivationStep(
                        operation,
                        evidence=(
                            PrimitiveEvidence(
                                PrimitiveStatus.POSITIVE,
                                record,
                                f"{gpo_field}[].resolved_steps[]",
                                item,
                                reason="validated GPO resolver step",
                            ),
                        ),
                    )
                    for operation, item in zip(GPO_OPERATIONS, step_items, strict=True)
                )
                primitive_evidence = tuple(step.evidence[0] for step in steps)
            else:
                steps = ()
                primitive_evidence = (evidence,)
            results.append(
                _result(
                    relationship,
                    principal,
                    record.id,
                    status,
                    source,
                    primitive_evidence,
                    derivation=steps,
                    conditions=conditions if status is InferenceStatus.POSITIVE else (),
                    reason=reason,
                )
            )
    return results


def evaluate_host_access(records: Iterable[NormalizedRecord]) -> list[HostAccessResult]:
    """Evaluate all host-access relationships from normalized records."""

    materialized = tuple(records)
    by_id = {record.id: record for record in materialized}
    aliases = _aliases(by_id)
    memberships = _membership_graph(by_id, aliases)
    evidence_map: defaultdict[tuple[str, str], list[PrimitiveEvidence]] = defaultdict(list)
    for record in materialized:
        if record.kind == "Group":
            for item in _items(record.raw.data.get("Members")):
                ref = _reference(item)
                if ref is None:
                    continue
                member = _resolve_reference(ref, aliases, by_id) or ref
                evidence_map[(member, record.id)].append(
                    PrimitiveEvidence(PrimitiveStatus.POSITIVE, record, "Members[]", item)
                )
        elif record.kind in {"User", "Computer"}:
            entry = extract_primary_group_entry(record.raw.data, record_kind=record.kind)
            if entry is not None:
                field_name, primary_ref = entry
                target = _resolve_reference(primary_ref, aliases, by_id) or primary_ref
                target_rec = by_id.get(target)
                if target_rec is None or target_rec.kind == "Group":
                    evidence_map[(record.id, target)].append(
                        PrimitiveEvidence(PrimitiveStatus.POSITIVE, record, field_name, primary_ref)
                    )
    membership_resolver = EffectiveMembershipResolver(
        memberships,
        {key: tuple(value) for key, value in evidence_map.items()},
    )
    results: list[HostAccessResult] = []
    for host in sorted(
        (record for record in materialized if record.kind == "Computer"), key=lambda item: item.id
    ):
        results.extend(
            _host_results(host, by_id, aliases, memberships, evidence_map, membership_resolver)
        )
    results.extend(evaluate_gpo_access(materialized))
    return results


__all__ = [
    "ADMINISTRATORS_SID",
    "ALLOW_RDP_RIGHT",
    "DENY_RDP_RIGHT",
    "EvidenceSource",
    "REMOTE_DESKTOP_USERS_SID",
    "REMOTE_MANAGEMENT_USERS_SID",
    "DerivationStep",
    "HostAccessResult",
    "InferenceStatus",
    "PrimitiveEvidence",
    "PrimitiveStatus",
    "evaluate_gpo_access",
    "evaluate_host_access",
    "evaluate_local_group_membership",
    "evaluate_user_right",
    "extract_primary_group_entry",
    "resolve_effective_membership",
]
