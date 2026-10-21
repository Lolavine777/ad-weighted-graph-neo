"""Shared Week 3 scopes and the strict structural/capability boundary."""

import json
from typing import get_args

import pytest

from scripts.research.week3_engine_acceptance import DEFAULT_RELEASE, context_for
from scripts.research.week3_semantic_bridge_probe import PLAN, ROOT, overlay
from src.engine.semantics import AttackState, RuntimeContext
from src.engine.semantics.models import (
    CAPABILITY_RELATIONSHIP_KINDS,
    STRUCTURAL_RELATIONSHIP_KINDS,
    CapabilityRelationship,
    FactOrigin,
    RelationshipKind,
    StructuralRelationship,
)
from src.engine.semantics.week3 import runtime_for_projection


@pytest.mark.parametrize(
    "bucket,value,layer,override,origin,scope",
    [
        ("assumed_facts", True, 3, {}, FactOrigin.DECLARED_ASSUMPTION, "72h"),
        ("observed_facts", True, 1, {}, FactOrigin.OBSERVED_EVIDENCE, None),
        ("observed_facts", True, 2, {}, FactOrigin.OBSERVED_EVIDENCE, None),
        ("false_facts", False, 3, {}, FactOrigin.BLOCKED_EVIDENCE, "scenario"),
        ("unknown_facts", None, 3, {}, FactOrigin.UNKNOWN, "scenario"),
        ("assumed_facts", True, 3, {"truth_value": False}, FactOrigin.BLOCKED_EVIDENCE, "scenario"),
        ("assumed_facts", True, 3, {"truth_value": None}, FactOrigin.UNKNOWN, "scenario"),
        (
            "false_facts",
            False,
            3,
            {"truth_value": True, "origin": "declared_assumption"},
            FactOrigin.BLOCKED_EVIDENCE,
            "scenario",
        ),
    ],
)
def test_probe_and_harness_facts_have_identical_scope_policy(
    bucket, value, layer, override, origin, scope
):
    query = {
        "query_metadata": {"scenario_id": "scenario", "horizon": "72h"},
        "facts_ledger": {
            bucket: [
                {
                    "predicate": "gate",
                    "truth_value": value,
                    "layer": layer,
                    "rationale": "reviewed basis",
                }
            ]
        },
    }
    source = {
        "actor": "actor",
        "authentication_context": "dc",
        "runtime_fact_bindings": [
            {
                "release_predicate": "gate",
                "semantic_predicate": "network_kdc_reachable",
                "subject": "user",
                "target": "dc",
            }
        ],
    }
    case = (
        {"runtime_fact_overrides": [{"release_predicate": "gate", **override}]} if override else {}
    )
    harness = context_for(query, source, case)
    _, bridge = runtime_for_projection(query, source, case)
    assert dict(harness.facts) == dict(bridge.facts)
    fact = next(iter(bridge.facts.values()))
    assert fact.origin is origin and fact.scope == scope
    assert fact.value is (override.get("truth_value", value) if value is not False else False)
    assert bridge.authentication_context == "dc"


def test_structural_taxonomy_remains_exactly_eight_kinds():
    expected = {
        "MemberOf",
        "AdminTo",
        "GenericAll",
        "WriteDacl",
        "ForceChangePassword",
        "CanRDP",
        "CanPSRemote",
        "HasSession",
    }
    assert set(get_args(RelationshipKind.__value__)) == expected
    assert STRUCTURAL_RELATIONSHIP_KINDS == expected
    assert CAPABILITY_RELATIONSHIP_KINDS == {
        "AuthenticationControl",
        "DeclaredHostAdmin",
        "ASRepTarget",
        "ASRepMaterial",
        "RoastTarget",
        "TicketMaterial",
        "RecoveredSecret",
        "RBCDReset",
        "RBCDPrepare",
        "RBCDConfigure",
        "RBCDDelegate",
        "RBCDAsset",
    }
    assert not STRUCTURAL_RELATIONSHIP_KINDS & CAPABILITY_RELATIONSHIP_KINDS


@pytest.mark.parametrize(
    "kind",
    [
        "AuthenticationControl",
        "DeclaredHostAdmin",
        "ASRepTarget",
        "ASRepMaterial",
        "RoastTarget",
        "TicketMaterial",
        "RecoveredSecret",
        "RBCDReset",
        "RBCDPrepare",
        "RBCDConfigure",
        "RBCDDelegate",
        "RBCDAsset",
    ],
)
def test_capability_cannot_be_constructed_as_structural(kind):
    with pytest.raises(ValueError, match="invalid structural relationship kind"):
        StructuralRelationship("source", kind, "target")


@pytest.mark.parametrize("field", ["permission", "relationship_added", "withheld_relationships"])
@pytest.mark.parametrize(
    "kind",
    [
        "AuthenticationControl",
        "DeclaredHostAdmin",
        "ASRepTarget",
        "ASRepMaterial",
        "RoastTarget",
        "TicketMaterial",
        "RecoveredSecret",
        "RBCDReset",
        "RBCDPrepare",
        "RBCDConfigure",
        "RBCDDelegate",
        "RBCDAsset",
    ],
)
def test_capability_cannot_enter_structural_state_or_evidence(field, kind):
    capability = CapabilityRelationship("source", kind, "target")
    constructor = RuntimeContext if field == "withheld_relationships" else AttackState
    with pytest.raises(ValueError, match="requires structural relationships"):
        constructor(**{field: {capability}})


def test_structural_relation_cannot_be_capability_trigger():
    with pytest.raises(ValueError, match="invalid capability relationship kind"):
        CapabilityRelationship("source", "MemberOf", "target")


@pytest.mark.parametrize(
    "case",
    json.loads(
        (ROOT / "tests/fixtures/ranking/week3_acceptance_cases.json").read_text(encoding="utf-8")
    )["cases"],
    ids=lambda case: case["case_id"],
)
def test_actual_release_cases_keep_harness_and_bridge_scope_parity(case):
    release = json.loads(DEFAULT_RELEASE.read_text(encoding="utf-8"))
    plan = json.loads(PLAN.read_text(encoding="utf-8"))
    source = plan["sources"][case["source"]]
    config = plan["cases"][case["case_id"]]
    query = overlay(release["query_projections"][case["source"]], case["overlay"])["query"]
    _, bridge = runtime_for_projection(query, source, config)
    harness = context_for(query, source, config)
    assert dict(harness.facts) == dict(bridge.facts)
    for fact in bridge.facts.values():
        if fact.origin is FactOrigin.DECLARED_ASSUMPTION:
            assert fact.scope == query["query_metadata"]["horizon"]
        elif fact.origin in (FactOrigin.BLOCKED_EVIDENCE, FactOrigin.UNKNOWN):
            assert fact.scope == query["query_metadata"]["scenario_id"]
        else:
            assert fact.scope is None
