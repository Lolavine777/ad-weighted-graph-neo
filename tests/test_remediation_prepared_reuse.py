"""Runtime-only views must preserve evidence binding and baseline isolation."""

from unittest.mock import patch

import pytest
from test_remediation_executor import finite, read

from scripts.research.asrep_inputs import V, inputs
from src.engine.query import materialize_query, run_attack_query
from src.engine.remediation import (
    _check_edits,
    _digest,
    effective_scenario,
    extract_witness,
    prepare_baseline,
    request_for_baseline,
)
from src.engine.semantics import FactOrigin
from src.parser.snapshot_facts import SnapshotFacts


def scenario():
    graph, query = inputs()
    baseline = prepare_baseline(
        graph, [{"source_id": "one", "goal_id": "host", "query": query}], run_id="reuse"
    )
    material = materialize_query(query, graph)
    return graph, query, baseline, material


def test_runtime_overlay_reuses_only_owned_static_views_and_preserves_provenance():
    graph, baseline = finite()
    material = materialize_query(read("alice-query.json"), graph)
    key, original = next(
        (k, f) for k, f in material.runtime_context.facts.items() if k[0] == "admin_channel"
    )
    edit = {
        "edit_id": "channel",
        "catalog_entry_id": "admin-channel",
        "kind": "runtime_fact_replace",
        "key": dict(
            predicate=key[0],
            subject=key[1],
            target=key[2],
            authentication_context=material.runtime_context.authentication_context,
            binding_id=None,
        ),
        "expected_before": True,
        "after": False,
        "declaration": "counterfactual_intervention",
        "evidence_refs": ["synthetic://reuse"],
        "rationale": "Declared counterfactual, not a new observation",
    }
    request = request_for_baseline(baseline, [edit], request_id="runtime-reuse")
    owned = graph.to_prepared()
    before = graph.to_canonical()
    with patch.object(graph, "to_canonical", side_effect=AssertionError("unnecessary graph copy")):
        effective, after, prepared, active = effective_scenario(request, graph, material)
    assert effective is graph and prepared is owned and active == ["channel"]
    assert prepared.snapshot_facts is graph.snapshot_facts
    changed = after.runtime_context.facts[key]
    assert changed.value is False and changed.origin == FactOrigin.BLOCKED_EVIDENCE
    assert changed.assumption_metadata["origin"] == "counterfactual_intervention"
    assert changed.provenance_reference == "intervention:runtime-reuse/channel"
    assert material.runtime_context.facts[key] == original and original.value is True
    assert graph.to_canonical() == before


def test_structural_overlay_without_snapshot_facts_cannot_reuse_baseline_graph():
    graph, baseline = finite()
    assert graph.snapshot_facts is None
    request = request_for_baseline(
        baseline, read("request-acl-v1.1.json")["edits"], request_id="structural"
    )
    material = materialize_query(read("alice-query.json"), graph)
    with patch.object(graph, "edges", side_effect=AssertionError("whole-edge scan")):
        _check_edits(request, graph, [material])
    effective, _, prepared, _ = effective_scenario(request, graph, material)
    assert effective is not graph and prepared is not graph.to_prepared()
    edge_id = request["edits"][0]["edge_id"]
    assert graph.edge(edge_id)
    with pytest.raises(KeyError):
        effective.edge(edge_id)


def test_static_fact_overlay_is_separate_and_remains_bound_to_its_projection():
    graph, _, baseline, material = scenario()
    fact = graph.snapshot_facts.lookup(V, "dontreqpreauth")
    assert fact.value is True
    edit = {
        "edit_id": "preauth",
        "catalog_entry_id": "asrep-preauth",
        "kind": "snapshot_fact_replace",
        "subject": V,
        "name": "dontreqpreauth",
        "expected_before": True,
        "after": False,
        "evidence_digest": _digest(fact.evidence),
        "declaration": "counterfactual_intervention",
        "evidence_refs": ["synthetic://reuse"],
        "rationale": "Enable preauthentication in this counterfactual",
    }
    request = request_for_baseline(baseline, [edit], request_id="static")
    _check_edits(request, graph, [material])
    effective, _, prepared, _ = effective_scenario(request, graph, material)
    assert effective is not graph and prepared is not graph.to_prepared()
    assert prepared.snapshot_facts.lookup(V, "dontreqpreauth").value is False
    assert graph.snapshot_facts.lookup(V, "dontreqpreauth").value is True
    changed = effective.to_canonical()
    changed["nodes"][0]["label"] += "-foreign-projection"
    with pytest.raises(ValueError, match="binding mismatch"):
        prepared.snapshot_facts.validate_binding(changed)


def test_witness_extraction_reuses_bound_prepared_without_copy_or_rebinding():
    graph, query, _, material = scenario()
    path = run_attack_query(query, graph).paths[0]
    graph.to_prepared()
    with (
        patch.object(graph, "to_canonical", side_effect=AssertionError("unnecessary graph copy")),
        patch.object(
            SnapshotFacts, "validate_binding", side_effect=AssertionError("unnecessary rebinding")
        ),
    ):
        witness = extract_witness(
            path,
            material,
            graph,
            comparison_scope_digest="sha256:" + "0" * 64,
            source_id="one",
            goal_id="host",
        )
    assert witness["semantic_program"]
