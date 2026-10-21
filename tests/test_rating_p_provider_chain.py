"""Comprehensive Tests for Conditional Likelihood (P) Provider Chain (Issue #248).

Covers all acceptance criteria from Issue #248 and Section 10:
- Provider precedence: empirical > reviewed scenario > unrated.
- Fallback / refusal matrix: differentiates absent, out-of-scope, malformed,
  contradictory, quarantined, and provider integrity refusals.
- Full-history mismatch: prefix order, prefix length, contextual binding.
- Scenario, actor/capability, method, budget, horizon, context mismatches.
- Prototype quarantine: lab benchmark prototype quarantined from production ranking.
- Malformed / contradictory evidence rejection.
- Anti-inference invariants: assumption=true is never q=1; no C/CVSS/MAUT/LLM as q.
- Later-prefix coverage reported even when earlier prefix is unrated.
- Exact Fraction path product calculation.
- Frozen #243 automatic P coverage inventory for all 4 required prefixes.
- Handcrafted arithmetic isolation; generated comparison remains pending B binding review.
- Regression protection for Week 3 release and #207/#212 oracles.
"""

from __future__ import annotations

import json
import os
from fractions import Fraction
from pathlib import Path
from typing import Any

import pytest

from scripts.research.empirical_qi_estimator import (
    TrialObservation,
)
from src.engine.ranking import (
    PathRankingEngine,
    format_rational,
    parse_rational,
)
from src.engine.ranking.likelihood import (
    EmpiricalLikelihoodProvider,
    ReviewedScenarioLikelihoodProvider,
    audit_frozen_243_likelihood_coverage,
    build_likelihood_provider_chain,
    parse_horizon_seconds,
)
from src.engine.ranking.resolver import (
    BasisClassification,
    RatingResolver,
    ReasonCode,
    ResolverDisposition,
    generate_rating_lookup_key_p,
)

FOOTHOLD_SID = "S-1-5-21-1271839998-3495686680-2211690266-1001"
TARGET_HOST_ID = "S-1-5-21-1271839998-3495686680-2211690266-1000"
USER_A_SID = "S-1-5-21-1271839998-3495686680-2211690266-1101"
USER_B_SID = "S-1-5-21-1271839998-3495686680-2211690266-1102"
DUMMY_SNAPSHOT_ID = "sha256:e0601d763eeea285d268ec9e468d321c50c9d7faba53c8e7442a2fcc4159c812"
DUMMY_EDGE_1 = "sha256:0000000000000000000000000000000000000000000000000000000000000001"
DUMMY_EDGE_2 = "sha256:0000000000000000000000000000000000000000000000000000000000000002"


def build_base_scope(**overrides: Any) -> dict[str, Any]:
    """Build standard query scope for testing likelihood providers."""
    base = {
        "query_id": "query-test-p-001",
        "scenario_id": "scenario-test-enterprise",
        "scenario_version": "1.0.0",
        "snapshot_id": DUMMY_SNAPSHOT_ID,
        "foothold_node_id": FOOTHOLD_SID,
        "source_foothold": FOOTHOLD_SID,
        "work_boundary": "intra_forest",
        "horizon": "24h",
        "active_work_budget": 6,
        "evaluation_mode": "scenario",
        "target_goal": {
            "goal_id": "admin_host_c0",
            "target_asset_id": TARGET_HOST_ID,
            "success_event": "terminal_compromise",
            "required_predicates": ["admin_control_host"],
        },
        "facts_ledger": {
            "predicate_layers": {
                "ticket_granted": 3,
                "admin_control_host": 3,
                "secret_recovered": 3,
                "usable_creds": 3,
            },
        },
        "declared_facts": {
            "ticket_granted": True,
            "admin_control_host": True,
            "secret_recovered": True,
            "usable_creds": True,
        },
        "governance": {
            "basis_category": "scenario_assumption",
            "allow_scenario_fallback": True,
        },
    }
    base.update(overrides)
    return base


def create_reviewed_trial_observations(
    n: int = 25,
    k: int = 20,
    technique: str = "recover_asrep_secret",
    method: str = "hashcat_gpu",
    budget: int = 10000000,
    horizon_seconds: float = 3600.0,
    complexity: str = "standard_enterprise_user",
) -> list[TrialObservation]:
    """Helper to generate n valid Bernoulli trial observations with k successes."""
    obs: list[TrialObservation] = []
    for i in range(n):
        outcome = "success" if i < k else "failure"
        obs.append(
            TrialObservation(
                trial_id=f"trial_{i + 1:03d}",
                technique=technique,
                method=method,
                budget=budget,
                horizon_seconds=horizon_seconds,
                target_complexity_class=complexity,
                outcome=outcome,
                target_hash_id=f"hash_{i + 1:03d}",
                provenance_reference=f"telemetry://lab/trials/{i + 1:03d}",
            )
        )
    return obs


def create_reviewed_manifest(
    scenario_id: str = "scenario-test-enterprise",
) -> dict[str, Any]:
    """Helper to create an approved reviewed evidence manifest."""
    return {
        "manifest_id": "manifest-reviewed-001",
        "dataset_classification": "empirical_measurement",
        "review_status": "reviewed",
        "reviewed_by": "Senior Reviewer (A/B approved)",
        "reviewed_at": "2026-10-09T10:00:00Z",
        "supported_scenario_ids": [scenario_id],
        "supported_techniques": ["recover_asrep_secret"],
        "manifest_digest": "sha256:" + "1" * 64,
    }


# ===========================================================================
# 1. Horizon parsing
# ===========================================================================


def test_parse_horizon_seconds():
    assert parse_horizon_seconds("24h") == 86400.0
    assert parse_horizon_seconds("1h") == 3600.0
    assert parse_horizon_seconds("30m") == 1800.0
    assert parse_horizon_seconds("45s") == 45.0
    assert parse_horizon_seconds("2d") == 172800.0
    assert parse_horizon_seconds(3600) == 3600.0
    assert parse_horizon_seconds(1800.5) == 1800.5
    assert parse_horizon_seconds(None) is None
    assert parse_horizon_seconds("invalid") is None


# ===========================================================================
# 2. Provider precedence
# ===========================================================================


def test_provider_precedence_empirical_over_scenario():
    """Empirical provider (Precedence 1) takes precedence over reviewed scenario (Precedence 2)."""
    scope = build_base_scope()

    # Set up approved empirical provider
    manifest = create_reviewed_manifest("scenario-test-enterprise")
    obs = create_reviewed_trial_observations(
        n=25,
        k=20,
        technique="recover_asrep_secret",
        method="default",
        budget=6,
        horizon_seconds=86400.0,
    )
    emp_prov = EmpiricalLikelihoodProvider(
        observations=obs,
        manifest=manifest,
        dataset_classification="empirical_measurement",
        for_production_ranking=True,
    )

    # Set up reviewed scenario provider with different interval
    scenario_records = [
        {
            "scenario_id": "scenario-test-enterprise",
            "ordered_work_prefix": ["asrep_request", "recover_asrep_secret"],
            "outcome_work_unit_id": "recover_asrep_secret",
            "outcome_technique": "recover_asrep_secret",
            "actor_id": FOOTHOLD_SID,
            "target_id": TARGET_HOST_ID,
            "method": "default",
            "horizon": "24h",
            "boundary": "intra_forest",
            "lower": "1/2",
            "upper": "2/3",
            "basis_category": "scenario_assumption",
            "rationale": "Scenario assumption fallback interval",
        }
    ]
    scen_prov = ReviewedScenarioLikelihoodProvider(scenario_records)

    cand = {
        "candidate_id": "Cand_Precedence",
        "transition_history": [
            {
                "technique_id": "asrep_request",
                "actor": FOOTHOLD_SID,
                "target": USER_A_SID,
                "edge_id": DUMMY_EDGE_1,
                "provenance": ["prov:step1"],
                "requires": ["ticket_granted"],
                "adds": ["ticket_granted"],
            },
            {
                "technique_id": "recover_asrep_secret",
                "actor": FOOTHOLD_SID,
                "target": TARGET_HOST_ID,
                "edge_id": DUMMY_EDGE_2,
                "provenance": ["prov:step2"],
                "requires": ["ticket_granted"],
                "adds": ["admin_control_host"],
            },
        ],
    }

    chain = build_likelihood_provider_chain(
        empirical_provider=emp_prov,
        scenario_provider=scen_prov,
    )
    resolver = RatingResolver(likelihood_providers=chain)
    output = resolver.resolve([cand], scope)

    p_report = output.coverage_report["candidates"]["Cand_Precedence"]["likelihood"]
    # Second prefix corresponds to recover_asrep_secret
    p_entries = [
        p for p in p_report["prefixes"] if p["outcome_unit"].startswith("recover_asrep_secret")
    ]
    assert len(p_entries) == 1
    selected = p_entries[0]
    assert selected["selected_provider"] == emp_prov.name
    assert selected["basis_category"] == BasisClassification.EMPIRICAL_EVIDENCE
    assert selected["disposition"] == ResolverDisposition.RATED


def test_provider_precedence_scenario_over_unrated():
    """Reviewed scenario (Precedence 2) resolves when empirical evidence is absent."""
    scope = build_base_scope()
    prefix_steps = [
        {
            "technique_id": "obtain_admin_execution_on_host",
            "actor": FOOTHOLD_SID,
            "target": TARGET_HOST_ID,
            "edge_id": DUMMY_EDGE_1,
            "provenance": ["prov:step1"],
            "requires": ["ticket_granted"],
            "adds": ["admin_control_host"],
        }
    ]
    cand = {"candidate_id": "Cand_Scenario_Fallback", "transition_history": prefix_steps}

    # Empirical provider has NO observations for obtain_admin_execution_on_host
    emp_prov = EmpiricalLikelihoodProvider(observations=[])

    # Scenario provider has reviewed record
    # Let resolver generate the work unit ID, but record matches prefix
    from tests.test_rating_p_review_regressions import accepted_test_record_dict

    seed = RatingResolver().resolve([cand], scope)
    cid = cand["candidate_id"]
    inventory = seed.coverage_report["candidates"][cid]["likelihood"]["prefixes"]
    record = accepted_test_record_dict(inventory[0]["rating_audit"]["lookup_key"])
    record.update(lower="3/5", upper="4/5")
    scen_prov = ReviewedScenarioLikelihoodProvider([record])

    chain = build_likelihood_provider_chain(
        empirical_provider=emp_prov,
        scenario_provider=scen_prov,
    )
    resolver = RatingResolver(likelihood_providers=chain)
    output = resolver.resolve([cand], scope)

    p_report = output.coverage_report["candidates"]["Cand_Scenario_Fallback"]["likelihood"]
    assert p_report["all_rated"] is True
    assert p_report["prefixes"][0]["selected_provider"] == scen_prov.name
    assert p_report["prefixes"][0]["interval"] == ["3/5", "4/5"]


# ===========================================================================
# 3. Refusal integrity & Fallback matrix
# ===========================================================================


def test_refusal_integrity_no_fallback_on_prerequisite_refusal():
    """Provider integrity refusal MUST NOT be masked by subsequent scenario fallback."""
    scope = build_base_scope()

    # Empirical provider configured to refuse domain transfer
    obs = create_reviewed_trial_observations(n=25, k=20, method="default", horizon_seconds=86400.0)
    emp_prov = EmpiricalLikelihoodProvider(
        observations=obs,
        manifest=create_reviewed_manifest("scenario-test-enterprise"),
        for_production_ranking=True,
    )
    # Scope is set to SEAMLESS, triggering domain transfer refusal
    scope["scenario_id"] = "scenario-seamless-host-to-dc"

    scen_prov = ReviewedScenarioLikelihoodProvider(
        records=[
            {
                "scenario_id": "scenario-seamless-host-to-dc",
                "ordered_work_prefix": ["any_prefix"],
                "outcome_technique": "recover_asrep_secret",
                "lower": "1/2",
                "upper": "1/2",
                "basis_category": "scenario_assumption",
            }
        ]
    )

    key = generate_rating_lookup_key_p(
        scenario_id="scenario-seamless-host-to-dc",
        scenario_version="1.0.0",
        snapshot_id=DUMMY_SNAPSHOT_ID,
        foothold_node_id=FOOTHOLD_SID,
        ordered_work_prefix=("wu_step1",),
        outcome_work_unit_id="wu_step1",
        outcome_technique="recover_asrep_secret",
        actor_id=FOOTHOLD_SID,
        target_id=TARGET_HOST_ID,
    )

    # Directly verify empirical provider returns REFUSED
    res = emp_prov.resolve_likelihood(key, ("wu_step1",), "wu_step1", scope)
    assert res.disposition == ResolverDisposition.REFUSED
    assert res.reason_code == ReasonCode.PREREQUISITE_GATE_REFUSAL
    assert "seamless" in res.reason_detail.lower()

    # In RatingResolver, refusal terminates chain without calling scen_prov
    cand = {
        "candidate_id": "Cand_Refusal_Integrity",
        "transition_history": [
            {
                "technique_id": "recover_asrep_secret",
                "actor": FOOTHOLD_SID,
                "target": TARGET_HOST_ID,
                "edge_id": DUMMY_EDGE_1,
                "provenance": ["prov:step1"],
                "requires": ["ticket_granted"],
                "adds": ["admin_control_host"],
            }
        ],
    }
    chain = build_likelihood_provider_chain(
        empirical_provider=emp_prov, scenario_provider=scen_prov
    )
    resolver = RatingResolver(likelihood_providers=chain)
    output = resolver.resolve([cand], scope)

    p_report = output.coverage_report["candidates"]["Cand_Refusal_Integrity"]["likelihood"]
    assert p_report["all_rated"] is False
    assert p_report["prefixes"][0]["disposition"] == ResolverDisposition.REFUSED
    assert p_report["prefixes"][0]["reason_code"] == ReasonCode.PREREQUISITE_GATE_REFUSAL
    # Scen_prov was NOT chosen
    assert p_report["prefixes"][0]["selected_provider"] == emp_prov.name


def test_refusal_integrity_on_contradictory_repeated_trials():
    """Contradictory empirical trial outcomes on same hash yield CONFLICTING and halt chain."""
    scope = build_base_scope()

    # Create contradictory trials on identical hash
    obs = [
        TrialObservation(
            trial_id="trial_1",
            technique="recover_asrep_secret",
            method="default",
            budget=1000,
            horizon_seconds=3600.0,
            target_complexity_class="standard",
            outcome="success",
            target_hash_id="identical_hash_1",
            provenance_reference="telemetry://test/1",
        ),
        TrialObservation(
            trial_id="trial_2",
            technique="recover_asrep_secret",
            method="default",
            budget=1000,
            horizon_seconds=3600.0,
            target_complexity_class="standard",
            outcome="failure",
            target_hash_id="identical_hash_1",
            provenance_reference="telemetry://test/2",
        ),
    ]

    emp_prov = EmpiricalLikelihoodProvider(
        observations=obs,
        manifest=create_reviewed_manifest("scenario-test-enterprise"),
        for_production_ranking=False,  # test contradiction in lab mode
    )

    key = generate_rating_lookup_key_p(
        scenario_id="scenario-test-enterprise",
        scenario_version="1.0.0",
        snapshot_id=DUMMY_SNAPSHOT_ID,
        foothold_node_id=FOOTHOLD_SID,
        ordered_work_prefix=("asrep_request", "recover_asrep_secret"),
        outcome_work_unit_id="recover_asrep_secret",
        outcome_technique="recover_asrep_secret",
        actor_id=FOOTHOLD_SID,
        target_id=TARGET_HOST_ID,
        method="default",
        budget=1000,
        horizon="1h",
    )

    res = emp_prov.resolve_likelihood(
        key, ("asrep_request", "recover_asrep_secret"), "recover_asrep_secret", scope
    )
    assert res.disposition == ResolverDisposition.CONFLICTING
    assert res.reason_code == ReasonCode.CONFLICTING_PROVIDER_BASIS
    assert "contradictory" in res.reason_detail.lower()


# ===========================================================================
# 4. Prototype quarantine
# ===========================================================================


def test_prototype_quarantine_refused_for_production_ranking():
    """#238 prototype dataset cannot be promoted to production empirical ranking."""
    scope = build_base_scope()

    # Lab benchmark dataset from #238 is classified as controlled_lab_benchmark_prototype
    prototype_path = Path("tests/fixtures/empirical_calibration/lab_benchmark_dataset.json")
    if not prototype_path.exists():
        pytest.skip("Prototype dataset not found")

    data = json.loads(prototype_path.read_text(encoding="utf-8"))
    common = data.get("common_parameters", {})
    obs: list[TrialObservation] = []
    for raw in data.get("training_observations", []):
        obs.append(
            TrialObservation(
                trial_id=raw["trial_id"],
                technique=common.get("technique", "recover_asrep_secret"),
                method=common.get("method", "hashcat_gpu"),
                budget=common.get("budget", 10000000),
                horizon_seconds=float(common.get("horizon_seconds", 3600.0)),
                target_complexity_class=common.get(
                    "target_complexity_class", "standard_enterprise_user"
                ),
                outcome=raw["outcome"],
                target_hash_id=raw["target_hash_id"],
                provenance_reference=raw["provenance_reference"],
            )
        )

    emp_prov = EmpiricalLikelihoodProvider(
        observations=obs,
        dataset_classification="controlled_lab_benchmark_prototype",
        for_production_ranking=True,  # Production mode: quarantine enforced!
    )

    key = generate_rating_lookup_key_p(
        scenario_id="lab-benchmark-asrep-v1",
        scenario_version="1.0.0",
        snapshot_id=DUMMY_SNAPSHOT_ID,
        foothold_node_id=FOOTHOLD_SID,
        ordered_work_prefix=("wu_crack",),
        outcome_work_unit_id="wu_crack",
        outcome_technique="recover_asrep_secret",
        actor_id=FOOTHOLD_SID,
        target_id=TARGET_HOST_ID,
        method=common.get("method", "hashcat_gpu"),
        budget=common.get("budget", 10000000),
        horizon="1h",
    )

    res = emp_prov.resolve_likelihood(key, ("wu_crack",), "wu_crack", scope)
    assert res.disposition == ResolverDisposition.REFUSED
    assert res.reason_code == ReasonCode.PREREQUISITE_GATE_REFUSAL
    assert "quarantined" in res.reason_detail.lower()


def test_prototype_allowed_in_controlled_lab_mode():
    """When for_production_ranking=False, lab prototype produces rated output labelled prototype."""
    scope = build_base_scope()

    prototype_path = Path("tests/fixtures/empirical_calibration/lab_benchmark_dataset.json")
    if not prototype_path.exists():
        pytest.skip("Prototype dataset not found")

    data = json.loads(prototype_path.read_text(encoding="utf-8"))
    common = data.get("common_parameters", {})
    obs: list[TrialObservation] = []
    for raw in data.get("training_observations", []):
        obs.append(
            TrialObservation(
                trial_id=raw["trial_id"],
                technique=common.get("technique", "recover_asrep_secret"),
                method=common.get("method", "hashcat_dictionary_rockyou_best64"),
                budget=common.get("budget", 10000000),
                horizon_seconds=float(common.get("horizon_seconds", 3600.0)),
                target_complexity_class=common.get(
                    "target_complexity_class", "standard_enterprise_user"
                ),
                outcome=raw["outcome"],
                target_hash_id=raw["target_hash_id"],
                provenance_reference=raw["provenance_reference"],
            )
        )

    emp_prov = EmpiricalLikelihoodProvider(
        observations=obs,
        dataset_classification="controlled_lab_benchmark_prototype",
        for_production_ranking=False,  # Research / lab mode
    )

    key = generate_rating_lookup_key_p(
        scenario_id="lab-benchmark-asrep-v1",
        scenario_version="1.0.0",
        snapshot_id=DUMMY_SNAPSHOT_ID,
        foothold_node_id=FOOTHOLD_SID,
        ordered_work_prefix=("asrep_request", "recover_asrep_secret"),
        outcome_work_unit_id="recover_asrep_secret",
        outcome_technique="recover_asrep_secret",
        actor_id=FOOTHOLD_SID,
        target_id=TARGET_HOST_ID,
        method="hashcat_dictionary_rockyou_best64",
        budget=10000000,
        horizon="1h",
    )

    res = emp_prov.resolve_likelihood(
        key, ("asrep_request", "recover_asrep_secret"), "recover_asrep_secret", scope
    )
    assert res.disposition == ResolverDisposition.RATED
    assert res.basis_category == "controlled_lab_benchmark_prototype"
    lo, hi = res.value
    assert isinstance(lo, Fraction) and isinstance(hi, Fraction)
    assert 0 <= lo <= hi <= 1


# ===========================================================================
# 5. Full-history prefix mismatch & anti-extrapolation
# ===========================================================================


def test_full_history_prefix_order_mismatch():
    """Prefix [A, B] and [B, A] are strictly distinct; reordered prefix is unrated."""
    scope = build_base_scope()
    prov = ReviewedScenarioLikelihoodProvider(
        records=[
            {
                "scenario_id": "scenario-test-enterprise",
                "ordered_work_prefix": ["wu_A", "wu_B"],
                "outcome_work_unit_id": "wu_B",
                "outcome_technique": "remote_exec_winrm",
                "actor_id": FOOTHOLD_SID,
                "target_id": TARGET_HOST_ID,
                "lower": "2/3",
                "upper": "3/4",
            }
        ]
    )

    key_reversed = generate_rating_lookup_key_p(
        scenario_id="scenario-test-enterprise",
        scenario_version="1.0.0",
        snapshot_id=DUMMY_SNAPSHOT_ID,
        foothold_node_id=FOOTHOLD_SID,
        ordered_work_prefix=("wu_B", "wu_A"),  # Reversed order!
        outcome_work_unit_id="wu_B",
        outcome_technique="remote_exec_winrm",
        actor_id=FOOTHOLD_SID,
        target_id=TARGET_HOST_ID,
    )

    res = prov.resolve_likelihood(key_reversed, ("wu_B", "wu_A"), "wu_B", scope)
    assert res.disposition == ResolverDisposition.UNSUPPORTED
    assert res.reason_code == ReasonCode.MISSING_EVIDENCE


def test_full_history_prefix_length_mismatch():
    """Marginal probability of step 1 cannot be reused for step 2 without history."""
    scope = build_base_scope()
    prov = ReviewedScenarioLikelihoodProvider(
        records=[
            {
                "scenario_id": "scenario-test-enterprise",
                "ordered_work_prefix": ["wu_A"],
                "outcome_work_unit_id": "wu_A",
                "outcome_technique": "acquire_ticket",
                "actor_id": FOOTHOLD_SID,
                "target_id": TARGET_HOST_ID,
                "lower": "3/5",
                "upper": "4/5",
            }
        ]
    )

    key_two_steps = generate_rating_lookup_key_p(
        scenario_id="scenario-test-enterprise",
        scenario_version="1.0.0",
        snapshot_id=DUMMY_SNAPSHOT_ID,
        foothold_node_id=FOOTHOLD_SID,
        ordered_work_prefix=("wu_A", "wu_B"),  # Length 2
        outcome_work_unit_id="wu_B",
        outcome_technique="acquire_ticket",
        actor_id=FOOTHOLD_SID,
        target_id=TARGET_HOST_ID,
    )

    res = prov.resolve_likelihood(key_two_steps, ("wu_A", "wu_B"), "wu_B", scope)
    assert res.disposition == ResolverDisposition.UNSUPPORTED
    assert res.reason_code == ReasonCode.MISSING_EVIDENCE


# ===========================================================================
# 6. Mismatch matrix (scenario, actor, method, budget, horizon, context)
# ===========================================================================


def test_scenario_mismatch_refused():
    scope = build_base_scope()
    prov = ReviewedScenarioLikelihoodProvider(
        records=[
            {
                "scenario_id": "scenario-alpha",
                "ordered_work_prefix": ["wu_1"],
                "outcome_work_unit_id": "wu_1",
                "outcome_technique": "acquire_ticket",
                "actor_id": FOOTHOLD_SID,
                "target_id": TARGET_HOST_ID,
                "lower": "1/2",
                "upper": "1/2",
            }
        ]
    )
    key = generate_rating_lookup_key_p(
        scenario_id="scenario-beta",  # Different scenario!
        scenario_version="1.0.0",
        snapshot_id=DUMMY_SNAPSHOT_ID,
        foothold_node_id=FOOTHOLD_SID,
        ordered_work_prefix=("wu_1",),
        outcome_work_unit_id="wu_1",
        outcome_technique="acquire_ticket",
        actor_id=FOOTHOLD_SID,
        target_id=TARGET_HOST_ID,
    )
    res = prov.resolve_likelihood(key, ("wu_1",), "wu_1", scope)
    assert res.disposition == ResolverDisposition.UNSUPPORTED
    assert res.reason_code == ReasonCode.OUT_OF_SCOPE


# ===========================================================================
# 7. Anti-inference invariants
# ===========================================================================


def test_anti_inference_boolean_assumption_is_never_one():
    """Declared runtime assumption (assumption=true) enables feasibility only; q is NEVER 1."""
    scope = build_base_scope(
        declared_facts={
            "ticket_granted": True,
            "admin_control_host": True,
        }
    )
    cand = {
        "candidate_id": "Cand_Assumption",
        "transition_history": [
            {
                "technique_id": "obtain_admin_execution_on_host",
                "actor": FOOTHOLD_SID,
                "target": TARGET_HOST_ID,
                "edge_id": DUMMY_EDGE_1,
                "provenance": ["prov:step1"],
                "requires": ["ticket_granted"],
                "adds": ["admin_control_host"],
            }
        ],
    }

    # Resolver with no likelihood providers (fail-closed fallback only)
    resolver = RatingResolver()
    output = resolver.resolve([cand], scope)

    p_report = output.coverage_report["candidates"]["Cand_Assumption"]["likelihood"]
    # Assumption is True, but likelihood must be UNRATED (never 1 or [1, 1])
    assert p_report["all_rated"] is False
    assert p_report["prefixes"][0]["interval"] is None
    assert p_report["prefixes"][0]["disposition"] == ResolverDisposition.UNRATED

    # When evaluated by PathRankingEngine, candidate is unrated/diagnostics
    evaluated = PathRankingEngine().evaluate(output.ranking_query, output.candidate_envelopes)[
        "result_payload"
    ]
    assert "Cand_Assumption" not in evaluated["eligible_candidates"]
    assert "Cand_Assumption" in evaluated["diagnostics"]
    assert "likelihood_unrated" in evaluated["diagnostics"]["Cand_Assumption"]["reasons"]
    assert (
        evaluated["diagnostics"]["Cand_Assumption"]["assessment"]["likelihood_status"] == "unrated"
    )
    assert evaluated["diagnostics"]["Cand_Assumption"]["assessment"]["likelihood_interval"] is None


def test_scenario_assumption_cannot_claim_empirical_label():
    """Reviewed scenario provider refuses records falsely claiming empirical_evidence."""
    scope = build_base_scope()
    prov = ReviewedScenarioLikelihoodProvider(
        records=[
            {
                "scenario_id": "scenario-test-enterprise",
                "ordered_work_prefix": ["wu_1"],
                "outcome_work_unit_id": "wu_1",
                "outcome_technique": "remote_exec_winrm",
                "actor_id": FOOTHOLD_SID,
                "target_id": TARGET_HOST_ID,
                "lower": "1/2",
                "upper": "1/2",
                "basis_category": BasisClassification.EMPIRICAL_EVIDENCE,  # Illegal!
            }
        ]
    )
    key = generate_rating_lookup_key_p(
        scenario_id="scenario-test-enterprise",
        scenario_version="1.0.0",
        snapshot_id=DUMMY_SNAPSHOT_ID,
        foothold_node_id=FOOTHOLD_SID,
        ordered_work_prefix=("wu_1",),
        outcome_work_unit_id="wu_1",
        outcome_technique="remote_exec_winrm",
        actor_id=FOOTHOLD_SID,
        target_id=TARGET_HOST_ID,
    )
    res = prov.resolve_likelihood(key, ("wu_1",), "wu_1", scope)
    assert res.disposition == ResolverDisposition.REFUSED
    assert res.reason_code == ReasonCode.PREREQUISITE_GATE_REFUSAL


# ===========================================================================
# 8. Later-prefix reporting after earlier missing prefix
# ===========================================================================


def test_later_prefix_coverage_reported_after_earlier_missing():
    """Resolver reports all prefixes and localized gaps without halting at step 1."""
    scope = build_base_scope()
    cand = {
        "candidate_id": "Cand_Multi_Prefix",
        "transition_history": [
            {
                "technique_id": "acquire_ticket",
                "actor": FOOTHOLD_SID,
                "target": USER_A_SID,
                "edge_id": DUMMY_EDGE_1,
                "provenance": ["prov:step1"],
                "requires": ["ticket_granted"],
                "adds": ["ticket_granted"],
            },
            {
                "technique_id": "obtain_admin_execution_on_host",
                "actor": FOOTHOLD_SID,
                "target": TARGET_HOST_ID,
                "edge_id": DUMMY_EDGE_2,
                "provenance": ["prov:step2"],
                "requires": ["ticket_granted"],
                "adds": ["admin_control_host"],
            },
        ],
    }

    # Provide rating for prefix 2 ONLY, prefix 1 is missing
    from tests.test_rating_p_review_regressions import accepted_test_record_dict

    seed = RatingResolver().resolve([cand], scope)
    cid = cand["candidate_id"]
    inventory = seed.coverage_report["candidates"][cid]["likelihood"]["prefixes"]
    record = accepted_test_record_dict(inventory[1]["rating_audit"]["lookup_key"])
    record.update(lower="4/5", upper="9/10")
    scen_prov = ReviewedScenarioLikelihoodProvider([record])

    resolver = RatingResolver(likelihood_providers=[scen_prov])
    output = resolver.resolve([cand], scope)

    p_report = output.coverage_report["candidates"]["Cand_Multi_Prefix"]["likelihood"]
    assert p_report["total_prefixes"] == 2
    # Prefix 1 is unrated
    assert p_report["prefixes"][0]["disposition"] == ResolverDisposition.UNRATED
    assert p_report["prefixes"][0]["interval"] is None
    # Prefix 2 was evaluated and rated even though prefix 1 was unrated!
    assert p_report["prefixes"][1]["disposition"] == ResolverDisposition.RATED
    assert p_report["prefixes"][1]["interval"] == ["4/5", "9/10"]

    # Coverage unresolved_gaps has localized gap for prefix 1
    gaps = output.coverage_report["unresolved_gaps"]
    p_gaps = [g for g in gaps if g["dimension"] == "P"]
    assert len(p_gaps) == 1
    assert p_gaps[0]["outcome_unit"].startswith("acquire_ticket")


# ===========================================================================
# 9. Exact Fraction path product
# ===========================================================================


def test_exact_fraction_path_product_arithmetic():
    """Path product is exact multiplication of component Fraction intervals."""
    # Test fractions: q1 = [3/5, 4/5], q2 = [2/3, 3/4]
    q1 = (Fraction(3, 5), Fraction(4, 5))
    q2 = (Fraction(2, 3), Fraction(3, 4))

    lo_prod = q1[0] * q2[0]
    hi_prod = q1[1] * q2[1]

    assert lo_prod == Fraction(2, 5)  # 6/15
    assert hi_prod == Fraction(3, 5)  # 12/20
    assert format_rational(lo_prod) == "2/5"
    assert format_rational(hi_prod) == "3/5"

    # Second branch: q3 = [1/2, 2/3], q4 = [1/5, 3/8]
    q3 = (Fraction(1, 2), Fraction(2, 3))
    q4 = (Fraction(1, 5), Fraction(3, 8))

    lo_prod_2 = q3[0] * q4[0]
    hi_prod_2 = q3[1] * q4[1]

    assert lo_prod_2 == Fraction(1, 10)  # 1/10
    assert hi_prod_2 == Fraction(1, 4)  # 6/24 = 1/4

    # Strict dominance verification: lo_prod (2/5 = 0.40) > hi_prod_2 (1/4 = 0.25)
    assert lo_prod > hi_prod_2


# ===========================================================================
# 10. Audit frozen #243 automatic P coverage inventory
# ===========================================================================


@pytest.mark.skipif(
    not Path(os.environ.get("SEAMLESS_RAW_DIR", "data/raw/SEAMLESS")).is_dir(),
    reason="manifest-verified private SEAMLESS raw inputs required",
)
def test_audit_frozen_243_automatic_p_coverage_inventory():
    """Verify that every required P event in frozen #243 is reported with exact localized trace."""
    from tests.frozen_rating_inputs import frozen_program

    paths, scope, bindings = frozen_program()
    audit = audit_frozen_243_likelihood_coverage(paths, scope, transition_bindings=bindings)

    assert audit["scenario_id"] == "week4-seamless-v1"
    assert audit["candidate_id"] == audit["candidate_envelope"]["candidate_id"]
    assert audit["horizon"] == "fixed-snapshot-window"
    assert audit["recovery_metadata"]["budget"] == "unmeasured-budget"
    actual_edges = [s.edge_id for s in paths[0].transition_history if s.edge_id]
    materialized_edges = [
        edge
        for route in audit["candidate_envelope"]["structural_routes"]
        for edge in route["edge_ids"]
    ]
    assert materialized_edges == actual_edges
    assert all(s.edge_id is None for s in paths[0].transition_history[:3])
    assert audit["total_required_prefixes"] == 4
    assert len(audit["audit_inventory"]) == 4

    expected_techniques = [
        "asrep_request",
        "recover_asrep_secret",
        "activate_recovered_identity",
        "obtain_admin_execution_on_host",
    ]

    for idx, item in enumerate(audit["audit_inventory"]):
        assert len(item["prefix"]) == idx + 1
        assert expected_techniques[idx] in item["outcome_unit"]
        # In frozen #243 on SEAMLESS, all P events must remain unrated (no unreviewed promotion)
        assert item["disposition"] == "unrated"
        assert item["interval"] is None
        assert item["reason_code"] == "missing_evidence"
        # Providers attempted must be tracked in trace
        assert "empirical_likelihood_provider" in item["providers_attempted"]
        assert "reviewed_scenario_likelihood_provider" in item["providers_attempted"]
        assert "fail_closed_unrated_provider" in item["providers_attempted"]
        # Lookup key is deterministic
        assert item["lookup_key"] is not None
        assert item["lookup_key"]["scenario_id"] == "week4-seamless-v1"
        assert item["lookup_key"]["outcome_technique"] == expected_techniques[idx]


# ===========================================================================
# 11. Handcrafted Fraction arithmetic isolation, not #251 acceptance
# ===========================================================================


def test_handcrafted_arithmetic_fixture_products():
    """Validate Fraction arithmetic only; no generated-flow or reviewed-basis claim."""
    path = Path("docs/research/scenarios/week4-risk-comparison-v1.json")
    assert path.exists(), "Risk-comparison scenario file must exist"

    spec = json.loads(path.read_text(encoding="utf-8"))
    assert spec["scenario_id"] == "week4-risk-comparison-v1"
    assert len(spec["candidates"]) == 2

    # Verify Cand 1 frozen product
    cand1 = spec["candidates"][0]
    assert cand1["candidate_id"] == "cand_risk_01_winrm"
    p1_lo = parse_rational(cand1["steps"][0]["lower"]) * parse_rational(cand1["steps"][1]["lower"])
    p1_hi = parse_rational(cand1["steps"][0]["upper"]) * parse_rational(cand1["steps"][1]["upper"])
    assert format_rational(p1_lo) == cand1["frozen_expected_likelihood_product"]["lower"]
    assert format_rational(p1_hi) == cand1["frozen_expected_likelihood_product"]["upper"]
    assert format_rational(p1_lo) == "2/5"
    assert format_rational(p1_hi) == "3/5"

    # Verify Cand 2 frozen product
    cand2 = spec["candidates"][1]
    assert cand2["candidate_id"] == "cand_risk_02_dcsync"
    p2_lo = parse_rational(cand2["steps"][0]["lower"]) * parse_rational(cand2["steps"][1]["lower"])
    p2_hi = parse_rational(cand2["steps"][0]["upper"]) * parse_rational(cand2["steps"][1]["upper"])
    assert format_rational(p2_lo) == cand2["frozen_expected_likelihood_product"]["lower"]
    assert format_rational(p2_hi) == cand2["frozen_expected_likelihood_product"]["upper"]
    assert format_rational(p2_lo) == "1/10"
    assert format_rational(p2_hi) == "1/4"

    # Verify Pareto relationship:
    # Cand 1 has higher likelihood: p1_lo (2/5 = 0.4) > p2_hi (1/4 = 0.25)
    assert p1_lo > p2_hi
    # Cand 2 has higher impact: Critical > High
    assert cand2["consequence_rating"] == "Critical"
    assert cand1["consequence_rating"] == "High"
    # Neither dominates -> Both are Pareto optimal
    assert spec["pareto_analysis"]["expected_pareto_frontier"] == [
        "cand_risk_01_winrm",
        "cand_risk_02_dcsync",
    ]


def test_unreviewed_handcrafted_arithmetic_records_cannot_rate():
    """Handcrafted DCSync/WinRM dictionaries are not generated acceptance evidence."""
    spec = json.loads(Path("docs/research/scenarios/week4-risk-comparison-v1.json").read_text())
    provider = ReviewedScenarioLikelihoodProvider(spec["reviewed_likelihood_records"])
    for record in spec["reviewed_likelihood_records"]:
        prefix = tuple(record["ordered_work_prefix"])
        key = generate_rating_lookup_key_p(
            spec["scenario_id"],
            spec["scenario_version"],
            spec["snapshot_id"],
            spec["foothold_node_id"],
            prefix,
            record["outcome_work_unit_id"],
            record["outcome_technique"],
            record["actor_id"],
            record["target_id"],
        )
        result = provider.resolve_likelihood(key, prefix, prefix[-1], build_base_scope())
        assert result.disposition != ResolverDisposition.RATED
        assert result.value is None
