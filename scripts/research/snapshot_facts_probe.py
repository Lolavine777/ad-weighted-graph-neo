"""Read-only manifest-verified SEAMLESS trace; output contains aggregates only.

No exploit, roasting transition, runtime inference or identity mapping is emitted.
Missing private inputs exit 2 with an explicit SKIP, never a synthetic PASS.
"""

from __future__ import annotations

import argparse
import copy
import json
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.data.manifest import load_manifest, verify_manifest  # noqa: E402
from src.engine.graph import EngineGraph  # noqa: E402
from src.engine.semantics.evaluator import PreparedSemanticGraph  # noqa: E402
from src.parser import DirectGraphBuilder, IdentityNormalizer, ManifestRawDataLoader  # noqa: E402
from src.parser.adapters import adapt_bloodhound_v3_records  # noqa: E402
from src.parser.cli import canonicalize_graph, load_time_policy  # noqa: E402
from src.parser.snapshot_facts import FIELDS, graph_digest, serialize_snapshot  # noqa: E402

SNAPSHOT = "sha256:e0601d763eeea285d268ec9e468d321c50c9d7faba53c8e7442a2fcc4159c812"


def analyze(raw_dir: Path, manifest_path: Path, time_policy: Path, *, code_version: str) -> dict:
    manifest = load_manifest(manifest_path)
    if manifest["snapshot_id"] != SNAPSHOT:
        raise ValueError("probe requires pinned SEAMLESS snapshot")
    if verify_manifest(raw_dir, manifest):
        raise ValueError("private inputs do not match manifest")
    loader = ManifestRawDataLoader(manifest_path, time_policy=load_time_policy(time_policy))
    raw = tuple(loader.load(raw_dir))
    raw_before = copy.deepcopy(raw)
    normalized = IdentityNormalizer().normalize_records(adapt_bloodhound_v3_records(raw))
    normalized_before = copy.deepcopy(normalized)
    builder = DirectGraphBuilder(
        metadata={
            "snapshot_id": SNAPSHOT,
            "created_at": "2026-10-07T00:00:00Z",
            "code_version": code_version,
        }
    )
    baseline = canonicalize_graph(builder.build(normalized))
    graph, facts = builder.build_snapshot(normalized)
    graph = canonicalize_graph(graph)
    if baseline != graph:
        raise AssertionError("snapshot extraction changed canonical graph contents")
    engine = EngineGraph.from_snapshot(serialize_snapshot(graph, facts))
    prepared = PreparedSemanticGraph(engine.to_canonical(), snapshot_facts=engine.snapshot_facts)
    stats = {name: {"known": 0, "unknown": 0, "true": 0, "false": 0, "empty": 0} for name in FIELDS}
    users = [r for r in normalized if r.kind == "User"]
    for record in users:
        for name, field in FIELDS.items():
            fact = prepared.snapshot_facts.lookup(record.id, name)
            value = record.raw.data.get("Properties", {}).get(field)
            if type(value) is bool:
                assert fact.status == "known" and fact.value is value
            elif isinstance(value, list):
                assert fact.status == "known" and fact.value == tuple(value)
            elif value is None:
                assert fact.status == "unknown"
            else:
                raise AssertionError("unexpected SEAMLESS field shape; review input contract")
            expected_sources = [
                source
                for source in record.raw_representations
                if field in source.data.get("Properties", {})
            ]
            assert len(fact.evidence) == len(expected_sources)
            for evidence in fact.evidence:
                assert evidence.classification == "collector_normalized"
                assert evidence.provenance["attribute"] == "Properties." + field
                assert evidence.provenance["snapshot_id"] == SNAPSHOT
                assert evidence.provenance.get("record_locator")
            stats[name][fact.status] += 1
            if fact.value is True:
                stats[name]["true"] += 1
            elif fact.value is False:
                stats[name]["false"] += 1
            elif fact.value == ():
                stats[name]["empty"] += 1
    assert raw == raw_before and normalized == normalized_before
    assert engine.to_canonical() == graph == baseline
    return {
        "disposition": "PASS",
        "evidence": "actual_manifest_verified_SEAMLESS",
        "snapshot_id": SNAPSHOT,
        "code_version": code_version,
        "users": len(users),
        "nodes": len(graph["nodes"]),
        "edges": len(graph["edges"]),
        "canonical_digest": graph_digest(graph),
        "facts": stats,
        "invariants": {
            "complete_graph_equal": True,
            "raw_and_normalized_unchanged": True,
            "persisted_engine_semantic_lookup": True,
        },
        "attack_success": "not_evaluated",
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-dir", type=Path, required=True)
    parser.add_argument(
        "--manifest", type=Path, default=ROOT / "data/samples/manifests/seamless-raw-v1.json"
    )
    parser.add_argument(
        "--time-policy",
        type=Path,
        default=ROOT / "tests/fixtures/ranking/seamless_time_policy.json",
    )
    parser.add_argument(
        "--code-version", required=True, help="exact source commit or explicit working-tree label"
    )
    args = parser.parse_args(argv)
    if not args.raw_dir.is_dir() or not args.manifest.is_file():
        print(
            json.dumps(
                {"disposition": "SKIP", "prerequisite": "private SEAMLESS raw and pinned manifest"}
            )
        )
        return 2
    try:
        print(
            json.dumps(
                analyze(
                    args.raw_dir, args.manifest, args.time_policy, code_version=args.code_version
                ),
                sort_keys=True,
            )
        )
    except (OSError, ValueError, AssertionError) as exc:
        # Avoid dumping source paths/identities from record errors.
        frames = traceback.extract_tb(exc.__traceback__)
        print(
            json.dumps(
                {
                    "disposition": "FAIL",
                    "error_type": type(exc).__name__,
                    "stage": frames[-1].name,
                    "line": frames[-1].lineno,
                }
            )
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
