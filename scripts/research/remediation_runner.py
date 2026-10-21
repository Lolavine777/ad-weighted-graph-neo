"""Run explicit #284 fixes and export strict reports plus auditable native packages."""

from __future__ import annotations

import argparse
import json
import sys
import time
from copy import deepcopy
from dataclasses import asdict
from pathlib import Path

from scripts.research.asrep_inputs import seamless_inputs
from src.data.manifest import load_manifest, verify_manifest
from src.engine.batch import BatchExecutionBudget
from src.engine.graph import EngineGraph
from src.engine.remediation import ROOT, _digest, _revision, prepare_baseline, request_for_baseline
from src.engine.remediation_runner import (
    expand_individual_interventions,
    inventory_interventions,
    rank_interventions,
    requests_from_inventory,
    run_remediation,
)


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def peak_rss_bytes():
    """Observed process high-water RSS; includes loading, replay and proof audit."""
    if sys.platform != "win32":
        import resource

        value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        return value if sys.platform == "darwin" else value * 1024
    import ctypes
    from ctypes import wintypes

    class Counters(ctypes.Structure):
        _fields_ = [("cb", wintypes.DWORD), ("page_faults", wintypes.DWORD)] + [
            (name, ctypes.c_size_t)
            for name in (
                "peak_working_set",
                "working_set",
                "peak_paged_pool",
                "paged_pool",
                "peak_nonpaged_pool",
                "nonpaged_pool",
                "pagefile",
                "peak_pagefile",
            )
        ]

    info = Counters()
    info.cb = ctypes.sizeof(info)
    current = ctypes.WinDLL("kernel32", use_last_error=True).GetCurrentProcess
    current.restype = wintypes.HANDLE
    measure = ctypes.WinDLL("psapi", use_last_error=True).GetProcessMemoryInfo
    measure.argtypes = [wintypes.HANDLE, ctypes.POINTER(Counters), wintypes.DWORD]
    if not measure(current(), ctypes.byref(info), info.cb):
        raise ctypes.WinError(ctypes.get_last_error())
    return info.peak_working_set


def finite_inputs(fixes):
    folder = ROOT / "tests/fixtures/remediation"
    graph = EngineGraph.from_canonical(read(folder / "graph.json"))
    cells = [
        {"source_id": s, "goal_id": "host", "query": read(folder / f"{s}-query.json")}
        for s in ("alice", "bob")
    ]
    baseline = prepare_baseline(graph, cells, run_id="finite-284-native")
    fixtures = {
        "shared-membership": "request-bypass-v1.1.json",
        "shared-channel": "request-v1.1.json",
        "direct-admin": "request-acl-v1.1.json",
    }
    cases = [
        (
            baseline,
            request_for_baseline(baseline, read(folder / fixtures[fix])["edits"], request_id=fix),
        )
        for fix in fixes
    ]
    return graph, baseline, cases


def seamless_cases(raw_dir):
    manifest = load_manifest(ROOT / "data/samples/manifests/seamless-raw-v1.json")
    if verify_manifest(raw_dir, manifest):
        raise ValueError("SEAMLESS manifest mismatch before pilot")
    graph, _, query, _ = seamless_inputs(raw_dir, _revision())
    query["allowed_techniques"] = [
        "asrep_request",
        "recover_asrep_secret",
        "activate_recovered_identity",
        "obtain_admin_execution_on_host",
    ]
    query["budget"] = {"max_paths": 10, "max_steps": 6, "max_expansions": 1000}

    def baseline_for(spec, label):
        return prepare_baseline(
            graph,
            [{"source_id": "declared-requester", "goal_id": "C0", "query": spec}],
            run_id="seamless-284-" + label,
        )

    def edit(predicate):
        fact = next(f for f in query["assumptions"] if f["predicate"] == predicate)
        return {
            "edit_id": "deny-" + predicate,
            "catalog_entry_id": "admin-channel"
            if predicate == "admin_channel"
            else "group-membership",
            "kind": "runtime_fact_replace",
            "key": {
                **{k: fact[k] for k in ("predicate", "subject", "target")},
                "authentication_context": query["authentication_context"],
                "binding_id": None,
            },
            "expected_before": True,
            "after": False,
            "declaration": "counterfactual_intervention",
            "evidence_refs": ["scenario://284/seamless"],
            "rationale": "Declared bounded-pilot control; no live AD change",
        }

    baseline = baseline_for(query, "declared")
    cases = [
        (baseline, request_for_baseline(baseline, [edit(predicate)], request_id=label))
        for predicate, label in (
            ("admin_channel", "shared-channel"),
            ("membership_usable", "ineffective-membership-retained-bypass"),
        )
    ]
    unknown = deepcopy(query)
    unknown["assumptions"] = [
        f for f in unknown["assumptions"] if f["predicate"] != "recovery_success"
    ]
    capped = deepcopy(query)
    capped["budget"]["max_steps"] = 3
    for label, spec in (("missing-recovery-control", unknown), ("step-cap-control", capped)):
        other = baseline_for(spec, label)
        cases.append(
            (other, request_for_baseline(other, [edit("admin_channel")], request_id=label))
        )
    return graph, baseline, cases, manifest


def summary(packages, *, private=False):
    return [
        {
            "intervention": f"intervention-{i}" if private else p["report"]["request_id"],
            "programs_cut": p["report"]["summary"]["programs_cut"],
            "pairs_disconnected": p["report"]["summary"]["pairs_disconnected"],
            "remaining_bypasses": sum(len(c["bypass_program_ids"]) for c in p["report"]["cells"]),
            "new_bypasses": p["analytics"]["new_after_programs"],
            "coverage": p["analytics"]["coverage"],
            "rediscovery": p["analytics"]["rediscovery_status_counts"],
            "declared_pairs": p["analytics"]["declared_pairs"],
            "not_run_pairs": p["analytics"]["after_not_run_pairs"],
            "C_available_cells": sum(
                c["effort"]["after"] is not None for c in p["report"]["cells"]
            ),
            "C_statuses": p["analytics"]["numeric_comparison"]["effort_status_counts"],
            "P_comparison": "pending",
            "raw_unchanged": True,
        }
        for i, p in enumerate(packages)
    ]


def table(rows):
    lines = [
        "| Intervention | Programs bị cắt | Pairs disconnected có proof "
        "| Bypass còn lại | C/P | Guarantee |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        cuts, pairs = row["programs_cut"], row["pairs_disconnected"]
        lines.append(
            f"| {row['intervention']} | {cuts['numerator']}/{cuts['denominator']} "
            f"({cuts['percent']}%) | {pairs['numerator']}/{pairs['denominator']} "
            f"({pairs['percent']}%) | {row['remaining_bypasses']} | "
            f"C: {row['C_statuses']}; P: pending | {cuts['scope']} |"
        )
    return "\n".join(lines) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--finite", action="store_true")
    source.add_argument("--seamless-raw-dir", type=Path)
    source.add_argument("--graph", type=Path)
    source.add_argument("--snapshot", type=Path)
    parser.add_argument("--cells", type=Path, help="exact declared source×goal public queries")
    parser.add_argument(
        "--request", type=Path, action="append", help="strict remediation 1.1.0 requests"
    )
    parser.add_argument("--label", choices=("synthetic", "private"), default="private")
    parser.add_argument(
        "--fix", choices=("shared-membership", "shared-channel", "direct-admin"), action="append"
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--checkpoint-dir", type=Path)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument(
        "--discover-interventions",
        type=int,
        metavar="N",
        help="Also evaluate up to N supported native-inventory candidates independently",
    )
    parser.add_argument(
        "--include-individuals",
        action="store_true",
        help="evaluate each edit separately as well as its selected set",
    )
    for option in ("max-cells", "max-expansions"):
        parser.add_argument("--" + option, type=int)
    for option in ("max-seconds", "per-query-seconds"):
        parser.add_argument("--" + option, type=float)
    args = parser.parse_args(argv)
    if args.discover_interventions is not None and args.discover_interventions < 1:
        parser.error("--discover-interventions must be a positive integer")
    started = time.perf_counter()
    manifest = None
    if args.finite:
        graph, baseline, cases = finite_inputs(
            args.fix or ["shared-membership", "shared-channel", "direct-admin"]
        )
        private = False
    elif args.seamless_raw_dir:
        graph, baseline, cases, manifest = seamless_cases(args.seamless_raw_dir)
        private = True
    else:
        if not args.cells or not args.request:
            parser.error("--graph/--snapshot requires --cells and --request")
        graph = (
            EngineGraph.from_snapshot(args.snapshot.read_text(encoding="utf-8"))
            if args.snapshot
            else EngineGraph.from_canonical(read(args.graph))
        )
        requests = [read(path) for path in args.request]
        baseline = prepare_baseline(graph, read(args.cells), run_id=requests[0]["baseline_run_id"])
        cases = [(baseline, request) for request in requests]
        private = args.label == "private"
    limits = BatchExecutionBudget(
        args.max_cells, args.max_expansions, args.max_seconds, args.per_query_seconds
    )
    inventory = inventory_interventions(graph, baseline)
    discovered = (
        requests_from_inventory(baseline, inventory, limit=args.discover_interventions)
        if args.discover_interventions is not None
        else []
    )
    cases.extend((baseline, request) for request in discovered)
    if args.include_individuals:
        cases = [
            (before, expanded)
            for before, request in cases
            for expanded in expand_individual_interventions(before, [request])
        ]
    packages = []
    for before, request in sorted(cases, key=lambda case: case[1]["request_id"]):
        checkpoint = (
            args.checkpoint_dir / (_digest(request)[-24:] + ".json")
            if args.checkpoint_dir is not None
            else None
        )
        packages.append(
            run_remediation(
                request,
                graph,
                before,
                execution_budget=limits,
                checkpoint=checkpoint,
                resume=args.resume,
            )
        )
    if manifest is not None and verify_manifest(args.seamless_raw_dir, manifest):
        raise ValueError("SEAMLESS raw manifest changed during pilot")
    groups = {}
    for package in packages:
        groups.setdefault(package["report"]["comparison_scope_digest"], []).append(package)
    rows = summary(packages, private=private and args.seamless_raw_dir is None)
    evidence = {
        "schema_version": "remediation-study-summary/1",
        "comparisons": rows,
        "scope": "bounded declared cohorts; not a full-source scan",
        "inventory_candidates": len(inventory["candidates"]),
        "runtime_seconds": time.perf_counter() - started,
        "process_peak_rss_bytes": peak_rss_bytes(),
        "verified_raw_files": len(manifest["files"]) if manifest else None,
        "budgets": asdict(limits),
    }
    if args.discover_interventions is not None:
        eligible = sum(c["status"] == "supported" for c in inventory["candidates"])
        evidence["discovery"] = {
            "scope": "supported candidates in observed baseline corpus only",
            "selection_policy": "observed_binding_coverage_then_candidate_id",
            "effectiveness_policy": "native_counterfactual_replay_and_rediscovery",
            "limit": args.discover_interventions,
            "eligible_candidates": eligible,
            "evaluated_candidates": len(discovered),
            "not_selected_candidates": eligible - len(discovered),
            "request_ids": [r["request_id"] for r in discovered],
            "optimal_intervention_claim": False,
        }
    study = {
        "schema_version": "remediation-study/1",
        "comparisons": packages,
        "inventory": inventory,
        "priority_groups": [rank_interventions(p) for p in groups.values()],
        "summary": evidence,
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)

    def write(name, value):
        (args.output_dir / name).write_text(
            json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )

    write("study.json", study)
    write("summary.json", evidence)
    for i, package in enumerate(packages):
        write(f"report-{i}.json", package["report"])
        write(f"package-{i}.json", package)
    (args.output_dir / "table.md").write_text(table(rows), encoding="utf-8")
    print(json.dumps(evidence, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
