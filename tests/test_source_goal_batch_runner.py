"""Real #275 runner replay against independent #268 and finite numeric oracles."""

import copy
import json
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import pytest
from jsonschema.exceptions import ValidationError

from src.engine.batch import (
    BatchExecutionBudget,
    _atomic_json,
    _query_for_cell,
    discover_source,
    run_source_goal_batch,
    validate_schema,
)
from src.engine.graph import EngineGraph
from src.engine.query import materialize_query, run_attack_query
from src.engine.ranking.resolution_service import canonical_digest
from src.engine.ranking.resolver import generate_rating_lookup_key_p, generate_work_unit_id
from src.engine.search import SearchBudget
from src.engine.semantics import FactOrigin, RuntimeFact
from tests.test_public_rating_integration import rated_case, registry
from tests.test_source_goal_batch_contract import (
    ADMINS_ID,
    ALICE_ID,
    HOST_C0_ID,
    BatchQueryRequest,
    load_json,
)

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests/fixtures/batch_contracts"
GRAPH = ROOT / "tests/fixtures/attack_scenarios/graphs/two-routes.json"


@pytest.fixture
def inputs():
    return load_json(FIXTURES / "batch_request_example.json"), EngineGraph.from_canonical(
        load_json(GRAPH)
    )


def semantic(result):
    value = copy.deepcopy(result.to_dict())
    value["reproducibility"].pop("runtime")
    return value


def trace(result, source, goal):
    return result.reproducibility["inputs"]["public_queries"][canonical_digest([source, goal])]


def test_real_runner_replays_frozen_contract_matrix(inputs):
    request, graph = inputs
    expected = load_json(FIXTURES / "batch_result_example.json")
    actual = run_source_goal_batch(request, graph)
    validate_schema(actual.to_dict(), "batch-query-result")
    for sid, row in actual.source_goal_matrix.items():
        for gid, cell in row.items():
            data = cell.to_dict()
            data["diagnostics"] = [
                d for d in data["diagnostics"] if d.get("code") != "PUBLIC_QUERY_TRACE"
            ]
            for diagnostic in data["diagnostics"]:
                for key in ("node_id", "node_kind", "profile_kind"):
                    diagnostic.pop(key, None)
            if data["min_effort_path"]:
                data["min_effort_path"].pop("trace_ref")
                data["min_effort_path"].pop("candidate_id")
            assert data == expected["source_goal_matrix"][sid][gid]
    assert actual.summary["declared_cells"] == 8
    assert actual.summary["successful_cells"] == 2
    assert actual.summary["effort_rated_cells"] == actual.summary["likelihood_rated_cells"] == 0
    assert [e.source_id for e in actual.source_prioritization] == [
        e["source_id"] for e in expected["source_prioritization"]
    ]


def test_input_order_and_source_goal_isolation(inputs):
    request, graph = inputs
    before = graph.to_canonical()
    result = run_source_goal_batch(request, graph)
    reverse = copy.deepcopy(request)
    reverse["sources"].reverse()
    reverse["target_manifest"]["targets"].reverse()
    reverse["target_goal_ids"] = list(
        reversed(request["target_manifest"]["default_discovery_goals"])
    )
    assert semantic(result) == semantic(run_source_goal_batch(reverse, graph))
    for source in request["sources"]:
        single = {**request, "sources": [source]}
        outcome = run_source_goal_batch(single, graph)
        assert (
            outcome.source_goal_matrix[source["source_id"]]
            == result.source_goal_matrix[source["source_id"]]
        )
    assert graph.to_canonical() == before


def test_discovery_drilldown_and_public_single_source_parity(inputs):
    raw, graph = inputs
    raw["sources"] = raw["sources"][:1]
    request = BatchQueryRequest.from_dict(raw)
    full = run_source_goal_batch(request, graph)
    discovered = discover_source(request, graph)
    assert full.source_goal_matrix == discovered.source_goal_matrix
    empty = run_source_goal_batch({**raw, "target_goal_ids": []}, graph)
    assert full.source_goal_matrix == empty.source_goal_matrix
    gid = "goal-synthetic-da"
    assert (
        run_source_goal_batch({**raw, "target_goal_ids": [gid]}, graph).source_goal_matrix[
            request.sources[0].source_id
        ][gid]
        == full.source_goal_matrix[request.sources[0].source_id][gid]
    )
    with pytest.raises(KeyError, match="not found"):
        run_source_goal_batch({**raw, "target_goal_ids": ["nonexistent"]}, graph)


@pytest.mark.parametrize(
    "mutation",
    [
        "snapshot",
        "source_kind",
        "source_missing",
        "duplicate",
        "target_kind",
        "unknown_field",
        "schema_version",
    ],
)
def test_invalid_inputs_rejected_before_execution(inputs, monkeypatch, mutation):
    raw, graph = inputs
    if mutation == "snapshot":
        raw["snapshot_id"] = "sha256:" + "0" * 64
    elif mutation == "source_kind":
        raw["sources"][0]["node_kind"] = "Computer"
    elif mutation == "source_missing":
        raw["sources"][0]["node_id"] = "S-1-5-21-1000-2000-3000-9999"
    elif mutation == "duplicate":
        raw["sources"].append(raw["sources"][0])
    elif mutation == "target_kind":
        raw["target_manifest"]["targets"][0]["target_node_kind"] = "Computer"
    elif mutation == "schema_version":
        raw["schema_version"] = "wrong/2.0.0"
    else:
        raw["typo"] = True

    def should_not_run(*args, **kwargs):
        pytest.fail("invalid request executed")

    monkeypatch.setattr("src.engine.batch.run_attack_query", should_not_run)
    with pytest.raises((ValueError, KeyError, ValidationError)):
        run_source_goal_batch(raw, graph)


@pytest.mark.parametrize(
    "context,code",
    [
        (None, "MISSING_AUTHENTICATION_CONTEXT"),
        ("", "MISSING_AUTHENTICATION_CONTEXT"),
        (ALICE_ID, "INVALID_AUTHENTICATION_CONTEXT"),
        (ADMINS_ID, "INVALID_AUTHENTICATION_CONTEXT"),
        ("S-1-5-21-1000-2000-3000-9999", "INVALID_AUTHENTICATION_CONTEXT"),
    ],
)
def test_password_context_boundary(inputs, context, code):
    raw, graph = inputs
    source = {
        **raw["sources"][0],
        "profile_kind": "user_leaked_password",
        "authentication_context": context,
    }
    result = run_source_goal_batch({**raw, "sources": [source]}, graph)
    assert all(
        c.status == "unsupported_source" and c.diagnostics[0]["code"] == code
        for c in result.source_goal_matrix[source["source_id"]].values()
    )
    assert result.source_prioritization[0].disposition == "unsupported"


def password_case(raw):
    raw = copy.deepcopy(raw)
    source = raw["sources"][0]
    source["profile_kind"] = "user_leaked_password"
    source["authentication_context"] = HOST_C0_ID
    source["declared_assumptions"] += [
        {
            "predicate": p,
            "subject": ALICE_ID,
            "target": HOST_C0_ID,
            "value": True,
            "rationale": "Synthetic declared activation",
            "provenance_reference": "synthetic://275",
        }
        for p in ("secret_valid", "network_kdc_reachable")
    ]
    raw["sources"] = [source]
    return raw


def test_password_usable_unknown_and_disabled_follow_independent_oracle(inputs):
    raw, graph = inputs
    oracle = load_json(FIXTURES / "oracles_expected.json")["cases"][
        "case_a_leaked_password_vs_usable_identity"
    ]
    request = password_case(raw)
    result = run_source_goal_batch(request, graph)
    sid = request["sources"][0]["source_id"]
    actual_steps = [
        s["result"]["request"]["technique_id"]
        for s in trace(result, sid, "goal-synthetic-da")["result"]["paths"][0]["transition_history"]
    ]
    assert len(actual_steps) == oracle["password_profile"]["expected_success_steps_to_da"]
    assert actual_steps[0] == oracle["password_profile"]["expected_first_step"]
    request["sources"][0]["declared_assumptions"] = []
    unknown = run_source_goal_batch(request, graph)
    assert unknown.source_goal_matrix[sid]["goal-synthetic-da"].status == "indeterminate"
    disabled = load_json(GRAPH)
    next(n for n in disabled["nodes"] if n["id"] == ALICE_ID)["enabled"] = False
    blocked = run_source_goal_batch(request, EngineGraph.from_canonical(disabled))
    assert blocked.source_goal_matrix[sid]["goal-synthetic-da"].status == "blocked"


def test_checkpoint_and_known_false_veto(inputs):
    raw, graph = inputs
    raw["sources"] = raw["sources"][:1]
    # Static snapshot FALSE is authoritative over the corresponding TRUE scenario.
    result = run_source_goal_batch(
        raw,
        graph,
        runtime_facts=[
            {
                "predicate": "admin_channel",
                "subject": ALICE_ID,
                "target": HOST_C0_ID,
                "value": False,
                "origin": "observed_evidence",
                "scope": "synthetic-snapshot",
                "rationale": "Independent observed gate FALSE",
                "provenance_reference": "synthetic://275/false",
            }
        ],
    )
    host = result.source_goal_matrix[raw["sources"][0]["source_id"]]["goal-synthetic-c0-host"]
    assert host.checkpoint_reached and not host.final_goal_reached
    assert host.status == "checkpoint_reached_final_goal_blocked"


def test_global_budget_keeps_all_cells_and_resume_equals_complete(inputs, tmp_path):
    raw, graph = inputs
    checkpoint = tmp_path / "checkpoint.json"
    partial = run_source_goal_batch(
        raw, graph, execution_budget=BatchExecutionBudget(max_cells=1), checkpoint=checkpoint
    )
    assert partial.summary["declared_cells"] == 8
    assert len(partial.summary["not_run_cells"]) == 7
    assert partial.source_prioritization[0].disposition == "not_evaluated"
    resumed = run_source_goal_batch(raw, graph, checkpoint=checkpoint, resume=True)
    assert resumed.reproducibility["runtime"]["reused_cells"] == 1
    assert semantic(resumed) == semantic(run_source_goal_batch(raw, graph))
    complete_resume = run_source_goal_batch(raw, graph, checkpoint=checkpoint, resume=True)
    assert complete_resume.reproducibility["runtime"]["executed_cells"] == 0
    assert semantic(complete_resume) == semantic(resumed)


@pytest.mark.parametrize(
    "mutation", ["profile", "basis", "goal", "graph", "techniques", "mode", "tamper"]
)
def test_resume_refuses_scope_drift_and_tampering(inputs, tmp_path, mutation):
    raw, graph = inputs
    checkpoint = tmp_path / "checkpoint.json"
    run_source_goal_batch(raw, graph, checkpoint=checkpoint)
    options = {}
    if mutation == "profile":
        raw["sources"][0]["profile_kind"] = "user_leaked_password"
    elif mutation == "basis":
        raw["rating_resolution"] = {"version": "public-rating-resolution/1.1.0", "scope": {}}
    elif mutation == "goal":
        raw["target_goal_ids"] = ["goal-synthetic-da"]
    elif mutation == "mode":
        raw["evaluation_mode"] = "evidence_only"
    elif mutation == "graph":
        canonical = graph.to_canonical()
        canonical["nodes"][0]["enabled"] = False
        graph = EngineGraph.from_canonical(canonical)
    elif mutation == "techniques":
        options["allowed_techniques"] = ["propagate_group_entitlement"]
    else:
        cached = load_json(checkpoint)
        next(iter(cached["cells"].values()))["payload"]["cell"]["min_effort"] = 999
        checkpoint.write_text(json.dumps(cached))
    with pytest.raises(ValueError, match="CHECKPOINT_"):
        run_source_goal_batch(raw, graph, checkpoint=checkpoint, resume=True, **options)


def test_error_isolation_and_partial_witnesses(inputs, monkeypatch, tmp_path):
    raw, graph = inputs
    calls = []

    def fail_one(query, graph):
        calls.append(query.target)
        if len(calls) == 1:
            raise RuntimeError("injected independent cell failure")
        return run_attack_query(query, graph)

    monkeypatch.setattr("src.engine.batch.run_attack_query", fail_one)
    result = run_source_goal_batch(raw, graph)
    assert result.summary["status_counts"]["error"] == 1
    assert len(calls) == 6
    assert result.summary["declared_cells"] == 8
    monkeypatch.setattr("src.engine.batch.run_attack_query", run_attack_query)
    raw["common_budget"]["max_paths"] = 1
    raw["sources"] = raw["sources"][:1]
    checkpoint = tmp_path / "partial.json"
    partial = run_source_goal_batch(raw, graph, checkpoint=checkpoint)
    host = partial.source_goal_matrix[raw["sources"][0]["source_id"]]["goal-synthetic-c0-host"]
    assert host.final_goal_reached and host.truncated
    assert host.min_effort is None
    packet = trace(partial, raw["sources"][0]["source_id"], "goal-synthetic-c0-host")
    assert packet["result"]["paths"]
    assert packet["guarantees"]["is_minimum_proven_over_scope"] is False
    assert (
        canonical_digest([raw["sources"][0]["source_id"], "goal-synthetic-c0-host"])
        not in load_json(checkpoint)["cells"]
    )


def test_global_expansion_budget_never_claims_no_path(inputs):
    raw, graph = inputs
    result = run_source_goal_batch(
        raw, graph, execution_budget=BatchExecutionBudget(max_expansions=1)
    )
    assert (
        sum(c.expansions for row in result.source_goal_matrix.values() for c in row.values()) <= 1
    )
    assert result.summary["not_run_cells"]
    assert result.source_prioritization[0].disposition == "not_evaluated"


def test_timeout_isolated_and_not_cached(inputs, tmp_path):
    raw, graph = inputs
    raw["sources"] = raw["sources"][:1]
    raw["target_goal_ids"] = ["goal-synthetic-da"]
    result = run_source_goal_batch(
        raw,
        graph,
        execution_budget=BatchExecutionBudget(per_query_seconds=0.001),
        checkpoint=tmp_path / "timeout.json",
    )
    cell = result.source_goal_matrix[raw["sources"][0]["source_id"]]["goal-synthetic-da"]
    assert cell.status == "truncated_incomplete"
    assert cell.diagnostics[0]["code"] == "QUERY_TIMEOUT"
    assert not load_json(tmp_path / "timeout.json")["cells"]
    assert not cell.final_goal_reached


def test_cli_writes_schema_valid_result_and_rejects_unknown_target(inputs, tmp_path):
    output = tmp_path / "output.json"
    command = [
        sys.executable,
        "-m",
        "src.engine.batch_cli",
        "--batch-request",
        str(FIXTURES / "batch_request_example.json"),
        "--graph",
        str(GRAPH),
        "--label",
        "synthetic",
        "--output",
        str(output),
        "--discover",
        "--query-seconds",
        "10",
    ]
    completed = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
    assert completed.returncode == 0, completed.stderr
    validate_schema(load_json(output), "batch-query-result")
    assert load_json(output)["summary"]["successful_cells"] == 2
    command.remove("--discover")
    command += ["--goal", "unknown"]
    refused = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
    assert refused.returncode == 2 and "not found" in refused.stderr


def independently_scoped_numeric_fixture(raw, graph, *, shared=False):
    """Published identity formulas bind declared inputs; expected C/P precede search.

    Two active alternatives: direct C=4/P=1/4; inherited C=1/P=3/4.
    An optional shared prerequisite adds C=1/P=1/2 once on each alternative.
    These are synthetic algorithm inputs, never adopted production parameters.
    """
    raw = copy.deepcopy(raw)
    raw["sources"] = raw["sources"][:1]
    raw["target_goal_ids"] = ["goal-synthetic-c0-host"]
    legacy, _ = rated_case(shared=shared)
    raw["rating_resolution"] = legacy["rating_resolution"]
    request = BatchQueryRequest.from_dict(raw)
    source = request.sources[0]
    goal = request.resolve_target_goals()[0]
    declared, _ = _query_for_cell(request, source, goal, graph, None, request.common_budget)
    config = raw["rating_resolution"]
    scope = declared.rating_resolution["scope"]
    scenario = scope["scenario_id"]
    effort = config["registries"]["effort"]["data"]
    for record in effort:
        record["applicability"]["scopes"] = [scenario]
    config["registries"]["effort"] = registry(effort)
    prep = None
    if shared:
        rules = config["registries"]["work"]["data"]
        rules[0]["scenario_id"] = scenario
        config["registries"]["work"] = registry(rules)
        context = {
            "actor": ALICE_ID,
            "target": HOST_C0_ID,
            "auth_context": ALICE_ID,
            "resource_context": None,
            "policy_id": None,
            "scenario_id": scenario,
            "method": "AdminTo",
        }
        prep = generate_work_unit_id(
            "auth_context",
            ALICE_ID,
            HOST_C0_ID,
            "ctx-" + canonical_digest(context).removeprefix("sha256:"),
            "intra_forest",
        )
    likelihood = []
    for source_id in [ALICE_ID, ADMINS_ID] + ([ALICE_ID] if shared else []):
        is_prep = shared and len(likelihood) == 2
        technique = "auth_context" if is_prep else "obtain_admin_execution_on_host"
        context = {
            "source_id": source_id,
            "method": "AdminTo",
            "auth_context": ALICE_ID,
            "resource_context": None,
            "policy_id": None,
            "scope": scenario,
        }
        unit = (
            prep
            if is_prep
            else generate_work_unit_id(
                technique,
                ALICE_ID,
                HOST_C0_ID,
                "ctx-" + canonical_digest(context).removeprefix("sha256:"),
                "intra_forest",
            )
        )
        prefix = (unit,) if not shared or is_prep else (prep, unit)
        key = generate_rating_lookup_key_p(
            scenario_id=scenario,
            scenario_version=scope["scenario_version"],
            snapshot_id=scope["snapshot_id"],
            foothold_node_id=ALICE_ID,
            ordered_work_prefix=prefix,
            outcome_work_unit_id=unit,
            outcome_technique=technique,
            actor_id=ALICE_ID,
            source_id=source_id,
            target_id=HOST_C0_ID,
            method="AdminTo",
            budget=12,
            horizon="24h",
            boundary="intra_forest",
            scope=scenario,
            auth_context=ALICE_ID,
        ).to_dict()
        key.pop("dimension")
        bound = "1/2" if is_prep else "1/4" if source_id == ALICE_ID else "3/4"
        likelihood.append(
            {
                **key,
                "disposition": "rated",
                "review_status": "accepted",
                "lower": bound,
                "upper": bound,
                "basis_category": "synthetic_test_only",
                "rationale": "Independent synthetic fixture",
                "review_reference": "synthetic://275/P",
                "provenance_digest": "sha256:" + "a" * 64,
            }
        )
    config["registries"]["likelihood"] = registry(likelihood)
    return raw


@pytest.mark.parametrize("shared,expected_c,expected_p", [(False, 1, 0.75), (True, 2, 0.375)])
def test_authoritative_selected_c_p_and_shared_work(inputs, shared, expected_c, expected_p):
    raw, graph = inputs
    request = independently_scoped_numeric_fixture(raw, graph, shared=shared)
    result = run_source_goal_batch(request, graph)
    cell = result.source_goal_matrix[request["sources"][0]["source_id"]]["goal-synthetic-c0-host"]
    assert cell.min_effort == expected_c
    assert cell.likelihood_interval == (expected_p, expected_p)
    assert cell.likelihood_status == "rated"
    packet = trace(result, request["sources"][0]["source_id"], "goal-synthetic-c0-host")
    assert packet["guarantees"]["is_minimum_proven_over_scope"] is True
    assert (
        cell.min_effort_path["candidate_id"] == packet["result"]["min_effort"]["best_candidate_id"]
    )
    assert cell.min_effort_path["steps"][-1] == "obtain_admin_execution_on_host"


def test_rebinding_does_not_expand_numeric_scope_or_adopt_proposed_records(inputs):
    raw, graph = inputs
    legacy, _ = rated_case()
    raw["sources"] = raw["sources"][:1]
    raw["target_goal_ids"] = ["goal-synthetic-c0-host"]
    raw["rating_resolution"] = copy.deepcopy(legacy["rating_resolution"])
    before = copy.deepcopy(raw["rating_resolution"])
    result = run_source_goal_batch(raw, graph)
    cell = result.source_goal_matrix[raw["sources"][0]["source_id"]]["goal-synthetic-c0-host"]
    assert cell.final_goal_reached and cell.min_effort is None and cell.likelihood_interval is None
    assert raw["rating_resolution"] == before
    scoped = independently_scoped_numeric_fixture(raw, graph)
    records = scoped["rating_resolution"]["registries"]["effort"]["data"]
    for record in records:
        record["review_status"] = "proposed_pending_b_review"
    scoped["rating_resolution"]["registries"]["effort"] = registry(records)
    refused = run_source_goal_batch(scoped, graph)
    assert (
        refused.source_goal_matrix[raw["sources"][0]["source_id"]][
            "goal-synthetic-c0-host"
        ].min_effort
        is None
    )


def test_snapshot_worker_preserves_evidence_and_rejects_assumption_override():
    from scripts.research.asrep_inputs import inputs as asrep_inputs
    from tests.test_source_goal_batch_contract import BatchSourceItem

    graph, query = asrep_inputs()
    owner = query["initial_state"]["known_identity"][0]
    source = BatchSourceItem(
        "password",
        owner,
        "User",
        "user_leaked_password",
        query["authentication_context"],
        tuple(query["assumptions"]),
    )
    # Enum inputs are reconstructed through the published JSON request contract.
    raw = load_json(FIXTURES / "batch_request_example.json")
    raw["snapshot_id"] = graph.metadata["snapshot_id"]
    raw["sources"] = [source.to_dict()]
    raw["target_manifest"]["snapshot_id"] = graph.metadata["snapshot_id"]
    raw["target_manifest"]["targets"] = [
        {
            "goal_id": "host",
            "category": "tier_0_host",
            "target_node_id": query["target"],
            "target_node_kind": "Computer",
            "display_name": "Synthetic Host",
            "technical_consequence": "host_admin_execution",
            "impact_rating": "High",
            "required_control_level": "host_admin_execution",
            "required_state": {"admin_control": [query["target"]]},
        }
    ]
    raw["target_manifest"]["default_discovery_goals"] = ["host"]
    direct = run_source_goal_batch(raw, graph)
    worker = run_source_goal_batch(
        raw, graph, execution_budget=BatchExecutionBudget(per_query_seconds=10)
    )
    assert direct.source_goal_matrix == worker.source_goal_matrix


@pytest.mark.parametrize("mode", ["scenario", "evidence_only"])
def test_worker_and_recorded_query_preserve_public_semantics(inputs, mode):
    raw, graph = inputs
    request = independently_scoped_numeric_fixture(raw, graph)
    request["evaluation_mode"] = mode
    request["sources"] = request["sources"][:1]
    request["target_goal_ids"] = ["goal-synthetic-c0-host"]
    direct = run_source_goal_batch(request, graph)
    worker = run_source_goal_batch(
        request, graph, execution_budget=BatchExecutionBudget(per_query_seconds=10)
    )
    assert direct.source_goal_matrix == worker.source_goal_matrix
    source_id = request["sources"][0]["source_id"]
    goal_id = request["target_goal_ids"][0]
    packet = trace(direct, source_id, goal_id)
    assert packet == trace(worker, source_id, goal_id)
    replayed = run_attack_query(materialize_query(packet["query"], graph), graph)
    assert replayed.status == packet["result"]["status"]
    assert replayed.min_effort == packet["result"]["min_effort"]
    assert replayed.top_k_result is None
    # An explicit invalid Top-K request must still be rejected by the public API.
    with pytest.raises(ValueError, match="top_k must be a positive integer"):
        materialize_query({**packet["query"], "top_k": None}, graph)


@pytest.mark.parametrize("wire_request", [False, True])
def test_discover_source_preserves_evidence_only_assumptions_and_caps(inputs, wire_request):
    raw, graph = inputs
    raw["sources"] = raw["sources"][:1]
    raw["evaluation_mode"] = "evidence_only"
    raw["common_budget"] = {"max_paths": 8, "max_steps": 4, "max_expansions": 24}
    raw["sources"][0]["custom_budget"] = {"max_paths": 3, "max_steps": 2, "max_expansions": 5}
    raw["target_goal_ids"] = ["goal-synthetic-c0-host"]
    request = raw if wire_request else BatchQueryRequest.from_dict(raw)
    batch = run_source_goal_batch(request, graph)
    helper = discover_source(request, graph)
    assert semantic(batch) == semantic(helper)
    sid = raw["sources"][0]["source_id"]
    assert not helper.source_goal_matrix[sid]["goal-synthetic-c0-host"].final_goal_reached
    packet = trace(helper, sid, "goal-synthetic-c0-host")
    assert packet["query"]["evaluation_mode"] == "evidence_only"
    assert packet["materialized"]["rejected_assumptions"]
    assert packet["result"]["caps"] == raw["sources"][0]["custom_budget"]


@pytest.mark.parametrize("shared", [False, True])
def test_discover_source_preserves_numeric_basis_and_target_selection(inputs, shared):
    raw, graph = inputs
    raw = independently_scoped_numeric_fixture(raw, graph, shared=shared)
    before = copy.deepcopy(raw)
    request = BatchQueryRequest.from_dict(raw)
    batch = run_source_goal_batch(request, graph)
    helper = discover_source(request, graph)
    assert semantic(batch) == semantic(helper)
    cell = next(iter(next(iter(helper.source_goal_matrix.values())).values()))
    assert cell.min_effort == (2 if shared else 1)
    assert cell.likelihood_interval == ((0.375, 0.375) if shared else (0.75, 0.75))
    assert list(next(iter(helper.source_goal_matrix.values()))) == raw["target_goal_ids"]
    assert raw == before


def test_discover_source_preserves_common_budget_and_explicit_source_selection(inputs):
    raw, graph = inputs
    request = BatchQueryRequest.from_dict(raw)
    sid = request.sources[0].source_id
    request = replace(
        request, common_budget=SearchBudget(1, 1, 1), target_goal_ids=("goal-synthetic-c0-host",)
    )
    selected = replace(request, sources=(request.sources[0],))
    assert semantic(discover_source(request, graph, source_id=sid)) == semantic(
        run_source_goal_batch(selected, graph)
    )
    with pytest.raises(ValueError, match="requires source_id"):
        discover_source(request, graph)
    with pytest.raises(ValueError, match="exactly one"):
        discover_source(request, graph, source_id="unknown")


@pytest.mark.parametrize("origin", [FactOrigin.DECLARED_ASSUMPTION, FactOrigin.UNSPECIFIED])
@pytest.mark.parametrize("typed", [False, True])
def test_batch_wide_assumption_or_unspecified_refused_before_any_cell(
    inputs, monkeypatch, tmp_path, origin, typed
):
    raw, graph = inputs
    fact = {
        "predicate": "admin_channel",
        "subject": ALICE_ID,
        "target": HOST_C0_ID,
        "value": True,
        "origin": origin,
        "scope": "synthetic-runtime",
        "rationale": "Synthetic record",
        "provenance_reference": "synthetic://275/origin",
    }
    forbidden = RuntimeFact(**fact) if typed else fact
    observed = {**fact, "origin": FactOrigin.OBSERVED_EVIDENCE}

    def never_execute(*args, **kwargs):
        pytest.fail("forbidden batch-wide origin reached a cell")

    monkeypatch.setattr("src.engine.batch._query_for_cell", never_execute)
    checkpoint = tmp_path / "checkpoint.json"
    with pytest.raises(ValueError, match="BATCH_RUNTIME_FACT_ORIGIN_REFUSED"):
        run_source_goal_batch(
            raw, graph, runtime_facts=[observed, forbidden], checkpoint=checkpoint
        )
    assert not checkpoint.exists()


@pytest.mark.parametrize(
    "value,expected", [(True, "complete_success"), (False, "checkpoint_reached_final_goal_blocked")]
)
@pytest.mark.parametrize("typed", [False, True])
def test_batch_observed_facts_keep_truth_and_false_veto(inputs, value, expected, typed):
    raw, graph = inputs
    raw["sources"] = raw["sources"][:1]
    fact = {
        "predicate": "admin_channel",
        "subject": ALICE_ID,
        "target": HOST_C0_ID,
        "value": value,
        "origin": FactOrigin.OBSERVED_EVIDENCE,
        "scope": "synthetic-runtime",
        "rationale": "Observed fixture",
        "provenance_reference": "synthetic://275/observed",
    }
    result = run_source_goal_batch(
        raw, graph, runtime_facts=[RuntimeFact(**fact) if typed else fact]
    )
    sid = raw["sources"][0]["source_id"]
    assert result.source_goal_matrix[sid]["goal-synthetic-c0-host"].status == expected
    facts = trace(result, sid, "goal-synthetic-c0-host")["materialized"]["runtime_context"]["facts"]
    actual = next(f for f in facts if f["predicate"] == "admin_channel")
    assert actual["value"] is value and actual["origin"] == "observed_evidence"
    if not value:
        rejected = trace(result, sid, "goal-synthetic-c0-host")["materialized"][
            "rejected_assumptions"
        ]
        assert any(
            r["predicate"] == "admin_channel" and r["reason"] == "known_false_veto"
            for r in rejected
        )


def test_batch_observed_default_and_explicit_unknown_stay_supported(inputs):
    raw, graph = inputs
    raw["sources"] = raw["sources"][:1]
    observed = {
        "predicate": "admin_channel",
        "subject": ALICE_ID,
        "target": HOST_C0_ID,
        "value": True,
        "provenance_reference": "synthetic://275/default",
    }
    explicit = {**observed, "origin": "observed_evidence"}
    default = run_source_goal_batch(raw, graph, runtime_facts=[observed])
    same = run_source_goal_batch(raw, graph, runtime_facts=[explicit])
    assert default.source_goal_matrix[raw["sources"][0]["source_id"]][
        "goal-synthetic-c0-host"
    ].final_goal_reached
    assert same.source_goal_matrix[raw["sources"][0]["source_id"]][
        "goal-synthetic-c0-host"
    ].final_goal_reached
    unknown = {**explicit, "origin": "unknown", "value": None}
    result = run_source_goal_batch(raw, graph, runtime_facts=[unknown])
    cell = result.source_goal_matrix[raw["sources"][0]["source_id"]]["goal-synthetic-c0-host"]
    assert cell.final_goal_reached  # Source-local unknown-only assumption may fill the gate.


def test_cli_refuses_batch_wide_assumption_origin(inputs, tmp_path):
    facts = tmp_path / "facts.json"
    fact = {
        "predicate": "admin_channel",
        "subject": ALICE_ID,
        "target": HOST_C0_ID,
        "value": True,
        "origin": "declared_assumption",
        "scope": "synthetic-runtime",
        "rationale": "Must be source-local",
        "provenance_reference": "synthetic://275/refused",
    }
    facts.write_text(json.dumps([fact]))
    output = tmp_path / "result.json"
    command = [
        sys.executable,
        "-m",
        "src.engine.batch_cli",
        "--batch-request",
        str(FIXTURES / "batch_request_example.json"),
        "--graph",
        str(GRAPH),
        "--label",
        "synthetic",
        "--runtime-facts",
        str(facts),
        "--output",
        str(output),
    ]
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
    assert result.returncode == 2 and "BATCH_RUNTIME_FACT_ORIGIN_REFUSED" in result.stderr
    assert not output.exists()


def test_failed_checkpoint_serialization_preserves_previous_checkpoint(tmp_path):
    path = tmp_path / "checkpoint.json"
    original = b'{"previous_complete_cell": true}\n'
    path.write_bytes(original)
    with pytest.raises(TypeError):
        _atomic_json(path, {"unserializable_cell": object()})
    assert path.read_bytes() == original
