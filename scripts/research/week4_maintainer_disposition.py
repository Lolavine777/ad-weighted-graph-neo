"""Consume exact A maintainer dispositions through the existing public automatic flow."""

from __future__ import annotations

import argparse
import copy
import hashlib
import subprocess
from pathlib import Path

from scripts.research.issue250_public_probe import (
    ROOT,
    assert_frozen_semantics,
    config_for_frozen,
    envelope,
    frozen_inputs,
    read,
    run_case,
    save,
)
from scripts.research.week4_acceptance_runner import execution_metadata
from src.engine import materialize_query, run_attack_query
from src.engine.query_cli import wire
from src.engine.ranking.orchestration import generate_and_evaluate_attack_paths
from src.parser.snapshot_facts import serialize_snapshot

PACKET = ROOT / "docs/research/ratings/week4-maintainer-v1/frozen243-disposition.json"


def frozen_case(raw_dir: Path, revision: str):
    graph, query, spec = frozen_inputs(raw_dir, revision)
    packet = read(PACKET)
    config = config_for_frozen(query, graph, spec)
    config["version"] = "public-rating-resolution/1.1.0"
    config["registries"]["effort"] = envelope(packet["effort"])
    config["registries"]["impact"] = envelope(packet["impact"])
    query["rating_resolution"] = config
    return graph, query, spec


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    execution = execution_metadata(None)
    if execution["source"]["dirty_pinned_files"]:
        raise ValueError("Source-provenance guard: commit source before running the probe")
    pins = {}
    for path in (
        PACKET,
        Path(__file__),
        ROOT / "tests/test_week4_maintainer_disposition.py",
        ROOT / "scripts/research/issue250_public_probe.py",
        ROOT / "docs/research/scenarios/week4-seamless-v1.json",
        ROOT / "docs/research/ratings/week4/reviewed-work-unit-classes.md",
        ROOT / "docs/research/ratings/week3-closeout/reviewed-release.json",
    ):
        name = path.relative_to(ROOT).as_posix()
        if subprocess.check_output(["git", "show", f"HEAD:{name}"], cwd=ROOT) != path.read_bytes():
            raise ValueError(
                "Source-provenance guard: packet/consumer differs from committed source"
            )
        pins[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    revision = execution["source"]["revision"]
    graph, query, spec = frozen_case(args.raw_dir, revision)
    local = ROOT / "reports/generated/week4-maintainer-disposition"
    local.mkdir(parents=True, exist_ok=True)
    snapshot = local / "frozen.snapshot.json"
    snapshot.write_text(serialize_snapshot(graph.to_canonical(), graph.snapshot_facts))
    results = []
    for name in spec["expected"]:
        variant = copy.deepcopy(query)
        if name == "raw":
            variant["assumptions"] = []
        elif name == "missing_recovery":
            variant["assumptions"] = [
                f for f in variant["assumptions"] if f["predicate"] != "recovery_success"
            ]
        elif name == "asset_veto":
            fact = next(f for f in variant["assumptions"] if f["predicate"] == "admin_channel")
            variant["runtime_facts"] = [{**fact, "value": False, "origin": "observed_evidence"}]
        elif name == "off":
            variant["allowed_techniques"] = ["obtain_admin_execution_on_host"]
        elif name == "no_request":
            variant["initial_state"]["asrep_request_capability"] = []
        elif name == "step_cap":
            variant["budget"]["max_steps"] = 3
            variant["rating_resolution"]["scope"]["active_work_budget"] = 3
        cli_query = copy.deepcopy(variant)
        cli_config = cli_query.pop("rating_resolution")
        result, semantic = run_case(name, cli_query, cli_config, snapshot, local, label="seamless")
        assert_frozen_semantics(semantic, spec["expected"][name])
        api = run_attack_query(variant, graph)
        assert api.rating_coverage == semantic["rating_coverage"]
        assert wire(api.ranking_result) == semantic["ranking_result"]
        if name == "assumed":
            assert (
                result["actual"]["numeric_requests"] == read(PACKET)["oracle"]["numeric_requests"]
            )
            assert result["actual"]["minimum_effort"] == 3
            assert not result["actual"]["pareto_frontier"]
            candidate = api.rating_coverage["candidates"]["generated_0001"]
            costs = {
                unit["rating_audit"]["lookup_key"]["technique"]: unit["cost"]
                for unit in candidate["effort"]["units"].values()
            }
            oracle = read(PACKET)["oracle"]
            assert [costs[tech] for tech in oracle["program"]] == oracle["unit_costs"]
            assert candidate["impact"]["consequence_rating"] == oracle["impact"]
            result["actual"]["unit_costs"] = oracle["unit_costs"]
            result["actual"]["impact"] = oracle["impact"]
            materialized = materialize_query(variant, graph)
            other = generate_and_evaluate_attack_paths(
                {},
                graph.to_canonical(),
                snapshot_facts=graph.snapshot_facts,
                actor=materialized.initial_actor,
                initial_state=materialized.initial_attack_state,
                runtime_context=materialized.runtime_context,
                budget=materialized.budget,
                catalog=materialized.catalog,
                scenario_reference=materialized.scenario_reference,
                success_state_predicate=materialized.success_state_predicate,
                semantic_goal=materialized.semantic_goal,
                rating_resolution=variant["rating_resolution"],
            )
            assert other["roundtrip_result"] == semantic["ranking_result"]
        result["frozen_semantic_expectations"] = "PASS"
        result["api_cli_equal"] = True
        results.append(result)
    save(
        args.output,
        {
            "revision": revision,
            "execution": execution,
            "packet_consumer_file_sha256": pins,
            "role": read(PACKET)["role"],
            "independent_b_review": False,
            "packet_sha256": envelope(read(PACKET))["sha256"],
            "cases": results,
        },
    )
    print(f"PASS: {len(results)} frozen cases, each CLI twice; C=4/4, P=0/4, I=1/1, C=3")


if __name__ == "__main__":
    main()
