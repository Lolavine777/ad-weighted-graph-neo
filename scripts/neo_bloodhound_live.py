"""Collect the fixed CE comparison and three isolated WRAITH counterfactuals.

Use the baseline runner's BLOODHOUND_PORT and NEO4J_WEB_PORT environment variables.
Only --remediation writes relationships, journals them and restores their properties.
"""

from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path

from scripts import neo_domain as native
from scripts import run_bloodhound_baseline as ce
from scripts.neo_bloodhound import DIRECTORY_EDGES, HOST_EDGES, path_query
from src.engine.batch import _atomic_json
from src.engine.graph import EngineGraph
from src.engine.query_cli import digest
from src.engine.ranking.resolution_service import canonical_digest
from src.engine.remediation import EffectiveSnapshotFacts
from src.parser.snapshot_facts import graph_digest

COMPOSE = Path(__file__).resolve().parents[1] / "deploy/bloodhound/compose.seamless.yml"
INVENTORY_NODES = (
    "MATCH (n) WHERE n.objectid IS NOT NULL RETURN n.objectid AS id, "
    "labels(n) AS labels, n.enabled AS enabled, n.domain AS domain"
)
INVENTORY_EDGES = (
    "MATCH (s)-[r]->(t) RETURN s.objectid AS source, type(r) AS kind, t.objectid AS target"
)


def canonical_id(raw, ids, sid, domain):
    """Match documented CE aliases only when their canonical identity exists."""
    if raw in ids:
        return raw
    if raw.lower() in ids:
        return raw.lower()
    prefix, separator, suffix = raw.upper().partition("-S-")
    if separator and prefix != domain.upper():
        return raw
    candidate = "S-" + suffix if separator else raw.upper()
    scoped = f"domain:sid:{sid}:{candidate}"
    if scoped in ids:
        return scoped
    return candidate if candidate in ids else raw


def ordered_path(data, source, target):
    nodes, remaining = data["nodes"], list(data["edges"])
    current = next((k for k, n in nodes.items() if n["objectId"] == source), None)
    result = []
    while remaining:
        choices = [e for e in remaining if e["source"] == current]
        if len(choices) != 1:
            raise ValueError("API graph is not one directed source-target path")
        edge = choices[0]
        result.append(
            {
                "source": nodes[edge["source"]]["objectId"],
                "source_label": nodes[edge["source"]]["label"],
                "kind": edge["kind"],
                "target": nodes[edge["target"]]["objectId"],
                "target_label": nodes[edge["target"]]["label"],
            }
        )
        current = edge["target"]
        remaining.remove(edge)
    if current is None or nodes[current]["objectId"] != target:
        raise ValueError("API path does not reach the declared target")
    return result


def bloodhound_query(query, token, source, target):
    started = time.perf_counter()
    request = urllib.request.Request(
        ce.BLOODHOUND_URL + "/api/v2/graphs/cypher",
        data=json.dumps({"query": query, "include_properties": True}).encode(),
        headers={"Content-Type": "application/json", "Authorization": "Bearer " + token},
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            status, payload = response.status, json.load(response)
    except urllib.error.HTTPError as error:
        status, payload = error.code, json.load(error)
    row = {
        "query": query,
        "http_status": status,
        "seconds": time.perf_counter() - started,
        "response": payload,
    }
    if status == 200:
        row["path"] = ordered_path(payload["data"], source, target)
    elif status == 404 and ce.query_neo4j(query) == []:
        row["empty_confirmed"] = True
    else:
        raise RuntimeError(f"BloodHound query failed: {row}")
    return row


def parity(graph, inventory, dataset):
    neo = {n["id"]: n for n in graph.nodes()}
    domain = next(n for n in graph.nodes(kind="Domain") if not n["is_boundary"])

    def resolve(raw):
        return canonical_id(raw, neo, domain["id"], domain["domain"])

    bh = defaultdict(list)
    for node in inventory["all_nodes"]:
        bh[resolve(node["id"])].append(node)
    edges = HOST_EDGES if dataset == "wraith" else DIRECTORY_EDGES
    a = {(e["source"], e["kind"], e["target"]) for e in graph.edges() if e["kind"] in edges}
    b = {
        (resolve(e["source"]), e["kind"], resolve(e["target"]))
        for e in inventory["all_edges"]
        if e["kind"] in edges
    }
    shared = set(neo) & set(bh)
    common_nodes = {e for e in b if e[0] in neo and e[2] in neo}
    core = {"User", "Computer", "Group", "Domain", "GPO", "OU"}
    bh_core = {k for k, ns in bh.items() if any(core & set(n["labels"]) for n in ns)}
    return {
        "id_aliases": {n["id"]: k for k, ns in bh.items() for n in ns if n["id"] != k},
        "alias_collisions": {k: ns for k, ns in bh.items() if len(ns) > 1},
        "neo_only_nodes": [neo[k] for k in sorted(set(neo) - set(bh))],
        "bh_only_core_nodes": {k: bh[k] for k in sorted(bh_core - set(neo))},
        "type_mismatches": {
            k: {"neo": neo[k], "bh": bh[k]}
            for k in sorted(shared)
            if not any(neo[k]["kind"] in n["labels"] for n in bh[k])
        },
        "enabled_mismatches": {
            k: {"neo": neo[k].get("enabled"), "bh": [n["enabled"] for n in bh[k]]}
            for k in sorted(shared)
            if not any(neo[k].get("enabled") == n["enabled"] for n in bh[k])
        },
        "neo_only_triples": sorted(a - b),
        "bh_only_common_node_triples": sorted(common_nodes - a),
        "bh_outside_neo_node_triples": sorted(b - common_nodes),
        "counts": {
            "neo_nodes": len(neo),
            "bh_nodes": len(inventory["all_nodes"]),
            "bh_core_nodes": len(bh_core),
            "shared_ids": len(shared),
            "neo_scoped_triples": len(a),
            "bh_common_node_scoped_triples": len(common_nodes),
            "shared_triples": len(a & b),
            "neo_only_by_kind": dict(Counter(e[1] for e in a - b)),
            "bh_only_common_by_kind": dict(Counter(e[1] for e in common_nodes - a)),
            "bh_outside_neo_nodes_by_kind": dict(Counter(e[1] for e in b - common_nodes)),
        },
    }


def collect(args, pack, graph, token):
    dataset = pack["datasets"][args.dataset]
    inventory = {
        "pack_nodes": ce.query_neo4j(dataset["parity_cypher"][0]),
        "pack_edges": ce.query_neo4j(dataset["parity_cypher"][1]),
        "all_nodes": ce.query_neo4j(INVENTORY_NODES),
        "all_edges": ce.query_neo4j(INVENTORY_EDGES),
    }
    _atomic_json(args.output_dir / "inventory.json", inventory)
    _atomic_json(args.output_dir / "parity.json", parity(graph, inventory, args.dataset))
    rows = []
    for name, cohort in pack["datasets"].items():
        if name.split("-")[0] != args.dataset:
            continue
        for pair in cohort["pairs"]:
            for variant, key in (
                ("structural", "structural_cypher"),
                ("enabled", "enabled_user_cypher"),
            ):
                row = bloodhound_query(pair[key], token, pair["source"], pair["target"])
                rows.append({**pair, "stratum": name, "variant": variant, **row})
                _atomic_json(args.output_dir / "queries.json", rows)
    # Audit ties for the two predeclared pairs whose returned route maps to C=5 vs neo C=4.
    ties = []
    if args.dataset == "seamless":
        for pair in dataset["pairs"]:
            if not pair["source_label"].startswith(("BENNY_", "EVAN_")):
                continue
            if not pair["target"].endswith("-519"):
                continue
            query = pair["enabled_user_cypher"].replace("shortestPath", "allShortestPaths")
            query = query.replace(
                "RETURN p;",
                "RETURN [n IN nodes(p) | n.objectid] AS ids, "
                "[n IN nodes(p) | labels(n)] AS labels, "
                "[r IN relationships(p) | type(r)] AS kinds LIMIT 1001;",
            )
            paths = ce.query_neo4j(query)
            ties.append(
                {
                    "pair_id": pair["id"],
                    "query": query,
                    "rows": paths,
                    "truncated": len(paths) == 1001,
                }
            )
        _atomic_json(args.output_dir / "shortest-ties.json", ties)
    return {"requests": len(rows), "paths": sum(r["http_status"] == 200 for r in rows)}


def parameter_query(query, parameters):
    request = urllib.request.Request(
        ce.NEO4J_URL,
        data=json.dumps({"statements": [{"statement": query, "parameters": parameters}]}).encode(),
        headers={"Content-Type": "application/json", "Authorization": "Basic " + ce.NEO4J_AUTH},
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        data = json.load(response)
    if data["errors"]:
        raise RuntimeError(data["errors"])
    result = data["results"][0]
    return [dict(zip(result["columns"], row["row"], strict=True)) for row in result["data"]]


def remediate(args, pack, graph, token):
    """Each edit starts from the intact graph and the same declared initial capability."""
    labels = {n["label"]: n["id"] for n in graph.nodes()}
    rodc = labels["RODCMANAGER@WRAITH.CORP"]
    bm = labels["BM@WRAITH.CORP"]
    admin = labels["ADMINISTRATORS@WRAITH.CORP"]
    ca = labels["EXTCA01.WRAITH.CORP"]
    sid = pack["datasets"]["wraith"]["domain_sid"]
    cases = [
        ("rodc-membership", rodc, rodc, "MemberOf", admin, "WRAITH.CORP-S-1-5-32-544"),
        ("extca-session", ca, ca, "HasSession", bm, bm),
        ("bm-da-membership", ca, bm, "MemberOf", sid + "-512", sid + "-512"),
    ]
    results = []
    for name, source, es, kind, et, bh_target in cases:
        folder = args.output_dir / name
        folder.mkdir()
        dataset = pack["datasets"]["wraith-sessions" if source == ca else "wraith"]
        native._initialize(args.snapshot, dataset["request"], dataset["scenario"])
        pairs = [(source, p["target"]) for p in dataset["pairs"] if p["source"] == source]
        assert len(pairs) == 2
        before = [native._evaluate(p) for p in pairs]
        edge = next(
            e for e in graph.edges() if (e["source"], e["kind"], e["target"]) == (es, kind, et)
        )
        canonical = graph.to_canonical()
        canonical["edges"] = [e for e in canonical["edges"] if e["id"] != edge["id"]]
        native._graph = EngineGraph.from_canonical(
            canonical,
            snapshot_facts=EffectiveSnapshotFacts(
                graph.snapshot_facts, (), name, graph_digest(canonical)
            ),
        )
        after = [native._evaluate(p) for p in pairs]
        assert all(row["status"] != "error" for row in before + after)

        def query(pair):
            cypher = path_query(*pair, "host-compromise", enabled_users=True)
            return bloodhound_query(cypher, token, *pair)

        bh_before = [query(p) for p in pairs]
        match = f"MATCH (s {{objectid:$source}})-[r:{kind}]->(t {{objectid:$target}})"
        parameters = {"source": es, "target": bh_target}
        saved = parameter_query(match + " RETURN properties(r) AS props", parameters)
        assert len(saved) == 1

        def fingerprint():
            rows = ce.query_neo4j(INVENTORY_EDGES + ", properties(r) AS props")
            return canonical_digest(sorted(rows, key=lambda x: json.dumps(x, sort_keys=True)))

        original = fingerprint()
        journal = {
            **parameters,
            "kind": kind,
            "props": saved[0]["props"],
            "before_digest": original,
        }
        _atomic_json(folder / "restore-journal.json", journal)
        try:
            parameter_query(match + " DELETE r", parameters)
            bh_after = [query(p) for p in pairs]
        finally:
            parameter_query(
                f"MATCH (s {{objectid:$source}}),(t {{objectid:$target}}) "
                f"MERGE (s)-[r:{kind}]->(t) SET r=$props",
                {**parameters, "props": saved[0]["props"]},
            )
            restored = fingerprint()
            assert restored == original
        result = {
            "case": name,
            "source": source,
            "edit": edge,
            "pairs": pairs,
            "neo_before": before,
            "neo_after": after,
            "bloodhound_before": bh_before,
            "bloodhound_after": bh_after,
            "restored_relationship_data_digest": restored,
            "restore_verified": True,
        }
        _atomic_json(folder / "results.json", result)
        results.append(result)
    _atomic_json(args.output_dir / "remediation.json", results)
    return {"independent_interventions": len(results), "restored": True}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pack", type=Path, required=True)
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--dataset", choices=("seamless", "wraith"), required=True)
    parser.add_argument("--project-name", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--remediation", action="store_true")
    args = parser.parse_args(argv)
    if args.remediation and args.dataset != "wraith":
        parser.error("--remediation requires WRAITH")
    pack = json.loads(args.pack.read_text())
    graph = EngineGraph.from_snapshot(args.snapshot.read_text())
    assert graph.metadata["snapshot_id"] == pack["datasets"][args.dataset]["snapshot_id"]
    assert digest(args.snapshot.read_bytes()) == pack["datasets"][args.dataset]["snapshot_sha256"]
    for service, port, expected in (
        ("bloodhound", "8080", ce.BLOODHOUND_URL),
        ("graph-db", "7474", ce.NEO4J_URL.removesuffix("/db/neo4j/tx/commit")),
    ):
        published = ce.run_cmd(
            [
                "docker",
                "compose",
                "-f",
                str(COMPOSE),
                "-p",
                args.project_name,
                "port",
                service,
                port,
            ]
        ).strip()
        if expected != "http://" + published:
            raise ValueError(f"Endpoint does not belong to selected project: {service}")
    args.output_dir.mkdir(parents=True, exist_ok=False)
    token = ce.login(ce.get_admin_password(compose_file=COMPOSE, project_name=args.project_name))
    result = (
        remediate(args, pack, graph, token)
        if args.remediation
        else collect(args, pack, graph, token)
    )
    _atomic_json(
        args.output_dir / "run.json",
        {
            **result,
            "pack_sha256": digest(args.pack.read_bytes()),
            "snapshot_sha256": digest(args.snapshot.read_bytes()),
            "runner_sha256": digest(Path(__file__).read_bytes()),
            "bloodhound_url": ce.BLOODHOUND_URL,
            "neo4j_url": ce.NEO4J_URL,
            "project_name": args.project_name,
        },
    )
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
