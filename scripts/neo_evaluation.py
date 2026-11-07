"""Measure the analysis app on real exports: reach, C against hop count, choke points, speed."""

from __future__ import annotations

import argparse
import json
import platform
import statistics
import time
from collections import Counter, defaultdict, deque
from concurrent.futures import ProcessPoolExecutor
from multiprocessing import get_context
from pathlib import Path

from scripts.neo_workspace import (
    COHORT_BUDGET,
    COHORT_SEED,
    _Planner,
    find_chokepoints,
    open_dataset,
    remove_relationship,
    sample_sources,
)
from src.engine.batch import _atomic_json, execution_source_pins
from src.engine.query_cli import digest
from src.engine.top_k import effort_programs

ROOT = Path(__file__).resolve().parents[1]
IDENTITY_KINDS = {"MemberOf", "GenericAll", "WriteDacl", "ForceChangePassword"}
HOST_KINDS = IDENTITY_KINDS | {"AdminTo", "CanPSRemote", "HasSession"}
DATASETS = {
    # name: folder, export, scenarios, sources sampled, search budget, sources for choke points
    "WRAITH": (
        "data/raw/ad_sampledata",
        "20240305111414",
        ("identity", "host-compromise"),
        None,
        4096,
        None,
    ),
    "NORTH": ("data/raw/NORTH", None, ("identity", "host-compromise"), None, 4096, None),
    "SEAMLESS": ("data/raw/SEAMLESS", None, ("identity",), 120, 1024, 40),
}


def hop_distances(graph, target, kinds):
    """Fewest observed edges to the target from every node, as a shortest-path tool counts them."""
    incoming = defaultdict(list)
    for edge in graph.edges():
        if edge["kind"] in kinds:
            incoming[edge["target"]].append(edge["source"])
    distance, queue = {target: 0}, deque([target])
    while queue:
        node = queue.popleft()
        for previous in incoming[node]:
            if previous not in distance:
                distance[previous] = distance[node] + 1
                queue.append(previous)
    return distance


def spearman(left, right):
    """Rank correlation with average ranks for ties; None when either side never varies."""

    def ranks(values):
        order = sorted(range(len(values)), key=values.__getitem__)
        result, start = [0.0] * len(values), 0
        while start < len(order):
            end = start
            while end + 1 < len(order) and values[order[end + 1]] == values[order[start]]:
                end += 1
            for position in range(start, end + 1):
                result[order[position]] = (start + end) / 2 + 1
            start = end + 1
        return result

    if len(left) < 2 or len(set(left)) < 2 or len(set(right)) < 2:
        return None
    return statistics.correlation(ranks(left), ranks(right))


def _evaluate(task):
    name, source, target, scenario, budget = task
    planner = _worker_planner(name, scenario, budget)
    started = time.perf_counter()
    result = planner.run(source, target)
    seconds = time.perf_counter() - started
    programs, _ = effort_programs(result)
    found = [
        {
            "C": p["effort"],
            "steps": len(
                result.paths[int(p["candidate_id"].rsplit("_", 1)[1]) - 1].transition_history
            ),
        }
        for p in programs
    ]
    return {
        "source": source,
        "target": target,
        "scenario": scenario,
        "reached": result.final_goal_reached,
        "no_path": result.is_no_path_proven_over_scope,
        "truncated": result.truncated,
        "expansions": result.expansions,
        "programs": found,
        "seconds": seconds,
    }


_workspaces, _planners = {}, {}


def _worker_planner(name, scenario, budget):
    key = (name, scenario, budget)
    if key not in _planners:
        folder, export, *_ = DATASETS[name]
        if name not in _workspaces:
            _workspaces[name] = open_dataset(ROOT / folder, export=export)
        workspace = _workspaces[name]
        _planners[key] = _Planner(
            workspace.graph,
            workspace.domain_sid,
            scenario,
            budget=budget,
            max_paths=10,
            search_order="neo_refine",
        )
    return _planners[key]


def summarize(rows, distance_by_target):
    reached = [r for r in rows if r["reached"] and r["programs"]]
    best = [min(p["C"] for p in r["programs"]) for r in reached]
    hops = [distance_by_target[r["target"]].get(r["source"]) for r in reached]
    best_steps = [
        min(p["steps"] for p in r["programs"] if p["C"] == c)
        for r, c in zip(reached, best, strict=True)
    ]
    several = [r for r in reached if len(r["programs"]) >= 2]
    # Choosing by fewest steps, as a hop count would, against choosing by C.
    costlier = 0
    for row in several:
        fewest = min(p["steps"] for p in row["programs"])
        cheapest = min(p["C"] for p in row["programs"])
        if min(p["C"] for p in row["programs"] if p["steps"] == fewest) > cheapest:
            costlier += 1
    by_hops = defaultdict(list)
    for hop, cost in zip(hops, best, strict=True):
        by_hops[hop].append(cost)
    return {
        "pairs": len(rows),
        "reached": sum(r["reached"] for r in rows),
        "no_path": sum(r["no_path"] for r in rows),
        "inconclusive": sum(not r["reached"] and not r["no_path"] for r in rows),
        "hop_path_exists": sum(r["source"] in distance_by_target[r["target"]] for r in rows),
        "hop_path_without_neo_path": sum(
            r["source"] in distance_by_target[r["target"]] and r["no_path"] for r in rows
        ),
        "neo_path_without_hop_path": sum(
            r["reached"] and r["source"] not in distance_by_target[r["target"]] for r in rows
        ),
        "best_C_values": dict(sorted(Counter(best).items())),
        "spearman_C_hops": spearman(best, hops) if None not in hops else None,
        "spearman_C_steps": spearman(best, best_steps),
        "pairs_with_several_paths": len(several),
        "fewest_steps_costs_more": costlier,
        "C_range_by_hops": {
            str(hop): {"pairs": len(costs), "min": min(costs), "max": max(costs)}
            for hop, costs in sorted(by_hops.items(), key=lambda item: item[0] or 0)
        },
        "seconds_median": statistics.median(r["seconds"] for r in rows) if rows else None,
        "seconds_max": max((r["seconds"] for r in rows), default=None),
    }


def measure_app(workspace, scenario):
    """Time what an analyst waits for, one question at a time, on the app's own settings."""

    def timed(work):
        started = time.perf_counter()
        value = work()
        return value, time.perf_counter() - started

    target = workspace.targets()[0]["id"]
    planner = _Planner(
        workspace.graph,
        workspace.domain_sid,
        scenario,
        budget=COHORT_BUDGET,
        max_paths=1,
        search_order="neo_guided",
    )
    sources = sample_sources(planner.sources, None)
    _, search = timed(lambda: workspace.search("admin"))
    _, neighbors = timed(lambda: workspace.neighbors(sources[0]))
    answer, paths = None, []
    for source in sources[:40]:
        found, seconds = timed(
            lambda chosen=source: workspace.find_paths(chosen, target, scenario=scenario)
        )
        paths.append(seconds)
        if found["programs"] and answer is None:
            answer = (source, found)
        if answer and len(paths) >= 3:
            break
    source, found = answer
    # Time a removal that really rebuilds the graph, not one answered without rebuilding.
    edges = [s["edge"] for s in found["programs"][0]["steps"] if s["edge"]]
    edge = next(
        e
        for e in edges
        if remove_relationship(workspace.records, e["source"], e["kind"], e["target"])[1]
    )
    removed, removal = timed(
        lambda: workspace.try_removal(
            edge["source"], edge["kind"], edge["target"], source, target, scenario=scenario
        )
    )
    _, chokepoints = timed(lambda: workspace.chokepoints(target, scenario=scenario))
    return {
        "search_seconds": search,
        "neighbors_seconds": neighbors,
        "find_paths_seconds": paths,
        "try_removal_seconds": removal,
        "try_removal_edge": {**edge, "status": removed["edit"]["status"]},
        "chokepoints_seconds": chokepoints,
    }


def evaluate_dataset(name, workers, with_chokepoints, previous=None):
    folder, export, scenarios, sample, budget, choke_sources = DATASETS[name]
    started = time.perf_counter()
    workspace = open_dataset(ROOT / folder, export=export)
    open_seconds = time.perf_counter() - started
    targets = [t["id"] for t in workspace.targets()]
    report = {
        "export": workspace.report["export"],
        "domains": workspace.report["domains"],
        "nodes": sum(workspace.report["nodes"].values()),
        "edges": sum(workspace.report["edges"].values()),
        "session_edges": workspace.report["session_edges"],
        "outside_references": sum(workspace.report["outside_references"].values()),
        "untyped_references": sum(workspace.report["untyped_references"].values()),
        "skipped_records": len(workspace.report["skipped_records"]),
        "open_seconds": open_seconds,
        "budget": budget,
        "targets": [t["label"] for t in workspace.targets()],
        "scenarios": {},
    }
    for scenario in scenarios:
        kinds = HOST_KINDS if scenario == "host-compromise" else IDENTITY_KINDS
        planner = _Planner(
            workspace.graph,
            workspace.domain_sid,
            scenario,
            budget=budget,
            max_paths=10,
            search_order="neo_refine",
        )
        cohort = sample_sources(planner.sources, sample)
        tasks = [(name, s, t, scenario, budget) for s in cohort for t in targets]
        with ProcessPoolExecutor(workers, mp_context=get_context("spawn")) as pool:
            rows = list(pool.map(_evaluate, tasks, chunksize=1))
        distances = {t: hop_distances(workspace.graph, t, kinds) for t in targets}
        entry = {
            "eligible_sources": len(planner.sources),
            "sources": len(cohort),
            **summarize(rows, distances),
            "by_target": {
                workspace.graph.node(t)["label"]: summarize(
                    [r for r in rows if r["target"] == t], distances
                )
                for t in targets
            },
        }
        if not with_chokepoints and previous:
            entry["chokepoints"] = previous["scenarios"][scenario]["chokepoints"]
        if with_chokepoints:
            entry["chokepoints"] = {
                workspace.graph.node(t)["label"]: find_chokepoints(
                    workspace,
                    t,
                    scenario,
                    sources=choke_sources if choke_sources else len(planner.sources),
                    candidates=5,
                )
                for t in targets
            }
        report["scenarios"][scenario] = entry
        print(
            json.dumps({"dataset": name, "scenario": scenario, "pairs": entry["pairs"]}), flush=True
        )
    report["app_seconds"] = measure_app(workspace, scenarios[-1])
    return report


def peak_rss_bytes():
    """Peak memory of this process, or None where the platform does not report it."""
    try:
        import resource
    except ImportError:  # Windows
        return None
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return peak if platform.system() == "Darwin" else peak * 1024  # Linux reports KiB


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output", type=Path, default=ROOT / "reports/neo/workspace-evaluation.json"
    )
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--dataset", action="append", choices=DATASETS)
    parser.add_argument("--skip-chokepoints", action="store_true")
    parser.add_argument(
        "--app-only", action="store_true", help="Only remeasure response times, keep the rest"
    )
    args = parser.parse_args(argv)
    names = args.dataset or list(DATASETS)
    result = {
        "version": "neo-workspace-evaluation/1",
        "python": platform.python_version(),
        "platform": platform.platform(),
        "cohort_seed": COHORT_SEED,
        "runner_sha256": digest(Path(__file__).read_bytes()),
        "workspace_sha256": digest((ROOT / "scripts/neo_workspace.py").read_bytes()),
        "source_pins_sha256": digest(json.dumps(execution_source_pins(), sort_keys=True).encode()),
        "datasets": {},
    }
    if args.output.exists():
        result["datasets"] = json.loads(args.output.read_text(encoding="utf-8"))["datasets"]
    for name in names:
        if args.app_only:
            folder, export, scenarios, *_ = DATASETS[name]
            workspace = open_dataset(ROOT / folder, export=export)
            result["datasets"][name]["app_seconds"] = measure_app(workspace, scenarios[-1])
            result["peak_rss_bytes"] = peak_rss_bytes()
            _atomic_json(args.output, result)
            continue
        result["datasets"][name] = evaluate_dataset(
            name, args.workers, not args.skip_chokepoints, result["datasets"].get(name)
        )
        result["peak_rss_bytes"] = peak_rss_bytes()
        _atomic_json(args.output, result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
