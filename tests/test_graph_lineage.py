"""Canonical ordered lineage, migration, validation, and round-trip coverage."""

from __future__ import annotations

import copy
import json
from itertools import permutations
from pathlib import Path

import pytest
import yaml

from scripts.check_contract import canonical_edge_id, provenance_reference, validate_graph
from src.parser import (
    DirectGraphBuilder,
    IdentityNormalizer,
    RawRecord,
    deserialize_graph,
    serialize_graph,
)

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = "sha256:" + "b" * 64
DOMAIN = "EXAMPLE.TEST"
CREATED = "2026-09-23T00:00:00Z"
USER = "S-1-5-21-1000-2000-3000-1101"
HOST = "S-1-5-21-1000-2000-3000-3101"
HOST_B = "S-1-5-21-1000-2000-3000-3102"
GROUP_A = "S-1-5-21-1000-2000-3000-2101"
GROUP_B = "S-1-5-21-1000-2000-3000-2102"
ADMINISTRATORS = "S-1-5-32-544"


def _raw(kind: str, data: dict, identifier: str) -> RawRecord:
    return RawRecord(
        kind=kind,
        data={
            "ObjectIdentifier": identifier,
            "Properties": {"name": identifier, "domain": DOMAIN},
            **data,
        },
        provenance={
            "raw_file": f"snapshot:{SNAPSHOT.removeprefix('sha256:')}/{kind.lower()}.json",
            "collector": "synthetic/92",
            "timestamp": "2026-09-22T00:00:00Z",
            "snapshot_id": SNAPSHOT,
            "record_id": identifier,
        },
    )


def _records(*, groups: tuple[str, ...] = (), gpo: dict | None = None):
    local_groups = [
        {
            "ObjectIdentifier": f"HOST-{ADMINISTRATORS}",
            "Results": [{"ObjectIdentifier": group} for group in groups],
        }
    ]
    host_data = {"LocalGroups": local_groups}
    if gpo is not None:
        host_data["GPOAccess"] = [gpo]
    records = [_raw("Computer", host_data, HOST)]
    records.extend(
        _raw(
            "Group",
            {"Members": [{"MemberId": USER, "MemberType": "User"}]},
            group,
        )
        for group in groups
    )
    records.append(_raw("User", {}, USER))
    return records


def _builder() -> DirectGraphBuilder:
    return DirectGraphBuilder(
        metadata={
            "contract_version": "1.3.0",
            "weight_profile": "unit",
            "snapshot_id": SNAPSHOT,
            "created_at": CREATED,
            "code_version": "tests/lineage",
        }
    )


def _build(records):
    return _builder().build(IdentityNormalizer().normalize_records(records))


def _admin_edge(graph):
    return next(edge for edge in graph["edges"] if edge["kind"] == "AdminTo")


def _gpo_records():
    operations = (
        "gpo_setting",
        "active_link",
        "target_scope",
        "security_filtering",
        "wmi_filtering",
        "inheritance_and_order",
        "client_side_extension",
        "resultant_host_state",
    )
    records = _records(
        gpo={
            "principal_id": USER,
            "relationship": "AdminTo",
            "status": "resolved",
            "resultant_state": True,
            "resolved_steps": [
                {"operation": operation, "status": "resolved"} for operation in operations
            ],
        }
    )
    records.extend((_raw("Computer", {}, HOST_B), _raw("Group", {}, GROUP_A)))
    return records


def test_nested_lineage_is_ordered_traceable_and_deterministic():
    graphs = [_build(records) for records in permutations(_records(groups=(GROUP_A, GROUP_B)))]
    serialized = {serialize_graph(graph) for graph in graphs}
    assert len(serialized) == 1
    graph = graphs[0]
    edge = _admin_edge(graph)
    assert edge["id"] == canonical_edge_id(USER, HOST, "AdminTo")
    assert edge["derivation"]["version"] == "1.1.0"
    assert edge["provenance"][0]["timestamp_status"] == "unknown_legacy"
    assert len(edge["derivation"]["paths"]) == 2
    assert all(
        [step["order"] for step in path["steps"]] == [0, 1] for path in edge["derivation"]["paths"]
    )
    for path in edge["derivation"]["paths"]:
        assert all(step["evidence_refs"] for step in path["steps"])
        assert all(
            ref in {"sha256:" + "0" * 64} or ref.startswith("sha256:")
            for step in path["steps"]
            for ref in step["evidence_refs"]
        )


def test_derived_lineage_and_distinct_collection_time_statuses_round_trip():
    records = _records(groups=(GROUP_A, GROUP_B))
    group_records = [record for record in records if record.kind == "Group"]
    host_record = next(record for record in records if record.kind == "Computer")
    host_record.provenance["time_provenance"] = "observed"
    group_records[0].provenance["time_provenance"] = "observed"
    group_records[1].provenance["time_provenance"] = "assumed"

    graph = _build(records)
    edge = _admin_edge(graph)
    assert edge["derivation"]["version"] == "1.1.0"
    assert len(edge["derivation"]["paths"]) == 2
    assert {record["timestamp_status"] for record in edge["provenance"]} == {
        "observed",
        "assumed",
    }

    payload = serialize_graph(graph)
    reloaded = deserialize_graph(payload)
    reloaded_edge = _admin_edge(reloaded)
    assert reloaded == graph
    assert reloaded_edge["derivation"] == edge["derivation"]
    assert {record["timestamp_status"] for record in reloaded_edge["provenance"]} == {
        "observed",
        "assumed",
    }
    assert {record["attribute"] for record in reloaded_edge["provenance"]} == {
        record["attribute"] for record in edge["provenance"]
    }


def test_gpo_resultant_lineage_is_serialized_but_partial_gpo_is_not():
    resolved = _build(
        _records(
            gpo={
                "principal_id": USER,
                "relationship": "AdminTo",
                "status": "resolved",
                "resultant_state": True,
                "resolved_steps": [
                    {"operation": operation, "status": "resolved"}
                    for operation in (
                        "gpo_setting",
                        "active_link",
                        "target_scope",
                        "security_filtering",
                        "wmi_filtering",
                        "inheritance_and_order",
                        "client_side_extension",
                        "resultant_host_state",
                    )
                ],
            }
        )
    )
    edge = _admin_edge(resolved)
    assert edge["derivation"]["kind"] == "gpo_resultant"
    assert [step["operation"] for step in edge["derivation"]["paths"][0]["steps"]] == [
        "gpo_setting",
        "active_link",
        "target_scope",
        "security_filtering",
        "wmi_filtering",
        "inheritance_and_order",
        "client_side_extension",
        "resultant_host_state",
    ]
    partial = _build(
        _records(
            gpo={
                "principal_id": USER,
                "relationship": "AdminTo",
                "status": "unresolved",
            }
        )
    )
    assert not any(edge["kind"] == "AdminTo" for edge in partial["edges"])
    assert any(item["status"] == "unknown" for item in partial["assessments"])


def test_gpo_canrdp_lineage_serializes_all_composite_conditions():
    predicates = ("rdu_membership", "allow_right", "deny_absent")
    operations = (
        "gpo_setting",
        "active_link",
        "target_scope",
        "security_filtering",
        "wmi_filtering",
        "inheritance_and_order",
        "client_side_extension",
        "resultant_host_state",
    )
    gpo = {
        "principal_id": USER,
        "relationship": "CanRDP",
        "status": "resolved",
        "resultant_state": True,
        "resolved_steps": [
            {"operation": operation, "status": "resolved"} for operation in operations
        ],
        "resolved_conditions": [
            {
                "predicate": predicate,
                "status": "resolved",
                "evidence": {"resolver_record": f"condition-{predicate}"},
            }
            for predicate in predicates
        ],
    }
    graph = _build(_records(gpo=gpo))
    edge = next(edge for edge in graph["edges"] if edge["kind"] == "CanRDP")
    assert [
        condition["predicate"] for condition in edge["derivation"]["paths"][0]["conditions"]
    ] == list(predicates)
    assert deserialize_graph(serialize_graph(graph)) == graph
    assert serialize_graph(graph) == serialize_graph(_build(list(reversed(_records(gpo=gpo)))))


def test_gpo_canrdp_without_explicit_composite_conditions_is_not_traversable():
    operations = (
        "gpo_setting",
        "active_link",
        "target_scope",
        "security_filtering",
        "wmi_filtering",
        "inheritance_and_order",
        "client_side_extension",
        "resultant_host_state",
    )
    graph = _build(
        _records(
            gpo={
                "principal_id": USER,
                "relationship": "CanRDP",
                "status": "resolved",
                "resultant_state": True,
                "resolved_steps": [
                    {"operation": operation, "status": "resolved"} for operation in operations
                ],
            }
        )
    )
    assert not any(edge["kind"] == "CanRDP" for edge in graph["edges"])
    assert any(
        assessment["kind"] == "CanRDP" and assessment["status"] == "unknown"
        for assessment in graph["assessments"]
    )


def test_direct_edge_and_legacy_contract_1_0_graph_remain_valid():
    graph = json.loads((ROOT / "data/samples/toy-graph.json").read_text(encoding="utf-8"))
    assert graph["metadata"]["contract_version"] == "1.0.0"
    contract = yaml.safe_load((ROOT / "configs/contract.yml").read_text())
    validate_graph(graph, contract)
    assert all("derivation" not in edge for edge in graph["edges"])


def test_contract_1_1_graph_with_derivation_remains_loadable_without_inferred_time_status():
    graph = _build(_records(groups=(GROUP_A, GROUP_B)))
    graph["metadata"]["contract_version"] = "1.1.0"
    legacy_references = {}
    for edge in graph["edges"]:
        for item in edge["provenance"]:
            current_reference = provenance_reference(item)
            item.pop("timestamp_status")
            item.pop("time_provenance_reason", None)
            legacy_references[current_reference] = provenance_reference(item)
    for edge in graph["edges"]:
        if "derivation" not in edge:
            continue
        for path in edge["derivation"]["paths"]:
            for step in path["steps"]:
                step["evidence_refs"] = sorted(
                    legacy_references[ref] for ref in step["evidence_refs"]
                )
        edge["derivation"]["paths"].sort(
            key=lambda path: json.dumps(
                path, ensure_ascii=False, sort_keys=True, separators=(",", ":")
            )
        )
    contract = yaml.safe_load((ROOT / "configs/contract.yml").read_text())
    payload = serialize_graph(graph, contract=contract)
    loaded = deserialize_graph(payload, contract=contract)
    assert any("derivation" in edge for edge in loaded["edges"])
    assert all(
        "timestamp_status" not in item for edge in loaded["edges"] for item in edge["provenance"]
    )


@pytest.mark.parametrize(
    "mutation",
    [
        lambda edge: edge["derivation"]["paths"][0]["steps"].clear(),
        lambda edge: edge["derivation"]["paths"][0]["steps"].__setitem__(
            1, copy.deepcopy(edge["derivation"]["paths"][0]["steps"][0])
        ),
        lambda edge: edge["derivation"]["paths"].reverse(),
        lambda edge: edge["derivation"]["paths"][0]["steps"][0]["evidence_refs"].__setitem__(
            0, "sha256:" + "f" * 64
        ),
    ],
)
def test_malformed_lineage_is_rejected(mutation):
    graph = _build(_records(groups=(GROUP_A, GROUP_B)))
    mutation(_admin_edge(graph))
    with pytest.raises(ValueError, match="derivation"):
        validate_graph(graph, yaml.safe_load((ROOT / "configs/contract.yml").read_text()))


def test_direct_only_edge_kinds_cannot_carry_derivation():
    graph = _build(_records(groups=(GROUP_A,)))
    edge = _admin_edge(graph)
    edge["kind"] = "MemberOf"
    edge["id"] = canonical_edge_id(edge["source"], edge["target"], edge["kind"])
    with pytest.raises(ValueError, match="direct-only"):
        validate_graph(graph, yaml.safe_load((ROOT / "configs/contract.yml").read_text()))


def test_gpo_lineage_must_use_the_declared_ordered_operations():
    graph = _build(
        _records(
            gpo={
                "principal_id": USER,
                "relationship": "AdminTo",
                "status": "resolved",
                "resultant_state": True,
                "resolved_steps": [
                    {"operation": operation, "status": "resolved"}
                    for operation in (
                        "gpo_setting",
                        "active_link",
                        "target_scope",
                        "security_filtering",
                        "wmi_filtering",
                        "inheritance_and_order",
                        "client_side_extension",
                        "resultant_host_state",
                    )
                ],
            }
        )
    )
    edge = _admin_edge(graph)
    edge["derivation"]["paths"][0]["steps"][0]["operation"] = "effective_membership"
    with pytest.raises(ValueError, match="GPO operation"):
        validate_graph(graph, yaml.safe_load((ROOT / "configs/contract.yml").read_text()))


@pytest.mark.parametrize(
    ("endpoint", "replacement"),
    [("source", GROUP_A), ("target", HOST_B), ("source", None), ("target", None)],
)
def test_gpo_resultant_lineage_must_bind_both_edge_endpoints(endpoint, replacement):
    graph = _build(_gpo_records())
    edge = _admin_edge(graph)
    path = edge["derivation"]["paths"][0]
    terminal = path["steps"][-1]
    if replacement is None:
        terminal.pop(endpoint)
    else:
        terminal[endpoint] = replacement
    with pytest.raises(ValueError, match="GPO resultant state must bind"):
        validate_graph(graph, yaml.safe_load((ROOT / "configs/contract.yml").read_text()))


@pytest.mark.parametrize("lineage_kind", ["nested_membership", "host_access"])
def test_nested_lineage_rejects_reversed_membership_order(lineage_kind):
    graph = _build(_records(groups=(GROUP_A,)))
    edge = _admin_edge(graph)
    derivation = edge["derivation"]
    derivation["kind"] = lineage_kind
    steps = derivation["paths"][0]["steps"]
    steps[0]["operation"], steps[1]["operation"] = (
        steps[1]["operation"],
        steps[0]["operation"],
    )
    with pytest.raises(ValueError, match="derivation sequence"):
        validate_graph(graph, yaml.safe_load((ROOT / "configs/contract.yml").read_text()))


def test_admin_to_lineage_rejects_effective_right_without_host_membership():
    graph = _build(_records(groups=(GROUP_A,)))
    edge = _admin_edge(graph)
    steps = edge["derivation"]["paths"][0]["steps"]
    steps[0]["operation"] = "effective_right"
    steps[0]["target"] = "SeRemoteInteractiveLogonRight"
    del steps[1]
    with pytest.raises(ValueError, match="derivation sequence"):
        validate_graph(graph, yaml.safe_load((ROOT / "configs/contract.yml").read_text()))


def test_nested_membership_lineage_rejects_non_group_parent_node():
    graph = _build(_records(groups=(GROUP_A,)))
    edge = _admin_edge(graph)
    other_computer = "S-1-5-21-1000-2000-3000-3102"
    graph["nodes"].append(
        {
            "id": other_computer,
            "kind": "Computer",
            "label": "OTHER.EXAMPLE.TEST",
            "domain": DOMAIN,
            "is_boundary": False,
        }
    )
    steps = edge["derivation"]["paths"][0]["steps"]
    steps[0]["target"] = other_computer
    steps[1]["source"] = other_computer

    with pytest.raises(ValueError, match="nested membership steps"):
        validate_graph(graph, yaml.safe_load((ROOT / "configs/contract.yml").read_text()))


def test_derived_host_access_target_must_be_a_computer():
    graph = _build(_records(groups=(GROUP_A,)))
    edge = _admin_edge(graph)
    edge["target"] = USER
    edge["id"] = canonical_edge_id(edge["source"], edge["target"], edge["kind"])

    with pytest.raises(ValueError, match="target must be a Computer"):
        validate_graph(graph, yaml.safe_load((ROOT / "configs/contract.yml").read_text()))


def test_graph_json_round_trip_is_exact_and_deterministic():
    graph = _build(_records(groups=(GROUP_A, GROUP_B)))
    payload = serialize_graph(graph)
    assert payload == serialize_graph(deserialize_graph(payload))
    edge = _admin_edge(deserialize_graph(payload))
    assert edge["derivation"]["kind"] == "nested_membership"
    assert edge["provenance"][0]["timestamp_status"] == "unknown_legacy"
