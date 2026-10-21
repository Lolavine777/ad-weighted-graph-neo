"""Compare native revisions using immutable R02 fixtures and independent finite oracles.

Run each benchmark fixture/revision in a fresh process, sequentially.
The retained R02 trial instruments phase boundaries, supplies precomputed search
to rating, and times internal replay, without changing production semantics.
Historical catalog-cache and state-merge alternatives are never enabled here.
After measurements, a separate untimed native execution retains the complete
public semantic result, including query materialization and guarantee flags.
"""

from __future__ import annotations

import argparse
import cProfile
import hashlib
import importlib.metadata
import json
import platform
import pstats
import shutil
import subprocess
import sys
import time
from pathlib import Path

FIXTURES = ("two-routes", "asrep", "rbcd", "rbcd-padding-1000")


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def save(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def git(repo: Path, *args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=repo, text=True).strip()


def prepare(args: argparse.Namespace) -> tuple[Path, dict]:
    repo, frozen, output = (p.resolve() for p in (args.repo, args.evidence_root, args.output))
    if output.is_relative_to(frozen) or frozen.is_relative_to(output):
        raise ValueError("output must be separate from frozen evidence")
    if output.exists():
        raise ValueError("output must be a new directory")
    verified = {}
    for entry in (frozen / "MANIFEST-SHA256.txt").read_text().splitlines():
        expected, name = entry.split(maxsplit=1)
        source = (frozen / name.lstrip(" *")).resolve()
        if not source.is_relative_to(frozen) or digest(source.read_bytes()) != expected:
            raise ValueError(f"frozen evidence checksum mismatch: {name}")
        verified[name] = expected
    output.mkdir(parents=True)
    harness = output / "harness"
    shutil.copytree(frozen / "experiments", harness / "experiments")
    (harness / "evidence").mkdir()
    cases = harness / "experiments/cases.py"
    original = cases.read_text()
    anchor = 'BASE = ROOT / "baseline"'
    if original.count(anchor) != 1:
        raise ValueError("unexpected historical harness source anchor")
    cases.write_text(original.replace(anchor, f"BASE = Path({str(repo)!r})"))
    sys.path.insert(0, str(harness / "experiments"))
    sys.path.insert(0, str(repo))
    provenance = {
        "revision": git(repo, "rev-parse", "HEAD"),
        "tree": git(repo, "rev-parse", "HEAD^{tree}"),
        "tracked_changes": git(repo, "diff", "HEAD", "--name-only").splitlines(),
        "patch_sha256": digest(
            subprocess.check_output(["git", "diff", "HEAD", "--binary"], cwd=repo)
        ),
        "python": sys.version,
        "platform": platform.platform(),
        "dependencies": {
            name: importlib.metadata.version(name)
            for name in ("networkx", "PyYAML", "pytest", "jsonschema")
        },
        "command": sys.argv,
        "runner_sha256": digest(Path(__file__).read_bytes()),
        "frozen_manifest_sha256": digest((frozen / "MANIFEST-SHA256.txt").read_bytes()),
        "verified_frozen_files": len(verified),
        "frozen_experiment_sha256": {
            p.name: digest(p.read_bytes()) for p in sorted((frozen / "experiments").glob("*.py"))
        },
        "scratch_adaptations": ["cases.BASE points to the explicitly selected native checkout"],
    }
    save(output / "provenance.json", provenance)
    return harness, provenance


def correctness(output: Path, harness: Path, provenance: dict, baseline: bool) -> None:
    import run_ablation

    run_ablation.main()
    results = json.loads((harness / "evidence/f1-results.json").read_text())
    summary = results["summary"]
    assert summary["variant_count"] == 78
    if baseline:
        assert len(summary["mismatches"]) == 1, summary
        assert summary["mismatches"][0]["case"] == 9
    else:
        assert summary["mismatches"] == [], summary
        import cases

        actor = next(row for row in results["cases"] if row["case"] == 9)
        expected = [
            (cases.IDS[a], cases.IDS[h]) for a, h in (("U", "H1"), ("V", "H2"), ("U", "H3"))
        ]
        assert any(
            [(r["actor"], r["target"]) for r in path["requests"]] == expected
            for path in actor["native"]["paths"]
        ), "the independently valid U:H1 -> V:H2 -> U:H3 ordering is missing"
    results["historical_runner_commit_label"] = results.pop("commit")
    results["commit"] = provenance["revision"]
    results["experiment"] = "AWG-R03/native-independent-comparison"
    results["provenance"] = provenance
    save(output / "f1-results.json", results)
    import run_cost_probe

    run_cost_probe.main()
    cost = json.loads((harness / "evidence/f1-shared-work-native-rating.json").read_text())
    assert cost["min_effort"]["minimum_effort_value"] == 5
    assert cost["top_k"]["guarantee"]["is_k_best_proven"]
    assert cost["min_effort"]["associated_likelihood_interval"] is None
    assert cost["min_effort"]["associated_impact"] is None
    assert all(
        program["likelihood_interval"] is None and program["impact"] is None
        for program in cost["top_k"]["programs"]
    )
    save(output / "shared-work.json", {"provenance": provenance, **cost})
    print(json.dumps(summary), flush=True)


def profile(callable_, output: Path, name: str, repo: Path) -> dict:
    profiler = cProfile.Profile()
    profiler.runcall(callable_)
    profiler.dump_stats(str(output / f"{name}.pstats"))
    stats = pstats.Stats(profiler)
    rows = []
    parses = validations = 0
    for (file, line, function), (primitive, calls, own, cumulative, callers) in stats.stats.items():
        normalized = file.replace(str(repo), "repository").replace("\\", "/")
        rows.append(
            dict(
                file=normalized,
                line=line,
                name=function,
                primitive_calls=primitive,
                calls=calls,
                own_seconds=own,
                cumulative_seconds=cumulative,
            )
        )
        if function == "safe_load":
            for (caller_file, _, _), values in callers.items():
                if caller_file.replace("\\", "/").endswith("/semantics/catalog.py"):
                    parses += values[1] if isinstance(values, tuple) else values
        if function == "validate_catalog" and normalized.endswith("/semantics/catalog.py"):
            validations += calls
    rows.sort(key=lambda row: row["cumulative_seconds"], reverse=True)
    return {
        "total_seconds": stats.total_tt,
        "catalog_yaml_parses": parses,
        "catalog_validations": validations,
        "catalog_and_replay": [
            row
            for row in rows
            if "/semantics/catalog.py" in row["file"]
            or row["name"] in {"evaluate_rbcd", "replay_path", "replay_candidate_sequence"}
        ],
        "top_cumulative": rows[:30],
    }


def measure(args: argparse.Namespace, harness: Path, provenance: dict) -> None:
    source = harness / "experiments/profile_pipeline.py"
    original = source.read_text()
    source.write_text(
        original.replace("from src.engine.semantics.credentials import _recipe\n", "")
    )
    provenance["scratch_adaptations"].append(
        "remove unused private-cache import from historical counterfactual main; "
        "call native fixture/trial only"
    )
    import profile_pipeline as pipeline

    from src.engine.semantics.catalog import load_catalog

    # Report native immutable-catalog construction explicitly, before input builders
    # can prepare a query and implicitly warm it. This is separate from request total.
    start = time.perf_counter()
    if args.mode == "profile":
        catalog_profile = profile(load_catalog, args.output, "catalog-setup", args.repo)
    else:
        load_catalog()
    catalog_setup_seconds = time.perf_counter() - start
    fixture_start = time.perf_counter()
    load, query, metadata = pipeline.fixture(args.fixture)
    fixture_setup_seconds = time.perf_counter() - fixture_start
    input_file = harness / f"evidence/f2-input-{args.fixture}.json"
    result = dict(
        fixture=args.fixture,
        metadata=metadata,
        provenance=provenance,
        input_sha256=digest(input_file.read_bytes()),
        catalog_setup_seconds=catalog_setup_seconds,
        fixture_setup_seconds=fixture_setup_seconds,
        setup_disclosure=(
            "one native catalog load before fixture construction; first/warm pipeline queries "
            "follow it; factory cost is separate and includes graph/packet construction"
        ),
    )
    if args.mode == "benchmark":
        samples = []
        for index in range(4):
            sample = pipeline.trial(load, query)
            samples.append(sample)
            print(
                json.dumps(
                    dict(
                        fixture=args.fixture,
                        sample=index,
                        total=sample["total_seconds"],
                        digest=sample["digest"],
                    )
                ),
                flush=True,
            )
        assert len({sample["digest"] for sample in samples}) == 1
        result["samples"] = samples
        result["first_query"] = samples[0]
        result["first_query_plus_catalog_setup_seconds"] = (
            samples[0]["total_seconds"] + catalog_setup_seconds
        )
        warm = sorted(samples[1:], key=lambda sample: sample["total_seconds"])
        result["representative_warm_trial"] = warm[1]
        result["warm_ranges"] = {
            key: {"minimum": min(s[key] for s in warm), "maximum": max(s[key] for s in warm)}
            for key in samples[0]
            if key.endswith("_seconds")
        }
    else:
        # Separate process/invocation from wall-clock trials. cProfile times are diagnostic only.
        result["catalog_setup"] = catalog_profile
        result["first_pipeline"] = profile(
            lambda: pipeline.trial(load, query), args.output, "cold-pipeline", args.repo
        )
        result["warm_pipeline"] = profile(
            lambda: pipeline.trial(load, query), args.output, "warm-pipeline", args.repo
        )
        graph = load()
        materialized = pipeline.materialize_query(query, graph)
        result["search"] = profile(
            lambda: materialized.search(graph), args.output, "search", args.repo
        )
    from src.engine.query_cli import execute, wire

    # This extra execution is outside both timing samples and cProfile passes.
    # Compare the entire public semantic response, without CLI runtime/git metadata.
    complete_payload = json.dumps(
        wire(execute(query, load())), ensure_ascii=False, sort_keys=True, allow_nan=False
    ).encode()
    (args.output / "full-semantic.json").write_bytes(complete_payload + b"\n")
    result["full_semantic_sha256"] = digest(complete_payload)
    result["full_semantic_bytes"] = len(complete_payload)
    save(args.output / "native-measurement.json", result)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--evidence-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--mode", choices=("correctness", "benchmark", "profile"), required=True)
    parser.add_argument("--fixture", choices=FIXTURES)
    parser.add_argument("--expect-baseline", action="store_true")
    args = parser.parse_args()
    if args.mode != "correctness" and args.fixture is None:
        parser.error("--fixture is required for benchmark/profile")
    args.repo, args.output = args.repo.resolve(), args.output.resolve()
    harness, provenance = prepare(args)
    if args.mode == "correctness":
        correctness(args.output, harness, provenance, args.expect_baseline)
    else:
        measure(args, harness, provenance)


if __name__ == "__main__":
    main()
