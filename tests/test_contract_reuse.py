"""Durable regression suite for validated graph contract reuse.

Verifies bounded immutable graph contract reuse by content hash, strict schema
validation, prevention of shared mutable cached objects, cache invalidation
when file content changes, and context/query isolation.
"""

from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from scripts.check_contract import (
    CURRENT_CONTRACT_VERSION,
    load_contract,
)
from src.engine.graph import EngineGraph
from src.parser import DirectGraphBuilder, deserialize_graph, serialize_graph

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONTRACT_PATH = ROOT / "configs/contract.yml"


def test_unchanged_content_reuse_avoids_repeated_yaml_parsing():
    """Consecutive load_contract calls on unchanged file parse YAML exactly once."""
    load_contract()

    with patch(
        "yaml.safe_load",
        side_effect=AssertionError("yaml.safe_load called for unchanged contract content"),
    ) as mock_load:
        c1 = load_contract()
        c2 = load_contract()
        assert c1 == c2
        assert c1["version"] == CURRENT_CONTRACT_VERSION
        mock_load.assert_not_called()


def test_mutating_returned_contract_does_not_corrupt_cache():
    """Mutating a returned contract dictionary does not alter cached content."""
    c1 = load_contract()
    original_memberof_weight = c1["profiles"]["unit"]["weights"]["MemberOf"]

    # Mutate the returned dictionary aggressively
    c1["profiles"]["unit"]["weights"]["MemberOf"] = 9999.0
    c1["status"] = "draft"
    del c1["node_kinds"]

    c2 = load_contract()
    assert c2["profiles"]["unit"]["weights"]["MemberOf"] == original_memberof_weight
    assert c2["status"] == "accepted"
    assert "node_kinds" in c2
    assert c2["profiles"]["unit"]["weights"]["MemberOf"] != 9999.0


def test_content_changes_on_disk_observed_without_stale_cache(tmp_path):
    """Modifying a contract file on disk invalidates cache and returns fresh data."""
    raw_doc = yaml.safe_load(DEFAULT_CONTRACT_PATH.read_text(encoding="utf-8"))
    test_path = tmp_path / "contract_mutable.yml"
    test_path.write_text(yaml.safe_dump(raw_doc), encoding="utf-8")

    c1 = load_contract(test_path)
    assert c1["profiles"]["unit"]["weights"]["AdminTo"] == 1.0

    # Modify content on disk
    mutated = deepcopy(raw_doc)
    mutated["profiles"]["unit"]["weights"]["AdminTo"] = 2.5
    test_path.write_text(yaml.safe_dump(mutated), encoding="utf-8")

    c2 = load_contract(test_path)
    assert c2["profiles"]["unit"]["weights"]["AdminTo"] == 2.5

    # Default contract is unaffected
    default_c = load_contract()
    assert default_c["profiles"]["unit"]["weights"]["AdminTo"] == 1.0


def test_distinct_custom_and_default_contracts_coexist(tmp_path):
    """Custom contract and default contract have independent cache entries."""
    default_c = load_contract()

    raw_doc = yaml.safe_load(DEFAULT_CONTRACT_PATH.read_text(encoding="utf-8"))
    custom_doc = deepcopy(raw_doc)
    custom_doc["profiles"]["unit"]["weights"]["GenericAll"] = 3.0
    custom_path = tmp_path / "custom_contract.yml"
    custom_path.write_text(yaml.safe_dump(custom_doc), encoding="utf-8")

    custom_c = load_contract(custom_path)
    refreshed_default = load_contract()

    assert default_c == refreshed_default
    assert custom_c["profiles"]["unit"]["weights"]["GenericAll"] == 3.0
    assert refreshed_default["profiles"]["unit"]["weights"]["GenericAll"] == 1.0


def test_invalid_contract_rejected_and_not_cached(tmp_path):
    """Malformed or invalid contract fails closed and does not leave a corrupt cache entry."""
    raw_doc = yaml.safe_load(DEFAULT_CONTRACT_PATH.read_text(encoding="utf-8"))
    bad_doc = deepcopy(raw_doc)
    bad_doc["profiles"]["unit"]["weights"]["MemberOf"] = -5.0  # Invalid cost
    bad_path = tmp_path / "bad_contract.yml"
    bad_path.write_text(yaml.safe_dump(bad_doc), encoding="utf-8")

    with pytest.raises(ValueError, match="finite and >= 1.0"):
        load_contract(bad_path)

    # Calling again still fails closed
    with pytest.raises(ValueError, match="finite and >= 1.0"):
        load_contract(bad_path)


def test_nonexistent_contract_path_raises_value_error():
    """Nonexistent contract path raises ValueError matching existing convention."""
    with pytest.raises(ValueError, match="unable to load graph contract"):
        load_contract(Path("/nonexistent/contract.yml"))


def test_graph_and_serialization_operations_reuse_contract():
    """EngineGraph and serialization functions reuse cached contract without parsing YAML."""
    toy_graph_path = ROOT / "data/samples/toy-graph.json"
    raw_json = toy_graph_path.read_text(encoding="utf-8")

    # Warm contract cache
    load_contract()

    with patch(
        "yaml.safe_load",
        side_effect=AssertionError("yaml.safe_load called during graph operations"),
    ) as mock_yaml:
        # EngineGraph from canonical
        eg = EngineGraph.from_canonical(raw_json)
        assert len(list(eg.nodes())) > 0

        # Serialization / deserialization
        serialized = serialize_graph(eg.to_canonical())
        deserialized = deserialize_graph(serialized)
        assert len(deserialized["nodes"]) == len(list(eg.nodes()))

        mock_yaml.assert_not_called()


def test_builder_reuses_cached_contract():
    """DirectGraphBuilder reuses cached contract without re-parsing YAML."""
    load_contract()

    with patch(
        "yaml.safe_load",
        side_effect=AssertionError("yaml.safe_load called during DirectGraphBuilder creation"),
    ) as mock_yaml:
        builder = DirectGraphBuilder()
        assert builder._contract["version"] == CURRENT_CONTRACT_VERSION
        mock_yaml.assert_not_called()


def test_evaluate_search_candidates_reuses_prepared_graph_query_locally():
    """evaluate_search_candidates constructs graph and prepared instances once per batch."""
    from scripts.research.rbcd_inputs import (
        inputs as rbcd_inputs,
    )
    from scripts.research.rbcd_inputs import (
        ranking_inputs as rbcd_ranking_inputs,
    )
    from src.engine.query import materialize_query

    graph, q = rbcd_inputs()
    packet, bindings = rbcd_ranking_inputs(graph, q)
    materialized = materialize_query(
        q,
        graph,
        action_bindings=bindings,
        ranking_query=packet,
    )

    import src.engine.ranking.verification as verification_mod

    received_graphs = []
    received_prepared = []
    orig_verify = verification_mod.verify_search_envelope

    def spy_verify(path, graph, envelope, query_metadata, *, catalog=None, prepared=None):
        received_graphs.append(graph)
        received_prepared.append(prepared)
        return orig_verify(
            path, graph, envelope, query_metadata, catalog=catalog, prepared=prepared
        )

    with patch.object(verification_mod, "verify_search_envelope", side_effect=spy_verify):
        result = materialized.run(graph)
        assert result.final_goal_reached
        assert len(result.paths) == 3

        # Exactly 3 candidates replayed
        assert len(received_prepared) == 3
        # All 3 candidates received the exact same query-local EngineGraph instance
        assert len({id(g) for g in received_graphs}) == 1
        # All 3 candidates received the exact same query-local PreparedSemanticGraph instance
        assert all(p is not None for p in received_prepared)
        assert len({id(p) for p in received_prepared}) == 1


def test_verify_search_envelope_omitted_prepared_works():
    """verify_search_envelope works correctly when prepared parameter is omitted."""
    from scripts.research.asrep_inputs import inputs as asrep_inputs
    from scripts.research.asrep_inputs import ranking_inputs as asrep_ranking_inputs
    from src.engine.ranking.adapter_145 import adapt_search_candidate
    from src.engine.ranking.verification import verify_search_envelope

    graph, q = asrep_inputs()
    payload, bindings = asrep_ranking_inputs(graph, q)
    from src.engine.query import run_attack_query

    result = run_attack_query(q, graph)
    path = result.paths[0]
    actions = [
        bindings[
            (
                s.result.request.technique_id,
                s.result.request.actor,
                s.result.request.source,
                s.result.request.target,
            )
        ]
        for s in path.transition_history
    ]
    metadata = {
        **payload["query_metadata"],
        "target_impact_assessments": payload["target_impact_assessments"],
    }
    envelope = adapt_search_candidate(
        path_result=path,
        candidate_id="cand_0",
        target_asset_id=q["target"],
        query_metadata=metadata,
        action_mapping=actions,
        route_id="route_0",
        bound_actions_catalog=payload.get("bound_actions"),
    )

    # Calling verify_search_envelope without prepared kwarg must succeed
    binding = verify_search_envelope(path, graph, envelope, payload["query_metadata"])
    assert binding is not None


def test_verify_search_envelope_snapshot_mismatch_fails_closed():
    """verify_search_envelope rejects mismatched snapshot_id even if prepared is supplied."""
    from scripts.research.asrep_inputs import inputs as asrep_inputs
    from scripts.research.asrep_inputs import ranking_inputs as asrep_ranking_inputs
    from src.engine.ranking import RankingValidationError
    from src.engine.ranking.adapter_145 import adapt_search_candidate
    from src.engine.ranking.verification import verify_search_envelope
    from src.engine.semantics.evaluator import PreparedSemanticGraph

    graph, q = asrep_inputs()
    payload, bindings = asrep_ranking_inputs(graph, q)
    from src.engine.query import run_attack_query

    result = run_attack_query(q, graph)
    path = result.paths[0]
    actions = [
        bindings[
            (
                s.result.request.technique_id,
                s.result.request.actor,
                s.result.request.source,
                s.result.request.target,
            )
        ]
        for s in path.transition_history
    ]
    metadata = {
        **payload["query_metadata"],
        "target_impact_assessments": payload["target_impact_assessments"],
    }
    envelope = adapt_search_candidate(
        path_result=path,
        candidate_id="cand_0",
        target_asset_id=q["target"],
        query_metadata=metadata,
        action_mapping=actions,
        route_id="route_0",
        bound_actions_catalog=payload.get("bound_actions"),
    )

    tampered_metadata = dict(payload["query_metadata"])
    tampered_metadata["snapshot_id"] = "sha256:" + "0" * 64

    prepared = PreparedSemanticGraph(graph.to_canonical(), snapshot_facts=graph.snapshot_facts)

    with pytest.raises(RankingValidationError, match="semantic replay snapshot does not match"):
        verify_search_envelope(path, graph, envelope, tampered_metadata, prepared=prepared)


def test_unreadable_contract_file_raises_value_error(tmp_path):
    """File on disk with permission denied (chmod 000) raises ValueError consistently."""
    bad_perm_file = tmp_path / "noperm_contract.yml"
    bad_perm_file.write_text("version: '1.3.0'\n", encoding="utf-8")
    bad_perm_file.chmod(0o000)
    try:
        with pytest.raises(ValueError, match="unable to load graph contract"):
            load_contract(bad_perm_file)
    finally:
        bad_perm_file.chmod(0o644)


def test_malformed_yaml_syntax_raises_value_error(tmp_path):
    """Contract file containing invalid YAML syntax fails closed with ValueError."""
    syntax_error_file = tmp_path / "syntax_error.yml"
    syntax_error_file.write_text(":\n  invalid: [yaml\n", encoding="utf-8")
    with pytest.raises(ValueError, match="unable to load graph contract"):
        load_contract(syntax_error_file)


def test_contract_non_mapping_raises_value_error(tmp_path):
    """Contract containing a YAML list instead of a mapping raises ValueError."""
    list_file = tmp_path / "list_contract.yml"
    list_file.write_text("- item1\n- item2\n", encoding="utf-8")
    with pytest.raises(ValueError, match="graph contract must be a mapping"):
        load_contract(list_file)


def test_contract_version_mismatch_raises_value_error(tmp_path):
    """Contract with unsupported version raises ValueError matching parser convention."""
    raw_doc = yaml.safe_load(DEFAULT_CONTRACT_PATH.read_text(encoding="utf-8"))
    wrong_version_doc = deepcopy(raw_doc)
    wrong_version_doc["version"] = "1.2.0"
    wrong_version_file = tmp_path / "wrong_version.yml"
    wrong_version_file.write_text(yaml.safe_dump(wrong_version_doc), encoding="utf-8")

    with pytest.raises(
        ValueError, match="graph contract is malformed: unexpected current contract version"
    ):
        load_contract(wrong_version_file)


def test_verify_search_envelope_avoids_to_canonical_with_prepared():
    """verify_search_envelope reads graph.metadata without invoking full graph.to_canonical()."""
    from scripts.research.asrep_inputs import inputs as asrep_inputs
    from scripts.research.asrep_inputs import ranking_inputs as asrep_ranking_inputs
    from src.engine.query import run_attack_query
    from src.engine.ranking.adapter_145 import adapt_search_candidate
    from src.engine.ranking.verification import verify_search_envelope
    from src.engine.semantics.evaluator import PreparedSemanticGraph

    graph, q = asrep_inputs()
    payload, bindings = asrep_ranking_inputs(graph, q)
    result = run_attack_query(q, graph)
    path = result.paths[0]
    actions = [
        bindings[
            (
                s.result.request.technique_id,
                s.result.request.actor,
                s.result.request.source,
                s.result.request.target,
            )
        ]
        for s in path.transition_history
    ]
    metadata = {
        **payload["query_metadata"],
        "target_impact_assessments": payload["target_impact_assessments"],
    }
    envelope = adapt_search_candidate(
        path_result=path,
        candidate_id="cand_0",
        target_asset_id=q["target"],
        query_metadata=metadata,
        action_mapping=actions,
        route_id="route_0",
        bound_actions_catalog=payload.get("bound_actions"),
    )
    prepared = PreparedSemanticGraph(graph.to_canonical(), snapshot_facts=graph.snapshot_facts)

    with patch.object(
        graph,
        "to_canonical",
        side_effect=AssertionError("to_canonical should not be called when prepared is supplied"),
    ):
        binding = verify_search_envelope(
            path, graph, envelope, payload["query_metadata"], prepared=prepared
        )
        assert binding is not None


def test_verify_search_envelope_legacy_mock_signature_fallback():
    """verify_search_envelope gracefully handles legacy replay_path mocks without prepared kwarg."""
    import src.engine.ranking.verification as verification_mod
    from scripts.research.asrep_inputs import inputs as asrep_inputs
    from scripts.research.asrep_inputs import ranking_inputs as asrep_ranking_inputs
    from src.engine.query import run_attack_query
    from src.engine.ranking.adapter_145 import adapt_search_candidate
    from src.engine.semantics.evaluator import PreparedSemanticGraph

    graph, q = asrep_inputs()
    payload, bindings = asrep_ranking_inputs(graph, q)
    result = run_attack_query(q, graph)
    path = result.paths[0]
    actions = [
        bindings[
            (
                s.result.request.technique_id,
                s.result.request.actor,
                s.result.request.source,
                s.result.request.target,
            )
        ]
        for s in path.transition_history
    ]
    metadata = {
        **payload["query_metadata"],
        "target_impact_assessments": payload["target_impact_assessments"],
    }
    envelope = adapt_search_candidate(
        path_result=path,
        candidate_id="cand_0",
        target_asset_id=q["target"],
        query_metadata=metadata,
        action_mapping=actions,
        route_id="route_0",
        bound_actions_catalog=payload.get("bound_actions"),
    )
    prepared = PreparedSemanticGraph(graph.to_canonical(), snapshot_facts=graph.snapshot_facts)

    call_signatures = []

    def legacy_replay_mock(path_arg, graph_arg, catalog=None):
        call_signatures.append(("no_prepared", catalog))
        return path_arg.final_state

    with patch.object(verification_mod, "replay_path", side_effect=legacy_replay_mock):
        binding = verification_mod.verify_search_envelope(
            path, graph, envelope, payload["query_metadata"], prepared=prepared
        )
        assert binding is not None
        assert call_signatures == [("no_prepared", None)]


def test_prepared_semantic_graph_edges_between_lookup_and_mutation_isolation():
    """PreparedSemanticGraph.edges_between returns matching edges and protects against mutation."""
    from scripts.research.rbcd_inputs import inputs as rbcd_inputs

    graph, _ = rbcd_inputs()
    prepared = graph.to_prepared()

    # Look up known edges
    canonical = graph.to_canonical()
    first_edge = canonical["edges"][0]
    matched = prepared.edges_between(first_edge["source"], first_edge["target"])
    assert len(matched) >= 1
    assert any(e["id"] == first_edge["id"] for e in matched)

    # Mutating the returned record must not corrupt prepared graph internal records
    matched[0]["weight"] = 99999.0
    fresh = prepared.edges_between(first_edge["source"], first_edge["target"])
    assert fresh[0]["weight"] != 99999.0

    # Non-existent pair returns empty tuple
    assert prepared.edges_between("nonexistent_src", "nonexistent_tgt") == ()


def test_engine_graph_to_prepared_caching_and_identity():
    """EngineGraph.to_prepared caches and returns the exact same PreparedSemanticGraph."""
    from scripts.research.rbcd_inputs import inputs as rbcd_inputs

    graph, _ = rbcd_inputs()
    p1 = graph.to_prepared()
    p2 = graph.to_prepared()
    assert p1 is p2
    assert p1.snapshot_facts is graph.snapshot_facts


def test_engine_graph_to_canonical_cached_mutation_isolation():
    """EngineGraph.to_canonical returns defensive copies from cached canonical structure."""
    from scripts.research.rbcd_inputs import inputs as rbcd_inputs

    graph, _ = rbcd_inputs()
    c1 = graph.to_canonical()
    orig_node_kind = c1["nodes"][0]["kind"]
    c1["nodes"][0]["kind"] = "MUTATED_KIND"

    c2 = graph.to_canonical()
    assert c2["nodes"][0]["kind"] == orig_node_kind
    assert c2["nodes"][0]["kind"] != "MUTATED_KIND"


def test_evaluate_search_candidates_direct_engine_and_prepared_reuse():
    """evaluate_search_candidates reuses supplied engine_graph and prepared directly."""
    from scripts.research.rbcd_inputs import (
        inputs as rbcd_inputs,
    )
    from scripts.research.rbcd_inputs import (
        ranking_inputs as rbcd_ranking_inputs,
    )
    from src.engine.query import run_attack_query
    from src.engine.ranking.orchestration import evaluate_search_candidates

    graph, q = rbcd_inputs()
    payload, bindings = rbcd_ranking_inputs(graph, q)
    result = run_attack_query(q, graph)
    path = result.paths[0]
    actions = [
        bindings[
            (
                s.result.request.technique_id,
                s.result.request.actor,
                s.result.request.source,
                s.result.request.target,
            )
        ]
        for s in path.transition_history
    ]
    candidate = {
        "candidate_id": "cand_reuse_0",
        "target_asset_id": q["target"],
        "route_id": "route_0",
        "action_mapping": actions,
        "path_result": path,
    }

    prepared = graph.to_prepared()

    with patch.object(
        EngineGraph,
        "from_canonical",
        side_effect=AssertionError(
            "EngineGraph.from_canonical should not be called when engine_graph is supplied"
        ),
    ):
        ranked = evaluate_search_candidates(
            payload,
            [candidate],
            engine_graph=graph,
            prepared=prepared,
        )
        assert ranked is not None
        assert "roundtrip_result" in ranked


def test_deserialize_graph_with_mapping_payload():
    """deserialize_graph validates and returns mapping without requiring JSON string round-trip."""
    from scripts.research.rbcd_inputs import inputs as rbcd_inputs

    graph, _ = rbcd_inputs()
    canonical = graph.to_canonical()
    deserialized = deserialize_graph(canonical)
    assert deserialized["metadata"]["snapshot_id"] == canonical["metadata"]["snapshot_id"]
    assert len(deserialized["nodes"]) == len(canonical["nodes"])


def test_prepared_semantic_graph_multiedge_deterministic_ordering_and_distinct_metadata():
    """PreparedSemanticGraph.edges_between returns all multiedges in deterministic sorted order."""
    from src.engine.semantics.evaluator import PreparedSemanticGraph

    sid = "sha256:" + "0" * 64
    prov = [
        {
            "raw_file": "f.json",
            "collector": "c",
            "timestamp": "2026-10-01T00:00:00Z",
            "attribute": "a",
            "record_locator": "1",
            "snapshot_id": sid,
        }
    ]
    canonical = {
        "metadata": {
            "snapshot_id": sid,
            "created_at": "2026-10-01T00:00:00Z",
            "code_version": "test",
            "synthetic": True,
        },
        "nodes": [
            {
                "id": "SRC",
                "kind": "User",
                "label": "SRC",
                "domain": "TEST",
                "is_boundary": False,
                "enabled": True,
            },
            {
                "id": "TGT",
                "kind": "Computer",
                "label": "TGT",
                "domain": "TEST",
                "is_boundary": False,
                "enabled": True,
            },
        ],
        "edges": [
            {
                "id": "edge_b",
                "source": "SRC",
                "target": "TGT",
                "kind": "GenericAll",
                "weight": 2.0,
                "provenance": prov,
            },
            {
                "id": "edge_a",
                "source": "SRC",
                "target": "TGT",
                "kind": "WriteDacl",
                "weight": 1.0,
                "provenance": prov,
            },
        ],
        "assessments": [],
    }

    prepared = PreparedSemanticGraph(canonical)
    matched = prepared.edges_between("SRC", "TGT")
    assert len(matched) == 2
    # Verify deterministic sorting by id
    assert matched[0]["id"] == "edge_a"
    assert matched[0]["kind"] == "WriteDacl"
    assert matched[1]["id"] == "edge_b"
    assert matched[1]["kind"] == "GenericAll"


def test_materialized_query_run_reuses_engine_graph_without_reconstruction():
    """MaterializedQuery.run(graph) reuses engine_graph and prepared without from_canonical."""
    from scripts.research.rbcd_inputs import (
        inputs as rbcd_inputs,
    )
    from scripts.research.rbcd_inputs import (
        ranking_inputs as rbcd_ranking_inputs,
    )
    from src.engine.query import materialize_query

    graph, q = rbcd_inputs()
    packet, bindings = rbcd_ranking_inputs(graph, q)
    materialized = materialize_query(
        q,
        graph,
        action_bindings=bindings,
        ranking_query=packet,
    )

    with patch.object(
        EngineGraph,
        "from_canonical",
        side_effect=AssertionError(
            "EngineGraph.from_canonical should not be called in MaterializedQuery.run"
        ),
    ):
        result = materialized.run(graph)
        assert result.final_goal_reached
        assert len(result.paths) == 3


def test_engine_graph_edge_lookup_by_id_fast_path():
    """EngineGraph.edge uses indexed lookup and raises KeyError for unknown IDs."""
    import pytest

    from scripts.research.rbcd_inputs import inputs as rbcd_inputs

    graph, _ = rbcd_inputs()
    canonical = graph.to_canonical()
    first_edge_id = canonical["edges"][0]["id"]

    edge_record = graph.edge(first_edge_id)
    assert edge_record["id"] == first_edge_id

    # Mutating returned record does not mutate internal cache
    edge_record["weight"] = 99999.0
    fresh_record = graph.edge(first_edge_id)
    assert fresh_record["weight"] != 99999.0

    # Non-existent edge raises KeyError
    with pytest.raises(KeyError, match="unknown canonical edge ID"):
        graph.edge("nonexistent_edge_id")


def test_graph_digest_skips_contract_validation():
    """graph_digest computes hash without calling validate_graph."""
    import scripts.check_contract as contract_mod
    from scripts.research.rbcd_inputs import inputs as rbcd_inputs
    from src.parser.snapshot_facts import graph_digest

    graph, _ = rbcd_inputs()
    canonical = graph.to_canonical()

    with patch.object(
        contract_mod,
        "validate_graph",
        side_effect=AssertionError("validate_graph should not be called during graph_digest"),
    ):
        digest = graph_digest(canonical)
        assert digest.startswith("sha256:")
