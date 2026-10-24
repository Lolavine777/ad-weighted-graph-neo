"""Proposed historical scenario transfer through native #258 public resolution."""

import copy

import pytest

from scripts.research.final_cpi_profiles import engineering_copy
from scripts.research.scenario_rating_pack import build_source_a_query
from src.engine import run_attack_query
from src.engine.graph import EngineGraph
from tests.source_a_identity import identity_source_a


def test_pending_source_a_cannot_infer_machine_identity_from_host_control():
    query, graph = build_source_a_query()
    result = run_attack_query(query, graph)
    assert result.search_result.complete
    assert not result.paths
    assert result.attempts
    assert all("computer_actor_authenticated" in attempt.failed for attempt in result.attempts)
    assert all(v["rated"] == 0 for v in result.rating_coverage["numeric_requests"].values())
    assert not result.ranking_result["pareto_frontier"]


def synthetic_identity_case():
    query, graph = identity_source_a()
    return engineering_copy(query, EngineGraph.from_canonical(graph))


def test_frozen_numeric_basis_matches_historical_source_without_rescoring():
    import json

    from scripts.research.scenario_rating_pack import PACKAGE, ROOT
    from src.engine.ranking.resolution_service import canonical_digest
    from src.engine.ranking.resolver import generate_work_unit_id

    basis = json.loads((ROOT / PACKAGE / "source-a-basis.json").read_text(encoding="utf-8"))
    historical = json.loads(
        (ROOT / "docs/research/ratings/week3-closeout/reviewed-release.json").read_text(
            encoding="utf-8"
        )
    )
    query, _ = build_source_a_query()
    regs = query["rating_resolution"]["registries"]
    scope = query["rating_resolution"]["scope"]
    assert (
        canonical_digest(basis)
        == "sha256:fd709b190fc3d388f61a38cab93100f9786332e667d9b8178914dd4aeefb5ac1"
    )
    assert not basis["numeric_activation_permitted"]
    assert query["rating_resolution"]["policy"] == "production"
    assert "work" not in regs
    assert "shared_preparation_units" not in json.dumps(query)
    assert "action_bindings" not in query
    assert "candidates" not in query
    unitmap = {}
    for transfer in basis["effort_transfers"]:
        olduid = transfer["historical_work_unit_id"]
        assert transfer["historical_effort_record"] == historical["work_units_ledger"][olduid]
        b = transfer["native_binding"]
        cls = next(
            c
            for c in regs["effort"]["data"]
            if b["technique_id"] in c["applicability"]["techniques"]
        )
        old = transfer["historical_effort_record"]
        assert (cls["t1"], cls["t2"], cls["computed_cost"]) == (
            old["rubric_scores"]["t1"],
            old["rubric_scores"]["t2"],
            old["computed_cost"],
        )
        context = {
            "source_id": b["source"],
            "method": cls["applicability"]["methods"][0],
            "auth_context": query["authentication_context"],
            "resource_context": None,
            "policy_id": scope["policy_id"],
            "scope": scope["scenario_id"],
        }
        uid = generate_work_unit_id(
            b["technique_id"],
            b["actor"],
            b["target"],
            "ctx-" + canonical_digest(context)[7:],
            scope["work_boundary"],
        )
        assert uid == transfer["native_work_unit_id"]
        unitmap[olduid] = uid
    assert len(unitmap) == 8
    for proposal, record in zip(
        basis["likelihood_transfers"], regs["likelihood"]["data"], strict=True
    ):
        old = next(
            p
            for p in historical["conditional_bounds_table"]
            if p["question_id"] == proposal["historical_question_id"]
        )
        assert proposal["historical_record"] == old
        assert (record["lower"], record["upper"]) == (old["lower"], old["upper"])
        assert record["provenance_digest"] == canonical_digest(proposal)
        assert record["ordered_work_prefix"] == [unitmap[u] for u in old["prefix"]]
        for key, value in proposal["native_lookup"].items():
            assert record[key] == value
        assert record["basis_category"] == "scenario_assumption"
        assert record["review_status"] == "pending_b_review"
        mechanism = old["outcome_action_id"]
        operation = (
            "reset_password"
            if "reset" in mechanism
            else "acquire_ticket"
            if "activate" in mechanism
            else "remote_exec_winrm"
        )
        assert record["retry_policy"]["by_mechanism"][operation] == old["execution_policy"]


def test_historical_numeric_review_cannot_supply_missing_machine_identity():
    from scripts.research.scenario_rating_pack import run_source_a_probe

    with pytest.raises(ValueError, match="lacks usable Computer identity"):
        run_source_a_probe()
    query, graph = build_source_a_query(simulate_review=True)
    result = run_attack_query(query, graph)
    assert result.search_result.complete
    assert not result.paths
    assert all("computer_actor_authenticated" in attempt.failed for attempt in result.attempts)
    assert not result.ranking_result["eligible_candidates"]


def test_frozen_source_a_exact_products_remain_independent_numeric_expectations():
    import json
    from fractions import Fraction

    from scripts.research.scenario_rating_pack import PACKAGE, ROOT

    oracle = json.loads((ROOT / PACKAGE / "source-a-oracles.json").read_text(encoding="utf-8"))
    for record in oracle["exact_products"].values():
        lo, hi = Fraction(1), Fraction(1)
        for a, b in record["q_intervals"]:
            lo *= Fraction(a)
            hi *= Fraction(b)
        assert [str(lo), str(hi)] == record["P"]


def test_review_simulation_changes_only_gates_on_copies():
    query, graph = build_source_a_query()
    simulated, other = build_source_a_query(simulate_review=True)
    from src.engine.ranking.resolution_service import canonical_digest

    assert graph == other
    regs = simulated["rating_resolution"]["registries"]
    for role in ("effort", "likelihood"):
        for record in regs[role]["data"]:
            record["review_status"] = "pending_b_review"
            record["disposition"] = "rated" if role == "effort" else "unrated"
        regs[role]["sha256"] = canonical_digest(regs[role]["data"])
    regs["impact"]["data"]["mappings"][0]["status"] = "proposed_pending_b_review"
    regs["impact"]["sha256"] = canonical_digest(regs["impact"]["data"])
    assert simulated == query


def test_false_veto_blocks_explicit_identity_scenario_despite_synthetic_ratings():
    query, graph = synthetic_identity_case()
    # Retain optimistic assumptions while adding authoritative negative evidence.
    facts = [
        copy.deepcopy(f)
        for f in query["runtime_facts"]
        if f["predicate"] == "directory_write_allowed"
    ]
    assert len(facts) == 3
    for fact in facts:
        fact.update(value=False, origin="observed_evidence")
    query["runtime_facts"].extend(facts)
    result = run_attack_query(query, graph)
    assert len(result.paths) == 0
    assert not result.ranking_result["pareto_frontier"]


@pytest.mark.parametrize("mutation", ["prefix", "snapshot", "horizon", "retry", "method", "auth"])
def test_native_exact_p_transfer_scope_refuses_mismatch(mutation):
    from src.engine.ranking.resolution_service import canonical_digest

    query, graph = synthetic_identity_case()
    env = query["rating_resolution"]["registries"]["likelihood"]
    for record in env["data"]:
        if mutation == "prefix":
            record["ordered_work_prefix"] = ["unreviewed-history", *record["ordered_work_prefix"]]
        elif mutation == "retry":
            record["retry_policy"] = copy.deepcopy(record["retry_policy"])
            record["retry_policy"]["by_mechanism"]["reset_password"]["max_attempts"] = 99
        else:
            record[{"auth": "auth_context", "snapshot": "snapshot_id"}.get(mutation, mutation)] = (
                "wrong"
            )
    env["sha256"] = canonical_digest(env["data"])
    result = run_attack_query(query, graph)
    assert result.paths
    assert result.rating_coverage["numeric_requests"]["P"]["rated"] == 0
    assert not result.ranking_result["pareto_frontier"]


@pytest.mark.parametrize("mutation", ["goal_id", "typed_goal", "authority", "auth_context"])
def test_native_impact_or_effort_transfer_refuses_wrong_goal_context(mutation):
    from src.engine.ranking.resolution_service import canonical_digest

    query, graph = synthetic_identity_case()
    regs = query["rating_resolution"]["registries"]
    if mutation == "authority":
        query.pop("scenario_reference")
    elif mutation == "auth_context":
        for record in regs["effort"]["data"]:
            record["applicability"]["required_auth_context"] = "wrong"
        regs["effort"]["sha256"] = canonical_digest(regs["effort"]["data"])
    else:
        app = regs["impact"]["data"]["mappings"][0]["applicability"]
        if mutation == "goal_id":
            app["goal_id"] = "wrong"
        else:
            app["semantic_goal"]["required_state"] = {"control": [query["target"]]}
        regs["impact"]["sha256"] = canonical_digest(regs["impact"]["data"])
    result = run_attack_query(query, graph)
    assert result.paths
    dimension = "C" if mutation == "auth_context" else "I"
    assert result.rating_coverage["numeric_requests"][dimension]["rated"] == 0
    if dimension == "C":
        assert result.min_effort["minimum_effort_value"] is None
    else:
        assert not result.ranking_result["pareto_frontier"]


def test_induced_projection_matches_verified_raw_when_available():
    from scripts.research.scenario_rating_pack import ROOT, verify_source_a_projection

    raw = ROOT / "data/raw/SEAMLESS"
    if not raw.exists():
        pytest.skip("optional manifest-verified SEAMLESS raw prerequisite unavailable")
    assert verify_source_a_projection(raw) == {"verified": True, "nodes": 7, "edges": 16}
