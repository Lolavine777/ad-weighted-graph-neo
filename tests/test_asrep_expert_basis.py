"""Independent Phase 1 oracles precede the new public generated run."""

import copy
from fractions import Fraction
from math import prod

import pytest

from scripts.research.asrep_expert_basis import (
    PACKAGE,
    ROOT,
    build_inputs,
    engineering_graph_copy,
    engineering_review_copy,
    read,
    verify_historical,
)
from src.engine import run_attack_query
from src.engine.ranking.likelihood import ReviewedScenarioLikelihoodProvider
from src.engine.ranking.resolution_service import canonical_digest
from src.engine.ranking.resolver import LikelihoodLookupKey, ResolverDisposition


@pytest.fixture(scope="module")
def inputs():
    raw = ROOT / "data/raw/SEAMLESS"
    if not raw.is_dir():
        pytest.skip("Authorized manifest-verified SEAMLESS raw required")
    return build_inputs(raw, "da21fbb545061c56c6dfff6ac489e7794a53ec73")


def test_independent_fraction_oracle_and_immutable_history():
    proposal, oracle = read(PACKAGE / "proposal.json"), read(PACKAGE / "oracle.json")
    lo = prod(Fraction(e["lower"]) for e in proposal["events"])
    hi = prod(Fraction(e["upper"]) for e in proposal["events"])
    assert [str(lo), str(hi)] == oracle["path_product"] == ["9/1024", "21609/400000"]
    population = proposal["target_population"]
    assert Fraction(population["compute_floor"], population["population_size"]) == Fraction(1, 32)
    assert Fraction(population["compute_cap"], population["population_size"]) == Fraction(1, 16)
    assert proposal["status"] == "proposed_pending_b_review"
    assert proposal["independent_b_review"] is False
    assert proposal["human_numeric_elicitation_completed"] is False
    verify_historical()


def test_engineering_copy_marks_converted_numeric_provenance_as_synthetic(inputs):
    _, query, _ = inputs
    before = copy.deepcopy(query)
    registries = engineering_review_copy(query)["rating_resolution"]["registries"]
    for role in ("effort", "likelihood"):
        assert all(
            r["basis_category"] == r.get("numeric_basis_class") == "synthetic_test_only"
            for r in registries[role]["data"]
        )
    assert registries["impact"]["data"]["evidence_class"] == "synthetic_test_only"
    assert all(
        m.get("numeric_basis_class") == "synthetic_test_only"
        for m in registries["impact"]["data"]["mappings"]
    )
    assert query == before


def test_pending_and_engineering_copy_generate_same_program_with_exact_product(inputs):
    graph, query, proposal = inputs
    pending = run_attack_query(query, graph)
    reviewed = run_attack_query(engineering_review_copy(query), engineering_graph_copy(graph))
    oracle = read(PACKAGE / "oracle.json")
    assert len(pending.search_result.paths) == len(reviewed.search_result.paths) == 1
    assert pending.rating_coverage["numeric_requests"]["P"] == {"required": 4, "rated": 0}
    assert reviewed.rating_coverage["numeric_requests"]["P"] == {"required": 4, "rated": 4}
    assessed = reviewed.ranking_result["eligible_candidates"]["generated_0001"]
    assert [str(v) for v in assessed["likelihood_interval"]] == oracle["path_product"]
    assert assessed["effort"] == 3
    assert assessed["impact"] == "High"
    path = reviewed.search_result.paths[0]
    assert [s.result.request.technique_id for s in path.transition_history] == oracle["program"]
    assert not pending.ranking_result["pareto_frontier"]
    assert reviewed.ranking_result["pareto_frontier"] == ["generated_0001"]
    assert proposal["status"] == "proposed_pending_b_review"
    assert all(
        r["review_status"] == "pending"
        for r in query["rating_resolution"]["registries"]["likelihood"]["data"]
    )
    prefixes = reviewed.rating_coverage["candidates"]["generated_0001"]["likelihood"]["prefixes"]
    records = query["rating_resolution"]["registries"]["likelihood"]["data"]
    assert [p["rating_audit"]["lookup_key"]["ordered_work_prefix"] for p in prefixes] == [
        r["ordered_work_prefix"] for r in records
    ]
    assert [p["rating_audit"]["lookup_key"]["resource_context"] for p in prefixes] == [
        r["resource_context"] for r in records
    ]


@pytest.mark.parametrize(
    "field",
    [
        "scenario_id",
        "snapshot_id",
        "foothold_node_id",
        "actor_id",
        "source_id",
        "target_id",
        "method",
        "budget",
        "horizon",
        "auth_context",
        "resource_context",
        "policy_id",
        "retry_policy",
        "target_population",
        "control_scope",
    ],
)
def test_changed_record_context_cannot_borrow_numeric_basis(inputs, field):
    _, query, _ = inputs
    changed = engineering_review_copy(query)
    records = changed["rating_resolution"]["registries"]["likelihood"]["data"]
    fields = LikelihoodLookupKey.__dataclass_fields__
    original = records[-1]
    key = LikelihoodLookupKey(
        **{
            k: tuple(v) if k == "ordered_work_prefix" else v
            for k, v in original.items()
            if k in fields
        }
    )
    for record in records:
        old = record[field]
        record[field] = (
            old + 1
            if type(old) is int
            else {"different": True}
            if isinstance(old, dict)
            else "different"
        )
    result = ReviewedScenarioLikelihoodProvider(records).resolve_likelihood(
        key,
        key.ordered_work_prefix,
        key.outcome_work_unit_id,
        changed["rating_resolution"]["scope"],
    )
    assert result.disposition != ResolverDisposition.RATED
    assert result.value is None


@pytest.mark.parametrize(
    "change",
    [
        "history_order",
        "missing_record",
        "contradictory_record",
        "weaker_goal",
        "known_false",
        "missing_recovery",
        "original_scenario",
    ],
)
def test_meaningful_refusals(inputs, change):
    graph, query, _ = inputs
    changed = engineering_review_copy(query)
    env = changed["rating_resolution"]["registries"]["likelihood"]
    if change == "history_order":
        env["data"][-1]["ordered_work_prefix"] = list(
            reversed(env["data"][-1]["ordered_work_prefix"])
        )
    elif change == "missing_record":
        env["data"].pop(1)
    elif change == "contradictory_record":
        record = copy.deepcopy(env["data"][1])
        record["lower"] = "1/64"
        env["data"].append(record)
    elif change == "weaker_goal":
        impact = changed["rating_resolution"]["registries"]["impact"]
        descriptor = impact["data"]["mappings"][0]["applicability"]["semantic_goal"]
        descriptor["required_state"] = {"session_control": [changed["target"]]}
        impact["sha256"] = canonical_digest(impact["data"])
    elif change == "known_false":
        fact = next(f for f in changed["assumptions"] if f["predicate"] == "admin_channel")
        changed["runtime_facts"] = [{**fact, "value": False, "origin": "blocked_evidence"}]
    elif change == "missing_recovery":
        changed["assumptions"] = [
            f for f in changed["assumptions"] if f["predicate"] != "recovery_success"
        ]
    else:
        changed["scenario_reference"] = "week4-seamless-v1"
        changed["rating_resolution"]["scope"]["scenario_id"] = "week4-seamless-v1"
        for fact in changed["assumptions"]:
            fact["scope"] = "week4-seamless-v1"
    env["sha256"] = canonical_digest(env["data"])
    result = run_attack_query(changed, engineering_graph_copy(graph))
    assert not result.ranking_result or not result.ranking_result["pareto_frontier"]
    if change == "known_false":
        assert result.status == "blocked"
        assert not result.search_result.paths
        assert "known_false_veto" in [
            r.reason for r in result.materialized_query.rejected_assumptions
        ]
    elif change == "missing_recovery":
        assert result.status == "indeterminate"
        assert not result.search_result.paths
    elif change == "weaker_goal":
        assert result.rating_coverage["numeric_requests"]["I"]["rated"] == 0
    else:
        assert result.rating_coverage["numeric_requests"]["P"]["rated"] < 4


@pytest.mark.parametrize("field", ["history", "program", "canonical_class", "recovery_bound"])
def test_documented_conditional_question_is_validated_before_search(field):
    from scripts.research.asrep_expert_basis import validate_proposal

    proposal = copy.deepcopy(read(PACKAGE / "proposal.json"))
    if field == "history":
        proposal["events"][2]["history"] = []
    elif field == "program":
        proposal["program"] = proposal["program"][::-1]
    elif field == "canonical_class":
        proposal["events"][1]["canonical_class"] = "directory_password_reset"
    else:
        proposal["events"][1]["upper"] = "1/2"
    with pytest.raises(ValueError):
        validate_proposal(proposal)


def test_engineering_copy_is_quarantined_and_original_graph_unchanged(inputs):
    graph, query, _ = inputs
    original = graph.to_canonical()
    derivative = engineering_graph_copy(graph)
    copied = engineering_review_copy(query)
    copied["rating_resolution"]["policy"] = "production"
    result = run_attack_query(copied, derivative)
    assert result.rating_coverage["numeric_requests"]["P"]["rated"] == 0
    assert not result.ranking_result["pareto_frontier"]
    assert graph.to_canonical() == original
    assert derivative.metadata["synthetic"] is True
    assert derivative.snapshot_facts.graph_sha256 != graph.snapshot_facts.graph_sha256


def test_synthetic_snapshot_cli_transport_preserves_static_facts(inputs, tmp_path):
    from scripts.research.asrep_expert_basis import run_snapshot_case
    from src.parser.snapshot_facts import serialize_snapshot

    graph, query, _ = inputs
    graph = engineering_graph_copy(graph)
    query = engineering_review_copy(query)
    config = query.pop("rating_resolution")
    snapshot = tmp_path / "snapshot.json"
    snapshot.write_text(serialize_snapshot(graph.to_canonical(), graph.snapshot_facts))
    report, semantic = run_snapshot_case(
        "engineering", query, config, snapshot, tmp_path, label="synthetic"
    )
    assert report["evidence_class"] == "synthetic_test_only"
    assert semantic["rating_coverage"]["numeric_requests"]["P"] == {"required": 4, "rated": 4}
    assert semantic["status"] == "success"
