"""Runner verdict regressions use real semantics without private SEAMLESS inputs."""

import copy
import json
import subprocess
import sys
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import pytest

from scripts.check_contract import canonical_edge_id
from scripts.research import kerberoasting_seamless_acceptance as runner
from scripts.research.kerberoasting_probe import C, D, G, U, V, X, synthetic
from src.engine.graph import EngineGraph
from src.parser.snapshot_facts import graph_digest

ROOT = Path(__file__).resolve().parents[1]


def _synthetic_inputs(*_):
    engine, _ = synthetic()
    graph = engine.to_canonical()
    labels = {
        U: "ALEXANDRIA_WALSH@SEAMLESS.INTERNAL",
        V: "AVIS_SWEET@SEAMLESS.INTERNAL",
        X: "AWSWWKS1000000.SEAMLESS.INTERNAL",
        G: "HO-170-DISTLIST1@SEAMLESS.INTERNAL",
        C: "BADBLOOD.SEAMLESS.INTERNAL",
    }
    for node in graph["nodes"]:
        node["label"] = labels[node["id"]]
    user = copy.deepcopy(next(n for n in graph["nodes"] if n["id"] == U))
    user.update(id=D, label="KATRINA_GREEN@SEAMLESS.INTERNAL")
    graph["nodes"].append(user)
    graph["edges"] = [edge for edge in graph["edges"] if edge["kind"] != "GenericAll"]
    for source, target, kind in ((G, D, "GenericAll"), (D, C, "AdminTo")):
        edge = copy.deepcopy(engine.edges(kind="GenericAll")[0])
        edge.update(
            id=canonical_edge_id(source, target, kind), source=source, target=target, kind=kind
        )
        edge["provenance"][0]["record_id"] = target
        graph["edges"].append(edge)
    facts = replace(engine.snapshot_facts, graph_sha256=graph_digest(graph))
    return EngineGraph.from_canonical(graph, snapshot_facts=facts), None, None, None


def _synthetic_cli(defect, output_dir, report):
    """Patch input loading only; perturb observations after real engine evaluation."""
    inspect = runner.inspect_transition
    execute = runner.execute
    proposals = runner.scenario_proposals

    def is_assumed(query):
        return any(f["predicate"] == "recovery_success" for f in query["assumptions"])

    def inspect_observed(query, engine, request, **kwargs):
        observed = inspect(query, engine, request, **kwargs)
        if defect == "blocked_replay" and is_assumed(query):
            if request.technique_id == "recover_ticket_secret":
                observed["options"][0]["status"] = "blocked"
        if (
            defect == "wrong_drop_status"
            and query["evaluation_mode"] == "scenario"
            and not is_assumed(query)
            and not query["runtime_facts"]
            and request.technique_id == "recover_ticket_secret"
        ):
            observed["options"][0]["status"] = "blocked"
        if (
            defect == "veto_identity_leak"
            and query["runtime_facts"]
            and request.technique_id == "activate_recovered_identity"
        ):
            observed["state"]["usable_identity"].append([V, X])
        return observed

    def execute_observed(query, engine):
        observed = execute(query, engine)
        if defect == "empty_candidates" and is_assumed(query):
            observed["candidates"] = []
        if defect == "wrong_raw_status" and query["evaluation_mode"] == "evidence_only":
            observed["status"] = "success"
        return observed

    def proposals_observed(template, query, engine):
        observed = proposals(template, query, engine)
        if defect == "missing_veto_ledger" and query["runtime_facts"]:
            observed["rejected_assumptions"] = []
        return observed

    sys.argv = [
        "kerberoasting_seamless_acceptance",
        "--raw-dir",
        "synthetic-input-boundary",
        "--output-dir",
        output_dir,
        "--sanitized-report",
        report,
    ]
    with (
        patch.object(runner, "seamless_inputs", _synthetic_inputs),
        patch.object(
            runner, "load_manifest", return_value={"snapshot_id": "sha256:" + "a" * 64}, create=True
        ),
        patch.object(runner, "verify_manifest", return_value=[], create=True),
        patch.object(runner, "inspect_transition", inspect_observed),
        patch.object(runner, "execute", execute_observed),
        patch.object(runner, "scenario_proposals", proposals_observed),
    ):
        raise SystemExit(runner.main())


@pytest.mark.parametrize(
    "defect,expected_status,failed_check",
    [
        ("none", "PASS", None),
        ("blocked_replay", "FAIL", "assumed_replay"),
        ("empty_candidates", "FAIL", "assumed_search"),
        ("wrong_drop_status", "FAIL", "drop_recovery_unknown_halt"),
        ("missing_veto_ledger", "FAIL", "known_false_veto"),
        ("veto_identity_leak", "FAIL", "known_false_veto"),
        ("wrong_raw_status", "FAIL", "raw_mode"),
    ],
)
def test_cli_derives_verdict_from_observed_invariants(
    tmp_path, defect, expected_status, failed_check
):
    report = tmp_path / "summary.json"
    private_root = ROOT / "reports/generated"
    private_root.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=private_root) as output_dir:
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                "import runpy, sys; runpy.run_path(sys.argv[1])['_synthetic_cli'](*sys.argv[2:])",
                str(Path(__file__).resolve()),
                defect,
                output_dir,
                str(report),
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        assert report.is_file(), result.stderr
        summary = json.loads(report.read_text())
        assert summary["status"] == expected_status
        assert (result.returncode == 0) == (expected_status == "PASS"), (
            result.stdout + result.stderr
        )
        failed = [row["check"] for row in summary["matrix"] if row["status"] == "FAIL"]
        assert failed == ([failed_check] if failed_check else [])


@pytest.mark.parametrize("raw_exists", [False, True], ids=["missing", "invalid-manifest"])
def test_cli_blocks_missing_or_unverified_raw_inputs(tmp_path, raw_exists):
    raw_dir = tmp_path / "raw"
    if raw_exists:
        raw_dir.mkdir()
        (raw_dir / "unverified.json").write_text("{}\n")
    report = tmp_path / "summary.json"
    private_root = ROOT / "reports/generated"
    private_root.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=private_root) as output_dir:
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "scripts.research.kerberoasting_seamless_acceptance",
                "--raw-dir",
                str(raw_dir),
                "--output-dir",
                output_dir,
                "--sanitized-report",
                str(report),
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        assert report.is_file(), result.stderr
        summary = json.loads(report.read_text())
        assert summary["status"] == "BLOCKED"
        assert result.returncode != 0
        assert summary["matrix"][0]["check"] == "manifest"
        assert summary["matrix"][0]["status"] == "BLOCKED"
