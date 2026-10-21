"""Finite fact/action oracle: opaque session material is not a password.

The two-action oracle below uses no AWG generator, state or cost calculation.
There is deliberately no real credential collection or authentication here.
"""

import copy
from dataclasses import dataclass, replace

import pytest
from test_computer_foothold_boundary import OTHER_HOST, OTHER_USER
from test_engine import ACTOR, GROUP, HOST, TOY, _edge, _graph

from src.engine.query import run_attack_query
from src.engine.query_cli import execute, wire
from src.engine.semantics.credentials import replay_path


@dataclass(frozen=True)
class Case:
    name: str
    material: str = "password"
    owner: str = ACTOR
    context: str = HOST
    enabled: bool | None = True
    secret_valid: bool | None = True
    network: bool | None = True
    accepted: bool | None = True
    membership: bool | None = True
    admin: bool = True
    fresh: bool | None = True
    present: bool | None = True
    accessible: bool | None = True
    foreign_fact_context: bool = False
    observed_veto: bool = False
    initial_usable: bool = False


CASES = (
    Case("typed_password"),
    Case("opaque_session_material", material="opaque"),
    Case("session_opportunity_only", material="session"),
    Case("session_with_password_claim", material="session_password_claim"),
    Case("session_without_admin", material="session", admin=False),
    Case("session_stale", material="session", fresh=False),
    Case("session_freshness_unknown", material="session", fresh=None),
    Case("session_absent", material="session", present=False),
    Case("session_presence_unknown", material="session", present=None),
    Case("session_protected", material="session", accessible=False),
    Case("session_access_unknown", material="session", accessible=None),
    Case("password_wrong_owner", owner=OTHER_USER),
    Case("password_wrong_context", context=OTHER_HOST),
    Case("password_disabled_owner", enabled=False),
    Case("password_enabled_unknown", enabled=None),
    Case("password_invalid", secret_valid=False),
    Case("password_validity_unknown", secret_valid=None),
    Case("password_network_false", network=False),
    Case("password_network_unknown", network=None),
    Case("password_authentication_false", accepted=False),
    Case("password_authentication_unknown", accepted=None),
    Case("password_membership_false", membership=False),
    Case("password_membership_unknown", membership=None),
    Case("password_foreign_fact_context", foreign_fact_context=True),
    Case("observed_false_veto", observed_veto=True),
    Case("opaque_with_usable_identity", material="opaque", initial_usable=True),
)


def oracle(case):
    """Two AND-actions; Unknown closure is separate from definite closure.

    Opaque material has no activation rule in this bounded model. This is a
    model-coverage limitation, not evidence that AD authentication is impossible.
    An untyped runtime password claim does not change the artifact's type.
    """
    session = case.material.startswith("session")
    session_gates = (case.admin, case.fresh, case.present, case.accessible)
    material_possible = not any(v is False for v in session_gates)
    material_definite = all(v is True for v in session_gates)
    if not case.initial_usable and (case.material == "opaque" or (session and material_definite)):
        return "unsupported"
    facts = {
        "password": case.material == "password" and case.owner == ACTOR and case.context == HOST,
        "enabled": case.enabled,
        "secret_valid": False if case.observed_veto else case.secret_valid,
        "network": case.network,
        "accepted": None if case.foreign_fact_context else case.accepted,
        "membership": case.membership,
        "usable": case.initial_usable,
    }
    actions = (
        ({"password", "enabled", "secret_valid", "network", "accepted"}, "usable"),
        ({"usable", "enabled", "membership"}, "goal"),
    )

    def closure(possible):
        known = {k for k, v in facts.items() if v is True or (possible and v is None)}
        while True:
            extended = known | {effect for needs, effect in actions if needs <= known}
            if extended == known:
                return "goal" in known
            known = extended

    return (
        "success"
        if closure(False)
        else "indeterminate"
        if closure(True) or (session and material_possible and not material_definite)
        else "negative_within_model"
    )


def scenario(case):
    extra = copy.deepcopy(next(n for n in TOY["nodes"] if n["id"] == ACTOR))
    extra.update(id=OTHER_USER, label="Synthetic unrelated User", enabled=True)
    host = copy.deepcopy(next(n for n in TOY["nodes"] if n["id"] == HOST))
    host.update(id=OTHER_HOST, label="Synthetic foreign context", enabled=True)
    graph = _graph(
        [_edge(HOST, ACTOR, "HasSession"), _edge(ACTOR, GROUP, "MemberOf")],
        extra_nodes=[extra, host],
    )
    canonical = graph.to_canonical()
    owner = next(n for n in canonical["nodes"] if n["id"] == ACTOR)
    if case.enabled is None:
        owner.pop("enabled", None)
    else:
        owner["enabled"] = case.enabled
    graph = type(graph).from_canonical(canonical)
    initial = {"control": [HOST], "admin_control": [HOST] if case.admin else []}
    if case.material == "password":
        initial["recovered_secret"] = [
            {
                "owner": case.owner,
                "context": case.context,
                "form": "password",
                "provenance": ["synthetic://session-boundary/typed-password/" + case.name],
            }
        ]
    elif case.material == "opaque":
        initial["credential_material"] = [ACTOR]
    if case.initial_usable:
        initial["usable_identity"] = [[ACTOR, HOST]]
    gates = [
        ("secret_valid", case.owner, HOST, case.secret_valid),
        ("network_kdc_reachable", case.owner, HOST, case.network),
        ("authentication_accepted", case.owner, HOST, case.accepted),
        ("security_group", ACTOR, GROUP, True),
        ("membership_usable", ACTOR, GROUP, case.membership),
    ]
    if case.material.startswith("session"):
        gates += [
            (p, HOST, ACTOR, v)
            for p, v in (
                ("session_fresh", case.fresh),
                ("session_present", case.present),
                ("credential_accessible", case.accessible),
            )
        ]
    facts = [
        {
            "predicate": p,
            "subject": s,
            "target": t,
            "value": v,
            "scope": "session-boundary-oracle",
            "rationale": "Synthetic finite gate",
            "provenance_reference": "synthetic://session-boundary/" + case.name,
        }
        for p, s, t, v in gates
        if v is not None
    ]
    if case.foreign_fact_context:
        next(f for f in facts if f["predicate"] == "authentication_accepted")[
            "assumption_metadata"
        ] = {"authentication_context": OTHER_HOST}
    if case.material == "session_password_claim":
        next(f for f in facts if f["predicate"] == "credential_accessible")[
            "assumption_metadata"
        ] = {"credential_form": "password", "owner": ACTOR, "authentication_context": HOST}
    query = {
        "source_foothold": HOST,
        "initial_actor": HOST,
        "initial_state": initial,
        "authentication_context": HOST,
        "target": GROUP,
        "target_goal": {"kind": "usable_identity_entitlement", "target": GROUP},
        "allowed_techniques": ["activate_recovered_identity", "propagate_group_entitlement"]
        + (["recover_session_credential_material"] if case.material.startswith("session") else []),
        "assumptions": facts,
        "budget": {"max_paths": 10, "max_steps": 4, "max_expansions": 100},
        "scenario_reference": "session-boundary-oracle/" + case.name,
    }
    if case.observed_veto:
        query["runtime_facts"] = [
            {
                "predicate": "secret_valid",
                "subject": ACTOR,
                "target": HOST,
                "value": False,
                "provenance_reference": "synthetic://observed-denial",
            }
        ]
    return graph, query


def classify(result):
    if result.final_goal_reached:
        return "success"
    if "indeterminate" in result.status:
        return "indeterminate"
    if result.status == "unsupported":
        return "unsupported"
    return "negative_within_model"


@pytest.mark.parametrize("case", CASES, ids=lambda c: c.name)
def test_independent_session_boundary(case):
    graph, query = scenario(case)
    original = copy.deepcopy(query)
    result = run_attack_query(query, graph)
    assert classify(result) == oracle(case)
    assert result.complete and not result.truncated
    assert query == original
    for path in result.paths:
        assert replay_path(path, graph) == path.final_state
        assert path.transition_history[-1].result.request.actor == ACTOR
        assert not path.final_state.control - {HOST}
        assert not path.final_state.reset_password_control
    if oracle(case) in {"unsupported", "indeterminate"}:
        assert not result.is_no_path_proven_over_scope
    if oracle(case) == "success" and not case.initial_usable:
        assert [s.result.request.technique_id for s in result.paths[0].transition_history] == [
            "activate_recovered_identity",
            "propagate_group_entitlement",
        ]
        assert result.paths[0].transition_history[0].result.request.actor == ACTOR


@pytest.mark.parametrize(
    "name", ["typed_password", "session_opportunity_only", "opaque_session_material"]
)
def test_public_session_boundary(name):
    case = next(c for c in CASES if c.name == name)
    graph, query = scenario(case)
    result = execute(wire(query), graph)
    assert result["status"] == ("unsupported" if oracle(case) == "unsupported" else "success")


def test_untyped_material_goal_itself_is_supported():
    graph, query = scenario(next(c for c in CASES if c.name == "session_opportunity_only"))
    query.update(
        target=ACTOR,
        target_goal={"target": ACTOR, "required_state": {"credential_material": [ACTOR]}},
    )
    result = run_attack_query(query, graph)
    assert result.final_goal_reached and result.status == "success"
    assert not result.semantic_coverage_gaps


def test_truncation_and_unknown_keep_priority_over_coverage_gap():
    case = replace(CASES[0], name="opaque_plus_unknown", material="opaque", network=None)
    graph, query = scenario(case)
    query["initial_state"]["recovered_secret"] = scenario(CASES[0])[1]["initial_state"][
        "recovered_secret"
    ]
    # Another reachable opaque owner still exposes a gap; activation Unknown is
    # the primary status, rather than a completed unsupported/no-path claim.
    query["initial_state"]["credential_material"] = [OTHER_USER]
    result = run_attack_query(query, graph)
    assert result.status == "indeterminate" and result.semantic_coverage_gaps
    query["budget"]["max_expansions"] = 1
    query["initial_state"]["admin_control"] = [HOST]
    query["allowed_techniques"].append("recover_session_credential_material")
    result = run_attack_query(query, graph)
    assert result.truncated and result.status == "truncated"
    assert result.semantic_coverage_gaps and not result.is_no_path_proven_over_scope


@pytest.mark.parametrize("form", ["nt_hash", "opaque", "kerberos_service_ticket", "kerberos_asrep"])
def test_another_material_form_cannot_masquerade_as_a_password(form):
    graph, query = scenario(CASES[0])
    query["initial_state"]["recovered_secret"][0]["form"] = form
    with pytest.raises(ValueError):
        run_attack_query(query, graph)


def test_exact_owner_context_and_explicit_goal_relevance_of_coverage_check():
    graph, query = scenario(CASES[0])
    query["initial_state"]["credential_material"] = [ACTOR]
    result = run_attack_query(query, graph)
    assert result.final_goal_reached and not result.semantic_coverage_gaps
    query["initial_state"]["recovered_secret"][0]["context"] = OTHER_HOST
    result = run_attack_query(query, graph)
    assert result.status == "unsupported"
    assert result.semantic_coverage_gaps[0]["owner"] == ACTOR
    query["target"] = HOST
    query["target_goal"] = {
        "target": HOST,
        "required_state": {"usable_identity": [[OTHER_USER, HOST]]},
    }
    result = run_attack_query(query, graph)
    assert not result.semantic_coverage_gaps


def batch_request():
    from test_machine_identity_profile import DOMAIN

    from scripts.exposure import build_request, inventory_exposure

    graph, public = scenario(next(c for c in CASES if c.name == "session_opportunity_only"))
    canonical = graph.to_canonical()
    canonical["nodes"].append(
        {
            "id": DOMAIN,
            "kind": "Domain",
            "domain": "EXAMPLE.TEST",
            "label": "Synthetic domain",
            "is_boundary": False,
        }
    )
    graph = type(graph).from_canonical(canonical)
    request, _ = build_request(
        graph,
        inventory_exposure(graph, domain_sid=DOMAIN),
        source_ids=[HOST],
        authentication_context=HOST,
        computer_profile="computer_control_admin",
        evaluation_mode="scenario",
        assumptions=public["assumptions"],
        budget=public["budget"],
    )
    goal = next(
        t["goal_id"] for t in request["target_manifest"]["targets"] if t["target_node_id"] == GROUP
    )
    request["target_goal_ids"] = [goal]
    return graph, request, public["allowed_techniques"], goal


@pytest.mark.parametrize("worker", [False, True])
def test_unsupported_session_continuation_survives_discovery_worker_and_resume(tmp_path, worker):
    from jsonschema.exceptions import ValidationError

    from src.engine.batch import BatchExecutionBudget, run_source_goal_batch, validate_schema

    graph, request, techniques, goal = batch_request()
    checkpoint = tmp_path / "checkpoint.json"
    options = {
        "allowed_techniques": techniques,
        "checkpoint": checkpoint,
        "execution_budget": BatchExecutionBudget(per_query_seconds=10) if worker else None,
    }
    before = run_source_goal_batch(request, graph, **options)
    source = request["sources"][0]["source_id"]
    cell = before.source_goal_matrix[source][goal]
    assert cell.status == "unsupported_semantics" and not cell.final_goal_reached
    assert cell.min_effort is None and cell.likelihood_interval is None
    assert before.source_prioritization[0].disposition == "unsupported_semantics"
    assert before.source_prioritization[0].priority_class == "Unknown"
    assert any(
        d.get("code") == "UNTYPED_CREDENTIAL_ACTIVATION_UNSUPPORTED" for d in cell.diagnostics
    )
    trace = next(iter(before.reproducibility["inputs"]["public_queries"].values()))
    assert not trace["guarantees"]["is_no_path_proven_over_scope"]
    assert before.schema_version == "batch-query-result/1.1.0"
    validate_schema(before.to_dict(), "batch-query-result")
    legacy = before.to_dict()
    legacy["schema_version"] = "batch-query-result/1.0.0"
    with pytest.raises(ValidationError):
        validate_schema(legacy, "batch-query-result")
    after = run_source_goal_batch(request, graph, resume=True, **options)
    assert after.source_goal_matrix == before.source_goal_matrix
    assert after.reproducibility["runtime"]["reused_cells"] == 1
    assert after.schema_version == before.schema_version


def test_ending_session_does_not_prove_initial_material_unusable():
    from src.engine.remediation import prepare_baseline, request_for_baseline
    from src.engine.remediation_runner import run_remediation, verify_package

    graph, query = scenario(next(c for c in CASES if c.name == "session_opportunity_only"))
    query["initial_state"]["credential_material"] = [ACTOR]
    baseline = prepare_baseline(
        graph,
        [{"source_id": "local-host", "goal_id": "group", "query": query}],
        run_id="session-support-before",
    )
    edit = {
        "kind": "runtime_fact_replace",
        "edit_id": "end-session",
        "catalog_entry_id": "session-end",
        "key": {
            "predicate": "session_present",
            "subject": HOST,
            "target": ACTOR,
            "authentication_context": HOST,
            "binding_id": None,
        },
        "expected_before": True,
        "after": False,
        "declaration": "counterfactual_intervention",
        "evidence_refs": ["synthetic://session-boundary"],
        "rationale": "Ending a session must not erase material already in the initial state.",
    }
    request = request_for_baseline(baseline, [edit], request_id="session-support-after")
    package = run_remediation(request, graph, baseline)
    cell = package["report"]["cells"][0]
    assert cell["before"]["reachability"] == cell["after"]["reachability"] == "unsupported"
    assert not cell["disconnected"]
    assert package["report"]["summary"]["pairs_disconnected"]["numerator"] == 0
    assert package["report"]["summary"]["pairs_disconnected"]["percent"] is None
    assert verify_package(package, graph)["status"] == "verified"


def test_executable_batch_cli_preserves_unsupported_status(tmp_path):
    import json
    import subprocess
    import sys
    from pathlib import Path

    from src.engine.batch import validate_schema

    graph, request, techniques, goal = batch_request()
    graph_file, request_file, output = [
        tmp_path / n for n in ("graph.json", "request.json", "result.json")
    ]
    graph_file.write_text(json.dumps(graph.to_canonical()))
    request_file.write_text(json.dumps(request))
    command = [
        sys.executable,
        "-m",
        "src.engine.batch_cli",
        "--graph",
        str(graph_file),
        "--batch-request",
        str(request_file),
        "--label",
        "synthetic",
        "--discover",
        "--query-seconds",
        "10",
        "--output",
        str(output),
    ]
    for technique in techniques:
        command.extend(["--technique", technique])
    completed = subprocess.run(
        command, cwd=Path(__file__).resolve().parents[1], capture_output=True, text=True
    )
    assert completed.returncode == 0, completed.stderr
    data = json.loads(output.read_text())
    validate_schema(data, "batch-query-result")
    assert data["schema_version"] == "batch-query-result/1.1.0"
    source = request["sources"][0]["source_id"]
    assert data["source_goal_matrix"][source][goal]["status"] == "unsupported_semantics"
    assert data["source_prioritization"][0]["priority_class"] == "Unknown"
