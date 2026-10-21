"""Numeric adoption is test-simulated; no fixture is a real B decision."""

import copy
import json
from fractions import Fraction
from types import SimpleNamespace

import pytest

from scripts.research.final_cpi_profiles import bind_source_a
from scripts.research.final_cpi_release import apply_release, template, validate_release
from src.engine import run_attack_query
from src.engine.graph import EngineGraph
from src.engine.query_cli import wire
from tests.test_final_cpi_profiles import _source_a_first_goal_programs, _source_a_traces


def simulated_release():
    release = template()
    release["status"] = "adopted"
    release["review"].update(
        reviewer="test-only simulated B",
        reviewed_at="2000-01-01T00:00:00Z",
        reference="test://final-cpi-release/simulated-numeric-adoption",
        confirmation="TEST ONLY: adopt the declared values and exact context/history equivalence",
    )
    for entry in release["classes"].values():
        for dimension in ("C", "P"):
            entry[dimension]["decision"] = "adopt"
    release["impact"]["decision"] = "adopt"
    return release


@pytest.fixture(scope="module")
def native_case():
    query, canonical = bind_source_a("source-a-projection")
    graph = EngineGraph.from_canonical(canonical)
    release = simulated_release()
    adopted = apply_release(query, release)
    result = run_attack_query(adopted, graph)
    return query, graph, release, adopted, result


def test_pending_release_never_activates_numeric_authority():
    query, _ = bind_source_a("source-a-projection")
    before = copy.deepcopy(query)
    with pytest.raises(ValueError, match="pending B"):
        apply_release(query, template())
    assert query == before


@pytest.mark.parametrize(
    "numeric_class,basis",
    [
        ("empirical", "scenario_assumption"),
        ("estimated_expert_scenario", "empirical_evidence"),
        ("synthetic_test_only", "scenario_assumption"),
    ],
)
def test_public_numeric_metadata_cannot_promote_estimates_or_synthetic(numeric_class, basis):
    from src.engine.ranking.models import RankingValidationError
    from src.engine.ranking.resolver import ResolutionResult, ResolverDisposition

    with pytest.raises(RankingValidationError, match="incompatible"):
        ResolutionResult(
            disposition=ResolverDisposition.RATED,
            basis_category=basis,
            numeric_basis_class=numeric_class,
        )


def test_native_production_policy_consumes_only_simulated_reviewed_dimensions(native_case):
    query, graph, _, adopted, result = native_case
    before = copy.deepcopy(query)
    pending = run_attack_query(query, graph)
    assert query == before
    assert wire(pending.paths) == wire(result.paths)
    expected, names = _source_a_first_goal_programs(query["budget"]["max_steps"])
    assert len(result.paths) == len(expected)
    assert _source_a_traces(result.paths, names) == expected
    assert len(result.ranking_result["eligible_candidates"]) == len(expected)
    assert not pending.ranking_result["eligible_candidates"]
    first = result.ranking_result["eligible_candidates"]["generated_0001"]
    assert first["effort"] == 2
    assert tuple(map(Fraction, first["likelihood_interval"])) == (
        Fraction(9, 40),
        Fraction(8379, 10000),
    )
    assert first["impact"] == "High"
    assert adopted["rating_resolution"]["policy"] == "production"
    assert graph.metadata.get("synthetic") is not True
    coverage = result.rating_coverage["candidates"]["generated_0001"]
    audits = [v["rating_audit"] for v in coverage["effort"]["units"].values()]
    audits += [v["rating_audit"] for v in coverage["likelihood"]["prefixes"]]
    audits += [coverage["impact"]["rating_audit"]]
    assert {a["numeric_basis_class"] for a in audits} == {"estimated_expert_scenario"}
    assert {a["review_disposition"] for a in audits} == {"rated"}
    assert {a["review_status"] for a in audits} == {"accepted", "reviewed"}
    assert all(a["review_reference"].startswith("test://") for a in audits)


@pytest.mark.parametrize("dimension", ["C", "P", "I"])
def test_rejected_dimension_is_not_promoted(native_case, dimension):
    query, graph, release, _, _ = native_case
    changed = copy.deepcopy(release)
    if dimension == "I":
        changed["impact"]["decision"] = "needs_evidence"
    else:
        for entry in changed["classes"].values():
            entry[dimension]["decision"] = "reject"
    result = run_attack_query(apply_release(query, changed), graph)
    expected, names = _source_a_first_goal_programs(query["budget"]["max_steps"])
    assert len(result.paths) == len(expected)
    assert _source_a_traces(result.paths, names) == expected
    if dimension != "C":
        assert not result.ranking_result["eligible_candidates"]
    assert not any(
        s[{"C": "c_complete", "P": "p_complete", "I": "i_complete"}[dimension]]
        for s in result.rating_coverage["candidate_summaries"].values()
    )


@pytest.mark.parametrize(
    "field",
    [
        "horizon",
        "retry",
        "cap",
        "fact",
        "record",
        "history",
        "class",
        "value",
        "timestamp",
        "confirmation",
        "implementation_approval",
    ],
)
def test_release_refuses_changed_questions_and_missing_authority(native_case, field):
    query, _, release, _, _ = native_case
    query, release = copy.deepcopy(query), copy.deepcopy(release)
    if field == "horizon":
        query["rating_resolution"]["scope"]["horizon"] = "1s"
    elif field == "retry":
        query["rating_resolution"]["scope"]["retry_policy"] = {"max_attempts": 1}
    elif field == "cap":
        query["budget"]["max_steps"] = 1
    elif field == "fact":
        query["runtime_facts"][0]["value"] = False
    elif field == "record":
        query["rating_resolution"]["registries"]["likelihood"]["data"][0]["lower"] = "1"
    elif field == "history":
        release["history_model"]["meaning"] = "arbitrary histories"
    elif field == "class":
        release["classes"]["asrep_password_recovery"] = {}
    elif field == "value":
        release["classes"]["directory_password_reset"]["values"]["lower"] = "1"
    elif field == "timestamp":
        release["review"]["reviewed_at"] = "2000-01-01"
    elif field == "confirmation":
        release["review"]["confirmation"] = None
    else:
        release["review"]["reference"] = (
            "https://github.com/nairyuuu/ad-weighted-graph/pull/271#pullrequestreview-5490113298"
        )
    with pytest.raises(ValueError):
        validate_release(release, query)


def test_release_is_immutable_and_known_false_still_vetoes(native_case):
    _, graph, _, adopted, _ = native_case
    changed = copy.deepcopy(adopted)
    for fact in changed["runtime_facts"]:
        if fact["predicate"] == "network_winrm_reachable":
            fact.update(
                value=False, origin="observed_evidence", provenance_reference="test://denied"
            )
    result = run_attack_query(changed, graph)
    assert not result.ranking_result["eligible_candidates"]
    assert not result.paths


def test_real_cli_and_orchestration_preserve_reviewed_numeric_provenance(native_case, tmp_path):
    from scripts.research.final_cpi_coverage import independent_checks, public_check

    _, graph, _, query, _ = native_case
    result, evidence = public_check(query, graph, tmp_path, "simulated-release", "synthetic")
    assert evidence["two_CLI_exit_codes"] == [0, 0]
    assert evidence["comparison_version"] == "final-cpi-public-comparison/2.0.0"
    expected, _ = _source_a_first_goal_programs(query["budget"]["max_steps"])
    assert independent_checks(result)["checked_eligible_candidates"] == len(expected)


@pytest.mark.parametrize(
    "field", ["actor", "edge", "before", "causal_lineage", "final_state", "scenario", "order"]
)
def test_public_comparator_refuses_same_technique_different_program(
    native_case, monkeypatch, tmp_path, field
):
    from scripts.research import final_cpi_coverage as probe

    _, graph, _, query, api = native_case
    semantic = {
        f: wire(getattr(api, f))
        for f in (
            "status",
            "truncated",
            "truncation_reason",
            "complete",
            "expansions",
            "caps",
            "final_goal_reached",
            "checkpoint_reached",
            "min_effort",
            "ranking_result",
            "rating_coverage",
        )
    }
    semantic["engine_reported_guarantees"] = {
        "optimization_scope": api.optimization_scope,
        "is_minimum_proven_over_scope": api.is_minimum_proven_over_scope,
        "is_no_path_proven_over_scope": api.is_no_path_proven_over_scope,
    }
    candidates = wire(api.paths)
    original_names = [
        [s["result"]["request"]["technique_id"] for s in p["transition_history"]]
        for p in candidates
    ]
    p = candidates[0]
    if field == "actor":
        p["transition_history"][0]["result"]["request"]["actor"] = "different-actor"
    elif field == "edge":
        p["edges"][0]["id"] = "different-edge"
    elif field == "before":
        p["transition_history"][0]["result"]["before"]["control"] = []
    elif field == "causal_lineage":
        p["transition_history"][0]["derived_from_step"] = 999
    elif field == "final_state":
        p["final_state"]["admin_control"] = []
    elif field == "scenario":
        p["scenario_reference"] = "different-scenario"
    else:
        p["transition_history"][0], p["transition_history"][1] = (
            p["transition_history"][1],
            p["transition_history"][0],
        )
    if field != "order":
        assert [
            [s["result"]["request"]["technique_id"] for s in c["transition_history"]]
            for c in candidates
        ] == original_names
    semantic["candidates"] = [
        {"candidate_id": f"generated_{i:04d}", **p} for i, p in enumerate(candidates, 1)
    ]

    def transport(command, **kwargs):
        from pathlib import Path

        Path(command[command.index("--output") + 1]).write_text(
            json.dumps({"semantic": semantic}, sort_keys=True, indent=2) + "\n", encoding="utf-8"
        )
        return SimpleNamespace(returncode=0, stderr="")

    monkeypatch.setattr(probe.subprocess, "run", transport)
    monkeypatch.setattr(probe, "run_attack_query", lambda *a, **k: api)
    with pytest.raises(ValueError, match="generated program mismatch"):
        probe.public_check(query, graph, tmp_path, "mismatch", "synthetic")
