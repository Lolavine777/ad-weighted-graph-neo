"""Reject unsupported numerical recovery and cross-event historical transfers."""

import copy
from fractions import Fraction

import pytest

from scripts.research.asrep_expert_basis import PACKAGE, ROOT, build_inputs, read, validate_proposal
from src.engine import run_attack_query

CURRENT = ROOT / "docs/research/ratings/asrep-expert-v2"


def test_current_recovery_is_unrated_without_population_and_completed_compute():
    proposal = read(CURRENT / "proposal.json")
    validate_proposal(proposal)
    recovery = proposal["events"][1]
    assert recovery["lower"] is recovery["upper"] is None
    assert recovery["numeric_disposition"] == "UNRATED_NO_BASIS"
    assert proposal["target_population"]["compute_floor"] is None
    assert proposal["events"][0]["numeric_source"] != "historical_activation_transfer"
    assert proposal["human_numeric_elicitation_completed"] is False


def test_recovery_cannot_be_reactivated_by_status_or_uniform_arithmetic():
    proposal = read(CURRENT / "proposal.json")
    proposal["events"][1].update(lower="1/32", upper="1/16")
    with pytest.raises(ValueError, match="recovery"):
        validate_proposal(proposal)


def test_full_history_audit_and_legacy_oracle_are_preserved():
    historical = read(PACKAGE / "proposal.json")
    assert historical["events"][1]["lower"] == "1/32"
    assert Fraction(524288, 72000) == Fraction(8192, 1125)
    changed = copy.deepcopy(read(CURRENT / "proposal.json"))
    changed["events"][2]["history"] = []
    with pytest.raises(ValueError, match="history"):
        validate_proposal(changed)


def test_current_native_consumer_omits_missing_recovery():
    raw = ROOT / "data/raw/SEAMLESS"
    if not raw.is_dir():
        pytest.skip("Authorized manifest-verified SEAMLESS raw required")
    graph, query, _ = build_inputs(raw, "da21fbb545061c56c6dfff6ac489e7794a53ec73", package=CURRENT)
    records = query["rating_resolution"]["registries"]["likelihood"]["data"]
    assert len(records) == 3
    assert all(r["outcome_technique"] != "recover_asrep_secret" for r in records)
    result = run_attack_query(query, graph)
    assert len(result.search_result.paths) == 1
    assert result.rating_coverage["numeric_requests"]["P"] == {"required": 4, "rated": 0}
    assert not result.ranking_result["pareto_frontier"]


def test_public_api_semantic_mismatch_is_refused():
    from types import SimpleNamespace

    from scripts.research.asrep_expert_basis import compare_api_cli

    values = dict(
        status="no_path",
        checkpoint_reached=False,
        final_goal_reached=False,
        caps={},
        complete=True,
        truncated=False,
        truncation_reason=None,
        expansions=0,
        ranking_result={},
        rating_coverage={},
        min_effort=None,
        optimization_scope=None,
        is_minimum_proven_over_scope=False,
        is_no_path_proven_over_scope=False,
    )
    api = SimpleNamespace(**values, paths=())
    cli = {
        k: v
        for k, v in values.items()
        if k
        not in (
            "optimization_scope",
            "is_minimum_proven_over_scope",
            "is_no_path_proven_over_scope",
        )
    }
    cli["candidates"] = []
    cli["status"] = "success"
    cli["engine_reported_guarantees"] = {
        k: values[k]
        for k in (
            "optimization_scope",
            "is_minimum_proven_over_scope",
            "is_no_path_proven_over_scope",
        )
    }
    with pytest.raises(ValueError, match="API/CLI"):
        compare_api_cli(api, cli)


@pytest.fixture(scope="module")
def public_program_results():
    import json
    import subprocess
    import sys

    from src.engine import materialize_query
    from src.engine.graph import EngineGraph
    from src.engine.ranking.orchestration import generate_and_evaluate_attack_paths

    query_path = ROOT / "tests/fixtures/rating_resolution/query.json"
    config_path = ROOT / "tests/fixtures/rating_resolution/complete.json"
    graph_path = ROOT / "tests/fixtures/attack_scenarios/graphs/two-routes.json"
    process = subprocess.run(
        [
            sys.executable,
            "-m",
            "src.engine.query_cli",
            "--query",
            str(query_path),
            "--rating-resolution",
            str(config_path),
            "--graph",
            str(graph_path),
            "--label",
            "synthetic",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )
    assert not process.stderr
    semantic = json.loads(process.stdout)["semantic"]
    query = {**read(query_path), "rating_resolution": read(config_path)}
    graph = EngineGraph.from_canonical(read(graph_path))
    materialized = materialize_query(query, graph)
    orchestration = generate_and_evaluate_attack_paths(
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
    )
    return run_attack_query(query, graph), semantic, orchestration


@pytest.mark.parametrize(
    "location,replacement",
    [
        (("transition_history", 0, "result", "request", "actor"), "different-participant"),
        (("transition_history", 0, "result", "request", "source"), "different-source"),
        (("transition_history", 0, "result", "request", "target"), "different-target"),
        (("transition_history", 0, "edge_id"), "sha256:" + "0" * 64),
        (("transition_history", 0, "derived_from_step"), 0),
        (("edges", 0, "provenance", 0, "raw_file"), "synthetic://different-evidence"),
        (("transition_history", 0, "result", "snapshot_evidence"), ["different-evidence"]),
        (("final_state", "admin_control"), []),
        (("runtime_context", "authentication_context"), "different-context"),
    ],
)
def test_same_techniques_do_not_establish_program_equality(
    public_program_results, location, replacement
):
    from scripts.research.asrep_expert_basis import compare_api_cli, compare_programs

    api, semantic, orchestration = public_program_results
    compare_api_cli(api, semantic)
    changed = copy.deepcopy(semantic)
    field = changed["candidates"][0]
    for key in location[:-1]:
        field = field[key]
    assert field[location[-1]] != replacement
    field[location[-1]] = replacement
    assert {k: v for k, v in changed.items() if k != "candidates"} == {
        k: v for k, v in semantic.items() if k != "candidates"
    }
    assert [
        [step["result"]["request"]["technique_id"] for step in path["transition_history"]]
        for path in changed["candidates"]
    ] == [
        [step.result.request.technique_id for step in path.transition_history] for path in api.paths
    ]
    with pytest.raises(ValueError, match="program"):
        compare_api_cli(api, changed)
    with pytest.raises(ValueError, match="orchestration/CLI.*program"):
        compare_programs(
            orchestration["search_result"].paths,
            changed["candidates"],
            interface="orchestration/CLI",
        )


def test_public_program_identity_ignores_only_candidate_transport_id(public_program_results):
    from scripts.research.asrep_expert_basis import compare_api_cli, compare_programs

    api, semantic, orchestration = public_program_results
    changed = copy.deepcopy(semantic)
    for path in changed["candidates"]:
        path["candidate_id"] = "transport-only-name"
    compare_api_cli(api, changed)
    compare_programs(
        orchestration["search_result"].paths, changed["candidates"], interface="orchestration/CLI"
    )


@pytest.mark.parametrize("change", ["candidate_order", "transition_order", "missing_evidence"])
def test_public_program_identity_preserves_order_and_requires_evidence(
    public_program_results, change
):
    from scripts.research.asrep_expert_basis import compare_api_cli, compare_programs

    api, semantic, orchestration = public_program_results
    changed = copy.deepcopy(semantic)
    if change == "candidate_order":
        changed["candidates"].reverse()
    elif change == "transition_order":
        path = next(p for p in changed["candidates"] if len(p["transition_history"]) > 1)
        path["transition_history"].reverse()
    else:
        changed["candidates"][0].pop("edges")
    with pytest.raises(ValueError, match="API/CLI.*program"):
        compare_api_cli(api, changed)
    with pytest.raises(ValueError, match="orchestration/CLI.*program"):
        compare_programs(
            orchestration["search_result"].paths,
            changed["candidates"],
            interface="orchestration/CLI",
        )


def test_distinct_generated_branches_with_same_techniques_are_refused(public_program_results):
    from scripts.research.asrep_expert_basis import compare_api_cli, compare_programs

    api, semantic, orchestration = public_program_results
    first, second = semantic["candidates"][1:]
    assert [s["result"]["request"]["technique_id"] for s in first["transition_history"]] == [
        s["result"]["request"]["technique_id"] for s in second["transition_history"]
    ]
    assert (
        first["transition_history"][-1]["result"]["request"]["source"]
        != (second["transition_history"][-1]["result"]["request"]["source"])
    )
    assert first["edges"] != second["edges"]
    changed = copy.deepcopy(semantic)
    changed["candidates"][1] = copy.deepcopy(second)
    changed["candidates"][1]["candidate_id"] = first["candidate_id"]
    with pytest.raises(ValueError, match="API/CLI.*program"):
        compare_api_cli(api, changed)
    with pytest.raises(ValueError, match="orchestration/CLI.*program"):
        compare_programs(
            orchestration["search_result"].paths,
            changed["candidates"],
            interface="orchestration/CLI",
        )
