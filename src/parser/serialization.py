"""Deterministic JSON boundary for canonical structural graphs."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import cast

from scripts.check_contract import load_contract, validate_graph

from . import Graph

_ROOT = Path(__file__).resolve().parents[2]


def _contract() -> dict:
    return load_contract()


def serialize_graph(
    graph: Graph,
    *,
    contract: dict | None = None,
    _skip_validation: bool = False,
) -> str:
    """Validate and serialize a graph with stable key and collection ordering."""

    if not _skip_validation:
        selected = contract or _contract()
        validate_graph(cast(dict, graph), selected)
    return json.dumps(graph, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def deserialize_graph(payload: str | Mapping, *, contract: dict | None = None) -> Graph:
    """Parse, validate, and return a canonical graph payload."""

    if isinstance(payload, str):
        try:
            graph = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise ValueError("graph JSON is invalid") from exc
    elif isinstance(payload, Mapping):
        graph = dict(payload)
    else:
        raise TypeError("canonical graph payload must be a JSON string or mapping")
    selected = contract or _contract()
    validate_graph(graph, selected)
    return cast(Graph, graph)


__all__ = ["deserialize_graph", "serialize_graph"]
