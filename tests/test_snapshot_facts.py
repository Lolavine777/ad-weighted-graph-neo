"""Synthetic snapshot evidence and actual materialization/query boundary coverage."""

import copy
import json
from dataclasses import FrozenInstanceError
from itertools import permutations

import pytest

from src.engine import query, search
from src.engine.graph import EngineGraph
from src.engine.semantics.evaluator import PreparedSemanticGraph
from src.parser import DirectGraphBuilder, ErrorPolicy, IdentityNormalizer, RawRecord
from src.parser.reconciliation import ReconciliationConflictError
from src.parser.snapshot_facts import deserialize_snapshot, serialize_snapshot

SNAPSHOT = "sha256:" + "a" * 64
USER = "S-1-5-21-1000-2000-3000-1101"
TARGET = "S-1-5-21-1000-2000-3000-1102"


def raw(properties, *, identifier=USER, locator="#/users/0", extra=None):
    return RawRecord(
        "User",
        {
            "ObjectIdentifier": identifier,
            "Properties": {"name": "SYNTHETIC", "domain": "EXAMPLE.TEST", **properties},
            **(extra or {}),
        },
        {
            "raw_file": "snapshot:" + "a" * 64 + "/users.json",
            "snapshot_id": SNAPSHOT,
            "collector": "synthetic/1",
            "timestamp": "2026-10-07T00:00:00Z",
            "record_locator": locator,
            "record_id": identifier,
            "time_provenance": "observed",
        },
    )


def builder():
    return DirectGraphBuilder(
        metadata={
            "snapshot_id": SNAPSHOT,
            "created_at": "2026-10-07T00:00:00Z",
            "code_version": "synthetic/215",
            "synthetic": True,
        }
    )


def materialize(records):
    normalized = IdentityNormalizer().normalize_records(records)
    graph, facts = builder().build_snapshot(normalized)
    return normalized, graph, facts


@pytest.mark.parametrize(
    "value,status",
    [
        (True, "known"),
        (False, "known"),
        (None, "unknown"),
        ("false", "unknown"),
        (0, "unknown"),
        ({}, "unknown"),
    ],
)
def test_boolean_evidence_is_strict(value, status):
    _, graph, facts = materialize([raw({"hasspn": value, "dontreqpreauth": value})])
    for name in ("has_spn", "dontreqpreauth"):
        fact = facts.lookup(USER, name)
        assert fact.status == status
        assert fact.value is (value if status == "known" else None)
        assert fact.evidence[0].classification == "collector_normalized"
        assert fact.evidence[0].provenance["attribute"].startswith("Properties.")
        assert fact.evidence[0].provenance["snapshot_id"] == graph["metadata"]["snapshot_id"]
        assert fact.evidence[0].provenance["record_locator"] == "#/users/0"


@pytest.mark.parametrize(
    "values,expected",
    [
        ([], ()),
        (["HTTP/synthetic.test"], ("HTTP/synthetic.test",)),
        (None, None),
        ("HTTP/host", None),
        ([False], None),
        ([""], None),
        (["   "], None),
    ],
)
def test_spn_values_empty_and_malformed(values, expected):
    _, _, facts = materialize([raw({"serviceprincipalnames": values})])
    fact = facts.lookup(USER, "service_principal_names")
    assert fact.value == expected
    assert fact.status == ("unknown" if expected is None else "known")
    assert facts.lookup(USER, "has_spn").status == "unknown"
    assert not facts.lookup(USER, "has_spn").evidence


def test_duplicate_origins_empty_precedence_determinism_and_no_mutation():
    records = [
        raw({"hasspn": True, "serviceprincipalnames": ["HTTP/synthetic.test"]}),
        raw({"hasspn": True, "serviceprincipalnames": []}, locator="#/users/1"),
        raw({}, locator="#/users/2"),
    ]
    before = copy.deepcopy(records)
    payloads = []
    for ordered in permutations(records):
        normalized, graph, facts = materialize(ordered)
        canonical = copy.deepcopy(graph)
        normalized_before = copy.deepcopy(normalized)
        assert graph == builder().build(normalized)
        fact = facts.lookup(USER, "has_spn")
        assert fact.value is True and len(fact.evidence) == 2
        assert {e.provenance["record_locator"] for e in fact.evidence} == {"#/users/0", "#/users/1"}
        spns = facts.lookup(USER, "service_principal_names")
        assert spns.value == ("HTTP/synthetic.test",) and len(spns.evidence) == 2
        with pytest.raises(TypeError):
            spns.value[0] = "changed"
        with pytest.raises(TypeError):
            fact.evidence[0].provenance["collector"] = "changed"
        with pytest.raises(FrozenInstanceError):
            fact.value = False
        assert normalized == normalized_before and graph == canonical
        payloads.append(serialize_snapshot(graph, facts))
    assert len(set(payloads)) == 1 and records == before


@pytest.mark.parametrize(
    "field,left,right",
    [
        ("hasspn", True, False),
        ("dontreqpreauth", False, True),
        ("serviceprincipalnames", ["HTTP/a"], ["HTTP/b"]),
    ],
)
def test_conflict_is_fatal_in_either_order(field, left, right):
    records = [raw({field: left}), raw({field: right}, locator="#/users/1")]
    for ordered in permutations(records):
        with pytest.raises(ReconciliationConflictError):
            materialize(ordered)


def test_canonical_scope_ids_are_isolated():
    records = [
        raw(
            {"hasspn": True},
            identifier="S-1-5-18",
            extra={"scope": {"kind": "host", "guid": "10000000-0000-4000-8000-000000000001"}},
        ),
        raw(
            {"hasspn": False},
            identifier="S-1-5-18",
            locator="#/users/1",
            extra={"scope": {"kind": "host", "guid": "10000000-0000-4000-8000-000000000002"}},
        ),
    ]
    normalized, _, facts = materialize(records)
    assert len({r.id for r in normalized}) == 2
    assert [facts.lookup(r.id, "has_spn").value for r in normalized] == [True, False]
    for alias in ("SYNTHETIC", "S-1-5-18", "#/users/0"):
        assert facts.lookup(alias, "has_spn").status == "unknown"


def test_extraction_filters_skipped_nodes_and_copies_source_values():
    records = [
        raw({"hasspn": True, "serviceprincipalnames": ["HTTP/synthetic.test"]}),
        raw(
            {"hasspn": False},
            identifier=TARGET,
            locator="#/users/1",
            extra={
                "Aces": [
                    {
                        "PrincipalSID": "unresolvable",
                        "PrincipalType": "User",
                        "RightName": "ForceChangePassword",
                    }
                ]
            },
        ),
    ]
    normalized = IdentityNormalizer().normalize_records(records)
    graph, facts = builder().build_snapshot(normalized, error_policy=ErrorPolicy.SKIP_RECORD)
    assert {n["id"] for n in graph["nodes"]} == {USER}
    assert facts.lookup(TARGET, "has_spn").status == "unknown"
    source = normalized[0].raw_representations[0]
    source.data["Properties"]["serviceprincipalnames"].append("HTTP/changed.test")
    source.provenance["collector"] = "changed"
    assert facts.lookup(USER, "service_principal_names").value == ("HTTP/synthetic.test",)
    assert facts.lookup(USER, "has_spn").evidence[0].provenance["collector"] == "synthetic/1"


def test_seamless_probe_explicitly_skips_without_private_inputs(tmp_path, capsys):
    from scripts.research.snapshot_facts_probe import main

    assert main(["--raw-dir", str(tmp_path / "absent"), "--code-version", "synthetic-test"]) == 2
    assert json.loads(capsys.readouterr().out)["disposition"] == "SKIP"


def test_snapshot_transport_binding_and_enabled_authority():
    _, graph, facts = materialize([raw({"enabled": False, "hasspn": True})])
    envelope = serialize_snapshot(graph, facts)
    restored, view = deserialize_snapshot(envelope)
    assert restored == graph and view == facts
    engine = EngineGraph.from_snapshot(envelope)
    assert engine.to_canonical() == graph
    assert engine.node(USER)["enabled"] is False
    assert engine.snapshot_facts.lookup(USER, "has_spn").value is True
    assert EngineGraph.from_canonical(graph).snapshot_facts is None
    with pytest.raises(KeyError):
        view.lookup(USER, "enabled")
    for field in ("nodes", "metadata"):
        altered = json.loads(envelope)
        if field == "nodes":
            altered["graph"][field][0]["label"] = "changed"
        else:
            altered["graph"][field]["snapshot_id"] = "sha256:" + "b" * 64
        with pytest.raises(ValueError, match="do not match"):
            EngineGraph.from_snapshot(json.dumps(altered))
    altered = json.loads(envelope)
    altered["facts"][0]["evidence"][0]["provenance"]["snapshot_id"] = "sha256:" + "b" * 64
    with pytest.raises(ValueError, match="another snapshot"):
        EngineGraph.from_snapshot(json.dumps(altered))


def test_binding_survives_engine_collection_order_but_detects_edge_evidence_changes():
    normalized, graph, facts = materialize(
        [
            raw({"hasspn": True}),
            raw(
                {},
                identifier=TARGET,
                locator="#/users/1",
                extra={
                    "Aces": [
                        {"PrincipalSID": USER, "PrincipalType": "User", "RightName": "GenericAll"},
                        {"PrincipalSID": USER, "PrincipalType": "User", "RightName": "WriteDacl"},
                    ]
                },
            ),
        ]
    )
    reordered = copy.deepcopy(graph)
    reordered["nodes"].reverse()
    reordered["edges"].reverse()
    engine = EngineGraph.from_canonical(reordered, snapshot_facts=facts)
    prepared = PreparedSemanticGraph(engine.to_canonical(), snapshot_facts=engine.snapshot_facts)
    assert prepared.snapshot_facts.lookup(USER, "has_spn").value is True
    assert graph == builder().build(normalized)
    altered = copy.deepcopy(graph)
    altered["edges"][0]["provenance"][0]["collector"] = "altered"
    with pytest.raises(ValueError, match="do not match"):
        EngineGraph.from_canonical(altered, snapshot_facts=facts)


@pytest.mark.integration
def test_fact_consumer_receives_evidence_through_actual_query_search_boundary(monkeypatch):
    _, graph, facts = materialize(
        [
            raw({"hasspn": False}),
            raw(
                {"hasspn": True, "dontreqpreauth": False},
                identifier=TARGET,
                locator="#/users/1",
                extra={
                    "Aces": [
                        {
                            "PrincipalSID": USER,
                            "PrincipalType": "User",
                            "RightName": "ForceChangePassword",
                        }
                    ]
                },
            ),
        ]
    )
    engine = EngineGraph.from_snapshot(serialize_snapshot(graph, facts))
    observed = []
    original = search.evaluate_semantic_transition

    def consumer(semantic_graph, state, request, context, catalog):
        assert isinstance(semantic_graph, PreparedSemanticGraph)
        observed.append(semantic_graph.snapshot_facts.lookup(request.target, "has_spn"))
        assert semantic_graph.snapshot_facts.lookup(request.target, "dontreqpreauth").value is False
        assert not context.facts  # Static evidence never enters runtime assumptions.
        return original(semantic_graph, state, request, context, catalog)

    monkeypatch.setattr(search, "evaluate_semantic_transition", consumer)
    materialized = query.materialize_query(
        {
            "source_foothold": USER,
            "initial_state": {"control": [USER]},
            "target": TARGET,
            "target_goal": {"target": TARGET, "required_state": {"control": [TARGET]}},
        },
        engine,
    )
    initial = materialized.initial_attack_state
    runtime = materialized.runtime_context
    result = materialized.search(engine)
    assert result.attempts and observed and all(f.value is True for f in observed)
    assert materialized.initial_attack_state == initial and materialized.runtime_context == runtime
    assert engine.to_canonical() == graph
