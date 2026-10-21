"""Finite chains verify neo C independently of the production rating catalog."""

import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest
from test_computer_foothold_boundary import CASES
from test_engine import ACTOR, GROUP, HOST, TOY, _edge, _graph
from test_identity_entitlement_goal import OTHER
from test_machine_identity_profile import request as machine_request
from test_machine_identity_profile import scenario as machine_scenario

from src.engine.batch import BatchExecutionBudget, run_source_goal_batch
from src.engine.query import run_attack_query
from src.engine.query_cli import execute, wire
from src.engine.ranking.effort_profiles import (
    NEO_PROFILE_ID,
    bind_effort_profile,
    load_effort_profile,
)
from src.engine.ranking.resolution_service import canonical_digest
from src.engine.semantics.credentials import replay_path

ROOT = Path(__file__).resolve().parents[1]
RESET = ["scenario_reset_password", "acquire_reset_identity"]
ADMIN = "obtain_admin_execution_on_host"
MEMBER = "propagate_group_entitlement"


def inputs(route):
    user = copy.deepcopy(next(n for n in TOY["nodes"] if n["id"] == ACTOR))
    user.update(id=OTHER, label="Acquired identity", enabled=True)
    if route == "inherited":
        edges = [_edge(ACTOR, GROUP, "MemberOf"), _edge(GROUP, OTHER, "GenericAll")]
        techniques = [MEMBER, *RESET, ADMIN]
    elif route == "acl":
        edges = [_edge(ACTOR, OTHER, "WriteDacl")]
        techniques = ["grant_new_object_right", *RESET, ADMIN]
    else:
        edges = [_edge(ACTOR, GROUP, "GenericAll"), _edge(GROUP, HOST, "AdminTo")]
        techniques = ["genericall_add_member", MEMBER, ADMIN]
    if route != "membership":
        edges.append(_edge(OTHER, HOST, "AdminTo"))
    graph = _graph(edges, extra_nodes=[user])
    gates = (
        "security_group",
        "membership_usable",
        "membership_change_allowed",
        "directory_write_allowed",
        "password_policy_accepts",
        "network_rpc_reachable",
        "network_kdc_reachable",
        "authentication_accepted",
        "admin_channel",
    )
    assumptions = [
        {
            "predicate": p,
            "subject": actor,
            "target": target,
            "value": True,
            "scope": "neo-finite",
            "rationale": "Explicit finite scenario",
            "provenance_reference": "synthetic://neo-finite",
        }
        for p in gates
        for actor in (ACTOR, OTHER)
        for target in (OTHER, GROUP, HOST)
    ]
    return graph, {
        "initial_actor": ACTOR,
        "initial_state": {"control": [ACTOR]},
        "authentication_context": HOST,
        "target": HOST,
        "target_goal": {"target": HOST, "required_state": {"admin_control": [HOST]}},
        "allowed_techniques": techniques,
        "assumptions": assumptions,
        "scenario_reference": "neo-finite",
        "budget": {"max_paths": 100, "max_steps": 6, "max_expansions": 1000},
    }


def bind(graph, query):
    return bind_effort_profile(query, graph, load_effort_profile(NEO_PROFILE_ID))


@pytest.mark.parametrize("route,expected", [("inherited", 2), ("acl", 4), ("membership", 2)])
def test_new_C_covers_whole_chains_without_changing_feasibility(route, expected):
    graph, query = inputs(route)
    before = run_attack_query(query, graph)
    after = run_attack_query(bind(graph, query), graph)
    assert before.paths and wire(before.paths) == wire(after.paths)
    assert before.min_effort is None
    assert before.expansions == after.expansions
    assert after.complete and not after.truncated
    assert after.min_effort["minimum_effort_value"] == expected
    assert after.is_minimum_proven_over_scope
    for index, path in enumerate(after.paths, 1):
        replay_path(path, graph)
        # Independent, concrete work-set oracle; no provider/catalog calls.
        costs = {
            "scenario_reset_password": 1,
            "acquire_reset_identity": 0,
            "genericall_add_member": 1,
            "grant_new_object_right": 2,
            ADMIN: 1,
        }
        work = {
            (
                s.result.request.technique_id,
                s.result.request.actor,
                s.result.request.source,
                s.result.request.target,
                HOST,
            )
            for s in path.transition_history
            if s.result.request.technique_id != MEMBER
        }
        independent = sum(costs[technique] for technique, *_ in work)
        packet = after.rating_coverage["candidates"][f"generated_{index:04d}"]
        assert sum(u["cost"] for u in packet["effort"]["units"].values()) == independent
        assert independent >= expected
        summary = after.rating_coverage["candidate_summaries"][f"generated_{index:04d}"]
        assert summary["c_complete"] and not summary["p_complete"] and not summary["i_complete"]


@pytest.mark.parametrize("gate", ["missing", "false"])
def test_price_does_not_supply_prerequisites(gate):
    graph, query = inputs("inherited")
    query["assumptions"] = [
        f for f in query["assumptions"] if f["predicate"] != "authentication_accepted"
    ]
    if gate == "false":
        query["runtime_facts"] = [
            {
                "predicate": "authentication_accepted",
                "subject": OTHER,
                "target": HOST,
                "value": False,
                "origin": "observed_evidence",
                "scope": "neo-finite",
                "rationale": "Observed refusal",
                "provenance_reference": "synthetic://refusal",
            }
        ]
    before = run_attack_query(query, graph)
    after = run_attack_query(bind(graph, query), graph)
    assert not after.paths and not after.final_goal_reached
    assert before.status == after.status


@pytest.mark.parametrize("field", ["actor", "source", "target"])
def test_foreign_intermediate_nodes_are_not_priced(field):
    graph, query = inputs("inherited")
    bound = bind(graph, query)
    registry = bound["rating_resolution"]["registries"]["effort"]
    # Remove a distinct participant from the reset record's domain allow-list.
    excluded = {"actor": ACTOR, "source": GROUP, "target": OTHER}[field]
    for record in registry["data"]:
        if record["name"] == "scenario_reset_password":
            record["applicability"]["node_ids"].remove(excluded)
    registry["sha256"] = canonical_digest(registry["data"])
    result = run_attack_query(bound, graph)
    assert result.paths
    assert result.min_effort is None or result.min_effort["minimum_effort_value"] is None


def test_cross_domain_target_is_outside_profile():
    graph, query = inputs("inherited")
    data = graph.to_canonical()
    next(n for n in data["nodes"] if n["id"] == HOST)["domain"] = "FOREIGN.TEST"
    foreign = type(graph).from_canonical(data)
    compiled = bind(foreign, query)
    assert compiled["effort_profile_metadata"]["status"] == "not_applicable"
    assert "rating_resolution" not in compiled


def test_unknown_technique_keeps_whole_path_unrated():
    graph, query = inputs("membership")
    query["allowed_techniques"] = ["open_remote_interactive_session"]
    query["target_goal"]["required_state"] = {"interactive_session": [[ACTOR, HOST]]}
    data = graph.to_canonical()
    data["edges"] = [_edge(ACTOR, HOST, "CanRDP")]
    graph = type(graph).from_canonical(data)
    query["assumptions"].append(
        {
            "predicate": "rdp_available",
            "subject": ACTOR,
            "target": HOST,
            "value": True,
            "scope": "neo-finite",
            "rationale": "RDP available",
            "provenance_reference": "synthetic://rdp",
        }
    )
    result = run_attack_query(bind(graph, query), graph)
    assert result.paths
    assert result.min_effort is None or result.min_effort["minimum_effort_value"] is None


def test_profile_cannot_override_an_explicit_registry():
    graph, query = inputs("inherited")
    with pytest.raises(ValueError, match="conflicts"):
        bind(graph, bind(graph, query))


def test_compiled_query_runs_through_public_CLI(tmp_path):
    graph, query = inputs("acl")
    compiled = bind(graph, query)
    gp, qp, out = (tmp_path / n for n in ("graph.json", "query.json", "output.json"))
    gp.write_text(json.dumps(graph.to_canonical()))
    qp.write_text(json.dumps(compiled))
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
        check=True,
        capture_output=True,
        text=True,
    )
    semantic = json.loads(out.read_text())["semantic"]
    native = execute(compiled, graph)
    assert {key: semantic[key] for key in native} == native


def test_acquired_identity_can_pay_for_a_second_reset():
    graph, query = inputs("inherited")
    data = graph.to_canonical()
    third = "S-1-5-21-1000-2000-3000-1103"
    node = copy.deepcopy(graph.node(OTHER))
    node.update(id=third, label="Second acquired identity")
    data["nodes"].append(node)
    data["edges"] = [
        _edge(ACTOR, OTHER, "GenericAll"),
        _edge(OTHER, third, "GenericAll"),
        _edge(third, HOST, "AdminTo"),
    ]
    graph = type(graph).from_canonical(data)
    query["assumptions"] += [
        {**f, "target": third} for f in list(query["assumptions"]) if f["target"] == OTHER
    ]
    query["assumptions"] += [
        {
            **f,
            "subject": third if f["subject"] == OTHER else f["subject"],
            "target": third if f["target"] == OTHER else f["target"],
        }
        for f in list(query["assumptions"])
        if OTHER in (f["subject"], f["target"])
    ]
    query["allowed_techniques"] = RESET + [ADMIN]
    result = run_attack_query(bind(graph, query), graph)
    assert result.paths and result.min_effort["minimum_effort_value"] == 3
    for path in result.paths:
        replay_path(path, graph)
    assert any(
        step.result.request.technique_id == "scenario_reset_password"
        and step.result.request.actor == OTHER
        for path in result.paths
        for step in path.transition_history
    )


def test_passive_membership_adds_no_work_or_C():
    graph, query = inputs("inherited")
    query["initial_state"] = {"usable_identity": [[ACTOR, HOST]]}
    query["target"] = GROUP
    query["target_goal"] = {"target": GROUP, "kind": "usable_identity_entitlement"}
    query["allowed_techniques"] = [MEMBER]
    result = run_attack_query(bind(graph, query), graph)
    assert result.paths and result.min_effort["minimum_effort_value"] == 0
    for candidate in result.rating_coverage["candidates"].values():
        assert candidate["effort"]["units"] == {}


def test_foreign_intermediate_is_automatically_excluded_from_C_scope():
    graph, query = inputs("inherited")
    data = graph.to_canonical()
    next(n for n in data["nodes"] if n["id"] == OTHER)["domain"] = "FOREIGN.TEST"
    graph = type(graph).from_canonical(data)
    compiled = bind(graph, query)
    assert compiled["effort_profile_metadata"]["status"] == "bound"
    result = run_attack_query(compiled, graph)
    assert result.paths
    assert result.min_effort is None or result.min_effort["minimum_effort_value"] is None


@pytest.mark.parametrize("worker", [False, True])
def test_batch_profile_survives_worker_and_resume(tmp_path, worker):
    graph, query = machine_scenario(CASES[2])
    request = machine_request(graph, query)
    options = {
        "allowed_techniques": RESET + [MEMBER],
        "effort_profile": NEO_PROFILE_ID,
        "checkpoint": tmp_path / "batch.json",
        "execution_budget": BatchExecutionBudget(per_query_seconds=10) if worker else None,
    }
    result = run_source_goal_batch(request, graph, **options)
    assert result.summary["effort_rated_cells"] == result.summary["successful_cells"] == 1
    resumed = run_source_goal_batch(request, graph, resume=True, **options)
    assert resumed.source_goal_matrix == result.source_goal_matrix


@pytest.mark.parametrize("case", [CASES[0], CASES[1], CASES[2], CASES[3], CASES[6], CASES[8]])
def test_machine_identity_boundary_remains_semantic(case):
    graph, query = machine_scenario(case)
    before = run_attack_query(query, graph)
    after = run_attack_query(bind(graph, query), graph)
    assert wire(before.paths) == wire(after.paths)
    if case.name == "explicit_machine_identity":
        assert after.min_effort["minimum_effort_value"] == 1
    else:
        assert not after.paths
