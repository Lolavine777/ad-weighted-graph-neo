"""Automated verification for SEAMLESS parameter proposal and sensitivity analysis.

Tests:
- Proposed query input fixture validity under research wire adapter.
- Exact Fraction calculation traces matching proposal dossier.
- Conservative Pareto preference incomparability due to interval overlap.
- Min-Effort-to-DA separation baseline.
- Roundtrip consistency between proposed input and expected output fixtures.
- Source B proposed query input and roundtrip validation.
- Neighborhood sensitivity analysis (effort friction flip, nested bounds, overlap margin).
- Executed sensitivity sweep flip when Candidate 2 upper bounds are reduced by 10%.
- Wire adapter acceptance of independent overlap state with unrated status and null rubric.
- Behavioral conformance probes (tie-break, impact shift, gating veto/unknown, irrelevant false).
- Safeguarding actual human rating sheets (pending, unrated, null).
- CLI invocation clean subprocess execution.
"""

from __future__ import annotations

import copy
import json
import subprocess
import sys
from fractions import Fraction
from pathlib import Path
from typing import Any

import pytest

from scripts.research.path_ranking_wire_adapter import (
    AUDITED_SEAMLESS_SNAPSHOT_ID,
    SUPPORTED_SOURCE_LAYOUTS,
    SUPPORTED_SOURCE_VERSIONS,
    decode_ranking_query,
    execute_ranking_roundtrip,
    migrate_wire_payload_to_canonical,
    validate_work_units_ledger,
)
from scripts.research.seamless_parameter_validation import (
    EXPECTED_CAND_1_EFFORT,
    EXPECTED_CAND_1_IMPACT,
    EXPECTED_CAND_2_EFFORT,
    EXPECTED_CAND_2_IMPACT,
    compute_bundle_digest,
    derive_query_and_candidates_from_bundle,
    extract_query_and_candidates_from_bundle,
    run_sensitivity_suite,
    verify_calculation_traces,
    verify_parameter_bundle,
)
from src.engine.ranking import PathRankingEngine, RankingValidationError

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures" / "ranking"


def test_proposed_query_input_decodes_cleanly():
    """Verify seamless_proposed_query_input.json validates against wire schema."""
    input_file = FIXTURES / "seamless_proposed_query_input.json"
    assert input_file.exists(), f"Missing fixture {input_file}"
    payload = json.loads(input_file.read_text(encoding="utf-8"))

    decoded_query = decode_ranking_query(json.dumps(payload["query"]))
    assert decoded_query["query_metadata"]["version"] == "1.0.0"
    assert decoded_query["query_metadata"]["scenario_id"] == "scenario-seamless-host-to-dc"
    assert len(payload["candidates"]) == 2

    # Verify work units ledger is fully populated with distinct_work / rated units
    ledger = decoded_query["work_units_ledger"]
    assert len(ledger) == 8
    for _uid, unit in ledger.items():
        assert unit["rating_status"] == "rated"
        assert unit["overlap_state"] in ("distinct_work", "independent")
        assert unit["effort_cost"] in (0, 1, 2)


def test_proposed_calculation_traces_and_pareto_incomparability():
    """Verify exact Fraction likelihoods, costs, and Pareto incomparability."""
    payload = json.loads(
        (FIXTURES / "seamless_proposed_query_input.json").read_text(encoding="utf-8")
    )
    result = execute_ranking_roundtrip(json.dumps(payload["query"]), payload["candidates"])
    traces = verify_calculation_traces(result["roundtrip_result"])

    assert traces["status"] == "PASS"
    assert traces["cand_1"]["effort"] == EXPECTED_CAND_1_EFFORT
    assert traces["cand_1"]["impact"] == EXPECTED_CAND_1_IMPACT
    assert traces["cand_2"]["effort"] == EXPECTED_CAND_2_EFFORT
    assert traces["cand_2"]["impact"] == EXPECTED_CAND_2_IMPACT

    # Pareto frontier must contain both candidates due to interval overlap
    assert set(traces["pareto_frontier"]) == {
        "cand_seamless_01_direct_lidia",
        "cand_seamless_02_alt_vajer_ollie",
    }
    # Min effort must select Cand 1 (effort 2 < 3)
    assert traces["min_effort_to_da"]["best_candidate_id"] == "cand_seamless_01_direct_lidia"
    assert traces["min_effort_to_da"]["minimum_effort_value"] == 2


def test_proposed_source_a_roundtrip_matches_expected_output_fixture():
    """Verify execution of proposed Source A query matches expected output fixture."""
    query_payload = json.loads(
        (FIXTURES / "seamless_proposed_query_input.json").read_text(encoding="utf-8")
    )
    expected_output = json.loads(
        (FIXTURES / "seamless_proposed_expected_output.json").read_text(encoding="utf-8")
    )

    result = execute_ranking_roundtrip(
        json.dumps(query_payload["query"]), query_payload["candidates"]
    )
    actual_rt = result["roundtrip_result"]

    assert actual_rt["pareto_frontier"] == expected_output["pareto_frontier"]
    assert (
        actual_rt["min_effort_to_da_baseline"]["best_candidate_id"]
        == expected_output["min_effort_to_da_baseline"]["best_candidate_id"]
    )
    assert (
        actual_rt["min_effort_to_da_baseline"]["minimum_effort_value"]
        == expected_output["min_effort_to_da_baseline"]["minimum_effort_value"]
    )
    assert actual_rt["diagnostics"] == expected_output["diagnostics"]


def test_proposed_source_b_roundtrip_matches_expected_output_fixture():
    """Verify execution of proposed Source B query matches expected output fixture."""
    query_payload = json.loads(
        (FIXTURES / "seamless_source_b_proposed_query_input.json").read_text(encoding="utf-8")
    )
    expected_output = json.loads(
        (FIXTURES / "seamless_source_b_proposed_expected_output.json").read_text(encoding="utf-8")
    )

    result = execute_ranking_roundtrip(
        json.dumps(query_payload["query"]), query_payload["candidates"]
    )
    actual_rt = result["roundtrip_result"]

    assert actual_rt["pareto_frontier"] == expected_output["pareto_frontier"]
    assert actual_rt["diagnostics"] == expected_output["diagnostics"]
    cand_b = actual_rt["eligible_candidates"]["cand_seamless_source_b_01_ollie"]
    assert cand_b["effort"] == 2
    assert cand_b["impact"] == "High"
    assert cand_b["likelihood_interval"] == ["42/125", "171/250"]


def test_sensitivity_suite_execution():
    """Verify all sensitivity scenarios execute and pass invariants."""
    payload = json.loads(
        (FIXTURES / "seamless_proposed_query_input.json").read_text(encoding="utf-8")
    )
    report = run_sensitivity_suite(payload)

    assert "neighborhood_sensitivity" in report
    assert "conformance_probes" in report

    for s_name, s_data in report["neighborhood_sensitivity"].items():
        assert s_data["status"] == "PASS", f"Neighborhood scenario {s_name} failed"

    for p_name, p_data in report["conformance_probes"].items():
        assert p_data["status"] == "PASS", f"Conformance probe {p_name} failed"


def test_sensitivity_friction_effort_increase_flips_min_effort():
    """Neighborhood Probe: Increasing friction T2 on Lidia flips Min-Effort to Cand 2."""
    payload = json.loads(
        (FIXTURES / "seamless_proposed_query_input.json").read_text(encoding="utf-8")
    )
    ledger = payload["query"]["work_units_ledger"]
    for u, rec in ledger.items():
        if ("reset_password" in u or "remote_exec_winrm" in u) and "3398" in u:
            rec["rubric_scores"]["t2"] = 3
            rec["rubric_scores"]["computed_cost"] = rec["rubric_scores"]["t1"] + 3 - 2
            rec["t2"] = 3
            rec["effort_cost"] = rec["rubric_scores"]["computed_cost"]
            rec["computed_cost"] = rec["rubric_scores"]["computed_cost"]

    result = execute_ranking_roundtrip(json.dumps(payload["query"]), payload["candidates"])
    rt = result["roundtrip_result"]

    # Candidate 1 effort jumps from 2 to 4, Candidate 2 stays 3
    assert rt["eligible_candidates"]["cand_seamless_01_direct_lidia"]["effort"] == 4
    assert rt["eligible_candidates"]["cand_seamless_02_alt_vajer_ollie"]["effort"] == 3
    # Min-Effort flips winner to Candidate 2
    assert (
        rt["min_effort_to_da_baseline"]["best_candidate_id"] == "cand_seamless_02_alt_vajer_ollie"
    )
    assert rt["min_effort_to_da_baseline"]["minimum_effort_value"] == 3
    # Pareto frontier still retains both candidates
    assert set(rt["pareto_frontier"]) == {
        "cand_seamless_01_direct_lidia",
        "cand_seamless_02_alt_vajer_ollie",
    }


def test_sensitivity_strictly_nested_bounds_narrowing():
    """Neighborhood Probe: Strictly nested bounds narrowing induces strict Pareto dominance."""
    payload = json.loads(
        (FIXTURES / "seamless_proposed_query_input.json").read_text(encoding="utf-8")
    )
    for row in payload["query"]["conditional_bounds_table"]:
        if len(row["prefix"]) == 1 and "3398" in row["prefix"][0]:
            row["lower"] = "17/20"
            row["upper"] = "9/10"
        elif len(row["prefix"]) == 2 and "3398" in row["prefix"][1]:
            row["lower"] = "9/10"
            row["upper"] = "19/20"
        elif len(row["prefix"]) == 3 and "3398" in row["prefix"][2]:
            row["lower"] = "3/4"
            row["upper"] = "4/5"

    result = execute_ranking_roundtrip(json.dumps(payload["query"]), payload["candidates"])
    rt = result["roundtrip_result"]
    assert rt["pareto_frontier"] == ["cand_seamless_01_direct_lidia"]
    assert "cand_seamless_02_alt_vajer_ollie" not in rt["pareto_frontier"]
    c1 = rt["eligible_candidates"]["cand_seamless_01_direct_lidia"]
    assert Fraction(c1["likelihood_interval"][0]) == Fraction(459, 800)
    assert Fraction(c1["likelihood_interval"][0]) > Fraction(55233, 100000)


def test_sensitivity_point_likelihood_tie_break():
    """Conformance Probe: Exact point likelihood equality triggers effort tie-break."""
    payload = json.loads(
        (FIXTURES / "seamless_proposed_query_input.json").read_text(encoding="utf-8")
    )
    for row in payload["query"]["conditional_bounds_table"]:
        if len(row["prefix"]) == 1:
            row["lower"] = "3/10"
            row["upper"] = "3/10"
        else:
            row["lower"] = "1"
            row["upper"] = "1"

    result = execute_ranking_roundtrip(json.dumps(payload["query"]), payload["candidates"])
    rt = result["roundtrip_result"]
    assert rt["pareto_frontier"] == ["cand_seamless_01_direct_lidia"]


def test_sensitivity_irrelevant_predicate_false_noop():
    """Conformance Probe: Irrelevant false fact does NOT block candidates or mutate frontier."""
    payload = json.loads(
        (FIXTURES / "seamless_proposed_query_input.json").read_text(encoding="utf-8")
    )
    payload["query"]["facts_ledger"]["false_facts"].append(
        {
            "predicate": "synthetic_unrelated_service_reachable",
            "truth_value": False,
            "layer": 3,
            "provenance_reference": "sensitivity:synthetic_irrelevant_false",
        }
    )

    result = execute_ranking_roundtrip(json.dumps(payload["query"]), payload["candidates"])
    rt = result["roundtrip_result"]
    assert set(rt["pareto_frontier"]) == {
        "cand_seamless_01_direct_lidia",
        "cand_seamless_02_alt_vajer_ollie",
    }
    assert len(rt["diagnostics"]) == 0


def test_sensitivity_known_false_veto():
    """Conformance Probe: Required known-false predicate vetoes candidate to diagnostics."""
    payload = json.loads(
        (FIXTURES / "seamless_proposed_query_input.json").read_text(encoding="utf-8")
    )
    payload["query"]["facts_ledger"]["false_facts"].append(
        {
            "predicate": "endpoint_authorized_lidia",
            "truth_value": False,
            "layer": 3,
            "provenance_reference": "sensitivity:synthetic_jea_restriction",
        }
    )

    result = execute_ranking_roundtrip(json.dumps(payload["query"]), payload["candidates"])
    rt = result["roundtrip_result"]
    assert "cand_seamless_01_direct_lidia" in rt["diagnostics"]
    assert rt["diagnostics"]["cand_seamless_01_direct_lidia"]["assessment"]["status"] == "blocked"
    assert rt["pareto_frontier"] == ["cand_seamless_02_alt_vajer_ollie"]


def test_sensitivity_missing_evidence_unknown():
    """Conformance Probe: Missing required predicate marks candidate as unknown in diagnostics."""
    payload = json.loads(
        (FIXTURES / "seamless_proposed_query_input.json").read_text(encoding="utf-8")
    )
    payload["query"]["facts_ledger"]["assumed_facts"] = [
        f
        for f in payload["query"]["facts_ledger"]["assumed_facts"]
        if f["predicate"] != "winrm_authentication_accepted_lidia"
    ]

    result = execute_ranking_roundtrip(json.dumps(payload["query"]), payload["candidates"])
    rt = result["roundtrip_result"]
    assert "cand_seamless_01_direct_lidia" in rt["diagnostics"]
    assert rt["diagnostics"]["cand_seamless_01_direct_lidia"]["assessment"]["status"] == "unknown"
    assert rt["pareto_frontier"] == ["cand_seamless_02_alt_vajer_ollie"]


def test_actual_human_sheets_remain_untouched_and_pending():
    """Governance safeguard: verify human rating sheets have null raters and null scores."""
    for sname in ["seamless_rater_1.json", "seamless_rater_2.json"]:
        sheet = json.loads((FIXTURES / sname).read_text(encoding="utf-8"))
        assert sheet["status"] == "pending_independent_rating"
        assert sheet["rater"]["evaluator"] is None
        assert sheet["rater"]["name"] is None
        assert sheet["rater"]["signature"] is None

        # Verify impact ratings unrated
        for rec in sheet["impact_ratings"]:
            assert rec["consequence_rating"] is None
            assert rec["rating_status"] == "unrated"

        # Verify likelihood ratings unrated
        for rec in sheet["likelihood_ratings"]:
            assert rec["conditional_bounds"]["lower"] is None
            assert rec["conditional_bounds"]["upper"] is None
            assert rec["rating_status"] == "unrated"

        # Verify effort ratings unrated
        for rec in sheet["effort_ratings"]:
            assert rec["rubric_evaluation"]["t1_complexity"] is None
            assert rec["rubric_evaluation"]["t2_friction"] is None
            assert rec["rubric_evaluation"]["computed_cost"] is None
            assert rec["rating_status"] == "unrated"


def test_validation_script_cli_runs_cleanly(tmp_path):
    """Verify validation CLI script executes cleanly via subprocess from clean environment."""
    out_file = tmp_path / "test_report.json"
    cmd = [
        sys.executable,
        "scripts/research/seamless_parameter_validation.py",
        "--input",
        str(FIXTURES / "seamless_proposed_query_input.json"),
        "--output",
        str(out_file),
    ]
    proc = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True, check=True)
    assert proc.returncode == 0
    assert "SEAMLESS PARAMETER PROPOSAL VALIDATION" in proc.stdout
    assert out_file.exists()
    report = json.loads(out_file.read_text(encoding="utf-8"))
    assert report["calculation_traces"]["status"] == "PASS"
    assert report["input_file"] == "tests/fixtures/ranking/seamless_proposed_query_input.json"


def test_sensitivity_executed_sweep_cand2_upper_minus_10pct_flips_frontier():
    """Neighborhood Probe: Cand 2 upper -10% drops u2 < l1 and collapses frontier."""
    payload = json.loads(
        (FIXTURES / "seamless_proposed_query_input.json").read_text(encoding="utf-8")
    )
    for row in payload["query"]["conditional_bounds_table"]:
        if "3398" not in str(row["prefix"]):
            if len(row["prefix"]) == 1:
                row["lower"] = "3/4"
                row["upper"] = "81/100"
            elif len(row["prefix"]) == 2:
                row["lower"] = "4/5"
                row["upper"] = "171/200"
            elif len(row["prefix"]) == 3:
                row["lower"] = "7/10"
                row["upper"] = "153/200"
            elif len(row["prefix"]) == 4:
                row["lower"] = "4/5"
                row["upper"] = "171/200"
            elif len(row["prefix"]) == 5:
                row["lower"] = "3/5"
                row["upper"] = "18/25"

    result = execute_ranking_roundtrip(json.dumps(payload["query"]), payload["candidates"])
    rt = result["roundtrip_result"]

    assert rt["pareto_frontier"] == ["cand_seamless_01_direct_lidia"]
    c1 = rt["eligible_candidates"]["cand_seamless_01_direct_lidia"]
    c2 = rt["eligible_candidates"]["cand_seamless_02_alt_vajer_ollie"]
    assert c1["likelihood_interval"] == ["42/125", "171/250"]
    assert c2["likelihood_interval"] == ["126/625", "3261453417/10000000000"]
    assert Fraction(c2["likelihood_interval"][1]) < Fraction(c1["likelihood_interval"][0])


def test_wire_adapter_accepts_independent_overlap_with_unrated_status():
    """Verify wire adapter allows independent overlap with unrated status and null rubric."""
    ledger = {
        "work_unit_withholding": {
            "work_unit_id": "work_unit_withholding",
            "overlap_state": "independent",
            "rating_status": "unrated",
            "rubric_scores": None,
            "computed_cost": None,
            "effort_cost": None,
        },
        "work_unit_alias_unrated": {
            "work_unit_id": "work_unit_alias_unrated",
            "overlap_state": "distinct_work",
            "rating_status": "unrated",
            "rubric_scores": None,
            "computed_cost": None,
            "effort_cost": None,
        },
    }
    validated = validate_work_units_ledger(ledger)
    assert len(validated) == 2
    for _uid, unit in validated.items():
        assert unit["rating_status"] == "unrated"
        assert unit["rubric_scores"] is None
        assert unit["effort_cost"] is None
        assert unit["computed_cost"] is None
        assert unit["overlap_state"] in ("independent", "distinct_work")


def test_canonical_migration_function_transforms_legacy_payload():
    """Verify versioned migration adapter maps legacy aliases to canonical 1.0.0 boundary."""
    from src.engine.ranking import PathRankingEngine

    # Synthesize legacy payload: distinct_work, missing technique_name, missing scope_binding
    snap_id = "sha256:e0601d763eeea285d268ec9e468d321c50c9d7faba53c8e7442a2fcc4159c812"
    u1 = (
        "reset_password:S-1-5-21-1271839998-3495686680-2211690266-4131:"
        "S-1-5-21-1271839998-3495686680-2211690266-3398:default:intra_forest:1.0.0"
    )
    u2 = (
        "acquire_ticket:S-1-5-21-1271839998-3495686680-2211690266-3398:"
        "S-1-5-21-1271839998-3495686680-2211690266-1000:default:intra_forest:1.0.0"
    )
    u3 = (
        "remote_exec_winrm:S-1-5-21-1271839998-3495686680-2211690266-3398:"
        "S-1-5-21-1271839998-3495686680-2211690266-1000:default:intra_forest:1.0.0"
    )
    legacy_payload = {
        "query": {
            "query_metadata": {
                "query_id": "query-seamless-host-to-dc-v1",
                "version": "legacy_draft",
                "scenario_id": "scenario-seamless-host-to-dc",
                "scenario_version": "1.1.0",
                "snapshot_id": snap_id,
                "evaluation_mode": "scenario",
                "work_boundary": "intra_forest",
                "foothold_node_id": "S-1-5-21-1271839998-3495686680-2211690266-4131",
                "target_goal": {
                    "goal_id": "terminal_compromise_seamless_dc",
                    "target_asset_id": "S-1-5-21-1271839998-3495686680-2211690266-1000",
                    "success_event": "terminal_compromise_seamless_dc",
                    "required_predicates": ["admin_control_badblood"],
                },
                "horizon": "24h",
                "active_work_budget": 6,
            },
            "facts_ledger": {
                "observed_facts": [
                    {
                        "predicate": "enabled_tstwvir",
                        "truth_value": True,
                        "layer": 2,
                        "provenance_reference": (
                            "20210920185958_computers.json#/computers/46/Properties/enabled"
                        ),
                    },
                    {
                        "predicate": "enabled_lidia",
                        "truth_value": True,
                        "layer": 2,
                        "provenance_reference": (
                            "20210920185958_users.json#/users/2310/Properties/enabled"
                        ),
                    },
                    {
                        "predicate": "genericall_tstwvir_lidia",
                        "truth_value": True,
                        "layer": 1,
                        "provenance_reference": "20210920185958_users.json#/users/2310/Aces/3",
                    },
                    {
                        "predicate": "memberof_lidia_da",
                        "truth_value": True,
                        "layer": 1,
                        "provenance_reference": "20210920185958_groups.json#/groups/40/Members/0",
                    },
                    {
                        "predicate": "genericall_da_badblood",
                        "truth_value": True,
                        "layer": 1,
                        "provenance_reference": "20210920185958_computers.json#/computers/0/Aces/1",
                    },
                    {
                        "predicate": "enabled_badblood",
                        "truth_value": True,
                        "layer": 2,
                        "provenance_reference": (
                            "20210920185958_computers.json#/computers/0/Properties/enabled"
                        ),
                    },
                ],
                "false_facts": [],
                "assumed_facts": [
                    {
                        "predicate": "foothold_controlled_tstwvir",
                        "truth_value": True,
                        "layer": 3,
                        "rationale": "Source A LocalSystem foothold",
                    },
                    {
                        "predicate": "network_rpc_reachable",
                        "truth_value": True,
                        "layer": 3,
                        "rationale": "Directory channel reachable",
                    },
                    {
                        "predicate": "network_kdc_reachable",
                        "truth_value": True,
                        "layer": 3,
                        "rationale": "KDC reachable",
                    },
                    {
                        "predicate": "network_winrm_reachable",
                        "truth_value": True,
                        "layer": 3,
                        "rationale": "WinRM transport reachable",
                    },
                    {
                        "predicate": "service_winrm_running",
                        "truth_value": True,
                        "layer": 3,
                        "rationale": "WinRM running",
                    },
                    {
                        "predicate": "da_host_admin_mapping",
                        "truth_value": True,
                        "layer": 3,
                        "rationale": "DA host admin mapping",
                    },
                    {
                        "predicate": "password_policy_accepts_lidia",
                        "truth_value": True,
                        "layer": 3,
                        "rationale": "Password policy accepts lidia",
                    },
                    {
                        "predicate": "directory_write_allowed_lidia",
                        "truth_value": True,
                        "layer": 3,
                        "rationale": "Directory write allowed lidia",
                    },
                    {
                        "predicate": "authentication_accepted_lidia",
                        "truth_value": True,
                        "layer": 3,
                        "rationale": "Authentication accepted lidia",
                    },
                    {
                        "predicate": "membership_security_group_usable_lidia_da",
                        "truth_value": True,
                        "layer": 3,
                        "rationale": "Membership usable",
                    },
                    {
                        "predicate": "winrm_authentication_accepted_lidia",
                        "truth_value": True,
                        "layer": 3,
                        "rationale": "WinRM auth accepted",
                    },
                    {
                        "predicate": "endpoint_authorized_lidia",
                        "truth_value": True,
                        "layer": 3,
                        "rationale": "Endpoint authorized",
                    },
                    {
                        "predicate": "admin_execution_context_lidia",
                        "truth_value": True,
                        "layer": 3,
                        "rationale": "Admin context",
                    },
                ],
                "unknown_facts": [],
                "predicate_layers": {
                    "credentials_lidia": 3,
                    "actor_controlled_lidia": 3,
                    "effective_member_da_lidia": 3,
                    "admin_control_badblood": 3,
                    "enabled_tstwvir": 2,
                    "enabled_lidia": 2,
                    "enabled_badblood": 2,
                    "genericall_tstwvir_lidia": 1,
                    "memberof_lidia_da": 1,
                    "genericall_da_badblood": 1,
                    "foothold_controlled_tstwvir": 3,
                    "network_rpc_reachable": 3,
                    "network_kdc_reachable": 3,
                    "network_winrm_reachable": 3,
                    "service_winrm_running": 3,
                    "da_host_admin_mapping": 3,
                    "password_policy_accepts_lidia": 3,
                    "directory_write_allowed_lidia": 3,
                    "authentication_accepted_lidia": 3,
                    "membership_security_group_usable_lidia_da": 3,
                    "winrm_authentication_accepted_lidia": 3,
                    "endpoint_authorized_lidia": 3,
                    "admin_execution_context_lidia": 3,
                },
            },
            "bound_actions": [
                {
                    "action_id": "action_reset_lidia",
                    "technique": "reset_password",
                    "actor_id": "S-1-5-21-1271839998-3495686680-2211690266-4131",
                    "target_id": "S-1-5-21-1271839998-3495686680-2211690266-3398",
                    "bound_work_units": [
                        "reset_password:S-1-5-21-1271839998-3495686680-2211690266-4131:S-1-5-21-1271839998-3495686680-2211690266-3398:default:intra_forest:1.0.0"
                    ],
                    "requires": [
                        "enabled_tstwvir",
                        "enabled_lidia",
                        "genericall_tstwvir_lidia",
                        "network_rpc_reachable",
                        "password_policy_accepts_lidia",
                        "directory_write_allowed_lidia",
                        "foothold_controlled_tstwvir",
                    ],
                    "adds": ["credentials_lidia"],
                    "is_passive_closure": False,
                },
                {
                    "action_id": "action_activate_lidia",
                    "technique": "acquire_ticket",
                    "actor_id": "S-1-5-21-1271839998-3495686680-2211690266-3398",
                    "target_id": "S-1-5-21-1271839998-3495686680-2211690266-1000",
                    "bound_work_units": [
                        "acquire_ticket:S-1-5-21-1271839998-3495686680-2211690266-3398:S-1-5-21-1271839998-3495686680-2211690266-1000:default:intra_forest:1.0.0"
                    ],
                    "requires": [
                        "credentials_lidia",
                        "enabled_lidia",
                        "network_kdc_reachable",
                        "authentication_accepted_lidia",
                    ],
                    "adds": ["actor_controlled_lidia"],
                    "is_passive_closure": False,
                },
                {
                    "action_id": "action_closure_lidia_da",
                    "technique": "membership_closure",
                    "actor_id": "S-1-5-21-1271839998-3495686680-2211690266-3398",
                    "target_id": "S-1-5-21-1271839998-3495686680-2211690266-512",
                    "requires": [
                        "actor_controlled_lidia",
                        "memberof_lidia_da",
                        "enabled_lidia",
                        "membership_security_group_usable_lidia_da",
                    ],
                    "adds": ["effective_member_da_lidia"],
                    "is_passive_closure": True,
                },
                {
                    "action_id": "action_winrm_badblood_lidia",
                    "technique": "remote_exec_winrm",
                    "actor_id": "S-1-5-21-1271839998-3495686680-2211690266-3398",
                    "target_id": "S-1-5-21-1271839998-3495686680-2211690266-1000",
                    "bound_work_units": [
                        "remote_exec_winrm:S-1-5-21-1271839998-3495686680-2211690266-3398:S-1-5-21-1271839998-3495686680-2211690266-1000:default:intra_forest:1.0.0"
                    ],
                    "requires": [
                        "effective_member_da_lidia",
                        "network_winrm_reachable",
                        "service_winrm_running",
                        "enabled_badblood",
                        "actor_controlled_lidia",
                        "enabled_lidia",
                        "da_host_admin_mapping",
                        "winrm_authentication_accepted_lidia",
                        "endpoint_authorized_lidia",
                        "admin_execution_context_lidia",
                    ],
                    "adds": ["admin_control_badblood"],
                    "is_passive_closure": False,
                },
            ],
            "work_units_ledger": {
                u1: {
                    "overlap_state": "distinct_work",
                    "status": "rated",
                    "rubric_scores": {
                        "t1": 1,
                        "t2": 2,
                    },
                },
                u2: {
                    "overlap_state": "distinct_work",
                    "status": "rated",
                    "rubric_scores": {
                        "t1": 1,
                        "t2": 1,
                    },
                },
                u3: {
                    "overlap_state": "distinct_work",
                    "status": "rated",
                    "rubric_scores": {
                        "t1": 1,
                        "t2": 2,
                    },
                },
            },
            "conditional_bounds_table": [
                {
                    "prefix": [u1],
                    "lower": "7/10",
                    "upper": "9/10",
                },
                {
                    "prefix": [u1, u2],
                    "lower": "4/5",
                    "upper": "19/20",
                },
                {
                    "prefix": [u1, u2, u3],
                    "lower": "3/5",
                    "upper": "4/5",
                },
            ],
            "target_impact_assessments": {
                "S-1-5-21-1271839998-3495686680-2211690266-1000": {
                    "target_asset_id": "S-1-5-21-1271839998-3495686680-2211690266-1000",
                    "success_event": "terminal_compromise_seamless_dc",
                    "rating_status": "rated",
                    "consequence_rating": "High",
                }
            },
        },
        "candidates": [
            {
                "candidate_id": "cand_seamless_01_direct_lidia",
                "target_asset_id": "S-1-5-21-1271839998-3495686680-2211690266-1000",
                "bound_action_ids": [
                    "action_reset_lidia",
                    "action_activate_lidia",
                    "action_closure_lidia_da",
                    "action_winrm_badblood_lidia",
                ],
                "structural_routes": [
                    {
                        "route_id": "route_seamless_01",
                        "node_ids": [
                            "S-1-5-21-1271839998-3495686680-2211690266-4131",
                            "S-1-5-21-1271839998-3495686680-2211690266-3398",
                            "S-1-5-21-1271839998-3495686680-2211690266-512",
                            "S-1-5-21-1271839998-3495686680-2211690266-1000",
                        ],
                        "edge_ids": [
                            "sha256:add3ecb3858d5426d003da9ecdba89274ea02d5c7d9e99e3e10ece6a5d077932",
                            "sha256:e44b0f47456908b5209f670f2cf0889ae4695e9efd24c82bbda4da1ae043cb48",
                            "sha256:57a246b4f71dff94a59b59addcf4e9aa6bd1bdb5d78817c1f733cc2ee197b2b9",
                        ],
                    }
                ],
            }
        ],
    }

    # Run migration
    canonical = migrate_wire_payload_to_canonical(legacy_payload)

    # 1. Assert version is normalized
    assert canonical["query"]["query_metadata"]["version"] == "1.0.0"

    # 2. Assert work_units_ledger overlap_state is migrated from distinct_work to independent
    for _uid, rec in canonical["query"]["work_units_ledger"].items():
        assert rec["overlap_state"] == "independent"
        assert rec["rating_status"] == "rated"
        assert rec["effort_cost"] in (0, 1)

    # 3. Assert bound_actions has technique_name and referenced_work_unit_ids
    for act in canonical["query"]["bound_actions"]:
        assert "technique_name" in act
        assert "referenced_work_unit_ids" in act
        if act["is_passive_closure"]:
            assert act["referenced_work_unit_ids"] == []

    # 4. Assert candidates have scope_binding and provenance_locators
    cand = canonical["candidates"][0]
    assert "scope_binding" in cand
    assert cand["scope_binding"]["query_id"] == "query-seamless-host-to-dc-v1"
    assert (
        cand["scope_binding"]["snapshot_id"]
        == legacy_payload["query"]["query_metadata"]["snapshot_id"]
    )

    route = cand["structural_routes"][0]
    assert "provenance_locators" in route
    assert len(route["provenance_locators"]) == 3
    assert route["provenance_locators"][0] == "20210920185958_users.json#/users/2310/Aces/3"

    # 5. Evaluate migrated payload on canonical engine API B
    engine = PathRankingEngine(version="1.0.0")
    res = engine.evaluate(query_payload=canonical["query"], candidates=canonical["candidates"])
    assert res["result_payload"]["pareto_frontier"] == ["cand_seamless_01_direct_lidia"]
    assert res["result_payload"]["min_effort_to_da_baseline"]["minimum_effort_value"] == 2


def test_canonical_engine_cli_evaluates_proposed_fixtures_cleanly(tmp_path):
    """Verify canonical engine CLI processes Source A and B proposed fixtures with exit 0."""
    out_a = tmp_path / "seamless_a_cli_output.json"
    cmd_a = [
        sys.executable,
        "-m",
        "src.engine.ranking.cli",
        "--input",
        str(FIXTURES / "seamless_proposed_query_input.json"),
        "--output",
        str(out_a),
    ]
    proc_a = subprocess.run(cmd_a, cwd=str(ROOT), capture_output=True, text=True, check=False)
    assert proc_a.returncode == 0, f"CLI Source A failed: {proc_a.stderr}"

    actual_a = json.loads(out_a.read_text(encoding="utf-8"))
    expected_a = json.loads(
        (FIXTURES / "seamless_proposed_expected_output.json").read_text(encoding="utf-8")
    )
    assert actual_a["pareto_frontier"] == expected_a["pareto_frontier"]
    assert actual_a["pareto_frontier"] == [
        "cand_seamless_01_direct_lidia",
        "cand_seamless_02_alt_vajer_ollie",
    ]
    assert "parameter_audit" in actual_a
    assert set(actual_a["parameter_audit"].keys()) == {
        "query_metadata",
        "work_units_ledger",
        "conditional_bounds_table",
        "target_impact_assessments",
    }
    for cand in actual_a["eligible_candidates"].values():
        assert "work_unit_basis" in cand
        assert "conditional_bounds_basis" in cand
        assert "diagnostic_reasons" in cand

    assert (
        actual_a["min_effort_to_da_baseline"]["best_candidate_id"]
        == expected_a["min_effort_to_da_baseline"]["best_candidate_id"]
    )
    assert (
        actual_a["min_effort_to_da_baseline"]["minimum_effort_value"]
        == expected_a["min_effort_to_da_baseline"]["minimum_effort_value"]
    )

    out_b = tmp_path / "seamless_b_cli_output.json"
    cmd_b = [
        sys.executable,
        "-m",
        "src.engine.ranking.cli",
        "--input",
        str(FIXTURES / "seamless_source_b_proposed_query_input.json"),
        "--output",
        str(out_b),
    ]
    proc_b = subprocess.run(cmd_b, cwd=str(ROOT), capture_output=True, text=True, check=False)
    assert proc_b.returncode == 0, f"CLI Source B failed: {proc_b.stderr}"

    actual_b = json.loads(out_b.read_text(encoding="utf-8"))
    expected_b = json.loads(
        (FIXTURES / "seamless_source_b_proposed_expected_output.json").read_text(encoding="utf-8")
    )
    assert actual_b["pareto_frontier"] == expected_b["pareto_frontier"]
    assert actual_b["pareto_frontier"] == ["cand_seamless_source_b_01_ollie"]
    assert "parameter_audit" in actual_b
    for cand in actual_b["eligible_candidates"].values():
        assert "work_unit_basis" in cand
        assert "conditional_bounds_basis" in cand
        assert "diagnostic_reasons" in cand

    assert (
        actual_b["min_effort_to_da_baseline"]["best_candidate_id"]
        == expected_b["min_effort_to_da_baseline"]["best_candidate_id"]
    )


def test_canonical_engine_cli_fails_closed_on_legacy_or_malformed_inputs(tmp_path):
    """Verify canonical engine CLI strictly fails closed (exit code 2) on unmigrated inputs."""
    # 1. Test unmigrated distinct_work overlap_state
    malformed_1 = json.loads(
        (FIXTURES / "seamless_proposed_query_input.json").read_text(encoding="utf-8")
    )
    first_unit = next(iter(malformed_1["query"]["work_units_ledger"].values()))
    first_unit["overlap_state"] = "distinct_work"
    bad_file_1 = tmp_path / "bad_overlap.json"
    bad_file_1.write_text(json.dumps(malformed_1), encoding="utf-8")

    proc_1 = subprocess.run(
        [sys.executable, "-m", "src.engine.ranking.cli", "--input", str(bad_file_1)],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc_1.returncode == 2
    assert "invalid overlap_state: 'distinct_work'" in proc_1.stderr

    # 2. Test candidate missing scope_binding
    malformed_2 = json.loads(
        (FIXTURES / "seamless_proposed_query_input.json").read_text(encoding="utf-8")
    )
    del malformed_2["candidates"][0]["scope_binding"]
    bad_file_2 = tmp_path / "missing_scope.json"
    bad_file_2.write_text(json.dumps(malformed_2), encoding="utf-8")

    proc_2 = subprocess.run(
        [sys.executable, "-m", "src.engine.ranking.cli", "--input", str(bad_file_2)],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc_2.returncode == 2
    assert "scope_binding" in proc_2.stderr

    # 3. Test bound_action missing technique_name
    malformed_3 = json.loads(
        (FIXTURES / "seamless_proposed_query_input.json").read_text(encoding="utf-8")
    )
    del malformed_3["query"]["bound_actions"][0]["technique_name"]
    bad_file_3 = tmp_path / "missing_technique.json"
    bad_file_3.write_text(json.dumps(malformed_3), encoding="utf-8")

    proc_3 = subprocess.run(
        [sys.executable, "-m", "src.engine.ranking.cli", "--input", str(bad_file_3)],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc_3.returncode == 2
    assert "technique_name" in proc_3.stderr


def test_migration_cost_mismatch_and_contradictory_aliases_fail_closed():
    """Verify migrate_wire_payload_to_canonical strictly rejects cost contradictions fail-closed."""
    raw = json.loads((FIXTURES / "seamless_proposed_query_input.json").read_text(encoding="utf-8"))
    first_uid = next(iter(raw["query"]["work_units_ledger"].keys()))

    # Case a: Within-scale cost mismatch (declared effort_cost=3 vs rubric t1=1, t2=2 -> cost=1)
    p_within = json.loads(json.dumps(raw))
    p_within["query"]["work_units_ledger"][first_uid]["effort_cost"] = 3
    p_within["query"]["work_units_ledger"][first_uid]["computed_cost"] = 3
    p_within["query"]["work_units_ledger"][first_uid]["rubric_scores"]["computed_cost"] = 3
    with pytest.raises(ValueError, match="Cost mismatch in work unit"):
        migrate_wire_payload_to_canonical(p_within)

    # Case b: Out-of-scale cost mismatch (declared effort_cost=999)
    p_out = json.loads(json.dumps(raw))
    p_out["query"]["work_units_ledger"][first_uid]["effort_cost"] = 999
    p_out["query"]["work_units_ledger"][first_uid]["computed_cost"] = 999
    p_out["query"]["work_units_ledger"][first_uid]["rubric_scores"]["computed_cost"] = 999
    with pytest.raises(ValueError, match="Cost mismatch in work unit"):
        migrate_wire_payload_to_canonical(p_out)

    # Case c: Contradictory cost aliases (effort_cost=1 != computed_cost=2)
    p_alias = json.loads(json.dumps(raw))
    p_alias["query"]["work_units_ledger"][first_uid]["effort_cost"] = 1
    p_alias["query"]["work_units_ledger"][first_uid]["computed_cost"] = 2
    with pytest.raises(ValueError, match="Contradictory cost aliases"):
        migrate_wire_payload_to_canonical(p_alias)

    # Case d: Contradictory rubric computed_cost
    p_rubric = json.loads(json.dumps(raw))
    p_rubric["query"]["work_units_ledger"][first_uid]["rubric_scores"]["computed_cost"] = 2
    p_rubric["query"]["work_units_ledger"][first_uid]["effort_cost"] = 1
    with pytest.raises(ValueError, match="Contradictory rubric computed_cost"):
        migrate_wire_payload_to_canonical(p_rubric)

    # Case e: Valid cost absent/None -> cleanly derived and evaluated by canonical engine
    p_valid = json.loads(json.dumps(raw))
    del p_valid["query"]["work_units_ledger"][first_uid]["effort_cost"]
    del p_valid["query"]["work_units_ledger"][first_uid]["computed_cost"]
    del p_valid["query"]["work_units_ledger"][first_uid]["rubric_scores"]["computed_cost"]
    migrated = migrate_wire_payload_to_canonical(p_valid)
    rec = migrated["query"]["work_units_ledger"][first_uid]
    assert rec["effort_cost"] == 1
    assert rec["computed_cost"] == 1
    assert rec["rubric_scores"]["computed_cost"] == 1

    engine = PathRankingEngine(version="1.0.0")
    res = engine.evaluate(migrated["query"], migrated["candidates"])
    assert res["roundtrip_result"]["pareto_frontier"] == [
        "cand_seamless_01_direct_lidia",
        "cand_seamless_02_alt_vajer_ollie",
    ]


def test_migration_invalid_types_and_conflicting_aliases_fail_closed():
    """Verify migration rejects non-string techniques, non-dict/list envelopes, and conflicts."""
    raw = json.loads((FIXTURES / "seamless_proposed_query_input.json").read_text(encoding="utf-8"))

    # 1. Invalid technique_name type (int)
    p_tech_int = json.loads(json.dumps(raw))
    p_tech_int["query"]["bound_actions"][0]["technique_name"] = 123
    with pytest.raises(TypeError, match="technique_name must be non-empty string"):
        migrate_wire_payload_to_canonical(p_tech_int)

    # 2. Technique alias behavior:
    # 2a. Invalid technique alias type (int) raises TypeError
    p_tech_alias_int = json.loads(json.dumps(raw))
    p_tech_alias_int["query"]["bound_actions"][0]["technique"] = 123
    with pytest.raises(TypeError, match="technique must be non-empty string"):
        migrate_wire_payload_to_canonical(p_tech_alias_int)

    # 2b. Canonical 1.0.0 missing technique_name entirely raises ValueError
    p_missing_tech = json.loads(json.dumps(raw))
    del p_missing_tech["query"]["bound_actions"][0]["technique_name"]
    with pytest.raises(
        ValueError, match="Canonical 1.0.0 bound action .* missing mandatory 'technique_name'"
    ):
        migrate_wire_payload_to_canonical(p_missing_tech)

    # 2c. Legacy draft with valid technique alias migrates to technique_name
    p_draft_tech = json.loads(json.dumps(p_missing_tech))
    p_draft_tech["query"]["bound_actions"][0]["technique"] = "reset_password"
    migrated_tech = migrate_wire_payload_to_canonical(p_draft_tech, source_layout="1.0.0-draft")
    assert migrated_tech["query"]["bound_actions"][0]["technique_name"] == "reset_password"

    # 3. Conflicting technique aliases
    p_tech_conflict = json.loads(json.dumps(raw))
    p_tech_conflict["query"]["bound_actions"][0]["technique_name"] = "reset_password"
    p_tech_conflict["query"]["bound_actions"][0]["technique"] = "other_technique"
    with pytest.raises(ValueError, match="conflicting technique aliases"):
        migrate_wire_payload_to_canonical(p_tech_conflict)

    # 4. Invalid scope_binding types (False, None, int)
    for bad_scope in (False, None, 123):
        p_scope_bad = json.loads(json.dumps(raw))
        p_scope_bad["candidates"][0]["scope_binding"] = bad_scope
        with pytest.raises(TypeError, match="scope_binding must be dict"):
            migrate_wire_payload_to_canonical(p_scope_bad)

    # 5. Empty dictionary scope_binding fails closed (both migration and direct engine)
    p_scope_empty = json.loads(json.dumps(raw))
    p_scope_empty["candidates"][0]["scope_binding"] = {}
    with pytest.raises(ValueError, match="scope_binding missing required field 'query_id'"):
        migrate_wire_payload_to_canonical(p_scope_empty)
    with pytest.raises(Exception, match="missing required field 'query_id'"):
        engine = PathRankingEngine(version="1.0.0")
        engine.evaluate(p_scope_empty["query"], p_scope_empty["candidates"])

    # 6. Partial dictionary scope_binding fails closed
    p_scope_partial = json.loads(json.dumps(raw))
    p_scope_partial["candidates"][0]["scope_binding"] = {"query_id": "query-seamless-host-to-dc-v1"}
    with pytest.raises(ValueError, match="scope_binding missing required field 'scenario_id'"):
        migrate_wire_payload_to_canonical(p_scope_partial)

    # 7. Conflicting scope_binding field
    p_scope_conflict = json.loads(json.dumps(raw))
    p_scope_conflict["candidates"][0]["scope_binding"]["horizon"] = "h99_unsupported"
    with pytest.raises(ValueError, match="conflicts with query_metadata"):
        migrate_wire_payload_to_canonical(p_scope_conflict)

    # 8. Absent scope_binding: canonical 1.0.0 fails closed, while draft layout derives template
    p_scope_absent = json.loads(json.dumps(raw))
    del p_scope_absent["candidates"][0]["scope_binding"]
    del p_scope_absent["candidates"][1]["scope_binding"]
    with pytest.raises(
        ValueError, match="Canonical 1.0.0 candidate .* missing mandatory 'scope_binding'"
    ):
        migrate_wire_payload_to_canonical(p_scope_absent)

    migrated_absent = migrate_wire_payload_to_canonical(p_scope_absent, source_layout="1.0.0-draft")
    for c in migrated_absent["candidates"]:
        assert "scope_binding" in c and isinstance(c["scope_binding"], dict)
        assert len(c["scope_binding"]) == 7
        assert c["scope_binding"]["query_id"] == "query-seamless-host-to-dc-v1"
    engine = PathRankingEngine(version="1.0.0")
    res_absent = engine.evaluate(migrated_absent["query"], migrated_absent["candidates"])
    parsed_absent = json.loads(res_absent["encoded_json"])
    assert len(parsed_absent["pareto_frontier"]) == 2

    # 9. Invalid provenance_locators type (False)
    p_loc_bool = json.loads(json.dumps(raw))
    p_loc_bool["candidates"][0]["structural_routes"][0]["provenance_locators"] = False
    with pytest.raises(TypeError, match="provenance_locators must be list"):
        migrate_wire_payload_to_canonical(p_loc_bool)

    # 10. Invalid requires/adds types fail closed
    p_req_bool = json.loads(json.dumps(raw))
    p_req_bool["query"]["bound_actions"][0]["requires"] = False
    with pytest.raises(TypeError, match="requires must be list"):
        migrate_wire_payload_to_canonical(p_req_bool)

    p_adds_bool = json.loads(json.dumps(raw))
    p_adds_bool["query"]["bound_actions"][0]["adds"] = False
    with pytest.raises(TypeError, match="adds must be list"):
        migrate_wire_payload_to_canonical(p_adds_bool)

    # 11. Missing requires and adds fail closed (no silent empty-list healing)
    p_missing_req = json.loads(json.dumps(raw))
    del p_missing_req["query"]["bound_actions"][0]["requires"]
    with pytest.raises(ValueError, match="missing required 'requires' field"):
        migrate_wire_payload_to_canonical(p_missing_req)
    with pytest.raises(ValueError, match="missing required 'requires' field"):
        migrate_wire_payload_to_canonical(p_missing_req, source_layout="1.0.0-draft")
    with pytest.raises(Exception, match="missing required 'requires' field"):
        engine.evaluate(p_missing_req["query"], p_missing_req["candidates"])

    p_missing_adds = json.loads(json.dumps(raw))
    del p_missing_adds["query"]["bound_actions"][0]["adds"]
    with pytest.raises(ValueError, match="missing required 'adds' field"):
        migrate_wire_payload_to_canonical(p_missing_adds)
    with pytest.raises(ValueError, match="missing required 'adds' field"):
        migrate_wire_payload_to_canonical(p_missing_adds, source_layout="1.0.0-draft")
    with pytest.raises(Exception, match="missing required 'adds' field"):
        engine.evaluate(p_missing_adds["query"], p_missing_adds["candidates"])


def test_migration_layout_declaration_precedence_and_conflicts_fail_closed():
    """Verify declared layout precedence, falsy/type validation, and conflict fail-closed."""
    raw = json.loads((FIXTURES / "seamless_proposed_query_input.json").read_text(encoding="utf-8"))

    # 1. Caller source_layout argument type and empty string validation
    for bad_arg in (False, True, 123, []):
        with pytest.raises(TypeError, match="source_layout argument must be non-empty string"):
            migrate_wire_payload_to_canonical(raw, source_layout=bad_arg)

    for empty_arg in ("", "   "):
        with pytest.raises(ValueError, match="source_layout argument must be a non-empty string"):
            migrate_wire_payload_to_canonical(raw, source_layout=empty_arg)

    # 2. Payload declared source_layout type and empty string validation
    for bad_meta_layout in (False, True, None, 123, []):
        p_bad = json.loads(json.dumps(raw))
        p_bad["query"]["query_metadata"]["source_layout"] = bad_meta_layout
        with pytest.raises(
            TypeError, match="query_metadata source_layout must be non-empty string"
        ):
            migrate_wire_payload_to_canonical(p_bad)

    for empty_meta in ("", "   "):
        p_empty = json.loads(json.dumps(raw))
        p_empty["query"]["query_metadata"]["source_layout"] = empty_meta
        with pytest.raises(
            ValueError, match="query_metadata source_layout must be a non-empty string"
        ):
            migrate_wire_payload_to_canonical(p_empty)

    p_unsupp = json.loads(json.dumps(raw))
    p_unsupp["query"]["query_metadata"]["source_layout"] = "unsupported_layout"
    with pytest.raises(
        ValueError, match="Unsupported source_layout 'unsupported_layout' in query_metadata"
    ):
        migrate_wire_payload_to_canonical(p_unsupp)

    # 3. Payload legacy layout alias type and empty string validation
    for bad_legacy in (False, True, None, 123, []):
        p_bad_l = json.loads(json.dumps(raw))
        p_bad_l["query"]["query_metadata"]["layout"] = bad_legacy
        with pytest.raises(TypeError, match="query_metadata layout must be non-empty string"):
            migrate_wire_payload_to_canonical(p_bad_l)

    for empty_legacy in ("", "   "):
        p_empty_l = json.loads(json.dumps(raw))
        p_empty_l["query"]["query_metadata"]["layout"] = empty_legacy
        with pytest.raises(ValueError, match="query_metadata layout must be a non-empty string"):
            migrate_wire_payload_to_canonical(p_empty_l)

    p_unsupp_l = json.loads(json.dumps(raw))
    p_unsupp_l["query"]["query_metadata"]["layout"] = "unsupported_legacy_layout"
    with pytest.raises(
        ValueError, match="Unsupported layout 'unsupported_legacy_layout' in query_metadata"
    ):
        migrate_wire_payload_to_canonical(p_unsupp_l)

    # 4. Conflicting payload declarations (source_layout vs layout)
    p_conflict_payload = json.loads(json.dumps(raw))
    p_conflict_payload["query"]["query_metadata"]["source_layout"] = "canonical"
    p_conflict_payload["query"]["query_metadata"]["layout"] = "1.0.0-draft"
    with pytest.raises(ValueError, match="Conflicting layout declarations in query_metadata"):
        migrate_wire_payload_to_canonical(p_conflict_payload)

    # Consistent payload declarations (both canonical or equivalent)
    p_consistent_payload = json.loads(json.dumps(raw))
    p_consistent_payload["query"]["query_metadata"]["source_layout"] = "canonical"
    p_consistent_payload["query"]["query_metadata"]["layout"] = "1.0.0"
    migrated_cons = migrate_wire_payload_to_canonical(p_consistent_payload)
    assert migrated_cons["query"]["query_metadata"]["source_layout"] == "1.0.0"
    assert (
        migrated_cons["query"]["query_metadata"]["migration_audit"]["declared_layout"]
        == "canonical"
    )

    # 5. Precedence: canonical-declared payload + draft override argument => fails closed
    p_declared_canonical = json.loads(json.dumps(raw))
    p_declared_canonical["query"]["query_metadata"]["source_layout"] = "canonical"
    with pytest.raises(
        ValueError,
        match="Conflicting source_layout argument '1.0.0-draft' with declared payload layout",
    ):
        migrate_wire_payload_to_canonical(p_declared_canonical, source_layout="1.0.0-draft")

    p_declared_100 = json.loads(json.dumps(raw))
    p_declared_100["query"]["query_metadata"]["source_layout"] = "1.0.0"
    with pytest.raises(
        ValueError,
        match="Conflicting source_layout argument '1.0.0-draft' with declared payload layout",
    ):
        migrate_wire_payload_to_canonical(p_declared_100, source_layout="1.0.0-draft")

    p_declared_legacy = json.loads(json.dumps(raw))
    p_declared_legacy["query"]["query_metadata"]["layout"] = "canonical"
    with pytest.raises(
        ValueError,
        match="Conflicting source_layout argument '1.0.0-draft' with declared payload layout",
    ):
        migrate_wire_payload_to_canonical(p_declared_legacy, source_layout="1.0.0-draft")

    # Matching override argument with declared layout succeeds
    migrated_matching = migrate_wire_payload_to_canonical(
        p_declared_canonical, source_layout="canonical"
    )
    assert migrated_matching["query"]["query_metadata"]["source_layout"] == "1.0.0"
    assert (
        migrated_matching["query"]["query_metadata"]["migration_audit"]["declared_layout"]
        == "canonical"
    )

    # 6. Historical mislabeled 1.0.0 without layout declaration allows caller draft override
    p_mislabeled = json.loads(json.dumps(raw))
    assert "source_layout" not in p_mislabeled["query"]["query_metadata"]
    assert "layout" not in p_mislabeled["query"]["query_metadata"]
    p_mislabeled["query"]["query_metadata"]["version"] = "1.0.0"
    del p_mislabeled["candidates"][0]["structural_routes"][0]["provenance_locators"]
    del p_mislabeled["candidates"][1]["structural_routes"][0]["provenance_locators"]

    migrated_mislabeled = migrate_wire_payload_to_canonical(
        p_mislabeled, source_layout="1.0.0-draft"
    )
    meta_mis = migrated_mislabeled["query"]["query_metadata"]
    assert meta_mis["source_version"] == "1.0.0"
    assert meta_mis["source_layout"] == "1.0.0-draft"
    assert meta_mis["migration_audit"] == {
        "source_version": "1.0.0",
        "declared_layout": None,
        "source_layout": "1.0.0-draft",
        "target_version": "1.0.0",
        "migrated": True,
    }
    assert (
        len(migrated_mislabeled["candidates"][0]["structural_routes"][0]["provenance_locators"])
        == 3
    )


def test_migration_version_dispatch_and_snapshot_pinning():
    """Verify version dispatch support matrix and audited snapshot locator scoping."""
    assert SUPPORTED_SOURCE_LAYOUTS == frozenset(
        {"legacy_draft", "1.0.0-draft", "1.0.0", "canonical"}
    )
    assert SUPPORTED_SOURCE_VERSIONS == frozenset({"legacy_draft", "1.0.0-draft", "1.0.0"})

    raw = json.loads((FIXTURES / "seamless_proposed_query_input.json").read_text(encoding="utf-8"))
    engine = PathRankingEngine(version="1.0.0")

    # 1. Unsupported target_version
    with pytest.raises(ValueError, match="Unsupported target_version '99.0.0'"):
        migrate_wire_payload_to_canonical(raw, target_version="99.0.0")

    # 2. Unsupported source version
    p_bad_ver = json.loads(json.dumps(raw))
    p_bad_ver["query"]["query_metadata"]["version"] = "99.0.0"
    with pytest.raises(ValueError, match="Unsupported source version '99.0.0'"):
        migrate_wire_payload_to_canonical(p_bad_ver)

    # 3. Explicit null source version fails closed (both direct engine and migration)
    p_null_ver = json.loads(json.dumps(raw))
    p_null_ver["query"]["query_metadata"]["version"] = None
    with pytest.raises(ValueError, match="Missing required query_metadata field: 'version'"):
        migrate_wire_payload_to_canonical(p_null_ver)
    with pytest.raises(Exception, match="Missing required query_metadata field: 'version'"):
        engine.evaluate(p_null_ver["query"], p_null_ver["candidates"])

    # 4. Missing version key fails closed (both direct engine and migration)
    p_missing_ver = json.loads(json.dumps(raw))
    del p_missing_ver["query"]["query_metadata"]["version"]
    with pytest.raises(ValueError, match="Missing required query_metadata field: 'version'"):
        migrate_wire_payload_to_canonical(p_missing_ver)
    with pytest.raises(Exception, match="Missing required query_metadata field: 'version'"):
        engine.evaluate(p_missing_ver["query"], p_missing_ver["candidates"])

    # 5. Non-string source version (int, bool) fails closed
    p_int_ver = json.loads(json.dumps(raw))
    p_int_ver["query"]["query_metadata"]["version"] = 123
    with pytest.raises(TypeError, match="query_metadata version must be non-empty string"):
        migrate_wire_payload_to_canonical(p_int_ver)

    # 6. Empty string source version fails closed
    p_empty_ver = json.loads(json.dumps(raw))
    p_empty_ver["query"]["query_metadata"]["version"] = "   "
    with pytest.raises(ValueError, match="query_metadata version must be a non-empty string"):
        migrate_wire_payload_to_canonical(p_empty_ver)

    # 7. Supported source versions all migrate cleanly and evaluate successfully
    for sup_ver in ("legacy_draft", "1.0.0-draft", "1.0.0"):
        p_sup = json.loads(json.dumps(raw))
        p_sup["query"]["query_metadata"]["version"] = sup_ver
        migrated = migrate_wire_payload_to_canonical(p_sup)
        m_meta = migrated["query"]["query_metadata"]
        assert m_meta["version"] == "1.0.0"
        assert m_meta["source_version"] == sup_ver
        assert m_meta["source_layout"] == sup_ver
        assert m_meta["migration_audit"]["source_version"] == sup_ver
        assert m_meta["migration_audit"]["declared_layout"] is None
        assert m_meta["migration_audit"]["source_layout"] == sup_ver
        assert m_meta["migration_audit"]["migrated"] == (sup_ver != "1.0.0")
        res = engine.evaluate(migrated["query"], migrated["candidates"])
        parsed = json.loads(res["encoded_json"])
        assert len(parsed["pareto_frontier"]) == 2

    # 8. Explicit source_layout parameter and conflict validation
    with pytest.raises(ValueError, match="Unsupported source_layout 'unsupported_profile'"):
        migrate_wire_payload_to_canonical(raw, source_layout="unsupported_profile")

    p_conflict = json.loads(json.dumps(raw))
    p_conflict["query"]["query_metadata"]["version"] = "legacy_draft"
    with pytest.raises(
        ValueError, match="Conflicting version 'legacy_draft' with canonical source_layout"
    ):
        migrate_wire_payload_to_canonical(p_conflict, source_layout="canonical")

    # 9. Snapshot scoping and route locators:
    # On canonical 1.0.0, missing provenance_locators strictly fails closed
    assert raw["query"]["query_metadata"]["snapshot_id"] == AUDITED_SEAMLESS_SNAPSHOT_ID
    p_audited = json.loads(json.dumps(raw))
    del p_audited["candidates"][0]["structural_routes"][0]["provenance_locators"]
    del p_audited["candidates"][1]["structural_routes"][0]["provenance_locators"]
    with pytest.raises(
        ValueError, match="Canonical 1.0.0 route .* missing mandatory 'provenance_locators'"
    ):
        migrate_wire_payload_to_canonical(p_audited)

    # On legacy draft layout, missing provenance_locators resolves from locators table
    migrated_audited = migrate_wire_payload_to_canonical(p_audited, source_layout="1.0.0-draft")
    assert (
        len(migrated_audited["candidates"][0]["structural_routes"][0]["provenance_locators"]) == 3
    )

    # 10. Unpinned snapshot without custom table fails closed on draft layout
    p_other_snap = json.loads(json.dumps(p_audited))
    other_snap_id = "sha256:0000000000000000000000000000000000000000000000000000000000000000"
    p_other_snap["query"]["query_metadata"]["snapshot_id"] = other_snap_id
    for c in p_other_snap["candidates"]:
        if "scope_binding" in c:
            c["scope_binding"]["snapshot_id"] = other_snap_id
    with pytest.raises(ValueError, match="missing provenance locator for edge"):
        migrate_wire_payload_to_canonical(p_other_snap, source_layout="1.0.0-draft")

    # 11. Unpinned snapshot with explicit edge_locators_table succeeds on draft layout
    all_edges = list(
        {
            eid
            for c in raw["candidates"]
            for r in c.get("structural_routes", [])
            for eid in r.get("edge_ids", [])
        }
    )
    custom_table = {eid: f"snapshot_000#/locators/{idx}" for idx, eid in enumerate(all_edges)}
    migrated_custom = migrate_wire_payload_to_canonical(
        p_other_snap, source_layout="1.0.0-draft", edge_locators_table=custom_table
    )
    first_eid = p_other_snap["candidates"][0]["structural_routes"][0]["edge_ids"][0]
    assert (
        migrated_custom["candidates"][0]["structural_routes"][0]["provenance_locators"][0]
        == custom_table[first_eid]
    )

    # 12. Conflicting edge locator in custom table fails closed
    conflict_table = {all_edges[0]: "conflicting_locator"}
    with pytest.raises(ValueError, match="Conflicting edge locator"):
        migrate_wire_payload_to_canonical(raw, edge_locators_table=conflict_table)

    # 13. Canonical work unit validation vs draft migration:
    # distinct_work fails closed on canonical 1.0.0, migrates on 1.0.0-draft
    p_distinct = json.loads(json.dumps(raw))
    first_uid = next(iter(p_distinct["query"]["work_units_ledger"].keys()))
    p_distinct["query"]["work_units_ledger"][first_uid]["overlap_state"] = "distinct_work"
    with pytest.raises(ValueError, match="has unsupported legacy overlap_state 'distinct_work'"):
        migrate_wire_payload_to_canonical(p_distinct)
    migrated_distinct = migrate_wire_payload_to_canonical(p_distinct, source_layout="1.0.0-draft")
    assert (
        migrated_distinct["query"]["work_units_ledger"][first_uid]["overlap_state"] == "independent"
    )

    # Missing rating_status fails closed on canonical 1.0.0, migrates from status on draft
    p_missing_status = json.loads(json.dumps(raw))
    del p_missing_status["query"]["work_units_ledger"][first_uid]["rating_status"]
    p_missing_status["query"]["work_units_ledger"][first_uid]["status"] = "rated"
    with pytest.raises(ValueError, match="missing mandatory 'rating_status'"):
        migrate_wire_payload_to_canonical(p_missing_status)
    migrated_status = migrate_wire_payload_to_canonical(
        p_missing_status, source_layout="1.0.0-draft"
    )
    assert migrated_status["query"]["work_units_ledger"][first_uid]["rating_status"] == "rated"


def project_canonical_to_common(canonical_payload: dict[str, Any]) -> dict[str, Any]:
    """Project a canonical engine evaluation result to the common research result format.

    Extracts common contract fields shared with research oracle fixtures by:
    1. Removing top-level canonical-only envelope: 'parameter_audit'.
    2. Removing candidate-level canonical-only fields ('work_unit_basis',
       'conditional_bounds_basis', 'diagnostic_reasons') from eligible_candidates
       and any candidate assessments in diagnostics.
    3. Normalizing the ordering of diagnostic reasons lists to allow deterministic
       comparison without masking schema or values drift.
    All search_metadata, eligible_candidates (with exact intervals, efforts, impacts,
    routes, gates, coverage), pareto_frontier, min_effort_to_da_baseline, and diagnostics
    assessments/gates/coverage are strictly preserved and asserted.
    """
    proj = copy.deepcopy(canonical_payload)
    proj.pop("parameter_audit", None)
    for c in proj.get("eligible_candidates", {}).values():
        if isinstance(c, dict):
            c.pop("work_unit_basis", None)
            c.pop("conditional_bounds_basis", None)
            c.pop("diagnostic_reasons", None)
            if "likelihood_basis_summary" in c and isinstance(c["likelihood_basis_summary"], str):
                c["likelihood_basis_summary"] = c["likelihood_basis_summary"].split(";")[0]
    for d in proj.get("diagnostics", {}).values():
        if isinstance(d, dict):
            if "reasons" in d and isinstance(d["reasons"], list):
                d["reasons"] = sorted(d["reasons"])
            if "assessment" in d and isinstance(d["assessment"], dict):
                d["assessment"].pop("work_unit_basis", None)
                d["assessment"].pop("conditional_bounds_basis", None)
                d["assessment"].pop("diagnostic_reasons", None)
    return proj


def normalize_expected_diagnostics(expected_payload: dict[str, Any]) -> dict[str, Any]:
    """Normalize reason ordering in expected oracle diagnostics for comparison."""
    norm = copy.deepcopy(expected_payload)
    for d in norm.get("diagnostics", {}).values():
        if isinstance(d, dict) and "reasons" in d and isinstance(d["reasons"], list):
            d["reasons"] = sorted(d["reasons"])
    return norm


def test_canonical_engine_proposal_a_and_b_full_audit_contract():
    """Verify canonical engine outputs maintain full parameter_audit and basis contract."""
    engine = PathRankingEngine(version="1.0.0")

    # --- Source A Evaluation ---
    raw_a = json.loads(
        (FIXTURES / "seamless_proposed_query_input.json").read_text(encoding="utf-8")
    )
    res_a = engine.evaluate(raw_a["query"], raw_a["candidates"])
    parsed_a = json.loads(res_a["encoded_json"])
    exp_a = json.loads(
        (FIXTURES / "seamless_proposed_expected_output.json").read_text(encoding="utf-8")
    )

    # 1. Exact common result projection against research oracle
    assert project_canonical_to_common(parsed_a) == normalize_expected_diagnostics(exp_a)

    # 2. Source A has TWO frontier candidates on Pareto frontier
    assert parsed_a["pareto_frontier"] == [
        "cand_seamless_01_direct_lidia",
        "cand_seamless_02_alt_vajer_ollie",
    ]
    assert (
        parsed_a["min_effort_to_da_baseline"]["best_candidate_id"]
        == "cand_seamless_01_direct_lidia"
    )
    assert parsed_a["min_effort_to_da_baseline"]["minimum_effort_value"] == 2

    # 3. Exact parameter_audit values matching input query components
    audit_a = parsed_a["parameter_audit"]
    assert audit_a["query_metadata"] == raw_a["query"]["query_metadata"]
    assert audit_a["work_units_ledger"] == raw_a["query"]["work_units_ledger"]
    assert audit_a["conditional_bounds_table"] == raw_a["query"]["conditional_bounds_table"]
    assert audit_a["target_impact_assessments"] == raw_a["query"]["target_impact_assessments"]

    # 4. Exact per-candidate basis fields
    for cid in ("cand_seamless_01_direct_lidia", "cand_seamless_02_alt_vajer_ollie"):
        c = parsed_a["eligible_candidates"][cid]
        assert "work_unit_basis" in c and isinstance(c["work_unit_basis"], dict)
        assert len(c["work_unit_basis"]) > 0
        for uid, ubasis in c["work_unit_basis"].items():
            assert uid in raw_a["query"]["work_units_ledger"]
            expected_u = raw_a["query"]["work_units_ledger"][uid]
            for field in (
                "overlap_state",
                "rating_status",
                "effort",
                "missing_basis_reasons",
                "rubric_scores",
                "effort_cost",
                "computed_cost",
            ):
                if field in expected_u:
                    assert ubasis.get(field) == expected_u.get(field)
            if expected_u.get("rubric_scores"):
                assert ubasis.get("t1") == expected_u["rubric_scores"].get("t1")
                assert ubasis.get("t2") == expected_u["rubric_scores"].get("t2")
        assert "conditional_bounds_basis" in c and isinstance(c["conditional_bounds_basis"], list)
        assert len(c["conditional_bounds_basis"]) > 0
        for row in c["conditional_bounds_basis"]:
            assert any(
                r["prefix"] == row["prefix"]
                and r["lower"] == row["lower"]
                and r["upper"] == row["upper"]
                for r in raw_a["query"]["conditional_bounds_table"]
            )
        assert c.get("diagnostic_reasons") == []

    # --- Source B Evaluation ---
    raw_b = json.loads(
        (FIXTURES / "seamless_source_b_proposed_query_input.json").read_text(encoding="utf-8")
    )
    res_b = engine.evaluate(raw_b["query"], raw_b["candidates"])
    parsed_b = json.loads(res_b["encoded_json"])
    exp_b = json.loads(
        (FIXTURES / "seamless_source_b_proposed_expected_output.json").read_text(encoding="utf-8")
    )

    # 1. Exact common result projection against research oracle
    assert project_canonical_to_common(parsed_b) == normalize_expected_diagnostics(exp_b)

    # 2. Source B has ONE frontier candidate on Pareto frontier
    assert parsed_b["pareto_frontier"] == ["cand_seamless_source_b_01_ollie"]
    assert (
        parsed_b["min_effort_to_da_baseline"]["best_candidate_id"]
        == "cand_seamless_source_b_01_ollie"
    )
    assert parsed_b["min_effort_to_da_baseline"]["minimum_effort_value"] == 2

    # 3. Exact parameter_audit values matching input query components
    audit_b = parsed_b["parameter_audit"]
    assert audit_b["query_metadata"] == raw_b["query"]["query_metadata"]
    assert audit_b["work_units_ledger"] == raw_b["query"]["work_units_ledger"]
    assert audit_b["conditional_bounds_table"] == raw_b["query"]["conditional_bounds_table"]
    assert audit_b["target_impact_assessments"] == raw_b["query"]["target_impact_assessments"]

    # 4. Exact per-candidate basis fields
    c_b = parsed_b["eligible_candidates"]["cand_seamless_source_b_01_ollie"]
    assert "work_unit_basis" in c_b and len(c_b["work_unit_basis"]) > 0
    for uid, ubasis in c_b["work_unit_basis"].items():
        assert uid in raw_b["query"]["work_units_ledger"]
        expected_u = raw_b["query"]["work_units_ledger"][uid]
        for field in (
            "overlap_state",
            "rating_status",
            "effort",
            "missing_basis_reasons",
            "rubric_scores",
            "effort_cost",
            "computed_cost",
        ):
            if field in expected_u:
                assert ubasis.get(field) == expected_u.get(field)
        if expected_u.get("rubric_scores"):
            assert ubasis.get("t1") == expected_u["rubric_scores"].get("t1")
            assert ubasis.get("t2") == expected_u["rubric_scores"].get("t2")
    assert "conditional_bounds_basis" in c_b and len(c_b["conditional_bounds_basis"]) > 0
    for row in c_b["conditional_bounds_basis"]:
        assert any(
            r["prefix"] == row["prefix"]
            and r["lower"] == row["lower"]
            and r["upper"] == row["upper"]
            for r in raw_b["query"]["conditional_bounds_table"]
        )
    assert c_b.get("diagnostic_reasons") == []


def test_canonical_engine_pending_fixtures_and_diagnostics():
    """Verify actual pending fixtures A and B through canonical boundary."""
    engine = PathRankingEngine(version="1.0.0")

    # 1. Actual Pending A Fixture Evaluation
    raw_pa = json.loads((FIXTURES / "seamless_query_input.json").read_text(encoding="utf-8"))
    migrated_pa = migrate_wire_payload_to_canonical(raw_pa)
    res_pa = engine.evaluate(migrated_pa["query"], migrated_pa["candidates"])
    parsed_pa = json.loads(res_pa["encoded_json"])
    exp_pa = json.loads(
        (FIXTURES / "seamless_expected_diagnostics.json").read_text(encoding="utf-8")
    )

    # Exact common result projection against research oracle
    assert project_canonical_to_common(parsed_pa) == normalize_expected_diagnostics(exp_pa)

    # Empty Pareto frontier and baseline disclosure
    assert parsed_pa["pareto_frontier"] == []
    assert parsed_pa["min_effort_to_da_baseline"]["best_candidate_id"] is None
    assert parsed_pa["min_effort_to_da_baseline"]["minimum_effort_value"] is None
    assert (
        parsed_pa["min_effort_to_da_baseline"]["coverage_disclosure"]
        == "No feasible rated candidate found in evaluated set."
    )

    # Both candidates unrated in diagnostics
    assert len(parsed_pa["diagnostics"]) == 2
    for diag in parsed_pa["diagnostics"].values():
        assert sorted(diag["reasons"]) == ["impact_unrated", "likelihood_unrated"]
        ass = diag["assessment"]
        assert ass["status"] == "feasible"
        assert ass["effort_status"] == "unrated"
        assert ass["effort"] is None
        assert ass["impact_status"] == "unrated"
        assert ass["impact"] is None
        assert ass["likelihood_status"] == "unrated"
        assert ass["likelihood_interval"] is None
        for ubasis in ass["work_unit_basis"].values():
            assert ubasis["missing_basis_reasons"] == ["pending_independent_ratings"]
            assert ubasis["rating_status"] == "unrated"

    # Audit preservation
    assert parsed_pa["parameter_audit"]["query_metadata"] == migrated_pa["query"]["query_metadata"]
    assert (
        parsed_pa["parameter_audit"]["work_units_ledger"]
        == migrated_pa["query"]["work_units_ledger"]
    )

    # 2. Actual Pending B Fixture Evaluation
    raw_pb = json.loads(
        (FIXTURES / "seamless_source_b_query_input.json").read_text(encoding="utf-8")
    )
    migrated_pb = migrate_wire_payload_to_canonical(raw_pb)
    res_pb = engine.evaluate(migrated_pb["query"], migrated_pb["candidates"])
    parsed_pb = json.loads(res_pb["encoded_json"])
    exp_pb = json.loads(
        (FIXTURES / "seamless_source_b_expected_diagnostics.json").read_text(encoding="utf-8")
    )

    # Exact common result projection against research oracle
    assert project_canonical_to_common(parsed_pb) == normalize_expected_diagnostics(exp_pb)

    # Empty Pareto frontier and baseline disclosure
    assert parsed_pb["pareto_frontier"] == []
    assert parsed_pb["min_effort_to_da_baseline"]["best_candidate_id"] is None
    assert parsed_pb["min_effort_to_da_baseline"]["minimum_effort_value"] is None
    assert (
        parsed_pb["min_effort_to_da_baseline"]["coverage_disclosure"]
        == "No feasible rated candidate found in evaluated set."
    )

    # Candidate Ollie unrated in diagnostics
    assert "cand_seamless_source_b_01_ollie" in parsed_pb["diagnostics"]
    diag_b = parsed_pb["diagnostics"]["cand_seamless_source_b_01_ollie"]
    assert sorted(diag_b["reasons"]) == ["impact_unrated", "likelihood_unrated"]
    ass_b = diag_b["assessment"]
    assert ass_b["status"] == "feasible"
    assert ass_b["effort_status"] == "unrated"
    assert ass_b["effort"] is None
    assert ass_b["impact_status"] == "unrated"
    assert ass_b["impact"] is None
    assert ass_b["likelihood_status"] == "unrated"
    assert ass_b["likelihood_interval"] is None
    for ubasis in ass_b["work_unit_basis"].values():
        assert ubasis["missing_basis_reasons"] == ["pending_independent_ratings"]
        assert ubasis["rating_status"] == "unrated"

    # Audit preservation
    assert parsed_pb["parameter_audit"]["query_metadata"] == migrated_pb["query"]["query_metadata"]
    assert (
        parsed_pb["parameter_audit"]["work_units_ledger"]
        == migrated_pb["query"]["work_units_ledger"]
    )


def test_canonical_engine_false_fact_veto_and_unknown_gating_both_sources():
    """Verify false-fact vetoes and unknown-fact gating across both Source A and Source B."""
    engine = PathRankingEngine(version="1.0.0")

    # --- Source A: False Fact Veto ---
    raw_a_false = json.loads(
        (FIXTURES / "seamless_proposed_query_input.json").read_text(encoding="utf-8")
    )
    raw_a_false["query"]["facts_ledger"]["false_facts"].append(
        {
            "predicate": "admin_execution_context_lidia",
            "truth_value": False,
            "layer": 3,
            "provenance_reference": "telemetry:admin_ctx_lidia_denied",
        }
    )
    migrated_a_false = migrate_wire_payload_to_canonical(raw_a_false)
    res_a_false = engine.evaluate(migrated_a_false["query"], migrated_a_false["candidates"])
    parsed_a_false = json.loads(res_a_false["encoded_json"])

    assert "cand_seamless_01_direct_lidia" not in parsed_a_false["pareto_frontier"]
    assert parsed_a_false["pareto_frontier"] == ["cand_seamless_02_alt_vajer_ollie"]
    assert "cand_seamless_01_direct_lidia" in parsed_a_false["diagnostics"]
    diag_a_c1 = parsed_a_false["diagnostics"]["cand_seamless_01_direct_lidia"]
    assert diag_a_c1["assessment"]["status"] == "blocked"
    assert diag_a_c1["assessment"]["gates_evaluation"]["admin_execution_context_lidia"] == "False"
    assert "blocked" in diag_a_c1["reasons"]

    # --- Source A: Unknown Fact Gating ---
    raw_a_unk = json.loads(
        (FIXTURES / "seamless_proposed_query_input.json").read_text(encoding="utf-8")
    )
    raw_a_unk["query"]["facts_ledger"]["assumed_facts"] = [
        f
        for f in raw_a_unk["query"]["facts_ledger"]["assumed_facts"]
        if f.get("predicate") != "winrm_authentication_accepted_lidia"
    ]
    migrated_a_unk = migrate_wire_payload_to_canonical(raw_a_unk)
    res_a_unk = engine.evaluate(migrated_a_unk["query"], migrated_a_unk["candidates"])
    parsed_a_unk = json.loads(res_a_unk["encoded_json"])

    assert "cand_seamless_01_direct_lidia" not in parsed_a_unk["pareto_frontier"]
    assert parsed_a_unk["pareto_frontier"] == ["cand_seamless_02_alt_vajer_ollie"]
    assert "cand_seamless_01_direct_lidia" in parsed_a_unk["diagnostics"]
    diag_a_unk = parsed_a_unk["diagnostics"]["cand_seamless_01_direct_lidia"]
    assert diag_a_unk["assessment"]["status"] == "unknown"
    assert (
        diag_a_unk["assessment"]["gates_evaluation"]["winrm_authentication_accepted_lidia"]
        == "Unknown"
    )
    assert "unknown" in diag_a_unk["reasons"]

    # --- Source B: False Fact Veto ---
    raw_b_false = json.loads(
        (FIXTURES / "seamless_source_b_proposed_query_input.json").read_text(encoding="utf-8")
    )
    raw_b_false["query"]["facts_ledger"]["false_facts"].append(
        {
            "predicate": "admin_execution_context_ollie",
            "truth_value": False,
            "layer": 3,
            "provenance_reference": "telemetry:admin_ctx_ollie_denied",
        }
    )
    migrated_b_false = migrate_wire_payload_to_canonical(raw_b_false)
    res_b_false = engine.evaluate(migrated_b_false["query"], migrated_b_false["candidates"])
    parsed_b_false = json.loads(res_b_false["encoded_json"])

    assert parsed_b_false["pareto_frontier"] == []
    assert "cand_seamless_source_b_01_ollie" in parsed_b_false["diagnostics"]
    diag_b_c1 = parsed_b_false["diagnostics"]["cand_seamless_source_b_01_ollie"]
    assert diag_b_c1["assessment"]["status"] == "blocked"
    assert diag_b_c1["assessment"]["gates_evaluation"]["admin_execution_context_ollie"] == "False"
    assert "blocked" in diag_b_c1["reasons"]

    # --- Source B: Unknown Fact Gating ---
    raw_b_unk = json.loads(
        (FIXTURES / "seamless_source_b_proposed_query_input.json").read_text(encoding="utf-8")
    )
    raw_b_unk["query"]["facts_ledger"]["assumed_facts"] = [
        f
        for f in raw_b_unk["query"]["facts_ledger"]["assumed_facts"]
        if f.get("predicate") != "winrm_authentication_accepted_ollie"
    ]
    migrated_b_unk = migrate_wire_payload_to_canonical(raw_b_unk)
    res_b_unk = engine.evaluate(migrated_b_unk["query"], migrated_b_unk["candidates"])
    parsed_b_unk = json.loads(res_b_unk["encoded_json"])

    assert parsed_b_unk["pareto_frontier"] == []
    assert "cand_seamless_source_b_01_ollie" in parsed_b_unk["diagnostics"]
    diag_b_unk = parsed_b_unk["diagnostics"]["cand_seamless_source_b_01_ollie"]
    assert diag_b_unk["assessment"]["status"] == "unknown"
    assert (
        diag_b_unk["assessment"]["gates_evaluation"]["winrm_authentication_accepted_ollie"]
        == "Unknown"
    )
    assert "unknown" in diag_b_unk["reasons"]


def test_seamless_parameter_bundle_schema_and_completeness():
    """Verify seamless_parameter_bundle.json structure, completeness, and governance commitments."""
    bundle_file = FIXTURES / "seamless_parameter_bundle.json"
    assert bundle_file.exists(), f"Missing parameter bundle fixture {bundle_file}"
    bundle = json.loads(bundle_file.read_text(encoding="utf-8"))

    report = verify_parameter_bundle(bundle)
    assert report["status"] == "PASS"
    assert report["bundle_id"] == "bundle-seamless-host-to-dc-v1"
    assert report["bundle_version"] == "1.0.0"
    assert report["scenario_version"] == "1.1.0"
    assert report["work_units_count"] == 9
    assert report["conditional_bounds_count"] == 11
    assert report["assumed_facts_count"] == 26
    assert report["candidates_count"] == 3
    assert report["governance_status"] == "pending_independent_human_ratings"

    # Verify target impact
    impacts = bundle["target_impact_assessments"]
    assert "S-1-5-21-1271839998-3495686680-2211690266-1000" in impacts
    dc_impact = impacts["S-1-5-21-1271839998-3495686680-2211690266-1000"]
    assert dc_impact["consequence_rating"] == "High"
    assert dc_impact["rating_status"] == "rated"
    assert dc_impact["success_event"] == "terminal_compromise_seamless_dc"

    # Verify all 9 work units are rated with base formula
    for _uid, unit in bundle["work_units_ledger"].items():
        assert unit["rating_status"] == "rated"
        assert unit["overlap_state"] == "independent"
        assert unit["rubric_scores"]["formula"] == "base"
        assert unit["rubric_scores"]["computed_cost"] == unit["effort_cost"]

    # Verify all 11 bounds have valid rational fractions
    for row in bundle["conditional_bounds_table"]:
        l_frac = Fraction(row["lower"])
        u_frac = Fraction(row["upper"])
        assert Fraction(0) <= l_frac <= u_frac <= Fraction(1)


def test_parameter_bundle_matches_query_fixtures():
    """Verify seamless_proposed_query_input fixtures are exact projections of parameter bundle."""
    bundle_file = FIXTURES / "seamless_parameter_bundle.json"
    bundle = json.loads(bundle_file.read_text(encoding="utf-8"))

    # Source A projection check (100% dictionary equality)
    query_a, cands_a = extract_query_and_candidates_from_bundle(bundle, "source_a")
    source_a_fixture = json.loads(
        (FIXTURES / "seamless_proposed_query_input.json").read_text(encoding="utf-8")
    )
    assert query_a == source_a_fixture["query"]
    assert cands_a == source_a_fixture["candidates"]

    # Source B projection check (100% dictionary equality)
    query_b, cands_b = extract_query_and_candidates_from_bundle(bundle, "source_b")
    source_b_fixture = json.loads(
        (FIXTURES / "seamless_source_b_proposed_query_input.json").read_text(encoding="utf-8")
    )
    assert query_b == source_b_fixture["query"]
    assert cands_b == source_b_fixture["candidates"]


def test_parameter_bundle_calculation_traces_and_pareto():
    """Verify roundtrip execution from bundle extracts reproduces calculation traces and Pareto."""
    bundle_file = FIXTURES / "seamless_parameter_bundle.json"
    bundle = json.loads(bundle_file.read_text(encoding="utf-8"))

    # Source A evaluation directly from bundle
    query_a, cands_a = extract_query_and_candidates_from_bundle(bundle, "source_a")
    res_a = execute_ranking_roundtrip(json.dumps(query_a), cands_a)
    traces_a = verify_calculation_traces(res_a["roundtrip_result"])
    assert traces_a["status"] == "PASS"
    assert set(traces_a["pareto_frontier"]) == {
        "cand_seamless_01_direct_lidia",
        "cand_seamless_02_alt_vajer_ollie",
    }
    assert traces_a["min_effort_to_da"]["best_candidate_id"] == "cand_seamless_01_direct_lidia"
    assert traces_a["min_effort_to_da"]["minimum_effort_value"] == 2

    # Source B evaluation directly from bundle
    query_b, cands_b = extract_query_and_candidates_from_bundle(bundle, "source_b")
    res_b = execute_ranking_roundtrip(json.dumps(query_b), cands_b)
    rt_b = res_b["roundtrip_result"]
    assert rt_b["pareto_frontier"] == ["cand_seamless_source_b_01_ollie"]
    cand_b = rt_b["eligible_candidates"]["cand_seamless_source_b_01_ollie"]
    assert cand_b["effort"] == 2
    assert cand_b["impact"] == "High"
    assert cand_b["likelihood_interval"] == ["42/125", "171/250"]


def test_parameter_bundle_cli_validation(tmp_path: Path):
    """Verify seamless_parameter_validation.py CLI executes cleanly with --bundle argument."""
    script = ROOT / "scripts" / "research" / "seamless_parameter_validation.py"
    bundle_file = FIXTURES / "seamless_parameter_bundle.json"
    out_file = tmp_path / "bundle_validation_report.json"

    cmd = [
        sys.executable,
        str(script),
        "--bundle",
        str(bundle_file),
        "--output",
        str(out_file),
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, check=False)
    assert res.returncode == 0, f"Script failed with code {res.returncode}:\n{res.stderr}"
    assert "SEAMLESS PARAMETER PROPOSAL VALIDATION" in res.stdout
    assert "Parameter Bundle: PASS" in res.stdout

    assert out_file.exists()
    report = json.loads(out_file.read_text(encoding="utf-8"))
    assert report["schema_version"] == "1.0.0"
    assert "bundle_validation" in report
    assert report["bundle_validation"]["status"] == "PASS"
    assert report["bundle_validation"]["bundle_id"] == "bundle-seamless-host-to-dc-v1"
    assert "calculation_traces" in report
    assert "sensitivity_analysis" in report


def test_parameter_bundle_governance_and_human_sheets_safeguard():
    """Verify governance integrity: hypotheses pending human agreement; sheets pristine."""
    bundle_file = FIXTURES / "seamless_parameter_bundle.json"
    bundle = json.loads(bundle_file.read_text(encoding="utf-8"))

    gov = bundle["governance"]
    assert gov["basis_category"] == "research_assisted_scenario_hypotheses"
    assert gov["status"] == "pending_independent_human_ratings"
    assert gov["human_agreement_status"] == "pending"
    assert gov["empirical_calibration_status"] == "none"
    assert gov["raters"] == []
    assert gov["reconciliation"] is None

    # Both rater sheets must remain unrated/pristine
    for rater_name in ("seamless_rater_1.json", "seamless_rater_2.json"):
        sheet_file = FIXTURES / rater_name
        assert sheet_file.exists()
        sheet = json.loads(sheet_file.read_text(encoding="utf-8"))
        assert sheet.get("status") == "pending_independent_rating"
        rater = sheet.get("rater", {})
        assert all(val is None for val in rater.values())

        # Check effort ratings
        assert len(sheet.get("effort_ratings", [])) == 9
        for rec in sheet["effort_ratings"]:
            assert rec.get("rating_status") == "unrated"
            rubric = rec.get("rubric_evaluation", {})
            assert rubric.get("computed_cost") is None

        # Check likelihood ratings
        assert len(sheet.get("likelihood_ratings", [])) == 11
        for rec in sheet["likelihood_ratings"]:
            assert rec.get("rating_status") == "unrated"
            cb = rec.get("conditional_bounds", {})
            assert cb.get("lower") is None
            assert cb.get("upper") is None

        # Check impact ratings
        assert len(sheet.get("impact_ratings", [])) == 1
        for rec in sheet["impact_ratings"]:
            assert rec.get("rating_status") == "unrated"
            assert rec.get("consequence_rating") is None


def test_parameter_bundle_negative_scope_drift():
    """Verify scope drift (mismatched snapshot_id on candidate) is rejected fail-closed."""
    engine = PathRankingEngine(version="1.0.0")
    source_a_fixture = json.loads(
        (FIXTURES / "seamless_proposed_query_input.json").read_text(encoding="utf-8")
    )
    query = copy.deepcopy(source_a_fixture["query"])
    cands = copy.deepcopy(source_a_fixture["candidates"])
    # Alter snapshot_id on candidate 1 to simulate scope drift
    cands[0]["scope_binding"]["snapshot_id"] = (
        "sha256:0000000000000000000000000000000000000000000000000000000000000000"
    )

    with pytest.raises(RankingValidationError, match="snapshot_id"):
        engine.evaluate(query, cands)


def _sync_bundle_digest(bundle: dict[str, Any]) -> str:
    """Helper to recompute valid digest and synchronize into bundle and query_projections."""
    digest = compute_bundle_digest(bundle)
    bundle["bundle_metadata"]["bundle_digest"] = digest
    if "query_projections" in bundle:
        for proj in bundle["query_projections"].values():
            if isinstance(proj, dict) and "query" in proj:
                qmeta = proj["query"].get("query_metadata", {})
                if "bundle_digest" in qmeta:
                    qmeta["bundle_digest"] = digest
    return digest


def test_parameter_bundle_negative_source_b_bounds_drift():
    """Verify Source B conditional bounds drift is detected against analytical baseline."""
    bundle_file = FIXTURES / "seamless_parameter_bundle.json"
    bundle = json.loads(bundle_file.read_text(encoding="utf-8"))
    # Drift Source B bound q9 lower bound from 7/10 to 1/10 in projection
    bundle["query_projections"]["source_b"]["query"]["conditional_bounds_table"][0]["lower"] = (
        "1/10"
    )
    _sync_bundle_digest(bundle)

    with pytest.raises(ValueError):
        verify_parameter_bundle(bundle)


def test_parameter_bundle_negative_root_bounds_mutation_fails_coherence_or_oracle():
    """Verify root conditional bounds mutation is detected fail-closed with valid digest."""
    bundle_file = FIXTURES / "seamless_parameter_bundle.json"
    bundle = json.loads(bundle_file.read_text(encoding="utf-8"))
    # Mutate root conditional bounds table (change lower from 7/10 to 1/10)
    bundle["conditional_bounds_table"][8]["lower"] = "1/10"
    _sync_bundle_digest(bundle)

    with pytest.raises(ValueError):
        verify_parameter_bundle(bundle)


def test_parameter_bundle_negative_root_snapshot_mutation_fails():
    """Verify root snapshot_id mutation is detected fail-closed with valid digest."""
    bundle_file = FIXTURES / "seamless_parameter_bundle.json"
    bundle = json.loads(bundle_file.read_text(encoding="utf-8"))
    bundle["bundle_metadata"]["snapshot_id"] = (
        "sha256:0000000000000000000000000000000000000000000000000000000000000000"
    )
    _sync_bundle_digest(bundle)

    with pytest.raises((ValueError, RankingValidationError)):
        verify_parameter_bundle(bundle)


def test_parameter_bundle_negative_root_candidate_snapshot_mutation_fails():
    """Verify root candidate envelope snapshot mutation is detected with valid digest."""
    bundle_file = FIXTURES / "seamless_parameter_bundle.json"
    bundle = json.loads(bundle_file.read_text(encoding="utf-8"))
    bundle["candidate_envelopes"][2]["scope_binding"]["snapshot_id"] = (
        "sha256:0000000000000000000000000000000000000000000000000000000000000000"
    )
    _sync_bundle_digest(bundle)

    with pytest.raises((ValueError, RankingValidationError)):
        verify_parameter_bundle(bundle)


def test_parameter_bundle_negative_noncanonical_inputs():
    """Verify noncanonical overlap_state ('distinct_work' or 'overlapping') is rejected."""
    bundle_file = FIXTURES / "seamless_parameter_bundle.json"
    bundle = json.loads(bundle_file.read_text(encoding="utf-8"))
    first_uid = next(iter(bundle["work_units_ledger"].keys()))
    bundle["work_units_ledger"][first_uid]["overlap_state"] = "distinct_work"
    _sync_bundle_digest(bundle)

    with pytest.raises(ValueError, match="canonical overlap_state 'independent'"):
        verify_parameter_bundle(bundle)


def test_parameter_bundle_negative_governance_inconsistencies():
    """Verify governance inconsistencies are rejected even with valid digest."""
    bundle_file = FIXTURES / "seamless_parameter_bundle.json"

    # Case 1: empirical_calibration claimed without raters
    b1 = json.loads(bundle_file.read_text(encoding="utf-8"))
    b1["governance"]["empirical_calibration_status"] = "calibrated"
    _sync_bundle_digest(b1)
    with pytest.raises(ValueError, match="empirical_calibration"):
        verify_parameter_bundle(b1)

    # Case 2: human_agreement claimed without raters
    b2 = json.loads(bundle_file.read_text(encoding="utf-8"))
    b2["governance"]["human_agreement_status"] = "consensus"
    _sync_bundle_digest(b2)
    with pytest.raises(ValueError, match="human_agreement"):
        verify_parameter_bundle(b2)

    # Case 3: reconciliation verdict claimed while pending human ratings
    b3 = json.loads(bundle_file.read_text(encoding="utf-8"))
    b3["governance"]["reconciliation"] = {"verdict": "Consensus"}
    _sync_bundle_digest(b3)
    with pytest.raises(ValueError, match="reconciliation"):
        verify_parameter_bundle(b3)

    # Case 4: basis_category empirical_calibration while pending
    b4 = json.loads(bundle_file.read_text(encoding="utf-8"))
    b4["governance"]["basis_category"] = "empirical_calibration"
    _sync_bundle_digest(b4)
    with pytest.raises(ValueError, match="basis_category"):
        verify_parameter_bundle(b4)

    # Case 5: fabricated raters while pending
    b5 = json.loads(bundle_file.read_text(encoding="utf-8"))
    b5["governance"]["raters"] = ["fabricated_rater_1", "fabricated_rater_2"]
    _sync_bundle_digest(b5)
    with pytest.raises(ValueError, match="Governance raters must be empty list"):
        verify_parameter_bundle(b5)


def test_parameter_bundle_negative_governance_projection_disagreement():
    """Verify disagreement between root governance and projected governance is rejected."""
    bundle_file = FIXTURES / "seamless_parameter_bundle.json"
    bundle = json.loads(bundle_file.read_text(encoding="utf-8"))
    bundle["query_projections"]["source_a"]["query"]["query_metadata"]["governance"][
        "human_agreement_status"
    ] = "consensus"
    bundle["query_projections"]["source_a"]["query"]["query_metadata"]["governance"]["raters"] = [
        "fake_rater_1"
    ]
    _sync_bundle_digest(bundle)

    with pytest.raises(ValueError):
        verify_parameter_bundle(bundle)


def test_parameter_bundle_require_valid_digest_and_reject_falsy():
    """Verify bundle_digest is strictly required and non-falsy/valid for canonical bundle 1.0.0."""
    bundle_file = FIXTURES / "seamless_parameter_bundle.json"

    # Missing digest
    b_missing = json.loads(bundle_file.read_text(encoding="utf-8"))
    del b_missing["bundle_metadata"]["bundle_digest"]
    with pytest.raises(ValueError, match="bundle_digest"):
        verify_parameter_bundle(b_missing)

    # Empty string digest
    b_empty = json.loads(bundle_file.read_text(encoding="utf-8"))
    b_empty["bundle_metadata"]["bundle_digest"] = ""
    with pytest.raises(ValueError, match="bundle_digest"):
        verify_parameter_bundle(b_empty)

    # Null digest
    b_null = json.loads(bundle_file.read_text(encoding="utf-8"))
    b_null["bundle_metadata"]["bundle_digest"] = None
    with pytest.raises(ValueError, match="bundle_digest"):
        verify_parameter_bundle(b_null)

    # Boolean digest
    b_bool = json.loads(bundle_file.read_text(encoding="utf-8"))
    b_bool["bundle_metadata"]["bundle_digest"] = False
    with pytest.raises(ValueError, match="bundle_digest"):
        verify_parameter_bundle(b_bool)

    # Corrupted / mismatched digest
    b_bad = json.loads(bundle_file.read_text(encoding="utf-8"))
    b_bad["bundle_metadata"]["bundle_digest"] = "sha256:" + "0" * 64
    with pytest.raises(ValueError, match="Bundle digest mismatch"):
        verify_parameter_bundle(b_bad)


def test_parameter_validation_cli_negative_cases(tmp_path: Path):
    """Verify CLI negative paths for missing bundle, missing input, and mutual exclusion."""
    script = ROOT / "scripts" / "research" / "seamless_parameter_validation.py"

    # 1. Non-existent bundle
    p1 = subprocess.run(
        [sys.executable, str(script), "--bundle", str(tmp_path / "non_existent.json")],
        capture_output=True,
        text=True,
    )
    assert p1.returncode == 2
    assert "Bundle file not found" in p1.stderr

    # 2. Non-existent input
    p2 = subprocess.run(
        [sys.executable, str(script), "--input", str(tmp_path / "non_existent.json")],
        capture_output=True,
        text=True,
    )
    assert p2.returncode == 2
    assert "Input file not found" in p2.stderr

    # 3. Both bundle and input provided
    p3 = subprocess.run(
        [
            sys.executable,
            str(script),
            "--bundle",
            str(FIXTURES / "seamless_parameter_bundle.json"),
            "--input",
            str(FIXTURES / "seamless_proposed_query_input.json"),
        ],
        capture_output=True,
        text=True,
    )
    assert p3.returncode == 2
    assert "not allowed with argument" in p3.stderr


def test_parameter_validation_cli_regressions(tmp_path: Path):
    """Verify CLI fails closed (exit != 0) on semantic corruption and falsy digest."""
    script = ROOT / "scripts" / "research" / "seamless_parameter_validation.py"
    bundle_file = FIXTURES / "seamless_parameter_bundle.json"

    # Regression 1: Root bounds changed with valid digest
    b1 = json.loads(bundle_file.read_text(encoding="utf-8"))
    b1["conditional_bounds_table"][8]["lower"] = "1/10"
    _sync_bundle_digest(b1)
    p1_path = tmp_path / "root_bound_drift.json"
    p1_path.write_text(json.dumps(b1, indent=2))
    p1 = subprocess.run(
        [sys.executable, str(script), "--bundle", str(p1_path)],
        capture_output=True,
        text=True,
    )
    assert p1.returncode != 0

    # Regression 2: Self-contradictory governance with valid digest
    b2 = json.loads(bundle_file.read_text(encoding="utf-8"))
    b2["governance"]["basis_category"] = "empirical_calibration"
    b2["governance"]["reconciliation"] = {"verdict": "Consensus"}
    _sync_bundle_digest(b2)
    p2_path = tmp_path / "gov_contradiction.json"
    p2_path.write_text(json.dumps(b2, indent=2))
    p2 = subprocess.run(
        [sys.executable, str(script), "--bundle", str(p2_path)],
        capture_output=True,
        text=True,
    )
    assert p2.returncode != 0

    # Regression 3: Root vs projected governance disagreement with valid digest
    b3 = json.loads(bundle_file.read_text(encoding="utf-8"))
    b3["query_projections"]["source_a"]["query"]["query_metadata"]["governance"][
        "human_agreement_status"
    ] = "consensus"
    b3["query_projections"]["source_a"]["query"]["query_metadata"]["governance"]["raters"] = [
        "fake_rater"
    ]
    _sync_bundle_digest(b3)
    p3_path = tmp_path / "gov_disagreement.json"
    p3_path.write_text(json.dumps(b3, indent=2))
    p3 = subprocess.run(
        [sys.executable, str(script), "--bundle", str(p3_path)],
        capture_output=True,
        text=True,
    )
    assert p3.returncode != 0

    # Regression 4: Missing or falsy digest
    b4 = json.loads(bundle_file.read_text(encoding="utf-8"))
    b4["bundle_metadata"]["bundle_digest"] = ""
    p4_path = tmp_path / "falsy_digest.json"
    p4_path.write_text(json.dumps(b4, indent=2))
    p4 = subprocess.run(
        [sys.executable, str(script), "--bundle", str(p4_path)],
        capture_output=True,
        text=True,
    )
    assert p4.returncode != 0


def test_root_bundle_required_false_fact_rejected_and_canonical_blocked(tmp_path: Path):
    """Verify root required false fact fails validation and blocks candidate in engine."""
    script = ROOT / "scripts" / "research" / "seamless_parameter_validation.py"
    bundle_file = FIXTURES / "seamless_parameter_bundle.json"

    # 1. With stale cached projections (cache has false_facts=[])
    b_stale = json.loads(bundle_file.read_text(encoding="utf-8"))
    b_stale["facts_ledger"]["false_facts"].append(
        {
            "predicate": "endpoint_authorized_lidia",
            "truth_value": False,
            "layer": 3,
            "provenance_reference": "review:synthetic-negative",
            "applicable_queries": ["query-seamless-host-to-dc-v1"],
        }
    )
    _sync_bundle_digest(b_stale)
    with pytest.raises(ValueError, match="does not match authoritative root records"):
        verify_parameter_bundle(b_stale)

    p_stale_path = tmp_path / "root_false_stale_cache.json"
    p_stale_path.write_text(json.dumps(b_stale, indent=2))
    p_stale = subprocess.run(
        [sys.executable, str(script), "--bundle", str(p_stale_path)],
        capture_output=True,
        text=True,
    )
    assert p_stale.returncode != 0
    assert "does not match authoritative root records" in p_stale.stderr

    # 2. Without cached projections: analytical oracle detects Cand 1 missing from eligible set
    b_nocache = json.loads(bundle_file.read_text(encoding="utf-8"))
    b_nocache["facts_ledger"]["false_facts"].append(
        {
            "predicate": "endpoint_authorized_lidia",
            "truth_value": False,
            "layer": 3,
            "provenance_reference": "review:synthetic-negative",
            "applicable_queries": ["query-seamless-host-to-dc-v1"],
        }
    )
    del b_nocache["query_projections"]
    _sync_bundle_digest(b_nocache)
    with pytest.raises(ValueError, match="cand_seamless_01_direct_lidia missing from eligible"):
        verify_parameter_bundle(b_nocache)

    p_nocache_path = tmp_path / "root_false_nocache.json"
    p_nocache_path.write_text(json.dumps(b_nocache, indent=2))
    p_nocache = subprocess.run(
        [sys.executable, str(script), "--bundle", str(p_nocache_path)],
        capture_output=True,
        text=True,
    )
    assert p_nocache.returncode != 0
    assert "cand_seamless_01_direct_lidia missing from eligible" in p_nocache.stderr

    # 3. Direct canonical engine execution on derived query: Candidate 1 blocked, Cand 2 sole winner
    query_a, cands_a = derive_query_and_candidates_from_bundle(b_nocache, "source_a")
    assert any(
        f["predicate"] == "endpoint_authorized_lidia"
        for f in query_a["facts_ledger"]["false_facts"]
    )
    engine = PathRankingEngine(version="1.0.0")
    res_a = engine.evaluate(query_a, cands_a)
    rt_a = res_a["roundtrip_result"]
    assert "cand_seamless_01_direct_lidia" in rt_a["diagnostics"]
    assert rt_a["diagnostics"]["cand_seamless_01_direct_lidia"]["assessment"]["status"] == "blocked"
    assert rt_a["pareto_frontier"] == ["cand_seamless_02_alt_vajer_ollie"]


def test_root_bundle_irrelevant_false_fact_preserved_and_passes(tmp_path: Path):
    """Verify root irrelevant false fact is preserved in query and does not veto valid paths."""
    script = ROOT / "scripts" / "research" / "seamless_parameter_validation.py"
    bundle_file = FIXTURES / "seamless_parameter_bundle.json"

    b = json.loads(bundle_file.read_text(encoding="utf-8"))
    b["facts_ledger"]["false_facts"].append(
        {
            "predicate": "synthetic_unrelated_service_reachable",
            "truth_value": False,
            "layer": 3,
            "provenance_reference": "test:synthetic_irrelevant_false",
            "applicable_queries": ["query-seamless-host-to-dc-v1"],
        }
    )
    del b["query_projections"]
    _sync_bundle_digest(b)

    # Verify Source A derived query preserves the irrelevant false fact and predicate layer
    query_a, _ = derive_query_and_candidates_from_bundle(b, "source_a")
    false_preds_a = {f["predicate"]: f for f in query_a["facts_ledger"]["false_facts"]}
    assert "synthetic_unrelated_service_reachable" in false_preds_a
    assert false_preds_a["synthetic_unrelated_service_reachable"]["layer"] == 3
    assert (
        false_preds_a["synthetic_unrelated_service_reachable"]["provenance_reference"]
        == "test:synthetic_irrelevant_false"
    )
    assert query_a["facts_ledger"]["predicate_layers"]["synthetic_unrelated_service_reachable"] == 3

    # Verify Source B derived query is completely unaffected
    query_b, _ = derive_query_and_candidates_from_bundle(b, "source_b")
    assert len(query_b["facts_ledger"]["false_facts"]) == 0

    # Verify bundle validation passes via API and CLI
    report = verify_parameter_bundle(b)
    assert report["status"] == "PASS"

    p_path = tmp_path / "root_irrelevant_false.json"
    p_path.write_text(json.dumps(b, indent=2))
    p = subprocess.run(
        [sys.executable, str(script), "--bundle", str(p_path)],
        capture_output=True,
        text=True,
    )
    assert p.returncode == 0
    assert "Parameter Bundle: PASS" in p.stdout


def test_root_bundle_source_b_scoped_false_fact_isolation(tmp_path: Path):
    """Verify false fact scoped to Source B does not affect Source A, and blocks Source B."""
    script = ROOT / "scripts" / "research" / "seamless_parameter_validation.py"
    bundle_file = FIXTURES / "seamless_parameter_bundle.json"

    b = json.loads(bundle_file.read_text(encoding="utf-8"))
    b["facts_ledger"]["false_facts"].append(
        {
            "predicate": "endpoint_authorized_ollie",
            "truth_value": False,
            "layer": 3,
            "provenance_reference": "test:synthetic_source_b_false",
            "applicable_queries": ["query-seamless-source-b-to-dc-v1"],
        }
    )
    del b["query_projections"]
    _sync_bundle_digest(b)

    # Source A has no false facts and retains both candidates
    query_a, cands_a = derive_query_and_candidates_from_bundle(b, "source_a")
    assert len(query_a["facts_ledger"]["false_facts"]) == 0
    engine = PathRankingEngine(version="1.0.0")
    res_a = engine.evaluate(query_a, cands_a)
    assert len(res_a["roundtrip_result"]["eligible_candidates"]) == 2

    # Source B has the false fact and candidate B is blocked
    query_b, cands_b = derive_query_and_candidates_from_bundle(b, "source_b")
    assert any(
        f["predicate"] == "endpoint_authorized_ollie"
        for f in query_b["facts_ledger"]["false_facts"]
    )
    res_b = engine.evaluate(query_b, cands_b)
    assert "cand_seamless_source_b_01_ollie" in res_b["roundtrip_result"]["diagnostics"]
    assert (
        res_b["roundtrip_result"]["diagnostics"]["cand_seamless_source_b_01_ollie"]["assessment"][
            "status"
        ]
        == "blocked"
    )

    # verify_parameter_bundle fails because Source B candidate is blocked
    with pytest.raises(ValueError, match="cand_seamless_source_b_01_ollie missing from eligible"):
        verify_parameter_bundle(b)

    p_path = tmp_path / "root_b_false.json"
    p_path.write_text(json.dumps(b, indent=2))
    p = subprocess.run(
        [sys.executable, str(script), "--bundle", str(p_path)],
        capture_output=True,
        text=True,
    )
    assert p.returncode != 0
    assert "cand_seamless_source_b_01_ollie missing from eligible" in p.stderr


def test_parameter_bundle_probability_bounds_contract_and_endpoints(tmp_path: Path):
    """Verify probability bounds invariant aligns with 0 <= l <= u <= 1 and accepts endpoints."""
    script = ROOT / "scripts" / "research" / "seamless_parameter_validation.py"
    bundle_file = FIXTURES / "seamless_parameter_bundle.json"

    # 1. Endpoint probabilities (1/1, 0/1, 0/1..1/1) must NOT be rejected by bounds validation
    for lower_ep, upper_ep in [("1/1", "1/1"), ("0/1", "0/1"), ("0/1", "1/1")]:
        b_ep = json.loads(bundle_file.read_text(encoding="utf-8"))
        b_ep["conditional_bounds_table"][0]["lower"] = lower_ep
        b_ep["conditional_bounds_table"][0]["upper"] = upper_ep
        del b_ep["query_projections"]
        _sync_bundle_digest(b_ep)
        # Bounds invariant 0 <= l <= u <= 1 must accept endpoints without bounds ValueError
        try:
            verify_parameter_bundle(b_ep)
        except ValueError as err:
            assert "Invalid probability interval" not in str(err)

    # 2. Negative test: lower bound < 0 rejected
    b_neg = json.loads(bundle_file.read_text(encoding="utf-8"))
    b_neg["conditional_bounds_table"][0]["lower"] = "-1/10"
    del b_neg["query_projections"]
    _sync_bundle_digest(b_neg)
    with pytest.raises(ValueError, match="Invalid probability interval"):
        verify_parameter_bundle(b_neg)

    # 3. Negative test: upper bound > 1 rejected
    b_over = json.loads(bundle_file.read_text(encoding="utf-8"))
    b_over["conditional_bounds_table"][0]["upper"] = "11/10"
    del b_over["query_projections"]
    _sync_bundle_digest(b_over)
    with pytest.raises(ValueError, match="Invalid probability interval"):
        verify_parameter_bundle(b_over)

    # 4. Negative test: inverted bounds lower > upper rejected
    b_inv = json.loads(bundle_file.read_text(encoding="utf-8"))
    b_inv["conditional_bounds_table"][0]["lower"] = "9/10"
    b_inv["conditional_bounds_table"][0]["upper"] = "7/10"
    del b_inv["query_projections"]
    _sync_bundle_digest(b_inv)
    with pytest.raises(ValueError, match="Invalid probability interval"):
        verify_parameter_bundle(b_inv)

    # 5. CLI execution fails closed on invalid bound
    p_inv_path = tmp_path / "invalid_bound.json"
    p_inv_path.write_text(json.dumps(b_inv, indent=2))
    p_inv = subprocess.run(
        [sys.executable, str(script), "--bundle", str(p_inv_path)],
        capture_output=True,
        text=True,
    )
    assert p_inv.returncode != 0
    assert "Invalid probability interval" in p_inv.stderr


def test_parameter_bundle_closed_world_cardinality_and_extension_rejection(tmp_path: Path):
    """Verify bundle validator enforces exact released 1.0.0 record counts and closed-world sets."""
    script = ROOT / "scripts" / "research" / "seamless_parameter_validation.py"
    bundle_file = FIXTURES / "seamless_parameter_bundle.json"

    # 1. Extra work unit rejected
    b_extra_wu = json.loads(bundle_file.read_text(encoding="utf-8"))
    b_extra_wu["work_units_ledger"]["extra_unit"] = {
        "rating_status": "rated",
        "overlap_state": "independent",
        "effort_cost": 1,
        "computed_cost": 1,
        "rubric_scores": {"t1": 1, "t2": 2, "formula": "base", "computed_cost": 1},
    }
    _sync_bundle_digest(b_extra_wu)
    with pytest.raises(ValueError, match="Work units ledger must contain exactly 9 units"):
        verify_parameter_bundle(b_extra_wu)

    # 2. Extra conditional bound row rejected
    b_extra_bound = json.loads(bundle_file.read_text(encoding="utf-8"))
    extra_row = copy.deepcopy(b_extra_bound["conditional_bounds_table"][0])
    extra_row["question_id"] = "q_extra"
    extra_row["prefix"] = ["extra_prefix_item"]
    b_extra_bound["conditional_bounds_table"].append(extra_row)
    _sync_bundle_digest(b_extra_bound)
    with pytest.raises(ValueError, match="Conditional bounds table must have 11 rows"):
        verify_parameter_bundle(b_extra_bound)

    # 3. Extra action rejected
    b_extra_action = json.loads(bundle_file.read_text(encoding="utf-8"))
    extra_act = copy.deepcopy(b_extra_action["bound_actions"][0])
    extra_act["action_id"] = "action_extra"
    b_extra_action["bound_actions"].append(extra_act)
    _sync_bundle_digest(b_extra_action)
    with pytest.raises(ValueError, match="Bound actions must contain exactly 12 actions"):
        verify_parameter_bundle(b_extra_action)

    # 4. Extra candidate envelope rejected
    b_extra_cand = json.loads(bundle_file.read_text(encoding="utf-8"))
    extra_cand = copy.deepcopy(b_extra_cand["candidate_envelopes"][0])
    extra_cand["candidate_id"] = "cand_seamless_03_extra"
    b_extra_cand["candidate_envelopes"].append(extra_cand)
    _sync_bundle_digest(b_extra_cand)
    with pytest.raises(ValueError, match="Candidate envelopes must contain exactly 3 candidates"):
        verify_parameter_bundle(b_extra_cand)

    # 5. CLI execution fails closed on extra unscoped record
    p_extra_path = tmp_path / "extra_cand.json"
    p_extra_path.write_text(json.dumps(b_extra_cand, indent=2))
    p_extra = subprocess.run(
        [sys.executable, str(script), "--bundle", str(p_extra_path)],
        capture_output=True,
        text=True,
    )
    assert p_extra.returncode != 0
    assert "Candidate envelopes must contain exactly 3 candidates" in p_extra.stderr
