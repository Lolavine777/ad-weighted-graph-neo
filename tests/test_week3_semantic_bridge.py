"""Synthetic regressions for scoped #180 capability/actor and evidence boundaries."""

import json
from copy import deepcopy

import pytest
from test_engine import ACTOR, GROUP, HOST, TOY, _auditable_context, _edge, _graph

from src.data.manifest import generate_manifest, raw_file_reference
from src.engine import SearchBudget, generate_attack_paths
from src.engine.semantics import AttackState, RuntimeContext, load_catalog
from src.engine.semantics.evaluator import PreparedSemanticGraph, evaluate
from src.engine.semantics.evidence_view import counterfactual_view, digest
from src.engine.semantics.transitions import Status, TransitionRequest

USER = "S-1-5-21-1000-2000-3000-1201"
CATALOG = tuple(
    t
    for t in load_catalog()
    if t.id
    in {
        "scenario_reset_password",
        "acquire_reset_identity",
        "propagate_group_entitlement",
        "scenario_winrm_admin",
    }
)


def fixture():
    graph = _graph(
        [
            _edge(ACTOR, USER, "GenericAll"),
            _edge(USER, GROUP, "MemberOf"),
            _edge(GROUP, HOST, "GenericAll"),
        ],
        extra_nodes=[
            {
                **next(n for n in TOY["nodes"] if n["id"] == ACTOR),
                "id": USER,
                "label": "synthetic",
                "enabled": True,
            }
        ],
    )
    facts = {
        (p, ACTOR, USER): True
        for p in ("network_rpc_reachable", "password_policy_accepts", "directory_write_allowed")
    }
    facts.update(
        {
            (p, USER, HOST): True
            for p in (
                "network_kdc_reachable",
                "authentication_accepted",
                "network_winrm_reachable",
                "service_winrm_running",
                "winrm_authentication_accepted",
                "endpoint_authorized",
                "admin_execution_context",
            )
        }
    )
    facts.update({(p, USER, GROUP): True for p in ("security_group", "membership_usable")})
    facts[("host_admin_mapping", GROUP, HOST)] = True
    return graph, facts


def run(graph, facts):
    context = RuntimeContext(
        list(_auditable_context(facts).facts.values()), authentication_context=HOST
    )
    return generate_attack_paths(
        graph,
        ACTOR,
        initial_state=AttackState(control={ACTOR}),
        runtime_context=context,
        target_predicate=lambda n: n["id"] == HOST,
        success_state_predicate=lambda s: HOST in s.admin_control,
        budget=SearchBudget(20, 7, 2000),
        catalog=CATALOG,
    )


def test_real_generator_uses_reset_then_scoped_authentication_then_new_actor():
    graph, facts = fixture()
    baseline = graph.to_canonical()
    result = run(graph, facts)
    assert len(result.paths) == 1
    path = result.paths[0]
    assert [step.result.request.actor for step in path.transition_history] == [
        ACTOR,
        USER,
        USER,
        USER,
    ]
    assert [step.result.technique.id for step in path.transition_history] == [
        "scenario_reset_password",
        "acquire_reset_identity",
        "propagate_group_entitlement",
        "scenario_winrm_admin",
    ]
    reset, ticket = [step.result for step in path.transition_history[:2]]
    assert not reset.additions.control and not reset.additions.usable_identity
    assert reset.additions.reset_password_control == {USER}
    assert ticket.additions.usable_identity == {(USER, HOST)}
    assert not ticket.additions.admin_control
    assert path.transition_history[1].edge_id is None
    assert path.transition_history[1].derived_from_step == 0
    assert path.final_state.control == {ACTOR}
    assert path.final_state.admin_control == {HOST}
    assert graph.to_canonical() == baseline
    assert {e["kind"] for e in path.edges} == {"GenericAll", "MemberOf"}


@pytest.mark.parametrize(
    "predicate,subject,target",
    [
        ("network_rpc_reachable", ACTOR, USER),
        ("directory_write_allowed", ACTOR, USER),
        ("network_kdc_reachable", USER, HOST),
        ("authentication_accepted", USER, HOST),
        ("security_group", USER, GROUP),
        ("membership_usable", USER, GROUP),
        ("host_admin_mapping", GROUP, HOST),
        ("network_winrm_reachable", USER, HOST),
        ("service_winrm_running", USER, HOST),
        ("winrm_authentication_accepted", USER, HOST),
        ("endpoint_authorized", USER, HOST),
        ("admin_execution_context", USER, HOST),
    ],
)
@pytest.mark.parametrize("value", [False, None])
def test_each_declared_gate_vetoes_or_stays_unknown(predicate, subject, target, value):
    graph, facts = fixture()
    if value is None:
        facts.pop((predicate, subject, target))
    else:
        facts[(predicate, subject, target)] = value
    result = run(graph, facts)
    assert not result.paths
    assert any(predicate in (a.failed if value is False else a.unknown) for a in result.attempts)


def test_authentication_control_is_not_an_unqualified_reset_password():
    graph, facts = fixture()
    context = RuntimeContext(
        list(_auditable_context(facts).facts.values()), authentication_context=HOST
    )
    request = TransitionRequest("acquire_reset_identity", USER, USER, HOST)
    result = evaluate(
        graph.to_canonical(), AttackState(authentication_control={USER}), request, context, CATALOG
    )
    assert result.status is Status.BLOCKED
    assert "reset_password_control" in result.failed


def test_identity_from_other_authentication_context_cannot_authorize_membership():
    graph, facts = fixture()
    context = RuntimeContext(
        list(_auditable_context(facts).facts.values()), authentication_context=HOST
    )
    state = AttackState(usable_identity={(USER, "other-context")})
    result = evaluate(
        graph.to_canonical(),
        state,
        TransitionRequest("propagate_group_entitlement", USER, USER, GROUP),
        context,
        CATALOG,
    )
    assert "actor_controlled" in result.failed


def test_snapshot_false_vetoes_optimistic_enabled_fact():
    graph, facts = fixture()
    canonical = graph.to_canonical()
    next(n for n in canonical["nodes"] if n["id"] == USER)["enabled"] = False
    facts[("target_enabled", ACTOR, USER)] = True
    context = RuntimeContext(
        list(_auditable_context(facts).facts.values()), authentication_context=HOST
    )
    result = evaluate(
        canonical,
        AttackState(control={ACTOR}),
        TransitionRequest("scenario_reset_password", ACTOR, ACTOR, USER),
        context,
        CATALOG,
    )
    assert "target_enabled" in result.failed
    assert not result.additions.reset_password_control


def test_prepared_graph_index_is_isolated_and_matches_plain_evaluation():
    graph, facts = fixture()
    canonical = graph.to_canonical()
    prepared = PreparedSemanticGraph(canonical)
    context = RuntimeContext(
        list(_auditable_context(facts).facts.values()), authentication_context=HOST
    )
    request = TransitionRequest("scenario_reset_password", ACTOR, ACTOR, USER)
    state = AttackState(control={ACTOR})
    assert evaluate(canonical, state, request, context, CATALOG) == evaluate(
        prepared, state, request, context, CATALOG
    )
    canonical["edges"].clear()
    assert evaluate(prepared, state, request, context, CATALOG).status is Status.APPLICABLE
    assert evaluate(canonical, state, request, context, CATALOG).status is Status.BLOCKED


def raw_fixture(tmp_path):
    raw = tmp_path / "raw"
    raw.mkdir()
    payload = {
        "users": [
            {
                "ObjectIdentifier": USER,
                "Properties": {"enabled": True},
                "Aces": [{"PrincipalSID": ACTOR, "RightName": "GenericAll"}],
            }
        ]
    }
    (raw / "users.json").write_text(json.dumps(payload), encoding="utf-8")
    manifest = generate_manifest(
        raw,
        dataset_id="synthetic-bridge",
        collector_name="synthetic",
        collector_version="1.0",
        collected_at="2026-10-03T00:00:00Z",
    )
    graph, _ = fixture()
    baseline = graph.to_canonical()
    edge = next(e for e in baseline["edges"] if e["source"] == ACTOR)
    edge["provenance"][0].update(
        raw_file=raw_file_reference(manifest, "users.json"),
        record_id=USER,
        attribute="Aces[].PrincipalSID",
    )
    spec = {
        "kind": "withhold_structural_provenance",
        "edge_id": edge["id"],
        "locator": "users.json#/users/0/Aces/0",
        "source": ACTOR,
        "relationship": "GenericAll",
        "target": USER,
    }
    return raw, manifest, baseline, spec


def test_withheld_structural_provenance_has_verified_raw_delta_and_unknown_trace(tmp_path):
    raw, manifest, baseline, spec = raw_fixture(tmp_path)
    before = deepcopy(baseline)
    view = counterfactual_view(
        baseline, spec, case_id="synthetic-missing", raw_dir=raw, manifest=manifest
    )
    assert baseline == before and view.audit["baseline_digest"] == digest(before)
    assert view.audit["view_digest"] != view.audit["baseline_digest"]
    assert view.audit["delta"][0]["locator"] == spec["locator"]
    graph, facts = fixture()
    context = RuntimeContext(
        list(_auditable_context(facts).facts.values()),
        authentication_context=HOST,
        withheld_relationships=view.withheld_relationships,
    )
    result = evaluate(
        view.graph,
        AttackState(control={ACTOR}),
        TransitionRequest("scenario_reset_password", ACTOR, ACTOR, USER),
        context,
        CATALOG,
    )
    assert result.status is Status.INDETERMINATE
    assert result.unknown == ("relationship_exists",)


def test_evidence_overlay_retains_independent_support(tmp_path):
    raw, manifest, baseline, spec = raw_fixture(tmp_path)
    edge = next(e for e in baseline["edges"] if e["id"] == spec["edge_id"])
    independent = {**edge["provenance"][0], "raw_file": "synthetic://independent"}
    edge["provenance"].append(independent)
    view = counterfactual_view(
        baseline, spec, case_id="synthetic-independent", raw_dir=raw, manifest=manifest
    )
    assert not view.withheld_relationships
    assert next(e for e in view.graph["edges"] if e["id"] == spec["edge_id"])["provenance"] == [
        independent
    ]


def test_enabled_overlay_removes_observation_without_default_or_baseline_mutation(tmp_path):
    raw, manifest, baseline, _ = raw_fixture(tmp_path)
    spec = {
        "kind": "withhold_enabled_observation",
        "node_id": USER,
        "locator": "users.json#/users/0/Properties/enabled",
    }
    view = counterfactual_view(
        baseline, spec, case_id="synthetic-enabled", raw_dir=raw, manifest=manifest
    )
    assert "enabled" not in next(n for n in view.graph["nodes"] if n["id"] == USER)
    assert next(n for n in baseline["nodes"] if n["id"] == USER)["enabled"] is True


def test_corrupt_raw_mapping_fails_closed(tmp_path):
    raw, manifest, baseline, spec = raw_fixture(tmp_path)
    (raw / "users.json").write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError):
        counterfactual_view(
            baseline, spec, case_id="synthetic-corrupt", raw_dir=raw, manifest=manifest
        )


def test_step_cap_reports_pending_acquire_identity():
    graph, facts = fixture()
    graph = _graph([_edge(ACTOR, USER, "GenericAll")], extra_nodes=[graph.node(USER)])
    context = RuntimeContext(
        list(_auditable_context(facts).facts.values()), authentication_context=HOST
    )
    catalog = tuple(
        t for t in CATALOG if t.id in {"scenario_reset_password", "acquire_reset_identity"}
    )

    def search(steps):
        return generate_attack_paths(
            graph,
            ACTOR,
            initial_state=AttackState(control={ACTOR}),
            runtime_context=context,
            target_predicate=lambda n: n["id"] == HOST,
            success_state_predicate=lambda s: (USER, HOST) in s.usable_identity,
            budget=SearchBudget(20, steps, 2000),
            catalog=catalog,
        )

    limited = search(1)
    assert not limited.paths and not limited.complete
    assert limited.truncation_reason == "step_limit_reached"
    complete = search(2)
    assert len(complete.paths) == 1 and complete.complete


def test_step_cap_reports_pending_declared_host_admin():
    graph = _graph([_edge(ACTOR, GROUP, "MemberOf"), _edge(GROUP, HOST, "GenericAll")])
    facts = {(p, ACTOR, GROUP): True for p in ("security_group", "membership_usable")}
    facts.update(
        {
            (p, ACTOR, HOST): True
            for p in (
                "network_winrm_reachable",
                "service_winrm_running",
                "winrm_authentication_accepted",
                "endpoint_authorized",
                "admin_execution_context",
            )
        }
    )
    facts[("host_admin_mapping", GROUP, HOST)] = True
    context = RuntimeContext(
        list(_auditable_context(facts).facts.values()), authentication_context=HOST
    )
    catalog = tuple(
        t for t in CATALOG if t.id in {"propagate_group_entitlement", "scenario_winrm_admin"}
    )

    def search(steps):
        return generate_attack_paths(
            graph,
            ACTOR,
            initial_state=AttackState(usable_identity={(ACTOR, HOST)}),
            runtime_context=context,
            target_predicate=lambda n: n["id"] == HOST,
            success_state_predicate=lambda s: HOST in s.admin_control,
            budget=SearchBudget(20, steps, 2000),
            catalog=catalog,
        )

    limited = search(1)
    assert not limited.paths and not limited.complete
    assert limited.truncation_reason == "step_limit_reached"
    assert len(search(2).paths) == 1


@pytest.mark.parametrize(
    "locator_key", ["provenance_locator", "provenance_reference", "record_locator"]
)
def test_raw_fallback_retains_different_explicit_locator(tmp_path, locator_key):
    raw, manifest, baseline, spec = raw_fixture(tmp_path)
    edge = next(e for e in baseline["edges"] if e["id"] == spec["edge_id"])
    independent = {**edge["provenance"][0], locator_key: "users.json#/users/0/Aces/1"}
    edge["provenance"].append(independent)
    before = deepcopy(baseline)
    view = counterfactual_view(
        baseline, spec, case_id="independent-ace", raw_dir=raw, manifest=manifest
    )
    assert not view.withheld_relationships
    assert next(e for e in view.graph["edges"] if e["id"] == spec["edge_id"])["provenance"] == [
        independent
    ]
    assert len(view.audit["delta"]) == 1
    assert baseline == before


def test_coarse_raw_mapping_with_duplicate_aces_fails_closed(tmp_path):
    raw, _, baseline, spec = raw_fixture(tmp_path)
    payload = json.loads((raw / "users.json").read_text(encoding="utf-8"))
    payload["users"][0]["Aces"].append(deepcopy(payload["users"][0]["Aces"][0]))
    (raw / "users.json").write_text(json.dumps(payload), encoding="utf-8")
    manifest = generate_manifest(
        raw,
        dataset_id="synthetic-bridge",
        collector_name="synthetic",
        collector_version="1.0",
        collected_at="2026-10-03T00:00:00Z",
    )
    edge = next(e for e in baseline["edges"] if e["id"] == spec["edge_id"])
    edge["provenance"][0]["raw_file"] = raw_file_reference(manifest, "users.json")
    before = deepcopy(baseline)
    with pytest.raises(ValueError, match="ambiguous raw ACL support"):
        counterfactual_view(baseline, spec, case_id="ambiguous-ace", raw_dir=raw, manifest=manifest)
    assert baseline == before


def test_exact_locator_removes_only_one_of_two_same_record_aces(tmp_path):
    _, _, baseline, spec = raw_fixture(tmp_path)
    edge = next(e for e in baseline["edges"] if e["id"] == spec["edge_id"])
    edge["provenance"][0]["record_locator"] = spec["locator"]
    independent = {**edge["provenance"][0], "record_locator": "users.json#/users/0/Aces/1"}
    edge["provenance"].append(independent)
    view = counterfactual_view(baseline, spec, case_id="exact-ace")
    assert not view.withheld_relationships
    assert next(e for e in view.graph["edges"] if e["id"] == spec["edge_id"])["provenance"] == [
        independent
    ]
    assert len(view.audit["delta"]) == 1
