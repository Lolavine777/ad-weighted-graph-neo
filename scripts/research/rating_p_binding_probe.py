"""Local Source-A generated contextual-binding inventory, pending B review.

Consumes the accepted #181 bridge and Week 3 release without changing either.
Never exports numeric ratings or treats generated aliases as accepted equivalences.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

from scripts.research.asrep_inputs import seamless_inputs
from scripts.research.reviewed_parameter_release import verify_release
from scripts.research.week3_semantic_bridge_probe import (
    PLAN,
    ROOT,
    load_acceptance_inputs,
    overlay,
)
from src.engine import SearchBudget, generate_attack_paths
from src.engine.ranking.resolver import ExplicitPacketRatingProvider, RatingResolver
from src.engine.semantics import load_catalog
from src.engine.semantics.evidence_view import digest
from src.engine.semantics.week3 import runtime_for_projection


def probe_generated_source_a(raw_dir: Path) -> dict:
    plan = json.loads(PLAN.read_text())
    manifest, pins = load_acceptance_inputs(ROOT, plan)
    release_path = ROOT / manifest["release"]["path"]
    if hashlib.sha256(release_path.read_bytes()).hexdigest() != manifest["release"]["file_sha256"]:
        raise ValueError("accepted release file pin mismatch")
    release = verify_release(json.loads(release_path.read_text()))
    if release["bundle_metadata"]["bundle_digest"] != plan["release_digest"]:
        raise ValueError("accepted release digest mismatch")
    raw_manifest = json.loads((ROOT / manifest["release"]["raw_manifest"]["path"]).read_text())
    if digest(raw_manifest) != manifest["release"]["raw_manifest"]["canonical_digest"]:
        raise ValueError("accepted raw manifest pin mismatch")
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    graph, _, _, _ = seamless_inputs(raw_dir, revision)  # Verifies raw file bytes first.
    if graph.metadata["snapshot_id"] != raw_manifest["snapshot_id"]:
        raise ValueError("generated graph snapshot mismatch")
    case = next(c for c in manifest["cases"] if c["case_id"] == "w3-source-a-positive")
    payload = overlay(release["query_projections"]["source_a"], case["overlay"])
    if digest(payload) != case["input"]["overlaid_digest"]:
        raise ValueError("accepted case input mismatch")
    source = plan["sources"]["source_a"]
    state, context = runtime_for_projection(
        payload["query"], source, plan["cases"][case["case_id"]]
    )
    generated = generate_attack_paths(
        graph,
        source["actor"],
        initial_state=state,
        runtime_context=context,
        target_predicate=lambda n: n["id"] == source["target"],
        success_state_predicate=lambda s: source["target"] in s.admin_control,
        budget=SearchBudget(**source["budget"]),
        catalog=tuple(t for t in load_catalog() if t.id in source["semantic_catalog"]),
        scenario_reference=payload["query"]["query_metadata"]["scenario_id"],
    )
    bridge = {
        (b["technique_id"], b["actor"], b["source"], b["target"]): b["action_id"]
        for b in source["transition_action_bindings"]
    }
    actions = {a["action_id"]: a for a in payload["query"]["bound_actions"]}
    expected = {tuple(c["bound_action_ids"]): c["candidate_id"] for c in payload["candidates"]}
    selected, labels, bindings = [], [], {}
    # Match historical identities only after actual search; never inject candidates.
    for path in generated.paths:
        keys = [
            (r.technique_id, r.actor, r.source, r.target)
            for step in path.transition_history
            for r in [step.result.request]
        ]
        sequence = tuple(bridge.get(k) for k in keys)
        cid = expected.get(sequence)
        if cid is None or cid in labels:
            continue
        selected.append(path)
        labels.append(cid)
        for key, aid in zip(keys, sequence, strict=True):
            bindings[key] = actions[aid]
    if len(selected) != 2:
        raise ValueError("supported Source-A search did not generate both historical programs")
    query = payload["query"]
    scope = {**query["query_metadata"], "facts_ledger": query["facts_ledger"]}
    packet = ExplicitPacketRatingProvider(query)
    output = RatingResolver(likelihood_providers=[packet]).resolve(
        selected,
        scope,
        transition_bindings=bindings,
    )
    policy = query["query_metadata"]["governance"]["rating_context"]["execution_policy"]
    canonical_scope = {
        **scope,
        "policy_id": policy["policy_id"],
        "retry_policy": policy,
        "target_population": "SEAMLESS v1 declared scenario only",
    }
    canonical_bindings = {
        key: {
            "requires": action["requires"],
            "adds": action["adds"],
            "is_passive_closure": action["is_passive_closure"],
            "method": "default",
            "auth_context": context.authentication_context,
            "policy_id": policy["policy_id"],
        }
        for key, action in bindings.items()
    }
    canonical = RatingResolver(likelihood_providers=[packet]).resolve(
        selected,
        canonical_scope,
        transition_bindings=canonical_bindings,
    )
    proposals = []
    for envelope, historical_id in zip(output.candidate_envelopes, labels, strict=True):
        prefixes = output.coverage_report["candidates"][envelope["candidate_id"]]["likelihood"][
            "prefixes"
        ]
        generated_prefixes = canonical.coverage_report["candidates"][envelope["candidate_id"]][
            "likelihood"
        ]["prefixes"]
        for item, canonical_item in zip(prefixes, generated_prefixes, strict=True):
            if item["interval"] is not None or canonical_item["interval"] is not None:
                raise ValueError("Unaccepted contextual bridge must remain nonnumeric")
            record = next(
                r for r in query["conditional_bounds_table"] if r["prefix"] == item["prefix"]
            )
            proposals.append(
                {
                    "status": "proposed_pending_b_review",
                    "historical_candidate_id": historical_id,
                    "source_question_id": record["question_id"],
                    "source_record_digest": digest(record),
                    "generated_lookup_key": canonical_item["rating_audit"]["lookup_key"],
                    "legacy_lookup_key": item["rating_audit"]["lookup_key"],
                    "proposed_retry_policy": policy,
                    "proposed_target_population": canonical_scope["target_population"],
                    "legacy_ordered_prefix": item["prefix"],
                    "legacy_outcome_action_id": record["outcome_action_id"],
                    "disposition": item["disposition"],
                    "reason_detail": item["reason_detail"],
                    "provider_trace": item["provider_trace"],
                }
            )
    return {
        "status": "proposed_pending_b_review",
        "revision": revision,
        "candidate_source": "generate_attack_paths",
        "historical_candidates": labels,
        "release_digest": plan["release_digest"],
        "accepted_input_pins": pins,
        "search_budget": source["budget"],
        "expansions": generated.expansions,
        "truncated": generated.truncated,
        "truncation_reason": generated.truncation_reason,
        "binding_inventory": proposals,
        "numeric_reuse_permitted": False,
        "required_b_decision": (
            "Review each exact generated contextual key against its pinned historical q record, "
            "including aliases, structural source, auth/resource context and retry policy; "
            "approve or reject each binding without changing Week 3 ratings."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True, help="Local private inventory path")
    args = parser.parse_args()
    report = probe_generated_source_a(args.raw_dir)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(
        json.dumps(
            {
                "historical_candidates": len(report["historical_candidates"]),
                "prefixes": len(report["binding_inventory"]),
                "status": report["status"],
                "truncated": report["truncated"],
            }
        )
    )


if __name__ == "__main__":
    main()
