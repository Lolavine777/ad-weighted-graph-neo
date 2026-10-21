"""A-owned analytical proposals for offline recovery; never a runtime provider.

Published guessing curves anchor declared scenario priors. Transfer, mixture
weights and conditional work completion still require B's separate adoption.
No guesses, credentials, acquired material, native rating records or searches.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from fractions import Fraction
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = ROOT / "docs/research/ratings/offline-recovery-v1"
FAMILIES = {
    "asrep_password_recovery": ("recover_asrep_secret", "AS-REP", 23, 18200),
    "kerberoast_password_recovery": ("recover_ticket_secret", "TGS", 23, 13100),
}
ORACLE_SCOPE = (
    "correct exact-password verification; no key leakage, key collision or cryptanalytic shortcut"
)
DEPLOYMENT_ROLE = "reference_scenario_not_default_baseline"
CONDITIONING = "acquisition_succeeded_and_exact_full_successful_history"


def validate_post_history_uniformity(assumption):
    """Validate the declared posterior model; this does not prove a real history."""
    required = {
        "conditioning": CONDITIONING,
        "posterior_law": "uniform_on_full_declared_space",
        "password_correlated_side_information": "assumed_absent",
        "password_dependent_account_selection": "assumed_absent",
        "known_rejected_candidates": "assumed_absent",
        "basis_class": "declared_scenario_assumption_pending_b_review",
    }
    if not isinstance(assumption, dict) or any(
        assumption.get(key) != value for key, value in required.items()
    ):
        raise ValueError(
            "Post-history uniformity is required; correlated, selected or unknown posterior refused"
        )
    reference = assumption.get("assumption_reference")
    if not isinstance(reference, str) or not reference.strip():
        raise ValueError("Post-history uniformity needs an explicit assumption reference")


def fraction(value):
    if not isinstance(value, (str, int)) or isinstance(value, bool):
        raise ValueError("Use exact integer or rational-string inputs")
    return Fraction(value)


def interval(values):
    if not isinstance(values, list) or len(values) != 2:
        raise ValueError("An interval needs two exact bounds")
    lower, upper = map(fraction, values)
    if not 0 <= lower <= upper <= 1:
        raise ValueError("Invalid probability interval")
    return lower, upper


def integer(value, minimum=0):
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ValueError("Invalid count or duration")
    return value


def curve_bounds(points, guesses, *, rounding_half_width):
    """CDF monotonicity only; no interpolation or tail extrapolation."""
    guesses = integer(guesses)
    half_width = fraction(rounding_half_width)
    if not 0 <= half_width < 1:
        raise ValueError("Invalid source rounding width")
    previous_n, previous_p = 0, Fraction(0)
    lower, upper = Fraction(0), Fraction(1)
    for point in points:
        n, p = integer(point["guesses"], 1), fraction(point["reported_fraction"])
        if n <= previous_n or not previous_p <= p <= 1:
            raise ValueError("Source CDF points must increase monotonically")
        if n <= guesses:
            lower = max(lower, p - half_width, Fraction(0))
        if n >= guesses:
            upper = min(upper, p + half_width, Fraction(1))
        previous_n, previous_p = n, p
    if not points:
        raise ValueError("Missing source CDF")
    return (Fraction(0), Fraction(0)) if guesses == 0 else (lower, upper)


def reference_envelope(source, guesses):
    rows = source["rows"]
    if not rows:
        raise ValueError("Missing reference populations")
    bounds = [
        curve_bounds(row["points"], guesses, rounding_half_width=source["rounding_half_width"])
        for row in rows
    ]
    # Using this min/max envelope for a target is itself a reviewed scenario assumption.
    return min(v[0] for v in bounds), max(v[1] for v in bounds)


def human_interval(source, floor, cap, completion_given_floor_rank):
    """q >= F(floor)*P(correct completion | R<=floor,H), q <= F(cap).

    The completion factor is conditional on the rank event, not an unrelated
    marginal; no independence claim. Work beyond the floor has no lower guarantee.
    """
    integer(floor, 1)
    integer(cap, floor)
    completion_lower, _ = interval(completion_given_floor_rank)
    lower, _ = reference_envelope(source, floor)
    _, upper = reference_envelope(source, cap)
    return lower * completion_lower, upper


def random_upper(cap, alphabet_size, length, *, post_history_uniformity):
    """cap/M requires uniformity after acquisition/full history, not just generation."""
    validate_post_history_uniformity(post_history_uniformity)
    integer(cap)
    integer(alphabet_size, 2)
    integer(length, 1)
    return min(Fraction(1), Fraction(cap, alphabet_size**length))


def mixture_interval(manual, generated, weight):
    """Law of total probability over conditional password-generation strata."""
    m_lower, m_upper = interval([str(v) for v in manual])
    g_lower, g_upper = interval([str(v) for v in generated])
    w_lower, w_upper = interval(weight)
    return (
        min(w * m_lower + (1 - w) * g_lower for w in (w_lower, w_upper)),
        max(w * m_upper + (1 - w) * g_upper for w in (w_lower, w_upper)),
    )


def conditional_chain(intervals):
    """Illustrative full-history chain arithmetic, never an eligible engine path."""
    lower, upper = Fraction(1), Fraction(1)
    for bounds in intervals:
        a, b = interval(bounds)
        lower, upper = lower * a, upper * b
    return lower, upper


def propose(profile, source):
    if profile.get("status") != "proposed_pending_b_review":
        raise ValueError("Research packet cannot adopt numeric authority")
    if profile.get("numeric_basis_class") != "estimated_expert_scenario":
        raise ValueError("Reference priors are not empirical target calibration")
    if profile.get("deployment_role") != DEPLOYMENT_ROLE:
        raise ValueError("Reference scenario cannot silently become a product baseline")
    family = profile.get("class_id")
    if family not in FAMILIES:
        raise ValueError("Unsupported recovery class")
    technique, material, etype, mode = FAMILIES[family]
    verifier = profile["verifier"]
    if verifier.get("oracle_scope") != ORACLE_SCOPE:
        raise ValueError("Unsupported verifier oracle scope; rank bounds do not cover shortcuts")
    if (
        profile["technique_id"] != technique
        or verifier["material"] != material
        or verifier["etype"] != etype
        or verifier["hashcat_mode"] != mode
    ):
        raise ValueError("No AS-REP/TGS or etype verifier transfer")
    if profile["target_success_event"] != "validated_password_for_acquired_material":
        raise ValueError("Recovery success must remain distinct from identity activation")
    if profile["conditioning"] != CONDITIONING:
        raise ValueError("Missing acquired-material/full-history conditioning")
    budget = profile["budget"]
    floor = budget["min_complete_distinct_verifications_on_no_hit"]
    cap = integer(budget["max_complete_distinct_verifications"], 1)
    if integer(budget["jobs"], 1) != 1 or budget["work_unit"] != "distinct_complete_verification":
        raise ValueError("Incompatible work or retry unit")
    deadline = integer(budget["deadline_seconds"], 1)
    if deadline > integer(profile["horizon_seconds"], 1):
        raise ValueError("Event deadline exceeds campaign horizon")
    feasibility = budget.get("cap_feasibility")
    if (
        not isinstance(feasibility, dict)
        or feasibility.get("cap_role") != "maximum_stop_limit_not_achieved_work"
        or feasibility.get("attainment_evidence") != "not_demonstrated"
        or feasibility.get("requires_separate_resource_evidence_before_operational_use_or_adoption")
        is not True
    ):
        raise ValueError("Cap feasibility is unverified; no operational attainment claim allowed")
    if floor is not None:
        integer(floor, 1)
        integer(cap, floor)
    common = {
        "profile_id": profile["profile_id"],
        "profile_version": profile["profile_version"],
        "class_id": family,
        "status": "proposed_pending_b_review",
        "numeric_basis_class": "estimated_expert_scenario",
        "deployment_role": DEPLOYMENT_ROLE,
        "records_emitted": 0,
        "production_coverage_measured": False,
        "resource_scope": {
            "cap_role": feasibility["cap_role"],
            "upper_role": (
                "hypothetical_loose_wide_cap_enclosure"
                if floor is not None and cap > floor
                else "mathematical_cap_enclosure_pending_resource_review"
            ),
            "floor_rate_requirement": str(Fraction(floor, deadline)) if floor else None,
            "cap_exhaustion_rate_requirement": str(Fraction(cap, deadline)),
            "rate_unit": "complete_distinct_verifications_per_second_including_generation",
            "attainment_evidence": "not_demonstrated",
            "requires_separate_resource_evidence_before_operational_use_or_adoption": True,
        },
    }
    population = profile["population"]
    kind = population["kind"]
    if kind == "unknown_natural_password":
        return {**common, "disposition": "UNRATED_NO_BASIS", "proposed_interval": None}
    if kind not in {"human_reference_envelope", "service_conditional_mixture", "uniform_service"}:
        raise ValueError("Unsupported population regime")
    if family == "asrep_password_recovery" and kind != "human_reference_envelope":
        raise ValueError("AS-REP profile must use its own declared human population")
    if family == "kerberoast_password_recovery" and kind == "human_reference_envelope":
        raise ValueError("Kerberoast needs a separate service-population proposal")
    if kind != "uniform_service":
        if population.get("reference_transfer") != "explicit_assumption_requires_separate_b_review":
            raise ValueError("No automatic research population or guess-unit transfer")
        if floor is None:
            return {
                **common,
                "disposition": "REQUIRES_CONTEXT_WORK_FLOOR",
                "proposed_interval": None,
            }
        manual = human_interval(source, floor, cap, profile["completion_given_floor_rank"])
    if kind == "human_reference_envelope":
        bounds = manual
    else:
        generated = population["generated_stratum"]
        if generated["generation"] != "independent_uniform_characters_no_side_information":
            raise ValueError("Random-space bound requires explicit generation regime")
        strong = (
            Fraction(0),
            random_upper(
                cap,
                generated["alphabet_size"],
                generated["length"],
                post_history_uniformity=generated.get("post_history_uniformity_assumption"),
            ),
        )
        bounds = (
            strong
            if kind == "uniform_service"
            else mixture_interval(manual, strong, population["manual_weight_given_history"])
        )
    return {
        **common,
        "disposition": "NUMERIC_PROPOSAL_ONLY",
        "proposed_interval": [str(v) for v in bounds],
        "percent_display_only": [float(v * 100) for v in bounds],
        "conditional_work_floor_is_assumed_not_measured": kind != "uniform_service",
    }


def audit(sources, packet):
    if packet["status"] != "proposed_pending_b_review" or packet["b_adopted"]:
        raise ValueError("Research packet must remain pending")
    if (
        packet.get("deployment_role") != DEPLOYMENT_ROLE
        or packet.get("product_baseline_selected") is not False
    ):
        raise ValueError("Reference packet cannot silently become a product baseline")
    profiles = packet["profiles"]
    if len({p["profile_id"] for p in profiles}) != len(profiles):
        raise ValueError("Duplicate scenario profile")
    source = sources["guessing_reference"]
    proposals = [propose(p, source) for p in profiles]
    return {
        "schema_version": "offline-recovery-proposal-audit/1.1.0",
        "source_package_version": packet["version"],
        "evidence_class": "analytical_scenario_proposal",
        "numeric_adopted": False,
        "records_emitted": 0,
        "native_search_or_coverage_run": False,
        "proposals": proposals,
        "limitations": packet["limitations"],
    }


def sensitivity(sources, packet):
    """Explicit alternative assumptions; no frozen query or denominator changes."""
    source = sources["guessing_reference"]
    profiles = {
        p["class_id"]: p
        for p in packet["profiles"]
        if p["population"]["kind"] in {"human_reference_envelope", "service_conditional_mixture"}
        and p["budget"]["max_complete_distinct_verifications"] == 10**9
    }
    rows = []
    for family, profile in profiles.items():
        for floor, cap in ((10**6, 10**9), (10**9, 10**9), (10**9, 2**36)):
            for completion in ("4/5", "19/20", "1"):
                changed = copy.deepcopy(profile)
                changed["budget"]["min_complete_distinct_verifications_on_no_hit"] = floor
                changed["budget"]["max_complete_distinct_verifications"] = cap
                changed["completion_given_floor_rank"] = [completion, "1"]
                rows.append(
                    {
                        "class_id": family,
                        "floor": floor,
                        "cap": cap,
                        "conditional_completion_floor": completion,
                        "recovery": propose(changed, source)["proposed_interval"],
                    }
                )
    weights = []
    for weight in ("0", "1/4", "1/2", "1"):
        changed = copy.deepcopy(profiles["kerberoast_password_recovery"])
        changed["population"]["manual_weight_given_history"] = [weight, weight]
        weights.append(
            {
                "manual_weight_given_history": weight,
                "recovery": propose(changed, source)["proposed_interval"],
            }
        )
    chains = []
    for profile in packet["profiles"]:
        if profile["population"]["kind"] != "human_reference_envelope":
            continue
        recovery = propose(profile, source)["proposed_interval"]
        product = conditional_chain(
            [
                ["9/10", "99/100"],
                recovery,
                ["3/4", "49/50"],
                ["1/2", "9/10"],
            ]
        )
        chains.append(
            {
                "profile_id": profile["profile_id"],
                "conditional_chain_only": [str(v) for v in product],
                "is_generated_or_eligible_path": False,
                "downstream_history_adopted": False,
            }
        )
    return {
        "evidence_class": "analytical_scenario_sensitivity",
        "budget_and_completion_sensitivity": rows,
        "service_weight_sensitivity": weights,
        "asrep_chain_arithmetic_only": chains,
        "ranking_or_chokepoint_stability_tested": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Output exists; choose a new evidence file")
    if args.output.resolve().is_relative_to((ROOT / "data/raw").resolve()):
        parser.error("Output must be outside immutable raw data")
    sources_path, scenarios_path = PACKAGE / "sources.json", PACKAGE / "scenarios.proposed.json"
    sources = json.loads(sources_path.read_text(encoding="utf-8"))
    packet = json.loads(scenarios_path.read_text(encoding="utf-8"))
    report = audit(sources, packet)
    report["sensitivity"] = sensitivity(sources, packet)
    report["input_sha256"] = {
        p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in (sources_path, scenarios_path, Path(__file__))
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, ensure_ascii=False, sort_keys=True, indent=2)
        stream.write("\n")
    print(json.dumps({"proposals_checked": len(report["proposals"]), "records_emitted": 0}))


if __name__ == "__main__":
    main()
