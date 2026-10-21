"""Usable C-rated WinRM results and a brief faithful to the native result."""

import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from test_engine import ACTOR, HOST, _edge
from test_neo_effort import bind, inputs

from src.engine.query import run_attack_query
from src.engine.query_cli import execute, wire
from src.engine.query_report import render_query_brief
from src.engine.semantics.credentials import replay_path

ROOT = Path(__file__).resolve().parents[1]


def winrm_inputs():
    graph, query = inputs("membership")
    data = graph.to_canonical()
    data["edges"] = [_edge(ACTOR, HOST, "CanPSRemote")]
    graph = type(graph).from_canonical(data)
    query["allowed_techniques"] = ["open_winrm_remote_session"]
    query["target_goal"]["required_state"] = {"remote_command_execution": [[ACTOR, HOST]]}
    query["assumptions"].append(
        {
            "predicate": "winrm_available",
            "subject": ACTOR,
            "target": HOST,
            "value": True,
            "scope": "neo-finite",
            "rationale": "WinRM service reachable under this scenario",
            "provenance_reference": "synthetic://neo-winrm",
        }
    )
    return graph, query


def test_winrm_C_one_does_not_change_semantics_or_grant_admin():
    graph, query = winrm_inputs()
    before = run_attack_query(query, graph)
    after = run_attack_query(bind(graph, query), graph)
    assert wire(before.paths) == wire(after.paths)
    assert after.min_effort["minimum_effort_value"] == 1
    assert after.top_k_result["returned_count"] == 1
    for path in after.paths:
        assert replay_path(path, graph) == path.final_state
        assert path.final_state.remote_command_execution == {(ACTOR, HOST)}
        assert not path.final_state.admin_control
    brief = render_query_brief(after, graph)
    assert "C=1" in brief and "không đồng nghĩa quyền quản trị" in brief
    assert "P: chưa chấm; I: chưa chấm" in brief
    assert "Giả định đã dùng" in brief and "winrm_available" in brief


@pytest.mark.parametrize("predicate", ["winrm_available", "authentication_accepted"])
@pytest.mark.parametrize("value", [None, False])
def test_WinRM_price_does_not_resolve_missing_or_false_gates(predicate, value):
    graph, query = winrm_inputs()
    query["assumptions"] = [f for f in query["assumptions"] if f["predicate"] != predicate]
    if value is False:
        query["runtime_facts"] = [
            {
                "predicate": predicate,
                "subject": ACTOR,
                "target": HOST,
                "value": False,
                "origin": "observed_evidence",
                "provenance_reference": "synthetic://winrm-refused",
            }
        ]
    result = run_attack_query(bind(graph, query), graph)
    assert not result.paths and result.top_k_result["returned_count"] == 0
    brief = render_query_brief(result, graph)
    assert "C=0" not in brief and "C=1" not in brief
    if value is None:
        assert "chưa kết luận an toàn" in brief


def test_brief_uses_selected_C_order_and_actual_ledger():
    graph, query = inputs("acl")
    data = graph.to_canonical()
    data["edges"].append(_edge(ACTOR, HOST, "AdminTo"))
    graph = type(graph).from_canonical(data)
    query["top_k"] = 100
    result = run_attack_query(bind(graph, query), graph)
    brief = render_query_brief(result, graph)
    assert brief.index("C=1") < brief.index("C=4")
    assert "Dùng danh tính vừa reset: C=0" in brief
    assert "khử trùng theo ledger" in brief


def test_missing_C_stays_visible_without_ranking():
    graph, query = winrm_inputs()
    result = run_attack_query(query, graph)
    brief = render_query_brief(result, graph)
    assert result.paths and "C=chưa chấm" in brief
    assert "chưa được xếp hạng theo C" in brief


def test_C_is_reported_without_an_explicit_top_k_request():
    graph, query = winrm_inputs()
    query = bind(graph, query)
    query.pop("top_k")
    result = run_attack_query(query, graph)
    assert result.top_k_result is None
    brief = render_query_brief(result, graph)
    assert "C=1" in brief and "C=chưa chấm" not in brief


def test_empty_context_and_initial_success_are_readable():
    graph, query = inputs("acl")
    query.pop("authentication_context")
    query["initial_state"] = {"admin_control": [HOST]}
    query["top_k"] = 3
    result = run_attack_query(query, graph)
    brief = render_query_brief(result, graph)
    assert "Context xác thực:** chưa khai báo" in brief
    assert "trạng thái ban đầu" in brief and "C=0" in brief


def test_brief_and_JSON_share_one_execution(tmp_path):
    graph, query = winrm_inputs()
    query = bind(graph, query)
    path = tmp_path / "brief.md"
    with patch("src.engine.query_cli.run_attack_query", wraps=run_attack_query) as run:
        payload = execute(query, graph, brief_output=str(path))
        assert run.call_count == 1
    assert payload["top_k"]["programs"][0]["effort"] == 1
    assert "C=1" in path.read_text(encoding="utf-8")
    gp, qp, out = (tmp_path / name for name in ("graph.json", "query.json", "result.json"))
    gp.write_text(json.dumps(graph.to_canonical()))
    qp.write_text(json.dumps(query))
    subprocess.run(
        [
            sys.executable,
            "-m",
            "src.engine",
            "query",
            "--graph",
            str(gp),
            "--query",
            str(qp),
            "--label",
            "synthetic",
            "--output",
            str(out),
            "--brief",
            str(path),
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    actual = json.loads(out.read_text())["semantic"]
    assert all(actual[key] == value for key, value in payload.items())
    assert "C=1" in path.read_text(encoding="utf-8")


def test_rating_reuses_owned_graph_and_witnesses_remain_isolated():
    graph, query = inputs("acl")
    query = bind(graph, query)
    before = graph.to_canonical()
    with patch.object(graph, "to_canonical", side_effect=AssertionError("full graph copy")):
        result = run_attack_query(query, graph)
    for path in result.paths:
        for edge in path.edges:
            edge["provenance"].clear()
    assert graph.to_canonical() == before
