"""Thin executable public-query bridge; experimental Week 4 result transport."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
import sys
import time
from collections.abc import Mapping
from dataclasses import fields, is_dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from src.engine import materialize_query, run_attack_query
from src.engine.graph import EngineGraph
from src.engine.ranking import RankingEngineError
from src.engine.ranking.orchestration import evaluate_search_candidates
from src.engine.search import PathResult
from src.engine.semantics import RuntimeContext, apply_transition
from src.engine.semantics.transitions import TransitionResult

ROOT = Path(__file__).resolve().parents[2]
SCHEMA_VERSION = "week4-query-result/0.2.0"
ACCEPTANCE_STATUS = "experimental_pending_213_208"
AUTOMATIC_ACCEPTANCE_STATUS = "experimental_pending_245_250_251_208"
TOP_K_SCHEMA_VERSION = "week4-query-result/0.4.0"


def wire(value: Any) -> Any:
    """Preserve ordered programs; sort only unordered state/fact collections."""
    # Most audit leaves are already JSON scalars. Exact types keep dataclass
    # subclasses and custom containers on the existing conversion path.
    if value is None or type(value) in (str, int, float, bool):
        return value
    if isinstance(value, RuntimeContext):
        return {
            "facts": [wire(fact) for _, fact in sorted(value.facts.items())],
            "authentication_context": value.authentication_context,
            "rbcd_bindings": wire(value.rbcd_bindings),
            "withheld_relationships": wire(value.withheld_relationships),
        }
    if isinstance(value, TransitionResult):
        return {
            **{f.name: wire(getattr(value, f.name)) for f in fields(value)},
            "after": wire(apply_transition(value.before, value)),
            "assumption_backed_facts": wire(value.assumption_backed_facts),
            "evidence_backed_facts": wire(value.evidence_backed_facts),
        }
    if is_dataclass(value) and not isinstance(value, type):
        return {
            f.name: wire(getattr(value, f.name))
            for f in fields(value)
            if not f.name.startswith("_")
            and not (f.name == "search_order" and getattr(value, f.name) == "fifo")
            # Source scope is already in materialized.initial_actor and the
            # Top-K key. Preserve the accepted legacy candidate transport shape.
            and not (isinstance(value, PathResult) and f.name == "initial_actor")
            and not (
                isinstance(value, PathResult)
                and f.name == "goal_target"
                and value.goal_target is None
            )
        }
    if isinstance(value, Mapping):
        return {k: wire(v) for k, v in value.items()}
    if isinstance(value, (set, frozenset)):
        return sorted((wire(v) for v in value), key=canonical_json)
    if isinstance(value, (tuple, list)):
        return [wire(v) for v in value]
    return value


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False)


def digest(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def read_input(path: str, references: dict[str, Any], role: str) -> Any:
    data = Path(path).read_bytes()
    references[role] = {"reference": path, "sha256": digest(data)}
    return json.loads(data.decode("utf-8-sig"))


def revision_metadata() -> dict[str, Any]:
    def git(*args: str) -> str:
        return subprocess.check_output(
            ["git", *args], cwd=ROOT, text=True, stderr=subprocess.PIPE
        ).strip()

    return {
        "revision": git("rev-parse", "HEAD"),
        "tracked_changes": git("diff", "HEAD", "--name-only").splitlines(),
    }


def execute(query: dict, graph: EngineGraph, *, brief_output: str | None = None) -> dict:
    for field in ("initial_state", "initial_capabilities"):
        if query.get(field) is not None and not isinstance(query[field], Mapping):
            raise TypeError(f"{field} must be a JSON object")
        # The public materializer treats {} as absent and grants default control.
        # Reject that ambiguous transport value before calling the engine.
        if field in query and isinstance(query[field], Mapping) and not query[field]:
            raise ValueError(
                f'{field} is explicitly empty; use {{"control": []}} for zero capabilities '
                "or omit the field to request the public default initial state"
            )
    ranking_input = query.get("ranking_query")
    if ranking_input is None:
        ranking_input = query.get("ranking_payload")
    # The explicit public override preserves an empty/falsey payload for validation.
    materialized = materialize_query(query, graph, ranking_query=ranking_input)
    # Always run the authoritative validator, even with no paths/unbound paths.
    # The empty assessment here is validation only, never substituted for search.
    if materialized.ranking_query is not None:
        ranking_query = dict(materialized.ranking_query)
        evaluate_search_candidates(
            ranking_query,
            [],
            canonical_graph=graph.to_canonical(),
            engine_graph=graph if isinstance(graph, EngineGraph) else None,
            prepared=graph.to_prepared() if hasattr(graph, "to_prepared") else None,
        )
        metadata = ranking_query["query_metadata"]
        if metadata["foothold_node_id"] != materialized.initial_actor:
            raise ValueError("ranking foothold_node_id must match materialized initial_actor")
        if metadata["target_goal"]["target_asset_id"] != materialized.target:
            raise ValueError("ranking target_asset_id must match materialized target")

    result = run_attack_query(materialized, graph)
    if brief_output is not None:
        from src.engine.query_report import render_query_brief

        Path(brief_output).write_text(render_query_brief(result, graph), encoding="utf-8")
    candidates = []
    for index, path in enumerate(result.paths, 1):
        candidates.append({"candidate_id": f"generated_{index:04d}", **wire(path)})
    bindings = materialized.action_bindings or {}
    return {
        "query": query,
        "materialized": {
            "initial_actor": materialized.initial_actor,
            "initial_attack_state": wire(materialized.initial_attack_state),
            "runtime_context": wire(materialized.runtime_context),
            "target": materialized.target,
            "catalog": wire(materialized.catalog),
            "budget": wire(materialized.budget),
            "scenario_reference": materialized.scenario_reference,
            "evaluation_mode": materialized.evaluation_mode,
            "active_scope": materialized.active_scope,
            "action_bindings": [
                {"transition": list(key), "action_id": value}
                for key, value in sorted(bindings.items())
            ],
            "rejected_assumptions": [r.to_dict() for r in materialized.rejected_assumptions],
            **(
                {"search_strategy": materialized.search_strategy}
                if materialized.search_order != "fifo"
                else {}
            ),
        },
        "status": result.status,
        "checkpoint_reached": result.checkpoint_reached,
        "final_goal_reached": result.final_goal_reached,
        "caps": result.caps,
        "complete": result.complete,
        "truncated": result.truncated,
        "truncation_reason": result.truncation_reason,
        "expansions": result.expansions,
        "candidates": candidates,
        "attempts": wire(result.attempts),
        "diagnostics": wire(result.diagnostics),
        "checkpoint_diagnostics": wire(result.checkpoint_diagnostics),
        "binding_diagnostics": wire(result.binding_diagnostics),
        "ranking_result": result.ranking_result,
        **(
            {"rating_coverage": result.rating_coverage}
            if result.rating_coverage is not None
            else {}
        ),
        "min_effort": result.min_effort,
        **({"top_k": result.top_k_result} if result.top_k_result is not None else {}),
        "ranking_disposition": "evaluated" if result.ranking_result is not None else "unrated",
        "engine_reported_guarantees": {
            "optimization_scope": result.optimization_scope,
            "is_minimum_proven_over_scope": result.is_minimum_proven_over_scope,
            "is_no_path_proven_over_scope": result.is_no_path_proven_over_scope,
        },
    }


def main(argv: list[str] | None = None) -> int:
    # Windows redirected streams otherwise use the active ANSI code page.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--query", required=True, help="Public AttackQuery JSON object")
    inputs = parser.add_mutually_exclusive_group(required=True)
    inputs.add_argument("--graph", help="Canonical structural graph JSON (no snapshot facts)")
    inputs.add_argument("--snapshot", help="Supported snapshot-facts/1 envelope")
    parser.add_argument("--ranking-query", help="Accepted scoring package or PathRankingQuery JSON")
    parser.add_argument(
        "--rating-resolution", help="Versioned automatic registry/scope/policy JSON"
    )
    parser.add_argument("--label", required=True, choices=["synthetic", "private", "seamless"])
    parser.add_argument("--prerequisite", action="append", default=[], help="Required private file")
    parser.add_argument("--source", dest="source_foothold")
    parser.add_argument("--actor", dest="initial_actor")
    parser.add_argument("--target")
    parser.add_argument(
        "--top-k", type=int, help="Number of effort-ranked programs; independent of caps"
    )
    parser.add_argument("--context", dest="authentication_context")
    parser.add_argument("--search-order", choices=("fifo", "goal_guided", "neo_guided", "neo_cost"))
    for name in ("initial-state", "target-goal", "runtime-facts", "assumptions"):
        parser.add_argument(f"--{name}", help="JSON override file")
    for name in ("max-paths", "max-steps", "max-expansions"):
        parser.add_argument(f"--{name}", type=int)
    parser.add_argument("--output", help="JSON output file; default stdout")
    parser.add_argument("--brief", help="Also write a readable Vietnamese Markdown result")
    parser.add_argument(
        "--compact-output", action="store_true", help="Omit JSON whitespace; retain the full audit"
    )
    args = parser.parse_args(argv)
    started = datetime.now(UTC).isoformat()
    clock = time.perf_counter()
    references: dict[str, Any] = {}
    try:
        if args.label != "synthetic" and not args.prerequisite:
            raise FileNotFoundError("private/SEAMLESS run requires explicit --prerequisite files")
        for index, path in enumerate(args.prerequisite):
            data = Path(path).read_bytes()
            references[f"prerequisite_{index}"] = {"reference": path, "sha256": digest(data)}
        query = read_input(args.query, references, "query")
        if not isinstance(query, dict):
            raise TypeError("query must be a JSON object")
        for key in ("graph", "catalog"):
            if key in query and query[key] is None:
                del query[key]
        if "graph" in query or "catalog" in query or "candidates" in query:
            raise ValueError(
                "use explicit graph/snapshot; supplied candidates/catalog are unsupported"
            )
        for key in ("source_foothold", "initial_actor", "target", "authentication_context"):
            if (value := getattr(args, key)) is not None:
                query[key] = value
        if args.top_k is not None:
            query["top_k"] = args.top_k
        if args.search_order is not None:
            query["search_order"] = args.search_order
        for key in ("initial_state", "target_goal", "runtime_facts", "assumptions"):
            if (path := getattr(args, key)) is not None:
                query[key] = read_input(path, references, key)
        raw_budget = query.get("budget", query.get("search_budget"))
        if raw_budget is not None and not isinstance(raw_budget, Mapping):
            raise TypeError("budget/search_budget must be a JSON object")
        budget = dict(raw_budget or {})
        for key in ("max_paths", "max_steps", "max_expansions"):
            if (value := getattr(args, key)) is not None:
                budget[key] = value
        if budget:
            query["budget"] = budget
        graph_data = read_input(args.snapshot or args.graph, references, "graph_input")
        graph = (
            EngineGraph.from_snapshot(canonical_json(graph_data))
            if args.snapshot
            else EngineGraph.from_canonical(graph_data)
        )
        if args.label != "synthetic" and graph.metadata.get("synthetic") is True:
            raise ValueError("synthetic graph cannot be labeled private/SEAMLESS")
        if args.ranking_query is not None:
            ranking = read_input(args.ranking_query, references, "ranking_input")
            if not isinstance(ranking, dict):
                raise TypeError("ranking input must be a JSON object")
            if "query" in ranking:
                if not isinstance(ranking["query"], dict):
                    raise TypeError("ranking input wrapper 'query' must be a JSON object")
                query["ranking_query"] = ranking["query"]
            else:
                query["ranking_query"] = ranking

        if args.rating_resolution is not None:
            if query.get("rating_resolution") is not None:
                raise ValueError("--rating-resolution conflicts with embedded rating_resolution")
            query["rating_resolution"] = read_input(
                args.rating_resolution, references, "rating_resolution"
            )
        semantic = execute(query, graph, **({"brief_output": args.brief} if args.brief else {}))
        semantic["input_label"] = args.label
        semantic["snapshot_metadata"] = graph.metadata
        semantic["snapshot_facts_present"] = graph.snapshot_facts is not None
        semantic["snapshot_facts"] = wire(graph.snapshot_facts)
        automatic = query.get("rating_resolution") is not None
        package = {
            "schema_version": "week4-query-result/0.3.0" if automatic else SCHEMA_VERSION,
            "acceptance": {
                "status": AUTOMATIC_ACCEPTANCE_STATUS if automatic else ACCEPTANCE_STATUS,
                "resolved_dependencies": {
                    "https://github.com/nairyuuu/ad-weighted-graph/pull/232": "merged",
                    **(
                        {"https://github.com/nairyuuu/ad-weighted-graph/pull/233": "merged"}
                        if automatic
                        else {}
                    ),
                },
                "pending_acceptance": [
                    "#245 resolver release acceptance",
                    "#250 public rating integration cross-review",
                    "#251 independent resolver cross-reproduction",
                    "#208 integrated Week 4 release acceptance",
                    "Actual private/SEAMLESS independent query reproduction",
                ]
                if automatic
                else [
                    "#213 human review and CLI acceptance",
                    "#208 independent exact-revision reproduction",
                    "Actual private/SEAMLESS query reproduction",
                ],
                "limitations": [
                    "Engine proof flags apply only to the declared scope and assessed coverage.",
                    "Synthetic PASS does not establish full Week 4 or SEAMLESS acceptance.",
                    "Graph binding digest is not authentication of snapshot fact evidence.",
                    "Prerequisite hashes record bytes; they do not verify raw-to-snapshot lineage.",
                    "Attempt diagnostics have no branch ID in the current engine API.",
                    'Explicit {} initial state is rejected; use {"control": []} for empty state.',
                ],
            },
            "reproducibility": {
                **revision_metadata(),
                "inputs": references,
                "effective_config_sha256": digest(canonical_json(query).encode("utf-8")),
                "semantic_sha256": digest(canonical_json(semantic).encode("utf-8")),
                "config_files": {
                    str(p.relative_to(ROOT).as_posix()): digest(p.read_bytes())
                    for p in sorted((ROOT / "configs").rglob("*"))
                    if p.is_file()
                },
                "source_files": {
                    str(p.relative_to(ROOT).as_posix()): digest(p.read_bytes())
                    for folder in ("src", "scripts")
                    for p in sorted((ROOT / folder).rglob("*.py"))
                },
            },
            "runtime": {
                "started_at": started,
                "duration_seconds": time.perf_counter() - clock,
                "python": sys.version,
                "platform": platform.platform(),
            },
            "semantic": semantic,
        }
        if materialized_top_k := semantic.get("top_k"):
            package["schema_version"] = TOP_K_SCHEMA_VERSION
            acceptance = package["acceptance"]
            acceptance.update(
                status="experimental_pending_226",
                resolved_dependencies={
                    **acceptance["resolved_dependencies"],
                    "https://github.com/nairyuuu/ad-weighted-graph/pull/232": "merged",
                    "https://github.com/nairyuuu/ad-weighted-graph/pull/233": "merged",
                },
                pending_acceptance=[
                    *acceptance["pending_acceptance"],
                    "#226 exact-head human review and independent reproduction",
                ],
            )
            package["acceptance"]["limitations"].append(
                "Top-K guarantees apply to the disclosed query/assessment scope: "
                + materialized_top_k["guarantee"]["kind"]
            )
        output = json.dumps(
            package,
            ensure_ascii=False,
            sort_keys=True,
            indent=None if args.compact_output else 2,
            separators=(",", ":") if args.compact_output else None,
            allow_nan=False,
        )
        if args.output:
            Path(args.output).write_text(output + "\n", encoding="utf-8")
        else:
            sys.stdout.write(output + "\n")
        return 0
    except FileNotFoundError as exc:
        sys.stderr.write(f"Missing prerequisite: {exc}\n")
        return 2
    except (RankingEngineError, ValueError, TypeError, KeyError, OSError) as exc:
        sys.stderr.write(f"Invalid input/run: {exc}\n")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
