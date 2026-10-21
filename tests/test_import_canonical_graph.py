"""The Neo4j importer must state its structural projection boundary."""

from __future__ import annotations

import sys

import pytest

from scripts.import_canonical_graph import main, projection_manifest


def test_projection_manifest_reports_excluded_assessments():
    graph = {
        "metadata": {"contract_version": "1.3.0", "snapshot_id": "sha256:" + "a" * 64},
        "assessments": [
            {"id": "first", "status": "unknown"},
            {"id": "second", "status": "rejected"},
        ],
    }
    report = projection_manifest(graph, "b" * 64)
    assert report["projection"] == "canonical_nodes_and_edges"
    assert report["assessments_in_graph"] == 2
    assert report["assessments_in_neo4j"] == 0
    assert report["assessment_statuses"] == {"rejected": 1, "unknown": 1}
    assert len(report["assessments_sha256"]) == 64


def test_import_requires_explicit_structural_projection(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["import_canonical_graph.py", "graph.json"])
    with pytest.raises(SystemExit, match="2"):
        main()
