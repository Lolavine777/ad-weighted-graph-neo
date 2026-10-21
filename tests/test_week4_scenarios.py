"""Consume A2's independent inputs with the unchanged accepted golden harness."""

import hashlib
import json
from pathlib import Path

import pytest

from scripts.research.attack_scenarios import load_suite, run_case

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "tests/fixtures/attack_scenarios/week4-v1.json"
SUITE = load_suite(PACKAGE)
S0 = {"control": ["Alice"]}
S1 = {**S0, "effective_member": [["Alice", "Admins"]]}
S2 = {**S0, "admin_control": ["Host"]}
S3 = {**S1, "admin_control": ["Host"]}


@pytest.mark.parametrize(
    "scenario_id,variant_id,expected_states",
    [
        ("w4-two-routes-exact", "positive", [S0, S1, S2, S3]),
        ("w4-two-routes-exact", "initial-entitlement", [S1, S3]),
        ("w4-two-routes-exact", "host-control-only", [{"admin_control": ["OtherHost"]}]),
        ("w4-other-target", "positive", [S0, S1, S2, S3]),
    ],
)
def test_week4_exact_programs_and_entire_state_set(scenario_id, variant_id, expected_states):
    case = next(c for c in SUITE["scenarios"] if c["scenario_id"] == scenario_id)
    variant = next(v for v in case["variants"] if v["variant_id"] == variant_id)
    report = run_case(SUITE, case, variant, PACKAGE.parent)
    # The existing schema checks reachable projections; A2 also requires full equality.
    assert report["complete"]
    assert set(report["reachable_states"]) == {
        json.dumps(state, sort_keys=True) for state in expected_states
    }


def test_week4_package_file_pins():
    manifest = PACKAGE.with_suffix(".sha256")
    for line in manifest.read_text(encoding="utf-8").splitlines():
        expected, relative = line.split("  ", 1)
        path = (ROOT / relative).resolve()
        assert path.is_relative_to(ROOT)
        assert hashlib.sha256(path.read_bytes()).hexdigest() == expected, relative


@pytest.mark.parametrize(
    "cap,reason",
    [
        ("max_paths", "path_limit_reached"),
        ("max_expansions", "expansion_limit_reached"),
        ("max_steps", "step_limit_reached"),
    ],
)
def test_week4_partial_search_cannot_prove_complete_minimum(cap, reason):
    from scripts.research.attack_scenarios import contains, state_from
    from src.engine import EngineGraph, SearchBudget, generate_attack_paths
    from src.engine.semantics import RuntimeContext, RuntimeFact, load_catalog

    case = SUITE["scenarios"][0]
    binding = SUITE["graphs"][case["graph"]]
    aliases = binding["aliases"]
    graph = EngineGraph.from_canonical(json.loads((PACKAGE.parent / binding["path"]).read_text()))
    context = RuntimeContext(
        [
            RuntimeFact(
                **{
                    **{k: v for k, v in fact.items() if k != "evidence_ref"},
                    "subject": aliases[fact["subject"]],
                    "target": aliases[fact["target"]],
                    "provenance_reference": fact["evidence_ref"],
                }
            )
            for fact in case["runtime_facts"]
        ]
    )
    goal = state_from(case["target_goal"]["required_state"], aliases)
    result = generate_attack_paths(
        graph,
        aliases[case["initial_actor"]],
        initial_state=state_from(case["initial_state"], aliases),
        runtime_context=context,
        target_predicate=lambda node: node["id"] == aliases[case["target_goal"]["target"]],
        success_state_predicate=lambda state: contains(state, goal),
        catalog=tuple(t for t in load_catalog() if t.id in case["oracle_scope"]["techniques"]),
        budget=SearchBudget(**{**case["oracle_scope"]["budget"], cap: 1}),
    )
    assert result.truncated and not result.complete
    assert result.truncation_reason == reason
    # The independent oracle includes M/I; a cap may miss this lower-effort program.
    assert all(
        tuple(step.result.request.source for step in path.transition_history)
        != (aliases["Alice"], aliases["Admins"])
        for path in result.paths
    )
