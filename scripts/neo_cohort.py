"""Compare neo search on ten pinned SEAMLESS queries and replay every witness."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from src.engine.graph import EngineGraph
from src.engine.query import run_attack_query
from src.engine.query_cli import digest, wire
from src.engine.ranking.effort_profiles import bind_effort_profile, load_effort_profile
from src.engine.semantics.credentials import replay_path
from src.engine.semantics.scenario_policy import apply_policy_to_query

DOMAIN = "S-1-5-21-1271839998-3495686680-2211690266"
MEMBER = "propagate_group_entitlement"
RESET = (MEMBER, "scenario_reset_password", "acquire_reset_identity")
ADMIN = "obtain_admin_execution_on_host"
FAMILIES = {
    "admin": (ADMIN,),
    "membership": (MEMBER,),
    "reset": RESET,
    "host": (*RESET, ADMIN),
    "acl": (MEMBER, "grant_new_object_right", "genericall_add_member"),
    "winrm": ("open_winrm_remote_session",),
}
# Same source, goal, context, technique scope and legacy order as docs/neo.md.
CASES = (
    (1116, 1000, 1000, "admin", "fifo"),
    (2799, 512, 1000, "membership", "fifo"),
    (1395, 512, 1000, "reset", "fifo"),
    (1111, 512, 1000, "reset", "fifo"),
    (1269, 512, 1000, "reset", "fifo"),
    (1116, 512, 1000, "acl", "fifo"),
    (4157, 512, 4157, "reset", "fifo"),
    (4157, 512, 4157, "reset", "goal_guided"),
    (1395, 1000, 1000, "host", "fifo"),
    (3385, 1000, 1000, "winrm", "fifo"),
)


def query_for_case(index, graph, max_paths):
    source, target, context, family, legacy_order = CASES[index - 1]
    source, target, context = (f"{DOMAIN}-{rid}" for rid in (source, target, context))
    if family == "winrm":
        goal = {"required_state": {"remote_command_execution": [[source, target]]}}
    elif target.endswith("-512"):
        goal = {"kind": "usable_identity_entitlement"}
    else:
        goal = {"required_state": {"admin_control": [target]}}
    query = {
        "initial_actor": source,
        "initial_state": {"control": [source], "usable_identity": [[source, context]]},
        "authentication_context": context,
        "target": target,
        "target_goal": {"target": target, **goal},
        "allowed_techniques": list(FAMILIES[family]),
        "scenario_reference": f"neo-cohort/Q{index}",
        "evaluation_mode": "scenario",
        "search_order": legacy_order,
        "top_k": 3,
        "budget": {"max_paths": max_paths, "max_steps": 5, "max_expansions": 6000},
    }
    return bind_effort_profile(
        apply_policy_to_query(query, graph, "neo-standard-v1"),
        graph,
        load_effort_profile("neo-c-v1"),
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--max-paths", type=int, default=1)
    args = parser.parse_args(argv)
    if args.max_paths < 1:
        parser.error("--max-paths must be positive")
    args.output_dir.mkdir(parents=True, exist_ok=False)
    snapshot = args.snapshot.read_bytes()
    graph = EngineGraph.from_snapshot(snapshot.decode("utf-8"))
    if (len(graph.nodes()), len(graph.edges())) != (3370, 56367):
        raise ValueError("Expected the pinned SEAMLESS graph: 3370 nodes / 56367 edges")
    summary = {"snapshot_sha256": digest(snapshot), "runs": []}
    for index in range(1, len(CASES) + 1):
        base = query_for_case(index, graph, args.max_paths)
        for variant in ("legacy", "neo_guided"):
            query = {
                **base,
                "search_order": base["search_order"] if variant == "legacy" else variant,
            }
            started = time.perf_counter()
            result = run_attack_query(query, graph)
            seconds = time.perf_counter() - started
            for path in result.paths:
                if replay_path(path, graph) != path.final_state:
                    raise AssertionError("Native witness replay diverged")
                if not result.materialized_query.is_success_state(path.final_state):
                    raise AssertionError("Witness does not satisfy the declared goal")
            row = {
                "query": f"Q{index}",
                "variant": variant,
                "search_order": query["search_order"],
                "paths": len(result.paths),
                "C": (result.min_effort or {}).get("minimum_effort_value"),
                "expansions": result.expansions,
                "seconds": seconds,
                "truncated": result.truncated,
                "truncation_reason": result.truncation_reason,
                "minimum_proven": result.is_minimum_proven_over_scope,
                "C_values": [p["effort"] for p in result.top_k_result["programs"]],
                "replay_passed": True,
            }
            summary["runs"].append(row)
            destination = args.output_dir / f"Q{index}" / variant
            destination.mkdir(parents=True)
            for name, payload in (
                ("query", query),
                ("result", {**row, "witnesses": wire(result.paths), "top_k": result.top_k_result}),
            ):
                (destination / f"{name}.json").write_text(
                    json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
                )
            print(json.dumps(row), flush=True)
    (args.output_dir / "summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
