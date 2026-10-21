"""Contract tests for the read-only Wave 2 coverage diagnosis."""

import copy
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.research.final_cpi_wave2_audit import (
    ADOPTED_NUMERIC,
    C_ONLY,
    NEEDS_EVIDENCE,
    REPORT,
    diagnose,
    protect_output,
)


class Wave2AuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.frozen = json.loads(REPORT.read_text(encoding="utf-8"))

    def test_frozen_cohorts_never_pool(self):
        result = diagnose(self.frozen)
        self.assertTrue(result["does_not_enable_production"])
        for name, all_feasible, supported_feasible, rated in (
            ("original", 50, 50, 48),
            ("supplementary", 109, 7, 0),
        ):
            group = result["groups"][name]
            self.assertEqual(group["all_completed_query_counts"]["fully_rated"], rated)
            self.assertEqual(
                group["all_completed_query_counts"]["conditioned_feasible"], all_feasible
            )
            self.assertEqual(group["supported_completed_query_counts"]["fully_rated"], rated)
            self.assertEqual(
                group["supported_completed_query_counts"]["conditioned_feasible"],
                supported_feasible,
            )
            self.assertNotIn("conditioned_feasible", group)

    def test_review_dispositions_are_not_implicit_production_adoption(self):
        self.assertEqual(len(ADOPTED_NUMERIC), 17)
        self.assertEqual(len(C_ONLY), 2)
        self.assertEqual(len(NEEDS_EVIDENCE), 1)
        result = diagnose(self.frozen)
        supplement = {c["query_id"]: c for c in result["groups"]["supplementary"]["cases"]}
        self.assertEqual(supplement["rbcd-scoped"]["conditioned_feasible"], 3)
        self.assertEqual(supplement["acl-group-host"]["conditioned_feasible"], 3)
        self.assertEqual(supplement["winrm-command"]["conditioned_feasible"], 1)
        self.assertTrue(
            any(
                family["numeric_disposition"] == "NUMERIC_ACCEPTED_CONTEXT_NOT_YET_BOUND"
                for family in supplement["rbcd-scoped"]["action_families"]
            )
        )

    def test_refuse_forged_coverage(self):
        altered = copy.deepcopy(self.frozen)
        altered["groups"]["supplementary"]["all_completed_query_counts"]["fully_rated"] = 7
        with self.assertRaisesRegex(ValueError, "numerator drift"):
            diagnose(altered)

    def test_refuse_unknown_replay_version(self):
        altered = copy.deepcopy(self.frozen)
        altered["version"] = "future-replay"
        with self.assertRaisesRegex(ValueError, "Unsupported replay"):
            diagnose(altered)

    def test_bound_wave1_and_unbound_same_family_are_context_specific(self):
        result = diagnose(self.frozen)
        original = {c["query_id"]: c for c in result["groups"]["original"]["cases"]}
        for query in ("source-a-projection", "source-a-full-raw-four", "lidia-full-generator"):
            case = original[query]
            self.assertTrue(case["binding_established_for_all_returned_occurrences"])
            self.assertTrue(
                all(
                    f["numeric_disposition"] == "BOUND_REPLAY_CONTEXT"
                    for f in case["action_families"]
                )
            )
        # Re-use the same families in an explicitly unadopted supplement
        # fixture; class numeric approval must not bind this new context.
        altered = copy.deepcopy(self.frozen)
        case = copy.deepcopy(altered["groups"]["original"]["cases"][0])
        supplement = altered["groups"]["supplementary"]
        case["query_id"] = "unbound-reset-context"
        case["evidence_scope"]["case_id"] = case["query_id"]
        case["evidence_scope"]["group"] = "supplementary"
        case["evidence_scope"]["cohort_digest"] = supplement["cohort_digest"]
        case["numeric_adoption_applied"] = False
        case["evidence_scope"]["adoption_applied"] = False
        case["actual_review_statuses"] = []
        case["actual_review_audit_entries"] = 0
        supplement["cases"].append(case)
        for field in ("all_completed_query_counts", "supported_completed_query_counts"):
            for key, count in case["actual_after_decision"]["counts"].items():
                supplement[field][key] += count
        unbound = diagnose(altered)["groups"]["supplementary"]["cases"][-1]
        self.assertTrue(
            all(
                f["numeric_disposition"] == "NUMERIC_ACCEPTED_CONTEXT_NOT_YET_BOUND"
                for f in unbound["action_families"]
            )
        )

    def test_adoption_flag_without_binding_proof_never_claims_bound(self):
        for mutation in (
            "no_audit",
            "no_accepted_review",
            "wrong_release",
            "wrong_cohort",
            "scope_not_applied",
            "partial_rating",
        ):
            with self.subTest(mutation=mutation):
                altered = copy.deepcopy(self.frozen)
                group = altered["groups"]["original"]
                case = group["cases"][0]
                if mutation == "no_audit":
                    case["actual_review_audit_entries"] = 0
                elif mutation == "no_accepted_review":
                    case["actual_review_statuses"] = ["reviewed"]
                elif mutation == "wrong_release":
                    case["evidence_scope"]["release_digest"] = "other-release"
                elif mutation == "wrong_cohort":
                    case["evidence_scope"]["cohort_digest"] = "other-cohort"
                elif mutation == "scope_not_applied":
                    case["evidence_scope"]["adoption_applied"] = False
                else:
                    # Keep both source aggregates consistent while making this
                    # adopted case only partly rated: no per-family inference.
                    case["actual_after_decision"]["counts"]["fully_rated"] -= 1
                    for field in ("all_completed_query_counts", "supported_completed_query_counts"):
                        group[field]["fully_rated"] -= 1
                audited = diagnose(altered)["groups"]["original"]["cases"][0]
                self.assertFalse(audited["binding_established_for_all_returned_occurrences"])
                self.assertTrue(
                    all(
                        f["numeric_disposition"] == "ADOPTION_APPLIED_BINDING_NOT_ESTABLISHED"
                        for f in audited["action_families"]
                    )
                )

    def test_supported_denominator_and_numerator_drift_fail_closed(self):
        for key, value, message in (
            ("conditioned_feasible", 109, "denominator drift"),
            ("fully_rated", 1, "numerator drift"),
        ):
            with self.subTest(key=key):
                altered = copy.deepcopy(self.frozen)
                altered["groups"]["supplementary"]["supported_completed_query_counts"][key] = value
                with self.assertRaisesRegex(ValueError, message):
                    diagnose(altered)

    def test_diagnostic_projection_cannot_silently_join_supported_cohort(self):
        altered = copy.deepcopy(self.frozen)
        projection = next(
            c
            for c in altered["groups"]["supplementary"]["cases"]
            if c["query_id"] == "acl-group-projection"
        )
        projection["supported_cohort"] = True
        with self.assertRaisesRegex(ValueError, "drift: supplementary/supported_completed"):
            diagnose(altered)

    def test_source_provenance_is_preserved_and_content_fingerprinted(self):
        before = copy.deepcopy(self.frozen)
        result = diagnose(self.frozen)
        for key in ("release_digest", "execution_identity", "raw_input_identity"):
            self.assertEqual(result[key], self.frozen[key])
        for name, group in result["groups"].items():
            self.assertEqual(group["cohort_digest"], self.frozen["groups"][name]["cohort_digest"])
            self.assertEqual(
                group["cases"][0]["evidence_scope"],
                self.frozen["groups"][name]["cases"][0]["evidence_scope"],
            )
        altered = copy.deepcopy(self.frozen)
        altered["limitations"].append("changed same-version source")
        self.assertNotEqual(
            result["source_report_digest"], diagnose(altered)["source_report_digest"]
        )
        self.assertEqual(self.frozen, before)

    def test_cli_output_records_exact_input_bytes_and_both_denominators(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "nested" / "audit.json"
            process = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "scripts.research.final_cpi_wave2_audit",
                    "--report",
                    str(REPORT),
                    "--output",
                    str(output),
                ],
                cwd=REPORT.parents[2],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(process.returncode, 0, process.stderr)
            result = json.loads(output.read_text())
            expected_digest = "sha256:" + hashlib.sha256(REPORT.read_bytes()).hexdigest()
            self.assertEqual(result["source_report_file_sha256"], expected_digest)
            group = result["groups"]["supplementary"]
            self.assertEqual(group["all_completed_query_counts"]["conditioned_feasible"], 109)
            self.assertEqual(group["supported_completed_query_counts"]["conditioned_feasible"], 7)

    def test_cli_rejects_output_identical_to_report(self):
        with tempfile.TemporaryDirectory() as directory:
            report_copy = Path(directory) / "source_replay.json"
            shutil.copyfile(REPORT, report_copy)
            hash_before = hashlib.sha256(report_copy.read_bytes()).hexdigest()
            process = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "scripts.research.final_cpi_wave2_audit",
                    "--report",
                    str(report_copy),
                    "--output",
                    str(report_copy),
                ],
                cwd=REPORT.parents[2],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(process.returncode, 0)
            self.assertIn("aliases protected report", process.stderr)
            self.assertEqual(hashlib.sha256(report_copy.read_bytes()).hexdigest(), hash_before)

    def test_cli_rejects_output_equivalent_path_variants(self):
        with tempfile.TemporaryDirectory() as directory:
            sub = Path(directory) / "nested"
            sub.mkdir()
            report_copy = sub / "source_replay.json"
            shutil.copyfile(REPORT, report_copy)
            hash_before = hashlib.sha256(report_copy.read_bytes()).hexdigest()
            variants = [
                sub / "." / "source_replay.json",
                sub / ".." / "nested" / "source_replay.json",
                report_copy.resolve(),
            ]
            for variant in variants:
                with self.subTest(variant=str(variant)):
                    process = subprocess.run(
                        [
                            sys.executable,
                            "-m",
                            "scripts.research.final_cpi_wave2_audit",
                            "--report",
                            str(report_copy),
                            "--output",
                            str(variant),
                        ],
                        cwd=REPORT.parents[2],
                        capture_output=True,
                        text=True,
                        check=False,
                    )
                    self.assertNotEqual(process.returncode, 0)
                    self.assertIn("aliases protected report", process.stderr)
                    self.assertEqual(
                        hashlib.sha256(report_copy.read_bytes()).hexdigest(), hash_before
                    )

    def test_cli_rejects_output_hardlink_to_report(self):
        with tempfile.TemporaryDirectory() as directory:
            report_copy = Path(directory) / "source_replay.json"
            shutil.copyfile(REPORT, report_copy)
            hardlink = Path(directory) / "hardlink_target.json"
            try:
                os.link(report_copy, hardlink)
            except OSError, NotImplementedError:
                self.skipTest("Hardlinks not supported on this platform/filesystem")
            hash_before = hashlib.sha256(report_copy.read_bytes()).hexdigest()
            process = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "scripts.research.final_cpi_wave2_audit",
                    "--report",
                    str(report_copy),
                    "--output",
                    str(hardlink),
                ],
                cwd=REPORT.parents[2],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(process.returncode, 0)
            self.assertIn("aliases protected report", process.stderr)
            self.assertEqual(hashlib.sha256(report_copy.read_bytes()).hexdigest(), hash_before)
            self.assertEqual(hashlib.sha256(hardlink.read_bytes()).hexdigest(), hash_before)

    def test_cli_rejects_output_symlink_to_report(self):
        with tempfile.TemporaryDirectory() as directory:
            report_copy = Path(directory) / "source_replay.json"
            shutil.copyfile(REPORT, report_copy)
            symlink = Path(directory) / "symlink_target.json"
            try:
                os.symlink(report_copy, symlink)
            except OSError, NotImplementedError:
                self.skipTest("Symlinks not supported on this platform/filesystem")
            hash_before = hashlib.sha256(report_copy.read_bytes()).hexdigest()
            process = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "scripts.research.final_cpi_wave2_audit",
                    "--report",
                    str(report_copy),
                    "--output",
                    str(symlink),
                ],
                cwd=REPORT.parents[2],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(process.returncode, 0)
            self.assertIn("aliases protected report", process.stderr)
            self.assertEqual(hashlib.sha256(report_copy.read_bytes()).hexdigest(), hash_before)

    def test_cli_protects_default_frozen_report_path(self):
        hash_before = hashlib.sha256(REPORT.read_bytes()).hexdigest()
        # Case A: --output points to default REPORT without --report flag
        process_default = subprocess.run(
            [
                sys.executable,
                "-m",
                "scripts.research.final_cpi_wave2_audit",
                "--output",
                str(REPORT),
            ],
            cwd=REPORT.parents[2],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertNotEqual(process_default.returncode, 0)
        self.assertIn("aliases protected report", process_default.stderr)
        self.assertEqual(hashlib.sha256(REPORT.read_bytes()).hexdigest(), hash_before)

        # Case B: --report points to custom input, but --output targets default frozen REPORT
        with tempfile.TemporaryDirectory() as directory:
            custom_report = Path(directory) / "custom_replay.json"
            shutil.copyfile(REPORT, custom_report)
            custom_hash_before = hashlib.sha256(custom_report.read_bytes()).hexdigest()
            process_custom = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "scripts.research.final_cpi_wave2_audit",
                    "--report",
                    str(custom_report),
                    "--output",
                    str(REPORT),
                ],
                cwd=REPORT.parents[2],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(process_custom.returncode, 0)
            self.assertIn("aliases protected report", process_custom.stderr)
            self.assertEqual(hashlib.sha256(REPORT.read_bytes()).hexdigest(), hash_before)
            self.assertEqual(
                hashlib.sha256(custom_report.read_bytes()).hexdigest(), custom_hash_before
            )

    def test_protect_output_helper_rejects_aliases_and_allows_distinct_path(self):
        with tempfile.TemporaryDirectory() as directory:
            report_copy = Path(directory) / "source_replay.json"
            shutil.copyfile(REPORT, report_copy)
            distinct_output = Path(directory) / "distinct.json"

            with self.assertRaisesRegex(ValueError, "aliases protected report"):
                protect_output(report_copy, [report_copy])
            with self.assertRaisesRegex(ValueError, "aliases protected report"):
                protect_output(Path(directory) / "." / "source_replay.json", [report_copy])

            protect_output(distinct_output, [report_copy, REPORT])


if __name__ == "__main__":
    unittest.main()
