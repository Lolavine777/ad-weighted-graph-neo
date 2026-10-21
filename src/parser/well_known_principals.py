"""Narrow, documented Windows authority identities eligible for boundary nodes.

The DNS prefix in a v3 reference is collector context, not part of these SIDs.
Only entries with an established structural Group interpretation are supported.
"""

from __future__ import annotations

from .adapters.bloodhound_v3 import parse_qualified_sid
from .scopes import normalize_sid

# Microsoft MS-DTYP well-known SID structures and MS-ADTS IIS_IUSRS object.
# IUSR is an account in Windows; the v3 membership export represents its
# foreign-security-principal membership with MemberType Group. This mapping
# describes that graph endpoint role, not a collected AD Group object.
_BOUNDARY_GROUPS = {"S-1-5-4": "INTERACTIVE", "S-1-5-17": "IUSR"}


def boundary_group(reference: str) -> tuple[str, str] | None:
    """Return (global SID, label) only for explicitly supported identities.

    Callers also enforce relationship context: IUSR's Group-shaped endpoint
    is supported only for collector Group membership evidence.
    """

    parsed = parse_qualified_sid(reference)
    sid = parsed[1] if parsed else normalize_sid(reference)
    if sid is None or sid not in _BOUNDARY_GROUPS:
        return None
    return sid, _BOUNDARY_GROUPS[sid]
