"""Replay #196 against the clean pinned checkout in cwd; keep all outputs ignored.

This harness may be executed from outside that checkout. Only pinned raw and
Legacy full exports are read; canonical/comparator/audit outputs are regenerated.
The accepted #195 slices supplement, never replace, the full comparator gate.
"""

from __future__ import annotations

import argparse
import json
import platform
import shutil
import subprocess
import sys
from collections import Counter
from importlib.metadata import version
from pathlib import Path

ROOT = Path.cwd().resolve()
sys.path.insert(0, str(ROOT))

from scripts.reconcile_graph_baseline import COMPARISON_SCOPE, M1_RELATIONSHIPS  # noqa: E402
from scripts.research.export_legacy_reconciliation_baseline import (  # noqa: E402
    SNAPSHOT,
    digest,
    encoded,
    raw_mapping,
    require,
    write_json,
)
from scripts.research.reconcile_seamless_legacy import (  # noqa: E402
    audit,
    direct_host_view,
    raw_index,
    require_ignored,
    summarize_sets,
    validate_project,
)
from src.data.manifest import load_manifest, verify_manifest  # noqa: E402

REVISION = "cc5f971435dc7d14476d6055024f441e398a4ff8"
CONTRACT_PATH = "docs/research/seamless-legacy-403-comparison-contract.md"
CONTRACT_DIGEST = "6a0bce271788560f3b9b32f5a15b824d6db17a874f95bb8a38b968f1714f2ac6"
MANIFEST_PATH = "data/samples/manifests/seamless-raw-v1.json"
MANIFEST_DIGEST = "a18d7a2a8b4cf283069da46d00368ffbe6a1eab6ad92a5c89b5a531809f5da9d"
# Accepted #183/#194 external-input byte pins, not generated project evidence.
EXTERNAL_PINS = {
    "legacy-nodes.json": "ed4a6aa7775a4bfb5994875243eaf11588cf03cf4301acc1f23ce62fae11839c",
    "legacy-relationships.json": "4071dd8747a18aef4f30b074eeac163cbc7454cfe42a234367e81f8c488cdbf6",
    "identity-mapping.json": "202a91b951ff9292f57eeb535c65f02bb7063f5c28a6b27589acdc4ae45c570b",
}
TIME_POLICY = (
    '{"timestamp":"2026-10-01T00:00:00Z","status":"assumed",'
    '"reason":"Reproducible assumption for #82; collection time unknown."}\n'
)
TIME_POLICY_DIGEST = "3540afa5ff3f4affd9deddd75f3da43409c5885af4ab9b7b2d17a97aac3a2e7b"


def new_output(directory):
    require(not directory.exists(), "output directory already exists; choose a fresh destination")
    require_ignored(
        directory,
        (
            *EXTERNAL_PINS,
            "time-policy.json",
            "raw-verify.log",
            "parser.log",
            "comparator.log",
            "project.json",
            "project-comparison.json",
            "legacy-comparison.json",
            "comparator-cli.json",
            "comparator-stable.json",
            "evidence.json",
            "slice-proofs.json",
            "manifest.json",
        ),
    )
    directory.mkdir(parents=True)


def stable_comparator(report):
    """The comparator clock is the only excluded field; original bytes stay intact."""
    return {k: v for k, v in report.items() if k != "reconciliation_timestamp"}


def accepted_slices(project, legacy, edges, raw):
    result = {}
    for kind in ("MemberOf", "GenericAll", "WriteDacl", "AdminTo", "CanPSRemote"):
        x = {t for t in project if t[1] == kind}
        y = {t for t in legacy if t[1] == kind}
        expected = {t for t in raw if t[1] == kind}
        if kind in {"GenericAll", "WriteDacl"}:
            x, y, expected = ({t for t in ts if t[0] != t[2]} for ts in (x, y, expected))
        elif kind in {"AdminTo", "CanPSRemote"}:
            x = direct_host_view(x, edges, raw)
        result[kind] = {
            "project": x,
            "legacy": y,
            "raw": expected,
            "matching": x & y,
            "project_only": x - y,
            "legacy_only": y - x,
            "raw_missing_project": expected - x,
            "raw_missing_legacy": expected - y,
            "project_unexpected": x - expected,
            "legacy_unexpected": y - expected,
            "exact_sets_equal": x == y == expected,
        }
    return result


def replay(raw_root, legacy_dir, out):
    def git(*args):
        return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()

    require(git("rev-parse", "HEAD") == REVISION, "requires the exact accepted develop revision")
    require(
        not git("status", "--porcelain=v1"), "requires a clean checkout including untracked files"
    )
    require(sys.prefix != sys.base_prefix, "run with a virtual-environment Python")
    require(sys.version_info[:2] == (3, 14), "Python 3.14 required")
    require(
        digest((ROOT / CONTRACT_PATH).read_bytes()) == CONTRACT_DIGEST, "#195 contract mismatch"
    )
    require(digest((ROOT / MANIFEST_PATH).read_bytes()) == MANIFEST_DIGEST, "raw manifest mismatch")
    manifest = load_manifest(ROOT / MANIFEST_PATH)
    require(manifest["snapshot_id"] == SNAPSHOT, "snapshot mismatch")
    require(not verify_manifest(raw_root, manifest), "raw checksum verification failed")
    for name, pin in EXTERNAL_PINS.items():
        require(
            digest((legacy_dir / name).read_bytes()) == pin, f"{name}: external checksum mismatch"
        )
    dependencies = {}
    for filename in ("requirements.txt", "requirements-dev.txt"):
        for line in (ROOT / filename).read_text().splitlines():
            if "==" not in line or line.startswith("#") or ";" in line:
                continue
            name, pin = line.split("==")
            dependencies[name] = version(name)
            require(dependencies[name] == pin, f"{name}: dependency version mismatch")
    if sys.platform == "win32":
        dependencies["colorama"] = version("colorama")
        require(dependencies["colorama"] == "0.4.6", "colorama version mismatch")
    new_output(out)
    for name in EXTERNAL_PINS:
        require_ignored(out, (name,))
        shutil.copyfile(legacy_dir / name, out / name)
        require(digest((out / name).read_bytes()) == EXTERNAL_PINS[name], "copied input changed")
    (out / "time-policy.json").write_bytes(TIME_POLICY.encode())
    require(
        digest((out / "time-policy.json").read_bytes()) == TIME_POLICY_DIGEST,
        "time policy mismatch",
    )
    commands = []

    def run(args, log, expected_exit=0):
        argv = [sys.executable, *map(str, args)]
        require_ignored(out, (log,))
        with (out / log).open("w", encoding="utf-8") as stream:
            completed = subprocess.run(argv, cwd=ROOT, stdout=stream, stderr=stream, check=False)
        replacements = {sys.executable: "<PY>", str(raw_root): "<RAW_ROOT>", str(out): "<OUTPUT>"}
        commands.append(
            {
                "argv": [replacements.get(a, a.replace(str(out), "<OUTPUT>")) for a in argv],
                "exit_code": completed.returncode,
                "log": log,
            }
        )
        require(
            completed.returncode == expected_exit, f"{log}: unexpected exit; inspect private log"
        )

    run(["scripts/snapshot_manifest.py", "verify", raw_root, MANIFEST_PATH], "raw-verify.log")
    run(
        [
            "-m",
            "src.parser.cli",
            "--snapshot-id",
            SNAPSHOT,
            "--raw-dir",
            raw_root,
            "--manifest-dir",
            "data/samples/manifests",
            "--time-policy",
            out / "time-policy.json",
            "--profile",
            "unit",
            "--created-at",
            "2026-10-01T00:00:00Z",
            "--error-policy",
            "fail_fast",
            "--output",
            out / "project.json",
            "--summary",
        ],
        "parser.log",
    )
    project = json.loads((out / "project.json").read_text())
    validate_project(project)
    require(project["metadata"]["code_version"] == REVISION, "CLI code binding mismatch")
    original_records = {
        k: digest(encoded(project.get(k, []))) for k in ("nodes", "edges", "assessments")
    }
    project["metadata"].update(
        synthetic=False,
        export_complete=True,
        source_evidence=MANIFEST_PATH,
        comparison_scope=COMPARISON_SCOPE,
    )
    write_json(out / "project-comparison.json", project)
    mapping = json.loads((out / "identity-mapping.json").read_text())
    rebuilt_mapping, kinds = raw_mapping(ROOT / MANIFEST_PATH, raw_root, out / "time-policy.json")
    require(
        mapping == rebuilt_mapping, "pinned mapping differs from independently rebuilt raw mapping"
    )
    nodes = json.loads((out / "legacy-nodes.json").read_text())
    project_nodes = {n["id"]: n for n in project["nodes"]}
    require({n["objectid"] for n in nodes} == set(mapping), "Legacy identity coverage mismatch")
    require(set(project_nodes) == set(mapping.values()), "project identity coverage mismatch")
    for n in nodes:
        target = project_nodes[mapping[n["objectid"]]]
        require(n["comparison_identity"] == target["id"], "Legacy node mapping mismatch")
        require(
            set(n["labels"]) == {"Base", kinds[n["objectid"]]} == {"Base", target["kind"]},
            "typed identity mismatch",
        )
        require(
            n["domain"] == target["domain"] and n["is_boundary"] == target["is_boundary"],
            "identity scope mismatch",
        )
    rows = json.loads((out / "legacy-relationships.json").read_text())
    relationships = []
    for row in rows:
        require(
            row["source_identity"] == mapping[row["source"]]
            and row["target_identity"] == mapping[row["target"]],
            "relationship mapping mismatch",
        )
        for side in ("source", "target"):
            require(
                row[side + "_boundary"] == project_nodes[mapping[row[side]]]["is_boundary"],
                "relationship boundary mismatch",
            )
        multiplicity = row["stored_multiplicity"]
        require(type(multiplicity) is int and multiplicity > 0, "invalid stored multiplicity")
        relationships.extend(
            {k: row[k] for k in ("source", "kind", "target")} for _ in range(multiplicity)
        )
    baseline = {
        "metadata": {
            "snapshot_id": SNAPSHOT,
            "synthetic": False,
            "export_complete": False,
            "source_evidence": "issue47 native Legacy read-only capture",
            "comparison_scope": COMPARISON_SCOPE,
            "reason": "Same-name stored rows have different input/materialization policies.",
        },
        "nodes": [
            {k: n[k] for k in ("objectid", "labels", "domain", "is_boundary")} for n in nodes
        ],
        "relationships": relationships,
    }
    write_json(out / "legacy-comparison.json", baseline)
    run(
        [
            "scripts/reconcile_graph_baseline.py",
            "--candidate",
            out / "project-comparison.json",
            "--baseline",
            out / "legacy-comparison.json",
            "--mapping",
            out / "identity-mapping.json",
            "--output",
            out / "comparator-cli.json",
            "--summary",
        ],
        "comparator.log",
        expected_exit=2,
    )
    comparator = json.loads((out / "comparator-cli.json").read_text())
    require(comparator["verdict"] == "NOT_MEASURABLE", "full comparator gate changed")
    write_json(out / "comparator-stable.json", stable_comparator(comparator))
    raw = raw_index(raw_root, manifest, mapping)
    evidence = audit(project, baseline, mapping, raw)
    write_json(out / "evidence.json", evidence)
    sets = {k: {tuple(t) for t in evidence["exact_triples"][k]} for k in ("project", "legacy")}
    edges = {(e["source"], e["kind"], e["target"]): e for e in project["edges"]}
    slices = accepted_slices(sets["project"], sets["legacy"], edges, raw)
    members = {t for t, refs in raw.items() if any(r["rule"] == "Members" for r in refs)}
    primary = {t for t, refs in raw.items() if any(r["rule"] == "PrimaryGroupSid" for r in refs)}
    raw_files = {
        f["relative_path"]: json.loads(
            (raw_root / f["relative_path"]).read_text(encoding="utf-8-sig")
        )
        for f in manifest["files"]
    }
    primary_kinds = Counter()
    for t in primary:
        require(t in edges and not edges[t].get("derivation"), "primary membership is not direct")
        for ref in (r for r in raw[t] if r["rule"] == "PrimaryGroupSid"):
            filename, pointer = ref["pointer"].split("#", 1)
            collection, index, _ = pointer.strip("/").split("/")
            record = raw_files[filename][collection][int(index)]
            require(
                t
                == (
                    mapping[record["ObjectIdentifier"]],
                    "MemberOf",
                    mapping[record["PrimaryGroupSid"]],
                ),
                "primary pointer mismatch",
            )
            require(
                any(
                    p["attribute"] == "PrimaryGroupSid"
                    and p["record_id"] == record["ObjectIdentifier"]
                    and p["raw_file"].endswith("/" + filename)
                    and p["evidence_type"] == "positive"
                    for p in edges[t]["provenance"]
                ),
                "primary positive provenance missing",
            )
            primary_kinds[project_nodes[t[0]]["kind"]] += 1
    proof = {
        k: {side: sorted(v) if isinstance(v, set) else v for side, v in view.items()}
        for k, view in slices.items()
    }
    proof["membership_sources"] = {
        "members": sorted(members),
        "primarygroup": sorted(primary),
        "overlap": sorted(members & primary),
    }
    ace_proofs = {}
    for kind in ("GenericAll", "WriteDacl"):
        expected = {t for t in raw if t[1] == kind}
        x, y = ({t for t in sets[side] if t[1] == kind} for side in ("project", "legacy"))
        ace_proofs[kind] = {
            "project_equals_raw_unique": x == expected,
            "legacy_equals_raw_unique_nonself": y == {t for t in expected if t[0] != t[2]},
            "project_only_equals_raw_self": x - y == {t for t in expected if t[0] == t[2]},
            "raw_duplicate_occurrences": sum(len(raw[t]) for t in expected) - len(expected),
        }
    write_json(out / "slice-proofs.json", proof)
    ledger = [
        {
            "side": d["side"],
            "kind": d["triple"][1],
            "triple_digest": digest(encoded(d["triple"])),
            "classification": d["classification"],
            "raw_rule_pointers": [r["pointer"] for r in d["raw_rule_evidence"]],
            "assessment_status": (d["project_assessment"] or {}).get("status"),
        }
        for d in evidence["differences"]
        if d["triple"][1] in M1_RELATIONSHIPS
    ]
    assessments = project.get("assessments", [])
    session_rows = 0
    for data in raw_files.values():
        if data["meta"]["type"] == "computers":
            for record in data["computers"]:
                for field in ("Sessions", "PrivilegedSessions", "RegistrySessions"):
                    value = record.get(field, [])
                    session_rows += len(
                        value.get("Results", []) if isinstance(value, dict) else value
                    )
    semantic_checks = {
        "canonical_records_unchanged_by_comparison_binding": original_records
        == {k: digest(encoded(project.get(k, []))) for k in original_records},
        "primary_positive_direct_provenance": dict(primary_kinds),
        "assessment_statuses": dict(Counter(a["status"] for a in assessments)),
        "assessment_kinds": dict(Counter(a["kind"] for a in assessments)),
        "assessment_digest": digest(encoded(assessments)),
        "rdp_assessments_exactly_raw_memberships": {
            (a["subject"], a["kind"], a["target"]) for a in assessments
        }
        == {t for t in raw if t[1] == "CanRDP"},
        "rdp_remains_unknown": all(
            a["kind"] == "CanRDP"
            and a["status"] == "unknown"
            and a["reason"] == "required UserRights evidence is incomplete"
            and all(
                r["user_rights_present"] is False
                for r in raw[(a["subject"], a["kind"], a["target"])]
            )
            for a in assessments
        ),
        "rdp_traversal_edges": sum(t[1] == "CanRDP" for t in sets["project"]),
        "raw_session_rows": session_rows,
    }
    summary = {
        "schema_version": 1,
        "runner": "TTS A / @Lolavine777",
        "cross_reproducer": "TTS B / @nairyuuu: pending",
        "code_revision": REVISION,
        "clean_checkout_before_run": True,
        "runtime": {
            "python": platform.python_version(),
            "implementation": platform.python_implementation(),
            "system": platform.system(),
            "machine": platform.machine(),
            "dependencies": dependencies,
        },
        "contract": {
            "graph": project["metadata"]["contract_version"],
            "profile": project["metadata"]["weight_profile"],
            "accepted_comparison": "seamless-legacy-403-m1-common-v1",
            "acceptance": "#195 accepted via merged PR #197",
            "digest": CONTRACT_DIGEST,
            "machine_scope": COMPARISON_SCOPE,
        },
        "snapshot_id": SNAPSHOT,
        "time_policy": {
            "sha256": TIME_POLICY_DIGEST,
            "status": "assumed",
            "collection_time": "unknown",
        },
        "inputs": {
            **EXTERNAL_PINS,
            "raw_manifest": MANIFEST_DIGEST,
            "raw_files": manifest["files"],
        },
        "harness_sha256": digest(Path(__file__).read_bytes()),
        "commands": commands,
        "comparator": {
            "verdict": comparator["verdict"],
            "exit_code": 2,
            "timestamp": comparator["reconciliation_timestamp"],
            "summary": comparator["summary"],
            "stable_exclusion": "reconciliation_timestamp only",
            "legacy_export_complete": False,
        },
        "identity_sets": summarize_sets(evidence["identity_sets"]),
        "by_kind": evidence["by_kind"],
        "multiplicity": evidence["multiplicity"],
        "accepted_slices": summarize_sets(proof),
        "semantic_checks": semantic_checks,
        "canonical_record_digests": original_records,
        "raw_ace_proofs": ace_proofs,
        "m1_difference_ledger": ledger,
        "difference_dispositions": {
            "legacy_self_ace_filter": "accepted_policy_difference",
            "project_nested_admin_materialization": "accepted_policy_difference",
            "policy_difference_unknown_userrights": "accepted_policy_difference",
        },
        "zero_observation_dispositions": {
            kind: {
                "disposition": "not_measurable",
                "project": evidence["by_kind"][kind]["project"],
                "legacy": evidence["by_kind"][kind]["legacy"],
                "raw_indexed_triples": sum(t[1] == kind for t in raw),
            }
            for kind in ("ForceChangePassword", "HasSession")
        },
        "limitations": [
            "Legacy exports/mapping are pinned private prerequisites, not a new import/capture.",
            "Legacy domain/boundary metadata comes from raw/project mapping; "
            "it is not independently measured.",
            "No decoder, active-session, endpoint, runtime or full BloodHound parity claim.",
            "Historical audit Members-only view is superseded by accepted_slices.MemberOf.",
            "B independent run/review and Week 3 acceptance remain pending.",
        ],
    }
    checks = [
        all(v["exact_sets_equal"] for v in slices.values()),
        all(
            all(
                v[k]
                for k in (
                    "project_equals_raw_unique",
                    "legacy_equals_raw_unique_nonself",
                    "project_only_equals_raw_self",
                )
            )
            for v in ace_proofs.values()
        ),
        not members & primary,
        semantic_checks["canonical_records_unchanged_by_comparison_binding"],
        semantic_checks["rdp_assessments_exactly_raw_memberships"],
        semantic_checks["rdp_remains_unknown"],
        semantic_checks["rdp_traversal_edges"] == 0,
        all(d["classification"] in summary["difference_dispositions"] for d in ledger),
        all(
            v["project"] == v["legacy"] == v["raw_indexed_triples"] == 0
            for v in summary["zero_observation_dispositions"].values()
        ),
        session_rows == 0,
    ]
    summary["reproduction_checks_passed"] = all(checks)
    summary["output_digests"] = {
        p.name: digest(p.read_bytes()) for p in sorted(out.iterdir()) if p.is_file()
    }
    write_json(out / "manifest.json", summary)
    require(
        summary["reproduction_checks_passed"],
        "discrepancy retained in manifest/proofs; do not hand-edit outputs",
    )
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-root", type=Path, required=True)
    parser.add_argument("--legacy-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = replay(
            args.raw_root.resolve(), args.legacy_dir.resolve(), args.output_dir.resolve()
        )
    except (ValueError, KeyError, OSError, subprocess.CalledProcessError) as exc:
        print(f"Reproduction refused: {exc}", file=sys.stderr)
        return 2
    print(
        json.dumps(
            {
                "checks_passed": result["reproduction_checks_passed"],
                "full_comparator": result["comparator"]["verdict"],
                "B_cross_reproduction": "pending",
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
