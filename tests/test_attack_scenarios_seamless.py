"""Trace mapper correctness with invented raw records; real run is an explicit CLI gate."""

import json
from copy import deepcopy

import pytest

from scripts.research.attack_scenarios import DEFAULT, load_suite
from scripts.research.attack_scenarios_seamless import load_binding, raw_edge_trace
from src.data.manifest import generate_manifest, raw_file_reference


def test_accepted_integration_pins_are_current():
    assert load_binding()["terminal_predicate"] == "admin_control(target)"


def trace_fixture(tmp_path):
    suite = load_suite()
    binding = suite["graphs"]["acl-auth-host"]
    aliases = binding["aliases"]
    graph = json.loads((DEFAULT.parent / binding["path"]).read_text(encoding="utf-8"))
    raw = tmp_path / "raw"
    raw.mkdir()
    rows = [
        (
            "users.json",
            "users",
            aliases["Bob"],
            "Aces",
            {"PrincipalSID": aliases["Helpdesk"], "RightName": "WriteDacl"},
        ),
        (
            "groups.json",
            "groups",
            aliases["Helpdesk"],
            "Members",
            {"MemberId": aliases["Alice"], "MemberType": "User"},
        ),
    ]
    locators, edges = [], []
    for filename, envelope, target, field, entry in rows:
        payload = {envelope: [{"ObjectIdentifier": target, field: [entry]}]}
        (raw / filename).write_text(json.dumps(payload), encoding="utf-8")
        source = entry.get("PrincipalSID", entry.get("MemberId"))
        kind = entry.get("RightName", "MemberOf")
        edge = next(
            e
            for e in graph["edges"]
            if (e["source"], e["target"], e["kind"]) == (source, target, kind)
        )
        edges.append(edge)
        locators.append(f"{filename}#/{envelope}/0/{field}/0")
    manifest = generate_manifest(
        raw,
        dataset_id="synthetic-golden-trace",
        collector_name="synthetic",
        collector_version="1.0",
        collected_at="2026-10-05T00:00:00Z",
    )
    for edge, row in zip(edges, rows, strict=True):
        edge["provenance"] = [
            {
                "raw_file": raw_file_reference(manifest, row[0]),
                "record_id": row[2],
                "attribute": row[3] + "[]",
            }
        ]
    candidate = {
        "structural_routes": [
            {
                "edge_ids": [e["id"]],
                "node_ids": [e["source"], e["target"]],
                "provenance_locators": [locator],
            }
            for e, locator in zip(edges, locators, strict=True)
        ]
    }
    return graph, candidate, raw, manifest


def test_raw_locator_to_canonical_acl_and_membership_trace(tmp_path):
    graph, candidate, raw, manifest = trace_fixture(tmp_path)
    baseline = deepcopy(graph)
    trace = raw_edge_trace(graph, candidate, raw, manifest)
    assert [r["relationship"] for r in trace] == ["WriteDacl", "MemberOf"]
    assert graph == baseline


@pytest.mark.parametrize("defect", ["direction", "locator", "provenance", "raw-tamper"])
def test_trace_rejects_unproven_raw_or_canonical_binding(tmp_path, defect):
    graph, candidate, raw, manifest = trace_fixture(tmp_path)
    route = candidate["structural_routes"][0]
    edge = next(e for e in graph["edges"] if e["id"] == route["edge_ids"][0])
    if defect == "direction":
        route["node_ids"].reverse()
    elif defect == "locator":
        route["provenance_locators"][0] = "groups.json#/groups/0/Members/0"
    elif defect == "provenance":
        edge["provenance"] = []
    else:
        (raw / "users.json").write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError):
        raw_edge_trace(graph, candidate, raw, manifest)
