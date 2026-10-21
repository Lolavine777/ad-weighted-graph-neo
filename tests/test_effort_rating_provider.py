"""Independent test suite for Reviewed Work-Unit Classes and Effort Rating Provider.

Specification v1.0.0, Issue #247 (parent #245).

Verifies:
1. Deterministic class resolution and exact integer rubric formulas (T1, T2 in {1, 2, 3},
   formula == "base", C = T1 + T2 - 2 in {0..4}).
2. Coverage of all frozen #243 active work units (AS-REP path).
3. Coverage of Kerberoasting active work units.
4. Coverage of all 5 active RBCD work units across recipes.
5. Shared preparation deduplication and multi-target context separation.
6. Passive steps (propagate_group_entitlement) produce zero friction and no artificial cost.
7. Candidate enumeration order invariance.
8. Negative probes:
   - Unsupported technique -> UNSUPPORTED (UNSUPPORTED_TECHNIQUE)
   - Boundary mismatch -> REFUSED (OUT_OF_SCOPE)
   - Conflicting registry definitions -> RankingValidationError / CONFLICTING
   - Unresolved overlap -> UNRATED (EXPLICIT_UNRATED_DISPOSITION)
9. Absolute refusal of unit weights (W=1.0) and maut_v1 fallback.
10. Independent Min-Effort multi-path oracle (Candidate 1 C=5 vs Candidate 2 C=2)
    verified through canonical PathRankingEngine.
11. Week 3 SEAMLESS parameter parity and regression protection.
"""

from __future__ import annotations

import json
import os
from dataclasses import replace
from fractions import Fraction
from pathlib import Path
from typing import Any

import pytest

from src.engine.ranking import (
    PathRankingEngine,
    RankingValidationError,
    decode_ranking_query,
    validate_candidate_envelope,
)
from src.engine.ranking.effort_registry import (
    ClassApplicability,
    ReviewedWorkUnitClassEffortProvider,
    WorkUnitClass,
    WorkUnitClassRegistry,
    build_default_work_unit_classes,
    get_default_work_unit_registry,
)
from src.engine.ranking.resolver import (
    BasisClassification,
    RatingResolver,
    ReasonCode,
    ResolutionResult,
    ResolverDisposition,
    WorkUnitClassification,
    generate_rating_lookup_key_c,
)

FOOTHOLD_SID = "S-1-5-21-1000-2000-3000-1101"
TARGET_HOST_ID = "10000000-0000-4000-8000-000000000002"
OTHER_HOST_ID = "10000000-0000-4000-8000-000000000003"
GROUP_ADMINS_SID = "S-1-5-21-1000-2000-3000-2103"
SNAPSHOT_ID = "sha256:" + "a" * 64


def accepted_test_provider():
    """Simulate an accepted disposition only in isolated provider tests."""
    classes = [
        replace(
            c,
            review_status="accepted",
            basis_category=BasisClassification.SYNTHETIC_TEST_ONLY.value,
            review_reference="tests/test_effort_rating_provider.py#accepted_test_provider",
        )
        for c in build_default_work_unit_classes()
    ]
    return ReviewedWorkUnitClassEffortProvider(WorkUnitClassRegistry(classes))


def make_scope(**overrides: Any) -> dict[str, Any]:
    """Helper to build canonical query scope for resolver tests."""
    base = {
        "query_id": "query-effort-test-001",
        "scenario_id": "scenario-test-enterprise",
        "scenario_version": "1.0.0",
        "snapshot_id": SNAPSHOT_ID,
        "foothold_node_id": FOOTHOLD_SID,
        "work_boundary": "intra_forest",
        "horizon": "24h",
        "active_work_budget": 10,
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
                    "provenance_reference": "prov:alice",
                },
                {
                    "predicate": "admin_channel_alice_host",
                    "layer": 3,
                    "truth_value": True,
                    "provenance_reference": "prov:channel",
                },
                {
                    "predicate": "authentication_accepted_alice_host",
                    "layer": 3,
                    "truth_value": True,
                    "provenance_reference": "prov:auth",
                },
                {
                    "predicate": "security_group_admins",
                    "layer": 3,
                    "truth_value": True,
                    "provenance_reference": "prov:sec_group",
                },
                {
                    "predicate": "membership_usable_alice_admins",
                    "layer": 3,
                    "truth_value": True,
                    "provenance_reference": "prov:member_usable",
                },
            ],
            "false_facts": [],
            "assumed_facts": [],
            "unknown_facts": [],
        },
    }
    base.update(overrides)
    return base


# ===========================================================================
# 1. Deterministic Class Resolution and Exact Integer Rubric Checks
# ===========================================================================


def test_default_registry_contains_expected_classes():
    """Verify default registry initialization and class integrity."""
    registry = get_default_work_unit_registry()
    classes = registry.list_classes()
    assert len(classes) == 23

    for cls in classes:
        assert isinstance(cls.class_id, str) and cls.class_id.startswith("class_")
        assert cls.formula == "base"
        if cls.disposition == ResolverDisposition.RATED:
            assert cls.t1 in (1, 2, 3)
            assert cls.t2 in (1, 2, 3)
            cost = cls.computed_cost
            assert type(cost) is int
            assert cost == cls.t1 + cls.t2 - 2
            assert 0 <= cost <= 4
            rubric = cls.rubric_scores
            assert rubric is not None
            assert rubric["t1"] == cls.t1
            assert rubric["t2"] == cls.t2
            assert rubric["formula"] == "base"
            assert rubric["computed_cost"] == cost
            assert rubric["effort_cost"] == cost


@pytest.mark.parametrize("field,value", [("t1", 1.0), ("t1", True), ("t2", 2.0), ("t2", False)])
def test_registry_rejects_non_exact_integer_rubrics(field, value):
    cls = build_default_work_unit_classes()[0]
    with pytest.raises(RankingValidationError, match=field):
        replace(cls, **{field: value})


@pytest.mark.parametrize("t1", [1, 2, 3])
@pytest.mark.parametrize("t2", [1, 2, 3])
def test_registry_accepts_exact_integer_rubrics(t1, t2):
    cls = replace(build_default_work_unit_classes()[0], t1=t1, t2=t2)
    assert type(cls.computed_cost) is int
    assert cls.computed_cost == t1 + t2 - 2


def test_provider_resolves_all_rated_classes_deterministically():
    """Provider produces identical ResolutionResult for repeat calls."""
    provider = accepted_test_provider()
    scope = make_scope()

    for cls in provider.registry.list_classes():
        if cls.disposition != ResolverDisposition.RATED:
            continue
        tech = cls.applicability.techniques[0]
        method = cls.applicability.methods[0] if cls.applicability.methods != ("*",) else "default"
        boundary = (
            cls.applicability.boundaries[0]
            if cls.applicability.boundaries != ("*",)
            else "intra_forest"
        )
        key = generate_rating_lookup_key_c(
            work_unit_id=f"{tech}:actor:target:ctx:1.0.0",
            technique=tech,
            actor_id=FOOTHOLD_SID,
            target_id=TARGET_HOST_ID,
            method=method,
            boundary=boundary,
        )
        record = {
            "work_unit_id": key.work_unit_id,
            "work_unit_class_id": cls.class_id,
            "overlap_state": "independent",
        }
        r1 = provider.resolve_effort(key, record, scope)
        r2 = provider.resolve_effort(key, record, scope)
        assert r1 == r2
        assert r1.disposition == ResolverDisposition.RATED
        assert type(r1.value) is int
        assert r1.value == cls.computed_cost
        assert r1.rubric_scores == cls.rubric_scores
        assert r1.reason_code == ReasonCode.REVIEWED_PACKET_MATCH


# ===========================================================================
# 2. Frozen #243 Active Work Units (AS-REP Path)
# ===========================================================================


# ===========================================================================
# 3. Kerberoasting Work Units
# ===========================================================================


def test_kerberoasting_work_units_coverage():
    """Verify Kerberoasting request and offline ticket secret recovery."""
    provider = accepted_test_provider()
    scope = make_scope()

    # kerberoast_request -> class_kerberoast_request, T1=1, T2=1, C=0
    k1 = generate_rating_lookup_key_c(
        work_unit_id="kerberoast_request:U:V:default:intra_forest:1.0.0",
        technique="kerberoast_request",
        actor_id=FOOTHOLD_SID,
        target_id=TARGET_HOST_ID,
    )
    r1 = provider.resolve_effort(k1, {"overlap_state": "independent"}, scope)
    assert r1.disposition == ResolverDisposition.RATED
    assert r1.value == 0
    assert r1.rubric_scores["computed_cost"] == 0

    # recover_ticket_secret -> class_kerberoast_offline_crack, T1=2, T2=2, C=2
    k2 = generate_rating_lookup_key_c(
        work_unit_id="recover_ticket_secret:U:V:default:intra_forest:1.0.0",
        technique="recover_ticket_secret",
        actor_id=FOOTHOLD_SID,
        target_id=TARGET_HOST_ID,
    )
    r2 = provider.resolve_effort(k2, {"overlap_state": "independent"}, scope)
    assert r2.disposition == ResolverDisposition.RATED
    assert r2.value == 2
    assert r2.rubric_scores["computed_cost"] == 2
    assert r2.rubric_scores["t1"] == 2
    assert r2.rubric_scores["t2"] == 2


# ===========================================================================
# 4. Five Active RBCD Work Units
# ===========================================================================


def test_rbcd_all_five_classes_coverage():
    """Verify all 5 RBCD work units across all 3 ordering recipes."""
    provider = accepted_test_provider()
    scope = make_scope(work_boundary="scoped-rbcd-delegation")

    rbcd_tests = [
        ("rbcd_acquire_secret", 1, 2, 1),
        ("rbcd_prepare_service", 1, 1, 0),
        ("rbcd_configure_descriptor", 2, 2, 2),
        ("rbcd_delegate_service", 2, 2, 2),
        ("rbcd_service_admin", 1, 2, 1),
    ]

    for tech, exp_t1, exp_t2, exp_cost in rbcd_tests:
        key = generate_rating_lookup_key_c(
            work_unit_id=f"{tech}:controller:target:ctx:1.0.0",
            technique=tech,
            actor_id=FOOTHOLD_SID,
            target_id=TARGET_HOST_ID,
            boundary="scoped-rbcd-delegation",
        )
        res = provider.resolve_effort(key, {"overlap_state": "independent"}, scope)
        assert res.disposition == ResolverDisposition.RATED, f"Failed for {tech}"
        assert res.value == exp_cost, f"Wrong cost for {tech}"
        assert res.rubric_scores["t1"] == exp_t1
        assert res.rubric_scores["t2"] == exp_t2
        assert res.rubric_scores["computed_cost"] == exp_cost


# ===========================================================================
# 5. Shared Preparation Deduplication and Multi-Target Separation
# ===========================================================================


def test_shared_preparation_deduplication_via_resolver():
    """Shared preparation (w-auth-context) is counted once across steps."""
    provider = accepted_test_provider()
    resolver = RatingResolver(effort_providers=[provider])
    scope = make_scope()

    shared_prep = {
        "w-auth-context": {
            "work_unit_id": "w-auth-context",
            "alias": "w-auth-context",
            "rating_status": "unrated",  # To be resolved by provider
            "overlap_state": "independent",
            "technique": "auth_context",
            "classification": WorkUnitClassification.SHARED_PREPARATION.value,
            "actor_id": FOOTHOLD_SID,
            "target_id": TARGET_HOST_ID,
        }
    }

    # Two transitions both referencing w-auth-context
    cand = {
        "candidate_id": "cand_shared_prep",
        "transition_history": [
            {
                "technique": "obtain_admin_execution_on_host",
                "actor": FOOTHOLD_SID,
                "source": FOOTHOLD_SID,
                "target": TARGET_HOST_ID,
                "method": "inherited",
                "alias": "w-inherited-admin",
                "shared_prep_key": "w-auth-context",
                "requires": ["actor_controlled_alice"],
                "adds": ["admin_channel_alice_host"],
            },
            {
                "technique": "obtain_admin_execution_on_host",
                "actor": FOOTHOLD_SID,
                "source": FOOTHOLD_SID,
                "target": TARGET_HOST_ID,
                "method": "direct",
                "alias": "w-direct-admin",
                "shared_prep_key": "w-auth-context",
                "requires": ["admin_channel_alice_host"],
                "adds": ["admin_control_host"],
            },
        ],
    }

    output = resolver.resolve([cand], scope, shared_preparation_units=shared_prep)
    ledger = output.ranking_query["work_units_ledger"]

    # w-auth-context is present once, cost = 1
    assert "w-auth-context" in ledger
    assert ledger["w-auth-context"]["rating_status"] == "rated"
    assert ledger["w-auth-context"]["computed_cost"] == 1

    # Distinct work: shared preparation 1 + inherited admin 1 + direct admin 4 = 6.
    envelope = output.candidate_envelopes[0]
    distinct_units = set()
    for packet in envelope["work_packets"]:
        distinct_units.update(packet)
    assert len(distinct_units) == 3
    total_cost = sum(ledger[u]["computed_cost"] for u in distinct_units)
    assert total_cost == 1 + 1 + 4 == 6


def test_independent_targets_preserve_separate_work_units():
    """Auth preparations to distinct hosts (Host C0 vs OtherHost) are not conflated."""
    provider = accepted_test_provider()
    resolver = RatingResolver(effort_providers=[provider])
    scope = make_scope()

    cand = {
        "candidate_id": "cand_multi_target",
        "transition_history": [
            {
                "technique": "remote_exec_winrm",
                "actor": FOOTHOLD_SID,
                "source": FOOTHOLD_SID,
                "target": OTHER_HOST_ID,
                "method": "winrm",
                "requires": ["actor_controlled_alice"],
                "adds": ["admin_channel_alice_host"],
            },
            {
                "technique": "remote_exec_winrm",
                "actor": OTHER_HOST_ID,
                "source": OTHER_HOST_ID,
                "target": TARGET_HOST_ID,
                "method": "winrm",
                "requires": ["admin_channel_alice_host"],
                "adds": ["admin_control_host"],
            },
        ],
    }

    output = resolver.resolve([cand], scope)
    ledger = output.ranking_query["work_units_ledger"]

    # Must produce two distinct work units with cost 1 each, 1 + 1 = 2
    assert len(ledger) == 2
    for rec in ledger.values():
        assert rec["computed_cost"] == 1
    total_cost = sum(r["computed_cost"] for r in ledger.values())
    assert total_cost == 2


# ===========================================================================
# 6. Passive Steps Incur Zero Cost
# ===========================================================================


def test_passive_closure_incurs_zero_cost():
    """Passive group entitlement propagation creates no work units and adds zero effort."""
    provider = accepted_test_provider()
    resolver = RatingResolver(effort_providers=[provider])
    scope = make_scope()

    cand_direct = {
        "candidate_id": "cand_direct",
        "transition_history": [
            {
                "technique": "obtain_admin_execution_on_host",
                "actor": FOOTHOLD_SID,
                "source": FOOTHOLD_SID,
                "target": TARGET_HOST_ID,
                "method": "inherited",
                "alias": "w-inherited-admin",
                "requires": ["actor_controlled_alice"],
                "adds": ["admin_control_host"],
            }
        ],
    }

    cand_with_passive = {
        "candidate_id": "cand_with_passive",
        "transition_history": [
            {
                "technique": "propagate_group_entitlement",
                "actor": FOOTHOLD_SID,
                "source": FOOTHOLD_SID,
                "target": GROUP_ADMINS_SID,
                "is_passive_closure": True,
                "requires": ["actor_controlled_alice"],
                "adds": ["effective_member_alice_admins"],
            },
            {
                "technique": "obtain_admin_execution_on_host",
                "actor": FOOTHOLD_SID,
                "source": FOOTHOLD_SID,
                "target": TARGET_HOST_ID,
                "method": "inherited",
                "alias": "w-inherited-admin",
                "requires": ["effective_member_alice_admins"],
                "adds": ["admin_control_host"],
            },
        ],
    }

    output = resolver.resolve([cand_direct, cand_with_passive], scope)
    ledger = output.ranking_query["work_units_ledger"]

    env1 = output.candidate_envelopes[0]
    env2 = output.candidate_envelopes[1]

    # Passive step adds empty packet ()
    assert env2["work_packets"][0] == []
    # Both envelopes reference the exact same single active work unit
    u1 = [u for p in env1["work_packets"] for u in p]
    u2 = [u for p in env2["work_packets"] for u in p]
    assert u1 == u2
    cost1 = sum(ledger[u]["computed_cost"] for u in set(u1))
    cost2 = sum(ledger[u]["computed_cost"] for u in set(u2))
    assert cost1 == cost2 == 1


# ===========================================================================
# 7. Candidate Enumeration Order Invariance
# ===========================================================================


def test_candidate_enumeration_order_invariance():
    """Candidate input order does not alter resolved identities or costs."""
    provider = accepted_test_provider()
    resolver = RatingResolver(effort_providers=[provider])
    scope = make_scope()

    c1 = {
        "candidate_id": "c1",
        "transition_history": [
            {
                "technique": "reset_password",
                "actor": FOOTHOLD_SID,
                "source": FOOTHOLD_SID,
                "target": TARGET_HOST_ID,
                "requires": ["actor_controlled_alice"],
                "adds": ["admin_control_host"],
            }
        ],
    }
    c2 = {
        "candidate_id": "c2",
        "transition_history": [
            {
                "technique": "acquire_ticket",
                "actor": FOOTHOLD_SID,
                "source": FOOTHOLD_SID,
                "target": TARGET_HOST_ID,
                "requires": ["actor_controlled_alice"],
                "adds": ["admin_control_host"],
            }
        ],
    }

    out_12 = resolver.resolve([c1, c2], scope)
    out_21 = resolver.resolve([c2, c1], scope)

    ledger_12 = out_12.ranking_query["work_units_ledger"]
    ledger_21 = out_21.ranking_query["work_units_ledger"]

    assert set(ledger_12.keys()) == set(ledger_21.keys())
    for k in ledger_12:
        assert ledger_12[k]["computed_cost"] == ledger_21[k]["computed_cost"]
        assert ledger_12[k]["rubric_scores"] == ledger_21[k]["rubric_scores"]


# ===========================================================================
# 8. Negative Probes (Fail-Closed Guarantees)
# ===========================================================================


def test_negative_probe_unsupported_technique():
    """Unrecognized attack technique returns UNSUPPORTED with UNSUPPORTED_TECHNIQUE."""
    provider = accepted_test_provider()
    scope = make_scope()

    key = generate_rating_lookup_key_c(
        work_unit_id="alien_exploit:actor:target:default:intra_forest:1.0.0",
        technique="alien_zero_day_teleportation",
        actor_id=FOOTHOLD_SID,
        target_id=TARGET_HOST_ID,
    )
    res = provider.resolve_effort(key, {"overlap_state": "independent"}, scope)
    assert res.disposition == ResolverDisposition.UNSUPPORTED
    assert res.reason_code == ReasonCode.UNSUPPORTED_TECHNIQUE
    assert res.value is None


def test_negative_probe_boundary_mismatch_refused():
    """Boundary mismatch (e.g. cross_forest) triggers REFUSED with OUT_OF_SCOPE."""
    provider = accepted_test_provider()
    scope = make_scope()

    key = generate_rating_lookup_key_c(
        work_unit_id="reset_password:actor:target:default:cross_forest_external:1.0.0",
        technique="reset_password",
        actor_id=FOOTHOLD_SID,
        target_id=TARGET_HOST_ID,
        boundary="cross_forest_external",
    )
    res = provider.resolve_effort(key, {"overlap_state": "independent"}, scope)
    assert res.disposition == ResolverDisposition.REFUSED
    assert res.reason_code == ReasonCode.OUT_OF_SCOPE


def test_negative_probe_unresolved_overlap_fails_closed():
    """Work unit with unresolved_overlap resolves to UNRATED with EXPLICIT_UNRATED_DISPOSITION."""
    provider = accepted_test_provider()
    scope = make_scope()

    key = generate_rating_lookup_key_c(
        work_unit_id="reset_password:actor:target:default:intra_forest:1.0.0",
        technique="reset_password",
        actor_id=FOOTHOLD_SID,
        target_id=TARGET_HOST_ID,
    )
    # Mark record with unresolved_overlap
    rec = {"overlap_state": "unresolved_overlap"}
    res = provider.resolve_effort(key, rec, scope)
    assert res.disposition == ResolverDisposition.UNRATED
    assert res.reason_code == ReasonCode.EXPLICIT_UNRATED_DISPOSITION
    assert res.value is None


def test_negative_probe_conflicting_registry_definitions():
    """Registry detects conflicting class definitions and raises RankingValidationError."""
    reg = WorkUnitClassRegistry()
    c1 = WorkUnitClass(
        class_id="class_test_conflict",
        name="Test 1",
        description="desc",
        t1=1,
        t2=1,
        applicability=ClassApplicability(techniques=("tech_a",)),
    )
    c2 = WorkUnitClass(
        class_id="class_test_conflict",
        name="Test 2",
        description="desc conflicting",
        t1=3,
        t2=3,
        applicability=ClassApplicability(techniques=("tech_a",)),
    )
    reg.register(c1)
    with pytest.raises(RankingValidationError, match="Conflicting class registration"):
        reg.register(c2)


def test_negative_probe_ambiguous_conflicting_classes_returns_conflicting():
    """Ambiguous classes with contradictory costs return ResolverDisposition.CONFLICTING."""
    reg = WorkUnitClassRegistry()
    c1 = WorkUnitClass(
        class_id="class_ambiguous_low",
        name="Low Cost",
        description="desc",
        t1=1,
        t2=1,  # C=0
        applicability=ClassApplicability(techniques=("conflicting_tech",)),
    )
    c2 = WorkUnitClass(
        class_id="class_ambiguous_high",
        name="High Cost",
        description="desc",
        t1=3,
        t2=3,  # C=4
        applicability=ClassApplicability(techniques=("conflicting_tech",)),
    )
    reg.register(c1)
    reg.register(c2)

    provider = ReviewedWorkUnitClassEffortProvider(registry=reg)
    key = generate_rating_lookup_key_c(
        work_unit_id="conflicting_tech:u:v:ctx:1.0.0",
        technique="conflicting_tech",
        actor_id=FOOTHOLD_SID,
        target_id=TARGET_HOST_ID,
    )
    res = provider.resolve_effort(key, {"overlap_state": "independent"}, make_scope())
    assert res.disposition == ResolverDisposition.CONFLICTING
    assert res.reason_code == ReasonCode.CONFLICTING_PROVIDER_BASIS


# ===========================================================================
# 9. Absolute Refusal of Unit Weights (W=1.0) and MAUT Fallback
# ===========================================================================


def test_no_unit_weight_or_maut_fallback():
    """Ensure no default 1.0 structural edge weights or maut_v1 fallback exists."""
    provider = accepted_test_provider()
    scope = make_scope()

    # Query an unrated class
    key = generate_rating_lookup_key_c(
        work_unit_id="unconstrained_delegation:u:v:default:intra_forest:1.0.0",
        technique="unconstrained_delegation_abuse",
        actor_id=FOOTHOLD_SID,
        target_id=TARGET_HOST_ID,
    )
    res = provider.resolve_effort(key, {"overlap_state": "independent"}, scope)
    assert res.disposition == ResolverDisposition.UNRATED
    assert res.reason_code == ReasonCode.MISSING_EVIDENCE
    # Cost MUST be None, never 1.0 or 0
    assert res.value is None


# ===========================================================================
# 10. Independent Min-Effort Multi-Path Oracle with PathRankingEngine
# ===========================================================================


def test_min_effort_multi_path_oracle_roundtrip():
    """Evaluate Candidate 1 (Direct C=5) vs Candidate 2 (Inherited C=2) via canonical engine.

    Demonstrates counter-structural Min-Effort: the 2-step path (M/I) requires lower effort
    than the 1-step direct path (D).
    """

    class SyntheticLikelihoodProvider:
        name = "test_p_provider"
        provider_version = "1.0.0"

        def resolve_likelihood(self, key, prefix, outcome_unit, scope_map):
            return ResolutionResult(
                disposition=ResolverDisposition.RATED,
                value=(Fraction(1, 2), Fraction(3, 4)),
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
                value="High",
                reason_code=ReasonCode.REVIEWED_PACKET_MATCH,
                provider_name=self.name,
                basis_category=BasisClassification.SYNTHETIC_TEST_ONLY,
            )

    provider = accepted_test_provider()
    resolver = RatingResolver(
        effort_providers=[provider],
        likelihood_providers=[SyntheticLikelihoodProvider()],
        impact_providers=[SyntheticImpactProvider()],
    )
    scope = make_scope()

    # Shared preparation w-auth-context
    shared_preps = {
        "w-auth-context": {
            "work_unit_id": "w-auth-context",
            "alias": "w-auth-context",
            "rating_status": "unrated",
            "overlap_state": "independent",
            "technique": "auth_context",
            "classification": WorkUnitClassification.SHARED_PREPARATION.value,
            "actor_id": FOOTHOLD_SID,
            "target_id": TARGET_HOST_ID,
        }
    }

    # Candidate 1: Direct admin (D)
    # References w-auth-context (C=1) + w-direct-admin (C=4) => C = 5
    cand_direct = {
        "candidate_id": "cand_direct_admin",
        "transition_history": [
            {
                "technique": "obtain_admin_execution_on_host",
                "actor": FOOTHOLD_SID,
                "source": FOOTHOLD_SID,
                "target": TARGET_HOST_ID,
                "method": "direct",
                "alias": "w-direct-admin",
                "shared_prep_key": "w-auth-context",
                "requires": [
                    "actor_controlled_alice",
                    "admin_channel_alice_host",
                    "authentication_accepted_alice_host",
                ],
                "adds": ["admin_control_host"],
            }
        ],
    }

    # Candidate 2: Member-inherited admin (M / I)
    # Step 1: Passive member-of propagation (C=0, no work unit)
    # Step 2: Inherited admin (w-auth-context [C=1] + w-inherited-admin [C=1] => C = 2)
    cand_inherited = {
        "candidate_id": "cand_member_inherited",
        "transition_history": [
            {
                "technique": "propagate_group_entitlement",
                "actor": FOOTHOLD_SID,
                "source": FOOTHOLD_SID,
                "target": GROUP_ADMINS_SID,
                "is_passive_closure": True,
                "requires": [
                    "actor_controlled_alice",
                    "security_group_admins",
                    "membership_usable_alice_admins",
                ],
                "adds": ["effective_member_alice_admins"],
            },
            {
                "technique": "obtain_admin_execution_on_host",
                "actor": FOOTHOLD_SID,
                "source": GROUP_ADMINS_SID,
                "target": TARGET_HOST_ID,
                "method": "inherited",
                "alias": "w-inherited-admin",
                "shared_prep_key": "w-auth-context",
                "requires": [
                    "actor_controlled_alice",
                    "effective_member_alice_admins",
                    "admin_channel_alice_host",
                    "authentication_accepted_alice_host",
                ],
                "adds": ["admin_control_host"],
            },
        ],
    }

    resolution = resolver.resolve(
        [cand_direct, cand_inherited],
        scope,
        shared_preparation_units=shared_preps,
    )

    ranking_query = resolution.ranking_query
    envelopes = resolution.candidate_envelopes

    # Check work units ledger costs by alias
    ledger = ranking_query["work_units_ledger"]
    by_alias = {rec.get("alias", uid): rec for uid, rec in ledger.items()}
    assert by_alias["w-auth-context"]["computed_cost"] == 1
    assert by_alias["w-direct-admin"]["computed_cost"] == 4
    assert by_alias["w-inherited-admin"]["computed_cost"] == 1

    # Verify query wire decoding and envelopes
    decoded_query = decode_ranking_query(ranking_query)
    for env in envelopes:
        validate_candidate_envelope(env, decoded_query)

    # Execute canonical evaluation through PathRankingEngine
    engine = PathRankingEngine(version="1.0.0")
    ranking_res = engine.evaluate(ranking_query, envelopes)
    payload = ranking_res["result_payload"]

    # Verify both candidates are eligible
    assert set(payload["eligible_candidates"]) == {"cand_direct_admin", "cand_member_inherited"}

    # Verify Min-Effort finding: counter-structural optimality
    # cand_member_inherited (C=2) beats cand_direct_admin (C=5)
    min_effort = payload["min_effort_to_da_baseline"]
    assert min_effort["best_candidate_id"] == "cand_member_inherited"
    assert min_effort["minimum_effort_value"] == 2


# ===========================================================================
# 11. Week 3 SEAMLESS Parameter Parity Regression Protection
# ===========================================================================


def test_week3_seamless_parameter_parity():
    """Verify that reviewed work-unit classes match accepted Week 3 SEAMLESS values."""
    provider = accepted_test_provider()
    scope = make_scope()

    # Reset password: T1=1, T2=2, C=1
    k_reset = generate_rating_lookup_key_c(
        work_unit_id="reset_password:lidia:target:default:intra_forest:1.0.0",
        technique="reset_password",
        actor_id=FOOTHOLD_SID,
        target_id=TARGET_HOST_ID,
    )
    r_reset = provider.resolve_effort(k_reset, {"overlap_state": "independent"}, scope)
    assert r_reset.value == 1
    assert r_reset.rubric_scores["t1"] == 1
    assert r_reset.rubric_scores["t2"] == 2

    # Acquire ticket: T1=1, T2=1, C=0
    k_ticket = generate_rating_lookup_key_c(
        work_unit_id="acquire_ticket:lidia:target:default:intra_forest:1.0.0",
        technique="acquire_ticket",
        actor_id=FOOTHOLD_SID,
        target_id=TARGET_HOST_ID,
    )
    r_ticket = provider.resolve_effort(k_ticket, {"overlap_state": "independent"}, scope)
    assert r_ticket.value == 0
    assert r_ticket.rubric_scores["t1"] == 1
    assert r_ticket.rubric_scores["t2"] == 1

    # Remote exec WinRM: T1=1, T2=2, C=1
    k_winrm = generate_rating_lookup_key_c(
        work_unit_id="remote_exec_winrm:lidia:target:default:intra_forest:1.0.0",
        technique="remote_exec_winrm",
        actor_id=FOOTHOLD_SID,
        target_id=TARGET_HOST_ID,
    )
    r_winrm = provider.resolve_effort(k_winrm, {"overlap_state": "independent"}, scope)
    assert r_winrm.value == 1
    assert r_winrm.rubric_scores["t1"] == 1
    assert r_winrm.rubric_scores["t2"] == 2


def test_obtain_admin_execution_direct_vs_inherited():
    """Verify obtain_admin_execution_on_host direct and inherited branch disambiguation."""
    provider = accepted_test_provider()
    scope = make_scope(scenario_id="synthetic-a2")

    # Direct host admin: actor == source -> class_direct_host_admin_execution (T1=3, T2=3, C=4)
    k_direct = generate_rating_lookup_key_c(
        work_unit_id="obtain_admin_execution_on_host:alice:host:default:intra_forest:1.0.0",
        technique="obtain_admin_execution_on_host",
        actor_id=FOOTHOLD_SID,
        source_id=FOOTHOLD_SID,
        target_id=TARGET_HOST_ID,
    )
    r_direct = provider.resolve_effort(k_direct, {"overlap_state": "independent"}, scope)
    assert r_direct.disposition == ResolverDisposition.RATED
    assert r_direct.value == 4
    assert r_direct.rubric_scores == {
        "t1": 3,
        "t2": 3,
        "formula": "base",
        "computed_cost": 4,
        "effort_cost": 4,
    }

    # Synthetic inherited branch: T1=1, T2=2, C=1.
    k_inherited = generate_rating_lookup_key_c(
        work_unit_id="obtain_admin_execution_on_host:alice:host:default:intra_forest:1.0.0",
        technique="obtain_admin_execution_on_host",
        actor_id=FOOTHOLD_SID,
        source_id=GROUP_ADMINS_SID,
        target_id=TARGET_HOST_ID,
    )
    r_inherited = provider.resolve_effort(k_inherited, {"overlap_state": "independent"}, scope)
    assert r_inherited.disposition == ResolverDisposition.RATED
    assert r_inherited.value == 1
    assert r_inherited.rubric_scores == {
        "t1": 1,
        "t2": 2,
        "formula": "base",
        "computed_cost": 1,
        "effort_cost": 1,
    }

    # Explicit method="direct" override matches class_direct_host_admin_execution
    k_override_direct = generate_rating_lookup_key_c(
        work_unit_id="obtain_admin_execution_on_host:alice:host:direct:intra_forest:1.0.0",
        technique="obtain_admin_execution_on_host",
        actor_id=FOOTHOLD_SID,
        source_id=GROUP_ADMINS_SID,
        target_id=TARGET_HOST_ID,
        method="direct",
    )
    r_override_direct = provider.resolve_effort(
        k_override_direct, {"overlap_state": "independent"}, scope
    )
    assert r_override_direct.disposition == ResolverDisposition.RATED
    assert r_override_direct.value == 4

    # Explicit method="inherited" override matches class_inherited_host_admin_execution
    k_override_inherited = generate_rating_lookup_key_c(
        work_unit_id="obtain_admin_execution_on_host:alice:host:inherited:intra_forest:1.0.0",
        technique="obtain_admin_execution_on_host",
        actor_id=FOOTHOLD_SID,
        source_id=FOOTHOLD_SID,
        target_id=TARGET_HOST_ID,
        method="inherited",
    )
    r_override_inherited = provider.resolve_effort(
        k_override_inherited, {"overlap_state": "independent"}, scope
    )
    assert r_override_inherited.disposition == ResolverDisposition.RATED
    assert r_override_inherited.value == 1


def test_default_admin_channel_resolves_without_alias():
    """Default generic channel has one proposal, without transport inference."""
    provider = accepted_test_provider()
    scope = make_scope()

    # Ambiguous key: source_id is None, method is default, alias is empty
    k_ambiguous = generate_rating_lookup_key_c(
        work_unit_id="obtain_admin_execution_on_host:actor:target:default:intra_forest:1.0.0",
        technique="obtain_admin_execution_on_host",
        actor_id=FOOTHOLD_SID,
        target_id=TARGET_HOST_ID,
    )
    r_ambiguous = provider.resolve_effort(k_ambiguous, {"overlap_state": "independent"}, scope)
    assert r_ambiguous.disposition == ResolverDisposition.RATED
    assert r_ambiguous.reason_code == ReasonCode.REVIEWED_PACKET_MATCH
    assert r_ambiguous.value == 1


def test_alias_cannot_authorize_unknown_technique():
    provider = accepted_test_provider()
    key = generate_rating_lookup_key_c("unknown", "unknown", FOOTHOLD_SID, TARGET_HOST_ID)
    result = provider.resolve_effort(key, {"alias": "WU_DIRECT_ADMIN"}, make_scope())
    assert result.disposition == ResolverDisposition.UNSUPPORTED


def test_proposed_catalog_cannot_self_certify_review():
    provider = ReviewedWorkUnitClassEffortProvider(get_default_work_unit_registry())
    key = generate_rating_lookup_key_c("probe", "asrep_request", FOOTHOLD_SID, TARGET_HOST_ID)
    result = provider.resolve_effort(key, {}, make_scope())
    assert result.disposition == ResolverDisposition.UNRATED
    assert result.value is None
    assert "pending" in result.reason_detail


@pytest.mark.skipif(
    not Path(
        os.environ.get("SEAMLESS_RAW_DIR", Path(__file__).parents[1] / "data/raw/SEAMLESS")
    ).is_dir(),
    reason="manifest-verified private SEAMLESS raw inputs required",
)
def test_real_frozen_program_automatic_class_matching():
    from tests.frozen_rating_inputs import frozen_program

    paths, scope, bindings = frozen_program()
    provider = accepted_test_provider()
    output = RatingResolver(effort_providers=[provider]).resolve(
        paths, scope, transition_bindings=bindings
    )
    ledger = output.ranking_query["work_units_ledger"]
    assert [r["computed_cost"] for r in ledger.values()] == [0, 2, 0, 1]
    assert [r["technique"] for r in ledger.values()] == [
        "asrep_request",
        "recover_asrep_secret",
        "activate_recovered_identity",
        "obtain_admin_execution_on_host",
    ]
    terminal = next(
        r for r in ledger.values() if r["technique"] == "obtain_admin_execution_on_host"
    )
    key = generate_rating_lookup_key_c(
        terminal["work_unit_id"],
        terminal["technique"],
        terminal["actor_id"],
        terminal["target_id"],
        source_id=terminal["source_id"],
        auth_context=terminal["auth_context"],
    )
    matches, _, _ = provider.registry.match(key, terminal, scope)
    assert [c.class_id for c in matches] == ["class_host_admin_channel"]
    reverse = ReviewedWorkUnitClassEffortProvider(
        WorkUnitClassRegistry(list(reversed(provider.registry.list_classes())))
    )
    assert reverse.resolve_effort(key, terminal, scope) == provider.resolve_effort(
        key, terminal, scope
    )


def test_generated_min_effort_and_passive_closure():
    from pathlib import Path

    from src.engine import AttackQuery, run_attack_query
    from tests.test_week4_min_effort_search import ALIASES, DEFAULT_RUNTIME_FACTS

    graph = json.loads(
        (Path(__file__).parent / "fixtures/attack_scenarios/graphs/two-routes.json").read_text()
    )
    result = run_attack_query(
        AttackQuery(
            initial_actor="Alice",
            initial_state={"control": ["Alice"]},
            target="Host",
            target_goal={"target": "Host", "required_state": {"admin_control": ["Host"]}},
            aliases=ALIASES,
            runtime_facts=DEFAULT_RUNTIME_FACTS,
            allowed_techniques=["propagate_group_entitlement", "obtain_admin_execution_on_host"],
            budget={"max_paths": 1000, "max_steps": 12, "max_expansions": 100000},
        ),
        graph,
    )
    paths = result.search_result.paths
    assert len(paths) == 3
    bindings = {}
    for path in paths:
        for step in path.transition_history:
            r = step.result.request
            passive = r.technique_id == "propagate_group_entitlement"
            inherited = r.source != r.actor
            bindings[(r.technique_id, r.actor, r.source, r.target)] = {
                "requires": ["actor_controlled_alice"]
                + (["effective_member_alice_admins"] if inherited else []),
                "adds": ["effective_member_alice_admins" if passive else "admin_control_host"],
                **({} if passive else {"shared_prep_key": "w-auth-context"}),
            }
    preparation = {
        "w-auth-context": {
            "work_unit_id": "w-auth-context",
            "technique": "auth_context",
            "classification": "shared_preparation",
            "actor_id": FOOTHOLD_SID,
            "target_id": TARGET_HOST_ID,
            "overlap_state": "independent",
        }
    }
    scope = make_scope(scenario_id="synthetic-a2", snapshot_id=graph["metadata"]["snapshot_id"])
    resolver = RatingResolver(effort_providers=[accepted_test_provider()])
    outputs = [
        resolver.resolve(
            order, scope, transition_bindings=bindings, shared_preparation_units=preparation
        )
        for order in (paths, tuple(reversed(paths)))
    ]
    costs = []
    for output in outputs:
        ledger = output.ranking_query["work_units_ledger"]
        assert len(ledger) == 3
        assert ledger["w-auth-context"]["computed_cost"] == 1
        assert all(r["technique"] != "propagate_group_entitlement" for r in ledger.values())
        passive_actions = [
            a for a in output.ranking_query["bound_actions"] if a["is_passive_closure"]
        ]
        assert all(a["referenced_work_unit_ids"] == [] for a in passive_actions)
        payload = PathRankingEngine().evaluate(output.ranking_query, output.candidate_envelopes)[
            "result_payload"
        ]
        baseline = payload["min_effort_to_da_baseline"]
        assert baseline["minimum_effort_value"] == 2
        winner = next(
            e
            for e in output.candidate_envelopes
            if e["candidate_id"] == baseline["best_candidate_id"]
        )
        assert len(winner["bound_action_ids"]) == 2
        costs.append(sorted(ledger[u]["computed_cost"] for u in ledger))
    assert costs[0] == costs[1] == [1, 1, 4]
