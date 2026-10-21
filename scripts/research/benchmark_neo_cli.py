"""Alternate unchanged-input native CLI trials across two AWG checkouts on macOS."""

from __future__ import annotations

import argparse
import json
import platform
import statistics
import subprocess
import sys
import time
from pathlib import Path

from src.engine.query_cli import canonical_json, digest

ROOT = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline-root", type=Path, required=True)
    parser.add_argument("--query-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=False)
    inputs = args.query_dir.resolve()
    roots = {"before": args.baseline_root.resolve(), "after": ROOT}
    packet = {
        "python": sys.version,
        "platform": platform.platform(),
        "scope": "One pinned machine-to-DA query; compact native CLI, macOS time -l peak RSS",
        "trials_per_variant_and_order": 3,
        "input_sha256": {
            p: digest((inputs / p).read_bytes()) for p in ("query.json", "snapshot.json")
        },
        "variants": {
            name: {
                "revision": subprocess.check_output(
                    ["git", "rev-parse", "HEAD"], cwd=root, text=True
                ).strip(),
                "query_cli_sha256": digest((root / "src/engine/query_cli.py").read_bytes()),
            }
            for name, root in roots.items()
        },
        "trials": [],
    }
    hashes = {}
    for trial in range(1, 4):
        for order in ("fifo", "goal_guided"):
            variants = ("before", "after") if trial % 2 else ("after", "before")
            for variant in variants:
                destination = output / f"{variant}-{order}.json"
                command = [
                    sys.executable,
                    "-m",
                    "src.engine",
                    "query",
                    "--snapshot",
                    str(inputs / "snapshot.json"),
                    "--query",
                    str(inputs / "query.json"),
                    "--search-order",
                    order,
                    "--label",
                    "seamless",
                    "--prerequisite",
                    str(ROOT / "data/samples/manifests/seamless-raw-v1.json"),
                    "--compact-output",
                    "--output",
                    str(destination),
                ]
                clock = time.perf_counter()
                process = subprocess.run(
                    ["/usr/bin/time", "-l", *command],
                    cwd=roots[variant],
                    capture_output=True,
                    text=True,
                    check=True,
                )
                elapsed = time.perf_counter() - clock
                package = json.loads(destination.read_text(encoding="utf-8"))
                semantic = package["semantic"]
                semantic_hash = digest(canonical_json(semantic).encode("utf-8"))
                assert semantic_hash == package["reproducibility"]["semantic_sha256"]
                assert semantic_hash == hashes.setdefault(order, semantic_hash), "Semantic drift"
                row = {
                    "trial": trial,
                    "variant": variant,
                    "search_order": order,
                    "wall_seconds": elapsed,
                    "reported_seconds": package["runtime"]["duration_seconds"],
                    "peak_rss_bytes": int(
                        next(
                            line.split()[0]
                            for line in process.stderr.splitlines()
                            if "maximum resident set size" in line
                        )
                    ),
                    "semantic_sha256": semantic_hash,
                    "expansions": semantic["expansions"],
                    "witnesses": len(semantic["candidates"]),
                    "best_C": semantic["min_effort"]["minimum_effort_value"],
                    "guarantees": semantic["engine_reported_guarantees"],
                }
                packet["trials"].append(row)
                print(json.dumps(row), flush=True)
    packet["medians"] = {
        variant: {
            order: {
                key: statistics.median(
                    r[key]
                    for r in packet["trials"]
                    if r["variant"] == variant and r["search_order"] == order
                )
                for key in ("wall_seconds", "reported_seconds", "peak_rss_bytes")
            }
            for order in ("fifo", "goal_guided")
        }
        for variant in roots
    }
    packet["complete_semantic_parity"] = True
    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(packet, indent=2) + "\n")


if __name__ == "__main__":
    main()
