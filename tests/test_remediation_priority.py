"""Adversarial display-policy comparisons; these are not native proof packages."""

import copy

import pytest

from src.engine.remediation_runner import rank_interventions


def package(request_id, reachability, exposed, *, complete=False, cuts=0):
    return {
        "report": {
            "request_id": request_id,
            "comparison_scope_digest": "same-scope",
            "declared_goal_ids": ["host"],
            "cells": [
                {
                    "source_id": "alice",
                    "goal_id": "host",
                    "before": {
                        "complete": True,
                        "unresolved_feasibility": False,
                        "reachability": "reachable",
                    },
                    "after": {
                        "complete": complete,
                        "unresolved_feasibility": not complete,
                        "reachability": reachability,
                    },
                }
            ],
            "summary": {
                "pairs_disconnected": {"numerator": 0},
                "exposed_sources_after": ["alice"] if exposed else [],
                "programs_cut": {"numerator": cuts},
            },
        }
    }


@pytest.mark.parametrize(
    "reachability,complete",
    [
        ("unknown", False),
        ("unknown", True),
        ("error", False),
        ("unsupported", False),
        ("not_evaluated", False),
    ],
)
@pytest.mark.parametrize("cuts", [0, 10])
def test_equal_incomplete_zero_witness_cannot_outrank_retained_witness(
    reachability, complete, cuts
):
    missing = package("a-missing", reachability, False, complete=complete, cuts=cuts)
    if complete:
        missing["report"]["cells"][0]["after"]["unresolved_feasibility"] = True
    retained = package("z-retained", "reachable", True)
    ordered = rank_interventions([missing, retained])
    assert [row["intervention"] for row in ordered] == ["z-retained", "a-missing"]
    assert [row["quantities"]["incomplete_observations"] for row in ordered] == [1, 1]
    assert [row["quantities"]["unresolved_after_pairs"] for row in ordered] == [0, 1]
    assert ordered == rank_interventions([retained, missing])
    assert all(row["policy"] == "defensive-complete-scope-first/2" for row in ordered)


def test_unknown_goal_counts_even_when_source_has_another_reachable_goal():
    missing = package("a-missing", "unknown", True)
    retained = package("z-retained", "reachable", True)
    for candidate in (missing, retained):
        report = candidate["report"]
        report["declared_goal_ids"].append("second-host")
        other = copy.deepcopy(report["cells"][0])
        other["goal_id"] = "second-host"
        other["after"].update(complete=True, unresolved_feasibility=False, reachability="reachable")
        report["cells"].append(other)
    ordered = rank_interventions([missing, retained])
    assert ordered[0]["intervention"] == "z-retained"
    assert [row["quantities"]["remaining_exposed_sources"] for row in ordered] == [1, 1]
    assert [row["quantities"]["unresolved_after_pairs"] for row in ordered] == [0, 1]


def test_equally_unresolved_ties_are_stable():
    one = package("a", "unknown", False)
    two = package("z", "error", False)
    ordered = rank_interventions([two, one])
    assert [row["intervention"] for row in ordered] == ["a", "z"]
    assert ordered == rank_interventions([one, two])


def test_complete_evidence_still_precedes_missing_evidence():
    missing = package("a-missing", "error", False, cuts=10)
    complete = package("z-complete", "reachable", True, complete=True)
    assert rank_interventions([missing, complete])[0]["intervention"] == "z-complete"
