"""Post-LocalGroup diagnostic; journals and restores only existing lab sessions."""

import argparse
import json
from contextlib import ExitStack
from pathlib import Path

from scripts import neo_bloodhound_live as live
from src.engine.graph import EngineGraph
from src.engine.remediation import EffectiveSnapshotFacts
from src.parser.snapshot_facts import graph_digest


def run(args):
    snapshot = args.snapshot
    pack = json.loads(args.pack.read_text())
    dataset = pack["datasets"]["wraith"]
    graph = EngineGraph.from_snapshot(snapshot.read_text())
    if live.digest(snapshot.read_bytes()) != dataset["snapshot_sha256"]:
        raise ValueError("Snapshot does not match the comparison pack")
    labels = {n["label"]: n["id"] for n in graph.nodes()}
    source = labels["TRUSTER@WRAITH.CORP"]
    bm = labels["BM@WRAITH.CORP"]
    pairs = [(source, p["target"]) for p in dataset["pairs"] if p["source"] == source]
    if len(pairs) != 2:
        raise ValueError("Diagnostic requires exactly two declared TRUSTER pairs")
    project = args.project_name
    for service, port, expected in [
        ("bloodhound", "8080", live.ce.BLOODHOUND_URL),
        ("graph-db", "7474", live.ce.NEO4J_URL.removesuffix("/db/neo4j/tx/commit")),
    ]:
        published = live.ce.run_cmd(
            ["docker", "compose", "-f", str(live.COMPOSE), "-p", project, "port", service, port]
        ).strip()
        if expected != "http://" + published:
            raise ValueError(f"Endpoint does not belong to selected project: {service}")
    folder = args.output_dir
    folder.mkdir(parents=True, exist_ok=False)
    token = live.ce.login(
        live.ce.get_admin_password(compose_file=live.COMPOSE, project_name=project)
    )

    def fingerprint():
        rows = live.ce.query_neo4j(live.INVENTORY_EDGES + ", properties(r) AS props")
        return live.canonical_digest(sorted(rows, key=lambda r: json.dumps(r, sort_keys=True)))

    def ce_rows():
        return [
            live.bloodhound_query(
                live.path_query(*p, "host-compromise", enabled_users=True), token, *p
            )
            for p in pairs
        ]

    original = fingerprint()
    results = []
    # One session removal is the original intervention; both sessions is a diagnostic follow-up.
    for hosts in [("EXTCA01.WRAITH.CORP",), ("EXTCA01.WRAITH.CORP", "UNCON.WRAITH.CORP")]:
        name = "single-session" if len(hosts) == 1 else "both-sessions"
        edits = [
            e
            for e in graph.edges(kind="HasSession")
            if e["source"] in {labels[h] for h in hosts} and e["target"] == bm
        ]
        if len(edits) != len(hosts):
            raise ValueError("Expected one observed BM session per selected host")
        live.native._initialize(snapshot, dataset["request"], dataset["scenario"])
        before = [live.native._evaluate(p) for p in pairs]
        canonical = graph.to_canonical()
        canonical["edges"] = [
            e for e in canonical["edges"] if e["id"] not in {x["id"] for x in edits}
        ]
        live.native._graph = EngineGraph.from_canonical(
            canonical,
            snapshot_facts=EffectiveSnapshotFacts(
                graph.snapshot_facts, (), name, graph_digest(canonical)
            ),
        )
        after = [live.native._evaluate(p) for p in pairs]
        if any(r["status"] == "error" for r in before + after):
            raise RuntimeError("Native query failed")
        if not all(r["reached"] and r["C"] == 3 for r in before):
            raise RuntimeError("Baseline TRUSTER result changed")
        bh_before = ce_rows()
        match = "MATCH (s {objectid:$source})-[r:HasSession]->(t {objectid:$target})"
        journal = []
        for edge in edits:
            params = {"source": edge["source"], "target": bm}
            saved = live.parameter_query(match + " RETURN properties(r) AS props", params)
            if len(saved) != 1:
                raise ValueError("Expected exactly one existing CE session to journal")
            journal.append({**params, "props": saved[0]["props"]})
        journal_path = folder / (name + "-restore-journal.json")
        live._atomic_json(journal_path, {"before_digest": original, "edges": journal})

        def verify_restored(journal_path):
            if fingerprint() != original:
                raise RuntimeError(f"Restoration incomplete; recovery journal: {journal_path}")

        with ExitStack() as rollback:
            rollback.callback(verify_restored, journal_path)
            for row in journal:
                rollback.callback(
                    live.parameter_query,
                    "MATCH (s {objectid:$source}),(t {objectid:$target}) "
                    "MERGE (s)-[r:HasSession]->(t) SET r=$props",
                    row,
                )
            for row in journal:
                live.parameter_query(match + " DELETE r", row)
            bh_after = ce_rows()
        if len(hosts) == 1:
            if not all(r["reached"] and r["C"] == 3 for r in after):
                raise RuntimeError("Expected native single-session bypass at C=3")
            if not all(
                r["http_status"] == 200
                and any(e["target_label"] == "UNCON.WRAITH.CORP" for e in r["path"])
                for r in bh_after
            ):
                raise RuntimeError("Expected CE single-session bypass through UNCON")
        else:
            if not all(
                not r["reached"] and r["no_path_proven"] and not r["truncated"] for r in after
            ):
                raise RuntimeError("Native two-session no-path proof changed")
            if not all(r["http_status"] == 404 and r["empty_confirmed"] for r in bh_after):
                raise RuntimeError("Expected CE queries confirmed empty after both removals")
        result = {
            "case": name,
            "pairs": pairs,
            "edits": edits,
            "neo_before": before,
            "neo_after": after,
            "bloodhound_before": bh_before,
            "bloodhound_after": bh_after,
            "restore_verified": True,
            "restored_relationship_data_digest": original,
        }
        live._atomic_json(folder / (name + ".json"), result)
        results.append(result)
        print(name, [(r["status"], r["C"], r["expansions"]) for r in after], flush=True)
    live._atomic_json(folder / "results.json", results)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--pack", type=Path, required=True)
    parser.add_argument("--project-name", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    run(parser.parse_args())


if __name__ == "__main__":
    main()
