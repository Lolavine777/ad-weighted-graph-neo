"""Compute exact BloodHound ingestion baseline counts for each raw snapshot.

Models BloodHound CE v9.7.0 ingestion semantics:
- Nodes deduplicated by ObjectIdentifier/SID with label assignment
- Edges deduplicated by (source_id, edge_type, target_id)
- Dangling references identified (targets not defined as first-class objects)
- 8 core M1 edge kinds and AD CS / structural edges analyzed
"""

import json
import sys
from collections import defaultdict
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

M1_KINDS = {
    "users": "User",
    "computers": "Computer",
    "groups": "Group",
    "domains": "Domain",
    "ous": "OU",
    "gpos": "GPO",
}

ALL_KINDS = {
    **M1_KINDS,
    "containers": "Container",
    "aiacas": "AIACA",
    "rootcas": "RootCA",
    "enterprisecas": "EnterpriseCA",
    "ntauthstores": "NTAuthStore",
    "certtemplates": "CertTemplate",
}

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


def analyze_snapshot(files: list[Path]) -> dict:
    files = sorted(files)
    file_records = {}

    defined_nodes = {}
    duplicate_ids = defaultdict(list)

    unique_edges = defaultdict(set)
    raw_edge_occurrences = defaultdict(int)

    # First pass: load all nodes and detect duplicates
    for f in files:
        kind = f.stem.split("_")[-1].lower()
        try:
            content = json.loads(f.read_text(encoding="utf-8-sig"))
        except Exception:
            content = json.loads(f.read_text(encoding="latin-1"))

        data = content.get("data", [])
        meta = content.get("meta", {})
        file_records[f.name] = {
            "kind": kind,
            "data_count": len(data),
            "meta_count": meta.get("count", len(data)),
            "size_bytes": f.stat().st_size,
        }

        label = ALL_KINDS.get(kind, "Base")

        for item in data:
            oid = item.get("ObjectIdentifier")
            if not oid:
                continue
            oid_norm = oid.upper()
            if oid_norm in defined_nodes:
                duplicate_ids[kind].append(oid_norm)
            else:
                defined_nodes[oid_norm] = {
                    "label": label,
                    "name": item.get("Properties", {}).get("name", ""),
                    "raw_item": item,
                }

    # Second pass: extract relationships according to BloodHound ingestion rules
    for f in files:
        kind = f.stem.split("_")[-1].lower()
        try:
            content = json.loads(f.read_text(encoding="utf-8-sig"))
        except Exception:
            content = json.loads(f.read_text(encoding="latin-1"))
        data = content.get("data", [])

        for item in data:
            src_oid = item.get("ObjectIdentifier", "").upper()
            if not src_oid:
                continue

            # 1. MemberOf from groups
            if kind == "groups":
                for member in item.get("Members", []):
                    m_oid = member.get("ObjectIdentifier", "").upper()
                    if m_oid:
                        raw_edge_occurrences["MemberOf"] += 1
                        unique_edges["MemberOf"].add((m_oid, src_oid))

            # 2. ACLs: GenericAll, WriteDacl, ForceChangePassword, Owns, WriteOwner, GenericWrite
            for ace in item.get("Aces", []):
                p_oid = ace.get("PrincipalSID", "").upper()
                right = ace.get("RightName", "")
                if not p_oid or not right:
                    continue
                raw_edge_occurrences[right] += 1
                unique_edges[right].add((p_oid, src_oid))

            # 3. LocalGroups on Computers: AdminTo (-544), raw RDU (-555), CanPSRemote (-580)
            if kind == "computers":
                for lg in item.get("LocalGroups", []):
                    lg_id = lg.get("ObjectIdentifier", "").upper()
                    for m in lg.get("Results", []):
                        m_id = m.get("ObjectIdentifier", "").upper()
                        if not m_id:
                            continue
                        if lg_id.endswith("-544"):
                            raw_edge_occurrences["AdminTo"] += 1
                            unique_edges["AdminTo"].add((m_id, src_oid))
                        elif lg_id.endswith("-555"):
                            raw_edge_occurrences["RemoteDesktopUsers_raw_memberships"] += 1
                            unique_edges["RemoteDesktopUsers_raw_memberships"].add((m_id, src_oid))
                        elif lg_id.endswith("-580"):
                            raw_edge_occurrences["CanPSRemote"] += 1
                            unique_edges["CanPSRemote"].add((m_id, src_oid))

                # LocalAdmins (legacy or direct)
                for la in item.get("LocalAdmins", []):
                    la_id = la.get("ObjectIdentifier", "").upper()
                    if la_id:
                        raw_edge_occurrences["AdminTo"] += 1
                        unique_edges["AdminTo"].add((la_id, src_oid))

                # 4. Sessions: HasSession
                sessions = (
                    item.get("Sessions", {}).get("Results", [])
                    + item.get("PrivilegedSessions", {}).get("Results", [])
                    + item.get("RegistrySessions", {}).get("Results", [])
                )
                for s in sessions:
                    u_id = s.get("UserSID", "").upper()
                    if u_id:
                        raw_edge_occurrences["HasSession"] += 1
                        unique_edges["HasSession"].add((src_oid, u_id))

            # 5. Trusts on Domains
            if kind == "domains":
                for t in item.get("Trusts", []):
                    t_target = t.get("TargetDomainName", "").upper()
                    raw_edge_occurrences["Trust"] += 1
                    unique_edges["Trust"].add((src_oid, t_target))

    # Identify dangling references
    dangling_targets = set()
    for _edge_name, pairs in unique_edges.items():
        for src, tgt in pairs:
            if src not in defined_nodes:
                dangling_targets.add(src)
            if tgt not in defined_nodes:
                dangling_targets.add(tgt)

    # Node counts by primary label
    node_counts_by_label = defaultdict(int)
    m1_node_counts = defaultdict(int)
    for _n_id, info in defined_nodes.items():
        lbl = info["label"]
        node_counts_by_label[lbl] += 1
        if lbl in M1_KINDS.values():
            m1_node_counts[lbl] += 1

    return {
        "file_count": len(files),
        "total_raw_records": sum(f["data_count"] for f in file_records.values()),
        "total_unique_nodes": len(defined_nodes),
        "m1_unique_nodes": sum(m1_node_counts.values()),
        "node_counts_by_label": dict(node_counts_by_label),
        "m1_node_counts": dict(m1_node_counts),
        "duplicate_counts": {k: len(v) for k, v in duplicate_ids.items()},
        "total_duplicates": sum(len(v) for v in duplicate_ids.values()),
        "dangling_reference_count": len(dangling_targets),
        "dangling_samples": sorted(list(dangling_targets))[:5],
        "raw_edge_occurrences": dict(raw_edge_occurrences),
        "unique_edge_counts": {k: len(v) for k, v in unique_edges.items()},
        "m1_unique_edges": {k: len(unique_edges.get(k, set())) for k in CORE_M1_EDGES},
        "file_records": file_records,
    }


SNAPSHOT_DEFINITIONS = {
    "a-sharphound": {
        "snapshot_id": "sha256:ca5f09dd0272f607354086c53d255967eec51b7dab2d5bf9d3bbdd902f3d6f63",
        "raw_root": ROOT / "data" / "raw" / "dataset_a",
        "file_pattern": "NORTH_20240410083414_*.json",
        "expected_files": 12,
        "staging_dir": ROOT / "data" / "processed" / "snapshot-inputs" / "a-sharphound",
    },
    "a-python": {
        "snapshot_id": "sha256:b25cb32639ed10c1b0ddf488bf02b6547740a0a1eed00259571c4dd776516cdc",
        "raw_root": ROOT / "data" / "raw" / "dataset_a",
        "file_pattern": "ce_branch_bloodhoundpy_20240411011008_*.json",
        "expected_files": 7,
        "staging_dir": ROOT / "data" / "processed" / "snapshot-inputs" / "a-python",
    },
    "b-run-1": {
        "snapshot_id": "sha256:39d3a48729a01550467125c3115dedbb355205c02f46cd83e2f9dfb780e02602",
        "raw_root": ROOT / "data" / "raw" / "dataset_b",
        "file_pattern": "20240305110018_*.json",
        "expected_files": 12,
        "staging_dir": ROOT / "data" / "processed" / "snapshot-inputs" / "b-run-1",
    },
    "b-run-2": {
        "snapshot_id": "sha256:dfe659eef9715ffc37b51144d65e71552b775cbf263907b6c88f9dfb4d72196d",
        "raw_root": ROOT / "data" / "raw" / "dataset_b",
        "file_pattern": "20240305110427_*.json",
        "expected_files": 7,
        "staging_dir": ROOT / "data" / "processed" / "snapshot-inputs" / "b-run-2",
    },
    "b-run-3": {
        "snapshot_id": "sha256:e4198d8c06426aa2ea214ac261a43935b14e98fe516d57c48a8da5be18031c12",
        "raw_root": ROOT / "data" / "raw" / "dataset_b",
        "file_pattern": "20240305111414_*.json",
        "expected_files": 12,
        "staging_dir": ROOT / "data" / "processed" / "snapshot-inputs" / "b-run-3",
    },
    "dataset_b": {
        "snapshot_id": "sha256:f62a39280b2cfcaaa4d6a738365870b82765cd37458a3ac17ce8f2702514e3e1",
        "raw_root": ROOT / "data" / "raw" / "dataset_b",
        "file_pattern": "*.json",
        "expected_files": 31,
        "staging_dir": ROOT / "data" / "raw" / "dataset_b",
    },
}


def resolve_snapshot_files(snapshot_key: str) -> list[Path]:
    """Resolve JSON files for a snapshot from staging dir or directly from raw root."""
    cfg = SNAPSHOT_DEFINITIONS[snapshot_key]
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
    """Verify local files against deterministic snapshot manifest and return verified ID."""
    manifest_path = ROOT / "data" / "processed" / "manifests" / f"{snapshot_key}.json"
    cfg = SNAPSHOT_DEFINITIONS[snapshot_key]

    if manifest_path.exists():
        manifest = load_manifest(manifest_path)
        expected_files = {entry["relative_path"]: entry for entry in manifest["files"]}
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
        return verified_id

    if len(files) != cfg["expected_files"]:
        msg = (
            f"Snapshot '{snapshot_key}' file count mismatch: "
            f"got {len(files)}, expected {cfg['expected_files']}"
        )
        raise ManifestError(msg)
    for f in files:
        sig = _signature(f.lstat())
        _hash_file(f, sig)
    return cfg["snapshot_id"]


def main():
    results = {}
    for name in SNAPSHOT_DEFINITIONS:
        try:
            files = resolve_snapshot_files(name)
            verified_id = verify_snapshot_integrity(name, files)
        except Exception as e:
            print(f"Skipping {name}: {e}")
            continue

        print(f"Analyzing {name} ({len(files)} files, snapshot_id={verified_id})...")
        res = analyze_snapshot(files)
        results[name] = res
        print(
            f"  Files: {res['file_count']}, Raw records: {res['total_raw_records']}, "
            f"Unique Nodes: {res['total_unique_nodes']}, M1 Nodes: {res['m1_unique_nodes']}"
        )
        print(
            f"  Duplicates: {res['total_duplicates']}, "
            f"Dangling references: {res['dangling_reference_count']}"
        )
        print(f"  M1 Edges: {res['m1_unique_edges']}")
        print()

    out_file = ROOT / ".cache" / "bloodhound_baseline_summary.json"
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"Summary written to {out_file}")


if __name__ == "__main__":
    main()
