"""Executable public query integration; expectations consume accepted #206/#207."""

import copy
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

from src.engine.query_cli import canonical_json, wire

pytestmark = pytest.mark.integration

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests/fixtures/attack_scenarios"
GRAPH = FIXTURES / "graphs/two-routes.json"
QUERY = ROOT / "tests/fixtures/query_cli/two-routes-query.json"
RATINGS = ROOT / "docs/research/ratings/week4/synthetic-a2-e.json"


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture
def query():
    return read(QUERY)


def run_cli(tmp_path, query, *options, success=True, graph=GRAPH):
    path = tmp_path / "query.json"
    path.write_text(json.dumps(query), encoding="utf-8")
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "src.engine.query_cli",
            "--query",
            str(path),
            *([] if "--snapshot" in options else ["--graph", str(graph)]),
            "--label",
            "synthetic",
            *map(str, options),
        ],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        capture_output=True,
    )
    if success:
        assert proc.returncode == 0, proc.stderr
        assert not proc.stderr
        if "--output" in options:
            assert proc.stdout == ""
            return read(Path(options[options.index("--output") + 1]))
        return json.loads(proc.stdout)
    assert proc.returncode != 0
    assert proc.stdout == ""
    return proc


def signature(request):
    return tuple(request[k] for k in ("technique_id", "actor", "source", "target"))


@pytest.mark.parametrize("format_options", [(), ("--compact-output",)])
def test_exact_independent_oracle_and_two_runs(tmp_path, query, format_options):
    oracle = read(FIXTURES / "week4-v1.json")
    scenario = oracle["scenarios"][0]
    aliases = oracle["graphs"]["two-routes"]["aliases"]
    steps = {
        step["step_id"]: (
            step["request"]["technique_id"],
            *(aliases[step["request"][k]] for k in ("actor", "source", "target")),
        )
        for step in scenario["steps"]
    }
    expected = {
        tuple(steps[s] for s in path)
        for path in scenario["variants"][0]["expected_search"]["acceptable_paths"]
    }
    first = run_cli(tmp_path, query, "--ranking-query", RATINGS, *format_options)
    second = run_cli(tmp_path, query, "--ranking-query", RATINGS, *format_options)
    semantic = first["semantic"]
    actual = {
        tuple(signature(step["result"]["request"]) for step in path["transition_history"])
        for path in semantic["candidates"]
    }
    assert actual == expected
    from scripts.research.attack_scenarios import state_from

    actual_states = {canonical_json(semantic["materialized"]["initial_attack_state"])} | {
        canonical_json(attempt["after"])
        for attempt in semantic["attempts"]
        if attempt["status"] == "applicable"
    }
    expected_states = {
        canonical_json(wire(state_from(state, aliases)))
        for state in scenario["variants"][0]["expected_search"]["required_reachable"]
    }
    assert actual_states == expected_states
    assert semantic["status"] == "success"
    # Independent Ledger E (#207): direct=5, inherited=2.
    assert semantic["min_effort"]["minimum_effort_value"] == 2
    assert semantic["min_effort"]["best_candidate_id"] == "generated_0003"
    rated = semantic["ranking_result"]["eligible_candidates"]
    assert rated["generated_0001"]["effort"] == rated["generated_0002"]["effort"] == 5
    assert rated["generated_0003"]["effort"] == 2
    assert semantic["engine_reported_guarantees"] == {
        "optimization_scope": "exhaustive_within_scope",
        "is_minimum_proven_over_scope": True,
        "is_no_path_proven_over_scope": False,
    }
    assert first["semantic"] == second["semantic"]
    assert first["reproducibility"] == second["reproducibility"]
    assert first["runtime"]["started_at"] != second["runtime"]["started_at"]
    assert first["runtime"]["duration_seconds"] > 0
    schema = read(ROOT / "docs/research/week4-query-result.schema.json")
    assert first["schema_version"] == schema["properties"]["schema_version"]["const"]
    acceptance_schema = schema["properties"]["acceptance"]
    assert set(acceptance_schema["required"]) == set(first["acceptance"])
    assert first["acceptance"]["status"] == acceptance_schema["properties"]["status"]["const"]
    assert first["acceptance"]["resolved_dependencies"] == {
        "https://github.com/nairyuuu/ad-weighted-graph/pull/232": "merged"
    }
    assert first["acceptance"]["pending_acceptance"] == [
        "#213 human review and CLI acceptance",
        "#208 independent exact-revision reproduction",
        "Actual private/SEAMLESS query reproduction",
    ]
    assert all(
        step["result"]["after"] for p in semantic["candidates"] for step in p["transition_history"]
    )
    assert any(
        step["result"]["assumption_backed_facts"]
        for p in semantic["candidates"]
        for step in p["transition_history"]
    )
    one, two = tmp_path / "one.json", tmp_path / "two.json"
    one.write_text(json.dumps(first), encoding="utf-8")
    two.write_text(json.dumps(second), encoding="utf-8")
    compare = subprocess.run(
        [sys.executable, "-m", "scripts.research.compare_query_runs", str(one), str(two)],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert compare.returncode == 0
    assert json.loads(compare.stdout)["equal"]
    second["semantic"]["candidates"].reverse()
    two.write_text(json.dumps(second), encoding="utf-8")
    tampered = subprocess.run(
        [sys.executable, "-m", "scripts.research.compare_query_runs", str(one), str(two)],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert tampered.returncode == 2
    assert "semantic digest mismatch" in tampered.stdout
    second["semantic"] = first["semantic"]
    second["schema_version"] = "week4-query-result/0.1.0"
    two.write_text(json.dumps(second), encoding="utf-8")
    legacy = subprocess.run(
        [sys.executable, "-m", "scripts.research.compare_query_runs", str(one), str(two)],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert legacy.returncode == 2
    assert "unsupported schema_version" in legacy.stdout


@pytest.mark.parametrize("output_mode", [False, True], ids=["stdout", "file"])
@pytest.mark.parametrize("nested", [None, [], "invalid", 0, 1, False, True, {}])
def test_ranking_wrapper_invalid_query_fails_without_output(tmp_path, query, output_mode, nested):
    ranking = tmp_path / "ranking.json"
    ranking.write_text(json.dumps({"query": nested}), encoding="utf-8")
    output = tmp_path / "never-created.json"
    options = ["--ranking-query", ranking]
    if output_mode:
        options += ["--output", output]
    assert not output.exists()
    error = run_cli(tmp_path, query, *options, success=False)
    assert error.returncode == 1
    assert "Invalid input/run" in error.stderr
    if nested != {}:
        assert "wrapper 'query' must be a JSON object" in error.stderr
    else:
        # Empty objects reach the authoritative decoder rather than disabling ranking.
        assert (
            "canonical_graph snapshot_id does not match PathRankingQuery snapshot_id"
            in error.stderr
        )
    assert not output.exists()


@pytest.mark.parametrize("output_mode", [False, True], ids=["stdout", "file"])
@pytest.mark.parametrize("input_kind", ["wrapped", "unwrapped", "omitted"])
def test_ranking_file_shapes_and_optional_scoring(tmp_path, query, output_mode, input_kind):
    options = []
    ranking = read(RATINGS)
    if input_kind != "omitted":
        path = tmp_path / "ranking.json"
        payload = ranking if input_kind == "wrapped" else ranking["query"]
        path.write_text(json.dumps(payload), encoding="utf-8")
        options = ["--ranking-query", path]
    if output_mode:
        output = tmp_path / "result.json"
        assert not output.exists()
        options += ["--output", output]
    semantic = run_cli(tmp_path, query, *options)["semantic"]
    assert semantic["status"] == "success"
    assert semantic["final_goal_reached"] and len(semantic["candidates"]) == 3
    if input_kind == "omitted":
        assert semantic["ranking_result"] is None
        assert semantic["min_effort"] is None
        assert semantic["ranking_disposition"] == "unrated"
    else:
        assert semantic["query"]["ranking_query"] == ranking["query"]
        assert semantic["ranking_disposition"] == "evaluated"
        assert semantic["min_effort"]["minimum_effort_value"] == 2
        assert semantic["min_effort"]["best_candidate_id"] == "generated_0003"


def test_initial_state_and_auth_context_overrides(tmp_path, query):
    state = tmp_path / "state.json"
    state.write_text(
        json.dumps({"control": ["OtherHost"], "usable_identity": [["Alice", "Host"]]}),
        encoding="utf-8",
    )
    good = run_cli(
        tmp_path, query, "--source", "OtherHost", "--initial-state", state, "--context", "Host"
    )["semantic"]
    bad = run_cli(
        tmp_path, query, "--source", "OtherHost", "--initial-state", state, "--context", "OtherHost"
    )["semantic"]
    assert good["status"] == "success" and len(good["candidates"]) == 3
    assert bad["status"] == "blocked" and bad["candidates"] == []
    state.write_text(json.dumps({"control": ["OtherHost"]}), encoding="utf-8")
    host_only = run_cli(
        tmp_path, query, "--actor", "OtherHost", "--source", "OtherHost", "--initial-state", state
    )["semantic"]
    assert host_only["candidates"] == []


@pytest.mark.parametrize("input_kind", ["initial_state", "initial_capabilities", "override"])
def test_explicit_empty_state_is_rejected_without_output(tmp_path, query, input_kind):
    query.pop("initial_state", None)
    options = []
    if input_kind == "override":
        state = tmp_path / "state.json"
        state.write_text("{}", encoding="utf-8")
        options = ["--initial-state", state]
    else:
        query[input_kind] = {}
    error = run_cli(tmp_path, query, *options, success=False)
    assert error.returncode == 1
    assert "explicitly empty" in error.stderr
    assert '"control": []' in error.stderr


def test_omitted_default_and_explicit_empty_capabilities_have_distinct_reachability(
    tmp_path, query
):
    query.pop("initial_state")
    default = run_cli(tmp_path, query)["semantic"]
    query["initial_state"] = {"control": ["Alice"]}
    explicit = run_cli(tmp_path, query)["semantic"]
    assert (
        default["materialized"]["initial_attack_state"]
        == explicit["materialized"]["initial_attack_state"]
    )
    assert default["candidates"] == explicit["candidates"]
    assert default["final_goal_reached"] and len(default["candidates"]) == 3
    state = tmp_path / "empty-capabilities.json"
    state.write_text('{"control": []}', encoding="utf-8")
    empty = run_cli(tmp_path, query, "--initial-state", state)["semantic"]
    assert all(value == [] for value in empty["materialized"]["initial_attack_state"].values())
    assert not empty["final_goal_reached"]
    assert empty["candidates"] == []
    assert empty["ranking_disposition"] == "unrated"


def test_unknown_false_assumption_veto_checkpoint_and_asset(tmp_path, query):
    query["checkpoint_goal"] = {
        "target": "Admins",
        "required_state": {"effective_member": [["Alice", "Admins"]]},
    }
    original = query["runtime_facts"].pop(0)
    missing = run_cli(tmp_path, query)["semantic"]
    assert missing["checkpoint_reached"] and not missing["final_goal_reached"]
    assert any(a["status"] == "indeterminate" for a in missing["attempts"])
    query["assumptions"] = [original]
    assumed = run_cli(tmp_path, query)["semantic"]
    assert assumed["final_goal_reached"]
    assert assumed["ranking_disposition"] == "unrated"
    query["runtime_facts"].append({**original, "origin": "blocked_evidence", "value": False})
    blocked = run_cli(tmp_path, query)["semantic"]
    assert blocked["checkpoint_reached"] and not blocked["final_goal_reached"]
    assert blocked["status"] == "checkpoint_reached_final_goal_blocked"
    rejected = blocked["materialized"]["rejected_assumptions"]
    assert rejected[0]["reason"] == "known_false_veto"
    assert rejected[0]["conflicting_fact"]["value"] is False
    # Accepted #225: direct asset success does not require the checkpoint.
    query["runtime_facts"] = read(QUERY)["runtime_facts"]
    query["assumptions"] = []
    query["allowed_techniques"] = ["obtain_admin_execution_on_host"]
    direct = run_cli(tmp_path, query)["semantic"]
    assert direct["final_goal_reached"] and not direct["checkpoint_reached"]


def test_effort_binding_without_likelihood_or_impact_basis(tmp_path, query):
    ranking = read(RATINGS)["query"]
    ranking["conditional_bounds_table"] = []
    for record in ranking["target_impact_assessments"].values():
        record.update(
            rating_status="unrated",
            consequence_rating=None,
            missing_basis_reasons=["Synthetic counterfactual: no impact basis"],
        )
    query["ranking_query"] = ranking
    semantic = run_cli(tmp_path, query)["semantic"]
    result = semantic["ranking_result"]
    assert semantic["final_goal_reached"]
    assert result["pareto_frontier"] == []
    for record in result["diagnostics"].values():
        assessment = record["assessment"]
        assert assessment["effort_status"] == "rated"
        assert assessment["likelihood_status"] == "unrated"
        assert assessment["impact_status"] == "unrated"
        assert assessment["likelihood_interval"] is None
        assert assessment["impact"] is None
    assert semantic["min_effort"]["minimum_effort_value"] == 2
    assert semantic["query"]["ranking_query"]["work_units_ledger"] == ranking["work_units_ledger"]


def test_missing_bindings_and_adapter_exclusions_remain_auditable(tmp_path, query):
    query["ranking_query"] = read(RATINGS)["query"]
    query["action_bindings"] = []
    unbound = run_cli(tmp_path, query)["semantic"]
    assert unbound["final_goal_reached"]
    assert len(unbound["binding_diagnostics"]) == len(unbound["candidates"]) == 3
    assert all(
        d["reason"] == "explicit_action_binding_missing"
        for d in unbound["binding_diagnostics"].values()
    )
    assert unbound["ranking_result"] is None
    assert unbound["complete"] and not unbound["truncated"]
    assert unbound["engine_reported_guarantees"]["optimization_scope"] == "no_bound_candidates"
    assert not unbound["engine_reported_guarantees"]["is_minimum_proven_over_scope"]
    query["action_bindings"] = read(QUERY)["action_bindings"]
    # Missing an entire impact record fails the canonical envelope validator.
    query["ranking_query"]["target_impact_assessments"] = {}
    excluded = run_cli(tmp_path, query)
    ranked = excluded["semantic"]["ranking_result"]
    assert excluded["semantic"]["final_goal_reached"]
    assert len(ranked["diagnostics"]) == 3
    assert all(
        "canonical_candidate_invalid" in d["reasons"] for d in ranked["diagnostics"].values()
    )
    assert ranked["eligible_candidates"] == {}
    excluded_semantic = excluded["semantic"]
    assert len(excluded_semantic["binding_diagnostics"]) == 3
    assert ranked["search_audit"]["candidates_adapted"] == 0
    assert ranked["search_audit"]["candidates_rejected_by_adapter"] == 3
    assert excluded_semantic["complete"] and not excluded_semantic["truncated"]
    assert (
        excluded_semantic["engine_reported_guarantees"]["optimization_scope"]
        == "no_bound_candidates"
    )
    assert not excluded_semantic["engine_reported_guarantees"]["is_minimum_proven_over_scope"]
    query["ranking_query"] = read(RATINGS)["query"]
    # Contradictory edge/action binding is rejected earlier by the adapter.
    query["action_bindings"][0][1] = "action_inherited_admin"
    rejected = run_cli(tmp_path, query)["semantic"]["ranking_result"]["diagnostics"]
    assert any("adapter_ineligible" in d["reasons"] for d in rejected.values())


@pytest.mark.parametrize("exclusion", ["adapter", "validator"])
def test_lowest_effort_exclusion_downgrades_ranking_scope(tmp_path, query, exclusion):
    query["ranking_query"] = read(RATINGS)["query"]
    if exclusion == "adapter":
        query["action_bindings"][2][1] = "unknown_inherited_action"
        reason = "adapter_ineligible"
    else:
        # Valid query metadata but no impact record for the candidate's target.
        query["ranking_query"]["target_impact_assessments"] = {}
        reason = "canonical_candidate_invalid"
    semantic = run_cli(tmp_path, query)["semantic"]
    assert len(semantic["candidates"]) == 3
    assert semantic["complete"] and not semantic["truncated"]
    assert semantic["final_goal_reached"]
    assert reason in semantic["binding_diagnostics"]["generated_0003"]["reasons"]
    result = semantic["ranking_result"]
    assert reason in result["diagnostics"]["generated_0003"]["reasons"]
    audit = result["search_audit"]
    assert audit["generated_paths"] == audit["generated_candidates_bound"] == 3
    assert audit["coverage"]["completeness_scope"] == "budget_bounded"
    assert not audit["coverage"]["is_truncated"]
    if exclusion == "adapter":
        assert audit["candidates_adapted"] == 2
        assert audit["candidates_rejected_by_adapter"] == audit["candidates_unbound"] == 1
        assert semantic["min_effort"]["minimum_effort_value"] == 5
        scope = "best_in_bound_subset"
    else:
        assert audit["candidates_adapted"] == 0
        assert audit["candidates_rejected_by_adapter"] == audit["candidates_unbound"] == 3
        assert semantic["min_effort"]["minimum_effort_value"] is None
        scope = "no_bound_candidates"
    assert semantic["engine_reported_guarantees"] == {
        "optimization_scope": scope,
        "is_minimum_proven_over_scope": False,
        "is_no_path_proven_over_scope": False,
    }


@pytest.mark.parametrize("missing_basis", [False, True])
def test_zero_action_other_target_never_manufactures_pareto_basis(tmp_path, query, missing_basis):
    query["initial_state"]["admin_control"] = ["Host"]
    query["ranking_query"] = read(RATINGS)["query"]
    if missing_basis:
        query["ranking_query"]["conditional_bounds_table"] = []
        for impact in query["ranking_query"]["target_impact_assessments"].values():
            impact.update(
                rating_status="unrated",
                consequence_rating=None,
                missing_basis_reasons=["No reviewed zero-work impact basis"],
            )
    package = run_cli(tmp_path, query)
    semantic = package["semantic"]
    assert semantic["materialized"]["initial_actor"] != semantic["materialized"]["target"]
    assert semantic["final_goal_reached"]
    assert semantic["candidates"][0]["transition_history"] == []
    ranking = semantic["ranking_result"]
    assert ranking is not None
    assert ranking["pareto_frontier"] == []
    assert ranking["eligible_candidates"] == {}
    assert ranking["search_metadata"]["candidates_evaluated"] == 0
    assert ranking["min_effort_to_da_baseline"]["minimum_effort_value"] is None
    assert ranking["parameter_audit"]
    assert semantic["min_effort"] == ranking["zero_work_disposition"]
    zero = semantic["min_effort"]
    assert zero["disposition"] == "semantic_initial_goal_zero_work"
    assert zero["ranking_status"] == "not_applicable"
    assert zero["minimum_effort_value"] == 0.0
    assert zero["associated_likelihood_interval"] is None
    assert zero["associated_impact"] is None
    assert semantic["binding_diagnostics"] == {}
    assert semantic["engine_reported_guarantees"]["optimization_scope"] == "exhaustive_within_scope"
    assert semantic["engine_reported_guarantees"]["is_minimum_proven_over_scope"]


@pytest.mark.parametrize(
    "cap, reason",
    [
        ("max-paths", "path_limit_reached"),
        ("max-steps", "step_limit_reached"),
        ("max-expansions", "expansion_limit_reached"),
    ],
)
def test_caps_never_claim_proof(tmp_path, query, cap, reason):
    semantic = run_cli(tmp_path, query, "--ranking-query", RATINGS, f"--{cap}", 1)["semantic"]
    assert semantic["truncated"] and not semantic["complete"]
    assert semantic["truncation_reason"] == reason
    proof = semantic["engine_reported_guarantees"]
    assert not proof["is_minimum_proven_over_scope"]
    assert not proof["is_no_path_proven_over_scope"]
    assert proof["optimization_scope"] in ("best_in_generated_subset", "truncated_incomplete")
    if semantic["ranking_result"] is not None:
        ranking = semantic["ranking_result"]
        assert ranking["search_audit"]["coverage"]["completeness_scope"] == "partial_truncated"
        assert ranking["search_metadata"]["is_truncated"]


@pytest.mark.parametrize("search_mode", ["actions", "zero_action", "no_path"])
@pytest.mark.parametrize("invalid", ["snapshot", "metadata", "empty", "non_mapping"])
def test_authoritative_ranking_validation_with_and_without_actions(
    tmp_path, query, search_mode, invalid
):
    ranking = read(RATINGS)["query"]
    if invalid == "snapshot":
        ranking["query_metadata"]["snapshot_id"] = "sha256:" + "0" * 64
    elif invalid == "metadata":
        del ranking["query_metadata"]["query_id"]
    elif invalid == "empty":
        ranking = {}
    else:
        ranking = []
    if search_mode == "zero_action":
        query["initial_state"]["admin_control"] = ["Host"]
    elif search_mode == "no_path":
        query["initial_state"] = {"control": []}
    query["ranking_query"] = ranking
    error = run_cli(tmp_path, query, success=False)
    assert error.returncode == 1
    assert "Invalid input/run" in error.stderr


@pytest.mark.parametrize("field", ["initial_state", "budget"])
def test_invalid_json_object_shapes_fail_closed(tmp_path, query, field):
    query[field] = []
    assert "Invalid input/run" in run_cli(tmp_path, query, success=False).stderr


def test_invalid_query_and_private_prerequisite(tmp_path, query):
    invalid = copy.deepcopy(query)
    invalid["target_goal"]["required_state"] = {}
    assert "required_state" in run_cli(tmp_path, invalid, success=False).stderr
    assert (
        "Missing prerequisite"
        in run_cli(
            tmp_path,
            query,
            "--label",
            "seamless",
            "--prerequisite",
            tmp_path / "absent.json",
            success=False,
        ).stderr
    )
    assert (
        "explicit --prerequisite"
        in run_cli(
            tmp_path,
            query,
            "--label",
            "private",
            success=False,
        ).stderr
    )
    assert (
        "cannot be labeled"
        in run_cli(
            tmp_path,
            query,
            "--label",
            "seamless",
            "--prerequisite",
            QUERY,
            success=False,
        ).stderr
    )


def test_snapshot_envelope_binding_and_digest(tmp_path, query):
    from src.parser.serialization import deserialize_graph
    from src.parser.snapshot_facts import (
        FactEvidence,
        SnapshotFact,
        SnapshotFacts,
        graph_digest,
        serialize_snapshot,
    )

    graph = deserialize_graph(GRAPH.read_text(encoding="utf-8"))
    provenance = {
        "raw_file": "synthetic://query-cli/users.json",
        "collector": "synthetic/213",
        "timestamp": "2026-10-08T00:00:00Z",
        "attribute": "Properties.hasspn",
        "record_locator": "#/users/0",
        "snapshot_id": graph["metadata"]["snapshot_id"],
    }
    fact = SnapshotFact(
        query["aliases"]["Alice"], "has_spn", "known", True, (FactEvidence("true", provenance),)
    )
    facts = SnapshotFacts(graph["metadata"]["snapshot_id"], graph_digest(graph), (fact,))
    snapshot = tmp_path / "snapshot.json"
    snapshot.write_text(serialize_snapshot(graph, facts), encoding="utf-8")
    result = run_cli(tmp_path, query, "--snapshot", snapshot)
    assert result["semantic"]["snapshot_facts_present"]
    exported = result["semantic"]["snapshot_facts"]["facts"][0]
    assert exported["value"] is True
    assert exported["evidence"][0]["provenance"] == provenance
    assert result["reproducibility"]["inputs"]["graph_input"]["sha256"] == (
        "sha256:" + hashlib.sha256(snapshot.read_bytes()).hexdigest()
    )
    payload = read(snapshot)
    payload["graph_sha256"] = "sha256:" + "0" * 64
    snapshot.write_text(json.dumps(payload), encoding="utf-8")
    assert (
        "Invalid input/run"
        in run_cli(
            tmp_path,
            query,
            "--snapshot",
            snapshot,
            success=False,
        ).stderr
    )


def test_cli_omitted_and_null_graph_catalog_normalized_semantic_equality(tmp_path, query):
    """Normalize null graph/catalog as absent, matching omitted across whole semantic payload."""
    variants = {
        "omitted": copy.deepcopy(query),
        "null_graph": {**copy.deepcopy(query), "graph": None},
        "null_catalog": {**copy.deepcopy(query), "catalog": None},
        "both_null": {**copy.deepcopy(query), "graph": None, "catalog": None},
    }
    outputs = {}
    for name, q in variants.items():
        res = run_cli(tmp_path, q)
        assert res["semantic"]["status"] == "success"
        assert res["semantic"]["complete"] is True
        outputs[name] = res["semantic"]

    def normalize(payload):
        p = copy.deepcopy(payload)
        if "query" in p and isinstance(p["query"], dict):
            p["query"].pop("graph", None)
            p["query"].pop("catalog", None)
        return p

    base = normalize(outputs["omitted"])
    for name in ("null_graph", "null_catalog", "both_null"):
        other = normalize(outputs[name])
        assert other == base


@pytest.mark.parametrize(
    "payload_key,payload_value",
    [
        ("graph", {"nodes": [], "edges": []}),
        ("graph", {}),
        ("catalog", [{"id": "custom_technique"}]),
        ("catalog", []),
        ("candidates", [{"candidate_id": "c001"}]),
        ("candidates", []),
        ("candidates", None),
    ],
)
def test_cli_rejects_unsupported_embedded_payloads(tmp_path, query, payload_key, payload_value):
    """Retain rejection for actual unsupported embedded graph/catalog/candidates."""
    invalid = copy.deepcopy(query)
    invalid[payload_key] = payload_value
    proc = run_cli(tmp_path, invalid, success=False)
    assert "use explicit graph/snapshot; supplied candidates/catalog are unsupported" in proc.stderr


@pytest.mark.parametrize("to_file", [False, True])
def test_compact_output_preserves_entire_package(tmp_path, query, to_file):
    """Formatting never removes evidence, attempts, ratings or proof disclosures."""
    path = tmp_path / "result.json"
    options = ("--output", path) if to_file else ()
    pretty = run_cli(tmp_path, query, "--ranking-query", RATINGS, *options)
    pretty_bytes = path.stat().st_size if to_file else None
    compact = run_cli(tmp_path, query, "--ranking-query", RATINGS, "--compact-output", *options)
    assert pretty["semantic"]["attempts"]
    assert pretty["semantic"]["min_effort"]["minimum_effort_value"] == 2
    for package in (pretty, compact):
        package["runtime"].pop("started_at")
        package["runtime"].pop("duration_seconds")
    assert pretty == compact
    if to_file:
        assert path.stat().st_size < pretty_bytes
