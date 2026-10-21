"""Keep observed support separate from successful remediation and bounded search."""

import pytest

from scripts import neo_domain_report as report


class Graph:
    def edge(self, edge_id):
        return {"kind": edge_id, "source": "a", "target": "b"}

    def node(self, node_id):
        return {"label": node_id}


def row(cost, *, reached=True):
    return {
        "reached": reached,
        "C": cost,
        "witness": {"transition_history": [{"edge_id": "MemberOf"}] * 2},
    }


def test_observed_support_counts_pairs_once_and_excludes_existing_privilege():
    rows = {("a", "b"): row(1), ("c", "b"): row(0), ("d", "b"): row(None)}
    inventory = report.observed_interventions(rows, Graph())
    assert len(inventory) == 1
    assert inventory[0]["observed_pairs"] == 1
    assert inventory[0]["pairs"] == [("a", "b")]
    rows[("a", "b")]["witness"]["transition_history"].append({"edge_id": "GenericAll"})
    inventory = report.observed_interventions(rows, Graph())
    assert next(c for c in inventory if c["edge_id"] == "GenericAll")["executor_supported"] is False


def test_report_separates_reached_path_cap_from_unresolved_and_formats_denominators():
    rows = {
        ("a", "b"): {**row(1), "target": "b", "truncated": True},
        ("c", "b"): {**row(None, reached=False), "target": "b", "truncated": True},
    }
    summary = {
        "eligible_sources": 2,
        "declared_pairs": 2,
        "recorded_pairs": 2,
        "not_run_pairs": 0,
        "reached_pairs": 1,
        "C_rated_reached_pairs": 1,
        "truncated_pairs": 2,
        "errors": 0,
        "unknown_attempts": {},
    }
    remediation = {
        "status": "executed",
        "sources": 1,
        "pairs": 2,
        "outcomes": [
            {
                "edits": ["remove membership"],
                "programs_cut": {"numerator": 1, "denominator": 1},
                "pairs_disconnected": {"numerator": 0, "denominator": 1},
                "reachable_after": 1,
                "unresolved_after": 1,
                "new_after_programs": 1,
            }
        ],
    }
    rendered = report.render_report(summary, rows, [], Graph(), remediation)
    assert "chưa có witness và còn giới hạn: 1" in rendered
    assert "Programs cut: 1/1; pairs disconnected: 0/1" in rendered
    assert "chương trình mới: 1" in rendered


def test_invalid_intervention_count_rejected_before_creating_output(tmp_path):
    output = tmp_path / "output"
    with pytest.raises(SystemExit):
        report.main(
            [
                "--survey",
                "unused",
                "--snapshot",
                "unused",
                "--output-dir",
                str(output),
                "--interventions",
                "-1",
            ]
        )
    assert not output.exists()
