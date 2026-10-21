"""Week 4 Acceptance Runner and Evidence Manifest Generator.

Executes all Week 4 acceptance query cases and records:
- Input parameters and query configuration
- Independent expected results (from #206/#214/#225, scoring #220, scenarios #218)
- Actual execution results from existing public APIs
- Exact command lines and revision hashes
- Semantic digests and output hashes
- Coverage and caps metadata
- Verdicts (PASS, FAIL / DEFECT CONFIRMED, PENDING, BLOCKED)
- Discrepancy dispositions (including explicit #212 defect analysis)

Reproducibility compares semantic results separately from observed execution metadata.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
import sys
from collections import Counter
from collections.abc import Mapping
from copy import deepcopy
from dataclasses import fields, is_dataclass, replace
from datetime import UTC, datetime
from importlib import metadata
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.research.kerberoasting_probe import (  # noqa: E402
    ranking_inputs,
)
from scripts.research.kerberoasting_probe import (  # noqa: E402
    synthetic as kerberoasting_fixture,
)
from scripts.research.week4_cli_acceptance import run_cli_acceptance  # noqa: E402
from src.engine import (  # noqa: E402
    AttackQuery,
    materialize_query,
    run_attack_query,
)
from src.engine.ranking import PathRankingEngine  # noqa: E402
from src.engine.ranking.assessment import assess_candidate_program  # noqa: E402
from src.engine.ranking.validation import decode_ranking_query  # noqa: E402
from src.engine.semantics import load_catalog  # noqa: E402
from src.engine.semantics.catalog import CATALOG_VERSION  # noqa: E402
from src.engine.semantics.transitions import Status, apply_transition  # noqa: E402

FIXTURES_DIR = ROOT / "tests" / "fixtures" / "attack_scenarios"
RATINGS_DIR = ROOT / "docs" / "research" / "ratings" / "week4"
TWO_ROUTES_GRAPH_PATH = FIXTURES_DIR / "graphs" / "two-routes.json"
PSREMOTE_GRAPH_PATH = FIXTURES_DIR / "graphs" / "psremote-command.json"

ALICE_ID = "S-1-5-21-1000-2000-3000-1101"
BOB_ID = "S-1-5-21-1000-2000-3000-1102"
HELPDESK_ID = "S-1-5-21-1000-2000-3000-2101"
OPERATORS_ID = "S-1-5-21-1000-2000-3000-2102"
ADMINS_ID = "S-1-5-21-1000-2000-3000-2103"
HOST_C0_ID = "10000000-0000-4000-8000-000000000002"
OTHERHOST_X_ID = "10000000-0000-4000-8000-000000000003"

ALIASES = {
    "Alice": ALICE_ID,
    "Bob": BOB_ID,
    "Helpdesk": HELPDESK_ID,
    "Operators": OPERATORS_ID,
    "Admins": ADMINS_ID,
    "Host": HOST_C0_ID,
    "OtherHost": OTHERHOST_X_ID,
}

PSREMOTE_ALIASES = {
    "Alice": ALICE_ID,
    "Host": HOST_C0_ID,
}

DEFAULT_RUNTIME_FACTS = [
    {
        "predicate": "admin_channel",
        "subject": "Alice",
        "target": "Host",
        "value": True,
        "origin": "observed_evidence",
        "scope": "two-routes:snapshot",
        "rationale": "observed admin channel",
        "provenance_reference": "evidence:admin-channel",
    },
    {
        "predicate": "authentication_accepted",
        "subject": "Alice",
        "target": "Host",
        "value": True,
        "origin": "observed_evidence",
        "scope": "two-routes:snapshot",
        "rationale": "observed auth accepted",
        "provenance_reference": "evidence:auth-accepted",
    },
    {
        "predicate": "security_group",
        "subject": "Alice",
        "target": "Admins",
        "value": True,
        "origin": "observed_evidence",
        "scope": "two-routes:snapshot",
        "rationale": "observed security group",
        "provenance_reference": "evidence:security-group",
    },
    {
        "predicate": "membership_usable",
        "subject": "Alice",
        "target": "Admins",
        "value": True,
        "origin": "observed_evidence",
        "scope": "two-routes:snapshot",
        "rationale": "observed usable membership",
        "provenance_reference": "evidence:usable-membership",
    },
]

DEFAULT_ACTION_BINDINGS = {
    ("obtain_admin_execution_on_host", "Alice", "Alice", "Host"): "action_direct_admin",
    ("propagate_group_entitlement", "Alice", "Alice", "Admins"): "action_member_admins",
    ("obtain_admin_execution_on_host", "Alice", "Admins", "Host"): "action_inherited_admin",
}


def compute_digest(obj: Any) -> str:
    """Compute canonical sha256 digest of any JSON-safe data structure."""
    payload = json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return f"sha256:{hashlib.sha256(payload.encode('utf-8')).hexdigest()}"


ORACLE_PATH = ROOT / "tests/fixtures/ranking/week4_acceptance_oracle.json"


def file_pins() -> dict[str, str]:
    """Pin the executed source, catalog, contracts and every acceptance input."""
    paths = set((ROOT / "src").rglob("*.py")) | set((ROOT / "configs").glob("*.yml"))
    paths |= {
        RATINGS_DIR / name
        for name in (
            "synthetic-a2-e.json",
            "synthetic-a2-t.json",
            "synthetic-a2-ties.json",
            "synthetic-a2-diagnostics.json",
        )
    }
    paths |= set(FIXTURES_DIR.rglob("*.json"))
    paths |= set((ROOT / "tests/fixtures/kerberoasting").glob("*.json"))
    paths |= set((ROOT / "tests/fixtures/asrep").glob("*.json"))
    paths |= set((ROOT / "tests/fixtures/rbcd").glob("*.json"))
    paths |= {
        ROOT / name
        for name in (
            "requirements.txt",
            "requirements-dev.txt",
            "requirements-tests.txt",
            "pyproject.toml",
            ".python-version",
            "scripts/check_contract.py",
            "scripts/research/week4_acceptance_runner.py",
            "scripts/research/kerberoasting_probe.py",
            "scripts/research/asrep_inputs.py",
            "scripts/research/credential_bindings.py",
            "scripts/research/rbcd_inputs.py",
            "tests/test_asrep.py",
            "tests/test_rbcd.py",
            "scripts/research/snapshot_facts_probe.py",
            "scripts/research/week4_scoring_eval.py",
            "scripts/research/week4_cli_acceptance.py",
            "scripts/research/compare_query_runs.py",
            "scripts/research/attack_scenarios.py",
            "tests/test_query_cli.py",
            "tests/test_week4_acceptance_checkout_bytes.py",
            "tests/fixtures/query_cli/two-routes-query.json",
            "docs/research/week4-query-cli.md",
            "docs/research/week4-query-result.schema.json",
            "tests/test_week4_acceptance_manifest.py",
            "tests/test_week4_acceptance_review_regressions.py",
            "data/samples/manifests/seamless-raw-v1.json",
            "tests/fixtures/ranking/seamless_time_policy.json",
            "docs/research/week4-query-scenario-mapping.md",
            "docs/research/week4-scenarios.md",
            "docs/research/week4-scoring-handoff.md",
            "docs/research/week4-extension-scenario-handoff.md",
            "docs/research/rbcd-229.md",
        )
    }
    paths.add(ORACLE_PATH)
    return {
        path.relative_to(ROOT).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(paths)
    }


def execution_metadata(revision: str | None) -> dict[str, Any]:
    """Observe the checkout instead of accepting a caller-provided source label."""
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    if revision is not None and revision != head:
        raise ValueError(f"revision must match executed HEAD {head}")
    pins = file_pins()
    tracked = subprocess.check_output(
        ["git", "ls-files"],
        cwd=ROOT,
        text=True,
    ).splitlines()
    # Compare bytes rather than trusting index/mtime state; include untracked inputs.
    changed = []
    for name in pins:
        committed = (
            subprocess.run(
                ["git", "show", f"HEAD:{name}"],
                cwd=ROOT,
                capture_output=True,
            )
            if name in tracked
            else None
        )
        if (
            committed is None
            or committed.returncode
            or hashlib.sha256(committed.stdout).hexdigest() != pins[name]
        ):
            changed.append(name)
    installed = {}
    for path in (
        ROOT / "requirements.txt",
        ROOT / "requirements-dev.txt",
        ROOT / "requirements-tests.txt",
    ):
        for line in path.read_text(encoding="utf-8").splitlines():
            if "==" in line and not line.startswith("#"):
                name = line.split("==", 1)[0]
                try:
                    installed[name] = metadata.version(name)
                except metadata.PackageNotFoundError:
                    installed[name] = None
    return {
        "executed_at": datetime.now(UTC).isoformat(),
        "executor": "automated_acceptance_runner; not human sign-off",
        "source": {
            "checkout_dirty": bool(
                subprocess.check_output(
                    ["git", "status", "--porcelain"], cwd=ROOT, text=True
                ).strip()
            ),
            "revision": head,
            "dirty_pinned_files": changed,
            "identity": "working_tree" if changed else "clean_commit",
        },
        "runtime": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "machine": platform.machine(),
            "installed_dependencies": installed,
        },
        "file_sha256": pins,
        "source_input_digest": compute_digest(pins),
        "catalog": {
            "version": CATALOG_VERSION,
            "technique_ids": sorted(t.id for t in load_catalog()),
        },
        "remote_dependency_status": "not_queried_by_runner; see dated worklog",
    }


def json_safe(value: Any) -> Any:
    """Serialize existing dataclasses without adding an engine or scoring model."""
    if is_dataclass(value):
        return {f.name: json_safe(getattr(value, f.name)) for f in fields(value)}
    if isinstance(value, Mapping):
        return {
            key if isinstance(key, str) else json.dumps(json_safe(key)): json_safe(item)
            for key, item in value.items()
        }
    if isinstance(value, (set, frozenset)):
        return sorted(
            (json_safe(item) for item in value), key=lambda item: json.dumps(item, sort_keys=True)
        )
    if isinstance(value, (tuple, list)):
        return [json_safe(item) for item in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise TypeError(f"Unsupported evidence value: {type(value).__name__}")


def transition_evidence(result: Any) -> dict[str, Any]:
    return {
        name: json_safe(getattr(result, name))
        for name in (
            "request",
            "status",
            "before",
            "additions",
            "failed",
            "unknown",
            "decisions",
        )
    }


def query_evidence(query: AttackQuery, result: Any) -> dict[str, Any]:
    inputs = {
        f.name: json_safe(getattr(query, f.name))
        for f in fields(query)
        if f.name not in {"graph", "ranking_query"}
        # An inactive public extension must preserve the accepted historical evidence.
        and not (f.name in {"rating_resolution", "top_k"} and getattr(query, f.name) is None)
        and not (f.name == "search_order" and getattr(query, f.name) == "fifo")
    }
    inputs["ranking_query_digest"] = compute_digest(query.ranking_query)
    evidence = {"query": inputs}
    if hasattr(result, "search_result"):
        evidence.update(
            {
                "caps": result.caps,
                "search_complete": result.search_result.complete,
                "search": {
                    "expansions": result.search_result.expansions,
                    "truncated": result.truncated,
                    "truncation_reason": result.truncation_reason,
                    "paths": [
                        {
                            "nodes": list(path.nodes),
                            "edge_ids": [edge["id"] for edge in path.edges],
                            "final_state": json_safe(path.final_state),
                            "steps": [
                                {
                                    "edge_id": step.edge_id,
                                    "derived_from_step": step.derived_from_step,
                                    "transition": transition_evidence(step.result),
                                }
                                for step in path.transition_history
                            ],
                        }
                        for path in result.paths
                    ],
                    "attempts": [
                        transition_evidence(attempt) for attempt in result.search_result.attempts
                    ],
                },
                "rejected_assumptions": [
                    r.to_dict() for r in result.materialized_query.rejected_assumptions
                ],
                "ranking": result.ranking_result,
            }
        )
    return evidence


def assertions(expected: dict[str, Any], actual: dict[str, Any]) -> list[dict[str, Any]]:
    """Every declared normative field gets a fail-closed comparison."""
    checks = []
    for field, value in expected.items():
        actual_field = field.removesuffix("_contains")
        observed = actual.get(actual_field)
        present = actual_field in actual
        if field.endswith("_contains"):
            passed = present and isinstance(observed, str) and value in observed
        else:
            passed = present and type(observed) is type(value) and observed == value
        checks.append(
            {
                "field": field,
                "expected": value,
                "actual": observed,
                "actual_present": present,
                "passed": passed,
            }
        )
    return checks


def evaluate_case(case: dict[str, Any]) -> None:
    """Assign a disposition from assertions and explicit observed defect signatures."""
    checks = assertions(case["expected"], case["actual"])
    case["assertions"] = checks
    complete = bool(checks) and all(c["passed"] for c in checks)
    case["normative_acceptance"] = complete
    if case.get("execution_status") == "not_executed":
        verdict = "NOT EXECUTED"
        if case["case_id"] == "W4-SEAMLESS-DATASET-GATE":
            verdict = (
                "BLOCKED RUN" if not case["actual"]["private_raw_data_present"] else "NOT EXECUTED"
            )
        disposition = "Normative expectation not evaluated; " + case["dependency"]
        case["evidence_class"] = (
            "prerequisite_observation_only"
            if verdict == "BLOCKED RUN"
            else "manual_check_not_executed"
        )
    elif complete:
        verdict = "PASS"
        disposition = (
            "All independent expected assertions satisfied within declared synthetic scope."
        )
    else:
        known = assertions(case.get("known_observation", {}), case["actual"])
        pending = assertions(case.get("pending_observation", {}), case["actual"])
        if known and all(c["passed"] for c in known):
            verdict = "KNOWN DEFECT"
            disposition = (
                "Normative expectation failed; observed known defect signature. "
                + case["dependency"]
            )
        elif pending and all(c["passed"] for c in pending):
            verdict = "PENDING B"
            disposition = (
                "Normative expectation unmet; observed unsupported interface. " + case["dependency"]
            )
        else:
            verdict = "FAIL"
            disposition = "Unexpected independent expectation mismatch: " + ", ".join(
                c["field"] for c in checks if not c["passed"]
            )
    case["verdict"] = verdict
    case["disposition"] = disposition
    case["output_digest"] = compute_digest(case["actual"])


def summarize(cases: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "total_cases": len(cases),
        **{
            key: sum(c["verdict"] == verdict for c in cases)
            for key, verdict in (
                ("pass_count", "PASS"),
                ("known_defect_count", "KNOWN DEFECT"),
                ("unexpected_failure_count", "FAIL"),
                ("pending_count", "PENDING B"),
                ("not_executed_count", "NOT EXECUTED"),
                ("blocked_run_count", "BLOCKED RUN"),
            )
        },
    }


def semantic_payload(manifest: dict[str, Any]) -> dict[str, Any]:
    """Compare results separately from timestamps, checkout identity and runtime."""
    payload = {key: value for key, value in manifest.items() if key != "execution"}
    payload["cases"] = [
        {
            **{key: value for key, value in case.items() if key != "evidence"},
            **({"evidence_digest": compute_digest(case["evidence"])} if "evidence" in case else {}),
        }
        for case in manifest["cases"]
    ]
    return payload


def coverage_witness_evidence(query: AttackQuery, result: Any) -> dict[str, Any]:
    """One goal witness proves existential coverage; disclose other paths/attempts."""
    evidence = query_evidence(query, result)
    search = evidence["search"]
    search["generated_paths_count"] = len(search["paths"])
    search["all_paths_digest"] = compute_digest(search["paths"])
    search["paths"] = search["paths"][:1]
    search["path_trace_policy"] = "first_goal_witness_only; other paths represented by digest"
    attempts = search.pop("attempts")
    search["attempt_summary"] = {
        "count": len(attempts),
        "status_counts": dict(sorted(Counter(str(a["status"]) for a in attempts).items())),
        "all_attempts_digest": compute_digest(attempts),
    }
    return evidence


def kerberoasting_cases() -> list[dict[str, Any]]:
    """Execute B's public API; independent A expectations remain in ORACLE_PATH."""
    graph, query = kerberoasting_fixture()
    original = deepcopy(graph.to_canonical())
    ranking_query, bindings = ranking_inputs(graph, query)
    q_on = AttackQuery(**query, action_bindings=bindings, ranking_query=ranking_query)
    result = run_attack_query(q_on, graph=graph)
    q_off = replace(
        q_on, allowed_techniques=["propagate_group_entitlement", "scenario_winrm_admin"]
    )
    baseline = run_attack_query(q_off, graph=graph)
    assessment = (
        result.ranking_result.get("diagnostics", {}).get("generated_0001", {}).get("assessment", {})
    )
    path = result.paths[0] if result.paths else None
    milestones = []
    if path:
        for step in path.transition_history:
            state = apply_transition(step.result.before, step.result)
            milestones.append(
                {
                    "ticket_material": bool(state.service_ticket_material),
                    "recovered_secret": bool(state.recovered_secret),
                    "activated_target": (
                        query["initial_state"]["known_identity"][0],
                        query["authentication_context"],
                    )
                    in state.usable_identity,
                    "member": bool(state.effective_member),
                    "admin": bool(state.admin_control),
                }
            )
    cases = [
        {
            "case_id": "W4-TECH-KERBEROASTING",
            "category": "extension_technique",
            "description": "Generated credential chain and asset action; unrated C/P/I",
            "inputs": {"fixture": "scripts/research/kerberoasting_probe.py:synthetic"},
            "actual": {
                "extension_off_status": baseline.status,
                "extension_off_paths": len(baseline.paths),
                "extension_on_status": result.status,
                "extension_on_paths": len(result.paths),
                "programs": [
                    [s.result.request.technique_id for s in p.transition_history]
                    for p in result.paths
                ],
                "actors": [s.result.request.actor for s in path.transition_history] if path else [],
                "milestones": milestones,
                "asset_goal": result.final_goal_reached,
                "checkpoint": result.checkpoint_reached,
                "truncated": result.truncated,
                "assumption_backed": any(
                    s.result.is_assumption_backed
                    for p in result.paths
                    for s in p.transition_history
                ),
                "candidates_adapted": result.ranking_result["search_audit"]["candidates_adapted"],
                "effort_status": assessment.get("effort_status"),
                "effort": assessment.get("effort"),
                "likelihood_status": assessment.get("likelihood_status"),
                "likelihood_interval": assessment.get("likelihood_interval"),
                "impact_status": assessment.get("impact_status"),
                "impact": assessment.get("impact"),
                "minimum_effort_value": (result.min_effort or {}).get("minimum_effort_value"),
                "is_minimum_proven_over_scope": result.is_minimum_proven_over_scope,
                "pareto_frontier": result.ranking_result["pareto_frontier"],
                "shared_inputs_equal": replace(q_on, allowed_techniques=None)
                == replace(q_off, allowed_techniques=None),
                "canonical_unchanged": graph.to_canonical() == original,
            },
            "command": "run_attack_query(q_off, graph) vs run_attack_query(q_on, graph)",
            "coverage": "generated_synthetic_program_and_unrated_assessment",
            "evidence": {
                "extension_off": query_evidence(q_off, baseline),
                "extension_on": query_evidence(q_on, result),
                "snapshot_digest": compute_digest(original),
            },
        }
    ]
    for case_id, predicate, value in (
        ("W4-K-MATERIAL", "recovery_success", None),
        ("W4-K-KDC-F", "network_kdc_reachable", False),
        ("W4-K-KDC-U", "network_kdc_reachable", None),
        ("W4-K-AUTH-F", "authentication_accepted", False),
        ("W4-K-NO-AUTH", None, None),
        ("W4-K-FACT-F", "has_spn", False),
        ("W4-K-FACT-U", "has_spn", None),
    ):
        if predicate == "has_spn":
            variant_graph, variant = kerberoasting_fixture(spn=value)
        else:
            variant_graph, variant = graph, deepcopy(query)
            if predicate is None:
                variant["initial_actor"] = variant["source_foothold"]
                variant["initial_state"]["usable_identity"] = []
            else:
                for fact in variant["assumptions"]:
                    if fact["predicate"] == predicate:
                        fact["value"] = value
        before = deepcopy(variant_graph.to_canonical())
        variant_query = AttackQuery(**variant)
        actual = run_attack_query(variant_query, graph=variant_graph)
        state = actual.materialized_query.initial_attack_state
        if actual.attempts:
            last = actual.attempts[-1]
            state = apply_transition(last.before, last)
        cases.append(
            {
                "case_id": case_id,
                "category": "extension_technique",
                "description": "Kerberoasting independent cutoff; preserve applicable prefix only",
                "inputs": {"changed_predicate": predicate, "value": value},
                "actual": {
                    "status": actual.status,
                    "paths_count": len(actual.paths),
                    "asset_goal": actual.final_goal_reached,
                    "checkpoint": actual.checkpoint_reached,
                    "applied_prefix": [
                        a.request.technique_id
                        for a in actual.attempts
                        if a.status == Status.APPLICABLE
                    ],
                    "ticket_material": bool(state.service_ticket_material),
                    "recovered_secret": bool(state.recovered_secret),
                    "activated_target": (
                        query["initial_state"]["known_identity"][0],
                        query["authentication_context"],
                    )
                    in state.usable_identity,
                    "canonical_unchanged": variant_graph.to_canonical() == before,
                },
                "command": "run_attack_query(variant_query, graph=variant_graph)",
                "coverage": "generated_synthetic_cutoff",
                "evidence": query_evidence(variant_query, actual),
            }
        )
    overlap_graph, overlap = kerberoasting_fixture(overlap=True)
    before = deepcopy(overlap_graph.to_canonical())
    from src.engine.semantics.credentials import OWNERS

    overlap_on = AttackQuery(**overlap)
    overlap_off = replace(
        overlap_on, allowed_techniques=[t for t in overlap_on.allowed_techniques if t not in OWNERS]
    )
    base = run_attack_query(overlap_off, graph=overlap_graph)
    extension = run_attack_query(overlap_on, graph=overlap_graph)
    cases.append(
        {
            "case_id": "W4-K-OVERLAP",
            "category": "extension_technique",
            "description": "Existing reset route reaches same asset; bounded coverage comparison",
            "inputs": {"fixture": "synthetic(overlap=True)"},
            "actual": {
                "baseline_asset_goal": base.final_goal_reached,
                "extension_asset_goal": extension.final_goal_reached,
                "new_asset_coverage": extension.final_goal_reached and not base.final_goal_reached,
                "shared_inputs_equal": replace(overlap_on, allowed_techniques=None)
                == replace(overlap_off, allowed_techniques=None),
                "scope": "generated_scope",
                "shared_caps": json_safe(overlap_on.budget),
                "baseline_truncated": base.truncated,
                "extension_truncated": extension.truncated,
                "extension_truncation_reason": extension.truncation_reason,
                "canonical_unchanged": overlap_graph.to_canonical() == before,
            },
            "command": "run_attack_query(overlap_off) vs run_attack_query(overlap_on)",
            "coverage": "same_input_generated_scope_coverage_comparison",
            "evidence": {
                "extension_off": coverage_witness_evidence(overlap_off, base),
                "extension_on": coverage_witness_evidence(overlap_on, extension),
                "snapshot_digest": compute_digest(before),
            },
        }
    )
    return cases


def run_all_cases(revision: str | None = None) -> dict[str, Any]:
    """Execute all acceptance cases and collect structured records."""
    execution = execution_metadata(revision)
    two_routes_raw = json.loads(TWO_ROUTES_GRAPH_PATH.read_text(encoding="utf-8"))
    psremote_raw = json.loads(PSREMOTE_GRAPH_PATH.read_text(encoding="utf-8"))
    ledger_e_pkg = json.loads((RATINGS_DIR / "synthetic-a2-e.json").read_text(encoding="utf-8"))
    ledger_t_pkg = json.loads((RATINGS_DIR / "synthetic-a2-t.json").read_text(encoding="utf-8"))
    ties_pkg = json.loads((RATINGS_DIR / "synthetic-a2-ties.json").read_text(encoding="utf-8"))
    diag_pkg = json.loads(
        (RATINGS_DIR / "synthetic-a2-diagnostics.json").read_text(encoding="utf-8")
    )

    cases: list[dict[str, Any]] = []

    # =========================================================================
    # Group 1: Q-ASSET & Input Variations (Changed Source / Target / Identity)
    # =========================================================================

    # Case 1: W4-M (Baseline Q-ASSET from Foothold Host with Alice Usable Identity)
    q_m = AttackQuery(
        target="Host",
        source_foothold="OtherHost",
        initial_actor="Alice",
        initial_state={
            "control": ["OtherHost"],
            "usable_identity": [["Alice", "Host"]],
        },
        authentication_context="Host",
        target_goal={"target": "Host", "required_state": {"admin_control": ["Host"]}},
        runtime_facts=DEFAULT_RUNTIME_FACTS,
        allowed_techniques=["obtain_admin_execution_on_host", "propagate_group_entitlement"],
        aliases=ALIASES,
    )
    res_m = run_attack_query(q_m, graph=two_routes_raw)
    cases.append(
        {
            "case_id": "W4-M-POSITIVE",
            "category": "core_query_asset",
            "description": (
                "Baseline Q-ASSET: Foothold Computer OtherHost + Alice usable at Host -> dynamic "
                "generation of 3 paths"
            ),
            "inputs": {
                "source_foothold": "OtherHost",
                "initial_actor": "Alice",
                "authentication_context": "Host",
                "usable_identity": [["Alice", "Host"]],
                "target": "Host",
            },
            "actual": {
                "status": res_m.status,
                "paths_count": len(res_m.paths),
                "final_goal_reached": res_m.final_goal_reached,
                "checkpoint_reached": res_m.checkpoint_reached,
                "program_routes": [
                    [
                        [
                            step.result.request.technique_id,
                            step.result.request.actor,
                            step.result.request.source,
                            step.result.request.target,
                        ]
                        for step in path.transition_history
                    ]
                    for path in res_m.paths
                ],
                "programs": [
                    [step.result.request.technique_id for step in path.transition_history]
                    for path in res_m.paths
                ],
            },
            "command": "run_attack_query(q_m, graph=two_routes_raw)",
            "coverage": "complete_3_paths",
        }
    )

    # Case 2: W4-X/S (Foothold switch without usable identity -> Fail-Fast ValueError)
    error_msg = ""
    try:
        materialize_query(
            {
                "source_foothold": "OtherHost",
                "initial_actor": "Alice",
                "initial_state": {"control": ["OtherHost"]},
                "target": "Host",
                "target_goal": {"target": "Host", "required_state": {"admin_control": ["Host"]}},
                "aliases": ALIASES,
            },
            graph=two_routes_raw,
        )
    except ValueError as exc:
        error_msg = str(exc)

    cases.append(
        {
            "case_id": "W4-X-S",
            "category": "core_query_input_separation",
            "description": (
                "Foothold Computer with domain user actor without declared usable_identity raises "
                "ValueError"
            ),
            "inputs": {
                "source_foothold": "OtherHost",
                "initial_actor": "Alice",
                "declared_usable_identity": None,
            },
            "actual": {
                "error_type": "ValueError" if error_msg else "None",
                "error_message": error_msg,
            },
            "command": "materialize_query(query_dict, graph=two_routes_raw)",
            "coverage": "fail_closed_validation",
        }
    )

    # Case 3: W4-X/I (Foothold Computer alone without user identity -> 0 paths, no_path)
    q_x_i = AttackQuery(
        target="Host",
        source_foothold="OtherHost",
        initial_state={"control": ["OtherHost"]},
        target_goal={"target": "Host", "required_state": {"admin_control": ["Host"]}},
        runtime_facts=DEFAULT_RUNTIME_FACTS,
        allowed_techniques=["obtain_admin_execution_on_host", "propagate_group_entitlement"],
        aliases=ALIASES,
    )
    res_x_i = run_attack_query(q_x_i, graph=two_routes_raw)
    cases.append(
        {
            "case_id": "W4-X-I",
            "category": "core_query_input_separation",
            "description": (
                "Foothold Computer alone (initial_actor=OtherHost) finds 0 paths to Host"
            ),
            "inputs": {
                "source_foothold": "OtherHost",
                "initial_actor": "OtherHost",
                "initial_state": {"control": ["OtherHost"]},
            },
            "actual": {
                "status": res_x_i.status,
                "paths_count": len(res_x_i.paths),
                "final_goal_reached": res_x_i.final_goal_reached,
            },
            "command": "run_attack_query(q_x_i, graph=two_routes_raw)",
            "coverage": "exhaustive_within_scope",
        }
    )

    # Case 4: W4-X/H (Wrong Authentication Context -> status blocked)
    q_x_h = AttackQuery(
        target="Host",
        source_foothold="OtherHost",
        initial_actor="Alice",
        initial_state={
            "control": ["OtherHost"],
            "usable_identity": [["Alice", "Host"]],
        },
        authentication_context="OtherHost",
        target_goal={"target": "Host", "required_state": {"admin_control": ["Host"]}},
        runtime_facts=DEFAULT_RUNTIME_FACTS,
        allowed_techniques=["obtain_admin_execution_on_host", "propagate_group_entitlement"],
        aliases=ALIASES,
    )
    res_x_h = run_attack_query(q_x_h, graph=two_routes_raw)
    cases.append(
        {
            "case_id": "W4-X-H-WRONG",
            "category": "core_query_input_separation",
            "description": (
                "Usable identity scoped to Host executed in OtherHost auth context -> blocked"
            ),
            "inputs": {
                "usable_identity": [["Alice", "Host"]],
                "authentication_context": "OtherHost",
            },
            "actual": {
                "status": res_x_h.status,
                "paths_count": len(res_x_h.paths),
                "final_goal_reached": res_x_h.final_goal_reached,
            },
            "command": "run_attack_query(q_x_h, graph=two_routes_raw)",
            "coverage": "blocked_auth_scope",
        }
    )

    # Case 5: W4-X/H-VALID (Matching Auth Context -> success, 3 paths)
    q_x_h_val = AttackQuery(
        target="Host",
        source_foothold="OtherHost",
        initial_actor="Alice",
        initial_state={
            "control": ["OtherHost"],
            "usable_identity": [["Alice", "Host"]],
        },
        authentication_context="Host",
        target_goal={"target": "Host", "required_state": {"admin_control": ["Host"]}},
        runtime_facts=DEFAULT_RUNTIME_FACTS,
        allowed_techniques=["obtain_admin_execution_on_host", "propagate_group_entitlement"],
        aliases=ALIASES,
    )
    res_x_h_val = run_attack_query(q_x_h_val, graph=two_routes_raw)
    cases.append(
        {
            "case_id": "W4-X-H-VALID",
            "category": "core_query_input_separation",
            "description": (
                "Usable identity scoped to Host executed in matching Host auth context -> success"
            ),
            "inputs": {
                "usable_identity": [["Alice", "Host"]],
                "authentication_context": "Host",
            },
            "actual": {
                "status": res_x_h_val.status,
                "paths_count": len(res_x_h_val.paths),
                "final_goal_reached": res_x_h_val.final_goal_reached,
            },
            "command": "run_attack_query(q_x_h_val, graph=two_routes_raw)",
            "coverage": "complete_3_paths",
        }
    )

    # =========================================================================
    # Group 2: DA Checkpoint vs Final Asset Goal Separation
    # =========================================================================

    # Case 6: W4-C/F (Checkpoint reached, final asset gate authoritative False)
    facts_c_f = [f for f in DEFAULT_RUNTIME_FACTS if f["predicate"] != "admin_channel"] + [
        {
            "predicate": "admin_channel",
            "subject": "Alice",
            "target": "Host",
            "value": False,
            "origin": "blocked_evidence",
            "scope": "two-routes:snapshot",
            "rationale": "admin channel disabled",
            "provenance_reference": "evidence:blocked-channel",
        }
    ]
    q_c_f = AttackQuery(
        target="Host",
        initial_actor="Alice",
        initial_state={"control": ["Alice"]},
        target_goal={"target": "Host", "required_state": {"admin_control": ["Host"]}},
        checkpoint_goal={
            "target": "Admins",
            "required_state": {"effective_member": [["Alice", "Admins"]]},
        },
        runtime_facts=facts_c_f,
        allowed_techniques=["obtain_admin_execution_on_host", "propagate_group_entitlement"],
        aliases=ALIASES,
    )
    res_c_f = run_attack_query(q_c_f, graph=two_routes_raw)
    cases.append(
        {
            "case_id": "W4-C-F",
            "category": "checkpoint_asset_separation",
            "description": "DA checkpoint reached, but final asset gate admin_channel=False",
            "inputs": {
                "checkpoint_goal": "effective_member(Alice, Admins)",
                "admin_channel": False,
            },
            "actual": {
                "status": res_c_f.status,
                "checkpoint_reached": res_c_f.checkpoint_reached,
                "final_goal_reached": res_c_f.final_goal_reached,
                "paths_count": len(res_c_f.paths),
            },
            "command": "run_attack_query(q_c_f, graph=two_routes_raw)",
            "coverage": "checkpoint_reached_asset_blocked",
        }
    )

    # Case 7: W4-C/U (Checkpoint reached, final asset gate missing/unknown)
    facts_c_u = [f for f in DEFAULT_RUNTIME_FACTS if f["predicate"] != "admin_channel"]
    q_c_u = AttackQuery(
        target="Host",
        initial_actor="Alice",
        initial_state={"control": ["Alice"]},
        target_goal={"target": "Host", "required_state": {"admin_control": ["Host"]}},
        checkpoint_goal={
            "target": "Admins",
            "required_state": {"effective_member": [["Alice", "Admins"]]},
        },
        runtime_facts=facts_c_u,
        allowed_techniques=["obtain_admin_execution_on_host", "propagate_group_entitlement"],
        aliases=ALIASES,
    )
    res_c_u = run_attack_query(q_c_u, graph=two_routes_raw)
    cases.append(
        {
            "case_id": "W4-C-U",
            "category": "checkpoint_asset_separation",
            "description": (
                "DA checkpoint reached, but final asset gate admin_channel is missing without "
                "assumption"
            ),
            "inputs": {
                "checkpoint_goal": "effective_member(Alice, Admins)",
                "admin_channel": "missing",
            },
            "actual": {
                "status": res_c_u.status,
                "checkpoint_reached": res_c_u.checkpoint_reached,
                "final_goal_reached": res_c_u.final_goal_reached,
                "paths_count": len(res_c_u.paths),
            },
            "command": "run_attack_query(q_c_u, graph=two_routes_raw)",
            "coverage": "checkpoint_reached_asset_indeterminate",
        }
    )

    # Case 8: W4-DA-NEGATIVE-ASSET-POSITIVE (Asset reached directly without DA checkpoint)
    facts_c_neg = [f for f in DEFAULT_RUNTIME_FACTS if f["predicate"] != "membership_usable"] + [
        {
            "predicate": "membership_usable",
            "subject": "Alice",
            "target": "Admins",
            "value": False,
            "origin": "blocked_evidence",
            "scope": "two-routes:snapshot",
            "rationale": "group membership propagation blocked",
            "provenance_reference": "evidence:blocked-member",
        }
    ]
    q_da_neg = AttackQuery(
        target="Host",
        initial_actor="Alice",
        initial_state={"control": ["Alice"]},
        target_goal={"target": "Host", "required_state": {"admin_control": ["Host"]}},
        checkpoint_goal={
            "target": "Admins",
            "required_state": {"effective_member": [["Alice", "Admins"]]},
        },
        runtime_facts=facts_c_neg,
        allowed_techniques=["obtain_admin_execution_on_host", "propagate_group_entitlement"],
        aliases=ALIASES,
    )
    res_da_neg = run_attack_query(q_da_neg, graph=two_routes_raw)
    cases.append(
        {
            "case_id": "W4-DA-NEG-ASSET-POS",
            "category": "checkpoint_asset_separation",
            "description": (
                "Asset goal reached directly via AdminTo; DA checkpoint blocked -> status success, "
                "checkpoint_reached=False"
            ),
            "inputs": {
                "checkpoint_goal": "effective_member(Alice, Admins)",
                "membership_usable": False,
            },
            "actual": {
                "status": res_da_neg.status,
                "checkpoint_reached": res_da_neg.checkpoint_reached,
                "final_goal_reached": res_da_neg.final_goal_reached,
                "paths_count": len(res_da_neg.paths),
            },
            "command": "run_attack_query(q_da_neg, graph=two_routes_raw)",
            "coverage": "asset_reached_without_checkpoint",
        }
    )

    # =========================================================================
    # Group 3: Q-GATES: Missing, Assumptions, and Known-False Veto
    # =========================================================================

    # Case 8b: W4-DA-POS (Both DA checkpoint and final asset goal reached)
    q_da_pos = AttackQuery(
        target="Host",
        initial_actor="Alice",
        initial_state={"control": ["Alice"]},
        target_goal={"target": "Host", "required_state": {"admin_control": ["Host"]}},
        checkpoint_goal={
            "target": "Admins",
            "required_state": {"effective_member": [["Alice", "Admins"]]},
        },
        runtime_facts=DEFAULT_RUNTIME_FACTS,
        allowed_techniques=["obtain_admin_execution_on_host", "propagate_group_entitlement"],
        aliases=ALIASES,
    )
    res_da_pos = run_attack_query(q_da_pos, graph=two_routes_raw)
    cases.append(
        {
            "case_id": "W4-DA-POS",
            "category": "checkpoint_asset_separation",
            "description": (
                "Both DA checkpoint and final asset goal are reached -> status success, "
                "checkpoint_reached=True, final_goal_reached=True"
            ),
            "inputs": {
                "checkpoint_goal": "effective_member(Alice, Admins)",
                "target_goal": "admin_control(Host)",
                "runtime_facts": "all observed true",
            },
            "actual": {
                "status": res_da_pos.status,
                "checkpoint_reached": res_da_pos.checkpoint_reached,
                "final_goal_reached": res_da_pos.final_goal_reached,
                "paths_count": len(res_da_pos.paths),
            },
            "command": "run_attack_query(q_da_pos, graph=two_routes_raw)",
            "coverage": "both_checkpoint_and_asset_reached",
        }
    )

    # Case 9: W4-G/U (Missing fact -> indeterminate)
    facts_sparse_psremote = [
        {
            "predicate": "authentication_accepted",
            "subject": "Alice",
            "target": "Host",
            "value": True,
            "origin": "observed_evidence",
            "scope": "psremote:test",
            "rationale": "auth observed",
            "provenance_reference": "evidence:ps-auth",
        }
    ]
    q_g_u = AttackQuery(
        target="Host",
        initial_actor="Alice",
        initial_state={"control": ["Alice"]},
        target_goal={
            "target": "Host",
            "required_state": {"remote_command_execution": [["Alice", "Host"]]},
        },
        runtime_facts=facts_sparse_psremote,
        allowed_techniques=["open_winrm_remote_session"],
        aliases=PSREMOTE_ALIASES,
    )
    res_g_u = run_attack_query(q_g_u, graph=psremote_raw)
    cases.append(
        {
            "case_id": "W4-G-U",
            "category": "runtime_facts_and_assumptions",
            "description": (
                "Missing required fact winrm_available without assumption -> status indeterminate"
            ),
            "inputs": {"missing_fact": "winrm_available"},
            "actual": {
                "status": res_g_u.status,
                "final_goal_reached": res_g_u.final_goal_reached,
                "indeterminate_attempts_present": any(
                    a.status == "indeterminate" for a in res_g_u.search_result.attempts
                ),
                "paths_count": len(res_g_u.paths),
            },
            "command": "run_attack_query(q_g_u, graph=psremote_raw)",
            "coverage": "missing_fact_indeterminate",
        }
    )

    # Case 10: W4-G/A (Declared assumption enables scenario execution)
    valid_assumption = [
        {
            "predicate": "winrm_available",
            "subject": "Alice",
            "target": "Host",
            "value": True,
            "origin": "declared_assumption",
            "scope": "psremote:scenario",
            "rationale": "Synthetic assumption of WinRM service availability",
            "provenance_reference": "evidence:winrm-doc",
            "assumption_metadata": {"declared_by": "ttsA-tester"},
        }
    ]
    q_g_a = AttackQuery(
        target="Host",
        initial_actor="Alice",
        initial_state={"control": ["Alice"]},
        target_goal={
            "target": "Host",
            "required_state": {"remote_command_execution": [["Alice", "Host"]]},
        },
        runtime_facts=facts_sparse_psremote,
        assumptions=valid_assumption,
        allowed_techniques=["open_winrm_remote_session"],
        aliases=PSREMOTE_ALIASES,
    )
    res_g_a = run_attack_query(q_g_a, graph=psremote_raw)
    cases.append(
        {
            "case_id": "W4-G-A",
            "category": "runtime_facts_and_assumptions",
            "description": (
                "Valid declared assumption with scope and rationale enables scenario execution -> "
                "success"
            ),
            "inputs": {"declared_assumption": "winrm_available=True"},
            "actual": {
                "status": res_g_a.status,
                "final_goal_reached": res_g_a.final_goal_reached,
                "assumption_backed": any(
                    step.result.is_assumption_backed
                    for path in res_g_a.paths
                    for step in path.transition_history
                ),
                "paths_count": len(res_g_a.paths),
            },
            "command": "run_attack_query(q_g_a, graph=psremote_raw)",
            "coverage": "scenario_assumption_success",
        }
    )

    # Case 10b: W4-G/F (Authoritative false fact without assumption -> status blocked)
    facts_false_standalone = list(facts_sparse_psremote) + [
        {
            "predicate": "winrm_available",
            "subject": "Alice",
            "target": "Host",
            "value": False,
            "origin": "blocked_evidence",
            "scope": "psremote:standalone",
            "rationale": "port 5985 closed by firewall",
            "provenance_reference": "evidence:fw-rule-blocked",
        }
    ]
    q_g_f = AttackQuery(
        target="Host",
        initial_actor="Alice",
        initial_state={"control": ["Alice"]},
        target_goal={
            "target": "Host",
            "required_state": {"remote_command_execution": [["Alice", "Host"]]},
        },
        runtime_facts=facts_false_standalone,
        allowed_techniques=["open_winrm_remote_session"],
        aliases=PSREMOTE_ALIASES,
    )
    res_g_f = run_attack_query(q_g_f, graph=psremote_raw)
    cases.append(
        {
            "case_id": "W4-G-F",
            "category": "runtime_facts_and_assumptions",
            "description": (
                "Authoritative false fact winrm_available=False without assumption -> status "
                "blocked"
            ),
            "inputs": {"authoritative_fact": "winrm_available=False"},
            "actual": {
                "status": res_g_f.status,
                "final_goal_reached": res_g_f.final_goal_reached,
                "blocked_attempts_present": any(
                    a.status == "blocked" for a in res_g_f.search_result.attempts
                ),
                "paths_count": len(res_g_f.paths),
            },
            "command": "run_attack_query(q_g_f, graph=psremote_raw)",
            "coverage": "authoritative_blocked",
        }
    )

    # Case 11: W4-G/VETO (Authoritative false vetoes optimistic assumption)
    facts_false_winrm = list(facts_sparse_psremote) + [
        {
            "predicate": "winrm_available",
            "subject": "Alice",
            "target": "Host",
            "value": False,
            "origin": "blocked_evidence",
            "scope": "psremote:scenario",
            "rationale": "port 5985 closed by firewall",
            "provenance_reference": "evidence:fw-rule-blocked",
        }
    ]
    q_g_veto = AttackQuery(
        target="Host",
        initial_actor="Alice",
        initial_state={"control": ["Alice"]},
        target_goal={
            "target": "Host",
            "required_state": {"remote_command_execution": [["Alice", "Host"]]},
        },
        runtime_facts=facts_false_winrm,
        assumptions=valid_assumption,
        allowed_techniques=["open_winrm_remote_session"],
        aliases=PSREMOTE_ALIASES,
    )
    res_g_veto = run_attack_query(q_g_veto, graph=psremote_raw)
    cases.append(
        {
            "case_id": "W4-G-VETO",
            "category": "runtime_facts_and_assumptions",
            "description": (
                "Authoritative false fact vetoes declared assumption true and records audit trace "
                "in rejected_assumptions"
            ),
            "inputs": {
                "authoritative_fact": "winrm_available=False",
                "declared_assumption": "winrm_available=True",
            },
            "actual": {
                "status": res_g_veto.status,
                "final_goal_reached": res_g_veto.final_goal_reached,
                "rejected_assumptions_count": len(
                    res_g_veto.materialized_query.rejected_assumptions
                ),
                "rejection_reasons": [
                    r.reason for r in res_g_veto.materialized_query.rejected_assumptions
                ],
            },
            "command": "run_attack_query(q_g_veto, graph=psremote_raw)",
            "coverage": "authoritative_veto",
        }
    )

    # =========================================================================
    # Group 4: Q-MULTI & Min-Effort (Ledger E, Ledger T, Anti-Double-Counting)
    # =========================================================================

    # Case 12: W4-MIN-EFFORT-E (Counter-structural Min-Effort under Ledger E)
    q_min_e = AttackQuery(
        initial_actor="Alice",
        initial_state={"control": ["Alice"]},
        target="Host",
        target_goal={"target": "Host", "required_state": {"admin_control": ["Host"]}},
        aliases=ALIASES,
        runtime_facts=DEFAULT_RUNTIME_FACTS,
        allowed_techniques=["propagate_group_entitlement", "obtain_admin_execution_on_host"],
        budget={"max_paths": 1000, "max_steps": 12, "max_expansions": 100000},
        action_bindings=DEFAULT_ACTION_BINDINGS,
        ranking_query=ledger_e_pkg["query"],
    )
    res_min_e = run_attack_query(q_min_e, two_routes_raw)
    cases.append(
        {
            "case_id": "W4-MIN-EFFORT-E",
            "category": "min_effort_scoring",
            "description": (
                "Counter-structural Min-Effort: 2-step M/I (effort 2) beats 1-step D (effort 5) "
                "under Ledger E"
            ),
            "inputs": {
                "scoring_ledger": "Ledger E",
                "budget": {"max_paths": 1000, "max_steps": 12, "max_expansions": 100000},
            },
            "actual": {
                "minimum_effort_value": (
                    res_min_e.min_effort.get("minimum_effort_value")
                    if res_min_e.min_effort
                    else None
                ),
                "best_candidate_id": (
                    res_min_e.min_effort.get("best_candidate_id") if res_min_e.min_effort else None
                ),
                "optimization_scope": res_min_e.optimization_scope,
                "efforts": {
                    cid: c["effort"]
                    for cid, c in (res_min_e.ranking_result or {})
                    .get("eligible_candidates", {})
                    .items()
                },
                "likelihoods": {
                    cid: c["likelihood_interval"]
                    for cid, c in (res_min_e.ranking_result or {})
                    .get("eligible_candidates", {})
                    .items()
                },
                "impacts": {
                    cid: c["impact"]
                    for cid, c in (res_min_e.ranking_result or {})
                    .get("eligible_candidates", {})
                    .items()
                },
                "is_minimum_proven_over_scope": res_min_e.is_minimum_proven_over_scope,
            },
            "command": "run_attack_query(q_min_e, two_routes_raw)",
            "coverage": "exhaustive_within_scope",
        }
    )

    # Case 13: W4-MIN-EFFORT-T (3-Way Min-Effort Tie under Ledger T)
    q_min_t = AttackQuery(
        initial_actor="Alice",
        initial_state={"control": ["Alice"]},
        target="Host",
        target_goal={"target": "Host", "required_state": {"admin_control": ["Host"]}},
        aliases=ALIASES,
        runtime_facts=DEFAULT_RUNTIME_FACTS,
        allowed_techniques=["propagate_group_entitlement", "obtain_admin_execution_on_host"],
        budget={"max_paths": 1000, "max_steps": 12, "max_expansions": 100000},
        action_bindings=DEFAULT_ACTION_BINDINGS,
        ranking_query=ledger_t_pkg["query"],
    )
    res_min_t = run_attack_query(q_min_t, two_routes_raw)
    cases.append(
        {
            "case_id": "W4-MIN-EFFORT-T",
            "category": "min_effort_scoring",
            "description": (
                "3-way Min-Effort tie: D (effort 2), M/D (effort 2), M/I (effort 2) all tied"
            ),
            "inputs": {"scoring_ledger": "Ledger T"},
            "actual": {
                "minimum_effort_value": (
                    res_min_t.min_effort.get("minimum_effort_value")
                    if res_min_t.min_effort
                    else None
                ),
                "all_best_candidate_ids": (res_min_t.min_effort or {}).get(
                    "all_best_candidate_ids", []
                ),
                "tie_count": (
                    res_min_t.min_effort.get("tie_count") if res_min_t.min_effort else None
                ),
                "all_best_candidates_count": (
                    len(res_min_t.min_effort.get("all_best_candidate_ids", []))
                    if res_min_t.min_effort
                    else 0
                ),
            },
            "command": "run_attack_query(q_min_t, two_routes_raw)",
            "coverage": "exhaustive_within_scope",
        }
    )

    # Case 13b: W4-MIN-EFFORT-TIES (ADR-0013 Section 4 point likelihood tie-break)
    res_ties = PathRankingEngine(version="1.0.0").evaluate(
        query_payload=ties_pkg["query"],
        candidates=ties_pkg["candidates"],
    )
    ties_frontier = list(res_ties["result_payload"]["pareto_frontier"])
    cases.append(
        {
            "case_id": "W4-MIN-EFFORT-TIES",
            "category": "min_effort_scoring",
            "description": (
                "ADR-0013 Sec 4 point likelihood tie-break: M/I (effort 2) strictly dominates D "
                "(effort 5) under P=1/2"
            ),
            "inputs": {
                "likelihood_point": "1/2",
                "candidates": ["cand_direct", "cand_member_inherited"],
            },
            "actual": {
                "pareto_frontier": ties_frontier,
                "strictly_dominates": (ties_frontier == ["cand_member_inherited"]),
            },
            "command": (
                "PathRankingEngine(version='1.0.0').evaluate(query_payload=ties_pkg['query'], "
                "candidates=ties_pkg['candidates'])"
            ),
            "coverage": "tie_break_resolved",
        }
    )

    # Case 14: W4-REUSE-ANTI-DOUBLE-COUNTING (Anti-double-counting and passive closure invariance)
    eligible_e = res_min_e.ranking_result.get("eligible_candidates", {})
    effort_d = eligible_e.get("generated_0001", {}).get("effort")
    effort_md = eligible_e.get("generated_0002", {}).get("effort")
    cases.append(
        {
            "case_id": "W4-REUSE-ANTI-DOUBLE-COUNTING",
            "category": "min_effort_scoring",
            "description": (
                "Reused work unit counted once; passive membership adds 0 effort; effort(D) == "
                "effort(M/D) == 5"
            ),
            "inputs": {
                "program_1": "Direct Admin (1 hop)",
                "program_2": "Member + Direct Admin (2 hops)",
            },
            "actual": {
                "effort_d": effort_d,
                "effort_md": effort_md,
                "efforts_equal": (effort_d == effort_md == 5),
            },
            "command": "run_attack_query(q_min_e, two_routes_raw)",
            "coverage": "anti_double_counting_verified",
        }
    )

    # Case 14b: W4-REUSE-CONTEXT-SEPARATION
    # (Negative control: distinct context work units not merged)
    decoded_diag = decode_ranking_query(diag_pkg["query"])
    cand_unrated_impact = next(
        c for c in diag_pkg["candidates"] if c["candidate_id"] == "cand_unrated_impact"
    )
    assessed_ui = assess_candidate_program(decoded_diag, cand_unrated_impact)
    cases.append(
        {
            "case_id": "W4-REUSE-CONTEXT-SEPARATION",
            "category": "min_effort_scoring",
            "description": (
                "OtherHost ledger: effort rated; impact remains unrated. "
                "This row does not prove deduplication across multiple contexts."
            ),
            "inputs": {"work_units": ["w-auth-otherhost (1)", "w-direct-admin-otherhost (4)"]},
            "actual": {
                "effort": assessed_ui.get("effort"),
                "effort_status": assessed_ui.get("effort_status"),
                "impact_status": assessed_ui.get("impact_status"),
                "program": assessed_ui.get("program"),
            },
            "command": "assess_candidate_program(decoded_diag, cand_unrated_impact)",
            "coverage": "otherhost_ledger_assessment_only",
        }
    )

    # =========================================================================
    # Group 5: Q-COVER: Caps, Truncation Bounds, and Diagnostic Partitioning
    # =========================================================================

    # Case 15: W4-CAP-PATHS (max_paths cap triggers truncation, cannot claim minimum)
    q_cap_paths = AttackQuery(
        initial_actor="Alice",
        initial_state={"control": ["Alice"]},
        target="Host",
        target_goal={"target": "Host", "required_state": {"admin_control": ["Host"]}},
        aliases=ALIASES,
        runtime_facts=DEFAULT_RUNTIME_FACTS,
        allowed_techniques=["propagate_group_entitlement", "obtain_admin_execution_on_host"],
        budget={"max_paths": 1, "max_steps": 12, "max_expansions": 100000},
        action_bindings=DEFAULT_ACTION_BINDINGS,
        ranking_query=ledger_e_pkg["query"],
    )
    res_cap_paths = run_attack_query(q_cap_paths, two_routes_raw)
    cases.append(
        {
            "case_id": "W4-CAP-PATHS",
            "category": "search_budget_caps",
            "description": "max_paths=1 cap triggers truncation; cannot claim global minimum",
            "inputs": {"max_paths": 1},
            "actual": {
                "truncated": res_cap_paths.truncated,
                "truncation_reason": res_cap_paths.truncation_reason,
                "optimization_scope": res_cap_paths.optimization_scope,
                "is_minimum_proven_over_scope": res_cap_paths.is_minimum_proven_over_scope,
            },
            "command": "run_attack_query(q_cap_paths, two_routes_raw)",
            "coverage": "partial_truncated",
        }
    )

    # Case 15b: W4-CAP-EXP (max_expansions cap triggers truncation)
    q_cap_exp = AttackQuery(
        initial_actor="Alice",
        initial_state={"control": ["Alice"]},
        target="Host",
        target_goal={"target": "Host", "required_state": {"admin_control": ["Host"]}},
        aliases=ALIASES,
        runtime_facts=DEFAULT_RUNTIME_FACTS,
        allowed_techniques=["propagate_group_entitlement", "obtain_admin_execution_on_host"],
        budget={"max_paths": 1000, "max_steps": 12, "max_expansions": 1},
        action_bindings=DEFAULT_ACTION_BINDINGS,
        ranking_query=ledger_e_pkg["query"],
    )
    res_cap_exp = run_attack_query(q_cap_exp, two_routes_raw)
    cases.append(
        {
            "case_id": "W4-CAP-EXP",
            "category": "search_budget_caps",
            "description": (
                "max_expansions=1 cap triggers truncation; "
                "truncation_reason=expansion_limit_reached"
            ),
            "inputs": {"max_expansions": 1},
            "actual": {
                "truncated": res_cap_exp.truncated,
                "truncation_reason": res_cap_exp.truncation_reason,
                "is_minimum_proven_over_scope": res_cap_exp.is_minimum_proven_over_scope,
            },
            "command": "run_attack_query(q_cap_exp, two_routes_raw)",
            "coverage": "partial_truncated_expansions",
        }
    )

    # Case 15c: W4-CAP-STEPS (max_steps cap triggers truncation)
    q_cap_steps = AttackQuery(
        initial_actor="Alice",
        initial_state={"control": ["Alice"]},
        target="Host",
        target_goal={"target": "Host", "required_state": {"admin_control": ["Host"]}},
        aliases=ALIASES,
        runtime_facts=DEFAULT_RUNTIME_FACTS,
        allowed_techniques=["propagate_group_entitlement", "obtain_admin_execution_on_host"],
        budget={"max_paths": 1000, "max_steps": 1, "max_expansions": 100000},
        action_bindings=DEFAULT_ACTION_BINDINGS,
        ranking_query=ledger_e_pkg["query"],
    )
    res_cap_steps = run_attack_query(q_cap_steps, two_routes_raw)
    cases.append(
        {
            "case_id": "W4-CAP-STEPS",
            "category": "search_budget_caps",
            "description": (
                "max_steps=1 cap triggers truncation; truncation_reason=step_limit_reached"
            ),
            "inputs": {"max_steps": 1},
            "actual": {
                "truncated": res_cap_steps.truncated,
                "truncation_reason": res_cap_steps.truncation_reason,
                "is_minimum_proven_over_scope": res_cap_steps.is_minimum_proven_over_scope,
            },
            "command": "run_attack_query(q_cap_steps, two_routes_raw)",
            "coverage": "partial_truncated_steps",
        }
    )

    # Case 15d: W4-SCORE-DIAGNOSTICS (Diagnostic fail-closed partitioning for unrated basis)
    res_diag = PathRankingEngine(version="1.0.0").evaluate(
        query_payload=diag_pkg["query"],
        candidates=diag_pkg["candidates"],
    )
    diag_cands = sorted(res_diag["result_payload"]["diagnostics"].keys())
    cases.append(
        {
            "case_id": "W4-SCORE-DIAGNOSTICS",
            "category": "min_effort_scoring",
            "description": (
                "Fail-closed diagnostic partitioning: missing effort/likelihood/impact basis -> "
                "unrated, fail-closed diagnostic partition, no score invented"
            ),
            "inputs": {"candidates_tested": 6},
            "actual": {
                "diagnostics_count": len(diag_cands),
                "pareto_frontier_count": len(res_diag["result_payload"]["pareto_frontier"]),
                "unrated_effort": res_diag["result_payload"]["diagnostics"]["cand_unrated_effort"][
                    "assessment"
                ]["effort"],
                "unrated_effort_status": res_diag["result_payload"]["diagnostics"][
                    "cand_unrated_effort"
                ]["assessment"]["effort_status"],
                "unrated_likelihood": res_diag["result_payload"]["diagnostics"][
                    "cand_missing_likelihood_basis"
                ]["assessment"]["likelihood_interval"],
                "unrated_assumed_likelihood": res_diag["result_payload"]["diagnostics"][
                    "cand_assumed_gate_unrated_basis"
                ]["assessment"]["likelihood_interval"],
                "unrated_impact": res_diag["result_payload"]["diagnostics"]["cand_unrated_impact"][
                    "assessment"
                ]["impact"],
            },
            "command": (
                "PathRankingEngine(version='1.0.0').evaluate(query_payload=diag_pkg['query'], "
                "candidates=diag_pkg['candidates'])"
            ),
            "coverage": "diagnostic_partitioning",
        }
    )

    # =========================================================================
    # Group 6: Issue #212 Regression Verification Rows (Integrated Fixes)
    # =========================================================================

    # Real public-query reproduction: a supplied binding rejects the cheapest program.
    rejected_bindings = dict(DEFAULT_ACTION_BINDINGS)
    rejected_bindings[("obtain_admin_execution_on_host", "Alice", "Admins", "Host")] = (
        "action_member_admins"
    )
    res_defect1 = run_attack_query(
        replace(q_min_e, action_bindings=rejected_bindings), graph=two_routes_raw
    )
    audit_d1 = res_defect1.ranking_result["search_audit"]
    cases.append(
        {
            "case_id": "W4-DEFECT-212-ADAPTER-REJECT",
            "aliases": ["W4-DEFECT-ADAPTER-REJECT"],
            "category": "defect_issue_212",
            "description": "Public query drops the cheapest generated path at adapter validation",
            "inputs": {"binding_override": "inherited admin -> action_member_admins"},
            "actual": {
                "paths_count": len(res_defect1.paths),
                "candidates_received": audit_d1["candidates_received"],
                "candidates_adapted": audit_d1["candidates_adapted"],
                "candidates_rejected_by_adapter": audit_d1["candidates_rejected_by_adapter"],
                "optimization_scope": res_defect1.optimization_scope,
                "is_minimum_proven_over_scope": res_defect1.is_minimum_proven_over_scope,
                "minimum_effort_value": res_defect1.min_effort["minimum_effort_value"],
            },
            "command": (
                "run_attack_query(replace(q_min_e, action_bindings=rejected_bindings), graph)"
            ),
            "coverage": "adapter_exclusion_reproduction",
        }
    )

    # Case 17: #212 DEFECT 2 (Zero-action goal with target != foothold causes adapter rejection)
    q_zero = AttackQuery(
        target="Host",
        source_foothold="OtherHost",
        initial_actor="Alice",
        initial_state={
            "control": ["OtherHost"],
            "usable_identity": [["Alice", "Host"]],
            "admin_control": ["Host"],
        },
        authentication_context="Host",
        target_goal={"target": "Host", "required_state": {"admin_control": ["Host"]}},
        runtime_facts=DEFAULT_RUNTIME_FACTS,
        allowed_techniques=["obtain_admin_execution_on_host"],
        aliases=ALIASES,
        action_bindings=DEFAULT_ACTION_BINDINGS,
        ranking_query=ledger_e_pkg["query"],
    )
    res_zero = run_attack_query(q_zero, graph=two_routes_raw)
    d2_rejected = (
        res_zero.ranking_result.get("search_audit", {}).get("candidates_rejected_by_adapter", 0)
        if res_zero.ranking_result
        else 0
    )
    d2_diag = (
        res_zero.ranking_result.get("diagnostics", {}).get("generated_0001", {})
        if res_zero.ranking_result
        else {}
    )

    cases.append(
        {
            "case_id": "W4-DEFECT-212-ZERO-ACTION",
            "aliases": ["W4-DEFECT-ZERO-ACTION"],
            "category": "defect_issue_212",
            "description": (
                "Zero-action semantic goal with target != foothold; separate canonical ranking"
            ),
            "inputs": {
                "source_foothold": "OtherHost",
                "target": "Host",
                "initial_state": "admin_control(Host)",
            },
            "actual": {
                "paths_count": len(res_zero.paths),
                "path_transitions": (
                    len(res_zero.paths[0].transition_history) if res_zero.paths else None
                ),
                "adapter_rejected": (d2_rejected > 0),
                "diagnostic": d2_diag.get("assessment", {}).get("diagnostic"),
                "ranking_status": (res_zero.min_effort or {}).get("ranking_status"),
                "disposition": (res_zero.min_effort or {}).get("disposition"),
                "likelihood_interval": (res_zero.min_effort or {}).get(
                    "associated_likelihood_interval"
                ),
                "impact": (res_zero.min_effort or {}).get("associated_impact"),
                "eligible_candidates": res_zero.ranking_result["eligible_candidates"],
                "pareto_frontier": res_zero.ranking_result["pareto_frontier"],
                "candidates_evaluated": res_zero.ranking_result["search_metadata"][
                    "candidates_evaluated"
                ],
                "canonical_minimum_effort": res_zero.ranking_result["min_effort_to_da_baseline"][
                    "minimum_effort_value"
                ],
                "optimization_scope": res_zero.optimization_scope,
                "final_goal_reached": res_zero.final_goal_reached,
                "zero_new_work_disclosed": (
                    res_zero.min_effort is not None
                    and res_zero.min_effort.get("minimum_effort_value") == 0
                ),
            },
            "command": "run_attack_query(q_zero, graph=two_routes_raw)",
            "coverage": "semantic_initial_goal_zero_work",
        }
    )

    cases.append(
        {
            "case_id": "W4-DEFECT-212-DOCS-SHAPE",
            "aliases": ["W4-DEFECT-DOCS-SHAPE"],
            "category": "manual_contract_audit",
            "description": "Public documentation/API agreement requires a manual audit",
            "inputs": {"api_field": "min_effort.minimum_effort_value"},
            "actual": {
                "documentation_matches_output": None,
                "actual_field_present": "minimum_effort_value" in (res_min_e.min_effort or {}),
            },
            "command": None,
            "coverage": "manual_audit_not_executed",
        }
    )

    # =========================================================================
    # Group 7: Extension Techniques (Week 4 Intended Outcome Verification)
    # =========================================================================

    cat_techs = [t.id for t in load_catalog()]
    cases.extend(kerberoasting_cases())

    # Case 20: use exact catalog owners and the public #228 query fixture.
    # Independent expected fields remain in the A-owned oracle, never from this output.
    from scripts.research.asrep_inputs import PROGRAM as ASREP_PROGRAM
    from scripts.research.asrep_inputs import inputs as asrep_inputs

    asrep_graph, asrep_query = asrep_inputs()
    asrep_spec = AttackQuery(
        **{f.name: asrep_query[f.name] for f in fields(AttackQuery) if f.name in asrep_query}
    )
    asrep_result = run_attack_query(asrep_spec, asrep_graph)
    cases.append(
        {
            "case_id": "W4-TECH-ASREP",
            "category": "extension_technique",
            "description": "AS-REP #228 synthetic query; domain mapping review pending",
            "inputs": {
                "issue_number": 228,
                "owner": "TTS B (@nairyuuu)",
                "techniques": ASREP_PROGRAM,
            },
            "actual": {
                "catalog_support": set(ASREP_PROGRAM).issubset(cat_techs),
                "query_validator_behavior": "",
                "search_support": asrep_result.final_goal_reached,
            },
            "evidence": query_evidence(asrep_spec, asrep_result),
            "command": "run_attack_query(asrep_query, asrep_graph)",
            "coverage": "scoped_synthetic_prediction_only_mapping_review_pending",
        }
    )

    # Case 21: RBCD Extension (#229)
    from scripts.research.rbcd_inputs import inputs as rbcd_inputs

    rbcd_graph, rbcd_query = rbcd_inputs()
    rbcd_spec = AttackQuery(
        **{f.name: rbcd_query[f.name] for f in fields(AttackQuery) if f.name in rbcd_query}
    )
    rbcd_result = run_attack_query(rbcd_spec, rbcd_graph)
    rbcd_program = rbcd_query["allowed_techniques"]

    cases.append(
        {
            "case_id": "W4-TECH-RBCD",
            "category": "extension_technique",
            "description": "RBCD #229 synthetic query; domain mapping review pending",
            "inputs": {
                "issue_number": 229,
                "owner": "TTS B (@nairyuuu)",
                "techniques": rbcd_program,
            },
            "actual": {
                "catalog_support": set(rbcd_program).issubset(cat_techs),
                "query_validator_behavior": "",
                "search_support": rbcd_result.final_goal_reached,
            },
            "evidence": query_evidence(rbcd_spec, rbcd_result),
            "command": "run_attack_query(rbcd_query, rbcd_graph)",
            "coverage": "scoped_synthetic_prediction_only_mapping_review_pending",
        }
    )

    cli_actual, cli_evidence, cli_processes = run_cli_acceptance()
    execution["cli_processes"] = cli_processes
    cases.append(
        {
            "case_id": "W4-CLI-PACKAGE",
            "category": "cli_integration",
            "description": "Execute CLI stdout/output, compare two runs and reject invalid inputs",
            "inputs": {
                "query": "tests/fixtures/query_cli/two-routes-query.json",
                "graph": "tests/fixtures/attack_scenarios/graphs/two-routes.json",
                "ratings": "docs/research/ratings/week4/synthetic-a2-e.json",
                "empty_initial_state": {},
                "null_ranking_wrapper": {"query": None},
            },
            "actual": cli_actual,
            "evidence": cli_evidence,
            "command": (
                "python -m src.engine.query_cli "
                "--query tests/fixtures/query_cli/two-routes-query.json "
                "--graph tests/fixtures/attack_scenarios/graphs/two-routes.json "
                "--ranking-query docs/research/ratings/week4/synthetic-a2-e.json --label synthetic"
            ),
            "coverage": "synthetic_cli_generation_scoring_and_transport; not private acceptance",
        }
    )

    raw_dir = ROOT / "data/raw/SEAMLESS"
    cases.append(
        {
            "case_id": "W4-SEAMLESS-DATASET-GATE",
            "category": "dataset_governance",
            "description": "Filesystem prerequisite check only; private probe not executed",
            "inputs": {"manifest_path": "data/samples/manifests/seamless-raw-v1.json"},
            "actual": {
                "authorized_trace_verified": None,
                "private_raw_data_present": raw_dir.is_dir() and any(raw_dir.iterdir()),
                "probe_execution": "not_executed",
            },
            "command": None,
            "coverage": "private_trace_not_executed",
        }
    )

    query_results = {
        "W4-M-POSITIVE": (q_m, res_m),
        "W4-X-I": (q_x_i, res_x_i),
        "W4-X-H-WRONG": (q_x_h, res_x_h),
        "W4-X-H-VALID": (q_x_h_val, res_x_h_val),
        "W4-C-F": (q_c_f, res_c_f),
        "W4-C-U": (q_c_u, res_c_u),
        "W4-DA-NEG-ASSET-POS": (q_da_neg, res_da_neg),
        "W4-DA-POS": (q_da_pos, res_da_pos),
        "W4-G-U": (q_g_u, res_g_u),
        "W4-G-A": (q_g_a, res_g_a),
        "W4-G-F": (q_g_f, res_g_f),
        "W4-G-VETO": (q_g_veto, res_g_veto),
        "W4-MIN-EFFORT-E": (q_min_e, res_min_e),
        "W4-MIN-EFFORT-T": (q_min_t, res_min_t),
        "W4-CAP-PATHS": (q_cap_paths, res_cap_paths),
        "W4-CAP-EXP": (q_cap_exp, res_cap_exp),
        "W4-CAP-STEPS": (q_cap_steps, res_cap_steps),
        "W4-DEFECT-212-ADAPTER-REJECT": (
            replace(q_min_e, action_bindings=rejected_bindings),
            res_defect1,
        ),
        "W4-DEFECT-212-ZERO-ACTION": (q_zero, res_zero),
    }
    oracle = json.loads(ORACLE_PATH.read_text(encoding="utf-8"))
    if {c["case_id"] for c in cases} != set(oracle["cases"]):
        raise ValueError("oracle/case IDs differ")
    for case in cases:
        spec = oracle["cases"][case["case_id"]]
        case.update(spec)
        case.setdefault("execution_status", "executed")
        case["evidence_class"] = "synthetic_test_only"
        if case["case_id"] in query_results:
            query, result = query_results[case["case_id"]]
            case["evidence"] = query_evidence(query, result)
        evaluate_case(case)

    # Verify engine/caller inputs remain unchanged; they are part of provenance.
    for path, raw in ((TWO_ROUTES_GRAPH_PATH, two_routes_raw), (PSREMOTE_GRAPH_PATH, psremote_raw)):
        if raw != json.loads(path.read_text(encoding="utf-8")):
            raise ValueError("acceptance execution mutated input graph")
    if execution["file_sha256"] != file_pins():
        raise ValueError("source/input files changed during acceptance execution")
    return {
        "manifest_version": "2.0.0",
        "execution": execution,
        "summary": summarize(cases),
        "cases": cases,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Week 4 Acceptance Runner")
    parser.add_argument("--revision", help="Optional assertion: must equal executed HEAD")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--semantic-output", type=Path)
    parser.add_argument("--check-determinism", action="store_true")
    parser.add_argument("--case-id")
    args = parser.parse_args()
    try:
        data = run_all_cases(args.revision)
    except (ValueError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    if args.case_id:
        case = next(
            (
                c
                for c in data["cases"]
                if c["case_id"] == args.case_id or args.case_id in c.get("aliases", [])
            ),
            None,
        )
        if case is None:
            print(f"Case {args.case_id} not found", file=sys.stderr)
            return 1
        print(
            json.dumps(
                semantic_payload({"cases": [case]})["cases"][0], indent=2, ensure_ascii=False
            )
        )
        return int(case["verdict"] == "FAIL")
    semantic = semantic_payload(data)
    if args.check_determinism:
        second = run_all_cases(args.revision)
        if (
            semantic != semantic_payload(second)
            or data["execution"]["source_input_digest"]
            != second["execution"]["source_input_digest"]
        ):
            print("Semantic determinism/source identity mismatch", file=sys.stderr)
            return 1
        print(f"SEMANTIC DETERMINISM VERIFIED: {compute_digest(semantic)}")
    for path, payload in ((args.output, data), (args.semantic_output, semantic)):
        if path:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            print(f"Wrote {path}")
    print(json.dumps(data["summary"], sort_keys=True))
    return int(data["summary"]["unexpected_failure_count"] > 0)


if __name__ == "__main__":
    raise SystemExit(main())
