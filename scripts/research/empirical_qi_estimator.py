"""Empirical conditional probability estimator and calibration protocol.

Implements defensible statistical derivation of q_i from empirical trial evidence:
- Wilson score interval for binomial proportion (NIST Handbook PRC 2.4.1).
- Outer conservative rational fraction conversion (preserves interval coverage).
- Fail-closed refusal behavior for unrepresentative domain transfer (case-insensitive SEAMLESS).
- Fail-closed refusal for unseen production domains outside verified lab evidence scope.
- Fail-closed rejection of synthetic test fixtures and missing context metadata.
- Full-history conditioning and strict prefix sequence validation (no unmeasured prior history).
- Strict parameter matching (method, budget, horizon) for i.i.d. Bernoulli trials.
- Validation of trial outcomes (success/failure) rejecting censored or invalid trial runs.
- Validation of required provenance metadata on every trial observation.
- Deduplication of repeated trials on identical hashes with
  order-independent contradictory duplicate rejection.
- Data leakage interception checking stable identity overlap between training and holdout sets.
- Single-split consistency diagnostic reporting (holdout rate in predicted interval).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from dataclasses import asdict, dataclass
from fractions import Fraction
from pathlib import Path
from typing import Any

Z_95: float = 1.959963984540054
MIN_SAMPLE_SIZE: int = 20
SUPPORTED_TECHNIQUES: frozenset[str] = frozenset({"recover_asrep_secret", "recover_ticket_secret"})
TECHNIQUE_PREREQUISITES: dict[str, str] = {
    "recover_asrep_secret": "asrep_request",
    "recover_ticket_secret": "kerberoast_request",
}
SUPPORTED_SCENARIOS: frozenset[str] = frozenset(
    {
        "lab-benchmark-asrep-v1",
        "lab-benchmark-v1",
        "lab://benchmarks/asrep/v1",
        "lab-scenario-01",
        "lab-benchmark-scenario",
        "lab-scenario",
    }
)
SUPPORTED_ACTOR_CAPABILITIES: frozenset[str] = frozenset(
    {"offline_gpu_cracking", "offline_hash_cracking"}
)
VALID_COMPLETED_OUTCOMES: frozenset[str] = frozenset({"success", "failure"})


def resolve_step_technique(step: Any, aliases: dict[str, str] | None = None) -> str:
    """Resolve an action or work unit step identifier to canonical technique name."""
    if not isinstance(step, str) or not step.strip():
        return ""
    if aliases and step in aliases:
        return aliases[step]
    if step in SUPPORTED_TECHNIQUES or step in TECHNIQUE_PREREQUISITES.values():
        return step
    for prefix_str in ("work_", "action_"):
        if step.startswith(prefix_str):
            remainder = step[len(prefix_str) :]
            if remainder in SUPPORTED_TECHNIQUES or remainder in TECHNIQUE_PREREQUISITES.values():
                return remainder
    for tech in SUPPORTED_TECHNIQUES | frozenset(TECHNIQUE_PREREQUISITES.values()):
        if step.endswith(f"_{tech}"):
            return tech
    return step


@dataclass(frozen=True)
class TrialObservation:
    """Single empirical trial observation record."""

    trial_id: str
    technique: str
    method: str
    budget: int
    horizon_seconds: float
    target_complexity_class: str
    outcome: str  # Strictly "success" or "failure"
    target_hash_id: str
    provenance_reference: str
    artifact_digest: str | None = None


@dataclass(frozen=True)
class EstimatorContext:
    """Target evaluation context and boundary constraints."""

    technique: str
    method: str | None
    budget: int | None
    horizon_seconds: float | None
    target_complexity_class: str | None
    scenario_id: str
    is_synthetic_fixture: bool = False
    initial_material_present: bool = False
    action_aliases: dict[str, str] | None = None
    actor_capability: str | None = None


@dataclass(frozen=True)
class EstimatorResult:
    """Structured estimator result with explicit basis and refusal reasons."""

    status: str  # "rated" or "unrated"
    lower_bound: float | None
    upper_bound: float | None
    lower_fraction: str | None
    upper_fraction: str | None
    point_estimate: float | None
    sample_size: int
    success_count: int
    confidence_level: float
    basis_category: str
    missing_basis_reasons: list[str]
    rationale: str
    dataset_classification: str = "controlled_lab_benchmark_prototype"
    evidence_disposition: str = "quarantined_prototype_not_for_production_ranking"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def wilson_score_interval(n: int, k: int, z: float = Z_95) -> tuple[float, float]:
    """Compute Wilson score interval for binomial proportion.

    Formula from NIST Handbook PRC Section 2.4.1.
    Handles boundary cases k=0 and k=n safely.
    """
    if z <= 0.0:
        raise ValueError(f"Critical value z must be positive, got {z}")
    if n <= 0:
        raise ValueError(f"Sample size n must be positive, got {n}")
    if not (0 <= k <= n):
        raise ValueError(f"Success count k must be between 0 and n, got {k} for n={n}")

    p_hat = k / n
    denominator = 1.0 + (z * z) / n
    center = (p_hat + (z * z) / (2.0 * n)) / denominator
    spread = z * math.sqrt((p_hat * (1.0 - p_hat) / n) + (z * z) / (4.0 * (n * n))) / denominator

    lower = 0.0 if k == 0 else max(0.0, center - spread)
    upper = 1.0 if k == n else min(1.0, center + spread)
    return lower, upper


def rationalize_conservative_bounds(
    lower: float, upper: float, max_denominator: int = 1000
) -> tuple[Fraction, Fraction]:
    """Convert float interval [lower, upper] to Fraction [l_frac, u_frac].

    Enforces outer conservative rounding:
    l_frac <= lower <= upper <= u_frac
    such that empirical coverage is strictly preserved.
    """
    if max_denominator <= 0:
        raise ValueError(f"max_denominator must be positive, got {max_denominator}")
    if math.isnan(lower) or math.isnan(upper):
        raise ValueError(f"Interval bounds cannot be NaN: [{lower}, {upper}]")
    if not (0.0 <= lower <= upper <= 1.0):
        raise ValueError(f"Invalid interval [{lower}, {upper}]")

    # Round lower bound downward (floor)
    l_num = math.floor(lower * max_denominator)
    l_frac = Fraction(max(0, l_num), max_denominator)

    # Round upper bound upward (ceil)
    u_num = math.ceil(upper * max_denominator)
    u_frac = Fraction(min(max_denominator, u_num), max_denominator)

    # Strict invariant verification
    if float(l_frac) > lower + 1e-12:
        raise ValueError(f"Floor fraction {l_frac} strictly exceeds lower bound {lower}")
    if float(u_frac) < upper - 1e-12:
        raise ValueError(f"Ceil fraction {u_frac} strictly below upper bound {upper}")
    if not (Fraction(0, 1) <= l_frac <= u_frac <= Fraction(1, 1)):
        raise ValueError(f"Rational bounds out of [0, 1] range: [{l_frac}, {u_frac}]")

    return l_frac, u_frac


class EmpiricalQiEstimator:
    """Empirical conditional success probability estimator."""

    def __init__(
        self,
        min_sample_size: int = MIN_SAMPLE_SIZE,
        supported_scenarios: frozenset[str] | set[str] | None = None,
        manifest: dict[str, Any] | None = None,
        dataset_classification: str | None = None,
    ) -> None:
        if min_sample_size <= 0:
            raise ValueError(f"min_sample_size must be positive, got {min_sample_size}")
        self.min_sample_size = min_sample_size
        self._manifest = manifest or {}

        # Authoritative classification from manifest
        self._manifest_classification: str | None = None
        if isinstance(self._manifest, dict) and "dataset_classification" in self._manifest:
            m_cls = self._manifest["dataset_classification"]
            if m_cls is not None:
                self._manifest_classification = str(m_cls)

        self._caller_classification: str | None = (
            str(dataset_classification) if dataset_classification is not None else None
        )
        self._has_classification_conflict: bool = False

        if (
            self._manifest_classification is not None
            and self._caller_classification is not None
            and self._manifest_classification != self._caller_classification
        ):
            self._has_classification_conflict = True

        # Manifest is authoritative for evidence dataset classification
        if self._manifest_classification is not None:
            self.dataset_classification = self._manifest_classification
        elif self._caller_classification is not None:
            self.dataset_classification = self._caller_classification
        else:
            self.dataset_classification = "controlled_lab_benchmark_prototype"

        if supported_scenarios is not None:
            self._supported_scenarios = frozenset(supported_scenarios)
        elif (
            "supported_scenario_ids" in self._manifest
            and self._manifest["supported_scenario_ids"] is not None
        ):
            # Strict evidence manifest boundary: do not union with default test aliases
            self._supported_scenarios = frozenset(self._manifest["supported_scenario_ids"])
        else:
            self._supported_scenarios = SUPPORTED_SCENARIOS
        self._observations: list[TrialObservation] = []

    @property
    def is_reviewed_evidence_package(self) -> bool:
        """Check whether evidence package is an approved, reviewed empirical package.

        In milestone #237, all empirical measurements on live Active Directory infrastructure
        are explicitly DEFERRED. A reviewed evidence package requires:
        1. A verified evidence manifest dictionary
        2. dataset_classification == 'empirical_measurement' (not prototype or synthetic)
        3. review_status == 'reviewed' (not unreviewed or draft)
        4. Non-empty reviewed_by identifier
        5. Non-empty reviewed_at timestamp (ISO 8601)
        Without an approved, reviewed evidence package, evidence cannot be promoted
        to production_empirical_calibration and cannot enter production ranking.
        """
        if not isinstance(self._manifest, dict) or not self._manifest:
            return False
        if getattr(self, "_has_classification_conflict", False):
            return False
        if self.dataset_classification == "controlled_lab_benchmark_prototype":
            return False
        if self._manifest.get("dataset_classification") == "controlled_lab_benchmark_prototype":
            return False
        if self.dataset_classification != "empirical_measurement":
            return False
        if self._manifest.get("review_status") != "reviewed":
            return False
        reviewed_by = self._manifest.get("reviewed_by")
        if not reviewed_by or not str(reviewed_by).strip():
            return False
        reviewed_at = self._manifest.get("reviewed_at")
        if not reviewed_at or not str(reviewed_at).strip():
            return False
        return True

    def fit(
        self,
        observations: list[TrialObservation],
        dataset_classification: str | None = None,
    ) -> None:
        """Ingest empirical trial observations."""
        self._observations = list(observations)
        if dataset_classification is not None:
            fit_cls = str(dataset_classification)
            if self._manifest_classification is not None:
                if self._manifest_classification != fit_cls:
                    self._has_classification_conflict = True
            elif self._caller_classification is not None:
                if self._caller_classification != fit_cls:
                    self._has_classification_conflict = True
            else:
                self.dataset_classification = fit_cls

    def estimate(self, context: EstimatorContext, prefix: tuple[str, ...]) -> EstimatorResult:
        """Estimate conditional likelihood interval or fail closed with reasons."""
        missing_reasons: list[str] = []

        # 1. Refusal check: synthetic test fixtures are software fixtures, not empirical evidence
        if context.is_synthetic_fixture or self.dataset_classification in (
            "synthetic",
            "synthetic_test_fixture",
            "synthetic_fixture",
        ):
            missing_reasons.append("synthetic_test_fixture_rejected_as_evidence")

        # 1b. Refusal check: conflicting dataset classification between caller and manifest
        if getattr(self, "_has_classification_conflict", False):
            missing_reasons.append(
                "conflicting_dataset_classification: caller classification conflicts with "
                "authoritative manifest specification"
            )

        # 1c. Refusal check: missing manifest when empirical measurement is claimed
        if self.dataset_classification == "empirical_measurement":
            if not isinstance(self._manifest, dict) or not self._manifest:
                missing_reasons.append(
                    "missing_evidence_manifest: empirical measurement claims require an "
                    "authoritative evidence manifest"
                )
            elif not self.is_reviewed_evidence_package:
                missing_reasons.append(
                    "unreviewed_evidence_manifest: empirical measurement evidence requires an "
                    "approved reviewed evidence package"
                )

        # 1d. Refusal check: prototype observations cannot be promoted to empirical measurement
        if self.dataset_classification == "empirical_measurement" and self._observations:
            if any(
                obs.provenance_reference.startswith("lab://")
                or "benchmark" in obs.provenance_reference
                for obs in self._observations
            ):
                missing_reasons.append(
                    "unverified_prototype_provenance: prototype observations cannot be promoted "
                    "to empirical measurement evidence"
                )

        # 2. Refusal check: unrepresentative domain transfer (case-insensitive SEAMLESS)
        if re.search(r"seamless", context.scenario_id, re.IGNORECASE):
            missing_reasons.append(
                "unrepresentative_domain_transfer_seamless: "
                "no empirical password distribution or telemetry observed in SEAMLESS snapshot"
            )
        elif context.scenario_id not in self._supported_scenarios:
            missing_reasons.append(
                f"unsupported_domain_or_scenario: scenario {context.scenario_id!r} is not within "
                f"verified evidence scope (supported: {sorted(self._supported_scenarios)})"
            )

        # 2b. Refusal check: actor capability binding
        if (
            "supported_actor_capabilities" in self._manifest
            and self._manifest["supported_actor_capabilities"] is not None
        ):
            supported_capabilities = frozenset(self._manifest["supported_actor_capabilities"])
            if not context.actor_capability or not context.actor_capability.strip():
                missing_reasons.append(
                    "missing_actor_capability_specification: actor_capability must be explicitly "
                    f"specified to bind against manifest evidence capability "
                    f"(supported: {sorted(supported_capabilities)})"
                )
            elif context.actor_capability not in supported_capabilities:
                missing_reasons.append(
                    f"unsupported_actor_capability: actor capability {context.actor_capability!r} "
                    f"is not supported by evidence (supported: {sorted(supported_capabilities)})"
                )
        else:
            if context.actor_capability is not None:
                if (
                    not context.actor_capability.strip()
                    or context.actor_capability not in SUPPORTED_ACTOR_CAPABILITIES
                ):
                    missing_reasons.append(
                        f"unsupported_actor_capability: actor capability "
                        f"{context.actor_capability!r} is not supported by evidence "
                        f"(supported: {sorted(SUPPORTED_ACTOR_CAPABILITIES)})"
                    )

        # 3. Refusal check: unsupported technique
        if context.technique not in SUPPORTED_TECHNIQUES:
            missing_reasons.append(
                f"out_of_scope_technique: {context.technique!r} not supported by recovery pilot"
            )

        # 4. Refusal check: required context metadata
        if not context.method or not context.method.strip():
            missing_reasons.append("missing_method_specification")
        if (
            context.budget is None
            or isinstance(context.budget, bool)
            or not isinstance(context.budget, int)
            or context.budget <= 0
        ):
            missing_reasons.append("missing_budget_specification")
        if (
            context.horizon_seconds is None
            or isinstance(context.horizon_seconds, bool)
            or not isinstance(context.horizon_seconds, (int, float))
            or context.horizon_seconds <= 0.0
            or not math.isfinite(context.horizon_seconds)
        ):
            missing_reasons.append("missing_horizon_specification")
        if not context.target_complexity_class or not context.target_complexity_class.strip():
            missing_reasons.append("missing_target_complexity_class_specification")

        # 5. Full-history conditioning and prefix sequence validation
        if len(prefix) == 0:
            missing_reasons.append("empty_prefix: prefix tuple cannot be empty")
        else:
            invalid_steps = [
                f"step[{idx}]={s!r}"
                for idx, s in enumerate(prefix)
                if not isinstance(s, str) or not s.strip()
            ]
            if invalid_steps:
                missing_reasons.append(
                    f"invalid_prefix_step_identifier: prefix contains non-string or empty "
                    f"step identifiers: {', '.join(invalid_steps)}"
                )
            else:
                target_step = prefix[-1]
                resolved_target = resolve_step_technique(target_step, context.action_aliases)
                if resolved_target != context.technique:
                    missing_reasons.append(
                        f"prefix_action_mismatch: target step {target_step!r} does not correspond "
                        f"to technique {context.technique!r}"
                    )

                resolved_prefix = tuple(
                    resolve_step_technique(s, context.action_aliases) for s in prefix
                )

                if not context.initial_material_present:
                    prereq_tech = TECHNIQUE_PREREQUISITES.get(context.technique)
                    if prereq_tech and prereq_tech not in resolved_prefix[:-1]:
                        missing_reasons.append(
                            f"missing_prerequisite_in_history: technique "
                            f"{context.technique!r} requires prior material acquisition "
                            f"{prereq_tech!r} in prefix history, found {list(prefix[:-1])}"
                        )

                # Check manifest supported prefix sequences if declared
                manifest_prefixes = (
                    {tuple(seq) for seq in self._manifest["supported_prefix_sequences"]}
                    if (
                        "supported_prefix_sequences" in self._manifest
                        and self._manifest["supported_prefix_sequences"] is not None
                    )
                    else None
                )

                if manifest_prefixes is not None:
                    if resolved_prefix not in manifest_prefixes:
                        missing_reasons.append(
                            f"unsupported_prefix_history: prefix sequence {list(prefix)} "
                            f"is not supported by evidence manifest (supported sequences: "
                            f"{sorted(list(s) for s in manifest_prefixes)})"
                        )
                    if context.initial_material_present and not any(
                        len(seq) == 1 and seq[0] == context.technique for seq in manifest_prefixes
                    ):
                        missing_reasons.append(
                            "unsupported_prefix_history: initial_material_present=True "
                            "is not supported by evidence manifest without prerequisite "
                            "acquisition step"
                        )
                else:
                    if not context.initial_material_present:
                        prereq_tech = TECHNIQUE_PREREQUISITES.get(context.technique)
                        expected_canonical = (
                            (prereq_tech, context.technique)
                            if prereq_tech
                            else (context.technique,)
                        )
                        if resolved_prefix != expected_canonical and not any(
                            r.startswith("prefix_action_mismatch")
                            or r.startswith("missing_prerequisite")
                            for r in missing_reasons
                        ):
                            missing_reasons.append(
                                f"unsupported_prefix_history: prefix sequence {list(prefix)} "
                                f"contains history conditions not supported by empirical evidence "
                                f"(supported sequence: {list(expected_canonical)})"
                            )
                    else:
                        expected_canonical = (context.technique,)
                        if resolved_prefix != expected_canonical and not any(
                            r.startswith("prefix_action_mismatch") for r in missing_reasons
                        ):
                            missing_reasons.append(
                                f"unsupported_prefix_history: prefix sequence {list(prefix)} "
                                f"contains history conditions not supported by empirical evidence "
                                f"(supported sequence: {list(expected_canonical)})"
                            )

        if missing_reasons:
            return EstimatorResult(
                status="unrated",
                lower_bound=None,
                upper_bound=None,
                lower_fraction=None,
                upper_fraction=None,
                point_estimate=None,
                sample_size=0,
                success_count=0,
                confidence_level=0.95,
                basis_category="insufficient_evidence",
                missing_basis_reasons=missing_reasons,
                rationale=("Fail-closed refusal: " + "; ".join(missing_reasons)),
                dataset_classification=self.dataset_classification,
                evidence_disposition="unrated",
            )

        # 6. Filter matching empirical observations (exact parameterization for i.i.d. Bernoulli)
        matching = [
            obs
            for obs in self._observations
            if obs.technique == context.technique
            and obs.method == context.method
            and obs.budget == context.budget
            and math.isclose(obs.horizon_seconds, context.horizon_seconds, rel_tol=1e-6)
            and obs.target_complexity_class == context.target_complexity_class
        ]

        # 7. Validate metadata, outcomes, and repeated trial consistency on matching observations
        obs_reasons: list[str] = []
        for obs in matching:
            if not obs.trial_id or not obs.trial_id.strip():
                obs_reasons.append("missing_trial_id: observation has empty trial_id")
            if not obs.target_hash_id or not obs.target_hash_id.strip():
                obs_reasons.append(
                    f"missing_target_hash_id: trial {obs.trial_id!r} has empty target_hash_id"
                )
            if not obs.provenance_reference or not obs.provenance_reference.strip():
                obs_reasons.append(
                    f"missing_provenance_metadata: trial {obs.trial_id!r} has empty "
                    "provenance_reference"
                )
            if obs.outcome not in VALID_COMPLETED_OUTCOMES:
                obs_reasons.append(
                    f"censored_or_invalid_trial_outcome: trial {obs.trial_id!r} has non-completed "
                    f"outcome {obs.outcome!r}; censored or invalid runs cannot be treated as "
                    "completed Bernoulli trials"
                )

        hash_groups: dict[str, list[TrialObservation]] = {}
        for obs in matching:
            hash_groups.setdefault(obs.target_hash_id, []).append(obs)

        for hash_id, group in hash_groups.items():
            completed_outcomes = {o.outcome for o in group if o.outcome in VALID_COMPLETED_OUTCOMES}
            if len(completed_outcomes) > 1:
                obs_reasons.append(
                    f"contradictory_repeated_trials: target_hash_id {hash_id!r} has conflicting "
                    f"outcomes {sorted(completed_outcomes)} across repeated trials"
                )

        if obs_reasons:
            return EstimatorResult(
                status="unrated",
                lower_bound=None,
                upper_bound=None,
                lower_fraction=None,
                upper_fraction=None,
                point_estimate=None,
                sample_size=0,
                success_count=0,
                confidence_level=0.95,
                basis_category="insufficient_evidence",
                missing_basis_reasons=obs_reasons,
                rationale=("Fail-closed refusal: " + "; ".join(obs_reasons)),
                dataset_classification=self.dataset_classification,
                evidence_disposition="unrated",
            )

        # 8. Check independent sample size
        # Each hash group has exactly one unique outcome
        independent_matching: list[TrialObservation] = [group[0] for group in hash_groups.values()]
        n = len(independent_matching)
        discarded_repeated = len(matching) - n

        if n < self.min_sample_size:
            dep_msg = (
                f" ({discarded_repeated} dependent repeated trials on identical hashes discarded)"
                if discarded_repeated > 0
                else ""
            )
            reason = (
                f"insufficient_sample_size: observed n={n} independent trials{dep_msg}, "
                f"required minimum n={self.min_sample_size}"
            )
            return EstimatorResult(
                status="unrated",
                lower_bound=None,
                upper_bound=None,
                lower_fraction=None,
                upper_fraction=None,
                point_estimate=None,
                sample_size=n,
                success_count=sum(1 for o in independent_matching if o.outcome == "success"),
                confidence_level=0.95,
                basis_category="insufficient_evidence",
                missing_basis_reasons=[reason],
                rationale=f"Fail-closed refusal: {reason}",
                dataset_classification=self.dataset_classification,
                evidence_disposition="unrated",
            )

        # 9. Compute empirical binomial statistics
        k = sum(1 for o in independent_matching if o.outcome == "success")
        p_hat = k / n
        lo, hi = wilson_score_interval(n, k, z=Z_95)
        lo_frac, hi_frac = rationalize_conservative_bounds(lo, hi, max_denominator=1000)

        if self.is_reviewed_evidence_package:
            basis_category = "empirical_calibration"
            evidence_disposition = "production_empirical_calibration"
            rationale = (
                f"Empirical Wilson 95% confidence interval derived from n={n} independent "
                f"lab benchmark trials (k={k} successes, p_hat={p_hat:.4f}). "
                f"Method: {context.method}, Budget: {context.budget}, "
                f"Horizon: {context.horizon_seconds}s. "
                f"Outer rational bounds: [{lo_frac}, {hi_frac}]."
            )
        elif self.dataset_classification == "controlled_lab_benchmark_prototype":
            basis_category = "controlled_lab_benchmark_prototype"
            evidence_disposition = "quarantined_prototype_not_for_production_ranking"
            rationale = (
                f"Controlled lab benchmark prototype Wilson 95% interval derived from n={n} "
                f"prototype trials (k={k} successes, p_hat={p_hat:.4f}). "
                f"Method: {context.method}, Budget: {context.budget}, "
                f"Horizon: {context.horizon_seconds}s. "
                f"Outer rational bounds: [{lo_frac}, {hi_frac}]. "
                "Notice: Classified as software benchmark prototype; quarantined from "
                "production ranking."
            )
        else:
            basis_category = f"unverified_{self.dataset_classification}"
            evidence_disposition = "quarantined_unverified_evidence"
            rationale = (
                f"Wilson 95% interval derived from n={n} trials under classification "
                f"{self.dataset_classification!r} (k={k} successes, p_hat={p_hat:.4f}). "
                f"Method: {context.method}, Budget: {context.budget}, "
                f"Horizon: {context.horizon_seconds}s. "
                f"Outer rational bounds: [{lo_frac}, {hi_frac}]. "
                "Notice: Quarantined pending approved reviewed evidence package."
            )

        return EstimatorResult(
            status="rated",
            lower_bound=lo,
            upper_bound=hi,
            lower_fraction=f"{lo_frac.numerator}/{lo_frac.denominator}",
            upper_fraction=f"{hi_frac.numerator}/{hi_frac.denominator}",
            point_estimate=p_hat,
            sample_size=n,
            success_count=k,
            confidence_level=0.95,
            basis_category=basis_category,
            missing_basis_reasons=[],
            rationale=rationale,
            dataset_classification=self.dataset_classification,
            evidence_disposition=evidence_disposition,
        )

    def export_bounds_table_entry(
        self,
        context: EstimatorContext,
        prefix: tuple[str, ...],
        for_production_ranking: bool = False,
    ) -> dict[str, Any] | None:
        """Export entry for conditional_bounds_table conforming to validation schema.

        If for_production_ranking=True, production empirical export is deferred/disabled
        in milestone #237 until an authentic, reviewed empirical evidence package on live
        Active Directory is approved and integrated. Prototype fixtures and unreviewed
        datasets are strictly quarantined and return None to prevent unverified data
        from acting as empirical basis in production ranking.
        """
        if for_production_ranking:
            # Under Issue #237, empirical measurements on live Active Directory infrastructure
            # are explicitly DEFERRED. Production empirical export is deferred/disabled until
            # an authentic reviewed evidence package is approved and available.
            return None

        res = self.estimate(context, prefix)
        if res.status != "rated" or res.lower_fraction is None or res.upper_fraction is None:
            return None

        return {
            "prefix": list(prefix),
            "lower": res.lower_fraction,
            "upper": res.upper_fraction,
            "basis_category": res.basis_category,
            "dataset_classification": res.dataset_classification,
            "evidence_disposition": res.evidence_disposition,
            "rationale": res.rationale,
        }


def evaluate_holdout_quality(
    estimator: EmpiricalQiEstimator,
    context: EstimatorContext,
    holdout_observations: list[TrialObservation],
    prefix: tuple[str, ...] | None = None,
) -> dict[str, Any]:
    """Evaluate predictive quality on independent holdout dataset."""
    if prefix is None:
        prereq = TECHNIQUE_PREREQUISITES.get(context.technique, "asrep_request")
        prefix = (prereq, context.technique)
    res = estimator.estimate(context, prefix)

    if res.status != "rated" or res.lower_bound is None or res.upper_bound is None:
        return {
            "status": "unrated",
            "refusal_reason": "; ".join(res.missing_basis_reasons),
            "refusal_reasons": res.missing_basis_reasons,
            "sample_size": len(holdout_observations),
            "holdout_sample_size": len(holdout_observations),
        }

    # Intercept data leakage: check overlap between training and holdout units
    train_hashes = {
        o.target_hash_id
        for o in estimator._observations
        if o.target_hash_id and o.target_hash_id.strip()
    }
    train_trials = {
        o.trial_id for o in estimator._observations if o.trial_id and o.trial_id.strip()
    }
    train_provs = {
        o.provenance_reference
        for o in estimator._observations
        if o.provenance_reference and o.provenance_reference.strip()
    }
    train_digests = {
        o.artifact_digest
        for o in estimator._observations
        if o.artifact_digest and o.artifact_digest.strip()
    }

    overlapping_hashes = {
        o.target_hash_id
        for o in holdout_observations
        if o.target_hash_id and o.target_hash_id in train_hashes
    }
    overlapping_trials = {
        o.trial_id for o in holdout_observations if o.trial_id and o.trial_id in train_trials
    }
    overlapping_provs = {
        o.provenance_reference
        for o in holdout_observations
        if o.provenance_reference and o.provenance_reference in train_provs
    }
    overlapping_digests = {
        o.artifact_digest
        for o in holdout_observations
        if o.artifact_digest and o.artifact_digest in train_digests
    }

    if overlapping_hashes or overlapping_trials or overlapping_provs or overlapping_digests:
        reason = (
            f"train_holdout_overlap_detected: {len(overlapping_hashes)} target hashes, "
            f"{len(overlapping_trials)} trials, {len(overlapping_provs)} "
            f"provenance references, and {len(overlapping_digests)} artifact digests "
            "overlap between training and holdout sets"
        )
        return {
            "status": "leakage_detected",
            "diagnostic": "train_holdout_overlap_detected",
            "overlapping_hash_count": len(overlapping_hashes),
            "overlapping_hashes": sorted(overlapping_hashes),
            "overlapping_trial_count": len(overlapping_trials),
            "overlapping_trials": sorted(overlapping_trials),
            "overlapping_provenance_count": len(overlapping_provs),
            "overlapping_digest_count": len(overlapping_digests),
            "overlapping_digests": sorted(overlapping_digests),
            "sample_size": len(holdout_observations),
            "holdout_sample_size": len(holdout_observations),
            "refusal_reason": reason,
            "refusal_reasons": [reason],
        }

    # Filter holdout observations matching context exactly
    matching_holdout = [
        obs
        for obs in holdout_observations
        if obs.technique == context.technique
        and obs.method == context.method
        and obs.budget == context.budget
        and (
            context.horizon_seconds is not None
            and math.isclose(obs.horizon_seconds, context.horizon_seconds, rel_tol=1e-6)
        )
        and obs.target_complexity_class == context.target_complexity_class
    ]

    # Validate holdout records
    for obs in matching_holdout:
        if not obs.trial_id or not obs.trial_id.strip():
            reason = "missing_trial_id: holdout observation has empty trial_id"
            return {
                "status": "invalid_holdout_data",
                "refusal_reason": reason,
                "refusal_reasons": [reason],
                "sample_size": len(matching_holdout),
                "holdout_sample_size": len(matching_holdout),
            }
        if not obs.target_hash_id or not obs.target_hash_id.strip():
            reason = (
                f"missing_target_hash_id: holdout trial {obs.trial_id!r} has empty target_hash_id"
            )
            return {
                "status": "invalid_holdout_data",
                "refusal_reason": reason,
                "refusal_reasons": [reason],
                "sample_size": len(matching_holdout),
                "holdout_sample_size": len(matching_holdout),
            }
        if not obs.provenance_reference or not obs.provenance_reference.strip():
            reason = (
                f"missing_provenance_metadata: holdout trial {obs.trial_id!r} has empty "
                "provenance_reference"
            )
            return {
                "status": "invalid_holdout_data",
                "refusal_reason": reason,
                "refusal_reasons": [reason],
                "sample_size": len(matching_holdout),
                "holdout_sample_size": len(matching_holdout),
            }
        if obs.outcome not in VALID_COMPLETED_OUTCOMES:
            reason = (
                f"censored_or_invalid_trial_outcome: holdout trial {obs.trial_id!r} has "
                f"non-completed outcome {obs.outcome!r}"
            )
            return {
                "status": "invalid_holdout_data",
                "refusal_reason": reason,
                "refusal_reasons": [reason],
                "sample_size": len(matching_holdout),
                "holdout_sample_size": len(matching_holdout),
            }

    # Deduplicate repeated trial hashes on holdout set
    holdout_groups: dict[str, list[TrialObservation]] = {}
    for obs in matching_holdout:
        holdout_groups.setdefault(obs.target_hash_id, []).append(obs)

    for hash_id, group in holdout_groups.items():
        outcomes = {o.outcome for o in group}
        if len(outcomes) > 1:
            reason = (
                f"contradictory_repeated_trials: holdout hash {hash_id!r} has conflicting "
                f"outcomes {sorted(outcomes)}"
            )
            return {
                "status": "contradictory_holdout_data",
                "refusal_reason": reason,
                "refusal_reasons": [reason],
                "sample_size": len(matching_holdout),
                "holdout_sample_size": len(matching_holdout),
            }

    independent_holdout = [group[0] for group in holdout_groups.values()]
    n_test = len(independent_holdout)
    if n_test == 0:
        reason = "empty_holdout: no matching independent holdout observations found"
        return {
            "status": "empty_holdout",
            "refusal_reason": reason,
            "refusal_reasons": [reason],
            "sample_size": 0,
            "holdout_sample_size": 0,
        }

    y_true = [1.0 if o.outcome == "success" else 0.0 for o in independent_holdout]
    holdout_success_rate = sum(y_true) / n_test

    # Single-split consistency diagnostic: does the holdout rate fall inside predicted Wilson CI?
    in_interval = res.lower_bound <= holdout_success_rate <= res.upper_bound
    interval_width = res.upper_bound - res.lower_bound

    # Point predictions: Brier score and log loss evaluated using posterior mean (Laplace shrinkage)
    p_pred = (res.success_count + 1.0) / (res.sample_size + 2.0)

    brier_score = sum((p_pred - y) ** 2 for y in y_true) / n_test

    eps = 1e-12
    p_pred_clamped = min(max(p_pred, eps), 1.0 - eps)
    log_loss = (
        -sum(
            y * math.log(p_pred_clamped) + (1.0 - y) * math.log(1.0 - p_pred_clamped)
            for y in y_true
        )
        / n_test
    )

    return {
        "status": "evaluated",
        "train_sample_size": res.sample_size,
        "train_successes": res.success_count,
        "train_p_hat": res.point_estimate,
        "confidence_level": res.confidence_level,
        "predicted_interval": (res.lower_bound, res.upper_bound),
        "predicted_rational_bounds": (res.lower_fraction, res.upper_fraction),
        "interval_width": interval_width,
        "holdout_sample_size": n_test,
        "holdout_empirical_rate": holdout_success_rate,
        "holdout_rate_in_interval_diagnostic": in_interval,
        "coverage_hit": in_interval,
        "coverage_diagnostic_note": (
            "Single-split consistency diagnostic only (whether holdout empirical rate falls within "
            "predicted Wilson CI). Does not establish repeated-sampling coverage or complete "
            "probability calibration."
        ),
        "point_prediction": p_pred,
        "brier_score": brier_score,
        "log_loss": log_loss,
    }


def compute_dataset_digest(data: Any) -> str:
    """Compute deterministic SHA-256 digest of json-serializable data."""
    raw = json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return f"sha256:{hashlib.sha256(raw.encode('utf-8')).hexdigest()}"


def run_full_evaluation(
    fixtures_dir: Path | None = None,
    output_path: Path | None = None,
) -> dict[str, Any]:
    """Run full calibration evaluation protocol and produce auditable JSON report."""
    if fixtures_dir is None:
        fixtures_dir = (
            Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "empirical_calibration"
        )

    # 1. Load benchmark dataset
    dataset_file = fixtures_dir / "lab_benchmark_dataset.json"
    with open(dataset_file, encoding="utf-8") as f:
        raw_dataset = json.load(f)
    dataset_digest = compute_dataset_digest(raw_dataset)

    common = raw_dataset["common_parameters"]
    train_obs = [
        TrialObservation(
            trial_id=item["trial_id"],
            technique=common["technique"],
            method=common["method"],
            budget=common["budget"],
            horizon_seconds=common["horizon_seconds"],
            target_complexity_class=common["target_complexity_class"],
            outcome=item["outcome"],
            target_hash_id=item["target_hash_id"],
            provenance_reference=item["provenance_reference"],
            artifact_digest=item.get("artifact_digest"),
        )
        for item in raw_dataset["training_observations"]
    ]

    holdout_obs = [
        TrialObservation(
            trial_id=item["trial_id"],
            technique=common["technique"],
            method=common["method"],
            budget=common["budget"],
            horizon_seconds=common["horizon_seconds"],
            target_complexity_class=common["target_complexity_class"],
            outcome=item["outcome"],
            target_hash_id=item["target_hash_id"],
            provenance_reference=item["provenance_reference"],
            artifact_digest=item.get("artifact_digest"),
        )
        for item in raw_dataset["holdout_observations"]
    ]

    # 2. Fit estimator on training observations with evidence manifest binding
    estimator = EmpiricalQiEstimator(
        min_sample_size=MIN_SAMPLE_SIZE,
        manifest=raw_dataset.get("evidence_manifest"),
        dataset_classification=raw_dataset.get(
            "dataset_classification", "controlled_lab_benchmark_prototype"
        ),
    )
    estimator.fit(train_obs)

    lab_context = EstimatorContext(
        technique=common["technique"],
        method=common["method"],
        budget=common["budget"],
        horizon_seconds=common["horizon_seconds"],
        target_complexity_class=common["target_complexity_class"],
        scenario_id="lab-benchmark-asrep-v1",
        is_synthetic_fixture=False,
        actor_capability="offline_gpu_cracking",
    )

    lab_prefix = ("asrep_request", "recover_asrep_secret")
    lab_estimation = estimator.estimate(lab_context, prefix=lab_prefix)
    bounds_entry = estimator.export_bounds_table_entry(lab_context, prefix=lab_prefix)
    prod_bounds_entry = estimator.export_bounds_table_entry(
        lab_context, prefix=lab_prefix, for_production_ranking=True
    )

    # 3. Evaluate holdout predictive quality
    holdout_metrics = evaluate_holdout_quality(
        estimator, lab_context, holdout_obs, prefix=lab_prefix
    )

    # 4. Evaluate refusal test cases
    refusal_file = fixtures_dir / "refusal_cases.json"
    with open(refusal_file, encoding="utf-8") as f:
        raw_refusals = json.load(f)

    refusal_results = []
    for case in raw_refusals["cases"]:
        raw_ctx = case["context"]
        ctx = EstimatorContext(
            technique=raw_ctx["technique"],
            method=raw_ctx["method"],
            budget=raw_ctx["budget"],
            horizon_seconds=raw_ctx["horizon_seconds"],
            target_complexity_class=raw_ctx["target_complexity_class"],
            scenario_id=raw_ctx["scenario_id"],
            is_synthetic_fixture=raw_ctx["is_synthetic_fixture"],
            initial_material_present=raw_ctx.get("initial_material_present", False),
            actor_capability=raw_ctx.get("actor_capability"),
        )
        case_prefix = tuple(case.get("prefix", ["asrep_request", raw_ctx["technique"]]))
        res = estimator.estimate(ctx, prefix=case_prefix)
        matches_expected = res.status == case["expected_status"] and any(
            case["expected_reason_substr"] in r for r in res.missing_basis_reasons
        )
        refusal_results.append(
            {
                "case_id": case["case_id"],
                "status": res.status,
                "missing_basis_reasons": res.missing_basis_reasons,
                "conformance_pass": matches_expected,
            }
        )

    # Build safe holdout evaluation report (preventing KeyError when unrated or refused)
    if holdout_metrics["status"] == "evaluated":
        holdout_report = {
            "status": "evaluated",
            "holdout_sample_size": holdout_metrics["holdout_sample_size"],
            "holdout_empirical_rate": holdout_metrics["holdout_empirical_rate"],
            "holdout_rate_in_interval_diagnostic": holdout_metrics[
                "holdout_rate_in_interval_diagnostic"
            ],
            "coverage_hit": holdout_metrics["coverage_hit"],
            "coverage_diagnostic_note": holdout_metrics["coverage_diagnostic_note"],
            "interval_width": holdout_metrics["interval_width"],
            "brier_score": holdout_metrics["brier_score"],
            "log_loss": holdout_metrics["log_loss"],
            "predicted_rational_bounds": holdout_metrics["predicted_rational_bounds"],
            "refusal_reason": None,
            "refusal_diagnostics": None,
        }
    else:
        excluded_keys = {
            "status",
            "sample_size",
            "holdout_sample_size",
            "refusal_reason",
            "refusal_reasons",
        }
        diagnostics = {k: v for k, v in holdout_metrics.items() if k not in excluded_keys}
        holdout_report = {
            "status": holdout_metrics["status"],
            "holdout_sample_size": holdout_metrics.get(
                "holdout_sample_size", holdout_metrics.get("sample_size", 0)
            ),
            "holdout_empirical_rate": None,
            "holdout_rate_in_interval_diagnostic": None,
            "coverage_hit": None,
            "coverage_diagnostic_note": None,
            "interval_width": None,
            "brier_score": None,
            "log_loss": None,
            "predicted_rational_bounds": None,
            "refusal_reason": holdout_metrics.get("refusal_reason"),
            "refusal_reasons": holdout_metrics.get("refusal_reasons"),
            "refusal_diagnostics": diagnostics if diagnostics else None,
        }

    # 5. Build full report structure
    report = {
        "report_id": "evidence-qi-calibration-237",
        "schema_version": "1.1.0",
        "evaluator": "Lolavine777",
        "pinned_revision": "develop@32ffd62ce9e65c20ccb032143bb8c8cb3dae259a",
        "dataset_digest": dataset_digest,
        "dataset_file": str(dataset_file.name),
        "dataset_classification": raw_dataset.get(
            "dataset_classification", "controlled_lab_benchmark_prototype"
        ),
        "lab_pilot_estimation": {
            "technique": common["technique"],
            "method": common["method"],
            "budget": common["budget"],
            "horizon_seconds": common["horizon_seconds"],
            "target_complexity_class": common["target_complexity_class"],
            "status": lab_estimation.status,
            "sample_size": lab_estimation.sample_size,
            "success_count": lab_estimation.success_count,
            "point_estimate": lab_estimation.point_estimate,
            "lower_bound": lab_estimation.lower_bound,
            "upper_bound": lab_estimation.upper_bound,
            "lower_fraction": lab_estimation.lower_fraction,
            "upper_fraction": lab_estimation.upper_fraction,
            "basis_category": lab_estimation.basis_category,
            "dataset_classification": lab_estimation.dataset_classification,
            "evidence_disposition": lab_estimation.evidence_disposition,
            "bounds_table_entry": bounds_entry,
            "production_ranking_bounds_table_entry": prod_bounds_entry,
        },
        "holdout_evaluation": holdout_report,
        "refusal_audit": {
            "total_cases": len(refusal_results),
            "all_passed": all(r["conformance_pass"] for r in refusal_results),
            "cases": refusal_results,
        },
        "baseline_comparison": {
            "status": "unavailable",
            "reason": "no_reviewed_baseline_for_technique",
            "explanation": (
                "No reviewed expert judgment baseline exists for recover_asrep_secret in Week 3 "
                "releases. Week 3 reviewed release only covered 11 parameters for other techniques "
                "(e.g. reset_password); Week 4 AS-REP #228 declared recover_asrep_secret unrated "
                "with missing_basis_reasons: ['no_numeric_basis']. Direct numeric comparison "
                "against the reset_password interval [3/5, 19/20] is methodologically invalid "
                "due to distinct attack events, policies, and contexts. A narrower confidence "
                "interval does not imply superiority."
            ),
            "seamless_status": "unrated",
            "seamless_disposition": (
                "Preserve unrated fail-closed due to lack of observed "
                "password distribution and telemetry in BloodHound snapshot"
            ),
        },
    }

    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
            f.write("\n")

    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Empirical Qi Estimator Evaluation")
    parser.add_argument("--output", type=Path, default=None, help="Output JSON report path")
    args = parser.parse_args()

    out_file = args.output or (
        Path(__file__).resolve().parents[2]
        / "reports"
        / "research"
        / "evidence-qi-calibration-237.json"
    )
    res = run_full_evaluation(output_path=out_file)
    print("Full evaluation completed successfully.")
    print(f"Report written to: {out_file}")
    print(f"Dataset digest: {res['dataset_digest']}")
    lo_str = res["lab_pilot_estimation"]["lower_fraction"]
    hi_str = res["lab_pilot_estimation"]["upper_fraction"]
    print(f"Lab Wilson 95% bounds: [{lo_str}, {hi_str}]")
    if res["holdout_evaluation"]["status"] == "evaluated":
        cov = res["holdout_evaluation"]["holdout_rate_in_interval_diagnostic"]
        rate = res["holdout_evaluation"]["holdout_empirical_rate"]
        print(f"Holdout rate in interval diagnostic: {cov} (rate: {rate:.4f})")
        bs = res["holdout_evaluation"]["brier_score"]
        ll = res["holdout_evaluation"]["log_loss"]
        print(f"Brier score: {bs:.4f}, Log loss: {ll:.4f}")
    else:
        print(f"Holdout evaluation status: {res['holdout_evaluation']['status']}")
        if res["holdout_evaluation"].get("refusal_reason"):
            print(f"Refusal reason: {res['holdout_evaluation']['refusal_reason']}")
    print(f"Refusal cases all passed: {res['refusal_audit']['all_passed']}")
