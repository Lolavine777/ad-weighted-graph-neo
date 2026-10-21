"""Generate and check independent #256 demos without writing candidate/oracle packets.

Full output is private and belongs in a local file. Numeric what-if C is synthetic
and test-only. Historical risk uses the unchanged accepted #181 bridge; expanded
contextual bindings remain pending and nonnumeric. This is not #250 integration.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from dataclasses import replace
from pathlib import Path

from scripts.research.asrep_inputs import seamless_inputs
from scripts.research.likelihood_catalog import (
    PACKAGE,
    ROOT,
    _read,
    _require,
    proposed_provider_records,
    verify_package,
)
from scripts.research.reviewed_parameter_release import verify_release
from scripts.research.week3_semantic_bridge_probe import load_acceptance_inputs, overlay
from src.engine import AttackQuery, SearchBudget, generate_attack_paths, run_attack_query
from src.engine.ranking import PathRankingEngine
from src.engine.ranking.effort_registry import (
    ReviewedWorkUnitClassEffortProvider,
    WorkUnitClassRegistry,
    get_default_work_unit_registry,
)
from src.engine.ranking.likelihood import ReviewedScenarioLikelihoodProvider
from src.engine.ranking.orchestration import coverage_from_search_result, evaluate_search_candidates
from src.engine.ranking.resolver import RatingResolver, ReviewedEquivalenceImpactProvider
from src.engine.semantics import load_catalog
from src.engine.semantics.credentials import replay_path
from src.engine.semantics.evidence_view import digest
from src.engine.semantics.week3 import runtime_for_projection


def _pending_c_provider():
    return ReviewedWorkUnitClassEffortProvider(get_default_work_unit_registry())


def _test_only_c_provider(class_ids):
    """In-memory what-if for selected scoped classes; no artifact gains acceptance."""
    classes = [
        replace(
            cls,
            review_status="accepted",
            basis_category="synthetic_test_only",
            review_reference="scripts/research/likelihood_demo_probe.py#isolated-what-if",
        )
        for cls in get_default_work_unit_registry().list_classes()
        if cls.class_id in class_ids
    ]
    _require({cls.class_id for cls in classes} == set(class_ids), "unknown what-if class")
    return ReviewedWorkUnitClassEffortProvider(WorkUnitClassRegistry(classes))


def probe_min_effort():
    verify_package()
    oracle = _read(ROOT, PACKAGE / "oracles.json")["min_effort"]
    query = _read(ROOT, PACKAGE / "min-effort-input.json")
    graph = _read(ROOT, "tests/fixtures/attack_scenarios/graphs/two-routes.json")
    graph_before = digest(graph)
    result = run_attack_query(AttackQuery(**query), graph)
    paths = result.search_result.paths
    _require(len(paths) == oracle["candidate_count"], "Min-Effort candidate count mismatch")
    _require(result.search_result.complete == oracle["complete"], "Min-Effort completeness")
    _require(digest(graph) == graph_before, "query mutated graph")
    # Frozen predicate declarations describe supported operations, not candidate programs.
    actor = query["aliases"]["Alice"]
    group = query["aliases"]["Admins"]
    host = query["aliases"]["Host"]
    bindings = {
        ("propagate_group_entitlement", actor, actor, group): {
            "requires": [
                "actor_controlled_alice",
                "security_group_admins",
                "membership_usable_alice_admins",
            ],
            "adds": ["effective_member_alice_admins"],
        },
    }
    for source in (actor, group):
        bindings[("obtain_admin_execution_on_host", actor, source, host)] = {
            "requires": [
                "actor_controlled_alice",
                "admin_channel_alice_host",
                "authentication_accepted_alice_host",
            ]
            + (["effective_member_alice_admins"] if source == group else []),
            "adds": ["admin_control_host"],
            "shared_prep_key": "auth-preparation",
        }
    prep = {
        "auth-preparation": {
            "work_unit_id": "auth_context:" + actor + ":" + host + ":default:intra_forest:1.0.0",
            "technique": "auth_context",
            "actor_id": actor,
            "target_id": host,
            "classification": "shared_preparation",
            "overlap_state": "independent",
        }
    }
    seed = _read(ROOT, "docs/research/ratings/week4/synthetic-a2-e.json")["query"]
    scope = {
        **seed["query_metadata"],
        "scenario_id": "synthetic-a2",
        "work_boundary": "intra_forest",
        "facts_ledger": seed["facts_ledger"],
    }
    pending = RatingResolver(effort_providers=[_pending_c_provider()]).resolve(
        paths,
        scope,
        transition_bindings=bindings,
        shared_preparation_units=prep,
    )
    pending_result = PathRankingEngine().evaluate(
        pending.ranking_query,
        pending.candidate_envelopes,
    )["result_payload"]
    _require(
        pending_result["min_effort_to_da_baseline"]["minimum_effort_value"] is None,
        "pending C produced numeric Min-Effort",
    )
    provider = _test_only_c_provider(
        {
            "class_shared_auth_preparation",
            "class_direct_host_admin_execution",
            "class_inherited_host_admin_execution",
        }
    )
    simulation = RatingResolver(effort_providers=[provider]).resolve(
        paths,
        scope,
        transition_bindings=bindings,
        shared_preparation_units=prep,
    )
    ranked = PathRankingEngine().evaluate(
        simulation.ranking_query,
        simulation.candidate_envelopes,
    )["result_payload"]
    ledger = simulation.ranking_query["work_units_ledger"]
    costs = []
    for envelope in simulation.candidate_envelopes:
        units = {u for packet in envelope["work_packets"] for u in packet}
        costs.append(sum(ledger[u]["computed_cost"] for u in units))
    _require(sorted(costs) == oracle["expected_cost_multiset"], "frozen C oracle mismatch")
    minimum = ranked["min_effort_to_da_baseline"]
    _require(minimum["minimum_effort_value"] == oracle["minimum_effort"], "winner C mismatch")
    winner_idx = next(
        i
        for i, e in enumerate(simulation.candidate_envelopes)
        if e["candidate_id"] == minimum["best_candidate_id"]
    )
    winner = paths[winner_idx]
    _require(len(winner.transition_history) == oracle["winner_step_count"], "winner step mismatch")
    _require(winner.transition_history[-1].result.request.source == group, "winner source mismatch")
    _require(
        all(u["technique"] != "propagate_group_entitlement" for u in ledger.values()),
        "passive closure created active work",
    )
    shared = [u for u in ledger.values() if u["classification"] == "shared_preparation"]
    _require(
        len(shared) == 1 and shared[0]["computed_cost"] == oracle["shared_preparation_C"],
        "shared work double counted",
    )
    # The fixed oracle must also survive generated-candidate enumeration reversal.
    reverse = RatingResolver(effort_providers=[provider]).resolve(
        tuple(reversed(paths)),
        scope,
        transition_bindings=bindings,
        shared_preparation_units=prep,
    )
    reverse_rank = PathRankingEngine().evaluate(
        reverse.ranking_query,
        reverse.candidate_envelopes,
    )["result_payload"]
    _require(
        reverse_rank["min_effort_to_da_baseline"]["minimum_effort_value"] == 2,
        "enumeration changed minimum",
    )
    return {
        "candidate_source": "run_attack_query",
        "candidate_count": len(paths),
        "complete": result.search_result.complete,
        "current_min_effort": None,
        "test_only_cost_multiset": sorted(costs),
        "test_only_min_effort": 2,
        "shared_work_units": len(shared),
        "passive_q_events": 0,
        "production_numeric_acceptance": False,
        "pending_coverage": pending.coverage_report,
        "test_only_coverage": simulation.coverage_report,
    }


def probe_source_a(raw_dir):
    verify_package()
    oracle = _read(ROOT, PACKAGE / "oracles.json")["risk_comparison"]
    plan = _read(ROOT, "docs/research/ratings/week3-closeout/semantic-bridge-plan.json")
    manifest, pins = load_acceptance_inputs(ROOT, plan)
    release = verify_release(_read(ROOT, manifest["release"]["path"]))
    _require(
        release["bundle_metadata"]["bundle_digest"] == plan["release_digest"],
        "accepted release pin mismatch",
    )
    graph, _, _, _ = seamless_inputs(raw_dir, plan["release_digest"])
    before = digest(graph.to_canonical())
    case = next(c for c in manifest["cases"] if c["case_id"] == "w3-source-a-positive")
    payload = overlay(release["query_projections"]["source_a"], case["overlay"])
    _require(digest(payload) == case["input"]["overlaid_digest"], "accepted overlay mismatch")
    source = plan["sources"]["source_a"]
    query = payload["query"]
    _require(
        graph.metadata["snapshot_id"] == query["query_metadata"]["snapshot_id"], "snapshot mismatch"
    )
    state, context = runtime_for_projection(query, source, plan["cases"][case["case_id"]])
    budget = SearchBudget(**source["budget"])
    search = generate_attack_paths(
        graph,
        source["actor"],
        initial_state=state,
        runtime_context=context,
        target_predicate=lambda n: n["id"] == source["target"],
        success_state_predicate=lambda s: source["target"] in s.admin_control,
        budget=budget,
        catalog=tuple(t for t in load_catalog() if t.id in source["semantic_catalog"]),
        scenario_reference=query["query_metadata"]["scenario_id"],
    )
    bridge = {
        (b["technique_id"], b["actor"], b["source"], b["target"]): b["action_id"]
        for b in source["transition_action_bindings"]
    }
    expected = {tuple(c["bound_action_ids"]): c["candidate_id"] for c in payload["candidates"]}
    selected, labels, candidates = [], [], []
    actions = {a["action_id"]: a for a in query["bound_actions"]}
    bindings = {}
    for path in search.paths:
        keys = [
            (r.technique_id, r.actor, r.source, r.target)
            for step in path.transition_history
            for r in [step.result.request]
        ]
        sequence = tuple(bridge.get(key) for key in keys)
        label = expected.get(sequence)
        if label is None or label in labels:
            continue
        # No oracle PathResult is ever supplied to generation or evaluation.
        replay_path(path, graph)
        selected.append(path)
        labels.append(label)
        candidates.append(
            {
                "candidate_id": label,
                "path_result": path,
                "target_asset_id": source["target"],
                "action_mapping": list(sequence),
            }
        )
        for key, aid in zip(keys, sequence, strict=True):
            action = actions[aid]
            bindings[key] = {
                "requires": action["requires"],
                "adds": action["adds"],
                "is_passive_closure": action["is_passive_closure"],
                "method": "default",
                "auth_context": context.authentication_context,
                "policy_id": query["query_metadata"]["governance"]["rating_context"][
                    "execution_policy"
                ]["policy_id"],
            }
    _require(set(labels) == set(oracle["expected_nondominated"]), "Source-A programs not generated")
    _require(digest(graph.to_canonical()) == before, "Source-A mutated snapshot")
    rated = evaluate_search_candidates(
        query,
        candidates,
        canonical_graph=graph.to_canonical(),
        coverage=coverage_from_search_result(search, budget),
    )["roundtrip_result"]
    _require(
        set(rated["pareto_frontier"]) == set(oracle["expected_nondominated"]),
        "historical generated Pareto oracle mismatch",
    )
    for expectation in oracle["expected_programs"]:
        result = rated["eligible_candidates"][expectation["historical_candidate_id"]]
        # Use serialized exact Fraction bounds, not floats or a product fitted to output.
        _require(
            result["likelihood_interval"] == expectation["exact_path_interval"], "exact P mismatch"
        )
        _require(result["effort"] == expectation["C"], "historical C mismatch")
        _require(result["consequence_rating"] == expectation["I"], "historical I mismatch")
    scope = {
        **query["query_metadata"],
        "facts_ledger": query["facts_ledger"],
        "policy_id": query["query_metadata"]["governance"]["rating_context"]["execution_policy"][
            "policy_id"
        ],
    }
    unresolved = RatingResolver(
        likelihood_providers=[ReviewedScenarioLikelihoodProvider(proposed_provider_records())]
    ).resolve(selected, scope, transition_bindings=bindings)
    pending = _read(ROOT, PACKAGE / "bindings.json")["records"]
    expected_digests = {r["generated_lookup_key_digest"] for r in pending}
    prefix_records = [
        p
        for c in unresolved.coverage_report["candidates"].values()
        for p in c["likelihood"]["prefixes"]
    ]
    _require(len(prefix_records) == 8, "generated prefix count")
    _require(
        {digest(p["rating_audit"]["lookup_key"]) for p in prefix_records} == expected_digests,
        "generated key differs from frozen binding proposal",
    )
    _require(all(p["interval"] is None for p in prefix_records), "pending numeric P activation")
    _require(
        all(
            p["disposition"] == "refused"
            and p["selected_provider"] == "reviewed_scenario_likelihood_provider"
            and any(
                attempt["provider"] == "reviewed_scenario_likelihood_provider"
                and attempt["disposition"] == "refused"
                and attempt["reason_code"] == "prerequisite_gate_refusal"
                and attempt["reason_detail"]
                == "Scenario record requires explicit accepted review_status and rated disposition"
                for attempt in p["provider_trace"]
            )
            for p in prefix_records
        ),
        "pending P refused for an unrelated reason",
    )
    return {
        "candidate_source": "generate_attack_paths",
        "reviewed_subset_count": len(selected),
        "generated_candidate_count": len(search.paths),
        "historical_labels": labels,
        "unreviewed_generated_count": len(search.paths) - len(selected),
        "expansions": search.expansions,
        "truncated": search.truncated,
        "truncation_reason": search.truncation_reason,
        "accepted_input_pins": pins,
        "historical_bridge_ranking": rated,
        "pending_context_coverage": unresolved.coverage_report,
        "current_context_P": None,
        "numeric_activation_permitted": False,
        "comparison_scope": "bounded reviewed subset only",
    }


def probe_frozen_243(raw_dir):
    from tests.frozen_rating_inputs import frozen_program

    verify_package()
    oracle = _read(ROOT, PACKAGE / "oracles.json")["frozen_243"]
    paths, scope, bindings = frozen_program(raw_dir)
    owners = [s.result.request.technique_id for s in paths[0].transition_history]
    _require(owners == oracle["program"], "frozen program changed")
    _require(scope["horizon"] == oracle["horizon"], "frozen horizon changed")
    _require(scope["recovery_metadata"]["budget"] == oracle["recovery_budget"], "budget changed")
    release = _read(ROOT, "docs/research/ratings/week3-closeout/reviewed-release.json")
    impact = ReviewedEquivalenceImpactProvider(
        _read(ROOT, "docs/research/ratings/week4/impact-equivalence-registry.json"),
        source_packet=release,
    )
    output = RatingResolver(
        effort_providers=[_pending_c_provider()], impact_providers=[impact]
    ).resolve(
        paths,
        scope,
        transition_bindings=bindings,
    )
    prefixes = next(iter(output.coverage_report["candidates"].values()))["likelihood"]["prefixes"]
    _require(len(prefixes) == oracle["q_event_count"], "frozen prefix count changed")
    _require(all(p["interval"] is None for p in prefixes), "frozen P gap concealed")
    classes = {
        "class_asrep_request",
        "class_asrep_offline_crack",
        "class_kerberos_identity_activation",
        "class_host_admin_channel",
    }
    what_if = RatingResolver(effort_providers=[_test_only_c_provider(classes)]).resolve(
        paths,
        scope,
        transition_bindings=bindings,
    )
    costs = [u["computed_cost"] for u in what_if.ranking_query["work_units_ledger"].values()]
    _require(costs == oracle["proposed_C_by_event"], "frozen C oracle mismatch")
    catalog = _read(ROOT, PACKAGE / "catalog.json")
    by_owner = {a["technique_id"]: a for a in catalog["actions"]}
    dispositions = [by_owner[owner]["disposition"] for owner in owners]
    _require(dispositions == oracle["event_dispositions"], "frozen dispositions changed")
    return {
        "candidate_source": "run_attack_query via frozen_program",
        "candidate_count": len(paths),
        "program": owners,
        "catalog_dispositions": dispositions,
        "current_P": None,
        "horizon": scope["horizon"],
        "recovery_budget": scope["recovery_metadata"]["budget"],
        "test_only_C_by_event": costs,
        "pending_coverage": output.coverage_report,
        "production_numeric_acceptance": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-dir", type=Path, required=True)
    parser.add_argument(
        "--output", type=Path, required=True, help="Local private result; not an oracle"
    )
    args = parser.parse_args()
    report = {
        "revision": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        "package": verify_package(),
        "min_effort": probe_min_effort(),
        "source_a": probe_source_a(args.raw_dir),
        "frozen_243": probe_frozen_243(args.raw_dir),
    }
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "min_effort_candidates": report["min_effort"]["candidate_count"],
                "source_a_candidates": report["source_a"]["reviewed_subset_count"],
                "source_a_truncated": report["source_a"]["truncated"],
                "frozen_243_P": report["frozen_243"]["current_P"],
                "numeric_activation_permitted": False,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
