"""Survey eligible AD sources to observed DA/EA groups with native independent queries."""

from __future__ import annotations

import argparse
import json
import time
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import replace
from multiprocessing import get_context
from pathlib import Path

from scripts.exposure import build_request, inventory_exposure
from scripts.research.source_goal_batch import BatchQueryRequest
from src.engine.batch import _atomic_json, _query_for_cell, execution_source_pins
from src.engine.graph import EngineGraph
from src.engine.program_identity import program_key
from src.engine.query import run_attack_query
from src.engine.query_cli import digest, wire
from src.engine.ranking.effort_profiles import load_effort_profile
from src.engine.ranking.resolution_service import canonical_digest
from src.engine.semantics import RuntimeContext
from src.engine.semantics.credentials import replay_path
from src.engine.semantics.scenario_policy import load_policy_profile

TECHNIQUES = (
    "propagate_group_entitlement",
    "scenario_reset_password",
    "acquire_reset_identity",
    "grant_new_object_right",
    "genericall_add_member",
    "genericall_grant_write_dacl",
    "reset_target_password",
)
HOST_SESSION_TECHNIQUES = TECHNIQUES + (
    "obtain_admin_execution_on_host",
    "open_winrm_remote_session",
    "use_session_identity",
)
SCENARIOS = ("identity", "host-compromise")


def techniques_for(scenario):
    if scenario not in SCENARIOS:
        raise ValueError("Unknown neo scenario")
    return HOST_SESSION_TECHNIQUES if scenario == "host-compromise" else TECHNIQUES


def input_coverage(graph, request, scenario):
    """Explain observed opportunities and declared capabilities before interpreting no-path."""
    techniques_for(scenario)
    computer_ids = {s.node_id for s in request.sources if s.node_kind == "Computer"}
    sessions = [e for e in graph.edges() if e["kind"] == "HasSession"]
    notes = []
    if scenario == "host-compromise" and computer_ids:
        notes.append(
            "Nguồn Computer chỉ có quyền local admin/SYSTEM; "
            "chưa khai báo danh tính mạng của tài khoản máy."
        )
        if not sessions:
            notes.append(
                "Snapshot không có cạnh HasSession; không kiểm chứng được nhánh qua session. "
                "Không tìm thấy đường trong cấu hình này không chứng minh máy an toàn."
            )
    return {
        "scenario": scenario,
        "selected_computer_sources": len(computer_ids),
        "observed_session_edges": len(sessions),
        "selected_computers_with_observed_session": len(
            computer_ids & {e["source"] for e in sessions}
        ),
        "computer_initial_capability": "local_admin_only"
        if scenario == "host-compromise"
        else "usable_machine_network_identity",
        "notes": notes,
    }


def scenario_profile(graph, scenario="identity"):
    """Bind the unchanged neo scenario assumptions to the snapshot being evaluated."""
    techniques_for(scenario)
    identifier = "neo-host-session-v1" if scenario == "host-compromise" else "neo-standard-v1"
    return replace(load_policy_profile(identifier), bound_snapshot_id=graph.metadata["snapshot_id"])


def build_survey(
    graph,
    *,
    max_expansions=1024,
    max_steps=12,
    max_paths=1,
    domain_sid=None,
    scenario="identity",
    source_ids=None,
):
    techniques_for(scenario)
    inventory = inventory_exposure(graph, domain_sid=domain_sid)
    contexts = sorted(
        t["goal"]["target_node_id"]
        for t in inventory["targets"]
        if t["selection_reason"] == "observed_dc_group_membership"
    )
    if not contexts:
        raise ValueError("Survey requires an observed DC Computer for authentication context")
    context = contexts[0]
    request, _ = build_request(
        graph,
        inventory,
        source_ids=source_ids,
        authentication_context=context,
        user_profile="user_usable_identity",
        computer_profile="computer_control_admin"
        if scenario == "host-compromise"
        else "computer_usable_identity",
        machine_identity_provenance=(
            None
            if scenario == "host-compromise"
            else "scenario://neo-domain/independent-compromised-network-identity"
        ),
        max_sources=0,
        max_targets=0,
        evaluation_mode="scenario",
        budget={"max_paths": max_paths, "max_steps": max_steps, "max_expansions": max_expansions},
    )
    targets = {inventory["domain_sid"] + "-512", inventory["domain_sid"] + "-519"}
    request["target_manifest"]["targets"] = [
        t for t in request["target_manifest"]["targets"] if t["target_node_id"] in targets
    ]
    if not request["target_manifest"]["targets"]:
        raise ValueError("Survey requires an observed DA or EA group")
    return inventory, BatchQueryRequest.from_dict(request)


def compact_witness(path, graph, catalog):
    """Retain all used facts and native transitions; verify the reduced context."""
    facts = {
        (d.fact.predicate, d.fact.subject, d.fact.target): d.fact
        for step in path.transition_history
        for d in step.result.decisions
        if d.fact is not None
    }
    context = RuntimeContext(
        facts,
        authentication_context=path.runtime_context.authentication_context,
        rbcd_bindings=path.runtime_context.rbcd_bindings,
        withheld_relationships=path.runtime_context.withheld_relationships,
    )
    reduced = replace(path, runtime_context=context)
    if (
        program_key(reduced) != program_key(path)
        or replay_path(reduced, graph, catalog) != path.final_state
    ):
        raise AssertionError("Fact-sliced witness changed its native program or replay")
    return wire(reduced)


def _initialize(snapshot, request, scenario="identity", search_order="neo_guided"):
    global _graph, _request, _sources, _goals, _policy, _effort, _techniques
    global _search_order
    _graph = EngineGraph.from_snapshot(Path(snapshot).read_text(encoding="utf-8"))
    _request = BatchQueryRequest.from_dict(request)
    _sources = {s.node_id: s for s in _request.sources}
    _goals = {g.target_node_id: g for g in _request.resolve_target_goals()}
    _policy, _effort = scenario_profile(_graph, scenario), load_effort_profile("neo-c-v1")
    _techniques = techniques_for(scenario)
    _search_order = search_order


def _evaluate(pair):
    source, target = pair
    started = time.perf_counter()
    base = {"source": source, "target": target, "source_kind": _sources[source].node_kind}
    try:
        query, error = _query_for_cell(
            _request,
            _sources[source],
            _goals[target],
            _graph,
            globals().get("_techniques", TECHNIQUES),
            _request.common_budget,
            scenario_policy=_policy,
            effort_profile=_effort,
            search_order=globals().get("_search_order", "neo_guided"),
        )
        if error is not None:
            raise ValueError(str(error))
        prepared = time.perf_counter()
        result = run_attack_query(query, _graph)
        witness = result.best_path or (result.paths[0] if result.paths else None)
        row = {
            **base,
            "status": result.status,
            "reached": result.final_goal_reached,
            "C": (result.min_effort or {}).get("minimum_effort_value"),
            "expansions": result.expansions,
            "truncated": result.truncated,
            "truncation_reason": result.truncation_reason,
            "minimum_proven": result.is_minimum_proven_over_scope,
            "no_path_proven": result.is_no_path_proven_over_scope,
            "unknown": dict(Counter(k for a in result.attempts for k in a.unknown)),
            "failed": dict(Counter(k for a in result.attempts for k in a.failed)),
            "witness": compact_witness(witness, _graph, result.materialized_query.catalog)
            if witness is not None
            else None,
            "prepare_seconds": prepared - started,
            "query_seconds": time.perf_counter() - prepared,
        }
        if _request.common_budget.max_paths > 1:
            from src.engine.top_k import effort_programs

            programs, _ = effort_programs(result)
            row["candidate_summary"] = [
                {
                    "candidate_id": p["candidate_id"],
                    "program_id": p["program_id"],
                    "C": p["effort"],
                    "steps": len(
                        result.paths[
                            int(p["candidate_id"].rsplit("_", 1)[1]) - 1
                        ].transition_history
                    ),
                }
                for p in programs
            ]
            row["top_k"] = result.top_k_result
            row["ranked_witnesses"] = [
                compact_witness(
                    result.paths[int(p["candidate_id"].rsplit("_", 1)[1]) - 1],
                    _graph,
                    result.materialized_query.catalog,
                )
                for p in (result.top_k_result or {}).get("programs", [])
            ]
        if len(_request.sources) == 1:
            from src.engine.query_report import render_query_brief

            scenario = (
                "host-compromise" if _policy.profile_id == "neo-host-session-v1" else "identity"
            )
            coverage = input_coverage(_graph, _request, scenario)
            row["input_coverage"] = coverage
            row["brief"] = "\n\n".join(coverage["notes"] + [render_query_brief(result, _graph)])
        return row
    except Exception as error:
        return {**base, "status": "error", "error": f"{type(error).__name__}: {error}"}


def load_records(path):
    """Recover complete hash-checked records; discard only a torn final line."""
    rows, valid_bytes = {}, 0
    raw = path.read_bytes() if path.exists() else b""
    lines = raw.splitlines(keepends=True)
    for index, line in enumerate(lines):
        if index == len(lines) - 1 and not line.endswith(b"\n"):
            break  # A record is committed only once its trailing newline was written.
        try:
            packet = json.loads(line)
        except ValueError, UnicodeDecodeError:
            if index == len(lines) - 1 and not line.endswith(b"\n"):
                break
            raise ValueError("Invalid checkpoint record") from None
        row = packet["row"]
        if packet["sha256"] != canonical_digest(row):
            raise ValueError("Checkpoint record integrity mismatch")
        rows[(row["source"], row["target"])] = row
        valid_bytes += len(line)
    return rows, valid_bytes


def summarize(rows, request, elapsed):
    expected = {
        (s.node_id, g.target_node_id)
        for s in request.sources
        for g in request.resolve_target_goals()
    }
    if set(rows) - expected:
        raise ValueError("Checkpoint contains cells outside declared scope")
    values = list(rows.values())
    reached = [r for r in values if r.get("reached")]
    counts = {
        "eligible_sources": len(request.sources),
        "selected_targets": len(request.resolve_target_goals()),
        "declared_pairs": len(expected),
        "recorded_pairs": len(values),
        "not_run_pairs": len(expected - set(rows)),
        "errors": sum(r["status"] == "error" for r in values),
        "reached_pairs": len(reached),
        "C_rated_reached_pairs": sum(r["C"] is not None for r in reached),
        "truncated_pairs": sum(r.get("truncated", False) for r in values),
        "no_path_proven_pairs": sum(r.get("no_path_proven", False) for r in values),
        "status_counts": dict(Counter(r["status"] for r in values)),
        "source_kinds": dict(Counter(s.node_kind for s in request.sources)),
        "unknown_attempts": dict(sum((Counter(r.get("unknown", {})) for r in values), Counter())),
        "elapsed_seconds": elapsed,
    }
    return counts


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--domain-sid", help="Select an observed domain in a multi-domain snapshot")
    parser.add_argument(
        "--source", action="append", help="Select an independent foothold ID; omit for all"
    )
    parser.add_argument(
        "--scenario",
        choices=SCENARIOS,
        default="identity",
        help="identity: network account only; host-compromise: local admin and reusable sessions",
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--max-expansions", type=int, default=1024)
    parser.add_argument("--max-steps", type=int, default=12)
    parser.add_argument(
        "--search-order",
        choices=("neo_guided", "neo_refine"),
        default="neo_guided",
        help="neo_refine keeps guided witnesses then seeks cheaper paths in the remaining budget",
    )
    parser.add_argument(
        "--max-paths",
        type=int,
        default=1,
        help="Candidate witness cap per query; the neo C profile returns Top-3",
    )
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument(
        "--max-cells", type=int, help="Optional execution slice; scope stays all sources"
    )
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args(argv)
    if (
        args.workers < 1
        or args.max_expansions < 1
        or args.max_steps < 1
        or args.max_paths < 1
        or (args.max_cells is not None and args.max_cells < 1)
    ):
        parser.error("workers, max-expansions, max-steps, max-paths and max-cells must be positive")
    started = time.perf_counter()
    graph = EngineGraph.from_snapshot(args.snapshot.read_text(encoding="utf-8"))
    inventory, request = build_survey(
        graph,
        max_expansions=args.max_expansions,
        max_steps=args.max_steps,
        max_paths=args.max_paths,
        domain_sid=args.domain_sid,
        scenario=args.scenario,
        source_ids=args.source,
    )
    coverage = input_coverage(graph, request, args.scenario)
    config = {
        "version": "neo-domain-survey/1",
        "request": request.to_dict(),
        "scenario": args.scenario,
        "search_order": args.search_order,
        "input_coverage": coverage,
        "techniques": techniques_for(args.scenario),
        "scenario_policy": scenario_profile(graph, args.scenario).canonical_dict(),
        "effort_profile": load_effort_profile("neo-c-v1"),
        "snapshot_sha256": digest(args.snapshot.read_bytes()),
        "source_pins": execution_source_pins(),
        "runner_sha256": digest(Path(__file__).read_bytes()),
        "trace_scope": (
            "Native witness with used facts only; reconstruct full query from request/profile"
        ),
    }
    scope_digest = canonical_digest(config)
    output = args.output_dir
    records = output / "cells.jsonl"
    if args.resume:
        header = json.loads((output / "scope.json").read_text())
        if header["scope_digest"] != scope_digest:
            raise ValueError("CHECKPOINT_SCOPE_MISMATCH")
        rows, valid_bytes = load_records(records)
        records.touch(exist_ok=True)
        with records.open("r+b") as stream:
            stream.truncate(valid_bytes)
    else:
        output.mkdir(parents=True, exist_ok=False)
        _atomic_json(output / "scope.json", {"scope_digest": scope_digest, **config})
        _atomic_json(output / "inventory.json", inventory)
        rows = {}
    summarize(rows, request, 0)
    print(json.dumps({"input_coverage": coverage}, ensure_ascii=False), flush=True)
    pairs = sorted(
        (s.node_id, g.target_node_id)
        for s in request.sources
        for g in request.resolve_target_goals()
    )
    pending = [p for p in pairs if p not in rows or rows[p]["status"] == "error"]
    if args.max_cells is not None:
        pending = pending[: args.max_cells]
    with (
        records.open("a", encoding="utf-8") as stream,
        ProcessPoolExecutor(
            max_workers=args.workers,
            mp_context=get_context("spawn"),
            initializer=_initialize,
            initargs=(
                str(args.snapshot.resolve()),
                request.to_dict(),
                args.scenario,
                args.search_order,
            ),
        ) as pool,
    ):
        futures = [pool.submit(_evaluate, pair) for pair in pending]
        for future in as_completed(futures):
            row = future.result()
            stream.write(
                json.dumps({"sha256": canonical_digest(row), "row": row}, ensure_ascii=False) + "\n"
            )
            stream.flush()
            rows[(row["source"], row["target"])] = row
            if "brief" in row:
                (output / ("goal-" + canonical_digest(row["target"])[7:19] + ".md")).write_text(
                    row["brief"], encoding="utf-8"
                )
            if len(rows) % 25 == 0:
                summary = summarize(rows, request, time.perf_counter() - started)
                summary["input_coverage"] = coverage
                _atomic_json(output / "summary.json", summary)
                print(json.dumps(summary), flush=True)
    summary = summarize(rows, request, time.perf_counter() - started)
    summary["input_coverage"] = coverage
    _atomic_json(output / "summary.json", summary)
    print(json.dumps(summary), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
