"""Final clean-checkout cross-reproduction for SEAMLESS to Legacy 4.0.3 reconciliation.

Reproduces canonical graph from raw SEAMLESS, executes comparator, and proves
exact per-slice decompositions according to Comparison Contract #195 without
relying on previous untracked state or lifting comparator gates.

Sanitized output: contains only counts, digests, and raw pointers.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from collections import Counter
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if __package__ in {None, ""}:
    sys.path.insert(0, str(ROOT))

from scripts.check_contract import validate_graph  # noqa: E402
from scripts.reconcile_graph_baseline import (  # noqa: E402
    COMPARISON_SCOPE,
    CONTRACT,
    M1_RELATIONSHIPS,
    extract_graph,
    graph_multiplicity,
    load_input_json,
    reconcile_graphs,
)
from scripts.research.export_legacy_reconciliation_baseline import (  # noqa: E402
    digest,
    encoded,
    require,
    write_json,
)
from scripts.research.reconcile_seamless_legacy import (  # noqa: E402
    IMPORTER_DIGEST,
    classify_difference,
    raw_index,
    validate_project,
)
from src.data.manifest import load_manifest, verify_manifest  # noqa: E402

ACCEPTED_DEVELOP_REVISION = "8535d44771ec9ec1960b4e883103f83654cc1d4f"
ACCEPTED_SNAPSHOT = "sha256:e0601d763eeea285d268ec9e468d321c50c9d7faba53c8e7442a2fcc4159c812"
ACCEPTED_MANIFEST_DIGEST = "a18d7a2a8b4cf283069da46d00368ffbe6a1eab6ad92a5c89b5a531809f5da9d"
ACCEPTED_TIME_POLICY_DIGEST = "3540afa5ff3f4affd9deddd75f3da43409c5885af4ab9b7b2d17a97aac3a2e7b"

EXPECTED_PREREQUISITES = {
    "legacy-nodes.json": "ed4a6aa7775a4bfb5994875243eaf11588cf03cf4301acc1f23ce62fae11839c",
    "legacy-relationships.json": "4071dd8747a18aef4f30b074eeac163cbc7454cfe42a234367e81f8c488cdbf6",
    "identity-mapping.json": "202a91b951ff9292f57eeb535c65f02bb7063f5c28a6b27589acdc4ae45c570b",
    "legacy-comparison.json": "7e170793f88abf39fc927b503aa60a26d6c8480e1a838be76da2840019e4f97d",
    "newingestion.js": IMPORTER_DIGEST,
    "time-policy.json": ACCEPTED_TIME_POLICY_DIGEST,
}


def get_git_commit(cwd: Path = ROOT) -> str:
    """Return the 40-character current HEAD commit SHA."""
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def verify_external_prerequisites(
    raw_root: Path,
    manifest_path: Path,
    prerequisites_dir: Path,
) -> dict[str, Any]:
    """Verify raw snapshot and external prerequisite digests."""
    require(raw_root.is_dir(), f"raw directory not found: {raw_root}")
    require(manifest_path.is_file(), f"manifest not found: {manifest_path}")
    manifest_bytes = manifest_path.read_bytes()
    manifest_sha = hashlib.sha256(manifest_bytes).hexdigest()
    require(
        manifest_sha == ACCEPTED_MANIFEST_DIGEST,
        f"manifest digest mismatch: expected {ACCEPTED_MANIFEST_DIGEST}, got {manifest_sha}",
    )
    manifest = load_manifest(manifest_path)
    require(
        manifest["snapshot_id"] == ACCEPTED_SNAPSHOT,
        f"snapshot_id mismatch: expected {ACCEPTED_SNAPSHOT}, got {manifest['snapshot_id']}",
    )
    issues = verify_manifest(raw_root, manifest)
    require(not issues, f"raw manifest verification failed: {issues}")

    verified_prereqs = {}
    for filename, expected_digest in EXPECTED_PREREQUISITES.items():
        filepath = prerequisites_dir / filename
        require(filepath.is_file(), f"missing external prerequisite: {filepath}")
        actual_digest = hashlib.sha256(filepath.read_bytes()).hexdigest()
        require(
            actual_digest == expected_digest,
            f"prerequisite digest mismatch for {filename}: "
            f"expected {expected_digest}, got {actual_digest}",
        )
        verified_prereqs[filename] = {
            "digest": actual_digest,
            "classification": "external_input",
            "matches_accepted": True,
        }

    return {
        "raw_manifest": {
            "path": str(manifest_path.as_posix()),
            "digest": manifest_sha,
            "snapshot_id": manifest["snapshot_id"],
            "classification": "external_input",
        },
        "prerequisites": verified_prereqs,
    }


def regenerate_canonical_graph(
    raw_root: Path,
    manifest_path: Path,
    time_policy_path: Path,
    output_path: Path,
    python_exe: str = sys.executable,
) -> dict[str, Any]:
    """Run official src.parser.cli to produce canonical graph from raw SEAMLESS."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        python_exe,
        "-m",
        "src.parser.cli",
        "--snapshot-id",
        ACCEPTED_SNAPSHOT,
        "--raw-dir",
        str(raw_root),
        "--manifest-dir",
        str(manifest_path.parent),
        "--time-policy",
        str(time_policy_path),
        "--created-at",
        "2026-10-01T00:00:00Z",
        "--error-policy",
        "fail_fast",
        "--output",
        str(output_path),
        "--summary",
    ]
    proc = subprocess.run(
        cmd,
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    require(
        proc.returncode == 0,
        f"parser CLI failed with exit code {proc.returncode}:\n{proc.stderr}\n{proc.stdout}",
    )
    raw_bytes = output_path.read_bytes()
    output_digest = hashlib.sha256(raw_bytes).hexdigest()

    graph = json.loads(raw_bytes.decode("utf-8"))
    validate_graph(graph, CONTRACT)

    node_counts = Counter(n["kind"] for n in graph["nodes"])
    edge_counts = Counter(e["kind"] for e in graph["edges"])
    assessments = graph.get("assessments", [])

    return {
        "output_path": str(output_path.as_posix()),
        "output_digest": output_digest,
        "node_total": len(graph["nodes"]),
        "node_counts": dict(sorted(node_counts.items())),
        "edge_total": len(graph["edges"]),
        "edge_counts": dict(sorted(edge_counts.items())),
        "assessment_total": len(assessments),
        "code_version": graph["metadata"]["code_version"],
        "contract_version": graph["metadata"]["contract_version"],
        "graph_data": graph,
    }


def compute_per_slice_proofs(
    project_graph: dict[str, Any],
    baseline_graph: dict[str, Any],
    mapping: dict[str, str],
    raw_root: Path,
    manifest: dict[str, Any],
) -> dict[str, Any]:
    """Calculate exact per-slice proofs and decompositions under Contract #195."""
    raw = raw_index(raw_root, manifest, mapping)
    candidate = extract_graph(project_graph, name="project")
    legacy = extract_graph(baseline_graph, name="Legacy", identity_mapping=mapping)

    c_triples = {t.as_tuple() for t in candidate.unique_triples}
    b_triples = {t.as_tuple() for t in legacy.unique_triples}

    edges = {(e["source"], e["kind"], e["target"]): e for e in project_graph["edges"]}
    assessments = {
        (a["subject"], a["kind"], a["target"]): a for a in project_graph.get("assessments", [])
    }

    # 1. MemberOf
    mo_members = {
        t
        for t, refs in raw.items()
        if t[1] == "MemberOf" and any(r["rule"] == "Members" for r in refs)
    }
    mo_primary = {
        t
        for t, refs in raw.items()
        if t[1] == "MemberOf" and any(r["rule"] == "PrimaryGroupSid" for r in refs)
    }
    mo_project = {t for t in c_triples if t[1] == "MemberOf"}
    mo_legacy = {t for t in b_triples if t[1] == "MemberOf"}
    mo_overlap = mo_members & mo_primary
    mo_matching = mo_project & mo_legacy
    mo_proj_only = mo_project - mo_legacy
    mo_leg_only = mo_legacy - mo_project

    memberof_proof = {
        "status": "equivalent_in_accepted_scope",
        "members_count": len(mo_members),
        "primary_group_count": len(mo_primary),
        "overlap_count": len(mo_overlap),
        "project_count": len(mo_project),
        "legacy_count": len(mo_legacy),
        "matching_count": len(mo_matching),
        "project_only_count": len(mo_proj_only),
        "legacy_only_count": len(mo_leg_only),
        "exact_sets_equal": mo_project == mo_legacy == (mo_members | mo_primary),
        "digests": {
            "members": digest(encoded(sorted(mo_members))),
            "primarygroup": digest(encoded(sorted(mo_primary))),
            "project_memberof": digest(encoded(sorted(mo_project))),
            "legacy_memberof": digest(encoded(sorted(mo_legacy))),
            "matching": digest(encoded(sorted(mo_matching))),
            "project_only": digest(encoded(sorted(mo_proj_only))),
            "legacy_only": digest(encoded(sorted(mo_leg_only))),
        },
    }

    # 2. GenericAll
    ga_expected_raw = {t for t in raw if t[1] == "GenericAll"}
    ga_expected_nonself = {t for t in ga_expected_raw if t[0] != t[2]}
    ga_expected_self = {t for t in ga_expected_raw if t[0] == t[2]}
    ga_project = {t for t in c_triples if t[1] == "GenericAll"}
    ga_legacy = {t for t in b_triples if t[1] == "GenericAll"}
    ga_nonself_proj = {t for t in ga_project if t[0] != t[2]}
    ga_nonself_leg = {t for t in ga_legacy if t[0] != t[2]}
    ga_self_proj = {t for t in ga_project if t[0] == t[2]}
    ga_self_leg = {t for t in ga_legacy if t[0] == t[2]}

    generic_all_proof = {
        "disposition_nonself": "equivalent_in_accepted_scope",
        "disposition_self_ace": "accepted_policy_difference",
        "project_total": len(ga_project),
        "legacy_total": len(ga_legacy),
        "nonself_matching_count": len(ga_nonself_proj & ga_nonself_leg),
        "project_only_self_count": len(ga_self_proj),
        "legacy_self_count": len(ga_self_leg),
        "nonself_exact_sets_equal": ga_nonself_proj == ga_nonself_leg == ga_expected_nonself,
        "project_equals_raw_unique": ga_project == ga_expected_raw,
        "legacy_equals_raw_unique_nonself": ga_legacy == ga_expected_nonself,
        "project_only_equals_raw_self": ga_self_proj
        == ga_expected_self
        == (ga_project - ga_legacy),
        "legacy_self_empty": ga_self_leg == set(),
        "legacy_only_empty": (ga_legacy - ga_project) == set(),
        "raw_duplicate_occurrences": sum(len(raw[t]) for t in ga_expected_raw)
        - len(ga_expected_raw),
        "digests": {
            "project_total": digest(encoded(sorted(ga_project))),
            "legacy_total": digest(encoded(sorted(ga_legacy))),
            "nonself_matching": digest(encoded(sorted(ga_nonself_proj & ga_nonself_leg))),
            "project_only_self": digest(encoded(sorted(ga_self_proj))),
        },
    }

    # 3. WriteDacl
    wd_expected_raw = {t for t in raw if t[1] == "WriteDacl"}
    wd_expected_nonself = {t for t in wd_expected_raw if t[0] != t[2]}
    wd_expected_self = {t for t in wd_expected_raw if t[0] == t[2]}
    wd_project = {t for t in c_triples if t[1] == "WriteDacl"}
    wd_legacy = {t for t in b_triples if t[1] == "WriteDacl"}
    wd_nonself_proj = {t for t in wd_project if t[0] != t[2]}
    wd_nonself_leg = {t for t in wd_legacy if t[0] != t[2]}
    wd_self_proj = {t for t in wd_project if t[0] == t[2]}
    wd_self_leg = {t for t in wd_legacy if t[0] == t[2]}

    write_dacl_proof = {
        "disposition_nonself": "equivalent_in_accepted_scope",
        "disposition_self_ace": "accepted_policy_difference",
        "project_total": len(wd_project),
        "legacy_total": len(wd_legacy),
        "nonself_matching_count": len(wd_nonself_proj & wd_nonself_leg),
        "project_only_self_count": len(wd_self_proj),
        "legacy_self_count": len(wd_self_leg),
        "nonself_exact_sets_equal": wd_nonself_proj == wd_nonself_leg == wd_expected_nonself,
        "project_equals_raw_unique": wd_project == wd_expected_raw,
        "legacy_equals_raw_unique_nonself": wd_legacy == wd_expected_nonself,
        "project_only_equals_raw_self": wd_self_proj
        == wd_expected_self
        == (wd_project - wd_legacy),
        "legacy_self_empty": wd_self_leg == set(),
        "legacy_only_empty": (wd_legacy - wd_project) == set(),
        "raw_duplicate_occurrences": sum(len(raw[t]) for t in wd_expected_raw)
        - len(wd_expected_raw),
        "digests": {
            "project_total": digest(encoded(sorted(wd_project))),
            "legacy_total": digest(encoded(sorted(wd_legacy))),
            "nonself_matching": digest(encoded(sorted(wd_nonself_proj & wd_nonself_leg))),
            "project_only_self": digest(encoded(sorted(wd_self_proj))),
        },
    }

    # 4. AdminTo
    at_raw_direct = {
        t for t in raw if t[1] == "AdminTo" and any(r["rule"] == "LocalAdmins" for r in raw[t])
    }
    at_project = {t for t in c_triples if t[1] == "AdminTo"}
    at_legacy = {t for t in b_triples if t[1] == "AdminTo"}
    at_direct = {t for t in at_project if any(r["rule"] == "LocalAdmins" for r in raw.get(t, []))}
    at_derived_only = {
        t for t in at_project if not any(r["rule"] == "LocalAdmins" for r in raw.get(t, []))
    }
    at_coalesced = {t for t in at_direct if edges[t].get("derivation")}

    admin_to_proof = {
        "disposition_direct": "equivalent_in_accepted_scope",
        "disposition_derived": "accepted_policy_difference",
        "project_total": len(at_project),
        "legacy_total": len(at_legacy),
        "direct_matching_count": len(at_direct & at_legacy),
        "project_derived_only_count": len(at_derived_only),
        "coalesced_direct_and_derived_count": len(at_coalesced),
        "direct_exact_sets_equal": at_direct == at_legacy == at_raw_direct,
        "legacy_only_direct_empty": (at_legacy - at_direct) == set(),
        "project_only_equals_derived_only": (at_project - at_legacy) == at_derived_only,
        "all_derived_have_derivation": all(
            edges.get(t, {}).get("derivation") is not None for t in at_derived_only
        ),
        "all_derived_lack_direct_raw": all(
            not any(r["rule"] == "LocalAdmins" for r in raw.get(t, [])) for t in at_derived_only
        ),
        "digests": {
            "project_total": digest(encoded(sorted(at_project))),
            "legacy_total": digest(encoded(sorted(at_legacy))),
            "direct_matching": digest(encoded(sorted(at_direct & at_legacy))),
            "project_derived_only": digest(encoded(sorted(at_derived_only))),
        },
    }

    # 5. CanPSRemote
    ps_raw = {t for t in raw if t[1] == "CanPSRemote"}
    ps_project = {t for t in c_triples if t[1] == "CanPSRemote"}
    ps_legacy = {t for t in b_triples if t[1] == "CanPSRemote"}

    can_psremote_proof = {
        "status": "equivalent_in_accepted_scope",
        "project_count": len(ps_project),
        "legacy_count": len(ps_legacy),
        "matching_count": len(ps_project & ps_legacy),
        "project_only_count": len(ps_project - ps_legacy),
        "legacy_only_count": len(ps_legacy - ps_project),
        "exact_sets_equal": ps_project == ps_legacy == ps_raw,
        "project_only_empty": (ps_project - ps_legacy) == set(),
        "legacy_only_empty": (ps_legacy - ps_project) == set(),
        "digests": {
            "matching": digest(encoded(sorted(ps_project & ps_legacy))),
        },
    }

    # 6. CanRDP
    rdp_raw = {t for t in raw if t[1] == "CanRDP"}
    rdp_project = {t for t in c_triples if t[1] == "CanRDP"}
    rdp_legacy = {t for t in b_triples if t[1] == "CanRDP"}
    rdp_assessments = [a for k, a in assessments.items() if k[1] == "CanRDP"]
    rdp_assessment_triples = {(a["subject"], a["kind"], a["target"]) for a in rdp_assessments}
    rdp_status_unknown = len(rdp_assessments) == 3 and all(
        a.get("status") == "unknown" for a in rdp_assessments
    )
    rdp_reason_incomplete = all(
        a.get("reason") == "required UserRights evidence is incomplete" for a in rdp_assessments
    )
    rdp_userrights_absent = all(
        all(
            r.get("user_rights_present") is False
            for r in raw.get((a["subject"], a["kind"], a["target"]), [])
        )
        for a in rdp_assessments
    )

    can_rdp_proof = {
        "disposition": "accepted_policy_difference",
        "legacy_structural_edges": len(rdp_legacy),
        "project_positive_traversal_edges": len(rdp_project),
        "project_unknown_assessments_count": len(rdp_assessments),
        "legacy_equals_raw": rdp_legacy == rdp_raw,
        "assessments_equal_raw_and_legacy": rdp_assessment_triples == rdp_raw == rdp_legacy,
        "project_positive_edges_empty": rdp_project == set(),
        "all_assessments_status_unknown": rdp_status_unknown,
        "all_assessments_reason_incomplete": rdp_reason_incomplete,
        "all_raw_userrights_false": rdp_userrights_absent,
        "digests": {
            "legacy_only": digest(encoded(sorted(rdp_legacy))),
        },
    }

    # 7. ForceChangePassword & HasSession
    fcp_project = {t for t in c_triples if t[1] == "ForceChangePassword"}
    fcp_legacy = {t for t in b_triples if t[1] == "ForceChangePassword"}
    hs_project = {t for t in c_triples if t[1] == "HasSession"}
    hs_legacy = {t for t in b_triples if t[1] == "HasSession"}
    fcp_raw = {t for t in raw if t[1] == "ForceChangePassword"}
    hs_raw = {t for t in raw if t[1] == "HasSession"}

    zero_obs_proof = {
        "ForceChangePassword": {
            "disposition": "not_measurable",
            "project_observations": len(fcp_project),
            "legacy_observations": len(fcp_legacy),
            "raw_observations": len(fcp_raw),
            "all_zero": fcp_project == fcp_legacy == fcp_raw == set(),
        },
        "HasSession": {
            "disposition": "not_measurable",
            "project_observations": len(hs_project),
            "legacy_observations": len(hs_legacy),
            "raw_observations": len(hs_raw),
            "all_zero": hs_project == hs_legacy == hs_raw == set(),
        },
    }

    # 8. Outside-M1
    outside_kinds = sorted({t[1] for t in b_triples} - set(M1_RELATIONSHIPS))
    outside_ledger = {kind: len({t for t in b_triples if t[1] == kind}) for kind in outside_kinds}
    outside_total = sum(outside_ledger.values())

    outside_m1_proof = {
        "disposition": "unsupported",
        "outside_kinds": outside_kinds,
        "counts_by_kind": outside_ledger,
        "total_outside_relationships": outside_total,
    }

    # Multiplicity
    c_mult = asdict(graph_multiplicity(candidate, candidate.unique_triples))
    b_mult = asdict(graph_multiplicity(legacy, legacy.unique_triples))

    # Filter to M1 relationships
    c_m1 = {t for t in c_triples if t[1] in M1_RELATIONSHIPS}
    b_m1 = {t for t in b_triples if t[1] in M1_RELATIONSHIPS}

    # All 20 discrepancy classifications (sanitized, no authentic identities)
    differences = []
    for side, triples in (
        ("project_only", c_m1 - b_m1),
        ("legacy_only", b_m1 - c_m1),
    ):
        for triple in sorted(triples):
            rule_refs = list(raw.get(triple, []))
            edge = edges.get(triple)
            if edge and edge.get("derivation"):
                for path in edge["derivation"]["paths"]:
                    for step in path["steps"]:
                        k = "MemberOf" if step["operation"] == "effective_membership" else "AdminTo"
                        rule_refs.extend(raw.get((step["source"], k, step["target"]), []))
            classification = classify_difference(triple, side, raw, edges, assessments)
            triple_sha = digest(encoded(list(triple)))
            pointers = sorted({r["pointer"] for r in rule_refs if "pointer" in r})
            differences.append(
                {
                    "side": side,
                    "kind": triple[1],
                    "triple_digest": triple_sha,
                    "classification": classification,
                    "raw_rule_pointers": pointers,
                    "project_assessment_status": assessments.get(triple, {}).get("status"),
                }
            )

    return {
        "MemberOf": memberof_proof,
        "GenericAll": generic_all_proof,
        "WriteDacl": write_dacl_proof,
        "AdminTo": admin_to_proof,
        "CanPSRemote": can_psremote_proof,
        "CanRDP": can_rdp_proof,
        "zero_observation_limits": zero_obs_proof,
        "outside_m1": outside_m1_proof,
        "multiplicity": {"project": c_mult, "legacy": b_mult},
        "m1_difference_ledger": differences,
        "m1_exact_sets": {
            "project": {"count": len(c_m1), "digest": digest(encoded(sorted(c_m1)))},
            "legacy": {"count": len(b_m1), "digest": digest(encoded(sorted(b_m1)))},
            "matching": {"count": len(c_m1 & b_m1), "digest": digest(encoded(sorted(c_m1 & b_m1)))},
            "project_only": {
                "count": len(c_m1 - b_m1),
                "digest": digest(encoded(sorted(c_m1 - b_m1))),
            },
            "legacy_only": {
                "count": len(b_m1 - c_m1),
                "digest": digest(encoded(sorted(b_m1 - c_m1))),
            },
        },
    }


def execute_reproduction(
    raw_root: Path,
    manifest_path: Path,
    prerequisites_dir: Path,
    work_dir: Path,
    report_output: Path | None = None,
    python_exe: str = sys.executable,
) -> dict[str, Any]:
    work_dir.mkdir(parents=True, exist_ok=True)
    project_output = work_dir / "project.json"
    project_comp_path = work_dir / "project-comparison.json"

    require(
        not project_output.is_file(),
        f"clean reproduction boundary violation: {project_output} already exists; "
        "reusing pre-existing canonical output is strictly prohibited",
    )

    base_commit = ACCEPTED_DEVELOP_REVISION
    current_head = get_git_commit(ROOT)
    prereq_status = verify_external_prerequisites(raw_root, manifest_path, prerequisites_dir)

    # Step 1: Regenerate canonical graph from raw SEAMLESS
    regen = regenerate_canonical_graph(
        raw_root=raw_root,
        manifest_path=manifest_path,
        time_policy_path=prerequisites_dir / "time-policy.json",
        output_path=project_output,
        python_exe=python_exe,
    )

    # Step 2: Prepare project-comparison.json
    project_data = regen["graph_data"]
    validate_project(project_data)
    project_data["metadata"].update(
        synthetic=False,
        export_complete=True,
        source_evidence="data/samples/manifests/seamless-raw-v1.json",
        comparison_scope=COMPARISON_SCOPE,
    )
    comp_digest = write_json(project_comp_path, project_data)

    # Step 3: Run Comparator Gate
    legacy_comp_path = prerequisites_dir / "legacy-comparison.json"
    mapping_path = prerequisites_dir / "identity-mapping.json"
    baseline_data = load_input_json(legacy_comp_path)
    mapping_data = load_input_json(mapping_path)

    gate = reconcile_graphs(
        candidate_data=project_data,
        baseline_data=baseline_data,
        identity_mapping=mapping_data,
        candidate_name="project-comparison",
        baseline_name="legacy-comparison",
    )
    require(
        gate.verdict == "NOT_MEASURABLE",
        f"unexpected comparator verdict: {gate.verdict}",
    )
    require(
        "export_complete is not verified true" in gate.summary,
        f"unexpected comparator summary: {gate.summary}",
    )

    # Step 4: Compute per-slice proofs
    manifest = load_manifest(manifest_path)
    proofs = compute_per_slice_proofs(
        project_graph=project_data,
        baseline_graph=baseline_data,
        mapping=mapping_data,
        raw_root=raw_root,
        manifest=manifest,
    )

    # Assert exact directed-set invariants matching contract #195
    mo = proofs["MemberOf"]
    require(mo["exact_sets_equal"] is True, "MemberOf exact set equality failed")
    require(mo["members_count"] == 13324, "MemberOf members count != 13324")
    require(mo["primary_group_count"] == 2593, "MemberOf primary group count != 2593")
    require(mo["overlap_count"] == 0, "MemberOf overlap count != 0")
    require(mo["matching_count"] == 15917, "MemberOf matching count != 15917")
    require(mo["project_only_count"] == 0, "MemberOf project-only != 0")
    require(mo["legacy_only_count"] == 0, "MemberOf legacy-only != 0")

    ga = proofs["GenericAll"]
    require(ga["nonself_exact_sets_equal"] is True, "GenericAll non-self exact sets mismatch")
    require(ga["project_equals_raw_unique"] is True, "GenericAll project != raw unique")
    require(ga["legacy_equals_raw_unique_nonself"] is True, "GenericAll legacy != raw non-self")
    require(ga["project_only_equals_raw_self"] is True, "GenericAll project-only != raw self-ACE")
    require(ga["legacy_self_empty"] is True, "GenericAll legacy self-ACE is not empty")
    require(ga["legacy_only_empty"] is True, "GenericAll legacy-only is not empty")
    require(ga["nonself_matching_count"] == 37034, "GenericAll non-self matching != 37034")
    require(ga["project_only_self_count"] == 10, "GenericAll self-ACE != 10")

    wd = proofs["WriteDacl"]
    require(wd["nonself_exact_sets_equal"] is True, "WriteDacl non-self exact sets mismatch")
    require(wd["project_equals_raw_unique"] is True, "WriteDacl project != raw unique")
    require(wd["legacy_equals_raw_unique_nonself"] is True, "WriteDacl legacy != raw non-self")
    require(wd["project_only_equals_raw_self"] is True, "WriteDacl project-only != raw self-ACE")
    require(wd["legacy_self_empty"] is True, "WriteDacl legacy self-ACE is not empty")
    require(wd["legacy_only_empty"] is True, "WriteDacl legacy-only is not empty")
    require(wd["nonself_matching_count"] == 3392, "WriteDacl non-self matching != 3392")
    require(wd["project_only_self_count"] == 3, "WriteDacl self-ACE != 3")

    at = proofs["AdminTo"]
    require(
        at["direct_exact_sets_equal"] is True,
        "AdminTo direct exact set mismatch with raw LocalAdmins",
    )
    require(at["legacy_only_direct_empty"] is True, "AdminTo legacy-only direct rows not empty")
    require(
        at["project_only_equals_derived_only"] is True,
        "AdminTo project-only != reviewed derived-only set",
    )
    require(
        at["all_derived_have_derivation"] is True,
        "AdminTo derived-only missing derivation in edge",
    )
    require(
        at["all_derived_lack_direct_raw"] is True,
        "AdminTo derived-only has direct LocalAdmins raw support",
    )
    require(at["direct_matching_count"] == 5, "AdminTo direct matching != 5")
    require(at["project_derived_only_count"] == 4, "AdminTo derived-only != 4")
    require(at["coalesced_direct_and_derived_count"] == 1, "AdminTo coalesced != 1")

    ps = proofs["CanPSRemote"]
    require(ps["exact_sets_equal"] is True, "CanPSRemote exact set mismatch with raw PSRemoteUsers")
    require(ps["project_only_empty"] is True, "CanPSRemote project-only not empty")
    require(ps["legacy_only_empty"] is True, "CanPSRemote legacy-only not empty")
    require(ps["matching_count"] == 2, "CanPSRemote matching != 2")

    rdp = proofs["CanRDP"]
    require(rdp["legacy_equals_raw"] is True, "CanRDP legacy set != raw RemoteDesktopUsers")
    require(
        rdp["assessments_equal_raw_and_legacy"] is True,
        "CanRDP assessment triples != raw and legacy",
    )
    require(
        rdp["project_positive_edges_empty"] is True,
        "CanRDP project positive traversal edges not empty",
    )
    require(
        rdp["all_assessments_status_unknown"] is True,
        "CanRDP assessments not all status unknown",
    )
    require(
        rdp["all_assessments_reason_incomplete"] is True,
        "CanRDP reason semantics mismatch",
    )
    require(rdp["all_raw_userrights_false"] is True, "CanRDP raw userrights not all False")
    require(rdp["legacy_structural_edges"] == 3, "CanRDP legacy edges != 3")
    require(rdp["project_unknown_assessments_count"] == 3, "CanRDP unknown assessments != 3")

    fcp = proofs["zero_observation_limits"]["ForceChangePassword"]
    hs = proofs["zero_observation_limits"]["HasSession"]
    require(fcp["all_zero"] is True, "FCP observations != 0")
    require(hs["all_zero"] is True, "HasSession observations != 0")

    outside = proofs["outside_m1"]
    require(outside["total_outside_relationships"] == 15243, "Outside-M1 count != 15243")

    # Build Sanitized Report Artifact
    report = {
        "schema_version": 1,
        "reproduction_task": "issue-196-final-clean-checkout-cross-reproduction",
        "analysis_date": datetime.now(UTC).strftime("%Y-%m-%d"),
        "base_develop_revision": base_commit,
        "head_commit": current_head,
        "snapshot_id": ACCEPTED_SNAPSHOT,
        "runtime_environment": {
            "python_version": sys.version.split()[0],
            "platform": sys.platform,
            "contract_version": "1.3.0",
            "time_policy_digest": ACCEPTED_TIME_POLICY_DIGEST,
        },
        "prerequisites_classification": prereq_status,
        "generated_in_this_run": {
            "canonical_graph_digest": regen["output_digest"],
            "comparison_candidate_digest": comp_digest,
            "node_counts": regen["node_counts"],
            "edge_counts": regen["edge_counts"],
            "assessment_counts": {"unknown": regen["assessment_total"]},
        },
        "comparator_gate": {
            "raw_verdict": gate.verdict,
            "raw_summary": gate.summary,
            "expected_exit_code": 2,
            "status": "expected_not_measurable_pending_full_semantics_gate",
        },
        "comparison_contract_binding": {
            "document": "docs/research/seamless-legacy-403-comparison-contract.md",
            "contract_version": "seamless-legacy-403-m1-common-v1",
            "refs": ["#195", "#194", "#189", "#184", "#183", "#47", "#48"],
        },
        "per_slice_results": {
            "MemberOf": proofs["MemberOf"],
            "GenericAll": proofs["GenericAll"],
            "WriteDacl": proofs["WriteDacl"],
            "AdminTo": proofs["AdminTo"],
            "CanPSRemote": proofs["CanPSRemote"],
            "CanRDP": proofs["CanRDP"],
            "ForceChangePassword": proofs["zero_observation_limits"]["ForceChangePassword"],
            "HasSession": proofs["zero_observation_limits"]["HasSession"],
            "outside_m1": proofs["outside_m1"],
        },
        "m1_exact_sets": proofs["m1_exact_sets"],
        "m1_difference_ledger": proofs["m1_difference_ledger"],
        "multiplicity": proofs["multiplicity"],
        "sanitization_statement": (
            "Deterministic sanitized evidence. No authentic Active Directory identities, "
            "raw names, unhashed credentials, or secrets are present in this artifact."
        ),
    }

    if report_output:
        report_output.parent.mkdir(parents=True, exist_ok=True)
        report_json = json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False)
        report_output.write_text(report_json + "\n", encoding="utf-8")

    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-root", type=Path, default=ROOT / "data/raw/SEAMLESS")
    parser.add_argument(
        "--manifest", type=Path, default=ROOT / "data/samples/manifests/seamless-raw-v1.json"
    )
    parser.add_argument("--prerequisites-dir", type=Path, required=True)
    parser.add_argument("--work-dir", type=Path, required=True)
    parser.add_argument("--report-output", type=Path)
    parser.add_argument("--python-exe", default=sys.executable)
    args = parser.parse_args()

    try:
        report = execute_reproduction(
            raw_root=args.raw_root,
            manifest_path=args.manifest,
            prerequisites_dir=args.prerequisites_dir,
            work_dir=args.work_dir,
            report_output=args.report_output,
            python_exe=args.python_exe,
        )
        print(
            json.dumps(
                {
                    "status": "PASS",
                    "base_commit": report["base_develop_revision"],
                    "canonical_graph_digest": report["generated_in_this_run"][
                        "canonical_graph_digest"
                    ],
                    "comparator_verdict": report["comparator_gate"]["raw_verdict"],
                    "memberof_matching": report["per_slice_results"]["MemberOf"]["matching_count"],
                    "genericall_nonself_matching": report["per_slice_results"]["GenericAll"][
                        "nonself_matching_count"
                    ],
                    "writedacl_nonself_matching": report["per_slice_results"]["WriteDacl"][
                        "nonself_matching_count"
                    ],
                    "adminto_direct_matching": report["per_slice_results"]["AdminTo"][
                        "direct_matching_count"
                    ],
                    "canpsremote_matching": report["per_slice_results"]["CanPSRemote"][
                        "matching_count"
                    ],
                    "outside_m1_count": report["per_slice_results"]["outside_m1"][
                        "total_outside_relationships"
                    ],
                },
                indent=2,
            )
        )
    except Exception as exc:
        print(f"Reproduction failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
