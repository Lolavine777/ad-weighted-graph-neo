"""Typed semantic metadata; none of these fields extend canonical graph records."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, Literal, get_args

from src.data.manifest import (
    canonical_path,
    raw_file_reference,
    read_verified_snapshot_file,
    resolve_reference,
    validate_manifest,
    verify_manifest,
)

type NodeKind = Literal["User", "Group", "Computer", "Domain", "OU", "GPO"]
type RelationshipKind = Literal[
    "MemberOf",
    "AdminTo",
    "GenericAll",
    "WriteDacl",
    "ForceChangePassword",
    "CanRDP",
    "CanPSRemote",
    "HasSession",
]
type StructuralRelationshipKind = RelationshipKind
type CapabilityRelationshipKind = Literal[
    "AuthenticationControl",
    "DeclaredHostAdmin",
    "RoastTarget",
    "TicketMaterial",
    "RecoveredSecret",
    "ASRepTarget",
    "ASRepMaterial",
    "RBCDReset",
    "RBCDPrepare",
    "RBCDConfigure",
    "RBCDDelegate",
    "RBCDAsset",
]
type SemanticRelationshipKind = RelationshipKind | CapabilityRelationshipKind

STRUCTURAL_RELATIONSHIP_KINDS = frozenset(get_args(RelationshipKind.__value__))
CAPABILITY_RELATIONSHIP_KINDS = frozenset(get_args(CapabilityRelationshipKind.__value__))

type SemanticClass = Literal[
    "entitlement",
    "host_admin",
    "object_control",
    "graph_mutation",
    "authentication_control",
    "remote_interactive",
    "remote_command",
    "credential_opportunity",
]


class Effect(StrEnum):
    EFFECTIVE_MEMBER = "effective_member"
    ADMIN_CONTROL = "admin_control"
    INTERACTIVE_SESSION = "interactive_session"
    REMOTE_COMMAND_EXECUTION = "remote_command_execution"
    CREDENTIAL_MATERIAL = "credential_material"
    AUTHENTICATION_CONTROL = "authentication_control"
    RESET_PASSWORD_CONTROL = "reset_password_control"
    USABLE_IDENTITY = "usable_identity"
    ASREP_MATERIAL = "asrep_material"
    SERVICE_TICKET_MATERIAL = "service_ticket_material"
    RECOVERED_SECRET = "recovered_secret"
    GRANT_GENERIC_ALL = "grant_generic_all"
    GRANT_WRITE_DACL = "grant_write_dacl"
    ADD_MEMBERSHIP = "add_membership"
    RBCD_SECRET = "rbcd_secret"
    CONTROLLED_SERVICE = "controlled_service"
    RBCD_DESCRIPTOR = "rbcd_descriptor"
    DELEGATED_CONTEXT = "delegated_context"


class SemanticEvidenceType(StrEnum):
    AUTHORITATIVE_REFERENCE = "authoritative_reference"
    ATTACK_FRAMEWORK_REFERENCE = "attack_framework_reference"
    TOOL_SEMANTICS_REFERENCE = "tool_semantics_reference"
    RESEARCH_RATIONALE = "research_rationale"


@dataclass(frozen=True)
class SemanticEvidenceRef:
    """A source supporting a normative catalog mapping, not an observed event."""

    id: str
    type: SemanticEvidenceType
    source: str
    locator: str
    claim: str
    rationale: str
    confidence: Literal["low", "medium", "high"]


@dataclass(frozen=True)
class ExpectedTelemetry:
    provider: str
    event_id: int | None
    requirement: str
    evidence_refs: tuple[str, ...]


_DATASET_ID = re.compile(r"[a-z0-9][a-z0-9_-]{0,63}\Z")
_SNAPSHOT_ID = re.compile(r"sha256:[0-9a-f]{64}\Z")
_RECORD_HASH = re.compile(r"[0-9a-f]{64}\Z")


@dataclass(frozen=True)
class TelemetryRecordLocator:
    """A repository-defined location inside an immutable telemetry file."""

    kind: Literal["csv_row", "content_hash"]
    value: int | str

    def __post_init__(self) -> None:
        if self.kind == "csv_row":
            if type(self.value) is not int or self.value < 1:
                raise ValueError("csv_row locator requires a positive 1-based row")
        elif self.kind == "content_hash":
            if not isinstance(self.value, str) or _RECORD_HASH.fullmatch(self.value) is None:
                raise ValueError("content_hash locator requires a lowercase SHA-256")
        else:
            raise ValueError("unsupported telemetry record locator kind")


@dataclass(frozen=True)
class TelemetryRecordRef:
    """Immutable dataset/file/record identity for one telemetry observation."""

    dataset_id: str
    snapshot_id: str
    raw_file: str
    record_locator: TelemetryRecordLocator
    _manifest_backed: bool = field(default=False, init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        if _DATASET_ID.fullmatch(self.dataset_id) is None:
            raise ValueError("invalid telemetry dataset_id")
        if _SNAPSHOT_ID.fullmatch(self.snapshot_id) is None:
            raise ValueError("invalid telemetry snapshot_id")
        if not isinstance(self.raw_file, str) or not self.raw_file.startswith("snapshot:"):
            raise ValueError("raw_file must be a manifest snapshot reference")
        prefix, separator, relative = self.raw_file.partition("/")
        if (
            not separator
            or prefix != f"snapshot:{self.snapshot_id.removeprefix('sha256:')}"
            or canonical_path(relative) != relative
        ):
            raise ValueError("raw_file must match snapshot and use a canonical relative path")

    @classmethod
    def from_manifest(
        cls,
        manifest: dict,
        relative_path: str,
        record_locator: TelemetryRecordLocator,
        *,
        source: Path,
    ) -> TelemetryRecordRef:
        """Build a reference only after verifying the locator in immutable file bytes."""

        validate_manifest(manifest)
        reference = cls(
            manifest["dataset_id"],
            manifest["snapshot_id"],
            raw_file_reference(manifest, relative_path),
            record_locator,
        )
        validate_telemetry_record_ref(reference, manifest, source=source)
        object.__setattr__(reference, "_manifest_backed", True)
        return reference


def _csv_record_hashes(payload: bytes) -> tuple[str, ...]:
    try:
        rows = csv.reader(io.StringIO(payload.decode("utf-8-sig"), newline=""))
        next(rows)  # The telemetry CSV has a header; locators address data rows only.
        return tuple(
            hashlib.sha256(
                json.dumps(row, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
            ).hexdigest()
            for row in rows
        )
    except (UnicodeDecodeError, csv.Error, StopIteration) as exc:
        raise ValueError("telemetry source is not a readable CSV with a header") from exc


def validate_telemetry_record_ref(
    reference: TelemetryRecordRef, manifest: dict, *, source: Path
) -> None:
    """Require that a record reference resolves to an actual record in verified bytes."""

    validate_manifest(manifest)
    discrepancies = verify_manifest(source, manifest)
    if discrepancies:
        raise ValueError(f"telemetry snapshot differs from manifest: {discrepancies}")
    if reference.dataset_id != manifest["dataset_id"]:
        raise ValueError("telemetry dataset_id does not match manifest")
    if reference.snapshot_id != manifest["snapshot_id"]:
        raise ValueError("telemetry snapshot_id does not match manifest")
    if resolve_reference(manifest, reference.raw_file) not in {
        entry["relative_path"] for entry in manifest["files"]
    }:
        raise ValueError("telemetry raw_file is absent from manifest")
    payload = read_verified_snapshot_file(source, manifest, reference.raw_file)
    hashes = _csv_record_hashes(payload)
    if reference.record_locator.kind == "csv_row":
        if reference.record_locator.value > len(hashes):
            raise ValueError("telemetry csv_row locator is outside the verified file")
    else:
        matches = hashes.count(reference.record_locator.value)
        if matches != 1:
            raise ValueError("telemetry content_hash locator is not a unique verified record")


@dataclass(frozen=True)
class ConfirmationBasis:
    """Explicit analyst/independent evidence required for a confirmed conclusion."""

    kind: Literal["analyst_review", "independent_evidence"]
    reference: str
    rationale: str

    def __post_init__(self) -> None:
        if self.kind not in {"analyst_review", "independent_evidence"}:
            raise ValueError("invalid confirmation basis")
        if not all(
            isinstance(value, str) and value.strip() for value in (self.reference, self.rationale)
        ):
            raise ValueError("confirmation basis requires reference and rationale")


@dataclass(frozen=True)
class Technique:
    id: str
    relationship: SemanticRelationshipKind
    semantic_class: SemanticClass
    source_kinds: tuple[NodeKind, ...]
    target_kinds: tuple[NodeKind, ...]
    action_required: bool
    prerequisites: tuple[str, ...]
    effects: tuple[Effect, ...]
    failure_conditions: tuple[str, ...]
    expected_telemetry: tuple[ExpectedTelemetry, ...]
    attack_refs: tuple[str, ...]
    confidence: Literal["low", "medium", "high"]
    cost_factors: tuple[str, ...]
    remediation: tuple[str, ...]


@dataclass(frozen=True, order=True)
class StructuralRelationship:
    source: str
    kind: StructuralRelationshipKind
    target: str

    def __post_init__(self):
        if self.kind not in STRUCTURAL_RELATIONSHIP_KINDS:
            raise ValueError(f"invalid structural relationship kind: {self.kind}")


@dataclass(frozen=True)
class CapabilityRelationship:
    """Search trigger only; never canonical or a derived structural permission."""

    source: str
    kind: CapabilityRelationshipKind
    target: str

    def __post_init__(self):
        if self.kind not in CAPABILITY_RELATIONSHIP_KINDS:
            raise ValueError(f"invalid capability relationship kind: {self.kind}")


class FactOrigin(StrEnum):
    OBSERVED_EVIDENCE = "observed_evidence"
    DECLARED_ASSUMPTION = "declared_assumption"
    TECHNICAL_RULE = "technical_rule"
    BLOCKED_EVIDENCE = "blocked_evidence"
    UNSPECIFIED = "unspecified"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class RuntimeFact:
    """Typed, auditable runtime fact supporting transition evaluation."""

    predicate: str
    subject: str
    target: str
    value: bool | None
    origin: FactOrigin | str
    scope: str | None = None
    rationale: str | None = None
    provenance_reference: str | None = None
    assumption_metadata: Mapping[str, Any] | None = None

    def __post_init__(self) -> None:
        if not (
            isinstance(self.predicate, str)
            and self.predicate.strip()
            and isinstance(self.subject, str)
            and self.subject.strip()
            and isinstance(self.target, str)
            and self.target.strip()
        ):
            raise ValueError("RuntimeFact requires non-empty predicate, subject, and target")
        try:
            origin = FactOrigin(self.origin)
        except ValueError as err:
            raise ValueError(f"invalid FactOrigin: {self.origin!r}") from err
        object.__setattr__(self, "origin", origin)
        if origin == FactOrigin.DECLARED_ASSUMPTION:
            if not (isinstance(self.rationale, str) and self.rationale.strip()):
                raise ValueError("declared assumption requires non-empty rationale")
            if not (isinstance(self.scope, str) and self.scope.strip()):
                raise ValueError("declared assumption requires non-empty scope")


@dataclass(frozen=True)
class PrerequisiteDecision:
    """Audit record for a single technique prerequisite evaluation."""

    predicate: str
    satisfied: bool
    origin: FactOrigin | str
    fact: RuntimeFact | None = None
    rationale: str | None = None


@dataclass(frozen=True)
class ObservedActivity:
    environment_id: str
    identity_namespace: str
    timestamp: datetime
    actor: str
    target: str
    provider: str
    event_id: int | None
    provenance: TelemetryRecordRef

    def __post_init__(self) -> None:
        if not self.provenance._manifest_backed:
            raise ValueError("observed activity provenance must be created from a manifest")
        if not all(
            isinstance(value, str) and value.strip()
            for value in (
                self.environment_id,
                self.identity_namespace,
                self.actor,
                self.target,
                self.provider,
            )
        ):
            raise ValueError("observed activity identity fields are required")
        if self.timestamp.tzinfo is None:
            raise ValueError("observed activity timestamp must be timezone-aware")
        if self.event_id is not None and (type(self.event_id) is not int or self.event_id <= 0):
            raise ValueError("observed activity event_id must be a positive integer")


@dataclass(frozen=True)
class CorrelationRecord:
    """A candidate/rejected join; it is never a confirmation by construction."""

    technique_id: str
    structural_relationship: StructuralRelationship
    observed_activity: ObservedActivity
    context: EvidenceContext
    status: Literal["candidate", "rejected"]
    rationale: str

    def __post_init__(self) -> None:
        if self.status not in {"candidate", "rejected"}:
            raise ValueError("correlation status must be candidate or rejected")
        if not self.technique_id.strip() or not self.rationale.strip():
            raise ValueError("correlation requires technique and rationale")
        _validate_correlation(self)


@dataclass(frozen=True)
class ConfirmedAttack:
    """External analyst conclusion; never constructed by transition evaluation."""

    technique_id: str
    evidence: tuple[ObservedActivity, ...]
    rationale: str
    confirmation: ConfirmationBasis

    def __post_init__(self) -> None:
        if not self.evidence:
            raise ValueError("confirmed attack requires observed evidence")
        if not self.rationale.strip():
            raise ValueError("confirmed attack requires rationale")


@dataclass(frozen=True)
class EvidenceContext:
    environment_id: str
    identity_namespace: str
    start: datetime
    end: datetime


def correlate_activity(
    activity: ObservedActivity, context: EvidenceContext, actor: str, target: str
) -> bool:
    """Gate entity matching on explicit environment, identity and time evidence.

    A match is only a candidate activity, not confirmation of a technique.
    Missing or incompatible context is rejected before entity comparison.
    """
    if (
        not context.environment_id.strip()
        or not context.identity_namespace.strip()
        or activity.environment_id != context.environment_id
        or activity.identity_namespace != context.identity_namespace
        or any(t.tzinfo is None for t in (context.start, context.end, activity.timestamp))
        or context.start > context.end
        or not context.start <= activity.timestamp <= context.end
    ):
        raise ValueError("activity lacks compatible environment, identity or time context")
    return activity.actor == actor and activity.target == target


def correlate_candidate(
    activity: ObservedActivity,
    context: EvidenceContext,
    technique_id: str,
    relationship: StructuralRelationship,
) -> CorrelationRecord:
    """Create an explicit candidate/rejected record after fail-closed compatibility checks."""

    _validate_technique_relationship(technique_id, relationship)
    compatible = correlate_activity(activity, context, relationship.source, relationship.target)
    return CorrelationRecord(
        technique_id,
        relationship,
        activity,
        context,
        "candidate" if compatible else "rejected",
        "environment, identity namespace and time window are compatible"
        if compatible
        else "activity actor/target does not match the structural relationship",
    )


def confirm_candidate(
    correlation: CorrelationRecord, confirmation: ConfirmationBasis
) -> ConfirmedAttack:
    """Require explicit stronger evidence before constructing a ConfirmedAttack."""

    if correlation.status != "candidate":
        raise ValueError("only a candidate correlation can be explicitly confirmed")
    _validate_correlation(correlation)
    return ConfirmedAttack(
        technique_id=correlation.technique_id,
        evidence=(correlation.observed_activity,),
        rationale=correlation.rationale,
        confirmation=confirmation,
    )


def _validate_technique_relationship(
    technique_id: str, relationship: StructuralRelationship
) -> None:
    from .catalog import load_catalog

    technique = next((item for item in load_catalog() if item.id == technique_id), None)
    if technique is None:
        raise ValueError(f"unknown technique: {technique_id}")
    if technique.relationship != relationship.kind:
        raise ValueError("technique relationship does not match structural relationship")


def _validate_correlation(correlation: CorrelationRecord) -> None:
    _validate_technique_relationship(correlation.technique_id, correlation.structural_relationship)
    compatible = correlate_activity(
        correlation.observed_activity,
        correlation.context,
        correlation.structural_relationship.source,
        correlation.structural_relationship.target,
    )
    expected_status = "candidate" if compatible else "rejected"
    if correlation.status != expected_status:
        raise ValueError(
            f"correlation status must be {expected_status} for actor/target compatibility"
        )
