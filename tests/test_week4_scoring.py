"""Week 4 Scoring Conformance Tests for Issue #207.

Verifies:
- Checksum integrity against manifest.sha256.
- Canonical evaluator (PathRankingEngine v1.0.0) execution matching actual results.
- CLI roundtrip execution via run_ranking_cli.
- Read-only verification mode CLI (--verify) without modifying files.
- Corruption and drift detection under read-only verification.
- Anti-double-counting equality between Direct and Member-Direct programs.
- Intra-program multi-action work unit reuse (split vs merged invariance).
- M/D/I history sequence replay ledger effort (6 instead of 7).
- Negative control: distinct context work units are not deduplicated.
- Counter-structural Min-Effort resolution under Ledger E (2 steps effort 2 beats 1 step effort 5).
- Conservative Pareto incomparability under overlapping likelihood intervals.
- 3-way Min-Effort tie under Ledger T.
- ADR-0013 Section 4 effort tie-break under exact point likelihood.
- Diagnostic partitioning for blocked, unknown, likelihood_unrated, effort_unrated, impact_unrated.
- SEAMLESS parameter disposition invariants (21 parameters unchanged, extensions unrated).
"""

from __future__ import annotations

import copy
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from scripts.research.week4_scoring_eval import verify_existing_artifacts
from src.engine.ranking import PathRankingEngine, scoped_preference
from src.engine.ranking.assessment import assess_candidate_program
from src.engine.ranking.cli import run_ranking_cli
from src.engine.ranking.models import ScopedPreferenceVerdict
from src.engine.ranking.validation import decode_ranking_query

ROOT = Path(__file__).resolve().parents[1]
RATINGS_DIR = ROOT / "docs" / "research" / "ratings" / "week4"
MANIFEST_PATH = RATINGS_DIR / "manifest.sha256"


def load_package(filename: str) -> dict[str, Any]:
    """Load JSON package from docs/research/ratings/week4/."""
    file_path = RATINGS_DIR / filename
    return json.loads(file_path.read_text(encoding="utf-8"))


def evaluate_package(pkg: dict[str, Any]) -> dict[str, Any]:
    """Execute canonical PathRankingEngine and extract roundtrip result payload."""
    engine = PathRankingEngine(version="1.0.0")
    raw = engine.evaluate(query_payload=pkg["query"], candidates=pkg["candidates"])
    return raw["roundtrip_result"]


def test_week4_manifest_checksums():
    """Verify all files listed in manifest.sha256 match their actual SHA-256 digests."""
    assert MANIFEST_PATH.exists(), "manifest.sha256 must exist"
    lines = [
        line.strip()
        for line in MANIFEST_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(lines) >= 6, "manifest must contain at least 6 verified artifacts"

    for line in lines:
        expected_digest, rel_path = line.split("  ", 1)
        file_path = ROOT / rel_path
        assert file_path.exists(), f"File in manifest does not exist: {rel_path}"
        actual_digest = hashlib.sha256(file_path.read_bytes()).hexdigest()
        assert actual_digest == expected_digest, f"Checksum mismatch for {rel_path}"


def test_week4_validation_summary_pass():
    """Verify validation summary records ALL_PASS status."""
    summary = load_package("validation-summary.json")
    assert summary["overall_status"] == "ALL_PASS"
    assert summary["evaluator_version"] == "1.0.0"
    assert len(summary["records"]) == 4
    for record in summary["records"]:
        assert record["status"] == "PASS"


def test_week4_seamless_disposition():
    """Verify SEAMLESS disposition preserves Week 3 invariants and declares unrated scope."""
    disp = load_package("week4-seamless-disposition.json")
    assert disp["status"] == "reviewed_disposition"
    assert disp["week3_reference"]["parameters_count"] == 21
    assert disp["week3_reference"]["status"] == "unchanged_historical_baseline"

    dispositions = {d["scope"]: d for d in disp["dispositions"]}
    assert "week4_machine_source_queries_X_to_Y" in dispositions
    assert (
        dispositions["week4_machine_source_queries_X_to_Y"]["week4_reuse_verdict"]
        == "unrated_pending_interface"
    )

    assert "week4_extension_as_rep_roasting" in dispositions
    assert (
        dispositions["week4_extension_as_rep_roasting"]["week4_reuse_verdict"]
        == "unrated_pending_empirical_basis"
    )

    assert "week4_extension_kerberoasting" in dispositions
    assert (
        dispositions["week4_extension_kerberoasting"]["week4_reuse_verdict"]
        == "unrated_pending_empirical_basis"
    )

    assert "week4_da_checkpoint_vs_asset_success" in dispositions
    assert (
        dispositions["week4_da_checkpoint_vs_asset_success"]["week4_reuse_verdict"]
        == "independent_evaluation"
    )


def test_week4_ledger_e_counter_structural_and_incomparability():
    """Verify Ledger E counter-structural Min-Effort and Pareto incomparability."""
    pkg = load_package("synthetic-a2-e.json")
    result = evaluate_package(pkg)

    eligible = result["eligible_candidates"]
    cand_d = eligible["cand_direct"]
    cand_md = eligible["cand_member_direct"]
    cand_mi = eligible["cand_member_inherited"]

    # Anti-double-counting: passive membership adds no extra effort or probability decay
    assert cand_d["effort"] == cand_md["effort"] == 5
    assert cand_d["likelihood_interval"] == cand_md["likelihood_interval"] == ["2/5", "27/40"]

    # Counter-structural Min-Effort: M/I has 2 steps but effort 2, beating D (effort 5)
    assert cand_mi["effort"] == 2
    min_effort_sec = result["min_effort_to_da_baseline"]
    assert min_effort_sec["best_candidate_id"] == "cand_member_inherited"
    assert min_effort_sec["minimum_effort_value"] == 2

    # Pareto incomparability: [2/5, 27/40] and [12/25, 18/25] overlap
    pareto = result["pareto_frontier"]
    assert set(pareto) == {"cand_direct", "cand_member_direct", "cand_member_inherited"}


def test_week4_ledger_t_3way_min_effort_tie():
    """Verify Ledger T produces identical effort 2 for all three programs."""
    pkg = load_package("synthetic-a2-t.json")
    result = evaluate_package(pkg)

    eligible = result["eligible_candidates"]
    assert eligible["cand_direct"]["effort"] == 2
    assert eligible["cand_member_direct"]["effort"] == 2
    assert eligible["cand_member_inherited"]["effort"] == 2

    min_effort_sec = result["min_effort_to_da_baseline"]
    assert min_effort_sec["minimum_effort_value"] == 2
    assert set(result["pareto_frontier"]) == {
        "cand_direct",
        "cand_member_direct",
        "cand_member_inherited",
    }


def test_week4_point_likelihood_effort_tie_break():
    """Verify ADR-0013 Section 4 effort tie-break on identical point likelihood P=1/2."""
    pkg = load_package("synthetic-a2-ties.json")
    result = evaluate_package(pkg)

    eligible = result["eligible_candidates"]
    assert eligible["cand_direct"]["likelihood_interval"] == ["1/2", "1/2"]
    assert eligible["cand_member_inherited"]["likelihood_interval"] == ["1/2", "1/2"]
    assert eligible["cand_direct"]["effort"] == 5
    assert eligible["cand_member_inherited"]["effort"] == 2

    # Under identical point likelihood and identical consequence High, effort 2 dominates effort 5
    assert result["pareto_frontier"] == ["cand_member_inherited"]


def test_week4_runtime_assumption_enables_gate_but_unrated_basis():
    """Verify Issue #207 AC 1: declared runtime assumption satisfies gate but basis is unrated."""
    pkg = load_package("synthetic-a2-diagnostics.json")
    result = evaluate_package(pkg)

    # Candidate cand_assumed_gate_unrated_basis uses action requiring runtime_session_alice
    diag = result["diagnostics"]
    assert "cand_assumed_gate_unrated_basis" in diag
    cand = diag["cand_assumed_gate_unrated_basis"]["assessment"]

    # 1. Gate is feasible because declared assumption is True in scenario mode
    assert cand["status"] == "feasible"
    assert cand["gates_evaluation"]["runtime_session_alice"] == "True"

    # 2. But numeric likelihood basis is missing for this prefix -> unrated
    assert cand["likelihood_status"] == "unrated"
    assert cand["likelihood_interval"] is None
    assert diag["cand_assumed_gate_unrated_basis"]["reasons"] == ["likelihood_unrated"]

    # 3. Candidate is safely quarantined in diagnostics and NEVER enters Pareto frontier
    assert "cand_assumed_gate_unrated_basis" not in result["pareto_frontier"]
    assert "cand_assumed_gate_unrated_basis" not in result["eligible_candidates"]


def test_week4_anti_double_counting_invariants():
    """Verify Issue #207 AC 4: anti-double-counting across split/merge, auth reuse, and hops."""
    pkg = load_package("synthetic-a2-e.json")
    result = evaluate_package(pkg)

    eligible = result["eligible_candidates"]
    cand_d = eligible["cand_direct"]
    cand_md = eligible["cand_member_direct"]
    cand_mi = eligible["cand_member_inherited"]

    # 1. Passive membership hop: D (1 hop) vs M/D (2 hops)
    # Delta effort = 0, delta likelihood = [0, 0]
    delta_effort_hop = cand_md["effort"] - cand_d["effort"]
    assert delta_effort_hop == 0, "Passive membership hop must not add friction effort"
    assert cand_md["likelihood_interval"] == cand_d["likelihood_interval"] == ["2/5", "27/40"]

    # 2. Secret and auth context reuse:
    # w-auth-context is used in both direct and member-inherited branches,
    # but counted exactly once per program (not duplicated)
    assert cand_d["program"] == ["w-auth-context", "w-direct-admin"]
    assert cand_mi["program"] == ["w-auth-context", "w-inherited-admin"]
    assert cand_d["work_unit_basis"]["w-auth-context"]["computed_cost"] == 1

    # 3. Genuine active work differences alter quantities by the exact delta of the added unit:
    # Direct branch uses w-direct-admin (cost 4), Inherited uses w-inherited-admin (cost 1)
    # Unit cost delta = 4 - 1 = +3
    # Total program effort delta = 5 - 2 = +3
    unit_delta = (
        cand_d["work_unit_basis"]["w-direct-admin"]["computed_cost"]
        - cand_mi["work_unit_basis"]["w-inherited-admin"]["computed_cost"]
    )
    program_delta = cand_d["effort"] - cand_mi["effort"]
    assert program_delta == unit_delta == 3, "Real active work must change effort by exact delta"

    # 4. Intra-program multiple actions reusing same work unit:
    # Split actions (Action 1 preparing auth, Action 2 executing admin) must evaluate
    # identically to a single combined action: same program, effort 5, likelihood [2/5, 27/40].
    # If deduplication were disabled, program would have 3 units and effort 6 (1 + 1 + 4 = 6).
    query_split = copy.deepcopy(pkg["query"])
    query_split["facts_ledger"]["predicate_layers"]["auth_prepared"] = 3
    edge_direct_id = pkg["candidates"][0]["structural_routes"][0]["edge_ids"][0]

    act_auth_prep = {
        "action_id": "action_auth_prep",
        "technique": "prep_auth",
        "technique_name": "prep_auth",
        "actor_id": "S-1-5-21-1000-2000-3000-1101",
        "target_id": "10000000-0000-4000-8000-000000000002",
        "edge_id": edge_direct_id,
        "referenced_work_unit_ids": ["w-auth-context"],
        "requires": ["actor_controlled_alice"],
        "adds": ["auth_prepared"],
        "is_passive_closure": False,
    }
    act_admin_exec = {
        "action_id": "action_admin_exec",
        "technique": "exec_admin",
        "technique_name": "exec_admin",
        "actor_id": "S-1-5-21-1000-2000-3000-1101",
        "target_id": "10000000-0000-4000-8000-000000000002",
        "edge_id": edge_direct_id,
        "referenced_work_unit_ids": ["w-auth-context", "w-direct-admin"],
        "requires": ["actor_controlled_alice", "auth_prepared"],
        "adds": ["admin_control_host"],
        "is_passive_closure": False,
    }
    query_split["bound_actions"].extend([act_auth_prep, act_admin_exec])

    cand_split = {
        "candidate_id": "cand_split",
        "target_asset_id": "10000000-0000-4000-8000-000000000002",
        "bound_action_ids": ["action_auth_prep", "action_admin_exec"],
        "scope_binding": copy.deepcopy(pkg["candidates"][0]["scope_binding"]),
        "structural_routes": [
            {
                "route_id": "route_split_1",
                "node_ids": [
                    "S-1-5-21-1000-2000-3000-1101",
                    "10000000-0000-4000-8000-000000000002",
                ],
                "edge_ids": [edge_direct_id],
                "provenance_locators": ["synthetic://golden/two-routes"],
                "action_step_indices": [0],
            },
            {
                "route_id": "route_split_2",
                "node_ids": [
                    "S-1-5-21-1000-2000-3000-1101",
                    "10000000-0000-4000-8000-000000000002",
                ],
                "edge_ids": [edge_direct_id],
                "provenance_locators": ["synthetic://golden/two-routes"],
                "action_step_indices": [1],
            },
        ],
    }

    engine = PathRankingEngine(version="1.0.0")
    res_split_eval = engine.evaluate(query_payload=query_split, candidates=[cand_split])
    split_result = res_split_eval["roundtrip_result"]["eligible_candidates"]["cand_split"]
    assert split_result["effort"] == cand_d["effort"] == 5
    assert split_result["likelihood_interval"] == cand_d["likelihood_interval"] == ["2/5", "27/40"]
    assert split_result["program"] == cand_d["program"] == ["w-auth-context", "w-direct-admin"]

    # 5. M/D/I history sequence replay from #206 (docs/research/week4-scenarios.md line 115):
    # Candidate executing M (passive, 0 units), D ([w-auth-context, w-direct-admin]), and
    # I ([w-auth-context, w-inherited-admin]) in a unified execution sequence.
    # Replayed active program deduplicates w-auth-context once:
    # Program = ("w-auth-context", "w-direct-admin", "w-inherited-admin")
    # Total ledger effort evaluates to 6 (1 + 4 + 1 = 6), NOT 7 (0 + 1 + 4 + 1 + 1 = 7).
    query_mdi = copy.deepcopy(pkg["query"])
    query_mdi["facts_ledger"]["predicate_layers"]["final_post_goal"] = 3
    query_mdi["query_metadata"]["target_goal"]["required_predicates"] = ["final_post_goal"]
    for act in query_mdi["bound_actions"]:
        if act["action_id"] == "action_inherited_admin":
            act["adds"].append("final_post_goal")

    alice_id = "S-1-5-21-1000-2000-3000-1101"
    group_admins_id = "S-1-5-21-1000-2000-3000-2103"
    host_c0_id = "10000000-0000-4000-8000-000000000002"

    cand_mdi = {
        "candidate_id": "cand_mdi",
        "target_asset_id": host_c0_id,
        "bound_action_ids": [
            "action_member_admins",
            "action_direct_admin",
            "action_inherited_admin",
        ],
        "scope_binding": copy.deepcopy(pkg["candidates"][0]["scope_binding"]),
        "structural_routes": [
            {
                "route_id": "route_mdi_semantic",
                "node_ids": [alice_id],
                "edge_ids": [],
                "provenance_locators": [],
                "action_step_indices": [],
                "semantic_lineage": [
                    {
                        "step_index": 0,
                        "action_id": "action_member_admins",
                        "technique_id": "obtain_admin_execution_on_host",
                        "actor": alice_id,
                        "source": alice_id,
                        "target": group_admins_id,
                        "origin": "initial_attack_state",
                        "derived_from_step": None,
                        "status": "applicable",
                    },
                    {
                        "step_index": 1,
                        "action_id": "action_direct_admin",
                        "technique_id": "obtain_admin_execution_on_host",
                        "actor": alice_id,
                        "source": alice_id,
                        "target": host_c0_id,
                        "origin": "initial_attack_state",
                        "derived_from_step": None,
                        "status": "applicable",
                    },
                    {
                        "step_index": 2,
                        "action_id": "action_inherited_admin",
                        "technique_id": "obtain_admin_execution_on_host",
                        "actor": alice_id,
                        "source": alice_id,
                        "target": host_c0_id,
                        "origin": "initial_attack_state",
                        "derived_from_step": None,
                        "status": "applicable",
                    },
                ],
            }
        ],
    }

    decoded_mdi = decode_ranking_query(query_mdi)
    res_mdi = assess_candidate_program(decoded_mdi, cand_mdi)
    assert res_mdi["program"] == ["w-auth-context", "w-direct-admin", "w-inherited-admin"]
    assert res_mdi["effort"] == 6, "M/D/I ledger effort must evaluate to 6 instead of 7"

    # 6. Negative control: distinct context work units are not deduplicated:
    # Context on Host C0 (w-auth-context, cost 1) vs OtherHost X (w-auth-otherhost, cost 1).
    # Since these represent different target entities, both are retained in the program.
    # Total effort is 1 + 1 = 2, proving context-scoped units are preserved.
    pkg_diag = load_package("synthetic-a2-diagnostics.json")
    query_neg = copy.deepcopy(pkg_diag["query"])
    otherhost_x_id = "10000000-0000-4000-8000-000000000003"

    act_auth_c0 = {
        "action_id": "action_auth_c0",
        "technique": "obtain_admin_execution_on_host",
        "technique_name": "obtain_admin_execution_on_host",
        "actor_id": alice_id,
        "target_id": host_c0_id,
        "edge_id": edge_direct_id,
        "referenced_work_unit_ids": ["w-auth-context"],
        "requires": ["actor_controlled_alice"],
        "adds": ["auth_c0_ready"],
        "is_passive_closure": False,
    }
    act_auth_x = {
        "action_id": "action_auth_x",
        "technique": "obtain_admin_execution_on_host",
        "technique_name": "obtain_admin_execution_on_host",
        "actor_id": alice_id,
        "target_id": otherhost_x_id,
        "referenced_work_unit_ids": ["w-auth-otherhost"],
        "requires": ["actor_controlled_alice"],
        "adds": ["auth_x_ready", "admin_control_host"],
        "is_passive_closure": False,
    }
    query_neg["bound_actions"].extend([act_auth_c0, act_auth_x])
    query_neg["facts_ledger"]["predicate_layers"]["auth_c0_ready"] = 3
    query_neg["facts_ledger"]["predicate_layers"]["auth_x_ready"] = 3

    cand_multi_context = {
        "candidate_id": "cand_multi_context",
        "target_asset_id": otherhost_x_id,
        "bound_action_ids": ["action_auth_c0", "action_auth_x"],
        "scope_binding": copy.deepcopy(pkg_diag["candidates"][0]["scope_binding"]),
        "structural_routes": [
            {
                "route_id": "route_multi_semantic",
                "node_ids": [alice_id],
                "edge_ids": [],
                "provenance_locators": [],
                "action_step_indices": [],
                "semantic_lineage": [
                    {
                        "step_index": 0,
                        "action_id": "action_auth_c0",
                        "technique_id": "obtain_admin_execution_on_host",
                        "actor": alice_id,
                        "source": alice_id,
                        "target": host_c0_id,
                        "origin": "initial_attack_state",
                        "derived_from_step": None,
                        "status": "applicable",
                    },
                    {
                        "step_index": 1,
                        "action_id": "action_auth_x",
                        "technique_id": "obtain_admin_execution_on_host",
                        "actor": alice_id,
                        "source": alice_id,
                        "target": otherhost_x_id,
                        "origin": "initial_attack_state",
                        "derived_from_step": None,
                        "status": "applicable",
                    },
                ],
            }
        ],
    }

    decoded_neg = decode_ranking_query(query_neg)
    res_neg = assess_candidate_program(decoded_neg, cand_multi_context)
    assert res_neg["program"] == ["w-auth-context", "w-auth-otherhost"]
    assert res_neg["effort"] == 2, "Distinct context work units must not be deduplicated"


def test_week4_unrated_effort_preserves_incomparability():
    """Verify ADR-0013 Section 4: unrated effort cannot break ties, preserving incomparability."""
    cand_rated = {
        "candidate_id": "cand_rated",
        "status": "feasible",
        "impact": "High",
        "likelihood_interval": ["1/2", "1/2"],
        "effort_status": "rated",
        "effort": 2,
    }
    cand_unrated = {
        "candidate_id": "cand_unrated",
        "status": "feasible",
        "impact": "High",
        "likelihood_interval": ["1/2", "1/2"],
        "effort_status": "unrated",
        "effort": None,
    }

    # Feasible candidates with identical (I, P) but unrated effort cannot tie-break -> INCOMPARABLE
    verdict = scoped_preference(cand_rated, cand_unrated)
    assert verdict == ScopedPreferenceVerdict.INCOMPARABLE

    verdict_rev = scoped_preference(cand_unrated, cand_rated)
    assert verdict_rev == ScopedPreferenceVerdict.INCOMPARABLE

    # Conversely, if a candidate has unfeasible gate status, preference returns NOT_ELIGIBLE
    cand_blocked = {**cand_rated, "status": "blocked"}
    assert scoped_preference(cand_rated, cand_blocked) == ScopedPreferenceVerdict.NOT_ELIGIBLE


def test_week4_diagnostics_fail_closed_partitioning():
    """Verify diagnostics partitioning for blocked, unknown, and unrated categories."""
    pkg = load_package("synthetic-a2-diagnostics.json")
    result = evaluate_package(pkg)

    diag = result["diagnostics"]
    assert len(diag) == 6, "Expected exactly 6 diagnostic candidates"

    # 1. Blocked gate
    assert "cand_blocked_firewall" in diag
    assert "blocked" in diag["cand_blocked_firewall"]["reasons"]
    assert diag["cand_blocked_firewall"]["assessment"]["status"] == "blocked"

    # 2. Unknown gate
    assert "cand_unknown_service" in diag
    assert "unknown" in diag["cand_unknown_service"]["reasons"]
    assert diag["cand_unknown_service"]["assessment"]["status"] == "unknown"

    # 3. Missing likelihood basis on observed gates
    assert "cand_missing_likelihood_basis" in diag
    assert "likelihood_unrated" in diag["cand_missing_likelihood_basis"]["reasons"]
    assert diag["cand_missing_likelihood_basis"]["assessment"]["status"] == "feasible"
    assert diag["cand_missing_likelihood_basis"]["assessment"]["effort"] == 5

    # 4. Declared runtime assumption gate with unrated likelihood basis
    assert "cand_assumed_gate_unrated_basis" in diag
    assert "likelihood_unrated" in diag["cand_assumed_gate_unrated_basis"]["reasons"]
    assert diag["cand_assumed_gate_unrated_basis"]["assessment"]["status"] == "feasible"

    # 5. Unrated effort friction unit
    assert "cand_unrated_effort" in diag
    cand_unrated_eff = diag["cand_unrated_effort"]["assessment"]
    assert cand_unrated_eff["effort_status"] == "unrated"
    assert cand_unrated_eff["effort"] is None
    assert "w-unrated-friction" in cand_unrated_eff["unrated_work_units"]

    # 6. Unrated impact consequence:
    # Action targets OTHERHOST_X_ID with scoped work units w-auth-otherhost (1) and
    # w-direct-admin-otherhost (4). Effort is 5, likelihood is [1/4, 1/4], impact is unrated (None).
    assert "cand_unrated_impact" in diag
    cand_unrated_imp = diag["cand_unrated_impact"]["assessment"]
    assert "impact_unrated" in diag["cand_unrated_impact"]["reasons"]
    assert cand_unrated_imp["impact"] is None
    assert cand_unrated_imp["impact_status"] == "unrated"
    assert cand_unrated_imp["effort"] == 5
    assert cand_unrated_imp["effort_status"] == "rated"
    assert cand_unrated_imp["likelihood_interval"] == ["1/4", "1/4"]
    assert cand_unrated_imp["likelihood_status"] == "rated"

    # Pareto frontier is empty because all candidates are in diagnostics
    assert result["pareto_frontier"] == []

    # Min-Effort selects the feasible candidate with minimum rated effort.
    # Feasible candidates with rated effort are cand_assumed_gate_unrated_basis (effort 5),
    # cand_missing_likelihood_basis (effort 5), and cand_unrated_impact (effort 5).
    # Deterministic alphabetical tie-breaker selects cand_assumed_gate_unrated_basis with effort 5.
    min_eff = result["min_effort_to_da_baseline"]
    assert min_eff["best_candidate_id"] == "cand_assumed_gate_unrated_basis"
    assert min_eff["minimum_effort_value"] == 5
    assert min_eff["associated_impact"] == "High"


def test_week4_evaluator_actual_results_match():
    """Verify actual-evaluator-results.json matches live evaluator runs deeply."""
    actual_saved = load_package("actual-evaluator-results.json")

    for pkg_name, key in [
        ("synthetic-a2-e.json", "synthetic-a2-e"),
        ("synthetic-a2-t.json", "synthetic-a2-t"),
        ("synthetic-a2-ties.json", "synthetic-a2-ties"),
        ("synthetic-a2-diagnostics.json", "synthetic-a2-diagnostics"),
    ]:
        pkg = load_package(pkg_name)
        live_result = evaluate_package(pkg)
        saved_result = actual_saved[key]

        # Deep equality across full roundtrip result
        assert live_result == saved_result, f"Full result divergence in {key}"
        assert live_result["pareto_frontier"] == saved_result["pareto_frontier"]
        assert live_result["min_effort_to_da_baseline"] == saved_result["min_effort_to_da_baseline"]
        assert live_result["eligible_candidates"] == saved_result["eligible_candidates"]
        assert live_result["diagnostics"] == saved_result["diagnostics"]


def test_week4_cli_roundtrip(tmp_path: Path):
    """Verify ranking CLI executes successfully on Week 4 package."""
    input_file = RATINGS_DIR / "synthetic-a2-e.json"
    output_file = tmp_path / "cli-result.json"

    exit_code = run_ranking_cli(["--input", str(input_file), "--output", str(output_file)])
    assert exit_code == 0
    assert output_file.exists()

    cli_data = json.loads(output_file.read_text(encoding="utf-8"))
    assert "pareto_frontier" in cli_data
    assert set(cli_data["pareto_frontier"]) == {
        "cand_direct",
        "cand_member_direct",
        "cand_member_inherited",
    }
    assert cli_data["min_effort_to_da_baseline"]["minimum_effort_value"] == 2


def test_week4_read_only_verify_mode():
    """Verify scripts/research/week4_scoring_eval.py --verify is strictly read-only."""
    artifacts = list(RATINGS_DIR.glob("*"))
    initial_state = {
        f.name: (f.stat().st_mtime_ns, hashlib.sha256(f.read_bytes()).hexdigest())
        for f in artifacts
    }

    # Run CLI with --verify
    proc = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "research" / "week4_scoring_eval.py"), "--verify"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert "Read-only verification completed successfully" in proc.stdout

    # Verify no files were modified or rewritten
    for f in artifacts:
        current_mtime = f.stat().st_mtime_ns
        current_hash = hashlib.sha256(f.read_bytes()).hexdigest()
        orig_mtime, orig_hash = initial_state[f.name]
        assert current_hash == orig_hash, f"File {f.name} content modified during --verify"
        assert current_mtime == orig_mtime, f"File {f.name} mtime modified during --verify"

    # Also run programmatic verify_existing_artifacts
    summary = verify_existing_artifacts()
    assert summary["overall_status"] == "ALL_PASS"


def test_week4_verify_mode_detects_drift_without_overwriting(tmp_path: Path):
    """Verify --verify detects checksum mismatch or result drift without overwriting disk files."""
    ratings_copy = tmp_path / "week4"
    ratings_copy.mkdir()
    for f in RATINGS_DIR.glob("*"):
        (ratings_copy / f.name).write_bytes(f.read_bytes())

    # Case A: Corrupt one package in the temporary copy (checksum mismatch)
    tampered_pkg_path = ratings_copy / "synthetic-a2-e.json"
    pkg_data = json.loads(tampered_pkg_path.read_text(encoding="utf-8"))
    pkg_data["query"]["work_units_ledger"]["w-auth-context"]["computed_cost"] = 999
    tampered_pkg_path.write_text(json.dumps(pkg_data, indent=2), encoding="utf-8")

    with pytest.raises(AssertionError) as exc_info:
        verify_existing_artifacts(ratings_dir=ratings_copy)
    assert "Checksum mismatch" in str(exc_info.value)
    # Ensure corrupted file was NOT repaired or overwritten
    assert (
        json.loads(tampered_pkg_path.read_text(encoding="utf-8"))["query"]["work_units_ledger"][
            "w-auth-context"
        ]["computed_cost"]
        == 999
    )

    # Restore valid package content
    tampered_pkg_path.write_bytes((RATINGS_DIR / "synthetic-a2-e.json").read_bytes())

    # Case B: Tamper saved actual evaluator results and update manifest checksum to match
    tampered_results = ratings_copy / "actual-evaluator-results.json"
    res_data = json.loads(tampered_results.read_text(encoding="utf-8"))
    res_data["synthetic-a2-e"]["pareto_frontier"] = ["tampered_candidate"]
    tampered_results.write_text(json.dumps(res_data, indent=2), encoding="utf-8")

    manifest_file = ratings_copy / "manifest.sha256"
    new_hash = hashlib.sha256(tampered_results.read_bytes()).hexdigest()
    lines = [line for line in manifest_file.read_text(encoding="utf-8").splitlines() if line]
    updated_lines = [
        f"{new_hash}  docs/research/ratings/week4/actual-evaluator-results.json"
        if "actual-evaluator-results.json" in line
        else line
        for line in lines
    ]
    manifest_file.write_text("\n".join(updated_lines) + "\n", encoding="utf-8")

    with pytest.raises(AssertionError) as exc_drift:
        verify_existing_artifacts(ratings_dir=ratings_copy)
    assert "Pareto frontier mismatch" in str(exc_drift.value)
    # Ensure drifted result file was NOT overwritten or repaired
    assert json.loads(tampered_results.read_text(encoding="utf-8"))["synthetic-a2-e"][
        "pareto_frontier"
    ] == ["tampered_candidate"]
