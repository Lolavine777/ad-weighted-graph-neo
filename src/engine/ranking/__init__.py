"""Path Ranking and Evaluation Engine Boundary (Specification v1.0.0).

Provides the versioned engine-side boundary for candidate attack path ranking,
conservative Pareto frontier extraction, and separate Min-Effort-to-DA baseline evaluation.
"""

from __future__ import annotations

import json
from fractions import Fraction
from typing import Any

from src.engine.ranking.adapter_145 import (
    PathResultProtocol,
    TransitionStepProtocol,
    adapt_search_candidate,
    convert_path_result_to_candidate_envelope,
)
from src.engine.ranking.assessment import assess_candidate_program
from src.engine.ranking.facts import evaluate_predicate_gates, resolve_facts_ledger
from src.engine.ranking.frontier import (
    compute_min_effort_baseline,
    risk_ineligibility,
    scoped_frontier,
    scoped_preference,
)
from src.engine.ranking.models import (
    CANONICAL_EDGE_ID_PATTERN,
    CANONICAL_GUID_PATTERN,
    CANONICAL_SCOPED_SID_PATTERN,
    CANONICAL_SID_PATTERN,
    IMPACT_ORDINAL,
    REQUIRED_SCOPE_BINDING_FIELDS,
    SCOPE_REQUIRED_SID_PATTERN,
    SNAPSHOT_ID_PATTERN,
    CompletenessScope,
    ConsequenceRating,
    DuplicatePrefixError,
    EffortStatus,
    EvaluationMode,
    GateStatus,
    MappingSyncError,
    RankingEngineError,
    RankingValidationError,
    ScopedPreferenceVerdict,
    format_rational,
    is_canonical_edge_id,
    is_canonical_node_id,
    parse_rational,
)
from src.engine.ranking.replay import replay_candidate_sequence
from src.engine.ranking.validation import (
    VALID_COMPLETENESS_SCOPES,
    VALID_TRUNCATION_REASONS,
    decode_ranking_query,
    validate_and_decode_bounds_table,
    validate_authoritative_predicate_layers,
    validate_bound_actions,
    validate_candidate_envelope,
    validate_candidate_envelopes,
    validate_query_metadata,
    validate_scope_binding,
    validate_target_impact_assessments,
    validate_upstream_coverage,
    validate_work_units_ledger,
)


def encode_ranking_result(result: dict[str, Any]) -> str:
    """Encode PathRankingResult dictionary into lossless JSON wire payload."""

    def sanitize(obj: Any) -> Any:
        if isinstance(obj, Fraction):
            return format_rational(obj)
        if isinstance(obj, tuple):
            return [sanitize(x) for x in obj]
        if isinstance(obj, list):
            return [sanitize(x) for x in obj]
        if isinstance(obj, dict):
            return {k: sanitize(v) for k, v in obj.items()}
        return obj

    sanitized = sanitize(result)
    return json.dumps(sanitized, indent=2, ensure_ascii=False)


def execute_ranking_roundtrip(
    query_payload: str | dict[str, Any],
    candidates: list[dict[str, Any]],
    upstream_coverage: dict[str, Any] | None = None,
    *,
    semantic_bindings=None,
) -> dict[str, Any]:
    """Execute full ranking roundtrip:
    decode -> validate envelopes -> assess -> frontier -> encode -> decode.
    """
    decoded = decode_ranking_query(query_payload)
    validated_candidates = validate_candidate_envelopes(
        candidates, decoded, semantic_bindings=semantic_bindings
    )
    assessed_candidates = [
        assess_candidate_program(
            decoded, cand, semantic_binding=(semantic_bindings or {}).get(cand["candidate_id"])
        )
        for cand in validated_candidates
    ]

    candidates_by_name = {c["candidate_id"]: c for c in assessed_candidates}
    frontier_result = scoped_frontier(candidates_by_name)

    eligible_map = dict(frontier_result["eligible"])
    diagnostics_map = dict(frontier_result["diagnostics"])
    frontier_ids = list(frontier_result["frontier"])

    # Search metadata and coverage resolution (Spec 3.1)
    budget_limit = decoded["query_metadata"]["active_work_budget"]
    has_budget_exceeded = any(
        c.get("gates_evaluation", {}).get("active_work_budget") == "budget_exceeded"
        for c in assessed_candidates
    )

    raw_coverage = (
        upstream_coverage
        if upstream_coverage is not None
        else decoded["query_metadata"].get("coverage")
    )
    upstream_cov = validate_upstream_coverage(raw_coverage) if raw_coverage is not None else None
    upstream_caps: dict[str, Any] = {}
    if upstream_cov is not None and isinstance(upstream_cov.get("caps_applied"), dict):
        upstream_caps = upstream_cov["caps_applied"]

    if upstream_cov is not None:
        completeness_scope = upstream_cov.get(
            "completeness_scope", CompletenessScope.UNSPECIFIED_SUBSET
        )
        is_truncated = bool(upstream_cov.get("is_truncated", False)) or has_budget_exceeded
        truncation_reasons = list(upstream_cov.get("truncation_reasons", []))
        if has_budget_exceeded and "work_budget_exceeded" not in truncation_reasons:
            truncation_reasons.append("work_budget_exceeded")
        if is_truncated:
            completeness_scope = CompletenessScope.PARTIAL_TRUNCATED
    else:
        if has_budget_exceeded:
            is_truncated = True
            truncation_reasons = ["work_budget_exceeded"]
            completeness_scope = CompletenessScope.PARTIAL_TRUNCATED
        else:
            is_truncated = False
            truncation_reasons = []
            completeness_scope = CompletenessScope.UNSPECIFIED_SUBSET

    canonical_caps = {
        "max_active_work_budget": (
            min(budget_limit, upstream_caps["max_active_work_budget"])
            if isinstance(upstream_caps.get("max_active_work_budget"), int)
            else budget_limit
        ),
        "max_candidates": upstream_caps.get("max_candidates"),
        "timeout_ms": upstream_caps.get("timeout_ms"),
        "max_expansions": upstream_caps.get("max_expansions"),
    }
    if "max_steps" in upstream_caps:
        canonical_caps["max_steps"] = upstream_caps["max_steps"]

    search_meta = {
        "budget_limit": budget_limit,
        "candidates_evaluated": len(assessed_candidates),
        "is_truncated": is_truncated,
        "truncation_reasons": truncation_reasons,
        "caps_applied": canonical_caps,
        "completeness_scope": completeness_scope,
        "search_algorithm": "provided_candidate_assessment",
    }

    baseline = compute_min_effort_baseline(
        assessed_candidates=assessed_candidates,
        target_goal=decoded["query_metadata"].get("target_goal", {}),
        is_truncated=is_truncated,
        truncation_reasons=truncation_reasons,
        completeness_scope=completeness_scope,
        caps_applied=(search_meta["caps_applied"] if upstream_cov is not None else None),
    )

    result_payload = {
        "query_id": decoded["query_metadata"]["query_id"],
        "version": "1.0.0",
        "parameter_audit": decoded["parameter_audit"],
        "search_metadata": search_meta,
        "eligible_candidates": eligible_map,
        "pareto_frontier": frontier_ids,
        "diagnostics": diagnostics_map,
        "min_effort_to_da_baseline": baseline,
    }

    encoded_json = encode_ranking_result(result_payload)
    roundtrip_result = json.loads(encoded_json)

    return {
        "decoded_query": decoded,
        "assessed_candidates": assessed_candidates,
        "result_payload": result_payload,
        "encoded_json": encoded_json,
        "roundtrip_result": roundtrip_result,
    }


class PathRankingEngine:
    """Versioned engine orchestrator for whole-path evaluation and ranking (v1.0.0)."""

    def __init__(self, version: str = "1.0.0") -> None:
        if version != "1.0.0":
            raise RankingValidationError(f"Unsupported engine ranking version: {version}")
        self.version = version

    def evaluate(
        self,
        query_payload: str | dict[str, Any],
        candidates: list[dict[str, Any]],
        upstream_coverage: dict[str, Any] | None = None,
        *,
        semantic_bindings=None,
    ) -> dict[str, Any]:
        """Evaluate and rank explicit candidate envelopes against a PathRankingQuery."""
        return execute_ranking_roundtrip(
            query_payload, candidates, upstream_coverage, semantic_bindings=semantic_bindings
        )


__all__ = [
    "CANONICAL_EDGE_ID_PATTERN",
    "CANONICAL_GUID_PATTERN",
    "CANONICAL_SCOPED_SID_PATTERN",
    "CANONICAL_SID_PATTERN",
    "IMPACT_ORDINAL",
    "REQUIRED_SCOPE_BINDING_FIELDS",
    "SCOPE_REQUIRED_SID_PATTERN",
    "SNAPSHOT_ID_PATTERN",
    "CompletenessScope",
    "ConsequenceRating",
    "DuplicatePrefixError",
    "EffortStatus",
    "EvaluationMode",
    "GateStatus",
    "MappingSyncError",
    "PathRankingEngine",
    "PathResultProtocol",
    "RankingEngineError",
    "RankingValidationError",
    "ScopedPreferenceVerdict",
    "TransitionStepProtocol",
    "assess_candidate_program",
    "compute_min_effort_baseline",
    "convert_path_result_to_candidate_envelope",
    "adapt_search_candidate",
    "decode_ranking_query",
    "encode_ranking_result",
    "evaluate_predicate_gates",
    "execute_ranking_roundtrip",
    "format_rational",
    "is_canonical_edge_id",
    "is_canonical_node_id",
    "parse_rational",
    "replay_candidate_sequence",
    "resolve_facts_ledger",
    "risk_ineligibility",
    "scoped_frontier",
    "scoped_preference",
    "VALID_COMPLETENESS_SCOPES",
    "VALID_TRUNCATION_REASONS",
    "validate_and_decode_bounds_table",
    "validate_authoritative_predicate_layers",
    "validate_bound_actions",
    "validate_candidate_envelope",
    "validate_candidate_envelopes",
    "validate_query_metadata",
    "validate_scope_binding",
    "validate_target_impact_assessments",
    "validate_upstream_coverage",
    "validate_work_units_ledger",
]
