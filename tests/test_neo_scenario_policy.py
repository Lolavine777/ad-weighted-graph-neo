"""Neo conditions missing group type without granting memberships or ACL rights."""

from dataclasses import replace

import pytest
from test_engine import ACTOR, GROUP, HOST, _edge, _graph
from test_identity_entitlement_goal import OTHER
from test_neo_effort import inputs

from src.engine.query import materialize_query, run_attack_query
from src.engine.ranking.effort_profiles import bind_effort_profile, load_effort_profile
from src.engine.semantics import Status, TransitionRequest, apply_transition, evaluate
from src.engine.semantics.credentials import replay_path
from src.engine.semantics.scenario_policy import (
    NEO_STANDARD_PROFILE,
    SEAMLESS_STANDARD_PROFILE,
    PolicyAssumptionResolver,
    apply_policy_to_query,
    load_policy_profile,
)

MID = "S-1-5-21-1000-2000-3000-2100"
MEMBER = "propagate_group_entitlement"
RESET = "scenario_reset_password"
ACTIVATE = "acquire_reset_identity"
WRITE = "grant_new_object_right"
ADD = "genericall_add_member"


def group_chain(label="Ordinary group"):
    graph, query = inputs("inherited")
    raw = graph.to_canonical()
    raw["nodes"].append(
        {
            **graph.node(GROUP),
            "id": MID,
            "label": label,
        }
    )
    raw["edges"] = [
        _edge(ACTOR, MID, "MemberOf"),
        _edge(MID, OTHER, "GenericAll"),
        _edge(OTHER, GROUP, "MemberOf"),
    ]
    graph = type(graph).from_canonical(raw)
    query.update(
        target=GROUP,
        target_goal={"target": GROUP, "kind": "usable_identity_entitlement"},
        initial_state={"control": [ACTOR], "usable_identity": [[ACTOR, HOST]]},
        assumptions=[],
        allowed_techniques=[MEMBER, RESET, ACTIVATE],
    )
    return graph, query


def compiled(graph, query, *, legacy=False):
    profile = SEAMLESS_STANDARD_PROFILE if legacy else NEO_STANDARD_PROFILE
    metadata = graph.metadata if hasattr(graph, "metadata") else graph["metadata"]
    profile = replace(profile, bound_snapshot_id=metadata["snapshot_id"])
    return apply_policy_to_query(query, graph, profile)


@pytest.mark.parametrize("label", ["Ordinary group", "HO-170-DISTLIST1"])
def test_missing_type_is_an_explicit_assumption_and_unlocks_reset_chain(label):
    graph, query = group_chain(label)
    before = run_attack_query(compiled(graph, query, legacy=True), graph)
    assert not before.paths
    neo = compiled(graph, query)
    assumed = next(
        f
        for f in neo["assumptions"]
        if (f["predicate"], f["subject"], f["target"]) == ("security_group", ACTOR, MID)
    )
    assert assumed["origin"] == "declared_assumption"
    assert (
        assumed["assumption_metadata"]["classification_basis"]
        == "scenario_assumed_missing_group_type"
    )
    assert "not observed" in assumed["rationale"]
    result = run_attack_query(
        bind_effort_profile(neo, graph, load_effort_profile("neo-c-v1")), graph
    )
    assert result.paths and result.min_effort["minimum_effort_value"] == 1
    for path in result.paths:
        assert replay_path(path, graph) == path.final_state
        assert MEMBER in [s.result.request.technique_id for s in path.transition_history]


@pytest.mark.parametrize(
    "attrs",
    [
        {"security_enabled": False},
        {"groupType": 2},
        {"properties": {"security_enabled": False}},
        {"properties": {"groupType": 8}},
    ],
)
def test_explicit_non_security_group_remains_unusable(attrs):
    graph, query = group_chain()
    # Group-type attributes are accepted by the policy's raw Mapping interface;
    # canonical EngineGraph currently carries a narrower node vocabulary.
    raw = graph.to_canonical()
    next(n for n in raw["nodes"] if n["id"] == MID).update(attrs)
    neo = compiled(raw, query)
    assert not any(
        f["predicate"] == "security_group" and f["target"] == MID for f in neo["assumptions"]
    )
    assert not run_attack_query(neo, graph).paths


@pytest.mark.parametrize("predicate", ["security_group", "membership_usable"])
def test_observed_false_vetoes_the_default(predicate):
    graph, query = group_chain()
    query["runtime_facts"] = [
        {
            "predicate": predicate,
            "subject": ACTOR,
            "target": MID,
            "value": False,
            "origin": "observed_evidence",
            "rationale": "Observed refusal",
            "provenance_reference": "synthetic://neo/group-false",
        }
    ]
    neo = compiled(graph, query)
    assert not run_attack_query(neo, graph).paths
    assert any(
        r["predicate"] == predicate and r["reason"] == "known_false_veto"
        for r in neo["scenario_policy_metadata"]["rejected_assumptions"]
    )


def test_explicit_assumption_cannot_override_non_security_attributes():
    graph, query = group_chain()
    raw = graph.to_canonical()
    next(n for n in raw["nodes"] if n["id"] == MID)["security_enabled"] = False
    query["assumptions"] = [
        {
            "predicate": "security_group",
            "subject": ACTOR,
            "target": MID,
            "value": True,
            "scope": "neo-finite",
            "rationale": "Contradictory override",
            "provenance_reference": "synthetic://contradictory-group",
        }
    ]
    with pytest.raises(ValueError, match="non-security attributes"):
        compiled(raw, query)


@pytest.mark.parametrize("missing", ["MemberOf", "GenericAll"])
def test_group_assumption_never_creates_a_structural_right(missing):
    graph, query = group_chain()
    raw = graph.to_canonical()
    raw["edges"] = [e for e in raw["edges"] if e["kind"] != missing]
    graph = type(graph).from_canonical(raw)
    assert not run_attack_query(compiled(graph, query), graph).paths


def acl_inputs():
    graph = _graph([_edge(ACTOR, GROUP, "WriteDacl")])
    _, query = inputs("membership")
    query.update(
        target=GROUP,
        target_goal={"target": GROUP, "kind": "usable_identity_entitlement"},
        initial_state={"control": [ACTOR], "usable_identity": [[ACTOR, HOST]]},
        assumptions=[],
        allowed_techniques=[WRITE, ADD, MEMBER],
    )
    return graph, query


def test_membership_gates_cover_rights_created_by_a_real_ACL_action():
    graph, query = acl_inputs()
    assert not run_attack_query(compiled(graph, query, legacy=True), graph).paths
    neo = compiled(graph, query)
    assert not any(f["predicate"] == "membership_change_allowed" for f in neo["assumptions"])
    material = materialize_query(neo, graph)
    attempted_add = evaluate(
        graph.to_prepared(),
        material.initial_attack_state,
        TransitionRequest(ADD, ACTOR, ACTOR, GROUP),
        material.runtime_context,
        material.catalog,
    )
    assert attempted_add.status == Status.BLOCKED
    state = material.initial_attack_state
    for technique in (WRITE, ADD, MEMBER):
        step = evaluate(
            graph.to_prepared(),
            state,
            TransitionRequest(technique, ACTOR, ACTOR, GROUP),
            material.runtime_context,
            material.catalog,
        )
        assert step.status == Status.APPLICABLE
        state = apply_transition(state, step)
    assert material.semantic_goal.matches(state)
    assert any(
        f.predicate == "membership_change_allowed" and str(f.origin) == "declared_assumption"
        for f in material.runtime_context.facts.values()
    )
    result = run_attack_query(
        bind_effort_profile(neo, graph, load_effort_profile("neo-c-v1")), graph
    )
    assert result.paths and result.min_effort["minimum_effort_value"] == 3
    assert not any(e["kind"] == "GenericAll" for e in graph.edges())
    for path in result.paths:
        replay_path(path, graph)


def test_false_membership_change_still_blocks_after_ACL():
    graph, query = acl_inputs()
    query["runtime_facts"] = [
        {
            "predicate": "membership_change_allowed",
            "subject": ACTOR,
            "target": GROUP,
            "value": False,
            "origin": "observed_evidence",
            "rationale": "Change forbidden",
            "provenance_reference": "synthetic://neo/no-member-add",
        }
    ]
    assert not run_attack_query(compiled(graph, query), graph).paths


def test_profile_roundtrip_and_lazy_group_lookup(tmp_path):
    assert "assume_missing_group_type_security" not in SEAMLESS_STANDARD_PROFILE.canonical_dict()
    graph, query = group_chain("HO-170-DISTLIST1")
    profile = replace(NEO_STANDARD_PROFILE, bound_snapshot_id=graph.metadata["snapshot_id"])
    path = tmp_path / "profile.json"
    path.write_text(profile.to_json())
    assert load_policy_profile(path) == profile
    resolver = PolicyAssumptionResolver(graph, query, profile)
    fact = resolver["security_group", ACTOR, MID]
    assert str(fact.origin) == "declared_assumption"
    assert fact.assumption_metadata["classification_basis"] == "scenario_assumed_missing_group_type"


def test_evidence_only_mode_does_not_activate_lazy_assumptions():
    graph, query = group_chain()
    neo = compiled(graph, query)
    neo["evaluation_mode"] = "evidence_only"
    assert not run_attack_query(neo, graph).paths


def two_reset_chain():
    graph, query = group_chain()
    raw = graph.to_canonical()
    second_group = "S-1-5-21-1000-2000-3000-2200"
    second_user = "S-1-5-21-1000-2000-3000-2300"
    raw["nodes"].extend(
        [
            {**graph.node(GROUP), "id": second_group},
            {**graph.node(OTHER), "id": second_user},
        ]
    )
    raw["edges"] = [
        _edge(ACTOR, MID, "MemberOf"),
        _edge(MID, OTHER, "GenericAll"),
        _edge(OTHER, second_group, "MemberOf"),
        _edge(second_group, second_user, "GenericAll"),
        _edge(second_user, GROUP, "MemberOf"),
    ]
    query.update(
        search_order="neo_guided",
        budget={
            "max_paths": 1,
            "max_steps": 8,
            "max_expansions": 256,
        },
    )
    return type(graph).from_canonical(raw), query, second_user


def test_existing_reset_policy_follows_an_acquired_identity():
    graph, query, second_user = two_reset_chain()
    neo = compiled(graph, query)
    # Eager compilation covers initial actors; this pair arises only after reset.
    assert not any(
        f["subject"] == OTHER
        and f["target"] == second_user
        and f["predicate"] == "password_policy_accepts"
        for f in neo["assumptions"]
    )
    result = run_attack_query(
        bind_effort_profile(neo, graph, load_effort_profile("neo-c-v1")), graph
    )
    assert result.final_goal_reached
    assert result.min_effort["minimum_effort_value"] == 2
    path = result.paths[0]
    reset = next(
        s
        for s in path.transition_history
        if s.result.request.technique_id == RESET and s.result.request.actor == OTHER
    )
    fact = next(d.fact for d in reset.result.decisions if d.predicate == "password_policy_accepts")
    assert fact.assumption_metadata["rule_id"] == "rule-typed-password-policy-accepts"
    assert replay_path(path, graph) == path.final_state


@pytest.mark.parametrize("predicate", ["password_policy_accepts", "network_rpc_reachable"])
def test_observed_false_still_blocks_a_second_reset(predicate):
    graph, query, second_user = two_reset_chain()
    query["runtime_facts"] = [
        {
            "predicate": predicate,
            "subject": OTHER,
            "target": second_user,
            "value": False,
            "origin": "observed_evidence",
            "provenance_reference": "synthetic://second-reset-denied",
        }
    ]
    assert not run_attack_query(compiled(graph, query), graph).paths


@pytest.mark.parametrize(
    "predicate", ["host_admin_mapping", "endpoint_authorized", "recovery_success"]
)
def test_group_fallback_does_not_expand_other_missing_conditions(predicate):
    graph, query = group_chain()
    material = materialize_query(compiled(graph, query), graph)
    assert material.runtime_context.facts.get((predicate, ACTOR, HOST)) is None


def test_serialized_policy_definition_cannot_drift_silently():
    graph, query = group_chain()
    neo = compiled(graph, query)
    neo["scenario_policy_metadata"]["profile"]["assume_missing_group_type_security"] = False
    with pytest.raises(ValueError, match="digest mismatch"):
        materialize_query(neo, graph)


@pytest.mark.parametrize("worker", [False, True])
def test_neo_profile_survives_batch_worker_and_resume(tmp_path, worker):
    from test_computer_foothold_boundary import CASES
    from test_machine_identity_profile import request, scenario

    from src.engine.batch import BatchExecutionBudget, run_source_goal_batch

    graph, query = scenario(CASES[2])
    req = request(graph, query)
    req["sources"][0]["declared_assumptions"] = []
    policy = replace(NEO_STANDARD_PROFILE, bound_snapshot_id=graph.metadata["snapshot_id"])
    options = {
        "allowed_techniques": [RESET, ACTIVATE, MEMBER],
        "scenario_policy": policy,
        "effort_profile": "neo-c-v1",
        "checkpoint": tmp_path / "batch.json",
        "execution_budget": BatchExecutionBudget(per_query_seconds=10) if worker else None,
    }
    result = run_source_goal_batch(req, graph, **options)
    assert result.summary["effort_rated_cells"] == result.summary["successful_cells"] == 1
    resumed = run_source_goal_batch(req, graph, resume=True, **options)
    assert resumed.source_goal_matrix == result.source_goal_matrix


def test_counterfactual_keeps_scenario_but_never_recreates_a_removed_right():
    from src.engine.remediation import _effective

    graph, query = acl_inputs()
    material = materialize_query(compiled(graph, query), graph)
    prepared, context, _ = _effective(
        {
            "request_id": "neo-deny-acl",
            "edits": [
                {"kind": "deny_relationship", "edit_id": "deny", "edge_id": graph.edges()[0]["id"]}
            ],
        },
        graph,
        material,
    )
    fact = context.facts.get(("membership_change_allowed", ACTOR, GROUP))
    assert fact is not None and str(fact.origin) == "declared_assumption"
    result = evaluate(
        prepared,
        material.initial_attack_state,
        TransitionRequest(ADD, ACTOR, ACTOR, GROUP),
        context,
        material.catalog,
    )
    assert result.status == Status.BLOCKED


def test_counterfactual_false_overrides_the_on_demand_default():
    from src.engine.remediation import _effective

    graph, query = acl_inputs()
    material = materialize_query(compiled(graph, query), graph)
    key = ("membership_change_allowed", ACTOR, GROUP)
    assert material.runtime_context.facts[key].value is True
    prepared, context, _ = _effective(
        {
            "request_id": "neo-deny-member-add",
            "edits": [
                {
                    "kind": "runtime_fact_replace",
                    "edit_id": "deny",
                    "rationale": "Member add denied",
                    "key": dict(zip(("predicate", "subject", "target"), key, strict=True)),
                    "after": False,
                }
            ],
        },
        graph,
        material,
    )
    assert context.facts[key].value is False
    first = evaluate(
        prepared,
        material.initial_attack_state,
        TransitionRequest(WRITE, ACTOR, ACTOR, GROUP),
        context,
        material.catalog,
    )
    assert first.status == Status.APPLICABLE
    denied = evaluate(
        prepared,
        apply_transition(first.before, first),
        TransitionRequest(ADD, ACTOR, ACTOR, GROUP),
        context,
        material.catalog,
    )
    assert denied.status == Status.BLOCKED and "membership_change_allowed" in denied.failed
