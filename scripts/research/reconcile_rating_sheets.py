"""Reconcile independent expert rating sheets according to governance protocol.

This module provides sheet-to-sheet reconciliation, record binding validation,
and descriptive agreement metrics per evidence-rating-governance.md section 3.5.
It reuses existing record reconciliation helpers and Cohen's Kappa calculation
from scripts.research.path_ranking_wire_adapter.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import sys
import tempfile
from datetime import datetime
from fractions import Fraction
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.research.path_ranking_wire_adapter import (  # noqa: E402
    PINNED_WORK_UNIT_CATALOG,
    assert_registry_definition_consistent_with_canonical_id,
    compute_kappa_with_fallback,
    is_canonical_node_id,
    normalize_technique_name,
    parse_canonical_work_unit_id,
    reconcile_expert_ratings,
    validate_authoritative_work_unit_definition,
)

REPORT_SCHEMA_VERSION = "1.1.0"
SHEET_SCHEMA_VERSION = "1.0.0"
GOVERNANCE_VERSION = "1.0.0"
PINNED_CATALOG_VERSION = "1.0.0"
STEP_QUANTITY = "q_i = P(E_i succeeds | foothold, scenario, all previous events succeeded)"
RATING_GROUPS = {
    "impact_ratings": "impact_rating",
    "likelihood_ratings": "conditional_likelihood",
    "effort_ratings": "work_unit_effort",
}
BINDING_FIELDS = {
    "impact": ("target_asset_id", "success_event"),
    "likelihood": (
        "scenario_id",
        "scenario_version",
        "query_id",
        "foothold_node_id",
        "snapshot_id",
        "operational_horizon",
        "target_population",
        "ordered_work_prefix",
        "outcome_action_id",
        "outcome_work_unit_id",
        "conditioning_previous_successes",
        "quantity",
    ),
    "effort": (
        "work_unit_id",
        "technique_name",
        "actor_scope",
        "target_scope",
        "context_scope",
        "boundary_scope",
        "ledger_version",
    ),
}
WORK_UNIT_COMPONENTS = (
    ("technique_name", ("technique_name", "technique")),
    ("actor_scope", ("actor_scope", "actor", "actor_id", "source_node_id")),
    ("target_scope", ("target_scope", "target", "target_id", "target_node_id")),
    ("context_scope", ("context_scope", "context")),
    ("boundary_scope", ("boundary_scope", "boundary")),
    ("ledger_version", ("ledger_version",)),
)
GOVERNANCE_NOTICE = (
    "This report contains descriptive reconciliation metrics and proposed "
    "consensus recommendations for human review. It does not constitute "
    "final parameter acceptance or approval."
)


def compute_catalog_digest() -> str:
    """Compute a deterministic SHA-256 digest of the pinned work unit catalog."""
    serialized = json.dumps(PINNED_WORK_UNIT_CATALOG, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def check_path_aliasing(
    sheet1_path: Path,
    sheet2_path: Path,
    registry_path: Path | None,
    output_path: Path | None,
) -> None:
    """Ensure output file does not alias input sheets or the registry file."""
    s1_res = sheet1_path.resolve()
    s2_res = sheet2_path.resolve()
    if s1_res == s2_res:
        raise ValueError(
            f"Path aliasing detected: sheet1 and sheet2 resolve to same file ({s1_res})"
        )

    if output_path is not None:
        out_res = output_path.resolve()
        if out_res in (s1_res, s2_res):
            raise ValueError(
                f"Path aliasing detected: output file ({out_res}) cannot overwrite an input sheet"
            )
        if registry_path is not None and out_res == registry_path.resolve():
            raise ValueError(
                f"Path aliasing detected: output file ({out_res}) cannot overwrite registry file"
            )


def load_and_hash_json(path: Path, label: str) -> tuple[dict[str, Any], str]:
    """Load JSON from path and compute SHA-256 of raw file bytes."""
    if not path.is_file():
        raise ValueError(f"{label} not found or is not a regular file: {path}")
    raw_bytes = path.read_bytes()
    digest = f"sha256:{hashlib.sha256(raw_bytes).hexdigest()}"
    try:
        data = json.loads(raw_bytes.decode("utf-8"))
    except Exception as err:
        raise ValueError(f"Invalid JSON in {label} ({path}): {err}") from err
    if not isinstance(data, dict):
        raise ValueError(f"Root of {label} ({path}) must be a JSON object")
    return data, digest


def require_text(value: Any, field: str, label: str, *, forbid_pending: bool = False) -> str:
    """Require nonempty text; placeholder restrictions apply to identities/bindings."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Invalid or missing '{field}' in {label}: expected nonempty text")
    if forbid_pending and "PENDING" in value.upper():
        raise ValueError(f"Pending placeholder in '{field}' in {label}")
    return value.strip()


def require_text_list(
    value: Any,
    field: str,
    label: str,
    *,
    nonempty: bool = False,
    forbid_pending: bool = False,
) -> None:
    """Validate list shape and each declared entry, allowing empty pending lists."""
    if not isinstance(value, list) or (nonempty and not value):
        raise ValueError(f"Invalid or missing '{field}' in {label}: expected a list")
    for item in value:
        require_text(item, field, label, forbid_pending=forbid_pending)


def validate_sheet_structure(sheet: dict[str, Any], label: str) -> None:
    """Validate top-level sheet envelope fields."""
    for field in (
        "sheet_id",
        "schema_version",
        "governance_version",
        "status",
        "rater",
        "query_scopes",
    ):
        if field not in sheet:
            raise ValueError(f"Missing mandatory field '{field}' in {label}")

    if not isinstance(sheet["sheet_id"], str) or not sheet["sheet_id"].strip():
        raise ValueError(f"Field 'sheet_id' in {label} must be a non-empty string")
    for field, supported in (
        ("schema_version", SHEET_SCHEMA_VERSION),
        ("governance_version", GOVERNANCE_VERSION),
    ):
        if sheet[field] != supported:
            raise ValueError(f"Unsupported {field} in {label}: expected {supported}")
    if sheet["status"] not in ("pending_independent_rating", "rated"):
        raise ValueError(f"Invalid sheet status in {label}: {sheet['status']!r}")
    rater = sheet["rater"]
    if not isinstance(rater, dict):
        raise ValueError(f"Field 'rater' in {label} must be an object")
    for field in (
        "evaluator",
        "name",
        "competence_and_scope",
        "independence_declaration",
        "rated_at",
    ):
        if field not in rater:
            raise ValueError(f"Missing mandatory rater.{field} in {label}")
        value = rater.get(field)
        if sheet["status"] == "rated" or value is not None:
            require_text(value, f"rater.{field}", label, forbid_pending=field == "evaluator")
    if rater.get("rated_at") is not None:
        try:
            timestamp = rater["rated_at"]
            if "T" not in timestamp:
                raise ValueError("expected date and time")
            datetime.fromisoformat(timestamp)
        except ValueError as err:
            raise ValueError(f"Invalid ISO-8601 rater.rated_at in {label}") from err
    for field in ("organization", "signature"):
        value = rater.get(field)
        if value is not None and not isinstance(value, str):
            raise ValueError(f"Optional rater.{field} in {label} must be text or null")
    if not isinstance(sheet["query_scopes"], list) or not sheet["query_scopes"]:
        raise ValueError(f"Field 'query_scopes' in {label} must be a non-empty list")

    for list_key in RATING_GROUPS:
        if list_key not in sheet:
            raise ValueError(f"Missing rating list '{list_key}' in {label}")
        if not isinstance(sheet[list_key], list):
            raise ValueError(f"Field '{list_key}' in {label} must be a list")


def validate_record_envelopes(sheet: dict[str, Any], label: str) -> None:
    """Validate types, statuses and identity on every record before pairing."""
    rater = sheet["rater"]
    for list_key, record_type in RATING_GROUPS.items():
        for record in sheet[list_key]:
            if not isinstance(record, dict):
                raise ValueError(f"Record in {label}.{list_key} must be an object")
            if record.get("record_type") != record_type:
                raise ValueError(
                    f"Invalid record_type in {label}.{list_key}: expected {record_type}"
                )
            status = record.get("rating_status")
            if status not in ("rated", "unrated"):
                raise ValueError(f"Invalid rating_status in {label}.{list_key}: {status!r}")
            if status == "rated" and sheet["status"] == "pending_independent_rating":
                raise ValueError(
                    f"Sheet status pending_independent_rating with rated record in {label}"
                )
            evaluator = record.get("evaluator")
            if status == "rated" or evaluator is not None:
                identity = require_text(evaluator, "evaluator", label, forbid_pending=True)
                if identity != (rater.get("evaluator") or "").strip():
                    raise ValueError(
                        f"Record evaluator inconsistent with rater.evaluator in {label}"
                    )


def validate_and_align_query_scopes(
    scopes1: list[dict[str, Any]],
    scopes2: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    """Validate query scopes in both sheets and ensure they match exactly."""

    def parse_scope_map(scopes: list[dict[str, Any]], label: str) -> dict[str, dict[str, Any]]:
        s_map: dict[str, dict[str, Any]] = {}
        for sc in scopes:
            if not isinstance(sc, dict):
                raise ValueError(f"Query scope item in {label} must be an object: {sc}")
            qid = sc.get("query_id")
            require_text(qid, "query_id", f"{label} query scope", forbid_pending=True)
            if qid in s_map:
                raise ValueError(f"Duplicate query_id '{qid}' within {label}")
            # Required scope attributes
            for req in (
                "version",
                "scenario_id",
                "scenario_version",
                "snapshot_id",
                "evaluation_mode",
                "work_boundary",
                "foothold_node_id",
                "target_goal",
                "horizon",
            ):
                if req not in sc:
                    raise ValueError(f"Query scope '{qid}' in {label} missing '{req}'")
                if req != "target_goal":
                    require_text(sc[req], req, f"{label} query scope '{qid}'", forbid_pending=True)
            if not is_canonical_node_id(sc["foothold_node_id"]):
                raise ValueError(f"Invalid foothold_node_id in query scope '{qid}'")
            budget = sc.get("active_work_budget")
            if budget is not None and (type(budget) is not int or budget < 0):
                raise ValueError(f"Invalid active_work_budget in query scope '{qid}'")

            tg = sc["target_goal"]
            if not isinstance(tg, dict):
                raise ValueError(f"target_goal in query scope '{qid}' must be an object")
            for tg_req in ("goal_id", "target_asset_id", "success_event"):
                require_text(
                    tg.get(tg_req),
                    tg_req,
                    f"{label} query scope '{qid}' target_goal",
                    forbid_pending=True,
                )
            if not is_canonical_node_id(tg["target_asset_id"]):
                raise ValueError(f"Invalid target_asset_id in query scope '{qid}'")
            require_text_list(tg.get("required_predicates"), "required_predicates", label)

            s_map[qid] = sc
        return s_map

    map1 = parse_scope_map(scopes1, "sheet1")
    map2 = parse_scope_map(scopes2, "sheet2")

    if set(map1.keys()) != set(map2.keys()):
        diff1 = set(map1.keys()) - set(map2.keys())
        diff2 = set(map2.keys()) - set(map1.keys())
        msg = f"Query scope mismatch: sheet1-only: {diff1}, sheet2-only: {diff2}"
        raise ValueError(msg)

    for qid, sc1 in map1.items():
        sc2 = map2[qid]
        for key in (
            "version",
            "scenario_id",
            "scenario_version",
            "snapshot_id",
            "evaluation_mode",
            "work_boundary",
            "foothold_node_id",
            "horizon",
            "active_work_budget",
        ):
            if sc1.get(key) != sc2.get(key):
                raise ValueError(
                    f"Query scope '{qid}' field '{key}' mismatch: "
                    f"'{sc1.get(key)}' != '{sc2.get(key)}'"
                )
        tg1, tg2 = sc1["target_goal"], sc2["target_goal"]
        for key in ("goal_id", "target_asset_id", "success_event", "required_predicates"):
            if tg1.get(key) != tg2.get(key):
                raise ValueError(
                    f"Query scope '{qid}' target_goal field '{key}' mismatch: "
                    f"'{tg1.get(key)}' != '{tg2.get(key)}'"
                )

    return map1


def build_impact_key(record: dict[str, Any]) -> tuple[str, str]:
    """Extract canonical binding key for an impact rating record."""
    target = record.get("target_asset_id")
    event = record.get("success_event")
    if not target or not isinstance(target, str):
        raise ValueError(f"Impact rating missing or invalid target_asset_id: {record}")
    if not event or not isinstance(event, str):
        raise ValueError(f"Impact rating missing or invalid success_event: {record}")
    return (str(target).strip(), str(event).strip())


def validate_impact_record(record: dict[str, Any], label: str) -> None:
    """Validate consequence rating and status for impact record."""
    status = record["rating_status"]
    require_text_list(record.get("affected_business_services"), "affected_business_services", label)
    if status == "rated":
        require_text(record.get("business_rationale"), "business_rationale", label)
        consequence = record.get("consequence_rating")
        valid_impacts = {"Low", "Medium", "High", "Critical"}
        if not isinstance(consequence, str) or consequence not in valid_impacts:
            msg = (
                f"Invalid consequence_rating '{consequence}' in {label}. "
                f"Must be one of {valid_impacts}"
            )
            raise ValueError(msg)
    elif record.get("consequence_rating") is not None:
        raise ValueError(f"Unrated impact in {label} must keep consequence_rating null")


def build_likelihood_key(record: dict[str, Any]) -> tuple[Any, ...]:
    """Extract complete canonical binding key for a conditional likelihood record."""
    scen_id = record.get("scenario_id")
    scen_ver = record.get("scenario_version")
    qid = record.get("query_id")
    foothold = record.get("foothold_node_id")
    snapshot = record.get("snapshot_id")
    horizon = record.get("operational_horizon")
    pop = record.get("target_population")
    prefix = record.get("ordered_work_prefix")
    outcome = record.get("outcome_action_id")

    for field, val in (
        ("scenario_id", scen_id),
        ("scenario_version", scen_ver),
        ("query_id", qid),
        ("foothold_node_id", foothold),
        ("snapshot_id", snapshot),
        ("operational_horizon", horizon),
        ("target_population", pop),
        ("outcome_action_id", outcome),
        ("outcome_work_unit_id", record.get("outcome_work_unit_id")),
    ):
        require_text(val, field, "likelihood binding", forbid_pending=True)

    if not isinstance(prefix, list) or not prefix:
        raise ValueError(f"Likelihood rating missing or empty ordered_work_prefix: {record}")
    require_text_list(
        prefix, "ordered_work_prefix", "likelihood binding", nonempty=True, forbid_pending=True
    )
    if record.get("outcome_work_unit_id") != prefix[-1]:
        raise ValueError(
            "Likelihood outcome_work_unit_id must be the last ordered_work_prefix unit"
        )
    if record.get("conditioning_previous_successes") != prefix[:-1]:
        raise ValueError(
            "Likelihood conditioning_previous_successes must equal prefix before outcome"
        )
    if record.get("quantity") != STEP_QUANTITY:
        raise ValueError(
            "Likelihood quantity must be the schema 1.0.0 step factor under full history"
        )

    return (
        str(scen_id).strip(),
        str(scen_ver).strip() if scen_ver else None,
        str(qid).strip(),
        str(foothold).strip(),
        str(snapshot).strip(),
        str(horizon).strip(),
        str(pop).strip(),
        tuple(str(item).strip() for item in prefix),
        str(outcome).strip() if outcome else None,
        record["outcome_work_unit_id"],
        tuple(record["conditioning_previous_successes"]),
        record["quantity"],
    )


def validate_likelihood_record(record: dict[str, Any], label: str) -> None:
    """Validate likelihood bounds if rated."""
    status = record["rating_status"]
    bounds = record.get("conditional_bounds")
    if not isinstance(bounds, dict) or not {"lower", "upper"} <= bounds.keys():
        raise ValueError(
            f"Missing conditional_bounds object/fields in likelihood record in {label}"
        )
    require_text_list(
        record.get("source_references"), "source_references", label, nonempty=status == "rated"
    )
    if status == "rated":
        require_text(record.get("basis_category"), "basis_category", label, forbid_pending=True)
        require_text(record.get("uncertainty_rationale"), "uncertainty_rationale", label)
        lower_str = bounds.get("lower")
        upper_str = bounds.get("upper")
        if not isinstance(lower_str, str) or not isinstance(upper_str, str):
            raise ValueError(f"Rated likelihood record in {label} has missing bounds: {bounds}")
        try:
            f_lower = Fraction(str(lower_str))
            f_upper = Fraction(str(upper_str))
        except Exception as err:
            msg = f"Invalid fraction in likelihood bounds {bounds} in {label}: {err}"
            raise ValueError(msg) from err
        if not (0 <= f_lower <= f_upper <= 1):
            msg = (
                f"Conditional bounds out of range [0, 1] or inverted: "
                f"[{f_lower}, {f_upper}] in {label}"
            )
            raise ValueError(msg)
    elif any(bounds[key] is not None for key in ("lower", "upper")):
        raise ValueError(f"Unrated likelihood in {label} must keep conditional_bounds null")


def build_effort_key(record: dict[str, Any]) -> str:
    """Extract canonical binding key for a work unit effort record."""
    wuid = record.get("work_unit_id")
    if not wuid or not isinstance(wuid, str) or not wuid.strip():
        raise ValueError(f"Effort rating missing or blank work_unit_id: {record}")
    return str(wuid).strip()


def resolve_work_unit_definition(
    wuid: str,
    work_unit_registry: dict[str, dict[str, Any]] | None,
) -> dict[str, Any]:
    """Resolve immutable definitions for all paths, including pending/unmatched records."""
    require_text(wuid, "work_unit_id", "work unit definition", forbid_pending=True)
    parsed = parse_canonical_work_unit_id(wuid)
    registry = work_unit_registry if work_unit_registry is not None else PINNED_WORK_UNIT_CATALOG
    if parsed is None:
        if wuid not in registry:
            raise ValueError(f"Unknown work_unit_id '{wuid}' not found in registry/catalog")
        definition = validate_authoritative_work_unit_definition(
            wuid, copy.deepcopy(registry[wuid]), source="registry/catalog"
        )
    else:
        definition = validate_authoritative_work_unit_definition(
            wuid, parsed, source="canonical ID"
        )
        if wuid in registry:
            registered = validate_authoritative_work_unit_definition(
                wuid, copy.deepcopy(registry[wuid]), source="registry/catalog"
            )
            assert_registry_definition_consistent_with_canonical_id(wuid, registered, definition)
    for field, aliases in WORK_UNIT_COMPONENTS:
        value = next((definition[k] for k in aliases if k in definition), None)
        require_text(value, field, f"definition '{wuid}'", forbid_pending=True)
    return definition


def validate_effort_metadata_and_rubric(
    record: dict[str, Any],
    work_unit_registry: dict[str, dict[str, Any]] | None,
    label: str,
) -> None:
    """Validate effort record metadata against canonical definition or registry."""
    wuid = record["work_unit_id"]
    definition = resolve_work_unit_definition(wuid, work_unit_registry)
    for field, aliases in WORK_UNIT_COMPONENTS:
        actual = require_text(record.get(field), field, label, forbid_pending=True)
        expected = next((definition[k] for k in aliases if k in definition), None)
        expected = require_text(expected, field, f"definition '{wuid}'", forbid_pending=True)
        if field == "technique_name":
            actual, expected = normalize_technique_name(actual), normalize_technique_name(expected)
        if actual != expected:
            raise ValueError(f"Effort {field} in {label} inconsistent with definition '{wuid}'")

    # Rubric type validation: boolean and float are strictly forbidden
    rub = record.get("rubric_evaluation")
    if not isinstance(rub, dict):
        raise ValueError(f"Missing rubric_evaluation object in effort record '{wuid}' in {label}")

    formula = rub.get("formula")
    if formula != "base":
        raise ValueError(
            f"Unsupported rubric formula '{formula}' in effort record '{wuid}' in {label}; "
            "only 'base' is supported"
        )

    t1 = rub.get("t1_complexity")
    t2 = rub.get("t2_friction")
    cost = rub.get("computed_cost")

    # Exact integer types: bool is an int subclass, and strings are not points.
    if any(value is not None and type(value) is not int for value in (t1, t2, cost)):
        raise TypeError(
            f"Rubric evaluation values must be integer, got types: "
            f"t1={type(t1).__name__}, t2={type(t2).__name__}, cost={type(cost).__name__}"
        )

    status = record["rating_status"]
    if status == "rated":
        require_text(record.get("effort_rationale"), "effort_rationale", label)
        if t1 is None or t2 is None or cost is None:
            raise ValueError(f"Rated effort record '{wuid}' in {label} has missing rubric values")
        if t1 not in {1, 2, 3} or t2 not in {1, 2, 3}:
            raise ValueError(f"T1 and T2 must be in {{1, 2, 3}}, got T1={t1}, T2={t2}")
        if cost not in {0, 1, 2, 3, 4}:
            raise ValueError(f"computed_cost must be in range {{0, 1, 2, 3, 4}}, got {cost}")
        if cost != (t1 + t2 - 2):
            raise ValueError(
                f"Formula consistency check failed: computed_cost {cost} != {t1} + {t2} - 2"
            )
    elif any(value is not None for value in (t1, t2, cost)):
        raise ValueError(f"Unrated effort in {label} must keep rubric values null")

    # Overlap analysis validation
    overlap = record.get("overlap_analysis")
    if not isinstance(overlap, dict):
        raise ValueError(f"Missing overlap_analysis object in effort record '{wuid}' in {label}")
    is_ind = overlap.get("is_independent")
    if status == "rated" and not isinstance(is_ind, bool):
        msg = f"Rated effort record '{wuid}' in {label} must have boolean is_independent"
        raise ValueError(msg)
    if is_ind is not None and not isinstance(is_ind, bool):
        raise ValueError(f"Invalid overlap_analysis.is_independent in {label}")
    for field in ("shared_preparation_tags", "prerequisite_dependencies"):
        require_text_list(
            overlap.get(field),
            f"overlap_analysis.{field}",
            label,
            forbid_pending=field == "prerequisite_dependencies",
        )


def reconcile_sheets(
    sheet1: dict[str, Any],
    sheet2: dict[str, Any],
    sheet1_path: Path,
    sheet2_path: Path,
    sheet1_digest: str,
    sheet2_digest: str,
    registry_path: Path | None = None,
    work_unit_registry: dict[str, dict[str, Any]] | None = None,
    registry_digest: str | None = None,
) -> dict[str, Any]:
    """Perform full sheet reconciliation across impact, likelihood, and effort."""
    validate_sheet_structure(sheet1, "sheet1")
    validate_sheet_structure(sheet2, "sheet2")
    evaluator1 = sheet1["rater"].get("evaluator")
    evaluator2 = sheet2["rater"].get("evaluator")
    if evaluator1 is not None and evaluator1.strip() == (evaluator2 or "").strip():
        raise ValueError("Evaluators must be distinct independent raters at sheet level")
    validate_record_envelopes(sheet1, "sheet1")
    validate_record_envelopes(sheet2, "sheet2")

    # Scope validation
    query_scope_map = validate_and_align_query_scopes(
        sheet1["query_scopes"], sheet2["query_scopes"]
    )

    # Registry provenance metadata
    if registry_path is not None and registry_digest is not None:
        registry_provenance = {
            "source": "file",
            "path": str(registry_path),
            "digest": registry_digest,
            "catalog_size": len(work_unit_registry or {}),
        }
    else:
        catalog_digest = compute_catalog_digest()
        registry_provenance = {
            "source": "pinned_catalog_fallback",
            "module": "scripts.research.path_ranking_wire_adapter.PINNED_WORK_UNIT_CATALOG",
            "version": PINNED_CATALOG_VERSION,
            "digest": f"sha256:{catalog_digest}",
            "catalog_size": len(PINNED_WORK_UNIT_CATALOG),
        }

    # Index records and detect duplicates within each sheet
    def index_records(
        records: list[dict[str, Any]],
        key_fn: Any,
        category: str,
        label: str,
    ) -> dict[Any, dict[str, Any]]:
        indexed: dict[Any, dict[str, Any]] = {}
        for rec in records:
            k = key_fn(rec)
            if k in indexed:
                raise ValueError(f"Duplicate {category} record with key '{k}' in {label}")
            indexed[k] = rec
        return indexed

    impact1 = index_records(sheet1["impact_ratings"], build_impact_key, "impact", "sheet1")
    impact2 = index_records(sheet2["impact_ratings"], build_impact_key, "impact", "sheet2")

    likelihood1 = index_records(
        sheet1["likelihood_ratings"], build_likelihood_key, "likelihood", "sheet1"
    )
    likelihood2 = index_records(
        sheet2["likelihood_ratings"], build_likelihood_key, "likelihood", "sheet2"
    )

    effort1 = index_records(sheet1["effort_ratings"], build_effort_key, "effort", "sheet1")
    effort2 = index_records(sheet2["effort_ratings"], build_effort_key, "effort", "sheet2")

    # Validate records fields
    for rec in sheet1["impact_ratings"]:
        validate_impact_record(rec, "sheet1")
    for rec in sheet2["impact_ratings"]:
        validate_impact_record(rec, "sheet2")

    for rec in sheet1["likelihood_ratings"]:
        validate_likelihood_record(rec, "sheet1")
    for rec in sheet2["likelihood_ratings"]:
        validate_likelihood_record(rec, "sheet2")

    for rec in sheet1["effort_ratings"]:
        validate_effort_metadata_and_rubric(rec, work_unit_registry, "sheet1")
    for rec in sheet2["effort_ratings"]:
        validate_effort_metadata_and_rubric(rec, work_unit_registry, "sheet2")

    # Validate bindings against declared query scopes
    for rec in sheet1["impact_ratings"] + sheet2["impact_ratings"]:
        target = rec["target_asset_id"]
        event = rec["success_event"]
        matched_scope = any(
            sc["target_goal"]["target_asset_id"] == target
            and sc["target_goal"]["success_event"] == event
            for sc in query_scope_map.values()
        )
        if not matched_scope:
            raise ValueError(
                f"Impact rating for asset '{target}' and event '{event}' not in query scopes"
            )

    for rec in sheet1["likelihood_ratings"] + sheet2["likelihood_ratings"]:
        qid = rec["query_id"]
        if qid not in query_scope_map:
            raise ValueError(f"Likelihood rating references undeclared query_id '{qid}'")
        sc = query_scope_map[qid]
        if rec["scenario_id"] != sc["scenario_id"]:
            msg = f"Likelihood scenario '{rec['scenario_id']}' != scope '{sc['scenario_id']}'"
            raise ValueError(msg)
        if rec["scenario_version"] != sc["scenario_version"]:
            msg = (
                f"Likelihood scenario_version '{rec['scenario_version']}' "
                f"!= scope '{sc['scenario_version']}'"
            )
            raise ValueError(msg)
        if rec["foothold_node_id"] != sc["foothold_node_id"]:
            msg = (
                f"Likelihood foothold '{rec['foothold_node_id']}' "
                f"!= scope '{sc['foothold_node_id']}'"
            )
            raise ValueError(msg)
        if rec["snapshot_id"] != sc["snapshot_id"]:
            raise ValueError(
                f"Likelihood snapshot '{rec['snapshot_id']}' != scope '{sc['snapshot_id']}'"
            )
        if rec["operational_horizon"] != sc["horizon"]:
            raise ValueError(
                f"Likelihood horizon '{rec['operational_horizon']}' != scope '{sc['horizon']}'"
            )
        for wuid in rec["ordered_work_prefix"]:
            try:
                definition = resolve_work_unit_definition(wuid, work_unit_registry)
            except ValueError as err:
                raise ValueError(f"Invalid ordered_work_prefix: {err}") from err
            boundary = definition.get("boundary_scope") or definition.get("boundary")
            if boundary != sc["work_boundary"]:
                raise ValueError("Likelihood ordered_work_prefix boundary differs from query scope")

    # Track pairs, unmatched records, and decisions
    reconciled_pairs: dict[str, list[dict[str, Any]]] = {
        "impact": [],
        "likelihood": [],
        "effort": [],
    }
    unmatched_records: dict[str, list[dict[str, Any]]] = {"sheet1": [], "sheet2": []}
    decisions_pending_human_review: list[dict[str, Any]] = []

    def append_pair(category: str, pair: dict[str, Any], r1: dict, r2: dict) -> None:
        # The record helper returns descriptive results, not a lossless audit object.
        pair["raw_records"] = copy.deepcopy([r1, r2])
        pair["binding"].update(
            copy.deepcopy({field: r1[field] for field in BINDING_FIELDS[category]})
        )
        if category == "effort":
            pair["rationales"] = [r1.get("effort_rationale"), r2.get("effort_rationale")]
            pair["overlap_details"] = copy.deepcopy(
                {
                    "sheet1": r1["overlap_analysis"],
                    "sheet2": r2["overlap_analysis"],
                }
            )
        reconciled_pairs[category].append(pair)

    # Helper to check if a record is fully rated
    def is_fully_rated(rec: dict[str, Any]) -> bool:
        return rec["rating_status"] == "rated"

    # 1. Reconcile Impact
    all_impact_keys = sorted(set(impact1.keys()) | set(impact2.keys()))
    for k in all_impact_keys:
        r1 = impact1.get(k)
        r2 = impact2.get(k)
        if r1 is None:
            unmatched_records["sheet2"].append(
                {"record_type": "impact_rating", "binding": k, "record": r2}
            )
            continue
        if r2 is None:
            unmatched_records["sheet1"].append(
                {"record_type": "impact_rating", "binding": k, "record": r1}
            )
            continue

        if is_fully_rated(r1) and is_fully_rated(r2):
            result = reconcile_expert_ratings(r1, r2, work_unit_registry)
            result["binding_key"] = list(k)
            result["pair_status"] = "fully_rated"
            append_pair("impact", result, r1, r2)
            if result.get("proposal_verdict") == "requires_reconciliation_panel":
                decisions_pending_human_review.append(
                    {
                        "record_type": "impact_rating",
                        "binding": result["binding"],
                        "reason": "Impact rating disagreement between independent raters",
                        "raw_ratings": result["raw_ratings"],
                        "raters": result["raters"],
                    }
                )
        else:
            pending_pair = {
                "record_type": "impact_rating",
                "binding_key": list(k),
                "binding": {
                    "target_asset_id": k[0],
                    "target_asset_label": (
                        r1.get("target_asset_label") or r2.get("target_asset_label")
                    ),
                    "success_event": k[1],
                },
                "pair_status": "unreconciled_pending",
                "proposal_verdict": "pending_independent_rating",
                "status": "pending",
                "reasons": [
                    f"sheet1: {r1.get('rating_status', 'unrated')}",
                    f"sheet2: {r2.get('rating_status', 'unrated')}",
                ],
                "raw_ratings": [r1.get("consequence_rating"), r2.get("consequence_rating")],
                "raters": [r1.get("evaluator"), r2.get("evaluator")],
                "rationales": [r1.get("business_rationale"), r2.get("business_rationale")],
            }
            append_pair("impact", pending_pair, r1, r2)
            decisions_pending_human_review.append(
                {
                    "record_type": "impact_rating",
                    "binding": pending_pair["binding"],
                    "reason": "Impact rating pending independent evaluation by human raters",
                    "raters": pending_pair["raters"],
                }
            )

    # 2. Reconcile Likelihood
    all_likelihood_keys = sorted(set(likelihood1.keys()) | set(likelihood2.keys()))
    for k in all_likelihood_keys:
        r1 = likelihood1.get(k)
        r2 = likelihood2.get(k)
        if r1 is None:
            unmatched_records["sheet2"].append(
                {"record_type": "conditional_likelihood", "binding": list(k), "record": r2}
            )
            continue
        if r2 is None:
            unmatched_records["sheet1"].append(
                {"record_type": "conditional_likelihood", "binding": list(k), "record": r1}
            )
            continue

        if is_fully_rated(r1) and is_fully_rated(r2):
            result = reconcile_expert_ratings(r1, r2, work_unit_registry)
            result["pair_status"] = "fully_rated"
            result["question_id"] = r1.get("question_id") or r2.get("question_id")
            append_pair("likelihood", result, r1, r2)
            if result.get("proposal_verdict") == "requires_reconciliation_panel":
                iou_val = result.get("inter_rater_iou")
                decisions_pending_human_review.append(
                    {
                        "record_type": "conditional_likelihood",
                        "question_id": result.get("question_id"),
                        "binding": result["binding"],
                        "reason": f"Likelihood IoU {iou_val} < 0.50 disagreement",
                        "raw_bounds": result["raw_bounds"],
                        "raters": result["raters"],
                    }
                )
            elif result.get("high_epistemic_uncertainty"):
                decisions_pending_human_review.append(
                    {
                        "record_type": "conditional_likelihood",
                        "question_id": result.get("question_id"),
                        "binding": result["binding"],
                        "reason": "High epistemic uncertainty warning (width > 0.50)",
                        "reconciled_bounds": result.get("reconciled_bounds"),
                        "raters": result["raters"],
                    }
                )
        else:
            pending_pair = {
                "record_type": "conditional_likelihood",
                "question_id": r1.get("question_id") or r2.get("question_id"),
                "binding": {
                    "scenario_id": k[0],
                    "scenario_version": k[1],
                    "query_id": k[2],
                    "foothold_node_id": k[3],
                    "snapshot_id": k[4],
                    "operational_horizon": k[5],
                    "target_population": k[6],
                    "ordered_work_prefix": list(k[7]),
                    "outcome_action_id": k[8],
                },
                "pair_status": "unreconciled_pending",
                "proposal_verdict": "pending_independent_rating",
                "status": "pending",
                "reasons": [
                    f"sheet1: {r1.get('rating_status', 'unrated')}",
                    f"sheet2: {r2.get('rating_status', 'unrated')}",
                ],
                "raw_bounds": [
                    (
                        r1.get("conditional_bounds", {}).get("lower"),
                        r1.get("conditional_bounds", {}).get("upper"),
                    ),
                    (
                        r2.get("conditional_bounds", {}).get("lower"),
                        r2.get("conditional_bounds", {}).get("upper"),
                    ),
                ],
                "raters": [r1.get("evaluator"), r2.get("evaluator")],
                "rationales": [r1.get("uncertainty_rationale"), r2.get("uncertainty_rationale")],
            }
            append_pair("likelihood", pending_pair, r1, r2)
            decisions_pending_human_review.append(
                {
                    "record_type": "conditional_likelihood",
                    "question_id": pending_pair.get("question_id"),
                    "binding": pending_pair["binding"],
                    "reason": "Likelihood pending independent evaluation by human raters",
                    "raters": pending_pair["raters"],
                }
            )

    # 3. Reconcile Effort
    all_effort_keys = sorted(set(effort1.keys()) | set(effort2.keys()))
    for k in all_effort_keys:
        r1 = effort1.get(k)
        r2 = effort2.get(k)
        if r1 is None:
            unmatched_records["sheet2"].append(
                {"record_type": "work_unit_effort", "work_unit_id": k, "record": r2}
            )
            continue
        if r2 is None:
            unmatched_records["sheet1"].append(
                {"record_type": "work_unit_effort", "work_unit_id": k, "record": r1}
            )
            continue

        if is_fully_rated(r1) and is_fully_rated(r2):
            result = reconcile_expert_ratings(r1, r2, work_unit_registry)
            result["pair_status"] = "fully_rated"
            result["alias"] = r1.get("alias") or r2.get("alias")

            # Check overlap analysis per governance rules
            o1 = r1.get("overlap_analysis", {})
            o2 = r2.get("overlap_analysis", {})
            ind1 = o1.get("is_independent")
            ind2 = o2.get("is_independent")
            withheld_overlap = (ind1 is False) or (ind2 is False)

            if withheld_overlap:
                result["overlap_status"] = "withheld_unresolved_overlap"
                result["overlap_details"] = {"sheet1": o1, "sheet2": o2}
                result["proposal_verdict"] = "requires_reconciliation_panel"
                result["status"] = "overlap_withheld"
                decisions_pending_human_review.append(
                    {
                        "record_type": "work_unit_effort",
                        "work_unit_id": k,
                        "alias": result["alias"],
                        "reason": "Unresolved effort overlap declared in overlap_analysis",
                        "overlap_details": result["overlap_details"],
                        "raters": result["raters"],
                    }
                )
            else:
                result["overlap_status"] = "independent"
                result["overlap_details"] = {"sheet1": o1, "sheet2": o2}
                if result.get("proposal_verdict") == "requires_reconciliation_panel":
                    decisions_pending_human_review.append(
                        {
                            "record_type": "work_unit_effort",
                            "work_unit_id": k,
                            "alias": result["alias"],
                            "reason": (
                                f"Effort cost delta {result.get('cost_delta')} > 1 disagreement"
                            ),
                            "raw_costs": result["raw_costs"],
                            "raters": result["raters"],
                        }
                    )

            append_pair("effort", result, r1, r2)
        else:
            pending_pair = {
                "record_type": "work_unit_effort",
                "alias": r1.get("alias") or r2.get("alias"),
                "binding": {
                    "work_unit_id": k,
                    "technique_name": r1.get("technique_name") or r2.get("technique_name"),
                    "actor_scope": r1.get("actor_scope") or r2.get("actor_scope"),
                    "target_scope": r1.get("target_scope") or r2.get("target_scope"),
                },
                "pair_status": "unreconciled_pending",
                "proposal_verdict": "pending_independent_rating",
                "status": "pending",
                "reasons": [
                    f"sheet1: {r1.get('rating_status', 'unrated')}",
                    f"sheet2: {r2.get('rating_status', 'unrated')}",
                ],
                "raw_costs": [
                    r1.get("rubric_evaluation", {}).get("computed_cost"),
                    r2.get("rubric_evaluation", {}).get("computed_cost"),
                ],
                "raters": [r1.get("evaluator"), r2.get("evaluator")],
                "rationales": [r1.get("effort_rationale"), r2.get("effort_rationale")],
            }
            append_pair("effort", pending_pair, r1, r2)
            decisions_pending_human_review.append(
                {
                    "record_type": "work_unit_effort",
                    "work_unit_id": k,
                    "alias": pending_pair["alias"],
                    "reason": "Work unit effort pending independent evaluation by human raters",
                    "raters": pending_pair["raters"],
                }
            )

    # Aggregate Metrics Calculation
    # 1. Impact Kappa
    rated_impact_pairs = [
        p for p in reconciled_pairs["impact"] if p.get("pair_status") == "fully_rated"
    ]
    if rated_impact_pairs:
        r1_list = [str(p["raw_ratings"][0]) for p in rated_impact_pairs]
        r2_list = [str(p["raw_ratings"][1]) for p in rated_impact_pairs]
        impact_metrics = compute_kappa_with_fallback(r1_list, r2_list)
        impact_metrics["rated_pair_count"] = len(rated_impact_pairs)
    else:
        impact_metrics = {
            "status": "no_rated_pairs",
            "kappa": None,
            "observed_agreement": None,
            "confusion_matrix": {},
            "small_sample_size_warning": True,
            "rated_pair_count": 0,
        }

    # 2. Likelihood IoU
    rated_lh_pairs = [
        p for p in reconciled_pairs["likelihood"] if p.get("pair_status") == "fully_rated"
    ]
    if rated_lh_pairs:
        ious = [float(p["inter_rater_iou"]) for p in rated_lh_pairs]
        mean_iou = sum(ious) / len(ious)
        high_unc_pairs = [
            p.get("question_id") or p["binding"].get("scenario_id")
            for p in rated_lh_pairs
            if p.get("high_epistemic_uncertainty")
        ]
        likelihood_metrics = {
            "rated_pair_count": len(rated_lh_pairs),
            "mean_inter_rater_iou": mean_iou,
            "high_epistemic_uncertainty_count": len(high_unc_pairs),
            "high_epistemic_uncertainty_items": high_unc_pairs,
        }
    else:
        likelihood_metrics = {
            "rated_pair_count": 0,
            "mean_inter_rater_iou": None,
            "high_epistemic_uncertainty_count": 0,
            "high_epistemic_uncertainty_items": [],
        }

    # 3. Effort Costs
    rated_eff_pairs = [
        p for p in reconciled_pairs["effort"] if p.get("pair_status") == "fully_rated"
    ]
    if rated_eff_pairs:
        deltas = [int(p["cost_delta"]) for p in rated_eff_pairs]
        disagreements = sum(1 for d in deltas if d > 1)
        withheld = sum(1 for p in rated_eff_pairs if p.get("status") == "overlap_withheld")
        effort_metrics = {
            "rated_pair_count": len(rated_eff_pairs),
            "max_cost_delta": max(deltas),
            "mean_cost_delta": sum(deltas) / len(deltas),
            "cost_disagreement_count": disagreements,
            "withheld_overlap_count": withheld,
        }
    else:
        effort_metrics = {
            "rated_pair_count": 0,
            "max_cost_delta": None,
            "mean_cost_delta": None,
            "cost_disagreement_count": 0,
            "withheld_overlap_count": 0,
        }

    # Coverage summary
    s1_imp = len(sheet1["impact_ratings"])
    s1_lh = len(sheet1["likelihood_ratings"])
    s1_eff = len(sheet1["effort_ratings"])
    total_s1 = s1_imp + s1_lh + s1_eff

    s2_imp = len(sheet2["impact_ratings"])
    s2_lh = len(sheet2["likelihood_ratings"])
    s2_eff = len(sheet2["effort_ratings"])
    total_s2 = s2_imp + s2_lh + s2_eff

    matched_count = (
        len(reconciled_pairs["impact"])
        + len(reconciled_pairs["likelihood"])
        + len(reconciled_pairs["effort"])
    )
    unmatched_s1 = len(unmatched_records["sheet1"])
    unmatched_s2 = len(unmatched_records["sheet2"])

    fully_rated_count = len(rated_impact_pairs) + len(rated_lh_pairs) + len(rated_eff_pairs)
    pending_count = matched_count - fully_rated_count

    all_pairs = (
        reconciled_pairs["impact"] + reconciled_pairs["likelihood"] + reconciled_pairs["effort"]
    )
    proposed_consensus_count = sum(
        1 for p in all_pairs if p.get("proposal_verdict") == "proposed_consensus"
    )
    disagreement_count = sum(
        1 for p in all_pairs if p.get("proposal_verdict") == "requires_reconciliation_panel"
    )
    withheld_overlap_count = effort_metrics["withheld_overlap_count"]

    # Processing status determination
    if unmatched_s1 > 0 or unmatched_s2 > 0:
        processing_status = "complete_with_unmatched_records"
    elif pending_count > 0:
        processing_status = "complete_with_pending_records"
    elif disagreement_count > 0 or withheld_overlap_count > 0:
        processing_status = "complete_with_disagreements"
    else:
        processing_status = "complete_all_reconciled"

    for category, index1, index2 in (
        ("impact", impact1, impact2),
        ("likelihood", likelihood1, likelihood2),
        ("effort", effort1, effort2),
    ):
        for label, index, other in (("sheet1", index1, index2), ("sheet2", index2, index1)):
            # Preserve the existing unmatched representation and add a complete object binding.
            items = [
                item
                for item in unmatched_records[label]
                if item["record_type"] == RATING_GROUPS[f"{category}_ratings"]
            ]
            for item, key in zip(items, sorted(index.keys() - other.keys()), strict=True):
                item["record"] = copy.deepcopy(index[key])
                item["validated_binding"] = copy.deepcopy(
                    {field: index[key][field] for field in BINDING_FIELDS[category]}
                )

    snapshots = sorted({sc["snapshot_id"] for sc in query_scope_map.values()})

    return {
        "report_version": REPORT_SCHEMA_VERSION,
        "governance_version": GOVERNANCE_VERSION,
        "processing_status": processing_status,
        "governance_notice": GOVERNANCE_NOTICE,
        "human_acceptance": "pending",
        "input_metadata": {
            label: copy.deepcopy({k: v for k, v in sheet.items() if k not in RATING_GROUPS})
            for label, sheet in (("sheet1", sheet1), ("sheet2", sheet2))
        },
        "input_digests": {
            "sheet1": {
                "sheet_id": sheet1["sheet_id"],
                "path": str(sheet1_path),
                "digest": sheet1_digest,
                "status": sheet1.get("status"),
            },
            "sheet2": {
                "sheet_id": sheet2["sheet_id"],
                "path": str(sheet2_path),
                "digest": sheet2_digest,
                "status": sheet2.get("status"),
            },
        },
        "registry_provenance": registry_provenance,
        "scope_summary": {
            "query_ids": sorted(query_scope_map.keys()),
            "snapshot_id": snapshots[0] if len(snapshots) == 1 else None,
            "snapshot_ids": snapshots,
            "query_scopes": copy.deepcopy(
                [query_scope_map[qid] for qid in sorted(query_scope_map)]
            ),
            "scenarios": sorted({sc["scenario_id"] for sc in query_scope_map.values()}),
        },
        "coverage": {
            "total_sheet1_records": total_s1,
            "total_sheet2_records": total_s2,
            "matched_pairs_count": matched_count,
            "unmatched_sheet1_count": unmatched_s1,
            "unmatched_sheet2_count": unmatched_s2,
            "fully_rated_pairs_count": fully_rated_count,
            "pending_unrated_pairs_count": pending_count,
            "proposed_consensus_count": proposed_consensus_count,
            "disagreement_count": disagreement_count,
            "withheld_overlap_count": withheld_overlap_count,
        },
        "reconciled_pairs": reconciled_pairs,
        "unmatched_records": unmatched_records,
        "aggregate_metrics": {
            "impact": impact_metrics,
            "likelihood": likelihood_metrics,
            "effort": effort_metrics,
        },
        "decisions_pending_human_review": decisions_pending_human_review,
    }


def format_summary_text(report: dict[str, Any]) -> str:
    """Format human-readable summary of the reconciliation report."""
    s1 = report["input_digests"]["sheet1"]
    s2 = report["input_digests"]["sheet2"]
    cov = report["coverage"]
    lines: list[str] = [
        "=" * 70,
        "EXPERT RATING SHEET RECONCILIATION SUMMARY",
        "=" * 70,
        f"Processing Status: {report['processing_status']}",
        f"Report Schema:     {report['report_version']}",
        f"Governance:        {report['governance_version']}",
        "",
        "Input Sheets:",
        f"  Sheet 1: {s1['sheet_id']} ({s1['path']})",
        f"           Digest: {s1['digest']}",
        f"  Sheet 2: {s2['sheet_id']} ({s2['path']})",
        f"           Digest: {s2['digest']}",
        "",
        "Registry Provenance:",
        f"  Source:  {report['registry_provenance']['source']}",
        f"  Digest:  {report['registry_provenance']['digest']}",
        f"  Entries: {report['registry_provenance'].get('catalog_size')}",
        "",
        "Coverage:",
        f"  Total Sheet 1 Records:    {cov['total_sheet1_records']}",
        f"  Total Sheet 2 Records:    {cov['total_sheet2_records']}",
        f"  Matched Pairs:            {cov['matched_pairs_count']}",
        f"  Fully Rated Pairs:        {cov['fully_rated_pairs_count']}",
        f"  Pending/Unrated Pairs:    {cov['pending_unrated_pairs_count']}",
        f"  Proposed Consensus:       {cov['proposed_consensus_count']}",
        f"  Disagreements (Review):   {cov['disagreement_count']}",
        f"  Withheld Overlaps:        {cov['withheld_overlap_count']}",
        f"  Unmatched Sheet 1:        {cov['unmatched_sheet1_count']}",
        f"  Unmatched Sheet 2:        {cov['unmatched_sheet2_count']}",
        "",
        "Aggregate Metrics:",
    ]

    imp = report["aggregate_metrics"]["impact"]
    lines.extend(
        [
            f"  Impact Kappa Status:      {imp['status']}",
            f"  Impact Kappa Value:       {imp['kappa']}",
            f"  Impact Observed Agree:    {imp['observed_agreement']}",
        ]
    )

    lh = report["aggregate_metrics"]["likelihood"]
    lines.extend(
        [
            f"  Likelihood Mean IoU:      {lh['mean_inter_rater_iou']}",
            f"  High Epistemic Warnings:  {lh['high_epistemic_uncertainty_count']}",
        ]
    )

    eff = report["aggregate_metrics"]["effort"]
    lines.extend(
        [
            f"  Effort Max Cost Delta:    {eff['max_cost_delta']}",
            f"  Effort Mean Cost Delta:   {eff['mean_cost_delta']}",
            f"  Effort Disagreements:     {eff['cost_disagreement_count']}",
            f"  Withheld Overlap Count:   {eff['withheld_overlap_count']}",
            "",
            f"Pending Human Review Items: {len(report['decisions_pending_human_review'])}",
            "=" * 70,
            "NOTICE: " + report["governance_notice"],
            "=" * 70,
        ]
    )
    return "\n".join(lines)


def write_report_safely(report: dict[str, Any], output_path: Path) -> None:
    """Atomically write JSON report to destination file."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = None
    try:
        # Exclusive creation prevents collisions and following pre-existing symlinks.
        # Close our handle before replacement so this also works on Windows.
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=output_path.parent,
            prefix=f".{output_path.name}.tmp.",
            delete=False,
        ) as stream:
            temp_path = Path(stream.name)
            json.dump(report, stream, indent=2)
            stream.write("\n")
        temp_path.replace(output_path)
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)


def parse_arguments(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments for rating sheet reconciliation."""
    parser = argparse.ArgumentParser(
        description="Reconcile two independent rating sheets per governance protocol section 3.5."
    )
    parser.add_argument(
        "--sheet1", required=True, type=Path, help="Path to first rating sheet JSON"
    )
    parser.add_argument(
        "--sheet2", required=True, type=Path, help="Path to second rating sheet JSON"
    )
    parser.add_argument(
        "--registry",
        type=Path,
        default=None,
        help="Optional path to work unit registry JSON (defaults to pinned catalog fallback)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Path to write reconciliation report JSON (prints to stdout if omitted)",
    )
    parser.add_argument(
        "--summary",
        action="store_true",
        help="Display summary (sent to stderr if stdout receives JSON report)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint for sheet reconciliation tool."""
    try:
        args = parse_arguments(argv)

        # 1. Path aliasing protection
        check_path_aliasing(args.sheet1, args.sheet2, args.registry, args.output)

        # 2. Load inputs
        s1_data, s1_digest = load_and_hash_json(args.sheet1, "sheet1")
        s2_data, s2_digest = load_and_hash_json(args.sheet2, "sheet2")

        registry_dict: dict[str, dict[str, Any]] | None = None
        registry_digest: str | None = None
        if args.registry is not None:
            reg_raw, reg_dig = load_and_hash_json(args.registry, "work_unit_registry")
            registry_dict = reg_raw
            registry_digest = reg_dig

        # 3. Perform reconciliation
        report = reconcile_sheets(
            sheet1=s1_data,
            sheet2=s2_data,
            sheet1_path=args.sheet1,
            sheet2_path=args.sheet2,
            sheet1_digest=s1_digest,
            sheet2_digest=s2_digest,
            registry_path=args.registry,
            work_unit_registry=registry_dict,
            registry_digest=registry_digest,
        )

        # 4. Handle output
        json_content = json.dumps(report, indent=2)
        if args.output is not None:
            write_report_safely(report, args.output)
            if args.summary:
                print(format_summary_text(report), file=sys.stdout)
        else:
            print(json_content, file=sys.stdout)
            if args.summary:
                print(format_summary_text(report), file=sys.stderr)

        return 0

    except Exception as err:
        print(f"Error: {err}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
