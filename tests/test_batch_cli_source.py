"""Single-foothold CLI uses the same scoped discovery API as Python callers."""

import json
import subprocess
import sys
from pathlib import Path

from src.engine.batch import discover_source
from src.engine.graph import EngineGraph

ROOT = Path(__file__).resolve().parents[1]
REQUEST = ROOT / "tests/fixtures/batch_contracts/batch_request_example.json"
GRAPH = ROOT / "tests/fixtures/attack_scenarios/graphs/two-routes.json"


def test_cli_single_source_matches_native_api_and_rejects_an_unknown_selector(tmp_path):
    output = tmp_path / "result.json"
    command = [
        sys.executable,
        "-m",
        "src.engine",
        "batch",
        "--batch-request",
        str(REQUEST),
        "--graph",
        str(GRAPH),
        "--label",
        "synthetic",
        "--source",
        "src-alice-usable",
        "--output",
        str(output),
    ]
    subprocess.run(command, cwd=ROOT, capture_output=True, text=True, check=True)
    actual = json.loads(output.read_text(encoding="utf-8"))
    expected = discover_source(
        json.loads(REQUEST.read_text()),
        EngineGraph.from_canonical(json.loads(GRAPH.read_text())),
        source_id="src-alice-usable",
    ).to_dict()
    actual["reproducibility"].pop("runtime")
    expected["reproducibility"].pop("runtime")
    assert actual == expected
    assert set(actual["source_goal_matrix"]) == {"src-alice-usable"}
    command[command.index("src-alice-usable")] = "unknown-source"
    command[-1] = str(tmp_path / "refused.json")
    process = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
    assert process.returncode == 2
    assert "exactly one declared source" in process.stderr
    assert not (tmp_path / "refused.json").exists()
