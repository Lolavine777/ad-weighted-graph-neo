"""Unit and contract tests for the Rating Resolver (Specification v1.0.0, Issue #246).

Verifies:
1. Deterministic versioned identities for bound actions, work units, and lookup keys.
2. Candidate enumeration order invariance.
3. Negative probes for context/method/budget/horizon/auth/policy collisions.
4. Ordered full-history active-work prefix preservation for Likelihood (P).
5. Passive steps and state propagation do not create work units or fake rating events.
6. Shared persistent preparation is reused and deduplicated across steps and candidates.
7. Dispositions, structured reason codes, and refusal integrity (cannot bypass refusal).
8. Machine-readable coverage schema reporting all unresolved gaps.
9. Compatibility with explicit reviewed ranking packets (Week 4 synthetic fixture).
10. Zero-action initial goal behavior without artificial probability inflation.
11. Fail-closed behavior on malformed or contradictory input.
12. Reference materialization producing payloads accepted by canonical PathRankingEngine.
"""

from __future__ import annotations

import json
from fractions import Fraction
from pathlib import Path
from typing import Any

import pytest

from src.engine.ranking import (
    ConsequenceRating,
    PathRankingEngine,
    RankingValidationError,
    decode_ranking_query,
    execute_ranking_roundtrip,
    validate_candidate_envelope,
    validate_candidate_envelopes,
)
from src.engine.ranking.resolver import (
    BasisClassification,
    RatingResolver,
    ReasonCode,
    ResolutionResult,
    ResolverDisposition,
    generate_bound_action_id,
    generate_rating_lookup_key_c,
    generate_rating_lookup_key_i,
    generate_rating_lookup_key_p,
    generate_work_unit_id,
)

FOOTHOLD_SID = "S-1-5-21-1000-2000-3000-1101"
TARGET_HOST_ID = "10000000-0000-4000-8000-000000000002"
OTHER_HOST_ID = "10000000-0000-4000-8000-000000000003"
GROUP_ADMINS_SID = "S-1-5-21-1000-2000-3000-2103"
DUMMY_EDGE_1 = "sha256:" + "1" * 64
DUMMY_EDGE_2 = "sha256:" + "2" * 64
DUMMY_EDGE_3 = "sha256:" + "3" * 64
SNAPSHOT_ID = "sha256:" + "a" * 64


def build_test_scope(**overrides: Any) -> dict[str, Any]:
    """Build standard query scope for testing."""
    base = {
        "query_id": "query-test-resolver-001",
        "scenario_id": "scenario-test-enterprise",
        "scenario_version": "1.0.0",
        "snapshot_id": SNAPSHOT_ID,
        "foothold_node_id": FOOTHOLD_SID,
        "work_boundary": "intra_forest",
        "horizon": "24h",
        "active_work_budget": 5,
        "evaluation_mode": "scenario",
        "target_goal": {
            "goal_id": "admin_host_c0",
            "description": "Administrative execution on Host C0",
            "target_asset_id": TARGET_HOST_ID,
            "success_event": "admin_execution_on_host_c0",
            "required_predicates": ["admin_control_host"],
        },
        "facts_ledger": {
            "predicate_layers": {
                "actor_controlled_alice": 3,
                "admin_channel_alice_host": 3,
                "authentication_accepted_alice_host": 3,
                "security_group_admins": 3,
                "membership_usable_alice_admins": 3,
                "effective_member_alice_admins": 3,
                "admin_control_host": 3,
            },
            "observed_facts": [
                {
                    "predicate": "actor_controlled_alice",
                    "layer": 3,
                    "truth_value": True,
                    "provenance_reference": "prov:fact:alice",
                },
                {
                    "predicate": "admin_channel_alice_host",
                    "layer": 3,
                    "truth_value": True,
                    "provenance_reference": "prov:fact:admin_channel",
                },
                {
                    "predicate": "authentication_accepted_alice_host",
                    "layer": 3,
                    "truth_value": True,
                    "provenance_reference": "prov:fact:auth",
                },
            ],
        },
    }
    base.update(overrides)
    return base


def test_deterministic_identities_and_versioning():
    """Deterministic bound action IDs, work unit IDs, and version prefixes."""
    aid1 = generate_bound_action_id(
        "obtain_admin_execution_on_host",
        FOOTHOLD_SID,
        TARGET_HOST_ID,
        {"method": "winrm", "auth_context": "kerberos"},
        version="1.0.0",
    )
    aid2 = generate_bound_action_id(
        "obtain_admin_execution_on_host",
        FOOTHOLD_SID,
        TARGET_HOST_ID,
        {"method": "winrm", "auth_context": "kerberos"},
        version="1.0.0",
    )
    assert aid1 == aid2
    assert aid1.startswith("act:1.0.0:obtain_admin_execution_on_host:")

    wuid1 = generate_work_unit_id(
        "obtain_admin_execution_on_host",
        FOOTHOLD_SID,
        TARGET_HOST_ID,
        context="winrm",
        boundary="intra_forest",
        ledger_version="1.0.0",
    )
    wuid2 = generate_work_unit_id(
        "obtain_admin_execution_on_host",
        FOOTHOLD_SID,
        TARGET_HOST_ID,
        context="winrm",
        boundary="intra_forest",
        ledger_version="1.0.0",
    )
    assert wuid1 == wuid2
    expected_wuid = (
        f"obtain_admin_execution_on_host:{FOOTHOLD_SID}:{TARGET_HOST_ID}:winrm:intra_forest:1.0.0"
    )
    assert wuid1 == expected_wuid


def test_negative_probes_context_collisions():
    """Negative probes proving distinct IDs when method, budget, horizon, or auth context differ."""
    # 1. Method difference
    aid_winrm = generate_bound_action_id(
        "obtain_admin_execution_on_host",
        FOOTHOLD_SID,
        TARGET_HOST_ID,
        {"method": "winrm"},
    )
    aid_wmi = generate_bound_action_id(
        "obtain_admin_execution_on_host",
        FOOTHOLD_SID,
        TARGET_HOST_ID,
        {"method": "wmi"},
    )
    assert aid_winrm != aid_wmi

    # 2. Work unit context difference
    wu_winrm = generate_work_unit_id(
        "obtain_admin_execution_on_host", FOOTHOLD_SID, TARGET_HOST_ID, context="winrm"
    )
    wu_wmi = generate_work_unit_id(
        "obtain_admin_execution_on_host", FOOTHOLD_SID, TARGET_HOST_ID, context="wmi"
    )
    assert wu_winrm != wu_wmi

    # 3. Budget difference in Likelihood lookup key
    key_p_b5 = generate_rating_lookup_key_p(
        "scenario-1",
        "1.0.0",
        SNAPSHOT_ID,
        FOOTHOLD_SID,
        ["wu:1"],
        "wu:1",
        "tech1",
        FOOTHOLD_SID,
        TARGET_HOST_ID,
        budget=5,
    )
    key_p_b10 = generate_rating_lookup_key_p(
        "scenario-1",
        "1.0.0",
        SNAPSHOT_ID,
        FOOTHOLD_SID,
        ["wu:1"],
        "wu:1",
        "tech1",
        FOOTHOLD_SID,
        TARGET_HOST_ID,
        budget=10,
    )
    assert key_p_b5.digest() != key_p_b10.digest()

    # 4. Horizon difference in Likelihood lookup key
    key_p_24h = generate_rating_lookup_key_p(
        "scenario-1",
        "1.0.0",
        SNAPSHOT_ID,
        FOOTHOLD_SID,
        ["wu:1"],
        "wu:1",
        "tech1",
        FOOTHOLD_SID,
        TARGET_HOST_ID,
        horizon="24h",
    )
    key_p_72h = generate_rating_lookup_key_p(
        "scenario-1",
        "1.0.0",
        SNAPSHOT_ID,
        FOOTHOLD_SID,
        ["wu:1"],
        "wu:1",
        "tech1",
        FOOTHOLD_SID,
        TARGET_HOST_ID,
        horizon="72h",
    )
    assert key_p_24h.digest() != key_p_72h.digest()

    # 5. Auth context difference in Effort lookup key
    key_c_auth1 = generate_rating_lookup_key_c(
        "wu:1", "tech1", FOOTHOLD_SID, TARGET_HOST_ID, auth_context="token_da"
    )
    key_c_auth2 = generate_rating_lookup_key_c(
        "wu:1", "tech1", FOOTHOLD_SID, TARGET_HOST_ID, auth_context="token_user"
    )
    assert key_c_auth1.digest() != key_c_auth2.digest()

    # 6. Target asset difference in Impact lookup key
    key_i_host_c0 = generate_rating_lookup_key_i(TARGET_HOST_ID, "admin_compromise")
    key_i_other = generate_rating_lookup_key_i(OTHER_HOST_ID, "admin_compromise")
    assert key_i_host_c0.digest() != key_i_other.digest()


def test_candidate_enumeration_order_invariance():
    """Candidate order in input sequence does not alter IDs, lookup keys, or candidate coverage."""
    scope = build_test_scope()

    step_a = {
        "provenance": ["synthetic://resolver-test/declared-edge"],
        "technique_id": "obtain_admin_execution_on_host",
        "actor": FOOTHOLD_SID,
        "target": TARGET_HOST_ID,
        "edge_id": DUMMY_EDGE_1,
        "requires": ["actor_controlled_alice", "admin_channel_alice_host"],
        "adds": ["admin_control_host"],
    }
    step_b = {
        "provenance": ["synthetic://resolver-test/declared-edge"],
        "technique_id": "obtain_admin_execution_on_host",
        "actor": FOOTHOLD_SID,
        "target": TARGET_HOST_ID,
        "edge_id": DUMMY_EDGE_2,
        "method": "secondary_channel",
        "requires": ["actor_controlled_alice", "admin_channel_alice_host"],
        "adds": ["admin_control_host"],
    }

    cand_1 = {"candidate_id": "Candidate_1", "transition_history": [step_a]}
    cand_2 = {"candidate_id": "Candidate_2", "transition_history": [step_b]}

    resolver = RatingResolver()
    res_12 = resolver.resolve([cand_1, cand_2], scope)
    res_21 = resolver.resolve([cand_2, cand_1], scope)

    c1_from_12 = res_12.coverage_report["candidates"]["Candidate_1"]
    c1_from_21 = res_21.coverage_report["candidates"]["Candidate_1"]

    assert c1_from_12["effort"]["total_units"] == c1_from_21["effort"]["total_units"]
    assert c1_from_12["likelihood"]["total_prefixes"] == c1_from_21["likelihood"]["total_prefixes"]

    # Bound action IDs match exactly
    env_c1_12 = next(e for e in res_12.candidate_envelopes if e["candidate_id"] == "Candidate_1")
    env_c1_21 = next(e for e in res_21.candidate_envelopes if e["candidate_id"] == "Candidate_1")
    assert env_c1_12["bound_action_ids"] == env_c1_21["bound_action_ids"]


def test_ordered_full_history_prefix_preservation_for_p():
    """Likelihood prefix key preserves full ordered active-work prefix; order matters."""
    prefix_ab = ("wu:alpha", "wu:beta")
    prefix_ba = ("wu:beta", "wu:alpha")

    key_ab = generate_rating_lookup_key_p(
        "scenario-1",
        "1.0.0",
        SNAPSHOT_ID,
        FOOTHOLD_SID,
        prefix_ab,
        "wu:beta",
        "tech_beta",
        FOOTHOLD_SID,
        TARGET_HOST_ID,
    )
    key_ba = generate_rating_lookup_key_p(
        "scenario-1",
        "1.0.0",
        SNAPSHOT_ID,
        FOOTHOLD_SID,
        prefix_ba,
        "wu:alpha",
        "tech_alpha",
        FOOTHOLD_SID,
        TARGET_HOST_ID,
    )

    assert key_ab.ordered_work_prefix == prefix_ab
    assert key_ba.ordered_work_prefix == prefix_ba
    assert key_ab.digest() != key_ba.digest()


def test_passive_steps_do_not_create_work_units_or_fake_rating_events():
    """Passive propagation (e.g. MemberOf closure) has empty work units and 0 cost delta."""
    scope = build_test_scope()

    passive_step = {
        "provenance": ["synthetic://resolver-test/declared-edge"],
        "technique_id": "propagate_group_entitlement",
        "actor": FOOTHOLD_SID,
        "target": GROUP_ADMINS_SID,
        "edge_id": DUMMY_EDGE_1,
        "is_passive_closure": True,
        "requires": ["actor_controlled_alice", "security_group_admins"],
        "adds": ["effective_member_alice_admins"],
    }
    active_step = {
        "provenance": ["synthetic://resolver-test/declared-edge"],
        "technique_id": "obtain_admin_execution_on_host",
        "actor": FOOTHOLD_SID,
        "target": TARGET_HOST_ID,
        "edge_id": DUMMY_EDGE_2,
        "is_passive_closure": False,
        "requires": [
            "actor_controlled_alice",
            "effective_member_alice_admins",
            "admin_channel_alice_host",
        ],
        "adds": ["admin_control_host"],
    }

    cand_direct = {
        "candidate_id": "Cand_Direct",
        "transition_history": [active_step],
    }
    cand_member_direct = {
        "candidate_id": "Cand_Member_Direct",
        "transition_history": [passive_step, active_step],
    }

    resolver = RatingResolver()
    result = resolver.resolve([cand_direct, cand_member_direct], scope)

    # Passive step has empty referenced_work_unit_ids
    act_passive = next(
        a
        for a in result.ranking_query["bound_actions"]
        if a["technique_name"] == "propagate_group_entitlement"
    )
    assert act_passive["is_passive_closure"] is True
    assert act_passive["referenced_work_unit_ids"] == []

    # Envelope for Cand_Member_Direct has work packet [(), (wu:...)]
    env_m = next(e for e in result.candidate_envelopes if e["candidate_id"] == "Cand_Member_Direct")
    assert env_m["work_packets"][0] == []
    assert len(env_m["work_packets"][1]) == 1

    # Active work program is identical between Cand_Direct and Cand_Member_Direct
    rep_direct = result.coverage_report["candidates"]["Cand_Direct"]
    rep_m = result.coverage_report["candidates"]["Cand_Member_Direct"]
    assert rep_direct["effort"]["total_units"] == rep_m["effort"]["total_units"]
    assert rep_direct["likelihood"]["total_prefixes"] == rep_m["likelihood"]["total_prefixes"]


def test_shared_persistent_preparation_deduplication():
    """Shared persistent preparation is deduplicated across steps; friction counted once."""
    scope = build_test_scope()

    shared_prep_uid = f"w-auth-context:{FOOTHOLD_SID}:{TARGET_HOST_ID}:intra_forest:1.0.0"
    shared_preps = {
        f"{FOOTHOLD_SID}:{TARGET_HOST_ID}": {
            "technique": "auth_context",
            "context": "shared_channel",
            "work_unit_id": shared_prep_uid,
            "computed_cost": 1,
            "effort_cost": 1,
            "rating_status": "rated",
            "rubric_scores": {"t1": 1, "t2": 2, "formula": "base", "computed_cost": 1},
        }
    }

    step1 = {
        "provenance": ["synthetic://resolver-test/declared-edge"],
        "technique_id": "obtain_admin_execution_on_host",
        "actor": FOOTHOLD_SID,
        "target": TARGET_HOST_ID,
        "edge_id": DUMMY_EDGE_1,
        "requires": ["actor_controlled_alice", "admin_channel_alice_host"],
        "adds": ["admin_control_host"],
    }
    step2 = {
        "provenance": ["synthetic://resolver-test/declared-edge"],
        "technique_id": "obtain_admin_execution_on_host",
        "actor": FOOTHOLD_SID,
        "target": TARGET_HOST_ID,
        "edge_id": DUMMY_EDGE_2,
        "method": "alternate_exec",
        "requires": ["actor_controlled_alice", "admin_channel_alice_host"],
        "adds": ["admin_control_host"],
    }

    cand = {"candidate_id": "Cand_Shared", "transition_history": [step1, step2]}

    resolver = RatingResolver()
    result = resolver.resolve([cand], scope, shared_preparation_units=shared_preps)

    # In work_units_ledger, shared_prep_uid appears once
    assert shared_prep_uid in result.ranking_query["work_units_ledger"]
    assert result.ranking_query["work_units_ledger"][shared_prep_uid]["computed_cost"] == 1

    # In candidate envelope, both actions reference shared_prep_uid
    act1 = result.ranking_query["bound_actions"][0]
    act2 = result.ranking_query["bound_actions"][1]
    assert shared_prep_uid in act1["referenced_work_unit_ids"]
    assert shared_prep_uid in act2["referenced_work_unit_ids"]


def test_dispositions_and_refusal_integrity():
    """Provider refusal cannot be bypassed by subsequent provider fallback."""
    scope = build_test_scope()

    class RefusingLikelihoodProvider:
        name = "empirical_estimator"
        provider_version = "1.0.0"

        def resolve_likelihood(self, key, prefix, outcome_unit, scope_map):
            return ResolutionResult(
                disposition=ResolverDisposition.REFUSED,
                reason_code=ReasonCode.PREREQUISITE_GATE_REFUSAL,
                reason_detail="Holdout boundary violated; estimation refused for this prefix",
                provider_name=self.name,
            )

    class ScenarioFallbackLikelihoodProvider:
        name = "scenario_fallback"
        provider_version = "1.0.0"

        def resolve_likelihood(self, key, prefix, outcome_unit, scope_map):
            # This should NEVER be reached because refusal is authoritative!
            return ResolutionResult(
                disposition=ResolverDisposition.RATED,
                value=(Fraction(1, 2), Fraction(3, 4)),
                reason_code=ReasonCode.REVIEWED_PACKET_MATCH,
                reason_detail="Bypassed refusal (illegal!)",
                provider_name=self.name,
            )

    step = {
        "provenance": ["synthetic://resolver-test/declared-edge"],
        "technique_id": "obtain_admin_execution_on_host",
        "actor": FOOTHOLD_SID,
        "target": TARGET_HOST_ID,
        "edge_id": DUMMY_EDGE_1,
        "requires": ["actor_controlled_alice", "admin_channel_alice_host"],
        "adds": ["admin_control_host"],
    }
    cand = {"candidate_id": "Cand_Refused", "transition_history": [step]}

    resolver = RatingResolver(
        likelihood_providers=[RefusingLikelihoodProvider(), ScenarioFallbackLikelihoodProvider()]
    )
    result = resolver.resolve([cand], scope)

    # Check P coverage for the candidate prefix
    cand_p = result.coverage_report["candidates"]["Cand_Refused"]["likelihood"]
    assert cand_p["all_rated"] is False
    assert len(cand_p["gaps"]) == 1

    gap = cand_p["gaps"][0]
    assert gap["disposition"] == ResolverDisposition.REFUSED
    assert gap["reason_code"] == ReasonCode.PREREQUISITE_GATE_REFUSAL

    # Trace verifies that scenario_fallback was NEVER invoked!
    trace_provs = [t["provider"] for t in gap["provider_trace"]]
    assert "empirical_estimator" in trace_provs
    assert "scenario_fallback" not in trace_provs


def test_machine_readable_coverage_schema_reports_all_gaps():
    """Coverage report exhaustively reports ALL unresolved gaps across all prefix lengths."""
    scope = build_test_scope()

    # 3-step candidate with missing likelihood basis
    steps = [
        {
            "provenance": ["synthetic://resolver-test/declared-edge"],
            "technique_id": "obtain_admin_execution_on_host",
            "actor": FOOTHOLD_SID,
            "target": TARGET_HOST_ID,
            "edge_id": DUMMY_EDGE_1,
            "method": "step1",
            "requires": ["actor_controlled_alice", "admin_channel_alice_host"],
            "adds": ["admin_control_host"],
        },
        {
            "provenance": ["synthetic://resolver-test/declared-edge"],
            "technique_id": "obtain_admin_execution_on_host",
            "actor": FOOTHOLD_SID,
            "target": TARGET_HOST_ID,
            "edge_id": DUMMY_EDGE_2,
            "method": "step2",
            "requires": ["actor_controlled_alice", "admin_channel_alice_host"],
            "adds": ["admin_control_host"],
        },
        {
            "provenance": ["synthetic://resolver-test/declared-edge"],
            "technique_id": "obtain_admin_execution_on_host",
            "actor": FOOTHOLD_SID,
            "target": TARGET_HOST_ID,
            "edge_id": DUMMY_EDGE_3,
            "method": "step3",
            "requires": ["actor_controlled_alice", "admin_channel_alice_host"],
            "adds": ["admin_control_host"],
        },
    ]
    cand = {"candidate_id": "Cand_ThreeSteps", "transition_history": steps}

    resolver = RatingResolver()
    result = resolver.resolve([cand], scope)

    cov = result.coverage_report
    cand_p = cov["candidates"]["Cand_ThreeSteps"]["likelihood"]
    assert cand_p["total_prefixes"] == 3
    assert cand_p["unrated_prefixes"] == 3
    # ALL 3 prefix lengths are reported in gaps!
    assert len(cand_p["gaps"]) == 3
    gap_prefix_lens = [len(g["prefix"]) for g in cand_p["gaps"]]
    assert gap_prefix_lens == [1, 2, 3]


def test_compatibility_with_explicit_reviewed_ranking_packet():
    """Compatible with Week 4 synthetic reviewed fixture without mutating values."""
    fixture_path = Path(__file__).parents[1] / "docs/research/ratings/week4/synthetic-a2-e.json"
    fixture_data = json.loads(fixture_path.read_text(encoding="utf-8"))
    query_fixture = fixture_data["query"]

    # Candidate matching direct admin route in A2 fixture
    step = {
        "provenance": ["synthetic://resolver-test/declared-edge"],
        "technique_id": "obtain_admin_execution_on_host",
        "actor": FOOTHOLD_SID,
        "target": TARGET_HOST_ID,
        "edge_id": "sha256:8f30ade289c16f75c747c8651362d8483c3ac7793c5a3f47b769fcbf110fca67",
        "referenced_work_unit_ids": ["w-auth-context", "w-direct-admin"],
        "requires": [
            "actor_controlled_alice",
            "admin_channel_alice_host",
            "authentication_accepted_alice_host",
        ],
        "adds": ["admin_control_host"],
    }
    cand = {"candidate_id": "cand_direct", "transition_history": [step]}

    resolver = RatingResolver(explicit_packet=query_fixture)
    result = resolver.resolve(
        [cand], {**query_fixture["query_metadata"], "facts_ledger": query_fixture["facts_ledger"]}
    )

    # Check work units resolved from packet
    ledger = result.ranking_query["work_units_ledger"]
    assert ledger["w-auth-context"]["computed_cost"] == 1
    assert ledger["w-direct-admin"]["computed_cost"] == 4

    # Check bounds table resolved from packet
    bounds_map = {tuple(r["prefix"]): r for r in result.ranking_query["conditional_bounds_table"]}
    assert ("w-auth-context",) in bounds_map
    assert bounds_map[("w-auth-context",)]["lower"] == "4/5"
    assert bounds_map[("w-auth-context",)]["upper"] == "9/10"

    # Check target impact resolved from packet
    impacts = result.ranking_query["target_impact_assessments"]
    assert impacts[TARGET_HOST_ID]["rating_status"] == "rated"
    assert impacts[TARGET_HOST_ID]["consequence_rating"] == "High"

    # Candidate coverage is fully rated
    cand_cov = result.coverage_report["candidates"]["cand_direct"]
    assert cand_cov["effort"]["all_rated"] is True
    assert cand_cov["likelihood"]["all_rated"] is True
    assert cand_cov["impact"]["disposition"] == ResolverDisposition.RATED


def test_zero_action_initial_goal_behavior():
    """Zero-action candidate produces clean zero-work envelope without artificial likelihood."""
    scope = build_test_scope(target_asset_id=FOOTHOLD_SID)
    scope["target_goal"]["target_asset_id"] = FOOTHOLD_SID

    zero_cand = {"candidate_id": "Cand_Zero", "transition_history": []}

    resolver = RatingResolver()
    result = resolver.resolve([zero_cand], scope)

    env = result.candidate_envelopes[0]
    assert env["candidate_id"] == "Cand_Zero"
    assert env["bound_action_ids"] == []
    assert env["work_packets"] == [()]
    assert len(env["structural_routes"]) == 1
    assert env["structural_routes"][0]["node_ids"] == [FOOTHOLD_SID]
    assert env["structural_routes"][0]["edge_ids"] == []

    # Validated by canonical validate_candidate_envelope
    decoded_query = decode_ranking_query(result.ranking_query)
    validated_env = validate_candidate_envelope(env, decoded_query)
    assert validated_env["candidate_id"] == "Cand_Zero"


def test_fail_closed_malformed_input():
    """Malformed or invalid canonical nodes/edges fail-closed."""
    scope = build_test_scope()

    # Non-canonical node ID
    invalid_step = {
        "requires": ["actor_controlled_alice"],
        "adds": ["admin_control_host"],
        "technique_id": "obtain_admin_execution_on_host",
        "actor": "AliceNotCanonical",
        "target": TARGET_HOST_ID,
    }
    cand = {"candidate_id": "Cand_Bad", "transition_history": [invalid_step]}

    resolver = RatingResolver()
    with pytest.raises(RankingValidationError, match="canonical"):
        resolver.resolve([cand], scope)


def test_reference_materialization_with_canonical_evaluator_unrated():
    """Materialization with missing numeric basis produces payloads accepted
    by canonical validator.
    """
    scope = build_test_scope()

    step = {
        "provenance": ["synthetic://resolver-test/declared-edge"],
        "technique_id": "obtain_admin_execution_on_host",
        "actor": FOOTHOLD_SID,
        "target": TARGET_HOST_ID,
        "edge_id": DUMMY_EDGE_1,
        "requires": ["actor_controlled_alice", "admin_channel_alice_host"],
        "adds": ["admin_control_host"],
    }
    cand = {"candidate_id": "Cand_Unrated", "transition_history": [step]}

    resolver = RatingResolver()  # No providers -> fail closed unrated
    res = resolver.resolve([cand], scope)

    # 1. Wire query decodes cleanly through canonical validator
    decoded = decode_ranking_query(res.ranking_query)
    assert decoded["query_metadata"]["query_id"] == scope["query_id"]
    assert decoded["target_impact_assessments"][TARGET_HOST_ID]["rating_status"] == "unrated"

    # 2. Candidate envelope validates cleanly
    validated_envelopes = validate_candidate_envelopes(res.candidate_envelopes, decoded)
    assert len(validated_envelopes) == 1

    # 3. Canonical PathRankingEngine roundtrip evaluates without error
    roundtrip = execute_ranking_roundtrip(res.ranking_query, res.candidate_envelopes)
    assert roundtrip is not None
    result_payload = roundtrip["result_payload"]
    # Since candidate has unrated likelihood and impact, it is partitioned into diagnostics
    assert "Cand_Unrated" in result_payload["diagnostics"]
    diag = result_payload["diagnostics"]["Cand_Unrated"]
    assert "likelihood_unrated" in diag["reasons"]
    assert "impact_unrated" in diag["reasons"]


def test_reference_materialization_with_canonical_evaluator_rated():
    """Materialization with rated providers produces payloads ranked on Pareto and Min-effort."""
    scope = build_test_scope()

    class SyntheticEffortProvider:
        name = "test_c_provider"
        provider_version = "1.0.0"

        def resolve_effort(self, key, work_unit_rec, scope_map):
            return ResolutionResult(
                disposition=ResolverDisposition.RATED,
                value=2,
                reason_code=ReasonCode.REVIEWED_PACKET_MATCH,
                provider_name=self.name,
                basis_category=BasisClassification.SYNTHETIC_TEST_ONLY,
                rubric_scores={"t1": 1, "t2": 3, "formula": "base", "computed_cost": 2},
            )

    class SyntheticLikelihoodProvider:
        name = "test_p_provider"
        provider_version = "1.0.0"

        def resolve_likelihood(self, key, prefix, outcome_unit, scope_map):
            return ResolutionResult(
                disposition=ResolverDisposition.RATED,
                value=(Fraction(3, 5), Fraction(4, 5)),
                reason_code=ReasonCode.REVIEWED_PACKET_MATCH,
                provider_name=self.name,
                basis_category=BasisClassification.SYNTHETIC_TEST_ONLY,
            )

    class SyntheticImpactProvider:
        name = "test_i_provider"
        provider_version = "1.0.0"

        def resolve_impact(self, key, target_asset_id, success_event, scope_map):
            return ResolutionResult(
                disposition=ResolverDisposition.RATED,
                value=ConsequenceRating.HIGH.value,
                reason_code=ReasonCode.REVIEWED_PACKET_MATCH,
                provider_name=self.name,
                basis_category=BasisClassification.SYNTHETIC_TEST_ONLY,
            )

    step = {
        "provenance": ["synthetic://resolver-test/declared-edge"],
        "technique_id": "obtain_admin_execution_on_host",
        "actor": FOOTHOLD_SID,
        "target": TARGET_HOST_ID,
        "edge_id": DUMMY_EDGE_1,
        "requires": ["actor_controlled_alice", "admin_channel_alice_host"],
        "adds": ["admin_control_host"],
    }
    cand = {"candidate_id": "Cand_Rated", "transition_history": [step]}

    resolver = RatingResolver(
        effort_providers=[SyntheticEffortProvider()],
        likelihood_providers=[SyntheticLikelihoodProvider()],
        impact_providers=[SyntheticImpactProvider()],
    )
    res = resolver.resolve([cand], scope)

    # Roundtrip execution through canonical PathRankingEngine
    engine = PathRankingEngine(version="1.0.0")
    ranking_res = engine.evaluate(res.ranking_query, res.candidate_envelopes)
    result_payload = ranking_res["result_payload"]

    assert "Cand_Rated" in result_payload["eligible_candidates"]
    assert result_payload["pareto_frontier"] == ["Cand_Rated"]
    assert result_payload["min_effort_to_da_baseline"]["best_candidate_id"] == "Cand_Rated"
    assert result_payload["min_effort_to_da_baseline"]["minimum_effort_value"] == 2


def test_impact_provider_refusal_and_conflicting_wire_validity():
    """Impact provider returning REFUSED or CONFLICTING normalizes wire status to unrated."""
    scope = build_test_scope()

    class RefusingImpactProvider:
        name = "strict_impact_policy"
        provider_version = "1.0.0"

        def resolve_impact(self, key, target_asset_id, success_event, scope_map):
            return ResolutionResult(
                disposition=ResolverDisposition.REFUSED,
                reason_code=ReasonCode.PREREQUISITE_GATE_REFUSAL,
                reason_detail="Target asset policy forbids unclassified impact",
                provider_name=self.name,
            )

    step = {
        "provenance": ["synthetic://resolver-test/declared-edge"],
        "technique_id": "obtain_admin_execution_on_host",
        "actor": FOOTHOLD_SID,
        "target": TARGET_HOST_ID,
        "edge_id": DUMMY_EDGE_1,
        "requires": ["actor_controlled_alice", "admin_channel_alice_host"],
        "adds": ["admin_control_host"],
    }
    cand = {"candidate_id": "Cand_Impact_Refused", "transition_history": [step]}

    resolver = RatingResolver(impact_providers=[RefusingImpactProvider()])
    res = resolver.resolve([cand], scope)

    # Wire query target_impact_assessments must have rating_status == "unrated"
    assert (
        res.ranking_query["target_impact_assessments"][TARGET_HOST_ID]["rating_status"] == "unrated"
    )

    # Must decode cleanly through canonical schema validator without ValueError
    decoded = decode_ranking_query(res.ranking_query)
    assert decoded["target_impact_assessments"][TARGET_HOST_ID]["rating_status"] == "unrated"

    # Coverage report must preserve rich disposition and reason code
    cand_cov = res.coverage_report["candidates"]["Cand_Impact_Refused"]
    assert cand_cov["impact"]["disposition"] == ResolverDisposition.REFUSED
    assert cand_cov["impact"]["reason_code"] == ReasonCode.PREREQUISITE_GATE_REFUSAL
    assert cand_cov["impact"]["selected_provider"] == "strict_impact_policy"


def test_step_context_propagated_to_lookup_keys():
    """Context from transitions and scope reaches lookup keys for C, P, and I."""
    captured_keys: dict[str, Any] = {}

    class ContextCapturingEffortProvider:
        name = "capturing_c"
        provider_version = "1.0.0"

        def resolve_effort(self, key, work_unit_rec, scope_map):
            captured_keys["effort"] = key
            return ResolutionResult(
                disposition=ResolverDisposition.RATED,
                value=3,
                rubric_scores={"t1": 2, "t2": 3, "computed_cost": 3},
                reason_code=ReasonCode.REVIEWED_PACKET_MATCH,
                provider_name=self.name,
            )

    class ContextCapturingLikelihoodProvider:
        name = "capturing_p"
        provider_version = "1.0.0"

        def resolve_likelihood(self, key, prefix, outcome_unit, scope_map):
            captured_keys["likelihood"] = key
            return ResolutionResult(
                disposition=ResolverDisposition.RATED,
                value=(Fraction(1, 2), Fraction(2, 3)),
                reason_code=ReasonCode.REVIEWED_PACKET_MATCH,
                provider_name=self.name,
            )

    class ContextCapturingImpactProvider:
        name = "capturing_i"
        provider_version = "1.0.0"

        def resolve_impact(self, key, target_asset_id, success_event, scope_map):
            captured_keys["impact"] = key
            return ResolutionResult(
                disposition=ResolverDisposition.RATED,
                value=ConsequenceRating.CRITICAL.value,
                reason_code=ReasonCode.REVIEWED_PACKET_MATCH,
                provider_name=self.name,
            )

    scope = build_test_scope(policy_id="corp_policy_strict_v2")

    step = {
        "provenance": ["synthetic://resolver-test/declared-edge"],
        "technique_id": "obtain_admin_execution_on_host",
        "actor": FOOTHOLD_SID,
        "source": FOOTHOLD_SID,
        "target": TARGET_HOST_ID,
        "edge_id": DUMMY_EDGE_1,
        "method": "kerberos_ticket_grant",
        "auth_context": "mutual_auth_pki",
        "resource_context": "rpc_named_pipe",
        "policy_id": "corp_policy_strict_v2",
        "requires": ["actor_controlled_alice", "admin_channel_alice_host"],
        "adds": ["admin_control_host"],
    }
    cand = {"candidate_id": "Cand_Ctx", "transition_history": [step]}

    resolver = RatingResolver(
        effort_providers=[ContextCapturingEffortProvider()],
        likelihood_providers=[ContextCapturingLikelihoodProvider()],
        impact_providers=[ContextCapturingImpactProvider()],
    )
    resolver.resolve([cand], scope)

    c_key = captured_keys["effort"]
    assert c_key.method == "kerberos_ticket_grant"
    assert c_key.auth_context == "mutual_auth_pki"
    assert c_key.resource_context == "rpc_named_pipe"
    assert c_key.policy_id == "corp_policy_strict_v2"

    p_key = captured_keys["likelihood"]
    assert p_key.method == "kerberos_ticket_grant"
    assert p_key.auth_context == "mutual_auth_pki"
    assert p_key.resource_context == "rpc_named_pipe"
    assert p_key.policy_id == "corp_policy_strict_v2"

    i_key = captured_keys["impact"]
    assert i_key.policy_id == "corp_policy_strict_v2"
    assert i_key.target_asset_id == TARGET_HOST_ID


def test_coverage_report_selected_provider_for_unrated():
    """Default fail-closed resolver records selected_provider as fail_closed_unrated_provider."""
    scope = build_test_scope()
    step = {
        "provenance": ["synthetic://resolver-test/declared-edge"],
        "technique_id": "obtain_admin_execution_on_host",
        "actor": FOOTHOLD_SID,
        "target": TARGET_HOST_ID,
        "edge_id": DUMMY_EDGE_1,
        "requires": ["actor_controlled_alice", "admin_channel_alice_host"],
        "adds": ["admin_control_host"],
    }
    cand = {"candidate_id": "Cand_Unrated_Prov", "transition_history": [step]}

    resolver = RatingResolver()
    res = resolver.resolve([cand], scope)

    cand_cov = res.coverage_report["candidates"]["Cand_Unrated_Prov"]
    c_unit_keys = list(cand_cov["effort"]["units"].keys())
    assert (
        cand_cov["effort"]["units"][c_unit_keys[0]]["selected_provider"]
        == "fail_closed_unrated_provider"
    )
    assert (
        cand_cov["likelihood"]["prefixes"][0]["selected_provider"] == "fail_closed_unrated_provider"
    )
    assert cand_cov["impact"]["selected_provider"] == "fail_closed_unrated_provider"
