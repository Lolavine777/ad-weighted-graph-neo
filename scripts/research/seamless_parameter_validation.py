"""Reproducible validation and sensitivity analysis for SEAMLESS parameter proposal.

Verifies exact rational calculation traces, conservative Pareto preference,
Min-Effort-to-DA baseline, and perturbation sensitivity across declared
research-assisted scenario parameters.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import sys
from fractions import Fraction
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.research.path_ranking_wire_adapter import (  # noqa: E402
    execute_ranking_roundtrip,
)
from src.engine.ranking import PathRankingEngine  # noqa: E402
from src.parser.cli import atomic_write  # noqa: E402

FIXTURES = ROOT / "tests" / "fixtures" / "ranking"

# Analytical expected values for Source A under proposed parameter basis
EXPECTED_CAND_1_LIKELIHOOD = (Fraction(42, 125), Fraction(171, 250))
EXPECTED_CAND_1_EFFORT = 2
EXPECTED_CAND_1_IMPACT = "High"

EXPECTED_CAND_2_LIKELIHOOD = (Fraction(126, 625), Fraction(55233, 100000))
EXPECTED_CAND_2_EFFORT = 3
EXPECTED_CAND_2_IMPACT = "High"

# Analytical expected values for Source B under proposed parameter basis
EXPECTED_CAND_B_LIKELIHOOD = (Fraction(42, 125), Fraction(171, 250))
EXPECTED_CAND_B_EFFORT = 2
EXPECTED_CAND_B_IMPACT = "High"


def compute_bundle_digest(bundle_payload: dict[str, Any]) -> str:
    """Compute deterministic SHA256 digest of parameter bundle."""
    bundle_copy = copy.deepcopy(bundle_payload)
    if "bundle_digest" in bundle_copy.get("bundle_metadata", {}):
        bundle_copy["bundle_metadata"]["bundle_digest"] = ""
    if "query_projections" in bundle_copy:
        for proj in bundle_copy["query_projections"].values():
            if isinstance(proj, dict) and "query" in proj:
                qmeta = proj["query"].get("query_metadata", {})
                if "bundle_digest" in qmeta:
                    qmeta["bundle_digest"] = ""
    raw_bytes = json.dumps(bundle_copy, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return f"sha256:{hashlib.sha256(raw_bytes).hexdigest()}"


def verify_parameter_bundle(bundle_payload: dict[str, Any]) -> dict[str, Any]:
    """Validate structure, completeness, governance commitments, and canonical engine execution."""
    meta = bundle_payload.get("bundle_metadata", {})
    required_meta = [
        "bundle_id",
        "bundle_version",
        "schema_version",
        "scenario_id",
        "scenario_version",
        "snapshot_id",
        "target_goal",
        "work_boundary",
        "horizon",
        "active_work_budget",
        "bundle_digest",
    ]
    missing_meta = [f for f in required_meta if f not in meta]
    if missing_meta:
        raise ValueError(f"Parameter bundle missing metadata fields: {missing_meta}")

    # Validate bundle_digest for canonical bundle 1.0.0
    declared_digest = meta.get("bundle_digest")
    if (
        not isinstance(declared_digest, str)
        or not declared_digest.startswith("sha256:")
        or len(declared_digest) != 71
    ):
        raise ValueError(
            f"Parameter bundle missing or invalid bundle_digest: {declared_digest!r}; "
            "canonical bundle 1.0.0 requires non-empty 'sha256:<64-hex>'"
        )
    expected_digest = compute_bundle_digest(bundle_payload)
    if declared_digest != expected_digest:
        raise ValueError(
            f"Bundle digest mismatch: declared {declared_digest}, expected {expected_digest}"
        )

    governance = bundle_payload.get("governance")
    if not isinstance(governance, dict):
        raise ValueError("Parameter bundle missing dictionary 'governance' object")
    required_gov_fields = [
        "status",
        "basis_category",
        "human_agreement_status",
        "empirical_calibration_status",
        "raters",
        "reconciliation",
    ]
    missing_gov = [f for f in required_gov_fields if f not in governance]
    if missing_gov:
        raise ValueError(f"Governance missing required fields: {missing_gov}")

    if governance.get("status") != "pending_independent_human_ratings":
        curr_status = governance.get("status")
        raise ValueError(
            f"Governance status must be 'pending_independent_human_ratings', got {curr_status}"
        )
    if governance.get("basis_category") != "research_assisted_scenario_hypotheses":
        raise ValueError(
            f"Governance basis_category must be 'research_assisted_scenario_hypotheses' "
            f"for pending research bundle, got {governance.get('basis_category')!r}"
        )
    if governance.get("human_agreement_status") != "pending":
        raise ValueError(
            f"Governance human_agreement_status must be 'pending' while pending human ratings, "
            f"got {governance.get('human_agreement_status')!r}"
        )
    calib_status = governance.get("empirical_calibration_status")
    if calib_status not in (None, "none"):
        raise ValueError(
            "Governance empirical_calibration_status must be 'none' (or null), "
            f"got {calib_status!r}"
        )
    if governance.get("raters") != []:
        raise ValueError("Governance raters must be empty list while pending human ratings")
    if governance.get("reconciliation") is not None:
        raise ValueError(
            f"Governance reconciliation must be null while pending human ratings, "
            f"got {governance.get('reconciliation')!r}"
        )

    # Validate work units ledger (must contain exactly 9 canonical units)
    ledger = bundle_payload.get("work_units_ledger", {})
    if len(ledger) != 9:
        raise ValueError(f"Work units ledger must contain exactly 9 units, got {len(ledger)}")
    for uid, unit in ledger.items():
        if unit.get("rating_status") != "rated":
            raise ValueError(f"Work unit {uid} must have rating_status 'rated'")
        if unit.get("overlap_state") != "independent":
            raise ValueError(
                f"Work unit {uid} must have canonical overlap_state 'independent', "
                f"got {unit.get('overlap_state')!r}"
            )
        rubric = unit.get("rubric_scores")
        if not rubric or rubric.get("computed_cost") not in range(5):
            raise ValueError(f"Work unit {uid} has invalid rubric cost: {rubric}")

    # Validate conditional bounds (must contain exactly 11 entries)
    bounds = bundle_payload.get("conditional_bounds_table", [])
    if len(bounds) != 11:
        raise ValueError(f"Conditional bounds table must have 11 rows, got {len(bounds)}")
    for row in bounds:
        l_frac = Fraction(row["lower"])
        u_frac = Fraction(row["upper"])
        if not (Fraction(0) <= l_frac <= u_frac <= Fraction(1)):
            raise ValueError(
                f"Invalid probability interval for prefix {row.get('prefix')}: [{l_frac}, {u_frac}]"
            )
        bound_fields = (
            "question_id",
            "outcome_action_id",
            "technical_source",
            "basis_category",
            "rationale",
        )
        for field in bound_fields:
            if not isinstance(row.get(field), str) or not row[field].strip():
                raise ValueError(
                    f"Conditional bound prefix {row.get('prefix')} missing non-empty '{field}'"
                )
        if not isinstance(row.get("applicable_queries"), list) or not row["applicable_queries"]:
            raise ValueError(
                f"Conditional bound prefix {row.get('prefix')} missing non-empty "
                "'applicable_queries'"
            )

    # Validate facts ledger
    facts = bundle_payload.get("facts_ledger", {})
    assumed = facts.get("assumed_facts", [])
    if len(assumed) != 26:
        raise ValueError(f"Assumed facts must contain 26 runtime hypotheses, got {len(assumed)}")
    observed = facts.get("observed_facts", [])
    if len(observed) != 14:
        raise ValueError(f"Observed facts must contain 14 items, got {len(observed)}")
    unknown = facts.get("unknown_facts", [])
    if len(unknown) != 2:
        raise ValueError(f"Unknown facts must contain 2 items, got {len(unknown)}")
    false_facts = facts.get("false_facts", [])
    if not isinstance(false_facts, list):
        raise ValueError(f"false_facts must be a list, got {type(false_facts).__name__}")
    for idx, ff in enumerate(false_facts):
        if not isinstance(ff, dict):
            raise ValueError(f"false_facts entry {idx} must be a dict")
        if not ff.get("predicate") or not isinstance(ff["predicate"], str):
            raise ValueError(f"false_facts entry {idx} predicate must be a non-empty string")
        if ff.get("truth_value") is not False:
            raise ValueError(
                f"false_facts entry {idx} truth_value must be False, got {ff.get('truth_value')!r}"
            )
        if not isinstance(ff.get("applicable_queries"), list) or not ff["applicable_queries"]:
            raise ValueError(f"false_facts entry {idx} missing non-empty 'applicable_queries'")
    pred_layers = facts.get("predicate_layers", {})
    if len(pred_layers) != 51:
        raise ValueError(f"Predicate layers must contain 51 items, got {len(pred_layers)}")

    # Validate actions and candidates
    actions = bundle_payload.get("bound_actions", [])
    if len(actions) != 12:
        raise ValueError(f"Bound actions must contain exactly 12 actions, got {len(actions)}")
    cands = bundle_payload.get("candidate_envelopes", [])
    if len(cands) != 3:
        raise ValueError(f"Candidate envelopes must contain exactly 3 candidates, got {len(cands)}")
    cand_ids = {c.get("candidate_id") for c in cands if isinstance(c, dict)}
    expected_cands = {
        "cand_seamless_01_direct_lidia",
        "cand_seamless_02_alt_vajer_ollie",
        "cand_seamless_source_b_01_ollie",
    }
    if cand_ids != expected_cands:
        raise ValueError(f"Candidate envelopes mismatch: expected {expected_cands}, got {cand_ids}")
    for c in cands:
        sb = c.get("scope_binding", {})
        if sb.get("snapshot_id") != meta["snapshot_id"]:
            raise ValueError(
                f"Candidate envelope {c.get('candidate_id')} scope_binding snapshot_id "
                f"{sb.get('snapshot_id')!r} does not match root bundle "
                f"snapshot_id {meta['snapshot_id']!r}"
            )
        if sb.get("work_boundary") != meta["work_boundary"]:
            raise ValueError(
                f"Candidate envelope {c.get('candidate_id')} scope_binding work_boundary "
                f"{sb.get('work_boundary')!r} does not match root bundle "
                f"work_boundary {meta['work_boundary']!r}"
            )
        if sb.get("horizon") != meta["horizon"]:
            raise ValueError(
                f"Candidate envelope {c.get('candidate_id')} scope_binding horizon "
                f"{sb.get('horizon')!r} does not match root bundle "
                f"horizon {meta['horizon']!r}"
            )

    # Validate query_projections consistency against independently derived projections
    if "query_projections" in bundle_payload:
        projections = bundle_payload["query_projections"]
        for src_name in ("source_a", "source_b"):
            if src_name not in projections:
                raise ValueError(f"Parameter bundle query_projections missing '{src_name}'")
            proj = projections[src_name]
            d_query, d_cands = derive_query_and_candidates_from_bundle(bundle_payload, src_name)
            if proj.get("query") != d_query:
                raise ValueError(
                    f"Query projection '{src_name}' query does not match authoritative root records"
                )
            if proj.get("candidates") != d_cands:
                raise ValueError(
                    f"Query projection '{src_name}' candidates do not match "
                    "authoritative root records"
                )
            proj_gov = proj.get("query", {}).get("query_metadata", {}).get("governance")
            if proj_gov != governance:
                raise ValueError(
                    f"Query projection '{src_name}' governance does not match root governance"
                )
            proj_digest = proj.get("query", {}).get("query_metadata", {}).get("bundle_digest")
            if proj_digest != declared_digest:
                raise ValueError(
                    f"Query projection '{src_name}' bundle_digest does not match "
                    "declared bundle_digest"
                )

    # Validate and execute BOTH Source A and Source B through canonical engine
    engine = PathRankingEngine(version="1.0.0")

    # Evaluate Source A
    query_a, cands_a = extract_query_and_candidates_from_bundle(bundle_payload, "source_a")
    res_a = engine.evaluate(query_a, cands_a)
    rt_a = res_a["roundtrip_result"]
    traces_a = verify_calculation_traces_source_a(rt_a)

    # Verify parameter_audit preservation for Source A
    audit_a = rt_a.get("parameter_audit", {})
    qmeta_a = audit_a.get("query_metadata", {})
    if qmeta_a.get("bundle_id") != meta["bundle_id"]:
        raise ValueError("Source A parameter_audit missing or mismatched bundle_id")
    if qmeta_a.get("bundle_version") != meta["bundle_version"]:
        raise ValueError("Source A parameter_audit missing or mismatched bundle_version")
    if qmeta_a.get("bundle_digest") != declared_digest:
        raise ValueError("Source A parameter_audit missing or mismatched bundle_digest")
    if qmeta_a.get("snapshot_id") != meta["snapshot_id"]:
        raise ValueError("Source A parameter_audit missing or mismatched snapshot_id")
    if qmeta_a.get("governance") != governance:
        raise ValueError("Source A parameter_audit missing or mismatched governance")
    if audit_a.get("conditional_bounds_table") != query_a["conditional_bounds_table"]:
        raise ValueError(
            "Source A parameter_audit did not preserve conditional_bounds_table references"
        )
    if audit_a.get("work_units_ledger") != query_a["work_units_ledger"]:
        raise ValueError("Source A parameter_audit did not preserve work_units_ledger references")

    # Evaluate Source B
    query_b, cands_b = extract_query_and_candidates_from_bundle(bundle_payload, "source_b")
    res_b = engine.evaluate(query_b, cands_b)
    rt_b = res_b["roundtrip_result"]
    traces_b = verify_calculation_traces_source_b(rt_b)

    # Verify parameter_audit preservation for Source B
    audit_b = rt_b.get("parameter_audit", {})
    qmeta_b = audit_b.get("query_metadata", {})
    if qmeta_b.get("bundle_id") != meta["bundle_id"]:
        raise ValueError("Source B parameter_audit missing or mismatched bundle_id")
    if qmeta_b.get("bundle_version") != meta["bundle_version"]:
        raise ValueError("Source B parameter_audit missing or mismatched bundle_version")
    if qmeta_b.get("bundle_digest") != declared_digest:
        raise ValueError("Source B parameter_audit missing or mismatched bundle_digest")
    if qmeta_b.get("snapshot_id") != meta["snapshot_id"]:
        raise ValueError("Source B parameter_audit missing or mismatched snapshot_id")
    if qmeta_b.get("governance") != governance:
        raise ValueError("Source B parameter_audit missing or mismatched governance")
    if audit_b.get("conditional_bounds_table") != query_b["conditional_bounds_table"]:
        raise ValueError(
            "Source B parameter_audit did not preserve conditional_bounds_table references"
        )
    if audit_b.get("work_units_ledger") != query_b["work_units_ledger"]:
        raise ValueError("Source B parameter_audit did not preserve work_units_ledger references")

    return {
        "status": "PASS",
        "bundle_id": meta["bundle_id"],
        "bundle_version": meta["bundle_version"],
        "bundle_digest": declared_digest,
        "scenario_id": meta["scenario_id"],
        "scenario_version": meta["scenario_version"],
        "snapshot_id": meta["snapshot_id"],
        "work_units_count": len(ledger),
        "conditional_bounds_count": len(bounds),
        "assumed_facts_count": len(assumed),
        "observed_facts_count": len(observed),
        "candidates_count": len(cands),
        "governance_status": governance["status"],
        "source_a_traces": traces_a,
        "source_b_traces": traces_b,
    }


def derive_query_and_candidates_from_bundle(
    bundle_payload: dict[str, Any], source: str = "source_a"
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Derive self-contained query and candidate envelopes from authoritative root records."""
    meta = bundle_payload["bundle_metadata"]
    if source == "source_a":
        query_id = "query-seamless-host-to-dc-v1"
        foothold = "S-1-5-21-1271839998-3495686680-2211690266-4131"
        scenario_id = meta["scenario_id"]
    elif source == "source_b":
        query_id = "query-seamless-source-b-to-dc-v1"
        foothold = "S-1-5-21-1271839998-3495686680-2211690266-4157"
        scenario_id = "scenario-seamless-source-b-to-dc"
    else:
        raise ValueError(f"Unknown source: {source}")

    # Scope filter by applicable_queries
    facts_ledger = bundle_payload.get("facts_ledger", {})
    obs_filtered = [
        copy.deepcopy(f)
        for f in facts_ledger.get("observed_facts", [])
        if query_id in f.get("applicable_queries", [])
    ]
    for f in obs_filtered:
        f.pop("applicable_queries", None)

    false_filtered = [
        copy.deepcopy(f)
        for f in facts_ledger.get("false_facts", [])
        if query_id in f.get("applicable_queries", [])
    ]
    for f in false_filtered:
        f.pop("applicable_queries", None)

    assumed_filtered = [
        copy.deepcopy(f)
        for f in facts_ledger.get("assumed_facts", [])
        if query_id in f.get("applicable_queries", [])
    ]
    for f in assumed_filtered:
        f.pop("applicable_queries", None)

    unknown_filtered = [
        copy.deepcopy(f)
        for f in facts_ledger.get("unknown_facts", [])
        if query_id in f.get("applicable_queries", [])
    ]
    for f in unknown_filtered:
        f.pop("applicable_queries", None)

    actions_filtered = [
        copy.deepcopy(a)
        for a in bundle_payload.get("bound_actions", [])
        if query_id in a.get("applicable_queries", [])
    ]
    for a in actions_filtered:
        a.pop("applicable_queries", None)

    units_filtered = {
        uid: copy.deepcopy(rec)
        for uid, rec in bundle_payload.get("work_units_ledger", {}).items()
        if query_id in rec.get("applicable_queries", [])
    }
    for u in units_filtered.values():
        u.pop("applicable_queries", None)
        u.pop("alias", None)
        u.pop("technical_source", None)
        u.pop("summary", None)

    bounds_filtered = [
        copy.deepcopy(b)
        for b in bundle_payload.get("conditional_bounds_table", [])
        if query_id in b.get("applicable_queries", [])
    ]
    for b in bounds_filtered:
        b.pop("applicable_queries", None)

    cands = [
        copy.deepcopy(c)
        for c in bundle_payload.get("candidate_envelopes", [])
        if c.get("scope_binding", {}).get("query_id") == query_id
        or query_id in c.get("applicable_queries", [])
    ]
    for c in cands:
        c.pop("applicable_queries", None)

    # Predicate layers needed by filtered components
    all_preds: set[str] = set()
    for f in obs_filtered:
        all_preds.add(f["predicate"])
    for f in false_filtered:
        all_preds.add(f["predicate"])
    for f in assumed_filtered:
        all_preds.add(f["predicate"])
    for f in unknown_filtered:
        all_preds.add(f["predicate"])
    for a in actions_filtered:
        all_preds.update(a.get("requires", []))
        all_preds.update(a.get("adds", []))
    for p in meta.get("target_goal", {}).get("required_predicates", []):
        all_preds.add(p)

    pred_layers = {
        p: layer for p, layer in facts_ledger.get("predicate_layers", {}).items() if p in all_preds
    }
    for f in obs_filtered + false_filtered + assumed_filtered + unknown_filtered:
        if "layer" in f and f["predicate"] not in pred_layers:
            pred_layers[f["predicate"]] = f["layer"]

    query = {
        "query_metadata": {
            "query_id": query_id,
            "version": meta.get("schema_version", "1.0.0"),
            "scenario_id": scenario_id,
            "scenario_version": meta["scenario_version"],
            "snapshot_id": meta["snapshot_id"],
            "evaluation_mode": meta.get("evaluation_mode", "scenario"),
            "work_boundary": meta["work_boundary"],
            "foothold_node_id": foothold,
            "target_goal": copy.deepcopy(meta["target_goal"]),
            "horizon": meta["horizon"],
            "active_work_budget": meta["active_work_budget"],
            "bundle_id": meta["bundle_id"],
            "bundle_version": meta["bundle_version"],
            "bundle_digest": meta.get("bundle_digest"),
            "governance": copy.deepcopy(bundle_payload.get("governance")),
        },
        "facts_ledger": {
            "observed_facts": obs_filtered,
            "false_facts": false_filtered,
            "assumed_facts": assumed_filtered,
            "unknown_facts": unknown_filtered,
            "predicate_layers": pred_layers,
        },
        "bound_actions": actions_filtered,
        "work_units_ledger": units_filtered,
        "conditional_bounds_table": bounds_filtered,
        "target_impact_assessments": copy.deepcopy(bundle_payload["target_impact_assessments"]),
    }
    return query, cands


def extract_query_and_candidates_from_bundle(
    bundle_payload: dict[str, Any], source: str = "source_a"
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Extract authoritative query and candidates from bundle, validating cached projections."""
    derived_query, derived_candidates = derive_query_and_candidates_from_bundle(
        bundle_payload, source
    )
    projections = bundle_payload.get("query_projections")
    if projections and source in projections:
        cached_proj = projections[source]
        cached_query = cached_proj.get("query")
        cached_candidates = cached_proj.get("candidates")
        if cached_query != derived_query or cached_candidates != derived_candidates:
            raise ValueError(
                f"Cached query projection for '{source}' does not match authoritative root records"
            )
    return derived_query, derived_candidates


def verify_calculation_traces_source_a(roundtrip_result: dict[str, Any]) -> dict[str, Any]:
    """Verify exact Fraction calculation traces for Source A proposed candidates."""
    eligible = roundtrip_result.get("eligible_candidates", {})
    if "cand_seamless_01_direct_lidia" not in eligible:
        raise ValueError("cand_seamless_01_direct_lidia missing from eligible candidates")
    if "cand_seamless_02_alt_vajer_ollie" not in eligible:
        raise ValueError("cand_seamless_02_alt_vajer_ollie missing from eligible candidates")

    c1 = eligible["cand_seamless_01_direct_lidia"]
    c2 = eligible["cand_seamless_02_alt_vajer_ollie"]

    trace_errors = []

    # Candidate 1 checks: [42/125, 171/250], effort=2, impact=High
    c1_lower = Fraction(c1["likelihood_interval"][0])
    c1_upper = Fraction(c1["likelihood_interval"][1])
    if (c1_lower, c1_upper) != EXPECTED_CAND_1_LIKELIHOOD:
        trace_errors.append(
            f"Cand 1 likelihood mismatch: got ({c1_lower}, {c1_upper}), "
            f"expected {EXPECTED_CAND_1_LIKELIHOOD}"
        )
    if c1.get("effort") != EXPECTED_CAND_1_EFFORT:
        trace_errors.append(f"Cand 1 effort mismatch: got {c1.get('effort')}, expected 2")
    if c1.get("impact") != EXPECTED_CAND_1_IMPACT:
        trace_errors.append(f"Cand 1 impact mismatch: got {c1.get('impact')}, expected High")

    # Candidate 2 checks: [126/625, 55233/100000], effort=3, impact=High
    c2_lower = Fraction(c2["likelihood_interval"][0])
    c2_upper = Fraction(c2["likelihood_interval"][1])
    if (c2_lower, c2_upper) != EXPECTED_CAND_2_LIKELIHOOD:
        trace_errors.append(
            f"Cand 2 likelihood mismatch: got ({c2_lower}, {c2_upper}), "
            f"expected {EXPECTED_CAND_2_LIKELIHOOD}"
        )
    if c2.get("effort") != EXPECTED_CAND_2_EFFORT:
        trace_errors.append(f"Cand 2 effort mismatch: got {c2.get('effort')}, expected 3")
    if c2.get("impact") != EXPECTED_CAND_2_IMPACT:
        trace_errors.append(f"Cand 2 impact mismatch: got {c2.get('impact')}, expected High")

    # Verify analytical interval overlap: c1_lower < c2_upper and c2_lower < c1_upper
    if not (c1_lower < c2_upper and c2_lower < c1_upper):
        trace_errors.append(
            f"Analytical interval overlap violated: c1=[{c1_lower}, {c1_upper}], "
            f"c2=[{c2_lower}, {c2_upper}]"
        )

    if trace_errors:
        raise ValueError("; ".join(trace_errors))

    # Verify Pareto frontier preserves incomparability due to interval overlap
    frontier = roundtrip_result.get("pareto_frontier", [])
    expected_frontier = ["cand_seamless_01_direct_lidia", "cand_seamless_02_alt_vajer_ollie"]
    if sorted(frontier) != sorted(expected_frontier):
        raise ValueError(f"Frontier mismatch: got {frontier}, expected {expected_frontier}")

    # Verify Min-Effort-to-DA baseline
    baseline = roundtrip_result.get("min_effort_to_da_baseline", {})
    if baseline.get("best_candidate_id") != "cand_seamless_01_direct_lidia":
        raise ValueError(
            f"Min effort best candidate mismatch: got {baseline.get('best_candidate_id')}"
        )
    if baseline.get("minimum_effort_value") != 2:
        raise ValueError(
            f"Min effort value mismatch: got {baseline.get('minimum_effort_value')}, expected 2"
        )

    return {
        "status": "PASS",
        "cand_1": {
            "likelihood_interval": [str(c1_lower), str(c1_upper)],
            "effort": c1["effort"],
            "impact": c1["impact"],
        },
        "cand_2": {
            "likelihood_interval": [str(c2_lower), str(c2_upper)],
            "effort": c2["effort"],
            "impact": c2["impact"],
        },
        "pareto_frontier": frontier,
        "min_effort_to_da": {
            "best_candidate_id": baseline.get("best_candidate_id"),
            "minimum_effort_value": baseline.get("minimum_effort_value"),
        },
    }


def verify_calculation_traces_source_b(roundtrip_result: dict[str, Any]) -> dict[str, Any]:
    """Verify exact Fraction calculation traces for Source B candidate."""
    eligible = roundtrip_result.get("eligible_candidates", {})
    if "cand_seamless_source_b_01_ollie" not in eligible:
        raise ValueError("cand_seamless_source_b_01_ollie missing from eligible candidates")

    cb = eligible["cand_seamless_source_b_01_ollie"]
    trace_errors = []

    cb_lower = Fraction(cb["likelihood_interval"][0])
    cb_upper = Fraction(cb["likelihood_interval"][1])
    if (cb_lower, cb_upper) != EXPECTED_CAND_B_LIKELIHOOD:
        trace_errors.append(
            f"Source B candidate likelihood mismatch: got ({cb_lower}, {cb_upper}), "
            f"expected {EXPECTED_CAND_B_LIKELIHOOD}"
        )
    if cb.get("effort") != EXPECTED_CAND_B_EFFORT:
        trace_errors.append(
            f"Source B candidate effort mismatch: got {cb.get('effort')}, expected 2"
        )
    if cb.get("impact") != EXPECTED_CAND_B_IMPACT:
        trace_errors.append(
            f"Source B candidate impact mismatch: got {cb.get('impact')}, expected High"
        )

    if trace_errors:
        raise ValueError("; ".join(trace_errors))

    frontier = roundtrip_result.get("pareto_frontier", [])
    expected_frontier = ["cand_seamless_source_b_01_ollie"]
    if sorted(frontier) != sorted(expected_frontier):
        raise ValueError(f"Frontier mismatch: got {frontier}, expected {expected_frontier}")

    baseline = roundtrip_result.get("min_effort_to_da_baseline", {})
    if baseline.get("best_candidate_id") != "cand_seamless_source_b_01_ollie":
        raise ValueError(
            f"Source B Min effort best candidate mismatch: got {baseline.get('best_candidate_id')}"
        )
    if baseline.get("minimum_effort_value") != 2:
        raise ValueError(
            f"Source B Min effort value mismatch: got {baseline.get('minimum_effort_value')}, "
            "expected 2"
        )

    return {
        "status": "PASS",
        "cand_b": {
            "likelihood_interval": [str(cb_lower), str(cb_upper)],
            "effort": cb["effort"],
            "impact": cb["impact"],
        },
        "pareto_frontier": frontier,
        "min_effort_to_da": {
            "best_candidate_id": baseline.get("best_candidate_id"),
            "minimum_effort_value": baseline.get("minimum_effort_value"),
        },
    }


def verify_calculation_traces(roundtrip_result: dict[str, Any]) -> dict[str, Any]:
    """Verify exact Fraction calculation traces for proposed candidates (defaults to Source A)."""
    return verify_calculation_traces_source_a(roundtrip_result)


def run_sensitivity_suite(base_payload: dict[str, Any]) -> dict[str, Any]:
    """Execute neighborhood sensitivity and behavioral conformance probes."""
    neighborhood: dict[str, Any] = {}
    conformance: dict[str, Any] = {}

    # -------------------------------------------------------------------------
    # Category A: Neighborhood Sensitivity Analysis around Proposal
    # -------------------------------------------------------------------------

    # Neighborhood Case 1: Friction (T2) effort increase on Candidate 1 (Lidia path)
    # T2 increases from 2 to 3 for reset_lidia and winrm_dc_lidia (T1=1, T2=3 -> C=2)
    # Cand 1 effort becomes 2 + 0 + 2 = 4 (up from 2); Cand 2 stays 3.
    # Min-Effort best flips from Cand 1 to Cand 2; Pareto frontier still keeps both.
    p_fric = copy.deepcopy(base_payload)
    ledger = p_fric["query"]["work_units_ledger"]
    for u, rec in ledger.items():
        if ("reset_password" in u or "remote_exec_winrm" in u) and "3398" in u:
            rec["rubric_scores"]["t2"] = 3
            rec["rubric_scores"]["computed_cost"] = rec["rubric_scores"]["t1"] + 3 - 2
            rec["t2"] = 3
            rec["effort_cost"] = rec["rubric_scores"]["computed_cost"]
            rec["computed_cost"] = rec["rubric_scores"]["computed_cost"]

    res_fric = execute_ranking_roundtrip(json.dumps(p_fric["query"]), p_fric["candidates"])
    rt_fric = res_fric["roundtrip_result"]
    assert rt_fric["eligible_candidates"]["cand_seamless_01_direct_lidia"]["effort"] == 4
    assert rt_fric["eligible_candidates"]["cand_seamless_02_alt_vajer_ollie"]["effort"] == 3
    assert rt_fric["min_effort_to_da_baseline"]["best_candidate_id"] == (
        "cand_seamless_02_alt_vajer_ollie"
    )
    assert rt_fric["min_effort_to_da_baseline"]["minimum_effort_value"] == 3
    assert set(rt_fric["pareto_frontier"]) == {
        "cand_seamless_01_direct_lidia",
        "cand_seamless_02_alt_vajer_ollie",
    }

    neighborhood["effort_friction_increase"] = {
        "description": (
            "Increase friction T2 from 2 to 3 for reset_lidia and winrm_dc_lidia. "
            "Candidate 1 effort jumps from 2 to 4 while Candidate 2 stays 3."
        ),
        "input_changes": {
            "reset_lidia": {"t2": "2 -> 3", "cost": "1 -> 2"},
            "winrm_dc_lidia": {"t2": "2 -> 3", "cost": "1 -> 2"},
        },
        "outputs": {
            "cand_1_effort": 4,
            "cand_2_effort": 3,
            "min_effort_best_candidate": "cand_seamless_02_alt_vajer_ollie",
            "minimum_effort_value": 3,
            "pareto_frontier": rt_fric["pareto_frontier"],
        },
        "diagnostics": (
            "Min-Effort-to-DA flips winner from Candidate 1 to Candidate 2; "
            "Pareto frontier remains incomparable because likelihood intervals still overlap."
        ),
        "status": "PASS",
    }

    # Neighborhood Case 2: Strictly nested likelihood bounds narrowing
    # Narrow Cand 1 bounds strictly inside original proposed intervals:
    # q1: [17/20, 9/10] subset [7/10, 9/10]
    # q2: [9/10, 19/20] subset [4/5, 19/20]
    # q3: [3/4, 4/5] subset [3/5, 4/5]
    # New Cand 1: [459/800, 171/250] = [0.57375, 0.684]
    # Since l1 = 0.57375 > u2 = 0.55233, strict Pareto dominance is achieved.
    p_nested = copy.deepcopy(base_payload)
    for row in p_nested["query"]["conditional_bounds_table"]:
        if len(row["prefix"]) == 1 and "3398" in row["prefix"][0]:
            row["lower"] = "17/20"
            row["upper"] = "9/10"
        elif len(row["prefix"]) == 2 and "3398" in row["prefix"][1]:
            row["lower"] = "9/10"
            row["upper"] = "19/20"
        elif len(row["prefix"]) == 3 and "3398" in row["prefix"][2]:
            row["lower"] = "3/4"
            row["upper"] = "4/5"

    res_nested = execute_ranking_roundtrip(json.dumps(p_nested["query"]), p_nested["candidates"])
    rt_nested = res_nested["roundtrip_result"]
    assert rt_nested["pareto_frontier"] == ["cand_seamless_01_direct_lidia"]
    assert rt_nested["eligible_candidates"]["cand_seamless_01_direct_lidia"][
        "likelihood_interval"
    ] == ["459/800", "171/250"]

    neighborhood["strictly_nested_bounds_narrowing"] = {
        "description": (
            "Cand 1 bounds strictly narrowed inside proposed intervals: "
            "q1=[17/20, 9/10] in [7/10, 9/10], q2=[9/10, 19/20] in [4/5, 19/20], "
            "q3=[3/4, 4/5] in [3/5, 4/5]."
        ),
        "input_changes": {
            "cand_1_q1": "[17/20, 9/10] (nested subset)",
            "cand_1_q2": "[9/10, 19/20] (nested subset)",
            "cand_1_q3": "[3/4, 4/5] (nested subset)",
        },
        "outputs": {
            "cand_1_interval": ["459/800", "171/250"],
            "cand_2_interval": ["126/625", "55233/100000"],
            "pareto_frontier": rt_nested["pareto_frontier"],
        },
        "diagnostics": (
            "Cand 1 lower bound 459/800 (0.57375) strictly exceeds Cand 2 upper bound "
            "55233/100000 (0.55233); strict Pareto dominance achieved and frontier "
            "collapses to Cand 1."
        ),
        "status": "PASS",
    }

    # Neighborhood Case 3: Dual Analysis: Single-Variable Margin & Executed Multi-Scenario Sweep
    # Part A: Single-variable analytic margin gap
    gap = float(Fraction(55233, 100000) - Fraction(42, 125))

    # Part B: Executed multi-scenario sweep: Candidate 2 upper bounds reduced by 10% (x 9/10)
    p_sweep = copy.deepcopy(base_payload)
    for row in p_sweep["query"]["conditional_bounds_table"]:
        if "3398" not in str(row["prefix"]):
            if len(row["prefix"]) == 1:
                row["lower"] = "3/4"
                row["upper"] = "81/100"
            elif len(row["prefix"]) == 2:
                row["lower"] = "4/5"
                row["upper"] = "171/200"
            elif len(row["prefix"]) == 3:
                row["lower"] = "7/10"
                row["upper"] = "153/200"
            elif len(row["prefix"]) == 4:
                row["lower"] = "4/5"
                row["upper"] = "171/200"
            elif len(row["prefix"]) == 5:
                row["lower"] = "3/5"
                row["upper"] = "18/25"

    res_sweep = execute_ranking_roundtrip(json.dumps(p_sweep["query"]), p_sweep["candidates"])
    rt_sweep = res_sweep["roundtrip_result"]
    assert rt_sweep["pareto_frontier"] == ["cand_seamless_01_direct_lidia"]
    cand2_sweep = rt_sweep["eligible_candidates"]["cand_seamless_02_alt_vajer_ollie"]
    assert cand2_sweep["likelihood_interval"] == ["126/625", "3261453417/10000000000"]
    assert Fraction(cand2_sweep["likelihood_interval"][1]) < Fraction(42, 125)

    neighborhood["bounds_overlap_margin_sweep"] = {
        "description": (
            "Dual analysis: (a) Single-variable analytic margin gap separating Candidate 1 lower "
            "bound (0.336) from Candidate 2 upper bound (0.55233); (b) Executed multi-scenario "
            "sweep where Candidate 2 upper bounds are reduced by 10% across all 5 steps."
        ),
        "overlap_margin_gap": round(gap, 5),
        "analytic_single_variable_gap": {
            "overlap_margin_gap": round(gap, 5),
            "required_l1_increase_percentage": "+64.4%",
            "diagnostics": (
                f"Overlap gap is {round(gap, 5)} (+64.4% increase of l1 required to break overlap "
                "if u2 is held fixed)."
            ),
        },
        "executed_multi_scenario_sweep": {
            "description": "Candidate 2 upper bounds reduced by 10% (x 9/10) across all 5 steps.",
            "input_changes": {
                "q1_upper": "9/10 * 9/10 = 81/100",
                "q2_upper": "19/20 * 9/10 = 171/200",
                "q3_upper": "17/20 * 9/10 = 153/200",
                "q4_upper": "19/20 * 9/10 = 171/200",
                "q5_upper": "4/5 * 9/10 = 18/25",
            },
            "outputs": {
                "cand_1_interval": ["42/125", "171/250"],
                "cand_2_interval": ["126/625", "3261453417/10000000000"],
                "cand_2_u2_float": float(Fraction(3261453417, 10000000000)),
                "cand_1_l1_float": float(Fraction(42, 125)),
                "frontier_transition": {
                    "before": ["cand_seamless_01_direct_lidia", "cand_seamless_02_alt_vajer_ollie"],
                    "after": rt_sweep["pareto_frontier"],
                },
            },
            "diagnostics": (
                "When Candidate 2 upper bounds are reduced by 10% compound across 5 steps, "
                "u2 drops to 3261453417/10000000000 (0.3261453417) < l1 (0.336). "
                "The Pareto frontier collapses from incomparable to single-winner "
                "['cand_seamless_01_direct_lidia']."
            ),
        },
        "status": "PASS",
    }

    # -------------------------------------------------------------------------
    # Category B: Behavioral & Gating Conformance Probes
    # -------------------------------------------------------------------------

    # Conformance Probe 1: Point-likelihood tie-break via effort
    p_tie = copy.deepcopy(base_payload)
    for row in p_tie["query"]["conditional_bounds_table"]:
        if len(row["prefix"]) == 1:
            row["lower"] = "3/10"
            row["upper"] = "3/10"
        else:
            row["lower"] = "1"
            row["upper"] = "1"
    res_tie = execute_ranking_roundtrip(json.dumps(p_tie["query"]), p_tie["candidates"])
    rt_tie = res_tie["roundtrip_result"]
    assert rt_tie["pareto_frontier"] == ["cand_seamless_01_direct_lidia"]
    conformance["point_likelihood_tie_break"] = {
        "description": (
            "Exact point likelihood equality [3/10, 3/10]; "
            "Cand 1 wins tie-break by lower effort (2 < 3)."
        ),
        "frontier": rt_tie["pareto_frontier"],
        "status": "PASS",
    }

    # Conformance Probe 2: Target impact rating Critical shift
    p_crit = copy.deepcopy(base_payload)
    p_crit["query"]["target_impact_assessments"]["S-1-5-21-1271839998-3495686680-2211690266-1000"][
        "consequence_rating"
    ] = "Critical"
    res_crit = execute_ranking_roundtrip(json.dumps(p_crit["query"]), p_crit["candidates"])
    rt_crit = res_crit["roundtrip_result"]
    assert set(rt_crit["pareto_frontier"]) == {
        "cand_seamless_01_direct_lidia",
        "cand_seamless_02_alt_vajer_ollie",
    }
    conformance["target_impact_critical_shift"] = {
        "description": (
            "Target DC consequence rating shifted to Critical for both candidates; "
            "frontier preserved with both candidates eligible."
        ),
        "frontier": rt_crit["pareto_frontier"],
        "status": "PASS",
    }

    # Conformance Probe 3: Target impact unrated fail-closed
    p_unrated = copy.deepcopy(base_payload)
    p_unrated["query"]["target_impact_assessments"][
        "S-1-5-21-1271839998-3495686680-2211690266-1000"
    ]["rating_status"] = "unrated"
    p_unrated["query"]["target_impact_assessments"][
        "S-1-5-21-1271839998-3495686680-2211690266-1000"
    ]["consequence_rating"] = None
    p_unrated["query"]["target_impact_assessments"][
        "S-1-5-21-1271839998-3495686680-2211690266-1000"
    ]["missing_basis_reasons"] = ["unrated_consequence"]
    res_unrated = execute_ranking_roundtrip(json.dumps(p_unrated["query"]), p_unrated["candidates"])
    rt_unrated = res_unrated["roundtrip_result"]
    assert rt_unrated["pareto_frontier"] == []
    assert len(rt_unrated["diagnostics"]) == 2
    conformance["target_impact_unrated_fail_closed"] = {
        "description": (
            "Unrated target consequence rating triggers fail-closed; "
            "both candidates excluded from eligible set and frontier is empty."
        ),
        "frontier": rt_unrated["pareto_frontier"],
        "diagnostics_count": len(rt_unrated["diagnostics"]),
        "status": "PASS",
    }

    # Conformance Probe 4: Required predicate known-false veto
    p_false = copy.deepcopy(base_payload)
    p_false["query"]["facts_ledger"]["false_facts"].append(
        {
            "predicate": "endpoint_authorized_lidia",
            "truth_value": False,
            "layer": 3,
            "provenance_reference": "sensitivity:synthetic_jea_restriction",
        }
    )
    res_false = execute_ranking_roundtrip(json.dumps(p_false["query"]), p_false["candidates"])
    rt_false = res_false["roundtrip_result"]
    assert "cand_seamless_01_direct_lidia" in rt_false["diagnostics"]
    assert (
        rt_false["diagnostics"]["cand_seamless_01_direct_lidia"]["assessment"]["status"]
        == "blocked"
    )
    assert rt_false["pareto_frontier"] == ["cand_seamless_02_alt_vajer_ollie"]
    conformance["required_predicate_known_false_veto"] = {
        "description": (
            "Required predicate endpoint_authorized_lidia marked false; "
            "Cand 1 partitioned to diagnostics with status 'blocked'; Cand 2 sole frontier."
        ),
        "frontier": rt_false["pareto_frontier"],
        "diagnostics_status": "blocked",
        "status": "PASS",
    }

    # Conformance Probe 5: Irrelevant predicate false no-op (proves veto is not global)
    p_irrel = copy.deepcopy(base_payload)
    p_irrel["query"]["facts_ledger"]["false_facts"].append(
        {
            "predicate": "synthetic_unrelated_service_reachable",
            "truth_value": False,
            "layer": 3,
            "provenance_reference": "sensitivity:synthetic_irrelevant_false",
        }
    )
    res_irrel = execute_ranking_roundtrip(json.dumps(p_irrel["query"]), p_irrel["candidates"])
    rt_irrel = res_irrel["roundtrip_result"]
    assert set(rt_irrel["pareto_frontier"]) == {
        "cand_seamless_01_direct_lidia",
        "cand_seamless_02_alt_vajer_ollie",
    }
    conformance["irrelevant_predicate_false_noop"] = {
        "description": (
            "Irrelevant predicate marked false in facts ledger; "
            "neither candidate requires it, so neither candidate is blocked."
        ),
        "frontier": rt_irrel["pareto_frontier"],
        "status": "PASS",
    }

    # Conformance Probe 6: Required predicate unknown gating
    p_unk = copy.deepcopy(base_payload)
    p_unk["query"]["facts_ledger"]["assumed_facts"] = [
        f
        for f in p_unk["query"]["facts_ledger"]["assumed_facts"]
        if f["predicate"] != "winrm_authentication_accepted_lidia"
    ]
    res_unk = execute_ranking_roundtrip(json.dumps(p_unk["query"]), p_unk["candidates"])
    rt_unk = res_unk["roundtrip_result"]
    assert "cand_seamless_01_direct_lidia" in rt_unk["diagnostics"]
    assert (
        rt_unk["diagnostics"]["cand_seamless_01_direct_lidia"]["assessment"]["status"] == "unknown"
    )
    assert rt_unk["pareto_frontier"] == ["cand_seamless_02_alt_vajer_ollie"]
    conformance["required_predicate_unknown_gating"] = {
        "description": (
            "Required predicate winrm_authentication_accepted_lidia omitted / unknown; "
            "Cand 1 partitioned to diagnostics with status 'unknown'; Cand 2 sole frontier."
        ),
        "frontier": rt_unk["pareto_frontier"],
        "diagnostics_status": "unknown",
        "status": "PASS",
    }

    return {
        "neighborhood_sensitivity": neighborhood,
        "conformance_probes": conformance,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=False)
    group.add_argument(
        "--bundle",
        type=Path,
        default=None,
        help="Path to seamless parameter bundle JSON",
    )
    group.add_argument(
        "--input",
        type=Path,
        default=None,
        help="Path to proposed query input JSON",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Optional path to write sensitivity analysis report JSON",
    )
    args = parser.parse_args()

    bundle_path: Path | None = None
    input_path: Path | None = None

    if args.bundle is not None:
        bundle_path = args.bundle.resolve()
        if not bundle_path.exists():
            parser.error(f"Bundle file not found: {args.bundle}")
    elif args.input is not None:
        input_path = args.input.resolve()
        if not input_path.exists():
            parser.error(f"Input file not found: {args.input}")
    else:
        # Default to canonical parameter bundle fixture
        bundle_path = (FIXTURES / "seamless_parameter_bundle.json").resolve()
        if not bundle_path.exists():
            parser.error(f"Default bundle file not found: {bundle_path}")

    bundle_report = None
    if bundle_path:
        bundle_payload = json.loads(bundle_path.read_text(encoding="utf-8"))
        bundle_report = verify_parameter_bundle(bundle_payload)
        query_a, cands_a = extract_query_and_candidates_from_bundle(bundle_payload, "source_a")
        payload = {"query": query_a, "candidates": cands_a}
        input_target_path = bundle_path
    else:
        assert input_path is not None
        payload = json.loads(input_path.read_text(encoding="utf-8"))
        input_target_path = input_path

    roundtrip = execute_ranking_roundtrip(json.dumps(payload["query"]), payload["candidates"])
    traces_report = verify_calculation_traces(roundtrip["roundtrip_result"])
    sensitivity_report = run_sensitivity_suite(payload)

    # Use portable relative path if input is inside repository ROOT
    try:
        portable_input = input_target_path.relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        portable_input = input_target_path.as_posix()

    report: dict[str, Any] = {
        "schema_version": "1.0.0",
        "input_file": portable_input,
    }
    if bundle_report:
        try:
            report["bundle_file"] = bundle_path.relative_to(ROOT.resolve()).as_posix()
        except ValueError:
            report["bundle_file"] = str(bundle_path)
        report["bundle_validation"] = bundle_report

    report["calculation_traces"] = traces_report
    report["sensitivity_analysis"] = sensitivity_report

    print("=== SEAMLESS PARAMETER PROPOSAL VALIDATION ===")
    if bundle_report:
        bid = bundle_report["bundle_id"]
        bver = bundle_report["bundle_version"]
        print(f"Parameter Bundle: PASS ({bid} v{bver})")
        u_cnt = bundle_report["work_units_count"]
        b_cnt = bundle_report["conditional_bounds_count"]
        a_cnt = bundle_report["assumed_facts_count"]
        c_cnt = bundle_report["candidates_count"]
        print(f"  Units: {u_cnt}, Bounds: {b_cnt}, Assumptions: {a_cnt}, Candidates: {c_cnt}")
        print("  Canonical Engine Evaluation (Source A): PASS")
        print("  Canonical Engine Evaluation (Source B): PASS")
    print("Base Calculation Traces (Source A): PASS")
    c1_line = (
        f"Cand 1: Likelihood={traces_report['cand_1']['likelihood_interval']}, "
        f"Effort={traces_report['cand_1']['effort']}, Impact={traces_report['cand_1']['impact']}"
    )
    c2_line = (
        f"Cand 2: Likelihood={traces_report['cand_2']['likelihood_interval']}, "
        f"Effort={traces_report['cand_2']['effort']}, Impact={traces_report['cand_2']['impact']}"
    )
    print(c1_line)
    print(c2_line)
    print(f"Pareto Frontier: {traces_report['pareto_frontier']}")
    print(f"Min Effort to DA: {traces_report['min_effort_to_da']}")

    if bundle_report and "source_b_traces" in bundle_report:
        b_traces = bundle_report["source_b_traces"]
        print("\nBase Calculation Traces (Source B): PASS")
        cb_line = (
            f"Cand B: Likelihood={b_traces['cand_b']['likelihood_interval']}, "
            f"Effort={b_traces['cand_b']['effort']}, Impact={b_traces['cand_b']['impact']}"
        )
        print(cb_line)
        print(f"Pareto Frontier: {b_traces['pareto_frontier']}")
        print(f"Min Effort to DA: {b_traces['min_effort_to_da']}")

    print("\n--- Neighborhood Sensitivity Analysis ---")
    for s_name, s_data in sensitivity_report["neighborhood_sensitivity"].items():
        print(f"- {s_name}: {s_data['status']}")
        if "outputs" in s_data:
            print(f"  Frontier: {s_data['outputs']['pareto_frontier']}")
        if "diagnostics" in s_data:
            print(f"  Diagnostics: {s_data['diagnostics']}")

    print("\n--- Behavioral Conformance Probes ---")
    for p_name, p_data in sensitivity_report["conformance_probes"].items():
        frontier_display = p_data.get("frontier", [])
        print(f"- {p_name}: {p_data['status']} -> Frontier: {frontier_display}")

    if args.output:
        atomic_write(args.output, json.dumps(report, indent=2) + "\n")
        print(f"\nWrote validation report to: {args.output}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
