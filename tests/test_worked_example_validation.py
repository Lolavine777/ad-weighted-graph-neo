"""Unit test suite for Issue #142 reproducible validation research script.

Tests all experiments, hand-worked example verifications, sensitivity analysis,
closure cost invariance, dynamic state & gate evaluation, Dijkstra vs exhaustive
graph search oracle, edge filtering failure, action packaging, and CLI execution.

Run with:
    uv run pytest tests/test_worked_example_validation.py
"""

from __future__ import annotations

import hashlib
import itertools
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

from scripts.research import worked_example_validation as wev
from scripts.research.worked_example_validation import (
    Edge,
    demonstrate_action_packaging_degradation,
    demonstrate_edge_filter_failure,
    dijkstra_search,
    evaluate_dynamic_modes,
    evaluate_gate_truth_table,
    exhaustive_search,
    rank_attack_paths,
    run_all_validations,
    verify_snapshot_data,
)


def permutation_program_oracle(initial, goal, actions, budget):
    """Independent enumeration order; shared synthetic semantics, not an AD oracle."""
    programs = set()
    for length in range(len(actions) + 1):
        for sequence in itertools.permutations(actions, length):
            state = set(initial)
            program = ()
            valid = True
            for action in sequence:
                if goal <= state or not action.requires <= state or action.adds <= state:
                    valid = False
                    break
                state.update(action.adds)
                program = tuple(dict.fromkeys(program + action.units))
            if valid and goal <= state and len(program) <= budget:
                programs.add(program)
    return programs


class ScopedProposalTests(unittest.TestCase):
    def test_frontier_partitions_insufficient_evidence(self):
        rated = {
            "status": "feasible",
            "impact": "High",
            "likelihood_interval": (0.8, 0.8),
            "effort": 3,
        }
        candidates = {
            "rated": rated,
            "blocked": {**rated, "status": "blocked"},
            "unknown": {**rated, "status": "unknown"},
            "likelihood_missing": {**rated, "likelihood_interval": None},
            "impact_missing": {**rated, "impact": None},
            "both_missing": {**rated, "impact": None, "likelihood_interval": None},
        }
        partition = wev.scoped_frontier(candidates)
        self.assertEqual(partition["frontier"], ["rated"])
        self.assertEqual(partition["eligible"], {"rated": rated})
        self.assertEqual(set(partition["diagnostics"]), set(candidates) - {"rated"})
        for name, diagnostic in partition["diagnostics"].items():
            self.assertEqual(diagnostic["assessment"], candidates[name])
            self.assertTrue(diagnostic["reasons"])
            self.assertEqual(wev.scoped_preference(rated, candidates[name]), "not_eligible")
            self.assertEqual(wev.scoped_preference(candidates[name], rated), "not_eligible")
        self.assertEqual(
            set(partition["diagnostics"]["both_missing"]["reasons"]),
            {"impact_unrated", "likelihood_unrated"},
        )
        self.assertEqual(wev.scoped_frontier({})["frontier"], [])
        self.assertEqual(wev.scoped_frontier({"unknown": candidates["unknown"]})["frontier"], [])

    def test_unrated_ledger_effort_preserves_risk_and_unresolved_point_ties(self):
        reset, activate, _, _ = wev.build_path_1_seamless_reset().steps
        bounds = {("reset",): (0.8, 0.9), ("reset", "activate"): (0.6, 0.7)}
        result = wev.assess_scoped_program(
            [("reset",), ("reset", "activate")],
            {"reset": reset, "activate": None},
            bounds,
        )
        self.assertIsNone(result["nominal_effort"])
        self.assertIsNone(result["effort"])
        self.assertEqual(result["effort_status"], "unrated")
        self.assertEqual(result["unrated_work_units"], ("activate",))
        self.assertAlmostEqual(result["likelihood_interval"][0], 0.48)
        blocked = wev.assess_scoped_program(
            [("reset", "activate")],
            {"reset": reset, "activate": None},
            bounds,
            (False,),
        )
        self.assertEqual((blocked["status"], blocked["effort_status"]), ("blocked", "ineligible"))
        self.assertIsNone(blocked["nominal_effort"])
        self.assertIsNone(blocked["likelihood_interval"])
        rated = {
            "status": "feasible",
            "impact": "High",
            "likelihood_interval": (0.8, 0.8),
            "effort": 3,
        }
        unrated = {**rated, "effort": None}
        for a, b in ((rated, unrated), (unrated, rated), (unrated, unrated)):
            self.assertEqual(wev.scoped_preference(a, b), "incomparable")
        self.assertEqual(
            wev.scoped_frontier({"rated": rated, "unrated": unrated})["frontier"],
            ["rated", "unrated"],
        )
        weaker = {**unrated, "likelihood_interval": (0.2, 0.2)}
        self.assertEqual(wev.scoped_preference(unrated, weaker), "a")
        empty = wev.assess_scoped_program([()], {}, {})
        self.assertEqual((empty["effort"], empty["effort_status"]), (0, "rated"))
        with self.assertRaises(KeyError):
            wev.assess_scoped_program([("missing",)], {}, {})

    def test_impact_rating_is_independent_of_security_labels(self):
        self.assertEqual(wev.IMPACT_ORDINAL, {"Low": 1, "Medium": 2, "High": 3, "Critical": 4})
        critical = {
            "impact": "Critical",
            "security_labels": ["CrownJewel"],
            "status": "feasible",
            "likelihood_interval": (0.8, 0.8),
            "effort": 3,
        }
        high = {**critical, "impact": "High", "security_labels": ["Tier0"]}
        self.assertEqual(wev.scoped_preference(critical, high), "a")
        # Relabeling either target cannot change an independently rated consequence.
        self.assertEqual(
            wev.scoped_preference(
                {**critical, "security_labels": ["Tier0"]},
                {**high, "security_labels": ["CrownJewel"]},
            ),
            "a",
        )
        for impact in ("Tier0", "Tier1", "CrownJewel", None):
            unrated = {**critical, "impact": impact, "security_labels": ["Tier0", "CrownJewel"]}
            self.assertEqual(wev.scoped_preference(unrated, high), "not_eligible")
            self.assertEqual(wev.scoped_preference(high, unrated), "not_eligible")
        unrated.pop("impact")
        self.assertEqual(wev.scoped_preference(unrated, high), "not_eligible")
        experiment = wev.run_experiment_1_ranking_tradeoff()
        self.assertEqual(experiment["path_a"]["impact"], "Critical")
        self.assertEqual(experiment["path_a"]["ad_technical_tier"], "Tier1")
        self.assertEqual(experiment["path_a"]["security_labels"], ["CrownJewel"])
        self.assertEqual(experiment["path_b"]["impact"], "High")
        self.assertEqual(experiment["path_b"]["security_labels"], ["Tier0"])

    def test_zero_prefix_needs_no_later_conditional_bound(self):
        reset, activate, _, _ = wev.build_path_1_seamless_reset().steps
        result = wev.assess_scoped_program(
            [("reset", "activate")],
            {"reset": reset, "activate": activate},
            {("reset",): (0.0, 0.0)},
        )
        self.assertEqual(result["likelihood_interval"], (0, 0))
        self.assertEqual(result["nominal_effort"], 3)

    def test_exact_point_products_do_not_create_order_preferences(self):
        unit = wev.build_path_1_seamless_reset().steps[0]
        units = dict.fromkeys(("a", "b", "c"), unit)
        conditional_values = {"a": 0.2, "b": 0.3, "c": 0.4}
        bounds = {
            program[:length]: (conditional_values[program[length - 1]],) * 2
            for program in itertools.permutations(units)
            for length in range(1, 4)
        }
        assessments = [
            {**wev.assess_scoped_program([program], units, bounds), "impact": "High"}
            for program in itertools.permutations(units)
        ]
        for assessment in assessments:
            self.assertEqual(wev.scoped_preference(assessments[0], assessment), "tie")
        self.assertAlmostEqual(assessments[0]["likelihood_interval"][0], 0.024)

    def test_conditional_composition_shared_work_and_packaging(self):
        reset, activate, closure, _ = wev.build_path_1_seamless_reset().steps
        units = {"reset": reset, "activate": activate}
        bounds = {("reset",): (0.8, 0.9), ("reset", "activate"): (0.6, 0.7)}
        split = wev.assess_scoped_program([("reset",), ("activate",), ()], units, bounds)
        merged = wev.assess_scoped_program([("reset", "activate")], units, bounds)
        nested = wev.assess_scoped_program([("reset",), ("activate",), (), (), ()], units, bounds)
        reused = wev.assess_scoped_program([("reset",), ("reset", "activate")], units, bounds)
        self.assertEqual(split, merged)
        self.assertEqual(split, nested)
        self.assertEqual(split, reused)
        self.assertEqual(split["effort"], 3)
        self.assertEqual(closure.cost(), 0)
        self.assertAlmostEqual(split["likelihood_interval"][0], 0.48)
        self.assertAlmostEqual(split["likelihood_interval"][1], 0.63)
        # Missing full-history assessment cannot fall back to a marginal for activate.
        incomplete = {("reset",): (0.8, 0.9), ("activate",): (0.6, 0.7)}
        self.assertIsNone(
            wev.assess_scoped_program([("reset", "activate")], units, incomplete)[
                "likelihood_interval"
            ]
        )
        for gates, status in [
            ((True, "Unknown"), "unknown"),
            (("Unknown", False, True), "blocked"),
        ]:
            result = wev.assess_scoped_program([("reset", "activate")], units, bounds, gates)
            self.assertEqual(result["status"], status)
            self.assertIsNone(result["effort"])
            self.assertIsNone(result["likelihood_interval"])
            self.assertEqual(result["nominal_effort"], 3)
        for interval in [(0.9, 0.2), (-0.1, 0.5), (0.0, float("nan")), (0.0, 1.1)]:
            with self.assertRaises(ValueError):
                wev.assess_scoped_program([("reset",)], units, {("reset",): interval})

    def test_robust_pareto_tradeoff_overlap_and_effort_ties(self):
        def assessment(impact, bounds, effort=3, status="feasible"):
            return {
                "impact": impact,
                "likelihood_interval": bounds,
                "effort": effort,
                "status": status,
            }

        critical = assessment("Critical", (0.1, 0.2))
        high = assessment("High", (0.8, 0.9))
        self.assertEqual(wev.scoped_preference(critical, high), "incomparable")
        self.assertEqual(wev.scoped_preference(high, critical), "incomparable")
        weaker = assessment("High", (0.05, 0.09))
        self.assertEqual(wev.scoped_preference(critical, weaker), "a")
        self.assertEqual(wev.scoped_preference(weaker, critical), "b")
        overlapping = assessment("Critical", (0.15, 0.4), 1)
        self.assertEqual(wev.scoped_preference(critical, overlapping), "incomparable")
        # Even identical non-point intervals do not prove equal latent probability.
        self.assertEqual(
            wev.scoped_preference(critical, assessment("Critical", (0.1, 0.2), 1)), "incomparable"
        )
        exact = assessment("Critical", (0.6, 0.6))
        self.assertEqual(wev.scoped_preference(exact, assessment("Critical", (0.6, 0.6), 4)), "a")
        self.assertEqual(wev.scoped_preference(exact, exact), "tie")
        self.assertEqual(
            wev.scoped_preference(exact, assessment("Critical", None, status="unknown")),
            "not_eligible",
        )

    def test_bounded_search_matches_independent_oracle_without_node_pruning(self):
        action = wev.ResearchAction
        steps = [
            action("prepare", frozenset({"start"}), frozenset({"prepared"}), ("prepare",)),
            action("a", frozenset({"prepared"}), frozenset({"a"}), ("a",)),
            action("b", frozenset({"prepared"}), frozenset({"b"}), ("b",)),
            action("finish", frozenset({"a", "b"}), frozenset({"goal"}), ("finish",)),
            action("cheap_low", frozenset({"start"}), frozenset({"goal"}), ("cheap_low",)),
            action("cycle", frozenset({"prepared"}), frozenset({"start"}), ()),
        ]
        for budget in (0, 1, 3, 4):
            found = wev.bounded_programs({"start"}, {"goal"}, steps, budget)
            oracle = permutation_program_oracle({"start"}, {"goal"}, steps, budget)
            self.assertEqual(set(found["programs"]), oracle)
            self.assertEqual(found["truncated"], budget < 4)
        self.assertEqual(len(wev.bounded_programs({"start"}, {"goal"}, steps, 4)["programs"]), 8)
        self.assertEqual(wev.bounded_programs({"goal"}, {"goal"}, steps, 0)["programs"], [()])
        for budget in (-1, True):
            with self.assertRaises(ValueError):
                wev.bounded_programs({"start"}, {"goal"}, steps, budget)
        # Same goal/work boundary, with prerequisites preserved in the merged packet.
        split = [
            action("reset", frozenset({"start"}), frozenset({"password"}), ("reset",)),
            action(
                "auth", frozenset({"password", "auth_allowed"}), frozenset({"usable"}), ("auth",)
            ),
            action("closure", frozenset({"usable"}), frozenset({"goal"}), ()),
        ]
        merged = [
            action(
                "reset_auth",
                frozenset({"start", "auth_allowed"}),
                frozenset({"usable"}),
                ("reset", "auth"),
            ),
            split[-1],
        ]
        nested = split[:-1] + [
            action("m1", frozenset({"usable"}), frozenset({"g1"}), ()),
            action("m2", frozenset({"g1"}), frozenset({"g2"}), ()),
            action("m3", frozenset({"g2"}), frozenset({"goal"}), ()),
        ]
        for context in ({"start", "auth_allowed"}, {"start"}):
            for representation in (split, merged, nested):
                found = wev.bounded_programs(context, {"goal"}, representation, 2)
                self.assertEqual(
                    set(found["programs"]),
                    permutation_program_oracle(context, {"goal"}, representation, 2),
                )
                self.assertEqual(
                    found["programs"], [("reset", "auth")] if "auth_allowed" in context else []
                )

    def test_scoped_experiment_is_reproducible_and_does_not_claim_support(self):
        report = wev.run_experiment_6_scoped_proposal()
        self.assertEqual(report["status"], "PASS")
        self.assertEqual(report["model_verdict"], "Insufficient Evidence")
        self.assertEqual(report["search"]["oracle_programs"], report["search"]["bounded_programs"])
        self.assertEqual(report["search"]["frontier"], ["shared_ab", "shared_ba"])
        self.assertEqual(report["search"]["min_effort"], "cheap_low")
        self.assertEqual(report["shared_preparation"]["effort"], 8)
        self.assertAlmostEqual(report["shared_preparation"]["likelihood_interval"][0], 0.648)
        for name in ("blocked", "unknown"):
            assessment = report["evidence_partition"]["diagnostics"][name]["assessment"]
            self.assertIsNone(assessment["effort"])
            self.assertIsNone(assessment["likelihood_interval"])
            self.assertEqual(assessment["effort_status"], "ineligible")
            self.assertEqual(assessment["nominal_effort"], 8)
        self.assertEqual(wev.run_all_validations()["experiment_6"], report)


class WorkedExampleValidationTests(unittest.TestCase):
    """Test suite covering the research experiments, graph algorithms, and validation CLI."""

    def test_hand_example_step_by_step_values_and_zero_deviation(self):
        """Test Experiment (a): Hand-worked Example Verification against Section 10."""
        result = wev.verify_hand_worked_examples()
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["total_deviation"], 0)

        # Path 1 (Reset) checks
        self.assertEqual(result["path1_s2"]["cost"], 3)
        self.assertEqual(result["path1_s2"]["likelihood"], "Medium")
        self.assertIsNone(result["path1_s3"]["cost"])
        self.assertEqual(result["path1_s3"]["nominal_cost"], 6)
        self.assertIsNone(result["path1_s3"]["realized_cost"])
        self.assertEqual(result["path1_s3"]["likelihood"], "Unknown")

        # Path 2 (Session) checks
        self.assertEqual(result["path2_s2"]["cost"], 3)
        self.assertEqual(result["path2_s2"]["likelihood"], "High")
        self.assertIsNone(result["path2_s3"]["cost"])
        self.assertEqual(result["path2_s3"]["nominal_cost"], 6)
        self.assertIsNone(result["path2_s3"]["realized_cost"])
        self.assertEqual(result["path2_s3"]["likelihood"], "Unknown")

        # Verify step-by-step details for Path 1
        p1_steps = [s for s in result["step_verifications"] if s["path"] == "Path 1"]
        self.assertEqual(len(p1_steps), 4)

        # Step 1: genericall_reset_password (T1=1, T2=3, C=2, P=Medium, T3=High)
        self.assertEqual(p1_steps[0]["t1"], 1)
        self.assertEqual(p1_steps[0]["t2"], 3)
        self.assertEqual(p1_steps[0]["cost"], 2)
        self.assertEqual(p1_steps[0]["likelihood"], "Medium")
        self.assertEqual(p1_steps[0]["t3"], "High (Event 4724)")
        self.assertEqual(p1_steps[0]["deviation"], 0)

        # Step 2: activate_identity (T1=1, T2=2, C=1, P=Medium, T3=Med)
        self.assertEqual(p1_steps[1]["t1"], 1)
        self.assertEqual(p1_steps[1]["t2"], 2)
        self.assertEqual(p1_steps[1]["cost"], 1)
        self.assertEqual(p1_steps[1]["likelihood"], "Medium")
        self.assertEqual(p1_steps[1]["t3"], "Medium (Event 4624)")
        self.assertEqual(p1_steps[1]["deviation"], 0)

        # Step 3: propagate_membership (T1=1, T2=1, C=0, P=High, T3=Low)
        self.assertEqual(p1_steps[2]["t1"], 1)
        self.assertEqual(p1_steps[2]["t2"], 1)
        self.assertEqual(p1_steps[2]["cost"], 0)
        self.assertEqual(p1_steps[2]["likelihood"], "High")
        self.assertEqual(p1_steps[2]["deviation"], 0)

        # Step 4: dcsync_krbtgt (T1=2, T2=3, C=3, P=Unknown, T3=High)
        self.assertEqual(p1_steps[3]["t1"], 2)
        self.assertEqual(p1_steps[3]["t2"], 3)
        self.assertEqual(p1_steps[3]["cost"], 3)
        self.assertEqual(p1_steps[3]["likelihood"], "Unknown")
        self.assertEqual(p1_steps[3]["deviation"], 0)

        # Verify ranking at S2 in Scenario Mode: Path 2 > Path 1
        self.assertTrue(result["ranking_correct"])
        self.assertEqual(
            result["ranking_at_s2"],
            ["Path 2 (Synthetic HasSession)", "Path 1 (SEAMLESS Reset)"],
        )

    def test_experiment_1_lexicographic_vs_tradeoff_models(self):
        """Test Experiment 1: Lexicographic Model vs Tradeoff Models."""
        result = wev.run_experiment_1_ranking_tradeoff()
        self.assertEqual(result["status"], "PASS")

        # Independently rated consequences: Path A (Critical, Low) > Path B (High, High).
        self.assertEqual(result["lexicographic_winner"], "Path A")

        # Expected Risk ranks Path B (Score 9) > Path A (Score 4)
        self.assertEqual(result["expected_risk_winner"], "Path B")

        # Multi-attribute utility ranks Path B (0.875) > Path A (0.6667)
        self.assertEqual(result["utility_winner"], "Path B")

        # Confirm disagreement between models
        self.assertTrue(result["rank_disagreement"])

        # Check comparison table values
        comp = {row["attribute"]: row for row in result["comparison_table"]}
        self.assertEqual(comp["Target Impact (I)"]["path_a"], "Critical (I=4)")
        self.assertEqual(comp["Target Impact (I)"]["path_b"], "High (I=3)")
        self.assertEqual(comp["Likelihood (P)"]["path_a"], "Low (P=1)")
        self.assertEqual(comp["Likelihood (P)"]["path_b"], "High (P=3)")
        self.assertEqual(comp["Effort Cost (C)"]["path_a"], "3")
        self.assertEqual(comp["Effort Cost (C)"]["path_b"], "3")

    def test_experiment_2_effort_sensitivity_and_rank_reversal(self):
        """Test Experiment 2: Effort Sensitivity within Equal Strata and Rank Reversal."""
        result = wev.run_experiment_2_effort_sensitivity()
        self.assertEqual(result["status"], "PASS")

        # Invariant: C_closure == 0 in all valid formula variants
        self.assertTrue(result["closure_invariants_pass"])

        # Check formula variants
        variants = {r["formula_key"]: r for r in result["variant_results"]}

        # Base formula: C1 = T1 + T2 - 2 -> 3A=2, 3B=2 (Tie)
        self.assertEqual(variants["base"]["path_3a_total"], 2)
        self.assertEqual(variants["base"]["path_3b_total"], 2)
        self.assertEqual(variants["base"]["closure_cost"], 0)
        self.assertIn("Tie", variants["base"]["preferred_path"])

        # Max formula: C2 = max(T1, T2) - 1 -> 3A=2, 3B=2 (Tie)
        self.assertEqual(variants["max"]["path_3a_total"], 2)
        self.assertEqual(variants["max"]["path_3b_total"], 2)
        self.assertEqual(variants["max"]["closure_cost"], 0)
        self.assertIn("Tie", variants["max"]["preferred_path"])

        # Tool-weighted formula: C3 = 2*T1 + T2 - 3 -> 3A=4, 3B=2 (Path 3B wins)
        self.assertEqual(variants["tool_weighted"]["path_3a_total"], 4)
        self.assertEqual(variants["tool_weighted"]["path_3b_total"], 2)
        self.assertEqual(variants["tool_weighted"]["closure_cost"], 0)
        self.assertIn("Path 3B", variants["tool_weighted"]["preferred_path"])

        # Friction-weighted formula: C4 = T1 + 2*T2 - 3 -> 3A=2, 3B=4 (Path 3A wins)
        self.assertEqual(variants["friction_weighted"]["path_3a_total"], 2)
        self.assertEqual(variants["friction_weighted"]["path_3b_total"], 4)
        self.assertEqual(variants["friction_weighted"]["closure_cost"], 0)
        self.assertIn("Path 3A", variants["friction_weighted"]["preferred_path"])

        # Rank reversal verified between Tool-weighted and Friction-weighted
        self.assertTrue(result["rank_reversal_observed"])

    def test_experiment_3_closure_invariance_and_semantic_equivalence(self):
        """Test Experiment 3: Closure Cost Invariance and Semantic Equivalence."""
        result = wev.run_experiment_3_closure_invariance()
        self.assertEqual(result["status"], "PASS")

        # 1-hop vs 3-hop nested closure under normalized formula has identical cost
        self.assertEqual(result["normalized_1hop_cost"], 3)
        self.assertEqual(result["normalized_3hop_cost"], 3)
        self.assertTrue(result["normalized_invariant"])

        # Non-normalized formula causes artificial inflation of +2
        self.assertEqual(result["raw_1hop_cost"], 3)
        self.assertEqual(result["raw_3hop_cost"], 5)
        self.assertEqual(result["raw_inflation_delta"], 2)

        # Packaging invariance: split (2 steps) vs merged (1 step) has identical cost (3 vs 3)
        self.assertEqual(result["packaging_split_cost"], 3)
        self.assertEqual(result["packaging_merged_cost"], 3)
        self.assertEqual(result["packaging_split_actions"], 2)
        self.assertEqual(result["packaging_merged_actions"], 1)
        self.assertTrue(result["packaging_invariant"])

    def test_experiment_4_uncertainty_propagation(self):
        """Test Experiment 4: Uncertainty Propagation with Gate O and Evaluation Modes."""
        result = wev.run_experiment_4_uncertainty_propagation()
        self.assertEqual(result["status"], "PASS")

        # Gate O Unknown -> S3 path likelihood is Unknown
        self.assertEqual(result["path1_s3_likelihood"], "Unknown")
        self.assertEqual(result["path2_s3_likelihood"], "Unknown")
        self.assertTrue(result["truth_table_passed"])
        self.assertTrue(result["propagation_correct"])
        self.assertTrue(result["gate_truth_table_passed"])
        self.assertEqual(result["gate_truth_table_count"], 27)

        # Check dual modes
        modes = result["modes_evaluation"]
        ev_mode = modes["evidence_only_mode"]
        self.assertFalse(ev_mode["foothold_proven"])
        self.assertFalse(ev_mode["gate_a_proven"])
        self.assertIn("Unsupported", ev_mode["checkpoint_s2_status"])
        self.assertIn("Unsupported", ev_mode["checkpoint_s3_status"])

        sc_mode = modes["scenario_mode"]
        self.assertTrue(sc_mode["foothold_proven"])
        self.assertTrue(sc_mode["gate_a_proven"])
        self.assertIn("Reached", sc_mode["checkpoint_s2_status"])
        self.assertIn("Unsupported", sc_mode["checkpoint_s3_status"])

    def test_experiment_5_length_degradation_and_dijkstra_compatibility(self):
        """Test Experiment 5: Path Length Degradation and Dijkstra Compatibility."""
        result = wev.run_experiment_5_length_degradation_dijkstra()
        self.assertEqual(result["status"], "PASS")

        # Bottleneck indirection: 1-step High vs 10-step High both equal High
        self.assertTrue(result["bottleneck_indifferent"])

        # Length discount model: active steps degrade from High -> Medium -> Low
        table = result["length_degradation_table"]
        self.assertEqual(table[0]["active_steps"], 1)
        self.assertEqual(table[0]["ordinal_stratum"], "High")
        self.assertEqual(table[0]["degraded_probability"], 0.90)

        self.assertEqual(table[2]["active_steps"], 3)
        self.assertEqual(table[2]["ordinal_stratum"], "Medium")

        self.assertEqual(table[6]["active_steps"], 7)
        self.assertEqual(table[6]["ordinal_stratum"], "Low")

        self.assertEqual(table[9]["active_steps"], 10)
        self.assertEqual(table[9]["ordinal_stratum"], "Low")

        # Passive closure invariance: passive steps do not degrade likelihood
        self.assertTrue(result["passive_invariance_maintained"])

        # Dijkstra compatibility: unconstrained non-linear search violates Bellman optimality
        self.assertTrue(result["bellman_violation_demonstrated"])
        self.assertTrue(result["stratified_dijkstra_success"])

    def test_actual_dijkstra_vs_exhaustive_search_counterexample_and_stratified(self):
        """Test Dijkstra search vs exhaustive oracle on non-linear and stratified cases."""
        # 1. Non-linear counterexample graph: C / prod(P)
        counterexample_graph: dict[str, list[Edge]] = {
            "S": [
                Edge("S", "X", cost=1.0, likelihood=0.5, name="S->X (fast but risky)"),
                Edge("S", "B", cost=1.0, likelihood=0.95, name="S->B"),
            ],
            "B": [
                Edge("B", "X", cost=1.0, likelihood=0.95, name="B->X"),
            ],
            "X": [
                Edge("X", "T", cost=6.0, likelihood=0.5, name="X->T"),
            ],
            "T": [],
        }

        dijk_res = dijkstra_search(counterexample_graph, "S", "T", metric_type="composite_ratio")
        exh_res = exhaustive_search(counterexample_graph, "S", "T", metric_type="composite_ratio")

        self.assertTrue(dijk_res["found"])
        self.assertTrue(exh_res["found"])
        # Dijkstra greedily chose path ['S', 'X', 'T'] with score 28.0
        self.assertEqual(dijk_res["path"], ["S", "X", "T"])
        self.assertAlmostEqual(dijk_res["score"], 28.0)

        # Exhaustive oracle proved optimal path is ['S', 'B', 'X', 'T'] with score ~17.7285
        self.assertEqual(exh_res["path"], ["S", "B", "X", "T"])
        self.assertAlmostEqual(exh_res["score"], 17.7285, places=3)

        # Dijkstra greedy choice is strictly suboptimal
        self.assertGreater(dijk_res["score"], exh_res["score"])

        # 2. Stratified Dijkstra case on additive C >= 0 (stratum filter min_likelihood=0.75)
        stratified_graph: dict[str, list[Edge]] = {
            "S": [
                Edge("S", "X", cost=1.0, likelihood=0.5, name="S->X (pruned)"),
                Edge("S", "B", cost=2.0, likelihood=0.95, name="S->B"),
                Edge("S", "C", cost=3.0, likelihood=0.95, name="S->C"),
            ],
            "B": [
                Edge("B", "T", cost=2.0, likelihood=0.95, name="B->T"),
            ],
            "C": [
                Edge("C", "T", cost=0.5, likelihood=0.95, name="C->T"),
            ],
            "X": [
                Edge("X", "T", cost=1.0, likelihood=0.5, name="X->T"),
            ],
            "T": [],
        }

        dijk_strat = dijkstra_search(
            stratified_graph, "S", "T", metric_type="additive_cost", min_likelihood=0.75
        )
        exh_strat = exhaustive_search(
            stratified_graph, "S", "T", metric_type="additive_cost", min_likelihood=0.75
        )

        self.assertTrue(dijk_strat["found"])
        self.assertTrue(exh_strat["found"])
        # Both find the optimal path ['S', 'C', 'T'] with cost 3.5
        self.assertEqual(dijk_strat["path"], ["S", "C", "T"])
        self.assertEqual(exh_strat["path"], ["S", "C", "T"])
        self.assertEqual(dijk_strat["cost"], 3.5)
        self.assertEqual(exh_strat["cost"], 3.5)

    def test_edge_filtering_fails_to_guarantee_path_stratum_under_degradation(self):
        """Test that static edge filtering fails under cumulative degradation."""
        failure_demo = demonstrate_edge_filter_failure()

        self.assertTrue(failure_demo["edges_pass_static_filter"])
        self.assertEqual(failure_demo["cumulative_path_likelihood"], 0.729)
        self.assertEqual(failure_demo["whole_path_stratum"], "Medium")
        # Static filtering failed to guarantee the path remains in High stratum
        self.assertFalse(failure_demo["static_filter_guarantees_stratum"])
        self.assertIn("State-space expansion", failure_demo["remedy"])

    def test_dynamic_gate_truth_table_27_permutations(self):
        """Test dynamic evaluation of all 27 combinations of Gate A, Gate M, and Gate O.

        Enforces Kleene 3-valued logic: False strictly absorbs Unknown.
        Aligns truth table outcomes with AttackPath._evaluate_gates.
        """
        table = evaluate_gate_truth_table()
        self.assertEqual(len(table), 27)

        status_map = {"reached": "feasible", "blocked": "blocked", "unknown": "unknown"}

        for row in table:
            ga = row["gate_a"]
            gm = row["gate_m"]
            go = row["gate_o"]

            # Kleene logic for S2 (prerequisites: Gate A and Gate M)
            s2_gates = [ga, gm]
            if any(g is False for g in s2_gates):
                expected_s2 = "blocked"
            elif any(g == "Unknown" for g in s2_gates):
                expected_s2 = "unknown"
            else:
                expected_s2 = "reached"

            self.assertEqual(row["s2_status"], expected_s2)
            if expected_s2 == "reached":
                self.assertEqual(row["s2_cost"], 3)
                self.assertEqual(row["s2_likelihood"], "Medium")
            else:
                self.assertIsNone(row["s2_cost"])

            # Kleene logic for S3 (prerequisite: S2 and Gate O)
            if expected_s2 == "blocked":
                expected_s3 = "blocked"
            elif expected_s2 == "unknown":
                if go is False:
                    expected_s3 = "blocked"
                else:
                    expected_s3 = "unknown"
            else:  # reached
                if go is True:
                    expected_s3 = "reached"
                elif go is False:
                    expected_s3 = "blocked"
                else:
                    expected_s3 = "unknown"

            self.assertEqual(row["s3_status"], expected_s3)
            if expected_s3 == "reached":
                self.assertEqual(row["s3_cost"], 6)
            else:
                self.assertIsNone(row["s3_cost"])

            # Verify 100% alignment with AttackPath._evaluate_gates
            p1 = wev.build_path_1_seamless_reset()
            p_ctx: dict[str, Any] = {
                "gate_a": ga,
                "gate_m": gm,
                "baseline_assumptions": True,
            }
            if go is True:
                p_ctx["structural_replication_rights"] = True
            else:
                p_ctx["gate_o"] = go
            self.assertEqual(p1.path_status("S2", gate_context=p_ctx), status_map[expected_s2])
            self.assertEqual(p1.path_status("S3", gate_context=p_ctx), status_map[expected_s3])

    def test_dynamic_evidence_only_vs_scenario_mode_evaluation(self):
        """Test dynamic mode evaluation driven by initial factual sets."""
        evidence_facts = {
            "source_a_exists",
            "structural_genericall",
            "structural_memberof",
            "target_krbtgt_exists",
        }
        ev_eval = evaluate_dynamic_modes(evidence_facts)
        self.assertFalse(ev_eval["foothold_proven"])
        self.assertFalse(ev_eval["gate_a_proven"])
        self.assertIn("Unsupported", ev_eval["checkpoint_s1_status"])
        self.assertIn("Unsupported", ev_eval["checkpoint_s2_status"])
        self.assertIn(
            "chua co bang chung da duoc kiem chung ve phan quyen replication",
            ev_eval["checkpoint_s3_status"],
        )

        # Baseline scenario mode includes all reset preconditions
        scenario_facts = {
            "source_a_exists",
            "structural_genericall",
            "structural_memberof",
            "target_krbtgt_exists",
            "source_computer_enabled",
            "target_user_enabled",
            "foothold",
            "password_policy_satisfied",
            "directory_write_available",
            "gate_a_accepted",
            "gate_m_usable",
        }
        sc_eval = evaluate_dynamic_modes(scenario_facts)
        self.assertTrue(sc_eval["foothold_proven"])
        self.assertTrue(sc_eval["gate_a_proven"])
        self.assertIn("Reached (cost=2)", sc_eval["checkpoint_s1_status"])
        self.assertIn("Reached (cost=3, P=Medium)", sc_eval["checkpoint_s2_status"])
        self.assertIn(
            "chua co bang chung da duoc kiem chung ve phan quyen replication",
            sc_eval["checkpoint_s3_status"],
        )

        # Precondition failure tests: missing or false conditions block S1
        for missing_fact in (
            "source_computer_enabled",
            "target_user_enabled",
            "password_policy_satisfied",
            "directory_write_available",
            "foothold",
        ):
            degraded_facts = set(scenario_facts) - {missing_fact}
            deg_eval = evaluate_dynamic_modes(degraded_facts)
            self.assertIn("Unsupported", deg_eval["checkpoint_s1_status"])
            self.assertIn("Unsupported", deg_eval["checkpoint_s2_status"])

    def test_action_packaging_breaks_under_naive_step_counting(self):
        """Test that naive step counting breaks action packaging invariance under degradation."""
        packaging = demonstrate_action_packaging_degradation()
        self.assertEqual(packaging["split_active_steps"], 2)
        self.assertEqual(packaging["split_degraded_p"], 0.81)
        self.assertEqual(packaging["merged_active_steps"], 1)
        self.assertEqual(packaging["merged_degraded_p"], 0.90)
        self.assertFalse(packaging["naive_step_counting_preserves_packaging"])

    def test_seamless_snapshot_verification_if_present(self):
        """Test snapshot verification against real snapshot files using reproducible selectors."""
        raw_dir = Path("data/raw/SEAMLESS")
        manifest_path = Path("data/samples/manifests/seamless-raw-v1.json")
        if raw_dir.is_dir() and manifest_path.is_file():
            snap_res = verify_snapshot_data(raw_dir, manifest_path)
            self.assertEqual(snap_res["status"], "PASS")
            self.assertTrue(snap_res["snapshot_verified"])
            self.assertTrue(snap_res["file_hash_verified"])
            details = snap_res["details"]

            # Verify aliases are used rather than raw identity names
            self.assertEqual(details["source_a"]["alias"], "Source A")
            self.assertTrue(details["source_a"]["found"])
            self.assertTrue(details["source_a"]["enabled"])
            self.assertTrue(details["source_a"]["file_hash_verified"])

            self.assertEqual(details["user_candidate"]["alias"], "User-Candidate")
            self.assertTrue(details["user_candidate"]["found"])
            self.assertTrue(details["user_candidate"]["genericall_from_source_a"])

            self.assertEqual(details["da_group"]["alias"], "Target-Group-DA")
            self.assertTrue(details["da_group"]["found"])
            self.assertTrue(details["da_group"]["user_candidate_is_member"])

            self.assertEqual(details["krbtgt"]["alias"], "Target-User-KRBTGT")
            self.assertTrue(details["krbtgt"]["found"])

            # Inspect Computer.Sessions[] primitive and manifest verification
            self.assertIn("sessions_inspection", details)
            si = details["sessions_inspection"]
            self.assertTrue(si["measured_empty"])
            self.assertEqual(si["source_a_sessions_count"], 0)
            self.assertEqual(si["computers_with_nonempty_sessions"], 0)
            self.assertIn("empty != false", si["caveat"])

            self.assertIn("manifest_verification", details)
            mv = details["manifest_verification"]
            self.assertTrue(mv["all_verified"])
            self.assertEqual(mv["total_files"], len(mv["verified_files"]))

    def test_snapshot_verification_fails_on_hash_mismatch_or_invalid_manifest(self):
        """Test snapshot verification strictly FAILS on hash mismatch or empty manifest."""
        dummy_hash = "0" * 64
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create dummy snapshot fixture files
            raw_dir = Path(tmpdir) / "raw"
            raw_dir.mkdir()
            (raw_dir / "20210920185958_computers.json").write_text(
                json.dumps({"computers": []}), encoding="utf-8"
            )
            (raw_dir / "20210920185958_users.json").write_text(
                json.dumps({"users": []}), encoding="utf-8"
            )
            (raw_dir / "20210920185958_groups.json").write_text(
                json.dumps({"groups": []}), encoding="utf-8"
            )

            # 1. Manifest with corrupted hash
            corrupt_manifest = Path(tmpdir) / "corrupt_manifest.json"
            corrupt_manifest.write_text(
                json.dumps(
                    {
                        "files": [
                            {
                                "relative_path": "20210920185958_computers.json",
                                "sha256": dummy_hash,
                            }
                        ]
                    }
                )
            )

            res = verify_snapshot_data(raw_dir, corrupt_manifest)
            self.assertEqual(res["status"], "FAIL")
            self.assertFalse(res["snapshot_verified"])
            self.assertFalse(res["file_hash_verified"])
            self.assertIn("file_hash_verified", res)
            self.assertIn("details", res)

            # 2. Empty manifest
            empty_manifest = Path(tmpdir) / "empty_manifest.json"
            empty_manifest.write_text(json.dumps({"files": []}))
            res_empty = verify_snapshot_data(raw_dir, empty_manifest)
            self.assertEqual(res_empty["status"], "FAIL")
            self.assertFalse(res_empty["snapshot_verified"])
            self.assertFalse(res_empty["file_hash_verified"])
            self.assertIn("file_hash_verified", res_empty)
            self.assertIn("details", res_empty)

            # 3. Nonexistent manifest
            res_no_manifest = verify_snapshot_data(raw_dir, Path(tmpdir) / "nonexistent.json")
            self.assertEqual(res_no_manifest["status"], "FAIL")
            self.assertFalse(res_no_manifest["snapshot_verified"])
            self.assertFalse(res_no_manifest["file_hash_verified"])
            self.assertIn("file_hash_verified", res_no_manifest)
            self.assertIn("details", res_no_manifest)

            # 4. Nonexistent raw directory
            res_no_raw = verify_snapshot_data(Path(tmpdir) / "nonexistent_dir", corrupt_manifest)
            self.assertEqual(res_no_raw["status"], "FAIL")
            self.assertFalse(res_no_raw["snapshot_verified"])
            self.assertFalse(res_no_raw["file_hash_verified"])
            self.assertIn("file_hash_verified", res_no_raw)
            self.assertIn("details", res_no_raw)

            # 5. Overall pass is False when snapshot fails
            combined = run_all_validations(raw_dir=raw_dir, manifest_path=corrupt_manifest)
            self.assertEqual(combined["overall_status"], "FAIL")
            self.assertFalse(combined["overall_pass"])

            # 6. Regression test: corrupting a non-selected file (e.g. domains.json)
            # causes snapshot verification to FAIL even if core files are present.
            comp_bytes = json.dumps({"computers": []}).encode("utf-8")
            user_bytes = json.dumps({"users": []}).encode("utf-8")
            grp_bytes = json.dumps({"groups": []}).encode("utf-8")
            dom_bytes = json.dumps({"domains": []}).encode("utf-8")

            dom_file = raw_dir / "20210920185958_domains.json"
            dom_file.write_bytes(dom_bytes)

            full_manifest = Path(tmpdir) / "full_manifest.json"
            full_manifest.write_text(
                json.dumps(
                    {
                        "files": [
                            {
                                "relative_path": "20210920185958_computers.json",
                                "sha256": hashlib.sha256(comp_bytes).hexdigest(),
                                "size_bytes": len(comp_bytes),
                            },
                            {
                                "relative_path": "20210920185958_users.json",
                                "sha256": hashlib.sha256(user_bytes).hexdigest(),
                                "size_bytes": len(user_bytes),
                            },
                            {
                                "relative_path": "20210920185958_groups.json",
                                "sha256": hashlib.sha256(grp_bytes).hexdigest(),
                                "size_bytes": len(grp_bytes),
                            },
                            {
                                "relative_path": "20210920185958_domains.json",
                                "sha256": dummy_hash,  # Corrupted hash on non-selected file!
                                "size_bytes": len(dom_bytes),
                            },
                        ]
                    }
                )
            )
            res_corrupt_non_core = verify_snapshot_data(raw_dir, full_manifest)
            self.assertEqual(res_corrupt_non_core["status"], "FAIL")
            self.assertFalse(res_corrupt_non_core["file_hash_verified"])
            self.assertFalse(res_corrupt_non_core["snapshot_verified"])
            failed_files = res_corrupt_non_core["details"]["manifest_verification"]["failed_files"]
            self.assertIn("20210920185958_domains.json", failed_files)

    def test_reproducible_selectors_purge_raw_ad_identities(self):
        """Test that snapshot details and validation outputs do not expose raw AD identities."""
        raw_dir = Path("data/raw/SEAMLESS")
        manifest_path = Path("data/samples/manifests/seamless-raw-v1.json")
        if raw_dir.is_dir() and manifest_path.is_file():
            snap_res = verify_snapshot_data(raw_dir, manifest_path)
            res_str = json.dumps(snap_res)

            # Purge assertions: raw domain, computer name, user name, and raw SIDs must NOT appear
            self.assertNotIn("SEAMLESS.INTERNAL", res_str)
            self.assertNotIn("TSTWVIR1000001", res_str)
            self.assertNotIn("LIDIA_ALFORD", res_str)
            self.assertNotIn("S-1-5-21-", res_str)

    def test_cli_execution_flags(self):
        """Test CLI execution with --all and --json flags via subprocess with UTF-8 encoding."""
        script_path = Path(wev.__file__).resolve()
        env = {"PYTHONIOENCODING": "utf-8", **os.environ}

        # 1. Test --json flag
        res_json = subprocess.run(
            [sys.executable, str(script_path), "--json"],
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
            env=env,
        )
        self.assertEqual(res_json.returncode, 0, res_json.stderr)
        data = json.loads(res_json.stdout)
        self.assertEqual(data["overall_status"], "PASS")
        self.assertIn("hand_worked_examples", data)
        self.assertIn("experiment_1", data)
        self.assertIn("experiment_2", data)
        self.assertIn("experiment_3", data)
        self.assertIn("experiment_4", data)
        self.assertIn("experiment_5", data)

        # 2. Test --all flag
        res_all = subprocess.run(
            [sys.executable, str(script_path), "--all"],
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
            env=env,
        )
        self.assertEqual(res_all.returncode, 0, res_all.stderr)
        self.assertIn("RESEARCH VALIDATION REPORT: ISSUE #142 (TTS A)", res_all.stdout)
        self.assertIn("OVERALL VALIDATION SUITE RESULT: PASS", res_all.stdout)
        self.assertIn("--- JSON OUTPUT ---", res_all.stdout)

        # 3. Test default execution
        res_default = subprocess.run(
            [sys.executable, str(script_path)],
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
            env=env,
        )
        self.assertEqual(res_default.returncode, 0, res_default.stderr)
        self.assertIn("OVERALL VALIDATION SUITE RESULT: PASS", res_default.stdout)

    def test_cli_manifest_failure_returns_exit_code_1(self):
        """Test that passing an invalid manifest causes CLI to fail with exit code 1."""
        script_path = Path(wev.__file__).resolve()
        env = {"PYTHONIOENCODING": "utf-8", **os.environ}

        res = subprocess.run(
            [sys.executable, str(script_path), "--manifest", "/invalid/nonexistent/manifest.json"],
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
            env=env,
        )
        self.assertNotEqual(res.returncode, 0)
        self.assertIn("OVERALL VALIDATION SUITE RESULT: FAIL", res.stdout)

    def test_cli_raw_dir_nonexistent_returns_exit_code_1(self):
        """Test that passing a nonexistent raw directory causes CLI to fail with exit code 1."""
        script_path = Path(wev.__file__).resolve()
        env = {"PYTHONIOENCODING": "utf-8", **os.environ}

        res = subprocess.run(
            [sys.executable, str(script_path), "--raw-dir", "/invalid/nonexistent/raw_dir"],
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
            env=env,
        )
        self.assertNotEqual(res.returncode, 0)
        self.assertIn("OVERALL VALIDATION SUITE RESULT: FAIL", res.stdout)

    def test_gate_context_blocks_path_and_affects_lexicographic_ranking(self):
        """Test that setting Gate A = False blocks the path and strictly deprioritizes it."""
        path1 = wev.build_path_1_seamless_reset()
        path2 = wev.build_path_2_synthetic_session()

        # By default in Scenario mode at S2, both paths are feasible
        self.assertTrue(path1.is_feasible("S2"))
        self.assertEqual(path1.path_status("S2"), "feasible")
        self.assertEqual(path1.path_likelihood("S2"), "Medium")
        self.assertEqual(path1.total_cost("S2"), 3)

        self.assertTrue(path2.is_feasible("S2"))
        self.assertEqual(path2.path_status("S2"), "feasible")
        self.assertEqual(path2.path_likelihood("S2"), "High")
        self.assertEqual(path2.total_cost("S2"), 3)

        # In default ranking at S2, Path 2 wins because Likelihood High > Medium
        default_ranked = sorted([path1, path2], key=lambda p: p.lexicographic_key("S2"))
        self.assertEqual(default_ranked[0].name, path2.name)
        self.assertEqual(default_ranked[1].name, path1.name)

        # Now set Gate A = False for path1 via gate_context
        blocked_ctx = {"Gate A": False}
        self.assertFalse(path1.is_feasible("S2", gate_context=blocked_ctx))
        self.assertEqual(path1.path_status("S2", gate_context=blocked_ctx), "blocked")
        self.assertEqual(path1.path_likelihood("S2", gate_context=blocked_ctx), "Blocked")
        self.assertIsNone(path1.total_cost("S2", gate_context=blocked_ctx))

        # Check lexicographic key has infeasible penalty
        p1_key_blocked = path1.lexicographic_key("S2", gate_context=blocked_ctx)
        p2_key_feasible = path2.lexicographic_key("S2")
        self.assertEqual(p1_key_blocked[0], 1)
        self.assertEqual(p2_key_feasible[0], 0)
        self.assertGreater(p1_key_blocked, p2_key_feasible)

        # If Path 2 is blocked (Gate A = False) while Path 1 remains feasible,
        # Path 1 MUST strictly beat Path 2 in ranking despite Path 1 having Medium likelihood
        p2_key_blocked = path2.lexicographic_key("S2", gate_context=blocked_ctx)
        p1_key_feasible = path1.lexicographic_key("S2")
        self.assertLess(p1_key_feasible, p2_key_blocked)

        # Gate M = False also blocks S2
        gm_blocked_ctx = {"gate_m": False}
        self.assertFalse(path1.is_feasible("S2", gate_context=gm_blocked_ctx))
        self.assertEqual(path1.path_status("S2", gate_context=gm_blocked_ctx), "blocked")

        # Gate A = 'Unknown' makes path unknown and infeasible
        unknown_ctx = {"gate_a": "Unknown"}
        self.assertFalse(path1.is_feasible("S2", gate_context=unknown_ctx))
        self.assertEqual(path1.path_status("S2", gate_context=unknown_ctx), "unknown")
        self.assertEqual(path1.path_likelihood("S2", gate_context=unknown_ctx), "Unknown")
        self.assertIsNone(path1.total_cost("S2", gate_context=unknown_ctx))

        # Gate O = True in generic scenario assumption CANNOT unlock S3
        go_generic_ctx = {"Gate O": True}
        self.assertFalse(path1.is_feasible("S3", gate_context=go_generic_ctx))
        self.assertEqual(path1.path_status("S3", gate_context=go_generic_ctx), "unknown")
        self.assertIsNone(path1.total_cost("S3", gate_context=go_generic_ctx))
        self.assertEqual(path1.nominal_cost("S3"), 6)

        # Downstream-only replication evidence without baseline_assumptions cannot make S3 feasible
        self.assertEqual(
            path1.path_status("S3", gate_context={"structural_replication_rights": True}),
            "unknown",
        )
        self.assertFalse(
            path1.is_feasible("S3", gate_context={"structural_replication_rights": True})
        )

        # Verified replication authorization evidence CAN unlock S3 under baseline assumptions
        go_evidence_ctx = {"structural_replication_rights": True, "baseline_assumptions": True}
        self.assertTrue(path1.is_feasible("S3", gate_context=go_evidence_ctx))
        self.assertEqual(path1.path_status("S3", gate_context=go_evidence_ctx), "feasible")
        self.assertEqual(path1.total_cost("S3", gate_context=go_evidence_ctx), 6)
        self.assertEqual(path1.realized_cost("S3", gate_context=go_evidence_ctx), 6)

        # Alternative explicit replication evidence key also unlocks S3 under baseline assumptions
        go_evidence_ctx2 = {"evidence_replication_granted": True, "baseline_assumptions": True}
        self.assertTrue(path1.is_feasible("S3", gate_context=go_evidence_ctx2))
        self.assertEqual(path1.path_status("S3", gate_context=go_evidence_ctx2), "feasible")

        # Reset preconditions via gate_context: false password policy or disabled target blocks S1
        pp_blocked_ctx = {"password_policy_satisfied": False}
        self.assertFalse(path1.is_feasible("S1", gate_context=pp_blocked_ctx))
        self.assertFalse(path1.is_feasible("S2", gate_context=pp_blocked_ctx))
        self.assertEqual(path1.path_status("S2", gate_context=pp_blocked_ctx), "blocked")
        self.assertIsNone(path1.total_cost("S2", gate_context=pp_blocked_ctx))

        target_disabled_ctx = {"target_user_enabled": False}
        self.assertFalse(path1.is_feasible("S2", gate_context=target_disabled_ctx))
        self.assertEqual(path1.path_status("S2", gate_context=target_disabled_ctx), "blocked")

    def test_reset_preconditions_and_replication_evidence_reconciled(self):
        """Test reset preconditions evaluation under Kleene logic and Gate O evidence."""
        p1 = wev.build_path_1_seamless_reset()
        p2 = wev.build_path_2_synthetic_session()

        # 1. structural_genericall precondition: False strictly blocks S1, S2, S3
        self.assertEqual(p1.path_status("S1", {"structural_genericall": False}), "blocked")
        self.assertEqual(p1.path_status("S2", {"structural_genericall": False}), "blocked")
        self.assertFalse(p1.is_feasible("S1", {"structural_genericall": False}))
        self.assertFalse(p1.is_feasible("S2", {"structural_genericall": False}))

        # 2. Evaluation order invariance: Unknown before False must still be BLOCKED
        ctx_unknown_first = {
            "source_computer_enabled": "Unknown",
            "password_policy_satisfied": False,
        }
        self.assertEqual(p1.path_status("S1", ctx_unknown_first), "blocked")
        self.assertEqual(p1.path_status("S2", ctx_unknown_first), "blocked")
        self.assertEqual(p1.path_status("S3", ctx_unknown_first), "blocked")
        self.assertFalse(p1.is_feasible("S1", ctx_unknown_first))
        self.assertFalse(p1.is_feasible("S2", ctx_unknown_first))

        ctx_foothold_false = {
            "source_computer_enabled": "Unknown",
            "foothold": False,
        }
        self.assertEqual(p1.path_status("S1", ctx_foothold_false), "blocked")
        self.assertEqual(p1.path_status("S2", ctx_foothold_false), "blocked")
        self.assertFalse(p1.is_feasible("S2", ctx_foothold_false))

        ctx_foothold_proven_false = {
            "source_computer_enabled": "Unknown",
            "foothold_proven": False,
        }
        self.assertEqual(p1.path_status("S1", ctx_foothold_proven_false), "blocked")
        self.assertEqual(p1.path_status("S2", ctx_foothold_proven_false), "blocked")
        self.assertFalse(p1.is_feasible("S2", ctx_foothold_proven_false))

        # Reverse order test: False before Unknown produces identical blocked result
        ctx_false_first = {
            "password_policy_satisfied": False,
            "source_computer_enabled": "Unknown",
        }
        self.assertEqual(p1.path_status("S1", ctx_false_first), "blocked")
        self.assertEqual(p1.path_status("S2", ctx_false_first), "blocked")

        # 3. Ranking regression: blocked reset path cannot compete as feasible
        p1_key_blocked = p1.lexicographic_key("S2", gate_context=ctx_unknown_first)
        p2_key_feasible = p2.lexicographic_key("S2")
        self.assertEqual(p1_key_blocked[0], 1)
        self.assertEqual(p2_key_feasible[0], 0)
        self.assertGreater(p1_key_blocked, p2_key_feasible)

        ranked = rank_attack_paths(
            [p1, p2],
            checkpoint="S2",
            gate_context={p1.name: ctx_unknown_first, p2.name: None},
        )
        self.assertEqual(len(ranked["feasible"]), 1)
        self.assertEqual(ranked["feasible"][0].name, p2.name)
        self.assertEqual(len(ranked["blocked"]), 1)
        self.assertEqual(ranked["blocked"][0].name, p1.name)

        # 4. Gate O negative evidence: explicit False on replication rights strictly blocks S3
        self.assertEqual(p1.path_status("S3", {"structural_replication_rights": False}), "blocked")
        self.assertEqual(p1.path_status("S3", {"evidence_replication_granted": False}), "blocked")
        self.assertFalse(p1.is_feasible("S3", {"structural_replication_rights": False}))
        self.assertIsNone(
            p1.total_cost("S3", gate_context={"structural_replication_rights": False})
        )

        # 5. Gate O conflicting evidence: negative vetoes positive claims
        conflict_ctx1 = {
            "structural_replication_rights": True,
            "evidence_replication_granted": False,
        }
        self.assertEqual(p1.path_status("S3", conflict_ctx1), "blocked")
        self.assertFalse(p1.is_feasible("S3", conflict_ctx1))

        conflict_ctx2 = {
            "structural_replication_rights": False,
            "evidence_replication_granted": True,
        }
        self.assertEqual(p1.path_status("S3", conflict_ctx2), "blocked")
        self.assertFalse(p1.is_feasible("S3", conflict_ctx2))

        # 6. Gate O generic scenario assumptions cannot unlock S3
        self.assertEqual(p1.path_status("S3", {"Gate O": True}), "unknown")
        self.assertEqual(p1.path_status("S3", {"gate_o": True}), "unknown")
        self.assertFalse(p1.is_feasible("S3", {"Gate O": True}))

        # 7. Valid affirmative evidence unlocks S3 under baseline assumptions
        # Downstream-only replication evidence without baseline_assumptions cannot make S3 feasible
        self.assertEqual(p1.path_status("S3", {"structural_replication_rights": True}), "unknown")
        self.assertFalse(p1.is_feasible("S3", {"structural_replication_rights": True}))

        ctx_s3_unlocked = {"structural_replication_rights": True, "baseline_assumptions": True}
        ctx_s3_unlocked2 = {"evidence_replication_granted": True, "baseline_assumptions": True}
        self.assertEqual(p1.path_status("S3", ctx_s3_unlocked), "feasible")
        self.assertEqual(p1.path_status("S3", ctx_s3_unlocked2), "feasible")
        self.assertTrue(p1.is_feasible("S3", ctx_s3_unlocked))
        self.assertEqual(p1.total_cost("S3", gate_context=ctx_s3_unlocked), 6)

    def test_step_gate_status_direct_modification_blocks_feasibility(self):
        """Test that directly modifying a step's gate_status blocks path without gate_context."""
        p2 = wev.build_path_2_synthetic_session()
        # Replace step 2 with blocked gate status
        blocked_step2 = wev.ActionStep(
            name=p2.steps[1].name,
            step_number=p2.steps[1].step_number,
            action_type=p2.steps[1].action_type,
            t1=p2.steps[1].t1,
            t2=p2.steps[1].t2,
            t3=p2.steps[1].t3,
            likelihood=p2.steps[1].likelihood,
            gate_status="Gate A: False (rejected)",
            fact_stratum=p2.steps[1].fact_stratum,
        )
        p2_blocked = wev.AttackPath(
            name=p2.name,
            target_name=p2.target_name,
            target_impact=p2.target_impact,
            steps=[p2.steps[0], blocked_step2, p2.steps[2], p2.steps[3]],
            is_synthetic=True,
        )

        self.assertFalse(p2_blocked.is_feasible("S2"))
        self.assertEqual(p2_blocked.path_status("S2"), "blocked")
        self.assertEqual(p2_blocked.path_likelihood("S2"), "Blocked")
        self.assertIsNone(p2_blocked.total_cost("S2"))

        # Lexicographic ranking: feasible Path 1 ranks before blocked Path 2
        p1 = wev.build_path_1_seamless_reset()
        ranked = sorted([p2_blocked, p1], key=lambda p: p.lexicographic_key("S2"))
        self.assertEqual(ranked[0].name, p1.name)
        self.assertEqual(ranked[1].name, p2_blocked.name)

    def test_rank_attack_paths_helper_partitions_feasible_and_blocked(self):
        """Test rank_attack_paths helper partitions feasible and blocked paths."""
        p1 = wev.build_path_1_seamless_reset()
        p2 = wev.build_path_2_synthetic_session()

        # Both feasible at S2
        res = rank_attack_paths([p1, p2], checkpoint="S2")
        self.assertEqual(len(res.feasible), 2)
        self.assertEqual(len(res.blocked), 0)
        self.assertEqual(res.feasible[0].name, p2.name)
        self.assertEqual(res.feasible[1].name, p1.name)

        # Both blocked if Gate A is False
        res_blocked = rank_attack_paths([p1, p2], checkpoint="S2", gate_context={"Gate A": False})
        self.assertEqual(len(res_blocked.feasible), 0)
        self.assertEqual(len(res_blocked.blocked), 2)

        # Dictionary access compatibility
        self.assertEqual(res["feasible"], res.feasible)
        self.assertEqual(res["blocked"], res.blocked)
        self.assertEqual(res["infeasible"], res.infeasible)

    def test_snapshot_selector_exact_locators(self):
        """Test that snapshot selector returns exact locators for all entities."""
        raw_dir = Path("data/raw/SEAMLESS")
        manifest_path = Path("data/samples/manifests/seamless-raw-v1.json")
        if raw_dir.is_dir() and manifest_path.is_file():
            snap_res = verify_snapshot_data(raw_dir, manifest_path)
            self.assertEqual(snap_res["status"], "PASS")
            details = snap_res["details"]

            # Exact locators matching reviewer feedback
            self.assertEqual(
                details["source_a"]["locator"],
                "20210920185958_computers.json#/computers/46",
            )
            self.assertEqual(
                details["user_candidate"]["locator"],
                "20210920185958_users.json#/users/2310",
            )
            self.assertEqual(
                details["genericall_ace"]["locator"],
                "20210920185958_users.json#/users/2310/Aces/3",
            )
            self.assertEqual(
                details["da_group"]["locator"],
                "20210920185958_groups.json#/groups/40",
            )
            self.assertEqual(
                details["da_membership"]["locator"],
                "20210920185958_groups.json#/groups/40/Members/0",
            )
            self.assertEqual(
                details["krbtgt"]["locator"],
                "20210920185958_users.json#/users/3",
            )

    def test_authoritative_reset_prerequisites_partial_context_unknown_and_separation(self):
        """Test that partial reset context resolves to Unknown and S1 is independent of S2/S3."""
        p1 = wev.build_path_1_seamless_reset()

        # 1. Partial context (source_computer_enabled=True only) leaves other 5 missing -> unknown
        self.assertEqual(p1.path_status("S1", {"source_computer_enabled": True}), "unknown")
        self.assertFalse(p1.is_feasible("S1", {"source_computer_enabled": True}))
        self.assertEqual(p1.path_status("S2", {"source_computer_enabled": True}), "unknown")
        self.assertFalse(p1.is_feasible("S2", {"source_computer_enabled": True}))

        # 2. Baseline assumption flag allows assuming missing preconditions
        self.assertEqual(
            p1.path_status("S1", {"source_computer_enabled": True, "baseline_assumptions": True}),
            "feasible",
        )
        self.assertTrue(
            p1.is_feasible("S1", {"source_computer_enabled": True, "baseline_assumptions": True})
        )

        # 3. All 6 reset preconditions explicitly provided and True -> feasible
        all_6_true = {
            "structural_genericall": True,
            "source_computer_enabled": True,
            "target_user_enabled": True,
            "foothold": True,
            "password_policy_satisfied": True,
            "directory_write_available": True,
        }
        self.assertEqual(p1.path_status("S1", all_6_true), "feasible")
        self.assertTrue(p1.is_feasible("S1", all_6_true))

        # 4. evaluate_dynamic_modes(): 6 reset facts only reach S1, while S2 is Unsupported
        facts_s1_only = {
            "structural_genericall",
            "source_computer_enabled",
            "target_user_enabled",
            "foothold",
            "password_policy_satisfied",
            "directory_write_available",
        }
        res_s1 = evaluate_dynamic_modes(facts_s1_only)
        self.assertIn("Reached (cost=2)", res_s1["checkpoint_s1_status"])
        self.assertIn("Unsupported", res_s1["checkpoint_s2_status"])
        self.assertIn("structural_memberof", res_s1["checkpoint_s2_status"])

        # 5. Adding downstream S2 facts unlocks S2
        facts_s2 = facts_s1_only | {"structural_memberof", "gate_a_accepted", "gate_m_usable"}
        res_s2 = evaluate_dynamic_modes(facts_s2)
        self.assertIn("Reached (cost=3, P=Medium)", res_s2["checkpoint_s2_status"])
        self.assertIn("Unsupported", res_s2["checkpoint_s3_status"])

    def test_parse_tristate_fails_closed_on_unrecognized_values_and_gate_o(self):
        """Test parse_tristate fails closed on unrecognized values, preventing Gate O unlock."""
        # Direct parse_tristate checks
        self.assertEqual(wev.parse_tristate("not_measured"), "Unknown")
        self.assertEqual(wev.parse_tristate("missing"), "Unknown")
        self.assertEqual(wev.parse_tristate({"invalid": True}), "Unknown")
        self.assertEqual(wev.parse_tristate([1, 2]), "Unknown")
        self.assertEqual(wev.parse_tristate(None), "Unknown")
        self.assertEqual(wev.parse_tristate("arbitrary_string"), "Unknown")
        self.assertEqual(wev.parse_tristate(True), True)
        self.assertEqual(wev.parse_tristate("true"), True)
        self.assertEqual(wev.parse_tristate("granted"), True)
        self.assertEqual(wev.parse_tristate(False), False)
        self.assertEqual(wev.parse_tristate("blocked"), False)

        # Gate O evaluation fails closed: invalid/unrecognized values cannot unlock S3
        p1 = wev.build_path_1_seamless_reset()
        self.assertEqual(
            p1.path_status("S3", {"structural_replication_rights": "not_measured"}), "unknown"
        )
        self.assertFalse(p1.is_feasible("S3", {"structural_replication_rights": "not_measured"}))
        self.assertEqual(
            p1.path_status("S3", {"evidence_replication_granted": {"invalid": True}}), "unknown"
        )
        self.assertFalse(p1.is_feasible("S3", {"evidence_replication_granted": {"invalid": True}}))
        self.assertEqual(
            p1.path_status("S3", {"structural_replication_rights": "missing"}), "unknown"
        )
        self.assertEqual(p1.path_status("S3", {"structural_replication_rights": [1, 2]}), "unknown")

    def test_snapshot_manifest_audit_records_failed_core_file(self):
        """Test manifest verification records corrupted core file into failed_files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            raw_dir = Path(tmpdir) / "raw"
            raw_dir.mkdir()
            comp_file = raw_dir / "20210920185958_computers.json"
            comp_file.write_text(json.dumps({"computers": []}), encoding="utf-8")
            user_file = raw_dir / "20210920185958_users.json"
            user_file.write_text(json.dumps({"users": []}), encoding="utf-8")
            grp_file = raw_dir / "20210920185958_groups.json"
            grp_file.write_text(json.dumps({"groups": []}), encoding="utf-8")

            # Corrupt expected hash of computers.json
            bad_hash = "0" * 64
            user_hash = hashlib.sha256(user_file.read_bytes()).hexdigest()
            grp_hash = hashlib.sha256(grp_file.read_bytes()).hexdigest()

            manifest_path = Path(tmpdir) / "manifest.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "files": [
                            {
                                "relative_path": "20210920185958_computers.json",
                                "sha256": bad_hash,
                                "size_bytes": comp_file.stat().st_size,
                            },
                            {
                                "relative_path": "20210920185958_users.json",
                                "sha256": user_hash,
                                "size_bytes": user_file.stat().st_size,
                            },
                            {
                                "relative_path": "20210920185958_groups.json",
                                "sha256": grp_hash,
                                "size_bytes": grp_file.stat().st_size,
                            },
                        ]
                    }
                )
            )

            res = verify_snapshot_data(raw_dir, manifest_path)
            self.assertEqual(res["status"], "FAIL")
            self.assertFalse(res["snapshot_verified"])
            self.assertFalse(res["file_hash_verified"])
            mv = res["details"]["manifest_verification"]
            self.assertFalse(mv["all_verified"])
            self.assertIn("20210920185958_computers.json", mv["failed_files"])
            self.assertNotIn("20210920185958_computers.json", mv["verified_files"])
            self.assertIn("20210920185958_users.json", mv["verified_files"])
            self.assertIn("20210920185958_groups.json", mv["verified_files"])
            self.assertFalse(res["details"]["source_a"]["file_hash_verified"])

    def test_direct_override_and_alias_negative_veto_and_ranking_propagation(self):
        """Test negative evidence strictly vetoes overrides and aliases, affecting ranking."""
        p1 = wev.build_path_1_seamless_reset()
        reset = {
            "structural_genericall": True,
            "source_computer_enabled": True,
            "target_user_enabled": True,
            "foothold": True,
            "password_policy_satisfied": True,
            "directory_write_available": True,
        }

        # 1. Direct step override (step_1: True) cannot bypass negative prerequisite fact
        ctx_override_neg = {"step_1": True, "target_user_enabled": False}
        self.assertEqual(p1.path_status("S1", ctx_override_neg), "blocked")
        self.assertEqual(p1.path_status("S2", ctx_override_neg), "blocked")
        self.assertEqual(p1.path_status("S3", ctx_override_neg), "blocked")
        self.assertFalse(p1.is_feasible("S1", ctx_override_neg))
        self.assertFalse(p1.is_feasible("S2", ctx_override_neg))
        self.assertIsNone(p1.total_cost("S1", gate_context=ctx_override_neg))
        self.assertIsNone(p1.total_cost("S2", gate_context=ctx_override_neg))

        # 2. Conflicting aliases: target_user_enabled=True vs target_enabled=False -> False vetoes
        ctx_alias_conflict = {**reset, "target_enabled": False}
        self.assertEqual(p1.path_status("S1", ctx_alias_conflict), "blocked")
        self.assertEqual(p1.path_status("S2", ctx_alias_conflict), "blocked")
        self.assertFalse(p1.is_feasible("S1", ctx_alias_conflict))

        # 3. Direct override step_1=False with positive prerequisites -> False vetoes
        ctx_direct_false = {**reset, "step_1": False}
        self.assertEqual(p1.path_status("S1", ctx_direct_false), "blocked")

        # 4. Ranking propagation: blocked path gets infeasible flag and goes to blocked partition
        key_blocked = p1.lexicographic_key("S1", gate_context=ctx_override_neg)
        self.assertEqual(key_blocked[0], 1)
        res_ranked = rank_attack_paths([p1], checkpoint="S1", gate_context=ctx_override_neg)
        self.assertEqual(len(res_ranked.blocked), 1)
        self.assertEqual(len(res_ranked.feasible), 0)

    def test_authoritative_reset_prerequisites_mandatory_and_no_step1_bypass(self):
        """Test authoritative reset prerequisites are mandatory whenever gate_context is provided.

        Verifies:
          1. step_1=True + structural_genericall=False => S1 blocked.
          2. downstream-only context without baseline_assumptions=True => S1 unknown/unsupported.
          3. downstream-only context with baseline_assumptions=True => S1 feasible, S2 feasible.
          4. step_1=True shortcut alone without baseline_assumptions=True => S1 unknown.
          5. step_1=True with baseline_assumptions=True => S1 feasible.
          6. step_1=True + structural_genericall=False with baseline_assumptions=True => S1 blocked.
        """
        p1 = wev.build_path_1_seamless_reset()

        # 1. step_1=True + structural_genericall=False => S1 blocked
        ctx_step1_struct_neg = {"step_1": True, "structural_genericall": False}
        self.assertEqual(p1.path_status("S1", ctx_step1_struct_neg), "blocked")
        self.assertFalse(p1.is_feasible("S1", ctx_step1_struct_neg))
        self.assertEqual(p1.path_status("S2", ctx_step1_struct_neg), "blocked")
        self.assertFalse(p1.is_feasible("S2", ctx_step1_struct_neg))

        # 2. downstream-only context without baseline_assumptions=True => S1 unknown, not feasible
        ctx_downstream_only = {"gate_a": True, "gate_m": True}
        self.assertEqual(p1.path_status("S1", ctx_downstream_only), "unknown")
        self.assertFalse(p1.is_feasible("S1", ctx_downstream_only))
        self.assertEqual(p1.path_status("S2", ctx_downstream_only), "unknown")
        self.assertFalse(p1.is_feasible("S2", ctx_downstream_only))

        # 3. downstream-only context with baseline_assumptions=True => S1 feasible, S2 feasible
        ctx_downstream_base = {"gate_a": True, "gate_m": True, "baseline_assumptions": True}
        self.assertEqual(p1.path_status("S1", ctx_downstream_base), "feasible")
        self.assertTrue(p1.is_feasible("S1", ctx_downstream_base))
        self.assertEqual(p1.path_status("S2", ctx_downstream_base), "feasible")
        self.assertTrue(p1.is_feasible("S2", ctx_downstream_base))

        # 4. step_1=True alone without baseline_assumptions=True => S1 unknown
        self.assertEqual(p1.path_status("S1", {"step_1": True}), "unknown")
        self.assertFalse(p1.is_feasible("S1", {"step_1": True}))

        # 5. step_1=True with baseline_assumptions=True => S1 feasible
        self.assertEqual(
            p1.path_status("S1", {"step_1": True, "baseline_assumptions": True}),
            "feasible",
        )
        self.assertTrue(p1.is_feasible("S1", {"step_1": True, "baseline_assumptions": True}))

        # 6. step_1=True with structural_genericall=False even with baseline assumptions => blocked
        self.assertEqual(
            p1.path_status(
                "S1",
                {
                    "step_1": True,
                    "structural_genericall": False,
                    "baseline_assumptions": True,
                },
            ),
            "blocked",
        )
        self.assertFalse(
            p1.is_feasible(
                "S1",
                {
                    "step_1": True,
                    "structural_genericall": False,
                    "baseline_assumptions": True,
                },
            )
        )

    def test_attackpath_s2_s3_structural_prerequisites_and_baseline_flag_parsing(self):
        """Test AttackPath S2 membership, S3 target prerequisites, and fail-closed flag parsing."""
        p1 = wev.build_path_1_seamless_reset()
        reset = {
            "structural_genericall": True,
            "source_computer_enabled": True,
            "target_user_enabled": True,
            "foothold": True,
            "password_policy_satisfied": True,
            "directory_write_available": True,
        }

        # 1. S2 structural_memberof: False -> blocked, total_cost=None
        ctx_s2_member_false = {
            **reset,
            "gate_a": True,
            "gate_m": True,
            "structural_memberof": False,
        }
        self.assertEqual(p1.path_status("S2", ctx_s2_member_false), "blocked")
        self.assertFalse(p1.is_feasible("S2", ctx_s2_member_false))
        self.assertIsNone(p1.total_cost("S2", gate_context=ctx_s2_member_false))

        # 2. S2 structural_memberof: Unknown / missing string -> unknown
        ctx_s2_member_unknown = {
            **reset,
            "gate_a": True,
            "gate_m": True,
            "structural_memberof": "unknown",
        }
        self.assertEqual(p1.path_status("S2", ctx_s2_member_unknown), "unknown")
        self.assertFalse(p1.is_feasible("S2", ctx_s2_member_unknown))

        ctx_s2_member_missing_str = {
            **reset,
            "gate_a": True,
            "gate_m": True,
            "structural_memberof": "missing",
        }
        self.assertEqual(p1.path_status("S2", ctx_s2_member_missing_str), "unknown")

        # 3. S2 structural_memberof omitted in full context -> unknown (unless baseline assumptions)
        ctx_s2_member_omitted = {
            **reset,
            "gate_a": True,
            "gate_m": True,
        }
        self.assertEqual(p1.path_status("S2", ctx_s2_member_omitted), "unknown")
        ctx_s2_member_omitted_base = {
            **reset,
            "gate_a": True,
            "gate_m": True,
            "baseline_assumptions": True,
        }
        self.assertEqual(p1.path_status("S2", ctx_s2_member_omitted_base), "feasible")
        self.assertEqual(p1.total_cost("S2", gate_context=ctx_s2_member_omitted_base), 3)

        # 4. S1 independence from downstream S2 membership and S3 target
        ctx_s1_indep = {
            **reset,
            "structural_memberof": False,
            "target_krbtgt_exists": False,
        }
        self.assertEqual(p1.path_status("S1", ctx_s1_indep), "feasible")
        self.assertTrue(p1.is_feasible("S1", ctx_s1_indep))

        # 5. S2 independence from downstream S3 target
        ctx_s2_indep = {
            **reset,
            "gate_a": True,
            "gate_m": True,
            "structural_memberof": True,
            "target_krbtgt_exists": False,
            "structural_replication_rights": False,
        }
        self.assertEqual(p1.path_status("S2", ctx_s2_indep), "feasible")
        self.assertTrue(p1.is_feasible("S2", ctx_s2_indep))

        # 6. S3 target_krbtgt_exists: False -> blocked, total_cost=None
        ctx_s3_target_false = {
            **reset,
            "gate_a": True,
            "gate_m": True,
            "structural_memberof": True,
            "structural_replication_rights": True,
            "target_krbtgt_exists": False,
        }
        self.assertEqual(p1.path_status("S3", ctx_s3_target_false), "blocked")
        self.assertFalse(p1.is_feasible("S3", ctx_s3_target_false))
        self.assertIsNone(p1.total_cost("S3", gate_context=ctx_s3_target_false))

        # 7. S3 target_krbtgt_exists: Unknown / missing string / omitted -> unknown
        ctx_s3_target_unknown = {
            **reset,
            "gate_a": True,
            "gate_m": True,
            "structural_memberof": True,
            "structural_replication_rights": True,
            "target_krbtgt_exists": "unknown",
        }
        self.assertEqual(p1.path_status("S3", ctx_s3_target_unknown), "unknown")

        ctx_s3_target_omitted = {
            **reset,
            "gate_a": True,
            "gate_m": True,
            "structural_memberof": True,
            "structural_replication_rights": True,
        }
        self.assertEqual(p1.path_status("S3", ctx_s3_target_omitted), "unknown")
        ctx_s3_target_omitted_base = {
            **reset,
            "gate_a": True,
            "gate_m": True,
            "structural_memberof": True,
            "structural_replication_rights": True,
            "baseline_assumptions": True,
        }
        self.assertEqual(p1.path_status("S3", ctx_s3_target_omitted_base), "feasible")
        self.assertEqual(p1.total_cost("S3", gate_context=ctx_s3_target_omitted_base), 6)

        # 8. All facts present and True -> S3 feasible with cost 6
        ctx_s3_all_true = {
            **reset,
            "gate_a": True,
            "gate_m": True,
            "structural_memberof": True,
            "structural_replication_rights": True,
            "target_krbtgt_exists": True,
        }
        self.assertEqual(p1.path_status("S3", ctx_s3_all_true), "feasible")
        self.assertTrue(p1.is_feasible("S3", ctx_s3_all_true))
        self.assertEqual(p1.total_cost("S3", gate_context=ctx_s3_all_true), 6)

        # 9. Baseline assumption flag fail-closed parsing (is_flag_true)
        # Truthy string "false" must NOT activate assumptions
        ctx_base_false_str = {"source_computer_enabled": True, "baseline_assumptions": "false"}
        self.assertEqual(p1.path_status("S1", ctx_base_false_str), "unknown")

        ctx_assume_false_str = {
            "source_computer_enabled": True,
            "assume_reset_prerequisites": "false",
        }
        self.assertEqual(p1.path_status("S1", ctx_assume_false_str), "unknown")

        self.assertEqual(
            p1.path_status("S1", {"source_computer_enabled": True, "baseline_assumptions": "0"}),
            "unknown",
        )
        self.assertEqual(
            p1.path_status("S1", {"source_computer_enabled": True, "baseline_assumptions": "no"}),
            "unknown",
        )
        ctx_base_invalid = {
            "source_computer_enabled": True,
            "baseline_assumptions": {"invalid": True},
        }
        self.assertEqual(p1.path_status("S1", ctx_base_invalid), "unknown")

        # Recognized True values activate assumptions
        self.assertEqual(
            p1.path_status("S1", {"source_computer_enabled": True, "baseline_assumptions": True}),
            "feasible",
        )
        self.assertEqual(
            p1.path_status("S1", {"source_computer_enabled": True, "baseline_assumptions": "true"}),
            "feasible",
        )

    def test_empty_or_unrecognized_context_fails_closed_without_baseline(self):
        """Test empty or unrecognized context fails closed dynamically without baseline fallback.

        Verifies:
          1. Empty gate_context={} evaluates dynamically: missing prerequisites remain
             Unknown -> S1 unknown, S2 unknown, total_cost is None, is_feasible is False.
          2. Unrecognized field context (e.g. {"unknown_field": "not_measured"}) evaluates
             dynamically without fallback to nominal baseline.
          3. rank_attack_paths with empty/unrecognized context partitions path to blocked,
             leaving feasible partition empty.
          4. Nominal baseline behavior is preserved when gate_context=None.
          5. Explicit baseline_assumptions=True allows assumptions for missing prerequisites.
          6. Explicit per-path ranking context ({p1.name: ctx1, p2.name: None}) isolates
             contexts correctly and allows omitted paths to default to nominal baseline.
        """
        p1 = wev.build_path_1_seamless_reset()
        p2 = wev.build_path_2_synthetic_session()

        # 1. Empty context: dynamic evaluation with missing prerequisites -> unknown
        self.assertEqual(p1.path_status("S1", {}), "unknown")
        self.assertFalse(p1.is_feasible("S1", {}))
        self.assertIsNone(p1.total_cost("S1", gate_context={}))
        self.assertEqual(p1.path_status("S2", {}), "unknown")
        self.assertFalse(p1.is_feasible("S2", {}))
        self.assertIsNone(p1.total_cost("S2", gate_context={}))

        # 2. Unrecognized field context: dynamic evaluation without fallback
        unrecognized_ctx = {"unknown_field": "not_measured"}
        self.assertEqual(p1.path_status("S1", unrecognized_ctx), "unknown")
        self.assertFalse(p1.is_feasible("S1", unrecognized_ctx))
        self.assertIsNone(p1.total_cost("S1", gate_context=unrecognized_ctx))
        self.assertEqual(p1.path_status("S2", unrecognized_ctx), "unknown")
        self.assertFalse(p1.is_feasible("S2", unrecognized_ctx))
        self.assertIsNone(p1.total_cost("S2", gate_context=unrecognized_ctx))

        # 3. Ranking partition with empty or unrecognized context
        ranked_empty = rank_attack_paths([p1], checkpoint="S2", gate_context={})
        self.assertEqual(len(ranked_empty.feasible), 0)
        self.assertEqual(len(ranked_empty.blocked), 1)
        self.assertEqual(ranked_empty.blocked[0].name, p1.name)

        ranked_unrec = rank_attack_paths([p1], checkpoint="S2", gate_context=unrecognized_ctx)
        self.assertEqual(len(ranked_unrec.feasible), 0)
        self.assertEqual(len(ranked_unrec.blocked), 1)
        self.assertEqual(ranked_unrec.blocked[0].name, p1.name)

        # 4. Nominal baseline preserved when gate_context=None
        self.assertEqual(p1.path_status("S1", None), "feasible")
        self.assertTrue(p1.is_feasible("S1", None))
        self.assertEqual(p1.path_status("S2", None), "feasible")
        self.assertTrue(p1.is_feasible("S2", None))
        self.assertEqual(p1.total_cost("S2", gate_context=None), 3)

        ranked_baseline = rank_attack_paths([p1], checkpoint="S2", gate_context=None)
        self.assertEqual(len(ranked_baseline.feasible), 1)
        self.assertEqual(len(ranked_baseline.blocked), 0)

        # 5. Explicit baseline_assumptions=True activates assumptions
        assume_ctx = {"baseline_assumptions": True}
        self.assertEqual(p1.path_status("S1", assume_ctx), "feasible")
        self.assertTrue(p1.is_feasible("S1", assume_ctx))
        self.assertEqual(p1.path_status("S2", assume_ctx), "feasible")
        self.assertTrue(p1.is_feasible("S2", assume_ctx))
        self.assertEqual(p1.total_cost("S2", gate_context=assume_ctx), 3)

        # 6. Explicit per-path ranking context and omitted path default
        ranked_per_path = rank_attack_paths(
            [p1, p2],
            checkpoint="S2",
            gate_context={p1.name: {}, p2.name: None},
        )
        self.assertEqual(len(ranked_per_path.feasible), 1)
        self.assertEqual(ranked_per_path.feasible[0].name, p2.name)
        self.assertEqual(len(ranked_per_path.blocked), 1)
        self.assertEqual(ranked_per_path.blocked[0].name, p1.name)

        # Omitted path from per-path mapping defaults to None (baseline)
        ranked_omitted = rank_attack_paths(
            [p1, p2],
            checkpoint="S2",
            gate_context={p1.name: {}},
        )
        self.assertEqual(len(ranked_omitted.feasible), 1)
        self.assertEqual(ranked_omitted.feasible[0].name, p2.name)
        self.assertEqual(len(ranked_omitted.blocked), 1)
        self.assertEqual(ranked_omitted.blocked[0].name, p1.name)

        # Case-insensitive path name key matching
        ranked_case_insensitive = rank_attack_paths(
            [p1, p2],
            checkpoint="S2",
            gate_context={p1.name.lower(): {}},
        )
        self.assertEqual(len(ranked_case_insensitive.feasible), 1)
        self.assertEqual(ranked_case_insensitive.feasible[0].name, p2.name)
        self.assertEqual(len(ranked_case_insensitive.blocked), 1)
        self.assertEqual(ranked_case_insensitive.blocked[0].name, p1.name)


if __name__ == "__main__":
    unittest.main()
