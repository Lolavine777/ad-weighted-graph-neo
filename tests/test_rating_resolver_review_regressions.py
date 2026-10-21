"""Regressions for review findings in PR #252, through the canonical evaluator."""

import json
from copy import deepcopy
from dataclasses import replace
from fractions import Fraction
from pathlib import Path

import pytest
from test_rating_resolver import (
    DUMMY_EDGE_1,
    FOOTHOLD_SID,
    OTHER_HOST_ID,
    TARGET_HOST_ID,
    build_test_scope,
)

from src.engine.ranking import PathRankingEngine, RankingValidationError
from src.engine.ranking.resolver import (
    BasisClassification,
    RatingResolver,
    ResolutionResult,
    ResolverDisposition,
)
from src.engine.search import PathResult, TransitionStep
from src.engine.semantics.models import Effect, Technique
from src.engine.semantics.state import AttackState
from src.engine.semantics.transitions import Status, TransitionRequest, TransitionResult


class SyntheticRatings:
    name = "synthetic_review_regression"
    provider_version = "1.0.0"

    def resolve_effort(self, key, record, scope):
        cost = 2 if key.auth_context == "ntlm" else 1
        return ResolutionResult(
            ResolverDisposition.RATED,
            cost,
            provider_name=self.name,
            basis_category=BasisClassification.SYNTHETIC_TEST_ONLY,
            rubric_scores={"t1": 1, "t2": cost + 1, "computed_cost": cost},
        )

    def resolve_likelihood(self, key, prefix, outcome, scope):
        q = Fraction(3, 4) if key.auth_context == "ntlm" else Fraction(1, 2)
        return ResolutionResult(
            ResolverDisposition.RATED,
            (q, q),
            provider_name=self.name,
            basis_category=BasisClassification.SYNTHETIC_TEST_ONLY,
        )

    def resolve_impact(self, key, target, event, scope):
        return ResolutionResult(
            ResolverDisposition.RATED,
            "High",
            provider_name=self.name,
            basis_category=BasisClassification.SYNTHETIC_TEST_ONLY,
        )


def rated_resolver():
    p = SyntheticRatings()
    return RatingResolver(effort_providers=[p], likelihood_providers=[p], impact_providers=[p])


def declared_step(**overrides):
    return {
        "technique_id": "obtain_admin_execution_on_host",
        "actor": FOOTHOLD_SID,
        "target": TARGET_HOST_ID,
        "edge_id": DUMMY_EDGE_1,
        "provenance": ["synthetic://review-regression/edge"],
        "requires": ["actor_controlled_alice"],
        "adds": ["admin_control_host"],
        **overrides,
    }


def evaluated(output):
    return PathRankingEngine().evaluate(output.ranking_query, output.candidate_envelopes)[
        "result_payload"
    ]


def test_context_ratings_and_coverage_are_invariant_under_candidate_order():
    candidates = [
        {"candidate_id": ctx, "transition_history": [declared_step(auth_context=ctx)]}
        for ctx in ("kerberos", "ntlm")
    ]
    first = rated_resolver().resolve(candidates, build_test_scope())
    second = rated_resolver().resolve(candidates[::-1], build_test_scope())
    assert first.coverage_report == second.coverage_report
    ratings = evaluated(first)["eligible_candidates"]
    assert ratings == evaluated(second)["eligible_candidates"]
    assert ratings["kerberos"]["effort"] == 1
    assert ratings["ntlm"]["effort"] == 2
    assert ratings["kerberos"]["likelihood_interval"] == (Fraction(1, 2), Fraction(1, 2))
    assert ratings["ntlm"]["likelihood_interval"] == (Fraction(3, 4), Fraction(3, 4))


@pytest.mark.parametrize(
    "field,values",
    [
        ("source", (FOOTHOLD_SID, OTHER_HOST_ID)),
        ("resource_context", ("winrm", "rpc")),
        ("policy_id", ("policy-a", "policy-b")),
        ("method", ("winrm", "wmi")),
    ],
)
def test_work_identity_preserves_applicability_before_deduplication(field, values):
    candidates = [
        {"candidate_id": str(i), "transition_history": [declared_step(**{field: value})]}
        for i, value in enumerate(values)
    ]
    output = rated_resolver().resolve(candidates, build_test_scope())
    assert len(output.ranking_query["work_units_ledger"]) == 2
    assert len(output.ranking_query["conditional_bounds_table"]) == 2
    assert len(evaluated(output)["eligible_candidates"]) == 2


def test_conflicting_explicit_work_identity_fails_in_both_orders():
    candidates = [
        {
            "candidate_id": ctx,
            "transition_history": [
                declared_step(auth_context=ctx, referenced_work_unit_ids=["shared-id"])
            ],
        }
        for ctx in ("kerberos", "ntlm")
    ]
    for order in (candidates, candidates[::-1]):
        with pytest.raises(RankingValidationError, match="Conflicting applicability"):
            rated_resolver().resolve(order, build_test_scope())


def explicit_case():
    packet = json.loads(
        (Path(__file__).parents[1] / "docs/research/ratings/week4/synthetic-a2-e.json").read_text()
    )["query"]
    action = packet["bound_actions"][0]
    step = declared_step(
        edge_id=action["edge_id"],
        requires=action["requires"],
        adds=action["adds"],
        referenced_work_unit_ids=action["referenced_work_unit_ids"],
    )
    scope = {**deepcopy(packet["query_metadata"]), "facts_ledger": deepcopy(packet["facts_ledger"])}
    return packet, {"candidate_id": "explicit", "transition_history": [step]}, scope


@pytest.mark.parametrize(
    "field,value",
    [
        ("snapshot_id", "sha256:" + "b" * 64),
        ("scenario_id", "different"),
        ("scenario_version", "2.0.0"),
        ("horizon", "72h"),
        ("active_work_budget", 20),
        ("work_boundary", "different"),
        ("policy_id", "different"),
    ],
)
def test_reviewed_packet_scope_mismatch_refuses_all_dimensions_without_fallback(field, value):
    packet, candidate, scope = explicit_case()
    scope[field] = value
    p = SyntheticRatings()
    resolver = RatingResolver(
        explicit_packet=packet, effort_providers=[p], likelihood_providers=[p], impact_providers=[p]
    )
    output = resolver.resolve([candidate], scope)
    gaps = output.coverage_report["unresolved_gaps"]
    assert {g["dimension"] for g in gaps} == {"C", "P", "I"}
    assert all(g["disposition"] == "refused" and g["reason_code"] == "out_of_scope" for g in gaps)
    assert all(len(g["provider_trace"]) == 1 for g in gaps)
    assert not evaluated(output)["eligible_candidates"]


def test_success_event_and_record_consequence_scope_are_not_reused():
    packet, candidate, scope = explicit_case()
    scope["target_goal"]["success_event"] = "different_event"
    output = RatingResolver(explicit_packet=packet).resolve([candidate], scope)
    assert output.coverage_report["candidates"]["explicit"]["impact"]["disposition"] == "refused"
    assert not evaluated(output)["eligible_candidates"]
    packet, candidate, scope = explicit_case()
    packet["target_impact_assessments"][TARGET_HOST_ID]["consequence_scope"] = "other"
    output = RatingResolver(explicit_packet=packet).resolve([candidate], scope)
    assert output.coverage_report["candidates"]["explicit"]["impact"]["disposition"] == "refused"
    assert not evaluated(output)["eligible_candidates"]


def test_packet_full_history_rejects_changed_context_in_earlier_work():
    packet, candidate, scope = explicit_case()
    first = deepcopy(candidate["transition_history"][0])
    first["referenced_work_unit_ids"] = ["w-auth-context"]
    first["auth_context"] = "ntlm"
    second = deepcopy(candidate["transition_history"][0])
    second["referenced_work_unit_ids"] = ["w-direct-admin"]
    candidate["transition_history"] = [first, second]
    output = RatingResolver(explicit_packet=packet).resolve([candidate], scope)
    entries = output.coverage_report["candidates"]["explicit"]["likelihood"]["prefixes"]
    assert len(entries) == 2
    assert all(entry["disposition"] == "refused" for entry in entries)
    assert not evaluated(output)["eligible_candidates"]


def actual_path(edge_ids):
    technique = Technique(
        id="obtain_admin_execution_on_host",
        relationship="AdminTo",
        semantic_class="host_admin",
        source_kinds=("User",),
        target_kinds=("Computer",),
        action_required=True,
        prerequisites=("actor_controlled",),
        effects=(Effect.ADMIN_CONTROL,),
        failure_conditions=(),
        expected_telemetry=(),
        attack_refs=(),
        confidence="high",
        cost_factors=(),
        remediation=(),
    )
    initial = AttackState(control={FOOTHOLD_SID})
    history = []
    before = initial
    targets = [OTHER_HOST_ID] * (len(edge_ids) - 1) + [TARGET_HOST_ID]
    edges = []
    for idx, (edge_id, target) in enumerate(zip(edge_ids, targets, strict=True)):
        result = TransitionResult(
            TransitionRequest(technique.id, FOOTHOLD_SID, FOOTHOLD_SID, target),
            technique,
            Status.APPLICABLE,
            before,
            AttackState(admin_control={target}),
            satisfied=("actor_controlled",),
        )
        history.append(
            TransitionStep(result, edge_id, idx - 1 if idx and edge_id is None else None)
        )
        before = replace(before, admin_control=before.admin_control | {target})
        if edge_id is not None:
            edges.append(
                {
                    "id": edge_id,
                    "source": FOOTHOLD_SID,
                    "target": target,
                    "provenance": ["synthetic://actual-path/declared-edge"],
                }
            )
    return PathResult(
        (FOOTHOLD_SID, *targets),
        tuple(edges),
        transition_history=tuple(history),
        final_state=before,
        scenario_reference="scenario-test-enterprise",
    )


def predicate_bindings(path):
    return {
        (
            step.result.request.technique_id,
            FOOTHOLD_SID,
            FOOTHOLD_SID,
            step.result.request.target,
        ): {
            "requires": ["actor_controlled_alice"],
            "predicate_layers": {"admin_control_host": 3, "admin_control_other_host": 3},
            "adds": ["admin_control_host"]
            if step.result.request.target == TARGET_HOST_ID
            else ["admin_control_other_host"],
        }
        for step in path.transition_history
    }


@pytest.mark.parametrize("edges", [(DUMMY_EDGE_1,), (None,), (DUMMY_EDGE_1, None)])
def test_actual_path_results_roundtrip_with_explicit_semantics_and_authentic_lineage(edges):
    path = actual_path(edges)
    assert TARGET_HOST_ID in path.final_state.admin_control
    output = rated_resolver().resolve(
        [path], build_test_scope(), transition_bindings=predicate_bindings(path)
    )
    envelope = output.candidate_envelopes[0]
    assert [e for r in envelope["structural_routes"] for e in r["edge_ids"]] == [
        e for e in edges if e is not None
    ]
    assert [r["edge_id"] for r in envelope["transition_lineage"]] == list(edges)
    assert [r["derived_from_step"] for r in envelope["transition_lineage"]] == [
        s.derived_from_step for s in path.transition_history
    ]
    assert envelope["transition_audit"][0]["decision"]["before"]["control"] == [FOOTHOLD_SID]
    assert all(
        not p.startswith("predicate_")
        for p in output.ranking_query["facts_ledger"]["predicate_layers"]
    )
    assert "Candidate_1" in evaluated(output)["eligible_candidates"]
    if len(edges) == 2:
        assert envelope["transition_lineage"][1]["origin"] == "derived_transition"


def test_actual_transition_without_predicate_binding_fails_closed():
    with pytest.raises(RankingValidationError, match="explicit predicate binding"):
        rated_resolver().resolve([actual_path((None,))], build_test_scope())


def test_generated_search_path_reaches_the_canonical_evaluator():
    from src.engine.graph import EngineGraph
    from src.engine.search import SearchBudget, generate_attack_paths
    from src.engine.semantics import FactOrigin, RuntimeContext, RuntimeFact, load_catalog

    graph = EngineGraph.from_canonical(
        json.loads(
            (
                Path(__file__).parents[1] / "tests/fixtures/attack_scenarios/graphs/two-routes.json"
            ).read_text()
        )
    )
    runtime = RuntimeContext(
        [
            RuntimeFact(
                predicate,
                FOOTHOLD_SID,
                TARGET_HOST_ID,
                True,
                FactOrigin.DECLARED_ASSUMPTION,
                scope="synthetic-test",
                rationale="Synthetic resolver integration precondition",
            )
            for predicate in ("admin_channel", "authentication_accepted")
        ]
    )
    search = generate_attack_paths(
        graph,
        FOOTHOLD_SID,
        initial_state=AttackState(control={FOOTHOLD_SID}),
        runtime_context=runtime,
        target_predicate=lambda n: n["id"] == TARGET_HOST_ID,
        success_state_predicate=lambda s: TARGET_HOST_ID in s.admin_control,
        budget=SearchBudget(3, 1, 10),
        scenario_reference="scenario-test-enterprise",
        catalog=tuple(t for t in load_catalog() if t.id == "obtain_admin_execution_on_host"),
    )
    assert search.paths
    path = search.paths[0]
    scope = build_test_scope(snapshot_id=graph.metadata["snapshot_id"])
    output = rated_resolver().resolve([path], scope, transition_bindings=predicate_bindings(path))
    assert evaluated(output)["eligible_candidates"]
    assert output.candidate_envelopes[0]["edge_provenance_map"] == {
        edge["id"]: edge["provenance"] for edge in path.edges
    }


def test_missing_observed_provenance_is_not_fabricated():
    path = actual_path((DUMMY_EDGE_1,))
    path = replace(path, edges=({k: v for k, v in path.edges[0].items() if k != "provenance"},))
    with pytest.raises(RankingValidationError, match="lacks authentic"):
        rated_resolver().resolve(
            [path], build_test_scope(), transition_bindings=predicate_bindings(path)
        )


@pytest.mark.parametrize("cost", [3, 4])
def test_rated_effort_requires_reviewed_rubric(cost):
    class NoRubric(SyntheticRatings):
        def resolve_effort(self, key, record, scope):
            return ResolutionResult(ResolverDisposition.RATED, cost)

    with pytest.raises(RankingValidationError, match="requires explicit rubric_scores"):
        RatingResolver(effort_providers=[NoRubric()]).resolve(
            [{"candidate_id": "x", "transition_history": [declared_step()]}], build_test_scope()
        )


@pytest.mark.parametrize("cost", [True, 1.5, "2"])
def test_effort_cost_is_an_exact_integer_without_coercion(cost):
    class BadCost(SyntheticRatings):
        def resolve_effort(self, key, record, scope):
            return ResolutionResult(
                ResolverDisposition.RATED,
                cost,
                rubric_scores={"t1": 1, "t2": 3, "computed_cost": 2},
            )

    with pytest.raises(RankingValidationError, match="exact integer"):
        RatingResolver(effort_providers=[BadCost()]).resolve(
            [{"candidate_id": "x", "transition_history": [declared_step()]}], build_test_scope()
        )


@pytest.mark.parametrize("cost,t1,t2", [(3, 2, 3), (4, 3, 3), (0, 1, 1)])
def test_high_and_zero_costs_preserve_declared_rubric_through_evaluator(cost, t1, t2):
    class Rubric(SyntheticRatings):
        def resolve_effort(self, key, record, scope):
            return ResolutionResult(
                ResolverDisposition.RATED,
                cost,
                rubric_scores={"t1": t1, "t2": t2, "computed_cost": cost},
            )

    provider = Rubric()
    output = RatingResolver(
        effort_providers=[provider], likelihood_providers=[provider], impact_providers=[provider]
    ).resolve([{"candidate_id": "x", "transition_history": [declared_step()]}], build_test_scope())
    assert evaluated(output)["eligible_candidates"]["x"]["effort"] == cost
    assert next(iter(output.ranking_query["work_units_ledger"].values()))["rubric_scores"] == {
        "t1": t1,
        "t2": t2,
        "computed_cost": cost,
    }


@pytest.mark.parametrize("reverse", [False, True])
@pytest.mark.parametrize(
    "changed", ["cost", "rubric", "rating_status", "technique", "target_id", "auth_context"]
)
def test_shared_preparation_conflicts_fail_before_evaluation(reverse, changed):
    prep = {
        "work_unit_id": "shared-prep",
        "technique": "auth_context",
        "rating_status": "rated",
        "computed_cost": 1,
        "rubric_scores": {"t1": 1, "t2": 2, "computed_cost": 1},
    }
    other = deepcopy(prep)
    if changed == "cost":
        other.update(computed_cost=2, rubric_scores={"t1": 1, "t2": 3, "computed_cost": 2})
    elif changed == "rubric":
        other["rubric_scores"] = {"t1": 2, "t2": 1, "computed_cost": 1}
    elif changed == "rating_status":
        other.update(rating_status="unrated", computed_cost=None, rubric_scores=None)
    else:
        other[changed] = OTHER_HOST_ID if changed == "target_id" else "different"
    candidates = [
        {"candidate_id": k, "transition_history": [declared_step(shared_prep_key=k)]}
        for k in ("one", "two")
    ]
    if reverse:
        candidates.reverse()
    with pytest.raises(RankingValidationError, match="Conflicting shared preparation"):
        evaluated(
            rated_resolver().resolve(
                candidates, build_test_scope(), shared_preparation_units={"one": prep, "two": other}
            )
        )


def test_identical_shared_preparations_keep_own_context_and_order_invariant_effort():
    prep = {
        "work_unit_id": "shared-prep",
        "technique": "setup",
        "actor_id": FOOTHOLD_SID,
        "source_id": FOOTHOLD_SID,
        "target_id": OTHER_HOST_ID,
        "method": "setup-method",
        "auth_context": "setup-auth",
        "resource_context": "setup-resource",
        "rating_status": "rated",
        "computed_cost": 1,
        "rubric_scores": {"t1": 1, "t2": 2, "computed_cost": 1},
    }
    candidates = [
        {"candidate_id": k, "transition_history": [declared_step(shared_prep_key=k, method=k)]}
        for k in ("one", "two")
    ]
    first = rated_resolver().resolve(
        candidates,
        build_test_scope(),
        shared_preparation_units={"one": prep, "two": deepcopy(prep)},
    )
    second = rated_resolver().resolve(
        candidates[::-1],
        build_test_scope(),
        shared_preparation_units={"one": prep, "two": deepcopy(prep)},
    )
    assert first.coverage_report == second.coverage_report
    assert evaluated(first)["eligible_candidates"] == evaluated(second)["eligible_candidates"]
    assert all(c["effort"] == 2 for c in evaluated(first)["eligible_candidates"].values())
    record = first.ranking_query["work_units_ledger"]["shared-prep"]
    for field in (
        "technique",
        "actor_id",
        "source_id",
        "target_id",
        "method",
        "auth_context",
        "resource_context",
    ):
        assert record[field] == prep[field]


@pytest.mark.parametrize("layer", [1, 2])
def test_authoritative_observed_layers_roundtrip_without_redundant_map(layer):
    scope = build_test_scope()
    scope["facts_ledger"] = {
        "observed_facts": [
            {
                "predicate": "actor_controlled_alice",
                "layer": layer,
                "truth_value": True,
                "provenance_reference": "synthetic://layer-regression",
            }
        ]
    }
    output = rated_resolver().resolve(
        [
            {
                "candidate_id": "layer",
                "transition_history": [declared_step(predicate_layers={"admin_control_host": 3})],
            }
        ],
        scope,
    )
    assert output.ranking_query["facts_ledger"]["predicate_layers"] == {
        "actor_controlled_alice": layer,
        "admin_control_host": 3,
    }
    assert "layer" in evaluated(output)["eligible_candidates"]


@pytest.mark.parametrize(
    "bucket,record",
    [
        ("false_facts", {"layer": 2, "truth_value": False}),
        ("unknown_facts", {"layer": 2}),
        ("assumed_facts", {"layer": 3, "truth_value": True, "rationale": "synthetic test"}),
    ],
)
def test_authoritative_layers_from_other_fact_buckets(bucket, record):
    scope = build_test_scope()
    scope["facts_ledger"] = {bucket: [{"predicate": "actor_controlled_alice", **record}]}
    output = rated_resolver().resolve(
        [
            {
                "candidate_id": "bucket",
                "transition_history": [declared_step(predicate_layers={"admin_control_host": 3})],
            }
        ],
        scope,
    )
    assert (
        output.ranking_query["facts_ledger"]["predicate_layers"]["actor_controlled_alice"]
        == record["layer"]
    )
    evaluated(output)


def test_runtime_effect_without_authoritative_layer_is_rejected():
    scope = build_test_scope()
    del scope["facts_ledger"]["predicate_layers"]["admin_control_host"]
    with pytest.raises(
        RankingValidationError, match="Missing authoritative predicate layers.*admin_control_host"
    ):
        rated_resolver().resolve([{"transition_history": [declared_step()]}], scope)


def reviewed_bundle():
    return json.loads(
        (
            Path(__file__).parents[1] / "docs/research/ratings/week3-closeout/reviewed-release.json"
        ).read_text()
    )


@pytest.mark.parametrize("projection", ["source_a", "source_b"])
def test_real_seamless_bundle_selects_projection_and_preserves_ratings(projection):
    from src.engine.ranking.resolver import (
        ExplicitPacketRatingProvider,
        generate_rating_lookup_key_c,
        generate_rating_lookup_key_i,
        generate_rating_lookup_key_p,
    )

    bundle = reviewed_bundle()
    original = deepcopy(bundle)
    query = bundle["query_projections"][projection]["query"]
    scope = query["query_metadata"]
    provider = ExplicitPacketRatingProvider(bundle)
    records = {}
    for uid, record in query["work_units_ledger"].items():
        action = next(a for a in query["bound_actions"] if uid in a["referenced_work_unit_ids"])
        key = generate_rating_lookup_key_c(
            uid,
            action["technique"],
            action["actor_id"],
            action["target_id"],
            source_id=action["actor_id"],
            boundary=scope["work_boundary"],
            scope=scope["scenario_id"],
        )
        result = provider.resolve_effort(key, record, scope)
        assert result.disposition == ResolverDisposition.RATED
        assert result.value == record["computed_cost"]
        assert result.rubric_scores == record["rubric_scores"]
        assert result.basis_category == scope["governance"]["basis_category"]
        assert result.provenance_digest == scope["bundle_digest"]
        records[uid] = {**key.to_dict(), "method": "default", "source_id": action["actor_id"]}
    for bounds in query["conditional_bounds_table"]:
        prefix = tuple(bounds["prefix"])
        rec = records[prefix[-1]]
        key = generate_rating_lookup_key_p(
            scenario_id=scope["scenario_id"],
            scenario_version=scope["scenario_version"],
            snapshot_id=scope["snapshot_id"],
            foothold_node_id=scope["foothold_node_id"],
            ordered_work_prefix=prefix,
            outcome_work_unit_id=prefix[-1],
            outcome_technique=rec["technique"],
            actor_id=rec["actor_id"],
            target_id=rec["target_id"],
            source_id=rec["source_id"],
            budget=scope["active_work_budget"],
            horizon=scope["horizon"],
            boundary=scope["work_boundary"],
            scope=scope["scenario_id"],
        )
        result = provider.resolve_likelihood(
            key, prefix, prefix[-1], {**scope, "resolved_work_units": records}
        )
        assert result.disposition == ResolverDisposition.RATED
        assert result.value == (Fraction(bounds["lower"]), Fraction(bounds["upper"]))
        assert result.basis_category == bounds["basis_category"]
    goal = scope["target_goal"]
    key = generate_rating_lookup_key_i(
        goal["target_asset_id"],
        goal["success_event"],
        consequence_scope=scope["work_boundary"],
        boundary=scope["work_boundary"],
        scenario_id=scope["scenario_id"],
    )
    result = provider.resolve_impact(key, goal["target_asset_id"], goal["success_event"], scope)
    assert result.disposition == ResolverDisposition.RATED
    assert (
        result.value
        == query["target_impact_assessments"][goal["target_asset_id"]]["consequence_rating"]
    )
    assert bundle == original


@pytest.mark.parametrize("ambiguous", [False, True])
def test_bundle_unknown_or_ambiguous_query_projection_is_refused(ambiguous):
    from src.engine.ranking.resolver import (
        ExplicitPacketRatingProvider,
        generate_rating_lookup_key_c,
    )

    bundle = reviewed_bundle()
    scope = deepcopy(bundle["query_projections"]["source_a"]["query"]["query_metadata"])
    if ambiguous:
        bundle["query_projections"]["duplicate"] = deepcopy(bundle["query_projections"]["source_a"])
    else:
        scope["query_id"] = "unknown"
    key = generate_rating_lookup_key_c("unit", "technique", FOOTHOLD_SID, TARGET_HOST_ID)
    result = ExplicitPacketRatingProvider(bundle).resolve_effort(key, {}, scope)
    assert result.disposition == ResolverDisposition.REFUSED


class AuditedRatings(SyntheticRatings):
    def __init__(self, version, digest, review):
        self.version, self.digest, self.review = version, digest, review

    def metadata(self, result):
        return replace(
            result,
            provider_version=self.version,
            provenance_digest=self.digest,
            review_reference=self.review,
        )

    def resolve_effort(self, *args):
        return self.metadata(super().resolve_effort(*args))

    def resolve_likelihood(self, *args):
        return self.metadata(super().resolve_likelihood(*args))

    def resolve_impact(self, *args):
        return self.metadata(super().resolve_impact(*args))


def test_selected_metadata_is_retained_per_dimension_in_wire_coverage_and_trace():
    outputs = []
    for version, digest, review in [
        ("2.0.0", "sha256:" + "f" * 64, "https://example.test/review/1"),
        ("3.0.0", "sha256:" + "e" * 64, "https://example.test/review/2"),
    ]:
        p = AuditedRatings(version, digest, review)
        output = RatingResolver(
            effort_providers=[p], likelihood_providers=[p], impact_providers=[p]
        ).resolve(
            [{"candidate_id": "audit", "transition_history": [declared_step()]}], build_test_scope()
        )
        outputs.append(output)
        query = output.ranking_query
        wire_records = [
            next(iter(query["work_units_ledger"].values())),
            query["conditional_bounds_table"][0],
            next(iter(query["target_impact_assessments"].values())),
        ]
        for record in wire_records:
            audit = record["rating_audit"]
            assert audit["provider_version"] == version
            assert audit["provenance_digest"] == digest
            assert audit["review_reference"] == review
            assert audit["lookup_key"]
            assert audit["scope_binding"] == query["query_metadata"]
            assert json.dumps(audit) in json.dumps(output.coverage_report)
        serialized = json.dumps(output.coverage_report)
        for field, value in [
            ("provider_version", version),
            ("provenance_digest", digest),
            ("review_reference", review),
        ]:
            assert serialized.count(json.dumps(field) + ": " + json.dumps(value)) >= 6
        assert "audit" in evaluated(output)["eligible_candidates"]
    for field in ("effort", "likelihood_interval", "consequence_rating"):
        assert (
            evaluated(outputs[0])["eligible_candidates"]["audit"][field]
            == evaluated(outputs[1])["eligible_candidates"]["audit"][field]
        )
    assert outputs[0].coverage_report != outputs[1].coverage_report
    assert outputs[0].ranking_query != outputs[1].ranking_query
