"""Sequential full-query audit benchmark; preserve every native semantic field.

Linux wait4 reports each child RSS; parent parsing/parity checks are outside wall
timing. Three Latin-square cycles compare old pretty, new pretty, new compact.
No live AD connection, semantic approximation or probability calibration.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import platform
import statistics
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODIFIED_SOURCE = {"src/engine/query_cli.py", "scripts/research/benchmark_query_audit.py"}
MEASURE_CHILD = """
import json, os, subprocess, sys, time
from pathlib import Path
command, cwd, log_path, stats_path = json.loads(sys.argv[1])
with open(log_path, 'w') as log:
    start = time.perf_counter()
    child = subprocess.Popen(command, cwd=cwd, stdout=log, stderr=subprocess.STDOUT)
    _, status, usage = os.wait4(child.pid, 0)
    wall = time.perf_counter() - start
    child.returncode = os.waitstatus_to_exitcode(status)
Path(stats_path).write_text(json.dumps({
    'returncode': child.returncode, 'wall_seconds': wall,
    'user_seconds': usage.ru_utime, 'system_seconds': usage.ru_stime,
    'peak_rss_KiB': usage.ru_maxrss}))
sys.exit(child.returncode)
"""


def sha(raw):
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def pin(path):
    raw = path.read_bytes()
    return {"path": str(path), "bytes": len(raw), "sha256": sha(raw)}


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False).encode()


def git(repo, *args):
    return subprocess.check_output(["git", *args], cwd=repo, text=True).strip()


def normalized(package):
    result = copy.deepcopy(package)
    for key in ("started_at", "duration_seconds"):
        del result["runtime"][key]
    del result["reproducibility"]["revision"]
    for path in MODIFIED_SOURCE:
        result["reproducibility"]["source_files"].pop(path, None)
    return result


def semantic_oracle(package, query):
    """Independent finite expectations from declared bindings; no AWG imports."""
    s = package["semantic"]
    source, context, target = (
        query["initial_actor"],
        query["authentication_context"],
        query["target"],
    )
    owners = {
        f["subject"]
        for f in query["assumptions"]
        if f["predicate"] == "membership_usable" and f["target"] == target
    }
    assert len(owners) == 1
    owner = owners.pop()
    assert owner != source
    assert query["initial_state"]["usable_identity"] == [[source, context]]
    expected = [
        ("scenario_reset_password", source, source, owner),
        ("acquire_reset_identity", owner, owner, context),
        ("propagate_group_entitlement", owner, owner, target),
    ]
    assert len(s["candidates"]) == 1
    requests = [t["result"]["request"] for t in s["candidates"][0]["transition_history"]]
    assert [(r["technique_id"], r["actor"], r["source"], r["target"]) for r in requests] == expected
    assert s["min_effort"]["minimum_effort_value"] == 1
    assert s["min_effort"]["associated_likelihood_interval"] is None
    assert s["min_effort"]["associated_impact"] is None
    assert s["engine_reported_guarantees"]["is_minimum_proven_over_scope"] is False
    assert not s["truncated"] and s["expansions"] == 7490
    assert len(s["attempts"]) == 7490 and len(s["diagnostics"]) == 7494
    assert package["reproducibility"]["semantic_sha256"] == sha(canonical(s))


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--before-repo", type=Path, required=True)
    p.add_argument("--after-repo", type=Path, default=ROOT)
    p.add_argument("--snapshot", type=Path, required=True)
    p.add_argument("--query", type=Path, required=True)
    p.add_argument("--raw-dir", type=Path, required=True)
    p.add_argument("--output-dir", type=Path, required=True)
    args = p.parse_args(argv)
    if not hasattr(os, "wait4") or platform.system() != "Linux":
        p.error("This measured RSS harness requires Linux wait4")
    before, after = args.before_repo.resolve(), args.after_repo.resolve()
    for repo in (before, after):
        if git(repo, "status", "--porcelain"):
            p.error(f"Require a clean source revision: {repo}")
    args.output_dir = args.output_dir.resolve()
    args.output_dir.mkdir(parents=True, exist_ok=False)
    manifest_path = after / "data/samples/manifests/seamless-raw-v1.json"
    manifest = json.loads(manifest_path.read_text())
    raw_files = []
    for entry in manifest["files"]:
        raw = (args.raw_dir / entry["relative_path"]).resolve()
        actual = pin(raw)
        assert actual["bytes"] == entry["size_bytes"]
        assert actual["sha256"] == "sha256:" + entry["sha256"]
        raw_files.append(raw)
    query = json.loads(args.query.read_text())
    revisions = {
        "before": git(before, "rev-parse", "HEAD"),
        "after": git(after, "rev-parse", "HEAD"),
    }
    # Each mode appears once in each within-cycle position. All subprocesses are
    # sequential; no tests/profilers run concurrently with this experiment.
    modes = [
        "before",
        "after",
        "compact",
        "after",
        "compact",
        "before",
        "compact",
        "before",
        "after",
    ]
    rows, reference, reference_normalized = [], None, None
    for i, mode in enumerate(modes, 1):
        repo = before if mode == "before" else after
        output = args.output_dir / f"{i:02d}-{mode}.json"
        command = [
            sys.executable,
            "-m",
            "src.engine",
            "query",
            "--snapshot",
            str(args.snapshot.resolve()),
            "--query",
            str(args.query.resolve()),
            "--label",
            "seamless",
            "--output",
            str(output),
        ]
        for raw in raw_files:
            command += ["--prerequisite", str(raw)]
        if mode == "compact":
            command.append("--compact-output")
        # A fresh small supervisor forks the measured CLI. wait4 maxrss can
        # otherwise inherit this parser's large pre-exec RSS at fork, polluting
        # both memory and process-creation measurements in later trials.
        stats = output.with_suffix(".stats.json")
        subprocess.run(
            [
                sys.executable,
                "-c",
                MEASURE_CHILD,
                json.dumps([command, str(repo), str(output.with_suffix(".log")), str(stats)]),
            ],
            check=True,
        )
        measured = json.loads(stats.read_text())
        assert measured.pop("returncode") == 0
        package = json.loads(output.read_text())
        semantic_oracle(package, query)
        assert package["reproducibility"]["tracked_changes"] == []
        assert (
            package["reproducibility"]["revision"]
            == revisions["before" if mode == "before" else "after"]
        )
        norm = normalized(package)
        if reference is None:
            reference, reference_normalized = package, norm
        else:
            assert package["semantic"] == reference["semantic"]
            assert norm == reference_normalized
        row = {
            "index": i,
            "mode": mode,
            "command": command,
            "cwd": str(repo),
            **measured,
            "output": pin(output),
            "semantic_sha256": package["reproducibility"]["semantic_sha256"],
            "normalized_package_sha256": sha(canonical(norm)),
            "reproducibility": package["reproducibility"],
        }
        rows.append(row)
        print(
            json.dumps({k: row[k] for k in ("index", "mode", "wall_seconds", "peak_rss_KiB")}),
            flush=True,
        )
        (args.output_dir / "progress.json").write_text(json.dumps(rows, indent=2) + "\n")
    medians = {
        mode: {
            k: statistics.median(r[k] for r in rows if r["mode"] == mode)
            for k in ("wall_seconds", "user_seconds", "system_seconds", "peak_rss_KiB")
        }
        for mode in ("before", "after", "compact")
    }
    summary = {
        "schema_version": "query-audit-benchmark/1",
        "revisions": revisions,
        "harness": pin(Path(__file__).resolve()),
        "query": pin(args.query.resolve()),
        "snapshot": pin(args.snapshot.resolve()),
        "raw_manifest": pin(manifest_path),
        "raw_verified": [pin(f) for f in raw_files],
        "python": sys.version,
        "platform": platform.platform(),
        "trials": rows,
        "medians": medians,
        "all_full_semantics_equal": True,
        "all_normalized_packages_equal": True,
        "normalization": [
            "runtime.started_at",
            "runtime.duration_seconds",
            "reproducibility.revision",
            *["reproducibility.source_files." + p for p in sorted(MODIFIED_SOURCE)],
        ],
        "limitations": [
            "Three trials per mode, one workload; not a statistical confidence interval.",
            "Fresh processes, shared OS cache; not cold disk or concurrent load testing.",
            "Parent parity parsing is excluded from measured child wall/RSS.",
            "A fresh supervisor isolates inherited parser RSS; supervisor startup is excluded.",
            "All 7490 attempts/7494 diagnostics retained. No search/pruning/cost/proof changes.",
        ],
    }
    (args.output_dir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps({"medians": medians, "full_parity": True}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
