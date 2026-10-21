"""Declared machine identity transport reuses the finite Computer oracle."""

import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest
from jsonschema.exceptions import ValidationError
from test_computer_foothold_boundary import CASES, TECHNIQUES, oracle
from test_computer_foothold_boundary import scenario as oracle_scenario
from test_engine import ACTOR, GROUP, HOST

from scripts.exposure import build_request, inventory_exposure
from scripts.research.source_goal_batch import BatchQueryRequest, create_foothold_profile
from src.engine.batch import BatchExecutionBudget, run_source_goal_batch, validate_schema
from src.engine.ranking.resolution_service import canonical_digest

ROOT = Path(__file__).resolve().parents[1]
DOMAIN = "S-1-5-21-1000-2000-3000"
PROVENANCE = "scenario://machine-identity/analyst-declaration"


def scenario(case):
    graph, query = oracle_scenario(case)
    canonical = graph.to_canonical()
    canonical["nodes"].append(
        {
            "id": DOMAIN,
            "kind": "Domain",
            "domain": "EXAMPLE.TEST",
            "label": "Synthetic explicit domain",
            "is_boundary": False,
        }
    )
    return type(graph).from_canonical(canonical), query


def profile(graph, **overrides):
    return create_foothold_profile(
        **{
            "profile_id": "machine-identity",
            "node_id": HOST,
            "node_kind": "Computer",
            "profile_type": "computer_usable_identity",
            "authentication_context": HOST,
            "provenance_reference": PROVENANCE,
            "graph": graph,
            **overrides,
        }
    )


def request(graph, public, **overrides):
    return build_request(
        graph,
        inventory_exposure(graph, domain_sid=DOMAIN),
        **{
            "source_ids": [HOST],
            "authentication_context": HOST,
            "computer_profile": "computer_usable_identity",
            "machine_identity_provenance": PROVENANCE,
            "evaluation_mode": "scenario",
            "assumptions": public["assumptions"],
            "budget": public["budget"],
            **overrides,
        },
    )[0]


def group_cell(result, req):
    gid = next(
        t["goal_id"] for t in req["target_manifest"]["targets"] if t["target_node_id"] == GROUP
    )
    sid = req["sources"][0]["source_id"]
    return result.source_goal_matrix[sid][gid], result.reproducibility["inputs"]["public_queries"][
        canonical_digest([sid, gid])
    ]


def test_machine_profile_grants_only_the_declared_network_identity():
    graph, _ = scenario(CASES[2])
    actual = profile(graph)
    assert actual.is_supported and actual.provenance_reference == PROVENANCE
    state = actual.initial_attack_state
    assert state.usable_identity == {(HOST, HOST)}
    assert state.known_identity == {HOST}
    assert all(
        not getattr(state, name)
        for name in state.__dataclass_fields__
        if name not in {"known_identity", "usable_identity"}
    )
    assert graph.node(HOST)["kind"] == "Computer"
    for version in ("foothold-profiles/1.0.0", "foothold-profiles/1.1.0"):
        payload = {"schema_version": version, "profiles": [actual.to_dict()]}
        if version.endswith("1.0.0"):
            with pytest.raises(ValidationError):
                validate_schema(payload, "foothold-profiles")
        else:
            validate_schema(payload, "foothold-profiles")


@pytest.mark.parametrize(
    "mutation,code",
    [
        ("missing_context", "MISSING_AUTHENTICATION_CONTEXT"),
        ("context_user", "INVALID_AUTHENTICATION_CONTEXT"),
        ("context_missing", "INVALID_AUTHENTICATION_CONTEXT"),
        ("kind_hint", "INVALID_AUTHENTICATION_CONTEXT"),
        ("missing_provenance", "MISSING_IDENTITY_PROVENANCE"),
        ("blank_provenance", "MISSING_IDENTITY_PROVENANCE"),
        ("no_graph", "PROFILE_GRAPH_REQUIRED"),
        ("source_kind", "INVALID_MACHINE_IDENTITY"),
        ("boundary_source", "MACHINE_IDENTITY_SCOPE_UNSUPPORTED"),
        ("boundary_context", "MACHINE_IDENTITY_SCOPE_UNSUPPORTED"),
        ("foreign_domain", "MACHINE_IDENTITY_SCOPE_UNSUPPORTED"),
        ("unknown_domain", "MACHINE_IDENTITY_SCOPE_UNSUPPORTED"),
        ("disabled", "DISABLED_MACHINE_ACCOUNT"),
    ],
)
def test_invalid_declarations_never_grant_a_capability(mutation, code):
    graph, _ = scenario(CASES[2])
    data = graph.to_canonical()
    changes = {}
    if mutation in {"missing_context", "context_user", "context_missing"}:
        changes["authentication_context"] = {
            "missing_context": None,
            "context_user": ACTOR,
            "context_missing": "absent",
        }[mutation]
    elif mutation == "kind_hint":
        changes["authentication_context_kind"] = "User"
    elif mutation in {"missing_provenance", "blank_provenance"}:
        changes["provenance_reference"] = None if mutation == "missing_provenance" else " "
    elif mutation == "no_graph":
        data = None
    else:
        from test_computer_foothold_boundary import OTHER_HOST

        source = next(n for n in data["nodes"] if n["id"] == HOST)
        target = next(n for n in data["nodes"] if n["id"] == OTHER_HOST)
        if mutation == "source_kind":
            source["kind"] = "User"
        elif mutation == "boundary_source":
            source["is_boundary"] = True
        else:
            changes["authentication_context"] = OTHER_HOST
            if mutation == "boundary_context":
                target["is_boundary"] = True
            elif mutation == "foreign_domain":
                target["domain"] = "FOREIGN.TEST"
            elif mutation == "unknown_domain":
                target.pop("domain")
            elif mutation == "disabled":
                source["enabled"] = False
    actual = profile(data, **changes)
    assert not actual.is_supported and actual.error_code == code
    assert all(
        not getattr(actual.initial_attack_state, name)
        for name in actual.initial_attack_state.__dataclass_fields__
    )


@pytest.mark.parametrize("index", [2, 6, 7, 8])
@pytest.mark.parametrize("worker", [False, True])
def test_batch_and_worker_keep_oracle_outcomes_without_implicit_host_control(index, worker):
    case = CASES[index]
    graph, public = scenario(case)
    req = request(graph, public)
    assert req["schema_version"] == "batch-query-request/1.1.0"
    assert BatchQueryRequest.from_dict(req).to_dict() == req
    validate_schema(req, "batch-query-request")
    result = run_source_goal_batch(
        req,
        graph,
        allowed_techniques=TECHNIQUES,
        execution_budget=BatchExecutionBudget(per_query_seconds=10) if worker else None,
    )
    cell, trace = group_cell(result, req)
    assert cell.final_goal_reached == (oracle(case) == "success")
    assert trace["result"]["status"] == oracle(case)
    if oracle(case) == "indeterminate":
        assert not trace["guarantees"]["is_no_path_proven_over_scope"]
    state = trace["materialized"]["initial_attack_state"]
    assert state["usable_identity"] == [[HOST, HOST]]
    assert not state["control"] and not state["admin_control"] and not state["recovered_secret"]
    source = result.reproducibility["inputs"]["request"]["sources"][0]
    assert source["identity_provenance_reference"] == PROVENANCE
    assert req["sources"][0]["node_id"] == HOST
    if cell.final_goal_reached:
        assert cell.min_effort is None and cell.likelihood_interval is None
        assert [
            s["result"]["request"]["technique_id"]
            for s in trace["result"]["paths"][0]["transition_history"]
        ] == TECHNIQUES


def test_provenance_changes_refuse_resume_and_change_public_scenario_identity(tmp_path):
    graph, public = scenario(CASES[2])
    req = request(graph, public)
    checkpoint = tmp_path / "checkpoint.json"
    before = run_source_goal_batch(req, graph, allowed_techniques=TECHNIQUES, checkpoint=checkpoint)
    modified = copy.deepcopy(req)
    modified["sources"][0]["identity_provenance_reference"] = "scenario://another-declaration"
    with pytest.raises(ValueError, match="CHECKPOINT_SCOPE_MISMATCH"):
        run_source_goal_batch(
            modified, graph, allowed_techniques=TECHNIQUES, checkpoint=checkpoint, resume=True
        )
    after = run_source_goal_batch(modified, graph, allowed_techniques=TECHNIQUES)
    assert (
        group_cell(before, req)[1]["query"]["scenario_reference"]
        != group_cell(after, modified)[1]["query"]["scenario_reference"]
    )


def test_mixed_sources_do_not_pool_identity_or_host_rights():
    graph, public = scenario(CASES[2])
    req = request(graph, public)
    local = copy.deepcopy(req["sources"][0])
    local.update(source_id="independent-local-shell", profile_kind="computer_control_user")
    local.pop("identity_provenance_reference")
    req["sources"].append(local)
    result = run_source_goal_batch(req, graph, allowed_techniques=TECHNIQUES)
    local_only = {**req, "sources": [local]}
    assert not group_cell(
        run_source_goal_batch(local_only, graph, allowed_techniques=TECHNIQUES), local_only
    )[0].final_goal_reached
    assert all(
        not cell.final_goal_reached
        for cell in result.source_goal_matrix[local["source_id"]].values()
    )
    machine_only = {**req, "sources": req["sources"][:1]}
    assert group_cell(result, machine_only)[0].final_goal_reached


@pytest.mark.parametrize("enabled", [False, None])
def test_source_enabled_false_or_unknown_is_not_overwritten_by_identity_declaration(enabled):
    graph, public = scenario(CASES[2])
    # A direct batch declaration must face the same disabled-account veto even
    # when the caller bypasses discovery's earlier disabled-source exclusion.
    req = request(graph, public)
    canonical = graph.to_canonical()
    node = next(n for n in canonical["nodes"] if n["id"] == HOST)
    if enabled is None:
        node.pop("enabled")
    else:
        node["enabled"] = False
    graph = type(graph).from_canonical(canonical)
    if enabled is False:
        assert HOST not in {
            s["node_id"] for s in inventory_exposure(graph, domain_sid=DOMAIN)["sources"]
        }
    result = run_source_goal_batch(req, graph, allowed_techniques=TECHNIQUES)
    cell = group_cell(result, req)[0]
    assert not cell.final_goal_reached
    if enabled is False:
        assert cell.status == "unsupported_source" and cell.expansions == 0
        assert any(d.get("code") == "DISABLED_MACHINE_ACCOUNT" for d in cell.diagnostics)
    else:
        assert cell.status == "indeterminate"


@pytest.mark.parametrize(
    "mutation", ["legacy", "missing_reference", "blank_reference", "missing_context", "wrong_kind"]
)
def test_schema_rejects_invalid_new_wire_inputs(mutation):
    graph, public = scenario(CASES[2])
    req = request(graph, public)
    if mutation == "legacy":
        req["schema_version"] = "batch-query-request/1.0.0"
    elif mutation == "missing_reference":
        req["sources"][0].pop("identity_provenance_reference")
    elif mutation == "blank_reference":
        req["sources"][0]["identity_provenance_reference"] = " "
    elif mutation == "missing_context":
        req["sources"][0]["authentication_context"] = None
    else:
        req["sources"][0]["node_kind"] = "User"
    with pytest.raises(ValidationError):
        run_source_goal_batch(req, graph, allowed_techniques=TECHNIQUES)


def test_legacy_profile_remains_v1_and_no_new_identity_field_is_serialized():
    graph, public = scenario(CASES[2])
    req = request(
        graph, public, computer_profile="computer_control_user", machine_identity_provenance=None
    )
    assert req["schema_version"] == "batch-query-request/1.0.0"
    assert "identity_provenance_reference" not in req["sources"][0]
    assert not group_cell(run_source_goal_batch(req, graph, allowed_techniques=TECHNIQUES), req)[
        0
    ].final_goal_reached
    new = request(graph, public)
    new["schema_version"] = "batch-query-request/1.0.0"
    with pytest.raises(ValueError, match="require.*1.1.0"):
        BatchQueryRequest.from_dict(new)


def test_executable_discovery_creates_goals_and_records_identity_declaration(tmp_path):
    graph, public = scenario(CASES[2])
    canonical = tmp_path / "graph.json"
    canonical.write_text(json.dumps(graph.to_canonical()))
    assumptions = tmp_path / "assumptions.json"
    assumptions.write_text(json.dumps(public["assumptions"]))
    output = tmp_path / "exposure"
    command = [
        sys.executable,
        "-m",
        "scripts.exposure",
        "--graph",
        str(canonical),
        "--domain-sid",
        DOMAIN,
        "--source",
        HOST,
        "--authentication-context",
        HOST,
        "--computer-profile",
        "computer_usable_identity",
        "--machine-identity-provenance",
        PROVENANCE,
        "--evaluation-mode",
        "scenario",
        "--assumptions",
        str(assumptions),
        "--output-dir",
        str(output),
    ]
    for technique in TECHNIQUES:
        command.extend(["--technique", technique])
    subprocess.run(command, cwd=ROOT, capture_output=True, text=True, check=True)
    req = json.loads((output / "request.json").read_text())
    assert req["schema_version"] == "batch-query-request/1.1.0"
    result = json.loads((output / "result.json").read_text())
    assert result["summary"]["successful_cells"] >= 1
    assert "computer_usable_identity" in (output / "overview.md").read_text()
    assert req["sources"][0]["identity_provenance_reference"] == PROVENANCE
    assert GROUP in {t["target_node_id"] for t in req["target_manifest"]["targets"]}
    subprocess.run(command + ["--resume"], cwd=ROOT, capture_output=True, text=True, check=True)


@pytest.mark.parametrize(
    "kwargs", [{"machine_identity_provenance": None}, {"authentication_context": None}]
)
def test_discovery_requires_explicit_identity_context_and_provenance(kwargs):
    graph, public = scenario(CASES[2])
    with pytest.raises(ValueError, match="requires|require"):
        request(graph, public, **kwargs)
