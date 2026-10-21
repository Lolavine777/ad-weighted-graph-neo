"""Compare actor-specific and acquired-identity goals on one unchanged full snapshot.

Select an actual enabled User GenericAll User MemberOf DA pair whose source does
not already reach DA through membership. Runtime gates are explicit assumptions,
never observations. This is a scoped regression experiment, not a domain audit.
"""

import argparse
import copy
import json
import time
from collections import defaultdict, deque
from pathlib import Path

from src.engine.batch import execution_source_pins
from src.engine.graph import EngineGraph
from src.engine.query import run_attack_query
from src.engine.query_cli import digest, wire
from src.engine.semantics.credentials import replay_path

ROOT = Path(__file__).resolve().parents[2]


def identity_goal_inputs(graph):
    """Select the unchanged structural fixture without using search candidates."""
    manifest = json.loads((ROOT / "configs/targets/seamless-v2.json").read_text())
    if graph.metadata["snapshot_id"] != manifest["snapshot_id"]:
        raise ValueError("SEAMLESS snapshot binding mismatch")
    group = manifest["targets"][0]["target_node_id"]
    context = next(
        t["target_node_id"] for t in manifest["targets"] if t["target_node_kind"] == "Computer"
    )
    nodes = {n["id"]: n for n in graph.nodes()}
    edges = graph.edges()
    membership = defaultdict(set)
    for edge in edges:
        if edge["kind"] == "MemberOf":
            membership[edge["source"]].add(edge["target"])

    def member_reaches_goal(source):
        queue, seen = deque([source]), set()
        while queue:
            node = queue.popleft()
            if node == group:
                return True
            if node not in seen:
                seen.add(node)
                queue.extend(membership[node] - seen)
        return False

    eligible = [
        e
        for e in edges
        if e["kind"] == "GenericAll"
        and group in membership[e["target"]]
        and all(
            nodes[n]["kind"] == "User" and nodes[n].get("enabled") is True
            for n in (e["source"], e["target"])
        )
        and not member_reaches_goal(e["source"])
    ]
    if not eligible:
        raise ValueError("No full-snapshot input meeting the independent structural preconditions")
    edge = min(eligible, key=lambda e: e["id"])
    source, owner = edge["source"], edge["target"]
    gates = [
        (p, source, owner)
        for p in ("password_policy_accepts", "directory_write_allowed", "network_rpc_reachable")
    ]
    gates += [(p, owner, context) for p in ("network_kdc_reachable", "authentication_accepted")]
    gates += [(p, owner, group) for p in ("security_group", "membership_usable")]
    query = {
        "initial_actor": source,
        "target": group,
        "authentication_context": context,
        "initial_state": {"control": [source], "usable_identity": [[source, context]]},
        "assumptions": [
            {
                "predicate": p,
                "subject": u,
                "target": v,
                "value": True,
                "scope": context,
                "rationale": "Declared experimental gate, not observed evidence",
                "provenance_reference": "scenario://awg-r04/identity-goal",
            }
            for p, u, v in gates
        ],
        "allowed_techniques": [
            "scenario_reset_password",
            "acquire_reset_identity",
            "propagate_group_entitlement",
        ],
        "budget": {"max_paths": 10, "max_steps": 4, "max_expansions": 10000},
        "scenario_reference": "r04-full-snapshot-identity-goal",
    }
    return query, edge, len(eligible)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    args.output_dir.mkdir(parents=True, exist_ok=False)
    snapshot = args.snapshot.read_bytes()
    graph = EngineGraph.from_snapshot(snapshot.decode())
    query, edge, eligible_count = identity_goal_inputs(graph)
    source, group = query["initial_actor"], query["target"]
    goals = {
        "original_actor": {
            "target": group,
            "required_state": {"effective_member": [[source, group]]},
        },
        "any_usable_identity": {"target": group, "kind": "usable_identity_entitlement"},
    }
    rows = {}
    for name, goal in goals.items():
        specification = copy.deepcopy(query)
        specification["target_goal"] = goal
        started = time.perf_counter()
        result = run_attack_query(specification, graph)
        for path in result.paths:
            replay_path(path, graph)
        rows[name] = {
            "goal_reached": result.final_goal_reached,
            "status": result.status,
            "complete": result.complete,
            "truncated": result.truncated,
            "no_path_proven": result.is_no_path_proven_over_scope,
            "expansions": result.expansions,
            "seconds": time.perf_counter() - started,
            "programs": [
                [s.result.request.technique_id for s in p.transition_history] for p in result.paths
            ],
        }
        (args.output_dir / f"{name}-query.json").write_text(json.dumps(specification, indent=2))
        (args.output_dir / f"{name}-paths.json").write_text(
            json.dumps(wire(result.paths), indent=2)
        )
    expected = {"original_actor": False, "any_usable_identity": True}
    if {k: v["goal_reached"] for k, v in rows.items()} != expected:
        raise AssertionError("Native results falsify the declared goal-scope expectation")
    report = {
        "snapshot_id": graph.metadata["snapshot_id"],
        "snapshot_file_sha256": digest(snapshot),
        "source_pins": execution_source_pins(),
        "eligible_input_pairs": eligible_count,
        "selected_reset_edge_id": edge["id"],
        "runtime_gates": "seven declared positive assumptions",
        "initial_state": "U already usable at declared Computer context; V is not initially usable",
        "expected": expected,
        "actual": rows,
        "limitations": [
            "One selected source/goal",
            "Three techniques",
            "Explicit scenario gates",
            "No new numeric basis",
            "No global optimality or domain-wide exposure claim",
        ],
    }
    (args.output_dir / "summary.json").write_text(json.dumps(report, indent=2))
    print(json.dumps({k: v for k, v in report.items() if k != "source_pins"}, sort_keys=True))


if __name__ == "__main__":
    main()
