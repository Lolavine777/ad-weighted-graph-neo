"""Acceptance coverage for the normalized synthetic graph in issue #9."""

import copy
import hashlib
import json
from pathlib import Path

import networkx as nx
import pytest
import yaml

from scripts.check_contract import validate_graph

ROOT = Path(__file__).resolve().parents[1]
PRINCIPALS = {"User", "Group", "Computer"}


@pytest.fixture(scope="module")
def fixture():
    return json.loads((ROOT / "data/samples/m1-fixtures.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def topology(fixture):
    graph = nx.MultiDiGraph()
    graph.add_nodes_from((node["id"], node) for node in fixture["nodes"])
    for edge in fixture["edges"]:
        graph.add_edge(edge["source"], edge["target"], key=edge["id"], kind=edge["kind"])
    return graph


def test_m1_fixture_matches_contract(fixture):
    contract = yaml.safe_load((ROOT / "configs/contract.yml").read_text(encoding="utf-8"))
    validate_graph(fixture, contract)
    assert fixture["metadata"]["synthetic"] is True
    assert {edge["kind"] for edge in fixture["edges"]} == set(contract["edge_kinds"])


def test_m1_fixture_size(fixture):
    assert 15 <= len(fixture["nodes"]) <= 20
    assert 25 <= len(fixture["edges"]) <= 30


def test_parallel_relations_are_preserved(fixture, topology):
    assert topology.number_of_edges() == len(fixture["edges"])
    assert any(
        len({edge["kind"] for edge in edges.values()}) > 1
        for targets in topology.adj.values()
        for edges in targets.values()
    )


def test_group_membership_cycle_has_distinct_nodes(fixture):
    groups = {node["id"] for node in fixture["nodes"] if node["kind"] == "Group"}
    membership = nx.DiGraph()
    membership.add_edges_from(
        (edge["source"], edge["target"])
        for edge in fixture["edges"]
        if edge["kind"] == "MemberOf" and edge["source"] in groups and edge["target"] in groups
    )
    assert any(len(component) > 1 for component in nx.strongly_connected_components(membership))


def test_orphan_node_is_preserved(fixture, topology):
    assert topology.number_of_nodes() == len(fixture["nodes"])
    assert list(nx.isolates(topology))


@pytest.mark.parametrize(
    ("kind", "sources", "targets"),
    [
        ("MemberOf", PRINCIPALS, {"Group"}),
        ("AdminTo", PRINCIPALS, {"Computer"}),
        ("CanRDP", PRINCIPALS, {"Computer"}),
        ("CanPSRemote", PRINCIPALS, {"Computer"}),
        ("HasSession", {"Computer"}, {"User"}),
        ("GenericAll", PRINCIPALS, PRINCIPALS | {"Domain", "OU", "GPO"}),
        ("WriteDacl", PRINCIPALS, PRINCIPALS | {"Domain", "OU", "GPO"}),
        ("ForceChangePassword", PRINCIPALS, {"User"}),
    ],
)
def test_fixture_edge_directions(fixture, kind, sources, targets):
    nodes = {node["id"]: node for node in fixture["nodes"]}
    edges = [edge for edge in fixture["edges"] if edge["kind"] == kind]
    assert edges, f"Missing coverage for {kind}"
    for edge in edges:
        assert nodes[edge["source"]]["kind"] in sources, edge["id"]
        assert nodes[edge["target"]]["kind"] in targets, edge["id"]


def test_disabled_account_can_retain_positive_outgoing_edge(fixture):
    """Issue #80: disabled state must not imply structural pruning."""
    candidate = copy.deepcopy(fixture)
    source = next(node["id"] for node in candidate["nodes"] if node.get("enabled") is False)
    target = next(node["id"] for node in candidate["nodes"] if node["kind"] == "Group")
    kind = "MemberOf"
    payload = json.dumps([source, target, kind], separators=(",", ":"), ensure_ascii=False)
    edge_id = f"sha256:{hashlib.sha256(payload.encode('utf-8')).hexdigest()}"
    candidate["edges"].append(
        {
            "id": edge_id,
            "source": source,
            "target": target,
            "kind": kind,
            "weight": 1.0,
            "provenance": [
                {
                    "raw_file": "synthetic://issue-80-disabled-outgoing.json",
                    "collector": "synthetic-fixture/1.0",
                    "timestamp": "2026-09-22T00:00:00Z",
                    "evidence_type": "positive",
                    "record_id": "issue80:disabled:memberof",
                    "attribute": "synthetic:MemberOf",
                }
            ],
        }
    )

    contract = yaml.safe_load((ROOT / "configs/contract.yml").read_text(encoding="utf-8"))
    validate_graph(candidate, contract)

    graph = nx.MultiDiGraph()
    graph.add_nodes_from((node["id"], node) for node in candidate["nodes"])
    for edge in candidate["edges"]:
        graph.add_edge(edge["source"], edge["target"], key=edge["id"], kind=edge["kind"])

    assert graph.nodes[source]["enabled"] is False
    assert graph.out_degree(source) > 0
    assert any(
        edge["source"] == source and edge["kind"] == "MemberOf" for edge in candidate["edges"]
    )


def test_fixture_has_no_self_loops(topology):
    assert nx.number_of_selfloops(topology) == 0


def test_repeated_evidence_is_aggregated(fixture):
    assert any(len(edge["provenance"]) > 1 for edge in fixture["edges"])
