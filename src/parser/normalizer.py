"""Identity normalization and duplicate-record reconciliation.

The collectors used by the project do not agree on casing, field names, or
whether object properties are nested under ``Properties``.  This module keeps
those differences at the parser boundary and emits the small, stable node
shape required by the M2 contract.  Relationship evidence remains in
``NormalizedRecord.raw`` for the graph builder.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from typing import Any

from . import ErrorPolicy, NormalizedRecord, RawRecord, RecordData, RecordError, process_records
from . import Normalizer as NormalizerInterface
from .identity_fields import lookup_raw_identifier
from .reconciliation import reconcile_raw_records
from .scopes import (
    ScopeIdentity,
    is_valid_sid,
    normalize_domain_sid,
    normalize_guid,
    normalize_sid,
    parse_scoped_sid,
)

SID_RE = re.compile(r"^S-1-(?:0|[1-9][0-9]*)(?:-(?:0|[1-9][0-9]*)){1,15}$", re.IGNORECASE)
LOCAL_SID_RE = re.compile(r"^S-1-5-(?:18|19|20|32-(?:0|[1-9][0-9]*))$", re.IGNORECASE)
DN_DOMAIN_RE = re.compile(r"(?:^|,)DC=([^,]+)", re.IGNORECASE)

_PROPERTY_CONTAINERS = ("properties", "property", "attributes", "Properties", "Attributes")
_GUID_KEYS = (
    "scope_guid",
    "scopeGuid",
    "ScopeGUID",
    "host_guid",
    "hostGuid",
    "HostGUID",
    "computer_guid",
    "computerGuid",
    "ComputerGUID",
    "domain_guid",
    "domainGuid",
    "DomainGUID",
    "container_guid",
    "containerGuid",
    "ContainerGUID",
    "scope_id",
    "scopeId",
    "container_id",
    "containerId",
    "ContainerId",
    "host_id",
    "hostId",
    "HostId",
    "computer_id",
    "computerId",
    "ComputerId",
)


def _lookup(data: Mapping[str, Any], keys: Iterable[str]) -> Any:
    wanted = {key.casefold() for key in keys}
    for key, value in data.items():
        if isinstance(key, str) and key.casefold() in wanted and value is not None:
            return value
    for container_name in _PROPERTY_CONTAINERS:
        container = data.get(container_name)
        if isinstance(container, Mapping):
            for key, value in container.items():
                if isinstance(key, str) and key.casefold() in wanted and value is not None:
                    return value
    return None


def _as_guid(value: object) -> str | None:
    return normalize_guid(value)


def _record_identifier(record: RawRecord) -> str | None:
    provenance_id = record.provenance.get("record_id")
    if isinstance(provenance_id, str) and provenance_id.strip():
        return provenance_id.strip()
    value = lookup_raw_identifier(record.data)
    return value.strip() if isinstance(value, str) and value.strip() else None


def _kind(value: str) -> str:
    normalized = value.strip().casefold()
    aliases = {
        "user": "User",
        "users": "User",
        "group": "Group",
        "groups": "Group",
        "computer": "Computer",
        "computers": "Computer",
        "host": "Computer",
        "hosts": "Computer",
        "domain": "Domain",
        "domains": "Domain",
        "ou": "OU",
        "ous": "OU",
        "gpo": "GPO",
        "gpos": "GPO",
    }
    try:
        return aliases[normalized]
    except KeyError as exc:
        raise ValueError(f"unsupported record kind {value!r}") from exc


def _scope_context(data: Mapping[str, Any], record_kind: str) -> ScopeIdentity | None:
    explicit = _lookup(data, ("scope", "scope_context", "scopeContext"))
    explicit_kind: str | None = None
    identity: ScopeIdentity | None = None
    direct_kind = _lookup(data, ("scope_kind", "scopeKind"))
    if isinstance(direct_kind, str):
        explicit_kind = direct_kind.strip().casefold()
    if isinstance(explicit, str):
        guid = _as_guid(explicit)
        if guid is None:
            raise ValueError("scope context has an invalid GUID")
        kind = explicit_kind or (
            _scope_default_kind(record_kind) if _scope_default_kind(record_kind) == "host" else None
        )
        if kind is None:
            raise ValueError("scope context requires an explicit domain or host kind")
        identity = ScopeIdentity(kind, "guid", guid)
    elif isinstance(explicit, Mapping):
        kind = explicit.get("kind") or explicit.get("scope_kind") or explicit.get("scopeKind")
        if isinstance(kind, str):
            explicit_kind = kind.strip().casefold()
        raw_value = (
            explicit.get("value")
            or explicit.get("guid")
            or explicit.get("scope_guid")
            or explicit.get("scopeGuid")
            or explicit.get("sid")
            or explicit.get("domain_sid")
            or explicit.get("id")
        )
        identity_type = explicit.get("identity_type") or explicit.get("type")
        if raw_value is not None:
            guid = _as_guid(raw_value)
            if identity_type == "sid" or (guid is None and explicit.get("sid") is not None):
                domain_sid = normalize_domain_sid(raw_value)
                if domain_sid is None:
                    raise ValueError("scope SID must be a valid AD domain SID")
                identity = ScopeIdentity(explicit_kind or "domain", "sid", domain_sid)
            elif guid is not None:
                kind = explicit_kind or (
                    _scope_default_kind(record_kind)
                    if _scope_default_kind(record_kind) == "host"
                    else None
                )
                if kind is None:
                    raise ValueError("scope context requires an explicit domain or host kind")
                identity = ScopeIdentity(kind, "guid", guid)
            else:
                raise ValueError("scope context has an invalid stable identity")

    if identity is not None:
        return identity

    for key in ("domain_sid", "domainSid", "DomainSID", "domainsid"):
        value = _lookup(data, (key,))
        if value is not None:
            if record_kind.casefold() in {"computer", "computers", "host", "hosts"}:
                raise ValueError("Domain SID cannot be used as host scope")
            domain_sid = normalize_domain_sid(value)
            if domain_sid is None:
                raise ValueError(f"scope field {key} is not a valid AD domain SID")
            if explicit_kind not in (None, "domain"):
                raise ValueError("a Domain SID cannot be used as host scope")
            return ScopeIdentity("domain", "sid", domain_sid)

    for key in _GUID_KEYS:
        value = _lookup(data, (key,))
        if value is None:
            continue
        guid = _as_guid(value)
        if guid is None:
            raise ValueError(f"scope field {key} is not a stable GUID")
        if key.casefold() in {
            "host_guid",
            "hostguid",
            "computer_guid",
            "computerguid",
            "host_id",
            "hostid",
            "computer_id",
            "computerid",
        }:
            return ScopeIdentity("host", "guid", guid)
        if key.casefold() in {"domain_guid", "domainguid"}:
            return ScopeIdentity("domain", "guid", guid)
        if explicit_kind is None:
            if _scope_default_kind(record_kind) == "host":
                return ScopeIdentity("host", "guid", guid)
            continue
        return ScopeIdentity(explicit_kind, "guid", guid)

    for key, scope_kind in (("computer", "host"), ("host", "host"), ("domain", "domain")):
        container = _lookup(data, (key,))
        if not isinstance(container, Mapping):
            continue
        nested_id = lookup_raw_identifier(container)
        guid = _as_guid(nested_id)
        if guid is not None:
            return ScopeIdentity(scope_kind, "guid", guid)
        if nested_id is not None and scope_kind == "domain":
            domain_sid = normalize_domain_sid(nested_id)
            if domain_sid is not None:
                return ScopeIdentity("domain", "sid", domain_sid)

    return None


def _scope_default_kind(record_kind: str) -> str:
    if record_kind.casefold() in {"computer", "computers", "host", "hosts"}:
        return "host"
    return "domain"


def _scope_kind(data: Mapping[str, Any], record_kind: str, explicit: str | None) -> str | None:
    if explicit is not None:
        if explicit not in {"host", "domain"}:
            raise ValueError("scope kind must be 'host' or 'domain'")
        return explicit
    raw_kind = record_kind.casefold()
    if raw_kind in {"computer", "computers", "host", "hosts"}:
        return "host"
    # A generic scope GUID attached to a group/user is intentionally ambiguous.
    return None


def _canonical_id(
    record: RawRecord, record_kind: str, scope_overrides: Mapping[str, object]
) -> str:
    value = lookup_raw_identifier(record.data)
    if not isinstance(value, str) or not value.strip():
        raise RecordError(
            "missing stable object SID or GUID",
            stage="normalize",
            record_id=_record_identifier(record),
        )
    candidate = value.strip()

    scoped = parse_scoped_sid(candidate)
    if scoped is not None:
        scope, sid = scoped
        if sid in {"S-1-5-18", "S-1-5-19", "S-1-5-20"} and scope.kind != "host":
            raise RecordError(
                "local service SID requires stable host scope",
                stage="normalize",
                record_id=_record_identifier(record),
            )
        if record_kind == "Computer" and sid.startswith("S-1-5-32-") and scope.kind != "host":
            raise RecordError(
                "computer-local built-in SID requires host scope",
                stage="normalize",
                record_id=_record_identifier(record),
            )
        return scope.canonical_sid(sid)
    if SID_RE.fullmatch(candidate) and is_valid_sid(candidate):
        candidate = normalize_sid(candidate)
        assert candidate is not None
        if not LOCAL_SID_RE.fullmatch(candidate):
            return candidate
        try:
            scope = _scope_context(record.data, record_kind)
            if scope is None:
                override = scope_overrides.get(_record_identifier(record))
                if override is None and {"kind", "scope_kind", "guid", "sid", "id"} & set(
                    scope_overrides
                ):
                    override = scope_overrides
                if isinstance(override, Mapping):
                    scope = _scope_context({"scope": override}, record_kind)
                elif isinstance(override, str):
                    if record_kind != "Computer":
                        raise ValueError("scope context requires an explicit domain or host kind")
                    scope = ScopeIdentity("host", "guid", _as_guid(override) or "")
        except ValueError as exc:
            raise RecordError(
                str(exc), stage="normalize", record_id=_record_identifier(record)
            ) from exc
        if scope is None:
            raise RecordError(
                "namespace-relative SID requires a stable domain or host identity",
                stage="normalize",
                record_id=_record_identifier(record),
            )
        if candidate in {"S-1-5-18", "S-1-5-19", "S-1-5-20"} and scope.kind != "host":
            raise RecordError(
                "local service SID requires stable host scope",
                stage="normalize",
                record_id=_record_identifier(record),
            )
        if record_kind == "Computer" and candidate.startswith("S-1-5-32-") and scope.kind != "host":
            raise RecordError(
                "computer-local built-in SID requires host scope",
                stage="normalize",
                record_id=_record_identifier(record),
            )
        if (
            scope.identity_type == "sid"
            and candidate.startswith("S-1-5-32-")
            and scope.kind != "domain"
        ):
            raise RecordError(
                "built-in group SID requires domain scope",
                stage="normalize",
                record_id=_record_identifier(record),
            )
        return scope.canonical_sid(candidate)
    guid = _as_guid(candidate)
    if guid is not None:
        return guid
    raise RecordError(
        "object identifier is not a valid SID or GUID",
        stage="normalize",
        record_id=_record_identifier(record),
    )


def _label(data: Mapping[str, Any], canonical_id: str) -> str:
    value = _lookup(
        data,
        (
            "label",
            "name",
            "Name",
            "samaccountname",
            "sAMAccountName",
            "displayname",
            "principalname",
        ),
    )
    if isinstance(value, str) and value.strip():
        return value.strip()
    return canonical_id


def _domain(data: Mapping[str, Any], label: str) -> str:
    value = _lookup(data, ("domain", "Domain", "domain_name", "domainName"))
    if isinstance(value, str) and value.strip():
        return value.strip()
    distinguished_name = _lookup(data, ("distinguishedname", "distinguishedName", "dn"))
    if isinstance(distinguished_name, str):
        parts = [match.group(1) for match in DN_DOMAIN_RE.finditer(distinguished_name)]
        if parts:
            return ".".join(parts)
    if label and "." in label and "@" not in label:
        # Domain records commonly use their DNS name as both label and domain.
        return label
    raise RecordError("missing domain context", stage="normalize", record_id=label)


def _node_attributes(record: RawRecord, canonical_id: str, kind: str) -> RecordData:
    data = record.data
    label = _label(data, canonical_id)
    boundary = _lookup(data, ("is_boundary", "isBoundary", "boundary"))
    if boundary is not None and type(boundary) is not bool:
        raise RecordError("is_boundary must be boolean", stage="normalize", record_id=canonical_id)
    attributes: dict[str, Any] = {
        "id": canonical_id,
        "kind": kind,
        "label": label,
        "domain": _domain(data, label),
        "is_boundary": boundary if boundary is not None else False,
    }
    for output, keys in {
        "enabled": ("enabled", "Enabled"),
        "admincount": ("admincount", "adminCount", "admincountvalue", "AdminCount"),
        "distinguishedname": ("distinguishedname", "distinguishedName", "dn"),
    }.items():
        value = _lookup(data, keys)
        if value is None:
            continue
        if output == "enabled" and type(value) is not bool:
            raise RecordError("enabled must be boolean", stage="normalize", record_id=canonical_id)
        if output == "admincount" and type(value) not in {bool, int}:
            raise RecordError(
                "admincount must be boolean or integer", stage="normalize", record_id=canonical_id
            )
        if output == "distinguishedname" and (not isinstance(value, str) or not value.strip()):
            raise RecordError(
                "distinguishedname must be a non-empty string",
                stage="normalize",
                record_id=canonical_id,
            )
        attributes[output] = value
    return attributes


class Normalizer(NormalizerInterface):
    """Concrete canonical identity normalizer for BloodHound-style records."""

    def __init__(self, *, scope_context: Mapping[str, object] | None = None) -> None:
        self.scope_context = dict(scope_context or {})

    def normalize(self, record: RawRecord) -> NormalizedRecord:
        if not isinstance(record, RawRecord):
            raise TypeError("record must be a RawRecord")
        try:
            kind = _kind(record.kind)
        except ValueError as exc:
            raise RecordError(
                str(exc), stage="normalize", record_id=_record_identifier(record)
            ) from exc
        canonical_id = _canonical_id(record, kind, self.scope_context)
        return NormalizedRecord(
            id=canonical_id,
            kind=kind,
            attributes=_node_attributes(record, canonical_id, kind),
            raw=record,
            raw_provenance=(record.provenance,),
            evidence_lineage=(),
        )

    def normalize_records(
        self,
        records: Iterable[RawRecord],
        *,
        error_policy: ErrorPolicy = ErrorPolicy.FAIL_FAST,
    ) -> list[NormalizedRecord]:
        """Reconcile the snapshot, then normalize records under the shared error policy.

        Reconciliation happens before record-level error handling because merge conflicts
        affect the interpretation of the snapshot and cannot safely be skipped. Once the
        logical records are established, recoverable normalization ``RecordError`` values
        use the shared :func:`process_records` policy.
        """
        if not isinstance(error_policy, ErrorPolicy):
            raise TypeError("error_policy must be an ErrorPolicy")

        merged: dict[str, NormalizedRecord] = {}

        def normalize_reconciled(reconciled):
            record = RawRecord(
                kind=reconciled.kind,
                data=reconciled.data,
                provenance=reconciled.provenance[0],
            )
            normalized = self.normalize(record)
            normalized = NormalizedRecord(
                id=normalized.id,
                kind=normalized.kind,
                attributes=normalized.attributes,
                raw=normalized.raw,
                raw_provenance=reconciled.provenance,
                evidence_lineage=reconciled.evidence_lineage,
                raw_representations=tuple(item.record for item in reconciled.representations),
            )
            return normalized

        normalized_records = process_records(
            reconcile_raw_records(records),
            normalize_reconciled,
            error_policy=error_policy,
        )
        for normalized in normalized_records:
            previous = merged.get(normalized.id)
            if previous is None:
                merged[normalized.id] = normalized
                continue
            if previous.kind != normalized.kind:
                raise RecordError(
                    f"canonical ID conflicts across kinds {previous.kind} and {normalized.kind}",
                    stage="normalize",
                    record_id=normalized.id,
                )
            raise RecordError(
                "canonical ID is produced by multiple reconciliation groups",
                stage="normalize",
                record_id=normalized.id,
            )
        return [merged[record_id] for record_id in sorted(merged)]

    normalize_many = normalize_records
    normalize_batch = normalize_records
    merge_records = normalize_records


IdentityNormalizer = Normalizer
RecordNormalizer = Normalizer

__all__ = ["IdentityNormalizer", "Normalizer", "RecordNormalizer"]
