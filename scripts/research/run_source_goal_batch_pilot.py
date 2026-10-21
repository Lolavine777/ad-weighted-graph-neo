"""Reproduce a declared #275 pilot on manifest-verified full SEAMLESS, no numeric adoption."""

import argparse
import copy
import json
import platform
import subprocess
import sys
import time
from pathlib import Path

from scripts.research.asrep_inputs import seamless_inputs
from src.data.manifest import load_manifest, verify_manifest
from src.engine.batch import _atomic_json, run_source_goal_batch
from src.engine.ranking.resolution_service import canonical_digest
from src.parser.snapshot_facts import serialize_snapshot

ROOT = Path(__file__).resolve().parents[2]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True, help="Private local results only")
    parser.add_argument("--sanitized-report", type=Path, required=True)
    parser.add_argument(
        "--target-manifest",
        type=Path,
        default=ROOT / "tests/fixtures/batch_contracts/target_manifest_seamless.json",
        help="Explicit successor goals; omitted preserves the historical pilot scope",
    )
    args = parser.parse_args(argv)
    manifest = load_manifest(ROOT / "data/samples/manifests/seamless-raw-v1.json")
    if verify_manifest(args.raw_dir, manifest):
        raise ValueError("SEAMLESS raw manifest failed before pilot")
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    started = time.perf_counter()
    graph, _, assumed, raw_trace = seamless_inputs(args.raw_dir, revision)
    owner = assumed["initial_state"]["known_identity"][0]
    host = assumed["authentication_context"]
    group = assumed["checkpoint_goal"]["target"]
    target_manifest = json.loads(args.target_manifest.read_text())
    # Every source is an independent scenario. No initial Group credentials,
    # no pooled compromise state, no implied identities from Computer control.
    profiles = [
        ("user-password", owner, "User", "user_leaked_password", host),
        ("user-identity", owner, "User", "user_usable_identity", host),
        ("computer-admin", host, "Computer", "computer_control_admin", host),
        ("computer-user", host, "Computer", "computer_control_user", host),
        ("group-unsupported", group, "Group", "unsupported", None),
    ]
    sources = []
    for sid, node_id, kind, profile, context in profiles:
        sources.append(
            {
                "source_id": sid,
                "node_id": node_id,
                "node_kind": kind,
                "profile_kind": profile,
                "authentication_context": context,
                "declared_assumptions": copy.deepcopy(assumed["assumptions"]),
                "description": "Independent scenario declaration; not observed compromise",
            }
        )
    request = {
        "schema_version": "batch-query-request/1.0.0",
        "batch_id": "issue275-seamless-pilot",
        "snapshot_id": graph.metadata["snapshot_id"],
        "evaluation_mode": "scenario",
        "prioritization_policy": "min_effort_impact_pareto",
        "sources": sources,
        "target_manifest": target_manifest,
        "target_goal_ids": None,
        "common_budget": {"max_paths": 10, "max_steps": 6, "max_expansions": 100},
    }
    techniques = [
        "activate_recovered_identity",
        "propagate_group_entitlement",
        "obtain_admin_execution_on_host",
        "scenario_winrm_admin",
    ]
    args.output_dir.mkdir(parents=True, exist_ok=True)
    _atomic_json(args.output_dir / "request.json", request)
    (args.output_dir / "snapshot.json").write_text(
        serialize_snapshot(graph.to_canonical(), graph.snapshot_facts), encoding="utf-8"
    )
    result = run_source_goal_batch(request, graph, allowed_techniques=techniques)
    _atomic_json(args.output_dir / "result.json", result.to_dict())
    raw_request = copy.deepcopy(request)
    raw_request["batch_id"] += "-evidence-only"
    raw_request["evaluation_mode"] = "evidence_only"
    raw_result = run_source_goal_batch(raw_request, graph, allowed_techniques=techniques)
    _atomic_json(args.output_dir / "evidence-only-result.json", raw_result.to_dict())
    if verify_manifest(args.raw_dir, manifest):
        raise ValueError("SEAMLESS raw manifest failed after pilot")
    try:
        import resource

        # This executable environment is Linux: ru_maxrss is in KiB.
        peak_rss = (
            resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024
            if sys.platform == "linux"
            else None
        )
    except ImportError:
        peak_rss = None
    report = {
        "version": "issue275-pilot-evidence/1.0.0",
        "revision": revision,
        "snapshot_id": graph.metadata["snapshot_id"],
        "graph_nodes": len(graph.nodes()),
        "graph_edges": len(graph.edges()),
        "graph_scope": "full manifest-verified snapshot",
        "source_scope": "five independently compromised profile scenarios; not all sources",
        "profiles": [p[3] for p in profiles],
        "kinds": [p[2] for p in profiles],
        "goal_ids": target_manifest["default_discovery_goals"],
        "allowed_techniques": techniques,
        "caps": request["common_budget"],
        "raw_verified_before_and_after": True,
        "raw_manifest_digest": canonical_digest(manifest),
        "request_digest": result.reproducibility["inputs"]["request_digest"],
        "scope_digest": result.reproducibility["inputs"]["scope_digest"],
        "source_pins": result.reproducibility["inputs"]["source_pins"],
        "raw_locators": raw_trace["locators"],
        "scenario": {
            "summary": result.summary,
            "rows": [
                {
                    "source_id": sid,
                    "cells": {
                        gid: {
                            key: cell.to_dict()[key]
                            for key in (
                                "status",
                                "checkpoint_reached",
                                "final_goal_reached",
                                "truncated",
                                "truncation_reason",
                                "expansions",
                                "min_effort",
                                "likelihood_status",
                            )
                        }
                        for gid, cell in row.items()
                    },
                }
                for sid, row in result.source_goal_matrix.items()
            ],
        },
        "evidence_only": {"summary": raw_result.summary},
        "numeric_adoption": "none; no proposed registries loaded",
        "runtime": {
            "python": platform.python_version(),
            "total_seconds": time.perf_counter() - started,
            "scenario_seconds": result.reproducibility["runtime"]["elapsed_seconds"],
            "evidence_only_seconds": raw_result.reproducibility["runtime"]["elapsed_seconds"],
            "process_peak_rss_bytes": peak_rss,
        },
        "limitations": [
            "Pilot source set only",
            "Four declared techniques",
            "Caps may truncate",
            "Scenario assumptions are predicted outcomes, not observations",
            "No production numeric adoption, full-source exposure, scalability or Top-K claim",
        ],
    }
    _atomic_json(args.sanitized_report, report)
    print(
        json.dumps({"summary": result.summary, "total_seconds": report["runtime"]["total_seconds"]})
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
