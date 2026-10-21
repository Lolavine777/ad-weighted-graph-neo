"""Unit tests for the Path Ranking Interface Specification v1.0.0.

Verifies input/output contract invariants, precision and serialization rules,
partitioning of diagnostics, conservative Pareto dominance, conditional effort
tie-breaking, separation of route traces from work ledger, separation of
min-effort-to-DA from the Pareto frontier, canonical Graph Contract 1.3 IDs,
wire adapter decoding/validation, facts contract predicate layering, and
evidence governance metrics.
"""

from __future__ import annotations

import json
from fractions import Fraction
from pathlib import Path

import pytest

from scripts.research.path_ranking_wire_adapter import (
    CANONICAL_EDGE_ID_PATTERN,
    CANONICAL_SID_PATTERN,
    canonical_edge_id,
    decode_ranking_query,
    evaluate_predicate_gates,
    execute_ranking_roundtrip,
    is_canonical_node_id,
    resolve_facts_ledger,
    validate_and_decode_bounds_table,
    validate_target_impact_assessments,
    validate_work_units_ledger,
)
from scripts.research.worked_example_validation import (
    ResearchAction,
    assess_scoped_program,
    bounded_programs,
    build_path_1_seamless_reset,
    risk_ineligibility,
    scoped_frontier,
    scoped_preference,
)
from src.engine.ranking.models import RankingValidationError
from src.engine.ranking.validation import (
    validate_work_units_ledger as canonical_validate_work_units_ledger,
)


def test_example_1_incomparability_tradeoff():
    """Example 1: Critical with lower likelihood vs High with higher likelihood."""
    cand_a = {
        "candidate_id": "Candidate_A",
        "impact": "Critical",
        "program": ("prep_kerberoast", "crack_ticket"),
        "likelihood_interval": (Fraction("1/10"), Fraction("2/10")),
        "effort": 3,
        "status": "feasible",
    }
    cand_b = {
        "candidate_id": "Candidate_B",
        "impact": "High",
        "program": ("prep_session_hijack", "pivot_dc"),
        "likelihood_interval": (Fraction("8/10"), Fraction("9/10")),
        "effort": 3,
        "status": "feasible",
    }
    assert scoped_preference(cand_a, cand_b) == "incomparable"
    assert scoped_preference(cand_b, cand_a) == "incomparable"

    frontier_res = scoped_frontier({"Candidate_A": cand_a, "Candidate_B": cand_b})
    assert set(frontier_res["frontier"]) == {"Candidate_A", "Candidate_B"}
    assert frontier_res["diagnostics"] == {}


def test_example_2_strict_dominance():
    """Example 2: Critical strictly dominates High when likelihood is also higher."""
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
        "effort": 2,  # Lower effort cannot compensate for worse risk axes
        "status": "feasible",
    }
    assert scoped_preference(cand_a, cand_c) == "a"
    assert scoped_preference(cand_c, cand_a) == "b"

    frontier_res = scoped_frontier({"Candidate_A": cand_a, "Candidate_C": cand_c})
    assert frontier_res["frontier"] == ["Candidate_A"]
    assert "Candidate_C" not in frontier_res["frontier"]


def test_example_3_point_tie_with_effort_tiebreak():
    """Example 3: Point-tie with effort breaks tie only when both are rated."""
    d1 = {
        "candidate_id": "D1",
        "impact": "High",
        "likelihood_interval": (Fraction("6/10"), Fraction("6/10")),
        "effort": 3,
        "status": "feasible",
    }
    d2 = {
        "candidate_id": "D2",
        "impact": "High",
        "likelihood_interval": (Fraction("6/10"), Fraction("6/10")),
        "effort": 5,
        "status": "feasible",
    }
    d3 = {
        "candidate_id": "D3",
        "impact": "High",
        "likelihood_interval": (Fraction("6/10"), Fraction("6/10")),
        "effort": 3,
        "status": "feasible",
    }
    assert scoped_preference(d1, d2) == "a"
    assert scoped_preference(d2, d1) == "b"
    assert scoped_preference(d1, d3) == "tie"

    frontier_res = scoped_frontier({"D1": d1, "D2": d2, "D3": d3})
    assert set(frontier_res["frontier"]) == {"D1", "D3"}
    assert "D2" not in frontier_res["frontier"]


def test_example_4_point_tie_unrated_effort():
    """Example 4: Point-tie with unrated effort remains incomparable."""
    e1 = {
        "candidate_id": "E1",
        "impact": "High",
        "likelihood_interval": (Fraction("6/10"), Fraction("6/10")),
        "effort": 3,
        "status": "feasible",
    }
    e2 = {
        "candidate_id": "E2",
        "impact": "High",
        "likelihood_interval": (Fraction("6/10"), Fraction("6/10")),
        "effort": None,
        "effort_status": "unrated",
        "status": "feasible",
    }
    assert scoped_preference(e1, e2) == "incomparable"
    assert scoped_preference(e2, e1) == "incomparable"

    frontier_res = scoped_frontier({"E1": e1, "E2": e2})
    assert set(frontier_res["frontier"]) == {"E1", "E2"}


def test_example_5_diagnostics_partitioning():
    """Example 5: Blocked, unknown, likelihood_unrated, and impact_unrated via gate evaluator."""
    reset, activate, _, _ = build_path_1_seamless_reset().steps
    units = {
        "reset": reset,
        "activate": activate,
    }
    conditional_bounds = {
        ("reset",): (0.8, 0.9),
        ("reset", "activate"): (0.6, 0.7),
    }

    # F1 evaluated through gate evaluator with False (blocked, withholding likelihood and effort)
    f1_assessed = assess_scoped_program(
        packets=[("reset", "activate")],
        units=units,
        conditional_bounds=conditional_bounds,
        gates=(False,),
    )
    # F2 evaluated through gate evaluator with Unknown (unknown, withholding likelihood and effort)
    f2_assessed = assess_scoped_program(
        packets=[("reset", "activate")],
        units=units,
        conditional_bounds=conditional_bounds,
        gates=("Unknown",),
    )
    # F3 feasible but missing conditional bounds (likelihood_unrated)
    f3_assessed = assess_scoped_program(
        packets=[("reset", "activate")],
        units=units,
        conditional_bounds={},
        gates=(True,),
    )
    # F4 feasible with valid likelihood but unrated business impact
    f4_assessed = assess_scoped_program(
        packets=[("reset", "activate")],
        units=units,
        conditional_bounds=conditional_bounds,
        gates=(True,),
    )

    f1 = {"candidate_id": "F1", "impact": "High", **f1_assessed}
    f2 = {"candidate_id": "F2", "impact": "High", **f2_assessed}
    f3 = {"candidate_id": "F3", "impact": "High", **f3_assessed}
    f4 = {"candidate_id": "F4", "impact": None, **f4_assessed}

    assert risk_ineligibility(f1) == ["blocked", "likelihood_unrated"]
    assert risk_ineligibility(f2) == ["unknown", "likelihood_unrated"]
    assert risk_ineligibility(f3) == ["likelihood_unrated"]
    assert risk_ineligibility(f4) == ["impact_unrated"]

    # Ineligible comparisons return "not_eligible", not "incomparable"
    assert scoped_preference(f1, f2) == "not_eligible"
    assert scoped_preference(f3, f4) == "not_eligible"

    candidates = {"F1": f1, "F2": f2, "F3": f3, "F4": f4}
    res = scoped_frontier(candidates)
    assert res["eligible"] == {}
    assert res["frontier"] == []
    assert set(res["diagnostics"].keys()) == {"F1", "F2", "F3", "F4"}
    assert res["diagnostics"]["F1"]["reasons"] == ["blocked", "likelihood_unrated"]
    assert res["diagnostics"]["F2"]["reasons"] == ["unknown", "likelihood_unrated"]
    assert res["diagnostics"]["F3"]["reasons"] == ["likelihood_unrated"]
    assert res["diagnostics"]["F4"]["reasons"] == ["impact_unrated"]


def test_example_6_split_merged_canonical_work_ledger():
    """Example 6: Split and merged action representations share the same persistent work units."""
    reset, activate, _, _ = build_path_1_seamless_reset().steps
    units = {
        "reset": reset,  # t1=1, t2=3 -> cost: 1+3-2 = 2
        "activate": activate,  # t1=1, t2=2 -> cost: 1+2-2 = 1
    }
    conditional_bounds = {
        ("reset",): (0.8, 0.9),
        ("reset", "activate"): (0.6, 0.7),
    }

    split_res = assess_scoped_program(
        packets=[("reset",), ("activate",), ()],
        units=units,
        conditional_bounds=conditional_bounds,
    )
    merged_res = assess_scoped_program(
        packets=[("reset", "activate")],
        units=units,
        conditional_bounds=conditional_bounds,
    )

    assert split_res["program"] == ("reset", "activate")
    assert merged_res["program"] == ("reset", "activate")
    assert split_res["effort"] == 3
    assert merged_res["effort"] == 3
    assert split_res["status"] == "feasible"
    assert merged_res["status"] == "feasible"
    assert split_res["likelihood_interval"] == (Fraction("12/25"), Fraction("63/100"))
    assert merged_res["likelihood_interval"] == (Fraction("12/25"), Fraction("63/100"))

    # When both are evaluated for preference:
    split_eval = {
        "candidate_id": "Split",
        "impact": "High",
        "likelihood_interval": split_res["likelihood_interval"],
        "effort": split_res["effort"],
        "status": split_res["status"],
    }
    merged_eval = {
        "candidate_id": "Merged",
        "impact": "High",
        "likelihood_interval": merged_res["likelihood_interval"],
        "effort": merged_res["effort"],
        "status": merged_res["status"],
    }
    # Non-point identical intervals remain incomparable
    assert scoped_preference(split_eval, merged_eval) == "incomparable"

    # Packaging equivalence: both candidates co-exist on the Pareto frontier
    frontier_res = scoped_frontier({"Split": split_eval, "Merged": merged_eval})
    assert set(frontier_res["frontier"]) == {"Split", "Merged"}


def test_example_7_min_effort_to_da_vs_pareto_frontier():
    """Example 7: Min-effort-to-DA baseline is distinct from the Pareto frontier."""
    cheap_cand = {
        "candidate_id": "Cheap_Goal",
        "impact": "High",
        "likelihood_interval": (Fraction("2/10"), Fraction("2/10")),
        "effort": 1,
        "status": "feasible",
    }
    shared_cand = {
        "candidate_id": "Shared_Goal",
        "impact": "High",
        "likelihood_interval": (Fraction("648/1000"), Fraction("648/1000")),
        "effort": 8,
        "status": "feasible",
    }
    # Shared dominates Cheap on likelihood (0.648 > 0.20) with identical impact
    assert scoped_preference(shared_cand, cheap_cand) == "a"

    frontier_res = scoped_frontier({"Cheap": cheap_cand, "Shared": shared_cand})
    # Pareto frontier retains only Shared
    assert frontier_res["frontier"] == ["Shared"]

    # Separate Min-Effort-to-DA query independently identifies Cheap as the minimum effort baseline
    candidates = [cheap_cand, shared_cand]
    min_effort_cand = min(
        (c for c in candidates if c["status"] == "feasible" and c["effort"] is not None),
        key=lambda c: c["effort"],
    )
    assert min_effort_cand["candidate_id"] == "Cheap_Goal"
    assert min_effort_cand["effort"] == 1


def test_route_trace_preservation_contract():
    """Verify multiple routes map to same program while preserving traces and canonical IDs."""
    sid_src = "S-1-5-21-3623811015-3361044348-30300820-1001"
    sid_dc1 = "S-1-5-21-3623811015-3361044348-30300820-1000"
    sid_dc2 = "S-1-5-21-3623811015-3361044348-30300820-2001"
    sid_da = "S-1-5-21-3623811015-3361044348-30300820-500"

    edge_1 = canonical_edge_id(sid_src, sid_dc1, "MemberOf")
    edge_2 = canonical_edge_id(sid_dc1, sid_da, "GenericAll")
    edge_3 = canonical_edge_id(sid_src, sid_dc2, "MemberOf")
    edge_4 = canonical_edge_id(sid_dc2, sid_da, "GenericAll")

    # Two distinct structural routes using Graph Contract 1.3 canonical SIDs and SHA-256 edge IDs
    route_1 = {
        "route_id": "route_dc1",
        "node_ids": [sid_src, sid_dc1, sid_da],
        "edge_ids": [edge_1, edge_2],
        "provenance_locators": ["#/computers/0", "#/users/1"],
    }
    route_2 = {
        "route_id": "route_dc2",
        "node_ids": [sid_src, sid_dc2, sid_da],
        "edge_ids": [edge_3, edge_4],
        "provenance_locators": ["#/computers/1", "#/users/1"],
    }

    # Verify ID patterns comply strictly with Graph Contract 1.3
    for route in (route_1, route_2):
        for nid in route["node_ids"]:
            assert CANONICAL_SID_PATTERN.match(nid), f"Node SID {nid} invalid"
        for eid in route["edge_ids"]:
            assert CANONICAL_EDGE_ID_PATTERN.match(eid), f"Edge ID {eid} invalid"

    program = ("work_reset_da", "work_logon_da")
    candidate = {
        "candidate_id": "cand_da_reset",
        "program": program,
        "structural_routes": [route_1, route_2],
        "route_count": 2,
    }

    assert len(candidate["structural_routes"]) == 2
    assert (
        candidate["structural_routes"][0]["route_id"]
        != candidate["structural_routes"][1]["route_id"]
    )
    # Verify program is 1 tuple, but route traces are preserved as 2 distinct items
    assert candidate["route_count"] == 2
    assert len(candidate["program"]) == 2


def test_numeric_precision_fraction_multiplication():
    """Verify that exact rational arithmetic avoids float rounding false dominance."""
    factors = [0.2, 0.3, 0.4]
    p1 = Fraction(str(factors[0])) * Fraction(str(factors[1])) * Fraction(str(factors[2]))
    p2 = Fraction(str(factors[2])) * Fraction(str(factors[1])) * Fraction(str(factors[0]))

    assert p1 == p2 == Fraction(3, 125)

    # String serialization check
    serialized = f"{p1.numerator}/{p1.denominator}"
    assert serialized == "3/125"
    deserialized = Fraction(serialized)
    assert deserialized == p1


def test_bounded_programs_truncation_reporting():
    """Verify that bounded_programs accurately reports truncation when work budget is exceeded."""
    actions = [
        ResearchAction(
            name="prep",
            requires=frozenset({"foothold"}),
            adds=frozenset({"prepared"}),
            units=("unit_prep",),
        ),
        ResearchAction(
            name="step1",
            requires=frozenset({"prepared"}),
            adds=frozenset({"cap_a"}),
            units=("unit_a",),
        ),
        ResearchAction(
            name="finish",
            requires=frozenset({"cap_a"}),
            adds=frozenset({"goal"}),
            units=("unit_finish",),
        ),
    ]
    # Budget 2 is not enough to complete prep (1) + step1 (1) + finish (1) = 3 units
    res_b2 = bounded_programs(
        initial={"foothold"},
        goal={"goal"},
        actions=actions,
        max_work_units=2,
    )
    assert res_b2["programs"] == []
    assert res_b2["truncated"] is True

    # Budget 3 completes the program
    res_b3 = bounded_programs(
        initial={"foothold"},
        goal={"goal"},
        actions=actions,
        max_work_units=3,
    )
    assert len(res_b3["programs"]) == 1
    assert res_b3["programs"][0] == ("unit_prep", "unit_a", "unit_finish")
    assert res_b3["truncated"] is False


def test_wire_adapter_bounds_table_and_impact_parsing():
    """Wire bounds validation, duplicate checks, and full JSON roundtrip."""
    # 1. Inverted bounds validation (lower > upper)
    inverted_bounds = [{"prefix": ["step_a"], "lower": "9/10", "upper": "1/10"}]
    with pytest.raises(ValueError, match="is invalid: must satisfy 0 <= lower <= upper <= 1"):
        validate_and_decode_bounds_table(inverted_bounds)

    # 2. Out-of-range bounds validation (< 0 or > 1)
    out_of_range_bounds = [{"prefix": ["step_a"], "lower": "2", "upper": "3"}]
    with pytest.raises(ValueError, match="is invalid: must satisfy 0 <= lower <= upper <= 1"):
        validate_and_decode_bounds_table(out_of_range_bounds)

    # 3. Malformed prefix non-string rejection (no coercion healing)
    with pytest.raises(TypeError, match="must be a non-empty string"):
        validate_and_decode_bounds_table([{"prefix": [None, 7], "lower": "1/2", "upper": "1/2"}])
    with pytest.raises(TypeError, match="must be a non-empty string"):
        validate_and_decode_bounds_table(
            [{"prefix": ["step_a", 7], "lower": "1/2", "upper": "1/2"}]
        )

    # 4. Reject duplicate prefix
    duplicate_prefix = [
        {"prefix": ["step_a"], "lower": "1/10", "upper": "2/10"},
        {"prefix": ["step_a"], "lower": "5/10", "upper": "6/10"},
    ]
    with pytest.raises(ValueError, match="DuplicatePrefixError"):
        validate_and_decode_bounds_table(duplicate_prefix)

    # 5. Valid impact assessments
    dc_sid = "S-1-5-21-3623811015-3361044348-30300820-1000"
    user_sid = "S-1-5-21-3623811015-3361044348-30300820-1001"
    da_sid = "S-1-5-21-3623811015-3361044348-30300820-500"

    valid_rated = {
        dc_sid: {
            "target_asset_id": dc_sid,
            "rating_status": "rated",
            "consequence_rating": "Critical",
        }
    }
    validate_target_impact_assessments(valid_rated)

    valid_unrated = {
        da_sid: {
            "target_asset_id": da_sid,
            "rating_status": "unrated",
            "consequence_rating": None,
            "missing_basis_reasons": ["unrated_target_asset"],
        }
    }
    validate_target_impact_assessments(valid_unrated)

    # 6. Invalid impact label ("Tier0") and invalid canonical ID
    invalid_ontology_label = {
        dc_sid: {
            "target_asset_id": dc_sid,
            "rating_status": "rated",
            "consequence_rating": "Tier0",
        }
    }
    with pytest.raises(ValueError, match="invalid consequence_rating 'Tier0'"):
        validate_target_impact_assessments(invalid_ontology_label)

    with pytest.raises(ValueError, match="not a valid canonical node ID"):
        validate_target_impact_assessments(
            {"dc01": {"rating_status": "rated", "consequence_rating": "High"}}
        )

    # 7. Query decoding: missing required top-level component
    incomplete_query = json.dumps({"query_metadata": {}})
    with pytest.raises(ValueError, match="Missing required top-level query component"):
        decode_ranking_query(incomplete_query)

    # 8. Query decoding: invalid metadata validation
    invalid_meta_query = json.dumps(
        {
            "query_metadata": {
                "query_id": "q1",
                "version": "1.0.0",
                "scenario_id": "s1",
                "scenario_version": "1.0.0",
                "snapshot_id": "bare_hex_without_sha256_prefix",
                "evaluation_mode": "scenario",
                "work_boundary": "corp",
                "foothold_node_id": user_sid,
                "target_goal": {"goal_id": "S2", "required_predicates": ["target_controlled"]},
                "horizon": "72h",
                "active_work_budget": -1,
            },
            "facts_ledger": {"observed_facts": []},
            "bound_actions": [],
            "work_units_ledger": {},
            "conditional_bounds_table": [],
            "target_impact_assessments": {},
        }
    )
    with pytest.raises(ValueError, match="Invalid snapshot_id"):
        decode_ranking_query(invalid_meta_query)

    # 9. Full JSON wire query roundtrip with non-terminating rational (1/3)
    # and multiple candidate outcomes (feasible, blocked, unknown)
    query_payload = {
        "query_metadata": {
            "query_id": "query-20260930-s2-synthetic-001",
            "version": "1.0.0",
            "scenario_id": "scenario-corp-compromised-host",
            "scenario_version": "1.0.0",
            "snapshot_id": (
                "sha256:e0601d763eeea285d268ec9e468d321c50c9d7faba53c8e7442a2fcc4159c812"
            ),
            "evaluation_mode": "scenario",
            "work_boundary": "corp_boundary",
            "foothold_node_id": user_sid,
            "target_goal": {
                "goal_id": "S2",
                "description": "Domain Administrator access",
                "required_predicates": ["target_controlled"],
            },
            "horizon": "business_hours_72h",
            "active_work_budget": 4,
            "coverage": {
                "completeness_scope": "budget_bounded",
                "is_truncated": False,
                "truncation_reasons": [],
            },
        },
        "work_units_ledger": {
            "reset": {
                "work_unit_id": "reset",
                "rating_status": "rated",
                "rubric_scores": {"t1": 1, "t2": 3, "formula": "base", "computed_cost": 2},
                "overlap_state": "independent",
            },
            "activate": {
                "work_unit_id": "activate",
                "rating_status": "rated",
                "rubric_scores": {"t1": 1, "t2": 2, "formula": "base", "computed_cost": 1},
                "overlap_state": "independent",
            },
        },
        "bound_actions": [
            {
                "action_id": "action_reset",
                "actor_id": user_sid,
                "target_id": dc_sid,
                "requires": ["structural_genericall"],
                "adds": ["pwd_reset_done"],
                "referenced_work_unit_ids": ["reset"],
                "is_passive_closure": False,
                "edge_id": canonical_edge_id(user_sid, dc_sid, "MemberOf"),
            },
            {
                "action_id": "action_activate",
                "actor_id": dc_sid,
                "target_id": da_sid,
                "requires": ["session_present"],
                "adds": ["target_controlled"],
                "referenced_work_unit_ids": ["activate"],
                "is_passive_closure": False,
                "edge_id": canonical_edge_id(dc_sid, da_sid, "GenericAll"),
            },
        ],
        "conditional_bounds_table": [
            {"prefix": ["reset"], "lower": "1/3", "upper": "1/3"},
            {"prefix": ["reset", "activate"], "lower": "1/3", "upper": "1/3"},
        ],
        "target_impact_assessments": {
            dc_sid: {
                "target_asset_id": dc_sid,
                "rating_status": "rated",
                "consequence_rating": "Critical",
            },
            da_sid: {
                "target_asset_id": da_sid,
                "rating_status": "rated",
                "consequence_rating": "High",
            },
        },
        "facts_ledger": {
            "observed_facts": [
                {
                    "predicate": "structural_genericall",
                    "layer": 1,
                    "truth_value": True,
                    "provenance_reference": (
                        "sha256:1111111111111111111111111111111111111111111111111111111111111111"
                    ),
                },
            ],
            "false_facts": [
                {"predicate": "firewall_blocked", "layer": 2, "truth_value": False},
            ],
            "assumed_facts": [
                {
                    "predicate": "session_present",
                    "layer": 3,
                    "truth_value": True,
                    "rationale": "Active administrator session",
                }
            ],
            "unknown_facts": [{"predicate": "missing_telemetry_probe", "layer": 2}],
            "predicate_layers": {"pwd_reset_done": 3, "target_controlled": 3},
        },
    }

    query_json_str = json.dumps(query_payload, indent=2)

    edge_1 = canonical_edge_id(user_sid, dc_sid, "MemberOf")
    edge_2 = canonical_edge_id(dc_sid, da_sid, "GenericAll")
    routes = [
        {
            "route_id": "route_dc1",
            "node_ids": [user_sid, dc_sid, da_sid],
            "edge_ids": [edge_1, edge_2],
            "provenance_locators": ["#/computers/0", "#/users/1"],
        }
    ]

    candidates = [
        # Feasible candidate: predicates satisfied, non-terminating 1/3 bounds
        {
            "candidate_id": "Cand_Feasible",
            "target_asset_id": dc_sid,
            "bound_action_ids": ["action_reset", "action_activate"],
            "structural_routes": routes,
        },
        # Blocked candidate: firewall_blocked is observed False
        {
            "candidate_id": "Cand_Blocked",
            "target_asset_id": dc_sid,
            "bound_action_ids": ["action_reset"],
            "required_predicates": ["firewall_blocked"],
            "structural_routes": routes,
        },
        # Unknown candidate: missing telemetry probe
        {
            "candidate_id": "Cand_Unknown",
            "target_asset_id": da_sid,
            "bound_action_ids": ["action_reset", "action_activate"],
            "required_predicates": ["missing_telemetry_probe"],
            "structural_routes": routes,
        },
    ]

    roundtrip = execute_ranking_roundtrip(query_json_str, candidates)
    res_payload = roundtrip["roundtrip_result"]

    # 1. Feasible candidate on Pareto frontier (Spec 3.3: frontier is list of candidate IDs)
    frontier_ids = res_payload["pareto_frontier"]
    assert frontier_ids == ["Cand_Feasible"]
    feasible_cand = res_payload["eligible_candidates"]["Cand_Feasible"]
    assert feasible_cand["candidate_id"] == "Cand_Feasible"
    # Exact non-terminating rational 1/3 * 1/3 = 1/9, lossless serialization!
    assert feasible_cand["likelihood_interval"] == ["1/9", "1/9"]
    assert feasible_cand["consequence_rating"] == "Critical"
    assert feasible_cand["nominal_effort"] == 3
    assert feasible_cand["status"] == "feasible"
    assert feasible_cand["program"] == ["reset", "activate"]
    assert feasible_cand["unrated_work_units"] == []
    assert (
        feasible_cand["likelihood_basis_summary"]
        == "Derived from prefix conditional bounds product"
    )

    # 2. Structural route preservation through the adaptation boundary
    route_out = feasible_cand["structural_routes"][0]
    assert route_out["route_id"] == "route_dc1"
    assert route_out["node_ids"] == [user_sid, dc_sid, da_sid]
    assert route_out["edge_ids"] == [edge_1, edge_2]
    assert CANONICAL_EDGE_ID_PATTERN.match(route_out["edge_ids"][0])
    assert CANONICAL_EDGE_ID_PATTERN.match(route_out["edge_ids"][1])

    # 3. Diagnostics partitioned properly as a map (Spec 3.3)
    diag_cands = res_payload["diagnostics"]
    assert isinstance(diag_cands, dict)
    assert "Cand_Blocked" in diag_cands
    assert "blocked" in diag_cands["Cand_Blocked"]["reasons"]
    assert (
        diag_cands["Cand_Blocked"]["assessment"]["gates_evaluation"]["firewall_blocked"] == "False"
    )

    assert "Cand_Unknown" in diag_cands
    assert "unknown" in diag_cands["Cand_Unknown"]["reasons"]
    assert (
        diag_cands["Cand_Unknown"]["assessment"]["gates_evaluation"]["missing_telemetry_probe"]
        == "Unknown"
    )

    # 4. Search metadata and min_effort_to_da_baseline (Spec 3.1, 3.4)
    search_meta = res_payload["search_metadata"]
    assert search_meta["budget_limit"] == 4
    assert search_meta["candidates_evaluated"] == 3
    assert search_meta["is_truncated"] is False
    assert search_meta["truncation_reasons"] == []
    assert search_meta["completeness_scope"] == "budget_bounded"
    assert search_meta["caps_applied"]["max_active_work_budget"] == 4

    baseline = res_payload["min_effort_to_da_baseline"]
    assert baseline["goal_id"] == "S2"
    assert baseline["best_candidate_id"] == "Cand_Feasible"
    assert baseline["minimum_effort_value"] == 3
    assert baseline["associated_likelihood_interval"] == ["1/9", "1/9"]
    assert baseline["associated_impact"] == "Critical"


def test_governance_iou_and_agreement_metrics():
    """Finding 6 & 5: Inter-rater agreement IoU edge cases and degenerate Kappa fallback."""

    from scripts.research.path_ranking_wire_adapter import (
        check_epistemic_uncertainty,
        compute_interval_iou,
        compute_kappa_with_fallback,
    )

    compute_iou = compute_interval_iou

    # 0. Mismatched rating lengths fail-closed
    with pytest.raises(ValueError, match="Mismatched rating lengths for Kappa calculation"):
        compute_kappa_with_fallback(["Low"], ["Low", "High"])

    # 1. Identical point bounds
    assert compute_iou((0.6, 0.6), (0.6, 0.6)) == 1.0

    # 2. Distinct point bounds
    assert compute_iou((0.6, 0.6), (0.8, 0.8)) == 0.0

    # 3. Overlapping interval bounds
    iou_overlap = compute_iou((0.6, 0.8), (0.7, 0.9))
    assert abs(iou_overlap - (1.0 / 3.0)) < 1e-6

    # 4. High epistemic uncertainty flag
    assert check_epistemic_uncertainty((0.1, 0.8)) is True
    assert check_epistemic_uncertainty((0.6, 0.7)) is False

    # 5. Empty rating set (N = 0)
    empty_res = compute_kappa_with_fallback([], [])
    assert empty_res["status"] == "empty_ratings"
    assert empty_res["kappa"] is None

    # 6. Small sample size with diverse categories (N = 3, Kappa mathematically defined = 1.0)
    rater_a = ["Low", "High", "Critical"]
    rater_b = ["Low", "High", "Critical"]
    small_res = compute_kappa_with_fallback(rater_a, rater_b)
    assert small_res["status"] == "valid"
    assert small_res["kappa"] == 1.0
    assert small_res["small_sample_size_warning"] is True

    # 7. Degenerate Kappa zero-variance case (all Critical, denominator = 0)
    rater_all_crit_1 = ["Critical", "Critical", "Critical", "Critical"]
    rater_all_crit_2 = ["Critical", "Critical", "Critical", "Critical"]
    deg_res = compute_kappa_with_fallback(rater_all_crit_1, rater_all_crit_2)
    assert deg_res["kappa"] is None
    assert deg_res["status"] == "degenerate_zero_variance"
    assert deg_res["observed_agreement"] == 1.0
    assert deg_res["confusion_matrix"]["Critical"]["Critical"] == 4


def test_facts_ledger_predicate_layering_precedence():
    """Observation reconciliation, conflict disposition, false_facts, and predicate layering."""
    # 1. Observation conflict: snapshot has both True and False observations for LDAP access
    facts_with_conflict = {
        "observed_facts": [
            {"predicate": "ldap_port_accessible", "layer": 2, "truth_value": True},
            {"predicate": "ldap_port_accessible", "layer": 2, "truth_value": False},
        ],
        "assumed_facts": [
            {
                "predicate": "ldap_port_accessible",
                "layer": 2,
                "truth_value": True,
                "rationale": "Assumed open",
            }
        ],
    }
    resolved_conflict = resolve_facts_ledger(facts_with_conflict, evaluation_mode="scenario")
    # Conflict cannot be overridden by assumption;
    # must resolve to Unknown with contradictory_telemetry
    assert resolved_conflict["ldap_port_accessible"]["value"] == "Unknown"
    assert resolved_conflict["ldap_port_accessible"]["disposition"] == "contradictory_telemetry"

    # 2. Known-False veto: false_facts vetoes assumption
    facts_with_false_bucket = {
        "false_facts": [{"predicate": "enabled", "layer": 3, "truth_value": False}],
        "assumed_facts": [
            {
                "predicate": "enabled",
                "layer": 3,
                "truth_value": True,
                "rationale": "fixture",
            }
        ],
    }
    resolved_false_bucket = resolve_facts_ledger(
        facts_with_false_bucket, evaluation_mode="scenario"
    )
    assert resolved_false_bucket["enabled"]["value"] == "False"
    assert resolved_false_bucket["enabled"]["disposition"] == "observed_false_veto"

    # 3. false_facts alone: predicate does NOT disappear from ledger
    facts_false_alone = {
        "false_facts": [{"predicate": "smb_disabled", "layer": 2, "truth_value": False}],
    }
    resolved_false_alone = resolve_facts_ledger(facts_false_alone, evaluation_mode="scenario")
    assert "smb_disabled" in resolved_false_alone
    assert resolved_false_alone["smb_disabled"]["value"] == "False"
    assert resolved_false_alone["smb_disabled"]["disposition"] == "observed_false_veto"

    # 4. unknown_facts alone: predicate does NOT disappear from ledger
    facts_unknown_alone = {
        "unknown_facts": [{"predicate": "custom_audit", "layer": 3, "reason": "Missing telemetry"}],
    }
    resolved_unknown_alone = resolve_facts_ledger(facts_unknown_alone, evaluation_mode="scenario")
    assert "custom_audit" in resolved_unknown_alone
    assert resolved_unknown_alone["custom_audit"]["value"] == "Unknown"
    assert resolved_unknown_alone["custom_audit"]["disposition"] == "declared_unknown_fact"

    # 5. Strict boolean truth_value validation
    with pytest.raises(TypeError, match="truth_value must be a boolean"):
        resolve_facts_ledger(
            {"observed_facts": [{"predicate": "p", "layer": 2, "truth_value": "False"}]}
        )
    with pytest.raises(TypeError, match="truth_value must be a boolean"):
        resolve_facts_ledger(
            {"observed_facts": [{"predicate": "p", "layer": 2, "truth_value": "True"}]}
        )
    with pytest.raises(ValueError, match="cannot have truth_value True"):
        resolve_facts_ledger({"false_facts": [{"predicate": "p", "layer": 2, "truth_value": True}]})

    # 6. Assumption truth_value: False resolves to False, never True
    facts_assumed_false = {
        "assumed_facts": [
            {
                "predicate": "user_present",
                "layer": 3,
                "truth_value": False,
                "rationale": "User assumed away",
            }
        ]
    }
    resolved_assumed_false = resolve_facts_ledger(facts_assumed_false, evaluation_mode="scenario")
    assert resolved_assumed_false["user_present"]["value"] == "False"
    assert resolved_assumed_false["user_present"]["disposition"] == "assumed_false"

    # 7. Layer 1 Structural Authorization: missing provenance reference -> Unknown (never verified!)
    facts_layer1_unverified = {
        "observed_facts": [{"predicate": "admin_to", "layer": 1, "truth_value": True}],
    }
    resolved_l1_unverified = resolve_facts_ledger(
        facts_layer1_unverified, evaluation_mode="scenario"
    )
    assert resolved_l1_unverified["admin_to"]["value"] == "Unknown"
    assert resolved_l1_unverified["admin_to"]["disposition"] == "missing_structural_provenance"

    # 8. Layer 1 with valid provenance reference -> structural_provenance_verified
    facts_layer1_verified = {
        "observed_facts": [
            {
                "predicate": "admin_to",
                "layer": 1,
                "truth_value": True,
                "provenance_reference": (
                    "sha256:abcdabcdabcdabcdabcdabcdabcdabcdabcdabcdabcdabcdabcdabcdabcdabcd"
                ),
            }
        ],
    }
    resolved_l1_verified = resolve_facts_ledger(facts_layer1_verified, evaluation_mode="scenario")
    assert resolved_l1_verified["admin_to"]["value"] == "True"
    assert resolved_l1_verified["admin_to"]["disposition"] == "structural_provenance_verified"

    # 9. Layer 3 in evidence_only mode: assumptions ignored -> Unknown
    facts_layer3 = {
        "observed_facts": [],
        "assumed_facts": [
            {
                "predicate": "session_present",
                "layer": 3,
                "truth_value": True,
                "rationale": "Assumed admin logon",
            }
        ],
    }
    resolved_evidence_only = resolve_facts_ledger(facts_layer3, evaluation_mode="evidence_only")
    assert resolved_evidence_only["session_present"]["value"] == "Unknown"
    assert (
        resolved_evidence_only["session_present"]["disposition"]
        == "evidence_only_disallows_assumptions"
    )

    # 10. Layer 3 in scenario mode: assumption accepted when no negative observation
    resolved_scenario = resolve_facts_ledger(facts_layer3, evaluation_mode="scenario")
    assert resolved_scenario["session_present"]["value"] == "True"
    assert resolved_scenario["session_present"]["disposition"] == "permitted_runtime_assumption"

    # 11. Missing predicate not mentioned in observations or assumptions
    facts_empty = {
        "observed_facts": [],
        "assumed_facts": [],
        "predicate_layers": {"unseen_pred": 3},
    }
    resolved_missing = resolve_facts_ledger(facts_empty, evaluation_mode="scenario")
    assert resolved_missing["unseen_pred"]["value"] == "Unknown"
    assert resolved_missing["unseen_pred"]["disposition"] == "missing_runtime_context"

    # 12. Gate evaluation precedence: False > Unknown > True
    res_map_blocked = {
        "p1": {"value": "True"},
        "p2": {"value": "False"},
        "p3": {"value": "Unknown"},
    }
    assert evaluate_predicate_gates(res_map_blocked, ["p1", "p2", "p3"]) == "blocked"

    res_map_unknown = {
        "p1": {"value": "True"},
        "p2": {"value": "Unknown"},
        "p3": {"value": "True"},
    }
    assert evaluate_predicate_gates(res_map_unknown, ["p1", "p2", "p3"]) == "unknown"

    res_map_feasible = {
        "p1": {"value": "True"},
        "p2": {"value": "True"},
        "p3": {"value": "True"},
    }
    assert evaluate_predicate_gates(res_map_feasible, ["p1", "p2", "p3"]) == "feasible"


def test_predicate_layer_authoritative_conflict_and_order_invariance():
    """Finding 1 (P1): Authoritative predicate layer registry and conflict rejection.

    Verifies:
    - Declaring layer 3 assumption on layer 1 predicate raises ValueError.
    - Conflicting layers across observed records for same predicate raises
      ValueError in both orders.
    - Layer 1 predicates without positive snapshot provenance resolve to Unknown.
    - Assumptions on Layer 1 can never convert it to True.
    """
    # 1. Authoritative predicate_layers conflicts with assumed_facts layer declaration
    conflict_payload = {
        "predicate_layers": {"replication_authorization": 1},
        "assumed_facts": [
            {
                "predicate": "replication_authorization",
                "layer": 3,
                "truth_value": True,
                "rationale": "fixture assumption",
            }
        ],
    }
    with pytest.raises(ValueError, match="Conflicting layer declaration for predicate"):
        resolve_facts_ledger(conflict_payload, evaluation_mode="scenario")

    # 2. Conflicting layers across multiple records for the same predicate: Order A
    conflict_records_a = {
        "observed_facts": [
            {"predicate": "admin_to", "layer": 1, "truth_value": True},
            {"predicate": "admin_to", "layer": 3, "truth_value": True},
        ]
    }
    with pytest.raises(ValueError, match="Conflicting layer declaration for predicate"):
        resolve_facts_ledger(conflict_records_a, evaluation_mode="scenario")

    # 3. Conflicting layers across multiple records for the same predicate: Order B (swapped)
    conflict_records_b = {
        "observed_facts": [
            {"predicate": "admin_to", "layer": 3, "truth_value": True},
            {"predicate": "admin_to", "layer": 1, "truth_value": True},
        ]
    }
    with pytest.raises(ValueError, match="Conflicting layer declaration for predicate"):
        resolve_facts_ledger(conflict_records_b, evaluation_mode="scenario")

    # 4. Layer 1 predicate without provenance in snapshot -> Unknown
    l1_no_prov = {
        "predicate_layers": {"replication_authorization": 1},
        "observed_facts": [{"predicate": "replication_authorization", "truth_value": True}],
    }
    res_l1_no_prov = resolve_facts_ledger(l1_no_prov, evaluation_mode="scenario")
    assert res_l1_no_prov["replication_authorization"]["value"] == "Unknown"
    assert (
        res_l1_no_prov["replication_authorization"]["disposition"]
        == "missing_structural_provenance"
    )

    # 5. Assumption on Layer 1 (even with matching layer 1) cannot satisfy provenance
    l1_assumed = {
        "predicate_layers": {"replication_authorization": 1},
        "assumed_facts": [
            {
                "predicate": "replication_authorization",
                "layer": 1,
                "truth_value": True,
                "rationale": "assume Gate O",
            }
        ],
    }
    res_l1_assumed = resolve_facts_ledger(l1_assumed, evaluation_mode="scenario")
    assert res_l1_assumed["replication_authorization"]["value"] == "Unknown"
    assert (
        res_l1_assumed["replication_authorization"]["disposition"]
        == "missing_structural_provenance"
    )


def test_action_catalog_requirements_enforced_in_candidate_assessment():
    """Finding 2 (P1): Action requirements enforced even when candidate omits required_predicates.

    Verifies:
    - If a bound action requires a predicate that resolves to False (e.g. firewall_blocked),
      candidate assessment status evaluates to blocked and candidate is partitioned
      into diagnostics.
    """
    user_sid = "S-1-5-21-3623811015-3361044348-30300820-1001"
    dc_sid = "S-1-5-21-3623811015-3361044348-30300820-1000"

    query_payload = {
        "query_metadata": {
            "query_id": "query-action-catalog-test",
            "version": "1.0.0",
            "scenario_id": "scenario-test",
            "scenario_version": "1.0.0",
            "snapshot_id": (
                "sha256:e0601d763eeea285d268ec9e468d321c50c9d7faba53c8e7442a2fcc4159c812"
            ),
            "evaluation_mode": "scenario",
            "work_boundary": "corp_boundary",
            "foothold_node_id": user_sid,
            "target_goal": {
                "goal_id": "S2",
                "required_predicates": ["target_controlled"],
            },
            "horizon": "72h",
            "active_work_budget": 4,
        },
        "work_units_ledger": {
            "reset": {
                "work_unit_id": "reset",
                "rating_status": "rated",
                "rubric_scores": {"t1": 1, "t2": 3, "formula": "base", "computed_cost": 2},
                "overlap_state": "independent",
            },
        },
        "bound_actions": [
            {
                "action_id": "action_firewalled_reset",
                "actor_id": user_sid,
                "target_id": dc_sid,
                "requires": ["firewall_blocked"],
                "adds": ["target_controlled"],
                "referenced_work_unit_ids": ["reset"],
                "is_passive_closure": False,
            }
        ],
        "conditional_bounds_table": [
            {"prefix": ["reset"], "lower": "1/2", "upper": "1/2"},
        ],
        "target_impact_assessments": {
            dc_sid: {
                "target_asset_id": dc_sid,
                "rating_status": "rated",
                "consequence_rating": "Critical",
            },
        },
        "facts_ledger": {
            "observed_facts": [],
            "false_facts": [
                {"predicate": "firewall_blocked", "layer": 2, "truth_value": False},
            ],
            "assumed_facts": [],
            "unknown_facts": [],
            "predicate_layers": {"target_controlled": 3},
        },
    }

    # Candidate binds to action_firewalled_reset and explicitly OMITS required_predicates
    candidates = [
        {
            "candidate_id": "Cand_ActionBlocked",
            "target_asset_id": dc_sid,
            "bound_action_ids": ["action_firewalled_reset"],
        }
    ]

    roundtrip = execute_ranking_roundtrip(json.dumps(query_payload), candidates)
    res = roundtrip["roundtrip_result"]

    assert res["pareto_frontier"] == []
    assert "Cand_ActionBlocked" in res["diagnostics"]
    diag = res["diagnostics"]["Cand_ActionBlocked"]
    assert "blocked" in diag["reasons"]
    assert diag["assessment"]["gates_evaluation"]["firewall_blocked"] == "False"
    assert diag["assessment"]["status"] == "blocked"


def test_wire_schema_passive_closure_and_empty_work_ledger():
    """Finding 3 (P2): Wire schema support for passive closure and empty work ledger.

    Verifies:
    - is_passive_closure: true with referenced_work_unit_ids: [] is valid.
    - work_units_ledger: {} is permitted when no active work units exist.
    """
    user_sid = "S-1-5-21-3623811015-3361044348-30300820-1001"
    dc_sid = "S-1-5-21-3623811015-3361044348-30300820-1000"

    query_payload = {
        "query_metadata": {
            "query_id": "query-passive-test",
            "version": "1.0.0",
            "scenario_id": "scenario-test",
            "scenario_version": "1.0.0",
            "snapshot_id": (
                "sha256:e0601d763eeea285d268ec9e468d321c50c9d7faba53c8e7442a2fcc4159c812"
            ),
            "evaluation_mode": "scenario",
            "work_boundary": "corp_boundary",
            "foothold_node_id": user_sid,
            "target_goal": {
                "goal_id": "S2",
                "required_predicates": ["entitlement_resolved"],
            },
            "horizon": "72h",
            "active_work_budget": 0,
        },
        "work_units_ledger": {},  # Pure passive query: empty work ledger
        "bound_actions": [
            {
                "action_id": "action_memberof_expansion",
                "actor_id": user_sid,
                "target_id": dc_sid,
                "requires": [],
                "adds": ["entitlement_resolved"],
                "referenced_work_unit_ids": [],
                "is_passive_closure": True,
            }
        ],
        "conditional_bounds_table": [],
        "target_impact_assessments": {
            dc_sid: {
                "target_asset_id": dc_sid,
                "rating_status": "rated",
                "consequence_rating": "Critical",
            },
        },
        "facts_ledger": {
            "observed_facts": [],
            "false_facts": [],
            "assumed_facts": [],
            "unknown_facts": [],
            "predicate_layers": {"entitlement_resolved": 3},
        },
    }

    decoded = decode_ranking_query(json.dumps(query_payload))
    assert decoded["work_units_ledger"] == {}
    assert len(decoded["bound_actions"]) == 1
    assert decoded["bound_actions"][0]["is_passive_closure"] is True
    assert decoded["bound_actions"][0]["referenced_work_unit_ids"] == []


def test_budget_limit_enforcement_and_search_metadata_compliance():
    """Finding 4 (P2): active_work_budget check blocks candidate with active work units.

    Verifies:
    - When active_work_budget = 0, candidate with 2 active work units is marked blocked.
    - Diagnostics contains work_budget_exceeded.
    - search_metadata has budget_limit, is_truncated = True, completeness_scope = partial_truncated.
    """
    user_sid = "S-1-5-21-3623811015-3361044348-30300820-1001"
    dc_sid = "S-1-5-21-3623811015-3361044348-30300820-1000"

    query_payload = {
        "query_metadata": {
            "query_id": "query-budget-test",
            "version": "1.0.0",
            "scenario_id": "scenario-test",
            "scenario_version": "1.0.0",
            "snapshot_id": (
                "sha256:e0601d763eeea285d268ec9e468d321c50c9d7faba53c8e7442a2fcc4159c812"
            ),
            "evaluation_mode": "scenario",
            "work_boundary": "corp_boundary",
            "foothold_node_id": user_sid,
            "target_goal": {
                "goal_id": "S2",
                "required_predicates": ["target_controlled"],
            },
            "horizon": "72h",
            "active_work_budget": 0,  # Zero budget!
        },
        "work_units_ledger": {
            "reset": {
                "work_unit_id": "reset",
                "rating_status": "rated",
                "rubric_scores": {"t1": 1, "t2": 3, "formula": "base", "computed_cost": 2},
                "overlap_state": "independent",
            },
            "activate": {
                "work_unit_id": "activate",
                "rating_status": "rated",
                "rubric_scores": {"t1": 1, "t2": 2, "formula": "base", "computed_cost": 1},
                "overlap_state": "independent",
            },
        },
        "bound_actions": [
            {
                "action_id": "action_reset",
                "actor_id": user_sid,
                "target_id": dc_sid,
                "requires": [],
                "adds": ["pwd_reset_done"],
                "referenced_work_unit_ids": ["reset"],
                "is_passive_closure": False,
            },
            {
                "action_id": "action_activate",
                "actor_id": dc_sid,
                "target_id": dc_sid,
                "requires": [],
                "adds": ["target_controlled"],
                "referenced_work_unit_ids": ["activate"],
                "is_passive_closure": False,
            },
        ],
        "conditional_bounds_table": [
            {"prefix": ["reset"], "lower": "1/2", "upper": "1/2"},
            {"prefix": ["reset", "activate"], "lower": "1/2", "upper": "1/2"},
        ],
        "target_impact_assessments": {
            dc_sid: {
                "target_asset_id": dc_sid,
                "rating_status": "rated",
                "consequence_rating": "Critical",
            },
        },
        "facts_ledger": {
            "observed_facts": [],
            "false_facts": [],
            "assumed_facts": [],
            "unknown_facts": [],
            "predicate_layers": {"pwd_reset_done": 3, "target_controlled": 3},
        },
    }

    candidates = [
        {
            "candidate_id": "Cand_OverBudget",
            "target_asset_id": dc_sid,
            "bound_action_ids": ["action_reset", "action_activate"],
        }
    ]

    roundtrip = execute_ranking_roundtrip(json.dumps(query_payload), candidates)
    res = roundtrip["roundtrip_result"]

    assert res["pareto_frontier"] == []
    assert "Cand_OverBudget" in res["diagnostics"]
    diag = res["diagnostics"]["Cand_OverBudget"]
    assert "work_budget_exceeded" in diag["reasons"]
    assert diag["assessment"]["status"] == "blocked"

    search_meta = res["search_metadata"]
    assert search_meta["budget_limit"] == 0
    assert search_meta["is_truncated"] is True
    assert search_meta["truncation_reasons"] == ["work_budget_exceeded"]
    assert search_meta["completeness_scope"] == "partial_truncated"


def test_rating_status_normalization_and_unresolved_overlap_withholding():
    """Finding 5 (P2): Rating status normalization and unresolved overlap withholding.

    Verifies:
    - Omission of status defaults to rated when rubric_scores/t1/t2 are present.
    - Conflicting state: rating_status rated with overlap_state unresolved_overlap
      raises ValueError.
    - Work unit with unresolved_overlap has rubric_scores null and computed_cost null.
    - Candidate with unresolved overlap unit has effort None and effort_status unrated.
    - Unresolved overlap cannot break ties in scoped_preference.
    """
    # 1. Omission of status defaults to rated
    ledger_no_status = {
        "u1": {
            "rubric_scores": {"t1": 1, "t2": 3, "formula": "base", "computed_cost": 2},
            "overlap_state": "independent",
        }
    }
    val = validate_work_units_ledger(ledger_no_status)
    assert val["u1"]["rating_status"] == "rated"
    assert val["u1"]["computed_cost"] == 2

    # 2. Conflicting state: rated + unresolved_overlap raises ValueError
    conflicting_ledger = {
        "u2": {
            "rating_status": "rated",
            "rubric_scores": {"t1": 1, "t2": 2, "formula": "base", "computed_cost": 1},
            "overlap_state": "unresolved_overlap",
        }
    }
    with pytest.raises(ValueError, match="conflicting state"):
        validate_work_units_ledger(conflicting_ledger)

    # 3. Legitimate unresolved overlap unit: unrated and null scores
    overlap_ledger = {
        "u3": {
            "rating_status": "unrated",
            "rubric_scores": None,
            "overlap_state": "unresolved_overlap",
        }
    }
    val_overlap = validate_work_units_ledger(overlap_ledger)
    assert val_overlap["u3"]["rating_status"] == "unrated"
    assert val_overlap["u3"]["computed_cost"] is None

    # 4. In scoped_preference, unresolved overlap withholding prevents effort tiebreak
    cand_rated = {
        "candidate_id": "Cand_Rated",
        "impact": "High",
        "likelihood_interval": (Fraction("6/10"), Fraction("6/10")),
        "effort": 3,
        "effort_status": "rated",
        "status": "feasible",
    }
    cand_unresolved = {
        "candidate_id": "Cand_Unresolved",
        "impact": "High",
        "likelihood_interval": (Fraction("6/10"), Fraction("6/10")),
        "effort": None,
        "effort_status": "unrated",
        "status": "feasible",
    }
    # Effort cannot break tie between identical impact and point likelihood when one is unrated
    assert scoped_preference(cand_rated, cand_unresolved) == "incomparable"
    assert scoped_preference(cand_unresolved, cand_rated) == "incomparable"


def test_conflicting_assumptions_order_invariance():
    """Finding 6 (P2): Conflicting assumptions resolve to Unknown regardless of JSON list order.

    Verifies:
    - Order A: [False, True] -> Unknown (contradictory_assumptions).
    - Order B: [True, False] -> Unknown (contradictory_assumptions).
    - Both orders route candidate to diagnostics with unknown status, never Pareto frontier.
    """
    # Order A: False first, True second
    facts_order_a = {
        "assumed_facts": [
            {
                "predicate": "session_present",
                "layer": 3,
                "truth_value": False,
                "rationale": "Assume no session",
            },
            {
                "predicate": "session_present",
                "layer": 3,
                "truth_value": True,
                "rationale": "Assume active session",
            },
        ]
    }
    res_a = resolve_facts_ledger(facts_order_a, evaluation_mode="scenario")
    assert res_a["session_present"]["value"] == "Unknown"
    assert res_a["session_present"]["disposition"] == "contradictory_assumptions"

    # Order B: True first, False second
    facts_order_b = {
        "assumed_facts": [
            {
                "predicate": "session_present",
                "layer": 3,
                "truth_value": True,
                "rationale": "Assume active session",
            },
            {
                "predicate": "session_present",
                "layer": 3,
                "truth_value": False,
                "rationale": "Assume no session",
            },
        ]
    }
    res_b = resolve_facts_ledger(facts_order_b, evaluation_mode="scenario")
    assert res_b["session_present"]["value"] == "Unknown"
    assert res_b["session_present"]["disposition"] == "contradictory_assumptions"


SNAPSHOT_SHA_ZERO = "sha256:" + "0" * 64


def test_work_packets_reconciliation_rejects_free_success_and_mismatches():
    """Finding 1 (P1): Reconcile candidate work packets with bound actions.

    Verifies:
    - Empty work packets when bound actions require active work is rejected.
    - Dropping an active work unit from bound actions is rejected.
    - Inverted packet order from bound actions is rejected.
    - Missing bound_action_ids is rejected (no unverified inference).
    - Matching packets pass and produce expected effort and likelihood.
    - Omitted work_packets derives authoritative packets from bound actions.
    """
    user_sid = "S-1-5-21-3623811015-3361044348-30300820-1001"
    dc_sid = "S-1-5-21-3623811015-3361044348-30300820-1000"
    da_sid = "S-1-5-21-3623811015-3361044348-30300820-512"

    query_payload = {
        "query_metadata": {
            "query_id": "qry_reconciliation_test",
            "version": "1.0.0",
            "scenario_id": "scen_test",
            "scenario_version": "1.0.0",
            "snapshot_id": SNAPSHOT_SHA_ZERO,
            "evaluation_mode": "scenario",
            "work_boundary": "active_directory_domain",
            "foothold_node_id": user_sid,
            "target_goal": {
                "goal_id": "S2",
                "description": "Domain Administrator access",
                "required_predicates": ["target_controlled"],
            },
            "horizon": "business_hours_72h",
            "active_work_budget": 4,
        },
        "work_units_ledger": {
            "reset": {
                "work_unit_id": "reset",
                "rating_status": "rated",
                "rubric_scores": {"t1": 1, "t2": 3, "formula": "base", "computed_cost": 2},
                "overlap_state": "independent",
            },
            "activate": {
                "work_unit_id": "activate",
                "rating_status": "rated",
                "rubric_scores": {"t1": 1, "t2": 2, "formula": "base", "computed_cost": 1},
                "overlap_state": "independent",
            },
        },
        "bound_actions": [
            {
                "action_id": "action_reset",
                "actor_id": user_sid,
                "target_id": dc_sid,
                "requires": ["structural_genericall"],
                "adds": ["pwd_reset_done"],
                "referenced_work_unit_ids": ["reset"],
                "is_passive_closure": False,
                "edge_id": canonical_edge_id(user_sid, dc_sid, "MemberOf"),
            },
            {
                "action_id": "action_activate",
                "actor_id": dc_sid,
                "target_id": da_sid,
                "requires": ["pwd_reset_done"],
                "adds": ["target_controlled"],
                "referenced_work_unit_ids": ["activate"],
                "is_passive_closure": False,
                "edge_id": canonical_edge_id(dc_sid, da_sid, "GenericAll"),
            },
        ],
        "conditional_bounds_table": [
            {"prefix": ["reset"], "lower": "1/2", "upper": "1/2"},
            {"prefix": ["reset", "activate"], "lower": "1/2", "upper": "1/2"},
        ],
        "target_impact_assessments": {
            dc_sid: {
                "target_asset_id": dc_sid,
                "rating_status": "rated",
                "consequence_rating": "Critical",
            },
        },
        "facts_ledger": {
            "observed_facts": [
                {
                    "predicate": "structural_genericall",
                    "layer": 1,
                    "truth_value": True,
                    "provenance_reference": (
                        "sha256:1111111111111111111111111111111111111111111111111111111111111111"
                    ),
                },
            ],
            "false_facts": [],
            "assumed_facts": [],
            "unknown_facts": [],
            "predicate_layers": {"pwd_reset_done": 3, "target_controlled": 3},
        },
    }
    query_str = json.dumps(query_payload)

    # 1. Empty packets attempting free success
    cand_empty_packets = [
        {
            "candidate_id": "cand_free_rider",
            "target_asset_id": dc_sid,
            "bound_action_ids": ["action_reset", "action_activate"],
            "work_packets": [],
        }
    ]
    with pytest.raises(ValueError, match="do not match authoritative work packets"):
        execute_ranking_roundtrip(query_str, cand_empty_packets)

    # 2. Dropping active work unit (attempting to cut effort/boost likelihood)
    cand_dropped_unit = [
        {
            "candidate_id": "cand_drop_activate",
            "target_asset_id": dc_sid,
            "bound_action_ids": ["action_reset", "action_activate"],
            "work_packets": [["reset"]],
        }
    ]
    with pytest.raises(ValueError, match="do not match authoritative work packets"):
        execute_ranking_roundtrip(query_str, cand_dropped_unit)

    # 3. Inverted packet order
    cand_inverted_packets = [
        {
            "candidate_id": "cand_inverted_order",
            "target_asset_id": dc_sid,
            "bound_action_ids": ["action_reset", "action_activate"],
            "work_packets": [["activate"], ["reset"]],
        }
    ]
    with pytest.raises(ValueError, match="do not match authoritative work packets"):
        execute_ranking_roundtrip(query_str, cand_inverted_packets)

    # 4. Missing bound_action_ids
    cand_missing_bindings = [
        {
            "candidate_id": "cand_no_bindings",
            "target_asset_id": dc_sid,
            "work_packets": [["reset"], ["activate"]],
        }
    ]
    with pytest.raises(ValueError, match="must explicitly specify bound_action_ids"):
        execute_ranking_roundtrip(query_str, cand_missing_bindings)

    # 5. Matching packets succeed
    cand_matching = [
        {
            "candidate_id": "cand_valid_reconciled",
            "target_asset_id": dc_sid,
            "bound_action_ids": ["action_reset", "action_activate"],
            "work_packets": [["reset"], ["activate"]],
        }
    ]
    res_matching = execute_ranking_roundtrip(query_str, cand_matching)["roundtrip_result"]
    assert res_matching["pareto_frontier"] == ["cand_valid_reconciled"]
    cand_data = res_matching["eligible_candidates"]["cand_valid_reconciled"]
    assert cand_data["effort"] == 3
    assert cand_data["likelihood_interval"] == ["1/4", "1/4"]

    # 6. Omitted work_packets automatically derived
    cand_derived = [
        {
            "candidate_id": "cand_derived_packets",
            "target_asset_id": dc_sid,
            "bound_action_ids": ["action_reset", "action_activate"],
        }
    ]
    res_derived = execute_ranking_roundtrip(query_str, cand_derived)["roundtrip_result"]
    assert res_derived["pareto_frontier"] == ["cand_derived_packets"]
    cand_der_data = res_derived["eligible_candidates"]["cand_derived_packets"]
    assert cand_der_data["effort"] == 3
    assert cand_der_data["likelihood_interval"] == ["1/4", "1/4"]


def test_sequential_action_step_evaluation_and_effects_chaining():
    """Finding 2 (P1): Sequential step-by-step gate evaluation and effect accumulation.

    Verifies:
    - Step 1 adds fact that satisfies Step 2's requirement (A -> B chain is feasible).
    - Reverse chain (B -> A) fails because Step 2 prerequisite is missing when Step 1 runs.
    - Action requiring its own effect fails because prerequisites evaluate before effects.
    - Future adds cannot retroactively satisfy earlier action requirements.
    """
    user_sid = "S-1-5-21-3623811015-3361044348-30300820-1001"
    dc_sid = "S-1-5-21-3623811015-3361044348-30300820-1000"
    da_sid = "S-1-5-21-3623811015-3361044348-30300820-512"

    query_payload = {
        "query_metadata": {
            "query_id": "qry_sequential_test",
            "version": "1.0.0",
            "scenario_id": "scen_test",
            "scenario_version": "1.0.0",
            "snapshot_id": SNAPSHOT_SHA_ZERO,
            "evaluation_mode": "scenario",
            "work_boundary": "active_directory_domain",
            "foothold_node_id": user_sid,
            "target_goal": {
                "goal_id": "S2",
                "description": "Domain Administrator access",
                "required_predicates": ["target_controlled"],
            },
            "horizon": "business_hours_72h",
            "active_work_budget": 4,
        },
        "work_units_ledger": {
            "reset": {
                "work_unit_id": "reset",
                "rating_status": "rated",
                "rubric_scores": {"t1": 1, "t2": 3, "formula": "base", "computed_cost": 2},
                "overlap_state": "independent",
            },
            "activate": {
                "work_unit_id": "activate",
                "rating_status": "rated",
                "rubric_scores": {"t1": 1, "t2": 2, "formula": "base", "computed_cost": 1},
                "overlap_state": "independent",
            },
            "loop": {
                "work_unit_id": "loop",
                "rating_status": "rated",
                "rubric_scores": {"t1": 1, "t2": 2, "formula": "base", "computed_cost": 1},
                "overlap_state": "independent",
            },
        },
        "bound_actions": [
            {
                "action_id": "action_reset",
                "actor_id": user_sid,
                "target_id": dc_sid,
                "requires": ["structural_genericall"],
                "adds": ["pwd_reset_done"],
                "referenced_work_unit_ids": ["reset"],
                "is_passive_closure": False,
                "edge_id": canonical_edge_id(user_sid, dc_sid, "MemberOf"),
            },
            {
                "action_id": "action_activate",
                "actor_id": dc_sid,
                "target_id": da_sid,
                "requires": ["pwd_reset_done"],
                "adds": ["target_controlled"],
                "referenced_work_unit_ids": ["activate"],
                "is_passive_closure": False,
                "edge_id": canonical_edge_id(dc_sid, da_sid, "GenericAll"),
            },
            {
                "action_id": "action_self_loop",
                "actor_id": user_sid,
                "target_id": dc_sid,
                "requires": ["self_generated_fact"],
                "adds": ["self_generated_fact", "target_controlled"],
                "referenced_work_unit_ids": ["loop"],
                "is_passive_closure": False,
                "edge_id": canonical_edge_id(user_sid, dc_sid, "MemberOf"),
            },
        ],
        "conditional_bounds_table": [
            {"prefix": ["reset"], "lower": "1/2", "upper": "1/2"},
            {"prefix": ["reset", "activate"], "lower": "1/2", "upper": "1/2"},
            {"prefix": ["activate"], "lower": "1/2", "upper": "1/2"},
            {"prefix": ["activate", "reset"], "lower": "1/2", "upper": "1/2"},
            {"prefix": ["loop"], "lower": "1/2", "upper": "1/2"},
        ],
        "target_impact_assessments": {
            dc_sid: {
                "target_asset_id": dc_sid,
                "rating_status": "rated",
                "consequence_rating": "Critical",
            },
        },
        "facts_ledger": {
            "observed_facts": [
                {
                    "predicate": "structural_genericall",
                    "layer": 1,
                    "truth_value": True,
                    "provenance_reference": (
                        "sha256:1111111111111111111111111111111111111111111111111111111111111111"
                    ),
                },
            ],
            "false_facts": [],
            "assumed_facts": [],
            "unknown_facts": [],
            "predicate_layers": {
                "pwd_reset_done": 3,
                "self_generated_fact": 3,
                "target_controlled": 3,
            },
        },
    }
    query_str = json.dumps(query_payload)

    # 1. Valid A -> B sequence: Step 1 provides prerequisite for Step 2
    cand_valid_seq = [
        {
            "candidate_id": "cand_a_to_b",
            "target_asset_id": dc_sid,
            "bound_action_ids": ["action_reset", "action_activate"],
        }
    ]
    res_a_to_b = execute_ranking_roundtrip(query_str, cand_valid_seq)["roundtrip_result"]
    assert res_a_to_b["pareto_frontier"] == ["cand_a_to_b"]
    assert "cand_a_to_b" in res_a_to_b["eligible_candidates"]
    eval_a_to_b = res_a_to_b["eligible_candidates"]["cand_a_to_b"]["gates_evaluation"]
    assert eval_a_to_b["pwd_reset_done"] == "True"
    assert eval_a_to_b["target_controlled"] == "True"

    # 2. Inverted B -> A sequence: Step 2 runs first and fails on unknown pwd_reset_done
    cand_inv_seq = [
        {
            "candidate_id": "cand_b_to_a",
            "target_asset_id": dc_sid,
            "bound_action_ids": ["action_activate", "action_reset"],
        }
    ]
    res_b_to_a = execute_ranking_roundtrip(query_str, cand_inv_seq)["roundtrip_result"]
    assert res_b_to_a["pareto_frontier"] == []
    assert "cand_b_to_a" in res_b_to_a["diagnostics"]
    diag_b_to_a = res_b_to_a["diagnostics"]["cand_b_to_a"]
    assert "unknown" in diag_b_to_a["reasons"]
    assert diag_b_to_a["assessment"]["gates_evaluation"]["pwd_reset_done"] == "Unknown"
    assert diag_b_to_a["assessment"]["status"] == "unknown"

    # 3. Action requiring its own addition cannot self-satisfy
    cand_self_loop = [
        {
            "candidate_id": "cand_self_referential",
            "target_asset_id": dc_sid,
            "bound_action_ids": ["action_self_loop"],
        }
    ]
    res_self = execute_ranking_roundtrip(query_str, cand_self_loop)["roundtrip_result"]
    assert res_self["pareto_frontier"] == []
    assert "cand_self_referential" in res_self["diagnostics"]
    diag_self = res_self["diagnostics"]["cand_self_referential"]
    assert "unknown" in diag_self["reasons"]
    assert diag_self["assessment"]["gates_evaluation"]["self_generated_fact"] == "Unknown"
    assert diag_self["assessment"]["status"] == "unknown"


def test_unspecified_subset_coverage_and_baseline_mirroring():
    """Finding 3 (P2): Coverage for arbitrary/empty subset and baseline truncation mirroring.

    Verifies:
    - Empty candidate set reports completeness_scope = 'unspecified_subset' and
      is_truncated = False.
    - min_effort_to_da_baseline baseline_coverage mirrors search_metadata for empty set.
    - Budget-exceeded candidate reports is_truncated = True and
      completeness_scope = 'partial_truncated' in both search_metadata and
      min_effort_to_da_baseline baseline_coverage.
    """
    user_sid = "S-1-5-21-3623811015-3361044348-30300820-1001"
    dc_sid = "S-1-5-21-3623811015-3361044348-30300820-1000"

    query_payload = {
        "query_metadata": {
            "query_id": "qry_coverage_test",
            "version": "1.0.0",
            "scenario_id": "scen_test",
            "scenario_version": "1.0.0",
            "snapshot_id": SNAPSHOT_SHA_ZERO,
            "evaluation_mode": "scenario",
            "work_boundary": "active_directory_domain",
            "foothold_node_id": user_sid,
            "target_goal": {
                "goal_id": "S2",
                "description": "Domain Administrator access",
                "required_predicates": ["target_controlled"],
            },
            "horizon": "business_hours_72h",
            "active_work_budget": 0,
        },
        "work_units_ledger": {
            "reset": {
                "work_unit_id": "reset",
                "rating_status": "rated",
                "rubric_scores": {"t1": 1, "t2": 3, "formula": "base", "computed_cost": 2},
                "overlap_state": "independent",
            },
            "activate": {
                "work_unit_id": "activate",
                "rating_status": "rated",
                "rubric_scores": {"t1": 1, "t2": 2, "formula": "base", "computed_cost": 1},
                "overlap_state": "independent",
            },
        },
        "bound_actions": [
            {
                "action_id": "action_reset",
                "actor_id": user_sid,
                "target_id": dc_sid,
                "requires": [],
                "adds": ["pwd_reset_done"],
                "referenced_work_unit_ids": ["reset"],
                "is_passive_closure": False,
                "edge_id": canonical_edge_id(user_sid, dc_sid, "MemberOf"),
            },
            {
                "action_id": "action_activate",
                "actor_id": user_sid,
                "target_id": dc_sid,
                "requires": ["pwd_reset_done"],
                "adds": ["target_controlled"],
                "referenced_work_unit_ids": ["activate"],
                "is_passive_closure": False,
                "edge_id": canonical_edge_id(user_sid, dc_sid, "GenericAll"),
            },
        ],
        "conditional_bounds_table": [
            {"prefix": ["reset"], "lower": "1/2", "upper": "1/2"},
            {"prefix": ["reset", "activate"], "lower": "1/2", "upper": "1/2"},
        ],
        "target_impact_assessments": {
            dc_sid: {
                "target_asset_id": dc_sid,
                "rating_status": "rated",
                "consequence_rating": "Critical",
            },
        },
        "facts_ledger": {
            "observed_facts": [],
            "false_facts": [],
            "assumed_facts": [],
            "unknown_facts": [],
            "predicate_layers": {"pwd_reset_done": 3, "target_controlled": 3},
        },
    }
    query_str = json.dumps(query_payload)

    # 1. Empty candidate set with no upstream coverage
    res_empty = execute_ranking_roundtrip(query_str, candidates=[])["roundtrip_result"]
    s_meta_empty = res_empty["search_metadata"]
    b_cov_empty = res_empty["min_effort_to_da_baseline"]["baseline_coverage"]

    assert s_meta_empty["candidates_evaluated"] == 0
    assert s_meta_empty["is_truncated"] is False
    assert s_meta_empty["truncation_reasons"] == []
    assert s_meta_empty["completeness_scope"] == "unspecified_subset"

    assert b_cov_empty["is_truncated"] is False
    assert b_cov_empty["truncation_reasons"] == []
    assert b_cov_empty["completeness_scope"] == "unspecified_subset"

    # 2. Budget exceeded (budget = 0, candidate has 2 active units)
    cand_over_budget = [
        {
            "candidate_id": "cand_budget_exceeded",
            "target_asset_id": dc_sid,
            "bound_action_ids": ["action_reset", "action_activate"],
        }
    ]
    res_budget = execute_ranking_roundtrip(query_str, cand_over_budget)["roundtrip_result"]
    s_meta_budget = res_budget["search_metadata"]
    b_cov_budget = res_budget["min_effort_to_da_baseline"]["baseline_coverage"]

    assert s_meta_budget["is_truncated"] is True
    assert s_meta_budget["truncation_reasons"] == ["work_budget_exceeded"]
    assert s_meta_budget["completeness_scope"] == "partial_truncated"

    # Baseline coverage must strictly mirror search metadata limits
    assert b_cov_budget["is_truncated"] is True
    assert b_cov_budget["truncation_reasons"] == ["work_budget_exceeded"]
    assert b_cov_budget["completeness_scope"] == "partial_truncated"


def test_duplicate_candidate_id_rejection_order_invariance():
    """Finding 4 (P2): Candidate ID uniqueness validation and order invariance.

    Verifies:
    - Order A [feasible, blocked] with duplicate candidate_id raises ValueError.
    - Order B [blocked, feasible] with duplicate candidate_id raises ValueError.
    - Prevents silent dictionary overwrite and arbitrary order-dependent frontier mutation.
    """
    user_sid = "S-1-5-21-3623811015-3361044348-30300820-1001"
    dc_sid = "S-1-5-21-3623811015-3361044348-30300820-1000"

    query_payload = {
        "query_metadata": {
            "query_id": "qry_dup_test",
            "version": "1.0.0",
            "scenario_id": "scen_test",
            "scenario_version": "1.0.0",
            "snapshot_id": SNAPSHOT_SHA_ZERO,
            "evaluation_mode": "scenario",
            "work_boundary": "active_directory_domain",
            "foothold_node_id": user_sid,
            "target_goal": {
                "goal_id": "S2",
                "description": "Domain Administrator access",
                "required_predicates": ["target_controlled"],
            },
            "horizon": "business_hours_72h",
            "active_work_budget": 4,
        },
        "work_units_ledger": {
            "reset": {
                "work_unit_id": "reset",
                "rating_status": "rated",
                "rubric_scores": {"t1": 1, "t2": 3, "formula": "base", "computed_cost": 2},
                "overlap_state": "independent",
            },
        },
        "bound_actions": [
            {
                "action_id": "action_reset",
                "actor_id": user_sid,
                "target_id": dc_sid,
                "requires": [],
                "adds": ["target_controlled"],
                "referenced_work_unit_ids": ["reset"],
                "is_passive_closure": False,
                "edge_id": canonical_edge_id(user_sid, dc_sid, "MemberOf"),
            },
        ],
        "conditional_bounds_table": [
            {"prefix": ["reset"], "lower": "1/2", "upper": "1/2"},
        ],
        "target_impact_assessments": {
            dc_sid: {
                "target_asset_id": dc_sid,
                "rating_status": "rated",
                "consequence_rating": "Critical",
            },
        },
        "facts_ledger": {
            "observed_facts": [],
            "false_facts": [
                {"predicate": "firewall_veto", "layer": 2, "truth_value": False},
            ],
            "assumed_facts": [],
            "unknown_facts": [],
            "predicate_layers": {"target_controlled": 3},
        },
    }
    query_str = json.dumps(query_payload)

    cand_feasible = {
        "candidate_id": "cand_dup",
        "target_asset_id": dc_sid,
        "bound_action_ids": ["action_reset"],
    }
    cand_blocked = {
        "candidate_id": "cand_dup",
        "target_asset_id": dc_sid,
        "bound_action_ids": ["action_reset"],
        "required_predicates": ["firewall_veto"],
    }

    # Order A: [feasible, blocked]
    with pytest.raises(ValueError, match="Duplicate candidate_id detected: 'cand_dup'"):
        execute_ranking_roundtrip(query_str, [cand_feasible, cand_blocked])

    # Order B: [blocked, feasible]
    with pytest.raises(ValueError, match="Duplicate candidate_id detected: 'cand_dup'"):
        execute_ranking_roundtrip(query_str, [cand_blocked, cand_feasible])


def test_layer_1_structural_authorization_immutability_in_action_effects():
    """Finding 1 (P1): Action effects cannot overwrite immutable Layer 1 snapshot authorizations.

    Verifies:
    - Snapshot structural authorization (Layer 1) observed False cannot be asserted True
      by action additions.
    - Candidate attempting to activate based on action-added Layer 1 predicate remains blocked.
    - Layer 3 derived facts (runtime state) added by actions are successfully asserted True
      in sequential replay.
    - Snapshot structural authorization (Layer 1) that is Unknown cannot be promoted to True
      by action additions.
    """
    user_sid = "S-1-5-21-3623811015-3361044348-30300820-1001"
    dc_sid = "S-1-5-21-3623811015-3361044348-30300820-1000"

    query_payload = {
        "query_metadata": {
            "query_id": "qry_layer1_immutability",
            "version": "1.0.0",
            "scenario_id": "scen_test",
            "scenario_version": "1.0.0",
            "snapshot_id": SNAPSHOT_SHA_ZERO,
            "evaluation_mode": "scenario",
            "work_boundary": "active_directory_domain",
            "foothold_node_id": user_sid,
            "target_goal": {
                "goal_id": "S2",
                "description": "Domain Administrator access",
                "required_predicates": ["target_controlled"],
            },
            "horizon": "business_hours_72h",
            "active_work_budget": 4,
        },
        "work_units_ledger": {
            "reset": {
                "work_unit_id": "reset",
                "rating_status": "rated",
                "rubric_scores": {"t1": 1, "t2": 3, "formula": "base", "computed_cost": 2},
                "overlap_state": "independent",
            },
            "activate": {
                "work_unit_id": "activate",
                "rating_status": "rated",
                "rubric_scores": {"t1": 1, "t2": 2, "formula": "base", "computed_cost": 1},
                "overlap_state": "independent",
            },
        },
        "bound_actions": [
            {
                "action_id": "action_reset",
                "actor_id": user_sid,
                "target_id": dc_sid,
                "requires": [],
                "adds": ["replication_authorization", "derived_session_fact"],
                "referenced_work_unit_ids": ["reset"],
                "is_passive_closure": False,
                "edge_id": canonical_edge_id(user_sid, dc_sid, "GenericAll"),
            },
            {
                "action_id": "action_activate_layer1",
                "actor_id": user_sid,
                "target_id": dc_sid,
                "requires": ["replication_authorization"],
                "adds": ["target_controlled"],
                "referenced_work_unit_ids": ["activate"],
                "is_passive_closure": False,
                "edge_id": canonical_edge_id(user_sid, dc_sid, "GetChangesAll"),
            },
            {
                "action_id": "action_activate_layer3",
                "actor_id": user_sid,
                "target_id": dc_sid,
                "requires": ["derived_session_fact"],
                "adds": ["target_controlled"],
                "referenced_work_unit_ids": ["activate"],
                "is_passive_closure": False,
                "edge_id": canonical_edge_id(user_sid, dc_sid, "GetChangesAll"),
            },
        ],
        "conditional_bounds_table": [
            {"prefix": ["reset"], "lower": "1/2", "upper": "1/2"},
            {"prefix": ["activate"], "lower": "1/2", "upper": "1/2"},
            {"prefix": ["reset", "activate"], "lower": "1/4", "upper": "1/4"},
        ],
        "target_impact_assessments": {
            dc_sid: {
                "target_asset_id": dc_sid,
                "rating_status": "rated",
                "consequence_rating": "Critical",
            },
        },
        "facts_ledger": {
            "observed_facts": [],
            "false_facts": [
                {
                    "predicate": "replication_authorization",
                    "layer": 1,
                    "truth_value": False,
                    "rationale": "Explicit Deny ACE in DACL snapshot",
                },
            ],
            "assumed_facts": [],
            "unknown_facts": [],
            "predicate_layers": {
                "replication_authorization": 1,
                "derived_session_fact": 3,
                "target_controlled": 3,
            },
        },
    }
    query_str = json.dumps(query_payload)

    # Candidate 1: attempts to overwrite replication_authorization (Layer 1) via action_reset
    # action_activate_layer1 requires replication_authorization
    cand_layer1_overwrite = [
        {
            "candidate_id": "cand_layer1_overwrite",
            "target_asset_id": dc_sid,
            "bound_action_ids": ["action_reset", "action_activate_layer1"],
        }
    ]
    res1 = execute_ranking_roundtrip(query_str, cand_layer1_overwrite)["roundtrip_result"]
    assert res1["pareto_frontier"] == []
    assert "cand_layer1_overwrite" in res1["diagnostics"]
    diag1 = res1["diagnostics"]["cand_layer1_overwrite"]
    assert "blocked" in diag1["reasons"]
    # Replication authorization must remain False despite action_reset adds
    assert diag1["assessment"]["gates_evaluation"]["replication_authorization"] == "False"
    assert diag1["assessment"]["status"] == "blocked"

    # Candidate 2: consumes derived_session_fact (Layer 3) added by action_reset
    # Layer 3 is runtime derived state, so action addition succeeds
    cand_layer3_ok = [
        {
            "candidate_id": "cand_layer3_ok",
            "target_asset_id": dc_sid,
            "bound_action_ids": ["action_reset", "action_activate_layer3"],
        }
    ]
    res2 = execute_ranking_roundtrip(query_str, cand_layer3_ok)["roundtrip_result"]
    assert res2["pareto_frontier"] == ["cand_layer3_ok"]
    assert "cand_layer3_ok" in res2["eligible_candidates"]
    elig2 = res2["eligible_candidates"]["cand_layer3_ok"]
    assert elig2["status"] == "feasible"
    assert elig2["gates_evaluation"]["derived_session_fact"] == "True"

    # Candidate 3: Unknown Layer 1 predicate cannot be promoted to True by action addition
    query_payload_unknown = dict(query_payload)
    query_payload_unknown["facts_ledger"] = {
        "observed_facts": [],
        "false_facts": [],
        "assumed_facts": [],
        "unknown_facts": [
            {
                "predicate": "replication_authorization",
                "layer": 1,
                "reason": "Missing snapshot replication link",
            }
        ],
        "predicate_layers": {
            "replication_authorization": 1,
            "derived_session_fact": 3,
            "target_controlled": 3,
        },
    }
    query_str_unknown = json.dumps(query_payload_unknown)
    res3 = execute_ranking_roundtrip(query_str_unknown, cand_layer1_overwrite)["roundtrip_result"]
    assert res3["pareto_frontier"] == []
    assert "cand_layer1_overwrite" in res3["diagnostics"]
    diag3 = res3["diagnostics"]["cand_layer1_overwrite"]
    assert "unknown" in diag3["reasons"]
    assert diag3["assessment"]["gates_evaluation"]["replication_authorization"] == "Unknown"
    assert diag3["assessment"]["status"] == "unknown"


def test_target_asset_reachability_and_goal_binding():
    """Finding 2 (P1): Target asset reachability and goal event binding.

    Verifies:
    - Candidate claiming an unreached target_asset_id is rejected with ValueError.
    - Candidate target_asset_id mismatching target_goal target_asset_id is rejected with ValueError.
    - Assessment success_event mismatching target_goal success_event is rejected with ValueError.
    - Candidate correctly reaching target asset via bound actions and matching target_goal succeeds.
    """
    user_sid = "S-1-5-21-3623811015-3361044348-30300820-1001"
    dc_sid = "S-1-5-21-3623811015-3361044348-30300820-1000"
    unreached_sid = "S-1-5-21-3623811015-3361044348-30300820-9999"

    query_payload = {
        "query_metadata": {
            "query_id": "qry_target_binding_test",
            "version": "1.0.0",
            "scenario_id": "scen_test",
            "scenario_version": "1.0.0",
            "snapshot_id": SNAPSHOT_SHA_ZERO,
            "evaluation_mode": "scenario",
            "work_boundary": "active_directory_domain",
            "foothold_node_id": user_sid,
            "target_goal": {
                "goal_id": "S2",
                "description": "Domain Administrator access",
                "target_asset_id": dc_sid,
                "success_event": "domain_admin_compromise",
                "required_predicates": ["target_controlled"],
            },
            "horizon": "business_hours_72h",
            "active_work_budget": 4,
        },
        "work_units_ledger": {
            "reset": {
                "work_unit_id": "reset",
                "rating_status": "rated",
                "rubric_scores": {"t1": 1, "t2": 3, "formula": "base", "computed_cost": 2},
                "overlap_state": "independent",
            },
        },
        "bound_actions": [
            {
                "action_id": "action_reset",
                "actor_id": user_sid,
                "target_id": dc_sid,
                "requires": [],
                "adds": ["target_controlled"],
                "referenced_work_unit_ids": ["reset"],
                "is_passive_closure": False,
                "edge_id": canonical_edge_id(user_sid, dc_sid, "MemberOf"),
            },
        ],
        "conditional_bounds_table": [
            {"prefix": ["reset"], "lower": "1/2", "upper": "1/2"},
        ],
        "target_impact_assessments": {
            dc_sid: {
                "target_asset_id": dc_sid,
                "rating_status": "rated",
                "consequence_rating": "Medium",
                "success_event": "domain_admin_compromise",
            },
            unreached_sid: {
                "target_asset_id": unreached_sid,
                "rating_status": "rated",
                "consequence_rating": "Critical",
                "success_event": "critical_exfiltration",
            },
        },
        "facts_ledger": {
            "observed_facts": [],
            "assumed_facts": [],
            "unknown_facts": [],
            "predicate_layers": {"target_controlled": 3, "pwd_reset_done": 3},
        },
    }
    query_str = json.dumps(query_payload)

    # 1. Candidate specifies target_asset_id = unreached_sid; actions only target dc_sid
    query_unreached_goal = json.loads(query_str)
    query_unreached_goal["query_metadata"]["target_goal"]["target_asset_id"] = unreached_sid
    query_unreached_goal["query_metadata"]["target_goal"]["success_event"] = "critical_exfiltration"
    cand_unreached = [
        {
            "candidate_id": "cand_unreached",
            "target_asset_id": unreached_sid,
            "bound_action_ids": ["action_reset"],
        }
    ]
    with pytest.raises(
        ValueError,
        match="is not reached by bound actions",
    ):
        execute_ranking_roundtrip(json.dumps(query_unreached_goal), cand_unreached)

    # 2. Target present only in structural route, but no bound action targets it
    route_to_unreached = [
        {
            "node_ids": [user_sid, unreached_sid],
            "edge_ids": [canonical_edge_id(user_sid, unreached_sid, "GenericAll")],
            "provenance_locators": ["snapshot:edge:0"],
        }
    ]
    cand_route_only = [
        {
            "candidate_id": "cand_route_only",
            "target_asset_id": unreached_sid,
            "bound_action_ids": ["action_reset"],
            "structural_routes": route_to_unreached,
        }
    ]
    with pytest.raises(
        ValueError,
        match="is not reached by bound actions",
    ):
        execute_ranking_roundtrip(json.dumps(query_unreached_goal), cand_route_only)

    # 3. Target reached only in suffix that gets trimmed at first hitting time
    query_suffix_trim = json.loads(query_str)
    query_suffix_trim["query_metadata"]["target_goal"]["target_asset_id"] = unreached_sid
    query_suffix_trim["query_metadata"]["target_goal"]["success_event"] = "critical_exfiltration"
    query_suffix_trim["query_metadata"]["target_goal"]["required_predicates"] = ["pwd_reset_done"]
    query_suffix_trim["bound_actions"] = [
        {
            "action_id": "action_reset",
            "actor_id": user_sid,
            "target_id": dc_sid,
            "requires": [],
            "adds": ["pwd_reset_done"],
            "referenced_work_unit_ids": ["reset"],
            "is_passive_closure": False,
            "edge_id": canonical_edge_id(user_sid, dc_sid, "MemberOf"),
        },
        {
            "action_id": "action_reach_unreached",
            "actor_id": user_sid,
            "target_id": unreached_sid,
            "requires": ["pwd_reset_done"],
            "adds": ["target_controlled"],
            "referenced_work_unit_ids": ["reset"],
            "is_passive_closure": False,
            "edge_id": canonical_edge_id(user_sid, unreached_sid, "GenericAll"),
        },
    ]
    cand_suffix_trim = [
        {
            "candidate_id": "cand_suffix_trim",
            "target_asset_id": unreached_sid,
            "bound_action_ids": ["action_reset", "action_reach_unreached"],
        }
    ]
    with pytest.raises(
        ValueError,
        match="is not reached by effective actions in executed prefix",
    ):
        execute_ranking_roundtrip(json.dumps(query_suffix_trim), cand_suffix_trim)

    # 4. Candidate target_asset_id does not match target_goal target_asset_id
    cand_mismatched_goal_target = [
        {
            "candidate_id": "cand_mismatched_target",
            "target_asset_id": unreached_sid,
            "bound_action_ids": ["action_reset"],
        }
    ]
    with pytest.raises(
        ValueError,
        match="does not match target_goal target_asset_id",
    ):
        execute_ranking_roundtrip(query_str, cand_mismatched_goal_target)

    # 5. Assessment success_event does not match target_goal success_event
    query_payload_bad_event = json.loads(query_str)
    query_payload_bad_event["target_impact_assessments"][dc_sid]["success_event"] = "wrong_event"
    query_str_bad_event = json.dumps(query_payload_bad_event)
    cand_valid = [
        {
            "candidate_id": "cand_valid",
            "target_asset_id": dc_sid,
            "bound_action_ids": ["action_reset"],
        }
    ]
    with pytest.raises(
        ValueError,
        match="does not match target_goal success_event",
    ):
        execute_ranking_roundtrip(query_str_bad_event, cand_valid)

    # 6. Assessment missing required success_event when target_goal specifies success_event
    query_payload_missing_event = json.loads(query_str)
    query_payload_missing_event["target_impact_assessments"][dc_sid].pop("success_event", None)
    query_str_missing_event = json.dumps(query_payload_missing_event)
    with pytest.raises(
        ValueError,
        match="is missing required success_event to match target_goal",
    ):
        execute_ranking_roundtrip(query_str_missing_event, cand_valid)

    # 7. Valid reachability and binding succeeds
    res_valid = execute_ranking_roundtrip(query_str, cand_valid)["roundtrip_result"]
    assert res_valid["pareto_frontier"] == ["cand_valid"]
    cand_out = res_valid["eligible_candidates"]["cand_valid"]
    assert cand_out["target_asset_id"] == dc_sid
    assert cand_out["consequence_rating"] == "Medium"


def test_goal_first_hitting_time_conformance_and_prefix_trimming():
    """Finding 3 (P2): Goal first hitting time conformance and prefix trimming (ADR-0013).

    Verifies:
    - Candidate sequence [action_reset, action_activate] achieving goal at action_reset
      terminates at step 1.
    - Suffix action_activate is trimmed; its unsatisfied/false prerequisite does not
      block candidate.
    - Nominal effort, effort, and likelihood are charged only for the trimmed prefix [action_reset].
    - Work packets, bound actions, and structural route traces are synchronized to trimmed prefix.
    - When goal is already satisfied in initial snapshot state, candidate is trimmed to
      empty sequence (effort 0, likelihood 1).
    """
    user_sid = "S-1-5-21-3623811015-3361044348-30300820-1001"
    dc_sid = "S-1-5-21-3623811015-3361044348-30300820-1000"

    edge_1 = canonical_edge_id(user_sid, dc_sid, "GenericAll")
    edge_2 = canonical_edge_id(user_sid, dc_sid, "WriteDacl")

    query_payload = {
        "query_metadata": {
            "query_id": "qry_first_hitting_time",
            "version": "1.0.0",
            "scenario_id": "scen_test",
            "scenario_version": "1.0.0",
            "snapshot_id": SNAPSHOT_SHA_ZERO,
            "evaluation_mode": "scenario",
            "work_boundary": "active_directory_domain",
            "foothold_node_id": user_sid,
            "target_goal": {
                "goal_id": "S2",
                "description": "Password reset privilege",
                "required_predicates": ["pwd_reset_done"],
            },
            "horizon": "business_hours_72h",
            "active_work_budget": 4,
        },
        "work_units_ledger": {
            "reset": {
                "work_unit_id": "reset",
                "rating_status": "rated",
                "rubric_scores": {"t1": 1, "t2": 3, "formula": "base", "computed_cost": 2},
                "overlap_state": "independent",
            },
            "activate": {
                "work_unit_id": "activate",
                "rating_status": "rated",
                "rubric_scores": {"t1": 1, "t2": 2, "formula": "base", "computed_cost": 1},
                "overlap_state": "independent",
            },
        },
        "bound_actions": [
            {
                "action_id": "action_reset",
                "actor_id": user_sid,
                "target_id": dc_sid,
                "requires": [],
                "adds": ["pwd_reset_done"],
                "referenced_work_unit_ids": ["reset"],
                "is_passive_closure": False,
                "edge_id": edge_1,
            },
            {
                "action_id": "action_activate",
                "actor_id": user_sid,
                "target_id": dc_sid,
                "requires": ["unsatisfiable_predicate"],
                "adds": ["target_controlled"],
                "referenced_work_unit_ids": ["activate"],
                "is_passive_closure": False,
                "edge_id": edge_2,
            },
        ],
        "conditional_bounds_table": [
            {"prefix": ["reset"], "lower": "1/2", "upper": "1/2"},
            {"prefix": ["activate"], "lower": "1/2", "upper": "1/2"},
            {"prefix": ["reset", "activate"], "lower": "1/4", "upper": "1/4"},
        ],
        "target_impact_assessments": {
            dc_sid: {
                "target_asset_id": dc_sid,
                "rating_status": "rated",
                "consequence_rating": "Critical",
            },
        },
        "facts_ledger": {
            "observed_facts": [],
            "false_facts": [
                {
                    "predicate": "unsatisfiable_predicate",
                    "layer": 2,
                    "truth_value": False,
                    "rationale": "Explicitly false security condition",
                }
            ],
            "assumed_facts": [],
            "unknown_facts": [],
            "predicate_layers": {"pwd_reset_done": 3, "target_controlled": 3},
        },
    }
    query_str = json.dumps(query_payload)

    # Candidate specifies sequence [action_reset, action_activate]
    # action_reset satisfies goal pwd_reset_done
    # action_activate has false precondition unsatisfiable_predicate
    cand_seq = [
        {
            "candidate_id": "cand_trim_test",
            "target_asset_id": dc_sid,
            "bound_action_ids": ["action_reset", "action_activate"],
            "structural_routes": [
                {
                    "node_ids": [user_sid, dc_sid, dc_sid],
                    "edge_ids": [edge_1, edge_2],
                    "provenance_locators": ["snapshot:edge:1", "snapshot:edge:2"],
                }
            ],
        }
    ]
    res = execute_ranking_roundtrip(query_str, cand_seq)["roundtrip_result"]
    assert res["pareto_frontier"] == ["cand_trim_test"]
    cand_out = res["eligible_candidates"]["cand_trim_test"]

    # Candidate must be feasible because execution terminated at action_reset (first hitting time)
    assert cand_out["status"] == "feasible"
    assert cand_out["bound_action_ids"] == ["action_reset"]
    assert cand_out["program"] == ["reset"]
    # Nominal effort is 2 (only reset), not 3 (reset + activate)
    assert cand_out["nominal_effort"] == 2
    assert cand_out["effort"] == 2
    # Likelihood is 1/2, not 1/4
    assert cand_out["likelihood_interval"] == ["1/2", "1/2"]
    # Structural route must be trimmed to the first step
    assert len(cand_out["structural_routes"]) == 1
    route_trimmed = cand_out["structural_routes"][0]
    assert route_trimmed["edge_ids"] == [edge_1]
    assert route_trimmed["provenance_locators"] == ["snapshot:edge:1"]
    assert route_trimmed["node_ids"] == [user_sid, dc_sid]

    # Case B: Goal is already satisfied at initial snapshot state (step 0)
    query_payload_init = json.loads(query_str)
    query_payload_init["facts_ledger"]["predicate_layers"]["pwd_reset_done"] = 2
    query_payload_init["facts_ledger"]["observed_facts"] = [
        {
            "predicate": "pwd_reset_done",
            "layer": 2,
            "truth_value": True,
            "telemetry_source": "ad_audit_log",
        }
    ]
    query_str_init = json.dumps(query_payload_init)

    # When foothold is user_sid but target_asset_id is dc_sid:
    # Neither trimmed cand_seq nor empty candidate can reach dc_sid with zero actions!
    with pytest.raises(ValueError, match="is not reached by initial foothold"):
        execute_ranking_roundtrip(query_str_init, cand_seq)

    cand_empty_dc = [
        {
            "candidate_id": "cand_empty_dc",
            "target_asset_id": dc_sid,
            "bound_action_ids": [],
        }
    ]
    with pytest.raises(ValueError, match="is not reached by initial foothold"):
        execute_ranking_roundtrip(query_str_init, cand_empty_dc)

    # When foothold_node_id is dc_sid (target is the initial foothold):
    # Both trimmed cand_seq and empty candidate reach dc_sid with 0 actions at step 0!
    query_payload_init_foothold = json.loads(query_str_init)
    query_payload_init_foothold["query_metadata"]["foothold_node_id"] = dc_sid
    cand_seq_foothold = [
        {
            "candidate_id": "cand_trim_test",
            "target_asset_id": dc_sid,
            "bound_action_ids": ["action_reset", "action_activate"],
            "structural_routes": [
                {
                    "node_ids": [dc_sid, dc_sid, dc_sid],
                    "edge_ids": [edge_1, edge_2],
                    "provenance_locators": ["snapshot:edge:1", "snapshot:edge:2"],
                }
            ],
        }
    ]
    res_init = execute_ranking_roundtrip(
        json.dumps(query_payload_init_foothold), cand_seq_foothold
    )["roundtrip_result"]
    assert res_init["pareto_frontier"] == ["cand_trim_test"]
    cand_init_out = res_init["eligible_candidates"]["cand_trim_test"]
    assert cand_init_out["status"] == "feasible"
    assert cand_init_out["bound_action_ids"] == []
    assert cand_init_out["program"] == []
    assert cand_init_out["nominal_effort"] == 0
    assert cand_init_out["effort"] == 0
    assert cand_init_out["likelihood_interval"] == ["1", "1"]
    route_init_trimmed = cand_init_out["structural_routes"][0]
    assert route_init_trimmed["edge_ids"] == []
    assert route_init_trimmed["provenance_locators"] == []
    assert route_init_trimmed["node_ids"] == [dc_sid]


def test_upstream_coverage_caps_preservation_and_truncation_normalization():
    """Finding 4 (P2): Upstream coverage caps preservation and truncation scope normalization.

    Verifies:
    - Upstream coverage caps (max_candidates, timeout_ms, max_expansions) are preserved
      in search_metadata.
    - Upstream coverage declared exhaustive_within_scope is normalized to partial_truncated when
      local active work budget is exceeded.
    - Baseline coverage strictly mirrors normalized search_metadata coverage.
    """
    user_sid = "S-1-5-21-3623811015-3361044348-30300820-1001"
    dc_sid = "S-1-5-21-3623811015-3361044348-30300820-1000"

    query_payload = {
        "query_metadata": {
            "query_id": "qry_caps_preservation_test",
            "version": "1.0.0",
            "scenario_id": "scen_test",
            "scenario_version": "1.0.0",
            "snapshot_id": SNAPSHOT_SHA_ZERO,
            "evaluation_mode": "scenario",
            "work_boundary": "active_directory_domain",
            "foothold_node_id": user_sid,
            "target_goal": {
                "goal_id": "S2",
                "description": "Domain Administrator access",
                "required_predicates": ["target_controlled"],
            },
            "horizon": "business_hours_72h",
            "active_work_budget": 4,
        },
        "work_units_ledger": {
            "reset": {
                "work_unit_id": "reset",
                "rating_status": "rated",
                "rubric_scores": {"t1": 1, "t2": 3, "formula": "base", "computed_cost": 2},
                "overlap_state": "independent",
            },
        },
        "bound_actions": [
            {
                "action_id": "action_reset",
                "actor_id": user_sid,
                "target_id": dc_sid,
                "requires": [],
                "adds": ["target_controlled"],
                "referenced_work_unit_ids": ["reset"],
                "is_passive_closure": False,
                "edge_id": canonical_edge_id(user_sid, dc_sid, "MemberOf"),
            },
        ],
        "conditional_bounds_table": [
            {"prefix": ["reset"], "lower": "1/2", "upper": "1/2"},
        ],
        "target_impact_assessments": {
            dc_sid: {
                "target_asset_id": dc_sid,
                "rating_status": "rated",
                "consequence_rating": "Critical",
            },
        },
        "facts_ledger": {
            "observed_facts": [],
            "assumed_facts": [],
            "unknown_facts": [],
            "predicate_layers": {"target_controlled": 3},
        },
    }
    query_str = json.dumps(query_payload)

    cand = {
        "candidate_id": "cand_caps_test",
        "target_asset_id": dc_sid,
        "bound_action_ids": ["action_reset"],
    }

    # Case A: Upstream coverage provides full caps_applied
    upstream_cov_with_caps = {
        "completeness_scope": "partial_truncated",
        "is_truncated": True,
        "truncation_reasons": ["candidate_limit_reached"],
        "caps_applied": {
            "max_active_work_budget": 4,
            "max_candidates": 1,
            "timeout_ms": 500,
            "max_expansions": 10,
        },
    }
    res_a = execute_ranking_roundtrip(query_str, [cand], upstream_coverage=upstream_cov_with_caps)[
        "roundtrip_result"
    ]
    s_meta_a = res_a["search_metadata"]
    assert s_meta_a["is_truncated"] is True
    assert "candidate_limit_reached" in s_meta_a["truncation_reasons"]
    assert s_meta_a["completeness_scope"] == "partial_truncated"
    caps_a = s_meta_a["caps_applied"]
    assert caps_a["max_active_work_budget"] == 4
    assert caps_a["max_candidates"] == 1
    assert caps_a["timeout_ms"] == 500
    assert caps_a["max_expansions"] == 10

    # Baseline coverage must strictly mirror the normalized search metadata
    b_cov_a = res_a["min_effort_to_da_baseline"]["baseline_coverage"]
    assert b_cov_a["is_truncated"] is True
    assert b_cov_a["truncation_reasons"] == ["candidate_limit_reached"]
    assert b_cov_a["completeness_scope"] == "partial_truncated"

    # Case B: Upstream declared exhaustive, but candidate exceeds local budget (0)
    query_payload_budget0 = json.loads(query_str)
    query_payload_budget0["query_metadata"]["active_work_budget"] = 0
    query_str_budget0 = json.dumps(query_payload_budget0)

    upstream_cov_exhaustive = {
        "completeness_scope": "exhaustive_within_scope",
        "is_truncated": False,
        "truncation_reasons": [],
        "caps_applied": {
            "max_active_work_budget": 4,
            "max_candidates": 100,
            "timeout_ms": 1000,
            "max_expansions": 50,
        },
    }
    res_b = execute_ranking_roundtrip(
        query_str_budget0, [cand], upstream_coverage=upstream_cov_exhaustive
    )["roundtrip_result"]
    s_meta_b = res_b["search_metadata"]
    assert s_meta_b["is_truncated"] is True
    assert "work_budget_exceeded" in s_meta_b["truncation_reasons"]
    # Must be normalized to partial_truncated, NOT remain exhaustive_within_scope!
    assert s_meta_b["completeness_scope"] == "partial_truncated"
    caps_b = s_meta_b["caps_applied"]
    assert caps_b["max_active_work_budget"] == 0
    assert caps_b["max_candidates"] == 100
    assert caps_b["timeout_ms"] == 1000
    assert caps_b["max_expansions"] == 50

    b_cov_b = res_b["min_effort_to_da_baseline"]["baseline_coverage"]
    assert b_cov_b["is_truncated"] is True
    assert "work_budget_exceeded" in b_cov_b["truncation_reasons"]
    assert b_cov_b["completeness_scope"] == "partial_truncated"


def test_unknown_initial_requirement_withholding_when_action_satisfies_goal():
    """Round 6 Review Finding 1 (P1): Initial Unknown requirement is withheld despite action goal.

    Verifies:
    - Candidate with initial required_predicates evaluating to Unknown does not become feasible
      when an action in replay satisfies the target goal.
    - Status remains unknown; candidate is withheld from Pareto frontier.
    - Diagnostics records reasons ['unknown', 'likelihood_unrated'].
    - Effort and likelihood_interval are None.
    """
    user_sid = "S-1-5-21-3623811015-3361044348-30300820-1001"
    dc_sid = "S-1-5-21-3623811015-3361044348-30300820-1000"

    query_payload = {
        "query_metadata": {
            "query_id": "qry_unknown_initial_test",
            "version": "1.0.0",
            "scenario_id": "scen_test",
            "scenario_version": "1.0.0",
            "snapshot_id": SNAPSHOT_SHA_ZERO,
            "evaluation_mode": "scenario",
            "work_boundary": "active_directory_domain",
            "foothold_node_id": user_sid,
            "target_goal": {
                "goal_id": "S2",
                "description": "Password reset privilege",
                "target_asset_id": dc_sid,
                "success_event": "password_reset",
                "required_predicates": ["pwd_reset_done"],
            },
            "horizon": "business_hours_72h",
            "active_work_budget": 4,
        },
        "work_units_ledger": {
            "reset": {
                "work_unit_id": "reset",
                "rating_status": "rated",
                "rubric_scores": {"t1": 1, "t2": 3, "formula": "base", "computed_cost": 2},
                "overlap_state": "independent",
            },
        },
        "bound_actions": [
            {
                "action_id": "action_reset",
                "actor_id": user_sid,
                "target_id": dc_sid,
                "requires": [],
                "adds": ["pwd_reset_done"],
                "referenced_work_unit_ids": ["reset"],
                "is_passive_closure": False,
                "edge_id": canonical_edge_id(user_sid, dc_sid, "MemberOf"),
            },
        ],
        "conditional_bounds_table": [
            {"prefix": ["reset"], "lower": "1/2", "upper": "1/2"},
        ],
        "target_impact_assessments": {
            dc_sid: {
                "target_asset_id": dc_sid,
                "rating_status": "rated",
                "consequence_rating": "Critical",
                "success_event": "password_reset",
            },
        },
        "facts_ledger": {
            "observed_facts": [],
            "assumed_facts": [],
            "unknown_facts": [
                {
                    "predicate": "session_present",
                    "layer": 3,
                    "reason": "Unknown session telemetry",
                }
            ],
            "predicate_layers": {"session_present": 3, "pwd_reset_done": 3},
        },
    }
    query_str = json.dumps(query_payload)

    cand = [
        {
            "candidate_id": "cand_unknown_initial",
            "target_asset_id": dc_sid,
            "bound_action_ids": ["action_reset"],
            "required_predicates": ["session_present"],
        }
    ]

    res = execute_ranking_roundtrip(query_str, cand)["roundtrip_result"]
    assert res["pareto_frontier"] == []
    assert "cand_unknown_initial" in res["diagnostics"]
    diag = res["diagnostics"]["cand_unknown_initial"]
    assert "unknown" in diag["reasons"]
    assert "likelihood_unrated" in diag["reasons"]
    assert diag["assessment"]["status"] == "unknown"
    assert diag["assessment"]["gates_evaluation"]["session_present"] == "Unknown"
    assert diag["assessment"]["effort"] is None
    assert diag["assessment"]["likelihood_interval"] is None


def test_structural_route_preservation_and_trimming_sync_safety():
    """Round 6 Review Finding 3 (P2): Multi-edge route preservation and sync safety.

    Verifies:
    - Route traces with multiple edges/locators per step are preserved completely intact
      when all actions are kept (goal achieved at the last step).
    - When an action suffix is trimmed and route edges do not match declared actions,
      adapter safely rejects synchronization with ValueError.
    """
    user_sid = "S-1-5-21-3623811015-3361044348-30300820-1001"
    dc_sid = "S-1-5-21-3623811015-3361044348-30300820-1000"
    aux_node = "S-1-5-21-3623811015-3361044348-30300820-2001"
    end_node = "S-1-5-21-3623811015-3361044348-30300820-3001"

    e1 = canonical_edge_id(user_sid, aux_node, "MemberOf")
    e2 = canonical_edge_id(aux_node, end_node, "GenericAll")
    e3 = canonical_edge_id(end_node, dc_sid, "WriteDacl")

    query_payload = {
        "query_metadata": {
            "query_id": "qry_route_preservation_test",
            "version": "1.0.0",
            "scenario_id": "scen_test",
            "scenario_version": "1.0.0",
            "snapshot_id": SNAPSHOT_SHA_ZERO,
            "evaluation_mode": "scenario",
            "work_boundary": "active_directory_domain",
            "foothold_node_id": user_sid,
            "target_goal": {
                "goal_id": "S2",
                "description": "DC takeover",
                "target_asset_id": dc_sid,
                "success_event": "dc_compromise",
                "required_predicates": ["target_controlled"],
            },
            "horizon": "business_hours_72h",
            "active_work_budget": 4,
        },
        "work_units_ledger": {
            "reset": {
                "work_unit_id": "reset",
                "rating_status": "rated",
                "rubric_scores": {"t1": 1, "t2": 3, "formula": "base", "computed_cost": 2},
                "overlap_state": "independent",
            },
            "activate": {
                "work_unit_id": "activate",
                "rating_status": "rated",
                "rubric_scores": {"t1": 1, "t2": 2, "formula": "base", "computed_cost": 1},
                "overlap_state": "independent",
            },
        },
        "bound_actions": [
            {
                "action_id": "action_reset",
                "actor_id": user_sid,
                "target_id": dc_sid,
                "requires": [],
                "adds": ["pwd_reset_done"],
                "referenced_work_unit_ids": ["reset"],
                "is_passive_closure": False,
                "edge_id": e1,
            },
            {
                "action_id": "action_activate",
                "actor_id": user_sid,
                "target_id": dc_sid,
                "requires": ["pwd_reset_done"],
                "adds": ["target_controlled"],
                "referenced_work_unit_ids": ["activate"],
                "is_passive_closure": False,
                "edge_id": e3,
            },
        ],
        "conditional_bounds_table": [
            {"prefix": ["reset"], "lower": "1/2", "upper": "1/2"},
            {"prefix": ["reset", "activate"], "lower": "1/4", "upper": "1/4"},
        ],
        "target_impact_assessments": {
            dc_sid: {
                "target_asset_id": dc_sid,
                "rating_status": "rated",
                "consequence_rating": "Critical",
                "success_event": "dc_compromise",
            },
        },
        "facts_ledger": {
            "observed_facts": [],
            "assumed_facts": [],
            "unknown_facts": [],
            "predicate_layers": {"pwd_reset_done": 3, "target_controlled": 3},
        },
    }
    query_str = json.dumps(query_payload)

    # Route has 4 nodes, 3 edges, 4 locators for 2 actions
    route_multi_edge = [
        {
            "route_id": "route_multi",
            "node_ids": [user_sid, aux_node, end_node, dc_sid],
            "edge_ids": [e1, e2, e3],
            "provenance_locators": ["loc:0", "loc:1", "loc:2", "loc:3"],
        }
    ]

    # Case A: Goal target_controlled achieved at the final step (action_activate).
    # No actions trimmed -> route must NOT be sliced!
    cand_full = [
        {
            "candidate_id": "cand_full",
            "target_asset_id": dc_sid,
            "bound_action_ids": ["action_reset", "action_activate"],
            "structural_routes": route_multi_edge,
        }
    ]
    res_full = execute_ranking_roundtrip(query_str, cand_full)["roundtrip_result"]
    assert res_full["pareto_frontier"] == ["cand_full"]
    route_out = res_full["eligible_candidates"]["cand_full"]["structural_routes"][0]
    assert len(route_out["node_ids"]) == 4
    assert len(route_out["edge_ids"]) == 3
    assert len(route_out["provenance_locators"]) == 4

    # Case B: Goal pwd_reset_done achieved at step 1 (action_reset).
    # action_activate is trimmed. Route has 3 edges for 2 declared actions.
    # Synchronization cannot map safely -> must raise ValueError.
    query_trim = json.loads(query_str)
    query_trim["query_metadata"]["target_goal"]["required_predicates"] = ["pwd_reset_done"]
    with pytest.raises(
        ValueError,
        match="cannot safely synchronize structural_routes upon suffix trimming",
    ):
        execute_ranking_roundtrip(json.dumps(query_trim), cand_full)


def test_zero_action_target_reachability_consistent_between_empty_and_trimmed_candidate():
    """Round 7 Review Finding 1 (P2): Zero-action target reachability consistency.

    Verifies:
    - An unexecuted action in a trimmed suffix cannot provide evidence of reaching a target.
    - When goal is met at initial step (step 0), a candidate trimmed to zero actions and
      a candidate declaring zero actions behave identically:
      - If target_asset_id != foothold_node_id, both are rejected with ValueError
        ('is not reached by initial foothold').
      - If target_asset_id == foothold_node_id, both succeed into the frontier with
        bound_action_ids = [], effort = 0, and likelihood = [1, 1].
    """
    user_sid = "S-1-5-21-3623811015-3361044348-30300820-1001"
    dc_sid = "S-1-5-21-3623811015-3361044348-30300820-1000"

    query_payload = {
        "query_metadata": {
            "query_id": "qry_zero_action_consistency",
            "version": "1.0.0",
            "scenario_id": "scen_test",
            "scenario_version": "1.0.0",
            "snapshot_id": SNAPSHOT_SHA_ZERO,
            "evaluation_mode": "scenario",
            "work_boundary": "active_directory_domain",
            "foothold_node_id": user_sid,
            "target_goal": {
                "goal_id": "S1",
                "description": "DC takeover already controlled",
                "target_asset_id": dc_sid,
                "success_event": "dc_compromise",
                "required_predicates": ["target_controlled"],
            },
            "horizon": "business_hours_72h",
            "active_work_budget": 4,
        },
        "work_units_ledger": {
            "reset": {
                "work_unit_id": "reset",
                "rating_status": "rated",
                "rubric_scores": {"t1": 1, "t2": 3, "formula": "base", "computed_cost": 2},
                "overlap_state": "independent",
            },
        },
        "bound_actions": [
            {
                "action_id": "action_reset",
                "actor_id": user_sid,
                "target_id": dc_sid,
                "requires": ["unsatisfiable_condition"],
                "adds": ["some_effect"],
                "referenced_work_unit_ids": ["reset"],
                "is_passive_closure": False,
                "edge_id": canonical_edge_id(user_sid, dc_sid, "MemberOf"),
            },
        ],
        "conditional_bounds_table": [
            {"prefix": ["reset"], "lower": "1/2", "upper": "1/2"},
        ],
        "target_impact_assessments": {
            dc_sid: {
                "target_asset_id": dc_sid,
                "rating_status": "rated",
                "consequence_rating": "Critical",
                "success_event": "dc_compromise",
            },
            user_sid: {
                "target_asset_id": user_sid,
                "rating_status": "rated",
                "consequence_rating": "Medium",
                "success_event": "user_compromise",
            },
        },
        "facts_ledger": {
            "observed_facts": [
                {
                    "predicate": "target_controlled",
                    "layer": 2,
                    "truth_value": True,
                    "telemetry_source": "ad_audit_log",
                }
            ],
            "false_facts": [],
            "assumed_facts": [],
            "unknown_facts": [],
            "predicate_layers": {
                "some_effect": 3,
                "unsatisfiable_condition": 2,
            },
        },
    }
    query_str = json.dumps(query_payload)

    # Candidate A declares action_reset to dc_sid, but goal target_controlled is met at step 0
    cand_trimmed = [
        {
            "candidate_id": "cand_trimmed",
            "target_asset_id": dc_sid,
            "bound_action_ids": ["action_reset"],
        }
    ]
    # Candidate B declares zero actions to dc_sid
    cand_empty = [
        {
            "candidate_id": "cand_empty",
            "target_asset_id": dc_sid,
            "bound_action_ids": [],
        }
    ]

    # Both must be rejected: dc_sid is NOT reached from user_sid foothold with 0 actions!
    with pytest.raises(ValueError, match="is not reached by initial foothold"):
        execute_ranking_roundtrip(query_str, cand_trimmed)

    with pytest.raises(ValueError, match="is not reached by initial foothold"):
        execute_ranking_roundtrip(query_str, cand_empty)

    # Now verify when foothold IS dc_sid (target_asset_id == foothold_node_id):
    query_payload_foothold = json.loads(query_str)
    query_payload_foothold["query_metadata"]["foothold_node_id"] = dc_sid
    query_str_foothold = json.dumps(query_payload_foothold)

    res_trimmed = execute_ranking_roundtrip(query_str_foothold, cand_trimmed)["roundtrip_result"]
    res_empty = execute_ranking_roundtrip(query_str_foothold, cand_empty)["roundtrip_result"]

    assert res_trimmed["pareto_frontier"] == ["cand_trimmed"]
    assert res_empty["pareto_frontier"] == ["cand_empty"]

    out_trimmed = res_trimmed["eligible_candidates"]["cand_trimmed"]
    out_empty = res_empty["eligible_candidates"]["cand_empty"]

    assert out_trimmed["status"] == "feasible"
    assert out_trimmed["bound_action_ids"] == []
    assert out_trimmed["effort"] == 0
    assert out_trimmed["likelihood_interval"] == ["1", "1"]

    assert out_empty["status"] == "feasible"
    assert out_empty["bound_action_ids"] == []
    assert out_empty["effort"] == 0
    assert out_empty["likelihood_interval"] == ["1", "1"]


def test_structural_route_trimming_requires_verified_1_to_1_mapping():
    """Round 7 Review Finding 2 (P2): Verified 1-to-1 route mapping guard on suffix trimming.

    Verifies:
    - Equal counts alone does NOT justify trimming.
    - Suffix trimming rejects candidates where route edges do not match action edge_ids in order.
    - Suffix trimming rejects candidates where actions lack explicit edge_id mapping.
    - Suffix trimming rejects candidates where route lacks node_ids or provenance_locators.
    """
    user_sid = "S-1-5-21-3623811015-3361044348-30300820-1001"
    dc_sid = "S-1-5-21-3623811015-3361044348-30300820-1000"

    e1 = canonical_edge_id(user_sid, dc_sid, "MemberOf")
    e2 = canonical_edge_id(user_sid, dc_sid, "GenericAll")

    query_payload = {
        "query_metadata": {
            "query_id": "qry_route_mapping_guard",
            "version": "1.0.0",
            "scenario_id": "scen_test",
            "scenario_version": "1.0.0",
            "snapshot_id": SNAPSHOT_SHA_ZERO,
            "evaluation_mode": "scenario",
            "work_boundary": "active_directory_domain",
            "foothold_node_id": user_sid,
            "target_goal": {
                "goal_id": "S1",
                "description": "Password reset",
                "target_asset_id": dc_sid,
                "success_event": "dc_compromise",
                "required_predicates": ["pwd_reset_done"],
            },
            "horizon": "business_hours_72h",
            "active_work_budget": 4,
        },
        "work_units_ledger": {
            "reset": {
                "work_unit_id": "reset",
                "rating_status": "rated",
                "rubric_scores": {"t1": 1, "t2": 3, "formula": "base", "computed_cost": 2},
                "overlap_state": "independent",
            },
            "activate": {
                "work_unit_id": "activate",
                "rating_status": "rated",
                "rubric_scores": {"t1": 1, "t2": 2, "formula": "base", "computed_cost": 1},
                "overlap_state": "independent",
            },
        },
        "bound_actions": [
            {
                "action_id": "action_reset",
                "actor_id": user_sid,
                "target_id": dc_sid,
                "requires": [],
                "adds": ["pwd_reset_done"],
                "referenced_work_unit_ids": ["reset"],
                "is_passive_closure": False,
                "edge_id": e2,  # Action 0 has e2!
            },
            {
                "action_id": "action_activate",
                "actor_id": user_sid,
                "target_id": dc_sid,
                "requires": ["pwd_reset_done"],
                "adds": ["target_controlled"],
                "referenced_work_unit_ids": ["activate"],
                "is_passive_closure": False,
                "edge_id": e1,  # Action 1 has e1!
            },
        ],
        "conditional_bounds_table": [
            {"prefix": ["reset"], "lower": "1/2", "upper": "1/2"},
            {"prefix": ["reset", "activate"], "lower": "1/4", "upper": "1/4"},
        ],
        "target_impact_assessments": {
            dc_sid: {
                "target_asset_id": dc_sid,
                "rating_status": "rated",
                "consequence_rating": "Critical",
                "success_event": "dc_compromise",
            },
        },
        "facts_ledger": {
            "observed_facts": [],
            "assumed_facts": [],
            "unknown_facts": [],
            "predicate_layers": {"pwd_reset_done": 3, "target_controlled": 3},
        },
    }
    query_str = json.dumps(query_payload)

    # Sub-case 1: Equal count (2 actions, 2 edges), but route has [e1, e2]
    # while actions have [e2, e1].
    # Goal pwd_reset_done is reached at step 1 (action_reset), triggering suffix trimming.
    cand_mismatched_order = [
        {
            "candidate_id": "cand_order_mismatch",
            "target_asset_id": dc_sid,
            "bound_action_ids": ["action_reset", "action_activate"],
            "structural_routes": [
                {
                    "route_id": "r1",
                    "node_ids": [user_sid, dc_sid, dc_sid],
                    "edge_ids": [e1, e2],  # e1 != action_reset.edge_id (e2)
                    "provenance_locators": ["loc:1", "loc:2"],
                }
            ],
        }
    ]
    with pytest.raises(
        ValueError,
        match="route edge .* at position 0 does not match bound action 'action_reset' edge_id",
    ):
        execute_ranking_roundtrip(query_str, cand_mismatched_order)

    # Sub-case 2: Missing edge_id on bound action
    query_no_edge = json.loads(query_str)
    del query_no_edge["bound_actions"][0]["edge_id"]
    cand_valid_route = [
        {
            "candidate_id": "cand_valid_route",
            "target_asset_id": dc_sid,
            "bound_action_ids": ["action_reset", "action_activate"],
            "structural_routes": [
                {
                    "route_id": "r1",
                    "node_ids": [user_sid, dc_sid, dc_sid],
                    "edge_ids": [e2, e1],
                    "provenance_locators": ["loc:1", "loc:2"],
                }
            ],
        }
    ]
    with pytest.raises(
        ValueError,
        match="missing edge_id mapping on bound action 'action_reset' at step 0",
    ):
        execute_ranking_roundtrip(json.dumps(query_no_edge), cand_valid_route)

    # Sub-case 3: Route missing provenance_locators or node_ids
    cand_no_locators = [
        {
            "candidate_id": "cand_no_locators",
            "target_asset_id": dc_sid,
            "bound_action_ids": ["action_reset", "action_activate"],
            "structural_routes": [
                {
                    "route_id": "r1",
                    "node_ids": [user_sid, dc_sid, dc_sid],
                    "edge_ids": [e2, e1],
                }
            ],
        }
    ]
    with pytest.raises(ValueError, match="route 'r1' missing provenance_locators"):
        execute_ranking_roundtrip(query_str, cand_no_locators)

    cand_no_nodes = [
        {
            "candidate_id": "cand_no_nodes",
            "target_asset_id": dc_sid,
            "bound_action_ids": ["action_reset", "action_activate"],
            "structural_routes": [
                {
                    "route_id": "r1",
                    "edge_ids": [e2, e1],
                    "provenance_locators": ["loc:1", "loc:2"],
                }
            ],
        }
    ]
    with pytest.raises(ValueError, match="route 'r1' missing node_ids"):
        execute_ranking_roundtrip(query_str, cand_no_nodes)

    # Sub-case 4: Correctly matched 1-to-1 mapping is successfully trimmed
    cand_matched = [
        {
            "candidate_id": "cand_matched",
            "target_asset_id": dc_sid,
            "bound_action_ids": ["action_reset", "action_activate"],
            "structural_routes": [
                {
                    "route_id": "r1",
                    "node_ids": [user_sid, dc_sid, dc_sid],
                    "edge_ids": [e2, e1],
                    "provenance_locators": ["loc:1", "loc:2"],
                }
            ],
        }
    ]
    res_matched = execute_ranking_roundtrip(query_str, cand_matched)["roundtrip_result"]
    assert res_matched["pareto_frontier"] == ["cand_matched"]
    r_trimmed = res_matched["eligible_candidates"]["cand_matched"]["structural_routes"][0]
    assert r_trimmed["edge_ids"] == [e2]
    assert r_trimmed["node_ids"] == [user_sid, dc_sid]
    assert r_trimmed["provenance_locators"] == ["loc:1"]


def test_layer_2_host_capability_immutability_under_action_adds():
    """Finding 1 (P1): Action adds cannot mutate Layer 2 host capabilities or Layer 1.

    Observed false of Layer 2 is a hard veto; action adds must only mutate
    Layer 3 runtime-derived predicates. If an action's adds specifies a Layer 2
    predicate that is observed False, the predicate must remain False and any
    subsequent action requiring it must remain blocked.
    """
    user_sid = "S-1-5-21-3623811015-3361044348-30300820-1001"
    host_sid = "S-1-5-21-3623811015-3361044348-30300820-1002"
    da_sid = "S-1-5-21-3623811015-3361044348-30300820-1000"

    edge_1 = canonical_edge_id(user_sid, host_sid, "CanRDP")
    edge_2 = canonical_edge_id(host_sid, da_sid, "AdminTo")

    query_payload = {
        "query_metadata": {
            "query_id": "query-layer2-immutability-001",
            "version": "1.0.0",
            "scenario_id": "scenario-veto-test",
            "scenario_version": "1.0.0",
            "snapshot_id": "sha256:" + "a" * 64,
            "evaluation_mode": "scenario",
            "work_boundary": "corp_boundary",
            "foothold_node_id": user_sid,
            "target_goal": {
                "goal_id": "G_DA",
                "required_predicates": ["target_controlled"],
            },
            "horizon": "24h",
            "active_work_budget": 5,
        },
        "bound_actions": [
            {
                "action_id": "action_disable_firewall",
                "actor_id": user_sid,
                "target_id": host_sid,
                "requires": ["structural_rdp_access"],
                # Attempts to mutate Layer 2 host capability predicate:
                "adds": ["firewall_port_open"],
                "referenced_work_unit_ids": ["rdp_pivot"],
                "is_passive_closure": False,
                "edge_id": edge_1,
            },
            {
                "action_id": "action_pivot",
                "actor_id": host_sid,
                "target_id": da_sid,
                # Requires the Layer 2 predicate that is known False:
                "requires": ["firewall_port_open"],
                "adds": ["target_controlled"],
                "referenced_work_unit_ids": ["exploit_host"],
                "is_passive_closure": False,
                "edge_id": edge_2,
            },
        ],
        "work_units_ledger": {
            "rdp_pivot": {"overlap_state": "independent", "nominal_effort": 1},
            "exploit_host": {"overlap_state": "independent", "nominal_effort": 1},
        },
        "conditional_bounds_table": [
            {"prefix": ["rdp_pivot"], "lower": "1/2", "upper": "1/2"},
            {"prefix": ["rdp_pivot", "exploit_host"], "lower": "1/2", "upper": "1/2"},
        ],
        "target_impact_assessments": {
            da_sid: {
                "target_asset_id": da_sid,
                "rating_status": "rated",
                "consequence_rating": "Critical",
            },
        },
        "facts_ledger": {
            "observed_facts": [
                {
                    "predicate": "structural_rdp_access",
                    "layer": 1,
                    "truth_value": True,
                    "provenance_reference": "sha256:" + "1" * 64,
                },
            ],
            "false_facts": [
                # firewall_port_open is observed False at Layer 2
                {
                    "predicate": "firewall_port_open",
                    "layer": 2,
                    "truth_value": False,
                },
            ],
            "assumed_facts": [],
            "unknown_facts": [],
            "predicate_layers": {"target_controlled": 3},
        },
    }

    candidates = [
        {
            "candidate_id": "cand_attempt_layer2_override",
            "target_asset_id": da_sid,
            "bound_action_ids": ["action_disable_firewall", "action_pivot"],
            "structural_routes": [
                {
                    "route_id": "route_1",
                    "node_ids": [user_sid, host_sid, da_sid],
                    "edge_ids": [edge_1, edge_2],
                    "provenance_locators": ["loc:1", "loc:2"],
                }
            ],
        }
    ]

    roundtrip = execute_ranking_roundtrip(json.dumps(query_payload), candidates)
    res = roundtrip["roundtrip_result"]

    # Candidate must NOT reach Pareto frontier
    assert res["pareto_frontier"] == []
    assert "cand_attempt_layer2_override" in res["diagnostics"]

    diag_entry = res["diagnostics"]["cand_attempt_layer2_override"]
    assert diag_entry["assessment"]["status"] == "blocked"
    assert "blocked" in diag_entry["reasons"]
    # firewall_port_open remained False despite action_disable_firewall's adds
    assert diag_entry["assessment"]["gates_evaluation"]["firewall_port_open"] == "False"
    assert diag_entry["assessment"]["effort"] is None
    assert diag_entry["assessment"]["likelihood_interval"] is None


def test_missing_predicate_layer_fails_validation():
    """Finding 2 (P1): Predicates in facts_ledger without authoritative layer must fail validation.

    resolve_facts_ledger must not silently default missing predicate layers to Layer 3
    (or 2). An authoritative layer must be explicitly provided in predicate_layers or on
    each entry. Structural predicates like replication_authorization cannot be assumed.
    """
    # 1. observed_facts entry without layer and without predicate_layers
    with pytest.raises(ValueError, match="Missing layer declaration for predicate 'p_obs'"):
        resolve_facts_ledger(
            {"observed_facts": [{"predicate": "p_obs", "truth_value": True}]},
            evaluation_mode="scenario",
        )

    # 2. false_facts entry without layer and without predicate_layers
    with pytest.raises(ValueError, match="Missing layer declaration for predicate 'p_false'"):
        resolve_facts_ledger(
            {"false_facts": [{"predicate": "p_false", "truth_value": False}]},
            evaluation_mode="scenario",
        )

    # 3. assumed_facts entry without layer and without predicate_layers
    with pytest.raises(ValueError, match="Missing layer declaration for predicate 'p_assumed'"):
        resolve_facts_ledger(
            {
                "assumed_facts": [
                    {"predicate": "p_assumed", "truth_value": True, "rationale": "test"}
                ]
            },
            evaluation_mode="scenario",
        )

    # 4. unknown_facts entry without layer and without predicate_layers
    with pytest.raises(ValueError, match="Missing layer declaration for predicate 'p_unk'"):
        resolve_facts_ledger(
            {"unknown_facts": [{"predicate": "p_unk"}]},
            evaluation_mode="scenario",
        )

    # 5. Reviewer core case: structural predicate (e.g. replication_authorization)
    # passed in assumed_facts without layer declaration must fail validation
    with pytest.raises(
        ValueError, match="Missing layer declaration for predicate 'replication_authorization'"
    ):
        resolve_facts_ledger(
            {
                "assumed_facts": [
                    {
                        "predicate": "replication_authorization",
                        "truth_value": True,
                        "rationale": "Attempting to assume Gate O without layer",
                    }
                ]
            },
            evaluation_mode="scenario",
        )

    # 6. When predicate_layers declares authoritative layer, resolution succeeds.
    # In scenario mode, Layer 1 cannot be assumed and stays Unknown.
    ledger_with_authoritative_layer = {
        "predicate_layers": {"replication_authorization": 1},
        "assumed_facts": [
            {
                "predicate": "replication_authorization",
                "truth_value": True,
                "rationale": "Attempting to assume Gate O",
            }
        ],
    }
    resolved = resolve_facts_ledger(ledger_with_authoritative_layer, evaluation_mode="scenario")
    assert resolved["replication_authorization"]["layer"] == 1
    assert resolved["replication_authorization"]["value"] == "Unknown"
    assert resolved["replication_authorization"]["disposition"] == "missing_structural_provenance"

    # 7. For Layer 3 with explicit layer, scenario assumption is permitted
    ledger_layer3_explicit = {
        "assumed_facts": [
            {
                "predicate": "session_present",
                "layer": 3,
                "truth_value": True,
                "rationale": "Active admin session",
            }
        ],
    }
    res_l3 = resolve_facts_ledger(ledger_layer3_explicit, evaluation_mode="scenario")
    assert res_l3["session_present"]["layer"] == 3
    assert res_l3["session_present"]["value"] == "True"
    assert res_l3["session_present"]["disposition"] == "permitted_runtime_assumption"


def test_canonical_node_id_scope_required_rejection():
    """Finding 3 (P2): Canonical node-ID validator enforces Graph Contract 1.3 scope rules.

    Namespace-relative SIDs (S-1-5-32-*) and host-relative SIDs (S-1-5-18/19/20) must be scoped.
    Bare/unscoped forms of these SIDs must be rejected by is_canonical_node_id and wire queries.
    """
    # 1. Bare namespace-relative SIDs (S-1-5-32-*) MUST be rejected
    assert not is_canonical_node_id("S-1-5-32-544")  # Builtin Administrators
    assert not is_canonical_node_id("S-1-5-32-555")  # Remote Desktop Users
    assert not is_canonical_node_id("S-1-5-32-580")  # Remote Management Users
    assert not is_canonical_node_id("S-1-5-32-0")
    assert not is_canonical_node_id("S-1-5-32-123456")

    # 2. Bare host-relative SIDs (S-1-5-18, 19, 20) MUST be rejected
    assert not is_canonical_node_id("S-1-5-18")  # Local System
    assert not is_canonical_node_id("S-1-5-19")  # Local Service
    assert not is_canonical_node_id("S-1-5-20")  # Network Service

    # 3. Scoped versions of S-1-5-32-* and S-1-5-18/19/20 MUST be accepted
    # Domain-SID scoped (Contract 1.3 form)
    assert is_canonical_node_id("domain:sid:S-1-5-21-3623811015-3361044348-30300820:S-1-5-32-544")
    assert is_canonical_node_id("domain:sid:S-1-5-21-3623811015-3361044348-30300820:S-1-5-32-555")
    # GUID-scoped domain
    assert is_canonical_node_id("domain:e0601d76-3eee-a285-d268-ec9e468d321c:S-1-5-32-544")
    # Host GUID-scoped
    assert is_canonical_node_id("host:e0601d76-3eee-a285-d268-ec9e468d321c:S-1-5-18")
    assert is_canonical_node_id("host:e0601d76-3eee-a285-d268-ec9e468d321c:S-1-5-19")
    assert is_canonical_node_id("host:e0601d76-3eee-a285-d268-ec9e468d321c:S-1-5-20")

    # 4. Unambiguous domain SIDs and lowercase GUIDs remain valid
    assert is_canonical_node_id("S-1-5-21-3623811015-3361044348-30300820-1001")
    assert is_canonical_node_id("S-1-5-21-3623811015-3361044348-30300820-500")
    assert is_canonical_node_id("e0601d76-3eee-a285-d268-ec9e468d321c")

    # 5. Malformed or non-canonical strings
    assert not is_canonical_node_id("dc01")
    assert not is_canonical_node_id("host:comp1")
    assert not is_canonical_node_id("S-1-5-32-")
    assert not is_canonical_node_id("")
    assert not is_canonical_node_id(123)  # type: ignore
    assert not is_canonical_node_id(None)  # type: ignore

    # 6. Wire query decoding rejects bare scoped-required SIDs
    valid_guid = "e0601d76-3eee-a285-d268-ec9e468d321c"
    valid_sid = "S-1-5-21-3623811015-3361044348-30300820-1001"
    base_query = {
        "query_metadata": {
            "query_id": "q-test-scope",
            "version": "1.0.0",
            "scenario_id": "sc1",
            "scenario_version": "1.0.0",
            "snapshot_id": "sha256:" + "b" * 64,
            "evaluation_mode": "scenario",
            "work_boundary": "boundary",
            "foothold_node_id": valid_sid,
            "target_goal": {"goal_id": "g1", "required_predicates": ["done"]},
            "horizon": "24h",
            "active_work_budget": 3,
        },
        "facts_ledger": {"observed_facts": [], "predicate_layers": {"done": 3}},
        "bound_actions": [
            {
                "action_id": "act1",
                "actor_id": valid_sid,
                "target_id": valid_guid,
                "referenced_work_unit_ids": ["w1"],
                "is_passive_closure": False,
            }
        ],
        "work_units_ledger": {"w1": {"nominal_effort": 1}},
        "conditional_bounds_table": [{"prefix": ["w1"], "lower": "1/2", "upper": "1/2"}],
        "target_impact_assessments": {
            valid_guid: {"target_asset_id": valid_guid, "rating_status": "unrated"}
        },
    }

    # Foothold with bare S-1-5-32-544 rejected
    q_bad_foothold = dict(base_query)
    q_bad_foothold["query_metadata"] = dict(base_query["query_metadata"])
    q_bad_foothold["query_metadata"]["foothold_node_id"] = "S-1-5-32-544"
    with pytest.raises(ValueError, match="Invalid foothold_node_id: 'S-1-5-32-544'"):
        decode_ranking_query(json.dumps(q_bad_foothold))

    # Action actor_id with bare S-1-5-18 rejected
    q_bad_actor = dict(base_query)
    q_bad_actor["bound_actions"] = [
        {
            "action_id": "act1",
            "actor_id": "S-1-5-18",
            "target_id": valid_guid,
            "referenced_work_unit_ids": ["w1"],
            "is_passive_closure": False,
        }
    ]
    with pytest.raises(ValueError, match="bound_actions entry 0 invalid actor_id: 'S-1-5-18'"):
        decode_ranking_query(json.dumps(q_bad_actor))

    # Action target_id with bare S-1-5-20 rejected
    q_bad_target = dict(base_query)
    q_bad_target["bound_actions"] = [
        {
            "action_id": "act1",
            "actor_id": valid_sid,
            "target_id": "S-1-5-20",
            "referenced_work_unit_ids": ["w1"],
            "is_passive_closure": False,
        }
    ]
    with pytest.raises(ValueError, match="bound_actions entry 0 invalid target_id: 'S-1-5-20'"):
        decode_ranking_query(json.dumps(q_bad_target))


def test_undeclared_predicate_across_actions_and_goals_fails_validation():
    """Finding 1 (P1): Predicates in actions and target_goal must have authoritative layer.

    Omitting predicates from predicate_layers and facts_ledger must fail validation
    during query decoding, preventing callers from bypassing Layer 1/2 immutability.
    """
    valid_sid = "S-1-5-21-3623811015-3361044348-30300820-1001"
    valid_guid = "e0601d76-3eee-a285-d268-ec9e468d321c"

    base_query = {
        "query_metadata": {
            "query_id": "q-undeclared-pred",
            "version": "1.0.0",
            "scenario_id": "sc1",
            "scenario_version": "1.0.0",
            "snapshot_id": "sha256:" + "c" * 64,
            "evaluation_mode": "scenario",
            "work_boundary": "boundary",
            "foothold_node_id": valid_sid,
            "target_goal": {"goal_id": "g1", "required_predicates": ["declared_goal"]},
            "horizon": "24h",
            "active_work_budget": 3,
        },
        "facts_ledger": {
            "observed_facts": [],
            "predicate_layers": {"declared_goal": 3, "declared_action": 3},
        },
        "bound_actions": [
            {
                "action_id": "act1",
                "actor_id": valid_sid,
                "target_id": valid_guid,
                "requires": ["declared_action"],
                "adds": ["declared_goal"],
                "referenced_work_unit_ids": ["w1"],
                "is_passive_closure": False,
            }
        ],
        "work_units_ledger": {"w1": {"nominal_effort": 1}},
        "conditional_bounds_table": [{"prefix": ["w1"], "lower": "1/2", "upper": "1/2"}],
        "target_impact_assessments": {
            valid_guid: {
                "target_asset_id": valid_guid,
                "rating_status": "rated",
                "consequence_rating": "Critical",
            }
        },
    }

    # 1. Undeclared predicate in bound_actions.adds
    q_bad_adds = json.loads(json.dumps(base_query))
    q_bad_adds["bound_actions"][0]["adds"] = ["undeclared_add_pred"]
    with pytest.raises(
        ValueError,
        match=(
            "Missing authoritative layer classification for predicate 'undeclared_add_pred' "
            "in bound_actions entry 0 \\(adds\\)"
        ),
    ):
        decode_ranking_query(json.dumps(q_bad_adds))

    # 2. Undeclared predicate in bound_actions.requires
    q_bad_requires = json.loads(json.dumps(base_query))
    q_bad_requires["bound_actions"][0]["requires"] = ["undeclared_req_pred"]
    with pytest.raises(
        ValueError,
        match=(
            "Missing authoritative layer classification for predicate 'undeclared_req_pred' "
            "in bound_actions entry 0 \\(requires\\)"
        ),
    ):
        decode_ranking_query(json.dumps(q_bad_requires))

    # 3. Undeclared predicate in target_goal.required_predicates
    q_bad_goal = json.loads(json.dumps(base_query))
    q_bad_goal["query_metadata"]["target_goal"]["required_predicates"] = ["undeclared_goal_pred"]
    with pytest.raises(
        ValueError,
        match=(
            "Missing authoritative layer classification for predicate 'undeclared_goal_pred' "
            "in target_goal.required_predicates"
        ),
    ):
        decode_ranking_query(json.dumps(q_bad_goal))


def test_undeclared_predicate_in_candidate_required_predicates_fails_validation():
    """Finding 1 (P1): Predicates in candidate required_predicates must have authoritative layer."""
    valid_sid = "S-1-5-21-3623811015-3361044348-30300820-1001"
    valid_guid = "e0601d76-3eee-a285-d268-ec9e468d321c"

    query_payload = {
        "query_metadata": {
            "query_id": "q-cand-req",
            "version": "1.0.0",
            "scenario_id": "sc1",
            "scenario_version": "1.0.0",
            "snapshot_id": "sha256:" + "d" * 64,
            "evaluation_mode": "scenario",
            "work_boundary": "boundary",
            "foothold_node_id": valid_sid,
            "target_goal": {"goal_id": "g1", "required_predicates": ["done"]},
            "horizon": "24h",
            "active_work_budget": 3,
        },
        "facts_ledger": {
            "observed_facts": [],
            "predicate_layers": {"done": 3},
        },
        "bound_actions": [
            {
                "action_id": "act1",
                "actor_id": valid_sid,
                "target_id": valid_guid,
                "requires": [],
                "adds": ["done"],
                "referenced_work_unit_ids": ["w1"],
                "is_passive_closure": False,
            }
        ],
        "work_units_ledger": {"w1": {"nominal_effort": 1}},
        "conditional_bounds_table": [{"prefix": ["w1"], "lower": "1/2", "upper": "1/2"}],
        "target_impact_assessments": {
            valid_guid: {
                "target_asset_id": valid_guid,
                "rating_status": "rated",
                "consequence_rating": "Critical",
            }
        },
    }

    candidates = [
        {
            "candidate_id": "cand_bad_pred",
            "target_asset_id": valid_guid,
            "bound_action_ids": ["act1"],
            "required_predicates": ["undeclared_cand_req"],
        }
    ]

    with pytest.raises(
        ValueError,
        match=(
            "Missing authoritative layer classification for predicate 'undeclared_cand_req' "
            "in candidate 'cand_bad_pred' required_predicates"
        ),
    ):
        execute_ranking_roundtrip(json.dumps(query_payload), candidates)


def test_structural_layer1_predicate_cannot_be_mutated_by_action_adds():
    """Finding 1 (P1): Declared Layer 1 predicate cannot be mutated by action adds.

    When replication_authorization is declared as Layer 1 in predicate_layers:
    - An action attempting to add replication_authorization is ignored in replay.
    - Subsequent action requiring replication_authorization evaluates to Unknown.
    - Candidate status is 'unknown' and pareto_frontier is empty (candidate is not feasible).
    """
    user_sid = "S-1-5-21-3623811015-3361044348-30300820-1001"
    host_sid = "S-1-5-21-3623811015-3361044348-30300820-1002"
    da_sid = "S-1-5-21-3623811015-3361044348-30300820-1000"

    edge_1 = canonical_edge_id(user_sid, host_sid, "GenericAll")
    edge_2 = canonical_edge_id(host_sid, da_sid, "GetChangesAll")

    query_payload = {
        "query_metadata": {
            "query_id": "q-layer1-mutation-repro",
            "version": "1.0.0",
            "scenario_id": "scen_l1",
            "scenario_version": "1.0.0",
            "snapshot_id": SNAPSHOT_SHA_ZERO,
            "evaluation_mode": "scenario",
            "work_boundary": "active_directory_domain",
            "foothold_node_id": user_sid,
            "target_goal": {
                "goal_id": "S2",
                "description": "Domain takeover",
                "required_predicates": ["target_controlled"],
            },
            "horizon": "72h",
            "active_work_budget": 4,
        },
        "work_units_ledger": {
            "reset": {"nominal_effort": 1, "overlap_state": "independent"},
            "activate": {"nominal_effort": 1, "overlap_state": "independent"},
        },
        "bound_actions": [
            {
                "action_id": "action_reset",
                "actor_id": user_sid,
                "target_id": host_sid,
                "requires": [],
                "adds": ["replication_authorization"],
                "referenced_work_unit_ids": ["reset"],
                "is_passive_closure": False,
                "edge_id": edge_1,
            },
            {
                "action_id": "action_activate",
                "actor_id": host_sid,
                "target_id": da_sid,
                "requires": ["replication_authorization"],
                "adds": ["target_controlled"],
                "referenced_work_unit_ids": ["activate"],
                "is_passive_closure": False,
                "edge_id": edge_2,
            },
        ],
        "conditional_bounds_table": [
            {"prefix": ["reset"], "lower": "1/2", "upper": "1/2"},
            {"prefix": ["reset", "activate"], "lower": "1/4", "upper": "1/4"},
        ],
        "target_impact_assessments": {
            da_sid: {
                "target_asset_id": da_sid,
                "rating_status": "rated",
                "consequence_rating": "Critical",
            },
        },
        "facts_ledger": {
            "observed_facts": [],
            "assumed_facts": [],
            "unknown_facts": [],
            "predicate_layers": {
                "replication_authorization": 1,
                "target_controlled": 3,
            },
        },
    }

    candidates = [
        {
            "candidate_id": "cand_a_to_b",
            "target_asset_id": da_sid,
            "bound_action_ids": ["action_reset", "action_activate"],
            "structural_routes": [
                {
                    "node_ids": [user_sid, host_sid, da_sid],
                    "edge_ids": [edge_1, edge_2],
                    "provenance_locators": ["loc:1", "loc:2"],
                }
            ],
        }
    ]

    res = execute_ranking_roundtrip(json.dumps(query_payload), candidates)["roundtrip_result"]

    # Candidate must NOT be feasible or reach the Pareto frontier
    assert res["pareto_frontier"] == []
    assert "cand_a_to_b" in res["diagnostics"]
    diag = res["diagnostics"]["cand_a_to_b"]
    assert diag["assessment"]["status"] == "unknown"
    assert "unknown" in diag["reasons"]
    assert diag["assessment"]["gates_evaluation"]["replication_authorization"] == "Unknown"


def test_wire_adapter_exported_governance_and_reconciliation_functions():
    """Verify wire adapter exports IoU, Epistemic Uncertainty, Kappa, and Reconciliation helpers."""
    from scripts.research.path_ranking_wire_adapter import (
        check_epistemic_uncertainty,
        compute_interval_iou,
        compute_kappa_with_fallback,
        reconcile_expert_ratings,
    )

    # 1. compute_interval_iou
    # Identical point bounds
    assert compute_interval_iou((0.5, 0.5), (0.5, 0.5)) == 1.0
    # Distinct point bounds
    assert compute_interval_iou((0.3, 0.3), (0.7, 0.7)) == 0.0
    # Overlapping intervals
    overlap_iou = compute_interval_iou((0.6, 0.8), (0.7, 0.9))
    assert abs(overlap_iou - (1.0 / 3.0)) < 1e-6
    # Non-overlapping intervals
    assert compute_interval_iou((0.1, 0.3), (0.5, 0.7)) == 0.0

    # 2. check_epistemic_uncertainty
    assert check_epistemic_uncertainty((0.1, 0.8), threshold=0.50) is True
    assert check_epistemic_uncertainty((0.6, 0.7), threshold=0.50) is False
    assert check_epistemic_uncertainty((0.2, 0.7), threshold=0.50) is False
    assert check_epistemic_uncertainty((0.2, 0.71), threshold=0.50) is True

    # 3. compute_kappa_with_fallback
    # Empty
    empty_k = compute_kappa_with_fallback([], [])
    assert empty_k["status"] == "empty_ratings"
    assert empty_k["kappa"] is None

    # Degenerate zero variance
    deg_k = compute_kappa_with_fallback(["Critical", "Critical"], ["Critical", "Critical"])
    assert deg_k["status"] == "degenerate_zero_variance"
    assert deg_k["kappa"] is None
    assert deg_k["observed_agreement"] == 1.0

    # Valid kappa with small sample warning
    val_k = compute_kappa_with_fallback(["Low", "High", "Critical"], ["Low", "High", "Critical"])
    assert val_k["status"] == "valid"
    assert val_k["kappa"] == 1.0
    assert val_k["small_sample_size_warning"] is True

    # 4. reconcile_expert_ratings with proper binding and schema
    target_sid = "S-1-5-21-3623811015-3361044348-30300820-1000"
    # Impact consensus
    imp_r1 = {
        "record_type": "impact_rating",
        "target_asset_id": target_sid,
        "success_event": "terminal_compromise_dc01",
        "consequence_rating": "Critical",
        "evaluator": "expert_sec_01",
        "business_rationale": "Full DC control compromised.",
    }
    imp_r2 = {
        "record_type": "impact_rating",
        "target_asset_id": target_sid,
        "success_event": "terminal_compromise_dc01",
        "consequence_rating": "Critical",
        "evaluator": "expert_sec_02",
        "business_rationale": "Loss of enterprise identity boundaries.",
    }
    reconciled_imp = reconcile_expert_ratings(imp_r1, imp_r2)
    assert reconciled_imp["status"] == "consensus"
    assert reconciled_imp["consequence_rating"] == "Critical"
    assert reconciled_imp["proposal_verdict"] == "proposed_consensus"
    assert reconciled_imp["binding"]["target_asset_id"] == target_sid

    # Impact disagreement
    imp_r3 = dict(imp_r2, consequence_rating="High")
    imp_disagree = reconcile_expert_ratings(imp_r1, imp_r3)
    assert imp_disagree["status"] == "disagreement"
    assert imp_disagree["consequence_rating"] is None
    assert imp_disagree["proposal_verdict"] == "requires_reconciliation_panel"

    # Likelihood consensus with outer bound expansion (IoU >= 0.50)
    lh_r1 = {
        "record_type": "conditional_likelihood",
        "scenario_id": "scenario-corp",
        "ordered_work_prefix": ["step1", "step2"],
        "conditional_bounds": {"lower": "6/10", "upper": "8/10"},
        "target_population": "Internal Active Directory Enterprise Topology",
        "operational_horizon": "72h",
        "evaluator": "expert_sec_01",
    }
    lh_r2 = {
        "record_type": "conditional_likelihood",
        "scenario_id": "scenario-corp",
        "ordered_work_prefix": ["step1", "step2"],
        "conditional_bounds": {"lower": "65/100", "upper": "85/100"},
        "target_population": "Internal Active Directory Enterprise Topology",
        "operational_horizon": "72h",
        "evaluator": "expert_sec_02",
    }
    reconciled_lh = reconcile_expert_ratings(lh_r1, lh_r2)
    assert reconciled_lh["status"] == "reconciled"
    assert reconciled_lh["reconciled_bounds"] == ("3/5", "17/20")
    assert reconciled_lh["high_epistemic_uncertainty"] is False
    assert reconciled_lh["proposal_verdict"] == "proposed_consensus"
    assert reconciled_lh["binding"]["scenario_id"] == "scenario-corp"
    assert (
        reconciled_lh["binding"]["target_population"]
        == "Internal Active Directory Enterprise Topology"
    )
    assert reconciled_lh["binding"]["operational_horizon"] == "72h"

    # Likelihood disagreement when IoU < 0.50
    lh_r3 = {
        "record_type": "conditional_likelihood",
        "scenario_id": "scenario-corp",
        "ordered_work_prefix": ["step1", "step2"],
        "conditional_bounds": {"lower": "8/10", "upper": "95/100"},
        "target_population": "Internal Active Directory Enterprise Topology",
        "operational_horizon": "72h",
        "evaluator": "expert_sec_02",
    }
    disagree_lh = reconcile_expert_ratings(lh_r1, lh_r3)
    assert disagree_lh["status"] == "disagreement"
    assert disagree_lh["proposal_verdict"] == "requires_reconciliation_panel"

    # Effort within delta <= 1 using nested rubric_evaluation
    eff_r1 = {
        "record_type": "work_unit_effort",
        "work_unit_id": "unit_pwd_reset",
        "technique_name": "genericall_reset_password",
        "actor_scope": "user_a",
        "target_scope": "user_b",
        "rubric_evaluation": {
            "t1_complexity": 1,
            "t2_friction": 2,
            "formula": "base",
            "computed_cost": 1,
        },
        "evaluator": "expert_sec_01",
    }
    eff_r2 = {
        "record_type": "work_unit_effort",
        "work_unit_id": "unit_pwd_reset",
        "technique_name": "genericall_reset_password",
        "actor_scope": "user_a",
        "target_scope": "user_b",
        "rubric_evaluation": {
            "t1_complexity": 2,
            "t2_friction": 2,
            "formula": "base",
            "computed_cost": 2,
        },
        "evaluator": "expert_sec_02",
    }
    reconciled_eff = reconcile_expert_ratings(eff_r1, eff_r2)
    assert reconciled_eff["status"] == "reconciled"
    assert reconciled_eff["cost_delta"] == 1
    assert reconciled_eff["resolved_cost"] == 2  # Conservative max

    # Effort valid cost 0 (passive closure or T1=1, T2=1)
    eff_zero_1 = {
        "record_type": "work_unit_effort",
        "work_unit_id": "unit_memberof",
        "technique_name": "memberof_group_nesting",
        "actor_scope": "user_b",
        "target_scope": "group_server_ops",
        "rubric_evaluation": {
            "t1_complexity": 1,
            "t2_friction": 1,
            "formula": "base",
            "computed_cost": 0,
        },
        "evaluator": "expert_sec_01",
    }
    eff_zero_2 = dict(eff_zero_1, evaluator="expert_sec_02")
    reconciled_zero = reconcile_expert_ratings(eff_zero_1, eff_zero_2)
    assert reconciled_zero["status"] == "reconciled"
    assert reconciled_zero["resolved_cost"] == 0

    # Effort delta = 2 (C=3 vs C=1) requires panel reconciliation
    eff_diff_2 = {
        "record_type": "work_unit_effort",
        "work_unit_id": "unit_pwd_reset",
        "technique_name": "genericall_reset_password",
        "actor_scope": "user_a",
        "target_scope": "user_b",
        "rubric_evaluation": {
            "t1_complexity": 2,
            "t2_friction": 3,
            "formula": "base",
            "computed_cost": 3,
        },
        "evaluator": "expert_sec_02",
    }
    reconciled_diff = reconcile_expert_ratings(eff_r1, eff_diff_2)
    assert reconciled_diff["status"] == "disagreement"
    assert reconciled_diff["cost_delta"] == 2
    assert reconciled_diff["proposal_verdict"] == "requires_reconciliation_panel"


def test_reconciliation_negative_and_validation_rules():
    """Verify fail-closed rejection of invalid bindings, raters, and bounds in reconciliation."""
    import pytest

    from scripts.research.path_ranking_wire_adapter import reconcile_expert_ratings

    base_imp = {
        "record_type": "impact_rating",
        "target_asset_id": "target_1",
        "success_event": "event_a",
        "consequence_rating": "High",
        "evaluator": "rater_a",
    }

    # 0a. Reject mismatched record_type
    with pytest.raises(ValueError, match="Cannot reconcile different record types"):
        reconcile_expert_ratings(
            base_imp,
            dict(base_imp, record_type="conditional_likelihood", evaluator="rater_b"),
        )

    # 0b. Reject unknown or unsupported record_type
    with pytest.raises(ValueError, match="Unknown or unsupported record_type"):
        reconcile_expert_ratings(
            dict(base_imp, record_type="unknown_type"),
            dict(base_imp, record_type="unknown_type", evaluator="rater_b"),
        )

    # 1. Reject identical evaluator
    with pytest.raises(ValueError, match="Evaluators must be distinct"):
        reconcile_expert_ratings(base_imp, dict(base_imp, evaluator="rater_a"))

    # 2. Reject pending evaluator
    with pytest.raises(ValueError, match="pending evaluators"):
        reconcile_expert_ratings(base_imp, dict(base_imp, evaluator="PENDING_RATER_2"))

    # 2b. Reject whitespace-only evaluator
    with pytest.raises(ValueError, match="Missing or blank evaluator"):
        reconcile_expert_ratings(base_imp, dict(base_imp, evaluator="   "))

    # 3. Reject mismatched target asset
    with pytest.raises(ValueError, match="Mismatched target_asset_id"):
        reconcile_expert_ratings(
            base_imp, dict(base_imp, target_asset_id="target_2", evaluator="rater_b")
        )

    # 4. Reject mismatched success event
    with pytest.raises(ValueError, match="Mismatched success_event"):
        reconcile_expert_ratings(
            base_imp, dict(base_imp, success_event="event_b", evaluator="rater_b")
        )

    # 5. Reject pending/invalid consequence rating
    with pytest.raises(ValueError, match="Invalid or pending consequence_rating"):
        reconcile_expert_ratings(
            base_imp, dict(base_imp, consequence_rating="PENDING", evaluator="rater_b")
        )

    # 6. Reject mismatched ordered_work_prefix in likelihood
    base_lh = {
        "record_type": "conditional_likelihood",
        "scenario_id": "scen_a",
        "ordered_work_prefix": ["act1", "act2"],
        "conditional_bounds": {"lower": "1/2", "upper": "3/4"},
        "target_population": "Internal Active Directory Enterprise Topology",
        "operational_horizon": "72h",
        "evaluator": "rater_a",
    }
    with pytest.raises(ValueError, match="Mismatched ordered_work_prefix"):
        reconcile_expert_ratings(
            base_lh, dict(base_lh, ordered_work_prefix=["act1"], evaluator="rater_b")
        )

    # 6b. Reject missing or mismatched operational_horizon
    with pytest.raises(ValueError, match="Missing operational_horizon"):
        lh_no_horiz = dict(base_lh)
        del lh_no_horiz["operational_horizon"]
        reconcile_expert_ratings(base_lh, dict(lh_no_horiz, evaluator="rater_b"))
    with pytest.raises(ValueError, match="Mismatched operational_horizon"):
        reconcile_expert_ratings(
            base_lh, dict(base_lh, operational_horizon="24h", evaluator="rater_b")
        )
    with pytest.raises(ValueError, match="pending operational_horizon"):
        reconcile_expert_ratings(
            base_lh, dict(base_lh, operational_horizon="PENDING_HORIZON", evaluator="rater_b")
        )

    # 6c. Reject missing or mismatched target_population
    with pytest.raises(ValueError, match="Missing target_population"):
        lh_no_pop = dict(base_lh)
        del lh_no_pop["target_population"]
        reconcile_expert_ratings(base_lh, dict(lh_no_pop, evaluator="rater_b"))
    with pytest.raises(ValueError, match="Mismatched target_population"):
        reconcile_expert_ratings(
            base_lh, dict(base_lh, target_population="Other Population", evaluator="rater_b")
        )
    with pytest.raises(ValueError, match="pending target_population"):
        reconcile_expert_ratings(
            base_lh, dict(base_lh, target_population="PENDING_POPULATION", evaluator="rater_b")
        )

    # 7. Reject invalid bounds: l > u or bounds > 1
    with pytest.raises(ValueError, match="Conditional bounds out of probability range"):
        reconcile_expert_ratings(
            base_lh,
            dict(base_lh, conditional_bounds={"lower": "4/5", "upper": "1/2"}, evaluator="rater_b"),
        )
    with pytest.raises(ValueError, match="Conditional bounds out of probability range"):
        reconcile_expert_ratings(
            base_lh,
            dict(base_lh, conditional_bounds={"lower": "2", "upper": "3"}, evaluator="rater_b"),
        )

    # 8. Reject formula inconsistency and rubric violations in effort
    valid_eff = {
        "record_type": "work_unit_effort",
        "work_unit_id": "unit_1",
        "technique_name": "tech_a",
        "actor_scope": "user_a",
        "target_scope": "user_b",
        "rubric_evaluation": {
            "t1_complexity": 1,
            "t2_friction": 2,
            "formula": "base",
            "computed_cost": 1,
        },
        "evaluator": "rater_b",
    }
    bad_formula_eff = {
        "record_type": "work_unit_effort",
        "work_unit_id": "unit_1",
        "technique_name": "tech_a",
        "actor_scope": "user_a",
        "target_scope": "user_b",
        "rubric_evaluation": {
            "t1_complexity": 1,
            "t2_friction": 2,
            "formula": "base",
            "computed_cost": 2,  # Inconsistent: 1 + 2 - 2 = 1 != 2 (both in range)
        },
        "evaluator": "rater_a",
    }
    with pytest.raises(ValueError, match="Formula consistency check failed"):
        reconcile_expert_ratings(bad_formula_eff, valid_eff)

    # 8a2. Reject out of range computed_cost
    out_of_range_cost_eff = {
        "record_type": "work_unit_effort",
        "work_unit_id": "unit_1",
        "technique_name": "tech_a",
        "actor_scope": "user_a",
        "target_scope": "user_b",
        "rubric_evaluation": {
            "t1_complexity": 1,
            "t2_friction": 2,
            "formula": "base",
            "computed_cost": 5,  # Out of range [0, 4]
        },
        "evaluator": "rater_a",
    }
    with pytest.raises(ValueError, match="computed_cost must be in range"):
        reconcile_expert_ratings(out_of_range_cost_eff, valid_eff)

    # 8b. Reject unsupported/pending rubric formula
    unsupported_formula_eff = {
        "record_type": "work_unit_effort",
        "work_unit_id": "unit_1",
        "technique_name": "tech_a",
        "actor_scope": "user_a",
        "target_scope": "user_b",
        "rubric_evaluation": {
            "t1_complexity": 1,
            "t2_friction": 2,
            "formula": "PENDING",
            "computed_cost": 1,
        },
        "evaluator": "rater_a",
    }
    with pytest.raises(ValueError, match="Unsupported or pending rubric formula"):
        reconcile_expert_ratings(unsupported_formula_eff, valid_eff)

    # 8c. Reject missing rubric_evaluation (no top-level computed_cost bypass)
    bypass_eff = {
        "record_type": "work_unit_effort",
        "work_unit_id": "unit_1",
        "technique_name": "tech_a",
        "actor_scope": "user_a",
        "target_scope": "user_b",
        "computed_cost": 1,
        "evaluator": "rater_a",
    }
    with pytest.raises(ValueError, match="missing mandatory rubric_evaluation"):
        reconcile_expert_ratings(bypass_eff, valid_eff)

    # 8d. Reject float / non-integer types in rubric_evaluation
    float_eff = {
        "record_type": "work_unit_effort",
        "work_unit_id": "unit_1",
        "technique_name": "tech_a",
        "actor_scope": "user_a",
        "target_scope": "user_b",
        "rubric_evaluation": {
            "t1_complexity": 1,
            "t2_friction": 2,
            "formula": "base",
            "computed_cost": 1.0,
        },
        "evaluator": "rater_a",
    }
    with pytest.raises(TypeError, match="Rubric evaluation values must be integers"):
        reconcile_expert_ratings(float_eff, valid_eff)

    # 8e. Reject mismatched effort metadata
    with pytest.raises(ValueError, match="Mismatched technique_name"):
        reconcile_expert_ratings(
            dict(valid_eff, evaluator="rater_a", technique_name="other_tech"),
            valid_eff,
        )
    with pytest.raises(ValueError, match="Mismatched actor_scope"):
        reconcile_expert_ratings(
            dict(valid_eff, evaluator="rater_a", actor_scope="other_actor"),
            valid_eff,
        )
    with pytest.raises(ValueError, match="Mismatched target_scope"):
        reconcile_expert_ratings(
            dict(valid_eff, evaluator="rater_a", target_scope="other_target"),
            valid_eff,
        )


def test_exact_rational_iou_and_boundary_behavior():
    """Verify that exact rational IoU prevents float rounding error at 0.50 threshold."""
    from fractions import Fraction

    from scripts.research.path_ranking_wire_adapter import (
        check_epistemic_uncertainty,
        compute_interval_iou,
        reconcile_expert_ratings,
    )

    # Exactly 0.50 threshold: R1=[3/10, 3/5], R2=[2/5, 7/10]
    # Inter: [4/10, 6/10] -> 2/10 = 1/5
    # Union: [3/10, 7/10] -> 4/10 = 2/5
    # IoU: (1/5) / (2/5) = 1/2 = 0.50 exactly.
    # In pure float math, 0.2 / 0.4 could produce 0.49999999999999994.
    # With exact Fraction, IoU is Fraction(1, 2) and must reconcile as consensus!
    r1 = {
        "record_type": "conditional_likelihood",
        "scenario_id": "scen_boundary",
        "ordered_work_prefix": ["step_a"],
        "conditional_bounds": {"lower": "3/10", "upper": "3/5"},
        "target_population": "Internal Active Directory Enterprise Topology",
        "operational_horizon": "72h",
        "evaluator": "rater_1",
    }
    r2_exact_half = {
        "record_type": "conditional_likelihood",
        "scenario_id": "scen_boundary",
        "ordered_work_prefix": ["step_a"],
        "conditional_bounds": {"lower": "2/5", "upper": "7/10"},
        "target_population": "Internal Active Directory Enterprise Topology",
        "operational_horizon": "72h",
        "evaluator": "rater_2",
    }

    # Verify helper directly
    exact_iou = compute_interval_iou(
        (Fraction(3, 10), Fraction(3, 5)),
        (Fraction(2, 5), Fraction(7, 10)),
    )
    assert exact_iou == Fraction(1, 2)

    # Verify reconciliation produces reconciled proposed_consensus
    recon = reconcile_expert_ratings(r1, r2_exact_half)
    assert recon["status"] == "reconciled"
    assert recon["proposal_verdict"] == "proposed_consensus"
    assert recon["inter_rater_iou"] == 0.5

    # Just below 0.50: R2=[21/50, 7/10] (lower=0.42 instead of 0.40)
    # Inter: [42/100, 60/100] -> 18/100 = 9/50
    # Union: [30/100, 70/100] -> 40/100 = 2/5 = 20/50
    # IoU: (9/50) / (20/50) = 9/20 = 0.45 < 0.50 -> disagreement!
    r2_below_half = dict(
        r2_exact_half,
        conditional_bounds={"lower": "21/50", "upper": "7/10"},
    )
    recon_below = reconcile_expert_ratings(r1, r2_below_half)
    assert recon_below["status"] == "disagreement"
    assert recon_below["proposal_verdict"] == "requires_reconciliation_panel"

    # Epistemic uncertainty exact width checks:
    # Width exactly 1/2 is not high uncertainty (strictly > 0.50 required)
    assert check_epistemic_uncertainty((Fraction(1, 4), Fraction(3, 4))) is False
    # Width 51/100 > 1/2 is high uncertainty
    assert check_epistemic_uncertainty((Fraction(0, 1), Fraction(51, 100))) is True


def test_effort_metadata_definition_consistency_and_regressions():
    """Verify that effort metadata is complete, non-pending, and consistent with work units."""
    import pytest

    from scripts.research.path_ranking_wire_adapter import reconcile_expert_ratings

    canonical_id = (
        "pwd_reset:S-1-5-21-3623811015-3361044348-30300820-1002:"
        "S-1-5-21-3623811015-3361044348-30300820-1003:corp_net:ad_boundary:v1"
    )

    base_r1 = {
        "record_type": "work_unit_effort",
        "work_unit_id": canonical_id,
        "technique_name": "genericall_reset_password",
        "actor_scope": "S-1-5-21-3623811015-3361044348-30300820-1002",
        "target_scope": "S-1-5-21-3623811015-3361044348-30300820-1003",
        "rubric_evaluation": {
            "t1_complexity": 1,
            "t2_friction": 1,
            "formula": "base",
            "computed_cost": 0,
        },
        "evaluator": "expert_sec_01",
    }
    base_r2 = dict(base_r1, evaluator="expert_sec_02")

    # Baseline valid case: reconciles as proposed_consensus
    recon = reconcile_expert_ratings(base_r1, base_r2)
    assert recon["status"] == "reconciled"
    assert recon["proposal_verdict"] == "proposed_consensus"
    assert recon["binding"]["actor_scope"] == "S-1-5-21-3623811015-3361044348-30300820-1002"
    assert recon["binding"]["target_scope"] == "S-1-5-21-3623811015-3361044348-30300820-1003"
    assert recon["binding"]["technique_name"] == "genericall_reset_password"

    # Regression 1: Both raters omit technique_name, actor_scope, target_scope
    r1_missing = dict(base_r1)
    del r1_missing["technique_name"]
    del r1_missing["actor_scope"]
    del r1_missing["target_scope"]
    r2_missing = dict(r1_missing, evaluator="expert_sec_02")
    with pytest.raises(ValueError, match="Missing mandatory effort metadata"):
        reconcile_expert_ratings(r1_missing, r2_missing)

    # Regression 1b: Both raters provide blank/whitespace metadata
    r1_blank = dict(base_r1, actor_scope="   ")
    r2_blank = dict(base_r2, actor_scope="   ")
    with pytest.raises(ValueError, match="Blank effort metadata"):
        reconcile_expert_ratings(r1_blank, r2_blank)

    # Regression 1c: Both raters provide pending metadata
    r1_pending = dict(base_r1, actor_scope="PENDING_ACTOR")
    r2_pending = dict(base_r2, actor_scope="PENDING_ACTOR")
    with pytest.raises(ValueError, match="Cannot reconcile pending effort metadata"):
        reconcile_expert_ratings(r1_pending, r2_pending)

    # Regression 2: Both raters supply WRONG actor_scope (BOB instead of ALICE) for canonical ID
    r1_wrong_actor = dict(base_r1, actor_scope="S-1-5-21-3623811015-3361044348-30300820-1003")
    r2_wrong_actor = dict(base_r2, actor_scope="S-1-5-21-3623811015-3361044348-30300820-1003")
    with pytest.raises(
        ValueError, match="Metadata actor_scope .* is inconsistent with work unit definition"
    ):
        reconcile_expert_ratings(r1_wrong_actor, r2_wrong_actor)

    # Regression 2b: Both raters supply WRONG target_scope (ALICE instead of BOB) for canonical ID
    r1_wrong_target = dict(base_r1, target_scope="S-1-5-21-3623811015-3361044348-30300820-1002")
    r2_wrong_target = dict(base_r2, target_scope="S-1-5-21-3623811015-3361044348-30300820-1002")
    with pytest.raises(
        ValueError, match="Metadata target_scope .* is inconsistent with work unit definition"
    ):
        reconcile_expert_ratings(r1_wrong_target, r2_wrong_target)

    # Regression 2c: Both raters supply WRONG technique_name for canonical ID
    r1_wrong_tech = dict(base_r1, technique_name="psremote_execute")
    r2_wrong_tech = dict(base_r2, technique_name="psremote_execute")
    with pytest.raises(
        ValueError, match="Metadata technique_name .* is inconsistent with work unit definition"
    ):
        reconcile_expert_ratings(r1_wrong_tech, r2_wrong_tech)

    # Regression 2d: Both raters supply substring technique_name (substring attack rejected)
    r1_sub_tech = dict(base_r1, technique_name="genericall_reset_password_and_dcsync")
    r2_sub_tech = dict(base_r2, technique_name="genericall_reset_password_and_dcsync")
    with pytest.raises(
        ValueError, match="Metadata technique_name .* is inconsistent with work unit definition"
    ):
        reconcile_expert_ratings(r1_sub_tech, r2_sub_tech)

    # Regression 2e: Both raters supply valid technique alias (pwd_reset)
    r1_alias_tech = dict(base_r1, technique_name="pwd_reset")
    r2_alias_tech = dict(base_r2, technique_name="pwd_reset")
    recon_alias = reconcile_expert_ratings(r1_alias_tech, r2_alias_tech)
    assert recon_alias["status"] == "reconciled"
    assert recon_alias["binding"]["technique_name"] == "pwd_reset"

    # Regression 3: Opaque work_unit_id without authoritative registry must fail closed
    opaque_r1 = dict(base_r1, work_unit_id="unregistered_custom_unit")
    opaque_r2 = dict(base_r2, work_unit_id="unregistered_custom_unit")
    with pytest.raises(
        ValueError,
        match="Cannot validate opaque work_unit_id .* without authoritative work_unit_registry",
    ):
        reconcile_expert_ratings(opaque_r1, opaque_r2)

    # Regression 3b: Opaque work_unit_id WITH authoritative registry succeeds when consistent
    custom_registry = {
        "unregistered_custom_unit": {
            "technique_name": "genericall_reset_password",
            "actor_scope": "S-1-5-21-3623811015-3361044348-30300820-1002",
            "target_scope": "S-1-5-21-3623811015-3361044348-30300820-1003",
        }
    }
    recon_opaque = reconcile_expert_ratings(
        opaque_r1, opaque_r2, work_unit_registry=custom_registry
    )
    assert recon_opaque["status"] == "reconciled"
    assert recon_opaque["binding"]["work_unit_id"] == "unregistered_custom_unit"

    # Regression 3c: Opaque work_unit_id WITH authoritative registry rejects conflicting metadata
    conflicting_registry = {
        "unregistered_custom_unit": {
            "technique_name": "genericall_reset_password",
            "actor_scope": "OTHER_ACTOR_SID",
            "target_scope": "S-1-5-21-3623811015-3361044348-30300820-1003",
        }
    }
    with pytest.raises(ValueError, match="is inconsistent with work unit definition"):
        reconcile_expert_ratings(opaque_r1, opaque_r2, work_unit_registry=conflicting_registry)

    # Regression 3d: Registry entry must be authoritative and complete (reject empty/partial)
    with pytest.raises(ValueError, match="missing mandatory technique definition"):
        reconcile_expert_ratings(
            opaque_r1, opaque_r2, work_unit_registry={"unregistered_custom_unit": {}}
        )

    with pytest.raises(ValueError, match="missing mandatory actor definition"):
        reconcile_expert_ratings(
            opaque_r1,
            opaque_r2,
            work_unit_registry={
                "unregistered_custom_unit": {"technique_name": "genericall_reset_password"}
            },
        )

    with pytest.raises(ValueError, match="missing mandatory target definition"):
        reconcile_expert_ratings(
            opaque_r1,
            opaque_r2,
            work_unit_registry={
                "unregistered_custom_unit": {
                    "technique_name": "genericall_reset_password",
                    "actor_scope": "S-1-5-21-3623811015-3361044348-30300820-1002",
                }
            },
        )

    with pytest.raises(ValueError, match="Blank actor in work unit definition"):
        reconcile_expert_ratings(
            opaque_r1,
            opaque_r2,
            work_unit_registry={
                "unregistered_custom_unit": {
                    "technique_name": "genericall_reset_password",
                    "actor_scope": "   ",
                    "target_scope": "S-1-5-21-3623811015-3361044348-30300820-1003",
                }
            },
        )

    with pytest.raises(ValueError, match="Pending target in work unit definition"):
        reconcile_expert_ratings(
            opaque_r1,
            opaque_r2,
            work_unit_registry={
                "unregistered_custom_unit": {
                    "technique_name": "genericall_reset_password",
                    "actor_scope": "S-1-5-21-3623811015-3361044348-30300820-1002",
                    "target_scope": "PENDING_TARGET",
                }
            },
        )

    with pytest.raises(ValueError, match="expected dict"):
        reconcile_expert_ratings(
            opaque_r1, opaque_r2, work_unit_registry={"unregistered_custom_unit": "not_a_dict"}
        )

    # Regression 4: Registry definition cannot override canonical work_unit_id components
    # 4a: Registry conflicts on technique
    conflict_tech_reg = {
        canonical_id: {
            "technique_name": "psremote_execute",
            "actor_scope": "S-1-5-21-3623811015-3361044348-30300820-1002",
            "target_scope": "S-1-5-21-3623811015-3361044348-30300820-1003",
        }
    }
    with pytest.raises(
        ValueError, match="Registry definition technique .* conflicts with canonical ID technique"
    ):
        reconcile_expert_ratings(base_r1, base_r2, work_unit_registry=conflict_tech_reg)

    # 4b: Registry conflicts on actor
    conflict_actor_reg = {
        canonical_id: {
            "technique_name": "genericall_reset_password",
            "actor_scope": "S-1-5-21-3623811015-3361044348-30300820-1003",  # BOB instead of ALICE
            "target_scope": "S-1-5-21-3623811015-3361044348-30300820-1003",
        }
    }
    with pytest.raises(
        ValueError, match="Registry definition actor .* conflicts with canonical ID actor"
    ):
        reconcile_expert_ratings(base_r1, base_r2, work_unit_registry=conflict_actor_reg)

    # 4c: Registry conflicts on target
    conflict_target_reg = {
        canonical_id: {
            "technique_name": "genericall_reset_password",
            "actor_scope": "S-1-5-21-3623811015-3361044348-30300820-1002",
            "target_scope": "S-1-5-21-3623811015-3361044348-30300820-1002",  # ALICE instead of BOB
        }
    }
    with pytest.raises(
        ValueError, match="Registry definition target .* conflicts with canonical ID target"
    ):
        reconcile_expert_ratings(base_r1, base_r2, work_unit_registry=conflict_target_reg)

    # 4d: Registry conflicts on context_scope
    conflict_ctx_reg = {
        canonical_id: {
            "technique_name": "genericall_reset_password",
            "actor_scope": "S-1-5-21-3623811015-3361044348-30300820-1002",
            "target_scope": "S-1-5-21-3623811015-3361044348-30300820-1003",
            "context_scope": "other_net",
        }
    }
    with pytest.raises(
        ValueError,
        match="Registry definition context_scope .* conflicts with canonical ID context",
    ):
        reconcile_expert_ratings(base_r1, base_r2, work_unit_registry=conflict_ctx_reg)

    # 4e: Registry conflicts on boundary_scope
    conflict_bnd_reg = {
        canonical_id: {
            "technique_name": "genericall_reset_password",
            "actor_scope": "S-1-5-21-3623811015-3361044348-30300820-1002",
            "target_scope": "S-1-5-21-3623811015-3361044348-30300820-1003",
            "boundary_scope": "other_boundary",
        }
    }
    with pytest.raises(
        ValueError,
        match="Registry definition boundary_scope .* conflicts with canonical ID boundary",
    ):
        reconcile_expert_ratings(base_r1, base_r2, work_unit_registry=conflict_bnd_reg)

    # 4f: Registry conflicts on ledger_version
    conflict_ver_reg = {
        canonical_id: {
            "technique_name": "genericall_reset_password",
            "actor_scope": "S-1-5-21-3623811015-3361044348-30300820-1002",
            "target_scope": "S-1-5-21-3623811015-3361044348-30300820-1003",
            "ledger_version": "v2",
        }
    }
    with pytest.raises(
        ValueError,
        match="Registry definition ledger_version .* conflicts with canonical ID ledger_version",
    ):
        reconcile_expert_ratings(base_r1, base_r2, work_unit_registry=conflict_ver_reg)

    # 4g: Registry consistent with canonical ID succeeds
    matching_reg = {
        canonical_id: {
            "technique_name": "genericall_reset_password",
            "actor_scope": "S-1-5-21-3623811015-3361044348-30300820-1002",
            "target_scope": "S-1-5-21-3623811015-3361044348-30300820-1003",
            "context_scope": "corp_net",
            "boundary_scope": "ad_boundary",
            "ledger_version": "v1",
        }
    }
    recon_matching = reconcile_expert_ratings(base_r1, base_r2, work_unit_registry=matching_reg)
    assert recon_matching["status"] == "reconciled"
    assert recon_matching["proposal_verdict"] == "proposed_consensus"

    # 4h: Registry consistent with canonical ID using alias succeeds
    matching_alias_reg = {
        canonical_id: {
            "technique_name": "pwd_reset",
            "actor_scope": "S-1-5-21-3623811015-3361044348-30300820-1002",
            "target_scope": "S-1-5-21-3623811015-3361044348-30300820-1003",
        }
    }
    recon_alias_reg = reconcile_expert_ratings(
        base_r1, base_r2, work_unit_registry=matching_alias_reg
    )
    assert recon_alias_reg["status"] == "reconciled"

    # 4i: Scoped node ID with matching and conflicting registry definition
    scoped_id = (
        "pwd_reset:S-1-5-21-3623811015-3361044348-30300820-1002:"
        "domain:sid:S-1-5-21-3623811015-3361044348-30300820:S-1-5-32-549:"
        "corp_net:ad_boundary:v1"
    )
    scoped_target = "domain:sid:S-1-5-21-3623811015-3361044348-30300820:S-1-5-32-549"
    scoped_r1 = dict(base_r1, work_unit_id=scoped_id, target_scope=scoped_target)
    scoped_r2 = dict(base_r2, work_unit_id=scoped_id, target_scope=scoped_target)
    scoped_reg = {
        scoped_id: {
            "technique_name": "genericall_reset_password",
            "actor_scope": "S-1-5-21-3623811015-3361044348-30300820-1002",
            "target_scope": scoped_target,
        }
    }
    recon_scoped = reconcile_expert_ratings(scoped_r1, scoped_r2, work_unit_registry=scoped_reg)
    assert recon_scoped["status"] == "reconciled"

    conflicting_scoped_reg = {
        scoped_id: {
            "technique_name": "genericall_reset_password",
            "actor_scope": "S-1-5-21-3623811015-3361044348-30300820-1003",
            "target_scope": scoped_target,
        }
    }
    with pytest.raises(
        ValueError, match="Registry definition actor .* conflicts with canonical ID actor"
    ):
        reconcile_expert_ratings(scoped_r1, scoped_r2, work_unit_registry=conflicting_scoped_reg)

    # 4j: Scoped node ID with direct middle definition in registry (from parser)
    from scripts.research.path_ranking_wire_adapter import parse_canonical_work_unit_id

    bob_actor = "S-1-5-21-3623811015-3361044348-30300820-1003"
    alice_actor = "S-1-5-21-3623811015-3361044348-30300820-1002"
    other_scoped_target = "domain:sid:S-1-5-21-3623811015-3361044348-30300820:S-1-5-32-544"

    # Negative 4j-1: Registry definition with middle changing actor to BOB
    wrong_actor_middle_def = parse_canonical_work_unit_id(
        f"pwd_reset:{bob_actor}:{scoped_target}:corp_net:ad_boundary:v1"
    )
    r1_bob_scoped = dict(scoped_r1, actor_scope=bob_actor)
    r2_bob_scoped = dict(scoped_r2, actor_scope=bob_actor)
    with pytest.raises(
        ValueError, match="Registry definition middle .* conflicts with canonical ID middle"
    ):
        reconcile_expert_ratings(
            r1_bob_scoped, r2_bob_scoped, work_unit_registry={scoped_id: wrong_actor_middle_def}
        )

    # Negative 4j-2: Registry definition with middle changing target to OTHER_TARGET
    wrong_target_middle_def = parse_canonical_work_unit_id(
        f"pwd_reset:{alice_actor}:{other_scoped_target}:corp_net:ad_boundary:v1"
    )
    r1_other_scoped = dict(scoped_r1, target_scope=other_scoped_target)
    r2_other_scoped = dict(scoped_r2, target_scope=other_scoped_target)
    with pytest.raises(
        ValueError, match="Registry definition middle .* conflicts with canonical ID middle"
    ):
        reconcile_expert_ratings(
            r1_other_scoped,
            r2_other_scoped,
            work_unit_registry={scoped_id: wrong_target_middle_def},
        )

    # Positive 4j-3: Registry definition with exact middle directly from canonical parser
    valid_middle_def = parse_canonical_work_unit_id(scoped_id)
    recon_valid_middle = reconcile_expert_ratings(
        scoped_r1, scoped_r2, work_unit_registry={scoped_id: valid_middle_def}
    )
    assert recon_valid_middle["status"] == "reconciled"
    assert recon_valid_middle["proposal_verdict"] == "proposed_consensus"

    # 4k: Boundary-shifting and canonical node-ID validation regressions (P1)
    # 4k-1: Boundary-shift attack where concatenation equals middle but actor/target are shifted
    shifted_actor = f"{alice_actor}:domain"
    shifted_target = "sid:S-1-5-21-3623811015-3361044348-30300820:S-1-5-32-549"
    parsed_scoped = parse_canonical_work_unit_id(scoped_id)
    assert parsed_scoped is not None
    assert f"{shifted_actor}:{shifted_target}" == parsed_scoped["middle"]

    r1_shifted = dict(scoped_r1, actor_scope=shifted_actor, target_scope=shifted_target)
    r2_shifted = dict(scoped_r2, actor_scope=shifted_actor, target_scope=shifted_target)
    with pytest.raises(ValueError, match="is not a valid canonical node ID"):
        reconcile_expert_ratings(r1_shifted, r2_shifted)

    # 4k-2: Negative test - non-canonical actor_scope in raw rating record
    r1_bad_actor = dict(scoped_r1, actor_scope="invalid_actor_id")
    r2_bad_actor = dict(scoped_r2, actor_scope="invalid_actor_id")
    with pytest.raises(
        ValueError, match="Metadata actor_scope .* is not a valid canonical node ID"
    ):
        reconcile_expert_ratings(r1_bad_actor, r2_bad_actor)

    # 4k-3: Negative test - non-canonical target_scope in raw record (unscoped local RID)
    unscoped_local_rid = "S-1-5-32-549"
    r1_bad_target = dict(scoped_r1, target_scope=unscoped_local_rid)
    r2_bad_target = dict(scoped_r2, target_scope=unscoped_local_rid)
    with pytest.raises(
        ValueError, match="Metadata target_scope .* is not a valid canonical node ID"
    ):
        reconcile_expert_ratings(r1_bad_target, r2_bad_target)

    # 4k-4: Negative test - registry definition with non-canonical actor
    bad_actor_reg = {
        scoped_id: {
            "technique_name": "genericall_reset_password",
            "actor_scope": "not_a_canonical_actor",
            "target_scope": scoped_target,
        }
    }
    with pytest.raises(
        ValueError, match="Registry definition actor .* is not a valid canonical node ID"
    ):
        reconcile_expert_ratings(scoped_r1, scoped_r2, work_unit_registry=bad_actor_reg)

    # 4k-5: Negative test - registry definition with non-canonical target
    bad_target_reg = {
        scoped_id: {
            "technique_name": "genericall_reset_password",
            "actor_scope": alice_actor,
            "target_scope": "not_a_canonical_target",
        }
    }
    with pytest.raises(
        ValueError, match="Registry definition target .* is not a valid canonical node ID"
    ):
        reconcile_expert_ratings(scoped_r1, scoped_r2, work_unit_registry=bad_target_reg)

    # 4k-6: Negative test - ambiguous middle without structured registry definition fails closed
    ambiguous_scoped_id = "pwd_reset:not_a_sid:another_not_a_sid:corp_net:ad_boundary:v1"
    r1_ambig = dict(base_r1, work_unit_id=ambiguous_scoped_id)
    r2_ambig = dict(base_r2, work_unit_id=ambiguous_scoped_id)
    with pytest.raises(
        ValueError,
        match="has ambiguous middle .* and lacks discrete canonical actor and target definitions",
    ):
        reconcile_expert_ratings(r1_ambig, r2_ambig)

    # 4k-7: Positive test - scoped canonical ID resolves actor/target uniquely without registry
    recon_direct_scoped = reconcile_expert_ratings(scoped_r1, scoped_r2)
    assert recon_direct_scoped["status"] == "reconciled"
    assert recon_direct_scoped["proposal_verdict"] == "proposed_consensus"
    assert recon_direct_scoped["binding"]["actor_scope"] == alice_actor
    assert recon_direct_scoped["binding"]["target_scope"] == scoped_target


def test_synthetic_hand_worked_example_in_brief():
    """Verify that the synthetic worked hand calculation in the brief matches code output 100%."""
    from scripts.research.worked_example_validation import (
        ActionStep,
        assess_scoped_program,
        scoped_preference,
    )

    # Program 1 from brief:
    # Bounds: [4/5, 9/10] * [3/4, 9/10] * [5/6, 1/1] = [1/2, 81/100]
    # Effort: (1+2-2) + (2+2-2) + (2+3-2) = 1 + 2 + 3 = 6
    units = {
        "unit_1": ActionStep(
            "unit_1",
            1,
            "active",
            t1=1,
            t2=2,
            t3="Low",
            likelihood="High",
            gate_status="Open",
            fact_stratum="AD",
        ),
        "unit_2": ActionStep(
            "unit_2",
            2,
            "active",
            t1=2,
            t2=2,
            t3="Low",
            likelihood="High",
            gate_status="Open",
            fact_stratum="AD",
        ),
        "unit_3": ActionStep(
            "unit_3",
            3,
            "active",
            t1=2,
            t2=3,
            t3="Low",
            likelihood="High",
            gate_status="Open",
            fact_stratum="AD",
        ),
        "unit_b1": ActionStep(
            "unit_b1",
            1,
            "active",
            t1=1,
            t2=2,
            t3="Low",
            likelihood="High",
            gate_status="Open",
            fact_stratum="AD",
        ),
        "unit_b2": ActionStep(
            "unit_b2",
            2,
            "active",
            t1=2,
            t2=2,
            t3="Low",
            likelihood="High",
            gate_status="Open",
            fact_stratum="AD",
        ),
    }
    conditional_bounds = {
        ("unit_1",): (0.8, 0.9),
        ("unit_1", "unit_2"): (0.75, 0.9),
        ("unit_1", "unit_2", "unit_3"): (Fraction(5, 6), 1.0),
        ("unit_b1",): (0.2, 0.4),
        ("unit_b1", "unit_b2"): (0.5, 0.5),
    }

    # Evaluate Program 1
    ass_1 = assess_scoped_program(
        packets=[("unit_1", "unit_2", "unit_3")],
        units=units,
        conditional_bounds=conditional_bounds,
    )
    ass_1["impact"] = "Critical"
    assert ass_1["status"] == "feasible"
    assert ass_1["impact"] == "Critical"
    assert ass_1["likelihood_interval"] == (Fraction(1, 2), Fraction(81, 100))
    assert ass_1["effort"] == 6

    # Evaluate Program 2
    ass_2 = assess_scoped_program(
        packets=[("unit_b1", "unit_b2")],
        units=units,
        conditional_bounds=conditional_bounds,
    )
    ass_2["impact"] = "Critical"
    assert ass_2["status"] == "feasible"
    assert ass_2["impact"] == "Critical"
    assert ass_2["likelihood_interval"] == (Fraction(1, 10), Fraction(1, 5))
    assert ass_2["effort"] == 3

    # Check dominance: P1 dominates P2 because l(P1)=1/2 > u(P2)=1/5 and I(P1)=I(P2)
    pref = scoped_preference(ass_1, ass_2)
    assert pref == "a"


def test_seamless_scenario_wire_query_and_expected_diagnostics():
    """Verify real SEAMLESS structural path query fixture and unrated diagnostics flow."""
    from pathlib import Path

    fixture_dir = Path(__file__).parent / "fixtures" / "ranking"
    query_file = fixture_dir / "seamless_query_input.json"
    expected_file = fixture_dir / "seamless_expected_diagnostics.json"

    assert query_file.exists(), f"Missing fixture file: {query_file}"
    assert expected_file.exists(), f"Missing fixture file: {expected_file}"

    data = json.loads(query_file.read_text(encoding="utf-8"))
    expected = json.loads(expected_file.read_text(encoding="utf-8"))

    query_payload = data["query"]
    candidates = data["candidates"]

    # 1. Decode query wire payload
    decoded = decode_ranking_query(json.dumps(query_payload))
    assert decoded["query_metadata"]["query_id"] == "query-seamless-host-to-dc-v1"
    assert decoded["query_metadata"]["scenario_id"] == "scenario-seamless-host-to-dc"
    assert (
        decoded["query_metadata"]["snapshot_id"]
        == "sha256:e0601d763eeea285d268ec9e468d321c50c9d7faba53c8e7442a2fcc4159c812"
    )

    # 2. Execute full roundtrip
    roundtrip = execute_ranking_roundtrip(json.dumps(query_payload), candidates)
    actual_result = roundtrip["roundtrip_result"]

    # 3. Assert exact match with expected diagnostics fixture
    assert actual_result["query_id"] == expected["query_id"]
    assert actual_result["pareto_frontier"] == []
    assert len(actual_result["diagnostics"]) == 2

    # Verify Candidate 1 diagnostics and structural route
    diag_1 = actual_result["diagnostics"]["cand_seamless_01_direct_lidia"]
    assert set(diag_1["reasons"]) == {"likelihood_unrated", "impact_unrated"}
    cand_1_eval = diag_1["assessment"]
    assert cand_1_eval["status"] == "feasible"
    assert cand_1_eval["structural_routes"][0]["node_ids"] == [
        "S-1-5-21-1271839998-3495686680-2211690266-4131",
        "S-1-5-21-1271839998-3495686680-2211690266-3398",
        "S-1-5-21-1271839998-3495686680-2211690266-512",
        "S-1-5-21-1271839998-3495686680-2211690266-1000",
    ]
    assert cand_1_eval["structural_routes"][0]["edge_ids"] == [
        "sha256:add3ecb3858d5426d003da9ecdba89274ea02d5c7d9e99e3e10ece6a5d077932",
        "sha256:e44b0f47456908b5209f670f2cf0889ae4695e9efd24c82bbda4da1ae043cb48",
        "sha256:57a246b4f71dff94a59b59addcf4e9aa6bd1bdb5d78817c1f733cc2ee197b2b9",
    ]

    # Verify Candidate 2 diagnostics and structural route
    diag_2 = actual_result["diagnostics"]["cand_seamless_02_alt_vajer_ollie"]
    assert set(diag_2["reasons"]) == {"likelihood_unrated", "impact_unrated"}
    cand_2_eval = diag_2["assessment"]
    assert cand_2_eval["status"] == "feasible"
    assert cand_2_eval["structural_routes"][0]["node_ids"] == [
        "S-1-5-21-1271839998-3495686680-2211690266-4131",
        "S-1-5-21-1271839998-3495686680-2211690266-1766",
        "S-1-5-21-1271839998-3495686680-2211690266-3790",
        "S-1-5-21-1271839998-3495686680-2211690266-2014",
        "S-1-5-21-1271839998-3495686680-2211690266-512",
        "S-1-5-21-1271839998-3495686680-2211690266-1000",
    ]
    assert cand_2_eval["structural_routes"][0]["edge_ids"] == [
        "sha256:e6e5d605be1a120753808f94017202855a53fdd9a6b9831ac3421d09fbba1538",
        "sha256:f8b6da6bcbda61ddab0d8184c957e39809ed4e444d5dee181f2309cf0e682173",
        "sha256:3b30de3caac96bad3b7b1980c323661cba1cbeccd3c676d20ce2eb15f4a67689",
        "sha256:250b099e406031037200bdf0d23277cc7d4fe7cc6f6ddad0d310a6be7f904d75",
        "sha256:57a246b4f71dff94a59b59addcf4e9aa6bd1bdb5d78817c1f733cc2ee197b2b9",
    ]

    # Min-Effort-to-DA baseline unrated disclosure
    assert actual_result["min_effort_to_da_baseline"]["best_candidate_id"] is None
    assert actual_result["min_effort_to_da_baseline"]["minimum_effort_value"] is None
    assert actual_result["min_effort_to_da_baseline"]["coverage_disclosure"] == (
        "No feasible rated candidate found in evaluated set."
    )


# ==============================================================================
# Issue #164: Reject boolean/float rubric values at canonical ranking boundary
# ==============================================================================


@pytest.mark.parametrize(
    "field,invalid_val",
    [
        ("t1", True),
        ("t1", False),
        ("t1", 1.0),
        ("t2", True),
        ("t2", False),
        ("t2", 2.0),
        ("computed_cost", True),
        ("computed_cost", False),
        ("computed_cost", 1.0),
        ("effort_cost", True),
        ("effort_cost", 1.0),
    ],
)
def test_issue_164_rubric_scores_rejects_bool_and_float(field, invalid_val):
    """Issue #164: Rubric score and cost fields in rubric_scores must reject bool and float."""
    ledger = {
        "unit_1": {
            "overlap_state": "independent",
            "rating_status": "rated",
            "rubric_scores": {
                "t1": 1,
                "t2": 2,
                "formula": "base",
                "computed_cost": 1,
            },
        }
    }
    ledger["unit_1"]["rubric_scores"][field] = invalid_val
    with pytest.raises(RankingValidationError) as exc:
        canonical_validate_work_units_ledger(ledger)
    assert f"rubric_scores.{field}" in str(exc.value) or "must be an exact integer" in str(
        exc.value
    )


@pytest.mark.parametrize(
    "field,invalid_val",
    [
        ("t1", True),
        ("t1", False),
        ("t1", 1.0),
        ("t2", True),
        ("t2", False),
        ("t2", 2.0),
        ("effort_cost", True),
        ("effort_cost", False),
        ("effort_cost", 1.0),
        ("computed_cost", True),
        ("computed_cost", False),
        ("computed_cost", 1.0),
        ("effort", True),
        ("effort", False),
        ("effort", 1.0),
    ],
)
def test_issue_164_top_level_fields_reject_bool_and_float(field, invalid_val):
    """Issue #164: Top-level rubric scores, costs, and aliases must reject bool and float."""
    ledger = {
        "unit_1": {
            "overlap_state": "independent",
            "rating_status": "rated",
            "t1": 1,
            "t2": 2,
            "formula": "base",
            "effort_cost": 1,
            "computed_cost": 1,
        }
    }
    ledger["unit_1"][field] = invalid_val
    with pytest.raises(RankingValidationError) as exc:
        canonical_validate_work_units_ledger(ledger)
    assert f"{field} must be an exact integer" in str(exc.value)


def test_issue_164_valid_exact_integers_and_zero_cost():
    """Issue #164: Valid exact integers and zero cost (t1=1, t2=1 -> cost=0) are accepted."""
    # 1. Valid positive cost
    ledger_pos = {
        "unit_pos": {
            "overlap_state": "independent",
            "rating_status": "rated",
            "rubric_scores": {
                "t1": 1,
                "t2": 2,
                "formula": "base",
                "computed_cost": 1,
            },
        }
    }
    val_pos = canonical_validate_work_units_ledger(ledger_pos)
    assert val_pos["unit_pos"]["effort_cost"] == 1
    assert val_pos["unit_pos"]["computed_cost"] == 1
    assert val_pos["unit_pos"]["rubric_scores"]["computed_cost"] == 1

    # 2. Valid zero cost
    ledger_zero = {
        "unit_zero": {
            "overlap_state": "independent",
            "rating_status": "rated",
            "rubric_scores": {
                "t1": 1,
                "t2": 1,
                "formula": "base",
                "computed_cost": 0,
            },
        }
    }
    val_zero = canonical_validate_work_units_ledger(ledger_zero)
    assert val_zero["unit_zero"]["effort_cost"] == 0
    assert val_zero["unit_zero"]["computed_cost"] == 0
    assert val_zero["unit_zero"]["rubric_scores"]["computed_cost"] == 0

    # 3. Top-level representation with zero cost
    ledger_top_zero = {
        "unit_top_zero": {
            "overlap_state": "independent",
            "rating_status": "rated",
            "t1": 1,
            "t2": 1,
            "formula": "base",
            "effort_cost": 0,
            "computed_cost": 0,
        }
    }
    val_top_zero = canonical_validate_work_units_ledger(ledger_top_zero)
    assert val_top_zero["unit_top_zero"]["effort_cost"] == 0


def test_issue_164_unrated_rejects_non_null_rubric_fields():
    """Issue #164: Unrated work units must reject non-null rubric score and cost fields."""
    base_unrated = {
        "overlap_state": "independent",
        "rating_status": "unrated",
    }

    # Non-null t1
    bad_t1 = {"u": {**base_unrated, "t1": 1}}
    with pytest.raises(RankingValidationError, match="unrated units must have t1, t2 null"):
        canonical_validate_work_units_ledger(bad_t1)

    # Non-null t2
    bad_t2 = {"u": {**base_unrated, "t2": 2}}
    with pytest.raises(RankingValidationError, match="unrated units must have t1, t2 null"):
        canonical_validate_work_units_ledger(bad_t2)

    # Non-null effort
    bad_effort = {"u": {**base_unrated, "effort": 1}}
    with pytest.raises(RankingValidationError, match="unrated units must have effort_cost null"):
        canonical_validate_work_units_ledger(bad_effort)

    # Non-null effort_cost
    bad_cost = {"u": {**base_unrated, "effort_cost": 0}}
    with pytest.raises(RankingValidationError, match="unrated units must have effort_cost null"):
        canonical_validate_work_units_ledger(bad_cost)


def test_issue_164_cli_fail_closed_on_invalid_rubric_types(tmp_path):
    """Issue #164: CLI fails closed (exit code 2) and writes no output when rubric is bool/float."""
    from src.engine.ranking.cli import run_ranking_cli

    raw_path = Path("tests/fixtures/ranking/seamless_proposed_query_input.json")
    raw = json.loads(raw_path.read_text(encoding="utf-8"))
    first_uid = next(iter(raw["query"]["work_units_ledger"].keys()))

    # Mutate to invalid float
    raw["query"]["work_units_ledger"][first_uid]["rubric_scores"]["t1"] = 1.0

    in_file = tmp_path / "invalid_input.json"
    out_file = tmp_path / "result.json"
    in_file.write_text(json.dumps(raw), encoding="utf-8")

    exit_code = run_ranking_cli(["--input", str(in_file), "--output", str(out_file)])
    assert exit_code == 2
    assert not out_file.exists()

    # Mutate to invalid bool
    raw["query"]["work_units_ledger"][first_uid]["rubric_scores"]["t1"] = True
    in_file.write_text(json.dumps(raw), encoding="utf-8")
    exit_code = run_ranking_cli(["--input", str(in_file), "--output", str(out_file)])
    assert exit_code == 2
    assert not out_file.exists()

    # Valid integer payload succeeds with exit code 0 and produces output
    raw["query"]["work_units_ledger"][first_uid]["rubric_scores"]["t1"] = 1
    in_file.write_text(json.dumps(raw), encoding="utf-8")
    exit_code = run_ranking_cli(["--input", str(in_file), "--output", str(out_file)])
    assert exit_code == 0
    assert out_file.exists()
    out_data = json.loads(out_file.read_text(encoding="utf-8"))
    assert "pareto_frontier" in out_data
