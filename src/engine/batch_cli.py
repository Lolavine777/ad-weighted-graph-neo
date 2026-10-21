"""Local batch entry point over the existing public AttackQuery engine (#275)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from jsonschema.exceptions import ValidationError

from src.engine.batch import (
    BatchExecutionBudget,
    _atomic_json,
    discover_source,
    run_source_goal_batch,
)
from src.engine.graph import EngineGraph
from src.engine.query_cli import read_input


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch-request", required=True)
    parser.add_argument("--source", help="Run exactly one declared source_id with its full profile")
    parser.add_argument("--target-manifest", help="Replace embedded pinned manifest")
    targets = parser.add_mutually_exclusive_group()
    targets.add_argument("--discover", action="store_true")
    targets.add_argument("--goal", action="append", help="Manifest goal ID; repeat for drilldown")
    inputs = parser.add_mutually_exclusive_group(required=True)
    inputs.add_argument("--graph")
    inputs.add_argument("--snapshot")
    parser.add_argument("--label", required=True, choices=["synthetic", "private", "seamless"])
    parser.add_argument("--prerequisite", action="append", default=[])
    parser.add_argument("--rating-resolution")
    parser.add_argument("--runtime-facts", help="Observed facts; assumptions stay in request")
    parser.add_argument("--technique", action="append", help="Explicit technique scope; repeat")
    parser.add_argument("--checkpoint")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--output", required=True)
    parser.add_argument("--max-cells", type=int)
    parser.add_argument("--global-max-expansions", type=int)
    parser.add_argument("--global-seconds", type=float)
    parser.add_argument("--query-seconds", type=float)
    args = parser.parse_args(argv)
    references = {}
    try:
        if args.label != "synthetic" and not args.prerequisite:
            raise FileNotFoundError("private/SEAMLESS run requires explicit --prerequisite files")
        for i, path in enumerate(args.prerequisite):
            read_input(path, references, f"prerequisite_{i}")
        request = read_input(args.batch_request, references, "batch_request")
        if args.target_manifest:
            request["target_manifest"] = read_input(
                args.target_manifest, references, "target_manifest"
            )
        if args.discover:
            request["target_goal_ids"] = None
        elif args.goal is not None:
            request["target_goal_ids"] = args.goal
        if args.rating_resolution:
            request["rating_resolution"] = read_input(
                args.rating_resolution, references, "rating_resolution"
            )
        if args.snapshot:
            payload = read_input(args.snapshot, references, "snapshot")
            graph = EngineGraph.from_snapshot(json.dumps(payload))
        else:
            graph = EngineGraph.from_canonical(read_input(args.graph, references, "graph"))
        if args.label == "synthetic" and graph.metadata.get("synthetic") is not True:
            raise ValueError("synthetic label requires explicitly synthetic graph")
        runner = discover_source if args.source is not None else run_source_goal_batch
        selection = {"source_id": args.source} if args.source is not None else {}
        result = runner(
            request,
            graph,
            checkpoint=args.checkpoint,
            resume=args.resume,
            allowed_techniques=args.technique,
            runtime_facts=read_input(args.runtime_facts, references, "runtime_facts")
            if args.runtime_facts
            else (),
            execution_budget=BatchExecutionBudget(
                max_cells=args.max_cells,
                max_expansions=args.global_max_expansions,
                max_seconds=args.global_seconds,
                per_query_seconds=args.query_seconds,
            ),
            **selection,
        ).to_dict()
        result["reproducibility"]["runtime"]["label"] = args.label
        result["reproducibility"]["runtime"]["file_references"] = references
        _atomic_json(Path(args.output), result)
    except (OSError, ValueError, TypeError, KeyError, RuntimeError, ValidationError) as exc:
        print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
