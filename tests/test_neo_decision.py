"""Small decision scopes preserve source isolation, ties and native denominators."""

import copy

import pytest

from scripts.neo_decision import aggregate, membership_points, route_count, select_sources


class Graph:
    def edge(self, edge_id):
        return {"id": edge_id, "kind": "MemberOf", "source": "member", "target": "DA"}


def sample_row(cost=1):
    return {
        "source": "one",
        "target": "DA",
        "programs": [{"candidate_id": "generated_0001", "effort": cost, "program_id": "p1"}],
        "paths": [{"transition_history": [{"edge_id": "e"}, {"edge_id": "e"}]}],
    }


def test_source_selection_is_order_independent_and_not_outcome_filtered():
    sources = [
        {"node_id": f"{kind}-{i}", "node_kind": kind, "reached": False}
        for kind in ("User", "Computer", "Group")
        for i in range(7)
    ]
    selected = select_sources(sources)
    assert selected == select_sources(list(reversed(sources)))
    assert sum(s["node_kind"] == "User" for s in selected) == 3
    assert sum(s["node_kind"] == "Computer" for s in selected) == 2
    assert all(s["reached"] is False for s in selected)


def test_membership_support_counts_distinct_programs_and_skips_zero_or_missing_C():
    one = sample_row()
    two = copy.deepcopy(one)
    two["programs"][0]["program_id"] = "p2"
    points = membership_points([one, two, sample_row(0), sample_row(None)], Graph(), {"DA"})
    assert len(points) == 1
    assert points[0]["programs"] == 2 and points[0]["pairs"] == [("one", "DA")]
    assert not membership_points([one], Graph(), {"other"})
    assert route_count({"paths": one["paths"] + two["paths"]}) == 1


def test_aggregate_keeps_cut_programs_separate_from_disconnected_pairs():
    source = {
        "source_index": 0,
        "cells": [{}, {}],
        "outcome": {
            "programs_cut": {"numerator": 3, "denominator": 6},
            "pairs_disconnected": {"numerator": 0},
            "reachable_before": 2,
            "reachable_after": 2,
            "unresolved_after": 0,
            "new_after_programs": 3,
        },
    }
    second = {**copy.deepcopy(source), "source_index": 1}
    totals = aggregate([source, second])
    assert totals["pairs"] == totals["reachable_after"] == 4
    assert totals["programs_cut"] == 6 and totals["baseline_programs"] == 12
    assert totals["pairs_disconnected"] == totals["unresolved_after"] == 0
    with pytest.raises(ValueError, match="Duplicate source"):
        aggregate([source, source])
