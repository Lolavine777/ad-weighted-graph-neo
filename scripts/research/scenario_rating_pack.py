"""Verify pending #260 artifacts using merged #258 public automatic resolution.

Review simulation only changes review gates on explicit copies.
It never grants B approval, modifies canonical pending records, or replaces native providers.
Subprocess reproduction may export gate simulations to a new temporary file.
Equal AdminTo numbers are synthetic; Source A proposes a scoped historical transfer.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from fractions import Fraction
from pathlib import Path
from typing import Any

from src.engine import run_attack_query
from src.engine.ranking.resolution_service import canonical_digest

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = Path("docs/research/ratings/scenario-basis-v1")
PENDING = "proposed_pending_b_review"
NEO_SOURCE_MANIFEST = Path("reports/neo/source-manifest.json")
HISTORICAL_SOURCE_MANIFEST = PACKAGE / "source-manifest-v14.json"
HISTORICAL_SOURCE_SHA256 = "sha256:da0896ece92187c1458b000179a5fc47a0d38a8352ed91117257fb9049bf1311"
HISTORICAL_SOURCE_MANIFESTS = {
    HISTORICAL_SOURCE_MANIFEST.as_posix(): HISTORICAL_SOURCE_SHA256,
    "docs/research/ratings/likelihood-v1/source-manifest-v14.json": (
        "sha256:ba3cad7abec7a5f9edf800d81cfa591385094cfa9856971bad67874f02311597"
    ),
}


def _require(condition: bool, detail: str) -> None:
    if not condition:
        raise ValueError(detail)


def _read(root: Path, path: Path | str) -> dict[str, Any]:
    return json.loads((root / path).read_text(encoding="utf-8"))


def load_scenario_pack(root: Path = ROOT) -> dict[str, Any]:
    return _read(root, PACKAGE / "scenario-rating-pack.json")


def load_oracles(root: Path = ROOT) -> dict[str, Any]:
    return _read(root, PACKAGE / "oracles.json")


def load_coverage_matrix(root: Path = ROOT) -> dict[str, Any]:
    return _read(root, PACKAGE / "coverage-matrix.json")


def _envelope(data: Any) -> dict[str, Any]:
    return {"version": "1.0.0", "sha256": canonical_digest(data), "data": data}


def proposed_likelihood_records(root: Path = ROOT) -> list[dict[str, Any]]:
    """Project metadata-rich pending P proposals to the unchanged native record API."""
    records = []
    for proposal in load_scenario_pack(root)["likelihood_basis"]["records"]:
        record = {
            k: copy.deepcopy(proposal[k])
            for k in (
                "scenario_id",
                "scenario_version",
                "snapshot_id",
                "foothold_node_id",
                "ordered_work_prefix",
                "outcome_work_unit_id",
                "outcome_technique",
                "actor_id",
                "source_id",
                "target_id",
                "method",
                "budget",
                "horizon",
                "boundary",
                "scope",
                "auth_context",
                "resource_context",
                "policy_id",
                "review_status",
                "rationale",
                "review_reference",
                "retry_policy",
            )
        }
        record.update(
            version="1.0.0",
            disposition="unrated",
            lower=proposal["proposed_interval"][0],
            upper=proposal["proposed_interval"][1],
            basis_category=proposal["evidence_class"],
            provenance_digest=canonical_digest(proposal),
            applicable_queries=["query-scenario-pack-v1"],
        )
        records.append(record)
    return records


def proposed_query(root: Path = ROOT) -> dict[str, Any]:
    """Publish a semantic query and native registry envelopes, never path packets."""
    pack = load_scenario_pack(root)
    profile = pack["scenario_profile"]
    actor, host = profile["foothold_node_id"], profile["target_asset_id"]
    goal = {k: v for k, v in profile["target_goal"].items() if k != "required_predicates"}
    scope = {
        k: profile[k]
        for k in (
            "scenario_id",
            "scenario_version",
            "snapshot_id",
            "foothold_node_id",
            "work_boundary",
            "evaluation_mode",
            "retry_policy",
        )
    }
    scope.update(
        query_id="query-scenario-pack-v1",
        target_goal=goal,
        horizon=profile["operational_horizon"],
        active_work_budget=profile["active_work_budget"],
    )
    data = {
        "effort": pack["effort_basis"]["classes"],
        "likelihood": proposed_likelihood_records(root),
        "impact": {
            "registry_id": pack["pack_id"],
            "version": "1.0.0",
            "mappings": pack["impact_basis"]["mappings"],
        },
        "impact_source": pack["impact_basis"]["source_packet"],
        "work": pack["work_basis"]["rules"],
    }
    return {
        "initial_actor": actor,
        "initial_state": {"control": [actor]},
        "target": host,
        "target_goal": {"target": host, "required_state": {"admin_control": [host]}},
        "runtime_facts": profile["assumptions_ledger"]["declared_assumptions"],
        "scenario_reference": profile["scenario_id"],
        "evaluation_mode": profile["evaluation_mode"],
        "allowed_techniques": ["propagate_group_entitlement", "obtain_admin_execution_on_host"],
        "budget": {
            "max_paths": 100,
            "max_steps": profile["active_work_budget"],
            "max_expansions": 1000,
        },
        "rating_resolution": {
            "version": "public-rating-resolution/1.1.0",
            "mode": "automatic",
            "policy": "synthetic_test_only",
            "scope": scope,
            "registries": {role: _envelope(value) for role, value in data.items()},
        },
    }


def build_two_routes_query(
    root: Path = ROOT,
    *,
    simulate_review: bool = False,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Load the published pending query; optionally simulate review on test copies.

    Synthetic policy is mandatory. Only provider review gates change; numeric
    values, work identities, applicability and native implementation stay exact.
    """
    query = _read(root, PACKAGE / "automatic-query.json")
    if simulate_review:
        regs = query["rating_resolution"]["registries"]
        for role in ("effort", "likelihood"):
            for record in regs[role]["data"]:
                record["review_status"] = "accepted"
                record["disposition"] = "rated"
        for mapping in regs["impact"]["data"]["mappings"]:
            mapping["status"] = "reviewed"
        for role in ("effort", "likelihood", "impact"):
            regs[role] = _envelope(regs[role]["data"])
    profile = load_scenario_pack(root)["scenario_profile"]
    return query, _read(root, profile["graph_fixture"])


def build_source_a_query(
    root: Path = ROOT, *, simulate_review: bool = False
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Load frozen scenario proposals; simulate B gates only on explicit copies.

    The production provider policy, historical values, full prefix bindings and
    engine behavior stay unchanged. This does not authorize numeric activation.
    """
    query = _read(root, PACKAGE / "source-a-query.json")
    if simulate_review:
        regs = query["rating_resolution"]["registries"]
        for role in ("effort", "likelihood"):
            for record in regs[role]["data"]:
                record["review_status"] = "accepted"
                record["disposition"] = "rated"
        for mapping in regs["impact"]["data"]["mappings"]:
            mapping["status"] = "reviewed"
        for role in ("effort", "likelihood", "impact"):
            regs[role] = _envelope(regs[role]["data"])
    return query, _read(root, PACKAGE / "source-a-graph.json")


def write_source_manifest(root: Path = ROOT) -> Path:
    """Generate neo integrity pins without changing historical evidence or approval."""
    names = set()
    for name, expected in HISTORICAL_SOURCE_MANIFESTS.items():
        _require(
            "sha256:" + hashlib.sha256((root / name).read_bytes()).hexdigest() == expected,
            "historical source manifest pin mismatch",
        )
        names.update(_read(root, name)["source_pins"])
    packet = {
        "schema_version": "neo-source-manifest/1.0.0",
        "purpose": "Live neo source integrity only; no historical numeric adoption or approval",
        "historical_source_manifests": HISTORICAL_SOURCE_MANIFESTS,
        "source_pins": {
            name: "sha256:" + hashlib.sha256((root / name).read_bytes()).hexdigest()
            for name in sorted(names)
        },
    }
    destination = root / NEO_SOURCE_MANIFEST
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(packet, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return destination


def verify_package(root: Path = ROOT) -> dict[str, Any]:
    manifest = _read(root, PACKAGE / "source-manifest-v2.json")
    historical = _read(root, PACKAGE / "manifest.json")
    _require(manifest["files"] == historical["files"], "frozen package file pins changed")
    _require(
        set(manifest["source_pins"]) == set(historical["source_pins"]),
        "source pin coverage mismatch",
    )
    _require(
        manifest["historical_manifest_sha256"]
        == "sha256:" + hashlib.sha256((root / PACKAGE / "manifest.json").read_bytes()).hexdigest(),
        "historical manifest pin changed",
    )
    _require(
        set(manifest["files"])
        == {
            "scenario-rating-pack.json",
            "automatic-query.json",
            "oracles.json",
            "coverage-matrix.json",
            "README.md",
            "source-a-basis.json",
            "source-a-query.json",
            "source-a-graph.json",
            "source-a-oracles.json",
        },
        "manifest file coverage mismatch",
    )
    for name, expected in manifest["files"].items():
        actual = "sha256:" + hashlib.sha256((root / PACKAGE / name).read_bytes()).hexdigest()
        _require(actual == expected, f"file digest mismatch: {name}")
    from scripts.research.rating_source_successors import GOAL_SOURCE_FILES

    for version in (4, 5, 6, 7, 8, 9, 10, 11, 12, 13):
        previous = _read(root, PACKAGE / f"source-manifest-v{version}.json")
        _require(
            previous["previous_source_manifest_sha256"]
            == "sha256:"
            + hashlib.sha256(
                (root / PACKAGE / f"source-manifest-v{version - 1}.json").read_bytes()
            ).hexdigest(),
            "previous historical source manifest pin mismatch",
        )
    successor = _read(root, PACKAGE / "source-manifest-v14.json")
    _require(successor["schema_version"] == "1.13.0", "source successor version")
    _require(
        successor["historical_manifest_sha256"]
        == "sha256:"
        + hashlib.sha256((root / PACKAGE / "source-manifest-v2.json").read_bytes()).hexdigest(),
        "historical source manifest pin mismatch",
    )
    _require(
        successor["previous_source_manifest_sha256"]
        == "sha256:"
        + hashlib.sha256((root / PACKAGE / "source-manifest-v13.json").read_bytes()).hexdigest(),
        "previous source manifest pin mismatch",
    )
    required_sources = (
        set(manifest["source_pins"])
        | GOAL_SOURCE_FILES
        | {
            "src/engine/program_identity.py",
            "src/engine/top_k.py",
            "src/engine/query.py",
            "src/engine/query_cli.py",
            "src/engine/search.py",
        }
    )
    _require(set(successor["source_pins"]) == required_sources, "source pin coverage mismatch")
    _require(
        "sha256:" + hashlib.sha256((root / HISTORICAL_SOURCE_MANIFEST).read_bytes()).hexdigest()
        == HISTORICAL_SOURCE_SHA256,
        "historical source manifest pin mismatch",
    )
    live_manifest = _read(root, NEO_SOURCE_MANIFEST)
    _require(live_manifest["schema_version"] == "neo-source-manifest/1.0.0", "neo source version")
    _require(
        live_manifest["historical_source_manifests"] == HISTORICAL_SOURCE_MANIFESTS,
        "historical source baseline mismatch",
    )
    _require(required_sources <= set(live_manifest["source_pins"]), "neo source coverage mismatch")
    archived_source_drift = []
    for name in sorted(required_sources):
        expected = live_manifest["source_pins"][name]
        actual = "sha256:" + hashlib.sha256((root / name).read_bytes()).hexdigest()
        _require(actual == expected, f"authoritative source pin drift: {name}")
        if actual != successor["source_pins"][name]:
            archived_source_drift.append(name)
    pack = load_scenario_pack(root)
    _require(pack["status"] == PENDING, "package must remain pending B review")
    _require(not pack["governance"]["numeric_activation_permitted"], "unauthorized activation")
    query, _ = build_two_routes_query(root)
    _require(query == proposed_query(root), "published automatic query differs from proposals")
    for role in ("effort", "likelihood"):
        for record in query["rating_resolution"]["registries"][role]["data"]:
            _require(
                record["review_status"] in ("pending_b_review", PENDING),
                "published numeric record must remain pending",
            )
            _require(record["basis_category"] == "synthetic_test_only", "unjustified numeric basis")
    for mapping in pack["impact_basis"]["mappings"]:
        _require(mapping["status"] == PENDING, "published impact must remain pending")
        _require(
            mapping["applicability"]["goal_id"]
            == pack["scenario_profile"]["target_goal"]["goal_id"],
            "impact goal ID mismatch",
        )
        _require("required_predicates" not in mapping["applicability"], "legacy impact predicates")
    basis = _read(root, PACKAGE / "source-a-basis.json")
    source_query, _ = build_source_a_query(root)
    _require(basis["status"] == PENDING, "Source A basis must remain pending")
    _require(not basis["numeric_activation_permitted"], "Source A numeric activation forbidden")
    _require(source_query["rating_resolution"]["policy"] == "production", "Source A policy changed")
    for role in ("effort", "likelihood"):
        for record in source_query["rating_resolution"]["registries"][role]["data"]:
            _require(record["review_status"] == "pending_b_review", "Source A numeric gate changed")
            _require(record["basis_category"] == "scenario_assumption", "Source A basis changed")
    _require(
        source_query["rating_resolution"]["registries"]["impact"]["data"]["mappings"][0]["status"]
        == PENDING,
        "Source A impact gate changed",
    )
    _require(
        canonical_digest(basis)
        == _read(root, PACKAGE / "source-a-oracles.json")["basis_canonical_digest"],
        "Source A frozen basis changed",
    )
    return {
        "verified": True,
        "status": pack["status"],
        "files_verified": len(manifest["files"]),
        "source_pins_verified": len(successor["source_pins"]),
        "source_baseline": NEO_SOURCE_MANIFEST.as_posix(),
        "archived_source_drift": sorted(archived_source_drift),
    }


def run_scenario_probe(root: Path = ROOT) -> dict[str, Any]:
    """Run native automatic rating twice: pending refusal and synthetic review simulation."""
    verify_package(root)
    oracle = load_oracles(root)["generated_risk_comparison"]
    pending_query, graph = build_two_routes_query(root)
    pending = run_attack_query(pending_query, graph)
    _require(
        all(v["rated"] == 0 for v in pending.rating_coverage["numeric_requests"].values()),
        "pending numeric records activated",
    )
    query, _ = build_two_routes_query(root, simulate_review=True)
    result = run_attack_query(query, graph)
    _require(
        result.search_result.complete and len(result.search_result.paths) == 3,
        "complete three-path search required",
    )
    ranking = result.ranking_result
    _require(
        ranking["pareto_frontier"] == oracle["expected_nondominated"], "Pareto oracle mismatch"
    )
    min_effort = ranking["min_effort_to_da_baseline"]
    _require(
        min_effort["minimum_effort_value"] == oracle["minimum_effort_value"], "C minimum mismatch"
    )
    _require(min_effort["all_best_candidate_ids"] == oracle["min_effort_ties"], "C ties mismatch")
    _require(
        min_effort["best_candidate_id"] == oracle["min_effort_winner"], "stable C winner mismatch"
    )
    for path, program in zip(result.search_result.paths, oracle["expected_programs"], strict=True):
        _require(
            path.transition_history[-1].result.request.source
            == program["expected_terminal_source"],
            "semantic source oracle mismatch",
        )
        _require(
            [step.result.request.technique_id for step in path.transition_history]
            == program["passive_steps"] + program["active_steps"],
            "semantic sequence oracle mismatch",
        )
        actual = ranking["eligible_candidates"][program["generated_candidate_id"]]
        _require(actual["effort"] == program["expected_C"], "C oracle mismatch")
        _require(
            tuple(map(Fraction, actual["likelihood_interval"]))
            == tuple(map(Fraction, program["exact_path_interval"])),
            "P oracle mismatch",
        )
        _require(actual["consequence_rating"] == program["expected_I"], "I oracle mismatch")
    return {
        "status": "PASS",
        "numeric_approval": False,
        "basis": "synthetic_test_only",
        "review_simulation": True,
        "scenario_id": query["scenario_reference"],
        "paths_generated": 3,
        "numeric_requests": result.rating_coverage["numeric_requests"],
        "pending_numeric_requests": pending.rating_coverage["numeric_requests"],
        "min_effort_winner": min_effort["best_candidate_id"],
        "min_effort_ties": min_effort["all_best_candidate_ids"],
        "min_effort_value": min_effort["minimum_effort_value"],
        "pareto_frontier": ranking["pareto_frontier"],
        "dominated": [],
        "configuration_digest": result.rating_coverage["configuration_digest"],
        "registries": result.rating_coverage["registries"],
        "coverage_digest": canonical_digest(result.rating_coverage),
        "ranking_digest": canonical_digest(ranking),
        "providers": result.rating_coverage["providers_configured"],
        "assessments": {
            cid: {
                field: assessment[field]
                for field in ("effort", "likelihood_interval", "consequence_rating")
            }
            for cid, assessment in ranking["eligible_candidates"].items()
        },
    }


def run_source_a_probe(root: Path = ROOT) -> dict[str, Any]:
    """Check frozen witnesses by program identity after actor-composition expansion.

    The historical 24 programs and their numbers remain immutable expectations.
    Newly reachable programs must not inherit their full-history P evidence.
    """
    oracle = _read(root, PACKAGE / "source-a-oracles.json")
    basis = _read(root, PACKAGE / "source-a-basis.json")
    _require(canonical_digest(basis) == oracle["basis_canonical_digest"], "frozen basis changed")
    query, graph = build_source_a_query(root)
    pending = run_attack_query(query, graph)
    _require(
        all(v["rated"] == 0 for v in pending.rating_coverage["numeric_requests"].values()),
        "pending Source A transfer activated",
    )
    _require(
        not any("computer_actor_authenticated" in attempt.failed for attempt in pending.attempts),
        "Historical Source A lacks usable Computer identity; a new context requires new review",
    )
    query, graph = build_source_a_query(root, simulate_review=True)
    result = run_attack_query(query, graph)
    _require(result.search_result.complete, "bounded Source A search incomplete")
    ranking = result.ranking_result
    minimum = ranking["min_effort_to_da_baseline"]
    _require(minimum["minimum_effort_value"] == oracle["min_effort_value"], "Source A minimum")
    plan = _read(root, "docs/research/ratings/week3-closeout/semantic-bridge-plan.json")
    labels = {
        (b["technique_id"], b["actor"], b["source"], b["target"]): b["action_id"]
        for b in plan["sources"]["source_a"]["transition_action_bindings"]
    }
    current = {}
    for index, path in enumerate(result.paths, 1):
        sequence = tuple(
            labels[
                (
                    step.result.request.technique_id,
                    step.result.request.actor,
                    step.result.request.source,
                    step.result.request.target,
                )
            ]
            for step in path.transition_history
        )
        _require(sequence not in current, "Source A duplicate program")
        current[sequence] = f"generated_{index:04d}"
    historical_ids = {}
    for program in oracle["programs"]:
        sequence = tuple(program["generated_actions"])
        _require(sequence in current, "Source A historical program missing")
        cid = current[sequence]
        historical_ids[program["candidate_id"]] = cid
        assessment = ranking["eligible_candidates"].get(cid)
        if assessment is None:
            assessment = ranking["diagnostics"][cid]["assessment"]
        for actual, expected in (
            ("effort", "C"),
            ("likelihood_interval", "P"),
            ("consequence_rating", "I"),
        ):
            _require(assessment[actual] == program[expected], f"Source A {cid} {expected}")
    for cid in set(current.values()) - set(historical_ids.values()):
        _require(cid not in ranking["eligible_candidates"], "New history inherited numeric P")
        _require(
            ranking["diagnostics"][cid]["assessment"]["likelihood_interval"] is None,
            "New history inherited conditional P",
        )
    for dimension in ("C", "I"):
        _require(
            result.rating_coverage["numeric_requests"][dimension]
            == oracle["numeric_requests"][dimension],
            f"Source A {dimension} unique coverage mismatch",
        )
    _require(
        result.rating_coverage["numeric_requests"]["P"]["rated"]
        == oracle["numeric_requests"]["P"]["rated"],
        "Source A new conditional rating evidence",
    )
    _require(
        ranking["pareto_frontier"] == [historical_ids[c] for c in oracle["pareto_frontier"]],
        "Source A frontier mismatch",
    )
    _require(
        minimum["all_best_candidate_ids"] == [historical_ids[c] for c in oracle["min_effort_ties"]],
        "Source A ties mismatch",
    )
    return {
        "status": "PASS",
        "basis": "scenario_assumption",
        "numeric_approval": False,
        "review_simulation": True,
        "basis_canonical_digest": oracle["basis_canonical_digest"],
        "paths_generated": len(result.paths),
        "numeric_requests": result.rating_coverage["numeric_requests"],
        "pending_numeric_requests": pending.rating_coverage["numeric_requests"],
        "min_effort": minimum,
        "pareto_frontier": ranking["pareto_frontier"],
        "fully_rated_paths": len(ranking["eligible_candidates"]),
        "p_unrated_paths": sum(
            not row["p_complete"] for row in result.rating_coverage["candidate_summaries"].values()
        ),
        "historical_candidate_ids": historical_ids,
        "ranking_digest": canonical_digest(ranking),
        "coverage_digest": canonical_digest(result.rating_coverage),
    }


def verify_source_a_projection(raw_dir: Path, root: Path = ROOT) -> dict[str, Any]:
    """Rebuild from manifest-verified raw, verifying every induced node and edge."""
    from scripts.research.asrep_inputs import seamless_inputs

    expected = _read(root, PACKAGE / "source-a-graph.json")
    source, _, _, _ = seamless_inputs(raw_dir, expected["metadata"]["code_version"])
    plan = _read(root, "docs/research/ratings/week3-closeout/semantic-bridge-plan.json")
    ids = {
        binding[key]
        for binding in plan["sources"]["source_a"]["transition_action_bindings"]
        for key in ("actor", "source", "target")
    }
    actual = source.to_canonical()
    actual["nodes"] = [node for node in actual["nodes"] if node["id"] in ids]
    actual["edges"] = [
        edge for edge in actual["edges"] if edge["source"] in ids and edge["target"] in ids
    ]
    actual["assessments"] = []
    _require(actual == expected, "Source A induced projection differs from manifest-verified raw")
    return {"verified": True, "nodes": len(actual["nodes"]), "edges": len(actual["edges"])}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--case", choices=["equal-synthetic", "source-a"], default="equal-synthetic"
    )
    parser.add_argument("--verify-source-raw", type=Path)
    parser.add_argument(
        "--export-query", type=Path, help="Export semantic automatic query to this file"
    )
    parser.add_argument(
        "--simulate-review",
        action="store_true",
        help="Review gate simulation only on copies; never B numeric approval",
    )
    args = parser.parse_args()
    if args.verify_source_raw:
        print(json.dumps(verify_source_a_projection(args.verify_source_raw), indent=2))
        return
    if args.export_query:
        verify_package()
        builder = build_source_a_query if args.case == "source-a" else build_two_routes_query
        query, _ = builder(simulate_review=args.simulate_review)
        with args.export_query.open("x", encoding="utf-8") as output:
            output.write(json.dumps(query, indent=2) + "\n")
    else:
        _require(not args.simulate_review, "--simulate-review requires --export-query")
        print(
            json.dumps(
                {
                    "package": verify_package(),
                    "probe": run_source_a_probe()
                    if args.case == "source-a"
                    else run_scenario_probe(),
                },
                indent=2,
                sort_keys=True,
            )
        )


if __name__ == "__main__":
    main()
