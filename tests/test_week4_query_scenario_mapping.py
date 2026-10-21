"""Verification tests connecting #206 scenarios to the received Query API.

Covers all required areas of Issue #206 mapped to the public query interface:
1. Separation of source machine (Computer), usable identity, and authentication context.
2. Separation of DA checkpoint from final asset target (checkpoint reached != asset target).
3. Missing facts (indeterminate), valid assumptions (scenario mode), and known-false veto
   with explanatory audit trace in rejected_assumptions.
4. Dynamic path generation when user changes source, target, or initial capabilities.
5. Query validator fail-closed rejection on unsupported / pending extension techniques.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.research.attack_scenarios import state_from
from src.engine import (
    AttackQuery,
    materialize_query,
    run_attack_query,
)
from src.engine.semantics import (
    apply_transition,
    load_catalog,
)
from src.engine.semantics.transitions import Status

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests/fixtures/attack_scenarios"
TWO_ROUTES_GRAPH_PATH = FIXTURES / "graphs/two-routes.json"
TWO_ROUTES_RAW = json.loads(TWO_ROUTES_GRAPH_PATH.read_text(encoding="utf-8"))

PSREMOTE_GRAPH_PATH = FIXTURES / "graphs/psremote-command.json"
PSREMOTE_RAW = json.loads(PSREMOTE_GRAPH_PATH.read_text(encoding="utf-8"))

ALIASES = {
    "Alice": "S-1-5-21-1000-2000-3000-1101",
    "Bob": "S-1-5-21-1000-2000-3000-1102",
    "Helpdesk": "S-1-5-21-1000-2000-3000-2101",
    "Operators": "S-1-5-21-1000-2000-3000-2102",
    "Admins": "S-1-5-21-1000-2000-3000-2103",
    "Host": "10000000-0000-4000-8000-000000000002",
    "OtherHost": "10000000-0000-4000-8000-000000000003",
}

PSREMOTE_ALIASES = {
    "Alice": "S-1-5-21-1000-2000-3000-1101",
    "Host": "10000000-0000-4000-8000-000000000002",
}

DEFAULT_RUNTIME_FACTS = [
    {
        "predicate": "admin_channel",
        "subject": "Alice",
        "target": "Host",
        "value": True,
        "origin": "observed_evidence",
        "scope": "two-routes:snapshot",
        "rationale": "observed admin channel",
        "provenance_reference": "evidence:admin-channel",
    },
    {
        "predicate": "authentication_accepted",
        "subject": "Alice",
        "target": "Host",
        "value": True,
        "origin": "observed_evidence",
        "scope": "two-routes:snapshot",
        "rationale": "observed auth accepted",
        "provenance_reference": "evidence:auth-accepted",
    },
    {
        "predicate": "security_group",
        "subject": "Alice",
        "target": "Admins",
        "value": True,
        "origin": "observed_evidence",
        "scope": "two-routes:snapshot",
        "rationale": "observed security group",
        "provenance_reference": "evidence:security-group",
    },
    {
        "predicate": "membership_usable",
        "subject": "Alice",
        "target": "Admins",
        "value": True,
        "origin": "observed_evidence",
        "scope": "two-routes:snapshot",
        "rationale": "observed usable membership",
        "provenance_reference": "evidence:usable-membership",
    },
]


def test_source_computer_usable_identity_and_auth_context_separation():
    """Separation of source foothold, usable identity, and authentication scope.

    1. Foothold Computer with domain user actor without declared identity raises ValueError.
    2. Foothold Computer with usable identity scoped to Host, but authentication context OtherHost,
       blocks domain actions and yields 0 paths.
    3. Foothold Computer with usable identity scoped to Host, matching Host authentication context,
       successfully finds all 3 attack paths.
    4. Foothold Computer alone (initial_actor=Computer) finds 0 paths to Host.
    """
    # Case 1: Foothold Computer + domain user actor without identity capability fail-fast
    with pytest.raises(ValueError, match="without declared usable_identity or control"):
        materialize_query(
            {
                "source_foothold": "OtherHost",
                "initial_actor": "Alice",
                "initial_state": {"control": ["OtherHost"]},
                "target": "Host",
                "target_goal": {
                    "target": "Host",
                    "required_state": {"admin_control": ["Host"]},
                },
                "aliases": ALIASES,
            },
            graph=TWO_ROUTES_RAW,
        )

    # Case 2: Usable identity scoped to Host, but query runs in OtherHost authentication context
    query_wrong_context = AttackQuery(
        target="Host",
        source_foothold="OtherHost",
        initial_actor="Alice",
        initial_state={
            "control": ["OtherHost"],
            "usable_identity": [["Alice", "Host"]],
        },
        authentication_context="OtherHost",
        target_goal={
            "target": "Host",
            "required_state": {"admin_control": ["Host"]},
        },
        runtime_facts=DEFAULT_RUNTIME_FACTS,
        allowed_techniques=["obtain_admin_execution_on_host", "propagate_group_entitlement"],
        aliases=ALIASES,
    )
    result_wrong_context = run_attack_query(query_wrong_context, graph=TWO_ROUTES_RAW)
    assert result_wrong_context.status == "blocked"
    assert len(result_wrong_context.paths) == 0

    # Case 3: Usable identity scoped to Host with matching Host authentication context
    query_valid_context = AttackQuery(
        target="Host",
        source_foothold="OtherHost",
        initial_actor="Alice",
        initial_state={
            "control": ["OtherHost"],
            "usable_identity": [["Alice", "Host"]],
        },
        authentication_context="Host",
        target_goal={
            "target": "Host",
            "required_state": {"admin_control": ["Host"]},
        },
        runtime_facts=DEFAULT_RUNTIME_FACTS,
        allowed_techniques=["obtain_admin_execution_on_host", "propagate_group_entitlement"],
        aliases=ALIASES,
    )
    result_valid_context = run_attack_query(query_valid_context, graph=TWO_ROUTES_RAW)
    assert result_valid_context.status == "success"
    assert len(result_valid_context.paths) == 3
    assert result_valid_context.final_goal_reached is True

    # Case 4: Foothold Computer alone (initial_actor=OtherHost)
    query_host_only = AttackQuery(
        target="Host",
        source_foothold="OtherHost",
        initial_state={"control": ["OtherHost"]},
        target_goal={
            "target": "Host",
            "required_state": {"admin_control": ["Host"]},
        },
        runtime_facts=DEFAULT_RUNTIME_FACTS,
        allowed_techniques=["obtain_admin_execution_on_host", "propagate_group_entitlement"],
        aliases=ALIASES,
    )
    result_host_only = run_attack_query(query_host_only, graph=TWO_ROUTES_RAW)
    assert result_host_only.status == "no_path"
    assert len(result_host_only.paths) == 0


def test_da_checkpoint_reached_separated_from_asset_target():
    """DA checkpoint reached does not equal asset target compromise.

    1. DA checkpoint reached, but final asset gate is known-false:
       checkpoint_reached=True, final_goal_reached=False,
       status='checkpoint_reached_final_goal_blocked'.
    2. DA checkpoint reached, but final asset gate is missing (unknown):
       checkpoint_reached=True, final_goal_reached=False,
       status='checkpoint_reached_final_goal_indeterminate'.
    3. Both DA checkpoint and final asset gate reached:
       checkpoint_reached=True, final_goal_reached=True, status='success'.
    4. Asset goal reached directly, but DA checkpoint unreached/blocked:
       checkpoint_reached=False, final_goal_reached=True, status='success',
       1 path (Direct AdminTo route), complete=True.
    """
    # Case 1: Final asset gate admin_channel is authoritative False
    facts_blocked_asset = [
        f for f in DEFAULT_RUNTIME_FACTS if f["predicate"] != "admin_channel"
    ] + [
        {
            "predicate": "admin_channel",
            "subject": "Alice",
            "target": "Host",
            "value": False,
            "origin": "blocked_evidence",
            "scope": "two-routes:snapshot",
            "rationale": "admin channel disabled",
            "provenance_reference": "evidence:blocked-channel",
        }
    ]
    query_blocked_asset = AttackQuery(
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
        runtime_facts=facts_blocked_asset,
        allowed_techniques=["obtain_admin_execution_on_host", "propagate_group_entitlement"],
        aliases=ALIASES,
    )
    result_blocked = run_attack_query(query_blocked_asset, graph=TWO_ROUTES_RAW)
    assert result_blocked.checkpoint_reached is True
    assert result_blocked.final_goal_reached is False
    assert len(result_blocked.paths) == 0
    assert result_blocked.status == "checkpoint_reached_final_goal_blocked"

    # Case 2: Final asset gate admin_channel is missing without assumption
    facts_missing_asset = [f for f in DEFAULT_RUNTIME_FACTS if f["predicate"] != "admin_channel"]
    query_missing_asset = AttackQuery(
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
        runtime_facts=facts_missing_asset,
        allowed_techniques=["obtain_admin_execution_on_host", "propagate_group_entitlement"],
        aliases=ALIASES,
    )
    result_missing = run_attack_query(query_missing_asset, graph=TWO_ROUTES_RAW)
    assert result_missing.checkpoint_reached is True
    assert result_missing.final_goal_reached is False
    assert len(result_missing.paths) == 0
    assert result_missing.status == "checkpoint_reached_final_goal_indeterminate"

    # Case 3: Both checkpoint and final asset gate are satisfied
    query_satisfied = AttackQuery(
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
        runtime_facts=DEFAULT_RUNTIME_FACTS,
        allowed_techniques=["obtain_admin_execution_on_host", "propagate_group_entitlement"],
        aliases=ALIASES,
    )
    result_satisfied = run_attack_query(query_satisfied, graph=TWO_ROUTES_RAW)
    assert result_satisfied.checkpoint_reached is True
    assert result_satisfied.final_goal_reached is True
    assert len(result_satisfied.paths) == 3
    assert result_satisfied.status == "success"

    # Case 4: Final asset goal reached directly, but checkpoint is unreached / blocked
    facts_blocked_checkpoint = [
        f for f in DEFAULT_RUNTIME_FACTS if f["predicate"] != "membership_usable"
    ] + [
        {
            "predicate": "membership_usable",
            "subject": "Alice",
            "target": "Admins",
            "value": False,
            "origin": "blocked_evidence",
            "scope": "two-routes:snapshot",
            "rationale": "group membership propagation blocked",
            "provenance_reference": "evidence:blocked-member",
        }
    ]
    query_blocked_checkpoint = AttackQuery(
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
        runtime_facts=facts_blocked_checkpoint,
        allowed_techniques=["obtain_admin_execution_on_host", "propagate_group_entitlement"],
        aliases=ALIASES,
    )
    result_asset_only = run_attack_query(query_blocked_checkpoint, graph=TWO_ROUTES_RAW)
    assert result_asset_only.checkpoint_reached is False
    assert result_asset_only.final_goal_reached is True
    assert len(result_asset_only.paths) == 1
    assert result_asset_only.complete is True
    assert result_asset_only.status == "success"
    direct_step = result_asset_only.paths[0].transition_history[0]
    assert direct_step.result.request.technique_id == "obtain_admin_execution_on_host"
    assert direct_step.result.request.source == ALIASES["Alice"]
    assert direct_step.result.request.target == ALIASES["Host"]


def test_missing_facts_vs_valid_assumptions_vs_known_false_veto():
    """Missing facts -> indeterminate; valid assumption -> scenario; known-false -> veto.

    1. Missing runtime fact without assumption yields status='indeterminate'.
    2. Valid declared assumption with scope and rationale enables scenario mode success.
    3. Authoritative false fact yields status='blocked'.
    4. Authoritative false fact vetoes declared assumption true and records explanatory trace
       in rejected_assumptions with reason='known_false_veto'.
    """
    # Case 1: Missing required fact winrm_available without assumption
    sparse_psremote_facts = [
        {
            "predicate": "authentication_accepted",
            "subject": "Alice",
            "target": "Host",
            "value": True,
            "origin": "observed_evidence",
            "scope": "psremote:test",
            "rationale": "auth observed",
            "provenance_reference": "evidence:ps-auth",
        }
    ]
    query_missing = AttackQuery(
        target="Host",
        initial_actor="Alice",
        initial_state={"control": ["Alice"]},
        target_goal={
            "target": "Host",
            "required_state": {"remote_command_execution": [["Alice", "Host"]]},
        },
        runtime_facts=sparse_psremote_facts,
        allowed_techniques=["open_winrm_remote_session"],
        aliases=PSREMOTE_ALIASES,
    )
    result_missing = run_attack_query(query_missing, graph=PSREMOTE_RAW)
    assert result_missing.status == "indeterminate"
    assert result_missing.final_goal_reached is False
    assert any(attempt.status == Status.INDETERMINATE for attempt in result_missing.attempts)

    # Case 2: Valid declared assumption enables scenario execution
    valid_assumption = [
        {
            "predicate": "winrm_available",
            "subject": "Alice",
            "target": "Host",
            "value": True,
            "origin": "declared_assumption",
            "scope": "psremote:scenario",
            "rationale": "Synthetic assumption of WinRM service availability",
            "provenance_reference": "evidence:winrm-doc",
            "assumption_metadata": {"declared_by": "ttsA-tester"},
        }
    ]
    query_assumed = AttackQuery(
        target="Host",
        initial_actor="Alice",
        initial_state={"control": ["Alice"]},
        target_goal={
            "target": "Host",
            "required_state": {"remote_command_execution": [["Alice", "Host"]]},
        },
        runtime_facts=sparse_psremote_facts,
        assumptions=valid_assumption,
        allowed_techniques=["open_winrm_remote_session"],
        aliases=PSREMOTE_ALIASES,
    )
    result_assumed = run_attack_query(query_assumed, graph=PSREMOTE_RAW)
    assert result_assumed.status == "success"
    assert result_assumed.final_goal_reached is True
    assert len(result_assumed.paths) == 1

    # Case 3: Authoritative false fact blocks transition
    blocked_facts = sparse_psremote_facts + [
        {
            "predicate": "winrm_available",
            "subject": "Alice",
            "target": "Host",
            "value": False,
            "origin": "blocked_evidence",
            "scope": "psremote:test",
            "rationale": "WinRM explicitly disabled",
            "provenance_reference": "evidence:port-scan-closed",
        }
    ]
    query_blocked = AttackQuery(
        target="Host",
        initial_actor="Alice",
        initial_state={"control": ["Alice"]},
        target_goal={
            "target": "Host",
            "required_state": {"remote_command_execution": [["Alice", "Host"]]},
        },
        runtime_facts=blocked_facts,
        allowed_techniques=["open_winrm_remote_session"],
        aliases=PSREMOTE_ALIASES,
    )
    result_blocked = run_attack_query(query_blocked, graph=PSREMOTE_RAW)
    assert result_blocked.status == "blocked"
    assert result_blocked.final_goal_reached is False

    # Case 4: Authoritative false vetoes declared assumption true with explanatory trace
    query_conflict = AttackQuery(
        target="Host",
        initial_actor="Alice",
        initial_state={"control": ["Alice"]},
        target_goal={
            "target": "Host",
            "required_state": {"remote_command_execution": [["Alice", "Host"]]},
        },
        runtime_facts=blocked_facts,
        assumptions=valid_assumption,
        allowed_techniques=["open_winrm_remote_session"],
        aliases=PSREMOTE_ALIASES,
    )
    materialized = materialize_query(query_conflict, graph=PSREMOTE_RAW)
    assert len(materialized.rejected_assumptions) == 1
    rejected = materialized.rejected_assumptions[0]
    assert rejected.predicate == "winrm_available"
    assert rejected.reason == "known_false_veto"
    assert rejected.assumption_value is True
    assert rejected.conflicting_fact is not None
    assert rejected.conflicting_fact.value is False
    assert rejected.rationale == "Synthetic assumption of WinRM service availability"

    result_conflict = run_attack_query(query_conflict, graph=PSREMOTE_RAW)
    assert result_conflict.status == "blocked"
    assert result_conflict.final_goal_reached is False
    assert len(result_conflict.paths) == 0


def test_dynamic_search_driven_by_user_input_changes():
    """Altering source, target, or initial state dynamically drives search without ordered paths.

    1. W4-M baseline (S0): exact acceptable_paths and reachable states {S0, S1, S2, S3}.
    2. W4-I/E initial entitlement (S1): exact acceptable_paths and states {S1, S3}.
    3. W4-I/H host control only: 0 paths, status='blocked', states {OtherHost admin_control}.
    4. W4-TARGET target changed: 0 paths, status='no_path', reachable states {S0..S3}.
    5. Search budget truncation caps (max_paths, max_expansions, max_steps): status='truncated'.
    """
    pkg = json.loads((FIXTURES / "week4-v1.json").read_text(encoding="utf-8"))
    sc0 = pkg["scenarios"][0]
    sc0_binding = pkg["graphs"][sc0["graph"]]
    sc0_aliases = sc0_binding["aliases"]
    sc0_graph = json.loads((FIXTURES / sc0_binding["path"]).read_text(encoding="utf-8"))

    step_signatures = {
        s["step_id"]: (
            s["request"]["technique_id"],
            sc0_aliases[s["request"]["actor"]],
            sc0_aliases[s["request"]["source"]],
            sc0_aliases[s["request"]["target"]],
        )
        for s in sc0["steps"]
    }

    S0 = state_from({"control": ["Alice"]}, sc0_aliases)
    S1 = state_from(
        {"control": ["Alice"], "effective_member": [["Alice", "Admins"]]},
        sc0_aliases,
    )
    S2 = state_from({"control": ["Alice"], "admin_control": ["Host"]}, sc0_aliases)
    S3 = state_from(
        {
            "control": ["Alice"],
            "effective_member": [["Alice", "Admins"]],
            "admin_control": ["Host"],
        },
        sc0_aliases,
    )

    base_query_params = {
        "runtime_facts": sc0["runtime_facts"],
        "allowed_techniques": sc0["oracle_scope"]["techniques"],
        "aliases": sc0_aliases,
        "budget": sc0["oracle_scope"]["budget"],
    }

    # 1. W4-M baseline (S0 -> Host)
    v0 = sc0["variants"][0]
    q_w4_m = {
        **base_query_params,
        "initial_actor": sc0["initial_actor"],
        "initial_state": sc0["initial_state"],
        "target": sc0["target_goal"]["target"],
        "target_goal": sc0["target_goal"],
    }
    res_w4_m = run_attack_query(q_w4_m, graph=sc0_graph)
    assert res_w4_m.status == "success"
    assert res_w4_m.complete is True
    actual_paths_m = {
        tuple(
            (
                step.result.request.technique_id,
                step.result.request.actor,
                step.result.request.source,
                step.result.request.target,
            )
            for step in path.transition_history
        )
        for path in res_w4_m.paths
    }
    expected_paths_m = {
        tuple(step_signatures[step_id] for step_id in path)
        for path in v0["expected_search"]["acceptable_paths"]
    }
    assert actual_paths_m == expected_paths_m
    states_m = {state_from(sc0["initial_state"], sc0_aliases)} | {
        apply_transition(a.before, a) for a in res_w4_m.attempts if a.status == Status.APPLICABLE
    }
    assert states_m == {S0, S1, S2, S3}

    # 2. W4-I/E initial entitlement (S1 with effective membership -> Host)
    v1 = sc0["variants"][1]
    q_w4_ie = {
        **base_query_params,
        "initial_actor": sc0["initial_actor"],
        "initial_state": v1["initial_state"],
        "target": sc0["target_goal"]["target"],
        "target_goal": sc0["target_goal"],
    }
    res_w4_ie = run_attack_query(q_w4_ie, graph=sc0_graph)
    assert res_w4_ie.status == "success"
    assert res_w4_ie.complete is True
    actual_paths_ie = {
        tuple(
            (
                step.result.request.technique_id,
                step.result.request.actor,
                step.result.request.source,
                step.result.request.target,
            )
            for step in path.transition_history
        )
        for path in res_w4_ie.paths
    }
    expected_paths_ie = {
        tuple(step_signatures[step_id] for step_id in path)
        for path in v1["expected_search"]["acceptable_paths"]
    }
    assert actual_paths_ie == expected_paths_ie
    states_ie = {state_from(v1["initial_state"], sc0_aliases)} | {
        apply_transition(a.before, a) for a in res_w4_ie.attempts if a.status == Status.APPLICABLE
    }
    assert states_ie == {S1, S3}

    # 3. W4-I/H host control only (OtherHost controlled, Alice not controlled)
    v2 = sc0["variants"][2]
    q_w4_ih = {
        **base_query_params,
        "initial_actor": sc0["initial_actor"],
        "initial_state": v2["initial_state"],
        "target": sc0["target_goal"]["target"],
        "target_goal": sc0["target_goal"],
    }
    res_w4_ih = run_attack_query(q_w4_ih, graph=sc0_graph)
    assert res_w4_ih.status == "blocked"
    assert res_w4_ih.complete is True
    assert len(res_w4_ih.paths) == 0
    states_ih = {state_from(v2["initial_state"], sc0_aliases)} | {
        apply_transition(a.before, a) for a in res_w4_ih.attempts if a.status == Status.APPLICABLE
    }
    assert states_ih == {state_from(v2["initial_state"], sc0_aliases)}

    # 4. W4-TARGET target changed to OtherHost
    sc1 = pkg["scenarios"][1]
    sc1_binding = pkg["graphs"][sc1["graph"]]
    sc1_aliases = sc1_binding["aliases"]
    sc1_graph = json.loads((FIXTURES / sc1_binding["path"]).read_text(encoding="utf-8"))
    q_w4_target = {
        "runtime_facts": sc1["runtime_facts"],
        "allowed_techniques": sc1["oracle_scope"]["techniques"],
        "aliases": sc1_aliases,
        "budget": sc1["oracle_scope"]["budget"],
        "initial_actor": sc1["initial_actor"],
        "initial_state": sc1["initial_state"],
        "target": sc1["target_goal"]["target"],
        "target_goal": sc1["target_goal"],
    }
    res_w4_target = run_attack_query(q_w4_target, graph=sc1_graph)
    assert res_w4_target.status == "no_path"
    assert res_w4_target.complete is True
    assert len(res_w4_target.paths) == 0
    states_target = {state_from(sc1["initial_state"], sc1_aliases)} | {
        apply_transition(a.before, a)
        for a in res_w4_target.attempts
        if a.status == Status.APPLICABLE
    }
    S0_target = state_from({"control": ["Alice"]}, sc1_aliases)
    S1_target = state_from(
        {"control": ["Alice"], "effective_member": [["Alice", "Admins"]]},
        sc1_aliases,
    )
    S2_target = state_from({"control": ["Alice"], "admin_control": ["Host"]}, sc1_aliases)
    S3_target = state_from(
        {
            "control": ["Alice"],
            "effective_member": [["Alice", "Admins"]],
            "admin_control": ["Host"],
        },
        sc1_aliases,
    )
    assert states_target == {S0_target, S1_target, S2_target, S3_target}

    # 5. Search budget truncation caps: partial search cannot prove complete minimum
    for cap, expected_reason in [
        ("max_paths", "path_limit_reached"),
        ("max_expansions", "expansion_limit_reached"),
        ("max_steps", "step_limit_reached"),
    ]:
        q_capped = {
            **base_query_params,
            "initial_actor": "Alice",
            "initial_state": {"control": ["Alice"]},
            "target": "Host",
            "target_goal": {"target": "Host", "required_state": {"admin_control": ["Host"]}},
            "budget": {
                "max_paths": 1 if cap == "max_paths" else 1000,
                "max_expansions": 1 if cap == "max_expansions" else 100000,
                "max_steps": 1 if cap == "max_steps" else 12,
            },
        }
        res_capped = run_attack_query(q_capped, graph=TWO_ROUTES_RAW)
        assert res_capped.truncated is True
        assert res_capped.complete is False
        assert res_capped.truncation_reason == expected_reason

    # With max_paths=1, only 1 path is found out of 3, missing the lower-effort M/I program
    q_max_paths_1 = {
        **base_query_params,
        "initial_actor": "Alice",
        "initial_state": {"control": ["Alice"]},
        "target": "Host",
        "target_goal": {"target": "Host", "required_state": {"admin_control": ["Host"]}},
        "budget": {"max_paths": 1, "max_steps": 12, "max_expansions": 100000},
    }
    res_p1 = run_attack_query(q_max_paths_1, graph=TWO_ROUTES_RAW)
    assert len(res_p1.paths) == 1
    assert res_p1.truncated is True
    assert res_p1.complete is False

    # When goal cannot be reached within cap, search yields truncated, never no_path/blocked
    facts_indirect_only = [
        f for f in DEFAULT_RUNTIME_FACTS if f["predicate"] != "admin_channel"
    ] + [
        {
            "predicate": "admin_channel",
            "subject": "Alice",
            "target": "Host",
            "value": False,
            "origin": "blocked_evidence",
            "scope": "two-routes:snapshot",
            "rationale": "direct admin channel blocked",
            "provenance_reference": "evidence:blocked-direct",
        }
    ]
    q_truncated_no_hit = {
        **base_query_params,
        "initial_actor": "Alice",
        "initial_state": {"control": ["Alice"]},
        "target": "Host",
        "target_goal": {"target": "Host", "required_state": {"admin_control": ["Host"]}},
        "runtime_facts": facts_indirect_only,
        "budget": {"max_steps": 1},
    }
    res_trunc_no_hit = run_attack_query(q_truncated_no_hit, graph=TWO_ROUTES_RAW)
    assert res_trunc_no_hit.truncated is True
    assert not res_trunc_no_hit.complete
    assert len(res_trunc_no_hit.paths) == 0
    assert res_trunc_no_hit.status == "truncated"
    assert res_trunc_no_hit.status not in ("no_path", "blocked")


def test_query_validator_fails_closed_on_unsupported_techniques():
    """Query API rejects unknown technique IDs fail-closed with ValueError.

    Extension techniques (AS-REP roasting, Kerberoasting, and RBCD) remain in
    pending disposition per handoff #218 until implemented by TTS B (e.g., #216).
    The query validator enforces fail-closed validation by raising ValueError whenever
    any requested technique ID is absent from the active catalog, without locking
    load_catalog() into an invariant of lacking upcoming techniques.
    """
    unsupported_technique = "unsupported_extension_technique_pending_b"
    catalog = load_catalog()
    assert unsupported_technique not in {t.id for t in catalog}

    # Query API rejects unknown technique IDs fail-closed
    with pytest.raises(ValueError, match="unknown technique IDs in allowed_techniques"):
        materialize_query(
            {
                "initial_actor": "Alice",
                "initial_state": {"control": ["Alice"]},
                "target": "Host",
                "target_goal": {"target": "Host", "required_state": {"admin_control": ["Host"]}},
                "allowed_techniques": [unsupported_technique],
                "aliases": ALIASES,
            },
            graph=TWO_ROUTES_RAW,
        )
