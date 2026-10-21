"""Finite, independent capability oracle for a Computer-to-group scenario.

This intentionally models three actions, not the native catalog or its candidate
generator. A local shell/admin atom cannot satisfy a network-identity atom.
"""

import copy
from dataclasses import dataclass

import pytest
from test_engine import ACTOR, GROUP, HOST, TOY, _edge, _graph

from scripts.research.source_goal_batch import create_foothold_profile
from src.engine.query import run_attack_query
from src.engine.query_cli import execute, wire
from src.engine.semantics.credentials import replay_path

OTHER_HOST = "10000000-0000-4000-8000-000000000003"
OTHER_USER = "S-1-5-21-1000-2000-3000-1102"
TECHNIQUES = [
    "scenario_reset_password",
    "acquire_reset_identity",
    "propagate_group_entitlement",
]


@dataclass(frozen=True)
class Case:
    name: str
    profile: str = "computer_control_user"
    identity: str = "absent"
    rpc: bool | None = True
    target_enabled: bool = True
    fake_runtime_identity: bool = False


CASES = (
    Case("local_shell_only"),
    Case("local_admin_only", profile="computer_control_admin"),
    Case("explicit_machine_identity", identity="same_context"),
    Case("foreign_context_identity", identity="foreign_context"),
    Case("identity_unknown", identity="unknown"),
    Case("missing_context", identity="missing_context"),
    Case("rpc_false", identity="same_context", rpc=False),
    Case("rpc_unknown", identity="same_context", rpc=None),
    Case("disabled_target_veto", identity="same_context", target_enabled=False),
    Case("runtime_fact_cannot_grant_identity", fake_runtime_identity=True),
    Case("foreign_unknown_identity", identity="foreign_unknown"),
    Case("explicit_user_switch", identity="other_user"),
)


def oracle(case):
    """AND-precondition closure twice: definite facts and possible Unknown facts.

    No AWG generator, evaluator, state type or cost helper participates here.
    Machine identity is declared separately from either local execution level.
    """
    facts = {
        "network_identity": True
        if case.identity in {"same_context", "other_user"}
        else None
        if case.identity in {"unknown", "missing_context"}
        else False,
        "acl": True,
        "directory_write": True,
        "password_policy": True,
        "rpc": case.rpc,
        "target_enabled": case.target_enabled,
        "activation_network": True,
        "activation_accepted": True,
        "security_group": True,
        "membership_usable": True,
    }
    actions = (
        (
            {
                "network_identity",
                "acl",
                "directory_write",
                "password_policy",
                "rpc",
                "target_enabled",
            },
            "reset_control",
        ),
        (
            {"reset_control", "target_enabled", "activation_network", "activation_accepted"},
            "usable_target",
        ),
        ({"usable_target", "security_group", "membership_usable"}, "entitled_target"),
    )

    def closure(possible):
        known = {k for k, v in facts.items() if v is True or (possible and v is None)}
        while True:
            expanded = known | {effect for needs, effect in actions if needs <= known}
            if expanded == known:
                return "entitled_target" in known
            known = expanded

    reached, possible = closure(False), closure(True)
    return "success" if reached else "indeterminate" if possible else "blocked"


def scenario(case):
    extra = copy.deepcopy(next(n for n in TOY["nodes"] if n["id"] == ACTOR))
    extra.update(id=OTHER_USER, label="Synthetic independently usable identity", enabled=True)
    host = copy.deepcopy(next(n for n in TOY["nodes"] if n["id"] == HOST))
    host.update(id=OTHER_HOST, label="Synthetic foreign context", enabled=True)
    edges = [_edge(HOST, ACTOR, "GenericAll"), _edge(ACTOR, GROUP, "MemberOf")]
    if case.identity == "other_user":
        edges.append(_edge(OTHER_USER, ACTOR, "GenericAll"))
    graph = _graph(edges, extra_nodes=[extra, host])
    if not case.target_enabled:
        canonical = graph.to_canonical()
        next(n for n in canonical["nodes"] if n["id"] == ACTOR)["enabled"] = False
        graph = type(graph).from_canonical(canonical)
    profile = create_foothold_profile(node_id=HOST, node_kind="Computer", profile_type=case.profile)
    initial = wire(profile.initial_attack_state)
    if case.identity in {"same_context", "foreign_context", "other_user"}:
        initial["usable_identity"] = [
            [
                OTHER_USER if case.identity == "other_user" else HOST,
                OTHER_HOST if case.identity == "foreign_context" else HOST,
            ]
        ]
    if case.identity in {"unknown", "foreign_unknown"}:
        initial["authentication_unknown"] = [
            [HOST, OTHER_HOST if case.identity == "foreign_unknown" else HOST]
        ]
    controller = OTHER_USER if case.identity == "other_user" else HOST
    gates = {
        ("password_policy_accepts", controller, ACTOR): True,
        ("directory_write_allowed", controller, ACTOR): True,
        ("network_rpc_reachable", controller, ACTOR): case.rpc,
        ("network_kdc_reachable", ACTOR, HOST): True,
        ("authentication_accepted", ACTOR, HOST): True,
        ("security_group", ACTOR, GROUP): True,
        ("membership_usable", ACTOR, GROUP): True,
        # An optimistic external fact cannot overwrite the disabled snapshot.
        ("target_enabled", controller, ACTOR): True,
    }
    if case.fake_runtime_identity:
        gates["computer_actor_authenticated", HOST, ACTOR] = True
    assumptions = [
        {
            "predicate": p,
            "subject": s,
            "target": t,
            "value": value,
            "scope": "computer-boundary-oracle",
            "rationale": "Independent finite scenario",
            "provenance_reference": "synthetic://computer-boundary/" + case.name,
        }
        for (p, s, t), value in gates.items()
        if value is not None
    ]
    return graph, {
        "source_foothold": HOST,
        "initial_actor": HOST,
        "initial_state": initial,
        "authentication_context": None if case.identity == "missing_context" else HOST,
        "target": GROUP,
        "target_goal": {"kind": "usable_identity_entitlement", "target": GROUP},
        "assumptions": assumptions,
        "allowed_techniques": TECHNIQUES,
        "budget": {"max_paths": 20, "max_steps": 4, "max_expansions": 100},
        "scenario_reference": "computer-boundary-oracle",
    }


@pytest.mark.parametrize("case", CASES, ids=lambda c: c.name)
def test_computer_to_group_matches_independent_oracle(case):
    graph, query = scenario(case)
    if case.identity == "missing_context":
        # The identity-entitlement goal itself needs a context. Use the same
        # explicit state goal to exercise unknown runtime authentication scope.
        query["target_goal"] = {
            "target": GROUP,
            "required_state": {"effective_member": [[ACTOR, GROUP]]},
        }
    result = run_attack_query(query, graph)
    assert result.status == oracle(case)
    assert result.final_goal_reached == (oracle(case) == "success")
    assert result.complete and not result.truncated
    if oracle(case) == "indeterminate":
        assert not result.is_no_path_proven_over_scope
    for path in result.paths:
        requests = [s.result.request for s in path.transition_history]
        assert [r.technique_id for r in requests] == TECHNIQUES
        assert [r.actor for r in requests] == [
            OTHER_USER if case.identity == "other_user" else HOST,
            ACTOR,
            ACTOR,
        ]
        replay_path(path, graph)
    # Neither the query declaration nor the graph is mutated to make a witness.
    assert query["initial_state"]["recovered_secret"] == []
    assert len(graph.edges()) == (3 if case.identity == "other_user" else 2)


@pytest.mark.parametrize("case", [CASES[0], CASES[2], CASES[-1]], ids=lambda c: c.name)
def test_public_serialization_and_cli_keep_boundary(case):
    graph, query = scenario(case)
    result = execute(wire(query), graph)
    assert result["status"] == oracle(case)
    assert result["final_goal_reached"] == (oracle(case) == "success")


@pytest.mark.parametrize(
    "admin,known,expected",
    [(True, True, "success"), (False, True, "no_path"), (True, False, "indeterminate")],
)
def test_local_session_material_keeps_its_independent_host_admin_gates(admin, known, expected):
    graph = _graph([_edge(HOST, ACTOR, "HasSession"), _edge(ACTOR, GROUP, "MemberOf")])
    query = {
        "source_foothold": HOST,
        "initial_actor": HOST,
        "initial_state": {"control": [HOST], "admin_control": [HOST] if admin else []},
        "authentication_context": HOST,
        "target": ACTOR,
        "target_goal": {"target": ACTOR, "required_state": {"credential_material": [ACTOR]}},
        "allowed_techniques": [
            "recover_session_credential_material",
            "activate_recovered_identity",
            "propagate_group_entitlement",
        ],
        "assumptions": [
            {
                "predicate": p,
                "subject": HOST,
                "target": ACTOR,
                "value": True,
                "scope": "computer-session-oracle",
                "rationale": "Synthetic session gates",
                "provenance_reference": "synthetic://computer-session",
            }
            for p in ("session_fresh", "session_present", "credential_accessible")
        ]
        if known
        else [],
        "budget": {"max_paths": 10, "max_steps": 4, "max_expansions": 100},
    }
    result = run_attack_query(query, graph)
    assert result.status == expected
    for path in result.paths:
        replay_path(path, graph)
        after = path.transition_history[-1].result.additions
        assert after.credential_material == {ACTOR}
        assert not after.usable_identity and not after.recovered_secret
    # The legacy untyped material is not a declared password or an identity.
    query["target"] = GROUP
    query["target_goal"] = {"target": GROUP, "kind": "usable_identity_entitlement"}
    group = run_attack_query(query, graph)
    assert not group.paths and not group.final_goal_reached
