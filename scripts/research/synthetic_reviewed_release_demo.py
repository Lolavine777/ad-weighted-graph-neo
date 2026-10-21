"""Create test-only Issue #171 declarations and run export -> validation -> engine.

All identities, timestamps, ratings and decisions here are deliberately synthetic.
This example never writes actual pending sheets or declares human acceptance.
"""

from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.research import reviewed_parameter_release as tool  # noqa: E402

FIXTURES = ROOT / "tests/fixtures/ranking"


def synthetic_inputs(tmp_path):
    inputs = {"template": tool.load_snapshot(FIXTURES / "seamless_parameter_bundle.json")}
    for i in (1, 2):
        sheet = json.loads((FIXTURES / f"seamless_rater_{i}.json").read_bytes())
        sheet["sheet_id"] = f"synthetic-171-{i}"
        sheet["evidence_class"] = "synthetic_test_only"
        sheet["status"] = "rated"
        sheet["rater"].update(
            evaluator=f"synthetic-171-rater-{i}",
            name=f"Synthetic test rater {i}",
            competence_and_scope="Test declaration only, no real evaluator",
            independence_declaration="Synthetic fixture, no human rating",
            rated_at="2000-01-01T00:00:00Z",
        )
        for group in tool.GROUPS.values():
            for r in sheet[group]:
                r.update(rating_status="rated", evaluator=sheet["rater"]["evaluator"])
        for r in sheet["impact_ratings"]:
            r.update(consequence_rating="Critical", business_rationale="Synthetic impact only")
        for r in sheet["likelihood_ratings"]:
            r.update(
                conditional_bounds={"lower": "1/2", "upper": "3/4"},
                basis_category="scenario_assumption",
                uncertainty_rationale="Synthetic full-history test interval",
                source_references=["synthetic-test-171"],
            )
        for r in sheet["effort_ratings"]:
            r.update(
                rubric_evaluation={
                    "t1_complexity": 2,
                    "t2_friction": 2,
                    "formula": "base",
                    "computed_cost": 2,
                },
                effort_rationale="Synthetic effort only",
                overlap_analysis={
                    "is_independent": True,
                    "shared_preparation_tags": [],
                    "prerequisite_dependencies": [],
                },
            )
        path = tmp_path / f"synthetic-sheet-{i}.json"
        path.write_text(json.dumps(sheet), encoding="utf-8")
        inputs[f"sheet{i}"] = tool.load_snapshot(path)
    return inputs


def synthetic_decisions(inputs):
    report = tool.reconcile_inputs(inputs)
    declarations = []
    for category, pairs in report["reconciled_pairs"].items():
        for pair in pairs:
            final = copy.deepcopy(pair["raw_records"][0])
            final["evaluator"] = "synthetic-171-reviewer"
            declarations.append(
                {
                    "category": category,
                    "pair_digest": tool.digest(pair),
                    "binding": copy.deepcopy(pair["binding"]),
                    "disposition": "reviewed",
                    "final_record": final,
                    "reviewer_identity": "synthetic-171-reviewer",
                    "declared_at": "2000-01-02T00:00:00Z",
                    "rationale": "Synthetic explicit choice, not human acceptance",
                    "resolution": "Synthetic disagreement/uncertainty/overlap reviewed",
                    "decision_reference": f"synthetic-test-171:{tool.digest(pair)}",
                }
            )
    return {
        "schema_version": "1.0.0",
        "release_id": "synthetic-171",
        "release_version": "1.0.0",
        "evidence_class": "synthetic_test_only",
        "input_digests": {k: v["digest"] for k, v in inputs.items()},
        "report_digest": tool.digest(report),
        "decisions": declarations,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        # Exclusive directory creation means reruns never overwrite prior evidence.
        args.directory.mkdir(parents=True, exist_ok=False)
        inputs = synthetic_inputs(args.directory)
        decisions = synthetic_decisions(inputs)
        tool.reconciliation.write_report_safely(decisions, args.directory / "decisions.json")
        release = tool.export_release(inputs, decisions)
        validation = tool.validate_and_sensitivity(release)
        tool.reconciliation.write_report_safely(release, args.directory / "release.json")
        tool.reconciliation.write_report_safely(validation, args.directory / "validation.json")
        print(
            json.dumps(
                {
                    "evidence_class": "synthetic_test_only",
                    "release_digest": release["bundle_metadata"]["bundle_digest"],
                    "validation_report_digest": validation["report_digest"],
                }
            )
        )
        return 0
    except (ValueError, TypeError, KeyError, OSError) as err:
        print(f"Error: {err}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
