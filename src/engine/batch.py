"""Isolated source×goal execution over the public engine and reviewed #268 contract.

No search, scoring or priority algorithm is duplicated here. Execution details and
exact public traces live in the extensible reproducibility/diagnostic fields of
batch-query-result/1.0.0. Checkpoints are local, integrity-checked run artifacts.
"""

from __future__ import annotations

import copy
import hashlib
import json
import multiprocessing
import platform
import subprocess
import time
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, replace
from pathlib import Path

from jsonschema import Draft202012Validator

from scripts.research.source_goal_batch import (
    BatchCellStatus,
    BatchQueryRequest,
    BatchQueryResult,
    BatchSourceItem,
    SourceGoalCell,
    TargetControlLevel,
    TargetGoal,
    _goal_ranking_key,
    map_query_result_to_cell,
    prioritize_sources,
)
from src.engine.graph import EngineGraph
from src.engine.query import AttackQuery, materialize_query, run_attack_query
from src.engine.query_cli import wire
from src.engine.ranking.effort_profiles import bind_effort_profile, load_effort_profile
from src.engine.ranking.resolution_service import canonical_digest
from src.engine.semantics import FactOrigin, RuntimeFact
from src.engine.semantics.scenario_policy import (
    ScenarioPolicyProfile,
    apply_policy_to_query,
    load_policy_profile,
)
from src.parser.snapshot_facts import serialize_snapshot

ROOT = Path(__file__).resolve().parents[2]
EXECUTION_VERSION = "source-goal-execution/1.0.0"
CHECKPOINT_VERSION = "source-goal-checkpoint/1.0.0"


@dataclass(frozen=True)
class BatchExecutionBudget:
    """Global limits count newly executed cells/expansions, excluding cached cells.

    Wall limits are opt-in and machine-dependent. Deterministic parity claims
    require logical budgets and completed cells, not identical timeout boundaries.
    """

    max_cells: int | None = None
    max_expansions: int | None = None
    max_seconds: float | None = None
    per_query_seconds: float | None = None

    def __post_init__(self):
        for name in ("max_cells", "max_expansions"):
            value = getattr(self, name)
            if value is not None and (type(value) is not int or value < 1):
                raise ValueError(f"{name} must be a positive integer")
        for name in ("max_seconds", "per_query_seconds"):
            value = getattr(self, name)
            if value is not None and (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not 0 < value < float("inf")
            ):
                raise ValueError(f"{name} must be positive and finite")


def validate_schema(value: Mapping, name: str) -> None:
    schema = json.loads((ROOT / "docs/research" / f"{name}.schema.json").read_text())
    Draft202012Validator(schema).validate(value)


def _parse_request(request: BatchQueryRequest | Mapping) -> BatchQueryRequest:
    """Validate the wire request before selection can discard any fields."""
    if isinstance(request, Mapping):
        validate_schema(request, "batch-query-request")
        # Embedded manifests may omit the standalone envelope marker.
        validate_schema(
            {"schema_version": "target-manifest/1.0.0", **request["target_manifest"]},
            "target-manifest",
        )
        return BatchQueryRequest.from_dict(request)
    if not isinstance(request, BatchQueryRequest):
        raise TypeError("request must be BatchQueryRequest or Mapping")
    return request


def _validate_runtime_fact_origins(runtime_facts: Sequence) -> tuple:
    """Batch-wide facts cannot carry source-local assumptions or untyped truth."""
    if isinstance(runtime_facts, (str, bytes, Mapping)):
        raise TypeError("runtime_facts must be a sequence of RuntimeFact or Mapping entries")
    facts = tuple(runtime_facts)
    for index, fact in enumerate(facts):
        if isinstance(fact, RuntimeFact):
            raw_origin = fact.origin
        elif isinstance(fact, Mapping):
            # Same observed default as the public fact materializer.
            raw_origin = fact.get("origin", FactOrigin.OBSERVED_EVIDENCE)
        else:
            raise TypeError(f"runtime_facts[{index}] must be RuntimeFact or Mapping")
        origin = FactOrigin(raw_origin)
        if origin in (FactOrigin.DECLARED_ASSUMPTION, FactOrigin.UNSPECIFIED):
            raise ValueError(
                f"BATCH_RUNTIME_FACT_ORIGIN_REFUSED: runtime_facts[{index}] has {origin}; "
                "declared assumptions belong in each source.declared_assumptions"
            )
    return facts


def execution_source_pins() -> dict[str, str]:
    """Content pins, rather than commit-only pins, also detect dirty input code."""
    paths = set()
    for directory in ("src", "configs"):
        paths.update(
            p
            for p in (ROOT / directory).rglob("*")
            if p.is_file() and p.suffix in (".py", ".yml", ".json")
        )
    paths.update(
        ROOT / p
        for p in (
            "scripts/check_contract.py",
            "scripts/research/source_goal_batch.py",
            "requirements-tests.txt",
            "requirements.txt",
            "docs/research/batch-query-request.schema.json",
            "docs/research/batch-query-result.schema.json",
            "docs/research/target-manifest.schema.json",
        )
    )
    return {
        str(p.relative_to(ROOT)): "sha256:" + hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(paths)
    }


def _graph_identity(graph: EngineGraph) -> dict:
    return {"graph": graph.to_canonical(), "snapshot_facts": wire(graph.snapshot_facts)}


def _validate_request(request: BatchQueryRequest, graph: EngineGraph) -> tuple[TargetGoal, ...]:
    validate_schema(request.to_dict(), "batch-query-request")
    validate_schema(request.target_manifest.to_dict(), "target-manifest")
    if request.snapshot_id != graph.metadata["snapshot_id"] or (
        request.target_manifest.snapshot_id != request.snapshot_id
    ):
        raise ValueError("SNAPSHOT_BINDING_MISMATCH")
    for collection, key in (
        (request.sources, "source_id"),
        (request.target_manifest.targets, "goal_id"),
    ):
        ids = [getattr(item, key) for item in collection]
        if len(ids) != len(set(ids)):
            raise ValueError(f"DUPLICATE_{key.upper()}")
    goals = tuple(sorted(request.resolve_target_goals(), key=lambda g: g.goal_id))
    if len({g.goal_id for g in goals}) != len(goals):
        raise ValueError("DUPLICATE_TARGET_SELECTION")
    # Validate canonical source/target references before any expensive query runs.
    for item in (*request.sources, *request.target_manifest.targets):
        node_id = item.node_id if isinstance(item, BatchSourceItem) else item.target_node_id
        kind = item.node_kind if isinstance(item, BatchSourceItem) else item.target_node_kind
        if graph.node(node_id)["kind"] != kind:
            raise ValueError(f"NODE_KIND_MISMATCH: {node_id}")
    return goals


def _cell(status: BatchCellStatus, code: str, **details) -> SourceGoalCell:
    return SourceGoalCell(
        status=status,
        control_level_attained=TargetControlLevel.NONE,
        truncated=code in ("QUERY_TIMEOUT", "GLOBAL_EXPANSION_BUDGET"),
        truncation_reason=code if code == "QUERY_TIMEOUT" else None,
        diagnostics=({"code": code, **details},),
    )


def _query_for_cell(
    request,
    source,
    goal,
    graph,
    allowed_techniques,
    budget,
    runtime_facts=(),
    scenario_policy=None,
    effort_profile=None,
    search_order="fifo",
):
    try:
        profile = source.to_foothold_profile(graph=graph)
    except ValueError as exc:
        return None, _cell(
            BatchCellStatus.UNSUPPORTED_SOURCE, "UNSUPPORTED_PROFILE", message=str(exc)
        )
    if not profile.is_supported:
        return None, _cell(
            BatchCellStatus.UNSUPPORTED_SOURCE,
            profile.error_code,
            message=profile.unsupported_reason,
            node_id=source.node_id,
            node_kind=source.node_kind,
            profile_kind=source.profile_kind,
        )
    target_goal = {"target": goal.target_node_id, "required_state": goal.required_state}
    if goal.goal_kind == "usable_identity_entitlement":
        context = profile.authentication_context
        if context is None or graph.node(context)["kind"] != "Computer":
            return None, _cell(
                BatchCellStatus.UNSUPPORTED_SOURCE,
                "UNSUPPORTED_AUTHENTICATION_CONTEXT",
                message="Identity-entitlement discovery requires an explicit Computer context",
            )
        target_goal = {"target": goal.target_node_id, "kind": goal.goal_kind}
    cell_id = canonical_digest(
        {
            "source": source.to_dict(),
            "goal": goal.to_dict(),
            "snapshot_id": request.snapshot_id,
            "evaluation_mode": request.evaluation_mode,
            "budget": asdict(budget),
            "allowed_techniques": allowed_techniques,
            "runtime_facts": wire(runtime_facts),
            **({"search_order": search_order} if search_order != "fifo" else {}),
            **({"scenario_policy_digest": scenario_policy.digest()} if scenario_policy else {}),
            **(
                {"effort_profile_digest": canonical_digest(effort_profile)}
                if effort_profile
                else {}
            ),
        }
    )
    scenario_id = f"batch-cell:{cell_id}"
    rating = copy.deepcopy(request.rating_resolution)
    if rating is not None:
        # Only query scope is rebound. Native records, applicability, context and
        # ordered-history bindings remain byte-for-byte unchanged and may refuse.
        scope = rating["scope"]
        scope.update(
            query_id=canonical_digest({"scenario": scenario_id, "rating_basis": rating}),
            scenario_id=scenario_id,
            foothold_node_id=source.node_id,
            snapshot_id=request.snapshot_id,
            evaluation_mode=request.evaluation_mode,
            active_work_budget=budget.max_steps,
            target_goal={
                "goal_id": goal.goal_id,
                "target_asset_id": goal.target_node_id,
                "success_event": goal.technical_consequence,
            },
        )
    query = AttackQuery(
        target=goal.target_node_id,
        source_foothold=profile.node_id,
        initial_actor=profile.initial_actor,
        initial_state=profile.initial_attack_state,
        authentication_context=profile.authentication_context,
        target_goal=target_goal,
        checkpoint_goal=copy.deepcopy(goal.checkpoint_goal),
        aliases={"__RESOLVED_ACTOR__": profile.initial_actor},
        assumptions=profile.declared_assumptions,
        runtime_facts=runtime_facts,
        budget=budget,
        scenario_reference=scenario_id,
        evaluation_mode=request.evaluation_mode,
        allowed_techniques=allowed_techniques,
        rating_resolution=rating,
        search_order=search_order,
    )
    # Compile each isolated source/context/goal through the existing resolver.
    # Wire first so typed defaults (notably top_k=None) do not become explicit
    # invalid mapping fields. The compiled assumptions and audit travel together
    # through workers, public traces and subsequent counterfactual replay.
    if scenario_policy is not None:
        query = apply_policy_to_query(_wire_query(query), graph, scenario_policy)
    if effort_profile is not None:
        query = bind_effort_profile(_wire_query(query), graph, effort_profile)
    return query, None


def _wire_query(query: AttackQuery | Mapping) -> dict:
    payload = wire(query)
    # None on the typed query means Top-K was not requested. On the public
    # mapping boundary, an explicitly present null is invalid, so omit only
    # the typed default when serializing worker requests and replayable traces.
    if isinstance(query, AttackQuery) and query.top_k is None:
        payload.pop("top_k", None)
    if isinstance(query, AttackQuery) and query.search_order == "fifo":
        payload.pop("search_order", None)
    return payload


def _evaluate(
    query: AttackQuery | Mapping, graph: EngineGraph, goal: TargetGoal
) -> tuple[dict, dict]:
    materialized = materialize_query(query, graph)
    result = run_attack_query(materialized, graph)
    cell = map_query_result_to_cell(result, goal)
    trace = {
        "query": _wire_query(query),
        "materialized": {
            "initial_actor": materialized.initial_actor,
            "initial_attack_state": wire(materialized.initial_attack_state),
            "runtime_context": wire(materialized.runtime_context),
            "rejected_assumptions": [r.to_dict() for r in materialized.rejected_assumptions],
            "semantic_goal": materialized.semantic_goal.to_dict(),
            **(
                {"search_strategy": materialized.search_strategy}
                if materialized.search_order != "fifo"
                else {}
            ),
        },
        "result": {
            name: wire(getattr(result, name))
            for name in (
                "status",
                "checkpoint_reached",
                "final_goal_reached",
                "caps",
                "complete",
                "truncated",
                "truncation_reason",
                "expansions",
                "paths",
                "attempts",
                "diagnostics",
                "checkpoint_diagnostics",
                "binding_diagnostics",
                "ranking_result",
                "rating_coverage",
                "min_effort",
                "best_path",
                "all_best_paths",
                "optimization_scope",
            )
        },
        "guarantees": {
            "is_minimum_proven_over_scope": result.is_minimum_proven_over_scope,
            "is_no_path_proven_over_scope": result.is_no_path_proven_over_scope,
        },
    }
    return cell.to_dict(), trace


def _worker(connection, query, graph, goal):
    try:
        graph = (
            EngineGraph.from_snapshot(graph)
            if isinstance(graph, str)
            else EngineGraph.from_canonical(graph)
        )
        connection.send({"outcome": _evaluate(query, graph, goal)})
    except Exception as exc:
        connection.send({"error": type(exc).__name__, "message": str(exc)})
    finally:
        connection.close()


def _execute(query, graph, goal, seconds):
    if seconds is None:
        return _evaluate(query, graph, goal)
    context = multiprocessing.get_context("spawn")
    receiver, sender = context.Pipe(duplex=False)
    graph_payload = (
        serialize_snapshot(graph.to_canonical(), graph.snapshot_facts)
        if graph.snapshot_facts is not None
        else graph.to_canonical()
    )
    process = context.Process(
        target=_worker, args=(sender, _wire_query(query), graph_payload, goal)
    )
    process.start()
    sender.close()
    try:
        if not receiver.poll(seconds):
            return _cell(
                BatchCellStatus.TRUNCATED_INCOMPLETE,
                "QUERY_TIMEOUT",
                message="Worker deadline; no completed public witness was received.",
            ).to_dict(), {"complete": False, "reason": "QUERY_TIMEOUT"}
        packet = receiver.recv()
        if "error" in packet:
            raise RuntimeError(f"{packet['error']}: {packet['message']}")
        return packet["outcome"]
    finally:
        if process.is_alive():
            process.terminate()
        process.join()
        receiver.close()


def _restore_cell(data):
    data = dict(data)
    data["status"] = BatchCellStatus(data["status"])
    data["control_level_attained"] = TargetControlLevel(data["control_level_attained"])
    data["diagnostics"] = tuple(data.get("diagnostics", ()))
    interval = data.get("likelihood_interval")
    data["likelihood_interval"] = tuple(interval) if interval is not None else None
    return SourceGoalCell(**data)


def _atomic_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    # Keep the full audit without concatenating another audit-sized string just
    # to append a newline. Close successfully before publishing the replacement.
    with temporary.open("w", encoding="utf-8") as stream:
        stream.write(json.dumps(data, ensure_ascii=False, sort_keys=True, indent=2))
        stream.write("\n")
    temporary.replace(path)


def run_source_goal_batch(
    request: BatchQueryRequest | Mapping,
    graph: EngineGraph,
    *,
    execution_budget: BatchExecutionBudget | None = None,
    allowed_techniques: Sequence[str] | None = None,
    runtime_facts: Sequence = (),
    checkpoint: str | Path | None = None,
    resume: bool = False,
    checkpoint_interval: int = 1,
    scenario_policy: ScenarioPolicyProfile | str | Path | None = None,
    effort_profile: str | None = None,
    search_order: str = "fifo",
    on_cell=None,
) -> BatchQueryResult:
    """Discover destinations or execute a declared matrix, one compromise at a time.

    Serial execution is intentional. A global expansion cap reduces each next
    query's public expansion budget; partial results retain native guarantees.
    A wall timeout kills an isolated worker, reports unknown/truncated, and is
    never cached as a completed negative. Successful partial witnesses from
    logical caps remain in the public trace and are also rerun on resume.

    Checkpoint interval changes persistence only, not query scope or proofs.
    Default 1 preserves per-cell persistence; every normal exit flushes the cache.
    An interruption may repeat up to N newly cacheable cells, including an
    interrupted atomic flush. Incomplete cells are never cached as negatives.

    An optional existing scenario profile is resolved once, pinned by contents,
    and compiled separately for each query. It must match snapshot and explicitly
    selected evaluation mode; omitted profiles preserve the existing boundary.
    """
    from src.engine.search import validate_search_order

    validate_search_order(search_order)
    if on_cell is not None and not callable(on_cell):
        raise TypeError("on_cell must be callable")
    request = _parse_request(request)
    policy = load_policy_profile(scenario_policy) if scenario_policy is not None else None
    effort = load_effort_profile(effort_profile) if effort_profile is not None else None
    if effort is not None and request.rating_resolution is not None:
        raise ValueError("effort_profile conflicts with explicit rating_resolution")
    policy_input = {}
    if search_order != "fifo":
        policy_input["search_order"] = search_order
    if effort is not None:
        policy_input["effort_profile"] = effort
    if policy is not None:
        expected_mode = "evidence_only" if policy.evaluation_mode == "evidence_only" else "scenario"
        if request.evaluation_mode != expected_mode:
            raise ValueError("SCENARIO_POLICY_MODE_MISMATCH: select the evaluation mode explicitly")
        if policy.bound_snapshot_id != request.snapshot_id:
            raise ValueError("SCENARIO_POLICY_SNAPSHOT_MISMATCH")
        # Pin resolved contents, not an alias or mutable profile file path.
        policy_input["scenario_policy"] = {
            "profile": policy.canonical_dict(),
            "digest": policy.digest(),
        }
    if type(checkpoint_interval) is not int or checkpoint_interval < 1:
        raise ValueError("checkpoint_interval must be a positive integer")
    runtime_facts = _validate_runtime_fact_origins(runtime_facts)
    limits = execution_budget or BatchExecutionBudget()
    goals = _validate_request(request, graph)
    sources = tuple(sorted(request.sources, key=lambda s: s.source_id))
    source_support = {}
    for source in sources:
        try:
            source_support[source.source_id] = source.to_foothold_profile(graph=graph).is_supported
        except ValueError:
            source_support[source.source_id] = False
    techniques = tuple(sorted(set(allowed_techniques))) if allowed_techniques is not None else None
    graph_input = _graph_identity(graph)
    graph_digest = canonical_digest(graph_input)
    pins = execution_source_pins()
    normalized_request = request.to_dict()
    normalized_request["sources"] = [s.to_dict() for s in sources]
    normalized_request["target_goal_ids"] = [g.goal_id for g in goals]
    normalized_request["target_manifest"]["targets"].sort(key=lambda g: g["goal_id"])
    normalized_request["target_manifest"]["default_discovery_goals"].sort()
    scope_digest = canonical_digest(
        {
            "request": normalized_request,
            "graph": graph_digest,
            "source_pins": pins,
            "allowed_techniques": techniques,
            "runtime_facts": wire(runtime_facts),
            "per_query_seconds": limits.per_query_seconds,
            "python": platform.python_version(),
            "execution_version": EXECUTION_VERSION,
            **policy_input,
        }
    )
    checkpoint_path = Path(checkpoint) if checkpoint is not None else None
    cache = {"version": CHECKPOINT_VERSION, "scope_digest": scope_digest, "cells": {}}
    if resume:
        if checkpoint_path is None:
            raise ValueError("resume requires a checkpoint")
        cache = json.loads(checkpoint_path.read_text(encoding="utf-8"))
        if cache.get("version") != CHECKPOINT_VERSION or cache.get("scope_digest") != scope_digest:
            raise ValueError("CHECKPOINT_SCOPE_MISMATCH")
        for packet in cache["cells"].values():
            if packet["sha256"] != canonical_digest(packet["payload"]):
                raise ValueError("CHECKPOINT_CELL_INTEGRITY_MISMATCH")
    started = time.perf_counter()
    executed = expansions = reused = 0
    pending_checkpoint_cells = 0
    matrix = {s.source_id: {} for s in sources}
    traces = {}
    not_run = []
    for source in sources:
        for goal in goals:
            reference = canonical_digest([source.source_id, goal.goal_id])
            remaining = (
                None if limits.max_expansions is None else limits.max_expansions - expansions
            )
            base_budget = source.custom_budget or request.common_budget
            budget = (
                replace(base_budget, max_expansions=min(base_budget.max_expansions, remaining))
                if remaining and remaining > 0
                else base_budget
            )
            # Cached cells always match the original public search policy. A cell
            # run with reduced remaining caps is not eligible for caching.
            fingerprint = canonical_digest(
                {"scope": scope_digest, "cell": reference, "budget": asdict(base_budget)}
            )
            packet = cache["cells"].get(reference)
            stop = (
                (limits.max_cells is not None and executed >= limits.max_cells)
                or (remaining is not None and remaining <= 0)
                or (
                    limits.max_seconds is not None
                    and time.perf_counter() - started >= limits.max_seconds
                )
            )
            if packet is not None and packet["payload"]["fingerprint"] == fingerprint:
                cell = _restore_cell(packet["payload"]["cell"])
                trace = packet["payload"]["trace"]
                if cell.truncated or cell.status == BatchCellStatus.ERROR:
                    raise ValueError("CHECKPOINT_INCOMPLETE_CELL")
                reused += 1
            elif stop:
                cell = _cell(
                    BatchCellStatus.INDETERMINATE,
                    "CELL_NOT_RUN",
                    source_id=source.source_id,
                    goal_id=goal.goal_id,
                )
                trace = {"complete": False, "reason": "GLOBAL_BUDGET", "query_executed": False}
                not_run.append({"source_id": source.source_id, "goal_id": goal.goal_id})
            else:
                executed += 1
                try:
                    query, cell = _query_for_cell(
                        request,
                        source,
                        goal,
                        graph,
                        techniques,
                        budget,
                        runtime_facts,
                        policy,
                        effort,
                        search_order,
                    )
                    if query is None:
                        trace = {
                            "query_executed": False,
                            "adapter_diagnostics": wire(cell.diagnostics),
                        }
                    else:
                        seconds = limits.per_query_seconds
                        if limits.max_seconds is not None:
                            left = max(0.001, limits.max_seconds - (time.perf_counter() - started))
                            seconds = left if seconds is None else min(seconds, left)
                        raw_cell, trace = _execute(query, graph, goal, seconds)
                        cell = _restore_cell(raw_cell)
                except Exception as exc:
                    cell = _cell(
                        BatchCellStatus.ERROR,
                        "CELL_EXECUTION_ERROR",
                        error_type=type(exc).__name__,
                        message=str(exc),
                    )
                    trace = {"complete": False, "reason": "CELL_EXECUTION_ERROR"}
                expansions += cell.expansions
                if (
                    cell.status != BatchCellStatus.ERROR
                    and not cell.truncated
                    and budget == base_budget
                ):
                    payload = {"fingerprint": fingerprint, "cell": cell.to_dict(), "trace": trace}
                    cache["cells"][reference] = {
                        "payload": payload,
                        "sha256": canonical_digest(payload),
                    }
                    pending_checkpoint_cells += 1
                    if (
                        checkpoint_path is not None
                        and pending_checkpoint_cells >= checkpoint_interval
                    ):
                        _atomic_json(checkpoint_path, cache)
                        pending_checkpoint_cells = 0
            # These stable references resolve inside the same result package.
            trace_ref = f"reproducibility.inputs.public_queries.{reference}"
            trace_digest = canonical_digest(trace)
            witness = dict(cell.min_effort_path) if cell.min_effort_path is not None else None
            if witness is not None:
                witness["trace_ref"] = trace_ref
                witness["candidate_id"] = (
                    trace.get("result", {}).get("min_effort", {}).get("best_candidate_id")
                    if trace.get("result", {}).get("min_effort")
                    else None
                )
            cell = replace(
                cell,
                min_effort_path=witness,
                diagnostics=cell.diagnostics
                + ({"code": "PUBLIC_QUERY_TRACE", "trace_ref": trace_ref, "sha256": trace_digest},),
            )
            matrix[source.source_id][goal.goal_id] = cell
            traces[reference] = trace
            if on_cell is not None:
                path = trace.get("result", {}).get("best_path") or next(
                    iter(trace.get("result", {}).get("paths", [])), None
                )
                on_cell(
                    copy.deepcopy(
                        {
                            "version": "discovery-progress/1",
                            "source_id": source.source_id,
                            "goal_id": goal.goal_id,
                            "status": str(cell.status),
                            "reached": cell.final_goal_reached,
                            "C": cell.min_effort,
                            "expansions": cell.expansions,
                            "truncated": cell.truncated,
                            "minimum_proven": bool(
                                trace.get("guarantees", {}).get(
                                    "is_minimum_proven_over_scope", False
                                )
                            ),
                            "search_strategy": trace.get("materialized", {}).get("search_strategy"),
                            "witness": {
                                "nodes": list(path["nodes"]),
                                "steps": [
                                    dict(s["result"]["request"]) for s in path["transition_history"]
                                ],
                            }
                            if path
                            else None,
                        }
                    )
                )
    if canonical_digest(_graph_identity(graph)) != graph_digest:
        raise RuntimeError("SNAPSHOT_MUTATED_DURING_BATCH")
    if checkpoint_path is not None:
        _atomic_json(checkpoint_path, cache)
    ranked, ties = prioritize_sources(matrix, request.target_manifest, sources=sources)
    # Reference priority is a defensive display policy, not an exposure proof.
    # A success in one cell must not erase incomplete/failed/unrun cells in its row.
    corrected = []
    for entry in ranked:
        cells = list(matrix[entry.source_id].values())
        codes = {d.get("code") for cell in cells for d in cell.diagnostics}
        disposition = entry.disposition
        if "CELL_NOT_RUN" in codes:
            disposition = "not_evaluated"
        elif any(c.status == BatchCellStatus.ERROR for c in cells):
            disposition = "error"
        elif any(c.truncated for c in cells):
            disposition = "truncated_incomplete"
        elif any(
            c.status
            in (
                BatchCellStatus.INDETERMINATE,
                BatchCellStatus.CHECKPOINT_REACHED_FINAL_GOAL_INDETERMINATE,
            )
            for c in cells
        ):
            disposition = "indeterminate"
        elif disposition == "proven_no_path" and not all(
            traces[canonical_digest([entry.source_id, gid])]
            .get("guarantees", {})
            .get("is_no_path_proven_over_scope", False)
            for gid in matrix[entry.source_id]
        ):
            disposition = "indeterminate"
        successful = [
            (gid, cell) for gid, cell in matrix[entry.source_id].items() if cell.final_goal_reached
        ]
        representative = (
            min(
                successful,
                key=lambda item: _goal_ranking_key(
                    item[0], item[1], request.target_manifest.get_goal(item[0]).impact_rating
                ),
            )[0]
            if successful
            else None
        )
        extra = {
            "code": "SOURCE_SCOPE",
            "representative_goal_id": representative,
            "declared_goals": len(goals),
            "not_run_goals": sum(
                any(d.get("code") == "CELL_NOT_RUN" for d in c.diagnostics) for c in cells
            ),
        }
        corrected.append(
            replace(
                entry,
                disposition=disposition,
                diagnostics=entry.diagnostics + (extra,),
                explainability=entry.explainability
                + (
                    f" Row disposition: {disposition}; incomplete cells are not safe."
                    if disposition
                    in ("error", "not_evaluated", "indeterminate", "truncated_incomplete")
                    else ""
                ),
            )
        )
    status_counts = dict(
        sorted(Counter(c.status.value for row in matrix.values() for c in row.values()).items())
    )
    unsupported = sum(not supported for supported in source_support.values())
    all_cells = [c for row in matrix.values() for c in row.values()]
    try:
        revision = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip()
    except OSError, subprocess.CalledProcessError:
        revision = "unavailable"
    result = BatchQueryResult(
        batch_id=request.batch_id,
        snapshot_id=request.snapshot_id,
        schema_version=(
            "batch-query-result/1.1.0"
            if any(c.status == BatchCellStatus.UNSUPPORTED_SEMANTICS for c in all_cells)
            else "batch-query-result/1.0.0"
        ),
        reproducibility={
            "revision": revision,
            "inputs": {
                "request": normalized_request,
                "request_digest": canonical_digest(normalized_request),
                "graph_digest": graph_digest,
                "source_pins": pins,
                "scope_digest": scope_digest,
                "public_queries": traces,
                "execution_version": EXECUTION_VERSION,
                "allowed_techniques": techniques,
                "runtime_facts": wire(runtime_facts),
                "per_query_seconds": limits.per_query_seconds,
                **policy_input,
            },
            "runtime": {
                "python": platform.python_version(),
                "elapsed_seconds": time.perf_counter() - started,
                "executed_cells": executed,
                "reused_cells": reused,
                "execution_budget": asdict(limits),
                **(
                    {"checkpoint_interval": checkpoint_interval} if checkpoint_interval != 1 else {}
                ),
            },
        },
        summary={
            "total_sources": len(sources),
            "supported_sources": len(sources) - unsupported,
            "unsupported_sources": unsupported,
            "successful_sources": sum(e.reachable_goals_count > 0 for e in corrected),
            "sources_reaching_tier_0": sum(bool(e.reachable_tier_0_goals) for e in corrected),
            "status_counts": status_counts,
            "declared_cells": len(sources) * len(goals),
            "not_run_cells": not_run,
            "evaluated_cells": len(all_cells) - len(not_run),
            "effort_rated_cells": sum(c.min_effort is not None for c in all_cells),
            "likelihood_rated_cells": sum(c.likelihood_status == "rated" for c in all_cells),
            "successful_cells": sum(c.final_goal_reached for c in all_cells),
            "policy": request.prioritization_policy,
        },
        source_goal_matrix=matrix,
        source_prioritization=tuple(corrected),
        tie_breaking_applied=ties,
    )
    validate_schema(result.to_dict(), "batch-query-result")
    return result


def discover_source(
    request: BatchQueryRequest | Mapping,
    graph: EngineGraph,
    *,
    source_id: str | None = None,
    **execution_options,
) -> BatchQueryResult:
    """Execute one declared source, preserving every request semantic field.

    A one-source request needs no selector. Multi-source requests require an
    explicit source_id; only sources is replaced. Mode, target selection,
    manifest/snapshot, common/custom budgets, policy and rating basis are retained.
    Use target_goal_ids=None/[] in the request for discovery or IDs for drilldown.
    """
    request = _parse_request(request)
    if source_id is None:
        if len(request.sources) != 1:
            raise ValueError("discover_source requires source_id for a multi-source request")
        selected = request.sources
    else:
        selected = tuple(s for s in request.sources if s.source_id == source_id)
        if len(selected) != 1:
            raise ValueError(f"source_id {source_id!r} must identify exactly one declared source")
    return run_source_goal_batch(
        replace(request, sources=selected),
        graph,
        **execution_options,
    )
