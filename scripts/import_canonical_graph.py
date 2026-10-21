"""Import a validated graph's structural node/edge projection into Compose Neo4j.

The target database must be empty. Canonical IDs and edge IDs remain properties;
provenance and derivation are preserved as JSON strings because Neo4j properties
cannot contain nested maps. Assessments remain in the canonical JSON and are
explicitly reported as excluded from this traversable projection. This does
not import a BloodHound CE graph.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import sys
import urllib.request
from collections import Counter
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.check_contract import validate_graph  # noqa: E402

CONTRACT = ROOT / "configs" / "contract.yml"
KINDS = {"User", "Group", "Computer", "Domain", "OU", "GPO"}
RELATIONSHIPS = {
    "MemberOf",
    "GenericAll",
    "WriteDacl",
    "ForceChangePassword",
    "HasSession",
    "AdminTo",
    "CanRDP",
    "CanPSRemote",
}


def query(statement: str, parameters: dict | None = None) -> list[dict]:
    password = os.environ.get("NEO4J_PASSWORD")
    if not password:
        raise RuntimeError("NEO4J_PASSWORD must be supplied from the local Compose environment")
    token = base64.b64encode(f"neo4j:{password}".encode()).decode("ascii")
    payload = json.dumps({"statements": [{"statement": statement, "parameters": parameters or {}}]})
    request = urllib.request.Request(
        os.environ.get("NEO4J_URL", "http://127.0.0.1:7474/db/neo4j/tx/commit"),
        data=payload.encode("utf-8"),
        headers={"Authorization": f"Basic {token}", "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        result = json.load(response)
    if result["errors"]:
        raise RuntimeError(f"Neo4j rejected canonical import: {result['errors']}")
    table = result["results"][0]
    return [dict(zip(table["columns"], row["row"], strict=True)) for row in table["data"]]


def chunks(items: list[dict], size: int = 500):
    for start in range(0, len(items), size):
        yield items[start : start + size]


def projection_manifest(graph: dict, digest: str) -> dict:
    """Describe exactly what Neo4j contains and what remains in graph JSON."""

    assessments = graph["assessments"]
    assessment_payload = json.dumps(assessments, sort_keys=True, separators=(",", ":"))
    return {
        "projection": "canonical_nodes_and_edges",
        "graph_sha256": digest,
        "contract_version": graph["metadata"]["contract_version"],
        "snapshot_id": graph["metadata"]["snapshot_id"],
        "assessments_in_graph": len(assessments),
        "assessments_in_neo4j": 0,
        "assessment_statuses": dict(sorted(Counter(a["status"] for a in assessments).items())),
        "assessments_sha256": hashlib.sha256(assessment_payload.encode("utf-8")).hexdigest(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("graph", type=Path)
    parser.add_argument(
        "--structural-projection",
        action="store_true",
        required=True,
        help="acknowledge that canonical assessments remain in JSON, outside Neo4j",
    )
    args = parser.parse_args()
    raw = args.graph.read_bytes()
    graph = json.loads(raw)
    contract = yaml.safe_load(CONTRACT.read_text(encoding="utf-8"))
    validate_graph(graph, contract)
    digest = hashlib.sha256(raw).hexdigest()
    if query("MATCH (n) RETURN count(n) AS count")[0]["count"]:
        raise RuntimeError("Neo4j target is not empty; select a clean project Compose volume")
    query("CREATE CONSTRAINT canonical_id IF NOT EXISTS FOR (n:Canonical) REQUIRE n.id IS UNIQUE")

    for kind in sorted(KINDS):
        selected = [node for node in graph["nodes"] if node["kind"] == kind]
        for batch in chunks(selected):
            rows = [
                dict(node, graph_digest=digest, snapshot_id=graph["metadata"]["snapshot_id"])
                for node in batch
            ]
            count = query(
                f"UNWIND $rows AS row CREATE (n:Canonical:{kind}) SET n = row "
                "RETURN count(n) AS count",
                {"rows": rows},
            )[0]["count"]
            if count != len(rows):
                raise RuntimeError(f"node batch import mismatch for {kind}")

    for kind in sorted(RELATIONSHIPS):
        selected = [edge for edge in graph["edges"] if edge["kind"] == kind]
        for batch in chunks(selected):
            rows = [
                {
                    "id": edge["id"],
                    "source": edge["source"],
                    "target": edge["target"],
                    "kind": kind,
                    "weight": edge["weight"],
                    "graph_digest": digest,
                    "snapshot_id": graph["metadata"]["snapshot_id"],
                    "provenance_json": json.dumps(edge["provenance"], sort_keys=True),
                    **(
                        {"derivation_json": json.dumps(edge["derivation"], sort_keys=True)}
                        if "derivation" in edge
                        else {}
                    ),
                }
                for edge in batch
            ]
            count = query(
                "UNWIND $rows AS row MATCH (source:Canonical {id: row.source}) "
                "MATCH (target:Canonical {id: row.target}) "
                f"CREATE (source)-[r:{kind}]->(target) SET r = row "
                "RETURN count(r) AS count",
                {"rows": rows},
            )[0]["count"]
            if count != len(rows):
                raise RuntimeError(f"relationship batch import mismatch for {kind}")

    observed_nodes = query("MATCH (n:Canonical) RETURN count(n) AS count")[0]["count"]
    observed_edges = query("MATCH (:Canonical)-[r]->(:Canonical) RETURN count(r) AS count")[0][
        "count"
    ]
    if (observed_nodes, observed_edges) != (len(graph["nodes"]), len(graph["edges"])):
        raise RuntimeError("Neo4j totals differ from validated canonical JSON")
    print(
        json.dumps(
            {
                **projection_manifest(graph, digest),
                "nodes": observed_nodes,
                "edges": observed_edges,
                "nodes_by_kind": dict(sorted(Counter(n["kind"] for n in graph["nodes"]).items())),
                "edges_by_kind": dict(sorted(Counter(e["kind"] for e in graph["edges"]).items())),
                "boundary_nodes": sum(n["is_boundary"] for n in graph["nodes"]),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
