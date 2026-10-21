"""Conditional Likelihood (P) Provider Chain and Governance Boundary.

Implements the conditional likelihood provider chain for Issue #248, adhering to:
- Explicit provider precedence:
  1. Applicable reviewed empirical evidence.
  2. Reviewed full-history scenario/rubric interval where governance permits it.
  3. Otherwise fail-closed unrated.
- Strict full-history conditioning preserving ordered active-work prefixes.
- Anti-inference invariants:
  * No mapping of one technique-level marginal q onto arbitrary prefixes.
  * No inferring q_i from boolean runtime assumptions (assumption=true is never q=1).
  * No inferring q_i from C/effort, CVSS, MAUT, or LLM confidence.
- #238 estimator integration with prototype quarantine and refusal integrity.
- Refusal matrix differentiating absence, out-of-scope, malformed, contradictory,
  quarantined, and provider integrity refusals.
"""

from __future__ import annotations

import json
import math
import re
from collections.abc import Mapping, Sequence
from copy import deepcopy
from fractions import Fraction
from typing import Any

from scripts.research.empirical_qi_estimator import (
    EmpiricalQiEstimator,
    EstimatorContext,
    TrialObservation,
)
from src.engine.ranking.models import (
    RankingValidationError,
    parse_rational,
)
from src.engine.ranking.resolver import (
    RESOLVER_CONTRACT_VERSION,
    BasisClassification,
    FallbackUnratedProvider,
    LikelihoodLookupKey,
    LikelihoodRatingProvider,
    ReasonCode,
    ResolutionResult,
    ResolverDisposition,
)

HORIZON_SECONDS_MAP = {
    "s": 1.0,
    "m": 60.0,
    "h": 3600.0,
    "d": 86400.0,
}


def parse_horizon_seconds(horizon: str | int | float | None) -> float | None:
    """Parse horizon string or numeric value into seconds as float."""
    if horizon is None:
        return None
    if isinstance(horizon, (int, float)):
        return float(horizon)
    horizon_str = str(horizon).strip().lower()
    if not horizon_str:
        return None
    match = re.match(r"^(\d+(?:\.\d+)?)\s*([smhd]?)$", horizon_str)
    if not match:
        try:
            return float(horizon_str)
        except ValueError:
            return None
    value = float(match.group(1))
    unit = match.group(2) or "s"
    return value * HORIZON_SECONDS_MAP.get(unit, 1.0)


class EmpiricalLikelihoodProvider:
    """Likelihood rating provider backed by empirical trials and #238 estimator.

    Precedence 1: applicable reviewed empirical evidence.
    Enforces strict prototype quarantine: prototype benchmark data cannot be
    promoted to production empirical calibration in production ranking mode.
    """

    def __init__(
        self,
        estimator: EmpiricalQiEstimator | None = None,
        *,
        observations: Sequence[TrialObservation] | None = None,
        manifest: Mapping[str, Any] | None = None,
        dataset_classification: str | None = None,
        for_production_ranking: bool = True,
        name: str = "empirical_likelihood_provider",
        provider_version: str = "1.0.0",
    ) -> None:
        self._name = name
        self._provider_version = provider_version
        self.for_production_ranking = for_production_ranking
        self.manifest = dict(manifest) if manifest is not None else {}

        if estimator is not None:
            self.estimator = estimator
        else:
            self.estimator = EmpiricalQiEstimator(
                manifest=self.manifest,
                dataset_classification=dataset_classification,
            )
            if observations is not None:
                self.estimator.fit(
                    list(observations),
                    dataset_classification=dataset_classification,
                )

    @property
    def name(self) -> str:
        return self._name

    @property
    def provider_version(self) -> str:
        return self._provider_version

    def resolve_likelihood(
        self,
        key: LikelihoodLookupKey,
        prefix: tuple[str, ...],
        outcome_unit: str,
        scope: Mapping[str, Any],
    ) -> ResolutionResult:
        """Resolve conditional likelihood from empirical trial evidence."""
        # 1. Absence check: provider has no trial observations
        if not self.estimator._observations:
            return ResolutionResult(
                disposition=ResolverDisposition.UNSUPPORTED,
                reason_code=ReasonCode.MISSING_EVIDENCE,
                reason_detail=(
                    f"No empirical observations for technique {key.outcome_technique!r}"
                ),
                provider_name=self.name,
                provider_version=self.provider_version,
            )

        matching_tech = [
            o for o in self.estimator._observations if o.technique == key.outcome_technique
        ]
        if not matching_tech:
            return ResolutionResult(
                disposition=ResolverDisposition.UNSUPPORTED,
                reason_code=ReasonCode.UNSUPPORTED_TECHNIQUE,
                reason_detail=(
                    f"Technique {key.outcome_technique!r} absent from empirical observations"
                ),
                provider_name=self.name,
                provider_version=self.provider_version,
            )

        # 2. Build EstimatorContext
        horizon_secs = parse_horizon_seconds(key.horizon)
        target_complexity = scope.get("target_complexity_class")
        if target_complexity is None and matching_tech:
            target_complexity = matching_tech[0].target_complexity_class

        action_aliases = {s: s.split(":")[0] for s in prefix}
        context = EstimatorContext(
            technique=key.outcome_technique,
            method=key.method,
            budget=key.budget,
            horizon_seconds=horizon_secs,
            target_complexity_class=target_complexity,
            scenario_id=key.scenario_id,
            is_synthetic_fixture=bool(scope.get("is_synthetic_fixture", False)),
            actor_capability=scope.get("actor_capability"),
            action_aliases=action_aliases,
        )

        # 3. Domain transfer check: SEAMLESS domain transfer refusal
        if re.search(r"seamless", key.scenario_id, re.IGNORECASE):
            return ResolutionResult(
                disposition=ResolverDisposition.REFUSED,
                reason_code=ReasonCode.PREREQUISITE_GATE_REFUSAL,
                reason_detail=(
                    "unrepresentative_domain_transfer_seamless: "
                    "no empirical password distribution or telemetry observed in SEAMLESS snapshot"
                ),
                provider_name=self.name,
                provider_version=self.provider_version,
            )

        # 4. Quarantine check for production ranking mode
        if self.for_production_ranking:
            if (
                self.estimator.dataset_classification == "controlled_lab_benchmark_prototype"
                or not self.estimator.is_reviewed_evidence_package
            ):
                return ResolutionResult(
                    disposition=ResolverDisposition.REFUSED,
                    reason_code=ReasonCode.PREREQUISITE_GATE_REFUSAL,
                    reason_detail=(
                        "Prototype evidence quarantined: cannot be promoted or exported for "
                        "production ranking without approved reviewed evidence package"
                    ),
                    provider_name=self.name,
                    provider_version=self.provider_version,
                    basis_category=self.estimator.dataset_classification,
                )

        # 5. Call #238 estimator
        res = self.estimator.estimate(context, prefix)

        # 6. Process estimator output
        if res.status == "unrated":
            reasons = res.missing_basis_reasons

            # 6a. Contradictory evidence
            if any("contradictory" in r or "conflicting" in r for r in reasons):
                return ResolutionResult(
                    disposition=ResolverDisposition.CONFLICTING,
                    reason_code=ReasonCode.CONFLICTING_PROVIDER_BASIS,
                    reason_detail=res.rationale,
                    provider_name=self.name,
                    provider_version=self.provider_version,
                )

            # 6b. Malformed input / synthetic fixture rejected
            if any(
                "synthetic" in r
                or "missing_trial_id" in r
                or "missing_target_hash" in r
                or "missing_provenance" in r
                or "censored" in r
                for r in reasons
            ):
                return ResolutionResult(
                    disposition=ResolverDisposition.REFUSED,
                    reason_code=ReasonCode.MALFORMED_INPUT,
                    reason_detail=res.rationale,
                    provider_name=self.name,
                    provider_version=self.provider_version,
                )

            # 6c. Holdout / data leakage refusal
            if any("holdout" in r or "data_leakage" in r for r in reasons):
                return ResolutionResult(
                    disposition=ResolverDisposition.REFUSED,
                    reason_code=ReasonCode.HOLDOUT_ISOLATION_REFUSAL,
                    reason_detail=res.rationale,
                    provider_name=self.name,
                    provider_version=self.provider_version,
                )

            # 6d. Prerequisite / unverified prototype / unreviewed manifest refusal
            if any(
                "prerequisite" in r or "unverified_prototype" in r or "unreviewed_evidence" in r
                for r in reasons
            ):
                return ResolutionResult(
                    disposition=ResolverDisposition.REFUSED,
                    reason_code=ReasonCode.PREREQUISITE_GATE_REFUSAL,
                    reason_detail=res.rationale,
                    provider_name=self.name,
                    provider_version=self.provider_version,
                )

            # 6e. Unsupported scenario
            if any("unsupported_domain_or_scenario" in r for r in reasons):
                return ResolutionResult(
                    disposition=ResolverDisposition.UNSUPPORTED,
                    reason_code=ReasonCode.OUT_OF_SCOPE,
                    reason_detail=res.rationale,
                    provider_name=self.name,
                    provider_version=self.provider_version,
                )

            # 6f. Parameter mismatches (method, budget, horizon)
            obs_methods = {o.method for o in matching_tech}
            if context.method not in obs_methods:
                return ResolutionResult(
                    disposition=ResolverDisposition.UNSUPPORTED,
                    reason_code=ReasonCode.OUT_OF_SCOPE,
                    reason_detail=(
                        f"Method mismatch: empirical trials use {sorted(obs_methods)!r}, "
                        f"lookup requires {context.method!r}"
                    ),
                    provider_name=self.name,
                    provider_version=self.provider_version,
                )

            obs_budgets = {o.budget for o in matching_tech}
            if context.budget not in obs_budgets:
                return ResolutionResult(
                    disposition=ResolverDisposition.UNSUPPORTED,
                    reason_code=ReasonCode.OUT_OF_SCOPE,
                    reason_detail=(
                        f"Budget mismatch: empirical trials use {sorted(obs_budgets)!r}, "
                        f"lookup requires {context.budget!r}"
                    ),
                    provider_name=self.name,
                    provider_version=self.provider_version,
                )

            if context.horizon_seconds is not None:
                has_horizon_match = any(
                    math.isclose(o.horizon_seconds, context.horizon_seconds, rel_tol=1e-6)
                    for o in matching_tech
                )
                if not has_horizon_match:
                    obs_horizons = {o.horizon_seconds for o in matching_tech}
                    return ResolutionResult(
                        disposition=ResolverDisposition.UNSUPPORTED,
                        reason_code=ReasonCode.OUT_OF_SCOPE,
                        reason_detail=(
                            f"Horizon mismatch: empirical trials use {sorted(obs_horizons)!r}s, "
                            f"lookup requires {context.horizon_seconds!r}s"
                        ),
                        provider_name=self.name,
                        provider_version=self.provider_version,
                    )

            # 6g. Insufficient sample size / missing evidence
            return ResolutionResult(
                disposition=ResolverDisposition.UNSUPPORTED,
                reason_code=ReasonCode.MISSING_EVIDENCE,
                reason_detail=res.rationale,
                provider_name=self.name,
                provider_version=self.provider_version,
            )

        # 7. Rated disposition
        if self.for_production_ranking and not self.estimator.is_reviewed_evidence_package:
            return ResolutionResult(
                disposition=ResolverDisposition.REFUSED,
                reason_code=ReasonCode.PREREQUISITE_GATE_REFUSAL,
                reason_detail=(
                    "Quarantined prototype evidence cannot be promoted to production ranking"
                ),
                provider_name=self.name,
                provider_version=self.provider_version,
            )

        lo_rat = parse_rational(res.lower_fraction)
        hi_rat = parse_rational(res.upper_fraction)
        review_ref = (
            self.manifest.get("reviewed_by") if isinstance(self.manifest, Mapping) else None
        )
        prov_digest = (
            self.manifest.get("manifest_digest") if isinstance(self.manifest, Mapping) else None
        )
        basis = (
            BasisClassification.EMPIRICAL_EVIDENCE
            if self.estimator.is_reviewed_evidence_package
            else res.basis_category
        )

        return ResolutionResult(
            disposition=ResolverDisposition.RATED,
            value=(lo_rat, hi_rat),
            reason_code=ReasonCode.REVIEWED_PACKET_MATCH,
            reason_detail=res.rationale,
            basis_category=basis,
            review_reference=review_ref,
            provenance_digest=prov_digest,
            provider_name=self.name,
            provider_version=self.provider_version,
        )


class ReviewedScenarioLikelihoodProvider:
    """Likelihood rating provider backed by reviewed scenario records.

    Precedence 2: reviewed full-history scenario/rubric interval where governance permits it.
    Preserves strict full-history ordering and all contextual dimensions:
    - ordered successful active-work prefix;
    - outcome work unit and technique;
    - actor, target, and source;
    - method, budget, and horizon;
    - boundary and scope;
    - auth context, resource context, and policy ID.
    Enforces that scenario assumption intervals are NEVER labelled empirical evidence.
    """

    def __init__(
        self,
        records: Sequence[Mapping[str, Any]] | None = None,
        *,
        name: str = "reviewed_scenario_likelihood_provider",
        provider_version: str = "1.0.0",
    ) -> None:
        self._name = name
        self._provider_version = provider_version
        self.records: list[dict[str, Any]] = [deepcopy(dict(r)) for r in (records or ())]

    @property
    def name(self) -> str:
        return self._name

    @property
    def provider_version(self) -> str:
        return self._provider_version

    def resolve_likelihood(
        self,
        key: LikelihoodLookupKey,
        prefix: tuple[str, ...],
        outcome_unit: str,
        scope: Mapping[str, Any],
    ) -> ResolutionResult:
        """Resolve conditional likelihood from reviewed scenario records."""

        def refuse(code: ReasonCode, detail: str) -> ResolutionResult:
            return ResolutionResult(
                disposition=ResolverDisposition.REFUSED,
                reason_code=code,
                reason_detail=detail,
                provider_name=self.name,
                provider_version=self.provider_version,
            )

        context_fields = (
            "actor_capability",
            "target_complexity_class",
            "control_scope",
            "retry_policy",
            "target_population",
            "recovery_metadata",
        )
        for field in context_fields:
            if field in scope:
                try:
                    json.dumps(scope[field], sort_keys=True, allow_nan=False)
                except TypeError, ValueError:
                    return refuse(ReasonCode.MALFORMED_INPUT, f"{field} must be JSON context")

        # 1. Governance permission check
        eval_mode = scope.get("evaluation_mode", "scenario")
        governance = scope.get("governance", {})
        if not isinstance(governance, Mapping):
            return refuse(ReasonCode.MALFORMED_INPUT, "governance must be an object")
        if (
            "allow_scenario_fallback" in governance
            and type(governance["allow_scenario_fallback"]) is not bool
        ):
            return refuse(
                ReasonCode.MALFORMED_INPUT, "allow_scenario_fallback must be an exact bool"
            )
        if eval_mode == "empirical_only" or governance.get("allow_scenario_fallback") is False:
            return ResolutionResult(
                disposition=ResolverDisposition.REFUSED,
                reason_code=ReasonCode.PREREQUISITE_GATE_REFUSAL,
                reason_detail="Governance policy forbids scenario fallback",
                provider_name=self.name,
                provider_version=self.provider_version,
            )

        # 2. Registry empty
        if not self.records:
            return ResolutionResult(
                disposition=ResolverDisposition.UNSUPPORTED,
                reason_code=ReasonCode.MISSING_EVIDENCE,
                reason_detail="No reviewed scenario records in registry",
                provider_name=self.name,
                provider_version=self.provider_version,
            )

        # A corrupted registry is an integrity refusal, not missing evidence.
        for record in self.records:
            rb = record.get("rating_binding", {})
            if not isinstance(rb, Mapping):
                return refuse(ReasonCode.MALFORMED_INPUT, "rating_binding must be an object")
            if "ordered_work_prefix" not in record and "ordered_work_prefix" not in rb:
                return refuse(ReasonCode.MALFORMED_INPUT, "Missing required ordered_work_prefix")
            history = record.get("ordered_work_prefix", rb.get("ordered_work_prefix"))
            for field in ("ordered_work_prefix", "prefix"):
                value = record.get(field, rb.get(field, history))
                if (
                    not isinstance(value, (list, tuple))
                    or not value
                    or not all(isinstance(unit, str) and unit for unit in value)
                    or tuple(value) != tuple(history)
                ):
                    return refuse(ReasonCode.MALFORMED_INPUT, f"Invalid or contradictory {field}")

            binding = {**rb, **record}
            if "outcome_unit" in binding and (
                not isinstance(binding["outcome_unit"], str)
                or binding["outcome_unit"] != binding.get("outcome_work_unit_id")
            ):
                return refuse(ReasonCode.MALFORMED_INPUT, "Contradictory outcome_unit alias")
            for field in context_fields:
                if field in binding:
                    try:
                        json.dumps(binding[field], sort_keys=True, allow_nan=False)
                    except TypeError, ValueError:
                        return refuse(ReasonCode.MALFORMED_INPUT, f"{field} must be JSON context")

        # 3. Match scenario ID
        matching_scenarios = [
            r
            for r in self.records
            if r.get("scenario_id") == key.scenario_id
            or r.get("rating_binding", {}).get("scenario_id") == key.scenario_id
        ]
        if not matching_scenarios:
            return ResolutionResult(
                disposition=ResolverDisposition.UNSUPPORTED,
                reason_code=ReasonCode.OUT_OF_SCOPE,
                reason_detail=f"Scenario {key.scenario_id!r} not in reviewed scenario registry",
                provider_name=self.name,
                provider_version=self.provider_version,
            )

        # 4. Match prefix and outcome work unit
        prefix_matches: list[dict[str, Any]] = []
        for r in matching_scenarios:
            rb = r.get("rating_binding", {})
            rec_prefix = tuple(
                r.get("ordered_work_prefix", rb.get("ordered_work_prefix", r.get("prefix", ())))
            )
            rec_outcome = (
                r.get("outcome_work_unit_id")
                or r.get("outcome_unit")
                or r.get("rating_binding", {}).get("outcome_work_unit_id")
            )
            if (
                len(rec_prefix) == len(prefix)
                and rec_prefix == prefix
                and (rec_outcome is None or rec_outcome == outcome_unit)
            ):
                prefix_matches.append(r)

        if not prefix_matches:
            return ResolutionResult(
                disposition=ResolverDisposition.UNSUPPORTED,
                reason_code=ReasonCode.MISSING_EVIDENCE,
                reason_detail=f"Exact prefix {list(prefix)!r} absent from registry",
                provider_name=self.name,
                provider_version=self.provider_version,
            )

        # Exact prefixes may have separately reviewed snapshot/context records.
        # Only complete applicable contexts compete; duplicates remain a conflict.
        if len(prefix_matches) > 1:
            applicable = []
            for record in prefix_matches:
                binding = {**record.get("rating_binding", {}), **record}
                if all(
                    field in binding
                    and binding[field] == value
                    and type(binding[field]) is type(value)
                    for field, value in key.to_dict().items()
                    if field not in ("dimension", "ordered_work_prefix")
                ) and all(
                    field not in binding
                    and field not in scope
                    or field in binding
                    and field in scope
                    and json.dumps(binding[field], sort_keys=True, allow_nan=False)
                    == json.dumps(scope[field], sort_keys=True, allow_nan=False)
                    for field in context_fields
                ):
                    applicable.append(record)
            if applicable:
                prefix_matches = applicable

        if len(prefix_matches) > 1:
            return ResolutionResult(
                disposition=ResolverDisposition.CONFLICTING,
                reason_code=ReasonCode.CONFLICTING_PROVIDER_BASIS,
                reason_detail=f"Multiple conflicting reviewed records for prefix {list(prefix)!r}",
                provider_name=self.name,
                provider_version=self.provider_version,
            )

        rec = prefix_matches[0]
        rb = rec.get("rating_binding", {})

        # Acceptance permits this exact record, not merely the fallback basis type.
        if not isinstance(rb, Mapping):
            return refuse(ReasonCode.MALFORMED_INPUT, "rating_binding must be an object")
        if any(rec[field] != rb[field] for field in rec.keys() & rb.keys()):
            return refuse(ReasonCode.MALFORMED_INPUT, "Contradictory record/rating_binding fields")
        binding = {**rb, **rec}
        if binding.get("review_status") != "accepted" or binding.get("disposition") != "rated":
            return refuse(
                ReasonCode.PREREQUISITE_GATE_REFUSAL,
                "Scenario record requires explicit accepted review_status and rated disposition",
            )
        review_ref = binding.get("review_reference")
        prov_digest = binding.get("provenance_digest")
        if not isinstance(review_ref, str) or not review_ref.strip():
            return refuse(ReasonCode.MALFORMED_INPUT, "Missing required review_reference")
        if not isinstance(prov_digest, str) or not re.fullmatch(
            r"sha256:[0-9a-f]{64}", prov_digest
        ):
            return refuse(ReasonCode.MALFORMED_INPUT, "Missing or malformed provenance_digest")
        basis = binding.get("basis_category")
        if not isinstance(basis, str) or basis not in {
            str(b) for b in BasisClassification if b != BasisClassification.EMPIRICAL_EVIDENCE
        }:
            return refuse(
                ReasonCode.PREREQUISITE_GATE_REFUSAL,
                "Scenario record requires a known non-empirical basis_category",
            )
        if binding.get("version") != RESOLVER_CONTRACT_VERSION:
            return refuse(ReasonCode.MALFORMED_INPUT, "Unsupported scenario record version")
        rationale = binding.get("rationale")
        if not isinstance(rationale, str) or not rationale.strip():
            return refuse(ReasonCode.MALFORMED_INPUT, "Missing required rationale")

        # Every lookup field binds explicitly, including null optional context.
        # Missing fields are not wildcards; zero budget is not missing budget.
        expected = key.to_dict()
        expected.pop("dimension")
        if "ordered_work_prefix" not in binding or tuple(binding["ordered_work_prefix"]) != prefix:
            return refuse(
                ReasonCode.MALFORMED_INPUT, "Missing or contradictory ordered_work_prefix"
            )
        if "prefix" in binding and tuple(binding["prefix"]) != prefix:
            return refuse(ReasonCode.MALFORMED_INPUT, "Contradictory prefix alias")
        expected.pop("ordered_work_prefix")  # Checked exactly in order above.
        for field, value in expected.items():
            if field not in binding:
                return refuse(ReasonCode.MALFORMED_INPUT, f"Missing required {field} binding")
            if binding[field] != value or type(binding[field]) is not type(value):
                return refuse(
                    ReasonCode.OUT_OF_SCOPE,
                    f"{field} mismatch: record {binding[field]!r} != lookup {value!r}",
                )
        if key.ordered_work_prefix != prefix or key.outcome_work_unit_id != outcome_unit:
            return refuse(ReasonCode.MALFORMED_INPUT, "Lookup key disagrees with supplied history")
        for field in context_fields:
            if field in scope or field in binding:
                if field not in binding or field not in scope:
                    return refuse(ReasonCode.OUT_OF_SCOPE, f"{field} missing or mismatched")
                try:
                    record_context = json.dumps(binding[field], sort_keys=True, allow_nan=False)
                    lookup_context = json.dumps(scope[field], sort_keys=True, allow_nan=False)
                except TypeError, ValueError:
                    return refuse(ReasonCode.MALFORMED_INPUT, f"{field} must be JSON context")
                if record_context != lookup_context:
                    return refuse(ReasonCode.OUT_OF_SCOPE, f"{field} missing or mismatched")
        rec_queries = binding.get("applicable_queries")
        if rec_queries is not None and (
            not isinstance(rec_queries, (list, tuple))
            or not all(isinstance(q, str) for q in rec_queries)
        ):
            return refuse(ReasonCode.MALFORMED_INPUT, "applicable_queries must be query identities")
        if rec_queries is not None and scope.get("query_id") not in rec_queries:
            return refuse(ReasonCode.OUT_OF_SCOPE, "Record not reviewed for query_id")

        # 7. Rational bounds validation
        lower_raw = rec.get("lower")
        upper_raw = rec.get("upper")
        if lower_raw is None or upper_raw is None:
            return ResolutionResult(
                disposition=ResolverDisposition.REFUSED,
                reason_code=ReasonCode.MALFORMED_INPUT,
                reason_detail="Reviewed scenario record missing lower or upper bound",
                provider_name=self.name,
                provider_version=self.provider_version,
            )

        try:
            lo = parse_rational(lower_raw)
            hi = parse_rational(upper_raw)
        except (ValueError, TypeError) as exc:
            return ResolutionResult(
                disposition=ResolverDisposition.REFUSED,
                reason_code=ReasonCode.MALFORMED_INPUT,
                reason_detail=f"Malformed rational bounds in scenario record: {exc}",
                provider_name=self.name,
                provider_version=self.provider_version,
            )

        if not (Fraction(0, 1) <= lo <= hi <= Fraction(1, 1)):
            return ResolutionResult(
                disposition=ResolverDisposition.REFUSED,
                reason_code=ReasonCode.MALFORMED_INPUT,
                reason_detail=f"Invalid rational interval bounds: [{lo}, {hi}]",
                provider_name=self.name,
                provider_version=self.provider_version,
            )

        return ResolutionResult(
            disposition=ResolverDisposition.RATED,
            value=(lo, hi),
            reason_code=ReasonCode.REVIEWED_PACKET_MATCH,
            reason_detail=rationale,
            basis_category=basis,
            review_reference=review_ref,
            provenance_digest=prov_digest,
            provider_name=self.name,
            provider_version=self.provider_version,
            numeric_basis_class=binding.get("numeric_basis_class"),
            review_status=binding.get("review_status"),
        )


def build_likelihood_provider_chain(
    *,
    empirical_provider: LikelihoodRatingProvider | None = None,
    scenario_provider: LikelihoodRatingProvider | None = None,
    fallback_provider: FallbackUnratedProvider | None = None,
) -> tuple[LikelihoodRatingProvider, ...]:
    """Build canonical likelihood provider chain with explicit precedence:

    1. Applicable reviewed empirical evidence.
    2. Reviewed full-history scenario/rubric interval where governance permits it.
    3. Fail-closed unrated fallback.
    """
    chain: list[LikelihoodRatingProvider] = []
    if empirical_provider is not None:
        chain.append(empirical_provider)
    if scenario_provider is not None:
        chain.append(scenario_provider)
    if fallback_provider is not None:
        chain.append(fallback_provider)
    else:
        chain.append(FallbackUnratedProvider())
    return tuple(chain)


def audit_frozen_243_likelihood_coverage(
    paths: Sequence[Any],
    query_scope: Mapping[str, Any],
    *,
    transition_bindings: Mapping[tuple[str, str, str, str], Mapping[str, Any]],
    resolver: Any | None = None,
    for_production_ranking: bool = True,
) -> dict[str, Any]:
    """Audit authentic public-generated frozen #243 PathResults, never reconstruct them.

    The caller supplies manifest-verified frozen query inputs and predicate bindings.
    Semantic assumptions permit generation only; they do not supply any numeric q_i.
    """
    from src.engine.ranking.resolver import RatingResolver
    from src.engine.search import PathResult

    expected = (
        "asrep_request",
        "recover_asrep_secret",
        "activate_recovered_identity",
        "obtain_admin_execution_on_host",
    )
    if (
        query_scope.get("scenario_id") != "week4-seamless-v1"
        or len(paths) != 1
        or not isinstance(paths[0], PathResult)
        or tuple(s.result.request.technique_id for s in paths[0].transition_history) != expected
    ):
        raise RankingValidationError(
            "Frozen #243 audit requires its authentic generated PathResult"
        )
    if resolver is None:
        resolver = RatingResolver(
            likelihood_providers=build_likelihood_provider_chain(
                empirical_provider=EmpiricalLikelihoodProvider(
                    for_production_ranking=for_production_ranking
                ),
                scenario_provider=ReviewedScenarioLikelihoodProvider(),
            )
        )
    output = resolver.resolve(paths, query_scope, transition_bindings=transition_bindings)
    envelope = output.candidate_envelopes[0]
    candidate_id = envelope["candidate_id"]
    report = output.coverage_report["candidates"][candidate_id]["likelihood"]
    inventory = []
    for item in report["prefixes"]:
        inventory.append(
            {
                **item,
                "lookup_key": item.get("rating_audit", {}).get("lookup_key"),
                "providers_attempted": [t["provider"] for t in item.get("provider_trace", [])],
                "work_context": output.ranking_query["work_units_ledger"][item["outcome_unit"]],
            }
        )
    return {
        "scenario_id": query_scope["scenario_id"],
        "candidate_id": candidate_id,
        "candidate_envelope": envelope,
        "horizon": query_scope["horizon"],
        "recovery_metadata": deepcopy(query_scope.get("recovery_metadata")),
        "total_required_prefixes": len(inventory),
        "audit_inventory": inventory,
        "all_rated": report["all_rated"],
        "unrated_prefixes": report["unrated_prefixes"],
        "unresolved_gaps": output.coverage_report["unresolved_gaps"],
        "coverage_report": output.coverage_report,
    }
