"""Execute the reviewed Week 3 release through real search and ranking for #155."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.research.reviewed_parameter_release import verify_release  # noqa: E402
from src.engine import SearchBudget  # noqa: E402
from src.engine.ranking.orchestration import generate_and_evaluate_attack_paths  # noqa: E402
from src.engine.semantics import (  # noqa: E402
    RuntimeContext,
    load_catalog,
)
from src.engine.semantics.evidence_view import counterfactual_view  # noqa: E402
from src.engine.semantics.projection_runtime import context_for_projection  # noqa: E402
from src.engine.semantics.projection_runtime import release_fact as release_fact  # noqa: E402
from src.engine.semantics.week3 import runtime_for_projection  # noqa: E402
from src.parser import ErrorPolicy  # noqa: E402
from src.parser.cli import (  # noqa: E402
    atomic_write,
    build_graph,
    load_contract,
    load_time_policy,
    resolve_code_version,
    resolve_manifest,
)

DEFAULT_RELEASE = ROOT / "docs/research/ratings/week3-closeout/reviewed-release.json"
DEFAULT_PLAN = ROOT / "docs/research/ratings/week3-closeout/search-integration-plan.json"
DEFAULT_ACCEPTANCE_MANIFEST = ROOT / "tests/fixtures/ranking/week3_acceptance_cases.json"
DEFAULT_MANIFEST_DIR = ROOT / "data/samples/manifests"
DEFAULT_RAW_DIR = ROOT / "data/raw/SEAMLESS"
EXPECTED_RELEASE_DIGEST = "sha256:20f67e8604f6399b5b360e412bb30bf898f4d788f13b69c08c78ef2df73d3358"


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"unable to load JSON {path}: {exc}") from exc


def digest(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return "sha256:" + hashlib.sha256(payload.encode()).hexdigest()


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def relative_repo_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return path.name


def checkout_revision() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--verify", "HEAD"],
            cwd=ROOT,
            capture_output=True,
            check=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise ValueError("unable to resolve checkout revision") from exc
    revision = result.stdout.strip()
    if len(revision) != 40 or any(ch not in "0123456789abcdef" for ch in revision):
        raise ValueError("git returned an invalid checkout revision")
    return revision


def overlay(payload: Any, operations: list[dict[str, Any]]) -> Any:
    result = json.loads(json.dumps(payload))
    for patch in operations:
        parts = patch["path"].lstrip("/").split("/")
        parent = result
        for part in parts[:-1]:
            parent = parent[int(part)] if isinstance(parent, list) else parent[part]
        key = parts[-1]
        if patch["op"] == "remove":
            del parent[int(key) if isinstance(parent, list) else key]
        elif patch["op"] == "add" and isinstance(parent, list) and key == "-":
            parent.append(json.loads(json.dumps(patch["value"])))
        else:
            raise ValueError(f"unsupported reviewed overlay operation: {patch['op']}")
    return result


def context_for(
    query: dict[str, Any],
    source_plan: dict[str, Any],
    case_plan: dict[str, Any],
    *,
    withheld_relationships=frozenset(),
) -> RuntimeContext:
    return context_for_projection(
        query,
        source_plan,
        case_plan,
        authentication_context=source_plan.get("authentication_context"),
        withheld_relationships=withheld_relationships,
    )


def bindings_for(source_plan: dict[str, Any]) -> dict[tuple[str, str, str, str], str]:
    result = {}
    for row in source_plan.get("transition_action_bindings", []):
        key = tuple(row[name] for name in ("technique_id", "actor", "source", "target"))
        if key in result and result[key] != row["action_id"]:
            raise ValueError(f"ambiguous action binding for {key!r}")
        result[key] = row["action_id"]
    return result


def selected_catalog(source_plan: dict[str, Any]):
    ids = set(source_plan.get("semantic_catalog", []))
    catalog = tuple(item for item in load_catalog() if item.id in ids)
    if {item.id for item in catalog} != ids:
        raise ValueError("search plan references an unknown semantic technique")
    return catalog


def ownership_audit(projection: dict[str, Any], source_plan: dict[str, Any]) -> dict[str, Any]:
    reviewed = {
        action_id
        for candidate in projection["candidates"]
        for action_id in candidate["bound_action_ids"]
    }
    owners = source_plan.get("action_semantic_owners", {})
    missing = sorted(reviewed - set(owners))
    gaps = [
        {"action_id": action_id, **owners[action_id]}
        for action_id in sorted(reviewed & set(owners))
        if owners[action_id].get("status") == "gap"
    ]

    known_techniques = {item.id for item in load_catalog()}
    selected_techniques = set(source_plan.get("semantic_catalog", []))
    binding_rows = source_plan.get("transition_action_bindings", [])
    invalid_catalog_owners = []
    for action_id in sorted(reviewed & set(owners)):
        owner = owners[action_id]
        status = owner.get("status")
        if status == "gap":
            continue
        if status != "catalog_transition":
            invalid_catalog_owners.append(
                {"action_id": action_id, "reason": f"unsupported owner status {status!r}"}
            )
            continue
        technique_id = owner.get("technique_id")
        rows = [row for row in binding_rows if row.get("action_id") == action_id]
        reasons = []
        if technique_id not in known_techniques:
            reasons.append("owner technique is absent from the semantic catalog")
        if technique_id not in selected_techniques:
            reasons.append("owner technique is absent from this source search catalog")
        if len(rows) != 1:
            reasons.append(f"expected exactly one transition binding, found {len(rows)}")
        elif rows[0].get("technique_id") != technique_id:
            reasons.append("transition binding technique differs from semantic owner")
        if reasons:
            invalid_catalog_owners.append(
                {"action_id": action_id, "technique_id": technique_id, "reasons": reasons}
            )

    return {
        "reviewed_action_ids": sorted(reviewed),
        "missing_owner_action_ids": missing,
        "gaps": gaps,
        "invalid_catalog_owners": invalid_catalog_owners,
        "complete": not missing and not gaps and not invalid_catalog_owners,
    }


def success_state_predicate(query: dict[str, Any], source_plan: dict[str, Any]):
    spec = source_plan.get("terminal_success_state")
    if not isinstance(spec, dict):
        raise ValueError("source plan requires terminal_success_state")
    goal = query["query_metadata"]["target_goal"]
    required = spec.get("required_query_predicate")
    if required not in goal.get("required_predicates", []):
        raise ValueError("terminal success-state predicate differs from query target_goal")
    if spec.get("state_field") != "admin_control" or spec.get("contains_target") is not True:
        raise ValueError(
            "Week 3 harness only supports explicit admin_control(target) terminal state"
        )
    target_id = goal["target_asset_id"]
    return lambda state: target_id in state.admin_control


def acceptance_manifest_audit(
    release: dict[str, Any],
    plan: dict[str, Any],
    acceptance_manifest: dict[str, Any] | None,
) -> dict[str, Any]:
    pin = plan.get("acceptance_manifest", {})
    if acceptance_manifest is None:
        return {
            "available": False,
            "complete": False,
            "source_revision": pin.get("source_revision"),
            "source_pr": pin.get("source_pr"),
            "reason": "A-owned acceptance manifest is not present in this checkout",
            "mismatches": [],
        }

    mismatches: list[dict[str, Any]] = []
    if digest(acceptance_manifest) != pin.get("canonical_digest"):
        mismatches.append({"field": "canonical_digest", "reason": "manifest pin differs"})
    if acceptance_manifest.get("release", {}).get("digest") != plan.get("release_digest"):
        mismatches.append({"field": "release.digest", "reason": "release digest differs"})
    external_cases = {case["case_id"]: case for case in acceptance_manifest.get("cases", [])}
    local_cases = plan.get("cases", {})
    if set(external_cases) != set(local_cases):
        mismatches.append(
            {
                "field": "case_ids",
                "expected": sorted(external_cases),
                "actual": sorted(local_cases),
            }
        )

    for case_id, local in local_cases.items():
        external = external_cases.get(case_id)
        if external is None:
            continue
        for field in ("source", "kind"):
            if local.get(field) != external.get(field):
                mismatches.append(
                    {
                        "case_id": case_id,
                        "field": field,
                        "expected": external.get(field),
                        "actual": local.get(field),
                    }
                )
        expected_candidates = external.get("expected", {}).get("candidates", {})
        reviewed_ids = {
            item["candidate_id"]
            for item in release["query_projections"][local["source"]]["candidates"]
        }
        if (
            set(expected_candidates) != reviewed_ids
            or any(
                item.get("status") not in {"feasible", "blocked", "unknown"}
                for item in expected_candidates.values()
            )
            or not external.get("search_expected")
        ):
            mismatches.append({"case_id": case_id, "field": "expected/search_expected"})
        external_predicate = external.get("predicate")
        local_predicate = local.get("predicate_name")
        if external_predicate is None:
            if local_predicate is not None:
                mismatches.append({"case_id": case_id, "field": "predicate_name", "expected": None})
            continue
        if local_predicate != external_predicate.get("name"):
            mismatches.append(
                {
                    "case_id": case_id,
                    "field": "predicate_name",
                    "expected": external_predicate.get("name"),
                    "actual": local_predicate,
                }
            )
        search_binding = external_predicate.get("search_binding")
        if local.get("search_binding_status") == "mapped":
            if local.get("kind") in {"structural_missing", "telemetry_missing"}:
                spec = local.get("evidence_view")
                if not isinstance(spec, dict):
                    mismatches.append(
                        {
                            "case_id": case_id,
                            "field": "evidence_view",
                            "reason": "missing case requires evidence_view specification",
                        }
                    )
                elif local.get("kind") == "structural_missing" and not (
                    spec.get("kind") == "withhold_structural_provenance"
                    and spec.get("locator") == "20210920185958_users.json#/users/2310/Aces/3"
                ):
                    mismatches.append(
                        {
                            "case_id": case_id,
                            "field": "evidence_view",
                            "reason": (
                                "structural_missing evidence_view differs from reviewed locator"
                            ),
                        }
                    )
                elif local.get("kind") == "telemetry_missing" and not (
                    spec.get("kind") == "withhold_enabled_observation"
                    and spec.get("locator")
                    == "20210920185958_users.json#/users/2310/Properties/enabled"
                ):
                    mismatches.append(
                        {
                            "case_id": case_id,
                            "field": "evidence_view",
                            "reason": (
                                "telemetry_missing evidence_view differs from reviewed locator"
                            ),
                        }
                    )
                continue
            overrides = local.get("runtime_fact_overrides", [])
            source_plan = plan["sources"][local["source"]]
            runtime_binding = next(
                (
                    item
                    for item in source_plan.get("runtime_fact_bindings", [])
                    if item.get("release_predicate") == local_predicate
                ),
                None,
            )
            if search_binding is None or len(overrides) != 1 or runtime_binding is None:
                mismatches.append(
                    {
                        "case_id": case_id,
                        "field": "search_binding",
                        "reason": "mapped case lacks exact A search binding inputs",
                    }
                )
                continue
            override = overrides[0]
            query = release["query_projections"][local["source"]]["query"]
            expected = {
                "technique_id": "genericall_reset_password",
                "predicate": runtime_binding["semantic_predicate"],
                "subject": runtime_binding["subject"],
                "target": runtime_binding["target"],
                "value": override.get("truth_value"),
                "origin": override.get("origin"),
                "scope": query["query_metadata"]["scenario_id"],
                "rationale": override.get("rationale"),
            }
            actual = {key: search_binding.get(key) for key in expected}
            if actual != expected:
                mismatches.append(
                    {
                        "case_id": case_id,
                        "field": "search_binding",
                        "expected": expected,
                        "actual": actual,
                    }
                )
        elif search_binding is not None:
            mismatches.append(
                {
                    "case_id": case_id,
                    "field": "search_binding_status",
                    "reason": "local gap conflicts with A-owned mapped search binding",
                }
            )

    return {
        "available": True,
        "complete": not mismatches,
        "pin_policy": "exact file/blob and canonical content; source revision is provenance",
        "case_expectations": external_cases,
        "source_revision": pin.get("source_revision"),
        "source_pr": pin.get("source_pr"),
        "mismatches": mismatches,
    }


def graph_from_args(
    args: argparse.Namespace, release: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    snapshot_id = release["bundle_metadata"]["snapshot_id"]
    manifest_path, manifest = resolve_manifest(args.manifest_dir, snapshot_id)
    manifest_pin = {
        "path": relative_repo_path(manifest_path),
        "file_sha256": file_sha256(manifest_path),
        "canonical_digest": digest(manifest),
        "dataset_id": manifest.get("dataset_id"),
        "file_count": len(manifest.get("files", [])),
    }

    if args.graph:
        graph = load_json(args.graph)
        if not isinstance(graph, dict):
            raise ValueError("--graph must contain a canonical graph object")
        return (
            graph,
            {
                "input_mode": "canonical_graph_file",
                "graph_file": {
                    "name": args.graph.name,
                    "file_sha256": file_sha256(args.graph),
                    "canonical_digest": digest(graph),
                },
                "raw_manifest": manifest_pin,
                "parser_config": {
                    "profile": graph.get("metadata", {}).get("weight_profile"),
                    "created_at": graph.get("metadata", {}).get("created_at"),
                    "time_policy": None,
                },
            },
            manifest,
        )

    if args.raw_dir is None or args.created_at is None:
        raise ValueError("raw execution requires --raw-dir and fixed --created-at")
    contract = load_contract()
    graph = build_graph(
        raw_dir=args.raw_dir,
        manifest_path=manifest_path,
        snapshot_id=snapshot_id,
        profile=args.profile,
        contract=contract,
        created_at=args.created_at,
        code_version=resolve_code_version(),
        error_policy=ErrorPolicy.FAIL_FAST,
        time_policy=load_time_policy(args.time_policy),
    )
    time_policy_pin = None
    if args.time_policy is not None:
        time_policy_pin = {
            "name": args.time_policy.name,
            "file_sha256": file_sha256(args.time_policy),
        }
    return (
        graph,
        {
            "input_mode": "verified_raw_parser_build",
            "graph_file": {"canonical_digest": digest(graph)},
            "raw_manifest": manifest_pin,
            "parser_config": {
                "profile": args.profile,
                "created_at": args.created_at,
                "time_policy": time_policy_pin,
            },
        },
        manifest,
    )


def checkout_tree() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD^{tree}"],
            cwd=ROOT,
            capture_output=True,
            check=True,
            text=True,
        )
        return result.stdout.strip()
    except OSError, subprocess.CalledProcessError:
        return ""


def execution_pins(
    args: argparse.Namespace,
    graph_pins: dict[str, Any],
) -> dict[str, Any]:
    files = {
        "release": args.release,
        "plan": args.plan,
        "contract": ROOT / "configs/contract.yml",
        "semantic_catalog": ROOT / "configs/attack_semantics.yml",
        "requirements": ROOT / "requirements.txt",
        "requirements_dev": ROOT / "requirements-dev.txt",
    }
    pins = {
        name: {
            "path": relative_repo_path(path),
            "file_sha256": file_sha256(path),
        }
        for name, path in files.items()
    }
    return {
        "checkout_revision": checkout_revision(),
        "git_tree": checkout_tree(),
        "python_version": ".".join(str(item) for item in sys.version_info[:3]),
        "platform": platform.platform(),
        "files": pins,
        "graph_input": graph_pins,
    }


def source_result(
    projection: dict[str, Any],
    source_plan: dict[str, Any],
    case_plan: dict[str, Any],
    graph: dict[str, Any],
    *,
    case_overlay: list[dict[str, Any]] | None = None,
    raw_dir: Path | str | None = None,
    raw_manifest: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload = overlay(projection, case_overlay or [])
    query = payload["query"]
    evidence_spec = case_plan.get("evidence_view")
    view = counterfactual_view(
        graph,
        evidence_spec,
        case_id=case_plan.get("case_id", ""),
        raw_dir=raw_dir,
        manifest=raw_manifest,
    )
    state, context = runtime_for_projection(
        query,
        source_plan,
        case_plan,
        withheld_relationships=view.withheld_relationships,
    )
    budget = SearchBudget(**source_plan["budget"])
    result = generate_and_evaluate_attack_paths(
        query,
        view.graph,
        actor=source_plan["actor"],
        initial_state=state,
        runtime_context=context,
        budget=budget,
        action_bindings=bindings_for(source_plan),
        catalog=selected_catalog(source_plan),
        scenario_reference=query["query_metadata"]["scenario_id"],
        success_state_predicate=success_state_predicate(query, source_plan),
    )
    ranked = result["roundtrip_result"]
    expected = {
        tuple(candidate["bound_action_ids"]): candidate["candidate_id"]
        for candidate in projection["candidates"]
    }
    matched = {
        expected.get(tuple(assessment.get("bound_action_ids", [])))
        for assessment in ranked.get("eligible_candidates", {}).values()
    }
    matched.discard(None)
    reviewed_mapping = {
        cand_id: expected.get(tuple(assessment.get("bound_action_ids", [])))
        for cand_id, assessment in ranked.get("eligible_candidates", {}).items()
        if expected.get(tuple(assessment.get("bound_action_ids", []))) is not None
    }
    return {
        "query_id": query["query_metadata"]["query_id"],
        "search_metadata": ranked.get("search_metadata"),
        "search_audit": ranked.get("search_audit"),
        "eligible_candidates": ranked.get("eligible_candidates"),
        "diagnostics": ranked.get("diagnostics"),
        "pareto_frontier": ranked.get("pareto_frontier"),
        "min_effort_to_da_baseline": ranked.get("min_effort_to_da_baseline"),
        "matched_reviewed_candidate_ids": sorted(matched),
        "reviewed_candidate_mapping": reviewed_mapping,
        "evidence_view": view.audit,
    }


def case_expectation_audit(
    projection: dict[str, Any],
    case: dict[str, Any] | None,
    result: dict[str, Any],
) -> dict[str, Any]:
    """Require feasible programs, correct metrics, frontier, and designated pruning evidence."""
    if case is None:
        return {"complete": False, "reason": "verified case expectations unavailable"}
    expectations = case["expected"]["candidates"]
    required = {cid for cid, item in expectations.items() if item["status"] == "feasible"}
    forbidden = set(expectations) - required
    programs = {
        tuple(item["bound_action_ids"]): item["candidate_id"] for item in projection["candidates"]
    }
    eligible = result.get("eligible_candidates") or {}
    matched = {}
    for k, item in eligible.items():
        cid = programs.get(tuple(item.get("bound_action_ids", []))) or k
        if cid in expectations:
            matched[cid] = item

    missing = required - set(matched)
    unexpected = forbidden & set(matched)

    candidate_metrics_matched = True
    metric_mismatches = []
    for cid in required:
        actual_assessment = matched.get(cid)
        if actual_assessment is None:
            continue
        expected_assessment = expectations[cid]
        for metric_key in ("effort", "likelihood_interval", "impact"):
            expected_val = expected_assessment.get(metric_key)
            actual_val = actual_assessment.get(metric_key)
            if actual_val != expected_val:
                candidate_metrics_matched = False
                metric_mismatches.append(
                    {
                        "candidate_id": cid,
                        "field": metric_key,
                        "expected": expected_val,
                        "actual": actual_val,
                    }
                )

    expected_frontier = case["expected"].get("pareto_frontier")
    actual_frontier = result.get("pareto_frontier") or []
    actual_frontier_cids = []
    for item in actual_frontier:
        if item in expectations:
            actual_frontier_cids.append(item)
        elif item in eligible:
            mapped_cid = programs.get(tuple(eligible[item].get("bound_action_ids", [])))
            if mapped_cid:
                actual_frontier_cids.append(mapped_cid)
            else:
                actual_frontier_cids.append(item)
        else:
            actual_frontier_cids.append(item)
    frontier_verified = True
    if expected_frontier is not None:
        frontier_verified = set(actual_frontier_cids) == set(expected_frontier)

    min_effort_verified = True
    expected_min = case["expected"].get("min_effort")
    actual_min = result.get("min_effort_to_da_baseline")
    mapped_best = None
    if expected_min is not None:
        if not isinstance(actual_min, dict):
            min_effort_verified = False
        else:
            best_id = actual_min.get("best_candidate_id")
            mapped_best = (
                programs.get(tuple(eligible.get(best_id, {}).get("bound_action_ids", [])))
                or best_id
            )
            if mapped_best != expected_min.get("best_candidate_id") or actual_min.get(
                "minimum_effort_value"
            ) != expected_min.get("minimum_effort_value"):
                min_effort_verified = False
    elif (
        not required
        and actual_min is not None
        and actual_min.get("minimum_effort_value") is not None
    ):
        min_effort_verified = False

    negative_evidence = case["kind"] == "positive"
    matching_attempts = []
    if case["kind"] in {"known_false", "runtime_unknown"}:
        binding = case["predicate"]["search_binding"]
        bucket = "failed" if case["kind"] == "known_false" else "unknown"
        status = "blocked" if bucket == "failed" else "indeterminate"
        for attempt in (result.get("search_audit") or {}).get("attempt_diagnostics", []):
            if not (
                attempt.get("technique_id") in {binding["technique_id"], "scenario_reset_password"}
                and attempt.get("actor") == binding["subject"]
                and attempt.get("source") == binding["subject"]
                and attempt.get("target") == binding["target"]
                and attempt.get("status") == status
                and binding["predicate"] in attempt.get(bucket, [])
            ):
                continue
            for decision in attempt.get("decisions", []):
                if (
                    decision.get("predicate") == binding["predicate"]
                    and decision.get("satisfied") is False
                    and decision.get("origin") == binding["origin"]
                    and decision.get("rationale") == binding["rationale"]
                    and decision.get("subject") == binding["subject"]
                    and decision.get("target") == binding["target"]
                    and decision.get("value") is binding["value"]
                    and decision.get("scope") == binding["scope"]
                ):
                    matching_attempts.append(attempt)
                    break
        negative_evidence = bool(matching_attempts)
    elif case["kind"] == "structural_missing":
        for attempt in (result.get("search_audit") or {}).get("attempt_diagnostics", []):
            if not (
                attempt.get("actor") == projection["query"]["query_metadata"]["foothold_node_id"]
                and attempt.get("target") == "S-1-5-21-1271839998-3495686680-2211690266-3398"
                and attempt.get("status") == "indeterminate"
                and "relationship_exists" in attempt.get("unknown", [])
            ):
                continue
            for decision in attempt.get("decisions", []):
                if (
                    decision.get("predicate") == "relationship_exists"
                    and decision.get("satisfied") is False
                    and decision.get("origin") == "unknown"
                    and decision.get("value") is None
                ):
                    matching_attempts.append(attempt)
                    break
        matching_delta = [
            d
            for d in (result.get("evidence_view") or {}).get("delta", [])
            if d.get("op") == "withhold_provenance"
            and d.get("locator") == "20210920185958_users.json#/users/2310/Aces/3"
        ]
        negative_evidence = bool(matching_attempts) and bool(matching_delta)
    elif case["kind"] == "telemetry_missing":
        for attempt in (result.get("search_audit") or {}).get("attempt_diagnostics", []):
            if not (
                attempt.get("actor") == projection["query"]["query_metadata"]["foothold_node_id"]
                and attempt.get("target") == "S-1-5-21-1271839998-3495686680-2211690266-3398"
                and attempt.get("status") == "indeterminate"
                and "target_enabled" in attempt.get("unknown", [])
            ):
                continue
            for decision in attempt.get("decisions", []):
                if (
                    decision.get("predicate") == "target_enabled"
                    and decision.get("satisfied") is False
                    and decision.get("origin") == "unknown"
                    and decision.get("value") is None
                ):
                    matching_attempts.append(attempt)
                    break
        matching_delta = [
            d
            for d in (result.get("evidence_view") or {}).get("delta", [])
            if d.get("op") == "remove"
            and d.get("field") == "enabled"
            and d.get("locator") == "20210920185958_users.json#/users/2310/Properties/enabled"
        ]
        negative_evidence = bool(matching_attempts) and bool(matching_delta)

    empty_frontier = bool(required) or (not eligible and not result.get("pareto_frontier"))
    complete = (
        not missing
        and not unexpected
        and candidate_metrics_matched
        and frontier_verified
        and min_effort_verified
        and negative_evidence
        and empty_frontier
    )
    reviewed_mapping = {
        k: programs.get(tuple(item.get("bound_action_ids", [])))
        for k, item in eligible.items()
        if programs.get(tuple(item.get("bound_action_ids", []))) is not None
    }
    return {
        "complete": complete,
        "expected_feasible_candidate_ids": sorted(required),
        "expected_pruned_candidate_ids": sorted(forbidden),
        "matched_reviewed_candidate_ids": sorted(matched),
        "missing_reviewed_candidate_ids": sorted(missing),
        "unexpected_ranked_candidate_ids": sorted(unexpected),
        "candidate_metrics_matched": candidate_metrics_matched,
        "metric_mismatches": metric_mismatches,
        "frontier_verified": frontier_verified,
        "mapped_pareto_frontier": actual_frontier_cids,
        "min_effort_verified": min_effort_verified,
        "mapped_min_effort_candidate_id": mapped_best,
        "reviewed_candidate_mapping": reviewed_mapping,
        "designated_negative_decision_verified": negative_evidence,
        "matching_negative_attempts": matching_attempts,
        "empty_frontier_verified": empty_frontier,
    }


def build_report(
    release: dict[str, Any],
    plan: dict[str, Any],
    graph: dict[str, Any],
    case_id: str,
    pins: dict[str, Any],
    acceptance_audit: dict[str, Any],
    *,
    raw_dir: Path | str | None = None,
    raw_manifest: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if plan.get("release_digest") != release["bundle_metadata"]["bundle_digest"]:
        raise ValueError("search plan does not target the reviewed release")
    case_plan = plan.get("cases", {}).get(case_id)
    if not isinstance(case_plan, dict):
        raise ValueError(f"unknown Week 3 acceptance case: {case_id}")
    source = case_plan["source"]
    projection = release["query_projections"][source]
    source_plan = plan["sources"][source]
    if source_plan["actor"] != projection["query"]["query_metadata"]["foothold_node_id"]:
        raise ValueError(f"{source} actor differs from reviewed foothold")

    ownership = ownership_audit(projection, source_plan)
    case_mapped = case_plan.get("search_binding_status") == "mapped"
    if case_mapped:
        case_overlay = None
        if acceptance_audit.get("complete"):
            external_case = acceptance_audit.get("case_expectations", {}).get(case_id)
            if external_case:
                case_overlay = external_case.get("overlay")
        result = source_result(
            projection,
            source_plan,
            case_plan,
            graph,
            case_overlay=case_overlay,
            raw_dir=raw_dir,
            raw_manifest=raw_manifest,
        )
        expectation = case_expectation_audit(
            projection,
            acceptance_audit.get("case_expectations", {}).get(case_id)
            if acceptance_audit.get("complete")
            else None,
            result,
        )
        result["case_expectation_audit"] = expectation
        result["missing_reviewed_candidate_ids"] = expectation.get(
            "missing_reviewed_candidate_ids", []
        )
        candidates_complete = expectation["complete"]
    else:
        result = {
            "status": "not_run",
            "reason": case_plan.get("reason"),
            "missing_reviewed_candidate_ids": [
                candidate["candidate_id"] for candidate in projection["candidates"]
            ],
        }
        candidates_complete = False

    if not case_mapped:
        status = "blocked_acceptance_case_mapping"
    elif not ownership["complete"]:
        status = "blocked_semantic_coverage"
    elif not acceptance_audit.get("complete"):
        status = "acceptance_manifest_not_verified"
    elif not candidates_complete:
        status = "case_search_expectations_not_met"
    else:
        status = "passed"

    metadata = graph.get("metadata", {})
    report = {
        "schema_version": "1.3.0",
        "scope": "issue-155-release-consuming-real-search-to-ranking",
        "case_id": case_id,
        "case_kind": case_plan["kind"],
        "source": source,
        "status": status,
        "release_digest": release["bundle_metadata"]["bundle_digest"],
        "plan_digest": digest(plan),
        "acceptance_manifest_audit": acceptance_audit,
        "execution_pins": pins,
        "graph": {
            "snapshot_id": metadata.get("snapshot_id"),
            "contract_version": metadata.get("contract_version"),
            "code_version": metadata.get("code_version"),
            "weight_profile": metadata.get("weight_profile"),
            "created_at": metadata.get("created_at"),
            "canonical_digest": digest(graph),
            "node_count": len(graph.get("nodes", [])),
            "edge_count": len(graph.get("edges", [])),
        },
        "semantic_ownership": ownership,
        "case_mapping": {
            "status": case_plan.get("search_binding_status"),
            "predicate_name": case_plan.get("predicate_name"),
            "reason": case_plan.get("reason"),
        },
        "result": result,
        "limitations": [
            "Supplied reviewed candidates are oracle inputs only and are never replayed "
            "as search output.",
            "Bounded search does not establish global optimality outside recorded caps.",
            "Bounded search with empty results does not establish global absence of paths.",
            (
                "Ranking applies only to generated and eligible candidates within "
                "the declared bounded scope."
            ),
        ],
    }
    report["report_digest"] = digest(report)
    return report


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--release", type=Path, default=DEFAULT_RELEASE)
    p.add_argument("--plan", type=Path, default=DEFAULT_PLAN)
    p.add_argument(
        "--acceptance-manifest",
        type=Path,
        default=DEFAULT_ACCEPTANCE_MANIFEST,
        help="A-owned #177/#178 acceptance manifest; absence is recorded fail-closed.",
    )
    p.add_argument("--case-id", default="w3-source-a-positive")
    p.add_argument("--graph", type=Path)
    p.add_argument(
        "--raw-dir",
        type=Path,
        default=DEFAULT_RAW_DIR if DEFAULT_RAW_DIR.exists() else None,
    )
    p.add_argument("--manifest-dir", type=Path, default=DEFAULT_MANIFEST_DIR)
    p.add_argument("--profile", default="unit")
    p.add_argument("--created-at")
    p.add_argument("--time-policy", type=Path)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--require-complete", action="store_true")
    return p


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        release = load_json(args.release)
        plan = load_json(args.plan)
        if not isinstance(release, dict) or not isinstance(plan, dict):
            raise ValueError("release and plan must be JSON objects")
        verify_release(release)
        if release["bundle_metadata"]["bundle_digest"] != EXPECTED_RELEASE_DIGEST:
            raise ValueError("reviewed release digest differs from the pinned Week 3 release")

        acceptance_manifest = None
        if args.acceptance_manifest.exists():
            loaded = load_json(args.acceptance_manifest)
            if not isinstance(loaded, dict):
                raise ValueError("acceptance manifest must be a JSON object")
            acceptance_manifest = loaded
        acceptance_audit = acceptance_manifest_audit(release, plan, acceptance_manifest)
        if acceptance_manifest is not None:
            raw_manifest = args.acceptance_manifest.read_bytes()
            actual_blob = hashlib.sha1(
                b"blob " + str(len(raw_manifest)).encode() + b"\0" + raw_manifest
            ).hexdigest()
            pin = plan["acceptance_manifest"]
            if actual_blob != pin.get("blob_sha"):
                acceptance_audit["mismatches"].append(
                    {"field": "blob_sha", "expected": pin.get("blob_sha"), "actual": actual_blob}
                )
                acceptance_audit["complete"] = False
            acceptance_audit["actual_blob_sha"] = actual_blob

        graph, graph_pins, raw_manifest = graph_from_args(args, release)
        if (
            graph.get("metadata", {}).get("snapshot_id")
            != release["bundle_metadata"]["snapshot_id"]
        ):
            raise ValueError("canonical graph snapshot differs from reviewed release snapshot")
        pins = execution_pins(args, graph_pins)
        if acceptance_manifest is not None:
            pins["acceptance_manifest"] = {
                "path": relative_repo_path(args.acceptance_manifest),
                "file_sha256": file_sha256(args.acceptance_manifest),
            }

        report = build_report(
            release,
            plan,
            graph,
            args.case_id,
            pins,
            acceptance_audit,
            raw_dir=args.raw_dir,
            raw_manifest=raw_manifest,
        )
        payload = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        atomic_write(args.output, payload)
        print(
            json.dumps(
                {"status": report["status"], "report_digest": report["report_digest"]},
                sort_keys=True,
            )
        )
        return 4 if args.require_complete and report["status"] != "passed" else 0
    except (KeyError, OSError, TypeError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
