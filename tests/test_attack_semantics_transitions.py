"""Behavioral acceptance tests for explicit attack transitions (Refs #63)."""

import copy
import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from src.data.manifest import generate_manifest
from src.engine.semantics import (
    AttackState,
    RuntimeContext,
    Status,
    TransitionRequest,
    apply_transition,
    evaluate,
    load_catalog,
    propagate_membership,
)
from src.engine.semantics.models import (
    ConfirmedAttack,
    EvidenceContext,
    ExpectedTelemetry,
    ObservedActivity,
    StructuralRelationship,
    TelemetryRecordLocator,
    TelemetryRecordRef,
    correlate_activity,
)

CATALOG = load_catalog()


def graph_for(kind, target_kind="Computer", source_kind="User"):
    return {
        "nodes": [
            {"id": "alice", "kind": source_kind, "enabled": True},
            {"id": "target", "kind": target_kind, "enabled": True},
        ],
        "edges": [{"source": "alice", "target": "target", "kind": kind}],
    }


def run(technique_id, graph, state=None, **overrides):
    technique = next(t for t in CATALOG if t.id == technique_id)
    facts = {(p, "alice", "target"): True for p in technique.prerequisites}
    for predicate, value in overrides.items():
        if value is None:
            facts.pop((predicate, "alice", "target"), None)
        else:
            facts[predicate, "alice", "target"] = value
    return evaluate(
        graph,
        state if state is not None else AttackState(control={"alice"}),
        TransitionRequest(technique_id, "alice", "alice", "target"),
        RuntimeContext(facts),
        CATALOG,
    )


@pytest.mark.parametrize("kind", ["User", "Computer", "Group"])
def test_nested_membership_cycles_silent_and_inherited_admin(kind):
    graph = {
        "nodes": [
            {"id": "alice", "kind": kind, "enabled": True},
            {"id": "g1", "kind": "Group"},
            {"id": "g2", "kind": "Group"},
            {"id": "host", "kind": "Computer"},
        ],
        "edges": [
            {"source": s, "target": t, "kind": k}
            for s, t, k in [
                ("alice", "g1", "MemberOf"),
                ("g1", "g2", "MemberOf"),
                ("g2", "g1", "MemberOf"),
                ("g2", "host", "AdminTo"),
            ]
        ],
    }
    original = copy.deepcopy(graph)
    context = RuntimeContext(
        {
            (p, "alice", target): True
            for target in ("g1", "g2", "host")
            for p in (
                "security_group",
                "membership_usable",
                "admin_channel",
                "authentication_accepted",
            )
        },
        authentication_context="host",
    )
    initial = AttackState(
        control={"alice"},
        usable_identity={("alice", "host")} if kind == "Computer" else set(),
    )
    closure = propagate_membership(graph, initial, context)
    assert closure.state.effective_member == {("alice", "g1"), ("alice", "g2")}
    assert closure.state.control == {"alice"}
    assert len(closure.transitions) == 3
    assert all(
        not r.technique.expected_telemetry and not r.technique.action_required
        for r in closure.transitions
    )
    assert initial.effective_member == frozenset()
    assert propagate_membership(graph, closure.state, context).state == closure.state
    request = TransitionRequest("obtain_admin_execution_on_host", "alice", "g2", "host")
    result = evaluate(graph, closure.state, request, context)
    assert result.additions.admin_control == {"host"}
    assert graph == original
    assert evaluate(graph, initial, request, context).status == Status.BLOCKED


@pytest.mark.parametrize(
    ("predicate", "value"),
    [
        ("security_group", False),
        ("membership_usable", False),
        ("security_group", None),
    ],
)
def test_membership_requires_security_and_usable_token(predicate, value):
    result = run(
        "propagate_group_entitlement", graph_for("MemberOf", "Group"), **{predicate: value}
    )
    assert result.status != Status.APPLICABLE
    assert not result.additions.effective_member


@pytest.mark.parametrize(
    ("technique", "kind", "guard"),
    [
        ("obtain_admin_execution_on_host", "AdminTo", "admin_channel"),
        ("obtain_admin_execution_on_host", "AdminTo", "authentication_accepted"),
        ("open_remote_interactive_session", "CanRDP", "rdp_available"),
        ("open_winrm_remote_session", "CanPSRemote", "winrm_available"),
        ("open_winrm_remote_session", "CanPSRemote", "authentication_accepted"),
    ],
)
@pytest.mark.parametrize("value", [False, None])
def test_host_runtime_false_blocks_unknown_is_indeterminate(technique, kind, guard, value):
    result = run(technique, graph_for(kind), **{guard: value})
    assert result.status == (Status.BLOCKED if value is False else Status.INDETERMINATE)
    assert result.additions == AttackState()
    assert apply_transition(result.before, result) == result.before


@pytest.mark.parametrize(
    ("technique", "kind", "field"),
    [
        ("open_remote_interactive_session", "CanRDP", "interactive_session"),
        ("open_winrm_remote_session", "CanPSRemote", "remote_command_execution"),
    ],
)
def test_remote_sessions_do_not_grant_admin(technique, kind, field):
    result = run(technique, graph_for(kind))
    assert result.status == Status.APPLICABLE
    after = apply_transition(result.before, result)
    assert getattr(after, field) == {("alice", "target")}
    assert not after.admin_control
    assert after.control == {"alice"}


def test_hassession_requires_host_admin_not_merely_a_session_or_principal_control():
    graph = graph_for("HasSession", "User", "Computer")
    for state in (
        AttackState(),
        AttackState(control={"alice"}),
        AttackState(interactive_session={("target", "alice")}),
    ):
        result = run("recover_session_credential_material", graph, state)
        assert "source_admin_control" in result.failed
        assert result.additions == AttackState()


@pytest.mark.parametrize("predicate", ["session_fresh", "session_present", "credential_accessible"])
@pytest.mark.parametrize("value", [False, None])
def test_hassession_freshness_availability_and_accessibility(predicate, value):
    result = run(
        "recover_session_credential_material",
        graph_for("HasSession", "User", "Computer"),
        AttackState(admin_control={"alice"}),
        **{predicate: value},
    )
    assert result.status != Status.APPLICABLE
    assert not result.additions.credential_material


def test_hassession_only_recovers_material():
    result = run(
        "recover_session_credential_material",
        graph_for("HasSession", "User", "Computer"),
        AttackState(admin_control={"alice"}),
    )
    assert result.status == Status.APPLICABLE
    assert result.additions.credential_material == {"target"}
    assert not result.additions.authentication_control
    assert not result.additions.control


@pytest.mark.parametrize("predicate", ["session_fresh", "session_present", "credential_accessible"])
@pytest.mark.parametrize("value", [False, None])
def test_hassession_runtime_facts_are_scoped_to_source_host(predicate, value):
    graph = {
        "nodes": [
            {"id": "alice", "kind": "User", "enabled": True},
            {"id": "carol", "kind": "User", "enabled": True},
            {"id": "host-a", "kind": "Computer"},
            {"id": "host-b", "kind": "Computer"},
        ],
        "edges": [
            {"source": host, "kind": "HasSession", "target": "carol"}
            for host in ("host-a", "host-b")
        ],
    }
    state = AttackState(control={"alice"}, admin_control={"host-a", "host-b"})
    predicates = ("session_fresh", "session_present", "credential_accessible")
    facts = {
        (name, subject, "carol"): True
        for name in predicates
        for subject in ("host-a", "host-b", "alice")
    }
    # Actor-scoped true facts must never override false/unknown host evidence.
    if value is None:
        del facts[predicate, "host-b", "carol"]
    else:
        facts[predicate, "host-b", "carol"] = value
    context = RuntimeContext(facts)
    request = TransitionRequest("recover_session_credential_material", "alice", "host-a", "carol")
    first = evaluate(graph, state, request, context)
    second = evaluate(graph, state, replace(request, source="host-b"), context)
    assert first.status == Status.APPLICABLE
    assert first.additions == AttackState(credential_material={"carol"})
    assert second.status == (Status.BLOCKED if value is False else Status.INDETERMINATE)
    assert predicate in (second.failed if value is False else second.unknown)
    assert second.additions == AttackState()
    # Host-scoped session evidence does not substitute for source admin control.
    uncontrolled = replace(state, admin_control=frozenset({"host-b"}))
    denied = evaluate(graph, uncontrolled, request, context)
    assert "source_admin_control" in denied.failed
    assert denied.additions == AttackState()


@pytest.mark.parametrize(
    ("kind", "technique"),
    [
        ("ForceChangePassword", "reset_target_password"),
        ("GenericAll", "genericall_reset_password"),
    ],
)
def test_password_reset_is_authentication_control_only(kind, technique):
    graph = graph_for(kind, "User")
    result = run(technique, graph)
    assert result.status == Status.APPLICABLE
    assert result.additions == AttackState(authentication_control={"target"})
    assert run(technique, graph, password_policy_accepts=False).status == Status.BLOCKED
    graph["nodes"][1]["enabled"] = False
    assert run(technique, graph).status == Status.BLOCKED


def test_write_dacl_derives_right_and_next_action_uses_it_without_graph_mutation():
    graph = graph_for("WriteDacl", "User")
    before = copy.deepcopy(graph)
    grant = run("grant_new_object_right", graph)
    state = apply_transition(grant.before, grant)
    right = StructuralRelationship("alice", "GenericAll", "target")
    assert state.relationship_added == {right}
    assert state.permission == {right}
    reset = run("genericall_reset_password", graph, state)
    assert reset.additions.authentication_control == {"target"}
    assert graph == before
    assert not grant.before.relationship_added
    assert (
        run("grant_new_object_right", graph, directory_write_allowed=False).additions
        == AttackState()
    )


def test_genericall_group_modification_requires_explicit_entitlement_refresh():
    graph = graph_for("GenericAll", "Group")
    result = run("genericall_add_member", graph)
    state = apply_transition(result.before, result)
    assert state.relationship_added == {StructuralRelationship("alice", "MemberOf", "target")}
    assert not state.effective_member and state.control == {"alice"}
    context = RuntimeContext({("security_group", "alice", "target"): True})
    assert not propagate_membership(graph, state, context).state.effective_member
    context = RuntimeContext({**context.facts, ("membership_usable", "alice", "target"): True})
    assert propagate_membership(graph, state, context).state.effective_member == {
        ("alice", "target")
    }


@pytest.mark.parametrize("kind", ["Computer", "Domain", "OU", "GPO"])
def test_genericall_non_user_only_derives_dacl_capability(kind):
    graph = graph_for("GenericAll", kind)
    result = run("genericall_grant_write_dacl", graph)
    assert result.additions.permission == {StructuralRelationship("alice", "WriteDacl", "target")}
    assert not result.additions.control and not result.additions.admin_control
    assert run("genericall_reset_password", graph).status == Status.BLOCKED


def test_disabled_actor_uncontrolled_actor_missing_edge_and_endpoint_are_blocked():
    graph = graph_for("CanRDP")
    assert run("open_remote_interactive_session", graph, AttackState()).status == Status.BLOCKED
    graph["nodes"][0]["enabled"] = False
    assert run("open_remote_interactive_session", graph).status == Status.BLOCKED
    graph["nodes"][0]["enabled"] = True
    graph["edges"] = []
    assert run("open_remote_interactive_session", graph).failed == ("relationship_missing",)
    graph["nodes"] = []
    assert "missing_endpoint" in run("open_remote_interactive_session", graph).failed


def test_telemetry_absence_does_not_change_applicability_or_infer_observation():
    result = run("reset_target_password", graph_for("ForceChangePassword", "User"))
    assert result.status == Status.APPLICABLE  # No observed activity was provided.
    assert result.technique.expected_telemetry
    assert isinstance(result.technique.expected_telemetry[0], ExpectedTelemetry)
    assert not isinstance(result, (ObservedActivity, ConfirmedAttack, StructuralRelationship))
    assert not hasattr(result.additions, "observed_activity")


def test_independent_telemetry_cannot_entity_join_and_matching_activity_is_not_confirmation(
    tmp_path,
):
    now = datetime(2026, 9, 21, tzinfo=UTC)
    context = EvidenceContext("lab-a", "snapshot-sids", now, now + timedelta(hours=1))
    telemetry_root = tmp_path / "telemetry"
    telemetry_root.mkdir()
    (telemetry_root / "evtx_data.csv").write_text(
        "EventID,Actor,Target\n4724,alice,target\n", encoding="utf-8"
    )
    telemetry_manifest = generate_manifest(
        telemetry_root,
        dataset_id="telemetry-test",
        collector_name="synthetic-telemetry",
        collector_version="1",
        collected_at="2026-09-21T00:00:00Z",
    )
    provenance = TelemetryRecordRef.from_manifest(
        telemetry_manifest,
        "evtx_data.csv",
        TelemetryRecordLocator("csv_row", 1),
        source=telemetry_root,
    )
    activity = ObservedActivity(
        "lab-a", "snapshot-sids", now, "alice", "target", "Security", 4724, provenance
    )
    assert correlate_activity(activity, context, "alice", "target")
    assert not correlate_activity(activity, context, "bob", "target")
    for changed in (
        replace(activity, environment_id="independent-lab"),
        replace(activity, identity_namespace="unverified-sids"),
        replace(activity, timestamp=now - timedelta(seconds=1)),
    ):
        with pytest.raises(ValueError, match="context"):
            correlate_activity(changed, context, "alice", "target")
    with pytest.raises(ValueError, match="timezone-aware"):
        replace(activity, timestamp=now.replace(tzinfo=None))
    for changed in (replace(context, environment_id=""), replace(context, identity_namespace="")):
        with pytest.raises(ValueError):
            correlate_activity(activity, changed, "alice", "target")
    assert not isinstance(activity, ConfirmedAttack)


def test_state_application_rejects_stale_branch_and_context_rejects_truthy_strings():
    result = run("open_remote_interactive_session", graph_for("CanRDP"))
    with pytest.raises(ValueError, match="different state"):
        apply_transition(AttackState(), result)
    with pytest.raises(ValueError, match="boolean"):
        RuntimeContext({("winrm_available", "alice", "target"): "false"})


def test_existing_m1_fixture_remains_unchanged_and_order_does_not_affect_closure():
    root = Path(__file__).resolve().parents[1]
    graph = json.loads((root / "data/samples/m1-fixtures.json").read_text())
    original = copy.deepcopy(graph)
    actors = {
        n["id"]
        for n in graph["nodes"]
        if n["kind"] in {"User", "Computer"} and n.get("enabled") is not False
    }
    context = RuntimeContext(
        {
            (p, actor, node["id"]): True
            for p in ("actor_enabled", "security_group", "membership_usable")
            for actor in actors
            for node in graph["nodes"]
        }
    )
    state = AttackState(control=actors)
    first = propagate_membership(graph, state, context)
    graph["edges"].reverse()
    second = propagate_membership(graph, state, context)
    assert first == second
    graph["edges"].reverse()
    assert graph == original
