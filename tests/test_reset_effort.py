"""Independent finite reset/activation cost oracle; no candidate/cost generator reuse."""

import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest
from test_engine import _edge
from test_identity_entitlement_goal import ACTOR, GROUP, HOST, OTHER
from test_identity_entitlement_goal import scenario as scenario

from scripts.research.source_goal_batch import BatchQueryRequest
from src.engine import run_attack_query
from src.engine.batch import BatchExecutionBudget, run_source_goal_batch
from src.engine.graph import EngineGraph
from src.engine.query_cli import wire
from src.engine.ranking.reset_effort import (
    PROFILE_ID,
    bind_reset_effort,
    load_reset_effort_profile,
)
from src.engine.ranking.resolution_service import canonical_digest
from src.engine.semantics.credentials import replay_path

ROOT = Path(__file__).resolve().parents[1]


def bound_inputs(scenario):
    graph, query = scenario
    query = wire(query)
    return graph, query, bind_reset_effort(query, graph, load_reset_effort_profile(PROFILE_ID))


def independent_cost(path, context):
    """In this finite model one unique A→owner reset costs1; activation costs0.

    The key deliberately contains concrete owners/context, not AWG work IDs.
    Every path must acquire a reset owner's identity before its entitlement.
    """
    resets, activated = set(), set()
    for step in path.transition_history:
        r = step.result.request
        if r.technique_id == "scenario_reset_password":
            assert r.actor == r.source == ACTOR
            resets.add((r.actor, r.source, r.target, context))
        elif r.technique_id == "acquire_reset_identity":
            assert r.actor == r.source and r.target == context
            assert any(owner == r.actor for _, _, owner, _ in resets)
            activated.add((r.actor, context))
        elif r.technique_id == "propagate_group_entitlement":
            if r.target == GROUP:
                assert (r.actor, context) in activated
        else:
            raise AssertionError("Oracle does not silently price another technique")
    return len(resets)


def assert_costs(result, graph):
    for i, path in enumerate(result.paths, 1):
        replay_path(path, graph)
        candidate = result.rating_coverage["candidates"][f"generated_{i:04d}"]
        actual = sum(unit["cost"] for unit in candidate["effort"]["units"].values())
        assert actual == independent_cost(path, HOST)
        for unit in candidate["effort"]["units"].values():
            key = unit["rating_audit"]["lookup_key"]
            assert key["auth_context"] == HOST
            assert (
                unit["cost"]
                == {"scenario_reset_password": 1, "acquire_reset_identity": 0}[key["technique"]]
            )
        assert result.rating_coverage["candidate_summaries"][f"generated_{i:04d}"]["c_complete"]
    assert not any(
        c["p_complete"] or c["i_complete"]
        for c in result.rating_coverage["candidate_summaries"].values()
    )


def test_new_goal_C_only_uses_native_engine_and_independent_oracle(scenario):
    graph, query, bound = bound_inputs(scenario)
    before, after = run_attack_query(query, graph), run_attack_query(bound, graph)
    assert wire(before.paths) == wire(after.paths)
    assert len(after.paths) == 1
    assert after.min_effort["minimum_effort_value"] == 1
    assert after.min_effort["associated_likelihood_interval"] is None
    assert after.min_effort["associated_impact"] is None
    assert set(bound["rating_resolution"]["registries"]) == {"effort"}
    assert after.is_minimum_proven_over_scope
    assert_costs(after, graph)


def two_owners(scenario):
    graph, query = scenario
    canonical = graph.to_canonical()
    third = "S-1-5-21-1000-2000-3000-1103"
    node = copy.deepcopy(graph.node(OTHER))
    node.update(id=third, label="Third identity")
    canonical["nodes"].append(node)
    for edge in list(canonical["edges"]):
        if OTHER not in (edge["source"], edge["target"]):
            continue
        e = _edge(
            third if edge["source"] == OTHER else edge["source"],
            third if edge["target"] == OTHER else edge["target"],
            edge["kind"],
        )
        canonical["edges"].append(e)
    graph = EngineGraph.from_canonical(canonical)
    query = wire(query)
    query["assumptions"] += [
        {
            **f,
            "subject": third if f["subject"] == OTHER else f["subject"],
            "target": third if f["target"] == OTHER else f["target"],
        }
        for f in list(query["assumptions"])
        if OTHER in (f["subject"], f["target"])
    ]
    query["budget"] = {"max_paths": 1000, "max_steps": 6, "max_expansions": 10000}
    return graph, query


def test_different_owners_and_schedules_use_union_work_not_path_hops(scenario):
    graph, query = two_owners(scenario)
    bound = bind_reset_effort(query, graph, load_reset_effort_profile(PROFILE_ID))
    result = run_attack_query(bound, graph)
    assert result.complete and not result.truncated
    assert {independent_cost(p, HOST) for p in result.paths} == {1, 2}
    assert_costs(result, graph)


@pytest.mark.parametrize(
    "field,value",
    [
        ("source_ids", ["other-owner"]),
        ("snapshot_ids", ["other-snapshot"]),
        ("required_auth_context", "other-context"),
        ("work_unit_digests", ["sha256:" + "0" * 64]),
        ("methods", ["other-method"]),
    ],
)
def test_exact_work_owner_context_binding_refuses_foreign_records(scenario, field, value):
    graph, query, bound = bound_inputs(scenario)
    registry = bound["rating_resolution"]["registries"]["effort"]
    for record in registry["data"]:
        record["applicability"][field] = value
    registry["sha256"] = canonical_digest(registry["data"])
    result = run_attack_query(bound, graph)
    assert result.final_goal_reached
    assert result.min_effort is None or result.min_effort["minimum_effort_value"] is None
    assert not any(c["c_complete"] for c in result.rating_coverage["candidate_summaries"].values())


def test_profile_cannot_mint_different_numeric_authority(scenario):
    graph, query = scenario
    profile = load_reset_effort_profile(PROFILE_ID)
    profile["classes"]["scenario_reset_password"]["cost"] = 0
    with pytest.raises(ValueError, match="definition changed"):
        bind_reset_effort(wire(query), graph, profile)


@pytest.mark.parametrize("control", ["missing", "false"])
def test_effort_binding_never_supplies_missing_or_false_prerequisites(scenario, control):
    graph, query = scenario
    query = wire(query)
    gate = next(f for f in query["assumptions"] if f["predicate"] == "authentication_accepted")
    query["assumptions"].remove(gate)
    if control == "false":
        query["runtime_facts"] = [{**gate, "value": False, "origin": "observed_evidence"}]
    result = run_attack_query(
        bind_reset_effort(query, graph, load_reset_effort_profile(PROFILE_ID)), graph
    )
    assert not result.final_goal_reached and not result.paths


def batch_request(graph, query):
    return {
        "schema_version": "batch-query-request/1.0.0",
        "batch_id": "C-only",
        "snapshot_id": graph.metadata["snapshot_id"],
        "evaluation_mode": "scenario",
        "sources": [
            {
                "source_id": "alice",
                "node_id": ACTOR,
                "node_kind": "User",
                "profile_kind": "user_usable_identity",
                "authentication_context": HOST,
                "declared_assumptions": query["assumptions"],
            }
        ],
        "target_manifest": {
            "schema_version": "target-manifest/1.2.0",
            "manifest_id": "new-goal",
            "version": "1.0.0",
            "snapshot_id": graph.metadata["snapshot_id"],
            "domain_sid": "S-1-5-21-1000-2000-3000",
            "default_discovery_goals": ["DA"],
            "targets": [
                {
                    "goal_id": "DA",
                    "category": "tier_0_identity",
                    "target_node_id": GROUP,
                    "target_node_kind": "Group",
                    "display_name": "DA",
                    "goal_kind": "usable_identity_entitlement",
                    "required_state": {},
                    "technical_consequence": "Usable identity with entitlement",
                    "impact_rating": "Unknown",
                    "required_control_level": "admin_entitlement",
                }
            ],
        },
        "common_budget": query["budget"],
    }


def test_batch_compilation_worker_and_checkpoint_preserve_C_scope(scenario, tmp_path):
    graph, query = scenario
    query = wire(query)
    request = batch_request(graph, query)
    BatchQueryRequest.from_dict(request)
    options = dict(allowed_techniques=query["allowed_techniques"], effort_profile=PROFILE_ID)
    result = run_source_goal_batch(request, graph, checkpoint=tmp_path / "cp.json", **options)
    cell = result.source_goal_matrix["alice"]["DA"]
    assert cell.final_goal_reached and cell.min_effort == 1
    assert cell.likelihood_interval is None
    worker = run_source_goal_batch(
        request, graph, execution_budget=BatchExecutionBudget(per_query_seconds=30), **options
    )
    assert (
        result.reproducibility["inputs"]["public_queries"]
        == worker.reproducibility["inputs"]["public_queries"]
    )
    resumed = run_source_goal_batch(
        request, graph, checkpoint=tmp_path / "cp.json", resume=True, **options
    )
    assert resumed.reproducibility["runtime"]["reused_cells"] == 1
    with pytest.raises(ValueError, match="CHECKPOINT_SCOPE_MISMATCH"):
        run_source_goal_batch(
            request,
            graph,
            checkpoint=tmp_path / "cp.json",
            resume=True,
            allowed_techniques=query["allowed_techniques"],
        )
    traced = next(iter(result.reproducibility["inputs"]["public_queries"].values()))["query"]
    assert run_attack_query(traced, graph).min_effort["minimum_effort_value"] == 1
    with pytest.raises(ValueError, match="conflicts"):
        run_source_goal_batch(
            {**request, "rating_resolution": traced["rating_resolution"]}, graph, **options
        )


def test_existing_scenario_policy_and_effort_profile_compose(scenario):
    from src.engine.semantics.scenario_policy import SEAMLESS_SNAPSHOT_ID

    graph, query = scenario
    raw = graph.to_canonical()
    raw["metadata"]["snapshot_id"] = SEAMLESS_SNAPSHOT_ID
    graph = EngineGraph.from_canonical(raw)
    request = batch_request(graph, wire(query))
    request["sources"][0]["declared_assumptions"] = []
    result = run_source_goal_batch(
        request,
        graph,
        allowed_techniques=query["allowed_techniques"],
        effort_profile=PROFILE_ID,
        scenario_policy="seamless-standard-v1",
    )
    assert result.source_goal_matrix["alice"]["DA"].min_effort == 1
    trace = next(iter(result.reproducibility["inputs"]["public_queries"].values()))
    assert trace["query"]["scenario_policy_metadata"]["policy_assumptions_count"] > 0
    assert trace["query"]["effort_profile_metadata"]["status"] == "bound"


def test_capped_success_has_C_without_optimum_claim(scenario):
    graph, query = two_owners(scenario)
    query["budget"]["max_paths"] = 1
    r = run_attack_query(
        bind_reset_effort(query, graph, load_reset_effort_profile(PROFILE_ID)), graph
    )
    assert r.final_goal_reached and r.truncated and r.min_effort["minimum_effort_value"] == 1
    assert not r.is_minimum_proven_over_scope


def test_unpriced_active_work_does_not_gain_C_or_global_minimum(scenario):
    graph, query = scenario
    raw = graph.to_canonical()
    raw["edges"].append(_edge(ACTOR, HOST, "AdminTo"))
    graph = EngineGraph.from_canonical(raw)
    query = wire(query)
    query["initial_state"]["usable_identity"] = [[ACTOR, HOST]]
    query["allowed_techniques"].append("obtain_admin_execution_on_host")
    query["assumptions"] += [
        {
            "predicate": p,
            "subject": ACTOR,
            "target": HOST,
            "value": True,
            "scope": HOST,
            "provenance_reference": "synthetic://unpriced-work",
            "rationale": "Fixture",
        }
        for p in ("admin_channel", "authentication_accepted")
    ]
    result = run_attack_query(
        bind_reset_effort(query, graph, load_reset_effort_profile(PROFILE_ID)), graph
    )
    complete = [s["c_complete"] for s in result.rating_coverage["candidate_summaries"].values()]
    assert any(complete) and not all(complete)
    assert result.min_effort["minimum_effort_value"] == 1
    assert not result.is_minimum_proven_over_scope


def test_bound_query_runs_through_existing_executable_CLI(scenario, tmp_path):
    graph, query, bound = bound_inputs(scenario)
    gp = tmp_path / "graph.json"
    qp = tmp_path / "query.json"
    out = tmp_path / "result.json"
    gp.write_text(json.dumps(graph.to_canonical()))
    qp.write_text(json.dumps(bound))
    subprocess.run(
        [
            sys.executable,
            "-m",
            "src.engine",
            "query",
            "--label",
            "synthetic",
            "--graph",
            str(gp),
            "--query",
            str(qp),
            "--output",
            str(out),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    data = json.loads(out.read_text())
    assert data["semantic"]["min_effort"]["minimum_effort_value"] == 1
    api = run_attack_query(bound, graph)
    assert data["semantic"]["candidates"] == [
        {"candidate_id": f"generated_{i:04d}", **wire(path)} for i, path in enumerate(api.paths, 1)
    ]
    assert data["semantic"]["rating_coverage"] == wire(api.rating_coverage)


@pytest.mark.parametrize("case", ["Computer", "host_goal", "cross_domain"])
def test_unsupported_scopes_stay_visible_without_new_ratings(scenario, case):
    graph, query = scenario
    query = wire(query)
    if case == "Computer":
        query["initial_actor"] = HOST
        query["initial_state"] = {"control": [HOST]}
    elif case == "host_goal":
        query["target"] = HOST
        query["target_goal"] = {"target": HOST, "required_state": {"admin_control": [HOST]}}
    else:
        raw = graph.to_canonical()
        next(n for n in raw["nodes"] if n["id"] == HOST)["domain"] = "OTHER.TEST"
        graph = EngineGraph.from_canonical(raw)
    compiled = bind_reset_effort(query, graph, load_reset_effort_profile(PROFILE_ID))
    assert compiled["effort_profile_metadata"]["status"] == "not_applicable"
    assert compiled["effort_profile_metadata"]["reason"]
    assert compiled.get("rating_resolution") is None


@pytest.mark.parametrize("case", ["existing_membership", "seeded_identity"])
def test_profile_does_not_present_vacuous_P_as_a_new_adoption(scenario, case):
    graph, query = scenario
    query = wire(query)
    query["initial_state"]["usable_identity"] = [[ACTOR, HOST]]
    if case == "existing_membership":
        raw = graph.to_canonical()
        raw["edges"].append(_edge(ACTOR, GROUP, "MemberOf"))
        graph = EngineGraph.from_canonical(raw)
    else:
        query["initial_state"]["usable_identity"].append([OTHER, HOST])
    compiled = bind_reset_effort(query, graph, load_reset_effort_profile(PROFILE_ID))
    assert compiled["effort_profile_metadata"]["status"] == "not_applicable"
    assert compiled.get("rating_resolution") is None
    assert wire(run_attack_query(compiled, graph).paths) == wire(
        run_attack_query(query, graph).paths
    )


def test_exposure_CLI_generates_goals_and_binds_C_without_rating_JSON(scenario, tmp_path):
    graph, query = scenario
    query = wire(query)
    raw = graph.to_canonical()
    raw["nodes"].append(
        {
            "id": "S-1-5-21-1000-2000-3000",
            "kind": "Domain",
            "domain": "EXAMPLE.TEST",
            "label": "EXAMPLE.TEST",
            "is_boundary": False,
        }
    )
    gp, facts, output = tmp_path / "graph.json", tmp_path / "gates.json", tmp_path / "exposure"
    gp.write_text(json.dumps(raw))
    facts.write_text(json.dumps(query["assumptions"]))
    command = [
        sys.executable,
        "-m",
        "scripts.exposure",
        "--graph",
        str(gp),
        "--source",
        ACTOR,
        "--authentication-context",
        HOST,
        "--user-profile",
        "user_usable_identity",
        "--evaluation-mode",
        "scenario",
        "--assumptions",
        str(facts),
        "--effort-profile",
        PROFILE_ID,
        "--output-dir",
        str(output),
    ]
    for technique in query["allowed_techniques"]:
        command += ["--technique", technique]
    subprocess.run(command, cwd=ROOT, text=True, capture_output=True, check=True)
    summary = json.loads((output / "summary.json").read_text())
    assert summary["batch"]["successful_cells"] == summary["batch"]["effort_rated_cells"] == 1
    assert summary["batch"]["likelihood_rated_cells"] == 0
    assert summary["effort_profile"]["profile_id"] == PROFILE_ID
    result = json.loads((output / "result.json").read_text())
    cell = next(iter(next(iter(result["source_goal_matrix"].values())).values()))
    assert cell["min_effort"] == 1
