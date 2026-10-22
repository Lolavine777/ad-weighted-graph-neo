"""Adapt BloodHound v3 identifiers using snapshot-observed scope identities."""

from __future__ import annotations

import copy
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from .. import RawRecord, RecordError
from ..identity_fields import lookup_raw_identifier
from ..scopes import (
    ScopeIdentity,
    is_valid_sid,
    normalize_domain_sid,
    normalize_guid,
    normalize_sid,
)

_SID = re.compile(r"^S-1-(?:0|[1-9][0-9]*)(?:-(?:0|[1-9][0-9]*)){1,15}$", re.IGNORECASE)
_QUALIFIED_SID = re.compile(
    r"^(?P<domain>[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?)-(?P<sid>S-1-(?:0|[1-9][0-9]*)(?:-(?:0|[1-9][0-9]*)){1,15})$",
    re.IGNORECASE,
)
_ID_KEYS = frozenset(
    {
        "objectidentifier",
        "objectid",
        "memberid",
        "principalsid",
        "usersid",
        "groupid",
        "computersid",
        "sid",
        "primarygroupsid",
        "primary_group_sid",
    }
)
_HOST_LOCAL_FIELDS = frozenset(
    {"localgroups", "localadmins", "remotedesktopusers", "dcomusers", "psremoteusers"}
)


@dataclass(frozen=True)
class DomainScopeContext:
    """Identity observed on a Domain record; GUID has canonical precedence."""

    name: str
    domain_guid: str | None
    domain_sid: str | None

    @property
    def scope(self) -> ScopeIdentity | None:
        if self.domain_guid is not None:
            return ScopeIdentity("domain", "guid", self.domain_guid)
        if self.domain_sid is not None:
            return ScopeIdentity("domain", "sid", self.domain_sid)
        return None


def normalize_domain_name(value: object) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    return value.strip().rstrip(".").casefold()


def parse_qualified_sid(value: str) -> tuple[str, str] | None:
    """Return (domain hint, valid SID suffix) for a BloodHound v3 identifier."""
    match = _QUALIFIED_SID.fullmatch(value.strip())
    if match is None or not _valid_sid(match.group("sid")):
        return None
    return match.group("domain"), match.group("sid").upper()


def _valid_sid(value: str) -> bool:
    return bool(_SID.fullmatch(value)) and is_valid_sid(value)


def _first(mapping: Mapping[str, object], names: Iterable[str]) -> object | None:
    wanted = {name.casefold() for name in names}
    for key, value in mapping.items():
        if isinstance(key, str) and key.casefold() in wanted and value is not None:
            return value
    return None


def _properties(record: RawRecord) -> Mapping[str, object]:
    value = _first(record.data, ("Properties", "properties", "Attributes", "attributes"))
    return value if isinstance(value, Mapping) else {}


def _domain_guid(record: RawRecord) -> str | None:
    props = _properties(record)
    raw = _first(record.data, ("ObjectGUID", "DomainGUID", "domain_guid"))
    if raw is None:
        raw = _first(props, ("ObjectGUID", "DomainGUID", "domain_guid"))
    object_id = lookup_raw_identifier(record.data)
    if raw is None and normalize_guid(object_id) is not None:
        raw = object_id
    if raw is None:
        return None
    guid = normalize_guid(raw)
    if guid is None:
        raise RecordError("Domain objectGUID is malformed", stage="adapt", record_id=str(raw))
    return guid


def _domain_sid(record: RawRecord) -> str | None:
    props = _properties(record)
    raw = _first(record.data, ("DomainSID", "domain_sid", "domainsid"))
    if raw is None:
        raw = _first(props, ("DomainSID", "domain_sid", "domainsid"))
    object_id = lookup_raw_identifier(record.data)
    if raw is None and isinstance(object_id, str) and _SID.fullmatch(object_id.strip()):
        raw = object_id
    elif raw is None and isinstance(object_id, str) and normalize_guid(object_id) is None:
        raise RecordError(
            "Domain SID is not a valid AD domain SID and identifier is not an objectGUID",
            stage="adapt",
            record_id=object_id,
        )
    if raw is None:
        prop_id = lookup_raw_identifier(props)
        if isinstance(prop_id, str) and _SID.fullmatch(prop_id.strip()):
            raw = prop_id
    if raw is None:
        return None
    sid = normalize_domain_sid(raw)
    if sid is None:
        raise RecordError(
            "Domain SID is not a valid AD domain SID", stage="adapt", record_id=str(raw)
        )
    return sid


def _domain_context(records: tuple[RawRecord, ...]) -> dict[str, DomainScopeContext]:
    context: dict[str, DomainScopeContext] = {}
    for record in records:
        if record.kind.casefold() not in {"domain", "domains"}:
            continue
        props = _properties(record)
        names = {
            normalize_domain_name(_first(props, ("domain", "name", "DNSName"))),
        }
        dn = _first(props, ("distinguishedname", "distinguishedName", "dn"))
        if isinstance(dn, str):
            dc_parts = re.findall(r"(?:^|,)DC=([^,]+)", dn, flags=re.IGNORECASE)
            if dc_parts:
                names.add(normalize_domain_name(".".join(dc_parts)))
        names.discard(None)
        if not names:
            raise RecordError(
                "Domain record has no DNS name for qualified identifier mapping", stage="adapt"
            )
        guid = _domain_guid(record)
        sid = _domain_sid(record)
        for name in names:
            assert name is not None
            previous = context.get(name)
            if previous is not None:
                if previous.domain_guid and guid and previous.domain_guid != guid:
                    raise RecordError(
                        f"conflicting Domain objectGUID evidence for {name!r}", stage="adapt"
                    )
                if previous.domain_sid and sid and previous.domain_sid != sid:
                    raise RecordError(
                        f"conflicting Domain SID evidence for {name!r}", stage="adapt"
                    )
                guid = previous.domain_guid or guid
                sid = previous.domain_sid or sid
            context[name] = DomainScopeContext(name, guid, sid)
    return context


def _host_context(records: tuple[RawRecord, ...]) -> dict[str, ScopeIdentity]:
    context: dict[str, ScopeIdentity] = {}
    for record in records:
        if record.kind.casefold() not in {"computer", "computers", "host", "hosts"}:
            continue
        props = _properties(record)
        raw_guid = _first(
            record.data, ("ObjectGUID", "objectguid", "ComputerGUID", "computer_guid")
        )
        if raw_guid is None:
            raw_guid = _first(props, ("ObjectGUID", "objectguid", "ComputerGUID", "computer_guid"))
        object_id = lookup_raw_identifier(record.data)
        if raw_guid is None and normalize_guid(object_id) is not None:
            raw_guid = object_id
        guid = normalize_guid(raw_guid)
        if raw_guid is not None and guid is None:
            raise RecordError(
                "Computer objectGUID is malformed", stage="adapt", record_id=str(raw_guid)
            )
        if guid is None:
            continue
        identity = ScopeIdentity("host", "guid", guid)
        aliases: set[str] = set()
        name = _first(props, ("name", "DNSHostName", "dNSHostName"))
        domain = _first(props, ("domain", "domain_name", "domainName"))
        if isinstance(name, str):
            aliases.add(normalize_domain_name(name) or "")
            if isinstance(domain, str) and "." not in name:
                aliases.add(normalize_domain_name(f"{name}.{domain}") or "")
        aliases.discard("")
        for alias in aliases:
            previous = context.get(alias)
            if previous is not None and previous != identity:
                raise RecordError(f"conflicting host GUID evidence for {alias!r}", stage="adapt")
            context[alias] = identity
    return context


def _group_domain_sid(
    record: RawRecord, domains: Mapping[str, DomainScopeContext]
) -> tuple[str, str] | None:
    if record.kind.casefold() not in {"group", "groups"}:
        return None
    raw_id = lookup_raw_identifier(record.data)
    parsed = parse_qualified_sid(raw_id) if isinstance(raw_id, str) else None
    props = _properties(record)
    domain_name = normalize_domain_name(
        parsed[0] if parsed else _first(props, ("domain", "domain_name", "domainName"))
    )
    sid = parsed[1] if parsed else raw_id.strip() if isinstance(raw_id, str) else ""
    if domain_name not in domains or not re.fullmatch(
        r"S-1-5-32-(?:0|[1-9][0-9]*)", sid, re.IGNORECASE
    ):
        return None
    return domain_name, sid.upper()


def _observed_domain_groups(
    records: tuple[RawRecord, ...], domains: Mapping[str, DomainScopeContext]
) -> frozenset[tuple[str, str]]:
    return frozenset(
        key for record in records if (key := _group_domain_sid(record, domains)) is not None
    )


def _local_sid_kind(sid: str) -> str | None:
    if re.fullmatch(r"S-1-5-(?:18|19|20)", sid, re.IGNORECASE):
        return "host_only"
    if re.fullmatch(r"S-1-5-32-(?:0|[1-9][0-9]*)", sid, re.IGNORECASE):
        return "builtin"
    return None


def adapt_identifier(
    raw_identifier: str,
    domain_context: Mapping[str, DomainScopeContext | ScopeIdentity | str],
    *,
    host_context: Mapping[str, ScopeIdentity] | None = None,
    observed_domain_groups: frozenset[tuple[str, str]] = frozenset(),
    domain_hint: str | None = None,
    host_scope: ScopeIdentity | None = None,
    group_object: bool = False,
    host_local: bool = False,
) -> str:
    """Convert an identifier only when its semantic scope is evidenced."""
    candidate = raw_identifier.strip()
    parsed = parse_qualified_sid(candidate)
    prefix = normalize_domain_name(parsed[0]) if parsed else normalize_domain_name(domain_hint)
    sid = parsed[1] if parsed else candidate
    if not _valid_sid(sid):
        return raw_identifier
    sid = normalize_sid(sid)
    assert sid is not None
    local_kind = _local_sid_kind(sid)
    if local_kind is None:
        return sid

    host_context = host_context or {}
    if local_kind == "host_only" or host_local:
        scope = host_scope or (host_context.get(prefix) if prefix else None)
        if scope is None or scope.kind != "host" or scope.identity_type != "guid":
            raise RecordError(
                f"host-relative SID {sid} requires a stable host GUID; "
                "Domain SID cannot be used as fallback",
                stage="adapt",
                record_id=raw_identifier,
            )
        return scope.canonical_sid(sid)

    # S-1-5-32 aliases are contextual. Domain scope is justified only when a
    # matching Group object was actually observed in that Domain export.
    domain_key = prefix
    if domain_key is None:
        domain_key = normalize_domain_name(domain_hint)
    group_key = (domain_key, sid.upper()) if domain_key is not None else None
    if group_key is not None and group_key in observed_domain_groups:
        raw_domain = domain_context.get(domain_key)
        if isinstance(raw_domain, ScopeIdentity):
            scope = raw_domain
        elif isinstance(raw_domain, DomainScopeContext):
            scope = raw_domain.scope
        elif isinstance(raw_domain, str):
            guid = normalize_guid(raw_domain)
            scope = ScopeIdentity("domain", "guid", guid) if guid else None
        else:
            scope = None
        if scope is None:
            raise RecordError(
                f"namespace-relative SID {sid} has no stable Domain GUID or Domain SID "
                f"for {domain_key!r}",
                stage="adapt",
                record_id=raw_identifier,
            )
        return scope.canonical_sid(sid)

    if group_object:
        raise RecordError(
            f"Domain Group SID {sid} is not backed by an observed Group record and Domain scope",
            stage="adapt",
            record_id=raw_identifier,
        )
    if parsed is None:
        return raw_identifier
    # Leave an unobserved qualified reference unresolved; never infer its scope
    # from its DNS-looking prefix alone.
    return raw_identifier


def _record_domain_hint(record: RawRecord) -> str | None:
    value = _first(_properties(record), ("domain", "domain_name", "domainName"))
    return normalize_domain_name(value)


def _adapt_tree(
    value: object,
    *,
    domains: Mapping[str, DomainScopeContext],
    hosts: Mapping[str, ScopeIdentity],
    observed_groups: frozenset[tuple[str, str]],
    domain_hint: str | None,
    host_scope: ScopeIdentity | None,
    record_kind: str,
    domain_controller: bool = False,
    parent_key: str = "",
    root: bool = False,
) -> object:
    host_local = parent_key.casefold() in _HOST_LOCAL_FIELDS and not domain_controller
    if isinstance(value, list):
        return [
            _adapt_tree(
                item,
                domains=domains,
                hosts=hosts,
                observed_groups=observed_groups,
                domain_hint=domain_hint,
                host_scope=host_scope,
                record_kind=record_kind,
                domain_controller=domain_controller,
                parent_key=parent_key,
            )
            for item in value
        ]
    if isinstance(value, Mapping):
        result = {}
        for key, item in value.items():
            if isinstance(key, str) and key.casefold() in _ID_KEYS and isinstance(item, str):
                result[key] = adapt_identifier(
                    item,
                    domains,
                    host_context=hosts,
                    observed_domain_groups=observed_groups,
                    domain_hint=domain_hint,
                    host_scope=host_scope,
                    group_object=root and record_kind.casefold() in {"group", "groups"},
                    host_local=host_local,
                )
            else:
                result[key] = _adapt_tree(
                    item,
                    domains=domains,
                    hosts=hosts,
                    observed_groups=observed_groups,
                    domain_hint=domain_hint,
                    host_scope=host_scope,
                    record_kind=record_kind,
                    domain_controller=domain_controller,
                    parent_key=str(key),
                )
        return result
    return value


def adapt_bloodhound_v3_records(records: Iterable[RawRecord]) -> tuple[RawRecord, ...]:
    """Adapt v3-style qualified identifiers using two-pass snapshot scope evidence."""
    materialized = tuple(records)
    if not any(
        record.provenance.get("schema_version") == "3"
        or (
            isinstance(object_id := lookup_raw_identifier(record.data), str)
            and parse_qualified_sid(object_id) is not None
        )
        for record in materialized
    ):
        return materialized
    domains = _domain_context(materialized)
    hosts = _host_context(materialized)
    observed_groups = _observed_domain_groups(materialized, domains)
    adapted: list[RawRecord] = []
    for record in materialized:
        props = _properties(record)
        domain_hint = _record_domain_hint(record)
        if domain_hint not in domains and record.kind.casefold() in {"group", "groups"}:
            object_id = lookup_raw_identifier(record.data)
            parsed = parse_qualified_sid(object_id) if isinstance(object_id, str) else None
            domain_hint = normalize_domain_name(parsed[0]) if parsed else domain_hint
        host_scope = None
        domain_controller = False
        if record.kind.casefold() in {"computer", "computers", "host", "hosts"}:
            domain = domains.get(domain_hint)
            if domain is not None and domain.domain_sid is not None:
                domain_controller = record.data.get("PrimaryGroupSID") in {
                    domain.domain_sid + "-516",
                    domain.domain_sid + "-521",
                }
            object_id = lookup_raw_identifier(record.data)
            aliases = [
                normalize_domain_name(_first(props, ("name", "DNSHostName", "dNSHostName"))),
            ]
            if isinstance(object_id, str):
                parsed = parse_qualified_sid(object_id)
                if parsed:
                    aliases.append(normalize_domain_name(parsed[0]))
            host_scope = next((hosts[a] for a in aliases if a in hosts), None)
        data = copy.deepcopy(dict(record.data))
        data = _adapt_tree(
            data,
            domains=domains,
            hosts=hosts,
            observed_groups=observed_groups,
            domain_hint=domain_hint,
            host_scope=host_scope,
            record_kind=record.kind,
            domain_controller=domain_controller,
            root=True,
        )
        adapted.append(RawRecord(kind=record.kind, data=data, provenance=record.provenance))
    return tuple(adapted)
