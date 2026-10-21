"""Focused invariants for the read-only #82 handoff exporter."""

import json

import pytest

from scripts.research.export_legacy_reconciliation_baseline import (
    digest,
    encoded,
    read_query_package,
    relationship_rows_for_export,
    write_json,
)
from scripts.research.trace_project_raw_locator import record_locators


def test_relationship_rows_keep_direction_kind_and_multiplicity():
    rows = [
        {"source": "a", "kind": "MemberOf", "target": "b"},
        {"source": "a", "kind": "MemberOf", "target": "b"},
        {"source": "b", "kind": "MemberOf", "target": "a"},
        {"source": "a", "kind": "GenericAll", "target": "b"},
    ]
    nodes = {"A": {"is_boundary": True}, "B": {"is_boundary": False}}
    result = relationship_rows_for_export(rows, {"a": "A", "b": "B"}, nodes)
    assert [
        (r["source_identity"], r["kind"], r["target_identity"], r["stored_multiplicity"])
        for r in result
    ] == [
        ("A", "GenericAll", "B", 1),
        ("A", "MemberOf", "B", 2),
        ("B", "MemberOf", "A", 1),
    ]
    assert result[0]["source_boundary"] is True
    assert result[2]["target_boundary"] is True


def test_json_digest_is_deterministic_utf8(tmp_path):
    first = {"đối_chiếu": 2, "a": 1}
    second = {"a": 1, "đối_chiếu": 2}
    assert encoded(first) == encoded(second)
    path = tmp_path / "export.json"
    assert write_json(path, first) == digest(encoded(second))
    assert json.loads(path.read_text(encoding="utf-8")) == second
    assert b"\xc4\x91" in path.read_bytes()


def test_query_package_is_read_only_and_rejects_mutation(tmp_path):
    source = "reports/research/issue-82-legacy-reconciliation-queries.json"
    queries = read_query_package(__import__("pathlib").Path(source))
    assert {
        "all_nodes",
        "all_relationships",
        "multiplicity",
        "memberof",
        "genericall",
        "boundary_principals",
        "exact_identity",
    } <= set(queries)
    package = {
        "schema_version": 1,
        "read_only": True,
        "queries": {"bad": "MATCH (n) DETACH DELETE n"},
    }
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(package), encoding="utf-8")
    with pytest.raises(ValueError, match="write token"):
        read_query_package(path)


def test_raw_locator_preserves_duplicate_record_representations():
    raw = {"groups": [{"ObjectIdentifier": "A"}, {"ObjectIdentifier": "A"}], "meta": {}}
    assert record_locators(raw, "A", "groups.json") == [
        "groups.json#/groups/0",
        "groups.json#/groups/1",
    ]
    assert record_locators(raw, "B", "groups.json") == []
