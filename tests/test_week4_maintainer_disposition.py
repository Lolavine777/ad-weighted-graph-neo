"""Exact A maintainer acceptance cannot activate broad or weaker-goal ratings."""

import copy
import hashlib
from pathlib import Path

import pytest

from scripts.research.issue250_public_probe import read
from scripts.research.week4_maintainer_disposition import PACKET, ROOT, frozen_case
from src.engine import run_attack_query
from src.engine.ranking.resolution_service import canonical_digest


@pytest.fixture(scope="module")
def frozen():
    raw = ROOT / "data/raw/SEAMLESS"
    if not raw.is_dir():
        pytest.skip("Authorized manifest-verified raw SEAMLESS required")
    return frozen_case(raw, "29ca3cb8f8daf850b51bfa658e99621a1e8a7c5c")


def test_frozen_exact_c_i_adoption_keeps_p_unrated(frozen):
    graph, query, _ = frozen
    packet = read(PACKET)
    assert packet["independent_b_review"] is False
    assert "A maintainer" in packet["role"]
    assert [c["computed_cost"] for c in packet["effort"]] == [0, 2, 0, 1]
    result = run_attack_query(query, graph)
    assert len(result.search_result.paths) == 1
    assert result.rating_coverage["numeric_requests"] == packet["oracle"]["numeric_requests"]
    assert result.ranking_result["min_effort_to_da_baseline"]["minimum_effort_value"] == 3
    assert not result.ranking_result["pareto_frontier"]
    impact = result.rating_coverage["candidates"]["generated_0001"]["impact"]
    assert impact["consequence_rating"] == "High"
    for c in packet["effort"]:
        app = c["applicability"]
        assert app["scopes"] == ["week4-seamless-v1"]
        assert app["snapshot_ids"] == [packet["snapshot_id"]]
        assert len(app["work_unit_digests"]) == 1
        assert "*" not in app["methods"]


@pytest.mark.parametrize("dimension", ["C", "I"])
def test_frozen_numeric_basis_refuses_context_or_typed_goal_change(frozen, dimension):
    graph, query, _ = frozen
    variant = copy.deepcopy(query)
    role = "effort" if dimension == "C" else "impact"
    env = variant["rating_resolution"]["registries"][role]
    if dimension == "C":
        for c in env["data"]:
            c["applicability"]["work_unit_digests"] = ["sha256:" + "0" * 64]
    else:
        goal = env["data"]["mappings"][0]["applicability"]["semantic_goal"]
        goal["required_state"] = {"usable_identity": [query["target"]]}
    env["sha256"] = canonical_digest(env["data"])
    result = run_attack_query(variant, graph)
    assert len(result.search_result.paths) == 1
    assert result.rating_coverage["numeric_requests"][dimension]["rated"] == 0
    assert not result.ranking_result["pareto_frontier"]


def test_frozen_historical_oracles_are_byte_preserved():
    scenario_hash = "66c5ffef9a10d30d685f437b10d2998b0d57b96c2151c7eb9d00a0feeb0df752"
    release_hash = "5cf9a00d50cc42d6c5828f06614a116684f7527a852447c44fc261d33e292d41"
    pins = {
        "docs/research/scenarios/week4-seamless-v1.json": scenario_hash,
        "docs/research/ratings/week3-closeout/reviewed-release.json": release_hash,
    }
    for name, expected in pins.items():
        assert hashlib.sha256((ROOT / Path(name)).read_bytes()).hexdigest() == expected
