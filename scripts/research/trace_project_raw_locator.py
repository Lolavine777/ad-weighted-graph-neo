"""Resolve a project comparison triple's provenance to verified raw record locators."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if __package__ in {None, ""}:
    sys.path.insert(0, str(ROOT))

from src.data.manifest import load_manifest, verify_manifest  # noqa: E402


def record_locators(raw: dict, record_id: str, filename: str) -> list[str]:
    locators = []
    for collection, records in raw.items():
        if not isinstance(records, list):
            continue
        for index, record in enumerate(records):
            if not isinstance(record, dict):
                continue
            identifiers = (
                record.get("ObjectIdentifier"),
                record.get("Properties", {}).get("objectid"),
            )
            if record_id in identifiers:
                locators.append(f"{filename}#/{collection}/{index}")
    return locators


def trace(graph: dict, manifest: dict, raw_root: Path, triple: tuple[str, str, str]) -> list[dict]:
    if verify_manifest(raw_root, manifest):
        raise ValueError("raw manifest verification failed")
    if graph["metadata"]["snapshot_id"] != manifest["snapshot_id"]:
        raise ValueError("project/raw snapshot mismatch")
    permitted_files = {item["relative_path"] for item in manifest["files"]}
    matching = [
        edge for edge in graph["edges"] if (edge["source"], edge["kind"], edge["target"]) == triple
    ]
    results = []
    for edge in matching:
        evidence = []
        for provenance in edge.get("provenance", []):
            raw_ref = provenance["raw_file"]
            prefix = "snapshot:" + manifest["snapshot_id"].split(":", 1)[1] + "/"
            if not raw_ref.startswith(prefix):
                raise ValueError("provenance snapshot binding mismatch")
            filename = raw_ref.removeprefix(prefix)
            if filename not in permitted_files:
                raise ValueError("provenance file absent from manifest")
            raw = json.loads((raw_root / filename).read_text(encoding="utf-8-sig"))
            locators = record_locators(raw, provenance["record_id"], filename)
            evidence.append(
                {
                    "attribute": provenance["attribute"],
                    "record_id": provenance["record_id"],
                    "raw_record_locators": locators,
                    "status": "located" if locators else "unknown",
                }
            )
        results.append(
            {"edge_id": edge.get("id"), "triple": triple, "project_provenance": evidence}
        )
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True, type=Path)
    parser.add_argument(
        "--manifest", default=ROOT / "data/samples/manifests/seamless-raw-v1.json", type=Path
    )
    parser.add_argument("--raw-root", required=True, type=Path)
    parser.add_argument("--source", required=True)
    parser.add_argument("--kind", required=True)
    parser.add_argument("--target", required=True)
    args = parser.parse_args()
    try:
        result = trace(
            json.loads(args.project.read_text(encoding="utf-8")),
            load_manifest(args.manifest),
            args.raw_root,
            (args.source, args.kind, args.target),
        )
    except (ValueError, KeyError, OSError) as exc:
        print(f"Trace refused: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result else 1


if __name__ == "__main__":
    raise SystemExit(main())
