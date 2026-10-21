"""Verify pinned SEAMLESS packet routes and replay its unrated scenario cases.

Uses the canonical parser export and research wire adapter, without implementing
search or the B-owned evaluator. Raw graph/records stay in ignored directories.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.metadata
import json
import platform
import subprocess
from pathlib import Path

from scripts.research.path_ranking_wire_adapter import (
    compute_kappa_with_fallback,
    decode_ranking_query,
    execute_ranking_roundtrip,
)
from src.data.manifest import load_manifest, verify_manifest
from src.parser.builder import canonical_edge_id
from src.parser.cli import atomic_write
from src.parser.serialization import deserialize_graph

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests" / "fixtures" / "ranking"
GRAPH_CODE_PIN = "4822e95045e7ebbe99316ddb56ac1b1d4e2dc30f"
GRAPH_DIGEST_PIN = "sha256:5781a365b3a44c57bc2b30f11a98d1f60242ca515ceca411e9c6e34cefd5518a"


def digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def verify_routes(graph: dict, payloads: list[dict]) -> list[dict]:
    """Require every route segment, including the computer ACL, in canonical output."""
    nodes = {node["id"] for node in graph["nodes"]}
    edges = {edge["id"]: edge for edge in graph["edges"]}
    reports = []
    for payload in payloads:
        foothold = payload["query"]["query_metadata"]["foothold_node_id"]
        target = payload["query"]["query_metadata"]["target_goal"]["target_asset_id"]
        for candidate in payload["candidates"]:
            for route in candidate["structural_routes"]:
                ids = route["node_ids"]
                if ids[0] != foothold or ids[-1] != target or not set(ids) <= nodes:
                    raise ValueError("route node/foothold/target binding mismatch")
                if len(route["edge_ids"]) != len(ids) - 1:
                    raise ValueError("route step count mismatch")
                for i, eid in enumerate(route["edge_ids"]):
                    if eid not in edges:
                        raise ValueError(f"missing canonical edge: {eid}")
                    edge = edges[eid]
                    if (edge["source"], edge["target"]) != (ids[i], ids[i + 1]):
                        raise ValueError("route edge endpoints mismatch")
                    if eid != canonical_edge_id(ids[i], ids[i + 1], edge["kind"]):
                        raise ValueError("route canonical edge hash mismatch")
                reports.append(
                    {
                        "route_id": route["route_id"],
                        "edge_count": len(ids) - 1,
                        "canonical_segments_verified": True,
                    }
                )
    return reports


def verify_raw_locators(
    graph: dict, payloads: list[dict], raw_dir: Path, *, bindings: dict | None = None
) -> int:
    """Cross-check every observed locator and canonical edge provenance against raw."""
    if bindings is None:
        bindings = json.loads(
            (FIXTURES / "seamless_predicate_bindings.json").read_text(encoding="utf-8")
        )["predicate_bindings"]
    raw = {}
    edges = {edge["id"]: edge for edge in graph["edges"]}
    verified = set()
    for payload in payloads:
        snapshot = payload["query"]["query_metadata"]["snapshot_id"].removeprefix("sha256:")
        evidence_edges = set()
        for fact in payload["query"]["facts_ledger"]["observed_facts"]:
            binding = bindings.get(fact["predicate"])
            if binding is None:
                raise ValueError(f"missing predicate binding: {fact['predicate']}")
            ref = fact["provenance_reference"]
            name, pointer = ref.split("#/", 1)
            if name not in raw:
                raw[name] = json.loads((raw_dir / name).read_text(encoding="utf-8-sig"))
            tokens = pointer.split("/")
            value = raw[name]
            for token in tokens:
                value = value[int(token)] if isinstance(value, list) else value[token]
            record = raw[name][tokens[0]][int(tokens[1])]
            if isinstance(value, bool):
                if (
                    binding.get("node_id") != record["ObjectIdentifier"]
                    or tokens[2:] != ["Properties", binding.get("property")]
                    or fact["layer"] != 2
                ):
                    raise ValueError(f"predicate binding mismatch: {fact['predicate']}")
                if value is not fact["truth_value"]:
                    raise ValueError(f"observed property mismatch: {ref}")
            else:
                if fact["truth_value"] is not True:
                    raise ValueError(f"positive relationship locator declared false: {ref}")
                kind = "GenericAll" if "Aces" in tokens else "MemberOf"
                source = value["PrincipalSID"] if kind == "GenericAll" else value["MemberId"]
                target = record["ObjectIdentifier"]
                if (binding.get("source"), binding.get("target"), binding.get("kind")) != (
                    source,
                    target,
                    kind,
                ) or fact["layer"] != 1:
                    raise ValueError(f"predicate binding mismatch: {fact['predicate']}")
                if kind == "GenericAll" and value["RightName"] != kind:
                    raise ValueError(f"observed ACE kind mismatch: {ref}")
                eid = canonical_edge_id(source, target, kind)
                edge = edges.get(eid)
                if not edge or not any(
                    prov["raw_file"] == f"snapshot:{snapshot}/{name}"
                    and prov["record_id"] == target
                    and prov.get("evidence_type") == "positive"
                    for prov in edge["provenance"]
                ):
                    raise ValueError(f"canonical provenance mismatch: {ref}")
                evidence_edges.add(eid)
            verified.add(ref)
        route_edges = {
            eid
            for c in payload["candidates"]
            for r in c["structural_routes"]
            for eid in r["edge_ids"]
        }
        if not route_edges <= evidence_edges:
            raise ValueError("route edge lacks a verified raw locator")
    return len(verified)


def replay_cases(payload: dict) -> list[dict]:
    """Expected/actual gates per query; denials are explicitly synthetic test inputs."""
    query = payload["query"]
    candidates = payload["candidates"]
    actions = {a["action_id"]: a for a in query["bound_actions"]}
    requirements = {
        r for c in candidates for aid in c["bound_action_ids"] for r in actions[aid]["requires"]
    }
    facts = query["facts_ledger"]
    assumptions = {f["predicate"] for f in facts["assumed_facts"]} & requirements
    variants = [
        ("positive_under_proposed_assumptions", None, None),
        ("evidence_only", None, "evidence_only"),
    ]
    variants += [
        (f"{kind}:{pred}", pred, kind)
        for pred in sorted(assumptions)
        for kind in ("required_false", "required_unknown")
    ]
    cases = []
    for case_id, pred, kind in variants:
        variant = copy.deepcopy(query)
        ledger = variant["facts_ledger"]
        if kind == "required_false":
            ledger["false_facts"].append(
                {
                    "predicate": pred,
                    "truth_value": False,
                    "layer": 3,
                    "provenance_reference": "synthetic:negative-case:" + pred,
                    "rationale": "Synthetic denial for veto testing; not observed SEAMLESS state.",
                }
            )
        elif kind == "required_unknown":
            ledger["assumed_facts"] = [f for f in ledger["assumed_facts"] if f["predicate"] != pred]
        elif kind == "evidence_only":
            variant["query_metadata"]["evaluation_mode"] = "evidence_only"
        result = execute_ranking_roundtrip(json.dumps(variant), candidates)["roundtrip_result"]
        expected = {}
        for c in candidates:
            affected = pred is not None and any(
                pred in actions[aid]["requires"] for aid in c["bound_action_ids"]
            )
            expected[c["candidate_id"]] = (
                "unknown"
                if kind == "evidence_only" or affected and kind == "required_unknown"
                else "blocked"
                if affected
                else "feasible"
            )
        actual = {cid: d["assessment"]["status"] for cid, d in result["diagnostics"].items()}
        if actual != expected or result["pareto_frontier"]:
            raise ValueError(f"scenario replay mismatch: {case_id}")
        cases.append(
            {
                "case_id": case_id,
                "input_classification": "synthetic_negative"
                if pred
                else "scenario_assumptions"
                if kind is None
                else "evidence_only",
                "expected": expected,
                "actual": actual,
                "verdict": "PASS",
            }
        )
    decoded = decode_ranking_query(json.dumps(query))
    if decoded["resolved_facts"]["session_badblood"]["value"] != "Unknown":
        raise ValueError("missing session was converted to observed false")
    return cases


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--graph", required=True, type=Path)
    parser.add_argument("--raw-dir", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    manifest_path = ROOT / "data/samples/manifests/seamless-raw-v1.json"
    manifest = load_manifest(manifest_path)
    if verify_manifest(args.raw_dir, manifest):
        raise ValueError("raw snapshot does not match pinned manifest")
    if digest(args.graph) != GRAPH_DIGEST_PIN:
        raise ValueError("canonical graph bytes do not match pin")
    graph = deserialize_graph(args.graph.read_text(encoding="utf-8"))
    if graph["metadata"]["code_version"] != GRAPH_CODE_PIN:
        raise ValueError("graph code revision does not match pin")
    if graph["metadata"]["snapshot_id"] != manifest["snapshot_id"]:
        raise ValueError("graph snapshot does not match pin")
    inputs = [FIXTURES / f"{stem}_query_input.json" for stem in ("seamless", "seamless_source_b")]
    payloads = [json.loads(path.read_text(encoding="utf-8")) for path in inputs]
    routes = verify_routes(graph, payloads)
    count = verify_raw_locators(graph, payloads, args.raw_dir)
    cases = {p["query"]["query_metadata"]["query_id"]: replay_cases(p) for p in payloads}
    for path, payload in zip(inputs, payloads, strict=True):
        actual = execute_ranking_roundtrip(json.dumps(payload["query"]), payload["candidates"])
        expected_path = path.with_name(path.name.replace("query_input", "expected_diagnostics"))
        if actual["roundtrip_result"] != json.loads(expected_path.read_text(encoding="utf-8")):
            raise ValueError("positive roundtrip differs from complete expected artifact")
    pins = inputs + [
        FIXTURES / name
        for name in (
            "seamless_time_policy.json",
            "seamless_rater_1.json",
            "seamless_rater_2.json",
            "seamless_expected_diagnostics.json",
            "seamless_source_b_expected_diagnostics.json",
            "seamless_predicate_bindings.json",
        )
    ]
    pins += [
        manifest_path,
        ROOT / "configs/contract.yml",
        ROOT / "configs/attack_semantics.yml",
        ROOT / "docs/research/evidence-rating-governance.md",
        ROOT / "scripts/research/path_ranking_wire_adapter.py",
        Path(__file__).resolve(),
        ROOT / "requirements.txt",
        ROOT / "requirements-dev.txt",
        ROOT / "tests/test_seamless_packet.py",
        ROOT / "docs/research/path-ranking-interface-specification.md",
    ]
    input_paths = [str(path.relative_to(ROOT)) for path in pins]
    input_changes = subprocess.check_output(
        ["git", "status", "--porcelain", "--untracked-files=all", "--", *input_paths],
        cwd=ROOT,
        text=True,
    ).strip()
    report = {
        "status": "PASS",
        "graph_metadata": graph["metadata"],
        "graph_digest": digest(args.graph),
        "collection_time_policy": json.loads(
            (FIXTURES / "seamless_time_policy.json").read_text(encoding="utf-8")
        ),
        "python_version": platform.python_version(),
        "installed_versions": {
            name: importlib.metadata.version(name)
            for name in ("networkx", "PyYAML", "pytest", "ruff", "yamllint")
        },
        "governance_version": "1.0.0 (Proposed)",
        "packet_code_revision": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        "packet_inputs_committed": not input_changes,
        "input_digests": {str(path.relative_to(ROOT)): digest(path) for path in pins},
        "verified_raw_file_count": len(manifest["files"]),
        "verified_observed_locators": count,
        "canonical_counts": {
            "nodes": len(graph["nodes"]),
            "edges": len(graph["edges"]),
            "assessments": len(graph["assessments"]),
        },
        "executed_reproduction_commands": [
            ".venv/bin/python scripts/snapshot_manifest.py verify data/raw/SEAMLESS "
            "data/samples/manifests/seamless-raw-v1.json",
            "At graph code pin: .venv/bin/python -m src.parser.cli "
            "--snapshot-id " + manifest["snapshot_id"] + " --raw-dir data/raw/SEAMLESS "
            "--profile unit --error-policy fail_fast "
            "--time-policy tests/fixtures/ranking/seamless_time_policy.json "
            "--created-at 2026-10-01T00:00:00Z "
            "--output data/processed/pr159-canonical-graph.json --summary",
            ".venv/bin/python -m scripts.research.seamless_packet_evidence "
            "--graph data/processed/pr159-canonical-graph.json --raw-dir data/raw/SEAMLESS "
            "--output reports/generated/pr159-packet-evidence.json",
            ".venv/bin/python -m pytest tests/test_seamless_packet.py "
            "tests/test_path_ranking_interface.py -q",
        ],
        "routes": routes,
        "scenario_cases": cases,
        "synthetic_one_target_kappa": compute_kappa_with_fallback(["Critical"], ["Critical"]),
        "ratings_status": "pending_independent_ratings",
        "assumption_review_status": "pending_B_review",
        "coverage": (
            "Three explicitly supplied structural routes in two separate queries; "
            "no search completeness claim."
        ),
    }
    atomic_write(args.output, json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(
        json.dumps(
            {
                "status": "PASS",
                "routes": len(routes),
                "scenario_cases": sum(map(len, cases.values())),
                "observed_locators": count,
                "graph_digest": report["graph_digest"],
            }
        )
    )


if __name__ == "__main__":
    main()
