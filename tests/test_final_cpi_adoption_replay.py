"""Adversarial evidence-scope accounting tests; invented counts are test-only."""

import copy

import pytest

from scripts.research import final_cpi_adoption_replay as replay
from scripts.research.final_cpi_profiles import bind_source_a, read
from scripts.research.final_cpi_release import apply_release
from scripts.research.issue250_public_probe import save
from src.engine.graph import EngineGraph
from src.engine.ranking.resolution_service import canonical_digest


@pytest.fixture
def accounting_case(monkeypatch, tmp_path):
    release = read(replay.RELEASE)
    bound, canonical = bind_source_a("source-a-projection")
    graph = EngineGraph.from_canonical(canonical)
    local, package = tmp_path / "local", tmp_path / "package"
    cohort, supplement = package / "cohort.json", package / "supplement.json"
    save(
        cohort,
        {
            "queries": [
                {"id": "source-a-projection", "supported_cohort": True},
                {"id": "source-a-full-raw-four", "supported_cohort": True},
            ]
        },
    )
    save(
        supplement,
        {
            "queries": [
                {
                    "id": "winrm-command",
                    "supported": False,
                    "budget": {"max_steps": 4},
                    "selection": "fixed test selector",
                },
            ]
        },
    )
    source = tmp_path / "src/engine.py"
    source.parent.mkdir()
    source.write_text("# test-only source identity\n")
    monkeypatch.setattr(replay, "ROOT", tmp_path)
    monkeypatch.setattr(replay, "SOURCE_PATTERNS", ("src/**/*.py",))
    monkeypatch.setattr(replay, "LOCAL", local)
    monkeypatch.setattr(replay, "PACKAGE", package)
    monkeypatch.setattr(replay, "COHORT", supplement)
    monkeypatch.setattr(replay, "REPORT", tmp_path / "report.json")
    monkeypatch.setattr(replay, "load_inputs", lambda raw_dir: (graph, {}))

    def prepare(group, case, raw, frozen, raw_dir, current_release):
        if group == "original":
            return bound, apply_release(bound, current_release), graph, True
        query = {"test_only_pending": True, "budget": case["budget"]}
        return query, query, graph, False

    monkeypatch.setattr(replay, "prepare_case", prepare)
    execution = replay.execution_identity()
    for group, cohort_path in (("original", cohort), ("supplementary", supplement)):
        declared = read(cohort_path)
        case = declared["queries"][0]
        original, consumed, case_graph, adopted = prepare(group, case, graph, {}, tmp_path, release)
        scope = replay.evidence_scope(
            group,
            declared,
            case,
            release,
            execution,
            replay.graph_identity(graph),
            case_graph,
            original,
            consumed,
        )
        name = group + "." + case["id"]
        save(local / (name + ".query.json"), consumed)
        save(
            local / (name + ".verified.json"),
            {
                "evidence_scope": scope,
                "execution_identity": replay.execution_summary(execution),
                "supported_cohort": case[
                    "supported_cohort" if group == "original" else "supported"
                ],
                "numeric_adoption_applied": adopted,
                "query_before_release_digest": canonical_digest(original),
                "query_consumed_digest": canonical_digest(consumed),
                "graph": {
                    "nodes": len(graph.nodes()),
                    "edges": len(graph.edges()),
                    "is_full_raw": True,
                    "sha256": replay.graph_identity(graph)["graph_digest"],
                },
                "actual_after_decision": {
                    "truncated": False,
                    "counts": {
                        "valid_generated": 2,
                        "conditioned_feasible": 2,
                        "fully_rated": 2 if adopted else 0,
                    },
                },
            },
        )
    return {
        "raw": tmp_path,
        "source": source,
        "graph": graph,
        "release": release,
        "supplement": supplement,
    }


def test_missing_queries_never_pass_gate_or_pool_supplement(accounting_case):
    replay.aggregate(accounting_case["raw"])
    groups = read(replay.REPORT)["groups"]
    original, supplement = groups["original"], groups["supplementary"]
    assert original["supported_returned_sample_full_fraction"] == "1"
    assert not original["complete_replay"]
    assert not original["meets_80_percent_on_complete_supported_returned_sample"]
    assert original["missing_queries"] == ["source-a-full-raw-four"]
    assert supplement["supported_completed_query_counts"] == {}
    assert supplement["all_completed_query_counts"]["conditioned_feasible"] == 2


def test_tampered_consumed_query_is_not_published(accounting_case):
    path = replay.LOCAL / "original.source-a-projection.query.json"
    changed = read(path)
    changed["budget"]["max_steps"] = 1
    save(path, changed)
    with pytest.raises(ValueError, match="consumed query digest mismatch"):
        replay.aggregate(accounting_case["raw"])
    assert not replay.REPORT.exists()


def test_checkpoint_from_another_review_is_not_reused(accounting_case, monkeypatch, tmp_path):
    changed = copy.deepcopy(accounting_case["release"])
    changed["review"]["reference"] = "test://different-review-not-actual-adoption"
    path = tmp_path / "test-only-release.json"
    save(path, changed)
    monkeypatch.setattr(replay, "RELEASE", path)
    with pytest.raises(ValueError, match="evidence scope mismatch"):
        replay.aggregate(accounting_case["raw"])
    assert not replay.REPORT.exists()


@pytest.mark.parametrize("field", ["supported", "budget", "selection", "cohort_metadata"])
def test_nonadopted_stale_checkpoint_refuses_current_cohort_changes(accounting_case, field):
    cohort = read(accounting_case["supplement"])
    case = cohort["queries"][0]
    if field == "supported":
        case["supported"] = True
    elif field == "budget":
        case["budget"]["max_steps"] = 1
    elif field == "selection":
        case["selection"] = "another selector"
    else:
        cohort["snapshot_id"] = "test://changed-cohort-snapshot"
    save(accounting_case["supplement"], cohort)
    with pytest.raises(ValueError, match="evidence scope mismatch"):
        replay.aggregate(accounting_case["raw"])
    assert not replay.REPORT.exists()


@pytest.mark.parametrize("field", ["source", "runtime", "graph", "snapshot", "legacy"])
def test_stale_execution_and_graph_identity_refused(accounting_case, monkeypatch, field):
    if field == "source":
        accounting_case["source"].write_text("# changed executable source\n")
    elif field == "runtime":
        current = replay.execution_identity()
        current["python_executable_digest"] = "test://another-interpreter"
        monkeypatch.setattr(replay, "execution_identity", lambda: current)
    elif field in ("graph", "snapshot"):
        canonical = accounting_case["graph"].to_canonical()
        key = "description" if field == "graph" else "snapshot_id"
        canonical["metadata"][key] = (
            "sha256:" + "0" * 64 if field == "snapshot" else "changed graph"
        )
        changed = EngineGraph.from_canonical(canonical)
        monkeypatch.setattr(replay, "load_inputs", lambda raw_dir: (changed, {}))
    else:
        path = replay.LOCAL / "supplementary.winrm-command.verified.json"
        row = read(path)
        del row["evidence_scope"]
        save(path, row)
    with pytest.raises(ValueError, match="evidence scope mismatch"):
        replay.aggregate(accounting_case["raw"])
    assert not replay.REPORT.exists()


def test_aggregation_requires_verified_raw_inputs():
    with pytest.raises(ValueError, match="raw-dir required"):
        replay.load_inputs(None)
