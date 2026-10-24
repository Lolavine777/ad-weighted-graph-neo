"""Reprice fixed native programs under declared hypothetical C rubric probes.

This experiment never changes production ratings, feasibility, or search order.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from copy import deepcopy
from itertools import combinations
from pathlib import Path

from scripts.neo_domain import scenario_profile, techniques_for
from scripts.neo_minimum_probe import fixture
from scripts.research.source_goal_batch import BatchQueryRequest
from src.engine.batch import _atomic_json, _query_for_cell, execution_source_pins
from src.engine.graph import EngineGraph
from src.engine.query import run_attack_query
from src.engine.query_cli import digest
from src.engine.ranking.effort_profiles import bind_effort_profile, load_effort_profile
from src.engine.ranking.resolution_service import canonical_digest
from src.engine.semantics.credentials import replay_path
from src.engine.top_k import effort_programs

ROOT = Path(__file__).resolve().parents[1]
FAMILIES = {
    "reset": ("genericall_reset_password", "reset_target_password", "scenario_reset_password"),
    "activation": ("acquire_reset_identity",),
    "membership": ("genericall_add_member",),
    "dacl_control": ("genericall_grant_write_dacl",),
    "acl_grant": ("grant_new_object_right",),
    "host_execution": ("obtain_admin_execution_on_host", "scenario_winrm_admin"),
    "winrm_command": ("open_winrm_remote_session",),
    "session": ("use_session_identity",),
}


def variants():
    baseline = load_effort_profile("neo-c-v1")["classes"]
    if set(baseline) != {t for family in FAMILIES.values() for t in family}:
        raise ValueError("Protocol no longer covers exactly the production C classes")
    result = {"baseline": deepcopy(baseline)}

    def add(name, changes):
        classes = deepcopy(baseline)
        for family, delta in changes.items():
            for technique in FAMILIES[family]:
                cls = classes[technique]
                cls["t2"] += delta
                cls["cost"] = cls["t1"] + cls["t2"] - 2
                if cls["t2"] not in (1, 2, 3):
                    raise ValueError("Probe exceeds the rubric")
        result[name] = classes

    for family, techniques in FAMILIES.items():
        for delta in (-1, 1):
            if all(baseline[t]["t2"] + delta in (1, 2, 3) for t in techniques):
                add(f"{family}_{delta:+d}", {family: delta})
    add(
        "reset_dearer_acl_cheaper", {"reset": 1, "activation": 1, "membership": -1, "acl_grant": -1}
    )
    add(
        "session_dearer_directory_cheaper",
        {
            "host_execution": 1,
            "session": 1,
            "reset": -1,
            "membership": -1,
            "dacl_control": -1,
            "acl_grant": -1,
        },
    )
    return result


def reprice(program, classes):
    units, ledger = set(program["work_unit_ids"]), program["work_unit_ledger"]
    if units != set(ledger):
        raise ValueError("Work-unit ledger is incomplete or has unexpected units")
    total = 0
    for unit in units:
        basis = ledger[unit]
        if basis.get("classification") != "active_work" or basis.get("technique") not in classes:
            raise ValueError("Work unit has no supported active-work C class")
        cls = classes[basis["technique"]]
        if any(type(cls[k]) is not int or cls[k] not in (1, 2, 3) for k in ("t1", "t2")):
            raise ValueError("Invalid T1/T2 rubric input")
        cost = cls["t1"] + cls["t2"] - 2
        if cls["cost"] != cost:
            raise ValueError("Cost disagrees with T1+T2-2")
        total += cost
    return total


def compare(programs, classes):
    if not programs:
        return None
    baseline = load_effort_profile("neo-c-v1")["classes"]
    before = {p["program_id"]: reprice(p, baseline) for p in programs}
    after = {p["program_id"]: reprice(p, classes) for p in programs}
    best_before = {key for key, value in before.items() if value == min(before.values())}
    best_after = {key for key, value in after.items() if value == min(after.values())}
    ordered = sorted(programs, key=lambda p: (after[p["program_id"]], p["program_key"]))
    prior = sorted(programs, key=lambda p: (before[p["program_id"]], p["program_key"]))
    return {
        "minimum_C": min(after.values()),
        "best_program_ids": sorted(best_after),
        "top_3_ids": [p["program_id"] for p in ordered[:3]],
        "best_C_changed": min(before.values()) != min(after.values()),
        "best_set_changed": best_before != best_after,
        "best_set_disjoint": best_before.isdisjoint(best_after),
        "top_3_set_changed": {p["program_id"] for p in ordered[:3]}
        != {p["program_id"] for p in prior[:3]},
        "strict_rank_reversals": sum(
            (before[a] - before[b]) * (after[a] - after[b]) < 0 for a, b in combinations(before, 2)
        ),
    }


def programs_for(query, graph):
    result = run_attack_query(query, graph)
    programs, exclusions = effort_programs(result)
    if result.status == "error" or exclusions:
        raise ValueError(f"Query failed or has unpriced programs: {exclusions}")
    baseline = load_effort_profile("neo-c-v1")["classes"]
    for program in programs:
        if reprice(program, baseline) != program["effort"]:
            raise AssertionError("Independent unique-work sum differs from public C")
    for path in result.paths:
        if replay_path(path, graph, result.materialized_query.catalog) != path.final_state:
            raise AssertionError("Native replay changed the generated program")
    return programs, {
        "status": result.status,
        "reached": result.final_goal_reached,
        "programs": len(programs),
        "expansions": result.expansions,
        "truncated": result.truncated,
        "minimum_proven": result.is_minimum_proven_over_scope,
        "unknown_attempts": sum(bool(a.unknown) for a in result.attempts),
    }


def run(args):
    args.output_dir.mkdir(parents=True, exist_ok=False)
    pack = json.loads(args.pack.read_text(encoding="utf-8"))
    fixed = json.loads(
        (ROOT / "reports/neo/bloodhound-query-pack.json").read_text(encoding="utf-8")
    )
    prices = variants()
    graph, query = fixture("two_routes")
    synthetic, _ = programs_for(
        bind_effort_profile(query, graph, load_effort_profile("neo-c-v1")), graph
    )
    control = {
        name: compare(synthetic, prices[name]) for name in ("baseline", "reset_dearer_acl_cheaper")
    }
    if (
        control["baseline"]["minimum_C"] != 1
        or not control["reset_dearer_acl_cheaper"]["best_set_disjoint"]
    ):
        raise AssertionError("Synthetic reversal control failed")
    unique, rows = {}, []
    for dataset_name, snapshot in [
        ("seamless", args.seamless_snapshot),
        ("wraith", args.wraith_snapshot),
    ]:
        graph = EngineGraph.from_snapshot(snapshot.read_text(encoding="utf-8"))
        strata = [dataset_name, "wraith-sessions"] if dataset_name == "wraith" else [dataset_name]
        for name in strata:
            dataset = pack["datasets"][name]
            if digest(snapshot.read_bytes()) != dataset["snapshot_sha256"]:
                raise ValueError("Snapshot hash differs from the prepared pack")
            for key in ("pairs", "request", "scenario", "scenario_policy", "techniques"):
                if dataset[key] != fixed["datasets"][name][key]:
                    raise ValueError("Fixed cohort scope changed")
            policy = scenario_profile(graph, dataset["scenario"])
            techniques = techniques_for(dataset["scenario"])
            if (
                policy.canonical_dict() != dataset["scenario_policy"]
                or list(techniques) != dataset["techniques"]
            ):
                raise ValueError("Executable policy or techniques differ from the fixed scope")
            request = BatchQueryRequest.from_dict(dataset["request"])
            sources = {s.node_id: s for s in request.sources}
            goals = {g.target_node_id: g for g in request.resolve_target_goals()}
            for pair in dataset["pairs"]:
                query, error = _query_for_cell(
                    request,
                    sources[pair["source"]],
                    goals[pair["target"]],
                    graph,
                    techniques,
                    request.common_budget,
                    scenario_policy=policy,
                    effort_profile=load_effort_profile("neo-c-v1"),
                    search_order="neo_guided",
                )
                if error is not None:
                    raise ValueError(str(error))
                programs, discovery = programs_for(query, graph)
                key = pair["source"], pair["target"]
                signature = canonical_digest(
                    sorted((p["program_id"], p["effort"]) for p in programs)
                )
                if key in unique and unique[key]["program_set_sha256"] != signature:
                    raise AssertionError("Overlapping strata have different candidate sets")
                row = {
                    **pair,
                    "stratum": name,
                    "discovery": discovery,
                    "program_set_sha256": signature,
                    "probes": {
                        label: compare(programs, classes) for label, classes in prices.items()
                    },
                }
                _atomic_json(
                    args.output_dir / f"{name}-{pair['id']}.json", {**row, "programs": programs}
                )
                unique.setdefault(key, row)
                rows.append(row)
                print(json.dumps({"stratum": name, "pair": pair["id"], **discovery}), flush=True)
    aggregates = {}
    for label in prices:
        evaluated = [r["probes"][label] for r in unique.values() if r["probes"][label] is not None]
        aggregates[label] = {
            "witness_pairs": len(evaluated),
            **{
                k: sum(r[k] for r in evaluated)
                for k in (
                    "best_C_changed",
                    "best_set_changed",
                    "best_set_disjoint",
                    "top_3_set_changed",
                    "strict_rank_reversals",
                )
            },
            "minimum_C_distribution": dict(Counter(r["minimum_C"] for r in evaluated)),
        }
    report = {
        "version": "neo-fixed-program-C-sensitivity/1",
        "authority": "hypothetical ordinal sensitivity, not adopted ratings",
        "source_pins": execution_source_pins(),
        "runner_sha256": digest(Path(__file__).read_bytes()),
        "protocol_sha256": digest((ROOT / "reports/neo/cost-sensitivity-protocol.md").read_bytes()),
        "pack_sha256": digest(args.pack.read_bytes()),
        "raw_inputs": pack["raw_inputs"],
        "snapshot_sha256": {
            name: digest(path.read_bytes())
            for name, path in (
                ("seamless", args.seamless_snapshot),
                ("wraith", args.wraith_snapshot),
            )
        },
        "prices": prices,
        "synthetic_control": control,
        "stratum_query_runs": len(rows),
        "unique_pairs": len(unique),
        "pair_programs": sum(r["discovery"]["programs"] for r in unique.values()),
        "aggregates": aggregates,
        "pairs": list(unique.values()),
        "limits": [
            "Fixed discovered candidate sets only; no search under perturbed costs.",
            "All real-data C values remain best-found; no global sensitivity "
            "or blind-evaluation claim.",
            "No-path cells remain unranked, not zero-cost; no P/I inference "
            "or empirical error model.",
        ],
    }
    _atomic_json(args.output_dir / "results.json", report)
    print(json.dumps({"unique_pairs": len(unique), "aggregates": aggregates}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("pack", "seamless-snapshot", "wraith-snapshot", "output-dir"):
        parser.add_argument("--" + name, type=Path, required=True)
    run(parser.parse_args())


if __name__ == "__main__":
    main()
