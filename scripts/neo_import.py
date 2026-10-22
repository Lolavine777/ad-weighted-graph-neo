"""Import a manifest-verified AD dataset through the existing parser and fact builder."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from dataclasses import replace
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


def _strings(value):
    if isinstance(value, dict):
        for item in value.values():
            yield from _strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from _strings(item)
    elif isinstance(value, str):
        yield value


def _empty_generated(record):
    properties = record.data.get("Properties", {})
    return (
        properties.get("reconcile") is False
        and not set(properties) - {"name", "domain", "domainsid", "reconcile"}
        and all(
            value in (None, False, [], {})
            for key, value in record.data.items()
            if key not in {"ObjectIdentifier", "Properties"}
        )
    )


def _reference_strings(record):
    for key, value in record.data.items():
        if key == "ObjectIdentifier":
            continue
        if key == "Properties":
            for field, item in value.items():
                if field not in {"name", "domain", "domainsid", "distinguishedname", "objectid"}:
                    yield from _strings(item)
        else:
            yield from _strings(value)


def prepare_records(records, export_prefix):
    """Select one export and retain observed foreign identities as boundary objects.

    Boundary identities supply SID/DN resolution, not relationships from another
    export. Omit only explicit empty generated records with no references.
    Every omission and boundary representation remains identifiable in the audit.
    """
    supported = [r for r in records if r.kind.casefold() in KINDS]
    selected = [
        r
        for r in supported
        if export_prefix is None
        or r.provenance["raw_file"].rsplit("/", 1)[-1].startswith(export_prefix)
    ]
    if not selected:
        raise ValueError("No supported records match the export prefix")
    references = Counter(value.casefold() for r in selected for value in _reference_strings(r))
    omitted = [
        r
        for r in selected
        if _empty_generated(r) and references[r.data["ObjectIdentifier"].casefold()] == 0
    ]
    omitted_ids = {id(r) for r in omitted}
    selected = [r for r in selected if id(r) not in omitted_ids]
    audit = {
        "omitted_unreferenced_empty_generated": [r.provenance for r in omitted],
        "boundary_representations": [],
        "selected_domain_sid": None,
    }
    if export_prefix is None:
        return selected, audit
    domains = [r for r in selected if r.kind.casefold() == "domains"]
    if len(domains) != 1:
        raise ValueError("An export prefix must select exactly one observed Domain record")
    domain = domains[0].data["Properties"]["domain"].casefold()
    audit["selected_domain_sid"] = domains[0].data["ObjectIdentifier"]
    needed = {value.casefold() for r in selected for value in _strings(r.data)}
    local = [
        r
        for r in selected
        if not r.data.get("Properties", {}).get("domain")
        or r.data["Properties"]["domain"].casefold() == domain
    ]
    for record in supported:
        properties = record.data.get("Properties", {})
        if properties.get("domain", "").casefold() == domain:
            continue
        aliases = [record.data.get("ObjectIdentifier"), properties.get("distinguishedname")]
        if record.kind.casefold() != "domains" and not any(
            isinstance(alias, str) and alias.casefold() in needed for alias in aliases
        ):
            continue
        local.append(
            replace(
                record,
                data={
                    "ObjectIdentifier": record.data["ObjectIdentifier"],
                    "Properties": properties,
                    "is_boundary": True,
                },
            )
        )
        audit["boundary_representations"].append(record.provenance)
    return local, audit


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
    raw = list(loader.load(args.raw_dir))
    excluded = Counter(r.kind for r in raw if r.kind.casefold() not in KINDS)
    records, preparation = prepare_records(raw, args.export_prefix)
    normalized = IdentityNormalizer().normalize_records(adapt_bloodhound_v3_records(records))
    builder = DirectGraphBuilder(
        retain_unresolved_members=True,
        metadata={
            "snapshot_id": manifest["snapshot_id"],
            "created_at": args.created_at or datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "code_version": "source-pins:" + digest(json.dumps(pins, sort_keys=True).encode()),
        },
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
        "preparation": preparation,
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
