"""Tests for target impact provider and reviewed equivalence registry (Issue #249, parent #245).

Verifies:
1. Exact asset/event reuse (reviewed packet match precedence).
2. Reviewed equivalent-event reuse (positive cases for #243 admin_control_c0,
   admin_control_seamless_dc, terminal_compromise).
3. Canonical validator and PathRankingEngine acceptance.
4. Fail-closed refusal integrity for negative cases:
   - Same asset different consequence refusal.
   - Different asset refusal.
   - Stale and out-of-scope refusal (snapshot, boundary, horizon, scenario).
   - Conflicting equivalence mappings.
   - Unreviewed mapping status refusal.
   - No unreviewed transitive equivalence.
   - Ambiguous/directional reverse query refusal.
   - Forbidden derivation from Domain Admin group membership.
5. Deterministic audit and provenance output.
6. Multi-path risk comparison and Pareto ranking under reused impact.
7. Week 3 baseline regression preservation.
"""

from __future__ import annotations

import copy
import json
import os
from fractions import Fraction
from pathlib import Path
from typing import Any

import pytest

from src.engine.ranking import (
    PathRankingEngine,
    RankingValidationError,
    validate_candidate_envelopes,
    validate_target_impact_assessments,
)
from src.engine.ranking.resolver import (
    BasisClassification,
    ReasonCode,
    ResolutionResult,
    ResolverDisposition,
    ReviewedEquivalenceImpactProvider,
    generate_rating_lookup_key_i,
    load_canonical_impact_equivalence_registry,
)
from src.engine.ranking.resolver import (
    RatingResolver as ContractRatingResolver,
)

ROOT = Path(__file__).resolve().parents[1]
WEEK3_RELEASE_PATH = ROOT / "docs/research/ratings/week3-closeout/reviewed-release.json"
EQUIVALENCE_REGISTRY_PATH = ROOT / "docs/research/ratings/week4/impact-equivalence-registry.json"

DC_ASSET_ID = "S-1-5-21-1271839998-3495686680-2211690266-1000"
WORKSTATION_ASSET_ID = "10000000-0000-4000-8000-000000000003"
SEAMLESS_SNAPSHOT_ID = "sha256:e0601d763eeea285d268ec9e468d321c50c9d7faba53c8e7442a2fcc4159c812"
FOOTHOLD_SID = "S-1-5-21-1271839998-3495686680-2211690266-4131"
SEAMLESS_SCENARIO_ID = "scenario-seamless-host-to-dc"
DUMMY_EDGE = "sha256:" + "1" * 64


def load_week3_release() -> dict[str, Any]:
    """Load canonical Week 3 reviewed release."""
    return json.loads(WEEK3_RELEASE_PATH.read_text(encoding="utf-8"))


def accepted_test_registry():
    """Simulate B acceptance for mechanism tests, never certify production data."""
    registry = copy.deepcopy(load_canonical_impact_equivalence_registry())
    registry.update(
        status="reviewed",
        evidence_class=BasisClassification.SYNTHETIC_TEST_ONLY.value,
        review_reference="tests/test_rating_resolver_impact_equivalence.py#accepted_test_registry",
    )
    for mapping in registry["mappings"]:
        mapping.update(
            status="reviewed",
            evidence_class=BasisClassification.SYNTHETIC_TEST_ONLY.value,
            review_reference=registry["review_reference"],
        )
    return registry


def impact_test_resolver(**kwargs):
    if "impact_equivalence_registry" not in kwargs:
        providers = list(kwargs.pop("impact_providers", []))
        providers.insert(
            0,
            ReviewedEquivalenceImpactProvider(
                accepted_test_registry(), source_packet=load_week3_release()
            ),
        )
        kwargs["impact_providers"] = providers
    return ContractRatingResolver(**kwargs)


def build_dc_scope(
    *,
    success_event: str = "admin_control_c0",
    scenario_id: str = SEAMLESS_SCENARIO_ID,
    snapshot_id: str = SEAMLESS_SNAPSHOT_ID,
    work_boundary: str = "intra_forest",
    horizon: str = "24h",
    target_asset_id: str = DC_ASSET_ID,
    **overrides: Any,
) -> dict[str, Any]:
    """Build standardized test query scope targeting BADBLOOD DC."""
    base = {
        "query_id": "query-seamless-host-to-dc-v1",
        "scenario_id": scenario_id,
        "scenario_version": "1.1.0",
        "snapshot_id": snapshot_id,
        "foothold_node_id": FOOTHOLD_SID,
        "work_boundary": work_boundary,
        "horizon": horizon,
        "active_work_budget": 6,
        "evaluation_mode": "scenario",
        "target_goal": {
            "goal_id": f"goal_{success_event}",
            "description": f"Goal for {success_event}",
            "target_asset_id": target_asset_id,
            "success_event": success_event,
            "required_predicates": ["admin_control_badblood"],
        },
        "facts_ledger": {
            "predicate_layers": {
                "actor_controlled_lidia": 3,
                "admin_control_badblood": 3,
            },
            "observed_facts": [
                {
                    "predicate": "actor_controlled_lidia",
                    "layer": 3,
                    "truth_value": True,
                    "provenance_reference": "test:fact:lidia",
                }
            ],
        },
    }
    base.update(overrides)
    return base


def declared_dc_step(**overrides: Any) -> dict[str, Any]:
    """Build transition step targeting DC01."""
    base = {
        "technique_id": "obtain_admin_execution_on_host",
        "actor": FOOTHOLD_SID,
        "target": DC_ASSET_ID,
        "edge_id": DUMMY_EDGE,
        "provenance": ["synthetic://test/edge"],
        "requires": ["actor_controlled_lidia"],
        "adds": ["admin_control_badblood"],
    }
    base.update(overrides)
    return base


class SyntheticCPRatings:
    """Synthetic provider supplying C and P for testing I isolation."""

    name = "synthetic_cp_provider"
    provider_version = "1.0.0"

    def resolve_effort(self, key: Any, record: Any, scope: Any) -> ResolutionResult:
        return ResolutionResult(
            disposition=ResolverDisposition.RATED,
            value=2,
            reason_code=ReasonCode.REVIEWED_PACKET_MATCH,
            provider_name=self.name,
            provider_version=self.provider_version,
            basis_category=BasisClassification.SYNTHETIC_TEST_ONLY,
            rubric_scores={"t1": 1, "t2": 3, "computed_cost": 2},
        )

    def resolve_likelihood(
        self, key: Any, prefix: Any, outcome: Any, scope: Any
    ) -> ResolutionResult:
        q = Fraction(3, 4)
        return ResolutionResult(
            disposition=ResolverDisposition.RATED,
            value=(q, q),
            reason_code=ReasonCode.REVIEWED_PACKET_MATCH,
            provider_name=self.name,
            provider_version=self.provider_version,
            basis_category=BasisClassification.SYNTHETIC_TEST_ONLY,
        )


# ===========================================================================
# 1. Registry Loading and Validation Tests
# ===========================================================================


def test_canonical_registry_loads_and_validates():
    """Verify canonical impact equivalence registry loads with correct schema and contents."""
    reg = load_canonical_impact_equivalence_registry()
    assert reg["registry_id"] == "impact-equivalence-registry-week4"
    assert reg["version"] == "1.0.0"
    assert reg["status"] == "proposed_pending_b_review"
    assert reg["evidence_class"] == "scenario_assumption"
    assert len(reg["mappings"]) == 4

    mapping_ids = {m["mapping_id"] for m in reg["mappings"]}
    assert mapping_ids == {
        "eq-seamless-dc-admin-control-001",
        "eq-seamless-dc-admin-control-002",
        "eq-seamless-dc-admin-control-003",
        "eq-seamless-frozen-admin-execution-004",
    }

    for m in reg["mappings"]:
        assert m["target_asset_id"] == DC_ASSET_ID
        assert m["status"] == "proposed_pending_b_review"
        assert m["consequence_rating"] == "High"
        assert m["directionality"] in ("symmetric", "directional")
        assert m["source_event"] == "terminal_compromise_seamless_dc"
        assert m["review_reference"] == "docs/research/ratings/week4/impact-equivalence-decision.md"


def test_registry_loading_fails_on_missing_file(tmp_path: Path):
    """Verify loading fails fast with RankingValidationError when file is missing."""
    missing = tmp_path / "nonexistent.json"
    with pytest.raises(RankingValidationError, match="not found"):
        load_canonical_impact_equivalence_registry(missing)


def test_registry_loading_fails_on_malformed_json(tmp_path: Path):
    """Verify loading fails fast on corrupted JSON."""
    bad_json = tmp_path / "bad.json"
    bad_json.write_text("{invalid json", encoding="utf-8")
    with pytest.raises(RankingValidationError, match="Failed to parse"):
        load_canonical_impact_equivalence_registry(bad_json)


def test_registry_loading_fails_on_missing_required_fields(tmp_path: Path):
    """Verify schema validation enforces required fields on mappings."""
    bad_reg = tmp_path / "bad_reg.json"
    bad_reg.write_text(
        json.dumps(
            {
                "mappings": [
                    {
                        "mapping_id": "test-001",
                        "target_asset_id": DC_ASSET_ID,
                        # missing source_event, destination_event, etc.
                        "status": "reviewed",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(RankingValidationError, match="missing required field"):
        load_canonical_impact_equivalence_registry(bad_reg)


def test_registry_loading_fails_on_invalid_consequence_rating(tmp_path: Path):
    """Verify consequence rating must be one of IMPACT_ORDINAL."""
    bad_reg = tmp_path / "bad_rating.json"
    bad_reg.write_text(
        json.dumps(
            {
                "mappings": [
                    {
                        "mapping_id": "test-001",
                        "target_asset_id": DC_ASSET_ID,
                        "source_event": "src",
                        "destination_event": "dst",
                        "consequence_rating": "SuperCritical",
                        "status": "reviewed",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(RankingValidationError, match="invalid consequence_rating"):
        load_canonical_impact_equivalence_registry(bad_reg)


# ===========================================================================
# 2. Exact Asset/Event Reuse Precedence Tests
# ===========================================================================


def test_exact_reviewed_packet_takes_precedence_over_equivalence():
    """Verify explicit packet provider resolves exact match before equivalence provider."""
    bundle = load_week3_release()
    scope = build_dc_scope(success_event="terminal_compromise_seamless_dc")
    candidate = {"candidate_id": "exact_cand", "transition_history": [declared_dc_step()]}

    scope["target_goal"] = copy.deepcopy(
        bundle["query_projections"]["source_a"]["query"]["query_metadata"]["target_goal"]
    )
    resolver = impact_test_resolver(explicit_packet=bundle)
    output = resolver.resolve([candidate], scope)

    impact_cov = output.coverage_report["candidates"]["exact_cand"]["impact"]
    assert impact_cov["disposition"] == ResolverDisposition.RATED
    assert impact_cov["consequence_rating"] == "High"
    assert impact_cov["reason_code"] == ReasonCode.REVIEWED_PACKET_MATCH
    assert impact_cov["selected_provider"] == "explicit_packet_provider"


# ===========================================================================
# 3. Reviewed Equivalent-Event Reuse Tests (#243 positive cases)
# ===========================================================================


@pytest.mark.parametrize(
    "event_name,expected_mapping_id",
    [
        ("admin_control_c0", "eq-seamless-dc-admin-control-001"),
        ("admin_control_seamless_dc", "eq-seamless-dc-admin-control-002"),
        ("terminal_compromise", "eq-seamless-dc-admin-control-003"),
    ],
)
def test_reviewed_equivalence_reuses_impact_with_explicit_packet(
    event_name: str, expected_mapping_id: str
):
    """Verify #243 equivalent events reuse High impact when backed by Week 3 packet."""
    cp = SyntheticCPRatings()
    scope = build_dc_scope(success_event=event_name)
    candidate = {"candidate_id": "c0_cand", "transition_history": [declared_dc_step()]}

    resolver = impact_test_resolver(
        effort_providers=[cp],
        likelihood_providers=[cp],
    )
    output = resolver.resolve([candidate], scope)

    cand_rep = output.coverage_report["candidates"]["c0_cand"]
    impact_cov = cand_rep["impact"]
    assert impact_cov["disposition"] == ResolverDisposition.RATED
    assert impact_cov["consequence_rating"] == "High"
    assert impact_cov["reason_code"] == ReasonCode.REVIEWED_EQUIVALENCE_MATCH
    assert impact_cov["selected_provider"] == "reviewed_equivalence_impact_provider"
    assert expected_mapping_id in impact_cov["reason_detail"]

    # Audit metadata check
    audit = impact_cov["rating_audit"]
    assert audit["provider_name"] == "reviewed_equivalence_impact_provider"
    assert (
        audit["review_reference"]
        == "tests/test_rating_resolver_impact_equivalence.py#accepted_test_registry"
    )
    assert audit["basis_category"] == "synthetic_test_only"
    assert audit["provenance_digest"].startswith("sha256:")
    assert len(audit["provenance_digest"]) == 71


@pytest.mark.parametrize(
    "event_name,expected_mapping_id",
    [
        ("admin_control_c0", "eq-seamless-dc-admin-control-001"),
        ("admin_control_seamless_dc", "eq-seamless-dc-admin-control-002"),
        ("terminal_compromise", "eq-seamless-dc-admin-control-003"),
    ],
)
def test_reviewed_equivalence_resolves_standalone_without_explicit_packet(
    event_name: str, expected_mapping_id: str
):
    """Explicit provider registration supplies the accepted historical source basis."""
    cp = SyntheticCPRatings()
    scope = build_dc_scope(success_event=event_name)
    candidate = {"candidate_id": "c0_standalone", "transition_history": [declared_dc_step()]}

    resolver = impact_test_resolver(
        effort_providers=[cp],
        likelihood_providers=[cp],
    )
    output = resolver.resolve([candidate], scope)

    impact_cov = output.coverage_report["candidates"]["c0_standalone"]["impact"]
    assert impact_cov["disposition"] == ResolverDisposition.RATED
    assert impact_cov["consequence_rating"] == "High"
    assert impact_cov["reason_code"] == ReasonCode.REVIEWED_EQUIVALENCE_MATCH
    assert impact_cov["selected_provider"] == "reviewed_equivalence_impact_provider"
    assert expected_mapping_id in impact_cov["reason_detail"]


# ===========================================================================
# 4. Canonical Validator and PathRankingEngine Acceptance Tests
# ===========================================================================


def test_resolved_wire_payload_accepted_by_canonical_validators_and_engine():
    """Verify materialized ranking query and candidate envelopes pass canonical
    engine evaluation."""
    cp = SyntheticCPRatings()
    scope = build_dc_scope(success_event="admin_control_c0")
    candidate = {"candidate_id": "cand_c0", "transition_history": [declared_dc_step()]}

    resolver = impact_test_resolver(
        effort_providers=[cp],
        likelihood_providers=[cp],
    )
    output = resolver.resolve([candidate], scope)

    # 1. Validate target_impact_assessments wire payload
    validated_impacts = validate_target_impact_assessments(
        output.ranking_query["target_impact_assessments"]
    )
    assert DC_ASSET_ID in validated_impacts
    assert validated_impacts[DC_ASSET_ID]["rating_status"] == "rated"
    assert validated_impacts[DC_ASSET_ID]["consequence_rating"] == "High"
    assert validated_impacts[DC_ASSET_ID]["success_event"] == "admin_control_c0"

    # 2. Validate candidate envelopes
    validated_cands = validate_candidate_envelopes(output.candidate_envelopes, output.ranking_query)
    assert len(validated_cands) == 1
    assert validated_cands[0]["candidate_id"] == "cand_c0"

    # 3. PathRankingEngine.evaluate roundtrip
    engine = PathRankingEngine()
    result = engine.evaluate(output.ranking_query, output.candidate_envelopes)["result_payload"]

    assert "eligible_candidates" in result
    assert "cand_c0" in result["eligible_candidates"]
    evaluated_cand = result["eligible_candidates"]["cand_c0"]
    assert evaluated_cand["consequence_rating"] == "High"
    assert evaluated_cand["effort"] == 2
    assert evaluated_cand["likelihood_interval"] == (Fraction(3, 4), Fraction(3, 4))


# ===========================================================================
# 5. Negative Cases (Fail-Closed Refusal Integrity) Tests
# ===========================================================================


def test_negative_same_asset_different_consequence_refused():
    """Verify unreviewed event on the same asset is refused, not silently unrated or reused."""
    scope = build_dc_scope(success_event="recon_port_scan")
    candidate = {"candidate_id": "scan_cand", "transition_history": [declared_dc_step()]}

    resolver = impact_test_resolver()
    output = resolver.resolve([candidate], scope)

    impact_cov = output.coverage_report["candidates"]["scan_cand"]["impact"]
    assert impact_cov["disposition"] == ResolverDisposition.REFUSED
    assert impact_cov["consequence_rating"] is None
    assert impact_cov["reason_code"] == ReasonCode.OUT_OF_SCOPE
    assert "no reviewed equivalence mapping" in impact_cov["reason_detail"]

    # Verify unresolved gaps records the refusal
    gaps = output.coverage_report["unresolved_gaps"]
    i_gap = next(g for g in gaps if g["dimension"] == "I")
    assert i_gap["disposition"] == "refused"


def test_negative_different_asset_workstation_not_granted_dc_impact():
    """Verify workstation execution is never granted Domain Controller compromise impact."""
    scope = build_dc_scope(
        target_asset_id=WORKSTATION_ASSET_ID,
        success_event="admin_control_c0",
    )
    candidate = {
        "candidate_id": "workstation_cand",
        "transition_history": [declared_dc_step(target=WORKSTATION_ASSET_ID)],
    }

    resolver = impact_test_resolver()
    output = resolver.resolve([candidate], scope)

    impact_cov = output.coverage_report["candidates"]["workstation_cand"]["impact"]
    # Workstation is absent from DC equivalence registry, so falls back to UNRATED
    assert impact_cov["disposition"] == ResolverDisposition.UNRATED
    assert impact_cov["consequence_rating"] is None


@pytest.mark.parametrize(
    "mismatch_field,mismatch_value",
    [
        ("horizon", "72h"),
        ("snapshot_id", "sha256:" + "0" * 64),
        ("work_boundary", "inter_forest"),
        ("scenario_id", "unrelated_scenario_v2"),
    ],
)
def test_negative_stale_or_out_of_scope_equivalence_refused(
    mismatch_field: str, mismatch_value: str
):
    """Verify equivalence provider strictly refuses when query scope deviates from applicability."""
    scope = build_dc_scope(
        success_event="admin_control_c0",
        **{mismatch_field: mismatch_value},
    )
    candidate = {"candidate_id": "scope_cand", "transition_history": [declared_dc_step()]}

    registry = accepted_test_registry()
    if mismatch_field == "horizon":
        for mapping in registry["mappings"]:
            mapping["applicability"]["operational_horizon"] = "24h"
    resolver = ContractRatingResolver(
        impact_providers=[
            ReviewedEquivalenceImpactProvider(registry, source_packet=load_week3_release())
        ]
    )
    output = resolver.resolve([candidate], scope)

    impact_cov = output.coverage_report["candidates"]["scope_cand"]["impact"]
    assert impact_cov["disposition"] == ResolverDisposition.REFUSED
    assert impact_cov["consequence_rating"] is None
    assert impact_cov["reason_code"] == ReasonCode.OUT_OF_SCOPE
    assert "mismatch" in impact_cov["reason_detail"].lower()


def test_negative_conflicting_equivalence_mappings_returns_conflicting():
    """Verify conflicting consequence ratings in equivalence registry return CONFLICTING."""
    conflicting_registry = {
        "schema_version": "1.0.0",
        "version": "1.0.0",
        "status": "reviewed",
        "mappings": [
            {
                "mapping_id": "eq-1",
                "status": "reviewed",
                "target_asset_id": DC_ASSET_ID,
                "source_event": "terminal_compromise_seamless_dc",
                "destination_event": "admin_control_c0",
                "consequence_rating": "High",
                "applicability": {
                    "scenario_id": [SEAMLESS_SCENARIO_ID],
                    "snapshot_id": SEAMLESS_SNAPSHOT_ID,
                    "boundary": "intra_forest",
                    "operational_horizon": "24h",
                },
            },
            {
                "mapping_id": "eq-2",
                "status": "reviewed",
                "target_asset_id": DC_ASSET_ID,
                "source_event": "terminal_compromise_seamless_dc",
                "destination_event": "admin_control_c0",
                "consequence_rating": "Medium",  # Conflicting!
                "applicability": {
                    "scenario_id": [SEAMLESS_SCENARIO_ID],
                    "snapshot_id": SEAMLESS_SNAPSHOT_ID,
                    "boundary": "intra_forest",
                    "operational_horizon": "24h",
                },
            },
        ],
    }

    resolver = impact_test_resolver(impact_equivalence_registry=conflicting_registry)
    scope = build_dc_scope(success_event="admin_control_c0")
    candidate = {"candidate_id": "conflict_cand", "transition_history": [declared_dc_step()]}

    output = resolver.resolve([candidate], scope)
    impact_cov = output.coverage_report["candidates"]["conflict_cand"]["impact"]
    assert impact_cov["disposition"] == ResolverDisposition.CONFLICTING
    assert impact_cov["reason_code"] == ReasonCode.CONFLICTING_PROVIDER_BASIS


def test_negative_unreviewed_equivalence_status_refused():
    """Verify mappings with status other than 'reviewed' are refused."""
    draft_registry = {
        "schema_version": "1.0.0",
        "version": "1.0.0",
        "status": "draft",
        "mappings": [
            {
                "mapping_id": "eq-draft-001",
                "status": "draft",  # Unreviewed!
                "target_asset_id": DC_ASSET_ID,
                "source_event": "terminal_compromise_seamless_dc",
                "destination_event": "admin_control_c0",
                "consequence_rating": "High",
                "applicability": {
                    "scenario_id": [SEAMLESS_SCENARIO_ID],
                    "snapshot_id": SEAMLESS_SNAPSHOT_ID,
                    "boundary": "intra_forest",
                    "operational_horizon": "24h",
                },
            }
        ],
    }

    resolver = impact_test_resolver(impact_equivalence_registry=draft_registry)
    scope = build_dc_scope(success_event="admin_control_c0")
    candidate = {"candidate_id": "draft_cand", "transition_history": [declared_dc_step()]}

    output = resolver.resolve([candidate], scope)
    impact_cov = output.coverage_report["candidates"]["draft_cand"]["impact"]
    assert impact_cov["disposition"] == ResolverDisposition.REFUSED
    assert impact_cov["reason_code"] == ReasonCode.PREREQUISITE_GATE_REFUSAL
    assert "unreviewed status" in impact_cov["reason_detail"]


def test_negative_no_unreviewed_transitive_equivalence():
    """Verify unreviewed transitive equivalence chaining is strictly rejected."""
    # Registry has A -> B and B -> C, but NOT A -> C
    transitive_registry = {
        "schema_version": "1.0.0",
        "version": "1.0.0",
        "status": "reviewed",
        "mappings": [
            {
                "mapping_id": "eq-step1",
                "status": "reviewed",
                "target_asset_id": DC_ASSET_ID,
                "source_event": "event_a",
                "destination_event": "event_b",
                "consequence_rating": "High",
                "applicability": {
                    "scenario_id": [SEAMLESS_SCENARIO_ID],
                    "snapshot_id": SEAMLESS_SNAPSHOT_ID,
                    "boundary": "intra_forest",
                    "operational_horizon": "24h",
                },
            },
            {
                "mapping_id": "eq-step2",
                "status": "reviewed",
                "target_asset_id": DC_ASSET_ID,
                "source_event": "event_b",
                "destination_event": "event_c",
                "consequence_rating": "High",
                "applicability": {
                    "scenario_id": [SEAMLESS_SCENARIO_ID],
                    "snapshot_id": SEAMLESS_SNAPSHOT_ID,
                    "boundary": "intra_forest",
                    "operational_horizon": "24h",
                },
            },
        ],
    }

    scope = build_dc_scope(success_event="event_c")
    key = generate_rating_lookup_key_i(
        target_asset_id=DC_ASSET_ID,
        success_event="event_c",
        consequence_scope="intra_forest",
        boundary="intra_forest",
        scenario_id=SEAMLESS_SCENARIO_ID,
    )

    # Querying event_c when source in packet is event_a (not event_b) must refuse
    packet = {
        "target_impact_assessments": {
            DC_ASSET_ID: {
                "target_asset_id": DC_ASSET_ID,
                "success_event": "event_a",
                "rating_status": "rated",
                "consequence_rating": "High",
            }
        }
    }
    provider_with_packet = ReviewedEquivalenceImpactProvider(
        transitive_registry, source_packet=packet
    )
    result = provider_with_packet.resolve_impact(key, DC_ASSET_ID, "event_c", scope)
    assert result.disposition == ResolverDisposition.REFUSED


def test_negative_directional_mapping_refuses_reverse_query():
    """Verify directional mapping cannot be traversed in reverse."""
    directional_registry = {
        "schema_version": "1.0.0",
        "version": "1.0.0",
        "status": "reviewed",
        "mappings": [
            {
                "mapping_id": "eq-directional-001",
                "status": "reviewed",
                "target_asset_id": DC_ASSET_ID,
                "source_event": "source_action",
                "destination_event": "derived_outcome",
                "directionality": "directional",  # Asymmetric!
                "consequence_rating": "High",
                "applicability": {
                    "scenario_id": [SEAMLESS_SCENARIO_ID],
                    "snapshot_id": SEAMLESS_SNAPSHOT_ID,
                    "boundary": "intra_forest",
                    "operational_horizon": "24h",
                },
            }
        ],
    }

    provider = ReviewedEquivalenceImpactProvider(directional_registry)
    scope = build_dc_scope(success_event="source_action")
    key = generate_rating_lookup_key_i(
        target_asset_id=DC_ASSET_ID,
        success_event="source_action",
        consequence_scope="intra_forest",
        boundary="intra_forest",
        scenario_id=SEAMLESS_SCENARIO_ID,
    )

    # Attempting to resolve in reverse (source_action from destination) is refused
    result = provider.resolve_impact(key, DC_ASSET_ID, "source_action", scope)
    assert result.disposition == ResolverDisposition.REFUSED
    assert result.reason_code == ReasonCode.PREREQUISITE_GATE_REFUSAL
    assert "directional" in result.reason_detail.lower()


@pytest.mark.parametrize(
    "forbidden_event",
    [
        "effective_member_da",
        "memberof_da_checkpoint",
        "domain_admin_group_membership",
        "effective_member([v_a, g_da])",
    ],
)
def test_negative_forbidden_da_membership_derivation_refused(forbidden_event: str):
    """Verify DC impact derivation from DA group membership entitlement is strictly forbidden."""
    provider = ReviewedEquivalenceImpactProvider()
    scope = build_dc_scope(success_event=forbidden_event)
    key = generate_rating_lookup_key_i(
        target_asset_id=DC_ASSET_ID,
        success_event=forbidden_event,
        consequence_scope="intra_forest",
        boundary="intra_forest",
        scenario_id=SEAMLESS_SCENARIO_ID,
    )

    result = provider.resolve_impact(key, DC_ASSET_ID, forbidden_event, scope)
    assert result.disposition == ResolverDisposition.REFUSED
    assert result.reason_code == ReasonCode.PREREQUISITE_GATE_REFUSAL
    assert "Domain Admin membership entitlement" in result.reason_detail


def test_negative_source_packet_conflict_refused():
    """Verify mismatch between source packet rating and equivalence mapping is refused."""
    mismatched_packet = {
        "target_impact_assessments": {
            DC_ASSET_ID: {
                "target_asset_id": DC_ASSET_ID,
                "success_event": "terminal_compromise_seamless_dc",
                "rating_status": "rated",
                "consequence_rating": "Medium",  # Registry says High!
            }
        }
    }
    provider = ReviewedEquivalenceImpactProvider(
        accepted_test_registry(), source_packet=mismatched_packet
    )
    scope = build_dc_scope(success_event="admin_control_c0")
    key = generate_rating_lookup_key_i(
        target_asset_id=DC_ASSET_ID,
        success_event="admin_control_c0",
        consequence_scope="intra_forest",
        boundary="intra_forest",
        scenario_id=SEAMLESS_SCENARIO_ID,
    )
    result = provider.resolve_impact(key, DC_ASSET_ID, "admin_control_c0", scope)
    assert result.disposition == ResolverDisposition.REFUSED
    assert result.reason_code == ReasonCode.CONFLICTING_PROVIDER_BASIS


# ===========================================================================
# 6. Multi-Path Risk Case Pareto Comparison Tests
# ===========================================================================


def test_multi_path_risk_comparison_pareto_ranking_with_equivalent_impact():
    """Verify multiple competing candidate paths targeting DC01 are ranked under
    reused High impact."""

    # Two paths: Direct (fewer steps, lower effort) vs Alternate (more steps, higher effort)
    direct_step = declared_dc_step(action_id="act_direct", method="winrm")
    alt_step1 = declared_dc_step(action_id="act_alt_1", method="rpc", adds=["intermediate_cred"])
    alt_step2 = declared_dc_step(
        action_id="act_alt_2",
        method="wmi",
        requires=["intermediate_cred"],
        adds=["admin_control_badblood"],
    )

    class MultiStepCP:
        name = "multi_step_cp"
        provider_version = "1.0.0"

        def resolve_effort(self, key: Any, record: Any, scope: Any) -> ResolutionResult:
            cost = 1 if "direct" in key.work_unit_id else 2
            return ResolutionResult(
                disposition=ResolverDisposition.RATED,
                value=cost,
                reason_code=ReasonCode.REVIEWED_PACKET_MATCH,
                provider_name=self.name,
                provider_version=self.provider_version,
                basis_category=BasisClassification.SYNTHETIC_TEST_ONLY,
                rubric_scores={"t1": 1, "t2": cost + 1, "computed_cost": cost},
            )

        def resolve_likelihood(
            self, key: Any, prefix: Any, outcome: Any, scope: Any
        ) -> ResolutionResult:
            q = Fraction(4, 5) if "direct" in outcome else Fraction(3, 5)
            return ResolutionResult(
                disposition=ResolverDisposition.RATED,
                value=(q, q),
                reason_code=ReasonCode.REVIEWED_PACKET_MATCH,
                provider_name=self.name,
                provider_version=self.provider_version,
                basis_category=BasisClassification.SYNTHETIC_TEST_ONLY,
            )

    cp = MultiStepCP()
    resolver = impact_test_resolver(
        effort_providers=[cp],
        likelihood_providers=[cp],
    )
    scope = build_dc_scope(success_event="admin_control_c0")
    scope["facts_ledger"]["predicate_layers"]["intermediate_cred"] = 3

    candidates = [
        {"candidate_id": "cand_direct", "transition_history": [direct_step]},
        {"candidate_id": "cand_alternate", "transition_history": [alt_step1, alt_step2]},
    ]

    output = resolver.resolve(candidates, scope)

    # Both candidates must be fully rated with High consequence rating
    for cid in ("cand_direct", "cand_alternate"):
        rep = output.coverage_report["candidates"][cid]
        assert rep["impact"]["disposition"] == ResolverDisposition.RATED
        assert rep["impact"]["consequence_rating"] == "High"
        assert rep["impact"]["reason_code"] == ReasonCode.REVIEWED_EQUIVALENCE_MATCH

    # Evaluate Pareto ranking through PathRankingEngine
    engine = PathRankingEngine()
    ranking_result = engine.evaluate(output.ranking_query, output.candidate_envelopes)[
        "result_payload"
    ]

    eligible = ranking_result["eligible_candidates"]
    assert "cand_direct" in eligible
    assert "cand_alternate" in eligible
    assert eligible["cand_direct"]["consequence_rating"] == "High"
    assert eligible["cand_alternate"]["consequence_rating"] == "High"
    assert eligible["cand_direct"]["effort"] < eligible["cand_alternate"]["effort"]

    # Direct candidate strictly dominates alternate candidate
    frontier = ranking_result.get("frontier", ranking_result.get("pareto_frontier", []))
    assert "cand_direct" in frontier


# ===========================================================================
# 7. Week 3 Baseline Regression Preservation
# ===========================================================================


def test_week3_baseline_evaluation_preserved():
    """Verify Week 3 reviewed-release query projections evaluate identically to baseline."""
    bundle = load_week3_release()
    query_proj = bundle["query_projections"]["source_a"]
    ranking_query = query_proj["query"]
    candidate_envelopes = query_proj["candidates"]

    engine = PathRankingEngine()
    result = engine.evaluate(ranking_query, candidate_envelopes)["result_payload"]

    assert "eligible_candidates" in result
    assert len(result["eligible_candidates"]) == 2
    for cand in result["eligible_candidates"].values():
        assert cand["consequence_rating"] == "High"


def test_default_resolver_does_not_register_hidden_impact_provider():
    output = ContractRatingResolver().resolve(
        [{"candidate_id": "no-default", "transition_history": [declared_dc_step()]}],
        build_dc_scope(),
    )
    impact = output.coverage_report["candidates"]["no-default"]["impact"]
    assert impact["disposition"] == ResolverDisposition.UNRATED
    assert impact["consequence_rating"] is None


def test_proposed_impact_registry_does_not_certify_review():
    provider = ReviewedEquivalenceImpactProvider(
        load_canonical_impact_equivalence_registry(), source_packet=load_week3_release()
    )
    scope = build_dc_scope()
    key = generate_rating_lookup_key_i(
        DC_ASSET_ID,
        "admin_control_c0",
        consequence_scope="intra_forest",
        boundary="intra_forest",
        scenario_id=SEAMLESS_SCENARIO_ID,
    )
    result = provider.resolve_impact(key, DC_ASSET_ID, "admin_control_c0", scope)
    assert result.disposition == ResolverDisposition.REFUSED
    assert result.value is None


@pytest.mark.skipif(
    not Path(os.environ.get("SEAMLESS_RAW_DIR", ROOT / "data/raw/SEAMLESS")).is_dir(),
    reason="manifest-verified private SEAMLESS raw inputs required",
)
def test_actual_frozen_program_refuses_pending_equivalence_and_consumes_accepted_disposition():
    from scripts.research.asrep_inputs import inputs, ranking_inputs
    from tests.frozen_rating_inputs import frozen_program

    paths, scope, bindings = frozen_program()
    # Consume the event spelling emitted by the existing authoritative ranking helper.
    fixture_graph, fixture_query = inputs()
    helper_query, _ = ranking_inputs(fixture_graph, fixture_query)
    event = next(iter(helper_query["target_impact_assessments"].values()))["success_event"]
    assert scope["target_goal"]["success_event"] == event == "admin_execution_on_C"
    assert scope["horizon"] == "fixed-snapshot-window"
    assert scope["target_goal"]["target_asset_id"] == DC_ASSET_ID
    results = []
    for registry in (load_canonical_impact_equivalence_registry(), accepted_test_registry()):
        provider = ReviewedEquivalenceImpactProvider(registry, source_packet=load_week3_release())
        output = ContractRatingResolver(impact_providers=[provider]).resolve(
            paths, scope, transition_bindings=bindings
        )
        impact = next(iter(output.coverage_report["candidates"].values()))["impact"]
        results.append(impact)
        assert output.ranking_query["query_metadata"]["horizon"] == "fixed-snapshot-window"
        assert output.candidate_envelopes[0]["edge_provenance_map"] == {
            edge["id"]: edge["provenance"] for edge in paths[0].edges
        }
    assert results[0]["disposition"] == ResolverDisposition.REFUSED
    assert results[0]["consequence_rating"] is None
    assert "unreviewed status" in results[0]["reason_detail"]
    assert results[1]["disposition"] == ResolverDisposition.RATED
    assert results[1]["consequence_rating"] == "High"
    assert results[1]["rating_audit"]["basis_category"] == "synthetic_test_only"


@pytest.mark.parametrize("horizon", ["24h", "fixed-snapshot-window", "72h"])
def test_reviewed_consequence_equivalence_explicitly_independent_of_recovery_horizon(horizon):
    provider = ReviewedEquivalenceImpactProvider(
        accepted_test_registry(), source_packet=load_week3_release()
    )
    scope = build_dc_scope(horizon=horizon)
    key = generate_rating_lookup_key_i(
        DC_ASSET_ID,
        "admin_control_c0",
        consequence_scope="intra_forest",
        boundary="intra_forest",
        scenario_id=SEAMLESS_SCENARIO_ID,
    )
    assert provider.resolve_impact(key, DC_ASSET_ID, "admin_control_c0", scope).value == "High"


def test_equivalence_cannot_supply_its_own_missing_source_basis():
    provider = ReviewedEquivalenceImpactProvider(accepted_test_registry())
    scope = build_dc_scope()
    key = generate_rating_lookup_key_i(
        DC_ASSET_ID,
        "admin_control_c0",
        consequence_scope="intra_forest",
        boundary="intra_forest",
        scenario_id=SEAMLESS_SCENARIO_ID,
    )
    result = provider.resolve_impact(key, DC_ASSET_ID, "admin_control_c0", scope)
    assert result.disposition == ResolverDisposition.REFUSED
    assert result.reason_code == ReasonCode.MISSING_EVIDENCE


@pytest.mark.parametrize("field", ["snapshot_id", "scenario_id", "target_goal"])
def test_missing_equivalence_scope_fails_closed(field):
    provider = ReviewedEquivalenceImpactProvider(
        accepted_test_registry(), source_packet=load_week3_release()
    )
    scope = build_dc_scope()
    scope.pop(field)
    key = generate_rating_lookup_key_i(
        DC_ASSET_ID,
        "admin_control_c0",
        consequence_scope="intra_forest",
        boundary="intra_forest",
        scenario_id=SEAMLESS_SCENARIO_ID,
    )
    assert (
        provider.resolve_impact(key, DC_ASSET_ID, "admin_control_c0", scope).disposition
        == ResolverDisposition.REFUSED
    )


def test_changed_source_release_cannot_reuse_pinned_equivalence():
    source = load_week3_release()
    source["bundle_metadata"]["bundle_version"] = "stale"
    provider = ReviewedEquivalenceImpactProvider(accepted_test_registry(), source_packet=source)
    scope = build_dc_scope()
    key = generate_rating_lookup_key_i(
        DC_ASSET_ID,
        "admin_control_c0",
        consequence_scope="intra_forest",
        boundary="intra_forest",
        scenario_id=SEAMLESS_SCENARIO_ID,
    )
    result = provider.resolve_impact(key, DC_ASSET_ID, "admin_control_c0", scope)
    assert result.disposition == ResolverDisposition.REFUSED
    assert result.reason_code == ReasonCode.CONFLICTING_PROVIDER_BASIS


@pytest.mark.parametrize("event", ["tier0_control", "crownjewel_control", "dc_label_only"])
def test_asset_labels_do_not_establish_consequence_equivalence(event):
    provider = ReviewedEquivalenceImpactProvider(
        accepted_test_registry(), source_packet=load_week3_release()
    )
    scope = build_dc_scope(success_event=event)
    key = generate_rating_lookup_key_i(
        DC_ASSET_ID,
        event,
        consequence_scope="intra_forest",
        boundary="intra_forest",
        scenario_id=SEAMLESS_SCENARIO_ID,
    )
    result = provider.resolve_impact(key, DC_ASSET_ID, event, scope)
    assert result.disposition == ResolverDisposition.REFUSED
    assert result.value is None


@pytest.mark.parametrize(
    "changed",
    [
        "key_asset",
        "key_event",
        "key_boundary",
        "key_scenario",
        "key_consequence",
        "goal_asset",
        "goal_event",
    ],
)
def test_inconsistent_impact_request_key_or_goal_is_refused(changed):
    provider = ReviewedEquivalenceImpactProvider(
        accepted_test_registry(), source_packet=load_week3_release()
    )
    scope = build_dc_scope()
    params = {
        "target_asset_id": DC_ASSET_ID,
        "success_event": "admin_control_c0",
        "consequence_scope": "intra_forest",
        "boundary": "intra_forest",
        "scenario_id": SEAMLESS_SCENARIO_ID,
    }
    if changed == "key_asset":
        params["target_asset_id"] = WORKSTATION_ASSET_ID
    elif changed == "key_event":
        params["success_event"] = "recon_port_scan"
    elif changed == "key_boundary":
        params["boundary"] = "cross_forest"
    elif changed == "key_scenario":
        params["scenario_id"] = "other"
    elif changed == "key_consequence":
        params["consequence_scope"] = "cross_forest"
    elif changed == "goal_asset":
        scope["target_goal"]["target_asset_id"] = WORKSTATION_ASSET_ID
    else:
        scope["target_goal"]["success_event"] = "recon_port_scan"
    result = provider.resolve_impact(
        generate_rating_lookup_key_i(**params), DC_ASSET_ID, "admin_control_c0", scope
    )
    assert result.disposition == ResolverDisposition.REFUSED
    assert result.value is None
