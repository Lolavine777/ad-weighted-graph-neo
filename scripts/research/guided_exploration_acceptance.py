"""Manifest-verified SEAMLESS acceptance; private traces stay in ignored output.

Run as python -m scripts.research.guided_exploration_acceptance --help.
Only the allowlisted summary is suitable for review/publication.
"""

import argparse
import copy
import hashlib
import importlib.metadata
import json
import os
import platform
import subprocess
import time
from pathlib import Path

from scripts.research.asrep_inputs import seamless_inputs
from src.data.manifest import load_manifest, verify_manifest
from src.engine import EngineGraph, materialize_query
from src.engine.exploration import (
    build_scenario_template,
    inspect_structural_edge,
    inspect_transition,
    query_with_proposals,
    scenario_proposals,
    structural_exploration,
)
from src.engine.query_cli import canonical_json, execute, wire
from src.engine.semantics.evaluator import candidates
from src.engine.semantics.transitions import TransitionRequest
from src.parser.snapshot_facts import serialize_snapshot

ROOT = Path(__file__).resolve().parents[2]


def digest(value):
    return "sha256:" + hashlib.sha256(canonical_json(value).encode()).hexdigest()


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(wire(value), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def scope(query):
    return {k: v for k, v in query.items() if k not in {"assumptions", "evaluation_mode"}}


def resolve_label(graph, label):
    if not isinstance(label, str) or not label.strip():
        raise ValueError("case B requires unique exact-snapshot labels")
    matches = [
        n for n in graph.nodes() if n["label"].upper().split("@")[0].split(".")[0] == label.upper()
    ]
    if len(matches) != 1:
        raise ValueError("case B requires unique exact-snapshot labels")
    return matches[0]


def run_acceptance(raw_dir, output_dir, *, source_label=None, target_label=None):
    # Refuse accidental publication of canonical identifiers, queries or states.
    output_dir = Path(output_dir).resolve()
    private_root = (ROOT / "reports/generated").resolve()
    if not output_dir.is_relative_to(private_root):
        raise ValueError("private output must be inside this checkout's reports/generated")
    output_dir.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    manifest_path = ROOT / "data/samples/manifests/seamless-raw-v1.json"
    summary = {
        "kind": "real_SEAMLESS_backend_acceptance",
        "code_revision": revision,
        "runtime": {"python": platform.python_version(), "platform": platform.system()},
        "dependencies": {
            k: importlib.metadata.version(k) for k in ("networkx", "PyYAML", "pytest", "ruff")
        },
        "case_scopes": {
            "A": (
                "Helper C0 Computer actor/AS-REP request capability; known V_A; "
                "admin_control(C0); effective_member(V_A,G_DA) checkpoint"
            ),
            "B": (
                "Unique requested labels resolved locally as B_SOURCE(User) -> B_TARGET(Computer); "
                "declared control(B_SOURCE) only; auth context C0; admin_control(B_TARGET); "
                "all catalog techniques; no runtime facts/assumptions/rating input"
            ),
        },
        "matrix": [],
        "cases": {},
        "limits": [
            "Bounded declared scopes only; no all-source coverage or global optimum.",
            "Case A template is helper-declared, pending maintainer adoption; never used in B.",
            "Case B has no reviewed assumptions template; diagnostics only.",
            "Veto is a separate experimental runtime view, not SEAMLESS observed evidence.",
            "HTTP/UI/live comparison acceptance remains pending #279.",
        ],
    }
    summary["executable_tree_digest"] = digest(
        {
            str(p.relative_to(ROOT)).replace("\\", "/"): hashlib.sha256(p.read_bytes()).hexdigest()
            for folder in ("src", "configs")
            for p in sorted((ROOT / folder).rglob("*"))
            if p.is_file() and p.suffix in {".py", ".json", ".yml", ".yaml"}
        }
    )
    summary["runner_digest"] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()

    def check(name, expected, observed, passed, ref, category="SEAMLESS"):
        row = dict(
            check=name,
            expected=expected,
            observed=observed,
            status="PASS" if passed else "FAIL",
            evidence=ref,
            category=category,
        )
        summary["matrix"].append(row)
        save(output_dir / "summary-progress.json", summary)
        print(name, row["status"], flush=True)

    summary["config_identity"] = digest(
        {
            str(p.relative_to(ROOT)).replace("\\", "/"): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in [
                manifest_path,
                ROOT / "requirements-tests.txt",
                ROOT / "requirements-dev.txt",
                ROOT / "requirements.txt",
                ROOT / "scripts/research/asrep_inputs.py",
                ROOT / "tests/fixtures/ranking/seamless_time_policy.json",
            ]
        }
    )
    try:
        manifest = load_manifest(manifest_path)
        summary["snapshot_id"] = manifest["snapshot_id"]
        before = verify_manifest(Path(raw_dir), manifest)
    except OSError, ValueError:
        before = ["missing or invalid raw/manifest prerequisite"]
    if before:
        summary["matrix"].append(
            dict(
                check="manifest",
                expected="valid pinned raw snapshot",
                observed="missing or invalid dataset",
                status="BLOCKED",
                evidence="manifest verifier",
            )
        )
        summary["status"] = "BLOCKED"
        return summary
    before_hashes = {
        p.name: hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(Path(raw_dir).rglob("*"))
        if p.is_file()
    }
    save(output_dir / "raw-integrity-before.json", before_hashes)
    graph, raw, assumed, trace = seamless_inputs(raw_dir, revision)
    raw = {**raw, "evaluation_mode": "evidence_only", "assumptions": []}
    (output_dir / "snapshot.json").write_text(
        serialize_snapshot(graph.to_canonical(), graph.snapshot_facts), encoding="utf-8"
    )
    save(output_dir / "helper-trace.json", trace)
    summary["graph_identity"] = digest(graph.to_canonical())
    summary["facts_identity"] = digest(wire(graph.snapshot_facts))
    summary["graph_counts"] = {"nodes": len(graph.nodes()), "edges": len(graph.edges())}
    actor, victim, group = (
        raw["initial_actor"],
        raw["initial_state"]["known_identity"][0],
        raw["checkpoint_goal"]["target"],
    )
    check(
        "A_helper_scope",
        "Computer C0 / known V_A / target C0; nine assumptions",
        "canonical scope verified locally",
        graph.node(actor)["kind"] == "Computer"
        and actor == raw["target"]
        and graph.node(victim)["kind"] == "User"
        and len(assumed["assumptions"]) == 9,
        "helper-trace.json; A/raw.json",
    )

    def run(name, query):
        result = execute(query, graph)  # public materializer -> run_attack_query
        save(output_dir / f"{name}.json", result)
        info = {
            k: result[k]
            for k in (
                "status",
                "final_goal_reached",
                "checkpoint_reached",
                "caps",
                "complete",
                "truncated",
                "truncation_reason",
                "expansions",
                "ranking_disposition",
                "engine_reported_guarantees",
            )
        }
        info["candidate_count"] = len(result["candidates"])
        info["numeric_rating_available"] = result["ranking_result"] is not None
        info["numeric_effort_available"] = result["min_effort"] is not None
        info["scope_digest"] = digest(scope(query))
        summary["cases"][name] = info
        print(name, result["status"], len(result["candidates"]), flush=True)
        return result

    baseline = run("A/raw", raw)
    structural_a = structural_exploration(raw, graph)
    save(output_dir / "A/structural.json", structural_a)
    summary["cases"]["A/structural"] = {
        k: structural_a[k]
        for k in ("kind", "budget", "expansions", "complete", "truncated", "truncation_reason")
    }
    summary["cases"]["A/structural"].update(path_count=len(structural_a["paths"]), edge_counts=[0])
    check(
        "A_RAW_and_degenerate_structure",
        "RAW unresolved; singleton structural_only",
        {
            "status": baseline["status"],
            "candidates": len(baseline["candidates"]),
            "structural_paths": len(structural_a["paths"]),
        },
        not baseline["final_goal_reached"]
        and structural_a["kind"] == "structural_only"
        and structural_a["paths"][0]["nodes"] == [actor],
        "A/raw.json; A/structural.json",
    )
    template = build_scenario_template(
        raw, graph, assumed["assumptions"], template_id="seamless-228-helper-C0"
    )
    proposals = scenario_proposals(template, raw, graph)
    save(output_dir / "A/template.json", template)
    save(output_dir / "A/proposals.json", proposals)
    check(
        "A_unchecked_proposals",
        "nine unchecked; ledger retained",
        {"count": len(proposals["proposals"]), "rejected": len(proposals["rejected_assumptions"])},
        len(proposals["proposals"]) == 9 and all(not p["selected"] for p in proposals["proposals"]),
        "A/proposals.json",
    )
    ids = [p["proposal_id"] for p in proposals["proposals"]]
    dropped = [
        p["proposal_id"]
        for p in proposals["proposals"]
        if p["assumption"]["predicate"] != "recovery_success"
    ]
    selections = {}
    results = {}
    for name, selected in (("none", []), ("full", ids), ("drop-recovery", dropped)):
        query = query_with_proposals(template, raw, graph, selected)
        selections[name] = query
        results[name] = run(f"A/{name}", query)
        check(
            f"A_{name}_scope",
            "only assumptions/evaluation_mode change",
            "scope identical",
            scope(query) == scope(raw),
            f"A/{name}.json",
        )
    check(
        "A_empty_rerun",
        "no goal without proposals",
        results["none"]["status"],
        not results["none"]["final_goal_reached"],
        "A/none.json",
    )
    check(
        "A_full_rerun",
        "conditional goal from actual rerun",
        results["full"]["status"],
        results["full"]["final_goal_reached"],
        "A/full.json",
    )
    first = TransitionRequest("asrep_request", actor, actor, victim)
    recovery = TransitionRequest("recover_asrep_secret", actor, actor, victim)
    activate = TransitionRequest("activate_recovered_identity", victim, victim, actor)
    membership = TransitionRequest("propagate_group_entitlement", victim, victim, group)
    admin = TransitionRequest("obtain_admin_execution_on_host", victim, victim, actor)
    chain = [first, recovery, activate, membership, admin]
    raw_probe = inspect_transition(raw, graph, recovery, prefix=[first])
    save(output_dir / "A/raw-prefix.json", raw_probe)
    check(
        "A_unknown_prefix_stops",
        "indeterminate; no suffix/effects",
        raw_probe["prefix_status"],
        raw_probe["prefix_status"] == "indeterminate"
        and not raw_probe["options"]
        and all(p["before"] == p["after"] for p in raw_probe["prefix"]),
        "A/raw-prefix.json",
    )
    for i, req in enumerate(chain):
        probe = inspect_transition(selections["full"], graph, req, prefix=chain[:i])
        save(output_dir / f"A/full-step-{i}.json", probe)
        check(
            f"A_applicable_step_{i}",
            "applicable after exact replay",
            probe["options"][0]["status"] if probe["options"] else probe["prefix_status"],
            bool(probe["options"]) and probe["options"][0]["status"] == "applicable",
            f"A/full-step-{i}.json",
        )
    probe = inspect_transition(selections["drop-recovery"], graph, recovery, prefix=[first])
    save(output_dir / "A/drop-recovery-probe.json", probe)
    action = probe["options"][0]
    suffix = inspect_transition(
        selections["drop-recovery"], graph, activate, prefix=[first, recovery]
    )
    save(output_dir / "A/drop-recovery-suffix.json", suffix)
    bypasses = [
        [s["result"]["request"]["technique_id"] for s in p["transition_history"]]
        for p in results["drop-recovery"]["candidates"]
    ]
    check(
        "A_drop_recovery_no_fake_effects",
        "recovery unresolved; suffix stopped; report bypass",
        {
            "recovery": action["status"],
            "query": results["drop-recovery"]["status"],
            "bypass_programs": bypasses,
        },
        "recovery_success" in action["unknown"]
        and not action["after"]["recovered_secret"]
        and not suffix["options"],
        "A/drop-recovery.json; A/drop-recovery-probe.json; A/drop-recovery-suffix.json",
    )

    invalid = []
    for field in ("source_foothold", "initial_actor", "target", "initial_state", "budget"):
        changed = copy.deepcopy(raw)
        changed[field] = {"invalid": True} if isinstance(changed[field], dict) else victim
        try:
            scenario_proposals(template, changed, graph)
        except ValueError:
            invalid.append(field)
    no_facts = EngineGraph.from_canonical(graph.to_canonical())
    try:
        scenario_proposals(template, raw, no_facts)
    except ValueError:
        invalid.append("SnapshotFacts")
    for label, selection in (("duplicate", ids[:1] * 2), ("unknown", ["unknown"])):
        try:
            query_with_proposals(template, raw, graph, selection)
        except ValueError:
            invalid.append(label)
    save(output_dir / "A/scope-controls.json", invalid)
    check(
        "A_scope_and_ID_controls",
        "eight rejections",
        invalid,
        len(invalid) == 8,
        "A/scope-controls.json",
    )

    veto_fact = next(
        a for a in assumed["assumptions"] if a["predicate"] == "asrep_request_accepted"
    )
    veto_raw = {
        **raw,
        "runtime_facts": [
            {
                **veto_fact,
                "value": False,
                "origin": "blocked_evidence",
                "provenance_reference": "control://287/veto",
            }
        ],
    }
    veto_template = build_scenario_template(
        veto_raw, graph, assumed["assumptions"], template_id="experimental-veto-only"
    )
    ledger = scenario_proposals(veto_template, veto_raw, graph)
    save(output_dir / "control/proposals.json", ledger)
    veto_query = query_with_proposals(veto_template, veto_raw, graph, ids)
    veto_result = run("control/veto", veto_query)
    veto_probe = inspect_transition(veto_query, graph, recovery, prefix=[first])
    save(output_dir / "control/probe.json", veto_probe)
    check(
        "known_false_veto",
        "ledger rejection; blocked prefix; no material; real rerun",
        {"prefix": veto_probe["prefix_status"], "query": veto_result["status"]},
        any(r["reason"] == "known_false_veto" for r in ledger["rejected_assumptions"])
        and veto_probe["prefix_status"] == "blocked"
        and not veto_probe["options"]
        and not veto_probe["state"]["asrep_material"]
        and bool(veto_result["materialized"]["rejected_assumptions"])
        and all(
            a["status"] != "applicable"
            for a in veto_result["attempts"]
            if a["request"]["technique_id"] == "asrep_request"
        ),
        "control/proposals.json; control/probe.json; control/veto.json",
        "experimental_control",
    )

    try:
        source = resolve_label(
            graph, source_label or os.environ.get("GUIDED_SEAMLESS_SOURCE_LABEL")
        )
        target = resolve_label(
            graph, target_label or os.environ.get("GUIDED_SEAMLESS_TARGET_LABEL")
        )
        save(output_dir / "B/bindings.json", {"B_SOURCE": source, "B_TARGET": target})
        check(
            "B_node_kinds",
            "User source; Computer admin-control target",
            [source["kind"], target["kind"]],
            source["kind"] == "User" and target["kind"] == "Computer",
            "B/bindings.json",
        )
        b = {
            "initial_actor": source["id"],
            "source_foothold": source["id"],
            "target": target["id"],
            "target_goal": {
                "target": target["id"],
                "required_state": {"admin_control": [target["id"]]},
            },
            "initial_state": {"control": [source["id"]]},
            "authentication_context": actor,
            "runtime_facts": [],
            "assumptions": [],
            "evaluation_mode": "evidence_only",
            "budget": {"max_paths": 10, "max_steps": 9, "max_expansions": 5000},
            "scenario_reference": "287-B-declared-control-no-secret-or-identity",
        }
        b_result = run("B/raw", b)
        structure = structural_exploration(b, graph)
        save(output_dir / "B/structural.json", structure)
        edges = {e["id"]: e for e in graph.edges()}
        valid = all(
            p["nodes"][0] == source["id"]
            and p["nodes"][-1] == target["id"]
            and all(
                e == edges[e["id"]]
                and e["provenance"]
                and (e["source"], e["target"]) == (p["nodes"][i], p["nodes"][i + 1])
                for i, e in enumerate(p["edges"])
            )
            for p in structure["paths"]
        )
        summary["cases"]["B/structural"] = {
            k: structure[k]
            for k in ("kind", "budget", "expansions", "complete", "truncated", "truncation_reason")
        }
        summary["cases"]["B/structural"]["path_count"] = len(structure["paths"])
        summary["cases"]["B/structural"]["edge_counts"] = [
            len(p["edges"]) for p in structure["paths"]
        ]
        check(
            "B_real_multistep_structure",
            "exact graph/provenance; structural_only independent of candidates",
            {"paths": len(structure["paths"]), "semantic_candidates": len(b_result["candidates"])},
            valid
            and structure["kind"] == "structural_only"
            and any(len(p["edges"]) > 1 for p in structure["paths"]),
            "B/raw.json; B/structural.json",
        )
        direct_valid = True
        for i, edge in enumerate(structure["paths"][0]["edges"] if structure["paths"] else []):
            probe = inspect_structural_edge(b, graph, edge["id"])
            save(output_dir / f"B/edge-{i}.json", probe)
            expected = candidates(
                edge["kind"],
                graph.node(edge["source"])["kind"],
                graph.node(edge["target"])["kind"],
                materialize_query(b, graph).catalog,
            )
            direct_valid &= [o["request"]["technique_id"] for o in probe["options"]] == [
                t.id for t in expected
            ]
            direct_valid &= all(
                o["request"]["source"] == edge["source"]
                and o["request"]["target"] == edge["target"]
                and (o["status"] == "applicable" or o["before"] == o["after"])
                for o in probe["options"]
            )
        check(
            "B_exact_edge_catalog",
            "direct options match catalog/bindings; no fabricated effects",
            "catalog and bindings compared",
            direct_valid and bool(structure["paths"]),
            "B/edge-*.json",
        )
        if structure["paths"] and len(structure["paths"][0]["edges"]) > 1:
            first_edge, next_edge = structure["paths"][0]["edges"][:2]
            first_options = inspect_structural_edge(b, graph, first_edge["id"])["options"]
            chosen = first_options[0]["request"]
            request = TransitionRequest(**chosen)
            halted = inspect_structural_edge(b, graph, next_edge["id"], prefix=[request])
            save(output_dir / "B/halted-prefix.json", halted)
            check(
                "B_unknown_structural_prefix",
                "stop at unresolved GenericAll; no suffix options",
                halted["prefix_status"],
                halted["prefix_status"] == "indeterminate"
                and not halted["options"]
                and halted["prefix"][0]["before"] == halted["prefix"][0]["after"],
                "B/halted-prefix.json",
            )
        tiny = {**b, "budget": {"max_paths": 1, "max_steps": 1, "max_expansions": 1}}
        limited = structural_exploration(tiny, graph)
        save(output_dir / "B/tiny-structural.json", limited)
        tiny_result = run("B/tiny-semantic", tiny)
        probe = inspect_transition(
            {**raw, "budget": tiny["budget"]}, graph, recovery, prefix=[first]
        )
        save(output_dir / "control/tiny-probe.json", probe)
        check(
            "small_budget",
            "truncated/not-evaluated; no false completeness/no-path",
            {
                "structural": limited["truncated"],
                "semantic": tiny_result["status"],
                "probe": probe["prefix_status"],
            },
            limited["truncated"]
            and not limited["complete"]
            and tiny_result["truncated"]
            and not tiny_result["complete"]
            and probe["prefix_status"] == "not_evaluated"
            and not probe["options"],
            "B/tiny-structural.json; B/tiny-semantic.json; control/tiny-probe.json",
        )
    except ValueError as exc:
        if str(exc) != "case B requires unique exact-snapshot labels":
            raise
        summary["matrix"].append(
            dict(
                check="B_exact_snapshot_nodes",
                expected="unique real nodes",
                observed="required labels absent or ambiguous",
                status="BLOCKED",
                evidence="snapshot.json",
            )
        )
    check(
        "numeric_boundary",
        "unrated without rating basis; no numeric P from True",
        {name: result["ranking_disposition"] for name, result in results.items()},
        all(
            r["ranking_disposition"] == "unrated"
            and r["ranking_result"] is None
            and r["min_effort"] is None
            for r in results.values()
        ),
        "A/none.json; A/full.json; A/drop-recovery.json",
    )
    after_hashes = {
        p.name: hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(Path(raw_dir).rglob("*"))
        if p.is_file()
    }
    save(output_dir / "raw-integrity-after.json", after_hashes)
    check(
        "raw_integrity",
        "same bytes; official verifier before/after clean",
        "unchanged",
        before_hashes == after_hashes and not verify_manifest(Path(raw_dir), manifest),
        "raw-integrity-before.json; raw-integrity-after.json",
    )
    summary["raw_checksums"] = before_hashes  # Manifest filenames are already reviewed public.
    summary["evidence_digests"] = {
        p.relative_to(output_dir).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(output_dir.rglob("*.json"))
        if p.name not in {"summary.json", "summary-progress.json"}
    }
    summary["elapsed_seconds"] = round(time.perf_counter() - started, 3)
    summary["status"] = (
        "FAIL"
        if any(r["status"] == "FAIL" for r in summary["matrix"])
        else "BLOCKED"
        if any(r["status"] == "BLOCKED" for r in summary["matrix"])
        else "PASS"
    )
    save(output_dir / "summary.json", summary)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--sanitized-report", type=Path, required=True)
    parser.add_argument("--source-label", help="Private exact-snapshot label for case B source")
    parser.add_argument("--target-label", help="Private exact-snapshot label for case B target")
    args = parser.parse_args()
    summary = run_acceptance(
        args.raw_dir,
        args.output_dir,
        source_label=args.source_label,
        target_label=args.target_label,
    )
    save(args.sanitized_report, summary)
    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
