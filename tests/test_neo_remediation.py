"""Counterfactual records must regenerate dependent access, then rediscover natively."""

from copy import deepcopy

import pytest
from test_graph_lineage import GROUP_A, GROUP_B, HOST, USER, _build, _records
from test_neo_host_session import scenario

from scripts.neo_remediation import classify, edit_records, rebuild, verify_result
from src.engine.query import run_attack_query
from src.engine.top_k import collect_assessments
from src.parser import RawRecord


@pytest.mark.parametrize("groups", [(GROUP_A,), (GROUP_A, GROUP_B)])
def test_membership_edit_regenerates_only_supported_admin_access(groups):
    records = _records(groups=groups)
    # Use the same collector shape as the pinned WRAITH export.
    for record in records:
        if record.kind == "Group":
            record.data["Members"] = [{"ObjectIdentifier": USER, "ObjectType": "User"}]
    metadata = _build(records)["metadata"]
    before = deepcopy(records)
    changed, audit = edit_records(records, USER, "MemberOf", GROUP_A)
    graph = rebuild(changed, metadata)
    assert records == before and audit == {"Members": 1}
    assert not graph.edges_between(USER, GROUP_A)
    admin = [e for e in graph.edges_between(USER, HOST) if e["kind"] == "AdminTo"]
    if len(groups) == 1:
        assert not admin
    else:
        assert len(admin) == 1 and len(admin[0]["derivation"]["paths"]) == 1
        assert admin[0]["derivation"]["paths"][0]["steps"][0]["target"] == GROUP_B


def test_session_edit_removes_duplicate_support_in_all_three_collections():
    records = _records()
    computer = records[0]
    for field in ("Sessions", "PrivilegedSessions", "RegistrySessions"):
        computer.data[field] = {
            "Collected": True,
            "Results": [{"UserSID": USER, "ComputerSID": HOST}] * 2,
        }
    other = RawRecord("Computer", {"ObjectIdentifier": "other"}, {})
    records.append(other)
    before = deepcopy(records)
    changed, audit = edit_records(records, HOST, "HasSession", USER)
    assert audit == {"Sessions": 2, "PrivilegedSessions": 2, "RegistrySessions": 2}
    assert records == before and changed[-1] == other
    graph = rebuild(changed[:-1], _build(records[:-1])["metadata"])
    assert not graph.edges(kind="HasSession")


def test_edit_fails_if_no_collector_support_matches():
    with pytest.raises(ValueError, match="No matching"):
        edit_records(_records(), USER, "MemberOf", GROUP_A)
    with pytest.raises(ValueError, match="Unsupported"):
        edit_records(_records(), USER, "GenericAll", HOST)


@pytest.mark.parametrize("strategy", ["neo_guided", "neo_refine"])
def test_every_witness_is_replayed_and_C_matches_its_unique_ledger(strategy):
    graph, query = scenario(lateral=True, mutate=True)
    result = run_attack_query({**query, "search_order": strategy}, graph)
    row, evidence = verify_result(result, graph)
    assert row["C"] == 4 and row["replayed_programs"] == len(result.paths)
    assert row["ledger_checked_programs"] == len(result.paths)
    assert len(evidence["witnesses"]) == len(result.paths)
    candidate = next(iter(collect_assessments(result).values()))
    candidate["effort"] += 1
    with pytest.raises(AssertionError, match="ledger"):
        verify_result(result, graph)


@pytest.mark.parametrize(
    "reached,no_path,truncated,unknown,expected",
    [
        (True, False, True, 0, "bypass"),
        (False, True, False, 0, "blocked_in_scope"),
        (False, False, True, 0, "inconclusive"),
        (False, False, False, 1, "inconclusive"),
    ],
)
def test_capped_or_unknown_failure_is_never_a_block(reached, no_path, truncated, unknown, expected):
    assert classify(reached, no_path, truncated, unknown) == expected
