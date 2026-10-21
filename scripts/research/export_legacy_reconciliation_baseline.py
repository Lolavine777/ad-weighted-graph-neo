"""Read retained Legacy databases and prepare a local #82 reconciliation handoff.

Full identity and edge outputs belong in the ignored output directory. This
tool never imports data or writes to Neo4j. It refuses a different snapshot,
runtime, database identity, population, or incomplete identity mapping.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import subprocess
import sys
import urllib.request
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if __package__ in {None, ""}:
    sys.path.insert(0, str(ROOT))

from scripts.reconcile_graph_baseline import COMPARISON_SCOPE  # noqa: E402
from src.data.manifest import load_manifest, verify_manifest  # noqa: E402
from src.parser import IdentityNormalizer, ManifestRawDataLoader  # noqa: E402
from src.parser.adapters import adapt_bloodhound_v3_records  # noqa: E402
from src.parser.cli import load_time_policy  # noqa: E402

SNAPSHOT = "sha256:e0601d763eeea285d268ec9e468d321c50c9d7faba53c8e7442a2fcc4159c812"
IMAGE = "sha256:1f08dd79d877776e2501ba77d8b4c5354e8953d603fcae31df6b7b2c61685bc0"
RUNS = {
    "bh-legacy-403-neo4j": (
        "c6d35fa9bfbd6b9b67bc4090c943a4090f6c377ec1239307085e44faf2eee865",
        17474,
    ),
    "bh-legacy-403-neo4j-rerun": (
        "644315813dbf44ba39b8299dee14d0ae8fc6a1d26a4d1d8176a90f81b8bd4ea4",
        27474,
    ),
}
BOUNDARY = {
    "SEAMLESS.INTERNAL-S-1-5-4": "S-1-5-4",
    "SEAMLESS.INTERNAL-S-1-5-17": "S-1-5-17",
}
EXPECTED_KINDS = {
    "AdminTo": 5,
    "AllExtendedRights": 2499,
    "CanPSRemote": 2,
    "CanRDP": 3,
    "Contains": 2816,
    "ExecuteDCOM": 1,
    "GenericAll": 37034,
    "GenericWrite": 3166,
    "GetChanges": 3,
    "GetChangesAll": 2,
    "GpLink": 2,
    "MemberOf": 15917,
    "Owns": 3362,
    "WriteDacl": 3392,
    "WriteOwner": 3392,
}


def require(ok: bool, message: str) -> None:
    if not ok:
        raise ValueError(message)


def encoded(value: object) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode("utf-8")


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def set_digest(values: set[str]) -> str:
    payload = json.dumps(sorted(values), ensure_ascii=False, separators=(",", ":"))
    return digest(payload.encode("utf-8"))


def write_json(path: Path, value: object) -> str:
    data = encoded(value)
    path.write_bytes(data)
    return digest(data)


def local_ref(path: Path) -> str:
    return str(path.resolve().relative_to(ROOT)).replace("\\", "/")


def relationship_rows_for_export(
    relationships: list[dict], mapping: dict[str, str], project_nodes: dict[str, dict]
) -> list[dict]:
    counts = Counter((row["source"], row["kind"], row["target"]) for row in relationships)
    return [
        {
            "source": source,
            "kind": kind,
            "target": target,
            "source_identity": mapping[source],
            "target_identity": mapping[target],
            "source_boundary": project_nodes[mapping[source]]["is_boundary"],
            "target_boundary": project_nodes[mapping[target]]["is_boundary"],
            "stored_multiplicity": count,
        }
        for (source, kind, target), count in sorted(counts.items())
    ]


def inspect_run(name: str) -> tuple[str, int, str]:
    result = subprocess.run(["docker", "inspect", name], capture_output=True, text=True, check=True)
    info = json.loads(result.stdout)[0]
    expected_id, port = RUNS[name]
    require(info["Id"] == expected_id, f"{name}: container ID differs from #139")
    require(info["Image"] == IMAGE, f"{name}: image differs from #130/#139")
    require(info["State"]["Running"], f"{name}: retained database is stopped")
    bindings = info["HostConfig"]["PortBindings"]["7474/tcp"]
    require(len(bindings) == 1 and int(bindings[0]["HostPort"]) == port, "port binding changed")
    password = os.environ.get("NEO4J_PASSWORD")
    if password is None:
        auth = next((v for v in info["Config"]["Env"] if v.startswith("NEO4J_AUTH=")), None)
        require(
            auth is not None and auth.startswith("NEO4J_AUTH=neo4j/"),
            "Neo4j credential unavailable",
        )
        password = auth.split("/", 1)[1]
    require(bool(password), "empty Neo4j password")
    return password, port, info["Id"]


def query(port: int, password: str, statement: str, parameters: dict | None = None) -> list[dict]:
    payload = json.dumps(
        {"statements": [{"statement": statement, "parameters": parameters or {}}]}
    ).encode()
    token = base64.b64encode(f"neo4j:{password}".encode()).decode("ascii")
    request = urllib.request.Request(
        f"http://127.0.0.1:{port}/db/neo4j/tx/commit",
        data=payload,
        headers={"Authorization": f"Basic {token}", "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        result = json.load(response)
    require(not result["errors"], f"Neo4j rejected read query: {result['errors']}")
    table = result["results"][0]
    return [dict(zip(table["columns"], item["row"], strict=True)) for item in table["data"]]


def read_query_package(path: Path) -> dict[str, str]:
    package = json.loads(path.read_text(encoding="utf-8"))
    require(
        package["schema_version"] == 1 and package["read_only"] is True, "query package version"
    )
    queries = package["queries"]
    for name, statement in queries.items():
        require(
            isinstance(statement, str)
            and statement.startswith(("MATCH ", "CALL dbms.components()")),
            f"{name}: not read-only",
        )
        upper = statement.upper()
        require(
            not any(
                token in upper
                for token in (
                    " CREATE ",
                    " DELETE ",
                    " DETACH ",
                    " SET ",
                    " MERGE ",
                    " REMOVE ",
                    " LOAD CSV",
                    "CALL DBMS.SECURITY",
                )
            ),
            f"{name}: write token",
        )
    return queries


def raw_mapping(
    manifest_path: Path, raw_root: Path, time_policy: Path
) -> tuple[dict[str, str], dict[str, str]]:
    loader = ManifestRawDataLoader(manifest_path, time_policy=load_time_policy(time_policy))
    original = tuple(loader.load(raw_root))
    adapted = adapt_bloodhound_v3_records(original)
    normalizer = IdentityNormalizer()
    mapping: dict[str, str] = {}
    kinds: dict[str, str] = {}
    for before, after in zip(original, adapted, strict=True):
        node = normalizer.normalize(after)
        source = before.data["ObjectIdentifier"]
        if source in mapping:
            require(
                mapping[source] == node.id and kinds[source] == node.kind, "ambiguous raw identity"
            )
        mapping[source] = node.id
        kinds[source] = node.kind
    require(len(mapping) == 3368, "collected raw identity count differs from #139")
    for source, target in BOUNDARY.items():
        require(source not in mapping, "boundary principal has first-class raw object")
        mapping[source] = target
        kinds[source] = "Group"
    require(len(set(mapping.values())) == len(mapping), "identity mapping is not one-to-one")
    group_ids = {target for source, target in mapping.items() if kinds[source] == "Group"}
    require(
        set_digest(group_ids) == "41d8c593b33785b8024f1d5960fa37284d99d17b22246d0b3ad75e8bbf3cd606",
        "#139 Group mapping digest mismatch",
    )
    return mapping, kinds


def export(args: argparse.Namespace) -> dict:
    manifest = load_manifest(args.manifest)
    require(
        manifest["dataset_id"] == "seamless-v1" and manifest["snapshot_id"] == SNAPSHOT,
        "wrong manifest",
    )
    require(
        len(manifest["files"]) == 6 and not verify_manifest(args.raw_root, manifest),
        "raw manifest verification failed",
    )
    project = json.loads(args.project.read_text(encoding="utf-8"))
    require(project["metadata"]["snapshot_id"] == SNAPSHOT, "project snapshot mismatch")
    require(project["metadata"]["contract_version"] == "1.3.0", "project contract mismatch")
    require(
        len(project["nodes"]) == 3370 and len(project["edges"]) == 53774,
        "project population differs",
    )
    mapping, raw_kinds = raw_mapping(args.manifest, args.raw_root, args.time_policy)
    project_nodes = {node["id"]: node for node in project["nodes"]}
    require(set(mapping.values()) == set(project_nodes), "raw/project identity set mismatch")
    queries = read_query_package(args.queries)
    observations = []
    for name in RUNS:
        password, port, run_id = inspect_run(name)
        runtime = query(port, password, queries["runtime"])
        require(
            any("4.1.13" in row["versions"] for row in runtime), f"{name}: Neo4j version mismatch"
        )
        nodes = query(port, password, queries["all_nodes"])
        relationships = query(port, password, queries["all_relationships"])
        labels = query(port, password, queries["nodes_by_labels"])
        kind_rows = query(port, password, queries["relationships_by_kind"])
        require(len(nodes) == 3370 and len(relationships) == 71596, f"{name}: population mismatch")
        require(
            {row["kind"]: row["stored_count"] for row in kind_rows} == EXPECTED_KINDS,
            f"{name}: kind counts mismatch",
        )
        require(sum(row["count"] for row in labels) == 3370, "label count mismatch")
        require(len({row["objectid"] for row in nodes}) == len(nodes), "duplicate Legacy objectid")
        require(
            {row["objectid"] for row in nodes} == set(mapping), "Legacy/raw mapping source mismatch"
        )
        require(
            all(row["source"] in mapping and row["target"] in mapping for row in relationships),
            "dangling Legacy endpoint",
        )
        for principal in BOUNDARY:
            outgoing = [row for row in relationships if row["source"] == principal]
            incoming = [row for row in relationships if row["target"] == principal]
            require(
                len(outgoing) == 1 and outgoing[0]["kind"] == "MemberOf" and not incoming,
                "#139 boundary membership observation changed",
            )
        observations.append((name, run_id, nodes, relationships, labels, kind_rows))
    first = observations[0]
    require(encoded(first[2]) == encoded(observations[1][2]), "clean-run node sets differ")
    require(
        encoded(first[3]) == encoded(observations[1][3]),
        "clean-run relationship observations differ",
    )
    nodes = first[2]
    relationships = first[3]
    node_rows = []
    for row in nodes:
        source = row["objectid"]
        target = mapping[source]
        project_node = project_nodes[target]
        require(raw_kinds[source] == project_node["kind"], "raw/project kind mismatch")
        require(set(row["labels"]) == {"Base", raw_kinds[source]}, "Legacy label mismatch")
        node_rows.append(
            {
                "objectid": source,
                "comparison_identity": target,
                "labels": row["labels"],
                "kind": raw_kinds[source],
                "domain": project_node["domain"],
                "is_boundary": project_node["is_boundary"],
                "mapping_rule": "issue-139-boundary"
                if source in BOUNDARY
                else "raw-adapter-normalizer",
            }
        )
    triple_counts = Counter((r["source"], r["kind"], r["target"]) for r in relationships)
    relationship_rows = relationship_rows_for_export(relationships, mapping, project_nodes)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    node_path = args.output_dir / "legacy-nodes.json"
    rel_path = args.output_dir / "legacy-relationships.json"
    mapping_path = args.output_dir / "identity-mapping.json"
    project_path = args.output_dir / "project-comparison.json"
    legacy_path = args.output_dir / "legacy-comparison.json"
    node_digest = write_json(node_path, node_rows)
    rel_digest = write_json(rel_path, relationship_rows)
    mapping_digest = write_json(mapping_path, mapping)
    project["metadata"].update(
        {
            "synthetic": False,
            "export_complete": True,
            "source_evidence": str(args.manifest),
            "comparison_scope": COMPARISON_SCOPE,
        }
    )
    project_digest = write_json(project_path, project)
    baseline = {
        "metadata": {
            "snapshot_id": SNAPSHOT,
            "synthetic": False,
            "export_complete": False,
            "source_evidence": str(args.queries),
            "comparison_scope": COMPARISON_SCOPE,
            "reason": (
                "Full stored graph exported; full m1 direct/effective semantic "
                "equivalence awaits #47 review."
            ),
        },
        "nodes": [
            {
                "objectid": r["objectid"],
                "labels": r["labels"],
                "domain": r["domain"],
                "is_boundary": r["is_boundary"],
            }
            for r in node_rows
        ],
        "relationships": [
            {"source": r["source"], "kind": r["kind"], "target": r["target"]} for r in relationships
        ],
    }
    legacy_digest = write_json(legacy_path, baseline)
    by_kind_unique = Counter(kind for _, kind, _ in triple_counts)
    scope_mapping = {
        kind: {
            "canonical_kind": kind,
            "status": "unknown",
            "reason": (
                "Stored kind exported; direct/derived and policy equivalence require #47 review"
            ),
        }
        for kind in COMPARISON_SCOPE["relationship_kinds"]
    }
    scope_mapping.update(
        {
            kind: {
                "canonical_kind": None,
                "status": "out_of_scope",
                "reason": "Not one of eight M1 structural kinds",
            }
            for kind in EXPECTED_KINDS
            if kind not in scope_mapping
        }
    )
    scope_mapping["MemberOf"]["reason"] = (
        "Full Legacy direct/effective/derived partition not established; "
        "#139 proves only two boundary direct pairs"
    )
    scope_mapping["AdminTo"]["reason"] = (
        "Project may derive nested administration; Legacy materialization rule requires review"
    )
    scope_mapping["ForceChangePassword"]["reason"] = (
        "No stored observations; AllExtendedRights is not assumed equivalent"
    )
    scope_mapping["Contains"]["reason"] = "Outside structural Graph Contract 1.3.0"
    summary = {
        "schema_version": 1,
        "dataset_id": "seamless-v1",
        "snapshot_id": SNAPSHOT,
        "manifest_digest": digest(args.manifest.read_bytes()),
        "source_revisions": {
            "pr130": "32a9b49573b09431ec13f6a6e823923ed366e164",
            "pr139": "453ec7ff2c4846af94726a5cd61783e864aed8fe",
            "project": project["metadata"]["code_version"],
        },
        "legacy": {
            "bloodhound_version": "4.0.3",
            "neo4j_version": "4.1.13",
            "runtime_digest": IMAGE,
            "run_identifiers": [row[1] for row in observations],
            "node_count": len(nodes),
            "stored_relationship_count": len(relationships),
        },
        "project": {
            "graph_contract_version": "1.3.0",
            "revision": project["metadata"]["code_version"],
            "node_count": len(project["nodes"]),
            "edge_count": len(project["edges"]),
            "canonical_graph_digest": digest(args.project.read_bytes()),
            "comparison_export_digest": project_digest,
        },
        "identity_export": {
            "local_reference": local_ref(node_path),
            "digest": node_digest,
            "record_count": len(node_rows),
            "population": {
                "collected": sum(not r["is_boundary"] for r in node_rows),
                "boundary": sum(r["is_boundary"] for r in node_rows),
            },
            "mapping_reference": local_ref(mapping_path),
            "mapping_digest": mapping_digest,
            "transformed_count": sum(source != target for source, target in mapping.items()),
        },
        "relationship_export": {
            "local_reference": local_ref(rel_path),
            "digest": rel_digest,
            "stored_count": len(relationships),
            "unique_triple_count": len(triple_counts),
            "stored_by_kind": EXPECTED_KINDS,
            "unique_by_kind": dict(sorted(by_kind_unique.items())),
        },
        "comparator_inputs": {
            "candidate": local_ref(project_path),
            "candidate_digest": project_digest,
            "baseline": local_ref(legacy_path),
            "baseline_digest": legacy_digest,
            "mapping": local_ref(mapping_path),
        },
        "comparison_scope": {
            "scope_id": "m1-structural-v1",
            "status": "pending_semantics_review",
            "kind_mapping": scope_mapping,
            "comparable_kinds": [],
            "excluded_kinds": sorted(
                kind
                for kind in EXPECTED_KINDS
                if kind not in COMPARISON_SCOPE["relationship_kinds"]
            ),
        },
        "provenance": {
            "query_package": local_ref(args.queries),
            "query_package_version": 1,
            "query_package_digest": digest(args.queries.read_bytes()),
            "exporter": "scripts/research/export_legacy_reconciliation_baseline.py",
            "exporter_digest": digest(Path(__file__).read_bytes()),
            "raw_project": "canonical edge provenance and raw locator available",
            "legacy_stored_graph": None,
        },
        "limitations": {
            "importer_write_error_count": None,
            "rejected_record_count": None,
            "import_duration_seconds": None,
            "legacy_raw_provenance": None,
            "full_m1_semantic_equivalence": "unknown",
            "comparator_verdict": "NOT_MEASURABLE",
            "comparator_use": "pre_handoff_validation_only",
        },
    }
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-root", required=True, type=Path)
    parser.add_argument(
        "--manifest", default=ROOT / "data/samples/manifests/seamless-raw-v1.json", type=Path
    )
    parser.add_argument("--project", required=True, type=Path)
    parser.add_argument("--time-policy", required=True, type=Path)
    parser.add_argument(
        "--queries",
        default=ROOT / "reports/research/issue-82-legacy-reconciliation-queries.json",
        type=Path,
    )
    parser.add_argument("--output-dir", default=ROOT / ".cache/issue82-handoff", type=Path)
    parser.add_argument(
        "--manifest-output",
        default=ROOT / "reports/baselines/seamless-legacy-403-reconciliation-handoff.json",
        type=Path,
    )
    args = parser.parse_args()
    try:
        summary = export(args)
        write_json(args.manifest_output, summary)
    except (ValueError, KeyError, OSError, subprocess.CalledProcessError) as exc:
        print(f"Export refused: {exc}", file=sys.stderr)
        return 2
    print(
        json.dumps(
            {
                "status": "exported",
                "nodes": summary["legacy"]["node_count"],
                "stored_relationships": summary["legacy"]["stored_relationship_count"],
                "unique_triples": summary["relationship_export"]["unique_triple_count"],
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
