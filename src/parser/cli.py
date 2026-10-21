"""Build a canonical weighted graph from a verified manifest snapshot."""

from __future__ import annotations

import argparse
import json
import logging
import math
import os
import re
import subprocess
import sys
import tempfile
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

from scripts.check_contract import load_contract as _load_contract
from src.data import manifest as snapshot_manifest

from . import (
    DirectGraphBuilder,
    ErrorPolicy,
    Graph,
    IdentityNormalizer,
    ManifestRawDataLoader,
    TimeProvenancePolicy,
    TimeProvenanceStatus,
)
from .adapters import adapt_bloodhound_v3_records
from .serialization import serialize_graph

ROOT = Path(__file__).resolve().parents[2]
SNAPSHOT_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")
ERROR_POLICIES = tuple(policy.value for policy in ErrorPolicy)


class _WarningCounter(logging.Handler):
    """Count parser warnings for the optional summary without changing logging."""

    def __init__(self) -> None:
        super().__init__(level=logging.WARNING)
        self.count = 0

    def emit(self, record: logging.LogRecord) -> None:
        self.count += 1


def load_contract(path: Path | str | None = None) -> dict:
    """Load and fully validate the canonical graph contract."""
    target_path = Path(
        path if path is not None and str(path) != "" else ROOT / "configs" / "contract.yml"
    )
    return _load_contract(target_path)


def resolve_profile(contract: dict, profile_name: str) -> dict[str, float | int]:
    """Return a validated profile's complete weight mapping."""
    profiles = contract.get("profiles")
    if not isinstance(profiles, dict) or profile_name not in profiles:
        raise ValueError(f"unknown weight profile: {profile_name}")
    profile = profiles[profile_name]
    edge_kinds = contract.get("edge_kinds")
    if not isinstance(profile, dict) or not isinstance(edge_kinds, list):
        raise ValueError(f"malformed weight profile: {profile_name}")
    weights = profile.get("weights")
    if not isinstance(weights, dict):
        raise ValueError(f"profile {profile_name} weights must be a mapping")
    missing = sorted(set(edge_kinds) - set(weights))
    extra = sorted(set(weights) - set(edge_kinds))
    if missing or extra:
        raise ValueError(
            f"profile {profile_name} edge weights do not match contract"
            f" (missing={missing}, unknown={extra})"
        )
    for kind in edge_kinds:
        weight = weights[kind]
        if type(weight) not in (int, float) or not math.isfinite(weight) or weight < 1.0:
            raise ValueError(f"profile {profile_name} has an invalid weight for {kind}")
    return cast(dict[str, float | int], weights)


def resolve_manifest(manifest_dir: Path, snapshot_id: str) -> tuple[Path, dict]:
    """Find the unique validated local manifest for a canonical snapshot ID."""
    if not SNAPSHOT_PATTERN.fullmatch(snapshot_id):
        raise ValueError("snapshot ID must be sha256: followed by 64 lowercase hexadecimal digits")
    if not manifest_dir.is_dir():
        raise ValueError(f"manifest directory does not exist: {manifest_dir}")
    matches: list[tuple[Path, dict]] = []
    for path in sorted(manifest_dir.glob("*.json")):
        try:
            manifest = snapshot_manifest.load_manifest(path)
        except snapshot_manifest.ManifestError as exc:
            raise ValueError(f"invalid manifest {path.name}: {exc}") from exc
        if manifest["snapshot_id"] == snapshot_id:
            matches.append((path, manifest))
    if not matches:
        raise ValueError(f"snapshot is not present in manifest directory: {snapshot_id}")
    if len(matches) > 1:
        raise ValueError(f"multiple manifests resolve snapshot ID: {snapshot_id}")
    return matches[0]


def load_time_policy(path: Path | None) -> TimeProvenancePolicy | None:
    """Load an explicit generic collection-time policy, if supplied."""
    if path is None:
        return None

    def unique_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate collection-time policy field: {key}")
            result[key] = value
        return result

    try:
        payload = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique_keys)
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        raise ValueError(f"unable to load collection-time policy: {path}") from exc
    if not isinstance(payload, dict) or set(payload) - {"timestamp", "status", "reason"}:
        raise ValueError("collection-time policy must contain only timestamp, status, and reason")
    if not isinstance(payload.get("timestamp"), str) or not isinstance(payload.get("status"), str):
        raise ValueError("collection-time policy requires string timestamp and status fields")
    try:
        status = TimeProvenanceStatus(payload["status"])
        return TimeProvenancePolicy(
            timestamp=payload["timestamp"],
            status=status,
            reason=payload.get("reason"),
        )
    except (TypeError, ValueError) as exc:
        raise ValueError(f"invalid collection-time policy: {exc}") from exc


def apply_weights(graph: Graph, profile_name: str, weights: dict[str, float | int]) -> None:
    """Assign the selected profile weight to every traversable edge."""
    for edge in graph["edges"]:
        kind = edge["kind"]
        if kind not in weights:
            raise ValueError(f"profile {profile_name} has no weight for traversable edge {kind}")
        edge["weight"] = weights[kind]


def canonicalize_graph(graph: Graph) -> Graph:
    """Order canonical top-level collections by their stable identities."""
    graph["nodes"] = sorted(graph["nodes"], key=lambda item: item["id"])
    graph["edges"] = sorted(graph["edges"], key=lambda item: item["id"])
    graph["assessments"] = sorted(graph["assessments"], key=lambda item: item["id"])
    return graph


def resolve_code_version(repo_root: Path = ROOT) -> str:
    """Resolve a full commit only when parser inputs match the committed source tree."""
    try:
        status = subprocess.run(
            [
                "git",
                "status",
                "--porcelain",
                "--untracked-files=all",
                "--",
                "src/parser",
                "src/data",
                "configs",
                "scripts/check_contract.py",
            ],
            cwd=repo_root,
            capture_output=True,
            check=True,
            text=True,
        )
        if status.stdout.strip():
            raise RuntimeError(
                "parser source or contract files have uncommitted changes; "
                "commit or revert them before graph export"
            )
        result = subprocess.run(
            ["git", "rev-parse", "--verify", "HEAD"],
            cwd=repo_root,
            capture_output=True,
            check=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise RuntimeError(
            "unable to resolve source Git commit or verify source cleanliness"
        ) from exc
    commit = result.stdout.strip()
    if not re.fullmatch(r"[0-9a-f]{40,64}", commit):
        raise RuntimeError("Git returned an invalid source commit for graph metadata")
    return commit


def atomic_write(path: Path, payload: str) -> None:
    """Write complete UTF-8 contents to a sibling temp file and atomically replace."""
    destination = Path(os.path.abspath(path))
    temporary: Path | None = None
    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            dir=destination.parent,
            prefix=f".{destination.name}.",
            suffix=".tmp",
            delete=False,
        ) as file:
            temporary = Path(file.name)
            file.write(payload)
            file.flush()
            os.fsync(file.fileno())
        os.replace(temporary, destination)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def build_graph(
    *,
    raw_dir: Path,
    manifest_path: Path,
    snapshot_id: str,
    profile: str,
    contract: dict,
    created_at: str,
    code_version: str,
    error_policy: ErrorPolicy,
    time_policy: TimeProvenancePolicy | None = None,
) -> Graph:
    """Run the existing loader, normalizer/reconciler, and direct builder."""
    metadata = {
        "contract_version": contract["version"],
        "weight_profile": profile,
        "snapshot_id": snapshot_id,
        "created_at": created_at,
        "code_version": code_version,
    }
    loader = ManifestRawDataLoader(manifest_path, time_policy=time_policy)
    raw_records = adapt_bloodhound_v3_records(loader.load(raw_dir, error_policy=error_policy))
    normalized = IdentityNormalizer().normalize_records(raw_records, error_policy=error_policy)
    graph = DirectGraphBuilder(metadata=metadata).build(normalized, error_policy=error_policy)
    apply_weights(graph, profile, resolve_profile(contract, profile))
    return canonicalize_graph(graph)


def render_summary(
    graph: Graph,
    output: Path,
    *,
    snapshot_id: str,
    profile: str,
    warning_count: int = 0,
    error_count: int = 0,
) -> str:
    """Render deterministic counts without changing graph contents."""
    nodes = Counter(node["kind"] for node in graph["nodes"])
    edges = Counter(edge["kind"] for edge in graph["edges"])
    assessments = Counter(str(item["status"]) for item in graph["assessments"])
    return "\n".join(
        [
            f"Nodes: {len(graph['nodes'])} "
            f"({', '.join(f'{key}={nodes[key]}' for key in sorted(nodes)) or 'none'})",
            f"Edges: {len(graph['edges'])} "
            f"({', '.join(f'{key}={edges[key]}' for key in sorted(edges)) or 'none'})",
            f"Assessments: {len(graph['assessments'])} "
            f"({', '.join(f'{key}={assessments[key]}' for key in sorted(assessments)) or 'none'})",
            f"Skipped records: unavailable; warnings: {warning_count}; errors: {error_count}",
            f"Snapshot ID: {snapshot_id}",
            f"Weight profile: {profile}",
            f"Output: {output}",
        ]
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot-id", required=True, help="canonical sha256 snapshot ID")
    parser.add_argument("--raw-dir", type=Path, help="raw snapshot root (contract default)")
    parser.add_argument(
        "--manifest-dir",
        type=Path,
        default=ROOT / "data" / "samples" / "manifests",
        help="directory containing validated JSON manifests",
    )
    parser.add_argument("--profile", default="unit", help="contract weight profile (default: unit)")
    parser.add_argument("--output", type=Path, help="output JSON path")
    parser.add_argument(
        "--error-policy",
        choices=ERROR_POLICIES,
        default=ErrorPolicy.FAIL_FAST.value,
    )
    parser.add_argument(
        "--time-policy",
        type=Path,
        help="JSON policy for unknown collection time; separate from --created-at",
    )
    parser.add_argument("--summary", action="store_true", help="print graph counts after writing")
    parser.add_argument("--created-at", help="explicit UTC export time (YYYY-MM-DDTHH:MM:SSZ)")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    warning_counter = _WarningCounter()
    root_logger = logging.getLogger()
    root_logger.addHandler(warning_counter)
    try:
        contract = load_contract()
        resolve_profile(contract, args.profile)
        created_at = args.created_at or datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        snapshot_manifest_timestamp = re.compile(
            contract["schema"]["metadata"]["timestamp_pattern"]
        )
        if not snapshot_manifest_timestamp.fullmatch(created_at):
            raise ValueError("created-at must be a UTC timestamp in YYYY-MM-DDTHH:MM:SSZ format")
        datetime.strptime(created_at, "%Y-%m-%dT%H:%M:%SZ")
        manifest_path, manifest = resolve_manifest(args.manifest_dir, args.snapshot_id)
        if manifest["snapshot_id"] != args.snapshot_id:
            raise ValueError("resolved manifest snapshot ID does not match requested snapshot")
        raw_dir = args.raw_dir or ROOT / contract["paths"]["raw"]
        time_policy = load_time_policy(args.time_policy)
        code_version = resolve_code_version()
        output = args.output or (
            ROOT
            / contract["paths"]["processed"]
            / "graphs"
            / f"graph-{args.profile}-{args.snapshot_id.removeprefix('sha256:')}.json"
        )
        graph = build_graph(
            raw_dir=raw_dir,
            manifest_path=manifest_path,
            snapshot_id=args.snapshot_id,
            profile=args.profile,
            contract=contract,
            created_at=created_at,
            code_version=code_version,
            error_policy=ErrorPolicy(args.error_policy),
            time_policy=time_policy,
        )
        payload = serialize_graph(graph, contract=contract)
        atomic_write(output, payload)
        if args.summary:
            print(
                render_summary(
                    graph,
                    output,
                    snapshot_id=args.snapshot_id,
                    profile=args.profile,
                    warning_count=warning_counter.count,
                    error_count=0,
                )
            )
        return 0
    except (ValueError, RuntimeError, OSError, snapshot_manifest.ManifestError) as exc:
        logging.getLogger(__name__).error("parser CLI failed: %s", exc)
        print(f"parser CLI failed: {exc}", file=sys.stderr)
        return 1
    finally:
        root_logger.removeHandler(warning_counter)


if __name__ == "__main__":
    sys.exit(main())
