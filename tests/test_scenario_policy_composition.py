"""A disconnected component must not suppress declared reset assumptions.

Independent expected chain: Computer --GenericAll--> User --MemberOf--> DA.
The policy threshold at 200 edges must not change that three-action witness.
"""

import copy
from dataclasses import replace

import pytest
from test_computer_foothold_boundary import CASES, TECHNIQUES
from test_engine import ACTOR, GROUP, HOST, _edge
from test_machine_identity_profile import request, scenario

from src.engine.batch import run_source_goal_batch
from src.engine.graph import EngineGraph
from src.engine.semantics.catalog import load_catalog
from src.engine.semantics.scenario_policy import (
    SEAMLESS_STANDARD_PROFILE,
    TECHNIQUE_EDGE_KINDS,
)


def inputs(padding=0, *, right=True):
    graph, query = scenario(CASES[2])
    raw = graph.to_canonical()
    if not right:
        raw["edges"] = [e for e in raw["edges"] if e["kind"] != "GenericAll"]
    for i in range(padding):
        node = copy.deepcopy(graph.node(ACTOR))
        node.update(id=f"S-1-5-21-1000-2000-3000-{8000 + i}", label=f"Uncontrolled{i}")
        raw["nodes"].append(node)
        raw["edges"].append(_edge(node["id"], GROUP, "MemberOf"))
    graph = EngineGraph.from_canonical(raw)
    req = request(graph, query)
    for source in req["sources"]:
        source["declared_assumptions"] = []
    policy = replace(SEAMLESS_STANDARD_PROFILE, bound_snapshot_id=graph.metadata["snapshot_id"])
    return graph, req, policy


@pytest.mark.parametrize("padding", [0, 198, 199, 201])
def test_same_identity_chain_across_query_local_policy_threshold(padding):
    graph, req, policy = inputs(padding)
    result = run_source_goal_batch(
        req,
        graph,
        allowed_techniques=TECHNIQUES,
        scenario_policy=policy,
        effort_profile="reset-activation-c-v2",
    ).to_dict()
    cell = next(iter(next(iter(result["source_goal_matrix"].values())).values()))
    assert cell["final_goal_reached"] and cell["min_effort"] == 1
    trace = next(iter(result["reproducibility"]["inputs"]["public_queries"].values()))
    path = trace["result"]["paths"][0]
    assert [s["result"]["request"]["technique_id"] for s in path["transition_history"]] == list(
        TECHNIQUES
    )
    assert [s["result"]["request"]["actor"] for s in path["transition_history"]] == [
        HOST,
        ACTOR,
        ACTOR,
    ]
    assert all(a["origin"] == "declared_assumption" for a in trace["query"]["assumptions"])
    assert all(
        a["provenance_reference"].startswith("policy://") for a in trace["query"]["assumptions"]
    )


@pytest.mark.parametrize("veto", ["no_right", "observed_false"])
def test_profile_does_not_create_permission_or_override_observed_false(veto):
    graph, req, policy = inputs(201, right=veto != "no_right")
    facts = []
    if veto == "observed_false":
        facts = [
            {
                "predicate": "network_rpc_reachable",
                "subject": HOST,
                "target": ACTOR,
                "value": False,
                "origin": "observed_evidence",
                "provenance_reference": "synthetic://rpc-blocked",
            }
        ]
    result = run_source_goal_batch(
        req, graph, allowed_techniques=TECHNIQUES, scenario_policy=policy, runtime_facts=facts
    )
    assert not any(
        c.final_goal_reached for row in result.source_goal_matrix.values() for c in row.values()
    )


def test_current_structural_catalog_ids_are_recognized_by_policy_filter():
    covered = {"GenericAll", "WriteDacl", "MemberOf", "AdminTo", "CanRDP", "CanPSRemote"}
    for technique in load_catalog():
        if technique.relationship in covered:
            assert TECHNIQUE_EDGE_KINDS[technique.id] == technique.relationship
