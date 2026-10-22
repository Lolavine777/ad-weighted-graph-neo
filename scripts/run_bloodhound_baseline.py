"""Automated BloodHound CE baseline ingestion and verification runner.

Manages clean environment lifecycle, snapshot upload, and Neo4j ground-truth
baseline extraction for Dataset A and Dataset B.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if __package__ in {None, ""}:
    sys.path.insert(0, str(ROOT))

from src.data.manifest import (  # noqa: E402
    ManifestError,
    _hash_file,
    _signature,
    load_manifest,
)

COMPOSE_FILE = ROOT / "deploy" / "bloodhound" / "compose.yml"

BLOODHOUND_PORT = os.getenv("BLOODHOUND_PORT", "8080")
BLOODHOUND_URL = os.getenv("BLOODHOUND_URL", f"http://127.0.0.1:{BLOODHOUND_PORT}")

NEO4J_WEB_PORT = os.getenv("NEO4J_WEB_PORT", "7474")
NEO4J_URL = os.getenv("NEO4J_URL", f"http://127.0.0.1:{NEO4J_WEB_PORT}/db/neo4j/tx/commit")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_SECRET = os.getenv("NEO4J_SECRET", "bloodhoundcommunityedition")
NEO4J_AUTH = base64.b64encode(f"{NEO4J_USER}:{NEO4J_SECRET}".encode()).decode("ascii")

CORE_M1_EDGES = [
    "MemberOf",
    "AdminTo",
    "GenericAll",
    "WriteDacl",
    "ForceChangePassword",
    "CanPSRemote",
    "CanRDP",
    "HasSession",
]

CORE_M1_LABELS = [
    "User",
    "Computer",
    "Group",
    "Domain",
    "OU",
    "GPO",
]

SNAPSHOTS = {
    "seamless": {
        "dataset_id": "seamless-v1",
        "snapshot_id": "sha256:e0601d763eeea285d268ec9e468d321c50c9d7faba53c8e7442a2fcc4159c812",
        "archive_name": "20210920185958_BloodHound.zip",
        "archive_sha256": "b8e9f003dd51a98838be86d8f98b0844a19a7876aad0a81b525f19e110105813",
        "collector": "SharpHound (legacy v3)",
        "raw_root": ROOT / "data/raw/SEAMLESS",
        "file_pattern": "20210920185958_*.json",
        "expected_files": 6,
        "manifest_path": ROOT / "data/samples/manifests/seamless-raw-v1.json",
    },
    "wraith": {
        "dataset_id": "ad-sampledata-v1:wraith:20240305111414",
        "snapshot_id": "sha256:10d29ec2b278ecf0b12e51dfaed95333f13c5d14933d3720500f38d6914b2227",
        "archive_name": "a8bfbcf9-4226-40ed-a0c4-a2cc05dbc708.zip (WRAITH.CORP)",
        "archive_sha256": "2adb4bd1a7286869c00b0e2698dc5275b9520178fd8a07ead4cdcdb5159161ba",
        "collector": "SharpHound v2.3.3 (C#)",
        "raw_root": ROOT / "data/raw/ad_sampledata",
        "file_pattern": "20240305111414_*.json",
        "expected_files": 12,
        "manifest_path": ROOT / "data/samples/manifests/ad-sampledata-v1.json",
        "manifest_prefix": "20240305111414_",
    },
    "a-sharphound": {
        "dataset_id": "a-sharphound",
        "snapshot_id": "sha256:ca5f09dd0272f607354086c53d255967eec51b7dab2d5bf9d3bbdd902f3d6f63",
        "archive_name": "NORTH_20240410083414_BloodHound-2.3.3.zip",
        "archive_sha256": "9f4482553b3d6b20df16e2fd615d543ac267f0e9a062ec4578d517548b4c666c",
        "collector": "SharpHound v2.3.3 (C#)",
        "raw_root": ROOT / "data" / "raw" / "dataset_a",
        "file_pattern": "NORTH_20240410083414_*.json",
        "expected_files": 12,
        "staging_dir": ROOT / "data" / "processed" / "snapshot-inputs" / "a-sharphound",
    },
    "a-python": {
        "dataset_id": "a-python",
        "snapshot_id": "sha256:b25cb32639ed10c1b0ddf488bf02b6547740a0a1eed00259571c4dd776516cdc",
        "archive_name": "ce_branch_bloodhoundpy_north_20240411011008_bloodhound.zip",
        "archive_sha256": "806fa21cc61b73c74a52126b0441ae633f6c6b6784731f5f16060b10c08e0e39",
        "collector": "BloodHound-Python CE",
        "raw_root": ROOT / "data" / "raw" / "dataset_a",
        "file_pattern": "ce_branch_bloodhoundpy_20240411011008_*.json",
        "expected_files": 7,
        "staging_dir": ROOT / "data" / "processed" / "snapshot-inputs" / "a-python",
    },
    "b-run-1": {
        "dataset_id": "b-run-1",
        "snapshot_id": "sha256:39d3a48729a01550467125c3115dedbb355205c02f46cd83e2f9dfb780e02602",
        "archive_name": "a8bfbcf9-4226-40ed-a0c4-a2cc05dbc708.zip (PHANTOM.CORP)",
        "archive_sha256": "2adb4bd1a7286869c00b0e2698dc5275b9520178fd8a07ead4cdcdb5159161ba",
        "collector": "SharpHound v2.3.3 (C#)",
        "raw_root": ROOT / "data" / "raw" / "dataset_b",
        "file_pattern": "20240305110018_*.json",
        "expected_files": 12,
        "staging_dir": ROOT / "data" / "processed" / "snapshot-inputs" / "b-run-1",
    },
    "b-run-2": {
        "dataset_id": "b-run-2",
        "snapshot_id": "sha256:dfe659eef9715ffc37b51144d65e71552b775cbf263907b6c88f9dfb4d72196d",
        "archive_name": "a8bfbcf9-4226-40ed-a0c4-a2cc05dbc708.zip (GHOST.CORP)",
        "archive_sha256": "2adb4bd1a7286869c00b0e2698dc5275b9520178fd8a07ead4cdcdb5159161ba",
        "collector": "SharpHound v2.3.3 (C#)",
        "raw_root": ROOT / "data" / "raw" / "dataset_b",
        "file_pattern": "20240305110427_*.json",
        "expected_files": 7,
        "staging_dir": ROOT / "data" / "processed" / "snapshot-inputs" / "b-run-2",
    },
    "b-run-3": {
        "dataset_id": "b-run-3",
        "snapshot_id": "sha256:e4198d8c06426aa2ea214ac261a43935b14e98fe516d57c48a8da5be18031c12",
        "archive_name": "a8bfbcf9-4226-40ed-a0c4-a2cc05dbc708.zip (WRAITH.CORP)",
        "archive_sha256": "2adb4bd1a7286869c00b0e2698dc5275b9520178fd8a07ead4cdcdb5159161ba",
        "collector": "SharpHound v2.3.3 (C#)",
        "raw_root": ROOT / "data" / "raw" / "dataset_b",
        "file_pattern": "20240305111414_*.json",
        "expected_files": 12,
        "staging_dir": ROOT / "data" / "processed" / "snapshot-inputs" / "b-run-3",
    },
    "dataset_b": {
        "dataset_id": "dataset_b",
        "snapshot_id": "sha256:f62a39280b2cfcaaa4d6a738365870b82765cd37458a3ac17ce8f2702514e3e1",
        "archive_name": "a8bfbcf9-4226-40ed-a0c4-a2cc05dbc708.zip (All 3 Domains)",
        "archive_sha256": "2adb4bd1a7286869c00b0e2698dc5275b9520178fd8a07ead4cdcdb5159161ba",
        "collector": "SharpHound v2.3.3 (C#)",
        "raw_root": ROOT / "data" / "raw" / "dataset_b",
        "file_pattern": "*.json",
        "expected_files": 31,
        "staging_dir": ROOT / "data" / "raw" / "dataset_b",
    },
}


def resolve_snapshot_files(snapshot_key: str) -> list[Path]:
    """Resolve JSON files for a snapshot from staging dir or directly from raw root."""
    cfg = SNAPSHOTS[snapshot_key]
    staging_dir = cfg.get("staging_dir")
    if staging_dir and staging_dir.exists():
        files = sorted(staging_dir.glob("*.json"))
        if len(files) == cfg["expected_files"]:
            return files

    raw_root = cfg["raw_root"]
    if raw_root.exists():
        files = sorted(raw_root.glob(cfg["file_pattern"]))
        if len(files) == cfg["expected_files"]:
            return files

    raise FileNotFoundError(
        f"Could not locate {cfg['expected_files']} files for snapshot {snapshot_key} "
        f"in {staging_dir} or {raw_root} matching pattern '{cfg['file_pattern']}'"
    )


def verify_snapshot_integrity(snapshot_key: str, files: list[Path]) -> str:
    """Verify local files against deterministic snapshot manifest and return verified snapshot_id.

    Fails fast if files are missing, sizes differ, checksums do not match,
    or the computed snapshot identity deviates from the registered snapshot.
    """
    cfg = SNAPSHOTS[snapshot_key]
    manifest_path = cfg.get(
        "manifest_path", ROOT / "data" / "processed" / "manifests" / f"{snapshot_key}.json"
    )
    if "manifest_path" in cfg and not manifest_path.exists():
        raise ManifestError(f"Required snapshot manifest is missing: {manifest_path}")

    if manifest_path.exists():
        manifest = load_manifest(manifest_path)
        expected_files = {
            entry["relative_path"]: entry
            for entry in manifest["files"]
            if entry["relative_path"].startswith(cfg.get("manifest_prefix", ""))
        }
        if len(expected_files) != cfg["expected_files"]:
            raise ManifestError(f"Manifest selection count mismatch for '{snapshot_key}'")
        if len(files) != len(expected_files):
            raise ManifestError(
                f"Snapshot '{snapshot_key}' file count mismatch: "
                f"got {len(files)}, expected {len(expected_files)}"
            )
        for f in files:
            if f.name not in expected_files:
                raise ManifestError(f"File '{f.name}' not found in manifest for '{snapshot_key}'")
            entry = expected_files[f.name]
            sig = _signature(f.lstat())
            size, digest = _hash_file(f, sig)
            if size != entry["size_bytes"]:
                raise ManifestError(
                    f"File '{f.name}' size mismatch: {size} != expected {entry['size_bytes']}"
                )
            if digest != entry["sha256"]:
                raise ManifestError(
                    f"File '{f.name}' SHA-256 mismatch: {digest} != expected {entry['sha256']}"
                )
        verified_id = manifest["snapshot_id"]
        if verified_id != cfg["snapshot_id"]:
            msg = (
                f"Snapshot ID mismatch for '{snapshot_key}': "
                f"{verified_id} != expected {cfg['snapshot_id']}"
            )
            raise ManifestError(msg)
        print(
            f"Verified snapshot '{snapshot_key}' integrity against manifest "
            f"({len(files)} files, ID: {verified_id})"
        )
        return verified_id

    # Fallback if manifest JSON is not generated locally: verify expected count and stream hashes
    if len(files) != cfg["expected_files"]:
        msg = (
            f"Snapshot '{snapshot_key}' file count mismatch: "
            f"got {len(files)}, expected {cfg['expected_files']}"
        )
        raise ManifestError(msg)
    for f in files:
        sig = _signature(f.lstat())
        _hash_file(f, sig)
    print(f"Verified snapshot '{snapshot_key}' file presence ({len(files)} files)")
    return cfg["snapshot_id"]


def run_cmd(cmd: list[str], check: bool = True) -> str:
    res = subprocess.run(cmd, capture_output=True, text=True, check=check)
    return res.stdout


def reset_environment(
    compose_file: Path = COMPOSE_FILE,
    project_name: str = "bloodhound-baseline",
    *,
    reset_volumes: bool = False,
) -> None:
    compose = ["docker", "compose", "-f", str(compose_file), "-p", project_name]
    if reset_volumes:
        print(f"Resetting BloodHound CE stack and volumes for {project_name}...")
        run_cmd([*compose, "down", "-v"])
    run_cmd([*compose, "up", "-d"])


def get_admin_password(
    max_wait_seconds: int = 90,
    *,
    compose_file: Path = COMPOSE_FILE,
    project_name: str = "bloodhound-baseline",
) -> str:
    print("Waiting for BloodHound to emit initial admin password...")
    deadline = time.time() + max_wait_seconds
    while time.time() < deadline:
        logs = run_cmd(
            [
                "docker",
                "compose",
                "-f",
                str(compose_file),
                "-p",
                project_name,
                "logs",
                "bloodhound",
            ],
            check=False,
        )
        matches = re.findall(r"Initial Password Set To:\s+([^\s#]+)", logs)
        if matches:
            return matches[-1]
        time.sleep(2)
    raise RuntimeError("Timed out waiting for initial admin password.")


def login(secret: str, max_wait: int = 60) -> str:
    print("Logging into BloodHound API...")
    payload = json.dumps(
        {
            "login_method": "secret",
            "username": "admin",
            "secret": secret,
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        f"{BLOODHOUND_URL}/api/v2/login",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    deadline = time.time() + max_wait
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(req) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return data["data"]["session_token"]
        except Exception:
            time.sleep(2)
    raise RuntimeError("Timed out logging into BloodHound API.")


def wait_for_bloodhound_ready(token: str, max_wait_seconds: int = 60) -> None:
    print("Waiting for BloodHound file-upload API readiness...")
    deadline = time.time() + max_wait_seconds
    headers = {"Authorization": f"Bearer {token}"}
    req = urllib.request.Request(f"{BLOODHOUND_URL}/api/v2/file-upload", headers=headers)
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(req) as resp:
                if resp.status == 200:
                    return
        except Exception:
            time.sleep(2)
    raise RuntimeError("Timed out waiting for BloodHound API to become ready.")


def query_neo4j(cypher: str) -> list[dict]:
    payload = json.dumps({"statements": [{"statement": cypher}]}).encode("utf-8")
    req = urllib.request.Request(
        NEO4J_URL,
        data=payload,
        headers={
            "Authorization": f"Basic {NEO4J_AUTH}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        if data.get("errors"):
            raise RuntimeError(f"Neo4j Cypher error: {data['errors']}")
        results = data["results"][0]
        columns = results["columns"]
        return [dict(zip(columns, row["row"], strict=False)) for row in results["data"]]


def ingest_snapshot(name: str, config: dict, token: str) -> dict:
    converted = None
    if config.get("converted_dir") is not None:
        from scripts.convert_seamless_ce import verify_install

        if name != "seamless":
            raise ValueError("converted input is only supported for seamless")
        converted = verify_install(SNAPSHOTS[name]["raw_root"], config["converted_dir"])
        files = converted["files"]
        verified_snapshot_id = converted["snapshot_id"]
    else:
        files = resolve_snapshot_files(name)
        verified_snapshot_id = verify_snapshot_integrity(name, files)

    print(f"\n--- Ingesting {name} ({len(files)} files) ---")
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    # 1. Start upload job
    req = urllib.request.Request(
        f"{BLOODHOUND_URL}/api/v2/file-upload/start",
        data=b"{}",
        headers=headers,
        method="POST",
    )
    with urllib.request.urlopen(req) as resp:
        job_data = json.loads(resp.read().decode("utf-8"))["data"]
        job_id = job_data["id"]
    print(f"Started upload job ID: {job_id}")

    # 2. Upload files
    file_statuses = []
    for f in files:
        upload_req = urllib.request.Request(
            f"{BLOODHOUND_URL}/api/v2/file-upload/{job_id}",
            data=f.read_bytes(),
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(upload_req) as upload_resp:
                status_code = upload_resp.status
                file_statuses.append({"file": f.name, "status": "success", "code": status_code})
                print(f"  Uploaded {f.name}: HTTP {status_code}")
        except urllib.error.HTTPError as e:
            file_statuses.append(
                {
                    "file": f.name,
                    "status": "failed",
                    "code": e.code,
                    "error": str(e),
                    "response_body": e.read(65536).decode("utf-8", errors="replace"),
                }
            )
            print(f"  FAILED {f.name}: HTTP {e.code}")

    # 3. End upload job
    end_req = urllib.request.Request(
        f"{BLOODHOUND_URL}/api/v2/file-upload/{job_id}/end",
        data=b"{}",
        headers=headers,
        method="POST",
    )
    with urllib.request.urlopen(end_req) as resp:
        pass

    # 4. Poll until job completed
    print("Waiting for BloodHound ingestion worker to complete...")
    for _ in range(120):
        time.sleep(3)
        status_req = urllib.request.Request(
            f"{BLOODHOUND_URL}/api/v2/file-upload", headers={"Authorization": f"Bearer {token}"}
        )
        with urllib.request.urlopen(status_req) as resp:
            jobs = json.loads(resp.read().decode("utf-8"))["data"]
            current = next((j for j in jobs if j["id"] == job_id), None)
            # BloodHound cmd/api/src/model/jobs.go: canceled, timed out, failed, partial.
            if current and current["status"] in {-1, 3, 4, 5, 8}:
                raise RuntimeError(
                    f"Ingest job failed or partial: {current}; uploads: {file_statuses}"
                )
            if current and current["status"] == 2:  # Complete
                if (
                    current.get("failed_files", 0)
                    or current.get("partial_failed_files", 0)
                    or any(f["status"] == "failed" for f in file_statuses)
                ):
                    raise RuntimeError(
                        f"Ingest job failed files: {current}; uploads: {file_statuses}"
                    )
                print(
                    f"Ingest complete! files: {current['total_files']}, "
                    f"failed: {current['failed_files']}"
                )
                break
    else:
        raise RuntimeError(
            f"Timed out waiting for ingest job {job_id}; last status: {current}; "
            f"uploads: {file_statuses}"
        )

    time.sleep(5)
    metrics = extract_baseline_metrics(name, config, file_statuses, verified_snapshot_id)
    if converted is not None:
        metrics.update(
            {key: converted[key] for key in ("source_snapshot_id", "converted_manifest_sha256")}
        )
    return metrics


def extract_baseline_metrics(
    name: str, config: dict, file_statuses: list[dict], verified_snapshot_id: str
) -> dict:
    print(f"Querying Neo4j baseline counts for {name}...")

    # Total nodes
    q_nodes = "MATCH (n) WHERE NOT 'MigrationData' IN labels(n) RETURN count(n) as total;"
    total_nodes = query_neo4j(q_nodes)[0]["total"]

    # Nodes by label
    q_labels = (
        "MATCH (n) WHERE NOT 'MigrationData' IN labels(n) "
        "UNWIND labels(n) as lbl RETURN lbl, count(n) as cnt ORDER BY cnt DESC;"
    )
    labels_res = query_neo4j(q_labels)
    label_counts = {r["lbl"]: r["cnt"] for r in labels_res}

    # Core M1 object counts
    m1_node_counts = {}
    for lbl in CORE_M1_LABELS:
        res = query_neo4j(f"MATCH (n:{lbl}) RETURN count(n) as cnt;")
        m1_node_counts[lbl] = res[0]["cnt"] if res else 0

    # Total relationships
    total_rels = query_neo4j("MATCH ()-[r]->() RETURN count(r) as total;")[0]["total"]

    # Relationships by type
    q_types = "MATCH ()-[r]->() RETURN type(r) as t, count(r) as cnt ORDER BY cnt DESC;"
    types_res = query_neo4j(q_types)
    rel_type_counts = {r["t"]: r["cnt"] for r in types_res}

    # Core M1 edges breakdown
    m1_edge_counts = {}
    for edge in CORE_M1_EDGES:
        cnt = rel_type_counts.get(edge, 0)
        m1_edge_counts[edge] = cnt

    # Check stub / dangling nodes
    dangling_res = query_neo4j("MATCH (n:Base) WHERE size(labels(n)) = 1 RETURN count(n) as cnt;")
    dangling_count = dangling_res[0]["cnt"] if dangling_res else 0

    # Sample edges for each M1 edge kind
    m1_samples = {}
    for edge in CORE_M1_EDGES:
        if m1_edge_counts[edge] > 0:
            sample_query = (
                f"MATCH (s)-[r:{edge}]->(t) "
                "RETURN labels(s) as s_lbl, s.name as s_name, s.objectid as s_id, "
                "labels(t) as t_lbl, t.name as t_name, t.objectid as t_id LIMIT 3;"
            )
            m1_samples[edge] = query_neo4j(sample_query)
        else:
            m1_samples[edge] = []

    return {
        "snapshot_key": name,
        "dataset_id": config["dataset_id"],
        "snapshot_id": verified_snapshot_id,
        "archive_name": config["archive_name"],
        "archive_sha256": config["archive_sha256"],
        "collector": config["collector"],
        "file_statuses": file_statuses,
        "total_nodes": total_nodes,
        "label_counts": label_counts,
        "m1_node_counts": m1_node_counts,
        "total_relationships": total_rels,
        "all_relationship_counts": rel_type_counts,
        "m1_edge_counts": m1_edge_counts,
        "dangling_base_nodes": dangling_count,
        "m1_samples": m1_samples,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run BloodHound CE baseline ingestion.")
    parser.add_argument("--snapshot", choices=list(SNAPSHOTS.keys()), help="Run specific snapshot")
    parser.add_argument(
        "--all", action="store_true", help="Run historical Dataset A/B snapshots sequentially"
    )
    parser.add_argument("--output", default=".cache/baseline_results.json", help="Path for JSON")
    parser.add_argument(
        "--project-name", default="bloodhound-baseline", help="Compose project name"
    )
    parser.add_argument("--compose-file", type=Path, default=COMPOSE_FILE, help="Compose file")
    parser.add_argument(
        "--seamless-ce-dir", type=Path, help="Verified SEAMLESS CE compatibility output"
    )
    parser.add_argument(
        "--reset-volumes",
        action="store_true",
        help="Delete selected project's volumes before import",
    )
    args = parser.parse_args()
    if args.seamless_ce_dir is not None and (args.snapshot != "seamless" or args.all):
        parser.error("--seamless-ce-dir requires --snapshot seamless")
    if args.all and not args.reset_volumes:
        parser.error("--all requires --reset-volumes to isolate each snapshot")

    targets = (
        [key for key in SNAPSHOTS if key not in {"seamless", "wraith"}]
        if args.all
        else [args.snapshot or "a-sharphound"]
    )
    all_results = {}
    failed = False

    for target in targets:
        try:
            files = resolve_snapshot_files(target)
            verify_snapshot_integrity(target, files)
            config = dict(SNAPSHOTS[target])
            if args.seamless_ce_dir is not None:
                from scripts.convert_seamless_ce import verify_install

                verify_install(config["raw_root"], args.seamless_ce_dir)
                config["converted_dir"] = args.seamless_ce_dir
            reset_environment(
                args.compose_file, args.project_name, reset_volumes=args.reset_volumes
            )
            admin_pass = get_admin_password(
                compose_file=args.compose_file, project_name=args.project_name
            )
            token = login(admin_pass)
            wait_for_bloodhound_ready(token)
            if query_neo4j(
                "MATCH (n) WHERE NOT 'MigrationData' IN labels(n) RETURN count(n) as total;"
            )[0]["total"]:
                raise RuntimeError(
                    "Refusing baseline import into a nonempty graph; "
                    "use a new --project-name or explicitly --reset-volumes"
                )
            all_results[target] = ingest_snapshot(target, config, token)
        except (RuntimeError, OSError, ValueError, subprocess.SubprocessError) as exc:
            all_results[target] = {"status": "failed", "error": str(exc)}
            failed = True
            break

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(all_results, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nAll baseline results saved to {out_path.resolve()}")
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
