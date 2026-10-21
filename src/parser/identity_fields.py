"""Shared raw-field lookup rules for parser identity handling."""

from __future__ import annotations

from collections.abc import Mapping

from . import JSONValue

# This is the authoritative raw identifier alias set used before canonical ID
# resolution. Matching is case-insensitive while iteration remains input-order
# deterministic, matching the parser's existing lookup convention.
RAW_IDENTIFIER_KEYS = (
    "ObjectIdentifier",
    "objectidentifier",
    "objectid",
    "ObjectId",
    "object_sid",
    "objectsid",
    "ObjectSid",
    "sid",
    "SID",
    "objectguid",
    "ObjectGUID",
    "objectGuid",
    "guid",
    "GUID",
    "id",
)

_PROPERTY_CONTAINERS = ("properties", "property", "attributes", "Properties", "Attributes")


def lookup_raw_identifier(data: Mapping[str, JSONValue]) -> JSONValue | None:
    """Return the first non-null accepted raw identifier value.

    Top-level fields take precedence over property containers, and matching is
    case-insensitive in insertion order. The helper intentionally returns the
    raw value so callers can apply their own type/format validation.
    """

    wanted = {key.casefold() for key in RAW_IDENTIFIER_KEYS}
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


__all__ = ["RAW_IDENTIFIER_KEYS", "lookup_raw_identifier"]
