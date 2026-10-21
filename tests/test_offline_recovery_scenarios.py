"""Independent finite-world checks and refusal controls for research proposals."""

from __future__ import annotations

import copy
import json
import subprocess
import sys
import tempfile
import unittest
from fractions import Fraction
from pathlib import Path

from scripts.research.offline_recovery_scenarios import (
    PACKAGE,
    ROOT,
    audit,
    conditional_chain,
    curve_bounds,
    human_interval,
    mixture_interval,
    propose,
    random_upper,
    reference_envelope,
)


class RecoveryProposalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sources = json.loads((PACKAGE / "sources.json").read_text(encoding="utf-8"))
        cls.packet = json.loads((PACKAGE / "scenarios.proposed.json").read_text(encoding="utf-8"))
        cls.source = cls.sources["guessing_reference"]
        cls.asrep = copy.deepcopy(cls.packet["profiles"][0])
        cls.kerberoast = copy.deepcopy(cls.packet["profiles"][3])
        cls.uniformity = copy.deepcopy(
            cls.packet["profiles"][-1]["population"]["generated_stratum"][
                "post_history_uniformity_assumption"
            ]
        )

    def test_source_rows_match_visually_verified_table_6(self):
        expected = {
            "CMUactive": (25459, [Fraction(1, 1000), Fraction(11, 250), Fraction(27, 100)]),
            "MTsim": (1000, [Fraction(1, 500), Fraction(63, 1000), Fraction(61, 200)]),
            "MTcomp8": (1000, [Fraction(0), Fraction(37, 1000), Fraction(263, 1000)]),
        }
        self.assertEqual({row["population"] for row in self.source["rows"]}, set(expected))
        for row in self.source["rows"]:
            n, fractions = expected[row["population"]]
            self.assertEqual(row["held_out_n"], n)
            self.assertEqual([p["guesses"] for p in row["points"]], [10**6, 10**9, 10**12])
            self.assertEqual([Fraction(p["reported_fraction"]) for p in row["points"]], fractions)

    def test_rounding_monotonicity_without_log_interpolation(self):
        self.assertEqual(
            reference_envelope(self.source, 10**9), (Fraction(73, 2000), Fraction(127, 2000))
        )
        self.assertEqual(
            reference_envelope(self.source, 2**36), (Fraction(73, 2000), Fraction(611, 2000))
        )
        self.assertEqual(reference_envelope(self.source, 0), (Fraction(0), Fraction(0)))
        self.assertEqual(reference_envelope(self.source, 10**15)[1], 1)

    def test_work_floor_bound_encloses_every_admissible_finite_world(self):
        source = {
            "rounding_half_width": "0",
            "rows": [
                {
                    "points": [
                        {"guesses": 2, "reported_fraction": "1/2"},
                        {"guesses": 3, "reported_fraction": "3/4"},
                    ]
                }
            ],
        }
        bounds = human_interval(source, 2, 3, ["1/2", "1"])
        self.assertEqual(bounds, (Fraction(1, 4), Fraction(3, 4)))
        checked = 0
        for floor in range(16):
            if floor.bit_count() != 2:
                continue
            for cap in range(16):
                if cap.bit_count() != 3 or floor & cap != floor:
                    continue
                for completion in range(16):
                    if (floor & completion).bit_count() < 1:
                        continue
                    actual = Fraction((cap & completion).bit_count(), 4)
                    self.assertLessEqual(bounds[0], actual)
                    self.assertLessEqual(actual, bounds[1])
                    checked += 1
        self.assertEqual(checked, 144)

    def test_conditional_completion_is_not_marginal_independence(self):
        # Half the passwords are in the floor. Completion happens only outside it.
        # Marginals are both 1/2, but recovery is zero: the conditional floor is zero.
        source = {
            "rounding_half_width": "0",
            "rows": [{"points": [{"guesses": 2, "reported_fraction": "1/2"}]}],
        }
        bounds = human_interval(source, 2, 2, ["0", "0"])
        self.assertEqual(bounds[0], 0)
        self.assertNotEqual(bounds[0], Fraction(1, 4))

    def test_mixture_extrema_cover_weights_and_strata_without_independence(self):
        bounds = mixture_interval(
            (Fraction(1, 5), Fraction(4, 5)), (Fraction(1, 10), Fraction(1, 2)), ["1/4", "3/4"]
        )
        for numerator in range(25, 76):
            w = Fraction(numerator, 100)
            for manual in (Fraction(1, 5), Fraction(1, 2), Fraction(4, 5)):
                for generated in (Fraction(1, 10), Fraction(1, 4), Fraction(1, 2)):
                    actual = w * manual + (1 - w) * generated
                    self.assertLessEqual(bounds[0], actual)
                    self.assertLessEqual(actual, bounds[1])
        # Also exercise the reverse ordering of generated and manual strata.
        self.assertEqual(
            mixture_interval(
                (Fraction(0), Fraction(1, 4)), (Fraction(1, 2), Fraction(1)), ["0", "1"]
            ),
            (Fraction(0), Fraction(1)),
        )

    def test_uniform_bound_encloses_all_candidate_sets_on_small_space(self):
        for cap in range(6):
            bound = random_upper(cap, 2, 2, post_history_uniformity=self.uniformity)
            for candidates in range(16):
                if candidates.bit_count() <= cap:
                    self.assertLessEqual(Fraction(candidates.bit_count(), 4), bound)
        self.assertGreater(random_upper(10**9, 94, 14, post_history_uniformity=self.uniformity), 0)

    def test_generation_uniformity_does_not_bound_a_correlated_posterior(self):
        # Four equally likely generated passwords; H discloses the first symbol.
        # One guess then succeeds with probability 1/2, greater than the prior 1/4 bound.
        passwords = ("00", "01", "10", "11")
        posterior = [password for password in passwords if password.startswith("0")]
        unconditional = Fraction(1, len(passwords))
        conditional = Fraction(1, len(posterior))
        self.assertGreater(conditional, unconditional)
        changed = copy.deepcopy(self.uniformity)
        changed["password_correlated_side_information"] = "known_password_prefix"
        with self.assertRaisesRegex(ValueError, "Post-history uniformity"):
            random_upper(1, 2, 2, post_history_uniformity=changed)

    def test_generated_stratum_requires_post_history_uniformity_for_both_service_profiles(self):
        mutations = (
            ("conditioning", "generation_only"),
            ("posterior_law", "unknown_or_nonuniform"),
            ("password_correlated_side_information", "known_password_prefix"),
            ("password_dependent_account_selection", "selected_using_password_information"),
            ("known_rejected_candidates", "one_or_more_prior_failed_guesses"),
            ("basis_class", "empirically_verified_without_evidence"),
            ("assumption_reference", ""),
        )
        for original in (self.kerberoast, self.packet["profiles"][-1]):
            for field, value in mutations:
                with self.subTest(profile=original["profile_id"], field=field):
                    p = copy.deepcopy(original)
                    p["population"]["generated_stratum"]["post_history_uniformity_assumption"][
                        field
                    ] = value
                    with self.assertRaisesRegex(ValueError, "Post-history uniformity"):
                        propose(p, self.source)
            for malformed in (None, "uniform_at_generation_only"):
                with self.subTest(profile=original["profile_id"], malformed=malformed):
                    p = copy.deepcopy(original)
                    p["population"]["generated_stratum"]["post_history_uniformity_assumption"] = (
                        malformed
                    )
                    with self.assertRaisesRegex(ValueError, "Post-history uniformity"):
                        propose(p, self.source)

    def test_asrep_proposal_exact_arithmetic(self):
        self.assertEqual(
            propose(self.asrep, self.source)["proposed_interval"], ["1387/40000", "127/2000"]
        )
        wider = copy.deepcopy(self.asrep)
        wider["budget"]["max_complete_distinct_verifications"] = 2**36
        self.assertEqual(
            propose(wider, self.source)["proposed_interval"], ["1387/40000", "611/2000"]
        )

    def test_wide_cap_rates_are_requirements_not_achieved_work(self):
        for p in self.packet["profiles"]:
            if "widecap" not in p["profile_id"]:
                continue
            result = propose(p, self.source)
            scope = result["resource_scope"]
            self.assertEqual(scope["floor_rate_requirement"], "125000/9")
            self.assertEqual(scope["cap_exhaustion_rate_requirement"], "1073741824/1125")
            self.assertGreater(
                Fraction(scope["cap_exhaustion_rate_requirement"]),
                68 * Fraction(scope["floor_rate_requirement"]),
            )
            self.assertEqual(scope["upper_role"], "hypothetical_loose_wide_cap_enclosure")
            self.assertEqual(scope["attainment_evidence"], "not_demonstrated")
            self.assertTrue(
                scope["requires_separate_resource_evidence_before_operational_use_or_adoption"]
            )
            self.assertEqual(result["records_emitted"], 0)

    def test_cap_cannot_claim_feasible_or_adoptable_without_resource_evidence(self):
        for field, value in (
            ("cap_role", "verified_completed_work"),
            ("attainment_evidence", "verified"),
            ("requires_separate_resource_evidence_before_operational_use_or_adoption", False),
        ):
            with self.subTest(field=field):
                p = copy.deepcopy(self.packet["profiles"][1])
                p["budget"]["cap_feasibility"][field] = value
                with self.assertRaisesRegex(ValueError, "Cap feasibility"):
                    propose(p, self.source)

    def test_service_has_own_stratified_interval(self):
        result = propose(self.kerberoast, self.source)
        lower, upper = map(Fraction, result["proposed_interval"])
        self.assertEqual(lower, Fraction(1387, 160000))
        expected_upper = Fraction(127, 4000) + Fraction(10**9, 2 * 94**14)
        self.assertEqual(upper, expected_upper)
        self.assertNotEqual(
            result["proposed_interval"], propose(self.asrep, self.source)["proposed_interval"]
        )

    def test_cap_without_floor_does_not_propose_positive_probability(self):
        p = copy.deepcopy(self.asrep)
        p["budget"]["min_complete_distinct_verifications_on_no_hit"] = None
        result = propose(p, self.source)
        self.assertEqual(result["disposition"], "REQUIRES_CONTEXT_WORK_FLOOR")
        self.assertIsNone(result["proposed_interval"])

    def test_snapshot_unknown_cases_stay_unrated(self):
        report = audit(self.sources, self.packet)
        unknowns = [p for p in report["proposals"] if "snapshot-only" in p["profile_id"]]
        self.assertEqual(len(unknowns), 2)
        self.assertTrue(all(p["proposed_interval"] is None for p in unknowns))

    def test_no_numeric_adoption_empirical_label_or_source_transfer(self):
        for change in ("status", "label", "transfer", "service_copy", "scope", "success"):
            with self.subTest(change=change):
                p = copy.deepcopy(self.asrep)
                if change == "status":
                    p["status"] = "adopted"
                elif change == "label":
                    p["numeric_basis_class"] = "empirical"
                elif change == "transfer":
                    p["population"]["reference_transfer"] = "automatic"
                elif change == "service_copy":
                    p.update(
                        class_id="kerberoast_password_recovery",
                        technique_id="recover_ticket_secret",
                    )
                    p["verifier"].update(material="TGS", hashcat_mode=13100)
                elif change == "scope":
                    p["conditioning"] = "marginal"
                else:
                    p["target_success_event"] = "usable_identity"
                with self.assertRaises(ValueError):
                    propose(p, self.source)

    def test_wrong_material_etype_and_mode_refused_separately(self):
        for field, value in (("material", "TGS"), ("etype", 18), ("hashcat_mode", 13100)):
            with self.subTest(field=field):
                p = copy.deepcopy(self.asrep)
                p["verifier"][field] = value
                with self.assertRaisesRegex(ValueError, "verifier transfer"):
                    propose(p, self.source)

    def test_random_bound_refuses_missing_or_changed_oracle_scope(self):
        for value in (None, "key leakage or verifier shortcuts permitted"):
            with self.subTest(scope=value):
                p = copy.deepcopy(self.packet["profiles"][-1])
                if value is None:
                    p["verifier"].pop("oracle_scope")
                else:
                    p["verifier"]["oracle_scope"] = value
                with self.assertRaisesRegex(ValueError, "oracle scope"):
                    propose(p, self.source)

    def test_reference_scenario_cannot_silently_become_product_baseline(self):
        result = propose(self.asrep, self.source)
        self.assertEqual(result["deployment_role"], "reference_scenario_not_default_baseline")
        for value in (None, "product_default"):
            with self.subTest(role=value):
                p = copy.deepcopy(self.asrep)
                if value is None:
                    p.pop("deployment_role")
                else:
                    p["deployment_role"] = value
                with self.assertRaisesRegex(ValueError, "product baseline"):
                    propose(p, self.source)
        packet = copy.deepcopy(self.packet)
        packet["product_baseline_selected"] = True
        with self.assertRaisesRegex(ValueError, "product baseline"):
            audit(self.sources, packet)

    def test_invalid_budget_and_probability_units_refused(self):
        mutations = [
            ("min_complete_distinct_verifications_on_no_hit", 10**9 + 1),
            ("max_complete_distinct_verifications", True),
            ("deadline_seconds", 86401),
            ("jobs", 3),
            ("jobs", True),
            ("work_unit", "kernel_hashes_per_second"),
        ]
        for field, value in mutations:
            with self.subTest(field=field):
                p = copy.deepcopy(self.asrep)
                p["budget"][field] = value
                with self.assertRaises(ValueError):
                    propose(p, self.source)
        for values in ([0.95, 1], ["3/4", "1/2"], ["-1", "1"]):
            p = copy.deepcopy(self.asrep)
            p["completion_given_floor_rank"] = values
            with self.assertRaises(ValueError):
                propose(p, self.source)

    def test_invalid_source_cdf_refused(self):
        for points in (
            [
                {"guesses": 1, "reported_fraction": "1/2"},
                {"guesses": 2, "reported_fraction": "1/4"},
            ],
            [
                {"guesses": 2, "reported_fraction": "1/4"},
                {"guesses": 1, "reported_fraction": "1/2"},
            ],
            [],
        ):
            with self.assertRaises(ValueError):
                curve_bounds(points, 1, rounding_half_width="0")

    def test_proposal_packet_never_emits_native_ratings(self):
        report = audit(self.sources, self.packet)
        self.assertEqual(len(report["proposals"]), 7)
        self.assertEqual(report["records_emitted"], 0)
        self.assertFalse(report["numeric_adopted"])
        self.assertFalse(report["native_search_or_coverage_run"])
        packet = copy.deepcopy(self.packet)
        packet["b_adopted"] = True
        with self.assertRaises(ValueError):
            audit(self.sources, packet)

    def test_chain_oracle_does_not_change_downstream_adoption(self):
        recovery = propose(self.asrep, self.source)["proposed_interval"]
        lower, upper = conditional_chain(
            [["9/10", "99/100"], recovery, ["3/4", "49/50"], ["1/2", "9/10"]]
        )
        self.assertEqual((lower, upper), (Fraction(37449, 3200000), Fraction(5544693, 100000000)))
        self.assertFalse(self.asrep["activation_or_winrm_history_reuse_authorized"])

    def test_real_cli_preserves_existing_output_and_rejects_raw_destination(self):
        command = [sys.executable, "-m", "scripts.research.offline_recovery_scenarios", "--output"]
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "report.json"
            good = subprocess.run([*command, str(target)], cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(good.returncode, 0, good.stderr)
            original = target.read_bytes()
            bad = subprocess.run([*command, str(target)], cwd=ROOT, capture_output=True, text=True)
            self.assertNotEqual(bad.returncode, 0)
            self.assertEqual(target.read_bytes(), original)
        raw_target = ROOT / "data/raw/must-not-create-offline-proposal.json"
        self.assertFalse(raw_target.exists())
        bad = subprocess.run([*command, str(raw_target)], cwd=ROOT, capture_output=True, text=True)
        self.assertNotEqual(bad.returncode, 0)
        self.assertFalse(raw_target.exists())


if __name__ == "__main__":
    unittest.main()
