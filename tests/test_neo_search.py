"""Finite oracles for neo guidance, C selection, and unchanged prerequisites."""

import copy

import pytest
from test_engine import ACTOR, GROUP, HOST, _edge
from test_neo_effort import ADMIN, OTHER, bind, inputs

from src.engine.program_identity import program_key
from src.engine.query import materialize_query, run_attack_query
from src.engine.query_cli import execute
from src.engine.semantics.credentials import replay_path


@pytest.mark.parametrize("route", ["inherited", "acl", "membership"])
def test_exhaustive_guidance_preserves_every_program_and_cost(route):
    graph, query = inputs(route)
    fifo = run_attack_query(bind(graph, query), graph)
    guided = run_attack_query(bind(graph, {**query, "search_order": "neo_guided"}), graph)
    assert fifo.complete and guided.complete
    assert {program_key(p) for p in guided.paths} == {program_key(p) for p in fifo.paths}
    assert guided.min_effort == fifo.min_effort

    def order(result):
        return [(p["program_id"], p["effort"]) for p in result.top_k_result["programs"]]

    assert order(guided) == order(fifo)
    for path in guided.paths:
        assert replay_path(path, graph) == path.final_state


def test_high_fanout_does_not_consume_budget_before_visiting_useful_child():
    graph, query = inputs("inherited")
    data = graph.to_canonical()
    data["edges"] = [_edge(ACTOR, OTHER, "GenericAll"), _edge(OTHER, GROUP, "MemberOf")]
    template = next(n for n in data["nodes"] if n["id"] == OTHER)
    for i in range(40):
        decoy = {**copy.deepcopy(template), "id": f"S-1-5-21-1000-2000-3000-{2000 + i}"}
        data["nodes"].append(decoy)
        data["edges"].append(_edge(ACTOR, decoy["id"], "GenericAll"))
    graph = type(graph).from_canonical(data)
    query["target"] = GROUP
    query["target_goal"] = {"target": GROUP, "kind": "usable_identity_entitlement"}
    query["allowed_techniques"].remove(ADMIN)
    query["initial_state"]["usable_identity"] = [[ACTOR, HOST]]
    query["budget"] = {"max_paths": 1, "max_steps": 3, "max_expansions": 6}
    fifo = run_attack_query(bind(graph, query), graph)
    guided = run_attack_query(bind(graph, {**query, "search_order": "neo_guided"}), graph)
    assert not fifo.paths and fifo.expansions == 6
    assert guided.final_goal_reached and guided.expansions <= 6
    assert guided.min_effort["minimum_effort_value"] == 1
    assert not guided.is_minimum_proven_over_scope
    assert replay_path(guided.paths[0], graph) == guided.paths[0].final_state


def computer_acl_decoys(count):
    graph, query = inputs("inherited")
    raw = graph.to_canonical()
    raw["edges"] = [_edge(ACTOR, OTHER, "GenericAll"), _edge(OTHER, GROUP, "MemberOf")]
    host = next(n for n in raw["nodes"] if n["id"] == HOST)
    for index in range(count):
        node = {**host, "id": f"70000000-0000-4000-8000-{index:012d}"}
        raw["nodes"].append(node)
        raw["edges"].extend(
            [
                _edge(ACTOR, node["id"], "GenericAll"),
                _edge(node["id"], GROUP, "MemberOf"),
            ]
        )
        query["assumptions"].append(
            {
                "predicate": "directory_write_allowed",
                "subject": ACTOR,
                "target": node["id"],
                "value": True,
                "scope": "neo-finite",
                "rationale": "Real ACL mutation, no machine identity",
                "provenance_reference": "synthetic://neo-computer-decoy",
            }
        )
    query["target"] = GROUP
    query["target_goal"] = {"target": GROUP, "kind": "usable_identity_entitlement"}
    query["initial_state"]["usable_identity"] = [[ACTOR, HOST]]
    query["allowed_techniques"].remove(ADMIN)
    query["allowed_techniques"] += ["genericall_grant_write_dacl", "grant_new_object_right"]
    return type(graph).from_canonical(raw), query


def test_computer_acl_is_not_a_shortcut_to_the_machine_identity():
    graph, query = computer_acl_decoys(20)
    query["budget"] = {"max_paths": 1, "max_steps": 4, "max_expansions": 6}
    result = run_attack_query(bind(graph, {**query, "search_order": "neo_guided"}), graph)
    assert result.final_goal_reached and result.expansions <= 6
    assert result.min_effort["minimum_effort_value"] == 1
    assert not result.best_path.final_state.admin_control
    assert replay_path(result.best_path, graph) == result.best_path.final_state


def test_computer_hint_change_keeps_all_programs_and_C_under_exhaustive_budget():
    graph, query = computer_acl_decoys(1)
    query["budget"] = {"max_paths": 100, "max_steps": 4, "max_expansions": 2000}
    query["top_k"] = 100
    fifo = run_attack_query(bind(graph, query), graph)
    guided = run_attack_query(bind(graph, {**query, "search_order": "neo_guided"}), graph)
    assert len(fifo.paths) > 1
    assert {program_key(p) for p in fifo.paths} == {program_key(p) for p in guided.paths}
    assert [(p["program_id"], p["effort"]) for p in fifo.top_k_result["programs"]] == [
        (p["program_id"], p["effort"]) for p in guided.top_k_result["programs"]
    ]


@pytest.mark.parametrize("value", [None, False])
def test_guidance_cannot_supply_missing_or_false_authentication(value):
    graph, query = inputs("inherited")
    query["search_order"] = "neo_guided"
    query["assumptions"] = [
        f for f in query["assumptions"] if f["predicate"] != "authentication_accepted"
    ]
    if value is False:
        query["runtime_facts"] = [
            {
                "predicate": "authentication_accepted",
                "subject": OTHER,
                "target": HOST,
                "value": False,
                "origin": "observed_evidence",
                "provenance_reference": "synthetic://refusal",
            }
        ]
    result = run_attack_query(bind(graph, query), graph)
    assert not result.paths
    assert result.top_k_result["returned_count"] == 0
    if value is None:
        assert not result.is_no_path_proven_over_scope


def test_C_ranking_compares_different_routes_without_P_or_I():
    graph, query = inputs("acl")
    data = graph.to_canonical()
    data["edges"].append(_edge(ACTOR, HOST, "AdminTo"))
    data["edges"].extend([_edge(ACTOR, GROUP, "MemberOf"), _edge(GROUP, OTHER, "GenericAll")])
    graph = type(graph).from_canonical(data)
    query["allowed_techniques"].append("propagate_group_entitlement")
    query.update(search_order="neo_guided", top_k=100)
    result = run_attack_query(bind(graph, query), graph)
    assert result.complete and result.is_minimum_proven_over_scope
    programs = result.top_k_result["programs"]
    # Direct admin: 1; inherited reset + admin: 2; ACL + reset + admin: 4.
    assert programs[0]["effort"] == 1
    assert {1, 2, 4} <= {p["effort"] for p in programs}
    assert all(p["likelihood_interval"] is None and p["impact"] is None for p in programs)
    assert result.top_k_result["guarantee"]["is_k_best_proven"]
    public = execute(bind(graph, query), graph)
    assert public["top_k"]["rating_policy"]["required_dimensions"] == ["C"]
    assert not public["top_k"]["rating_policy"]["missing_supplementary_blocks_selection"]


def test_unrated_C_is_excluded_instead_of_treated_as_zero():
    graph, query = inputs("acl")
    data = graph.to_canonical()
    data["edges"].append(_edge(ACTOR, HOST, "AdminTo"))
    graph = type(graph).from_canonical(data)
    query = bind(graph, query)
    from src.engine.ranking.resolution_service import canonical_digest

    registry = query["rating_resolution"]["registries"]["effort"]
    registry["data"] = [r for r in registry["data"] if r["name"] != ADMIN]
    registry["sha256"] = canonical_digest(registry["data"])
    result = run_attack_query(query, graph)
    assert result.paths and result.top_k_result["returned_count"] == 0
    assert {e["reason"] for e in result.top_k_result["coverage"]["exclusions"]} == {
        "effort_unrated"
    }


def test_unsupported_catalog_falls_back_explicitly_and_explicit_k_is_kept():
    graph, query = inputs("membership")
    query.update(search_order="neo_guided", top_k=1)
    query.pop("allowed_techniques")
    bound = bind(graph, query)
    material = materialize_query(bound, graph)
    assert material.top_k == 1
    assert material.search_strategy["effective"] == "fifo"
    assert material.search_strategy["fallback_reason"] == "unsupported_goal_or_catalog"
