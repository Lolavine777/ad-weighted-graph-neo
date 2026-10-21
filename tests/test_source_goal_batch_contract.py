"""Comprehensive verification suite for Week 5 Source/Goal/Batch contracts (#268).

Tests:
1. JSON Schema validation (Draft 2020-12) for manifests, profiles, requests, results.
2. Case A: Leaked password vs usable identity (activation requirement, gate failures).
3. Case B: Destination discovery mode vs single-target drilldown.
4. Case C: DA checkpoint reached vs final host admin blocked.
5. Case D: Source node eligibility enforcement (User/Computer vs Group/OU/Domain).
6. Case E: Multi-source independent execution and graph immutability.
7. Case F: Missing likelihood handling (unrated != zero / safe).
8. Case G: Known-false veto over declared assumptions.
9. Case H: Truncated search bounds cannot prove global minimum.
10. Case I: Multi-criteria source prioritization and deterministic tie-breaking.
11. Formal validation of policy counterexamples (anti-probability summation).
12. SEAMLESS snapshot-pinned target manifest validation.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator

from scripts.research.source_goal_batch import (
    BatchCellStatus,
    BatchQueryRequest,
    BatchQueryResult,
    BatchSourceItem,
    FootholdProfileKind,
    SourceGoalCell,
    SourcePrioritizationEntry,
    TargetControlLevel,
    TargetGoal,
    TargetGoalCategory,
    TargetManifest,
    create_foothold_profile,
    map_query_result_to_cell,
    prioritize_sources,
)
from src.engine import AttackQuery, EngineGraph, run_attack_query
from src.engine.semantics import (
    AttackState,
    FactOrigin,
    RuntimeFact,
    StructuralRelationship,
)
from src.engine.semantics.state import CredentialArtifact

ROOT = Path(__file__).resolve().parents[1]
FIXTURES_DIR = ROOT / "tests" / "fixtures" / "batch_contracts"
SCHEMAS_DIR = ROOT / "docs" / "research"
GRAPH_TWO_ROUTES_PATH = (
    ROOT / "tests" / "fixtures" / "attack_scenarios" / "graphs" / "two-routes.json"
)

ALICE_ID = "S-1-5-21-1000-2000-3000-1101"
BOB_ID = "S-1-5-21-1000-2000-3000-1102"
ADMINS_ID = "S-1-5-21-1000-2000-3000-2103"
HELPDESK_ID = "S-1-5-21-1000-2000-3000-2101"
HOST_C0_ID = "10000000-0000-4000-8000-000000000002"
OTHERHOST_X_ID = "10000000-0000-4000-8000-000000000003"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def make_assumption(
    predicate: str,
    subject: str,
    target: str,
    value: bool = True,
    origin: FactOrigin = FactOrigin.DECLARED_ASSUMPTION,
    scope: str = "test_scope",
) -> RuntimeFact:
    return RuntimeFact(
        predicate=predicate,
        subject=subject,
        target=target,
        value=value,
        origin=origin,
        scope=scope,
        rationale="Declared test precondition",
        provenance_reference="test:provenance_reference",
    )


# ---------------------------------------------------------------------------
# 1. JSON Schema Validations
# ---------------------------------------------------------------------------


def test_target_manifest_schema_validation():
    """Verify target manifest schema validates synthetic and SEAMLESS fixtures."""
    schema = load_json(SCHEMAS_DIR / "target-manifest.schema.json")
    validator = Draft202012Validator(schema)

    seamless_manifest = load_json(FIXTURES_DIR / "target_manifest_seamless.json")
    synthetic_manifest = load_json(FIXTURES_DIR / "target_manifest_synthetic.json")

    assert not list(validator.iter_errors(seamless_manifest))
    assert not list(validator.iter_errors(synthetic_manifest))


def test_foothold_profiles_schema_validation():
    """Verify foothold profiles schema validates standard test suite."""
    schema = load_json(SCHEMAS_DIR / "foothold-profiles.schema.json")
    validator = Draft202012Validator(schema)

    profiles_fixture = load_json(FIXTURES_DIR / "foothold_profiles.json")
    assert not list(validator.iter_errors(profiles_fixture))


def test_batch_query_request_schema_validation():
    """Verify batch query request schema validates example batch payload."""
    schema = load_json(SCHEMAS_DIR / "batch-query-request.schema.json")
    validator = Draft202012Validator(schema)

    request_fixture = load_json(FIXTURES_DIR / "batch_request_example.json")
    assert not list(validator.iter_errors(request_fixture))


def test_batch_query_result_schema_validation():
    """Verify batch query result schema validates example batch result."""
    schema = load_json(SCHEMAS_DIR / "batch-query-result.schema.json")
    validator = Draft202012Validator(schema)

    result_fixture = load_json(FIXTURES_DIR / "batch_result_example.json")
    assert not list(validator.iter_errors(result_fixture))


# ---------------------------------------------------------------------------
# 2. Case A: Leaked Password vs Usable Identity
# ---------------------------------------------------------------------------


def test_case_a_leaked_password_requires_activation():
    """A leaked password starts as an unverified credential artifact, NOT a usable identity.

    Attacker must perform activate_recovered_identity to attain usable identity.
    If KDC is unreachable, status is indeterminate.
    If account is disabled, status is blocked.
    """
    graph = EngineGraph.from_canonical(load_json(GRAPH_TWO_ROUTES_PATH))

    # Leaked password profile for Alice
    alice_profile = create_foothold_profile(
        node_id=ALICE_ID,
        node_kind="User",
        profile_type=FootholdProfileKind.USER_LEAKED_PASSWORD,
        authentication_context=HOST_C0_ID,
        provenance_reference="test:alice_password_leak",
    )
    assert alice_profile.is_supported
    assert alice_profile.required_activation_technique == "activate_recovered_identity"
    assert len(alice_profile.initial_attack_state.control) == 0
    assert len(alice_profile.initial_attack_state.usable_identity) == 0
    assert len(alice_profile.initial_attack_state.recovered_secret) == 1

    # Attempt query without activation assumptions -> indeterminate due to unknown KDC/auth
    q_indeterminate = AttackQuery(
        initial_actor=ALICE_ID,
        initial_state=alice_profile.initial_attack_state,
        authentication_context=HOST_C0_ID,
        target=ADMINS_ID,
        target_goal={
            "target": ADMINS_ID,
            "required_state": {"effective_member": [[ALICE_ID, ADMINS_ID]]},
        },
        budget={"max_paths": 100, "max_steps": 10, "max_expansions": 1000},
    )
    res_indet = run_attack_query(q_indeterminate, graph)
    assert not res_indet.final_goal_reached
    assert any(a.status.name == "INDETERMINATE" for a in res_indet.attempts)

    # Disabled account -> blocked
    raw_graph = load_json(GRAPH_TWO_ROUTES_PATH)
    for n in raw_graph["nodes"]:
        if n["id"] == ALICE_ID:
            n["enabled"] = False
    disabled_graph = EngineGraph.from_canonical(raw_graph)
    res_disabled = run_attack_query(q_indeterminate, disabled_graph)
    assert not res_disabled.final_goal_reached
    assert any(
        a.status.name == "BLOCKED" and "actor_enabled" in a.failed
        for a in res_disabled.attempts
        if a.request.technique_id == "activate_recovered_identity"
    )

    # Supply valid activation assumptions -> succeeds in 2 steps (activation + group propagation)
    assumptions = [
        make_assumption("secret_valid", ALICE_ID, HOST_C0_ID, True, scope=HOST_C0_ID),
        make_assumption("network_kdc_reachable", ALICE_ID, HOST_C0_ID, True, scope=HOST_C0_ID),
        make_assumption("authentication_accepted", ALICE_ID, HOST_C0_ID, True, scope=HOST_C0_ID),
        make_assumption("security_group", ALICE_ID, ADMINS_ID, True, scope=HOST_C0_ID),
        make_assumption("membership_usable", ALICE_ID, ADMINS_ID, True, scope=HOST_C0_ID),
    ]

    q_success = AttackQuery(
        initial_actor=ALICE_ID,
        initial_state=alice_profile.initial_attack_state,
        authentication_context=HOST_C0_ID,
        target=ADMINS_ID,
        target_goal={
            "target": ADMINS_ID,
            "required_state": {"effective_member": [[ALICE_ID, ADMINS_ID]]},
        },
        assumptions=assumptions,
        budget={"max_paths": 100, "max_steps": 10, "max_expansions": 1000},
    )
    res_success = run_attack_query(q_success, graph)
    assert res_success.final_goal_reached
    assert len(res_success.paths) == 1
    techs = [s.result.request.technique_id for s in res_success.paths[0].transition_history]
    assert techs == ["activate_recovered_identity", "propagate_group_entitlement"]


def test_case_a_usable_identity_skips_activation():
    """A usable identity already has control over the principal and active usable_identity.

    Can immediately propagate group entitlement in 1 step without activate_recovered_identity.
    """
    graph = EngineGraph.from_canonical(load_json(GRAPH_TWO_ROUTES_PATH))

    alice_profile = create_foothold_profile(
        node_id=ALICE_ID,
        node_kind="User",
        profile_type=FootholdProfileKind.USER_USABLE_IDENTITY,
        authentication_context=ALICE_ID,
    )
    assert alice_profile.is_supported
    assert alice_profile.required_activation_technique is None
    assert (ALICE_ID, ALICE_ID) in alice_profile.initial_attack_state.usable_identity

    assumptions = [
        make_assumption("security_group", ALICE_ID, ADMINS_ID, True),
        make_assumption("membership_usable", ALICE_ID, ADMINS_ID, True),
    ]

    q = AttackQuery(
        initial_actor=ALICE_ID,
        initial_state=alice_profile.initial_attack_state,
        authentication_context=ALICE_ID,
        target=ADMINS_ID,
        target_goal={
            "target": ADMINS_ID,
            "required_state": {"effective_member": [[ALICE_ID, ADMINS_ID]]},
        },
        assumptions=assumptions,
        budget={"max_paths": 100, "max_steps": 10, "max_expansions": 1000},
    )
    res = run_attack_query(q, graph)
    assert res.final_goal_reached
    assert len(res.paths) == 1
    techs = [s.result.request.technique_id for s in res.paths[0].transition_history]
    assert techs == ["propagate_group_entitlement"]


# ---------------------------------------------------------------------------
# 3. Case B: Destination Discovery Mode vs Single Target Drilldown
# ---------------------------------------------------------------------------


def test_case_b_destination_discovery_manifest_resolution():
    """Verify that TargetManifest resolves default goals when no single target is chosen."""
    manifest_data = load_json(FIXTURES_DIR / "target_manifest_synthetic.json")
    manifest = TargetManifest(
        manifest_id=manifest_data["manifest_id"],
        version=manifest_data["version"],
        snapshot_id=manifest_data["snapshot_id"],
        domain_sid=manifest_data["domain_sid"],
        default_discovery_goals=tuple(manifest_data["default_discovery_goals"]),
        targets=tuple(
            TargetGoal(
                goal_id=t["goal_id"],
                category=TargetGoalCategory(t["category"]),
                target_node_id=t["target_node_id"],
                target_node_kind=t["target_node_kind"],
                display_name=t["display_name"],
                technical_consequence=t["technical_consequence"],
                impact_rating=t["impact_rating"],
                required_control_level=TargetControlLevel(t["required_control_level"]),
                required_state=t["required_state"],
                checkpoint_goal=t.get("checkpoint_goal"),
            )
            for t in manifest_data["targets"]
        ),
    )

    # In discovery mode (target_goal_ids is None), discovery targets are resolved
    assert len(manifest.default_discovery_goals) == 2
    resolved_default = manifest.resolve_goals(None)
    assert len(resolved_default) == 2
    assert [g.goal_id for g in resolved_default] == [
        "goal-synthetic-da",
        "goal-synthetic-c0-host",
    ]

    # In drilldown mode, specific target is resolved
    drilldown = manifest.resolve_goals(["goal-synthetic-da"])
    assert len(drilldown) == 1
    assert drilldown[0].goal_id == "goal-synthetic-da"
    assert drilldown[0].impact_rating == "Catastrophic"


def test_case_b_target_manifest_resolve_goals_edge_cases():
    """Verify edge cases for resolve_goals on TargetManifest and BatchQueryRequest."""
    manifest_data = load_json(FIXTURES_DIR / "target_manifest_synthetic.json")
    manifest = TargetManifest(
        manifest_id=manifest_data["manifest_id"],
        version=manifest_data["version"],
        snapshot_id=manifest_data["snapshot_id"],
        domain_sid=manifest_data["domain_sid"],
        default_discovery_goals=tuple(manifest_data["default_discovery_goals"]),
        targets=tuple(
            TargetGoal(
                goal_id=t["goal_id"],
                category=TargetGoalCategory(t["category"]),
                target_node_id=t["target_node_id"],
                target_node_kind=t["target_node_kind"],
                display_name=t["display_name"],
                technical_consequence=t["technical_consequence"],
                impact_rating=t["impact_rating"],
                required_control_level=TargetControlLevel(t["required_control_level"]),
                required_state=t["required_state"],
            )
            for t in manifest_data["targets"]
        ),
    )

    # Empty list/tuple normalizes to default discovery goals
    assert manifest.resolve_goals([]) == manifest.resolve_goals(None)
    assert len(manifest.resolve_goals([])) == 2

    # Non-existent target goal ID raises KeyError with details
    with pytest.raises(KeyError, match="Target goal ID\\(s\\) \\['non-existent-goal'\\] not found"):
        manifest.resolve_goals(["non-existent-goal"])

    # Mixed valid and non-existent IDs raises KeyError
    with pytest.raises(KeyError, match="invalid-goal-999"):
        manifest.resolve_goals(["goal-synthetic-da", "invalid-goal-999"])

    # BatchQueryRequest delegation to resolve_target_goals
    batch_req_discovery = BatchQueryRequest(
        batch_id="test-batch-discovery",
        snapshot_id=manifest.snapshot_id,
        sources=(),
        target_manifest=manifest,
        target_goal_ids=None,
    )
    assert len(batch_req_discovery.resolve_target_goals()) == 2

    # BatchQueryRequest with empty tuple also activates default discovery
    batch_req_empty = BatchQueryRequest(
        batch_id="test-batch-empty",
        snapshot_id=manifest.snapshot_id,
        sources=(),
        target_manifest=manifest,
        target_goal_ids=(),
    )
    assert batch_req_empty.resolve_target_goals() == batch_req_discovery.resolve_target_goals()

    batch_req_drilldown = BatchQueryRequest(
        batch_id="test-batch-drilldown",
        snapshot_id=manifest.snapshot_id,
        sources=(),
        target_manifest=manifest,
        target_goal_ids=("goal-synthetic-c0-host",),
    )
    assert [g.goal_id for g in batch_req_drilldown.resolve_target_goals()] == [
        "goal-synthetic-c0-host"
    ]


# ---------------------------------------------------------------------------
# 4. Case C: DA Checkpoint Reached vs Host Admin Goal Blocked
# ---------------------------------------------------------------------------


def test_case_c_da_checkpoint_vs_host_admin_blocked():
    """Demonstrate DA checkpoint reached while host administrative execution is blocked."""
    graph = EngineGraph.from_canonical(load_json(GRAPH_TWO_ROUTES_PATH))

    # Allow Alice to reach DA group, but block admin channel to Host C0
    assumptions = [
        make_assumption("security_group", ALICE_ID, ADMINS_ID, True),
        make_assumption("membership_usable", ALICE_ID, ADMINS_ID, True),
        make_assumption("admin_channel", ALICE_ID, HOST_C0_ID, False),
    ]

    q = AttackQuery(
        initial_actor=ALICE_ID,
        initial_state={"control": [ALICE_ID], "usable_identity": [[ALICE_ID, ALICE_ID]]},
        authentication_context=ALICE_ID,
        target=HOST_C0_ID,
        target_goal={"target": HOST_C0_ID, "required_state": {"admin_control": [HOST_C0_ID]}},
        checkpoint_goal={
            "target": ADMINS_ID,
            "required_state": {"effective_member": [[ALICE_ID, ADMINS_ID]]},
        },
        assumptions=assumptions,
        budget={"max_paths": 100, "max_steps": 10, "max_expansions": 1000},
    )
    res = run_attack_query(q, graph)

    assert res.checkpoint_reached is True
    assert res.final_goal_reached is False
    assert res.status == "checkpoint_reached_final_goal_blocked"


# ---------------------------------------------------------------------------
# 5. Case D: Source Node Eligibility Enforcement
# ---------------------------------------------------------------------------


def test_case_d_source_node_eligibility():
    """Verify User and Computer are supported, while Group, Domain, OU are rejected."""
    # User is supported
    p_user = create_foothold_profile(
        node_id=ALICE_ID,
        node_kind="User",
        profile_type=FootholdProfileKind.USER_USABLE_IDENTITY,
    )
    assert p_user.is_supported
    assert p_user.error_code is None
    assert p_user.unsupported_reason is None
    assert p_user.to_dict()["error_code"] is None

    # Computer is supported
    p_comp = create_foothold_profile(
        node_id=OTHERHOST_X_ID,
        node_kind="Computer",
        profile_type=FootholdProfileKind.COMPUTER_CONTROL_ADMIN,
    )
    assert p_comp.is_supported
    assert p_comp.error_code is None
    assert p_comp.unsupported_reason is None

    # Group is explicitly rejected
    p_group = create_foothold_profile(
        node_id=HELPDESK_ID,
        node_kind="Group",
        profile_type="unsupported",
    )
    assert not p_group.is_supported
    assert p_group.kind == FootholdProfileKind.UNSUPPORTED
    assert p_group.error_code == "UNSUPPORTED_FOOTHOLD_KIND"
    assert "cannot serve as an initial attack foothold" in (p_group.unsupported_reason or "")
    assert p_group.to_dict()["error_code"] == "UNSUPPORTED_FOOTHOLD_KIND"

    # OU is explicitly rejected
    p_ou = create_foothold_profile(
        node_id="OU=Workstations,DC=example,DC=test",
        node_kind="OU",
        profile_type="unsupported",
    )
    assert not p_ou.is_supported
    assert p_ou.kind == FootholdProfileKind.UNSUPPORTED
    assert p_ou.error_code == "UNSUPPORTED_FOOTHOLD_KIND"

    # Arbitrary unsupported/ineligible node kinds (e.g. RootCA, Container) are rejected
    p_ca = create_foothold_profile(
        node_id="CN=RootCA,CN=Public Key Services",
        node_kind="CertificationAuthority",
        profile_type="unsupported",
    )
    assert not p_ca.is_supported
    assert p_ca.kind == FootholdProfileKind.UNSUPPORTED
    assert p_ca.error_code == "UNSUPPORTED_FOOTHOLD_KIND"


# ---------------------------------------------------------------------------
# 6. Case E: Multi-Source Independent Execution & Immutability
# ---------------------------------------------------------------------------


def test_case_e_multi_source_execution_isolation():
    """Verify running multiple sources against the same graph produces isolated results."""
    graph_dict = load_json(GRAPH_TWO_ROUTES_PATH)
    graph_before = copy.deepcopy(graph_dict)
    graph = EngineGraph.from_canonical(graph_dict)

    # Source 1: Alice (reaches DA)
    q_alice = AttackQuery(
        initial_actor=ALICE_ID,
        initial_state={"control": [ALICE_ID], "usable_identity": [[ALICE_ID, ALICE_ID]]},
        authentication_context=ALICE_ID,
        target=ADMINS_ID,
        target_goal={
            "target": ADMINS_ID,
            "required_state": {"effective_member": [[ALICE_ID, ADMINS_ID]]},
        },
        assumptions=[
            make_assumption("security_group", ALICE_ID, ADMINS_ID, True),
            make_assumption("membership_usable", ALICE_ID, ADMINS_ID, True),
        ],
        budget={"max_paths": 10, "max_steps": 5, "max_expansions": 500},
    )
    res_alice = run_attack_query(q_alice, graph)
    assert res_alice.final_goal_reached

    # Source 2: OtherHost (no path to DA)
    q_host = AttackQuery(
        initial_actor=OTHERHOST_X_ID,
        initial_state={"control": [OTHERHOST_X_ID], "admin_control": [OTHERHOST_X_ID]},
        authentication_context=OTHERHOST_X_ID,
        target=ADMINS_ID,
        target_goal={
            "target": ADMINS_ID,
            "required_state": {"effective_member": [[OTHERHOST_X_ID, ADMINS_ID]]},
        },
        budget={"max_paths": 10, "max_steps": 5, "max_expansions": 500},
    )
    res_host = run_attack_query(q_host, graph)
    assert not res_host.final_goal_reached
    assert res_host.status == "no_path"

    # Graph remains completely unmodified
    assert graph.to_canonical() == graph_before


# ---------------------------------------------------------------------------
# 7. Case F: Missing Likelihood Basis Stays Unrated (Not Zero / Safe)
# ---------------------------------------------------------------------------


def test_case_f_missing_likelihood_stays_unrated():
    """Missing likelihood basis leaves path unrated; Min-Effort evaluates; path is not safe."""
    graph = EngineGraph.from_canonical(load_json(GRAPH_TWO_ROUTES_PATH))

    q = AttackQuery(
        initial_actor=ALICE_ID,
        initial_state={"control": [ALICE_ID], "usable_identity": [[ALICE_ID, ALICE_ID]]},
        authentication_context=ALICE_ID,
        target=ADMINS_ID,
        target_goal={
            "target": ADMINS_ID,
            "required_state": {"effective_member": [[ALICE_ID, ADMINS_ID]]},
        },
        assumptions=[
            make_assumption("security_group", ALICE_ID, ADMINS_ID, True),
            make_assumption("membership_usable", ALICE_ID, ADMINS_ID, True),
        ],
        budget={"max_paths": 10, "max_steps": 5, "max_expansions": 500},
    )
    res = run_attack_query(q, graph)

    assert res.final_goal_reached
    assert res.rating_coverage is None  # No rating resolution supplied
    # Search succeeds and path exists
    assert len(res.paths) == 1


# ---------------------------------------------------------------------------
# 8. Case G: Known-False Veto Over Declared Assumption
# ---------------------------------------------------------------------------


def test_case_g_known_false_veto():
    """An authoritative false fact vetoes a declared assumption and marks transition blocked."""
    graph = EngineGraph.from_canonical(load_json(GRAPH_TWO_ROUTES_PATH))

    # Provide conflicting facts: authoritative BLOCKED_EVIDENCE vs DECLARED_ASSUMPTION True
    facts = [
        RuntimeFact(
            predicate="admin_channel",
            subject=ALICE_ID,
            target=HOST_C0_ID,
            value=False,
            origin=FactOrigin.BLOCKED_EVIDENCE,
            scope="case_g",
            rationale="Firewall log proves port 5985 is blocked",
            provenance_reference="firewall_log_001",
        ),
        make_assumption("admin_channel", ALICE_ID, HOST_C0_ID, True),
    ]

    q = AttackQuery(
        initial_actor=ALICE_ID,
        initial_state={"control": [ALICE_ID], "admin_control": [HOST_C0_ID]},
        authentication_context=ALICE_ID,
        target=HOST_C0_ID,
        target_goal={"target": HOST_C0_ID, "required_state": {"admin_control": [HOST_C0_ID]}},
        runtime_facts=facts,
        budget={"max_paths": 10, "max_steps": 5, "max_expansions": 500},
    )
    res = run_attack_query(q, graph)

    # Check that rejected assumptions ledger recorded the known-false veto
    rejected = res.materialized_query.rejected_assumptions
    assert len(rejected) == 1
    assert rejected[0].reason == "known_false_veto"
    assert rejected[0].predicate == "admin_channel"


# ---------------------------------------------------------------------------
# 9. Case H: Truncated Search Cannot Prove Global Minimum
# ---------------------------------------------------------------------------


def test_case_h_truncated_search_bounds():
    """When budget limit is reached before goal, truncated=True and minimum is not proven."""
    graph = EngineGraph.from_canonical(load_json(GRAPH_TWO_ROUTES_PATH))

    # Path to C0 requires 2 steps (Alice -> Admins -> Host) when direct AdminTo is withheld
    # Set max_steps=1 to force truncation
    q = AttackQuery(
        initial_actor=ALICE_ID,
        initial_state={"control": [ALICE_ID], "usable_identity": [[ALICE_ID, ALICE_ID]]},
        authentication_context=ALICE_ID,
        target=HOST_C0_ID,
        target_goal={"target": HOST_C0_ID, "required_state": {"admin_control": [HOST_C0_ID]}},
        assumptions=[
            make_assumption("security_group", ALICE_ID, ADMINS_ID, True),
            make_assumption("membership_usable", ALICE_ID, ADMINS_ID, True),
            make_assumption("admin_channel", ADMINS_ID, HOST_C0_ID, True),
            make_assumption("authentication_accepted", ADMINS_ID, HOST_C0_ID, True),
        ],
        withheld_relationships=[StructuralRelationship(ALICE_ID, "AdminTo", HOST_C0_ID)],
        budget={"max_paths": 100, "max_steps": 1, "max_expansions": 1000},
    )
    res = run_attack_query(q, graph)

    assert not res.final_goal_reached
    assert res.truncated is True
    assert res.truncation_reason == "step_limit_reached"
    assert res.is_minimum_proven_over_scope is False


# ---------------------------------------------------------------------------
# 10. Case I: Multi-Criteria Prioritization & Deterministic Ties
# ---------------------------------------------------------------------------


def test_case_i_source_prioritization_and_tie_breaking():
    """Verify explainable multi-criteria source prioritization and deterministic tie-breaking."""
    manifest_data = load_json(FIXTURES_DIR / "target_manifest_synthetic.json")
    manifest = TargetManifest(
        manifest_id=manifest_data["manifest_id"],
        version=manifest_data["version"],
        snapshot_id=manifest_data["snapshot_id"],
        domain_sid=manifest_data["domain_sid"],
        default_discovery_goals=tuple(manifest_data["default_discovery_goals"]),
        targets=tuple(
            TargetGoal(
                goal_id=t["goal_id"],
                category=TargetGoalCategory(t["category"]),
                target_node_id=t["target_node_id"],
                target_node_kind=t["target_node_kind"],
                display_name=t["display_name"],
                technical_consequence=t["technical_consequence"],
                impact_rating=t["impact_rating"],
                required_control_level=TargetControlLevel(t["required_control_level"]),
                required_state=t["required_state"],
            )
            for t in manifest_data["targets"]
        ),
    )

    batch_result = load_json(FIXTURES_DIR / "batch_result_example.json")
    matrix = batch_result["source_goal_matrix"]

    ranked_sources, ties = prioritize_sources(matrix, manifest)

    assert len(ranked_sources) == 4
    # Rank 1: Alice (Catastrophic, unrated effort)
    assert ranked_sources[0].source_id == "src-alice-usable"
    assert ranked_sources[0].highest_impact_reached == "Catastrophic"
    assert ranked_sources[0].min_effort_to_highest_impact is None
    assert ranked_sources[0].priority_class == "High"

    # Rank 2: Bob (no path from Bob in two-routes.json graph)
    assert ranked_sources[1].source_id == "src-bob-password"
    assert ranked_sources[1].highest_impact_reached == "None"
    assert ranked_sources[1].min_effort_to_highest_impact is None
    assert ranked_sources[1].priority_class == "None"
    assert ranked_sources[1].disposition == "proven_no_path"

    # Rank 3: Helpdesk (unsupported group foothold)
    assert ranked_sources[2].source_id == "src-helpdesk-group"
    assert ranked_sources[2].highest_impact_reached == "None"
    assert ranked_sources[2].priority_class == "None"
    assert ranked_sources[2].disposition == "unsupported"

    # Rank 4: OtherHost (no path within search budget)
    assert ranked_sources[3].source_id == "src-otherhost-admin"
    assert ranked_sources[3].highest_impact_reached == "None"
    assert ranked_sources[3].priority_class == "None"
    assert ranked_sources[3].disposition == "proven_no_path"

    # Verify tie records (Bob, Helpdesk, OtherHost all have None impact, tie-broken by source_id)
    assert len(ties) == 2
    assert ties[0]["tie_breaker_applied"] == "source_id"
    assert ties[0]["selected_first"] == "src-bob-password"
    assert ties[1]["tie_breaker_applied"] == "source_id"
    assert ties[1]["selected_first"] == "src-helpdesk-group"


def test_case_i_source_metadata_mapping_from_sources():
    """Verify that prioritize_sources correctly resolves node_id, node_kind, and profile_kind."""
    manifest_data = load_json(FIXTURES_DIR / "target_manifest_synthetic.json")
    manifest = TargetManifest(
        manifest_id=manifest_data["manifest_id"],
        version=manifest_data["version"],
        snapshot_id=manifest_data["snapshot_id"],
        domain_sid=manifest_data["domain_sid"],
        targets=tuple(
            TargetGoal(
                goal_id=t["goal_id"],
                category=TargetGoalCategory(t["category"]),
                target_node_id=t["target_node_id"],
                target_node_kind=t["target_node_kind"],
                display_name=t["display_name"],
                technical_consequence=t["technical_consequence"],
                impact_rating=t["impact_rating"],
                required_control_level=TargetControlLevel(t["required_control_level"]),
                required_state=t["required_state"],
            )
            for t in manifest_data["targets"]
        ),
    )

    batch_result = load_json(FIXTURES_DIR / "batch_result_example.json")
    batch_request = load_json(FIXTURES_DIR / "batch_request_example.json")
    matrix = batch_result["source_goal_matrix"]
    sources = [
        BatchSourceItem(
            source_id=s["source_id"],
            node_id=s["node_id"],
            node_kind=s["node_kind"],
            profile_kind=s["profile_kind"],
        )
        for s in batch_request["sources"]
    ]

    ranked_sources, _ = prioritize_sources(matrix, manifest, sources=sources)

    # Alice
    assert ranked_sources[0].source_id == "src-alice-usable"
    assert ranked_sources[0].node_id == ALICE_ID
    assert ranked_sources[0].node_kind == "User"
    assert ranked_sources[0].profile_kind == "user_usable_identity"

    # Bob
    assert ranked_sources[1].source_id == "src-bob-password"
    assert ranked_sources[1].node_id == BOB_ID
    assert ranked_sources[1].node_kind == "User"
    assert ranked_sources[1].profile_kind == "user_leaked_password"

    # Helpdesk
    assert ranked_sources[2].source_id == "src-helpdesk-group"
    assert ranked_sources[2].node_id == HELPDESK_ID
    assert ranked_sources[2].node_kind == "Group"
    assert ranked_sources[2].profile_kind == "unsupported"

    # OtherHost
    assert ranked_sources[3].source_id == "src-otherhost-admin"
    assert ranked_sources[3].node_id == OTHERHOST_X_ID
    assert ranked_sources[3].node_kind == "Computer"
    assert ranked_sources[3].profile_kind == "computer_control_admin"


def test_case_i_unrated_likelihood_prioritization():
    """Verify non-numeric likelihood tiering policy without synthetic 0.50 score.

    For sources with identical impact, effort, and reachability:
    Rank 1: High rated likelihood (e.g. [0.80, 0.90], rated tier 1, lower bound 0.80)
    Rank 2: Low rated likelihood (e.g. [0.05, 0.10], rated tier 1, lower bound 0.05)
    Rank 3: Unrated likelihood (unrated tier 0, never given synthetic 0.50)

    Additionally, when an unrated source has a larger blast radius (more reachable goals),
    blast radius is evaluated before likelihood, preventing low-rated sources from demoting it.
    """
    manifest_data = load_json(FIXTURES_DIR / "target_manifest_synthetic.json")
    manifest = TargetManifest(
        manifest_id=manifest_data["manifest_id"],
        version=manifest_data["version"],
        snapshot_id=manifest_data["snapshot_id"],
        domain_sid=manifest_data["domain_sid"],
        targets=tuple(
            TargetGoal(
                goal_id=t["goal_id"],
                category=TargetGoalCategory(t["category"]),
                target_node_id=t["target_node_id"],
                target_node_kind=t["target_node_kind"],
                display_name=t["display_name"],
                technical_consequence=t["technical_consequence"],
                impact_rating=t["impact_rating"],
                required_control_level=TargetControlLevel(t["required_control_level"]),
                required_state=t["required_state"],
            )
            for t in manifest_data["targets"]
        ),
    )

    cell_high = SourceGoalCell(
        status=BatchCellStatus.COMPLETE_SUCCESS,
        control_level_attained=TargetControlLevel.ADMIN_ENTITLEMENT,
        min_effort=1.0,
        min_effort_path={"cost": 1.0, "steps": ["step1"]},
        likelihood_interval=(0.80, 0.90),
        likelihood_status="rated",
        impact="Catastrophic",
    )
    cell_unrated = SourceGoalCell(
        status=BatchCellStatus.COMPLETE_SUCCESS,
        control_level_attained=TargetControlLevel.ADMIN_ENTITLEMENT,
        min_effort=1.0,
        min_effort_path={"cost": 1.0, "steps": ["step1"]},
        likelihood_interval=None,
        likelihood_status="unrated",
        impact="Catastrophic",
    )
    cell_low = SourceGoalCell(
        status=BatchCellStatus.COMPLETE_SUCCESS,
        control_level_attained=TargetControlLevel.ADMIN_ENTITLEMENT,
        min_effort=1.0,
        min_effort_path={"cost": 1.0, "steps": ["step1"]},
        likelihood_interval=(0.05, 0.10),
        likelihood_status="rated",
        impact="Catastrophic",
    )

    test_matrix = {
        "src-low-rated": {"goal-synthetic-da": cell_low},
        "src-unrated": {"goal-synthetic-da": cell_unrated},
        "src-high-rated": {"goal-synthetic-da": cell_high},
    }

    ranked, _ = prioritize_sources(test_matrix, manifest)

    assert len(ranked) == 3
    assert ranked[0].source_id == "src-high-rated"
    assert ranked[0].likelihood_to_highest_impact == (0.80, 0.90)

    # Mutually rated compared by lower bound; unrated has no synthetic 0.50 scalar
    assert ranked[1].source_id == "src-low-rated"
    assert ranked[1].likelihood_to_highest_impact == (0.05, 0.10)

    assert ranked[2].source_id == "src-unrated"
    assert ranked[2].likelihood_to_highest_impact is None

    # However, if unrated source reaches 2 goals, blast radius places it above
    # single-goal low-rated source
    matrix_blast = {
        "src-low-rated": {"goal-synthetic-da": cell_low},
        "src-unrated-2goals": {
            "goal-synthetic-da": cell_unrated,
            "goal-synthetic-c0-host": SourceGoalCell(
                status=BatchCellStatus.COMPLETE_SUCCESS,
                control_level_attained=TargetControlLevel.HOST_ADMIN_EXECUTION,
                min_effort=1.0,
                min_effort_path={"cost": 1.0, "steps": ["step1"]},
                likelihood_interval=None,
                likelihood_status="unrated",
                impact="High",
            ),
        },
    }
    ranked_blast, _ = prioritize_sources(matrix_blast, manifest)
    assert ranked_blast[0].source_id == "src-unrated-2goals"
    assert ranked_blast[1].source_id == "src-low-rated"


def test_case_i_tie_breaking_hierarchy():
    """Verify tier-0 count, reachable count, steps, and source_id tie-breaking order."""
    manifest_data = load_json(FIXTURES_DIR / "target_manifest_synthetic.json")
    manifest = TargetManifest(
        manifest_id=manifest_data["manifest_id"],
        version=manifest_data["version"],
        snapshot_id=manifest_data["snapshot_id"],
        domain_sid=manifest_data["domain_sid"],
        targets=tuple(
            TargetGoal(
                goal_id=t["goal_id"],
                category=TargetGoalCategory(t["category"]),
                target_node_id=t["target_node_id"],
                target_node_kind=t["target_node_kind"],
                display_name=t["display_name"],
                technical_consequence=t["technical_consequence"],
                impact_rating=t["impact_rating"],
                required_control_level=TargetControlLevel(t["required_control_level"]),
                required_state=t["required_state"],
            )
            for t in manifest_data["targets"]
        ),
    )

    # Two sources tied on impact, effort, likelihood, but one has fewer steps
    cell_steps2 = SourceGoalCell(
        status=BatchCellStatus.COMPLETE_SUCCESS,
        control_level_attained=TargetControlLevel.ADMIN_ENTITLEMENT,
        min_effort=2.0,
        min_effort_path={"cost": 2.0, "steps": ["step1", "step2"]},
        likelihood_interval=None,
        likelihood_status="unrated",
        impact="High",
    )
    cell_steps4 = SourceGoalCell(
        status=BatchCellStatus.COMPLETE_SUCCESS,
        control_level_attained=TargetControlLevel.ADMIN_ENTITLEMENT,
        min_effort=2.0,
        min_effort_path={"cost": 2.0, "steps": ["step1", "step2", "step3", "step4"]},
        likelihood_interval=None,
        likelihood_status="unrated",
        impact="High",
    )

    matrix_steps = {
        "src-z-steps4": {"goal-synthetic-c0-host": cell_steps4},
        "src-a-steps2": {"goal-synthetic-c0-host": cell_steps2},
    }

    ranked, ties = prioritize_sources(matrix_steps, manifest)
    assert ranked[0].source_id == "src-a-steps2"
    assert ranked[1].source_id == "src-z-steps4"
    assert len(ties) == 1
    assert ties[0]["tie_breaker_applied"] == "steps"
    assert ties[0]["selected_first"] == "src-a-steps2"


# ---------------------------------------------------------------------------
# 11. Mathematical Validation of Policy Counterexamples
# ---------------------------------------------------------------------------


def test_counterexample_anti_probability_summation():
    """Verify mathematical proof that probability summation violates Kolmogorov axioms."""
    ce_data = load_json(FIXTURES_DIR / "policy_counterexamples.json")
    ce_01 = next(c for c in ce_data["counterexamples"] if c["id"] == "CE-01-PROBABILITY-SUMMATION")

    p1 = ce_01["paths"][0]["conditional_p"]
    p2 = ce_01["paths"][1]["conditional_p"]
    naive_sum = p1 + p2

    assert naive_sum > 1.0  # 0.60 + 0.55 = 1.15 > 1.0
    assert ce_01["flawed_calculation"]["result"] == naive_sum


def test_counterexample_unrated_not_treated_as_zero():
    """Verify unrated low-effort path is not dismissed for noisy high-effort rated path."""
    ce_data = load_json(FIXTURES_DIR / "policy_counterexamples.json")
    ce_02 = next(c for c in ce_data["counterexamples"] if c["id"] == "CE-02-UNRATED-AS-ZERO")

    rbcd_effort = ce_02["paths"][0]["effort"]
    phishing_effort = ce_02["paths"][1]["effort"]

    assert rbcd_effort < phishing_effort  # 2.0 < 12.0
    assert ce_02["paths"][0]["likelihood_status"] == "unrated"


# ---------------------------------------------------------------------------
# 12. SEAMLESS Snapshot-Pinned Target Manifest Validation
# ---------------------------------------------------------------------------


def test_seamless_target_manifest_pins():
    """Verify that SEAMLESS target manifest pins canonical Active Directory SIDs and locators."""
    manifest = load_json(FIXTURES_DIR / "target_manifest_seamless.json")

    assert (
        manifest["snapshot_id"]
        == "sha256:e0601d763eeea285d268ec9e468d321c50c9d7faba53c8e7442a2fcc4159c812"
    )
    domain_sid = manifest["domain_sid"]
    assert domain_sid == "S-1-5-21-1271839998-3495686680-2211690266"

    # DA group has RID 512
    da_target = next(
        t for t in manifest["targets"] if t["goal_id"] == "goal-seamless-da-entitlement"
    )
    assert da_target["target_node_id"] == f"{domain_sid}-512"
    assert da_target["provenance_locator"] == "20210920185958_groups.json#/groups/40"

    # EA group has RID 519
    ea_target = next(
        t for t in manifest["targets"] if t["goal_id"] == "goal-seamless-ea-entitlement"
    )
    assert ea_target["target_node_id"] == f"{domain_sid}-519"
    assert ea_target["provenance_locator"] == "20210920185958_groups.json#/groups/18"

    # DC computer has RID 1000
    dc_target = next(t for t in manifest["targets"] if t["goal_id"] == "goal-seamless-dc-admin")
    assert dc_target["target_node_id"] == f"{domain_sid}-1000"
    assert dc_target["provenance_locator"] == "20210920185958_computers.json#/computers/0"


# ---------------------------------------------------------------------------
# 13. PR #270 Review Regressions and Conformance Tests
# ---------------------------------------------------------------------------


def test_model_serializers_schema_validation():
    """Verify that .to_dict() of all models validates against Draft 2020-12 schemas."""
    # 1. TargetManifest with default description=None
    manifest = TargetManifest(
        manifest_id="manifest-test-defaults",
        version="1.0.0",
        snapshot_id="sha256:cc6b062c65d9266268673105c46c9b0ec199a17fedb70cb3ab64407361c389d3",
        domain_sid="S-1-5-21-1000-2000-3000",
        description=None,
        default_discovery_goals=("goal-1",),
        targets=(
            TargetGoal(
                goal_id="goal-1",
                category=TargetGoalCategory.TIER_0_IDENTITY,
                target_node_id="S-1-5-21-1000-2000-3000-2103",
                target_node_kind="Group",
                display_name="Domain Admins",
                technical_consequence="domain_admin_entitlement",
                impact_rating="Catastrophic",
                required_control_level=TargetControlLevel.ADMIN_ENTITLEMENT,
                required_state={
                    "effective_member": [["__RESOLVED_ACTOR__", "S-1-5-21-1000-2000-3000-2103"]]
                },
                description=None,
            ),
        ),
    )
    manifest_dict = manifest.to_dict()
    assert manifest_dict["schema_version"] == "target-manifest/1.0.0"
    schema_manifest = load_json(SCHEMAS_DIR / "target-manifest.schema.json")
    v_manifest = Draft202012Validator(schema_manifest)
    assert not list(v_manifest.iter_errors(manifest_dict))

    # 2. BatchQueryRequest.to_dict()
    req = BatchQueryRequest(
        batch_id="batch-test-req",
        snapshot_id=manifest.snapshot_id,
        sources=(
            BatchSourceItem(
                source_id="src-alice",
                node_id="S-1-5-21-1000-2000-3000-1101",
                node_kind="User",
                profile_kind="user_usable_identity",
            ),
        ),
        target_manifest=manifest,
        target_goal_ids=None,
    )
    req_dict = req.to_dict()
    assert req_dict["schema_version"] == "batch-query-request/1.0.0"
    schema_req = load_json(SCHEMAS_DIR / "batch-query-request.schema.json")
    v_req = Draft202012Validator(schema_req)
    assert not list(v_req.iter_errors(req_dict))

    # 3. FootholdProfile.to_dict() with default assumptions and valid Computer context
    profile = create_foothold_profile(
        profile_id="prof-bob",
        node_id=BOB_ID,
        node_kind="User",
        profile_type="user_leaked_password",
        authentication_context=HOST_C0_ID,
        assumptions=[
            {
                "predicate": "secret_valid",
                "subject": BOB_ID,
                "target": HOST_C0_ID,
            }
        ],
    )
    prof_dict = profile.to_dict()
    schema_prof = load_json(SCHEMAS_DIR / "foothold-profiles.schema.json")
    v_prof_item = Draft202012Validator(schema_prof["$defs"]["footholdProfile"])
    assert not list(v_prof_item.iter_errors(prof_dict))

    v_prof_doc = Draft202012Validator(schema_prof)
    assert not list(
        v_prof_doc.iter_errors(
            {
                "schema_version": "foothold-profiles/1.0.0",
                "profiles": [prof_dict],
            }
        )
    )

    # Also verify schema conformance for an unresolved/missing authentication_context profile
    profile_missing_ctx = create_foothold_profile(
        profile_id="prof-bob-unresolved",
        node_id=BOB_ID,
        node_kind="User",
        profile_type="user_leaked_password",
        authentication_context=None,
    )
    prof_missing_dict = profile_missing_ctx.to_dict()
    assert prof_missing_dict["authentication_context"] is None
    assert prof_missing_dict["is_supported"] is False
    assert prof_missing_dict["error_code"] == "MISSING_AUTHENTICATION_CONTEXT"
    assert not list(v_prof_item.iter_errors(prof_missing_dict))

    # 4. BatchQueryResult.to_dict()
    result_model = BatchQueryResult(
        batch_id="batch-test-result",
        snapshot_id=manifest.snapshot_id,
        reproducibility={"revision": "rev-test", "inputs": {}, "runtime": {}},
        summary={
            "total_sources": 1,
            "supported_sources": 1,
            "unsupported_sources": 0,
            "successful_sources": 1,
            "sources_reaching_tier_0": 1,
            "status_counts": {"complete_success": 1},
        },
        source_goal_matrix={
            "src-alice": {
                "goal-1": SourceGoalCell(
                    status=BatchCellStatus.COMPLETE_SUCCESS,
                    control_level_attained=TargetControlLevel.ADMIN_ENTITLEMENT,
                    min_effort=1.0,
                    likelihood_status="unrated",
                    truncated=False,
                )
            }
        },
        source_prioritization=(
            SourcePrioritizationEntry(
                rank=1,
                source_id="src-alice",
                node_id="S-1-5-21-1000-2000-3000-1101",
                node_kind="User",
                profile_kind="user_usable_identity",
                highest_impact_reached="Catastrophic",
                min_effort_to_highest_impact=1.0,
                likelihood_to_highest_impact=None,
                reachable_goals_count=1,
                reachable_tier_0_goals=("goal-1",),
                priority_class="Critical",
                explainability="Source src-alice attains Catastrophic compromise.",
                disposition="complete",
            ),
        ),
        tie_breaking_applied=(),
    )
    result_dict = result_model.to_dict()
    assert result_dict["schema_version"] == "batch-query-result/1.0.0"
    schema_res = load_json(SCHEMAS_DIR / "batch-query-result.schema.json")
    v_res = Draft202012Validator(schema_res)
    assert not list(v_res.iter_errors(result_dict))


def test_foothold_profile_default_assumptions_provenance_integration():
    """Verify factory defaults attach valid provenance so public query does not raise."""
    graph = EngineGraph.from_canonical(GRAPH_TWO_ROUTES_PATH.read_text())
    profile = create_foothold_profile(
        profile_id="src-default-prov",
        node_id=ALICE_ID,
        node_kind="User",
        profile_type="user_usable_identity",
        assumptions=[
            {
                "predicate": "admin_channel",
                "subject": ALICE_ID,
                "target": HOST_C0_ID,
                "value": True,
            }
        ],
    )

    # Must preserve provenance reference and declared_by
    assert profile.declared_assumptions[0].provenance_reference == "foothold:src-default-prov"
    assert (
        profile.declared_assumptions[0].assumption_metadata.get("declared_by") == "security_analyst"
    )

    # Passing to public AttackQuery must not raise provenance ValueError
    target_goal = {"target": HOST_C0_ID, "required_state": {"admin_control": [HOST_C0_ID]}}
    q = AttackQuery(
        target=HOST_C0_ID,
        source_foothold=profile.node_id,
        initial_actor=profile.initial_actor,
        initial_state=profile.initial_attack_state,
        authentication_context=profile.authentication_context,
        target_goal=target_goal,
        assumptions=profile.declared_assumptions,
    )
    res = run_attack_query(q, graph)
    assert res is not None

    # Also verify that a raw RuntimeFact without provenance is normalized
    raw_fact = RuntimeFact(
        predicate="admin_channel",
        subject=ALICE_ID,
        target=HOST_C0_ID,
        value=True,
        origin=FactOrigin.DECLARED_ASSUMPTION,
        scope="foothold_declaration",
        rationale="Raw RuntimeFact assumption",
    )
    profile_rf = create_foothold_profile(
        profile_id="src-rf-prov",
        node_id=ALICE_ID,
        node_kind="User",
        profile_type="user_usable_identity",
        assumptions=[raw_fact],
    )
    assert profile_rf.declared_assumptions[0].provenance_reference == "foothold:src-rf-prov"
    assert (
        profile_rf.declared_assumptions[0].assumption_metadata.get("declared_by")
        == "security_analyst"
    )


def test_map_query_result_to_cell_conformance():
    """Verify mapping from AttackQueryResult to SourceGoalCell preserves checkpoint states."""
    goal = TargetGoal(
        goal_id="goal-c0",
        category=TargetGoalCategory.TIER_0_HOST,
        target_node_id=HOST_C0_ID,
        target_node_kind="Computer",
        display_name="C0 Host",
        technical_consequence="host_admin",
        impact_rating="High",
        required_control_level=TargetControlLevel.HOST_ADMIN_EXECUTION,
        required_state={"admin_control": [HOST_C0_ID]},
    )

    class MockResult:
        def __init__(self, **kwargs):
            self.checkpoint_reached = kwargs.get("checkpoint_reached", False)
            self.final_goal_reached = kwargs.get("final_goal_reached", False)
            self.truncated = kwargs.get("truncated", False)
            self.status = kwargs.get("status", "no_path")
            self.min_effort_baseline = kwargs.get("min_effort_baseline")
            self.best_path = kwargs.get("best_path")
            self.paths = kwargs.get("paths", ())
            self.diagnostics = kwargs.get("diagnostics", ())
            self.expansions = kwargs.get("expansions", 10)

    # 1. Checkpoint reached, final goal blocked
    c_blocked = map_query_result_to_cell(
        MockResult(checkpoint_reached=True, final_goal_reached=False, status="blocked"),
        goal,
    )
    assert c_blocked.status == BatchCellStatus.CHECKPOINT_REACHED_FINAL_GOAL_BLOCKED
    assert c_blocked.checkpoint_reached is True
    assert c_blocked.final_goal_reached is False

    # 2. Checkpoint reached, final goal indeterminate
    c_indet = map_query_result_to_cell(
        MockResult(checkpoint_reached=True, final_goal_reached=False, status="indeterminate"),
        goal,
    )
    assert c_indet.status == BatchCellStatus.CHECKPOINT_REACHED_FINAL_GOAL_INDETERMINATE
    assert c_indet.checkpoint_reached is True
    assert c_indet.final_goal_reached is False

    # 3. Checkpoint reached, final goal no_path
    c_nopath = map_query_result_to_cell(
        MockResult(checkpoint_reached=True, final_goal_reached=False, status="no_path"),
        goal,
    )
    assert c_nopath.status == BatchCellStatus.CHECKPOINT_REACHED_FINAL_GOAL_NO_PATH
    assert c_nopath.checkpoint_reached is True
    assert c_nopath.final_goal_reached is False

    # 4. Checkpoint reached, final goal truncated
    c_trunc = map_query_result_to_cell(
        MockResult(checkpoint_reached=True, final_goal_reached=False, truncated=True),
        goal,
    )
    assert c_trunc.checkpoint_reached is True
    assert c_trunc.final_goal_reached is False

    # 5. Checkpoint reached, final goal checkpoint_only
    c_chk_only = map_query_result_to_cell(
        MockResult(checkpoint_reached=True, final_goal_reached=False, status="checkpoint_only"),
        goal,
    )
    assert c_chk_only.status == BatchCellStatus.CHECKPOINT_ONLY
    assert c_chk_only.checkpoint_reached is True
    assert c_chk_only.final_goal_reached is False

    # 6. Execution error without checkpoint
    c_err = map_query_result_to_cell(
        MockResult(checkpoint_reached=False, final_goal_reached=False, status="error"),
        goal,
    )
    assert c_err.status == BatchCellStatus.ERROR
    assert c_err.checkpoint_reached is False
    assert c_err.final_goal_reached is False


def test_incomplete_and_error_sources_disposition_not_no_path():
    """Verify error, indeterminate, and truncated sources are not collapsed into no-path."""
    manifest_data = load_json(FIXTURES_DIR / "target_manifest_synthetic.json")
    manifest = TargetManifest(
        manifest_id=manifest_data["manifest_id"],
        version=manifest_data["version"],
        snapshot_id=manifest_data["snapshot_id"],
        domain_sid=manifest_data["domain_sid"],
        targets=tuple(
            TargetGoal(
                goal_id=t["goal_id"],
                category=TargetGoalCategory(t["category"]),
                target_node_id=t["target_node_id"],
                target_node_kind=t["target_node_kind"],
                display_name=t["display_name"],
                technical_consequence=t["technical_consequence"],
                impact_rating=t["impact_rating"],
                required_control_level=TargetControlLevel(t["required_control_level"]),
                required_state=t["required_state"],
            )
            for t in manifest_data["targets"]
        ),
    )

    cell_error = SourceGoalCell(
        status=BatchCellStatus.ERROR,
        control_level_attained=TargetControlLevel.NONE,
        diagnostics=({"code": "TIMEOUT", "message": "Search timed out"},),
    )
    cell_indet = SourceGoalCell(
        status=BatchCellStatus.INDETERMINATE,
        control_level_attained=TargetControlLevel.NONE,
    )
    cell_trunc = SourceGoalCell(
        status=BatchCellStatus.TRUNCATED_INCOMPLETE,
        control_level_attained=TargetControlLevel.NONE,
        truncated=True,
    )

    matrix = {
        "src-error": {"goal-synthetic-da": cell_error},
        "src-indet": {"goal-synthetic-da": cell_indet},
        "src-trunc": {"goal-synthetic-da": cell_trunc},
    }

    ranked, _ = prioritize_sources(matrix, manifest)
    rank_by_id = {r.source_id: r for r in ranked}

    # All incomplete/error sources must have Unknown impact and priority class
    assert rank_by_id["src-error"].highest_impact_reached == "Unknown"
    assert rank_by_id["src-error"].priority_class == "Unknown"
    assert rank_by_id["src-error"].disposition == "error"
    assert "no viable attack path" not in rank_by_id["src-error"].explainability.lower()

    assert rank_by_id["src-indet"].highest_impact_reached == "Unknown"
    assert rank_by_id["src-indet"].priority_class == "Unknown"
    assert rank_by_id["src-indet"].disposition == "indeterminate"
    assert "no viable attack path" not in rank_by_id["src-indet"].explainability.lower()

    assert rank_by_id["src-trunc"].highest_impact_reached == "Unknown"
    assert rank_by_id["src-trunc"].priority_class == "Unknown"
    assert rank_by_id["src-trunc"].disposition == "truncated_incomplete"
    assert "no viable attack path" not in rank_by_id["src-trunc"].explainability.lower()


def test_mixed_rated_unrated_source_aggregation_and_ranking():
    """Verify nairyuuu probe: Source A (2 goals) outranks Source B (1 goal unrated)."""
    manifest_data = load_json(FIXTURES_DIR / "target_manifest_synthetic.json")
    manifest = TargetManifest(
        manifest_id=manifest_data["manifest_id"],
        version=manifest_data["version"],
        snapshot_id=manifest_data["snapshot_id"],
        domain_sid=manifest_data["domain_sid"],
        targets=tuple(
            TargetGoal(
                goal_id=t["goal_id"],
                category=TargetGoalCategory(t["category"]),
                target_node_id=t["target_node_id"],
                target_node_kind=t["target_node_kind"],
                display_name=t["display_name"],
                technical_consequence=t["technical_consequence"],
                impact_rating=t["impact_rating"],
                required_control_level=TargetControlLevel(t["required_control_level"]),
                required_state=t["required_state"],
            )
            for t in manifest_data["targets"]
        ),
    )

    cell_unrated = SourceGoalCell(
        status=BatchCellStatus.COMPLETE_SUCCESS,
        control_level_attained=TargetControlLevel.ADMIN_ENTITLEMENT,
        min_effort=1.0,
        min_effort_path={"cost": 1.0, "steps": ["step1"]},
        likelihood_interval=None,
        likelihood_status="unrated",
        impact="Catastrophic",
    )
    cell_low = SourceGoalCell(
        status=BatchCellStatus.COMPLETE_SUCCESS,
        control_level_attained=TargetControlLevel.HOST_ADMIN_EXECUTION,
        min_effort=1.0,
        min_effort_path={"cost": 1.0, "steps": ["step2"]},
        likelihood_interval=(0.05, 0.10),
        likelihood_status="rated",
        impact="Catastrophic",
    )

    # Source A reaches 2 goals: one unrated, one low-rated
    # Source B reaches 1 goal: unrated
    matrix = {
        "src-a-mixed": {
            "goal-synthetic-da": cell_unrated,
            "goal-synthetic-c0-host": cell_low,
        },
        "src-b-single": {
            "goal-synthetic-da": cell_unrated,
        },
    }

    ranked, ties = prioritize_sources(matrix, manifest)

    # Source A must outrank Source B because reachable_count 2 > 1
    assert ranked[0].source_id == "src-a-mixed"
    assert ranked[0].reachable_goals_count == 2
    assert ranked[1].source_id == "src-b-single"
    assert ranked[1].reachable_goals_count == 1

    # Verify no synthetic 0.50 was reported or injected
    for r in ranked:
        assert "0.50" not in r.explainability
        assert "0.5" not in r.explainability


def test_full_batch_replay_conformance_against_frozen_graph():
    """Verify replay of batch_request_example against two-routes.json matches result."""
    graph = EngineGraph.from_canonical(GRAPH_TWO_ROUTES_PATH.read_text())
    req_data = load_json(FIXTURES_DIR / "batch_request_example.json")
    expected_result_data = load_json(FIXTURES_DIR / "batch_result_example.json")

    manifest_data = req_data["target_manifest"]
    manifest = TargetManifest(
        manifest_id=manifest_data["manifest_id"],
        version=manifest_data["version"],
        snapshot_id=manifest_data["snapshot_id"],
        domain_sid=manifest_data["domain_sid"],
        default_discovery_goals=tuple(manifest_data["default_discovery_goals"]),
        targets=tuple(
            TargetGoal(
                goal_id=t["goal_id"],
                category=TargetGoalCategory(t["category"]),
                target_node_id=t["target_node_id"],
                target_node_kind=t["target_node_kind"],
                display_name=t["display_name"],
                technical_consequence=t["technical_consequence"],
                impact_rating=t["impact_rating"],
                required_control_level=TargetControlLevel(t["required_control_level"]),
                required_state=t["required_state"],
                checkpoint_goal=t.get("checkpoint_goal"),
            )
            for t in manifest_data["targets"]
        ),
    )

    sources = tuple(
        BatchSourceItem(
            source_id=s["source_id"],
            node_id=s["node_id"],
            node_kind=s["node_kind"],
            profile_kind=s["profile_kind"],
            authentication_context=s.get("authentication_context"),
            declared_assumptions=tuple(s.get("declared_assumptions", [])),
        )
        for s in req_data["sources"]
    )

    req = BatchQueryRequest(
        batch_id=req_data["batch_id"],
        snapshot_id=req_data["snapshot_id"],
        sources=sources,
        target_manifest=manifest,
        target_goal_ids=req_data.get("target_goal_ids"),
    )

    goals = req.resolve_target_goals()
    matrix: dict[str, dict[str, SourceGoalCell]] = {}

    for src in req.sources:
        matrix[src.source_id] = {}
        profile = src.to_foothold_profile(declared_by="test-analyst")
        for g in goals:
            if not profile.is_supported:
                cell = SourceGoalCell(
                    status=BatchCellStatus.UNSUPPORTED_SOURCE,
                    control_level_attained=TargetControlLevel.NONE,
                    min_effort=None,
                    min_effort_path=None,
                    likelihood_interval=None,
                    likelihood_status="unrated",
                    impact=None,
                    checkpoint_reached=False,
                    final_goal_reached=False,
                    optimization_scope=None,
                    truncated=False,
                    truncation_reason=None,
                    expansions=0,
                    diagnostics=(
                        {
                            "code": profile.error_code or "UNSUPPORTED_FOOTHOLD_KIND",
                            "message": profile.unsupported_reason or "Unsupported foothold",
                        },
                    ),
                )
            else:
                tg = (
                    {"target": g.target_node_id, "required_state": g.required_state}
                    if g.required_state
                    else None
                )
                cg = dict(g.checkpoint_goal) if g.checkpoint_goal else None
                q = AttackQuery(
                    target=g.target_node_id,
                    source_foothold=profile.node_id,
                    initial_actor=profile.initial_actor,
                    initial_state=profile.initial_attack_state,
                    authentication_context=profile.authentication_context,
                    target_goal=tg,
                    checkpoint_goal=cg,
                    assumptions=profile.declared_assumptions,
                    aliases={"__RESOLVED_ACTOR__": profile.initial_actor or profile.node_id},
                    budget=src.custom_budget or req.common_budget,
                )
                res = run_attack_query(q, graph)
                cell = map_query_result_to_cell(res, g)
            matrix[src.source_id][g.goal_id] = cell

    ranked, ties = prioritize_sources(matrix, manifest, sources=req.sources)

    replayed_result = BatchQueryResult(
        batch_id=req.batch_id,
        snapshot_id=req.snapshot_id,
        reproducibility=expected_result_data["reproducibility"],
        summary={
            "total_sources": len(req.sources),
            "supported_sources": sum(1 for s in req.sources if s.profile_kind != "unsupported"),
            "unsupported_sources": sum(1 for s in req.sources if s.profile_kind == "unsupported"),
            "successful_sources": sum(1 for r in ranked if r.disposition == "complete"),
            "sources_reaching_tier_0": sum(1 for r in ranked if len(r.reachable_tier_0_goals) > 0),
            "status_counts": {
                "complete_success": sum(
                    1
                    for row in matrix.values()
                    for c in row.values()
                    if c.status == BatchCellStatus.COMPLETE_SUCCESS
                ),
                "no_path": sum(
                    1
                    for row in matrix.values()
                    for c in row.values()
                    if c.status == BatchCellStatus.NO_PATH
                ),
                "unsupported_source": sum(
                    1
                    for row in matrix.values()
                    for c in row.values()
                    if c.status == BatchCellStatus.UNSUPPORTED_SOURCE
                ),
            },
        },
        source_goal_matrix=matrix,
        source_prioritization=ranked,
        tie_breaking_applied=ties,
    )

    replayed_dict = replayed_result.to_dict()
    assert replayed_dict == expected_result_data


def test_prioritize_sources_goal_order_independence():
    """Verify prioritize_sources yields identical results regardless of goal dictionary order."""
    manifest = TargetManifest(
        manifest_id="manifest-order-test",
        version="1.0.0",
        snapshot_id="sha256:cc6b062c65d9266268673105c46c9b0ec199a17fedb70cb3ab64407361c389d3",
        domain_sid="S-1-5-21-1000-2000-3000",
        targets=(
            TargetGoal(
                goal_id="g1",
                category=TargetGoalCategory.TIER_0_IDENTITY,
                target_node_id="t1",
                target_node_kind="Group",
                display_name="Goal 1",
                technical_consequence="c1",
                impact_rating="Catastrophic",
                required_control_level=TargetControlLevel.ADMIN_ENTITLEMENT,
                required_state={},
            ),
            TargetGoal(
                goal_id="g2",
                category=TargetGoalCategory.TIER_0_IDENTITY,
                target_node_id="t2",
                target_node_kind="Group",
                display_name="Goal 2",
                technical_consequence="c2",
                impact_rating="Catastrophic",
                required_control_level=TargetControlLevel.ADMIN_ENTITLEMENT,
                required_state={},
            ),
        ),
    )

    cell_rated = SourceGoalCell(
        status=BatchCellStatus.COMPLETE_SUCCESS,
        control_level_attained=TargetControlLevel.ADMIN_ENTITLEMENT,
        min_effort=1.0,
        min_effort_path={"cost": 1.0, "steps": ["s1", "s2", "s3", "s4", "s5", "s6"]},
        likelihood_interval=(0.05, 0.10),
        likelihood_status="rated",
        impact="Catastrophic",
    )
    cell_unrated = SourceGoalCell(
        status=BatchCellStatus.COMPLETE_SUCCESS,
        control_level_attained=TargetControlLevel.ADMIN_ENTITLEMENT,
        min_effort=1.0,
        min_effort_path={"cost": 1.0, "steps": ["s1"]},
        likelihood_interval=None,
        likelihood_status="unrated",
        impact="Catastrophic",
    )

    # Order 1: g1 (rated) first, g2 (unrated) second
    m1 = {"src": {"g1": cell_rated, "g2": cell_unrated}}
    r1, ties1 = prioritize_sources(m1, manifest)

    # Order 2: g2 (unrated) first, g1 (rated) second
    m2 = {"src": {"g2": cell_unrated, "g1": cell_rated}}
    r2, ties2 = prioritize_sources(m2, manifest)

    assert r1[0].to_dict() == r2[0].to_dict()
    assert ties1 == ties2


def test_rated_low_vs_unrated_prioritization_and_audit():
    """Verify rated-low vs unrated prioritization adheres to non-numeric tiering policy.

    Confirms:
    1. Rated-low (tier 1) is ordered before unrated (tier 0) without synthetic 0.50.
    2. Missing likelihood basis is never reported as a numeric probability or scalar.
    3. Multi-target blast radius outranks single-target rated-low.
    """
    manifest_data = load_json(FIXTURES_DIR / "target_manifest_synthetic.json")
    manifest = TargetManifest(
        manifest_id=manifest_data["manifest_id"],
        version=manifest_data["version"],
        snapshot_id=manifest_data["snapshot_id"],
        domain_sid=manifest_data["domain_sid"],
        targets=tuple(
            TargetGoal(
                goal_id=t["goal_id"],
                category=TargetGoalCategory(t["category"]),
                target_node_id=t["target_node_id"],
                target_node_kind=t["target_node_kind"],
                display_name=t["display_name"],
                technical_consequence=t["technical_consequence"],
                impact_rating=t["impact_rating"],
                required_control_level=TargetControlLevel(t["required_control_level"]),
                required_state=t["required_state"],
            )
            for t in manifest_data["targets"]
        ),
    )

    cell_rated_low = SourceGoalCell(
        status=BatchCellStatus.COMPLETE_SUCCESS,
        control_level_attained=TargetControlLevel.ADMIN_ENTITLEMENT,
        min_effort=1.0,
        min_effort_path={"cost": 1.0, "steps": ["step1"]},
        likelihood_interval=(0.01, 0.05),
        likelihood_status="rated",
        impact="Catastrophic",
    )
    cell_unrated = SourceGoalCell(
        status=BatchCellStatus.COMPLETE_SUCCESS,
        control_level_attained=TargetControlLevel.ADMIN_ENTITLEMENT,
        min_effort=1.0,
        min_effort_path={"cost": 1.0, "steps": ["step1"]},
        likelihood_interval=None,
        likelihood_status="unrated",
        impact="Catastrophic",
    )

    matrix = {
        "src-rated-low": {"goal-synthetic-da": cell_rated_low},
        "src-unrated": {"goal-synthetic-da": cell_unrated},
    }

    ranked, ties = prioritize_sources(matrix, manifest)

    assert ranked[0].source_id == "src-rated-low"
    assert ranked[0].likelihood_to_highest_impact == (0.01, 0.05)
    assert ranked[1].source_id == "src-unrated"
    assert ranked[1].likelihood_to_highest_impact is None

    # Explanation and audit log must never invent a 0.50 scalar
    for r in ranked:
        assert "0.50" not in r.explainability
        assert "0.5" not in r.explainability

    for tie in ties:
        matched = tie.get("matched_criteria", {})
        assert "0.50" not in str(matched)


# ---------------------------------------------------------------------------
# 13. Round 2 Review Regressions: Public Rating Boundary & Checkpoint Semantics
# ---------------------------------------------------------------------------


def test_public_run_attack_query_rated_scoring_conformance():
    """Verify real public run_attack_query() output preserves rated C and P in batch cell."""
    from tests.test_public_rating_integration import rated_case

    query, graph = rated_case()
    res = run_attack_query(query, graph)

    goal = TargetGoal(
        goal_id="admin",
        category=TargetGoalCategory.TIER_0_HOST,
        target_node_id=query["aliases"]["Host"],
        target_node_kind="Computer",
        display_name="Admin Host",
        technical_consequence="admin_control_host",
        impact_rating="High",
        required_control_level=TargetControlLevel.HOST_ADMIN_EXECUTION,
        required_state={"admin_control": [query["aliases"]["Host"]]},
    )

    cell = map_query_result_to_cell(res, goal)
    assert cell.status == BatchCellStatus.COMPLETE_SUCCESS
    assert cell.min_effort == 1.0
    assert cell.min_effort_path == {
        "cost": 1.0,
        "steps": ["propagate_group_entitlement", "obtain_admin_execution_on_host"],
    }
    assert cell.likelihood_status == "rated"
    assert cell.likelihood_interval == (0.75, 0.75)


def test_public_run_attack_query_effort_only_scoring_conformance():
    """Verify real public run_attack_query() effort-only keeps C=1.0 and unrated likelihood."""
    from tests.test_public_rating_integration import rated_case, registry

    query, graph = rated_case()
    query["rating_resolution"]["registries"]["likelihood"] = registry([])
    res = run_attack_query(query, graph)

    goal = TargetGoal(
        goal_id="admin",
        category=TargetGoalCategory.TIER_0_HOST,
        target_node_id=query["aliases"]["Host"],
        target_node_kind="Computer",
        display_name="Admin Host",
        technical_consequence="admin_control_host",
        impact_rating="High",
        required_control_level=TargetControlLevel.HOST_ADMIN_EXECUTION,
        required_state={"admin_control": [query["aliases"]["Host"]]},
    )

    cell = map_query_result_to_cell(res, goal)
    assert cell.status == BatchCellStatus.COMPLETE_SUCCESS
    assert cell.min_effort == 1.0
    assert cell.min_effort_path == {
        "cost": 1.0,
        "steps": ["propagate_group_entitlement", "obtain_admin_execution_on_host"],
    }
    assert cell.likelihood_status == "unrated"
    assert cell.likelihood_interval is None


def test_public_run_attack_query_unrated_never_infers_effort_from_steps():
    """Verify real public run_attack_query() without ratings keeps C=null without step fallback."""
    from tests.test_public_rating_integration import rated_case

    query, graph = rated_case()
    query.pop("rating_resolution")
    res = run_attack_query(query, graph)

    goal = TargetGoal(
        goal_id="admin",
        category=TargetGoalCategory.TIER_0_HOST,
        target_node_id=query["aliases"]["Host"],
        target_node_kind="Computer",
        display_name="Admin Host",
        technical_consequence="admin_control_host",
        impact_rating="High",
        required_control_level=TargetControlLevel.HOST_ADMIN_EXECUTION,
        required_state={"admin_control": [query["aliases"]["Host"]]},
    )

    cell = map_query_result_to_cell(res, goal)
    assert cell.status == BatchCellStatus.COMPLETE_SUCCESS
    assert cell.min_effort is None
    assert cell.min_effort_path == {
        "cost": None,
        "steps": ["obtain_admin_execution_on_host"],
    }
    assert cell.likelihood_status == "unrated"
    assert cell.likelihood_interval is None

    # Verify downstream source prioritization keeps unrated effort and does not assign Critical
    manifest = TargetManifest(
        manifest_id="test-manifest",
        version="1.0.0",
        snapshot_id=graph.metadata["snapshot_id"],
        domain_sid="S-1-5-21-test",
        targets=(goal,),
    )
    matrix = {"src-unrated": {"admin": cell}}
    ranked, _ = prioritize_sources(matrix, manifest)
    assert ranked[0].min_effort_to_highest_impact is None
    assert ranked[0].priority_class == "High"
    assert "unrated effort" in ranked[0].explainability
    assert "C=" not in ranked[0].explainability


def test_batch_request_rating_resolution_transport_and_roundtrip():
    """Verify rating_resolution round-trips through BatchQueryRequest serializer and JSON schema."""
    from tests.test_public_rating_integration import rated_case

    query, _ = rated_case()
    rating_res = query["rating_resolution"]

    manifest_data = load_json(FIXTURES_DIR / "target_manifest_synthetic.json")
    manifest = TargetManifest.from_dict(manifest_data)

    source = BatchSourceItem(
        source_id="src-alice",
        node_id=ALICE_ID,
        node_kind="User",
        profile_kind="user_usable_identity",
    )

    req = BatchQueryRequest(
        batch_id="batch-roundtrip-test",
        snapshot_id=manifest.snapshot_id,
        sources=(source,),
        target_manifest=manifest,
        rating_resolution=rating_res,
    )

    req_dict = req.to_dict()
    assert "rating_resolution" in req_dict
    assert req_dict["rating_resolution"]["version"] == "public-rating-resolution/1.1.0"

    schema = load_json(SCHEMAS_DIR / "batch-query-request.schema.json")
    validator = Draft202012Validator(schema)
    errors = list(validator.iter_errors(req_dict))
    assert not errors, f"Schema validation errors: {errors}"

    # Round-trip deserialization
    req_restored = BatchQueryRequest.from_dict(req_dict)
    assert req_restored.rating_resolution == req.rating_resolution
    assert req_restored.to_dict() == req_dict


def test_checkpoint_only_and_unevaluated_distinct_from_proven_no_path():
    """Verify checkpoint_only and unevaluated sources are distinct from proven_no_path."""
    manifest_data = load_json(FIXTURES_DIR / "target_manifest_synthetic.json")
    manifest = TargetManifest.from_dict(manifest_data)

    class MockResult:
        def __init__(self, status, checkpoint_reached=False, final_goal_reached=False):
            self.status = status
            self.checkpoint_reached = checkpoint_reached
            self.final_goal_reached = final_goal_reached
            self.truncated = False
            self.expansions = 5
            self.diagnostics = ()

    goal_da = manifest.get_goal("goal-synthetic-da")
    goal_host = manifest.get_goal("goal-synthetic-c0-host")

    # 1. Map query result with checkpoint_only status
    res_chk = MockResult(
        status="checkpoint_only", checkpoint_reached=True, final_goal_reached=False
    )
    cell_chk = map_query_result_to_cell(res_chk, goal_da)
    assert cell_chk.status == BatchCellStatus.CHECKPOINT_ONLY
    assert cell_chk.checkpoint_reached is True
    assert cell_chk.final_goal_reached is False

    res_nopath = MockResult(status="no_path", checkpoint_reached=False, final_goal_reached=False)
    cell_nopath = map_query_result_to_cell(res_nopath, goal_host)
    assert cell_nopath.status == BatchCellStatus.NO_PATH

    res_blocked = MockResult(status="blocked", checkpoint_reached=False, final_goal_reached=False)
    cell_blocked = map_query_result_to_cell(res_blocked, goal_host)
    assert cell_blocked.status == BatchCellStatus.BLOCKED

    # Test matrix with 4 sources
    matrix = {
        # Source 1: only checkpoint_only cell
        "src-chk-only": {"goal-synthetic-da": cell_chk},
        # Source 2: empty matrix row (unevaluated)
        "src-empty": {},
        # Source 3: mixed checkpoint_only and no_path
        "src-mixed": {"goal-synthetic-da": cell_chk, "goal-synthetic-c0-host": cell_nopath},
        # Source 4: fully evaluated negative conclusion
        "src-proven-negative": {
            "goal-synthetic-da": cell_nopath,
            "goal-synthetic-c0-host": cell_blocked,
        },
    }

    ranked, _ = prioritize_sources(matrix, manifest)
    rank_by_id = {r.source_id: r for r in ranked}

    # Source 1: checkpoint_only
    assert rank_by_id["src-chk-only"].disposition == "checkpoint_only"
    assert rank_by_id["src-chk-only"].highest_impact_reached == "Unknown"
    assert rank_by_id["src-chk-only"].priority_class == "Unknown"
    assert "proven no viable attack path" not in rank_by_id["src-chk-only"].explainability
    assert "absence of path is not proven" in rank_by_id["src-chk-only"].explainability

    # Source 2: not_evaluated
    assert rank_by_id["src-empty"].disposition == "not_evaluated"
    assert rank_by_id["src-empty"].highest_impact_reached == "Unknown"
    assert rank_by_id["src-empty"].priority_class == "Unknown"
    assert "proven no viable attack path" not in rank_by_id["src-empty"].explainability

    # Source 3: mixed (cannot be proven_no_path because checkpoint was reached without final eval)
    assert rank_by_id["src-mixed"].disposition == "checkpoint_only"
    assert rank_by_id["src-mixed"].highest_impact_reached == "Unknown"
    assert rank_by_id["src-mixed"].priority_class == "Unknown"
    assert "proven no viable attack path" not in rank_by_id["src-mixed"].explainability

    # Source 4: verified absence of paths across all evaluated goals
    assert rank_by_id["src-proven-negative"].disposition == "proven_no_path"
    assert rank_by_id["src-proven-negative"].highest_impact_reached == "None"
    assert rank_by_id["src-proven-negative"].priority_class == "None"
    assert "has proven no viable attack path" in rank_by_id["src-proven-negative"].explainability


def test_public_run_attack_query_empty_registries_never_infers_effort():
    """Verify public run_attack_query() with empty registries keeps C=null without fallback."""
    from tests.test_public_rating_integration import rated_case

    query, graph = rated_case()
    query["rating_resolution"]["registries"] = {}
    res = run_attack_query(query, graph)

    goal = TargetGoal(
        goal_id="admin",
        category=TargetGoalCategory.TIER_0_HOST,
        target_node_id=query["aliases"]["Host"],
        target_node_kind="Computer",
        display_name="Admin Host",
        technical_consequence="admin_control_host",
        impact_rating="High",
        required_control_level=TargetControlLevel.HOST_ADMIN_EXECUTION,
        required_state={"admin_control": [query["aliases"]["Host"]]},
    )

    cell = map_query_result_to_cell(res, goal)
    assert cell.status == BatchCellStatus.COMPLETE_SUCCESS
    assert cell.min_effort is None
    assert cell.min_effort_path == {
        "cost": None,
        "steps": ["obtain_admin_execution_on_host"],
    }
    assert cell.likelihood_status == "unrated"
    assert cell.likelihood_interval is None

    # Verify downstream source prioritization keeps unrated effort and does not assign Critical
    manifest = TargetManifest(
        manifest_id="test-manifest",
        version="1.0.0",
        snapshot_id=graph.metadata["snapshot_id"],
        domain_sid="S-1-5-21-test",
        targets=(goal,),
    )
    matrix = {"src-empty-registries": {"admin": cell}}
    ranked, _ = prioritize_sources(matrix, manifest)
    assert ranked[0].min_effort_to_highest_impact is None
    assert ranked[0].priority_class == "High"
    assert "unrated effort" in ranked[0].explainability


def test_public_run_attack_query_missing_effort_registry_never_infers_effort():
    """Verify real public run_attack_query() with missing effort registry keeps C=null."""
    from tests.test_public_rating_integration import rated_case

    query, graph = rated_case()
    query["rating_resolution"]["registries"].pop("effort")
    res = run_attack_query(query, graph)

    goal = TargetGoal(
        goal_id="admin",
        category=TargetGoalCategory.TIER_0_HOST,
        target_node_id=query["aliases"]["Host"],
        target_node_kind="Computer",
        display_name="Admin Host",
        technical_consequence="admin_control_host",
        impact_rating="High",
        required_control_level=TargetControlLevel.HOST_ADMIN_EXECUTION,
        required_state={"admin_control": [query["aliases"]["Host"]]},
    )

    cell = map_query_result_to_cell(res, goal)
    assert cell.status == BatchCellStatus.COMPLETE_SUCCESS
    assert cell.min_effort is None
    assert cell.min_effort_path == {
        "cost": None,
        "steps": ["obtain_admin_execution_on_host"],
    }
    assert cell.likelihood_status == "unrated"
    assert cell.likelihood_interval is None


def test_parse_probability_interval_validation_and_rejection():
    """Verify _parse_probability_interval validates numeric bounds and rejects malformed inputs."""
    from scripts.research.source_goal_batch import _parse_probability_interval

    # Valid intervals
    assert _parse_probability_interval(["3/4", "3/4"]) == (0.75, 0.75)
    assert _parse_probability_interval([0.25, 0.75]) == (0.25, 0.75)
    assert _parse_probability_interval([0, 1]) == (0.0, 1.0)
    assert _parse_probability_interval(("1/3", "2/3")) == (
        pytest.approx(1 / 3),
        pytest.approx(2 / 3),
    )

    # Out of range bounds
    assert _parse_probability_interval([-0.1, 0.5]) is None
    assert _parse_probability_interval([0.2, 1.5]) is None

    # Inverted bounds (lower > upper)
    assert _parse_probability_interval([0.8, 0.2]) is None
    assert _parse_probability_interval(["3/4", "1/4"]) is None

    # Invalid non-list / non-tuple types or wrong lengths
    assert _parse_probability_interval("34") is None
    assert _parse_probability_interval({"a": 0.1, "b": 0.2}) is None
    assert _parse_probability_interval(None) is None
    assert _parse_probability_interval([]) is None
    assert _parse_probability_interval([0.5]) is None
    assert _parse_probability_interval([0.1, 0.2, 0.3]) is None

    # Malformed tokens and division by zero
    assert _parse_probability_interval(["foo", "bar"]) is None
    assert _parse_probability_interval(["1/0", "1/2"]) is None


def test_public_engine_checkpoint_mapping_and_prioritization():
    """Verify real engine execution with checkpoint_goal maps correctly to cell and dispositions."""
    from tests.test_week4_query_scenario_mapping import (
        ALIASES,
        DEFAULT_RUNTIME_FACTS,
        TWO_ROUTES_RAW,
    )

    manifest_data = load_json(FIXTURES_DIR / "target_manifest_synthetic.json")
    manifest = TargetManifest.from_dict(manifest_data)
    goal_host = manifest.get_goal("goal-synthetic-c0-host")

    # Real engine run with blocked final asset gate
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
    res_blocked = run_attack_query(query_blocked_asset, graph=TWO_ROUTES_RAW)
    assert res_blocked.checkpoint_reached is True
    assert res_blocked.final_goal_reached is False
    assert res_blocked.status == "checkpoint_reached_final_goal_blocked"

    cell_blocked = map_query_result_to_cell(res_blocked, goal_host)
    assert cell_blocked.status == BatchCellStatus.CHECKPOINT_REACHED_FINAL_GOAL_BLOCKED
    assert cell_blocked.checkpoint_reached is True
    assert cell_blocked.final_goal_reached is False

    # Real engine run with missing asset gate (indeterminate)
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
    res_missing = run_attack_query(query_missing_asset, graph=TWO_ROUTES_RAW)
    assert res_missing.checkpoint_reached is True
    assert res_missing.final_goal_reached is False
    assert res_missing.status == "checkpoint_reached_final_goal_indeterminate"

    cell_missing = map_query_result_to_cell(res_missing, goal_host)
    assert cell_missing.status == BatchCellStatus.CHECKPOINT_REACHED_FINAL_GOAL_INDETERMINATE

    # Synthetic negative cell for DA
    cell_nopath = SourceGoalCell(
        status=BatchCellStatus.NO_PATH,
        control_level_attained=TargetControlLevel.NONE,
    )
    cell_chk_only = SourceGoalCell(
        status=BatchCellStatus.CHECKPOINT_ONLY,
        control_level_attained=TargetControlLevel.NONE,
        checkpoint_reached=True,
        final_goal_reached=False,
    )

    # Prioritization matrix testing the boundary
    matrix = {
        # Source 1: proven negative across all goals (checkpoint reached then blocked + no path)
        "src-proven-neg": {
            "goal-synthetic-c0-host": cell_blocked,
            "goal-synthetic-da": cell_nopath,
        },
        # Source 2: checkpoint reached but final goal indeterminate (cannot be proven_no_path)
        "src-indet": {
            "goal-synthetic-c0-host": cell_missing,
            "goal-synthetic-da": cell_nopath,
        },
        # Source 3: checkpoint-only cell
        "src-chk-only": {"goal-synthetic-da": cell_chk_only},
        # Source 4: empty matrix row
        "src-empty": {},
    }
    ranked, _ = prioritize_sources(matrix, manifest)
    rank_by_id = {r.source_id: r for r in ranked}

    # Proven negative -> proven_no_path, None impact, None priority
    assert rank_by_id["src-proven-neg"].disposition == "proven_no_path"
    assert rank_by_id["src-proven-neg"].highest_impact_reached == "None"
    assert rank_by_id["src-proven-neg"].priority_class == "None"
    assert "has proven no viable attack path" in rank_by_id["src-proven-neg"].explainability

    # Indeterminate -> indeterminate, Unknown impact, Unknown priority
    assert rank_by_id["src-indet"].disposition == "indeterminate"
    assert rank_by_id["src-indet"].highest_impact_reached == "Unknown"
    assert rank_by_id["src-indet"].priority_class == "Unknown"
    assert "potential risk cannot be ruled out as no-path" in rank_by_id["src-indet"].explainability

    # Checkpoint only -> checkpoint_only, Unknown impact, Unknown priority
    assert rank_by_id["src-chk-only"].disposition == "checkpoint_only"
    assert rank_by_id["src-chk-only"].highest_impact_reached == "Unknown"
    assert rank_by_id["src-chk-only"].priority_class == "Unknown"
    assert "absence of path is not proven" in rank_by_id["src-chk-only"].explainability

    # Empty matrix -> not_evaluated, Unknown impact, Unknown priority
    assert rank_by_id["src-empty"].disposition == "not_evaluated"
    assert rank_by_id["src-empty"].highest_impact_reached == "Unknown"
    assert rank_by_id["src-empty"].priority_class == "Unknown"
    assert (
        "has not been evaluated against any target goals" in rank_by_id["src-empty"].explainability
    )


def test_public_engine_password_missing_context_indeterminate_not_proven_no_path():
    """Verify leaked password without context yields indeterminate, never proven_no_path."""
    graph = EngineGraph.from_canonical(GRAPH_TWO_ROUTES_PATH.read_text())

    # 1. At profile boundary, missing context is unsupported with MISSING_AUTHENTICATION_CONTEXT
    profile_missing = create_foothold_profile(
        node_id=BOB_ID,
        node_kind="User",
        profile_type=FootholdProfileKind.USER_LEAKED_PASSWORD,
        authentication_context=None,
    )
    assert profile_missing.is_supported is False
    assert profile_missing.error_code == "MISSING_AUTHENTICATION_CONTEXT"
    assert profile_missing.authentication_context is None

    # 2. When valid Computer context is passed without runtime facts, it yields indeterminate
    password_artifact = CredentialArtifact(
        owner=BOB_ID,
        context=HOST_C0_ID,
        form="password",
        provenance=("test",),
    )
    initial_state = AttackState(
        known_identity=frozenset({BOB_ID}),
        recovered_secret=frozenset({password_artifact}),
    )
    q = AttackQuery(
        target=ADMINS_ID,
        source_foothold=BOB_ID,
        initial_actor=BOB_ID,
        initial_state=initial_state,
        authentication_context=HOST_C0_ID,
        target_goal={
            "target": ADMINS_ID,
            "required_state": {"usable_identity": [[BOB_ID, ADMINS_ID]]},
        },
    )
    res = run_attack_query(q, graph)
    assert res.status == "indeterminate"
    assert res.is_no_path_proven_over_scope is False

    goal = TargetGoal(
        goal_id="goal-da",
        category=TargetGoalCategory.TIER_0_IDENTITY,
        target_node_id=ADMINS_ID,
        target_node_kind="Group",
        display_name="Domain Admins",
        technical_consequence="DA compromise",
        impact_rating="Catastrophic",
        required_control_level=TargetControlLevel.ADMIN_ENTITLEMENT,
        required_state={"usable_identity": [[BOB_ID, ADMINS_ID]]},
    )
    cell = map_query_result_to_cell(res, goal)
    assert cell.status == BatchCellStatus.INDETERMINATE
    assert cell.status != BatchCellStatus.NO_PATH
    assert cell.status != BatchCellStatus.BLOCKED

    # 3. End-to-end prioritization: missing context source evaluated against goals yields
    # disposition='unsupported' with MISSING_AUTHENTICATION_CONTEXT, NEVER proven_no_path.
    manifest = TargetManifest(
        manifest_id="manifest-missing-ctx-test",
        version="1.0.0",
        snapshot_id="snap-test",
        domain_sid="DOMAIN-SID",
        targets=(goal,),
    )
    cell_unsupported = SourceGoalCell(
        status=BatchCellStatus.UNSUPPORTED_SOURCE,
        control_level_attained=TargetControlLevel.NONE,
        diagnostics=(
            {
                "error_code": profile_missing.error_code,
                "message": profile_missing.unsupported_reason,
            },
        ),
    )
    ranked, _ = prioritize_sources(
        {"src-bob-missing": {"goal-da": cell_unsupported}},
        manifest,
    )
    assert len(ranked) == 1
    assert ranked[0].disposition == "unsupported"
    assert ranked[0].disposition != "proven_no_path"
    assert ranked[0].highest_impact_reached == "None"
    assert ranked[0].priority_class == "None"
    assert "MISSING_AUTHENTICATION_CONTEXT" in ranked[0].explainability


def test_public_engine_password_wrong_kind_context_discards_activation():
    """Verify public engine behavior with wrong-kind context vs input boundary rejection."""
    graph = EngineGraph.from_canonical(GRAPH_TWO_ROUTES_PATH.read_text())

    # 1. Under raw public engine semantics, passing a User SID context causes credential producer
    # to discard activation candidates because catalog mandates target_kinds == {"Computer"}.
    password_artifact = CredentialArtifact(
        owner=BOB_ID,
        context=BOB_ID,  # User SID context
        form="password",
        provenance=("test",),
    )
    initial_state = AttackState(
        known_identity=frozenset({BOB_ID}),
        recovered_secret=frozenset({password_artifact}),
    )
    q = AttackQuery(
        target=ADMINS_ID,
        source_foothold=BOB_ID,
        initial_actor=BOB_ID,
        initial_state=initial_state,
        authentication_context=BOB_ID,
        target_goal={
            "target": ADMINS_ID,
            "required_state": {"usable_identity": [[BOB_ID, ADMINS_ID]]},
        },
    )
    res = run_attack_query(q, graph)
    # The search queue empties without expanding activation, returning no_path / proven_no_path.
    assert res.status in ("no_path", "blocked")
    assert res.is_no_path_proven_over_scope is True

    # 2. Under the batch contract boundary, such invalid configurations are caught and rejected
    # BEFORE invoking search, preventing false negative proven_no_path conclusions.
    profile = create_foothold_profile(
        node_id=BOB_ID,
        node_kind="User",
        profile_type=FootholdProfileKind.USER_LEAKED_PASSWORD,
        authentication_context=BOB_ID,
        graph=graph,
    )
    assert profile.is_supported is False
    assert profile.error_code == "INVALID_AUTHENTICATION_CONTEXT"
    assert "cannot be a User principal" in (profile.unsupported_reason or "")


def test_public_engine_password_valid_computer_context_activates():
    """Verify that with valid Computer context and assumptions, leaked password activates."""
    graph = EngineGraph.from_canonical(GRAPH_TWO_ROUTES_PATH.read_text())
    profile = create_foothold_profile(
        node_id=ALICE_ID,
        node_kind="User",
        profile_type=FootholdProfileKind.USER_LEAKED_PASSWORD,
        authentication_context=HOST_C0_ID,
        assumptions=[
            make_assumption("actor_enabled", ALICE_ID, HOST_C0_ID),
            make_assumption("secret_valid", ALICE_ID, HOST_C0_ID),
            make_assumption("network_kdc_reachable", ALICE_ID, HOST_C0_ID),
            make_assumption("authentication_accepted", ALICE_ID, HOST_C0_ID),
            make_assumption("admin_channel", ALICE_ID, HOST_C0_ID),
        ],
    )
    assert profile.is_supported is True
    assert profile.authentication_context == HOST_C0_ID

    goal = TargetGoal(
        goal_id="goal-host-admin",
        category=TargetGoalCategory.TIER_0_HOST,
        target_node_id=HOST_C0_ID,
        target_node_kind="Computer",
        display_name="C0 Host Administrator",
        technical_consequence="Host compromise",
        impact_rating="High",
        required_control_level=TargetControlLevel.HOST_ADMIN_EXECUTION,
        required_state={"admin_control": [HOST_C0_ID]},
    )
    q = AttackQuery(
        target=HOST_C0_ID,
        source_foothold=profile.node_id,
        initial_actor=profile.initial_actor,
        initial_state=profile.initial_attack_state,
        authentication_context=profile.authentication_context,
        target_goal={"target": HOST_C0_ID, "required_state": goal.required_state},
        assumptions=profile.declared_assumptions,
        aliases={"__RESOLVED_ACTOR__": profile.initial_actor},
    )
    res = run_attack_query(q, graph)
    assert res.status == "success"
    assert res.final_goal_reached is True
    techniques = [
        s.result.request.technique_id for path in res.paths for s in path.transition_history
    ]
    assert "activate_recovered_identity" in techniques
    assert "obtain_admin_execution_on_host" in techniques

    cell = map_query_result_to_cell(res, goal)
    assert cell.status == BatchCellStatus.COMPLETE_SUCCESS
    assert cell.final_goal_reached is True
    assert cell.control_level_attained == TargetControlLevel.HOST_ADMIN_EXECUTION


def test_foothold_profile_password_context_validation_rejections():
    """Verify input boundary validation catches all invalid authentication_context variants."""
    graph = EngineGraph.from_canonical(GRAPH_TWO_ROUTES_PATH.read_text())

    # Case 1: Missing / None
    p_none = create_foothold_profile(
        node_id=BOB_ID,
        node_kind="User",
        profile_type=FootholdProfileKind.USER_LEAKED_PASSWORD,
        authentication_context=None,
    )
    assert p_none.is_supported is False
    assert p_none.error_code == "MISSING_AUTHENTICATION_CONTEXT"
    assert p_none.authentication_context is None

    # Case 2: Empty string or whitespace
    p_empty = create_foothold_profile(
        node_id=BOB_ID,
        node_kind="User",
        profile_type=FootholdProfileKind.USER_LEAKED_PASSWORD,
        authentication_context="   ",
    )
    assert p_empty.is_supported is False
    assert p_empty.error_code == "MISSING_AUTHENTICATION_CONTEXT"

    # Case 3: Same as node_id (User principal)
    p_user_same = create_foothold_profile(
        node_id=BOB_ID,
        node_kind="User",
        profile_type=FootholdProfileKind.USER_LEAKED_PASSWORD,
        authentication_context=BOB_ID,
    )
    assert p_user_same.is_supported is False
    assert p_user_same.error_code == "INVALID_AUTHENTICATION_CONTEXT"

    # Case 4: Explicit authentication_context_kind != "Computer"
    p_kind_mismatch = create_foothold_profile(
        node_id=BOB_ID,
        node_kind="User",
        profile_type=FootholdProfileKind.USER_LEAKED_PASSWORD,
        authentication_context=ALICE_ID,
        authentication_context_kind="User",
    )
    assert p_kind_mismatch.is_supported is False
    assert p_kind_mismatch.error_code == "INVALID_AUTHENTICATION_CONTEXT"

    # Case 5: Context node in graph is a Group
    p_graph_group = create_foothold_profile(
        node_id=BOB_ID,
        node_kind="User",
        profile_type=FootholdProfileKind.USER_LEAKED_PASSWORD,
        authentication_context=ADMINS_ID,
        graph=graph,
    )
    assert p_graph_group.is_supported is False
    assert p_graph_group.error_code == "INVALID_AUTHENTICATION_CONTEXT"

    # Case 6: Valid Computer context in graph
    p_valid = create_foothold_profile(
        node_id=BOB_ID,
        node_kind="User",
        profile_type=FootholdProfileKind.USER_LEAKED_PASSWORD,
        authentication_context=HOST_C0_ID,
        graph=graph,
    )
    assert p_valid.is_supported is True
    assert p_valid.error_code is None
    assert p_valid.authentication_context == HOST_C0_ID

    # Case 7: BatchSourceItem.to_foothold_profile() helper delegates correctly
    src_item = BatchSourceItem(
        source_id="src-test-bob",
        node_id=BOB_ID,
        node_kind="User",
        profile_kind="user_leaked_password",
        authentication_context=HOST_C0_ID,
    )
    p_from_src = src_item.to_foothold_profile(graph=graph)
    assert p_from_src.is_supported is True
    assert p_from_src.authentication_context == HOST_C0_ID

    src_item_bad = BatchSourceItem(
        source_id="src-test-bob-bad",
        node_id=BOB_ID,
        node_kind="User",
        profile_kind="user_leaked_password",
        authentication_context=BOB_ID,
    )
    p_from_bad = src_item_bad.to_foothold_profile(graph=graph)
    assert p_from_bad.is_supported is False
    assert p_from_bad.error_code == "INVALID_AUTHENTICATION_CONTEXT"

    # Case 8: Non-existent context host in EngineGraph (must not raise KeyError)
    p_nonexistent_host = create_foothold_profile(
        node_id=BOB_ID,
        node_kind="User",
        profile_type=FootholdProfileKind.USER_LEAKED_PASSWORD,
        authentication_context="NON_EXISTENT_HOST_ID",
        graph=graph,
    )
    assert p_nonexistent_host.is_supported is False
    assert p_nonexistent_host.error_code == "INVALID_AUTHENTICATION_CONTEXT"

    # Case 9: Non-existent context host in Mapping graph
    dict_graph = {"nodes": [{"id": BOB_ID, "kind": "User"}, {"id": HOST_C0_ID, "kind": "Computer"}]}
    p_dict_nonexistent = create_foothold_profile(
        node_id=BOB_ID,
        node_kind="User",
        profile_type=FootholdProfileKind.USER_LEAKED_PASSWORD,
        authentication_context="NON_EXISTENT_HOST_ID",
        graph=dict_graph,
    )
    assert p_dict_nonexistent.is_supported is False
    assert p_dict_nonexistent.error_code == "INVALID_AUTHENTICATION_CONTEXT"

    # Case 10: Explicit FootholdProfileKind.UNSUPPORTED on User and Computer kinds
    p_unsupported_user = create_foothold_profile(
        node_id=BOB_ID,
        node_kind="User",
        profile_type=FootholdProfileKind.UNSUPPORTED,
    )
    assert p_unsupported_user.is_supported is False
    assert p_unsupported_user.error_code == "UNSUPPORTED_FOOTHOLD_KIND"

    p_unsupported_comp = create_foothold_profile(
        node_id=HOST_C0_ID,
        node_kind="Computer",
        profile_type=FootholdProfileKind.UNSUPPORTED,
    )
    assert p_unsupported_comp.is_supported is False
    assert p_unsupported_comp.error_code == "UNSUPPORTED_FOOTHOLD_KIND"


def test_prioritize_sources_diagnostics_order_independence():
    """Verify diagnostics aggregation in entry is deterministic regardless of goal order."""
    manifest = TargetManifest(
        manifest_id="manifest-diag-test",
        version="1.0.0",
        snapshot_id="snap-test",
        domain_sid="DOMAIN-SID",
        targets=(
            TargetGoal(
                goal_id="goal-alpha",
                category=TargetGoalCategory.TIER_0_IDENTITY,
                target_node_id=ADMINS_ID,
                target_node_kind="Group",
                display_name="Alpha Goal",
                technical_consequence="Impact A",
                impact_rating="High",
                required_control_level=TargetControlLevel.ADMIN_ENTITLEMENT,
                required_state={"usable_identity": [[BOB_ID, ADMINS_ID]]},
            ),
            TargetGoal(
                goal_id="goal-beta",
                category=TargetGoalCategory.TIER_0_HOST,
                target_node_id=HOST_C0_ID,
                target_node_kind="Computer",
                display_name="Beta Goal",
                technical_consequence="Impact B",
                impact_rating="High",
                required_control_level=TargetControlLevel.HOST_ADMIN_EXECUTION,
                required_state={"admin_control": [HOST_C0_ID]},
            ),
        ),
    )

    cell_alpha = SourceGoalCell(
        status=BatchCellStatus.NO_PATH,
        control_level_attained=TargetControlLevel.NONE,
        diagnostics=(
            {
                "predicate": "secret_valid",
                "subject": BOB_ID,
                "target": HOST_C0_ID,
                "action": "test_z",
            },
            {
                "predicate": "actor_enabled",
                "subject": BOB_ID,
                "target": HOST_C0_ID,
                "action": "test_a",
            },
        ),
    )
    cell_beta = SourceGoalCell(
        status=BatchCellStatus.NO_PATH,
        control_level_attained=TargetControlLevel.NONE,
        diagnostics=(
            {
                "predicate": "network_kdc_reachable",
                "subject": BOB_ID,
                "target": HOST_C0_ID,
                "action": "test_m",
            },
            {
                "predicate": "actor_enabled",
                "subject": BOB_ID,
                "target": HOST_C0_ID,
                "action": "test_a",
            },
        ),
    )

    # Matrix order 1: alpha then beta
    matrix_1 = {"src-1": {"goal-alpha": cell_alpha, "goal-beta": cell_beta}}
    # Matrix order 2: beta then alpha
    matrix_2 = {"src-1": {"goal-beta": cell_beta, "goal-alpha": cell_alpha}}

    ranked_1, _ = prioritize_sources(matrix_1, manifest)
    ranked_2, _ = prioritize_sources(matrix_2, manifest)

    # Diagnostics must be identically deduplicated and sorted
    assert ranked_1[0].diagnostics == ranked_2[0].diagnostics
    assert len(ranked_1[0].diagnostics) == 3
    # Verify deterministic ordering: test_a, test_m, test_z
    actions = [d["action"] for d in ranked_1[0].diagnostics]
    assert actions == ["test_a", "test_m", "test_z"]
    assert ranked_1[0].to_dict() == ranked_2[0].to_dict()

    # Also test all_unsupported explainability error code extraction
    cell_unsupported = SourceGoalCell(
        status=BatchCellStatus.UNSUPPORTED_SOURCE,
        control_level_attained=TargetControlLevel.NONE,
        diagnostics=(
            {
                "error_code": "MISSING_AUTHENTICATION_CONTEXT",
                "message": "Missing context",
            },
        ),
    )
    matrix_unsupported = {"src-unsupported": {"goal-alpha": cell_unsupported}}
    ranked_unsupported, _ = prioritize_sources(matrix_unsupported, manifest)
    assert ranked_unsupported[0].disposition == "unsupported"
    assert "MISSING_AUTHENTICATION_CONTEXT" in ranked_unsupported[0].explainability


def test_concurrent_worker_diagnostics_determinism():
    """Verify bit-for-bit identical diagnostics serialization across 30 parallel workers."""
    import concurrent.futures
    import random

    manifest = TargetManifest(
        manifest_id="manifest-concurrency-test",
        version="1.0.0",
        snapshot_id="snap-test",
        domain_sid="DOMAIN-SID",
        targets=tuple(
            TargetGoal(
                goal_id=f"goal-{i}",
                category=TargetGoalCategory.TIER_0_IDENTITY,
                target_node_id=ADMINS_ID,
                target_node_kind="Group",
                display_name=f"Goal {i}",
                technical_consequence="Impact",
                impact_rating="High",
                required_control_level=TargetControlLevel.ADMIN_ENTITLEMENT,
                required_state={"usable_identity": [[BOB_ID, ADMINS_ID]]},
            )
            for i in range(5)
        ),
    )

    base_cells = {
        f"goal-{i}": SourceGoalCell(
            status=BatchCellStatus.NO_PATH,
            control_level_attained=TargetControlLevel.NONE,
            diagnostics=(
                {"code": f"CODE_{i}", "tags": {"tag_b", "tag_a"}, "detail": f"info_{i}"},
                {"code": "COMMON", "action": "check"},
            ),
        )
        for i in range(5)
    }

    def worker_run(worker_idx: int) -> dict[str, Any]:
        # Shuffle goal dictionary insertion order
        goal_keys = list(base_cells.keys())
        rng = random.Random(worker_idx)
        rng.shuffle(goal_keys)
        shuffled_matrix = {"src-bob": {k: base_cells[k] for k in goal_keys}}
        ranked, _ = prioritize_sources(shuffled_matrix, manifest)
        return ranked[0].to_dict()

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(worker_run, i) for i in range(30)]
        results = [f.result() for f in futures]

    first_result = results[0]
    for r in results[1:]:
        assert r == first_result
        assert r["diagnostics"] == first_result["diagnostics"]
