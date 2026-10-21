"""Tests for empirical conditional probability estimator, refusal rules, and engine integration."""

from __future__ import annotations

import json
import math
from fractions import Fraction
from pathlib import Path

import pytest

from scripts.research.empirical_qi_estimator import (
    EmpiricalQiEstimator,
    EstimatorContext,
    TrialObservation,
    evaluate_holdout_quality,
    rationalize_conservative_bounds,
    wilson_score_interval,
)
from src.engine.ranking.assessment import assess_candidate_program
from src.engine.ranking.validation import (
    validate_and_decode_bounds_table,
)

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures" / "empirical_calibration"


def load_benchmark_dataset() -> tuple[list[TrialObservation], list[TrialObservation], dict]:
    with open(FIXTURES_DIR / "lab_benchmark_dataset.json", encoding="utf-8") as f:
        data = json.load(f)
    common = data["common_parameters"]

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
        for item in data["training_observations"]
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
        for item in data["holdout_observations"]
    ]

    return train_obs, holdout_obs, common


class TestWilsonScoreInterval:
    """Mathematical verification of Wilson score interval (NIST PRC 2.4.1)."""

    def test_known_reference_values(self):
        # 100 trials, 50 successes -> p_hat = 0.5
        # Wilson interval at z=1.95996398454 should be symmetric around 0.5
        lo, hi = wilson_score_interval(100, 50)
        assert abs(lo - (1.0 - hi)) < 1e-12
        assert 0.40 < lo < 0.41
        assert 0.59 < hi < 0.60

    def test_interval_invariants(self):
        for n, k in [(20, 5), (60, 22), (100, 1), (100, 99)]:
            lo, hi = wilson_score_interval(n, k)
            p_hat = k / n
            assert 0.0 <= lo <= p_hat <= hi <= 1.0

    def test_boundary_zero_and_all_successes(self):
        # k = 0
        lo_0, hi_0 = wilson_score_interval(50, 0)
        assert lo_0 == 0.0
        assert hi_0 > 0.0

        # k = n
        lo_n, hi_n = wilson_score_interval(50, 50)
        assert lo_n < 1.0
        assert hi_n == 1.0

    def test_invalid_parameters_raise_error(self):
        with pytest.raises(ValueError, match="Sample size n must be positive"):
            wilson_score_interval(0, 0)
        with pytest.raises(ValueError, match="Success count k must be between 0 and n"):
            wilson_score_interval(10, 11)
        with pytest.raises(ValueError, match="Success count k must be between 0 and n"):
            wilson_score_interval(10, -1)
        with pytest.raises(ValueError, match="Critical value z must be positive"):
            wilson_score_interval(50, 25, z=0.0)


class TestRationalizeConservativeBounds:
    """Verification of outer conservative fraction conversion."""

    def test_conservative_outer_rounding(self):
        lo_float, hi_float = 0.25620916687225426, 0.49316999369896963
        lo_frac, hi_frac = rationalize_conservative_bounds(lo_float, hi_float, max_denominator=1000)

        assert isinstance(lo_frac, Fraction)
        assert isinstance(hi_frac, Fraction)
        # Outer conservative: lo_frac <= lo_float, hi_frac >= hi_float
        assert float(lo_frac) <= lo_float
        assert float(hi_frac) >= hi_float
        assert Fraction(0, 1) <= lo_frac <= hi_frac <= Fraction(1, 1)

    def test_boundary_zero_and_one(self):
        lo_frac, hi_frac = rationalize_conservative_bounds(0.0, 1.0)
        assert lo_frac == Fraction(0, 1)
        assert hi_frac == Fraction(1, 1)

    def test_invalid_bounds_raise(self):
        with pytest.raises(ValueError):
            rationalize_conservative_bounds(-0.1, 0.5)
        with pytest.raises(ValueError):
            rationalize_conservative_bounds(0.8, 0.5)
        with pytest.raises(ValueError, match="max_denominator must be positive"):
            rationalize_conservative_bounds(0.2, 0.8, max_denominator=0)
        with pytest.raises(ValueError, match="Interval bounds cannot be NaN"):
            rationalize_conservative_bounds(math.nan, 0.8)


class TestEmpiricalEstimator:
    """Verification of EmpiricalQiEstimator behavior and refusal rules."""

    def test_lab_benchmark_estimation_rated(self):
        train_obs, _, common = load_benchmark_dataset()
        estimator = EmpiricalQiEstimator(min_sample_size=20)
        estimator.fit(train_obs)

        ctx = EstimatorContext(
            technique=common["technique"],
            method=common["method"],
            budget=common["budget"],
            horizon_seconds=common["horizon_seconds"],
            target_complexity_class=common["target_complexity_class"],
            scenario_id="lab-benchmark-scenario",
            is_synthetic_fixture=False,
        )

        # Standard canonical prefix: asrep_request followed by recover_asrep_secret
        res = estimator.estimate(ctx, prefix=("asrep_request", "recover_asrep_secret"))
        assert res.status == "rated"
        assert res.basis_category == "controlled_lab_benchmark_prototype"
        assert res.dataset_classification == "controlled_lab_benchmark_prototype"
        assert res.evidence_disposition == "quarantined_prototype_not_for_production_ranking"
        assert res.sample_size == 60
        assert res.success_count == 22
        assert res.point_estimate == 22 / 60
        assert res.lower_bound is not None and res.upper_bound is not None
        assert 0.25 < res.lower_bound < 0.26
        assert 0.49 < res.upper_bound < 0.50
        assert res.lower_fraction == "32/125"
        assert res.upper_fraction == "247/500"

        # Missing manifest with empirical_measurement classification is refused fail-closed
        est_unreviewed = EmpiricalQiEstimator(
            min_sample_size=20, dataset_classification="empirical_measurement"
        )
        est_unreviewed.fit(train_obs)
        res_unrev = est_unreviewed.estimate(ctx, prefix=("asrep_request", "recover_asrep_secret"))
        assert res_unrev.status == "unrated"
        assert res_unrev.basis_category == "insufficient_evidence"
        assert any("missing_evidence_manifest" in r for r in res_unrev.missing_basis_reasons)
        assert (
            est_unreviewed.export_bounds_table_entry(
                ctx, prefix=("asrep_request", "recover_asrep_secret"), for_production_ranking=True
            )
            is None
        )

        # Prototype observations cannot be promoted by attaching mock manifest
        mock_manifest = {
            "dataset_classification": "empirical_measurement",
            "review_status": "reviewed",
            "reviewed_by": "sec-team@research.ad",
            "reviewed_at": "2026-10-09T00:00:00Z",
            "package_id": "lab-reviewed-asrep-v1",
            "supported_scenario_ids": ["lab-benchmark-scenario"],
            "supported_actor_capabilities": ["offline_gpu_cracking"],
            "supported_prefix_sequences": [["asrep_request", "recover_asrep_secret"]],
        }
        ctx_rev = EstimatorContext(
            technique=common["technique"],
            method=common["method"],
            budget=common["budget"],
            horizon_seconds=common["horizon_seconds"],
            target_complexity_class=common["target_complexity_class"],
            scenario_id="lab-benchmark-scenario",
            is_synthetic_fixture=False,
            actor_capability="offline_gpu_cracking",
        )
        est_mock = EmpiricalQiEstimator(min_sample_size=20, manifest=mock_manifest)
        est_mock.fit(train_obs)
        res_mock = est_mock.estimate(ctx_rev, prefix=("asrep_request", "recover_asrep_secret"))
        assert res_mock.status == "unrated"
        assert any("unverified_prototype_provenance" in r for r in res_mock.missing_basis_reasons)
        assert (
            est_mock.export_bounds_table_entry(
                ctx_rev,
                prefix=("asrep_request", "recover_asrep_secret"),
                for_production_ranking=True,
            )
            is None
        )

        # Prefix with work_ namespace aliases also resolves correctly
        res_work = estimator.estimate(
            ctx, prefix=("work_asrep_request", "work_recover_asrep_secret")
        )
        assert res_work.status == "rated"
        assert res_work.lower_fraction == "32/125"

    def test_export_bounds_table_entry_structure(self):
        train_obs, _, common = load_benchmark_dataset()
        estimator = EmpiricalQiEstimator()
        estimator.fit(train_obs)

        ctx = EstimatorContext(
            technique=common["technique"],
            method=common["method"],
            budget=common["budget"],
            horizon_seconds=common["horizon_seconds"],
            target_complexity_class=common["target_complexity_class"],
            scenario_id="lab-benchmark-scenario",
            is_synthetic_fixture=False,
            action_aliases={"u1": "asrep_request", "u2": "recover_asrep_secret"},
        )

        entry = estimator.export_bounds_table_entry(ctx, prefix=("u1", "u2"))
        assert entry is not None
        assert entry["prefix"] == ["u1", "u2"]
        assert entry["lower"] == "32/125"
        assert entry["upper"] == "247/500"
        assert entry["basis_category"] == "controlled_lab_benchmark_prototype"
        assert entry["dataset_classification"] == "controlled_lab_benchmark_prototype"
        assert entry["evidence_disposition"] == "quarantined_prototype_not_for_production_ranking"

        # Production ranking export gate blocks unverified prototype data
        assert (
            estimator.export_bounds_table_entry(
                ctx, prefix=("u1", "u2"), for_production_ranking=True
            )
            is None
        )

        # Conformance with engine validation decoder (engine accepts distinct prototype label)
        table = validate_and_decode_bounds_table([entry])
        assert ("u1", "u2") in table
        lo, hi = table[("u1", "u2")]
        assert lo == Fraction(32, 125)
        assert hi == Fraction(247, 500)

    def test_all_refusal_cases_fail_closed(self):
        with open(FIXTURES_DIR / "lab_benchmark_dataset.json", encoding="utf-8") as f:
            bench_data = json.load(f)
        manifest = bench_data.get("evidence_manifest")
        train_obs, _, _ = load_benchmark_dataset()
        estimator = EmpiricalQiEstimator(manifest=manifest)
        estimator.fit(train_obs)

        with open(FIXTURES_DIR / "refusal_cases.json", encoding="utf-8") as f:
            refusal_data = json.load(f)

        for case in refusal_data["cases"]:
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
            assert res.status == case["expected_status"], f"Failed on case {case['case_id']}"
            assert res.lower_bound is None
            assert res.upper_bound is None
            assert any(case["expected_reason_substr"] in r for r in res.missing_basis_reasons), (
                f"Expected reason substr {case['expected_reason_substr']!r} "
                f"not found in {res.missing_basis_reasons}"
            )

            # Ensure bounds entry export returns None for unrated results
            entry = estimator.export_bounds_table_entry(ctx, prefix=case_prefix)
            assert entry is None

    def test_empty_prefix_refusal(self):
        train_obs, _, common = load_benchmark_dataset()
        estimator = EmpiricalQiEstimator()
        estimator.fit(train_obs)

        ctx = EstimatorContext(
            technique=common["technique"],
            method=common["method"],
            budget=common["budget"],
            horizon_seconds=common["horizon_seconds"],
            target_complexity_class=common["target_complexity_class"],
            scenario_id="lab-scenario",
        )
        res = estimator.estimate(ctx, prefix=())
        assert res.status == "unrated"
        assert any("empty_prefix" in r for r in res.missing_basis_reasons)

    def test_prefix_action_mismatch_refusal(self):
        train_obs, _, common = load_benchmark_dataset()
        estimator = EmpiricalQiEstimator()
        estimator.fit(train_obs)

        ctx = EstimatorContext(
            technique=common["technique"],
            method=common["method"],
            budget=common["budget"],
            horizon_seconds=common["horizon_seconds"],
            target_complexity_class=common["target_complexity_class"],
            scenario_id="lab-scenario",
        )
        res = estimator.estimate(ctx, prefix=("asrep_request", "random_unrelated_step"))
        assert res.status == "unrated"
        assert any("prefix_action_mismatch" in r for r in res.missing_basis_reasons)

    def test_missing_prerequisite_history_refusal(self):
        train_obs, _, common = load_benchmark_dataset()
        estimator = EmpiricalQiEstimator()
        estimator.fit(train_obs)

        ctx = EstimatorContext(
            technique=common["technique"],
            method=common["method"],
            budget=common["budget"],
            horizon_seconds=common["horizon_seconds"],
            target_complexity_class=common["target_complexity_class"],
            scenario_id="lab-scenario",
            initial_material_present=False,
        )
        # Standalone recovery without asrep_request in history prefix must fail-closed
        res = estimator.estimate(ctx, prefix=("recover_asrep_secret",))
        assert res.status == "unrated"
        assert any("missing_prerequisite_in_history" in r for r in res.missing_basis_reasons)

    def test_unseen_history_prefix_refusal(self):
        train_obs, _, common = load_benchmark_dataset()
        estimator = EmpiricalQiEstimator()
        estimator.fit(train_obs)

        ctx = EstimatorContext(
            technique=common["technique"],
            method=common["method"],
            budget=common["budget"],
            horizon_seconds=common["horizon_seconds"],
            target_complexity_class=common["target_complexity_class"],
            scenario_id="lab-benchmark-asrep-v1",
            initial_material_present=False,
        )
        # History with reset_password alters password distribution; must be refused!
        res = estimator.estimate(
            ctx, prefix=("reset_password", "asrep_request", "recover_asrep_secret")
        )
        assert res.status == "unrated"
        assert any("unsupported_prefix_history" in r for r in res.missing_basis_reasons)

    def test_mixed_case_seamless_refusal(self):
        train_obs, _, common = load_benchmark_dataset()
        estimator = EmpiricalQiEstimator()
        estimator.fit(train_obs)

        ctx = EstimatorContext(
            technique=common["technique"],
            method=common["method"],
            budget=common["budget"],
            horizon_seconds=common["horizon_seconds"],
            target_complexity_class=common["target_complexity_class"],
            scenario_id="SeAmLeSs",
        )
        res = estimator.estimate(ctx, prefix=("asrep_request", "recover_asrep_secret"))
        assert res.status == "unrated"
        assert any(
            "unrepresentative_domain_transfer_seamless" in r for r in res.missing_basis_reasons
        )

    def test_unseen_domain_refusal(self):
        train_obs, _, common = load_benchmark_dataset()
        estimator = EmpiricalQiEstimator()
        estimator.fit(train_obs)

        ctx = EstimatorContext(
            technique=common["technique"],
            method=common["method"],
            budget=common["budget"],
            horizon_seconds=common["horizon_seconds"],
            target_complexity_class=common["target_complexity_class"],
            scenario_id="new-production-domain",
        )
        res = estimator.estimate(ctx, prefix=("asrep_request", "recover_asrep_secret"))
        assert res.status == "unrated"
        assert any("unsupported_domain_or_scenario" in r for r in res.missing_basis_reasons)

    def test_initial_material_present_allows_standalone_recovery(self):
        train_obs, _, common = load_benchmark_dataset()
        estimator = EmpiricalQiEstimator()
        estimator.fit(train_obs)

        ctx = EstimatorContext(
            technique=common["technique"],
            method=common["method"],
            budget=common["budget"],
            horizon_seconds=common["horizon_seconds"],
            target_complexity_class=common["target_complexity_class"],
            scenario_id="lab-scenario",
            initial_material_present=True,
        )
        # When material is explicitly present in initial state, standalone recovery is allowed
        res = estimator.estimate(ctx, prefix=("recover_asrep_secret",))
        assert res.status == "rated"
        assert res.lower_fraction == "32/125"

    def test_insufficient_sample_size_refusal(self):
        train_obs, _, common = load_benchmark_dataset()
        estimator = EmpiricalQiEstimator(min_sample_size=20)
        estimator.fit(train_obs[:10])

        ctx = EstimatorContext(
            technique=common["technique"],
            method=common["method"],
            budget=common["budget"],
            horizon_seconds=common["horizon_seconds"],
            target_complexity_class=common["target_complexity_class"],
            scenario_id="lab-scenario",
            is_synthetic_fixture=False,
        )
        res = estimator.estimate(ctx, prefix=("asrep_request", "recover_asrep_secret"))
        assert res.status == "unrated"
        assert any("insufficient_sample_size" in r for r in res.missing_basis_reasons)

    def test_repeated_trial_dependence_deduplication(self):
        common = {
            "technique": "recover_asrep_secret",
            "method": "hashcat_dictionary_rockyou_best64",
            "budget": 10000000,
            "horizon_seconds": 3600.0,
            "target_complexity_class": "standard_enterprise_user",
        }
        # 30 trials with identical outcome on the same hash
        repeated_obs = [
            TrialObservation(
                trial_id=f"rep_{i}",
                technique=common["technique"],
                method=common["method"],
                budget=common["budget"],
                horizon_seconds=common["horizon_seconds"],
                target_complexity_class=common["target_complexity_class"],
                outcome="success",
                target_hash_id="identical_hash_repeated",
                provenance_reference="lab://trials/rep",
            )
            for i in range(30)
        ]
        estimator = EmpiricalQiEstimator(min_sample_size=20)
        estimator.fit(repeated_obs)

        ctx = EstimatorContext(
            technique=common["technique"],
            method=common["method"],
            budget=common["budget"],
            horizon_seconds=common["horizon_seconds"],
            target_complexity_class=common["target_complexity_class"],
            scenario_id="lab-scenario",
            is_synthetic_fixture=False,
        )
        res = estimator.estimate(ctx, prefix=("asrep_request", "recover_asrep_secret"))
        # After deduplicating identical hash, effective n is 1 < 20 -> must be refused!
        assert res.status == "unrated"
        assert any("insufficient_sample_size" in r for r in res.missing_basis_reasons)

    def test_contradictory_duplicates_refused_order_independent(self):
        common = {
            "technique": "recover_asrep_secret",
            "method": "hashcat_dictionary_rockyou_best64",
            "budget": 10000000,
            "horizon_seconds": 3600.0,
            "target_complexity_class": "standard_enterprise_user",
        }
        ctx = EstimatorContext(
            technique=common["technique"],
            method=common["method"],
            budget=common["budget"],
            horizon_seconds=common["horizon_seconds"],
            target_complexity_class=common["target_complexity_class"],
            scenario_id="lab-scenario",
            is_synthetic_fixture=False,
        )

        obs_success_first = [
            TrialObservation(
                "t1",
                common["technique"],
                common["method"],
                common["budget"],
                common["horizon_seconds"],
                common["target_complexity_class"],
                "success",
                "shared_hash",
                "lab://t1",
            ),
            TrialObservation(
                "t2",
                common["technique"],
                common["method"],
                common["budget"],
                common["horizon_seconds"],
                common["target_complexity_class"],
                "failure",
                "shared_hash",
                "lab://t2",
            ),
        ] + [
            TrialObservation(
                f"t_{i}",
                common["technique"],
                common["method"],
                common["budget"],
                common["horizon_seconds"],
                common["target_complexity_class"],
                "success",
                f"hash_{i}",
                f"lab://t_{i}",
            )
            for i in range(25)
        ]
        est_sf = EmpiricalQiEstimator(min_sample_size=20)
        est_sf.fit(obs_success_first)
        res_sf = est_sf.estimate(ctx, prefix=("asrep_request", "recover_asrep_secret"))

        obs_failure_first = [
            TrialObservation(
                "t2",
                common["technique"],
                common["method"],
                common["budget"],
                common["horizon_seconds"],
                common["target_complexity_class"],
                "failure",
                "shared_hash",
                "lab://t2",
            ),
            TrialObservation(
                "t1",
                common["technique"],
                common["method"],
                common["budget"],
                common["horizon_seconds"],
                common["target_complexity_class"],
                "success",
                "shared_hash",
                "lab://t1",
            ),
        ] + [
            TrialObservation(
                f"t_{i}",
                common["technique"],
                common["method"],
                common["budget"],
                common["horizon_seconds"],
                common["target_complexity_class"],
                "success",
                f"hash_{i}",
                f"lab://t_{i}",
            )
            for i in range(25)
        ]
        est_ff = EmpiricalQiEstimator(min_sample_size=20)
        est_ff.fit(obs_failure_first)
        res_ff = est_ff.estimate(ctx, prefix=("asrep_request", "recover_asrep_secret"))

        # Both must refuse fail-closed with contradictory_repeated_trials regardless of input order
        assert res_sf.status == "unrated"
        assert res_ff.status == "unrated"
        assert any("contradictory_repeated_trials" in r for r in res_sf.missing_basis_reasons)
        assert any("contradictory_repeated_trials" in r for r in res_ff.missing_basis_reasons)

    def test_censored_and_invalid_outcomes_refused(self):
        common = {
            "technique": "recover_asrep_secret",
            "method": "hashcat_dictionary_rockyou_best64",
            "budget": 10000000,
            "horizon_seconds": 3600.0,
            "target_complexity_class": "standard_enterprise_user",
        }
        ctx = EstimatorContext(
            technique=common["technique"],
            method=common["method"],
            budget=common["budget"],
            horizon_seconds=common["horizon_seconds"],
            target_complexity_class=common["target_complexity_class"],
            scenario_id="lab-scenario",
            is_synthetic_fixture=False,
        )

        censored_obs = [
            TrialObservation(
                f"t_{i}",
                common["technique"],
                common["method"],
                common["budget"],
                common["horizon_seconds"],
                common["target_complexity_class"],
                "censored",
                f"hash_{i}",
                f"lab://t_{i}",
            )
            for i in range(25)
        ]
        est = EmpiricalQiEstimator(min_sample_size=20)
        est.fit(censored_obs)
        res = est.estimate(ctx, prefix=("asrep_request", "recover_asrep_secret"))

        assert res.status == "unrated"
        assert any("censored_or_invalid_trial_outcome" in r for r in res.missing_basis_reasons)

    def test_empty_provenance_refused(self):
        common = {
            "technique": "recover_asrep_secret",
            "method": "hashcat_dictionary_rockyou_best64",
            "budget": 10000000,
            "horizon_seconds": 3600.0,
            "target_complexity_class": "standard_enterprise_user",
        }
        ctx = EstimatorContext(
            technique=common["technique"],
            method=common["method"],
            budget=common["budget"],
            horizon_seconds=common["horizon_seconds"],
            target_complexity_class=common["target_complexity_class"],
            scenario_id="lab-scenario",
            is_synthetic_fixture=False,
        )

        empty_prov_obs = [
            TrialObservation(
                f"t_{i}",
                common["technique"],
                common["method"],
                common["budget"],
                common["horizon_seconds"],
                common["target_complexity_class"],
                "success",
                f"hash_{i}",
                "   ",
            )
            for i in range(25)
        ]
        est = EmpiricalQiEstimator(min_sample_size=20)
        est.fit(empty_prov_obs)
        res = est.estimate(ctx, prefix=("asrep_request", "recover_asrep_secret"))

        assert res.status == "unrated"
        assert any("missing_provenance_metadata" in r for r in res.missing_basis_reasons)

    def test_parameter_mismatch_does_not_pool_trials(self):
        train_obs, _, common = load_benchmark_dataset()
        estimator = EmpiricalQiEstimator()
        estimator.fit(train_obs)

        # Context specifies a different budget (5000000 instead of 10000000)
        ctx = EstimatorContext(
            technique=common["technique"],
            method=common["method"],
            budget=5000000,
            horizon_seconds=common["horizon_seconds"],
            target_complexity_class=common["target_complexity_class"],
            scenario_id="lab-scenario",
        )
        res = estimator.estimate(ctx, prefix=("asrep_request", "recover_asrep_secret"))
        # Must refuse because observed trials at budget 10M do not match budget 5M
        assert res.status == "unrated"
        assert any("insufficient_sample_size" in r for r in res.missing_basis_reasons)

    def test_zero_train_test_leakage(self):
        train_obs, holdout_obs, _ = load_benchmark_dataset()
        train_hashes = {o.target_hash_id for o in train_obs}
        holdout_hashes = {o.target_hash_id for o in holdout_obs}
        overlap = train_hashes & holdout_hashes
        assert len(overlap) == 0, f"Detected train/test hash leakage: {overlap}"

    def test_wildcard_lab_domain_rejected(self):
        train_obs, _, common = load_benchmark_dataset()
        estimator = EmpiricalQiEstimator()
        estimator.fit(train_obs)

        # Unverified scenarios with 'lab-' prefix must NOT bypass domain refusal
        for fake_lab_domain in ("lab-unseen-production-bank-ad", "lab-corp-enterprise", "lab-"):
            ctx = EstimatorContext(
                technique=common["technique"],
                method=common["method"],
                budget=common["budget"],
                horizon_seconds=common["horizon_seconds"],
                target_complexity_class=common["target_complexity_class"],
                scenario_id=fake_lab_domain,
            )
            res = estimator.estimate(ctx, prefix=("asrep_request", "recover_asrep_secret"))
            assert res.status == "unrated"
            assert any("unsupported_domain_or_scenario" in r for r in res.missing_basis_reasons)

    def test_invalid_prefix_step_identifiers_fail_closed(self):
        train_obs, _, common = load_benchmark_dataset()
        estimator = EmpiricalQiEstimator()
        estimator.fit(train_obs)

        ctx = EstimatorContext(
            technique=common["technique"],
            method=common["method"],
            budget=common["budget"],
            horizon_seconds=common["horizon_seconds"],
            target_complexity_class=common["target_complexity_class"],
            scenario_id="lab-scenario",
        )
        # None or empty string in prefix must NOT raise unhandled exception
        for bad_prefix in [
            (None, "recover_asrep_secret"),
            ("", "recover_asrep_secret"),
            ("   ", "recover_asrep_secret"),
        ]:
            res = estimator.estimate(ctx, prefix=bad_prefix)
            assert res.status == "unrated"
            assert any("invalid_prefix_step_identifier" in r for r in res.missing_basis_reasons)

    def test_empty_observation_identifiers_refused(self):
        common = {
            "technique": "recover_asrep_secret",
            "method": "hashcat_dictionary_rockyou_best64",
            "budget": 10000000,
            "horizon_seconds": 3600.0,
            "target_complexity_class": "standard_enterprise_user",
        }
        ctx = EstimatorContext(
            technique=common["technique"],
            method=common["method"],
            budget=common["budget"],
            horizon_seconds=common["horizon_seconds"],
            target_complexity_class=common["target_complexity_class"],
            scenario_id="lab-scenario",
        )
        # Empty trial_id
        obs_empty_trial = [
            TrialObservation(
                trial_id="",
                technique=common["technique"],
                method=common["method"],
                budget=common["budget"],
                horizon_seconds=common["horizon_seconds"],
                target_complexity_class=common["target_complexity_class"],
                outcome="success",
                target_hash_id=f"hash_{i}",
                provenance_reference="lab://trial",
            )
            for i in range(25)
        ]
        est = EmpiricalQiEstimator(min_sample_size=20)
        est.fit(obs_empty_trial)
        res = est.estimate(ctx, prefix=("asrep_request", "recover_asrep_secret"))
        assert res.status == "unrated"
        assert any("missing_trial_id" in r for r in res.missing_basis_reasons)

        # Empty target_hash_id
        obs_empty_hash = [
            TrialObservation(
                trial_id=f"t_{i}",
                technique=common["technique"],
                method=common["method"],
                budget=common["budget"],
                horizon_seconds=common["horizon_seconds"],
                target_complexity_class=common["target_complexity_class"],
                outcome="success",
                target_hash_id="",
                provenance_reference="lab://trial",
            )
            for i in range(25)
        ]
        est = EmpiricalQiEstimator(min_sample_size=20)
        est.fit(obs_empty_hash)
        res = est.estimate(ctx, prefix=("asrep_request", "recover_asrep_secret"))
        assert res.status == "unrated"
        assert any("missing_target_hash_id" in r for r in res.missing_basis_reasons)

    def test_missing_complexity_class_and_non_finite_horizon(self):
        train_obs, _, common = load_benchmark_dataset()
        estimator = EmpiricalQiEstimator()
        estimator.fit(train_obs)

        # Missing target_complexity_class
        for bad_complexity in [None, "", "   "]:
            ctx = EstimatorContext(
                technique=common["technique"],
                method=common["method"],
                budget=common["budget"],
                horizon_seconds=common["horizon_seconds"],
                target_complexity_class=bad_complexity,
                scenario_id="lab-scenario",
            )
            res = estimator.estimate(ctx, prefix=("asrep_request", "recover_asrep_secret"))
            assert res.status == "unrated"
            assert any(
                "missing_target_complexity_class_specification" in r
                for r in res.missing_basis_reasons
            )

        # Non-finite horizon
        for bad_horizon in [float("nan"), float("inf"), float("-inf")]:
            ctx = EstimatorContext(
                technique=common["technique"],
                method=common["method"],
                budget=common["budget"],
                horizon_seconds=bad_horizon,
                target_complexity_class=common["target_complexity_class"],
                scenario_id="lab-scenario",
            )
            res = estimator.estimate(ctx, prefix=("asrep_request", "recover_asrep_secret"))
            assert res.status == "unrated"
            assert any("missing_horizon_specification" in r for r in res.missing_basis_reasons)

    def test_unsupported_actor_capability_refused(self):
        train_obs, _, common = load_benchmark_dataset()
        estimator = EmpiricalQiEstimator()
        estimator.fit(train_obs)

        ctx = EstimatorContext(
            technique=common["technique"],
            method=common["method"],
            budget=common["budget"],
            horizon_seconds=common["horizon_seconds"],
            target_complexity_class=common["target_complexity_class"],
            scenario_id="lab-scenario",
            actor_capability="unprivileged_user_no_gpu",
        )
        res = estimator.estimate(ctx, prefix=("asrep_request", "recover_asrep_secret"))
        assert res.status == "unrated"
        assert any("unsupported_actor_capability" in r for r in res.missing_basis_reasons)


class TestHoldoutEvaluation:
    """Verification of holdout predictive quality and metrics."""

    def test_holdout_evaluation_metrics(self):
        train_obs, holdout_obs, common = load_benchmark_dataset()
        estimator = EmpiricalQiEstimator()
        estimator.fit(train_obs)

        ctx = EstimatorContext(
            technique=common["technique"],
            method=common["method"],
            budget=common["budget"],
            horizon_seconds=common["horizon_seconds"],
            target_complexity_class=common["target_complexity_class"],
            scenario_id="lab-benchmark-scenario",
            is_synthetic_fixture=False,
        )

        eval_res = evaluate_holdout_quality(
            estimator, ctx, holdout_obs, prefix=("asrep_request", "recover_asrep_secret")
        )
        assert eval_res["status"] == "evaluated"
        assert eval_res["holdout_sample_size"] == 40
        assert eval_res["holdout_empirical_rate"] == 14 / 40  # 0.35
        # Single-split consistency diagnostic: predicted CI [0.2562, 0.4932] covers 0.35
        assert eval_res["holdout_rate_in_interval_diagnostic"] is True
        assert eval_res["coverage_hit"] is True
        assert "Single-split consistency diagnostic" in eval_res["coverage_diagnostic_note"]
        assert 0.0 < eval_res["brier_score"] < 0.5
        assert 0.0 < eval_res["log_loss"] < 2.0
        assert eval_res["predicted_rational_bounds"] == ("32/125", "247/500")

    def test_holdout_evaluation_refuses_seamless(self):
        train_obs, holdout_obs, common = load_benchmark_dataset()
        estimator = EmpiricalQiEstimator()
        estimator.fit(train_obs)

        ctx = EstimatorContext(
            technique=common["technique"],
            method=common["method"],
            budget=common["budget"],
            horizon_seconds=common["horizon_seconds"],
            target_complexity_class=common["target_complexity_class"],
            scenario_id="scenario-seamless-host-to-dc",
            is_synthetic_fixture=False,
        )

        eval_res = evaluate_holdout_quality(
            estimator, ctx, holdout_obs, prefix=("asrep_request", "recover_asrep_secret")
        )
        assert eval_res["status"] == "unrated"
        assert any(
            "unrepresentative_domain_transfer_seamless" in r for r in eval_res["refusal_reasons"]
        )

    def test_holdout_repeated_hash_deduplication(self):
        train_obs, _, common = load_benchmark_dataset()
        estimator = EmpiricalQiEstimator()
        estimator.fit(train_obs)

        ctx = EstimatorContext(
            technique=common["technique"],
            method=common["method"],
            budget=common["budget"],
            horizon_seconds=common["horizon_seconds"],
            target_complexity_class=common["target_complexity_class"],
            scenario_id="lab-benchmark-scenario",
        )

        # Create holdout dataset with 10 repeated observations with identical outcome on same hash
        repeated_holdout = [
            TrialObservation(
                trial_id=f"holdout_rep_{i}",
                technique=common["technique"],
                method=common["method"],
                budget=common["budget"],
                horizon_seconds=common["horizon_seconds"],
                target_complexity_class=common["target_complexity_class"],
                outcome="failure",
                target_hash_id="same_holdout_hash",
                provenance_reference="lab://trials/test/rep",
            )
            for i in range(10)
        ]
        eval_res = evaluate_holdout_quality(
            estimator, ctx, repeated_holdout, prefix=("asrep_request", "recover_asrep_secret")
        )
        # Deduplication must reduce sample size to 1 independent observation
        assert eval_res["status"] == "evaluated"
        assert eval_res["holdout_sample_size"] == 1

    def test_holdout_contradictory_duplicates_detected(self):
        train_obs, _, common = load_benchmark_dataset()
        estimator = EmpiricalQiEstimator()
        estimator.fit(train_obs)

        ctx = EstimatorContext(
            technique=common["technique"],
            method=common["method"],
            budget=common["budget"],
            horizon_seconds=common["horizon_seconds"],
            target_complexity_class=common["target_complexity_class"],
            scenario_id="lab-benchmark-scenario",
        )

        contradictory_holdout = [
            TrialObservation(
                "h1",
                common["technique"],
                common["method"],
                common["budget"],
                common["horizon_seconds"],
                common["target_complexity_class"],
                "success",
                "same_holdout_hash",
                "lab://t1",
            ),
            TrialObservation(
                "h2",
                common["technique"],
                common["method"],
                common["budget"],
                common["horizon_seconds"],
                common["target_complexity_class"],
                "failure",
                "same_holdout_hash",
                "lab://t2",
            ),
        ]
        eval_res = evaluate_holdout_quality(
            estimator, ctx, contradictory_holdout, prefix=("asrep_request", "recover_asrep_secret")
        )
        assert eval_res["status"] == "contradictory_holdout_data"

    def test_evaluator_rejects_train_as_holdout_leakage(self):
        train_obs, _, common = load_benchmark_dataset()
        estimator = EmpiricalQiEstimator()
        estimator.fit(train_obs)

        ctx = EstimatorContext(
            technique=common["technique"],
            method=common["method"],
            budget=common["budget"],
            horizon_seconds=common["horizon_seconds"],
            target_complexity_class=common["target_complexity_class"],
            scenario_id="lab-benchmark-scenario",
            is_synthetic_fixture=False,
        )

        eval_res = evaluate_holdout_quality(
            estimator, ctx, train_obs, prefix=("asrep_request", "recover_asrep_secret")
        )
        assert eval_res["status"] == "leakage_detected"
        assert eval_res["diagnostic"] == "train_holdout_overlap_detected"
        assert eval_res["overlapping_hash_count"] == 60

    def test_evaluator_rejects_partial_hash_overlap(self):
        train_obs, holdout_obs, common = load_benchmark_dataset()
        estimator = EmpiricalQiEstimator()
        estimator.fit(train_obs)

        ctx = EstimatorContext(
            technique=common["technique"],
            method=common["method"],
            budget=common["budget"],
            horizon_seconds=common["horizon_seconds"],
            target_complexity_class=common["target_complexity_class"],
            scenario_id="lab-benchmark-scenario",
            is_synthetic_fixture=False,
        )

        # Inject single training hash into holdout
        contaminated_holdout = list(holdout_obs) + [train_obs[0]]
        eval_res = evaluate_holdout_quality(
            estimator, ctx, contaminated_holdout, prefix=("asrep_request", "recover_asrep_secret")
        )
        assert eval_res["status"] == "leakage_detected"
        assert eval_res["overlapping_hash_count"] == 1

    def test_evaluator_rejects_artifact_digest_leakage(self):
        train_obs, holdout_obs, common = load_benchmark_dataset()
        estimator = EmpiricalQiEstimator()
        estimator.fit(train_obs)

        ctx = EstimatorContext(
            technique=common["technique"],
            method=common["method"],
            budget=common["budget"],
            horizon_seconds=common["horizon_seconds"],
            target_complexity_class=common["target_complexity_class"],
            scenario_id="lab-benchmark-scenario",
            is_synthetic_fixture=False,
        )

        # Create holdout with fresh IDs but identical artifact_digest from training set
        contaminated_holdout = [
            TrialObservation(
                trial_id=f"clean_trial_{i}",
                technique=o.technique,
                method=o.method,
                budget=o.budget,
                horizon_seconds=o.horizon_seconds,
                target_complexity_class=o.target_complexity_class,
                outcome=o.outcome,
                target_hash_id=f"clean_hash_{i}",
                provenance_reference=f"lab://clean_prov/{i}",
                artifact_digest=train_obs[0].artifact_digest,
            )
            for i, o in enumerate(holdout_obs)
        ]
        eval_res = evaluate_holdout_quality(
            estimator, ctx, contaminated_holdout, prefix=("asrep_request", "recover_asrep_secret")
        )
        assert eval_res["status"] == "leakage_detected"
        assert eval_res["diagnostic"] == "train_holdout_overlap_detected"
        assert eval_res["overlapping_digest_count"] == 1

    def test_evaluator_rejects_invalid_holdout_records(self):
        train_obs, _, common = load_benchmark_dataset()
        estimator = EmpiricalQiEstimator()
        estimator.fit(train_obs)

        ctx = EstimatorContext(
            technique=common["technique"],
            method=common["method"],
            budget=common["budget"],
            horizon_seconds=common["horizon_seconds"],
            target_complexity_class=common["target_complexity_class"],
            scenario_id="lab-benchmark-scenario",
            is_synthetic_fixture=False,
        )

        # Empty trial_id in holdout
        invalid_holdout = [
            TrialObservation(
                trial_id="",
                technique=common["technique"],
                method=common["method"],
                budget=common["budget"],
                horizon_seconds=common["horizon_seconds"],
                target_complexity_class=common["target_complexity_class"],
                outcome="success",
                target_hash_id=f"hash_{i}",
                provenance_reference=f"lab://holdout/{i}",
            )
            for i in range(25)
        ]
        eval_res = evaluate_holdout_quality(
            estimator, ctx, invalid_holdout, prefix=("asrep_request", "recover_asrep_secret")
        )
        assert eval_res["status"] == "invalid_holdout_data"
        assert "missing_trial_id" in eval_res["refusal_reason"]


class TestEngineIntegrationAndWeek3Preservation:
    """Verify integration with assessment.py and strict preservation of Week 3 release."""

    def test_engine_conformance_lab_rated_path(self):
        train_obs, _, common = load_benchmark_dataset()
        estimator = EmpiricalQiEstimator()
        estimator.fit(train_obs)

        ctx = EstimatorContext(
            technique=common["technique"],
            method=common["method"],
            budget=common["budget"],
            horizon_seconds=common["horizon_seconds"],
            target_complexity_class=common["target_complexity_class"],
            scenario_id="lab-benchmark-scenario",
            is_synthetic_fixture=False,
            action_aliases={"w-req": "asrep_request", "w-rec": "recover_asrep_secret"},
        )

        entry1 = {
            "prefix": ["w-req"],
            "lower": "9/10",
            "upper": "19/20",
            "basis_category": "empirical_calibration",
            "rationale": "High network availability",
        }
        entry2 = estimator.export_bounds_table_entry(ctx, prefix=("w-req", "w-rec"))
        assert entry2 is not None

        decoded_query = {
            "query_metadata": {
                "active_work_budget": 5,
            },
            "work_units_ledger": {
                "w-req": {
                    "rating_status": "rated",
                    "overlap_state": "independent",
                    "computed_cost": 1,
                },
                "w-rec": {
                    "rating_status": "rated",
                    "overlap_state": "independent",
                    "computed_cost": 2,
                },
            },
            "conditional_bounds_table": validate_and_decode_bounds_table([entry1, entry2]),
            "conditional_bounds_records": [entry1, entry2],
        }

        candidate_envelope = {
            "candidate_id": "cand-lab-01",
            "bound_action_ids": ["a-req", "a-rec"],
            "target_asset_id": "C0",
            "structural_routes": [],
            "gate_status": "feasible",
            "gates_evaluation": {"g1": "satisfied"},
            "impact": "High",
            "impact_status": "rated",
            "work_packets": [["w-req"], ["w-rec"]],
        }

        # Mock replay candidate sequence
        import src.engine.ranking.assessment as asm

        original_replay = asm.replay_candidate_sequence
        try:
            asm.replay_candidate_sequence = lambda dq, ce, **kw: ce
            result = assess_candidate_program(decoded_query, candidate_envelope)
        finally:
            asm.replay_candidate_sequence = original_replay

        assert result["status"] == "feasible"
        assert result["effort_status"] == "rated"
        assert result["effort"] == 3
        assert result["likelihood_status"] == "rated"
        lo, hi = result["likelihood_interval"]
        # Exact fraction multiplication: 9/10 * 32/125 = 144/625, 19/20 * 247/500 = 4693/10000
        assert lo == Fraction(9, 10) * Fraction(32, 125)
        assert hi == Fraction(19, 20) * Fraction(247, 500)
        assert lo == Fraction(144, 625)
        assert hi == Fraction(4693, 10000)

    def test_engine_conformance_seamless_unrated_path(self):
        train_obs, _, common = load_benchmark_dataset()
        estimator = EmpiricalQiEstimator()
        estimator.fit(train_obs)

        # SEAMLESS context is refused by estimator -> bounds table has NO entry for w-rec
        ctx = EstimatorContext(
            technique=common["technique"],
            method=common["method"],
            budget=common["budget"],
            horizon_seconds=common["horizon_seconds"],
            target_complexity_class=common["target_complexity_class"],
            scenario_id="scenario-seamless-host-to-dc",
            is_synthetic_fixture=False,
            action_aliases={"w-req": "asrep_request", "w-rec": "recover_asrep_secret"},
        )
        entry2 = estimator.export_bounds_table_entry(ctx, prefix=("w-req", "w-rec"))
        assert entry2 is None  # Estimator refuses to export bounds for SEAMLESS

        entry1 = {
            "prefix": ["w-req"],
            "lower": "9/10",
            "upper": "19/20",
            "basis_category": "scenario_assumption",
        }
        decoded_query = {
            "query_metadata": {
                "active_work_budget": 5,
            },
            "work_units_ledger": {
                "w-req": {
                    "rating_status": "rated",
                    "overlap_state": "independent",
                    "computed_cost": 1,
                },
                "w-rec": {
                    "rating_status": "unrated",
                    "overlap_state": "independent",
                    "computed_cost": None,
                },
            },
            "conditional_bounds_table": validate_and_decode_bounds_table([entry1]),
            "conditional_bounds_records": [entry1],
        }

        candidate_envelope = {
            "candidate_id": "cand-seamless-01",
            "bound_action_ids": ["a-req", "a-rec"],
            "target_asset_id": "DC01",
            "structural_routes": [],
            "gate_status": "feasible",
            "gates_evaluation": {"g1": "satisfied"},
            "impact": "High",
            "impact_status": "rated",
            "work_packets": [["w-req"], ["w-rec"]],
        }

        import src.engine.ranking.assessment as asm

        original_replay = asm.replay_candidate_sequence
        try:
            asm.replay_candidate_sequence = lambda dq, ce, **kw: ce
            result = assess_candidate_program(decoded_query, candidate_envelope)
        finally:
            asm.replay_candidate_sequence = original_replay

        assert result["status"] == "feasible"
        # Effort is unrated because w-rec is unrated
        assert result["effort_status"] == "unrated"
        # Likelihood is unrated because prefix ("w-req", "w-rec") is missing in bounds table
        assert result["likelihood_status"] == "unrated"
        assert result["likelihood_interval"] is None
        assert "likelihood_unrated" in result["diagnostic_reasons"]

    def test_week3_21_parameters_release_undisturbed(self):
        # Week 3 release canonical digest must be strictly preserved
        release_path = Path("docs/research/ratings/week3-closeout/reviewed-release.json")
        assert release_path.exists()
        with open(release_path, encoding="utf-8") as f:
            release_data = json.load(f)

        meta = release_data["bundle_metadata"]
        assert meta["bundle_id"] == "seamless-week3-human-reviewed"
        assert meta["bundle_version"] == "1.0.0"
        expected_digest = "sha256:20f67e8604f6399b5b360e412bb30bf898f4d788f13b69c08c78ef2df73d3358"
        assert meta["bundle_digest"] == expected_digest

        decisions_path = Path("docs/research/ratings/week3-closeout/parameter-decisions-final.json")
        assert decisions_path.exists()
        with open(decisions_path, encoding="utf-8") as f:
            decisions_data = json.load(f)
        assert len(decisions_data["decisions"]) == 21

    def test_full_evaluation_report_artifact(self, tmp_path):
        from scripts.research.empirical_qi_estimator import run_full_evaluation

        tmp_out = tmp_path / "test_report.json"
        rep = run_full_evaluation(output_path=tmp_out)
        assert tmp_out.exists()
        assert rep["report_id"] == "evidence-qi-calibration-237"
        assert rep["refusal_audit"]["all_passed"] is True
        assert rep["refusal_audit"]["total_cases"] == 19
        assert rep["holdout_evaluation"]["holdout_rate_in_interval_diagnostic"] is True
        assert rep["baseline_comparison"]["status"] == "unavailable"
        assert rep["baseline_comparison"]["seamless_status"] == "unrated"
        assert rep["lab_pilot_estimation"]["bounds_table_entry"]["prefix"] == [
            "asrep_request",
            "recover_asrep_secret",
        ]
        assert rep["lab_pilot_estimation"]["basis_category"] == "controlled_lab_benchmark_prototype"
        assert (
            rep["lab_pilot_estimation"]["dataset_classification"]
            == "controlled_lab_benchmark_prototype"
        )
        assert (
            rep["lab_pilot_estimation"]["evidence_disposition"]
            == "quarantined_prototype_not_for_production_ranking"
        )
        assert (
            rep["lab_pilot_estimation"]["bounds_table_entry"]["basis_category"]
            == "controlled_lab_benchmark_prototype"
        )
        assert rep["lab_pilot_estimation"]["production_ranking_bounds_table_entry"] is None

    def test_manifest_scope_negative_probes(self):
        train_obs, _, common = load_benchmark_dataset()
        with open(FIXTURES_DIR / "lab_benchmark_dataset.json", encoding="utf-8") as f:
            manifest = json.load(f)["evidence_manifest"]

        estimator = EmpiricalQiEstimator(manifest=manifest)
        estimator.fit(train_obs)

        # Probe 1: lab-scenario outside manifest supported_scenario_ids
        ctx_unsupported_scen = EstimatorContext(
            technique=common["technique"],
            method=common["method"],
            budget=common["budget"],
            horizon_seconds=common["horizon_seconds"],
            target_complexity_class=common["target_complexity_class"],
            scenario_id="lab-scenario",
            actor_capability="offline_gpu_cracking",
        )
        res_scen = estimator.estimate(
            ctx_unsupported_scen, prefix=("asrep_request", "recover_asrep_secret")
        )
        assert res_scen.status == "unrated"
        assert any("unsupported_domain_or_scenario" in r for r in res_scen.missing_basis_reasons)

        # Probe 2: standalone recovery outside supported_prefix_sequences
        ctx_standalone = EstimatorContext(
            technique=common["technique"],
            method=common["method"],
            budget=common["budget"],
            horizon_seconds=common["horizon_seconds"],
            target_complexity_class=common["target_complexity_class"],
            scenario_id="lab-benchmark-asrep-v1",
            initial_material_present=True,
            actor_capability="offline_gpu_cracking",
        )
        res_standalone = estimator.estimate(ctx_standalone, prefix=("recover_asrep_secret",))
        assert res_standalone.status == "unrated"
        assert any("unsupported_prefix_history" in r for r in res_standalone.missing_basis_reasons)

        # Probe 3: actor_capability=None rejected when manifest defines supported capabilities
        ctx_no_actor = EstimatorContext(
            technique=common["technique"],
            method=common["method"],
            budget=common["budget"],
            horizon_seconds=common["horizon_seconds"],
            target_complexity_class=common["target_complexity_class"],
            scenario_id="lab-benchmark-asrep-v1",
            actor_capability=None,
        )
        res_no_actor = estimator.estimate(
            ctx_no_actor, prefix=("asrep_request", "recover_asrep_secret")
        )
        assert res_no_actor.status == "unrated"
        assert any(
            "missing_actor_capability_specification" in r
            for r in res_no_actor.missing_basis_reasons
        )

        # Probe 4: actor_capability not in manifest supported capabilities
        ctx_bad_actor = EstimatorContext(
            technique=common["technique"],
            method=common["method"],
            budget=common["budget"],
            horizon_seconds=common["horizon_seconds"],
            target_complexity_class=common["target_complexity_class"],
            scenario_id="lab-benchmark-asrep-v1",
            actor_capability="offline_cpu_cracking",
        )
        res_bad_actor = estimator.estimate(
            ctx_bad_actor, prefix=("asrep_request", "recover_asrep_secret")
        )
        assert res_bad_actor.status == "unrated"
        assert any("unsupported_actor_capability" in r for r in res_bad_actor.missing_basis_reasons)

        # Probe 5: strictly valid manifest context is rated with prototype label
        ctx_valid = EstimatorContext(
            technique=common["technique"],
            method=common["method"],
            budget=common["budget"],
            horizon_seconds=common["horizon_seconds"],
            target_complexity_class=common["target_complexity_class"],
            scenario_id="lab-benchmark-asrep-v1",
            actor_capability="offline_gpu_cracking",
        )
        res_valid = estimator.estimate(ctx_valid, prefix=("asrep_request", "recover_asrep_secret"))
        assert res_valid.status == "rated"
        assert res_valid.basis_category == "controlled_lab_benchmark_prototype"

        # Probe 6: manifest with explicitly empty supported_scenario_ids refuses scenarios
        est_empty_scen = EmpiricalQiEstimator(manifest={"supported_scenario_ids": []})
        est_empty_scen.fit(train_obs)
        res_empty_scen = est_empty_scen.estimate(
            ctx_valid, prefix=("asrep_request", "recover_asrep_secret")
        )
        assert res_empty_scen.status == "unrated"
        assert any(
            "unsupported_domain_or_scenario" in r for r in res_empty_scen.missing_basis_reasons
        )

        # Probe 7: manifest with explicitly empty actor capabilities refuses all capabilities
        est_empty_act = EmpiricalQiEstimator(manifest={"supported_actor_capabilities": []})
        est_empty_act.fit(train_obs)
        res_empty_act = est_empty_act.estimate(
            ctx_valid, prefix=("asrep_request", "recover_asrep_secret")
        )
        assert res_empty_act.status == "unrated"
        assert any("unsupported_actor_capability" in r for r in res_empty_act.missing_basis_reasons)

        # Probe 8: manifest with explicitly empty prefix sequences refuses all prefixes
        est_empty_pref = EmpiricalQiEstimator(manifest={"supported_prefix_sequences": []})
        est_empty_pref.fit(train_obs)
        res_empty_pref = est_empty_pref.estimate(
            ctx_valid, prefix=("asrep_request", "recover_asrep_secret")
        )
        assert res_empty_pref.status == "unrated"
        assert any("unsupported_prefix_history" in r for r in res_empty_pref.missing_basis_reasons)

    def test_run_full_evaluation_resilience_on_holdout_refusals(self, tmp_path):
        import shutil

        from scripts.research.empirical_qi_estimator import run_full_evaluation

        fixtures_copy = tmp_path / "fixtures"
        fixtures_copy.mkdir(parents=True, exist_ok=True)
        shutil.copy(FIXTURES_DIR / "refusal_cases.json", fixtures_copy / "refusal_cases.json")

        with open(FIXTURES_DIR / "lab_benchmark_dataset.json", encoding="utf-8") as f:
            base_data = json.load(f)

        # 1. Test censored holdout record does not throw KeyError 'holdout_sample_size'
        data_censored = json.loads(json.dumps(base_data))
        data_censored["holdout_observations"][0]["outcome"] = "censored"
        with open(fixtures_copy / "lab_benchmark_dataset.json", "w", encoding="utf-8") as f:
            json.dump(data_censored, f)

        rep_censored = run_full_evaluation(
            fixtures_dir=fixtures_copy, output_path=tmp_path / "out_censored.json"
        )
        assert rep_censored["holdout_evaluation"]["status"] == "invalid_holdout_data"
        assert rep_censored["holdout_evaluation"]["holdout_empirical_rate"] is None
        assert rep_censored["holdout_evaluation"]["brier_score"] is None
        assert (
            "censored_or_invalid_trial_outcome"
            in rep_censored["holdout_evaluation"]["refusal_reason"]
        )

        # 2. Test leakage in holdout does not throw KeyError and preserves diagnostics
        data_leakage = json.loads(json.dumps(base_data))
        train_first_hash = data_leakage["training_observations"][0]["target_hash_id"]
        data_leakage["holdout_observations"][0]["target_hash_id"] = train_first_hash
        with open(fixtures_copy / "lab_benchmark_dataset.json", "w", encoding="utf-8") as f:
            json.dump(data_leakage, f)

        rep_leakage = run_full_evaluation(
            fixtures_dir=fixtures_copy, output_path=tmp_path / "out_leakage.json"
        )
        assert rep_leakage["holdout_evaluation"]["status"] == "leakage_detected"
        assert rep_leakage["holdout_evaluation"]["holdout_empirical_rate"] is None
        assert rep_leakage["holdout_evaluation"]["refusal_diagnostics"] is not None
        assert (
            rep_leakage["holdout_evaluation"]["refusal_diagnostics"]["overlapping_hash_count"] >= 1
        )

        # 3. Test empty holdout does not throw KeyError
        data_empty = json.loads(json.dumps(base_data))
        data_empty["holdout_observations"] = []
        with open(fixtures_copy / "lab_benchmark_dataset.json", "w", encoding="utf-8") as f:
            json.dump(data_empty, f)

        rep_empty = run_full_evaluation(
            fixtures_dir=fixtures_copy, output_path=tmp_path / "out_empty.json"
        )
        assert rep_empty["holdout_evaluation"]["status"] == "empty_holdout"
        assert rep_empty["holdout_evaluation"]["holdout_sample_size"] == 0
        assert rep_empty["holdout_evaluation"]["holdout_empirical_rate"] is None

    def test_promotion_probes_cannot_bypass_quarantine(self):
        with open(FIXTURES_DIR / "lab_benchmark_dataset.json", encoding="utf-8") as f:
            bench_data = json.load(f)
        manifest = bench_data.get("evidence_manifest")
        train_obs, _, common = load_benchmark_dataset()

        ctx = EstimatorContext(
            technique=common["technique"],
            method=common["method"],
            budget=common["budget"],
            horizon_seconds=common["horizon_seconds"],
            target_complexity_class=common["target_complexity_class"],
            scenario_id="lab-benchmark-asrep-v1",
            actor_capability="offline_gpu_cracking",
        )

        # Probe 1: constructor override fails to promote (refused for conflict)
        manifest_proto = dict(manifest)
        manifest_proto["dataset_classification"] = "controlled_lab_benchmark_prototype"
        est_p1 = EmpiricalQiEstimator(
            manifest=manifest_proto, dataset_classification="empirical_measurement"
        )
        est_p1.fit(train_obs)
        res_p1 = est_p1.estimate(ctx, prefix=("asrep_request", "recover_asrep_secret"))
        assert res_p1.status == "unrated"
        assert any("conflicting_dataset_classification" in r for r in res_p1.missing_basis_reasons)
        assert (
            est_p1.export_bounds_table_entry(
                ctx, prefix=("asrep_request", "recover_asrep_secret"), for_production_ranking=True
            )
            is None
        )

        # Probe 2: fit override fails to promote (refused for conflict)
        est_p2 = EmpiricalQiEstimator(manifest=manifest_proto)
        est_p2.fit(train_obs, dataset_classification="empirical_measurement")
        res_p2 = est_p2.estimate(ctx, prefix=("asrep_request", "recover_asrep_secret"))
        assert res_p2.status == "unrated"
        assert any("conflicting_dataset_classification" in r for r in res_p2.missing_basis_reasons)
        assert (
            est_p2.export_bounds_table_entry(
                ctx, prefix=("asrep_request", "recover_asrep_secret"), for_production_ranking=True
            )
            is None
        )

        # Probe 3: caller classification without manifest fails to promote (missing manifest)
        est_p3 = EmpiricalQiEstimator(manifest=None, dataset_classification="empirical_measurement")
        est_p3.fit(train_obs)
        res_p3 = est_p3.estimate(ctx, prefix=("asrep_request", "recover_asrep_secret"))
        assert res_p3.status == "unrated"
        assert any("missing_evidence_manifest" in r for r in res_p3.missing_basis_reasons)
        assert (
            est_p3.export_bounds_table_entry(
                ctx, prefix=("asrep_request", "recover_asrep_secret"), for_production_ranking=True
            )
            is None
        )

        # Probe 4: unreviewed manifest fails to promote (refused for unreviewed manifest)
        unreviewed_manifest = {
            "dataset_classification": "empirical_measurement",
            "supported_scenario_ids": ["lab-benchmark-asrep-v1"],
            "supported_actor_capabilities": ["offline_gpu_cracking"],
            "supported_prefix_sequences": [["asrep_request", "recover_asrep_secret"]],
        }
        est_p4 = EmpiricalQiEstimator(manifest=unreviewed_manifest)
        est_p4.fit(train_obs)
        res_p4 = est_p4.estimate(ctx, prefix=("asrep_request", "recover_asrep_secret"))
        assert res_p4.status == "unrated"
        assert any("unreviewed_evidence_manifest" in r for r in res_p4.missing_basis_reasons)
        assert (
            est_p4.export_bounds_table_entry(
                ctx, prefix=("asrep_request", "recover_asrep_secret"), for_production_ranking=True
            )
            is None
        )

        # Probe 5: reviewed manifest cannot promote prototype observations (provenance check)
        reviewed_manifest = {
            "dataset_classification": "empirical_measurement",
            "review_status": "reviewed",
            "reviewed_by": "sec-team@research.ad",
            "reviewed_at": "2026-10-09T00:00:00Z",
            "package_id": "lab-reviewed-asrep-v1",
            "supported_scenario_ids": ["lab-benchmark-asrep-v1"],
            "supported_actor_capabilities": ["offline_gpu_cracking"],
            "supported_prefix_sequences": [["asrep_request", "recover_asrep_secret"]],
        }
        est_p5 = EmpiricalQiEstimator(manifest=reviewed_manifest)
        est_p5.fit(train_obs)
        res_p5 = est_p5.estimate(ctx, prefix=("asrep_request", "recover_asrep_secret"))
        assert res_p5.status == "unrated"
        assert any("unverified_prototype_provenance" in r for r in res_p5.missing_basis_reasons)
        assert (
            est_p5.export_bounds_table_entry(
                ctx, prefix=("asrep_request", "recover_asrep_secret"), for_production_ranking=True
            )
            is None
        )

        # Probe 6: default prototype manifest remains prototype and quarantined
        est_p6 = EmpiricalQiEstimator(manifest=manifest)
        est_p6.fit(train_obs)
        res_p6 = est_p6.estimate(ctx, prefix=("asrep_request", "recover_asrep_secret"))
        assert res_p6.status == "rated"
        assert res_p6.basis_category == "controlled_lab_benchmark_prototype"
        assert res_p6.evidence_disposition == "quarantined_prototype_not_for_production_ranking"
        assert (
            est_p6.export_bounds_table_entry(
                ctx, prefix=("asrep_request", "recover_asrep_secret"), for_production_ranking=True
            )
            is None
        )
        assert (
            est_p6.export_bounds_table_entry(
                ctx, prefix=("asrep_request", "recover_asrep_secret"), for_production_ranking=False
            )
            is not None
        )
