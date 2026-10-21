"""Measure real scoped search/adapter output for #180; not the #179 acceptance gate."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.research.reviewed_parameter_release import verify_release  # noqa: E402
from src.data.manifest import verify_manifest  # noqa: E402
from src.engine import EngineGraph, SearchBudget, generate_attack_paths  # noqa: E402
from src.engine.ranking.orchestration import (  # noqa: E402
    coverage_from_search_result,
    evaluate_search_candidates,
)
from src.engine.semantics import load_catalog  # noqa: E402
from src.engine.semantics.evidence_view import counterfactual_view, digest  # noqa: E402
from src.engine.semantics.week3 import runtime_for_projection  # noqa: E402

PLAN = ROOT / "docs/research/ratings/week3-closeout/semantic-bridge-plan.json"


def load_acceptance_inputs(root: Path, plan: dict):
    """Consume #179's accepted pin and verify the exact fixture before probing."""
    reference = plan["acceptance_manifest"]
    if set(reference) != {"accepted_plan_path"}:
        raise ValueError("bridge must reference the accepted plan, not duplicate manifest pins")
    accepted_path = root / reference["accepted_plan_path"]
    accepted_bytes = accepted_path.read_bytes()
    accepted = json.loads(accepted_bytes)
    if accepted["release_digest"] != plan["release_digest"]:
        raise ValueError("accepted plan release digest mismatch")
    pin = accepted["acceptance_manifest"]
    manifest_bytes = (root / pin["path"]).read_bytes()
    blob_sha = hashlib.sha1(
        b"blob " + str(len(manifest_bytes)).encode() + b"\0" + manifest_bytes
    ).hexdigest()
    if blob_sha != pin["blob_sha"]:
        raise ValueError("acceptance manifest blob pin mismatch")
    manifest = json.loads(manifest_bytes)
    if digest(manifest) != pin["canonical_digest"]:
        raise ValueError("acceptance manifest canonical pin mismatch")
    if manifest["release"]["digest"] != plan["release_digest"]:
        raise ValueError("acceptance manifest release digest mismatch")
    if {case["case_id"] for case in manifest["cases"]} != set(plan["cases"]):
        raise ValueError("bridge case IDs differ from accepted manifest")
    return manifest, {
        "accepted_plan": {
            "path": reference["accepted_plan_path"],
            "file_sha256": hashlib.sha256(accepted_bytes).hexdigest(),
            "canonical_digest": digest(accepted),
        },
        "acceptance_manifest": {
            **pin,
            "file_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
        },
    }


def overlay(payload, operations):
    result = deepcopy(payload)
    for patch in operations:
        parts = patch["path"].lstrip("/").split("/")
        parent = result
        for part in parts[:-1]:
            parent = parent[int(part)] if isinstance(parent, list) else parent[part]
        key = parts[-1]
        if patch["op"] == "remove":
            del parent[int(key) if isinstance(parent, list) else key]
        elif patch["op"] == "add" and isinstance(parent, list) and key == "-":
            parent.append(deepcopy(patch["value"]))
        else:
            raise ValueError("unsupported reviewed overlay")
    return result


def run_case(graph, release, plan, case, *, raw_dir, raw_manifest):
    source = plan["sources"][case["source"]]
    config = plan["cases"][case["case_id"]]
    payload = overlay(release["query_projections"][case["source"]], case["overlay"])
    if digest(payload) != case["input"]["overlaid_digest"]:
        raise ValueError("case overlay digest mismatch")
    view = counterfactual_view(
        graph,
        config.get("evidence_view"),
        case_id=case["case_id"],
        raw_dir=raw_dir,
        manifest=raw_manifest,
    )
    state, context = runtime_for_projection(
        payload["query"], source, config, withheld_relationships=view.withheld_relationships
    )
    budget = SearchBudget(**source["budget"])
    catalog = tuple(t for t in load_catalog() if t.id in source["semantic_catalog"])
    generated = generate_attack_paths(
        EngineGraph.from_canonical(view.graph),
        source["actor"],
        initial_state=state,
        runtime_context=context,
        target_predicate=lambda n: n["id"] == source["target"],
        success_state_predicate=lambda s: source["target"] in s.admin_control,
        budget=budget,
        catalog=catalog,
        scenario_reference=payload["query"]["query_metadata"]["scenario_id"],
    )
    bindings = {
        (b["technique_id"], b["actor"], b["source"], b["target"]): b["action_id"]
        for b in source["transition_action_bindings"]
    }
    oracle_sequences = {
        tuple(c["bound_action_ids"]): c["candidate_id"] for c in payload["candidates"]
    }
    candidates, programs, unbound = [], [], []
    for index, path in enumerate(generated.paths):
        actions = []
        for step in path.transition_history:
            req = step.result.request
            key = (req.technique_id, req.actor, req.source, req.target)
            if key not in bindings:
                unbound.append({"path_index": index, "transition": list(key)})
                break
            actions.append(bindings[key])
        else:
            # Labels may match an oracle only after exact ordered binding identity;
            # PathResults always originate from the invocation above.
            cid = oracle_sequences.get(tuple(actions), f"generated_{index:04d}")
            candidates.append(
                {
                    "candidate_id": cid,
                    "target_asset_id": source["target"],
                    "path_result": path,
                    "action_mapping": actions,
                }
            )
            programs.append(
                {
                    "candidate_id": cid,
                    "actions": actions,
                    "work_ids": [
                        work
                        for action_id in actions
                        for a in payload["query"]["bound_actions"]
                        if a["action_id"] == action_id
                        for work in a["referenced_work_unit_ids"]
                    ],
                }
            )
    ranked = evaluate_search_candidates(
        payload["query"],
        candidates,
        canonical_graph=view.graph,
        coverage=coverage_from_search_result(generated, budget),
    )
    ranked = ranked["roundtrip_result"]
    attempts = []
    for result in generated.attempts:
        req = result.request
        attempts.append(
            {
                "technique_id": req.technique_id,
                "actor": req.actor,
                "source": req.source,
                "target": req.target,
                "status": result.status,
                "failed": list(result.failed),
                "unknown": list(result.unknown),
                "decisions": [
                    {
                        "predicate": d.predicate,
                        "satisfied": d.satisfied,
                        "origin": d.origin,
                        "rationale": d.rationale,
                        "value": d.fact.value if d.fact else None,
                        "scope": d.fact.scope if d.fact else None,
                        "subject": d.fact.subject if d.fact else req.actor,
                        "target": d.fact.target if d.fact else req.target,
                    }
                    for d in result.decisions
                ],
            }
        )
    return {
        "case_id": case["case_id"],
        "candidate_source": "generate_attack_paths",
        "mapping_review": plan["mapping_review"],
        "evidence_view": view.audit,
        "caps": source["budget"],
        "expansions": generated.expansions,
        "truncated": generated.truncated,
        "truncation_reason": generated.truncation_reason,
        "programs": programs,
        "unbound": unbound,
        "ranking": ranked,
        "attempts": attempts,
        "non_claim": "Probe only; final #179 acceptance and A overlay review remain required.",
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--graph", type=Path, required=True)
    parser.add_argument("--raw-dir", type=Path, required=True)
    parser.add_argument("--case-id", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    plan = json.loads(PLAN.read_text(encoding="utf-8"))
    manifest, acceptance_pins = load_acceptance_inputs(ROOT, plan)
    release_path = ROOT / manifest["release"]["path"]
    if hashlib.sha256(release_path.read_bytes()).hexdigest() != manifest["release"]["file_sha256"]:
        raise ValueError("release file pin mismatch")
    release = verify_release(json.loads(release_path.read_text(encoding="utf-8")))
    if release["bundle_metadata"]["bundle_digest"] != plan["release_digest"]:
        raise ValueError("release digest mismatch")
    raw_manifest = json.loads(
        (ROOT / manifest["release"]["raw_manifest"]["path"]).read_text(encoding="utf-8")
    )
    if digest(raw_manifest) != manifest["release"]["raw_manifest"]["canonical_digest"]:
        raise ValueError("raw manifest pin mismatch")
    discrepancies = verify_manifest(args.raw_dir, raw_manifest)
    if discrepancies:
        raise ValueError(f"raw input differs from pinned manifest: {discrepancies}")
    graph = json.loads(args.graph.read_text(encoding="utf-8"))
    if graph["metadata"]["snapshot_id"] != raw_manifest["snapshot_id"]:
        raise ValueError("graph snapshot mismatch")
    case = next(c for c in manifest["cases"] if c["case_id"] == args.case_id)
    report = run_case(graph, release, plan, case, raw_dir=args.raw_dir, raw_manifest=raw_manifest)
    report["pins"] = {
        "revision": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        "python": sys.version,
        "platform": platform.platform(),
        "graph_digest": digest(graph),
        "raw_manifest_digest": digest(raw_manifest),
        **acceptance_pins,
        "manifest_file_sha256": acceptance_pins["acceptance_manifest"]["file_sha256"],
        "graph_metadata": graph["metadata"],
        "requirements_file_sha256": hashlib.sha256(
            (ROOT / "requirements.txt").read_bytes()
        ).hexdigest(),
        "dev_requirements_file_sha256": hashlib.sha256(
            (ROOT / "requirements-dev.txt").read_bytes()
        ).hexdigest(),
        "plan_digest": digest(plan),
        "release_digest": plan["release_digest"],
        "catalog_file_sha256": hashlib.sha256(
            (ROOT / "configs/attack_semantics.yml").read_bytes()
        ).hexdigest(),
    }
    report["report_digest"] = digest(report)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "case_id": args.case_id,
                "programs": len(report["programs"]),
                "eligible": list(report["ranking"]["eligible_candidates"]),
                "report_digest": report["report_digest"],
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
