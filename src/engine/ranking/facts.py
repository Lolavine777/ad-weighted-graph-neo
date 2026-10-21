"""Facts ledger resolution, layer rules, and known-false veto pipeline.

Implements the 3-step resolution pipeline and truth confluence (Spec 2.2):
1. Observation conflict reconciliation (contradictory_telemetry -> Unknown).
2. Known-false veto (observed False vetoes any runtime assumption).
3. Authoritative layer semantics:
   - Layer 1 (Structural Authorization): Immutable, requires positive snapshot provenance,
     cannot be assumed.
   - Layer 2 (Host Capability & Hygiene): Immutable, telemetry observation only.
   - Layer 3 (Runtime Context): Assumed facts permitted in 'scenario' mode with rationale,
     disallowed in 'evidence_only' mode.
"""

from __future__ import annotations

from typing import Any

from src.engine.ranking.models import RankingValidationError


def resolve_facts_ledger(
    facts_ledger: Any,
    evaluation_mode: str = "scenario",
) -> dict[str, dict[str, Any]]:
    """Resolve facts ledger across all 4 contract buckets with observation reconciliation."""
    if not isinstance(facts_ledger, dict):
        raise TypeError("facts_ledger must be a dictionary")

    if evaluation_mode not in ("evidence_only", "scenario"):
        raise RankingValidationError(f"Invalid evaluation_mode: {evaluation_mode!r}")

    obs_by_pred: dict[str, list[bool]] = {}
    prov_by_pred: dict[str, list[str]] = {}
    layer_by_pred: dict[str, int] = {}

    # 0. Authoritative predicate layers first
    predicate_layers = facts_ledger.get("predicate_layers", {})
    if not isinstance(predicate_layers, dict):
        raise TypeError("predicate_layers must be a dictionary")
    for p, layer in predicate_layers.items():
        if not isinstance(p, str) or not p.strip():
            raise TypeError(f"predicate_layers predicate must be a non-empty string, got {p!r}")
        if layer not in (1, 2, 3):
            raise RankingValidationError(f"predicate_layers for {p} invalid layer: {layer}")
        layer_by_pred[p] = layer

    def register_or_check_layer(p: str, declared_layer: Any, source_desc: str) -> int:
        if declared_layer is not None:
            if declared_layer not in (1, 2, 3):
                raise RankingValidationError(
                    f"{source_desc} for predicate {p!r} has invalid layer: {declared_layer}"
                )
            if p in layer_by_pred:
                if layer_by_pred[p] != declared_layer:
                    raise RankingValidationError(
                        f"Conflicting layer declaration for predicate {p!r}: "
                        f"already defined as layer {layer_by_pred[p]}, but {source_desc} "
                        f"declares layer {declared_layer}"
                    )
            else:
                layer_by_pred[p] = declared_layer
            return declared_layer
        else:
            if p in layer_by_pred:
                return layer_by_pred[p]
            raise RankingValidationError(
                f"Missing layer declaration for predicate {p!r} in {source_desc}: "
                f"authoritative layer must be explicitly declared in predicate_layers or entry"
            )

    # 1. Process observed_facts
    obs_list = facts_ledger.get("observed_facts", [])
    if not isinstance(obs_list, list):
        raise TypeError("observed_facts must be a list")

    for idx, obs in enumerate(obs_list):
        if not isinstance(obs, dict):
            raise TypeError(f"observed_facts entry {idx} must be an object")
        p = obs.get("predicate")
        if not isinstance(p, str) or not p.strip():
            raise TypeError(f"observed_facts entry {idx} predicate must be a non-empty string")
        register_or_check_layer(p, obs.get("layer"), f"observed_facts entry {idx}")

        tv = obs.get("truth_value")
        if type(tv) is not bool:
            raise TypeError(
                f"observed_facts entry {idx} ({p}) truth_value must be a boolean, got {tv!r}"
            )
        obs_by_pred.setdefault(p, []).append(tv)

        prov = obs.get("provenance_reference") or obs.get("provenance_locator")
        if isinstance(prov, str) and prov.strip():
            prov_by_pred.setdefault(p, []).append(prov.strip())

    # 2. Process false_facts
    false_list = facts_ledger.get("false_facts", [])
    if not isinstance(false_list, list):
        raise TypeError("false_facts must be a list")

    for idx, ff in enumerate(false_list):
        if not isinstance(ff, dict):
            raise TypeError(f"false_facts entry {idx} must be an object")
        p = ff.get("predicate")
        if not isinstance(p, str) or not p.strip():
            raise TypeError(f"false_facts entry {idx} predicate must be a non-empty string")
        register_or_check_layer(p, ff.get("layer"), f"false_facts entry {idx}")

        tv = ff.get("truth_value", False)
        if type(tv) is not bool:
            raise TypeError(
                f"false_facts entry {idx} ({p}) truth_value must be a boolean, got {tv!r}"
            )
        if tv is True:
            raise RankingValidationError(
                f"false_facts entry {idx} ({p}) cannot have truth_value True"
            )
        obs_by_pred.setdefault(p, []).append(False)

    # 3. Process assumed_facts
    assumed_list = facts_ledger.get("assumed_facts", [])
    if not isinstance(assumed_list, list):
        raise TypeError("assumed_facts must be a list")

    assumed_by_pred: dict[str, list[dict[str, Any]]] = {}
    for idx, af in enumerate(assumed_list):
        if not isinstance(af, dict):
            raise TypeError(f"assumed_facts entry {idx} must be an object")
        p = af.get("predicate")
        if not isinstance(p, str) or not p.strip():
            raise TypeError(f"assumed_facts entry {idx} predicate must be a non-empty string")
        register_or_check_layer(p, af.get("layer"), f"assumed_facts entry {idx}")

        if "truth_value" not in af:
            raise RankingValidationError(
                f"assumed_facts entry {idx} ({p}) missing required truth_value"
            )
        tv = af["truth_value"]
        if type(tv) is not bool:
            raise TypeError(
                f"assumed_facts entry {idx} ({p}) truth_value must be a boolean, got {tv!r}"
            )

        rationale = af.get("rationale")
        if not isinstance(rationale, str) or not rationale.strip():
            raise RankingValidationError(
                f"assumed_facts entry {idx} ({p}) must have a non-empty rationale string"
            )

        assumed_by_pred.setdefault(p, []).append(af)

    # 4. Process unknown_facts
    unknown_list = facts_ledger.get("unknown_facts", [])
    if not isinstance(unknown_list, list):
        raise TypeError("unknown_facts must be a list")

    unknown_by_pred: dict[str, dict[str, Any]] = {}
    for idx, uf in enumerate(unknown_list):
        if not isinstance(uf, dict):
            raise TypeError(f"unknown_facts entry {idx} must be an object")
        p = uf.get("predicate")
        if not isinstance(p, str) or not p.strip():
            raise TypeError(f"unknown_facts entry {idx} predicate must be a non-empty string")
        register_or_check_layer(p, uf.get("layer"), f"unknown_facts entry {idx}")
        unknown_by_pred[p] = uf

    # Resolution pipeline
    resolved: dict[str, dict[str, Any]] = {}
    for p, layer in layer_by_pred.items():
        obs_vals = obs_by_pred.get(p)
        has_obs_true = obs_vals is not None and (True in obs_vals)
        has_obs_false = obs_vals is not None and (False in obs_vals)

        # Step 1: Observation Conflict Reconciliation
        if has_obs_true and has_obs_false:
            resolved[p] = {
                "value": "Unknown",
                "layer": layer,
                "disposition": "contradictory_telemetry",
                "reason": (
                    "Conflicting positive and negative telemetry observations "
                    "for predicate in snapshot"
                ),
            }
            continue

        # Step 2: Known-False Veto (hard veto overrides any runtime assumption)
        if has_obs_false:
            resolved[p] = {
                "value": "False",
                "layer": layer,
                "disposition": "observed_false_veto",
                "reason": "Snapshot observation confirmed false, vetoes any runtime assumption",
            }
            continue

        # Step 3: Positive Observation Resolution
        if has_obs_true:
            if layer == 1:
                provs = prov_by_pred.get(p, [])
                if provs:
                    resolved[p] = {
                        "value": "True",
                        "layer": 1,
                        "disposition": "structural_provenance_verified",
                        "reason": "Positive structural provenance confirmed from snapshot",
                        "provenance_reference": provs[0],
                    }
                else:
                    resolved[p] = {
                        "value": "Unknown",
                        "layer": 1,
                        "disposition": "missing_structural_provenance",
                        "reason": (
                            "Layer 1 structural predicate requires positive "
                            "provenance reference; unverified"
                        ),
                    }
            elif layer == 2:
                resolved[p] = {
                    "value": "True",
                    "layer": 2,
                    "disposition": "observed_true",
                    "reason": "Host capability/hygiene confirmed positive in telemetry",
                }
            elif layer == 3:
                resolved[p] = {
                    "value": "True",
                    "layer": 3,
                    "disposition": "observed_true",
                    "reason": "Runtime context confirmed positive in telemetry",
                }
            continue

        # Step 4: No Observations (neither positive nor negative)
        if layer == 1:
            resolved[p] = {
                "value": "Unknown",
                "layer": 1,
                "disposition": "missing_structural_provenance",
                "reason": "Layer 1 cannot be assumed; missing snapshot provenance",
            }
        elif layer == 2:
            resolved[p] = {
                "value": "Unknown",
                "layer": 2,
                "disposition": "missing_telemetry",
                "reason": "Host capability/hygiene observation missing from telemetry",
            }
        elif layer == 3:
            if p in assumed_by_pred:
                af_list = assumed_by_pred[p]
                tvs = {item["truth_value"] for item in af_list}
                if True in tvs and False in tvs:
                    resolved[p] = {
                        "value": "Unknown",
                        "layer": 3,
                        "disposition": "contradictory_assumptions",
                        "reason": (
                            "Conflicting positive and negative runtime assumptions declared "
                            "for predicate"
                        ),
                    }
                elif evaluation_mode == "evidence_only":
                    resolved[p] = {
                        "value": "Unknown",
                        "layer": 3,
                        "disposition": "evidence_only_disallows_assumptions",
                        "reason": "Runtime assumption ignored in evidence_only evaluation mode",
                    }
                elif False in tvs:
                    first_af = af_list[0]
                    resolved[p] = {
                        "value": "False",
                        "layer": 3,
                        "disposition": "assumed_false",
                        "reason": first_af.get(
                            "rationale", "Assumption explicitly set truth_value to False"
                        ),
                    }
                else:
                    first_af = af_list[0]
                    resolved[p] = {
                        "value": "True",
                        "layer": 3,
                        "disposition": "permitted_runtime_assumption",
                        "reason": first_af["rationale"],
                    }
            elif p in unknown_by_pred:
                resolved[p] = {
                    "value": "Unknown",
                    "layer": 3,
                    "disposition": "declared_unknown_fact",
                    "reason": unknown_by_pred[p].get(
                        "reason", "Declared unknown fact without observation"
                    ),
                }
            else:
                resolved[p] = {
                    "value": "Unknown",
                    "layer": 3,
                    "disposition": "missing_runtime_context",
                    "reason": "Runtime context predicate missing from observations and assumptions",
                }

    return resolved


def evaluate_predicate_gates(
    resolved_predicates: dict[str, dict[str, Any]], required: list[str]
) -> str:
    """Evaluate program gate status from resolved predicates: False > Unknown > True."""
    vals = [resolved_predicates.get(req, {}).get("value", "Unknown") for req in required]
    if "False" in vals:
        return "blocked"
    if "Unknown" in vals:
        return "unknown"
    return "feasible"
