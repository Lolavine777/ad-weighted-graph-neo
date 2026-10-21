"""Export and replay declared reviewed SEAMLESS parameters without altering research inputs.

Declarations are checked, never authenticated as human ratings or acceptance.
Raw UTF-8 inputs, reconciliation proposals and final records remain lossless.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import os
import re
import sys
from datetime import datetime
from fractions import Fraction
from itertools import combinations
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.research import reconcile_rating_sheets as reconciliation  # noqa: E402
from scripts.research.seamless_parameter_validation import (  # noqa: E402
    compute_bundle_digest,
    derive_query_and_candidates_from_bundle,
    verify_parameter_bundle,
)
from src.engine.ranking import PathRankingEngine, scoped_preference  # noqa: E402

GROUPS = {
    "impact": "impact_ratings",
    "likelihood": "likelihood_ratings",
    "effort": "effort_ratings",
}
SOURCES = ("source_a", "source_b")
SCHEMA_VERSION = "1.0.0"
POPULATION = "SEAMLESS v1 declared scenario only"
# Canonical pin is independent of checkout newline bytes; scope changes need an explicit audit.
TEMPLATE_DIGEST = "sha256:0a137817d33c7f22884ca06a19039b10bf75b39bd470a25b73ce5cb40ee58246"
AI_REVIEWED = "human_reviewed_ai_assisted_ratings"
EVIDENCE_CLASSES = ("synthetic_test_only", "declared_independent_ratings", AI_REVIEWED)


def digest(value: Any) -> str:
    """Hash canonical JSON, independent of formatting and object key order."""
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def load_snapshot(path: Path) -> dict[str, Any]:
    """Keep raw bytes as UTF-8 text, including whitespace and CRLF, with their digest."""
    raw = path.read_bytes()
    snapshot = {
        "path": path.as_posix(),
        "raw_utf8": raw.decode("utf-8"),
        "digest": "sha256:" + hashlib.sha256(raw).hexdigest(),
    }
    decode_snapshot(snapshot)
    return snapshot


def decode_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
    raw = snapshot["raw_utf8"].encode("utf-8")
    if snapshot["digest"] != "sha256:" + hashlib.sha256(raw).hexdigest():
        raise ValueError("Input digest mismatch")

    def unique_object(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"Duplicate JSON object key: {key}")
            result[key] = value
        return result

    def invalid_constant(value):
        raise ValueError(f"Nonfinite JSON number: {value}")

    def finite_float(value):
        number = float(value)
        if not math.isfinite(number):
            raise ValueError(f"Nonfinite JSON number: {value}")
        return number

    value = json.loads(
        raw,
        object_pairs_hook=unique_object,
        parse_constant=invalid_constant,
        parse_float=finite_float,
    )
    if not isinstance(value, dict):
        raise ValueError("Input must be a JSON object")
    reconciliation.require_text(snapshot["path"], "path", "input")
    return value


def reconcile_inputs(inputs: dict[str, Any]) -> dict[str, Any]:
    """Recompute #170 report; use original path labels for an exact report comparison."""
    if not {"template", "sheet1", "sheet2"} <= inputs.keys() or inputs.keys() - {
        "template",
        "sheet1",
        "sheet2",
        "registry",
        "report",
        "policy",
        "confirmation",
        "ai_draft",
    }:
        raise ValueError("Invalid source input set")
    data = {k: decode_snapshot(v) for k, v in inputs.items()}
    validate_rating_context(data, inputs)  # #170 itself ignores execution-policy extras.
    registry = data.get("registry")
    report = reconciliation.reconcile_sheets(
        data["sheet1"],
        data["sheet2"],
        inputs["sheet1"]["path"],
        inputs["sheet2"]["path"],
        inputs["sheet1"]["digest"],
        inputs["sheet2"]["digest"],
        inputs["registry"]["path"] if registry is not None else None,
        registry,
        inputs["registry"]["digest"] if registry is not None else None,
    )
    # Reports serialized by #170 contain JSON arrays rather than Python tuples.
    report = json.loads(json.dumps(report))
    if "report" in data and data["report"] != report:
        raise ValueError("Stale or altered reconciliation report")
    return report


def require_resolved_text(value: Any, field: str, label: str) -> str:
    """Reject explicit placeholders, preserving prose and references containing those words."""
    text = reconciliation.require_text(value, field, label)
    if text.casefold() in {"pending", "unresolved", "tbd", "todo"}:
        raise ValueError(f"Unresolved placeholder in '{field}' in {label}")
    return text


def validate_source_class(sheets: list[dict[str, Any]], evidence: str) -> None:
    """Check declared evidence without authenticating people or inferring independence."""
    if evidence not in EVIDENCE_CLASSES:
        raise ValueError("Unsupported evidence_class")
    synthetic = [
        s.get("evidence_class") == "synthetic_test_only"
        or "synthetic" in s.get("sheet_id", "").casefold()
        or "synthetic" in s.get("rater", {}).get("evaluator", "").casefold()
        for s in sheets
    ]
    if evidence == "synthetic_test_only" and not all(synthetic):
        raise ValueError("Synthetic release requires explicitly synthetic source sheets")
    if evidence != "synthetic_test_only" and any(synthetic):
        raise ValueError(
            "Synthetic ratings cannot become declared independent or human-reviewed ratings"
        )
    if evidence == "declared_independent_ratings" and any(
        s.get("evidence_class") not in (None, "declared_independent_ratings")
        or s.get("independent_inter_rater_agreement_eligible") is False
        or s.get("human_agreement_eligible") is False
        or s.get("human_rating_status") == "pending_human_review"
        or s.get("shared_review_confirmation")
        for s in sheets
    ):
        raise ValueError("AI-only or exposed sources cannot become declared independent ratings")
    if evidence == AI_REVIEWED and any(s.get("evidence_class") != AI_REVIEWED for s in sheets):
        raise ValueError("Human-reviewed AI sources must declare confirmed evidence_class")


def validate_policy_record(record: dict[str, Any], policy: dict[str, Any], reference: dict) -> None:
    mechanism = record["outcome_work_unit_id"].split(":", 1)[0]
    expected = policy["by_mechanism"].get(mechanism)
    actual = record.get("execution_policy")
    if (
        expected is None
        or not isinstance(actual, dict)
        or actual != expected
        or record.get("execution_policy_reference") != reference
        or record["operational_horizon"] != policy["operational_horizon"]
        or any(type(v) is not int for v in actual.values())
    ):
        raise ValueError("Likelihood execution policy mismatch")


def validate_rating_context(data: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any] | None:
    """Validate explicit policy/relayed confirmation/archive snapshots before reconciliation."""
    sheets = [data[f"sheet{i}"] for i in (1, 2)]
    reviewed = any(s.get("evidence_class") == AI_REVIEWED for s in sheets)
    has_policy = "policy" in data or any(
        s.get("execution_policy_reference")
        or any("execution_policy" in r for r in s["likelihood_ratings"])
        for s in sheets
    )
    if not reviewed and not has_policy:
        if "confirmation" in data or "ai_draft" in data:
            raise ValueError("Unused confirmation/archive context")
        return None
    if "policy" not in data:
        raise ValueError("Missing execution policy snapshot")
    policy = data["policy"]
    for field in (
        "policy_id",
        "version",
        "operational_horizon",
        "outcome_semantics",
        "uncertainty_basis",
    ):
        require_resolved_text(policy.get(field), field, "execution policy")
    mechanisms = policy.get("by_mechanism")
    if not isinstance(mechanisms, dict) or not mechanisms:
        raise ValueError("Missing execution policy mechanisms")
    for limits in mechanisms.values():
        if (
            not isinstance(limits, dict)
            or set(limits) != {"max_attempts", "deadline_minutes"}
            or any(type(v) is not int or v <= 0 for v in limits.values())
        ):
            raise ValueError("Execution policy limits must be positive integers")
    reference = {
        "policy_id": policy["policy_id"],
        "version": policy["version"],
        "path": Path(inputs["policy"]["path"]).name,
        "sha256": inputs["policy"]["digest"].removeprefix("sha256:"),
    }
    for sheet in sheets:
        if sheet.get("execution_policy_reference") != reference:
            raise ValueError("Sheet execution policy reference/digest mismatch")
        for record in sheet["likelihood_ratings"]:
            validate_policy_record(record, policy, reference)
    context = {"execution_policy": copy.deepcopy(policy), "execution_policy_reference": reference}
    if not reviewed:
        if "confirmation" in data or "ai_draft" in data:
            raise ValueError("Confirmation/archive requires human-reviewed AI evidence class")
        return context
    validate_source_class(sheets, AI_REVIEWED)
    if not {"confirmation", "ai_draft"} <= data.keys():
        raise ValueError("Missing human confirmation or original AI archive snapshot")
    confirmation = data["confirmation"]
    for field in (
        "record_id",
        "recorded_by",
        "confirmation_channel",
        "exposure",
        "final_parameter_dispositions",
    ):
        require_resolved_text(confirmation.get(field), field, "confirmation")
    review_fields = {}
    for field, legacy in (
        ("reviewed_at", "user_message_time"),
        ("review_summary", "user_statement"),
    ):
        if (
            field in confirmation
            and legacy in confirmation
            and confirmation[field] != confirmation[legacy]
        ):
            raise ValueError(f"Conflicting confirmation fields: {field}/{legacy}")
        review_fields[field] = require_resolved_text(
            confirmation.get(field, confirmation.get(legacy)), field, "confirmation"
        )
    try:
        if datetime.fromisoformat(review_fields["reviewed_at"]).tzinfo is None:
            raise ValueError
    except ValueError as err:
        raise ValueError("Confirmation timestamp must include timezone") from err
    if (
        confirmation.get("evidence_class") != AI_REVIEWED
        or confirmation.get("independent_inter_rater_agreement_eligible") is not False
    ):
        raise ValueError("Confirmation must disclose AI review and ineligible independence")
    participants = confirmation.get("participants")
    if (
        not isinstance(participants, list)
        or any(not isinstance(p, str) for p in participants)
        or {p.partition(" (")[0] for p in participants} != {s["rater"]["evaluator"] for s in sheets}
    ):
        raise ValueError("Confirmation participants differ from source raters")
    scope = confirmation.get("scope")
    if not isinstance(scope, list) or not scope:
        raise ValueError("Missing confirmation scope")
    for item in scope:
        require_resolved_text(item, "scope", "confirmation")
    confirmation_name = Path(inputs["confirmation"]["path"]).name
    if policy.get("confirmation_record") != confirmation_name or confirmation.get(
        "execution_policy"
    ) != {"path": reference["path"], "sha256": reference["sha256"]}:
        raise ValueError("Confirmation execution policy digest/reference mismatch")
    originals = confirmation.get("original_inputs", {})
    if set(originals) != {"A", "B"}:
        raise ValueError("Missing original source provenance in confirmation")
    for sheet, source in zip(sheets, ("A", "B"), strict=True):
        if (
            sheet.get("human_rating_status")
            not in ("confirmed_by_user", "confirmed_via_user_relay")
            or sheet.get("human_agreement_eligible") is not True
        ):
            raise ValueError("AI source review must be confirmed by user or via user relay")
        if sheet.get("independent_inter_rater_agreement_eligible") is not False:
            raise ValueError("AI/exposed review must disclose ineligible independence")
        if sheet.get("shared_review_confirmation") != confirmation_name:
            raise ValueError("Sheet confirmation reference mismatch")
        if sheet.get("source_rating_provenance") != originals[source] or not re.fullmatch(
            r"[0-9a-f]{64}", originals[source].get("sha256", "")
        ):
            raise ValueError("Original source provenance mismatch")
    archive = originals["B"]
    if archive.get("path") != Path(inputs["ai_draft"]["path"]).name or archive["sha256"] != inputs[
        "ai_draft"
    ]["digest"].removeprefix("sha256:"):
        raise ValueError("Original AI archive digest/reference mismatch")
    if (
        data["ai_draft"].get("evidence_class") != "ai_assisted_scenario_assessment"
        or data["ai_draft"].get("human_rating_status") != "pending_human_review"
    ):
        raise ValueError("Original AI archive must retain unconfirmed assessment status")
    if sheets[1]["human_rating_status"] != "confirmed_via_user_relay":
        raise ValueError("Archived B assessment adoption must retain user-relayed confirmation")
    expected_confirmation = {
        "record": confirmation_name,
        "channel": "relayed_by_A",
        "scope": "adoption_of_existing_assessment_under_shared_policy",
    }
    for group in GROUPS.values():
        if any(r.get("human_confirmation") != expected_confirmation for r in sheets[1][group]):
            raise ValueError("B record confirmation must match declared relayed adoption")
    # Adoption of the existing assessment cannot silently authorize changed source scores.
    try:
        archive_report = reconciliation.reconcile_sheets(
            data["ai_draft"],
            sheets[1],
            inputs["ai_draft"]["path"],
            inputs["sheet2"]["path"],
            inputs["ai_draft"]["digest"],
            inputs["sheet2"]["digest"],
        )
    except (ValueError, TypeError, KeyError) as err:
        raise ValueError(f"Original AI archive invalid: {err}") from err
    coverage = archive_report["coverage"]
    if (
        coverage["fully_rated_pairs_count"] != 21
        or coverage["unmatched_sheet1_count"]
        or coverage["unmatched_sheet2_count"]
    ):
        raise ValueError("Original AI archive must bind all 21 adopted records")
    value_fields = {
        "impact": ("consequence_rating",),
        "likelihood": ("conditional_bounds",),
        "effort": ("rubric_evaluation", "overlap_analysis"),
    }
    for category, pairs in archive_report["reconciled_pairs"].items():
        for pair in pairs:
            original, adopted = pair["raw_records"]
            if any(original[field] != adopted[field] for field in value_fields[category]):
                raise ValueError("Adoption confirmation does not cover changed AI source values")
    context.update(
        confirmation=copy.deepcopy(confirmation),
        confirmation_digest=inputs["confirmation"]["digest"],
        ai_draft_digest=inputs["ai_draft"]["digest"],
        independent_inter_rater_agreement_eligible=False,
    )
    return context


def validate_release_evidence(record: dict[str, Any], category: str, label: str) -> None:
    """Rated sources and final choices must declare evidence rather than placeholder text."""
    fields = {
        "impact": ("business_rationale",),
        "likelihood": ("basis_category", "uncertainty_rationale"),
        "effort": ("effort_rationale",),
    }
    for field in fields[category]:
        require_resolved_text(record.get(field), field, label)
    if category == "likelihood":
        for reference in record["source_references"]:
            require_resolved_text(reference, "source_references", label)


def require_declaration(decision: dict[str, Any], category: str, pair: dict[str, Any], registry):
    for field in (
        "reviewer_identity",
        "declared_at",
        "rationale",
        "resolution",
        "decision_reference",
    ):
        require_resolved_text(decision.get(field), field, "decision")
    reconciliation.require_text(
        decision["reviewer_identity"], "reviewer_identity", "decision", forbid_pending=True
    )
    timestamp = decision["declared_at"]
    if "T" not in timestamp or datetime.fromisoformat(timestamp).tzinfo is None:
        raise ValueError("declared_at must be an ISO-8601 timestamp with timezone")
    if decision.get("disposition") != "reviewed" or decision.get("binding") != pair["binding"]:
        raise ValueError("Missing reviewed disposition or mismatched full binding")
    record = decision["final_record"]
    if record.get("record_type") != reconciliation.RATING_GROUPS[GROUPS[category]]:
        raise ValueError("Final record_type mismatch")
    if record.get("missing_basis_reasons"):
        raise ValueError("Unresolved final basis")
    if record.get("rating_status") != "rated":
        raise ValueError("Final record must be rated")
    if record.get("evaluator") != decision["reviewer_identity"]:
        raise ValueError("Final evaluator must match declared reviewer_identity")
    for field in reconciliation.BINDING_FIELDS[category]:
        if record.get(field) != pair["binding"][field]:
            raise ValueError(f"Final record binding mismatch: {field}")
    if category == "impact":
        reconciliation.validate_impact_record(record, "final impact")
    elif category == "likelihood":
        reconciliation.build_likelihood_key(record)
        reconciliation.validate_likelihood_record(record, "final likelihood")
    else:
        reconciliation.validate_effort_metadata_and_rubric(record, registry, "final effort")
        if record["overlap_analysis"]["is_independent"] is not True:
            raise ValueError("Final overlap must be resolved and accounted independently")
    validate_release_evidence(record, category, "final record")
    return record


def seal_release(release: dict[str, Any]) -> None:
    """Seal root and both complete projections using the existing digest convention."""
    release["bundle_metadata"]["bundle_digest"] = ""
    release["query_projections"] = {}
    for source in SOURCES:
        query, candidates = derive_query_and_candidates_from_bundle(release, source)
        release["query_projections"][source] = {"query": query, "candidates": candidates}
    release_digest = compute_bundle_digest(release)
    release["bundle_metadata"]["bundle_digest"] = release_digest
    for projection in release["query_projections"].values():
        projection["query"]["query_metadata"]["bundle_digest"] = release_digest


def export_release(inputs: dict[str, Any], decisions: dict[str, Any]) -> dict[str, Any]:
    """Require 21 explicit dispositions and project only chosen values onto an audited template."""
    sheets = [decode_snapshot(inputs[f"sheet{i}"]) for i in (1, 2)]
    if any(s.get("status") != "rated" for s in sheets):
        raise ValueError(
            "Both source sheets must be rated; actual pending sheets cannot be released"
        )
    evidence = decisions.get("evidence_class")
    validate_source_class(sheets, evidence)
    report = reconcile_inputs(inputs)
    template = decode_snapshot(inputs["template"])
    if compute_bundle_digest(template) != TEMPLATE_DIGEST:
        raise ValueError("Research template differs from pinned audited baseline")
    verify_parameter_bundle(template)  # Intentionally retain the research-only verifier unchanged.
    if decisions.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("Unsupported decision schema_version")
    if decisions.get("input_digests") != {k: v["digest"] for k, v in inputs.items()}:
        raise ValueError("Stale decision input digests")
    if decisions.get("report_digest") != digest(report):
        raise ValueError("Stale decision report digest")
    reconciliation.require_text(
        decisions.get("release_id"), "release_id", "release", forbid_pending=True
    )
    if not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", decisions.get("release_version", "")):
        raise ValueError("release_version must have major.minor.patch form")
    for sheet in sheets:
        for field in ("evaluator", "name", "competence_and_scope", "independence_declaration"):
            require_resolved_text(sheet["rater"].get(field), f"rater.{field}", "source sheet")
        for category, group in GROUPS.items():
            for record in sheet[group]:
                if record.get("missing_basis_reasons"):
                    raise ValueError("Unresolved source basis")
                if record["rating_status"] == "rated":
                    validate_release_evidence(record, category, "source record")
    cov = report["coverage"]
    if (
        cov["fully_rated_pairs_count"] != 21
        or cov["unmatched_sheet1_count"]
        or cov["unmatched_sheet2_count"]
    ):
        raise ValueError("Release requires all 21 matched, fully rated pairs")
    # Bind both source scopes to the audited canonical template, with no fallback between scopes.
    template_queries = {
        derive_query_and_candidates_from_bundle(template, s)[0]["query_metadata"][
            "query_id"
        ]: derive_query_and_candidates_from_bundle(template, s)[0]["query_metadata"]
        for s in SOURCES
    }
    scopes = report["scope_summary"]["query_scopes"]
    if {s["query_id"] for s in scopes} != template_queries.keys():
        raise ValueError("Query scope set mismatch")
    for scope in scopes:
        if any(
            scope.get(k) != template_queries[scope["query_id"]][k]
            for k in (
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
            )
        ):
            raise ValueError("Query scope differs from audited template")
    pairs = {
        (cat, digest(pair)): pair
        for cat, rows in report["reconciled_pairs"].items()
        for pair in rows
    }
    declared = {}
    for decision in decisions["decisions"]:
        key = (decision["category"], decision["pair_digest"])
        if key in declared:
            raise ValueError("Duplicate decision")
        if key not in pairs:
            raise ValueError("Extra or stale decision")
        declared[key] = decision
    if declared.keys() != pairs.keys():
        raise ValueError("Missing decision")
    release = copy.deepcopy(template)
    # Research oracles do not belong to a reviewed release with chosen parameters.
    release.pop("analytical_baseline")
    release.pop("sensitivity_thresholds")
    release["release_schema_version"] = SCHEMA_VERSION
    release["bundle_metadata"].update(
        bundle_id=decisions["release_id"], bundle_version=decisions["release_version"]
    )
    release["governance"] = {
        "basis_category": evidence,
        "status": "declared_reviewed_release",
        "human_acceptance": "pending",
        "human_agreement_status": "not_authenticated_by_tool",
        "empirical_calibration_status": "none",
        "raters": [copy.deepcopy(s["rater"]) for s in sheets],
        "publication_status": "not_published",
        "reconciliation": {"report_digest": digest(report)},
    }
    context = validate_rating_context({k: decode_snapshot(v) for k, v in inputs.items()}, inputs)
    if context is not None:
        release["governance"]["rating_context"] = context
    release["provenance"] = {
        "inputs": copy.deepcopy(inputs),
        "report": report,
        "decisions": copy.deepcopy(decisions),
        "decision_digest": digest(decisions),
    }
    registry = decode_snapshot(inputs["registry"]) if "registry" in inputs else None
    consumed = {"impact": set(), "likelihood": set(), "effort": set()}
    for key, pair in pairs.items():
        cat = key[0]
        decision = declared[key]
        r = require_declaration(decision, cat, pair, registry)
        if cat == "likelihood" and context is not None:
            validate_policy_record(
                r, context["execution_policy"], context["execution_policy_reference"]
            )
        reference = {
            "decision_reference": decision["decision_reference"],
            "pair_digest": key[1],
            "rationale": decision["rationale"],
            "resolution": decision["resolution"],
        }
        if cat == "impact":
            target = r["target_asset_id"]
            if target not in release["target_impact_assessments"]:
                raise ValueError("Impact target outside template")
            record = copy.deepcopy(r)
            record.update(missing_basis_reasons=[], reviewed_disposition=reference)
            release["target_impact_assessments"][target] = record
            consumed[cat].add(target)
        elif cat == "effort":
            uid = r["work_unit_id"]
            if uid not in release["work_units_ledger"]:
                raise ValueError("Effort unit outside template")
            old = template["work_units_ledger"][uid]
            rub = r["rubric_evaluation"]
            release["work_units_ledger"][uid] = {
                "applicable_queries": copy.deepcopy(old["applicable_queries"]),
                "alias": old["alias"],
                "rating_status": "rated",
                "overlap_state": "independent",
                "missing_basis_reasons": [],
                "effort": rub["computed_cost"],
                "effort_cost": rub["computed_cost"],
                "computed_cost": rub["computed_cost"],
                "rubric_scores": {
                    "t1": rub["t1_complexity"],
                    "t2": rub["t2_friction"],
                    "formula": rub["formula"],
                    "computed_cost": rub["computed_cost"],
                },
                "effort_rationale": r["effort_rationale"],
                "overlap_analysis": copy.deepcopy(r["overlap_analysis"]),
                "reviewed_disposition": reference,
            }
            consumed[cat].add(uid)
        else:
            if r["target_population"] != POPULATION:
                raise ValueError("Likelihood target_population mismatch")
            matches = [
                i
                for i, row in enumerate(template["conditional_bounds_table"])
                if row["prefix"] == r["ordered_work_prefix"]
                and row["outcome_action_id"] == r["outcome_action_id"]
                and row["applicable_queries"] == [r["query_id"]]
            ]
            if len(matches) != 1 or matches[0] in consumed[cat]:
                raise ValueError("Likelihood mapping mismatch or duplicate")
            i = matches[0]
            row = release["conditional_bounds_table"][i]
            # Replace every numeric/basis field; never inherit research rating evidence.
            row.pop("technical_source", None)
            row.update(
                lower=r["conditional_bounds"]["lower"],
                upper=r["conditional_bounds"]["upper"],
                question_id=r.get("question_id"),
                basis_category=r["basis_category"],
                rationale=r["uncertainty_rationale"],
                source_references=copy.deepcopy(r["source_references"]),
                reviewed_disposition=reference,
                rating_binding={f: copy.deepcopy(r[f]) for f in reconciliation.BINDING_FIELDS[cat]},
            )
            if context is not None:
                row.update(
                    execution_policy=copy.deepcopy(r["execution_policy"]),
                    execution_policy_reference=copy.deepcopy(r["execution_policy_reference"]),
                )
            consumed[cat].add(i)
    if (
        consumed["impact"] != template["target_impact_assessments"].keys()
        or consumed["effort"] != template["work_units_ledger"].keys()
        or consumed["likelihood"] != set(range(len(template["conditional_bounds_table"])))
    ):
        raise ValueError("Incomplete root parameter mapping")
    seal_release(release)
    return release


def verify_release(release: dict[str, Any]) -> dict[str, Any]:
    """Replay declarations and compare every root, cache, source and provenance field."""
    if release.get("release_schema_version") != SCHEMA_VERSION:
        raise ValueError("Unsupported reviewed release schema")
    if release["bundle_metadata"]["bundle_digest"] != compute_bundle_digest(release):
        raise ValueError("Release digest mismatch")
    provenance = release["provenance"]
    expected = export_release(provenance["inputs"], provenance["decisions"])
    if release != expected:
        raise ValueError("Release root/projection/provenance differs from replayed declarations")
    return release


def analytical_expectations(
    query: dict[str, Any], candidates: list[dict[str, Any]]
) -> dict[str, Any]:
    """Independent scoped oracle: exact products, persistent work dedup and partial order.

    Only the audited positive template routes are supported. Does not implement search,
    general fact replay, or empirical inference.
    """
    actions = {a["action_id"]: a for a in query["bound_actions"]}
    bounds = {tuple(r["prefix"]): r for r in query["conditional_bounds_table"]}
    scored = {}
    for c in candidates:
        history = []
        lower = upper = Fraction(1)
        for aid in c["bound_action_ids"]:
            a = actions[aid]
            for uid in a["referenced_work_unit_ids"]:
                if uid in history:
                    continue
                history.append(uid)
                row = bounds[tuple(history)]
                lower *= Fraction(row["lower"])
                upper *= Fraction(row["upper"])
        scored[c["candidate_id"]] = {
            "likelihood_interval": [str(lower), str(upper)],
            "effort": sum(query["work_units_ledger"][uid]["effort"] for uid in history),
            "impact": query["target_impact_assessments"][c["target_asset_id"]][
                "consequence_rating"
            ],
            "program": history,
        }
    levels = {"Low": 0, "Medium": 1, "High": 2, "Critical": 3}

    def relation(a, b):
        la, ua = map(Fraction, a["likelihood_interval"])
        lb, ub = map(Fraction, b["likelihood_interval"])
        ia, ib = levels[a["impact"]], levels[b["impact"]]
        if ia == ib and la == ua == lb == ub:
            return (
                "tie" if a["effort"] == b["effort"] else ("a" if a["effort"] < b["effort"] else "b")
            )
        if ia >= ib and la >= ub and (ia > ib or la > ub):
            return "a"
        if ib >= ia and lb >= ua and (ib > ia or lb > ua):
            return "b"
        return "incomparable"

    relations = [
        {"a": a, "b": b, "relation": relation(scored[a], scored[b])}
        for a, b in combinations(sorted(scored), 2)
    ]
    dominated = {
        p["b"] if p["relation"] == "a" else p["a"] for p in relations if p["relation"] in ("a", "b")
    }
    best = min(scored, key=lambda k: (scored[k]["effort"], k))
    return {
        "candidates": scored,
        "pareto_frontier": sorted(scored.keys() - dominated),
        "relations": relations,
        "min_effort": {"best_candidate_id": best, "minimum_effort_value": scored[best]["effort"]},
    }


def evaluate_selected(bundle: dict[str, Any], source: str) -> dict[str, Any]:
    query, candidates = derive_query_and_candidates_from_bundle(bundle, source)
    expected = analytical_expectations(query, candidates)
    execution = PathRankingEngine(version="1.0.0").evaluate(query, candidates)
    actual = execution["roundtrip_result"]
    assessments = {a["candidate_id"]: a for a in execution["assessed_candidates"]}
    actual_relations = [
        {
            "a": p["a"],
            "b": p["b"],
            "relation": scoped_preference(assessments[p["a"]], assessments[p["b"]]),
        }
        for p in expected["relations"]
    ]
    if actual_relations != expected["relations"]:
        raise ValueError("Engine tie/incomparability differs from independent oracle")
    scored = actual["eligible_candidates"]
    if scored.keys() != expected["candidates"].keys():
        raise ValueError("Engine eligibility differs from audited positive template")
    for cid, fields in expected["candidates"].items():
        if any(scored[cid][k] != v for k, v in fields.items()):
            raise ValueError(f"Engine calculation differs from independent oracle: {cid}")
    if actual["pareto_frontier"] != expected["pareto_frontier"] or any(
        actual["min_effort_to_da_baseline"][k] != v for k, v in expected["min_effort"].items()
    ):
        raise ValueError("Engine frontier or separate Min-Effort differs from independent oracle")
    return {"expected": expected, "actual": actual, "actual_relations": actual_relations}


def validate_and_sensitivity(release: dict[str, Any]) -> dict[str, Any]:
    """Validate before execution and run explicit local perturbations on chosen values."""
    verify_release(release)
    baseline = {s: evaluate_selected(release, s) for s in SOURCES}
    probes = []
    # Every step factor, persistent unit and target gets a scoped numeric probe.
    for index, row in enumerate(release["conditional_bounds_table"]):
        probe = copy.deepcopy(release)
        changed = probe["conditional_bounds_table"][index]
        changed["lower"] = str(Fraction(row["lower"]) * Fraction(9, 10))
        changed["upper"] = str(Fraction(row["upper"]) * Fraction(9, 10))
        rationale = "Multiply one full-history step interval by 9/10; local assumption probe"
        if Fraction(row["upper"]) == 0:
            changed["upper"] = "1/100"
            rationale = "Widen a zero-point factor upper bound to 1/100; exploratory boundary probe"
        probes.append(
            (
                "likelihood",
                str(index),
                probe,
                row["applicable_queries"],
                rationale,
            )
        )
    for uid, unit in release["work_units_ledger"].items():
        probe = copy.deepcopy(release)
        changed = probe["work_units_ledger"][uid]
        rub = changed["rubric_scores"]
        score = "t1" if rub["t1"] < 3 else "t2"
        delta = 1 if rub[score] < 3 else -1
        rub[score] += delta
        rub["computed_cost"] += delta
        for field in ("effort", "effort_cost", "computed_cost"):
            changed[field] = rub["computed_cost"]
        probes.append(
            (
                "effort",
                uid,
                probe,
                unit["applicable_queries"],
                "Change one reviewed rubric score by one point within 1..3",
            )
        )
    for target, impact in release["target_impact_assessments"].items():
        probe = copy.deepcopy(release)
        levels = ["Low", "Medium", "High", "Critical"]
        old = levels.index(impact["consequence_rating"])
        probe["target_impact_assessments"][target]["consequence_rating"] = levels[
            old - 1 if old else 1
        ]
        probes.append(
            (
                "impact",
                target,
                probe,
                list(baseline[s]["actual"]["query_id"] for s in SOURCES),
                "Move selected consequence by one ordinal category",
            )
        )
    sensitivity = []
    for category, key, probe, query_ids, rationale in probes:
        probe["governance"].update(
            status="hypothetical_sensitivity_probe", publication_status="not_published"
        )
        probe["sensitivity_probe"] = {
            "category": category,
            "record_key": key,
            "rationale": rationale,
            "selected_release_digest": release["bundle_metadata"]["bundle_digest"],
        }
        seal_release(probe)
        outcomes = {}
        for source in SOURCES:
            if baseline[source]["actual"]["query_id"] not in query_ids:
                continue
            result = evaluate_selected(probe, source)
            before = baseline[source]["expected"]
            after = result["expected"]
            outcomes[source] = {
                "expected_actual": result,
                "frontier_changed": before["pareto_frontier"] != after["pareto_frontier"],
                "relations_changed": before["relations"] != after["relations"],
                "min_effort_changed": before["min_effort"] != after["min_effort"],
            }
        sensitivity.append(
            {
                "category": category,
                "record_key": key,
                "rationale": rationale,
                "query_ids": query_ids,
                "outcomes": outcomes,
            }
        )
    report = {
        "schema_version": SCHEMA_VERSION,
        "release_digest": release["bundle_metadata"]["bundle_digest"],
        "evidence_class": release["governance"]["basis_category"],
        "validation_status": "passed",
        "human_acceptance": "pending",
        "sources": baseline,
        "sensitivity": sensitivity,
        "coverage": {
            "parameter_records_perturbed": len(probes),
            "scope": "three supplied SEAMLESS candidates only",
            "missing_coverage": [
                "global path search",
                "joint/multivariate perturbations",
                "empirical calibration",
                "attack execution",
            ],
        },
    }
    if "rating_context" in release["governance"]:
        report["rating_context"] = copy.deepcopy(release["governance"]["rating_context"])
    report["report_digest"] = digest(report)
    return report


def protect_output(output: Path, inputs: list[Path]) -> None:
    """Reject path, symlink and hardlink aliases before reading or writing."""
    if output.is_symlink():
        raise ValueError("Output symlink is not allowed")
    for path in inputs:
        if output.resolve() == path.resolve() or (
            output.exists() and path.exists() and output.samefile(path)
        ):
            raise ValueError("Output aliases an input")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    export = sub.add_parser("export")
    for name in ("sheet1", "sheet2", "template", "decisions", "output"):
        export.add_argument("--" + name, required=True, type=Path)
    for name in ("registry", "report", "policy", "confirmation", "ai_draft"):
        export.add_argument("--" + name.replace("_", "-"), type=Path)
    validate = sub.add_parser("validate")
    validate.add_argument("--release", type=Path, required=True)
    validate.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "export":
            names = [
                n
                for n in (
                    "sheet1",
                    "sheet2",
                    "template",
                    "registry",
                    "report",
                    "policy",
                    "confirmation",
                    "ai_draft",
                )
                if getattr(args, n)
            ]
            paths = [getattr(args, n) for n in names] + [args.decisions]
            protect_output(args.output, paths)
            if args.sheet1.resolve() == args.sheet2.resolve() or args.sheet1.samefile(args.sheet2):
                raise ValueError("Source sheets alias")
            inputs = {n: load_snapshot(getattr(args, n)) for n in names}
            decisions = decode_snapshot(load_snapshot(args.decisions))
            result = export_release(inputs, decisions)
            verify_release(result)
        else:
            protect_output(args.output, [args.release])
            result = validate_and_sensitivity(decode_snapshot(load_snapshot(args.release)))
        # Preflight the exact writer serialization before replacing any destination.
        # NamedTemporaryFile uses platform newline translation, including CRLF on Windows.
        serialized = (json.dumps(result, indent=2, allow_nan=False) + "\n").replace(
            "\n", os.linesep
        )
        output_digest = "sha256:" + hashlib.sha256(serialized.encode("utf-8")).hexdigest()
        reconciliation.write_report_safely(result, args.output)
        print(json.dumps({"status": "written", "output_digest": output_digest}))
        return 0
    except (
        ValueError,
        TypeError,
        KeyError,
        AttributeError,
        OSError,
        ZeroDivisionError,
        UnicodeError,
        IndexError,
    ) as err:
        print(f"Error: {err}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
