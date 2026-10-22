"""Import a manifest-verified AD dataset through the existing parser and fact builder."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

from src.data.manifest import ManifestError, load_manifest
from src.engine.batch import _atomic_json, execution_source_pins
from src.engine.graph import EngineGraph
from src.engine.query_cli import digest
from src.parser import DirectGraphBuilder, IdentityNormalizer, ManifestRawDataLoader, RecordError
from src.parser.adapters import adapt_bloodhound_v3_records
from src.parser.cli import canonicalize_graph, load_time_policy
from src.parser.snapshot_facts import serialize_snapshot

KINDS = {"users", "computers", "groups", "domains", "gpos", "ous"}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-dir", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--time-policy", type=Path)
    parser.add_argument(
        "--export-prefix", help="Select one collection's filename prefix from a combined manifest"
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--created-at", help="Export time only; not collection time")
    args = parser.parse_args(argv)
    try:
        return import_snapshot(args)
    except (ManifestError, RecordError, ValueError, OSError) as error:
        print(json.dumps({"status": "import_error", "error": str(error)}), file=sys.stderr)
        return 2


def import_snapshot(args):
    if args.output_dir.exists():
        raise FileExistsError(args.output_dir)
    manifest = load_manifest(args.manifest)
    pins = execution_source_pins()
    loader = ManifestRawDataLoader(args.manifest, time_policy=load_time_policy(args.time_policy))
    records, excluded = [], Counter()
    for record in loader.load(args.raw_dir):
        if (
            args.export_prefix
            and record.kind.casefold() != "domains"
            and not record.provenance["raw_file"].rsplit("/", 1)[-1].startswith(args.export_prefix)
        ):
            excluded["other_exports"] += 1
            continue
        if record.kind.casefold() in KINDS:
            records.append(record)
        else:
            excluded[record.kind] += 1
    normalized = IdentityNormalizer().normalize_records(adapt_bloodhound_v3_records(records))
    builder = DirectGraphBuilder(
        metadata={
            "snapshot_id": manifest["snapshot_id"],
            "created_at": args.created_at or datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "code_version": "source-pins:" + digest(json.dumps(pins, sort_keys=True).encode()),
        }
    )
    canonical, facts = builder.build_snapshot(normalized)
    payload = serialize_snapshot(canonicalize_graph(canonical), facts)
    graph = EngineGraph.from_snapshot(payload)
    args.output_dir.mkdir(parents=True, exist_ok=False)
    (args.output_dir / "snapshot.json").write_text(payload, encoding="utf-8")
    summary = {
        "dataset_id": manifest["dataset_id"],
        "snapshot_id": manifest["snapshot_id"],
        "snapshot_sha256": digest(payload.encode()),
        "manifest_sha256": digest(args.manifest.read_bytes()),
        "source_pins": pins,
        "runner_sha256": digest(Path(__file__).read_bytes()),
        "time_policy": json.loads(args.time_policy.read_text()) if args.time_policy else None,
        "export_prefix": args.export_prefix,
        "projection": "Existing six node kinds and direct relationships; snapshot facts retained",
        "excluded_record_kinds": dict(excluded),
        "nodes": dict(Counter(n["kind"] for n in graph.nodes())),
        "edges": dict(Counter(e["kind"] for e in graph.edges())),
    }
    _atomic_json(args.output_dir / "import.json", summary)
    print(
        json.dumps(
            {k: summary[k] for k in ("dataset_id", "nodes", "edges", "excluded_record_kinds")}
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
