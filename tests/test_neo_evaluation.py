"""The evaluation's own arithmetic, checked on small cases with known answers."""

import pytest

from scripts.neo_evaluation import hop_distances, spearman, summarize


class _Graph:
    def __init__(self, edges):
        self._edges = [{"source": s, "kind": k, "target": t} for s, k, t in edges]

    def edges(self):
        return self._edges


def test_hop_distances_follow_edge_direction_and_allowed_kinds():
    graph = _Graph([("a", "MemberOf", "b"), ("b", "GenericAll", "t"), ("c", "HasSession", "t")])
    assert hop_distances(graph, "t", {"MemberOf", "GenericAll"}) == {"t": 0, "b": 1, "a": 2}
    assert hop_distances(graph, "t", {"HasSession"}) == {"t": 0, "c": 1}


def test_spearman_handles_order_ties_and_no_variation():
    assert spearman([1, 2, 3], [10, 20, 30]) == pytest.approx(1)
    assert spearman([1, 2, 3], [30, 20, 10]) == pytest.approx(-1)
    assert spearman([1, 1, 2, 2], [1, 1, 2, 2]) == pytest.approx(1)
    assert spearman([1, 1, 1], [1, 2, 3]) is None
    assert spearman([1], [1]) is None


def test_summary_counts_when_the_shortest_choice_costs_more():
    row = {
        "source": "a",
        "target": "t",
        "reached": True,
        "no_path": False,
        "seconds": 1.0,
        "programs": [{"C": 3, "steps": 3}, {"C": 1, "steps": 5}],
    }
    tie = {**row, "source": "b", "programs": [{"C": 2, "steps": 2}, {"C": 2, "steps": 4}]}
    blocked = {**row, "source": "c", "reached": False, "no_path": True, "programs": []}
    stopped = {**row, "source": "d", "reached": False, "programs": []}
    summary = summarize([row, tie, blocked, stopped], {"t": {"a": 1, "b": 2, "c": 1}})
    assert (summary["pairs"], summary["reached"], summary["no_path"]) == (4, 2, 1)
    assert summary["inconclusive"] == 1
    assert summary["pairs_with_several_paths"] == 2
    assert summary["fewest_steps_costs_more"] == 1
    assert summary["hop_path_exists"] == 3
    assert summary["hop_path_without_neo_path"] == 1
    assert summary["neo_path_without_hop_path"] == 0
    assert summary["C_range_by_hops"] == {
        "1": {"pairs": 1, "min": 1, "max": 1},
        "2": {"pairs": 1, "min": 2, "max": 2},
    }
