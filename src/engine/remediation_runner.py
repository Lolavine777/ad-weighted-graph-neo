"""Evidence-backed before/replay/rediscovery comparisons; no alternative search engine.

The strict report is remediation 1.1.0. Native evidence, execution coverage and
unrated applicability reasons live in the accompanying local result package.
"""

from __future__ import annotations

import json
import multiprocessing
import platform
import time
import uuid
from collections import Counter
from copy import deepcopy
from dataclasses import asdict, replace
from datetime import UTC, datetime
from pathlib import Path

from scripts.research.remediation_acceptance import require, validate_result
from src.engine.batch import BatchExecutionBudget, _atomic_json, execution_source_pins
from src.engine.graph import EngineGraph
from src.engine.query import materialize_query, run_attack_query
from src.engine.remediation import (
    DOC,
    ROOT,
    SUPPORTED,
    ReplayBaseline,
    UnsupportedIntervention,
    _check_edits,
    _decision_audit,
    _digest,
    _facts,
    _value,
    effective_scenario,
    extract_witness,
    prepare_baseline,
    replay_baseline,
    replay_program,
)
from src.engine.semantics.transitions import Status
from src.parser.snapshot_facts import serialize_snapshot

PACKAGE_VERSION = "remediation-package/1"
CHECKPOINT_VERSION = "remediation-checkpoint/1"
PRIORITY_POLICY = "defensive-complete-scope-first/2"


def _source_pins():
    """Include the reviewed remediation transport/verifier and CLI, not only engine code."""
    pins = {path.replace("\\", "/"): value for path, value in execution_source_pins().items()}
    from scripts.research.remediation_acceptance import sha

    for relative in (
        "scripts/research/remediation_acceptance.py",
        "scripts/research/remediation_runner.py",
        "docs/research/remediation/request-v1.1.schema.json",
        "docs/research/remediation/result-v1.1.schema.json",
        "docs/research/remediation/catalog-v1.json",
    ):
        pins[relative] = sha(ROOT / relative)
    return dict(sorted(pins.items()))


def _put(artifacts, value):
    ref = "artifact:" + _digest(value)
    artifacts[ref] = value
    return ref


def _context(material):
    context = material.runtime_context
    return {
        "facts": [_value(context.facts[k]) for k in sorted(context.facts)],
        "authentication_context": context.authentication_context,
        "rbcd_bindings": _value(context.rbcd_bindings),
        "withheld_relationships": _value(context.withheld_relationships),
    }


def _paths(paths, graph, material, cell, comparison, run_id, artifacts):
    traces, identities, all_native = [], set(), []
    for path in paths:
        witness = extract_witness(
            path,
            material,
            graph,
            comparison_scope_digest=comparison,
            source_id=cell["source_id"],
            goal_id=cell["goal_id"],
            observation_id=run_id,
        )
        record = {
            "run_id": run_id,
            "program_id": witness["program_id"],
            "semantic_identity": witness["semantic_identity"],
            "semantic_program": witness["semantic_program"],
            "native_history": _value(path.transition_history),
            "final_state": _value(path.final_state),
            "edge_ids": [e for e in path.transition_edge_ids if e is not None],
            "initial_state": _value(material.initial_attack_state),
            "runtime_context": _context(material),
        }
        ref = _put(artifacts, record)
        all_native.append(ref)
        if witness["semantic_identity"] in identities:
            continue
        identities.add(witness["semantic_identity"])
        traces.append(
            {k: v for k, v in witness.items() if k not in {"semantic_identity", "trace_ref"}}
            | {"trace_ref": ref}
        )
    traces.sort(key=lambda t: (t["program_id"], t["trace_ref"]))
    return traces, all_native


def _query_digest(cell, graph, material, request, side):
    return _digest(
        {
            "public_query": cell["query"],
            "effective_graph": graph.to_canonical(),
            "runtime_context": _context(material),
            "initial_state": _value(material.initial_attack_state),
            "comparison_scope": request["scope"],
            "edits": request["edits"] if side == "after" else [],
        }
    )


def _observation(
    result,
    paths,
    graph,
    material,
    cell,
    request,
    run_id,
    side,
    artifacts,
    *,
    disposition=None,
    diagnostic=None,
    rating_attempt_charge=0,
):
    comparison = _digest(request["scope"])
    traces, native_refs = _paths(paths, graph, material, cell, comparison, run_id, artifacts)
    complete = result.complete if result is not None else False
    truncated = result.truncated if result is not None else False
    unresolved = (
        any(a.status == Status.INDETERMINATE for a in result.attempts)
        if result is not None
        else True
    )
    negative = result.is_no_path_proven_over_scope if result is not None else False
    reachability = (
        "reachable"
        if traces
        else "proven_unreachable"
        if negative
        else "unsupported"
        if result is not None and result.status == "unsupported"
        else disposition
        if disposition in {"unsupported", "error", "not_evaluated"}
        else "unknown"
    )
    query_digest = _query_digest(cell, graph, material, request, side)
    proof_ref = None
    if result is not None:
        proof_ref = _put(
            artifacts,
            {
                "kind": "native-semantic-search/1",
                "run_id": run_id,
                "side": side,
                "source_id": cell["source_id"],
                "goal_id": cell["goal_id"],
                "comparison_scope_digest": comparison,
                "overlay_digest": _digest(request["edits"]) if side == "after" else None,
                "query_digest": query_digest,
                "native_paths": native_refs,
                "attempts": _value(result.attempts),
                "effective_attempt_decisions": [
                    _decision_audit(a, request, [e["edit_id"] for e in request["edits"]])
                    for a in result.attempts
                ]
                if side == "after"
                else [],
                "intervention_origin": "declared_intervention_not_observation"
                if side == "after"
                else None,
                "caps": result.caps,
                "expansions": result.expansions,
                "native_status": result.status,
                "native_complete": complete,
                "native_truncated": truncated,
                "truncation_reason": result.truncation_reason,
                "unresolved_feasibility": unresolved,
                "native_no_path_proven": negative,
                "binding_diagnostics": _value(dict(result.binding_diagnostics)),
                "rating_result": _value(result.ranking_result),
                "min_effort": _value(result.min_effort),
                "is_minimum_proven_over_scope": result.is_minimum_proven_over_scope,
                "rating_configuration": _value(material.rating_resolution),
                "rating_failed_attempt_full_cap": rating_attempt_charge,
            },
        )
    observation = {
        "run_id": run_id,
        "cell_ref": _digest([cell["source_id"], cell["goal_id"]]),
        "query_digest": query_digest,
        "reachability": reachability,
        "complete": complete,
        "truncated": truncated,
        "unresolved_feasibility": unresolved,
        "program_count": len(traces),
        "route_count": len({t["route_id"] for t in traces}),
        "witness_program_ids": [t["program_id"] for t in traces],
        "route_ids": sorted({t["route_id"] for t in traces}),
        "trace_refs": traces,
        "scope_proof_ref": proof_ref,
        "search_diagnostics": ([diagnostic] if diagnostic else [])
        + (["NATIVE_UNKNOWN_FEASIBILITY"] if unresolved else []),
    }
    if side == "after":
        status = (
            "truncated"
            if truncated
            else "complete"
            if complete
            else "error"
            if disposition == "error"
            else "not_run"
        )
        observation["rediscovery"] = {"status": status, "run_id": run_id, "proof_ref": proof_ref}
    return observation


def _after_search(request, cell, graph, run_id):
    before_material = materialize_query(cell["query"], graph)
    view, material, _, _ = effective_scenario(request, graph, before_material)
    unrated_material = material
    refusal, charge = None, 0
    if before_material.rating_resolution is not None:
        config = deepcopy(dict(before_material.rating_resolution))
        config["scope"]["query_id"] = _query_digest(cell, view, material, request, "after")
        material = replace(material, rating_resolution=config)
    try:
        result = material.run(view)
    except (ValueError, TypeError, KeyError) as error:
        if material.rating_resolution is None:
            raise
        refusal = f"FRESH_RATING_REFUSED: {type(error).__name__}: {error}"
        charge = material.budget.max_expansions
        material = unrated_material
        result = material.run(view)
    artifacts = {}
    observation = _observation(
        result,
        result.paths,
        view,
        material,
        cell,
        request,
        run_id,
        "after",
        artifacts,
        diagnostic=refusal,
        rating_attempt_charge=charge,
    )
    return observation, artifacts, result.expansions + charge


def _worker(connection, request, cell, graph_payload, run_id):
    try:
        graph = (
            EngineGraph.from_snapshot(graph_payload)
            if isinstance(graph_payload, str)
            else EngineGraph.from_canonical(graph_payload)
        )
        connection.send({"outcome": _after_search(request, cell, graph, run_id)})
    except Exception as error:
        connection.send({"error": type(error).__name__, "message": str(error)})
    finally:
        connection.close()


def _execute_after(request, cell, graph, run_id, seconds):
    """Same spawn/Pipe/terminate boundary as public batch; views are built in worker."""
    if seconds is None:
        return _after_search(request, cell, graph, run_id)
    context = multiprocessing.get_context("spawn")
    receiver, sender = context.Pipe(duplex=False)
    payload = (
        serialize_snapshot(graph.to_canonical(), graph.snapshot_facts)
        if graph.snapshot_facts is not None
        else graph.to_canonical()
    )
    process = context.Process(target=_worker, args=(sender, request, cell, payload, run_id))
    process.start()
    sender.close()
    try:
        if not receiver.poll(seconds):
            raise TimeoutError("AFTER_QUERY_TIMEOUT: no completed search result received")
        packet = receiver.recv()
        if "error" in packet:
            raise RuntimeError(f"{packet['error']}: {packet['message']}")
        return packet["outcome"]
    finally:
        if process.is_alive():
            process.terminate()
        process.join()
        receiver.close()


def _seed_paths(before, material, prepared, request, active):
    paths = []
    for path in before.paths:
        *_, replayed = replay_program(
            path, before.materialized_query, prepared, material.runtime_context, request, active
        )
        if replayed is not None:
            paths.append(replayed)
    return paths


def _unrated(rated):
    return (
        {
            "status": "incomparable" if rated else "unrated",
            "before": None,
            "after": None,
            "delta": None,
            "unit": None,
            "basis_refs": [],
            "proof_refs": [],
        },
        {
            "status": "incomparable" if rated else "unrated",
            "before_interval": None,
            "after_interval": None,
            "delta_interval": None,
            "before_program_id": None,
            "after_program_id": None,
            "comparison_scope_digest": None,
            "basis_refs": [],
            "interpretation": "conditional_single_program_not_campaign",
        },
    )


def _effort_comparison(before, after, artifacts, cell):
    """Only native automatic resolution can establish fresh comparable effort."""
    value, _ = _unrated(True)
    config = cell["query"].get("rating_resolution")
    if config is None or "effort" not in config.get("registries", {}):
        return value
    proof_before = artifacts.get(before["scope_proof_ref"], {})
    proof_after = artifacts.get(after["scope_proof_ref"], {})
    # Scope is rebound by the native resolver; registries, method/horizon/model
    # and declared outcome remain unchanged. Explicit old packets are refused.
    resolved = proof_after.get("rating_configuration")
    if resolved is None or resolved.get("registries") != config["registries"]:
        return value
    registry = config["registries"]["effort"]
    value["basis_refs"] = [registry["sha256"]]
    value["unit"] = "native_engine_effort_score"
    for side, row, proof in (("before", before, proof_before), ("after", after, proof_after)):
        minimum = (proof.get("min_effort") or {}).get("minimum_effort_value")
        if row["reachability"] == "reachable" and minimum is not None:
            value[side] = minimum
    certified = all(
        proof.get("is_minimum_proven_over_scope")
        and row["complete"]
        and not row["truncated"]
        and not row["unresolved_feasibility"]
        for row, proof in ((before, proof_before), (after, proof_after))
    )
    if value["before"] is not None and value["after"] is not None:
        value["status"] = "exact" if certified else "incumbent"
        if certified:
            value["delta"] = value["after"] - value["before"]
            value["proof_refs"] = [before["scope_proof_ref"], after["scope_proof_ref"]]
    return value


def _report(request, baseline, replay, before_rows, after_rows, replay_ref, applied, artifacts):
    cells = []
    declared = json.loads(baseline.cells_json)
    for index, (cell, before, after) in enumerate(
        zip(declared, before_rows, after_rows, strict=True)
    ):
        programs = replay["cells"][index]["programs"] if replay is not None else []
        cut = sorted(p["baseline"]["program_id"] for p in programs if p["disposition"] == "cut")
        before_semantics = {
            t["program_id"]: _identity(t, cell, request) for t in before["trace_refs"]
        }
        new = sorted(
            t["program_id"]
            for t in after["trace_refs"]
            if _identity(t, cell, request) not in before_semantics.values()
        )
        cut_routes = sorted(
            rid
            for rid in before["route_ids"]
            if rid not in after["route_ids"]
            and all(t["program_id"] in cut for t in before["trace_refs"] if t["route_id"] == rid)
        )
        failures = []
        for pi, program in enumerate(programs):
            if program["disposition"] != "cut":
                continue
            refs = program["steps"][-1]["intervention_refs"]
            ids = sorted(
                e["edit_id"]
                for e in request["edits"]
                if f"intervention:{request['request_id']}/{e['edit_id']}" in refs
            )
            require(bool(ids), "cut lacks explicit intervention decision origin")
            failures.append(
                {
                    "program_id": program["baseline"]["program_id"],
                    "intervention_ids": ids,
                    "trace_ref": f"{replay_ref}#/cells/{index}/programs/{pi}",
                    "decision_ref": f"{replay_ref}#/cells/{index}/programs/{pi}/steps/"
                    f"{program['failure']['step_index']}/decisions",
                }
            )
        rated = any(
            k in cell["query"] and cell["query"][k] is not None
            for k in ("ranking_query", "rating_resolution", "ranking_payload")
        )
        effort, probability = _unrated(rated)
        if rated:
            effort = _effort_comparison(before, after, artifacts, cell)
        cells.append(
            {
                "source_id": cell["source_id"],
                "goal_id": cell["goal_id"],
                "before": before,
                "after": after,
                "affected": bool(cut),
                "affected_program_ids": cut,
                "cut_program_ids": cut,
                "cut_route_ids": cut_routes,
                "replay_failures": failures,
                "bypass_program_ids": after["witness_program_ids"],
                "new_program_ids": new,
                "disconnected": applied
                and before["reachability"] == "reachable"
                and after["reachability"] == "proven_unreachable",
                "effort": effort,
                "conditional_p": probability,
            }
        )
    sources, goals = sorted({c["source_id"] for c in cells}), sorted({c["goal_id"] for c in cells})
    complete = applied and all(
        c[side]["complete"]
        and not c[side]["truncated"]
        and not c[side]["unresolved_feasibility"]
        and c[side]["reachability"] in {"reachable", "proven_unreachable"}
        for c in cells
        for side in ("before", "after")
    )
    scope = "complete_declared_scope" if complete else "observed_corpus_only"

    def fraction(numerator, denominator):
        return {
            "numerator": numerator,
            "denominator": denominator,
            "percent": 100 * numerator / denominator if denominator else None,
            "scope": scope,
        }

    summary = {
        "requested_pairs": len(sources) * len(goals),
        "evaluated_pairs": len(cells),
        "unsupported_pairs": sum(
            any(c[s]["reachability"] == "unsupported" for s in ("before", "after")) for c in cells
        ),
        "unknown_pairs": sum(
            any(
                c[s]["reachability"] in {"unknown", "error", "not_evaluated"}
                for s in ("before", "after")
            )
            for c in cells
        ),
        "truncated_pairs": sum(any(c[s]["truncated"] for s in ("before", "after")) for c in cells),
        "affected_sources": sorted({c["source_id"] for c in cells if c["affected"]}),
        "exposed_sources_before": sorted(
            {c["source_id"] for c in cells if c["before"]["reachability"] == "reachable"}
        ),
        "exposed_sources_after": sorted(
            {c["source_id"] for c in cells if c["after"]["reachability"] == "reachable"}
        ),
        "fully_disconnected_sources": sorted(
            s
            for s in sources
            if any(
                c["source_id"] == s and c["before"]["reachability"] == "reachable" for c in cells
            )
            and all(
                c["after"]["reachability"] == "proven_unreachable"
                for c in cells
                if c["source_id"] == s
            )
        ),
        "goals_still_reachable": sorted(
            {c["goal_id"] for c in cells if c["after"]["reachability"] == "reachable"}
        ),
        "proven_disconnected_pairs": [
            {"source_id": c["source_id"], "goal_id": c["goal_id"]}
            for c in cells
            if c["disconnected"]
        ],
        "programs_cut": fraction(
            sum(len(c["cut_program_ids"]) for c in cells),
            sum(c["before"]["program_count"] for c in cells),
        ),
        "routes_cut": fraction(
            sum(len(c["cut_route_ids"]) for c in cells),
            sum(c["before"]["route_count"] for c in cells),
        ),
        "pairs_disconnected": fraction(
            sum(c["disconnected"] for c in cells),
            sum(c["before"]["reachability"] == "reachable" for c in cells),
        ),
        "limitations": [
            "Declared finite scope; no global choke-point or campaign probability claim.",
            "Returned-path inventory is observed-corpus only; defender costs are unrated.",
            "Old packets are refused; fresh automatic C only; P/I comparison remains pending.",
            "Transport evaluated_pairs counts represented cells; analytics counts execution.",
        ],
    }
    return {
        "schema_version": "1.1.0",
        "request_id": request["request_id"],
        "catalog_digest": request["catalog_digest"],
        "comparison_scope_digest": _digest(request["scope"]),
        "overlay_digest": _digest(request["edits"]),
        "overlay_disposition": "applied" if applied else "unresolved",
        "counterfactual_origin": "declared_intervention_not_observation",
        "baseline_input_digest_after": request["scope"]["graph_digest"],
        "program_identity_version": "semantic-program/1",
        "declared_source_ids": sources,
        "declared_goal_ids": goals,
        "cells": cells,
        "summary": summary,
    }


def _identity(trace, cell, request):
    from scripts.research.remediation_acceptance import normalized_program_identity

    return normalized_program_identity(cell, _digest(request["scope"]), trace)


def _analytics(report, replay):
    cells = report["cells"]
    coverage = {
        side: dict(
            sorted(
                Counter(
                    "truncated" if c[side]["truncated"] else c[side]["reachability"] for c in cells
                ).items()
            )
        )
        for side in ("before", "after")
    }
    status = Counter(c["after"]["rediscovery"]["status"] for c in cells)
    return {
        "declared_pairs": len(cells),
        "configured_goals": report["declared_goal_ids"],
        "after_evaluated_pairs": sum(status[k] for k in ("complete", "truncated", "error")),
        "after_not_run_pairs": status["not_run"],
        "rediscovery_status_counts": dict(sorted(status.items())),
        "coverage": coverage,
        "unresolved_feasibility_counts": {
            side: sum(c[side]["unresolved_feasibility"] for c in cells)
            for side in ("before", "after")
        },
        "complete_discovery_counts": {
            side: sum(c[side]["complete"] for c in cells) for side in ("before", "after")
        },
        "unknown_replay_programs": sum(
            p["disposition"] in {"indeterminate", "error"}
            for c in replay["cells"]
            for p in c["programs"]
        )
        if replay
        else 0,
        "retained_after_programs": sum(
            c["after"]["program_count"] - len(c["new_program_ids"]) for c in cells
        ),
        "new_after_programs": sum(len(c["new_program_ids"]) for c in cells),
        "numeric_comparison": {
            "effort_status_counts": dict(
                sorted(Counter(c["effort"]["status"] for c in cells).items())
            ),
            "probability": "pending_reviewed_cross_intervention_comparability",
            "defender_cost": None,
            "operational_impact": None,
            "impact_comparison": None,
        },
        "priority_policy": PRIORITY_POLICY,
    }


def run_remediation(
    request, graph, baseline, *, execution_budget=None, checkpoint=None, resume=False
):
    """Run #283 then native rediscovery for every declared cell, and audit actual proofs.

    Batch budgets count newly scheduled after cells. Completed checkpoint cells
    are re-executed for proof verification, reported separately as audit work.
    Validation/replay/audit are outside the after-worker wall deadline.
    """
    started = time.perf_counter()
    started_at = datetime.now(UTC).isoformat()
    request = deepcopy(request)
    limits = execution_budget or BatchExecutionBudget()
    cells = json.loads(baseline.cells_json)
    keys = {(c["source_id"], c["goal_id"]) for c in cells}
    require(
        len(keys) == len({k[0] for k in keys}) * len({k[1] for k in keys}),
        "baseline must represent the entire declared source-goal product",
    )
    graph_before = _digest([graph.to_canonical(), _facts(graph)])
    try:
        replay = replay_baseline(request, graph, baseline)
        unsupported = None
    except UnsupportedIntervention as error:
        # Still validate the exact baseline scope with actual public reproduction.
        from src.engine.remediation import prepare_baseline

        actual = prepare_baseline(graph, cells, run_id=baseline.run_id)
        require(
            actual == baseline
            and request["scope"] == baseline.scope
            and request["baseline_run_id"] == baseline.run_id,
            "unsupported baseline pins mismatch",
        )
        replay, unsupported = None, str(error)
    artifacts = {}
    replay_ref = _put(artifacts, replay) if replay else None
    pins = _source_pins()
    cache_scope = _digest(
        {
            "request": request,
            "baseline": asdict(baseline),
            "code": pins,
            "python": platform.python_version(),
            "per_query_seconds": limits.per_query_seconds,
        }
    )
    cache = {"version": CHECKPOINT_VERSION, "scope_digest": cache_scope, "cells": {}}
    path = Path(checkpoint) if checkpoint is not None else None
    if resume:
        require(path is not None, "resume requires checkpoint")
        cache = json.loads(path.read_text(encoding="utf-8"))
        require(
            cache["version"] == CHECKPOINT_VERSION and cache["scope_digest"] == cache_scope,
            "CHECKPOINT_SCOPE_MISMATCH",
        )
        require(
            all(_digest(p["payload"]) == p["sha256"] for p in cache["cells"].values()),
            "CHECKPOINT_CELL_INTEGRITY_MISMATCH",
        )
    before_rows, after_rows = [], []
    executed = expansions = reported_expansions = reused = 0
    after_started = time.perf_counter()
    for index, cell in enumerate(cells):
        before = run_attack_query(cell["query"], graph)
        material = before.materialized_query
        reserved = material.budget.max_expansions * (2 if material.rating_resolution else 1)
        before_rows.append(
            _observation(
                before,
                before.paths,
                graph,
                material,
                cell,
                request,
                f"{baseline.run_id}/{index}",
                "before",
                artifacts,
            )
        )
        run_id = "after-" + uuid.uuid4().hex
        key = _digest([cell["source_id"], cell["goal_id"]])
        packet = cache["cells"].get(key)
        stop = (
            (limits.max_cells is not None and executed >= limits.max_cells)
            or (limits.max_expansions is not None and limits.max_expansions - expansions < reserved)
            or (
                limits.max_seconds is not None
                and time.perf_counter() - after_started >= limits.max_seconds
            )
        )
        if packet is not None:
            payload = packet["payload"]
            row, stored, used = payload["outcome"]
            actual = _after_search(request, cell, graph, row["run_id"])
            require(
                _digest(actual) == _digest(payload["outcome"]), "CHECKPOINT_NATIVE_PROOF_MISMATCH"
            )
            artifacts.update(stored)
            reused += 1
        elif unsupported is not None:
            row = _observation(
                None,
                (),
                graph,
                material,
                cell,
                request,
                run_id,
                "after",
                artifacts,
                disposition="unsupported",
                diagnostic=unsupported,
            )
        else:
            view, effective, prepared, active = effective_scenario(request, graph, material)
            seeds = _seed_paths(before, effective, prepared, request, active)
            if stop:
                row = _observation(
                    None,
                    seeds,
                    view,
                    effective,
                    cell,
                    request,
                    run_id,
                    "after",
                    artifacts,
                    disposition="not_evaluated",
                    diagnostic="AFTER_CELL_NOT_RUN: execution budget",
                )
            else:
                executed += 1
                seconds = limits.per_query_seconds
                if limits.max_seconds is not None:
                    left = max(0.001, limits.max_seconds - (time.perf_counter() - after_started))
                    seconds = left if seconds is None else min(seconds, left)
                try:
                    row, stored, used = _execute_after(request, cell, graph, run_id, seconds)
                    artifacts.update(stored)
                    expansions += used
                    reported_expansions += stored[row["scope_proof_ref"]]["expansions"]
                    if row["complete"]:
                        payload = {"outcome": (row, stored, used)}
                        cache["cells"][key] = {"payload": payload, "sha256": _digest(payload)}
                except Exception as error:
                    expansions += reserved
                    row = _observation(
                        None,
                        seeds,
                        view,
                        effective,
                        cell,
                        request,
                        run_id,
                        "after",
                        artifacts,
                        disposition="error",
                        diagnostic=f"{type(error).__name__}: {error}",
                    )
        after_rows.append(row)
        if path is not None:
            _atomic_json(path, cache)
    report = _report(
        request,
        baseline,
        replay,
        before_rows,
        after_rows,
        replay_ref,
        unsupported is None,
        artifacts,
    )
    validate_result(report)
    require(
        graph_before == _digest([graph.to_canonical(), _facts(graph)]), "raw graph/facts mutated"
    )
    package = {
        "schema_version": PACKAGE_VERSION,
        "request": request,
        "baseline": asdict(baseline),
        "report": report,
        "replay_ref": replay_ref,
        "artifacts": artifacts,
        "analytics": _analytics(report, replay),
        "execution": {
            "started_at": started_at,
            "elapsed_seconds": time.perf_counter() - started,
            "after_executed_cells": executed,
            "cache_audit_reexecuted_cells": reused,
            "new_after_expansions": reported_expansions,
            "charged_expansion_budget": expansions,
            "unknown_expansion_accounting": "Failed workers charged their full reserved cap.",
            "budget": asdict(limits),
            "python": platform.python_version(),
            "platform": platform.platform(),
            "source_pins": pins,
        },
    }
    verify_package(package, graph)
    package["execution"]["elapsed_seconds"] = time.perf_counter() - started
    return package


def verify_package(package, graph):
    """Independently reproduce native searches and #283 replay, never trust proof flags.

    Error/unrun cells are verified through their retained replay witnesses and
    cannot acquire a negative proof. Wall-clock boundary parity is not claimed.
    """
    require(package["schema_version"] == PACKAGE_VERSION, "wrong package version")
    request, report, artifacts = package["request"], package["report"], package["artifacts"]
    validate_result(report)
    require(package["execution"]["source_pins"] == _source_pins(), "package code pins mismatch")
    require(
        all(ref == "artifact:" + _digest(value) for ref, value in artifacts.items()),
        "artifact digest mismatch",
    )
    baseline = ReplayBaseline(**package["baseline"])
    cells = json.loads(baseline.cells_json)
    try:
        replay = replay_baseline(request, graph, baseline)
        require(artifacts[package["replay_ref"]] == replay, "native replay artifact mismatch")
        applied = True
    except UnsupportedIntervention:
        replay, applied = None, False
        require(
            prepare_baseline(graph, json.loads(baseline.cells_json), run_id=baseline.run_id)
            == baseline
            and request["scope"] == baseline.scope
            and request["baseline_run_id"] == baseline.run_id,
            "unsupported baseline pins mismatch",
        )
        require(package["replay_ref"] is None, "unsupported overlay has replay artifact")
    before_rows, after_rows, checked = [], [], {}
    for cell, row in zip(cells, report["cells"], strict=True):
        require(
            (cell["source_id"], cell["goal_id"]) == (row["source_id"], row["goal_id"]),
            "cell binding mismatch",
        )
        native = run_attack_query(cell["query"], graph)
        material = native.materialized_query
        before = _observation(
            native,
            native.paths,
            graph,
            material,
            cell,
            request,
            row["before"]["run_id"],
            "before",
            checked,
        )
        require(before == row["before"], "before native proof mismatch")
        before_rows.append(before)
        after = row["after"]
        if after["rediscovery"]["status"] in {"complete", "truncated"}:
            require(applied, "unapplied overlay has discovery proof")
            reproduced, data, _ = _after_search(request, cell, graph, after["run_id"])
            checked.update(data)
            require(reproduced == after, "after native proof mismatch")
        elif applied:
            view, effective, prepared, active = effective_scenario(request, graph, material)
            seeds = _seed_paths(native, effective, prepared, request, active)
            # Preserve the recorded wall failure reason, not any claimed negative result.
            reproduced = _observation(
                None,
                seeds,
                view,
                effective,
                cell,
                request,
                after["run_id"],
                "after",
                checked,
                disposition="error"
                if after["rediscovery"]["status"] == "error"
                else "not_evaluated",
                diagnostic=after["search_diagnostics"][0],
            )
            require(reproduced == after, "unrun/error retained witness mismatch")
        else:
            require(
                after["reachability"] == "unsupported"
                and not after["trace_refs"]
                and after["scope_proof_ref"] is None,
                "unsupported overlay has success/negative proof",
            )
        after_rows.append(after)
    require(
        all(artifacts.get(ref) == data for ref, data in checked.items()),
        "native artifact contents mismatch",
    )
    expected = _report(
        request,
        baseline,
        replay,
        before_rows,
        after_rows,
        package["replay_ref"],
        applied,
        artifacts,
    )
    require(expected == report, "report/native evidence mismatch")
    require(package["analytics"] == _analytics(expected, replay), "analytics denominator mismatch")
    return {
        "status": "verified",
        "method": "native_search_and_replay_reproduction",
        "declared_cells": len(cells),
    }


def rank_interventions(packages):
    """Named defensive display policy; incomplete zero-witness runs are not safe."""
    require(
        len({p["report"]["comparison_scope_digest"] for p in packages}) <= 1,
        "priority needs one comparison scope",
    )
    rows = []
    for package in packages:
        report = package["report"]
        incomplete = sum(
            not c[s]["complete"]
            or c[s]["unresolved_feasibility"]
            or c[s]["reachability"] in {"error", "unsupported", "not_evaluated"}
            for c in report["cells"]
            for s in ("before", "after")
        )
        summary = report["summary"]
        quantities = {
            "incomplete_observations": incomplete,
            "proven_disconnected_pairs": summary["pairs_disconnected"]["numerator"],
            # A missing witness is not evidence of safety. Count each unresolved
            # source-goal cell, even if another goal proves that source exposed.
            "unresolved_after_pairs": sum(
                c["after"]["reachability"] not in {"reachable", "proven_unreachable"}
                for c in report["cells"]
            ),
            "remaining_exposed_sources": len(summary["exposed_sources_after"]),
            "observed_programs_cut": summary["programs_cut"]["numerator"],
        }
        rows.append(
            {
                "intervention": report["request_id"],
                "policy": PRIORITY_POLICY,
                "quantities": quantities,
                "configured_goals": report["declared_goal_ids"],
                "rationale": (
                    "Prefer complete evidence, then more proven disconnections, "
                    "fewer unresolved after pairs, fewer exposed sources, more observed cuts; "
                    "tie by intervention ID."
                ),
                "defender_cost": None,
                "operational_impact": None,
            }
        )
    rows.sort(
        key=lambda r: (
            r["quantities"]["incomplete_observations"],
            -r["quantities"]["proven_disconnected_pairs"],
            r["quantities"]["unresolved_after_pairs"],
            r["quantities"]["remaining_exposed_sources"],
            -r["quantities"]["observed_programs_cut"],
            r["intervention"],
        )
    )
    return [{"rank": i, **row} for i, row in enumerate(rows, 1)]


def expand_individual_interventions(baseline, requests):
    """Keep selected sets and explicit individual experiments separate; never add effects."""
    from src.engine.remediation import request_for_baseline

    expanded = list(requests)
    for request in requests:
        if len(request["edits"]) < 2:
            continue
        for edit in sorted(request["edits"], key=lambda e: e["edit_id"]):
            expanded.append(
                request_for_baseline(
                    baseline,
                    [edit],
                    request_id=f"{request['request_id']}:individual:{edit['edit_id']}",
                )
            )
    require(len({r["request_id"] for r in expanded}) == len(expanded), "duplicate intervention IDs")
    return sorted(expanded, key=lambda r: r["request_id"])


def inventory_interventions(graph, baseline):
    """Observed-scope inventory from edges AND native prerequisites/producers.

    This does not enumerate all possible interventions or authorize live changes.
    Unsupported entries remain visible with their technical preconditions.
    """
    cells = json.loads(baseline.cells_json)
    require(
        prepare_baseline(graph, cells, run_id=baseline.run_id) == baseline,
        "inventory baseline input mismatch",
    )
    catalog = json.loads((DOC / "catalog-v1.json").read_text(encoding="utf-8"))["entries"]
    inventory = {}
    materials = []

    def add(entry, edits, cell, program_id, prerequisites):
        technical = {"catalog_entry_id": entry["id"], "edits": edits}
        key = _digest(technical)
        if key not in inventory:
            tagged = [{"edit_id": f"inventory-{key[-12:]}-{i}", **e} for i, e in enumerate(edits)]
            inventory[key] = {
                "candidate_id": key,
                "catalog_entry_id": entry["id"],
                "technical_edits": tagged,
                "status": "supported" if entry["id"] in SUPPORTED and tagged else "unsupported",
                "reason": "Observed native support; exact before evidence must revalidate."
                if entry["id"] in SUPPORTED and tagged
                else "Executor adapter or new reviewed basis required.",
                "required_evidence": entry["required_evidence"],
                "support_scope": "native_declared_model_not_live_AD",
                "prerequisites": sorted(prerequisites),
                "observed_bindings": [],
            }
        binding = {
            "source_id": cell["source_id"],
            "goal_id": cell["goal_id"],
            "program_id": program_id,
        }
        if binding not in inventory[key]["observed_bindings"]:
            inventory[key]["observed_bindings"].append(binding)
        inventory[key]["prerequisites"] = sorted(
            set(inventory[key]["prerequisites"]) | set(prerequisites)
        )

    for cell in cells:
        result = run_attack_query(cell["query"], graph)
        material = result.materialized_query
        materials.append(material)
        for path in result.paths:
            from src.engine.program_identity import program_id, program_key

            pid = program_id(program_key(path))
            for step in path.transition_history:
                for entry in catalog:
                    if step.result.request.technique_id not in entry["techniques"]:
                        continue
                    common = {
                        "catalog_entry_id": entry["id"],
                        "rationale": (
                            "Observed-scope counterfactual candidate; "
                            "validate operational prerequisites separately."
                        ),
                    }
                    if entry["layer"] == "relationship" and step.edge_id is not None:
                        edge = graph.edge(step.edge_id)
                        if edge["kind"] in entry["relationships"]:
                            add(
                                entry,
                                [
                                    {
                                        **common,
                                        "kind": "deny_relationship",
                                        "edge_id": edge["id"],
                                        "relationship": {
                                            k: edge[k] for k in ("source", "kind", "target")
                                        },
                                        "provenance_digest": _digest(edge["provenance"]),
                                        "effective_right_verified": True,
                                        "evidence_refs": [edge["id"]],
                                    }
                                ],
                                cell,
                                pid,
                                step.result.technique.prerequisites,
                            )
                    if entry["layer"] == "runtime" or entry["id"] == "group-membership":
                        for decision in step.result.decisions:
                            fact = decision.fact
                            if (
                                fact is None
                                or fact.predicate not in entry["predicates"]
                                or fact.value is not True
                            ):
                                continue
                            add(
                                entry,
                                [
                                    {
                                        **common,
                                        "kind": "runtime_fact_replace",
                                        "expected_before": True,
                                        "after": False,
                                        "declaration": "counterfactual_intervention",
                                        "evidence_refs": [
                                            fact.provenance_reference or _digest(fact)
                                        ],
                                        "key": {
                                            "predicate": fact.predicate,
                                            "subject": fact.subject,
                                            "target": fact.target,
                                            "binding_id": None,
                                            "authentication_context": (
                                                material.runtime_context.authentication_context
                                            ),
                                        },
                                    }
                                ],
                                cell,
                                pid,
                                step.result.technique.prerequisites,
                            )
                    if entry["layer"] == "snapshot_fact" and graph.snapshot_facts is not None:
                        subject = (
                            step.result.request.rbcd_binding.principal
                            if step.result.request.rbcd_binding
                            else step.result.request.target
                        )
                        facts = [
                            graph.snapshot_facts.lookup(subject, name)
                            for name in entry["predicates"]
                        ]
                        if not all(f.status == "known" and bool(f.value) for f in facts):
                            continue
                        add(
                            entry,
                            [
                                {
                                    **common,
                                    "kind": "snapshot_fact_replace",
                                    "subject": subject,
                                    "name": f.name,
                                    "expected_before": _value(f.value),
                                    "after": [] if f.name == "service_principal_names" else False,
                                    "evidence_digest": _digest(f.evidence),
                                    "evidence_refs": [_digest(f.evidence)],
                                    "declaration": "counterfactual_intervention",
                                }
                                for f in facts
                            ],
                            cell,
                            pid,
                            step.result.technique.prerequisites,
                        )
                    if entry["layer"] == "advisory":
                        add(entry, [], cell, pid, entry["required_evidence"])
    for item in inventory.values():
        if item["status"] == "supported":
            # A prerequisite seen in one witness is not sufficient authority to
            # edit every baseline cell. Reuse the executor's existing boundary
            # checks (including authentication context and expected-before),
            # retaining refused proposals for audit instead of crashing later.
            try:
                _check_edits({"edits": item["technical_edits"]}, graph, materials)
            except (ValueError, UnsupportedIntervention) as error:
                item["status"] = "unsupported"
                item["reason"] = f"Baseline edit binding refused: {error}"
        item["observed_bindings"].sort(
            key=lambda v: (v["source_id"], v["goal_id"], v["program_id"])
        )
    return {
        "scope": "observed_baseline_corpus_only",
        "comparison_scope_digest": _digest(baseline.scope),
        "candidates": [inventory[k] for k in sorted(inventory)],
        "limitations": [
            "Not exhaustive fixes/global choke points; no default node deletion.",
            "Defender cost and operational impact require separate reviewed basis.",
        ],
    }


def requests_from_inventory(baseline, inventory, *, limit):
    """Select bounded, independently replayable experiments from native support.

    Binding coverage orders experiments only; effectiveness is established by
    counterfactual replay plus rediscovery, never by the inventory's frequency.
    Unsupported candidates remain in the inventory and are never silently run.
    """
    from src.engine.remediation import request_for_baseline

    if type(limit) is not int or limit < 1:
        raise ValueError("inventory experiment limit must be a positive integer")
    require(
        inventory["comparison_scope_digest"] == _digest(baseline.scope),
        "inventory comparison scope differs from baseline",
    )
    candidates = sorted(
        (c for c in inventory["candidates"] if c["status"] == "supported" and c["technical_edits"]),
        key=lambda c: (-len(c["observed_bindings"]), c["candidate_id"]),
    )
    return [
        request_for_baseline(
            baseline,
            candidate["technical_edits"],
            request_id=f"discovered:{candidate['candidate_id']}",
        )
        for candidate in candidates[:limit]
    ]
