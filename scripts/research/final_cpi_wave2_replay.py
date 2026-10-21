"""Fresh Wave 2 evidence with separate production and synthetic preview ledgers.

The candidate remains pending; CLI repeats verify programs and never add attacks.
Original and supplementary query-program denominators are never pooled.
"""

from __future__ import annotations

import argparse
import copy
import json
from collections import Counter
from fractions import Fraction
from pathlib import Path

from scripts.research import final_cpi_release as release_tool
from scripts.research.final_cpi_adoption_replay import (
    RELEASE,
    execution_identity,
    execution_summary,
    graph_identity,
    load_inputs,
    prepare_case,
)
from scripts.research.final_cpi_coverage import (
    COUNT_FIELDS,
    independent_checks,
    public_check,
    report_case,
    sensitivity,
)
from scripts.research.final_cpi_extension import COHORT
from scripts.research.final_cpi_profiles import (
    HISTORICAL,
    PACKAGE,
    ROOT,
    engineering_copy,
    historical_pins,
    read,
)
from scripts.research.final_cpi_wave2_audit import ADOPTED_NUMERIC, C_ONLY, NEEDS_EVIDENCE
from scripts.research.issue250_public_probe import envelope, save
from src.engine import run_attack_query
from src.engine.query_cli import wire
from src.engine.ranking.resolution_service import canonical_digest
from src.parser.snapshot_facts import graph_digest

PENDING = ROOT / "docs/research/ratings/final-cpi-release-v2/decisions.pending.json"
LOCAL = ROOT / "reports/generated/issue267-wave2-replay-v2"
REPORT = ROOT / "reports/research/issue267-wave2-replay-v2.json"


def candidate_copy(query, graph, pending):
    """Preview only listed dimensions; unknown or withheld authority stays unresolved."""
    candidate, derivative = engineering_copy(query, graph)
    original = query["rating_resolution"]["registries"]
    registries = candidate["rating_resolution"]["registries"]
    taxonomy = {
        row["technique_id"]: row["canonical_class"]
        for row in read(PACKAGE / "taxonomy.json")["actions"]
    }
    for role, dimension in (("effort", "C"), ("likelihood", "P")):
        for index, record in enumerate(original[role]["data"]):
            cls = record["name"] if dimension == "C" else taxonomy[record["outcome_technique"]]
            decision = pending.get("classes", {}).get(cls, {}).get(dimension, {}).get("decision")
            if decision not in ("pending", "adopt"):
                registries[role]["data"][index] = copy.deepcopy(record)
        registries[role] = envelope(registries[role]["data"])
    case_id = query["rating_resolution"]["scope"]["query_id"]
    if pending.get("impacts", {}).get(case_id, {}).get("decision") not in ("pending", "adopt"):
        for role in ("impact", "impact_source"):
            registries[role] = copy.deepcopy(original[role])
    return candidate, derivative


def load_pending(graph, raw_dir):
    pending = read(PENDING)
    expected = release_tool.template_wave2(graph, raw_dir)
    if pending.get("status") != "pending_b_numeric_review" or pending != expected:
        raise ValueError("Replay requires the exact pending Wave 2 proposal")
    return pending


def prepare_queries(group, case, raw_graph, frozen, raw_dir, release, pending):
    query, current, graph, adopted = prepare_case(group, case, raw_graph, frozen, raw_dir, release)
    context = pending.get("contexts", {}).get(case["id"], {}).get("decision")
    preview = (
        not adopted and case["id"] in pending["query_pins"] and context in ("pending", "adopt")
    )
    if preview:
        if canonical_digest(query) != pending["query_pins"][case["id"]]:
            raise ValueError("Candidate exact query/context digest mismatch")
        candidate, derivative = candidate_copy(query, graph, pending)
    else:
        candidate, derivative = current, graph
    return query, current, graph, adopted, candidate, derivative, preview


def report_family_coverage(result):
    """Count returned programs containing each active class; families overlap."""
    taxonomy = {row["technique_id"]: row for row in read(PACKAGE / "taxonomy.json")["actions"]}
    summaries = result.rating_coverage["candidate_summaries"]
    eligible = result.ranking_result["eligible_candidates"]
    families = {}
    for index, path in enumerate(result.search_result.paths, 1):
        cid = f"generated_{index:04d}"
        summary = summaries[cid]
        classes = {
            taxonomy[step.result.request.technique_id]["canonical_class"]
            for step in path.transition_history
            if taxonomy[step.result.request.technique_id]["active"]
        }
        for cls in classes:
            row = families.setdefault(cls, dict.fromkeys(COUNT_FIELDS, 0))
            row["valid_generated"] += 1
            row["conditioned_feasible"] += summary["semantic_status"] == "feasible"
            for field, dimension in (
                ("C_rated", "c_complete"),
                ("P_rated", "p_complete"),
                ("I_rated", "i_complete"),
                ("fully_rated", "numeric_complete"),
            ):
                row[field] += summary[dimension]
            row["Pareto_eligible"] += cid in eligible
    return dict(sorted(families.items()))


def step_blockers(result):
    """Expose native per-action resolution without publishing raw identities."""
    taxonomy = {r["technique_id"]: r for r in read(PACKAGE / "taxonomy.json")["actions"]}

    def rating(record, cls, dimension):
        resolved = record["disposition"] == "rated"
        diagnosis = (
            "resolved"
            if resolved
            else "missing_numeric_basis"
            if dimension == "P" and cls in C_ONLY
            else "recovered_secret_lineage_history_unapproved"
            if cls in NEEDS_EVIDENCE
            else "approved_numeric_context_history_binding_pending"
            if cls in ADOPTED_NUMERIC or dimension == "C" and cls in C_ONLY
            else "context_history_policy_or_basis_gap"
        )
        return {
            "disposition": record["disposition"],
            "value": record.get("cost") if dimension == "C" else record.get("interval"),
            "diagnosis": diagnosis,
            "native_reason_codes": sorted(
                {
                    trace["reason_code"]
                    for trace in record["provider_trace"]
                    if trace.get("reason_code")
                }
            ),
            "lookup_digest": canonical_digest(record["rating_audit"]["lookup_key"]),
            "numeric_basis_class": record["rating_audit"].get("numeric_basis_class"),
        }

    programs = []
    for index, path in enumerate(result.search_result.paths, 1):
        cid = f"generated_{index:04d}"
        detail = result.rating_coverage["candidates"][cid]
        units, prefixes = detail["effort"]["units"], detail["likelihood"]["prefixes"]
        seen, steps = set(), []
        for ordinal, step in enumerate(path.transition_history, 1):
            request = step.result.request
            row = taxonomy[request.technique_id]
            action = {"step": ordinal, "technique": request.technique_id, "active": row["active"]}
            if row["active"]:
                matches = [
                    (uid, record)
                    for uid, record in units.items()
                    if record["rating_audit"]["lookup_key"]["technique"] == request.technique_id
                    and record["rating_audit"]["lookup_key"]["actor_id"] == request.actor
                    and record["rating_audit"]["lookup_key"]["target_id"] == request.target
                    and record["rating_audit"]["lookup_key"]["source_id"] == request.source
                ]
                if len(matches) != 1:
                    raise ValueError("Step-level native work binding is ambiguous")
                uid, effort = matches[0]
                action["C"] = rating(effort, row["canonical_class"], "C")
                action["first_use"] = uid not in seen
                if uid not in seen:
                    seen.add(uid)
                    likelihood = next(p for p in prefixes if p["outcome_unit"] == uid)
                    action["P"] = rating(likelihood, row["canonical_class"], "P")
                    action["P"]["full_active_history_length"] = len(likelihood["prefix"])
                else:
                    action["P"] = {"diagnosis": "shared_work_no_new_success_event"}
            else:
                action["C"] = {"value": 0, "diagnosis": "passive_no_work"}
                action["P"] = {"diagnosis": "passive_no_success_event"}
            steps.append(action)
        impact = detail["impact"]
        programs.append(
            {
                "candidate": cid,
                "semantic_status": result.rating_coverage["candidate_summaries"][cid][
                    "semantic_status"
                ],
                "steps": steps,
                "terminal_I": {
                    "disposition": impact["disposition"],
                    "value": impact["consequence_rating"],
                    "goal_digest": canonical_digest(wire(result.materialized_query.semantic_goal)),
                    "native_reason_code": impact.get("reason_code"),
                },
            }
        )
    attempts = Counter((a.request.technique_id, str(a.status)) for a in result.attempts)
    return {
        "programs": programs,
        "attempts_nonexclusive": [
            {"technique": technique, "status": status, "count": count}
            for (technique, status), count in sorted(attempts.items())
        ],
        "interpretation": "I belongs to the terminal typed goal, not every intermediate action; "
        "attempt counts are not returned-path denominators. Native no-path/goal gaps and "
        "search truncation remain in the case report.",
    }


def evidence_scope(
    group,
    cohort,
    case,
    release,
    pending,
    execution,
    raw_identity,
    graph,
    query,
    current,
    derivative,
    candidate,
    adopted,
    preview,
):
    return {
        "version": "final-cpi-wave2-checkpoint-scope/1.0.0",
        "group": group,
        "case_id": case["id"],
        "cohort_digest": canonical_digest(cohort),
        "case_digest": canonical_digest(case),
        "release_digest": canonical_digest(release),
        "candidate_release_digest": canonical_digest(pending),
        "adoption_applied": adopted,
        "candidate_preview_applied": preview,
        "candidate_authority": "synthetic_test_only" if preview else "current_production",
        "execution_digest": canonical_digest(execution),
        "raw_input_identity": raw_identity,
        "case_graph_identity": graph_identity(graph),
        "candidate_graph_identity": graph_identity(derivative),
        "query_before_release_digest": canonical_digest(query),
        "query_consumed_digest": canonical_digest(current),
        "candidate_query_consumed_digest": canonical_digest(candidate),
    }


def checkpoint(group, case_id, raw_dir, timeout_seconds):
    execution, pins = execution_identity(), historical_pins()
    release = read(RELEASE)
    cohort_path = PACKAGE / "cohort.json" if group == "original" else COHORT
    cohort = read(cohort_path)
    case = next(c for c in cohort["queries"] if c["id"] == case_id)
    raw_graph, frozen = load_inputs(raw_dir)
    raw_identity = graph_identity(raw_graph)
    pending = load_pending(raw_graph, raw_dir)
    projection = read(HISTORICAL / "source-a-graph.json")
    ids = {node["id"] for node in projection["nodes"]}
    canonical = raw_graph.to_canonical()
    if [n for n in canonical["nodes"] if n["id"] in ids] != projection["nodes"] or [
        e for e in canonical["edges"] if e["source"] in ids and e["target"] in ids
    ] != projection["edges"]:
        raise ValueError("Historical projection is not exactly raw-backed")
    query, current, graph, adopted, candidate, derivative, preview = prepare_queries(
        group, case, raw_graph, frozen, raw_dir, release, pending
    )
    scope = evidence_scope(
        group,
        cohort,
        case,
        release,
        pending,
        execution,
        raw_identity,
        graph,
        query,
        current,
        derivative,
        candidate,
        adopted,
        preview,
    )
    name = group + "." + case_id
    baseline = run_attack_query(query, graph)
    actual, current_public = public_check(
        current, graph, LOCAL, name + ".current", "seamless", timeout_seconds=timeout_seconds
    )
    if preview:
        potential, candidate_public = public_check(
            candidate,
            derivative,
            LOCAL,
            name + ".candidate",
            "synthetic",
            timeout_seconds=timeout_seconds,
        )
    else:
        potential, candidate_public = (
            actual,
            {
                "same_current_production_execution": True,
                "current_public_verification_reference": name + ".current",
            },
        )
        save(LOCAL / (name + ".candidate.query.json"), candidate)
    if wire(actual.paths) != wire(baseline.paths) or wire(potential.paths) != wire(actual.paths):
        raise ValueError("Numeric wiring changed generated program identities")
    audits = []
    for detail in actual.rating_coverage["candidates"].values():
        audits.extend(u["rating_audit"] for u in detail["effort"]["units"].values())
        audits.extend(u["rating_audit"] for u in detail["likelihood"]["prefixes"])
        if detail["impact"].get("rating_audit"):
            audits.append(detail["impact"]["rating_audit"])
    reviewed = [
        audit for audit in audits if audit.get("review_reference") == release["review"]["reference"]
    ]
    if adopted and actual.ranking_result["eligible_candidates"] and not reviewed:
        raise ValueError("Missing actual Wave 1 adoption provenance")
    if any(audit.get("numeric_basis_class") != "estimated_expert_scenario" for audit in reviewed):
        raise ValueError("Actual Wave 1 adoption provenance mislabeled")
    row = {
        "evidence_scope": scope,
        "execution_identity": execution_summary(execution),
        "query_id": case_id,
        "supported_cohort": case["supported_cohort" if group == "original" else "supported"],
        "numeric_adoption_applied": adopted,
        "candidate_preview_applied": preview,
        "candidate_authority": scope["candidate_authority"],
        "query_before_release_digest": canonical_digest(query),
        "query_consumed_digest": canonical_digest(current),
        "candidate_query_consumed_digest": canonical_digest(candidate),
        "baseline_pending": report_case(baseline),
        "current_production": report_case(actual),
        "candidate_engineering_preview": report_case(potential),
        "step_level_blockers": {
            "current_production": step_blockers(actual),
            "candidate_engineering_preview": step_blockers(potential),
        },
        "family_coverage_nonexclusive": {
            "denominator_unit": "returned query-programs containing the active canonical class",
            "interpretation": "families overlap; never sum them or infer per-event P calibration",
            "current_production": report_family_coverage(actual),
            "candidate_engineering_preview": report_family_coverage(potential),
        },
        "programs_unchanged_by_numeric_wiring": True,
        "public_verification": {
            "current_production": current_public,
            "candidate_engineering_preview": candidate_public,
        },
        "independent_oracle": {
            "current_production": independent_checks(actual),
            "candidate_engineering_preview": independent_checks(potential),
        },
        "actual_review_audit_entries": len(reviewed),
        "actual_numeric_basis_classes": sorted(
            {audit["numeric_basis_class"] for audit in reviewed}
        ),
        "graph": {
            "nodes": len(graph.nodes()),
            "edges": len(graph.edges()),
            "is_full_raw": graph is raw_graph,
            "sha256": graph_digest(graph.to_canonical()),
        },
    }
    if group == "original" and case_id == "source-a-projection":
        test_query, test_graph = engineering_copy(current, graph)
        row["sensitivity"] = sensitivity(test_query, test_graph)
        row["sensitivity"]["authority"] = "synthetic_test_only; query-local controls only"
        row["sensitivity"]["baseline_query_digest"] = canonical_digest(test_query)
        row["sensitivity"]["baseline_graph_identity"] = graph_identity(test_graph)
    if historical_pins() != pins or graph_identity(raw_graph) != raw_identity:
        raise ValueError("Frozen history or raw graph changed during replay")
    if execution_identity() != execution:
        raise ValueError("Executable/source changed during replay")
    if read(cohort_path) != cohort or read(RELEASE) != release or read(PENDING) != pending:
        raise ValueError("Cohort/release changed during replay")
    row["historical_files_byte_preserved"] = len(pins)
    save(LOCAL / (name + ".verified.json"), row)
    print(
        json.dumps(
            {
                "group": group,
                "case": case_id,
                "current": row["current_production"]["counts"],
                "candidate": row["candidate_engineering_preview"]["counts"],
            }
        ),
        flush=True,
    )


def aggregate(raw_dir=None):
    execution, release = execution_identity(), read(RELEASE)
    raw_graph, frozen = load_inputs(raw_dir)
    raw_identity = graph_identity(raw_graph)
    pending = load_pending(raw_graph, raw_dir)
    report = {
        "version": "final-cpi-wave2-replay/2.0.0",
        "release_digest": canonical_digest(release),
        "candidate_release_digest": canonical_digest(pending),
        "candidate_release_status": pending["status"],
        "candidate_numeric_authority_adopted": False,
        "review": release["review"],
        "execution_identity": execution,
        "raw_input_identity": raw_identity,
        "groups": {},
        "limitations": [
            "Current production includes only the existing Wave 1 expert scenario decision.",
            "Wave 2 preview is synthetic_test_only and cannot satisfy production acceptance.",
            "Recovery P and recovered-identity activation remain withheld, including in preview.",
            "Original and supplementary query-program denominators remain separate.",
            "Truncated returned samples never establish full generator/global optimum coverage.",
            "Sensitivity covers Source A only; source/remediation contracts remain B-owned.",
        ],
    }
    cohort_pins = {}
    for group, cohort_path, supported_field in (
        ("original", PACKAGE / "cohort.json", "supported_cohort"),
        ("supplementary", COHORT, "supported"),
    ):
        cohort = read(cohort_path)
        cohort_pins[cohort_path] = cohort
        rows, missing = [], []
        for case in cohort["queries"]:
            name = group + "." + case["id"]
            path = LOCAL / (name + ".verified.json")
            if not path.exists():
                missing.append(case["id"])
                continue
            row = read(path)
            query, current, graph, adopted, candidate, derivative, preview = prepare_queries(
                group, case, raw_graph, frozen, raw_dir, release, pending
            )
            expected = evidence_scope(
                group,
                cohort,
                case,
                release,
                pending,
                execution,
                raw_identity,
                graph,
                query,
                current,
                derivative,
                candidate,
                adopted,
                preview,
            )
            if row.get("evidence_scope") != expected or row.get(
                "execution_identity"
            ) != execution_summary(execution):
                raise ValueError("Checkpoint evidence scope mismatch; fresh replay required")
            for kind, consumed, digest_field in (
                ("current", current, "query_consumed_digest"),
                ("candidate", candidate, "candidate_query_consumed_digest"),
            ):
                actual_query = read(LOCAL / (name + "." + kind + ".query.json"))
                if canonical_digest(actual_query) != canonical_digest(consumed) or row.get(
                    digest_field
                ) != canonical_digest(consumed):
                    raise ValueError("Checkpoint " + kind + " consumed query digest mismatch")
            if row.get("query_before_release_digest") != canonical_digest(query):
                raise ValueError("Checkpoint original query digest mismatch")
            if (
                row.get("numeric_adoption_applied") != adopted
                or row.get("candidate_preview_applied") != preview
            ):
                raise ValueError("Checkpoint adoption/preview domain mismatch")
            if row.get("candidate_authority") != expected["candidate_authority"]:
                raise ValueError("Checkpoint candidate authority mismatch")
            if (
                row.get("supported_cohort") != case[supported_field]
                or row.get("query_id") != case["id"]
            ):
                raise ValueError("Checkpoint cohort/query identity mismatch")
            if row.get("graph") != {
                "nodes": len(graph.nodes()),
                "edges": len(graph.edges()),
                "is_full_raw": graph is raw_graph,
                "sha256": expected["case_graph_identity"]["graph_digest"],
            }:
                raise ValueError("Checkpoint graph identity mismatch")
            if not preview and row["candidate_engineering_preview"] != row["current_production"]:
                raise ValueError("Candidate must preserve unchanged current production evidence")
            for kind in ("current_production", "candidate_engineering_preview"):
                counts = row[kind].get("counts", {})
                if (
                    not set(COUNT_FIELDS) <= counts.keys()
                    or any(
                        type(counts[field]) is not int or counts[field] < 0
                        for field in COUNT_FIELDS
                    )
                    or counts["conditioned_feasible"] > counts["valid_generated"]
                    or any(
                        counts[field] > counts["conditioned_feasible"] for field in COUNT_FIELDS[2:]
                    )
                    or counts["fully_rated"]
                    > min(counts[field] for field in ("C_rated", "P_rated", "I_rated"))
                    or counts["Pareto_eligible"] > counts["fully_rated"]
                ):
                    raise ValueError("Checkpoint count accounting mismatch")
                public = row.get("public_verification", {}).get(kind, {})
                if kind == "candidate_engineering_preview" and not preview:
                    if (
                        public.get("same_current_production_execution") is not True
                        or public.get("current_public_verification_reference") != name + ".current"
                    ):
                        raise ValueError("Checkpoint public verification reference mismatch")
                    continue
                if (
                    public.get("two_CLI_exit_codes") != [0, 0]
                    or any(type(code) is not int for code in public["two_CLI_exit_codes"])
                    or any(
                        public.get(field) is not True
                        for field in (
                            "two_process_equal",
                            "API_CLI_semantic_ranking_coverage_programs_equal",
                            "orchestration_search_ranking_programs_equal",
                        )
                    )
                ):
                    raise ValueError("Checkpoint public verification failed or missing")
            rows.append(row)
        group_report = {
            "cohort_digest": canonical_digest(cohort),
            "complete_replay": not missing,
            "missing_queries": missing,
            "cases": rows,
            "denominator_unit": (
                "query-program occurrences per frozen cohort; predeclared projection/raw overlap "
                "retained; CLI repeats verify execution and never enter the denominator"
            ),
        }
        for kind in ("current_production", "candidate_engineering_preview"):
            all_counts, supported_counts, raw_counts = Counter(), Counter(), Counter()
            for row in rows:
                all_counts.update(row[kind]["counts"])
                if row["supported_cohort"]:
                    supported_counts.update(row[kind]["counts"])
                if row["graph"]["is_full_raw"]:
                    raw_counts.update(row[kind]["counts"])
            feasible = supported_counts["conditioned_feasible"]
            ratio = Fraction(supported_counts["fully_rated"], feasible) if feasible else None
            group_report[kind] = {
                "authority": "current_production"
                if kind == "current_production"
                else "synthetic_test_only_preview_with_current_production_retained",
                "production_accepted_coverage": kind == "current_production",
                "all_completed_query_counts": dict(all_counts),
                "supported_completed_query_counts": dict(supported_counts),
                "manifest_verified_full_raw_completed_query_counts": dict(raw_counts),
                "supported_returned_sample_full_fraction": str(ratio)
                if ratio is not None
                else None,
                "meets_80_percent_on_complete_supported_returned_sample": (
                    kind == "current_production"
                    and not missing
                    and ratio is not None
                    and ratio >= Fraction(4, 5)
                ),
                "full_generator_coverage_established": False,
                "truncated_query_count": sum(row[kind]["truncated"] for row in rows),
                "unrated_query_count": sum(
                    row[kind]["counts"]["conditioned_feasible"] > row[kind]["counts"]["fully_rated"]
                    for row in rows
                ),
            }
        report["groups"][group] = group_report
    if execution_identity() != execution or read(RELEASE) != release or read(PENDING) != pending:
        raise ValueError("Executable/source/release changed during aggregation")
    if graph_identity(raw_graph) != raw_identity or any(
        read(path) != value for path, value in cohort_pins.items()
    ):
        raise ValueError("Raw graph/snapshot/cohort changed during aggregation")
    save(REPORT, report)
    print(
        json.dumps(
            {
                group: {key: value for key, value in row.items() if key != "cases"}
                for group, row in report["groups"].items()
            }
        ),
        flush=True,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--group", choices=("original", "supplementary"))
    parser.add_argument("--case")
    parser.add_argument("--raw-dir", type=Path)
    parser.add_argument("--timeout-seconds", type=int, default=600)
    parser.add_argument("--aggregate", action="store_true")
    args = parser.parse_args()
    if args.raw_dir is None:
        parser.error("--raw-dir is required for manifest-backed evidence scope")
    if args.aggregate:
        aggregate(args.raw_dir)
    else:
        if not args.group or not args.case:
            parser.error("--group and --case are required")
        if args.timeout_seconds <= 0:
            parser.error("--timeout-seconds must be positive")
        checkpoint(args.group, args.case, args.raw_dir, args.timeout_seconds)


if __name__ == "__main__":
    main()
