"""Canonical identity for first-goal semantic programs, independent of ratings/IDs."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import fields, is_dataclass
from enum import Enum
from typing import Any


def canonical_value(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value) and not isinstance(value, type):
        return {f.name: canonical_value(getattr(value, f.name)) for f in fields(value)}
    if isinstance(value, Mapping):
        return {key: canonical_value(item) for key, item in value.items()}
    if isinstance(value, (set, frozenset)):
        return sorted((canonical_value(item) for item in value), key=canonical_json)
    if isinstance(value, (tuple, list)):
        return [canonical_value(item) for item in value]
    return value


def canonical_json(value: Any) -> str:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    )


def program_key(path: Any) -> str:
    """Keep ordered requests, state, exact edge evidence and causal parent indices.

    Canonicalization has already resolved aliases. Passive actions remain in the
    identity even if they add no work. Numeric basis, enumeration IDs and cost do
    not define equivalence. The key is scoped to the query/environment, not a claim
    that programs from different snapshots/scenarios can be ranked together.
    """
    context = path.runtime_context
    payload = {
        "version": "attack-program-identity/1",
        "nodes": path.nodes,
        "scenario_reference": path.scenario_reference,
        "authentication_context": getattr(context, "authentication_context", None),
        "steps": [
            {
                "request": step.result.request,
                "edge_id": step.edge_id,
                "derived_from_step": step.derived_from_step,
                "before": step.result.before,
                "additions": step.result.additions,
            }
            for step in path.transition_history
        ],
        "final_state": path.final_state,
        "initial_actor": path.initial_actor,
    }
    # Order by the executed history before terminal capabilities. This retains
    # the established direct-before-passive-prefix tie order on the independent
    # Week 4 oracle, while preserving every field in the equivalence key.
    ordered = [
        payload["version"],
        payload["authentication_context"],
        payload["scenario_reference"],
        payload["steps"],
        payload["nodes"],
        payload["final_state"],
        payload["initial_actor"],
    ]
    return canonical_json(canonical_value(ordered))


def program_id(key: str) -> str:
    return "sha256:" + hashlib.sha256(key.encode("utf-8")).hexdigest()
