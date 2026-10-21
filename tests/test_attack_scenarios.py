"""Independent golden oracle, discovery and deliberate regression counterexamples."""

import json
from copy import deepcopy
from dataclasses import replace

import pytest

from scripts.check_contract import canonical_edge_id
from scripts.research.attack_scenarios import (
    DEFAULT,
    contains,
    digest,
    load_suite,
    materialize,
    run_case,
    state_from,
    validate_suite,
)
from src.engine import EngineGraph, SearchBudget, generate_attack_paths
from src.engine.semantics import AttackState, RuntimeContext, RuntimeFact, load_catalog
from src.engine.semantics.evaluator import evaluate
from src.engine.semantics.models import StructuralRelationship
from src.engine.semantics.transitions import TransitionRequest

SUITE = load_suite()
CASES = [(c, v) for c in SUITE["scenarios"] for v in c["variants"]]


@pytest.mark.parametrize(
    "case,variant", CASES, ids=[f"{c['scenario_id']}/{v['variant_id']}" for c, v in CASES]
)
def test_golden_transition_and_real_search(case, variant):
    assert run_case(SUITE, case, variant)["complete"]


def case_named(name):
    return next(c for c in SUITE["scenarios"] if c["scenario_id"] == name)


def inputs(name):
    case = case_named(name)
    binding = SUITE["graphs"][case["graph"]]
    aliases = binding["aliases"]
    graph = json.loads((DEFAULT.parent / binding["path"]).read_text(encoding="utf-8"))
    _, facts = materialize(case, case["variants"][0])
    context = RuntimeContext(
        [
            RuntimeFact(
                f["predicate"],
                aliases[f["subject"]],
                aliases[f["target"]],
                f["value"],
                f["origin"],
                scope=f["scope"],
                rationale=f["rationale"],
                provenance_reference=f["evidence_ref"],
            )
            for f in facts
        ],
        authentication_context=aliases.get(case["authentication_context"]),
    )
    return case, aliases, graph, context


def search(case, aliases, graph, context, *, exclude=(), state=None, budget=None):
    goal = state_from(case["target_goal"]["required_state"], aliases)
    return generate_attack_paths(
        EngineGraph.from_canonical(graph),
        aliases[case["initial_actor"]],
        initial_state=state if state is not None else state_from(case["initial_state"], aliases),
        runtime_context=context,
        target_predicate=lambda n: n["id"] == aliases[case["target_goal"]["target"]],
        success_state_predicate=lambda s: contains(s, goal),
        budget=budget or SearchBudget(**case["oracle_scope"]["budget"]),
        catalog=tuple(
            t
            for t in load_catalog()
            if t.id in case["oracle_scope"]["techniques"] and t.id not in exclude
        ),
    )


def test_counterfactual_same_graph_different_foothold_and_host_control():
    for name, variant_id in (
        ("acl-auth-host", "no-foothold"),
        ("session-material", "without-host-admin"),
        ("no-route", "initial-success"),
    ):
        case = case_named(name)
        positive = run_case(SUITE, case, case["variants"][0])
        other = run_case(
            SUITE, case, next(v for v in case["variants"] if v["variant_id"] == variant_id)
        )
        assert positive["graph_digest"] == other["graph_digest"]
        assert positive["reachable_states"] != other["reachable_states"]
        assert positive["outcome"] != other["outcome"]


@pytest.mark.parametrize(
    "owner",
    [
        "scenario_reset_password",
        "acquire_reset_identity",
        "propagate_group_entitlement",
        "grant_new_object_right",
    ],
)
def test_removing_causal_owner_prevents_host_success(owner):
    case, aliases, graph, context = inputs("acl-auth-host")
    result = search(case, aliases, graph, context, exclude=(owner,))
    assert result.complete and not result.paths


@pytest.mark.parametrize("mutation", ["reverse", "kind"])
def test_direction_and_kind_are_not_interchangeable(mutation):
    case, aliases, graph, context = inputs("direct-admin")
    edge = graph["edges"][0]
    if mutation == "reverse":
        # AdminTo Computer -> User is not contract-compatible; check transition
        # direction using another valid principal -> Computer binding instead.
        edge["source"] = aliases["Bob"]
    else:
        edge["kind"] = "CanRDP"
    edge["id"] = canonical_edge_id(edge["source"], edge["target"], edge["kind"])
    result = search(case, aliases, graph, context)
    assert result.complete and not result.paths
    actual = evaluate(
        graph,
        state_from(case["initial_state"], aliases),
        TransitionRequest(
            "obtain_admin_execution_on_host", aliases["Alice"], aliases["Alice"], aliases["Host"]
        ),
        context,
    )
    assert "relationship_missing" in actual.failed


def test_reversed_acl_does_not_authorize_original_actor():
    case, aliases, graph, context = inputs("genericall-user")
    edge = graph["edges"][0]
    edge["source"], edge["target"] = edge["target"], edge["source"]
    edge["id"] = canonical_edge_id(edge["source"], edge["target"], edge["kind"])
    result = search(case, aliases, graph, context)
    assert result.complete and not result.paths


def test_search_accepts_remaining_valid_alternative():
    case, aliases, graph, context = inputs("two-routes")
    graph["edges"] = [
        e
        for e in graph["edges"]
        if not (e["source"] == aliases["Alice"] and e["kind"] == "AdminTo")
    ]
    result = search(case, aliases, graph, context)
    assert result.complete and result.paths
    assert {tuple(s.result.technique.id for s in p.transition_history) for p in result.paths} == {
        ("propagate_group_entitlement", "obtain_admin_execution_on_host")
    }


def test_known_false_snapshot_veto_and_contradictory_runtime_rejected():
    case, aliases, graph, context = inputs("genericall-user")
    next(n for n in graph["nodes"] if n["id"] == aliases["Bob"])["enabled"] = False
    optimistic = RuntimeFact(
        "target_enabled",
        aliases["Alice"],
        aliases["Bob"],
        True,
        "declared_assumption",
        scope="fixed-window",
        rationale="deliberately optimistic",
    )
    modified = RuntimeContext([*context.facts.values(), optimistic])
    result = search(case, aliases, graph, modified)
    assert result.complete and not result.paths
    assert any(
        "target_enabled" in a.failed and a.additions == AttackState() for a in result.attempts
    )
    with pytest.raises(ValueError, match="contradictory"):
        RuntimeContext([optimistic, replace(optimistic, value=False, origin="blocked_evidence")])


@pytest.mark.parametrize("change", ["actor", "host", "auth-context"])
def test_scoped_assumptions_and_identity_do_not_authorize_other_context(change):
    case, aliases, graph, context = inputs("acl-auth-host")
    if change == "auth-context":
        context = RuntimeContext(
            list(context.facts.values()), authentication_context=aliases["OtherHost"]
        )
    else:
        facts = [
            replace(f, subject=aliases["Alice"])
            if change == "actor" and f.subject == aliases["Bob"]
            else replace(f, target=aliases["OtherHost"])
            if change == "host" and f.target == aliases["Host"]
            else f
            for f in context.facts.values()
        ]
        context = RuntimeContext(facts, authentication_context=context.authentication_context)
    result = search(case, aliases, graph, context)
    assert result.complete and not result.paths
    assert any(a.unknown or "actor_authenticated" in a.failed for a in result.attempts)


def test_wrong_scoped_initial_identity_cannot_use_inherited_right():
    case, aliases, graph, context = inputs("acl-auth-host")
    request = TransitionRequest(
        "scenario_winrm_admin", aliases["Bob"], aliases["Admins"], aliases["Host"]
    )
    state = AttackState(
        usable_identity={(aliases["Bob"], aliases["OtherHost"])},
        effective_member={(aliases["Bob"], aliases["Admins"])},
    )
    result = evaluate(graph, state, request, context)
    assert {"actor_controlled", "actor_authenticated"} <= set(result.failed)
    assert result.additions == AttackState()


def test_initial_success_is_zero_action_with_unique_target():
    case, aliases, graph, context = inputs("no-route")
    result = search(
        case,
        aliases,
        graph,
        context,
        state=AttackState(admin_control={aliases["Host"]}),
        budget=SearchBudget(1, 1, 1),
    )
    assert result.complete and len(result.paths) == 1 and result.expansions == 0
    path = result.paths[0]
    assert path.target == aliases["Host"] and not path.transition_history and not path.edges
    assert path.final_state == AttackState(admin_control={aliases["Host"]})


@pytest.mark.parametrize("max_paths", [1, 10])
def test_initial_success_rejects_ambiguous_two_target_attribution(max_paths):
    _, aliases, graph, context = inputs("no-route")
    computers = {n["id"] for n in graph["nodes"] if n["kind"] == "Computer"}
    assert computers == {aliases["Host"], aliases["OtherHost"]}
    state = AttackState(admin_control={aliases["Host"]})
    original = deepcopy(graph)
    with pytest.raises(ValueError, match="zero-action success requires a unique target"):
        generate_attack_paths(
            EngineGraph.from_canonical(graph),
            aliases["Alice"],
            initial_state=state,
            runtime_context=context,
            target_predicate=lambda n: n["kind"] == "Computer",
            success_state_predicate=lambda s: aliases["Host"] in s.admin_control,
            budget=SearchBudget(max_paths, 1, 1),
        )
    assert graph == original
    assert state == AttackState(admin_control={aliases["Host"]})


def test_initial_success_without_matching_target_does_not_synthesize_asset():
    _, aliases, graph, context = inputs("no-route")
    result = generate_attack_paths(
        EngineGraph.from_canonical(graph),
        aliases["Alice"],
        initial_state=AttackState(admin_control={aliases["Host"]}),
        runtime_context=context,
        target_predicate=lambda n: False,
        success_state_predicate=lambda s: aliases["Host"] in s.admin_control,
        budget=SearchBudget(1, 1, 1),
    )
    assert result.complete and not result.paths


def test_truncation_is_incomplete_and_harness_rejects_no_path_claim():
    case, aliases, graph, context = inputs("acl-auth-host")
    result = search(case, aliases, graph, context, budget=SearchBudget(1, 1, 1))
    assert result.truncated and not result.complete and not result.paths
    broken = deepcopy(case)
    broken["oracle_scope"]["budget"] = dict(max_paths=1, max_steps=1, max_expansions=1)
    with pytest.raises(AssertionError, match="incomplete/truncated"):
        run_case(SUITE, broken, broken["variants"][0])


@pytest.mark.parametrize(
    "defect",
    [
        "unknown",
        "bad-actor",
        "bad-state",
        "bad-edge",
        "bad-owner",
        "bad-evidence",
        "ambiguous",
        "non-applicable-effect",
        "bad-delta",
        "bad-pin",
        "bad-path",
        "duplicate-fact",
        "unknown-nested",
        "invalid-kind",
        "wrong-state-kind",
        "wrong-goal",
        "zero-action-without-goal",
        "wrong-derived-parent",
        "duplicate-request",
    ],
)
def test_real_validator_rejects_contract_defects(defect):
    suite = deepcopy(SUITE)
    case = suite["scenarios"][0]
    step = case["steps"][0]
    variant = case["variants"][0]
    if defect == "unknown":
        case["observed_log_required"] = True
    elif defect == "bad-actor":
        case["initial_actor"] = "missing"
    elif defect == "bad-state":
        case["initial_state"] = {"usable_identity": [["Alice"]]}
    elif defect == "bad-edge":
        step["edge_id"] = "unknown"
    elif defect == "bad-owner":
        step["request"]["technique_id"] = "invented"
    elif defect == "bad-evidence":
        step["evidence_refs"] = ["missing"]
    elif defect == "ambiguous":
        variant["expected_search"]["outcome"] = "unknown-or-success"
    elif defect == "non-applicable-effect":
        step["expected"]["status"] = "blocked"
    elif defect == "bad-delta":
        variant["fact_changes"] = [{"key": ["missing", "Alice", "Host"], "operation": "remove"}]
    elif defect == "bad-pin":
        suite["bindings"]["catalog_digest"] = "sha256:" + "0" * 64
    elif defect == "bad-path":
        variant["expected_search"]["acceptable_paths"] = [["invented"]]
    elif defect == "duplicate-fact":
        case["runtime_facts"].append(deepcopy(case["runtime_facts"][0]))
    elif defect == "unknown-nested":
        step["expected"]["probability"] = 1
    elif defect == "invalid-kind":
        case["initial_state"] = {"permission": [["Alice", "AuthenticationControl", "Bob"]]}
    elif defect == "wrong-state-kind":
        case["initial_state"] = {"effective_member": [["Alice", "Host"]]}
    elif defect == "wrong-goal":
        case["target_goal"]["required_state"] = {"admin_control": ["OtherHost"]}
    elif defect == "zero-action-without-goal":
        variant["expected_search"]["acceptable_paths"] = [[]]
    elif defect == "wrong-derived-parent":
        chain = next(c for c in suite["scenarios"] if c["scenario_id"] == "acl-auth-host")
        next(s for s in chain["steps"] if s["step_id"] == "reset")["derived_from"] = "helpdesk"
    elif defect == "duplicate-request":
        duplicate = deepcopy(step)
        duplicate["step_id"] = "another-id"
        case["steps"].append(duplicate)
    with pytest.raises(ValueError):
        validate_suite(suite, DEFAULT.parent)


def test_catalog_scope_covers_all_accepted_owners_and_eight_structural_kinds():
    ids = {i for c in SUITE["scenarios"] for i in c["oracle_scope"]["techniques"]}
    from src.engine.semantics.credentials import OWNERS
    from src.engine.semantics.rbcd import OWNERS as RBCD_OWNERS

    # Extension owners have their independent #216/#229 oracle; core expected programs stay frozen.
    assert ids | OWNERS | RBCD_OWNERS == {t.id for t in load_catalog()}
    kinds = set()
    for g in SUITE["graphs"].values():
        graph = json.loads((DEFAULT.parent / g["path"]).read_text(encoding="utf-8"))
        kinds.update(e["kind"] for e in graph["edges"])
        assert digest(graph) == g["digest"]
    assert kinds == {
        "MemberOf",
        "GenericAll",
        "ForceChangePassword",
        "WriteDacl",
        "AdminTo",
        "CanRDP",
        "CanPSRemote",
        "HasSession",
    }


def test_deterministic_prediction_report():
    case = case_named("membership-cycle-diamond")
    assert run_case(SUITE, case, case["variants"][0]) == run_case(SUITE, case, case["variants"][0])


def test_wrong_oracle_is_not_silently_relearned():
    case = deepcopy(case_named("direct-admin"))
    case["steps"][0]["expected"]["additions"] = {"control": ["Host"]}
    with pytest.raises(AssertionError):
        run_case(SUITE, case, case["variants"][0])


def test_initial_derived_permission_does_not_modify_snapshot():
    case, aliases, graph, context = inputs("genericall-user")
    graph["edges"] = []
    baseline = digest(graph)
    state = AttackState(
        control={aliases["Alice"]},
        permission={StructuralRelationship(aliases["Alice"], "GenericAll", aliases["Bob"])},
    )
    result = search(case, aliases, graph, context, state=state)
    assert result.complete and result.paths and digest(graph) == baseline
    assert result.paths[0].transition_history[0].edge_id is None
