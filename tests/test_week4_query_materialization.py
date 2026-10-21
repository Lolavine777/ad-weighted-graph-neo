"""Unit and integration tests for Week 4 query materialization and fact resolution.

Verifies all mandatory invariants for Issue #211:
- Case A: source Computer does not infer usable identity.
- Case B: usable_identity is context-scoped, not global.
- Case C: missing runtime fact remains indeterminate.
- Case D: accepted declared assumption preserves provenance and enables applicability.
- Case E: authoritative false vetoes optimistic assumption; transition blocked.
- Case F: rejected assumption does not enter authoritative RuntimeContext as true.
- Case G: target asset and goal validation fails clearly for mismatched/unrelated goals.
- Case H: changing source/foothold dynamically drives search without ordered paths.
- Invariant 7: DA checkpoint reached does not report final asset compromise when final gate blocked.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.engine import (
    AttackQuery,
    MaterializedQuery,
    SearchBudget,
    materialize_query,
    run_attack_query,
)
from src.engine.semantics import (
    FactOrigin,
    load_catalog,
)
from src.engine.semantics.evaluator import evaluate
from src.engine.semantics.transitions import Status, TransitionRequest

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests/fixtures/attack_scenarios"
TWO_ROUTES_GRAPH_PATH = FIXTURES / "graphs/two-routes.json"
TWO_ROUTES_RAW = json.loads(TWO_ROUTES_GRAPH_PATH.read_text(encoding="utf-8"))

ALIASES = {
    "Alice": "S-1-5-21-1000-2000-3000-1101",
    "Bob": "S-1-5-21-1000-2000-3000-1102",
    "Helpdesk": "S-1-5-21-1000-2000-3000-2101",
    "Operators": "S-1-5-21-1000-2000-3000-2102",
    "Admins": "S-1-5-21-1000-2000-3000-2103",
    "Host": "10000000-0000-4000-8000-000000000002",
    "OtherHost": "10000000-0000-4000-8000-000000000003",
}

DEFAULT_RUNTIME_FACTS = [
    {
        "predicate": "admin_channel",
        "subject": "Alice",
        "target": "Host",
        "value": True,
        "origin": "observed_evidence",
        "scope": None,
        "rationale": "observed admin channel",
    },
    {
        "predicate": "authentication_accepted",
        "subject": "Alice",
        "target": "Host",
        "value": True,
        "origin": "observed_evidence",
        "scope": None,
        "rationale": "observed auth accepted",
    },
    {
        "predicate": "security_group",
        "subject": "Alice",
        "target": "Admins",
        "value": True,
        "origin": "observed_evidence",
        "scope": None,
        "rationale": "observed security group",
    },
    {
        "predicate": "membership_usable",
        "subject": "Alice",
        "target": "Admins",
        "value": True,
        "origin": "observed_evidence",
        "scope": None,
        "rationale": "observed usable membership",
    },
]


def test_case_a_source_computer_does_not_infer_usable_identity():
    """Case A: source foothold = Computer does not infer usable domain identity.

    Source is Host (Computer). Initial state has control(Host).
    No usable identity is supplied.
    Expected: materialized state has no usable identity, and search cannot actor-switch
    into domain users without credentials.
    """
    materialized = materialize_query(
        {
            "source_foothold": "Host",
            "initial_state": {"control": ["Host"]},
            "target": "Host",
            "target_goal": {
                "target": "Host",
                "required_state": {"admin_control": ["Host"]},
            },
            "aliases": ALIASES,
        },
        graph=TWO_ROUTES_RAW,
    )

    assert materialized.initial_actor == ALIASES["Host"]
    assert materialized.initial_attack_state.control == frozenset([ALIASES["Host"]])
    assert materialized.initial_attack_state.usable_identity == frozenset()

    # Search from Host cannot execute actions of Alice or Bob
    result = materialized.search(TWO_ROUTES_RAW)
    assert len(result.paths) == 0

    # Furthermore, attempt to declare Computer foothold with domain User actor
    # without identity capability raises validation error:
    with pytest.raises(ValueError, match="without declared usable_identity or control"):
        materialize_query(
            {
                "source_foothold": "Host",
                "initial_actor": "Alice",
                "initial_state": {"control": ["Host"]},
                "target": "Admins",
                "target_goal": {
                    "target": "Admins",
                    "required_state": {"admin_control": ["Host"]},
                },
                "aliases": ALIASES,
            },
            graph=TWO_ROUTES_RAW,
        )


def test_case_b_context_scoped_identity_not_globally_usable():
    """Case B: usable_identity(UserA, HostA) cannot be used in HostB auth context.

    Caller declares usable_identity(Alice, Host).
    Query requires authentication context OtherHost.
    Expected: Alice cannot authenticate in OtherHost context.
    """
    materialized = materialize_query(
        {
            "initial_actor": "Alice",
            "initial_state": {
                "usable_identity": [["Alice", "Host"]],
            },
            "authentication_context": "OtherHost",
            "target": "Host",
            "target_goal": {
                "target": "Host",
                "required_state": {"admin_control": ["Host"]},
            },
            "runtime_facts": DEFAULT_RUNTIME_FACTS,
            "aliases": ALIASES,
        },
        graph=TWO_ROUTES_RAW,
    )

    expected_scoped_identity = (ALIASES["Alice"], ALIASES["Host"])
    assert expected_scoped_identity in materialized.initial_attack_state.usable_identity
    assert materialized.runtime_context.authentication_context == ALIASES["OtherHost"]

    # Directly evaluate technique requiring actor_authenticated in OtherHost context
    catalog = load_catalog()
    winrm_technique = next((t for t in catalog if t.id == "scenario_winrm_admin"), None)
    assert winrm_technique is not None

    req = TransitionRequest(
        technique_id=winrm_technique.id,
        actor=ALIASES["Alice"],
        source=ALIASES["Alice"],
        target=ALIASES["Host"],
    )
    res = evaluate(
        TWO_ROUTES_RAW,
        materialized.initial_attack_state,
        req,
        materialized.runtime_context,
        catalog,
    )
    assert res.status == Status.BLOCKED
    assert "actor_authenticated" in res.failed


def test_case_c_missing_runtime_fact_yields_indeterminate():
    """Case C: required runtime fact missing with no assumption yields indeterminate."""
    # admin_channel is absent
    sparse_facts = [f for f in DEFAULT_RUNTIME_FACTS if f["predicate"] != "admin_channel"]

    materialized = materialize_query(
        {
            "initial_actor": "Alice",
            "initial_state": {"control": ["Alice"]},
            "target": "Host",
            "target_goal": {
                "target": "Host",
                "required_state": {"admin_control": ["Host"]},
            },
            "runtime_facts": sparse_facts,
            "aliases": ALIASES,
        },
        graph=TWO_ROUTES_RAW,
    )

    key = ("admin_channel", ALIASES["Alice"], ALIASES["Host"])
    assert key not in materialized.runtime_context.facts

    catalog = load_catalog()
    req = TransitionRequest(
        technique_id="obtain_admin_execution_on_host",
        actor=ALIASES["Alice"],
        source=ALIASES["Alice"],
        target=ALIASES["Host"],
    )
    res = evaluate(
        TWO_ROUTES_RAW,
        materialized.initial_attack_state,
        req,
        materialized.runtime_context,
        catalog,
    )
    assert res.status == Status.INDETERMINATE
    assert "admin_channel" in res.unknown


def test_case_d_accepted_assumption_preserves_provenance():
    """Case D: missing runtime fact with accepted assumption enables applicability.

    Assumption provenance, rationale and scope are preserved in RuntimeContext.
    """
    sparse_facts = [f for f in DEFAULT_RUNTIME_FACTS if f["predicate"] != "admin_channel"]
    assumptions = [
        {
            "predicate": "admin_channel",
            "subject": "Alice",
            "target": "Host",
            "value": True,
            "origin": "declared_assumption",
            "scope": "scenario-window-w4",
            "rationale": "Caller explicitly assumes WinRM channel connectivity",
            "evidence_ref": "bh-admin",
        }
    ]

    materialized = materialize_query(
        {
            "initial_actor": "Alice",
            "initial_state": {"control": ["Alice"]},
            "target": "Host",
            "target_goal": {
                "target": "Host",
                "required_state": {"admin_control": ["Host"]},
            },
            "runtime_facts": sparse_facts,
            "assumptions": assumptions,
            "aliases": ALIASES,
        },
        graph=TWO_ROUTES_RAW,
    )

    key = ("admin_channel", ALIASES["Alice"], ALIASES["Host"])
    resolved_fact = materialized.runtime_context.facts[key]
    assert resolved_fact.value is True
    assert resolved_fact.origin == FactOrigin.DECLARED_ASSUMPTION
    assert resolved_fact.scope == "scenario-window-w4"
    assert resolved_fact.rationale == "Caller explicitly assumes WinRM channel connectivity"
    assert len(materialized.rejected_assumptions) == 0

    catalog = load_catalog()
    req = TransitionRequest(
        technique_id="obtain_admin_execution_on_host",
        actor=ALIASES["Alice"],
        source=ALIASES["Alice"],
        target=ALIASES["Host"],
    )
    res = evaluate(
        TWO_ROUTES_RAW,
        materialized.initial_attack_state,
        req,
        materialized.runtime_context,
        catalog,
    )
    assert res.status == Status.APPLICABLE
    assert "admin_channel" in res.satisfied


def test_case_e_known_false_vetoes_optimistic_assumption():
    """Case E: authoritative false vetoes optimistic assumption.

    Authoritative fact = False, declared assumption = True.
    Resolved fact remains False, assumption rejected with diagnostic.
    """
    authoritative_facts = [
        *[f for f in DEFAULT_RUNTIME_FACTS if f["predicate"] != "admin_channel"],
        {
            "predicate": "admin_channel",
            "subject": "Alice",
            "target": "Host",
            "value": False,
            "origin": "observed_evidence",
            "scope": "scenario-window-w4",
            "rationale": "Network firewall probe recorded port 5985 blocked",
        },
    ]
    # Optimistic assumption attempts to assert True
    assumptions = [
        {
            "provenance_reference": "fixture:test_week4_query_materialization",
            "predicate": "admin_channel",
            "subject": "Alice",
            "target": "Host",
            "value": True,
            "origin": "declared_assumption",
            "scope": "scenario-window-w4",
            "rationale": "Optimistic penetration test assumption",
        }
    ]

    materialized = materialize_query(
        {
            "initial_actor": "Alice",
            "initial_state": {"control": ["Alice"]},
            "target": "Host",
            "target_goal": {
                "target": "Host",
                "required_state": {"admin_control": ["Host"]},
            },
            "runtime_facts": authoritative_facts,
            "assumptions": assumptions,
            "aliases": ALIASES,
        },
        graph=TWO_ROUTES_RAW,
    )

    # Invariant 3: resolved fact must be False
    key = ("admin_channel", ALIASES["Alice"], ALIASES["Host"])
    resolved_fact = materialized.runtime_context.facts[key]
    assert resolved_fact.value is False
    assert resolved_fact.origin == FactOrigin.OBSERVED_EVIDENCE

    # Invariant 4: assumption must be audited as rejected
    assert len(materialized.rejected_assumptions) == 1
    rejected = materialized.rejected_assumptions[0]
    assert rejected.predicate == "admin_channel"
    assert rejected.assumption_value is True
    assert rejected.reason == "known_false_veto"
    assert rejected.conflicting_fact is not None
    assert rejected.conflicting_fact.value is False

    # Evaluation is BLOCKED
    catalog = load_catalog()
    req = TransitionRequest(
        technique_id="obtain_admin_execution_on_host",
        actor=ALIASES["Alice"],
        source=ALIASES["Alice"],
        target=ALIASES["Host"],
    )
    res = evaluate(
        TWO_ROUTES_RAW,
        materialized.initial_attack_state,
        req,
        materialized.runtime_context,
        catalog,
    )
    assert res.status == Status.BLOCKED
    assert "admin_channel" in res.failed


def test_case_f_rejected_assumption_absent_from_runtime_context_authoritative_view():
    """Case F: rejected assumption does not appear as resolved true fact in RuntimeContext."""
    facts = [
        {
            "predicate": "network_winrm_reachable",
            "subject": "Alice",
            "target": "Host",
            "value": False,
            "origin": "blocked_evidence",
            "scope": "scenario-scope",
            "rationale": "port blocked by egress rule",
        }
    ]
    assumptions = [
        {
            "provenance_reference": "fixture:test_week4_query_materialization",
            "predicate": "network_winrm_reachable",
            "subject": "Alice",
            "target": "Host",
            "value": True,
            "origin": "declared_assumption",
            "scope": "scenario-scope",
            "rationale": "assume port open",
        }
    ]

    materialized = materialize_query(
        {
            "initial_actor": "Alice",
            "target": "Host",
            "target_goal": {
                "target": "Host",
                "required_state": {"admin_control": ["Host"]},
            },
            "runtime_facts": facts,
            "assumptions": assumptions,
            "aliases": ALIASES,
        },
        graph=TWO_ROUTES_RAW,
    )

    key = ("network_winrm_reachable", ALIASES["Alice"], ALIASES["Host"])
    fact_in_context = materialized.runtime_context.facts[key]
    assert fact_in_context.value is False
    assert fact_in_context.origin != FactOrigin.DECLARED_ASSUMPTION
    assert any(
        rej.predicate == "network_winrm_reachable" and rej.reason == "known_false_veto"
        for rej in materialized.rejected_assumptions
    )


def test_case_g_target_and_goal_validation():
    """Case G: malformed target/goal contracts fail with clear validation error."""
    # Subcase 1: target_goal references different target than query target
    with pytest.raises(ValueError, match="does not match query target"):
        materialize_query(
            {
                "initial_actor": "Alice",
                "target": "Host",
                "target_goal": {
                    "target": "OtherHost",
                    "required_state": {"admin_control": ["OtherHost"]},
                },
                "aliases": ALIASES,
            },
            graph=TWO_ROUTES_RAW,
        )

    # Subcase 2: target_goal required_state does not reference declared target asset
    with pytest.raises(ValueError, match="success predicate must reference target asset"):
        materialize_query(
            {
                "initial_actor": "Alice",
                "target": "Host",
                "target_goal": {
                    "target": "Host",
                    "required_state": {"admin_control": ["OtherHost"]},
                },
                "aliases": ALIASES,
            },
            graph=TWO_ROUTES_RAW,
        )

    # Subcase 3: empty required_state
    with pytest.raises(ValueError, match="target_goal requires non-empty required_state"):
        materialize_query(
            {
                "initial_actor": "Alice",
                "target": "Host",
                "target_goal": {
                    "target": "Host",
                    "required_state": {},
                },
                "aliases": ALIASES,
            },
            graph=TWO_ROUTES_RAW,
        )

    # Subcase 4: unknown target asset
    with pytest.raises((KeyError, ValueError)):
        materialize_query(
            {
                "initial_actor": "Alice",
                "target": "NonExistentServer",
                "target_goal": {
                    "target": "NonExistentServer",
                    "required_state": {"admin_control": ["NonExistentServer"]},
                },
                "aliases": ALIASES,
            },
            graph=TWO_ROUTES_RAW,
        )


def test_case_h_dynamic_search_driven_by_query_inputs():
    """Case H: altering query source/state dynamically alters generated candidates.

    Proves search is actively controlled by query parameters, not replaying fixed paths.
    """
    # Query 1: Alice has direct and group AdminTo access to Host
    q1 = {
        "initial_actor": "Alice",
        "initial_state": {"control": ["Alice"]},
        "target": "Host",
        "target_goal": {
            "target": "Host",
            "required_state": {"admin_control": ["Host"]},
        },
        "runtime_facts": DEFAULT_RUNTIME_FACTS,
        "aliases": ALIASES,
    }
    res1 = run_attack_query(q1, graph=TWO_ROUTES_RAW)
    assert res1.complete
    assert len(res1.paths) > 0
    assert res1.status == "success"

    # Query 2: Bob has no edges to Host or Admins in two-routes graph
    q2 = {
        "initial_actor": "Bob",
        "initial_state": {"control": ["Bob"]},
        "target": "Host",
        "target_goal": {
            "target": "Host",
            "required_state": {"admin_control": ["Host"]},
        },
        "runtime_facts": DEFAULT_RUNTIME_FACTS,
        "aliases": ALIASES,
    }
    res2 = run_attack_query(q2, graph=TWO_ROUTES_RAW)
    assert len(res2.paths) == 0
    assert res2.status == "no_path"

    # Reachable final states must be completely different
    states_1 = {p.final_state for p in res1.paths}
    states_2 = {p.final_state for p in res2.paths}
    assert states_1 != states_2


def test_invariant_7_da_checkpoint_not_final_asset_compromise():
    """Invariant 7: DA checkpoint reached does not report success when final gate blocked."""
    # Alice is member of Admins (DA checkpoint).
    # Final asset is Host, requiring admin_control(Host).
    # But admin_channel to Host is blocked (False).
    facts = [
        {
            "predicate": "admin_channel",
            "subject": "Alice",
            "target": "Host",
            "value": False,
            "origin": "blocked_evidence",
            "scope": "test-scope",
            "rationale": "admin channel blocked",
        },
        {
            "predicate": "security_group",
            "subject": "Alice",
            "target": "Admins",
            "value": True,
            "origin": "observed_evidence",
            "scope": "test-scope",
            "rationale": "security group observed",
        },
        {
            "predicate": "membership_usable",
            "subject": "Alice",
            "target": "Admins",
            "value": True,
            "origin": "observed_evidence",
            "scope": "test-scope",
            "rationale": "membership usable observed",
        },
    ]

    query = AttackQuery(
        target="Host",
        initial_actor="Alice",
        initial_state={"control": ["Alice"]},
        target_goal={
            "target": "Host",
            "required_state": {"admin_control": ["Host"]},
        },
        checkpoint_goal={
            "target": "Admins",
            "required_state": {"effective_member": [["Alice", "Admins"]]},
        },
        runtime_facts=facts,
        aliases=ALIASES,
    )

    result = run_attack_query(query, graph=TWO_ROUTES_RAW)

    # Invariant 7 assertion:
    assert result.checkpoint_reached is True
    assert result.final_goal_reached is False
    assert len(result.paths) == 0
    assert result.status != "success"
    assert result.status == "checkpoint_reached_final_goal_blocked"


def test_materialize_query_with_typed_dataclass():
    """Verify materialize_query directly accepts AttackQuery dataclass and runs."""
    query = AttackQuery(
        target="Host",
        initial_actor="Alice",
        initial_state={"control": ["Alice"]},
        target_goal={
            "target": "Host",
            "required_state": {"admin_control": ["Host"]},
        },
        runtime_facts=DEFAULT_RUNTIME_FACTS,
        budget=SearchBudget(max_paths=10, max_steps=6, max_expansions=100),
        aliases=ALIASES,
    )
    materialized = materialize_query(query, graph=TWO_ROUTES_RAW)
    assert isinstance(materialized, MaterializedQuery)
    assert materialized.budget.max_paths == 10
    assert materialized.target == ALIASES["Host"]

    res = materialized.run(TWO_ROUTES_RAW)
    assert res.final_goal_reached is True
    assert res.status == "success"


def test_canonical_ids_directly_without_aliases():
    """Verify materialize_query accepts canonical SIDs/GUIDs without an alias mapping."""
    query = {
        "initial_actor": ALIASES["Alice"],
        "initial_state": {"control": [ALIASES["Alice"]]},
        "target": ALIASES["Host"],
        "target_goal": {
            "target": ALIASES["Host"],
            "required_state": {"admin_control": [ALIASES["Host"]]},
        },
        "runtime_facts": [
            {
                "predicate": "admin_channel",
                "subject": ALIASES["Alice"],
                "target": ALIASES["Host"],
                "value": True,
                "origin": "observed_evidence",
                "scope": "test-scope",
                "rationale": "observed",
            },
            {
                "predicate": "authentication_accepted",
                "subject": ALIASES["Alice"],
                "target": ALIASES["Host"],
                "value": True,
                "origin": "observed_evidence",
                "scope": "test-scope",
                "rationale": "observed",
            },
        ],
    }
    materialized = materialize_query(query, graph=TWO_ROUTES_RAW)
    assert materialized.initial_actor == ALIASES["Alice"]
    assert materialized.target == ALIASES["Host"]
    result = materialized.search(TWO_ROUTES_RAW)
    assert len(result.paths) > 0


def test_unresolvable_identity_fails_fast():
    """Verify that an unknown display name or missing identity fails fast with clear error."""
    query = {
        "initial_actor": "UnknownUser123",
        "target": ALIASES["Host"],
        "target_goal": {
            "target": ALIASES["Host"],
            "required_state": {"admin_control": [ALIASES["Host"]]},
        },
    }
    with pytest.raises(ValueError, match="unresolvable identity reference"):
        materialize_query(query, graph=TWO_ROUTES_RAW)


def test_contradictory_assumptions_both_rejected():
    """Verify conflicting positive and negative assumptions are both rejected."""
    assumptions = [
        {
            "provenance_reference": "fixture:test_week4_query_materialization",
            "predicate": "winrm_available",
            "subject": "Alice",
            "target": "Host",
            "value": True,
            "origin": "declared_assumption",
            "scope": "scope-1",
            "rationale": "assume winrm true",
        },
        {
            "provenance_reference": "fixture:test_week4_query_materialization",
            "predicate": "winrm_available",
            "subject": "Alice",
            "target": "Host",
            "value": False,
            "origin": "declared_assumption",
            "scope": "scope-1",
            "rationale": "assume winrm false",
        },
    ]
    materialized = materialize_query(
        {
            "initial_actor": "Alice",
            "target": "Host",
            "target_goal": {
                "target": "Host",
                "required_state": {"admin_control": ["Host"]},
            },
            "assumptions": assumptions,
            "aliases": ALIASES,
        },
        graph=TWO_ROUTES_RAW,
    )
    key = ("winrm_available", ALIASES["Alice"], ALIASES["Host"])
    assert key not in materialized.runtime_context.facts
    assert len(materialized.rejected_assumptions) == 2
    assert all(r.reason == "contradictory_assumptions" for r in materialized.rejected_assumptions)


def test_evidence_only_mode_disallows_assumptions():
    """Verify evaluation_mode='evidence_only' rejects declared assumptions."""
    assumptions = [
        {
            "provenance_reference": "fixture:test_week4_query_materialization",
            "predicate": "winrm_available",
            "subject": "Alice",
            "target": "Host",
            "value": True,
            "origin": "declared_assumption",
            "scope": "scope-1",
            "rationale": "assume winrm true",
        }
    ]
    materialized = materialize_query(
        {
            "initial_actor": "Alice",
            "target": "Host",
            "target_goal": {
                "target": "Host",
                "required_state": {"admin_control": ["Host"]},
            },
            "assumptions": assumptions,
            "aliases": ALIASES,
        },
        graph=TWO_ROUTES_RAW,
        evaluation_mode="evidence_only",
    )
    key = ("winrm_available", ALIASES["Alice"], ALIASES["Host"])
    assert key not in materialized.runtime_context.facts
    assert len(materialized.rejected_assumptions) == 1
    assert materialized.rejected_assumptions[0].reason == "evidence_only_mode_disallows_assumptions"


def test_canonical_graph_immutability():
    """Verify materialization and search do not mutate the canonical graph."""
    import copy

    original_graph = copy.deepcopy(TWO_ROUTES_RAW)
    materialized = materialize_query(
        {
            "initial_actor": "Alice",
            "initial_state": {"control": ["Alice"]},
            "target": "Host",
            "target_goal": {
                "target": "Host",
                "required_state": {"admin_control": ["Host"]},
            },
            "runtime_facts": DEFAULT_RUNTIME_FACTS,
            "aliases": ALIASES,
        },
        graph=TWO_ROUTES_RAW,
    )
    result = materialized.search(TWO_ROUTES_RAW)
    assert len(result.paths) > 0
    assert TWO_ROUTES_RAW == original_graph


def test_week4_v1_fixture_scenario_consumption():
    """Verify Week 4 fixture scenarios can be directly consumed via materialize_query."""
    week4_pkg = FIXTURES / "week4-v1.json"
    suite = json.loads(week4_pkg.read_text(encoding="utf-8"))
    case = suite["scenarios"][0]  # w4-two-routes-exact
    binding = suite["graphs"][case["graph"]]
    graph = json.loads((FIXTURES / binding["path"]).read_text(encoding="utf-8"))
    aliases = binding["aliases"]

    query = {
        "initial_actor": case["initial_actor"],
        "initial_state": case["initial_state"],
        "authentication_context": case["authentication_context"],
        "target": case["target_goal"]["target"],
        "target_goal": case["target_goal"],
        "runtime_facts": case["runtime_facts"],
        "allowed_techniques": case["oracle_scope"]["techniques"],
        "budget": case["oracle_scope"]["budget"],
        "aliases": aliases,
    }

    materialized = materialize_query(query, graph=graph)
    assert materialized.initial_actor == aliases["Alice"]
    assert materialized.target == aliases["Host"]

    result = materialized.run(graph)
    assert result.complete
    assert result.final_goal_reached
    assert len(result.paths) > 0


def test_target_only_query_without_goal_predicate_fails_closed():
    """Verify target-only query without success predicate or goal is rejected fail-closed."""
    query = {
        "initial_actor": "Alice",
        "target": "Host",
        "aliases": ALIASES,
    }
    with pytest.raises(
        ValueError, match="requires an explicit success state predicate or target_goal"
    ):
        materialize_query(query, graph=TWO_ROUTES_RAW)


def test_target_goal_and_callable_predicate_conjunction_and():
    """Verify conjunction of target_goal and callable predicate:
    callable cannot bypass required_state.
    """
    query = {
        "initial_actor": "Alice",
        "target": "Host",
        "target_goal": {
            "target": "Host",
            "required_state": {"admin_control": ["Host"]},
        },
        # Callable requires an unattainable state that is never reached in the graph
        "success_state_predicate": lambda state: "unattainable_capability" in state.control,
        "runtime_facts": DEFAULT_RUNTIME_FACTS,
        "aliases": ALIASES,
    }
    materialized = materialize_query(query, graph=TWO_ROUTES_RAW)
    result = materialized.run(TWO_ROUTES_RAW)
    # Even though admin_control(Host) was achieved on target node, callable was not satisfied
    assert not result.final_goal_reached
    assert len(result.paths) == 0


def test_truncated_query_returns_truncated_outcome_never_terminal():
    """Verify incomplete/truncated search returns 'truncated' outcome
    and never claims no_path/blocked.
    """
    sparse_facts = [
        # Direct route blocked so it requires multi-step route via Admins
        {
            "predicate": "admin_channel",
            "subject": "Alice",
            "target": "Host",
            "value": False,
            "origin": "observed_evidence",
            "scope": None,
            "rationale": "blocked direct admin channel",
        },
        {
            "predicate": "security_group",
            "subject": "Alice",
            "target": "Admins",
            "value": True,
            "origin": "observed_evidence",
            "scope": None,
            "rationale": "group true",
        },
        {
            "predicate": "membership_usable",
            "subject": "Alice",
            "target": "Admins",
            "value": True,
            "origin": "observed_evidence",
            "scope": None,
            "rationale": "usable",
        },
    ]
    query = {
        "initial_actor": "Alice",
        "target": "Host",
        "target_goal": {
            "target": "Host",
            "required_state": {"admin_control": ["Host"]},
        },
        "budget": {"max_steps": 1},
        "runtime_facts": sparse_facts,
        "aliases": ALIASES,
    }
    result = run_attack_query(query, graph=TWO_ROUTES_RAW)
    assert result.truncated
    assert not result.complete
    assert result.status == "truncated"
    assert result.status not in ("no_path", "blocked", "checkpoint_reached_final_goal_blocked")


def test_mixed_blocked_and_indeterminate_aggregates_to_indeterminate():
    """Verify conservative lattice: if any candidate route is indeterminate,
    query outcome is indeterminate, not blocked.
    """
    sparse_facts = [
        # AdminTo direct route: missing admin_channel -> INDETERMINATE
        {
            "predicate": "authentication_accepted",
            "subject": "Alice",
            "target": "Host",
            "value": True,
            "origin": "observed_evidence",
            "scope": None,
            "rationale": "auth accepted",
        },
        # Group MemberOf route prerequisite: security_group = False -> BLOCKED
        {
            "predicate": "security_group",
            "subject": "Alice",
            "target": "Admins",
            "value": False,
            "origin": "observed_evidence",
            "scope": None,
            "rationale": "group not security enabled",
        },
    ]
    query = {
        "initial_actor": "Alice",
        "target": "Host",
        "target_goal": {
            "target": "Host",
            "required_state": {"admin_control": ["Host"]},
        },
        "runtime_facts": sparse_facts,
        "aliases": ALIASES,
    }
    result = run_attack_query(query, graph=TWO_ROUTES_RAW)
    statuses = {attempt.status for attempt in result.attempts}
    assert Status.BLOCKED in statuses
    assert Status.INDETERMINATE in statuses
    # Conservative lattice: INDETERMINATE must not be overshadowed by BLOCKED noise
    assert result.status == "indeterminate"


def test_assumption_origin_spoofing_raises_value_error():
    """Verify declaring an assumption with origin='observed_evidence' is rejected fail-closed."""
    assumptions = [
        {
            "predicate": "admin_channel",
            "subject": "Alice",
            "target": "Host",
            "value": True,
            "origin": "observed_evidence",
            "scope": "test-scope",
            "rationale": "spoofed origin",
        }
    ]
    query = {
        "initial_actor": "Alice",
        "target": "Host",
        "target_goal": {
            "target": "Host",
            "required_state": {"admin_control": ["Host"]},
        },
        "assumptions": assumptions,
        "aliases": ALIASES,
    }
    with pytest.raises(ValueError, match="cannot claim origin 'observed_evidence'"):
        materialize_query(query, graph=TWO_ROUTES_RAW)


def test_cross_scope_mixing_without_active_scope_rejected():
    """Verify assumptions with multiple distinct scopes without active_scope
    are rejected fail-closed.
    """
    assumptions = [
        {
            "provenance_reference": "fixture:test_week4_query_materialization",
            "assumption_metadata": {"view_id": "view-1"},
            "predicate": "admin_channel",
            "subject": "Alice",
            "target": "Host",
            "value": True,
            "origin": "declared_assumption",
            "scope": "view-1",
            "rationale": "branch 1",
        },
        {
            "provenance_reference": "fixture:test_week4_query_materialization",
            "assumption_metadata": {"view_id": "view-2"},
            "predicate": "admin_channel",
            "subject": "Alice",
            "target": "Host",
            "value": False,
            "origin": "declared_assumption",
            "scope": "view-2",
            "rationale": "branch 2",
        },
    ]
    query = {
        "initial_actor": "Alice",
        "target": "Host",
        "target_goal": {
            "target": "Host",
            "required_state": {"admin_control": ["Host"]},
        },
        "assumptions": assumptions,
        "aliases": ALIASES,
    }
    with pytest.raises(ValueError, match="multiple scenario views"):
        materialize_query(query, graph=TWO_ROUTES_RAW)


def test_cross_scope_with_active_scope_isolates_view():
    """Verify specifying active_scope isolates the view and prevents cross-scope veto."""
    facts = [
        {
            "predicate": "admin_channel",
            "subject": "Alice",
            "target": "Host",
            "value": False,
            "origin": "observed_evidence",
            "scope": "view-2",
            "rationale": "blocked in view-2",
            "assumption_metadata": {"view_id": "view-2"},
        }
    ]
    assumptions = [
        {
            "provenance_reference": "fixture:test_week4_query_materialization",
            "assumption_metadata": {"view_id": "view-1"},
            "predicate": "admin_channel",
            "subject": "Alice",
            "target": "Host",
            "value": True,
            "origin": "declared_assumption",
            "scope": "view-1",
            "rationale": "optimistic in view-1",
        }
    ]
    materialized = materialize_query(
        {
            "initial_actor": "Alice",
            "target": "Host",
            "target_goal": {
                "target": "Host",
                "required_state": {"admin_control": ["Host"]},
            },
            "runtime_facts": facts,
            "assumptions": assumptions,
            "active_scope": "view-1",
            "aliases": ALIASES,
        },
        graph=TWO_ROUTES_RAW,
    )
    key = ("admin_channel", ALIASES["Alice"], ALIASES["Host"])
    # View-2 authoritative false does NOT veto view-1 assumption
    assert key in materialized.runtime_context.facts
    assert materialized.runtime_context.facts[key].value is True
    assert len(materialized.rejected_assumptions) == 0


def test_invalid_evaluation_mode_raises_value_error():
    """Verify misspelled evaluation_mode raises ValueError fail-closed."""
    query = {
        "initial_actor": "Alice",
        "target": "Host",
        "target_goal": {
            "target": "Host",
            "required_state": {"admin_control": ["Host"]},
        },
        "evaluation_mode": "evidence_onyl",
        "aliases": ALIASES,
    }
    with pytest.raises(ValueError, match="invalid evaluation_mode"):
        materialize_query(query, graph=TWO_ROUTES_RAW)


def test_unknown_allowed_technique_raises_value_error():
    """Verify unknown technique ID in allowed_techniques raises ValueError fail-closed."""
    query = {
        "initial_actor": "Alice",
        "target": "Host",
        "target_goal": {
            "target": "Host",
            "required_state": {"admin_control": ["Host"]},
        },
        "allowed_techniques": ["obtain_admin_execution_on_host", "non_existent_technique_typo"],
        "aliases": ALIASES,
    }
    with pytest.raises(ValueError, match="unknown technique IDs in allowed_techniques"):
        materialize_query(query, graph=TWO_ROUTES_RAW)
