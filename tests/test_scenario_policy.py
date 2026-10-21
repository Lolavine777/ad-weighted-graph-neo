"""Unit and integration tests for SEAMLESS scenario policy specification and resolver.

Tests Issue #290: Reusable, versioned scenario policy replacing per-query
hand-crafted assumptions across diverse sources and goals.

Verifies:
1. Multi-source reuse: identical policy profile applied across AS-REP C0, GINO_ROSS,
   Kerberoasting, and OLA_CARSON.
2. Missing condition behavior: unverifiable predicates remain indeterminate without policy rule.
3. Authoritative False vetoes: snapshot enabled=False or runtime fact False rejects assumption.
4. Distribution group semantics: DISTLIST rejected by default, accepted with explicit override.
5. Recovery opt-in: recovery_success rejected by default in standard profile, accepted in what-if.
6. Security boundary enforcement: overrides trying to grant usable_identity or
   admin_control rejected.
7. Snapshot ID mismatch rejection.
8. Profile sensitivity: evidence_only vs seamless_standard_scenario vs exploratory_what_if yield
   deterministically distinct states.
9. Integration with materialize_query and search execution.
"""

from __future__ import annotations

import copy
import json
from typing import Any

import networkx as nx
import pytest

from src.engine.graph import EngineGraph
from src.engine.query import materialize_query
from src.engine.semantics.scenario_policy import (
    SEAMLESS_SNAPSHOT_ID,
    STANDARD_SEAMLESS_RULES,
    ApplicabilityRule,
    PolicyOverride,
    RuleTaxonomy,
    ScenarioPolicyProfile,
    ScenarioPolicyResolutionResult,
    apply_policy_to_query,
    load_policy_profile,
    resolve_scenario_policy,
)


@pytest.fixture
def seamless_graph_fixture() -> dict[str, Any]:
    """Synthetic representative SEAMLESS graph with users, groups, and computers."""
    return {
        "metadata": {
            "snapshot_id": SEAMLESS_SNAPSHOT_ID,
            "domain": "SEAMLESS.LOCAL",
        },
        "nodes": [
            {"id": "USER-C0", "kind": "User", "label": "C0", "enabled": True},
            {
                "id": "USER-GINO",
                "kind": "User",
                "label": "GINO_ROSS",
                "enabled": True,
                "dontreqpreauth": True,
            },
            {
                "id": "USER-OLA",
                "kind": "User",
                "label": "OLA_CARSON",
                "enabled": True,
                "serviceprincipalnames": ["HTTP/web.seamless.local"],
            },
            {
                "id": "USER-ALEX",
                "kind": "User",
                "label": "ALEXANDRIA_WALSH",
                "enabled": True,
            },
            {"id": "USER-DISABLED", "kind": "User", "label": "DISABLED_USER", "enabled": False},
            {
                "id": "GROUP-DU",
                "kind": "Group",
                "label": "DOMAIN USERS",
                "objectsid": "S-1-5-21-1271839998-3495686680-2211690266-513",
                "security_enabled": True,
            },
            {
                "id": "GROUP-DA",
                "kind": "Group",
                "label": "DOMAIN ADMINS",
                "objectsid": "S-1-5-21-1271839998-3495686680-2211690266-512",
                "security_enabled": True,
            },
            {
                "id": "GROUP-ADM1",
                "kind": "Group",
                "label": "VA-JER-ADMINGROUP1",
                "security_enabled": True,
            },
            {"id": "GROUP-DIST1", "kind": "Group", "label": "HO-170-DISTLIST1"},
            {"id": "GROUP-DL2", "kind": "Group", "label": "CORP-DL-ANNOUNCEMENTS"},
            {"id": "COMP-WS1", "kind": "Computer", "label": "WS-01.SEAMLESS.LOCAL"},
            {"id": "COMP-DC1", "kind": "Computer", "label": "DC01.SEAMLESS.LOCAL"},
        ],
        "edges": [
            {"id": "e1", "source": "USER-C0", "target": "GROUP-DU", "kind": "MemberOf"},
            {"id": "e2", "source": "USER-GINO", "target": "GROUP-DU", "kind": "MemberOf"},
            {"id": "e3", "source": "USER-OLA", "target": "GROUP-DU", "kind": "MemberOf"},
            {"id": "e4", "source": "USER-ALEX", "target": "GROUP-DIST1", "kind": "MemberOf"},
            {"id": "e5", "source": "USER-C0", "target": "GROUP-ADM1", "kind": "MemberOf"},
            {"id": "e6", "source": "GROUP-ADM1", "target": "COMP-WS1", "kind": "AdminTo"},
            {"id": "e7", "source": "USER-GINO", "target": "GROUP-DA", "kind": "GenericAll"},
            {"id": "e8", "source": "USER-OLA", "target": "USER-ALEX", "kind": "GenericAll"},
            {"id": "e9", "source": "GROUP-DA", "target": "COMP-DC1", "kind": "AdminTo"},
            {"id": "e10", "source": "USER-DISABLED", "target": "GROUP-DU", "kind": "MemberOf"},
        ],
    }


# ==============================================================================
# 1. Multi-source reuse tests
# ==============================================================================


def test_multi_source_reuse_standard_profile(seamless_graph_fixture):
    """The same standard policy profile resolves appropriate assumptions across
    4 distinct sources.
    """
    profile = load_policy_profile("seamless_standard_scenario")

    sources_to_test = [
        {"actor": "USER-C0", "target": "COMP-WS1", "known": ["USER-GINO"]},
        {"actor": "USER-GINO", "target": "COMP-DC1", "known": ["USER-OLA"]},
        {"actor": "USER-OLA", "target": "COMP-DC1", "known": ["USER-ALEX"]},
        {"actor": "USER-ALEX", "target": "COMP-WS1", "known": []},
    ]

    for spec in sources_to_test:
        query = {
            "initial_actor": spec["actor"],
            "source_foothold": spec["actor"],
            "target": spec["target"],
            "authentication_context": spec["actor"],
            "initial_state": {
                "control": [spec["actor"]],
                "usable_identity": [[spec["actor"], spec["actor"]]],
                "known_identity": spec["known"],
            },
            "target_goal": {
                "target": spec["target"],
                "required_state": {"admin_control": [spec["target"]]},
            },
        }
        res = resolve_scenario_policy(seamless_graph_fixture, query, profile=profile)
        assert isinstance(res, ScenarioPolicyResolutionResult)
        assert res.profile_id == "seamless-standard-v1"
        assert res.evaluation_mode == "seamless_standard_scenario"
        assert len(res.assumptions) > 0

        # In standard mode, recovery_success must never appear
        assert not any(a.predicate == "recovery_success" for a in res.assumptions)
        # Attacker capabilities must never be assumed
        assert not any(
            a.predicate in ("usable_identity", "admin_control", "control") for a in res.assumptions
        )


# ==============================================================================
# 2. Missing condition / Invariant tests
# ==============================================================================


def test_missing_condition_behavior(seamless_graph_fixture):
    """Predicates without declared rules in profile are NOT fabricated."""
    profile = load_policy_profile("seamless_standard_scenario")
    query = {
        "initial_actor": "USER-C0",
        "target": "COMP-WS1",
        "authentication_context": "USER-C0",
        "initial_state": {"control": ["USER-C0"], "usable_identity": [["USER-C0", "USER-C0"]]},
        "target_goal": {"target": "COMP-WS1", "required_state": {"admin_control": ["COMP-WS1"]}},
    }
    res = resolve_scenario_policy(seamless_graph_fixture, query, profile=profile)

    # Predicates like 'arbitrary_predicate' or 'credential_accessible' are not generated
    resolved_preds = {a.predicate for a in res.assumptions}
    assert "arbitrary_unrelated_predicate" not in resolved_preds
    assert "credential_accessible" not in resolved_preds
    assert "session_fresh" not in resolved_preds


# ==============================================================================
# 3. Authoritative False vetoes
# ==============================================================================


def test_authoritative_false_veto_from_runtime_facts(seamless_graph_fixture):
    """Runtime facts containing False authoritative evidence veto candidate assumptions."""
    profile = load_policy_profile("seamless_standard_scenario")
    query = {
        "initial_actor": "USER-C0",
        "target": "COMP-WS1",
        "authentication_context": "USER-C0",
        "runtime_facts": [
            {
                "predicate": "admin_channel",
                "subject": "GROUP-ADM1",
                "target": "COMP-WS1",
                "value": False,
                "origin": "snapshot",
            }
        ],
        "initial_state": {"control": ["USER-C0"], "usable_identity": [["USER-C0", "USER-C0"]]},
        "target_goal": {"target": "COMP-WS1", "required_state": {"admin_control": ["COMP-WS1"]}},
    }
    res = resolve_scenario_policy(seamless_graph_fixture, query, profile=profile)

    # admin_channel on GROUP-ADM1 -> COMP-WS1 must be vetoed
    assert not any(
        a.predicate == "admin_channel" and a.subject == "GROUP-ADM1" and a.target == "COMP-WS1"
        for a in res.assumptions
    )
    vetoed = [r for r in res.rejected_assumptions if r.reason == "known_false_veto"]
    assert len(vetoed) >= 1
    assert any(
        r.predicate == "admin_channel" and r.conflicting_origin == "runtime_facts" for r in vetoed
    )


def test_authoritative_false_veto_disabled_account(seamless_graph_fixture):
    """Disabled account (enabled=False) in snapshot vetoes actor_enabled or target_enabled."""
    # Add candidate assumption for target_enabled
    custom_rule = ApplicabilityRule(
        rule_id="rule-test-enabled",
        predicate="target_enabled",
        taxonomy=RuleTaxonomy.TYPED,
        provenance_reference="policy://test",
    )
    test_profile = ScenarioPolicyProfile(
        profile_id="test-profile",
        version="1.0.0",
        bound_snapshot_id=SEAMLESS_SNAPSHOT_ID,
        evaluation_mode="seamless_standard_scenario",
        rules=(custom_rule,),
        forbidden_predicates=(),
        description="Test",
    )
    query = {
        "initial_actor": "USER-C0",
        "target": "USER-DISABLED",
        "authentication_context": "USER-C0",
        "initial_state": {"control": ["USER-C0"], "usable_identity": [["USER-C0", "USER-C0"]]},
        "target_goal": {
            "target": "USER-DISABLED",
            "required_state": {"control": ["USER-DISABLED"]},
        },
    }
    # Provide override to trigger target_enabled on disabled account
    override = PolicyOverride(
        predicate="target_enabled",
        subject="USER-C0",
        target="USER-DISABLED",
        value=True,
        rationale="Hypothetical enabled",
    )
    res = resolve_scenario_policy(
        seamless_graph_fixture,
        query,
        profile=test_profile,
        overrides=[override],
    )
    # Must be vetoed because USER-DISABLED has enabled=False in snapshot
    assert not any(a.predicate == "target_enabled" for a in res.assumptions)
    vetoed = [r for r in res.rejected_assumptions if r.reason == "known_false_veto"]
    assert any(r.predicate == "target_enabled" and r.target == "USER-DISABLED" for r in vetoed)


# ==============================================================================
# 4. Distribution group semantics
# ==============================================================================


def test_distribution_group_rejection_and_override(seamless_graph_fixture):
    """Groups named DISTLIST or DL are rejected by default; accepted only with explicit override."""
    profile = load_policy_profile("seamless_standard_scenario")
    query = {
        "initial_actor": "USER-ALEX",
        "target": "COMP-WS1",
        "authentication_context": "USER-ALEX",
        "initial_state": {
            "control": ["USER-ALEX"],
            "usable_identity": [["USER-ALEX", "USER-ALEX"]],
        },
        "target_goal": {"target": "COMP-WS1", "required_state": {"admin_control": ["COMP-WS1"]}},
    }
    # By default, USER-ALEX is MemberOf GROUP-DIST1 (HO-170-DISTLIST1)
    res_default = resolve_scenario_policy(seamless_graph_fixture, query, profile=profile)

    # security_group on GROUP-DIST1 must be rejected
    dist_rejections = [
        r
        for r in res_default.rejected_assumptions
        if r.target == "GROUP-DIST1" and r.reason == "distribution_group_cannot_default"
    ]
    assert len(dist_rejections) == 1
    assert not any(
        a.target == "GROUP-DIST1" and a.predicate == "security_group"
        for a in res_default.assumptions
    )

    # Standard security group GROUP-ADM1 (VA-JER-ADMINGROUP1) must be accepted
    assert any(
        a.target == "GROUP-ADM1" and a.predicate == "security_group"
        for a in res_default.assumptions
    )

    # With explicit override, distribution list can be accepted
    override = PolicyOverride(
        predicate="security_group",
        subject="USER-ALEX",
        target="GROUP-DIST1",
        value=True,
        override_type="mail_enabled_security_group",
        rationale="Verified out-of-band as mail-enabled security group",
    )
    res_overridden = resolve_scenario_policy(
        seamless_graph_fixture,
        query,
        profile=profile,
        overrides=[override],
    )
    assert any(
        a.target == "GROUP-DIST1" and a.predicate == "security_group"
        for a in res_overridden.assumptions
    )
    assert len(res_overridden.applied_overrides) == 1


# ==============================================================================
# 5. Recovery opt-in
# ==============================================================================


def test_recovery_opt_in_policy(seamless_graph_fixture):
    """recovery_success is rejected in standard profile, but accepted in what-if profile."""
    standard_profile = load_policy_profile("seamless_standard_scenario")
    what_if_profile = load_policy_profile("exploratory_what_if")

    query = {
        "initial_actor": "USER-C0",
        "target": "COMP-DC1",
        "authentication_context": "USER-C0",
        "initial_state": {
            "control": ["USER-C0"],
            "usable_identity": [["USER-C0", "USER-C0"]],
            "known_identity": ["USER-GINO"],
        },
        "target_goal": {"target": "COMP-DC1", "required_state": {"admin_control": ["COMP-DC1"]}},
    }

    override = PolicyOverride(
        predicate="recovery_success",
        subject="USER-C0",
        target="USER-GINO",
        value=True,
        override_type="recovery_opt_in",
        rationale="Cracking budget 48h hashcat dictionary attack",
        metadata={"method": "hashcat_dictionary", "budget": "48h", "horizon": "48h"},
    )

    # 1. Standard mode without override: no recovery_success
    res_std = resolve_scenario_policy(seamless_graph_fixture, query, profile=standard_profile)
    assert not any(a.predicate == "recovery_success" for a in res_std.assumptions)

    # 2. Standard mode with override: rejected because recovery_success
    # is in forbidden_predicates of standard
    res_std_attempt = resolve_scenario_policy(
        seamless_graph_fixture, query, profile=standard_profile, overrides=[override]
    )
    # forbidden_predicates in standard profile rejects it
    assert not any(a.predicate == "recovery_success" for a in res_std_attempt.assumptions)
    assert any(
        r.predicate == "recovery_success" and r.reason == "forbidden_to_default"
        for r in res_std_attempt.rejected_assumptions
    )

    # 3. What-if mode with override: accepted!
    res_whatif = resolve_scenario_policy(
        seamless_graph_fixture, query, profile=what_if_profile, overrides=[override]
    )
    assert any(
        a.predicate == "recovery_success" and a.target == "USER-GINO"
        for a in res_whatif.assumptions
    )
    assert len(res_whatif.applied_overrides) == 1


# ==============================================================================
# 6. Security boundary enforcement
# ==============================================================================


def test_security_boundary_enforcement(seamless_graph_fixture):
    """Overrides attempting to grant attacker capabilities or edges are rejected."""
    profile = load_policy_profile("exploratory_what_if")

    forbidden_overrides = [
        PolicyOverride(
            predicate="control",
            subject="USER-C0",
            target="COMP-DC1",
            value=True,
            rationale="Attempting to assume control",
        ),
        PolicyOverride(
            predicate="usable_identity",
            subject="USER-C0",
            target="USER-GINO",
            value=True,
            rationale="Attempting to assume usable_identity",
        ),
        PolicyOverride(
            predicate="admin_control",
            subject="USER-C0",
            target="COMP-DC1",
            value=True,
            rationale="Attempting to assume admin_control",
        ),
        PolicyOverride(
            predicate="relationship_exists",
            subject="USER-C0",
            target="COMP-DC1",
            value=True,
            rationale="Attempting to assume structural relationship",
        ),
    ]

    query = {
        "initial_actor": "USER-C0",
        "target": "COMP-DC1",
        "authentication_context": "USER-C0",
        "initial_state": {"control": ["USER-C0"], "usable_identity": [["USER-C0", "USER-C0"]]},
        "target_goal": {"target": "COMP-DC1", "required_state": {"admin_control": ["COMP-DC1"]}},
    }

    res = resolve_scenario_policy(
        seamless_graph_fixture, query, profile=profile, overrides=forbidden_overrides
    )

    # None of the forbidden predicates may appear in assumptions
    resolved_preds = {a.predicate for a in res.assumptions}
    for bad_pred in ("control", "usable_identity", "admin_control", "relationship_exists"):
        assert bad_pred not in resolved_preds

    # All must be rejected with override_violates_non_negotiable_security_boundary
    boundary_rejections = [
        r
        for r in res.rejected_assumptions
        if r.reason == "override_violates_non_negotiable_security_boundary"
    ]
    assert len(boundary_rejections) == len(forbidden_overrides)


# ==============================================================================
# 7. Snapshot ID mismatch rejection
# ==============================================================================


def test_snapshot_id_mismatch_rejection(seamless_graph_fixture):
    """Mismatched snapshot ID raises ValueError when enforce_snapshot_binding is True."""
    tampered_graph = dict(seamless_graph_fixture)
    tampered_graph["metadata"] = {"snapshot_id": "sha256:00000000000000000000000000000000"}

    query = {
        "initial_actor": "USER-C0",
        "target": "COMP-WS1",
        "authentication_context": "USER-C0",
        "initial_state": {"control": ["USER-C0"], "usable_identity": [["USER-C0", "USER-C0"]]},
        "target_goal": {"target": "COMP-WS1", "required_state": {"admin_control": ["COMP-WS1"]}},
    }

    with pytest.raises(ValueError, match="bound to snapshot"):
        resolve_scenario_policy(tampered_graph, query, enforce_snapshot_binding=True)

    # When enforce_snapshot_binding=False, it executes without error
    res = resolve_scenario_policy(
        tampered_graph,
        query,
        profile="seamless_standard_scenario",
        enforce_snapshot_binding=False,
    )
    assert len(res.assumptions) > 0


# ==============================================================================
# 8. Profile sensitivity
# ==============================================================================


def test_profile_sensitivity_distinct_states(seamless_graph_fixture):
    """evidence_only, standard, and what-if yield deterministically distinct states."""
    query = {
        "initial_actor": "USER-C0",
        "target": "COMP-WS1",
        "authentication_context": "USER-C0",
        "initial_state": {
            "control": ["USER-C0"],
            "usable_identity": [["USER-C0", "USER-C0"]],
            "known_identity": ["USER-GINO"],
        },
        "target_goal": {"target": "COMP-WS1", "required_state": {"admin_control": ["COMP-WS1"]}},
    }

    # 1. evidence_only -> 0 assumptions
    res_evidence = resolve_scenario_policy(seamless_graph_fixture, query, profile="evidence_only")
    assert len(res_evidence.assumptions) == 0
    assert res_evidence.evaluation_mode == "evidence_only"

    # 2. standard -> assumptions > 0, 0 recovery_success
    res_std = resolve_scenario_policy(
        seamless_graph_fixture, query, profile="seamless_standard_scenario"
    )
    assert len(res_std.assumptions) > 0
    assert not any(a.predicate == "recovery_success" for a in res_std.assumptions)

    # 3. what-if with recovery override -> standard assumptions + recovery_success
    res_whatif = resolve_scenario_policy(
        seamless_graph_fixture,
        query,
        profile="exploratory_what_if",
        overrides=[
            PolicyOverride(
                predicate="recovery_success",
                subject="USER-C0",
                target="USER-GINO",
                value=True,
                override_type="recovery_opt_in",
                rationale="Cracking budget",
                metadata={"method": "hashcat_dictionary", "budget": "48h", "horizon": "48h"},
            )
        ],
    )
    assert len(res_whatif.assumptions) == len(res_std.assumptions) + 1
    assert any(a.predicate == "recovery_success" for a in res_whatif.assumptions)


# ==============================================================================
# 9. Consumer integration (apply_policy_to_query + materialize_query)
# ==============================================================================


def test_apply_policy_to_query_and_materialization(seamless_graph_fixture):
    """apply_policy_to_query generates a compliant query dict consumable by materialize_query."""
    query_input = {
        "initial_actor": "USER-C0",
        "source_foothold": "USER-C0",
        "target": "COMP-WS1",
        "authentication_context": "USER-C0",
        "initial_state": {
            "control": ["USER-C0"],
            "usable_identity": [["USER-C0", "USER-C0"]],
            "known_identity": ["USER-GINO"],
        },
        "target_goal": {
            "target": "COMP-WS1",
            "required_state": {"admin_control": ["COMP-WS1"]},
        },
    }

    compiled_query = apply_policy_to_query(
        query_input, seamless_graph_fixture, profile="seamless_standard_scenario"
    )

    assert compiled_query["evaluation_mode"] == "scenario"
    assert len(compiled_query["assumptions"]) > 0
    assert "scenario_policy_metadata" in compiled_query
    meta = compiled_query["scenario_policy_metadata"]
    assert meta["profile_id"] == "seamless-standard-v1"
    assert meta["snapshot_id"] == SEAMLESS_SNAPSHOT_ID

    g = nx.MultiDiGraph()
    for node in seamless_graph_fixture["nodes"]:
        g.add_node(node["id"], record=copy.deepcopy(node))
    for edge in seamless_graph_fixture["edges"]:
        g.add_edge(edge["source"], edge["target"], key=edge["id"], record=copy.deepcopy(edge))
    engine_graph = EngineGraph(g, copy.deepcopy(seamless_graph_fixture["metadata"]), [])

    # Materialize query using the core engine query materializer
    materialized = materialize_query(compiled_query, graph=engine_graph)
    assert materialized.runtime_context is not None
    assert len(materialized.runtime_context.facts) > 0

    # Execute search with the materialized query
    search_res = materialized.search(engine_graph)
    assert len(search_res.paths) > 0
    first_path = search_res.paths[0]
    assert len(first_path.transition_history) > 0
    assert first_path.target == "COMP-WS1"
    assert "COMP-WS1" in first_path.final_state.admin_control


# ==============================================================================
# 10. Additional Oracle and Regression Invariants
# ==============================================================================


def test_authoritative_false_veto_snapshot_facts(seamless_graph_fixture):
    """SnapshotFacts lookup returning False vetoes assumption with known_false_veto."""
    from unittest.mock import MagicMock

    mock_facts = MagicMock()
    mock_facts.snapshot_id = SEAMLESS_SNAPSHOT_ID
    mock_fact_record = MagicMock()
    mock_fact_record.value = False
    mock_facts.lookup.return_value = mock_fact_record

    graph_with_facts = dict(seamless_graph_fixture)
    graph_with_facts["snapshot_facts"] = mock_facts

    # Custom profile with dontreqpreauth
    test_profile = ScenarioPolicyProfile(
        profile_id="test-facts-profile",
        version="1.0.0",
        bound_snapshot_id=SEAMLESS_SNAPSHOT_ID,
        evaluation_mode="seamless_standard_scenario",
        rules=(
            ApplicabilityRule(
                rule_id="rule-test-preauth",
                predicate="dontreqpreauth",
                taxonomy=RuleTaxonomy.GLOBAL,
                provenance_reference="policy://test",
            ),
        ),
        forbidden_predicates=(),
        description="Test",
    )

    query = {
        "initial_actor": "USER-C0",
        "target": "USER-GINO",
        "authentication_context": "USER-C0",
        "initial_state": {"control": ["USER-C0"], "known_identity": ["USER-GINO"]},
        "target_goal": {"target": "USER-GINO", "required_state": {"control": ["USER-GINO"]}},
    }

    override = PolicyOverride(
        predicate="dontreqpreauth",
        subject="USER-C0",
        target="USER-GINO",
        value=True,
        rationale="Hypothetical preauth flag",
    )

    res = resolve_scenario_policy(
        graph_with_facts, query, profile=test_profile, overrides=[override]
    )
    assert not any(a.predicate == "dontreqpreauth" for a in res.assumptions)
    vetoed = [r for r in res.rejected_assumptions if r.reason == "known_false_veto"]
    assert any(
        r.predicate == "dontreqpreauth" and r.conflicting_origin == "snapshot_facts" for r in vetoed
    )


def test_recovery_never_implies_p1(seamless_graph_fixture):
    """Non-negotiable invariant: successful assumptions never inject probability P=1."""
    profile = load_policy_profile("exploratory_what_if")
    override = PolicyOverride(
        predicate="recovery_success",
        subject="USER-C0",
        target="USER-GINO",
        value=True,
        override_type="recovery_opt_in",
        rationale="Offline hashcat dictionary",
        metadata={"method": "hashcat_dictionary", "budget": "48h", "horizon": "48h"},
    )

    query = {
        "initial_actor": "USER-C0",
        "target": "COMP-DC1",
        "authentication_context": "USER-C0",
        "initial_state": {
            "control": ["USER-C0"],
            "usable_identity": [["USER-C0", "USER-C0"]],
            "known_identity": ["USER-GINO"],
        },
        "target_goal": {"target": "COMP-DC1", "required_state": {"admin_control": ["COMP-DC1"]}},
    }

    compiled = apply_policy_to_query(
        query, seamless_graph_fixture, profile=profile, overrides=[override]
    )

    # All generated assumptions must have origin DECLARED_ASSUMPTION
    for asm in compiled["assumptions"]:
        assert asm["origin"] == "declared_assumption"
        # No assumption metadata may claim P=1
        meta = asm.get("assumption_metadata", {})
        assert meta.get("probability") != 1
        assert meta.get("probability") != 1.0


def test_profile_json_schema_validation():
    """Verify that seamless-policy-profile-v1.json conforms to seamless-policy.schema.json."""
    from pathlib import Path

    import jsonschema

    root = Path(__file__).resolve().parents[1]
    schema = json.loads(
        (root / "docs/research/scenarios/seamless-policy.schema.json").read_text(encoding="utf-8")
    )
    profile_data = json.loads(
        (root / "docs/research/scenarios/seamless-policy-profile-v1.json").read_text(
            encoding="utf-8"
        )
    )

    jsonschema.validate(instance=profile_data, schema=schema)
    assert profile_data["profile_id"] == "seamless-standard-v1"
    assert profile_data["bound_snapshot_id"] == SEAMLESS_SNAPSHOT_ID


def test_load_policy_profile_from_file():
    """Verify load_policy_profile loads correctly from file path."""
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    path = root / "docs/research/scenarios/seamless-policy-profile-v1.json"
    profile = load_policy_profile(path)

    assert isinstance(profile, ScenarioPolicyProfile)
    assert profile.profile_id == "seamless-standard-v1"
    assert profile.version == "1.0.0"
    assert profile.bound_snapshot_id == SEAMLESS_SNAPSHOT_ID
    assert len(profile.rules) >= 15
    assert "recovery_success" in profile.forbidden_predicates


def test_conflicting_overrides_rejected(seamless_graph_fixture):
    """Passing contradictory overrides for the same predicate and target raises ValueError."""
    query = {"initial_actor": "USER-C0", "target": "COMP-WS1"}
    ov1 = PolicyOverride(
        predicate="admin_channel",
        subject="USER-C0",
        target="COMP-WS1",
        value=True,
    )
    ov2 = PolicyOverride(
        predicate="admin_channel",
        subject="USER-C0",
        target="COMP-WS1",
        value=False,
    )
    with pytest.raises(ValueError, match="conflicting policy overrides"):
        resolve_scenario_policy(seamless_graph_fixture, query, overrides=[ov1, ov2])


def test_engine_graph_snapshot_binding_rejection(seamless_graph_fixture):
    """EngineGraph with mismatched snapshot_id raises ValueError when binding is enforced."""
    g = nx.MultiDiGraph()
    for node in seamless_graph_fixture["nodes"]:
        g.add_node(node["id"], record=copy.deepcopy(node))
    for edge in seamless_graph_fixture["edges"]:
        g.add_edge(edge["source"], edge["target"], key=edge["id"], record=copy.deepcopy(edge))

    mismatched_metadata = {"snapshot_id": "sha256:00000000000000000000000000000000"}
    engine_graph = EngineGraph(g, mismatched_metadata, [])

    query = {"initial_actor": "USER-C0", "target": "COMP-WS1"}
    with pytest.raises(ValueError, match="bound to snapshot"):
        resolve_scenario_policy(engine_graph, query, enforce_snapshot_binding=True)

    # If enforce_snapshot_binding is False, it succeeds
    res = resolve_scenario_policy(
        engine_graph,
        query,
        profile="seamless_standard_scenario",
        enforce_snapshot_binding=False,
    )
    assert len(res.assumptions) > 0


def test_raw_networkx_graph_compatibility(seamless_graph_fixture):
    """Direct NetworkX MultiDiGraph instances resolve cleanly."""
    g = nx.MultiDiGraph()
    for node in seamless_graph_fixture["nodes"]:
        g.add_node(node["id"], record=copy.deepcopy(node))
    for edge in seamless_graph_fixture["edges"]:
        g.add_edge(edge["source"], edge["target"], key=edge["id"], record=copy.deepcopy(edge))

    query = {"initial_actor": "USER-C0", "target": "COMP-WS1"}
    res = resolve_scenario_policy(
        g,
        query,
        profile="seamless_standard_scenario",
        enforce_snapshot_binding=False,
    )
    assert len(res.assumptions) > 0
    assert any(a.predicate == "admin_channel" for a in res.assumptions)


def test_empty_rules_profile_generates_zero_assumptions(seamless_graph_fixture):
    """Profile with empty rules generates zero assumptions unless overrides are provided."""
    empty_profile = ScenarioPolicyProfile(
        profile_id="empty-profile",
        version="1.0.0",
        bound_snapshot_id=SEAMLESS_SNAPSHOT_ID,
        evaluation_mode="seamless_standard_scenario",
        description="Empty test profile",
        rules=(),
        forbidden_predicates=(),
    )
    query = {"initial_actor": "USER-C0", "target": "COMP-WS1"}
    res = resolve_scenario_policy(seamless_graph_fixture, query, profile=empty_profile)
    assert len(res.assumptions) == 0
    assert len(res.rejected_assumptions) == 0
    assert len(res.applied_overrides) == 0


def test_rejected_override_excluded_from_applied_overrides(seamless_graph_fixture):
    """Rejected overrides (e.g. boundary or forbidden) are not in applied_overrides."""
    query = {"initial_actor": "USER-C0", "target": "COMP-WS1"}
    # 1. Attacker capability override rejected at non-negotiable boundary
    cap_ov = PolicyOverride(
        predicate="usable_identity",
        subject="USER-C0",
        target="USER-GINO",
        value=True,
    )
    # 2. Forbidden predicate override in standard profile
    forbid_ov = PolicyOverride(
        predicate="recovery_success",
        subject="USER-C0",
        target="USER-GINO",
        value=True,
    )
    # 3. Valid scoped override
    valid_ov = PolicyOverride(
        predicate="security_group",
        subject="USER-ALEX",
        target="GROUP-DIST1",
        value=True,
    )

    res = resolve_scenario_policy(
        seamless_graph_fixture,
        query,
        profile="seamless_standard_scenario",
        overrides=[cap_ov, forbid_ov, valid_ov],
    )
    applied_preds = [o.predicate for o in res.applied_overrides]
    assert "usable_identity" not in applied_preds
    assert "recovery_success" not in applied_preds
    assert "security_group" in applied_preds

    rejected_preds = [r.predicate for r in res.rejected_assumptions]
    assert "usable_identity" in rejected_preds
    assert "recovery_success" in rejected_preds


def test_security_group_rule_presence_and_profile_count():
    """Verify rule-typed-security-group is defined in Python and JSON specification."""
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    profile_data = json.loads(
        (root / "docs/research/scenarios/seamless-policy-profile-v1.json").read_text(
            encoding="utf-8"
        )
    )

    # 1. Python standard rules
    py_rule_ids = {r.rule_id for r in STANDARD_SEAMLESS_RULES}
    assert "rule-typed-security-group" in py_rule_ids
    assert len(STANDARD_SEAMLESS_RULES) == 22

    # 2. JSON specification
    json_rule_ids = {r["rule_id"] for r in profile_data["rules"]}
    assert "rule-typed-security-group" in json_rule_ids
    assert len(profile_data["rules"]) == 22
    assert py_rule_ids == json_rule_ids


def test_absent_snapshot_identity_fails_closed(seamless_graph_fixture: dict[str, Any]) -> None:
    """Fail closed when snapshot_id is absent from graph metadata."""
    g = copy.deepcopy(seamless_graph_fixture)
    del g["metadata"]["snapshot_id"]
    query = {"source_foothold": "COMP-X", "target": "COMP-C0"}
    with pytest.raises(ValueError, match="authoritative snapshot_id is required"):
        resolve_scenario_policy(g, query, profile="seamless_standard_scenario")


def test_disabled_object_veto_on_arbitrary_predicates(
    seamless_graph_fixture: dict[str, Any],
) -> None:
    """Authoritative False (enabled=False) on node vetoes candidate assumptions on that node."""
    g = copy.deepcopy(seamless_graph_fixture)
    query = {
        "source_foothold": "COMP-X",
        "initial_actor": "USER-DISABLED",
        "authentication_context": "COMP-X",
        "target": "COMP-C0",
    }
    res = resolve_scenario_policy(g, query, profile="seamless_standard_scenario")
    for fact in res.assumptions:
        assert fact.subject != "USER-DISABLED"
        assert fact.target != "USER-DISABLED"
    vetoed = [r for r in res.rejected_assumptions if r.reason == "known_false_veto"]
    assert any(r.subject == "USER-DISABLED" or r.target == "USER-DISABLED" for r in vetoed)


def test_unrecognized_group_without_grouptype_stays_unknown(
    seamless_graph_fixture: dict[str, Any],
) -> None:
    """Unrecognized groups without groupType stay unknown without proposing security_group."""
    g = copy.deepcopy(seamless_graph_fixture)
    g["nodes"].append(
        {"id": "GROUP-AMBIGUOUS", "kind": "Group", "label": "CUSTOM_GROUP_XYZ", "enabled": True}
    )
    g["edges"].append(
        {
            "id": "EDGE-AMBIGUOUS",
            "kind": "MemberOf",
            "source": "USER-GINO",
            "target": "GROUP-AMBIGUOUS",
        }
    )
    query = {
        "source_foothold": "COMP-X",
        "initial_actor": "USER-GINO",
        "authentication_context": "COMP-X",
        "target": "GROUP-AMBIGUOUS",
    }
    res = resolve_scenario_policy(g, query, profile="seamless_standard_scenario")
    sec_groups = [f.target for f in res.assumptions if f.predicate == "security_group"]
    assert "GROUP-AMBIGUOUS" not in sec_groups


def test_recovery_opt_in_metadata_validation(seamless_graph_fixture: dict[str, Any]) -> None:
    """recovery_opt_in requires valid override_type and structured metadata."""
    query = {"source_foothold": "COMP-X", "target": "COMP-C0"}

    # 1. Wrong override_type
    bad_type_ov = PolicyOverride(
        predicate="recovery_success",
        subject="COMP-X",
        target="USER-C0",
        value=True,
        override_type="custom_recovery",
        rationale="Invalid type",
        metadata={"method": "hashcat", "budget": "24h"},
    )
    res = resolve_scenario_policy(
        seamless_graph_fixture, query, profile="exploratory_what_if", overrides=[bad_type_ov]
    )
    rejections = [r for r in res.rejected_assumptions if r.predicate == "recovery_success"]
    assert any(r.reason == "invalid_recovery_override_type" for r in rejections)

    # 2. Missing method or budget
    missing_meta_ov = PolicyOverride(
        predicate="recovery_success",
        subject="COMP-X",
        target="USER-C0",
        value=True,
        override_type="recovery_opt_in",
        rationale="Missing method",
        metadata={"budget": "24h"},
    )
    res2 = resolve_scenario_policy(
        seamless_graph_fixture, query, profile="exploratory_what_if", overrides=[missing_meta_ov]
    )
    rejections2 = [r for r in res2.rejected_assumptions if r.predicate == "recovery_success"]
    assert any(r.reason == "invalid_recovery_opt_in_metadata" for r in rejections2)

    # 3. Valid metadata with horizon defaulting to budget
    valid_ov = PolicyOverride(
        predicate="recovery_success",
        subject="COMP-X",
        target="USER-C0",
        value=True,
        override_type="recovery_opt_in",
        rationale="Valid opt-in",
        metadata={"method": "hashcat", "budget": "24h"},
    )
    res3 = resolve_scenario_policy(
        seamless_graph_fixture, query, profile="exploratory_what_if", overrides=[valid_ov]
    )
    rec_facts = [f for f in res3.assumptions if f.predicate == "recovery_success"]
    assert len(rec_facts) == 1
    assert rec_facts[0].assumption_metadata.get("horizon") == "24h"


def test_apply_policy_to_query_preserves_and_merges_assumptions(
    seamless_graph_fixture: dict[str, Any],
) -> None:
    """apply_policy_to_query safely preserves existing query assumptions and catches conflicts."""
    query = {
        "source_foothold": "COMP-X",
        "initial_actor": "COMP-X",
        "authentication_context": "COMP-X",
        "target": "COMP-C0",
        "assumptions": [
            {
                "predicate": "custom_existing_fact",
                "subject": "COMP-X",
                "target": "COMP-C0",
                "value": True,
            }
        ],
    }
    applied = apply_policy_to_query(
        query, seamless_graph_fixture, profile="seamless_standard_scenario"
    )
    preds = [a["predicate"] for a in applied["assumptions"]]
    assert "custom_existing_fact" in preds

    conflict_query = {
        "source_foothold": "COMP-X",
        "initial_actor": "COMP-X",
        "authentication_context": "COMP-X",
        "initial_state": {
            "known_identity": ["USER-C0"],
        },
        "target": "COMP-C0",
        "assumptions": [
            {
                "predicate": "network_kdc_reachable",
                "subject": "COMP-X",
                "target": "USER-C0",
                "value": False,
            }
        ],
    }
    with pytest.raises(ValueError, match="conflicting assumption"):
        apply_policy_to_query(
            conflict_query, seamless_graph_fixture, profile="seamless_standard_scenario"
        )

    forbidden_query = {
        "source_foothold": "COMP-X",
        "initial_actor": "COMP-X",
        "authentication_context": "COMP-X",
        "target": "COMP-C0",
        "assumptions": [
            {
                "predicate": "recovery_success",
                "subject": "COMP-X",
                "target": "USER-C0",
                "value": True,
            }
        ],
    }
    with pytest.raises(ValueError, match="forbidden by policy profile"):
        apply_policy_to_query(
            forbidden_query, seamless_graph_fixture, profile="seamless_standard_scenario"
        )


def test_assumption_count_is_bounded_and_query_local() -> None:
    """Verify that on a large graph, candidate edge selection is bounded and query-local (< 200)."""
    from pathlib import Path

    from scripts.research.asrep_inputs import seamless_inputs

    raw_dir = Path(__file__).resolve().parents[1] / "data/raw/SEAMLESS"
    if not raw_dir.is_dir():
        pytest.skip("Manifest-verified private SEAMLESS raw inputs required")
    engine, base, _, _ = seamless_inputs(raw_dir, "test")
    x_id = "S-1-5-21-1271839998-3495686680-2211690266-4095"
    c_id = base["target"]
    query = {
        **base,
        "source_foothold": x_id,
        "initial_actor": x_id,
        "authentication_context": x_id,
        "target": c_id,
    }
    res = resolve_scenario_policy(engine, query, profile="seamless_standard_scenario")
    assert len(res.assumptions) < 200
    assert len(res.assumptions) > 0


def test_decode_ad_group_type_security() -> None:
    """Active Directory groupType decoding correctly checks GROUP_TYPE_SECURITY_ENABLED."""
    from src.engine.semantics.scenario_policy import decode_ad_group_type_security

    # Signed 32-bit security groupTypes
    assert decode_ad_group_type_security(-2147483646) is True
    assert decode_ad_group_type_security(-2147483644) is True
    assert decode_ad_group_type_security(-2147483640) is True

    # Unsigned 32-bit security groupTypes
    assert decode_ad_group_type_security(2147483650) is True
    assert decode_ad_group_type_security(2147483648) is True

    # String representations
    assert decode_ad_group_type_security("0x80000002") is True
    assert decode_ad_group_type_security("-2147483646") is True

    # Distribution groups (security bit not set)
    assert decode_ad_group_type_security(2) is False
    assert decode_ad_group_type_security(4) is False
    assert decode_ad_group_type_security(8) is False
    assert decode_ad_group_type_security("2") is False
    assert decode_ad_group_type_security("0x00000002") is False

    # Missing or invalid
    assert decode_ad_group_type_security(None) is None
    assert decode_ad_group_type_security(True) is None
    assert decode_ad_group_type_security(False) is None
    assert decode_ad_group_type_security("not_a_number") is None


def test_grouptype_decoding_enforced_in_memberof_and_genericall(
    seamless_graph_fixture: dict[str, Any],
) -> None:
    """groupType without security bit is rejected in MemberOf and GenericAll."""
    g = copy.deepcopy(seamless_graph_fixture)
    # Add a group with distribution groupType (2 = global distribution group) and neutral name
    g["nodes"].append(
        {
            "id": "GROUP-DIST-EXPLICIT",
            "kind": "Group",
            "label": "CUSTOM_ANNOUNCEMENTS",
            "groupType": 2,
            "enabled": True,
        }
    )
    g["nodes"].append(
        {
            "id": "GROUP-SEC-EXPLICIT",
            "kind": "Group",
            "label": "CUSTOM_OPERATIONS",
            "groupType": -2147483646,
            "enabled": True,
        }
    )
    g["edges"].extend(
        [
            {
                "id": "EDGE-MEM-DIST",
                "kind": "MemberOf",
                "source": "USER-GINO",
                "target": "GROUP-DIST-EXPLICIT",
            },
            {
                "id": "EDGE-MEM-SEC",
                "kind": "MemberOf",
                "source": "USER-GINO",
                "target": "GROUP-SEC-EXPLICIT",
            },
            {
                "id": "EDGE-GEN-DIST",
                "kind": "GenericAll",
                "source": "USER-GINO",
                "target": "GROUP-DIST-EXPLICIT",
            },
            {
                "id": "EDGE-GEN-SEC",
                "kind": "GenericAll",
                "source": "USER-GINO",
                "target": "GROUP-SEC-EXPLICIT",
            },
        ]
    )
    query = {
        "source_foothold": "COMP-X",
        "initial_actor": "USER-GINO",
        "authentication_context": "COMP-X",
        "target": "GROUP-SEC-EXPLICIT",
    }
    res = resolve_scenario_policy(g, query, profile="seamless_standard_scenario")

    # Security groupType emitted security_group=True
    sec_targets = [f.target for f in res.assumptions if f.predicate == "security_group"]
    assert "GROUP-SEC-EXPLICIT" in sec_targets
    assert "GROUP-DIST-EXPLICIT" not in sec_targets

    # Distribution groupType recorded rejection
    dist_rejections = [
        r for r in res.rejected_assumptions if r.reason == "distribution_group_cannot_default"
    ]
    assert any(r.target == "GROUP-DIST-EXPLICIT" for r in dist_rejections)


def test_gino_assumption_count_is_bounded() -> None:
    """Verify GINO search assumptions are bounded (< 300) without pre-materialization."""
    from pathlib import Path

    from scripts.research.asrep_inputs import seamless_inputs

    raw_dir = Path(__file__).resolve().parents[1] / "data/raw/SEAMLESS"
    if not raw_dir.is_dir():
        pytest.skip("Manifest-verified private SEAMLESS raw inputs required")
    engine, base, _, _ = seamless_inputs(raw_dir, "test")
    gino_id = "S-1-5-21-1271839998-3495686680-2211690266-1103"
    c_id = base["target"]
    query = {
        "source_foothold": "S-1-5-21-1271839998-3495686680-2211690266-4095",
        "initial_actor": gino_id,
        "authentication_context": "S-1-5-21-1271839998-3495686680-2211690266-4095",
        "target": c_id,
        "target_goal": {"target": c_id, "required_state": {"admin_control": [c_id]}},
        "initial_state": {
            "control": [gino_id],
            "usable_identity": [[gino_id, "S-1-5-21-1271839998-3495686680-2211690266-4095"]],
        },
        "budget": {"max_paths": 10, "max_steps": 6, "max_expansions": 5000},
    }
    res = resolve_scenario_policy(engine, query, profile="seamless_standard_scenario")
    # Must be bounded (< 300 assumptions), not 22,956!
    assert len(res.assumptions) < 300
    assert len(res.assumptions) > 0


def test_policy_assumption_resolver_on_demand_cache(
    seamless_graph_fixture: dict[str, Any],
) -> None:
    """PolicyAssumptionResolver provides on-demand bounded mapping lookup."""
    from src.engine.semantics.scenario_policy import PolicyAssumptionResolver

    query = {
        "source_foothold": "COMP-X",
        "initial_actor": "USER-GINO",
        "authentication_context": "COMP-X",
        "target": "COMP-C0",
    }
    resolver = PolicyAssumptionResolver(
        seamless_graph_fixture, query, profile="seamless_standard_scenario", max_cache_size=50
    )

    # Initially empty cache
    assert len(resolver) == 0

    # Look up an existing recognized security group
    key = ("security_group", "USER-GINO", "GROUP-DA")
    fact = resolver[key]
    assert fact.value is True
    assert fact.predicate == "security_group"
    assert len(resolver) == 1
    assert key in resolver

    # Look up distribution group without override: raises KeyError and records rejection
    dist_key = ("security_group", "USER-GINO", "GROUP-DIST1")
    with pytest.raises(KeyError):
        _ = resolver[dist_key]
    assert any(
        r.reason == "distribution_group_cannot_default" for r in resolver.rejected_assumptions
    )

    # Look up non-existent predicate: raises KeyError
    bad_key = ("non_existent_pred", "USER-GINO", "GROUP-DA")
    with pytest.raises(KeyError):
        _ = resolver[bad_key]


def test_policy_assumption_resolver_snapshot_facts_veto(
    seamless_graph_fixture: dict[str, Any],
) -> None:
    """PolicyAssumptionResolver vetoes assumption when snapshot_facts lookup returns False."""
    from unittest.mock import MagicMock

    from src.engine.semantics.scenario_policy import (
        ApplicabilityRule,
        PolicyAssumptionResolver,
        RuleTaxonomy,
        ScenarioPolicyProfile,
    )

    mock_facts = MagicMock()
    mock_facts.snapshot_id = SEAMLESS_SNAPSHOT_ID
    mock_fact_record = MagicMock()
    mock_fact_record.value = False
    mock_facts.lookup.return_value = mock_fact_record

    graph_with_facts = dict(seamless_graph_fixture)
    graph_with_facts["snapshot_facts"] = mock_facts

    test_profile = ScenarioPolicyProfile(
        profile_id="test-facts-profile",
        version="1.0.0",
        bound_snapshot_id=SEAMLESS_SNAPSHOT_ID,
        evaluation_mode="seamless_standard_scenario",
        rules=(
            ApplicabilityRule(
                rule_id="rule-test-preauth",
                predicate="dontreqpreauth",
                taxonomy=RuleTaxonomy.GLOBAL,
                provenance_reference="policy://test",
            ),
        ),
        forbidden_predicates=(),
        description="Test",
    )

    resolver = PolicyAssumptionResolver(
        graph_with_facts,
        query={"initial_actor": "USER-C0", "target": "USER-GINO"},
        profile=test_profile,
    )
    key = ("dontreqpreauth", "USER-C0", "USER-GINO")
    with pytest.raises(KeyError):
        _ = resolver[key]

    vetoed = [r for r in resolver.rejected_assumptions if r.reason == "known_false_veto"]
    assert any(
        r.predicate == "dontreqpreauth" and r.conflicting_origin == "snapshot_facts" for r in vetoed
    )


def test_policy_assumption_resolver_forbidden_predicates_recorded(
    seamless_graph_fixture: dict[str, Any],
) -> None:
    """Forbidden predicate lookups without opt-in record forbidden_to_default rejection."""
    from src.engine.semantics.scenario_policy import PolicyAssumptionResolver

    resolver = PolicyAssumptionResolver(
        seamless_graph_fixture,
        query={"initial_actor": "USER-C0", "target": "USER-GINO"},
        profile="seamless_standard_scenario",
    )
    key = ("recovery_success", "USER-C0", "USER-GINO")
    with pytest.raises(KeyError):
        _ = resolver[key]

    assert any(
        r.predicate == "recovery_success" and r.reason == "forbidden_to_default"
        for r in resolver.rejected_assumptions
    )


def test_policy_assumption_resolver_true_lru_eviction(
    seamless_graph_fixture: dict[str, Any],
) -> None:
    """PolicyAssumptionResolver evicts least recently used items when max_cache_size is exceeded."""
    from src.engine.semantics.scenario_policy import PolicyAssumptionResolver

    resolver = PolicyAssumptionResolver(
        seamless_graph_fixture,
        profile="seamless_standard_scenario",
        max_cache_size=2,
    )

    # Resolve key1 and key2
    key1 = ("security_group", "USER-GINO", "GROUP-DA")
    key2 = ("security_group", "USER-GINO", "GROUP-DU")
    key3 = ("security_group", "USER-GINO", "GROUP-ADM1")

    _ = resolver[key1]
    _ = resolver[key2]
    assert len(resolver) == 2
    assert key1 in resolver._cache
    assert key2 in resolver._cache

    # Access key1 again to make key2 the least recently used
    _ = resolver[key1]

    # Resolve key3: should evict key2 (the LRU), keeping key1 and key3
    _ = resolver[key3]
    assert len(resolver) == 2
    assert key1 in resolver._cache
    assert key3 in resolver._cache
    assert key2 not in resolver._cache


def test_policy_assumption_resolver_no_query_default(
    seamless_graph_fixture: dict[str, Any],
) -> None:
    """PolicyAssumptionResolver can be instantiated without query as in B handoff."""
    from src.engine.semantics.scenario_policy import PolicyAssumptionResolver

    resolver = PolicyAssumptionResolver(
        seamless_graph_fixture,
        profile="seamless_standard_scenario",
    )
    assert resolver.query_dict == {}
    key = ("security_group", "USER-GINO", "GROUP-DA")
    fact = resolver[key]
    assert fact.value is True


def test_policy_assumption_resolver_paired_membership_usable(
    seamless_graph_fixture: dict[str, Any],
) -> None:
    """Overriding security_group automatically generates paired membership_usable fact."""
    from src.engine.semantics.scenario_policy import PolicyAssumptionResolver, PolicyOverride

    override = PolicyOverride(
        predicate="security_group",
        subject="USER-ALEX",
        target="GROUP-DIST1",
        value=True,
        override_type="mail_enabled_security_group",
        rationale="Verified out-of-band as mail-enabled security group",
    )
    resolver = PolicyAssumptionResolver(
        seamless_graph_fixture,
        profile="seamless_standard_scenario",
        overrides=[override],
    )
    sec_fact = resolver[("security_group", "USER-ALEX", "GROUP-DIST1")]
    assert sec_fact.value is True
    assert sec_fact.provenance_reference == "override://seamless/mail_enabled_security_group"

    mem_fact = resolver[("membership_usable", "USER-ALEX", "GROUP-DIST1")]
    assert mem_fact.value is True
    assert mem_fact.predicate == "membership_usable"
    assert mem_fact.provenance_reference == "override://seamless/mail_enabled_security_group"


def test_classify_ad_group_type_authoritative_outranks_naming() -> None:
    """Authoritative groupType/security_enabled always outranks naming heuristics."""
    from src.engine.semantics.scenario_policy import classify_ad_group_type

    # Authoritative security group with distribution naming
    assert (
        classify_ad_group_type({"groupType": -2147483646, "label": "ALL_DISTLIST_USERS"})
        == "security_group"
    )
    assert (
        classify_ad_group_type({"security_enabled": True, "label": "EXCHANGE_DISTRIBUTION_LIST"})
        == "security_group"
    )

    # Authoritative distribution group with security naming
    assert (
        classify_ad_group_type({"groupType": 2, "label": "DOMAIN ADMINS"}) == "distribution_group"
    )
    assert (
        classify_ad_group_type({"security_enabled": False, "label": "ENTERPRISE ADMINS"})
        == "distribution_group"
    )

    # Conservative negative hint from distribution list naming
    assert classify_ad_group_type({"label": "ALL_DISTLIST_USERS"}) == "distribution_group"

    # Issue #290: untyped groups with security group names MUST NOT be authorized purely by name
    assert classify_ad_group_type({"label": "DOMAIN ADMINS"}) == "unrecognized"
    assert classify_ad_group_type({"label": "FOO-SEC-GROUP"}) == "unrecognized"
    assert classify_ad_group_type({"label": "SOME-ADMINGROUP"}) == "unrecognized"
    assert classify_ad_group_type({"label": "CUSTOM_UNCATEGORIZED_GROUP"}) == "unrecognized"

    # Well-known AD security groups authorized via reviewed stable SID/RID identity with provenance
    assert (
        classify_ad_group_type({"id": "S-1-5-21-512", "label": "DOMAIN ADMINS"}) == "security_group"
    )
    assert (
        classify_ad_group_type({"id": "S-1-5-32-544", "label": "ADMINISTRATORS"})
        == "security_group"
    )


def test_authoritative_grouptype_outranks_naming_in_resolver_and_eager(
    seamless_graph_fixture: dict[str, Any],
) -> None:
    """Both eager and lazy resolvers prioritize authoritative groupType over DISTLIST naming."""
    import copy

    from src.engine.semantics.scenario_policy import PolicyAssumptionResolver

    g = copy.deepcopy(seamless_graph_fixture)
    g["nodes"].extend(
        [
            {
                "id": "GROUP-SEC-DISTNAME",
                "kind": "Group",
                "label": "DISTLIST-CRITICAL-INFRA",
                "groupType": -2147483646,
                "enabled": True,
            },
            {
                "id": "GROUP-DIST-SECNAME",
                "kind": "Group",
                "label": "DOMAIN ADMINS ARCHIVE",
                "groupType": 2,
                "enabled": True,
            },
        ]
    )
    g["edges"].extend(
        [
            {
                "id": "EDGE-MEM-1",
                "kind": "MemberOf",
                "source": "USER-GINO",
                "target": "GROUP-SEC-DISTNAME",
            },
            {
                "id": "EDGE-MEM-2",
                "kind": "MemberOf",
                "source": "USER-GINO",
                "target": "GROUP-DIST-SECNAME",
            },
        ]
    )
    query = {
        "source_foothold": "COMP-X",
        "initial_actor": "USER-GINO",
        "authentication_context": "COMP-X",
        "target": "GROUP-SEC-DISTNAME",
    }

    # 1. Eager resolver verification
    eager_res = resolve_scenario_policy(g, query, profile="seamless_standard_scenario")
    sec_targets = [f.target for f in eager_res.assumptions if f.predicate == "security_group"]
    assert "GROUP-SEC-DISTNAME" in sec_targets
    assert "GROUP-DIST-SECNAME" not in sec_targets

    dist_rejections = [
        r.target
        for r in eager_res.rejected_assumptions
        if r.reason == "distribution_group_cannot_default"
    ]
    assert "GROUP-DIST-SECNAME" in dist_rejections
    assert "GROUP-SEC-DISTNAME" not in dist_rejections

    # 2. Lazy resolver verification
    resolver = PolicyAssumptionResolver(g, query, profile="seamless_standard_scenario")
    key_sec = ("security_group", "USER-GINO", "GROUP-SEC-DISTNAME")
    assert key_sec in resolver
    fact = resolver[key_sec]
    assert fact.value is True

    key_dist = ("security_group", "USER-GINO", "GROUP-DIST-SECNAME")
    assert key_dist not in resolver
    with pytest.raises(KeyError):
        _ = resolver[key_dist]
    assert any(
        r.target == "GROUP-DIST-SECNAME" and r.reason == "distribution_group_cannot_default"
        for r in resolver.rejected_assumptions
    )


def test_policy_assumption_resolver_rejects_standard_profile_recovery_override(
    seamless_graph_fixture: dict[str, Any],
) -> None:
    """Standard-profile lazy resolver rejects validly-shaped recovery_opt_in."""
    from src.engine.semantics.scenario_policy import PolicyAssumptionResolver, PolicyOverride

    valid_recovery_ov = PolicyOverride(
        predicate="recovery_success",
        subject="COMP-X",
        target="USER-GINO",
        value=True,
        override_type="recovery_opt_in",
        rationale="Offline hash cracking attack",
        metadata={"method": "hashcat_dictionary", "budget": "24h", "horizon": "24h"},
    )
    resolver = PolicyAssumptionResolver(
        seamless_graph_fixture,
        query={"source_foothold": "COMP-X", "initial_actor": "USER-C0", "target": "USER-GINO"},
        profile="seamless_standard_scenario",
        overrides=[valid_recovery_ov],
    )
    key = ("recovery_success", "COMP-X", "USER-GINO")

    # Lookup must fail with KeyError and __contains__ must be False
    assert key not in resolver
    with pytest.raises(KeyError):
        _ = resolver[key]

    # Rejection must be recorded with forbidden_to_default
    rejections = [
        r
        for r in resolver.rejected_assumptions
        if r.predicate == "recovery_success" and r.target == "USER-GINO"
    ]
    assert len(rejections) == 1
    assert rejections[0].reason == "forbidden_to_default"


def test_policy_assumption_resolver_validates_recovery_metadata_in_what_if(
    seamless_graph_fixture: dict[str, Any],
) -> None:
    """What-if lazy resolver accepts valid recovery_opt_in and rejects malformed ones."""
    from src.engine.semantics.scenario_policy import PolicyAssumptionResolver, PolicyOverride

    # 1. Invalid override_type
    bad_type_ov = PolicyOverride(
        predicate="recovery_success",
        subject="COMP-X",
        target="USER-GINO",
        value=True,
        override_type="custom_type",
        rationale="Invalid type",
        metadata={"method": "hashcat", "budget": "24h"},
    )
    r1 = PolicyAssumptionResolver(
        seamless_graph_fixture,
        profile="exploratory_what_if",
        overrides=[bad_type_ov],
    )
    k1 = ("recovery_success", "COMP-X", "USER-GINO")
    with pytest.raises(KeyError):
        _ = r1[k1]
    assert any(r.reason == "invalid_recovery_override_type" for r in r1.rejected_assumptions)

    # 2. Missing method or budget
    missing_meta_ov = PolicyOverride(
        predicate="recovery_success",
        subject="COMP-X",
        target="USER-GINO",
        value=True,
        override_type="recovery_opt_in",
        rationale="Missing method",
        metadata={"budget": "24h"},
    )
    r2 = PolicyAssumptionResolver(
        seamless_graph_fixture,
        profile="exploratory_what_if",
        overrides=[missing_meta_ov],
    )
    with pytest.raises(KeyError):
        _ = r2[k1]
    assert any(r.reason == "invalid_recovery_opt_in_metadata" for r in r2.rejected_assumptions)

    # 3. Valid recovery_opt_in without horizon: horizon defaults to budget
    valid_ov = PolicyOverride(
        predicate="recovery_success",
        subject="COMP-X",
        target="USER-GINO",
        value=True,
        override_type="recovery_opt_in",
        rationale="Valid opt-in",
        metadata={"method": "hashcat_dictionary", "budget": "48h"},
    )
    r3 = PolicyAssumptionResolver(
        seamless_graph_fixture,
        profile="exploratory_what_if",
        overrides=[valid_ov],
    )
    assert k1 in r3
    fact = r3[k1]
    assert fact.value is True
    assert fact.predicate == "recovery_success"
    assert fact.assumption_metadata.get("method") == "hashcat_dictionary"
    assert fact.assumption_metadata.get("budget") == "48h"
    assert fact.assumption_metadata.get("horizon") == "48h"
    assert fact.provenance_reference == "override://seamless/recovery_opt_in"


def test_policy_assumption_resolver_rejects_forbidden_capability_overrides(
    seamless_graph_fixture: dict[str, Any],
) -> None:
    """Lazy resolver enforces non-negotiable attacker capability boundaries."""
    from src.engine.semantics.scenario_policy import PolicyAssumptionResolver, PolicyOverride

    forbidden_ov = PolicyOverride(
        predicate="control",
        subject="USER-C0",
        target="COMP-DC1",
        value=True,
        override_type="scoped_opt_in",
        rationale="Attempting to force attacker control",
    )
    resolver = PolicyAssumptionResolver(
        seamless_graph_fixture,
        profile="seamless_standard_scenario",
        overrides=[forbidden_ov],
    )
    k = ("control", "USER-C0", "COMP-DC1")
    with pytest.raises(KeyError):
        _ = resolver[k]
    assert any(
        r.reason == "override_violates_non_negotiable_security_boundary"
        for r in resolver.rejected_assumptions
    )


def test_policy_assumption_resolver_cross_subject_isolation(
    seamless_graph_fixture: dict[str, Any],
) -> None:
    """Overrides on distribution groups are strictly scoped to the declared subject."""
    import copy

    from src.engine.semantics.scenario_policy import PolicyAssumptionResolver, PolicyOverride

    g = copy.deepcopy(seamless_graph_fixture)
    g["nodes"].append(
        {
            "id": "GROUP-DIST-SCOPED",
            "kind": "Group",
            "label": "HO-170-DISTLIST1",
            "groupType": 2,
            "enabled": True,
        }
    )
    ov = PolicyOverride(
        predicate="security_group",
        subject="USER-ALICE",
        target="GROUP-DIST-SCOPED",
        value=True,
        override_type="scoped_opt_in",
        rationale="Authorized override for Alice only",
    )
    resolver = PolicyAssumptionResolver(
        g,
        profile="exploratory_what_if",
        overrides=[ov],
    )

    # 1. Alice is granted security_group and membership_usable under override
    k_alice_sec = ("security_group", "USER-ALICE", "GROUP-DIST-SCOPED")
    k_alice_mem = ("membership_usable", "USER-ALICE", "GROUP-DIST-SCOPED")
    assert k_alice_sec in resolver
    assert resolver[k_alice_sec].value is True
    assert k_alice_mem in resolver
    assert resolver[k_alice_mem].value is True

    # 2. Bob was not overridden: lookup must fail with KeyError and reject as distribution group
    k_bob_sec = ("security_group", "USER-BOB", "GROUP-DIST-SCOPED")
    k_bob_mem = ("membership_usable", "USER-BOB", "GROUP-DIST-SCOPED")
    assert k_bob_sec not in resolver
    with pytest.raises(KeyError):
        _ = resolver[k_bob_sec]
    assert k_bob_mem not in resolver
    with pytest.raises(KeyError):
        _ = resolver[k_bob_mem]

    bob_rejections = [
        r
        for r in resolver.rejected_assumptions
        if r.subject == "USER-BOB" and r.target == "GROUP-DIST-SCOPED"
    ]
    assert len(bob_rejections) == 2
    assert all(r.reason == "distribution_group_cannot_default" for r in bob_rejections)


def test_policy_assumption_resolver_tracks_applied_overrides(
    seamless_graph_fixture: dict[str, Any],
) -> None:
    """Resolver accurately exposes applied user overrides via applied_overrides property."""
    from src.engine.semantics.scenario_policy import PolicyAssumptionResolver, PolicyOverride

    ov = PolicyOverride(
        predicate="network_kdc_reachable",
        subject="COMP-X",
        target="COMP-DC1",
        value=True,
        override_type="scoped_opt_in",
        rationale="Scoped reachability override",
    )
    resolver = PolicyAssumptionResolver(
        seamless_graph_fixture,
        profile="seamless_standard_scenario",
        overrides=[ov],
    )
    assert len(resolver.applied_overrides) == 0

    # Before lookup, applied_overrides is empty
    key = ("network_kdc_reachable", "COMP-X", "COMP-DC1")
    fact = resolver[key]
    assert fact.value is True

    # After lookup, applied_overrides contains ov
    assert len(resolver.applied_overrides) == 1
    assert resolver.applied_overrides[0] == ov


def test_resolvers_accept_none_overrides(
    seamless_graph_fixture: dict[str, Any],
) -> None:
    """Both eager and lazy resolvers accept overrides=None without raising TypeError."""
    from src.engine.semantics.scenario_policy import (
        PolicyAssumptionResolver,
        apply_policy_to_query,
        resolve_scenario_policy,
    )

    query = {
        "source_foothold": "COMP-X",
        "initial_actor": "USER-C0",
        "target": "USER-GINO",
    }
    # 1. resolve_scenario_policy
    eager_res = resolve_scenario_policy(
        seamless_graph_fixture, query, profile="seamless_standard_scenario", overrides=None
    )
    assert eager_res.evaluation_mode == "seamless_standard_scenario"

    # 2. apply_policy_to_query
    q_dict = apply_policy_to_query(
        query, seamless_graph_fixture, profile="seamless_standard_scenario", overrides=None
    )
    assert q_dict["evaluation_mode"] == "scenario"

    # 3. PolicyAssumptionResolver
    resolver = PolicyAssumptionResolver(
        seamless_graph_fixture, query=query, profile="seamless_standard_scenario", overrides=None
    )
    assert len(resolver.applied_overrides) == 0


def test_classify_ad_group_type_properties_and_name_support() -> None:
    """Group classification inspects name, properties dict, and parses boolean strings."""
    from src.engine.semantics.scenario_policy import classify_ad_group_type

    # 1. Group with name attribute instead of label
    node_name_dist = {
        "id": "S-1-5-21-3610",
        "name": "JE-MAR-DISTLIST1@SEAMLESS.INTERNAL",
        "kind": "Group",
    }
    assert classify_ad_group_type(node_name_dist) == "distribution_group"

    node_name_sec = {
        "id": "S-1-5-21-512",
        "name": "DOMAIN ADMINS@SEAMLESS.INTERNAL",
        "kind": "Group",
    }
    assert classify_ad_group_type(node_name_sec) == "security_group"

    # 2. Properties nested dict with lowercase grouptype
    node_nested = {
        "id": "GROUP-NESTED",
        "kind": "Group",
        "properties": {
            "name": "CUSTOM-GROUP",
            "grouptype": -2147483646,
        },
    }
    assert classify_ad_group_type(node_nested) == "security_group"

    # 3. String boolean security_enabled
    node_str_bool = {
        "id": "GROUP-STR-BOOL",
        "kind": "Group",
        "security_enabled": "true",
        "label": "CUSTOM-DISTLIST-NAME",
    }
    # Authoritative security_enabled="true" outranks DISTLIST naming
    assert classify_ad_group_type(node_str_bool) == "security_group"

    node_str_false = {
        "id": "GROUP-STR-FALSE",
        "kind": "Group",
        "security_enabled": "false",
        "label": "DOMAIN ADMINS BACKUP",
    }
    # Authoritative security_enabled="false" outranks DOMAIN ADMINS naming
    assert classify_ad_group_type(node_str_false) == "distribution_group"


def test_untyped_group_name_heuristics_do_not_authorize_security_group() -> None:
    """Issue #290: untyped groups named FOO-SEC-GROUP / SOME-ADMINGROUP must stay unresolved.

    Naming heuristics cannot independently authorize security_group=True.
    """
    from src.engine.semantics.scenario_policy import classify_ad_group_type

    # Untyped groups with security-suggestive naming must NOT be authorized
    assert (
        classify_ad_group_type({"id": "G1", "label": "FOO-SEC-GROUP", "kind": "Group"})
        == "unrecognized"
    )
    assert (
        classify_ad_group_type({"id": "G2", "name": "SOME-ADMINGROUP", "kind": "Group"})
        == "unrecognized"
    )
    assert (
        classify_ad_group_type({"id": "G3", "label": "DOMAIN ADMINS", "kind": "Group"})
        == "unrecognized"
    )
    assert (
        classify_ad_group_type({"id": "G4", "label": "DOMAIN USERS", "kind": "Group"})
        == "unrecognized"
    )
    # Untyped with arbitrary RID (not well-known) also stays unrecognized
    assert (
        classify_ad_group_type(
            {"id": "S-1-5-21-1271839998-3495686680-2211690266-4019", "name": "KE-666-ADMINGROUP1"}
        )
        == "unrecognized"
    )

    # Conservative negative hint from distribution list naming is preserved
    assert (
        classify_ad_group_type({"id": "G5", "label": "CORP-DISTLIST1", "kind": "Group"})
        == "distribution_group"
    )


def test_well_known_security_group_explicit_identity_provenance() -> None:
    """Issue #290: well-known AD security groups require explicit identity with provenance."""
    from src.engine.semantics.scenario_policy import (
        classify_ad_group_type,
        lookup_well_known_security_group_identity,
    )

    # Builtin Administrators (MS-DTYP 2.4.2.4)
    prov_admin = lookup_well_known_security_group_identity({"id": "S-1-5-32-544"})
    assert prov_admin is not None
    assert "Administrators" in prov_admin
    assert classify_ad_group_type({"id": "S-1-5-32-544"}) == "security_group"

    # Domain Admins RID 512 (MS-SAMR 2.2.1.1.5)
    node_da = {
        "id": "S-1-5-21-1271839998-3495686680-2211690266-512",
        "name": "DOMAIN ADMINS@SEAMLESS.INTERNAL",
    }
    prov_da = lookup_well_known_security_group_identity(node_da)
    assert prov_da is not None
    assert "Domain Admins" in prov_da
    assert classify_ad_group_type(node_da) == "security_group"

    # Domain Users RID 513 (MS-SAMR 2.2.1.1.5)
    node_du = {
        "id": "S-1-5-21-1271839998-3495686680-2211690266-513",
        "name": "DOMAIN USERS@SEAMLESS.INTERNAL",
    }
    prov_du = lookup_well_known_security_group_identity(node_du)
    assert prov_du is not None
    assert "Domain Users" in prov_du
    assert classify_ad_group_type(node_du) == "security_group"

    # Authenticated Users (MS-DTYP 2.4.2.4)
    node_auth = {"objectsid": "S-1-5-11", "label": "AUTHENTICATED USERS"}
    prov_auth = lookup_well_known_security_group_identity(node_auth)
    assert prov_auth is not None
    assert "Authenticated Users" in prov_auth
    assert classify_ad_group_type(node_auth) == "security_group"

    # Numeric RID property
    node_rid = {"id": "CUSTOM-RID-NODE", "rid": 512}
    prov_rid = lookup_well_known_security_group_identity(node_rid)
    assert prov_rid is not None
    assert "Domain Admins" in prov_rid
    assert classify_ad_group_type(node_rid) == "security_group"

    # Non-well-known RID returns None
    node_non_wk = {"id": "CUSTOM-RID-NODE", "rid": 4019}
    assert lookup_well_known_security_group_identity(node_non_wk) is None
    assert classify_ad_group_type(node_non_wk) == "unrecognized"


def test_evidence_only_helper_metadata_strips_existing_assumptions(
    seamless_graph_fixture: dict[str, Any],
) -> None:
    """apply_policy_to_query(profile='evidence_only') strips assumptions and exposes rejections."""
    query = {
        "source_foothold": "COMP-WS1",
        "initial_actor": "USER-C0",
        "authentication_context": "USER-C0",
        "target": "COMP-DC1",
        "assumptions": [
            {
                "predicate": "custom_prior_assumption",
                "subject": "COMP-WS1",
                "target": "COMP-DC1",
                "value": True,
            },
            {
                "predicate": "another_prior_assumption",
                "subject": "USER-C0",
                "target": "GROUP-DU",
                "value": True,
            },
        ],
    }

    compiled = apply_policy_to_query(query, seamless_graph_fixture, profile="evidence_only")

    # Under evidence_only, assumptions must be strictly stripped
    assert compiled["assumptions"] == []
    meta = compiled["scenario_policy_metadata"]
    assert meta["assumptions_count"] == 0
    assert meta["policy_assumptions_count"] == 0
    assert meta["evaluation_mode"] == "evidence_only"

    # The existing assumptions must be explicitly reported as rejected
    assert meta["rejected_count"] == 2
    rej_reasons = [r["reason"] for r in meta["rejected_assumptions"]]
    assert all(r == "profile_evidence_only_rejects_all_assumptions" for r in rej_reasons)


def test_resolver_and_eager_untyped_admingroup_stays_unresolved(
    seamless_graph_fixture: dict[str, Any],
) -> None:
    """Untyped group like SOME-ADMINGROUP stays unresolved in eager and lazy resolvers."""
    import copy

    from src.engine.semantics.scenario_policy import (
        PolicyAssumptionResolver,
        resolve_scenario_policy,
    )

    g = copy.deepcopy(seamless_graph_fixture)
    g["nodes"].append(
        {
            "id": "GROUP-UNTYPED-ADM",
            "kind": "Group",
            "label": "SOME-ADMINGROUP",
        }
    )
    g["edges"].append(
        {
            "id": "e_test_untyped",
            "source": "USER-C0",
            "target": "GROUP-UNTYPED-ADM",
            "kind": "MemberOf",
        }
    )

    query = {
        "initial_actor": "USER-C0",
        "target": "COMP-DC1",
        "authentication_context": "USER-C0",
        "initial_state": {
            "control": ["USER-C0"],
            "usable_identity": [["USER-C0", "USER-C0"]],
        },
        "target_goal": {"target": "COMP-DC1", "required_state": {"admin_control": ["COMP-DC1"]}},
    }

    # Eager resolution: no security_group fact generated for untyped group
    eager_res = resolve_scenario_policy(g, query, profile="seamless_standard_scenario")
    untyped_facts = [a for a in eager_res.assumptions if a.target == "GROUP-UNTYPED-ADM"]
    assert untyped_facts == []
    assert any(
        d.get("action") == "unrecognized_group_detected"
        and d.get("group_id") == "GROUP-UNTYPED-ADM"
        for d in eager_res.diagnostics
    )

    # Lazy resolver: KeyError / unresolved for untyped group
    resolver = PolicyAssumptionResolver(g, profile="seamless_standard_scenario")
    key = ("security_group", "USER-C0", "GROUP-UNTYPED-ADM")
    assert key not in resolver
    with pytest.raises(KeyError):
        _ = resolver[key]


def test_omitted_profile_defaults_to_evidence_only(
    seamless_graph_fixture: dict[str, Any],
) -> None:
    """All policy entry points default safely to evidence_only when profile is omitted."""
    from src.engine.semantics.scenario_policy import (
        PolicyAssumptionResolver,
        apply_policy_to_query,
        resolve_scenario_policy,
    )

    query = {
        "source_foothold": "COMP-X",
        "initial_actor": "USER-C0",
        "target": "COMP-WS1",
    }

    # 1. resolve_scenario_policy defaults to evidence_only with 0 assumptions
    res = resolve_scenario_policy(seamless_graph_fixture, query)
    assert res.evaluation_mode == "evidence_only"
    assert len(res.assumptions) == 0
    assert res.audit_summary["assumptions_generated"] == 0

    # 2. apply_policy_to_query defaults to evidence_only with 0 assumptions
    compiled = apply_policy_to_query(query, seamless_graph_fixture)
    assert compiled["evaluation_mode"] == "evidence_only"
    assert len(compiled["assumptions"]) == 0
    assert compiled["scenario_policy_metadata"]["assumptions_count"] == 0
    assert compiled["scenario_policy_metadata"]["evaluation_mode"] == "evidence_only"

    # 3. PolicyAssumptionResolver defaults to evidence_only (resolves nothing)
    resolver = PolicyAssumptionResolver(seamless_graph_fixture, query=query)
    assert resolver.profile.evaluation_mode == "evidence_only"
    assert len(resolver) == 0
    key = ("admin_channel", "USER-C0", "COMP-WS1")
    assert key not in resolver
    with pytest.raises(KeyError):
        _ = resolver[key]


def test_evidence_only_records_rejected_overrides(
    seamless_graph_fixture: dict[str, Any],
) -> None:
    """Explicit overrides provided under evidence_only are recorded in rejected_assumptions."""
    from src.engine.semantics.scenario_policy import (
        PolicyAssumptionResolver,
        PolicyOverride,
        resolve_scenario_policy,
    )

    query = {
        "source_foothold": "COMP-X",
        "initial_actor": "USER-C0",
        "target": "COMP-WS1",
    }
    ov = PolicyOverride(
        predicate="network_kdc_reachable",
        subject="COMP-X",
        target="COMP-DC1",
        value=True,
        override_type="scoped_opt_in",
        rationale="Scoped reachability override in evidence-only test",
    )

    # 1. Eager resolver with omitted profile (defaults to evidence_only)
    res_omitted = resolve_scenario_policy(seamless_graph_fixture, query, overrides=[ov])
    assert res_omitted.evaluation_mode == "evidence_only"
    assert len(res_omitted.assumptions) == 0
    assert len(res_omitted.rejected_assumptions) == 1
    rej = res_omitted.rejected_assumptions[0]
    assert rej.predicate == "network_kdc_reachable"
    assert rej.reason == "profile_evidence_only_rejects_all_overrides"

    # 2. Eager resolver with explicit evidence_only
    res_explicit = resolve_scenario_policy(
        seamless_graph_fixture, query, profile="evidence_only", overrides=[ov]
    )
    assert len(res_explicit.rejected_assumptions) == 1
    assert (
        res_explicit.rejected_assumptions[0].reason == "profile_evidence_only_rejects_all_overrides"
    )

    # 3. Lazy resolver with omitted profile
    resolver = PolicyAssumptionResolver(seamless_graph_fixture, query=query, overrides=[ov])
    assert len(resolver.rejected_assumptions) == 1
    assert resolver.rejected_assumptions[0].reason == "profile_evidence_only_rejects_all_overrides"


def test_security_group_runtime_fact_carries_strict_identity_provenance(
    seamless_graph_fixture: dict[str, Any],
) -> None:
    """security_group RuntimeFacts carry strict classification_basis and identity_provenance."""
    import copy

    from src.engine.semantics.scenario_policy import (
        PolicyAssumptionResolver,
        resolve_scenario_policy,
    )

    g = copy.deepcopy(seamless_graph_fixture)
    # Add a group with authoritative groupType bitmask
    g["nodes"].append(
        {
            "id": "GROUP-AUTH-GT",
            "kind": "Group",
            "label": "SEC-ENG-TEAM",
            "groupType": -2147483646,  # 0x80000002
            "enabled": True,
        }
    )
    # Add a group matching reviewed well-known SID
    g["nodes"].append(
        {
            "id": "GROUP-WK-SID",
            "kind": "Group",
            "label": "ADMINISTRATORS",
            "objectsid": "S-1-5-32-544",
            "enabled": True,
        }
    )
    g["edges"].extend(
        [
            {"id": "e_auth_gt", "source": "USER-C0", "target": "GROUP-AUTH-GT", "kind": "MemberOf"},
            {"id": "e_wk_sid", "source": "USER-C0", "target": "GROUP-WK-SID", "kind": "MemberOf"},
        ]
    )

    query = {
        "initial_actor": "USER-C0",
        "target": "COMP-WS1",
        "authentication_context": "USER-C0",
    }

    # 1. Eager resolver
    res = resolve_scenario_policy(g, query, profile="seamless_standard_scenario")
    gt_facts = [
        a
        for a in res.assumptions
        if a.target == "GROUP-AUTH-GT" and a.predicate == "security_group"
    ]
    wk_facts = [
        a for a in res.assumptions if a.target == "GROUP-WK-SID" and a.predicate == "security_group"
    ]
    prop_facts = [
        a for a in res.assumptions if a.target == "GROUP-DU" and a.predicate == "security_group"
    ]

    assert len(gt_facts) > 0
    assert (
        gt_facts[0].assumption_metadata["classification_basis"]
        == "authoritative_grouptype_security_bit"
    )
    assert "0x80000000" in gt_facts[0].assumption_metadata["identity_provenance"]

    assert len(wk_facts) > 0
    assert (
        wk_facts[0].assumption_metadata["classification_basis"] == "well_known_identity_allowlist"
    )
    assert "S-1-5-32-544" in wk_facts[0].assumption_metadata["identity_provenance"]

    assert len(prop_facts) > 0
    assert (
        prop_facts[0].assumption_metadata["classification_basis"]
        == "authoritative_security_enabled_property"
    )

    # 2. Lazy resolver
    resolver = PolicyAssumptionResolver(g, profile="seamless_standard_scenario")
    lazy_gt = resolver[("security_group", "USER-C0", "GROUP-AUTH-GT")]
    lazy_wk = resolver[("security_group", "USER-C0", "GROUP-WK-SID")]

    assert (
        lazy_gt.assumption_metadata["classification_basis"]
        == "authoritative_grouptype_security_bit"
    )
    assert lazy_wk.assumption_metadata["classification_basis"] == "well_known_identity_allowlist"
    assert "S-1-5-32-544" in lazy_wk.assumption_metadata["identity_provenance"]
