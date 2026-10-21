"""Independent finite expectations; end-to-end cases use the real public engine."""

import copy
import json
from pathlib import Path

import pytest

from scripts.research.remediation_acceptance import validate_result
from src.engine.batch import BatchExecutionBudget
from src.engine.graph import EngineGraph
from src.engine.remediation import _digest, prepare_baseline, request_for_baseline
from src.engine.remediation_runner import (
    inventory_interventions,
    rank_interventions,
    run_remediation,
    verify_package,
)

FIX = Path(__file__).parent / "fixtures/remediation"


def read(name):
    return json.loads((FIX / name).read_text(encoding="utf-8"))


def inputs(fixture="request-bypass-v1.1.json", mutate=None, sources=("alice", "bob")):
    graph = EngineGraph.from_canonical(read("graph.json"))
    cells = [{"source_id": s, "goal_id": "host", "query": read(f"{s}-query.json")} for s in sources]
    if mutate:
        mutate(cells)
    baseline = prepare_baseline(graph, cells, run_id="native-before")
    edits = read(fixture)["edits"]
    if sources == ("alice",) and fixture != "request-acl-v1.1.json":
        edits = edits[:1]
    request = request_for_baseline(baseline, edits, request_id=fixture)
    return graph, baseline, request


@pytest.mark.parametrize(
    "fixture,after,cut,disconnected",
    [
        ("request-bypass-v1.1.json", [1, 0], 3, 1),
        ("request-v1.1.json", [0, 0], 4, 2),
        ("request-acl-v1.1.json", [1, 1], 2, 0),
    ],
)
def test_real_finite_before_after(fixture, after, cut, disconnected):
    graph, baseline, request = inputs(fixture)
    original = graph.to_canonical()
    package = run_remediation(request, graph, baseline)
    report = package["report"]
    validate_result(report)
    assert [c["before"]["program_count"] for c in report["cells"]] == [3, 1]
    assert [c["after"]["program_count"] for c in report["cells"]] == after
    assert report["summary"]["programs_cut"]["numerator"] == cut
    assert report["summary"]["pairs_disconnected"]["numerator"] == disconnected
    assert report["summary"]["programs_cut"]["scope"] == "complete_declared_scope"
    assert all(c["after"]["rediscovery"]["status"] == "complete" for c in report["cells"])
    assert all(
        c["bypass_program_ids"] == c["after"]["witness_program_ids"] for c in report["cells"]
    )
    assert all(not c["new_program_ids"] for c in report["cells"])
    assert graph.to_canonical() == original
    assert verify_package(package, graph)["status"] == "verified"
    if fixture == "request-bypass-v1.1.json":
        assert report["summary"]["programs_cut"]["percent"] == 75
        assert report["summary"]["pairs_disconnected"]["percent"] == 50
        assert report["summary"]["exposed_sources_after"] == ["alice"]
        assert report["summary"]["fully_disconnected_sources"] == ["bob"]


def test_new_bypass_after_capped_baseline_is_discovered():
    def cap(cells):
        cells[0]["query"]["budget"]["max_paths"] = 1

    graph, baseline, request = inputs("request-acl-v1.1.json", cap, ("alice",))
    report = run_remediation(request, graph, baseline)["report"]
    cell = report["cells"][0]
    assert cell["before"]["program_count"] == 1 and cell["before"]["truncated"]
    assert cell["after"]["reachability"] == "reachable"
    assert cell["after"]["program_count"] == len(cell["new_program_ids"]) == 1
    assert len(cell["cut_program_ids"]) == 1 and not cell["disconnected"]
    assert report["summary"]["programs_cut"]["percent"] == 100
    assert report["summary"]["programs_cut"]["scope"] == "observed_corpus_only"
    assert report["summary"]["pairs_disconnected"]["percent"] == 0


@pytest.mark.parametrize("control", ["unknown", "false"])
def test_missing_and_known_false_have_native_dispositions(control):
    def change(cells):
        for cell in cells:
            query = cell["query"]
            fact = next(
                f for f in query["assumptions"] if f["predicate"] == "authentication_accepted"
            )
            if control == "unknown":
                query["assumptions"].remove(fact)
            else:
                query["runtime_facts"] = [{**fact, "value": False, "origin": "blocked_evidence"}]

    graph, baseline, request = inputs(mutate=change)
    report = run_remediation(request, graph, baseline)["report"]
    assert not report["summary"]["proven_disconnected_pairs"]
    assert all(
        c["before"]["reachability"] == ("unknown" if control == "unknown" else "proven_unreachable")
        for c in report["cells"]
    )
    assert all(not c["cut_program_ids"] for c in report["cells"])
    if control == "unknown":
        assert report["summary"]["programs_cut"]["scope"] == "observed_corpus_only"


def test_zero_action_goal_survives_denial():
    def initial_goal(cells):
        cells[0]["query"]["initial_state"]["admin_control"] = [cells[0]["query"]["target"]]

    graph, baseline, request = inputs("request-v1.1.json", initial_goal, ("alice",))
    cell = run_remediation(request, graph, baseline)["report"]["cells"][0]
    assert cell["before"]["program_count"] == cell["after"]["program_count"] == 1
    assert cell["after"]["trace_refs"][0]["semantic_program"] == []
    assert not cell["cut_program_ids"] and not cell["new_program_ids"]
    assert cell["after"]["reachability"] == "reachable"


def test_not_run_preserves_retained_witnesses_and_all_declared_denominators(tmp_path):
    graph, baseline, request = inputs("request-v1.1.json")
    package = run_remediation(
        request,
        graph,
        baseline,
        execution_budget=BatchExecutionBudget(max_cells=1),
        checkpoint=tmp_path / "checkpoint.json",
    )
    report = package["report"]
    assert len(report["cells"]) == report["summary"]["requested_pairs"] == 2
    assert report["cells"][1]["after"]["reachability"] == "not_evaluated"
    assert not report["cells"][1]["disconnected"]
    assert package["analytics"]["after_not_run_pairs"] == 1
    assert report["summary"]["pairs_disconnected"]["scope"] == "observed_corpus_only"
    graph, baseline, request = inputs("request-acl-v1.1.json")
    package = run_remediation(
        request, graph, baseline, execution_budget=BatchExecutionBudget(max_cells=1)
    )
    bob = package["report"]["cells"][1]
    assert bob["after"]["rediscovery"]["status"] == "not_run"
    assert bob["after"]["reachability"] == "reachable" and bob["bypass_program_ids"]
    assert bob["after"]["scope_proof_ref"] is None


def _semantic(package):
    from scripts.research.remediation_acceptance import normalized_program_identity

    report = package["report"]
    return {
        "summary": report["summary"],
        "cells": [
            {
                "source_id": c["source_id"],
                "goal_id": c["goal_id"],
                **{
                    side: {
                        "reachability": c[side]["reachability"],
                        "complete": c[side]["complete"],
                        "programs": sorted(
                            normalized_program_identity(c, report["comparison_scope_digest"], t)
                            for t in c[side]["trace_refs"]
                        ),
                    }
                    for side in ("before", "after")
                },
            }
            for c in report["cells"]
        ],
    }


def test_resume_and_source_order_are_semantically_stable(tmp_path):
    graph, baseline, request = inputs()
    checkpoint = tmp_path / "resume.json"
    run_remediation(
        request,
        graph,
        baseline,
        execution_budget=BatchExecutionBudget(max_cells=1),
        checkpoint=checkpoint,
    )
    resumed = run_remediation(
        request,
        graph,
        baseline,
        execution_budget=BatchExecutionBudget(max_cells=1),
        checkpoint=checkpoint,
        resume=True,
    )
    complete = run_remediation(request, graph, baseline)
    assert _semantic(resumed) == _semantic(complete)
    assert resumed["execution"]["cache_audit_reexecuted_cells"] == 1
    assert resumed["execution"]["after_executed_cells"] == 1
    reverse = prepare_baseline(
        graph, list(reversed(json.loads(baseline.cells_json))), run_id=baseline.run_id
    )
    assert reverse == baseline
    assert (
        rank_interventions([resumed, complete])[0]["quantities"]
        == rank_interventions([complete, resumed])[0]["quantities"]
    )


@pytest.mark.parametrize("tamper", ["overlay", "integrity", "forged_proof"])
def test_checkpoint_scope_and_native_integrity_fail_closed(tmp_path, tamper):
    graph, baseline, request = inputs()
    path = tmp_path / "cache.json"
    run_remediation(request, graph, baseline, checkpoint=path)
    if tamper == "overlay":
        request = request_for_baseline(
            baseline, read("request-v1.1.json")["edits"], request_id="other-fix"
        )
    else:
        cache = json.loads(path.read_text())
        packet = next(iter(cache["cells"].values()))
        packet["payload"]["outcome"][0]["query_digest"] = "sha256:" + "0" * 64
        if tamper == "forged_proof":
            packet["sha256"] = _digest(packet["payload"])
        path.write_text(json.dumps(cache), encoding="utf-8")
    with pytest.raises(ValueError, match="CHECKPOINT"):
        run_remediation(request, graph, baseline, checkpoint=path, resume=True)


def test_actual_wall_timeout_keeps_replay_successes_without_negative_proof():
    graph, baseline, request = inputs()
    package = run_remediation(
        request, graph, baseline, execution_budget=BatchExecutionBudget(per_query_seconds=0.001)
    )
    assert all(c["after"]["rediscovery"]["status"] == "error" for c in package["report"]["cells"])
    alice, bob = package["report"]["cells"]
    assert alice["after"]["reachability"] == "reachable" and alice["bypass_program_ids"]
    assert bob["after"]["reachability"] == "error" and not bob["disconnected"]
    assert all(
        not c["after"]["complete"] and c["after"]["scope_proof_ref"] is None
        for c in package["report"]["cells"]
    )


def test_error_isolation_retains_other_cells(monkeypatch):
    import src.engine.remediation_runner as runner

    original = runner._execute_after

    def one_error(request, cell, graph, run_id, seconds):
        if cell["source_id"] == "bob":
            raise RuntimeError("injected worker failure")
        return original(request, cell, graph, run_id, seconds)

    monkeypatch.setattr(runner, "_execute_after", one_error)
    graph, baseline, request = inputs()
    report = run_remediation(request, graph, baseline)["report"]
    assert report["cells"][0]["after"]["rediscovery"]["status"] == "complete"
    assert report["cells"][1]["after"]["rediscovery"]["status"] == "error"
    assert not report["cells"][1]["disconnected"]


@pytest.mark.parametrize(
    "tamper", ["after_run", "bypass", "negative_flag", "numeric_scope", "artifact"]
)
def test_published_package_proofs_cannot_be_self_declared(tamper):
    graph, baseline, request = inputs()
    package = run_remediation(request, graph, baseline)
    c = package["report"]["cells"][0]
    if tamper == "after_run":
        c["after"]["rediscovery"]["run_id"] = "borrowed-baseline-run"
    elif tamper == "bypass":
        c["bypass_program_ids"] = []
    elif tamper == "numeric_scope":
        c["conditional_p"].update(status="comparable", comparison_scope_digest="sha256:" + "0" * 64)
    elif tamper == "negative_flag":
        c["after"]["complete"] = False
    else:
        ref = c["after"]["scope_proof_ref"]
        proof = package["artifacts"].pop(ref)
        proof["native_no_path_proven"] = True
        altered = "artifact:" + _digest(proof)
        package["artifacts"][altered] = proof
        c["after"]["scope_proof_ref"] = c["after"]["rediscovery"]["proof_ref"] = altered
    with pytest.raises(ValueError):
        verify_package(package, graph)


def test_unsupported_overlay_remains_in_denominator():
    graph, baseline, request = inputs("request-acl-v1.1.json")
    request["edits"][0].update(catalog_entry_id="acl-revoke")
    request["edits"][0]["relationship"]["kind"] = "GenericAll"
    package = run_remediation(request, graph, baseline)
    assert package["report"]["overlay_disposition"] == "unresolved"
    assert package["report"]["summary"]["unsupported_pairs"] == 2
    assert not package["report"]["summary"]["proven_disconnected_pairs"]
    assert len(package["report"]["cells"]) == 2


def test_fresh_native_effort_resolution_without_fabricated_p():
    from test_public_rating_integration import rated_case

    graph_query, graph = rated_case()
    actor, group = graph_query["aliases"]["Alice"], graph_query["aliases"]["Admins"]
    baseline = prepare_baseline(
        graph, [{"source_id": "alice", "goal_id": "host", "query": graph_query}], run_id="rated"
    )
    edit = copy.deepcopy(read("request-bypass-v1.1.json")["edits"][0])
    edit["key"].update(subject=actor, target=group)
    package = run_remediation(
        request_for_baseline(baseline, [edit], request_id="rated"), graph, baseline
    )
    cell = package["report"]["cells"][0]
    assert cell["effort"]["status"] == "exact"
    assert (cell["effort"]["before"], cell["effort"]["after"], cell["effort"]["delta"]) == (1, 4, 3)
    assert cell["conditional_p"]["status"] == "incomparable"
    assert cell["conditional_p"]["delta_interval"] is None


def test_priority_counterexample_complete_evidence_precedes_observed_cut_percentage():
    graph, baseline, channel = inputs("request-v1.1.json")
    membership = request_for_baseline(
        baseline, read("request-bypass-v1.1.json")["edits"], request_id="membership"
    )
    incomplete = run_remediation(
        channel, graph, baseline, execution_budget=BatchExecutionBudget(max_cells=1)
    )
    complete = run_remediation(membership, graph, baseline)
    assert incomplete["report"]["summary"]["programs_cut"]["percent"] == 100
    assert complete["report"]["summary"]["programs_cut"]["percent"] == 75
    ordered = rank_interventions([incomplete, complete])
    assert ordered[0]["intervention"] == "membership"
    assert rank_interventions([complete, incomplete]) == ordered


def test_inventory_covers_nonstructural_preauth_and_advisory_basis():
    from scripts.research.asrep_inputs import inputs as asrep

    graph, query = asrep()
    baseline = prepare_baseline(
        graph, [{"source_id": "requester", "goal_id": "host", "query": query}], run_id="asrep"
    )
    inventory = inventory_interventions(graph, baseline)
    ids = {c["catalog_entry_id"] for c in inventory["candidates"]}
    assert "asrep-preauth" in ids and "secret-hardening" in ids
    static = next(c for c in inventory["candidates"] if c["catalog_entry_id"] == "asrep-preauth")
    package = run_remediation(
        request_for_baseline(baseline, static["technical_edits"], request_id="preauth"),
        graph,
        baseline,
    )
    assert package["report"]["cells"][0]["disconnected"]
    assert package["report"]["cells"][0]["after"]["program_count"] == 0
    assert (
        next(c for c in inventory["candidates"] if c["catalog_entry_id"] == "secret-hardening")[
            "status"
        ]
        == "unsupported"
    )


def test_wrong_preconditions_and_snapshot_fail_before_effective_execution():
    graph, baseline, request = inputs()
    request["edits"][0]["expected_before"] = None
    with pytest.raises(ValueError, match="expected_before"):
        run_remediation(request, graph, baseline)
    request["scope"]["snapshot_id"] = "sha256:" + "0" * 64
    with pytest.raises(ValueError, match="scope mismatch"):
        run_remediation(request, graph, baseline)


def test_failed_worker_charges_full_logical_expansion_reservation(monkeypatch):
    import src.engine.remediation_runner as runner

    def failed(*args):
        raise RuntimeError("worker result unavailable")

    monkeypatch.setattr(runner, "_execute_after", failed)
    graph, baseline, request = inputs()
    package = run_remediation(
        request, graph, baseline, execution_budget=BatchExecutionBudget(max_expansions=1000)
    )
    assert package["execution"]["after_executed_cells"] == 1
    assert package["execution"]["new_after_expansions"] == 0
    assert package["execution"]["charged_expansion_budget"] == 1000
    assert package["analytics"]["after_not_run_pairs"] == 1


def test_same_effect_priority_ties_use_stable_ids():
    graph, baseline, request = inputs()
    one = run_remediation(request | {"request_id": "a"}, graph, baseline)
    two = run_remediation(request | {"request_id": "z"}, graph, baseline)
    assert [r["intervention"] for r in rank_interventions([two, one])] == ["a", "z"]
    assert rank_interventions([two, one]) == rank_interventions([one, two])


def test_capped_effort_stays_incumbent_with_no_delta():
    from test_public_rating_integration import rated_case

    query, graph = rated_case()
    query["budget"]["max_paths"] = 1
    baseline = prepare_baseline(
        graph, [{"source_id": "alice", "goal_id": "host", "query": query}], run_id="capped-C"
    )
    edit = copy.deepcopy(read("request-bypass-v1.1.json")["edits"][0])
    edit["key"].update(subject=query["aliases"]["Alice"], target=query["aliases"]["Admins"])
    package = run_remediation(
        request_for_baseline(baseline, [edit], request_id="capped-C"), graph, baseline
    )
    effort = package["report"]["cells"][0]["effort"]
    assert effort["status"] == "incumbent"
    assert effort["delta"] is None


def test_ineffective_selected_fix_keeps_declared_source_exposed():
    graph, baseline, request = inputs("request-acl-v1.1.json", sources=("bob",))
    package = run_remediation(request, graph, baseline)
    cell = package["report"]["cells"][0]
    assert cell["before"]["program_count"] == cell["after"]["program_count"] == 1
    assert package["report"]["summary"]["programs_cut"]["numerator"] == 0
    assert package["report"]["summary"]["exposed_sources_after"] == ["bob"]


def test_native_audit_detects_omitted_success_even_when_transport_is_consistent():
    graph, baseline, request = inputs()
    package = run_remediation(request, graph, baseline)
    report = package["report"]
    cell = report["cells"][0]
    cell["after"].update(
        reachability="unknown",
        unresolved_feasibility=True,
        program_count=0,
        route_count=0,
        witness_program_ids=[],
        route_ids=[],
        trace_refs=[],
    )
    cell["bypass_program_ids"] = []
    report["summary"].update(exposed_sources_after=[], goals_still_reachable=[], unknown_pairs=1)
    for name in ("programs_cut", "routes_cut", "pairs_disconnected"):
        report["summary"][name]["scope"] = "observed_corpus_only"
    validate_result(
        report
    )  # The reviewed validator checks consistency, not actual engine execution.
    with pytest.raises(ValueError, match="after native proof mismatch"):
        verify_package(package, graph)


def test_multiple_goals_use_independent_initial_states_and_full_denominator():
    graph, baseline, request = inputs()
    cells = json.loads(baseline.cells_json)
    group = request["edits"][0]["key"]["target"]
    for old in list(cells):
        other = copy.deepcopy(old)
        other["goal_id"] = "membership"
        other["query"]["target"] = group
        other["query"]["target_goal"] = {
            "target": group,
            "required_state": {"effective_member": [[other["query"]["initial_actor"], group]]},
        }
        cells.append(other)
    baseline = prepare_baseline(graph, list(reversed(cells)), run_id="multi-goal")
    request = request_for_baseline(baseline, request["edits"], request_id="membership")
    report = run_remediation(request, graph, baseline)["report"]
    assert report["summary"]["requested_pairs"] == len(report["cells"]) == 4
    assert report["summary"]["fully_disconnected_sources"] == ["bob"]
    assert report["summary"]["goals_still_reachable"] == ["host"]
    assert all(
        c["after"]["reachability"] == "proven_unreachable"
        for c in report["cells"]
        if c["goal_id"] == "membership"
    )
