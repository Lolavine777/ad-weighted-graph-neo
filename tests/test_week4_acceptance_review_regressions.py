"""Review regressions: acceptance must reject changed engine observations."""

import subprocess
from pathlib import Path
from types import SimpleNamespace

from scripts.research import week4_acceptance_runner as runner


def demo_shell(platform, git_executable):
    """Windows PATH may resolve bash to WSL; use Git's own Bash installation."""
    if platform != "win32":
        return "bash"
    if git_executable is None:
        raise RuntimeError("Git Bash is required for the documented demo")
    git = Path(git_executable)
    for bash in (git.parent / "bash.exe", git.parent.parent / "bin" / "bash.exe"):
        if bash.is_file():
            return str(bash)
    raise RuntimeError("Cannot locate Git Bash beside the Git installation")


def test_baseline_mutation_is_unexpected_failure(monkeypatch):
    original = runner.run_attack_query
    calls = 0

    def changed(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            return SimpleNamespace(
                status="no_path",
                paths=[],
                final_goal_reached=False,
                checkpoint_reached=False,
            )
        return original(*args, **kwargs)

    monkeypatch.setattr(runner, "run_attack_query", changed)
    revision = subprocess.check_output(
        ["git", "rev-parse", "HEAD"],
        cwd=runner.ROOT,
        text=True,
    ).strip()
    result = runner.run_all_cases(revision)
    case = result["cases"][0]
    assert case["verdict"] == "FAIL"
    assert "expectation" in case["disposition"].lower()
    assert result["summary"]["unexpected_failure_count"] == 1


def test_fabricated_revision_is_rejected():
    import pytest

    with pytest.raises(ValueError, match="revision"):
        runner.run_all_cases("this-is-not-the-executed-revision")


def test_execution_metadata_is_observed():
    import platform

    result = runner.run_all_cases()
    metadata = result["execution"]
    assert metadata["runtime"]["python"] == platform.python_version()
    assert metadata["runtime"]["platform"] == platform.platform()
    assert metadata["runtime"]["machine"] == platform.machine()
    assert (
        metadata["source"]["revision"]
        == subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=runner.ROOT,
            text=True,
        ).strip()
    )
    assert metadata["executed_at"]
    assert metadata["file_sha256"]["configs/contract.yml"]
    assert "src/engine/query.py" in metadata["file_sha256"]
    assert "configs/attack_semantics.yml" in metadata["file_sha256"]
    assert metadata["catalog"]["technique_ids"]
    dataset = next(c for c in result["cases"] if c["case_id"] == "W4-SEAMLESS-DATASET-GATE")
    assert dataset["actual"]["probe_execution"] == "not_executed"
    assert dataset["command"] is None


def test_cli_acceptance_validates_content_provenance_in_working_tree():
    actual, _, processes = runner.run_cli_acceptance()
    assert actual["source_provenance_verified"] is True
    assert "clean_tracked_source" not in actual
    assert processes[0]["reproducibility"]["revision"]


def test_cli_acceptance_rejects_forged_source_pin(monkeypatch):
    import json

    from scripts.research import week4_cli_acceptance as cli

    original = cli.subprocess.run

    def forged(*args, **kwargs):
        process = original(*args, **kwargs)
        if process.returncode == 0 and process.stdout.lstrip().startswith("{"):
            payload = json.loads(process.stdout)
            if "reproducibility" in payload:
                payload["reproducibility"]["source_files"]["src/engine/query.py"] = (
                    "sha256:" + "0" * 64
                )
                process.stdout = json.dumps(payload)
        return process

    monkeypatch.setattr(cli.subprocess, "run", forged)
    actual, _, _ = cli.run_cli_acceptance()
    assert actual["source_provenance_verified"] is False


def test_every_normative_field_controls_verdict():
    from copy import deepcopy

    result = runner.run_all_cases()
    for original in result["cases"]:
        if original["execution_status"] != "executed":
            continue
        for field in original["expected"]:
            changed = deepcopy(original)
            actual_field = field.removesuffix("_contains")
            changed["actual"][actual_field] = "MUTATED"
            runner.evaluate_case(changed)
            assert changed["verdict"] == "FAIL", (original["case_id"], field)
        changed = deepcopy(original)
        for field in changed["expected"]:
            changed["actual"].pop(field.removesuffix("_contains"), None)
        runner.evaluate_case(changed)
        assert changed["verdict"] == "FAIL", original["case_id"]


def test_known_defect_can_be_fixed_or_change_unexpectedly():
    from copy import deepcopy

    result = runner.run_all_cases()
    for case in result["cases"]:
        if not case.get("known_observation"):
            continue
        assert case["verdict"] == "PASS"
        recurring = deepcopy(case)
        for field, value in case["known_observation"].items():
            recurring["actual"][field.removesuffix("_contains")] = value
        runner.evaluate_case(recurring)
        assert recurring["verdict"] == "KNOWN DEFECT"
        repaired = deepcopy(recurring)
        repaired["actual"].update(repaired["expected"])
        runner.evaluate_case(repaired)
        assert repaired["verdict"] == "PASS"
        unexpected = deepcopy(case)
        unexpected["actual"]["paths_count"] = -1
        runner.evaluate_case(unexpected)
        assert unexpected["verdict"] == "FAIL"


def test_cli_failure_exit_and_selected_case(monkeypatch, capsys):
    result = runner.run_all_cases()
    result["cases"][0]["actual"]["paths_count"] = 0
    runner.evaluate_case(result["cases"][0])
    result["summary"] = runner.summarize(result["cases"])
    monkeypatch.setattr(runner, "run_all_cases", lambda revision=None: result)
    monkeypatch.setattr(runner.sys, "argv", ["runner"])
    assert runner.main() == 1
    monkeypatch.setattr(runner.sys, "argv", ["runner", "--case-id", "W4-M-POSITIVE"])
    assert runner.main() == 1
    monkeypatch.setattr(runner.sys, "argv", ["runner", "--case-id", "W4-G-U"])
    assert runner.main() == 0
    capsys.readouterr()


def test_demo_commands_and_claims_smoke(tmp_path):
    """Execute every bash block; wrong prerequisites/scoring commands must fail."""
    import re
    import shlex
    import shutil

    demo = (runner.ROOT / "docs/reports/week4-demo.md").read_text(encoding="utf-8")
    report = (runner.ROOT / "docs/reports/week4-report.md").read_text(encoding="utf-8")
    for text in (demo, report):
        assert not re.search(r"github|\bPRs?\b|\bissues?\b", text, re.IGNORECASE)
        assert "two_routes_scenario.json" not in text
        assert "\N{EM DASH}" not in text
        assert "synthetic-a2-e.json" in text
        assert "recover_ticket_secret" in text
    blocks = re.findall(r"```bash\n(.*?)\n```", demo, re.DOTALL)
    assert blocks
    for block in blocks:
        command = block.replace(
            ".venv/bin/python", shlex.quote(runner.sys.executable.replace("\\", "/"))
        )
        result = subprocess.run(
            [demo_shell(runner.sys.platform, shutil.which("git")), "-e", "-c", command],
            cwd=runner.ROOT,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stdout + result.stderr


def test_case_cli_is_nonzero_for_mutated_engine(tmp_path):
    """Use the actual CLI in a child process with the reviewer's first-call mutation."""
    import os

    hook = tmp_path / "mutated_cli.py"
    hook.write_text(
        """
from types import SimpleNamespace
from pathlib import Path
from scripts.research import week4_acceptance_runner as runner
original = runner.run_attack_query
calls = 0
def changed(*args, **kwargs):
    global calls
    calls += 1
    if calls == 1:
        return SimpleNamespace(
            status="no_path", paths=[], final_goal_reached=False, checkpoint_reached=False,
        )
    return original(*args, **kwargs)
runner.run_attack_query = changed
raise SystemExit(runner.main())
""",
        encoding="utf-8",
    )
    result = subprocess.run(
        [runner.sys.executable, str(hook), "--case-id", "W4-M-POSITIVE"],
        cwd=runner.ROOT,
        env={**os.environ, "PYTHONPATH": str(runner.ROOT)},
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    import json

    case = json.loads(result.stdout)
    assert case["verdict"] == "FAIL"
    assert {c["field"] for c in case["assertions"] if not c["passed"]} >= {
        "status",
        "paths_count",
        "final_goal_reached",
    }


def test_windows_demo_uses_git_bash_instead_of_wsl(tmp_path):
    """CI reproduced PATH bash selecting the WSL launcher, which cannot run the demo."""
    git_binary = tmp_path / "Git" / "cmd" / "git.exe"
    git_binary.parent.mkdir(parents=True)
    git_binary.touch()
    git_bash = tmp_path / "Git" / "bin" / "bash.exe"
    git_bash.parent.mkdir()
    git_bash.touch()
    assert demo_shell("win32", str(git_binary)) == str(git_bash)


def test_rbcd_acceptance_inputs_pinned_and_mutation_detected(monkeypatch):
    pins = runner.file_pins()
    required = {
        "scripts/research/rbcd_inputs.py",
        "tests/fixtures/rbcd/snapshot.json",
        "tests/fixtures/rbcd/query.json",
        "tests/fixtures/rbcd/query-off.json",
        "tests/fixtures/rbcd/query-raw.json",
        "tests/fixtures/rbcd/oracle.json",
        "tests/test_rbcd.py",
        "docs/research/rbcd-229.md",
    }
    for req in required:
        assert req in pins, f"{req} must be in file_pins"

    # Verify that mutation of an RBCD pinned file is detected in execution_metadata
    original_pins = runner.file_pins
    mutated_file = "tests/fixtures/rbcd/snapshot.json"

    def fake_pins():
        p = original_pins()
        p[mutated_file] = "0" * 64
        return p

    monkeypatch.setattr(runner, "file_pins", fake_pins)
    meta = runner.execution_metadata(revision=None)
    assert mutated_file in meta["source"]["dirty_pinned_files"]
    assert meta["source"]["identity"] == "working_tree"
