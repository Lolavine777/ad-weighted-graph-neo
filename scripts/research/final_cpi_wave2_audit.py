"""Read-only Wave 2 diagnosis of frozen #277 replay (not numeric adoption).

Run: python -m scripts.research.final_cpi_wave2_audit
Optional: --report PATH --output PATH
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
from collections.abc import Iterable
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "reports/research/issue277-adopted-replay-v2.json"
DECISION_REF = "https://github.com/nairyuuu/ad-weighted-graph/issues/267#issuecomment-6142406787"

# Numeric decisions are already recorded by the maintainer. This is *not* an
# authorization to bind those values to unreviewed contexts or full histories.
ADOPTED_NUMERIC = frozenset(
    {
        "directory_password_reset",
        "reset_identity_activation",
        "winrm_admin_execution",
        "host_admin_execution",
        "asrep_material_request",
        "kerberoast_material_request",
        "group_membership_mutation",
        "grant_write_dacl",
        "grant_generic_all",
        "rdp_interactive_session",
        "winrm_command_session",
        "session_credential_material",
        "rbcd_secret_acquisition",
        "rbcd_service_preparation",
        "rbcd_descriptor_mutation",
        "rbcd_service_delegation",
        "rbcd_admin_execution",
    }
)
C_ONLY = frozenset({"asrep_password_recovery", "kerberoast_password_recovery"})
NEEDS_EVIDENCE = frozenset({"recovered_identity_activation"})
UNBOUND_POLICY = frozenset({"rdp_interactive_session", "session_credential_material"})
COUNT_FIELDS = (
    "valid_generated",
    "conditioned_feasible",
    "C_rated",
    "P_rated",
    "I_rated",
    "fully_rated",
    "Pareto_eligible",
)


def _bound_context(case: dict, report: dict, group: dict) -> bool:
    """Only establish binding when every returned occurrence is rated.

    Aggregate replay evidence cannot identify which families are bound in a
    partially rated case. Do not distribute its numerator across families.
    """
    actual = case["actual_after_decision"]
    counts = actual["counts"]
    scope = case.get("evidence_scope", {})
    statuses = set(case.get("actual_review_statuses", []))
    return (
        case.get("numeric_adoption_applied") is True
        and scope.get("adoption_applied") is True
        and scope.get("case_id") == case["query_id"]
        and scope.get("release_digest") == report["release_digest"]
        and scope.get("cohort_digest") == group["cohort_digest"]
        and bool(scope.get("execution_digest"))
        and bool(scope.get("query_consumed_digest"))
        and bool(report.get("review", {}).get("reference"))
        and case.get("actual_review_audit_entries", 0) > 0
        and "accepted" in statuses
        and statuses <= {"accepted", "reviewed"}
        and counts["conditioned_feasible"] > 0
        and all(
            counts[k] == counts["conditioned_feasible"]
            for k in ("C_rated", "P_rated", "I_rated", "fully_rated")
        )
        and not actual.get("gaps")
    )


def _validated_totals(group: dict, cases: list[dict], name: str, supported: bool) -> dict:
    field = "supported_completed_query_counts" if supported else "all_completed_query_counts"
    totals = group[field]
    selected = [c for c in cases if c["supported_cohort"]] if supported else cases
    for key in COUNT_FIELDS:
        expected = sum(c["counts"][key] for c in selected)
        if type(totals[key]) is not int or totals[key] != expected:
            label = (
                "denominator"
                if key == "conditioned_feasible"
                else "rated numerator"
                if key == "fully_rated"
                else key
            )
            raise ValueError(f"Frozen {label} drift: {name}/{field}")
    return {key: totals[key] for key in COUNT_FIELDS}


def diagnose(report: dict) -> dict:
    """Diagnose observed replay blockers; never infer per-path adoption."""
    if report.get("version") != "final-cpi-actual-adoption-replay/2.0.0":
        raise ValueError("Unsupported replay revision; refresh audit explicitly")
    groups = report["groups"]
    canonical = json.dumps(report, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    result = {
        "version": "final-cpi-wave2-audit/2.0.0",
        "source_report_version": report["version"],
        "source_report_digest": "sha256:" + hashlib.sha256(canonical.encode()).hexdigest(),
        "source_report_digest_scope": "canonical JSON; sorted keys, compact, UTF-8",
        "release_digest": report["release_digest"],
        "execution_identity": copy.deepcopy(report["execution_identity"]),
        "raw_input_identity": copy.deepcopy(report["raw_input_identity"]),
        "source_review": copy.deepcopy(report["review"]),
        "numeric_decision_reference": DECISION_REF,
        "does_not_enable_production": True,
        "groups": {},
    }
    for name in ("original", "supplementary"):
        group = groups[name]
        cases = []
        for case in group["cases"]:
            actual = case["actual_after_decision"]
            counts = actual["counts"]
            feasible = counts["conditioned_feasible"]
            rated = counts["fully_rated"]
            if (
                any(type(counts[k]) is not int or counts[k] < 0 for k in COUNT_FIELDS)
                or feasible > counts["valid_generated"]
                or any(counts[k] > feasible for k in COUNT_FIELDS[2:])
                or rated > min(counts[k] for k in ("C_rated", "P_rated", "I_rated"))
            ):
                raise ValueError("Inconsistent coverage: " + case["query_id"])
            if type(case.get("supported_cohort")) is not bool:
                raise ValueError("Missing or invalid supported cohort: " + case["query_id"])
            bound = _bound_context(case, report, group)
            families = actual.get("paths_by_action_family_nonexclusive", {})
            blockers = []
            for family, observed in sorted(families.items()):
                # Family occurrences overlap within a path; they are NOT
                # additional denominators or independent failure counts.
                if type(observed) is not int or not 0 <= observed <= feasible:
                    raise ValueError("Inconsistent family occurrences: " + case["query_id"])
                disposition = (
                    "BOUND_REPLAY_CONTEXT"
                    if bound
                    else "ADOPTION_APPLIED_BINDING_NOT_ESTABLISHED"
                    if case.get("numeric_adoption_applied") is True and family in ADOPTED_NUMERIC
                    else "C_ONLY_P_UNRATED"
                    if family in C_ONLY
                    else "NEEDS_EVIDENCE"
                    if family in NEEDS_EVIDENCE
                    else "NUMERIC_ACCEPTED_POLICY_BINDING_UNSUPPORTED"
                    if family in UNBOUND_POLICY
                    else "NUMERIC_ACCEPTED_CONTEXT_NOT_YET_BOUND"
                    if family in ADOPTED_NUMERIC
                    else "UNREVIEWED_CLASS"
                )
                blockers.append(
                    {
                        "class": family,
                        "nonexclusive_occurrences": observed,
                        "numeric_disposition": disposition,
                    }
                )
            cases.append(
                {
                    "query_id": case["query_id"],
                    "supported_cohort": case.get("supported_cohort", False),
                    "conditioned_feasible": feasible,
                    "fully_rated": rated,
                    "counts": {key: counts[key] for key in COUNT_FIELDS},
                    "binding_established_for_all_returned_occurrences": bound,
                    "numeric_adoption_applied": case.get("numeric_adoption_applied", False),
                    "actual_review_statuses": copy.deepcopy(case.get("actual_review_statuses", [])),
                    "actual_review_audit_entries": case.get("actual_review_audit_entries", 0),
                    "evidence_scope": copy.deepcopy(case.get("evidence_scope", {})),
                    "truncated": actual.get("truncated"),
                    "gaps": actual.get("gaps", []),
                    "action_families": blockers,
                }
            )
        result["groups"][name] = {
            "all_completed_query_counts": _validated_totals(group, cases, name, False),
            "supported_completed_query_counts": _validated_totals(group, cases, name, True),
            "cohort_digest": group["cohort_digest"],
            "denominator_unit": group["denominator_unit"],
            "cases": cases,
            "note": (
                "All includes diagnostic cases; supported is the declared target cohort. "
                "Do not pool cohorts or count overlapping families as paths. "
                "Binding classification covers returned occurrences, not unreturned paths."
            ),
        }
    return result


def _is_same_path(path_a: Path, path_b: Path) -> bool:
    try:
        res_a = path_a.resolve()
        res_b = path_b.resolve()
        if res_a == res_b:
            return True
        if os.path.normcase(str(res_a)) == os.path.normcase(str(res_b)):
            return True
    except OSError:
        pass
    try:
        if path_a.exists() and path_b.exists() and path_a.samefile(path_b):
            return True
    except OSError:
        pass
    return False


def protect_output(output: Path, inputs: Iterable[Path]) -> None:
    """Reject path, symlink, and hardlink aliases to protected input reports."""
    for path in inputs:
        if _is_same_path(output, path):
            raise ValueError(f"Output path aliases protected report: {path}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, default=REPORT)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.output:
        try:
            protect_output(args.output, (args.report, REPORT))
        except ValueError as err:
            parser.error(str(err))
    source_bytes = args.report.read_bytes()
    diagnosis = diagnose(json.loads(source_bytes.decode("utf-8")))
    diagnosis["source_report_file_sha256"] = "sha256:" + hashlib.sha256(source_bytes).hexdigest()
    payload = json.dumps(diagnosis, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
    else:
        print(payload, end="")


if __name__ == "__main__":
    main()
