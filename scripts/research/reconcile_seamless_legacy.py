"""Audit exact #82 observations without overriding the common-semantics comparator gate.

Full sets and raw identities stay in an ignored output directory. The summary
contains counts/digests only. Classifications describe evidenced input/policy
rules; they do not certify live privileges or historical importer operations.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from collections import Counter, defaultdict
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if __package__ in {None, ""}:
    sys.path.insert(0, str(ROOT))

from scripts.check_contract import validate_graph  # noqa: E402
from scripts.reconcile_graph_baseline import (  # noqa: E402
    CONTRACT,
    M1_RELATIONSHIPS,
    eligibility_reasons,
    extract_graph,
    graph_multiplicity,
    load_input_json,
    reconcile_graphs,
    validate_mapping,
)
from scripts.research.export_legacy_reconciliation_baseline import (  # noqa: E402
    BOUNDARY,
    IMAGE,
    digest,
    encoded,
    query,
    raw_mapping,
    read_query_package,
    relationship_rows_for_export,
    require,
    write_json,
)
from src.data.manifest import load_manifest, verify_manifest  # noqa: E402

IMPORTER_DIGEST = "01e969d83e87217318603887c7f5818a82bc044eead26502f0daf78ac55cad3b"


def require_ignored(directory, filenames):
    """Check every resolved destination, including a caller-supplied symlink path."""
    paths = {str((directory / filename).resolve()) for filename in filenames}
    checked = subprocess.run(
        ["git", "check-ignore", "--stdin", "-z"],
        input="\0".join(sorted(paths)) + "\0",
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    require(
        checked.returncode == 0 and set(checked.stdout.rstrip("\0").split("\0")) == paths,
        "every output destination must be git-ignored",
    )


def raw_index(raw_root, manifest, mapping):
    """Index positive raw occurrences by mapped triple, preserving exact array indices."""
    index = defaultdict(list)
    for item in manifest["files"]:
        filename = item["relative_path"]
        data = json.loads((raw_root / filename).read_text(encoding="utf-8-sig"))
        collection = data["meta"]["type"]
        for n, record in enumerate(data[collection]):
            target = mapping[record["ObjectIdentifier"]]
            pointer = f"{filename}#/{collection}/{n}"

            def add(source, kind, rule, suffix, *, target=target, pointer=pointer, **details):
                index[(mapping[source], kind, target)].append(
                    {"rule": rule, "pointer": pointer + suffix, **details}
                )

            for i, member in enumerate(record.get("Members", [])):
                add(member["MemberId"], "MemberOf", "Members", f"/Members/{i}")
            primary = record.get("PrimaryGroupSid")
            if primary is not None:
                index[(target, "MemberOf", mapping[primary])].append(
                    {"rule": "PrimaryGroupSid", "pointer": pointer + "/PrimaryGroupSid"}
                )
            for i, ace in enumerate(record.get("Aces", [])):
                if ace["RightName"] in {"GenericAll", "WriteDacl", "ForceChangePassword"}:
                    add(
                        ace["PrincipalSID"],
                        ace["RightName"],
                        "Aces",
                        f"/Aces/{i}",
                        right_name=ace["RightName"],
                        ace_type=ace.get("AceType"),
                        is_inherited=ace.get("IsInherited"),
                        principal_type=ace["PrincipalType"],
                    )
            if collection == "computers":
                for field, kind in (
                    ("LocalAdmins", "AdminTo"),
                    ("PSRemoteUsers", "CanPSRemote"),
                    ("RemoteDesktopUsers", "CanRDP"),
                ):
                    for i, member in enumerate(record.get(field, [])):
                        add(
                            member["MemberId"],
                            kind,
                            field,
                            f"/{field}/{i}",
                            user_rights_present="UserRights" in record,
                        )
    return dict(index)


def classify_difference(triple, side, raw, project_edges, assessments):
    """Explain only rules supported by exact raw triples and validated project records."""
    source, kind, target = triple
    rules = {r["rule"] for r in raw.get(triple, [])}
    if kind not in M1_RELATIONSHIPS:
        return "out_of_scope"
    if side == "legacy_only" and kind == "MemberOf" and "PrimaryGroupSid" in rules:
        return "primary_group_input_gap"
    if side == "project_only" and kind in {"GenericAll", "WriteDacl"}:
        if source == target and "Aces" in rules:
            return "legacy_self_ace_filter"
    if side == "project_only" and kind == "AdminTo":
        derivation = project_edges.get(triple, {}).get("derivation", {})
        paths = derivation.get("paths", [])
        if derivation.get("kind") == "nested_membership" and paths:
            supported = True
            for path in paths:
                for step in path["steps"]:
                    step_kind = {
                        "effective_membership": "MemberOf",
                        "host_local_membership": "AdminTo",
                    }.get(step["operation"])
                    step_rules = {
                        r["rule"] for r in raw.get((step["source"], step_kind, step["target"]), [])
                    }
                    expected = "Members" if step_kind == "MemberOf" else "LocalAdmins"
                    supported &= step_kind is not None and expected in step_rules
            if supported:
                return "project_nested_admin_materialization"
    if side == "legacy_only" and kind == "CanRDP" and "RemoteDesktopUsers" in rules:
        assessment = assessments.get(triple, {})
        if (
            assessment.get("status") == "unknown"
            and assessment.get("reason") == "required UserRights evidence is incomplete"
            and all(r.get("user_rights_present") is False for r in raw[triple])
        ):
            return "policy_difference_unknown_userrights"
    return "unknown"


def direct_host_view(triples, edges, raw):
    return {
        t
        for t in triples
        if not edges[t].get("derivation")
        or any(r["rule"] in {"LocalAdmins", "PSRemoteUsers"} for r in raw.get(t, []))
    }


def validate_project(project):
    """Validate CLI records before enriching metadata; never relabel declared synthetic data."""
    canonical = {
        **project,
        "metadata": {
            k: v
            for k, v in project["metadata"].items()
            if k not in {"comparison_scope", "export_complete", "source_evidence"}
        },
    }
    validate_graph(canonical, CONTRACT)
    require(project["metadata"].get("synthetic", False) is False, "synthetic project refused")


def audit(project, baseline, mapping, raw):
    validate_mapping(mapping)
    validate_project(project)
    candidate = extract_graph(project, name="project")
    legacy = extract_graph(baseline, name="Legacy", identity_mapping=mapping)
    require(
        candidate.metadata["snapshot_id"] == legacy.metadata["snapshot_id"], "snapshot mismatch"
    )
    require(
        project["metadata"].get("synthetic") is False
        and baseline["metadata"].get("synthetic") is False,
        "measured inputs required",
    )
    require(
        eligibility_reasons(candidate, legacy) == ["Legacy: export_complete is not verified true"],
        "expected only the pending full-semantics gate",
    )
    edges = {(e["source"], e["kind"], e["target"]): e for e in project["edges"]}
    assessments = {
        (a["subject"], a["kind"], a["target"]): a for a in project.get("assessments", [])
    }
    require(len(assessments) == len(project.get("assessments", [])), "ambiguous assessment triple")
    for assessment in assessments.values():
        for provenance in assessment["provenance"]:
            prefix = "snapshot:" + candidate.metadata["snapshot_id"].split(":")[1] + "/"
            require(provenance["raw_file"].startswith(prefix), "assessment snapshot mismatch")
    c = {t.as_tuple() for t in candidate.unique_triples}
    b = {t.as_tuple() for t in legacy.unique_triples}
    differences = []
    for side, triples in (("project_only", c - b), ("legacy_only", b - c)):
        for triple in sorted(triples):
            evidence = list(raw.get(triple, []))
            edge = edges.get(triple)
            if edge and edge.get("derivation"):
                for path in edge["derivation"]["paths"]:
                    for step in path["steps"]:
                        kind = (
                            "MemberOf" if step["operation"] == "effective_membership" else "AdminTo"
                        )
                        evidence.extend(raw.get((step["source"], kind, step["target"]), []))
            differences.append(
                {
                    "side": side,
                    "triple": triple,
                    "classification": classify_difference(triple, side, raw, edges, assessments),
                    "raw_rule_evidence": evidence,
                    "project_edge": edge,
                    "project_assessment": assessments.get(triple),
                    "legacy_import_operation_provenance": None,
                }
            )
    by_kind = {}
    common = {}
    for kind in sorted(set(M1_RELATIONSHIPS) | {t[1] for t in b}):
        x, y = {t for t in c if t[1] == kind}, {t for t in b if t[1] == kind}
        by_kind[kind] = {
            "project": len(x),
            "legacy": len(y),
            "matching": len(x & y),
            "project_only": len(x - y),
            "legacy_only": len(y - x),
            "classifications": dict(
                Counter(d["classification"] for d in differences if d["triple"][1] == kind)
            ),
            "set_digests": {
                side: digest(encoded(sorted(triples)))
                for side, triples in (
                    ("project", x),
                    ("legacy", y),
                    ("matching", x & y),
                    ("project_only", x - y),
                    ("legacy_only", y - x),
                )
            },
        }
        # These source-rule views are explicitly narrower than m1-structural-v1.
        # Keep unexpected triples visible; do not select just the intersection.
        if kind == "MemberOf":
            expected = {
                t
                for t, refs in raw.items()
                if t[1] == kind and any(r["rule"] == "Members" for r in refs)
            }
            y -= {
                t
                for t in y
                if t not in expected and any(r["rule"] == "PrimaryGroupSid" for r in raw.get(t, []))
            }
        elif kind in {"GenericAll", "WriteDacl"}:
            expected = {t for t in raw if t[1] == kind and t[0] != t[2]}
            x, y = {t for t in x if t[0] != t[2]}, {t for t in y if t[0] != t[2]}
        elif kind in {"AdminTo", "CanPSRemote"}:
            expected = {t for t in raw if t[1] == kind}
            x = direct_host_view(x, edges, raw)
        else:
            continue
        common[kind] = {
            "status": "A_source_rule_view_pending_B_review",
            "raw_expected": len(expected),
            "project_selected": len(x),
            "legacy_selected": len(y),
            "exact_sets_equal": x == y == expected,
            "project_only": sorted(x - y),
            "legacy_only": sorted(y - x),
            "raw_missing_project": sorted(expected - x),
            "raw_missing_legacy": sorted(expected - y),
            "project_unexpected": sorted(x - expected),
            "legacy_unexpected": sorted(y - expected),
            "set_digest": digest(encoded(sorted(expected))),
        }
    samples = []
    for kind in M1_RELATIONSHIPS:
        matching = sorted(t for t in c & b if t[1] == kind)
        if matching:
            triple = matching[0]
            samples.append(
                {
                    "triple": triple,
                    "raw_rule_evidence": raw.get(triple, []),
                    "project_edge": edges[triple],
                    "legacy_import_operation_provenance": None,
                }
            )
    ids_c, ids_b = set(candidate.nodes), set(legacy.nodes)
    identity = {
        "project": len(ids_c),
        "legacy": len(ids_b),
        "matching": len(ids_c & ids_b),
        "project_only": sorted(ids_c - ids_b),
        "legacy_only": sorted(ids_b - ids_c),
        "by_kind": {
            kind: {
                "project": sum(n.kind == kind for n in candidate.nodes.values()),
                "legacy": sum(n.kind == kind for n in legacy.nodes.values()),
                "project_only": sorted(
                    n
                    for n in ids_c
                    if candidate.nodes[n].kind == kind
                    and (n not in ids_b or legacy.nodes[n].kind != kind)
                ),
                "legacy_only": sorted(
                    n
                    for n in ids_b
                    if legacy.nodes[n].kind == kind
                    and (n not in ids_c or candidate.nodes[n].kind != kind)
                ),
            }
            for kind in sorted({n.kind for n in candidate.nodes.values()})
        },
        "project_population": {
            "collected": sum(not n.is_boundary for n in candidate.nodes.values()),
            "boundary": sum(n.is_boundary for n in candidate.nodes.values()),
        },
        "by_population": {
            population: {
                "project_only": sorted(
                    n
                    for n in ids_c
                    if candidate.nodes[n].is_boundary == boundary
                    and (n not in ids_b or legacy.nodes[n].is_boundary != boundary)
                ),
                "legacy_only": sorted(
                    n
                    for n in ids_b
                    if legacy.nodes[n].is_boundary == boundary
                    and (n not in ids_c or candidate.nodes[n].is_boundary != boundary)
                ),
            }
            for population, boundary in (("collected", False), ("boundary", True))
        },
        "metadata_limit": "Legacy domain/boundary fields were assigned from project/raw mapping; "
        "their equality is not an independent Legacy metadata measurement.",
    }
    return {
        "schema_version": 1,
        "snapshot_id": candidate.metadata["snapshot_id"],
        "verdict": "OBSERVATION_DIFFERENCES_CLASSIFIED_PENDING_B_REVIEW",
        "identity_sets": identity,
        "by_kind": by_kind,
        "raw_occurrences": dict(
            Counter((r["rule"] + ":" + t[1]) for t, refs in raw.items() for r in refs)
        ),
        "common_source_rule_views": common,
        "differences": differences,
        "matching_samples": samples,
        "exact_triples": {"project": sorted(c), "legacy": sorted(b), "matching": sorted(c & b)},
        "multiplicity": {
            "project": asdict(graph_multiplicity(candidate, candidate.unique_triples)),
            "legacy": asdict(graph_multiplicity(legacy, legacy.unique_triples)),
        },
    }


def capture(args):
    """Reuse B's read-only queries/mapping on a new container; never change B's run pins."""
    require(
        args.project is not None and args.time_policy is not None,
        "local capture requires --project and --time-policy",
    )
    info = json.loads(
        subprocess.run(
            ["docker", "inspect", args.capture_container],
            capture_output=True,
            text=True,
            check=True,
        ).stdout
    )[0]
    require(info["Image"] == IMAGE and info["State"]["Running"], "runtime image/state mismatch")
    ports = info["NetworkSettings"]["Ports"]["7474/tcp"]
    require(
        any(p["HostIp"] == "127.0.0.1" and int(p["HostPort"]) == args.port for p in ports),
        "container localhost HTTP binding mismatch",
    )
    password = os.environ.get("NEO4J_PASSWORD")
    require(bool(password), "NEO4J_PASSWORD must be set for the local database")
    package = ROOT / "reports/research/issue-82-legacy-reconciliation-queries.json"
    queries = read_query_package(package)
    observations = {
        name: query(args.port, password, queries[name])
        for name in (
            "runtime",
            "all_nodes",
            "all_relationships",
            "nodes_by_labels",
            "relationships_by_kind",
        )
    }
    require(
        any("4.1.13" in row["versions"] for row in observations["runtime"]),
        "Neo4j version mismatch",
    )
    project = load_input_json(args.project)
    validate_project(project)
    manifest_path = ROOT / "data/samples/manifests/seamless-raw-v1.json"
    mapping, kinds = raw_mapping(manifest_path, args.raw_root, args.time_policy)
    project_nodes = {n["id"]: n for n in project["nodes"]}
    require(set(mapping.values()) == set(project_nodes), "project/raw identity mismatch")
    rows = []
    for node in observations["all_nodes"]:
        source = node["objectid"]
        require(set(node["labels"]) == {"Base", kinds[source]}, "Legacy typed-label mismatch")
        target = project_nodes[mapping[source]]
        rows.append(
            {
                "objectid": source,
                "comparison_identity": mapping[source],
                "labels": node["labels"],
                "kind": kinds[source],
                "domain": target["domain"],
                "is_boundary": target["is_boundary"],
                "mapping_rule": "issue-139-boundary"
                if source in BOUNDARY
                else "raw-adapter-normalizer",
            }
        )
    from scripts.reconcile_graph_baseline import COMPARISON_SCOPE

    project["metadata"].update(
        synthetic=False,
        export_complete=True,
        source_evidence="data/samples/manifests/seamless-raw-v1.json",
        comparison_scope=COMPARISON_SCOPE,
    )
    baseline = {
        "metadata": {
            "snapshot_id": project["metadata"]["snapshot_id"],
            "synthetic": False,
            "export_complete": False,
            "source_evidence": "issue47 native Legacy read-only capture",
            "comparison_scope": COMPARISON_SCOPE,
            "reason": "Same-name stored rows have different input/materialization policies.",
        },
        "nodes": [
            {
                "objectid": n["objectid"],
                "labels": n["labels"],
                "domain": n["domain"],
                "is_boundary": n["is_boundary"],
            }
            for n in rows
        ],
        "relationships": observations["all_relationships"],
    }
    require_ignored(
        args.export_dir,
        (
            "legacy-nodes.json",
            "identity-mapping.json",
            "legacy-relationships.json",
            "project-comparison.json",
            "legacy-comparison.json",
            "capture.json",
        ),
    )
    args.export_dir.mkdir(parents=True, exist_ok=True)
    for filename, data in (
        ("legacy-nodes.json", rows),
        ("identity-mapping.json", mapping),
        (
            "legacy-relationships.json",
            relationship_rows_for_export(observations["all_relationships"], mapping, project_nodes),
        ),
        ("project-comparison.json", project),
        ("legacy-comparison.json", baseline),
    ):
        write_json(args.export_dir / filename, data)
    write_json(
        args.export_dir / "capture.json",
        {
            "container_id": info["Id"],
            "image_id": info["Image"],
            "query_package_digest": digest(package.read_bytes()),
            "runtime": observations["runtime"],
            "labels": observations["nodes_by_labels"],
            "kinds": observations["relationships_by_kind"],
            "native_upload_required": True,
        },
    )


def summarize_sets(value):
    """Keep exact identity lists local, including on a run with unresolved differences."""
    if isinstance(value, dict):
        return {key: summarize_sets(item) for key, item in value.items()}
    if isinstance(value, list):
        return {"count": len(value), "digest": digest(encoded(value))}
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--export-dir", type=Path, required=True)
    parser.add_argument("--raw-root", type=Path, required=True)
    parser.add_argument("--importer-source", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=ROOT / ".cache/issue47-analysis")
    parser.add_argument("--capture-container", help="Read-only export after native Legacy upload")
    parser.add_argument("--port", type=int, default=47474)
    parser.add_argument("--project", type=Path, help="Canonical CLI output for local capture")
    parser.add_argument("--time-policy", type=Path, help="CLI time policy for local mapping")
    args = parser.parse_args()
    try:
        # Sensitive outputs must be ignored even when an alternate directory is supplied.
        require_ignored(args.output_dir, ("evidence.json", "comparator.json", "summary.json"))
        handoff = load_input_json(
            ROOT / "reports/baselines/seamless-legacy-403-reconciliation-handoff.json"
        )
        manifest = load_manifest(ROOT / "data/samples/manifests/seamless-raw-v1.json")
        require(not verify_manifest(args.raw_root, manifest), "raw manifest verification failed")
        require(
            digest(args.importer_source.read_bytes()) == IMPORTER_DIGEST,
            "Legacy importer source mismatch",
        )
        if args.capture_container:
            capture(args)
        for filename, expected in (
            ("legacy-nodes.json", handoff["identity_export"]["digest"]),
            ("legacy-relationships.json", handoff["relationship_export"]["digest"]),
            ("identity-mapping.json", handoff["identity_export"]["mapping_digest"]),
        ):
            require(
                digest((args.export_dir / filename).read_bytes()) == expected,
                f"{filename}: differs from #183 full observation digest",
            )
        project = load_input_json(args.export_dir / "project-comparison.json")
        baseline = load_input_json(args.export_dir / "legacy-comparison.json")
        mapping = load_input_json(args.export_dir / "identity-mapping.json")
        require(
            project["metadata"]["snapshot_id"] == manifest["snapshot_id"],
            "project/raw snapshot mismatch",
        )
        # Verify the comparator input rows against the pinned full tables as well.
        nodes = load_input_json(args.export_dir / "legacy-nodes.json")
        expected_nodes = [
            {
                "objectid": n["objectid"],
                "labels": n["labels"],
                "domain": n["domain"],
                "is_boundary": n["is_boundary"],
            }
            for n in nodes
        ]
        require(baseline["nodes"] == expected_nodes, "Legacy comparator node table mismatch")
        full_rows = load_input_json(args.export_dir / "legacy-relationships.json")
        expected_rows = Counter(
            {(r["source"], r["kind"], r["target"]): r["stored_multiplicity"] for r in full_rows}
        )
        actual_rows = Counter(
            (r["source"], r["kind"], r["target"]) for r in baseline["relationships"]
        )
        require(
            actual_rows == expected_rows, "Legacy comparator directed rows/multiplicity mismatch"
        )
        raw = raw_index(args.raw_root, manifest, mapping)
        result = audit(project, baseline, mapping, raw)
        gate = reconcile_graphs(project, baseline, identity_mapping=mapping)
        require(gate.verdict != "INVALID_INPUT", gate.summary)
        args.output_dir.mkdir(parents=True, exist_ok=True)
        evidence_digest = write_json(args.output_dir / "evidence.json", result)
        write_json(args.output_dir / "comparator.json", gate.to_dict())
        summary = {
            key: value
            for key, value in result.items()
            if key in {"schema_version", "snapshot_id", "verdict", "by_kind", "multiplicity"}
        }
        summary["identity_sets"] = summarize_sets(result["identity_sets"])
        summary["common_source_rule_views"] = summarize_sets(result["common_source_rule_views"])
        summary["raw_occurrences"] = result["raw_occurrences"]
        summary["bindings"] = {
            "analysis_tool_digest": digest(Path(__file__).read_bytes()),
            "project_revision": project["metadata"]["code_version"],
            "project_digest": digest((args.export_dir / "project-comparison.json").read_bytes()),
            "baseline_digest": digest((args.export_dir / "legacy-comparison.json").read_bytes()),
            "handoff_manifest_digest": digest(encoded(handoff)),
            "raw_manifest_digest": digest(
                (ROOT / "data/samples/manifests/seamless-raw-v1.json").read_bytes()
            ),
            "importer_source_digest": IMPORTER_DIGEST,
            "evidence_digest": evidence_digest,
        }
        summary["comparator_gate"] = {"verdict": gate.verdict, "summary": gate.summary}
        summary["historical_unknowns"] = handoff["limitations"]
        write_json(args.output_dir / "summary.json", summary)
        print(
            json.dumps(
                {
                    "status": result["verdict"],
                    "comparator": gate.verdict,
                    "evidence_digest": evidence_digest,
                }
            )
        )
    except (ValueError, KeyError, OSError) as exc:
        print(f"Audit refused: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
