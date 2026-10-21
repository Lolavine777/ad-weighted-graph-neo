"""Measure the existing source/goal pipeline on an explicitly pinned snapshot.

Setup, native query/wire execution, JSON output, and instrumented profiling are
reported separately. Run revisions sequentially; compare complete trace digests,
not only elapsed time. This runner changes no search or scoring semantics.
"""

from __future__ import annotations

import argparse
import cProfile
import functools
import hashlib
import json
import platform
import pstats
import subprocess
import time
from collections import defaultdict
from pathlib import Path

from src.engine import batch
from src.engine.graph import EngineGraph
from src.engine.semantics.evaluator import PreparedSemanticGraph
from src.parser.snapshot_facts import SnapshotFacts

ROOT = Path(__file__).resolve().parents[2]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--batch-request", type=Path, required=True)
    parser.add_argument("--source", required=True, help="One declared source_id")
    parser.add_argument("--technique", action="append", required=True)
    parser.add_argument("--trials", type=int, default=4, help="First use plus repeated warm calls")
    parser.add_argument("--profile", action="store_true", help="Separate instrumented execution")
    parser.add_argument("--output", type=Path, required=True, help="New local evidence directory")
    args = parser.parse_args(argv)
    if args.trials < 1:
        parser.error("--trials must be positive")
    args.output.mkdir(parents=True, exist_ok=False)
    started = time.perf_counter()
    graph = EngineGraph.from_snapshot(args.snapshot.read_text(encoding="utf-8"))
    request = batch._parse_request(json.loads(args.batch_request.read_text(encoding="utf-8")))
    goals = batch._validate_request(request, graph)
    matches = [s for s in request.sources if s.source_id == args.source]
    if len(matches) != 1:
        raise ValueError("source must identify exactly one declared source_id")
    queries = []
    for goal in goals:
        query, unsupported = batch._query_for_cell(
            request, matches[0], goal, graph, args.technique, request.common_budget
        )
        if unsupported is not None:
            raise ValueError("benchmark source is unsupported; use a supported profile")
        queries.append((goal, query))
    setup_seconds = time.perf_counter() - started
    phases = defaultdict(lambda: {"seconds": 0.0, "calls": 0})
    originals = []

    def instrument(owner, name):
        original = getattr(owner, name)

        @functools.wraps(original)
        def wrapped(*a, **kw):
            start = time.perf_counter()
            try:
                return original(*a, **kw)
            finally:
                row = phases[f"{owner.__name__}.{name}"]
                row["seconds"] += time.perf_counter() - start
                row["calls"] += 1

        originals.append((owner, name, original))
        setattr(owner, name, wrapped)

    profiler = cProfile.Profile()
    if args.profile:
        instrument(EngineGraph, "to_canonical")
        instrument(PreparedSemanticGraph, "__init__")
        instrument(SnapshotFacts, "validate_binding")
        profiler.enable()
    trials = []
    try:
        for trial_id in range(args.trials):
            rows = {}
            for goal, query in queries:
                start = time.perf_counter()
                cell, trace = batch._evaluate(query, graph, goal)
                query_seconds = time.perf_counter() - start
                start = time.perf_counter()
                payload = json.dumps(trace, sort_keys=True, ensure_ascii=False).encode("utf-8")
                (args.output / f"trace-{trial_id}-{goal.goal_id}.json").write_bytes(payload)
                rows[goal.goal_id] = {
                    "query_and_wire_seconds": query_seconds,
                    "json_and_write_seconds": time.perf_counter() - start,
                    "status": cell["status"],
                    "expansions": cell["expansions"],
                    "paths": len(trace["result"]["paths"]),
                    "trace_sha256": hashlib.sha256(payload).hexdigest(),
                }
            trials.append(rows)
    finally:
        if args.profile:
            profiler.disable()
        for owner, name, original in reversed(originals):
            setattr(owner, name, original)
    if args.profile:
        profiler.dump_stats(str(args.output / "profile.pstats"))
        with (args.output / "profile.txt").open("w", encoding="utf-8") as stream:
            pstats.Stats(profiler, stream=stream).strip_dirs().sort_stats("cumulative").print_stats(
                70
            )
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    changed = subprocess.check_output(
        ["git", "diff", "HEAD", "--name-only"], cwd=ROOT, text=True
    ).splitlines()
    report = {
        "version": "awg-discovery-benchmark/1",
        "revision": revision,
        "tracked_changes": changed,
        "python": platform.python_version(),
        "source_pins": batch.execution_source_pins(),
        "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "input_sha256": {
            "snapshot": hashlib.sha256(args.snapshot.read_bytes()).hexdigest(),
            "request": hashlib.sha256(args.batch_request.read_bytes()).hexdigest(),
        },
        "source_id": args.source,
        "techniques": args.technique,
        "setup_seconds": setup_seconds,
        "instrumented": args.profile,
        "nested_inclusive_phases": dict(phases),
        "trials": trials,
        "limitations": [
            "Single declared source and selected goals/techniques/budgets only.",
            "Nested inclusive phases overlap; do not add them.",
            "First use and warm queries share one prepared EngineGraph per process.",
            "Use separate uninstrumented runs for wall-clock comparisons.",
        ],
    }
    (args.output / "summary.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps({"trials": len(trials), "goals": len(goals), "profile": args.profile}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
