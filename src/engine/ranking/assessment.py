"""Candidate program assessment: likelihood, effort, impact, and diagnostic partitioning.

Implements exact whole-path assessment according to Specification v1.0.0 and ADR-0013:
- Exact Fraction arithmetic for prefix conditional likelihood bounds (no float rounding).
- Full prefix traversal; no marginal fallback or independence assumptions.
- Canonical persistent work unit deduplication (shared preparation counted once).
- Unresolved work unit overlap keeps cost null and effort_status unrated.
- Target impact consequence rating bound to target asset and success event.
- Exhaustive diagnostic partitioning preserving all failure reasons.
"""

from __future__ import annotations

from copy import deepcopy
from fractions import Fraction
from typing import Any

from src.engine.ranking.models import IMPACT_ORDINAL, RankingValidationError
from src.engine.ranking.replay import replay_candidate_sequence


def assess_candidate_program(
    decoded_query: dict[str, Any],
    candidate_envelope: dict[str, Any],
    *,
    semantic_binding=None,
) -> dict[str, Any]:
    """Assess a candidate attack program against query constraints."""
    # 1. Replay candidate action sequence up to goal first-hitting time
    replayed = replay_candidate_sequence(
        decoded_query, candidate_envelope, semantic_binding=semantic_binding
    )

    candidate_id = replayed["candidate_id"]
    bound_action_ids = replayed["bound_action_ids"]
    target_asset_id = replayed["target_asset_id"]
    structural_routes = replayed["structural_routes"]
    gate_status = replayed["gate_status"]
    gates_eval = replayed["gates_evaluation"]
    impact = replayed["impact"]
    impact_status = replayed["impact_status"]
    work_packets = replayed["work_packets"]

    # 2. Derive canonical active work units program (deduplicated persistent units)
    program = tuple(dict.fromkeys(u for packet in work_packets for u in packet))

    # 3. Active work budget check on effective work units
    budget_limit = decoded_query["query_metadata"]["active_work_budget"]
    budget_exceeded = len(program) > budget_limit
    if budget_exceeded:
        gate_status = "blocked"
        gates_eval["active_work_budget"] = "budget_exceeded"

    # 4. Work units evaluation via normalized work_units_ledger
    ledger = decoded_query["work_units_ledger"]
    unrated_units: list[str] = []
    nominal_total = 0
    all_units_rated = True

    for u in program:
        if u not in ledger:
            raise RankingValidationError(
                f"Candidate {candidate_id} references unknown work unit: {u!r}"
            )
        rec = ledger[u]
        is_unit_rated = (
            rec.get("rating_status") == "rated"
            and rec.get("overlap_state") != "unresolved_overlap"
            and rec.get("computed_cost") is not None
        )
        if is_unit_rated:
            nominal_total += rec["computed_cost"]
        else:
            unrated_units.append(u)
            all_units_rated = False

    nominal_effort = nominal_total if all_units_rated else None
    effort = nominal_effort if gate_status == "feasible" else None
    effort_status = (
        "ineligible"
        if gate_status != "feasible"
        else ("unrated" if not all_units_rated else "rated")
    )

    # 5. Exact Fraction conditional bounds calculation
    bounds_table = decoded_query["conditional_bounds_table"]
    bounds_records = {
        tuple(record["prefix"]): record
        for record in decoded_query.get("conditional_bounds_records", [])
    }
    conditional_bounds_basis: list[dict[str, Any]] = []
    lower = upper = Fraction(1, 1)
    likelihood_rated = True

    for length in range(1, len(program) + 1):
        prefix = program[:length]
        interval = bounds_table.get(prefix)
        if interval is None:
            likelihood_rated = False
            break
        lo, hi = interval
        if prefix in bounds_records:
            conditional_bounds_basis.append(deepcopy(bounds_records[prefix]))
        lower *= lo
        upper *= hi
        if upper == 0:
            likelihood_rated = True
            break

    # Likelihood is withheld if candidate execution is blocked or unknown
    if gate_status == "feasible" and likelihood_rated:
        likelihood_interval: tuple[Fraction, Fraction] | None = (lower, upper)
    else:
        likelihood_interval = None

    if likelihood_interval is not None:
        likelihood_basis_summary = "Derived from prefix conditional bounds product"
    elif budget_exceeded:
        likelihood_basis_summary = "Withheld: candidate active work units exceed budget_limit"
    elif gate_status == "blocked":
        likelihood_basis_summary = "Withheld: candidate execution is blocked by predicate gating"
    elif gate_status == "unknown":
        likelihood_basis_summary = "Withheld: candidate execution gate status is unknown"
    else:
        likelihood_basis_summary = "Withheld: missing conditional prefix bounds in table"

    basis_details = [
        f"{record['prefix']!r}: {record.get('basis_category', 'unspecified')} — "
        f"{record.get('rationale', 'No rationale supplied')}"
        for record in conditional_bounds_basis
        if "basis_category" in record or "rationale" in record
    ]
    if basis_details:
        likelihood_basis_summary += "; " + "; ".join(basis_details)

    # 6. Authoritative risk ineligibility diagnostic reasons
    reasons: list[str] = []
    if gate_status != "feasible":
        reasons.append("blocked" if gate_status == "blocked" else "unknown")
    if likelihood_interval is None:
        reasons.append("likelihood_unrated")
    if impact is None or impact not in IMPACT_ORDINAL:
        reasons.append("impact_unrated")
    if budget_exceeded:
        reasons.append("work_budget_exceeded")

    return {
        "candidate_id": candidate_id,
        "bound_action_ids": bound_action_ids,
        "target_asset_id": target_asset_id,
        "program": list(program),
        "structural_routes": structural_routes,
        "status": gate_status,
        "gates_evaluation": gates_eval,
        "nominal_effort": nominal_effort,
        "effort": effort,
        "effort_status": effort_status,
        "unrated_work_units": unrated_units,
        "work_unit_basis": {unit: deepcopy(ledger[unit]) for unit in program},
        "impact": impact,
        "consequence_rating": impact,
        "impact_status": impact_status,
        "likelihood_interval": likelihood_interval,
        "likelihood_status": "rated" if likelihood_interval is not None else "unrated",
        "likelihood_basis_summary": likelihood_basis_summary,
        "conditional_bounds_basis": conditional_bounds_basis,
        "diagnostic_reasons": reasons,
    }
