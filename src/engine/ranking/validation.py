"""Fail-closed contract validation boundary for PathRankingQuery and Candidate Envelopes.

Implements strict validation according to Specification v1.0.0:
- Graph Contract 1.3 canonical IDs (canonical SIDs, GUIDs, scoped SIDs, edge hashes).
- Mandatory 6-component query wire payload.
- Versioned query metadata, snapshot identity, evaluation mode, work boundary.
- Canonical persistent work units ledger with rubric validation and unresolved overlap rules.
- Bound actions catalog referencing known work units and canonical node IDs.
- Conditional bounds table with duplicate prefix detection and [0, 1] rational bounds.
- Target impact assessments with ordinal ratings vs unrated missing basis reasons.
- Mandatory authoritative predicate layer for EVERY referenced predicate.
- Candidate envelopes validation, unique candidate IDs, and route trace integrity.
"""

from __future__ import annotations

import json
from copy import deepcopy
from fractions import Fraction
from typing import Any

from src.engine.ranking.models import (
    CANONICAL_EDGE_ID_PATTERN,
    IMPACT_ORDINAL,
    REQUIRED_SCOPE_BINDING_FIELDS,
    SNAPSHOT_ID_PATTERN,
    CompletenessScope,
    DuplicatePrefixError,
    MappingSyncError,
    RankingValidationError,
    is_canonical_node_id,
    parse_rational,
)

VALID_TRUNCATION_REASONS: frozenset[str] = frozenset(
    {
        "work_budget_exceeded",
        "candidate_limit_reached",
        "timeout_exceeded",
        "expansion_limit_reached",
        "step_limit_reached",
    }
)

VALID_COMPLETENESS_SCOPES: frozenset[str] = frozenset(
    {
        CompletenessScope.EXHAUSTIVE_WITHIN_SCOPE.value,
        CompletenessScope.BUDGET_BOUNDED.value,
        CompletenessScope.PARTIAL_TRUNCATED.value,
        CompletenessScope.UNSPECIFIED_SUBSET.value,
    }
)


def _is_exact_int(val: Any) -> bool:
    """Return True if val is an exact int, excluding bools and floats."""
    return type(val) is int


def validate_work_units_ledger(ledger: Any) -> dict[str, dict[str, Any]]:
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

        if "missing_basis_reasons" in rec:
            reasons = rec["missing_basis_reasons"]
            if not isinstance(reasons, list) or any(
                not isinstance(reason, str) or not reason.strip() for reason in reasons
            ):
                raise RankingValidationError(
                    f"work unit {unit_id} missing_basis_reasons must be a list of non-empty strings"
                )

        if "overlap_state" not in rec:
            raise RankingValidationError(f"work unit {unit_id} missing required 'overlap_state'")
        overlap_state = rec["overlap_state"]
        if overlap_state not in ("independent", "unresolved_overlap"):
            raise RankingValidationError(
                f"work unit {unit_id} invalid overlap_state: {overlap_state!r}"
            )

        rubric = rec.get("rubric_scores")
        if rubric is not None and not isinstance(rubric, dict):
            raise TypeError(f"work unit {unit_id} rubric_scores must be a dict or null")

        # Contradictory alias validation: rating_status vs status
        explicit_rating_status = rec.get("rating_status")
        explicit_status = rec.get("status")
        if explicit_rating_status is None and explicit_status is None:
            raise RankingValidationError(f"work unit {unit_id} missing required 'rating_status'")
        if explicit_rating_status is not None and explicit_status is not None:
            if explicit_rating_status != explicit_status:
                raise RankingValidationError(
                    f"work unit {unit_id} contradictory aliases: "
                    f"rating_status {explicit_rating_status!r} != status {explicit_status!r}"
                )
            status_val = explicit_rating_status
        elif explicit_rating_status is not None:
            status_val = explicit_rating_status
        else:
            status_val = explicit_status

        if status_val not in ("rated", "unrated"):
            raise RankingValidationError(f"work unit {unit_id} invalid status: {status_val!r}")
        rating_status = status_val

        # Strict exact-integer type validation for declared cost fields
        cost_effort = rec.get("effort_cost")
        if cost_effort is not None:
            if not _is_exact_int(cost_effort):
                raise RankingValidationError(
                    f"work unit {unit_id} effort_cost must be an exact integer, "
                    f"got {cost_effort!r} (type {type(cost_effort).__name__})"
                )
            if not (0 <= cost_effort <= 4):
                raise RankingValidationError(
                    f"work unit {unit_id} effort_cost must be in range 0..4, got {cost_effort}"
                )

        cost_computed = rec.get("computed_cost")
        if cost_computed is not None:
            if not _is_exact_int(cost_computed):
                raise RankingValidationError(
                    f"work unit {unit_id} computed_cost must be an exact integer, "
                    f"got {cost_computed!r} (type {type(cost_computed).__name__})"
                )
            if not (0 <= cost_computed <= 4):
                raise RankingValidationError(
                    f"work unit {unit_id} computed_cost must be in range 0..4, got {cost_computed}"
                )

        top_effort = rec.get("effort")
        if top_effort is not None:
            if not _is_exact_int(top_effort):
                raise RankingValidationError(
                    f"work unit {unit_id} effort must be an exact integer, got {top_effort!r} "
                    f"(type {type(top_effort).__name__})"
                )
            if not (0 <= top_effort <= 4):
                raise RankingValidationError(
                    f"work unit {unit_id} effort must be in range 0..4, got {top_effort}"
                )

        # Contradictory alias validation: effort_cost vs computed_cost vs effort
        if cost_effort is not None and cost_computed is not None:
            if cost_effort != cost_computed:
                raise RankingValidationError(
                    f"work unit {unit_id} contradictory aliases: "
                    f"effort_cost {cost_effort!r} != computed_cost {cost_computed!r}"
                )
        if top_effort is not None:
            if cost_effort is not None and top_effort != cost_effort:
                raise RankingValidationError(
                    f"work unit {unit_id} contradictory aliases: "
                    f"effort {top_effort!r} != effort_cost {cost_effort!r}"
                )
            if cost_computed is not None and top_effort != cost_computed:
                raise RankingValidationError(
                    f"work unit {unit_id} contradictory aliases: "
                    f"effort {top_effort!r} != computed_cost {cost_computed!r}"
                )

        # Strict exact-integer type validation for top-level rubric scores (if declared)
        top_t1 = rec.get("t1")
        if top_t1 is not None:
            if not _is_exact_int(top_t1):
                raise RankingValidationError(
                    f"work unit {unit_id} t1 must be an exact integer in {{1, 2, 3}}, "
                    f"got {top_t1!r} (type {type(top_t1).__name__})"
                )
            if top_t1 not in (1, 2, 3):
                raise RankingValidationError(
                    f"work unit {unit_id} t1 must be in {{1, 2, 3}}, got {top_t1}"
                )

        top_t2 = rec.get("t2")
        if top_t2 is not None:
            if not _is_exact_int(top_t2):
                raise RankingValidationError(
                    f"work unit {unit_id} t2 must be an exact integer in {{1, 2, 3}}, "
                    f"got {top_t2!r} (type {type(top_t2).__name__})"
                )
            if top_t2 not in (1, 2, 3):
                raise RankingValidationError(
                    f"work unit {unit_id} t2 must be in {{1, 2, 3}}, got {top_t2}"
                )

        if overlap_state == "unresolved_overlap":
            if (
                status_val == "rated"
                or rubric is not None
                or top_t1 is not None
                or top_t2 is not None
            ):
                raise RankingValidationError(
                    f"work unit {unit_id} has conflicting state: rating_status is 'rated' "
                    f"but overlap_state is 'unresolved_overlap'"
                )
            rating_status = "unrated"
            rubric = None

        if rating_status == "rated":
            if rubric is not None:
                t1 = rubric.get("t1")
                if not _is_exact_int(t1):
                    raise RankingValidationError(
                        f"work unit {unit_id} rubric_scores.t1 must be an exact integer "
                        f"in {{1, 2, 3}}, got {t1!r} (type {type(t1).__name__})"
                    )
                if t1 not in (1, 2, 3):
                    raise RankingValidationError(
                        f"work unit {unit_id} rated units must have t1 in {{1, 2, 3}}, got {t1}"
                    )

                t2 = rubric.get("t2")
                if not _is_exact_int(t2):
                    raise RankingValidationError(
                        f"work unit {unit_id} rubric_scores.t2 must be an exact integer "
                        f"in {{1, 2, 3}}, got {t2!r} (type {type(t2).__name__})"
                    )
                if t2 not in (1, 2, 3):
                    raise RankingValidationError(
                        f"work unit {unit_id} rated units must have t2 in {{1, 2, 3}}, got {t2}"
                    )

                # Check top-level t1/t2 consistency if also declared
                if top_t1 is not None and top_t1 != t1:
                    raise RankingValidationError(
                        f"work unit {unit_id} contradictory aliases: "
                        f"top-level t1 {top_t1!r} != rubric t1 {t1!r}"
                    )
                if top_t2 is not None and top_t2 != t2:
                    raise RankingValidationError(
                        f"work unit {unit_id} contradictory aliases: "
                        f"top-level t2 {top_t2!r} != rubric t2 {t2!r}"
                    )

                rubric_cost = rubric.get("computed_cost")
                if rubric_cost is not None:
                    if not _is_exact_int(rubric_cost):
                        raise RankingValidationError(
                            f"work unit {unit_id} rubric_scores.computed_cost must be "
                            f"an exact integer, got {rubric_cost!r} "
                            f"(type {type(rubric_cost).__name__})"
                        )
                    if not (0 <= rubric_cost <= 4):
                        raise RankingValidationError(
                            f"work unit {unit_id} rubric_scores.computed_cost must be "
                            f"in range 0..4, got {rubric_cost}"
                        )

                rubric_effort_cost = rubric.get("effort_cost")
                if rubric_effort_cost is not None:
                    if not _is_exact_int(rubric_effort_cost):
                        raise RankingValidationError(
                            f"work unit {unit_id} rubric_scores.effort_cost must be "
                            f"an exact integer, got {rubric_effort_cost!r} "
                            f"(type {type(rubric_effort_cost).__name__})"
                        )
                    if not (0 <= rubric_effort_cost <= 4):
                        raise RankingValidationError(
                            f"work unit {unit_id} rubric_scores.effort_cost must be "
                            f"in range 0..4, got {rubric_effort_cost}"
                        )
                    if rubric_cost is not None and rubric_effort_cost != rubric_cost:
                        raise RankingValidationError(
                            f"work unit {unit_id} contradictory rubric cost aliases: "
                            f"rubric_scores.effort_cost {rubric_effort_cost!r} != "
                            f"rubric_scores.computed_cost {rubric_cost!r}"
                        )
                    if rubric_cost is None:
                        rubric_cost = rubric_effort_cost

                # Cost conflict checks between rubric and top-level declared costs
                if (
                    rubric_cost is not None
                    and cost_effort is not None
                    and rubric_cost != cost_effort
                ):
                    raise RankingValidationError(
                        f"work unit {unit_id} contradictory cost aliases: "
                        f"rubric_scores.computed_cost {rubric_cost!r} != "
                        f"effort_cost {cost_effort!r}"
                    )
                if (
                    rubric_cost is not None
                    and cost_computed is not None
                    and rubric_cost != cost_computed
                ):
                    raise RankingValidationError(
                        f"work unit {unit_id} contradictory cost aliases: "
                        f"rubric_scores.computed_cost {rubric_cost!r} != "
                        f"computed_cost {cost_computed!r}"
                    )
                if rubric_cost is not None and top_effort is not None and rubric_cost != top_effort:
                    raise RankingValidationError(
                        f"work unit {unit_id} contradictory cost aliases: "
                        f"rubric_scores.computed_cost {rubric_cost!r} != "
                        f"effort {top_effort!r}"
                    )

                declared_cost = (
                    rubric_cost
                    if rubric_cost is not None
                    else (cost_effort if cost_effort is not None else cost_computed)
                )
                if declared_cost is None and top_effort is not None:
                    declared_cost = top_effort

                formula_rubric = rubric.get("formula")
                formula_top = rec.get("formula")
                if (
                    formula_rubric is not None
                    and formula_top is not None
                    and formula_rubric != formula_top
                ):
                    raise RankingValidationError(
                        f"work unit {unit_id} contradictory formula: "
                        f"rubric_scores formula {formula_rubric!r} != "
                        f"top-level formula {formula_top!r}"
                    )
                formula = formula_rubric if formula_rubric is not None else formula_top
                if formula is None:
                    formula = "base"
            else:
                if top_t1 is None or top_t2 is None:
                    raise RankingValidationError(
                        f"work unit {unit_id} rated units without rubric_scores "
                        "must declare top-level t1 and t2"
                    )
                t1 = top_t1
                t2 = top_t2
                declared_cost = cost_effort if cost_effort is not None else cost_computed
                if declared_cost is None and top_effort is not None:
                    declared_cost = top_effort
                formula = rec.get("formula", "base")

            if formula != "base":
                raise RankingValidationError(
                    f"work unit {unit_id} unsupported formula: {formula!r}, "
                    "only 'base' is supported"
                )

            expected_cost = t1 + t2 - 2
            if declared_cost is not None and declared_cost != expected_cost:
                raise RankingValidationError(
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
                **deepcopy(rec),
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
                raise RankingValidationError(
                    f"work unit {unit_id} unrated units must have rubric_scores null"
                )
            if cost_effort is not None or cost_computed is not None or top_effort is not None:
                raise RankingValidationError(
                    f"work unit {unit_id} unrated units must have effort_cost null"
                )
            if top_t1 is not None or top_t2 is not None:
                raise RankingValidationError(
                    f"work unit {unit_id} unrated units must have t1, t2 null"
                )
            if rec.get("formula") is not None:
                raise RankingValidationError(
                    f"work unit {unit_id} unrated units must have formula null"
                )

            validated[unit_id] = {
                **deepcopy(rec),
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
    actions: Any,
    known_work_units: set[str],
) -> list[dict[str, Any]]:
    """Validate bound actions catalog referencing canonical work units (Spec 2.3)."""
    if not isinstance(actions, list):
        raise TypeError("bound_actions must be a list")

    seen_action_ids: set[str] = set()
    validated: list[dict[str, Any]] = []
    for idx, act in enumerate(actions):
        if not isinstance(act, dict):
            raise TypeError(f"bound_actions entry {idx} must be a dict")

        action_id = act.get("action_id")
        if not isinstance(action_id, str) or not action_id.strip():
            raise TypeError(f"bound_actions entry {idx} action_id must be a non-empty string")
        if action_id in seen_action_ids:
            raise RankingValidationError(
                f"Duplicate action_id detected in bound_actions: {action_id!r} at index {idx}"
            )
        seen_action_ids.add(action_id)

        if "technique_name" not in act:
            raise RankingValidationError(
                f"bound_actions entry {idx} ({action_id!r}) missing required 'technique_name' field"
            )
        technique_name = act["technique_name"]
        if not isinstance(technique_name, str) or not technique_name.strip():
            raise RankingValidationError(
                f"bound_actions entry {idx} ({action_id!r}) technique_name "
                "must be a non-empty string"
            )

        if "is_passive_closure" not in act:
            raise RankingValidationError(
                f"bound_actions entry {idx} ({action_id!r}) missing required "
                "'is_passive_closure' field"
            )
        raw_passive = act["is_passive_closure"]
        if not isinstance(raw_passive, bool):
            raise RankingValidationError(
                f"bound_actions entry {idx} ({action_id!r}) is_passive_closure must be a "
                f"boolean, got {type(raw_passive).__name__}"
            )
        is_passive = raw_passive

        ref_units = act.get("referenced_work_unit_ids")
        bound_units_raw = act.get("bound_work_units")
        if ref_units is not None and bound_units_raw is not None:
            if ref_units != bound_units_raw:
                raise RankingValidationError(
                    f"bound_actions entry {idx} ({action_id!r}) contradictory aliases: "
                    f"referenced_work_unit_ids {ref_units!r} != "
                    f"bound_work_units {bound_units_raw!r}"
                )
            bound_units = ref_units
        elif ref_units is not None:
            bound_units = ref_units
        elif bound_units_raw is not None:
            bound_units = bound_units_raw
        else:
            raise RankingValidationError(
                f"bound_actions entry {idx} ({action_id!r}) missing required "
                "'referenced_work_unit_ids'"
            )

        if not isinstance(bound_units, list):
            raise TypeError(f"bound_actions entry {idx} referenced_work_unit_ids must be a list")

        if is_passive:
            if bound_units:
                raise RankingValidationError(
                    f"bound_actions entry {idx} ({action_id!r}) passive closure must have empty "
                    "referenced_work_unit_ids"
                )
        else:
            if not bound_units:
                raise TypeError(
                    f"bound_actions entry {idx} active action must have non-empty "
                    f"referenced_work_unit_ids"
                )

        for u in bound_units:
            if not isinstance(u, str) or u not in known_work_units:
                raise RankingValidationError(
                    f"bound_actions entry {idx} references unknown work unit: {u!r}"
                )

        # Contradictory alias validation: actor_id vs source_node_id
        actor_id = act.get("actor_id")
        source_node_id = act.get("source_node_id")
        if actor_id is not None and source_node_id is not None:
            if actor_id != source_node_id:
                raise RankingValidationError(
                    f"bound_actions entry {idx} ({action_id!r}) contradictory aliases: "
                    f"actor_id {actor_id!r} != source_node_id {source_node_id!r}"
                )
            src = actor_id
        elif actor_id is not None:
            src = actor_id
        elif source_node_id is not None:
            src = source_node_id
        else:
            src = None

        if src is None:
            raise RankingValidationError(
                f"bound_actions entry {idx} ({action_id!r}) missing required actor_id"
            )
        if not is_canonical_node_id(src):
            raise RankingValidationError(
                f"bound_actions entry {idx} ({action_id!r}) invalid actor_id: {src!r}"
            )

        # Contradictory alias validation: target_id vs target_node_id
        target_id = act.get("target_id")
        target_node_id = act.get("target_node_id")
        if target_id is not None and target_node_id is not None:
            if target_id != target_node_id:
                raise RankingValidationError(
                    f"bound_actions entry {idx} ({action_id!r}) contradictory aliases: "
                    f"target_id {target_id!r} != target_node_id {target_node_id!r}"
                )
            tgt = target_id
        elif target_id is not None:
            tgt = target_id
        elif target_node_id is not None:
            tgt = target_node_id
        else:
            tgt = None

        if tgt is None:
            raise RankingValidationError(
                f"bound_actions entry {idx} ({action_id!r}) missing required target_id"
            )
        if not is_canonical_node_id(tgt):
            raise RankingValidationError(
                f"bound_actions entry {idx} ({action_id!r}) invalid target_id: {tgt!r}"
            )

        edge_id = act.get("edge_id")
        if edge_id is not None and not CANONICAL_EDGE_ID_PATTERN.match(edge_id):
            raise RankingValidationError(f"bound_actions entry {idx} invalid edge_id: {edge_id!r}")

        norm_act = dict(act)
        norm_act["action_id"] = action_id
        norm_act["technique_name"] = technique_name
        norm_act["actor_id"] = src
        norm_act["source_node_id"] = src
        norm_act["target_id"] = tgt
        norm_act["target_node_id"] = tgt
        norm_act["referenced_work_unit_ids"] = bound_units
        norm_act["bound_work_units"] = bound_units
        if "requires" not in act:
            raise RankingValidationError(
                f"bound_actions entry {idx} ({action_id!r}) missing required 'requires' field"
            )
        raw_requires = act["requires"]
        if not isinstance(raw_requires, list):
            raise TypeError(
                f"bound_actions entry {idx} ({action_id!r}) requires must be a list of "
                "non-empty strings"
            )
        for r_idx, req in enumerate(raw_requires):
            if not isinstance(req, str) or not req.strip():
                raise RankingValidationError(
                    f"bound_actions entry {idx} ({action_id!r}) requires element at "
                    f"index {r_idx} must be a non-empty string"
                )
        req_list = list(raw_requires)

        if "adds" not in act:
            raise RankingValidationError(
                f"bound_actions entry {idx} ({action_id!r}) missing required 'adds' field"
            )
        raw_adds = act["adds"]
        if not isinstance(raw_adds, list):
            raise TypeError(
                f"bound_actions entry {idx} ({action_id!r}) adds must be a list of "
                "non-empty strings"
            )
        for a_idx, add_item in enumerate(raw_adds):
            if not isinstance(add_item, str) or not add_item.strip():
                raise RankingValidationError(
                    f"bound_actions entry {idx} ({action_id!r}) adds element at "
                    f"index {a_idx} must be a non-empty string"
                )
        adds_list = list(raw_adds)

        norm_act["is_passive_closure"] = is_passive
        norm_act["requires"] = req_list
        norm_act["adds"] = adds_list
        validated.append(norm_act)

    return validated


def validate_and_decode_bounds_table(
    wire_bounds_list: Any,
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

        for field in ("basis_category", "rationale"):
            if field in entry and (not isinstance(entry[field], str) or not entry[field].strip()):
                raise RankingValidationError(f"Entry {idx} {field} must be a non-empty string")

        prefix_raw = entry.get("prefix")
        if not isinstance(prefix_raw, (list, tuple)):
            raise TypeError(f"Entry {idx} prefix must be a list of string identifiers")
        if not prefix_raw:
            raise RankingValidationError(f"Entry {idx} prefix cannot be empty")

        prefix_elements: list[str] = []
        for step_idx, step in enumerate(prefix_raw):
            if not isinstance(step, str) or not step.strip():
                raise TypeError(
                    f"Entry {idx} prefix step {step_idx} must be a non-empty string, got {step!r}"
                )
            if known_work_units is not None and step not in known_work_units:
                raise RankingValidationError(
                    f"Entry {idx} prefix references unknown work unit ID: {step!r}"
                )
            prefix_elements.append(step)

        prefix = tuple(prefix_elements)
        if prefix in table:
            raise DuplicatePrefixError(f"Duplicate prefix detected in bounds table: {prefix}")

        lower_raw = entry.get("lower")
        upper_raw = entry.get("upper")
        if lower_raw is None or upper_raw is None:
            raise RankingValidationError(
                f"Entry {idx} must provide both 'lower' and 'upper' bounds"
            )

        try:
            lower = parse_rational(lower_raw)
            upper = parse_rational(upper_raw)
        except (ValueError, ZeroDivisionError, TypeError) as err:
            raise RankingValidationError(
                f"Entry {idx} bounds must be valid rational numbers/strings: {err}"
            ) from err

        if not (0 <= lower <= upper <= 1):
            raise RankingValidationError(
                f"Entry {idx} bounds interval [{lower}, {upper}] is invalid: "
                "must satisfy 0 <= lower <= upper <= 1"
            )

        table[prefix] = (lower, upper)

    return table


def validate_target_impact_assessments(
    assessments: Any,
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
            raise RankingValidationError(
                f"Target asset ID {asset_id!r} is not a valid canonical node ID"
            )
        if not isinstance(record, dict):
            raise TypeError(f"Assessment for {asset_id} must be an object")

        declared_target = record.get("target_asset_id")
        if declared_target is not None and declared_target != asset_id:
            raise RankingValidationError(
                f"Target asset ID mismatch: key {asset_id!r} != record {declared_target!r}"
            )

        success_event = record.get("success_event")
        if not isinstance(success_event, str) or not success_event.strip():
            raise RankingValidationError(
                f"Asset {asset_id} missing required non-empty 'success_event'"
            )

        status = record.get("rating_status")
        if status not in ("rated", "unrated"):
            raise RankingValidationError(
                f"Asset {asset_id} rating_status must be 'rated' or 'unrated', got {status!r}"
            )

        rating = record.get("consequence_rating")
        if status == "rated":
            if rating not in IMPACT_ORDINAL:
                raise RankingValidationError(
                    f"Asset {asset_id} invalid consequence_rating {rating!r}: "
                    f"must be one of {list(IMPACT_ORDINAL.keys())}"
                )
        else:
            if rating is not None:
                raise RankingValidationError(
                    f"Asset {asset_id} consequence_rating must be null when "
                    "rating_status is 'unrated'"
                )
            reasons = record.get("missing_basis_reasons")
            if not isinstance(reasons, list) or not reasons:
                raise RankingValidationError(
                    f"Asset {asset_id} must provide a non-empty missing_basis_reasons list"
                )
            for r in reasons:
                if not isinstance(r, str) or not r.strip():
                    raise TypeError(
                        f"Asset {asset_id} missing_basis_reasons elements must be strings"
                    )

        validated[asset_id] = record

    return validated


def validate_upstream_coverage(coverage: Any) -> dict[str, Any]:
    """Validate upstream search coverage boundary and enforce consistency invariants (Spec §3.1).

    Enforces:
    - coverage must be a dictionary.
    - is_truncated must be a strict boolean if present.
    - truncation_reasons must be a list of non-empty strings from VALID_TRUNCATION_REASONS.
    - When is_truncated is False, truncation_reasons must be empty and scope not partial_truncated.
    - completeness_scope must be one of VALID_COMPLETENESS_SCOPES.
    - caps_applied must be a dictionary with non-negative integer or None values.
    """
    if coverage is None:
        return {}
    if not isinstance(coverage, dict):
        raise TypeError(f"upstream_coverage must be a dictionary, got {type(coverage).__name__}")

    raw_is_truncated = coverage.get("is_truncated")
    if raw_is_truncated is not None and type(raw_is_truncated) is not bool:
        raise TypeError(
            f"upstream_coverage is_truncated must be a boolean, got {raw_is_truncated!r}"
        )
    is_truncated = bool(raw_is_truncated) if raw_is_truncated is not None else False

    raw_reasons = coverage.get("truncation_reasons")
    reasons: list[str] = []
    if raw_reasons is not None:
        if not isinstance(raw_reasons, list):
            raise TypeError(
                "upstream_coverage truncation_reasons must be a list of strings, "
                f"got {type(raw_reasons).__name__}"
            )
        for idx, r in enumerate(raw_reasons):
            if not isinstance(r, str) or not r.strip():
                raise RankingValidationError(
                    f"upstream_coverage truncation_reasons element at index {idx} "
                    "must be a non-empty string"
                )
            if r not in VALID_TRUNCATION_REASONS:
                allowed = sorted(VALID_TRUNCATION_REASONS)
                raise RankingValidationError(
                    f"upstream_coverage invalid truncation_reason: {r!r}, allowed: {allowed}"
                )
            reasons.append(r)

    if not is_truncated and len(reasons) > 0:
        raise RankingValidationError(
            "upstream_coverage cannot have non-empty truncation_reasons when is_truncated is "
            f"False: {reasons!r}"
        )
    if is_truncated and len(reasons) == 0:
        raise RankingValidationError(
            "upstream_coverage must provide at least one non-empty truncation_reason when "
            "is_truncated is True"
        )

    raw_scope = coverage.get("completeness_scope")
    if raw_scope is not None:
        if not isinstance(raw_scope, str):
            raise TypeError(
                "upstream_coverage completeness_scope must be a string, "
                f"got {type(raw_scope).__name__}"
            )
        if raw_scope not in VALID_COMPLETENESS_SCOPES:
            allowed_scopes = sorted(VALID_COMPLETENESS_SCOPES)
            raise RankingValidationError(
                f"upstream_coverage invalid completeness_scope: {raw_scope!r}, "
                f"allowed: {allowed_scopes}"
            )
        if not is_truncated and raw_scope == CompletenessScope.PARTIAL_TRUNCATED.value:
            raise RankingValidationError(
                f"upstream_coverage cannot claim {raw_scope!r} when is_truncated is False"
            )
        if is_truncated:
            # Spec §3.1: When is_truncated is True, scope is normalized to partial_truncated
            scope = CompletenessScope.PARTIAL_TRUNCATED.value
        else:
            scope = raw_scope
    else:
        scope = (
            CompletenessScope.PARTIAL_TRUNCATED.value
            if is_truncated
            else CompletenessScope.UNSPECIFIED_SUBSET.value
        )

    raw_caps = coverage.get("caps_applied")
    caps: dict[str, Any] = {}
    if raw_caps is not None:
        if not isinstance(raw_caps, dict):
            raise TypeError(
                "upstream_coverage caps_applied must be a dictionary, "
                f"got {type(raw_caps).__name__}"
            )
        normalized_caps = dict(raw_caps)
        if "max_paths" in normalized_caps:
            max_paths = normalized_caps["max_paths"]
            if (
                "max_candidates" in normalized_caps
                and normalized_caps["max_candidates"] != max_paths
            ):
                raise RankingValidationError(
                    "upstream_coverage caps_applied has conflicting aliases: "
                    f"max_paths={max_paths!r} != "
                    f"max_candidates={normalized_caps['max_candidates']!r}"
                )
            normalized_caps["max_candidates"] = max_paths
            del normalized_caps["max_paths"]
        for cap_key, cap_val in normalized_caps.items():
            if cap_val is not None:
                if type(cap_val) is not int or cap_val < 0:
                    raise RankingValidationError(
                        f"upstream_coverage caps_applied {cap_key!r} must be a non-negative "
                        f"integer or null, got {cap_val!r}"
                    )
            caps[cap_key] = cap_val

    normalized: dict[str, Any] = dict(coverage)
    normalized["is_truncated"] = is_truncated
    normalized["truncation_reasons"] = reasons
    normalized["completeness_scope"] = scope
    normalized["caps_applied"] = caps
    return normalized


def validate_query_metadata(meta: Any) -> dict[str, Any]:
    """Validate query metadata section."""
    if not isinstance(meta, dict):
        raise TypeError("query_metadata must be a dictionary")

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
            raise RankingValidationError(f"Missing required query_metadata field: {field!r}")

    if meta["version"] != "1.0.0":
        raise RankingValidationError(
            f"Unsupported contract version: {meta['version']!r}, expected '1.0.0'"
        )

    if meta["evaluation_mode"] not in ("evidence_only", "scenario"):
        raise RankingValidationError(f"Invalid evaluation_mode: {meta['evaluation_mode']!r}")

    if not SNAPSHOT_ID_PATTERN.match(str(meta["snapshot_id"])):
        raise RankingValidationError(
            f"Invalid snapshot_id: {meta['snapshot_id']!r}, must match ^sha256:[0-9a-f]{{64}}$"
        )

    if not is_canonical_node_id(meta["foothold_node_id"]):
        raise RankingValidationError(f"Invalid foothold_node_id: {meta['foothold_node_id']!r}")

    budget = meta["active_work_budget"]
    if type(budget) is not int or budget < 0:
        raise RankingValidationError(
            f"active_work_budget must be a non-negative integer, got {budget!r}"
        )

    target_goal = meta["target_goal"]
    if not isinstance(target_goal, dict):
        raise TypeError("target_goal must be a dictionary")
    if not target_goal.get("goal_id") or not isinstance(
        target_goal.get("required_predicates"), list
    ):
        raise RankingValidationError(
            "target_goal must contain goal_id and required_predicates list"
        )

    if "coverage" in meta and meta["coverage"] is not None:
        meta["coverage"] = validate_upstream_coverage(meta["coverage"])

    return meta


def validate_authoritative_predicate_layers(
    facts_ledger: dict[str, Any],
    bound_actions: list[dict[str, Any]],
    target_goal: dict[str, Any],
    resolved_facts: dict[str, dict[str, Any]],
) -> dict[str, int]:
    """Ensure every referenced predicate has an authoritative layer classification."""
    authoritative_layers: dict[str, int] = dict(facts_ledger.get("predicate_layers", {}))
    for p, v in resolved_facts.items():
        if "layer" in v:
            authoritative_layers[p] = v["layer"]

    for idx, act in enumerate(bound_actions):
        for req in act.get("requires", []):
            if req not in authoritative_layers:
                raise RankingValidationError(
                    f"Missing authoritative layer classification for predicate {req!r} in "
                    f"bound_actions entry {idx} (requires): authoritative layer must be explicitly "
                    f"declared in predicate_layers or facts_ledger"
                )
        for add_p in act.get("adds", []):
            if add_p not in authoritative_layers:
                raise RankingValidationError(
                    f"Missing authoritative layer classification for predicate {add_p!r} in "
                    f"bound_actions entry {idx} (adds): authoritative layer must be explicitly "
                    f"declared in predicate_layers or facts_ledger"
                )

    for gp in target_goal.get("required_predicates", []):
        if gp not in authoritative_layers:
            raise RankingValidationError(
                f"Missing authoritative layer classification for predicate {gp!r} in "
                f"target_goal.required_predicates: authoritative layer must be explicitly "
                f"declared in predicate_layers or facts_ledger"
            )

    return authoritative_layers


def decode_ranking_query(query_json: str | dict[str, Any]) -> dict[str, Any]:
    """Parse and validate full PathRankingQuery wire payload.

    Enforces all 6 mandatory top-level sections according to Specification v1.0.0.
    """
    from src.engine.ranking.facts import resolve_facts_ledger

    if isinstance(query_json, str):
        query = json.loads(query_json)
    elif isinstance(query_json, dict):
        query = query_json
    else:
        raise TypeError("query payload must be a JSON string or dict")

    if not isinstance(query, dict):
        raise TypeError("Top-level query payload must be a JSON object")

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
            raise RankingValidationError(f"Missing required top-level query component: {section!r}")

    meta = validate_query_metadata(query["query_metadata"])
    validated_units = validate_work_units_ledger(query["work_units_ledger"])
    known_units = set(validated_units.keys())
    validated_actions = validate_bound_actions(query["bound_actions"], known_units)
    decoded_bounds = validate_and_decode_bounds_table(
        query["conditional_bounds_table"], known_work_units=known_units
    )
    validated_impacts = validate_target_impact_assessments(query["target_impact_assessments"])

    resolved_facts = resolve_facts_ledger(
        query["facts_ledger"],
        evaluation_mode=meta["evaluation_mode"],
    )

    authoritative_layers = validate_authoritative_predicate_layers(
        facts_ledger=query["facts_ledger"],
        bound_actions=validated_actions,
        target_goal=meta["target_goal"],
        resolved_facts=resolved_facts,
    )

    return {
        "query_metadata": meta,
        "facts_ledger": query["facts_ledger"],
        "predicate_layers": authoritative_layers,
        "resolved_facts": resolved_facts,
        "bound_actions": validated_actions,
        "work_units_ledger": validated_units,
        "conditional_bounds_table": decoded_bounds,
        "conditional_bounds_records": deepcopy(query["conditional_bounds_table"]),
        "parameter_audit": deepcopy(
            {
                "query_metadata": query["query_metadata"],
                "work_units_ledger": query["work_units_ledger"],
                "conditional_bounds_table": query["conditional_bounds_table"],
                "target_impact_assessments": query["target_impact_assessments"],
            }
        ),
        "target_impact_assessments": validated_impacts,
    }


def validate_scope_binding(
    scope: Any,
    query_metadata: dict[str, Any],
    candidate_id: str,
) -> dict[str, Any]:
    """Validate candidate envelope scope binding against query metadata.

    Fails closed if scope_binding is missing, malformed, or mismatches any required field.
    """
    if not isinstance(scope, dict):
        raise RankingValidationError(
            f"Candidate {candidate_id} must specify an explicit 'scope_binding' dictionary"
        )

    for field in REQUIRED_SCOPE_BINDING_FIELDS:
        if field not in scope or scope[field] is None:
            raise RankingValidationError(
                f"Candidate {candidate_id} scope_binding missing required field {field!r}"
            )
        val = scope[field]
        if not isinstance(val, str) or not val.strip():
            raise RankingValidationError(
                f"Candidate {candidate_id} scope_binding field {field!r} "
                f"must be a non-empty string, got {val!r}"
            )
        expected = query_metadata.get(field)
        if val != expected:
            raise RankingValidationError(
                f"Candidate {candidate_id} scope_binding {field} mismatch: "
                f"candidate has {val!r}, query expects {expected!r}"
            )

    if not is_canonical_node_id(scope["foothold_node_id"]):
        raise RankingValidationError(
            f"Candidate {candidate_id} scope_binding foothold_node_id "
            f"{scope['foothold_node_id']!r} is not a valid canonical node ID"
        )

    # Optional metadata checks if provided
    if "evaluation_mode" in scope:
        em = scope["evaluation_mode"]
        if em != query_metadata.get("evaluation_mode"):
            raise RankingValidationError(
                f"Candidate {candidate_id} scope_binding evaluation_mode mismatch: "
                f"candidate has {em!r}, query expects {query_metadata.get('evaluation_mode')!r}"
            )
    if "active_work_budget" in scope:
        wb = scope["active_work_budget"]
        if wb != query_metadata.get("active_work_budget"):
            raise RankingValidationError(
                f"Candidate {candidate_id} scope_binding active_work_budget mismatch: "
                f"candidate has {wb!r}, query expects {query_metadata.get('active_work_budget')!r}"
            )

    return scope


def _has_snapshot_fact_origin(record, semantic_verified=False):
    """Bounded credential producers require replay and exact positive snapshot evidence."""
    import json

    if (
        not semantic_verified
        or record.get("origin") != "snapshot_fact"
        or record.get("technique_id") not in {"kerberoast_request", "asrep_request"}
    ):
        return False
    evidence = record.get("snapshot_evidence")
    if not isinstance(evidence, list) or not evidence:
        return False
    try:
        facts = [json.loads(item) for item in evidence]
        names = {f["name"] for f in facts}
        required = (
            {"dontreqpreauth"}
            if record["technique_id"] == "asrep_request"
            else {"has_spn", "service_principal_names"}
        )
        return names == required and all(
            f["subject"] == record["target"]
            and f["status"] == "known"
            and bool(f["value"])
            and f["evidence"]
            for f in facts
        )
    except TypeError, ValueError, KeyError:
        return False


def _validate_transition_lineage(
    candidate_id: str,
    lineage: Any,
    cand_actions: list[dict[str, Any]],
    foothold_id: str,
    target_asset_id: str,
    semantic_verified: bool = False,
    state_goal_verified: bool = False,
) -> list[dict[str, Any]]:
    """Validate adapter step lineage used to audit sparse #146 structural evidence."""
    if not isinstance(lineage, list):
        raise TypeError(f"Candidate {candidate_id} transition_lineage must be a list")
    if len(lineage) != len(cand_actions):
        raise RankingValidationError(
            f"Candidate {candidate_id} transition_lineage count ({len(lineage)}) must match "
            f"bound action count ({len(cand_actions)})"
        )

    normalized: list[dict[str, Any]] = []
    for expected_index, record in enumerate(lineage):
        if not isinstance(record, dict):
            raise TypeError(
                f"Candidate {candidate_id} transition_lineage entry {expected_index} "
                "must be an object"
            )
        step_index = record.get("step_index")
        if step_index != expected_index:
            raise RankingValidationError(
                f"Candidate {candidate_id} transition_lineage must cover ordered step "
                f"{expected_index}, got {step_index!r}"
            )
        action = cand_actions[step_index]
        if record.get("action_id") != action.get("action_id"):
            raise RankingValidationError(
                f"Candidate {candidate_id} transition_lineage step {step_index} action binding "
                "does not match bound action"
            )

        technique_id = record.get("technique_id")
        if not isinstance(technique_id, str) or not technique_id.strip():
            raise RankingValidationError(
                f"Candidate {candidate_id} transition_lineage step {step_index} "
                "requires a technique_id"
            )

        actor = record.get("actor")
        source = record.get("source")
        target = record.get("target")
        for field_name, node_id in (("actor", actor), ("source", source), ("target", target)):
            if not is_canonical_node_id(node_id):
                raise RankingValidationError(
                    f"Candidate {candidate_id} transition_lineage step {step_index} has invalid "
                    f"{field_name} {node_id!r}"
                )
        if action.get("actor_id") != actor:
            raise RankingValidationError(
                f"Candidate {candidate_id} transition_lineage step {step_index} actor "
                "does not match bound action"
            )
        if action.get("target_id") != target:
            raise RankingValidationError(
                f"Candidate {candidate_id} transition_lineage step {step_index} target "
                "does not match bound action"
            )
        if record.get("status") != "applicable":
            raise RankingValidationError(
                f"Candidate {candidate_id} transition_lineage step {step_index} must preserve "
                "an applicable transition"
            )

        edge_id = record.get("edge_id")
        derived_from_step = record.get("derived_from_step")
        origin = record.get("origin")
        if edge_id is None:
            if derived_from_step is None:
                if origin != "initial_attack_state" and not _has_snapshot_fact_origin(
                    record, semantic_verified
                ):
                    raise RankingValidationError(
                        f"Candidate {candidate_id} transition_lineage step {step_index} without "
                        "a parent must originate from initial_attack_state"
                    )
            elif (
                type(derived_from_step) is not int
                or derived_from_step < 0
                or derived_from_step >= step_index
                or origin != "derived_transition"
            ):
                raise RankingValidationError(
                    f"Candidate {candidate_id} transition_lineage step {step_index} has invalid "
                    "derived transition origin"
                )
        else:
            if not CANONICAL_EDGE_ID_PATTERN.fullmatch(edge_id):
                raise RankingValidationError(
                    f"Candidate {candidate_id} transition_lineage step {step_index} has invalid "
                    f"canonical edge_id {edge_id!r}"
                )
            if derived_from_step is not None or origin != "observed_edge":
                raise RankingValidationError(
                    f"Candidate {candidate_id} transition_lineage step {step_index} observed "
                    "edge must use origin='observed_edge' and derived_from_step=null"
                )
            declared_edge = action.get("edge_id")
            if declared_edge is not None and declared_edge != edge_id:
                raise RankingValidationError(
                    f"Candidate {candidate_id} transition_lineage step {step_index} edge "
                    f"{edge_id!r} does not match bound action edge_id {declared_edge!r}"
                )

        rbcd_binding = record.get("rbcd_binding")
        if rbcd_binding is not None:
            if not isinstance(rbcd_binding, dict):
                raise RankingValidationError(
                    f"Candidate {candidate_id} transition_lineage step {step_index} "
                    "has invalid rbcd_binding"
                )

        normalized.append(dict(record))

    if normalized:
        if normalized[0]["actor"] != foothold_id and not semantic_verified:
            raise RankingValidationError(
                f"Candidate {candidate_id} transition_lineage first actor must match foothold "
                f"{foothold_id!r}"
            )
        if normalized[-1]["target"] != target_asset_id and not state_goal_verified:
            raise RankingValidationError(
                f"Candidate {candidate_id} transition_lineage final target must match "
                f"target_asset_id {target_asset_id!r}"
            )
    return normalized


def validate_candidate_envelope(
    candidate: Any,
    decoded_query: dict[str, Any],
    *,
    semantic_binding=None,
) -> dict[str, Any]:
    """Fail-closed validation boundary for a single CandidateEnvelope before replay.

    Enforces:
    - Valid non-empty string candidate_id.
    - Explicit fixed-query scope binding matching active query metadata.
    - Canonical target_asset_id matching impact assessments and target_goal if specified.
    - Explicit bound_action_ids referencing declared bound actions.
    - Target asset reachability on declared action sequence or foothold (step 0).
    - Authoritative layer classification for candidate required_predicates.
    - Consistency of work_packets if supplied.
    - Structural route auditability and invariants:
      * non-zero step candidates require auditable routes;
      * unique non-empty route_ids;
      * canonical node IDs and edge IDs;
      * len(node_ids) == len(edge_ids) + 1;
      * len(provenance_locators) == len(edge_ids);
      * 1:1 action edge alignment when actions declare edge_id;
      * zero-step route: node_ids == [foothold], edge_ids == [], provenance_locators == [].
    """
    if not isinstance(candidate, dict):
        raise TypeError(f"Candidate envelope must be a dictionary, got {type(candidate)!r}")

    candidate_id = candidate.get("candidate_id")
    if not isinstance(candidate_id, str) or not candidate_id.strip():
        raise TypeError(f"Candidate candidate_id must be a non-empty string, got {candidate_id!r}")

    from src.engine.ranking.verification import SemanticReplayBinding

    query_meta = decoded_query["query_metadata"]
    semantic_verified = isinstance(
        semantic_binding, SemanticReplayBinding
    ) and semantic_binding.matches(candidate, query_meta)
    if query_meta.get("semantic_goal") is not None and candidate.get("state_goal_binding") is None:
        raise RankingValidationError("Declared semantic goal requires its typed state-goal binding")
    if candidate.get("state_goal_binding") is not None and not semantic_verified:
        raise RankingValidationError("State-goal binding requires native semantic replay")
    state_goal_verified = semantic_verified and candidate.get("state_goal_binding") is not None
    # Credential and delegation extension JSON is not an authoritative
    # initial-state or snapshot root.
    from src.engine.semantics.credentials import OWNERS
    from src.engine.semantics.rbcd import OWNERS as RBCD_OWNERS

    if (
        any(
            record.get("technique_id") in (OWNERS | RBCD_OWNERS)
            for record in (candidate.get("transition_lineage") or [])
            if isinstance(record, dict)
        )
        and not semantic_verified
    ):
        raise RankingValidationError("credential transitions require verified semantic replay")

    foothold_id = query_meta["foothold_node_id"]

    # 1. Enforce fixed query scope binding
    scope_binding = validate_scope_binding(
        candidate.get("scope_binding"),
        query_metadata=query_meta,
        candidate_id=candidate_id,
    )

    # 2. Canonical target asset validation
    target_asset_id = candidate.get("target_asset_id")
    if not isinstance(target_asset_id, str) or not target_asset_id.strip():
        raise TypeError(f"Candidate {candidate_id} target_asset_id must be a non-empty string")
    if not is_canonical_node_id(target_asset_id):
        raise RankingValidationError(
            f"Candidate {candidate_id} invalid target_asset_id: {target_asset_id!r}"
        )
    if target_asset_id not in decoded_query["target_impact_assessments"]:
        raise RankingValidationError(
            f"Candidate {candidate_id} target asset {target_asset_id!r} not in assessments"
        )

    # Check against target_goal if specified
    target_goal = query_meta.get("target_goal", {})
    goal_target = target_goal.get("target_asset_id")
    if goal_target and goal_target != target_asset_id:
        raise RankingValidationError(
            f"Candidate {candidate_id} target_asset_id {target_asset_id!r} does not match "
            f"target_goal target_asset_id {goal_target!r}"
        )

    # Check target impact success event against target_goal if specified
    impact_rec = decoded_query["target_impact_assessments"][target_asset_id]
    assessment_event = impact_rec.get("success_event")
    if not isinstance(assessment_event, str) or not assessment_event.strip():
        raise RankingValidationError(
            f"Target impact assessment for {target_asset_id!r} is missing required non-empty "
            "success_event"
        )
    goal_event = target_goal.get("success_event")
    if goal_event:
        if assessment_event != goal_event:
            raise RankingValidationError(
                f"Target impact assessment success_event {assessment_event!r} "
                f"does not match target_goal success_event {goal_event!r}"
            )

    # 3. Bound actions validation
    bound_action_ids = candidate.get("bound_action_ids")
    if bound_action_ids is None:
        raise RankingValidationError(
            f"Candidate {candidate_id} must explicitly specify bound_action_ids; "
            "automatic inference from work packets is disallowed."
        )
    if not isinstance(bound_action_ids, list):
        raise TypeError(f"Candidate {candidate_id} bound_action_ids must be a list")

    actions_catalog = {act["action_id"]: act for act in decoded_query["bound_actions"]}
    cand_actions = []
    for aid in bound_action_ids:
        if not isinstance(aid, str) or not aid.strip():
            raise TypeError(
                f"Candidate {candidate_id} bound_action_ids elements must be non-empty strings"
            )
        if aid not in actions_catalog:
            raise RankingValidationError(
                f"Candidate {candidate_id} references unknown action: {aid!r}"
            )
        cand_actions.append(actions_catalog[aid])

    # Target reachability on declared actions
    if cand_actions:
        initial_action_targets = {act["target_id"] for act in cand_actions}
        if target_asset_id not in initial_action_targets and not state_goal_verified:
            raise RankingValidationError(
                f"Candidate {candidate_id} target_asset_id {target_asset_id!r} is not reached "
                f"by bound actions"
            )
    else:
        if target_asset_id != foothold_id:
            raise RankingValidationError(
                f"Candidate {candidate_id} target_asset_id {target_asset_id!r} is not reached "
                f"by initial foothold"
            )

    # 4. Required predicates validation
    predicate_layers = decoded_query.get("predicate_layers") or dict(
        decoded_query["facts_ledger"].get("predicate_layers", {})
    )
    cand_required = candidate.get("required_predicates", [])
    if not isinstance(cand_required, list):
        raise TypeError(f"Candidate {candidate_id} required_predicates must be a list")
    for req in cand_required:
        if not isinstance(req, str) or not req.strip():
            raise TypeError(
                f"Candidate {candidate_id} required_predicates elements must be non-empty strings"
            )
        if req not in predicate_layers:
            raise RankingValidationError(
                f"Missing authoritative layer classification for predicate {req!r} in "
                f"candidate {candidate_id!r} required_predicates: authoritative layer must be "
                f"explicitly declared in predicate_layers or facts_ledger"
            )

    # 5. Work packets reconciliation if declared
    if "work_packets" in candidate:
        cand_raw_packets = candidate["work_packets"]
        if not isinstance(cand_raw_packets, list):
            raise TypeError(f"Candidate {candidate_id} work_packets must be a list")
        initial_canonical_packets: list[tuple[str, ...]] = []
        for act in cand_actions:
            units = act.get("referenced_work_unit_ids", [])
            if units:
                initial_canonical_packets.append(tuple(units))
            elif act.get("is_passive_closure"):
                initial_canonical_packets.append(())
        if not initial_canonical_packets:
            initial_canonical_packets = [()]
        parsed_cand_packets = [tuple(p) for p in cand_raw_packets]
        if parsed_cand_packets != initial_canonical_packets:
            raise RankingValidationError(
                f"Candidate {candidate_id} work_packets {parsed_cand_packets!r} do not match "
                "authoritative work packets derived from bound_action_ids "
                f"{initial_canonical_packets!r}"
            )

    # 6. Structural route auditability & integrity invariants
    raw_transition_lineage = candidate.get("transition_lineage")
    transition_lineage = (
        _validate_transition_lineage(
            candidate_id,
            raw_transition_lineage,
            cand_actions,
            foothold_id,
            target_asset_id,
            semantic_verified,
            state_goal_verified,
        )
        if raw_transition_lineage is not None
        else None
    )
    observed_lineage_steps = (
        {
            record["step_index"]: record
            for record in transition_lineage
            if record.get("edge_id") is not None
        }
        if transition_lineage is not None
        else {}
    )
    covered_observed_steps: list[int] = []

    structural_routes = candidate.get("structural_routes")
    if structural_routes is None:
        structural_routes = []
    if not isinstance(structural_routes, list):
        raise TypeError(f"Candidate {candidate_id} structural_routes must be a list")

    if cand_actions and not structural_routes:
        raise RankingValidationError(
            f"Candidate {candidate_id} has executable action sequence "
            f"({len(cand_actions)} actions) but no auditable structural_routes"
        )

    seen_route_ids: set[str] = set()
    for r_idx, r in enumerate(structural_routes):
        if not isinstance(r, dict):
            raise TypeError(
                f"Candidate {candidate_id} structural_routes entry {r_idx} must be an object"
            )

        route_id = r.get("route_id")
        if not isinstance(route_id, str) or not route_id.strip():
            raise RankingValidationError(
                f"Candidate {candidate_id} structural_routes entry {r_idx} "
                "route_id must be a non-empty string"
            )
        if route_id in seen_route_ids:
            raise RankingValidationError(
                f"Duplicate route_id detected in candidate {candidate_id}: {route_id!r}"
            )
        seen_route_ids.add(route_id)

        node_ids = r.get("node_ids")
        edge_ids = r.get("edge_ids")
        locators = r.get("provenance_locators")

        if not isinstance(node_ids, list):
            raise TypeError(f"Candidate {candidate_id} route {route_id!r} node_ids must be a list")
        if not isinstance(edge_ids, list):
            raise TypeError(f"Candidate {candidate_id} route {route_id!r} edge_ids must be a list")
        if not isinstance(locators, list):
            raise TypeError(
                f"Candidate {candidate_id} route {route_id!r} provenance_locators must be a list"
            )

        for nid in node_ids:
            if not is_canonical_node_id(nid):
                raise RankingValidationError(
                    f"Candidate {candidate_id} route {route_id!r} node {nid!r} "
                    "not a valid canonical node ID"
                )
        for eid in edge_ids:
            if not CANONICAL_EDGE_ID_PATTERN.match(eid):
                raise RankingValidationError(
                    f"Candidate {candidate_id} route {route_id!r} edge {eid!r} "
                    "does not match ^sha256:[0-9a-f]{64}$"
                )
        for loc in locators:
            if not isinstance(loc, str) or not loc.strip():
                raise RankingValidationError(
                    f"Candidate {candidate_id} route {route_id!r} "
                    "provenance locator must be a non-empty string"
                )

        semantic_lineage = r.get("semantic_lineage")
        if semantic_lineage is not None:
            if not isinstance(semantic_lineage, list):
                raise TypeError(
                    f"Candidate {candidate_id} route {route_id!r} semantic_lineage must be a list"
                )
            semantic_indices: list[int] = []
            for lineage_idx, record in enumerate(semantic_lineage):
                if not isinstance(record, dict):
                    raise TypeError(
                        f"Candidate {candidate_id} route {route_id!r} semantic_lineage entry "
                        f"{lineage_idx} must be an object"
                    )
                step_index = record.get("step_index")
                action_id = record.get("action_id")
                actor = record.get("actor")
                source = record.get("source")
                target = record.get("target")
                derived_from_step = record.get("derived_from_step")
                origin = record.get("origin")
                if type(step_index) is not int or not 0 <= step_index < len(cand_actions):
                    raise RankingValidationError(
                        f"Candidate {candidate_id} route {route_id!r} semantic_lineage entry "
                        f"{lineage_idx} has invalid step_index"
                    )
                if action_id != cand_actions[step_index].get("action_id"):
                    raise RankingValidationError(
                        f"Candidate {candidate_id} route {route_id!r} semantic_lineage step "
                        f"{step_index} action binding does not match bound action"
                    )
                if record.get("edge_id") is not None:
                    raise RankingValidationError(
                        f"Candidate {candidate_id} route {route_id!r} semantic_lineage step "
                        f"{step_index} must not fabricate a canonical edge"
                    )
                for field_name, node_id in (
                    ("actor", actor),
                    ("source", source),
                    ("target", target),
                ):
                    if not is_canonical_node_id(node_id):
                        raise RankingValidationError(
                            f"Candidate {candidate_id} route {route_id!r} semantic_lineage step "
                            f"{step_index} has invalid {field_name} {node_id!r}"
                        )
                if cand_actions[step_index].get("actor_id") != actor:
                    raise RankingValidationError(
                        f"Candidate {candidate_id} route {route_id!r} semantic_lineage step "
                        f"{step_index} actor does not match bound action"
                    )
                if cand_actions[step_index].get("target_id") != target:
                    raise RankingValidationError(
                        f"Candidate {candidate_id} route {route_id!r} semantic_lineage step "
                        f"{step_index} target does not match bound action"
                    )
                if record.get("status") != "applicable":
                    raise RankingValidationError(
                        f"Candidate {candidate_id} route {route_id!r} semantic_lineage step "
                        f"{step_index} must preserve an applicable transition"
                    )
                if derived_from_step is None:
                    if origin != "initial_attack_state" and not _has_snapshot_fact_origin(
                        record, semantic_verified
                    ):
                        raise RankingValidationError(
                            f"Candidate {candidate_id} route {route_id!r} semantic_lineage step "
                            f"{step_index} without a parent must originate from "
                            "initial_attack_state"
                        )
                elif (
                    type(derived_from_step) is not int
                    or derived_from_step < 0
                    or derived_from_step >= step_index
                    or origin != "derived_transition"
                ):
                    raise RankingValidationError(
                        f"Candidate {candidate_id} route {route_id!r} semantic_lineage step "
                        f"{step_index} has invalid derived transition origin"
                    )
                technique_id = record.get("technique_id")
                if not isinstance(technique_id, str) or not technique_id.strip():
                    raise RankingValidationError(
                        f"Candidate {candidate_id} route {route_id!r} semantic_lineage step "
                        f"{step_index} requires a technique_id"
                    )
                semantic_indices.append(step_index)
            if semantic_indices != sorted(set(semantic_indices)):
                raise RankingValidationError(
                    f"Candidate {candidate_id} route {route_id!r} semantic_lineage step indices "
                    "must be unique and ordered"
                )

        action_step_indices = r.get("action_step_indices")
        if action_step_indices is not None:
            if (
                not isinstance(action_step_indices, list)
                or len(action_step_indices) != len(edge_ids)
                or any(type(step_idx) is not int for step_idx in action_step_indices)
                or action_step_indices != sorted(set(action_step_indices))
                or any(
                    step_idx < 0 or step_idx >= len(cand_actions)
                    for step_idx in action_step_indices
                )
            ):
                raise MappingSyncError(
                    f"Candidate {candidate_id} route {route_id!r} has invalid action_step_indices"
                )

        if cand_actions:
            if len(node_ids) != len(edge_ids) + 1:
                raise RankingValidationError(
                    f"Candidate {candidate_id} route {route_id!r} node count ({len(node_ids)}) "
                    f"must be edge count ({len(edge_ids)}) + 1"
                )
            if len(locators) != len(edge_ids):
                raise RankingValidationError(
                    f"Candidate {candidate_id} route {route_id!r} provenance count "
                    f"({len(locators)}) must match edge count ({len(edge_ids)})"
                )

            if transition_lineage is not None:
                if edge_ids:
                    if action_step_indices is None:
                        raise MappingSyncError(
                            f"Candidate {candidate_id} sparse route {route_id!r} requires "
                            "action_step_indices"
                        )
                    for edge_index, step_index in enumerate(action_step_indices):
                        lineage_record = observed_lineage_steps.get(step_index)
                        if lineage_record is None:
                            raise MappingSyncError(
                                f"Candidate {candidate_id} route {route_id!r} maps edge "
                                f"{edge_ids[edge_index]!r} to non-observed step {step_index}"
                            )
                        if lineage_record["edge_id"] != edge_ids[edge_index]:
                            raise MappingSyncError(
                                f"Candidate {candidate_id} route {route_id!r} edge "
                                f"{edge_ids[edge_index]!r} does not match transition_lineage "
                                f"step {step_index} edge {lineage_record['edge_id']!r}"
                            )
                        if (
                            node_ids[edge_index] != lineage_record["source"]
                            or node_ids[edge_index + 1] != lineage_record["target"]
                        ):
                            raise RankingValidationError(
                                f"Candidate {candidate_id} route {route_id!r} segment endpoints "
                                f"do not match transition_lineage step {step_index}"
                            )
                        covered_observed_steps.append(step_index)
                else:
                    if action_step_indices != []:
                        raise RankingValidationError(
                            f"Candidate {candidate_id} semantic-only route {route_id!r} must "
                            "have empty action_step_indices"
                        )
                    if observed_lineage_steps:
                        raise RankingValidationError(
                            f"Candidate {candidate_id} empty structural route {route_id!r} "
                            "cannot stand in for observed transition evidence"
                        )
                    if node_ids != [foothold_id]:
                        raise RankingValidationError(
                            f"Candidate {candidate_id} semantic-only route {route_id!r} "
                            f"node_ids must be [{foothold_id!r}]"
                        )
            else:
                if node_ids[0] != foothold_id:
                    raise RankingValidationError(
                        f"Candidate {candidate_id} route {route_id!r} has wrong route source: "
                        f"expected foothold {foothold_id!r}, got {node_ids[0]!r}"
                    )
                if edge_ids:
                    if node_ids[-1] != target_asset_id:
                        raise RankingValidationError(
                            f"Candidate {candidate_id} route {route_id!r} has wrong route target: "
                            f"expected target {target_asset_id!r}, got {node_ids[-1]!r}"
                        )
                else:
                    if node_ids != [foothold_id]:
                        raise RankingValidationError(
                            f"Candidate {candidate_id} route {route_id!r} semantic-only node_ids "
                            f"must preserve only the foothold [{foothold_id!r}]"
                        )
                    if action_step_indices != []:
                        raise RankingValidationError(
                            f"Candidate {candidate_id} route {route_id!r} semantic-only path must "
                            "have empty action_step_indices because it has no structural edges"
                        )
                    if not semantic_lineage or len(semantic_lineage) != len(cand_actions):
                        raise RankingValidationError(
                            f"Candidate {candidate_id} route {route_id!r} has no structural "
                            "edges; explicit semantic_lineage for every action is required"
                        )
                    if [record["step_index"] for record in semantic_lineage] != list(
                        range(len(cand_actions))
                    ):
                        raise RankingValidationError(
                            f"Candidate {candidate_id} route {route_id!r} semantic-only lineage "
                            "must cover every bound action in order"
                        )
                    if (
                        semantic_lineage[-1]["target"] != target_asset_id
                        and not state_goal_verified
                    ):
                        raise RankingValidationError(
                            f"Candidate {candidate_id} route {route_id!r} semantic-only lineage "
                            f"does not reach target {target_asset_id!r}"
                        )
        else:
            if edge_ids:
                raise RankingValidationError(
                    f"Zero-step candidate {candidate_id} route {route_id!r} "
                    "must have empty edge_ids"
                )
            if locators:
                raise RankingValidationError(
                    f"Zero-step candidate {candidate_id} route {route_id!r} "
                    "must have empty provenance_locators"
                )
            if node_ids != [foothold_id]:
                raise RankingValidationError(
                    f"Zero-step candidate {candidate_id} route {route_id!r} node_ids must be "
                    f"[{foothold_id!r}], got {node_ids!r}"
                )

    if transition_lineage is not None:
        expected_observed_steps = sorted(observed_lineage_steps)
        if sorted(covered_observed_steps) != expected_observed_steps:
            raise RankingValidationError(
                f"Candidate {candidate_id} structural segments cover observed steps "
                f"{sorted(covered_observed_steps)!r}, expected {expected_observed_steps!r}"
            )
        if len(set(covered_observed_steps)) != len(covered_observed_steps):
            raise RankingValidationError(
                f"Candidate {candidate_id} structural segments duplicate observed step evidence"
            )

    norm_cand = dict(candidate)
    norm_cand["scope_binding"] = scope_binding
    norm_cand["structural_routes"] = structural_routes
    if transition_lineage is not None:
        norm_cand["transition_lineage"] = transition_lineage
    return norm_cand


def validate_candidate_envelopes(
    candidates: Any,
    decoded_query: dict[str, Any],
    *,
    semantic_bindings=None,
) -> list[dict[str, Any]]:
    """Validate a batch of candidate envelopes with uniqueness and fixed query scope binding."""
    if not isinstance(candidates, list):
        raise TypeError(
            f"candidates must be a list of candidate envelopes, got {type(candidates)!r}"
        )

    seen_candidate_ids: set[str] = set()
    validated_candidates: list[dict[str, Any]] = []

    for idx, cand in enumerate(candidates):
        if not isinstance(cand, dict):
            raise TypeError(f"Candidate envelope at index {idx} must be a dictionary")
        cid = cand.get("candidate_id")
        if not isinstance(cid, str) or not cid.strip():
            raise TypeError(
                f"Candidate envelope at index {idx} must have a non-empty string candidate_id"
            )
        if cid in seen_candidate_ids:
            raise RankingValidationError(f"Duplicate candidate_id detected: {cid!r}")
        seen_candidate_ids.add(cid)

        validated_cand = validate_candidate_envelope(
            cand, decoded_query, semantic_binding=(semantic_bindings or {}).get(cid)
        )
        validated_candidates.append(validated_cand)

    return validated_candidates
