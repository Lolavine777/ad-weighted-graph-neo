"""Independent Conformance Tests for Engine Path Ranking (Specification v1.0.0).

Verifies normative behavior independently of research prototype scripts:
- Valid eligible candidates & risk partition.
- Gate evaluations: blocked, unknown, likelihood-unrated, impact-unrated.
- Mandatory authoritative predicate layering.
- Observation reconciliation and known-false hard veto.
- Layer 1 & Layer 2 immutability under action effects.
- Layer 3 runtime context advancement.
- First hitting time goal trimming and zero-step goal satisfaction.
- Verified 1-to-1 route trace synchronization upon suffix trimming.
- Lossless rational Fraction calculations and roundtrip serialization.
- Conservative Pareto frontier and narrow point-only effort tie-breaking.
- Non-point interval incomparability preservation.
- Min-Effort-to-DA separate query baseline.
- Upstream coverage and caps preservation.
- Issue #145 adapter boundary and CLI execution.
"""

from __future__ import annotations

import json
from copy import deepcopy
from fractions import Fraction
from pathlib import Path
from typing import Any

import pytest

from src.engine.ranking import (
    CompletenessScope,
    DuplicatePrefixError,
    MappingSyncError,
    PathRankingEngine,
    RankingValidationError,
    ScopedPreferenceVerdict,
    convert_path_result_to_candidate_envelope,
    execute_ranking_roundtrip,
    format_rational,
    parse_rational,
    scoped_frontier,
    scoped_preference,
)
from src.engine.ranking.cli import run_ranking_cli
from src.engine.ranking.orchestration import (
    evaluate_search_candidates,
    generate_and_evaluate_attack_paths,
)

DUMMY_SNAPSHOT = "sha256:" + "a" * 64
FOOTHOLD_SID = "S-1-5-21-3623811015-3361044348-30300820-1001"
DC_TARGET_SID = "S-1-5-21-3623811015-3361044348-30300820-1000"
SERVER_TARGET_SID = "S-1-5-21-3623811015-3361044348-30300820-2000"
DUMMY_EDGE_1 = "sha256:" + "1" * 64
DUMMY_EDGE_2 = "sha256:" + "2" * 64
DUMMY_EDGE_3 = "sha256:" + "3" * 64
DUMMY_EDGE_4 = "sha256:" + "4" * 64


def build_base_query() -> dict[str, Any]:
    """Build a standard contract-compliant PathRankingQuery dictionary."""
    return {
        "query_metadata": {
            "query_id": "query-20261001-test-001",
            "version": "1.0.0",
            "scenario_id": "scenario-corp-test",
            "scenario_version": "1.0.0",
            "snapshot_id": DUMMY_SNAPSHOT,
            "evaluation_mode": "scenario",
            "work_boundary": "corp_boundary",
            "foothold_node_id": FOOTHOLD_SID,
            "target_goal": {
                "goal_id": "S2",
                "description": "Domain Admin control",
                "required_predicates": ["target_controlled", "da_entitlement_active"],
                "target_asset_id": DC_TARGET_SID,
                "success_event": "domain_controller_full_compromise",
            },
            "horizon": "business_hours_72h",
            "active_work_budget": 10,
        },
        "facts_ledger": {
            "predicate_layers": {
                "structural_genericall": 1,
                "replication_authorization": 1,
                "member_of_group": 1,
                "smb_signing_enabled": 2,
                "target_enabled": 2,
                "session_present": 3,
                "password_policy_satisfied": 3,
                "directory_write_available": 3,
                "target_controlled": 3,
                "da_entitlement_active": 3,
            },
            "observed_facts": [
                {
                    "predicate": "structural_genericall",
                    "layer": 1,
                    "truth_value": True,
                    "provenance_reference": "prov:ad:acl:001",
                },
                {"predicate": "target_enabled", "layer": 2, "truth_value": True},
            ],
            "false_facts": [],
            "assumed_facts": [
                {
                    "predicate": "session_present",
                    "layer": 3,
                    "truth_value": True,
                    "rationale": "Active admin session present during business hours",
                },
                {
                    "predicate": "password_policy_satisfied",
                    "layer": 3,
                    "truth_value": True,
                    "rationale": "Entropy policy satisfied",
                },
            ],
            "unknown_facts": [],
        },
        "bound_actions": [
            {
                "action_id": "act_reset_pwd",
                "technique_name": "genericall_reset_password",
                "actor_id": FOOTHOLD_SID,
                "target_id": DC_TARGET_SID,
                "requires": ["structural_genericall", "target_enabled"],
                "adds": ["directory_write_available"],
                "referenced_work_unit_ids": ["unit_reset"],
                "is_passive_closure": False,
                "edge_id": DUMMY_EDGE_1,
            },
            {
                "action_id": "act_activate_da",
                "technique_name": "activate_domain_admin",
                "actor_id": FOOTHOLD_SID,
                "target_id": DC_TARGET_SID,
                "requires": ["directory_write_available", "session_present"],
                "adds": ["target_controlled", "da_entitlement_active"],
                "referenced_work_unit_ids": ["unit_activate"],
                "is_passive_closure": False,
                "edge_id": DUMMY_EDGE_2,
            },
        ],
        "work_units_ledger": {
            "unit_reset": {
                "work_unit_id": "unit_reset",
                "rating_status": "rated",
                "overlap_state": "independent",
                "t1": 1,
                "t2": 2,
                "computed_cost": 1,
            },
            "unit_activate": {
                "work_unit_id": "unit_activate",
                "rating_status": "rated",
                "overlap_state": "independent",
                "t1": 2,
                "t2": 2,
                "computed_cost": 2,
            },
        },
        "conditional_bounds_table": [
            {"prefix": ["unit_reset"], "lower": "8/10", "upper": "9/10"},
            {"prefix": ["unit_reset", "unit_activate"], "lower": "7/10", "upper": "8/10"},
        ],
        "target_impact_assessments": {
            DC_TARGET_SID: {
                "target_asset_id": DC_TARGET_SID,
                "success_event": "domain_controller_full_compromise",
                "rating_status": "rated",
                "consequence_rating": "Critical",
                "business_rationale": "Full domain compromise",
            }
        },
    }


def build_candidate_envelope(
    candidate_id: str = "cand_01",
    target_asset_id: str = DC_TARGET_SID,
    action_ids: list[str] | None = None,
    routes: list[dict[str, Any]] | None = None,
    scope_binding: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a standard candidate envelope."""
    if action_ids is None:
        action_ids = ["act_reset_pwd", "act_activate_da"]
    if routes is None:
        routes = [
            {
                "route_id": f"route_{candidate_id}",
                "node_ids": [FOOTHOLD_SID, DC_TARGET_SID, DC_TARGET_SID],
                "edge_ids": [DUMMY_EDGE_1, DUMMY_EDGE_2],
                "provenance_locators": ["loc:001", "loc:002"],
            }
        ]
    if scope_binding is None:
        scope_binding = {
            "query_id": "query-20261001-test-001",
            "scenario_id": "scenario-corp-test",
            "scenario_version": "1.0.0",
            "snapshot_id": DUMMY_SNAPSHOT,
            "work_boundary": "corp_boundary",
            "horizon": "business_hours_72h",
            "foothold_node_id": FOOTHOLD_SID,
        }
    return {
        "candidate_id": candidate_id,
        "scope_binding": scope_binding,
        "target_asset_id": target_asset_id,
        "bound_action_ids": action_ids,
        "structural_routes": routes,
    }


# ==============================================================================
# 32 Mandatory Conformance Tests
# ==============================================================================


def test_conformance_01_valid_eligible_candidate():
    """1. Valid eligible candidate: reaches goal, exact likelihood and effort."""
    query = build_base_query()
    cand = build_candidate_envelope("cand_valid")
    res = execute_ranking_roundtrip(query, [cand])

    assert "cand_valid" in res["result_payload"]["eligible_candidates"]
    assert res["result_payload"]["pareto_frontier"] == ["cand_valid"]
    assessment = res["result_payload"]["eligible_candidates"]["cand_valid"]
    assert assessment["status"] == "feasible"
    assert assessment["effort"] == 3  # 1 + 2
    # Exact Fraction interval: [8/10 * 7/10, 9/10 * 8/10] = [56/100, 72/100] = [14/25, 18/25]
    assert assessment["likelihood_interval"] == (Fraction(14, 25), Fraction(18, 25))
    assert assessment["impact"] == "Critical"


def test_conformance_02_blocked_prerequisite():
    """2. Blocked prerequisite: observed false fact blocks candidate."""
    query = build_base_query()
    query["facts_ledger"]["false_facts"].append(
        {"predicate": "target_enabled", "layer": 2, "truth_value": False}
    )
    query["facts_ledger"]["observed_facts"] = [
        f for f in query["facts_ledger"]["observed_facts"] if f["predicate"] != "target_enabled"
    ]
    cand = build_candidate_envelope("cand_blocked")
    res = execute_ranking_roundtrip(query, [cand])

    assert "cand_blocked" in res["result_payload"]["diagnostics"]
    diag = res["result_payload"]["diagnostics"]["cand_blocked"]
    assert "blocked" in diag["reasons"]
    assert "likelihood_unrated" in diag["reasons"]
    assert diag["assessment"]["status"] == "blocked"
    assert diag["assessment"]["likelihood_interval"] is None
    assert diag["assessment"]["effort"] is None


def test_conformance_03_unknown_prerequisite():
    """3. Unknown prerequisite: missing fact leaves gate unknown."""
    query = build_base_query()
    # Remove session_present assumption
    query["facts_ledger"]["assumed_facts"] = []
    cand = build_candidate_envelope("cand_unknown")
    res = execute_ranking_roundtrip(query, [cand])

    assert "cand_unknown" in res["result_payload"]["diagnostics"]
    diag = res["result_payload"]["diagnostics"]["cand_unknown"]
    assert "unknown" in diag["reasons"]
    assert "likelihood_unrated" in diag["reasons"]
    assert diag["assessment"]["status"] == "unknown"


def test_conformance_04_likelihood_unrated():
    """4. Likelihood unrated: candidate feasible but prefix missing from bounds table."""
    query = build_base_query()
    query["conditional_bounds_table"] = [
        {"prefix": ["unit_reset"], "lower": "8/10", "upper": "9/10"}
    ]  # Missing ["unit_reset", "unit_activate"]
    cand = build_candidate_envelope("cand_missing_bounds")
    res = execute_ranking_roundtrip(query, [cand])

    diag = res["result_payload"]["diagnostics"]["cand_missing_bounds"]
    assert diag["reasons"] == ["likelihood_unrated"]
    assert diag["assessment"]["status"] == "feasible"
    assert diag["assessment"]["likelihood_interval"] is None


def test_conformance_05_impact_unrated():
    """5. Impact unrated: target asset unrated produces impact_unrated diagnostic."""
    query = build_base_query()
    query["target_impact_assessments"][DC_TARGET_SID] = {
        "target_asset_id": DC_TARGET_SID,
        "success_event": "domain_controller_full_compromise",
        "rating_status": "unrated",
        "consequence_rating": None,
        "missing_basis_reasons": ["unrated_target_asset"],
    }
    cand = build_candidate_envelope("cand_unrated_impact")
    res = execute_ranking_roundtrip(query, [cand])

    diag = res["result_payload"]["diagnostics"]["cand_unrated_impact"]
    assert diag["reasons"] == ["impact_unrated"]
    assert diag["assessment"]["status"] == "feasible"
    assert diag["assessment"]["impact"] is None


def test_conformance_06_missing_authoritative_layer_fails_validation():
    """6. Missing authoritative layer for any referenced predicate must fail closed."""
    query = build_base_query()
    # Add undeclared predicate to action requires
    query["bound_actions"][0]["requires"].append("unclassified_predicate")
    cand = build_candidate_envelope("cand_bad_pred")
    with pytest.raises(RankingValidationError) as exc_info:
        execute_ranking_roundtrip(query, [cand])
    assert "Missing authoritative layer classification" in str(exc_info.value)


def test_conformance_07_contradictory_telemetry_reconciliation():
    """7. Contradictory telemetry resolves to Unknown (contradictory_telemetry)."""
    query = build_base_query()
    query["facts_ledger"]["observed_facts"].append(
        {"predicate": "target_enabled", "layer": 2, "truth_value": False}
    )
    cand = build_candidate_envelope("cand_conflict")
    res = execute_ranking_roundtrip(query, [cand])

    diag = res["result_payload"]["diagnostics"]["cand_conflict"]
    assert "unknown" in diag["reasons"]
    resolved = res["decoded_query"]["resolved_facts"]["target_enabled"]
    assert resolved["disposition"] == "contradictory_telemetry"


def test_conformance_08_layer_1_immutability_under_action_adds():
    """8. Layer 1 immutability: action effects cannot mutate Layer 1 authorization."""
    query = build_base_query()
    # Remove structural_genericall observation so it is Unknown
    query["facts_ledger"]["observed_facts"] = [
        f
        for f in query["facts_ledger"]["observed_facts"]
        if f["predicate"] != "structural_genericall"
    ]
    # Add dummy action attempting to add structural_genericall
    query["bound_actions"].insert(
        0,
        {
            "action_id": "act_fake_grant",
            "technique_name": "fake_grant",
            "actor_id": FOOTHOLD_SID,
            "target_id": DC_TARGET_SID,
            "requires": [],
            "adds": ["structural_genericall"],  # Attempted mutation of Layer 1
            "referenced_work_unit_ids": ["unit_reset"],
            "is_passive_closure": False,
            "edge_id": DUMMY_EDGE_3,
        },
    )
    cand = build_candidate_envelope(
        "cand_layer1_mutation",
        action_ids=["act_fake_grant", "act_reset_pwd", "act_activate_da"],
        routes=[
            {
                "route_id": "r1",
                "node_ids": [FOOTHOLD_SID, DC_TARGET_SID, DC_TARGET_SID, DC_TARGET_SID],
                "edge_ids": [DUMMY_EDGE_3, DUMMY_EDGE_1, DUMMY_EDGE_2],
                "provenance_locators": ["loc:0", "loc:1", "loc:2"],
            }
        ],
    )
    res = execute_ranking_roundtrip(query, [cand])
    # The attempted adds of Layer 1 must be ignored, so act_reset_pwd is unknown/blocked
    diag = res["result_payload"]["diagnostics"]["cand_layer1_mutation"]
    assert "unknown" in diag["reasons"]


def test_conformance_09_layer_2_immutability_under_action_adds():
    """9. Layer 2 immutability: action effects cannot mutate Layer 2 host configuration."""
    query = build_base_query()
    query["facts_ledger"]["observed_facts"] = [
        f for f in query["facts_ledger"]["observed_facts"] if f["predicate"] != "target_enabled"
    ]
    # Action trying to add target_enabled (Layer 2)
    query["bound_actions"].insert(
        0,
        {
            "action_id": "act_fake_enable",
            "technique_name": "fake_enable",
            "actor_id": FOOTHOLD_SID,
            "target_id": DC_TARGET_SID,
            "requires": [],
            "adds": ["target_enabled"],
            "referenced_work_unit_ids": ["unit_reset"],
            "is_passive_closure": False,
            "edge_id": DUMMY_EDGE_3,
        },
    )
    cand = build_candidate_envelope(
        "cand_layer2_mutation",
        action_ids=["act_fake_enable", "act_reset_pwd", "act_activate_da"],
        routes=[
            {
                "route_id": "r1",
                "node_ids": [FOOTHOLD_SID, DC_TARGET_SID, DC_TARGET_SID, DC_TARGET_SID],
                "edge_ids": [DUMMY_EDGE_3, DUMMY_EDGE_1, DUMMY_EDGE_2],
                "provenance_locators": ["loc:0", "loc:1", "loc:2"],
            }
        ],
    )
    res = execute_ranking_roundtrip(query, [cand])
    diag = res["result_payload"]["diagnostics"]["cand_layer2_mutation"]
    assert "unknown" in diag["reasons"]


def test_conformance_10_layer_3_effect_updates_runtime_state():
    """10. Layer 3 effect updates: action adds of Layer 3 successfully advance state."""
    query = build_base_query()
    # act_reset_pwd adds directory_write_available (Layer 3), which act_activate_da requires
    cand = build_candidate_envelope("cand_l3_success")
    res = execute_ranking_roundtrip(query, [cand])
    assert "cand_l3_success" in res["result_payload"]["eligible_candidates"]


def test_conformance_11_known_false_hard_veto_overrides_assumptions():
    """11. Known-false veto overrides optimistic scenario assumptions."""
    query = build_base_query()
    # Observed false in false_facts
    query["facts_ledger"]["false_facts"].append(
        {"predicate": "session_present", "layer": 3, "truth_value": False}
    )
    # Even though assumed_facts has session_present: True
    cand = build_candidate_envelope("cand_veto")
    res = execute_ranking_roundtrip(query, [cand])

    diag = res["result_payload"]["diagnostics"]["cand_veto"]
    assert "blocked" in diag["reasons"]
    resolved = res["decoded_query"]["resolved_facts"]["session_present"]
    assert resolved["value"] == "False"
    assert resolved["disposition"] == "observed_false_veto"


def test_conformance_12_zero_step_goal_satisfaction():
    """12. Zero-step goal: target goal satisfied initially at step 0."""
    query = build_base_query()
    # Add goal predicates directly to observed facts so goal is met at step 0
    query["facts_ledger"]["observed_facts"].extend(
        [
            {"predicate": "target_controlled", "layer": 3, "truth_value": True},
            {"predicate": "da_entitlement_active", "layer": 3, "truth_value": True},
        ]
    )

    # If foothold is FOOTHOLD_SID and candidate targets DC_TARGET_SID with trimmed 0 actions,
    # it must be rejected because dc_sid is not reached by initial foothold!
    cand_unreachable = build_candidate_envelope(
        "cand_unreachable_0",
        target_asset_id=DC_TARGET_SID,
        action_ids=["act_reset_pwd", "act_activate_da"],
    )
    with pytest.raises(RankingValidationError) as exc:
        execute_ranking_roundtrip(query, [cand_unreachable])
    assert "is not reached by initial foothold" in str(exc.value)

    # When foothold IS DC_TARGET_SID and candidate targets DC_TARGET_SID:
    query["query_metadata"]["foothold_node_id"] = DC_TARGET_SID
    scope_dc = {
        "query_id": "query-20261001-test-001",
        "scenario_id": "scenario-corp-test",
        "scenario_version": "1.0.0",
        "snapshot_id": DUMMY_SNAPSHOT,
        "work_boundary": "corp_boundary",
        "horizon": "business_hours_72h",
        "foothold_node_id": DC_TARGET_SID,
    }
    cand_trimmed = {
        "candidate_id": "cand_zero_step_trimmed",
        "scope_binding": scope_dc,
        "target_asset_id": DC_TARGET_SID,
        "bound_action_ids": ["act_reset_pwd", "act_activate_da"],
        "structural_routes": [
            {
                "route_id": "r_zero",
                "node_ids": [DC_TARGET_SID, DC_TARGET_SID, DC_TARGET_SID],
                "edge_ids": [DUMMY_EDGE_1, DUMMY_EDGE_2],
                "provenance_locators": ["loc:1", "loc:2"],
            }
        ],
    }
    cand_empty = {
        "candidate_id": "cand_zero_step_empty",
        "scope_binding": scope_dc,
        "target_asset_id": DC_TARGET_SID,
        "bound_action_ids": [],
    }

    res = execute_ranking_roundtrip(query, [cand_trimmed, cand_empty])
    el = res["result_payload"]["eligible_candidates"]

    # Both trimmed and empty candidates succeed with bound_action_ids = [],
    # effort = 0, and likelihood = [1, 1]
    for cid in ("cand_zero_step_trimmed", "cand_zero_step_empty"):
        assessment = el[cid]
        assert assessment["bound_action_ids"] == []
        assert assessment["program"] == []
        assert assessment["nominal_effort"] == 0
        assert assessment["effort"] == 0
        assert assessment["likelihood_interval"] == (Fraction(1, 1), Fraction(1, 1))


def test_conformance_13_first_goal_hitting_and_suffix_trimming():
    """13. First-goal hitting: execution trims actions after goal is first satisfied."""
    query = build_base_query()
    # Change target goal so that directory_write_available alone satisfies it
    query["query_metadata"]["target_goal"]["required_predicates"] = ["directory_write_available"]
    cand = build_candidate_envelope("cand_trim")
    res = execute_ranking_roundtrip(query, [cand])

    assessment = res["result_payload"]["eligible_candidates"]["cand_trim"]
    # Only act_reset_pwd is kept, act_activate_da is trimmed
    assert assessment["bound_action_ids"] == ["act_reset_pwd"]
    assert assessment["program"] == ["unit_reset"]
    assert assessment["effort"] == 1
    # Route is trimmed to 1 edge
    routes = assessment["structural_routes"]
    assert len(routes[0]["edge_ids"]) == 1
    assert routes[0]["edge_ids"] == [DUMMY_EDGE_1]


def test_conformance_14_target_binding_mismatch_rejected():
    """14. Target binding mismatch between candidate and query must fail validation."""
    query = build_base_query()
    # Candidate targets SERVER_TARGET_SID while query goal requires DC_TARGET_SID
    query["target_impact_assessments"][SERVER_TARGET_SID] = {
        "target_asset_id": SERVER_TARGET_SID,
        "success_event": "domain_controller_full_compromise",
        "rating_status": "rated",
        "consequence_rating": "High",
    }
    cand = build_candidate_envelope("cand_bad_target", target_asset_id=SERVER_TARGET_SID)
    with pytest.raises(RankingValidationError) as exc:
        execute_ranking_roundtrip(query, [cand])
    assert "does not match target_goal target_asset_id" in str(exc.value)


def test_conformance_15_success_event_mismatch_rejected():
    """15. Success event mismatch between goal and assessment must fail validation."""
    query = build_base_query()
    query["target_impact_assessments"][DC_TARGET_SID]["success_event"] = "wrong_event"
    cand = build_candidate_envelope("cand_bad_event")
    with pytest.raises(RankingValidationError) as exc:
        execute_ranking_roundtrip(query, [cand])
    assert "does not match target_goal success_event" in str(exc.value)


def test_conformance_16_persistent_work_unit_deduplication():
    """16. Persistent work units are deduplicated across multiple actions."""
    query = build_base_query()
    # Both actions reference the same work unit "unit_reset"
    query["bound_actions"][1]["referenced_work_unit_ids"] = ["unit_reset"]
    cand = build_candidate_envelope("cand_dedup")
    res = execute_ranking_roundtrip(query, [cand])

    assessment = res["result_payload"]["eligible_candidates"]["cand_dedup"]
    assert assessment["program"] == ["unit_reset"]
    assert assessment["effort"] == 1  # Not 1 + 1 = 2


def test_conformance_17_shared_work_across_actions_not_double_counted():
    """17. Shared work units across steps in program are counted only once."""
    query = build_base_query()
    # Add a 3rd action that also references unit_reset
    query["bound_actions"].append(
        {
            "action_id": "act_extra",
            "technique_name": "extra_action",
            "actor_id": FOOTHOLD_SID,
            "target_id": DC_TARGET_SID,
            "requires": [],
            "adds": [],
            "referenced_work_unit_ids": ["unit_reset"],
            "is_passive_closure": False,
            "edge_id": DUMMY_EDGE_3,
        }
    )
    cand = build_candidate_envelope(
        "cand_shared",
        action_ids=["act_reset_pwd", "act_activate_da", "act_extra"],
        routes=[
            {
                "route_id": "r1",
                "node_ids": [FOOTHOLD_SID, DC_TARGET_SID, DC_TARGET_SID, DC_TARGET_SID],
                "edge_ids": [DUMMY_EDGE_1, DUMMY_EDGE_2, DUMMY_EDGE_3],
                "provenance_locators": ["loc:1", "loc:2", "loc:3"],
            }
        ],
    )
    res = execute_ranking_roundtrip(query, [cand])
    assessment = res["result_payload"]["eligible_candidates"]["cand_shared"]
    assert assessment["program"] == ["unit_reset", "unit_activate"]
    assert assessment["effort"] == 3


def test_conformance_18_unresolved_work_overlap_withholds_cost():
    """18. Unresolved work overlap keeps unit unrated and withholds effort."""
    query = build_base_query()
    query["work_units_ledger"]["unit_reset"] = {
        "work_unit_id": "unit_reset",
        "rating_status": "unrated",
        "overlap_state": "unresolved_overlap",
        "computed_cost": None,
    }
    cand = build_candidate_envelope("cand_unresolved")
    res = execute_ranking_roundtrip(query, [cand])

    assessment = res["result_payload"]["eligible_candidates"]["cand_unresolved"]
    assert assessment["nominal_effort"] is None
    assert assessment["effort"] is None
    assert assessment["effort_status"] == "unrated"
    assert "unit_reset" in assessment["unrated_work_units"]


def test_conformance_19_unrated_work_effort_preserves_incomparability():
    """19. Unrated work effort preserves incomparability on identical point likelihoods."""
    query = build_base_query()
    # Cand 1 has rated effort 3, point likelihood [6/10, 6/10]
    query["conditional_bounds_table"] = [
        {"prefix": ["unit_reset"], "lower": "6/10", "upper": "6/10"},
        {"prefix": ["unit_reset", "unit_activate"], "lower": "1/1", "upper": "1/1"},
    ]
    cand1 = build_candidate_envelope("cand_rated")
    # Cand 2 has unrated work unit
    query["work_units_ledger"]["unit_unrated"] = {
        "work_unit_id": "unit_unrated",
        "rating_status": "unrated",
        "overlap_state": "independent",
        "computed_cost": None,
    }
    query["bound_actions"].append(
        {
            "action_id": "act_unrated",
            "technique_name": "unrated_action",
            "actor_id": FOOTHOLD_SID,
            "target_id": DC_TARGET_SID,
            "requires": ["directory_write_available", "session_present"],
            "adds": ["target_controlled", "da_entitlement_active"],
            "referenced_work_unit_ids": ["unit_unrated"],
            "is_passive_closure": False,
            "edge_id": DUMMY_EDGE_2,
        }
    )
    query["conditional_bounds_table"].append(
        {"prefix": ["unit_reset", "unit_unrated"], "lower": "1/1", "upper": "1/1"}
    )
    cand2 = build_candidate_envelope("cand_unrated", action_ids=["act_reset_pwd", "act_unrated"])

    res = execute_ranking_roundtrip(query, [cand1, cand2])
    el = res["result_payload"]["eligible_candidates"]
    pref = scoped_preference(el["cand_rated"], el["cand_unrated"])
    assert pref == ScopedPreferenceVerdict.INCOMPARABLE


def test_conformance_20_exact_rational_serialization_roundtrip():
    """20. Rational serialization roundtrips losslessly without float rounding."""
    frac = Fraction(81, 125)
    formatted = format_rational(frac)
    assert formatted == "81/125"
    parsed = parse_rational(formatted)
    assert parsed == frac

    query = build_base_query()
    cand = build_candidate_envelope("cand_roundtrip")
    res = execute_ranking_roundtrip(query, [cand])
    encoded = res["encoded_json"]
    decoded_back = json.loads(encoded)
    interval = decoded_back["eligible_candidates"]["cand_roundtrip"]["likelihood_interval"]
    assert interval == ["14/25", "18/25"]


def test_conformance_21_deterministic_output_and_ordering():
    """21. Evaluation outputs and candidate ordering are strictly deterministic."""
    query = build_base_query()
    cands = [build_candidate_envelope(f"cand_{i}") for i in range(5)]
    results = [execute_ranking_roundtrip(query, cands)["encoded_json"] for _ in range(5)]
    for r in results[1:]:
        assert r == results[0]


def test_conformance_22_conservative_pareto_dominance():
    """22. Conservative Pareto dominance: Critical [0.8, 0.9] dominates High [0.1, 0.2]."""
    c_a = {
        "candidate_id": "A",
        "impact": "Critical",
        "likelihood_interval": (Fraction(8, 10), Fraction(9, 10)),
        "effort": 5,
        "status": "feasible",
    }
    c_b = {
        "candidate_id": "B",
        "impact": "High",
        "likelihood_interval": (Fraction(1, 10), Fraction(2, 10)),
        "effort": 2,
        "status": "feasible",
    }
    assert scoped_preference(c_a, c_b) == ScopedPreferenceVerdict.A
    assert scoped_preference(c_b, c_a) == ScopedPreferenceVerdict.B

    frontier_res = scoped_frontier({"A": c_a, "B": c_b})
    assert frontier_res["frontier"] == ["A"]


def test_conformance_23_overlapping_intervals_remain_incomparable():
    """23. Overlapping intervals on same impact remain incomparable."""
    c_1 = {
        "candidate_id": "C1",
        "impact": "High",
        "likelihood_interval": (Fraction(4, 10), Fraction(7, 10)),
        "effort": 3,
        "status": "feasible",
    }
    c_2 = {
        "candidate_id": "C2",
        "impact": "High",
        "likelihood_interval": (Fraction(5, 10), Fraction(8, 10)),
        "effort": 2,
        "status": "feasible",
    }
    assert scoped_preference(c_1, c_2) == ScopedPreferenceVerdict.INCOMPARABLE
    frontier_res = scoped_frontier({"C1": c_1, "C2": c_2})
    assert set(frontier_res["frontier"]) == {"C1", "C2"}


def test_conformance_24_exact_point_likelihood_effort_tiebreak():
    """24. Narrow effort tie-break applies when impact and exact point likelihood match."""
    c_cheap = {
        "candidate_id": "Cheap",
        "impact": "High",
        "likelihood_interval": (Fraction(6, 10), Fraction(6, 10)),
        "effort": 3,
        "effort_status": "rated",
        "status": "feasible",
    }
    c_expensive = {
        "candidate_id": "Expensive",
        "impact": "High",
        "likelihood_interval": (Fraction(6, 10), Fraction(6, 10)),
        "effort": 5,
        "effort_status": "rated",
        "status": "feasible",
    }
    assert scoped_preference(c_cheap, c_expensive) == ScopedPreferenceVerdict.A
    assert scoped_preference(c_expensive, c_cheap) == ScopedPreferenceVerdict.B

    frontier_res = scoped_frontier({"Cheap": c_cheap, "Expensive": c_expensive})
    assert frontier_res["frontier"] == ["Cheap"]


def test_conformance_25_no_effort_tiebreak_for_interval_likelihood():
    """25. No effort tie-break when likelihood is an interval (l < u)."""
    c_int1 = {
        "candidate_id": "Int1",
        "impact": "High",
        "likelihood_interval": (Fraction(5, 10), Fraction(7, 10)),
        "effort": 3,
        "status": "feasible",
    }
    c_int2 = {
        "candidate_id": "Int2",
        "impact": "High",
        "likelihood_interval": (Fraction(5, 10), Fraction(7, 10)),
        "effort": 5,
        "status": "feasible",
    }
    assert scoped_preference(c_int1, c_int2) == ScopedPreferenceVerdict.INCOMPARABLE
    frontier_res = scoped_frontier({"Int1": c_int1, "Int2": c_int2})
    assert set(frontier_res["frontier"]) == {"Int1", "Int2"}


def test_conformance_26_distinct_routes_with_identical_work_history():
    """26. Distinct structural routes are preserved independently from identical work history."""
    query = build_base_query()
    cand_1 = build_candidate_envelope(
        "cand_route_1",
        routes=[
            {
                "route_id": "route_alpha",
                "node_ids": [FOOTHOLD_SID, DC_TARGET_SID, DC_TARGET_SID],
                "edge_ids": [DUMMY_EDGE_1, DUMMY_EDGE_2],
                "provenance_locators": ["loc:alpha1", "loc:alpha2"],
            }
        ],
    )
    cand_2 = build_candidate_envelope(
        "cand_route_2",
        routes=[
            {
                "route_id": "route_beta",
                "node_ids": [FOOTHOLD_SID, DC_TARGET_SID, DC_TARGET_SID],
                "edge_ids": [DUMMY_EDGE_3, DUMMY_EDGE_2],
                "provenance_locators": ["loc:beta1", "loc:beta2"],
            }
        ],
    )
    res = execute_ranking_roundtrip(query, [cand_1, cand_2])
    el = res["result_payload"]["eligible_candidates"]
    assert el["cand_route_1"]["structural_routes"][0]["route_id"] == "route_alpha"
    assert el["cand_route_2"]["structural_routes"][0]["route_id"] == "route_beta"


def test_conformance_27_exact_edge_and_provenance_preservation():
    """27. Edge IDs and provenance locators are preserved losslessly in output."""
    query = build_base_query()
    cand = build_candidate_envelope("cand_prov")
    res = execute_ranking_roundtrip(query, [cand])
    routes = res["result_payload"]["eligible_candidates"]["cand_prov"]["structural_routes"]
    assert routes[0]["edge_ids"] == [DUMMY_EDGE_1, DUMMY_EDGE_2]
    assert routes[0]["provenance_locators"] == ["loc:001", "loc:002"]


def test_conformance_28_invalid_action_to_route_mapping_fails_safely():
    """28. Suffix trimming fails safely with MappingSyncError if 1-to-1 route mapping is broken."""
    query = build_base_query()
    query["query_metadata"]["target_goal"]["required_predicates"] = ["directory_write_available"]
    # Provide a route whose edge count does not match initial actions
    cand = build_candidate_envelope(
        "cand_bad_sync",
        routes=[
            {
                "route_id": "r_mismatch",
                "node_ids": [FOOTHOLD_SID, DC_TARGET_SID],
                "edge_ids": [DUMMY_EDGE_1],  # 1 edge, but 2 initial actions declared
                "provenance_locators": ["loc:1"],
            }
        ],
    )
    with pytest.raises(MappingSyncError) as exc:
        execute_ranking_roundtrip(query, [cand])
    assert "cannot safely synchronize structural_routes upon suffix trimming" in str(exc.value)


def test_conformance_29_unknown_target_asset_rejected():
    """29. Unknown target asset rejected: candidate with unassessed target is rejected."""
    query = build_base_query()
    # Candidate referencing unknown target asset
    cand = build_candidate_envelope(
        "cand_unknown_target", target_asset_id="S-1-5-21-999-999-999-999"
    )
    with pytest.raises(RankingValidationError):
        execute_ranking_roundtrip(query, [cand])


def test_conformance_30_caps_scope_and_truncation_preserved():
    """30. Upstream caps and truncation reasons are preserved and completeness_scope normalized."""
    query = build_base_query()
    cand = build_candidate_envelope("cand_trunc")
    upstream = {
        "is_truncated": True,
        "truncation_reasons": ["timeout_exceeded"],
        "caps_applied": {
            "max_active_work_budget": 5,
            "max_candidates": 100,
            "timeout_ms": 3000,
            "max_expansions": 500,
        },
        "completeness_scope": "exhaustive_within_scope",  # Must be normalized to partial_truncated
    }
    res = execute_ranking_roundtrip(query, [cand], upstream_coverage=upstream)
    meta = res["result_payload"]["search_metadata"]
    assert meta["is_truncated"] is True
    assert meta["truncation_reasons"] == ["timeout_exceeded"]
    assert meta["completeness_scope"] == CompletenessScope.PARTIAL_TRUNCATED
    assert meta["caps_applied"]["timeout_ms"] == 3000


def test_conformance_31_empty_candidate_set_does_not_claim_global_no_path():
    """31. Empty candidate set yields empty frontier and does not claim global no-path."""
    query = build_base_query()
    res = execute_ranking_roundtrip(query, [])
    assert res["result_payload"]["pareto_frontier"] == []
    baseline = res["result_payload"]["min_effort_to_da_baseline"]
    assert baseline["best_candidate_id"] is None
    assert "No feasible rated candidate found" in baseline["coverage_disclosure"]


def test_conformance_32_min_effort_to_da_separate_result():
    """32. Min-Effort-to-DA baseline is distinct and independent from Pareto frontier."""
    # Cheap candidate: Effort 1, Likelihood [0.2, 0.2]
    # Shared candidate: Effort 8, Likelihood [0.8, 0.8]
    # Both High impact
    c_cheap = {
        "candidate_id": "Cheap",
        "impact": "High",
        "likelihood_interval": (Fraction(2, 10), Fraction(2, 10)),
        "effort": 1,
        "effort_status": "rated",
        "status": "feasible",
    }
    c_shared = {
        "candidate_id": "Shared",
        "impact": "High",
        "likelihood_interval": (Fraction(8, 10), Fraction(8, 10)),
        "effort": 8,
        "effort_status": "rated",
        "status": "feasible",
    }
    frontier_res = scoped_frontier({"Cheap": c_cheap, "Shared": c_shared})
    # Shared dominates Cheap because 0.8 > 0.2
    assert frontier_res["frontier"] == ["Shared"]

    from src.engine.ranking.frontier import compute_min_effort_baseline

    baseline = compute_min_effort_baseline([c_cheap, c_shared], {"goal_id": "S2"}, False, [], "")
    assert baseline["best_candidate_id"] == "Cheap"
    assert baseline["minimum_effort_value"] == 1


# ==============================================================================
# Additional Tests: #145 Adapter Boundary & CLI Execution
# ==============================================================================


def test_conformance_33_adapter_145_path_result_conversion():
    """33. Convert #145 search PathResult into validated CandidateEnvelope."""

    class MockRequest:
        def __init__(self, technique_id: str):
            self.technique_id = technique_id

    class MockTransitionResult:
        def __init__(self, technique_id: str):
            self.request = MockRequest(technique_id)

    class MockStep:
        def __init__(self, technique_id: str, edge_id: str):
            self.result = MockTransitionResult(technique_id)
            self.edge_id = edge_id
            self.derived_from_step = None

    class MockPathResult:
        nodes = (FOOTHOLD_SID, DC_TARGET_SID, DC_TARGET_SID)
        edges = (
            {
                "id": DUMMY_EDGE_1,
                "source": FOOTHOLD_SID,
                "target": DC_TARGET_SID,
                "provenance": [
                    {
                        "raw_file": "synthetic://evidence_1.json",
                        "collector": "synthetic/1.0",
                        "timestamp": "2026-09-23T00:00:00Z",
                        "record_id": "loc:prov:001",
                        "evidence_type": "positive",
                        "timestamp_status": "observed",
                    }
                ],
            },
            {
                "id": DUMMY_EDGE_2,
                "source": DC_TARGET_SID,
                "target": DC_TARGET_SID,
                "provenance": [
                    {
                        "raw_file": "synthetic://evidence_2.json",
                        "collector": "synthetic/1.0",
                        "timestamp": "2026-09-23T00:00:00Z",
                        "record_id": "loc:prov:002",
                        "evidence_type": "positive",
                        "timestamp_status": "observed",
                    }
                ],
            },
        )
        transition_history = (
            MockStep("tech_reset", DUMMY_EDGE_1),
            MockStep("tech_activate", DUMMY_EDGE_2),
        )
        scenario_reference = "scenario-corp-test"

    query = build_base_query()
    mapping = {"tech_reset": "act_reset_pwd", "tech_activate": "act_activate_da"}
    envelope = convert_path_result_to_candidate_envelope(
        path_result=MockPathResult(),
        candidate_id="cand_from_145",
        target_asset_id=DC_TARGET_SID,
        query_metadata=query["query_metadata"],
        action_mapping=mapping,
    )
    assert envelope["candidate_id"] == "cand_from_145"
    assert envelope["scope_binding"]["query_id"] == "query-20261001-test-001"
    assert envelope["bound_action_ids"] == ["act_reset_pwd", "act_activate_da"]
    assert len(envelope["structural_routes"]) == 1
    assert envelope["structural_routes"][0]["edge_ids"] == [DUMMY_EDGE_1, DUMMY_EDGE_2]
    assert envelope["structural_routes"][0]["provenance_locators"] == [
        "loc:prov:001",
        "loc:prov:002",
    ]

    # Replay through engine
    res = execute_ranking_roundtrip(query, [envelope])
    assert "cand_from_145" in res["result_payload"]["eligible_candidates"]


def test_conformance_34_cli_execution(tmp_path: Path):
    """34. CLI execution via wire JSON input and output file."""
    query = build_base_query()
    cand = build_candidate_envelope("cand_cli")
    combined = {
        "query": query,
        "candidates": [cand],
    }
    input_file = tmp_path / "combined.json"
    output_file = tmp_path / "output.json"
    input_file.write_text(json.dumps(combined), encoding="utf-8")

    exit_code = run_ranking_cli(["--input", str(input_file), "--output", str(output_file)])
    assert exit_code == 0
    assert output_file.exists()

    result = json.loads(output_file.read_text(encoding="utf-8"))
    assert "cand_cli" in result["eligible_candidates"]
    assert result["pareto_frontier"] == ["cand_cli"]


def test_conformance_35_duplicate_prefix_error():
    """35. Duplicate prefix keys in bounds table must raise DuplicatePrefixError."""
    query = build_base_query()
    query["conditional_bounds_table"].append(
        {"prefix": ["unit_reset"], "lower": "1/2", "upper": "1/2"}
    )
    cand = build_candidate_envelope("cand_dup")
    with pytest.raises(DuplicatePrefixError):
        execute_ranking_roundtrip(query, [cand])


# ==============================================================================
# Specification v1.0.0 Section 5 Normative Worked Examples
# ==============================================================================


def test_conformance_spec_example_1_incomparability_tradeoff():
    """Spec Example 1: Critical with lower likelihood vs High with higher likelihood."""
    cand_a = {
        "candidate_id": "Candidate_A",
        "impact": "Critical",
        "program": ["prep_kerberoast", "crack_ticket"],
        "likelihood_interval": (Fraction("1/10"), Fraction("2/10")),
        "effort": 3,
        "status": "feasible",
    }
    cand_b = {
        "candidate_id": "Candidate_B",
        "impact": "High",
        "program": ["prep_session_hijack", "pivot_dc"],
        "likelihood_interval": (Fraction("8/10"), Fraction("9/10")),
        "effort": 3,
        "status": "feasible",
    }
    assert scoped_preference(cand_a, cand_b) == ScopedPreferenceVerdict.INCOMPARABLE
    assert scoped_preference(cand_b, cand_a) == ScopedPreferenceVerdict.INCOMPARABLE

    frontier_res = scoped_frontier({"Candidate_A": cand_a, "Candidate_B": cand_b})
    assert set(frontier_res["frontier"]) == {"Candidate_A", "Candidate_B"}
    assert frontier_res["diagnostics"] == {}


def test_conformance_spec_example_2_strict_dominance():
    """Spec Example 2: Critical strictly dominates High when likelihood is also higher."""
    cand_a = {
        "candidate_id": "Candidate_A",
        "impact": "Critical",
        "likelihood_interval": (Fraction("1/10"), Fraction("2/10")),
        "effort": 3,
        "status": "feasible",
    }
    cand_c = {
        "candidate_id": "Candidate_C",
        "impact": "High",
        "likelihood_interval": (Fraction("5/100"), Fraction("9/100")),
        "effort": 2,
        "status": "feasible",
    }
    assert scoped_preference(cand_a, cand_c) == ScopedPreferenceVerdict.A
    assert scoped_preference(cand_c, cand_a) == ScopedPreferenceVerdict.B

    frontier_res = scoped_frontier({"Candidate_A": cand_a, "Candidate_C": cand_c})
    assert frontier_res["frontier"] == ["Candidate_A"]


def test_conformance_spec_example_3_point_tie_with_effort_tiebreak():
    """Spec Example 3: Point-tie with effort breaks tie only when both are rated."""
    d1 = {
        "candidate_id": "Candidate_D1",
        "impact": "High",
        "likelihood_interval": (Fraction("6/10"), Fraction("6/10")),
        "effort": 3,
        "effort_status": "rated",
        "status": "feasible",
    }
    d2 = {
        "candidate_id": "Candidate_D2",
        "impact": "High",
        "likelihood_interval": (Fraction("6/10"), Fraction("6/10")),
        "effort": 5,
        "effort_status": "rated",
        "status": "feasible",
    }
    d3 = {
        "candidate_id": "Candidate_D3",
        "impact": "High",
        "likelihood_interval": (Fraction("6/10"), Fraction("6/10")),
        "effort": 3,
        "effort_status": "rated",
        "status": "feasible",
    }
    assert scoped_preference(d1, d2) == ScopedPreferenceVerdict.A
    assert scoped_preference(d1, d3) == ScopedPreferenceVerdict.TIE

    frontier_res = scoped_frontier({"Candidate_D1": d1, "Candidate_D2": d2, "Candidate_D3": d3})
    assert set(frontier_res["frontier"]) == {"Candidate_D1", "Candidate_D3"}


def test_conformance_spec_example_4_point_tie_unrated_effort():
    """Spec Example 4: Point-tie with unrated effort remains incomparable."""
    e1 = {
        "candidate_id": "Candidate_E1",
        "impact": "High",
        "likelihood_interval": (Fraction("6/10"), Fraction("6/10")),
        "effort": 3,
        "effort_status": "rated",
        "status": "feasible",
    }
    e2 = {
        "candidate_id": "Candidate_E2",
        "impact": "High",
        "likelihood_interval": (Fraction("6/10"), Fraction("6/10")),
        "effort": None,  # unrated
        "effort_status": "unrated",
        "status": "feasible",
    }
    assert scoped_preference(e1, e2) == ScopedPreferenceVerdict.INCOMPARABLE
    frontier_res = scoped_frontier({"Candidate_E1": e1, "Candidate_E2": e2})
    assert set(frontier_res["frontier"]) == {"Candidate_E1", "Candidate_E2"}


def test_conformance_spec_example_5_diagnostics_partitioning():
    """Spec Example 5: Partitioning diagnostics for blocked, unknown, and unrated candidates."""
    f1 = {
        "candidate_id": "F1",
        "status": "blocked",
        "likelihood_interval": None,
        "effort": None,
        "impact": "High",
        "diagnostic_reasons": ["blocked", "likelihood_unrated"],
    }
    f2 = {
        "candidate_id": "F2",
        "status": "unknown",
        "likelihood_interval": None,
        "effort": None,
        "impact": "High",
        "diagnostic_reasons": ["unknown", "likelihood_unrated"],
    }
    f3 = {
        "candidate_id": "F3",
        "status": "feasible",
        "likelihood_interval": None,
        "effort": 3,
        "impact": "High",
        "diagnostic_reasons": ["likelihood_unrated"],
    }
    f4 = {
        "candidate_id": "F4",
        "status": "feasible",
        "likelihood_interval": (Fraction("5/10"), Fraction("6/10")),
        "effort": 3,
        "impact": None,
        "diagnostic_reasons": ["impact_unrated"],
    }
    assert scoped_preference(f1, f2) == ScopedPreferenceVerdict.NOT_ELIGIBLE
    frontier_res = scoped_frontier({"F1": f1, "F2": f2, "F3": f3, "F4": f4})
    assert frontier_res["eligible"] == {}
    assert frontier_res["frontier"] == []
    assert set(frontier_res["diagnostics"].keys()) == {"F1", "F2", "F3", "F4"}
    assert frontier_res["diagnostics"]["F1"]["reasons"] == ["blocked", "likelihood_unrated"]
    assert frontier_res["diagnostics"]["F2"]["reasons"] == ["likelihood_unrated", "unknown"]
    assert frontier_res["diagnostics"]["F3"]["reasons"] == ["likelihood_unrated"]
    assert frontier_res["diagnostics"]["F4"]["reasons"] == ["impact_unrated"]


def test_conformance_spec_example_6_canonical_work_ledger_split_merged():
    """Spec Example 6: Split and Merged actions canonical work ledger packaging equivalence."""
    split_cand = {
        "candidate_id": "Candidate_Split",
        "impact": "High",
        "program": ["unit_reset", "unit_activate"],
        "likelihood_interval": (Fraction("12/25"), Fraction("63/100")),
        "effort": 3,
        "status": "feasible",
    }
    merged_cand = {
        "candidate_id": "Candidate_Merged",
        "impact": "High",
        "program": ["unit_reset", "unit_activate"],
        "likelihood_interval": (Fraction("12/25"), Fraction("63/100")),
        "effort": 3,
        "status": "feasible",
    }
    # Non-point intervals (l < u) remain incomparable
    assert scoped_preference(split_cand, merged_cand) == ScopedPreferenceVerdict.INCOMPARABLE
    frontier_res = scoped_frontier({"Candidate_Split": split_cand, "Candidate_Merged": merged_cand})
    assert set(frontier_res["frontier"]) == {"Candidate_Split", "Candidate_Merged"}


def test_conformance_spec_example_7_min_effort_to_da_vs_pareto_frontier():
    """Spec Example 7: Separation between Min-Effort-to-DA and the Pareto frontier."""
    cheap = {
        "candidate_id": "Candidate_Cheap",
        "impact": "High",
        "likelihood_interval": (Fraction("2/10"), Fraction("2/10")),
        "effort": 1,
        "effort_status": "rated",
        "status": "feasible",
    }
    shared = {
        "candidate_id": "Candidate_Shared",
        "impact": "High",
        "likelihood_interval": (Fraction("648/1000"), Fraction("648/1000")),
        "effort": 8,
        "effort_status": "rated",
        "status": "feasible",
    }
    frontier_res = scoped_frontier({"Candidate_Cheap": cheap, "Candidate_Shared": shared})
    # Shared dominates Cheap because 0.648 > 0.20 on likelihood
    assert frontier_res["frontier"] == ["Candidate_Shared"]

    from src.engine.ranking.frontier import compute_min_effort_baseline

    baseline = compute_min_effort_baseline(
        [cheap, shared], {"goal_id": "S2"}, False, [], "exhaustive_within_scope"
    )
    assert baseline["best_candidate_id"] == "Candidate_Cheap"
    assert baseline["minimum_effort_value"] == 1
    assert baseline["associated_likelihood_interval"] == (Fraction("2/10"), Fraction("2/10"))


def test_conformance_path_ranking_engine_class():
    """Verify PathRankingEngine OOP interface and version enforcement."""
    engine = PathRankingEngine(version="1.0.0")
    assert engine.version == "1.0.0"

    with pytest.raises(RankingValidationError):
        PathRankingEngine(version="2.0.0")

    query = build_base_query()
    cand = build_candidate_envelope("cand_oop")
    result = engine.evaluate(query, [cand])
    assert "cand_oop" in result["result_payload"]["eligible_candidates"]


# ==============================================================================
# Hardening Tests: Fixed Query Scope Binding
# ==============================================================================


def test_scope_binding_exact_match_passes():
    """Exact matching scope binding succeeds through validation and evaluation."""
    query = build_base_query()
    cand = build_candidate_envelope("cand_exact_scope")
    res = execute_ranking_roundtrip(query, [cand])
    assert "cand_exact_scope" in res["result_payload"]["eligible_candidates"]


def test_scope_binding_query_id_mismatch_rejected():
    """Candidate with mismatched query_id is rejected fail-closed."""
    query = build_base_query()
    scope = {
        "query_id": "query-DIFFERENT-999",
        "scenario_id": "scenario-corp-test",
        "scenario_version": "1.0.0",
        "snapshot_id": DUMMY_SNAPSHOT,
        "work_boundary": "corp_boundary",
        "horizon": "business_hours_72h",
        "foothold_node_id": FOOTHOLD_SID,
    }
    cand = build_candidate_envelope("cand_bad_qid", scope_binding=scope)
    with pytest.raises(RankingValidationError) as exc:
        execute_ranking_roundtrip(query, [cand])
    assert "scope_binding query_id mismatch" in str(exc.value)


def test_scope_binding_scenario_id_mismatch_rejected():
    """Candidate with mismatched scenario_id is rejected fail-closed."""
    query = build_base_query()
    scope = {
        "query_id": "query-20261001-test-001",
        "scenario_id": "scenario-OTHER-SCENARIO",
        "scenario_version": "1.0.0",
        "snapshot_id": DUMMY_SNAPSHOT,
        "work_boundary": "corp_boundary",
        "horizon": "business_hours_72h",
        "foothold_node_id": FOOTHOLD_SID,
    }
    cand = build_candidate_envelope("cand_bad_scen", scope_binding=scope)
    with pytest.raises(RankingValidationError) as exc:
        execute_ranking_roundtrip(query, [cand])
    assert "scope_binding scenario_id mismatch" in str(exc.value)


def test_scope_binding_scenario_version_mismatch_rejected():
    """Candidate with mismatched scenario_version is rejected fail-closed."""
    query = build_base_query()
    scope = {
        "query_id": "query-20261001-test-001",
        "scenario_id": "scenario-corp-test",
        "scenario_version": "2.0.0",
        "snapshot_id": DUMMY_SNAPSHOT,
        "work_boundary": "corp_boundary",
        "horizon": "business_hours_72h",
        "foothold_node_id": FOOTHOLD_SID,
    }
    cand = build_candidate_envelope("cand_bad_sver", scope_binding=scope)
    with pytest.raises(RankingValidationError) as exc:
        execute_ranking_roundtrip(query, [cand])
    assert "scope_binding scenario_version mismatch" in str(exc.value)


def test_scope_binding_snapshot_id_mismatch_rejected():
    """Candidate with mismatched snapshot_id is rejected fail-closed."""
    query = build_base_query()
    scope = {
        "query_id": "query-20261001-test-001",
        "scenario_id": "scenario-corp-test",
        "scenario_version": "1.0.0",
        "snapshot_id": "sha256:" + "b" * 64,
        "work_boundary": "corp_boundary",
        "horizon": "business_hours_72h",
        "foothold_node_id": FOOTHOLD_SID,
    }
    cand = build_candidate_envelope("cand_bad_snap", scope_binding=scope)
    with pytest.raises(RankingValidationError) as exc:
        execute_ranking_roundtrip(query, [cand])
    assert "scope_binding snapshot_id mismatch" in str(exc.value)


def test_scope_binding_work_boundary_mismatch_rejected():
    """Candidate with mismatched work_boundary is rejected fail-closed."""
    query = build_base_query()
    scope = {
        "query_id": "query-20261001-test-001",
        "scenario_id": "scenario-corp-test",
        "scenario_version": "1.0.0",
        "snapshot_id": DUMMY_SNAPSHOT,
        "work_boundary": "external_boundary",
        "horizon": "business_hours_72h",
        "foothold_node_id": FOOTHOLD_SID,
    }
    cand = build_candidate_envelope("cand_bad_boundary", scope_binding=scope)
    with pytest.raises(RankingValidationError) as exc:
        execute_ranking_roundtrip(query, [cand])
    assert "scope_binding work_boundary mismatch" in str(exc.value)


def test_scope_binding_horizon_mismatch_rejected():
    """Candidate with mismatched horizon is rejected fail-closed."""
    query = build_base_query()
    scope = {
        "query_id": "query-20261001-test-001",
        "scenario_id": "scenario-corp-test",
        "scenario_version": "1.0.0",
        "snapshot_id": DUMMY_SNAPSHOT,
        "work_boundary": "corp_boundary",
        "horizon": "after_hours_12h",
        "foothold_node_id": FOOTHOLD_SID,
    }
    cand = build_candidate_envelope("cand_bad_horizon", scope_binding=scope)
    with pytest.raises(RankingValidationError) as exc:
        execute_ranking_roundtrip(query, [cand])
    assert "scope_binding horizon mismatch" in str(exc.value)


def test_scope_binding_foothold_node_id_mismatch_rejected():
    """Candidate with mismatched foothold_node_id in scope binding is rejected fail-closed."""
    query = build_base_query()
    scope = {
        "query_id": "query-20261001-test-001",
        "scenario_id": "scenario-corp-test",
        "scenario_version": "1.0.0",
        "snapshot_id": DUMMY_SNAPSHOT,
        "work_boundary": "corp_boundary",
        "horizon": "business_hours_72h",
        "foothold_node_id": "S-1-5-21-3623811015-3361044348-30300820-9999",
    }
    cand = build_candidate_envelope("cand_bad_foothold", scope_binding=scope)
    with pytest.raises(RankingValidationError) as exc:
        execute_ranking_roundtrip(query, [cand])
    assert "scope_binding foothold_node_id mismatch" in str(exc.value)


def test_scope_binding_missing_scope_binding_rejected():
    """Candidate missing the scope_binding dictionary entirely is rejected fail-closed."""
    query = build_base_query()
    cand = build_candidate_envelope("cand_no_scope")
    del cand["scope_binding"]
    with pytest.raises(RankingValidationError) as exc:
        execute_ranking_roundtrip(query, [cand])
    assert "must specify an explicit 'scope_binding' dictionary" in str(exc.value)


def test_scope_binding_missing_required_field_rejected():
    """Candidate scope_binding missing a required field is rejected fail-closed."""
    query = build_base_query()
    scope = {
        "query_id": "query-20261001-test-001",
        "scenario_id": "scenario-corp-test",
        # missing scenario_version
        "snapshot_id": DUMMY_SNAPSHOT,
        "work_boundary": "corp_boundary",
        "horizon": "business_hours_72h",
        "foothold_node_id": FOOTHOLD_SID,
    }
    cand = build_candidate_envelope("cand_missing_field", scope_binding=scope)
    with pytest.raises(RankingValidationError) as exc:
        execute_ranking_roundtrip(query, [cand])
    assert "missing required field 'scenario_version'" in str(exc.value)


# ==============================================================================
# Hardening Tests: Duplicate and Contradictory Action / Work Unit Bindings
# ==============================================================================


def test_bound_actions_duplicate_action_id_rejected():
    """Duplicate action_id in bound_actions list raises RankingValidationError."""
    query = build_base_query()
    dup_action = dict(query["bound_actions"][0])
    query["bound_actions"].append(dup_action)
    cand = build_candidate_envelope("cand_dup_action")
    with pytest.raises(RankingValidationError) as exc:
        execute_ranking_roundtrip(query, [cand])
    assert "Duplicate action_id detected in bound_actions" in str(exc.value)


def test_bound_actions_conflicting_actor_aliases_rejected():
    """Contradictory actor_id vs source_node_id in bound_action raises RankingValidationError."""
    query = build_base_query()
    query["bound_actions"][0]["actor_id"] = FOOTHOLD_SID
    query["bound_actions"][0]["source_node_id"] = DC_TARGET_SID  # Conflicting!
    cand = build_candidate_envelope("cand_bad_actor")
    with pytest.raises(RankingValidationError) as exc:
        execute_ranking_roundtrip(query, [cand])
    assert "contradictory aliases: actor_id" in str(exc.value)


def test_bound_actions_conflicting_target_aliases_rejected():
    """Contradictory target_id vs target_node_id in bound_action raises RankingValidationError."""
    query = build_base_query()
    query["bound_actions"][0]["target_id"] = DC_TARGET_SID
    query["bound_actions"][0]["target_node_id"] = SERVER_TARGET_SID  # Conflicting!
    cand = build_candidate_envelope("cand_bad_tgt")
    with pytest.raises(RankingValidationError) as exc:
        execute_ranking_roundtrip(query, [cand])
    assert "contradictory aliases: target_id" in str(exc.value)


def test_bound_actions_conflicting_work_unit_aliases_rejected():
    """Contradictory referenced_work_unit_ids vs bound_work_units raises RankingValidationError."""
    query = build_base_query()
    query["bound_actions"][0]["referenced_work_unit_ids"] = ["unit_reset"]
    query["bound_actions"][0]["bound_work_units"] = ["unit_activate"]  # Conflicting!
    cand = build_candidate_envelope("cand_bad_units")
    with pytest.raises(RankingValidationError) as exc:
        execute_ranking_roundtrip(query, [cand])
    assert "contradictory aliases: referenced_work_unit_ids" in str(exc.value)


def test_work_units_conflicting_status_aliases_rejected():
    """Contradictory rating_status vs status in work unit raises RankingValidationError."""
    query = build_base_query()
    query["work_units_ledger"]["unit_reset"]["rating_status"] = "rated"
    query["work_units_ledger"]["unit_reset"]["status"] = "unrated"  # Conflicting!
    cand = build_candidate_envelope("cand_bad_wu_status")
    with pytest.raises(RankingValidationError) as exc:
        execute_ranking_roundtrip(query, [cand])
    assert "contradictory aliases: rating_status" in str(exc.value)


def test_work_units_conflicting_cost_aliases_rejected():
    """Contradictory effort_cost vs computed_cost in work unit raises RankingValidationError."""
    query = build_base_query()
    query["work_units_ledger"]["unit_reset"]["effort_cost"] = 1
    query["work_units_ledger"]["unit_reset"]["computed_cost"] = 2  # Conflicting!
    cand = build_candidate_envelope("cand_bad_cost")
    with pytest.raises(RankingValidationError) as exc:
        execute_ranking_roundtrip(query, [cand])
    assert "contradictory aliases: effort_cost" in str(exc.value)


# ==============================================================================
# Hardening Tests: Structural Route Auditability & Invariants
# ==============================================================================


def test_structural_routes_duplicate_route_id_rejected():
    """Duplicate route_id in same candidate envelope raises RankingValidationError."""
    query = build_base_query()
    route1 = {
        "route_id": "route_dup",
        "node_ids": [FOOTHOLD_SID, DC_TARGET_SID, DC_TARGET_SID],
        "edge_ids": [DUMMY_EDGE_1, DUMMY_EDGE_2],
        "provenance_locators": ["loc:1", "loc:2"],
    }
    route2 = dict(route1)
    cand = build_candidate_envelope("cand_dup_route", routes=[route1, route2])
    with pytest.raises(RankingValidationError) as exc:
        execute_ranking_roundtrip(query, [cand])
    assert "Duplicate route_id detected" in str(exc.value)


def test_structural_routes_missing_route_id_rejected():
    """Structural route with missing or empty route_id raises RankingValidationError."""
    query = build_base_query()
    route = {
        "route_id": "",
        "node_ids": [FOOTHOLD_SID, DC_TARGET_SID, DC_TARGET_SID],
        "edge_ids": [DUMMY_EDGE_1, DUMMY_EDGE_2],
        "provenance_locators": ["loc:1", "loc:2"],
    }
    cand = build_candidate_envelope("cand_empty_rid", routes=[route])
    with pytest.raises(RankingValidationError) as exc:
        execute_ranking_roundtrip(query, [cand])
    assert "route_id must be a non-empty string" in str(exc.value)


def test_structural_routes_edge_node_count_mismatch_rejected():
    """Structural route where len(node_ids) != len(edge_ids) + 1 raises RankingValidationError."""
    query = build_base_query()
    route = {
        "route_id": "r_mismatch_nodes",
        "node_ids": [FOOTHOLD_SID, DC_TARGET_SID],  # 2 nodes, but 2 edges requires 3 nodes!
        "edge_ids": [DUMMY_EDGE_1, DUMMY_EDGE_2],
        "provenance_locators": ["loc:1", "loc:2"],
    }
    cand = build_candidate_envelope("cand_bad_node_count", routes=[route])
    with pytest.raises(RankingValidationError) as exc:
        execute_ranking_roundtrip(query, [cand])
    assert "must be edge count (2) + 1" in str(exc.value)


def test_structural_routes_provenance_count_mismatch_rejected():
    """Structural route where len(provenance_locators) != len(edge_ids)
    raises RankingValidationError."""
    query = build_base_query()
    route = {
        "route_id": "r_mismatch_prov",
        "node_ids": [FOOTHOLD_SID, DC_TARGET_SID, DC_TARGET_SID],
        "edge_ids": [DUMMY_EDGE_1, DUMMY_EDGE_2],
        "provenance_locators": ["loc:1"],  # 1 locator for 2 edges!
    }
    cand = build_candidate_envelope("cand_bad_prov_count", routes=[route])
    with pytest.raises(RankingValidationError) as exc:
        execute_ranking_roundtrip(query, [cand])
    assert "provenance count (1) must match edge count (2)" in str(exc.value)


def test_structural_routes_invalid_edge_id_rejected():
    """Structural route with non-canonical edge_id raises RankingValidationError."""
    query = build_base_query()
    route = {
        "route_id": "r_bad_edge",
        "node_ids": [FOOTHOLD_SID, DC_TARGET_SID, DC_TARGET_SID],
        "edge_ids": ["edge:not_sha256", DUMMY_EDGE_2],
        "provenance_locators": ["loc:1", "loc:2"],
    }
    cand = build_candidate_envelope("cand_bad_eid", routes=[route])
    with pytest.raises(RankingValidationError) as exc:
        execute_ranking_roundtrip(query, [cand])
    assert "does not match ^sha256:[0-9a-f]{64}$" in str(exc.value)


def test_structural_routes_valid_zero_step_route_passes():
    """Zero-step candidate with node_ids=[foothold], edge_ids=[], provenance_locators=[] passes."""
    query = build_base_query()
    query["facts_ledger"]["observed_facts"].extend(
        [
            {"predicate": "target_controlled", "layer": 3, "truth_value": True},
            {"predicate": "da_entitlement_active", "layer": 3, "truth_value": True},
        ]
    )
    query["query_metadata"]["foothold_node_id"] = DC_TARGET_SID
    scope_dc = {
        "query_id": "query-20261001-test-001",
        "scenario_id": "scenario-corp-test",
        "scenario_version": "1.0.0",
        "snapshot_id": DUMMY_SNAPSHOT,
        "work_boundary": "corp_boundary",
        "horizon": "business_hours_72h",
        "foothold_node_id": DC_TARGET_SID,
    }
    cand_zero = {
        "candidate_id": "cand_zero_valid_route",
        "scope_binding": scope_dc,
        "target_asset_id": DC_TARGET_SID,
        "bound_action_ids": [],
        "structural_routes": [
            {
                "route_id": "r_zero_valid",
                "node_ids": [DC_TARGET_SID],
                "edge_ids": [],
                "provenance_locators": [],
            }
        ],
    }
    res = execute_ranking_roundtrip(query, [cand_zero])
    assert "cand_zero_valid_route" in res["result_payload"]["eligible_candidates"]


def test_structural_routes_missing_for_executable_candidate_rejected():
    """Candidate with executable actions but empty structural_routes
    raises RankingValidationError."""
    query = build_base_query()
    cand = build_candidate_envelope("cand_no_routes", routes=[])
    with pytest.raises(RankingValidationError) as exc:
        execute_ranking_roundtrip(query, [cand])
    assert "has executable action sequence" in str(exc.value)
    assert "no auditable structural_routes" in str(exc.value)


# ==============================================================================
# ==============================================================================
# Hardening Tests: #145 Adapter Boundary
# ==============================================================================


class _MockRequest:
    def __init__(
        self,
        technique_id: str,
        source: str | None = None,
        target: str | None = None,
    ):
        self.technique_id = technique_id
        self.source = source
        self.target = target


class _MockTechnique:
    def __init__(self, technique_id: str):
        self.id = technique_id


class _MockTransitionResult:
    def __init__(
        self,
        request: Any = None,
        technique: Any = None,
    ):
        self.request = request
        self.technique = technique


class _MockStep:
    def __init__(self, result: Any, edge_id: str | None, derived_from_step: int | None = None):
        self.result = result
        self.edge_id = edge_id
        self.derived_from_step = derived_from_step


def _canonical_edge(
    edge_id: str,
    loc: str = "loc:001",
    source: str = FOOTHOLD_SID,
    target: str = DC_TARGET_SID,
    provenance_records: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    prov = provenance_records or [
        {
            "raw_file": "synthetic://evidence.json",
            "collector": "synthetic/1.0",
            "timestamp": "2026-09-23T00:00:00Z",
            "record_id": loc,
            "evidence_type": "positive",
            "timestamp_status": "observed",
        }
    ]
    return {
        "id": edge_id,
        "source": source,
        "target": target,
        "provenance": prov,
    }


def test_adapter_145_request_technique_id_extracted():
    """Adapter extracts technique identifier from step.result.request.technique_id."""
    step = _MockStep(
        result=_MockTransitionResult(request=_MockRequest("tech_reset")),
        edge_id=DUMMY_EDGE_1,
    )

    class MockPathResult:
        nodes = (FOOTHOLD_SID, DC_TARGET_SID)
        edges = (_canonical_edge(DUMMY_EDGE_1, "loc:prov:001"),)
        transition_history = (step,)
        scenario_reference = "scenario-corp-test"

    query = build_base_query()
    envelope = convert_path_result_to_candidate_envelope(
        path_result=MockPathResult(),
        candidate_id="cand_adapter_req",
        target_asset_id=DC_TARGET_SID,
        query_metadata=query["query_metadata"],
        action_mapping={"tech_reset": "act_reset_pwd"},
    )
    assert envelope["bound_action_ids"] == ["act_reset_pwd"]
    assert envelope["structural_routes"][0]["provenance_locators"] == ["loc:prov:001"]


def test_adapter_145_technique_obj_id_fallback():
    """Adapter extracts technique identifier from step.result.technique.id when request absent."""
    step = _MockStep(
        result=_MockTransitionResult(request=None, technique=_MockTechnique("tech_reset")),
        edge_id=DUMMY_EDGE_1,
    )

    class MockPathResult:
        nodes = (FOOTHOLD_SID, DC_TARGET_SID)
        edges = (_canonical_edge(DUMMY_EDGE_1, "loc:prov:fallback"),)
        transition_history = (step,)
        scenario_reference = "scenario-corp-test"

    query = build_base_query()
    envelope = convert_path_result_to_candidate_envelope(
        path_result=MockPathResult(),
        candidate_id="cand_adapter_tech_obj",
        target_asset_id=DC_TARGET_SID,
        query_metadata=query["query_metadata"],
        action_mapping={"tech_reset": "act_reset_pwd"},
    )
    assert envelope["bound_action_ids"] == ["act_reset_pwd"]
    assert envelope["structural_routes"][0]["provenance_locators"] == ["loc:prov:fallback"]


def test_adapter_145_conflicting_technique_ids_rejected():
    """Adapter rejects step when request.technique_id conflicts with technique.id."""
    step = _MockStep(
        result=_MockTransitionResult(
            request=_MockRequest("tech_alpha"),
            technique=_MockTechnique("tech_beta"),
        ),
        edge_id=DUMMY_EDGE_1,
    )

    class MockPathResult:
        nodes = (FOOTHOLD_SID, DC_TARGET_SID)
        edges = (_canonical_edge(DUMMY_EDGE_1),)
        transition_history = (step,)
        scenario_reference = "scenario-corp-test"

    query = build_base_query()
    with pytest.raises(RankingValidationError) as exc:
        convert_path_result_to_candidate_envelope(
            path_result=MockPathResult(),
            candidate_id="cand_bad",
            target_asset_id=DC_TARGET_SID,
            query_metadata=query["query_metadata"],
            action_mapping={"tech_alpha": "act_reset_pwd", "tech_beta": "act_reset_pwd"},
        )
    assert "contradictory technique identifiers" in str(exc.value)


def test_adapter_145_missing_technique_id_rejected():
    """Adapter rejects transition step missing technique identifier fail-closed (no step_{idx})."""
    step = _MockStep(
        result=_MockTransitionResult(request=None, technique=None),
        edge_id=DUMMY_EDGE_1,
    )

    class MockPathResult:
        nodes = (FOOTHOLD_SID, DC_TARGET_SID)
        edges = (_canonical_edge(DUMMY_EDGE_1),)
        transition_history = (step,)
        scenario_reference = "scenario-corp-test"

    query = build_base_query()
    with pytest.raises(RankingValidationError) as exc:
        convert_path_result_to_candidate_envelope(
            path_result=MockPathResult(),
            candidate_id="cand_bad",
            target_asset_id=DC_TARGET_SID,
            query_metadata=query["query_metadata"],
            action_mapping={"tech": "act_reset_pwd"},
        )
    assert "missing required technique identifier" in str(exc.value)


def test_adapter_145_missing_action_mapping_rejected():
    """Adapter rejects unmapped technique_id fail-closed (no identity fallback)."""
    step = _MockStep(
        result=_MockTransitionResult(request=_MockRequest("unknown_unmapped_technique")),
        edge_id=DUMMY_EDGE_1,
    )

    class MockPathResult:
        nodes = (FOOTHOLD_SID, DC_TARGET_SID)
        edges = (_canonical_edge(DUMMY_EDGE_1),)
        transition_history = (step,)
        scenario_reference = "scenario-corp-test"

    query = build_base_query()
    with pytest.raises(RankingValidationError) as exc:
        convert_path_result_to_candidate_envelope(
            path_result=MockPathResult(),
            candidate_id="cand_bad",
            target_asset_id=DC_TARGET_SID,
            query_metadata=query["query_metadata"],
            action_mapping={"other_technique": "act_reset_pwd"},
        )
    assert "has no explicit mapping in action_mapping" in str(exc.value)


def test_adapter_145_edge_not_in_path_result_edges_rejected():
    """Adapter rejects step when edge_id is missing from PathResult.edges."""
    step = _MockStep(
        result=_MockTransitionResult(request=_MockRequest("tech_reset")),
        edge_id=DUMMY_EDGE_1,
    )

    class MockPathResult:
        nodes = (FOOTHOLD_SID, DC_TARGET_SID)
        edges = ()  # DUMMY_EDGE_1 is missing!
        transition_history = (step,)
        scenario_reference = "scenario-corp-test"

    query = build_base_query()
    with pytest.raises(RankingValidationError) as exc:
        convert_path_result_to_candidate_envelope(
            path_result=MockPathResult(),
            candidate_id="cand_edge_missing",
            target_asset_id=DC_TARGET_SID,
            query_metadata=query["query_metadata"],
            action_mapping={"tech_reset": "act_reset_pwd"},
        )
    assert "not found in PathResult.edges" in str(exc.value)


def test_adapter_145_conflicting_duplicate_edges_rejected():
    """Adapter rejects PathResult.edges containing conflicting duplicate edge records."""
    step = _MockStep(
        result=_MockTransitionResult(request=_MockRequest("tech_reset")),
        edge_id=DUMMY_EDGE_1,
    )
    edge_a = _canonical_edge(DUMMY_EDGE_1, "loc:A")
    edge_b = _canonical_edge(DUMMY_EDGE_1, "loc:B")

    class MockPathResult:
        nodes = (FOOTHOLD_SID, DC_TARGET_SID)
        edges = (edge_a, edge_b)
        transition_history = (step,)
        scenario_reference = "scenario-corp-test"

    query = build_base_query()
    with pytest.raises(RankingValidationError) as exc:
        convert_path_result_to_candidate_envelope(
            path_result=MockPathResult(),
            candidate_id="cand_dup_edge",
            target_asset_id=DC_TARGET_SID,
            query_metadata=query["query_metadata"],
            action_mapping={"tech_reset": "act_reset_pwd"},
        )
    assert "ambiguous conflicting duplicate records" in str(exc.value)


def test_adapter_145_actual_provenance_preserved():
    """Adapter preserves authentic upstream provenance locator losslessly."""
    step = _MockStep(
        result=_MockTransitionResult(request=_MockRequest("tech_reset")),
        edge_id=DUMMY_EDGE_1,
    )

    class MockPathResult:
        nodes = (FOOTHOLD_SID, DC_TARGET_SID)
        edges = (_canonical_edge(DUMMY_EDGE_1, "snapshot:ad:acl:reset_pwd_evidence_123"),)
        transition_history = (step,)
        scenario_reference = "scenario-corp-test"

    query = build_base_query()
    envelope = convert_path_result_to_candidate_envelope(
        path_result=MockPathResult(),
        candidate_id="cand_prov_preserved",
        target_asset_id=DC_TARGET_SID,
        query_metadata=query["query_metadata"],
        action_mapping={"tech_reset": "act_reset_pwd"},
    )
    assert envelope["structural_routes"][0]["provenance_locators"] == [
        "snapshot:ad:acl:reset_pwd_evidence_123"
    ]


def test_adapter_145_missing_provenance_rejected_no_fabrication():
    """Adapter refuses to fabricate synthetic telemetry provenance when upstream is missing."""
    step = _MockStep(
        result=_MockTransitionResult(request=_MockRequest("tech_reset")),
        edge_id=DUMMY_EDGE_1,
    )
    edge_no_prov = {
        "id": DUMMY_EDGE_1,
        "source": FOOTHOLD_SID,
        "target": DC_TARGET_SID,
        "provenance": [],
    }

    class MockPathResult:
        nodes = (FOOTHOLD_SID, DC_TARGET_SID)
        edges = (edge_no_prov,)
        transition_history = (step,)
        scenario_reference = "scenario-corp-test"

    query = build_base_query()
    with pytest.raises(RankingValidationError) as exc:
        convert_path_result_to_candidate_envelope(
            path_result=MockPathResult(),
            candidate_id="cand_no_prov",
            target_asset_id=DC_TARGET_SID,
            query_metadata=query["query_metadata"],
            action_mapping={"tech_reset": "act_reset_pwd"},
        )
    assert "lacks authentic usable provenance" in str(exc.value)
    assert "fabricating synthetic locators is disallowed" in str(exc.value)


def test_adapter_145_derived_step_requires_valid_origin_index():
    """Adapter rejects malformed derived transitions without an earlier origin step."""
    step = _MockStep(
        result=_MockTransitionResult(request=_MockRequest("tech_derived")),
        edge_id=None,
        derived_from_step=0,
    )

    class MockPathResult:
        nodes = (FOOTHOLD_SID, DC_TARGET_SID)
        edges = ()
        transition_history = (step,)
        scenario_reference = "scenario-corp-test"

    query = build_base_query()
    with pytest.raises(RankingValidationError) as exc:
        convert_path_result_to_candidate_envelope(
            path_result=MockPathResult(),
            candidate_id="cand_derived",
            target_asset_id=DC_TARGET_SID,
            query_metadata=query["query_metadata"],
            action_mapping={"tech_derived": "act_reset_pwd"},
        )
    assert "requires an earlier derived_from_step index" in str(exc.value)


def test_adapter_145_scenario_mismatch_rejected():
    """Adapter rejects PathResult whose scenario_reference does not match query scenario_id."""
    step = _MockStep(
        result=_MockTransitionResult(request=_MockRequest("tech_reset")),
        edge_id=DUMMY_EDGE_1,
    )

    class MockPathResult:
        nodes = (FOOTHOLD_SID, DC_TARGET_SID)
        edges = (_canonical_edge(DUMMY_EDGE_1),)
        transition_history = (step,)
        scenario_reference = "scenario-other-unrelated"

    query = build_base_query()
    with pytest.raises(RankingValidationError) as exc:
        convert_path_result_to_candidate_envelope(
            path_result=MockPathResult(),
            candidate_id="cand_scenario_mismatch",
            target_asset_id=DC_TARGET_SID,
            query_metadata=query["query_metadata"],
            action_mapping={"tech_reset": "act_reset_pwd"},
        )
    assert "Scenario reference mismatch" in str(exc.value)


def test_adapter_145_attaches_explicit_scope_binding():
    """Adapter strictly binds converted envelope to verified query_metadata scope."""
    step = _MockStep(
        result=_MockTransitionResult(request=_MockRequest("tech_reset")),
        edge_id=DUMMY_EDGE_1,
    )

    class MockPathResult:
        nodes = (FOOTHOLD_SID, DC_TARGET_SID)
        edges = (_canonical_edge(DUMMY_EDGE_1),)
        transition_history = (step,)
        scenario_reference = "scenario-corp-test"

    query = build_base_query()
    envelope = convert_path_result_to_candidate_envelope(
        path_result=MockPathResult(),
        candidate_id="cand_scoped",
        target_asset_id=DC_TARGET_SID,
        query_metadata=query["query_metadata"],
        action_mapping={"tech_reset": "act_reset_pwd"},
    )
    scope = envelope["scope_binding"]
    assert scope["query_id"] == "query-20261001-test-001"
    assert scope["scenario_id"] == "scenario-corp-test"
    assert scope["scenario_version"] == "1.0.0"
    assert scope["snapshot_id"] == DUMMY_SNAPSHOT
    assert scope["work_boundary"] == "corp_boundary"
    assert scope["horizon"] == "business_hours_72h"
    assert scope["foothold_node_id"] == FOOTHOLD_SID


# ==============================================================================
# Hardening Tests: Structural Route Endpoint Binding
# ==============================================================================


def test_structural_routes_valid_source_and_target_passes():
    """Valid structural route starting at foothold and ending at target passes."""
    query = build_base_query()
    route = {
        "route_id": "r_valid_endpoints",
        "node_ids": [FOOTHOLD_SID, DC_TARGET_SID, DC_TARGET_SID],
        "edge_ids": [DUMMY_EDGE_1, DUMMY_EDGE_2],
        "provenance_locators": ["loc:1", "loc:2"],
    }
    cand = build_candidate_envelope("cand_valid_endpoints", routes=[route])
    res = execute_ranking_roundtrip(query, [cand])
    assert "cand_valid_endpoints" in res["result_payload"]["eligible_candidates"]


def test_structural_routes_wrong_source_rejected():
    """Structural route starting at non-foothold node raises RankingValidationError."""
    query = build_base_query()
    route = {
        "route_id": "r_wrong_source",
        "node_ids": [SERVER_TARGET_SID, DC_TARGET_SID, DC_TARGET_SID],
        "edge_ids": [DUMMY_EDGE_1, DUMMY_EDGE_2],
        "provenance_locators": ["loc:1", "loc:2"],
    }
    cand = build_candidate_envelope("cand_bad_source", routes=[route])
    with pytest.raises(RankingValidationError) as exc:
        execute_ranking_roundtrip(query, [cand])
    assert "wrong route source" in str(exc.value)
    assert f"expected foothold '{FOOTHOLD_SID}'" in str(exc.value)


def test_structural_routes_wrong_target_rejected():
    """Structural route terminating at non-candidate-target node raises RankingValidationError."""
    query = build_base_query()
    route = {
        "route_id": "r_wrong_target",
        "node_ids": [FOOTHOLD_SID, DC_TARGET_SID, SERVER_TARGET_SID],
        "edge_ids": [DUMMY_EDGE_1, DUMMY_EDGE_2],
        "provenance_locators": ["loc:1", "loc:2"],
    }
    cand = build_candidate_envelope("cand_bad_target", routes=[route])
    with pytest.raises(RankingValidationError) as exc:
        execute_ranking_roundtrip(query, [cand])
    assert "wrong route target" in str(exc.value)
    assert f"expected target '{DC_TARGET_SID}'" in str(exc.value)


def test_structural_routes_multiple_routes_one_invalid_rejected():
    """Candidate with one valid route and one route with wrong endpoint is rejected."""
    query = build_base_query()
    valid_route = {
        "route_id": "r_valid",
        "node_ids": [FOOTHOLD_SID, DC_TARGET_SID, DC_TARGET_SID],
        "edge_ids": [DUMMY_EDGE_1, DUMMY_EDGE_2],
        "provenance_locators": ["loc:1", "loc:2"],
    }
    invalid_route = {
        "route_id": "r_invalid_endpoint",
        "node_ids": [FOOTHOLD_SID, DC_TARGET_SID, SERVER_TARGET_SID],
        "edge_ids": [DUMMY_EDGE_3, DUMMY_EDGE_2],
        "provenance_locators": ["loc:3", "loc:2"],
    }
    cand = build_candidate_envelope("cand_multi_one_bad", routes=[valid_route, invalid_route])
    with pytest.raises(RankingValidationError) as exc:
        execute_ranking_roundtrip(query, [cand])
    assert "wrong route target" in str(exc.value)


def test_structural_routes_multiple_routes_all_valid_passes():
    """Candidate with multiple auditable routes all matching foothold and target passes."""
    query = build_base_query()
    route_1 = {
        "route_id": "r_path_alpha",
        "node_ids": [FOOTHOLD_SID, DC_TARGET_SID, DC_TARGET_SID],
        "edge_ids": [DUMMY_EDGE_1, DUMMY_EDGE_2],
        "provenance_locators": ["loc:1", "loc:2"],
    }
    route_2 = {
        "route_id": "r_path_beta",
        "node_ids": [FOOTHOLD_SID, SERVER_TARGET_SID, DC_TARGET_SID],
        "edge_ids": [DUMMY_EDGE_3, DUMMY_EDGE_2],
        "provenance_locators": ["loc:3", "loc:2"],
    }
    cand = build_candidate_envelope("cand_multi_all_valid", routes=[route_1, route_2])
    res = execute_ranking_roundtrip(query, [cand])
    el = res["result_payload"]["eligible_candidates"]["cand_multi_all_valid"]
    assert len(el["structural_routes"]) == 2


# ==============================================================================
# Hardening Tests: Likelihood Prefix Traversal
# ==============================================================================


def test_likelihood_missing_early_prefix_leaves_program_unrated():
    """Missing prefix 1 while prefix 2 exists leaves entire program likelihood_unrated."""
    query = build_base_query()
    # conditional_bounds_table has only the 2-step prefix, missing the 1-step prefix!
    query["conditional_bounds_table"] = [
        {"prefix": ["unit_reset", "unit_activate"], "lower": "7/10", "upper": "8/10"}
    ]
    cand = build_candidate_envelope("cand_missing_prefix_1")
    res = execute_ranking_roundtrip(query, [cand])

    assert "cand_missing_prefix_1" in res["result_payload"]["diagnostics"]
    diag = res["result_payload"]["diagnostics"]["cand_missing_prefix_1"]
    assert "likelihood_unrated" in diag["reasons"]
    assert diag["assessment"]["status"] == "feasible"
    assert diag["assessment"]["likelihood_interval"] is None
    assert (
        "Withheld: missing conditional prefix bounds in table"
        in diag["assessment"]["likelihood_basis_summary"]
    )


# ==============================================================================
# Hardening Tests: Exact Transition ↔ Edge ↔ Route Segment & Full Provenance
# ==============================================================================


def test_adapter_145_multiple_provenance_records_preserved():
    """Canonical edge with multiple provenance records preserves all lineage without loss."""
    prov_records = [
        {
            "raw_file": "synthetic://collector-a/evidence_1.json",
            "collector": "synthetic/1.3",
            "timestamp": "2026-09-23T00:00:00Z",
            "record_id": "loc:prov:primary",
            "evidence_type": "positive",
            "timestamp_status": "observed",
        },
        {
            "raw_file": "synthetic://collector-b/evidence_2.json",
            "collector": "synthetic/1.3",
            "timestamp": "2026-09-23T00:05:00Z",
            "record_id": "loc:prov:secondary",
            "evidence_type": "positive",
            "timestamp_status": "observed",
        },
    ]

    step_1 = _MockStep(
        result=_MockTransitionResult(
            request=_MockRequest("tech_reset", source=FOOTHOLD_SID, target=DC_TARGET_SID)
        ),
        edge_id=DUMMY_EDGE_1,
    )
    step_2 = _MockStep(
        result=_MockTransitionResult(
            request=_MockRequest("tech_activate", source=DC_TARGET_SID, target=DC_TARGET_SID)
        ),
        edge_id=DUMMY_EDGE_2,
    )

    class MockPathResult:
        nodes = (FOOTHOLD_SID, DC_TARGET_SID, DC_TARGET_SID)
        edges = (
            _canonical_edge(
                DUMMY_EDGE_1,
                source=FOOTHOLD_SID,
                target=DC_TARGET_SID,
                provenance_records=prov_records,
            ),
            _canonical_edge(
                DUMMY_EDGE_2,
                loc="loc:prov:step2",
                source=DC_TARGET_SID,
                target=DC_TARGET_SID,
            ),
        )
        transition_history = (step_1, step_2)
        scenario_reference = "scenario-corp-test"

    query = build_base_query()
    envelope = convert_path_result_to_candidate_envelope(
        path_result=MockPathResult(),
        candidate_id="cand_multi_prov",
        target_asset_id=DC_TARGET_SID,
        query_metadata=query["query_metadata"],
        action_mapping={"tech_reset": "act_reset_pwd", "tech_activate": "act_activate_da"},
    )

    # 1. Auditable via delimited string in provenance_locators
    combined_locator = envelope["structural_routes"][0]["provenance_locators"][0]
    recovered_locators = combined_locator.split(";")
    assert len(recovered_locators) == 2
    assert "loc:prov:primary" in recovered_locators
    assert "loc:prov:secondary" in recovered_locators

    # 2. Explicit lineage in route
    assert envelope["structural_routes"][0]["provenance_lineage"][0] == [
        "loc:prov:primary",
        "loc:prov:secondary",
    ]

    # 3. Full raw records preserved with timestamp_status intact
    raw_records = envelope["structural_routes"][0]["edge_provenance_records"][0]
    assert len(raw_records) == 2
    assert raw_records[0]["timestamp_status"] == "observed"
    assert raw_records[1]["timestamp_status"] == "observed"
    assert raw_records[0]["collector"] == "synthetic/1.3"
    assert raw_records[1]["collector"] == "synthetic/1.3"

    # 4. Map on candidate envelope preserved
    assert len(envelope["edge_provenance_map"][DUMMY_EDGE_1]) == 2

    # 5. Successfully passes validation through the engine
    res = execute_ranking_roundtrip(query, [envelope])
    assert "cand_multi_prov" in res["result_payload"]["eligible_candidates"]


def test_adapter_145_edge_source_mismatch_rejected():
    """Adapter rejects transition step when edge source does not match route segment source."""
    step = _MockStep(
        result=_MockTransitionResult(request=_MockRequest("tech_reset")),
        edge_id=DUMMY_EDGE_1,
    )

    class MockPathResult:
        nodes = (FOOTHOLD_SID, DC_TARGET_SID)
        # Edge source is SERVER_TARGET_SID but route segment source is FOOTHOLD_SID!
        edges = (
            _canonical_edge(
                DUMMY_EDGE_1,
                source=SERVER_TARGET_SID,
                target=DC_TARGET_SID,
            ),
        )
        transition_history = (step,)
        scenario_reference = "scenario-corp-test"

    query = build_base_query()
    with pytest.raises(RankingValidationError) as exc:
        convert_path_result_to_candidate_envelope(
            path_result=MockPathResult(),
            candidate_id="cand_bad_src",
            target_asset_id=DC_TARGET_SID,
            query_metadata=query["query_metadata"],
            action_mapping={"tech_reset": "act_reset_pwd"},
        )
    assert "source mismatch" in str(exc.value)


def test_adapter_145_edge_target_mismatch_rejected():
    """Adapter rejects transition step when edge target does not match route segment target."""
    step = _MockStep(
        result=_MockTransitionResult(request=_MockRequest("tech_reset")),
        edge_id=DUMMY_EDGE_1,
    )

    class MockPathResult:
        nodes = (FOOTHOLD_SID, DC_TARGET_SID)
        # Edge target is SERVER_TARGET_SID but route segment target is DC_TARGET_SID!
        edges = (
            _canonical_edge(
                DUMMY_EDGE_1,
                source=FOOTHOLD_SID,
                target=SERVER_TARGET_SID,
            ),
        )
        transition_history = (step,)
        scenario_reference = "scenario-corp-test"

    query = build_base_query()
    with pytest.raises(RankingValidationError) as exc:
        convert_path_result_to_candidate_envelope(
            path_result=MockPathResult(),
            candidate_id="cand_bad_tgt",
            target_asset_id=DC_TARGET_SID,
            query_metadata=query["query_metadata"],
            action_mapping={"tech_reset": "act_reset_pwd"},
        )
    assert "target mismatch" in str(exc.value)


def test_adapter_145_transition_request_source_conflict_rejected():
    """Adapter rejects transition step when request.source contradicts canonical edge source."""
    step = _MockStep(
        result=_MockTransitionResult(
            request=_MockRequest("tech_reset", source=SERVER_TARGET_SID, target=DC_TARGET_SID)
        ),
        edge_id=DUMMY_EDGE_1,
    )

    class MockPathResult:
        nodes = (FOOTHOLD_SID, DC_TARGET_SID)
        edges = (
            _canonical_edge(
                DUMMY_EDGE_1,
                source=FOOTHOLD_SID,
                target=DC_TARGET_SID,
            ),
        )
        transition_history = (step,)
        scenario_reference = "scenario-corp-test"

    query = build_base_query()
    with pytest.raises(RankingValidationError) as exc:
        convert_path_result_to_candidate_envelope(
            path_result=MockPathResult(),
            candidate_id="cand_req_src_conflict",
            target_asset_id=DC_TARGET_SID,
            query_metadata=query["query_metadata"],
            action_mapping={"tech_reset": "act_reset_pwd"},
        )
    assert "request source" in str(exc.value)


def test_adapter_145_transition_request_target_conflict_rejected():
    """Adapter rejects transition step when request.target contradicts canonical edge target."""
    step = _MockStep(
        result=_MockTransitionResult(
            request=_MockRequest("tech_reset", source=FOOTHOLD_SID, target=SERVER_TARGET_SID)
        ),
        edge_id=DUMMY_EDGE_1,
    )

    class MockPathResult:
        nodes = (FOOTHOLD_SID, DC_TARGET_SID)
        edges = (
            _canonical_edge(
                DUMMY_EDGE_1,
                source=FOOTHOLD_SID,
                target=DC_TARGET_SID,
            ),
        )
        transition_history = (step,)
        scenario_reference = "scenario-corp-test"

    query = build_base_query()
    with pytest.raises(RankingValidationError) as exc:
        convert_path_result_to_candidate_envelope(
            path_result=MockPathResult(),
            candidate_id="cand_req_tgt_conflict",
            target_asset_id=DC_TARGET_SID,
            query_metadata=query["query_metadata"],
            action_mapping={"tech_reset": "act_reset_pwd"},
        )
    assert "request target" in str(exc.value)


def test_adapter_145_valid_exact_alignment_passes():
    """Step with matching request endpoints, canonical edge endpoints, and route segment passes."""
    step_1 = _MockStep(
        result=_MockTransitionResult(
            request=_MockRequest("tech_reset", source=FOOTHOLD_SID, target=DC_TARGET_SID)
        ),
        edge_id=DUMMY_EDGE_1,
    )
    step_2 = _MockStep(
        result=_MockTransitionResult(
            request=_MockRequest("tech_activate", source=DC_TARGET_SID, target=DC_TARGET_SID)
        ),
        edge_id=DUMMY_EDGE_2,
    )

    class MockPathResult:
        nodes = (FOOTHOLD_SID, DC_TARGET_SID, DC_TARGET_SID)
        edges = (
            _canonical_edge(
                DUMMY_EDGE_1,
                source=FOOTHOLD_SID,
                target=DC_TARGET_SID,
            ),
            _canonical_edge(
                DUMMY_EDGE_2,
                source=DC_TARGET_SID,
                target=DC_TARGET_SID,
            ),
        )
        transition_history = (step_1, step_2)
        scenario_reference = "scenario-corp-test"

    query = build_base_query()
    envelope = convert_path_result_to_candidate_envelope(
        path_result=MockPathResult(),
        candidate_id="cand_exact_ok",
        target_asset_id=DC_TARGET_SID,
        query_metadata=query["query_metadata"],
        action_mapping={"tech_reset": "act_reset_pwd", "tech_activate": "act_activate_da"},
    )
    assert envelope["candidate_id"] == "cand_exact_ok"
    res = execute_ranking_roundtrip(query, [envelope])
    assert "cand_exact_ok" in res["result_payload"]["eligible_candidates"]


def test_adapter_145_bound_action_declared_edge_id_matches_passes():
    """Adapter validates matching declared edge_id in bound_actions_catalog."""
    step = _MockStep(
        result=_MockTransitionResult(request=_MockRequest("tech_reset")),
        edge_id=DUMMY_EDGE_1,
    )

    class MockPathResult:
        nodes = (FOOTHOLD_SID, DC_TARGET_SID)
        edges = (
            _canonical_edge(
                DUMMY_EDGE_1,
                source=FOOTHOLD_SID,
                target=DC_TARGET_SID,
            ),
        )
        transition_history = (step,)
        scenario_reference = "scenario-corp-test"

    query = build_base_query()
    catalog = [{"action_id": "act_reset_pwd", "edge_id": DUMMY_EDGE_1}]
    envelope = convert_path_result_to_candidate_envelope(
        path_result=MockPathResult(),
        candidate_id="cand_action_match",
        target_asset_id=DC_TARGET_SID,
        query_metadata=query["query_metadata"],
        action_mapping={"tech_reset": "act_reset_pwd"},
        bound_actions_catalog=catalog,
    )
    assert envelope["bound_action_ids"] == ["act_reset_pwd"]


def test_adapter_145_bound_action_declared_edge_id_mismatch_rejected():
    """Adapter rejects step when bound_action declares an edge_id conflicting with step.edge_id."""
    step = _MockStep(
        result=_MockTransitionResult(request=_MockRequest("tech_reset")),
        edge_id=DUMMY_EDGE_1,
    )

    class MockPathResult:
        nodes = (FOOTHOLD_SID, DC_TARGET_SID)
        edges = (
            _canonical_edge(
                DUMMY_EDGE_1,
                source=FOOTHOLD_SID,
                target=DC_TARGET_SID,
            ),
        )
        transition_history = (step,)
        scenario_reference = "scenario-corp-test"

    query = build_base_query()
    catalog = [{"action_id": "act_reset_pwd", "edge_id": DUMMY_EDGE_2}]
    with pytest.raises(RankingValidationError) as exc:
        convert_path_result_to_candidate_envelope(
            path_result=MockPathResult(),
            candidate_id="cand_action_mismatch",
            target_asset_id=DC_TARGET_SID,
            query_metadata=query["query_metadata"],
            action_mapping={"tech_reset": "act_reset_pwd"},
            bound_actions_catalog=catalog,
        )
    assert "declared edge_id" in str(exc.value)


def test_conformance_regression_missing_prefix_followed_by_zero_upper_stays_unrated():
    """Regression: Missing prefix bounds followed by zero-upper bound must remain unrated.

    Contract rule: If ANY prefix along the candidate program is missing in the bounds table,
    the program must be assessed as likelihood_unrated (withheld). A subsequent prefix with
    upper == 0 must NOT flip likelihood_rated back to True.
    """
    query = build_base_query()
    # Program has 2 steps: ["unit_reset", "unit_activate"]
    # Prefix ["unit_reset"] is MISSING from bounds table
    # Prefix ["unit_reset", "unit_activate"] has upper == 0
    query["conditional_bounds_table"] = [
        {"prefix": ["unit_reset", "unit_activate"], "lower": "0/1", "upper": "0/1"},
    ]
    cand = build_candidate_envelope("cand_missing_prefix_zero_upper")
    res = execute_ranking_roundtrip(query, [cand])

    # Candidate must NOT be eligible with [0, 0] likelihood
    assert "cand_missing_prefix_zero_upper" not in res["result_payload"]["eligible_candidates"]
    assert "cand_missing_prefix_zero_upper" in res["result_payload"]["diagnostics"]

    diag = res["result_payload"]["diagnostics"]["cand_missing_prefix_zero_upper"]
    assert "likelihood_unrated" in diag["reasons"]
    assessment = diag["assessment"]
    assert assessment["likelihood_interval"] is None
    assert assessment["likelihood_status"] == "unrated"
    assert "likelihood_unrated" in assessment["diagnostic_reasons"]
    assert "missing conditional prefix bounds" in assessment["likelihood_basis_summary"]


def test_conformance_regression_suffix_trimming_synchronizes_provenance_lineage_and_records():
    """Regression: Suffix trimming must synchronize provenance_lineage and raw records.

    When actions are trimmed at goal first-hitting time, all parallel evidence vectors
    (provenance_locators, provenance_lineage, edge_provenance_records) must be sliced
    identically so that no dropped suffix evidence remains in the effective route trace.
    """
    query = build_base_query()
    # Set goal to be satisfied by the first action alone
    query["query_metadata"]["target_goal"]["required_predicates"] = ["directory_write_available"]

    rec_step1_a = {"collector": "col_1", "raw_id": "rec_001", "timestamp_status": "observed"}
    rec_step1_b = {"collector": "col_2", "raw_id": "rec_002", "timestamp_status": "observed"}
    rec_step2 = {"collector": "col_1", "raw_id": "rec_003", "timestamp_status": "observed"}

    route = {
        "route_id": "route_trim_lineage",
        "node_ids": [FOOTHOLD_SID, DC_TARGET_SID, DC_TARGET_SID],
        "edge_ids": [DUMMY_EDGE_1, DUMMY_EDGE_2],
        "provenance_locators": ["loc:1a;loc:1b", "loc:2"],
        "provenance_lineage": [["loc:1a", "loc:1b"], ["loc:2"]],
        "edge_provenance_records": [[rec_step1_a, rec_step1_b], [rec_step2]],
    }
    cand = build_candidate_envelope("cand_trim_prov", routes=[route])
    res = execute_ranking_roundtrip(query, [cand])

    assessment = res["result_payload"]["eligible_candidates"]["cand_trim_prov"]
    assert assessment["bound_action_ids"] == ["act_reset_pwd"]
    assert assessment["program"] == ["unit_reset"]

    trimmed_route = assessment["structural_routes"][0]
    # Suffix at step 2 must be trimmed from all evidence vectors
    assert len(trimmed_route["edge_ids"]) == 1
    assert trimmed_route["edge_ids"] == [DUMMY_EDGE_1]
    assert len(trimmed_route["node_ids"]) == 2
    assert trimmed_route["node_ids"] == [FOOTHOLD_SID, DC_TARGET_SID]
    assert trimmed_route["provenance_locators"] == ["loc:1a;loc:1b"]
    assert trimmed_route["provenance_lineage"] == [["loc:1a", "loc:1b"]]
    assert trimmed_route["edge_provenance_records"] == [[rec_step1_a, rec_step1_b]]

    # Also test mismatch detection before trimming: mismatched length fails safely
    route_mismatched = dict(route)
    route_mismatched["provenance_lineage"] = [["loc:1a"]]  # only 1 element instead of 2
    cand_mismatched = build_candidate_envelope("cand_mismatch_prov", routes=[route_mismatched])
    with pytest.raises(MappingSyncError) as exc:
        execute_ranking_roundtrip(query, [cand_mismatched])
    assert "provenance_lineage count" in str(exc.value)


def test_conformance_regression_scoped_preference_requires_both_effort_status_rated():
    """Regression: scoped_preference effort tie-break requires effort_status == 'rated'.

    ADR-0013 Section 4: Effort tie-break only applies when candidates have identical impact,
    identical point likelihood, AND both have effort_status == 'rated'. If either candidate
    has effort_status == 'unrated', 'ineligible', or missing, verdict must be INCOMPARABLE.
    """
    cand_rated_low = {
        "candidate_id": "Cand_Rated_Low",
        "impact": "High",
        "likelihood_interval": (Fraction(6, 10), Fraction(6, 10)),
        "effort": 3,
        "effort_status": "rated",
        "status": "feasible",
    }
    cand_rated_high = {
        "candidate_id": "Cand_Rated_High",
        "impact": "High",
        "likelihood_interval": (Fraction(6, 10), Fraction(6, 10)),
        "effort": 5,
        "effort_status": "rated",
        "status": "feasible",
    }
    cand_unrated_status = {
        "candidate_id": "Cand_Unrated_Status",
        "impact": "High",
        "likelihood_interval": (Fraction(6, 10), Fraction(6, 10)),
        "effort": 5,
        "effort_status": "unrated",
        "status": "feasible",
    }
    cand_missing_status = {
        "candidate_id": "Cand_Missing_Status",
        "impact": "High",
        "likelihood_interval": (Fraction(6, 10), Fraction(6, 10)),
        "effort": 5,
        "status": "feasible",
    }
    cand_ineligible_status = {
        "candidate_id": "Cand_Ineligible_Status",
        "impact": "High",
        "likelihood_interval": (Fraction(6, 10), Fraction(6, 10)),
        "effort": 5,
        "effort_status": "ineligible",
        "status": "feasible",
    }

    # When both are rated: effort tie-break works
    assert scoped_preference(cand_rated_low, cand_rated_high) == ScopedPreferenceVerdict.A
    assert scoped_preference(cand_rated_high, cand_rated_low) == ScopedPreferenceVerdict.B

    # When one is unrated effort_status: must be INCOMPARABLE even if effort is populated
    assert (
        scoped_preference(cand_rated_low, cand_unrated_status)
        == ScopedPreferenceVerdict.INCOMPARABLE
    )
    assert (
        scoped_preference(cand_unrated_status, cand_rated_low)
        == ScopedPreferenceVerdict.INCOMPARABLE
    )

    # When one is missing effort_status key: must be INCOMPARABLE
    assert (
        scoped_preference(cand_rated_low, cand_missing_status)
        == ScopedPreferenceVerdict.INCOMPARABLE
    )
    assert (
        scoped_preference(cand_missing_status, cand_rated_low)
        == ScopedPreferenceVerdict.INCOMPARABLE
    )

    # When one is ineligible effort_status: must be INCOMPARABLE
    assert (
        scoped_preference(cand_rated_low, cand_ineligible_status)
        == ScopedPreferenceVerdict.INCOMPARABLE
    )
    assert (
        scoped_preference(cand_ineligible_status, cand_rated_low)
        == ScopedPreferenceVerdict.INCOMPARABLE
    )


def test_conformance_regression_bound_actions_is_passive_closure_non_boolean_rejected():
    """Regression: is_passive_closure must be strict boolean, not coerced from strings or numbers.

    Passing string 'false' or numeric 0/1 must raise RankingValidationError to prevent malformed
    active actions from becoming passive closures.
    """
    query = build_base_query()
    cand = build_candidate_envelope("cand_passive_test")

    # Non-boolean string "false"
    query["bound_actions"][0]["is_passive_closure"] = "false"
    with pytest.raises(RankingValidationError) as exc:
        execute_ranking_roundtrip(query, [cand])
    assert "is_passive_closure must be a boolean" in str(exc.value)

    # Non-boolean integer 1
    query["bound_actions"][0]["is_passive_closure"] = 1
    with pytest.raises(RankingValidationError) as exc:
        execute_ranking_roundtrip(query, [cand])
    assert "is_passive_closure must be a boolean" in str(exc.value)


def test_conformance_regression_bound_actions_missing_actor_or_target_rejected():
    """Regression: bound_actions entry missing required actor_id or target_id must be rejected.

    Bound Actions Catalog requires actions to bind to canonical actor_id and target_id.
    """
    cand = build_candidate_envelope("cand_actor_target_test")

    # Missing actor_id
    query_no_actor = build_base_query()
    del query_no_actor["bound_actions"][0]["actor_id"]
    query_no_actor["bound_actions"][0].pop("source_node_id", None)
    with pytest.raises(RankingValidationError) as exc:
        execute_ranking_roundtrip(query_no_actor, [cand])
    assert "missing required actor_id" in str(exc.value)

    # Missing target_id
    query_no_target = build_base_query()
    del query_no_target["bound_actions"][0]["target_id"]
    query_no_target["bound_actions"][0].pop("target_node_id", None)
    with pytest.raises(RankingValidationError) as exc:
        execute_ranking_roundtrip(query_no_target, [cand])
    assert "missing required target_id" in str(exc.value)


def test_conformance_regression_work_units_unsupported_overlap_states_rejected():
    """Regression: work unit overlap_state outside Spec 1.0.0-draft enums must fail closed.

    Specification 1.0.0-draft only permits 'independent' and 'unresolved_overlap'.
    Enums outside this specification ('distinct_work', 'composite_subsumed') must be rejected.
    """
    cand = build_candidate_envelope("cand_overlap_test")

    # distinct_work is not in Spec 1.0.0-draft
    query_distinct = build_base_query()
    query_distinct["work_units_ledger"]["unit_reset"]["overlap_state"] = "distinct_work"
    with pytest.raises(RankingValidationError) as exc:
        execute_ranking_roundtrip(query_distinct, [cand])
    assert "invalid overlap_state: 'distinct_work'" in str(exc.value)

    # composite_subsumed is not in Spec 1.0.0-draft
    query_composite = build_base_query()
    query_composite["work_units_ledger"]["unit_reset"]["overlap_state"] = "composite_subsumed"
    with pytest.raises(RankingValidationError) as exc:
        execute_ranking_roundtrip(query_composite, [cand])
    assert "invalid overlap_state: 'composite_subsumed'" in str(exc.value)


def test_conformance_regression_bound_actions_requires_adds_array_validation():
    """Regression (Round 5 Finding 1): bound_actions requires and adds must be array of strings.

    Empty string '' or non-string elements must not bypass prerequisites and must fail closed.
    """
    cand = build_candidate_envelope("cand_req_adds_test")

    # 1. requires as single string "" (not list)
    query_req_str = build_base_query()
    query_req_str["bound_actions"][0]["requires"] = ""
    with pytest.raises(TypeError) as exc:
        execute_ranking_roundtrip(query_req_str, [cand])
    assert "requires must be a list of non-empty strings" in str(exc.value)

    # 2. requires as list containing empty string ""
    query_req_empty = build_base_query()
    query_req_empty["bound_actions"][0]["requires"] = [""]
    with pytest.raises(RankingValidationError) as exc:
        execute_ranking_roundtrip(query_req_empty, [cand])
    assert "requires element at index 0 must be a non-empty string" in str(exc.value)

    # 3. requires as list containing non-string
    query_req_nonstr = build_base_query()
    query_req_nonstr["bound_actions"][0]["requires"] = [123]
    with pytest.raises(RankingValidationError) as exc:
        execute_ranking_roundtrip(query_req_nonstr, [cand])
    assert "requires element at index 0 must be a non-empty string" in str(exc.value)

    # 4. adds as single string (not list)
    query_adds_str = build_base_query()
    query_adds_str["bound_actions"][0]["adds"] = "admin_access"
    with pytest.raises(TypeError) as exc:
        execute_ranking_roundtrip(query_adds_str, [cand])
    assert "adds must be a list of non-empty strings" in str(exc.value)

    # 5. adds as list containing whitespace string
    query_adds_empty = build_base_query()
    query_adds_empty["bound_actions"][0]["adds"] = ["   "]
    with pytest.raises(RankingValidationError) as exc:
        execute_ranking_roundtrip(query_adds_empty, [cand])
    assert "adds element at index 0 must be a non-empty string" in str(exc.value)


def test_conformance_regression_assumed_facts_truth_value_mandatory_boolean():
    """Regression (Round 5 Finding 2): assumed_facts entry missing truth_value must fail closed.

    Defaulting implicitly to True is prohibited; truth_value must be a strict boolean.
    """
    cand = build_candidate_envelope("cand_assumed_tv_test")

    # 1. Missing truth_value field
    query_missing_tv = build_base_query()
    query_missing_tv["facts_ledger"]["predicate_layers"] = {"session_present": 3}
    query_missing_tv["facts_ledger"]["assumed_facts"] = [
        {
            "predicate": "session_present",
            "layer": 3,
            "rationale": "Active admin session without explicit truth_value",
        }
    ]
    with pytest.raises(RankingValidationError) as exc:
        execute_ranking_roundtrip(query_missing_tv, [cand])
    assert "missing required truth_value" in str(exc.value)

    # 2. truth_value as integer 1 instead of boolean
    query_int_tv = build_base_query()
    query_int_tv["facts_ledger"]["predicate_layers"] = {"session_present": 3}
    query_int_tv["facts_ledger"]["assumed_facts"] = [
        {
            "predicate": "session_present",
            "layer": 3,
            "truth_value": 1,
            "rationale": "Integer truth value",
        }
    ]
    with pytest.raises(TypeError) as exc:
        execute_ranking_roundtrip(query_int_tv, [cand])
    assert "truth_value must be a boolean" in str(exc.value)

    # 3. truth_value as string "True" instead of boolean
    query_str_tv = build_base_query()
    query_str_tv["facts_ledger"]["predicate_layers"] = {"session_present": 3}
    query_str_tv["facts_ledger"]["assumed_facts"] = [
        {
            "predicate": "session_present",
            "layer": 3,
            "truth_value": "True",
            "rationale": "String truth value",
        }
    ]
    with pytest.raises(TypeError) as exc:
        execute_ranking_roundtrip(query_str_tv, [cand])
    assert "truth_value must be a boolean" in str(exc.value)


def test_conformance_regression_upstream_coverage_contradictory_metadata_rejected():
    """Regression (Round 5 Finding 3): contradictory upstream coverage metadata must fail closed.

    Examples:
    - is_truncated=False with non-empty truncation_reasons (e.g. timeout_exceeded).
    - is_truncated=False with completeness_scope='partial_truncated'.
    - is_truncated non-boolean.
    - invalid truncation_reasons or completeness_scope.
    """
    query = build_base_query()
    cand = build_candidate_envelope("cand_cov_test")

    # 1. Reviewer exact finding:
    # is_truncated=false + truncation_reasons=["timeout_exceeded"] + exhaustive_within_scope
    contradictory_upstream = {
        "is_truncated": False,
        "truncation_reasons": ["timeout_exceeded"],
        "completeness_scope": "exhaustive_within_scope",
    }
    with pytest.raises(RankingValidationError) as exc:
        execute_ranking_roundtrip(query, [cand], upstream_coverage=contradictory_upstream)
    assert "cannot have non-empty truncation_reasons when is_truncated is False" in str(exc.value)

    # 2. is_truncated=False with completeness_scope="partial_truncated"
    cov_false_partial = {
        "is_truncated": False,
        "completeness_scope": "partial_truncated",
    }
    with pytest.raises(RankingValidationError) as exc:
        execute_ranking_roundtrip(query, [cand], upstream_coverage=cov_false_partial)
    assert "cannot claim 'partial_truncated' when is_truncated is False" in str(exc.value)

    # 3. is_truncated as non-boolean string "false"
    cov_str_truncated = {
        "is_truncated": "false",
    }
    with pytest.raises(TypeError) as exc:
        execute_ranking_roundtrip(query, [cand], upstream_coverage=cov_str_truncated)
    assert "is_truncated must be a boolean" in str(exc.value)

    # 4. Unknown truncation reason
    cov_bad_reason = {
        "is_truncated": True,
        "truncation_reasons": ["arbitrary_unknown_reason"],
    }
    with pytest.raises(RankingValidationError) as exc:
        execute_ranking_roundtrip(query, [cand], upstream_coverage=cov_bad_reason)
    assert "invalid truncation_reason: 'arbitrary_unknown_reason'" in str(exc.value)

    # 5. Invalid completeness_scope enum
    cov_bad_scope = {
        "is_truncated": False,
        "completeness_scope": "arbitrary_scope",
    }
    with pytest.raises(RankingValidationError) as exc:
        execute_ranking_roundtrip(query, [cand], upstream_coverage=cov_bad_scope)
    assert "invalid completeness_scope: 'arbitrary_scope'" in str(exc.value)

    # 6. caps_applied with negative value
    cov_negative_cap = {
        "is_truncated": False,
        "caps_applied": {"timeout_ms": -100},
    }
    with pytest.raises(RankingValidationError) as exc:
        execute_ranking_roundtrip(query, [cand], upstream_coverage=cov_negative_cap)
    assert "must be a non-negative integer or null" in str(exc.value)


def test_conformance_regression_bound_actions_missing_requires_or_adds_rejected():
    """Regression (Round 6 Finding 1): missing requires or adds must fail closed.

    Implicitly defaulting missing requires/adds to [] is prohibited; empty array must be explicit.
    """
    cand = build_candidate_envelope("cand_missing_req_adds")

    # 1. Missing requires field entirely
    query_no_req = build_base_query()
    del query_no_req["bound_actions"][0]["requires"]
    with pytest.raises(RankingValidationError) as exc:
        execute_ranking_roundtrip(query_no_req, [cand])
    assert "missing required 'requires' field" in str(exc.value)

    # 2. Missing adds field entirely
    query_no_adds = build_base_query()
    del query_no_adds["bound_actions"][0]["adds"]
    with pytest.raises(RankingValidationError) as exc:
        execute_ranking_roundtrip(query_no_adds, [cand])
    assert "missing required 'adds' field" in str(exc.value)


def test_conformance_regression_work_units_missing_overlap_state_or_status_rejected():
    """Regression (Round 6 Finding 2): missing overlap_state or rating_status must fail closed.

    Inferring overlap_state => independent or rating_status => rated/unrated is prohibited.
    """
    cand = build_candidate_envelope("cand_wu_missing_fields")

    # 1. Missing overlap_state
    query_no_overlap = build_base_query()
    del query_no_overlap["work_units_ledger"]["unit_reset"]["overlap_state"]
    with pytest.raises(RankingValidationError) as exc:
        execute_ranking_roundtrip(query_no_overlap, [cand])
    assert "missing required 'overlap_state'" in str(exc.value)

    # 2. Missing rating_status/status when rubric exists
    query_no_status_rubric = build_base_query()
    del query_no_status_rubric["work_units_ledger"]["unit_reset"]["rating_status"]
    query_no_status_rubric["work_units_ledger"]["unit_reset"].pop("status", None)
    with pytest.raises(RankingValidationError) as exc:
        execute_ranking_roundtrip(query_no_status_rubric, [cand])
    assert "missing required 'rating_status'" in str(exc.value)

    # 3. Missing rating_status/status when unrated
    query_no_status_unrated = build_base_query()
    query_no_status_unrated["work_units_ledger"]["unit_unrated"] = {
        "work_unit_id": "unit_unrated",
        "overlap_state": "independent",
        "computed_cost": None,
    }
    with pytest.raises(RankingValidationError) as exc:
        execute_ranking_roundtrip(query_no_status_unrated, [cand])
    assert "missing required 'rating_status'" in str(exc.value)


def test_conformance_regression_upstream_coverage_truncated_without_reasons_rejected():
    """Regression (Round 6 Finding 3): is_truncated=True with empty reasons must fail closed.

    Spec §3.1 requires non-empty reasons when truncated; empty [] is reserved for exhaustive.
    """
    query = build_base_query()
    cand = build_candidate_envelope("cand_trunc_no_reasons")

    # 1. is_truncated=True with empty list of reasons
    cov_empty_reasons = {
        "is_truncated": True,
        "truncation_reasons": [],
    }
    with pytest.raises(RankingValidationError) as exc:
        execute_ranking_roundtrip(query, [cand], upstream_coverage=cov_empty_reasons)
    assert "must provide at least one non-empty truncation_reason" in str(exc.value)

    # 2. is_truncated=True with missing truncation_reasons field
    cov_missing_reasons = {
        "is_truncated": True,
    }
    with pytest.raises(RankingValidationError) as exc:
        execute_ranking_roundtrip(query, [cand], upstream_coverage=cov_missing_reasons)
    assert "must provide at least one non-empty truncation_reason" in str(exc.value)


def test_conformance_regression_bound_actions_missing_technique_name_rejected():
    """Regression (Round 7 Finding 1a): bound_actions entry missing technique_name must fail closed.

    Spec §2.3: technique_name (string) is a mandatory canonical field.
    """
    cand = build_candidate_envelope("cand_no_tech")

    # 1. Missing technique_name
    query_no_tech = build_base_query()
    del query_no_tech["bound_actions"][0]["technique_name"]
    with pytest.raises(RankingValidationError) as exc:
        execute_ranking_roundtrip(query_no_tech, [cand])
    assert "missing required 'technique_name' field" in str(exc.value)

    # 2. Empty string technique_name
    query_empty_tech = build_base_query()
    query_empty_tech["bound_actions"][0]["technique_name"] = "   "
    with pytest.raises(RankingValidationError) as exc:
        execute_ranking_roundtrip(query_empty_tech, [cand])
    assert "technique_name must be a non-empty string" in str(exc.value)


def test_conformance_regression_bound_actions_missing_is_passive_closure_rejected():
    """Regression (Round 7 Finding 1b): missing is_passive_closure must fail closed.

    Spec §2.3: is_passive_closure (boolean) is a mandatory canonical field, no silent False default.
    """
    cand = build_candidate_envelope("cand_no_passive")

    query_no_passive = build_base_query()
    del query_no_passive["bound_actions"][0]["is_passive_closure"]
    with pytest.raises(RankingValidationError) as exc:
        execute_ranking_roundtrip(query_no_passive, [cand])
    assert "missing required 'is_passive_closure' field" in str(exc.value)


def test_conformance_regression_bound_actions_passive_missing_referenced_work_units_rejected():
    """Regression (Round 7 Finding 1c): passive action missing referenced units must fail closed.

    Spec §2.3: passive action requires explicit list [] for referenced_work_unit_ids;
    missing field must NOT be silently healed to [].
    """
    cand = build_candidate_envelope("cand_passive_test")

    # 1. Passive action missing referenced_work_unit_ids / bound_work_units
    query_passive_missing_units = build_base_query()
    query_passive_missing_units["bound_actions"][0]["is_passive_closure"] = True
    del query_passive_missing_units["bound_actions"][0]["referenced_work_unit_ids"]
    query_passive_missing_units["bound_actions"][0].pop("bound_work_units", None)
    with pytest.raises(RankingValidationError) as exc:
        execute_ranking_roundtrip(query_passive_missing_units, [cand])
    assert "missing required 'referenced_work_unit_ids'" in str(exc.value)

    # 2. Passive action with explicit empty list [] passes
    query_passive_explicit_empty = build_base_query()
    query_passive_explicit_empty["bound_actions"][0]["is_passive_closure"] = True
    query_passive_explicit_empty["bound_actions"][0]["referenced_work_unit_ids"] = []
    # unit_reset is no longer in action 0, only unit_activate in action 1
    query_passive_explicit_empty["conditional_bounds_table"] = [
        {"prefix": ["unit_activate"], "lower": "7/10", "upper": "8/10"},
    ]
    res = execute_ranking_roundtrip(query_passive_explicit_empty, [cand])
    assert "cand_passive_test" in res["result_payload"]["eligible_candidates"]


@pytest.mark.parametrize("unit_field", ["referenced_work_unit_ids", "bound_work_units"])
def test_conformance_regression_passive_closure_active_work_units_rejected(unit_field):
    """Passive closure must never contribute active effort or conditional factors."""
    query = build_base_query()
    action = query["bound_actions"][0]
    action["is_passive_closure"] = True
    units = action.pop("referenced_work_unit_ids")
    action[unit_field] = units

    with pytest.raises(RankingValidationError, match="passive closure must have empty"):
        execute_ranking_roundtrip(query, [build_candidate_envelope("cand_passive_units")])


@pytest.mark.parametrize("blocked", [False, True])
def test_parameter_basis_metadata_survives_decode_assessment_and_wire_roundtrip(blocked):
    """Unrated work and bounds retain the human rating context in both result partitions."""
    from copy import deepcopy

    query = build_base_query()
    query["work_units_ledger"]["unit_reset"] = {
        "rating_status": "unrated",
        "overlap_state": "independent",
        "missing_basis_reasons": ["pending_independent_ratings"],
        "rating_provenance": {"raters": ["A", "B"], "bundle_version": "1.1.0"},
    }
    bounds = query["conditional_bounds_table"][0]
    bounds.update(
        basis_category="reviewed_research",
        rationale="Conditional on the declared scenario; no empirical calibration.",
        rating_provenance={"scenario_version": "1.1.0", "references": ["research:143"]},
    )
    if blocked:
        query["facts_ledger"]["false_facts"].append(
            {"predicate": "target_enabled", "layer": 2, "truth_value": False}
        )
    original = deepcopy(query)
    result = execute_ranking_roundtrip(query, [build_candidate_envelope()])
    assert query == original
    unit = result["decoded_query"]["work_units_ledger"]["unit_reset"]
    assert unit["missing_basis_reasons"] == ["pending_independent_ratings"]
    assert (
        unit["rating_provenance"]
        == original["work_units_ledger"]["unit_reset"]["rating_provenance"]
    )
    assert (
        result["decoded_query"]["conditional_bounds_records"]
        == original["conditional_bounds_table"]
    )
    audit = result["roundtrip_result"]["parameter_audit"]
    for section in audit:
        assert audit[section] == original[section]
    wire = result["roundtrip_result"]
    assessment = (
        wire["diagnostics"]["cand_01"]["assessment"]
        if blocked
        else wire["eligible_candidates"]["cand_01"]
    )
    assert assessment["effort"] is None
    if not blocked:
        assert assessment["work_unit_basis"]["unit_reset"]["missing_basis_reasons"] == [
            "pending_independent_ratings"
        ]
        assert assessment["conditional_bounds_basis"][0] == bounds
        assert bounds["rationale"] in assessment["likelihood_basis_summary"]
        assert bounds["basis_category"] in assessment["likelihood_basis_summary"]
        assert assessment["likelihood_interval"] == ["14/25", "18/25"]

    # Mutating caller-owned metadata after decoding cannot alter retained audit evidence.
    bounds["rating_provenance"]["references"].append("later")
    query["work_units_ledger"]["unit_reset"]["missing_basis_reasons"].append("later")
    assert result["decoded_query"]["parameter_audit"] == audit
    assert unit["missing_basis_reasons"] == ["pending_independent_ratings"]


@pytest.mark.parametrize(
    ("section", "field", "value"),
    [
        ("work_units_ledger", "missing_basis_reasons", "pending_independent_ratings"),
        ("conditional_bounds_table", "basis_category", 1),
        ("conditional_bounds_table", "rationale", ""),
    ],
)
def test_malformed_parameter_basis_metadata_rejected(section, field, value):
    query = build_base_query()
    record = query[section]["unit_reset"] if section == "work_units_ledger" else query[section][0]
    record[field] = value
    with pytest.raises(RankingValidationError, match=field):
        execute_ranking_roundtrip(query, [build_candidate_envelope()])


def test_conformance_regression_work_units_unsupported_formula_rejected():
    """Regression (Round 7 Finding 2): work-unit formula other than 'base' must fail closed.

    Spec §2.4: currently only research rubric convention 'base' (t1 + t2 - 2) is supported.
    Unsupported formulas or formula on unrated units must be rejected.
    """
    cand = build_candidate_envelope("cand_formula_test")

    # 1. Unsupported formula in rubric_scores
    query_bad_rubric_formula = build_base_query()
    query_bad_rubric_formula["work_units_ledger"]["unit_reset"]["rubric_scores"] = {
        "t1": 1,
        "t2": 2,
        "formula": "quadratic_penalty",
        "computed_cost": 1,
    }
    with pytest.raises(RankingValidationError) as exc:
        execute_ranking_roundtrip(query_bad_rubric_formula, [cand])
    assert "unsupported formula: 'quadratic_penalty', only 'base' is supported" in str(exc.value)

    # 2. Unsupported formula at top-level record
    query_bad_top_formula = build_base_query()
    query_bad_top_formula["work_units_ledger"]["unit_reset"]["formula"] = "exponential"
    with pytest.raises(RankingValidationError) as exc:
        execute_ranking_roundtrip(query_bad_top_formula, [cand])
    assert "unsupported formula: 'exponential', only 'base' is supported" in str(exc.value)

    # 3. Contradictory formulas between rubric_scores and top-level
    query_contradictory_formula = build_base_query()
    query_contradictory_formula["work_units_ledger"]["unit_reset"]["formula"] = "base"
    query_contradictory_formula["work_units_ledger"]["unit_reset"]["rubric_scores"] = {
        "t1": 1,
        "t2": 2,
        "formula": "custom",
        "computed_cost": 1,
    }
    with pytest.raises(RankingValidationError) as exc:
        execute_ranking_roundtrip(query_contradictory_formula, [cand])
    assert "contradictory formula" in str(exc.value)

    # 4. Unrated work unit declaring formula must fail closed
    query_unrated_with_formula = build_base_query()
    query_unrated_with_formula["work_units_ledger"]["unit_unrated"] = {
        "work_unit_id": "unit_unrated",
        "rating_status": "unrated",
        "overlap_state": "independent",
        "formula": "base",
        "computed_cost": None,
    }
    with pytest.raises(RankingValidationError) as exc:
        execute_ranking_roundtrip(query_unrated_with_formula, [cand])
    assert "unrated units must have formula null" in str(exc.value)


def test_conformance_regression_target_impact_assessment_missing_success_event_rejected():
    """Regression (Round 7 Finding 3): TargetImpactAssessment must have non-empty success_event.

    Spec §2.6: Impact is a consequence of a specific success event; always declare it.
    """
    cand = build_candidate_envelope("cand_impact_event")

    # 1. Assessment missing success_event in query
    query_no_event = build_base_query()
    del query_no_event["target_impact_assessments"][DC_TARGET_SID]["success_event"]
    with pytest.raises(RankingValidationError) as exc:
        execute_ranking_roundtrip(query_no_event, [cand])
    assert "missing required non-empty 'success_event'" in str(exc.value)

    query_empty_event = build_base_query()
    query_empty_event["target_impact_assessments"][DC_TARGET_SID]["success_event"] = "   "
    with pytest.raises(RankingValidationError) as exc:
        execute_ranking_roundtrip(query_empty_event, [cand])
    assert "missing required non-empty 'success_event'" in str(exc.value)

    query_no_goal_event = build_base_query()
    query_no_goal_event["query_metadata"]["target_goal"].pop("success_event", None)
    del query_no_goal_event["target_impact_assessments"][DC_TARGET_SID]["success_event"]
    with pytest.raises(RankingValidationError) as exc:
        execute_ranking_roundtrip(query_no_goal_event, [cand])
    assert "missing required non-empty 'success_event'" in str(exc.value)


def _path_result_for_ranking(
    *,
    first_edge: str = DUMMY_EDGE_1,
    first_technique: str = "tech_reset",
    target_asset_id: str = DC_TARGET_SID,
    second_edge: str = DUMMY_EDGE_2,
    second_technique: str = "tech_activate",
) -> dict[str, Any]:
    """Small JSON form shared by integration-boundary cases."""
    return {
        "nodes": [FOOTHOLD_SID, target_asset_id, target_asset_id],
        "edges": [
            {
                "id": first_edge,
                "source": FOOTHOLD_SID,
                "target": target_asset_id,
                "provenance": [{"record_locator": "evidence:edge:reset"}],
            },
            {
                "id": second_edge,
                "source": target_asset_id,
                "target": target_asset_id,
                "provenance": [{"record_locator": "evidence:edge:activate"}],
            },
        ],
        "transition_history": [
            {
                "edge_id": first_edge,
                "result": {
                    "request": {
                        "technique_id": first_technique,
                        "actor": FOOTHOLD_SID,
                        "source": FOOTHOLD_SID,
                        "target": target_asset_id,
                    },
                    "status": "applicable",
                    "failed": [],
                    "unknown": [],
                },
            },
            {
                "edge_id": second_edge,
                "result": {
                    "request": {
                        "technique_id": second_technique,
                        "actor": FOOTHOLD_SID,
                        "source": target_asset_id,
                        "target": target_asset_id,
                    },
                    "status": "applicable",
                    "failed": [],
                    "unknown": [],
                },
            },
        ],
        "scenario_reference": "scenario-corp-test",
        "runtime_context": {
            "facts": {"session_present|" + FOOTHOLD_SID + "|" + DC_TARGET_SID: True}
        },
    }


def _search_candidate(
    candidate_id: str = "search_candidate", target_asset_id: str = DC_TARGET_SID
) -> dict[str, Any]:
    return {
        "candidate_id": candidate_id,
        "target_asset_id": target_asset_id,
        "route_id": f"route_{candidate_id}",
        "action_mapping": {"tech_reset": "act_reset_pwd", "tech_activate": "act_activate_da"},
        "path_result": _path_result_for_ranking(),
    }


def test_search_to_ranking_positive_preserves_bindings_facts_and_trace():
    query = build_base_query()
    candidate = _search_candidate()
    coverage = {
        "is_truncated": True,
        "truncation_reasons": ["candidate_limit_reached"],
        "completeness_scope": "partial_truncated",
        "caps_applied": {"max_candidates": 1},
    }

    result = evaluate_search_candidates(query, [candidate], coverage=coverage)
    output = result["roundtrip_result"]
    assessment = output["eligible_candidates"]["search_candidate"]

    assert output["pareto_frontier"] == ["search_candidate"]
    assert assessment["structural_routes"][0]["node_ids"] == [
        FOOTHOLD_SID,
        DC_TARGET_SID,
        DC_TARGET_SID,
    ]
    assert assessment["structural_routes"][0]["edge_ids"] == [DUMMY_EDGE_1, DUMMY_EDGE_2]
    assert assessment["search_trace"]["target_binding"]["target_asset_id"] == DC_TARGET_SID
    assert assessment["search_trace"]["success_event_binding"]["success_event"] == (
        "domain_controller_full_compromise"
    )
    assert assessment["search_trace"]["transition_audit"][0]["decision"]["status"] == ("applicable")
    assert output["search_audit"]["facts_ledger"] == query["facts_ledger"]
    assert output["search_metadata"]["is_truncated"] is True
    assert output["search_audit"]["candidates_adapted"] == 1
    assert (
        result["encoded_json"]
        == evaluate_search_candidates(query, [candidate], coverage=coverage)["encoded_json"]
    )


def test_search_to_ranking_keeps_parallel_routes_and_bundle_version_context():
    query = build_base_query()
    query["query_metadata"].update(
        bundle_id="bundle-synthetic-1",
        bundle_version="1.0.0",
        bundle_digest="sha256:" + "b" * 64,
        governance={
            "basis_category": "research_assisted_scenario_hypotheses",
            "status": "pending_independent_human_ratings",
        },
    )
    parallel_action = deepcopy(query["bound_actions"][0])
    parallel_action["action_id"] = "act_reset_pwd_parallel"
    parallel_action["edge_id"] = DUMMY_EDGE_3
    query["bound_actions"].append(parallel_action)

    primary = _search_candidate("route_primary")
    parallel = _search_candidate("route_parallel")
    parallel["action_mapping"]["tech_reset"] = "act_reset_pwd_parallel"
    parallel["path_result"] = _path_result_for_ranking(first_edge=DUMMY_EDGE_3)

    result = evaluate_search_candidates(query, [primary, parallel])
    output = result["roundtrip_result"]
    primary_assessment = output["eligible_candidates"]["route_primary"]
    parallel_assessment = output["eligible_candidates"]["route_parallel"]

    assert primary_assessment["structural_routes"][0]["edge_ids"][0] == DUMMY_EDGE_1
    assert parallel_assessment["structural_routes"][0]["edge_ids"][0] == DUMMY_EDGE_3
    assert primary_assessment["program"] == parallel_assessment["program"]
    assert output["pareto_frontier"] == ["route_parallel", "route_primary"]
    assert output["parameter_audit"]["query_metadata"]["bundle_id"] == "bundle-synthetic-1"
    assert output["parameter_audit"]["query_metadata"]["bundle_version"] == "1.0.0"
    assert output["parameter_audit"]["query_metadata"]["bundle_digest"] == ("sha256:" + "b" * 64)


def test_search_to_ranking_keeps_distinct_target_contexts():
    query = build_base_query()
    query["query_metadata"]["target_goal"].pop("target_asset_id")
    query["target_impact_assessments"][SERVER_TARGET_SID] = {
        **deepcopy(query["target_impact_assessments"][DC_TARGET_SID]),
        "target_asset_id": SERVER_TARGET_SID,
    }
    server_actions = []
    for index, edge_id in enumerate((DUMMY_EDGE_3, DUMMY_EDGE_4)):
        action = deepcopy(query["bound_actions"][index])
        action["action_id"] += "_server"
        action["target_id"] = SERVER_TARGET_SID
        action["edge_id"] = edge_id
        server_actions.append(action)
    query["bound_actions"].extend(server_actions)

    dc_candidate = _search_candidate("target_dc")
    server_candidate = _search_candidate("target_server", SERVER_TARGET_SID)
    server_candidate["action_mapping"] = {
        "tech_reset_server": "act_reset_pwd_server",
        "tech_activate_server": "act_activate_da_server",
    }
    server_candidate["path_result"] = _path_result_for_ranking(
        first_edge=DUMMY_EDGE_3,
        first_technique="tech_reset_server",
        target_asset_id=SERVER_TARGET_SID,
        second_edge=DUMMY_EDGE_4,
        second_technique="tech_activate_server",
    )

    output = evaluate_search_candidates(query, [dc_candidate, server_candidate])["roundtrip_result"]

    assert output["eligible_candidates"]["target_dc"]["target_asset_id"] == DC_TARGET_SID
    assert output["eligible_candidates"]["target_server"]["target_asset_id"] == SERVER_TARGET_SID
    assert (
        output["eligible_candidates"]["target_server"]["search_trace"]["success_event_binding"][
            "target_asset_id"
        ]
        == SERVER_TARGET_SID
    )


@pytest.mark.parametrize(
    ("fact_case", "expected_status", "expected_reason"),
    [
        ("false", "blocked", "blocked"),
        ("unknown", "unknown", "unknown"),
    ],
)
def test_search_to_ranking_false_and_unknown_facts_fail_closed(
    fact_case: str, expected_status: str, expected_reason: str
):
    query = build_base_query()
    query["facts_ledger"]["observed_facts"].clear()
    if fact_case == "false":
        query["facts_ledger"]["false_facts"].append(
            {"predicate": "structural_genericall", "layer": 1, "truth_value": False}
        )
    else:
        query["facts_ledger"]["unknown_facts"].append(
            {"predicate": "structural_genericall", "layer": 1}
        )

    result = evaluate_search_candidates(query, [_search_candidate()])
    output = result["roundtrip_result"]

    assert output["pareto_frontier"] == []
    diagnostic = output["diagnostics"]["search_candidate"]
    assert diagnostic["assessment"]["status"] == expected_status
    assert expected_reason in diagnostic["reasons"]
    assert diagnostic["assessment"]["likelihood_interval"] is None


def test_search_to_ranking_unrated_and_missing_action_mapping_are_diagnostics():
    query = build_base_query()
    query["conditional_bounds_table"] = query["conditional_bounds_table"][1:]
    missing_mapping = _search_candidate("missing_mapping")
    missing_mapping["action_mapping"].pop("tech_reset")

    result = evaluate_search_candidates(query, [missing_mapping, _search_candidate("unrated")])
    output = result["roundtrip_result"]

    assert output["pareto_frontier"] == []
    assert output["diagnostics"]["missing_mapping"]["reasons"] == [
        "adapter_ineligible",
        "action_binding_missing",
    ]
    assert "likelihood_unrated" in output["diagnostics"]["unrated"]["reasons"]
    assert output["search_audit"]["candidates_rejected_by_adapter"] == 1


def test_search_adapter_supports_repeated_technique_with_ordered_step_bindings():
    query = build_base_query()
    second_action = deepcopy(query["bound_actions"][0])
    second_action.update(action_id="act_reset_pwd_second", edge_id=DUMMY_EDGE_2)
    query["bound_actions"].append(second_action)
    path = _path_result_for_ranking(second_technique="tech_reset")
    metadata = {
        **query["query_metadata"],
        "target_impact_assessments": query["target_impact_assessments"],
    }

    envelope = convert_path_result_to_candidate_envelope(
        path,
        candidate_id="repeated_technique",
        target_asset_id=DC_TARGET_SID,
        query_metadata=metadata,
        action_mapping=["act_reset_pwd", "act_reset_pwd_second"],
        bound_actions_catalog=query["bound_actions"],
    )

    assert envelope["bound_action_ids"] == ["act_reset_pwd", "act_reset_pwd_second"]
    assert [step["technique_id"] for step in envelope["transition_audit"]] == [
        "tech_reset",
        "tech_reset",
    ]
    with pytest.raises(RankingValidationError, match="ambiguous technique-only"):
        convert_path_result_to_candidate_envelope(
            path,
            candidate_id="ambiguous_repeated_technique",
            target_asset_id=DC_TARGET_SID,
            query_metadata=metadata,
            action_mapping={"tech_reset": "act_reset_pwd"},
            bound_actions_catalog=query["bound_actions"],
        )


@pytest.mark.parametrize(
    ("action_id", "diagnostic_fragment"),
    [("act_activate_da", "edge_id"), ("act_does_not_exist", "unknown bound_action")],
)
def test_search_adapter_rejects_wrong_or_unknown_step_action(
    action_id: str, diagnostic_fragment: str
):
    candidate = _search_candidate("invalid_action")
    candidate["action_mapping"] = [action_id, "act_activate_da"]

    output = evaluate_search_candidates(build_base_query(), [candidate])["roundtrip_result"]

    diagnostic = output["diagnostics"]["invalid_action"]["assessment"]["diagnostic"]
    assert diagnostic_fragment in diagnostic
    assert "invalid_action" not in output["eligible_candidates"]
    assert output["pareto_frontier"] == []


@pytest.mark.parametrize(
    ("field", "value", "fragment"),
    [
        ("actor_id", SERVER_TARGET_SID, "actor"),
        ("target_id", SERVER_TARGET_SID, "target"),
    ],
)
def test_search_adapter_checks_existing_action_actor_and_target_context(
    field: str, value: str, fragment: str
):
    query = build_base_query()
    query["bound_actions"][0][field] = value

    output = evaluate_search_candidates(query, [_search_candidate("wrong_context")])[
        "roundtrip_result"
    ]

    diagnostic = output["diagnostics"]["wrong_context"]["assessment"]["diagnostic"]
    assert fragment in diagnostic
    assert output["pareto_frontier"] == []


def test_search_adapter_preserves_derived_transition_without_structural_evidence():
    query = build_base_query()
    derived_action = deepcopy(query["bound_actions"][1])
    derived_action.update(action_id="act_derived_activate")
    derived_action.pop("edge_id")
    query["bound_actions"].append(derived_action)
    path = _path_result_for_ranking()
    path["transition_history"][1]["edge_id"] = None
    path["transition_history"][1]["derived_from_step"] = None
    candidate = _search_candidate("derived_transition")
    candidate["action_mapping"] = ["act_reset_pwd", "act_derived_activate"]
    candidate["path_result"] = path

    output = evaluate_search_candidates(query, [candidate])["roundtrip_result"]
    assessment = output["eligible_candidates"]["derived_transition"]

    assert assessment["structural_routes"][0]["node_ids"] == [FOOTHOLD_SID, DC_TARGET_SID]
    assert assessment["structural_routes"][0]["edge_ids"] == [DUMMY_EDGE_1]
    trace = assessment["search_trace"]["transition_audit"]
    assert trace[1]["edge_id"] is None
    assert trace[1]["derived_from_step"] is None
    assert output["pareto_frontier"] == ["derived_transition"]


def test_search_adapter_supports_real_146_initial_state_only_path_and_runtime_fact():
    from src.engine.ranking.orchestration import coverage_from_search_result
    from src.engine.search import AttackSearchResult, PathResult, SearchBudget, TransitionStep
    from src.engine.semantics import load_catalog
    from src.engine.semantics.models import FactOrigin, RuntimeFact
    from src.engine.semantics.state import AttackState, RuntimeContext
    from src.engine.semantics.transitions import Status, TransitionRequest, TransitionResult

    query = build_base_query()
    semantic_action = deepcopy(query["bound_actions"][1])
    semantic_action.update(
        action_id="act_initial_state_activate",
        requires=["session_present"],
        referenced_work_unit_ids=["unit_activate"],
    )
    semantic_action.pop("edge_id")
    query["bound_actions"] = [semantic_action]
    query["work_units_ledger"] = {"unit_activate": query["work_units_ledger"]["unit_activate"]}
    query["conditional_bounds_table"] = [
        {"prefix": ["unit_activate"], "lower": "7/10", "upper": "8/10"}
    ]

    technique = load_catalog()[0]
    before = AttackState()
    request = TransitionRequest(
        technique.id,
        FOOTHOLD_SID,
        FOOTHOLD_SID,
        DC_TARGET_SID,
    )
    transition = TransitionResult(
        request=request,
        technique=technique,
        status=Status.APPLICABLE,
        before=before,
        additions=AttackState(),
    )
    runtime_fact = RuntimeFact(
        predicate="session_present",
        subject=FOOTHOLD_SID,
        target=DC_TARGET_SID,
        value=True,
        origin=FactOrigin.DECLARED_ASSUMPTION,
        scope="business_hours_72h",
        rationale="scenario runtime assumption",
        provenance_reference="prov:runtime:session:001",
        assumption_metadata={"source": "scenario-corp-test"},
    )
    runtime_context = RuntimeContext(
        {("session_present", FOOTHOLD_SID, DC_TARGET_SID): runtime_fact}
    )
    path = PathResult(
        nodes=(FOOTHOLD_SID, DC_TARGET_SID),
        edges=(),
        transition_history=(
            TransitionStep(
                result=transition,
                edge_id=None,
                derived_from_step=None,
            ),
        ),
        final_state=before,
        scenario_reference="scenario-corp-test",
        runtime_context=runtime_context,
    )
    search_result = AttackSearchResult(
        paths=(path,),
        attempts=(transition,),
        expansions=1,
        truncated=True,
        truncation_reason="step_limit_reached",
    )
    budget = SearchBudget(max_paths=5, max_steps=1, max_expansions=10)
    coverage = coverage_from_search_result(search_result, budget)
    candidate = {
        "candidate_id": "initial_state_only",
        "target_asset_id": DC_TARGET_SID,
        "route_id": "route_initial_state_only",
        "action_mapping": ["act_initial_state_activate"],
        "path_result": path,
    }

    output = evaluate_search_candidates(query, [candidate], coverage=coverage)["roundtrip_result"]
    assessment = output["eligible_candidates"]["initial_state_only"]
    route = assessment["structural_routes"][0]

    assert route["node_ids"] == [FOOTHOLD_SID]
    assert route["edge_ids"] == []
    assert route["action_step_indices"] == []
    assert route["provenance_locators"] == []
    assert route["semantic_lineage"] == [
        {
            "step_index": 0,
            "action_id": "act_initial_state_activate",
            "technique_id": technique.id,
            "actor": FOOTHOLD_SID,
            "source": FOOTHOLD_SID,
            "target": DC_TARGET_SID,
            "edge_id": None,
            "derived_from_step": None,
            "origin": "initial_attack_state",
            "status": "applicable",
        }
    ]
    assert assessment["search_trace"]["transition_audit"][0]["edge_id"] is None
    assert assessment["search_trace"]["transition_audit"][0]["derived_from_step"] is None
    fact = assessment["search_trace"]["runtime_fact_values"][0]
    assert fact["truth_value"] is True
    assert fact["origin"] == "declared_assumption"
    assert fact["scope"] == "business_hours_72h"
    assert fact["provenance_reference"] == "prov:runtime:session:001"
    assert output["search_metadata"]["truncation_reasons"] == ["step_limit_reached"]
    assert output["search_metadata"]["caps_applied"]["max_candidates"] == 5
    assert output["search_metadata"]["caps_applied"]["max_steps"] == 1
    assert output["search_metadata"]["caps_applied"]["max_expansions"] == 10
    assert (
        output["min_effort_to_da_baseline"]["baseline_coverage"]["caps_applied"]
        == output["search_metadata"]["caps_applied"]
    )
    assert output["pareto_frontier"] == ["initial_state_only"]


def test_search_adapter_preserves_real_146_non_contiguous_observed_segments():
    from src.engine.search import PathResult, TransitionStep
    from src.engine.semantics import load_catalog
    from src.engine.semantics.state import AttackState, RuntimeContext
    from src.engine.semantics.transitions import Status, TransitionRequest, TransitionResult

    query = build_base_query()
    reset_server = deepcopy(query["bound_actions"][0])
    reset_server.update(
        action_id="act_reset_server",
        target_id=SERVER_TARGET_SID,
        edge_id=DUMMY_EDGE_1,
    )
    activate_dc = deepcopy(query["bound_actions"][1])
    activate_dc.update(
        action_id="act_activate_dc_sparse",
        target_id=DC_TARGET_SID,
        edge_id=DUMMY_EDGE_2,
    )
    query["bound_actions"] = [reset_server, activate_dc]

    technique = load_catalog()[0]
    before = AttackState()
    first = TransitionResult(
        request=TransitionRequest(
            technique.id,
            FOOTHOLD_SID,
            FOOTHOLD_SID,
            SERVER_TARGET_SID,
        ),
        technique=technique,
        status=Status.APPLICABLE,
        before=before,
        additions=AttackState(),
    )
    second = TransitionResult(
        request=TransitionRequest(
            technique.id,
            FOOTHOLD_SID,
            FOOTHOLD_SID,
            DC_TARGET_SID,
        ),
        technique=technique,
        status=Status.APPLICABLE,
        before=before,
        additions=AttackState(),
    )
    first_edge = _canonical_edge(
        DUMMY_EDGE_1,
        "evidence:sparse:first",
        source=FOOTHOLD_SID,
        target=SERVER_TARGET_SID,
    )
    second_edge = _canonical_edge(
        DUMMY_EDGE_2,
        "evidence:sparse:second",
        source=FOOTHOLD_SID,
        target=DC_TARGET_SID,
    )
    path = PathResult(
        nodes=(FOOTHOLD_SID, SERVER_TARGET_SID, DC_TARGET_SID),
        edges=(first_edge, second_edge),
        transition_history=(
            TransitionStep(result=first, edge_id=DUMMY_EDGE_1, derived_from_step=None),
            TransitionStep(result=second, edge_id=DUMMY_EDGE_2, derived_from_step=None),
        ),
        final_state=before,
        scenario_reference="scenario-corp-test",
        runtime_context=RuntimeContext(),
    )
    candidate = {
        "candidate_id": "sparse_observed_program",
        "target_asset_id": DC_TARGET_SID,
        "route_id": "route_sparse_observed",
        "action_mapping": ["act_reset_server", "act_activate_dc_sparse"],
        "path_result": path,
    }

    output = evaluate_search_candidates(query, [candidate])["roundtrip_result"]
    assessment = output["eligible_candidates"]["sparse_observed_program"]
    routes = assessment["structural_routes"]

    assert len(routes) == 2
    assert routes[0]["node_ids"] == [FOOTHOLD_SID, SERVER_TARGET_SID]
    assert routes[0]["edge_ids"] == [DUMMY_EDGE_1]
    assert routes[0]["action_step_indices"] == [0]
    assert routes[1]["node_ids"] == [FOOTHOLD_SID, DC_TARGET_SID]
    assert routes[1]["edge_ids"] == [DUMMY_EDGE_2]
    assert routes[1]["action_step_indices"] == [1]
    lineage = assessment["search_trace"]["transition_lineage"]
    assert [record["edge_id"] for record in lineage] == [DUMMY_EDGE_1, DUMMY_EDGE_2]
    assert [record["source"] for record in lineage] == [FOOTHOLD_SID, FOOTHOLD_SID]
    assert [record["target"] for record in lineage] == [SERVER_TARGET_SID, DC_TARGET_SID]
    assert output["pareto_frontier"] == ["sparse_observed_program"]


def test_direct_candidate_cannot_fabricate_empty_semantic_route_without_lineage():
    query = build_base_query()
    candidate = build_candidate_envelope(
        "fabricated_semantic_only",
        action_ids=["act_activate_da"],
        routes=[
            {
                "route_id": "route_fabricated_semantic_only",
                "node_ids": [FOOTHOLD_SID],
                "edge_ids": [],
                "action_step_indices": [],
                "provenance_locators": [],
            }
        ],
    )

    with pytest.raises(RankingValidationError, match="explicit semantic_lineage"):
        execute_ranking_roundtrip(query, [candidate])


def test_derived_step_first_goal_trimming_keeps_exact_structural_prefix():
    query = build_base_query()
    derived_action = deepcopy(query["bound_actions"][1])
    derived_action.update(action_id="act_derived_activate")
    derived_action.pop("edge_id")
    query["bound_actions"].append(derived_action)
    path = _path_result_for_ranking()
    path["transition_history"][1]["edge_id"] = None
    path["transition_history"][1]["derived_from_step"] = 0
    path["transition_history"].append(deepcopy(path["transition_history"][0]))
    path["transition_history"][2]["edge_id"] = DUMMY_EDGE_2
    path["transition_history"][2]["result"]["request"].update(
        source=DC_TARGET_SID, target=DC_TARGET_SID
    )
    path["nodes"].append(DC_TARGET_SID)
    candidate = _search_candidate("derived_first_goal")
    candidate["action_mapping"] = [
        "act_reset_pwd",
        "act_derived_activate",
        "act_activate_da",
    ]
    candidate["path_result"] = path

    output = evaluate_search_candidates(query, [candidate])["roundtrip_result"]
    assessment = output["eligible_candidates"]["derived_first_goal"]

    assert assessment["bound_action_ids"] == ["act_reset_pwd", "act_derived_activate"]
    assert assessment["structural_routes"][0]["edge_ids"] == [DUMMY_EDGE_1]
    assert assessment["structural_routes"][0]["node_ids"] == [FOOTHOLD_SID, DC_TARGET_SID]
    assert [step["edge_id"] for step in assessment["search_trace"]["transition_audit"]] == [
        DUMMY_EDGE_1,
        None,
        DUMMY_EDGE_2,
    ]


def test_search_orchestration_isolates_canonical_candidate_validation_per_candidate():
    good = _search_candidate("valid_candidate")
    bad = _search_candidate("invalid_candidate")
    bad["route_id"] = ""

    output = evaluate_search_candidates(build_base_query(), [good, bad])["roundtrip_result"]

    assert "valid_candidate" in output["eligible_candidates"]
    assert output["pareto_frontier"] == ["valid_candidate"]
    assert output["diagnostics"]["invalid_candidate"]["reasons"] == ["canonical_candidate_invalid"]
    assert "route_id" in output["diagnostics"]["invalid_candidate"]["assessment"]["diagnostic"]


def test_search_coverage_translates_current_issue_146_result_and_budget_shape():
    from types import SimpleNamespace

    from src.engine.ranking.orchestration import coverage_from_search_result

    coverage = coverage_from_search_result(
        SimpleNamespace(
            paths=(object(),),
            attempts=(),
            expansions=8,
            truncated=True,
            truncation_reason="expansion_limit_reached",
        ),
        SimpleNamespace(max_paths=3, max_steps=5, max_expansions=8),
    )

    assert coverage == {
        "is_truncated": True,
        "truncation_reasons": ["expansion_limit_reached"],
        "completeness_scope": "partial_truncated",
        "caps_applied": {"max_candidates": 3, "max_steps": 5, "max_expansions": 8},
        "search_expansions": 8,
        "candidates_found": 1,
    }
    ranked = evaluate_search_candidates(
        build_base_query(), [_search_candidate("coverage_from_146")], coverage=coverage
    )["roundtrip_result"]
    assert ranked["search_metadata"]["is_truncated"] is True
    assert ranked["search_metadata"]["caps_applied"]["max_candidates"] == 3
    assert ranked["search_metadata"]["caps_applied"]["max_steps"] == 5
    assert ranked["search_metadata"]["caps_applied"]["max_expansions"] == 8
    assert ranked["search_audit"]["coverage"]["caps_applied"] == coverage["caps_applied"]
    assert (
        ranked["min_effort_to_da_baseline"]["baseline_coverage"]["caps_applied"]
        == ranked["search_metadata"]["caps_applied"]
    )


def test_search_cli_normalizes_max_paths_alias_into_final_coverage(tmp_path: Path):
    query_path = tmp_path / "query.json"
    candidates_path = tmp_path / "search-candidates.json"
    coverage_path = tmp_path / "coverage.json"
    output_path = tmp_path / "result.json"

    query_path.write_text(json.dumps(build_base_query()), encoding="utf-8")
    candidates_path.write_text(
        json.dumps([_search_candidate("cli_coverage_alias")]),
        encoding="utf-8",
    )
    coverage_path.write_text(
        json.dumps(
            {
                "is_truncated": True,
                "truncation_reasons": ["candidate_limit_reached"],
                "completeness_scope": "partial_truncated",
                "caps_applied": {
                    "max_paths": 2,
                    "max_steps": 4,
                    "max_expansions": 12,
                },
            }
        ),
        encoding="utf-8",
    )

    rc = run_ranking_cli(
        [
            "--query",
            str(query_path),
            "--search-candidates",
            str(candidates_path),
            "--coverage",
            str(coverage_path),
            "--output",
            str(output_path),
        ]
    )

    assert rc == 0
    output = json.loads(output_path.read_text(encoding="utf-8"))
    caps = output["search_metadata"]["caps_applied"]
    assert caps["max_candidates"] == 2
    assert caps["max_steps"] == 4
    assert caps["max_expansions"] == 12
    assert "max_paths" not in caps
    baseline_caps = output["min_effort_to_da_baseline"]["baseline_coverage"]["caps_applied"]
    assert baseline_caps == caps
    assert output["search_audit"]["coverage"]["caps_applied"] == {
        "max_candidates": 2,
        "max_steps": 4,
        "max_expansions": 12,
    }


def test_search_coverage_rejects_conflicting_candidate_cap_aliases():
    coverage = {
        "is_truncated": True,
        "truncation_reasons": ["candidate_limit_reached"],
        "completeness_scope": "partial_truncated",
        "caps_applied": {"max_paths": 2, "max_candidates": 3},
    }

    with pytest.raises(RankingValidationError, match="conflicting aliases"):
        evaluate_search_candidates(
            build_base_query(),
            [_search_candidate("conflicting_coverage_alias")],
            coverage=coverage,
        )


def test_search_coverage_preserves_explicit_issue_146_step_limit_reason():
    from types import SimpleNamespace

    from src.engine.ranking.orchestration import coverage_from_search_result

    coverage = coverage_from_search_result(
        SimpleNamespace(
            paths=(),
            attempts=(),
            expansions=2,
            truncated=True,
            truncation_reason="step_limit_reached",
        ),
        SimpleNamespace(max_paths=5, max_steps=3, max_expansions=10),
    )

    assert coverage["truncation_reasons"] == ["step_limit_reached"]
    assert coverage["caps_applied"] == {
        "max_candidates": 5,
        "max_steps": 3,
        "max_expansions": 10,
    }
    ranked = evaluate_search_candidates(
        build_base_query(), [_search_candidate("step_limited")], coverage=coverage
    )["roundtrip_result"]
    assert ranked["search_metadata"]["truncation_reasons"] == ["step_limit_reached"]
    assert ranked["search_metadata"]["is_truncated"] is True
    assert ranked["search_metadata"]["caps_applied"]["max_candidates"] == 5
    assert ranked["search_metadata"]["caps_applied"]["max_steps"] == 3
    assert ranked["search_metadata"]["caps_applied"]["max_expansions"] == 10


def test_search_coverage_does_not_infer_step_truncation_from_completed_path_length():
    from types import SimpleNamespace

    from src.engine.ranking.orchestration import coverage_from_search_result

    path = SimpleNamespace(transition_history=(object(), object(), object()))
    coverage = coverage_from_search_result(
        SimpleNamespace(paths=(path,), attempts=(), expansions=10, truncated=True),
        SimpleNamespace(max_paths=5, max_steps=3, max_expansions=10),
    )

    assert coverage["truncation_reasons"] == ["expansion_limit_reached"]


def test_search_coverage_fails_closed_when_truncation_cause_is_not_observable():
    from types import SimpleNamespace

    from src.engine.ranking.orchestration import coverage_from_search_result

    with pytest.raises(RankingValidationError, match="refusing to invent a truncation reason"):
        coverage_from_search_result(
            SimpleNamespace(paths=(), attempts=(), expansions=2, truncated=True),
            SimpleNamespace(max_paths=5, max_steps=3, max_expansions=10),
        )


def test_search_runtime_fact_audit_serializes_merged_146_runtime_context():
    from src.engine.semantics.models import FactOrigin, RuntimeFact
    from src.engine.semantics.state import RuntimeContext

    path = _path_result_for_ranking()
    key = ("session_present", FOOTHOLD_SID, DC_TARGET_SID)
    path["runtime_context"] = RuntimeContext(
        {
            key: RuntimeFact(
                predicate=key[0],
                subject=key[1],
                target=key[2],
                value=True,
                origin=FactOrigin.DECLARED_ASSUMPTION,
                scope="business_hours_72h",
                rationale="scenario runtime assumption",
                provenance_reference="prov:runtime:session:001",
                assumption_metadata={"source": "scenario-corp-test"},
            )
        }
    )
    candidate = _search_candidate("typed_runtime_fact")
    candidate["path_result"] = path

    result = evaluate_search_candidates(build_base_query(), [candidate])
    output = result["roundtrip_result"]
    fact = output["eligible_candidates"]["typed_runtime_fact"]["search_trace"][
        "runtime_fact_values"
    ][0]

    assert fact == {
        "predicate": "session_present",
        "subject": FOOTHOLD_SID,
        "target": DC_TARGET_SID,
        "truth_value": True,
        "origin": "declared_assumption",
        "scope": "business_hours_72h",
        "rationale": "scenario runtime assumption",
        "provenance_reference": "prov:runtime:session:001",
        "assumption_metadata": {"source": "scenario-corp-test"},
    }
    assert json.loads(result["encoded_json"]) == output


def test_action_step_indices_are_validated_even_without_goal_trimming():
    from src.engine.ranking import decode_ranking_query
    from src.engine.ranking.replay import replay_candidate_sequence

    query_payload = build_base_query()
    candidate = convert_path_result_to_candidate_envelope(
        path_result=_path_result_for_ranking(),
        candidate_id="malformed_step_indices",
        target_asset_id=DC_TARGET_SID,
        query_metadata={
            **query_payload["query_metadata"],
            "target_impact_assessments": query_payload["target_impact_assessments"],
        },
        action_mapping=["act_reset_pwd", "act_activate_da"],
        bound_actions_catalog=query_payload["bound_actions"],
    )
    candidate["structural_routes"][0]["action_step_indices"] = [0, 9]

    with pytest.raises(MappingSyncError, match="invalid action_step_indices"):
        replay_candidate_sequence(decode_ranking_query(query_payload), candidate)


def test_search_to_ranking_hydrates_exact_edge_from_pinned_canonical_graph():
    graph = json.loads(
        (Path(__file__).parents[1] / "data" / "samples" / "toy-graph.json").read_text(
            encoding="utf-8"
        )
    )
    edge = graph["edges"][0]
    source, target = edge["source"], edge["target"]
    query = build_base_query()
    query["query_metadata"]["snapshot_id"] = graph["metadata"]["snapshot_id"]
    query["query_metadata"]["foothold_node_id"] = source
    query["query_metadata"]["target_goal"]["target_asset_id"] = target
    query["bound_actions"] = [query["bound_actions"][0]]
    action = query["bound_actions"][0]
    action["actor_id"] = source
    action["target_id"] = target
    action["edge_id"] = edge["id"]
    action["adds"] = ["target_controlled", "da_entitlement_active"]
    impact = query["target_impact_assessments"].pop(DC_TARGET_SID)
    impact["target_asset_id"] = target
    query["target_impact_assessments"] = {target: impact}
    path_result = {
        "nodes": [source, target],
        "transition_history": [
            {
                "edge_id": edge["id"],
                "result": {
                    "request": {
                        "technique_id": "tech_reset",
                        "source": source,
                        "target": target,
                    },
                    "status": "applicable",
                },
            }
        ],
        "scenario_reference": "scenario-corp-test",
    }
    candidate = {
        "candidate_id": "graph_hydrated",
        "target_asset_id": target,
        "route_id": "route_graph_hydrated",
        "action_mapping": {"tech_reset": "act_reset_pwd"},
        "path_result": path_result,
    }

    result = evaluate_search_candidates(query, [candidate], canonical_graph=graph)
    assessment = result["roundtrip_result"]["eligible_candidates"]["graph_hydrated"]

    assert assessment["structural_routes"][0]["edge_ids"] == [edge["id"]]
    assert assessment["structural_routes"][0]["provenance_locators"][0]
    assert assessment["search_trace"]["success_event_binding"]["target_asset_id"] == target


def test_search_to_ranking_cli_accepts_separate_query_and_path_result_files(tmp_path: Path):
    query_path = tmp_path / "query.json"
    search_path = tmp_path / "search.json"
    mapping_path = tmp_path / "mapping.json"
    output_path = tmp_path / "ranking.json"
    query_path.write_text(
        json.dumps({"query": build_base_query(), "candidates": []}), encoding="utf-8"
    )
    candidate = _search_candidate()
    candidate.pop("action_mapping")
    search_path.write_text(json.dumps([candidate]), encoding="utf-8")
    mapping_path.write_text(json.dumps(["act_reset_pwd", "act_activate_da"]), encoding="utf-8")

    exit_code = run_ranking_cli(
        [
            "--query",
            str(query_path),
            "--search-candidates",
            str(search_path),
            "--action-mapping",
            str(mapping_path),
            "--output",
            str(output_path),
        ]
    )

    assert exit_code == 0
    output = json.loads(output_path.read_text(encoding="utf-8"))
    assert output["pareto_frontier"] == ["search_candidate"]
    assert output["search_audit"]["candidate_source"] == "explicit_path_results"


@pytest.mark.parametrize("directory_write_value", [True, False, None])
def test_real_generate_attack_paths_flows_through_binding_and_ranking(directory_write_value):
    from src.engine import SearchBudget
    from src.engine.semantics import (
        AttackState,
        FactOrigin,
        RuntimeContext,
        RuntimeFact,
        load_catalog,
    )

    graph = json.loads(
        (Path(__file__).parents[1] / "data" / "samples" / "toy-graph.json").read_text(
            encoding="utf-8"
        )
    )
    actor = "10000000-0000-4000-8000-000000000001"
    target = "S-1-5-21-1000-2000-3000-512"
    edge_id = "sha256:471092492f59bece8eec52226d171979595cbd2a554280bc396097e483ffb327"

    query = build_base_query()
    query["query_metadata"]["snapshot_id"] = graph["metadata"]["snapshot_id"]
    query["query_metadata"]["foothold_node_id"] = actor
    query["query_metadata"]["target_goal"]["target_asset_id"] = target
    query["bound_actions"] = [query["bound_actions"][0]]
    action = query["bound_actions"][0]
    action.update(
        action_id="act_add_member",
        technique_name="genericall_add_member",
        actor_id=actor,
        target_id=target,
        edge_id=edge_id,
        adds=["target_controlled", "da_entitlement_active"],
        referenced_work_unit_ids=["unit_reset"],
    )
    query["conditional_bounds_table"] = [
        {"prefix": ["unit_reset"], "lower": "8/10", "upper": "9/10"}
    ]
    query["work_units_ledger"] = {"unit_reset": query["work_units_ledger"]["unit_reset"]}
    impact = query["target_impact_assessments"].pop(DC_TARGET_SID)
    impact["target_asset_id"] = target
    query["target_impact_assessments"] = {target: impact}

    facts = [
        RuntimeFact(
            predicate,
            actor,
            target,
            directory_write_value if predicate == "directory_write_allowed" else True,
            (
                FactOrigin.BLOCKED_EVIDENCE
                if directory_write_value is False
                else FactOrigin.UNKNOWN
                if directory_write_value is None
                else FactOrigin.DECLARED_ASSUMPTION
            )
            if predicate == "directory_write_allowed"
            else FactOrigin.DECLARED_ASSUMPTION,
            scope="business_hours_72h",
            rationale="synthetic real-search integration prerequisite",
        )
        for predicate in ("security_group", "membership_change_allowed", "directory_write_allowed")
    ]
    result = generate_and_evaluate_attack_paths(
        query,
        graph,
        actor=actor,
        initial_state=AttackState(control={actor}, usable_identity={(actor, actor)}),
        runtime_context=RuntimeContext(facts, authentication_context=actor),
        budget=SearchBudget(max_paths=3, max_steps=2, max_expansions=10),
        action_bindings={
            ("genericall_add_member", actor, actor, target): "act_add_member",
        },
        catalog=tuple(item for item in load_catalog() if item.id == "genericall_add_member"),
        scenario_reference="scenario-corp-test",
        success_state_predicate=lambda state: bool(state.relationship_added),
    )

    output = result["roundtrip_result"]
    assert output["search_audit"]["candidate_source"] == "generate_attack_paths"
    assert output["search_audit"]["terminal_condition"] == "target_asset_and_declared_success_state"
    if directory_write_value is not True:
        from scripts.research.week3_engine_acceptance import case_expectation_audit

        binding = {
            "technique_id": "genericall_add_member",
            "predicate": "directory_write_allowed",
            "subject": actor,
            "target": target,
            "value": directory_write_value,
            "origin": "blocked_evidence" if directory_write_value is False else "unknown",
            "scope": "business_hours_72h",
            "rationale": "synthetic real-search integration prerequisite",
        }
        case = {
            "kind": "known_false" if directory_write_value is False else "runtime_unknown",
            "expected": {"candidates": {"reviewed": {"status": "blocked"}}},
            "predicate": {"search_binding": binding},
        }
        projection = {
            "candidates": [{"candidate_id": "reviewed", "bound_action_ids": ["act_add_member"]}]
        }
        audit = case_expectation_audit(projection, case, output)
        assert audit["complete"] is True
        assert audit["matching_negative_attempts"]
        assert output["search_audit"]["generated_paths"] == 0
        return
    assert output["search_audit"]["generated_paths"] == 1
    assert output["search_audit"]["generated_candidates_bound"] == 1
    assert output["search_audit"]["binding_diagnostics"] == {}
    assert output["pareto_frontier"] == ["generated_0001"]
    assert output["eligible_candidates"]["generated_0001"]["bound_action_ids"] == ["act_add_member"]


def test_equal_effort_generated_candidates_independent_of_oracle_naming():
    """Verify generated candidate ranking and tie-breaking are independent of oracle names.

    When search generates multiple candidates with equal effort:
    1. Orchestration assigns pure generator identities (generated_0001, generated_0002).
    2. compute_min_effort_baseline tie-breaks on (effort, candidate_id) strictly using
       these generator identities, ensuring generation order is preserved.
    3. External oracle naming schemes cannot enter generate_and_evaluate_attack_paths()
       or alter the ranking output.
    4. Post-evaluation mapping in case_expectation_audit correctly maps generated identities
       to oracle IDs without influencing the ranking engine's evaluation.
    """
    from scripts.check_contract import canonical_edge_id
    from scripts.research.week3_engine_acceptance import case_expectation_audit
    from src.engine import SearchBudget
    from src.engine.ranking.orchestration import generate_and_evaluate_attack_paths
    from src.engine.semantics import (
        AttackState,
        FactOrigin,
        RuntimeContext,
        RuntimeFact,
        load_catalog,
    )

    graph_dict = json.loads(
        (Path(__file__).parents[1] / "data" / "samples" / "toy-graph.json").read_text(
            encoding="utf-8"
        )
    )
    actor = "10000000-0000-4000-8000-000000000001"
    target = "S-1-5-21-1000-2000-3000-512"
    g1 = "S-1-5-21-1000-2000-3000-520"
    g2 = "S-1-5-21-1000-2000-3000-521"

    node1 = deepcopy(graph_dict["nodes"][2])
    node1["id"] = g1
    node1["label"] = "GROUP-1"
    node1["distinguishedname"] = "CN=GROUP-1,OU=Groups,DC=example,DC=test"

    node2 = deepcopy(graph_dict["nodes"][2])
    node2["id"] = g2
    node2["label"] = "GROUP-2"
    node2["distinguishedname"] = "CN=GROUP-2,OU=Groups,DC=example,DC=test"

    graph_dict["nodes"].extend([node1, node2])

    e_g1 = canonical_edge_id(actor, g1, "GenericAll")
    e_g1_t = canonical_edge_id(g1, target, "MemberOf")
    e_g2 = canonical_edge_id(actor, g2, "GenericAll")
    e_g2_t = canonical_edge_id(g2, target, "MemberOf")

    graph_dict["edges"] = [
        {
            "id": e_g1,
            "source": actor,
            "target": g1,
            "kind": "GenericAll",
            "weight": 1.0,
            "provenance": deepcopy(graph_dict["edges"][2]["provenance"]),
        },
        {
            "id": e_g1_t,
            "source": g1,
            "target": target,
            "kind": "MemberOf",
            "weight": 1.0,
            "provenance": deepcopy(graph_dict["edges"][1]["provenance"]),
        },
        {
            "id": e_g2,
            "source": actor,
            "target": g2,
            "kind": "GenericAll",
            "weight": 1.0,
            "provenance": deepcopy(graph_dict["edges"][2]["provenance"]),
        },
        {
            "id": e_g2_t,
            "source": g2,
            "target": target,
            "kind": "MemberOf",
            "weight": 1.0,
            "provenance": deepcopy(graph_dict["edges"][1]["provenance"]),
        },
    ]

    query = build_base_query()
    query["query_metadata"]["snapshot_id"] = graph_dict["metadata"]["snapshot_id"]
    query["query_metadata"]["foothold_node_id"] = actor
    query["query_metadata"]["target_goal"]["target_asset_id"] = target

    u0 = deepcopy(query["work_units_ledger"]["unit_reset"])
    u0["unit_id"] = "unit_common"
    u0["cost"] = 1

    u1 = deepcopy(query["work_units_ledger"]["unit_reset"])
    u1["unit_id"] = "unit_branch_1"
    u1["cost"] = 1

    u2 = deepcopy(query["work_units_ledger"]["unit_reset"])
    u2["unit_id"] = "unit_branch_2"
    u2["cost"] = 1

    query["work_units_ledger"] = {"unit_common": u0, "unit_branch_1": u1, "unit_branch_2": u2}

    query["conditional_bounds_table"] = [
        {"prefix": ["unit_common"], "lower": "9/10", "upper": "1"},
        {"prefix": ["unit_common", "unit_branch_1"], "lower": "8/10", "upper": "9/10"},
        {"prefix": ["unit_common", "unit_branch_2"], "lower": "8/10", "upper": "9/10"},
    ]

    def make_act(aid, tech, act_id, tgt_id, eid, adds, units):
        b = deepcopy(query["bound_actions"][0])
        b.update(
            {
                "action_id": aid,
                "technique_name": tech,
                "actor_id": act_id,
                "target_id": tgt_id,
                "edge_id": eid,
                "requires": [],
                "adds": adds,
                "referenced_work_unit_ids": units,
                "is_passive_closure": False,
            }
        )
        return b

    query["bound_actions"] = [
        make_act(
            "act_add_g1",
            "genericall_add_member",
            actor,
            g1,
            e_g1,
            ["g1_controlled"],
            ["unit_common"],
        ),
        make_act(
            "act_prop_g1",
            "propagate_group_entitlement",
            actor,
            g1,
            None,
            ["g1_prop"],
            ["unit_common"],
        ),
        make_act(
            "act_reach_target_g1",
            "propagate_group_entitlement",
            actor,
            target,
            e_g1_t,
            ["target_controlled", "da_entitlement_active"],
            ["unit_branch_1"],
        ),
        make_act(
            "act_add_g2",
            "genericall_add_member",
            actor,
            g2,
            e_g2,
            ["g2_controlled"],
            ["unit_common"],
        ),
        make_act(
            "act_prop_g2",
            "propagate_group_entitlement",
            actor,
            g2,
            None,
            ["g2_prop"],
            ["unit_common"],
        ),
        make_act(
            "act_reach_target_g2",
            "propagate_group_entitlement",
            actor,
            target,
            e_g2_t,
            ["target_controlled", "da_entitlement_active"],
            ["unit_branch_2"],
        ),
    ]

    query["facts_ledger"]["predicate_layers"].update(
        {
            "g1_controlled": 3,
            "g1_prop": 3,
            "g2_controlled": 3,
            "g2_prop": 3,
        }
    )
    impact = query["target_impact_assessments"].pop(
        list(query["target_impact_assessments"].keys())[0]
    )
    impact["target_asset_id"] = target
    query["target_impact_assessments"] = {target: impact}

    catalog = tuple(
        item
        for item in load_catalog()
        if item.id in ("genericall_add_member", "propagate_group_entitlement")
    )
    facts = [
        RuntimeFact(
            "security_group",
            actor,
            g1,
            True,
            FactOrigin.DECLARED_ASSUMPTION,
            "horizon",
            rationale="test",
        ),
        RuntimeFact(
            "membership_change_allowed",
            actor,
            g1,
            True,
            FactOrigin.DECLARED_ASSUMPTION,
            "horizon",
            rationale="test",
        ),
        RuntimeFact(
            "directory_write_allowed",
            actor,
            g1,
            True,
            FactOrigin.DECLARED_ASSUMPTION,
            "horizon",
            rationale="test",
        ),
        RuntimeFact(
            "membership_usable",
            actor,
            g1,
            True,
            FactOrigin.DECLARED_ASSUMPTION,
            "horizon",
            rationale="test",
        ),
        RuntimeFact(
            "security_group",
            actor,
            g2,
            True,
            FactOrigin.DECLARED_ASSUMPTION,
            "horizon",
            rationale="test",
        ),
        RuntimeFact(
            "membership_change_allowed",
            actor,
            g2,
            True,
            FactOrigin.DECLARED_ASSUMPTION,
            "horizon",
            rationale="test",
        ),
        RuntimeFact(
            "directory_write_allowed",
            actor,
            g2,
            True,
            FactOrigin.DECLARED_ASSUMPTION,
            "horizon",
            rationale="test",
        ),
        RuntimeFact(
            "membership_usable",
            actor,
            g2,
            True,
            FactOrigin.DECLARED_ASSUMPTION,
            "horizon",
            rationale="test",
        ),
        RuntimeFact(
            "security_group",
            actor,
            target,
            True,
            FactOrigin.DECLARED_ASSUMPTION,
            "horizon",
            rationale="test",
        ),
        RuntimeFact(
            "membership_usable",
            actor,
            target,
            True,
            FactOrigin.DECLARED_ASSUMPTION,
            "horizon",
            rationale="test",
        ),
    ]
    bindings = {
        ("genericall_add_member", actor, actor, g1): "act_add_g1",
        ("propagate_group_entitlement", actor, actor, g1): "act_prop_g1",
        ("propagate_group_entitlement", actor, g1, target): "act_reach_target_g1",
        ("genericall_add_member", actor, actor, g2): "act_add_g2",
        ("propagate_group_entitlement", actor, actor, g2): "act_prop_g2",
        ("propagate_group_entitlement", actor, g2, target): "act_reach_target_g2",
    }

    # 1. Fail closed: candidate_id_lookup is forbidden in orchestration
    with pytest.raises(TypeError, match="unexpected keyword argument"):
        generate_and_evaluate_attack_paths(
            query,
            graph_dict,
            actor=actor,
            initial_state=AttackState(control={actor}, usable_identity={(actor, actor)}),
            runtime_context=RuntimeContext(facts, authentication_context=actor),
            budget=SearchBudget(max_paths=5, max_steps=3, max_expansions=100),
            action_bindings=bindings,
            catalog=catalog,
            scenario_reference="scenario-corp-test",
            success_state_predicate=lambda s: (actor, target) in s.effective_member,
            candidate_id_lookup={"dummy": "lookup"},
        )

    # 2. Real search generation + evaluation
    res = generate_and_evaluate_attack_paths(
        query,
        graph_dict,
        actor=actor,
        initial_state=AttackState(control={actor}, usable_identity={(actor, actor)}),
        runtime_context=RuntimeContext(facts, authentication_context=actor),
        budget=SearchBudget(max_paths=5, max_steps=3, max_expansions=100),
        action_bindings=bindings,
        catalog=catalog,
        scenario_reference="scenario-corp-test",
        success_state_predicate=lambda s: (actor, target) in s.effective_member,
    )
    out = res["roundtrip_result"]

    # Candidate identities in the evaluator are strictly generator-assigned
    assert list(out["eligible_candidates"].keys()) == ["generated_0001", "generated_0002"]
    assert out["eligible_candidates"]["generated_0001"]["effort"] == 2
    assert out["eligible_candidates"]["generated_0002"]["effort"] == 2

    # Equal-effort tie breaking uses (effort, candidate_id) -> generated_0001 wins
    assert out["pareto_frontier"] == ["generated_0001", "generated_0002"]
    assert out["min_effort_to_da_baseline"]["best_candidate_id"] == "generated_0001"
    assert out["min_effort_to_da_baseline"]["minimum_effort_value"] == 2

    # 3. Acceptance post-evaluation mapping:
    # Scheme A assigns 'cand_zebra' to generated_0001 and 'cand_apple' to generated_0002.
    # If oracle names had entered the evaluator, 'cand_apple' would have won over 'cand_zebra'
    # purely due to alphabetical sorting. Because ranking is decoupled, generated_0001 wins.
    case_a = {
        "kind": "positive",
        "expected": {
            "candidates": {
                "cand_zebra": {
                    "status": "feasible",
                    "effort": 2,
                    "likelihood_interval": ["18/25", "9/10"],
                    "impact": "Critical",
                },
                "cand_apple": {
                    "status": "feasible",
                    "effort": 2,
                    "likelihood_interval": ["18/25", "9/10"],
                    "impact": "Critical",
                },
            },
            "pareto_frontier": ["cand_zebra", "cand_apple"],
            "min_effort": {"best_candidate_id": "cand_zebra", "minimum_effort_value": 2},
        },
    }
    projection_a = {
        "candidates": [
            {
                "candidate_id": "cand_zebra",
                "bound_action_ids": ["act_add_g1", "act_prop_g1", "act_reach_target_g1"],
            },
            {
                "candidate_id": "cand_apple",
                "bound_action_ids": ["act_add_g2", "act_prop_g2", "act_reach_target_g2"],
            },
        ]
    }
    audit_a = case_expectation_audit(projection_a, case_a, out)
    assert audit_a["complete"] is True
    assert audit_a["min_effort_verified"] is True
    assert audit_a["mapped_min_effort_candidate_id"] == "cand_zebra"
    assert audit_a["frontier_verified"] is True
    assert audit_a["reviewed_candidate_mapping"] == {
        "generated_0001": "cand_zebra",
        "generated_0002": "cand_apple",
    }
