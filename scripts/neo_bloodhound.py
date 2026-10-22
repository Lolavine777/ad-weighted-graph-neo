"""Prepare fixed exploratory cohorts and read-only BloodHound queries, not a live comparison."""

from __future__ import annotations

import argparse
import json
import shlex
import shutil
from pathlib import Path

from scripts.neo_decision import SEED, select_sources
from scripts.neo_domain import build_survey, input_coverage, scenario_profile, techniques_for
from src.data.manifest import load_manifest, verify_manifest
from src.engine.batch import _atomic_json, execution_source_pins
from src.engine.graph import EngineGraph
from src.engine.query_cli import digest
from src.engine.ranking.resolution_service import canonical_digest

ROOT = Path(__file__).resolve().parents[1]
DIRECTORY_EDGES = ("MemberOf", "GenericAll", "WriteDacl", "ForceChangePassword")
HOST_EDGES = DIRECTORY_EDGES + ("AdminTo", "CanPSRemote", "HasSession")
BUDGET = {"max_paths": 10, "max_steps": 12, "max_expansions": 4096}
DOMAIN_SIDS = {
    "seamless": "S-1-5-21-1271839998-3495686680-2211690266",
    "wraith": "S-1-5-21-3702535222-3822678775-2090119576",
}


def literal(value):
    return "'" + value.replace("\\", "\\\\").replace("'", "\\'") + "'"


def path_query(source, target, scenario, *, enabled_users=False):
    relations = "|".join(HOST_EDGES if scenario == "host-compromise" else DIRECTORY_EDGES)
    query = (
        f"MATCH (s {{objectid: {literal(source)}}}), (t:Group {{objectid: {literal(target)}}})\n"
        f"MATCH p = shortestPath((s)-[:{relations}*1..12]->(t))\n"
    )
    if enabled_users:
        query += "WHERE all(n IN nodes(p) WHERE NOT n:User OR coalesce(n.enabled, true))\n"
    return query + "RETURN p;"


def prepare_dataset(
    graph, snapshot, scenario, native_output, *, session_coverage=False, expected_domain=None
):
    domains = [n for n in graph.nodes(kind="Domain") if not n["is_boundary"]]
    if len(domains) != 1:
        raise ValueError("Comparison requires exactly one non-boundary Domain")
    domain_sid = domains[0]["id"]
    if expected_domain is not None and domain_sid != expected_domain:
        raise ValueError("Snapshot has a different domain from the declared dataset")
    inventory, full = build_survey(graph, domain_sid=domain_sid, scenario=scenario, **BUDGET)
    eligible = {s["node_id"]: s for s in inventory["sources"]}
    selected = select_sources(inventory["sources"])
    if session_coverage:
        selected = [
            eligible[source]
            for source in sorted(
                {e["source"] for e in graph.edges(kind="HasSession") if e["source"] in eligible}
            )
        ]
    if not selected:
        raise ValueError("Empty declared cohort")
    ids = sorted(s["node_id"] for s in selected)
    _, request = build_survey(
        graph, domain_sid=domain_sid, scenario=scenario, source_ids=ids, **BUDGET
    )
    sources = {s.node_id: s for s in request.sources}
    pairs = [
        {
            "id": canonical_digest([scenario, source, goal.target_node_id])[7:23],
            "source": source,
            "source_label": graph.node(source)["label"],
            "source_profile": sources[source].profile_kind,
            "target": goal.target_node_id,
            "target_label": graph.node(goal.target_node_id)["label"],
            "structural_cypher": path_query(source, goal.target_node_id, scenario),
            "enabled_user_cypher": path_query(
                source, goal.target_node_id, scenario, enabled_users=True
            ),
        }
        for source in ids
        for goal in request.resolve_target_goals()
    ]
    command = [
        ".venv/bin/python",
        "-m",
        "scripts.neo_domain",
        "--snapshot",
        str(snapshot),
        "--scenario",
        scenario,
        "--output-dir",
        str(native_output),
        "--workers",
        "2",
    ]
    command.extend(["--domain-sid", domain_sid])
    for key, value in BUDGET.items():
        command.extend(["--" + key.replace("_", "-"), str(value)])
    for source in ids:
        command.extend(["--source", source])
    domain = graph.node(inventory["domain_sid"])["domain"].upper()
    relations = "|".join(HOST_EDGES if scenario == "host-compromise" else DIRECTORY_EDGES)
    return {
        "selection": "all eligible observed session hosts (coverage stratum, not random)"
        if session_coverage
        else "3 Users + 2 Computers, deterministic hash; not outcome-filtered",
        "selection_seed": None if session_coverage else SEED,
        "eligible_sources": len(full.sources),
        "snapshot_sha256": digest(Path(snapshot).read_bytes()),
        "snapshot_id": graph.metadata["snapshot_id"],
        "domain_sid": inventory["domain_sid"],
        "scenario": scenario,
        "input_coverage": input_coverage(graph, request, scenario),
        "request": request.to_dict(),
        "scenario_policy": scenario_profile(graph, scenario).canonical_dict(),
        "techniques": techniques_for(scenario),
        "pairs": pairs,
        "neo_argv": command,
        "parity_cypher": [
            f"MATCH (n) WHERE toUpper(n.domain) = {literal(domain)}\n"
            "RETURN n.objectid AS id, labels(n) AS labels, n.enabled AS enabled;",
            f"MATCH (s)-[r:{relations}]->(t)\n"
            f"WHERE toUpper(s.domain) = {literal(domain)} "
            f"AND toUpper(t.domain) = {literal(domain)}\n"
            "RETURN s.objectid AS source, type(r) AS kind, t.objectid AS target;",
        ],
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seamless-snapshot", required=True, type=Path)
    parser.add_argument("--wraith-snapshot", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args(argv)
    if args.output_dir.exists():
        raise FileExistsError(args.output_dir)
    verified, datasets = {}, {}
    for name, directory, filename, snapshot, scenario in (
        ("seamless", "SEAMLESS", "seamless-raw-v1.json", args.seamless_snapshot, "identity"),
        (
            "wraith",
            "ad_sampledata",
            "ad-sampledata-v1.json",
            args.wraith_snapshot,
            "host-compromise",
        ),
    ):
        path = ROOT / "data/samples/manifests" / filename
        manifest = load_manifest(path)
        errors = verify_manifest(ROOT / "data/raw" / directory, manifest)
        if errors:
            raise ValueError(f"{name} raw integrity failure: {errors}")
        graph = EngineGraph.from_snapshot(snapshot.read_text(encoding="utf-8"))
        if graph.metadata["snapshot_id"] != manifest["snapshot_id"]:
            raise ValueError(f"{name} snapshot is not bound to verified raw inputs")
        verified[name] = {
            "snapshot_id": manifest["snapshot_id"],
            "manifest_sha256": digest(path.read_bytes()),
            "files_verified": len(manifest["files"]),
        }
        datasets[name] = prepare_dataset(
            graph, snapshot, scenario, args.output_dir / name, expected_domain=DOMAIN_SIDS[name]
        )
        if name == "wraith":
            datasets["wraith-sessions"] = prepare_dataset(
                graph,
                snapshot,
                scenario,
                args.output_dir / "wraith-sessions",
                session_coverage=True,
                expected_domain=DOMAIN_SIDS[name],
            )
    compose = ROOT / "deploy/bloodhound/compose.seamless.yml"
    pack = {
        "version": "neo-bloodhound-comparison/1",
        "phase": "prepared_not_compared",
        "study": "Exploratory, not blind: datasets and some cases were previously inspected",
        "raw_inputs": verified,
        "source_pins": execution_source_pins(),
        "runner_sha256": digest(Path(__file__).read_bytes()),
        "selection_runner_sha256": digest((ROOT / "scripts/neo_decision.py").read_bytes()),
        "native_runner_sha256": digest((ROOT / "scripts/neo_domain.py").read_bytes()),
        "bloodhound": {
            "status": "not_run",
            "graph_parity": "not_checked",
            "docker_cli": "available_daemon_unchecked" if shutil.which("docker") else "missing",
            "compose": str(compose.relative_to(ROOT)),
            "compose_sha256": digest(compose.read_bytes()),
            "version": "9.8.0 (existing digest-pinned compose; not necessarily latest)",
        },
        "limits": [
            "Use isolated databases. Preparation makes no service calls or mutations.",
            "SEAMLESS needs the verified CE adapter; retain original and converted hashes.",
            "WRAITH uses export 20240305111414 only, not the other two domains.",
            "Check exact IDs/types, disabled properties and scoped triples before comparing paths.",
            "Explain primary groups, self-ACE filters, boundary nodes and derived AdminTo deltas.",
            "Scoped custom queries are not default full-capability BloodHound pathfinding.",
            "Structural paths are not executable programs; unsupported is not a BloodHound defect.",
            "Local admin is not machine network identity. Session reuse is assumed, not observed.",
            "12 graph hops differ from 12 semantic steps: no negative-proof or speed comparison.",
            "shortestPath ties are arbitrary; they cannot establish C superiority.",
            "C is expert scenario effort and best-found, not empirical time or global minimum.",
            "WRAITH strata can overlap: keep them separate and deduplicate overall counts.",
            "Rediscover bypasses on both sides; cutting a witness is not source disconnection.",
        ],
        "datasets": datasets,
    }
    args.output_dir.mkdir(parents=True, exist_ok=False)
    _atomic_json(args.output_dir / "comparison.json", pack)
    (args.output_dir / "neo-commands.sh").write_text(
        "#!/bin/sh\nset -eu\n# Run from repo root; no external services are modified.\n"
        + "\n".join(shlex.join(d["neo_argv"]) for d in datasets.values())
        + "\n",
        encoding="utf-8",
    )
    for name, dataset in datasets.items():
        queries = dataset["parity_cypher"] + [
            f"// {p['id']} {variant}\n{p[key]}"
            for p in dataset["pairs"]
            for variant, key in (
                ("structural", "structural_cypher"),
                ("enabled_users", "enabled_user_cypher"),
            )
        ]
        (args.output_dir / f"{name}.cypher").write_text(
            "\n\n".join(queries) + "\n", encoding="utf-8"
        )
    print(
        json.dumps(
            {
                "phase": pack["phase"],
                "bloodhound": pack["bloodhound"],
                "pairs_by_stratum": {n: len(d["pairs"]) for n, d in datasets.items()},
                "pack_sha256": digest((args.output_dir / "comparison.json").read_bytes()),
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
