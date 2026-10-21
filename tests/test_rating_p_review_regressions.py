"""Independent negative probes for B's #254 findings; synthetic test bases only."""

from dataclasses import replace
from fractions import Fraction

import pytest

from src.engine.ranking.likelihood import ReviewedScenarioLikelihoodProvider
from src.engine.ranking.resolver import (
    BasisClassification,
    RatingResolver,
    ResolverDisposition,
    generate_rating_lookup_key_p,
)
from tests.test_rating_p_provider_chain import build_base_scope

PREFIX = (
    "asrep_request:a:b:ctx-111:intra_forest:1.0.0",
    "recover_asrep_secret:a:b:ctx-999:intra_forest:1.0.0",
)


def accepted_test_record(key):
    """Explicit acceptance simulation, never a production record or equivalence."""
    return {
        **key.to_dict(),
        "review_status": "accepted",
        "disposition": "rated",
        "review_reference": "tests/test_rating_p_review_regressions.py#accepted_test_record",
        "provenance_digest": "sha256:" + "1" * 64,
        "basis_category": BasisClassification.SYNTHETIC_TEST_ONLY.value,
        "rationale": "Isolated full-history conditional interval for regression testing",
        "lower": "1/2",
        "upper": "3/4",
    }


def lookup():
    return generate_rating_lookup_key_p(
        "scenario-test",
        "1.0.0",
        "snapshot-A",
        "source-X",
        PREFIX,
        PREFIX[-1],
        "recover_asrep_secret",
        "a",
        "b",
        source_id="source-X",
        budget=6,
        scope="target-population-A",
        auth_context="auth-A",
        resource_context="resource-A",
        policy_id="no-retry-A",
    )


def resolve(record, key=None, scope=None):
    key = key or lookup()
    return ReviewedScenarioLikelihoodProvider([record]).resolve_likelihood(
        key,
        key.ordered_work_prefix,
        key.outcome_work_unit_id,
        scope or {},
    )


def test_explicitly_accepted_exact_scope_and_history_rates():
    result = resolve(accepted_test_record(lookup()))
    assert result.disposition == ResolverDisposition.RATED
    assert result.value == (Fraction(1, 2), Fraction(3, 4))
    assert result.basis_category == BasisClassification.SYNTHETIC_TEST_ONLY


@pytest.mark.parametrize(
    "field,value",
    [
        ("review_status", "pending"),
        ("review_status", "rejected"),
        ("review_status", None),
        ("disposition", "rejected"),
        ("disposition", "typo"),
        ("review_reference", None),
        ("review_reference", ""),
        ("provenance_digest", None),
        ("provenance_digest", "not-a-digest"),
        ("basis_category", None),
        ("basis_category", "empirical_evidence"),
        ("version", "unknown-version"),
        ("rationale", ""),
    ],
)
def test_unaccepted_or_malformed_record_is_nonnumeric(field, value):
    record = accepted_test_record(lookup())
    record[field] = value
    result = resolve(record, scope={"governance": {"allow_scenario_fallback": True}})
    assert result.disposition == ResolverDisposition.REFUSED
    assert result.value is None


@pytest.mark.parametrize(
    "field,value",
    [
        ("scenario_version", "2.0.0"),
        ("snapshot_id", "snapshot-B"),
        ("source_id", "source-Y"),
        ("foothold_node_id", "source-Y"),
        ("actor_id", "other-actor"),
        ("target_id", "other-target"),
        ("boundary", "cross_forest"),
        ("method", "other-method"),
        ("horizon", "48h"),
        ("budget", 0),
        ("budget", None),
        ("auth_context", "auth-B"),
        ("resource_context", "resource-B"),
        ("policy_id", "retry-B"),
        ("policy_id", None),
        ("scope", "target-population-B"),
    ],
)
def test_each_context_mismatch_is_nonnumeric(field, value):
    key = lookup()
    result = resolve(accepted_test_record(key), replace(key, **{field: value}))
    assert result.disposition == ResolverDisposition.REFUSED
    assert result.value is None
    assert field in result.reason_detail


@pytest.mark.parametrize(
    "field",
    [
        "scenario_version",
        "snapshot_id",
        "source_id",
        "foothold_node_id",
        "actor_id",
        "target_id",
        "boundary",
        "method",
        "horizon",
        "budget",
        "auth_context",
        "resource_context",
        "policy_id",
        "scope",
        "version",
        "review_status",
        "disposition",
        "review_reference",
        "provenance_digest",
        "basis_category",
        "outcome_work_unit_id",
    ],
)
def test_missing_required_binding_is_nonnumeric(field):
    record = accepted_test_record(lookup())
    del record[field]
    result = resolve(record)
    assert result.disposition != ResolverDisposition.RATED
    assert result.value is None


@pytest.mark.parametrize(
    "prefix",
    [
        (PREFIX[0].replace("ctx-111", "ctx-222"), PREFIX[1]),
        tuple(reversed(PREFIX)),
        (PREFIX[1],),
        ("asrep_request", PREFIX[1]),
        (PREFIX[0].replace("ctx-111", "default"), PREFIX[1]),
    ],
)
def test_no_implicit_history_projection(prefix):
    key = lookup()
    result = resolve(accepted_test_record(key), replace(key, ordered_work_prefix=prefix))
    assert result.disposition != ResolverDisposition.RATED
    assert result.value is None


@pytest.mark.parametrize("field", ["actor_capability", "retry_policy", "target_population"])
def test_additional_reviewed_scope_is_required_and_exact(field):
    record = {**accepted_test_record(lookup()), field: "context-A"}
    assert resolve(record, scope={field: "context-A"}).disposition == ResolverDisposition.RATED
    assert resolve(record, scope={field: "context-B"}).value is None
    assert resolve(record).value is None
    del record[field]
    assert resolve(record, scope={field: "context-A"}).value is None


def generated_test_program():
    from tests.test_week3_semantic_bridge import ACTOR, HOST, fixture, run

    graph, facts = fixture()
    paths = run(graph, facts).paths
    assert len(paths) == 1
    scope = build_base_scope(foothold_node_id=ACTOR, scenario_id="synthetic-p-gates")
    scope["target_goal"]["target_asset_id"] = HOST
    scope["facts_ledger"] = {
        "predicate_layers": {"ready": 3, "admin_control_host": 3},
        "assumed_facts": [
            {
                "predicate": "ready",
                "layer": 3,
                "truth_value": True,
                "provenance_reference": "tests://synthetic-p-gates",
                "rationale": "Synthetic fixture initial capability",
            }
        ],
    }
    scope.pop("declared_facts", None)
    bindings = {
        (r.technique_id, r.actor, r.source, r.target): {
            "requires": ["ready"],
            "adds": ["admin_control_host" if r.technique_id == "scenario_winrm_admin" else "ready"],
        }
        for path in paths
        for step in path.transition_history
        for r in [step.result.request]
    }
    seed = RatingResolver().resolve(paths, scope, transition_bindings=bindings)
    cid = seed.candidate_envelopes[0]["candidate_id"]
    prefixes = seed.coverage_report["candidates"][cid]["likelihood"]["prefixes"]
    records = [accepted_test_record_dict(p["rating_audit"]["lookup_key"]) for p in prefixes]
    return paths, scope, bindings, cid, records


def accepted_test_record_dict(key_dict):
    return {**accepted_test_record(lookup()), **key_dict}


def test_generated_flow_pending_refusal_cannot_be_hidden_by_later_accepted_provider():
    paths, scope, bindings, cid, records = generated_test_program()
    pending = [{**r, "review_status": "pending"} for r in records]
    output = RatingResolver(
        likelihood_providers=[
            ReviewedScenarioLikelihoodProvider(pending, name="pending"),
            ReviewedScenarioLikelihoodProvider(records, name="later_accepted"),
        ]
    ).resolve(paths, scope, transition_bindings=bindings)
    report = output.coverage_report["candidates"][cid]["likelihood"]
    assert not report["all_rated"]
    assert len(report["prefixes"]) == 3
    for prefix in report["prefixes"]:
        assert prefix["interval"] is None
        assert prefix["selected_provider"] == "pending"
        assert [t["provider"] for t in prefix["provider_trace"]] == ["pending"]


def test_generated_flow_preserves_governance_and_actor_retry_population_scope():
    paths, scope, bindings, cid, records = generated_test_program()
    scope["governance"] = {"allow_scenario_fallback": False}
    output = RatingResolver(
        likelihood_providers=[ReviewedScenarioLikelihoodProvider(records)]
    ).resolve(paths, scope, transition_bindings=bindings)
    assert not output.coverage_report["candidates"][cid]["likelihood"]["all_rated"]


def test_generated_full_history_fraction_product_and_passive_no_event():
    from src.engine.ranking import PathRankingEngine, parse_rational

    paths, scope, bindings, cid, records = generated_test_program()
    output = RatingResolver(
        likelihood_providers=[ReviewedScenarioLikelihoodProvider(records)]
    ).resolve(paths, scope, transition_bindings=bindings)
    report = output.coverage_report["candidates"][cid]["likelihood"]
    assert report["all_rated"]
    assert len(report["prefixes"]) == 3  # Four transitions, one passive closure.
    assert len(output.ranking_query["work_units_ledger"]) == 3
    result = PathRankingEngine().evaluate(output.ranking_query, output.candidate_envelopes)[
        "result_payload"
    ]
    assessment = result["diagnostics"][cid]["assessment"]
    assert [parse_rational(v) for v in assessment["likelihood_interval"]] == [
        Fraction(1, 2) ** 3,
        Fraction(3, 4) ** 3,
    ]


@pytest.mark.parametrize("field", ["actor_capability", "retry_policy", "target_population"])
def test_generated_provider_receives_additional_scope(field):
    paths, scope, bindings, cid, records = generated_test_program()
    for record in records:
        record[field] = "context-A"
    provider = ReviewedScenarioLikelihoodProvider(records)
    resolver = RatingResolver(likelihood_providers=[provider])
    scope[field] = "context-A"
    assert resolver.resolve(paths, scope, transition_bindings=bindings).coverage_report[
        "candidates"
    ][cid]["likelihood"]["all_rated"]
    scope[field] = "context-B"
    assert not resolver.resolve(paths, scope, transition_bindings=bindings).coverage_report[
        "candidates"
    ][cid]["likelihood"]["all_rated"]


@pytest.mark.parametrize(
    "field,value",
    [
        ("rating_binding", None),
        ("rating_binding", "malformed"),
        ("basis_category", []),
        ("ordered_work_prefix", 42),
        ("applicable_queries", "query-test-p-001"),
    ],
)
def test_malformed_registry_input_has_explicit_integrity_refusal(field, value):
    record = accepted_test_record(lookup())
    record[field] = value
    result = resolve(record, scope={"query_id": "query-test-p-001"})
    assert result.disposition == ResolverDisposition.REFUSED
    assert result.value is None


def test_malformed_governance_has_explicit_refusal():
    result = resolve(accepted_test_record(lookup()), scope={"governance": None})
    assert result.disposition == ResolverDisposition.REFUSED
    assert result.value is None


@pytest.mark.parametrize("value", [0, 1, "false", None])
def test_nonboolean_scenario_permission_is_malformed(value):
    result = resolve(
        accepted_test_record(lookup()), scope={"governance": {"allow_scenario_fallback": value}}
    )
    assert result.disposition == ResolverDisposition.REFUSED
    assert result.value is None


def test_empty_canonical_history_cannot_fall_back_to_alias_field():
    record = accepted_test_record(lookup())
    record["prefix"] = record["ordered_work_prefix"]
    record["ordered_work_prefix"] = []
    result = resolve(record)
    assert result.disposition != ResolverDisposition.RATED
    assert result.value is None


def test_missing_history_integrity_refusal_cannot_be_hidden_by_fallback():
    paths, scope, bindings, cid, records = generated_test_program()
    broken = [{k: v for k, v in r.items() if k != "ordered_work_prefix"} for r in records]
    output = RatingResolver(
        likelihood_providers=[
            ReviewedScenarioLikelihoodProvider(broken, name="broken"),
            ReviewedScenarioLikelihoodProvider(records, name="accepted"),
        ]
    ).resolve(paths, scope, transition_bindings=bindings)
    for prefix in output.coverage_report["candidates"][cid]["likelihood"]["prefixes"]:
        assert prefix["interval"] is None
        assert [t["provider"] for t in prefix["provider_trace"]] == ["broken"]


def test_structured_scope_does_not_equate_bool_and_int():
    record = {**accepted_test_record(lookup()), "retry_policy": {"max_attempts": 1}}
    assert resolve(record, scope={"retry_policy": {"max_attempts": 1}}).value is not None
    assert resolve(record, scope={"retry_policy": {"max_attempts": True}}).value is None


def test_distinct_complete_contexts_do_not_conflict():
    key = lookup()
    records = [
        accepted_test_record(key),
        accepted_test_record(replace(key, snapshot_id="snapshot-B")),
    ]
    result = ReviewedScenarioLikelihoodProvider(records).resolve_likelihood(
        key, PREFIX, PREFIX[-1], {}
    )
    assert result.disposition == ResolverDisposition.RATED


def test_duplicate_applicable_contexts_still_conflict():
    record = accepted_test_record(lookup())
    result = ReviewedScenarioLikelihoodProvider([record, record]).resolve_likelihood(
        lookup(), PREFIX, PREFIX[-1], {}
    )
    assert result.disposition == ResolverDisposition.CONFLICTING
    assert result.value is None


@pytest.mark.parametrize(
    "field,value",
    [
        ("ordered_work_prefix", []),
        ("ordered_work_prefix", None),
        ("prefix", 12),
        ("prefix", []),
        ("prefix", list(reversed(PREFIX))),
    ],
)
def test_invalid_history_field_is_integrity_refusal(field, value):
    record = accepted_test_record(lookup())
    record[field] = value
    result = resolve(record)
    assert result.disposition == ResolverDisposition.REFUSED
    assert result.value is None


def test_proposed_source_a_binding_is_not_numeric_acceptance():
    import json
    from pathlib import Path

    proposal = json.loads(
        Path("docs/research/ratings/week4/source-a-p-binding-proposal.json").read_text()
    )
    assert proposal["status"] == "proposed_pending_b_review"
    assert proposal["numeric_reuse_permitted"] is False
    assert len(proposal["historical_candidates"]) == 2
    assert len(proposal["binding_inventory"]) == 8
    assert all(b["status"] == "proposed_pending_b_review" for b in proposal["binding_inventory"])
    assert all("lower" not in b and "upper" not in b for b in proposal["binding_inventory"])


def test_private_generated_source_a_proposal_reproduces_exact_inventory():
    import json
    import os
    from pathlib import Path

    from scripts.research.rating_p_binding_probe import probe_generated_source_a
    from src.engine.semantics.evidence_view import digest

    raw_dir = Path(os.environ.get("SEAMLESS_RAW_DIR", "data/raw/SEAMLESS"))
    if not raw_dir.is_dir():
        pytest.skip("manifest-verified private SEAMLESS raw inputs required")
    report = probe_generated_source_a(raw_dir)
    proposal = json.loads(
        Path("docs/research/ratings/week4/source-a-p-binding-proposal.json").read_text()
    )
    assert report["candidate_source"] == "generate_attack_paths"
    assert report["numeric_reuse_permitted"] is False
    assert report["truncated"] is True
    assert report["historical_candidates"] == proposal["historical_candidates"]
    assert len(report["binding_inventory"]) == 8
    for actual, pinned in zip(
        report["binding_inventory"], proposal["binding_inventory"], strict=True
    ):
        assert actual["status"] == "proposed_pending_b_review"
        assert actual["source_record_digest"] == pinned["source_record_digest"]
        assert digest(actual["generated_lookup_key"]) == pinned["generated_lookup_key_digest"]
        assert digest(actual["legacy_lookup_key"]) == pinned["legacy_lookup_key_digest"]
        assert actual["provider_trace"][0]["disposition"] == "refused"
        assert actual["reason_detail"].startswith(
            (
                "Likelihood prefix applicability not reviewed",
                "Legacy packet has no reviewed applicability context",
            )
        )


@pytest.mark.parametrize("value", ["different-work-unit", 12, None])
def test_contradictory_or_malformed_outcome_alias_refuses(value):
    record = {**accepted_test_record(lookup()), "outcome_unit": value}
    assert resolve(record).disposition == ResolverDisposition.REFUSED
    assert resolve(record).value is None


@pytest.mark.parametrize("field", ["retry_policy", "actor_capability", "target_population"])
def test_distinct_optional_contexts_do_not_conflict(field):
    record = {**accepted_test_record(lookup()), field: "context-A"}
    other = {**record, field: "context-B", "lower": "1/4", "upper": "1/3"}
    result = ReviewedScenarioLikelihoodProvider([record, other]).resolve_likelihood(
        lookup(), PREFIX, PREFIX[-1], {field: "context-A"}
    )
    assert result.disposition == ResolverDisposition.RATED
    assert result.value == (Fraction(1, 2), Fraction(3, 4))
