"""Reviewed Work-Unit Classes and Effort Rating Provider (Issue #247, parent #245).

Generalizes the Week 3 instance-specific effort rubric into proposed, reusable
work-unit classes with scoped applicability, and implements EffortRatingProvider
for consumption by RatingResolver.

Architecture and Governance Invariants:
1. Strict integer rubrics:
   - T1 in {1, 2, 3} (tooling and technical complexity).
   - T2 in {1, 2, 3} (operational friction and defense posture).
   - Formula strictly "base", C = T1 + T2 - 2 in {0..4}.
2. Scoped applicability matching:
   - Matches candidate actions and work units by technique, execution method,
     security boundary, and authentication/resource context.
   - Fail-closed refusal if boundary violates scope (e.g. cross_forest).
   - Fail-closed conflict detection if multiple incompatible classes match.
3. Fail-closed disposition handling:
   - Work units with unresolved overlap (overlap_state == "unresolved_overlap")
     resolve to UNRATED with ReasonCode.EXPLICIT_UNRATED_DISPOSITION.
   - Unsupported techniques resolve to UNSUPPORTED with
     ReasonCode.UNSUPPORTED_TECHNIQUE.
   - Out-of-scope contexts resolve to REFUSED with ReasonCode.OUT_OF_SCOPE.
4. Anti-double-counting semantics:
   - Shared persistent preparation (e.g. w-auth-context) is classified as
     SHARED_PREPARATION with cost 1, evaluated once per distinct identity.
   - Passive closures (e.g. propagate_group_entitlement) incur no friction
     and generate no active work-unit cost.
5. Absolute refusal of unit weights (W=1.0) and maut_v1 fallback.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from src.engine.ranking.models import RankingValidationError
from src.engine.ranking.resolver import (
    BasisClassification,
    EffortLookupKey,
    ReasonCode,
    ResolutionResult,
    ResolverDisposition,
    WorkUnitClassification,
)

EFFORT_REGISTRY_VERSION = "1.0.0"


def _digest_data(data: Any) -> str:
    """Compute deterministic SHA-256 hex digest for canonical JSON."""
    raw = json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class ApplicabilityMatchResult(StrEnum):
    """Result of evaluating a work unit class applicability against a lookup key."""

    MATCH = "match"
    TECHNIQUE_MISMATCH = "technique_mismatch"
    METHOD_MISMATCH = "method_mismatch"
    BOUNDARY_MISMATCH = "boundary_mismatch"
    WORK_CLASS_MISMATCH = "work_class_mismatch"
    SCOPE_MISMATCH = "scope_mismatch"
    CONTEXT_MISMATCH = "context_mismatch"


@dataclass(frozen=True)
class ClassApplicability:
    """Defines the scoped execution boundary and context where a class applies.

    Guarantees that a work unit class is never applied outside its reviewed
    operational context, execution method, or security boundary.
    """

    techniques: tuple[str, ...]
    methods: tuple[str, ...] = ("*",)
    boundaries: tuple[str, ...] = (
        "intra_forest",
        "synthetic_two_routes",
        "scoped-rbcd-delegation",
    )
    work_classes: tuple[WorkUnitClassification, ...] = (
        WorkUnitClassification.ACTIVE_WORK,
        WorkUnitClassification.SHARED_PREPARATION,
    )
    scopes: tuple[str, ...] | None = None
    aliases: tuple[str, ...] = ()
    source_ids: tuple[str, ...] | None = None
    required_auth_context: str | None = None
    required_resource_context: str | None = None
    predicate: Callable[[EffortLookupKey, Mapping[str, Any], Mapping[str, Any]], bool] | None = None
    snapshot_ids: tuple[str, ...] | None = None
    work_unit_digests: tuple[str, ...] | None = None
    node_ids: tuple[str, ...] | None = None

    def evaluate(
        self,
        key: EffortLookupKey,
        record: Mapping[str, Any],
        scope: Mapping[str, Any],
    ) -> ApplicabilityMatchResult:
        """Evaluate applicability of this specification against key and record."""
        # 1. Technique check
        clean_tech = str(key.technique).strip()
        tech_matches = clean_tech in self.techniques
        if not tech_matches:
            return ApplicabilityMatchResult.TECHNIQUE_MISMATCH

        # 2. Boundary check (fail-closed refusal on boundary violation)
        if "*" not in self.boundaries and key.boundary not in self.boundaries:
            return ApplicabilityMatchResult.BOUNDARY_MISMATCH

        # 3. Work class check
        if key.work_class not in self.work_classes:
            return ApplicabilityMatchResult.WORK_CLASS_MISMATCH

        # 4. Method check
        if "*" not in self.methods:
            clean_method = str(key.method).strip()
            if clean_method not in self.methods:
                # Also check record method if different
                rec_method = str(record.get("method") or "").strip()
                if rec_method not in self.methods:
                    return ApplicabilityMatchResult.METHOD_MISMATCH

        # 5. Scope check (if specific scenarios declared)
        if self.scopes is not None:
            scope_id = str(scope.get("scenario_id") or key.scope or "").strip()
            if scope_id not in self.scopes:
                return ApplicabilityMatchResult.SCOPE_MISMATCH

        # 6. Auth / Resource context check
        if self.node_ids is not None and any(
            node not in self.node_ids
            for node in (key.actor_id, key.source_id or key.actor_id, key.target_id)
        ):
            return ApplicabilityMatchResult.CONTEXT_MISMATCH
        if self.source_ids is not None and key.source_id not in self.source_ids:
            return ApplicabilityMatchResult.CONTEXT_MISMATCH
        if self.snapshot_ids is not None and scope.get("snapshot_id") not in self.snapshot_ids:
            return ApplicabilityMatchResult.CONTEXT_MISMATCH
        if (
            self.work_unit_digests is not None
            and "sha256:" + _digest_data(key.work_unit_id) not in self.work_unit_digests
        ):
            return ApplicabilityMatchResult.CONTEXT_MISMATCH
        if self.required_auth_context is not None:
            if (key.auth_context or record.get("auth_context")) != self.required_auth_context:
                return ApplicabilityMatchResult.CONTEXT_MISMATCH
        if self.required_resource_context is not None:
            if (
                key.resource_context or record.get("resource_context")
            ) != self.required_resource_context:
                return ApplicabilityMatchResult.CONTEXT_MISMATCH

        # 7. Custom fine-grained predicate check
        if self.predicate is not None:
            try:
                if not self.predicate(key, record, scope):
                    return ApplicabilityMatchResult.CONTEXT_MISMATCH
            except Exception:
                return ApplicabilityMatchResult.CONTEXT_MISMATCH

        return ApplicabilityMatchResult.MATCH

    def to_dict(self) -> dict[str, Any]:
        return {
            "techniques": list(self.techniques),
            "methods": list(self.methods),
            "boundaries": list(self.boundaries),
            "work_classes": [str(wc) for wc in self.work_classes],
            "scopes": list(self.scopes) if self.scopes is not None else None,
            "aliases": list(self.aliases),
            **({"source_ids": list(self.source_ids)} if self.source_ids is not None else {}),
            **({"snapshot_ids": list(self.snapshot_ids)} if self.snapshot_ids is not None else {}),
            **({"node_ids": list(self.node_ids)} if self.node_ids is not None else {}),
            **(
                {"work_unit_digests": list(self.work_unit_digests)}
                if self.work_unit_digests is not None
                else {}
            ),
            "required_auth_context": self.required_auth_context,
            "required_resource_context": self.required_resource_context,
            "semantic_predicate": self.predicate.__name__ if self.predicate else None,
        }


@dataclass(frozen=True)
class WorkUnitClass:
    """Canonical reviewed work-unit class with scoped rubric and governance.

    Adheres strictly to the C rubric invariants:
    - T1 in {1, 2, 3}
    - T2 in {1, 2, 3}
    - formula is strictly 'base'
    - computed_cost = T1 + T2 - 2 in {0..4}
    """

    class_id: str
    name: str
    description: str
    t1: int
    t2: int
    applicability: ClassApplicability
    formula: str = "base"
    disposition: ResolverDisposition = ResolverDisposition.RATED
    unrated_reason_code: str | None = None
    unrated_reason_detail: str | None = None
    basis_category: str = BasisClassification.SCENARIO_ASSUMPTION.value
    review_reference: str = "docs/research/ratings/week4/reviewed-work-unit-classes.md"
    provenance_digest: str | None = None
    notes: str = ""
    review_status: str = "pending_b_review"
    numeric_basis_class: str | None = None

    def __post_init__(self) -> None:
        if not self.class_id or not isinstance(self.class_id, str):
            raise RankingValidationError("class_id must be a non-empty string")
        if self.formula != "base":
            raise RankingValidationError(
                f"Unsupported formula {self.formula!r}; only 'base' is permitted"
            )
        if self.disposition == ResolverDisposition.RATED:
            if type(self.t1) is not int or self.t1 not in (1, 2, 3):
                raise RankingValidationError(
                    f"t1 must be an exact integer in {{1, 2, 3}}, got {self.t1}"
                )
            if type(self.t2) is not int or self.t2 not in (1, 2, 3):
                raise RankingValidationError(
                    f"t2 must be an exact integer in {{1, 2, 3}}, got {self.t2}"
                )
            cost = self.t1 + self.t2 - 2
            if not (0 <= cost <= 4):
                raise RankingValidationError(f"computed_cost must be in range 0..4, got {cost}")

    @property
    def computed_cost(self) -> int | None:
        if self.disposition != ResolverDisposition.RATED:
            return None
        return self.t1 + self.t2 - 2

    @property
    def rubric_scores(self) -> dict[str, Any] | None:
        if self.disposition != ResolverDisposition.RATED:
            return None
        cost = self.computed_cost
        return {
            "t1": self.t1,
            "t2": self.t2,
            "formula": self.formula,
            "computed_cost": cost,
            "effort_cost": cost,
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "class_id": self.class_id,
            "name": self.name,
            "description": self.description,
            "t1": self.t1,
            "t2": self.t2,
            "formula": self.formula,
            "computed_cost": self.computed_cost,
            "disposition": str(self.disposition),
            "unrated_reason_code": self.unrated_reason_code,
            "unrated_reason_detail": self.unrated_reason_detail,
            "basis_category": self.basis_category,
            "review_reference": self.review_reference,
            "provenance_digest": self.provenance_digest,
            "notes": self.notes,
            "review_status": self.review_status,
            **(
                {"numeric_basis_class": self.numeric_basis_class}
                if self.numeric_basis_class is not None
                else {}
            ),
            "applicability": self.applicability.to_dict(),
        }

    def digest(self) -> str:
        return _digest_data(self.to_dict())


class WorkUnitClassRegistry:
    """Thread-safe catalog of reviewed work-unit classes with fail-closed matching."""

    def __init__(self, classes: Sequence[WorkUnitClass] = ()) -> None:
        self._classes_by_id: dict[str, WorkUnitClass] = {}
        for cls in classes:
            self.register(cls)

    def register(self, cls: WorkUnitClass) -> None:
        """Register a work unit class, ensuring no conflicting definitions."""
        if cls.class_id in self._classes_by_id:
            existing = self._classes_by_id[cls.class_id]
            if existing != cls:
                raise RankingValidationError(f"Conflicting class registration for {cls.class_id!r}")
        self._classes_by_id[cls.class_id] = cls

    def get(self, class_id: str) -> WorkUnitClass | None:
        """Retrieve class by exact identifier."""
        return self._classes_by_id.get(class_id)

    def list_classes(self) -> list[WorkUnitClass]:
        """Return all registered classes in deterministic order."""
        return [self._classes_by_id[k] for k in sorted(self._classes_by_id.keys())]

    def match(
        self,
        key: EffortLookupKey,
        record: Mapping[str, Any],
        scope: Mapping[str, Any],
    ) -> tuple[
        list[WorkUnitClass],
        list[tuple[WorkUnitClass, str]],
        list[tuple[WorkUnitClass, str]],
    ]:
        """Match registered classes against lookup key and record.

        Returns:
            (matches, boundary_refusals, context_mismatches) where:
            - matches is a list of applicable classes.
            - boundary_refusals is a list of (class, reason_detail) where the class matched
              the technique but failed due to boundary or scope constraint.
            - context_mismatches is a list of (class, reason_detail) where the class matched
              the technique and boundary, but failed a context constraint.
        """
        # If record explicitly specifies class_id, verify directly
        explicit_class_id = record.get("work_unit_class_id") or record.get("class_id")
        if explicit_class_id:
            cls = self.get(str(explicit_class_id))
            if cls is None:
                return [], [], []
            result = cls.applicability.evaluate(key, record, scope)
            if result == ApplicabilityMatchResult.MATCH:
                return [cls], [], []
            if result in (
                ApplicabilityMatchResult.BOUNDARY_MISMATCH,
                ApplicabilityMatchResult.SCOPE_MISMATCH,
            ):
                return (
                    [],
                    [(cls, f"Boundary {key.boundary!r} not permitted for class {cls.class_id}")],
                    [],
                )
            return [], [], [(cls, f"Context mismatch ({result.value}) for class {cls.class_id}")]

        matches: list[WorkUnitClass] = []
        boundary_refusals: list[tuple[WorkUnitClass, str]] = []
        context_mismatches: list[tuple[WorkUnitClass, str]] = []

        for cls in self.list_classes():
            res = cls.applicability.evaluate(key, record, scope)
            if res == ApplicabilityMatchResult.MATCH:
                matches.append(cls)
            elif res in (
                ApplicabilityMatchResult.BOUNDARY_MISMATCH,
                ApplicabilityMatchResult.SCOPE_MISMATCH,
            ):
                boundary_refusals.append(
                    (cls, f"Boundary {key.boundary!r} not permitted for class {cls.class_id}")
                )
            elif res in (
                ApplicabilityMatchResult.METHOD_MISMATCH,
                ApplicabilityMatchResult.CONTEXT_MISMATCH,
                ApplicabilityMatchResult.WORK_CLASS_MISMATCH,
            ):
                context_mismatches.append(
                    (cls, f"Context mismatch ({res.value}) for class {cls.class_id}")
                )

        return matches, boundary_refusals, context_mismatches

    def to_dict(self) -> dict[str, Any]:
        """Return full dictionary representation of the registry for audit and storage."""
        classes_data = [cls.to_dict() for cls in self.list_classes()]
        return {
            "schema_version": EFFORT_REGISTRY_VERSION,
            "total_classes": len(classes_data),
            "classes": classes_data,
            "registry_digest": "sha256:" + _digest_data(classes_data),
        }


class ReviewedWorkUnitClassEffortProvider:
    """Effort Rating Provider resolving Effort (C) via reviewed work-unit classes.

    Implements EffortRatingProvider protocol:
    - Resolves exact integer rubrics T1, T2 in {1, 2, 3}.
    - Emits C = T1 + T2 - 2 in {0..4}.
    - Enforces strict refusal integrity on boundary violations and out-of-scope probes.
    - Preserves fail-closed unrated dispositions on unresolved overlaps.
    - Detects and flags conflicting registry matches.
    - Zero unit weights (W=1.0) and zero maut_v1 fallback.
    """

    def __init__(
        self,
        registry: WorkUnitClassRegistry | None = None,
        *,
        name: str = "reviewed_work_unit_class_effort_provider",
        version: str = EFFORT_REGISTRY_VERSION,
    ) -> None:
        self._name = name
        self._version = version
        self._registry = registry if registry is not None else WorkUnitClassRegistry()

    @property
    def name(self) -> str:
        return self._name

    @property
    def provider_version(self) -> str:
        return self._version

    @property
    def registry(self) -> WorkUnitClassRegistry:
        return self._registry

    def resolve_effort(
        self,
        key: EffortLookupKey,
        work_unit_record: Mapping[str, Any],
        scope: Mapping[str, Any],
    ) -> ResolutionResult:
        """Resolve effort cost and rubric scores for a work unit."""
        # 1. Fail closed on unresolved overlap
        overlap_state = str(work_unit_record.get("overlap_state") or "independent").strip()
        if overlap_state == "unresolved_overlap":
            return ResolutionResult(
                disposition=ResolverDisposition.UNRATED,
                reason_code=ReasonCode.EXPLICIT_UNRATED_DISPOSITION,
                reason_detail=(
                    f"Work unit {key.work_unit_id!r} has unresolved overlap; "
                    "cannot assign independent effort cost"
                ),
                provider_name=self.name,
                provider_version=self.provider_version,
            )

        # 2. Check explicit class ID if specified
        explicit_class_id = work_unit_record.get("work_unit_class_id") or work_unit_record.get(
            "class_id"
        )
        if explicit_class_id:
            cls = self._registry.get(str(explicit_class_id))
            if cls is None:
                return ResolutionResult(
                    disposition=ResolverDisposition.UNSUPPORTED,
                    reason_code=ReasonCode.UNSUPPORTED_TECHNIQUE,
                    reason_detail=f"Work unit class {explicit_class_id!r} not found in registry",
                    provider_name=self.name,
                    provider_version=self.provider_version,
                )

            res = cls.applicability.evaluate(key, work_unit_record, scope)
            if res in (
                ApplicabilityMatchResult.BOUNDARY_MISMATCH,
                ApplicabilityMatchResult.SCOPE_MISMATCH,
            ):
                return ResolutionResult(
                    disposition=ResolverDisposition.REFUSED,
                    reason_code=ReasonCode.OUT_OF_SCOPE,
                    reason_detail=(f"Boundary {key.boundary!r} rejected by class {cls.class_id!r}"),
                    provider_name=self.name,
                    provider_version=self.provider_version,
                )
            if res != ApplicabilityMatchResult.MATCH:
                return ResolutionResult(
                    disposition=ResolverDisposition.UNRATED,
                    reason_code=ReasonCode.MISSING_EVIDENCE,
                    reason_detail=(
                        f"Applicability check failed ({res.value}) for class {cls.class_id!r}"
                    ),
                    provider_name=self.name,
                    provider_version=self.provider_version,
                )

            return self._build_result_from_class(cls)

        # 3. Match across registered classes
        matches, boundary_refusals, context_mismatches = self._registry.match(
            key, work_unit_record, scope
        )

        # Case A: Exactly one class matches
        if len(matches) == 1:
            return self._build_result_from_class(matches[0])

        # Case B: Multiple classes match
        if len(matches) > 1:
            return ResolutionResult(
                disposition=ResolverDisposition.CONFLICTING,
                reason_code=ReasonCode.CONFLICTING_PROVIDER_BASIS,
                reason_detail=f"Multiple effort classes matched: {[c.class_id for c in matches]}",
                provider_name=self.name,
                provider_version=self.provider_version,
            )

        # Case C: Zero classes match
        if boundary_refusals:
            # Technique recognized, but rejected due to boundary/scope violation
            refusal_cls, detail = boundary_refusals[0]
            return ResolutionResult(
                disposition=ResolverDisposition.REFUSED,
                reason_code=ReasonCode.OUT_OF_SCOPE,
                reason_detail=detail,
                provider_name=self.name,
                provider_version=self.provider_version,
            )

        if context_mismatches:
            # Technique recognized and in-scope, but unresolved context/method
            mismatch_cls, detail = context_mismatches[0]
            return ResolutionResult(
                disposition=ResolverDisposition.UNRATED,
                reason_code=ReasonCode.EXPLICIT_UNRATED_DISPOSITION,
                reason_detail=detail,
                provider_name=self.name,
                provider_version=self.provider_version,
            )

        # Technique not recognized anywhere in the reviewed registry
        return ResolutionResult(
            disposition=ResolverDisposition.UNSUPPORTED,
            reason_code=ReasonCode.UNSUPPORTED_TECHNIQUE,
            reason_detail=(f"Technique {key.technique!r} not supported by reviewed effort classes"),
            provider_name=self.name,
            provider_version=self.provider_version,
        )

    def _build_result_from_class(self, cls: WorkUnitClass) -> ResolutionResult:
        """Construct structured ResolutionResult from a matched WorkUnitClass."""
        if cls.disposition == ResolverDisposition.RATED and cls.review_status != "accepted":
            return ResolutionResult(
                disposition=ResolverDisposition.UNRATED,
                reason_code=ReasonCode.EXPLICIT_UNRATED_DISPOSITION,
                reason_detail=f"Class {cls.class_id} is proposed; pending B review",
                provider_name=self.name,
                provider_version=self.provider_version,
                review_reference=cls.review_reference,
                provenance_digest=cls.provenance_digest or ("sha256:" + cls.digest()),
            )
        if cls.disposition == ResolverDisposition.RATED:
            return ResolutionResult(
                disposition=ResolverDisposition.RATED,
                value=cls.computed_cost,
                reason_code=ReasonCode.REVIEWED_PACKET_MATCH,
                reason_detail=f"Resolved via reviewed class {cls.class_id}",
                provider_name=self.name,
                provider_version=self.provider_version,
                basis_category=cls.basis_category,
                review_reference=cls.review_reference,
                provenance_digest=cls.provenance_digest or ("sha256:" + cls.digest()),
                rubric_scores=cls.rubric_scores,
                numeric_basis_class=cls.numeric_basis_class,
                review_status=cls.review_status,
            )

        return ResolutionResult(
            disposition=cls.disposition,
            reason_code=cls.unrated_reason_code or ReasonCode.MISSING_EVIDENCE,
            reason_detail=cls.unrated_reason_detail or f"Class {cls.class_id} is unrated",
            provider_name=self.name,
            provider_version=self.provider_version,
            basis_category=cls.basis_category,
            review_reference=cls.review_reference,
            provenance_digest=cls.provenance_digest or ("sha256:" + cls.digest()),
        )


# ---------------------------------------------------------------------------
# Default Work-Unit Class Inventory
# ---------------------------------------------------------------------------


def _is_direct_admin(key, record, scope):
    return key.work_class == WorkUnitClassification.ACTIVE_WORK and (
        key.method == "direct"
        or (
            scope.get("scenario_id") == "synthetic-a2"
            and key.method == "default"
            and key.source_id == key.actor_id
        )
    )


def _is_inherited_admin(key, record, scope):
    return key.work_class == WorkUnitClassification.ACTIVE_WORK and (
        key.method == "inherited"
        or (
            scope.get("scenario_id") == "synthetic-a2"
            and key.method == "default"
            and key.source_id is not None
            and key.source_id != key.actor_id
        )
    )


def _is_winrm_admin(key, record, scope):
    return key.work_class == WorkUnitClassification.ACTIVE_WORK and (
        key.technique != "obtain_admin_execution_on_host" or key.method == "winrm"
    )


def _is_shared_auth_prep(key, record, scope):
    return key.work_class == WorkUnitClassification.SHARED_PREPARATION or (
        key.technique in ("auth_context", "shared_preparation", "w-auth-context")
    )


def _is_generic_admin_channel(key, record, scope):
    return (
        key.work_class == WorkUnitClassification.ACTIVE_WORK
        and key.method == "default"
        and scope.get("scenario_id") != "synthetic-a2"
    )


def build_default_work_unit_classes() -> list[WorkUnitClass]:
    """Construct the complete inventory of reviewed work-unit classes."""
    classes: list[WorkUnitClass] = [
        # 1. Active Directory Password Reset over SAMR/LDAP
        WorkUnitClass(
            class_id="class_ad_password_reset_samr",
            name="Active Directory Password Reset over SAMR/LDAP",
            description=(
                "Resetting target user account password over authenticated SAMR/RPC or "
                "LDAP connection using standard tools and APIs."
            ),
            t1=1,
            t2=2,
            formula="base",
            applicability=ClassApplicability(
                techniques=(
                    "reset_password",
                    "genericall_reset_password",
                    "reset_target_password",
                    "scenario_reset_password",
                ),
                methods=("*",),
                aliases=("WU_RESET_LIDIA", "WU_RESET_JOSEFA", "WU_RESET_OLLIE"),
            ),
            notes="Week 3 reviewed baseline (SEAMLESS WU_RESET_*, T1=1, T2=2, C=1).",
        ),
        # 2. Kerberos Ticket Acquisition
        WorkUnitClass(
            class_id="class_kerberos_ticket_acquisition",
            name="Kerberos Ticket Acquisition",
            description=(
                "Requesting standard Kerberos TGT or service ticket using acquired "
                "credentials via automated protocol exchange."
            ),
            t1=1,
            t2=1,
            formula="base",
            applicability=ClassApplicability(
                techniques=(
                    "acquire_ticket",
                    "acquire_reset_identity",
                ),
                methods=("*",),
                aliases=("WU_ACTIVATE_LIDIA", "WU_ACTIVATE_JOSEFA", "WU_ACTIVATE_OLLIE"),
            ),
            notes="Week 3 reviewed baseline (SEAMLESS WU_ACTIVATE_*, T1=1, T2=1, C=0).",
        ),
        # 3. WinRM Remote Host Administration
        WorkUnitClass(
            class_id="class_winrm_host_admin",
            name="WinRM Remote Host Administration",
            description=(
                "Establishing remote PowerShell / WinRM management session, verifying "
                "administrative credentials and executing host commands."
            ),
            t1=1,
            t2=2,
            formula="base",
            applicability=ClassApplicability(
                techniques=(
                    "remote_exec_winrm",
                    "open_winrm_remote_session",
                    "scenario_winrm_admin",
                    "obtain_admin_execution_on_host",
                ),
                methods=("*",),
                aliases=("WU_WINRM_DC_LIDIA", "WU_WINRM_DC_OLLIE"),
                predicate=_is_winrm_admin,
            ),
            notes="Week 3 reviewed baseline and Frozen #243 AS-REP (T1=1, T2=2, C=1).",
        ),
        # 4. Shared Persistent Authentication Context Preparation
        WorkUnitClass(
            class_id="class_shared_auth_preparation",
            name="Shared Persistent Authentication Preparation",
            description=(
                "Establishing and validating shared authenticated channel and staging "
                "reusable credentials on a target machine."
            ),
            t1=1,
            t2=2,
            formula="base",
            applicability=ClassApplicability(
                techniques=(
                    "auth_context",
                    "shared_preparation",
                    "w-auth-context",
                    "obtain_admin_execution_on_host",
                ),
                methods=("*",),
                work_classes=(
                    WorkUnitClassification.ACTIVE_WORK,
                    WorkUnitClassification.SHARED_PREPARATION,
                ),
                aliases=("w-auth-context", "WU_AUTH_CONTEXT"),
                predicate=_is_shared_auth_prep,
            ),
            notes="Week 4 Fixture A2 shared preparation baseline (T1=1, T2=2, C=1).",
        ),
        # 5. Direct Host Admin Execution (High Friction)
        WorkUnitClass(
            class_id="class_direct_host_admin_execution",
            name="Direct Host Admin Execution",
            description=(
                "Direct privilege escalation or admin execution facing active host "
                "defenses and monitoring without inherited delegation."
            ),
            t1=3,
            t2=3,
            formula="base",
            applicability=ClassApplicability(
                techniques=("obtain_admin_execution_on_host",),
                methods=("direct", "*"),
                aliases=("w-direct-admin", "WU_DIRECT_ADMIN"),
                predicate=_is_direct_admin,
            ),
            notes="Week 4 Fixture A2 direct branch baseline (T1=3, T2=3, C=4).",
        ),
        # 6. Inherited Host Admin Execution (Low Friction via Membership)
        WorkUnitClass(
            class_id="class_inherited_host_admin_execution",
            name="Inherited Host Admin Execution",
            description=(
                "Administrative execution utilizing existing group delegation or "
                "inherited authority under reduced host friction."
            ),
            t1=1,
            t2=2,
            formula="base",
            applicability=ClassApplicability(
                techniques=("obtain_admin_execution_on_host",),
                methods=("inherited", "*"),
                aliases=("w-inherited-admin", "WU_INHERITED_ADMIN"),
                predicate=_is_inherited_admin,
            ),
            notes="Week 4 Fixture A2 inherited branch baseline (T1=1, T2=2, C=1).",
        ),
        # 7. AS-REP Roasting Request
        WorkUnitClass(
            class_id="class_asrep_request",
            name="AS-REP Roasting Request",
            description=(
                "Issuing AS-REQ for accounts with DoNotRequirePreAuth set to obtain "
                "encrypted AS-REP response."
            ),
            t1=1,
            t2=1,
            formula="base",
            applicability=ClassApplicability(
                techniques=("asrep_request",),
                methods=("*",),
            ),
            notes="Frozen #243 AS-REP request work unit (T1=1, T2=1, C=0).",
        ),
        # 8. AS-REP Offline Secret Recovery
        WorkUnitClass(
            class_id="class_asrep_offline_crack",
            name="AS-REP Offline Secret Recovery",
            description=(
                "Offline password cracking of recovered AS-REP encrypted timestamp "
                "using dictionary and rule attacks."
            ),
            t1=2,
            t2=2,
            formula="base",
            applicability=ClassApplicability(
                techniques=("recover_asrep_secret",),
                methods=("*",),
            ),
            notes="Frozen #243 AS-REP offline cracking work unit (T1=2, T2=2, C=2).",
        ),
        # 9. Kerberos Recovered Identity Activation
        WorkUnitClass(
            class_id="class_kerberos_identity_activation",
            name="Kerberos Recovered Identity Activation",
            description=(
                "Activating and verifying recovered password or ticket secret into "
                "an authenticated execution session."
            ),
            t1=1,
            t2=1,
            formula="base",
            applicability=ClassApplicability(
                techniques=("activate_recovered_identity",),
                methods=("*",),
            ),
            notes="Frozen #243 AS-REP and Kerberoasting activation (T1=1, T2=1, C=0).",
        ),
        # 10. Kerberoast Service Ticket Request
        WorkUnitClass(
            class_id="class_kerberoast_request",
            name="Kerberoast Service Ticket Request",
            description=(
                "Requesting Kerberos TGS service ticket for accounts configured with "
                "ServicePrincipalNames."
            ),
            t1=1,
            t2=1,
            formula="base",
            applicability=ClassApplicability(
                techniques=("kerberoast_request",),
                methods=("*",),
            ),
            notes="Kerberoasting TGS request baseline (T1=1, T2=1, C=0).",
        ),
        # 11. Kerberoast Offline Ticket Secret Recovery
        WorkUnitClass(
            class_id="class_kerberoast_offline_crack",
            name="Kerberoast Offline Ticket Secret Recovery",
            description=(
                "Offline password hash cracking of Kerberos TGS ticket secret using "
                "specialized compute tooling."
            ),
            t1=2,
            t2=2,
            formula="base",
            applicability=ClassApplicability(
                techniques=("recover_ticket_secret",),
                methods=("*",),
            ),
            notes="Kerberoasting offline cracking (#246 Worked Example 2, T1=2, T2=2, C=2).",
        ),
        # 12. RBCD Intermediate Secret Acquisition
        WorkUnitClass(
            class_id="class_rbcd_acquire_secret",
            name="RBCD Intermediate Secret Acquisition",
            description=(
                "Acquiring intermediate computer account secret or machine account "
                "quota utilization for RBCD delegation."
            ),
            t1=1,
            t2=2,
            formula="base",
            applicability=ClassApplicability(
                techniques=("rbcd_acquire_secret",),
                methods=("*",),
                aliases=("work_rbcd_acquire_secret",),
            ),
            notes="RBCD Recipe step 1 (T1=1, T2=2, C=1).",
        ),
        # 13. RBCD Service Preparation
        WorkUnitClass(
            class_id="class_rbcd_prepare_service",
            name="RBCD Service Preparation",
            description=(
                "Verifying service principal name and service registration readiness "
                "for constrained delegation."
            ),
            t1=1,
            t2=1,
            formula="base",
            applicability=ClassApplicability(
                techniques=("rbcd_prepare_service",),
                methods=("*",),
                aliases=("work_rbcd_prepare_service",),
            ),
            notes="RBCD Recipe step 2 (T1=1, T2=1, C=0).",
        ),
        # 14. RBCD Security Descriptor Configuration
        WorkUnitClass(
            class_id="class_rbcd_configure_descriptor",
            name="RBCD Security Descriptor Configuration",
            description=(
                "Writing msDS-AllowedToActOnBehalfOfOtherIdentity security descriptor "
                "attribute on target computer via LDAP."
            ),
            t1=2,
            t2=2,
            formula="base",
            applicability=ClassApplicability(
                techniques=("rbcd_configure_descriptor",),
                methods=("*",),
                aliases=("work_rbcd_configure_descriptor",),
            ),
            notes="RBCD Recipe step 3 (T1=2, T2=2, C=2).",
        ),
        # 15. RBCD Constrained Service Delegation
        WorkUnitClass(
            class_id="class_rbcd_delegate_service",
            name="RBCD Constrained Service Delegation",
            description=(
                "Performing S4U2self and S4U2proxy protocol transition exchange to "
                "obtain impersonated service ticket."
            ),
            t1=2,
            t2=2,
            formula="base",
            applicability=ClassApplicability(
                techniques=("rbcd_delegate_service",),
                methods=("*",),
                aliases=("work_rbcd_delegate_service",),
            ),
            notes="RBCD Recipe step 4 (T1=2, T2=2, C=2).",
        ),
        # 16. RBCD Delegated Service Administration
        WorkUnitClass(
            class_id="class_rbcd_service_admin",
            name="RBCD Delegated Service Administration",
            description=(
                "Executing administrative commands on target host using delegated "
                "Kerberos service ticket."
            ),
            t1=1,
            t2=2,
            formula="base",
            applicability=ClassApplicability(
                techniques=("rbcd_service_admin",),
                methods=("*",),
                aliases=("work_rbcd_service_admin",),
            ),
            notes="RBCD Recipe step 5 (T1=1, T2=2, C=1).",
        ),
        # 17. Active Directory Group Membership Addition
        WorkUnitClass(
            class_id="class_ad_group_membership_add",
            name="Active Directory Group Membership Addition",
            description=(
                "Adding an Active Directory principal to a security group using "
                "GenericAll or WriteProperty permissions."
            ),
            t1=1,
            t2=2,
            formula="base",
            applicability=ClassApplicability(
                techniques=("genericall_add_member",),
                methods=("*",),
            ),
            notes="Semantics catalog group addition (T1=1, T2=2, C=1).",
        ),
        # 18. Active Directory DACL Mutation
        WorkUnitClass(
            class_id="class_ad_dacl_mutation",
            name="Active Directory DACL Mutation",
            description=(
                "Modifying discretionary access control lists on directory objects to "
                "grant administrative or replication rights."
            ),
            t1=2,
            t2=2,
            formula="base",
            applicability=ClassApplicability(
                techniques=("genericall_grant_write_dacl", "grant_new_object_right"),
                methods=("*",),
            ),
            notes="Semantics catalog DACL mutation (T1=2, T2=2, C=2).",
        ),
        # 19. Remote Interactive Session (RDP)
        WorkUnitClass(
            class_id="class_rdp_remote_interactive",
            name="Remote Interactive Desktop Session",
            description=("Establishing authenticated remote desktop interactive session over RDP."),
            t1=1,
            t2=2,
            formula="base",
            applicability=ClassApplicability(
                techniques=("open_remote_interactive_session",),
                methods=("*",),
            ),
            notes="Semantics catalog RDP interactive session (T1=1, T2=2, C=1).",
        ),
        # 20. LSASS Process Credential Material Dump
        WorkUnitClass(
            class_id="class_lsass_credential_dump",
            name="LSASS Process Credential Material Dump",
            description=(
                "Extracting plaintext credentials or ticket keys from LSASS process "
                "memory on compromised host."
            ),
            t1=2,
            t2=2,
            formula="base",
            applicability=ClassApplicability(
                techniques=("recover_session_credential_material",),
                methods=("*",),
            ),
            notes="Semantics catalog credential dumping (T1=2, T2=2, C=2).",
        ),
        # 21. Explicitly Unrated: Unconstrained Delegation Abuse (Missing Evidence)
        WorkUnitClass(
            class_id="class_unconstrained_delegation_abuse",
            name="Unconstrained Delegation Abuse",
            description=(
                "Abusing unconstrained Kerberos delegation on compromised host; "
                "lacks empirical timing and friction measurements."
            ),
            t1=0,
            t2=0,
            formula="base",
            disposition=ResolverDisposition.UNRATED,
            unrated_reason_code=ReasonCode.MISSING_EVIDENCE,
            unrated_reason_detail=(
                "Unconstrained delegation abuse has no empirical timing or friction basis"
            ),
            applicability=ClassApplicability(
                techniques=("unconstrained_delegation_abuse",),
                methods=("*",),
            ),
            notes="Explicit unrated disposition due to missing empirical calibration.",
        ),
        # 22. Explicitly Refused: Cross-Forest Trust Hop (Out of Scope Boundary)
        WorkUnitClass(
            class_id="class_cross_forest_trust_hop",
            name="Cross-Forest Trust Hop",
            description=("Attempting cross-forest trust traversal outside intra_forest boundary."),
            t1=0,
            t2=0,
            formula="base",
            disposition=ResolverDisposition.REFUSED,
            unrated_reason_code=ReasonCode.OUT_OF_SCOPE,
            unrated_reason_detail=("Cross-forest trust hop violates intra_forest work boundary"),
            applicability=ClassApplicability(
                techniques=("cross_forest_trust_hop",),
                methods=("*",),
                boundaries=("cross_forest",),
            ),
            notes="Explicit refusal due to intra_forest boundary constraint.",
        ),
    ]
    classes.append(
        WorkUnitClass(
            class_id="class_host_admin_channel",
            name="Host administration via declared admin channel",
            description="Accepted semantic admin_channel abstraction; transport unspecified.",
            t1=1,
            t2=2,
            applicability=ClassApplicability(
                techniques=("obtain_admin_execution_on_host",),
                methods=("default",),
                work_classes=(WorkUnitClassification.ACTIVE_WORK,),
                predicate=_is_generic_admin_channel,
            ),
            notes="Proposed generic channel effort; transport and defense friction unspecified.",
        )
    )
    return classes


def get_default_work_unit_registry() -> WorkUnitClassRegistry:
    """Return the proposed catalog explicitly, without registering it in a provider."""
    return WorkUnitClassRegistry(build_default_work_unit_classes())
