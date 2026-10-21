"""Validate and package the selected AWG-R03 native comparisons without overwrites."""

from __future__ import annotations

import argparse
import hashlib
import json
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

FIXTURES = ("two-routes", "asrep", "rbcd", "rbcd-padding-1000")


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write(path: Path, data: object) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def native_case(row: dict) -> dict:
    return {
        key: value
        for key, value in row["native"].items()
        if key not in {"materialize_seconds", "search_seconds"}
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs", required=True, type=Path)
    parser.add_argument("--before", default="final-before")
    parser.add_argument("--after", default="final-after")
    parser.add_argument("--acceptance", required=True, type=Path)
    parser.add_argument("--correctness-before", required=True, type=Path)
    parser.add_argument("--audited-baseline", required=True, type=Path)
    parser.add_argument("--junit", required=True, type=Path)
    parser.add_argument("--checks", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("output must be a new directory")

    final = read(args.acceptance / "f1-results.json")
    before = read(args.correctness_before / "f1-results.json")
    baseline = read(args.audited_baseline / "f1-results.json")
    assert final["summary"]["variant_count"] == before["summary"]["variant_count"] == 78
    assert final["summary"]["mismatches"] == before["summary"]["mismatches"] == []
    for old, new in zip(before["cases"], final["cases"], strict=True):
        assert (old["case"], old["variant"]) == (new["case"], new["variant"])
        assert old["input_sha256"] == new["input_sha256"]
        assert old["oracle"] == new["oracle"]
        assert native_case(old) == native_case(new), (new["case"], new["variant"])
    shared = read(args.acceptance / "shared-work.json")
    assert shared["min_effort"]["minimum_effort_value"] == 5
    assert shared["top_k"]["guarantee"]["is_k_best_proven"]
    assert all(
        p["likelihood_interval"] is None and p["impact"] is None
        for p in shared["top_k"]["programs"]
    )
    junit = ET.parse(args.junit).getroot()
    suites = junit.iter("testsuite")
    counts = {key: 0 for key in ("tests", "failures", "errors", "skipped")}
    for suite in suites:
        for key in counts:
            counts[key] += int(suite.attrib.get(key, 0))
    assert counts["tests"] > 0 and counts["failures"] == counts["errors"] == 0, counts
    # Pytest's suite total includes successful subtests without separate testcase
    # elements. Keep those checks distinct from collected repository test cases.
    case_count = sum(1 for _ in junit.iter("testcase"))
    skipped_cases = sum(case.find("skipped") is not None for case in junit.iter("testcase"))
    assert 0 < case_count <= counts["tests"]
    assert skipped_cases == counts["skipped"]
    test_counts = {
        **counts,
        "tests": case_count,
        "passed": case_count - skipped_cases,
        "passed_subtests": counts["tests"] - case_count,
        "junit_reported_tests": counts["tests"],
    }
    checks = read(args.checks)
    assert checks["results"] and all(row["exit_code"] == 0 for row in checks["results"])

    summary = {
        "f1": final["summary"],
        "validated_witnesses": sum(row["native"]["path_count"] for row in final["cases"]),
        "shared_work_minimum_C": 5,
        "shared_work_P_I": "unrated",
        "pytest": test_counts,
        "optimization_preserves_all_78_native_outputs": True,
        "correctness_deltas": [
            {
                "case": old["case"],
                "variant": old["variant"],
                "baseline_paths": old["native"]["path_count"],
                "corrected_paths": new["native"]["path_count"],
            }
            for old, new in zip(baseline["cases"], final["cases"], strict=True)
            if old["native"]["path_count"] != new["native"]["path_count"]
        ],
        "fixtures": [],
    }
    directories = []
    for fixture in FIXTURES:
        modes = {}
        for label, prefix in (("before", args.before), ("after", args.after)):
            directory = args.runs / f"{prefix}-{fixture}"
            profile_directory = args.runs / f"{prefix}-profile-{fixture}"
            data = read(directory / "native-measurement.json")
            profile = read(profile_directory / "native-measurement.json")
            assert data["fixture"] == profile["fixture"] == fixture
            for key in (
                "revision",
                "tree",
                "tracked_changes",
                "patch_sha256",
                "runner_sha256",
                "python",
                "platform",
                "dependencies",
                "frozen_manifest_sha256",
                "verified_frozen_files",
                "frozen_experiment_sha256",
            ):
                assert data["provenance"][key] == profile["provenance"][key], (fixture, key)
            assert not profile["provenance"]["tracked_changes"]
            assert data["input_sha256"] == profile["input_sha256"]
            assert len(data["samples"]) == 4
            assert len({sample["digest"] for sample in data["samples"]}) == 1
            for sample in data["samples"]:
                phases = (
                    "graph_seconds",
                    "materialize_seconds",
                    "search_seconds",
                    "replay_seconds",
                    "rating_exclusive_seconds",
                    "serialization_seconds",
                )
                assert all(sample[key] >= 0 for key in phases)
                assert abs(sum(sample[key] for key in phases) - sample["total_seconds"]) < 1e-8
            full_bytes = (directory / "full-semantic.json").read_bytes().removesuffix(b"\n")
            assert hashlib.sha256(full_bytes).hexdigest() == data["full_semantic_sha256"]
            profile_bytes = (
                (profile_directory / "full-semantic.json").read_bytes().removesuffix(b"\n")
            )
            assert hashlib.sha256(profile_bytes).hexdigest() == profile["full_semantic_sha256"]
            assert data["full_semantic_sha256"] == profile["full_semantic_sha256"]
            modes[label] = {"measurement": data, "profile": profile}
            directories.extend((directory, profile_directory))
        old, new = (modes[label]["measurement"] for label in ("before", "after"))
        assert old["provenance"]["revision"] == before["commit"]
        assert new["provenance"]["revision"] == final["commit"]
        assert old["provenance"]["revision"] != new["provenance"]["revision"]
        assert not old["provenance"]["tracked_changes"]
        assert not new["provenance"]["tracked_changes"]
        assert old["provenance"]["runner_sha256"] == new["provenance"]["runner_sha256"]
        assert old["provenance"]["python"] == new["provenance"]["python"]
        assert old["provenance"]["platform"] == new["provenance"]["platform"]
        assert old["provenance"]["dependencies"] == new["provenance"]["dependencies"]
        assert old["input_sha256"] == new["input_sha256"]
        assert old["samples"][0]["digest"] == new["samples"][0]["digest"]
        assert old["full_semantic_sha256"] == new["full_semantic_sha256"]
        summary["fixtures"].append({"name": fixture, "full_semantic_equal": True, **modes})

    args.output.mkdir(parents=True)
    write(args.output / "summary.json", summary)
    files = {
        args.output / "summary.json": "summary.json",
        args.junit: "verification/pytest.xml",
        args.checks: "verification/checks.json",
    }
    for root, prefix in [
        (args.acceptance, "acceptance"),
        (args.correctness_before, "correctness-before"),
        (args.audited_baseline, "audited-baseline"),
    ]:
        for path in root.rglob("*"):
            if path.is_file() and "__pycache__" not in path.parts:
                files[path] = f"{prefix}/{path.relative_to(root).as_posix()}"
    for root in directories:
        for path in root.rglob("*"):
            if path.is_file() and "__pycache__" not in path.parts:
                files[path] = f"runs/{root.name}/{path.relative_to(root).as_posix()}"
    manifest = {name: hashlib.sha256(path.read_bytes()).hexdigest() for path, name in files.items()}
    archive = args.output / "AWG-R03_Verification.zip"
    with zipfile.ZipFile(
        archive, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
    ) as package:
        package.writestr(
            "MANIFEST-SHA256.json", json.dumps(manifest, sort_keys=True, indent=2) + "\n"
        )
        for path, name in sorted(files.items(), key=lambda pair: pair[1]):
            package.write(path, name)
    write(
        args.output / "manifest.json",
        {
            "archive": archive.name,
            "sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
            "entries": len(files) + 1,
        },
    )
    print(
        json.dumps(
            {
                "pytest": summary["pytest"],
                "witnesses": summary["validated_witnesses"],
                "archive": str(archive),
            }
        )
    )


if __name__ == "__main__":
    main()
