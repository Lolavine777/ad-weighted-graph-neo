"""Real delegated decisions, declared recovery models and native fail-closed bindings."""

import copy
from fractions import Fraction

import pytest

from scripts.research import final_cpi_delegated_release as release
from scripts.research.final_cpi_adoption_replay import load_inputs
from scripts.research.final_cpi_profiles import PACKAGE, ROOT, read
from src.engine import run_attack_query


def test_numeric_receipt_inputs_are_separate_from_executable_replay_pins(tmp_path, monkeypatch):
    monkeypatch.setattr(release, "ROOT", tmp_path)
    monkeypatch.setattr(release, "COHORT", tmp_path / "declared-cohort.json")
    for name in release.MODEL_INPUTS:
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("model-input")
    profile = tmp_path / "docs/research/ratings/final-cpi-v1/profile.json"
    profile.parent.mkdir(parents=True, exist_ok=True)
    profile.write_text('{"cost":1}')
    before = release.signature()
    source = tmp_path / "src/engine/query.py"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text("# unrelated source refresh\n")
    assert release.signature() == before
    profile.write_text('{"cost":2}')
    assert release.signature() != before


@pytest.fixture(scope="module")
def contexts():
    raw = ROOT / "data/raw/SEAMLESS"
    if not raw.is_dir():
        pytest.skip("Manifest-verified raw required")
    graph, frozen = load_inputs(raw)
    definition = release.definition()
    queries = release.queries(graph, frozen, raw)
    return graph, definition, queries


def test_selected_models_keep_existing_research_inputs_and_actual_user_authority(contexts):
    _, definition, _ = contexts
    assert definition["review"]["reviewer"] == "Lolavine777"
    assert definition["review"]["delegated_for"] == "nairyuuu"
    assert definition["review"]["reference"].endswith("issuecomment-6166280449")
    assert definition["recovery_models"][release.MODELS[0]]["P"] == ["1387/40000", "611/2000"]
    assert definition["recovery_models"][release.MODELS[1]]["P"] == [
        "1387/160000",
        "156823528560664795491907459/1026667944750669637337476000",
    ]
    assert read(PACKAGE / "profile.json")["b_numeric_adoption"] is False


@pytest.mark.parametrize("case_id", release.MODELS)
def test_declared_recovery_model_is_consumed_by_native_full_path(contexts, case_id):
    graph, definition, queries = contexts
    result = run_attack_query(release.apply(queries[case_id], definition), graph)
    assert result.final_goal_reached and len(result.paths) == 1
    assert result.rating_coverage["candidate_summaries"]["generated_0001"]["numeric_complete"]
    item = result.ranking_result["eligible_candidates"]["generated_0001"]
    lo = hi = Fraction(1)
    taxonomy = {
        t["technique_id"]: t["canonical_class"] for t in read(PACKAGE / "taxonomy.json")["actions"]
    }
    for prefix in result.rating_coverage["candidates"]["generated_0001"]["likelihood"]["prefixes"]:
        name = taxonomy[prefix["rating_audit"]["lookup_key"]["outcome_technique"]]
        bounds = (
            definition["recovery_models"][case_id]["P"]
            if "password_recovery" in name
            else [definition["classes"][name]["lower"], definition["classes"][name]["upper"]]
        )
        lo *= Fraction(bounds[0])
        hi *= Fraction(bounds[1])
    assert list(map(Fraction, item["likelihood_interval"])) == [lo, hi]
    assert item["effort"] == (3 if case_id == release.MODELS[0] else 4)
    assert item["impact"] == ("High" if case_id == release.MODELS[0] else "Medium")


@pytest.mark.parametrize("case_id", ["acl-group-projection", "acl-group-all-generator"])
def test_existing_approved_acl_numbers_bind_all_returned_diagnostic_paths(contexts, case_id):
    _, definition, queries = contexts
    query = queries[case_id]
    graph = release.case_graph(case_id, contexts[0], query)
    result = run_attack_query(release.apply(query, definition), graph)
    assert len(result.paths) == (100 if case_id.endswith("projection") else 2)
    assert all(
        s["numeric_complete"] for s in result.rating_coverage["candidate_summaries"].values()
    )


@pytest.mark.parametrize("case_id", ["asrep-natural-password", "kerberoast-identity"])
def test_frozen_unknown_population_controls_keep_recovery_P_unrated(contexts, case_id):
    graph, definition, queries = contexts
    result = run_attack_query(release.apply(queries[case_id], definition), graph)
    assert len(result.paths) == 1
    assert not result.ranking_result["eligible_candidates"]
    assert result.rating_coverage["candidate_summaries"]["generated_0001"]["c_complete"]
    assert not result.rating_coverage["candidate_summaries"]["generated_0001"]["p_complete"]


@pytest.mark.parametrize("mutation", ["no_model", "floor", "population", "history", "synthetic"])
def test_delegated_release_refuses_changed_recovery_question(contexts, mutation):
    _, definition, queries = contexts
    query = copy.deepcopy(queries[release.MODELS[0]])
    fact = next(
        f
        for f in query.get("assumptions", []) + query.get("runtime_facts", [])
        if f["predicate"] == "recovery_success"
    )
    if mutation == "no_model":
        fact["assumption_metadata"].pop("recovery_model")
    elif mutation in ("floor", "population"):
        fact["assumption_metadata"]["recovery_model"][mutation] = "changed"
    elif mutation == "history":
        query["rating_resolution"]["scope"]["control_scope"] = {}
    else:
        query["rating_resolution"]["policy"] = "synthetic_test_only"
    with pytest.raises(ValueError):
        release.apply(query, definition)


def test_delegated_receipt_refuses_faked_reviewer_or_boolean_cost(contexts):
    _, definition, queries = contexts
    for mutate in ("reviewer", "cost"):
        changed = copy.deepcopy(definition)
        if mutate == "reviewer":
            changed["review"]["reviewer"] = "nairyuuu"
        else:
            changed["classes"]["host_admin_execution"]["cost"] = True
        with pytest.raises(ValueError):
            release.apply(queries[release.MODELS[0]], changed)


@pytest.mark.parametrize("change", ["changed_model", "missing_model", "removed_declaration"])
def test_native_resolver_cannot_reuse_bound_P_after_model_metadata_changes(contexts, change):
    from src.engine.ranking.models import RankingValidationError

    graph, definition, queries = contexts
    query = release.apply(queries[release.MODELS[0]], definition)
    fact = next(
        f
        for f in query.get("assumptions", []) + query.get("runtime_facts", [])
        if f["predicate"] == "recovery_success"
    )
    metadata = fact["assumption_metadata"]
    if change == "changed_model":
        metadata["recovery_model"]["floor"] = 0
    else:
        metadata.pop("recovery_model")
        if change == "removed_declaration":
            metadata.pop("recovery_model_digest")
    if change == "removed_declaration":
        result = run_attack_query(query, graph)
        assert not result.ranking_result["eligible_candidates"]
        assert not result.rating_coverage["candidate_summaries"]["generated_0001"]["p_complete"]
    else:
        with pytest.raises(RankingValidationError, match="Recovery model declaration"):
            run_attack_query(query, graph)


def test_adopted_numeric_models_do_not_override_authoritative_FALSE(contexts):
    graph, definition, queries = contexts
    query = release.apply(queries[release.MODELS[1]], definition)
    for fact in query["runtime_facts"]:
        if fact["predicate"] == "authentication_accepted":
            fact.update(value=False, origin="blocked_evidence")
    result = run_attack_query(query, graph)
    assert not result.paths and not result.final_goal_reached


def test_state_goal_candidate_JSON_cannot_mint_or_mutate_native_replay_proof(contexts):
    from src.engine.ranking import decode_ranking_query
    from src.engine.ranking.adapter_145 import adapt_search_candidate
    from src.engine.ranking.models import RankingValidationError
    from src.engine.ranking.resolution_service import resolve_generated_rating_inputs
    from src.engine.ranking.validation import validate_candidate_envelope
    from src.engine.ranking.verification import verify_search_envelope

    graph, definition, queries = contexts
    query = release.apply(queries[release.MODELS[1]], definition)
    result = run_attack_query(query, graph)
    payload, candidates, _ = resolve_generated_rating_inputs(
        query["rating_resolution"], graph, result.materialized_query, result.search_result
    )
    c = candidates[0]
    envelope = adapt_search_candidate(
        path_result=c["path_result"],
        candidate_id=c["candidate_id"],
        target_asset_id=c["target_asset_id"],
        query_metadata=payload["query_metadata"],
        action_mapping=c["action_mapping"],
        route_id=c["route_id"],
        bound_actions_catalog=payload["bound_actions"],
    )
    decoded = decode_ranking_query(payload)
    proof = verify_search_envelope(result.paths[0], graph, envelope, payload["query_metadata"])
    validate_candidate_envelope(envelope, decoded, semantic_binding=proof)
    with pytest.raises(RankingValidationError):
        validate_candidate_envelope(copy.deepcopy(envelope), decoded)
    changed = copy.deepcopy(envelope)
    changed["state_goal_binding"]["final_state_digest"] = "sha256:" + "0" * 64
    with pytest.raises(RankingValidationError):
        validate_candidate_envelope(changed, decoded, semantic_binding=proof)


def test_reused_secret_User_goal_from_another_foothold_stays_visible_without_P_transfer(contexts):
    from src.engine.query_cli import wire

    graph, definition, queries = contexts
    query = release.apply(queries[release.MODELS[1]], definition)
    generated = run_attack_query(query, graph)
    secret = next(iter(generated.paths[0].final_state.recovered_secret))
    host = query["authentication_context"]
    query.update(
        initial_actor=host,
        source_foothold=host,
        initial_state={"control": [host], "recovered_secret": [wire(secret)]},
        allowed_techniques=["activate_recovered_identity"],
    )
    query["rating_resolution"]["scope"]["foothold_node_id"] = host
    result = run_attack_query(query, graph)
    assert result.final_goal_reached and len(result.paths) == 1
    assert result.paths[0].target == query["target"] != host
    assert result.paths[0].nodes[-1] == host
    assert not result.ranking_result["eligible_candidates"]
    assert (
        result.rating_coverage["candidate_summaries"]["generated_0001"]["semantic_status"]
        == "feasible"
    )
    assert not result.rating_coverage["candidate_summaries"]["generated_0001"]["p_complete"]
