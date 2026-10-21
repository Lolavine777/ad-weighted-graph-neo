"""Wave 2 accounting tests; invented counts and decisions are test-only."""

import copy
import importlib
import json
import subprocess
import sys

import pytest

from scripts.research.final_cpi_coverage import COUNT_FIELDS
from scripts.research.final_cpi_profiles import bind_source_a, read
from scripts.research.issue250_public_probe import save
from src.engine import run_attack_query
from src.engine.graph import EngineGraph
from src.engine.query_cli import wire
from src.engine.ranking.resolution_service import canonical_digest
from tests.test_final_cpi_release import native_case as native_case


@pytest.fixture
def replay():
    name = "scripts.research.final_cpi_wave2_replay"
    return importlib.import_module(name)


def test_candidate_withholds_missing_classes_and_needs_evidence_dimensions(replay):
    query, canonical = bind_source_a("source-a-projection")
    graph = EngineGraph.from_canonical(canonical)
    before = copy.deepcopy(query)
    pending = {
        "classes": {
            "directory_password_reset": {
                "C": {"decision": "pending"},
                "P": {"decision": "needs_evidence"},
            },
        },
        "impacts": {"source-a-projection": {"decision": "pending", "rating": "High"}},
    }
    candidate, derivative = replay.candidate_copy(query, graph, pending)
    original = query["rating_resolution"]["registries"]
    registries = candidate["rating_resolution"]["registries"]
    for before_record, after_record in zip(
        original["effort"]["data"], registries["effort"]["data"], strict=True
    ):
        if before_record["name"] == "directory_password_reset":
            assert after_record["numeric_basis_class"] == "synthetic_test_only"
        else:
            assert after_record == before_record
    assert registries["likelihood"] == original["likelihood"]
    assert candidate["rating_resolution"]["policy"] == "synthetic_test_only"
    assert derivative.metadata["synthetic"] is True
    assert graph.metadata.get("synthetic") is not True
    assert query == before
    assert not run_attack_query(candidate, derivative).ranking_result["eligible_candidates"]


def test_candidate_withholds_unlisted_typed_impact(replay):
    query, canonical = bind_source_a("source-a-projection")
    candidate, _ = replay.candidate_copy(
        query, EngineGraph.from_canonical(canonical), {"classes": {}, "impacts": {}}
    )
    for role in ("impact", "impact_source"):
        assert (
            candidate["rating_resolution"]["registries"][role]
            == query["rating_resolution"]["registries"][role]
        )


def test_family_coverage_counts_programs_nonexclusively(replay, native_case):
    query, graph, _, _, actual = native_case
    pending = run_attack_query(query, graph)
    pending_families = replay.report_family_coverage(pending)
    actual_families = replay.report_family_coverage(actual)
    assert actual_families.keys() == {
        "directory_password_reset",
        "reset_identity_activation",
        "winrm_admin_execution",
    }
    for family, counts in actual_families.items():
        assert counts == dict.fromkeys(COUNT_FIELDS, len(actual.paths))
        assert pending_families[family]["conditioned_feasible"] == len(pending.paths)
        assert pending_families[family]["fully_rated"] == 0
    assert sum(row["valid_generated"] for row in actual_families.values()) > len(actual.paths)
    ledger = replay.step_blockers(actual)
    assert len(ledger["programs"]) == len(actual.paths)
    for program in ledger["programs"]:
        assert program["terminal_I"]["value"] == "High"
        for step in program["steps"]:
            if step["active"]:
                assert step["C"]["diagnosis"] == "resolved"
                assert step["P"]["diagnosis"] == "resolved"
            else:
                assert step["P"]["diagnosis"] == "passive_no_success_event"
    assert "S-1-5-" not in str(ledger)


def test_production_wave1_native_topk_preserves_full_coverage(replay, native_case, tmp_path):
    _, graph, _, query, baseline = native_case
    query = copy.deepcopy(query)
    canonical = graph.to_canonical()
    # Top-K is a presentation selector; source, scope, caps and rating histories stay exact.
    query["top_k"] = 3
    selected = run_attack_query(query, EngineGraph.from_canonical(canonical))
    assert selected.rating_coverage == baseline.rating_coverage
    assert wire(selected.paths) == wire(baseline.paths)
    assert selected.top_k_result["returned_count"] == 3
    save(tmp_path / "query.json", query)
    save(tmp_path / "graph.json", canonical)
    for _ in range(2):
        process = subprocess.run(
            [
                sys.executable,
                "-m",
                "src.engine.query_cli",
                "--query",
                str(tmp_path / "query.json"),
                "--graph",
                str(tmp_path / "graph.json"),
                "--label",
                "seamless",
                "--prerequisite",
                str(replay.ROOT / "data/samples/manifests/seamless-raw-v1.json"),
            ],
            cwd=replay.ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=True,
        )
        packet = json.loads(process.stdout)
        assert packet["semantic"]["top_k"] == wire(selected.top_k_result)


@pytest.fixture(scope="module")
def raw_context():
    from scripts.research import final_cpi_wave2_replay as tool

    raw = tool.ROOT / "data/raw/SEAMLESS"
    if not raw.is_dir():
        pytest.skip("Authorized manifest-verified raw required")
    graph, frozen = tool.load_inputs(raw)
    return raw, graph, frozen, read(tool.RELEASE), read(tool.PENDING)


@pytest.mark.parametrize(
    "case_id,expected_full",
    [("asrep-natural-password", 0), ("kerberoast-material", 1), ("kerberoast-identity", 0)],
)
def test_raw_roasting_preserves_unrated_password_and_activation(
    replay, raw_context, case_id, expected_full
):
    raw, graph, frozen, current, pending = raw_context
    case = next(c for c in read(replay.PACKAGE / "cohort.json")["queries"] if c["id"] == case_id)
    query, _, original, _, candidate, derivative, preview = replay.prepare_queries(
        "original", case, graph, frozen, raw, current, pending
    )
    assert preview
    baseline = run_attack_query(query, original)
    result = run_attack_query(candidate, derivative)
    assert wire(result.paths) == wire(baseline.paths)
    assert replay.report_case(result)["counts"]["fully_rated"] == expected_full
    if case_id == "asrep-natural-password":
        ledger = replay.step_blockers(result)
        steps = ledger["programs"][0]["steps"]
        recovery = next(s for s in steps if s["technique"] == "recover_asrep_secret")
        assert recovery["P"]["diagnosis"] == "missing_numeric_basis"
        activation = next(s for s in steps if s["technique"] == "activate_recovered_identity")
        assert activation["P"]["diagnosis"] == "recovered_secret_lineage_history_unapproved"
    taxonomy = {
        row["technique_id"]: row["canonical_class"]
        for row in read(replay.PACKAGE / "taxonomy.json")["actions"]
    }
    registries = candidate["rating_resolution"]["registries"]
    original_registries = query["rating_resolution"]["registries"]
    for role, dimension in (("effort", "C"), ("likelihood", "P")):
        for before, after in zip(
            original_registries[role]["data"], registries[role]["data"], strict=True
        ):
            cls = before["name"] if dimension == "C" else taxonomy[before["outcome_technique"]]
            if (
                cls == "recovered_identity_activation"
                or dimension == "P"
                and cls in {"asrep_password_recovery", "kerberoast_password_recovery"}
            ):
                assert after == before


def test_native_candidate_public_transport_and_fraction_oracle(replay, raw_context, tmp_path):
    raw, graph, frozen, current, pending = raw_context
    case = next(
        c
        for c in read(replay.PACKAGE / "cohort.json")["queries"]
        if c["id"] == "kerberoast-material"
    )
    _, _, _, _, candidate, derivative, _ = replay.prepare_queries(
        "original", case, graph, frozen, raw, current, pending
    )
    result, public = replay.public_check(
        candidate, derivative, tmp_path, "candidate", "synthetic", timeout_seconds=180
    )
    assert public["two_CLI_exit_codes"] == [0, 0]
    assert public["API_CLI_semantic_ranking_coverage_programs_equal"]
    assert public["orchestration_search_ranking_programs_equal"]
    assert replay.independent_checks(result)["checked_eligible_candidates"] == 1


def test_raw_acl_diagnostic_distinguishes_work_source_contexts(replay, raw_context):
    raw, graph, frozen, current, pending = raw_context
    case = next(c for c in read(replay.COHORT)["queries"] if c["id"] == "acl-group-projection")
    _, production, projected, _, candidate, derivative, _ = replay.prepare_queries(
        "supplementary", case, graph, frozen, raw, current, pending
    )
    for query, selected in ((production, projected), (candidate, derivative)):
        result = run_attack_query(query, selected)
        ledger = replay.step_blockers(result)
        assert len(ledger["programs"]) == len(result.paths) == 100
        assert any(
            step["technique"] == "genericall_add_member"
            for program in ledger["programs"]
            for step in program["steps"]
        )
        assert "S-1-5-" not in str(ledger)


@pytest.fixture
def accounting_case(replay, monkeypatch, tmp_path):
    _, canonical = bind_source_a("source-a-projection")
    graph = EngineGraph.from_canonical(canonical)
    package, local = tmp_path / "package", tmp_path / "local"
    supplement = package / "supplement.json"
    save(
        package / "cohort.json",
        {"queries": [{"id": "already-adopted", "supported_cohort": True}]},
    )
    save(
        supplement,
        {
            "queries": [
                {"id": "pending-material", "supported": True},
                {"id": "unassumed-control", "supported": False},
            ]
        },
    )
    current_release = {"query_pins": {"already-adopted": "test://adopted"}, "review": {}}
    pending_query = {"test_only_pending": True, "target_goal": {}}
    candidate_query = {"test_only_synthetic": True, "target_goal": {}}
    pending = {
        "status": "pending_b_numeric_review",
        "query_pins": {"pending-material": canonical_digest(pending_query)},
        "contexts": {"pending-material": {"decision": "pending"}},
    }
    release_path, pending_path = tmp_path / "current.json", tmp_path / "pending.json"
    save(release_path, current_release)
    save(pending_path, pending)
    monkeypatch.setattr(replay, "PACKAGE", package)
    monkeypatch.setattr(replay, "COHORT", supplement)
    monkeypatch.setattr(replay, "LOCAL", local)
    monkeypatch.setattr(replay, "REPORT", tmp_path / "report.json")
    monkeypatch.setattr(replay, "RELEASE", release_path)
    monkeypatch.setattr(replay, "PENDING", pending_path)
    monkeypatch.setattr(replay, "load_inputs", lambda raw: (graph, {}))
    monkeypatch.setattr(replay, "execution_identity", lambda: {"test_source": "frozen"})
    monkeypatch.setattr(replay.release_tool, "template_wave2", lambda graph, raw: pending)

    def prepare(group, case, raw_graph, frozen, raw_dir, release):
        adopted = case["id"] == "already-adopted"
        query = {"test_only_adopted": True, "target_goal": {}} if adopted else pending_query
        return query, query, raw_graph, adopted

    monkeypatch.setattr(replay, "prepare_case", prepare)
    monkeypatch.setattr(
        replay, "candidate_copy", lambda query, graph, release: (candidate_query, graph)
    )
    execution = replay.execution_identity()
    for group, cohort_path in (
        ("original", package / "cohort.json"),
        ("supplementary", supplement),
    ):
        cohort = read(cohort_path)
        for case in cohort["queries"]:
            query, current, original, adopted, candidate, derivative, applied = (
                replay.prepare_queries(group, case, graph, {}, tmp_path, current_release, pending)
            )
            scope = replay.evidence_scope(
                group,
                cohort,
                case,
                current_release,
                pending,
                execution,
                replay.graph_identity(graph),
                original,
                query,
                current,
                derivative,
                candidate,
                adopted,
                applied,
            )
            current_counts = {
                "valid_generated": 10 if adopted else 2,
                "conditioned_feasible": 10 if adopted else 2,
                "C_rated": 8 if adopted else 0,
                "P_rated": 8 if adopted else 0,
                "I_rated": 8 if adopted else 0,
                "fully_rated": 8 if adopted else 0,
                "Pareto_eligible": 8 if adopted else 0,
            }
            candidate_counts = dict(current_counts)
            if applied:
                candidate_counts.update(dict.fromkeys(COUNT_FIELDS[2:], 2))
            name = group + "." + case["id"]
            save(local / (name + ".current.query.json"), current)
            save(local / (name + ".candidate.query.json"), candidate)
            save(
                local / (name + ".verified.json"),
                {
                    "evidence_scope": scope,
                    "execution_identity": replay.execution_summary(execution),
                    "query_id": case["id"],
                    "supported_cohort": case[
                        "supported_cohort" if group == "original" else "supported"
                    ],
                    "numeric_adoption_applied": adopted,
                    "candidate_preview_applied": applied,
                    "candidate_authority": "synthetic_test_only"
                    if applied
                    else "current_production",
                    "query_before_release_digest": canonical_digest(query),
                    "query_consumed_digest": canonical_digest(current),
                    "candidate_query_consumed_digest": canonical_digest(candidate),
                    "graph": {
                        "nodes": len(original.nodes()),
                        "edges": len(original.edges()),
                        "is_full_raw": True,
                        "sha256": replay.graph_identity(original)["graph_digest"],
                    },
                    "current_production": {"truncated": False, "counts": current_counts},
                    "candidate_engineering_preview": {
                        "truncated": False,
                        "counts": candidate_counts,
                    },
                    "public_verification": {
                        "current_production": {
                            "two_CLI_exit_codes": [0, 0],
                            "two_process_equal": True,
                            "API_CLI_semantic_ranking_coverage_programs_equal": True,
                            "orchestration_search_ranking_programs_equal": True,
                        },
                        "candidate_engineering_preview": {
                            "two_CLI_exit_codes": [0, 0],
                            "two_process_equal": True,
                            "API_CLI_semantic_ranking_coverage_programs_equal": True,
                            "orchestration_search_ranking_programs_equal": True,
                        }
                        if applied
                        else {
                            "same_current_production_execution": True,
                            "current_public_verification_reference": name + ".current",
                        },
                    },
                },
            )
    return {"raw": tmp_path, "pending": pending, "pending_path": pending_path, "graph": graph}


def test_denominators_and_production_authority_stay_separate(replay, accounting_case):
    replay.aggregate(accounting_case["raw"])
    report = read(replay.REPORT)
    original, supplement = report["groups"]["original"], report["groups"]["supplementary"]
    assert original["current_production"]["supported_returned_sample_full_fraction"] == "4/5"
    assert (
        original["candidate_engineering_preview"]["supported_returned_sample_full_fraction"]
        == "4/5"
    )
    assert supplement["current_production"]["supported_returned_sample_full_fraction"] == "0"
    assert (
        supplement["candidate_engineering_preview"]["supported_returned_sample_full_fraction"]
        == "1"
    )
    assert (
        supplement["candidate_engineering_preview"]["all_completed_query_counts"][
            "conditioned_feasible"
        ]
        == 4
    )
    assert not supplement["candidate_engineering_preview"]["production_accepted_coverage"]
    assert not supplement["current_production"][
        "meets_80_percent_on_complete_supported_returned_sample"
    ]


def test_missing_query_never_passes_complete_gate(replay, accounting_case):
    (replay.LOCAL / "original.already-adopted.verified.json").unlink()
    replay.aggregate(accounting_case["raw"])
    group = read(replay.REPORT)["groups"]["original"]
    assert not group["complete_replay"]
    assert group["missing_queries"] == ["already-adopted"]
    assert not group["current_production"]["meets_80_percent_on_complete_supported_returned_sample"]


def test_adopted_query_cannot_receive_synthetic_uplift(replay, accounting_case):
    path = replay.LOCAL / "original.already-adopted.verified.json"
    row = read(path)
    row["candidate_engineering_preview"]["counts"]["fully_rated"] = 10
    save(path, row)
    with pytest.raises(ValueError, match="unchanged current production"):
        replay.aggregate(accounting_case["raw"])
    assert not replay.REPORT.exists()


@pytest.mark.parametrize(
    "field", ["current", "candidate", "cohort", "release", "execution", "graph"]
)
def test_changed_checkpoint_scope_cannot_be_published(replay, accounting_case, monkeypatch, field):
    if field in ("current", "candidate"):
        path = replay.LOCAL / ("supplementary.pending-material." + field + ".query.json")
        query = read(path)
        query["test_only_changed"] = True
        save(path, query)
    elif field == "cohort":
        cohort = read(replay.COHORT)
        cohort["queries"][0]["supported"] = False
        save(replay.COHORT, cohort)
    elif field == "release":
        pending = copy.deepcopy(accounting_case["pending"])
        pending["test_only_changed"] = True
        save(accounting_case["pending_path"], pending)
        monkeypatch.setattr(replay.release_tool, "template_wave2", lambda graph, raw: pending)
    elif field == "execution":
        monkeypatch.setattr(replay, "execution_identity", lambda: {"test_source": "changed"})
    else:
        canonical = accounting_case["graph"].to_canonical()
        canonical["metadata"]["description"] = "test-only changed graph"
        graph = EngineGraph.from_canonical(canonical)
        monkeypatch.setattr(replay, "load_inputs", lambda raw: (graph, {}))
    with pytest.raises(ValueError, match="digest mismatch|evidence scope mismatch"):
        replay.aggregate(accounting_case["raw"])
    assert not replay.REPORT.exists()


def test_changed_candidate_proposal_is_refused_before_replay(replay, accounting_case):
    pending = copy.deepcopy(accounting_case["pending"])
    pending["status"] = "adopted"
    save(accounting_case["pending_path"], pending)
    with pytest.raises(ValueError, match="pending Wave 2 proposal"):
        replay.load_pending(accounting_case["graph"], accounting_case["raw"])


@pytest.mark.parametrize("decision", ["needs_evidence", "reject", None])
def test_withheld_context_cannot_receive_synthetic_preview(replay, accounting_case, decision):
    pending = copy.deepcopy(accounting_case["pending"])
    pending["contexts"]["pending-material"]["decision"] = decision
    case = read(replay.COHORT)["queries"][0]
    _, current, graph, _, candidate, derivative, preview = replay.prepare_queries(
        "supplementary",
        case,
        accounting_case["graph"],
        {},
        accounting_case["raw"],
        read(replay.RELEASE),
        pending,
    )
    assert not preview
    assert candidate == current
    assert derivative is graph


@pytest.mark.parametrize(
    "field,value",
    [
        ("fully_rated", 3),
        ("conditioned_feasible", -1),
        ("C_rated", None),
        ("P_rated", True),
        ("I_rated", 3),
        ("Pareto_eligible", 1),
        ("valid_generated", 1),
    ],
)
def test_invalid_numeric_accounting_cannot_be_published(replay, accounting_case, field, value):
    path = replay.LOCAL / "supplementary.pending-material.verified.json"
    row = read(path)
    counts = row["current_production"]["counts"]
    if value is None:
        del counts[field]
    else:
        counts[field] = value
    save(path, row)
    with pytest.raises(ValueError, match="count accounting"):
        replay.aggregate(accounting_case["raw"])
    assert not replay.REPORT.exists()


@pytest.mark.parametrize("kind", ["current_production", "candidate_engineering_preview"])
@pytest.mark.parametrize("value", [False, None])
def test_false_or_missing_public_success_cannot_be_published(replay, accounting_case, kind, value):
    path = replay.LOCAL / "supplementary.pending-material.verified.json"
    row = read(path)
    public = row["public_verification"][kind]
    key = "API_CLI_semantic_ranking_coverage_programs_equal"
    if value is None:
        del public[key]
    else:
        public[key] = value
    save(path, row)
    with pytest.raises(ValueError, match="public verification"):
        replay.aggregate(accounting_case["raw"])
    assert not replay.REPORT.exists()
