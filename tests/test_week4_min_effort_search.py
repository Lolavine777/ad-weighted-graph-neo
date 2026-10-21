"""Conformance tests for Week 4 stateful Min-Effort search, checkpoint,
and asset semantics (Issue #212).

Acceptance Criteria:
- Query operates declaratively without supplied ordered path.
- Stateful candidate generation preserves branch-local AttackState, actor switching,
  and graph immutability.
- DA checkpoint and final asset goal are reported separately with proper diagnostics.
- Min-Effort correctly resolves according to accepted work-unit/cost bindings (#207).
- Counter-structural Min-Effort: fewer hops with higher effort loses to longer path
  with lower effort.
- Reused work units are deduplicated within candidate programs without falsely merging
  different contexts.
- Ties and alternative ordering are deterministic across multiple runs.
- Completeness and truncation bounds: truncated search cannot claim global minimum or no-path.
- Missing effort basis remains unrated and prevents claiming scope-wide minimum.
"""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from src.engine import AttackQuery, run_attack_query

ROOT = Path(__file__).resolve().parents[1]
RATINGS_DIR = ROOT / "docs" / "research" / "ratings" / "week4"
FIXTURES_DIR = ROOT / "tests" / "fixtures" / "attack_scenarios"

# Canonical Node IDs from two-routes fixture
ALICE_ID = "S-1-5-21-1000-2000-3000-1101"
ADMINS_ID = "S-1-5-21-1000-2000-3000-2103"
HOST_C0_ID = "10000000-0000-4000-8000-000000000002"
OTHERHOST_X_ID = "10000000-0000-4000-8000-000000000003"

ALIASES = {
    "Alice": ALICE_ID,
    "Admins": ADMINS_ID,
    "Host": HOST_C0_ID,
    "OtherHost": OTHERHOST_X_ID,
}

DEFAULT_RUNTIME_FACTS = [
    {
        "predicate": "admin_channel",
        "subject": "Alice",
        "target": "Host",
        "value": True,
        "origin": "declared_assumption",
        "scope": "two-routes:fixed-snapshot-window",
        "rationale": "Synthetic channel assumption",
        "evidence_ref": "bh-admin",
    },
    {
        "predicate": "authentication_accepted",
        "subject": "Alice",
        "target": "Host",
        "value": True,
        "origin": "declared_assumption",
        "scope": "two-routes:fixed-snapshot-window",
        "rationale": "Synthetic auth assumption",
        "evidence_ref": "bh-admin",
    },
    {
        "predicate": "security_group",
        "subject": "Alice",
        "target": "Admins",
        "value": True,
        "origin": "declared_assumption",
        "scope": "two-routes:fixed-snapshot-window",
        "rationale": "Synthetic security group assumption",
        "evidence_ref": "bh-admin",
    },
    {
        "predicate": "membership_usable",
        "subject": "Alice",
        "target": "Admins",
        "value": True,
        "origin": "declared_assumption",
        "scope": "two-routes:fixed-snapshot-window",
        "rationale": "Synthetic membership usable assumption",
        "evidence_ref": "bh-admin",
    },
]

DEFAULT_ACTION_BINDINGS = {
    ("obtain_admin_execution_on_host", "Alice", "Alice", "Host"): "action_direct_admin",
    ("propagate_group_entitlement", "Alice", "Alice", "Admins"): "action_member_admins",
    ("obtain_admin_execution_on_host", "Alice", "Admins", "Host"): "action_inherited_admin",
}


@pytest.fixture
def two_routes_graph() -> dict[str, Any]:
    graph_path = FIXTURES_DIR / "graphs" / "two-routes.json"
    return json.loads(graph_path.read_text(encoding="utf-8"))


@pytest.fixture
def ledger_e_package() -> dict[str, Any]:
    pkg_path = RATINGS_DIR / "synthetic-a2-e.json"
    return json.loads(pkg_path.read_text(encoding="utf-8"))


@pytest.fixture
def ledger_t_package() -> dict[str, Any]:
    pkg_path = RATINGS_DIR / "synthetic-a2-t.json"
    return json.loads(pkg_path.read_text(encoding="utf-8"))


def test_min_effort_counter_structural_ledger_e(two_routes_graph, ledger_e_package):
    """Counter-structural Min-Effort: fewer hops (1 hop D, effort 5) loses to

    longer path (2 hops M/I, effort 2) under accepted Ledger E bindings (#207).
    """
    query = AttackQuery(
        initial_actor="Alice",
        initial_state={"control": ["Alice"]},
        target="Host",
        target_goal={"target": "Host", "required_state": {"admin_control": ["Host"]}},
        aliases=ALIASES,
        runtime_facts=DEFAULT_RUNTIME_FACTS,
        allowed_techniques=["propagate_group_entitlement", "obtain_admin_execution_on_host"],
        budget={"max_paths": 1000, "max_steps": 12, "max_expansions": 100000},
        action_bindings=DEFAULT_ACTION_BINDINGS,
        ranking_query=ledger_e_package["query"],
    )

    result = run_attack_query(query, two_routes_graph)

    # 1. Stateful generation: 3 paths automatically generated without ordered input
    assert len(result.paths) == 3
    assert result.status == "success"
    assert result.final_goal_reached is True

    # 2. Min-Effort resolution matches independent oracle:
    # M/I (2 steps: Alice -> Admins -> Host) has effort 2
    # D (1 step: Alice -> Host) has effort 5
    # M/D (2 steps: Alice -> Admins -> Host) has effort 5
    assert result.min_effort is not None
    assert result.min_effort["best_candidate_id"] == "generated_0003"
    assert result.min_effort["minimum_effort_value"] == 2

    # 3. Best path points to the lower-effort, longer program
    assert result.best_path is not None
    assert result.best_path.cost == 2.0
    assert result.best_path.nodes == (ALICE_ID, ADMINS_ID, HOST_C0_ID)
    assert len(result.best_path.transition_history) == 2

    # 4. Completeness and optimization scope
    assert result.search_result.complete is True
    assert result.optimization_scope == "exhaustive_within_scope"
    assert result.is_minimum_proven_over_scope is True


def test_min_effort_ties_and_deterministic_ordering_ledger_t(two_routes_graph, ledger_t_package):
    """Under Ledger T, all three candidate programs achieve effort 2 (3-way tie).

    Evaluation must report all ties and select deterministically across runs.
    """
    query = AttackQuery(
        initial_actor="Alice",
        initial_state={"control": ["Alice"]},
        target="Host",
        target_goal={"target": "Host", "required_state": {"admin_control": ["Host"]}},
        aliases=ALIASES,
        runtime_facts=DEFAULT_RUNTIME_FACTS,
        allowed_techniques=["propagate_group_entitlement", "obtain_admin_execution_on_host"],
        budget={"max_paths": 1000, "max_steps": 12, "max_expansions": 100000},
        action_bindings=DEFAULT_ACTION_BINDINGS,
        ranking_query=ledger_t_package["query"],
    )

    # Run 1
    res1 = run_attack_query(query, two_routes_graph)
    # Run 2
    res2 = run_attack_query(query, two_routes_graph)

    # 3-way tie: all candidate programs achieve effort 2
    assert res1.min_effort["minimum_effort_value"] == 2
    assert len(res1.all_best_paths) == 3
    assert len(res2.all_best_paths) == 3

    # Tie-breaking is deterministic across runs
    assert res1.min_effort["best_candidate_id"] == res2.min_effort["best_candidate_id"]
    assert res1.best_path.nodes == res2.best_path.nodes
    assert res1.optimization_scope == "exhaustive_within_scope"
    assert res1.is_minimum_proven_over_scope is True


def test_initial_capabilities_drive_different_reachable_paths(two_routes_graph):
    """Same graph, different initial capabilities -> different reachable paths.

    Host control does NOT automatically grant usable domain identity.
    """
    # Baseline: control={Alice} -> 3 reachable paths (D, M/D, M/I)
    q_base = AttackQuery(
        initial_actor="Alice",
        initial_state={"control": ["Alice"]},
        target="Host",
        target_goal={"target": "Host", "required_state": {"admin_control": ["Host"]}},
        aliases=ALIASES,
        runtime_facts=DEFAULT_RUNTIME_FACTS,
    )
    res_base = run_attack_query(q_base, two_routes_graph)
    assert len(res_base.paths) == 3

    # Case 2: Initial entitlement effective_member(Alice, Admins)
    # -> 4 reachable paths (D, I, M/D, M/I)
    q_member = AttackQuery(
        initial_actor="Alice",
        initial_state={
            "control": ["Alice"],
            "effective_member": [["Alice", "Admins"]],
        },
        target="Host",
        target_goal={"target": "Host", "required_state": {"admin_control": ["Host"]}},
        aliases=ALIASES,
        runtime_facts=DEFAULT_RUNTIME_FACTS,
    )
    res_member = run_attack_query(q_member, two_routes_graph)
    assert len(res_member.paths) == 4

    # Case 3: Host control only (OtherHost) without Alice control/identity
    # Cannot deduce domain identity from host control -> complete no-path
    q_host_only = AttackQuery(
        initial_actor="Alice",
        initial_state={"admin_control": ["OtherHost"]},
        target="Host",
        target_goal={"target": "Host", "required_state": {"admin_control": ["Host"]}},
        aliases=ALIASES,
        runtime_facts=DEFAULT_RUNTIME_FACTS,
    )
    res_host_only = run_attack_query(q_host_only, two_routes_graph)
    assert len(res_host_only.paths) == 0
    assert res_host_only.status == "blocked"
    assert res_host_only.is_no_path_proven_over_scope is True


def test_checkpoint_reached_vs_final_asset_gate_blocked(two_routes_graph):
    """DA checkpoint reached but final asset gate blocked:

    Reports checkpoint_reached=True, final_goal_reached=False,
    status='checkpoint_reached_final_goal_blocked', and proper diagnostics.
    """
    facts_blocked_host = [
        {
            "predicate": "admin_channel",
            "subject": "Alice",
            "target": "Host",
            "value": False,  # BLOCKED gate
            "origin": "blocked_evidence",
            "scope": "two-routes:fixed-snapshot-window",
            "evidence_ref": "bh-admin",
        },
        {
            "predicate": "security_group",
            "subject": "Alice",
            "target": "Admins",
            "value": True,
            "origin": "declared_assumption",
            "scope": "two-routes:fixed-snapshot-window",
            "rationale": "Synthetic sec group",
            "evidence_ref": "bh-admin",
        },
        {
            "predicate": "membership_usable",
            "subject": "Alice",
            "target": "Admins",
            "value": True,
            "origin": "declared_assumption",
            "scope": "two-routes:fixed-snapshot-window",
            "rationale": "Synthetic membership",
            "evidence_ref": "bh-admin",
        },
    ]

    query = AttackQuery(
        initial_actor="Alice",
        initial_state={"control": ["Alice"]},
        target="Host",
        target_goal={"target": "Host", "required_state": {"admin_control": ["Host"]}},
        checkpoint_goal={
            "target": "Admins",
            "required_state": {"effective_member": [["Alice", "Admins"]]},
        },
        aliases=ALIASES,
        runtime_facts=facts_blocked_host,
    )

    result = run_attack_query(query, two_routes_graph)

    assert result.checkpoint_reached is True
    assert result.final_goal_reached is False
    assert result.status == "checkpoint_reached_final_goal_blocked"
    assert len(result.checkpoint_diagnostics) > 0
    assert any("admin_channel" in d.get("failed", []) for d in result.checkpoint_diagnostics)
    assert result.is_no_path_proven_over_scope is True


def test_checkpoint_reached_vs_final_asset_gate_indeterminate(two_routes_graph):
    """DA checkpoint reached but final asset gate missing (unknown):

    Reports checkpoint_reached=True, final_goal_reached=False,
    status='checkpoint_reached_final_goal_indeterminate',
    and does NOT claim scope-wide no-path.
    """
    facts_missing_host = [
        # admin_channel to Host is omitted (missing evidence -> indeterminate)
        {
            "predicate": "security_group",
            "subject": "Alice",
            "target": "Admins",
            "value": True,
            "origin": "declared_assumption",
            "scope": "two-routes:fixed-snapshot-window",
            "rationale": "Synthetic sec group",
            "evidence_ref": "bh-admin",
        },
        {
            "predicate": "membership_usable",
            "subject": "Alice",
            "target": "Admins",
            "value": True,
            "origin": "declared_assumption",
            "scope": "two-routes:fixed-snapshot-window",
            "rationale": "Synthetic membership",
            "evidence_ref": "bh-admin",
        },
    ]

    query = AttackQuery(
        initial_actor="Alice",
        initial_state={"control": ["Alice"]},
        target="Host",
        target_goal={"target": "Host", "required_state": {"admin_control": ["Host"]}},
        checkpoint_goal={
            "target": "Admins",
            "required_state": {"effective_member": [["Alice", "Admins"]]},
        },
        aliases=ALIASES,
        runtime_facts=facts_missing_host,
    )

    result = run_attack_query(query, two_routes_graph)

    assert result.checkpoint_reached is True
    assert result.final_goal_reached is False
    assert result.status == "checkpoint_reached_final_goal_indeterminate"
    assert len(result.checkpoint_diagnostics) > 0
    # Conservative lattice: unknown gate cannot prove no-path
    assert result.is_no_path_proven_over_scope is False


def test_checkpoint_reached_and_final_asset_success(two_routes_graph):
    """DA checkpoint reached AND final asset goal reached:

    Both checkpoint_reached and final_goal_reached are True, status is success.
    """
    query = AttackQuery(
        initial_actor="Alice",
        initial_state={"control": ["Alice"]},
        target="Host",
        target_goal={"target": "Host", "required_state": {"admin_control": ["Host"]}},
        checkpoint_goal={
            "target": "Admins",
            "required_state": {"effective_member": [["Alice", "Admins"]]},
        },
        aliases=ALIASES,
        runtime_facts=DEFAULT_RUNTIME_FACTS,
    )

    result = run_attack_query(query, two_routes_graph)

    assert result.checkpoint_reached is True
    assert result.final_goal_reached is True
    assert result.status == "success"
    assert len(result.paths) == 3


def test_complete_finite_scope_no_path_w4_other_target(two_routes_graph):
    """On two-routes graph, query targeting OtherHost has no paths.

    Complete finite scope exhaustive search claims no-path with proof.
    """
    query = AttackQuery(
        initial_actor="Alice",
        initial_state={"control": ["Alice"]},
        target="OtherHost",
        target_goal={"target": "OtherHost", "required_state": {"admin_control": ["OtherHost"]}},
        aliases=ALIASES,
        runtime_facts=DEFAULT_RUNTIME_FACTS,
        budget={"max_paths": 1000, "max_steps": 12, "max_expansions": 100000},
    )

    result = run_attack_query(query, two_routes_graph)

    assert len(result.paths) == 0
    assert result.status == "no_path"
    assert result.search_result.complete is True
    assert result.search_result.truncated is False
    assert result.is_no_path_proven_over_scope is True
    assert result.optimization_scope == "exhaustive_within_scope"


@pytest.mark.parametrize(
    "cap_field,reason",
    [
        ("max_paths", "path_limit_reached"),
        ("max_expansions", "expansion_limit_reached"),
        ("max_steps", "step_limit_reached"),
    ],
)
def test_truncation_limits_and_bounds_on_claims(
    two_routes_graph, ledger_e_package, cap_field, reason
):
    """Truncated search cannot claim global minimum or complete no-path.

    Reports explicit truncation reason, caps, and bounds claims to generated subset.
    """
    budget_dict = {"max_paths": 1000, "max_steps": 12, "max_expansions": 100000}
    budget_dict[cap_field] = 1

    query = AttackQuery(
        initial_actor="Alice",
        initial_state={"control": ["Alice"]},
        target="Host",
        target_goal={"target": "Host", "required_state": {"admin_control": ["Host"]}},
        aliases=ALIASES,
        runtime_facts=DEFAULT_RUNTIME_FACTS,
        allowed_techniques=["propagate_group_entitlement", "obtain_admin_execution_on_host"],
        budget=budget_dict,
        action_bindings=DEFAULT_ACTION_BINDINGS,
        ranking_query=ledger_e_package["query"],
    )

    result = run_attack_query(query, two_routes_graph)

    assert result.truncated is True
    assert result.truncation_reason == reason
    assert result.caps[cap_field] == 1

    # Incomplete search can NEVER claim global minimum over full scope
    assert result.is_minimum_proven_over_scope is False

    if result.best_path is not None:
        assert result.optimization_scope == "best_in_generated_subset"
    else:
        assert result.optimization_scope == "truncated_incomplete"
        # Truncated without paths can NEVER claim no_path
        assert result.status == "truncated"
        assert result.is_no_path_proven_over_scope is False


def test_unrated_effort_candidate_bounds_optimization_claim(two_routes_graph, ledger_e_package):
    """When a feasible alternative program has unrated effort basis,

    the engine evaluates rated programs but bounds the optimization scope
    to 'best_in_rated_subset', refusing to claim minimum across all feasible paths.
    """
    ranking_query = copy.deepcopy(ledger_e_package["query"])
    # Set w-inherited-admin work unit to unrated in ledger
    ranking_query["work_units_ledger"]["w-inherited-admin"] = {
        "alias": "WU_INHERITED_ADMIN",
        "rating_status": "unrated",
        "status": "unrated",
        "overlap_state": "independent",
        "computed_cost": None,
        "effort_cost": None,
        "rubric_scores": None,
        "summary": "Unrated test",
        "technical_source": "synthetic://rubric/unrated",
        "applicable_queries": [ranking_query["query_metadata"]["query_id"]],
        "missing_basis_reasons": ["missing_empirical_effort_basis"],
    }

    query = AttackQuery(
        initial_actor="Alice",
        initial_state={"control": ["Alice"]},
        target="Host",
        target_goal={"target": "Host", "required_state": {"admin_control": ["Host"]}},
        aliases=ALIASES,
        runtime_facts=DEFAULT_RUNTIME_FACTS,
        allowed_techniques=["propagate_group_entitlement", "obtain_admin_execution_on_host"],
        budget={"max_paths": 1000, "max_steps": 12, "max_expansions": 100000},
        action_bindings=DEFAULT_ACTION_BINDINGS,
        ranking_query=ranking_query,
    )

    result = run_attack_query(query, two_routes_graph)

    # Search is complete, but feasible alternative program M/I is unrated
    assert result.search_result.complete is True
    assert result.min_effort is not None
    # Best rated program is D (effort 5)
    assert result.min_effort["minimum_effort_value"] == 5
    assert result.optimization_scope == "best_in_rated_subset"
    # Claim of minimum over the whole scope is rejected
    assert result.is_minimum_proven_over_scope is False


def test_anti_double_counting_and_passive_closure_invariance(two_routes_graph, ledger_e_package):
    """Anti-double-counting conformance:

    - Reused work unit within the same candidate program is counted only once.
    - Passive group entitlement closure (propagate_group_entitlement) adds 0 active work units.
    - D (1 step) and M/D (2 steps: passive closure + direct) achieve identical effort 5.
    """
    query = AttackQuery(
        initial_actor="Alice",
        initial_state={"control": ["Alice"]},
        target="Host",
        target_goal={"target": "Host", "required_state": {"admin_control": ["Host"]}},
        aliases=ALIASES,
        runtime_facts=DEFAULT_RUNTIME_FACTS,
        allowed_techniques=["propagate_group_entitlement", "obtain_admin_execution_on_host"],
        budget={"max_paths": 1000, "max_steps": 12, "max_expansions": 100000},
        action_bindings=DEFAULT_ACTION_BINDINGS,
        ranking_query=ledger_e_package["query"],
    )

    result = run_attack_query(query, two_routes_graph)

    eligible = result.ranking_result["eligible_candidates"]
    # generated_0001 corresponds to D (effort 5)
    # generated_0002 corresponds to M/D (effort 5)
    # generated_0003 corresponds to M/I (effort 2)
    assert eligible["generated_0001"]["effort"] == 5
    assert eligible["generated_0002"]["effort"] == 5
    assert eligible["generated_0003"]["effort"] == 2

    # Verify anti-double-counting: D and M/D have identical effort despite M/D having an extra hop
    assert eligible["generated_0001"]["effort"] == eligible["generated_0002"]["effort"]


def test_negative_control_distinct_context_work_units_not_deduplicated():
    """Negative control: work units bound to distinct targets/contexts

    (e.g., Host vs OtherHost) are NOT deduplicated across different execution contexts.
    """
    from src.engine.ranking.assessment import assess_candidate_program
    from src.engine.ranking.validation import decode_ranking_query

    diagnostics_pkg = json.loads(
        (RATINGS_DIR / "synthetic-a2-diagnostics.json").read_text(encoding="utf-8")
    )
    decoded = decode_ranking_query(diagnostics_pkg["query"])

    # cand_unrated_impact targets OtherHost with
    # w-auth-otherhost (1) + w-direct-admin-otherhost (4) = 5
    cand_envelope = next(
        c for c in diagnostics_pkg["candidates"] if c["candidate_id"] == "cand_unrated_impact"
    )
    assessed = assess_candidate_program(decoded, cand_envelope)

    # Effort is computed as 5 (1 + 4), not merged with Host C0's work units
    assert assessed["effort"] == 5
    assert assessed["effort_status"] == "rated"
    assert assessed["impact_status"] == "unrated"


def test_graph_immutability_and_branch_isolation(two_routes_graph):
    """Search operations must never mutate canonical graph nodes, edges, or provenance."""
    original_copy = copy.deepcopy(two_routes_graph)
    orig_digest = hashlib.sha256(
        json.dumps(original_copy, sort_keys=True).encode("utf-8")
    ).hexdigest()

    query = AttackQuery(
        initial_actor="Alice",
        initial_state={"control": ["Alice"]},
        target="Host",
        target_goal={"target": "Host", "required_state": {"admin_control": ["Host"]}},
        aliases=ALIASES,
        runtime_facts=DEFAULT_RUNTIME_FACTS,
    )

    result = run_attack_query(query, two_routes_graph)
    assert len(result.paths) == 3

    post_digest = hashlib.sha256(
        json.dumps(two_routes_graph, sort_keys=True).encode("utf-8")
    ).hexdigest()

    assert orig_digest == post_digest, "Canonical graph was mutated by search!"
    assert two_routes_graph["nodes"] == original_copy["nodes"]
    assert two_routes_graph["edges"] == original_copy["edges"]


def test_omitted_action_binding_on_lowest_effort_path_downgrades_scope(
    two_routes_graph, ledger_e_package
):
    """[BLOCKER 1 Regression] When lowest-effort generated path lacks action binding:

    - Search still generates all 3 paths.
    - Only bound paths are evaluated (effort 5).
    - Scope claim MUST be downgraded from exhaustive_within_scope to best_in_bound_subset.
    - is_minimum_proven_over_scope MUST be False.
    - binding_diagnostics must record the omitted candidate and missing step.
    """
    # Omit binding for Path 3 (inherited admin)
    bindings_missing_path3 = {
        ("obtain_admin_execution_on_host", "Alice", "Alice", "Host"): "action_direct_admin",
        ("propagate_group_entitlement", "Alice", "Alice", "Admins"): "action_member_admins",
    }

    query = AttackQuery(
        initial_actor="Alice",
        initial_state={"control": ["Alice"]},
        target="Host",
        target_goal={"target": "Host", "required_state": {"admin_control": ["Host"]}},
        aliases=ALIASES,
        runtime_facts=DEFAULT_RUNTIME_FACTS,
        allowed_techniques=["propagate_group_entitlement", "obtain_admin_execution_on_host"],
        budget={"max_paths": 1000, "max_steps": 12, "max_expansions": 100000},
        action_bindings=bindings_missing_path3,
        ranking_query=ledger_e_package["query"],
    )

    result = run_attack_query(query, two_routes_graph)

    # 1. Search generated all 3 paths
    assert len(result.paths) == 3

    # 2. Only bound paths evaluated -> best effort is 5 (instead of 2)
    assert result.min_effort is not None
    assert result.min_effort["minimum_effort_value"] == 5

    # 3. Optimization scope MUST be downgraded to best_in_bound_subset
    assert result.optimization_scope == "best_in_bound_subset"
    assert result.is_minimum_proven_over_scope is False

    # 4. Binding diagnostics captures generated_0003
    assert len(result.binding_diagnostics) == 1
    assert "generated_0003" in result.binding_diagnostics
    diag = result.binding_diagnostics["generated_0003"]
    assert diag["reason"] == "explicit_action_binding_missing"
    assert len(diag["unbound_steps"]) == 1
    assert diag["unbound_steps"][0]["technique_id"] == "obtain_admin_execution_on_host"

    # 5. Search audit in ranking_result preserves binding diagnostics
    assert result.ranking_result is not None
    audit = result.ranking_result.get("search_audit", {})
    assert audit.get("candidates_unbound") == 1
    assert audit.get("generated_candidates_bound") == 2
    assert "generated_0003" in audit.get("binding_diagnostics", {})

    # 6. Public diagnostics expose unbound candidate
    unbound_diags = [d for d in result.diagnostics if d.get("status") == "unbound"]
    assert len(unbound_diags) == 1
    assert unbound_diags[0]["candidate_id"] == "generated_0003"


def test_min_effort_retains_candidate_with_unrated_impact_or_likelihood(
    two_routes_graph, ledger_e_package
):
    """[BLOCKER 2 Regression] Candidate with rated effort but unrated impact:

    - Min-Effort selects and ties candidates across ALL assessed candidates,
      not just risk/Pareto eligible_candidates partition.
    - Path 3 (effort 2) is retained in best_path, all_best_paths, and tie counting.
    - Min-Effort completeness remains exhaustive_within_scope because all feasible
      candidates have rated effort.
    """
    ranking_query = copy.deepcopy(ledger_e_package["query"])
    # Modify target_impact_assessments so impact is unrated
    ranking_query["target_impact_assessments"] = {
        "10000000-0000-4000-8000-000000000002": {
            "target_asset_id": "10000000-0000-4000-8000-000000000002",
            "success_event": "admin_execution_on_host_c0",
            "rating_status": "unrated",
            "consequence_rating": None,
            "business_rationale": "Synthetic unrated impact test",
            "affected_business_services": [],
            "missing_basis_reasons": ["missing_impact_basis"],
        }
    }

    query = AttackQuery(
        initial_actor="Alice",
        initial_state={"control": ["Alice"]},
        target="Host",
        target_goal={"target": "Host", "required_state": {"admin_control": ["Host"]}},
        aliases=ALIASES,
        runtime_facts=DEFAULT_RUNTIME_FACTS,
        allowed_techniques=["propagate_group_entitlement", "obtain_admin_execution_on_host"],
        budget={"max_paths": 1000, "max_steps": 12, "max_expansions": 100000},
        action_bindings=DEFAULT_ACTION_BINDINGS,
        ranking_query=ranking_query,
    )

    result = run_attack_query(query, two_routes_graph)

    # Risk ranking eligible_candidates is empty because impact is unrated
    assert result.ranking_result is not None
    assert len(result.ranking_result.get("eligible_candidates", {})) == 0
    assert len(result.ranking_result.get("diagnostics", {})) == 3

    # BUT Min-Effort correctly selects from all assessed candidates:
    assert result.min_effort is not None
    assert result.min_effort["minimum_effort_value"] == 2
    assert result.min_effort["best_candidate_id"] == "generated_0003"
    assert result.min_effort["all_best_candidate_ids"] == ["generated_0003"]
    assert result.min_effort["tie_count"] == 1

    # best_path and all_best_paths retain the candidate
    assert result.best_path is not None
    assert result.best_path.cost == 2.0
    assert len(result.all_best_paths) == 1
    assert result.all_best_paths[0].cost == 2.0

    # Effort completeness is NOT downgraded by unrated impact:
    assert result.optimization_scope == "exhaustive_within_scope"
    assert result.is_minimum_proven_over_scope is True


def test_action_bindings_alias_canonical_collision_fail_closed(two_routes_graph):
    """[MAJOR 3 Regression] Alias-vs-canonical collisions in action_bindings:

    - Conflicting action IDs for the same canonical key MUST fail-closed with ValueError.
    - Identical action IDs for the same canonical key MUST deduplicate cleanly.
    """
    from src.engine import materialize_query

    # Subcase 3a: Conflicting action IDs (Alice alias vs Alice canonical SID)
    conflicting_bindings = [
        (
            ("obtain_admin_execution_on_host", "Alice", "Alice", "Host"),
            "action_direct_admin_v1",
        ),
        (
            ("obtain_admin_execution_on_host", ALICE_ID, ALICE_ID, HOST_C0_ID),
            "action_direct_admin_v2",
        ),
    ]

    with pytest.raises(ValueError, match="Conflicting action bindings for canonical key"):
        materialize_query(
            {
                "initial_actor": "Alice",
                "initial_state": {"control": ["Alice"]},
                "target": "Host",
                "target_goal": {"target": "Host", "required_state": {"admin_control": ["Host"]}},
                "aliases": ALIASES,
                "action_bindings": conflicting_bindings,
            },
            two_routes_graph,
        )

    # Subcase 3b: Identical action IDs (deduplicate cleanly)
    identical_bindings = [
        (
            ("obtain_admin_execution_on_host", "Alice", "Alice", "Host"),
            "action_direct_admin",
        ),
        (
            ("obtain_admin_execution_on_host", ALICE_ID, ALICE_ID, HOST_C0_ID),
            "action_direct_admin",
        ),
    ]

    mat = materialize_query(
        {
            "initial_actor": "Alice",
            "initial_state": {"control": ["Alice"]},
            "target": "Host",
            "target_goal": {"target": "Host", "required_state": {"admin_control": ["Host"]}},
            "aliases": ALIASES,
            "action_bindings": identical_bindings,
        },
        two_routes_graph,
    )
    assert mat.action_bindings is not None
    assert len(mat.action_bindings) == 1
    canonical_key = ("obtain_admin_execution_on_host", ALICE_ID, ALICE_ID, HOST_C0_ID)
    assert mat.action_bindings[canonical_key] == "action_direct_admin"


def test_adapter_rejected_candidate_on_lowest_effort_path_downgrades_scope(
    two_routes_graph, ledger_e_package
):
    """[BLOCKER 1 Regression - Rereview]
    When a candidate has explicit bindings for all steps, but is rejected by the canonical
    ranking adapter or envelope validator (e.g. unknown action ID or actor/target mismatch):
    - Search generates all 3 paths.
    - Evaluator evaluates the remaining valid candidates (e.g. effort 5).
    - Scope claim MUST be downgraded from exhaustive_within_scope to best_in_bound_subset.
    - is_minimum_proven_over_scope MUST be False.
    - Rejected candidate must be captured in binding_diagnostics and public diagnostics.
    """
    # Explicitly bind all transitions, but map Path 3's inherited admin step to an unknown action ID
    bindings_invalid_action_id = {
        ("obtain_admin_execution_on_host", "Alice", "Alice", "Host"): "action_direct_admin",
        ("propagate_group_entitlement", "Alice", "Alice", "Admins"): "action_member_admins",
        (
            "obtain_admin_execution_on_host",
            "Alice",
            "Admins",
            "Host",
        ): "action_inherited_admin_unknown_id",
    }

    query = AttackQuery(
        initial_actor="Alice",
        initial_state={"control": ["Alice"]},
        target="Host",
        target_goal={"target": "Host", "required_state": {"admin_control": ["Host"]}},
        aliases=ALIASES,
        runtime_facts=DEFAULT_RUNTIME_FACTS,
        allowed_techniques=["propagate_group_entitlement", "obtain_admin_execution_on_host"],
        budget={"max_paths": 1000, "max_steps": 12, "max_expansions": 100000},
        action_bindings=bindings_invalid_action_id,
        ranking_query=ledger_e_package["query"],
    )

    result = run_attack_query(query, two_routes_graph)

    # 1. Search generated all 3 paths
    assert len(result.paths) == 3

    # 2. Only remaining valid candidates evaluated -> best effort is 5 (Path 1 / Direct Admin)
    assert result.min_effort is not None
    assert result.min_effort["minimum_effort_value"] == 5

    # 3. Scope MUST downgrade to best_in_bound_subset and minimum is NOT proven
    assert result.optimization_scope == "best_in_bound_subset"
    assert result.is_minimum_proven_over_scope is False

    # 4. Binding diagnostics captures generated_0003 with adapter rejection details
    assert len(result.binding_diagnostics) == 1
    assert "generated_0003" in result.binding_diagnostics
    diag = result.binding_diagnostics["generated_0003"]
    assert "adapter_ineligible" in diag.get("reasons", [diag.get("reason")])
    assert "diagnostic" in diag and "unknown bound_action" in diag["diagnostic"]

    # 5. Search audit in ranking_result preserves rejection
    assert result.ranking_result is not None
    audit = result.ranking_result.get("search_audit", {})
    assert audit.get("candidates_rejected_by_adapter") >= 1
    assert audit.get("candidates_unbound") == 1
    assert "generated_0003" in audit.get("binding_diagnostics", {})

    # 6. Public diagnostics expose rejected candidate with rejected status
    rejected_diags = [d for d in result.diagnostics if d.get("status") == "rejected"]
    assert len(rejected_diags) == 1
    assert rejected_diags[0]["candidate_id"] == "generated_0003"
    assert "unknown bound_action" in rejected_diags[0].get("diagnostic", "")


def test_zero_action_initial_goal_satisfaction_with_distinct_foothold_and_target(
    two_routes_graph, ledger_e_package
):
    """[BLOCKER 2 Regression - Rereview]
    Zero-action / initial-goal success where initial_state already satisfies target_goal,
    with foothold (Alice) != target asset (Host):
    - Semantic success is preserved (status="success", final_goal_reached=True).
    - Returns a single 0-step PathResult (nodes=(Host,), transition_history=()).
    - Min-Effort has explicit 0 work semantics (minimum_effort_value=0.0, best_path.cost=0.0).
    - Scope claim is exhaustive_within_scope and is_minimum_proven_over_scope=True.
    - No hidden adapter rejection (binding_diagnostics is empty).
    """
    # initial_state already includes admin_control on Host
    initial_state_with_goal = {
        "control": ["Alice"],
        "admin_control": ["Host"],
    }

    query = AttackQuery(
        initial_actor="Alice",
        initial_state=initial_state_with_goal,
        target="Host",
        target_goal={"target": "Host", "required_state": {"admin_control": ["Host"]}},
        aliases=ALIASES,
        runtime_facts=DEFAULT_RUNTIME_FACTS,
        allowed_techniques=["propagate_group_entitlement", "obtain_admin_execution_on_host"],
        budget={"max_paths": 1000, "max_steps": 12, "max_expansions": 100000},
        action_bindings=DEFAULT_ACTION_BINDINGS,
        ranking_query=ledger_e_package["query"],
    )

    result = run_attack_query(query, two_routes_graph)

    # 1. Semantic success preserved
    assert result.status == "success"
    assert result.final_goal_reached is True
    assert len(result.paths) == 1
    zero_step_path = result.paths[0]
    assert len(zero_step_path.transition_history) == 0
    assert zero_step_path.nodes == (HOST_C0_ID,)

    # 2. Min-Effort evaluated with 0 work
    assert result.min_effort is not None
    assert result.min_effort["minimum_effort_value"] == 0.0
    assert result.min_effort["best_candidate_id"] == "generated_0001"
    assert result.min_effort["all_best_candidate_ids"] == ["generated_0001"]
    assert result.min_effort["tie_count"] == 1

    # 3. Best path and all_best_paths reflect 0.0 cost
    assert result.best_path is not None
    assert result.best_path.cost == 0.0
    assert len(result.all_best_paths) == 1
    assert result.all_best_paths[0].cost == 0.0

    # 4. Scope is exhaustive and minimum is proven
    assert result.optimization_scope == "exhaustive_within_scope"
    assert result.is_minimum_proven_over_scope is True

    # 5. Clean diagnostics without adapter rejection
    assert len(result.binding_diagnostics) == 0
    assert not any(d.get("status") in ("unbound", "rejected") for d in result.diagnostics)


def _run_zero_action_entry_point(entry_point, graph, ranking_query):
    """Use the same distinct actor/target initial goal through both public APIs."""
    from src.engine import SearchBudget
    from src.engine.ranking.orchestration import generate_and_evaluate_attack_paths
    from src.engine.semantics import AttackState, RuntimeContext

    if entry_point == "query":
        return run_attack_query(
            AttackQuery(
                initial_actor="Alice",
                initial_state={"control": ["Alice"], "admin_control": ["Host"]},
                target="Host",
                target_goal={"target": "Host", "required_state": {"admin_control": ["Host"]}},
                aliases=ALIASES,
                ranking_query=ranking_query,
            ),
            graph,
        )
    return generate_and_evaluate_attack_paths(
        ranking_query,
        graph,
        actor=ALICE_ID,
        initial_state=AttackState(control={ALICE_ID}, admin_control={HOST_C0_ID}),
        runtime_context=RuntimeContext(),
        budget=SearchBudget(max_paths=1000, max_steps=12, max_expansions=100000),
        action_bindings={},
        success_state_predicate=lambda state: HOST_C0_ID in state.admin_control,
    )


@pytest.mark.parametrize("entry_point", ["query", "orchestration"])
@pytest.mark.parametrize(
    "invalid_input",
    ["snapshot", "missing_metadata", "invalid_metadata", "target", "actor", "missing_section"],
)
def test_zero_action_ranking_inputs_fail_closed(
    two_routes_graph, ledger_e_package, entry_point, invalid_input
):
    from src.engine.ranking import RankingValidationError

    ranking_query = copy.deepcopy(ledger_e_package["query"])
    metadata = ranking_query["query_metadata"]
    if invalid_input == "snapshot":
        metadata["snapshot_id"] = "sha256:" + "0" * 64
    elif invalid_input == "missing_metadata":
        del ranking_query["query_metadata"]
    elif invalid_input == "invalid_metadata":
        metadata["version"] = "invalid"
    elif invalid_input == "target":
        metadata["target_goal"]["target_asset_id"] = "10000000-0000-4000-8000-000000000099"
    elif invalid_input == "actor":
        metadata["foothold_node_id"] = ADMINS_ID
    else:
        del ranking_query["facts_ledger"]

    with pytest.raises((RankingValidationError, TypeError, ValueError)):
        _run_zero_action_entry_point(entry_point, two_routes_graph, ranking_query)


@pytest.mark.parametrize("entry_point", ["query", "orchestration"])
@pytest.mark.parametrize("missing_basis", [False, True])
def test_zero_action_is_separate_from_canonical_pareto_assessment(
    two_routes_graph, ledger_e_package, entry_point, missing_basis
):
    ranking_query = copy.deepcopy(ledger_e_package["query"])
    if missing_basis:
        ranking_query["conditional_bounds_table"] = []
        ranking_query["target_impact_assessments"][HOST_C0_ID].update(
            rating_status="unrated",
            consequence_rating=None,
            missing_basis_reasons=["No reviewed business impact basis"],
        )
    original = copy.deepcopy(ranking_query)
    result = _run_zero_action_entry_point(entry_point, two_routes_graph, ranking_query)
    if entry_point == "query":
        assert result.status == "success"
        assert result.best_path.cost == 0.0
        assert result.is_minimum_proven_over_scope
        payload = result.ranking_result
        assert result.min_effort == payload["zero_work_disposition"]
    else:
        assert len(result["search_result"].paths) == 1
        assert result["assessed_candidates"] == []
        assert json.loads(result["encoded_json"]) == result["roundtrip_result"]
        payload = result["roundtrip_result"]
    assert ranking_query == original
    assert payload["eligible_candidates"] == {}
    assert payload["pareto_frontier"] == []
    assert payload["search_metadata"]["candidates_evaluated"] == 0
    assert payload["min_effort_to_da_baseline"]["minimum_effort_value"] is None
    zero_work = payload["zero_work_disposition"]
    assert zero_work["disposition"] == "semantic_initial_goal_zero_work"
    assert zero_work["ranking_status"] == "not_applicable"
    assert zero_work["minimum_effort_value"] == 0.0
    assert zero_work["associated_likelihood_interval"] is None
    assert zero_work["associated_impact"] is None
    assert payload["parameter_audit"]
