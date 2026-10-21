"""Pinned legacy SEAMLESS to CE schema 6, with independent conservation checks.

Run: .venv/bin/python -m scripts.convert_seamless_ce --output .cache/seamless-ce
Only inputs/*.json are uploaded; originals and manifest are provenance evidence.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import tempfile
from collections import Counter
from pathlib import Path

from src.data.manifest import (
    load_manifest,
    raw_file_reference,
    read_verified_snapshot_file,
    verify_manifest,
)

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "data/samples/manifests/seamless-raw-v1.json"
ROLES = {
    "LocalAdmins": "544",
    "RemoteDesktopUsers": "555",
    "DcomUsers": "562",
    "PSRemoteUsers": "580",
}
CHILDREN = {"Users": "User", "Computers": "Computer", "ChildOus": "OU"}
BASE = {"ObjectIdentifier", "Properties", "Aces"}
EMPTY = {"AllowedToAct", "AllowedToDelegate", "HasSIDHistory", "SPNTargets", "Trusts"}
FIELDS = {
    "computers": BASE | EMPTY | set(ROLES) | {"PrimaryGroupSid", "Sessions"},
    "users": BASE | EMPTY | {"PrimaryGroupSid"},
    "groups": BASE | {"Members"},
    "gpos": BASE,
    "domains": BASE | EMPTY | set(ROLES) | set(CHILDREN) | {"Links"},
    "ous": BASE | set(ROLES) | set(CHILDREN) | {"Links", "ACLProtected"},
}
RIGHTS = {
    ("Owner", ""): "Owns",
    ("ExtendedRight", "All"): "AllExtendedRights",
    ("ExtendedRight", "GetChanges"): "GetChanges",
    ("ExtendedRight", "GetChangesAll"): "GetChangesAll",
    **{(right, ""): right for right in ("GenericAll", "GenericWrite", "WriteDacl", "WriteOwner")},
}


def encoded(value):
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode()


def digest(data):
    return hashlib.sha256(data).hexdigest()


def typed(ref):
    if set(ref) != {"MemberId", "MemberType"} or not all(
        isinstance(v, str) and v for v in ref.values()
    ):
        raise ValueError("unsupported typed principal")
    return {"ObjectIdentifier": ref["MemberId"], "ObjectType": ref["MemberType"]}


def convert_records(raw):
    domains = {}
    for row in raw.get("domains", []):
        name = row["Properties"]["domain"]
        if name in domains:
            raise ValueError("ambiguous domain identity")
        domains[name] = row["ObjectIdentifier"]
    converted = copy.deepcopy(raw)
    for kind, rows in converted.items():
        if kind not in FIELDS:
            raise ValueError(f"unsupported collection {kind}")
        for row in rows:
            if set(row) - FIELDS[kind] or any(row.get(field) for field in EMPTY):
                raise ValueError(f"unsupported fields in {kind}")
            if not row.get("ObjectIdentifier") or not isinstance(row.get("Properties"), dict):
                raise ValueError("missing source identity or properties")
            for ace in row["Aces"]:
                if set(ace) != {
                    "PrincipalSID",
                    "PrincipalType",
                    "RightName",
                    "AceType",
                    "IsInherited",
                }:
                    raise ValueError("unsupported ACE fields")
                pair = (ace["RightName"], ace["AceType"])
                if pair not in RIGHTS:
                    raise ValueError(f"unsupported ACE {pair}")
                ace["RightName"] = RIGHTS[pair]
            if "Members" in row:
                row["Members"] = [typed(ref) for ref in row["Members"]]
            if kind in {"domains", "ous"}:
                if any(row.get(field) for field in ROLES):
                    raise ValueError("unsupported nonempty GPO local rights")
                row["ChildObjects"] = [
                    {"ObjectIdentifier": ref, "ObjectType": label}
                    for field, label in CHILDREN.items()
                    for ref in row.get(field, [])
                ]
                if "ACLProtected" in row:
                    row["IsACLProtected"] = row["ACLProtected"]
            if kind in {"users", "computers"}:
                row["DomainSID"] = domains[row["Properties"]["domain"]]
            if kind == "computers":
                if row.get("Sessions"):
                    raise ValueError("unsupported nonempty legacy Sessions")
                row["Sessions"] = {"Collected": True, "FailureReason": None, "Results": []}
                row["LocalGroups"] = [
                    {
                        "Collected": True,
                        "FailureReason": None,
                        "Results": [typed(ref) for ref in row[field]],
                        "Name": field,
                        "ObjectIdentifier": row["ObjectIdentifier"] + "-" + rid,
                    }
                    for field, rid in ROLES.items()
                    if row.get(field)
                ]
    validate_conservation(raw, converted)
    return converted


def validate_conservation(raw, converted):
    """Reverse schema changes and compare all source rows, including duplicate references."""
    restored = copy.deepcopy(converted)
    try:
        domains = {row["Properties"]["domain"]: row["ObjectIdentifier"] for row in raw["domains"]}
        for kind, rows in restored.items():
            for row in rows:
                for ace in row["Aces"]:
                    original = [
                        key[0]
                        for key, value in RIGHTS.items()
                        if value == ace["RightName"] and key[1] == ace["AceType"]
                    ]
                    if len(original) != 1:
                        raise ValueError("ACE mapping")
                    ace["RightName"] = original[0]
                if "Members" in row:
                    row["Members"] = [
                        {"MemberId": ref["ObjectIdentifier"], "MemberType": ref["ObjectType"]}
                        for ref in row["Members"]
                    ]
                if kind in {"domains", "ous"}:
                    expected = [
                        {"ObjectIdentifier": ref, "ObjectType": label}
                        for field, label in CHILDREN.items()
                        for ref in row.get(field, [])
                    ]
                    if row.pop("ChildObjects") != expected:
                        raise ValueError("children")
                    if "ACLProtected" in row and row.pop("IsACLProtected") != row["ACLProtected"]:
                        raise ValueError("ACL protection")
                if kind in {"users", "computers"}:
                    if row.pop("DomainSID") != domains[row["Properties"]["domain"]]:
                        raise ValueError("domain")
                if kind == "computers":
                    if row["Sessions"] != {"Collected": True, "FailureReason": None, "Results": []}:
                        raise ValueError("sessions")
                    row["Sessions"] = []
                    groups = row.pop("LocalGroups")
                    expected_roles = {field for field in ROLES if row.get(field)}
                    if (
                        len(groups) != len(expected_roles)
                        or {group["Name"] for group in groups} != expected_roles
                    ):
                        raise ValueError("local groups")
                    for group in groups:
                        field = group["Name"]
                        refs = [
                            {"MemberId": ref["ObjectIdentifier"], "MemberType": ref["ObjectType"]}
                            for ref in group["Results"]
                        ]
                        if (
                            refs != row[field]
                            or group["ObjectIdentifier"]
                            != row["ObjectIdentifier"] + "-" + ROLES[field]
                            or group["Collected"] is not True
                            or group["FailureReason"] is not None
                        ):
                            raise ValueError("local right")
        if set(raw) != set(restored) or any(
            Counter(encoded(row) for row in raw[kind])
            != Counter(encoded(row) for row in restored[kind])
            for kind in raw
        ):
            raise ValueError("source records")
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"conservation failure: {exc}") from exc
    return {
        "records": sum(map(len, raw.values())),
        "aces": sum(len(row["Aces"]) for rows in raw.values() for row in rows),
        "memberships": sum(len(row.get("Members", [])) for rows in raw.values() for row in rows),
        "containment": sum(
            len(row.get(f, [])) for rows in raw.values() for row in rows for f in CHILDREN
        ),
        "local_rights": sum(len(row.get(f, [])) for row in raw.get("computers", []) for f in ROLES),
    }


def install(source: Path, output: Path):
    if output.exists() or output.is_symlink():
        raise FileExistsError(f"refusing existing output: {output}")
    manifest = load_manifest(MANIFEST)
    errors = verify_manifest(source, manifest)
    if errors:
        raise ValueError(f"raw manifest mismatch: {errors}")
    originals, raw, metadata = {}, {}, {}
    for entry in manifest["files"]:
        name = entry["relative_path"]
        data = read_verified_snapshot_file(source, manifest, raw_file_reference(manifest, name))
        payload = json.loads(data.decode("utf-8-sig"))
        meta = payload["meta"]
        kind = meta["type"]
        if (
            set(payload) != {kind, "meta"}
            or meta["version"] != 3
            or meta["count"] != len(payload[kind])
        ):
            raise ValueError("unsupported legacy envelope")
        originals[name], raw[kind], metadata[name] = data, payload[kind], meta
    converted = convert_records(raw)
    evidence = {
        "adapter": "seamless-legacy-to-ce6-v1",
        "source_snapshot_id": manifest["snapshot_id"],
        "collector_claim": "adapter-generated compatibility schema, not a new collection",
        "schema_artifacts": "host-scoped LocalGroup nodes materialized by CE",
        "conservation": validate_conservation(raw, converted),
        "files": [],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".seamless-ce-", dir=output.parent) as temporary:
        staging = Path(temporary) / "output"
        (staging / "inputs").mkdir(parents=True)
        (staging / "originals").mkdir()
        for name, original in originals.items():
            meta = metadata[name]
            data = encoded({"data": converted[meta["type"]], "meta": {**meta, "version": 6}})
            (staging / "inputs" / name).write_bytes(data)
            (staging / "originals" / name).write_bytes(original)
            evidence["files"].append(
                {
                    "name": name,
                    "source_sha256": digest(original),
                    "converted_sha256": digest(data),
                    "source_meta": meta,
                }
            )
        (staging / "manifest.json").write_bytes(encoded(evidence))
        staging.rename(output)
    return evidence


def verify_install(source: Path, output: Path):
    """Verify provenance, converted bytes and conservation before any CE upload."""
    pinned = load_manifest(MANIFEST)
    errors = verify_manifest(source, pinned)
    if errors:
        raise ValueError(f"raw manifest mismatch: {errors}")
    manifest_bytes = (output / "manifest.json").read_bytes()
    evidence = json.loads(manifest_bytes)
    names = {entry["relative_path"] for entry in pinned["files"]}
    if (
        evidence["source_snapshot_id"] != pinned["snapshot_id"]
        or evidence["adapter"] != "seamless-legacy-to-ce6-v1"
        or len(evidence["files"]) != len(names)
        or {entry["name"] for entry in evidence["files"]} != names
    ):
        raise ValueError("converted manifest source mismatch")
    for directory in ("inputs", "originals"):
        if {path.name for path in (output / directory).iterdir()} != names:
            raise ValueError("converted file inventory mismatch")
    raw, converted, files = {}, {}, []
    for entry in evidence["files"]:
        name = entry["name"]
        original = read_verified_snapshot_file(source, pinned, raw_file_reference(pinned, name))
        source_payload = json.loads(original.decode("utf-8-sig"))
        for directory in ("inputs", "originals"):
            path = output / directory / name
            if path.is_symlink():
                raise ValueError("symlink in converted snapshot")
        path = output / "inputs" / name
        data = path.read_bytes()
        if (
            (output / "originals" / name).read_bytes() != original
            or entry["source_sha256"] != digest(original)
            or entry["converted_sha256"] != digest(data)
            or entry["source_meta"] != source_payload["meta"]
        ):
            raise ValueError("converted snapshot hash or provenance mismatch")
        payload = json.loads(data)
        meta = source_payload["meta"]
        if set(payload) != {"data", "meta"} or payload["meta"] != {**meta, "version": 6}:
            raise ValueError("converted metadata mismatch")
        raw[meta["type"]] = source_payload[meta["type"]]
        converted[meta["type"]] = payload["data"]
        files.append(path)
    if validate_conservation(raw, converted) != evidence["conservation"]:
        raise ValueError("conservation census mismatch")
    manifest_hash = digest(manifest_bytes)
    return {
        "files": files,
        "snapshot_id": "sha256:" + manifest_hash,
        "source_snapshot_id": pinned["snapshot_id"],
        "converted_manifest_sha256": manifest_hash,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=ROOT / "data/raw/SEAMLESS")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(install(args.source, args.output), indent=2))


if __name__ == "__main__":
    main()
