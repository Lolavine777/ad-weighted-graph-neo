"""Finite conditional-history binding, without candidate injection or numeric adoption."""

import copy
from fractions import Fraction

import pytest

from scripts.research.final_cpi_profiles import (
    PACKAGE,
    bind_source_a,
    compile_histories,
    engineering_copy,
    read,
    validate_package,
)
from src.engine import run_attack_query
from src.engine.graph import EngineGraph


def test_taxonomy_covers_engine_and_recovery_remains_a_gap():
    assert validate_package() == {"active": 22, "likelihood_classes": 20, "passive": 1}
    profile = read(PACKAGE / "profile.json")
    assert profile["b_numeric_adoption"] is False
    recovery = [c for c in profile["classes"] if c["lower"] is None]
    assert {c["class_id"] for c in recovery} == {
        "asrep_password_recovery",
        "kerberoast_password_recovery",
    }


def test_histories_require_exact_lineage_and_fail_on_expansion_cap():
    actions = read(PACKAGE / "source-a-inventory.json")["actions"]
    histories = compile_histories(actions, max_records=5000)
    assert len(histories) > 46
    assert all(len({a["action_id"] for a in h}) == len(h) for h in histories)
    for history in histories:
        seen = set()
        for action in history:
            assert set(action["requires"]) <= seen
            seen.add(action["action_id"])
    with pytest.raises(ValueError, match="cap"):
        compile_histories(actions, max_records=1)


@pytest.mark.parametrize("after_activation", [False, True])
def test_profile_refuses_aliased_canonical_work_identity(after_activation):
    from scripts.research.final_cpi_profiles import HISTORICAL, bind_registry

    query = read(HISTORICAL / "source-a-query.json")
    actions = read(PACKAGE / "source-a-inventory.json")["actions"][:2]
    alias = copy.deepcopy(actions[0])
    alias["action_id"] = "aliased_reset"
    if after_activation:
        alias["requires"] = [actions[1]["action_id"]]
    else:
        actions = actions[:1]
    actions.append(alias)
    before = copy.deepcopy(query)
    with pytest.raises(ValueError, match="Repeated canonical work identity"):
        bind_registry(query, actions)
    assert query == before


def _source_a_first_goal_programs(max_steps):
    """Independent finite action ordering over the declared source-A inventory.

    The fixture has eight declared active actions and three membership steps.
    WinRM requires its actor's DA membership, and Josefa needs her admin-group
    membership before resetting Ollie. All other active dependencies come from
    the historical declarative inventory, never the native planner's output.
    """
    inventory = read(PACKAGE / "source-a-inventory.json")["actions"]
    requires = {a["action_id"]: set(a["requires"]) for a in inventory}
    names = {
        (a["technique_id"], a["actor"], a["source"], a["target"]): a["action_id"] for a in inventory
    }
    by_id = {a["action_id"]: a for a in inventory}
    for user in ("lidia", "josefa", "ollie"):
        actor = by_id[f"action_activate_{user}"]["actor"]
        group = (
            by_id["action_reset_ollie"]["source"]
            if user == "josefa"
            else by_id[f"action_winrm_badblood_{user}"]["source"]
        )
        member = f"member_{user}"
        names[("propagate_group_entitlement", actor, actor, group)] = member
        requires[member] = {f"action_activate_{user}"}
    requires["action_reset_ollie"].add("member_josefa")
    requires["action_winrm_badblood_lidia"].add("member_lidia")
    requires["action_winrm_badblood_ollie"].add("member_ollie")
    terminals = {a["action_id"] for a in inventory if a["terminal"]}
    programs = set()

    def visit(trace, completed):
        if trace and trace[-1] in terminals:
            programs.add(trace)
        elif len(trace) < max_steps:
            for action, prerequisites in requires.items():
                if action not in completed and prerequisites <= completed:
                    visit((*trace, action), completed | {action})

    visit((), set())
    return programs, names


def _source_a_traces(paths, names):
    return {
        tuple(
            names[(r.technique_id, r.actor, r.source, r.target)]
            for r in (step.result.request for step in path.transition_history)
        )
        for path in paths
    }


def test_native_generator_consumes_all_source_a_histories_only_on_synthetic_copy():
    query, canonical = bind_source_a("source-a-projection")
    graph = EngineGraph.from_canonical(canonical)
    before = copy.deepcopy(query)
    expected, names = _source_a_first_goal_programs(query["budget"]["max_steps"])
    assert len(expected) == 330
    pending = run_attack_query(query, graph)
    assert pending.search_result.complete
    assert len(pending.paths) == len(expected)
    assert _source_a_traces(pending.paths, names) == expected
    assert not pending.ranking_result["eligible_candidates"]
    test_query, test_graph = engineering_copy(query, graph)
    result = run_attack_query(test_query, test_graph)
    assert result.search_result.complete
    assert len(result.paths) == len(expected)
    assert _source_a_traces(result.paths, names) == expected
    assert len(result.ranking_result["eligible_candidates"]) == len(expected)
    first = result.ranking_result["eligible_candidates"]["generated_0001"]
    assert first["effort"] == 2
    assert tuple(map(Fraction, first["likelihood_interval"])) == (
        Fraction(9, 40),
        Fraction(8379, 10000),
    )
    assert first["impact"] == "High"
    assert query == before
    assert test_graph.metadata["synthetic"] is True
    test_query["rating_resolution"]["policy"] = "production"
    refused = run_attack_query(test_query, test_graph)
    assert not refused.ranking_result["eligible_candidates"]


def test_cli_normalization_streams_selected_fields_and_programs(tmp_path):
    import json

    from scripts.research.final_cpi_coverage import normalized_cli

    semantic = {
        "status": "success",
        "truncated": False,
        "truncation_reason": None,
        "complete": True,
        "expansions": 3,
        "caps": {},
        "final_goal_reached": True,
        "checkpoint_reached": False,
        "min_effort": {},
        "engine_reported_guarantees": {},
        "ranking_result": {"pareto_frontier": ["generated_0001"]},
        "rating_coverage": {},
        "candidates": [
            {
                "candidate_id": "generated_0001",
                "transition_history": [{"result": {"request": {"technique_id": "asrep_request"}}}],
            }
        ],
        "attempts": [{"large_private_payload": "unused" * 10000}],
    }
    path = tmp_path / "cli.json"
    path.write_text(
        json.dumps({"runtime": {"elapsed": 1}, "semantic": semantic}, indent=2, sort_keys=True)
        + "\n"
    )
    result = normalized_cli(path)
    assert result["programs"] == [["asrep_request"]]
    assert result["status"] == "success"
    assert result["ranking_result"] == semantic["ranking_result"]
    assert "attempts" not in result
    path.write_text("{}\n")
    with pytest.raises(ValueError, match="CLI"):
        normalized_cli(path)


@pytest.fixture(scope="module")
def raw_inputs():
    from scripts.research.final_cpi_profiles import ROOT
    from scripts.research.issue250_public_probe import frozen_inputs

    raw = ROOT / "data/raw/SEAMLESS"
    if not raw.is_dir():
        pytest.skip("Authorized manifest-verified raw required")
    return frozen_inputs(raw, "da21fbb545061c56c6dfff6ac489e7794a53ec73")


@pytest.mark.parametrize("case_id", ["kerberoast-material", "kerberoast-identity"])
def test_real_public_kerberoast_preserves_typed_goal_and_unrated_recovery(raw_inputs, case_id):
    from scripts.research.final_cpi_coverage import prepare_roasting

    graph, frozen, _ = raw_inputs
    case = next(q for q in read(PACKAGE / "cohort.json")["queries"] if q["id"] == case_id)
    query = prepare_roasting(case, graph, frozen)
    pending = run_attack_query(query, graph)
    assert len(pending.search_result.paths) == 1
    assert pending.final_goal_reached
    assert not pending.ranking_result["eligible_candidates"]
    test_query, derivative = engineering_copy(query, graph)
    result = run_attack_query(test_query, derivative)
    assert len(result.search_result.paths) == 1
    if case_id.endswith("material"):
        assessed = result.ranking_result["eligible_candidates"]["generated_0001"]
        assert assessed["effort"] == 1
        assert assessed["likelihood_interval"] == ["17/20", "49/50"]
        assert assessed["impact"] == "Low"
    else:
        assert not result.ranking_result["eligible_candidates"]
        from scripts.research.final_cpi_coverage import report_case

        path = result.paths[0]
        assert path.target == query["target"]
        assert path.nodes[-1] == query["authentication_context"]
        assert path.transition_history[-1].result.request.target == query["authentication_context"]
        assert len(path.nodes) == len(path.transition_history) + 1
        assert (
            query["target"],
            query["authentication_context"],
        ) in path.final_state.usable_identity
        assert report_case(result)["unreturned_goal_state_success_events"] == []
        assert len(query["rating_resolution"]["registries"]["likelihood"]["data"]) == 2


@pytest.mark.parametrize("control", ["false_authentication", "wrong_authentication_goal"])
def test_real_kerberoast_state_goal_refuses_failed_or_incompatible_activation(raw_inputs, control):
    from scripts.research.final_cpi_coverage import prepare_roasting

    graph, frozen, _ = raw_inputs
    case = next(
        q for q in read(PACKAGE / "cohort.json")["queries"] if q["id"] == "kerberoast-identity"
    )
    query = prepare_roasting(case, graph, frozen)
    if control == "false_authentication":
        for fact in query["runtime_facts"]:
            if fact["predicate"] == "authentication_accepted":
                fact.update(value=False, origin="blocked_evidence")
    else:
        other = next(
            n["id"]
            for n in graph.nodes(kind="Computer")
            if n["id"] != query["authentication_context"]
        )
        query["target_goal"]["required_state"] = {"usable_identity": [[query["target"], other]]}
    result = run_attack_query(query, graph)
    assert not result.paths
    assert not result.final_goal_reached


@pytest.mark.parametrize(
    "case_id",
    ["rbcd-unassumed", "rbcd-scoped", "acl-group-host", "acl-group-projection", "winrm-command"],
)
def test_supplementary_native_raw_profiles(raw_inputs, case_id):
    from scripts.research.final_cpi_coverage import counts, independent_checks
    from scripts.research.final_cpi_extension import extension_graph, prepare_extension
    from scripts.research.final_cpi_profiles import ROOT

    graph, _, _ = raw_inputs
    cohort = read(PACKAGE / "supplementary-cohort.json")
    case = next(q for q in cohort["queries"] if q["id"] == case_id)
    query, trace = prepare_extension(case, graph, ROOT / "data/raw/SEAMLESS")
    graph = extension_graph(case, graph, query)
    assert "ranking_query" not in query and "action_bindings" not in query
    original = copy.deepcopy(query)
    pending = run_attack_query(query, graph)
    assert not pending.ranking_result["eligible_candidates"]
    synthetic, derivative = engineering_copy(query, graph)
    result = run_attack_query(synthetic, derivative)
    assert len(result.paths) == len(pending.paths)
    assert query == original
    if case_id == "rbcd-unassumed":
        assert not result.paths and result.status == "indeterminate"
        return
    assert result.paths
    assert counts(result)["fully_rated"] == len(result.paths)
    assert independent_checks(result)["checked_eligible_candidates"] == len(result.paths)
    families = {
        step.result.request.technique_id
        for path in result.paths
        for step in path.transition_history
    }
    if case_id == "rbcd-scoped":
        assert len(result.paths) == 3
        assert families == set(query["allowed_techniques"])
        assert all(
            a["impact"] == "High" for a in result.ranking_result["eligible_candidates"].values()
        )
        assert trace["exact_reset_and_descriptor_edges"] is True
        assert "known reset" in query["rating_resolution"]["scope"]["target_population"]
    elif case_id.startswith("acl-group"):
        assert {
            "grant_new_object_right",
            "obtain_admin_execution_on_host",
        } <= families
        assert trace["selector_candidates"] == 8
        if case_id.endswith("projection"):
            assert {"genericall_add_member", "genericall_grant_write_dacl"} <= families
            assert len(graph.nodes()) == 4
    else:
        assert len(result.paths) == 1
        assert families == {"open_winrm_remote_session"}
        first = result.ranking_result["eligible_candidates"]["generated_0001"]
        assert first["effort"] == 1 and first["impact"] == "Medium"
        assert first["likelihood_interval"] == ["7/10", "19/20"]
        assert not result.paths[0].final_state.admin_control


def test_history_domain_accepts_either_declared_permission_lineage():
    actions = [
        {"action_id": "static_dacl", "requires": []},
        {"action_id": "static_generic", "requires": []},
        {
            "action_id": "derived_write",
            "requires": [],
            "requires_any": ["static_dacl", "static_generic"],
        },
    ]
    histories = compile_histories(actions, max_records=50)
    assert not any(h[0]["action_id"] == "derived_write" for h in histories)
    assert any([a["action_id"] for a in h] == ["static_dacl", "derived_write"] for h in histories)
    assert any(
        [a["action_id"] for a in h] == ["static_generic", "derived_write"] for h in histories
    )
    actions[-1]["requires_any"] = ["unlisted_root"]
    with pytest.raises(ValueError, match="lineage"):
        compile_histories(actions, max_records=50)


@pytest.mark.parametrize("field", ["horizon", "policy", "retry", "method", "lineage"])
def test_profile_refuses_changed_context_before_binding(field):
    from scripts.research.final_cpi_profiles import HISTORICAL, bind_registry

    query = read(HISTORICAL / "source-a-query.json")
    actions = read(PACKAGE / "source-a-inventory.json")["actions"]
    scope = query["rating_resolution"]["scope"]
    if field == "horizon":
        scope["horizon"] = "1s"
    elif field == "policy":
        scope["policy_id"] = "one-attempt-1-second"
    elif field == "retry":
        scope["retry_policy"] = {"max_attempts": 1, "deadline_seconds": 1}
    elif field == "method":
        actions[-1]["method"] = "RDP"
    else:
        actions[1]["requires"] = []
    with pytest.raises(ValueError, match="applicability"):
        bind_registry(query, actions)


@pytest.mark.parametrize(
    "field",
    [
        "status",
        "final_goal_reached",
        "truncated",
        "expansions",
        "caps",
        "engine_reported_guarantees",
    ],
)
def test_public_verifier_rejects_semantic_mismatch_with_equal_ranking(monkeypatch, tmp_path, field):
    import json
    from types import SimpleNamespace

    from scripts.research import final_cpi_coverage as probe

    query, canonical = bind_source_a("source-a-projection")
    graph = EngineGraph.from_canonical(canonical)
    m = probe.materialize_query(query, graph)
    semantic = {
        "status": "no_path",
        "truncated": False,
        "truncation_reason": None,
        "complete": True,
        "expansions": 0,
        "caps": query["budget"],
        "final_goal_reached": False,
        "checkpoint_reached": False,
        "min_effort": None,
        "ranking_result": {},
        "rating_coverage": {},
        "candidates": [],
        "engine_reported_guarantees": {
            "optimization_scope": None,
            "is_minimum_proven_over_scope": False,
            "is_no_path_proven_over_scope": False,
        },
    }
    cli = copy.deepcopy(semantic)
    cli[field] = (
        {"changed": True}
        if isinstance(cli[field], dict)
        else ("success" if field == "status" else (100 if field == "expansions" else True))
    )
    if field == "engine_reported_guarantees":
        cli[field] = {**semantic[field], "is_minimum_proven_over_scope": True}
    api = SimpleNamespace(
        **{
            k: v
            for k, v in semantic.items()
            if k not in ("candidates", "engine_reported_guarantees")
        },
        search_result=SimpleNamespace(
            paths=(), expansions=0, truncated=False, truncation_reason=None, complete=True
        ),
        optimization_scope=None,
        is_minimum_proven_over_scope=False,
        is_no_path_proven_over_scope=False,
    )

    def transport(command, **kwargs):
        path = command[command.index("--output") + 1]
        from pathlib import Path

        Path(path).write_text(json.dumps({"semantic": cli}, indent=2, sort_keys=True) + "\n")
        return SimpleNamespace(returncode=0, stderr="")

    monkeypatch.setattr(probe.subprocess, "run", transport)
    monkeypatch.setattr(probe, "run_attack_query", lambda *a, **k: api)
    monkeypatch.setattr(probe, "materialize_query", lambda *a, **k: m)
    monkeypatch.setattr(
        probe,
        "generate_and_evaluate_attack_paths",
        lambda *a, **k: {"roundtrip_result": {}, "search_result": api.search_result},
    )
    with pytest.raises(ValueError, match="API/CLI"):
        probe.public_check(query, graph, tmp_path, "mismatch", "synthetic")
