"""Finite minimum-C experiment using the unchanged planner and reference Dijkstra.

The two serial routes have hand-computable costs. The conditioned graph is a
reference for these fixtures only: it does not compile general attack programs.
"""

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path

from scripts.check_contract import canonical_edge_id
from src.engine.batch import _atomic_json, execution_source_pins
from src.engine.graph import EngineGraph
from src.engine.query import run_attack_query
from src.engine.query_cli import digest
from src.engine.ranking.effort_profiles import bind_effort_profile, load_effort_profile
from src.engine.ranking.resolution_service import canonical_digest
from src.engine.search import shortest_path, unit_cost
from src.engine.semantics.credentials import replay_path
from src.engine.top_k import effort_programs

ROOT = Path(__file__).resolve().parents[1]
ACTOR = "S-1-5-21-1000-2000-3000-1101"
OWNER = "S-1-5-21-1000-2000-3000-1102"
GOAL = "S-1-5-21-1000-2000-3000-512"
HOST = "10000000-0000-4000-8000-000000000002"
GROUPS = ("S-1-5-21-1000-2000-3000-2101", "S-1-5-21-1000-2000-3000-2102")
CASE_NAMES = ("two_routes", "reset_auth_false", "reset_auth_unknown", "free_membership")
# Deliberately independent of load_effort_profile and the production cost resolver.
ACTION_C = {
    "grant_new_object_right": 2,
    "genericall_add_member": 1,
    "scenario_reset_password": 1,
    "acquire_reset_identity": 0,
    "propagate_group_entitlement": 0,
}


def edge(source, target, kind):
    return {
        "id": canonical_edge_id(source, target, kind),
        "source": source,
        "target": target,
        "kind": kind,
        "weight": 1.0,
        "provenance": [
            {
                "raw_file": "synthetic://neo-minimum-probe",
                "collector": "finite-oracle",
                "timestamp": "2026-10-23T00:00:00Z",
                "evidence_type": "positive",
            }
        ],
    }


def fixture(name):
    if name not in CASE_NAMES:
        raise ValueError("Unknown finite minimum case")
    data = json.loads((ROOT / "data/samples/toy-graph.json").read_text())
    data["nodes"] = [n for n in data["nodes"] if n["id"] in {ACTOR, GOAL, HOST}]
    nodes = {n["id"]: n for n in data["nodes"]}
    nodes[HOST]["enabled"] = True
    owner = {**copy.deepcopy(nodes[ACTOR]), "id": OWNER, "label": "Reset identity"}
    data["nodes"].append(owner)
    data["nodes"].extend(
        {**copy.deepcopy(nodes[GOAL]), "id": group, "label": f"Free group {i}"}
        for i, group in enumerate(GROUPS, 1)
    )
    data["edges"] = [
        edge(ACTOR, GOAL, "WriteDacl"),
        edge(ACTOR, GROUPS[0], "MemberOf"),
        edge(GROUPS[0], GROUPS[1], "MemberOf"),
    ]
    if name == "free_membership":
        data["edges"].append(edge(GROUPS[1], GOAL, "MemberOf"))
    else:
        data["edges"].extend(
            [
                edge(GROUPS[1], OWNER, "GenericAll"),
                edge(OWNER, GOAL, "MemberOf"),
            ]
        )
    data["metadata"]["snapshot_id"] = canonical_digest([data["nodes"], data["edges"]])
    data["metadata"]["description"] = "Synthetic serial routes; not observed AD data"
    graph = EngineGraph.from_canonical(data)
    gates = (
        "security_group",
        "membership_usable",
        "membership_change_allowed",
        "directory_write_allowed",
        "password_policy_accepts",
        "network_rpc_reachable",
        "network_kdc_reachable",
        "authentication_accepted",
    )
    assumptions = [
        {
            "predicate": predicate,
            "subject": actor,
            "target": target,
            "value": True,
            "scope": "neo-minimum-probe",
            "rationale": "Declared finite fixture",
            "provenance_reference": "synthetic://neo-minimum-probe",
        }
        for predicate in gates
        for actor in (ACTOR, OWNER)
        for target in (*GROUPS, OWNER, GOAL, HOST)
        if not (
            name.startswith("reset_auth_")
            and predicate == "authentication_accepted"
            and actor == OWNER
            and target == HOST
        )
    ]
    query = {
        "initial_actor": ACTOR,
        "initial_state": {
            "control": [ACTOR],
            "known_identity": [ACTOR],
            "usable_identity": [[ACTOR, HOST]],
        },
        "authentication_context": HOST,
        "target": GOAL,
        "target_goal": {"kind": "usable_identity_entitlement", "target": GOAL},
        "allowed_techniques": list(ACTION_C),
        "assumptions": assumptions,
        "scenario_reference": "neo-minimum-probe",
        "budget": {"max_paths": 1000, "max_steps": 12, "max_expansions": 20000},
        "top_k": 3,
    }
    if name == "reset_auth_false":
        query["runtime_facts"] = [
            {
                "predicate": "authentication_accepted",
                "subject": OWNER,
                "target": HOST,
                "value": False,
                "origin": "observed_evidence",
                "provenance_reference": "synthetic://neo-minimum-probe/refusal",
            }
        ]
    return graph, query


def oracle(name):
    # Route A: grant GenericAll (2), add membership (1), entitlement (0).
    # Route B: two memberships (0), reset (1), authentication (0), entitlement (0).
    return {
        "certain_minimum_C": 3
        if name.startswith("reset_auth_")
        else 0
        if name == "free_membership"
        else 1,
        "possible_minimum_C": 0
        if name == "free_membership"
        else 3
        if name == "reset_auth_false"
        else 1,
        "minimum_provable": name != "reset_auth_unknown",
    }


def independent_cost(path):
    work = {
        (
            s.result.request.technique_id,
            s.result.request.actor,
            s.result.request.source,
            s.result.request.target,
        )
        for s in path.transition_history
        if ACTION_C[s.result.request.technique_id] != 0
    }
    return sum(ACTION_C[technique] for technique, *_ in work)


def conditioned_reference(graph, name):
    # For this fixture, the only compound actions are fixed serial recipes.
    # An Unknown authentication gate must keep a possible cheaper route open.
    def solve(remove_reset):
        canonical = graph.to_canonical()
        if remove_reset:
            canonical["edges"] = [e for e in canonical["edges"] if e["kind"] != "GenericAll"]
        projected = EngineGraph.from_canonical(canonical)
        costs = {"MemberOf": 0, "GenericAll": 1, "WriteDacl": 3}
        route = shortest_path(projected, ACTOR, GOAL, cost_fn=lambda e, _: costs[e["kind"]])
        hop_route = shortest_path(projected, ACTOR, GOAL, cost_fn=unit_cost)
        return {
            "C": route.cost,
            "nodes": list(route.nodes),
            "edge_ids": [e["id"] for e in route.edges],
            "graph_hops": len(route.edges),
            "hop_only": {
                "graph_hops": len(hop_route.edges),
                "mapped_C": sum(costs[e["kind"]] for e in hop_route.edges),
            },
        }

    return {
        "certain": solve(name.startswith("reset_auth_")),
        "possible": solve(name == "reset_auth_false"),
        "minimum_provable": name != "reset_auth_unknown",
        "scope": "Two serial routes only; preconditions conditioned before Dijkstra",
    }


def evaluate(name, strategy, *, max_paths=1000, max_steps=12, max_expansions=20000):
    graph, query = fixture(name)
    query.update(search_order=strategy)
    query["budget"] = dict(max_paths=max_paths, max_steps=max_steps, max_expansions=max_expansions)
    result = run_attack_query(
        bind_effort_profile(query, graph, load_effort_profile("neo-c-v1")), graph
    )
    programs, exclusions = effort_programs(result)
    by_id = {p["candidate_id"]: p for p in programs}
    for index, path in enumerate(result.paths, 1):
        if replay_path(path, graph, result.materialized_query.catalog) != path.final_state:
            raise AssertionError("Native replay changed final state")
        if independent_cost(path) != by_id[f"generated_{index:04d}"]["effort"]:
            raise AssertionError("Native C differs from independent work-set sum")
    reference = conditioned_reference(graph, name)
    reference_matches = {
        kind: sum(
            [edge["id"] for edge in path.edges] == reference[kind]["edge_ids"]
            and independent_cost(path) == reference[kind]["C"]
            for path in result.paths
        )
        for kind in ("certain", "possible")
    }
    return {
        "case": name,
        "strategy": strategy,
        "budget": query["budget"],
        "graph_sha256": canonical_digest(graph.to_canonical()),
        "query_sha256": canonical_digest(query),
        "status": result.status,
        "reached": result.final_goal_reached,
        "C": (result.min_effort or {}).get("minimum_effort_value"),
        "first_C": by_id.get("generated_0001", {}).get("effort"),
        "programs": len(programs),
        "expansions": result.expansions,
        "truncated": result.truncated,
        "truncation_reason": result.truncation_reason,
        "minimum_proven": result.is_minimum_proven_over_scope,
        "unknown_attempts": sum(bool(a.unknown) for a in result.attempts),
        "rating_exclusions": exclusions,
        "reference_routes_with_native_replay": reference_matches,
        "best_steps": [s.result.request.technique_id for s in result.best_path.transition_history]
        if result.best_path
        else [],
        "program_set_sha256": canonical_digest(
            sorted((p["program_id"], p["effort"]) for p in programs)
        ),
    }


def run():
    rows = [
        evaluate(name, strategy, max_paths=cap)
        for name in CASE_NAMES
        for strategy in ("fifo", "neo_guided")
        for cap in (1, 10, 1000)
    ]
    rows.extend(
        [
            evaluate("two_routes", "neo_guided", max_expansions=1),
            evaluate("two_routes", "neo_guided", max_steps=3),
        ]
    )
    references = {name: conditioned_reference(fixture(name)[0], name) for name in CASE_NAMES}
    for name in CASE_NAMES:
        expected = oracle(name)
        full = [
            r
            for r in rows
            if r["case"] == name
            and r["budget"]
            == {
                "max_paths": 1000,
                "max_steps": 12,
                "max_expansions": 20000,
            }
        ]
        if len(full) != 2 or full[0]["program_set_sha256"] != full[1]["program_set_sha256"]:
            raise AssertionError("FIFO and guided finite program sets differ")
        for result in full:
            if (
                result["C"] != expected["certain_minimum_C"]
                or result["truncated"]
                or result["minimum_proven"] != expected["minimum_provable"]
                or not result["reference_routes_with_native_replay"]["certain"]
            ):
                raise AssertionError("Native minimum disagrees with finite oracle")
        if (
            references[name]["certain"]["C"] != expected["certain_minimum_C"]
            or references[name]["possible"]["C"] != expected["possible_minimum_C"]
        ):
            raise AssertionError("Conditioned Dijkstra disagrees with finite oracle")
    return {
        "version": "neo-minimum-probe/1",
        "synthetic": True,
        "fixture_template_sha256": digest((ROOT / "data/samples/toy-graph.json").read_bytes()),
        "dependency_lock_sha256": digest((ROOT / "requirements-neo.lock").read_bytes()),
        "source_pins": execution_source_pins(),
        "runner_sha256": digest(Path(__file__).read_bytes()),
        "effort_profile": load_effort_profile("neo-c-v1"),
        "oracles": {name: oracle(name) for name in CASE_NAMES},
        "references": references,
        "rows": rows,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args(argv)
    if args.output_dir.exists():
        raise FileExistsError(args.output_dir)
    report = run()
    args.output_dir.mkdir(parents=True, exist_ok=False)
    _atomic_json(args.output_dir / "results.json", report)
    print(
        json.dumps(
            {"queries": len(report["rows"]), "results": str(args.output_dir / "results.json")}
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
