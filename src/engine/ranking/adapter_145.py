"""Adapter boundary and protocol for Issue #145 PathResult integration.

Compatible with the current #145 PathResult shape as reviewed,
while runtime search integration remains pending merge of #145.

Provides the contract and translation layer showing how a path result produced
by the canonical multigraph search foundation (#145) maps into an explicit candidate
envelope (v1.0.0) for whole-path ranking.

Note:
Issue #145 remains pending review on PR #146 and is not yet merged into develop.
This module defines the clean boundary protocol without duplicating multigraph
search or embedding research prototype code.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import asdict, fields, is_dataclass
from enum import Enum
from fractions import Fraction
from typing import Any, Protocol, runtime_checkable

from src.engine.ranking.models import (
    REQUIRED_SCOPE_BINDING_FIELDS,
    RankingValidationError,
    is_canonical_edge_id,
    is_canonical_node_id,
)


@runtime_checkable
class TransitionStepProtocol(Protocol):
    """Protocol representing a transition step from #145 search."""

    @property
    def edge_id(self) -> str | None: ...

    @property
    def result(self) -> Any: ...

    @property
    def derived_from_step(self) -> int | None: ...


@runtime_checkable
class PathResultProtocol(Protocol):
    """Protocol representing a search path result from #145 multigraph search."""

    @property
    def nodes(self) -> tuple[str, ...]: ...

    @property
    def edges(self) -> tuple[Any, ...]: ...

    @property
    def transition_history(self) -> tuple[Any, ...]: ...

    @property
    def scenario_reference(self) -> str | None: ...


def compute_provenance_reference(record: dict[str, Any]) -> str:
    """Compute deterministic SHA-256 reference for a canonical provenance record dict."""
    payload = json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return f"sha256:{hashlib.sha256(payload.encode('utf-8')).hexdigest()}"


def _audit_value(value: Any) -> Any:
    """Convert search trace values to deterministic, JSON-safe audit records."""
    if isinstance(value, Fraction):
        return f"{value.numerator}/{value.denominator}"
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value) and not isinstance(value, type):
        return {item.name: _audit_value(getattr(value, item.name)) for item in fields(value)}
    if hasattr(value, "__dict__"):
        return {name: _audit_value(item) for name, item in vars(value).items()}
    if isinstance(value, Mapping):
        return {str(key): _audit_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_audit_value(item) for item in value]
    if isinstance(value, (set, frozenset)):
        return sorted(
            (_audit_value(item) for item in value),
            key=lambda item: json.dumps(item, sort_keys=True),
        )
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise RankingValidationError(f"Unsupported value in search audit trace: {type(value).__name__}")


def _runtime_fact_audit(path_result: Any) -> Any:
    context = getattr(path_result, "runtime_context", None)
    if context is None and isinstance(path_result, dict):
        context = path_result.get("runtime_context")
    facts = getattr(context, "facts", None)
    if facts is None and isinstance(context, dict):
        facts = context.get("facts")
    if not isinstance(facts, Mapping):
        return _audit_value(facts or {})
    if all(isinstance(key, tuple) and len(key) == 3 for key in facts):
        audited: list[dict[str, Any]] = []
        for key in sorted(facts):
            fact_value = _audit_value(facts[key])
            record: dict[str, Any] = {
                "predicate": key[0],
                "subject": key[1],
                "target": key[2],
            }
            if isinstance(fact_value, dict) and "value" in fact_value:
                record["truth_value"] = fact_value["value"]
                for field_name in (
                    "origin",
                    "scope",
                    "rationale",
                    "provenance_reference",
                    "assumption_metadata",
                ):
                    if field_name in fact_value:
                        record[field_name] = fact_value[field_name]
            else:
                # Backward compatibility with pre-typed #146 boolean runtime facts.
                record["truth_value"] = fact_value
            audited.append(record)
        return audited
    return _audit_value(facts)


def extract_technique_id(step: Any, idx: int) -> str:
    """Extract and validate technique identifier from actual #145 transition step contract.

    Primary source-of-truth is step.result.request.technique_id.
    Secondary compatible source is step.result.technique.id.
    Rejects conflicting sources, missing technique identifiers, and forbids fallbacks.
    """
    res = getattr(step, "result", None) or (step.get("result") if isinstance(step, dict) else None)
    if res is None:
        raise RankingValidationError(f"Transition step {idx} is missing required result object")

    # 1. Primary source: step.result.request.technique_id
    req = getattr(res, "request", None) or (res.get("request") if isinstance(res, dict) else None)
    req_tech: str | None = None
    if req is not None:
        raw_req = getattr(req, "technique_id", None) or (
            req.get("technique_id") if isinstance(req, dict) else None
        )
        if raw_req is not None and str(raw_req).strip():
            req_tech = str(raw_req).strip()

    # 2. Secondary source: step.result.technique.id
    tech = getattr(res, "technique", None) or (
        res.get("technique") if isinstance(res, dict) else None
    )
    tech_id: str | None = None
    if tech is not None:
        raw_tech = (
            getattr(tech, "id", None)
            or getattr(tech, "technique_id", None)
            or (tech.get("id") or tech.get("technique_id") if isinstance(tech, dict) else None)
        )
        if raw_tech is not None and str(raw_tech).strip():
            tech_id = str(raw_tech).strip()

    # Reject if both sources are present but contradictory
    if req_tech and tech_id and req_tech != tech_id:
        raise RankingValidationError(
            f"Transition step {idx} has contradictory technique identifiers: "
            f"request.technique_id={req_tech!r} != technique.id={tech_id!r}"
        )

    technique_id = req_tech or tech_id
    if not technique_id:
        raise RankingValidationError(
            f"Transition step {idx} is missing required technique identifier; "
            "expected in step.result.request.technique_id or step.result.technique.id"
        )
    return technique_id


def extract_edge_provenance_locators(
    edge_record: Any,
    edge_id: str,
) -> tuple[list[str], list[dict[str, Any]]]:
    """Extract all authentic provenance locator/reference strings and raw records from an edge.

    Preserves the full provenance lineage without collapsing multiple records into one
    or silently dropping aggregated evidence. Conforms strictly to Graph Contract 1.3.

    Returns:
        A tuple of (locators_list, normalized_records_list).
    """
    raw_prov = (
        edge_record.get("provenance")
        if isinstance(edge_record, dict)
        else getattr(edge_record, "provenance", None)
    )

    records: list[Any] = []
    if isinstance(raw_prov, (list, tuple)):
        records = list(raw_prov)
    elif isinstance(raw_prov, dict):
        records = [raw_prov]
    elif isinstance(raw_prov, str) and raw_prov.strip():
        records = [raw_prov.strip()]
    else:
        # Fall back to top-level edge fields if provenance field is absent
        for field in ("provenance_locator", "provenance_reference"):
            val = (
                edge_record.get(field)
                if isinstance(edge_record, dict)
                else getattr(edge_record, field, None)
            )
            if isinstance(val, str) and val.strip():
                records = [val.strip()]
                break

    if not records:
        raise RankingValidationError(
            f"Canonical edge {edge_id!r} lacks authentic usable provenance; "
            "fabricating synthetic locators is disallowed"
        )

    locators: list[str] = []
    normalized_records: list[dict[str, Any]] = []

    for item_idx, item in enumerate(records):
        if isinstance(item, str) and item.strip():
            locators.append(item.strip())
            normalized_records.append({"locator": item.strip()})
        elif isinstance(item, dict):
            # Check for declared explicit locator/reference/id fields
            explicit_ref: str | None = None
            for field in (
                "provenance_locator",
                "provenance_reference",
                "record_locator",
                "record_id",
            ):
                val = item.get(field)
                if isinstance(val, str) and val.strip():
                    explicit_ref = val.strip()
                    break

            if explicit_ref:
                locators.append(explicit_ref)
                normalized_records.append(dict(item))
            elif {"raw_file", "collector", "timestamp"} <= set(item.keys()):
                # Standard Graph Contract 1.3 provenance record
                ref = compute_provenance_reference(item)
                locators.append(ref)
                normalized_records.append(dict(item))
            else:
                raise RankingValidationError(
                    f"Canonical edge {edge_id!r} provenance record {item_idx} lacks required "
                    "Graph Contract fields or explicit identifier"
                )
        elif hasattr(item, "provenance_locator") or hasattr(item, "provenance_reference"):
            val = getattr(item, "provenance_locator", None) or getattr(
                item, "provenance_reference", None
            )
            if isinstance(val, str) and val.strip():
                locators.append(val.strip())
                normalized_records.append({"locator": val.strip()})
            else:
                raise RankingValidationError(
                    f"Canonical edge {edge_id!r} provenance object {item_idx} has empty locator"
                )
        else:
            raise RankingValidationError(
                f"Canonical edge {edge_id!r} provenance entry {item_idx} has invalid format"
            )

    if not locators:
        raise RankingValidationError(
            f"Canonical edge {edge_id!r} has no valid provenance locators extracted"
        )

    # Deduplicate while preserving original order
    seen: set[str] = set()
    deduped_locators: list[str] = []
    for loc in locators:
        if loc not in seen:
            seen.add(loc)
            deduped_locators.append(loc)

    return deduped_locators, normalized_records


def extract_edge_provenance_locator(edge_record: Any, edge_id: str) -> str:
    """Extract genuine provenance locator or reference string from a canonical edge record.

    Inspects canonical edge schema conforming to Graph Contract without fabricating synthetic tags
    and without stringifying complex objects.
    When multiple provenance records exist, returns a deterministic semicolon-delimited string
    preserving all records so that no evidence is dropped.
    """
    locators, _ = extract_edge_provenance_locators(edge_record, edge_id)
    return ";".join(locators)


def convert_path_result_to_candidate_envelope(
    path_result: Any,
    candidate_id: str,
    target_asset_id: str,
    query_metadata: dict[str, Any],
    action_mapping: dict[str, str] | list[str] | tuple[str, ...],
    route_id: str = "route-001",
    *,
    bound_actions_catalog: list[dict[str, Any]] | dict[str, dict[str, Any]] | None = None,
    success_event: str | None = None,
) -> dict[str, Any]:
    """Convert a #145 PathResult or compatible structure into a v1.0.0 candidate envelope.

    Enforces fail-closed rules:
    - Candidate fixed query scope binding derived strictly from verified query_metadata.
    - Explicit technique identifier extracted from step.result.request.technique_id or
      step.result.technique.id (rejecting conflicts and missing identifiers).
    - Explicit ordered per-step bound_action_ids, or an unambiguous technique mapping.
    - Genuine provenance resolved directly from exact canonical edge records in PathResult.edges,
      preserving all records without collapsing or dropping aggregated evidence.
    - Exact transition request <-> canonical edge endpoint verification where an observed edge
      exists; structural route nodes are derived only from the ordered observed edge records.
    - Transition request source/target consistency check (if provided,
      request.source == edge['source'] and request.target == edge['target']).
    - Derived transitions retain their semantic trace but add no structural edge evidence.
    - Structural route endpoints must match query foothold and candidate target.
    - If bound_actions_catalog is provided, verifies catalog membership and transition context.

    Args:
        path_result: An object satisfying PathResultProtocol or a dictionary with equivalent keys.
        candidate_id: Unique candidate identifier.
        target_asset_id: Canonical node ID of the target asset.
        query_metadata: Metadata of the active PathRankingQuery.
        action_mapping: Ordered action IDs (one per transition), or technique-to-action IDs.
        route_id: Identifier for the structural route trace.
        bound_actions_catalog: Optional catalog of bound actions to check edge_id alignment.

    Returns:
        A validated candidate envelope dictionary conforming to v1.0.0.
    """
    if not isinstance(candidate_id, str) or not candidate_id.strip():
        raise RankingValidationError("candidate_id must be a non-empty string")
    if not is_canonical_node_id(target_asset_id):
        raise RankingValidationError(f"Invalid canonical target_asset_id: {target_asset_id!r}")

    # Build and verify scope binding from caller query_metadata
    if not isinstance(query_metadata, dict):
        raise TypeError("query_metadata must be a dictionary")
    for f in REQUIRED_SCOPE_BINDING_FIELDS:
        if f not in query_metadata or not query_metadata[f]:
            raise RankingValidationError(
                f"Cannot convert #145 PathResult: query_metadata missing required scope field {f!r}"
            )
    scope_binding = {f: query_metadata[f] for f in REQUIRED_SCOPE_BINDING_FIELDS}
    foothold_id = query_metadata["foothold_node_id"]

    # Extract and validate nodes
    if hasattr(path_result, "nodes"):
        nodes = list(path_result.nodes)
    elif isinstance(path_result, dict) and "nodes" in path_result:
        nodes = list(path_result["nodes"])
    else:
        raise TypeError("path_result must provide 'nodes'")

    if not nodes:
        raise RankingValidationError("path_result.nodes cannot be empty")

    for nid in nodes:
        if not is_canonical_node_id(nid):
            raise RankingValidationError(f"Path contains non-canonical node ID: {nid!r}")

    if nodes[0] != foothold_id:
        raise RankingValidationError(
            f"PathResult source node {nodes[0]!r} does not match query foothold {foothold_id!r}"
        )
    goal_target = getattr(path_result, "goal_target", None)
    state_goal_binding = None
    if isinstance(path_result, dict):
        goal_target = path_result.get("goal_target")
    if goal_target is not None or query_metadata.get("semantic_goal") is not None:
        from src.engine.query import IdentityResolver, _state_from_spec, semantic_goal_from_dict

        goal = query_metadata.get("semantic_goal")
        final_state = (
            path_result.get("final_state")
            if isinstance(path_result, dict)
            else getattr(path_result, "final_state", None)
        )
        if (
            (goal_target if goal_target is not None else nodes[-1]) != target_asset_id
            or not isinstance(goal, dict)
            or goal.get("target_asset_id") != target_asset_id
            or final_state is None
        ):
            raise RankingValidationError(
                "State-goal target requires its exact typed goal and state"
            )
        identities = IdentityResolver({})
        try:
            descriptor = semantic_goal_from_dict(goal, identities)
        except (KeyError, TypeError, ValueError) as exc:
            raise RankingValidationError("Malformed typed state-goal descriptor") from exc
        if not descriptor.matches(_state_from_spec(_audit_value(final_state), identities)):
            raise RankingValidationError("State-goal target is not satisfied by final state")
        from src.engine.ranking.resolution_service import canonical_digest

        state_goal_binding = {
            "target_asset_id": target_asset_id,
            "semantic_goal_digest": canonical_digest(goal),
            "final_state_digest": canonical_digest(_audit_value(final_state)),
        }
    elif nodes[-1] != target_asset_id:
        raise RankingValidationError(
            f"PathResult target node {nodes[-1]!r} does not match "
            f"target_asset_id {target_asset_id!r}"
        )

    # Build mapping from canonical edge records in path_result.edges
    raw_edges = (
        getattr(path_result, "edges", None)
        or (path_result.get("edges") if isinstance(path_result, dict) else None)
        or ()
    )
    if not isinstance(raw_edges, (list, tuple)):
        raise TypeError("path_result.edges must be a sequence")

    edges_by_id: dict[str, Any] = {}
    for e_idx, edge_rec in enumerate(raw_edges):
        eid = edge_rec.get("id") if isinstance(edge_rec, dict) else getattr(edge_rec, "id", None)
        if not eid or not isinstance(eid, str) or not eid.strip():
            raise RankingValidationError(
                f"PathResult edges entry {e_idx} is missing canonical edge ID"
            )
        eid = eid.strip()
        if not is_canonical_edge_id(eid):
            raise RankingValidationError(
                f"PathResult edges entry {e_idx} has invalid canonical edge ID: {eid!r}"
            )
        if eid in edges_by_id:
            existing = edges_by_id[eid]
            if existing != edge_rec:
                raise RankingValidationError(
                    f"PathResult edges contains ambiguous conflicting duplicate records "
                    f"for edge {eid!r}"
                )
        else:
            edges_by_id[eid] = edge_rec

    # Extract transitions and map to bound_action_ids.
    history: list[Any] = []
    if hasattr(path_result, "transition_history"):
        history = list(path_result.transition_history)
    elif isinstance(path_result, dict) and "transition_history" in path_result:
        history = list(path_result["transition_history"])

    # Prepare catalog mapping if provided
    actions_by_id: dict[str, Any] = {}
    if bound_actions_catalog is not None:
        if isinstance(bound_actions_catalog, list):
            actions_by_id = {
                act.get("action_id"): act
                for act in bound_actions_catalog
                if isinstance(act, dict) and act.get("action_id")
            }
        elif isinstance(bound_actions_catalog, dict):
            actions_by_id = bound_actions_catalog
        else:
            raise TypeError("bound_actions_catalog must be a list or dict if provided")

    if not isinstance(action_mapping, (dict, list, tuple)):
        raise TypeError("action_mapping must be a technique mapping or ordered action ID sequence")
    if isinstance(action_mapping, (list, tuple)) and len(action_mapping) != len(history):
        raise RankingValidationError(
            "ordered action_mapping length must match transition_history length"
        )

    # Legacy technique maps remain accepted only when every technique occurs once.
    techniques = [extract_technique_id(step, idx) for idx, step in enumerate(history)]
    if isinstance(action_mapping, dict):
        repeated = sorted({tech for tech in techniques if techniques.count(tech) > 1})
        if repeated:
            raise RankingValidationError(
                "ambiguous technique-only action_mapping for repeated techniques "
                f"{repeated!r}; provide ordered per-step action IDs"
            )

    bound_action_ids: list[str] = []
    route_edge_ids: list[str] = []
    route_action_step_indices: list[int] = []
    provenance_locators: list[str] = []
    route_provenance_lineage: list[list[str]] = []
    route_edge_provenance_records: list[list[dict[str, Any]]] = []
    semantic_lineage: list[dict[str, Any]] = []
    transition_lineage: list[dict[str, Any]] = []

    for idx, step in enumerate(history):
        step_edge_id = None
        if hasattr(step, "edge_id"):
            step_edge_id = step.edge_id
        elif isinstance(step, dict):
            step_edge_id = step.get("edge_id")

        derived_from_step = (
            getattr(step, "derived_from_step", None)
            if not isinstance(step, dict)
            else step.get("derived_from_step")
        )
        derived = step_edge_id is None
        if derived:
            # An initial AttackState relationship has no canonical edge or prior
            # transition step in #146's representation.
            if derived_from_step is None:
                edge_rec = None
            elif type(derived_from_step) is not int or not 0 <= derived_from_step < idx:
                raise RankingValidationError(
                    f"Derived transition step {idx} requires an earlier derived_from_step index"
                )
            else:
                edge_rec = None
        elif not is_canonical_edge_id(step_edge_id):
            raise RankingValidationError(
                f"Transition step {idx} has invalid canonical edge_id: {step_edge_id!r}"
            )

        if not derived:
            if step_edge_id not in edges_by_id:
                raise RankingValidationError(
                    f"Transition step {idx} edge {step_edge_id!r} not found in PathResult.edges"
                )
            edge_rec = edges_by_id[step_edge_id]

        # ----------------------------------------------------------------------
        # 1. Exact canonical edge <-> route segment mapping verification
        # ----------------------------------------------------------------------
        edge_source = edge_target = None
        if not derived:
            edge_source = (
                edge_rec.get("source")
                if isinstance(edge_rec, dict)
                else getattr(edge_rec, "source", None)
            )
            edge_target = (
                edge_rec.get("target")
                if isinstance(edge_rec, dict)
                else getattr(edge_rec, "target", None)
            )
            if not isinstance(edge_source, str) or not edge_source.strip():
                raise RankingValidationError(
                    f"Canonical edge {step_edge_id!r} in PathResult.edges is missing 'source'"
                )
            if not isinstance(edge_target, str) or not edge_target.strip():
                raise RankingValidationError(
                    f"Canonical edge {step_edge_id!r} in PathResult.edges is missing 'target'"
                )
            edge_source, edge_target = edge_source.strip(), edge_target.strip()
            if idx + 1 < len(nodes):
                # Legacy PathResult-like records may omit request endpoints. The #146
                # TransitionRequest contract includes them and takes precedence.
                legacy_source = nodes[idx]
                legacy_target = nodes[idx + 1]
            else:
                legacy_source = legacy_target = None

        # ----------------------------------------------------------------------
        # 2. Transition request source/target verification (if provided)
        # ----------------------------------------------------------------------
        res = getattr(step, "result", None) or (
            step.get("result") if isinstance(step, dict) else None
        )
        req = (
            getattr(res, "request", None) or (res.get("request") if isinstance(res, dict) else None)
            if res is not None
            else None
        )
        if idx + 1 >= len(nodes):
            raise RankingValidationError(
                f"Transition history step index {idx} exceeds PathResult node sequence"
            )
        req_source = getattr(req, "source", None) or (
            req.get("source") if isinstance(req, dict) else None
        )
        req_target = getattr(req, "target", None) or (
            req.get("target") if isinstance(req, dict) else None
        )
        request_target = req_target
        if request_target is not None and request_target != nodes[idx + 1]:
            raise RankingValidationError(
                f"Transition step {idx} request target {request_target!r} does not match "
                f"PathResult transition target {nodes[idx + 1]!r}"
            )
        if req is not None:
            if req_source is not None and str(req_source).strip() and not derived:
                clean_req_src = str(req_source).strip()
                if clean_req_src != edge_source:
                    raise RankingValidationError(
                        f"Transition step {idx} request source {clean_req_src!r} does not match "
                        f"canonical edge source {edge_source!r}"
                    )

            if req_target is not None and str(req_target).strip() and not derived:
                clean_req_tgt = str(req_target).strip()
                if clean_req_tgt != edge_target:
                    raise RankingValidationError(
                        f"Transition step {idx} request target {clean_req_tgt!r} does not match "
                        f"canonical edge target {edge_target!r}"
                    )
        if not derived and legacy_source is not None:
            if req_source is None and edge_source != legacy_source:
                raise RankingValidationError(
                    f"Transition step {idx} edge source mismatch with legacy route segment"
                )
            if req_target is None and edge_target != legacy_target:
                raise RankingValidationError(
                    f"Transition step {idx} edge target mismatch with legacy route segment"
                )

        # ----------------------------------------------------------------------
        # 3. Provenance extraction preserving full lineage (no silently dropped records)
        # ----------------------------------------------------------------------
        if derived:
            locators_list, records_list = [], []
        else:
            locators_list, records_list = extract_edge_provenance_locators(edge_rec, step_edge_id)
        combined_locator = ";".join(locators_list)

        # Extract technique identifier from contract
        technique_id = techniques[idx]

        if isinstance(action_mapping, dict):
            if technique_id not in action_mapping:
                raise RankingValidationError(
                    f"Transition step {idx} technique {technique_id!r} has no explicit mapping "
                    "in action_mapping"
                )
            action_id = action_mapping[technique_id]
        else:
            action_id = action_mapping[idx]
        if not isinstance(action_id, str) or not action_id.strip():
            raise RankingValidationError(
                f"Transition step {idx} mapped action_id must be a non-empty string"
            )

        request_actor = getattr(req, "actor", None) or (
            req.get("actor") if isinstance(req, dict) else None
        )

        # ----------------------------------------------------------------------
        # 4. Bound action declared edge_id verification (if catalog available)
        # ----------------------------------------------------------------------
        if bound_actions_catalog is not None:
            if action_id not in actions_by_id:
                raise RankingValidationError(
                    f"Transition step {idx} references unknown bound_action {action_id!r}"
                )
            act_meta = actions_by_id[action_id]
            request_source = getattr(req, "source", None) or (
                req.get("source") if isinstance(req, dict) else None
            )
            request_target = getattr(req, "target", None) or (
                req.get("target") if isinstance(req, dict) else None
            )
            expected_actor = request_actor or request_source
            action_actor = (
                act_meta.get("actor_id", act_meta.get("source_node_id"))
                if isinstance(act_meta, dict)
                else getattr(act_meta, "actor_id", None)
            )
            action_target = (
                act_meta.get("target_id", act_meta.get("target_node_id"))
                if isinstance(act_meta, dict)
                else getattr(act_meta, "target_id", None)
            )
            if expected_actor is not None and action_actor != expected_actor:
                raise RankingValidationError(
                    f"Transition step {idx} mapped bound_action {action_id!r} actor "
                    f"{action_actor!r} does not match transition actor {expected_actor!r}"
                )
            if request_target is not None and action_target != request_target:
                raise RankingValidationError(
                    f"Transition step {idx} mapped bound_action {action_id!r} target "
                    f"{action_target!r} does not match transition target {request_target!r}"
                )
            if not derived and (
                (request_source is not None and request_source != edge_source)
                or (request_target is not None and request_target != edge_target)
            ):
                raise RankingValidationError(
                    f"Transition step {idx} request source/target does not match exact edge "
                    f"{step_edge_id!r}"
                )
            decl_eid = (
                act_meta.get("edge_id")
                if isinstance(act_meta, dict)
                else getattr(act_meta, "edge_id", None)
            )
            if decl_eid is not None and str(decl_eid).strip():
                clean_decl_eid = str(decl_eid).strip()
                if derived or clean_decl_eid != step_edge_id:
                    raise RankingValidationError(
                        f"Transition step {idx} mapped bound_action {action_id!r} declared edge_id "
                        f"{clean_decl_eid!r} does not match step edge_id {step_edge_id!r}"
                    )
        if not derived and legacy_source is not None:
            if req_source is None and edge_source != legacy_source:
                raise RankingValidationError(
                    f"Transition step {idx} edge source mismatch with legacy route segment"
                )
            if req_target is None and edge_target != legacy_target:
                raise RankingValidationError(
                    f"Transition step {idx} edge target mismatch with legacy route segment"
                )

        bound_action_ids.append(action_id)
        lineage_source = req_source or edge_source or nodes[idx]
        lineage_target = req_target or edge_target or nodes[idx + 1]
        lineage_actor = request_actor or req_source or edge_source or foothold_id
        lineage_record = {
            "step_index": idx,
            "action_id": action_id,
            "technique_id": technique_id,
            "actor": lineage_actor,
            "source": lineage_source,
            "target": lineage_target,
            "edge_id": step_edge_id,
            "derived_from_step": derived_from_step,
            "origin": (
                "observed_edge"
                if not derived
                else ("initial_attack_state" if derived_from_step is None else "derived_transition")
            ),
            "status": _audit_value(
                getattr(res, "status", None) if not isinstance(res, dict) else res.get("status")
            ),
        }
        if not isinstance(res, dict):
            snapshot_evidence = getattr(res, "snapshot_evidence", ())
            capability_provenance = getattr(res, "capability_provenance", ())
            if snapshot_evidence:
                if step_edge_id is None and derived_from_step is None:
                    lineage_record["origin"] = "snapshot_fact"
                lineage_record["snapshot_evidence"] = list(snapshot_evidence)
            if capability_provenance:
                lineage_record["capability_provenance"] = list(capability_provenance)
        request_rbcd_binding = getattr(req, "rbcd_binding", None) or (
            req.get("rbcd_binding") if isinstance(req, dict) else None
        )
        if request_rbcd_binding is not None:
            lineage_record["rbcd_binding"] = (
                asdict(request_rbcd_binding)
                if not isinstance(request_rbcd_binding, dict)
                else dict(request_rbcd_binding)
            )
        transition_lineage.append(lineage_record)
        if derived:
            semantic_lineage.append(dict(lineage_record))
        else:
            route_edge_ids.append(step_edge_id)
            route_action_step_indices.append(idx)
            provenance_locators.append(combined_locator)
            route_provenance_lineage.append(locators_list)
            route_edge_provenance_records.append(records_list)

    # Check scenario reference consistency if available
    scenario_ref = getattr(path_result, "scenario_reference", None) or (
        path_result.get("scenario_reference") if isinstance(path_result, dict) else None
    )
    if scenario_ref and scenario_ref != query_metadata.get("scenario_id"):
        raise RankingValidationError(
            f"Scenario reference mismatch: path '{scenario_ref}' != "
            f"query '{query_metadata.get('scenario_id')}'"
        )

    # Route integrity check
    if len(nodes) != len(history) + 1:
        raise RankingValidationError(
            f"PathResult node count ({len(nodes)}) does not match "
            f"transition count ({len(history)}) + 1"
        )

    # Preserve observed evidence as internally contiguous structural segments.
    # #146 action programs are semantic/state programs, not guaranteed topology walks:
    # observed edges can be separated by semantic transitions or use unrelated sources.
    structural_routes: list[dict[str, Any]] = []
    current_segment: dict[str, Any] | None = None
    for pos, edge_id in enumerate(route_edge_ids):
        edge_rec = edges_by_id[edge_id]
        source = edge_rec.get("source") if isinstance(edge_rec, dict) else edge_rec.source
        target = edge_rec.get("target") if isinstance(edge_rec, dict) else edge_rec.target
        if current_segment is None or current_segment["node_ids"][-1] != source:
            current_segment = {
                "route_id": "",
                "node_ids": [source],
                "edge_ids": [],
                "action_step_indices": [],
                "provenance_locators": [],
                "provenance_lineage": [],
                "edge_provenance_records": [],
                "semantic_lineage": [],
            }
            structural_routes.append(current_segment)
        current_segment["node_ids"].append(target)
        current_segment["edge_ids"].append(edge_id)
        current_segment["action_step_indices"].append(route_action_step_indices[pos])
        current_segment["provenance_locators"].append(provenance_locators[pos])
        current_segment["provenance_lineage"].append(route_provenance_lineage[pos])
        current_segment["edge_provenance_records"].append(route_edge_provenance_records[pos])

    if not structural_routes:
        # A #146 path can be entirely semantic when its relationships are supplied by
        # initial/derived AttackState. Preserve the absence of canonical evidence.
        structural_routes = [
            {
                "route_id": route_id,
                "node_ids": [foothold_id],
                "edge_ids": [],
                "action_step_indices": [],
                "provenance_locators": [],
                "provenance_lineage": [],
                "edge_provenance_records": [],
                "semantic_lineage": semantic_lineage,
            }
        ]
    else:
        for segment_index, segment in enumerate(structural_routes):
            segment["route_id"] = (
                route_id if len(structural_routes) == 1 else f"{route_id}:segment:{segment_index}"
            )
        structural_routes[0]["semantic_lineage"] = semantic_lineage

    edge_provenance_map = {
        eid: (
            edges_by_id[eid].get("provenance")
            if isinstance(edges_by_id[eid], dict)
            else getattr(edges_by_id[eid], "provenance", None)
        )
        for eid in route_edge_ids
    }

    transition_audit = []
    for idx, step in enumerate(history):
        result = getattr(step, "result", None) or (
            step.get("result") if isinstance(step, dict) else None
        )
        req = getattr(result, "request", None) or (
            result.get("request") if isinstance(result, dict) else None
        )
        technique_id = extract_technique_id(step, idx)
        action_id = bound_action_ids[idx]
        transition_audit.append(
            {
                "step_index": idx,
                "edge_id": (
                    getattr(step, "edge_id", None)
                    if not isinstance(step, dict)
                    else step.get("edge_id")
                ),
                "technique_id": technique_id,
                "action_id": action_id,
                "derived_from_step": _audit_value(
                    getattr(step, "derived_from_step", None)
                    if not isinstance(step, dict)
                    else step.get("derived_from_step")
                ),
                "request": _audit_value(req),
                "decision": _audit_value(result),
            }
        )

    if success_event is None:
        target_impact = query_metadata.get("target_impact_assessments", {})
        impact_record = (
            target_impact.get(target_asset_id, {}) if isinstance(target_impact, dict) else {}
        )
        success_event = impact_record.get("success_event")
    if success_event is None:
        goal = query_metadata.get("target_goal", {})
        if (
            isinstance(goal, dict)
            and goal.get("target_asset_id", target_asset_id) == target_asset_id
        ):
            success_event = goal.get("success_event")
    if not isinstance(success_event, str) or not success_event.strip():
        raise RankingValidationError(
            f"Candidate {candidate_id!r} has no explicit success-event binding for target "
            f"{target_asset_id!r}"
        )

    envelope = {
        "candidate_id": candidate_id,
        "scope_binding": scope_binding,
        "target_asset_id": target_asset_id,
        "target_binding": {"target_asset_id": target_asset_id},
        "success_event_binding": {
            "target_asset_id": target_asset_id,
            "success_event": success_event,
        },
        "bound_action_ids": bound_action_ids,
        "structural_routes": structural_routes,
        "edge_provenance_map": edge_provenance_map,
        "transition_audit": transition_audit,
        "scenario_reference": scenario_ref,
        "runtime_fact_values": _runtime_fact_audit(path_result),
    }
    if transition_lineage and all(
        record.get("status") == "applicable"
        and is_canonical_node_id(record.get("actor"))
        and is_canonical_node_id(record.get("source"))
        and is_canonical_node_id(record.get("target"))
        for record in transition_lineage
    ):
        envelope["transition_lineage"] = transition_lineage
    if state_goal_binding is not None:
        envelope["state_goal_binding"] = state_goal_binding
    return envelope


def adapt_search_candidate(*args: Any, **kwargs: Any) -> dict[str, Any]:
    """Versioned #145 search boundary; kept separate from search implementation details."""
    return convert_path_result_to_candidate_envelope(*args, **kwargs)
