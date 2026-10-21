"""Typed stable identity for a namespace-relative SID's containing scope."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

ScopeKind = Literal["domain", "host"]
ScopeIdentityType = Literal["guid", "sid"]

_GUID_RE = re.compile(
    r"^(?:\{)?(?P<guid>[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12})(?:\})?$"
)
_SID_RE = re.compile(r"^S-1-(?:0|[1-9][0-9]*)(?:-(?:0|[1-9][0-9]*)){1,15}$", re.IGNORECASE)
_DOMAIN_SID_RE = re.compile(
    r"^S-1-5-21-(?:0|[1-9][0-9]*)-(?:0|[1-9][0-9]*)-(?:0|[1-9][0-9]*)$",
    re.IGNORECASE,
)


def normalize_guid(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    match = _GUID_RE.fullmatch(value.strip())
    return match.group("guid").lower() if match else None


def is_valid_sid(value: object) -> bool:
    if not isinstance(value, str) or not _SID_RE.fullmatch(value):
        return False
    components = value.split("-")[2:]
    return int(components[0]) <= (1 << 48) - 1 and all(
        int(component) <= (1 << 32) - 1 for component in components[1:]
    )


def normalize_sid(value: object) -> str | None:
    """Accept SID input case insensitively and emit canonical uppercase S."""
    return value.upper() if is_valid_sid(value) else None


def normalize_domain_sid(value: object) -> str | None:
    if not isinstance(value, str) or not _DOMAIN_SID_RE.fullmatch(value):
        return None
    if not is_valid_sid(value):
        return None
    return normalize_sid(value)


@dataclass(frozen=True)
class ScopeIdentity:
    """A scope kind plus an observed, stable GUID or domain SID identity."""

    kind: ScopeKind
    identity_type: ScopeIdentityType
    value: str

    def __post_init__(self) -> None:
        if self.kind not in {"domain", "host"}:
            raise ValueError("scope kind must be 'domain' or 'host'")
        if self.identity_type == "guid":
            normalized = normalize_guid(self.value)
            if normalized is None:
                raise ValueError("scope GUID is invalid")
            object.__setattr__(self, "value", normalized)
        elif self.identity_type == "sid":
            if self.kind != "domain":
                raise ValueError("SID scope identity is supported only for domain scopes")
            normalized = normalize_domain_sid(self.value)
            if normalized is None:
                raise ValueError("scope SID must be a valid AD domain SID")
            object.__setattr__(self, "value", normalized)
        else:
            raise ValueError("scope identity type must be 'guid' or 'sid'")

    def canonical_sid(self, sid: str) -> str:
        canonical = normalize_sid(sid)
        if canonical is None:
            raise ValueError("target SID is invalid")
        if self.identity_type == "sid":
            return f"domain:sid:{self.value}:{canonical}"
        return f"{self.kind}:{self.value}:{canonical}"


def parse_scoped_sid(value: str) -> tuple[ScopeIdentity, str] | None:
    """Parse both the legacy GUID grammar and the explicit domain SID grammar."""
    pieces = value.split(":")
    try:
        if len(pieces) == 3 and pieces[0] in {"domain", "host"}:
            scope = ScopeIdentity(pieces[0], "guid", pieces[1])
            sid = pieces[2]
            canonical = normalize_sid(sid)
            return (scope, canonical) if canonical is not None else None
        if len(pieces) == 4 and pieces[0:2] == ["domain", "sid"]:
            scope = ScopeIdentity("domain", "sid", pieces[2])
            sid = pieces[3]
            canonical = normalize_sid(sid)
            return (scope, canonical) if canonical is not None else None
    except ValueError:
        return None
    return None


__all__ = [
    "ScopeIdentity",
    "ScopeIdentityType",
    "ScopeKind",
    "is_valid_sid",
    "normalize_domain_sid",
    "normalize_guid",
    "normalize_sid",
    "parse_scoped_sid",
]
