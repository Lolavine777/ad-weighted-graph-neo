"""Public query regressions for PR #221's fact, scope and goal boundaries."""

import json
from pathlib import Path

import pytest

from src.engine import AttackQuery, materialize_query, run_attack_query
from src.engine.semantics import FactOrigin, RuntimeFact, load_catalog
from src.engine.semantics.projection_runtime import context_for_projection

FIXTURES = Path(__file__).parent / "fixtures/attack_scenarios"
PACKAGE = json.loads((FIXTURES / "week4-v1.json").read_text(encoding="utf-8"))
CASE = PACKAGE["scenarios"][0]
BINDING = PACKAGE["graphs"][CASE["graph"]]
GRAPH = json.loads((FIXTURES / BINDING["path"]).read_text(encoding="utf-8"))
ALIASES = BINDING["aliases"]
BASE = {
    "initial_actor": CASE["initial_actor"],
    "initial_state": CASE["initial_state"],
    "target": CASE["target_goal"]["target"],
    "target_goal": CASE["target_goal"],
    "runtime_facts": CASE["runtime_facts"],
    "aliases": ALIASES,
    "budget": CASE["oracle_scope"]["budget"],
}


def assumption(**overrides):
    return {
        "predicate": "admin_channel",
        "subject": "Alice",
        "target": "Host",
        "value": True,
        "origin": "declared_assumption",
        "scope": "current_snapshot",
        "rationale": "Explicit synthetic channel assumption",
        "provenance_reference": "fixture:query-boundary",
        **overrides,
    }


@pytest.mark.parametrize("custom", [False, True])
def test_empty_allow_list_never_attempts_any_technique(custom):
    query = {**BASE, "allowed_techniques": []}
    if custom:
        query["catalog"] = load_catalog()
    result = run_attack_query(query, GRAPH)
    assert result.materialized_query.catalog == ()
    assert result.attempts == ()
    assert result.paths == ()
    assert result.status == "no_path"


def test_custom_catalog_intersects_allowed_ids_before_search():
    result = run_attack_query(
        {**BASE, "catalog": load_catalog(), "allowed_techniques": ["propagate_group_entitlement"]},
        GRAPH,
    )
    assert {t.id for t in result.materialized_query.catalog} == {"propagate_group_entitlement"}
    assert result.attempts
    assert {attempt.request.technique_id for attempt in result.attempts} == {
        "propagate_group_entitlement"
    }
    assert result.paths == ()


@pytest.mark.parametrize("typed", [False, True])
def test_explicit_evidence_only_mode_has_identical_public_input_behavior(typed):
    query = {
        **BASE,
        "runtime_facts": [f for f in BASE["runtime_facts"] if f["predicate"] != "admin_channel"],
        "assumptions": [assumption()],
    }
    result = run_attack_query(
        AttackQuery(**query) if typed else query, GRAPH, evaluation_mode="evidence_only"
    )
    assert result.materialized_query.evaluation_mode == "evidence_only"
    assert result.paths == ()
    assert result.status == "indeterminate"
    assert result.materialized_query.rejected_assumptions[0].reason == (
        "evidence_only_mode_disallows_assumptions"
    )


def test_projection_scopes_preserve_known_false_and_rejected_source():
    binding = {
        "runtime_fact_bindings": [
            {
                "release_predicate": "channel",
                "semantic_predicate": "admin_channel",
                "subject": ALIASES["Alice"],
                "target": ALIASES["Host"],
            }
        ]
    }
    query = {
        "query_metadata": {"horizon": "current_snapshot", "scenario_id": "gate-f"},
        "facts_ledger": {
            "false_facts": [
                {
                    "predicate": "channel",
                    "truth_value": False,
                    "rationale": "Blocked channel",
                    "provenance_reference": "fixture:blocked",
                }
            ]
        },
    }
    blocked = next(iter(context_for_projection(query, binding, {}).facts.values()))
    query["facts_ledger"] = {
        "assumed_facts": [
            {
                "predicate": "channel",
                "truth_value": True,
                "rationale": "Synthetic channel available",
                "provenance_reference": "fixture:declared",
            }
        ]
    }
    optimistic = next(iter(context_for_projection(query, binding, {}).facts.values()))
    assert blocked.scope == "gate-f" and optimistic.scope == "current_snapshot"
    result = run_attack_query(
        {
            **BASE,
            "runtime_facts": [f for f in BASE["runtime_facts"] if f["predicate"] != "admin_channel"]
            + [blocked],
            "assumptions": [optimistic],
        },
        GRAPH,
    )
    assert result.paths == () and result.status == "blocked"
    resolved = result.materialized_query.runtime_context.facts[
        blocked.predicate, blocked.subject, blocked.target
    ]
    assert resolved.value is False and resolved.origin is FactOrigin.BLOCKED_EVIDENCE
    rejected = result.materialized_query.rejected_assumptions[0].to_dict()
    assert rejected["reason"] == "known_false_veto"
    assert rejected["provenance_reference"] == "fixture:declared"
    assert rejected["assumption_metadata"]["release_predicate"] == "channel"


def test_authoritative_counterfactual_views_require_selector_and_remain_isolated():
    facts = [
        {
            **assumption(value=value, assumption_metadata={"view_id": view}),
            "origin": "observed_evidence",
        }
        for view, value in (("baseline", False), ("counterfactual", True))
    ]
    query = {**BASE, "runtime_facts": facts}
    with pytest.raises(ValueError, match="multiple scenario views"):
        materialize_query(query, GRAPH)
    for view, value in (("baseline", False), ("counterfactual", True)):
        materialized = materialize_query(query, GRAPH, active_scope=view)
        assert next(iter(materialized.runtime_context.facts.values())).value is value


def test_untagged_false_is_not_removed_by_explicit_view_selector():
    fact = {**assumption(value=False, scope="scenario-1"), "origin": "blocked_evidence"}
    materialized = materialize_query(
        {
            **BASE,
            "runtime_facts": [fact],
            "assumptions": [assumption(assumption_metadata={"view_id": "selected"})],
        },
        GRAPH,
        active_scope="selected",
    )
    assert next(iter(materialized.runtime_context.facts.values())).value is False
    assert materialized.rejected_assumptions[0].reason == "known_false_veto"


@pytest.mark.parametrize(
    "goal",
    [
        "DA",
        {},
        {"target": "Admins", "required_state": {}},
        {"target": "Admins", "required_state": {"effective_member": []}},
        {"target": "missing", "required_state": {"admin_control": ["Host"]}},
        {"target": "Admins", "required_state": {"admin_control": ["Host"]}},
    ],
)
def test_malformed_or_unrelated_checkpoint_rejected_even_with_callable(goal):
    with pytest.raises((TypeError, ValueError)):
        materialize_query(
            {**BASE, "checkpoint_goal": goal, "checkpoint_state_predicate": lambda state: True},
            GRAPH,
        )


def test_checkpoint_callable_cannot_bypass_declared_goal():
    result = run_attack_query(
        {
            **BASE,
            "allowed_techniques": [],
            "checkpoint_goal": {
                "target": "Admins",
                "required_state": {"effective_member": [["Alice", "Admins"]]},
            },
            "checkpoint_state_predicate": lambda state: True,
        },
        GRAPH,
    )
    assert not result.checkpoint_reached


@pytest.mark.parametrize(
    "typed,channel",
    [
        (False, "assumptions"),
        (True, "assumptions"),
        (False, "runtime_facts"),
        (True, "runtime_facts"),
    ],
)
def test_assumption_source_required_on_every_input_channel(typed, channel):
    entry = assumption(provenance_reference=None)
    if typed:
        entry = RuntimeFact(**{**entry, "subject": ALIASES["Alice"], "target": ALIASES["Host"]})
    with pytest.raises(ValueError, match="requires provenance_reference"):
        materialize_query({**BASE, channel: [entry]}, GRAPH)


@pytest.mark.parametrize("source_key", ["declared_by", "source"])
def test_existing_metadata_can_identify_assumption_declarer(source_key):
    materialized = materialize_query(
        {
            **BASE,
            "runtime_facts": [],
            "assumptions": [
                assumption(
                    provenance_reference=None,
                    assumption_metadata={source_key: "synthetic fixture author"},
                )
            ],
        },
        GRAPH,
    )
    assert next(iter(materialized.runtime_context.facts.values())).value is True


@pytest.mark.parametrize("scope", ["", "missing-view"])
def test_invalid_view_selector_fails_closed(scope):
    with pytest.raises(ValueError, match="active_scope"):
        materialize_query(
            {**BASE, "assumptions": [assumption(assumption_metadata={"view_id": "known"})]},
            GRAPH,
            active_scope=scope,
        )


def test_evaluation_mode_cannot_be_changed_on_materialized_query():
    materialized = materialize_query({**BASE, "assumptions": [assumption()]}, GRAPH)
    with pytest.raises(ValueError, match="after materialization"):
        run_attack_query(materialized, GRAPH, evaluation_mode="evidence_only")
