"""Replay the real first-wave decision without widening its frozen query domain.

Each case writes a sanitized checkpoint; aggregate only complete, verified cases.
Supplementary queries remain pending because their context pins were not adopted.
Native transport timeout is wall time, not an attack/search/retry budget.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import sys
from collections import Counter
from fractions import Fraction
from pathlib import Path

from scripts.research.final_cpi_coverage import (
    independent_checks,
    prepare_roasting,
    public_check,
    report_case,
    sensitivity,
)
from scripts.research.final_cpi_extension import COHORT, extension_graph, prepare_extension
from scripts.research.final_cpi_profiles import (
    HISTORICAL,
    PACKAGE,
    ROOT,
    bind_source_a,
    engineering_copy,
    historical_pins,
    read,
)
from scripts.research.final_cpi_release import apply_release
from scripts.research.issue250_public_probe import frozen_inputs, save
from src.engine import run_attack_query
from src.engine.graph import EngineGraph
from src.engine.query_cli import wire
from src.engine.ranking.resolution_service import canonical_digest
from src.parser.snapshot_facts import graph_digest

RELEASE = ROOT / "docs/research/ratings/final-cpi-release-v1/decisions.adopted.json"
LOCAL = ROOT / "reports/generated/issue277-adoption-v2"
REPORT = ROOT / "reports/research/issue277-adopted-replay-v2.json"
REVIEWED_HEAD = "365a5f628d0750db055026c5fcdfe13bea93f121"


SOURCE_PATTERNS = (
    "src/**/*.py",
    "scripts/**/*.py",
    "configs/**/*.yml",
    "configs/**/*.yaml",
    "docs/research/ratings/**/*.json",
    "docs/research/scenarios/**/*.json",
    "data/samples/manifests/*.json",
    "tests/fixtures/**/*.json",
    "pyproject.toml",
    "requirements*.txt",
)
DEPENDENCIES = (
    "networkx",
    "PyYAML",
    "jsonschema",
    "attrs",
    "referencing",
    "rpds-py",
    "jsonschema-specifications",
)


def file_digest(path):
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def execution_identity():
    """Content pins detect source/runtime drift even with unchanged query bytes."""
    paths = {p for pattern in SOURCE_PATTERNS for p in ROOT.glob(pattern) if p.is_file()}
    source = {str(p.relative_to(ROOT)): file_digest(p) for p in sorted(paths)}
    dependencies = {}
    for name in DEPENDENCIES:
        dist = importlib.metadata.distribution(name)
        files = {
            str(p): file_digest(Path(dist.locate_file(p)))
            for p in dist.files or ()
            if str(p).endswith((".py", ".so", "/METADATA", "/RECORD"))
            and Path(dist.locate_file(p)).is_file()
        }
        dependencies[name] = {"version": dist.version, "content_digest": canonical_digest(files)}
    return {
        "source_files": source,
        "source_digest": canonical_digest(source),
        "python_version": sys.version,
        "python_executable_digest": file_digest(Path(sys.executable).resolve()),
        "dependencies": dependencies,
    }


def graph_identity(graph):
    return {
        "graph_digest": graph_digest(graph.to_canonical()),
        "snapshot_id": graph.metadata.get("snapshot_id"),
        "snapshot_facts_digest": canonical_digest(wire(graph.snapshot_facts)),
    }


def execution_summary(execution):
    # The digest pins the complete source-file map; publish that map once in the report.
    return {k: v for k, v in execution.items() if k != "source_files"}


def load_inputs(raw_dir):
    if raw_dir is None:
        raise ValueError("Manifest-verified --raw-dir required for checkpoint scope verification")
    return frozen_inputs(raw_dir, read(PACKAGE / "cohort.json")["baseline_revision"])[:2]


def prepare_case(group, case, raw_graph, frozen, raw_dir, release):
    """Re-derive all current questions, including non-adopted ones, before counting."""
    if group == "original":
        if case["id"] in release["query_pins"]:
            query, projected = bind_source_a(case["id"])
            graph = (
                EngineGraph.from_canonical(projected)
                if case["graph"].startswith("historical_induced")
                else raw_graph
            )
        else:
            query, graph = prepare_roasting(case, raw_graph, frozen), raw_graph
    else:
        query, _ = prepare_extension(case, raw_graph, raw_dir)
        graph = extension_graph(case, raw_graph, query)
    adopted = group == "original" and case["id"] in release["query_pins"]
    if adopted:
        consumed = apply_release(query, release)
    else:
        try:
            apply_release(query, release)
        except ValueError:
            pass
        else:
            raise ValueError("Adoption leaked beyond reviewed query domain")
        consumed = query
    return query, consumed, graph, adopted


def evidence_scope(group, cohort, case, release, execution, raw_identity, graph, query, consumed):
    return {
        "version": "final-cpi-checkpoint-scope/2.0.0",
        "group": group,
        "case_id": case["id"],
        "cohort_digest": canonical_digest(cohort),
        "case_digest": canonical_digest(case),
        "release_digest": canonical_digest(release),
        "adoption_applied": group == "original" and case["id"] in release["query_pins"],
        "execution_digest": canonical_digest(execution),
        "raw_input_identity": raw_identity,
        "case_graph_identity": graph_identity(graph),
        "query_before_release_digest": canonical_digest(query),
        "query_consumed_digest": canonical_digest(consumed),
    }


def checkpoint(group, case_id, raw_dir, timeout_seconds):
    execution = execution_identity()
    release, pins = read(RELEASE), historical_pins()
    cohort = read(PACKAGE / "cohort.json" if group == "original" else COHORT)
    case = next(c for c in cohort["queries"] if c["id"] == case_id)
    graph, frozen = load_inputs(raw_dir)
    raw_identity = graph_identity(graph)
    raw_digest = raw_identity["graph_digest"]
    projection = read(HISTORICAL / "source-a-graph.json")
    ids = {n["id"] for n in projection["nodes"]}
    canonical = graph.to_canonical()
    if [n for n in canonical["nodes"] if n["id"] in ids] != projection["nodes"] or [
        e for e in canonical["edges"] if e["source"] in ids and e["target"] in ids
    ] != projection["edges"]:
        raise ValueError("Historical projection is not exactly raw-backed")
    query, released, original, adopted = prepare_case(group, case, graph, frozen, raw_dir, release)
    scope = evidence_scope(
        group, cohort, case, release, execution, raw_identity, original, query, released
    )
    supported = case["supported_cohort" if group == "original" else "supported"]
    baseline = run_attack_query(query, original)
    result, public = public_check(
        released,
        original,
        LOCAL,
        group + "." + case_id,
        "seamless",
        timeout_seconds=timeout_seconds,
    )
    if wire(result.paths) != wire(baseline.paths):
        raise ValueError("Numeric adoption changed generated program identities")
    audits = []
    for detail in result.rating_coverage["candidates"].values():
        audits.extend(u["rating_audit"] for u in detail["effort"]["units"].values())
        audits.extend(u["rating_audit"] for u in detail["likelihood"]["prefixes"])
        if detail["impact"].get("rating_audit"):
            audits.append(detail["impact"]["rating_audit"])
    actual = [a for a in audits if a.get("review_reference") == release["review"]["reference"]]
    if adopted and result.ranking_result["eligible_candidates"] and not actual:
        raise ValueError("Missing actual adoption provenance")
    if any(a.get("numeric_basis_class") != "estimated_expert_scenario" for a in actual):
        raise ValueError("Actual decision mislabeled as empirical or synthetic")
    row = {
        "evidence_scope": scope,
        "execution_identity": execution_summary(execution),
        "query_id": case_id,
        "supported_cohort": supported,
        "numeric_adoption_applied": adopted,
        "query_before_release_digest": canonical_digest(query),
        "query_consumed_digest": canonical_digest(released),
        "baseline_pending": report_case(baseline),
        "actual_after_decision": report_case(result),
        "programs_unchanged_by_adoption": True,
        "public_verification": public,
        "independent_oracle": independent_checks(result),
        "actual_review_audit_entries": len(actual),
        "actual_numeric_basis_classes": sorted({a["numeric_basis_class"] for a in actual}),
        "actual_review_statuses": sorted({a["review_status"] for a in actual}),
        "graph": {
            "nodes": len(original.nodes()),
            "edges": len(original.edges()),
            "is_full_raw": original is graph,
            "sha256": graph_digest(original.to_canonical()),
        },
    }
    if case_id == "source-a-projection" and group == "original":
        test_query, derivative = engineering_copy(released, original)
        row["sensitivity"] = sensitivity(test_query, derivative)
        row["sensitivity"]["authority"] = (
            "synthetic_test_only controls; changed questions are not an adopted release"
        )
    if historical_pins() != pins or graph_digest(graph.to_canonical()) != raw_digest:
        raise ValueError("Frozen history or raw graph changed")
    if execution_identity() != execution:
        raise ValueError("Executable/source changed during replay")
    current_cohort = read(PACKAGE / "cohort.json" if group == "original" else COHORT)
    if current_cohort != cohort or read(RELEASE) != release:
        raise ValueError("Cohort/release changed during replay")
    row["historical_files_byte_preserved"] = len(pins)
    save(LOCAL / (group + "." + case_id + ".verified.json"), row)
    print(
        json.dumps(
            {"group": group, "case": case_id, "counts": row["actual_after_decision"]["counts"]}
        ),
        flush=True,
    )


def aggregate(raw_dir=None):
    execution = execution_identity()
    release = read(RELEASE)
    raw_graph, frozen = load_inputs(raw_dir)
    raw_identity = graph_identity(raw_graph)
    report = {
        "version": "final-cpi-actual-adoption-replay/2.0.0",
        "reviewed_proposal_head": REVIEWED_HEAD,
        "release_digest": canonical_digest(release),
        "review": release["review"],
        "execution_python": sys.version,
        "execution_identity": execution,
        "raw_input_identity": raw_identity,
        "groups": {},
        "limitations": [
            "First-wave expert scenario adoption, not empirical calibration.",
            "Original and supplementary cohorts are separate; no denominator pooling.",
            "Supplementary context/query pins were not adopted; pending remains pending.",
            "Truncated returned samples are not full generator/global-optimum coverage.",
            "Query-local sensitivity only; source/batch/chokepoint sensitivity not established.",
            "Partial connector-materialized checkout; no full repository test claim.",
        ],
    }
    for group, cohort_path, supported_field in (
        ("original", PACKAGE / "cohort.json", "supported_cohort"),
        ("supplementary", COHORT, "supported"),
    ):
        cohort = read(cohort_path)
        rows, missing = [], []
        all_counts, supported_counts, raw_counts = Counter(), Counter(), Counter()
        for case in cohort["queries"]:
            path = LOCAL / (group + "." + case["id"] + ".verified.json")
            if not path.exists():
                missing.append(case["id"])
                continue
            row = read(path)
            # Current manifest-backed graph, scope and source are independently re-derived.
            bound, expected_consumed, graph, expected_adoption = prepare_case(
                group, case, raw_graph, frozen, raw_dir, release
            )
            expected_scope = evidence_scope(
                group,
                cohort,
                case,
                release,
                execution,
                raw_identity,
                graph,
                bound,
                expected_consumed,
            )
            if row.get("evidence_scope") != expected_scope or row.get(
                "execution_identity"
            ) != execution_summary(execution):
                raise ValueError("Checkpoint evidence scope mismatch; fresh replay required")
            consumed = read(LOCAL / (group + "." + case["id"] + ".query.json"))
            if canonical_digest(consumed) != canonical_digest(expected_consumed):
                raise ValueError("Checkpoint consumed query digest mismatch")
            if row.get("query_consumed_digest") != canonical_digest(consumed):
                raise ValueError("Checkpoint consumed query digest mismatch")
            if row.get("query_before_release_digest") != canonical_digest(bound):
                raise ValueError("Checkpoint original query digest mismatch")
            if row["numeric_adoption_applied"] != expected_adoption:
                raise ValueError("Checkpoint adoption domain mismatch")
            if row["supported_cohort"] != case[supported_field]:
                raise ValueError("Checkpoint supported scope mismatch")
            expected_graph = {
                "nodes": len(graph.nodes()),
                "edges": len(graph.edges()),
                "is_full_raw": graph is raw_graph,
                "sha256": expected_scope["case_graph_identity"]["graph_digest"],
            }
            if row["graph"] != expected_graph:
                raise ValueError("Checkpoint graph identity mismatch")
            row["source_profile"] = case.get("source", cohort.get("source_profile"))
            row["goal"] = case.get(
                "goal", ",".join(sorted(consumed.get("target_goal", {}).get("required_state", {})))
            )
            rows.append(row)
            all_counts.update(row["actual_after_decision"]["counts"])
            if case[supported_field]:
                supported_counts.update(row["actual_after_decision"]["counts"])
            if row["graph"]["is_full_raw"]:
                raw_counts.update(row["actual_after_decision"]["counts"])
        feasible = supported_counts["conditioned_feasible"]
        ratio = Fraction(supported_counts["fully_rated"], feasible) if feasible else None
        report["groups"][group] = {
            "cohort_digest": canonical_digest(cohort),
            "complete_replay": not missing,
            "missing_queries": missing,
            "cases": rows,
            "all_completed_query_counts": dict(all_counts),
            "denominator_unit": (
                "query-program occurrences in the frozen cohort; predeclared projection/raw "
                "overlap retained, never interpreted as independent unique attacks; CLI repeats "
                "are verification only and are never added to the denominator"
            ),
            "manifest_verified_full_raw_completed_query_counts": dict(raw_counts),
            "supported_completed_query_counts": dict(supported_counts),
            "supported_returned_sample_full_fraction": str(ratio) if ratio is not None else None,
            "meets_80_percent_on_complete_supported_returned_sample": (
                not missing and ratio is not None and ratio >= Fraction(4, 5)
            ),
            "full_generator_coverage_established": False,
            "truncated_query_count": sum(r["actual_after_decision"]["truncated"] for r in rows),
            "unrated_query_count": sum(
                r["actual_after_decision"]["counts"]["conditioned_feasible"]
                > r["actual_after_decision"]["counts"]["fully_rated"]
                for r in rows
            ),
        }
    if execution_identity() != execution or read(RELEASE) != release:
        raise ValueError("Executable/source/release changed during aggregation")
    if graph_identity(raw_graph) != raw_identity:
        raise ValueError("Raw graph/snapshot changed during aggregation")
    save(REPORT, report)
    print(
        json.dumps(
            {
                g: {k: v for k, v in row.items() if k != "cases"}
                for g, row in report["groups"].items()
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
    if args.aggregate:
        if args.raw_dir is None:
            parser.error("--aggregate requires --raw-dir to re-derive current evidence scope")
        aggregate(args.raw_dir)
    else:
        if not args.group or not args.case or not args.raw_dir:
            parser.error("--group, --case and --raw-dir required")
        if args.timeout_seconds <= 0:
            parser.error("--timeout-seconds must be positive")
        checkpoint(args.group, args.case, args.raw_dir, args.timeout_seconds)


if __name__ == "__main__":
    main()
