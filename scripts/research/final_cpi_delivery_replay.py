"""Fresh native before/after evidence for the dimension-scoped Wave 2 release."""

from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path

from scripts.research.final_cpi_adoption_replay import (
    RELEASE as WAVE1,
)
from scripts.research.final_cpi_adoption_replay import (
    execution_identity,
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
from scripts.research.final_cpi_delegated_release import (
    COHORT as DECLARED_COHORT,
)
from scripts.research.final_cpi_delegated_release import (
    MODELS,
    REFERENCE,
    prepare_declared,
)
from scripts.research.final_cpi_delegated_release import (
    RELEASE as DELEGATED_RELEASE,
)
from scripts.research.final_cpi_effort_release import C_ONLY, RELEASE
from scripts.research.final_cpi_extension import COHORT
from scripts.research.final_cpi_profiles import PACKAGE, ROOT, historical_pins, read
from scripts.research.final_cpi_release import apply_release
from scripts.research.final_cpi_wave2_replay import report_family_coverage, step_blockers
from scripts.research.issue250_public_probe import save
from src.engine import run_attack_query
from src.engine.query_cli import revision_metadata, wire
from src.engine.ranking.resolution_service import canonical_digest

ADOPTED_WAVE2 = PACKAGE.parent / "final-cpi-release-v2/decisions.adopted.json"
LOCAL = ROOT / "reports/generated/issue267-wave2-delivery-v11"
REPORT = ROOT / "reports/research/issue267-wave2-delivery-v11.json"
COHORTS = {
    "original": PACKAGE / "cohort.json",
    "supplementary": COHORT,
    "declared_recovery": DECLARED_COHORT,
}


def prepare(group, case, raw_graph, frozen, raw_dir):
    if group == "declared_recovery":
        query = prepare_declared(case, raw_graph, frozen)
        return query, query, apply_release(query, read(DELEGATED_RELEASE)), raw_graph, False, False
    query, before, graph, wave1 = prepare_case(group, case, raw_graph, frozen, raw_dir, read(WAVE1))
    release = read(RELEASE)
    adopted = read(ADOPTED_WAVE2)
    bound = adopted["contexts"].get(case["id"], {}).get("decision") == "adopt"
    recovery_C = case["id"] in ("asrep-natural-password", "kerberoast-identity")
    if bound:
        before = apply_release(query, adopted)
    elif recovery_C:
        # The newly returned User-goal program has no prior approved history pin.
        if canonical_digest(query) == release["query_pins"][case["id"]]:
            before = apply_release(query, release)
        elif case["id"] != "kerberoast-identity":
            raise ValueError("Unexpected previous recovery context drift")
    after = apply_release(query, read(DELEGATED_RELEASE))
    return query, before, after, graph, wave1, bound


def scope(group, cohort, case, query, before, after, graph, raw_graph, execution):
    return {
        "version": "final-cpi-delivery-scope/3.0.0",
        "group": group,
        "case_digest": canonical_digest(case),
        "cohort_digest": canonical_digest(cohort),
        "wave1_release_digest": canonical_digest(read(WAVE1)),
        "wave2_release_digest": canonical_digest(read(RELEASE)),
        "adopted_wave2_release_digest": canonical_digest(read(ADOPTED_WAVE2)),
        "delegated_release_digest": canonical_digest(read(DELEGATED_RELEASE)),
        "execution_digest": canonical_digest(execution),
        "executable_checkout": revision_metadata(),
        "raw_identity": graph_identity(raw_graph),
        "graph_identity": graph_identity(graph),
        "query_digest": canonical_digest(query),
        "before_digest": canonical_digest(before),
        "after_digest": canonical_digest(after),
    }


def matrix(result, query):
    """Native records plus exact anonymized authority/history identifiers.

    Private query/CLI artifacts retain complete canonical identities. Public
    digests preserve ordered full-history equality without publishing AD IDs.
    """
    ledger = step_blockers(result)
    context = query["rating_resolution"]["scope"]
    taxonomy = {
        r["technique_id"]: r["canonical_class"] for r in read(PACKAGE / "taxonomy.json")["actions"]
    }
    for program in ledger["programs"]:
        detail = result.rating_coverage["candidates"][program["candidate"]]
        for action in program["steps"]:
            action["class"] = taxonomy[action["technique"]]
            if not action["active"]:
                continue
            for dimension in ("C", "P"):
                record = action.get(dimension, {})
                if "disposition" not in record:
                    continue
                if record["disposition"] == "rated":
                    blocker, owner, treatment = None, None, "bound by actual dimension authority"
                elif dimension == "P" and action["class"] in C_ONLY:
                    blocker, owner, treatment = (
                        "no numeric basis",
                        "deployment evidence",
                        "retain frozen control unrated; declared models are separate contexts",
                    )
                elif action["class"] == "recovered_identity_activation":
                    blocker, owner, treatment = (
                        "context/history mismatch",
                        "A resolver",
                        "exact reviewed recovered lineage/freshness/full-history record required",
                    )
                else:
                    blocker, owner, treatment = (
                        "approved-but-unbound",
                        "A resolver",
                        "retain unrated outside the exact adopted context/history inventory",
                    )
                record.update(
                    blocker=blocker,
                    owner=owner,
                    treatment=treatment,
                    location=(
                        "scripts/research/final_cpi_delegated_release.py:validate; "
                        "docs/research/ratings/final-cpi-release-v5/decisions.adopted.json"
                    ),
                )
            prefix = next(
                (
                    p
                    for p in detail["likelihood"]["prefixes"]
                    if canonical_digest(p["rating_audit"]["lookup_key"])
                    == action.get("P", {}).get("lookup_digest")
                ),
                None,
            )
            if prefix is not None:
                key = prefix["rating_audit"]["lookup_key"]
                action["conditional_question"] = {
                    "full_history": [canonical_digest(unit) for unit in prefix["prefix"]],
                    "lookup_digest": canonical_digest(key),
                    "actor_resource_target_digest": canonical_digest(
                        {
                            k: key.get(k)
                            for k in (
                                "actor_id",
                                "source_id",
                                "target_id",
                                "resource_context",
                                "auth_context",
                            )
                        }
                    ),
                    "policy_id": key.get("policy_id"),
                    "method": key.get("method"),
                    "horizon": key.get("horizon"),
                    "retry_policy_digest": canonical_digest(context["retry_policy"]),
                }
        program["terminal_I"].update(
            blocker=None
            if program["terminal_I"]["disposition"] == "rated"
            else "approved-but-unbound",
            owner="A typed mapping",
            location="docs/research/ratings/final-cpi-release-v4/decisions.adopted.json",
        )
    native = report_case(result)
    ledger["path_disposition"] = (
        "truncated" if result.truncated else "generated" if result.paths else "not_generated"
    )
    ledger["numeric_disposition"] = (
        "unrated"
        if native["counts"]["conditioned_feasible"] > native["counts"]["fully_rated"]
        else "fully_rated"
        if result.paths
        else "no_returned_program"
    )
    ledger["additional_blockers"] = (
        [
            {
                "class": "state/goal attribution",
                "owner": "B",
                "reproducer": "kerberoast-identity",
                "expected": (
                    "preserve typed User goal; return successful activation state "
                    "despite authentication-Computer action endpoint"
                ),
            }
        ]
        if native["B_goal_contract_gap"]
        else []
    )
    if result.truncated:
        ledger["additional_blockers"].append(
            {
                "class": "search truncated",
                "owner": "B search",
                "reason": result.truncation_reason,
                "treatment": "report bounded returned sample; no global optimum",
            }
        )
    outcomes = Counter()
    for attempt in result.attempts:
        for predicate in attempt.failed:
            outcomes[(attempt.request.technique_id, "not feasible", predicate)] += 1
        for predicate in attempt.unknown:
            category = (
                "missing policy"
                if "policy" in predicate or "context" in predicate
                else "context/history mismatch"
            )
            outcomes[(attempt.request.technique_id, category, predicate)] += 1
    ledger["attempt_blockers_nonexclusive"] = [
        {
            "technique": technique,
            "blocker": category,
            "predicate": predicate,
            "count": count,
            "owner": "A scenario inputs / B semantics",
            "location": "src/engine/semantics/evaluator.py",
            "treatment": "known-FALSE veto"
            if category == "not feasible"
            else "retain Unknown; supply supported scoped evidence",
        }
        for (technique, category, predicate), count in sorted(outcomes.items())
    ]
    return ledger


def c_oracle(result):
    classes = {r["class_id"]: r["cost"] for r in read(PACKAGE / "profile.json")["classes"]}
    taxonomy = {
        r["technique_id"]: r["canonical_class"] for r in read(PACKAGE / "taxonomy.json")["actions"]
    }
    checked = 0
    for detail in result.rating_coverage["candidates"].values():
        for unit in detail["effort"]["units"].values():
            if unit["disposition"] == "rated":
                cls = taxonomy[unit["rating_audit"]["lookup_key"]["technique"]]
                if unit["cost"] != classes[cls]:
                    raise ValueError("Independent C-only oracle mismatch")
                checked += 1
    return checked


def oracle(result, case_id):
    overrides = {}
    if case_id in MODELS:
        name = "asrep_password_recovery" if case_id == MODELS[0] else "kerberoast_password_recovery"
        lower, upper = read(DELEGATED_RELEASE)["recovery_models"][case_id]["P"]
        overrides[name] = {"lower": lower, "upper": upper}
    return independent_checks(result, overrides)


def validate_counts(counts):
    if not set(COUNT_FIELDS) <= counts.keys() or any(
        type(counts[k]) is not int or counts[k] < 0 for k in COUNT_FIELDS
    ):
        raise ValueError("Invalid checkpoint counts")
    if (
        counts["conditioned_feasible"] > counts["valid_generated"]
        or any(counts[k] > counts["conditioned_feasible"] for k in COUNT_FIELDS[2:])
        or counts["fully_rated"] > min(counts[k] for k in ("C_rated", "P_rated", "I_rated"))
        or counts["Pareto_eligible"] > counts["fully_rated"]
    ):
        raise ValueError("Inconsistent checkpoint counts")


def recount(coverage, ranking, generated):
    summaries = list(coverage["candidate_summaries"].values())
    return {
        "valid_generated": generated,
        "conditioned_feasible": sum(s["semantic_status"] == "feasible" for s in summaries),
        **{
            field: sum(s[key] for s in summaries)
            for field, key in (
                ("C_rated", "c_complete"),
                ("P_rated", "p_complete"),
                ("I_rated", "i_complete"),
                ("fully_rated", "numeric_complete"),
            )
        },
        "Pareto_eligible": len(ranking["eligible_candidates"]),
    }


def checkpoint(group, case, cohort, raw_graph, frozen, raw_dir, execution):
    name = group + "." + case["id"]
    destination = LOCAL / (name + ".verified.json")
    if destination.exists():
        raise ValueError("Checkpoint exists; preserve evidence and choose another namespace")
    query, before, after, graph, wave1, bound = prepare(group, case, raw_graph, frozen, raw_dir)
    expected = scope(group, cohort, case, query, before, after, graph, raw_graph, execution)
    result, public = public_check(
        after, graph, LOCAL, name + ".after", "seamless", timeout_seconds=1200
    )
    baseline = run_attack_query(before, graph) if after != before else result
    if wire(baseline.paths) != wire(result.paths):
        raise ValueError("C binding changed native paths")
    save(LOCAL / (name + ".before.query.json"), before)
    row = {
        "scope": expected,
        "query_id": case["id"],
        "supported": case["supported_cohort" if group == "original" else "supported"],
        "full_raw": graph is raw_graph,
        "wave1_applied": wave1,
        "wave2_context_adoption_applied": bound,
        "delegated_adoption_applied": True,
        "rating_bindings_changed": after != before,
        "before": report_case(baseline),
        "after": report_case(result),
        "family_coverage_nonexclusive": {
            "before": report_family_coverage(baseline),
            "after": report_family_coverage(result),
        },
        "blocker_matrix": matrix(result, after),
        "public_verification": public,
        "independent_oracle": oracle(result, case["id"]),
        "C_units_checked": c_oracle(result),
        "programs_unchanged": True,
    }
    save(
        LOCAL / (name + ".before.numeric.json"),
        {
            "coverage": wire(baseline.rating_coverage),
            "ranking": wire(baseline.ranking_result),
            "generated": len(baseline.paths),
        },
    )
    row["before_coverage_digest"] = canonical_digest(wire(baseline.rating_coverage))
    row["after_coverage_digest"] = canonical_digest(wire(result.rating_coverage))
    if group == "original" and case["id"] == "source-a-projection":
        row["sensitivity"] = sensitivity(after, graph)
        row["sensitivity"]["authority"] = (
            "test-only bounds perturbation of applicable production records; "
            "no new production approval"
        )
    if (
        scope(group, cohort, case, query, before, after, graph, raw_graph, execution_identity())
        != expected
    ):
        raise ValueError("Evidence scope changed during execution")
    save(destination, row)
    print(name, row["before"]["counts"], "=>", row["after"]["counts"], flush=True)


def aggregate(raw_graph, frozen, raw_dir, execution):
    if REPORT.exists():
        raise ValueError("Report exists; never overwrite frozen evidence")
    report = {
        "version": "final-cpi-wave2-delivery/11.0.0",
        "execution_identity": execution,
        "executable_checkout": revision_metadata(),
        "effort_release": read(RELEASE),
        "adopted_release": read(ADOPTED_WAVE2),
        "delegated_release": read(DELEGATED_RELEASE),
        "adoption_authority": REFERENCE,
        "baseline": (
            "Prior releases in their exact applicable domains, evaluated with the corrected "
            "native state-goal engine. Newly returned Kerberoast identity history remains "
            "unbound under the old receipt. Declared models are distinct new contexts."
        ),
        "groups": {},
        "source_ranking_sensitivity": "unmeasured",
        "chokepoint_sensitivity": "unmeasured",
        "global_optimum": "not established",
    }
    for group, path in COHORTS.items():
        cohort = read(path)
        rows = []
        for case in cohort["queries"]:
            row = read(LOCAL / (group + "." + case["id"] + ".verified.json"))
            for phase in ("before", "after"):
                validate_counts(row[phase]["counts"])
            name = group + "." + case["id"]
            baseline = read(LOCAL / (name + ".before.numeric.json"))
            actual = read(LOCAL / (name + ".after.run1.normalized.json"))
            repeated = read(LOCAL / (name + ".after.run2.normalized.json"))
            if canonical_digest(actual) != canonical_digest(repeated):
                raise ValueError("Native two-process determinism mismatch")
            if (
                recount(baseline["coverage"], baseline["ranking"], baseline["generated"])
                != row["before"]["counts"]
                or recount(
                    actual["rating_coverage"],
                    actual["ranking_result"],
                    len(actual["program_identities"]),
                )
                != row["after"]["counts"]
                or canonical_digest(baseline["coverage"]) != row["before_coverage_digest"]
                or canonical_digest(actual["rating_coverage"]) != row["after_coverage_digest"]
            ):
                raise ValueError("Native ledger/count mismatch")
            query, before, after, graph, wave1, bound = prepare(
                group, case, raw_graph, frozen, raw_dir
            )
            for phase, consumed in (("before", before), ("after", after)):
                actual_query = read(LOCAL / (name + "." + phase + ".query.json"))
                if canonical_digest(actual_query) != canonical_digest(consumed):
                    raise ValueError("Checkpoint " + phase + " consumed query mismatch")
            if row["scope"] != scope(
                group, cohort, case, query, before, after, graph, raw_graph, execution
            ):
                raise ValueError("Stale checkpoint scope")
            if (
                row["supported"] != case["supported_cohort" if group == "original" else "supported"]
                or row["full_raw"] != (graph is raw_graph)
                or row["wave1_applied"] != wave1
                or row["wave2_context_adoption_applied"] != bound
                or row["rating_bindings_changed"] != (after != before)
                or row["delegated_adoption_applied"] is not True
            ):
                raise ValueError("Checkpoint membership drift")
            public = row["public_verification"]
            if (
                public.get("two_CLI_exit_codes") != [0, 0]
                or any(type(code) is not int for code in public["two_CLI_exit_codes"])
                or any(
                    row["public_verification"].get(k) is not True
                    for k in (
                        "two_process_equal",
                        "API_CLI_semantic_ranking_coverage_programs_equal",
                        "orchestration_search_ranking_programs_equal",
                    )
                )
            ):
                raise ValueError("Unverified public native execution")
            rows.append(row)
        totals = {}
        for selection in ("all", "supported", "full_raw"):
            totals[selection] = {}
            for phase in ("before", "after"):
                counts = Counter({field: 0 for field in COUNT_FIELDS})
                chosen = [r for r in rows if selection == "all" or r[selection]]
                for row in chosen:
                    counts.update(row[phase]["counts"])
                totals[selection][phase] = {
                    **dict(counts),
                    "truncated_queries": sum(r[phase]["truncated"] for r in chosen),
                    "not_generated_queries": sum(
                        r[phase]["counts"]["valid_generated"] == 0 for r in chosen
                    ),
                }
        report["groups"][group] = {
            "cohort_digest": canonical_digest(cohort),
            "complete": True,
            "totals": totals,
            "cases": rows,
            "denominator": (
                "unchanged cohort selectors; actual returned query-program occurrences; "
                "declared recovery scenarios separate from frozen controls; CLI repeats excluded; "
                "projection/raw overlap retained"
            ),
        }
    if execution_identity() != execution:
        raise ValueError("Execution identity changed during aggregation")
    save(REPORT, report)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-dir", type=Path, required=True)
    parser.add_argument("--group", choices=tuple(COHORTS))
    parser.add_argument("--case")
    parser.add_argument("--aggregate", action="store_true")
    args = parser.parse_args()
    if revision_metadata()["tracked_changes"]:
        raise ValueError("Native delivery acceptance requires a clean committed executable")
    raw_graph, frozen = load_inputs(args.raw_dir)
    execution, history = execution_identity(), historical_pins()
    if args.aggregate:
        aggregate(raw_graph, frozen, args.raw_dir, execution)
    else:
        for group, path in COHORTS.items():
            if args.group and args.group != group:
                continue
            cohort = read(path)
            for case in cohort["queries"]:
                if not args.case or args.case == case["id"]:
                    checkpoint(group, case, cohort, raw_graph, frozen, args.raw_dir, execution)
    if history != historical_pins():
        raise ValueError("Historical files changed")


if __name__ == "__main__":
    main()
