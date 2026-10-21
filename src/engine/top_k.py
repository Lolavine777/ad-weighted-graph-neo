"""Select effort Top-K from canonical whole-program assessments; never rescore."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from src.engine.program_identity import program_id, program_key
from src.engine.semantics.transitions import Status

IDENTITY_POLICY = "attack-program-identity/1"
TIE_POLICY = "effort_then_canonical_program_key/1"


def validate_k(k: Any) -> None:
    if type(k) is not int or k < 1:
        raise ValueError("top_k must be a positive integer (boolean is not an integer K)")


def collect_assessments(result: Any) -> dict[str, dict[str, Any]]:
    ranking = result.ranking_result or {}
    assessments = dict(ranking.get("eligible_candidates", {}))
    for cid, diagnostic in ranking.get("diagnostics", {}).items():
        if isinstance(diagnostic, dict) and isinstance(diagnostic.get("assessment"), dict):
            assessments[cid] = diagnostic["assessment"]
    return assessments


def effort_programs(result: Any) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Return distinct feasible C-rated programs, including P/I-unrated ones."""
    assessments = collect_assessments(result)
    programs: dict[str, dict[str, Any]] = {}
    exclusions: list[dict[str, Any]] = []
    for index, path in enumerate(result.paths, 1):
        cid = f"generated_{index:04d}"
        key = program_key(path)
        assessment = assessments.get(cid)
        if not path.transition_history:
            effort = 0
            assessment = None
        elif assessment is None or assessment.get("status") not in {
            "feasible",
            "infeasible",
            "blocked",
        }:
            exclusions.append(
                {
                    "candidate_id": cid,
                    "reason": "unassessed_or_rejected",
                    "diagnostic": deepcopy(result.binding_diagnostics.get(cid)),
                }
            )
            continue
        elif assessment["status"] in {"infeasible", "blocked"}:
            exclusions.append({"candidate_id": cid, "reason": "assessment_infeasible"})
            continue
        elif assessment.get("effort_status") != "rated" or assessment.get("effort") is None:
            exclusions.append(
                {
                    "candidate_id": cid,
                    "reason": "effort_unrated",
                    "unrated_work_units": deepcopy(assessment.get("unrated_work_units", [])),
                    "diagnostic": {
                        "reasons": deepcopy(assessment.get("diagnostic_reasons", [])),
                        "work_unit_basis": deepcopy(assessment.get("work_unit_basis", {})),
                    },
                }
            )
            continue
        else:
            effort = assessment["effort"]
        if key in programs:
            if programs[key]["effort"] != effort:
                raise ValueError("Equivalent programs have inconsistent effort assessments")
            programs[key]["duplicate_candidate_ids"].append(cid)
            continue
        programs[key] = {
            "candidate_id": cid,
            "duplicate_candidate_ids": [],
            "program_id": program_id(key),
            "program_key": key,
            "effort": effort,
            "work_unit_ids": deepcopy(assessment.get("program", [])) if assessment else [],
            "work_unit_ledger": deepcopy(assessment.get("work_unit_basis", {}))
            if assessment
            else {},
            "likelihood_interval": deepcopy(assessment.get("likelihood_interval"))
            if assessment
            else None,
            "impact": assessment.get("impact") if assessment else None,
            "disposition": "assessed" if assessment else "semantic_initial_goal_zero_work",
        }
    return sorted(programs.values(), key=lambda p: (p["effort"], p["program_key"])), exclusions


def select_top_k(result: Any, k: int) -> dict[str, Any]:
    validate_k(k)
    programs, exclusions = effort_programs(result)
    selected = programs[:k]
    ranking = result.ranking_result or {}
    reasons = []
    if result.truncated or not result.complete:
        reasons.append("search_incomplete")
    if any(a.status is Status.INDETERMINATE for a in result.attempts):
        reasons.append("indeterminate_transitions")
    if ranking.get("search_metadata", {}).get("is_truncated"):
        reasons.append("assessment_incomplete")
    if any(e["reason"] == "unassessed_or_rejected" for e in exclusions):
        reasons.append("binding_or_assessment_gap")
    if any(e["reason"] == "effort_unrated" for e in exclusions):
        reasons.append("effort_rating_gap")
    exact = not reasons
    cutoff = selected[-1]["effort"] if selected else None
    tied = [p for p in programs if p["effort"] == cutoff] if cutoff is not None else []
    return {
        "version": "effort-top-k/1.0.0",
        "objective": "unique_active_work_unit_effort_C",
        "requested_k": k,
        "returned_count": len(selected),
        "program_identity_policy": IDENTITY_POLICY,
        "tie_policy": TIE_POLICY,
        "programs": selected,
        "boundary_ties": {
            "effort": cutoff,
            "observed_count": len(tied),
            "omitted_count": sum(p not in selected for p in tied),
            "complete": exact,
        },
        "coverage": {
            "generated_count": len(result.paths),
            "bound_count": ranking.get("search_audit", {}).get("generated_candidates_bound", 0),
            "assessed_count": len(collect_assessments(result)),
            "effort_rated_count": sum(1 + len(p["duplicate_candidate_ids"]) for p in programs),
            "eligible_distinct_count": len(programs),
            "duplicate_count": sum(len(p["duplicate_candidate_ids"]) for p in programs),
            "exclusions": exclusions,
            "search_complete": result.complete,
            "truncated": result.truncated,
            "truncation_reason": result.truncation_reason,
            "caps": result.caps,
            "assessment_search_metadata": deepcopy(ranking.get("search_metadata")),
        },
        "guarantee": {
            "kind": "exact_k_best_within_scope" if exact else "best_in_eligible_subset",
            "is_k_best_proven": exact,
            "fewer_than_k_proven": exact and len(programs) < k,
            "no_path_proven": result.is_no_path_proven_over_scope,
            "reasons": reasons,
            "scope": "declared query, supported first-goal programs and assessment work budget",
        },
    }
