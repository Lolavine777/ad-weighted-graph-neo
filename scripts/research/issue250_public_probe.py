"""Reproduce #250 public CLI/API integration; save only sanitized evidence to Git.

Numeric synthetic cases are algorithm tests, never numeric production acceptance.
Full private CLI artifacts remain under ignored reports/generated/issue250/.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import subprocess
import sys
from pathlib import Path

from scripts.research.asrep_inputs import seamless_inputs
from scripts.research.week4_acceptance_runner import execution_metadata
from src.engine import materialize_query
from src.engine.query_cli import canonical_json, wire
from src.engine.ranking.orchestration import generate_and_evaluate_attack_paths
from src.engine.ranking.resolution_service import canonical_digest
from src.parser import IdentityNormalizer, ManifestRawDataLoader
from src.parser.adapters import adapt_bloodhound_v3_records
from src.parser.cli import load_time_policy
from src.parser.snapshot_facts import serialize_snapshot

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests/fixtures/rating_resolution"
GRAPH = ROOT / "tests/fixtures/attack_scenarios/graphs/two-routes.json"


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(
        (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")
    )


def envelope(data):
    return {"version": "1.0.0", "sha256": canonical_digest(data), "data": data}


def frozen_inputs(raw_dir, revision):
    """Consume the frozen #243 specification without changing its historical oracle."""
    spec = read(ROOT / "docs/research/scenarios/week4-seamless-v1.json")
    graph, base, _, _ = seamless_inputs(raw_dir, revision)
    loader = ManifestRawDataLoader(
        ROOT / "data/samples/manifests/seamless-raw-v1.json",
        time_policy=load_time_policy(ROOT / "tests/fixtures/ranking/seamless_time_policy.json"),
    )
    records = IdentityNormalizer().normalize_records(
        adapt_bloodhound_v3_records(loader.load(raw_dir))
    )
    ids = {}
    for alias, locator in spec["locators"].items():
        values = {
            record.id
            for record in records
            for source in record.raw_representations or (record.raw,)
            if source.provenance.get("record_locator") == locator
        }
        if len(values) != 1:
            raise ValueError("Frozen locator must resolve uniquely")
        ids[alias] = values.pop()
    query = {
        **base,
        "initial_actor": ids["X"],
        "source_foothold": ids["X"],
        "authentication_context": ids["X"],
        "allowed_techniques": spec["allowed_techniques"],
        "budget": spec["budget"],
        "evaluation_mode": spec["evaluation_mode"],
        "scenario_reference": spec["scenario_id"],
        "initial_state": {
            "control": [],
            "known_identity": [ids["V_A"]],
            "asrep_request_capability": [[ids["X"], ids["X"]]],
        },
        "assumptions": [],
    }
    for predicate, subject, target in spec["assumptions"]:
        metadata = {"declared_by": spec["declared_by"], "authentication_context": ids["X"]}
        if predicate == "recovery_success":
            metadata.update(spec["recovery_metadata"])
        query["assumptions"].append(
            {
                "predicate": predicate,
                "subject": ids[subject],
                "target": ids[target],
                "value": True,
                "scope": spec["scenario_id"],
                "rationale": "Explicit conditional prediction outcome",
                "provenance_reference": "scenario://week4-seamless-v1/explicit-outcomes",
                "assumption_metadata": metadata,
            }
        )
    return graph, query, spec


def config_for_frozen(query, graph, spec):
    return {
        "version": "public-rating-resolution/1.0.0",
        "mode": "automatic",
        "policy": "production",
        "scope": {
            "query_id": "issue250-frozen243-public",
            "scenario_id": spec["scenario_id"],
            "scenario_version": "1.0.0",
            "snapshot_id": spec["snapshot_id"],
            "foothold_node_id": query["initial_actor"],
            "work_boundary": "intra_forest",
            "horizon": spec["recovery_metadata"]["horizon"],
            "active_work_budget": query["budget"]["max_steps"],
            "evaluation_mode": spec["evaluation_mode"],
            "recovery_metadata": spec["recovery_metadata"],
            "target_goal": {
                "goal_id": "admin_control(C0)",
                "target_asset_id": query["target"],
                "success_event": "admin_execution_on_C",
            },
        },
        "registries": {
            "effort": envelope(
                read(ROOT / "docs/research/ratings/week4/reviewed-work-unit-classes.json")[
                    "classes"
                ]
            ),
            "impact": envelope(
                read(ROOT / "docs/research/ratings/week4/impact-equivalence-registry.json")
            ),
            "impact_source": envelope(
                read(ROOT / "docs/research/ratings/week3-closeout/reviewed-release.json")
            ),
        },
    }


def summary(semantic):
    coverage = semantic.get("rating_coverage") or {}
    ranking = semantic.get("ranking_result") or {}
    assessed = {
        **ranking.get("eligible_candidates", {}),
        **{
            cid: item["assessment"]
            for cid, item in ranking.get("diagnostics", {}).items()
            if "assessment" in item
        },
    }
    return {
        "status": semantic["status"],
        "paths": len(semantic["candidates"]),
        "checkpoint_reached": semantic["checkpoint_reached"],
        "final_goal_reached": semantic["final_goal_reached"],
        "programs": [
            [step["result"]["request"]["technique_id"] for step in path["transition_history"]]
            for path in semantic["candidates"]
        ],
        "numeric_requests": coverage.get("numeric_requests"),
        "aggregate_summary": coverage.get("aggregate_summary"),
        "passive_steps": coverage.get("binding", {}).get("passive_steps"),
        "canonical_work_units": coverage.get("binding", {}).get("canonical_work_units"),
        "efforts": {cid: item.get("effort") for cid, item in assessed.items()},
        "likelihoods": {cid: item.get("likelihood_interval") for cid, item in assessed.items()},
        "pareto_frontier": ranking.get("pareto_frontier"),
        "minimum_effort": (semantic.get("min_effort") or {}).get("minimum_effort_value"),
        "minimum_proven": semantic["engine_reported_guarantees"]["is_minimum_proven_over_scope"],
        "gap_codes": [
            {
                "dimension": gap["dimension"],
                "disposition": gap["disposition"],
                "reason_code": gap["reason_code"],
            }
            for gap in coverage.get("unresolved_gaps", [])
        ],
    }


def assert_frozen_semantics(semantic, expected):
    """Check every frozen semantic field without publishing private identities."""
    actual = summary(semantic)
    for key in ("status", "final_goal_reached", "checkpoint_reached", "programs"):
        if key in expected:
            assert actual[key] == expected[key], key
    if "path_count" in expected:
        assert actual["paths"] == expected["path_count"]
    for key in ("truncated", "truncation_reason"):
        if key in expected:
            assert semantic[key] == expected[key], key

    def projected(state):
        return [
            label
            for field, label in (
                ("asrep_material", "material"),
                ("recovered_secret", "secret"),
                ("usable_identity", "usable"),
                ("admin_control", "admin"),
            )
            if state[field]
        ]

    if "projected_states" in expected:
        history = semantic["candidates"][0]["transition_history"]
        assert [projected(history[0]["result"]["before"])] + [
            projected(step["result"]["after"]) for step in history
        ] == expected["projected_states"]
    if "maximum_successful_prefix_steps" in expected:
        states = [semantic["materialized"]["initial_attack_state"]] + [
            attempt["after"] for attempt in semantic["attempts"]
        ]
        assert (
            max(len(projected(state)) for state in states)
            == expected["maximum_successful_prefix_steps"]
        )
    if "rejected_assumption_reasons" in expected:
        assert (
            sorted({r["reason"] for r in semantic["materialized"]["rejected_assumptions"]})
            == expected["rejected_assumption_reasons"]
        )


def run_case(name, query, config, graph_path, output_dir, *, label="synthetic", expected_exit=0):
    query_path, config_path = output_dir / f"{name}.query.json", output_dir / f"{name}.config.json"
    save(query_path, query)
    save(config_path, config)
    command = [
        sys.executable,
        "-m",
        "src.engine.query_cli",
        "--query",
        str(query_path),
        "--rating-resolution",
        str(config_path),
        "--snapshot" if label == "seamless" else "--graph",
        str(graph_path),
        "--label",
        label,
    ]
    if label == "seamless":
        command += ["--prerequisite", str(ROOT / "data/samples/manifests/seamless-raw-v1.json")]
    outputs = []
    codes = []
    for index in (1, 2):
        destination = output_dir / f"{name}.run{index}.json"
        process = subprocess.run(
            command + ["--output", str(destination)],
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        codes.append(process.returncode)
        if process.returncode != expected_exit:
            raise ValueError(
                f"{name}: unexpected CLI exit {process.returncode}; details kept local"
            )
        if expected_exit:
            (output_dir / f"{name}.stderr.txt").write_text(process.stderr, encoding="utf-8")
            if destination.exists():
                raise ValueError("Invalid input unexpectedly produced an output artifact")
            continue
        output = read(destination)
        output.pop("runtime")  # the only declared volatile metadata block
        outputs.append(output)
    if outputs and outputs[0] != outputs[1]:
        raise ValueError(f"{name}: two-run determinism mismatch")
    result = {
        "case": name,
        "command": subprocess.list2cmdline(command),
        "exit_codes": codes,
        "status": "PASS",
        "evidence_class": "actual_private_dataset_conditional_prediction"
        if label == "seamless"
        else "synthetic_test_only",
        "two_runs_equal": bool(outputs),
    }
    if outputs:
        result["actual"] = summary(outputs[0]["semantic"])
    else:
        result["actual"] = {"invalid_input_diagnostic": True, "output_artifact": False}
    return result, outputs[0]["semantic"] if outputs else None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seamless-raw", type=Path)
    args = parser.parse_args()
    execution = execution_metadata(None)
    if execution["source"]["dirty_pinned_files"]:
        raise ValueError("Source-provenance guard: commit source before running the probe")
    pins = {}
    for path in [
        *FIXTURES.glob("*.json"),
        ROOT / "docs/research/public-rating-coverage.schema.json",
        Path(__file__),
        ROOT / "tests/test_public_rating_integration.py",
    ]:
        name = path.relative_to(ROOT).as_posix()
        if subprocess.check_output(["git", "show", f"HEAD:{name}"], cwd=ROOT) != path.read_bytes():
            raise ValueError("Source-provenance guard: fixture bytes differ from committed source")
        pins[name] = "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()
    local = ROOT / "reports/generated/issue250"
    query, full = read(FIXTURES / "query.json"), read(FIXTURES / "complete.json")
    variants = {
        "complete": full,
        "shared": read(FIXTURES / "complete-shared.json"),
        "missing": read(FIXTURES / "missing.json"),
    }
    effort = copy.deepcopy(full)
    effort["registries"] = {"effort": effort["registries"]["effort"]}
    variants["effort_only"] = effort
    context = copy.deepcopy(full)
    records = context["registries"]["likelihood"]["data"]
    records[0]["horizon"] = "72h"
    context["registries"]["likelihood"] = envelope(records)
    variants["context_refused"] = context
    pending = copy.deepcopy(effort)
    pending["policy"] = "production"
    classes = pending["registries"]["effort"]["data"]
    for record in classes:
        record.update(review_status="pending_b_review", basis_category="scenario_assumption")
    pending["registries"]["effort"] = envelope(classes)
    variants["pending_production"] = pending
    synthetic = copy.deepcopy(full)
    synthetic["policy"] = "production"
    variants["synthetic_production_refused"] = synthetic
    invalid = copy.deepcopy(full)
    invalid["registries"]["effort"]["sha256"] = "sha256:" + "0" * 64
    variants["integrity_error"] = invalid
    results = []
    for name, config in variants.items():
        result, semantic = run_case(
            name, query, config, GRAPH, local, expected_exit=1 if name == "integrity_error" else 0
        )
        if name in ("complete", "shared", "effort_only"):
            assert result["actual"]["minimum_effort"] == (2 if name == "shared" else 1)
        if semantic:
            from src.engine.graph import EngineGraph

            graph = EngineGraph.from_canonical(read(GRAPH))
            materialized = materialize_query({**query, "rating_resolution": config}, graph)
            api = materialized.run(graph)
            assert wire(api.ranking_result) == semantic["ranking_result"]
            orchestration = generate_and_evaluate_attack_paths(
                {},
                graph.to_canonical(),
                actor=materialized.initial_actor,
                initial_state=materialized.initial_attack_state,
                runtime_context=materialized.runtime_context,
                budget=materialized.budget,
                catalog=materialized.catalog,
                scenario_reference=materialized.scenario_reference,
                success_state_predicate=materialized.success_state_predicate,
                semantic_goal=materialized.semantic_goal,
                rating_resolution=config,
            )
            assert orchestration["roundtrip_result"] == semantic["ranking_result"]
            result["api_cli_orchestration_equal"] = True
        results.append(result)
    if args.seamless_raw is not None:
        revision = execution["source"]["revision"]
        graph, query, spec = frozen_inputs(args.seamless_raw, revision)
        snapshot_path = local / "frozen243.snapshot.json"
        snapshot_path.parent.mkdir(parents=True, exist_ok=True)
        snapshot_path.write_text(
            serialize_snapshot(graph.to_canonical(), graph.snapshot_facts), encoding="utf-8"
        )
        for name in (
            "assumed",
            "raw",
            "missing_recovery",
            "asset_veto",
            "off",
            "no_request",
            "step_cap",
        ):
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
            config = config_for_frozen(variant, graph, spec)
            result, semantic = run_case(
                "frozen243_" + name, variant, config, snapshot_path, local, label="seamless"
            )
            expected = spec["expected"][name]
            assert_frozen_semantics(semantic, expected)
            if name == "assumed":
                assert result["actual"]["numeric_requests"]["P"] == {"required": 4, "rated": 0}
            result["frozen_semantic_expectations"] = "PASS"
            results.append(result)
    else:
        results.append(
            {
                "case": "frozen243",
                "status": "NOT EXECUTED/BLOCKED",
                "reason": "manifest-verified private raw prerequisite not supplied",
            }
        )
    report = {
        "schema_version": "issue250-public-probe/1.0.0",
        "execution": execution,
        "fixture_canonical_digests": pins,
        "cases": results,
        "remote_ci": "NOT EXECUTED; local evidence is not remote CI PASS",
        "numeric_acceptance": "No production catalogs/equivalence accepted by this probe",
    }
    save(args.output, report)
    print(
        canonical_json(
            {
                "revision": execution["source"]["revision"],
                "cases": [{"case": r["case"], "status": r["status"]} for r in results],
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
