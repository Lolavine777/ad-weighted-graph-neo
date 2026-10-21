"""Path Ranking Wire Adapter and Contract Validator.

Provides research-level wire contract validation, serialization, decoding,
and candidate program assessment for PathRankingQuery and PathRankingResult (v1.0.0).

Handles:
- Graph Contract 1.3 canonical identifier validation (SID, GUID, scoped SID, edge hash).
- Full 6-component query wire payload decoding and validation.
- Rational string parsing and interval bounds validation (0 <= lower <= upper <= 1).
- Non-empty string prefix validation (no coercion healing) and duplicate prefix detection.
- Target impact assessment validation (canonical node IDs, ordinal ratings vs unrated basis).
- 4-bucket facts ledger resolution: observed_facts, false_facts, assumed_facts, unknown_facts.
- Strict boolean truth value enforcement, observation conflict reconciliation, known-false veto,
  Layer 1 provenance verification, and Layer 3 scenario / evidence_only semantics.
- Direct Fraction conditional bounds evaluation (zero float precision loss).
- Full roundtrip execution: decode -> assess -> frontier -> encode -> parse back.
- Structural route traces preservation across the boundary.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
from fractions import Fraction
from typing import Any

from scripts.research.worked_example_validation import (
    IMPACT_ORDINAL,
    ActionStep,
    assess_scoped_program,
    scoped_frontier,
)

# Graph Contract 1.3 canonical identifier patterns
CANONICAL_SID_PATTERN = re.compile(r"^S-1-(?:0|[1-9][0-9]*)(?:-(?:0|[1-9][0-9]*)){1,15}$")
CANONICAL_GUID_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
)
CANONICAL_SCOPED_SID_PATTERN = re.compile(
    r"^(?:(?:domain|host):[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}:"
    r"S-1-(?:0|[1-9][0-9]*)(?:-(?:0|[1-9][0-9]*)){1,15}|"
    r"domain:sid:S-1-5-21-(?:0|[1-9][0-9]*)-(?:0|[1-9][0-9]*)-(?:0|[1-9][0-9]*):"
    r"S-1-(?:0|[1-9][0-9]*)(?:-(?:0|[1-9][0-9]*)){1,15})$"
)
CANONICAL_EDGE_ID_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")
SNAPSHOT_ID_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")
SCOPE_REQUIRED_SID_PATTERN = re.compile(r"^S-1-5-(?:18|19|20|32-(?:0|[1-9][0-9]*))$")


def is_canonical_node_id(node_id: str) -> bool:
    """Validate canonical node ID against Graph Contract 1.3 schema."""
    if not isinstance(node_id, str):
        return False
    is_unscoped_sid = bool(CANONICAL_SID_PATTERN.fullmatch(node_id))
    if is_unscoped_sid and SCOPE_REQUIRED_SID_PATTERN.fullmatch(node_id) is None:
        return True
    if bool(CANONICAL_GUID_PATTERN.fullmatch(node_id)):
        return True
    if bool(CANONICAL_SCOPED_SID_PATTERN.fullmatch(node_id)):
        return True
    return False


def canonical_edge_id(source: str, target: str, kind: str) -> str:
    """Compute the Graph Contract 1.3 canonical edge identifier."""
    if not is_canonical_node_id(source):
        raise ValueError(f"Invalid canonical source node ID: {source}")
    if not is_canonical_node_id(target):
        raise ValueError(f"Invalid canonical target node ID: {target}")
    if not isinstance(kind, str) or not kind.strip():
        raise ValueError(f"Invalid edge kind: {kind}")
    payload = json.dumps([source, target, kind], ensure_ascii=True, separators=(",", ":"))
    return f"sha256:{hashlib.sha256(payload.encode('utf-8')).hexdigest()}"


def validate_work_units_ledger(ledger: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Validate and normalize canonical work units ledger section (Spec 2.4)."""
    if not isinstance(ledger, dict):
        raise TypeError("work_units_ledger must be a dictionary")

    validated: dict[str, dict[str, Any]] = {}
    for unit_id, rec in ledger.items():
        if not isinstance(unit_id, str) or not unit_id.strip():
            raise TypeError(
                f"work_units_ledger unit ID must be a non-empty string, got {unit_id!r}"
            )
        if not isinstance(rec, dict):
            raise TypeError(f"work unit {unit_id} record must be a dict")

        overlap_state = rec.get("overlap_state", "independent")
        if overlap_state not in (
            "independent",
            "distinct_work",
            "unresolved_overlap",
            "composite_subsumed",
        ):
            raise ValueError(f"work unit {unit_id} invalid overlap_state: {overlap_state!r}")

        # Check for rubric_scores dictionary
        rubric = rec.get("rubric_scores")
        if rubric is not None and not isinstance(rubric, dict):
            raise TypeError(f"work unit {unit_id} rubric_scores must be a dict or null")

        # Determine rating_status: accept rating_status or status
        explicit_status = rec.get("rating_status") or rec.get("status")
        if explicit_status is not None:
            if explicit_status not in ("rated", "unrated"):
                raise ValueError(f"work unit {unit_id} invalid status: {explicit_status!r}")
            rating_status = explicit_status
        else:
            # Default to rated if rubric or t1/t2 provided, else unrated
            if rubric is not None or rec.get("t1") is not None:
                rating_status = "rated"
            else:
                rating_status = "unrated"

        if overlap_state == "unresolved_overlap":
            # Disallow conflicting state: cannot be rated if unresolved_overlap
            if explicit_status == "rated" or rubric is not None:
                raise ValueError(
                    f"work unit {unit_id} has conflicting state: rating_status is 'rated' "
                    f"but overlap_state is 'unresolved_overlap'"
                )
            rating_status = "unrated"
            rubric = None

        if rating_status == "rated":
            if rubric is not None:
                t1 = rubric.get("t1")
                t2 = rubric.get("t2")
                declared_cost = rubric.get("computed_cost")
                formula = rubric.get("formula", "base")
            else:
                t1 = rec.get("t1")
                t2 = rec.get("t2")
                declared_cost = rec.get("effort_cost") or rec.get("computed_cost")
                formula = rec.get("formula", "base")

            if t1 not in (1, 2, 3) or t2 not in (1, 2, 3):
                raise ValueError(f"work unit {unit_id} rated units must have t1, t2 in {{1, 2, 3}}")

            expected_cost = t1 + t2 - 2
            if declared_cost is not None and declared_cost != expected_cost:
                raise ValueError(
                    f"work unit {unit_id} cost mismatch: "
                    f"declared {declared_cost}, expected {expected_cost}"
                )

            normalized_rubric = {
                "t1": t1,
                "t2": t2,
                "formula": formula,
                "computed_cost": expected_cost,
            }
            validated[unit_id] = {
                "work_unit_id": unit_id,
                "rating_status": "rated",
                "status": "rated",
                "overlap_state": overlap_state,
                "rubric_scores": normalized_rubric,
                "t1": t1,
                "t2": t2,
                "effort_cost": expected_cost,
                "computed_cost": expected_cost,
            }
        else:
            if rubric is not None:
                raise ValueError(f"work unit {unit_id} unrated units must have rubric_scores null")
            if rec.get("effort_cost") is not None or rec.get("computed_cost") is not None:
                raise ValueError(f"work unit {unit_id} unrated units must have effort_cost null")

            validated[unit_id] = {
                "work_unit_id": unit_id,
                "rating_status": "unrated",
                "status": "unrated",
                "overlap_state": overlap_state,
                "rubric_scores": None,
                "t1": None,
                "t2": None,
                "effort_cost": None,
                "computed_cost": None,
            }

    return validated


def validate_bound_actions(
    actions: list[dict[str, Any]],
    known_work_units: set[str],
) -> list[dict[str, Any]]:
    """Validate bound actions catalog referencing canonical work units (Spec 2.3)."""
    if not isinstance(actions, list):
        raise TypeError("bound_actions must be a list")

    validated: list[dict[str, Any]] = []
    for idx, act in enumerate(actions):
        if not isinstance(act, dict):
            raise TypeError(f"bound_actions entry {idx} must be a dict")

        action_id = act.get("action_id")
        if not isinstance(action_id, str) or not action_id.strip():
            raise TypeError(f"bound_actions entry {idx} action_id must be a non-empty string")

        is_passive = bool(act.get("is_passive_closure", False))

        bound_units = act.get("referenced_work_unit_ids")
        if bound_units is None:
            bound_units = act.get("bound_work_units")

        if is_passive:
            if bound_units is None:
                bound_units = []
            if not isinstance(bound_units, list):
                raise TypeError(
                    f"bound_actions entry {idx} referenced_work_unit_ids must be a list"
                )
        else:
            if not isinstance(bound_units, list) or not bound_units:
                raise TypeError(
                    f"bound_actions entry {idx} active action must have non-empty "
                    f"referenced_work_unit_ids"
                )

        for u in bound_units:
            if not isinstance(u, str) or u not in known_work_units:
                raise ValueError(f"bound_actions entry {idx} references unknown work unit: {u!r}")

        src = act.get("actor_id") or act.get("source_node_id")
        tgt = act.get("target_id") or act.get("target_node_id")
        if src is not None and not is_canonical_node_id(src):
            raise ValueError(f"bound_actions entry {idx} invalid actor_id: {src!r}")
        if tgt is not None and not is_canonical_node_id(tgt):
            raise ValueError(f"bound_actions entry {idx} invalid target_id: {tgt!r}")

        edge_id = act.get("edge_id")
        if edge_id is not None and not CANONICAL_EDGE_ID_PATTERN.match(edge_id):
            raise ValueError(f"bound_actions entry {idx} invalid edge_id: {edge_id!r}")

        has_tech_name = "technique_name" in act
        has_tech = "technique" in act
        tech_name_val = act.get("technique_name")
        tech_val = act.get("technique")

        if has_tech_name:
            if not isinstance(tech_name_val, str) or not tech_name_val.strip():
                raise TypeError(
                    f"bound_actions entry {idx} technique_name must be non-empty string, "
                    f"got {type(tech_name_val).__name__}"
                )
        if has_tech:
            if not isinstance(tech_val, str) or not tech_val.strip():
                raise TypeError(
                    f"bound_actions entry {idx} technique must be non-empty string, "
                    f"got {type(tech_val).__name__}"
                )
        if has_tech_name and has_tech:
            if tech_name_val != tech_val:
                raise ValueError(
                    f"bound_actions entry {idx} conflicting technique aliases: "
                    f"technique_name={tech_name_val!r} != technique={tech_val!r}"
                )
            effective_tech = tech_name_val
        elif has_tech_name:
            effective_tech = tech_name_val
        elif has_tech:
            effective_tech = tech_val
        else:
            effective_tech = None

        norm_act = dict(act)
        norm_act["action_id"] = action_id
        if effective_tech is not None:
            norm_act["technique_name"] = effective_tech
            norm_act["technique"] = effective_tech
        norm_act["actor_id"] = src
        norm_act["source_node_id"] = src
        norm_act["target_id"] = tgt
        norm_act["target_node_id"] = tgt
        norm_act["referenced_work_unit_ids"] = bound_units
        norm_act["bound_work_units"] = bound_units
        norm_act["is_passive_closure"] = is_passive
        norm_act["requires"] = act.get("requires", [])
        norm_act["adds"] = act.get("adds", [])
        validated.append(norm_act)

    return validated


def validate_and_decode_bounds_table(
    wire_bounds_list: list[dict[str, Any]],
    known_work_units: set[str] | None = None,
) -> dict[tuple[str, ...], tuple[Fraction, Fraction]]:
    """Validate wire conditional bounds list and decode into memory tuple-keyed table.

    Enforces:
    - Array of objects with 'prefix', 'lower', and 'upper'.
    - Prefix elements must be non-empty strings (no coercion healing).
    - Uniqueness of prefix across the table (DuplicatePrefixError).
    - 0 <= lower <= upper <= 1 bounds invariant.
    """
    if not isinstance(wire_bounds_list, list):
        raise TypeError("conditional_bounds_table must be a list of objects")

    table: dict[tuple[str, ...], tuple[Fraction, Fraction]] = {}
    for idx, entry in enumerate(wire_bounds_list):
        if not isinstance(entry, dict):
            raise TypeError(f"Entry {idx} in conditional_bounds_table must be an object")

        prefix_raw = entry.get("prefix")
        if not isinstance(prefix_raw, (list, tuple)):
            raise TypeError(f"Entry {idx} prefix must be a list of string identifiers")
        if not prefix_raw:
            raise ValueError(f"Entry {idx} prefix cannot be empty")

        prefix_elements: list[str] = []
        for step_idx, step in enumerate(prefix_raw):
            if not isinstance(step, str) or not step.strip():
                raise TypeError(
                    f"Entry {idx} prefix step {step_idx} must be a non-empty string, got {step!r}"
                )
            if known_work_units is not None and step not in known_work_units:
                raise ValueError(f"Entry {idx} prefix references unknown work unit ID: {step!r}")
            prefix_elements.append(step)

        prefix = tuple(prefix_elements)
        if prefix in table:
            raise ValueError(f"DuplicatePrefixError: duplicate prefix {prefix} at entry {idx}")

        lower_raw = entry.get("lower")
        upper_raw = entry.get("upper")
        if lower_raw is None or upper_raw is None:
            raise ValueError(f"Entry {idx} must provide both 'lower' and 'upper' bounds")

        try:
            lower = Fraction(str(lower_raw))
            upper = Fraction(str(upper_raw))
        except (ValueError, ZeroDivisionError) as err:
            msg = f"Entry {idx} bounds must be valid rational numbers/strings: {err}"
            raise ValueError(msg) from err

        if not (0 <= lower <= upper <= 1):
            msg = (
                f"Entry {idx} bounds interval [{lower}, {upper}] is invalid: "
                "must satisfy 0 <= lower <= upper <= 1"
            )
            raise ValueError(msg)

        table[prefix] = (lower, upper)

    return table


def validate_target_impact_assessments(
    assessments: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    """Validate target impact assessments mapping.

    Enforces:
    - Mapping from canonical target asset ID to assessment object.
    - Each asset ID must be a valid canonical node ID.
    - rating_status must be 'rated' or 'unrated'.
    - If 'rated', consequence_rating must be in ('Low', 'Medium', 'High', 'Critical').
    - If 'unrated', consequence_rating must be null, and missing_basis_reasons provided.
    """
    if not isinstance(assessments, dict):
        raise TypeError("target_impact_assessments must be a dictionary")

    validated: dict[str, dict[str, Any]] = {}
    for asset_id, record in assessments.items():
        if not is_canonical_node_id(asset_id):
            raise ValueError(f"Target asset ID {asset_id!r} is not a valid canonical node ID")
        if not isinstance(record, dict):
            raise TypeError(f"Assessment for {asset_id} must be an object")

        declared_target = record.get("target_asset_id")
        if declared_target is not None and declared_target != asset_id:
            raise ValueError(
                f"Target asset ID mismatch: key {asset_id!r} != record {declared_target!r}"
            )

        status = record.get("rating_status")
        if status not in ("rated", "unrated"):
            msg = f"Asset {asset_id} rating_status must be 'rated' or 'unrated', got {status!r}"
            raise ValueError(msg)

        rating = record.get("consequence_rating")
        if status == "rated":
            if rating not in IMPACT_ORDINAL:
                msg = (
                    f"Asset {asset_id} invalid consequence_rating {rating!r}: "
                    f"must be one of {list(IMPACT_ORDINAL.keys())}"
                )
                raise ValueError(msg)
        else:  # unrated
            if rating is not None:
                msg = (
                    f"Asset {asset_id} consequence_rating must be null when "
                    "rating_status is 'unrated'"
                )
                raise ValueError(msg)
            reasons = record.get("missing_basis_reasons")
            if not isinstance(reasons, list) or not reasons:
                msg = f"Asset {asset_id} must provide a non-empty missing_basis_reasons list"
                raise ValueError(msg)
            for r in reasons:
                if not isinstance(r, str) or not r.strip():
                    raise TypeError(
                        f"Asset {asset_id} missing_basis_reasons elements must be strings"
                    )

        validated[asset_id] = record

    return validated


def resolve_facts_ledger(
    facts_ledger: dict[str, Any],
    evaluation_mode: str = "scenario",
) -> dict[str, dict[str, Any]]:
    """Resolve facts ledger across all 4 contract buckets with observation reconciliation.

    Buckets:
    - observed_facts: Positive/telemetry observations from snapshot.
    - false_facts: Negative observations (known-false facts).
    - assumed_facts: Scenario assumptions for Layer 3 context.
    - unknown_facts: Declared unmeasured/missing facts.
    - predicate_layers: Authoritative layer classification mapping (layer 1, 2, 3).
    """
    if not isinstance(facts_ledger, dict):
        raise TypeError("facts_ledger must be a dictionary")

    if evaluation_mode not in ("evidence_only", "scenario"):
        raise ValueError(f"Invalid evaluation_mode: {evaluation_mode!r}")

    # Gather observations and metadata
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
            raise ValueError(f"predicate_layers for {p} invalid layer: {layer}")
        layer_by_pred[p] = layer

    def register_or_check_layer(p: str, declared_layer: Any, source_desc: str) -> int:
        if declared_layer is not None:
            if declared_layer not in (1, 2, 3):
                raise ValueError(
                    f"{source_desc} for predicate {p!r} has invalid layer: {declared_layer}"
                )
            if p in layer_by_pred:
                if layer_by_pred[p] != declared_layer:
                    raise ValueError(
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
            raise ValueError(
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
            raise ValueError(f"false_facts entry {idx} ({p}) cannot have truth_value True")
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
            raise ValueError(f"assumed_facts entry {idx} ({p}) missing required truth_value")
        tv = af["truth_value"]
        if type(tv) is not bool:
            raise TypeError(
                f"assumed_facts entry {idx} ({p}) truth_value must be a boolean, got {tv!r}"
            )

        rationale = af.get("rationale")
        if not isinstance(rationale, str) or not rationale.strip():
            raise ValueError(
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
                    # Contradictory assumptions: order-independent resolution to Unknown
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


def format_rational_string(val: Fraction | int) -> str:
    """Serialize Fraction or integer to lossless rational string."""
    if isinstance(val, int):
        return str(val)
    if val.denominator == 1:
        return str(val.numerator)
    return f"{val.numerator}/{val.denominator}"


def decode_ranking_query(query_json_str: str) -> dict[str, Any]:
    """Parse and validate full PathRankingQuery JSON wire payload.

    Enforces all 6 mandatory top-level sections according to the specification:
    1. query_metadata
    2. facts_ledger
    3. bound_actions
    4. work_units_ledger
    5. conditional_bounds_table
    6. target_impact_assessments
    """
    if not isinstance(query_json_str, str):
        raise TypeError("query_json_str must be a JSON string")

    query = json.loads(query_json_str)
    if not isinstance(query, dict):
        raise TypeError("Top-level query payload must be a JSON object")

    # Enforce all 6 mandatory top-level sections
    required_sections = [
        "query_metadata",
        "facts_ledger",
        "bound_actions",
        "work_units_ledger",
        "conditional_bounds_table",
        "target_impact_assessments",
    ]
    for section in required_sections:
        if section not in query or query[section] is None:
            raise ValueError(f"Missing required top-level query component: {section!r}")

    meta = query["query_metadata"]
    if not isinstance(meta, dict):
        raise TypeError("query_metadata must be a dictionary")

    # Required query metadata fields
    required_meta = [
        "query_id",
        "version",
        "scenario_id",
        "scenario_version",
        "snapshot_id",
        "evaluation_mode",
        "work_boundary",
        "foothold_node_id",
        "target_goal",
        "horizon",
        "active_work_budget",
    ]
    for field in required_meta:
        if field not in meta or meta[field] is None:
            raise ValueError(f"Missing required query_metadata field: {field!r}")

    if meta["version"] != "1.0.0":
        raise ValueError(f"Unsupported contract version: {meta['version']!r}, expected '1.0.0'")

    if meta["evaluation_mode"] not in ("evidence_only", "scenario"):
        raise ValueError(f"Invalid evaluation_mode: {meta['evaluation_mode']!r}")

    if not SNAPSHOT_ID_PATTERN.match(str(meta["snapshot_id"])):
        raise ValueError(
            f"Invalid snapshot_id: {meta['snapshot_id']!r}, must match ^sha256:[0-9a-f]{{64}}$"
        )

    if not is_canonical_node_id(meta["foothold_node_id"]):
        raise ValueError(f"Invalid foothold_node_id: {meta['foothold_node_id']!r}")

    budget = meta["active_work_budget"]
    if type(budget) is not int or budget < 0:
        raise ValueError(f"active_work_budget must be a non-negative integer, got {budget!r}")

    target_goal = meta["target_goal"]
    if not isinstance(target_goal, dict):
        raise TypeError("target_goal must be a dictionary")
    if not target_goal.get("goal_id") or not isinstance(
        target_goal.get("required_predicates"), list
    ):
        raise ValueError("target_goal must contain goal_id and required_predicates list")

    # Validate work units ledger
    validated_units = validate_work_units_ledger(query["work_units_ledger"])
    known_units = set(validated_units.keys())

    # Validate bound actions referencing work units
    validated_actions = validate_bound_actions(query["bound_actions"], known_units)

    # Validate conditional bounds referencing work units
    decoded_bounds = validate_and_decode_bounds_table(
        query["conditional_bounds_table"], known_work_units=known_units
    )

    # Validate target impact assessments
    validated_impacts = validate_target_impact_assessments(query["target_impact_assessments"])

    # Resolve facts ledger
    resolved_facts = resolve_facts_ledger(
        query["facts_ledger"],
        evaluation_mode=meta["evaluation_mode"],
    )

    # Validate authoritative classification for all predicates in actions and target goal
    authoritative_layers: dict[str, int] = dict(query["facts_ledger"].get("predicate_layers", {}))
    for p, v in resolved_facts.items():
        if "layer" in v:
            authoritative_layers[p] = v["layer"]

    for idx, act in enumerate(validated_actions):
        for req in act.get("requires", []):
            if req not in authoritative_layers:
                raise ValueError(
                    f"Missing authoritative layer classification for predicate {req!r} in "
                    f"bound_actions entry {idx} (requires): authoritative layer must be explicitly "
                    f"declared in predicate_layers or facts_ledger"
                )
        for add_p in act.get("adds", []):
            if add_p not in authoritative_layers:
                raise ValueError(
                    f"Missing authoritative layer classification for predicate {add_p!r} in "
                    f"bound_actions entry {idx} (adds): authoritative layer must be explicitly "
                    f"declared in predicate_layers or facts_ledger"
                )

    for gp in target_goal.get("required_predicates", []):
        if gp not in authoritative_layers:
            raise ValueError(
                f"Missing authoritative layer classification for predicate {gp!r} in "
                f"target_goal.required_predicates: authoritative layer must be explicitly "
                f"declared in predicate_layers or facts_ledger"
            )

    return {
        "query_metadata": meta,
        "facts_ledger": query["facts_ledger"],
        "predicate_layers": authoritative_layers,
        "resolved_facts": resolved_facts,
        "bound_actions": validated_actions,
        "work_units_ledger": validated_units,
        "conditional_bounds_table": decoded_bounds,
        "target_impact_assessments": validated_impacts,
    }


def assess_candidate_program(
    decoded_query: dict[str, Any],
    candidate_envelope: dict[str, Any],
) -> dict[str, Any]:
    """Assess a candidate attack program against decoded query constraints.

    Derives:
    - Action catalog binding and required predicates from actions and target goal
    - Gates status from resolved_facts
    - Consequence impact from target_impact_assessments
    - ActionStep unit instances from normalized work_units_ledger
    - Budget limit enforcement: budget_exceeded -> status blocked
    - Exact Fraction bounds from assess_scoped_program
    - Preserves structural route traces across the boundary.
    """
    candidate_id = candidate_envelope["candidate_id"]
    target_asset_id = candidate_envelope["target_asset_id"]

    # Validate canonical identifiers in candidate
    if not is_canonical_node_id(target_asset_id):
        raise ValueError(f"Candidate {candidate_id} invalid target_asset_id: {target_asset_id}")
    if target_asset_id not in decoded_query["target_impact_assessments"]:
        raise ValueError(
            f"Candidate {candidate_id} target asset {target_asset_id} not in assessments"
        )

    # Validate structural routes
    structural_routes = candidate_envelope.get("structural_routes", [])
    for r in structural_routes:
        for nid in r.get("node_ids", []):
            if not is_canonical_node_id(nid):
                raise ValueError(f"Route node {nid} not a valid canonical node ID")
        for eid in r.get("edge_ids", []):
            if not CANONICAL_EDGE_ID_PATTERN.match(eid):
                raise ValueError(f"Route edge {eid} does not match ^sha256:[0-9a-f]{{64}}$")
        for loc in r.get("provenance_locators", []):
            if not isinstance(loc, str) or not loc.strip():
                raise ValueError(f"Route provenance locator must be a non-empty string: {loc!r}")

    # 1. Action binding & target reachability verification
    actions_catalog = {act["action_id"]: act for act in decoded_query["bound_actions"]}
    bound_action_ids = candidate_envelope.get("bound_action_ids")

    if bound_action_ids is None:
        raise ValueError(
            f"Candidate {candidate_id} must explicitly specify bound_action_ids; "
            "automatic inference from work packets is disallowed."
        )
    if not isinstance(bound_action_ids, list):
        raise TypeError(f"Candidate {candidate_id} bound_action_ids must be a list")
    for aid in bound_action_ids:
        if aid not in actions_catalog:
            raise ValueError(f"Candidate {candidate_id} references unknown action: {aid!r}")
    cand_actions = [actions_catalog[aid] for aid in bound_action_ids]

    initial_cand_actions = list(cand_actions)
    initial_action_targets = {act["target_id"] for act in cand_actions}
    foothold_id = decoded_query["query_metadata"].get("foothold_node_id")

    # If target_goal in query_metadata specifies target_asset_id, verify matching asset
    target_goal = decoded_query["query_metadata"].get("target_goal", {})
    goal_target = target_goal.get("target_asset_id")
    if goal_target and goal_target != target_asset_id:
        raise ValueError(
            f"Candidate {candidate_id} target_asset_id {target_asset_id!r} does not match "
            f"target_goal target_asset_id {goal_target!r}"
        )

    # Initial target asset reachability check on declared actions
    # (structural route presence is insufficient)
    if cand_actions:
        if target_asset_id not in initial_action_targets:
            raise ValueError(
                f"Candidate {candidate_id} target_asset_id {target_asset_id!r} is not reached "
                f"by bound actions"
            )
    else:
        if target_asset_id != foothold_id:
            raise ValueError(
                f"Candidate {candidate_id} target_asset_id {target_asset_id!r} is not reached "
                f"by initial foothold"
            )

    impact_rec = decoded_query["target_impact_assessments"][target_asset_id]
    goal_event = target_goal.get("success_event")
    if goal_event:
        assessment_event = impact_rec.get("success_event")
        if not assessment_event:
            raise ValueError(
                f"Target impact assessment for {target_asset_id!r} is missing required "
                f"success_event to match target_goal"
            )
        if assessment_event != goal_event:
            raise ValueError(
                f"Target impact assessment success_event {assessment_event!r} "
                f"does not match target_goal success_event {goal_event!r}"
            )

    impact = impact_rec.get("consequence_rating")
    impact_status = impact_rec.get("rating_status", "unrated")

    # Initial canonical work packets of declared bound actions
    initial_canonical_packets: list[tuple[str, ...]] = []
    for act in cand_actions:
        units = act.get("referenced_work_unit_ids", [])
        if units:
            initial_canonical_packets.append(tuple(units))
        elif act.get("is_passive_closure"):
            initial_canonical_packets.append(())
    if not initial_canonical_packets:
        initial_canonical_packets = [()]

    # Reconcile candidate work packets against declared actions
    if "work_packets" in candidate_envelope:
        cand_raw_packets = candidate_envelope["work_packets"]
        if not isinstance(cand_raw_packets, list):
            raise TypeError(f"Candidate {candidate_id} work_packets must be a list")
        parsed_cand_packets = [tuple(p) for p in cand_raw_packets]
        if parsed_cand_packets != initial_canonical_packets:
            raise ValueError(
                f"Candidate {candidate_id} work_packets {parsed_cand_packets!r} do not match "
                f"authoritative work packets derived from bound_action_ids "
                f"{initial_canonical_packets!r}"
            )

    # 2. Sequential step-by-step evaluation, Layer 1 immutability & first hitting time replay
    resolved_facts = decoded_query["resolved_facts"]
    current_facts: dict[str, str] = {p: v["value"] for p, v in resolved_facts.items()}
    predicate_layers: dict[str, int] = decoded_query.get("predicate_layers") or dict(
        decoded_query["facts_ledger"].get("predicate_layers", {})
    )
    for p, v in resolved_facts.items():
        if "layer" in v:
            predicate_layers[p] = v["layer"]
    gates_eval: dict[str, Any] = {}

    goal_required = target_goal.get("required_predicates", [])
    cand_required = candidate_envelope.get("required_predicates", [])
    for req in cand_required:
        if req not in predicate_layers:
            raise ValueError(
                f"Missing authoritative layer classification for predicate {req!r} in "
                f"candidate {candidate_id!r} required_predicates: authoritative layer must be "
                f"explicitly declared in predicate_layers or facts_ledger"
            )

    all_predicates_to_check = set(cand_required)
    for act in cand_actions:
        for req in act.get("requires", []):
            all_predicates_to_check.add(req)
    for gp in goal_required:
        all_predicates_to_check.add(gp)

    for p in sorted(all_predicates_to_check):
        gates_eval[p] = current_facts.get(p, "Unknown")

    def is_goal_satisfied(facts: dict[str, str]) -> tuple[bool, str]:
        st = "feasible"
        for p_goal in goal_required:
            v_goal = facts.get(p_goal, "Unknown")
            if v_goal == "False":
                return False, "blocked"
            elif v_goal == "Unknown":
                st = "unknown"
        return (st == "feasible"), st

    # Step 2a: Evaluate candidate's initial required predicates
    initial_gate_status = "feasible"
    for req in cand_required:
        val = current_facts.get(req, "Unknown")
        gates_eval[req] = val
        if val == "False":
            initial_gate_status = "blocked"
        elif val == "Unknown" and initial_gate_status != "blocked":
            initial_gate_status = "unknown"

    gate_status = initial_gate_status

    # Step 2b: Evaluate each action sequentially up to first hitting time
    init_sat, init_status = is_goal_satisfied(current_facts)
    if init_sat:
        trimmed_actions: list[dict[str, Any]] | None = []
        goal_reached = True
    else:
        trimmed_actions = None
        goal_reached = False

        if gate_status != "blocked":
            for k, act in enumerate(cand_actions):
                act_blocked = False
                act_unknown = False
                for req in act.get("requires", []):
                    val = current_facts.get(req, "Unknown")
                    gates_eval[req] = val
                    if val == "False":
                        act_blocked = True
                    elif val == "Unknown":
                        act_unknown = True

                if act_blocked:
                    gate_status = "blocked"
                    break
                if act_unknown:
                    if gate_status != "blocked":
                        gate_status = "unknown"
                    break

                # Action succeeded: update current state with additions
                # CRITICAL (Finding 1): Only Layer 3 runtime-derived predicates can be
                # mutated by action effects. Layer 1 and Layer 2 are immutable evidence.
                for add_p in act.get("adds", []):
                    p_layer = resolved_facts.get(add_p, {}).get("layer")
                    if p_layer is None:
                        p_layer = predicate_layers.get(add_p)
                    if p_layer != 3:
                        # Layer 1 and Layer 2 predicates are immutable based on evidence
                        continue
                    current_facts[add_p] = "True"
                    gates_eval[add_p] = "True"

                # Check first hitting time (Finding 3)
                step_sat, step_status = is_goal_satisfied(current_facts)
                if step_sat:
                    trimmed_actions = cand_actions[: k + 1]
                    goal_reached = True
                    # CRITICAL (Finding 1): gate_status is NOT overwritten to "feasible"!
                    # It preserves initial_gate_status (e.g. "unknown" or "feasible").
                    break

        if not goal_reached:
            # Evaluate target goal predicates at termination point
            for gp in goal_required:
                val = current_facts.get(gp, "Unknown")
                gates_eval[gp] = val
                if val == "False":
                    gate_status = "blocked"
                elif val == "Unknown" and gate_status != "blocked":
                    gate_status = "unknown"

    # Step 2c: Synchronize trimmed actions, work packets, and route traces (Finding 3)
    if goal_reached and trimmed_actions is not None:
        cand_actions = trimmed_actions
        bound_action_ids = [act["action_id"] for act in trimmed_actions]

        # Only synchronize/trim routes if a suffix of actions was actually trimmed
        if len(trimmed_actions) < len(initial_cand_actions):
            trimmed_routes = []
            for r in structural_routes:
                edge_ids = r.get("edge_ids", [])
                node_ids = r.get("node_ids", [])
                locators = r.get("provenance_locators", [])
                trimmed_r = dict(r)

                # Validate verified 1-to-1 mapping before any trimming
                # 1. Every declared initial action must have an explicit edge_id
                for act_idx, act in enumerate(initial_cand_actions):
                    if not act.get("edge_id"):
                        raise ValueError(
                            f"Candidate {candidate_id} cannot safely synchronize structural_routes "
                            f"upon suffix trimming: missing edge_id mapping on bound action "
                            f"{act.get('action_id')!r} at step {act_idx}"
                        )

                # 2. Structural route must have edge_ids, node_ids, and provenance_locators
                if not edge_ids:
                    raise ValueError(
                        f"Candidate {candidate_id} cannot safely synchronize structural_routes "
                        f"upon suffix trimming: route {r.get('route_id')!r} missing edge_ids"
                    )
                if not node_ids:
                    raise ValueError(
                        f"Candidate {candidate_id} cannot safely synchronize structural_routes "
                        f"upon suffix trimming: route {r.get('route_id')!r} missing node_ids"
                    )
                if not locators:
                    raise ValueError(
                        f"Candidate {candidate_id} cannot safely synchronize structural_routes "
                        f"upon suffix trimming: route {r.get('route_id')!r} missing "
                        f"provenance_locators"
                    )

                # 3. Cardinality checks
                if len(edge_ids) != len(initial_cand_actions):
                    raise ValueError(
                        f"Candidate {candidate_id} cannot safely synchronize structural_routes "
                        f"upon suffix trimming: route edge count ({len(edge_ids)}) does not "
                        f"match declared action count ({len(initial_cand_actions)})"
                    )
                if len(node_ids) != len(initial_cand_actions) + 1:
                    raise ValueError(
                        f"Candidate {candidate_id} cannot safely synchronize structural_routes "
                        f"upon suffix trimming: route node count ({len(node_ids)}) must be "
                        f"{len(initial_cand_actions) + 1}"
                    )
                if len(locators) != len(initial_cand_actions):
                    raise ValueError(
                        f"Candidate {candidate_id} cannot safely synchronize structural_routes "
                        f"upon suffix trimming: route provenance_locators count ({len(locators)}) "
                        f"must be {len(initial_cand_actions)}"
                    )

                # 4. Verified 1-to-1 edge mapping and sequence order
                for act_idx, act in enumerate(initial_cand_actions):
                    expected_eid = act["edge_id"]
                    if edge_ids[act_idx] != expected_eid:
                        raise ValueError(
                            f"Candidate {candidate_id} cannot safely synchronize structural_routes "
                            f"upon suffix trimming: route edge {edge_ids[act_idx]!r} at position "
                            f"{act_idx} does not match bound action {act['action_id']!r} "
                            f"edge_id {expected_eid!r}"
                        )

                # Synchronize prefix traces after 1-to-1 mapping is fully verified
                if len(trimmed_actions) == 0:
                    trimmed_r["edge_ids"] = []
                    trimmed_r["provenance_locators"] = []
                    trimmed_r["node_ids"] = [node_ids[0]]
                else:
                    n_trim = len(trimmed_actions)
                    trimmed_r["edge_ids"] = edge_ids[:n_trim]
                    trimmed_r["node_ids"] = node_ids[: n_trim + 1]
                    trimmed_r["provenance_locators"] = locators[:n_trim]

                trimmed_routes.append(trimmed_r)
            structural_routes = trimmed_routes

    # CRITICAL: Verify target asset reachability on effective executed actions
    effective_targets = {act["target_id"] for act in cand_actions}
    if cand_actions:
        if target_asset_id not in effective_targets:
            raise ValueError(
                f"Candidate {candidate_id} target_asset_id {target_asset_id!r} is not reached "
                f"by effective actions in executed prefix"
            )
    else:
        if target_asset_id != foothold_id:
            raise ValueError(
                f"Candidate {candidate_id} target_asset_id {target_asset_id!r} is not reached "
                f"by initial foothold"
            )

    # Derive work packets for the effective actions
    canonical_packets: list[tuple[str, ...]] = []
    for act in cand_actions:
        units = act.get("referenced_work_unit_ids", [])
        if units:
            canonical_packets.append(tuple(units))
        elif act.get("is_passive_closure"):
            canonical_packets.append(())
    if not canonical_packets:
        canonical_packets = [()]
    work_packets = canonical_packets

    # 3. Active work budget check on effective work packets
    budget_limit = decoded_query["query_metadata"]["active_work_budget"]
    distinct_active_units = tuple(dict.fromkeys(u for packet in work_packets for u in packet))
    budget_exceeded = len(distinct_active_units) > budget_limit
    if budget_exceeded:
        gate_status = "blocked"
        gates_eval["active_work_budget"] = "budget_exceeded"

    # 5. Build units mapping from normalized work_units_ledger
    ledger = decoded_query["work_units_ledger"]
    units: dict[str, ActionStep | None] = {}
    for packet in work_packets:
        for u in packet:
            if u not in ledger:
                raise ValueError(f"Candidate {candidate_id} references unknown work unit: {u}")
            rec = ledger[u]
            if (
                rec.get("rating_status") == "rated"
                and rec.get("overlap_state") != "unresolved_overlap"
            ):
                units[u] = ActionStep(
                    name=u,
                    step_number=1,
                    action_type="active",
                    t1=rec["t1"],
                    t2=rec["t2"],
                    t3="low",
                    likelihood="medium",
                    gate_status="feasible",
                    fact_stratum="runtime",
                )
            else:
                units[u] = None

    # 6. Evaluate assessment via assess_scoped_program
    gate_val = (
        True if gate_status == "feasible" else False if gate_status == "blocked" else "Unknown"
    )
    assessed = assess_scoped_program(
        packets=work_packets,
        units=units,
        conditional_bounds=decoded_query["conditional_bounds_table"],
        gates=(gate_val,),
    )

    status = assessed["status"]
    unrated_work_units = list(assessed["unrated_work_units"])
    program = list(assessed["program"])
    likelihood_interval = assessed["likelihood_interval"]

    if likelihood_interval is not None:
        likelihood_basis_summary = "Derived from prefix conditional bounds product"
    elif budget_exceeded:
        likelihood_basis_summary = "Withheld: candidate active work units exceed budget_limit"
    elif status == "blocked":
        likelihood_basis_summary = "Withheld: candidate execution is blocked by predicate gating"
    elif status == "unknown":
        likelihood_basis_summary = "Withheld: candidate execution gate status is unknown"
    else:
        likelihood_basis_summary = "Withheld: missing conditional prefix bounds in table"

    return {
        "candidate_id": candidate_id,
        "bound_action_ids": bound_action_ids,
        "target_asset_id": target_asset_id,
        "program": program,
        "structural_routes": structural_routes,
        "status": status,
        "gates_evaluation": gates_eval,
        "nominal_effort": assessed["nominal_effort"],
        "effort": assessed["effort"],
        "effort_status": assessed["effort_status"],
        "unrated_work_units": unrated_work_units,
        "impact": impact,
        "consequence_rating": impact,
        "impact_status": impact_status,
        "likelihood_interval": likelihood_interval,
        "likelihood_status": "rated" if likelihood_interval is not None else "unrated",
        "likelihood_basis_summary": likelihood_basis_summary,
    }


def execute_ranking_roundtrip(
    query_json_str: str,
    candidates: list[dict[str, Any]],
    upstream_coverage: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Execute full ranking roundtrip: decode -> assess -> frontier -> encode -> decode."""
    if not isinstance(candidates, list):
        raise TypeError("candidates must be a list of candidate envelopes")

    # Validate unique candidate_id before assessment (prevent silent overwrite)
    seen_candidate_ids: set[str] = set()
    for idx, cand in enumerate(candidates):
        if not isinstance(cand, dict):
            raise TypeError(f"Candidate envelope at index {idx} must be a dictionary")
        cid = cand.get("candidate_id")
        if not isinstance(cid, str) or not cid.strip():
            raise TypeError(
                f"Candidate envelope at index {idx} must have a non-empty string candidate_id"
            )
        if cid in seen_candidate_ids:
            raise ValueError(f"Duplicate candidate_id detected: {cid!r}")
        seen_candidate_ids.add(cid)

    decoded = decode_ranking_query(query_json_str)
    assessed_candidates = [assess_candidate_program(decoded, cand) for cand in candidates]

    # Map to candidates dictionary for scoped_frontier
    candidates_by_name = {c["candidate_id"]: c for c in assessed_candidates}
    frontier_result = scoped_frontier(candidates_by_name)

    eligible_map = dict(frontier_result["eligible"])
    diagnostics_map = dict(frontier_result["diagnostics"])
    frontier_ids = list(frontier_result["frontier"])

    # If any candidate was blocked due to budget, ensure reason is annotated in diagnostics
    for cand in assessed_candidates:
        cid = cand["candidate_id"]
        if cand.get("gates_evaluation", {}).get("active_work_budget") == "budget_exceeded":
            if cid in diagnostics_map:
                if "work_budget_exceeded" not in diagnostics_map[cid]["reasons"]:
                    diagnostics_map[cid]["reasons"].append("work_budget_exceeded")

    # Search metadata and coverage resolution (Spec 3.1)
    budget_limit = decoded["query_metadata"]["active_work_budget"]
    has_budget_exceeded = any(
        c.get("gates_evaluation", {}).get("active_work_budget") == "budget_exceeded"
        for c in assessed_candidates
    )

    upstream_cov = upstream_coverage or decoded["query_metadata"].get("coverage")
    upstream_caps: dict[str, Any] = {}
    if upstream_cov is not None and isinstance(upstream_cov.get("caps_applied"), dict):
        upstream_caps = upstream_cov["caps_applied"]

    if upstream_cov is not None:
        completeness_scope = upstream_cov.get("completeness_scope", "unspecified_subset")
        is_truncated = bool(upstream_cov.get("is_truncated", False)) or has_budget_exceeded
        truncation_reasons = list(upstream_cov.get("truncation_reasons", []))
        if has_budget_exceeded and "work_budget_exceeded" not in truncation_reasons:
            truncation_reasons.append("work_budget_exceeded")
        if is_truncated:
            completeness_scope = "partial_truncated"
    else:
        if has_budget_exceeded:
            is_truncated = True
            truncation_reasons = ["work_budget_exceeded"]
            completeness_scope = "partial_truncated"
        else:
            is_truncated = False
            truncation_reasons = []
            completeness_scope = "unspecified_subset"

    search_meta = {
        "budget_limit": budget_limit,
        "candidates_evaluated": len(assessed_candidates),
        "is_truncated": is_truncated,
        "truncation_reasons": truncation_reasons,
        "caps_applied": {
            "max_active_work_budget": (
                min(budget_limit, upstream_caps["max_active_work_budget"])
                if isinstance(upstream_caps.get("max_active_work_budget"), int)
                else budget_limit
            ),
            "max_candidates": upstream_caps.get("max_candidates"),
            "timeout_ms": upstream_caps.get("timeout_ms"),
            "max_expansions": upstream_caps.get("max_expansions"),
        },
        "completeness_scope": completeness_scope,
        "search_algorithm": "provided_candidate_assessment",
    }

    # Min-Effort-to-DA Baseline calculation (Spec 3.4)
    # Baseline coverage mirrors the evaluated candidate set's limits unless an
    # independent query was performed
    feasible_rated = [
        c
        for c in assessed_candidates
        if c.get("status") == "feasible"
        and c.get("effort_status") == "rated"
        and c.get("effort") is not None
    ]
    target_goal = decoded["query_metadata"].get("target_goal", {})
    goal_id = target_goal.get("goal_id", "target_goal")

    baseline_coverage = {
        "is_truncated": is_truncated,
        "truncation_reasons": list(truncation_reasons),
        "completeness_scope": completeness_scope,
    }

    if feasible_rated:
        best_cand = min(feasible_rated, key=lambda c: c["effort"])
        baseline = {
            "goal_id": goal_id,
            "best_candidate_id": best_cand["candidate_id"],
            "minimum_effort_value": best_cand["effort"],
            "associated_likelihood_interval": best_cand["likelihood_interval"],
            "associated_impact": best_cand["impact"],
            "coverage_disclosure": (
                "Baseline evaluated over candidate set within active work budget; "
                "does not guarantee global minimum if unrated work units or unvisited paths exist."
            ),
            "baseline_coverage": baseline_coverage,
        }
    else:
        baseline = {
            "goal_id": goal_id,
            "best_candidate_id": None,
            "minimum_effort_value": None,
            "associated_likelihood_interval": None,
            "associated_impact": None,
            "coverage_disclosure": "No feasible rated candidate found in evaluated set.",
            "baseline_coverage": baseline_coverage,
        }

    result_payload = {
        "query_id": decoded["query_metadata"]["query_id"],
        "version": "1.0.0",
        "search_metadata": search_meta,
        "eligible_candidates": eligible_map,
        "pareto_frontier": frontier_ids,
        "diagnostics": diagnostics_map,
        "min_effort_to_da_baseline": baseline,
    }

    encoded_json = encode_ranking_result(result_payload)
    roundtrip_result = json.loads(encoded_json)
    return {
        "decoded_query": decoded,
        "assessed_candidates": assessed_candidates,
        "result_payload": result_payload,
        "encoded_json": encoded_json,
        "roundtrip_result": roundtrip_result,
    }


def encode_ranking_result(result: dict[str, Any]) -> str:
    """Encode PathRankingResult into lossless JSON wire payload."""

    def sanitize(obj: Any) -> Any:
        if isinstance(obj, Fraction):
            return format_rational_string(obj)
        if isinstance(obj, tuple):
            return [sanitize(x) for x in obj]
        if isinstance(obj, list):
            return [sanitize(x) for x in obj]
        if isinstance(obj, dict):
            return {k: sanitize(v) for k, v in obj.items()}
        return obj

    sanitized = sanitize(result)
    return json.dumps(sanitized, indent=2, ensure_ascii=False)


def _to_fraction(val: Any) -> Fraction:
    """Coerce number or string representation to exact Fraction."""
    if isinstance(val, Fraction):
        return val
    if isinstance(val, int):
        return Fraction(val, 1)
    if isinstance(val, float):
        return Fraction(str(val))
    return Fraction(str(val))


def compute_interval_iou(b1: tuple[Any, Any], b2: tuple[Any, Any]) -> Fraction:
    """Compute exact rational Intersection over Union (IoU) between two intervals [l, u]."""
    l1, u1 = _to_fraction(b1[0]), _to_fraction(b1[1])
    l2, u2 = _to_fraction(b2[0]), _to_fraction(b2[1])
    if l1 == u1 == l2 == u2:
        return Fraction(1, 1)  # Identical point bounds have full agreement (avoid 0/0)
    if l1 == u1 and l2 == u2 and l1 != l2:
        return Fraction(0, 1)  # Distinct point bounds have zero intersection
    inter = max(Fraction(0, 1), min(u1, u2) - max(l1, l2))
    union = max(u1, u2) - min(l1, l2)
    return inter / union if union > 0 else Fraction(0, 1)


def check_epistemic_uncertainty(b: tuple[Any, Any], threshold: Any = Fraction(1, 2)) -> bool:
    """Flag intervals whose width strictly exceeds the epistemic uncertainty threshold."""
    lower = _to_fraction(b[0])
    upper = _to_fraction(b[1])
    thresh = _to_fraction(threshold)
    return (upper - lower) > thresh


def compute_kappa_with_fallback(ratings1: list[str], ratings2: list[str]) -> dict[str, Any]:
    """Compute Cohen's Kappa for categorical ratings with zero-variance and empty set fallbacks."""
    if len(ratings1) != len(ratings2):
        raise ValueError(
            f"Mismatched rating lengths for Kappa calculation: {len(ratings1)} != {len(ratings2)}"
        )
    n = len(ratings1)
    if n == 0:
        return {
            "kappa": None,
            "status": "empty_ratings",
            "observed_agreement": None,
            "confusion_matrix": {},
            "small_sample_size_warning": True,
        }

    agree_count = sum(1 for r1, r2 in zip(ratings1, ratings2, strict=True) if r1 == r2)
    po = agree_count / n
    categories = sorted(set(ratings1) | set(ratings2))
    matrix: dict[str, dict[str, int]] = {c1: {c2: 0 for c2 in categories} for c1 in categories}
    for r1, r2 in zip(ratings1, ratings2, strict=True):
        matrix[r1][r2] += 1

    small_sample = n < 5

    p_e = sum(
        (sum(matrix[c][c2] for c2 in categories) / n)
        * (sum(matrix[c1][c] for c1 in categories) / n)
        for c in categories
    )
    if p_e == 1.0:
        return {
            "kappa": None,
            "status": "degenerate_zero_variance",
            "observed_agreement": po,
            "confusion_matrix": matrix,
            "small_sample_size_warning": small_sample,
        }

    kappa = (po - p_e) / (1.0 - p_e)
    return {
        "kappa": kappa,
        "status": "valid",
        "observed_agreement": po,
        "confusion_matrix": matrix,
        "small_sample_size_warning": small_sample,
    }


CANONICAL_TECHNIQUE_ALIASES: dict[str, str] = {
    "pwd_reset": "genericall_reset_password",
    "net_auth": "kerberos_network_logon",
    "winrm_exec": "psremote_execute",
    "memberof": "memberof_group_nesting",
}

PINNED_WORK_UNIT_CATALOG: dict[str, dict[str, str]] = {
    (
        "pwd_reset:S-1-5-21-3623811015-3361044348-30300820-1002:"
        "S-1-5-21-3623811015-3361044348-30300820-1003:corp_net:ad_boundary:v1"
    ): {
        "technique_name": "genericall_reset_password",
        "actor_scope": "S-1-5-21-3623811015-3361044348-30300820-1002",
        "target_scope": "S-1-5-21-3623811015-3361044348-30300820-1003",
        "context_scope": "corp_net",
        "boundary_scope": "ad_boundary",
        "ledger_version": "v1",
    },
    (
        "net_auth:S-1-5-21-3623811015-3361044348-30300820-1003:"
        "S-1-5-21-3623811015-3361044348-30300820-1000:corp_net:ad_boundary:v1"
    ): {
        "technique_name": "kerberos_network_logon",
        "actor_scope": "S-1-5-21-3623811015-3361044348-30300820-1003",
        "target_scope": "S-1-5-21-3623811015-3361044348-30300820-1000",
        "context_scope": "corp_net",
        "boundary_scope": "ad_boundary",
        "ledger_version": "v1",
    },
    (
        "winrm_exec:S-1-5-21-3623811015-3361044348-30300820-1003:"
        "S-1-5-21-3623811015-3361044348-30300820-1000:corp_net:ad_boundary:v1"
    ): {
        "technique_name": "psremote_execute",
        "actor_scope": "S-1-5-21-3623811015-3361044348-30300820-1003",
        "target_scope": "S-1-5-21-3623811015-3361044348-30300820-1000",
        "context_scope": "corp_net",
        "boundary_scope": "ad_boundary",
        "ledger_version": "v1",
    },
    "unit_pwd_reset": {
        "technique_name": "genericall_reset_password",
        "actor_scope": "user_a",
        "target_scope": "user_b",
    },
    "unit_memberof": {
        "technique_name": "memberof_group_nesting",
        "actor_scope": "user_b",
        "target_scope": "group_server_ops",
    },
    "unit_1": {
        "technique_name": "tech_a",
        "actor_scope": "user_a",
        "target_scope": "user_b",
    },
}


def parse_canonical_work_unit_id(work_unit_id: str) -> dict[str, Any] | None:
    """Parse a canonical work unit ID: technique:actor:target:context:boundary:ledger_version.

    Returns dict with keys:
    - technique, context, boundary, ledger_version
    - actor, target (if resolvable)
    - middle (if multi-token middle)
    - ambiguous_middle: True (if multi-token middle has 0 or >1 canonical node-ID splits)
    or None if the ID does not follow canonical colon-delimited structure.
    """
    if not isinstance(work_unit_id, str):
        return None
    parts = work_unit_id.split(":")
    if len(parts) == 6:
        tech, actor, target, context, boundary, version = parts
        res: dict[str, Any] = {
            "technique": tech,
            "context": context,
            "boundary": boundary,
            "ledger_version": version,
        }
        if is_canonical_node_id(actor) and is_canonical_node_id(target):
            res["actor"] = actor
            res["target"] = target
        else:
            res["middle"] = f"{actor}:{target}"
            res["ambiguous_middle"] = True
        return res
    if len(parts) > 6:
        tech = parts[0]
        context = parts[-3]
        boundary = parts[-2]
        version = parts[-1]
        middle_parts = parts[1:-3]
        middle = ":".join(middle_parts)
        candidate_splits: list[tuple[str, str]] = []
        for i in range(1, len(middle_parts)):
            cand_actor = ":".join(middle_parts[:i])
            cand_target = ":".join(middle_parts[i:])
            if is_canonical_node_id(cand_actor) and is_canonical_node_id(cand_target):
                candidate_splits.append((cand_actor, cand_target))

        res = {
            "technique": tech,
            "middle": middle,
            "context": context,
            "boundary": boundary,
            "ledger_version": version,
        }
        if len(candidate_splits) == 1:
            res["actor"] = candidate_splits[0][0]
            res["target"] = candidate_splits[0][1]
        else:
            res["ambiguous_middle"] = True
        return res
    return None


def normalize_technique_name(tech: str) -> str:
    """Normalize a technique identifier or alias to its canonical long name."""
    t = str(tech).strip()
    return CANONICAL_TECHNIQUE_ALIASES.get(t, t)


def validate_authoritative_work_unit_definition(
    work_unit_id: str,
    raw_def: Any,
    source: str = "work_unit_registry",
) -> dict[str, Any]:
    """Validate that an authoritative work unit definition has non-blank, non-pending schema."""
    if not isinstance(raw_def, dict):
        raise ValueError(
            f"Invalid work unit definition for '{work_unit_id}' in {source}: "
            f"expected dict, got {type(raw_def).__name__}"
        )

    # 1. Technique definition check
    raw_tech = raw_def.get("technique_name") or raw_def.get("technique")
    if raw_tech is None:
        raise ValueError(
            f"Incomplete work unit definition for '{work_unit_id}' in {source}: "
            "missing mandatory technique definition"
        )
    tech_str = str(raw_tech).strip()
    if not tech_str:
        raise ValueError(
            f"Blank technique in work unit definition for '{work_unit_id}' in {source}"
        )
    if "PENDING" in tech_str.upper():
        raise ValueError(
            f"Pending technique in work unit definition for '{work_unit_id}' in {source}"
        )

    # 2. Actor and Target checks (or canonical middle)
    has_middle = (
        "middle" in raw_def
        and isinstance(raw_def["middle"], str)
        and bool(raw_def["middle"].strip())
    )

    if has_middle:
        middle_str = str(raw_def["middle"]).strip()
        if "PENDING" in middle_str.upper() or ":" not in middle_str:
            raise ValueError(
                f"Invalid canonical middle in work unit definition for '{work_unit_id}' in {source}"
            )
        raw_actor = (
            raw_def.get("actor_scope")
            or raw_def.get("actor")
            or raw_def.get("actor_id")
            or raw_def.get("source_node_id")
        )
        raw_target = (
            raw_def.get("target_scope")
            or raw_def.get("target")
            or raw_def.get("target_id")
            or raw_def.get("target_node_id")
        )
        if raw_actor is None or raw_target is None:
            middle_parts = middle_str.split(":")
            cand_splits: list[tuple[str, str]] = []
            for i in range(1, len(middle_parts)):
                c_act = ":".join(middle_parts[:i])
                c_tgt = ":".join(middle_parts[i:])
                if is_canonical_node_id(c_act) and is_canonical_node_id(c_tgt):
                    cand_splits.append((c_act, c_tgt))
            if len(cand_splits) == 1:
                raw_def.setdefault("actor_scope", cand_splits[0][0])
                raw_def.setdefault("target_scope", cand_splits[0][1])
            else:
                raise ValueError(
                    f"Work unit definition for '{work_unit_id}' in {source} "
                    f"has ambiguous middle '{middle_str}' "
                    "and lacks discrete canonical actor and target definitions"
                )
        if raw_actor is not None:
            actor_str = str(raw_actor).strip()
            if not actor_str or "PENDING" in actor_str.upper():
                raise ValueError(
                    f"Blank or pending actor in work unit definition for '{work_unit_id}' "
                    f"in {source}"
                )
        if raw_target is not None:
            target_str = str(raw_target).strip()
            if not target_str or "PENDING" in target_str.upper():
                raise ValueError(
                    f"Blank or pending target in work unit definition for '{work_unit_id}' "
                    f"in {source}"
                )
    else:
        raw_actor = (
            raw_def.get("actor_scope")
            or raw_def.get("actor")
            or raw_def.get("actor_id")
            or raw_def.get("source_node_id")
        )
        if raw_actor is None:
            raise ValueError(
                f"Incomplete work unit definition for '{work_unit_id}' in {source}: "
                "missing mandatory actor definition"
            )
        actor_str = str(raw_actor).strip()
        if not actor_str:
            raise ValueError(
                f"Blank actor in work unit definition for '{work_unit_id}' in {source}"
            )
        if "PENDING" in actor_str.upper():
            raise ValueError(
                f"Pending actor in work unit definition for '{work_unit_id}' in {source}"
            )

        raw_target = (
            raw_def.get("target_scope")
            or raw_def.get("target")
            or raw_def.get("target_id")
            or raw_def.get("target_node_id")
        )
        if raw_target is None:
            raise ValueError(
                f"Incomplete work unit definition for '{work_unit_id}' in {source}: "
                "missing mandatory target definition"
            )
        target_str = str(raw_target).strip()
        if not target_str:
            raise ValueError(
                f"Blank target in work unit definition for '{work_unit_id}' in {source}"
            )
        if "PENDING" in target_str.upper():
            raise ValueError(
                f"Pending target in work unit definition for '{work_unit_id}' in {source}"
            )

    return raw_def


def assert_registry_definition_consistent_with_canonical_id(
    work_unit_id: str,
    reg_def: dict[str, Any],
    can_def: dict[str, Any],
) -> None:
    """Ensure registry definition does not conflict with immutable canonical ID components."""
    # 1. Technique check
    reg_tech = reg_def.get("technique_name") or reg_def.get("technique")
    can_tech = can_def.get("technique")
    if reg_tech is not None and can_tech is not None:
        if normalize_technique_name(str(reg_tech)) != normalize_technique_name(str(can_tech)):
            raise ValueError(
                f"Registry definition technique '{reg_tech}' conflicts with canonical ID "
                f"technique '{can_tech}' in work_unit_id '{work_unit_id}'"
            )

    # 2. Actor, Target, and Middle checks
    can_has_middle = "middle" in can_def
    expected_can_middle = (
        str(can_def["middle"]).strip()
        if can_has_middle
        else f"{str(can_def.get('actor', '')).strip()}:{str(can_def.get('target', '')).strip()}"
    )

    reg_middle = reg_def.get("middle")
    if reg_middle is not None:
        reg_middle_str = str(reg_middle).strip()
        if reg_middle_str != expected_can_middle:
            raise ValueError(
                f"Registry definition middle '{reg_middle_str}' conflicts with canonical ID "
                f"middle '{expected_can_middle}' in work_unit_id '{work_unit_id}'"
            )

    reg_actor = (
        reg_def.get("actor_scope")
        or reg_def.get("actor")
        or reg_def.get("actor_id")
        or reg_def.get("source_node_id")
    )
    reg_target = (
        reg_def.get("target_scope")
        or reg_def.get("target")
        or reg_def.get("target_id")
        or reg_def.get("target_node_id")
    )

    if reg_actor is not None:
        reg_actor_str = str(reg_actor).strip()
        if not is_canonical_node_id(reg_actor_str):
            raise ValueError(
                f"Registry definition actor '{reg_actor_str}' is not a valid canonical node ID "
                f"in work_unit_id '{work_unit_id}'"
            )
    if reg_target is not None:
        reg_target_str = str(reg_target).strip()
        if not is_canonical_node_id(reg_target_str):
            raise ValueError(
                f"Registry definition target '{reg_target_str}' is not a valid canonical node ID "
                f"in work_unit_id '{work_unit_id}'"
            )

    can_actor = can_def.get("actor")
    if reg_actor is not None and can_actor is not None:
        if str(reg_actor).strip() != str(can_actor).strip():
            raise ValueError(
                f"Registry definition actor '{reg_actor}' conflicts with canonical ID "
                f"actor '{can_actor}' in work_unit_id '{work_unit_id}'"
            )

    can_target = can_def.get("target")
    if reg_target is not None and can_target is not None:
        if str(reg_target).strip() != str(can_target).strip():
            raise ValueError(
                f"Registry definition target '{reg_target}' conflicts with canonical ID "
                f"target '{can_target}' in work_unit_id '{work_unit_id}'"
            )

    if can_has_middle:
        if reg_actor is not None and reg_target is not None:
            constructed_middle = f"{str(reg_actor).strip()}:{str(reg_target).strip()}"
            if constructed_middle != expected_can_middle:
                raise ValueError(
                    f"Registry definition actor/target '{constructed_middle}' conflicts with "
                    f"canonical ID middle '{expected_can_middle}' in work_unit_id '{work_unit_id}'"
                )
        elif reg_actor is not None:
            if not expected_can_middle.startswith(f"{str(reg_actor).strip()}:"):
                raise ValueError(
                    f"Registry definition actor '{reg_actor}' conflicts with canonical ID "
                    f"middle '{expected_can_middle}' in work_unit_id '{work_unit_id}'"
                )
        elif reg_target is not None:
            if not expected_can_middle.endswith(f":{str(reg_target).strip()}"):
                raise ValueError(
                    f"Registry definition target '{reg_target}' conflicts with canonical ID "
                    f"middle '{expected_can_middle}' in work_unit_id '{work_unit_id}'"
                )

    # 3. Context, boundary, and ledger_version checks
    for opt_field, can_key in (
        ("context_scope", "context"),
        ("boundary_scope", "boundary"),
        ("ledger_version", "ledger_version"),
    ):
        reg_val = reg_def.get(opt_field) or reg_def.get(can_key)
        can_val = can_def.get(can_key)
        if reg_val is not None and can_val is not None:
            if str(reg_val).strip() != str(can_val).strip():
                raise ValueError(
                    f"Registry definition {opt_field} '{reg_val}' conflicts with canonical ID "
                    f"{can_key} '{can_val}' in work_unit_id '{work_unit_id}'"
                )


def reconcile_expert_ratings(
    r1: dict[str, Any],
    r2: dict[str, Any],
    work_unit_registry: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Reconcile two expert rating records according to the governance protocol."""
    rec_type = r1.get("record_type")
    r2_type = r2.get("record_type")
    if rec_type != r2_type:
        raise ValueError(f"Cannot reconcile different record types: '{rec_type}' != '{r2_type}'")
    if rec_type not in ("impact_rating", "conditional_likelihood", "work_unit_effort"):
        raise ValueError(f"Unknown or unsupported record_type: '{rec_type}'")

    # 1. Rater validation: evaluators must be present, distinct, and non-empty
    e1 = r1.get("evaluator")
    e2 = r2.get("evaluator")
    e1_clean = str(e1 or "").strip()
    e2_clean = str(e2 or "").strip()
    if not e1_clean or not e2_clean:
        raise ValueError("Missing or blank evaluator in rating record")
    if "PENDING" in e1_clean.upper() or "PENDING" in e2_clean.upper():
        raise ValueError(f"Cannot reconcile records with pending evaluators: '{e1}', '{e2}'")
    if e1_clean == e2_clean:
        raise ValueError(f"Evaluators must be distinct independent raters, got same: '{e1_clean}'")

    # 2. Type-specific binding validation and reconciliation
    if rec_type == "impact_rating":
        target1 = r1.get("target_asset_id")
        target2 = r2.get("target_asset_id")
        if not target1 or not target2 or target1 != target2:
            raise ValueError(
                f"Mismatched target_asset_id for impact reconciliation: '{target1}' != '{target2}'"
            )

        event1 = r1.get("success_event")
        event2 = r2.get("success_event")
        if not event1 or not event2 or event1 != event2:
            raise ValueError(
                f"Mismatched success_event for impact reconciliation: '{event1}' != '{event2}'"
            )

        c1 = r1.get("consequence_rating")
        c2 = r2.get("consequence_rating")
        valid_impacts = set(IMPACT_ORDINAL.keys())
        if c1 not in valid_impacts or c2 not in valid_impacts:
            raise ValueError(
                f"Invalid or pending consequence_rating: '{c1}', '{c2}'. "
                f"Must be one of {valid_impacts}"
            )

        is_consensus = c1 == c2
        return {
            "record_type": "impact_rating",
            "binding": {
                "target_asset_id": target1,
                "target_asset_label": r1.get("target_asset_label") or r2.get("target_asset_label"),
                "success_event": event1,
            },
            "status": "consensus" if is_consensus else "disagreement",
            "consequence_rating": c1 if is_consensus else None,
            "proposal_verdict": "proposed_consensus"
            if is_consensus
            else "requires_reconciliation_panel",
            "raters": [e1_clean, e2_clean],
            "raw_ratings": [c1, c2],
            "rationales": [r1.get("business_rationale"), r2.get("business_rationale")],
            "affected_business_services": list(
                dict.fromkeys(
                    (r1.get("affected_business_services") or [])
                    + (r2.get("affected_business_services") or [])
                )
            ),
        }

    if rec_type == "conditional_likelihood":
        scen1 = r1.get("scenario_id")
        scen2 = r2.get("scenario_id")
        if not scen1 or not scen2 or scen1 != scen2:
            raise ValueError(f"Mismatched scenario_id: '{scen1}' != '{scen2}'")

        pref1 = r1.get("ordered_work_prefix")
        pref2 = r2.get("ordered_work_prefix")
        if not pref1 or not pref2 or pref1 != pref2:
            raise ValueError(f"Mismatched ordered_work_prefix: '{pref1}' != '{pref2}'")

        horiz1 = str(r1.get("operational_horizon") or "").strip()
        horiz2 = str(r2.get("operational_horizon") or "").strip()
        if not horiz1 or not horiz2:
            raise ValueError("Missing operational_horizon in conditional_likelihood record")
        if "PENDING" in horiz1.upper() or "PENDING" in horiz2.upper():
            raise ValueError(
                f"Cannot reconcile pending operational_horizon: '{horiz1}', '{horiz2}'"
            )
        if horiz1 != horiz2:
            raise ValueError(f"Mismatched operational_horizon: '{horiz1}' != '{horiz2}'")

        pop1 = str(r1.get("target_population") or "").strip()
        pop2 = str(r2.get("target_population") or "").strip()
        if not pop1 or not pop2:
            raise ValueError("Missing target_population in conditional_likelihood record")
        if "PENDING" in pop1.upper() or "PENDING" in pop2.upper():
            raise ValueError(f"Cannot reconcile pending target_population: '{pop1}', '{pop2}'")
        if pop1 != pop2:
            raise ValueError(f"Mismatched target_population: '{pop1}' != '{pop2}'")

        b1_raw = r1.get("conditional_bounds", {})
        b2_raw = r2.get("conditional_bounds", {})
        if not b1_raw or not b2_raw:
            raise ValueError("Missing conditional_bounds in likelihood rating record")

        l1_str, u1_str = str(b1_raw.get("lower", "")), str(b1_raw.get("upper", ""))
        l2_str, u2_str = str(b2_raw.get("lower", "")), str(b2_raw.get("upper", ""))
        if "PENDING" in (l1_str + u1_str + l2_str + u2_str).upper():
            raise ValueError("Cannot reconcile pending conditional bounds")

        f_l1, f_u1 = Fraction(l1_str), Fraction(u1_str)
        f_l2, f_u2 = Fraction(l2_str), Fraction(u2_str)

        if not (0 <= f_l1 <= f_u1 <= 1) or not (0 <= f_l2 <= f_u2 <= 1):
            raise ValueError(
                f"Conditional bounds out of probability range [0, 1] or inverted: "
                f"[{f_l1}, {f_u1}], [{f_l2}, {f_u2}]"
            )

        iou = compute_interval_iou((f_l1, f_u1), (f_l2, f_u2))
        rec_lower = min(f_l1, f_l2)
        rec_upper = max(f_u1, f_u2)
        high_unc = check_epistemic_uncertainty((rec_lower, rec_upper), threshold=Fraction(1, 2))
        has_agreement = iou >= Fraction(1, 2)

        return {
            "record_type": "conditional_likelihood",
            "binding": {
                "scenario_id": scen1,
                "ordered_work_prefix": pref1,
                "operational_horizon": horiz1,
                "target_population": pop1,
            },
            "status": "reconciled" if has_agreement else "disagreement",
            "inter_rater_iou": float(iou),
            "reconciled_bounds": (
                format_rational_string(rec_lower),
                format_rational_string(rec_upper),
            ),
            "high_epistemic_uncertainty": high_unc,
            "proposal_verdict": "proposed_consensus"
            if has_agreement
            else "requires_reconciliation_panel",
            "raters": [e1_clean, e2_clean],
            "raw_bounds": [
                (format_rational_string(f_l1), format_rational_string(f_u1)),
                (format_rational_string(f_l2), format_rational_string(f_u2)),
            ],
            "rationales": [r1.get("uncertainty_rationale"), r2.get("uncertainty_rationale")],
        }

    if rec_type == "work_unit_effort":
        w1 = r1.get("work_unit_id")
        w2 = r2.get("work_unit_id")
        w1_s = str(w1 or "").strip()
        w2_s = str(w2 or "").strip()
        if not w1_s or not w2_s:
            raise ValueError("Missing or blank work_unit_id in work_unit_effort record")
        if "PENDING" in w1_s.upper() or "PENDING" in w2_s.upper():
            raise ValueError(f"Cannot reconcile pending work_unit_id: '{w1_s}', '{w2_s}'")
        if w1_s != w2_s:
            raise ValueError(f"Mismatched work_unit_id: '{w1_s}' != '{w2_s}'")

        for meta_key in ("technique_name", "actor_scope", "target_scope"):
            v1 = r1.get(meta_key)
            v2 = r2.get(meta_key)
            if v1 is None or v2 is None:
                raise ValueError(
                    f"Missing mandatory effort metadata '{meta_key}' in work_unit_effort record"
                )
            v1_s = str(v1).strip()
            v2_s = str(v2).strip()
            if not v1_s or not v2_s:
                raise ValueError(f"Blank effort metadata '{meta_key}' in work_unit_effort record")
            if "PENDING" in v1_s.upper() or "PENDING" in v2_s.upper():
                raise ValueError(
                    f"Cannot reconcile pending effort metadata '{meta_key}': '{v1_s}', '{v2_s}'"
                )
            if v1_s != v2_s:
                raise ValueError(f"Mismatched {meta_key} in work_unit_effort: '{v1_s}' != '{v2_s}'")

        tech_val = str(r1["technique_name"]).strip()
        actor_val = str(r1["actor_scope"]).strip()
        target_val = str(r1["target_scope"]).strip()

        # Resolve authoritative work unit definition to prevent blind mutual errors
        expected_def: dict[str, Any]
        parsed_canonical = parse_canonical_work_unit_id(w1_s)

        if parsed_canonical is not None:
            # Enforce canonical node ID validation on rater metadata for canonical work units
            if not is_canonical_node_id(actor_val):
                raise ValueError(
                    f"Metadata actor_scope '{actor_val}' is not a valid canonical node ID"
                )
            if not is_canonical_node_id(target_val):
                raise ValueError(
                    f"Metadata target_scope '{target_val}' is not a valid canonical node ID"
                )

            can_def = validate_authoritative_work_unit_definition(
                w1_s, parsed_canonical, source="canonical ID"
            )
            if work_unit_registry is not None and w1_s in work_unit_registry:
                reg_def = validate_authoritative_work_unit_definition(
                    w1_s, work_unit_registry[w1_s], source="work_unit_registry"
                )
                assert_registry_definition_consistent_with_canonical_id(w1_s, reg_def, can_def)
                expected_def = {**reg_def, **can_def}
                if "actor" in can_def:
                    expected_def["actor_scope"] = can_def["actor"]
                    expected_def["actor"] = can_def["actor"]
                if "target" in can_def:
                    expected_def["target_scope"] = can_def["target"]
                    expected_def["target"] = can_def["target"]
                if "middle" in can_def:
                    expected_def["middle"] = can_def["middle"]
                if "context" in can_def:
                    expected_def["context_scope"] = can_def["context"]
                    expected_def["context"] = can_def["context"]
                if "boundary" in can_def:
                    expected_def["boundary_scope"] = can_def["boundary"]
                    expected_def["boundary"] = can_def["boundary"]
                if "ledger_version" in can_def:
                    expected_def["ledger_version"] = can_def["ledger_version"]
            elif w1_s in PINNED_WORK_UNIT_CATALOG:
                cat_def = validate_authoritative_work_unit_definition(
                    w1_s, PINNED_WORK_UNIT_CATALOG[w1_s], source="PINNED_WORK_UNIT_CATALOG"
                )
                assert_registry_definition_consistent_with_canonical_id(w1_s, cat_def, can_def)
                expected_def = {**cat_def, **can_def}
                if "actor" in can_def:
                    expected_def["actor_scope"] = can_def["actor"]
                    expected_def["actor"] = can_def["actor"]
                if "target" in can_def:
                    expected_def["target_scope"] = can_def["target"]
                    expected_def["target"] = can_def["target"]
                if "middle" in can_def:
                    expected_def["middle"] = can_def["middle"]
                if "context" in can_def:
                    expected_def["context_scope"] = can_def["context"]
                    expected_def["context"] = can_def["context"]
                if "boundary" in can_def:
                    expected_def["boundary_scope"] = can_def["boundary"]
                    expected_def["boundary"] = can_def["boundary"]
                if "ledger_version" in can_def:
                    expected_def["ledger_version"] = can_def["ledger_version"]
            else:
                expected_def = dict(can_def)
                if "actor" in can_def:
                    expected_def["actor_scope"] = can_def["actor"]
                if "target" in can_def:
                    expected_def["target_scope"] = can_def["target"]
                if "context" in can_def:
                    expected_def["context_scope"] = can_def["context"]
                if "boundary" in can_def:
                    expected_def["boundary_scope"] = can_def["boundary"]
                if "ledger_version" in can_def:
                    expected_def["ledger_version"] = can_def["ledger_version"]

            if parsed_canonical.get("ambiguous_middle") and (
                "actor_scope" not in expected_def or "target_scope" not in expected_def
            ):
                raise ValueError(
                    f"Canonical work_unit_id '{w1_s}' has ambiguous actor/target delimiter "
                    "boundaries and requires an authoritative structured registry definition "
                    "with discrete actor and target"
                )
        else:
            # Opaque work unit ID: requires authoritative registry or pinned catalog
            if work_unit_registry is not None:
                if w1_s not in work_unit_registry:
                    raise ValueError(
                        f"Unknown work_unit_id '{w1_s}' not found in provided work_unit_registry"
                    )
                expected_def = validate_authoritative_work_unit_definition(
                    w1_s, work_unit_registry[w1_s], source="work_unit_registry"
                )
            elif w1_s in PINNED_WORK_UNIT_CATALOG:
                expected_def = validate_authoritative_work_unit_definition(
                    w1_s, PINNED_WORK_UNIT_CATALOG[w1_s], source="PINNED_WORK_UNIT_CATALOG"
                )
            else:
                raise ValueError(
                    f"Cannot validate opaque work_unit_id '{w1_s}' "
                    "without authoritative work_unit_registry: "
                    "definition must be provided via work_unit_registry or conform to canonical ID"
                )

        # 1. Validate actor_scope
        exp_actor = (
            expected_def.get("actor_scope")
            or expected_def.get("actor")
            or expected_def.get("actor_id")
            or expected_def.get("source_node_id")
        )
        if exp_actor is not None:
            if actor_val != str(exp_actor).strip():
                raise ValueError(
                    f"Metadata actor_scope '{actor_val}' is inconsistent with work unit "
                    f"definition for '{w1_s}': expected actor '{exp_actor}'"
                )
        else:
            raise ValueError(
                f"Work unit definition for '{w1_s}' lacks expected actor specification"
            )

        # 2. Validate target_scope
        exp_target = (
            expected_def.get("target_scope")
            or expected_def.get("target")
            or expected_def.get("target_id")
            or expected_def.get("target_node_id")
        )
        if exp_target is not None:
            if target_val != str(exp_target).strip():
                raise ValueError(
                    f"Metadata target_scope '{target_val}' is inconsistent with work unit "
                    f"definition for '{w1_s}': expected target '{exp_target}'"
                )
        else:
            raise ValueError(
                f"Work unit definition for '{w1_s}' lacks expected target specification"
            )

        # Scoped middle check when target contains colons
        if "middle" in expected_def:
            expected_middle = f"{actor_val}:{target_val}"
            if str(expected_def["middle"]).strip() != expected_middle:
                raise ValueError(
                    f"Metadata actor/target '{expected_middle}' is inconsistent with canonical "
                    f"middle '{expected_def['middle']}' in work_unit_id '{w1_s}'"
                )

        # 3. Validate technique_name
        exp_tech = expected_def.get("technique_name") or expected_def.get("technique")
        if exp_tech is None:
            raise ValueError(
                f"Work unit definition for '{w1_s}' lacks expected technique specification"
            )
        matches_tech = normalize_technique_name(tech_val) == normalize_technique_name(str(exp_tech))
        if not matches_tech:
            raise ValueError(
                f"Metadata technique_name '{tech_val}' is inconsistent with work unit "
                f"definition for '{w1_s}': expected technique '{exp_tech}'"
            )

        # 4. Optional context_scope, boundary_scope, ledger_version validation
        for opt_field, exp_key in (
            ("context_scope", "context"),
            ("boundary_scope", "boundary"),
            ("ledger_version", "ledger_version"),
        ):
            c1 = r1.get(opt_field)
            c2 = r2.get(opt_field)
            if c1 is not None or c2 is not None:
                if c1 is None or c2 is None or str(c1).strip() != str(c2).strip():
                    raise ValueError(
                        f"Mismatched {opt_field} in work_unit_effort: '{c1}' != '{c2}'"
                    )
                exp_c = expected_def.get(opt_field) or expected_def.get(exp_key)
                if exp_c is not None and str(c1).strip() != exp_c:
                    raise ValueError(
                        f"Metadata {opt_field} '{c1}' is inconsistent with work unit definition "
                        f"for '{w1_s}': expected '{exp_c}'"
                    )

        def extract_effort(r: dict[str, Any]) -> int:
            rub = r.get("rubric_evaluation")
            if not isinstance(rub, dict):
                raise ValueError(
                    f"work_unit_effort record missing mandatory rubric_evaluation object: {r}"
                )
            formula = rub.get("formula")
            if formula != "base":
                raise ValueError(
                    f"Unsupported or pending rubric formula {formula!r}: only 'base' is supported"
                )
            t1 = rub.get("t1_complexity")
            t2 = rub.get("t2_friction")
            cost = rub.get("computed_cost")
            if t1 is None or t2 is None or cost is None:
                raise ValueError(f"Incomplete rubric_evaluation fields: {rub}")
            if (
                isinstance(t1, (float, bool))
                or isinstance(t2, (float, bool))
                or isinstance(cost, (float, bool))
            ):
                raise TypeError(
                    f"Rubric evaluation values must be integers, got types: "
                    f"t1={type(t1).__name__}, t2={type(t2).__name__}, cost={type(cost).__name__}"
                )
            t1_s, t2_s, cost_s = str(t1).strip(), str(t2).strip(), str(cost).strip()
            if "PENDING" in (t1_s + t2_s + cost_s).upper():
                raise ValueError(f"Cannot reconcile pending rubric values in record: {r}")
            try:
                t1_int, t2_int, cost_int = int(t1_s), int(t2_s), int(cost_s)
            except ValueError as err:
                msg = f"Rubric evaluation values must be integer strings: {err}"
                raise ValueError(msg) from err
            if t1_int not in {1, 2, 3} or t2_int not in {1, 2, 3}:
                raise ValueError(f"T1 and T2 must be in {{1, 2, 3}}, got T1={t1_int}, T2={t2_int}")
            if cost_int not in {0, 1, 2, 3, 4}:
                raise ValueError(
                    f"computed_cost must be in range {{0, 1, 2, 3, 4}}, got {cost_int}"
                )
            if cost_int != (t1_int + t2_int - 2):
                raise ValueError(
                    f"Formula consistency check failed: computed_cost {cost_int} "
                    f"!= {t1_int} + {t2_int} - 2"
                )
            return cost_int

        c1 = extract_effort(r1)
        c2 = extract_effort(r2)
        delta = abs(c1 - c2)
        resolved = max(c1, c2)  # Conservative resolution
        status = "reconciled" if delta <= 1 else "disagreement"
        return {
            "record_type": "work_unit_effort",
            "binding": {
                "work_unit_id": w1_s,
                "technique_name": tech_val,
                "actor_scope": actor_val,
                "target_scope": target_val,
            },
            "status": status,
            "cost_delta": delta,
            "resolved_cost": resolved,
            "proposal_verdict": "proposed_consensus"
            if delta <= 1
            else "requires_reconciliation_panel",
            "raters": [e1_clean, e2_clean],
            "raw_costs": [c1, c2],
        }

    raise ValueError(f"Unknown record type for reconciliation: '{rec_type}'")


SEAMLESS_CANONICAL_EDGE_LOCATORS: dict[str, str] = {
    "sha256:add3ecb3858d5426d003da9ecdba89274ea02d5c7d9e99e3e10ece6a5d077932": (
        "20210920185958_users.json#/users/2310/Aces/3"
    ),
    "sha256:e44b0f47456908b5209f670f2cf0889ae4695e9efd24c82bbda4da1ae043cb48": (
        "20210920185958_groups.json#/groups/40/Members/0"
    ),
    "sha256:57a246b4f71dff94a59b59addcf4e9aa6bd1bdb5d78817c1f733cc2ee197b2b9": (
        "20210920185958_computers.json#/computers/0/Aces/1"
    ),
    "sha256:e6e5d605be1a120753808f94017202855a53fdd9a6b9831ac3421d09fbba1538": (
        "20210920185958_users.json#/users/666/Aces/3"
    ),
    "sha256:f8b6da6bcbda61ddab0d8184c957e39809ed4e444d5dee181f2309cf0e682173": (
        "20210920185958_groups.json#/groups/246/Members/14"
    ),
    "sha256:3b30de3caac96bad3b7b1980c323661cba1cbeccd3c676d20ce2eb15f4a67689": (
        "20210920185958_users.json#/users/917/Aces/3"
    ),
    "sha256:250b099e406031037200bdf0d23277cc7d4fe7cc6f6ddad0d310a6be7f904d75": (
        "20210920185958_groups.json#/groups/40/Members/3"
    ),
    "sha256:b1ba7341c1075b25a3e1a096006b2ca01901d347fc4b9b9d7494402f480b7b1b": (
        "20210920185958_users.json#/users/917/Aces/11"
    ),
}


AUDITED_SEAMLESS_SNAPSHOT_ID = (
    "sha256:e0601d763eeea285d268ec9e468d321c50c9d7faba53c8e7442a2fcc4159c812"
)
SUPPORTED_SOURCE_VERSIONS = frozenset({"legacy_draft", "1.0.0-draft", "1.0.0"})
SUPPORTED_SOURCE_LAYOUTS = frozenset({"legacy_draft", "1.0.0-draft", "1.0.0", "canonical"})
SUPPORTED_TARGET_VERSIONS = frozenset({"1.0.0"})


def migrate_wire_payload_to_canonical(
    payload: dict[str, Any],
    *,
    target_version: str = "1.0.0",
    source_layout: str | None = None,
    edge_locators_table: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Migrate wire ranking query payload and candidate envelopes to canonical Specification 1.0.0.

    Transforms legacy wire representations and missing candidate envelope structures
    into canonical schema boundary format with fail-closed validation:
    1. Version and Layout Dispatch:
       - Strictly requires explicit, non-empty string source version in supported set
         (legacy_draft, 1.0.0-draft, 1.0.0); rejects missing or explicit null version.
       - Supports explicit source_layout profile ("legacy_draft", "1.0.0-draft", "1.0.0",
         "canonical"). When omitted, defaults to declared layout or source_version.
       - Enforces strict layout declaration precedence and conflict detection: payload-declared
         source_layout or legacy layout alias must be non-empty string and cannot conflict with
         caller source_layout parameter; caller override is rejected fail-closed if payload
         already declared a layout.
       - Distinguishes true canonical 1.0.0 (identity/strict validation, failing closed on missing
         mandatory fields without healing) from precanonical/legacy drafts (1.0.0-draft,
         legacy_draft).
       - Preserves machine-readable source_version, declared_layout, source_layout, and
         migration_audit in query_metadata.
       - Enforces target version 1.0.0.
    2. Edge Locators and Provenance Scoping:
       - Pins default SEAMLESS locator table to snapshot sha256:e0601d76...
       - Fails closed on unpinned snapshots unless explicit edge_locators_table provided.
       - Rejects conflicting locator mappings.
    3. work_units_ledger:
       - On legacy layouts: maps 'distinct_work' alias to canonical 'independent' overlap_state,
         and normalizes 'status' to 'rating_status'.
       - On canonical 1.0.0: strictly rejects legacy 'distinct_work' and missing 'rating_status'.
       - Strictly rejects cost mismatches (within-scale or out-of-scale) and contradictory
         cost aliases without altering declared numerical values; only populates when absent.
    4. bound_actions:
       - Rejects missing requires and adds fields fail-closed across all layouts
         (no empty-list healing).
       - Strictly validates non-empty string types for technique_name, technique, requires, adds.
       - On canonical 1.0.0: strictly requires technique_name and referenced_work_unit_ids.
       - On legacy layouts: normalizes technique to technique_name, populates
         referenced_work_unit_ids.
       - Ensures passive closures have empty list referenced_work_unit_ids: [].
    5. candidates.scope_binding:
       - On canonical 1.0.0: requires explicit scope_binding; missing fails closed.
       - If scope_binding is present, strictly validates that all 7 required fields are present,
         non-empty strings matching query_metadata; rejects empty/partial dicts, non-dict
         types (e.g. False, None), and conflicting scope values.
       - On legacy layouts: derives and injects 7-field template when scope_binding is absent.
    6. candidates.structural_routes:
       - On canonical 1.0.0: requires explicit provenance_locators; missing fails closed.
       - Rejects non-list provenance_locators (e.g. False) and conflicting locators.
       - On legacy layouts: resolves and attaches exact audited provenance_locators for each edge.
    """
    if not isinstance(payload, dict):
        raise TypeError(f"Payload must be a dictionary, got {type(payload).__name__}")

    if target_version not in SUPPORTED_TARGET_VERSIONS:
        raise ValueError(
            f"Unsupported target_version {target_version!r}; "
            f"supported: {sorted(SUPPORTED_TARGET_VERSIONS)}"
        )

    if source_layout is not None:
        if isinstance(source_layout, bool) or not isinstance(source_layout, str):
            tname = type(source_layout).__name__
            raise TypeError(f"source_layout argument must be non-empty string, got {tname}")
        if not source_layout.strip():
            raise ValueError("source_layout argument must be a non-empty string")
        if source_layout not in SUPPORTED_SOURCE_LAYOUTS:
            raise ValueError(
                f"Unsupported source_layout {source_layout!r}; "
                f"supported: {sorted(SUPPORTED_SOURCE_LAYOUTS)}"
            )

    migrated = copy.deepcopy(payload)

    is_wrapped = "query" in migrated and isinstance(migrated["query"], dict)
    query_part = migrated["query"] if is_wrapped else migrated

    if not isinstance(query_part, dict) or "query_metadata" not in query_part:
        raise ValueError("Payload missing mandatory 'query_metadata' component")

    meta = query_part["query_metadata"]
    if not isinstance(meta, dict):
        raise TypeError(f"query_metadata must be a dictionary, got {type(meta).__name__}")

    if "version" not in meta or meta["version"] is None:
        raise ValueError("Missing required query_metadata field: 'version'")
    source_version = meta["version"]
    if not isinstance(source_version, str) or isinstance(source_version, bool):
        raise TypeError(
            f"query_metadata version must be non-empty string, got {type(source_version).__name__}"
        )
    if not source_version.strip():
        raise ValueError("query_metadata version must be a non-empty string")
    if source_version not in SUPPORTED_SOURCE_VERSIONS:
        raise ValueError(
            f"Unsupported source version {source_version!r}; "
            f"supported: {sorted(SUPPORTED_SOURCE_VERSIONS)}"
        )

    # Validate payload declared layout markers fail-closed (no truthiness fallback)
    has_source_layout = "source_layout" in meta
    has_layout = "layout" in meta
    payload_source_layout = None
    payload_legacy_layout = None

    if has_source_layout:
        raw_sl = meta["source_layout"]
        if raw_sl is None or isinstance(raw_sl, bool) or not isinstance(raw_sl, str):
            tname = type(raw_sl).__name__
            raise TypeError(f"query_metadata source_layout must be non-empty string, got {tname}")
        if not raw_sl.strip():
            raise ValueError("query_metadata source_layout must be a non-empty string")
        if raw_sl not in SUPPORTED_SOURCE_LAYOUTS:
            raise ValueError(
                f"Unsupported source_layout {raw_sl!r} in query_metadata; "
                f"supported: {sorted(SUPPORTED_SOURCE_LAYOUTS)}"
            )
        payload_source_layout = "1.0.0" if raw_sl == "canonical" else raw_sl

    if has_layout:
        raw_l = meta["layout"]
        if raw_l is None or isinstance(raw_l, bool) or not isinstance(raw_l, str):
            raise TypeError(
                f"query_metadata layout must be non-empty string, got {type(raw_l).__name__}"
            )
        if not raw_l.strip():
            raise ValueError("query_metadata layout must be a non-empty string")
        if raw_l not in SUPPORTED_SOURCE_LAYOUTS:
            raise ValueError(
                f"Unsupported layout {raw_l!r} in query_metadata; "
                f"supported: {sorted(SUPPORTED_SOURCE_LAYOUTS)}"
            )
        payload_legacy_layout = "1.0.0" if raw_l == "canonical" else raw_l

    if has_source_layout and has_layout:
        if payload_source_layout != payload_legacy_layout:
            raise ValueError(
                f"Conflicting layout declarations in query_metadata: "
                f"source_layout={meta['source_layout']!r} != layout={meta['layout']!r}"
            )

    declared_layout = (
        meta["source_layout"] if has_source_layout else (meta["layout"] if has_layout else None)
    )
    normalized_payload_layout = (
        payload_source_layout if has_source_layout else payload_legacy_layout
    )

    if source_layout is not None:
        norm_arg_layout = "1.0.0" if source_layout == "canonical" else source_layout
        if normalized_payload_layout is not None and norm_arg_layout != normalized_payload_layout:
            raise ValueError(
                f"Conflicting source_layout argument {source_layout!r} with declared "
                f"payload layout {declared_layout!r}"
            )
        effective_source_layout = norm_arg_layout
    elif normalized_payload_layout is not None:
        effective_source_layout = normalized_payload_layout
    else:
        effective_source_layout = "1.0.0" if source_version == "canonical" else source_version

    if source_version in ("legacy_draft", "1.0.0-draft") and effective_source_layout == "1.0.0":
        raise ValueError(f"Conflicting version {source_version!r} with canonical source_layout")

    is_legacy = effective_source_layout in ("legacy_draft", "1.0.0-draft")

    meta["version"] = target_version
    meta["source_version"] = source_version
    meta["source_layout"] = effective_source_layout
    meta["migration_audit"] = {
        "source_version": source_version,
        "declared_layout": declared_layout,
        "source_layout": effective_source_layout,
        "target_version": target_version,
        "migrated": is_legacy,
    }

    # Build locators mapping scoped to snapshot
    snapshot_id = meta.get("snapshot_id")
    loc_map: dict[str, str] = {}
    if snapshot_id == AUDITED_SEAMLESS_SNAPSHOT_ID:
        loc_map.update(SEAMLESS_CANONICAL_EDGE_LOCATORS)

    if edge_locators_table is not None:
        if not isinstance(edge_locators_table, dict):
            raise TypeError(
                f"edge_locators_table must be dict, got {type(edge_locators_table).__name__}"
            )
        for eid, loc in edge_locators_table.items():
            if eid in loc_map and loc_map[eid] != loc:
                raise ValueError(
                    f"Conflicting edge locator for {eid!r}: {loc_map[eid]!r} != {loc!r}"
                )
            loc_map[eid] = loc

    facts_ledger = query_part.get("facts_ledger")
    if facts_ledger is not None:
        if not isinstance(facts_ledger, dict):
            raise TypeError(f"facts_ledger must be dict, got {type(facts_ledger).__name__}")
        observed_facts = facts_ledger.get("observed_facts", [])
        if not isinstance(observed_facts, list):
            raise TypeError(f"observed_facts must be list, got {type(observed_facts).__name__}")
        for obs in observed_facts:
            if not isinstance(obs, dict):
                continue
            ref = obs.get("provenance_reference") or obs.get("provenance_locator")
            eid = obs.get("edge_id")
            if eid and ref:
                if eid in loc_map and loc_map[eid] != ref:
                    raise ValueError(
                        f"Conflicting observed edge locator for {eid!r}: "
                        f"{loc_map[eid]!r} != {ref!r}"
                    )
                loc_map[eid] = ref

    # 1. Migrate work_units_ledger
    ledger = query_part.get("work_units_ledger", {})
    if isinstance(ledger, dict):
        for uid, rec in ledger.items():
            if not isinstance(rec, dict):
                continue
            if rec.get("overlap_state") == "distinct_work":
                if is_legacy:
                    rec["overlap_state"] = "independent"
                else:
                    raise ValueError(
                        f"Canonical 1.0.0 work unit {uid!r} has unsupported "
                        "legacy overlap_state 'distinct_work'"
                    )
            elif not is_legacy and rec.get("overlap_state") not in (
                "independent",
                "unresolved_overlap",
            ):
                raise ValueError(
                    f"Canonical 1.0.0 work unit {uid!r} has invalid "
                    f"overlap_state {rec.get('overlap_state')!r}"
                )

            if is_legacy:
                if "rating_status" not in rec and "status" in rec:
                    rec["rating_status"] = rec["status"]
                if rec.get("rating_status") == "pending":
                    rec["rating_status"] = "unrated"
                if rec.get("status") == "pending":
                    rec["status"] = "unrated"
            else:
                if "rating_status" not in rec or rec["rating_status"] is None:
                    raise ValueError(
                        f"Canonical 1.0.0 work unit {uid!r} missing mandatory 'rating_status'"
                    )
                if rec["rating_status"] not in ("rated", "unrated"):
                    raise ValueError(
                        f"Canonical 1.0.0 work unit {uid!r} has invalid rating_status "
                        f"{rec['rating_status']!r}; expected 'rated' or 'unrated'"
                    )
                if "status" in rec and rec["status"] != rec["rating_status"]:
                    raise ValueError(
                        f"Canonical 1.0.0 work unit {uid!r} conflicting status aliases: "
                        f"rating_status={rec['rating_status']!r} != status={rec['status']!r}"
                    )

            # Validate cost alias consistency
            has_effort = "effort_cost" in rec and rec["effort_cost"] is not None
            has_computed = "computed_cost" in rec and rec["computed_cost"] is not None
            if has_effort and has_computed and rec["effort_cost"] != rec["computed_cost"]:
                raise ValueError(
                    f"Contradictory cost aliases in work unit {uid!r}: "
                    f"effort_cost={rec['effort_cost']!r} != computed_cost={rec['computed_cost']!r}"
                )

            rubric = rec.get("rubric_scores")
            if rubric is not None:
                if not isinstance(rubric, dict):
                    raise TypeError(
                        f"work unit {uid!r} rubric_scores must be dict, got {type(rubric).__name__}"
                    )
                rubric_cost = rubric.get("computed_cost")
                if rubric_cost is not None:
                    if has_effort and rubric_cost != rec["effort_cost"]:
                        raise ValueError(
                            f"Contradictory rubric computed_cost in work unit {uid!r}: "
                            f"rubric.computed_cost={rubric_cost!r} "
                            f"!= effort_cost={rec['effort_cost']!r}"
                        )
                    if has_computed and rubric_cost != rec["computed_cost"]:
                        raise ValueError(
                            f"Contradictory rubric computed_cost in work unit {uid!r}: "
                            f"rubric.computed_cost={rubric_cost!r} "
                            f"!= computed_cost={rec['computed_cost']!r}"
                        )

            if rec.get("rating_status") == "rated":
                if rubric and isinstance(rubric, dict):
                    t1 = rubric.get("t1")
                    t2 = rubric.get("t2")
                    if t1 in (1, 2, 3) and t2 in (1, 2, 3):
                        expected_cost = t1 + t2 - 2
                        # Reject cost mismatches fail-closed
                        if has_effort and rec["effort_cost"] != expected_cost:
                            raise ValueError(
                                f"Cost mismatch in work unit {uid!r}: "
                                f"declared effort_cost={rec['effort_cost']!r} "
                                f"!= rubric expected_cost={expected_cost!r}"
                            )
                        if has_computed and rec["computed_cost"] != expected_cost:
                            raise ValueError(
                                f"Cost mismatch in work unit {uid!r}: "
                                f"declared computed_cost={rec['computed_cost']!r} "
                                f"!= rubric expected_cost={expected_cost!r}"
                            )
                        if (
                            rubric.get("computed_cost") is not None
                            and rubric["computed_cost"] != expected_cost
                        ):
                            raise ValueError(
                                f"Cost mismatch in work unit {uid!r}: "
                                f"declared rubric.computed_cost={rubric['computed_cost']!r} "
                                f"!= rubric expected_cost={expected_cost!r}"
                            )
                        # Only populate derived costs when absent / None
                        if rubric.get("computed_cost") is None:
                            rubric["computed_cost"] = expected_cost
                        rubric.setdefault("formula", "base")
                        if not has_effort:
                            rec["effort_cost"] = expected_cost
                        if not has_computed:
                            rec["computed_cost"] = expected_cost

    # 2. Migrate bound_actions
    actions = query_part.get("bound_actions", [])
    if isinstance(actions, list):
        for idx, act in enumerate(actions):
            if not isinstance(act, dict):
                raise TypeError(
                    f"bound_actions entry {idx} must be a dict, got {type(act).__name__}"
                )

            action_id = act.get("action_id", idx)

            has_tech_name = "technique_name" in act and act["technique_name"] is not None
            has_tech = "technique" in act and act["technique"] is not None
            tech_name_val = act.get("technique_name")
            tech_val = act.get("technique")

            if has_tech_name:
                if not isinstance(tech_name_val, str) or not tech_name_val.strip():
                    raise TypeError(
                        f"bound_actions entry {idx} ({action_id!r}) technique_name "
                        f"must be non-empty string, got {type(tech_name_val).__name__}"
                    )
            if has_tech:
                if not isinstance(tech_val, str) or not tech_val.strip():
                    raise TypeError(
                        f"bound_actions entry {idx} ({action_id!r}) technique "
                        f"must be non-empty string, got {type(tech_val).__name__}"
                    )

            if not is_legacy:
                if not has_tech_name:
                    raise ValueError(
                        f"Canonical 1.0.0 bound action {action_id!r} "
                        "missing mandatory 'technique_name'"
                    )
                if has_tech and tech_val != tech_name_val:
                    raise ValueError(
                        f"bound_actions entry {idx} ({action_id!r}) conflicting technique "
                        f"aliases: technique_name={tech_name_val!r} != technique={tech_val!r}"
                    )
            else:
                if has_tech_name and has_tech:
                    if tech_name_val != tech_val:
                        raise ValueError(
                            f"bound_actions entry {idx} ({action_id!r}) conflicting technique "
                            f"aliases: technique_name={tech_name_val!r} != technique={tech_val!r}"
                        )
                    effective_tech = tech_name_val
                elif has_tech_name:
                    effective_tech = tech_name_val
                elif has_tech:
                    effective_tech = tech_val
                else:
                    effective_tech = None

                if effective_tech is not None:
                    act["technique_name"] = effective_tech
                    act["technique"] = effective_tech

            # Blocker 1: requires and adds fail closed on missing or non-list (no silent default)
            if "requires" not in act or act["requires"] is None:
                raise ValueError(
                    f"bound_actions entry {idx} ({action_id!r}) missing required 'requires' field"
                )
            if not isinstance(act["requires"], list):
                raise TypeError(
                    f"bound_actions entry {idx} ({action_id!r}) requires must be list, "
                    f"got {type(act['requires']).__name__}"
                )
            for r_idx, req in enumerate(act["requires"]):
                if not isinstance(req, str) or not req.strip():
                    raise TypeError(
                        f"bound_actions entry {idx} ({action_id!r}) requires element at "
                        f"index {r_idx} must be non-empty string"
                    )

            if "adds" not in act or act["adds"] is None:
                raise ValueError(
                    f"bound_actions entry {idx} ({action_id!r}) missing required 'adds' field"
                )
            if not isinstance(act["adds"], list):
                raise TypeError(
                    f"bound_actions entry {idx} ({action_id!r}) adds must be list, "
                    f"got {type(act['adds']).__name__}"
                )
            for a_idx, add_item in enumerate(act["adds"]):
                if not isinstance(add_item, str) or not add_item.strip():
                    raise TypeError(
                        f"bound_actions entry {idx} ({action_id!r}) adds element at "
                        f"index {a_idx} must be non-empty string"
                    )

            # referenced_work_unit_ids
            is_passive = act.get("is_passive_closure")
            if not is_legacy:
                if "referenced_work_unit_ids" not in act or act["referenced_work_unit_ids"] is None:
                    raise ValueError(
                        f"Canonical 1.0.0 bound action {action_id!r} "
                        "missing mandatory 'referenced_work_unit_ids'"
                    )
                if not isinstance(act["referenced_work_unit_ids"], list):
                    raise TypeError(
                        f"bound_actions entry {idx} ({action_id!r}) "
                        "referenced_work_unit_ids must be list"
                    )
                if "bound_work_units" in act and act["bound_work_units"] is not None:
                    if act["bound_work_units"] != act["referenced_work_unit_ids"]:
                        raise ValueError(
                            f"bound_actions entry {idx} ({action_id!r}) contradictory aliases: "
                            f"referenced_work_unit_ids {act['referenced_work_unit_ids']!r} != "
                            f"bound_work_units {act['bound_work_units']!r}"
                        )
                if is_passive and act["referenced_work_unit_ids"] != []:
                    raise ValueError(
                        f"Canonical 1.0.0 passive closure {action_id!r} "
                        "must have empty referenced_work_unit_ids"
                    )
                if not is_passive and len(act["referenced_work_unit_ids"]) == 0:
                    raise ValueError(
                        f"Canonical 1.0.0 active action {action_id!r} "
                        "must have non-empty referenced_work_unit_ids"
                    )
            else:
                if is_passive:
                    if (
                        "referenced_work_unit_ids" not in act
                        or act["referenced_work_unit_ids"] is None
                    ):
                        act["referenced_work_unit_ids"] = []
                    elif not isinstance(act["referenced_work_unit_ids"], list):
                        raise TypeError(
                            f"bound_actions entry {idx} referenced_work_unit_ids must be list"
                        )
                    if "bound_work_units" not in act or act["bound_work_units"] is None:
                        act["bound_work_units"] = []
                    elif not isinstance(act["bound_work_units"], list):
                        raise TypeError(f"bound_actions entry {idx} bound_work_units must be list")
                else:
                    if "referenced_work_unit_ids" in act and not isinstance(
                        act["referenced_work_unit_ids"], list
                    ):
                        raise TypeError(
                            f"bound_actions entry {idx} referenced_work_unit_ids must be list"
                        )
                    if "bound_work_units" in act and not isinstance(act["bound_work_units"], list):
                        raise TypeError(f"bound_actions entry {idx} bound_work_units must be list")
                    if "referenced_work_unit_ids" not in act and "bound_work_units" in act:
                        act["referenced_work_unit_ids"] = list(act["bound_work_units"])

    # 3. Migrate candidates if present
    candidates = migrated.get("candidates")
    if candidates is not None:
        if not isinstance(candidates, list):
            raise TypeError(f"candidates must be list, got {type(candidates).__name__}")
        scope_binding_template = {
            "query_id": meta.get("query_id"),
            "scenario_id": meta.get("scenario_id"),
            "scenario_version": meta.get("scenario_version"),
            "snapshot_id": meta.get("snapshot_id"),
            "work_boundary": meta.get("work_boundary"),
            "horizon": meta.get("horizon"),
            "foothold_node_id": meta.get("foothold_node_id"),
        }
        for cand in candidates:
            if not isinstance(cand, dict):
                raise TypeError(f"Candidate envelope must be dict, got {type(cand).__name__}")
            cid = cand.get("candidate_id")

            if "scope_binding" in cand:
                if not isinstance(cand["scope_binding"], dict) or isinstance(
                    cand["scope_binding"], bool
                ):
                    raise TypeError(
                        f"Candidate {cid!r} scope_binding must be dict, "
                        f"got {type(cand['scope_binding']).__name__}"
                    )
                for k, expected_v in scope_binding_template.items():
                    if k not in cand["scope_binding"] or cand["scope_binding"][k] is None:
                        raise ValueError(
                            f"Candidate {cid!r} scope_binding missing required field {k!r}"
                        )
                    actual_v = cand["scope_binding"][k]
                    if not isinstance(actual_v, str) or not actual_v.strip():
                        raise TypeError(
                            f"Candidate {cid!r} scope_binding field {k!r} "
                            f"must be non-empty string, got {actual_v!r}"
                        )
                    if actual_v != expected_v:
                        raise ValueError(
                            f"Candidate {cid!r} scope_binding field {k!r} "
                            f"conflicts with query_metadata: {actual_v!r} != {expected_v!r}"
                        )
            else:
                if not is_legacy:
                    raise ValueError(
                        f"Canonical 1.0.0 candidate {cid!r} missing mandatory 'scope_binding'"
                    )
                cand["scope_binding"] = dict(scope_binding_template)

            routes = cand.get("structural_routes")
            if routes is not None:
                if not isinstance(routes, list):
                    raise TypeError(
                        f"Candidate {cid!r} structural_routes must be list, "
                        f"got {type(routes).__name__}"
                    )
                for route in routes:
                    if not isinstance(route, dict):
                        continue
                    rid = route.get("route_id")
                    if "provenance_locators" in route:
                        if not isinstance(route["provenance_locators"], list):
                            raise TypeError(
                                f"Route {rid!r} provenance_locators must be list, "
                                f"got {type(route['provenance_locators']).__name__}"
                            )
                        for l_idx, loc_val in enumerate(route["provenance_locators"]):
                            if not isinstance(loc_val, str) or not loc_val.strip():
                                raise TypeError(
                                    f"Route {rid!r} provenance_locators[{l_idx}] "
                                    f"must be non-empty string, got {type(loc_val).__name__}"
                                )
                        eids = route.get("edge_ids", [])
                        if isinstance(eids, list) and len(eids) == len(
                            route["provenance_locators"]
                        ):
                            for eid, loc_str in zip(
                                eids, route["provenance_locators"], strict=False
                            ):
                                if eid in loc_map and loc_map[eid] != loc_str:
                                    raise ValueError(
                                        f"Route {rid!r} conflicting provenance locator "
                                        f"for edge {eid!r}: {loc_str!r} != {loc_map[eid]!r}"
                                    )
                    else:
                        if not is_legacy:
                            raise ValueError(
                                f"Canonical 1.0.0 route {rid!r} "
                                "missing mandatory 'provenance_locators'"
                            )
                        eids = route.get("edge_ids", [])
                        if not isinstance(eids, list):
                            raise TypeError(
                                f"Route {rid!r} edge_ids must be list, got {type(eids).__name__}"
                            )
                        locators = []
                        for eid in eids:
                            if eid in loc_map:
                                locators.append(loc_map[eid])
                            else:
                                raise ValueError(
                                    f"Cannot migrate route {rid!r}: missing provenance locator "
                                    f"for edge {eid!r} in snapshot {snapshot_id!r}"
                                )
                        route["provenance_locators"] = locators

    return migrated
