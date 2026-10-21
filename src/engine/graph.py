"""Contract-aware in-memory view of a canonical structural graph."""

from __future__ import annotations

import copy
import json
from collections import deque
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

import networkx as nx

from scripts.check_contract import load_contract, validate_graph
from src.parser.snapshot_facts import SnapshotFacts, deserialize_snapshot

_ROOT = Path(__file__).resolve().parents[2]


def _load_contract() -> dict[str, Any]:
    return load_contract()


class EngineGraph:
    """Small deterministic API over a directed multigraph.

    Canonical records are retained losslessly as edge/node attributes. The internal
    NetworkX graph is intentionally private; each returned record is a defensive copy.
    """

    def __init__(self, graph: nx.MultiDiGraph, metadata: dict[str, Any], assessments: list[dict]):
        self._graph = graph
        self._metadata = metadata
        self._assessments = assessments
        self._snapshot_facts: SnapshotFacts | None = None
        self._canonical_cache: dict[str, Any] | None = None
        self._edges_by_id: dict[str, dict[str, Any]] | None = None
        self._prepared_cache: Any = None

    @classmethod
    def from_canonical(
        cls,
        payload: Mapping[str, Any] | str,
        *,
        contract: dict[str, Any] | None = None,
        snapshot_facts: SnapshotFacts | None = None,
        _validated: bool = False,
    ) -> EngineGraph:
        """Validate canonical JSON/object with Graph Contract, then load its positive edges."""
        if isinstance(payload, str):
            try:
                data = json.loads(payload)
            except json.JSONDecodeError as exc:
                raise ValueError("graph JSON is invalid") from exc
        elif isinstance(payload, Mapping):
            data = dict(payload) if _validated else copy.deepcopy(dict(payload))
        else:
            raise TypeError("canonical graph must be a JSON string or mapping")

        selected_contract = contract if contract is not None else _load_contract()
        if not _validated:
            try:
                validate_graph(data, selected_contract)
            except (KeyError, TypeError, ValueError) as exc:
                raise ValueError(f"canonical graph validation failed: {exc}") from exc

        graph = nx.MultiDiGraph()
        sorted_nodes = sorted(data["nodes"], key=lambda item: item["id"])
        sorted_edges = sorted(data["edges"], key=lambda item: item["id"])
        for node in sorted_nodes:
            graph.add_node(node["id"], record=node)
        for edge in sorted_edges:
            graph.add_edge(edge["source"], edge["target"], key=edge["id"], record=edge)
        # Schema validation and evidence binding are separate guarantees. Internal
        # callers may have validated the schema, but their supplied facts must
        # still belong to this exact canonical projection.
        if snapshot_facts is not None:
            snapshot_facts.validate_binding(data)
        result = cls(graph, data["metadata"], data["assessments"])
        result._snapshot_facts = snapshot_facts
        result._canonical_cache = {
            "metadata": data["metadata"],
            "nodes": sorted_nodes,
            "edges": sorted_edges,
            "assessments": data["assessments"],
        }
        result._edges_by_id = {edge["id"]: edge for edge in sorted_edges}
        return result

    @classmethod
    def from_snapshot(cls, payload: str) -> EngineGraph:
        """Load the graph and its static evidence from the snapshot transport envelope."""
        graph, facts = deserialize_snapshot(payload)
        return cls.from_canonical(graph, snapshot_facts=facts, _validated=True)

    def to_prepared(self) -> Any:
        """Return an isolated PreparedSemanticGraph view, validating snapshot binding once."""
        if not hasattr(self, "_prepared_cache") or self._prepared_cache is None:
            from src.engine.semantics.evaluator import PreparedSemanticGraph

            canonical = (
                self._canonical_cache
                if hasattr(self, "_canonical_cache") and self._canonical_cache is not None
                else self.to_canonical()
            )
            self._prepared_cache = PreparedSemanticGraph(
                canonical,
                snapshot_facts=self.snapshot_facts,
                _skip_binding_validation=True,
                _defensive_copy=False,
            )
        return self._prepared_cache

    @property
    def snapshot_facts(self) -> SnapshotFacts | None:
        """None means the caller loaded only structural graph JSON."""
        return self._snapshot_facts

    @property
    def metadata(self) -> dict[str, Any]:
        return copy.deepcopy(self._metadata)

    @property
    def assessments(self) -> list[dict[str, Any]]:
        """Non-traversable assessments retained separately from positive relationships."""
        return copy.deepcopy(self._assessments)

    def node(self, node_id: str) -> dict[str, Any]:
        try:
            return copy.deepcopy(self._graph.nodes[node_id]["record"])
        except KeyError as exc:
            raise KeyError(f"unknown canonical node ID: {node_id}") from exc

    def nodes(self, *, kind: str | None = None, predicate: Callable[[dict], bool] | None = None):
        records = [self.node(node_id) for node_id in sorted(self._graph.nodes)]
        return tuple(
            node
            for node in records
            if (kind is None or node["kind"] == kind) and (predicate is None or predicate(node))
        )

    def edge(self, edge_id: str) -> dict[str, Any]:
        if hasattr(self, "_edges_by_id") and self._edges_by_id is not None:
            try:
                return copy.deepcopy(self._edges_by_id[edge_id])
            except KeyError as exc:
                raise KeyError(f"unknown canonical edge ID: {edge_id}") from exc
        for _, _, _, data in self._graph.edges(keys=True, data=True):
            if data["record"]["id"] == edge_id:
                return copy.deepcopy(data["record"])
        raise KeyError(f"unknown canonical edge ID: {edge_id}")

    def edges(self, *, kind: str | None = None) -> tuple[dict[str, Any], ...]:
        records = [copy.deepcopy(d["record"]) for *_, d in self._graph.edges(keys=True, data=True)]
        return tuple(
            sorted((e for e in records if kind is None or e["kind"] == kind), key=lambda e: e["id"])
        )

    def to_canonical(self) -> dict[str, Any]:
        """Return an isolated canonical mapping for existing semantic evaluators."""
        if hasattr(self, "_canonical_cache") and self._canonical_cache is not None:
            return copy.deepcopy(self._canonical_cache)
        return {
            "metadata": self.metadata,
            "nodes": list(self.nodes()),
            "edges": list(self.edges()),
            "assessments": self.assessments,
        }

    def edges_between(self, source: str, target: str) -> tuple[dict[str, Any], ...]:
        records = self._graph.get_edge_data(source, target, default={})
        return tuple(copy.deepcopy(records[key]["record"]) for key in sorted(records))

    def successors(self, node_id: str) -> tuple[str, ...]:
        self.node(node_id)
        return tuple(sorted(self._graph.successors(node_id)))

    def predecessors(self, node_id: str) -> tuple[str, ...]:
        self.node(node_id)
        return tuple(sorted(self._graph.predecessors(node_id)))

    def select_targets(self, predicate: Callable[[dict], bool]) -> tuple[dict[str, Any], ...]:
        return self.nodes(predicate=predicate)

    def reachable(self, source: str, target: str) -> bool:
        self.node(source)
        self.node(target)
        visited = {source}
        pending = deque([source])
        while pending:
            current = pending.popleft()
            if current == target:
                return True
            for successor in self.successors(current):
                if successor not in visited:
                    visited.add(successor)
                    pending.append(successor)
        return False

    def _outgoing(self, node_id: str) -> tuple[dict[str, Any], ...]:
        records = []
        for successor in sorted(self._graph.successors(node_id)):
            records.extend(self.edges_between(node_id, successor))
        return tuple(sorted(records, key=lambda edge: (edge["target"], edge["id"])))
