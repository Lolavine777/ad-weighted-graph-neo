"""Independent finite expectations for acquired privileged identity goals."""

import copy
import json
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError
from test_engine import ACTOR, GROUP, HOST, TOY, _auditable_context, _edge, _graph

from scripts.research.source_goal_batch import TargetManifest
from src.engine.batch import BatchExecutionBudget, run_source_goal_batch, validate_schema
from src.engine.query import (
    IdentityResolver,
    SemanticGoalDescriptor,
    UsableIdentityEntitlementGoal,
    materialize_query,
    run_attack_query,
    semantic_goal_from_dict,
)
from src.engine.query_cli import execute, wire
from src.engine.ranking import RankingValidationError
from src.engine.ranking.adapter_145 import adapt_search_candidate
from src.engine.ranking.resolution_service import _impact_goal_guard, canonical_digest
from src.engine.ranking.resolver import ResolutionResult, ResolverDisposition
from src.engine.ranking.verification import verify_search_envelope
from src.engine.semantics import AttackState, FactOrigin
from src.engine.semantics.credentials import replay_path

OTHER = "S-1-5-21-1000-2000-3000-1102"
ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def scenario():
    node = copy.deepcopy(next(n for n in TOY["nodes"] if n["id"] == ACTOR))
    node.update(id=OTHER, label="Synthetic acquired identity", enabled=True)
    graph = _graph(
        [_edge(ACTOR, OTHER, "GenericAll"), _edge(OTHER, GROUP, "MemberOf")],
        extra_nodes=[node],
    )
    gates = {
        (p, ACTOR, OTHER): True
        for p in ("password_policy_accepts", "directory_write_allowed", "network_rpc_reachable")
    }
    gates.update(
        {(p, OTHER, HOST): True for p in ("network_kdc_reachable", "authentication_accepted")}
    )
    gates.update({(p, OTHER, GROUP): True for p in ("security_group", "membership_usable")})
    assumptions = tuple(
        replace(f, provenance_reference="synthetic://identity-goal")
        for f in _auditable_context(gates).facts.values()
    )
    return graph, {
        "initial_actor": ACTOR,
        "initial_state": {"control": [ACTOR]},
        "target": GROUP,
        "authentication_context": HOST,
        "assumptions": assumptions,
        "target_goal": {"target": GROUP, "kind": "usable_identity_entitlement"},
        "allowed_techniques": [
            "scenario_reset_password",
            "acquire_reset_identity",
            "propagate_group_entitlement",
        ],
        "budget": {"max_paths": 100, "max_steps": 6, "max_expansions": 1000},
        "scenario_reference": "synthetic-identity-goal",
    }


@pytest.mark.parametrize(
    "usable,members,expected",
    [
        ([(OTHER, HOST)], [(OTHER, GROUP)], True),
        ([(OTHER, HOST)], [(ACTOR, GROUP)], False),
        ([(OTHER, ACTOR)], [(OTHER, GROUP)], False),
        ([], [(OTHER, GROUP)], False),
        ([(OTHER, HOST)], [], False),
    ],
)
def test_same_identity_and_context_are_necessary(usable, members, expected):
    assert (
        UsableIdentityEntitlementGoal(GROUP, HOST).matches(
            AttackState(usable_identity=usable, effective_member=members)
        )
        is expected
    )


def test_acquired_identity_and_legacy_scope_have_distinct_expected_results(scenario):
    graph, query = scenario
    result = run_attack_query(query, graph)
    assert result.final_goal_reached and result.complete and not result.truncated
    assert [
        [s.result.request.technique_id for s in p.transition_history] for p in result.paths
    ] == [["scenario_reset_password", "acquire_reset_identity", "propagate_group_entitlement"]]
    assert [s.result.request.actor for s in result.paths[0].transition_history] == [
        ACTOR,
        OTHER,
        OTHER,
    ]
    for path in result.paths:
        replay_path(path, graph)
    query["target_goal"] = {
        "target": GROUP,
        "required_state": {"effective_member": [[ACTOR, GROUP]]},
    }
    legacy = run_attack_query(query, graph)
    assert not legacy.final_goal_reached and legacy.is_no_path_proven_over_scope
    old = SemanticGoalDescriptor(GROUP, AttackState(effective_member=[(ACTOR, GROUP)]))
    assert legacy.materialized_query.semantic_goal.to_dict() == old.to_dict()
    assert semantic_goal_from_dict(old.to_dict(), IdentityResolver({})) == old


@pytest.mark.parametrize(
    "gate", ["activation_absent", "auth_false", "auth_unknown", "callable_false"]
)
def test_missing_prerequisites_and_extra_callable_are_not_bypassed(scenario, gate):
    graph, query = scenario
    if gate == "activation_absent":
        query["allowed_techniques"].remove("acquire_reset_identity")
    elif gate in ("auth_false", "auth_unknown"):
        query["assumptions"] = tuple(
            f for f in query["assumptions"] if f.predicate != "authentication_accepted"
        )
        if gate == "auth_false":
            query["runtime_facts"] = tuple(
                replace(
                    f,
                    origin=FactOrigin.OBSERVED_EVIDENCE,
                    provenance_reference="synthetic://auth-false",
                )
                for f in _auditable_context(
                    {("authentication_accepted", OTHER, HOST): False}
                ).facts.values()
            )
    else:
        query["success_state_predicate"] = lambda state: False
    result = run_attack_query(query, graph)
    assert not result.paths and not result.final_goal_reached
    if gate == "auth_unknown":
        assert result.status == "indeterminate" and not result.is_no_path_proven_over_scope


@pytest.mark.parametrize("mutation", ["context", "target_kind", "ambiguous", "kind"])
def test_invalid_or_cross_context_goal_is_refused(scenario, mutation):
    graph, query = scenario
    if mutation == "context":
        query["target_goal"]["authentication_context"] = ACTOR
    elif mutation == "target_kind":
        query["target"] = query["target_goal"]["target"] = HOST
    elif mutation == "ambiguous":
        query["target_goal"]["required_state"] = {"control": [ACTOR]}
    else:
        query["target_goal"]["kind"] = "unknown_goal"
    with pytest.raises(ValueError):
        materialize_query(query, graph)


def test_wire_cli_and_replay_binding_refuse_forged_final_state(scenario):
    graph, query = scenario
    public_query = json.loads(json.dumps(wire(query)))
    assert execute(public_query, graph)["final_goal_reached"]
    result = run_attack_query(public_query, graph)
    path = result.paths[0]
    descriptor = result.materialized_query.semantic_goal.to_dict()
    schema = json.loads((ROOT / "docs/research/public-rating-coverage.schema.json").read_text())
    Draft202012Validator({"$ref": "#/$defs/semanticGoal", "$defs": schema["$defs"]}).validate(
        descriptor
    )
    metadata = dict(
        query_id="identity-goal",
        scenario_id="synthetic-identity-goal",
        scenario_version="1.0.0",
        snapshot_id=graph.metadata["snapshot_id"],
        work_boundary="intra_forest",
        horizon="24h",
        foothold_node_id=ACTOR,
        semantic_goal=descriptor,
    )
    envelope = adapt_search_candidate(
        path_result=path,
        candidate_id="acquired",
        target_asset_id=GROUP,
        query_metadata=metadata,
        action_mapping=["reset", "activate", "membership"],
        success_event="synthetic_group_entitlement",
    )
    proof = verify_search_envelope(path, graph, envelope, metadata)
    assert proof.matches(envelope, metadata)
    assert [proof.state_goal_matches_prefix(i) for i in range(4)] == [False, False, False, True]
    forged = copy.deepcopy(envelope)
    forged["state_goal_binding"]["final_state_digest"] = "sha256:" + "0" * 64
    with pytest.raises(RankingValidationError, match="final capability"):
        verify_search_envelope(path, graph, forged, metadata)
    assert not proof.matches(forged, metadata)
    metadata["semantic_goal"]["required_state"] = {"control": [ACTOR]}
    with pytest.raises(RankingValidationError, match="Malformed"):
        verify_search_envelope(path, graph, envelope, metadata)


@pytest.mark.parametrize("worker", [False, True])
def test_batch_successor_is_explicit_and_legacy_serialization_is_unchanged(scenario, worker):
    graph, query = scenario
    raw = json.loads(
        (ROOT / "tests/fixtures/batch_contracts/batch_request_example.json").read_text()
    )
    legacy = TargetManifest.from_dict(raw["target_manifest"]).to_dict()
    assert legacy["schema_version"] == "target-manifest/1.0.0"
    assert all("goal_kind" not in t for t in legacy["targets"])
    goal = raw["target_manifest"]["targets"][0]
    goal.update(target_node_id=GROUP, goal_kind="usable_identity_entitlement", required_state={})
    raw["target_manifest"].update(
        schema_version="target-manifest/1.1.0",
        snapshot_id=graph.metadata["snapshot_id"],
        targets=[goal],
        default_discovery_goals=[goal["goal_id"]],
    )
    source = raw["sources"][0]
    source.update(
        node_id=ACTOR, authentication_context=HOST, declared_assumptions=wire(query["assumptions"])
    )
    raw.update(snapshot_id=graph.metadata["snapshot_id"], sources=[source])
    limits = BatchExecutionBudget(per_query_seconds=30) if worker else None
    result = run_source_goal_batch(
        raw, graph, allowed_techniques=query["allowed_techniques"], execution_budget=limits
    )
    assert result.summary["successful_cells"] == 1
    source["authentication_context"] = ACTOR
    result = run_source_goal_batch(raw, graph, allowed_techniques=query["allowed_techniques"])
    cell = result.source_goal_matrix[source["source_id"]][goal["goal_id"]]
    assert cell.status.value == "unsupported_source"
    assert cell.diagnostics[0]["code"] == "UNSUPPORTED_AUTHENTICATION_CONTEXT"
    raw["target_manifest"]["schema_version"] = "target-manifest/1.0.0"
    with pytest.raises(ValidationError):
        validate_schema(raw["target_manifest"], "target-manifest")


def test_executable_query_cli_accepts_the_new_goal(scenario, tmp_path):
    graph, query = scenario
    query_path, graph_path = tmp_path / "query.json", tmp_path / "graph.json"
    query_path.write_text(json.dumps(wire(query)))
    graph_path.write_text(json.dumps(graph.to_canonical()))
    process = subprocess.run(
        [
            sys.executable,
            "-m",
            "src.engine.query_cli",
            "--query",
            str(query_path),
            "--graph",
            str(graph_path),
            "--label",
            "synthetic",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    payload = json.loads(process.stdout)
    assert payload["semantic"]["final_goal_reached"]


def test_replay_refuses_other_known_context_even_if_final_state_contains_that_identity(scenario):
    graph, query = scenario
    other_context = "10000000-0000-4000-8000-000000000099"
    canonical = graph.to_canonical()
    node = copy.deepcopy(next(n for n in canonical["nodes"] if n["id"] == HOST))
    node["id"] = other_context
    canonical["nodes"].append(node)
    graph = type(graph).from_canonical(canonical)
    query["initial_state"]["usable_identity"] = [[OTHER, other_context]]
    result = run_attack_query(query, graph)
    path = result.paths[0]
    descriptor = UsableIdentityEntitlementGoal(GROUP, other_context)
    assert descriptor.matches(path.final_state)
    metadata = dict(
        query_id="cross-context",
        scenario_id=query["scenario_reference"],
        scenario_version="1.0.0",
        snapshot_id=graph.metadata["snapshot_id"],
        work_boundary="intra_forest",
        horizon="24h",
        foothold_node_id=ACTOR,
        semantic_goal=descriptor.to_dict(),
    )
    envelope = adapt_search_candidate(
        path_result=path,
        candidate_id="wrong-context",
        target_asset_id=GROUP,
        query_metadata=metadata,
        action_mapping=[f"action-{i}" for i in range(len(path.transition_history))],
        success_event="synthetic_group_entitlement",
    )
    with pytest.raises(RankingValidationError, match="authentication context mismatch"):
        verify_search_envelope(path, graph, envelope, metadata)


def test_seamless_successor_manifest_roundtrips_without_touching_historical_fixture():
    value = json.loads((ROOT / "configs/targets/seamless-v2.json").read_text())
    validate_schema(value, "target-manifest")
    assert TargetManifest.from_dict(value).to_dict() == value


@pytest.mark.parametrize("binding", ["exact", "legacy", "context", "snapshot", "malformed"])
def test_reviewed_impact_cannot_silently_transfer_to_a_different_goal(binding):
    # Synthetic boundary test; no new production estimate is introduced.
    descriptor = UsableIdentityEntitlementGoal(GROUP, HOST).to_dict()
    declared = copy.deepcopy(descriptor)
    if binding == "legacy":
        declared = SemanticGoalDescriptor(
            GROUP, AttackState(effective_member=[(ACTOR, GROUP)])
        ).to_dict()
    elif binding == "context":
        declared["authentication_context"] = ACTOR
    elif binding == "malformed":
        declared["version"] = "unsupported-version"
    mapping = {
        "applicability": {
            "semantic_goal": declared,
            "goal_id": "new-group-goal",
            "snapshot_id": "snapshot-A",
        }
    }
    data = {"impact": {"mappings": [mapping]}}
    native = ResolutionResult(
        disposition=ResolverDisposition.RATED,
        value="High",
        provenance_digest=canonical_digest({"mapping": mapping, "source": None}),
        review_reference="synthetic://reviewed-goal-binding",
    )
    scope = {
        "snapshot_id": "snapshot-B" if binding == "snapshot" else "snapshot-A",
        "target_goal": {"goal_id": "new-group-goal"},
    }
    result = _impact_goal_guard(data, descriptor, "synthetic-scenario")(
        native, (None, GROUP, None, scope)
    )
    if binding == "exact":
        assert result is native
    else:
        assert result.disposition == ResolverDisposition.REFUSED
