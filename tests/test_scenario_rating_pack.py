"""Public automatic integration of pending Owner A records, never numeric approval."""

import copy
import json
import subprocess
import sys
from fractions import Fraction

import pytest
from jsonschema import Draft202012Validator

from scripts.research.scenario_rating_pack import (
    PACKAGE,
    ROOT,
    build_source_a_query,
    build_two_routes_query,
    load_coverage_matrix,
    load_oracles,
    load_scenario_pack,
    run_scenario_probe,
    verify_package,
)
from src.engine import materialize_query, run_attack_query
from src.engine.ranking.orchestration import generate_and_evaluate_attack_paths
from src.engine.ranking.resolution_service import canonical_digest


def repin(query, role):
    envelope = query["rating_resolution"]["registries"][role]
    envelope["sha256"] = canonical_digest(envelope["data"])


def test_manifest_and_pending_numeric_governance():
    assert verify_package()["verified"]
    pack = load_scenario_pack()
    assert pack["status"] == "proposed_pending_b_review"
    assert not pack["governance"]["numeric_activation_permitted"]
    query, _ = build_two_routes_query()
    regs = query["rating_resolution"]["registries"]
    for record in regs["effort"]["data"] + regs["likelihood"]["data"]:
        assert record["review_status"] in ("pending_b_review", "proposed_pending_b_review")
        assert record["basis_category"] == "synthetic_test_only"
    assert regs["impact"]["data"]["mappings"][0]["status"] == "proposed_pending_b_review"


def test_public_automatic_review_simulation_matches_frozen_oracle():
    report = run_scenario_probe()
    assert report["status"] == "PASS"
    assert report["numeric_approval"] is False
    assert report["paths_generated"] == 3
    assert report["numeric_requests"] == {
        "C": {"required": 3, "rated": 3},
        "P": {"required": 3, "rated": 3},
        "I": {"required": 1, "rated": 1},
    }
    assert report["pareto_frontier"] == ["generated_0001", "generated_0002", "generated_0003"]


@pytest.mark.parametrize("simulate", [False, True])
@pytest.mark.parametrize("case", ["equal-synthetic", "source-a"])
def test_api_subprocess_cli_and_orchestration_agree(tmp_path, simulate, case):
    builder = build_source_a_query if case == "source-a" else build_two_routes_query
    query, graph = builder(simulate_review=simulate)
    graph_path = (
        ROOT / PACKAGE / "source-a-graph.json"
        if case == "source-a"
        else ROOT / load_scenario_pack()["scenario_profile"]["graph_fixture"]
    )
    api = run_attack_query(query, graph)
    materialized = materialize_query(query, graph)
    other = generate_and_evaluate_attack_paths(
        {},
        graph,
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
    from src.engine.query_cli import wire

    assert other == wire(api.ranking_result)
    query_file = tmp_path / "query.json"
    query_file.write_text(json.dumps(query), encoding="utf-8")
    results = []
    for _ in range(2):
        process = subprocess.run(
            [
                sys.executable,
                "-m",
                "src.engine.query_cli",
                "--query",
                str(query_file),
                "--graph",
                str(graph_path),
                "--label",
                "seamless" if case == "source-a" else "synthetic",
                "--prerequisite",
                str(ROOT / "data/samples/manifests/seamless-raw-v1.json"),
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        result = json.loads(process.stdout)
        assert result["semantic"]["ranking_result"] == wire(api.ranking_result)
        assert result["semantic"]["rating_coverage"] == api.rating_coverage
        schema = json.loads((ROOT / "docs/research/public-rating-coverage.schema.json").read_text())
        Draft202012Validator(schema).validate(result["semantic"]["rating_coverage"])
        result.pop("runtime")
        results.append(result)
    assert results[0] == results[1]


def test_pending_pack_refused_by_real_automatic_providers():
    query, graph = build_two_routes_query()
    result = run_attack_query(query, graph)
    assert len(result.search_result.paths) == 3
    assert result.rating_coverage["numeric_requests"] == {
        "C": {"required": 3, "rated": 0},
        "P": {"required": 3, "rated": 0},
        "I": {"required": 1, "rated": 0},
    }
    assert not result.ranking_result["pareto_frontier"]


def test_production_refuses_synthetic_work_rule():
    query, graph = build_two_routes_query(simulate_review=True)
    query["rating_resolution"]["policy"] = "production"
    with pytest.raises(ValueError, match="Production policy refuses synthetic work binding rule"):
        run_attack_query(query, graph)


def test_production_refuses_numeric_fixtures_without_work_rule():
    query, graph = build_two_routes_query(simulate_review=True)
    query["rating_resolution"]["policy"] = "production"
    query["rating_resolution"]["registries"].pop("work")
    result = run_attack_query(query, graph)
    assert all(v["rated"] == 0 for v in result.rating_coverage["numeric_requests"].values())
    assert not result.ranking_result["pareto_frontier"]


def test_exact_effort_applicability_no_private_predicates():
    query, graph = build_two_routes_query(simulate_review=True)
    classes = query["rating_resolution"]["registries"]["effort"]["data"]
    direct, inherited = classes[1:]
    assert set(direct["applicability"]["source_ids"]).isdisjoint(
        inherited["applicability"]["source_ids"]
    )
    for record in classes:
        assert record["applicability"]["methods"] == ["AdminTo"]
        assert record["applicability"]["scopes"] == ["w4-two-routes-exact"]
        assert "predicate" not in record["applicability"]
        assert "semantic_predicate" not in record["applicability"]
    assert all(
        v["rated"] == v["required"]
        for v in run_attack_query(query, graph).rating_coverage["numeric_requests"].values()
    )


def test_shared_preparation_and_passive_closure_from_public_work_rule():
    query, graph = build_two_routes_query(simulate_review=True)
    assert "shared_preparation_units" not in json.dumps(query)
    result = run_attack_query(query, graph)
    coverage = result.rating_coverage
    assert coverage["numeric_requests"]["C"]["required"] == 3
    for candidate in result.ranking_result["eligible_candidates"].values():
        assert candidate["effort"] == 2
        assert tuple(map(Fraction, candidate["likelihood_interval"])) == (
            Fraction(2, 5),
            Fraction(27, 40),
        )
    assert len(coverage["candidates"]) == 3
    for candidate in coverage["candidates"].values():
        assert candidate["effort"]["total_units"] == 2
        assert candidate["likelihood"]["total_prefixes"] == 2


@pytest.mark.parametrize("dimension", ["effort", "likelihood", "impact"])
def test_missing_registry_never_silently_rates(dimension):
    query, graph = build_two_routes_query(simulate_review=True)
    query["rating_resolution"]["registries"].pop(dimension)
    result = run_attack_query(query, graph)
    if dimension != "effort":
        assert not result.ranking_result["pareto_frontier"]
    else:
        assert result.ranking_result["min_effort_to_da_baseline"]["minimum_effort_value"] is None
    assert (
        result.rating_coverage["numeric_requests"][
            {"effort": "C", "likelihood": "P", "impact": "I"}[dimension]
        ]["rated"]
        == 0
    )


@pytest.mark.parametrize(
    "mutation", ["prefix_order", "method", "horizon", "boundary", "source", "snapshot", "retry"]
)
def test_likelihood_exact_context_refused(mutation):
    query, graph = build_two_routes_query(simulate_review=True)
    regs = query["rating_resolution"]["registries"]
    records = regs["likelihood"]["data"]
    for rec in records:
        if mutation == "prefix_order":
            rec["ordered_work_prefix"].reverse()
        else:
            field = {"source": "source_id", "snapshot": "snapshot_id", "retry": "retry_policy"}.get(
                mutation, mutation
            )
            rec[field] = {"max_attempts": 99} if field == "retry_policy" else "wrong"
    repin(query, "likelihood")
    result = run_attack_query(query, graph)
    assert not result.ranking_result["pareto_frontier"]
    assert result.rating_coverage["numeric_requests"]["P"]["rated"] < 3


@pytest.mark.parametrize("mutation", ["goal_id", "typed_goal", "snapshot", "scenario"])
def test_impact_exact_typed_goal_refused(mutation):
    query, graph = build_two_routes_query(simulate_review=True)
    app = query["rating_resolution"]["registries"]["impact"]["data"]["mappings"][0]["applicability"]
    if mutation == "typed_goal":
        app["semantic_goal"]["required_state"] = {
            "remote_command_execution": [[query["initial_actor"], query["target"]]]
        }
    else:
        app[{"snapshot": "snapshot_id", "scenario": "scenario_id"}.get(mutation, mutation)] = (
            "wrong"
        )
    repin(query, "impact")
    result = run_attack_query(query, graph)
    assert result.rating_coverage["numeric_requests"]["I"]["rated"] == 0
    assert not result.ranking_result["pareto_frontier"]


def test_missing_scenario_authority_does_not_wildcard():
    query, graph = build_two_routes_query(simulate_review=True)
    query.pop("scenario_reference")
    result = run_attack_query(query, graph)
    assert all(v["rated"] == 0 for v in result.rating_coverage["numeric_requests"].values())


def test_authoritative_false_veto():
    query, graph = build_two_routes_query(simulate_review=True)
    query["runtime_facts"][0].update(value=False, origin="observed_evidence")
    result = run_attack_query(query, graph)
    assert len(result.search_result.paths) == 0


def test_conflicting_effort_basis_remains_conflicting():
    query, graph = build_two_routes_query(simulate_review=True)
    records = query["rating_resolution"]["registries"]["effort"]["data"]
    clone = copy.deepcopy(records[1])
    clone["class_id"] = "conflicting-direct"
    clone.update(t1=3, t2=3, computed_cost=4)
    records.append(clone)
    repin(query, "effort")
    result = run_attack_query(query, graph)
    assert result.rating_coverage["numeric_requests"]["C"]["rated"] < 3


def test_exact_products_and_historical_oracles():
    oracles = load_oracles()
    for program in oracles["generated_risk_comparison"]["expected_programs"]:
        lo, hi = Fraction(1), Fraction(1)
        for bounds in program["q_intervals"]:
            lo *= Fraction(bounds[0])
            hi *= Fraction(bounds[1])
        assert [str(lo), str(hi)] == program["exact_path_interval"]
    assert oracles["frozen_243"]["current_P"] is None
    assert oracles["incomparable_alternative_case"]["expected_dominated"] == []


def test_coverage_inventory_and_scope():
    from src.engine.semantics import load_catalog

    coverage = load_coverage_matrix()
    assert {t.id for t in load_catalog()} == {
        t["technique_id"] for t in coverage["techniques_matrix"]
    }
    assert coverage["summary"]["unrated_techniques_count"] == 21
    assert (
        coverage["denominators"]["synthetic_review_simulation"]["fully_rated_paths"]["count"] == 3
    )
    assert coverage["denominators"]["pending_pack"]["fully_rated_paths"]["count"] == 0


def test_manifest_tamper_detection(tmp_path):
    import shutil

    shutil.copytree(ROOT / PACKAGE, tmp_path / PACKAGE)
    (tmp_path / PACKAGE / "scenario-rating-pack.json").write_text("{}")
    with pytest.raises(ValueError, match="file digest mismatch"):
        verify_package(tmp_path)


def test_source_manifest_cannot_omit_authoritative_pin(tmp_path):
    import shutil

    shutil.copytree(ROOT / PACKAGE, tmp_path / PACKAGE)
    manifest_path = tmp_path / PACKAGE / "source-manifest-v2.json"
    manifest = json.loads(manifest_path.read_text())
    for name in manifest["source_pins"]:
        target = tmp_path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, target)
    manifest["source_pins"].pop("src/engine/ranking/resolution_service.py")
    manifest_path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="source pin coverage mismatch"):
        verify_package(tmp_path)


def test_unknown_runtime_prerequisite_cannot_be_numerically_overridden():
    query, graph = build_two_routes_query(simulate_review=True)
    query["runtime_facts"] = [
        f for f in query["runtime_facts"] if f["predicate"] != "admin_channel"
    ]
    result = run_attack_query(query, graph)
    assert len(result.search_result.paths) == 0
    assert all(
        request["required"] == 0 for request in result.rating_coverage["numeric_requests"].values()
    )


def test_simulation_changes_only_native_review_gates():
    query, _ = build_two_routes_query()
    simulation, _ = build_two_routes_query(simulate_review=True)
    for role in ("effort", "likelihood"):
        for record in simulation["rating_resolution"]["registries"][role]["data"]:
            record["review_status"] = (
                "pending_b_review" if role == "effort" else "proposed_pending_b_review"
            )
            record["disposition"] = "rated" if role == "effort" else "unrated"
        repin(simulation, role)
    simulation["rating_resolution"]["registries"]["impact"]["data"]["mappings"][0]["status"] = (
        "proposed_pending_b_review"
    )
    repin(simulation, "impact")
    assert simulation == query


def test_export_cannot_overwrite_pending_package(tmp_path):
    export = tmp_path / "query.json"
    export.write_text("existing pending artifact")
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "scripts.research.scenario_rating_pack",
            "--simulate-review",
            "--export-query",
            str(export),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert export.read_text() == "existing pending artifact"
