"""Focused tests for the Week 3 release-consuming acceptance harness."""

from __future__ import annotations

import json
from copy import deepcopy

import pytest

from scripts.research import week3_engine_acceptance as harness
from scripts.research.week3_engine_acceptance import (
    DEFAULT_PLAN,
    DEFAULT_RELEASE,
    acceptance_manifest_audit,
    context_for,
    load_json,
    ownership_audit,
    success_state_predicate,
)
from src.engine.semantics import AttackState, FactOrigin


def _release_and_plan():
    release = load_json(DEFAULT_RELEASE)
    plan = load_json(DEFAULT_PLAN)
    assert isinstance(release, dict)
    assert isinstance(plan, dict)
    return release, plan


def _synthetic_acceptance_manifest(release, plan):
    return load_json(harness.DEFAULT_ACCEPTANCE_MANIFEST)


def test_week3_plan_fails_closed_and_catalog_owners_have_exact_bindings():
    release, plan = _release_and_plan()
    audits = {
        source: ownership_audit(release["query_projections"][source], plan["sources"][source])
        for source in ("source_a", "source_b")
    }

    assert audits["source_a"]["gaps"] == []
    assert audits["source_b"]["gaps"] == []
    for audit in audits.values():
        assert audit["missing_owner_action_ids"] == []
        assert audit["invalid_catalog_owners"] == []
        assert audit["complete"] is True

    # Malformed catalog technique fails closed
    malformed = deepcopy(plan["sources"]["source_a"])
    malformed["action_semantic_owners"]["action_closure_lidia_da"] = {
        "status": "catalog_transition",
        "technique_id": "nonexistent_technique_invented",
    }
    bad = ownership_audit(release["query_projections"]["source_a"], malformed)
    assert [item["action_id"] for item in bad["invalid_catalog_owners"]] == [
        "action_closure_lidia_da"
    ]
    assert bad["complete"] is False

    # Gap fails closed
    gap = deepcopy(plan["sources"]["source_a"])
    gap["action_semantic_owners"]["action_closure_lidia_da"] = {
        "status": "gap",
        "reason": "explicit gap test",
    }
    bad_gap = ownership_audit(release["query_projections"]["source_a"], gap)
    assert bad_gap["gaps"]
    assert bad_gap["complete"] is False


@pytest.mark.parametrize(
    ("source", "false_case", "unknown_case", "release_predicate", "target"),
    [
        (
            "source_a",
            "w3-source-a-known-false",
            "w3-source-a-runtime-unknown",
            "directory_write_allowed_lidia",
            "S-1-5-21-1271839998-3495686680-2211690266-3398",
        ),
        (
            "source_b",
            "w3-source-b-known-false",
            "w3-source-b-runtime-unknown",
            "directory_write_allowed_ollie",
            "S-1-5-21-1271839998-3495686680-2211690266-2014",
        ),
    ],
)
def test_pinned_false_and_unknown_cases_replace_only_a_owned_runtime_fact(
    source, false_case, unknown_case, release_predicate, target
):
    release, plan = _release_and_plan()
    query = release["query_projections"][source]["query"]
    source_plan = plan["sources"][source]

    positive = context_for(query, source_plan, {})
    false_variant = context_for(query, source_plan, plan["cases"][false_case])
    unknown_variant = context_for(query, source_plan, plan["cases"][unknown_case])

    key = ("directory_write_allowed", source_plan["actor"], target)
    assert positive.facts[key].value is True
    assert positive.facts[key].origin is FactOrigin.DECLARED_ASSUMPTION
    assert false_variant.facts[key].value is False
    assert false_variant.facts[key].origin is FactOrigin.BLOCKED_EVIDENCE
    assert unknown_variant.facts[key].value is None
    assert unknown_variant.facts[key].origin is FactOrigin.UNKNOWN
    assert false_variant.facts[key].assumption_metadata == {"release_predicate": release_predicate}
    assert set(positive.facts) == set(false_variant.facts) == set(unknown_variant.facts)

    if source == "source_a":
        josefa_key = (
            "directory_write_allowed",
            source_plan["actor"],
            "S-1-5-21-1271839998-3495686680-2211690266-1766",
        )
        assert false_variant.facts[josefa_key].value is True
        assert unknown_variant.facts[josefa_key].value is True


def test_plan_case_ids_and_search_bindings_cross_check_against_a_manifest():
    release, plan = _release_and_plan()
    manifest = _synthetic_acceptance_manifest(release, plan)
    audit = acceptance_manifest_audit(release, plan, manifest)

    assert audit["available"] is True
    assert audit["complete"] is True
    assert audit["mismatches"] == []
    assert plan["acceptance_manifest"]["source_revision"] == (
        "6d06dc7bb9352db568eb7dc6deb92285a8d32489"
    )

    changed = deepcopy(manifest)
    case = next(item for item in changed["cases"] if item["case_id"] == "w3-source-b-known-false")
    case["predicate"]["search_binding"]["target"] = "S-1-5-21-0-0-0-9999"
    bad = acceptance_manifest_audit(release, plan, changed)
    assert bad["complete"] is False
    assert any(item["field"] == "search_binding" for item in bad["mismatches"])


def test_terminal_success_state_matches_reviewed_goal_not_node_reachability():
    release, plan = _release_and_plan()
    query = release["query_projections"]["source_a"]["query"]
    source_plan = plan["sources"]["source_a"]
    target = query["query_metadata"]["target_goal"]["target_asset_id"]
    predicate = success_state_predicate(query, source_plan)

    assert predicate(AttackState()) is False
    assert predicate(AttackState(admin_control={target})) is True

    malformed = deepcopy(source_plan)
    malformed["terminal_success_state"]["required_query_predicate"] = "credentials_lidia"
    with pytest.raises(ValueError, match="differs from query target_goal"):
        success_state_predicate(query, malformed)


def test_structural_and_telemetry_missing_cases_have_evidence_view_mappings():
    _, plan = _release_and_plan()
    for case_id, expected_kind, expected_locator in (
        (
            "w3-source-a-structural-missing",
            "withhold_structural_provenance",
            "20210920185958_users.json#/users/2310/Aces/3",
        ),
        (
            "w3-source-a-telemetry-missing",
            "withhold_enabled_observation",
            "20210920185958_users.json#/users/2310/Properties/enabled",
        ),
    ):
        case = plan["cases"][case_id]
        assert case["search_binding_status"] == "mapped"
        assert case["evidence_view"]["kind"] == expected_kind
        assert case["evidence_view"]["locator"] == expected_locator
        assert case["predicate_name"]


def test_main_pins_release_graph_runtime_and_is_deterministic(tmp_path, monkeypatch):
    release, plan = _release_and_plan()
    acceptance = tmp_path / "acceptance.json"
    acceptance.write_bytes(harness.DEFAULT_ACCEPTANCE_MANIFEST.read_bytes())

    graph = {
        "metadata": {
            "snapshot_id": release["bundle_metadata"]["snapshot_id"],
            "contract_version": "1.3.0",
            "weight_profile": "unit",
            "created_at": "2026-10-03T00:00:00Z",
            "code_version": "a" * 40,
        },
        "nodes": [],
        "edges": [],
        "assessments": [],
    }
    graph_pins = {
        "input_mode": "test",
        "graph_file": {"canonical_digest": harness.digest(graph)},
        "raw_manifest": {"canonical_digest": "sha256:" + "b" * 64},
        "parser_config": {
            "profile": "unit",
            "created_at": "2026-10-03T00:00:00Z",
            "time_policy": None,
        },
    }
    monkeypatch.setattr(
        harness, "checkout_revision", lambda: "c4392186ce95c8948b62c789ce8ae5493ef427f3"
    )
    monkeypatch.setattr(harness, "graph_from_args", lambda _args, _release: (graph, graph_pins, {}))
    monkeypatch.setattr(
        harness,
        "source_result",
        lambda projection, _source_plan, _case_plan, _graph, **_kwargs: {
            "query_id": projection["query"]["query_metadata"]["query_id"],
            "missing_reviewed_candidate_ids": [
                candidate["candidate_id"] for candidate in projection["candidates"]
            ],
        },
    )

    first = tmp_path / "first.json"
    second = tmp_path / "second.json"
    common = [
        "--case-id",
        "w3-source-a-positive",
        "--acceptance-manifest",
        str(acceptance),
    ]
    assert harness.main([*common, "--output", str(first)]) == 0
    assert harness.main([*common, "--output", str(second)]) == 0

    first_report = json.loads(first.read_text(encoding="utf-8"))
    second_report = json.loads(second.read_text(encoding="utf-8"))
    assert first_report == second_report
    assert first_report["status"] == "case_search_expectations_not_met"
    assert first_report["acceptance_manifest_audit"]["complete"] is True
    assert first_report["execution_pins"]["checkout_revision"]
    assert first_report["execution_pins"]["files"]["release"]["file_sha256"]
    assert first_report["graph"]["canonical_digest"] == harness.digest(graph)
    assert first_report["report_digest"] == harness.digest(
        {key: value for key, value in first_report.items() if key != "report_digest"}
    )

    # Same parsed JSON with different bytes must fail the exact Git blob pin.
    acceptance.write_bytes(acceptance.read_bytes() + b"\n")
    changed = tmp_path / "changed.json"
    assert harness.main([*common, "--output", str(changed), "--require-complete"]) == 4
    changed_report = json.loads(changed.read_text(encoding="utf-8"))
    assert changed_report["acceptance_manifest_audit"]["complete"] is False
    assert any(
        item["field"] == "blob_sha"
        for item in changed_report["acceptance_manifest_audit"]["mismatches"]
    )


@pytest.mark.parametrize("source", ["a", "b"])
@pytest.mark.parametrize("kind", ["known-false", "runtime-unknown"])
def test_case_specific_negative_completion_and_designated_decision(source, kind, monkeypatch):
    release, plan = _release_and_plan()
    manifest = load_json(harness.DEFAULT_ACCEPTANCE_MANIFEST)
    case_id = f"w3-source-{source}-{kind}"
    external = next(case for case in manifest["cases"] if case["case_id"] == case_id)
    projection = release["query_projections"][external["source"]]
    binding = external["predicate"]["search_binding"]
    false_case = kind == "known-false"
    attempt = {
        "technique_id": binding["technique_id"],
        "actor": binding["subject"],
        "source": binding["subject"],
        "target": binding["target"],
        "status": "blocked" if false_case else "indeterminate",
        "failed": [binding["predicate"]] if false_case else [],
        "unknown": [] if false_case else [binding["predicate"]],
        "decisions": [
            {
                "predicate": binding["predicate"],
                "satisfied": False,
                "origin": binding["origin"],
                "rationale": binding["rationale"],
                "subject": binding["subject"],
                "target": binding["target"],
                "value": binding["value"],
                "scope": binding["scope"],
            }
        ],
    }
    feasible = {
        cid
        for cid, item in external["expected"]["candidates"].items()
        if item["status"] == "feasible"
    }
    eligible = {}
    for index, candidate in enumerate(projection["candidates"]):
        cid = candidate["candidate_id"]
        if cid in feasible:
            metrics = external["expected"]["candidates"][cid]
            eligible[f"generated_{index}"] = {
                "bound_action_ids": candidate["bound_action_ids"],
                "effort": metrics.get("effort"),
                "likelihood_interval": metrics.get("likelihood_interval"),
                "impact": metrics.get("impact"),
            }
    min_effort_val = None
    if external["expected"].get("min_effort"):
        min_effort_val = {
            "best_candidate_id": external["expected"]["min_effort"]["best_candidate_id"],
            "minimum_effort_value": external["expected"]["min_effort"]["minimum_effort_value"],
        }
    result = {
        "eligible_candidates": eligible,
        "pareto_frontier": list(external["expected"].get("pareto_frontier", [])),
        "min_effort_to_da_baseline": min_effort_val,
        "search_audit": {"attempt_diagnostics": [attempt]},
    }
    audit = harness.case_expectation_audit(projection, external, result)
    assert audit["complete"] is True
    assert audit["missing_reviewed_candidate_ids"] == []
    assert audit["expected_pruned_candidate_ids"]

    # A correct negative can reach the report's pass gate once capability ownership is ready.
    monkeypatch.setattr(harness, "ownership_audit", lambda *_args: {"complete": True})
    monkeypatch.setattr(harness, "source_result", lambda *_args, **_kwargs: deepcopy(result))
    acceptance = acceptance_manifest_audit(release, plan, manifest)
    report = harness.build_report(release, plan, {}, case_id, {}, acceptance)
    assert report["status"] == "passed"

    unrelated = deepcopy(result)
    unrelated["search_audit"]["attempt_diagnostics"] = []
    assert harness.case_expectation_audit(projection, external, unrelated)["complete"] is False
    monkeypatch.setattr(harness, "source_result", lambda *_args, **_kwargs: unrelated)
    assert harness.build_report(release, plan, {}, case_id, {}, acceptance)["status"] == (
        "case_search_expectations_not_met"
    )

    for field in ("predicate", "subject", "target", "origin", "rationale", "scope", "value"):
        wrong = deepcopy(result)
        wrong["search_audit"]["attempt_diagnostics"][0]["decisions"][0][field] = "wrong"
        assert harness.case_expectation_audit(projection, external, wrong)["complete"] is False
    for field in ("technique_id", "actor", "source", "target", "status"):
        wrong = deepcopy(result)
        wrong["search_audit"]["attempt_diagnostics"][0][field] = "wrong"
        assert harness.case_expectation_audit(projection, external, wrong)["complete"] is False

    wrong = deepcopy(result)
    wrong["eligible_candidates"]["forbidden"] = {
        "bound_action_ids": next(
            candidate["bound_action_ids"]
            for candidate in projection["candidates"]
            if candidate["candidate_id"] not in feasible
        )
    }
    assert harness.case_expectation_audit(projection, external, wrong)["complete"] is False
    if feasible:
        wrong = deepcopy(result)
        wrong["eligible_candidates"] = {}
        assert harness.case_expectation_audit(projection, external, wrong)["complete"] is False


def test_manifest_expected_semantics_are_pinned():
    release, plan = _release_and_plan()
    manifest = load_json(harness.DEFAULT_ACCEPTANCE_MANIFEST)
    changed = deepcopy(manifest)
    changed["cases"][1]["expected"]["candidates"]["cand_seamless_01_direct_lidia"]["status"] = (
        "feasible"
    )
    assert acceptance_manifest_audit(release, plan, changed)["complete"] is False
    assert acceptance_manifest_audit(release, plan, None)["complete"] is False


def test_positive_case_still_requires_every_reviewed_program():
    release, _ = _release_and_plan()
    manifest = load_json(harness.DEFAULT_ACCEPTANCE_MANIFEST)
    case = next(item for item in manifest["cases"] if item["case_id"] == "w3-source-a-positive")
    projection = release["query_projections"][case["source"]]
    result = {"eligible_candidates": {"generated": projection["candidates"][0]}}
    assert harness.case_expectation_audit(projection, case, result)["complete"] is False


@pytest.mark.parametrize("source", ["a", "b"])
@pytest.mark.parametrize("kind", ["known-false", "runtime-unknown"])
def test_negative_scope_survives_real_context_search_and_acceptance(source, kind):
    """Use real Week 3 fact bindings on a synthetic reset-only graph, without decision mocks."""
    from scripts.check_contract import canonical_edge_id

    release, plan = _release_and_plan()
    case_id = f"w3-source-{source}-{kind}"
    manifest = load_json(harness.DEFAULT_ACCEPTANCE_MANIFEST)
    external = next(case for case in manifest["cases"] if case["case_id"] == case_id)
    case_plan = plan["cases"][case_id]
    source_plan = plan["sources"][external["source"]]
    projection = release["query_projections"][external["source"]]
    binding = external["predicate"]["search_binding"]
    context = context_for(projection["query"], source_plan, case_plan)
    fact = context.facts[(binding["predicate"], binding["subject"], binding["target"])]

    graph = load_json(harness.ROOT / "data/samples/toy-graph.json")
    actor = deepcopy(graph["nodes"][1])
    actor["id"] = binding["subject"]
    target = deepcopy(graph["nodes"][1])
    target["id"] = binding["target"]
    dc = deepcopy(graph["nodes"][0])
    dc["id"] = source_plan["target"]
    graph["nodes"] = [actor, target, dc]
    edge = deepcopy(graph["edges"][0])
    edge.update(
        id=canonical_edge_id(actor["id"], target["id"], "GenericAll"),
        source=actor["id"],
        target=target["id"],
        kind="GenericAll",
    )
    graph["edges"] = [edge]
    graph["metadata"]["snapshot_id"] = release["bundle_metadata"]["snapshot_id"]

    # source_result calls context_for, the actual generator/evaluator, and orchestration.
    result = harness.source_result(projection, source_plan, case_plan, graph)
    audit = harness.case_expectation_audit(projection, external, result)
    assert audit["designated_negative_decision_verified"] is True
    assert fact.scope == binding["scope"]
    assert fact.scope == projection["query"]["query_metadata"]["scenario_id"]
    assert result["eligible_candidates"] == {}
    assert result["pareto_frontier"] == []
    assert result["search_audit"]["generated_paths"] == 0
    assert audit["matching_negative_attempts"]
    if source == "b":
        assert audit["complete"] is True
    else:
        # This reset-only graph intentionally cannot generate the alternative positive route.
        assert audit["missing_reviewed_candidate_ids"] == ["cand_seamless_02_alt_vajer_ollie"]
    for attempt in audit["matching_negative_attempts"]:
        decision = next(
            item for item in attempt["decisions"] if item["predicate"] == binding["predicate"]
        )
        assert decision["scope"] == binding["scope"]
        assert decision["origin"] == binding["origin"]
        assert decision["value"] is binding["value"]

    positive = context_for(projection["query"], source_plan, {})
    assumption = positive.facts[(binding["predicate"], binding["subject"], binding["target"])]
    assert assumption.scope == projection["query"]["query_metadata"]["horizon"]


def test_structural_and_telemetry_missing_completion_and_designated_evidence():
    release, _ = _release_and_plan()
    manifest = load_json(harness.DEFAULT_ACCEPTANCE_MANIFEST)
    proj_a = release["query_projections"]["source_a"]

    # 1. Structural missing
    ext_s = next(
        case for case in manifest["cases"] if case["case_id"] == "w3-source-a-structural-missing"
    )
    attempt_s = {
        "technique_id": "scenario_reset_password",
        "actor": proj_a["query"]["query_metadata"]["foothold_node_id"],
        "source": proj_a["query"]["query_metadata"]["foothold_node_id"],
        "target": "S-1-5-21-1271839998-3495686680-2211690266-3398",
        "status": "indeterminate",
        "unknown": ["relationship_exists"],
        "decisions": [
            {
                "predicate": "relationship_exists",
                "satisfied": False,
                "origin": "unknown",
                "value": None,
            }
        ],
    }
    cand_alt = ext_s["expected"]["candidates"]["cand_seamless_02_alt_vajer_ollie"]
    eligible_s = {
        "gen_alt": {
            "bound_action_ids": next(
                c["bound_action_ids"]
                for c in proj_a["candidates"]
                if c["candidate_id"] == "cand_seamless_02_alt_vajer_ollie"
            ),
            "effort": cand_alt["effort"],
            "likelihood_interval": cand_alt["likelihood_interval"],
            "impact": cand_alt["impact"],
        }
    }
    result_s = {
        "eligible_candidates": eligible_s,
        "pareto_frontier": ["cand_seamless_02_alt_vajer_ollie"],
        "min_effort_to_da_baseline": {
            "best_candidate_id": "cand_seamless_02_alt_vajer_ollie",
            "minimum_effort_value": 3,
        },
        "search_audit": {"attempt_diagnostics": [attempt_s]},
        "evidence_view": {
            "delta": [
                {
                    "op": "withhold_provenance",
                    "locator": "20210920185958_users.json#/users/2310/Aces/3",
                }
            ]
        },
    }
    audit_s = harness.case_expectation_audit(proj_a, ext_s, result_s)
    assert audit_s["complete"] is True
    assert audit_s["designated_negative_decision_verified"] is True

    # 2. Telemetry missing
    ext_t = next(
        case for case in manifest["cases"] if case["case_id"] == "w3-source-a-telemetry-missing"
    )
    attempt_t = {
        "technique_id": "scenario_reset_password",
        "actor": proj_a["query"]["query_metadata"]["foothold_node_id"],
        "source": proj_a["query"]["query_metadata"]["foothold_node_id"],
        "target": "S-1-5-21-1271839998-3495686680-2211690266-3398",
        "status": "indeterminate",
        "unknown": ["target_enabled"],
        "decisions": [
            {
                "predicate": "target_enabled",
                "satisfied": False,
                "origin": "unknown",
                "value": None,
            }
        ],
    }
    result_t = {
        "eligible_candidates": eligible_s,
        "pareto_frontier": ["cand_seamless_02_alt_vajer_ollie"],
        "min_effort_to_da_baseline": {
            "best_candidate_id": "cand_seamless_02_alt_vajer_ollie",
            "minimum_effort_value": 3,
        },
        "search_audit": {"attempt_diagnostics": [attempt_t]},
        "evidence_view": {
            "delta": [
                {
                    "op": "remove",
                    "field": "enabled",
                    "locator": "20210920185958_users.json#/users/2310/Properties/enabled",
                }
            ]
        },
    }
    audit_t = harness.case_expectation_audit(proj_a, ext_t, result_t)
    assert audit_t["complete"] is True
    assert audit_t["designated_negative_decision_verified"] is True
