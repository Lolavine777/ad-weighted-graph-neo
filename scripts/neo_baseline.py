"""Reproduce the pinned SEAMLESS machine-to-DA baseline through the native CLI."""

from __future__ import annotations

import argparse
import json
import platform
import subprocess
import sys
import time
from pathlib import Path

from scripts.download_seamless import install
from scripts.exposure import build_request, inventory_exposure
from scripts.research.asrep_inputs import seamless_inputs
from scripts.research.source_goal_batch import BatchQueryRequest
from src.engine.batch import _query_for_cell
from src.engine.query import run_attack_query
from src.engine.query_cli import canonical_json, digest, wire
from src.engine.ranking.reset_effort import MACHINE_PROFILE_ID, load_reset_effort_profile
from src.engine.semantics.credentials import replay_path
from src.engine.semantics.scenario_policy import load_policy_profile
from src.parser.snapshot_facts import serialize_snapshot

ROOT = Path(__file__).resolve().parents[1]
HOST = "S-1-5-21-1271839998-3495686680-2211690266-4157"
TECHNIQUES = ("scenario_reset_password", "acquire_reset_identity", "propagate_group_entitlement")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=False)
    raw = ROOT / "data/raw/SEAMLESS"
    install(raw)
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    started = time.perf_counter()
    graph, *_ = seamless_inputs(raw, revision)
    assert (len(graph.nodes()), len(graph.edges())) == (3370, 56367)
    snapshot = output / "snapshot.json"
    snapshot.write_text(
        serialize_snapshot(graph.to_canonical(), graph.snapshot_facts), encoding="utf-8"
    )
    inventory = inventory_exposure(graph)
    request, _ = build_request(
        graph,
        inventory,
        source_ids=[HOST],
        authentication_context=HOST,
        computer_profile="computer_usable_identity",
        machine_identity_provenance="scenario://neo/machine-identity/FINWVIR-4157",
        max_sources=0,
        max_targets=0,
        evaluation_mode="scenario",
        budget={"max_paths": 1, "max_steps": 3, "max_expansions": 6000},
    )
    request = BatchQueryRequest.from_dict(request)
    goal = next(
        g
        for g in request.resolve_target_goals()
        if g.target_node_id == inventory["domain_sid"] + "-512"
    )
    query, error = _query_for_cell(
        request,
        request.sources[0],
        goal,
        graph,
        TECHNIQUES,
        request.common_budget,
        scenario_policy=load_policy_profile("seamless-standard-v1"),
        effort_profile=load_reset_effort_profile(MACHINE_PROFILE_ID),
    )
    assert error is None, error
    query_path = output / "query.json"
    query_path.write_text(json.dumps(query, indent=2) + "\n", encoding="utf-8")
    summary = {
        "revision": revision,
        "python": sys.version,
        "platform": platform.platform(),
        "nodes": 3370,
        "edges": 56367,
        "snapshot_sha256": digest(snapshot.read_bytes()),
        "query_sha256": digest(query_path.read_bytes()),
        "preparation_seconds": time.perf_counter() - started,
        "runs": [],
    }
    guided = None
    for order in ("fifo", "goal_guided"):
        destination = output / f"{order}.json"
        command = [
            sys.executable,
            "-m",
            "src.engine",
            "query",
            "--snapshot",
            str(snapshot),
            "--query",
            str(query_path),
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
        subprocess.run(command, cwd=ROOT, check=True)
        wall_seconds = time.perf_counter() - clock
        package = json.loads(destination.read_text(encoding="utf-8"))
        semantic = package["semantic"]
        semantic_hash = digest(canonical_json(semantic).encode("utf-8"))
        assert semantic_hash == package["reproducibility"]["semantic_sha256"]
        summary["runs"].append(
            {
                "search_order": order,
                "wall_seconds": wall_seconds,
                "expansions": semantic["expansions"],
                "witnesses": len(semantic["candidates"]),
                "best_C": semantic["min_effort"]["minimum_effort_value"],
                "truncated": semantic["truncated"],
                "guarantees": semantic["engine_reported_guarantees"],
                "semantic_sha256": semantic_hash,
                "command": command,
            }
        )
        if order == "goal_guided":
            guided = semantic
    native = run_attack_query({**query, "search_order": "goal_guided"}, graph)
    assert native.paths and native.min_effort["minimum_effort_value"] == 1
    assert native.min_effort["associated_likelihood_interval"] is None
    assert native.min_effort["associated_impact"] is None
    assert wire(native.paths) == [
        {k: v for k, v in p.items() if k != "candidate_id"} for p in guided["candidates"]
    ]
    assert wire(native.min_effort) == guided["min_effort"]
    assert wire(native.rating_coverage) == guided["rating_coverage"]
    for path in native.paths:
        assert replay_path(path, graph) == path.final_state
    summary["native_replay_and_API_CLI_parity"] = True
    (output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
