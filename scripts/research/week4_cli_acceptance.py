"""A-owned subprocess acceptance of the integrated CLI against existing independent inputs."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

from scripts.research.attack_scenarios import state_from
from src.engine.query_cli import canonical_json, digest, wire

ROOT = Path(__file__).resolve().parents[2]
QUERY = "tests/fixtures/query_cli/two-routes-query.json"
GRAPH = "tests/fixtures/attack_scenarios/graphs/two-routes.json"
RATINGS = "docs/research/ratings/week4/synthetic-a2-e.json"


def run_cli_acceptance() -> tuple[dict, dict, list[dict]]:
    """Keep observed process/runtime provenance outside the deterministic semantic payload."""
    base = [
        sys.executable,
        "-m",
        "src.engine.query_cli",
        "--query",
        QUERY,
        "--graph",
        GRAPH,
        "--label",
        "synthetic",
    ]
    processes = []

    def run(command):
        result = subprocess.run(
            command, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", check=False
        )
        processes.append(
            {
                "command": command,
                "return_code": result.returncode,
                "stdout_sha256": digest(result.stdout.encode("utf-8")),
                "stderr": result.stderr,
            }
        )
        return result

    with tempfile.TemporaryDirectory(prefix="week4-cli-") as folder:
        directory = Path(folder)
        first_run = run([*base, "--ranking-query", RATINGS])
        first = json.loads(first_run.stdout) if first_run.returncode == 0 else {}
        first_path, second_path = directory / "first.json", directory / "second.json"
        first_path.write_text(json.dumps(first), encoding="utf-8")
        second_run = run([*base, "--ranking-query", RATINGS, "--output", str(second_path)])
        second = json.loads(second_path.read_text(encoding="utf-8")) if second_path.exists() else {}
        comparison = run(
            [
                sys.executable,
                "-m",
                "scripts.research.compare_query_runs",
                str(first_path),
                str(second_path),
            ]
        )
        compared = json.loads(comparison.stdout) if comparison.stdout else {}
        empty_state, null_ranking = directory / "empty-state.json", directory / "null-ranking.json"
        empty_state.write_text("{}", encoding="utf-8")
        null_ranking.write_text('{"query": null}', encoding="utf-8")
        invalid_outputs = [
            directory / "invalid-state-output.json",
            directory / "invalid-ranking-output.json",
        ]
        empty = run(
            [
                *base,
                "--ranking-query",
                RATINGS,
                "--initial-state",
                str(empty_state),
                "--output",
                str(invalid_outputs[0]),
            ]
        )
        null = run(
            [*base, "--ranking-query", str(null_ranking), "--output", str(invalid_outputs[1])]
        )
        invalid_artifacts_absent = all(not path.exists() for path in invalid_outputs)

    for process, package in zip(processes[:2], (first, second), strict=True):
        process["runtime"] = package.get("runtime")
        process["reproducibility"] = package.get("reproducibility")
    expected_provenance = {
        "revision": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        "tracked_changes": subprocess.check_output(
            ["git", "diff", "HEAD", "--name-only"], cwd=ROOT, text=True
        ).splitlines(),
        "source_files": {
            path.relative_to(ROOT).as_posix(): digest(path.read_bytes())
            for folder in ("src", "scripts")
            for path in sorted((ROOT / folder).rglob("*.py"))
        },
        "config_files": {
            path.relative_to(ROOT).as_posix(): digest(path.read_bytes())
            for path in sorted((ROOT / "configs").rglob("*"))
            if path.is_file()
        },
        "inputs": {
            role: {"reference": name, "sha256": digest((ROOT / name).read_bytes())}
            for role, name in (("query", QUERY), ("graph_input", GRAPH), ("ranking_input", RATINGS))
        },
    }
    semantic = first.get("semantic", {})
    oracle = json.loads(
        (ROOT / "tests/fixtures/attack_scenarios/week4-v1.json").read_text(encoding="utf-8")
    )
    aliases = oracle["graphs"]["two-routes"]["aliases"]
    names = {value: name for name, value in aliases.items()}
    paths = semantic.get("candidates", [])
    sequences = sorted(
        [
            [
                [
                    request["technique_id"],
                    *[
                        names.get(request[key], request[key])
                        for key in ("actor", "source", "target")
                    ],
                ]
                for step in path["transition_history"]
                for request in [step["result"]["request"]]
            ]
            for path in paths
        ]
    )
    initial = semantic.get("materialized", {}).get("initial_attack_state")
    states = {canonical_json(initial)} | {
        canonical_json(attempt["after"])
        for attempt in semantic.get("attempts", [])
        if attempt["status"] == "applicable"
    }
    expected_states = {
        canonical_json(wire(state_from(state, aliases)))
        for state in oracle["scenarios"][0]["variants"][0]["expected_search"]["required_reachable"]
    }
    ranking = semantic.get("ranking_result") or {}
    rated = ranking.get("eligible_candidates", {})
    minimum = semantic.get("min_effort") or {}
    guarantees = semantic.get("engine_reported_guarantees") or {}
    return (
        {
            "exit_code": first_run.returncode,
            "output_exit_code": second_run.returncode,
            "schema_version": first.get("schema_version"),
            "status": semantic.get("status"),
            "paths_count": len(paths),
            "path_sequences": sequences,
            "reachable_states_match_oracle": states == expected_states,
            "final_goal_reached": semantic.get("final_goal_reached"),
            "checkpoint_reached": semantic.get("checkpoint_reached"),
            "complete": semantic.get("complete"),
            "truncated": semantic.get("truncated"),
            "ranking_disposition": semantic.get("ranking_disposition"),
            "minimum_effort_value": minimum.get("minimum_effort_value"),
            "best_candidate_id": minimum.get("best_candidate_id"),
            "optimization_scope": guarantees.get("optimization_scope"),
            "is_minimum_proven_over_scope": guarantees.get("is_minimum_proven_over_scope"),
            "efforts": {key: value["effort"] for key, value in rated.items()},
            "likelihoods": {key: value["likelihood_interval"] for key, value in rated.items()},
            "impacts": {key: value["impact"] for key, value in rated.items()},
            "semantic_digest_valid": first.get("reproducibility", {}).get("semantic_sha256")
            == digest(canonical_json(semantic).encode("utf-8")),
            "source_provenance_verified": all(
                package.get("reproducibility", {}).get(key) == expected
                for package in (first, second)
                for key, expected in expected_provenance.items()
            ),
            "comparison_exit_code": comparison.returncode,
            "two_runs_equal": compared.get("equal") is True,
            "runtime_compared": compared.get("runtime_compared"),
            "output_stdout_empty": second_run.stdout == "",
            "invalid_exit_codes": {
                "empty_state": empty.returncode,
                "null_ranking": null.returncode,
            },
            "invalid_stdout_empty": empty.stdout == null.stdout == "",
            "invalid_diagnostics_present": bool(empty.stderr.strip()) and bool(null.stderr.strip()),
            "invalid_artifacts_absent": invalid_artifacts_absent,
        },
        {"semantic": semantic, "comparison": compared},
        processes,
    )
