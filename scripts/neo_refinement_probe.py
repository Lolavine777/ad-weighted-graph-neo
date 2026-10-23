"""Measure bounded C improvement without losing the existing guided witnesses."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from scripts.neo_domain import compact_witness, scenario_profile, techniques_for
from scripts.neo_minimum_probe import CASE_NAMES, evaluate, oracle
from scripts.research.source_goal_batch import BatchQueryRequest
from src.engine.batch import _atomic_json, _query_for_cell, execution_source_pins
from src.engine.graph import EngineGraph
from src.engine.query import run_attack_query
from src.engine.query_cli import digest
from src.engine.ranking.effort_profiles import load_effort_profile
from src.engine.ranking.resolution_service import canonical_digest
from src.engine.semantics.credentials import replay_path
from src.engine.top_k import effort_programs

ROOT = Path(__file__).resolve().parents[1]
STRATEGIES = ("neo_guided", "neo_refine")


def finite_rows():
    rows = [
        evaluate(name, strategy, max_paths=cap)
        for name in CASE_NAMES
        for strategy in STRATEGIES
        for cap in (1, 10, 1000)
    ]
    for name in CASE_NAMES:
        complete = [r for r in rows if r["case"] == name and r["budget"]["max_paths"] == 1000]
        if complete[0]["program_set_sha256"] != complete[1]["program_set_sha256"]:
            raise AssertionError("Exhaustive strategies changed the finite program set")
        first = next(
            r
            for r in rows
            if r["case"] == name and r["strategy"] == "neo_refine" and r["budget"]["max_paths"] == 1
        )
        if first["C"] != oracle(name)["certain_minimum_C"] or first["minimum_proven"]:
            raise AssertionError("Cost ordering violated the finite oracle or capped guarantee")
    return rows


def cohort_rows(graph, dataset, name, output, pair_limit=None, max_expansions=None):
    request = BatchQueryRequest.from_dict(dataset["request"])
    if graph.metadata["snapshot_id"] != dataset["snapshot_id"]:
        raise ValueError("Snapshot does not match the fixed cohort raw-input identity")
    sources = {s.node_id: s for s in request.sources}
    goals = {g.target_node_id: g for g in request.resolve_target_goals()}
    policy = scenario_profile(graph, dataset["scenario"])
    rows = []
    for pair in dataset["pairs"][:pair_limit]:
        for cap in (1, 10):
            for strategy in STRATEGIES:
                budget = {**dataset["request"]["common_budget"], "max_paths": cap}
                if max_expansions is not None:
                    budget["max_expansions"] = max_expansions
                # Reconstruct the same request with only the witness cap changed.
                bounded = BatchQueryRequest.from_dict(
                    {**request.to_dict(), "common_budget": budget}
                )
                query, error = _query_for_cell(
                    bounded,
                    sources[pair["source"]],
                    goals[pair["target"]],
                    graph,
                    techniques_for(dataset["scenario"]),
                    bounded.common_budget,
                    scenario_policy=policy,
                    effort_profile=load_effort_profile("neo-c-v1"),
                    search_order=strategy,
                )
                if error is not None:
                    raise ValueError(str(error))
                started = time.perf_counter()
                result = run_attack_query(query, graph)
                seconds = time.perf_counter() - started
                programs, exclusions = effort_programs(result)
                by_id = {p["candidate_id"]: p for p in programs}
                for path in result.paths:
                    replayed = replay_path(path, graph, result.materialized_query.catalog)
                    if replayed != path.final_state:
                        raise AssertionError("Native replay changed the generated program")
                row = {
                    "dataset": name,
                    "pair_id": pair["id"],
                    "source": pair["source"],
                    "source_label": pair["source_label"],
                    "target": pair["target"],
                    "target_label": pair["target_label"],
                    "strategy": strategy,
                    "budget": budget,
                    "query_sha256": canonical_digest(query),
                    "seconds": seconds,
                    "status": result.status,
                    "reached": result.final_goal_reached,
                    "C": (result.min_effort or {}).get("minimum_effort_value"),
                    "first_C": by_id.get("generated_0001", {}).get("effort"),
                    "expansions": result.expansions,
                    "programs": len(programs),
                    "truncated": result.truncated,
                    "truncation_reason": result.truncation_reason,
                    "minimum_proven": result.is_minimum_proven_over_scope,
                    "unknown_attempts": sum(bool(a.unknown) for a in result.attempts),
                    "rating_exclusions": exclusions,
                    "discovery_C": [
                        by_id[f"generated_{i:04d}"]["effort"]
                        for i in range(1, len(result.paths) + 1)
                    ],
                    "top_C": [p["effort"] for p in result.top_k_result["programs"]],
                    "replayed_programs": len(result.paths),
                }
                evidence = {
                    "row": row,
                    "query": query,
                    "programs": programs,
                    "best_witness": compact_witness(
                        result.best_path, graph, result.materialized_query.catalog
                    )
                    if result.best_path
                    else None,
                }
                _atomic_json(output / f"{name}-{pair['id']}-{cap}-{strategy}.json", evidence)
                rows.append(row)
                print(
                    json.dumps(
                        {
                            k: row[k]
                            for k in (
                                "dataset",
                                "source_label",
                                "target_label",
                                "strategy",
                                "C",
                                "expansions",
                            )
                        }
                    ),
                    flush=True,
                )
    return rows


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--seamless-snapshot", type=Path)
    parser.add_argument("--wraith-snapshot", type=Path)
    parser.add_argument("--pair-limit", type=int, help="First N fixed pairs per stratum")
    parser.add_argument("--max-expansions", type=int, help="Override the common expansion budget")
    args = parser.parse_args(argv)
    if args.max_expansions is not None and args.max_expansions < 1:
        parser.error("--max-expansions must be positive")
    if args.pair_limit is not None and args.pair_limit < 1:
        parser.error("--pair-limit must be positive")
    args.output_dir.mkdir(parents=True, exist_ok=False)
    pack_path = ROOT / "reports/neo/bloodhound-query-pack.json"
    pack = json.loads(pack_path.read_text())
    report = {
        "version": "neo-refinement-probe/1",
        "source_pins": execution_source_pins(),
        "runner_sha256": digest(Path(__file__).read_bytes()),
        "fixed_pack_sha256": digest(pack_path.read_bytes()),
        "effort_profile": load_effort_profile("neo-c-v1"),
        "pair_limit": args.pair_limit,
        "max_expansions": args.max_expansions,
        "finite_rows": finite_rows(),
        "snapshots": {},
        "cohort_rows": [],
    }
    for name, path in (("seamless", args.seamless_snapshot), ("wraith", args.wraith_snapshot)):
        if path is None:
            continue
        content = path.read_bytes()
        graph = EngineGraph.from_snapshot(content.decode())
        report["snapshots"][name] = {
            "sha256": digest(content),
            "snapshot_id": graph.metadata["snapshot_id"],
            "nodes": len(graph.nodes()),
            "edges": len(graph.edges()),
            "AdminTo": len(graph.edges(kind="AdminTo")),
        }
        strata = (name, "wraith-sessions") if name == "wraith" else (name,)
        for stratum in strata:
            report["cohort_rows"].extend(
                cohort_rows(
                    graph,
                    pack["datasets"][stratum],
                    stratum,
                    args.output_dir,
                    args.pair_limit,
                    args.max_expansions,
                )
            )
    _atomic_json(args.output_dir / "results.json", report)
    print(json.dumps({"results": str(args.output_dir / "results.json")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
