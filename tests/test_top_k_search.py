"""Top-K uses independent Ledger E arithmetic, not generated output as expected."""

from __future__ import annotations

import copy
import json
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from referencing import Registry, Resource

from scripts.check_contract import canonical_edge_id
from src.engine import AttackQuery, materialize_query, run_attack_query
from src.engine.program_identity import program_key
from src.engine.query_cli import canonical_json, digest
from src.engine.semantics import AttackState, RuntimeContext
from src.engine.top_k import collect_assessments, select_top_k

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests/fixtures"


def read(path):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


@pytest.fixture
def case():
    query = read("tests/fixtures/query_cli/two-routes-query.json")
    query["ranking_query"] = read("docs/research/ratings/week4/synthetic-a2-e.json")["query"]
    query["top_k"] = 3
    graph = read("tests/fixtures/attack_scenarios/graphs/two-routes.json")
    return query, graph


def action_signature(result, program):
    return "/".join(collect_assessments(result)[program["candidate_id"]]["bound_action_ids"])


@pytest.mark.parametrize("k", [1, 2, 3, 8])
def test_complete_top_k_matches_independent_oracle_and_minimum(case, k):
    query, graph = case
    query["top_k"] = k
    before = copy.deepcopy((query, graph))
    result = run_attack_query(query, graph)
    top = result.top_k_result
    oracle = read("tests/fixtures/query_cli/top-k-oracle.json")
    assert (query, graph) == before
    assert top["returned_count"] == min(k, oracle["distinct_program_count"])
    assert top["guarantee"]["is_k_best_proven"]
    assert top["guarantee"]["fewer_than_k_proven"] == (k > 3)
    assert top["programs"][0]["candidate_id"] == result.min_effort["best_candidate_id"]
    assert top["programs"][0]["effort"] == result.min_effort["minimum_effort_value"] == 2
    assert action_signature(result, top["programs"][0]) == oracle["best_program"]
    for program in top["programs"]:
        assert program["effort"] == oracle["program_efforts"][action_signature(result, program)]
        assert len(program["work_unit_ids"]) == len(set(program["work_unit_ids"]))
        assert (
            sum(u["computed_cost"] for u in program["work_unit_ledger"].values())
            == program["effort"]
        )
    if k == 2:
        assert top["boundary_ties"] == {
            "effort": 5,
            "observed_count": 2,
            "omitted_count": 1,
            "complete": True,
        }
    if k >= 3:
        assert {action_signature(result, p) for p in top["programs"]} == set(
            oracle["program_efforts"]
        )
    Draft202012Validator(read("docs/research/effort-top-k.schema.json")).validate(top)


@pytest.mark.parametrize("k", [0, -1, True, False, 1.5, "2", [], {}, None])
def test_invalid_k_rejected_before_search(case, k):
    query, graph = case
    query["top_k"] = k
    with pytest.raises(ValueError, match="positive integer"):
        materialize_query(query, graph)


def test_typed_and_materialized_api_and_k_independent_of_budget(case):
    query, graph = case
    query["top_k"] = 1
    mapping = run_attack_query(query, graph)
    typed = run_attack_query(AttackQuery(**query), graph)
    materialized = materialize_query(query, graph)
    assert materialized.budget.max_paths == 1000
    assert materialized.run(graph).top_k_result == typed.top_k_result == mapping.top_k_result
    assert len(mapping.paths) == 3  # K=1 did not stop at the first (C=5) candidate.


def test_c_rated_p_i_unrated_remains_exact_top_k(case):
    query, graph = case
    query["ranking_query"]["conditional_bounds_table"] = []
    for impact in query["ranking_query"]["target_impact_assessments"].values():
        impact.update(
            rating_status="unrated",
            consequence_rating=None,
            missing_basis_reasons=["Synthetic missing impact"],
        )
    result = run_attack_query(query, graph)
    assert result.ranking_result["pareto_frontier"] == []
    assert result.top_k_result["guarantee"]["is_k_best_proven"]
    assert [p["effort"] for p in result.top_k_result["programs"]] == [2, 5, 5]
    assert all(
        p["likelihood_interval"] is None and p["impact"] is None
        for p in result.top_k_result["programs"]
    )


def test_fully_overlapping_probability_bounds_do_not_block_effort_recommendation(case):
    query, graph = case
    for bound in query["ranking_query"]["conditional_bounds_table"]:
        bound.update(lower="0", upper="1")
    result = run_attack_query(query, graph)
    assert len(result.ranking_result["pareto_frontier"]) == 3
    assert [p["effort"] for p in result.top_k_result["programs"]] == [2, 5, 5]
    assert all(p["likelihood_interval"] == ["0", "1"] for p in result.top_k_result["programs"])
    assert (
        result.top_k_result["programs"][0]["candidate_id"] == result.min_effort["best_candidate_id"]
    )


def test_missing_c_keeps_incumbents_but_downgrades_proof(case):
    query, graph = case
    unit = query["ranking_query"]["work_units_ledger"]["w-inherited-admin"]
    unit.update(
        rating_status="unrated",
        computed_cost=None,
        effort_cost=None,
        rubric_scores=None,
        missing_basis_reasons=["Synthetic missing C"],
    )
    result = run_attack_query(query, graph)
    top = result.top_k_result
    assert [p["effort"] for p in top["programs"]] == [5, 5]
    assert "effort_rating_gap" in top["guarantee"]["reasons"]
    assert not top["guarantee"]["fewer_than_k_proven"]
    assert top["coverage"]["exclusions"][0]["unrated_work_units"] == ["w-inherited-admin"]


@pytest.mark.parametrize("mode", ["binding", "adapter", "semantic_only"])
def test_excluded_candidates_never_prove_whole_scope(case, mode):
    query, graph = case
    if mode == "binding":
        query["action_bindings"] = []
    elif mode == "adapter":
        query["ranking_query"]["target_impact_assessments"] = {}
    else:
        query.pop("ranking_query")
    result = run_attack_query(query, graph)
    assert len(result.paths) == 3
    assert result.top_k_result["returned_count"] == 0
    assert "binding_or_assessment_gap" in result.top_k_result["guarantee"]["reasons"]
    assert not result.top_k_result["guarantee"]["no_path_proven"]


@pytest.mark.parametrize("cap,value", [("max_paths", 1), ("max_steps", 1), ("max_expansions", 1)])
def test_caps_keep_incumbents_without_k_best_or_no_path_claim(case, cap, value):
    query, graph = case
    query["top_k"] = 1
    query["budget"][cap] = value
    top = run_attack_query(query, graph).top_k_result
    assert top["coverage"]["truncated"]
    assert not top["guarantee"]["is_k_best_proven"]
    assert not top["guarantee"]["no_path_proven"]
    assert not top["boundary_ties"]["complete"]
    assert "search_incomplete" in top["guarantee"]["reasons"]


def test_unknown_alternative_downgrades_even_with_successful_incumbent(case):
    query, graph = case
    query["runtime_facts"] = [
        f for f in query["runtime_facts"] if f["predicate"] != "membership_usable"
    ]
    result = run_attack_query(query, graph)
    assert result.final_goal_reached
    assert result.top_k_result["returned_count"] == 1
    assert "indeterminate_transitions" in result.top_k_result["guarantee"]["reasons"]
    assert not result.is_minimum_proven_over_scope


@pytest.mark.parametrize("known_false", [False, True])
def test_blocked_and_unknown_not_successful_programs(case, known_false):
    query, graph = case
    query["checkpoint_goal"] = {
        "target": "Admins",
        "required_state": {"effective_member": [["Alice", "Admins"]]},
    }
    query["runtime_facts"] = [
        f for f in query["runtime_facts"] if f["predicate"] != "admin_channel"
    ]
    if known_false:
        query["runtime_facts"].append(
            {
                "predicate": "admin_channel",
                "subject": "Alice",
                "target": "Host",
                "value": False,
                "origin": "observed_evidence",
                "evidence_ref": "synthetic://known-false",
            }
        )
    result = run_attack_query(query, graph)
    assert result.checkpoint_reached and not result.final_goal_reached
    assert result.top_k_result["returned_count"] == 0
    assert result.top_k_result["guarantee"]["no_path_proven"] == known_false
    assert result.top_k_result["guarantee"]["is_k_best_proven"] == known_false


def test_initial_goal_is_single_zero_work_without_post_goal_tails(case):
    query, graph = case
    query["initial_state"]["admin_control"] = ["Host"]
    result = run_attack_query(query, graph)
    top = result.top_k_result
    assert result.expansions == 0 and len(result.paths) == 1
    assert top["returned_count"] == 1 and top["guarantee"]["fewer_than_k_proven"]
    assert top["programs"][0]["effort"] == result.min_effort["minimum_effort_value"] == 0
    assert top["programs"][0]["work_unit_ledger"] == {}
    assert top["programs"][0]["likelihood_interval"] is None
    assert top["programs"][0]["impact"] is None
    assert result.ranking_result["pareto_frontier"] == []


def test_zero_work_identity_retains_canonical_source_under_same_state(case):
    query, graph = case
    query.pop("ranking_query")
    query["initial_state"] = {"control": ["Alice", "Bob"], "admin_control": ["Host"]}
    results = []
    for actor in ("Alice", "Bob", query["aliases"]["Alice"]):
        query["initial_actor"] = actor
        results.append(run_attack_query(query, graph))
    alice, bob, alias = results
    assert alice.paths[0].final_state == bob.paths[0].final_state
    assert alice.paths[0].runtime_context == bob.paths[0].runtime_context
    for result in results:
        path = result.paths[0]
        assert path.nodes == (query["aliases"]["Host"],)
        assert path.transition_history == () and result.expansions == 0
        assert path.initial_actor == result.materialized_query.initial_actor
        assert result.best_path.initial_actor == path.initial_actor
        assert result.top_k_result["programs"][0]["effort"] == 0
    programs = [result.top_k_result["programs"][0] for result in results]
    assert programs[0]["program_id"] != programs[1]["program_id"]
    assert programs[0]["program_key"] != programs[1]["program_key"]
    assert programs[0]["program_id"] == programs[2]["program_id"]
    assert programs[0]["program_key"] == programs[2]["program_key"]


def test_same_actor_state_and_work_program_does_not_collapse_top_two(case):
    query, graph = case
    # A passive prefix may have no additional active work, yet is a distinct program.
    query["initial_state"]["effective_member"] = [["Alice", "Admins"]]
    # Declare the same initial entitlement to the explicit replay packet. Its
    # original Ledger E scenario acquires membership through the passive action.
    query["ranking_query"]["facts_ledger"]["observed_facts"].append(
        {
            "predicate": "effective_member_alice_admins",
            "layer": 3,
            "truth_value": True,
            "provenance_reference": "synthetic://initial-entitlement",
        }
    )
    result = run_attack_query(query, graph)
    top = result.top_k_result
    assert len(result.paths) == 4
    assert [p["effort"] for p in top["programs"]] == [2, 2, 5]
    assert top["programs"][0]["work_unit_ids"] == top["programs"][1]["work_unit_ids"]
    assert top["programs"][0]["program_key"] != top["programs"][1]["program_key"]


def test_identity_keeps_context_edge_parent_and_capability_history(case):
    query, graph = case
    path = run_attack_query(query, graph).paths[-1]
    key = program_key(path)
    last = path.transition_history[-1]
    for changed in [
        replace(last, edge_id="synthetic-distinct-evidence"),
        replace(last, derived_from_step=0),
        replace(last, result=replace(last.result, before=AttackState())),
        replace(
            last,
            result=replace(
                last.result, request=replace(last.result.request, actor="synthetic-other-actor")
            ),
        ),
    ]:
        assert (
            program_key(replace(path, transition_history=(*path.transition_history[:-1], changed)))
            != key
        )
    assert (
        program_key(replace(path, runtime_context=RuntimeContext(authentication_context="other")))
        != key
    )
    assert program_key(replace(path, cost=999)) == key
    assert program_key(replace(path, initial_actor="synthetic-other-source")) != key


def test_supported_parallel_relationships_keep_exact_edges_and_first_goal(case):
    query, graph = case
    query.pop("ranking_query")
    query.pop("action_bindings")
    query.pop("target_goal")
    actor, host = query["aliases"]["Alice"], query["aliases"]["Host"]
    edge = copy.deepcopy(graph["edges"][0])
    edge.update(kind="CanPSRemote", id=canonical_edge_id(actor, host, "CanPSRemote"))
    graph["edges"].append(edge)
    query["allowed_techniques"] = ["obtain_admin_execution_on_host", "open_winrm_remote_session"]
    query["runtime_facts"].append(
        {
            "predicate": "winrm_available",
            "subject": "Alice",
            "target": "Host",
            "value": True,
            "origin": "declared_assumption",
            "scope": "two-routes:fixed-snapshot-window",
            "rationale": "Synthetic alternative channel",
            "evidence_ref": "synthetic://winrm",
        }
    )
    query["success_state_predicate"] = lambda state: (
        host in state.admin_control or (actor, host) in state.remote_command_execution
    )
    before = copy.deepcopy(graph)
    result = run_attack_query(query, graph)
    assert len(result.paths) == 2
    assert {path.edges[0]["kind"] for path in result.paths} == {"AdminTo", "CanPSRemote"}
    assert len({program_key(path) for path in result.paths}) == 2
    assert all(len(path.transition_history) == 1 for path in result.paths)
    assert graph == before


def test_duplicate_enumeration_dedup_and_ties_do_not_depend_on_candidate_ids(case):
    query, graph = case
    original = run_attack_query(query, graph)
    paths = original.paths
    assessments = collect_assessments(original)
    reordered = replace(
        original, search_result=replace(original.search_result, paths=paths[::-1] + (paths[0],))
    )
    reordered_ranking = copy.deepcopy(original.ranking_result)
    reordered_ranking["diagnostics"] = {}
    reordered_ranking["eligible_candidates"] = {
        f"generated_{i:04d}": {
            **copy.deepcopy(assessments[f"generated_{j:04d}"]),
            "candidate_id": f"generated_{i:04d}",
        }
        for i, j in enumerate([3, 2, 1, 1], 1)
    }
    reordered = replace(reordered, ranking_result=reordered_ranking)
    top = select_top_k(reordered, 3)
    assert top["coverage"]["duplicate_count"] == 1
    assert [p["program_key"] for p in top["programs"]] == [
        p["program_key"] for p in original.top_k_result["programs"]
    ]


def test_aliases_and_repeated_runs_preserve_semantic_order(case):
    query, graph = case
    first = run_attack_query(query, graph)
    query["initial_actor"] = query["aliases"]["Alice"]
    query["target"] = query["aliases"]["Host"]
    second = run_attack_query(query, graph)
    assert first.top_k_result == second.top_k_result


def validate_transport(package):
    schema = read("docs/research/week4-query-result-0.4.schema.json")
    registry = Registry().with_resources(
        [
            (name, Resource.from_contents(read("docs/research/" + name)))
            for name in ["effort-top-k.schema.json", "public-rating-coverage.schema.json"]
        ]
    )
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema, registry=registry).validate(package)


@pytest.mark.parametrize("automatic", [False, True])
def test_cli_transport_reproduction_and_automatic_ratings(tmp_path, automatic):
    args = [
        sys.executable,
        "-m",
        "src.engine.query_cli",
        "--query",
        "tests/fixtures/rating_resolution/query.json"
        if automatic
        else "tests/fixtures/query_cli/two-routes-query.json",
        "--graph",
        "tests/fixtures/attack_scenarios/graphs/two-routes.json",
        "--label",
        "synthetic",
        "--top-k",
        "2",
    ]
    args += (
        ["--rating-resolution", "tests/fixtures/rating_resolution/complete.json"]
        if automatic
        else ["--ranking-query", "docs/research/ratings/week4/synthetic-a2-e.json"]
    )
    files = [tmp_path / "first.json", tmp_path / "second.json"]
    packages = []
    for path in files:
        subprocess.run(
            [*args, "--output", str(path)], cwd=ROOT, check=True, capture_output=True, text=True
        )
        package = json.loads(path.read_text())
        validate_transport(package)
        assert package["semantic"]["top_k"]["returned_count"] == 2
        assert package["reproducibility"]["semantic_sha256"] == digest(
            canonical_json(package["semantic"]).encode()
        )
        packages.append(package)
    base_path = tmp_path / "base.json"
    top_k_index = args.index("--top-k")
    base_args = args[:top_k_index] + args[top_k_index + 2 :]
    subprocess.run(
        [*base_args, "--output", str(base_path)],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    base_acceptance = json.loads(base_path.read_text())["acceptance"]
    acceptance = packages[0]["acceptance"]
    assert (
        acceptance["resolved_dependencies"].items()
        >= base_acceptance["resolved_dependencies"].items()
    )
    assert acceptance["pending_acceptance"] == [
        *base_acceptance["pending_acceptance"],
        "#226 exact-head human review and independent reproduction",
    ]
    assert packages[0]["semantic"] == packages[1]["semantic"]
    subprocess.run(
        [sys.executable, "-m", "scripts.research.compare_query_runs", *map(str, files)],
        cwd=ROOT,
        check=True,
        capture_output=True,
    )


def test_cli_invalid_k_writes_no_package(tmp_path):
    output = tmp_path / "invalid.json"
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "src.engine.query_cli",
            "--query",
            "tests/fixtures/query_cli/two-routes-query.json",
            "--graph",
            "tests/fixtures/attack_scenarios/graphs/two-routes.json",
            "--label",
            "synthetic",
            "--top-k",
            "0",
            "--output",
            str(output),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 1 and "positive integer" in completed.stderr
    assert not output.exists()
