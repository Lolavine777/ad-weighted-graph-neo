"""Rating Resolver Contract and Reference Materialization (Specification v1.0.0).

Connects generated semantic attack paths and transitions to the canonical
C/P/I PathRankingEngine evaluation boundary (Issue #246, parent #245).

Architecture Invariants:
1. Deterministic versioned identities:
   - Bound Action Identity (action_id)
   - Canonical Work Unit Identity (work_unit_id / work ledger)
   - Rating Lookup Keys for Effort (C), Likelihood (P), Impact (I)
2. Semantic work classification:
   - Active work units (friction, cost, conditioning events)
   - Passive closures (state/group propagation, zero friction, empty work units)
   - Shared persistent preparation (reused across steps/paths, deduplicated)
3. Full-history ordered active-work prefix preservation for conditional likelihood P.
4. Resolver dispositions and structured reason codes:
   - rated, unrated, unsupported, refused, conflicting
5. Fail-closed provider provenance and basis governance:
   - Forbids unit / maut_v1 fallback
   - Enforces refusal integrity (refusal cannot be bypassed by fallback)
6. Machine-readable rating coverage schema (per-candidate C, P, I + aggregate gaps).
7. Compatibility with explicit reviewed ranking packets (Week 3, Week 4) and zero-action goal.
8. Reference materialization producing wire payloads accepted by canonical validator.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from copy import deepcopy
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from src.engine.ranking.adapter_145 import (
    convert_path_result_to_candidate_envelope,
    extract_technique_id,
)
from src.engine.ranking.facts import resolve_facts_ledger
from src.engine.ranking.models import (
    IMPACT_ORDINAL,
    REQUIRED_SCOPE_BINDING_FIELDS,
    RankingValidationError,
    format_rational,
    is_canonical_edge_id,
    is_canonical_node_id,
    parse_rational,
)
from src.engine.ranking.validation import validate_work_units_ledger

RESOLVER_CONTRACT_VERSION = "1.0.0"
DEFAULT_LEDGER_VERSION = "1.0.0"


class ResolverDisposition(StrEnum):
    """Disposition of rating resolution for a work unit, prefix, or target consequence."""

    RATED = "rated"
    UNRATED = "unrated"
    UNSUPPORTED = "unsupported"
    REFUSED = "refused"
    CONFLICTING = "conflicting"


class ReasonCode(StrEnum):
    """Machine-readable structured reason codes for resolver decisions and gaps."""

    MISSING_EVIDENCE = "missing_evidence"
    OUT_OF_SCOPE = "out_of_scope"
    UNSUPPORTED_TECHNIQUE = "unsupported_technique"
    PREREQUISITE_GATE_REFUSAL = "prerequisite_gate_refusal"
    HOLDOUT_ISOLATION_REFUSAL = "holdout_isolation_refusal"
    CONFLICTING_PROVIDER_BASIS = "conflicting_provider_basis"
    MALFORMED_INPUT = "malformed_input"
    EXPLICIT_UNRATED_DISPOSITION = "explicit_unrated_disposition"
    ZERO_ACTION_GOAL = "zero_action_goal"
    PASSIVE_CLOSURE = "passive_closure"
    SHARED_PREPARATION_REUSED = "shared_preparation_reused"
    REVIEWED_PACKET_MATCH = "reviewed_packet_match"
    REVIEWED_EQUIVALENCE_MATCH = "reviewed_equivalence_match"


class WorkUnitClassification(StrEnum):
    """Classification of an attack step's work semantics for cost and likelihood."""

    ACTIVE_WORK = "active_work"
    PASSIVE_CLOSURE = "passive_closure"
    SHARED_PREPARATION = "shared_preparation"


class BasisClassification(StrEnum):
    """Governance classification of the evidence basis behind a rating."""

    EMPIRICAL_EVIDENCE = "empirical_evidence"
    SCENARIO_ASSUMPTION = "scenario_assumption"
    HUMAN_REVIEWED_AI_ASSISTED = "human_reviewed_ai_assisted_ratings"
    DECLARED_INDEPENDENT = "declared_independent_ratings"
    SYNTHETIC_TEST_ONLY = "synthetic_test_only"


KNOWN_PASSIVE_TECHNIQUES: frozenset[str] = frozenset(
    {
        "propagate_group_entitlement",
        "member_of_propagation",
        "nested_group_closure",
    }
)


def _digest_object(data: Any) -> str:
    """Compute deterministic SHA-256 hex digest for canonical JSON."""
    raw = json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Deterministic Identity and Lookup Key Generators
# ---------------------------------------------------------------------------


def generate_bound_action_id(
    technique_id: str,
    actor_id: str,
    target_id: str,
    context: Mapping[str, Any] | None = None,
    *,
    source_id: str | None = None,
    version: str = RESOLVER_CONTRACT_VERSION,
) -> str:
    """Generate deterministic versioned identity for a bound action.

    Action identity captures technique, endpoints, prerequisites, effects,
    execution method, and relevant auth/resource contexts so identical action
    signatures in the same context reuse the same action ID without collisions.
    """
    if not isinstance(technique_id, str) or not technique_id.strip():
        raise RankingValidationError("technique_id must be a non-empty string")
    if not is_canonical_node_id(actor_id):
        raise RankingValidationError(f"actor_id must be a canonical node ID, got {actor_id!r}")
    if not is_canonical_node_id(target_id):
        raise RankingValidationError(f"target_id must be a canonical node ID, got {target_id!r}")

    ctx = dict(context or {})
    src_id = str(source_id or ctx.get("source_id") or ctx.get("source") or actor_id).strip()
    if not is_canonical_node_id(src_id):
        raise RankingValidationError(f"source_id must be a canonical node ID, got {src_id!r}")

    requires = sorted(str(r) for r in ctx.get("requires", []))
    adds = sorted(str(a) for a in ctx.get("adds", []))
    is_passive = bool(ctx.get("is_passive_closure", False))
    method = str(ctx.get("method") or "default").strip()
    auth_ctx = str(ctx.get("auth_context") or "default").strip()
    res_ctx = str(ctx.get("resource_context") or "default").strip()
    edge_id = ctx.get("edge_id")

    payload = {
        "version": version,
        "technique_id": technique_id,
        "actor_id": actor_id,
        "source_id": src_id,
        "target_id": target_id,
        "edge_id": edge_id if edge_id else None,
        "is_passive": is_passive,
        "requires": requires,
        "adds": adds,
        "method": method,
        "auth_context": auth_ctx,
        "resource_context": res_ctx,
        "policy_id": ctx.get("policy_id"),
    }
    digest = _digest_object(payload)[:16]
    return f"act:{version}:{technique_id}:{actor_id}:{target_id}:{digest}"


def generate_work_unit_id(
    technique: str,
    actor_id: str,
    target_id: str,
    context: str = "default",
    boundary: str = "intra_forest",
    *,
    ledger_version: str = DEFAULT_LEDGER_VERSION,
) -> str:
    """Generate canonical work unit identity following ADR-0013 §5.

    Format: technique:actor:target:context:boundary:ledger_version
    Guarantees that work units representing the same real task match across steps.
    """
    clean_technique = str(technique).strip()
    if not clean_technique:
        raise RankingValidationError("technique must be a non-empty string")
    if not is_canonical_node_id(actor_id):
        raise RankingValidationError(f"actor_id must be a canonical node ID, got {actor_id!r}")
    if not is_canonical_node_id(target_id):
        raise RankingValidationError(f"target_id must be a canonical node ID, got {target_id!r}")
    clean_context = str(context).strip() or "default"
    clean_boundary = str(boundary).strip() or "intra_forest"
    clean_version = str(ledger_version).strip() or DEFAULT_LEDGER_VERSION
    return (
        f"{clean_technique}:{actor_id}:{target_id}:{clean_context}:{clean_boundary}:{clean_version}"
    )


@dataclass(frozen=True)
class EffortLookupKey:
    """Rating lookup key for Effort (C) preserving applicability context."""

    version: str
    work_unit_id: str
    technique: str
    actor_id: str
    target_id: str
    work_class: WorkUnitClassification
    method: str
    boundary: str
    scope: str
    source_id: str | None = None
    auth_context: str | None = None
    resource_context: str | None = None
    policy_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "dimension": "C",
            "version": self.version,
            "work_unit_id": self.work_unit_id,
            "technique": self.technique,
            "actor_id": self.actor_id,
            "source_id": self.source_id or self.actor_id,
            "target_id": self.target_id,
            "work_class": str(self.work_class),
            "method": self.method,
            "boundary": self.boundary,
            "scope": self.scope,
            "auth_context": self.auth_context,
            "resource_context": self.resource_context,
            "policy_id": self.policy_id,
        }

    def digest(self) -> str:
        return _digest_object(self.to_dict())


@dataclass(frozen=True)
class LikelihoodLookupKey:
    """Rating lookup key for Likelihood (P) preserving full ordered active-work prefix."""

    version: str
    scenario_id: str
    scenario_version: str
    snapshot_id: str
    foothold_node_id: str
    ordered_work_prefix: tuple[str, ...]
    outcome_work_unit_id: str
    outcome_technique: str
    actor_id: str
    target_id: str
    method: str
    budget: int | None
    horizon: str
    boundary: str
    scope: str
    source_id: str | None = None
    auth_context: str | None = None
    resource_context: str | None = None
    policy_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "dimension": "P",
            "version": self.version,
            "scenario_id": self.scenario_id,
            "scenario_version": self.scenario_version,
            "snapshot_id": self.snapshot_id,
            "foothold_node_id": self.foothold_node_id,
            "ordered_work_prefix": list(self.ordered_work_prefix),
            "outcome_work_unit_id": self.outcome_work_unit_id,
            "outcome_technique": self.outcome_technique,
            "actor_id": self.actor_id,
            "source_id": self.source_id or self.actor_id,
            "target_id": self.target_id,
            "method": self.method,
            "budget": self.budget,
            "horizon": self.horizon,
            "boundary": self.boundary,
            "scope": self.scope,
            "auth_context": self.auth_context,
            "resource_context": self.resource_context,
            "policy_id": self.policy_id,
        }

    def digest(self) -> str:
        return _digest_object(self.to_dict())


@dataclass(frozen=True)
class ImpactLookupKey:
    """Rating lookup key for Impact (I) bound to target asset and consequence scope."""

    version: str
    target_asset_id: str
    success_event: str
    consequence_scope: str
    boundary: str
    scenario_id: str
    policy_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "dimension": "I",
            "version": self.version,
            "target_asset_id": self.target_asset_id,
            "success_event": self.success_event,
            "consequence_scope": self.consequence_scope,
            "boundary": self.boundary,
            "scenario_id": self.scenario_id,
            "policy_id": self.policy_id,
        }

    def digest(self) -> str:
        return _digest_object(self.to_dict())


def generate_rating_lookup_key_c(
    work_unit_id: str,
    technique: str,
    actor_id: str,
    target_id: str,
    *,
    source_id: str | None = None,
    work_class: WorkUnitClassification = WorkUnitClassification.ACTIVE_WORK,
    method: str = "default",
    boundary: str = "intra_forest",
    scope: str = "default",
    auth_context: str | None = None,
    resource_context: str | None = None,
    policy_id: str | None = None,
    version: str = RESOLVER_CONTRACT_VERSION,
) -> EffortLookupKey:
    """Build strongly typed lookup key for Effort (C)."""
    return EffortLookupKey(
        version=version,
        work_unit_id=work_unit_id,
        technique=technique,
        actor_id=actor_id,
        source_id=source_id,
        target_id=target_id,
        work_class=work_class,
        method=method,
        boundary=boundary,
        scope=scope,
        auth_context=auth_context,
        resource_context=resource_context,
        policy_id=policy_id,
    )


def generate_rating_lookup_key_p(
    scenario_id: str,
    scenario_version: str,
    snapshot_id: str,
    foothold_node_id: str,
    ordered_work_prefix: Sequence[str],
    outcome_work_unit_id: str,
    outcome_technique: str,
    actor_id: str,
    target_id: str,
    *,
    source_id: str | None = None,
    method: str = "default",
    budget: int | None = None,
    horizon: str = "24h",
    boundary: str = "intra_forest",
    scope: str = "default",
    auth_context: str | None = None,
    resource_context: str | None = None,
    policy_id: str | None = None,
    version: str = RESOLVER_CONTRACT_VERSION,
) -> LikelihoodLookupKey:
    """Build strongly typed lookup key for Likelihood (P) preserving full ordered prefix."""
    return LikelihoodLookupKey(
        version=version,
        scenario_id=scenario_id,
        scenario_version=scenario_version,
        snapshot_id=snapshot_id,
        foothold_node_id=foothold_node_id,
        ordered_work_prefix=tuple(ordered_work_prefix),
        outcome_work_unit_id=outcome_work_unit_id,
        outcome_technique=outcome_technique,
        actor_id=actor_id,
        source_id=source_id,
        target_id=target_id,
        method=method,
        budget=budget,
        horizon=horizon,
        boundary=boundary,
        scope=scope,
        auth_context=auth_context,
        resource_context=resource_context,
        policy_id=policy_id,
    )


def generate_rating_lookup_key_i(
    target_asset_id: str,
    success_event: str,
    *,
    consequence_scope: str = "intra_forest",
    boundary: str = "intra_forest",
    scenario_id: str = "default",
    policy_id: str | None = None,
    version: str = RESOLVER_CONTRACT_VERSION,
) -> ImpactLookupKey:
    """Build strongly typed lookup key for Impact (I)."""
    return ImpactLookupKey(
        version=version,
        target_asset_id=target_asset_id,
        success_event=success_event,
        consequence_scope=consequence_scope,
        boundary=boundary,
        scenario_id=scenario_id,
        policy_id=policy_id,
    )


# ---------------------------------------------------------------------------
# Resolution Results & Provider Protocols
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ResolutionResult:
    """Structured result returned by a rating provider during resolution."""

    disposition: ResolverDisposition
    value: Any = None
    reason_code: str = ReasonCode.MISSING_EVIDENCE
    reason_detail: str = ""
    provider_name: str = "unknown"
    provider_version: str = "1.0.0"
    basis_category: str | None = None
    provenance_digest: str | None = None
    review_reference: str | None = None
    rubric_scores: dict[str, Any] | None = None
    numeric_basis_class: str | None = None
    review_status: str | None = None

    def __post_init__(self) -> None:
        if self.numeric_basis_class is None:
            return
        allowed = {
            "estimated_expert_scenario": {
                BasisClassification.SCENARIO_ASSUMPTION,
                BasisClassification.HUMAN_REVIEWED_AI_ASSISTED,
            },
            "synthetic_test_only": {BasisClassification.SYNTHETIC_TEST_ONLY},
        }
        if not isinstance(self.numeric_basis_class, str) or self.basis_category not in allowed.get(
            self.numeric_basis_class, set()
        ):
            raise RankingValidationError("numeric_basis_class is incompatible with provider basis")


@runtime_checkable
class EffortRatingProvider(Protocol):
    """Protocol for providers resolving Effort (C) on work units."""

    @property
    def name(self) -> str: ...

    @property
    def provider_version(self) -> str: ...

    def resolve_effort(
        self,
        key: EffortLookupKey,
        work_unit_record: Mapping[str, Any],
        scope: Mapping[str, Any],
    ) -> ResolutionResult: ...


@runtime_checkable
class LikelihoodRatingProvider(Protocol):
    """Protocol for providers resolving Likelihood (P) on ordered prefixes."""

    @property
    def name(self) -> str: ...

    @property
    def provider_version(self) -> str: ...

    def resolve_likelihood(
        self,
        key: LikelihoodLookupKey,
        prefix: tuple[str, ...],
        outcome_unit: str,
        scope: Mapping[str, Any],
    ) -> ResolutionResult: ...


@runtime_checkable
class ImpactRatingProvider(Protocol):
    """Protocol for providers resolving Impact (I) on target assets."""

    @property
    def name(self) -> str: ...

    @property
    def provider_version(self) -> str: ...

    def resolve_impact(
        self,
        key: ImpactLookupKey,
        target_asset_id: str,
        success_event: str,
        scope: Mapping[str, Any],
    ) -> ResolutionResult: ...


def _rating_audit(
    result: ResolutionResult | None, key: Any, scope: Mapping[str, Any]
) -> dict[str, Any]:
    return {
        "provider_name": result.provider_name if result else None,
        "provider_version": result.provider_version if result else None,
        "basis_category": result.basis_category if result else None,
        "provenance_digest": result.provenance_digest if result else None,
        "review_reference": result.review_reference if result else None,
        **(
            {
                "numeric_basis_class": result.numeric_basis_class,
                "review_status": result.review_status,
                "review_disposition": str(result.disposition),
            }
            if result and result.numeric_basis_class is not None
            else {}
        ),
        "lookup_key": key.to_dict(),
        "scope_binding": deepcopy(dict(scope)),
    }


# ---------------------------------------------------------------------------
# Default / Reference Provider Implementations
# ---------------------------------------------------------------------------


class ExplicitPacketRatingProvider:
    """Rating provider consuming explicit reviewed ranking packets or bundles.

    Preserves explicit human-reviewed parameters (e.g. Week 3 release or Week 4 fixtures)
    without modifying, rounding, or substituting values.
    """

    def __init__(
        self, packet: Mapping[str, Any], *, name: str = "explicit_packet_provider"
    ) -> None:
        self._name = name
        self._version = str(packet.get("schema_version") or "1.0.0")
        self._packet = deepcopy(dict(packet))
        # Unwrap nested query payload if present
        self._query_data = self._packet.get("query", self._packet)

    @property
    def name(self) -> str:
        return self._name

    @property
    def provider_version(self) -> str:
        return self._version

    def _projection_provider(self, scope: Mapping[str, Any]):
        projections = self._packet.get("query_projections")
        if projections is None:
            return None
        matches = [
            projection["query"]
            for projection in projections.values()
            if isinstance(projection, Mapping)
            and isinstance(projection.get("query"), Mapping)
            and projection["query"].get("query_metadata", {}).get("query_id")
            == scope.get("query_id")
        ]
        if len(matches) != 1:
            return self._refuse("Reviewed bundle requires exactly one query_id projection")
        return ExplicitPacketRatingProvider(matches[0], name=self.name)

    def _rating_metadata(self, record: Mapping[str, Any]) -> dict[str, Any]:
        metadata = self._query_data.get("query_metadata", {})
        governance = metadata.get("governance", {})
        return {
            "basis_category": record.get("basis_category")
            or governance.get("basis_category")
            or BasisClassification.SYNTHETIC_TEST_ONLY,
            "provenance_digest": record.get("provenance_digest")
            or metadata.get("bundle_digest")
            or "sha256:" + _digest_object(self._query_data),
            "review_reference": record.get("review_reference")
            or record.get("reviewed_disposition", {}).get("decision_reference"),
        }

    def _scope_refusal(self, scope: Mapping[str, Any]) -> ResolutionResult | None:
        """A reviewed packet grants no authority outside its exact declared scope."""
        metadata = self._query_data.get("query_metadata", {})
        fields = (
            *REQUIRED_SCOPE_BINDING_FIELDS,
            "horizon",
            "active_work_budget",
            "evaluation_mode",
            "target_goal",
        )
        mismatches = [field for field in fields if metadata.get(field) != scope.get(field)]
        if (metadata.get("policy_id") or None) != (scope.get("policy_id") or None):
            mismatches.append("policy_id")
        if not mismatches:
            return None
        return self._refuse("Packet scope mismatch: " + ", ".join(mismatches))

    def _refuse(self, detail: str) -> ResolutionResult:
        return ResolutionResult(
            disposition=ResolverDisposition.REFUSED,
            reason_code=ReasonCode.OUT_OF_SCOPE,
            reason_detail=detail,
            provider_name=self.name,
            provider_version=self.provider_version,
        )

    def _record_refusal(
        self, record: Mapping[str, Any], key: Any, scope: Mapping[str, Any]
    ) -> ResolutionResult | None:
        queries = record.get("applicable_queries")
        if queries is not None and scope["query_id"] not in queries:
            return self._refuse("Record is not reviewed for this query_id")
        binding = record.get("scope_binding")
        if binding is not None and any(scope.get(k) != v for k, v in binding.items()):
            return self._refuse("Record scope_binding mismatch")
        context = record.get("rating_context")
        if context is not None:
            if context != key.to_dict():
                return self._refuse("Record rating_context mismatch")
        elif isinstance(key, (EffortLookupKey, LikelihoodLookupKey)):
            # Legacy packets have no contextual rating keys. Reuse is limited to
            # their default method/auth/resource/policy context, never extrapolated.
            if (
                key.method != "default"
                or key.auth_context
                or key.resource_context
                or key.policy_id
                or (key.source_id or key.actor_id) != key.actor_id
            ):
                return self._refuse("Legacy packet has no reviewed applicability context")
        for field in (
            "technique",
            "actor_id",
            "source_id",
            "target_id",
            "method",
            "auth_context",
            "resource_context",
            "policy_id",
        ):
            if field in record and record[field] != getattr(key, field, None):
                return self._refuse(f"Record {field} mismatch")
        return None

    def resolve_effort(
        self,
        key: EffortLookupKey,
        work_unit_record: Mapping[str, Any],
        scope: Mapping[str, Any],
    ) -> ResolutionResult:
        projection = self._projection_provider(scope)
        if isinstance(projection, ResolutionResult):
            return projection
        if projection is not None:
            return projection.resolve_effort(key, work_unit_record, scope)
        refusal = self._scope_refusal(scope)
        if refusal is not None:
            return refusal
        ledger = self._query_data.get("work_units_ledger", {})
        unit_id = key.work_unit_id
        alias = work_unit_record.get("alias")

        matched_rec = ledger.get(unit_id)
        if matched_rec is None and alias:
            # Check by alias in explicit packet
            matches = [
                rec for uid, rec in ledger.items() if rec.get("alias") == alias or uid == alias
            ]
            if len(matches) > 1:
                return self._refuse("Ambiguous explicit work-unit alias")
            matched_rec = matches[0] if matches else None

        if matched_rec is None:
            return ResolutionResult(
                disposition=ResolverDisposition.UNSUPPORTED,
                reason_code=ReasonCode.OUT_OF_SCOPE,
                reason_detail=f"Work unit {unit_id!r} absent from explicit packet ledger",
                provider_name=self.name,
                provider_version=self.provider_version,
            )

        refusal = self._record_refusal(matched_rec, key, scope)
        if refusal is not None:
            return refusal
        if matched_rec.get("rating_context") is None:
            actions = self._query_data.get("bound_actions", [])
            compatible = [
                a
                for a in actions
                if unit_id in a.get("referenced_work_unit_ids", [])
                or (alias and alias in a.get("referenced_work_unit_ids", []))
            ]
            if not any(
                a.get("technique", a.get("technique_name")) == key.technique
                and a.get("actor_id") == key.actor_id
                and a.get("target_id", a.get("target_node_id")) == key.target_id
                and a.get("source_node_id", key.actor_id) == (key.source_id or key.actor_id)
                for a in compatible
            ):
                return self._refuse("No reviewed action applicability for this work unit")
        status = matched_rec.get("rating_status", matched_rec.get("status"))
        if status == "rated":
            computed_cost = matched_rec.get("computed_cost", matched_rec.get("effort_cost"))
            rubric = matched_rec.get("rubric_scores")
            return ResolutionResult(
                disposition=ResolverDisposition.RATED,
                value=computed_cost,
                reason_code=ReasonCode.REVIEWED_PACKET_MATCH,
                reason_detail="Resolved from explicit reviewed packet",
                provider_name=self.name,
                provider_version=self.provider_version,
                **self._rating_metadata(matched_rec),
                rubric_scores=dict(rubric) if rubric else None,
            )

        return ResolutionResult(
            disposition=ResolverDisposition.UNRATED,
            reason_code=ReasonCode.EXPLICIT_UNRATED_DISPOSITION,
            reason_detail="Work unit declared unrated in explicit packet",
            provider_name=self.name,
            provider_version=self.provider_version,
        )

    def resolve_likelihood(
        self,
        key: LikelihoodLookupKey,
        prefix: tuple[str, ...],
        outcome_unit: str,
        scope: Mapping[str, Any],
    ) -> ResolutionResult:
        projection = self._projection_provider(scope)
        if isinstance(projection, ResolutionResult):
            return projection
        if projection is not None:
            return projection.resolve_likelihood(key, prefix, outcome_unit, scope)
        refusal = self._scope_refusal(scope)
        if refusal is not None:
            return refusal
        bounds_table = self._query_data.get("conditional_bounds_table", [])
        matched_entry = None
        if isinstance(bounds_table, dict):
            # Dict form keyed by prefix tuple or JSON string
            matched_entry = bounds_table.get(prefix)
            if matched_entry is None:
                matched_entry = bounds_table.get(str(list(prefix)))
        elif isinstance(bounds_table, list):
            matched_entry = None
            for entry in bounds_table:
                if isinstance(entry, dict) and tuple(entry.get("prefix", ())) == prefix:
                    matched_entry = entry
                    break

        if matched_entry is None:
            return ResolutionResult(
                disposition=ResolverDisposition.UNSUPPORTED,
                reason_code=ReasonCode.OUT_OF_SCOPE,
                reason_detail=f"Prefix {prefix!r} absent from explicit packet bounds table",
                provider_name=self.name,
                provider_version=self.provider_version,
            )

        refusal = self._record_refusal(matched_entry, key, scope)
        if refusal is not None:
            return refusal
        if tuple(prefix) != key.ordered_work_prefix or outcome_unit != key.outcome_work_unit_id:
            return self._refuse("Likelihood full-history lookup binding mismatch")
        for uid in prefix:
            record = scope.get("resolved_work_units", {}).get(uid)
            if record is None:
                return self._refuse("Likelihood prefix lacks explicit work applicability")
            ckey = generate_rating_lookup_key_c(
                uid,
                record["technique"],
                record["actor_id"],
                record["target_id"],
                source_id=record["source_id"],
                method=record["method"],
                auth_context=record.get("auth_context"),
                resource_context=record.get("resource_context"),
                policy_id=record.get("policy_id"),
                scope=key.scope,
                boundary=key.boundary,
            )
            c_result = self.resolve_effort(ckey, record, scope)
            if c_result.disposition not in (ResolverDisposition.RATED, ResolverDisposition.UNRATED):
                return self._refuse(f"Likelihood prefix applicability not reviewed: {uid}")
        lo = parse_rational(matched_entry.get("lower"))
        hi = parse_rational(matched_entry.get("upper"))
        return ResolutionResult(
            disposition=ResolverDisposition.RATED,
            value=(lo, hi),
            reason_code=ReasonCode.REVIEWED_PACKET_MATCH,
            reason_detail="Resolved from explicit reviewed packet bounds table",
            provider_name=self.name,
            provider_version=self.provider_version,
            **self._rating_metadata(matched_entry),
        )

    def resolve_impact(
        self,
        key: ImpactLookupKey,
        target_asset_id: str,
        success_event: str,
        scope: Mapping[str, Any],
    ) -> ResolutionResult:
        projection = self._projection_provider(scope)
        if isinstance(projection, ResolutionResult):
            return projection
        if projection is not None:
            return projection.resolve_impact(key, target_asset_id, success_event, scope)
        refusal = self._scope_refusal(scope)
        if refusal is not None:
            return refusal
        impacts = self._query_data.get("target_impact_assessments", {})
        rec = impacts.get(target_asset_id)
        if rec is None:
            return ResolutionResult(
                disposition=ResolverDisposition.UNSUPPORTED,
                reason_code=ReasonCode.OUT_OF_SCOPE,
                reason_detail=(
                    f"Target asset {target_asset_id!r} absent from explicit packet assessments"
                ),
                provider_name=self.name,
                provider_version=self.provider_version,
            )

        refusal = self._record_refusal(rec, key, scope)
        if refusal is not None:
            return refusal
        if rec.get("success_event") != success_event:
            return self._refuse("Impact success_event mismatch")
        if rec.get("consequence_scope", key.boundary) != key.consequence_scope:
            return self._refuse("Impact consequence_scope mismatch")
        status = rec.get("rating_status")
        rating = rec.get("consequence_rating")
        if status == "rated" and rating in IMPACT_ORDINAL:
            return ResolutionResult(
                disposition=ResolverDisposition.RATED,
                value=rating,
                reason_code=ReasonCode.REVIEWED_PACKET_MATCH,
                reason_detail="Resolved from explicit reviewed packet impact assessments",
                provider_name=self.name,
                provider_version=self.provider_version,
                **self._rating_metadata(rec),
            )

        return ResolutionResult(
            disposition=ResolverDisposition.UNRATED,
            reason_code=ReasonCode.EXPLICIT_UNRATED_DISPOSITION,
            reason_detail="Target impact declared unrated in explicit packet",
            provider_name=self.name,
            provider_version=self.provider_version,
        )


class FallbackUnratedProvider:
    """Fail-closed fallback provider returning explicit UNRATED with structured reason codes.

    Guarantees no invented numbers, no unit weights, and no assumption leakage.
    """

    def __init__(
        self,
        reason_code: str = ReasonCode.MISSING_EVIDENCE,
        reason_detail: str = "No rating provider found; missing empirical or reviewed basis",
        *,
        name: str = "fail_closed_unrated_provider",
    ) -> None:
        self._name = name
        self._reason_code = reason_code
        self._reason_detail = reason_detail

    @property
    def name(self) -> str:
        return self._name

    @property
    def provider_version(self) -> str:
        return RESOLVER_CONTRACT_VERSION

    def resolve_effort(
        self,
        key: EffortLookupKey,
        work_unit_record: Mapping[str, Any],
        scope: Mapping[str, Any],
    ) -> ResolutionResult:
        return ResolutionResult(
            disposition=ResolverDisposition.UNRATED,
            reason_code=self._reason_code,
            reason_detail=self._reason_detail,
            provider_name=self.name,
            provider_version=self.provider_version,
        )

    def resolve_likelihood(
        self,
        key: LikelihoodLookupKey,
        prefix: tuple[str, ...],
        outcome_unit: str,
        scope: Mapping[str, Any],
    ) -> ResolutionResult:
        return ResolutionResult(
            disposition=ResolverDisposition.UNRATED,
            reason_code=self._reason_code,
            reason_detail=self._reason_detail,
            provider_name=self.name,
            provider_version=self.provider_version,
        )

    def resolve_impact(
        self,
        key: ImpactLookupKey,
        target_asset_id: str,
        success_event: str,
        scope: Mapping[str, Any],
    ) -> ResolutionResult:
        return ResolutionResult(
            disposition=ResolverDisposition.UNRATED,
            reason_code=self._reason_code,
            reason_detail=self._reason_detail,
            provider_name=self.name,
            provider_version=self.provider_version,
        )


CANONICAL_EQUIVALENCE_REGISTRY_PATH = (
    Path(__file__).resolve().parents[3]
    / "docs"
    / "research"
    / "ratings"
    / "week4"
    / "impact-equivalence-registry.json"
)


def load_canonical_impact_equivalence_registry(
    path: Path | str | None = None,
) -> dict[str, Any]:
    """Load and validate the reviewed impact equivalence registry.

    Args:
        path: Optional file path to the registry JSON file.
            Defaults to CANONICAL_EQUIVALENCE_REGISTRY_PATH.

    Returns:
        The loaded registry dictionary.

    Raises:
        RankingValidationError: If the registry file is missing, malformed, or invalid.
    """
    target_path = Path(path) if path is not None else CANONICAL_EQUIVALENCE_REGISTRY_PATH
    if not target_path.exists():
        raise RankingValidationError(f"Impact equivalence registry file not found: {target_path}")

    try:
        data = json.loads(target_path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise RankingValidationError(
            f"Failed to parse impact equivalence registry {target_path}: {exc}"
        ) from exc

    if not isinstance(data, dict):
        raise RankingValidationError("Impact equivalence registry root must be a dictionary")

    mappings = data.get("mappings")
    if not isinstance(mappings, list):
        raise RankingValidationError("Impact equivalence registry must contain a 'mappings' list")

    for idx, mapping in enumerate(mappings):
        if not isinstance(mapping, dict):
            raise RankingValidationError(f"Mapping at index {idx} must be a dictionary")
        for req_field in (
            "mapping_id",
            "target_asset_id",
            "source_event",
            "destination_event",
            "consequence_rating",
            "status",
        ):
            if not mapping.get(req_field):
                raise RankingValidationError(
                    f"Mapping at index {idx} missing required field {req_field!r}"
                )
        if mapping["consequence_rating"] not in IMPACT_ORDINAL:
            raise RankingValidationError(
                f"Mapping at index {idx} invalid consequence_rating "
                f"{mapping['consequence_rating']!r}"
            )

    return data


FORBIDDEN_DA_MEMBERSHIP_MARKERS: frozenset[str] = frozenset(
    {
        "effective_member_da",
        "memberof_da",
        "domain_admin_group",
        "effective_member([v_a, g_da])",
        "checkpoint_goal",
        "g_da",
    }
)


class ReviewedEquivalenceImpactProvider:
    """Impact rating provider resolving target impact via reviewed equivalence registry.

    Reuses accepted target impact assessments (e.g. Week 3 DC compromise) when
    the target asset and consequence semantics are genuinely equivalent,
    without requiring handwritten rating packets for each event identifier.
    """

    def __init__(
        self,
        registry: Mapping[str, Any] | Path | str | None = None,
        *,
        source_packet: Mapping[str, Any] | None = None,
        name: str = "reviewed_equivalence_impact_provider",
        provider_version: str = "1.0.0",
    ) -> None:
        self._name = name
        if registry is None:
            self._registry = {"mappings": []}
        elif isinstance(registry, (Path, str)):
            self._registry = load_canonical_impact_equivalence_registry(registry)
        else:
            self._registry = deepcopy(dict(registry))

        self._version = str(self._registry.get("version") or provider_version)
        self._mappings: list[dict[str, Any]] = list(self._registry.get("mappings", []))
        self._source_packet = deepcopy(dict(source_packet)) if source_packet is not None else None

    @property
    def name(self) -> str:
        return self._name

    @property
    def provider_version(self) -> str:
        return self._version

    def _refuse(
        self, detail: str, reason_code: ReasonCode = ReasonCode.OUT_OF_SCOPE
    ) -> ResolutionResult:
        return ResolutionResult(
            disposition=ResolverDisposition.REFUSED,
            reason_code=reason_code,
            reason_detail=detail,
            provider_name=self.name,
            provider_version=self.provider_version,
        )

    def resolve_impact(
        self,
        key: ImpactLookupKey,
        target_asset_id: str,
        success_event: str,
        scope: Mapping[str, Any],
    ) -> ResolutionResult:
        goal = scope.get("target_goal", {})
        if (
            key.target_asset_id != target_asset_id
            or key.success_event != success_event
            or goal.get("target_asset_id") != target_asset_id
            or goal.get("success_event") != success_event
            or key.boundary != scope.get("work_boundary")
            or key.consequence_scope != scope.get("consequence_scope", scope.get("work_boundary"))
            or (key.scenario_id is not None and key.scenario_id != scope.get("scenario_id"))
        ):
            return self._refuse("Impact request, lookup key and target goal scope mismatch")

        # 1. Negative gate: Forbidden derivation from Domain Admin group membership
        lower_event = success_event.lower()
        if any(marker in lower_event for marker in FORBIDDEN_DA_MEMBERSHIP_MARKERS):
            return self._refuse(
                f"Forbidden derivation of target impact from Domain Admin membership entitlement: "
                f"{success_event!r}",
                reason_code=ReasonCode.PREREQUISITE_GATE_REFUSAL,
            )

        # 2. Check asset presence in registry mappings
        asset_mappings = [m for m in self._mappings if m.get("target_asset_id") == target_asset_id]
        if not asset_mappings:
            # Asset is absent from equivalence registry
            # If source packet is provided and covers this asset, but registry has no mappings:
            if self._source_packet is not None:
                impacts = self._source_packet.get("query", self._source_packet).get(
                    "target_impact_assessments", {}
                )
                if target_asset_id in impacts:
                    return self._refuse(
                        f"Target asset {target_asset_id!r} has no reviewed equivalence "
                        "mappings in registry",
                        reason_code=ReasonCode.OUT_OF_SCOPE,
                    )
            return ResolutionResult(
                disposition=ResolverDisposition.UNSUPPORTED,
                reason_code=ReasonCode.OUT_OF_SCOPE,
                reason_detail=f"Target asset {target_asset_id!r} absent from equivalence registry",
                provider_name=self.name,
                provider_version=self.provider_version,
            )

        # 3. Match mappings by success_event taking directionality into account
        matching_mappings: list[dict[str, Any]] = []
        for m in asset_mappings:
            directionality = str(m.get("directionality", "symmetric")).lower()
            src = m.get("source_event")
            dst = m.get("destination_event")

            if dst == success_event:
                matching_mappings.append(m)
            elif directionality == "symmetric" and src == success_event:
                matching_mappings.append(m)
            elif directionality != "symmetric" and src == success_event:
                # Query in reverse of asymmetric/directional mapping is strictly refused
                return self._refuse(
                    f"Equivalence mapping {m.get('mapping_id')} is directional and cannot "
                    f"be resolved in reverse for {success_event!r}",
                    reason_code=ReasonCode.PREREQUISITE_GATE_REFUSAL,
                )

        if not matching_mappings:
            return self._refuse(
                f"Unreviewed equivalence: event {success_event!r} on target asset "
                f"{target_asset_id!r} has no reviewed equivalence mapping",
                reason_code=ReasonCode.OUT_OF_SCOPE,
            )

        # 4. Filter and validate reviewed status
        valid_status_mappings: list[dict[str, Any]] = []
        for m in matching_mappings:
            status = m.get("status")
            if status != "reviewed":
                return self._refuse(
                    f"Equivalence mapping {m.get('mapping_id')!r} has unreviewed status {status!r}",
                    reason_code=ReasonCode.PREREQUISITE_GATE_REFUSAL,
                )
            valid_status_mappings.append(m)

        # 5. Validate scope / applicability
        scoped_mappings: list[dict[str, Any]] = []
        for m in valid_status_mappings:
            applicability = m.get("applicability", {})

            # Snapshot check
            req_snap = applicability.get("snapshot_id")
            scope_snap = scope.get("snapshot_id")
            if req_snap and req_snap != scope_snap:
                return self._refuse(
                    f"Equivalence snapshot mismatch: mapping requires {req_snap}, "
                    f"query has {scope_snap}",
                    reason_code=ReasonCode.OUT_OF_SCOPE,
                )

            # Boundary check
            req_boundary = applicability.get("boundary")
            scope_boundary = scope.get("work_boundary") or key.boundary or key.consequence_scope
            if req_boundary and req_boundary != scope_boundary:
                return self._refuse(
                    f"Equivalence boundary mismatch: mapping requires {req_boundary}, "
                    f"query has {scope_boundary}",
                    reason_code=ReasonCode.OUT_OF_SCOPE,
                )

            # Horizon check
            req_horizon = applicability.get("operational_horizon")
            scope_horizon = scope.get("horizon") or scope.get("operational_horizon")
            if req_horizon and req_horizon != scope_horizon:
                return self._refuse(
                    f"Equivalence operational horizon mismatch: mapping requires {req_horizon}, "
                    f"query has {scope_horizon}",
                    reason_code=ReasonCode.OUT_OF_SCOPE,
                )

            horizon_policy = applicability.get("horizon_policy")
            if horizon_policy not in (None, "independent_of_recovery_horizon"):
                return self._refuse("Unsupported impact horizon policy")
            goal = scope.get("target_goal", {})
            predicates = applicability.get("required_predicates")
            if predicates and set(goal.get("required_predicates", [])) != set(predicates):
                return self._refuse("Consequence goal predicates mismatch")
            if applicability.get("goal_id") and goal.get("goal_id") != applicability["goal_id"]:
                return self._refuse("Consequence goal ID mismatch")

            # Scenario ID check
            req_scenarios = applicability.get("scenario_id")
            if req_scenarios:
                allowed = [req_scenarios] if isinstance(req_scenarios, str) else list(req_scenarios)
                scope_scen = scope.get("scenario_id")
                if scope_scen not in allowed:
                    return self._refuse(
                        f"Equivalence scenario mismatch: {scope_scen!r} not in {allowed}",
                        reason_code=ReasonCode.OUT_OF_SCOPE,
                    )

            scoped_mappings.append(m)

        if not scoped_mappings:
            return self._refuse(
                f"Equivalence mapping out of scope for event {success_event!r}",
                reason_code=ReasonCode.OUT_OF_SCOPE,
            )

        # 6. Check for conflicting ratings among matching mappings
        ratings = {m.get("consequence_rating") for m in scoped_mappings}
        if len(ratings) > 1:
            return ResolutionResult(
                disposition=ResolverDisposition.CONFLICTING,
                reason_code=ReasonCode.CONFLICTING_PROVIDER_BASIS,
                reason_detail=(
                    f"Conflicting equivalence mappings declare different ratings: {sorted(ratings)}"
                ),
                provider_name=self.name,
                provider_version=self.provider_version,
            )

        selected = scoped_mappings[0]
        consequence_rating = selected.get("consequence_rating")
        if consequence_rating not in IMPACT_ORDINAL:
            raise RankingValidationError(
                f"Equivalence mapping {selected.get('mapping_id')!r} has invalid "
                f"consequence rating {consequence_rating!r}"
            )

        # 7. A mapping does not certify the presence or acceptance of its source.
        if self._source_packet is None:
            return self._refuse("Missing accepted source impact basis", ReasonCode.MISSING_EVIDENCE)
        source_data = self._source_packet.get("query", self._source_packet)
        source_rec = source_data.get("target_impact_assessments", {}).get(target_asset_id)
        expected_source_event = selected.get("source_event")
        if not source_rec or source_rec.get("success_event") != expected_source_event:
            return self._refuse("Source impact asset/event mismatch")
        if source_rec.get("rating_status") != "rated":
            return self._refuse("Source impact is unrated", ReasonCode.MISSING_EVIDENCE)
        if source_rec.get("consequence_rating") != consequence_rating:
            return self._refuse(
                "Source impact rating conflict", ReasonCode.CONFLICTING_PROVIDER_BASIS
            )
        mapping_digest = selected.get("source_rating_digest")
        pair_digest = source_rec.get("reviewed_disposition", {}).get("pair_digest")
        if mapping_digest and pair_digest != mapping_digest:
            return self._refuse(
                "Source rating digest mismatch", ReasonCode.CONFLICTING_PROVIDER_BASIS
            )
        release_digest = selected.get("source_release_canonical_digest")
        if not release_digest or "sha256:" + _digest_object(self._source_packet) != release_digest:
            return self._refuse(
                "Source release canonical digest mismatch", ReasonCode.CONFLICTING_PROVIDER_BASIS
            )

        # 8. Return successfully RATED result with audited metadata
        evidence_class = (
            selected.get("evidence_class")
            or self._registry.get("evidence_class")
            or BasisClassification.HUMAN_REVIEWED_AI_ASSISTED
        )
        provenance_digest = "sha256:" + _digest_object({"mapping": selected, "source": source_rec})
        review_ref = selected.get("review_reference") or self._registry.get("review_reference")

        return ResolutionResult(
            disposition=ResolverDisposition.RATED,
            value=consequence_rating,
            reason_code=ReasonCode.REVIEWED_EQUIVALENCE_MATCH,
            reason_detail=(
                f"Resolved via reviewed impact equivalence mapping {selected.get('mapping_id')!r}: "
                f"{selected.get('source_event')!r} <=> {selected.get('destination_event')!r}"
            ),
            provider_name=self.name,
            provider_version=self.provider_version,
            basis_category=evidence_class,
            provenance_digest=provenance_digest,
            review_reference=review_ref,
            numeric_basis_class=selected.get("numeric_basis_class"),
            review_status=selected.get("status"),
        )


# ---------------------------------------------------------------------------
# Helper Step Extraction
# ---------------------------------------------------------------------------


def _extract_step_technique_id(step: Any, idx: int = 0) -> str:
    """Extract technique identifier from step dictionary or TransitionStep object."""
    if isinstance(step, dict):
        tech = step.get("technique_id") or step.get("technique")
        if isinstance(tech, str) and tech.strip():
            return tech.strip()
    return extract_technique_id(step, idx)


def _extract_step_endpoints(step: Any, default_actor: str) -> tuple[str, str, str]:
    """Extract canonical (actor, source, target) from step dict or transition."""
    if isinstance(step, dict):
        actor = step.get("actor") or step.get("actor_id") or default_actor
        source = step.get("source") or step.get("source_node_id") or actor
        target = step.get("target") or step.get("target_id") or step.get("target_node_id")
        return str(actor).strip(), str(source).strip(), str(target).strip()

    res = getattr(step, "result", None)
    req = getattr(res, "request", None) if res else None
    if req is not None:
        actor = getattr(req, "actor", default_actor)
        source = getattr(req, "source", actor)
        target = getattr(req, "target", None)
        return str(actor).strip(), str(source).strip(), str(target).strip()

    raise RankingValidationError(f"Cannot extract endpoints from transition step {step!r}")


def _extract_step_edge_id(step: Any) -> str | None:
    if isinstance(step, dict):
        return step.get("edge_id")
    return getattr(step, "edge_id", None)


# ---------------------------------------------------------------------------
# Rating Resolver
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RatingResolutionOutput:
    """Complete output of RatingResolver ready for canonical PathRankingEngine."""

    ranking_query: dict[str, Any]
    candidate_envelopes: list[dict[str, Any]]
    coverage_report: dict[str, Any]
    disposition_summary: dict[str, Any]


class RatingResolver:
    """Rating Resolver coordinating C, P, I resolution across candidate paths.

    Connects generated semantic attack paths to the existing C/P/I ranking evaluator:
    - Generates deterministic versioned IDs and rating lookup keys.
    - Preserves ordered full-history active-work prefixes for P.
    - Classifies active work, passive propagation/closure, and shared preparation.
    - Resolves C, P, I through provider chains with strict refusal integrity.
    - Builds machine-readable per-candidate and aggregate coverage report.
    - Emits wire payloads accepted by the canonical validator even when unrated.
    """

    def __init__(
        self,
        *,
        effort_providers: Sequence[EffortRatingProvider] = (),
        likelihood_providers: Sequence[LikelihoodRatingProvider] = (),
        impact_providers: Sequence[ImpactRatingProvider] = (),
        explicit_packet: Mapping[str, Any] | None = None,
        impact_equivalence_registry: Mapping[str, Any] | Path | str | None = None,
        ledger_version: str = DEFAULT_LEDGER_VERSION,
        contract_version: str = RESOLVER_CONTRACT_VERSION,
        fallback_provider: FallbackUnratedProvider | None = None,
    ) -> None:
        self.ledger_version = ledger_version
        self.contract_version = contract_version
        self.fallback = fallback_provider or FallbackUnratedProvider()

        # Build provider chains; explicit packet takes priority if supplied
        eff_chain: list[EffortRatingProvider] = []
        lik_chain: list[LikelihoodRatingProvider] = []
        imp_chain: list[ImpactRatingProvider] = []

        if explicit_packet is not None:
            packet_prov = ExplicitPacketRatingProvider(explicit_packet)
            eff_chain.append(packet_prov)
            lik_chain.append(packet_prov)
            imp_chain.append(packet_prov)

        equiv_reg = impact_equivalence_registry
        if isinstance(equiv_reg, (str, Path)):
            equiv_reg = load_canonical_impact_equivalence_registry(equiv_reg)

        if equiv_reg and impact_equivalence_registry is not False:
            imp_chain.append(
                ReviewedEquivalenceImpactProvider(
                    equiv_reg,
                    source_packet=explicit_packet,
                )
            )

        eff_chain.extend(effort_providers)
        lik_chain.extend(likelihood_providers)
        imp_chain.extend(impact_providers)

        # Append fail-closed fallback
        eff_chain.append(self.fallback)
        lik_chain.append(self.fallback)
        imp_chain.append(self.fallback)

        self.effort_providers = tuple(eff_chain)
        self.likelihood_providers = tuple(lik_chain)
        self.impact_providers = tuple(imp_chain)

    def resolve(
        self,
        candidates: Sequence[Any],
        query_scope: Mapping[str, Any],
        *,
        shared_preparation_units: Mapping[str, Mapping[str, Any]] | None = None,
        transition_bindings: Mapping[tuple[str, str, str, str] | tuple[str, int], Mapping[str, Any]]
        | None = None,
    ) -> RatingResolutionOutput:
        """Resolve ratings and materialize contract payloads for given candidates."""
        # 1. Validate query scope
        scope = dict(query_scope)
        query_meta = self._build_query_metadata(scope)
        facts_ledger = deepcopy(scope.get("facts_ledger", {}))
        predicate_layers = {
            predicate: fact["layer"]
            for predicate, fact in resolve_facts_ledger(
                facts_ledger, query_meta["evaluation_mode"]
            ).items()
        }

        # 2. Extract and bind actions and work units across all candidates
        # Maintain order and identity invariance
        shared_preps = self._normalize_shared_preparations(shared_preparation_units or {})
        bound_actions_catalog: dict[str, dict[str, Any]] = {}
        work_units_ledger: dict[str, dict[str, Any]] = {}
        parsed_candidates: list[dict[str, Any]] = []

        target_asset_id = query_meta["target_goal"]["target_asset_id"]

        for cand_idx, raw_cand in enumerate(candidates):
            parsed = self._parse_candidate_structure(
                raw_cand,
                cand_idx=cand_idx,
                query_meta=query_meta,
                shared_preps=shared_preps,
                bound_actions_catalog=bound_actions_catalog,
                work_units_ledger=work_units_ledger,
                predicate_layers=predicate_layers,
                transition_bindings=transition_bindings or {},
            )
            parsed_candidates.append(parsed)
        ids = [c["candidate_id"] for c in parsed_candidates]
        if len(set(ids)) != len(ids):
            raise RankingValidationError("Duplicate candidate_id in resolver input")

        # 3. Resolve Effort (C) on work units ledger
        c_coverage, c_trace = self._resolve_effort_ledger(work_units_ledger, query_meta)

        # 4. Resolve Likelihood (P) on candidate prefixes
        bounds_records: list[dict[str, Any]] = []
        p_coverage = self._resolve_likelihood_prefixes(
            parsed_candidates, query_meta, bounds_records, work_units_ledger
        )

        # 5. Resolve Impact (I) on target asset
        i_coverage = self._resolve_target_impact(
            target_asset_id, query_meta["target_goal"]["success_event"], query_meta
        )

        # 6. Ensure all predicates referenced in actions/goal exist in predicate_layers
        self._ensure_predicate_layers(
            predicate_layers, bound_actions_catalog.values(), query_meta["target_goal"]
        )
        facts_ledger["predicate_layers"] = predicate_layers

        # 7. Materialize wire PathRankingQuery payload
        target_impact_assessments = {
            target_asset_id: {
                "target_asset_id": target_asset_id,
                "success_event": query_meta["target_goal"]["success_event"],
                "rating_status": (
                    "rated" if i_coverage["disposition"] == ResolverDisposition.RATED else "unrated"
                ),
                "consequence_rating": i_coverage["consequence_rating"],
                "rating_audit": i_coverage["rating_audit"],
                "missing_basis_reasons": (
                    []
                    if i_coverage["disposition"] == ResolverDisposition.RATED
                    else [f"{i_coverage['reason_code']}: {i_coverage['reason_detail']}"]
                ),
            }
        }

        wire_query = {
            "query_metadata": query_meta,
            "facts_ledger": facts_ledger,
            "bound_actions": list(bound_actions_catalog.values()),
            "work_units_ledger": work_units_ledger,
            "conditional_bounds_table": bounds_records,
            "target_impact_assessments": target_impact_assessments,
        }

        # 8. Materialize candidate envelopes
        envelopes = [p["envelope"] for p in parsed_candidates]

        # 9. Build machine-readable coverage report
        coverage_report = self._build_coverage_report(
            query_meta=query_meta,
            parsed_candidates=parsed_candidates,
            c_coverage=c_coverage,
            p_coverage=p_coverage,
            i_coverage=i_coverage,
        )

        disposition_summary = {
            "total_candidates": len(candidates),
            "fully_rated_candidates": coverage_report["aggregate_summary"][
                "fully_rated_candidates"
            ],
            "all_c_rated": all(
                c["c_complete"] for c in coverage_report["candidate_summaries"].values()
            ),
            "all_p_rated": all(
                c["p_complete"] for c in coverage_report["candidate_summaries"].values()
            ),
            "all_i_rated": i_coverage["disposition"] == ResolverDisposition.RATED,
            "unresolved_gaps_count": len(coverage_report["unresolved_gaps"]),
        }

        return RatingResolutionOutput(
            ranking_query=wire_query,
            candidate_envelopes=envelopes,
            coverage_report=coverage_report,
            disposition_summary=disposition_summary,
        )

    # -----------------------------------------------------------------------
    # Parsing and Identity Generation
    # -----------------------------------------------------------------------

    def _normalize_shared_preparations(
        self, declarations: Mapping[str, Mapping[str, Any]]
    ) -> dict[str, dict[str, Any]]:
        normalized = {}
        by_uid = {}
        for key, declaration in declarations.items():
            record = deepcopy(dict(declaration))
            status = record.get("rating_status", "unrated")
            record["rating_status"] = status
            cost = record.get("computed_cost", record.get("effort_cost"))
            if (
                "computed_cost" in record
                and "effort_cost" in record
                and record["computed_cost"] != record["effort_cost"]
            ):
                raise RankingValidationError("Conflicting shared preparation cost aliases")
            record["computed_cost"] = record["effort_cost"] = cost
            uid = record.get("work_unit_id")
            validation_id = uid or str(key)
            validate_work_units_ledger(
                {
                    validation_id: {
                        **record,
                        "overlap_state": record.get("overlap_state", "independent"),
                        "missing_basis_reasons": []
                        if status == "rated"
                        else ["Unrated shared preparation"],
                    }
                }
            )
            if uid:
                if uid in by_uid and by_uid[uid] != record:
                    raise RankingValidationError(
                        f"Conflicting shared preparation declarations for {uid!r}"
                    )
                by_uid[uid] = record
            normalized[key] = record
        return normalized

    def _build_query_metadata(self, scope: dict[str, Any]) -> dict[str, Any]:
        """Validate and construct query_metadata section."""
        query_id = str(scope.get("query_id", "query-resolved-001")).strip()
        scenario_id = str(scope.get("scenario_id", "scenario-resolved")).strip()
        scenario_version = str(scope.get("scenario_version", "1.0.0")).strip()
        snapshot_id = str(scope.get("snapshot_id", "sha256:" + "0" * 64)).strip()
        foothold_node_id = str(scope.get("foothold_node_id", "")).strip()
        if not is_canonical_node_id(foothold_node_id):
            raise RankingValidationError(
                f"Invalid canonical foothold_node_id: {foothold_node_id!r}"
            )

        work_boundary = str(scope.get("work_boundary", "intra_forest")).strip()
        horizon = str(scope.get("horizon", "24h")).strip()
        budget = scope.get("active_work_budget", 10)
        if type(budget) is not int or budget < 0:
            raise RankingValidationError("active_work_budget must be an exact non-negative integer")
        eval_mode = str(scope.get("evaluation_mode", "scenario")).strip()

        target_goal = dict(scope.get("target_goal", {}))
        if not target_goal.get("goal_id"):
            target_goal["goal_id"] = "goal_terminal"
        if not target_goal.get("required_predicates"):
            target_goal["required_predicates"] = ["target_compromised"]
        if not target_goal.get("target_asset_id"):
            target_goal["target_asset_id"] = scope.get("target_asset_id", foothold_node_id)
        if not target_goal.get("success_event"):
            target_goal["success_event"] = "terminal_compromise"

        target_asset_id = target_goal["target_asset_id"]
        if not is_canonical_node_id(target_asset_id):
            raise RankingValidationError(f"Invalid canonical target_asset_id: {target_asset_id!r}")

        policy_id = str(scope.get("policy_id") or "").strip() or None

        meta: dict[str, Any] = {
            "query_id": query_id,
            "version": "1.0.0",
            "scenario_id": scenario_id,
            "scenario_version": scenario_version,
            "snapshot_id": snapshot_id,
            "evaluation_mode": eval_mode,
            "work_boundary": work_boundary,
            "foothold_node_id": foothold_node_id,
            "target_goal": target_goal,
            "horizon": horizon,
            "active_work_budget": budget,
        }
        if policy_id is not None:
            meta["policy_id"] = policy_id
        if "coverage" in scope:
            meta["coverage"] = scope["coverage"]
        # Providers must receive the caller's explicit governance/context gates.
        for field in (
            "governance",
            "actor_capability",
            "target_complexity_class",
            "control_scope",
            "retry_policy",
            "target_population",
            "recovery_metadata",
            "is_synthetic_fixture",
            "semantic_goal",
        ):
            if field in scope:
                meta[field] = deepcopy(scope[field])
        return meta

    def _parse_candidate_structure(
        self,
        candidate: Any,
        *,
        cand_idx: int,
        query_meta: dict[str, Any],
        shared_preps: dict[str, Any],
        bound_actions_catalog: dict[str, dict[str, Any]],
        work_units_ledger: dict[str, dict[str, Any]],
        predicate_layers: dict[str, int],
        transition_bindings: Mapping[
            tuple[str, str, str, str] | tuple[str, int], Mapping[str, Any]
        ],
    ) -> dict[str, Any]:
        """Parse one candidate, binding actions, work units, and route segments."""
        foothold_id = query_meta["foothold_node_id"]
        target_asset_id = query_meta["target_goal"]["target_asset_id"]
        work_boundary = query_meta["work_boundary"]

        # Extract basic candidate metadata
        if isinstance(candidate, dict):
            cand_id = candidate.get("candidate_id") or f"Candidate_{cand_idx + 1}"
            history = list(candidate.get("transition_history", ()))
        else:
            cand_id = getattr(candidate, "candidate_id", f"Candidate_{cand_idx + 1}")
            history = list(getattr(candidate, "transition_history", ()))

        is_zero_action = len(history) == 0

        # Handle zero-action initial goal
        if is_zero_action:
            if target_asset_id != foothold_id:
                raise RankingValidationError(
                    f"Zero-action candidate {cand_id!r} target {target_asset_id!r} "
                    f"does not match foothold {foothold_id!r}"
                )
            scope_binding = {field: query_meta[field] for field in REQUIRED_SCOPE_BINDING_FIELDS}
            declared_routes = (
                candidate.get("structural_routes")
                if isinstance(candidate, dict)
                else getattr(candidate, "structural_routes", None)
            )
            structural_routes = (
                list(declared_routes)
                if declared_routes
                else [
                    {
                        "route_id": f"{cand_id}:route:0",
                        "node_ids": [foothold_id],
                        "edge_ids": [],
                        "provenance_locators": [],
                    }
                ]
            )
            envelope = {
                "candidate_id": cand_id,
                "scope_binding": scope_binding,
                "target_asset_id": target_asset_id,
                "bound_action_ids": [],
                "work_packets": [()],
                "structural_routes": structural_routes,
                "required_predicates": (
                    list(candidate.get("required_predicates", []))
                    if isinstance(candidate, dict)
                    else []
                ),
            }
            return {
                "candidate_id": cand_id,
                "is_zero_action": True,
                "envelope": envelope,
                "bound_action_ids": [],
                "work_packets": [()],
                "active_work_program": (),
            }

        # Process non-empty transitions
        bound_action_ids: list[str] = []
        work_packets: list[tuple[str, ...]] = []
        adapter_history: list[Any] = []
        declared_edges: list[dict[str, Any]] = []

        current_actor = foothold_id
        for step_idx, step in enumerate(history):
            technique_id = _extract_step_technique_id(step, step_idx)
            actor, source, target = _extract_step_endpoints(step, current_actor)
            edge_id = _extract_step_edge_id(step)
            result = step.get("result") if isinstance(step, dict) else getattr(step, "result", None)
            status = (
                result.get("status")
                if isinstance(result, dict)
                else getattr(result, "status", None)
            )
            if status is not None and status != "applicable":
                raise RankingValidationError(f"Transition step {step_idx} is not applicable")

            if not is_canonical_node_id(actor):
                raise RankingValidationError(
                    f"Invalid canonical actor in step {step_idx}: {actor!r}"
                )
            if not is_canonical_node_id(source):
                raise RankingValidationError(
                    f"Invalid canonical source in step {step_idx}: {source!r}"
                )
            if not is_canonical_node_id(target):
                raise RankingValidationError(
                    f"Invalid canonical target in step {step_idx}: {target!r}"
                )
            if edge_id and not is_canonical_edge_id(edge_id):
                raise RankingValidationError(
                    f"Invalid canonical edge_id in step {step_idx}: {edge_id!r}"
                )

            # Check passive closure semantics
            step_dict = (
                dict(step)
                if isinstance(step, dict)
                else dict(
                    transition_bindings.get(
                        (cand_id, step_idx),
                        transition_bindings.get((technique_id, actor, source, target), {}),
                    )
                )
            )
            if "requires" not in step_dict or "adds" not in step_dict:
                raise RankingValidationError(
                    f"Transition step {step_idx} requires explicit predicate binding "
                    "(requires/adds); placeholder predicates are forbidden"
                )
            is_passive = bool(
                step_dict.get("is_passive_closure", False)
                or getattr(step, "is_passive_closure", False)
                or technique_id in KNOWN_PASSIVE_TECHNIQUES
            )

            # Determine prerequisites and effects
            requires = list(step_dict.get("requires", []))
            adds = list(step_dict.get("adds", []))

            for predicate, layer in step_dict.get("predicate_layers", {}).items():
                if layer not in (1, 2, 3):
                    raise RankingValidationError(f"Invalid layer for {predicate!r}: {layer}")
                if predicate in predicate_layers and predicate_layers[predicate] != layer:
                    raise RankingValidationError(f"Conflicting layer declaration for {predicate!r}")
                predicate_layers[predicate] = layer

            method = (
                str(step_dict.get("method") or getattr(step, "method", "default")).strip()
                or "default"
            )
            auth_context = step_dict.get("auth_context") or getattr(step, "auth_context", None)
            resource_context = step_dict.get("resource_context") or getattr(
                step, "resource_context", None
            )
            policy_id = (
                step_dict.get("policy_id")
                or getattr(step, "policy_id", None)
                or query_meta.get("policy_id")
            )

            step_context = {
                "requires": requires,
                "adds": adds,
                "is_passive_closure": is_passive,
                "edge_id": edge_id,
                "source_id": source,
                "method": method,
                "auth_context": auth_context,
                "resource_context": resource_context,
                "policy_id": policy_id,
            }

            action_id = (
                step_dict.get("action_id")
                or getattr(step, "action_id", None)
                or generate_bound_action_id(
                    technique_id,
                    actor,
                    target,
                    step_context,
                    source_id=source,
                    version=self.contract_version,
                )
            )

            # Determine work units
            ref_unit_ids: list[str] = []
            if is_passive:
                ref_unit_ids = []
                work_packets.append(())
            else:
                # Check if step references explicit work units or shared preparations
                declared_units = step_dict.get("referenced_work_unit_ids") or step_dict.get(
                    "bound_work_units"
                )
                if declared_units is not None:
                    ref_unit_ids = list(declared_units)
                else:
                    # Check shared preparation for this step/target
                    prep_keys_to_check = [
                        step_dict.get("shared_prep_key"),
                        step_dict.get("shared_preparation_id"),
                        f"{technique_id}:{actor}:{target}",
                        f"{actor}:{target}",
                    ]
                    prep_unit = None
                    for pk in prep_keys_to_check:
                        if pk and pk in shared_preps:
                            prep_unit = shared_preps[pk]
                            break

                    if prep_unit is not None:
                        prep_uid = prep_unit.get("work_unit_id") or generate_work_unit_id(
                            prep_unit.get("technique", "auth_context"),
                            prep_unit.get("actor_id", actor),
                            prep_unit.get("target_id", target),
                            prep_unit.get("context", "auth"),
                            work_boundary,
                            ledger_version=self.ledger_version,
                        )
                        ref_unit_ids.append(prep_uid)
                        is_rated_prep = prep_unit.get("rating_status") == "rated"
                        cost_val = prep_unit.get("computed_cost", prep_unit.get("effort_cost"))
                        prep_record = {
                            "work_unit_id": prep_uid,
                            "alias": prep_unit.get("alias", prep_uid),
                            "rating_status": "rated" if is_rated_prep else "unrated",
                            "overlap_state": prep_unit.get("overlap_state", "independent"),
                            "missing_basis_reasons": (
                                [] if is_rated_prep else ["Unrated shared preparation"]
                            ),
                            "computed_cost": cost_val if is_rated_prep else None,
                            "effort_cost": cost_val if is_rated_prep else None,
                            "rubric_scores": prep_unit.get("rubric_scores")
                            if is_rated_prep
                            else None,
                            "classification": WorkUnitClassification.SHARED_PREPARATION.value,
                            "technique": prep_unit.get("technique", "auth_context"),
                            "actor_id": prep_unit.get("actor_id", actor),
                            "source_id": prep_unit.get(
                                "source_id", prep_unit.get("actor_id", actor)
                            ),
                            "target_id": prep_unit.get("target_id", target),
                            "method": prep_unit.get("method", "default"),
                            "auth_context": prep_unit.get("auth_context"),
                            "resource_context": prep_unit.get("resource_context"),
                            "policy_id": prep_unit.get("policy_id", query_meta.get("policy_id")),
                        }

                        for field in (
                            "basis_category",
                            "provider_version",
                            "provenance_digest",
                            "review_reference",
                        ):
                            if field in prep_unit:
                                prep_record[field] = prep_unit[field]
                        existing_prep = work_units_ledger.get(prep_uid)
                        if existing_prep is not None and existing_prep != prep_record:
                            raise RankingValidationError(
                                f"Conflicting shared preparation {prep_uid!r}"
                            )
                        work_units_ledger[prep_uid] = prep_record

                    # Main work unit for this active action
                    main_unit_id = generate_work_unit_id(
                        technique_id,
                        actor,
                        target,
                        context="ctx-"
                        + _digest_object(
                            {
                                "source_id": source,
                                "method": method,
                                "auth_context": auth_context,
                                "resource_context": resource_context,
                                "policy_id": policy_id,
                                "scope": query_meta["scenario_id"],
                            }
                        ),
                        boundary=work_boundary,
                        ledger_version=self.ledger_version,
                    )
                    ref_unit_ids.append(main_unit_id)

                for uid in ref_unit_ids:
                    if uid in work_units_ledger:
                        existing = work_units_ledger[uid]
                        if (
                            existing.get("classification")
                            != WorkUnitClassification.SHARED_PREPARATION
                        ):
                            context_fields = {
                                "source_id": source,
                                "auth_context": auth_context,
                                "resource_context": resource_context,
                                "policy_id": policy_id,
                                "technique": technique_id,
                                "actor_id": actor,
                                "target_id": target,
                                "method": method,
                            }
                            if any(existing.get(k) != v for k, v in context_fields.items()):
                                raise RankingValidationError(
                                    f"Conflicting applicability for work unit {uid!r}"
                                )
                    if uid not in work_units_ledger:
                        work_units_ledger[uid] = {
                            "work_unit_id": uid,
                            "alias": step_dict.get("alias", uid),
                            "rating_status": "unrated",
                            "overlap_state": "independent",
                            "missing_basis_reasons": ["Unrated candidate work unit"],
                            "computed_cost": None,
                            "effort_cost": None,
                            "rubric_scores": None,
                            "classification": WorkUnitClassification.ACTIVE_WORK.value,
                            "technique": technique_id,
                            "actor_id": actor,
                            "source_id": source,
                            "target_id": target,
                            "method": method,
                            "auth_context": auth_context,
                            "resource_context": resource_context,
                            "policy_id": policy_id,
                        }
                work_packets.append(tuple(ref_unit_ids))

            # Register bound action
            if action_id not in bound_actions_catalog:
                bound_actions_catalog[action_id] = {
                    "action_id": action_id,
                    "technique_name": technique_id,
                    "technique": technique_id,
                    "actor_id": actor,
                    "source_node_id": actor,
                    "structural_source_node_id": source,
                    "target_id": target,
                    "target_node_id": target,
                    "is_passive_closure": is_passive,
                    "referenced_work_unit_ids": ref_unit_ids,
                    "bound_work_units": ref_unit_ids,
                    "requires": requires,
                    "adds": adds,
                    "edge_id": edge_id,
                }
            else:
                registered = bound_actions_catalog[action_id]
                if (
                    registered["requires"] != requires
                    or registered["adds"] != adds
                    or registered["referenced_work_unit_ids"] != ref_unit_ids
                    or registered["actor_id"] != actor
                    or registered["structural_source_node_id"] != source
                    or registered["target_id"] != target
                    or registered["edge_id"] != edge_id
                ):
                    raise RankingValidationError(f"Conflicting bound action {action_id!r}")

            bound_action_ids.append(action_id)

            if isinstance(step, dict):
                adapter_history.append(
                    {
                        "edge_id": edge_id,
                        "derived_from_step": step.get("derived_from_step"),
                        "result": step.get("result")
                        or {
                            "request": {
                                "technique_id": technique_id,
                                "actor": actor,
                                "source": source,
                                "target": target,
                            },
                            "status": step.get("status", "applicable"),
                        },
                    }
                )
                if edge_id and "provenance" in step:
                    declared_edges.append(
                        {
                            "id": edge_id,
                            "source": source,
                            "target": target,
                            "provenance": step["provenance"],
                        }
                    )
            else:
                adapter_history.append(step)

        # Build candidate envelope
        scope_binding = {field: query_meta[field] for field in REQUIRED_SCOPE_BINDING_FIELDS}
        active_program = tuple(dict.fromkeys(u for packet in work_packets for u in packet))
        if isinstance(candidate, dict):
            adapter_path = {
                **candidate,
                "nodes": candidate.get("nodes")
                or [foothold_id] + [_extract_step_endpoints(s, foothold_id)[2] for s in history],
                "edges": candidate.get("edges", declared_edges),
                "transition_history": adapter_history,
            }
        else:
            adapter_path = candidate
        envelope = convert_path_result_to_candidate_envelope(
            adapter_path,
            cand_id,
            target_asset_id,
            query_meta,
            bound_action_ids,
            route_id=f"{cand_id}:route:0",
            bound_actions_catalog=bound_actions_catalog,
            success_event=query_meta["target_goal"]["success_event"],
        )
        envelope["work_packets"] = [list(p) for p in work_packets]
        envelope["required_predicates"] = (
            list(candidate.get("required_predicates", [])) if isinstance(candidate, dict) else []
        )

        return {
            "candidate_id": cand_id,
            "is_zero_action": False,
            "envelope": envelope,
            "bound_action_ids": bound_action_ids,
            "work_packets": work_packets,
            "active_work_program": active_program,
        }

    # -----------------------------------------------------------------------
    # C, P, I Resolution Loops
    # -----------------------------------------------------------------------

    def _resolve_effort_ledger(
        self,
        ledger: dict[str, dict[str, Any]],
        query_meta: dict[str, Any],
    ) -> tuple[dict[str, Any], dict[str, list[dict[str, Any]]]]:
        """Resolve effort for each work unit in the ledger through provider chain."""
        c_coverage: dict[str, Any] = {}
        c_traces: dict[str, list[dict[str, Any]]] = {}

        for unit_id, unit_rec in ledger.items():
            technique = unit_rec.get("technique")
            actor = unit_rec.get("actor_id")
            source = unit_rec.get("source_id") or actor
            target = unit_rec.get("target_id")
            method = unit_rec.get("method") or "default"
            auth_context = unit_rec.get("auth_context")
            resource_context = unit_rec.get("resource_context")
            policy_id = unit_rec.get("policy_id") or query_meta.get("policy_id")

            if not technique or not actor or not target:
                tokens = unit_id.split(":")
                technique = technique or (tokens[0] if len(tokens) >= 1 else "unknown")
                actor = actor or (tokens[1] if len(tokens) >= 2 else query_meta["foothold_node_id"])
                target = target or (
                    tokens[2] if len(tokens) >= 3 else query_meta["target_goal"]["target_asset_id"]
                )
                if method == "default" and len(tokens) >= 4:
                    method = tokens[3]
                source = source or actor

            lookup_key = generate_rating_lookup_key_c(
                work_unit_id=unit_id,
                technique=technique,
                actor_id=actor,
                source_id=source,
                target_id=target,
                work_class=WorkUnitClassification(
                    unit_rec.get("classification", WorkUnitClassification.ACTIVE_WORK)
                ),
                method=method,
                boundary=query_meta["work_boundary"],
                scope=query_meta["scenario_id"],
                auth_context=auth_context,
                resource_context=resource_context,
                policy_id=policy_id,
                version=self.contract_version,
            )

            # Check if unit is already rated
            if (
                unit_rec.get("rating_status") == "rated"
                and unit_rec.get("computed_cost") is not None
            ):
                validate_work_units_ledger({unit_id: unit_rec})
                cost_val = unit_rec["computed_cost"]
                result = ResolutionResult(
                    ResolverDisposition.RATED,
                    cost_val,
                    provider_name="pre_rated",
                    provider_version=unit_rec.get("provider_version", self.ledger_version),
                    basis_category=unit_rec.get(
                        "basis_category", BasisClassification.SYNTHETIC_TEST_ONLY
                    ),
                    provenance_digest=unit_rec.get("provenance_digest"),
                    review_reference=unit_rec.get("review_reference"),
                )
                audit = _rating_audit(result, lookup_key, query_meta)
                unit_rec["rating_audit"] = audit
                c_coverage[unit_id] = {
                    "work_unit_id": unit_id,
                    "disposition": ResolverDisposition.RATED,
                    "cost": cost_val,
                    "reason_code": ReasonCode.REVIEWED_PACKET_MATCH,
                    "reason_detail": "Pre-rated work unit",
                    "selected_provider": "pre_rated",
                    "basis_category": unit_rec.get(
                        "basis_category", BasisClassification.SYNTHETIC_TEST_ONLY
                    ),
                    "rating_audit": audit,
                    "provider_trace": [],
                }
                c_traces[unit_id] = []
                continue

            trace: list[dict[str, Any]] = []
            selected_res: ResolutionResult | None = None
            last_res: ResolutionResult | None = None

            for prov in self.effort_providers:
                res = prov.resolve_effort(lookup_key, unit_rec, query_meta)
                trace.append(
                    {
                        "provider": prov.name,
                        "rating_audit": _rating_audit(res, lookup_key, query_meta),
                        "disposition": str(res.disposition),
                        "reason_code": str(res.reason_code),
                        "reason_detail": res.reason_detail,
                    }
                )
                last_res = res

                if res.disposition == ResolverDisposition.RATED:
                    selected_res = res
                    break
                if res.disposition in (
                    ResolverDisposition.REFUSED,
                    ResolverDisposition.CONFLICTING,
                ):
                    selected_res = res
                    break
                if (
                    res.disposition == ResolverDisposition.UNRATED
                    and res.reason_code == ReasonCode.EXPLICIT_UNRATED_DISPOSITION
                ):
                    selected_res = res
                    break

            if selected_res is None:
                selected_res = last_res

            if selected_res is None or selected_res.disposition != ResolverDisposition.RATED:
                disposition = (
                    selected_res.disposition if selected_res else ResolverDisposition.UNRATED
                )
                reason_code = (
                    selected_res.reason_code if selected_res else ReasonCode.MISSING_EVIDENCE
                )
                reason_detail = (
                    selected_res.reason_detail if selected_res else "No provider resolved effort"
                )

                unit_rec["rating_status"] = "unrated"
                unit_rec["status"] = "unrated"
                unit_rec["computed_cost"] = None
                unit_rec["effort_cost"] = None
                unit_rec["rubric_scores"] = None
                unit_rec["missing_basis_reasons"] = [f"{reason_code}: {reason_detail}"]
                unit_rec["rating_audit"] = _rating_audit(selected_res, lookup_key, query_meta)

                c_coverage[unit_id] = {
                    "work_unit_id": unit_id,
                    "disposition": disposition,
                    "cost": None,
                    "reason_code": reason_code,
                    "reason_detail": reason_detail,
                    "selected_provider": selected_res.provider_name if selected_res else None,
                    "basis_category": None,
                    "rating_audit": _rating_audit(selected_res, lookup_key, query_meta),
                    "provider_trace": trace,
                }
            else:
                cost_val = selected_res.value
                rubric = selected_res.rubric_scores
                if rubric is None:
                    raise RankingValidationError(
                        f"Rated effort {unit_id!r} requires explicit rubric_scores"
                    )
                unit_rec["rating_status"] = "rated"
                unit_rec["status"] = "rated"
                unit_rec["computed_cost"] = cost_val
                unit_rec["effort_cost"] = cost_val
                unit_rec["rubric_scores"] = rubric
                unit_rec["rating_audit"] = _rating_audit(selected_res, lookup_key, query_meta)
                unit_rec["missing_basis_reasons"] = []
                validate_work_units_ledger({unit_id: unit_rec})

                c_coverage[unit_id] = {
                    "work_unit_id": unit_id,
                    "disposition": ResolverDisposition.RATED,
                    "cost": cost_val,
                    "reason_code": selected_res.reason_code,
                    "reason_detail": selected_res.reason_detail,
                    "selected_provider": selected_res.provider_name,
                    "basis_category": selected_res.basis_category,
                    "rating_audit": _rating_audit(selected_res, lookup_key, query_meta),
                    "provider_trace": trace,
                }

            c_traces[unit_id] = trace

        return c_coverage, c_traces

    def _resolve_likelihood_prefixes(
        self,
        parsed_candidates: list[dict[str, Any]],
        query_meta: dict[str, Any],
        bounds_records: list[dict[str, Any]],
        work_units_ledger: dict[str, dict[str, Any]],
    ) -> dict[str, dict[str, Any]]:
        """Resolve conditional likelihood intervals for all unique active-work prefixes."""
        seen_prefixes: dict[tuple[str, ...], dict[str, Any]] = {}

        for p_cand in parsed_candidates:
            if p_cand["is_zero_action"]:
                continue
            program = p_cand["active_work_program"]
            for length in range(1, len(program) + 1):
                prefix = program[:length]
                if prefix not in seen_prefixes:
                    seen_prefixes[prefix] = {
                        "prefix": prefix,
                        "outcome_unit": prefix[-1],
                        "candidate_ids": [p_cand["candidate_id"]],
                    }
                else:
                    seen_prefixes[prefix]["candidate_ids"].append(p_cand["candidate_id"])

        p_coverage: dict[str, Any] = {}
        added_to_table: set[tuple[str, ...]] = set()

        sorted_prefixes = sorted(seen_prefixes.keys(), key=lambda p: (len(p), p))

        for prefix in sorted_prefixes:
            p_info = seen_prefixes[prefix]
            outcome_unit = p_info["outcome_unit"]
            prefix_key_str = json.dumps(list(prefix))

            unit_rec = work_units_ledger.get(outcome_unit, {})
            technique = unit_rec.get("technique")
            actor = unit_rec.get("actor_id")
            source = unit_rec.get("source_id") or actor
            target = unit_rec.get("target_id")
            method = unit_rec.get("method") or "default"
            auth_context = unit_rec.get("auth_context")
            resource_context = unit_rec.get("resource_context")
            policy_id = unit_rec.get("policy_id") or query_meta.get("policy_id")

            if not technique or not actor or not target:
                tokens = outcome_unit.split(":")
                technique = technique or (tokens[0] if len(tokens) >= 1 else "unknown")
                actor = actor or (tokens[1] if len(tokens) >= 2 else query_meta["foothold_node_id"])
                target = target or (
                    tokens[2] if len(tokens) >= 3 else query_meta["target_goal"]["target_asset_id"]
                )
                if method == "default" and len(tokens) >= 4:
                    method = tokens[3]
                source = source or actor

            lookup_key = generate_rating_lookup_key_p(
                scenario_id=query_meta["scenario_id"],
                scenario_version=query_meta["scenario_version"],
                snapshot_id=query_meta["snapshot_id"],
                foothold_node_id=query_meta["foothold_node_id"],
                ordered_work_prefix=prefix,
                outcome_work_unit_id=outcome_unit,
                outcome_technique=technique,
                actor_id=actor,
                source_id=source,
                target_id=target,
                method=method,
                budget=query_meta["active_work_budget"],
                horizon=query_meta["horizon"],
                boundary=query_meta["work_boundary"],
                scope=query_meta["scenario_id"],
                auth_context=auth_context,
                resource_context=resource_context,
                policy_id=policy_id,
                version=self.contract_version,
            )

            trace: list[dict[str, Any]] = []
            selected_res: ResolutionResult | None = None
            last_res: ResolutionResult | None = None

            for prov in self.likelihood_providers:
                res = prov.resolve_likelihood(
                    lookup_key,
                    prefix,
                    outcome_unit,
                    {**query_meta, "resolved_work_units": work_units_ledger},
                )
                trace.append(
                    {
                        "provider": prov.name,
                        "rating_audit": _rating_audit(res, lookup_key, query_meta),
                        "disposition": str(res.disposition),
                        "reason_code": str(res.reason_code),
                        "reason_detail": res.reason_detail,
                    }
                )
                last_res = res

                if res.disposition == ResolverDisposition.RATED:
                    selected_res = res
                    break
                if res.disposition in (
                    ResolverDisposition.REFUSED,
                    ResolverDisposition.CONFLICTING,
                ):
                    selected_res = res
                    break

            if selected_res is None:
                selected_res = last_res

            if selected_res is not None and selected_res.disposition == ResolverDisposition.RATED:
                lo, hi = selected_res.value
                lo_rat = parse_rational(lo)
                hi_rat = parse_rational(hi)
                if not (0 <= lo_rat <= hi_rat <= 1):
                    raise RankingValidationError(
                        f"Likelihood provider {selected_res.provider_name!r} returned invalid "
                        f"bounds [{lo_rat}, {hi_rat}]: must satisfy 0 <= lower <= upper <= 1"
                    )
                interval_str = [format_rational(lo_rat), format_rational(hi_rat)]

                if prefix not in added_to_table:
                    bounds_records.append(
                        {
                            "prefix": list(prefix),
                            "lower": interval_str[0],
                            "upper": interval_str[1],
                            "basis_category": selected_res.basis_category
                            or BasisClassification.SYNTHETIC_TEST_ONLY,
                            "rationale": selected_res.reason_detail or "Resolved by provider",
                            "rating_audit": _rating_audit(selected_res, lookup_key, query_meta),
                        }
                    )
                    added_to_table.add(prefix)

                p_coverage[prefix_key_str] = {
                    "prefix": list(prefix),
                    "outcome_unit": outcome_unit,
                    "disposition": ResolverDisposition.RATED,
                    "interval": interval_str,
                    "reason_code": selected_res.reason_code,
                    "reason_detail": selected_res.reason_detail,
                    "selected_provider": selected_res.provider_name,
                    "basis_category": selected_res.basis_category,
                    "rating_audit": _rating_audit(selected_res, lookup_key, query_meta),
                    "provider_trace": trace,
                    "affected_candidates": sorted(p_info["candidate_ids"]),
                }
            else:
                disposition = (
                    selected_res.disposition if selected_res else ResolverDisposition.UNRATED
                )
                reason_code = (
                    selected_res.reason_code if selected_res else ReasonCode.MISSING_EVIDENCE
                )
                reason_detail = (
                    selected_res.reason_detail
                    if selected_res
                    else "No provider resolved likelihood"
                )

                p_coverage[prefix_key_str] = {
                    "prefix": list(prefix),
                    "outcome_unit": outcome_unit,
                    "disposition": disposition,
                    "interval": None,
                    "reason_code": reason_code,
                    "reason_detail": reason_detail,
                    "selected_provider": selected_res.provider_name if selected_res else None,
                    "basis_category": None,
                    "rating_audit": _rating_audit(selected_res, lookup_key, query_meta),
                    "provider_trace": trace,
                    "affected_candidates": sorted(p_info["candidate_ids"]),
                }

        return p_coverage

    def _resolve_target_impact(
        self,
        target_asset_id: str,
        success_event: str,
        query_meta: dict[str, Any],
    ) -> dict[str, Any]:
        """Resolve impact rating for the target asset through provider chain."""
        lookup_key = generate_rating_lookup_key_i(
            target_asset_id=target_asset_id,
            success_event=success_event,
            consequence_scope=query_meta["work_boundary"],
            boundary=query_meta["work_boundary"],
            scenario_id=query_meta["scenario_id"],
            policy_id=query_meta.get("policy_id"),
            version=self.contract_version,
        )

        trace: list[dict[str, Any]] = []
        selected_res: ResolutionResult | None = None
        last_res: ResolutionResult | None = None

        for prov in self.impact_providers:
            res = prov.resolve_impact(lookup_key, target_asset_id, success_event, query_meta)
            trace.append(
                {
                    "provider": prov.name,
                    "rating_audit": _rating_audit(res, lookup_key, query_meta),
                    "disposition": str(res.disposition),
                    "reason_code": str(res.reason_code),
                    "reason_detail": res.reason_detail,
                }
            )
            last_res = res

            if res.disposition == ResolverDisposition.RATED:
                selected_res = res
                break
            if res.disposition in (ResolverDisposition.REFUSED, ResolverDisposition.CONFLICTING):
                selected_res = res
                break

        if selected_res is None:
            selected_res = last_res

        if selected_res is not None and selected_res.disposition == ResolverDisposition.RATED:
            rating_val = str(selected_res.value)
            if rating_val not in IMPACT_ORDINAL:
                raise RankingValidationError(
                    f"Impact provider {selected_res.provider_name!r} returned invalid rating "
                    f"{rating_val!r}: must be one of {list(IMPACT_ORDINAL.keys())}"
                )
            return {
                "target_asset_id": target_asset_id,
                "success_event": success_event,
                "disposition": ResolverDisposition.RATED,
                "consequence_rating": rating_val,
                "reason_code": selected_res.reason_code,
                "reason_detail": selected_res.reason_detail,
                "selected_provider": selected_res.provider_name,
                "basis_category": selected_res.basis_category,
                "rating_audit": _rating_audit(selected_res, lookup_key, query_meta),
                "provider_trace": trace,
            }

        disposition = selected_res.disposition if selected_res else ResolverDisposition.UNRATED
        reason_code = selected_res.reason_code if selected_res else ReasonCode.MISSING_EVIDENCE
        reason_detail = (
            selected_res.reason_detail if selected_res else "No provider resolved impact"
        )

        return {
            "target_asset_id": target_asset_id,
            "success_event": success_event,
            "disposition": disposition,
            "consequence_rating": None,
            "reason_code": reason_code,
            "reason_detail": reason_detail,
            "selected_provider": selected_res.provider_name if selected_res else None,
            "basis_category": None,
            "rating_audit": _rating_audit(selected_res, lookup_key, query_meta),
            "provider_trace": trace,
        }

    def _ensure_predicate_layers(
        self,
        layers: dict[str, int],
        bound_actions: Sequence[dict[str, Any]],
        target_goal: dict[str, Any],
    ) -> None:
        """Ensure all referenced action and goal predicates have authoritative layers."""
        referenced = set(target_goal.get("required_predicates", []))
        for act in bound_actions:
            referenced.update(act.get("requires", []))
            referenced.update(act.get("adds", []))
        missing = sorted(referenced - layers.keys())
        if missing:
            raise RankingValidationError(
                "Missing authoritative predicate layers: " + ", ".join(missing)
            )

    # -----------------------------------------------------------------------
    # Machine-Readable Coverage Schema Builder
    # -----------------------------------------------------------------------

    def _build_coverage_report(
        self,
        *,
        query_meta: dict[str, Any],
        parsed_candidates: list[dict[str, Any]],
        c_coverage: dict[str, Any],
        p_coverage: dict[str, Any],
        i_coverage: dict[str, Any],
    ) -> dict[str, Any]:
        """Construct comprehensive machine-readable rating coverage report."""
        unresolved_gaps: list[dict[str, Any]] = []
        candidate_reports: dict[str, Any] = {}
        candidate_summaries: dict[str, Any] = {}

        fully_rated_count = 0
        partially_rated_count = 0
        unrated_count = 0

        # Build per-candidate coverage
        for p_cand in parsed_candidates:
            cid = p_cand["candidate_id"]
            is_zero = p_cand["is_zero_action"]

            # Effort coverage for this candidate
            cand_units = list(p_cand["active_work_program"])
            cand_c_units = {u: c_coverage[u] for u in cand_units if u in c_coverage}
            c_gaps = [
                u
                for u, rec in cand_c_units.items()
                if rec["disposition"] != ResolverDisposition.RATED
            ]
            c_complete = len(c_gaps) == 0 if cand_units else True

            # Likelihood coverage for this candidate
            cand_p_entries: list[dict[str, Any]] = []
            p_gaps: list[dict[str, Any]] = []

            if is_zero:
                p_complete = True
            else:
                program = p_cand["active_work_program"]
                for length in range(1, len(program) + 1):
                    prefix = program[:length]
                    key_str = json.dumps(list(prefix))
                    rec = p_coverage.get(key_str)
                    if rec:
                        cand_p_entries.append(rec)
                        if rec["disposition"] != ResolverDisposition.RATED:
                            p_gaps.append(rec)
                p_complete = len(p_gaps) == 0

            i_complete = i_coverage["disposition"] == ResolverDisposition.RATED

            # Candidate eligibility
            if c_complete and p_complete and i_complete:
                eligibility = "eligible"
                fully_rated_count += 1
            elif not c_complete and not p_complete and not i_complete:
                eligibility = "ineligible_unrated"
                unrated_count += 1
            else:
                eligibility = "ineligible_partially_unrated"
                partially_rated_count += 1

            candidate_reports[cid] = {
                "candidate_id": cid,
                "is_zero_action": is_zero,
                "rating_eligibility": eligibility,
                "effort": {
                    "all_rated": c_complete,
                    "total_units": len(cand_units),
                    "rated_units": len(cand_units) - len(c_gaps),
                    "unrated_units": len(c_gaps),
                    "units": cand_c_units,
                    "gaps": c_gaps,
                },
                "likelihood": {
                    "all_rated": p_complete,
                    "total_prefixes": len(cand_p_entries),
                    "rated_prefixes": len(cand_p_entries) - len(p_gaps),
                    "unrated_prefixes": len(p_gaps),
                    "prefixes": cand_p_entries,
                    "gaps": p_gaps,
                },
                "impact": i_coverage,
            }

            candidate_summaries[cid] = {
                "c_complete": c_complete,
                "p_complete": p_complete,
                "i_complete": i_complete,
                "eligibility": eligibility,
            }

        # Collect global unresolved gaps (reporting ALL gaps, never stopping at first!)
        for u, rec in c_coverage.items():
            if rec["disposition"] != ResolverDisposition.RATED:
                unresolved_gaps.append(
                    {
                        "dimension": "C",
                        "target_id": u,
                        "disposition": str(rec["disposition"]),
                        "reason_code": str(rec["reason_code"]),
                        "reason_detail": rec.get("reason_detail", ""),
                        "provider_trace": rec.get("provider_trace", []),
                    }
                )

        for key_str, rec in p_coverage.items():
            if rec["disposition"] != ResolverDisposition.RATED:
                unresolved_gaps.append(
                    {
                        "dimension": "P",
                        "target_id": key_str,
                        "prefix": rec["prefix"],
                        "outcome_unit": rec["outcome_unit"],
                        "disposition": str(rec["disposition"]),
                        "reason_code": str(rec["reason_code"]),
                        "reason_detail": rec.get("reason_detail", ""),
                        "affected_candidates": rec.get("affected_candidates", []),
                        "provider_trace": rec.get("provider_trace", []),
                    }
                )

        if i_coverage["disposition"] != ResolverDisposition.RATED:
            unresolved_gaps.append(
                {
                    "dimension": "I",
                    "target_id": i_coverage["target_asset_id"],
                    "success_event": i_coverage["success_event"],
                    "disposition": str(i_coverage["disposition"]),
                    "reason_code": str(i_coverage["reason_code"]),
                    "reason_detail": i_coverage.get("reason_detail", ""),
                    "provider_trace": i_coverage.get("provider_trace", []),
                }
            )

        attempted_provs = sorted(
            {p.name for p in self.effort_providers}
            | {p.name for p in self.likelihood_providers}
            | {p.name for p in self.impact_providers}
        )

        return {
            "coverage_version": self.contract_version,
            "query_id": query_meta["query_id"],
            "scenario_id": query_meta["scenario_id"],
            "snapshot_id": query_meta["snapshot_id"],
            "providers_attempted": attempted_provs,
            "aggregate_summary": {
                "total_candidates": len(parsed_candidates),
                "fully_rated_candidates": fully_rated_count,
                "partially_rated_candidates": partially_rated_count,
                "unrated_candidates": unrated_count,
                "total_unresolved_gaps": len(unresolved_gaps),
            },
            "candidate_summaries": candidate_summaries,
            "candidates": candidate_reports,
            "unresolved_gaps": unresolved_gaps,
        }


# ---------------------------------------------------------------------------
# Re-exports from Effort Registry (Issue #247 via PEP 562 lazy module lookup)
# ---------------------------------------------------------------------------

_EFFORT_REGISTRY_EXPORTS = {
    "ApplicabilityMatchResult",
    "ClassApplicability",
    "ReviewedWorkUnitClassEffortProvider",
    "WorkUnitClass",
    "WorkUnitClassRegistry",
    "get_default_work_unit_registry",
}


def __getattr__(name: str) -> Any:
    if name in _EFFORT_REGISTRY_EXPORTS:
        import src.engine.ranking.effort_registry as _er

        return getattr(_er, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    return sorted(list(globals().keys()) + list(_EFFORT_REGISTRY_EXPORTS))
