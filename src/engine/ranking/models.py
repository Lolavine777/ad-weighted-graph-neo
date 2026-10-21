"""Data models, constants, and lossless rational helpers for engine path ranking.

Defines the contract structures and invariants for the versioned path-ranking
and evaluation boundary (Specification v1.0.0).
"""

from __future__ import annotations

import re
from enum import StrEnum
from fractions import Fraction
from typing import Any

# Graph Contract 1.3 canonical identifier patterns
CANONICAL_SID_PATTERN = re.compile(r"^S-1-(?:0|[1-9][0-9]*)(?:-(?:0|[1-9][0-9]*)){1,15}$")
CANONICAL_GUID_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
)
CANONICAL_SCOPED_SID_PATTERN = re.compile(
    r"^(?:(?:domain|host):[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}:"
    r"S-1-(?:0|[1-9][0-9]*)(?:-(?:0|[1-9][0-9]*)){1,15}|"
    r"domain:sid:S-1-5-21-(?:0|[1-9][0-9]*)-(?:0|[1-9][0-9]*)-(?:0|[1-9][0-9]*):"
    r"S-1-(?:0|[1-9][0-9]*)(?:-(?:0|[1-9][0-9]*)){1,15})$"
)
CANONICAL_EDGE_ID_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")
SNAPSHOT_ID_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")
SCOPE_REQUIRED_SID_PATTERN = re.compile(r"^S-1-5-(?:18|19|20|32-(?:0|[1-9][0-9]*))$")

REQUIRED_SCOPE_BINDING_FIELDS: tuple[str, ...] = (
    "query_id",
    "scenario_id",
    "scenario_version",
    "snapshot_id",
    "work_boundary",
    "horizon",
    "foothold_node_id",
)


class ConsequenceRating(StrEnum):
    """Business consequence impact rating ordinal levels."""

    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"
    CRITICAL = "Critical"


IMPACT_ORDINAL: dict[str, int] = {
    ConsequenceRating.LOW: 1,
    ConsequenceRating.MEDIUM: 2,
    ConsequenceRating.HIGH: 3,
    ConsequenceRating.CRITICAL: 4,
}


class EvaluationMode(StrEnum):
    """Query evaluation mode governing runtime context assumptions."""

    EVIDENCE_ONLY = "evidence_only"
    SCENARIO = "scenario"


class GateStatus(StrEnum):
    """Candidate gate evaluation status."""

    FEASIBLE = "feasible"
    BLOCKED = "blocked"
    UNKNOWN = "unknown"


class EffortStatus(StrEnum):
    """Effort rating status on canonical work unit ledger."""

    RATED = "rated"
    UNRATED = "unrated"
    INELIGIBLE = "ineligible"


class CompletenessScope(StrEnum):
    """Search space completeness and truncation disclosure scope."""

    EXHAUSTIVE_WITHIN_SCOPE = "exhaustive_within_scope"
    BUDGET_BOUNDED = "budget_bounded"
    PARTIAL_TRUNCATED = "partial_truncated"
    UNSPECIFIED_SUBSET = "unspecified_subset"


class ScopedPreferenceVerdict(StrEnum):
    """Pairwise conservative Pareto preference comparison verdict."""

    A = "a"
    B = "b"
    TIE = "tie"
    INCOMPARABLE = "incomparable"
    NOT_ELIGIBLE = "not_eligible"


class RankingEngineError(Exception):
    """Base exception for all path ranking engine errors."""


class RankingValidationError(RankingEngineError, ValueError):
    """Raised when an input query or candidate envelope violates contract specifications."""


class DuplicatePrefixError(RankingValidationError):
    """Raised when conditional_bounds_table contains duplicate prefix keys."""


class MappingSyncError(RankingEngineError, ValueError):
    """Raised when action-to-route synchronization cannot be verified 1-to-1 upon trimming."""


def is_canonical_node_id(node_id: Any) -> bool:
    """Validate canonical node ID against Graph Contract 1.3 schema.

    Enforces that namespace-relative SIDs (S-1-5-32-*) and host-relative SIDs
    (S-1-5-18/19/20) must be scoped. Unscoped bare forms are rejected.
    """
    if not isinstance(node_id, str) or not node_id.strip():
        return False
    is_unscoped_sid = bool(CANONICAL_SID_PATTERN.fullmatch(node_id))
    if is_unscoped_sid and SCOPE_REQUIRED_SID_PATTERN.fullmatch(node_id) is None:
        return True
    if bool(CANONICAL_GUID_PATTERN.fullmatch(node_id)):
        return True
    if bool(CANONICAL_SCOPED_SID_PATTERN.fullmatch(node_id)):
        return True
    return False


def is_canonical_edge_id(edge_id: Any) -> bool:
    """Validate canonical edge ID matching Graph Contract 1.3 format."""
    if not isinstance(edge_id, str):
        return False
    return bool(CANONICAL_EDGE_ID_PATTERN.fullmatch(edge_id))


def parse_rational(val: Any) -> Fraction:
    """Parse decimal string, integer, or Fraction into an exact stdlib Fraction.

    Strictly avoids float intermediate casting to eliminate precision drift.
    """
    if isinstance(val, Fraction):
        return val
    if isinstance(val, bool):
        raise TypeError(f"Boolean {val!r} is not a valid rational value")
    if isinstance(val, int):
        return Fraction(val, 1)
    if isinstance(val, str):
        cleaned = val.strip()
        if not cleaned:
            raise ValueError("Cannot parse rational from empty string")
        try:
            return Fraction(cleaned)
        except (ValueError, ZeroDivisionError) as err:
            raise ValueError(f"Invalid rational representation {val!r}: {err}") from err
    raise TypeError(f"Unsupported type {type(val)!r} for rational parsing: {val!r}")


def format_rational(val: Fraction | int) -> str:
    """Serialize Fraction or integer to a lossless rational string."""
    if isinstance(val, int):
        return str(val)
    if not isinstance(val, Fraction):
        val = parse_rational(val)
    if val.denominator == 1:
        return str(val.numerator)
    return f"{val.numerator}/{val.denominator}"
