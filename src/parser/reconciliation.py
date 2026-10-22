"""Deterministic reconciliation of raw representations of one AD object.

This stage runs after raw loading and before canonical identity normalization.
It is deliberately conservative: snapshot boundaries and namespace-relative
scope are validated before records can be merged, and only relationship fields
with an established evidence-union meaning are treated as sets.
"""

from __future__ import annotations

import copy
import json
import re
from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import cast

from . import EvidenceLineage, JSONValue, RawProvenance, RawRecord, RecordError
from .identity_fields import lookup_raw_identifier
from .scopes import normalize_domain_sid, normalize_guid


class RepresentationKind(StrEnum):
    """The evidence role of one serialized raw representation."""

    FULL = "full"
    SUPPLEMENTAL = "supplemental"


class DuplicateCause(StrEnum):
    """Known causes for a reconciled duplicate group."""

    VERIFIED_SUPPLEMENTAL = "verified_supplemental"
    UNKNOWN = "unknown"
    NOT_APPLICABLE = "not_applicable"


@dataclass(frozen=True)
class RawRepresentation:
    """One serialized representation retained inside a logical object."""

    record: RawRecord
    kind: RepresentationKind

    @property
    def provenance(self) -> RawProvenance:
        """Return the source reference for this raw occurrence."""

        return self.record.provenance


@dataclass(frozen=True)
class ReconciledRecord:
    """One logical object with merged evidence and all raw representations."""

    kind: str
    # A scoped raw key has the shape (kind, ObjectIdentifier, scope-token).
    logical_key: tuple[str, ...] | None
    data: Mapping[str, JSONValue]
    representations: tuple[RawRepresentation, ...]
    evidence_lineage: tuple[EvidenceLineage, ...]
    duplicate_cause: str

    @property
    def raw_occurrence_count(self) -> int:
        """Number of raw records represented by this logical object."""

        return len(self.representations)

    @property
    def provenance(self) -> tuple[RawProvenance, ...]:
        """All raw provenance entries in deterministic representation order."""

        return tuple(item.provenance for item in self.representations)


class ReconciliationConflictError(RecordError):
    """Raised when reconciliation lacks a safe authority rule."""


# These fields represent independently observed relationship evidence. Unknown
# list-valued fields must not silently acquire set-union semantics.
EVIDENCE_UNION_FIELDS = frozenset(
    {
        "Aces",
        "AllowedToAct",
        "AllowedToDelegate",
        "Controllers",
        "LocalGroups",
        "Members",
        "PrivilegedSessions",
        "RegistrySessions",
        "Sessions",
        "Trusts",
        "UserRights",
        "LocalAdmins",
        "RemoteDesktopUsers",
        "PSRemoteUsers",
        "GPOAccess",
        "GPOHostAccess",
        "GPOAssessments",
        "EndpointACL",
        "EndpointAcl",
        "SessionConfigurationACL",
        "WinRMEndpointACL",
        "PSRemotingEndpointACL",
    }
)

_LOCAL_SID_RE = re.compile(r"^S-1-5-(?:18|19|20|32-(?:0|[1-9][0-9]*))$", re.IGNORECASE)
_SCOPE_KEYS = {
    "scope_guid",
    "scopeguid",
    "host_guid",
    "hostguid",
    "computer_guid",
    "computerguid",
    "domain_guid",
    "domainguid",
    "scope_id",
    "scopeid",
    "host_id",
    "hostid",
    "computer_id",
    "computerid",
    "domain_id",
    "domainid",
}
_SCOPE_SID_KEYS = {"domain_sid", "domainsid"}


def reconcile_raw_records(
    records: Iterable[RawRecord], *, snapshot_id: str | None = None
) -> tuple[ReconciledRecord, ...]:
    """Reconcile records within one snapshot and one safe raw identity.

    Records with an unsafe namespace-relative identifier are grouped only when
    a stable scope GUID is present in both representations. Otherwise they are
    retained as separate occurrences for canonical normalization to resolve.
    """

    materialized = tuple(records)
    _validate_snapshot_boundary(materialized, snapshot_id)

    grouped: dict[tuple[str, ...], list[RawRecord]] = defaultdict(list)
    unkeyed: list[RawRecord] = []
    for record in materialized:
        key = _reconciliation_key(record)
        if key is None:
            unkeyed.append(record)
        else:
            grouped[key].append(record)

    reconciled = [
        _reconcile_group(key, group)
        for key, group in sorted(grouped.items(), key=lambda item: item[0])
    ]
    reconciled.extend(_reconcile_single(record) for record in sorted(unkeyed, key=_sort_key))
    return tuple(reconciled)


def _reconcile_group(key: tuple[str, ...], records: list[RawRecord]) -> ReconciledRecord:
    ordered = tuple(sorted(records, key=_sort_key))
    merged: dict[str, JSONValue] = {}
    for record in ordered:
        data = record.data
        if _default_acl_stub(record) and any(
            not _default_acl_stub(other)
            and other.provenance.get("raw_file") == record.provenance.get("raw_file")
            and other.data.get("reconcile") is not False
            and other.data.get("Properties")
            and "IsACLProtected" in other.data
            for other in ordered
        ):
            # SharpHound's explicitly non-reconciled generated group carries a
            # default False here, not a second observation of ACL protection.
            # Retain its original bytes/provenance in representations below.
            data = {field: value for field, value in data.items() if field != "IsACLProtected"}
        merged = _merge_mapping(merged, data, path=(), record=record)

    merged.pop("reconcile", None)
    object_id = min(cast(str, _object_identifier(record)) for record in ordered)
    merged["ObjectIdentifier"] = object_id
    representations = tuple(_representation(record) for record in ordered)
    if _is_verified_supplemental_pattern(ordered, representations):
        duplicate_cause = DuplicateCause.VERIFIED_SUPPLEMENTAL.value
    else:
        duplicate_cause = DuplicateCause.UNKNOWN.value
    return ReconciledRecord(
        kind=key[0],
        logical_key=key,
        data=merged,
        representations=representations,
        evidence_lineage=_build_evidence_lineage(ordered),
        duplicate_cause=duplicate_cause,
    )


def _reconcile_single(record: RawRecord) -> ReconciledRecord:
    data = copy.deepcopy(dict(record.data))
    data.pop("reconcile", None)
    return ReconciledRecord(
        kind=record.kind,
        logical_key=None,
        data=data,
        representations=(_representation(record),),
        evidence_lineage=_build_evidence_lineage((record,)),
        duplicate_cause=DuplicateCause.NOT_APPLICABLE.value,
    )


def _representation(record: RawRecord) -> RawRepresentation:
    role = (
        RepresentationKind.SUPPLEMENTAL
        if record.data.get("reconcile") is False or _default_acl_stub(record)
        else RepresentationKind.FULL
    )
    return RawRepresentation(record=record, kind=role)


def _default_acl_stub(record: RawRecord) -> bool:
    """Recognize only the explicit generated-group shape, never sparse full records."""
    data = record.data
    properties = data.get("Properties")
    return (
        record.kind.casefold() in {"group", "groups"}
        and isinstance(properties, Mapping)
        and properties.get("reconcile") is False
        and not set(properties) - {"name", "domain", "domainsid", "reconcile"}
        and data.get("Aces") == []
        and data.get("Members") == []
        and data.get("IsACLProtected") is False
        and data.get("IsDeleted") is False
        and data.get("ContainedBy") is None
        and not set(data)
        - {
            "Properties",
            "Members",
            "Aces",
            "ObjectIdentifier",
            "IsDeleted",
            "IsACLProtected",
            "ContainedBy",
        }
    )


def _object_identifier(record: RawRecord) -> str | None:
    value = lookup_raw_identifier(record.data)
    return value if isinstance(value, str) and value.strip() else None


def _is_verified_supplemental_pattern(
    records: tuple[RawRecord, ...], representations: tuple[RawRepresentation, ...]
) -> bool:
    """Match only the narrowly documented Dataset A full-plus-stub shape."""

    if len(records) != 2:
        return False
    if {item.kind for item in representations} != {
        RepresentationKind.FULL,
        RepresentationKind.SUPPLEMENTAL,
    }:
        return False
    if records[0].provenance.get("raw_file") != records[1].provenance.get("raw_file"):
        return False

    supplemental = next(
        record
        for record, representation in zip(records, representations, strict=True)
        if representation.kind is RepresentationKind.SUPPLEMENTAL
    )
    full = next(
        record
        for record, representation in zip(records, representations, strict=True)
        if representation.kind is RepresentationKind.FULL
    )
    allowed_keys = {"ObjectIdentifier", "Properties", "Members", "Aces", "reconcile"}
    if set(supplemental.data) - allowed_keys:
        return False
    if not (
        isinstance(full.data.get("Properties"), Mapping)
        and full.data.get("Properties")
        and isinstance(full.data.get("Members"), list)
        and full.data.get("Members")
        and isinstance(full.data.get("Aces"), list)
        and full.data.get("Aces")
    ):
        return False
    return (
        supplemental.data.get("reconcile") is False
        and supplemental.data.get("Properties") == {}
        and supplemental.data.get("Members") == []
        and supplemental.data.get("Aces") == []
    )


def _reconciliation_key(record: RawRecord) -> tuple[str, ...] | None:
    object_id = _object_identifier(record)
    if object_id is None:
        return None
    normalized_id = object_id.casefold()
    if not _LOCAL_SID_RE.fullmatch(object_id):
        return (record.kind, normalized_id)

    scope = _scope_token(record.data)
    if scope is None:
        # A bare local SID is not safe to merge before canonicalization.
        return None
    return (record.kind, normalized_id, scope)


def _scope_token(data: Mapping[str, JSONValue]) -> str | None:
    """Find a typed stable scope without guessing from a display label."""

    explicit = data.get("scope")
    if isinstance(explicit, Mapping):
        kind = explicit.get("kind") or explicit.get("scope_kind")
        guid = _guid(explicit.get("guid") or explicit.get("value") or explicit.get("id"))
        if guid is not None and kind in {"domain", "host"}:
            return f"scope:guid:{kind}:{guid}"
        domain_sid = normalize_domain_sid(
            explicit.get("sid") or explicit.get("domain_sid") or explicit.get("value")
        )
        if domain_sid is not None and kind == "domain":
            return f"scope:sid:domain:{domain_sid}"

    for key, value in data.items():
        if isinstance(key, str) and key.casefold() in _SCOPE_KEYS:
            candidate = _guid(value)
            if candidate is not None:
                return f"scope:{candidate}"
        if isinstance(key, str) and key.casefold() in _SCOPE_SID_KEYS:
            candidate_sid = normalize_domain_sid(value)
            if candidate_sid is not None:
                return f"scope:sid:domain:{candidate_sid}"

    for container_name in ("Properties", "properties", "Attributes", "attributes"):
        container = data.get(container_name)
        if isinstance(container, Mapping):
            found = _scope_token(container)
            if found is not None:
                return found

    for container_name in ("domain", "host", "computer", "scope"):
        container = data.get(container_name)
        if isinstance(container, Mapping):
            for key in ("ObjectIdentifier", "objectid", "id", "guid", "GUID"):
                candidate = _guid(container.get(key))
                if candidate is not None:
                    return f"scope:{candidate}"
    return None


def _guid(value: JSONValue) -> str | None:
    return normalize_guid(value)


def _snapshot_identity(record: RawRecord) -> str | None:
    value = record.provenance.get("snapshot_id")
    if isinstance(value, str) and value:
        return value
    raw_file = record.provenance.get("raw_file", "")
    if raw_file.startswith("snapshot:"):
        return raw_file.removeprefix("snapshot:").split("/", 1)[0]
    return None


def _validate_snapshot_boundary(records: tuple[RawRecord, ...], expected: str | None) -> None:
    observed = [_snapshot_identity(record) for record in records]
    identities = {identity for identity in observed if identity is not None}
    if expected is not None:
        if identities and identities != {expected}:
            raise ReconciliationConflictError(
                "records do not belong to the requested snapshot",
                stage="reconcile",
            )
        # The caller-supplied boundary is authoritative for records whose
        # provenance predates snapshot_id/encoded snapshot references.
        return
    if len(identities) > 1:
        raise ReconciliationConflictError(
            "records from multiple snapshots cannot be reconciled together",
            stage="reconcile",
        )
    if identities and any(identity is None for identity in observed):
        raise ReconciliationConflictError(
            "snapshot identity is missing from part of the reconciliation input",
            stage="reconcile",
        )
    if len(records) > 1 and not identities:
        raise ReconciliationConflictError(
            "snapshot identity is required to reconcile multiple records",
            stage="reconcile",
        )


def _sort_key(record: RawRecord) -> tuple[str, str, str, str, str]:
    object_id = _object_identifier(record) or ""
    provenance = record.provenance
    return (
        record.kind,
        object_id.casefold(),
        str(provenance.get("raw_file", "")),
        str(provenance.get("record_locator", "")),
        str(provenance.get("record_id", "")),
    )


def _merge_mapping(
    current: dict[str, JSONValue],
    incoming: Mapping[str, JSONValue],
    *,
    path: tuple[str, ...],
    record: RawRecord,
) -> dict[str, JSONValue]:
    result = copy.deepcopy(current)
    for field in sorted(incoming):
        if field == "reconcile":
            continue
        value = incoming[field]
        if field not in result:
            result[field] = copy.deepcopy(value)
            continue
        result[field] = _merge_value(result[field], value, path=path + (field,), record=record)
    return result


def _merge_value(
    current: JSONValue,
    incoming: JSONValue,
    *,
    path: tuple[str, ...],
    record: RawRecord,
) -> JSONValue:
    if _is_empty(incoming):
        return copy.deepcopy(current)
    if _is_empty(current):
        return copy.deepcopy(incoming)
    if isinstance(current, Mapping) and isinstance(incoming, Mapping):
        return _merge_mapping(dict(current), incoming, path=path, record=record)
    if isinstance(current, list) and isinstance(incoming, list):
        field = _evidence_union_field(path)
        if field is None:
            if current == incoming:
                return copy.deepcopy(current)
            _raise_conflict(path, record)
        return _merge_list(current, incoming)
    if current == incoming:
        return copy.deepcopy(current)
    _raise_conflict(path, record)


def _raise_conflict(path: tuple[str, ...], record: RawRecord) -> None:
    field = ".".join(path) or "<record>"
    raise ReconciliationConflictError(
        f"conflicting non-empty values for {field}; no authoritative rule exists",
        stage="reconcile",
        record_id=_object_identifier(record),
    )


def _merge_list(current: list[JSONValue], incoming: list[JSONValue]) -> list[JSONValue]:
    values = {_canonical_json(item): copy.deepcopy(item) for item in [*current, *incoming]}
    return [values[key] for key in sorted(values)]


def _canonical_json(value: JSONValue) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _evidence_union_field(path: tuple[str, ...]) -> str | None:
    if not path:
        return None
    if path[-1] in EVIDENCE_UNION_FIELDS:
        return path[-1]
    if len(path) >= 2 and path[-1] == "Results" and path[-2] in EVIDENCE_UNION_FIELDS:
        return path[-2]
    return None


def _is_empty(value: JSONValue) -> bool:
    return value is None or value == "" or value == [] or value == {}


def _build_evidence_lineage(records: tuple[RawRecord, ...]) -> tuple[EvidenceLineage, ...]:
    """Map each unioned evidence item to the occurrences that supplied it."""

    items: dict[tuple[str, str], JSONValue] = {}
    sources: dict[tuple[str, str], list[RawProvenance]] = defaultdict(list)
    seen_occurrences: dict[tuple[str, str], set[int]] = defaultdict(set)
    for occurrence_index, record in enumerate(records):
        for field, values in _iter_evidence_lists(record.data):
            for item in values:
                item_key = _canonical_json(item)
                lineage_key = (field, item_key)
                items.setdefault(lineage_key, copy.deepcopy(item))
                if occurrence_index not in seen_occurrences[lineage_key]:
                    seen_occurrences[lineage_key].add(occurrence_index)
                    sources[lineage_key].append(copy.deepcopy(record.provenance))

    return tuple(
        EvidenceLineage(
            field=field,
            item_key=item_key,
            item=items[(field, item_key)],
            provenance=tuple(sources[(field, item_key)]),
        )
        for field, item_key in sorted(items)
    )


def _iter_evidence_lists(
    data: Mapping[str, JSONValue], path: tuple[str, ...] = ()
) -> Iterable[tuple[str, list[JSONValue]]]:
    for field, value in data.items():
        current_path = path + (field,)
        if isinstance(value, list) and (
            field in EVIDENCE_UNION_FIELDS
            or any(part.rstrip("[]") in EVIDENCE_UNION_FIELDS for part in path)
        ):
            yield ".".join(current_path), value
            for item in value:
                if isinstance(item, Mapping):
                    yield from _iter_evidence_lists(item, (*path, f"{field}[]"))
        elif isinstance(value, Mapping):
            results = value.get("Results")
            if field in EVIDENCE_UNION_FIELDS and isinstance(results, list):
                yield ".".join(current_path), results
                for item in results:
                    if isinstance(item, Mapping):
                        yield from _iter_evidence_lists(item, (*path, f"{field}[]"))
            else:
                yield from _iter_evidence_lists(value, current_path)


__all__ = [
    "DuplicateCause",
    "EVIDENCE_UNION_FIELDS",
    "EvidenceLineage",
    "RawRepresentation",
    "ReconciledRecord",
    "ReconciliationConflictError",
    "RepresentationKind",
    "reconcile_raw_records",
]
