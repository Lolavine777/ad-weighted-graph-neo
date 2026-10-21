"""Cross-run #283 through the public engine; stdout is aggregate/alias-only evidence."""

import argparse
import json
from collections import Counter
from pathlib import Path

from scripts.research.asrep_inputs import seamless_inputs
from src.data.manifest import load_manifest, verify_manifest
from src.engine.graph import EngineGraph
from src.engine.remediation import (
    ROOT,
    prepare_baseline,
    replay_baseline,
    request_for_baseline,
)


def _read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def _summary(artifact):
    return {
        "baseline_unchanged": artifact["baseline_input_digest_before"]
        == artifact["baseline_input_digest_after"],
        "rediscovery": "not_run",
        "cells": [
            {
                "source": c["source_id"],
                "goal": c["goal_id"],
                "baseline_complete": c["baseline_complete"],
                "baseline_programs": len(c["programs"]),
                "replay": dict(Counter(p["disposition"] for p in c["programs"])),
            }
            for c in artifact["cells"]
        ],
    }


def finite_probe():
    folder = ROOT / "tests/fixtures/remediation"
    graph = EngineGraph.from_canonical(_read(folder / "graph.json"))
    cells = [
        {"source_id": s, "goal_id": "host", "query": _read(folder / f"{s}-query.json")}
        for s in ("alice", "bob")
    ]
    baseline = prepare_baseline(graph, cells, run_id="283-finite-native")
    cases = {}
    for name, fixture in (
        ("shared_channel", "request-v1.1.json"),
        ("shared_membership", "request-bypass-v1.1.json"),
        ("direct_admin_denial", "request-acl-v1.1.json"),
    ):
        request = request_for_baseline(baseline, _read(folder / fixture)["edits"], request_id=name)
        cases[name] = _summary(replay_baseline(request, graph, baseline))
    return cases


def seamless_probe(raw_dir):
    manifest = load_manifest(ROOT / "data/samples/manifests/seamless-raw-v1.json")
    if verify_manifest(raw_dir, manifest):
        raise ValueError("SEAMLESS raw manifest mismatch")
    # Existing reviewed manifest loader, locator bindings and declared scenario.
    graph, _, query, _ = seamless_inputs(raw_dir, "7368cac505b3d19331cb8a688114107e91134f25")
    query["allowed_techniques"] = [
        "asrep_request",
        "recover_asrep_secret",
        "activate_recovered_identity",
        "obtain_admin_execution_on_host",
    ]
    query["budget"] = {"max_paths": 10, "max_steps": 6, "max_expansions": 1000}
    cells = [{"source_id": "declared-requester", "goal_id": "C0", "query": query}]
    baseline = prepare_baseline(graph, cells, run_id="283-seamless-native")
    channel = next(f for f in query["assumptions"] if f["predicate"] == "admin_channel")
    edit = {
        "edit_id": "deny-channel",
        "catalog_entry_id": "admin-channel",
        "kind": "runtime_fact_replace",
        "key": {
            **{k: channel[k] for k in ("predicate", "subject", "target")},
            "authentication_context": query["authentication_context"],
            "binding_id": None,
        },
        "expected_before": True,
        "after": False,
        "declaration": "counterfactual_intervention",
        "evidence_refs": ["scenario://283/seamless"],
        "rationale": "Declared channel denial in fixed authentication context",
    }
    request = request_for_baseline(baseline, [edit], request_id="seamless-channel")
    artifact = replay_baseline(request, graph, baseline)
    if verify_manifest(raw_dir, manifest):
        raise ValueError("raw input changed during replay")
    summary = _summary(artifact)
    assert summary["cells"][0]["baseline_programs"] == 1
    assert summary["cells"][0]["replay"] == {"cut": 1}
    return {
        "verified_raw_files": len(manifest["files"]),
        "scope": "one source, one host goal",
        "case": summary,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seamless-raw-dir", type=Path)
    parser.add_argument("--output", type=Path, help="write only the aggregate alias-only summary")
    args = parser.parse_args()
    evidence = {
        "issue": 283,
        "finite": finite_probe(),
        "seamless": seamless_probe(args.seamless_raw_dir)
        if args.seamless_raw_dir
        else {"status": "pending_raw_input"},
    }
    encoded = json.dumps(evidence, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(encoded, encoding="utf-8")
    print(encoded, end="")


if __name__ == "__main__":
    main()
