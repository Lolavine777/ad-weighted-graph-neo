"""Issue #250 public generated flow; numeric fixtures are never production evidence."""

import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from referencing import Registry, Resource

from scripts.check_contract import canonical_edge_id
from src.engine import materialize_query, run_attack_query
from src.engine.graph import EngineGraph
from src.engine.query_cli import wire
from src.engine.ranking.orchestration import generate_and_evaluate_attack_paths
from src.engine.ranking.resolution_service import canonical_digest
from src.engine.ranking.resolver import generate_rating_lookup_key_p, generate_work_unit_id

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests/fixtures"
GRAPH = FIXTURES / "attack_scenarios/graphs/two-routes.json"


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def validate_public_coverage(coverage):
    schema = read(ROOT / "docs/research/public-rating-coverage.schema.json")
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(coverage)


def validate_public_transport(package):
    coverage = read(ROOT / "docs/research/public-rating-coverage.schema.json")
    schema = read(ROOT / "docs/research/week4-query-result-0.3.schema.json")
    Draft202012Validator.check_schema(schema)
    registry = Registry().with_resource(
        "public-rating-coverage.schema.json", Resource.from_contents(coverage)
    )
    Draft202012Validator(schema, registry=registry).validate(package)


def registry(data):
    return {"version": "1.0.0", "sha256": canonical_digest(data), "data": data}


@pytest.mark.parametrize("selector", ["snapshot_ids", "work_unit_digests"])
def test_exact_effort_disposition_refuses_other_snapshot_or_work_identity(selector):
    query, graph = rated_case()
    original = run_attack_query(query, graph)
    units = {
        uid
        for candidate in original.rating_coverage["candidates"].values()
        for uid in candidate["effort"]["units"]
    }
    records = query["rating_resolution"]["registries"]["effort"]["data"]
    for record in records:
        record["applicability"].update(
            snapshot_ids=[graph.metadata["snapshot_id"]],
            work_unit_digests=sorted(canonical_digest(uid) for uid in units),
        )
    query["rating_resolution"]["registries"]["effort"] = registry(records)
    assert run_attack_query(query, graph).rating_coverage["numeric_requests"]["C"] == {
        "required": 2,
        "rated": 2,
    }
    for record in records:
        record["applicability"][selector] = ["sha256:" + "0" * 64]
    query["rating_resolution"]["registries"]["effort"] = registry(records)
    refused = run_attack_query(query, graph)
    assert len(refused.search_result.paths) == len(original.search_result.paths)
    assert refused.rating_coverage["numeric_requests"]["C"] == {"required": 2, "rated": 0}
    assert refused.ranking_result["min_effort_to_da_baseline"]["minimum_effort_value"] is None


def base_case():
    query = read(FIXTURES / "query_cli/two-routes-query.json")
    query.pop("action_bindings")
    graph = EngineGraph.from_canonical(read(GRAPH))
    actor, target = query["aliases"]["Alice"], query["aliases"]["Host"]
    query["rating_resolution"] = {
        "version": "public-rating-resolution/1.1.0",
        "mode": "automatic",
        "policy": "synthetic_test_only",
        "scope": {
            "query_id": "synthetic-issue250",
            "scenario_id": query["scenario_reference"],
            "scenario_version": "1.0.0",
            "snapshot_id": graph.metadata["snapshot_id"],
            "foothold_node_id": actor,
            "work_boundary": "intra_forest",
            "horizon": "24h",
            "active_work_budget": 12,
            "evaluation_mode": "scenario",
            "target_goal": {
                "goal_id": "admin",
                "target_asset_id": target,
                "success_event": "admin_control_host",
            },
        },
        "registries": {},
    }
    return query, graph


def test_ordinary_state_goal_gets_native_replay_in_public_automatic_resolution(tmp_path):
    query, graph = base_case()
    alice, admins = query["aliases"]["Alice"], query["aliases"]["Admins"]
    query.update(
        target="Alice",
        target_goal={
            "target": "Alice",
            "required_state": {"effective_member": [["Alice", "Admins"]]},
        },
        allowed_techniques=["propagate_group_entitlement"],
    )
    query["rating_resolution"]["scope"]["target_goal"]["target_asset_id"] = alice
    result = run_attack_query(query, graph)
    assert len(result.paths) == 1
    assert result.paths[0].goal_target == alice and result.paths[0].nodes[-1] == admins
    assessment = result.ranking_result["diagnostics"]["generated_0001"]["assessment"]
    assert assessment["status"] == "feasible"
    assert len(assessment["bound_action_ids"]) == 1
    assert result.ranking_result["search_audit"]["candidates_adapted"] == 1
    # Missing numeric basis remains visible after successful semantic replay.
    assert result.rating_coverage["aggregate_summary"]["fully_rated_candidates"] == 0
    query_file = tmp_path / "ordinary-state-goal.json"
    query_file.write_text(json.dumps(query), encoding="utf-8")
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "src.engine.query_cli",
            "--query",
            str(query_file),
            "--graph",
            str(GRAPH),
            "--label",
            "synthetic",
        ],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        capture_output=True,
        check=True,
    )
    assert json.loads(proc.stdout)["semantic"]["ranking_result"] == wire(result.ranking_result)


@pytest.mark.parametrize("wire_relation", [False, True])
def test_same_endpoint_goal_proof_preserves_declared_relationship_state(wire_relation):
    query, graph = base_case()
    relation = {"source": "Alice", "kind": "MemberOf", "target": "Admins"}
    query["initial_state"]["relationship_added"] = [
        relation if wire_relation else ["Alice", "MemberOf", "Admins"]
    ]
    result = run_attack_query(query, graph)
    assert result.paths and result.final_goal_reached
    assert not result.rating_coverage["binding"]["canonical_rejections"]
    assert all(
        s["semantic_status"] == "feasible"
        for s in result.rating_coverage["candidate_summaries"].values()
    )


def test_relationship_wire_state_rejects_undeclared_fields():
    query, graph = base_case()
    query["initial_state"]["relationship_added"] = [
        {
            "source": "Alice",
            "kind": "MemberOf",
            "target": "Admins",
            "approved": True,
        }
    ]
    with pytest.raises(ValueError, match="requires source/kind/target triples"):
        run_attack_query(query, graph)


@pytest.mark.parametrize("prefix,typed_membership", [(0, True), (1, True), (2, True), (1, False)])
def test_manual_state_goal_ranking_checks_the_first_hit_prefix(prefix, typed_membership):
    from src.engine.ranking import RankingValidationError
    from src.engine.ranking.orchestration import evaluate_search_candidates
    from src.engine.ranking.resolution_service import resolve_generated_rating_inputs

    query, graph = base_case()
    alice, host = query["aliases"]["Alice"], query["aliases"]["Host"]
    query.update(
        target="Alice",
        authentication_context=host,
        initial_state={
            "recovered_secret": [
                {
                    "owner": alice,
                    "context": host,
                    "form": "password",
                    "provenance": ["synthetic://state-goal/password"],
                }
            ],
        },
        target_goal={
            "target": "Alice",
            "required_state": {
                "usable_identity": [["Alice", "Host"]],
                "effective_member": [["Alice", "Admins"]],
            },
        },
        allowed_techniques=["activate_recovered_identity", "propagate_group_entitlement"],
    )
    query["runtime_facts"] += [
        {
            "predicate": predicate,
            "subject": alice,
            "target": host,
            "value": True,
            "origin": "declared_assumption",
            "scope": host,
            "rationale": "Synthetic activation precondition",
            "provenance_reference": "synthetic://state-goal/activation",
        }
        for predicate in ("secret_valid", "network_kdc_reachable")
    ]
    query["rating_resolution"]["scope"]["target_goal"]["target_asset_id"] = alice
    generated = run_attack_query(query, graph)
    assert len(generated.paths) == 1
    path = generated.paths[0]
    assert [s.result.request.technique_id for s in path.transition_history] == [
        "activate_recovered_identity",
        "propagate_group_entitlement",
    ]
    assert generated.materialized_query.semantic_goal.matches(path.final_state)
    packet, candidates, _ = resolve_generated_rating_inputs(
        query["rating_resolution"], graph, generated.materialized_query, generated.search_result
    )
    if prefix == 0:
        predicate = next(f["predicate"] for f in packet["facts_ledger"]["observed_facts"])
    elif prefix == 1:
        predicate = packet["bound_actions"][0]["adds"][0]
    else:
        predicate = packet["query_metadata"]["target_goal"]["required_predicates"][0]
    packet["query_metadata"]["target_goal"]["required_predicates"] = [predicate]
    if not typed_membership:
        packet["query_metadata"]["semantic_goal"]["required_state"].pop("effective_member")
    if typed_membership and prefix < 2:
        with pytest.raises(
            RankingValidationError, match="executed prefix does not satisfy the typed semantic goal"
        ):
            evaluate_search_candidates(packet, candidates, canonical_graph=graph.to_canonical())
    else:
        ranked = evaluate_search_candidates(
            packet, candidates, canonical_graph=graph.to_canonical()
        )["roundtrip_result"]
        assessment = ranked["diagnostics"]["generated_0001"]["assessment"]
        assert assessment["status"] == "feasible"
        assert len(assessment["bound_action_ids"]) == prefix
        assert len(assessment["program"]) == 1  # Group propagation is passive closure.


def rated_case(*, shared=False):
    """Freeze C=4 direct, C=1 inherited and P=1/4 vs 3/4 before engine execution.

    Prefix IDs use the published deterministic identity formula, never actual engine output.
    With shared preparation C adds 1 and P multiplies by 1/2 exactly once.
    """
    query, graph = base_case()
    config = query["rating_resolution"]
    scope = config["scope"]
    actor, target = scope["foothold_node_id"], scope["target_goal"]["target_asset_id"]
    sources = [actor, query["aliases"]["Admins"]]
    classes, likelihood = [], []
    prep_id = None
    if shared:
        rule = {
            "techniques": ["obtain_admin_execution_on_host"],
            "method": "AdminTo",
            "preparation_technique": "auth_context",
            "review_status": "accepted",
            "review_reference": "synthetic://issue250/work-rule",
            "basis_category": "synthetic_test_only",
            "scenario_id": scope["scenario_id"],
            "boundary": scope["work_boundary"],
        }
        config["registries"]["work"] = registry([rule])
        context = {
            "actor": actor,
            "target": target,
            "auth_context": None,
            "resource_context": None,
            "policy_id": None,
            "scenario_id": scope["scenario_id"],
            "method": "AdminTo",
        }
        prep_id = generate_work_unit_id(
            "auth_context",
            actor,
            target,
            "ctx-" + canonical_digest(context).removeprefix("sha256:"),
            "intra_forest",
        )
    for source_index, source in enumerate(sources + ([actor] if shared else [])):
        is_prep = source_index == 2
        technique = "auth_context" if is_prep else "obtain_admin_execution_on_host"
        cost = 1 if is_prep or source != actor else 4
        t1, t2 = (3, 3) if cost == 4 else (1, 2)
        classes.append(
            {
                "class_id": f"synthetic-{source_index}",
                "name": "Synthetic effort",
                "description": "Algorithm test; no production numeric acceptance",
                "t1": t1,
                "t2": t2,
                "review_status": "accepted",
                "basis_category": "synthetic_test_only",
                "review_reference": "synthetic://issue250/C",
                "applicability": {
                    "techniques": [technique],
                    "source_ids": [source],
                    "boundaries": ["intra_forest"],
                    "scopes": [scope["scenario_id"]],
                },
            }
        )
        context = {
            "source_id": source,
            "method": "AdminTo",
            "auth_context": None,
            "resource_context": None,
            "policy_id": None,
            "scope": scope["scenario_id"],
        }
        unit = (
            prep_id
            if is_prep
            else generate_work_unit_id(
                technique,
                actor,
                target,
                "ctx-" + canonical_digest(context).removeprefix("sha256:"),
                "intra_forest",
            )
        )
        prefix = [unit] if not shared or is_prep else [prep_id, unit]
        key = generate_rating_lookup_key_p(
            scenario_id=scope["scenario_id"],
            scenario_version=scope["scenario_version"],
            snapshot_id=scope["snapshot_id"],
            foothold_node_id=actor,
            ordered_work_prefix=tuple(prefix),
            outcome_work_unit_id=unit,
            outcome_technique=technique,
            actor_id=actor,
            source_id=source,
            target_id=target,
            method="AdminTo",
            budget=12,
            horizon="24h",
            boundary="intra_forest",
            scope=scope["scenario_id"],
        ).to_dict()
        key.pop("dimension")
        likelihood.append(
            {
                **key,
                "disposition": "rated",
                "review_status": "accepted",
                "lower": "1/2" if is_prep else "1/4" if source == actor else "3/4",
                "upper": "1/2" if is_prep else "1/4" if source == actor else "3/4",
                "basis_category": "synthetic_test_only",
                "rationale": "Synthetic oracle",
                "review_reference": "synthetic://issue250/P",
                "provenance_digest": "sha256:" + "a" * 64,
            }
        )
    source_packet = {
        "target_impact_assessments": {
            target: {
                "target_asset_id": target,
                "success_event": "synthetic_old_admin",
                "rating_status": "rated",
                "consequence_rating": "High",
            }
        }
    }
    impact = {
        "version": "1.0.0",
        "mappings": [
            {
                "mapping_id": "synthetic-equivalence",
                "target_asset_id": target,
                "source_event": "synthetic_old_admin",
                "destination_event": "admin_control_host",
                "directionality": "directional",
                "consequence_rating": "High",
                "status": "reviewed",
                "evidence_class": "synthetic_test_only",
                "review_reference": "synthetic://issue250/I",
                "source_release_canonical_digest": canonical_digest(source_packet),
                "applicability": {
                    "semantic_goal": materialize_query(query, graph).semantic_goal.to_dict(),
                    "goal_id": scope["target_goal"]["goal_id"],
                    "snapshot_id": scope["snapshot_id"],
                    "boundary": "intra_forest",
                    "scenario_id": scope["scenario_id"],
                    "operational_horizon": "24h",
                },
            }
        ],
    }
    config["registries"].update(
        effort=registry(classes),
        likelihood=registry(likelihood),
        impact=registry(impact),
        impact_source=registry(source_packet),
    )
    return query, graph


def assessments(result):
    payload = result.ranking_result
    return {
        **payload["eligible_candidates"],
        **{
            cid: value["assessment"]
            for cid, value in payload["diagnostics"].items()
            if "assessment" in value
        },
    }


@pytest.mark.parametrize("shared", [False, True])
def test_generated_effort_risk_and_passive_work(shared):
    query, graph = rated_case(shared=shared)
    result = run_attack_query(query, graph)
    rated = assessments(result)
    assert len(result.paths) == len(rated) == 3
    assert sorted(c["effort"] for c in rated.values()) == ([2, 5, 5] if shared else [1, 4, 4])
    assert result.min_effort["minimum_effort_value"] == (2 if shared else 1)
    assert result.is_minimum_proven_over_scope
    assert not result.binding_diagnostics
    assert result.rating_coverage["aggregate_summary"]["fully_rated_candidates"] == 3
    assert result.rating_coverage["numeric_requests"] == {
        "C": {"required": 3 if shared else 2, "rated": 3 if shared else 2},
        "P": {"required": 3 if shared else 2, "rated": 3 if shared else 2},
        "I": {"required": 1, "rated": 1},
    }
    assert result.rating_coverage["binding"]["passive_steps"] == 2
    assert result.rating_coverage["binding"]["canonical_rejections"] == {}
    assert result.rating_coverage["binding"]["canonical_admitted_candidates"] == 3
    validate_public_coverage(result.rating_coverage)
    for coverage in result.rating_coverage["candidates"].values():
        assert coverage["effort"]["total_units"] == (2 if shared else 1)
        assert coverage["likelihood"]["total_prefixes"] == (2 if shared else 1)
    for candidate in rated.values():
        from fractions import Fraction

        direct = candidate["effort"] == (5 if shared else 4)
        expected = Fraction(1, 4) if direct else Fraction(3, 4)
        if shared:
            expected *= Fraction(1, 2)
        assert [Fraction(x) for x in candidate["likelihood_interval"]] == [expected, expected]
        assert len(candidate["program"]) == (2 if shared else 1)
    assert result.ranking_result["pareto_frontier"] == ["generated_0003"]


def test_missing_all_and_effort_only_keep_generated_assessments():
    query, graph = rated_case()
    query["rating_resolution"]["registries"] = {}
    result = run_attack_query(query, graph)
    assert len(assessments(result)) == 3
    assert result.rating_coverage["aggregate_summary"]["fully_rated_candidates"] == 0
    assert not result.is_minimum_proven_over_scope
    assert not result.ranking_result["pareto_frontier"]
    query, graph = rated_case()
    regs = query["rating_resolution"]["registries"]
    query["rating_resolution"]["registries"] = {"effort": regs["effort"]}
    result = run_attack_query(query, graph)
    assert result.min_effort["minimum_effort_value"] == 1
    assert result.is_minimum_proven_over_scope
    assert not result.ranking_result["pareto_frontier"]


@pytest.mark.parametrize(
    "mode", ["complete", "missing", "production_refusal", "truncated", "zero_action", "empty"]
)
def test_all_entry_points_and_two_runs(tmp_path, mode):
    query, graph = rated_case(shared=mode != "production_refusal")
    if mode == "missing":
        query["rating_resolution"]["registries"] = {}
    elif mode == "production_refusal":
        query["rating_resolution"]["policy"] = "production"
    elif mode == "truncated":
        query["budget"]["max_paths"] = 1
    elif mode == "zero_action":
        query["initial_state"]["admin_control"] = [query["aliases"]["Host"]]
    elif mode == "empty":
        query["initial_state"] = {"control": []}
    materialized = materialize_query(query, graph)
    api = materialized.run(graph)
    validate_public_coverage(api.rating_coverage)
    other = generate_and_evaluate_attack_paths(
        {},
        graph.to_canonical(),
        actor=materialized.initial_actor,
        initial_state=materialized.initial_attack_state,
        runtime_context=materialized.runtime_context,
        budget=materialized.budget,
        catalog=materialized.catalog,
        scenario_reference=materialized.scenario_reference,
        success_state_predicate=materialized.success_state_predicate,
        semantic_goal=materialized.semantic_goal,
        rating_resolution=query["rating_resolution"],
    )["roundtrip_result"]
    assert wire(api.ranking_result) == other
    for key in ("eligible_candidates", "pareto_frontier", "diagnostics"):
        assert wire(api.ranking_result[key]) == other[key]
    query_file = tmp_path / "query.json"
    query_file.write_text(json.dumps(query), encoding="utf-8")
    outputs = []
    for _ in range(2):
        proc = subprocess.run(
            [
                sys.executable,
                "-m",
                "src.engine.query_cli",
                "--query",
                str(query_file),
                "--graph",
                str(GRAPH),
                "--label",
                "synthetic",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        assert proc.returncode == 0, proc.stderr
        output = json.loads(proc.stdout)
        assert output["schema_version"] == "week4-query-result/0.3.0"
        validate_public_transport(output)
        assert output["semantic"]["rating_coverage"] == api.rating_coverage
        assert output["semantic"]["ranking_result"] == wire(api.ranking_result)
        output.pop("runtime")  # defined volatile transport block only
        outputs.append(output)
    assert outputs[0] == outputs[1]


@pytest.mark.parametrize("boundary", ["adapter", "canonical_validator"])
def test_public_coverage_reports_actual_canonical_rejection(monkeypatch, boundary):
    from src.engine.ranking import orchestration

    query, graph = rated_case()
    if boundary == "adapter":
        from src.engine.ranking import resolution_service

        original = resolution_service.resolve_generated_rating_inputs

        def corrupt_mapping(*args):
            packet, candidates, coverage = original(*args)
            candidates[0]["action_mapping"] = ["unbound-action"]
            return packet, candidates, coverage

        monkeypatch.setattr(resolution_service, "resolve_generated_rating_inputs", corrupt_mapping)
        expected_reason = "adapter_ineligible"
    else:
        original = orchestration.adapt_search_candidate

        def corrupt_required_predicate(**kwargs):
            envelope = original(**kwargs)
            if kwargs["candidate_id"] == "generated_0001":
                envelope["required_predicates"] = ["unclassified_test_predicate"]
            return envelope

        monkeypatch.setattr(orchestration, "adapt_search_candidate", corrupt_required_predicate)
        expected_reason = "canonical_candidate_invalid"
    result = run_attack_query(query, graph)
    validate_public_coverage(result.rating_coverage)
    binding = result.rating_coverage["binding"]
    assert binding["materialized_candidates"] == 3
    assert binding["canonical_admitted_candidates"] == 2
    assert list(binding["canonical_rejections"]) == ["generated_0001"]
    rejection = binding["canonical_rejections"]["generated_0001"]
    diagnostic = result.ranking_result["diagnostics"]["generated_0001"]
    assert rejection["reason"] == expected_reason
    assert rejection["reasons"] == diagnostic["reasons"]
    assert rejection["diagnostic"] == diagnostic["assessment"]["diagnostic"]
    assert not result.is_minimum_proven_over_scope
    assert result.optimization_scope == "best_in_bound_subset"


@pytest.mark.parametrize("role", ["effort", "likelihood", "impact"])
def test_synthetic_numeric_is_refused_by_production_policy(role):
    query, graph = rated_case()
    query["rating_resolution"]["policy"] = "production"
    coverage = run_attack_query(query, graph).rating_coverage
    dimension = {"effort": "C", "likelihood": "P", "impact": "I"}[role]
    gaps = [g for g in coverage["unresolved_gaps"] if g["dimension"] == dimension]
    assert gaps and all(g["disposition"] == "refused" for g in gaps)
    assert all(g["provider_trace"][-1]["disposition"] == "refused" for g in gaps)


def test_context_integrity_conflicts_pending_and_mixed_coverage():
    query, graph = rated_case()
    regs = query["rating_resolution"]["registries"]
    classes = copy.deepcopy(regs["effort"]["data"])
    classes[0]["review_status"] = "pending_b_review"
    regs["effort"] = registry(classes)
    result = run_attack_query(query, graph)
    assert result.min_effort["minimum_effort_value"] == 1
    assert not result.is_minimum_proven_over_scope
    assert result.rating_coverage["aggregate_summary"]["fully_rated_candidates"] == 1
    records = copy.deepcopy(regs["likelihood"]["data"])
    records[0]["horizon"] = "72h"
    regs["likelihood"] = registry(records)
    gaps = run_attack_query(query, graph).rating_coverage["unresolved_gaps"]
    assert any(g["reason_code"] == "out_of_scope" and g["disposition"] == "refused" for g in gaps)
    regs["likelihood"]["sha256"] = "sha256:" + "0" * 64
    with pytest.raises(ValueError, match="integrity digest mismatch"):
        run_attack_query(query, graph)
    query, graph = base_case()
    query["ranking_query"] = read(ROOT / "docs/research/ratings/week4/synthetic-a2-e.json")["query"]
    with pytest.raises(ValueError, match="conflicts with explicit"):
        run_attack_query(query, graph)


@pytest.mark.parametrize("extension", ["asrep", "kerberoasting", "rbcd"])
def test_extensions_all_missing_prefixes_and_semantic_replay(extension):
    query = read(FIXTURES / extension / "query.json")
    query.pop("ranking_query", None)
    query.pop("action_bindings", None)
    graph = EngineGraph.from_snapshot(json.dumps(read(FIXTURES / extension / "snapshot.json")))
    materialized = materialize_query(query, graph)
    config = base_case()[0]["rating_resolution"]
    config["policy"] = "production"
    scope = config["scope"]
    scope.update(
        snapshot_id=graph.metadata["snapshot_id"],
        foothold_node_id=materialized.initial_actor,
        active_work_budget=materialized.budget.max_steps,
        scenario_id=materialized.scenario_reference or "synthetic-extension",
    )
    scope["target_goal"]["target_asset_id"] = materialized.target
    query["rating_resolution"] = config
    result = run_attack_query(query, graph)
    assert result.paths and not result.binding_diagnostics
    assert len(assessments(result)) == len(result.paths)
    for candidate in result.rating_coverage["candidates"].values():
        count = candidate["effort"]["total_units"]
        assert candidate["likelihood"]["total_prefixes"] == count
        assert len(candidate["likelihood"]["gaps"]) == count
    assert all(c["status"] == "feasible" for c in assessments(result).values())


def test_zero_action_and_truncation_never_invent_risk():
    query, graph = rated_case()
    query["budget"]["max_paths"] = 1
    result = run_attack_query(query, graph)
    assert result.truncated and not result.is_minimum_proven_over_scope
    assert result.rating_coverage["semantic_search"]["is_truncated"]
    query, graph = rated_case()
    query["initial_state"]["admin_control"] = [query["aliases"]["Host"]]
    result = run_attack_query(query, graph)
    assert len(result.paths) == 1 and not result.paths[0].transition_history
    assert not result.ranking_result["pareto_frontier"]
    assert result.min_effort["associated_likelihood_interval"] is None
    assert result.min_effort["associated_impact"] is None
    assert result.rating_coverage["numeric_requests"] == {
        dimension: {"required": 0, "rated": 0} for dimension in ("C", "P", "I")
    }


def test_prototype_refusal_halts_before_available_scenario_basis():
    query, graph = rated_case()
    empirical = {
        "dataset_classification": "controlled_lab_benchmark_prototype",
        "observations": [
            {
                "trial_id": "synthetic-trial",
                "technique": "obtain_admin_execution_on_host",
                "method": "AdminTo",
                "budget": 12,
                "horizon_seconds": 86400.0,
                "target_complexity_class": "synthetic",
                "outcome": "success",
                "target_hash_id": "synthetic-hash",
                "provenance_reference": "synthetic://trial",
            }
        ],
    }
    query["rating_resolution"]["registries"]["empirical"] = registry(empirical)
    result = run_attack_query(query, graph)
    gaps = [g for g in result.rating_coverage["unresolved_gaps"] if g["dimension"] == "P"]
    assert gaps and all(g["disposition"] == "refused" for g in gaps)
    assert all("Prototype" in g["reason_detail"] for g in gaps)
    assert all(len(g["provider_trace"]) == 1 for g in gaps)
    assert not result.ranking_result["pareto_frontier"]


def test_malformed_numeric_registry_is_not_absence_and_later_prefix_is_reported():
    query, graph = rated_case(shared=True)
    records = query["rating_resolution"]["registries"]["likelihood"]["data"]
    # First prefix absent, later prefixes still resolve; evaluator remains P-unrated.
    query["rating_resolution"]["registries"]["likelihood"] = registry(records[:-1])
    result = run_attack_query(query, graph)
    for candidate in result.rating_coverage["candidates"].values():
        prefixes = candidate["likelihood"]["prefixes"]
        assert len(prefixes) == 2
        assert prefixes[0]["disposition"] != "rated"
        assert prefixes[1]["disposition"] == "rated"
    assert not result.ranking_result["pareto_frontier"]
    query["rating_resolution"]["registries"]["likelihood"] = registry([{"lower": "invalid"}])
    gaps = run_attack_query(query, graph).rating_coverage["unresolved_gaps"]
    assert any(
        g["reason_code"] == "malformed_input" and g["disposition"] == "refused" for g in gaps
    )


@pytest.mark.parametrize("value", [False, None])
def test_numeric_basis_cannot_open_false_or_unknown_semantic_gate(value):
    query, graph = rated_case()
    query["runtime_facts"] = [
        f for f in query["runtime_facts"] if f["predicate"] != "admin_channel"
    ]
    query["runtime_facts"].append(
        {
            "predicate": "admin_channel",
            "subject": "Alice",
            "target": "Host",
            "value": value,
            "origin": "observed_evidence" if value is False else "unknown",
            "provenance_reference": "synthetic://negative-gate",
        }
    )
    result = run_attack_query(query, graph)
    assert not result.paths
    assert not result.ranking_result["pareto_frontier"]
    assert not result.is_minimum_proven_over_scope


def test_snapshot_context_mismatch_is_error_before_numeric_fallback():
    query, graph = base_case()
    query["rating_resolution"]["scope"]["snapshot_id"] = "sha256:" + "0" * 64
    with pytest.raises(ValueError, match="conflicts with semantic query"):
        run_attack_query(query, graph)


@pytest.mark.parametrize("field", ["ranking_query", "ranking_payload"])
def test_empty_explicit_packet_cannot_be_silently_overridden(field):
    query, graph = rated_case()
    query[field] = {}
    with pytest.raises(ValueError, match="conflicts with explicit"):
        run_attack_query(query, graph)


def test_malformed_applicability_is_error_rather_than_missing_class():
    query, graph = rated_case()
    records = query["rating_resolution"]["registries"]["effort"]["data"]
    records[0]["applicability"]["source_ids"] = "not-a-list"
    query["rating_resolution"]["registries"]["effort"] = registry(records)
    with pytest.raises(ValueError, match="source_ids must be a string list"):
        run_attack_query(query, graph)


def goal_case(*, session=False, legitimate=False):
    """Same synthetic snapshot has AdminTo and CanRDP; their consequences differ."""
    query, original = rated_case()
    canonical = copy.deepcopy(original.to_canonical())
    for edge in list(canonical["edges"]):
        if edge["kind"] == "AdminTo":
            rdp = copy.deepcopy(edge)
            rdp.update(
                id=canonical_edge_id(edge["source"], edge["target"], "CanRDP"), kind="CanRDP"
            )
            canonical["edges"].append(rdp)
    canonical["metadata"]["snapshot_id"] = canonical_digest(canonical["edges"])
    graph = EngineGraph.from_canonical(canonical)
    config = query["rating_resolution"]
    scope = config["scope"]
    scope["snapshot_id"] = graph.metadata["snapshot_id"]
    target, actor = scope["target_goal"]["target_asset_id"], scope["foothold_node_id"]
    regs = config["registries"]
    impact = regs["impact"]["data"]
    mapping = impact["mappings"][0]
    mapping["applicability"]["snapshot_id"] = scope["snapshot_id"]
    for record in regs["likelihood"]["data"]:
        record["snapshot_id"] = scope["snapshot_id"]
    if session:
        query["target_goal"]["required_state"] = {"interactive_session": [["Alice", "Host"]]}
        query["allowed_techniques"] = [
            "open_remote_interactive_session",
            "propagate_group_entitlement",
        ]
        query["runtime_facts"].append(
            {
                "predicate": "rdp_available",
                "subject": "Alice",
                "target": "Host",
                "value": True,
                "origin": "observed_evidence",
                "provenance_reference": "synthetic://issue250/RDP",
            }
        )
        for cls in regs["effort"]["data"]:
            cls["applicability"]["techniques"] = ["open_remote_interactive_session"]
        for record in regs["likelihood"]["data"]:
            context = {
                "source_id": record["source_id"],
                "method": "CanRDP",
                "auth_context": None,
                "resource_context": None,
                "policy_id": None,
                "scope": scope["scenario_id"],
            }
            unit = generate_work_unit_id(
                "open_remote_interactive_session",
                actor,
                target,
                "ctx-" + canonical_digest(context).removeprefix("sha256:"),
                "intra_forest",
            )
            record.update(
                method="CanRDP",
                outcome_technique="open_remote_interactive_session",
                ordered_work_prefix=[unit],
                outcome_work_unit_id=unit,
            )
        if legitimate:
            scope["target_goal"].update(goal_id="session", success_event="interactive_session_host")
            mapping["destination_event"] = "interactive_session_host"
            mapping["source_event"] = "synthetic_old_session"
            mapping["consequence_rating"] = "Low"
            mapping["applicability"].update(
                goal_id="session",
                semantic_goal=materialize_query(query, graph).semantic_goal.to_dict(),
            )
            source = regs["impact_source"]["data"]
            source["target_impact_assessments"][target].update(
                success_event="synthetic_old_session", consequence_rating="Low"
            )
            mapping["source_release_canonical_digest"] = canonical_digest(source)
    for name in ("effort", "likelihood", "impact", "impact_source"):
        regs[name] = registry(regs[name]["data"])
    return query, graph


@pytest.mark.parametrize("legitimate", [False, True])
def test_goal_consequence_binding_across_public_entry_points(tmp_path, legitimate):
    admin_query, graph = goal_case()
    query, same_graph = goal_case(session=True, legitimate=legitimate)
    assert same_graph.metadata["snapshot_id"] == graph.metadata["snapshot_id"]
    admin = run_attack_query(admin_query, graph)
    materialized = materialize_query(query, graph)
    actual = materialized.run(graph)
    assert actual.paths and actual.min_effort["minimum_effort_value"] == 1
    assert actual.rating_coverage["numeric_requests"]["C"] == {"required": 2, "rated": 2}
    assert actual.rating_coverage["numeric_requests"]["P"] == {"required": 2, "rated": 2}
    assert actual.rating_coverage["semantic_goal"] != admin.rating_coverage["semantic_goal"]
    assert actual.rating_coverage["numeric_requests"]["I"]["rated"] == int(legitimate)
    if legitimate:
        assert actual.ranking_result["pareto_frontier"]
        assert all(c["impact"] == "Low" for c in assessments(actual).values())
    else:
        assert not actual.ranking_result["pareto_frontier"]
        assert any(
            "semantic_goal_mismatch" in g["reason_detail"]
            for g in actual.rating_coverage["unresolved_gaps"]
        )
        assert all(c["status"] == "feasible" for c in assessments(actual).values())
    orchestration = generate_and_evaluate_attack_paths(
        {},
        graph.to_canonical(),
        actor=materialized.initial_actor,
        initial_state=materialized.initial_attack_state,
        runtime_context=materialized.runtime_context,
        budget=materialized.budget,
        catalog=materialized.catalog,
        scenario_reference=materialized.scenario_reference,
        semantic_goal=materialized.semantic_goal,
        success_state_predicate=materialized.success_state_predicate,
        rating_resolution=query["rating_resolution"],
    )
    assert orchestration["roundtrip_result"] == wire(actual.ranking_result)
    query_path, graph_path = tmp_path / "query.json", tmp_path / "graph.json"
    query_path.write_text(json.dumps(query), encoding="utf-8")
    graph_path.write_text(json.dumps(graph.to_canonical()), encoding="utf-8")
    outputs = []
    for _ in range(2):
        proc = subprocess.run(
            [
                sys.executable,
                "-m",
                "src.engine.query_cli",
                "--query",
                str(query_path),
                "--graph",
                str(graph_path),
                "--label",
                "synthetic",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        assert proc.returncode == 0, proc.stderr
        output = json.loads(proc.stdout)
        validate_public_transport(output)
        assert output["semantic"]["ranking_result"] == wire(actual.ranking_result)
        output.pop("runtime")
        outputs.append(output)
    assert outputs[0] == outputs[1]


def test_missing_scenario_is_not_a_wildcard_or_a_search_veto():
    query, graph = rated_case()
    query.pop("scenario_reference")
    actual = run_attack_query(query, graph)
    assert actual.paths and not actual.ranking_result["pareto_frontier"]
    assert all(c["status"] == "feasible" for c in assessments(actual).values())
    assert all(c["rated"] == 0 for c in actual.rating_coverage["numeric_requests"].values())
    assert all(
        "scenario_authority_missing" in g["reason_detail"]
        for g in actual.rating_coverage["unresolved_gaps"]
    )
    regs = query["rating_resolution"]["registries"]
    classes = regs["effort"]["data"]
    for cls in classes:
        cls["applicability"]["scopes"] = None
    regs["effort"] = registry(classes)
    # A genuinely unscoped reviewed C class still works without a named scenario.
    actual = run_attack_query(query, graph)
    assert actual.min_effort["minimum_effort_value"] == 1
    mapping = regs["impact"]["data"]["mappings"][0]
    mapping["applicability"].pop("scenario_id")
    regs["impact"] = registry(regs["impact"]["data"])
    actual = run_attack_query(query, graph)
    assert actual.rating_coverage["numeric_requests"]["I"] == {"required": 1, "rated": 1}
    assert not actual.ranking_result["pareto_frontier"]  # P is still scenario scoped.
    assert actual.rating_coverage["scenario_authority"]["status"] == "absent"
    query["scenario_reference"] = "conflicting-scenario"
    with pytest.raises(ValueError, match="Rating scenario conflicts"):
        run_attack_query(query, graph)


def test_review_eligible_empirical_p_requires_semantic_scenario_authority(tmp_path):
    """Exercise the real estimator's rated branch, not prototype quarantine.

    In-memory observations/manifest model review-eligible input for this regression
    only; they are not a measured evidence package or a production catalog release.
    """
    query = read(FIXTURES / "asrep/query.json")
    query.pop("ranking_query")
    query.pop("action_bindings")
    graph = EngineGraph.from_snapshot(json.dumps(read(FIXTURES / "asrep/snapshot.json")))
    materialized = materialize_query(query, graph)
    config = rated_case()[0]["rating_resolution"]
    config["policy"] = "production"
    scope = config["scope"]
    scope.update(
        scenario_id=materialized.scenario_reference,
        snapshot_id=graph.metadata["snapshot_id"],
        foothold_node_id=materialized.initial_actor,
        active_work_budget=materialized.budget.max_steps,
    )
    scope["target_goal"]["target_asset_id"] = materialized.target
    regs = config["registries"]
    regs.pop("likelihood")  # A rated P can only come from the real empirical provider.
    effort = regs["effort"]["data"][1]
    effort["basis_category"] = "scenario_assumption"
    effort["applicability"] = {
        "techniques": query["allowed_techniques"],
        "boundaries": ["intra_forest"],
    }
    regs["effort"] = registry([effort])
    source = next(iter(regs["impact_source"]["data"]["target_impact_assessments"].values()))
    source["target_asset_id"] = materialized.target
    source_packet = {"target_impact_assessments": {materialized.target: source}}
    regs["impact_source"] = registry(source_packet)
    mapping = regs["impact"]["data"]["mappings"][0]
    mapping.update(
        target_asset_id=materialized.target,
        evidence_class="scenario_assumption",
        source_release_canonical_digest=canonical_digest(source_packet),
    )
    mapping["applicability"].update(
        semantic_goal=materialized.semantic_goal.to_dict(), snapshot_id=scope["snapshot_id"]
    )
    mapping["applicability"].pop("scenario_id")  # Unscoped I must survive P refusal.
    regs["impact"] = registry(regs["impact"]["data"])
    regs["empirical"] = registry(
        {
            "dataset_classification": "empirical_measurement",
            "manifest": {
                "dataset_classification": "empirical_measurement",
                "review_status": "reviewed",
                "reviewed_by": "test-only-reviewer",
                "reviewed_at": "2026-10-10T00:00:00Z",
                "manifest_digest": "sha256:" + "1" * 64,
                "supported_scenario_ids": [scope["scenario_id"]],
                "supported_prefix_sequences": [["asrep_request", "recover_asrep_secret"]],
            },
            "observations": [
                {
                    "trial_id": f"test-trial-{i}",
                    "technique": "recover_asrep_secret",
                    "method": "offline-password-prediction",
                    "budget": scope["active_work_budget"],
                    "horizon_seconds": 86400.0,
                    "target_complexity_class": "test-only-enterprise",
                    "outcome": "success" if i < 20 else "failure",
                    "target_hash_id": f"test-independent-hash-{i}",
                    "provenance_reference": f"telemetry://test-only/trials/{i}",
                }
                for i in range(25)
            ],
        }
    )
    query["rating_resolution"] = config
    anchored = run_attack_query(query, graph)
    assert anchored.paths and not anchored.binding_diagnostics
    prefixes = next(iter(anchored.rating_coverage["candidates"].values()))["likelihood"]["prefixes"]
    rated = [p for p in prefixes if p["disposition"] == "rated"]
    assert len(rated) == 1
    assert rated[0]["provider_trace"][0]["provider"] == "empirical_likelihood_provider"
    assert rated[0]["basis_category"] == "empirical_evidence"
    query.pop("scenario_reference")
    missing = run_attack_query(query, graph)
    assert [p.nodes for p in missing.paths] == [p.nodes for p in anchored.paths]
    assert not missing.binding_diagnostics
    assert all(materialized.semantic_goal.matches(p.final_state) for p in missing.paths)
    assert all(c["status"] == "feasible" for c in assessments(missing).values())
    assert missing.min_effort["minimum_effort_value"] == anchored.min_effort["minimum_effort_value"]
    for dimension in ("C", "I"):
        assert missing.rating_coverage["numeric_requests"][dimension]["rated"] > 0
        assert (
            missing.rating_coverage["numeric_requests"][dimension]
            == anchored.rating_coverage["numeric_requests"][dimension]
        )
    assert missing.rating_coverage["numeric_requests"]["P"]["rated"] == 0
    refused = [
        g
        for g in missing.rating_coverage["unresolved_gaps"]
        if "scenario_authority_missing" in g["reason_detail"]
    ]
    assert len(refused) == 1
    assert refused[0]["dimension"] == "P"
    assert refused[0]["disposition"] == "refused"
    assert refused[0]["reason_code"] == "missing_evidence"
    assert refused[0]["provider_trace"][0]["provider"] == "empirical_likelihood_provider"
    assert len(refused[0]["provider_trace"]) == 1
    assert not missing.ranking_result["pareto_frontier"]
    validate_public_coverage(missing.rating_coverage)
    for scenario, expected in ((None, missing), (scope["scenario_id"], anchored)):
        if scenario is None:
            query.pop("scenario_reference", None)
        else:
            query["scenario_reference"] = scenario
        decoded = materialize_query(query, graph)
        orchestration = generate_and_evaluate_attack_paths(
            {},
            graph.to_canonical(),
            actor=decoded.initial_actor,
            initial_state=decoded.initial_attack_state,
            runtime_context=decoded.runtime_context,
            budget=decoded.budget,
            catalog=decoded.catalog,
            snapshot_facts=graph.snapshot_facts,
            scenario_reference=decoded.scenario_reference,
            semantic_goal=decoded.semantic_goal,
            success_state_predicate=decoded.success_state_predicate,
            rating_resolution=config,
        )
        assert orchestration["roundtrip_result"] == wire(expected.ranking_result)
        query_path = tmp_path / "empirical-query.json"
        query_path.write_text(json.dumps(query), encoding="utf-8")
        proc = subprocess.run(
            [
                sys.executable,
                "-m",
                "src.engine.query_cli",
                "--query",
                str(query_path),
                "--snapshot",
                str(FIXTURES / "asrep/snapshot.json"),
                "--label",
                "synthetic",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        assert proc.returncode == 0, proc.stderr
        transport = json.loads(proc.stdout)
        validate_public_transport(transport)
        assert transport["semantic"]["ranking_result"] == wire(expected.ranking_result)
        assert transport["semantic"]["rating_coverage"] == wire(expected.rating_coverage)
    query["scenario_reference"] = "conflicting-empirical-scenario"
    with pytest.raises(ValueError, match="Rating scenario conflicts"):
        run_attack_query(query, graph)


def test_opaque_goal_retains_c_p_and_typed_orchestration_enforces_its_goal():
    query, graph = rated_case()
    original = materialize_query(query, graph)
    query.pop("target_goal")
    query["success_state_predicate"] = original.success_state_predicate
    actual = run_attack_query(query, graph)
    assert actual.paths and actual.min_effort["minimum_effort_value"] == 1
    assert actual.rating_coverage["numeric_requests"]["P"]["rated"] == 2
    assert actual.rating_coverage["semantic_goal"] == {"descriptor": None, "sha256": None}
    assert any(
        "semantic_goal_unverifiable" in g["reason_detail"]
        for g in actual.rating_coverage["unresolved_gaps"]
    )
    assert not actual.ranking_result["pareto_frontier"]
    opaque = generate_and_evaluate_attack_paths(
        {},
        graph.to_canonical(),
        actor=original.initial_actor,
        initial_state=original.initial_attack_state,
        runtime_context=original.runtime_context,
        budget=original.budget,
        catalog=original.catalog,
        scenario_reference=original.scenario_reference,
        success_state_predicate=original.success_state_predicate,
        rating_resolution=query["rating_resolution"],
    )
    assert opaque["roundtrip_result"] == wire(actual.ranking_result)
    typed = generate_and_evaluate_attack_paths(
        {},
        graph.to_canonical(),
        actor=original.initial_actor,
        initial_state=original.initial_attack_state,
        runtime_context=original.runtime_context,
        budget=original.budget,
        catalog=original.catalog,
        scenario_reference=original.scenario_reference,
        semantic_goal=original.semantic_goal,
        success_state_predicate=lambda state: True,
        rating_resolution=query["rating_resolution"],
    )
    assert len(typed["search_result"].paths) == 3
    assert all(original.semantic_goal.matches(p.final_state) for p in typed["search_result"].paths)
    assert typed["roundtrip_result"]["pareto_frontier"]
    # A callable conjoined with a declarative goal does not invalidate its necessary capability.
    query["target_goal"] = {"target": "Host", "required_state": {"admin_control": ["Host"]}}
    assert run_attack_query(query, graph).rating_coverage["numeric_requests"]["I"]["rated"] == 1


def test_legacy_automatic_mapping_without_semantic_binding_is_explicitly_refused():
    query, graph = rated_case()
    query["rating_resolution"]["version"] = "public-rating-resolution/1.0.0"
    impact = query["rating_resolution"]["registries"]["impact"]["data"]
    impact["mappings"][0]["applicability"].pop("semantic_goal")
    query["rating_resolution"]["registries"]["impact"] = registry(impact)
    actual = run_attack_query(query, graph)
    assert actual.min_effort["minimum_effort_value"] == 1
    assert not actual.ranking_result["pareto_frontier"]
    assert any(
        "semantic_goal_binding_missing" in g["reason_detail"]
        for g in actual.rating_coverage["unresolved_gaps"]
    )


def test_unanchored_preparation_cannot_prove_minimum_using_unscoped_action_costs():
    query, graph = rated_case(shared=True)
    query.pop("scenario_reference")
    regs = query["rating_resolution"]["registries"]
    for cls in regs["effort"]["data"]:
        cls["applicability"]["scopes"] = None
    regs["effort"] = registry(regs["effort"]["data"])
    result = run_attack_query(query, graph)
    assert result.paths and not result.is_minimum_proven_over_scope
    assert result.min_effort["minimum_effort_value"] is None
    assert result.rating_coverage["binding"]["unapplied_preparation_rules"]
    assert any(
        "scoped work decomposition" in gap["reason_detail"]
        for gap in result.rating_coverage["unresolved_gaps"]
    )


def test_malformed_goal_binding_is_not_missing_and_native_integrity_refusal_wins():
    query, graph = rated_case()
    regs = query["rating_resolution"]["registries"]
    mapping = regs["impact"]["data"]["mappings"][0]
    mapping["applicability"]["semantic_goal"] = "admin"
    regs["impact"] = registry(regs["impact"]["data"])
    result = run_attack_query(query, graph)
    assert result.min_effort["minimum_effort_value"] == 1
    assert any(
        gap["reason_code"] == "malformed_input" and gap["disposition"] == "refused"
        for gap in result.rating_coverage["unresolved_gaps"]
    )
    # Envelope integrity is valid, but the native source-release digest is false.
    mapping["source_release_canonical_digest"] = "sha256:" + "0" * 64
    regs["impact"] = registry(regs["impact"]["data"])
    result = run_attack_query(query, graph)
    assert not result.ranking_result["pareto_frontier"]
    assert any(
        gap["reason_code"] == "conflicting_provider_basis"
        and "Source release canonical digest mismatch" in gap["reason_detail"]
        for gap in result.rating_coverage["unresolved_gaps"]
    )
