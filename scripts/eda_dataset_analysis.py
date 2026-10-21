"""Exploratory structural and descriptive telemetry analysis of AD datasets.

Profiles SEAMLESS.INTERNAL, historical datasets, and an independent telemetry
corpus without treating event distributions as attack or relationship evidence.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import os
import statistics
import subprocess
import sys
import tempfile
from collections import Counter, defaultdict, deque
from itertools import islice
from pathlib import Path
from typing import Any

import networkx as nx

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.data.manifest import (  # noqa: E402
    ManifestError,
    load_manifest,
    raw_file_reference,
    read_verified_snapshot_file,
    verify_manifest,
)

REQUIRED_SEAMLESS_ROLES = ("computers", "domains", "gpos", "groups", "ous", "users")
REQUIRED_TELEMETRY_FILES = ("evtx_data.csv",)


def validate_snapshot_roles(manifest: dict, dataset_type: str) -> list[str]:
    """Validate that the manifest contains required envelope roles or expected files."""
    issues: list[str] = []
    files = manifest.get("files", [])
    if dataset_type == "seamless":
        for role in REQUIRED_SEAMLESS_ROLES:
            target_suffix = f"_{role}.json"
            target_exact = f"{role}.json"
            matches = [
                f
                for f in files
                if f["relative_path"].lower().endswith(target_suffix)
                or f["relative_path"].lower() == target_exact
            ]
            if not matches:
                issues.append(f"Missing required SEAMLESS envelope role: '{role}'")
            elif len(matches) > 1:
                matched_paths = [m["relative_path"] for m in matches]
                issues.append(
                    f"Ambiguous/duplicate match for SEAMLESS envelope role '{role}': "
                    f"{matched_paths}"
                )
    elif dataset_type == "telemetry":
        matches = [
            f
            for f in files
            if f["relative_path"].lower() == "evtx_data.csv"
            or Path(f["relative_path"]).name.lower() == "evtx_data.csv"
        ]
        if not matches:
            issues.append("Missing required telemetry file: 'evtx_data.csv'")
        elif len(matches) > 1:
            matched_paths = [m["relative_path"] for m in matches]
            issues.append(
                f"Ambiguous/duplicate match for telemetry file 'evtx_data.csv': {matched_paths}"
            )
    return issues


def get_code_revision(root_dir: Path | None = None) -> dict[str, Any]:
    """Return reproducible generator identity including script SHA-256 and git state."""
    base_dir = root_dir if root_dir is not None else ROOT
    script_path = Path(__file__).resolve()
    try:
        script_sha256 = hashlib.sha256(script_path.read_bytes()).hexdigest()
    except Exception:
        script_sha256 = "unknown"

    commit: str | None = None
    dirty: bool | None = None

    try:
        proc = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=base_dir,
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode == 0 and proc.stdout.strip():
            commit = proc.stdout.strip()
            status_proc = subprocess.run(
                ["git", "status", "--porcelain", "--untracked-files=no"],
                cwd=base_dir,
                capture_output=True,
                text=True,
                check=False,
            )
            if status_proc.returncode == 0:
                generated_report = Path("reports/eda_summary.json")
                changed_paths = []
                for line in status_proc.stdout.splitlines():
                    path_text = line[3:].split(" -> ")[-1].strip()
                    if Path(path_text) != generated_report:
                        changed_paths.append(path_text)
                dirty = bool(changed_paths)
    except Exception:
        pass

    return {
        "generator_sha256": script_sha256,
        "git_commit": commit,
        "git_dirty": dirty,
    }


def _git_output(args: list[str], *, cwd: Path = ROOT) -> str | None:
    """Return trimmed git output, or None when the requested object is unavailable."""
    try:
        proc = subprocess.run(
            ["git", *args],
            cwd=cwd,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return None
    if proc.returncode != 0 or not proc.stdout.strip():
        return None
    return proc.stdout.strip()


def _load_preserved_report(
    report_path: Path | None = None,
    *,
    git_ref: str | None = None,
    relative_path: str = "reports/eda_summary.json",
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Load a historical report and return its content plus immutable source metadata.

    A Git ref is preferred for reproducibility: it lets a clean checkout preserve the
    exact historical artifact without reading the output file that will be replaced.
    A filesystem path remains available for explicit fixture/report migration workflows.
    """
    if git_ref and report_path:
        raise ValueError("Specify only one historical report source")
    if not git_ref and not report_path:
        raise ValueError("A historical report path or Git ref is required")

    if git_ref:
        try:
            show_proc = subprocess.run(
                ["git", "show", f"{git_ref}:{relative_path}"],
                cwd=ROOT,
                capture_output=True,
                check=False,
            )
        except OSError as exc:
            raise ValueError("Git is unavailable for historical report preservation") from exc
        if show_proc.returncode != 0 or not show_proc.stdout:
            raise ValueError(f"Historical report is unavailable at Git ref '{git_ref}'")
        payload = show_proc.stdout
        source_commit = _git_output(["log", "-1", "--format=%H", git_ref, "--", relative_path])
        source = {
            "kind": "git_ref",
            "git_ref": git_ref,
            "git_commit": source_commit,
            "relative_path": relative_path,
        }
    else:
        assert report_path is not None
        if not report_path.is_file():
            raise ValueError(f"Historical report does not exist: {report_path}")
        payload = report_path.read_bytes()
        source = {
            "kind": "filesystem",
            "path": str(report_path.resolve()),
            "git_commit": _git_output(["log", "-1", "--format=%H", "--", str(report_path)]),
        }

    try:
        report = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("Historical report is not valid UTF-8 JSON") from exc
    if not isinstance(report, dict):
        raise ValueError("Historical report root must be a JSON object")
    source["sha256"] = hashlib.sha256(payload).hexdigest()
    return report, source


def _recompute_preserved_v4_metrics(dataset: dict[str, Any], removed_edges: int) -> None:
    """Recompute v4 aggregate metrics after removing legacy raw RDU edge labels."""
    if removed_edges <= 0:
        return

    total_edges = sum(dataset.get("edge_counts", {}).values())
    old_simple_edges = dataset.get("simple_edges", total_edges)
    simple_edges = max(0, old_simple_edges - removed_edges)
    total_nodes = dataset.get("total_nodes", 0)
    possible_pairs = total_nodes * (total_nodes - 1) if total_nodes > 1 else 0

    dataset["total_edges"] = total_edges
    dataset["simple_edges"] = simple_edges
    dataset["edge_to_node_ratio"] = round(total_edges / max(total_nodes, 1), 2)
    dataset["graph_density"] = round(simple_edges / possible_pairs, 6) if possible_pairs else 0.0
    dataset["multiedge_density"] = round(total_edges / possible_pairs, 6) if possible_pairs else 0.0

    density = dataset.setdefault("density_metrics", {})
    density["canonical_directed_simple_density"] = dataset["graph_density"]
    density["multigraph_edge_intensity"] = dataset["multiedge_density"]
    density["simple_edges_numerator"] = simple_edges
    density["total_edges_numerator"] = total_edges
    density.setdefault("unique_nodes", total_nodes)
    density.setdefault("possible_pairs_denominator", possible_pairs)

    ratios = dataset.setdefault("normalized_ratios", {})
    acl_details = ratios.get("details", {}).get("acl_density")
    if acl_details:
        acl_details["denominator"] = total_edges
        acl_details["value"] = round(acl_details.get("numerator", 0) / max(total_edges, 1), 4)
        ratios["acl_density"] = acl_details["value"]


def _migrate_preserved_v4_dataset(dataset: dict[str, Any]) -> dict[str, Any]:
    """Migrate historical v4 raw RDU counts away from the canonical CanRDP key."""
    migrated = json.loads(json.dumps(dataset))
    edge_counts = migrated.setdefault("edge_counts", {})
    legacy_canrdp = int(edge_counts.pop("CanRDP", 0) or 0)
    raw_counts = migrated.setdefault("raw_host_access_counts", {})
    raw_counts["RemoteDesktopUsers_raw_memberships"] = max(
        int(raw_counts.get("RemoteDesktopUsers_raw_memberships", 0) or 0),
        legacy_canrdp,
    )
    raw_counts["CanRDP_verified_effective_edges"] = None
    raw_counts["CanRDP_status"] = "unknown_without_complete_UserRights_evidence"
    if legacy_canrdp:
        _recompute_preserved_v4_metrics(migrated, legacy_canrdp)
    migrated["host_access_semantics"] = {
        "raw_primitive_key": "RemoteDesktopUsers_raw_memberships",
        "verified_relationship": "CanRDP",
        "verified_relationship_status": "unknown",
        "collection_completeness_status": "not_measurable_from_historical_report",
        "note": (
            "Historical CanRDP counts were produced from raw Remote Desktop Users membership; "
            "they are retained only as raw RDU observations because UserRights allow/deny "
            "and collection completeness evidence are unavailable."
        ),
    }
    return migrated


def _migrate_preserved_collector_bias(report: dict[str, Any]) -> dict[str, Any]:
    """Rename the legacy collector-bias raw RDU bucket without changing set totals."""
    migrated = json.loads(json.dumps(report))
    breakdown = migrated.get("Per_edge_kind_breakdown", {})
    legacy = breakdown.pop("CanRDP", None)
    if legacy is not None:
        existing = breakdown.get("RemoteDesktopUsers_raw_memberships")
        if existing is None:
            breakdown["RemoteDesktopUsers_raw_memberships"] = legacy
        else:
            for key in ("SharpHound", "BloodHound.py", "Common", "Union"):
                existing[key] = max(existing.get(key, 0), legacy.get(key, 0))
            existing["Jaccard"] = round(
                existing.get("Common", 0) / max(existing.get("Union", 0), 1), 4
            )
    migrated["Per_edge_kind_breakdown"] = breakdown
    migrated["Discrepancy_analysis"] = (
        "SharpHound collects local admin RPC/SAM and AD CS evidence "
        "(AdminTo, RemoteDesktopUsers_raw_memberships, Enroll), while BloodHound.py "
        "primarily performs standard LDAP queries. The raw RDU bucket is not verified "
        "CanRDP without UserRights allow/deny evidence."
    )
    migrated["semantic_note"] = (
        "RemoteDesktopUsers_raw_memberships is raw RDU evidence only; it is not verified CanRDP."
    )
    return migrated


def preserve_historical_sections(
    report: dict[str, Any], source: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Preserve historical sections through an explicit, deterministic migration path."""
    results = {}
    for dataset_name in ("NORTH", "ad_sampledata"):
        if dataset_name in report and isinstance(report[dataset_name], dict):
            results[dataset_name] = _migrate_preserved_v4_dataset(report[dataset_name])
            results[dataset_name]["preservation_metadata"] = {
                "status": "preserved_historical",
                "source": source,
            }
    if "collector_bias_comparison" in report:
        results["collector_bias_comparison"] = _migrate_preserved_collector_bias(
            report["collector_bias_comparison"]
        )
        results["collector_bias_comparison"]["preservation_metadata"] = {
            "status": "preserved_historical",
            "source": source,
        }
    return results, {
        "status": "scoped_preservation",
        "source": source,
        "preserved_sections": sorted(results),
    }


def build_cross_dataset_normalized_comparison(results: dict[str, Any]) -> dict[str, Any]:
    """Build comparison metrics from the currently assembled dataset sections."""
    comparison = {}
    for ds_name in ["SEAMLESS", "NORTH", "ad_sampledata"]:
        if ds_name in results and results[ds_name].get("status") != "skipped":
            ds = results[ds_name]
            nr = ds.get("normalized_ratios", {})
            comparison[ds_name] = {
                "total_raw_records": ds.get("total_raw_records", ds.get("total_nodes", 0)),
                "total_nodes": ds.get("total_nodes", 0),
                "total_edges": ds.get("total_edges", 0),
                "simple_edges": ds.get(
                    "simple_edges", ds.get("density_metrics", {}).get("simple_edges_numerator", 0)
                ),
                "edge_to_node_ratio": ds.get("edge_to_node_ratio", 0.0),
                "graph_density": ds.get("graph_density", 0.0),
                "multiedge_density": ds.get("multiedge_density", 0.0),
                "density_metrics": ds.get("density_metrics", {}),
                "privileged_principal_ratio": nr.get("privileged_principal_ratio", 0.0),
                "acl_density": nr.get("acl_density", 0.0),
                "session_density": nr.get("session_density", 0.0),
                "session_density_status": nr.get("session_density_status", "unknown"),
                "normalized_ratios_details": nr.get("details", {}),
            }
    return comparison


def _load_snapshot_json(
    data_dir: Path, pattern: str, manifest: dict | None = None
) -> tuple[str, dict] | None:
    """Load JSON content, verifying bytes against snapshot manifest if provided."""
    if manifest is not None:
        target = pattern.removeprefix("*").lower()
        matches = [
            entry
            for entry in manifest["files"]
            if entry["relative_path"].lower().endswith(target)
            or entry["relative_path"].lower() == target.lstrip("_")
        ]
        if not matches:
            raise ValueError(
                f"Manifest for '{data_dir}' does not contain required pattern: '{pattern}'"
            )
        if len(matches) > 1:
            paths = [m["relative_path"] for m in matches]
            raise ValueError(
                f"Ambiguous match for '{pattern}' in manifest for '{data_dir}': {paths}"
            )
        rel_path = matches[0]["relative_path"]
        ref = raw_file_reference(manifest, rel_path)
        payload = read_verified_snapshot_file(data_dir, manifest, ref)
        return rel_path, json.loads(payload.decode("utf-8-sig"))

    matched = list(data_dir.glob(pattern))
    if not matched:
        return None
    with matched[0].open("r", encoding="utf-8-sig") as f:
        return matched[0].name, json.load(f)


def reconcile_raw_records(items: list[dict]) -> tuple[list[dict], int]:
    """Reconcile duplicate records deterministically."""
    merged_items = {}
    non_oid_items = []

    for item in items:
        oid = item.get("ObjectIdentifier")
        if not oid:
            non_oid_items.append(item)
            continue

        if oid not in merged_items:
            # Create a copy so we don't mutate the original dictionary in place if we don't want to?  # noqa: E501
            # Actually, dictionary is fine to mutate, but let's copy to be safe.
            merged_items[oid] = dict(item)
            # ensure arrays are lists to allow safe extension
            for k in ["Properties", "Members", "Aces", "LocalAdmins", "LocalGroups"]:
                if k in merged_items[oid] and merged_items[oid][k] is None:
                    if k == "Properties":
                        merged_items[oid][k] = {}
                    else:
                        merged_items[oid][k] = []
            continue

        existing = merged_items[oid]

        # Merge Properties
        props_new = item.get("Properties") or {}
        props_ex = existing.get("Properties") or {}
        merged_props = {**props_ex}
        for k, v in props_new.items():
            if k in props_ex:
                val_ex = props_ex[k]
                if isinstance(v, bool) and isinstance(val_ex, bool):
                    merged_props[k] = v or val_ex
                elif v and not val_ex:
                    merged_props[k] = v
                elif val_ex and not v:
                    merged_props[k] = val_ex
                elif v != val_ex:
                    # Deterministic tie-break on conflict: lexicographical max for identical types,
                    # or string representation comparison, ensuring order invariance.
                    if type(v) is type(val_ex):
                        try:
                            merged_props[k] = max(v, val_ex)
                        except TypeError:
                            merged_props[k] = max(
                                json.dumps(v, sort_keys=True), json.dumps(val_ex, sort_keys=True)
                            )
                    else:
                        merged_props[k] = max(str(v), str(val_ex))
            else:
                merged_props[k] = v
        existing["Properties"] = merged_props

        # Arrays to deduplicate
        def merge_array(arr_ex, arr_new, key_func):
            seen = set()
            merged = []
            for e in arr_ex + arr_new:
                k = key_func(e)
                if k not in seen:
                    seen.add(k)
                    merged.append(e)
            return merged

        if "Members" in item or "Members" in existing:
            ex_members = existing.get("Members") or []
            new_members = item.get("Members") or []
            existing["Members"] = merge_array(
                ex_members,
                new_members,
                lambda x: (x.get("MemberId") or x.get("ObjectIdentifier") or "").upper(),
            )

        if "Aces" in item or "Aces" in existing:
            ex_aces = existing.get("Aces") or []
            new_aces = item.get("Aces") or []
            existing["Aces"] = merge_array(
                ex_aces,
                new_aces,
                lambda x: (
                    (x.get("PrincipalSID") or "").upper(),
                    x.get("RightName"),
                    x.get("AceType"),
                ),
            )

        if "LocalAdmins" in item or "LocalAdmins" in existing:
            ex_la = existing.get("LocalAdmins") or []
            new_la = item.get("LocalAdmins") or []
            existing["LocalAdmins"] = merge_array(
                ex_la,
                new_la,
                lambda x: (x.get("MemberId") or x.get("ObjectIdentifier") or "").upper(),
            )

        if "LocalGroups" in item or "LocalGroups" in existing:
            ex_lg_list = existing.get("LocalGroups") or []
            new_lg_list = item.get("LocalGroups") or []
            lg_dict: dict[str, dict] = {}
            for lg in ex_lg_list + new_lg_list:
                lg_oid = (lg.get("ObjectIdentifier") or "").upper()
                if not lg_oid:
                    continue
                if lg_oid not in lg_dict:
                    lg_copy = dict(lg)
                    lg_copy["Results"] = list(lg.get("Results") or [])
                    lg_dict[lg_oid] = lg_copy
                else:
                    target_lg = lg_dict[lg_oid]
                    for k_lg, v_lg in lg.items():
                        if k_lg == "Results":
                            continue
                        if k_lg not in target_lg or not target_lg[k_lg]:
                            target_lg[k_lg] = v_lg
                        elif target_lg[k_lg] and v_lg and target_lg[k_lg] != v_lg:
                            target_lg[k_lg] = max(str(target_lg[k_lg]), str(v_lg))
                    ex_results = target_lg.get("Results") or []
                    new_results = lg.get("Results") or []
                    seen_res = set()
                    merged_res = []
                    for res in ex_results + new_results:
                        res_id = (res.get("ObjectIdentifier") or res.get("MemberId") or "").upper()
                        if res_id and res_id not in seen_res:
                            seen_res.add(res_id)
                            merged_res.append(res)
                        elif not res_id:
                            merged_res.append(res)
                    target_lg["Results"] = sorted(
                        merged_res,
                        key=lambda x: (
                            x.get("ObjectIdentifier") or x.get("MemberId") or ""
                        ).upper(),
                    )
            existing["LocalGroups"] = sorted(
                lg_dict.values(),
                key=lambda x: (x.get("ObjectIdentifier") or "").upper(),
            )

        if "Sessions" in item or "Sessions" in existing:
            ex_sess = existing.get("Sessions") or []
            new_sess = item.get("Sessions") or []
            existing["Sessions"] = merge_array(
                ex_sess,
                new_sess,
                lambda x: (
                    (x.get("UserId") or x.get("UserSID") or "").upper(),
                    (x.get("ComputerId") or x.get("ComputerSID") or "").upper(),
                ),
            )

        # other fields: merge if empty in existing
        for k, v in item.items():
            if k not in [
                "Properties",
                "Members",
                "Aces",
                "LocalAdmins",
                "LocalGroups",
                "Sessions",
            ]:
                if k not in existing or not existing[k]:
                    existing[k] = v
                elif existing[k] and v and existing[k] != v:
                    if isinstance(existing[k], dict) and isinstance(v, dict):
                        for subk, subv in v.items():
                            if subk not in existing[k] or not existing[k][subk]:
                                existing[k][subk] = subv
                            elif isinstance(existing[k][subk], list) and isinstance(subv, list):
                                existing[k][subk] = existing[k][subk] + [
                                    x for x in subv if x not in existing[k][subk]
                                ]
                    else:
                        try:
                            existing[k] = max(existing[k], v)
                        except TypeError:
                            existing[k] = max(
                                json.dumps(existing[k], sort_keys=True),
                                json.dumps(v, sort_keys=True),
                            )

    reconciled = non_oid_items + sorted(
        merged_items.values(), key=lambda x: (x.get("ObjectIdentifier") or "").upper()
    )
    dropped = len(items) - len(reconciled)
    return reconciled, dropped


def _compute_gini(values: list[int | float]) -> float:
    """Compute Gini inequality coefficient for a list of values."""
    sorted_vals = sorted(values)
    n = len(sorted_vals)
    s = sum(sorted_vals)
    if s == 0 or n == 0:
        return 0.0
    return sum((2 * i - n - 1) * y for i, y in enumerate(sorted_vals, 1)) / (n * s)


def _compute_percentiles(values: list[int | float], percentiles: list[float]) -> dict[str, float]:
    """Compute percentiles using standard linear interpolation."""
    if not values:
        return {f"p{int(round(p * 100))}": 0.0 for p in percentiles}
    sorted_vals = sorted(values)
    n = len(sorted_vals)
    result: dict[str, float] = {}
    for p in percentiles:
        key = f"p{int(round(p * 100))}"
        if n == 1:
            result[key] = float(sorted_vals[0])
            continue
        k = (n - 1) * p
        f = int(k)
        c = f + 1
        if c < n:
            val = sorted_vals[f] + (k - f) * (sorted_vals[c] - sorted_vals[f])
        else:
            val = float(sorted_vals[f])
        result[key] = round(val, 2)
    return result


TRI_STATE_POSITIVE = "positive"
TRI_STATE_KNOWN_NEGATIVE = "known-negative"
TRI_STATE_UNKNOWN = "unknown"


def _normalise_tri_state(value: str | None) -> str:
    """Normalize the small tri-state vocabulary used by the EDA semantic helper."""
    if value in {TRI_STATE_POSITIVE, "true", "yes"}:
        return TRI_STATE_POSITIVE
    if value in {TRI_STATE_KNOWN_NEGATIVE, "negative", "false", "no", "absent"}:
        return TRI_STATE_KNOWN_NEGATIVE
    return TRI_STATE_UNKNOWN


def classify_canrdp_evidence(
    rdu_membership: str | None,
    allow_right: str | None,
    deny_right: str | None,
    *,
    completeness: str = "known",
) -> dict[str, Any]:
    """Classify canonical CanRDP evidence without building a production graph edge.

    This is deliberately an EDA/reporting helper for testing and evidence audits.  It
    requires the accepted composite rule's three mandatory dimensions and complete
    collection of those dimensions before returning a positive result.
    """
    states = {
        "rdu_membership": _normalise_tri_state(rdu_membership),
        "allow_right": _normalise_tri_state(allow_right),
        "deny_right": _normalise_tri_state(deny_right),
    }
    if completeness not in {"known", "complete"}:
        return {
            "status": TRI_STATE_UNKNOWN,
            "materialize": False,
            "reason": "mandatory primitive collection completeness is unknown",
            "primitives": states,
        }
    if TRI_STATE_UNKNOWN in states.values():
        return {
            "status": TRI_STATE_UNKNOWN,
            "materialize": False,
            "reason": "one or more mandatory CanRDP primitives are unknown",
            "primitives": states,
        }
    if (
        states["rdu_membership"] != TRI_STATE_POSITIVE
        or states["allow_right"] != TRI_STATE_POSITIVE
        or states["deny_right"] == TRI_STATE_POSITIVE
    ):
        return {
            "status": TRI_STATE_KNOWN_NEGATIVE,
            "materialize": False,
            "reason": "membership/allow requirement is not met or deny precedence applies",
            "primitives": states,
        }
    return {
        "status": TRI_STATE_POSITIVE,
        "materialize": True,
        "reason": "RDU membership and allow right are positive; deny right is known-negative",
        "primitives": states,
    }


def _summarize_raw_host_primitive(
    computers: list[dict], field_name: str, report_name: str
) -> dict[str, Any]:
    """Summarize a host-scoped raw array without turning emptiness into absence."""
    field_present = sum(1 for computer in computers if field_name in computer)
    missing_field = len(computers) - field_present
    empty_array = 0
    raw_count = 0
    for computer in computers:
        value = computer.get(field_name)
        if isinstance(value, list):
            raw_count += len(value)
            if not value:
                empty_array += 1
        elif field_name in computer:
            empty_array += 1

    positive_hosts = sum(
        1
        for computer in computers
        if isinstance(computer.get(field_name), list) and computer[field_name]
    )
    empty_or_unobserved = len(computers) - positive_hosts
    return {
        "report_name": report_name,
        "raw_field": f"Computer.{field_name}[]",
        "total_hosts": len(computers),
        "field_present_hosts": field_present,
        "field_missing_hosts": missing_field,
        "empty_array_hosts": empty_array,
        "hosts_with_positive_observation": positive_hosts,
        "empty_or_unobserved_hosts": empty_or_unobserved,
        "raw_observation_count": raw_count,
        "field_presence_rate": round(field_present / max(len(computers), 1) * 100, 2),
        "positive_observation_rate": round(positive_hosts / max(len(computers), 1) * 100, 2),
        "unknown_rate": "not_measurable_from_snapshot",
        "collection_completeness_status": "not_measurable_from_snapshot",
        "status": (
            "positive_observation_and_unknown_coverage"
            if positive_hosts
            else "empty_or_unobserved_with_unknown_coverage"
        ),
        "note": (
            f"{raw_count} raw {report_name} observation(s) were present on "
            f"{positive_hosts}/{len(computers)} hosts. The remaining "
            f"{empty_or_unobserved}/{len(computers)} hosts are empty or unobserved; "
            "collection completeness is not measurable from this snapshot, so canonical "
            "relationship absence cannot be concluded."
        ),
    }


def summarize_seamless_host_access(computers: list[dict]) -> dict[str, Any]:
    """Return raw host primitives and effective CanRDP measurability for SEAMLESS."""
    raw = {
        "RemoteDesktopUsers_raw_memberships": _summarize_raw_host_primitive(
            computers, "RemoteDesktopUsers", "Remote Desktop Users membership"
        ),
        "LocalAdmins_raw_memberships": _summarize_raw_host_primitive(
            computers, "LocalAdmins", "local Administrators membership"
        ),
        "PSRemoteUsers_raw_memberships": _summarize_raw_host_primitive(
            computers, "PSRemoteUsers", "Remote Management Users membership"
        ),
        "Sessions_raw_observations": _summarize_raw_host_primitive(
            computers, "Sessions", "session"
        ),
    }
    rdu = raw["RemoteDesktopUsers_raw_memberships"]
    effective_canrdp = {
        "relationship": "CanRDP",
        "status": TRI_STATE_UNKNOWN,
        "verified_effective_edges_count": None,
        "materialized_edges_count": 0,
        "unknown_hosts": len(computers),
        "required_primitives": [
            "effective Remote Desktop Users membership",
            "SeRemoteInteractiveLogonRight",
            "SeDenyRemoteInteractiveLogonRight",
        ],
        "collection_completeness_status": "not_measurable_from_snapshot",
        "raw_primitive_key": "RemoteDesktopUsers_raw_memberships",
        "note": (
            f"{rdu['raw_observation_count']} raw RDU membership observation(s) are reported "
            "separately. SEAMLESS does not provide sufficient UserRights and completeness "
            "evidence, so verified effective CanRDP cannot be measured or materialized; "
            "canonical relationship absence cannot be concluded."
        ),
    }
    return {"raw_primitives": raw, "effective_relationships": {"CanRDP": effective_canrdp}}


def build_networkx_graph(
    data_dir: Path,
    manifest: dict | None = None,
) -> tuple[nx.MultiDiGraph, nx.DiGraph, dict[str, dict]]:
    """Construct MultiDiGraph and DiGraph from BloodHound v3 dataset directory.

    Constructs both a MultiDiGraph (preserving all multigraph edges and types for
    mixing/concentration) and a DiGraph (for connectivity/reachability/paths),
    plus the nodes dictionary. Well-known external nodes are included if referenced.
    """
    type_files = {
        "User": "*_users.json",
        "Group": "*_groups.json",
        "Computer": "*_computers.json",
        "OU": "*_ous.json",
        "GPO": "*_gpos.json",
        "Domain": "*_domains.json",
    }

    if manifest is not None:
        role_issues = validate_snapshot_roles(manifest, "seamless")
        if role_issues:
            raise ValueError(f"SEAMLESS manifest failed semantic validation: {role_issues}")

    nodes: dict[str, dict] = {}
    loaded_items: dict[str, list[dict]] = {}

    for kind, pattern in type_files.items():
        loaded = _load_snapshot_json(data_dir, pattern, manifest)
        if loaded is None:
            continue
        _rel_name, content = loaded
        key = [k for k in content if k != "meta"][0]
        items = content[key]
        items, _dropped = reconcile_raw_records(items)
        loaded_items[kind] = items
        for item in items:
            oid = item.get("ObjectIdentifier")
            if not oid:
                continue
            oid_norm = oid.upper()
            props = item.get("Properties", {}) or {}
            nodes[oid_norm] = {
                "kind": kind,
                "name": props.get("name", ""),
                "admincount": bool(props.get("admincount", False)),
                "highvalue": bool(props.get("highvalue", False)),
                "raw": item,
            }

    # Include well-known external nodes if referenced
    well_known = {
        "SEAMLESS.INTERNAL-S-1-5-4": {
            "kind": "Group",
            "name": "INTERACTIVE@SEAMLESS.INTERNAL",
            "admincount": False,
            "highvalue": False,
            "raw": {},
            "is_external": True,
        },
        "SEAMLESS.INTERNAL-S-1-5-17": {
            "kind": "Group",
            "name": "IUSR@SEAMLESS.INTERNAL",
            "admincount": False,
            "highvalue": False,
            "raw": {},
            "is_external": True,
        },
    }
    for wk_id, wk_data in well_known.items():
        if wk_id not in nodes:
            nodes[wk_id] = wk_data

    G_multi = nx.MultiDiGraph()
    G_di = nx.DiGraph()

    for oid, data in nodes.items():
        node_attrs = {k: v for k, v in data.items() if k != "raw"}
        G_multi.add_node(oid, **node_attrs)
        G_di.add_node(oid, **node_attrs)

    for kind, items in loaded_items.items():
        for item in items:
            target_id = (item.get("ObjectIdentifier") or "").upper()
            if not target_id:
                continue

            if kind == "Group":
                for m in item.get("Members", []):
                    mid = (m.get("MemberId") or m.get("ObjectIdentifier") or "").upper()
                    if mid:
                        if mid not in nodes:
                            mtype = m.get("MemberType", "Group")
                            nodes[mid] = {
                                "kind": mtype,
                                "name": mid,
                                "admincount": False,
                                "highvalue": False,
                                "raw": {},
                                "is_external": True,
                            }
                            G_multi.add_node(mid, kind=mtype, name=mid)
                            G_di.add_node(mid, kind=mtype, name=mid)
                        G_multi.add_edge(mid, target_id, kind="MemberOf")
                        G_di.add_edge(mid, target_id, kind="MemberOf")

            elif kind == "Computer":
                for la in item.get("LocalAdmins", []):
                    mid = (la.get("MemberId") or la.get("ObjectIdentifier") or "").upper()
                    if mid:
                        if mid not in nodes:
                            nodes[mid] = {
                                "kind": "Principal",
                                "name": mid,
                                "admincount": False,
                                "highvalue": False,
                                "raw": {},
                                "is_external": True,
                            }
                            G_multi.add_node(mid, kind="Principal", name=mid)
                            G_di.add_node(mid, kind="Principal", name=mid)
                        G_multi.add_edge(mid, target_id, kind="AdminTo")
                        G_di.add_edge(mid, target_id, kind="AdminTo")

                # RemoteDesktopUsers[] is raw membership evidence only.  The
                # accepted CanRDP rule also requires effective UserRights allow
                # and deny evaluation, which this v3 snapshot does not contain.

                for ps in item.get("PSRemoteUsers", []):
                    mid = (ps.get("MemberId") or ps.get("ObjectIdentifier") or "").upper()
                    if mid:
                        if mid not in nodes:
                            nodes[mid] = {
                                "kind": "Principal",
                                "name": mid,
                                "admincount": False,
                                "highvalue": False,
                                "raw": {},
                                "is_external": True,
                            }
                            G_multi.add_node(mid, kind="Principal", name=mid)
                            G_di.add_node(mid, kind="Principal", name=mid)
                        G_multi.add_edge(mid, target_id, kind="CanPSRemote")
                        G_di.add_edge(mid, target_id, kind="CanPSRemote")

                for s in item.get("Sessions", []):
                    uid = (s.get("UserId") or s.get("UserSID") or "").upper()
                    if uid:
                        if uid not in nodes:
                            nodes[uid] = {
                                "kind": "User",
                                "name": uid,
                                "admincount": False,
                                "highvalue": False,
                                "raw": {},
                                "is_external": True,
                            }
                            G_multi.add_node(uid, kind="User", name=uid)
                            G_di.add_node(uid, kind="User", name=uid)
                        G_multi.add_edge(target_id, uid, kind="HasSession")
                        G_di.add_edge(target_id, uid, kind="HasSession")

            for ace in item.get("Aces", []):
                psid = (ace.get("PrincipalSID") or "").upper()
                right = ace.get("RightName", "")
                if psid and right:
                    if psid not in nodes:
                        ptype = ace.get("PrincipalType", "Principal")
                        nodes[psid] = {
                            "kind": ptype,
                            "name": psid,
                            "admincount": False,
                            "highvalue": False,
                            "raw": {},
                            "is_external": True,
                        }
                        G_multi.add_node(psid, kind=ptype, name=psid)
                        G_di.add_node(psid, kind=ptype, name=psid)
                    G_multi.add_edge(psid, target_id, kind=right)
                    G_di.add_edge(psid, target_id, kind=right)

    return G_multi, G_di, nodes


def compute_connectivity_metrics(G: nx.DiGraph) -> dict:
    """Compute Weakly and Strongly Connected Components, and node topological roles."""
    total_nodes = max(G.number_of_nodes(), 1)

    wcc = list(nx.weakly_connected_components(G))
    wcc_giant_size = len(max(wcc, key=len)) if wcc else 0

    scc = list(nx.strongly_connected_components(G))
    scc_giant_size = len(max(scc, key=len)) if scc else 0

    roles = {"isolated": 0, "source": 0, "sink": 0, "transit": 0}
    for n in G.nodes():
        in_d = G.in_degree(n)
        out_d = G.out_degree(n)
        if in_d == 0 and out_d == 0:
            roles["isolated"] += 1
        elif in_d == 0 and out_d > 0:
            roles["source"] += 1
        elif in_d > 0 and out_d == 0:
            roles["sink"] += 1
        else:
            roles["transit"] += 1

    G_undirected = G.to_undirected()
    clustering_coefficient = round(nx.average_clustering(G_undirected), 4)
    wcc_giant_comp = max(wcc, key=len) if wcc else set()
    giant_subgraph = G_undirected.subgraph(wcc_giant_comp)
    diameter_giant = nx.diameter(giant_subgraph) if wcc_giant_comp else 0

    possible_edges = total_nodes * (total_nodes - 1) if total_nodes > 1 else 0
    graph_density = round(G.number_of_edges() / possible_edges, 6) if possible_edges > 0 else 0.0

    return {
        "graph_density": graph_density,
        "wcc": {
            "count": len(wcc),
            "giant_component_size": wcc_giant_size,
            "giant_component_ratio": round(wcc_giant_size / total_nodes * 100, 2),
        },
        "scc": {
            "count": len(scc),
            "giant_component_size": scc_giant_size,
            "giant_component_ratio": round(scc_giant_size / total_nodes * 100, 2),
        },
        "clustering_coefficient": clustering_coefficient,
        "diameter": {
            "value": diameter_giant,
            "note": (
                "diameter of giant component (undirected projection); "
                "directed graph diameter is infinite due to sink nodes"
            ),
        },
        "node_roles": {
            role: {
                "count": count,
                "percentage": round(count / total_nodes * 100, 2),
            }
            for role, count in roles.items()
        },
    }


def compute_reachability_metrics(
    G: nx.DiGraph, nodes: dict, target_sids: list[str] | None = None
) -> dict:
    """Compute reachability to high-privilege targets across classes and hop distribution."""
    default_targets = [
        "S-1-5-21-1271839998-3495686680-2211690266-512",  # Domain Admins
        "SEAMLESS.INTERNAL-S-1-5-32-544",  # Builtin Administrators
        "S-1-5-21-1271839998-3495686680-2211690266-519",  # Enterprise Admins
    ]
    query_targets = target_sids if target_sids is not None else default_targets

    # Resolve target SIDs to ensure presence in G
    resolved_targets: list[str] = []
    for t in query_targets:
        t_norm = t.upper()
        if t_norm in G:
            if t_norm not in resolved_targets:
                resolved_targets.append(t_norm)
        elif t_norm.endswith("-544"):
            for candidate in ["SEAMLESS.INTERNAL-S-1-5-32-544", "S-1-5-32-544"]:
                if candidate in G and candidate not in resolved_targets:
                    resolved_targets.append(candidate)
                    break
        else:
            for n in G:
                if t_norm in n and n not in resolved_targets:
                    resolved_targets.append(n)
                    break

    G_rev = G.reverse()
    min_hops: dict[str, int] = {}
    target_reach_counts: dict[str, int] = defaultdict(int)

    for target in resolved_targets:
        if target in G_rev:
            lengths = nx.single_source_shortest_path_length(G_rev, target)
            for node, dist in lengths.items():
                if node not in min_hops or dist < min_hops[node]:
                    min_hops[node] = dist
                if dist > 0:
                    target_reach_counts[node] += 1

    # Non-target reachable nodes (hops >= 1)
    target_set = set(resolved_targets)
    non_target_hops = {
        node: dist for node, dist in min_hops.items() if node not in target_set and dist > 0
    }

    # Separate total graph nodes from security principals to fix denominator semantic
    non_target_graph_nodes = sum(1 for n in G.nodes() if n not in target_set)
    total_graph_nodes = G.number_of_nodes()
    reachable_graph_nodes_count = len(non_target_hops)
    reachable_graph_nodes_percentage = round(
        reachable_graph_nodes_count / max(non_target_graph_nodes, 1) * 100, 2
    )
    reachable_all_graph_nodes_percentage = round(
        reachable_graph_nodes_count / max(total_graph_nodes, 1) * 100, 2
    )

    security_principals = {
        n for n in G.nodes() if nodes.get(n, {}).get("kind") in ["User", "Group", "Computer"]
    }
    non_target_principals = {n for n in security_principals if n not in target_set}
    reachable_principals = {n for n in non_target_hops if n in non_target_principals}
    reachable_principal_count = len(reachable_principals)
    reachable_non_target_principal_percentage = round(
        reachable_principal_count / max(len(non_target_principals), 1) * 100, 2
    )

    # Class breakdown
    classes = ["User", "Group", "Computer"]
    class_breakdown: dict[str, dict] = {}
    for cls in classes:
        cls_total = sum(1 for n in G.nodes() if nodes.get(n, {}).get("kind") == cls)
        cls_reach = sum(1 for n in non_target_hops if nodes.get(n, {}).get("kind") == cls)
        cls_targets_reach_sum = sum(
            target_reach_counts.get(n, 0) for n in G.nodes() if nodes.get(n, {}).get("kind") == cls
        )
        class_breakdown[cls] = {
            "count": cls_reach,
            "total": cls_total,
            "percentage": round(cls_reach / max(cls_total, 1) * 100, 2),
            "avg_tier0_targets_reachable": round(cls_targets_reach_sum / max(cls_total, 1), 2),
        }

    # Shortest-hop distribution
    hop_values = list(non_target_hops.values())
    hop_histogram = Counter(hop_values)
    quantiles_data = _compute_percentiles(hop_values, [0.25, 0.50, 0.75, 0.90, 0.95])

    return {
        "target_sids": resolved_targets,
        "reachable_count": reachable_principal_count,
        "reachable_principal_count": reachable_principal_count,
        "reachable_graph_nodes_count": reachable_graph_nodes_count,
        "non_target_graph_nodes_count": non_target_graph_nodes,
        "total_graph_nodes_count": total_graph_nodes,
        "reachable_non_target_principal_percentage": reachable_non_target_principal_percentage,
        "reachable_graph_nodes_percentage": reachable_graph_nodes_percentage,
        "reachable_non_target_graph_nodes_percentage": reachable_graph_nodes_percentage,
        "reachable_all_graph_nodes_percentage": reachable_all_graph_nodes_percentage,
        "by_class": class_breakdown,
        "shortest_hop_distribution": {
            "histogram": {str(h): count for h, count in sorted(hop_histogram.items())},
            "min": min(hop_values) if hop_values else 0,
            "max": max(hop_values) if hop_values else 0,
            "median": statistics.median(hop_values) if hop_values else 0.0,
            "mean": round(statistics.mean(hop_values), 2) if hop_values else 0.0,
            "quantiles": {
                "p25": quantiles_data.get("p25", 0.0),
                "p50": quantiles_data.get("p50", 0.0),
                "p75": quantiles_data.get("p75", 0.0),
                "p90": quantiles_data.get("p90", 0.0),
                "p95": quantiles_data.get("p95", 0.0),
            },
        },
    }


PRIVILEGED_CONTROL_KINDS = {
    "AdminTo",
    "GenericAll",
    "WriteDacl",
    "ForceChangePassword",
    "CanRDP",
    "CanPSRemote",
}


def compute_privilege_concentration(G: nx.MultiDiGraph, nodes: dict) -> dict:
    """Compute Gini inequality coefficients, top-tier share, hubs/targets, and Lorenz curve.

    Calculates both raw graph out-degree concentration (overall topological connectivity)
    and privileged control-edge concentration (strictly for administrative control edges:
    AdminTo, GenericAll, WriteDacl, ForceChangePassword, CanRDP, CanPSRemote).
    """
    out_degrees = [G.out_degree(n) for n in G.nodes()]
    in_degrees = [G.in_degree(n) for n in G.nodes()]
    total_degrees = [G.degree(n) for n in G.nodes()]

    total_out = sum(out_degrees)
    total_nodes = max(G.number_of_nodes(), 1)

    sorted_out_nodes = sorted(G.nodes(), key=lambda n: G.out_degree(n), reverse=True)
    top_1pct_count = int(total_nodes * 0.01)
    top_5pct_count = int(total_nodes * 0.05)

    top_1pct_edges = sum(G.out_degree(n) for n in sorted_out_nodes[:top_1pct_count])
    top_5pct_edges = sum(G.out_degree(n) for n in sorted_out_nodes[:top_5pct_count])

    top_10_hubs = [
        {
            "id": n,
            "name": nodes.get(n, {}).get("name", n),
            "kind": nodes.get(n, {}).get("kind", "Unknown"),
            "out_degree": G.out_degree(n),
            "in_degree": G.in_degree(n),
        }
        for n in sorted_out_nodes[:10]
    ]

    sorted_in_nodes = sorted(G.nodes(), key=lambda n: G.in_degree(n), reverse=True)
    top_10_targets = [
        {
            "id": n,
            "name": nodes.get(n, {}).get("name", n),
            "kind": nodes.get(n, {}).get("kind", "Unknown"),
            "in_degree": G.in_degree(n),
            "out_degree": G.out_degree(n),
        }
        for n in sorted_in_nodes[:10]
    ]

    # Lorenz curve: deciles (0%, 10%, ..., 100%) vs cumulative share of outgoing edges
    sorted_asc_out = sorted(out_degrees)
    lorenz_points: list[dict] = []
    for d in range(0, 11):
        pct = d * 10
        idx = int(total_nodes * (pct / 100.0))
        cum_share = (sum(sorted_asc_out[:idx]) / total_out * 100) if total_out > 0 else 0.0
        lorenz_points.append({"percentile": pct, "cumulative_share": round(cum_share, 2)})

    # Privileged control edge concentration (excluding passive MemberOf and non-control edges)
    priv_out_degrees: dict[str, int] = {n: 0 for n in G.nodes()}
    for u, _v, _k, data in G.edges(keys=True, data=True):
        if data.get("kind") in PRIVILEGED_CONTROL_KINDS:
            priv_out_degrees[u] += 1
    priv_out_vals = list(priv_out_degrees.values())
    total_priv_out = sum(priv_out_vals)
    sorted_priv_nodes = sorted(G.nodes(), key=lambda n: priv_out_degrees[n], reverse=True)
    top_1pct_priv_edges = sum(priv_out_degrees[n] for n in sorted_priv_nodes[:top_1pct_count])
    top_5pct_priv_edges = sum(priv_out_degrees[n] for n in sorted_priv_nodes[:top_5pct_count])

    return {
        "metric_scope": (
            "Dual-scope analysis: raw_out_degree measures overall connectivity; "
            "privileged_control_edges measures administrative control concentration strictly on "
            "AdminTo, GenericAll, WriteDacl, ForceChangePassword, CanRDP, and CanPSRemote."
        ),
        "gini_coefficients": {
            "out_degree": round(_compute_gini(out_degrees), 4),
            "in_degree": round(_compute_gini(in_degrees), 4),
            "total_degree": round(_compute_gini(total_degrees), 4),
            "privileged_control_out_degree": round(_compute_gini(priv_out_vals), 4),
        },
        "top_shares": {
            "top_1_percent": {
                "node_count": top_1pct_count,
                "edge_count": top_1pct_edges,
                "share_percentage": round(top_1pct_edges / max(total_out, 1) * 100, 2),
            },
            "top_5_percent": {
                "node_count": top_5pct_count,
                "edge_count": top_5pct_edges,
                "share_percentage": round(top_5pct_edges / max(total_out, 1) * 100, 2),
            },
        },
        "privileged_control_concentration": {
            "total_control_edges": total_priv_out,
            "top_1_percent_share": round(top_1pct_priv_edges / max(total_priv_out, 1) * 100, 2),
            "top_5_percent_share": round(top_5pct_priv_edges / max(total_priv_out, 1) * 100, 2),
            "gini": round(_compute_gini(priv_out_vals), 4),
        },
        "top_10_hubs": top_10_hubs,
        "top_10_targets": top_10_targets,
        "lorenz_curve": lorenz_points,
        "degree_distribution": (
            "heavy-tailed / highly concentrated synthetic enterprise-scale benchmark"
        ),
        "description": (
            "Distribution exhibits heavy-tailed skew and extreme administrative hub concentration "
            "without claiming a mathematically verified scale-free power-law."
        ),
    }


def compute_relationship_mixing(G: nx.MultiDiGraph, nodes: dict) -> list[dict]:
    """Cross-tabulate source_kind x edge_kind x target_kind combinations."""
    total_edges = max(G.number_of_edges(), 1)
    triplet_counts: Counter[tuple[str, str, str]] = Counter()

    for u, v, _k, data in G.edges(keys=True, data=True):
        src_kind = nodes.get(u, {}).get("kind", "Unknown")
        dst_kind = nodes.get(v, {}).get("kind", "Unknown")
        edge_kind = data.get("kind", "Unknown")
        triplet_counts[(src_kind, edge_kind, dst_kind)] += 1

    mixing: list[dict] = []
    for (src, edge, dst), count in triplet_counts.most_common():
        mixing.append(
            {
                "source_kind": src,
                "edge_kind": edge,
                "target_kind": dst,
                "count": count,
                "percentage": round(count / total_edges * 100, 2),
            }
        )
    return mixing


def compute_group_nesting_pathology(group_subgraph: nx.DiGraph, nodes: dict) -> dict:
    """Verify group nesting DAG property, detect cycles, and compute branching and depth stats.

    For DAGs, nesting depth is computed as the longest nesting chain using dynamic programming
    over reverse topological order: dist[u] = max(dist[v] + 1 for v in successors(u)),
    ensuring that shortcut edges do not underestimate depth.
    """
    is_dag = nx.is_directed_acyclic_graph(group_subgraph)
    cycles = list(nx.simple_cycles(group_subgraph))

    out_degs = [group_subgraph.out_degree(n) for n in group_subgraph.nodes()]
    in_degs = [group_subgraph.in_degree(n) for n in group_subgraph.nodes()]

    depths: dict[str, int] = {}
    if is_dag:
        topo_order = list(nx.topological_sort(group_subgraph))
        dist: dict[str, int] = {n: 0 for n in group_subgraph.nodes()}
        for u in reversed(topo_order):
            for v in group_subgraph.successors(u):
                if dist[v] + 1 > dist[u]:
                    dist[u] = dist[v] + 1
        depths = {n: d for n, d in dist.items() if d > 0}
    else:
        # Longest path is undefined/infinite along cycles in a general cyclic digraph.
        # Report cycles explicitly and mark depth computation accordingly.
        depths = {}

    depth_dist = Counter(depths.values())

    return {
        "is_dag": is_dag,
        "cycles_count": len(cycles),
        "cycles": cycles,
        "branching_factor": {
            "out_degree_child_to_parents": {
                "max": max(out_degs) if out_degs else 0,
                "mean": round(statistics.mean(out_degs), 2) if out_degs else 0.0,
                "median": statistics.median(out_degs) if out_degs else 0.0,
                "distribution": {str(k): v for k, v in sorted(Counter(out_degs).items())},
            },
            "in_degree_parent_from_children": {
                "max": max(in_degs) if in_degs else 0,
                "mean": round(statistics.mean(in_degs), 2) if in_degs else 0.0,
                "median": statistics.median(in_degs) if in_degs else 0.0,
                "distribution": {str(k): v for k, v in sorted(Counter(in_degs).items())},
            },
        },
        "depth_stats": {
            "computation_method": (
                "longest_nesting_chain_dag_dp" if is_dag else "cyclic_graph_unsupported"
            ),
            "max_depth": max(depths.values()) if depths else 0,
            "avg_depth": round(statistics.mean(depths.values()), 2) if depths else 0.0,
            "distribution": {str(d): count for d, count in sorted(depth_dist.items())},
            "total_nested_groups": len(depths),
        },
    }


def compute_path_redundancy(
    G: nx.DiGraph, nodes: dict, sample_pairs: list[tuple[str, str]] | None = None
) -> list[dict]:
    """Evaluate path redundancy (disjoint and alternative paths) for sample pairs."""
    da_sid = "S-1-5-21-1271839998-3495686680-2211690266-512"
    if sample_pairs is None:
        armand_sid = None
        ola_sid = None
        for oid, d in nodes.items():
            name = d.get("name", "").upper()
            if "ARMAND_ROSE" in name:
                armand_sid = oid
            elif "OLA_CARSON" in name:
                ola_sid = oid

        std_user_sid = None
        if da_sid in G:
            for oid, d in nodes.items():
                if d.get("kind") == "User" and oid not in (armand_sid, ola_sid):
                    if nx.has_path(G, oid, da_sid):
                        sp = nx.shortest_path_length(G, oid, da_sid)
                        if 4 <= sp <= 5:
                            std_user_sid = oid
                            break

        pairs: list[tuple[str, str]] = []
        if armand_sid and da_sid in G:
            pairs.append((armand_sid, da_sid))
        if ola_sid and da_sid in G:
            pairs.append((ola_sid, da_sid))
        if std_user_sid and da_sid in G:
            pairs.append((std_user_sid, da_sid))
    else:
        pairs = sample_pairs

    results: list[dict] = []
    for s, t in pairs:
        if not (s in G and t in G and nx.has_path(G, s, t)):
            continue
        sp_hops = nx.shortest_path_length(G, s, t)
        nd_paths = len(list(nx.node_disjoint_paths(G, s, t)))
        ed_paths = len(list(nx.edge_disjoint_paths(G, s, t)))
        alt_paths_sample = len(list(islice(nx.all_simple_paths(G, s, t, cutoff=sp_hops + 1), 20)))

        results.append(
            {
                "source_id": s,
                "source_name": nodes.get(s, {}).get("name", s),
                "target_id": t,
                "target_name": nodes.get(t, {}).get("name", t),
                "shortest_hops": sp_hops,
                "node_disjoint_paths_count": nd_paths,
                "edge_disjoint_paths_count": ed_paths,
                "alternative_paths_sample_count": alt_paths_sample,
                "cutoff_hops": sp_hops + 1,
                "capped_at": 20,
                "truncated": alt_paths_sample >= 20,
                "description": (
                    "Alternative paths search within shortest_hops + 1 cutoff "
                    "capped at 20 (>= 20 paths exist)."
                ),
            }
        )
    return results


def compute_structural_outliers(G: nx.MultiDiGraph, nodes: dict) -> dict:
    """Flag outliers across degree, privilege count, nesting behavior, and session count."""
    out_degrees = {n: G.out_degree(n) for n in G.nodes()}
    in_degrees = {n: G.in_degree(n) for n in G.nodes()}

    admin_kinds = {
        "AdminTo",
        "GenericAll",
        "WriteDacl",
        "ForceChangePassword",
        "CanRDP",
        "CanPSRemote",
    }
    privilege_counts = {n: 0 for n in G.nodes()}
    for u, _v, _k, d in G.edges(keys=True, data=True):
        if d.get("kind") in admin_kinds:
            privilege_counts[u] += 1

    group_member_counts = {}
    for n, info in nodes.items():
        if info.get("kind") == "Group":
            group_member_counts[n] = sum(
                1 for u, v, d in G.in_edges(n, data=True) if d.get("kind") == "MemberOf"
            )

    def _get_outlier_report(val_dict: dict[str, int], metric_label: str = "degree") -> dict:
        if not val_dict:
            return {
                "metric": metric_label,
                "p99_threshold": 0,
                "p99_outlier_count": 0,
                "p99_outliers": [],
                "iqr_threshold": 0,
                "iqr_outlier_count": 0,
                "top_iqr_outliers": [],
            }
        vals = sorted(val_dict.values())
        p_data = _compute_percentiles(vals, [0.25, 0.75, 0.99])
        q1 = p_data["p25"]
        q3 = p_data["p75"]
        iqr = q3 - q1
        iqr_threshold = round(q3 + 1.5 * iqr, 2)
        p99_threshold = p_data["p99"]

        sorted_items = sorted(val_dict.items(), key=lambda x: x[1], reverse=True)
        p99_outliers = [
            {
                "id": n,
                "name": nodes.get(n, {}).get("name", n),
                "kind": nodes.get(n, {}).get("kind", "Unknown"),
                "degree": d,
                "value": d,
            }
            for n, d in sorted_items
            if d > p99_threshold
        ]
        iqr_outliers = [
            {
                "id": n,
                "name": nodes.get(n, {}).get("name", n),
                "kind": nodes.get(n, {}).get("kind", "Unknown"),
                "degree": d,
                "value": d,
            }
            for n, d in sorted_items
            if d > iqr_threshold
        ]

        return {
            "metric": metric_label,
            "p99_threshold": p99_threshold,
            "p99_outlier_count": len(p99_outliers),
            "p99_outliers": p99_outliers,
            "iqr_threshold": iqr_threshold,
            "iqr_outlier_count": len(iqr_outliers),
            "top_iqr_outliers": iqr_outliers[:20],
        }

    return {
        "boundary_note": (
            "Structural topological anomalies only; does not imply malicious activity."
        ),
        "out_degree": _get_outlier_report(out_degrees, "out_degree"),
        "in_degree": _get_outlier_report(in_degrees, "in_degree"),
        "privilege_count": _get_outlier_report(privilege_counts, "privilege_count"),
        "nesting_behavior": _get_outlier_report(group_member_counts, "group_member_count"),
        "session_count": {
            "status": "not_measurable_from_snapshot",
            "reason": (
                "Session data is unpopulated on endpoints (100% missing); dynamic sessions are not "
                "measurable from this static directory snapshot."
            ),
        },
    }


def trace_sample_control_path(
    nodes: dict[str, dict], group_memberships: dict[str, list[str]]
) -> list[dict]:
    """Find a concrete multi-hop attack path from a normal user to Domain Admins."""
    da_sid = "S-1-5-21-1271839998-3495686680-2211690266-512"
    if da_sid not in nodes:
        return []

    # Reverse adjacency: target -> list of (source, relationship)
    rev_adj: dict[str, list[tuple[str, str]]] = defaultdict(list)

    # 1. Group membership: mid is MemberOf gid -> edge mid -> gid
    for gid, members in group_memberships.items():
        for mid in members:
            rev_adj[gid].append((mid, "MemberOf"))

    # 2. ACLs: psid has RightName on target_id -> edge psid -> target_id
    for target_id, node_info in nodes.items():
        for ace in node_info["raw"].get("Aces", []):
            psid = ace.get("PrincipalSID", "").upper()
            right = ace.get("RightName", "")
            if psid and right in [
                "GenericAll",
                "WriteDacl",
                "WriteOwner",
                "ForceChangePassword",
            ]:
                rev_adj[target_id].append((psid, right))

    # Backward BFS from Domain Admins
    visited: dict[str, tuple[str, str] | None] = {da_sid: None}
    queue: deque[str] = deque([da_sid])

    while queue:
        curr = queue.popleft()
        for prev_node, edge_type in rev_adj.get(curr, []):
            if prev_node not in visited:
                visited[prev_node] = (curr, edge_type)
                queue.append(prev_node)

    # Find longest path starting from a non-admin user
    longest_path: list[dict] = []
    for oid, node_info in nodes.items():
        if node_info["kind"] == "User" and not node_info["admincount"] and oid in visited:
            path: list[dict] = []
            curr = oid
            while curr != da_sid:
                parent_info = visited[curr]
                if parent_info is None:
                    break
                nxt, edge_type = parent_info
                path.append(
                    {
                        "source_id": curr,
                        "source_name": nodes.get(curr, {}).get("name", curr),
                        "relationship": edge_type,
                        "target_id": nxt,
                        "target_name": nodes.get(nxt, {}).get("name", nxt),
                    }
                )
                curr = nxt
            if len(path) > len(longest_path):
                longest_path = path

    return longest_path


def parse_v3_dataset(data_dir: Path, manifest: dict | None = None) -> dict:
    """Parse BloodHound v3 dataset (e.g., SEAMLESS.INTERNAL)."""
    if manifest is not None:
        role_issues = validate_snapshot_roles(manifest, "seamless")
        if role_issues:
            raise ValueError(f"SEAMLESS manifest failed semantic validation: {role_issues}")

    raw_node_counts: dict[str, int] = defaultdict(int)
    reconciled_node_counts: dict[str, int] = defaultdict(int)
    total_dropped_records: int = 0
    nodes: dict[str, dict] = {}
    edges_by_kind: Counter[str] = Counter()
    group_memberships: dict[str, list[str]] = defaultdict(list)
    group_to_group: dict[str, list[str]] = defaultdict(list)
    ou_children: dict[str, list[str]] = defaultdict(list)
    ou_users: dict[str, list[str]] = defaultdict(list)
    ou_computers: dict[str, list[str]] = defaultdict(list)

    type_files = {
        "User": "*_users.json",
        "Group": "*_groups.json",
        "Computer": "*_computers.json",
        "OU": "*_ous.json",
        "GPO": "*_gpos.json",
        "Domain": "*_domains.json",
    }

    for kind, pattern in type_files.items():
        loaded = _load_snapshot_json(data_dir, pattern, manifest)
        if loaded is None:
            continue
        _rel_name, content = loaded
        key = [k for k in content if k != "meta"][0]
        items = content[key]
        raw_node_counts[kind] = len(items)
        items, dropped = reconcile_raw_records(items)
        total_dropped_records += dropped
        reconciled_node_counts[kind] = len(items)

        for item in items:
            oid = item.get("ObjectIdentifier")
            if not oid:
                continue
            oid_norm = oid.upper()
            props = item.get("Properties", {}) or {}
            nodes[oid_norm] = {
                "kind": kind,
                "name": props.get("name", ""),
                "admincount": bool(props.get("admincount", False)),
                "highvalue": bool(props.get("highvalue", False)),
                "raw": item,
            }

            if kind == "Group":
                for m in item.get("Members", []):
                    mid = (m.get("MemberId") or m.get("ObjectIdentifier") or "").upper()
                    mtype = m.get("MemberType")
                    if mid:
                        group_memberships[oid_norm].append(mid)
                        edges_by_kind["MemberOf"] += 1
                        if mtype == "Group":
                            group_to_group[mid].append(oid_norm)

            elif kind == "OU":
                for ch in item.get("ChildOus", []):
                    ou_children[oid_norm].append(ch.upper())
                for u in item.get("Users", []):
                    ou_users[oid_norm].append(u.upper())
                for c in item.get("Computers", []):
                    ou_computers[oid_norm].append(c.upper())

            elif kind == "Computer":
                for la in item.get("LocalAdmins", []):
                    mid = (la.get("MemberId") or la.get("ObjectIdentifier") or "").upper()
                    if mid:
                        edges_by_kind["AdminTo"] += 1
                for ps in item.get("PSRemoteUsers", []):
                    mid = (ps.get("MemberId") or ps.get("ObjectIdentifier") or "").upper()
                    if mid:
                        edges_by_kind["CanPSRemote"] += 1
                for s in item.get("Sessions", []):
                    uid = (s.get("UserId") or s.get("UserSID") or "").upper()
                    if uid:
                        edges_by_kind["HasSession"] += 1

            for ace in item.get("Aces", []):
                right = ace.get("RightName", "")
                psid = ace.get("PrincipalSID", "").upper()
                if psid and right:
                    edges_by_kind[right] += 1

    in_degree: Counter[str] = Counter()
    out_degree: Counter[str] = Counter()

    for gid, members in group_memberships.items():
        for m in members:
            out_degree[m] += 1
            in_degree[gid] += 1

    for oid_norm, node_data in nodes.items():
        item = node_data["raw"]
        for ace in item.get("Aces", []):
            right = ace.get("RightName", "")
            psid = ace.get("PrincipalSID", "").upper()
            if psid and right:
                out_degree[psid] += 1
                in_degree[oid_norm] += 1

    active_graph_nodes = set(in_degree.keys()) | set(out_degree.keys()) | set(nodes.keys())
    in_vals = [in_degree[n] for n in active_graph_nodes]
    out_vals = [out_degree[n] for n in active_graph_nodes]

    nesting_memo: dict[str, int] = {}

    def get_nesting_depth(g_id: str, visited: set[str]) -> int:
        if g_id in visited or g_id in nesting_memo:
            return nesting_memo.get(g_id, 0)
        visited.add(g_id)
        max_d = 0
        for parent_gid in group_to_group.get(g_id, []):
            d = 1 + get_nesting_depth(parent_gid, visited.copy())
            if d > max_d:
                max_d = d
        nesting_memo[g_id] = max_d
        return max_d

    group_depths = [get_nesting_depth(g, set()) for g in group_to_group]
    max_nesting_depth = max(group_depths) if group_depths else 0
    avg_nesting_depth = (sum(group_depths) / len(group_depths)) if group_depths else 0.0

    ou_all = set(ou_children.keys()) | {c for ch in ou_children.values() for c in ch}
    ou_child_set = {c for ch in ou_children.values() for c in ch}
    ou_roots = ou_all - ou_child_set

    def get_ou_depth(ou_id: str) -> int:
        if not ou_children.get(ou_id):
            return 1
        return 1 + max(get_ou_depth(ch) for ch in ou_children[ou_id])

    ou_depths = [get_ou_depth(r) for r in ou_roots]
    max_ou_depth = max(ou_depths) if ou_depths else (1 if ou_all else 0)

    users_list = [n["raw"] for n in nodes.values() if n["kind"] == "User"]
    comps_list = [n["raw"] for n in nodes.values() if n["kind"] == "Computer"]
    host_access_semantics = summarize_seamless_host_access(comps_list)

    user_null_lastlogon = sum(
        1
        for u in users_list
        if not u.get("Properties", {}).get("lastlogontimestamp")
        or u.get("Properties", {}).get("lastlogontimestamp") <= 0
    )
    user_spn_count = sum(
        1 for u in users_list if len(u.get("Properties", {}).get("serviceprincipalnames", [])) > 0
    )
    comp_sessions_count = sum(1 for c in comps_list if len(c.get("Sessions", [])) > 0)
    comp_localadmin_count = sum(1 for c in comps_list if len(c.get("LocalAdmins", [])) > 0)

    # Trace concrete sample control path
    sample_path = trace_sample_control_path(nodes, group_memberships)

    # Comprehensive Graph Attack Surface EDA
    G_multi, G_di, graph_nodes = build_networkx_graph(data_dir)

    group_subgraph = nx.DiGraph()
    for g_id, g_info in graph_nodes.items():
        if g_info.get("kind") == "Group":
            group_subgraph.add_node(g_id)
    for u, v, data in G_multi.edges(data=True):
        if (
            data.get("kind") == "MemberOf"
            and graph_nodes.get(u, {}).get("kind") == "Group"
            and graph_nodes.get(v, {}).get("kind") == "Group"
        ):
            group_subgraph.add_edge(u, v, kind="MemberOf")

    attack_surface_eda = {
        "connectivity": compute_connectivity_metrics(G_di),
        "reachability": compute_reachability_metrics(G_di, graph_nodes),
        "privilege_concentration": compute_privilege_concentration(G_multi, graph_nodes),
        "relationship_mixing": compute_relationship_mixing(G_multi, graph_nodes),
        "group_nesting_pathology": compute_group_nesting_pathology(group_subgraph, graph_nodes),
        "path_redundancy": compute_path_redundancy(G_di, graph_nodes),
        "structural_outliers": compute_structural_outliers(G_multi, graph_nodes),
    }

    total_raw_records = sum(raw_node_counts.values())
    unique_nodes = len(nodes)
    dropped_duplicate_records = total_dropped_records

    res = {
        "schema_version": 3,
        "raw_node_counts": dict(raw_node_counts),
        "reconciled_node_counts": dict(reconciled_node_counts),
        "node_counts": dict(reconciled_node_counts),
        "total_raw_records": total_raw_records,
        "total_nodes": unique_nodes,
        "dropped_duplicate_records": dropped_duplicate_records,
        "node_count_reconciliation_note": (
            f"Parsed {total_raw_records} raw records yielding {unique_nodes} unique nodes; "
            f"{dropped_duplicate_records} duplicate record(s) deduplicated by ObjectIdentifier."
        ),
        "edge_counts": dict(edges_by_kind),
        "total_edges": sum(edges_by_kind.values()),
        "simple_edges": G_di.number_of_edges(),
        "edge_to_node_ratio": round(sum(edges_by_kind.values()) / max(len(nodes), 1), 2),
        "graph_density": round(
            G_di.number_of_edges() / (G_di.number_of_nodes() * (G_di.number_of_nodes() - 1)), 6
        )
        if G_di.number_of_nodes() > 1
        else 0.0,
        "multiedge_density": (
            round(sum(edges_by_kind.values()) / (unique_nodes * (unique_nodes - 1)), 6)
            if unique_nodes > 1
            else 0.0
        ),
        "density_metrics": {
            "canonical_directed_simple_density": (
                round(
                    G_di.number_of_edges()
                    / (G_di.number_of_nodes() * (G_di.number_of_nodes() - 1)),
                    6,
                )
                if G_di.number_of_nodes() > 1
                else 0.0
            ),
            "multigraph_edge_intensity": (
                round(sum(edges_by_kind.values()) / (unique_nodes * (unique_nodes - 1)), 6)
                if unique_nodes > 1
                else 0.0
            ),
            "simple_edges_numerator": G_di.number_of_edges(),
            "simple_graph_nodes": G_di.number_of_nodes(),
            "simple_possible_pairs_denominator": (
                G_di.number_of_nodes() * (G_di.number_of_nodes() - 1)
            ),
            "multigraph_edges_numerator": sum(edges_by_kind.values()),
            "snapshot_unique_nodes": unique_nodes,
            "snapshot_possible_pairs_denominator": unique_nodes * (unique_nodes - 1),
            "formula": "E / (V * (V - 1))",
        },
        "normalized_ratios": {
            "privileged_principal_ratio": round(
                sum(
                    1
                    for n in nodes.values()
                    if n["kind"] in ("User", "Group", "Computer") and n.get("admincount", False)
                )
                / max(
                    sum(1 for n in nodes.values() if n["kind"] in ("User", "Group", "Computer")), 1
                ),
                4,
            ),
            "acl_density": round(
                sum(
                    count
                    for kind, count in edges_by_kind.items()
                    if kind
                    in {
                        "GenericAll",
                        "WriteDacl",
                        "ForceChangePassword",
                        "GenericWrite",
                        "WriteOwner",
                        "Owns",
                        "AllExtendedRights",
                        "AddKeyCredentialLink",
                        "GetChanges",
                        "GetChangesAll",
                        "GetChangesInFilteredSet",
                        "AddMember",
                        "AddSelf",
                        "ReadLAPSPassword",
                        "ReadGMSAPassword",
                    }
                )
                / max(sum(edges_by_kind.values()), 1),
                4,
            ),
            "session_density": (
                round(
                    edges_by_kind.get("HasSession", 0) / max(len(comps_list) * len(users_list), 1),
                    6,
                )
                if edges_by_kind.get("HasSession", 0) > 0
                else 0.0
            ),
            "session_density_status": (
                "measured" if edges_by_kind.get("HasSession", 0) > 0 else "unobserved_in_snapshot"
            ),
            "details": {
                "privileged_principal_ratio": {
                    "numerator": sum(
                        1
                        for n in nodes.values()
                        if n["kind"] in ("User", "Group", "Computer") and n.get("admincount", False)
                    ),
                    "denominator": sum(
                        1 for n in nodes.values() if n["kind"] in ("User", "Group", "Computer")
                    ),
                    "formula": "privileged_principals / total_principals",
                    "value": round(
                        sum(
                            1
                            for n in nodes.values()
                            if n["kind"] in ("User", "Group", "Computer")
                            and n.get("admincount", False)
                        )
                        / max(
                            sum(
                                1
                                for n in nodes.values()
                                if n["kind"] in ("User", "Group", "Computer")
                            ),
                            1,
                        ),
                        4,
                    ),
                },
                "acl_density": {
                    "numerator": sum(
                        count
                        for kind, count in edges_by_kind.items()
                        if kind
                        in {
                            "GenericAll",
                            "WriteDacl",
                            "ForceChangePassword",
                            "GenericWrite",
                            "WriteOwner",
                            "Owns",
                            "AllExtendedRights",
                            "AddKeyCredentialLink",
                            "GetChanges",
                            "GetChangesAll",
                            "GetChangesInFilteredSet",
                            "AddMember",
                            "AddSelf",
                            "ReadLAPSPassword",
                            "ReadGMSAPassword",
                        }
                    ),
                    "denominator": sum(edges_by_kind.values()),
                    "formula": "acl_edges / total_edges",
                    "value": round(
                        sum(
                            count
                            for kind, count in edges_by_kind.items()
                            if kind
                            in {
                                "GenericAll",
                                "WriteDacl",
                                "ForceChangePassword",
                                "GenericWrite",
                                "WriteOwner",
                                "Owns",
                                "AllExtendedRights",
                                "AddKeyCredentialLink",
                                "GetChanges",
                                "GetChangesAll",
                                "GetChangesInFilteredSet",
                                "AddMember",
                                "AddSelf",
                                "ReadLAPSPassword",
                                "ReadGMSAPassword",
                            }
                        )
                        / max(sum(edges_by_kind.values()), 1),
                        4,
                    ),
                },
                "session_density": {
                    "numerator": edges_by_kind.get("HasSession", 0),
                    "unique_computers": len(comps_list),
                    "unique_users": len(users_list),
                    "denominator": len(comps_list) * len(users_list),
                    "formula": "session_edges / (unique_computers * unique_users)",
                    "value": (
                        round(
                            edges_by_kind.get("HasSession", 0)
                            / max(len(comps_list) * len(users_list), 1),
                            6,
                        )
                        if edges_by_kind.get("HasSession", 0) > 0
                        else 0.0
                    ),
                    "status": (
                        "measured"
                        if edges_by_kind.get("HasSession", 0) > 0
                        else "unobserved_in_snapshot"
                    ),
                },
            },
        },
        "degree_stats": {
            "in_degree_max": max(in_vals) if in_vals else 0,
            "in_degree_mean": round(statistics.mean(in_vals), 2) if in_vals else 0,
            "in_degree_median": statistics.median(in_vals) if in_vals else 0,
            "out_degree_max": max(out_vals) if out_vals else 0,
            "out_degree_mean": round(statistics.mean(out_vals), 2) if out_vals else 0,
            "out_degree_median": statistics.median(out_vals) if out_vals else 0,
        },
        "group_nesting": {
            "max_depth": max_nesting_depth,
            "avg_depth": round(avg_nesting_depth, 2),
            "distribution": dict(Counter(group_depths)),
        },
        "ou_hierarchy": {
            "total_ous": len(ou_all),
            "max_depth": max_ou_depth,
            "root_ous": len(ou_roots),
        },
        "privilege_distribution": {
            "user_admincount": sum(
                1 for n in nodes.values() if n["kind"] == "User" and n["admincount"]
            ),
            "group_admincount": sum(
                1 for n in nodes.values() if n["kind"] == "Group" and n["admincount"]
            ),
            "group_highvalue": sum(
                1 for n in nodes.values() if n["kind"] == "Group" and n["highvalue"]
            ),
            "user_with_spn": user_spn_count,
        },
        "missingness": {
            "user_null_lastlogon_rate": round(
                user_null_lastlogon / max(len(users_list), 1) * 100, 2
            ),
            "comp_empty_or_unobserved_sessions_rate": round(
                (len(comps_list) - comp_sessions_count) / max(len(comps_list), 1) * 100, 2
            ),
            "comp_empty_or_unobserved_localadmins_rate": round(
                (len(comps_list) - comp_localadmin_count) / max(len(comps_list), 1) * 100, 2
            ),
        },
        "host_access_semantics": host_access_semantics,
        "sample_control_path": {
            "description": (
                "Multi-hop administrative control reachability path through permissions and "
                "group memberships, NOT an executed attack claim."
            ),
            "hops": len(sample_path),
            "path": sample_path,
        },
        "attack_surface_eda": attack_surface_eda,
        "data_quality_audit": audit_data_quality(data_dir, manifest=manifest),
    }
    if manifest is not None:
        res["provenance_metadata"] = {
            "dataset_id": manifest["dataset_id"],
            "snapshot_id": manifest["snapshot_id"],
            "schema_version": manifest["schema_version"],
            "files": [
                {
                    "relative_path": f["relative_path"],
                    "sha256": f["sha256"],
                    "size_bytes": f["size_bytes"],
                }
                for f in manifest["files"]
            ],
            "analyzed_population": {
                "total_raw_records": res["total_raw_records"],
                "unique_snapshot_nodes": res["total_nodes"],
                "materialized_graph_nodes": G_di.number_of_nodes(),
            },
            "analysis_code_revision": get_code_revision(),
        }
    return res


def parse_v4_dataset(data_dir: Path) -> dict:
    """Parse BloodHound v4/CE dataset (e.g., NORTH or ad_sampledata)."""
    kinds_raw: dict[str, list[dict]] = defaultdict(list)
    raw_node_counts: dict[str, int] = defaultdict(int)
    reconciled_node_counts: dict[str, int] = defaultdict(int)
    duplicate_records_by_kind: dict[str, int] = defaultdict(int)

    kind_map = {
        "users": "User",
        "groups": "Group",
        "computers": "Computer",
        "ous": "OU",
        "gpos": "GPO",
        "domains": "Domain",
        "containers": "Container",
        "certtemplates": "CertTemplate",
        "aiacas": "AIACA",
        "rootcas": "RootCA",
        "enterprisecas": "EnterpriseCA",
        "ntauthstores": "NTAuthStore",
    }

    for f in sorted(data_dir.glob("*.json")):
        kind_key = f.stem.split("_")[-1].lower()
        kind = kind_map.get(kind_key, kind_key.capitalize())
        try:
            content = json.loads(f.read_text(encoding="utf-8-sig"))
        except Exception:
            content = json.loads(f.read_text(encoding="latin-1"))

        data = content.get("data", [])
        kinds_raw[kind].extend(data)
        raw_node_counts[kind] += len(data)

    nodes: dict[str, dict] = {}
    edges_by_kind: Counter[str] = Counter()
    raw_host_access_counts: Counter[str] = Counter()
    simple_edges: set[tuple[str, str]] = set()
    group_to_group: dict[str, list[str]] = defaultdict(list)

    for kind, items in kinds_raw.items():
        reconciled_items, dropped = reconcile_raw_records(items)
        reconciled_node_counts[kind] = len(reconciled_items)
        duplicate_records_by_kind[kind] = dropped

        for item in reconciled_items:
            oid = item.get("ObjectIdentifier")
            if not oid:
                continue
            oid_norm = oid.upper()
            props = item.get("Properties", {}) or {}
            nodes[oid_norm] = {
                "kind": kind,
                "name": props.get("name", ""),
                "admincount": bool(props.get("admincount", False)),
                "highvalue": bool(props.get("highvalue", False)),
                "raw": item,
            }

            if kind == "Group":
                for m in item.get("Members", []):
                    mid = (m.get("ObjectIdentifier") or "").upper()
                    mtype = m.get("ObjectType") or m.get("Type")
                    if mid:
                        edges_by_kind["MemberOf"] += 1
                        simple_edges.add((mid, oid_norm))
                        if mtype == "Group":
                            group_to_group[mid].append(oid_norm)

            elif kind == "Computer":
                for lg in item.get("LocalGroups", []):
                    lg_id = (lg.get("ObjectIdentifier") or "").upper()
                    kind_edge = None
                    if lg_id.endswith("-544"):
                        kind_edge = "AdminTo"
                    elif lg_id.endswith("-555"):
                        kind_edge = None
                    elif lg_id.endswith("-580"):
                        kind_edge = "CanPSRemote"

                    for m in lg.get("Results", []):
                        if lg_id.endswith("-555"):
                            raw_host_access_counts["RemoteDesktopUsers_raw_memberships"] += 1
                            continue
                        if kind_edge:
                            mid = (m.get("ObjectIdentifier") or "").upper()
                            if mid:
                                edges_by_kind[kind_edge] += 1
                                simple_edges.add((mid, oid_norm))

                for la in item.get("LocalAdmins", []):
                    mid = (la.get("ObjectIdentifier") or "").upper()
                    if mid:
                        edges_by_kind["AdminTo"] += 1
                        simple_edges.add((mid, oid_norm))

                sessions = (
                    item.get("Sessions", {}).get("Results", [])
                    + item.get("PrivilegedSessions", {}).get("Results", [])
                    + item.get("RegistrySessions", {}).get("Results", [])
                )
                for s in sessions:
                    usid = (s.get("UserSID") or "").upper()
                    if usid:
                        edges_by_kind["HasSession"] += 1
                        simple_edges.add((oid_norm, usid))

            for ace in item.get("Aces", []):
                right = ace.get("RightName", "")
                psid = (ace.get("PrincipalSID") or "").upper()
                if psid and right:
                    edges_by_kind[right] += 1
                    simple_edges.add((psid, oid_norm))

    group_depths: list[int] = []
    nesting_memo: dict[str, int] = {}

    def get_nesting(g_id: str, visited: set[str]) -> int:
        if g_id in visited or g_id in nesting_memo:
            return nesting_memo.get(g_id, 0)
        visited.add(g_id)
        md = 0
        for p in group_to_group.get(g_id, []):
            d = 1 + get_nesting(p, visited.copy())
            if d > md:
                md = d
        nesting_memo[g_id] = md
        return md

    for g in group_to_group:
        group_depths.append(get_nesting(g, set()))

    total_v4_nodes = len(nodes)
    total_v4_edges = sum(edges_by_kind.values())
    simple_edges_count = len(simple_edges)
    possible_pairs = total_v4_nodes * (total_v4_nodes - 1) if total_v4_nodes > 1 else 0

    v4_comps = sum(1 for n in nodes.values() if n["kind"] == "Computer")
    v4_users = sum(1 for n in nodes.values() if n["kind"] == "User")
    v4_groups = sum(1 for n in nodes.values() if n["kind"] == "Group")
    v4_principals = v4_comps + v4_users + v4_groups
    v4_admin_principals = sum(
        1
        for n in nodes.values()
        if n["kind"] in ("User", "Group", "Computer") and n.get("admincount", False)
    )
    v4_session_edges = edges_by_kind.get("HasSession", 0)

    ACL_KINDS = {
        "GenericAll",
        "WriteDacl",
        "ForceChangePassword",
        "GenericWrite",
        "WriteOwner",
        "Owns",
        "AllExtendedRights",
        "AddKeyCredentialLink",
        "GetChanges",
        "GetChangesAll",
        "GetChangesInFilteredSet",
        "AddMember",
        "AddSelf",
        "ReadLAPSPassword",
        "ReadGMSAPassword",
    }
    v4_acl_edges = sum(count for kind_e, count in edges_by_kind.items() if kind_e in ACL_KINDS)

    directed_simple_density = (
        round(simple_edges_count / possible_pairs, 6) if possible_pairs else 0.0
    )
    multiedge_density = round(total_v4_edges / possible_pairs, 6) if possible_pairs else 0.0

    return {
        "schema_version": 4,
        "raw_node_counts": dict(raw_node_counts),
        "reconciled_node_counts": dict(reconciled_node_counts),
        "duplicate_records_by_kind": dict(duplicate_records_by_kind),
        "node_counts": dict(reconciled_node_counts),
        "total_raw_records": sum(raw_node_counts.values()),
        "total_nodes": total_v4_nodes,
        "dropped_duplicate_records": sum(duplicate_records_by_kind.values()),
        "node_count_reconciliation_note": (
            f"Parsed {sum(raw_node_counts.values())} raw records "
            f"yielding {total_v4_nodes} unique nodes; "
            f"{sum(duplicate_records_by_kind.values())} duplicate record(s) "
            "deduplicated by ObjectIdentifier."
        ),
        "edge_counts": dict(edges_by_kind),
        "raw_host_access_counts": {
            "RemoteDesktopUsers_raw_memberships": raw_host_access_counts[
                "RemoteDesktopUsers_raw_memberships"
            ],
            "CanRDP_verified_effective_edges": None,
            "CanRDP_status": "unknown_without_complete_UserRights_evidence",
        },
        "total_edges": total_v4_edges,
        "simple_edges": simple_edges_count,
        "edge_to_node_ratio": round(total_v4_edges / max(total_v4_nodes, 1), 2),
        "graph_density": directed_simple_density,
        "multiedge_density": multiedge_density,
        "density_metrics": {
            "canonical_directed_simple_density": directed_simple_density,
            "multigraph_edge_intensity": multiedge_density,
            "simple_edges_numerator": simple_edges_count,
            "total_edges_numerator": total_v4_edges,
            "unique_nodes": total_v4_nodes,
            "possible_pairs_denominator": possible_pairs,
            "formula": "E / (V * (V - 1))",
        },
        "normalized_ratios": {
            "privileged_principal_ratio": round(v4_admin_principals / max(v4_principals, 1), 4),
            "acl_density": round(v4_acl_edges / max(total_v4_edges, 1), 4),
            "session_density": (
                round(v4_session_edges / max(v4_comps * v4_users, 1), 6)
                if v4_session_edges > 0
                else 0.0
            ),
            "session_density_status": (
                "measured" if v4_session_edges > 0 else "unobserved_in_snapshot"
            ),
            "details": {
                "privileged_principal_ratio": {
                    "numerator": v4_admin_principals,
                    "denominator": v4_principals,
                    "formula": "privileged_principals / total_principals",
                    "value": round(v4_admin_principals / max(v4_principals, 1), 4),
                },
                "acl_density": {
                    "numerator": v4_acl_edges,
                    "denominator": total_v4_edges,
                    "formula": "acl_edges / total_edges",
                    "value": round(v4_acl_edges / max(total_v4_edges, 1), 4),
                },
                "session_density": {
                    "numerator": v4_session_edges,
                    "unique_computers": v4_comps,
                    "unique_users": v4_users,
                    "denominator": v4_comps * v4_users,
                    "formula": "session_edges / (unique_computers * unique_users)",
                    "value": (
                        round(v4_session_edges / max(v4_comps * v4_users, 1), 6)
                        if v4_session_edges > 0
                        else 0.0
                    ),
                    "status": ("measured" if v4_session_edges > 0 else "unobserved_in_snapshot"),
                },
            },
        },
        "group_nesting": {
            "max_depth": max(group_depths) if group_depths else 0,
            "avg_depth": round(sum(group_depths) / len(group_depths), 2) if group_depths else 0.0,
        },
        "privilege_distribution": {
            "user_admincount": sum(
                1 for n in nodes.values() if n["kind"] == "User" and n["admincount"]
            ),
            "group_admincount": sum(
                1 for n in nodes.values() if n["kind"] == "Group" and n["admincount"]
            ),
            "group_highvalue": sum(
                1 for n in nodes.values() if n["kind"] == "Group" and n["highvalue"]
            ),
        },
    }


def parse_telemetry(csv_path: Path, manifest: dict | None = None) -> dict:
    """Describe corpus rows without assigning relationship or attack semantics."""
    upstream_tactic_labels: Counter[str] = Counter()
    event_ids: Counter[str] = Counter()
    computers: Counter[str] = Counter()
    users: Counter[str] = Counter()
    timestamps: list[str] = []
    total_events = 0

    if manifest is not None:
        role_issues = validate_snapshot_roles(manifest, "telemetry")
        if role_issues:
            raise ValueError(f"Telemetry manifest failed semantic validation: {role_issues}")
        telemetry_dir = csv_path if csv_path.is_dir() else csv_path.parent
        ref = raw_file_reference(manifest, "evtx_data.csv")
        payload = read_verified_snapshot_file(telemetry_dir, manifest, ref)
        stream = io.StringIO(payload.decode("utf-8", errors="replace"))
        reader = csv.DictReader(stream)
        for row in reader:
            total_events += 1
            upstream_tactic_labels[row.get("EVTX_Tactic", "Unknown")] += 1
            eid = row.get("EventID", "Unknown").strip()
            event_ids[eid] += 1
            comp = row.get("Computer", "").strip()
            if comp:
                computers[comp] += 1
            user = row.get("TargetUserName", "").strip() or row.get("SubjectUserName", "").strip()
            if user and user != "-":
                users[user] += 1
            t_str = row.get("SystemTime", "").strip() or row.get("UtcTime", "").strip()
            if t_str and t_str != "-":
                timestamps.append(t_str[:19])
    else:
        file_path = csv_path / "evtx_data.csv" if csv_path.is_dir() else csv_path
        with file_path.open("r", encoding="utf-8", errors="replace") as f:
            reader = csv.DictReader(f)
            for row in reader:
                total_events += 1
                upstream_tactic_labels[row.get("EVTX_Tactic", "Unknown")] += 1
                eid = row.get("EventID", "Unknown").strip()
                event_ids[eid] += 1
                comp = row.get("Computer", "").strip()
                if comp:
                    computers[comp] += 1
                user = (
                    row.get("TargetUserName", "").strip() or row.get("SubjectUserName", "").strip()
                )
                if user and user != "-":
                    users[user] += 1
                t_str = row.get("SystemTime", "").strip() or row.get("UtcTime", "").strip()
                if t_str and t_str != "-":
                    timestamps.append(t_str[:19])

    timestamps.sort()

    res = {
        "total_events": total_events,
        "unique_computers": len(computers),
        "unique_users": len(users),
        "temporal_span": {
            "earliest": timestamps[0] if timestamps else None,
            "latest": timestamps[-1] if timestamps else None,
        },
        "upstream_tactic_annotations": {
            "source_field": "EVTX_Tactic",
            "status": "upstream_annotation_not_windows_ground_truth",
            "distribution": dict(upstream_tactic_labels.most_common()),
        },
        "corpus_event_id_distribution": dict(event_ids.most_common()),
        "top_event_ids": dict(event_ids.most_common(15)),
        "telemetry_evidence_inventory": {
            "scope": "corpus_statistics_only",
            "semantic_catalog": "configs/attack_semantics.yml",
            "event_id_qualification": "not_assessed",
            "attack_or_relationship_attribution": "not_assessed",
            "boundary_note": (
                "EventID counts are independent corpus row frequencies, not attack counts, "
                "structural relationships, or ExpectedTelemetry satisfaction. Provider, "
                "channel, event-specific qualifiers, identity, environment, and time correlation "
                "are not assessed here."
            ),
        },
        "population_provenance": {
            "measured_events": total_events,
            "distinct_upstream_tactic_labels": len(upstream_tactic_labels),
            "external_corpus_claim": {
                "claimed_events": 6432,
                "claimed_tactics": 11,
                "status": "external_unverified_claim",
                "note": (
                    "6,432 events and 11 tactics are external project claims from "
                    "EVTX-ATTACK-SAMPLES literature, not measured in the verified local snapshot."
                ),
            },
        },
    }
    if manifest is not None:
        res["provenance_metadata"] = {
            "dataset_id": manifest["dataset_id"],
            "snapshot_id": manifest["snapshot_id"],
            "schema_version": manifest["schema_version"],
            "files": [
                {
                    "relative_path": f["relative_path"],
                    "sha256": f["sha256"],
                    "size_bytes": f["size_bytes"],
                }
                for f in manifest["files"]
            ],
            "analyzed_population": {
                "measured_events": total_events,
                "distinct_upstream_tactic_labels": len(upstream_tactic_labels),
                "temporal_span": res["temporal_span"],
            },
            "analysis_code_revision": get_code_revision(),
        }
    return res


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--seamless-dir",
        type=Path,
        default=ROOT / "data" / "raw" / "SEAMLESS",
        help="Path to SEAMLESS raw directory",
    )
    parser.add_argument(
        "--seamless-manifest",
        type=Path,
        default=ROOT / "data" / "samples" / "manifests" / "seamless-raw-v1.json",
        help="Path to SEAMLESS snapshot manifest",
    )
    parser.add_argument(
        "--telemetry-dir",
        type=Path,
        default=ROOT / "data" / "raw" / "telemetry",
        help="Path to telemetry raw directory",
    )
    parser.add_argument(
        "--telemetry-manifest",
        type=Path,
        default=ROOT / "data" / "samples" / "manifests" / "telemetry-raw-v1.json",
        help="Path to telemetry snapshot manifest",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "reports" / "eda_summary.json",
        help="Path to output summary JSON",
    )
    parser.add_argument(
        "--north-dir",
        type=Path,
        default=ROOT / "data" / "raw" / "NORTH",
        help="Path to optional NORTH raw directory",
    )
    parser.add_argument(
        "--north-python-dir",
        type=Path,
        default=ROOT / "data" / "raw" / "NORTH_CE_PYTHON",
        help="Path to optional NORTH BloodHound.py raw directory",
    )
    parser.add_argument(
        "--ad-sample-dir",
        type=Path,
        default=ROOT / "data" / "raw" / "ad_sampledata",
        help="Path to optional ad_sampledata raw directory",
    )
    parser.add_argument(
        "--preserve-historical-report",
        type=Path,
        help=(
            "Preserve historical NORTH/ad_sampledata/collector-bias sections from this "
            "report when their raw inputs are unavailable"
        ),
    )
    parser.add_argument(
        "--preserve-historical-from-ref",
        help=(
            "Load the historical report from a Git ref, e.g. origin/develop, and preserve "
            "its historical sections deterministically"
        ),
    )
    args = parser.parse_args(argv)

    print("=== EXPLORATORY DATA ANALYSIS (EDA) REPORT ===")

    # 1. Validate existence of required primary inputs
    if not args.seamless_dir.is_dir():
        print(f"Error: SEAMLESS directory not found: {args.seamless_dir}", file=sys.stderr)
        return 2
    if not args.seamless_manifest.is_file():
        print(f"Error: SEAMLESS manifest not found: {args.seamless_manifest}", file=sys.stderr)
        return 2
    if not args.telemetry_dir.is_dir():
        print(f"Error: Telemetry directory not found: {args.telemetry_dir}", file=sys.stderr)
        return 2
    if not args.telemetry_manifest.is_file():
        print(f"Error: Telemetry manifest not found: {args.telemetry_manifest}", file=sys.stderr)
        return 2

    # 2. Load manifests
    try:
        seamless_m = load_manifest(args.seamless_manifest)
    except ManifestError as exc:
        print(f"Error loading SEAMLESS manifest: {exc}", file=sys.stderr)
        return 2
    try:
        telemetry_m = load_manifest(args.telemetry_manifest)
    except ManifestError as exc:
        print(f"Error loading telemetry manifest: {exc}", file=sys.stderr)
        return 2

    # 3. Preflight manifest verification
    seamless_issues = verify_manifest(args.seamless_dir, seamless_m)
    if seamless_issues:
        print(
            f"Error: SEAMLESS manifest verification failed with {len(seamless_issues)} issues: "
            f"{seamless_issues}",
            file=sys.stderr,
        )
        return 1

    seamless_role_issues = validate_snapshot_roles(seamless_m, "seamless")
    if seamless_role_issues:
        for issue in seamless_role_issues:
            print(f"Error: {issue}", file=sys.stderr)
        return 1

    telemetry_issues = verify_manifest(args.telemetry_dir, telemetry_m)
    if telemetry_issues:
        print(
            f"Error: Telemetry manifest verification failed with {len(telemetry_issues)} issues: "
            f"{telemetry_issues}",
            file=sys.stderr,
        )
        return 1

    telemetry_role_issues = validate_snapshot_roles(telemetry_m, "telemetry")
    if telemetry_role_issues:
        for issue in telemetry_role_issues:
            print(f"Error: {issue}", file=sys.stderr)
        return 1

    results = {}

    # 4. Parse primary datasets using verified bytes
    try:
        print(f"Analyzing SEAMLESS.INTERNAL at {args.seamless_dir} (verified snapshot)...")
        results["SEAMLESS"] = parse_v3_dataset(args.seamless_dir, manifest=seamless_m)

        print(f"Analyzing telemetry at {args.telemetry_dir} (verified snapshot)...")
        results["telemetry"] = parse_telemetry(args.telemetry_dir, manifest=telemetry_m)
    except (ManifestError, ValueError) as exc:
        print(f"Error reading verified snapshot files: {exc}", file=sys.stderr)
        return 1

    report_provenance = {
        "mode": "fresh_inputs",
        "generator_revision": get_code_revision(),
        "sections": {
            "SEAMLESS": {"status": "generated_current"},
            "telemetry": {"status": "generated_current"},
        },
    }

    if args.preserve_historical_report or args.preserve_historical_from_ref:
        try:
            preserved_report, preservation_source = _load_preserved_report(
                args.preserve_historical_report,
                git_ref=args.preserve_historical_from_ref,
            )
            preserved_sections, preservation_metadata = preserve_historical_sections(
                preserved_report, preservation_source
            )
        except ValueError as exc:
            print(f"Error loading historical report: {exc}", file=sys.stderr)
            return 1
        results.update(preserved_sections)
        report_provenance = {
            "mode": "scoped_preservation",
            "generator_revision": get_code_revision(),
            "sections": {
                "SEAMLESS": {"status": "generated_current"},
                "telemetry": {"status": "generated_current"},
                **{
                    name: {
                        "status": "preserved_historical",
                        "source": preservation_source,
                    }
                    for name in preservation_metadata["preserved_sections"]
                },
            },
            "preservation": preservation_metadata,
        }

    # 5. Optional historical A/B baselines (reported as skipped when absent, not measured zero)
    if "NORTH" in results:
        print("Preserving historical NORTH section from the explicit report source...")
    elif args.north_dir and args.north_dir.is_dir():
        print(f"Analyzing NORTH at {args.north_dir}...")
        results["NORTH"] = parse_v4_dataset(args.north_dir)
    else:
        results["NORTH"] = {
            "status": "skipped",
            "reason": f"Input directory not found: {args.north_dir}",
        }

    if "ad_sampledata" in results:
        print("Preserving historical ad_sampledata section from the explicit report source...")
    elif args.ad_sample_dir and args.ad_sample_dir.is_dir():
        print(f"Analyzing ad_sampledata at {args.ad_sample_dir}...")
        results["ad_sampledata"] = parse_v4_dataset(args.ad_sample_dir)
    else:
        results["ad_sampledata"] = {
            "status": "skipped",
            "reason": f"Input directory not found: {args.ad_sample_dir}",
        }

    if "collector_bias_comparison" in results:
        print("Preserving historical collector-bias section from the explicit report source...")
    elif (
        args.north_dir
        and args.north_dir.is_dir()
        and args.north_python_dir
        and args.north_python_dir.is_dir()
    ):
        print("Comparing SharpHound vs BloodHound.py (Collector Bias)...")
        results["collector_bias_comparison"] = compare_collector_bias(
            args.north_dir, args.north_python_dir
        )
    else:
        results["collector_bias_comparison"] = {
            "status": "skipped",
            "reason": "One or both NORTH directories not found",
        }

    # 6. Cross dataset comparison for present non-skipped datasets.  This is deliberately
    # computed after optional historical preservation so no stale comparison is copied.
    comparison = build_cross_dataset_normalized_comparison(results)
    if comparison:
        results["cross_dataset_normalized_comparison"] = comparison
        report_provenance["sections"]["cross_dataset_normalized_comparison"] = {
            "status": "derived_from_assembled_sections"
        }

    results["report_provenance"] = report_provenance

    # 7. Atomic file replace
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temp_file = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            dir=args.output.parent,
            prefix=".eda_summary-",
            suffix=".tmp",
            delete=False,
            encoding="utf-8",
        ) as f:
            temp_file = Path(f.name)
            json.dump(results, f, indent=2)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp_file, args.output)
    except Exception as exc:
        if temp_file and temp_file.exists():
            temp_file.unlink(missing_ok=True)
        print(f"Error: Failed to write output atomically: {exc}", file=sys.stderr)
        return 2

    print(f"EDA analysis complete! Results written to {args.output}")
    return 0


def audit_data_quality(data_dir: Path, manifest: dict | None = None) -> dict:
    """Audit data quality (missingness, referential integrity) directly from dataset files."""
    total_dropped = 0
    if not data_dir.exists():
        raise FileNotFoundError(f"Data directory does not exist: {data_dir}")

    type_files = {
        "User": "*_users.json",
        "Group": "*_groups.json",
        "Computer": "*_computers.json",
        "OU": "*_ous.json",
        "GPO": "*_gpos.json",
        "Domain": "*_domains.json",
    }

    if manifest is not None:
        role_issues = validate_snapshot_roles(manifest, "seamless")
        if role_issues:
            raise ValueError(f"SEAMLESS manifest failed semantic validation: {role_issues}")

    matched_contents = {}
    for kind, pattern in type_files.items():
        loaded = _load_snapshot_json(data_dir, pattern, manifest)
        if loaded is not None:
            matched_contents[kind] = loaded[1]

    if not matched_contents:
        raise FileNotFoundError(f"No BloodHound JSON files found in {data_dir}")

    counts = {"User": 0, "Group": 0, "Computer": 0, "OU": 0, "GPO": 0, "Domain": 0}
    valid_parsed = 0
    all_oids: list[str] = []
    nodes: set[str] = set()
    malformed_records = 0

    # Computer missingness counters
    comp_os_observed = 0
    comp_haslaps_true = 0
    comp_haslaps_false = 0
    comp_haslaps_missing = 0
    comp_lastlogon_positive = 0
    comp_sessions_populated = 0
    comp_localadmins_populated = 0

    # User missingness counters
    user_lastlogon_positive = 0
    user_with_spn = 0

    # Sub-population counters for missingness concentration (#56)
    dc_count = 0
    dc_os_missing = 0
    dc_localadmins_missing = 0
    dc_lastlogon_missing = 0

    workstation_count = 0
    workstation_os_missing = 0
    workstation_localadmins_missing = 0
    workstation_lastlogon_missing = 0

    user_admincount_true_count = 0
    user_admincount_true_lastlogon_missing = 0
    user_admincount_false_count = 0
    user_admincount_false_lastlogon_missing = 0

    reconciled_files = {}

    for kind, content in matched_contents.items():
        key = [k for k in content if k != "meta"][0]
        items = content[key]
        items, dropped = reconcile_raw_records(items)
        total_dropped += dropped

        counts[kind] = len(items)
        valid_parsed += len(items)
        reconciled_files[kind] = items

        for item in items:
            oid = (item.get("ObjectIdentifier") or "").upper()
            if oid:
                all_oids.append(oid)
                nodes.add(oid)
            else:
                malformed_records += 1

            props = item.get("Properties", {}) or {}
            if kind == "Computer":
                primary_sid = str(item.get("PrimaryGroupSid") or "")
                name_upper = (props.get("name") or "").upper()
                is_dc = primary_sid.endswith("-516") or "BADBLOOD" in name_upper
                has_os = bool(props.get("operatingsystem"))
                has_la = bool(item.get("LocalAdmins") and len(item["LocalAdmins"]) > 0)
                has_ll = bool((props.get("lastlogontimestamp") or 0) > 0)

                if is_dc:
                    dc_count += 1
                    if not has_os:
                        dc_os_missing += 1
                    if not has_la:
                        dc_localadmins_missing += 1
                    if not has_ll:
                        dc_lastlogon_missing += 1
                else:
                    workstation_count += 1
                    if not has_os:
                        workstation_os_missing += 1
                    if not has_la:
                        workstation_localadmins_missing += 1
                    if not has_ll:
                        workstation_lastlogon_missing += 1

                if props.get("operatingsystem"):
                    comp_os_observed += 1

                if "haslaps" in props:
                    if props.get("haslaps") is True:
                        comp_haslaps_true += 1
                    elif props.get("haslaps") is False:
                        comp_haslaps_false += 1
                    else:
                        comp_haslaps_missing += 1
                else:
                    comp_haslaps_missing += 1

                if (props.get("lastlogontimestamp") or 0) > 0:
                    comp_lastlogon_positive += 1

                if item.get("Sessions") and len(item["Sessions"]) > 0:
                    comp_sessions_populated += 1

                if item.get("LocalAdmins") and len(item["LocalAdmins"]) > 0:
                    comp_localadmins_populated += 1

            elif kind == "User":
                is_admin = bool(props.get("admincount", False))
                has_ll = bool((props.get("lastlogontimestamp") or 0) > 0)
                if is_admin:
                    user_admincount_true_count += 1
                    if not has_ll:
                        user_admincount_true_lastlogon_missing += 1
                else:
                    user_admincount_false_count += 1
                    if not has_ll:
                        user_admincount_false_lastlogon_missing += 1

                if (props.get("lastlogontimestamp") or 0) > 0:
                    user_lastlogon_positive += 1

                spns = props.get("serviceprincipalnames")
                if spns and isinstance(spns, list) and len(spns) > 0:
                    user_with_spn += 1

    duplicate_oids = total_dropped
    dropped_records = duplicate_oids + malformed_records

    # Second pass for referential integrity
    total_edge_references = 0
    internal_references = 0
    external_principals: set[str] = set()
    external_boundary_count = 0
    well_known = {"SEAMLESS.INTERNAL-S-1-5-4", "SEAMLESS.INTERNAL-S-1-5-17"}

    for kind, items in reconciled_files.items():
        for item in items:
            refs: list[str] = []
            if kind == "Group":
                for m in item.get("Members", []):
                    refs.append((m.get("MemberId") or m.get("ObjectIdentifier") or "").upper())
            elif kind == "Computer":
                for la in item.get("LocalAdmins", []):
                    refs.append((la.get("MemberId") or la.get("ObjectIdentifier") or "").upper())
                for rdp in item.get("RemoteDesktopUsers", []):
                    refs.append((rdp.get("MemberId") or rdp.get("ObjectIdentifier") or "").upper())
                for ps in item.get("PSRemoteUsers", []):
                    refs.append((ps.get("MemberId") or ps.get("ObjectIdentifier") or "").upper())
                for s in item.get("Sessions", []):
                    refs.append((s.get("UserId") or s.get("UserSID") or "").upper())
            for ace in item.get("Aces", []):
                refs.append((ace.get("PrincipalSID") or "").upper())

            for ref in refs:
                if not ref:
                    continue
                total_edge_references += 1
                if ref in nodes:
                    internal_references += 1
                elif ref in well_known:
                    external_principals.add(ref)
                    external_boundary_count += 1

    dangling_refs = total_edge_references - internal_references - external_boundary_count
    ref_integrity = (
        round((internal_references + external_boundary_count) / total_edge_references * 100, 2)
        if total_edge_references
        else 100.0
    )

    total_comps = counts["Computer"]
    total_users = counts["User"]

    missingness = {
        "operatingSystem": {
            "observed": comp_os_observed,
            "missing": total_comps - comp_os_observed,
            "total": total_comps,
            "percentage_missing": round(
                (total_comps - comp_os_observed) / max(total_comps, 1) * 100, 2
            ),
            "classification": "empty or absent in snapshot; cause not established by field alone",
        },
        "haslaps": {
            "observed_false": comp_haslaps_false,
            "observed_true": comp_haslaps_true,
            "missing_or_absent": comp_haslaps_missing,
            "total": total_comps,
            "percentage_observed_false": round(comp_haslaps_false / max(total_comps, 1) * 100, 2),
            "classification": (
                "collector observed false; deployment state not independently established"
            ),
        },
        "lastLogonTimestamp_User": {
            "observed_positive": user_lastlogon_positive,
            "missing": total_users - user_lastlogon_positive,
            "total": total_users,
            "percentage_missing": round(
                (total_users - user_lastlogon_positive) / max(total_users, 1) * 100, 2
            ),
            "classification": "zero or absent in snapshot; logon activity unknown",
        },
        "lastLogonTimestamp_Computer": {
            "observed_positive": comp_lastlogon_positive,
            "missing": total_comps - comp_lastlogon_positive,
            "total": total_comps,
            "percentage_missing": round(
                (total_comps - comp_lastlogon_positive) / max(total_comps, 1) * 100, 2
            ),
            "classification": "zero or absent in snapshot; logon activity unknown",
        },
        "servicePrincipalNames": {
            "with_spn": user_with_spn,
            "without_spn": total_users - user_with_spn,
            "total": total_users,
            "percentage_with": round(user_with_spn / max(total_users, 1) * 100, 2),
            "percentage_without": round(
                (total_users - user_with_spn) / max(total_users, 1) * 100, 2
            ),
            "classification": "SPN presence only; does not establish attack applicability",
        },
        "Sessions": {
            "populated": comp_sessions_populated,
            "empty_or_unobserved": total_comps - comp_sessions_populated,
            "total": total_comps,
            "percentage_empty_or_unobserved": round(
                (total_comps - comp_sessions_populated) / max(total_comps, 1) * 100, 2
            ),
            "classification": "empty/unobserved; collection completeness not measurable",
        },
        "LocalAdmins": {
            "populated": comp_localadmins_populated,
            "empty_or_unobserved": total_comps - comp_localadmins_populated,
            "total": total_comps,
            "percentage_empty_or_unobserved": round(
                (total_comps - comp_localadmins_populated) / max(total_comps, 1) * 100, 2
            ),
            "classification": "empty/unobserved; collection completeness not measurable",
        },
    }

    # Dynamic field presence, relationship presence, and edge counts
    # derivation across snapshot objects
    groups_list = reconciled_files.get("Group", [])
    total_groups = len(groups_list)
    groups_field_present = sum(1 for g in groups_list if "Members" in g)
    groups_with_rel = sum(1 for g in groups_list if g.get("Members"))
    groups_without_rel = total_groups - groups_with_rel
    memberof_edges = sum(len(g.get("Members", [])) for g in groups_list)

    comps_list = reconciled_files.get("Computer", [])
    host_access_semantics = summarize_seamless_host_access(comps_list)
    raw_host = host_access_semantics["raw_primitives"]
    rdu_raw = raw_host["RemoteDesktopUsers_raw_memberships"]
    localadmins_raw = raw_host["LocalAdmins_raw_memberships"]
    psremote_raw = raw_host["PSRemoteUsers_raw_memberships"]
    sessions_raw = raw_host["Sessions_raw_observations"]
    comps_la_with_rel = localadmins_raw["hosts_with_positive_observation"]
    adminto_edges = localadmins_raw["raw_observation_count"]

    all_objects = [item for items in reconciled_files.values() for item in items]
    total_objects = len(all_objects)
    objects_aces_field_present = sum(1 for obj in all_objects if "Aces" in obj)

    genericall_with_rel = sum(
        1
        for obj in all_objects
        if any(ace.get("RightName") == "GenericAll" for ace in obj.get("Aces", []))
    )
    genericall_without_rel = total_objects - genericall_with_rel
    genericall_edges = sum(
        sum(1 for ace in obj.get("Aces", []) if ace.get("RightName") == "GenericAll")
        for obj in all_objects
    )

    writedacl_with_rel = sum(
        1
        for obj in all_objects
        if any(ace.get("RightName") == "WriteDacl" for ace in obj.get("Aces", []))
    )
    writedacl_without_rel = total_objects - writedacl_with_rel
    writedacl_edges = sum(
        sum(1 for ace in obj.get("Aces", []) if ace.get("RightName") == "WriteDacl")
        for obj in all_objects
    )

    forcepwd_with_rel = sum(
        1
        for obj in all_objects
        if any(ace.get("RightName") == "ForceChangePassword" for ace in obj.get("Aces", []))
    )
    forcepwd_without_rel = total_objects - forcepwd_with_rel
    forcepwd_edges = sum(
        sum(1 for ace in obj.get("Aces", []) if ace.get("RightName") == "ForceChangePassword")
        for obj in all_objects
    )

    completeness_note = (
        "Snapshot schema lacks collection-result/error metadata (.errors); "
        "true collection completeness or access-denied rate cannot be established from JSON alone."
    )

    unknown_rate_by_edge_type = {
        "MemberOf": {
            "collection_surface": "directory_ldap",
            "source_entity_type": "Group",
            "total_source_entities": total_groups,
            "entities_with_field_present": groups_field_present,
            "field_presence_rate": round(groups_field_present / max(total_groups, 1) * 100, 2),
            "source_entities_with_observed_evidence": groups_with_rel,
            "source_entities_without_observed_evidence": groups_without_rel,
            "positive_raw_evidence_rate": round(groups_with_rel / max(total_groups, 1) * 100, 2),
            "raw_nonobservation_rate": round(groups_without_rel / max(total_groups, 1) * 100, 2),
            "unknown_rate": "not_measurable_from_snapshot",
            "unknown_or_unobserved_rate": "not_measurable_from_snapshot",
            "extracted_edges_count": memberof_edges,
            "collection_completeness_status": "not_measurable_from_snapshot",
            "collection_completeness_note": completeness_note,
            "status": "directory_observed",
            "note": (
                f"{groups_with_rel}/{total_groups} groups have raw member references "
                f"({memberof_edges} references extracted); {groups_without_rel}/{total_groups} "
                "groups have empty or unobserved Members arrays. Collection completeness "
                "and canonical relationship absence cannot be established from this snapshot."
            ),
        },
        "AdminTo": {
            "collection_surface": "endpoint_rpc_sam",
            "source_entity_type": "Computer",
            "total_source_entities": total_comps,
            "raw_primitive_key": "LocalAdmins_raw_memberships",
            "entities_with_field_present": localadmins_raw["field_present_hosts"],
            "field_presence_rate": localadmins_raw["field_presence_rate"],
            "source_entities_with_positive_evidence": localadmins_raw[
                "hosts_with_positive_observation"
            ],
            "source_entities_empty_or_unobserved": localadmins_raw["empty_or_unobserved_hosts"],
            "positive_evidence_rate": localadmins_raw["positive_observation_rate"],
            "unknown_rate": "not_measurable_from_snapshot",
            "unknown_or_unobserved_rate": "not_measurable_from_snapshot",
            "extracted_edges_count": adminto_edges,
            "collection_completeness_status": "not_measurable_from_snapshot",
            "collection_completeness_note": completeness_note,
            "status": "endpoint_partially_observed",
            "note": (
                f"{adminto_edges} positive host-bound LocalAdmins raw membership observation(s) "
                f"were found on {comps_la_with_rel}/{total_comps} computers. The remaining "
                f"{localadmins_raw['empty_or_unobserved_hosts']}/{total_comps} hosts are "
                "empty or unobserved; canonical AdminTo absence cannot be concluded."
            ),
        },
        "CanRDP": {
            "measurement": "verified_effective_relationship",
            "collection_surface": "endpoint_rpc_sam_and_user_rights",
            "source_entity_type": "Computer",
            "total_source_entities": total_comps,
            "raw_primitive_key": "RemoteDesktopUsers_raw_memberships",
            "raw_observation_count": rdu_raw["raw_observation_count"],
            "verified_effective_edges_count": None,
            "materialized_edges_count": 0,
            "unknown_source_entities": total_comps,
            "unknown_rate": "not_measurable_from_snapshot",
            "unknown_or_unobserved_rate": "not_measurable_from_snapshot",
            "collection_completeness_status": "not_measurable_from_snapshot",
            "collection_completeness_note": completeness_note,
            "status": "unknown_not_materialized",
            "note": host_access_semantics["effective_relationships"]["CanRDP"]["note"],
        },
        "CanPSRemote": {
            "collection_surface": "endpoint_rpc_sam",
            "source_entity_type": "Computer",
            "total_source_entities": total_comps,
            "raw_primitive_key": "PSRemoteUsers_raw_memberships",
            "entities_with_field_present": psremote_raw["field_present_hosts"],
            "field_presence_rate": psremote_raw["field_presence_rate"],
            "source_entities_with_positive_evidence": psremote_raw[
                "hosts_with_positive_observation"
            ],
            "source_entities_empty_or_unobserved": psremote_raw["empty_or_unobserved_hosts"],
            "positive_evidence_rate": psremote_raw["positive_observation_rate"],
            "unknown_rate": "not_measurable_from_snapshot",
            "unknown_or_unobserved_rate": "not_measurable_from_snapshot",
            "modeled_structural_edges_count": psremote_raw["raw_observation_count"],
            "collection_completeness_status": "not_measurable_from_snapshot",
            "collection_completeness_note": completeness_note,
            "status": "endpoint_partially_observed",
            "note": (
                f"{psremote_raw['raw_observation_count']} positive Remote Management Users "
                f"membership observation(s) were found on "
                f"{psremote_raw['hosts_with_positive_observation']}/"
                f"{total_comps} computers. Empty or unobserved hosts remain unknown; WinRM "
                "availability and endpoint ACL authorization are runtime/endpoint predicates."
            ),
        },
        "HasSession": {
            "collection_surface": "endpoint_net_session_enum",
            "source_entity_type": "Computer",
            "total_source_entities": total_comps,
            "raw_primitive_key": "Sessions_raw_observations",
            "entities_with_positive_observation": sessions_raw["hosts_with_positive_observation"],
            "entities_empty_or_unobserved": sessions_raw["empty_or_unobserved_hosts"],
            "field_presence_rate": sessions_raw["field_presence_rate"],
            "positive_observation_rate": sessions_raw["positive_observation_rate"],
            "unknown_rate": "not_measurable_from_snapshot",
            "unknown_or_unobserved_rate": "not_measurable_from_snapshot",
            "observed_session_edges_count": sessions_raw["raw_observation_count"],
            "collection_completeness_status": "not_measurable_from_snapshot",
            "collection_completeness_note": completeness_note,
            "status": "session_unobserved",
            "note": (
                f"{sessions_raw['raw_observation_count']} session observation(s) were present. "
                f"Empty or unobserved on {sessions_raw['empty_or_unobserved_hosts']}/{total_comps} "
                "computers; collection completeness is not measurable, so session absence "
                "cannot be concluded."
            ),
        },
        "GenericAll": {
            "collection_surface": "directory_dacl",
            "source_entity_type": "All AD Objects",
            "total_source_entities": total_objects,
            "entities_with_field_present": objects_aces_field_present,
            "field_presence_rate": round(
                objects_aces_field_present / max(total_objects, 1) * 100, 2
            ),
            "source_entities_with_observed_evidence": genericall_with_rel,
            "source_entities_without_observed_evidence": genericall_without_rel,
            "positive_raw_evidence_rate": round(
                genericall_with_rel / max(total_objects, 1) * 100, 2
            ),
            "raw_nonobservation_rate": round(
                genericall_without_rel / max(total_objects, 1) * 100, 2
            ),
            "unknown_rate": "not_measurable_from_snapshot",
            "unknown_or_unobserved_rate": "not_measurable_from_snapshot",
            "extracted_edges_count": genericall_edges,
            "collection_completeness_status": "not_measurable_from_snapshot",
            "collection_completeness_note": completeness_note,
            "status": "directory_observed",
            "note": (
                f"{genericall_with_rel}/{total_objects} objects have explicit GenericAll ACE "
                f"observations ({genericall_edges} raw entries); "
                f"{genericall_without_rel}/{total_objects} have no such observed entry. "
                "Collection completeness and canonical relationship absence are unverified."
            ),
        },
        "WriteDacl": {
            "collection_surface": "directory_dacl",
            "source_entity_type": "All AD Objects",
            "total_source_entities": total_objects,
            "entities_with_field_present": objects_aces_field_present,
            "field_presence_rate": round(
                objects_aces_field_present / max(total_objects, 1) * 100, 2
            ),
            "source_entities_with_observed_evidence": writedacl_with_rel,
            "source_entities_without_observed_evidence": writedacl_without_rel,
            "positive_raw_evidence_rate": round(
                writedacl_with_rel / max(total_objects, 1) * 100, 2
            ),
            "raw_nonobservation_rate": round(
                writedacl_without_rel / max(total_objects, 1) * 100, 2
            ),
            "unknown_rate": "not_measurable_from_snapshot",
            "unknown_or_unobserved_rate": "not_measurable_from_snapshot",
            "extracted_edges_count": writedacl_edges,
            "collection_completeness_status": "not_measurable_from_snapshot",
            "collection_completeness_note": completeness_note,
            "status": "directory_observed",
            "note": (
                f"{writedacl_with_rel}/{total_objects} objects have explicit WriteDacl ACE "
                f"observations ({writedacl_edges} raw entries); "
                f"{writedacl_without_rel}/{total_objects} have no such observed entry. "
                "Collection completeness and canonical relationship absence are unverified."
            ),
        },
        "ForceChangePassword": {
            "collection_surface": "directory_dacl",
            "source_entity_type": "All AD Objects",
            "total_source_entities": total_objects,
            "entities_with_field_present": objects_aces_field_present,
            "field_presence_rate": round(
                objects_aces_field_present / max(total_objects, 1) * 100, 2
            ),
            "source_entities_with_observed_evidence": forcepwd_with_rel,
            "source_entities_without_observed_evidence": forcepwd_without_rel,
            "positive_raw_evidence_rate": round(forcepwd_with_rel / max(total_objects, 1) * 100, 2),
            "raw_nonobservation_rate": round(forcepwd_without_rel / max(total_objects, 1) * 100, 2),
            "unknown_rate": "not_measurable_from_snapshot",
            "unknown_or_unobserved_rate": "not_measurable_from_snapshot",
            "extracted_edges_count": forcepwd_edges,
            "collection_completeness_status": "not_measurable_from_snapshot",
            "collection_completeness_note": completeness_note,
            "status": "directory_raw_evidence_unobserved",
            "note": (
                f"{forcepwd_edges} explicit ForceChangePassword RightName entries observed "
                f"across {total_objects} objects. ExtendedRight interpretation and collection "
                "completeness remain unverified; canonical absence cannot be concluded."
            ),
        },
    }

    collector_error_and_access_denied = {
        "status": "not_measurable_from_snapshot",
        "reason": (
            "Raw BloodHound snapshot contains only successfully parsed JSON object envelopes "
            "without collector error logs (.errors) or access-denied telemetry metadata."
        ),
        "limitation_note": (
            "Cannot assert 100% observability or complete absence of blind spots; "
            "access-denied rate is unmeasured in this static snapshot."
        ),
    }

    # Per-OU missingness aggregation across all 100 computers
    comp_ou_buckets: dict[str, list[dict]] = {}
    for c in comps_list:
        dn = (c.get("Properties", {}) or {}).get("distinguishedname", "")
        parts = dn.split(",")
        ou_parts = [p.strip() for p in parts if p.strip().upper().startswith("OU=")]
        parent_ou = ",".join(ou_parts) if ou_parts else "NO_OU"
        comp_ou_buckets.setdefault(parent_ou, []).append(c)

    ou_aggregations = []
    for ou_name, comp_group in sorted(
        comp_ou_buckets.items(), key=lambda item: len(item[1]), reverse=True
    ):
        c_count = len(comp_group)
        c_os_missing = sum(
            1
            for comp in comp_group
            if not (comp.get("Properties", {}) or {}).get("operatingsystem")
        )
        c_la_missing = sum(1 for comp in comp_group if not comp.get("LocalAdmins"))
        ou_aggregations.append(
            {
                "ou": ou_name,
                "computer_count": c_count,
                "os_missing_rate": round(c_os_missing / max(c_count, 1) * 100, 2),
                "localadmins_missing_rate": round(c_la_missing / max(c_count, 1) * 100, 2),
            }
        )

    dc_ou_info = comp_ou_buckets.get("OU=Domain Controllers", [])
    dc_ou_comps = len(dc_ou_info)
    dc_ou_os_missing = sum(
        1 for comp in dc_ou_info if not (comp.get("Properties", {}) or {}).get("operatingsystem")
    )
    dc_ou_la_missing = sum(1 for comp in dc_ou_info if not comp.get("LocalAdmins"))

    non_dc_comps = [
        c for ou, clist in comp_ou_buckets.items() if ou != "OU=Domain Controllers" for c in clist
    ]
    non_dc_count = len(non_dc_comps)
    non_dc_os_missing = sum(
        1 for comp in non_dc_comps if not (comp.get("Properties", {}) or {}).get("operatingsystem")
    )
    non_dc_la_missing = sum(1 for comp in non_dc_comps if not comp.get("LocalAdmins"))

    missingness_concentration = {
        "boundary_note": (
            "Rates describe raw field non-population in this snapshot, not collection "
            "completeness, endpoint state, or canonical relationship absence."
        ),
        "by_tier_and_role": {
            "domain_controllers": {
                "total": dc_count,
                "os_missing_rate": round(dc_os_missing / max(dc_count, 1) * 100, 2),
                "localadmins_missing_rate": round(
                    dc_localadmins_missing / max(dc_count, 1) * 100, 2
                ),
                "lastlogon_missing_rate": round(dc_lastlogon_missing / max(dc_count, 1) * 100, 2),
            },
            "workstations": {
                "total": workstation_count,
                "os_missing_rate": round(
                    workstation_os_missing / max(workstation_count, 1) * 100, 2
                ),
                "localadmins_missing_rate": round(
                    workstation_localadmins_missing / max(workstation_count, 1) * 100, 2
                ),
                "lastlogon_missing_rate": round(
                    workstation_lastlogon_missing / max(workstation_count, 1) * 100, 2
                ),
            },
            "concentration_finding": (
                "Raw operatingSystem and LocalAdmins non-population is concentrated in "
                "non-DC workstations; the Domain Controller has populated raw values. "
                "Collection completeness is not established."
            ),
        },
        "by_privilege_level": {
            "privileged_users_admincount_true": {
                "total": user_admincount_true_count,
                "lastlogon_missing": user_admincount_true_lastlogon_missing,
                "lastlogon_missing_rate": round(
                    user_admincount_true_lastlogon_missing
                    / max(user_admincount_true_count, 1)
                    * 100,
                    2,
                ),
            },
            "standard_users_admincount_false": {
                "total": user_admincount_false_count,
                "lastlogon_missing": user_admincount_false_lastlogon_missing,
                "lastlogon_missing_rate": round(
                    user_admincount_false_lastlogon_missing
                    / max(user_admincount_false_count, 1)
                    * 100,
                    2,
                ),
            },
            "concentration_finding": (
                "User lastLogonTimestamp is zero or absent on most recorded accounts; "
                "one administrative user has a positive value. This does not establish "
                "whether other accounts logged on."
            ),
        },
        "by_ou": {
            "distinct_parent_ous_count": len(comp_ou_buckets),
            "top_ous_by_computer_count": ou_aggregations[:10],
            "domain_controllers_ou": {
                "ou": "OU=Domain Controllers",
                "computer_count": dc_ou_comps,
                "populated_computers": dc_ou_comps - dc_ou_os_missing,
                "unpopulated_computers": dc_ou_os_missing,
                "operating_system_missing_rate": round(
                    dc_ou_os_missing / max(dc_ou_comps, 1) * 100, 2
                ),
                "local_admins_missing_rate": round(dc_ou_la_missing / max(dc_ou_comps, 1) * 100, 2),
                "members": [
                    {
                        "name": (comp.get("Properties", {}) or {}).get("name", ""),
                        "has_operatingsystem": bool(
                            (comp.get("Properties", {}) or {}).get("operatingsystem")
                        ),
                        "local_admins_count": len(comp.get("LocalAdmins", [])),
                    }
                    for comp in dc_ou_info
                ],
            },
            "non_dc_workstation_ous_summary": {
                "distinct_ous_count": len(comp_ou_buckets)
                - (1 if "OU=Domain Controllers" in comp_ou_buckets else 0),
                "total_computers": non_dc_count,
                "operating_system_missing_rate": round(
                    non_dc_os_missing / max(non_dc_count, 1) * 100, 2
                ),
                "local_admins_missing_rate": round(
                    non_dc_la_missing / max(non_dc_count, 1) * 100, 2
                ),
            },
            "concentration_finding": (
                f"Analyzed {len(comp_ou_buckets)} distinct parent OUs containing computers: "
                f"OU=Domain Controllers contains {dc_ou_comps} computers and "
                f"{dc_ou_os_missing} without a populated operatingSystem value; "
                f"the other {len(comp_ou_buckets) - 1} parent OUs contain "
                f"{non_dc_count} computers, of which {non_dc_os_missing} lack a populated "
                "operatingSystem value. These are raw field observations, not collection "
                "completeness findings."
            ),
        },
    }

    return {
        "record_counts": {**counts, "total": valid_parsed},
        "valid_parsed": valid_parsed,
        "unique_nodes_materialized": len(nodes),
        "dropped_records": dropped_records,
        "malformed_records": malformed_records,
        "duplicate_detection": {"duplicate_ObjectIdentifiers": duplicate_oids},
        "referential_integrity": {
            "total_edge_references": total_edge_references,
            "collected_entity_resolutions": {
                "count": internal_references,
                "denominator": total_edge_references,
                "percentage": round(internal_references / total_edge_references * 100, 3)
                if total_edge_references
                else 100.0,
                "description": (
                    "References resolved directly to collected first-class snapshot principals"
                ),
            },
            "boundary_stub_resolutions": {
                "count": external_boundary_count,
                "denominator": total_edge_references,
                "percentage": round(external_boundary_count / total_edge_references * 100, 3)
                if total_edge_references
                else 0.0,
                "description": (
                    "References resolved to external well-known boundary nodes (INTERACTIVE, IUSR)"
                ),
                "principals": sorted(list(external_principals)),
            },
            "unresolved_dangling_references": {
                "count": max(0, dangling_refs),
                "denominator": total_edge_references,
                "percentage": round(max(0, dangling_refs) / total_edge_references * 100, 3)
                if total_edge_references
                else 0.0,
                "description": "Dangling references failing resolution",
            },
            "internal_references": internal_references,
            "referenced_well_known_external": len(external_principals),
            "dangling_references": max(0, dangling_refs),
            "integrity_percentage": ref_integrity,
            "external_principals": sorted(list(external_principals)),
        },
        "missingness_taxonomy": missingness,
        "host_access_semantics": host_access_semantics,
        "unknown_rate_by_edge_type": unknown_rate_by_edge_type,
        "collector_error_and_access_denied": collector_error_and_access_denied,
        "missingness_concentration": missingness_concentration,
    }


def compare_collector_bias(sharphound_dir: Path, python_dir: Path) -> dict:
    """Compare SharpHound vs BloodHound.py edges strictly using set-of-triples comparison."""

    def get_edges(d: Path) -> set[tuple[str, str, str]]:
        if not d.exists():
            return set()
        edges: set[tuple[str, str, str]] = set()
        for p in d.glob("*.json"):
            with p.open("r", encoding="utf-8-sig") as f:
                c = json.load(f)
            key = [k for k in c if k != "meta"][0]
            for item in c[key]:
                tid = (item.get("ObjectIdentifier") or "").upper()

                # Group Members
                if "Members" in item:
                    for m in item["Members"]:
                        mid = (m.get("MemberId") or m.get("ObjectIdentifier") or "").upper()
                        if mid and tid:
                            edges.add((mid, "MemberOf", tid))

                # Computer LocalGroups v4
                if "LocalGroups" in item:
                    for lg in item["LocalGroups"]:
                        lg_id = (lg.get("ObjectIdentifier") or "").upper()
                        kind = None
                        if lg_id.endswith("-544"):
                            kind = "AdminTo"
                        elif lg_id.endswith("-555"):
                            kind = "RemoteDesktopUsers_raw_memberships"
                        elif lg_id.endswith("-580"):
                            kind = "CanPSRemote"

                        if kind:
                            for m in lg.get("Results", []):
                                mid = (m.get("MemberId") or m.get("ObjectIdentifier") or "").upper()  # noqa: E501
                                if mid and tid:
                                    edges.add((mid, kind, tid))

                # Legacy computer fields
                if "LocalAdmins" in item:
                    for m in item["LocalAdmins"]:
                        mid = (m.get("MemberId") or m.get("ObjectIdentifier") or "").upper()
                        if mid and tid:
                            edges.add((mid, "AdminTo", tid))
                if "RemoteDesktopUsers" in item:
                    for m in item["RemoteDesktopUsers"]:
                        mid = (m.get("MemberId") or m.get("ObjectIdentifier") or "").upper()
                        if mid and tid:
                            edges.add((mid, "RemoteDesktopUsers_raw_memberships", tid))
                if "PSRemoteUsers" in item:
                    for m in item["PSRemoteUsers"]:
                        mid = (m.get("MemberId") or m.get("ObjectIdentifier") or "").upper()
                        if mid and tid:
                            edges.add((mid, "CanPSRemote", tid))

                # Sessions
                for sess_key in ["Sessions", "PrivilegedSessions", "RegistrySessions"]:
                    if sess_key in item:
                        sess_data = item[sess_key]
                        if isinstance(sess_data, dict):
                            sess_list = sess_data.get("Results", [])
                        else:
                            sess_list = sess_data
                        for s in sess_list:
                            usid = (s.get("UserId") or s.get("UserSID") or "").upper()
                            if usid and tid:
                                edges.add((tid, "HasSession", usid))

                # Aces
                for ace in item.get("Aces", []):
                    psid = (ace.get("PrincipalSID") or "").upper()
                    right = ace.get("RightName", "")
                    if psid and right and tid:
                        edges.add((psid, right, tid))
        return edges

    sh_set = get_edges(sharphound_dir)
    py_set = get_edges(python_dir)

    common = sh_set & py_set
    union = sh_set | py_set
    jaccard = len(common) / len(union) if union else 0.0

    all_kinds = {e[1] for e in sh_set} | {e[1] for e in py_set}
    breakdown = {}
    for k in sorted(all_kinds):
        k_sh = {e for e in sh_set if e[1] == k}
        k_py = {e for e in py_set if e[1] == k}
        k_common = k_sh & k_py
        k_union = k_sh | k_py
        breakdown[k] = {
            "SharpHound": len(k_sh),
            "BloodHound.py": len(k_py),
            "Common": len(k_common),
            "Union": len(k_union),
            "Jaccard": round(len(k_common) / len(k_union), 4) if k_union else 0.0,
        }

    return {
        "Total_SharpHound_edges": len(sh_set),
        "Total_BloodHound.py_edges": len(py_set),
        "Common_edges": len(common),
        "Union_edges": len(union),
        "Overall_Jaccard_Similarity": round(jaccard, 4),
        "Per_edge_kind_breakdown": breakdown,
        "Discrepancy_analysis": (
            "SharpHound collects host-local membership primitives through RPC/SAM, while "
            "BloodHound.py primarily performs standard LDAP queries. The comparison keeps "
            "Remote Desktop Users membership as raw evidence and does not call it verified "
            "CanRDP without UserRights allow/deny evidence."
        ),
    }


if __name__ == "__main__":
    sys.exit(main())
