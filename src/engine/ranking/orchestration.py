"""Orchestrate #145 search candidates through the canonical PathRankingEngine.

This module owns only the handoff. Graph traversal remains in the graph/search layer,
and all replay, scoring, Pareto, and Min-Effort behavior remains in PathRankingEngine.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping, Sequence
from copy import deepcopy
from typing import Any

from scripts.check_contract import load_contract, validate_graph
from src.engine.graph import EngineGraph
from src.engine.ranking import (
    PathRankingEngine,
    RankingValidationError,
    decode_ranking_query,
    encode_ranking_result,
    validate_candidate_envelope,
    validate_upstream_coverage,
)
from src.engine.ranking.adapter_145 import adapt_search_candidate
from src.engine.semantics.models import Technique


def _field(value: Any, name: str, default: Any = None) -> Any:
    if isinstance(value, Mapping):
        return value.get(name, default)
    return getattr(value, name, default)


def coverage_from_search_result(search_result: Any, budget: Any) -> dict[str, Any]:
    """Translate #146 AttackSearchResult plus its SearchBudget to ranking coverage."""
    paths = _field(search_result, "paths")
    truncated = _field(search_result, "truncated")
    expansions = _field(search_result, "expansions")
    truncation_reason = _field(search_result, "truncation_reason")
    if not isinstance(paths, Sequence) or isinstance(paths, (str, bytes)):
        raise TypeError("search_result.paths must be a sequence")
    if not isinstance(truncated, bool):
        raise TypeError("search_result.truncated must be a boolean")
    if type(expansions) is not int or expansions < 0:
        raise TypeError("search_result.expansions must be a non-negative integer")
    if truncation_reason is not None and (
        not isinstance(truncation_reason, str) or not truncation_reason.strip()
    ):
        raise TypeError("search_result.truncation_reason must be a non-empty string or null")

    raw_caps = {name: _field(budget, name) for name in ("max_paths", "max_steps", "max_expansions")}
    if any(type(value) is not int or value < 1 for value in raw_caps.values()):
        raise TypeError("search budget must provide positive max_paths/max_steps/max_expansions")
    caps = {
        "max_candidates": raw_caps["max_paths"],
        "max_steps": raw_caps["max_steps"],
        "max_expansions": raw_caps["max_expansions"],
    }

    reason_mapping = {
        "path_limit_reached": "candidate_limit_reached",
        "candidate_limit_reached": "candidate_limit_reached",
        "expansion_limit_reached": "expansion_limit_reached",
        "step_limit_reached": "step_limit_reached",
    }
    reasons: list[str] = []
    if not truncated:
        if truncation_reason is not None:
            raise RankingValidationError(
                "search result is not truncated but provides truncation_reason "
                f"{truncation_reason!r}"
            )
    elif truncation_reason is not None:
        mapped_reason = reason_mapping.get(truncation_reason)
        if mapped_reason is None:
            raise RankingValidationError(
                f"unsupported search truncation_reason {truncation_reason!r}; "
                f"expected one of {sorted(reason_mapping)!r}"
            )
        reasons.append(mapped_reason)
    else:
        # Backward-compatible fail-closed support for older #146 result shapes that
        # predate explicit truncation_reason. Infer only causes proven by counters.
        if expansions >= raw_caps["max_expansions"]:
            reasons.append("expansion_limit_reached")
        if len(paths) >= raw_caps["max_paths"]:
            reasons.append("candidate_limit_reached")
        if not reasons:
            raise RankingValidationError(
                "search result is truncated but does not provide truncation_reason and "
                "does not identify a reached candidate or expansion budget; refusing to "
                "invent a truncation reason"
            )
    return {
        "is_truncated": truncated,
        "truncation_reasons": reasons,
        "completeness_scope": "partial_truncated" if truncated else "budget_bounded",
        "caps_applied": caps,
        "search_expansions": expansions,
        "candidates_found": len(paths),
    }


def _hydrate_path_edges(path: Any, graph: Mapping[str, Any]) -> dict[str, Any]:
    """Use exact step edge IDs to attach canonical graph records to a serialized path."""
    edge_records = graph.get("edges")
    if not isinstance(edge_records, list):
        raise RankingValidationError("canonical_graph must provide an edges array")
    by_id: dict[str, dict[str, Any]] = {}
    for edge in edge_records:
        if not isinstance(edge, dict) or not isinstance(edge.get("id"), str):
            raise RankingValidationError("canonical_graph contains an edge without an ID")
        if edge["id"] in by_id:
            raise RankingValidationError(
                f"canonical_graph contains duplicate edge ID {edge['id']!r}"
            )
        by_id[edge["id"]] = edge

    history = _field(path, "transition_history", ()) or ()
    selected: list[dict[str, Any]] = []
    seen: set[str] = set()
    for idx, step in enumerate(history):
        edge_id = _field(step, "edge_id")
        if edge_id is None:
            # #145 uses None for branch-local derived transitions. They carry no graph evidence.
            continue
        if not isinstance(edge_id, str) or not edge_id:
            raise RankingValidationError(f"Transition step {idx} has an invalid edge ID")
        if edge_id not in by_id:
            raise RankingValidationError(
                f"Transition step {idx} edge {edge_id!r} is absent from canonical_graph"
            )
        if edge_id not in seen:
            selected.append(deepcopy(by_id[edge_id]))
            seen.add(edge_id)

    return {
        "nodes": deepcopy(_field(path, "nodes", ())),
        "edges": selected,
        "transition_history": history,
        "scenario_reference": _field(path, "scenario_reference"),
        "goal_target": _field(path, "goal_target"),
        "runtime_context": _field(path, "runtime_context"),
        "final_state": _field(path, "final_state"),
    }


def _adapter_diagnostic(candidate_id: str, error: Exception) -> dict[str, Any]:
    message = str(error)
    code = "candidate_binding_invalid"
    if "no explicit mapping" in message or "missing required technique identifier" in message:
        code = "action_binding_missing"
    elif "success-event binding" in message:
        code = "success_event_binding_missing"
    return {
        "reasons": ["adapter_ineligible", code],
        "assessment": {
            "candidate_id": candidate_id,
            "status": "unknown",
            "effort": None,
            "likelihood_interval": None,
            "diagnostic": message,
        },
    }


def evaluate_search_candidates(
    query_payload: dict[str, Any],
    search_candidates: Sequence[dict[str, Any]],
    *,
    action_mapping: dict[str, str] | list[str] | None = None,
    canonical_graph: dict[str, Any] | None = None,
    coverage: dict[str, Any] | None = None,
    snapshot_facts: Any = None,
    catalog: Sequence[Technique] | None = None,
    engine_graph: EngineGraph | None = None,
    prepared: Any = None,
) -> dict[str, Any]:
    """Adapt explicit #145 PathResults and rank them with the single canonical evaluator.

    A missing coverage record is disclosed as ``unspecified_subset``. Callers must pass
    the search layer's caps/truncation metadata to make stronger coverage claims.
    Candidates with missing or contradictory bindings are retained in diagnostics only.
    """
    if not isinstance(query_payload, dict):
        raise TypeError("query_payload must be a PathRankingQuery object")
    if not isinstance(search_candidates, Sequence) or isinstance(search_candidates, (str, bytes)):
        raise TypeError("search_candidates must be a sequence")

    if engine_graph is not None:
        owned_canonical = (
            engine_graph._canonical_cache
            if hasattr(engine_graph, "_canonical_cache")
            and engine_graph._canonical_cache is not None
            else engine_graph.to_canonical()
        )
        if canonical_graph is None:
            canonical_graph = owned_canonical
        elif not isinstance(canonical_graph, dict):
            raise TypeError("canonical_graph must be a canonical Graph JSON object")
        elif canonical_graph is not owned_canonical and canonical_graph != owned_canonical:
            raise RankingValidationError("canonical_graph does not match supplied engine_graph")
        if snapshot_facts is not None and snapshot_facts != engine_graph.snapshot_facts:
            raise RankingValidationError("snapshot facts do not match supplied engine_graph")

    if canonical_graph is not None:
        if not isinstance(canonical_graph, dict):
            raise TypeError("canonical_graph must be a canonical Graph JSON object")
        if engine_graph is None:
            contract = load_contract()
            validate_graph(canonical_graph, contract)
        graph_snapshot = canonical_graph["metadata"].get("snapshot_id")
        query_snapshot = query_payload.get("query_metadata", {}).get("snapshot_id")
        if graph_snapshot != query_snapshot:
            raise RankingValidationError(
                "canonical_graph snapshot_id does not match PathRankingQuery snapshot_id"
            )

    normalized_coverage = validate_upstream_coverage(coverage) if coverage is not None else None

    seen_ids: set[str] = set()
    adapted: list[dict[str, Any]] = []
    semantic_bindings = {}
    candidate_audits: dict[str, dict[str, Any]] = {}
    adapter_diagnostics: dict[str, dict[str, Any]] = {}
    replay_graph: EngineGraph | None = engine_graph
    replay_prepared: Any = prepared
    metadata_for_adapter = {
        **query_payload.get("query_metadata", {}),
        "target_impact_assessments": query_payload.get("target_impact_assessments", {}),
    }

    for idx, item in enumerate(search_candidates):
        if not isinstance(item, dict):
            raise TypeError(f"search candidate at index {idx} must be an object")
        raw_id = item.get("candidate_id")
        if not isinstance(raw_id, str) or not raw_id.strip():
            candidate_id = f"candidate_index_{idx}"
            adapter_diagnostics[candidate_id] = {
                "reasons": ["adapter_ineligible", "candidate_id_missing"],
                "assessment": {
                    "candidate_id": candidate_id,
                    "status": "unknown",
                    "effort": None,
                    "likelihood_interval": None,
                    "diagnostic": "search candidate requires an explicit non-empty candidate_id",
                },
            }
            continue
        candidate_id = raw_id
        if candidate_id in seen_ids:
            raise RankingValidationError(f"Duplicate search candidate_id: {candidate_id!r}")
        seen_ids.add(candidate_id)

        try:
            path = item.get("path_result")
            if path is None:
                raise RankingValidationError("search candidate is missing path_result")
            from src.engine.ranking.verification import verify_search_envelope
            from src.engine.semantics.credentials import OWNERS
            from src.engine.semantics.rbcd import OWNERS as RBCD_OWNERS

            history = _field(path, "transition_history", ())
            replay_owners = OWNERS | RBCD_OWNERS
            replay_required = (
                metadata_for_adapter.get("semantic_goal") is not None
                or _field(path, "goal_target") is not None
                or any(
                    _field(_field(_field(step, "result"), "request"), "technique_id")
                    in replay_owners
                    for step in history
                )
                or bool(
                    history
                    and (
                        _field(_field(_field(history[0], "result"), "request"), "actor")
                        or _field(_field(_field(history[0], "result"), "request"), "source")
                        or metadata_for_adapter["foothold_node_id"]
                    )
                    != metadata_for_adapter["foothold_node_id"]
                )
            )
            typed_path = path
            if replay_required:
                if canonical_graph is None:
                    raise RankingValidationError("artifact replay requires the canonical graph")
            if canonical_graph is not None:
                path = _hydrate_path_edges(path, canonical_graph)
            candidate_mapping = item.get("action_mapping", action_mapping)
            if not isinstance(candidate_mapping, (dict, list)):
                raise RankingValidationError("candidate requires an explicit action_mapping")
            target_id = item.get("target_asset_id")
            route_id = item.get("route_id", f"route_{candidate_id}")
            if not isinstance(target_id, str) or not target_id.strip():
                raise RankingValidationError("candidate requires an explicit target_asset_id")
            envelope = adapt_search_candidate(
                path_result=path,
                candidate_id=candidate_id,
                target_asset_id=target_id,
                query_metadata=metadata_for_adapter,
                action_mapping=candidate_mapping,
                route_id=route_id,
                bound_actions_catalog=query_payload.get("bound_actions"),
            )
            envelope["search_coverage"] = deepcopy(normalized_coverage)
            if replay_required:
                if replay_graph is None:
                    replay_graph = (
                        engine_graph
                        if engine_graph is not None
                        else EngineGraph.from_canonical(
                            canonical_graph, snapshot_facts=snapshot_facts, _validated=True
                        )
                    )
                if replay_prepared is None:
                    if prepared is not None:
                        replay_prepared = prepared
                    elif hasattr(replay_graph, "to_prepared"):
                        replay_prepared = replay_graph.to_prepared()
                    else:
                        from src.engine.semantics.evaluator import PreparedSemanticGraph

                        replay_prepared = PreparedSemanticGraph(
                            canonical_graph, snapshot_facts=snapshot_facts
                        )
                semantic_bindings[candidate_id] = verify_search_envelope(
                    typed_path,
                    replay_graph,
                    envelope,
                    query_payload["query_metadata"],
                    catalog=catalog,
                    prepared=replay_prepared,
                )
            adapted.append(envelope)
            candidate_audits[candidate_id] = {
                "initial_actor_binding": (
                    semantic_bindings[candidate_id].initial_actor_audit
                    if candidate_id in semantic_bindings
                    else None
                ),
                "target_binding": envelope["target_binding"],
                "success_event_binding": envelope["success_event_binding"],
                "scenario_reference": envelope["scenario_reference"],
                "runtime_fact_values": envelope["runtime_fact_values"],
                "transition_lineage": deepcopy(envelope.get("transition_lineage")),
                "transition_audit": envelope["transition_audit"],
            }
        except (RankingValidationError, TypeError, ValueError, KeyError, AttributeError) as error:
            adapter_diagnostics[candidate_id] = _adapter_diagnostic(candidate_id, error)

    # Use the evaluator's authoritative per-candidate validator before handing a batch
    # to evaluate(). This keeps one malformed envelope from aborting good candidates.
    decoded_query = decode_ranking_query(query_payload)
    validated: list[dict[str, Any]] = []
    for envelope in adapted:
        candidate_id = envelope["candidate_id"]
        try:
            validated.append(
                validate_candidate_envelope(
                    envelope, decoded_query, semantic_binding=semantic_bindings.get(candidate_id)
                )
            )
        except (RankingValidationError, TypeError, ValueError, KeyError, AttributeError) as error:
            adapter_diagnostics[candidate_id] = {
                "reasons": ["canonical_candidate_invalid"],
                "assessment": {
                    "candidate_id": candidate_id,
                    "status": "unknown",
                    "effort": None,
                    "likelihood_interval": None,
                    "diagnostic": str(error),
                },
            }
            candidate_audits.pop(candidate_id, None)

    effective_coverage = (
        normalized_coverage
        if normalized_coverage is not None
        else {
            "is_truncated": False,
            "truncation_reasons": [],
            "completeness_scope": "unspecified_subset",
            "caps_applied": {},
        }
    )
    result = PathRankingEngine(version="1.0.0").evaluate(
        query_payload=query_payload,
        candidates=validated,
        upstream_coverage=effective_coverage,
        semantic_bindings=semantic_bindings,
    )
    payload = result["result_payload"]
    payload["diagnostics"].update(adapter_diagnostics)
    for partition in (payload["eligible_candidates"], payload["diagnostics"]):
        for candidate_id, assessment in partition.items():
            if candidate_id in candidate_audits:
                assessment["search_trace"] = candidate_audits[candidate_id]

    payload["search_audit"] = {
        "candidate_source": "explicit_path_results",
        "candidates_received": len(search_candidates),
        "candidates_adapted": len(validated),
        "candidates_rejected_by_adapter": len(adapter_diagnostics),
        "coverage": deepcopy(effective_coverage),
        "facts_ledger": deepcopy(query_payload.get("facts_ledger", {})),
    }
    result["encoded_json"] = encode_ranking_result(payload)
    result["roundtrip_result"] = json.loads(result["encoded_json"])
    return result


def evaluate_zero_action_initial_goal(
    query_payload: dict[str, Any],
    canonical_graph: dict[str, Any],
    *,
    actor: str,
    target_id: str,
    search_result: Any,
    budget: Any,
    engine_graph: EngineGraph | None = None,
    prepared: Any = None,
) -> dict[str, Any]:
    """Validate ranking inputs and disclose semantic zero work separately from ranking.

    The search layer has already established its declared initial-state goal. This
    does not evaluate the ranking success event or calibrate likelihood/impact, so
    no candidate envelope, assessed candidate, or Pareto entry is manufactured.
    """
    coverage = coverage_from_search_result(search_result, budget)
    # Reuse the authoritative query decoder, graph contract and snapshot boundary,
    # including parameter audit, even though there are no ranking envelopes.
    result = evaluate_search_candidates(
        query_payload,
        [],
        canonical_graph=canonical_graph,
        coverage=coverage,
        engine_graph=engine_graph,
        prepared=prepared,
    )
    metadata = query_payload["query_metadata"]
    if metadata["foothold_node_id"] != actor:
        raise RankingValidationError("zero-action actor must match query foothold_node_id")
    if metadata["target_goal"]["target_asset_id"] != target_id:
        raise RankingValidationError("zero-action target must match ranking target_asset_id")
    node_ids = {node["id"] for node in canonical_graph["nodes"]}
    if actor not in node_ids or target_id not in node_ids:
        raise RankingValidationError("zero-action actor and target must belong to canonical_graph")
    paths = _field(search_result, "paths")
    if (
        len(paths) != 1
        or _field(paths[0], "transition_history")
        or tuple(_field(paths[0], "nodes")) != (target_id,)
        or _field(search_result, "truncated")
    ):
        raise RankingValidationError("zero-work disposition requires an initial-goal search path")

    payload = result["result_payload"]
    payload["zero_work_disposition"] = {
        "disposition": "semantic_initial_goal_zero_work",
        "ranking_status": "not_applicable",
        "goal_id": metadata["target_goal"]["goal_id"],
        "best_candidate_id": "generated_0001",
        "minimum_effort_value": 0.0,
        "associated_likelihood_interval": None,
        "associated_impact": None,
        "all_best_candidate_ids": ["generated_0001"],
        "tie_count": 1,
        "coverage_disclosure": (
            "Declared semantic goal holds in the initial AttackState: zero new work. "
            "This is not a canonical candidate assessment of the ranking success event; "
            "likelihood and impact are not evaluated and Pareto ranking is not applicable."
        ),
        "baseline_coverage": deepcopy(coverage),
    }
    payload["search_audit"].update(
        {
            "candidate_source": "initial_state_goal_satisfaction",
            "generated_paths": 1,
            "generated_candidates_bound": 0,
            "candidates_unbound": 0,
            "binding_diagnostics": {},
            "zero_action_initial_goal": True,
        }
    )
    result["encoded_json"] = encode_ranking_result(payload)
    result["roundtrip_result"] = json.loads(result["encoded_json"])
    return result


def generate_and_evaluate_attack_paths(
    query_payload: dict[str, Any],
    canonical_graph: dict[str, Any],
    *,
    actor: str,
    initial_state: Any,
    runtime_context: Any,
    budget: Any,
    action_bindings: Mapping[tuple[str, str, str, str], str] | None = None,
    rating_resolution: Mapping[str, Any] | None = None,
    snapshot_facts: Any = None,
    catalog: Sequence[Any] | None = None,
    scenario_reference: str | None = None,
    success_state_predicate: Callable[[Any], bool] | None = None,
    semantic_goal: Any = None,
) -> dict[str, Any]:
    """Run the merged semantic search and rank only candidates it actually generates.

    action_bindings is deliberately exact and fail-closed. Keys are
    (technique_id, actor, source, target) transition identities and values are
    canonical ranking action IDs. A generated path with any unbound transition is
    excluded from ranking and retained in search_audit.binding_diagnostics.

    Generated candidates retain strictly generator-assigned identities through
    evaluation and ranking to ensure oracle naming cannot alter tie-breaking or
    Pareto order.

    This function never replays query-supplied candidate envelopes as search output.
    """
    from collections import Counter

    from src.engine.graph import EngineGraph
    from src.engine.search import generate_attack_paths

    if rating_resolution is not None:
        if action_bindings is not None or query_payload:
            raise RankingValidationError(
                "Automatic mode conflicts with explicit query_payload/action_bindings"
            )
        from src.engine.query import MaterializedQuery, SemanticGoalDescriptor
        from src.engine.semantics import load_catalog

        if success_state_predicate is None and semantic_goal is None:
            raise RankingValidationError(
                "Automatic orchestration requires a semantic success predicate"
            )
        target_id = rating_resolution["scope"]["target_goal"]["target_asset_id"]
        if semantic_goal is not None:
            if not isinstance(semantic_goal, SemanticGoalDescriptor):
                raise RankingValidationError("semantic_goal must be a typed SemanticGoalDescriptor")
            if semantic_goal.target_asset_id != target_id:
                raise RankingValidationError("Semantic goal target conflicts with rating target")
            # Enforce the typed requirements, even if a caller supplies a weaker callable.
            original_predicate = success_state_predicate

            def success_state_predicate(state):
                return semantic_goal.matches(state) and (
                    original_predicate is None or original_predicate(state)
                )

        graph = EngineGraph.from_canonical(canonical_graph, snapshot_facts=snapshot_facts)
        materialized = MaterializedQuery(
            initial_actor=actor,
            initial_attack_state=initial_state,
            runtime_context=runtime_context,
            target=target_id,
            target_predicate=lambda node: node["id"] == target_id,
            success_state_predicate=success_state_predicate,
            budget=budget,
            catalog=tuple(catalog if catalog is not None else load_catalog()),
            scenario_reference=scenario_reference,
            evaluation_mode=rating_resolution["scope"]["evaluation_mode"],
            rating_resolution=rating_resolution,
            semantic_goal=semantic_goal,
        )
        executed = materialized.run(graph)
        encoded = encode_ranking_result(executed.ranking_result)
        return {
            "result_payload": executed.ranking_result,
            "encoded_json": encoded,
            "roundtrip_result": json.loads(encoded),
            "search_result": executed.search_result,
        }

    if not isinstance(query_payload, dict):
        raise TypeError("query_payload must be a PathRankingQuery object")
    if not isinstance(canonical_graph, dict):
        raise TypeError("canonical_graph must be a canonical Graph JSON object")
    if not isinstance(actor, str) or not actor.strip():
        raise TypeError("actor must be a non-empty canonical node ID")
    if not isinstance(action_bindings, Mapping):
        raise TypeError("action_bindings must be a mapping")

    normalized_bindings: dict[tuple[str, str, str, str], str] = {}
    for key, action_id in action_bindings.items():
        if (
            not isinstance(key, tuple)
            or len(key) != 4
            or any(not isinstance(value, str) or not value.strip() for value in key)
        ):
            raise TypeError(
                "action binding keys must be (technique_id, actor, source, target) string tuples"
            )
        if not isinstance(action_id, str) or not action_id.strip():
            raise TypeError("action binding values must be non-empty action IDs")
        normalized_bindings[key] = action_id

    metadata = query_payload.get("query_metadata")
    if not isinstance(metadata, dict):
        raise RankingValidationError("query_metadata is required for generated search")
    target_goal = metadata.get("target_goal")
    if not isinstance(target_goal, dict):
        raise RankingValidationError("query_metadata.target_goal is required for generated search")
    target_id = target_goal.get("target_asset_id")
    if not isinstance(target_id, str) or not target_id.strip():
        raise RankingValidationError("target_goal.target_asset_id must be a non-empty string")
    if metadata.get("foothold_node_id") != actor:
        raise RankingValidationError("generated search actor must match query foothold_node_id")
    if semantic_goal is not None:
        from src.engine.query import SemanticGoalDescriptor

        if not isinstance(semantic_goal, SemanticGoalDescriptor):
            raise RankingValidationError("semantic_goal must be a typed SemanticGoalDescriptor")
        if semantic_goal.target_asset_id != target_id:
            raise RankingValidationError("Semantic goal target conflicts with ranking target")
        descriptor = semantic_goal.to_dict()
        if metadata.get("semantic_goal") not in (None, descriptor):
            raise RankingValidationError(
                "Ranking state-goal descriptor conflicts with semantic query"
            )
        metadata = {**metadata, "semantic_goal": descriptor}
        query_payload = {**query_payload, "query_metadata": metadata}
        original_predicate = success_state_predicate

        def success_state_predicate(state):
            return semantic_goal.matches(state) and (
                original_predicate is None or original_predicate(state)
            )

    graph = EngineGraph.from_canonical(deepcopy(canonical_graph), snapshot_facts=snapshot_facts)
    if target_id not in {node["id"] for node in canonical_graph["nodes"]}:
        raise RankingValidationError("generated search target must belong to canonical_graph")
    search_result = generate_attack_paths(
        graph,
        actor,
        initial_state=initial_state,
        runtime_context=runtime_context,
        target_predicate=lambda node: node["id"] == target_id,
        budget=budget,
        success_state_predicate=success_state_predicate,
        scenario_reference=scenario_reference or metadata.get("scenario_id"),
        catalog=catalog,
    )
    coverage = coverage_from_search_result(search_result, budget)

    if len(search_result.paths) == 1 and len(search_result.paths[0].transition_history) == 0:
        result = evaluate_zero_action_initial_goal(
            query_payload,
            canonical_graph,
            actor=actor,
            target_id=target_id,
            search_result=search_result,
            budget=budget,
        )
        result["search_result"] = search_result
        return result

    generated_candidates: list[dict[str, Any]] = []
    binding_diagnostics: dict[str, dict[str, Any]] = {}
    for index, path in enumerate(search_result.paths, start=1):
        action_ids: list[str] = []
        missing: list[dict[str, Any]] = []
        for step_index, step in enumerate(path.transition_history):
            request = step.result.request
            key = (
                request.technique_id,
                request.actor,
                request.source,
                request.target,
            )
            action_id = normalized_bindings.get(key)
            if action_id is None:
                missing.append(
                    {
                        "step_index": step_index,
                        "technique_id": request.technique_id,
                        "actor": request.actor,
                        "source": request.source,
                        "target": request.target,
                    }
                )
            else:
                action_ids.append(action_id)
        candidate_id = f"generated_{index:04d}"
        if missing:
            binding_diagnostics[candidate_id] = {
                "reason": "explicit_action_binding_missing",
                "unbound_steps": missing,
            }
            continue
        generated_candidates.append(
            {
                "candidate_id": candidate_id,
                "target_asset_id": target_id,
                "route_id": f"route_{candidate_id}",
                "action_mapping": action_ids,
                "path_result": path,
            }
        )

    result = evaluate_search_candidates(
        query_payload,
        generated_candidates,
        canonical_graph=canonical_graph,
        coverage=coverage,
        snapshot_facts=snapshot_facts,
        catalog=catalog,
    )
    payload = result["result_payload"]
    status_counts = Counter(str(attempt.status) for attempt in search_result.attempts)
    technique_counts = Counter(attempt.request.technique_id for attempt in search_result.attempts)
    attempt_diagnostics = [
        {
            "technique_id": attempt.request.technique_id,
            "actor": attempt.request.actor,
            "source": attempt.request.source,
            "target": attempt.request.target,
            "status": str(attempt.status),
            "failed": list(attempt.failed),
            "unknown": list(attempt.unknown),
            "decisions": [
                {
                    "predicate": decision.predicate,
                    "satisfied": decision.satisfied,
                    "origin": str(decision.origin),
                    "rationale": decision.rationale,
                    "subject": decision.fact.subject if decision.fact is not None else None,
                    "target": decision.fact.target if decision.fact is not None else None,
                    "value": decision.fact.value if decision.fact is not None else None,
                    "scope": decision.fact.scope if decision.fact is not None else None,
                }
                for decision in attempt.decisions
            ],
        }
        for attempt in search_result.attempts
    ]
    payload["search_audit"].update(
        {
            "candidate_source": "generate_attack_paths",
            "generated_paths": len(search_result.paths),
            "generated_candidates_bound": len(generated_candidates),
            "binding_diagnostics": binding_diagnostics,
            "attempts": len(search_result.attempts),
            "attempt_status_counts": dict(sorted(status_counts.items())),
            "attempt_technique_counts": dict(sorted(technique_counts.items())),
            "attempt_diagnostics": attempt_diagnostics,
            "terminal_condition": (
                "target_asset_and_declared_success_state"
                if success_state_predicate is not None
                else "target_asset_only"
            ),
            "expansions": search_result.expansions,
            "truncated": search_result.truncated,
            "truncation_reason": search_result.truncation_reason,
        }
    )
    result["encoded_json"] = encode_ranking_result(payload)
    result["roundtrip_result"] = json.loads(result["encoded_json"])
    result["search_result"] = search_result
    return result
