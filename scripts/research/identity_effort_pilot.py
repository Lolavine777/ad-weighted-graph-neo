"""Run a non-DA User→acquired DA identity C-only pilot on full SEAMLESS.

The independent oracle checks one direct reset, its owner-bound activation and
membership; it does not call AWG's cost compiler or candidate generator. Native
API/CLI/batch and ordered replay remain the implementation under test.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

from scripts.exposure import build_request, inventory_exposure
from scripts.research.compare_identity_goals import identity_goal_inputs
from src.data.manifest import load_manifest, verify_manifest
from src.engine.batch import _atomic_json, execution_source_pins, run_source_goal_batch
from src.engine.graph import EngineGraph
from src.engine.query import run_attack_query
from src.engine.query_cli import wire
from src.engine.ranking.reset_effort import PROFILE_ID, bind_reset_effort, load_reset_effort_profile
from src.engine.semantics.credentials import replay_path

ROOT = Path(__file__).resolve().parents[2]


def _sha(raw):
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _oracle(result, graph, source, owner, context, group):
    expected = [
        ("scenario_reset_password", source, source, owner),
        ("acquire_reset_identity", owner, owner, context),
        ("propagate_group_entitlement", owner, owner, group),
    ]
    assert result.paths, "The selected direct reset case must produce a witness"
    ledgers = []
    for index, path in enumerate(result.paths, 1):
        replay_path(path, graph)
        requests = [s.result.request for s in path.transition_history]
        assert [(r.technique_id, r.actor, r.source, r.target) for r in requests] == expected
        # Expected active-work union is two owner/context-specific operations.
        # Cost1 is the chosen ordinal reset rubric, activation0, passive member0.
        operations = {
            (r.technique_id, r.actor, r.source, r.target, context)
            for r in requests
            if r.technique_id != "propagate_group_entitlement"
        }
        independent_C = sum(1 if op[0] == "scenario_reset_password" else 0 for op in operations)
        assert independent_C == 1 and len(operations) == 2
        cid = f"generated_{index:04d}"
        candidate = result.rating_coverage["candidates"][cid]
        units = candidate["effort"]["units"]
        assert len(units) == 2 and sorted(u["cost"] for u in units.values()) == [0, 1]
        for unit in units.values():
            key = unit["rating_audit"]["lookup_key"]
            assert key["auth_context"] == context
            assert (
                unit["cost"]
                == {"scenario_reset_password": 1, "acquire_reset_identity": 0}[key["technique"]]
            )
        assert sum(u["cost"] for u in units.values()) == independent_C
        summary = result.rating_coverage["candidate_summaries"][cid]
        assert summary["c_complete"] and not summary["p_complete"] and not summary["i_complete"]
        ledgers.append({"candidate_id": cid, "expected_C": independent_C, "native_units": units})
    assert result.min_effort["minimum_effort_value"] == 1
    assert result.min_effort["associated_likelihood_interval"] is None
    assert result.min_effort["associated_impact"] is None
    return ledgers


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--raw-dir", type=Path, default=ROOT / "data/raw/SEAMLESS")
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    args.output_dir.mkdir(parents=True, exist_ok=False)
    errors = verify_manifest(
        args.raw_dir, load_manifest(ROOT / "data/samples/manifests/seamless-raw-v1.json")
    )
    if errors:
        raise ValueError(f"Raw manifest mismatch: {errors}")
    raw = args.snapshot.read_bytes()
    graph = EngineGraph.from_snapshot(raw.decode())
    query, edge, count = identity_goal_inputs(graph)
    query["target_goal"] = {"target": query["target"], "kind": "usable_identity_entitlement"}
    source, owner = edge["source"], edge["target"]
    context, group = query["authentication_context"], query["target"]
    assert (owner, context) not in map(tuple, query["initial_state"].get("usable_identity", []))
    stages = {}
    start = time.perf_counter()
    before = run_attack_query(query, graph)
    stages["unrated_native_query"] = time.perf_counter() - start
    bound = bind_reset_effort(query, graph, load_reset_effort_profile(PROFILE_ID))
    _atomic_json(args.output_dir / "query-unrated.json", query)
    _atomic_json(args.output_dir / "query-C-only.json", bound)
    _atomic_json(args.output_dir / "assumptions.json", query["assumptions"])
    start = time.perf_counter()
    after = run_attack_query(bound, graph)
    stages["C_only_native_query"] = time.perf_counter() - start
    assert wire(before.paths) == wire(after.paths)
    assert before.expansions == after.expansions
    ledgers = _oracle(after, graph, source, owner, context, group)
    inventory = inventory_exposure(graph)
    request, selection = build_request(
        graph,
        inventory,
        source_ids=[source],
        authentication_context=context,
        user_profile="user_usable_identity",
        max_sources=0,
        max_targets=0,
        evaluation_mode="scenario",
        assumptions=query["assumptions"],
        budget=query["budget"],
    )
    da_goal = next(
        t["goal"]["goal_id"] for t in inventory["targets"] if t["goal"]["target_node_id"] == group
    )
    request["target_goal_ids"] = [da_goal]
    _atomic_json(args.output_dir / "batch-request.json", request)
    start = time.perf_counter()
    batch = run_source_goal_batch(
        request,
        graph,
        allowed_techniques=query["allowed_techniques"],
        effort_profile=PROFILE_ID,
        checkpoint=args.output_dir / "checkpoint.json",
    )
    stages["one_source_one_goal_batch"] = time.perf_counter() - start
    _atomic_json(args.output_dir / "batch-result.json", batch.to_dict())
    assert batch.summary["effort_rated_cells"] == batch.summary["successful_cells"] == 1
    assert batch.summary["likelihood_rated_cells"] == 0
    trace = next(iter(batch.reproducibility["inputs"]["public_queries"].values()))
    exact_query = trace["query"]
    qp, op = args.output_dir / "batch-public-query.json", args.output_dir / "native-cli.json"
    _atomic_json(qp, exact_query)
    exact = run_attack_query(exact_query, graph)
    _oracle(exact, graph, source, owner, context, group)
    command = [
        sys.executable,
        "-m",
        "src.engine",
        "query",
        "--snapshot",
        str(args.snapshot),
        "--query",
        str(qp),
        "--label",
        "seamless",
        "--output",
        str(op),
    ]
    for prerequisite in sorted(args.raw_dir.glob("*.json")):
        command += ["--prerequisite", str(prerequisite)]
    start = time.perf_counter()
    with (args.output_dir / "native-cli.log").open("w") as log:
        subprocess.run(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, check=True)
    stages["exact_batch_query_CLI"] = time.perf_counter() - start
    semantic = json.loads(op.read_text())["semantic"]
    expected_candidates = [
        {"candidate_id": f"generated_{i:04d}", **wire(path)}
        for i, path in enumerate(exact.paths, 1)
    ]
    assert expected_candidates == semantic["candidates"]
    assert wire(exact.min_effort) == semantic["min_effort"]
    assert wire(exact.rating_coverage) == semantic["rating_coverage"]
    assert wire(exact.ranking_result) == semantic["ranking_result"]
    summary = {
        "version": "identity-effort-pilot/1.0",
        "revision": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        "snapshot_sha256": _sha(raw),
        "source_pins": execution_source_pins(),
        "orchestration_pins": {
            p: _sha((ROOT / p).read_bytes())
            for p in (
                "scripts/research/compare_identity_goals.py",
                "scripts/research/identity_effort_pilot.py",
            )
        },
        "source": {
            "node": source,
            "label": graph.node(source)["label"],
            "initial_state": query["initial_state"],
            "membership_to_DA": False,
        },
        "acquired_owner": {"node": owner, "label": graph.node(owner)["label"]},
        "context": context,
        "group": group,
        "direct_reset_edge": edge,
        "eligible_pairs": count,
        "before": {"paths": len(before.paths), "min_effort": wire(before.min_effort)},
        "after": {
            "paths": len(after.paths),
            "expansions": after.expansions,
            "complete": after.complete,
            "truncated": after.truncated,
            "min_effort": wire(after.min_effort),
            "minimum_proven_over_scope": after.is_minimum_proven_over_scope,
            "ledgers": ledgers,
        },
        "batch_selection": {
            "manifest_goals": selection["selected_targets"],
            "executed_goals": 1,
            "goals_outside_pilot": selection["selected_targets"] - 1,
        },
        "batch_summary": batch.summary,
        "CLI_command": command,
        "API_CLI_exact_semantic_parity": True,
        "before_after_full_path_parity": True,
        "stage_seconds": stages,
        "limitations": [
            "One selected direct GenericAll reset scenario; not whole-domain coverage.",
            "Source is initially usable at the declared Computer; not password-only.",
            "Seven runtime gates are assumptions, not observed success.",
            "Ordinal C-only scope extension, not the old reviewer's new-scope approval.",
            "P/I remain unrated. No timing improvement or globally optimal AD claim.",
        ],
    }
    summary["artifacts"] = [
        {"path": str(p), "bytes": p.stat().st_size, "sha256": _sha(p.read_bytes())}
        for p in sorted(args.output_dir.iterdir())
        if p.is_file()
    ]
    _atomic_json(args.output_dir / "summary.json", summary)
    print(
        json.dumps(
            {
                "source": source,
                "owner": owner,
                "C": 1,
                "paths": len(after.paths),
                "complete": after.complete,
                "native_scope_minimum": after.is_minimum_proven_over_scope,
                "API_CLI_exact_semantic_parity": True,
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
