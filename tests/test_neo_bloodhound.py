"""Fixed cohorts and comparison boundaries without a BloodHound stand-in."""

import json
from unittest.mock import MagicMock

import pytest
from test_engine import ACTOR, GROUP, HOST, _edge
from test_exposure import BOB
from test_exposure import graph as graph_fixture

from scripts import neo_bloodhound as comparison
from src.engine.graph import EngineGraph


@pytest.fixture
def graph():
    raw = graph_fixture.__wrapped__().to_canonical()
    raw["edges"].append(_edge(HOST, BOB, "HasSession"))
    return EngineGraph.from_canonical(raw)


def test_cohort_does_not_depend_on_reachability(graph, tmp_path):
    snapshot = tmp_path / "snapshot.json"
    snapshot.write_text("transport bytes")
    baseline = comparison.prepare_dataset(graph, snapshot, "identity", tmp_path / "native")
    raw = graph.to_canonical()
    raw["edges"] = [e for e in raw["edges"] if e["source"] != ACTOR]
    changed = comparison.prepare_dataset(
        EngineGraph.from_canonical(raw), snapshot, "identity", tmp_path / "native"
    )
    assert baseline["pairs"] == changed["pairs"]
    assert baseline["request"] == changed["request"]
    assert {p["source_profile"] for p in baseline["pairs"]} == {
        "user_usable_identity",
        "computer_usable_identity",
    }
    assert "--max-paths" in baseline["neo_argv"]


def test_session_coverage_has_host_control_not_machine_identity(graph, tmp_path):
    snapshot = tmp_path / "snapshot.json"
    snapshot.write_text("transport bytes")
    pack = comparison.prepare_dataset(
        graph, snapshot, "host-compromise", tmp_path / "native", session_coverage=True
    )
    assert {p["source"] for p in pack["pairs"]} == {HOST}
    assert {p["source_profile"] for p in pack["pairs"]} == {"computer_control_admin"}
    assert pack["selection_seed"] is None
    assert pack["input_coverage"]["computer_initial_capability"] == "local_admin_only"
    assert "HasSession" in pack["pairs"][0]["structural_cypher"]


def test_cypher_scope_and_disabled_control_are_distinct():
    plain = comparison.path_query(ACTOR, GROUP, "identity")
    enabled = comparison.path_query(ACTOR, GROUP, "identity", enabled_users=True)
    assert "HasSession" not in plain and "AdminTo" not in plain
    assert "enabled" not in plain and "coalesce(n.enabled, true)" in enabled
    assert "shortestPath" in plain and "*1..12" in plain
    assert comparison.literal("a'b\\c") == "'a\\'b\\\\c'"


def test_boundary_domains_are_not_selected(graph, tmp_path):
    snapshot = tmp_path / "snapshot.json"
    snapshot.write_text("transport bytes")
    raw = graph.to_canonical()
    raw["nodes"].append(
        {
            "id": "S-1-5-21-999-888-777",
            "kind": "Domain",
            "domain": "FOREIGN.TEST",
            "label": "FOREIGN.TEST",
            "is_boundary": True,
        }
    )
    pack = comparison.prepare_dataset(
        EngineGraph.from_canonical(raw), snapshot, "identity", tmp_path / "native"
    )
    assert pack["domain_sid"] != "S-1-5-21-999-888-777"
    assert "--domain-sid" in pack["neo_argv"]
    with pytest.raises(ValueError, match="different domain"):
        comparison.prepare_dataset(
            graph, snapshot, "identity", tmp_path / "native", expected_domain="another-domain"
        )
    raw["nodes"][-1]["is_boundary"] = False
    with pytest.raises(ValueError, match="exactly one"):
        comparison.prepare_dataset(
            EngineGraph.from_canonical(raw), snapshot, "identity", tmp_path / "native"
        )


def test_existing_output_is_never_overwritten(tmp_path):
    with pytest.raises(FileExistsError):
        comparison.main(
            [
                "--seamless-snapshot",
                "missing",
                "--wraith-snapshot",
                "missing",
                "--output-dir",
                str(tmp_path),
            ]
        )


def test_raw_failure_cannot_prepare_or_search(monkeypatch, tmp_path):
    monkeypatch.setattr(comparison, "load_manifest", lambda _: {})
    monkeypatch.setattr(comparison, "verify_manifest", lambda *args: ["hash mismatch"])
    prepare = MagicMock()
    monkeypatch.setattr(comparison, "prepare_dataset", prepare)
    output = tmp_path / "not-created"
    with pytest.raises(ValueError, match="raw integrity"):
        comparison.main(
            [
                "--seamless-snapshot",
                "missing",
                "--wraith-snapshot",
                "missing",
                "--output-dir",
                str(output),
            ]
        )
    prepare.assert_not_called()
    assert not output.exists()


def test_preparation_never_marks_comparison_or_parity_complete(monkeypatch, tmp_path):
    snapshot = tmp_path / "snapshot.json"
    snapshot.write_text("snapshot")
    graph = MagicMock(metadata={"snapshot_id": "verified"})
    monkeypatch.setattr(comparison.EngineGraph, "from_snapshot", lambda _: graph)
    monkeypatch.setattr(
        comparison, "load_manifest", lambda _: {"snapshot_id": "verified", "files": []}
    )
    monkeypatch.setattr(comparison, "verify_manifest", lambda *args: [])
    monkeypatch.setattr(comparison.shutil, "which", lambda _: None)
    monkeypatch.setattr(
        comparison,
        "prepare_dataset",
        lambda *args, **kwargs: {
            "pairs": [],
            "neo_argv": ["echo", "not executed"],
            "parity_cypher": [],
        },
    )
    output = tmp_path / "pack"
    assert (
        comparison.main(
            [
                "--seamless-snapshot",
                str(snapshot),
                "--wraith-snapshot",
                str(snapshot),
                "--output-dir",
                str(output),
            ]
        )
        == 0
    )
    pack = json.loads((output / "comparison.json").read_text())
    assert pack["phase"] == "prepared_not_compared"
    assert pack["bloodhound"]["status"] == "not_run"
    assert pack["bloodhound"]["graph_parity"] == "not_checked"
    assert pack["bloodhound"]["docker_cli"] == "missing"
