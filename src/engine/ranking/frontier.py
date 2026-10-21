"""Conservative Pareto frontier and separate Min-Effort-to-DA baseline.

Implements conservative partial-order dominance according to ADR-0013 and Specification v1.0.0:
- Compares risk-eligible candidates within the same fixed query scope.
- Two independent risk axes: Target Business Impact (I) and Conditional Likelihood Interval [l, u].
- A dominates B iff (I_A >= I_B and l_A >= u_B) with at least one strict inequality.
- Overlapping intervals remain incomparable.
- Conditional effort tie-break ONLY when: same impact, same exact point likelihood, both rated.
- Separate Min-Effort-to-DA query baseline with explicit coverage and truncation disclosure.
"""

from __future__ import annotations

from typing import Any

from src.engine.ranking.models import IMPACT_ORDINAL, ScopedPreferenceVerdict


def risk_ineligibility(assessment: dict[str, Any]) -> list[str]:
    """Return reasons why a candidate assessment is ineligible for risk ranking."""
    reasons: list[str] = list(assessment.get("diagnostic_reasons", []))
    if not reasons:
        status = assessment.get("status", "unknown")
        if status != "feasible":
            reasons.append("blocked" if status == "blocked" else "unknown")
        if assessment.get("likelihood_interval") is None:
            reasons.append("likelihood_unrated")
        impact = assessment.get("impact")
        if not isinstance(impact, str) or impact not in IMPACT_ORDINAL:
            reasons.append("impact_unrated")
    return sorted(dict.fromkeys(reasons))


def scoped_preference(a: dict[str, Any], b: dict[str, Any]) -> str:
    """Evaluate conservative Pareto preference between two candidate assessments.

    Returns:
    - 'a': Candidate A strictly dominates B.
    - 'b': Candidate B strictly dominates A.
    - 'tie': Candidates have identical impact, identical point likelihood, and identical effort.
    - 'incomparable': Candidates have non-dominating trade-offs or overlapping intervals.
    - 'not_eligible': One or both candidates are ineligible for risk comparison.
    """
    if risk_ineligibility(a) or risk_ineligibility(b):
        return ScopedPreferenceVerdict.NOT_ELIGIBLE

    ia = IMPACT_ORDINAL[a["impact"]]
    ib = IMPACT_ORDINAL[b["impact"]]
    la, ua = a["likelihood_interval"]
    lb, ub = b["likelihood_interval"]

    # Conditional effort tie-break: only for identical impact and identical point likelihood
    if ia == ib and la == ua == lb == ub:
        if (
            a.get("effort_status") != "rated"
            or b.get("effort_status") != "rated"
            or a.get("effort") is None
            or b.get("effort") is None
        ):
            return ScopedPreferenceVerdict.INCOMPARABLE
        if a["effort"] < b["effort"]:
            return ScopedPreferenceVerdict.A
        if b["effort"] < a["effort"]:
            return ScopedPreferenceVerdict.B
        return ScopedPreferenceVerdict.TIE

    # Conservative Pareto dominance
    if ia >= ib and la >= ub and (ia > ib or la > ub):
        return ScopedPreferenceVerdict.A
    if ib >= ia and lb >= ua and (ib > ia or lb > ua):
        return ScopedPreferenceVerdict.B

    return ScopedPreferenceVerdict.INCOMPARABLE


def scoped_frontier(candidates: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Partition candidates into eligible and diagnostics, and extract Pareto frontier."""
    eligible: dict[str, dict[str, Any]] = {}
    diagnostics: dict[str, dict[str, Any]] = {}

    for name, assessment in candidates.items():
        reasons = risk_ineligibility(assessment)
        if reasons:
            diagnostics[name] = {"reasons": reasons, "assessment": assessment}
        else:
            eligible[name] = assessment

    frontier: list[str] = [
        name
        for name, assessment in eligible.items()
        if not any(
            scoped_preference(other, assessment) == ScopedPreferenceVerdict.A
            for other in eligible.values()
        )
    ]

    return {
        "eligible": eligible,
        "diagnostics": diagnostics,
        "frontier": sorted(frontier),
    }


def compute_min_effort_baseline(
    assessed_candidates: list[dict[str, Any]],
    target_goal: dict[str, Any],
    is_truncated: bool,
    truncation_reasons: list[str],
    completeness_scope: str,
    caps_applied: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Compute separate Min-Effort-to-DA baseline (Spec 3.4)."""
    feasible_rated = [
        c
        for c in assessed_candidates
        if c.get("status") == "feasible"
        and c.get("effort_status") == "rated"
        and c.get("effort") is not None
    ]
    goal_id = target_goal.get("goal_id", "target_goal")

    baseline_coverage = {
        "is_truncated": is_truncated,
        "truncation_reasons": list(truncation_reasons),
        "completeness_scope": completeness_scope,
    }
    if caps_applied is not None:
        baseline_coverage["caps_applied"] = dict(caps_applied)

    if feasible_rated:
        best_cand = min(feasible_rated, key=lambda c: (c["effort"], c["candidate_id"]))
        return {
            "goal_id": goal_id,
            "best_candidate_id": best_cand["candidate_id"],
            "minimum_effort_value": best_cand["effort"],
            "associated_likelihood_interval": best_cand["likelihood_interval"],
            "associated_impact": best_cand["impact"],
            "coverage_disclosure": (
                "Baseline evaluated over candidate set within active work budget; "
                "does not guarantee global minimum if unrated work units or unvisited paths exist."
            ),
            "baseline_coverage": baseline_coverage,
        }
    else:
        return {
            "goal_id": goal_id,
            "best_candidate_id": None,
            "minimum_effort_value": None,
            "associated_likelihood_interval": None,
            "associated_impact": None,
            "coverage_disclosure": "No feasible rated candidate found in evaluated set.",
            "baseline_coverage": baseline_coverage,
        }
