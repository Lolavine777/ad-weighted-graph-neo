"""Durable regression suite for validated catalog reuse (issue #294).

Verifies bounded immutable catalog reuse by content hash, strict executable
recipe validation, rejection of modified recipes, cache invalidation across
queries when content changes, and context/state isolation.
"""

from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from scripts.research.asrep_inputs import C, V, X
from scripts.research.asrep_inputs import inputs as asrep_inputs
from scripts.research.asrep_inputs import ranking_inputs as asrep_ranking_inputs
from scripts.research.rbcd_inputs import C_R, U_R, M
from scripts.research.rbcd_inputs import inputs as rbcd_inputs
from src.engine.query import materialize_query, run_attack_query
from src.engine.semantics import (
    AttackState,
    RuntimeContext,
    evaluate,
    load_catalog,
)
from src.engine.semantics.credentials import _recipe, replay_path
from src.engine.semantics.evaluator import PreparedSemanticGraph
from src.engine.semantics.rbcd_types import DelegationBinding
from src.engine.semantics.transitions import TransitionRequest

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CATALOG_PATH = ROOT / "configs/attack_semantics.yml"


def test_unchanged_content_reuse_avoids_repeated_yaml_parsing():
    """Consecutive load_catalog calls on unchanged file parse YAML exactly once."""
    load_catalog()

    with patch(
        "yaml.safe_load",
        side_effect=AssertionError("yaml.safe_load called for unchanged content"),
    ) as mock_load:
        c1 = load_catalog()
        c2 = load_catalog()
        assert c1 is c2 or c1 == c2
        assert len(c1) > 0
        mock_load.assert_not_called()


def test_yaml_work_does_not_grow_with_rbcd_transitions_or_replay_steps():
    """RBCD query execution and replay do not reload/reparse YAML per transition step."""
    import src.engine.semantics.catalog as catalog_module

    graph, q = rbcd_inputs()
    catalog_yaml_loads = []
    orig_safe_load = yaml.safe_load

    def spy_catalog_yaml(stream):
        res = orig_safe_load(stream)
        if isinstance(res, dict) and "evidence_registry" in res:
            catalog_yaml_loads.append(1)
        return res

    with (
        patch("yaml.safe_load", side_effect=spy_catalog_yaml),
        patch.object(
            catalog_module, "validate_catalog", wraps=catalog_module.validate_catalog
        ) as spy_val,
    ):
        result = run_attack_query(q, graph)
        assert result.final_goal_reached and len(result.paths) == 3

        # Search executed 15 total path transitions across 3 paths (plus candidate evaluations).
        # Catalog YAML parsing and validation must be bounded and not scale with RBCD transitions.
        search_yaml_calls = len(catalog_yaml_loads)
        search_val_calls = spy_val.call_count
        assert search_yaml_calls <= 1, (
            f"Expected <= 1 catalog YAML parse during search, got {search_yaml_calls}"
        )
        assert search_val_calls <= 1, (
            f"Expected <= 1 catalog validation during search, got {search_val_calls}"
        )

        # Replay each path. Replay must carry catalog and not re-parse/re-validate YAML per step.
        before_replay_yaml = len(catalog_yaml_loads)
        before_replay_val = spy_val.call_count
        for path in result.paths:
            final_state = replay_path(path, graph)
            assert final_state == path.final_state
        replay_yaml_calls = len(catalog_yaml_loads) - before_replay_yaml
        replay_val_calls = spy_val.call_count - before_replay_val
        assert replay_yaml_calls == 0, (
            f"Expected 0 catalog YAML parses during replay, got {replay_yaml_calls}"
        )
        assert replay_val_calls == 0, (
            f"Expected 0 catalog validations during replay, got {replay_val_calls}"
        )


def test_distinct_custom_and_default_catalogs_coexist(tmp_path):
    """Custom catalog and default catalog have independent validated cache identities."""
    default_cat = load_catalog()

    # Create a distinct custom catalog modifying a non-gate field on an entitlement technique
    raw_doc = yaml.safe_load(DEFAULT_CATALOG_PATH.read_text(encoding="utf-8"))
    custom_path = tmp_path / "custom_semantics.yml"
    custom_doc = deepcopy(raw_doc)
    for entry in custom_doc["techniques"]:
        if entry["id"] == "genericall_add_member":
            entry["cost_factors"] = ["custom_cost_factor"]
    custom_path.write_text(yaml.safe_dump(custom_doc), encoding="utf-8")

    custom_cat = load_catalog(custom_path)
    refreshed_default = load_catalog()

    assert default_cat == refreshed_default
    custom_member = next(t for t in custom_cat if t.id == "genericall_add_member")
    default_member = next(t for t in default_cat if t.id == "genericall_add_member")
    assert custom_member.cost_factors == ("custom_cost_factor",)
    assert default_member.cost_factors != ("custom_cost_factor",)


def test_modified_rbcd_recipe_rejected_and_never_compared_to_itself(tmp_path):
    """Custom catalog modifying an RBCD recipe's gates is rejected against authoritative recipe."""
    graph, q = rbcd_inputs()
    canonical = graph.to_canonical()
    prepared_graph = PreparedSemanticGraph(canonical, snapshot_facts=graph.snapshot_facts)
    binding = DelegationBinding(**q["rbcd_bindings"][0])
    context = RuntimeContext(
        authentication_context=C_R,
        rbcd_bindings=(binding,),
    )

    req = TransitionRequest(
        technique_id="rbcd_acquire_secret",
        actor=U_R,
        source=U_R,
        target=M,
        rbcd_binding=binding,
    )

    # Tampered technique: remove 'effective_reset_right' prerequisite
    authoritative = next(t for t in load_catalog() if t.id == "rbcd_acquire_secret")
    tampered_technique = replace(
        authoritative,
        prerequisites=tuple(p for p in authoritative.prerequisites if p != "effective_reset_right"),
    )

    custom_catalog = tuple(
        tampered_technique if t.id == "rbcd_acquire_secret" else t for t in load_catalog()
    )

    # Calling evaluate with custom_catalog must NOT compare tampered_technique to itself!
    # It must validate against the authoritative default recipe and raise ValueError.
    with pytest.raises(ValueError, match="unsupported RBCD recipe; preserve executable gates"):
        evaluate(
            prepared_graph,
            AttackState(),
            req,
            context,
            catalog=custom_catalog,
        )

    # Complete RBCD recipe equality also rejects metadata-only modifications
    tampered_metadata = replace(
        authoritative,
        cost_factors=("custom_cost",),
    )
    custom_catalog_meta = tuple(
        tampered_metadata if t.id == "rbcd_acquire_secret" else t for t in load_catalog()
    )
    with pytest.raises(ValueError, match="unsupported RBCD recipe; preserve executable gates"):
        evaluate(
            prepared_graph,
            AttackState(),
            req,
            context,
            catalog=custom_catalog_meta,
        )


def test_modified_artifact_recipe_rejected_and_never_compared_to_itself(tmp_path):
    """Custom catalog modifying artifact recipe gates is rejected against authoritative recipe."""
    graph, q = asrep_inputs()
    canonical = graph.to_canonical()
    prepared_graph = PreparedSemanticGraph(canonical, snapshot_facts=graph.snapshot_facts)
    context = RuntimeContext(authentication_context=C)

    authoritative = next(t for t in load_catalog() if t.id == "asrep_request")
    tampered_asrep = replace(
        authoritative,
        prerequisites=("known_identity",),
    )
    custom_catalog = tuple(tampered_asrep if t.id == "asrep_request" else t for t in load_catalog())

    req = TransitionRequest(
        technique_id="asrep_request",
        actor=X,
        source=X,
        target=V,
    )

    # Calling evaluate with custom_catalog must reject tampered asrep_request
    with pytest.raises(ValueError, match="unsupported artifact recipe"):
        evaluate(
            prepared_graph,
            AttackState(),
            req,
            context,
            catalog=custom_catalog,
        )


def test_content_changes_between_queries_observed_without_stale_cache(tmp_path):
    """Modifying a catalog file between queries updates cache rather than returning stale data."""
    raw_doc = yaml.safe_load(DEFAULT_CATALOG_PATH.read_text(encoding="utf-8"))
    test_path = tmp_path / "mutable_catalog.yml"
    test_path.write_text(yaml.safe_dump(raw_doc), encoding="utf-8")

    cat1 = load_catalog(test_path)
    assert len(cat1) > 0

    # Mutate the file: update cost_factors on genericall_add_member
    mutated_doc = deepcopy(raw_doc)
    for entry in mutated_doc["techniques"]:
        if entry["id"] == "genericall_add_member":
            entry["cost_factors"] = ["high_noise", "detection_risk"]
    test_path.write_text(yaml.safe_dump(mutated_doc), encoding="utf-8")

    cat2 = load_catalog(test_path)
    cat2_member = next(t for t in cat2 if t.id == "genericall_add_member")
    cat1_member = next(t for t in cat1 if t.id == "genericall_add_member")
    assert cat2_member.cost_factors == ("high_noise", "detection_risk")
    assert cat2_member != cat1_member


def test_credentials_recipe_lookup_not_permanently_stale_owner_cache(tmp_path, monkeypatch):
    """Authoritative recipe lookup in credentials observes default content changes."""
    import src.engine.semantics.catalog as catalog_module

    tmp_configs = tmp_path / "configs"
    tmp_configs.mkdir(parents=True)
    tmp_catalog_path = tmp_configs / "attack_semantics.yml"
    raw_doc = yaml.safe_load(DEFAULT_CATALOG_PATH.read_text(encoding="utf-8"))
    tmp_catalog_path.write_text(yaml.safe_dump(raw_doc), encoding="utf-8")

    monkeypatch.setattr(catalog_module, "ROOT", tmp_path)

    # First lookup fetches asrep_request via _recipe
    rec1 = _recipe("asrep_request")
    assert rec1 is not None

    # Change cost_factors on asrep_request in the default file
    mutated_doc = deepcopy(raw_doc)
    for entry in mutated_doc["techniques"]:
        if entry["id"] == "asrep_request":
            entry["cost_factors"] = ["updated_recovery_cost"]
    tmp_catalog_path.write_text(yaml.safe_dump(mutated_doc), encoding="utf-8")

    # Second lookup must observe changed default content without owner-cache clear
    rec2 = _recipe("asrep_request")
    fresh_authoritative = next(t for t in load_catalog() if t.id == "asrep_request")
    assert fresh_authoritative.cost_factors == ("updated_recovery_cost",)
    assert rec2 is not None
    assert rec2.cost_factors == ("updated_recovery_cost",)
    assert rec2 == fresh_authoritative


def test_prepared_context_freezes_catalog_while_new_queries_observe_updates(tmp_path):
    """A prepared query retains its frozen catalog while subsequent queries observe file edits."""
    raw_doc = yaml.safe_load(DEFAULT_CATALOG_PATH.read_text(encoding="utf-8"))
    catalog_file = tmp_path / "evolving_catalog.yml"
    catalog_file.write_text(yaml.safe_dump(raw_doc), encoding="utf-8")

    graph, q = rbcd_inputs()
    q_copy = dict(q)
    q_copy["catalog"] = load_catalog(catalog_file)

    prepared_query = materialize_query(q_copy, graph)
    frozen_catalog = prepared_query.catalog
    assert frozen_catalog is not None

    # Modify catalog file: update cost_factors on rbcd_acquire_secret
    mutated_doc = deepcopy(raw_doc)
    for entry in mutated_doc["techniques"]:
        if entry["id"] == "rbcd_acquire_secret":
            entry["cost_factors"] = ["modified_cost"]
    catalog_file.write_text(yaml.safe_dump(mutated_doc), encoding="utf-8")

    # Newly loaded catalog sees the update
    new_cat = load_catalog(catalog_file)
    new_member = next(t for t in new_cat if t.id == "rbcd_acquire_secret")
    assert new_member.cost_factors == ("modified_cost",)

    # Prepared query still holds original frozen content
    frozen_member = next(t for t in prepared_query.catalog if t.id == "rbcd_acquire_secret")
    assert frozen_member.cost_factors != ("modified_cost",)


def test_query_context_isolation_no_leaked_attack_state_or_applicability():
    """Consecutive queries with distinct runtime facts remain strictly isolated."""
    graph, q = rbcd_inputs()

    # Query 1 with valid RBCD facts
    res1 = run_attack_query(q, graph)
    assert res1.final_goal_reached

    # Query 2 with runtime facts blocked
    q_blocked = deepcopy(q)
    q_blocked["runtime_facts"] = [
        {
            "predicate": "effective_reset_right",
            "subject": U_R,
            "target": M,
            "value": False,
            "origin": "technical_rule",
            "rationale": "explicitly blocked in test",
        }
    ]
    res2 = run_attack_query(q_blocked, graph)
    assert not res2.final_goal_reached
    assert len(res2.paths) == 0

    # Query 3 re-running original query must still reach goal without being poisoned by Query 2
    res3 = run_attack_query(q, graph)
    assert res3.final_goal_reached
    assert len(res3.paths) == 3


def test_ranking_verification_carries_prepared_catalog_through_replay():
    """Ranking verification carries prepared catalog into verify_search_envelope and replay."""
    import src.engine.ranking.verification as verification_module

    graph, q = asrep_inputs()
    payload, bindings = asrep_ranking_inputs(graph, q)

    explicit_catalog = load_catalog()
    q_with_catalog = dict(q)
    q_with_catalog["catalog"] = explicit_catalog

    materialized = materialize_query(
        q_with_catalog,
        graph,
        action_bindings=bindings,
        ranking_query=payload,
    )
    assert materialized.catalog is not None

    replay_catalogs_received = []
    original_replay_path = verification_module.replay_path

    def spy_replay_path(path, replay_graph, catalog=None):
        replay_catalogs_received.append(catalog)
        return original_replay_path(path, replay_graph, catalog=catalog)

    with patch.object(verification_module, "replay_path", side_effect=spy_replay_path):
        result = materialized.run(graph)
        assert result.final_goal_reached
        assert len(result.paths) > 0

    # The prepared catalog must reach the actual semantic replay call!
    assert len(replay_catalogs_received) > 0
    for cat in replay_catalogs_received:
        assert cat is materialized.catalog, (
            "Prepared catalog was not carried to replay_path in ranking verification"
        )


def test_load_catalog_empty_string_falls_back_to_default():
    """Calling load_catalog('') falls back to the default catalog configuration."""
    default_cat = load_catalog()
    fallback_cat = load_catalog("")
    none_cat = load_catalog(None)
    assert fallback_cat == default_cat
    assert fallback_cat == none_cat
    assert len(fallback_cat) > 0
