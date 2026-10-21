"""Read-only guided exploration using existing traversal and semantic evaluation.

Probes evaluate explicit requests against a replayed prefix, not hypothetical
effects of blocked actions. Templates are declared scenarios, not a recommender.
This transport is separate from public query-result/ranking schemas.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, fields, is_dataclass
from typing import Any

from .graph import EngineGraph
from .query import MaterializedQuery, materialize_query
from .search import generate_structural_paths
from .semantics.evaluator import PreparedSemanticGraph, candidates, evaluate
from .semantics.transitions import Status, TransitionRequest, apply_transition

VERSION = "guided-exploration/0.1.0"


def _wire(value: Any) -> Any:
    if is_dataclass(value) and not isinstance(value, type):
        return {
            f.name: _wire(getattr(value, f.name))
            for f in fields(value)
            if not f.name.startswith("_")
        }
    if isinstance(value, Mapping):
        return {key: _wire(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_wire(item) for item in value]
    if isinstance(value, (set, frozenset)):
        return sorted((_wire(item) for item in value), key=_json)
    return value


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False)


def _digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(_json(value).encode("utf-8")).hexdigest()


def _graph_binding(graph: EngineGraph) -> str:
    # Static facts may differ even when the structural graph is byte-identical.
    return _digest({"graph": graph.to_canonical(), "snapshot_facts": _wire(graph.snapshot_facts)})


def _query_binding(query: Mapping[str, Any]) -> str:
    # Switching evidence-only/scenario or checking a subset of assumptions is
    # intentional. Every other input, including budget/rating scope, stays pinned.
    return _digest({k: v for k, v in query.items() if k not in {"assumptions", "evaluation_mode"}})


def structural_exploration(query: Mapping[str, Any], graph: EngineGraph) -> dict:
    """Return topology paths independently of whether semantic candidates exist."""
    materialized = materialize_query(query, graph)
    result = generate_structural_paths(
        graph,
        materialized.initial_actor,
        materialized.target,
        budget=materialized.budget,
    )
    return {
        "schema_version": VERSION,
        "kind": "structural_only",
        "graph_binding": _graph_binding(graph),
        "source": materialized.initial_actor,
        "target": materialized.target,
        "paths": [
            {"route_id": f"route_{i:04d}", "nodes": list(p.nodes), "edges": _wire(p.edges)}
            for i, p in enumerate(result.paths, 1)
        ],
        "budget": _wire(materialized.budget),
        "expansions": result.expansions,
        "complete": result.complete,
        "truncated": result.truncated,
        "truncation_reason": result.truncation_reason,
        "notice": "Topology only; no attack feasibility, goal success or ranking claim.",
    }


def _transition(result) -> dict:
    return {
        **_wire(result),
        "after": _wire(apply_transition(result.before, result)),
        "assumption_backed_facts": _wire(result.assumption_backed_facts),
        "evidence_backed_facts": _wire(result.evidence_backed_facts),
    }


def _replay(
    materialized: MaterializedQuery,
    graph: PreparedSemanticGraph,
    prefix: Sequence[TransitionRequest],
) -> tuple[Any, dict]:
    state = materialized.initial_attack_state
    report = {
        "schema_version": VERSION,
        "kind": "explicit_prefix_probe",
        "authentication_context": materialized.runtime_context.authentication_context,
        "evaluation_mode": materialized.evaluation_mode,
        "prefix": [],
        "rejected_assumptions": [r.to_dict() for r in materialized.rejected_assumptions],
        "options": [],
        "prefix_status": "applicable",
        "truncated": False,
        "truncation_reason": None,
    }
    # Leave room for at least one inspected action within the declared budgets.
    if len(prefix) >= min(materialized.budget.max_steps, materialized.budget.max_expansions):
        report.update(
            prefix_status="not_evaluated",
            truncated=True,
            truncation_reason="probe_budget_exhausted",
        )
        return state, report
    for request in prefix:
        result = evaluate(graph, state, request, materialized.runtime_context, materialized.catalog)
        report["prefix"].append(_transition(result))
        if result.status != Status.APPLICABLE:
            report["prefix_status"] = result.status.value
            report["state"] = _wire(state)
            return state, report
        state = apply_transition(state, result)
    report["state"] = _wire(state)
    return state, report


def inspect_transition(
    query: Mapping[str, Any],
    graph: EngineGraph,
    request: TransitionRequest,
    *,
    prefix: Sequence[TransitionRequest] = (),
) -> dict:
    """Probe a chosen action, including credential actions not bound to a raw edge.

    Unknown/blocked prefix stops replay. No downstream prerequisites are fabricated.
    The caller supplies canonical request IDs; the evaluator validates capability,
    relationship, artifact and auth context using the ordinary technique catalog.
    """
    materialized = materialize_query(query, graph)
    prepared = PreparedSemanticGraph(graph.to_canonical(), snapshot_facts=graph.snapshot_facts)
    state, report = _replay(materialized, prepared, prefix)
    if report["prefix_status"] == "applicable":
        result = evaluate(
            prepared, state, request, materialized.runtime_context, materialized.catalog
        )
        report["options"] = [_transition(result)]
    report["graph_binding"] = _graph_binding(graph)
    return report


def inspect_structural_edge(
    query: Mapping[str, Any],
    graph: EngineGraph,
    edge_id: str,
    *,
    actor: str | None = None,
    prefix: Sequence[TransitionRequest] = (),
) -> dict:
    """List direct catalog options for an exact edge at an explicitly replayed state.

    This is not a whole-route planner. Derived/compound recipes may need explicit
    inspect_transition calls and typed bindings, rather than an edge-kind shortcut.
    """
    edge = graph.edge(edge_id)
    materialized = materialize_query(query, graph)
    selected_actor = actor if actor is not None else materialized.initial_actor
    graph.node(selected_actor)
    prepared = PreparedSemanticGraph(graph.to_canonical(), snapshot_facts=graph.snapshot_facts)
    state, report = _replay(materialized, prepared, prefix)
    report["edge"] = edge
    report["graph_binding"] = _graph_binding(graph)
    if report["prefix_status"] != "applicable":
        return report
    choices = candidates(
        edge["kind"],
        graph.node(edge["source"])["kind"],
        graph.node(edge["target"])["kind"],
        materialized.catalog,
    )
    remaining = materialized.budget.max_expansions - len(prefix)
    if len(choices) > remaining:
        report.update(truncated=True, truncation_reason="probe_budget_exhausted")
    for technique in choices[:remaining]:
        request = TransitionRequest(technique.id, selected_actor, edge["source"], edge["target"])
        result = evaluate(
            prepared, state, request, materialized.runtime_context, materialized.catalog
        )
        report["options"].append(_transition(result))
    report["catalog_support"] = "direct_options" if choices else "no_direct_catalog_option"
    return report


@dataclass(frozen=True)
class ScopedScenarioTemplate:
    """Immutable declared proposal set bound to one exact graph/query scope."""

    template_id: str
    graph_binding: str
    query_binding: str
    assumptions_json: str


def build_scenario_template(
    query: Mapping[str, Any],
    graph: EngineGraph,
    assumptions: Sequence[Mapping[str, Any]],
    *,
    template_id: str,
) -> ScopedScenarioTemplate:
    """Register reviewed scenario records; never infer missing fact scope or outcomes."""
    if not isinstance(template_id, str) or not template_id.strip():
        raise ValueError("template_id must be non-empty")
    records = json.loads(_json(list(assumptions)))
    # The normal materializer validates identity/scope/metadata and contradictory
    # records. Known-false proposals remain auditable rejected records.
    materialize_query({**query, "evaluation_mode": "scenario", "assumptions": records}, graph)
    return ScopedScenarioTemplate(
        template_id, _graph_binding(graph), _query_binding(query), _json(records)
    )


def scenario_proposals(
    template: ScopedScenarioTemplate, query: Mapping[str, Any], graph: EngineGraph
) -> dict:
    """Return unchecked template choices, not alleged missing facts for every route."""
    if template.graph_binding != _graph_binding(graph) or template.query_binding != _query_binding(
        query
    ):
        raise ValueError("scenario template does not match the exact graph/query scope")
    records = json.loads(template.assumptions_json)
    materialized = materialize_query(
        {**query, "evaluation_mode": "scenario", "assumptions": records}, graph
    )
    rejected = [r.to_dict() for r in materialized.rejected_assumptions]
    # Alias normalization belongs to the resolver. Do not infer canonical fact
    # keys here; expose its ledger separately and let rerun enforce every veto.
    return {
        "schema_version": VERSION,
        "kind": "scoped_template",
        "template_id": template.template_id,
        "graph_binding": template.graph_binding,
        "query_binding": template.query_binding,
        "proposals": [
            {"proposal_id": f"proposal_{i:04d}", "selected": False, "assumption": record}
            for i, record in enumerate(records, 1)
        ],
        "rejected_assumptions": rejected,
        "notice": (
            "Declared template outcomes, not a complete route diagnosis. "
            "Selection requires a real engine rerun; snapshot/state vetoes are evaluated there."
        ),
    }


def query_with_proposals(
    template: ScopedScenarioTemplate,
    query: Mapping[str, Any],
    graph: EngineGraph,
    selected_ids: Sequence[str],
) -> dict:
    """Build a fresh validated scenario query without mutating or executing input."""
    proposals = scenario_proposals(template, query, graph)["proposals"]
    by_id = {p["proposal_id"]: p["assumption"] for p in proposals}
    if len(selected_ids) != len(set(selected_ids)) or any(p not in by_id for p in selected_ids):
        raise ValueError("selection must contain unique proposal IDs from this template")
    updated = json.loads(_json(dict(query)))
    updated["evaluation_mode"] = "scenario"
    # Template order is stable regardless of checkbox-click order.
    selected = set(selected_ids)
    updated["assumptions"] = [by_id[p] for p in by_id if p in selected]
    materialize_query(updated, graph)
    return updated
