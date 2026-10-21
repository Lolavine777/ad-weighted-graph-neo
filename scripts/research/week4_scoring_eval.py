"""Week 4 Scoring and Canonical Evaluator Verification Tool.

Generates and validates Week 4 scoring packages for Issue #207:
- Synthetic fixture A2 under Ledger E (counter-structural Min-Effort).
- Synthetic fixture A2 under Ledger T (3-way Min-Effort tie).
- Synthetic fixture A2 point-likelihood tie-break under ADR-0013 Section 4.
- Synthetic fixture A2 diagnostics (fail-closed partitioning).
- SEAMLESS Week 4 reviewed parameter disposition.
- Verification via canonical PathRankingEngine (Specification v1.0.0).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.engine.ranking import PathRankingEngine  # noqa: E402

RATINGS_DIR = ROOT / "docs" / "research" / "ratings" / "week4"

# Canonical Node IDs from two-routes fixture
ALICE_ID = "S-1-5-21-1000-2000-3000-1101"
ADMINS_ID = "S-1-5-21-1000-2000-3000-2103"
HOST_C0_ID = "10000000-0000-4000-8000-000000000002"
OTHERHOST_X_ID = "10000000-0000-4000-8000-000000000003"

# Canonical Edge IDs from two-routes fixture
EDGE_DIRECT_ID = "sha256:8f30ade289c16f75c747c8651362d8483c3ac7793c5a3f47b769fcbf110fca67"
EDGE_MEMBER_ID = "sha256:e2cd3c70f3965249626848c95819d3ded826e66056e60dcc519459d71a644456"
EDGE_INHERITED_ID = "sha256:96f8b42d2faeec14ace61d181e577b0f7d45e3950982bc1174e85fab9f4af716"

SNAPSHOT_TWO_ROUTES = "sha256:cc6b062c65d9266268673105c46c9b0ec199a17fedb70cb3ab64407361c389d3"
PROVENANCE_LOCATOR = "synthetic://golden/two-routes"


def build_synthetic_a2_base_query(query_id: str) -> dict[str, Any]:
    """Construct common query structure for fixture A2 (w4-two-routes-exact)."""
    return {
        "query_metadata": {
            "query_id": query_id,
            "version": "1.0.0",
            "scenario_id": "w4-two-routes-exact",
            "scenario_version": "1.0.0",
            "snapshot_id": SNAPSHOT_TWO_ROUTES,
            "evaluation_mode": "scenario",
            "work_boundary": "synthetic_two_routes",
            "foothold_node_id": ALICE_ID,
            "target_goal": {
                "goal_id": "admin_host_c0",
                "description": "Administrative control on Host C0",
                "target_asset_id": HOST_C0_ID,
                "success_event": "admin_execution_on_host_c0",
                "required_predicates": ["admin_control_host"],
            },
            "horizon": "fixed_snapshot_window",
            "active_work_budget": 10,
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
                    "provenance_reference": "synthetic://golden/two-routes/facts/alice",
                },
                {
                    "predicate": "admin_channel_alice_host",
                    "layer": 3,
                    "truth_value": True,
                    "provenance_reference": "synthetic://golden/two-routes/facts/admin_channel",
                },
                {
                    "predicate": "authentication_accepted_alice_host",
                    "layer": 3,
                    "truth_value": True,
                    "provenance_reference": "synthetic://golden/two-routes/facts/auth",
                },
                {
                    "predicate": "security_group_admins",
                    "layer": 3,
                    "truth_value": True,
                    "provenance_reference": "synthetic://golden/two-routes/facts/sec_group",
                },
                {
                    "predicate": "membership_usable_alice_admins",
                    "layer": 3,
                    "truth_value": True,
                    "provenance_reference": "synthetic://golden/two-routes/facts/membership_usable",
                },
            ],
            "false_facts": [],
            "assumed_facts": [],
            "unknown_facts": [],
        },
        "target_impact_assessments": {
            HOST_C0_ID: {
                "target_asset_id": HOST_C0_ID,
                "success_event": "admin_execution_on_host_c0",
                "rating_status": "rated",
                "consequence_rating": "High",
                "business_rationale": (
                    "Administrative control over Host C0 compromises host-level applications and "
                    "data. In the synthetic test enterprise context, Host C0 is a departmental "
                    "server without domain-wide Tier0 authority, so High consequence is "
                    "appropriate rather than Critical."
                ),
                "affected_business_services": ["synthetic_host_service"],
                "missing_basis_reasons": [],
            }
        },
        "bound_actions": [
            {
                "action_id": "action_direct_admin",
                "technique": "obtain_admin_execution_on_host",
                "technique_name": "obtain_admin_execution_on_host",
                "actor_id": ALICE_ID,
                "target_id": HOST_C0_ID,
                "edge_id": EDGE_DIRECT_ID,
                "referenced_work_unit_ids": ["w-auth-context", "w-direct-admin"],
                "requires": [
                    "actor_controlled_alice",
                    "admin_channel_alice_host",
                    "authentication_accepted_alice_host",
                ],
                "adds": ["admin_control_host"],
                "is_passive_closure": False,
            },
            {
                "action_id": "action_member_admins",
                "technique": "propagate_group_entitlement",
                "technique_name": "propagate_group_entitlement",
                "actor_id": ALICE_ID,
                "target_id": ADMINS_ID,
                "edge_id": EDGE_MEMBER_ID,
                "referenced_work_unit_ids": [],
                "requires": [
                    "actor_controlled_alice",
                    "security_group_admins",
                    "membership_usable_alice_admins",
                ],
                "adds": ["effective_member_alice_admins"],
                "is_passive_closure": True,
            },
            {
                "action_id": "action_inherited_admin",
                "technique": "obtain_admin_execution_on_host",
                "technique_name": "obtain_admin_execution_on_host",
                "actor_id": ALICE_ID,
                "target_id": HOST_C0_ID,
                "edge_id": EDGE_INHERITED_ID,
                "referenced_work_unit_ids": ["w-auth-context", "w-inherited-admin"],
                "requires": [
                    "actor_controlled_alice",
                    "effective_member_alice_admins",
                    "admin_channel_alice_host",
                    "authentication_accepted_alice_host",
                ],
                "adds": ["admin_control_host"],
                "is_passive_closure": False,
            },
        ],
    }


def build_synthetic_a2_candidates(query_id: str) -> list[dict[str, Any]]:
    """Build candidate envelopes for fixture A2: D, M/D, and M/I."""
    scope_binding = {
        "query_id": query_id,
        "scenario_id": "w4-two-routes-exact",
        "scenario_version": "1.0.0",
        "snapshot_id": SNAPSHOT_TWO_ROUTES,
        "work_boundary": "synthetic_two_routes",
        "horizon": "fixed_snapshot_window",
        "foothold_node_id": ALICE_ID,
    }
    return [
        {
            "candidate_id": "cand_direct",
            "target_asset_id": HOST_C0_ID,
            "bound_action_ids": ["action_direct_admin"],
            "scope_binding": scope_binding,
            "structural_routes": [
                {
                    "route_id": "route_direct",
                    "node_ids": [ALICE_ID, HOST_C0_ID],
                    "edge_ids": [EDGE_DIRECT_ID],
                    "provenance_locators": [PROVENANCE_LOCATOR],
                }
            ],
        },
        {
            "candidate_id": "cand_member_direct",
            "target_asset_id": HOST_C0_ID,
            "bound_action_ids": ["action_member_admins", "action_direct_admin"],
            "scope_binding": scope_binding,
            "transition_lineage": [
                {
                    "step_index": 0,
                    "action_id": "action_member_admins",
                    "technique_id": "propagate_group_entitlement",
                    "actor": ALICE_ID,
                    "source": ALICE_ID,
                    "target": ADMINS_ID,
                    "edge_id": EDGE_MEMBER_ID,
                    "origin": "observed_edge",
                    "derived_from_step": None,
                    "status": "applicable",
                },
                {
                    "step_index": 1,
                    "action_id": "action_direct_admin",
                    "technique_id": "obtain_admin_execution_on_host",
                    "actor": ALICE_ID,
                    "source": ALICE_ID,
                    "target": HOST_C0_ID,
                    "edge_id": EDGE_DIRECT_ID,
                    "origin": "observed_edge",
                    "derived_from_step": None,
                    "status": "applicable",
                },
            ],
            "structural_routes": [
                {
                    "route_id": "route_member_seg",
                    "node_ids": [ALICE_ID, ADMINS_ID],
                    "edge_ids": [EDGE_MEMBER_ID],
                    "provenance_locators": [PROVENANCE_LOCATOR],
                    "action_step_indices": [0],
                },
                {
                    "route_id": "route_direct_seg",
                    "node_ids": [ALICE_ID, HOST_C0_ID],
                    "edge_ids": [EDGE_DIRECT_ID],
                    "provenance_locators": [PROVENANCE_LOCATOR],
                    "action_step_indices": [1],
                },
            ],
        },
        {
            "candidate_id": "cand_member_inherited",
            "target_asset_id": HOST_C0_ID,
            "bound_action_ids": ["action_member_admins", "action_inherited_admin"],
            "scope_binding": scope_binding,
            "structural_routes": [
                {
                    "route_id": "route_member_inherited",
                    "node_ids": [ALICE_ID, ADMINS_ID, HOST_C0_ID],
                    "edge_ids": [EDGE_MEMBER_ID, EDGE_INHERITED_ID],
                    "provenance_locators": [PROVENANCE_LOCATOR, PROVENANCE_LOCATOR],
                }
            ],
        },
    ]


def build_package_a2_e() -> dict[str, Any]:
    """Construct Package A2 under Ledger E (w-direct-admin cost 4, w-inherited-admin cost 1)."""
    query_id = "query-week4-synthetic-a2-e"
    query = build_synthetic_a2_base_query(query_id)
    query["work_units_ledger"] = {
        "w-auth-context": {
            "alias": "WU_AUTH_CONTEXT",
            "rating_status": "rated",
            "overlap_state": "independent",
            "computed_cost": 1,
            "effort_cost": 1,
            "rubric_scores": {"t1": 1, "t2": 2, "formula": "base", "computed_cost": 1},
            "summary": "Establish shared authentication context for Alice towards Host C0",
            "technical_source": "synthetic://rubric/w-auth-context",
            "applicable_queries": [query_id],
            "missing_basis_reasons": [],
        },
        "w-direct-admin": {
            "alias": "WU_DIRECT_ADMIN",
            "rating_status": "rated",
            "overlap_state": "independent",
            "computed_cost": 4,
            "effort_cost": 4,
            "rubric_scores": {"t1": 3, "t2": 3, "formula": "base", "computed_cost": 4},
            "summary": "Direct administrator execution on Host C0 after authentication context",
            "technical_source": "synthetic://rubric/w-direct-admin",
            "applicable_queries": [query_id],
            "missing_basis_reasons": [],
        },
        "w-inherited-admin": {
            "alias": "WU_INHERITED_ADMIN",
            "rating_status": "rated",
            "overlap_state": "independent",
            "computed_cost": 1,
            "effort_cost": 1,
            "rubric_scores": {"t1": 1, "t2": 2, "formula": "base", "computed_cost": 1},
            "summary": "Inherited administrator execution on Host C0 via group membership",
            "technical_source": "synthetic://rubric/w-inherited-admin",
            "applicable_queries": [query_id],
            "missing_basis_reasons": [],
        },
    }
    query["conditional_bounds_table"] = [
        {
            "prefix": ["w-auth-context"],
            "lower": "4/5",
            "upper": "9/10",
            "question_id": "q1",
            "outcome_action_id": "action_direct_admin",
            "technical_source": "synthetic://bounds/q1",
            "basis_category": "synthetic_fixture",
            "rationale": "Likelihood of establishing auth context given foothold",
            "applicable_queries": [query_id],
        },
        {
            "prefix": ["w-auth-context", "w-direct-admin"],
            "lower": "1/2",
            "upper": "3/4",
            "question_id": "q2",
            "outcome_action_id": "action_direct_admin",
            "technical_source": "synthetic://bounds/q2",
            "basis_category": "synthetic_fixture",
            "rationale": "Likelihood of direct admin execution given auth context",
            "applicable_queries": [query_id],
        },
        {
            "prefix": ["w-auth-context", "w-inherited-admin"],
            "lower": "3/5",
            "upper": "4/5",
            "question_id": "q3",
            "outcome_action_id": "action_inherited_admin",
            "technical_source": "synthetic://bounds/q3",
            "basis_category": "synthetic_fixture",
            "rationale": (
                "Likelihood of inherited admin execution given auth context and membership"
            ),
            "applicable_queries": [query_id],
        },
    ]
    return {
        "metadata": {
            "package_id": "package-week4-synthetic-a2-e",
            "version": "1.0.0",
            "evidence_class": "synthetic_test_only",
            "description": (
                "Synthetic fixture A2 under Ledger E: M/I has lower effort (2) than D (5), "
                "proving counter-structural Min-Effort."
            ),
        },
        "query": query,
        "candidates": build_synthetic_a2_candidates(query_id),
    }


def build_package_a2_t() -> dict[str, Any]:
    """Construct Package A2 under Ledger T (w-direct-admin cost 1, w-inherited-admin cost 1)."""
    query_id = "query-week4-synthetic-a2-t"
    query = build_synthetic_a2_base_query(query_id)
    query["work_units_ledger"] = {
        "w-auth-context": {
            "alias": "WU_AUTH_CONTEXT",
            "rating_status": "rated",
            "overlap_state": "independent",
            "computed_cost": 1,
            "effort_cost": 1,
            "rubric_scores": {"t1": 1, "t2": 2, "formula": "base", "computed_cost": 1},
            "summary": "Establish shared authentication context for Alice towards Host C0",
            "technical_source": "synthetic://rubric/w-auth-context",
            "applicable_queries": [query_id],
            "missing_basis_reasons": [],
        },
        "w-direct-admin": {
            "alias": "WU_DIRECT_ADMIN",
            "rating_status": "rated",
            "overlap_state": "independent",
            "computed_cost": 1,
            "effort_cost": 1,
            "rubric_scores": {"t1": 1, "t2": 2, "formula": "base", "computed_cost": 1},
            "summary": (
                "Direct administrator execution on Host C0 after authentication context "
                "(Ledger T: cost 1)"
            ),
            "technical_source": "synthetic://rubric/w-direct-admin-t",
            "applicable_queries": [query_id],
            "missing_basis_reasons": [],
        },
        "w-inherited-admin": {
            "alias": "WU_INHERITED_ADMIN",
            "rating_status": "rated",
            "overlap_state": "independent",
            "computed_cost": 1,
            "effort_cost": 1,
            "rubric_scores": {"t1": 1, "t2": 2, "formula": "base", "computed_cost": 1},
            "summary": "Inherited administrator execution on Host C0 via group membership",
            "technical_source": "synthetic://rubric/w-inherited-admin",
            "applicable_queries": [query_id],
            "missing_basis_reasons": [],
        },
    }
    query["conditional_bounds_table"] = [
        {
            "prefix": ["w-auth-context"],
            "lower": "4/5",
            "upper": "9/10",
            "question_id": "q1",
            "outcome_action_id": "action_direct_admin",
            "technical_source": "synthetic://bounds/q1",
            "basis_category": "synthetic_fixture",
            "rationale": "Likelihood of establishing auth context given foothold",
            "applicable_queries": [query_id],
        },
        {
            "prefix": ["w-auth-context", "w-direct-admin"],
            "lower": "1/2",
            "upper": "3/4",
            "question_id": "q2",
            "outcome_action_id": "action_direct_admin",
            "technical_source": "synthetic://bounds/q2",
            "basis_category": "synthetic_fixture",
            "rationale": "Likelihood of direct admin execution given auth context",
            "applicable_queries": [query_id],
        },
        {
            "prefix": ["w-auth-context", "w-inherited-admin"],
            "lower": "3/5",
            "upper": "4/5",
            "question_id": "q3",
            "outcome_action_id": "action_inherited_admin",
            "technical_source": "synthetic://bounds/q3",
            "basis_category": "synthetic_fixture",
            "rationale": (
                "Likelihood of inherited admin execution given auth context and membership"
            ),
            "applicable_queries": [query_id],
        },
    ]
    return {
        "metadata": {
            "package_id": "package-week4-synthetic-a2-t",
            "version": "1.0.0",
            "evidence_class": "synthetic_test_only",
            "description": (
                "Synthetic fixture A2 under Ledger T: all three programs have identical effort 2, "
                "resulting in a 3-way Min-Effort tie."
            ),
        },
        "query": query,
        "candidates": build_synthetic_a2_candidates(query_id),
    }


def build_package_a2_ties() -> dict[str, Any]:
    """Construct Package A2 point-likelihood tie-break under ADR-0013 Section 4.

    Both D and M/I have exact point probability P = 1/2 and same Impact High.
    Under Ledger E: M/I has effort 2, D has effort 5 -> M/I strictly dominates via effort tie-break.
    """
    query_id = "query-week4-synthetic-a2-ties"
    query = build_synthetic_a2_base_query(query_id)
    query["work_units_ledger"] = {
        "w-auth-context": {
            "alias": "WU_AUTH_CONTEXT",
            "rating_status": "rated",
            "overlap_state": "independent",
            "computed_cost": 1,
            "effort_cost": 1,
            "rubric_scores": {"t1": 1, "t2": 2, "formula": "base", "computed_cost": 1},
            "summary": "Establish shared authentication context for Alice towards Host C0",
            "technical_source": "synthetic://rubric/w-auth-context",
            "applicable_queries": [query_id],
            "missing_basis_reasons": [],
        },
        "w-direct-admin": {
            "alias": "WU_DIRECT_ADMIN",
            "rating_status": "rated",
            "overlap_state": "independent",
            "computed_cost": 4,
            "effort_cost": 4,
            "rubric_scores": {"t1": 3, "t2": 3, "formula": "base", "computed_cost": 4},
            "summary": "Direct administrator execution on Host C0 after authentication context",
            "technical_source": "synthetic://rubric/w-direct-admin",
            "applicable_queries": [query_id],
            "missing_basis_reasons": [],
        },
        "w-inherited-admin": {
            "alias": "WU_INHERITED_ADMIN",
            "rating_status": "rated",
            "overlap_state": "independent",
            "computed_cost": 1,
            "effort_cost": 1,
            "rubric_scores": {"t1": 1, "t2": 2, "formula": "base", "computed_cost": 1},
            "summary": "Inherited administrator execution on Host C0 via group membership",
            "technical_source": "synthetic://rubric/w-inherited-admin",
            "applicable_queries": [query_id],
            "missing_basis_reasons": [],
        },
    }
    # Exact point likelihoods: P([w-auth-context]) = 1, P(direct) = 1/2, P(inherited) = 1/2
    query["conditional_bounds_table"] = [
        {
            "prefix": ["w-auth-context"],
            "lower": "1/1",
            "upper": "1/1",
            "question_id": "q1_point",
            "outcome_action_id": "action_direct_admin",
            "technical_source": "synthetic://bounds/q1_point",
            "basis_category": "synthetic_fixture",
            "rationale": "Exact point likelihood for tie-break testing",
            "applicable_queries": [query_id],
        },
        {
            "prefix": ["w-auth-context", "w-direct-admin"],
            "lower": "1/2",
            "upper": "1/2",
            "question_id": "q2_point",
            "outcome_action_id": "action_direct_admin",
            "technical_source": "synthetic://bounds/q2_point",
            "basis_category": "synthetic_fixture",
            "rationale": "Exact point likelihood for tie-break testing",
            "applicable_queries": [query_id],
        },
        {
            "prefix": ["w-auth-context", "w-inherited-admin"],
            "lower": "1/2",
            "upper": "1/2",
            "question_id": "q3_point",
            "outcome_action_id": "action_inherited_admin",
            "technical_source": "synthetic://bounds/q3_point",
            "basis_category": "synthetic_fixture",
            "rationale": "Exact point likelihood for tie-break testing",
            "applicable_queries": [query_id],
        },
    ]
    return {
        "metadata": {
            "package_id": "package-week4-synthetic-a2-ties",
            "version": "1.0.0",
            "evidence_class": "synthetic_test_only",
            "description": (
                "Synthetic fixture A2 under exact point likelihoods: verifies ADR-0013 "
                "Section 4 conditional effort tie-break."
            ),
        },
        "query": query,
        "candidates": build_synthetic_a2_candidates(query_id),
    }


def build_package_a2_diagnostics() -> dict[str, Any]:
    """Construct Package A2 verifying diagnostic partitioning:

    1. Declared runtime assumption is True (gate is feasible), but likelihood bounds are missing
       -> likelihood_unrated, excluded from Pareto frontier.
    2. Work unit unrated (missing friction basis) -> effort_status unrated.
    3. Target consequence unrated -> impact_unrated.
    4. Blocked gate -> gate_status blocked, likelihood withheld.
    5. Unknown gate -> gate_status unknown, likelihood withheld.
    """
    query_id = "query-week4-synthetic-a2-diagnostics"
    query = build_synthetic_a2_base_query(query_id)
    query["query_metadata"]["target_goal"] = {
        "goal_id": "admin_execution_goal",
        "description": "Administrative control goal",
        "required_predicates": ["admin_control_host"],
    }

    # Initialize work_units_ledger with base units plus unrated unit
    query["work_units_ledger"] = {
        "w-auth-context": {
            "alias": "WU_AUTH_CONTEXT",
            "rating_status": "rated",
            "overlap_state": "independent",
            "computed_cost": 1,
            "effort_cost": 1,
            "rubric_scores": {"t1": 1, "t2": 2, "formula": "base", "computed_cost": 1},
            "summary": "Establish shared authentication context for Alice towards Host C0",
            "technical_source": "synthetic://rubric/w-auth-context",
            "applicable_queries": [query_id],
            "missing_basis_reasons": [],
        },
        "w-direct-admin": {
            "alias": "WU_DIRECT_ADMIN",
            "rating_status": "rated",
            "overlap_state": "independent",
            "computed_cost": 4,
            "effort_cost": 4,
            "rubric_scores": {"t1": 3, "t2": 3, "formula": "base", "computed_cost": 4},
            "summary": "Direct administrator execution on Host C0 after authentication context",
            "technical_source": "synthetic://rubric/w-direct-admin",
            "applicable_queries": [query_id],
            "missing_basis_reasons": [],
        },
        "w-inherited-admin": {
            "alias": "WU_INHERITED_ADMIN",
            "rating_status": "rated",
            "overlap_state": "independent",
            "computed_cost": 1,
            "effort_cost": 1,
            "rubric_scores": {"t1": 1, "t2": 2, "formula": "base", "computed_cost": 1},
            "summary": "Inherited administrator execution on Host C0 via group membership",
            "technical_source": "synthetic://rubric/w-inherited-admin",
            "applicable_queries": [query_id],
            "missing_basis_reasons": [],
        },
        "w-unrated-friction": {
            "alias": "WU_UNRATED_FRICTION",
            "rating_status": "unrated",
            "overlap_state": "independent",
            "computed_cost": None,
            "effort_cost": None,
            "summary": "Work unit without empirical friction data",
            "technical_source": "synthetic://rubric/w-unrated",
            "applicable_queries": [query_id],
            "missing_basis_reasons": ["insufficient_empirical_friction_data"],
        },
        "w-auth-otherhost": {
            "alias": "WU_AUTH_OTHERHOST",
            "rating_status": "rated",
            "overlap_state": "independent",
            "computed_cost": 1,
            "effort_cost": 1,
            "rubric_scores": {"t1": 1, "t2": 2, "formula": "base", "computed_cost": 1},
            "summary": "Establish authentication context for Alice towards OtherHost X",
            "technical_source": "synthetic://rubric/w-auth-otherhost",
            "applicable_queries": [query_id],
            "missing_basis_reasons": [],
        },
        "w-direct-admin-otherhost": {
            "alias": "WU_DIRECT_ADMIN_OTHERHOST",
            "rating_status": "rated",
            "overlap_state": "independent",
            "computed_cost": 4,
            "effort_cost": 4,
            "rubric_scores": {"t1": 3, "t2": 3, "formula": "base", "computed_cost": 4},
            "summary": "Direct administrator execution on OtherHost X after authentication context",
            "technical_source": "synthetic://rubric/w-direct-admin-otherhost",
            "applicable_queries": [query_id],
            "missing_basis_reasons": [],
        },
    }

    query["target_impact_assessments"][OTHERHOST_X_ID] = {
        "target_asset_id": OTHERHOST_X_ID,
        "success_event": "admin_execution_on_otherhost",
        "rating_status": "unrated",
        "consequence_rating": None,
        "business_rationale": None,
        "affected_business_services": ["synthetic_service_x"],
        "missing_basis_reasons": ["no_business_consequence_rationale_available"],
    }

    # Add blocked, unknown, and assumed predicates
    query["facts_ledger"]["predicate_layers"]["blocked_firewall_host"] = 3
    query["facts_ledger"]["predicate_layers"]["unknown_service_health"] = 3
    query["facts_ledger"]["predicate_layers"]["target_x_controlled"] = 3
    query["facts_ledger"]["predicate_layers"]["runtime_session_alice"] = 3

    query["facts_ledger"]["observed_facts"].append(
        {
            "predicate": "blocked_firewall_host",
            "layer": 3,
            "truth_value": False,
            "provenance_reference": "synthetic://facts/firewall_blocked",
        }
    )
    query["facts_ledger"]["unknown_facts"].append(
        {
            "predicate": "unknown_service_health",
            "layer": 3,
            "reason": "Declared unknown fact without observation",
        }
    )
    query["facts_ledger"]["assumed_facts"].append(
        {
            "predicate": "runtime_session_alice",
            "layer": 3,
            "truth_value": True,
            "rationale": "Declared scenario runtime assumption of active administrative session",
            "provenance_reference": "synthetic://assumptions/runtime_session_alice",
        }
    )

    query["bound_actions"].append(
        {
            "action_id": "action_blocked_attempt",
            "technique": "obtain_admin_execution_on_host",
            "technique_name": "obtain_admin_execution_on_host",
            "actor_id": ALICE_ID,
            "target_id": HOST_C0_ID,
            "edge_id": EDGE_DIRECT_ID,
            "referenced_work_unit_ids": ["w-auth-context"],
            "requires": ["actor_controlled_alice", "blocked_firewall_host"],
            "adds": ["admin_control_host"],
            "is_passive_closure": False,
        }
    )
    query["bound_actions"].append(
        {
            "action_id": "action_unknown_attempt",
            "technique": "obtain_admin_execution_on_host",
            "technique_name": "obtain_admin_execution_on_host",
            "actor_id": ALICE_ID,
            "target_id": HOST_C0_ID,
            "edge_id": EDGE_DIRECT_ID,
            "referenced_work_unit_ids": ["w-auth-context"],
            "requires": ["actor_controlled_alice", "unknown_service_health"],
            "adds": ["admin_control_host"],
            "is_passive_closure": False,
        }
    )
    query["bound_actions"].append(
        {
            "action_id": "action_unrated_effort_attempt",
            "technique": "obtain_admin_execution_on_host",
            "technique_name": "obtain_admin_execution_on_host",
            "actor_id": ALICE_ID,
            "target_id": HOST_C0_ID,
            "edge_id": EDGE_DIRECT_ID,
            "referenced_work_unit_ids": ["w-unrated-friction"],
            "requires": ["actor_controlled_alice", "admin_channel_alice_host"],
            "adds": ["admin_control_host"],
            "is_passive_closure": False,
        }
    )
    query["bound_actions"].append(
        {
            "action_id": "action_unrated_impact_attempt",
            "technique": "obtain_admin_execution_on_host",
            "technique_name": "obtain_admin_execution_on_host",
            "actor_id": ALICE_ID,
            "target_id": OTHERHOST_X_ID,
            "referenced_work_unit_ids": ["w-auth-otherhost", "w-direct-admin-otherhost"],
            "requires": ["actor_controlled_alice"],
            "adds": ["target_x_controlled", "admin_control_host"],
            "is_passive_closure": False,
        }
    )
    query["bound_actions"].append(
        {
            "action_id": "action_assumed_gate_attempt",
            "technique": "obtain_admin_execution_on_host",
            "technique_name": "obtain_admin_execution_on_host",
            "actor_id": ALICE_ID,
            "target_id": HOST_C0_ID,
            "edge_id": EDGE_DIRECT_ID,
            "referenced_work_unit_ids": ["w-auth-context", "w-direct-admin"],
            "requires": ["actor_controlled_alice", "runtime_session_alice"],
            "adds": ["admin_control_host"],
            "is_passive_closure": False,
        }
    )

    # Leave bounds table empty for unrated work units
    query["conditional_bounds_table"] = [
        {
            "prefix": ["w-auth-context"],
            "lower": "1/2",
            "upper": "1/2",
            "question_id": "q1",
            "outcome_action_id": "action_direct_admin",
            "technical_source": "synthetic://bounds/q1",
            "basis_category": "synthetic_fixture",
            "rationale": "auth context",
            "applicable_queries": [query_id],
        },
        {
            "prefix": ["w-auth-otherhost"],
            "lower": "1/2",
            "upper": "1/2",
            "question_id": "q_auth_otherhost",
            "outcome_action_id": "action_unrated_impact_attempt",
            "technical_source": "synthetic://bounds/q_auth_otherhost",
            "basis_category": "synthetic_fixture",
            "rationale": "authentication context for otherhost",
            "applicable_queries": [query_id],
        },
        {
            "prefix": ["w-auth-otherhost", "w-direct-admin-otherhost"],
            "lower": "1/2",
            "upper": "1/2",
            "question_id": "q_admin_otherhost",
            "outcome_action_id": "action_unrated_impact_attempt",
            "technical_source": "synthetic://bounds/q_admin_otherhost",
            "basis_category": "synthetic_fixture",
            "rationale": "administrative execution on otherhost",
            "applicable_queries": [query_id],
        },
    ]

    scope_binding = {
        "query_id": query_id,
        "scenario_id": "w4-two-routes-exact",
        "scenario_version": "1.0.0",
        "snapshot_id": SNAPSHOT_TWO_ROUTES,
        "work_boundary": "synthetic_two_routes",
        "horizon": "fixed_snapshot_window",
        "foothold_node_id": ALICE_ID,
    }

    candidates = [
        {
            "candidate_id": "cand_blocked_firewall",
            "target_asset_id": HOST_C0_ID,
            "bound_action_ids": ["action_blocked_attempt"],
            "scope_binding": scope_binding,
            "structural_routes": [
                {
                    "route_id": "route_blocked",
                    "node_ids": [ALICE_ID, HOST_C0_ID],
                    "edge_ids": [EDGE_DIRECT_ID],
                    "provenance_locators": [PROVENANCE_LOCATOR],
                }
            ],
        },
        {
            "candidate_id": "cand_unknown_service",
            "target_asset_id": HOST_C0_ID,
            "bound_action_ids": ["action_unknown_attempt"],
            "scope_binding": scope_binding,
            "structural_routes": [
                {
                    "route_id": "route_unknown",
                    "node_ids": [ALICE_ID, HOST_C0_ID],
                    "edge_ids": [EDGE_DIRECT_ID],
                    "provenance_locators": [PROVENANCE_LOCATOR],
                }
            ],
        },
        {
            "candidate_id": "cand_missing_likelihood_basis",
            "target_asset_id": HOST_C0_ID,
            "bound_action_ids": ["action_direct_admin"],
            "scope_binding": scope_binding,
            "structural_routes": [
                {
                    "route_id": "route_missing_likelihood",
                    "node_ids": [ALICE_ID, HOST_C0_ID],
                    "edge_ids": [EDGE_DIRECT_ID],
                    "provenance_locators": [PROVENANCE_LOCATOR],
                }
            ],
        },
        {
            "candidate_id": "cand_assumed_gate_unrated_basis",
            "target_asset_id": HOST_C0_ID,
            "bound_action_ids": ["action_assumed_gate_attempt"],
            "scope_binding": scope_binding,
            "structural_routes": [
                {
                    "route_id": "route_assumed_gate",
                    "node_ids": [ALICE_ID, HOST_C0_ID],
                    "edge_ids": [EDGE_DIRECT_ID],
                    "provenance_locators": [PROVENANCE_LOCATOR],
                }
            ],
        },
        {
            "candidate_id": "cand_unrated_effort",
            "target_asset_id": HOST_C0_ID,
            "bound_action_ids": ["action_unrated_effort_attempt"],
            "scope_binding": scope_binding,
            "structural_routes": [
                {
                    "route_id": "route_unrated_effort",
                    "node_ids": [ALICE_ID, HOST_C0_ID],
                    "edge_ids": [EDGE_DIRECT_ID],
                    "provenance_locators": [PROVENANCE_LOCATOR],
                }
            ],
        },
        {
            "candidate_id": "cand_unrated_impact",
            "target_asset_id": OTHERHOST_X_ID,
            "bound_action_ids": ["action_unrated_impact_attempt"],
            "scope_binding": {
                **scope_binding,
                "target_asset_id": OTHERHOST_X_ID,
            },
            "structural_routes": [
                {
                    "route_id": "route_unrated_impact",
                    "node_ids": [ALICE_ID],
                    "edge_ids": [],
                    "provenance_locators": [],
                    "action_step_indices": [],
                    "semantic_lineage": [
                        {
                            "step_index": 0,
                            "action_id": "action_unrated_impact_attempt",
                            "technique_id": "obtain_admin_execution_on_host",
                            "actor": ALICE_ID,
                            "source": ALICE_ID,
                            "target": OTHERHOST_X_ID,
                            "origin": "initial_attack_state",
                            "derived_from_step": None,
                            "status": "applicable",
                        }
                    ],
                }
            ],
        },
    ]

    return {
        "metadata": {
            "package_id": "package-week4-synthetic-a2-diagnostics",
            "version": "1.0.0",
            "evidence_class": "synthetic_test_only",
            "description": (
                "Synthetic fixture A2 verifying fail-closed diagnostic partitioning: blocked, "
                "unknown, likelihood_unrated, effort_unrated, and impact_unrated."
            ),
        },
        "query": query,
        "candidates": candidates,
    }


def build_week4_seamless_disposition() -> dict[str, Any]:
    """Construct Week 4 SEAMLESS reviewed parameter disposition record."""
    return {
        "schema_version": "1.0.0",
        "disposition_id": "seamless-week4-parameter-disposition",
        "version": "1.0.0",
        "created_at": "2026-10-07T00:00:00Z",
        "author": "Lolavine777 (TTS A)",
        "reviewer": "nairyuuu (TTS B)",
        "status": "reviewed_disposition",
        "evidence_class": "human_reviewed_disposition",
        "week3_reference": {
            "release_id": "seamless-week3-human-reviewed",
            "release_version": "1.0.0",
            "canonical_digest": (
                "sha256:20f67e8604f6399b5b360e412bb30bf898f4d788f13b69c08c78ef2df73d3358"
            ),
            "parameters_count": 21,
            "status": "unchanged_historical_baseline",
        },
        "reuse_criteria": {
            "description": (
                "Ratings from Week 3 closeout are only reused when all five dimensions are "
                "identical: exact binding, success event, context, operational horizon, "
                "and target asset."
            ),
            "enforcement": (
                "If any condition deviates or runtime mapping is unresolved, the candidate "
                "remains unrated. No synthetic or default values may be substituted."
            ),
        },
        "dispositions": [
            {
                "scope": "week3_source_a_candidate_1_lidia",
                "binding_status": "reusable_under_week3_scope",
                "week4_reuse_verdict": "reusable_if_query_unchanged",
                "parameters_reused": [
                    "WU_RESET_LIDIA",
                    "WU_ACTIVATE_LIDIA",
                    "WU_WINRM_DC_LIDIA",
                    "q1",
                    "q2",
                    "q3",
                ],
                "notes": "Valid only for original query-seamless-host-to-dc-v1 within 24h horizon.",
            },
            {
                "scope": "week3_source_a_candidate_2_josefa_ollie",
                "binding_status": "reusable_under_week3_scope",
                "week4_reuse_verdict": "reusable_if_query_unchanged",
                "parameters_reused": [
                    "WU_RESET_JOSEFA",
                    "WU_ACTIVATE_JOSEFA",
                    "WU_RESET_OLLIE",
                    "WU_ACTIVATE_OLLIE",
                    "WU_WINRM_DC_OLLIE",
                    "q4",
                    "q5",
                    "q6",
                    "q7",
                    "q8",
                ],
                "notes": "Valid only for original query-seamless-host-to-dc-v1 within 24h horizon.",
            },
            {
                "scope": "week3_source_b_candidate_ollie",
                "binding_status": "reusable_under_week3_scope",
                "week4_reuse_verdict": "reusable_if_query_unchanged",
                "parameters_reused": [
                    "WU_RESET_OLLIE_FROM_B",
                    "WU_ACTIVATE_OLLIE",
                    "WU_WINRM_DC_OLLIE",
                    "q9",
                    "q10",
                    "q11",
                ],
                "notes": (
                    "Valid only for original query-seamless-source-b-to-dc-v1 within 24h horizon."
                ),
            },
            {
                "scope": "week4_machine_source_queries_X_to_Y",
                "binding_status": "unresolved_mapping_pending_B",
                "week4_reuse_verdict": "unrated_pending_interface",
                "parameters_reused": [],
                "unrated_reason": (
                    "Machine source mapping (Computer X to Y) and host-level authentication "
                    "context are not yet bound in public query interface. No numeric rating "
                    "is claimed."
                ),
            },
            {
                "scope": "week4_extension_as_rep_roasting",
                "binding_status": "screened_without_recovery_data",
                "week4_reuse_verdict": "unrated_pending_empirical_basis",
                "parameters_reused": [],
                "unrated_reason": (
                    "AS-REP roasting request material is supported by dontreqpreauth field, but "
                    "password recovery within 24h horizon lacks empirical cracked rate data. "
                    "Reset qualifier from Week 3 must NOT be reused for offline hash cracking. "
                    "Remains explicitly unrated; neither P=0 nor P=1 nor synthetic defaults "
                    "are filled."
                ),
            },
            {
                "scope": "week4_extension_kerberoasting",
                "binding_status": "screened_without_recovery_data",
                "week4_reuse_verdict": "unrated_pending_empirical_basis",
                "parameters_reused": [],
                "unrated_reason": (
                    "SPN enumeration produces ticket material, but offline TGS cracking lacks "
                    "empirical dictionary calibration in SEAMLESS. Remains explicitly unrated."
                ),
            },
            {
                "scope": "week4_extension_rbcd",
                "binding_status": "screened_without_runtime_support",
                "week4_reuse_verdict": "unrated_pending_runtime_gates",
                "parameters_reused": [],
                "unrated_reason": (
                    "AddAllowedToAct DACL write is identified, but S4U2self/S4U2proxy delegation "
                    "and machine account acquisition runtime gates lack empirical basis. "
                    "Remains unrated."
                ),
            },
            {
                "scope": "week4_da_checkpoint_vs_asset_success",
                "binding_status": "distinct_events",
                "week4_reuse_verdict": "independent_evaluation",
                "parameters_reused": [],
                "unrated_reason": (
                    "Acquiring Domain Admin membership checkpoint is distinct from compromise "
                    "of DC asset. Impact consequence is bound to specific asset target, not "
                    "defaulted from DA role."
                ),
            },
        ],
    }


def compute_sha256(path: Path) -> str:
    """Compute standard SHA-256 hex digest of file bytes."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def generate_all_packages() -> dict[str, Path]:
    """Write all Week 4 rating packages to docs/research/ratings/week4/."""
    RATINGS_DIR.mkdir(parents=True, exist_ok=True)

    packages = {
        "synthetic-a2-e.json": build_package_a2_e(),
        "synthetic-a2-t.json": build_package_a2_t(),
        "synthetic-a2-ties.json": build_package_a2_ties(),
        "synthetic-a2-diagnostics.json": build_package_a2_diagnostics(),
        "week4-seamless-disposition.json": build_week4_seamless_disposition(),
    }

    paths: dict[str, Path] = {}
    for filename, data in packages.items():
        file_path = RATINGS_DIR / filename
        formatted = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
        file_path.write_text(formatted, encoding="utf-8")
        paths[filename] = file_path

    return paths


def evaluate_package(package_data: dict[str, Any]) -> dict[str, Any]:
    """Execute canonical PathRankingEngine on package query and candidates."""
    engine = PathRankingEngine(version="1.0.0")
    query = package_data["query"]
    candidates = package_data["candidates"]
    res = engine.evaluate(query_payload=query, candidates=candidates)
    return res["roundtrip_result"]


def generate_all_artifacts(ratings_dir: Path = RATINGS_DIR) -> dict[str, Any]:
    """Generate all Week 4 rating packages, evaluate them, and write results and manifests."""
    ratings_dir.mkdir(parents=True, exist_ok=True)
    paths = generate_all_packages()

    actual_results: dict[str, Any] = {}
    validation_records: list[dict[str, Any]] = []

    # 1. Evaluate Package E
    pkg_e = json.loads(paths["synthetic-a2-e.json"].read_text(encoding="utf-8"))
    res_e = evaluate_package(pkg_e)
    actual_results["synthetic-a2-e"] = res_e

    # Verify Ledger E invariants
    min_cand_e = res_e["min_effort_to_da_baseline"]["best_candidate_id"]
    min_val_e = res_e["min_effort_to_da_baseline"]["minimum_effort_value"]
    cand_d_e = res_e["eligible_candidates"]["cand_direct"]
    cand_md_e = res_e["eligible_candidates"]["cand_member_direct"]
    cand_mi_e = res_e["eligible_candidates"]["cand_member_inherited"]

    assert min_cand_e == "cand_member_inherited", (
        f"Expected cand_member_inherited, got {min_cand_e}"
    )
    assert min_val_e == 2, f"Expected min effort 2, got {min_val_e}"
    assert cand_d_e["effort"] == 5, f"Expected D effort 5, got {cand_d_e['effort']}"
    assert cand_md_e["effort"] == 5, f"Expected M/D effort 5, got {cand_md_e['effort']}"
    assert cand_mi_e["effort"] == 2, f"Expected M/I effort 2, got {cand_mi_e['effort']}"
    assert cand_md_e["effort"] == cand_d_e["effort"]
    assert cand_md_e["likelihood_interval"] == cand_d_e["likelihood_interval"] == ["2/5", "27/40"]
    assert cand_mi_e["likelihood_interval"] == ["12/25", "18/25"]
    assert set(res_e["pareto_frontier"]) == {
        "cand_direct",
        "cand_member_direct",
        "cand_member_inherited",
    }

    validation_records.append(
        {
            "package": "synthetic-a2-e.json",
            "status": "PASS",
            "description": (
                "Counter-structural Min-Effort: M/I has 2 steps but effort 2, beating D (effort 5)."
            ),
            "min_effort_optimum": "cand_member_inherited",
            "minimum_effort_value": 2,
            "pareto_frontier": res_e["pareto_frontier"],
            "anti_double_counting_verified": True,
        }
    )

    # 2. Evaluate Package T
    pkg_t = json.loads(paths["synthetic-a2-t.json"].read_text(encoding="utf-8"))
    res_t = evaluate_package(pkg_t)
    actual_results["synthetic-a2-t"] = res_t

    cand_d_t = res_t["eligible_candidates"]["cand_direct"]
    cand_md_t = res_t["eligible_candidates"]["cand_member_direct"]
    cand_mi_t = res_t["eligible_candidates"]["cand_member_inherited"]

    assert cand_d_t["effort"] == 2
    assert cand_md_t["effort"] == 2
    assert cand_mi_t["effort"] == 2
    assert res_t["min_effort_to_da_baseline"]["minimum_effort_value"] == 2
    assert set(res_t["pareto_frontier"]) == {
        "cand_direct",
        "cand_member_direct",
        "cand_member_inherited",
    }

    validation_records.append(
        {
            "package": "synthetic-a2-t.json",
            "status": "PASS",
            "description": (
                "Ledger T Min-Effort tie: all three programs achieve identical effort 2."
            ),
            "minimum_effort_value": 2,
            "all_efforts_equal": True,
            "pareto_frontier": res_t["pareto_frontier"],
        }
    )

    # 3. Evaluate Package Ties (ADR-0013 Section 4 point tie-break)
    pkg_ties = json.loads(paths["synthetic-a2-ties.json"].read_text(encoding="utf-8"))
    res_ties = evaluate_package(pkg_ties)
    actual_results["synthetic-a2-ties"] = res_ties

    cand_d_ties = res_ties["eligible_candidates"]["cand_direct"]
    cand_mi_ties = res_ties["eligible_candidates"]["cand_member_inherited"]

    assert cand_d_ties["likelihood_interval"] == ["1/2", "1/2"]
    assert cand_mi_ties["likelihood_interval"] == ["1/2", "1/2"]
    assert cand_d_ties["effort"] == 5
    assert cand_mi_ties["effort"] == 2
    assert res_ties["pareto_frontier"] == ["cand_member_inherited"]

    validation_records.append(
        {
            "package": "synthetic-a2-ties.json",
            "status": "PASS",
            "description": (
                "ADR-0013 Section 4 effort tie-break: M/I effort 2 strictly dominates D effort 5 "
                "under point P=1/2."
            ),
            "pareto_frontier": res_ties["pareto_frontier"],
            "effort_tie_break_verified": True,
        }
    )

    # 4. Evaluate Package Diagnostics (fail-closed partitioning)
    pkg_diag = json.loads(paths["synthetic-a2-diagnostics.json"].read_text(encoding="utf-8"))
    res_diag = evaluate_package(pkg_diag)
    actual_results["synthetic-a2-diagnostics"] = res_diag

    diag_map = res_diag["diagnostics"]
    assert "cand_blocked_firewall" in diag_map
    assert "blocked" in diag_map["cand_blocked_firewall"]["reasons"]
    assert "cand_unknown_service" in diag_map
    assert "unknown" in diag_map["cand_unknown_service"]["reasons"]
    assert "cand_missing_likelihood_basis" in diag_map
    assert "likelihood_unrated" in diag_map["cand_missing_likelihood_basis"]["reasons"]

    assert "cand_assumed_gate_unrated_basis" in diag_map
    cand_assumed = diag_map["cand_assumed_gate_unrated_basis"]["assessment"]
    assert cand_assumed["status"] == "feasible"
    assert cand_assumed["gates_evaluation"]["runtime_session_alice"] == "True"
    assert cand_assumed["likelihood_status"] == "unrated"
    assert cand_assumed["likelihood_interval"] is None
    assert "likelihood_unrated" in diag_map["cand_assumed_gate_unrated_basis"]["reasons"]

    assert "cand_unrated_impact" in diag_map
    cand_unrated_imp = diag_map["cand_unrated_impact"]["assessment"]
    assert cand_unrated_imp["impact_status"] == "unrated"
    assert cand_unrated_imp["impact"] is None
    assert cand_unrated_imp["effort"] == 5
    assert cand_unrated_imp["effort_status"] == "rated"
    assert cand_unrated_imp["likelihood_interval"] == ["1/4", "1/4"]
    assert cand_unrated_imp["likelihood_status"] == "rated"
    assert diag_map["cand_unrated_impact"]["reasons"] == ["impact_unrated"]

    assert "cand_unrated_effort" in diag_map
    cand_unrated_eff = diag_map["cand_unrated_effort"]["assessment"]
    assert cand_unrated_eff["effort_status"] == "unrated"
    assert cand_unrated_eff["effort"] is None
    assert "w-unrated-friction" in cand_unrated_eff["unrated_work_units"]

    assert res_diag["pareto_frontier"] == []

    min_eff_diag = res_diag["min_effort_to_da_baseline"]
    assert min_eff_diag["best_candidate_id"] == "cand_assumed_gate_unrated_basis"
    assert min_eff_diag["minimum_effort_value"] == 5
    assert min_eff_diag["associated_impact"] == "High"

    validation_records.append(
        {
            "package": "synthetic-a2-diagnostics.json",
            "status": "PASS",
            "description": (
                "Diagnostic partitioning: blocked, unknown, likelihood_unrated, effort_unrated, "
                "and impact_unrated."
            ),
            "diagnostics_candidates": list(diag_map.keys()),
            "fail_closed_verified": True,
        }
    )

    # Save actual results
    actual_path = ratings_dir / "actual-evaluator-results.json"
    actual_path.write_text(
        json.dumps(actual_results, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    # Generate validation summary
    summary_data = {
        "summary_id": "week4-scoring-validation-summary",
        "version": "1.0.0",
        "timestamp": "2026-10-07T00:00:00Z",
        "overall_status": "ALL_PASS",
        "author": "Lolavine777 (TTS A)",
        "evaluator_version": "1.0.0",
        "records": validation_records,
        "checksums": {
            filename: compute_sha256(ratings_dir / filename)
            for filename in [
                "synthetic-a2-e.json",
                "synthetic-a2-t.json",
                "synthetic-a2-ties.json",
                "synthetic-a2-diagnostics.json",
                "week4-seamless-disposition.json",
                "actual-evaluator-results.json",
            ]
        },
    }
    summary_path = ratings_dir / "validation-summary.json"
    summary_path.write_text(
        json.dumps(summary_data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    # Generate manifest.sha256
    manifest_lines = []
    for filename in sorted(
        [
            "synthetic-a2-e.json",
            "synthetic-a2-t.json",
            "synthetic-a2-ties.json",
            "synthetic-a2-diagnostics.json",
            "week4-seamless-disposition.json",
            "actual-evaluator-results.json",
            "validation-summary.json",
        ]
    ):
        fpath = ratings_dir / filename
        csum = compute_sha256(fpath)
        manifest_lines.append(f"{csum}  docs/research/ratings/week4/{filename}")

    manifest_path = ratings_dir / "manifest.sha256"
    manifest_path.write_text("\n".join(manifest_lines) + "\n", encoding="utf-8")

    return summary_data


def verify_existing_artifacts(ratings_dir: Path = RATINGS_DIR) -> dict[str, Any]:
    """Read-only verification of existing Week 4 artifacts on disk against evaluator.

    Does not modify, generate, or overwrite any artifact file.
    Validates manifest digests, re-evaluates input packages with canonical
    PathRankingEngine, deeply compares evaluated results against on-disk
    actual-evaluator-results.json, and validates all invariant assertions.
    """
    manifest_path = ratings_dir / "manifest.sha256"
    if not manifest_path.exists():
        raise FileNotFoundError(f"Manifest not found: {manifest_path}")

    # 1. Byte-level digest verification
    manifest_lines = [
        line.strip()
        for line in manifest_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(manifest_lines) >= 7, (
        f"Manifest must contain at least 7 entries, got {len(manifest_lines)}"
    )

    for line in manifest_lines:
        expected_digest, rel_path = line.split("  ", 1)
        if ratings_dir != RATINGS_DIR and (ratings_dir / Path(rel_path).name).exists():
            file_path = ratings_dir / Path(rel_path).name
        else:
            file_path = ROOT / rel_path
        if not file_path.exists():
            raise FileNotFoundError(f"File in manifest does not exist: {rel_path}")
        data = file_path.read_bytes()
        actual_digest = hashlib.sha256(data).hexdigest()
        if actual_digest != expected_digest and b"\r\n" in data:
            normalized = hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest()
            if normalized == expected_digest:
                actual_digest = normalized
        assert actual_digest == expected_digest, (
            f"Checksum mismatch for {rel_path}: expected {expected_digest}, got {actual_digest}"
        )

    # 2. Load on-disk actual-evaluator-results.json
    actual_results_path = ratings_dir / "actual-evaluator-results.json"
    if not actual_results_path.exists():
        raise FileNotFoundError(f"Saved actual results file not found: {actual_results_path}")
    saved_actual_results = json.loads(actual_results_path.read_text(encoding="utf-8"))

    # 3. Evaluate each on-disk package and compare deeply
    packages_to_check = [
        ("synthetic-a2-e.json", "synthetic-a2-e"),
        ("synthetic-a2-t.json", "synthetic-a2-t"),
        ("synthetic-a2-ties.json", "synthetic-a2-ties"),
        ("synthetic-a2-diagnostics.json", "synthetic-a2-diagnostics"),
    ]

    for pkg_filename, result_key in packages_to_check:
        pkg_file = ratings_dir / pkg_filename
        if not pkg_file.exists():
            raise FileNotFoundError(f"Package file not found: {pkg_file}")
        pkg_data = json.loads(pkg_file.read_text(encoding="utf-8"))
        fresh_result = evaluate_package(pkg_data)

        assert result_key in saved_actual_results, (
            f"Missing key {result_key!r} in saved actual results"
        )
        saved_result = saved_actual_results[result_key]

        # Deep comparison
        assert fresh_result["pareto_frontier"] == saved_result["pareto_frontier"], (
            f"{result_key}: Pareto frontier mismatch: "
            f"fresh={fresh_result['pareto_frontier']} vs saved={saved_result['pareto_frontier']}"
        )
        assert (
            fresh_result["min_effort_to_da_baseline"] == saved_result["min_effort_to_da_baseline"]
        ), (
            f"{result_key}: Min-effort baseline mismatch: "
            f"fresh={fresh_result['min_effort_to_da_baseline']} vs "
            f"saved={saved_result['min_effort_to_da_baseline']}"
        )
        assert fresh_result["eligible_candidates"] == saved_result["eligible_candidates"], (
            f"{result_key}: Eligible candidates mismatch"
        )
        assert fresh_result["diagnostics"] == saved_result["diagnostics"], (
            f"{result_key}: Diagnostics mismatch"
        )

    # 4. Check on-disk validation-summary.json
    summary_path = ratings_dir / "validation-summary.json"
    if not summary_path.exists():
        raise FileNotFoundError(f"Validation summary not found: {summary_path}")
    saved_summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert saved_summary["overall_status"] == "ALL_PASS", (
        f"Validation summary overall_status is not ALL_PASS: {saved_summary['overall_status']}"
    )

    # 5. Semantic invariants check (using saved/fresh results)
    res_e = saved_actual_results["synthetic-a2-e"]
    assert res_e["min_effort_to_da_baseline"]["best_candidate_id"] == "cand_member_inherited"
    assert res_e["min_effort_to_da_baseline"]["minimum_effort_value"] == 2
    cand_d_e = res_e["eligible_candidates"]["cand_direct"]
    cand_md_e = res_e["eligible_candidates"]["cand_member_direct"]
    cand_mi_e = res_e["eligible_candidates"]["cand_member_inherited"]
    assert cand_d_e["effort"] == 5
    assert cand_md_e["effort"] == 5
    assert cand_mi_e["effort"] == 2
    assert cand_md_e["effort"] == cand_d_e["effort"]
    assert cand_md_e["likelihood_interval"] == cand_d_e["likelihood_interval"] == ["2/5", "27/40"]
    assert cand_mi_e["likelihood_interval"] == ["12/25", "18/25"]
    assert set(res_e["pareto_frontier"]) == {
        "cand_direct",
        "cand_member_direct",
        "cand_member_inherited",
    }

    res_t = saved_actual_results["synthetic-a2-t"]
    assert res_t["eligible_candidates"]["cand_direct"]["effort"] == 2
    assert res_t["eligible_candidates"]["cand_member_direct"]["effort"] == 2
    assert res_t["eligible_candidates"]["cand_member_inherited"]["effort"] == 2
    assert res_t["min_effort_to_da_baseline"]["minimum_effort_value"] == 2
    assert set(res_t["pareto_frontier"]) == {
        "cand_direct",
        "cand_member_direct",
        "cand_member_inherited",
    }

    res_ties = saved_actual_results["synthetic-a2-ties"]
    assert res_ties["eligible_candidates"]["cand_direct"]["likelihood_interval"] == ["1/2", "1/2"]
    assert res_ties["eligible_candidates"]["cand_member_inherited"]["likelihood_interval"] == [
        "1/2",
        "1/2",
    ]
    assert res_ties["eligible_candidates"]["cand_direct"]["effort"] == 5
    assert res_ties["eligible_candidates"]["cand_member_inherited"]["effort"] == 2
    assert res_ties["pareto_frontier"] == ["cand_member_inherited"]

    res_diag = saved_actual_results["synthetic-a2-diagnostics"]
    diag_map = res_diag["diagnostics"]
    assert "cand_blocked_firewall" in diag_map
    assert "blocked" in diag_map["cand_blocked_firewall"]["reasons"]
    assert "cand_unknown_service" in diag_map
    assert "unknown" in diag_map["cand_unknown_service"]["reasons"]
    assert "cand_missing_likelihood_basis" in diag_map
    assert "likelihood_unrated" in diag_map["cand_missing_likelihood_basis"]["reasons"]

    assert "cand_assumed_gate_unrated_basis" in diag_map
    cand_assumed = diag_map["cand_assumed_gate_unrated_basis"]["assessment"]
    assert cand_assumed["status"] == "feasible"
    assert cand_assumed["gates_evaluation"]["runtime_session_alice"] == "True"
    assert cand_assumed["likelihood_status"] == "unrated"
    assert cand_assumed["likelihood_interval"] is None
    assert "likelihood_unrated" in diag_map["cand_assumed_gate_unrated_basis"]["reasons"]

    assert "cand_unrated_effort" in diag_map
    cand_unrated_eff = diag_map["cand_unrated_effort"]["assessment"]
    assert cand_unrated_eff["effort_status"] == "unrated"
    assert cand_unrated_eff["effort"] is None
    assert "w-unrated-friction" in cand_unrated_eff["unrated_work_units"]

    assert "cand_unrated_impact" in diag_map
    cand_unrated_imp = diag_map["cand_unrated_impact"]["assessment"]
    assert cand_unrated_imp["impact_status"] == "unrated"
    assert cand_unrated_imp["impact"] is None
    assert cand_unrated_imp["effort"] == 5
    assert cand_unrated_imp["effort_status"] == "rated"
    assert cand_unrated_imp["likelihood_interval"] == ["1/4", "1/4"]
    assert cand_unrated_imp["likelihood_status"] == "rated"
    assert diag_map["cand_unrated_impact"]["reasons"] == ["impact_unrated"]

    assert res_diag["pareto_frontier"] == []
    min_eff_diag = res_diag["min_effort_to_da_baseline"]
    assert min_eff_diag["best_candidate_id"] == "cand_assumed_gate_unrated_basis"
    assert min_eff_diag["minimum_effort_value"] == 5
    assert min_eff_diag["associated_impact"] == "High"

    return saved_summary


def run_full_verification() -> dict[str, Any]:
    """Preserved alias for verify_existing_artifacts()."""
    return verify_existing_artifacts()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Week 4 Scoring Evaluator and Verifier")
    parser.add_argument(
        "--verify",
        action="store_true",
        default=False,
        help="Run read-only verification of existing artifacts without modifying files (default)",
    )
    parser.add_argument(
        "--generate",
        "--update",
        dest="generate",
        action="store_true",
        default=False,
        help="Regenerate all packages, run evaluation, and update actual results and manifests",
    )
    args = parser.parse_args()

    if args.generate:
        summary = generate_all_artifacts()
        print("Generation and evaluation completed successfully:")
        print(json.dumps(summary, indent=2))
    else:
        summary = verify_existing_artifacts()
        print("Read-only verification completed successfully:")
        print(json.dumps(summary, indent=2))
