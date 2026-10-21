"""Proposed historical scenario transfer through native #258 public resolution."""

import pytest

from scripts.research.scenario_rating_pack import build_source_a_query
from src.engine import run_attack_query
from tests.test_final_cpi_profiles import _source_a_first_goal_programs, _source_a_traces


def test_pending_source_a_generates_all_paths_without_numeric_activation():
    query, graph = build_source_a_query()
    result = run_attack_query(query, graph)
    assert result.search_result.complete
    expected, names = _source_a_first_goal_programs(query["budget"]["max_steps"])
    assert len(expected) == 330
    assert len(result.paths) == len(expected)
    assert _source_a_traces(result.paths, names) == expected
    assert all(v["rated"] == 0 for v in result.rating_coverage["numeric_requests"].values())
    assert not result.ranking_result["pareto_frontier"]


def test_frozen_numeric_basis_matches_historical_source_without_rescoring():
    import json

    from scripts.research.scenario_rating_pack import PACKAGE, ROOT
    from src.engine.ranking.resolution_service import canonical_digest
    from src.engine.ranking.resolver import generate_work_unit_id

    basis = json.loads((ROOT / PACKAGE / "source-a-basis.json").read_text())
    historical = json.loads(
        (ROOT / "docs/research/ratings/week3-closeout/reviewed-release.json").read_text()
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


def test_real_automatic_products_frontier_and_all_generated_history_gaps():
    import json
    from fractions import Fraction

    from scripts.research.scenario_rating_pack import PACKAGE, ROOT, run_source_a_probe

    report = run_source_a_probe()
    assert report["status"] == "PASS"
    assert not report["numeric_approval"]
    assert report["fully_rated_paths"] == 2
    assert report["p_unrated_paths"] == 328
    oracle = json.loads((ROOT / PACKAGE / "source-a-oracles.json").read_text())
    plan = json.loads(
        (ROOT / "docs/research/ratings/week3-closeout/semantic-bridge-plan.json").read_text()
    )
    bindings = plan["sources"]["source_a"]["transition_action_bindings"]
    labels = {
        (b["technique_id"], b["actor"], b["source"], b["target"]): b["action_id"] for b in bindings
    }
    query, graph = build_source_a_query(simulate_review=True)
    result = run_attack_query(query, graph)
    expected_programs, names = _source_a_first_goal_programs(query["budget"]["max_steps"])
    assert len(result.paths) == len(expected_programs)
    assert _source_a_traces(result.paths, names) == expected_programs
    programs = {
        tuple(
            labels[
                (
                    s.result.request.technique_id,
                    s.result.request.actor,
                    s.result.request.source,
                    s.result.request.target,
                )
            ]
            for s in path.transition_history
        ): f"generated_{index:04d}"
        for index, path in enumerate(result.paths, 1)
    }
    for expected in oracle["programs"]:
        assert tuple(expected["generated_actions"]) in programs
        assert (
            report["historical_candidate_ids"][expected["candidate_id"]]
            == programs[tuple(expected["generated_actions"])]
        )
    for cid, record in oracle["exact_products"].items():
        lo, hi = Fraction(1), Fraction(1)
        for a, b in record["q_intervals"]:
            lo *= Fraction(a)
            hi *= Fraction(b)
        assert [str(lo), str(hi)] == record["P"]
        assert (
            result.ranking_result["eligible_candidates"][report["historical_candidate_ids"][cid]][
                "likelihood_interval"
            ]
            == record["P"]
        )
    assert result.rating_coverage["binding"]["shared_preparation_units"] == []
    assert result.rating_coverage["binding"]["canonical_rejections"] == {}
    assert result.min_effort["all_best_candidate_ids"] == [
        report["historical_candidate_ids"][cid] for cid in oracle["min_effort_ties"]
    ]
    assert result.ranking_result["pareto_frontier"] == [
        report["historical_candidate_ids"][cid] for cid in oracle["pareto_frontier"]
    ]
    assert all(
        d["reasons"] == ["likelihood_unrated"]
        for d in result.ranking_result["diagnostics"].values()
    )
    assert all(
        s["c_complete"] and s["i_complete"]
        for s in result.rating_coverage["candidate_summaries"].values()
    )


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


def test_false_veto_blocks_historical_route_despite_numeric_gate_simulation():
    import copy

    query, graph = build_source_a_query(simulate_review=True)
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

    query, graph = build_source_a_query(simulate_review=True)
    env = query["rating_resolution"]["registries"]["likelihood"]
    for record in env["data"]:
        if mutation == "prefix":
            record["ordered_work_prefix"] = ["unreviewed-history", *record["ordered_work_prefix"]]
        elif mutation == "retry":
            record["retry_policy"]["by_mechanism"]["reset_password"]["max_attempts"] = 99
        else:
            record[{"auth": "auth_context", "snapshot": "snapshot_id"}.get(mutation, mutation)] = (
                "wrong"
            )
    env["sha256"] = canonical_digest(env["data"])
    result = run_attack_query(query, graph)
    assert result.rating_coverage["numeric_requests"]["P"]["rated"] == 0
    assert not result.ranking_result["pareto_frontier"]


@pytest.mark.parametrize("mutation", ["goal_id", "typed_goal", "authority", "auth_context"])
def test_native_impact_or_effort_transfer_refuses_wrong_goal_context(mutation):
    from src.engine.ranking.resolution_service import canonical_digest

    query, graph = build_source_a_query(simulate_review=True)
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
