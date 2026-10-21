"""SEAMLESS Scenario Policy Acceptance Runner and Funnel Quantifier.

Implements Issue #290: Native SEAMLESS scenario policy acceptance across
four genuinely distinct representative sources and goals:
1. SRC-C0-ASREP: Foothold Computer X -> AS-REP Target (C0).
   Standard profile indeterminate at password recovery; what-if succeeds with recovery_opt_in.
2. SRC-KERBEROAST-SPN: Foothold Computer X -> SPN Candidate (JEANNE_YANG) -> Usable identity.
   Standard profile indeterminate at ticket recovery; what-if succeeds with recovery_opt_in.
3. SRC-GINO-FANOUT: Compromised GINO -> Domain Users fan-out -> Target C0 admin control.
   Both standard and exploratory modes truncate strictly at 5,000 expansions.
4. SRC-BORIS-DISTLIST: Compromised BORIS -> Direct member of HO-170-DISTLIST1.
   Standard profile indeterminate due to distribution list naming; what-if succeeds.

Enforces non-negotiable invariants:
1. Never turn all Unknown facts into True blindly.
2. Never invent structural edges or permissions.
3. Never grant attacker capabilities (control, usable_identity, admin_control).
4. Authoritative False in snapshot facts always vetoes assumptions.
5. Successful assumptions never imply P=1 (likelihood remains unrated).
6. Groups named DISTLIST cannot default to security groups.
7. Offline password recovery cannot default to True.
"""

from __future__ import annotations

import copy
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.research.asrep_inputs import seamless_inputs  # noqa: E402
from src.data.manifest import load_manifest, verify_manifest  # noqa: E402
from src.engine.query import materialize_query  # noqa: E402
from src.engine.semantics.scenario_policy import (  # noqa: E402
    SEAMLESS_SNAPSHOT_ID,
    PolicyOverride,
    apply_policy_to_query,
)


def run_seamless_policy_acceptance() -> dict[str, Any]:
    raw_dir = ROOT / "data/raw/SEAMLESS"
    manifest_path = ROOT / "data/samples/manifests/seamless-raw-v1.json"
    manifest = load_manifest(manifest_path)
    errors = verify_manifest(raw_dir, manifest)
    if errors:
        raise ValueError(f"SEAMLESS raw manifest verification failed: {errors}")

    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()

    started_at = time.time()
    print("Loading SEAMLESS graph engine and snapshot facts...")
    engine, base, _, _ = seamless_inputs(raw_dir, revision)

    spec = json.loads(
        (ROOT / "docs/research/scenarios/week4-seamless-v1.json").read_text(encoding="utf-8")
    )

    # Resolve Computer X quickly from raw computers file without full re-parse
    comp_file = next(raw_dir.glob("*_computers.json"))
    comp_data = json.loads(comp_file.read_text(encoding="utf-8-sig"))
    x_idx = int(spec["locators"]["X"].split("/")[-1])
    x_id = comp_data["computers"][x_idx]["ObjectIdentifier"]
    if engine.node(x_id)["kind"] != "Computer":
        raise ValueError(f"Resolved X {x_id} is not Computer")

    v_id = base["initial_state"]["known_identity"][0]
    c_id = base["target"]

    # Target SIDs for four genuinely distinct representative acceptance cases:
    # 1. SRC-C0-ASREP: Foothold Computer X, AS-REP target v_id, target c_id
    # 2. SRC-KERBEROAST-SPN: Foothold Computer X, SPN candidate JEANNE_YANG, target x_id
    # 3. SRC-GINO-FANOUT: Foothold GINO_ROSS, target c_id (fanout hits 5000 limit)
    # 4. SRC-BORIS-DISTLIST: Foothold BORIS_DILLARD, target HO-170-DISTLIST1
    jeanne_id = "S-1-5-21-1271839998-3495686680-2211690266-1110"
    gino_id = "S-1-5-21-1271839998-3495686680-2211690266-1103"
    boris_id = "S-1-5-21-1271839998-3495686680-2211690266-1137"
    distlist_id = "S-1-5-21-1271839998-3495686680-2211690266-4038"

    source_cases: list[dict[str, Any]] = [
        {
            "source_id": "SRC-C0-ASREP",
            "source_label": "Computer X Foothold -> AS-REP Target (C0)",
            "source_principal": x_id,
            "target_principal": c_id,
            "query": {
                "source_foothold": x_id,
                "initial_actor": x_id,
                "authentication_context": x_id,
                "target": c_id,
                "target_goal": {"target": c_id, "required_state": {"admin_control": [c_id]}},
                "initial_state": {
                    "control": [],
                    "known_identity": [v_id],
                    "asrep_request_capability": [[x_id, x_id]],
                },
                "allowed_techniques": [
                    "asrep_request",
                    "recover_asrep_secret",
                    "activate_recovered_identity",
                    "obtain_admin_execution_on_host",
                ],
                "budget": {"max_paths": 10, "max_steps": 6, "max_expansions": 1000},
            },
            "what_if_override": PolicyOverride(
                predicate="recovery_success",
                subject=x_id,
                target=v_id,
                value=True,
                override_type="recovery_opt_in",
                rationale="Offline dictionary cracking with hashcat (48h GPU budget)",
                metadata={
                    "method": "offline-password-prediction",
                    "budget": "48h-gpu",
                    "horizon": "48h-gpu",
                },
            ),
            "expected_behavior": (
                "Halted in standard mode at recover_asrep_secret (indeterminate); "
                "feasible in exploratory what-if with recovery_opt_in override."
            ),
        },
        {
            "source_id": "SRC-KERBEROAST-SPN",
            "source_label": ("Computer X Foothold -> JEANNE_YANG SPN Candidate -> Usable Identity"),
            "source_principal": x_id,
            "target_principal": x_id,
            "query": {
                "source_foothold": x_id,
                "initial_actor": x_id,
                "authentication_context": x_id,
                "target": x_id,
                "target_goal": {
                    "target": x_id,
                    "required_state": {"usable_identity": [[jeanne_id, x_id]]},
                },
                "initial_state": {
                    "control": [x_id],
                    "usable_identity": [[x_id, x_id]],
                    "known_identity": [jeanne_id],
                    "service_ticket_material": [],
                },
                "allowed_techniques": [
                    "kerberoast_request",
                    "recover_ticket_secret",
                    "activate_recovered_identity",
                ],
                "budget": {"max_paths": 10, "max_steps": 6, "max_expansions": 1000},
            },
            "what_if_override": PolicyOverride(
                predicate="recovery_success",
                subject=x_id,
                target=jeanne_id,
                value=True,
                override_type="recovery_opt_in",
                rationale="Kerberoasting TGS crack with hashcat 48h budget",
                metadata={
                    "method": "kerberoast-hashcat",
                    "budget": "48h-gpu",
                    "horizon": "48h-gpu",
                },
            ),
            "expected_behavior": (
                "Standard mode indeterminate at recover_ticket_secret; "
                "exploratory what-if succeeds with recovery_opt_in override."
            ),
        },
        {
            "source_id": "SRC-GINO-FANOUT",
            "source_label": "GINO_ROSS Foothold -> Domain Users Search Fan-out -> Target C0",
            "source_principal": gino_id,
            "target_principal": c_id,
            "query": {
                "source_foothold": x_id,
                "initial_actor": gino_id,
                "authentication_context": x_id,
                "target": c_id,
                "target_goal": {"target": c_id, "required_state": {"admin_control": [c_id]}},
                "initial_state": {
                    "control": [gino_id],
                    "usable_identity": [[gino_id, x_id]],
                },
                "budget": {"max_paths": 10, "max_steps": 6, "max_expansions": 5000},
            },
            "what_if_override": None,
            "expected_behavior": (
                "Free search hits 5,000 expansions due to fan-out at DOMAIN USERS. "
                "Classified strictly as search_fanout_blocker / expansion_limit_reached, "
                "not conflated with 'no_path'."
            ),
        },
        {
            "source_id": "SRC-BORIS-DISTLIST",
            "source_label": "BORIS_DILLARD Foothold -> HO-170-DISTLIST1 Direct Member",
            "source_principal": boris_id,
            "target_principal": distlist_id,
            "query": {
                "source_foothold": x_id,
                "initial_actor": boris_id,
                "authentication_context": x_id,
                "target": distlist_id,
                "target_goal": {
                    "target": distlist_id,
                    "required_state": {"effective_member": [[boris_id, distlist_id]]},
                },
                "initial_state": {
                    "control": [boris_id],
                    "usable_identity": [[boris_id, x_id]],
                },
                "allowed_techniques": ["propagate_group_entitlement"],
                "budget": {"max_paths": 1, "max_steps": 6, "max_expansions": 2000},
            },
            "what_if_override": PolicyOverride(
                predicate="security_group",
                subject=boris_id,
                target=distlist_id,
                value=True,
                override_type="mail_enabled_security_group",
                rationale="Verified out-of-band as mail-enabled security group",
            ),
            "expected_behavior": (
                "Standard mode rejects security_group assumption for HO-170-DISTLIST1 "
                "due to distribution list naming (status: indeterminate). "
                "Exploratory what-if accepts explicit override and succeeds in 1 path."
            ),
        },
    ]

    expected_outcomes: dict[str, dict[str, dict[str, Any]]] = {
        "SRC-C0-ASREP": {
            "evidence_only": {"status": "indeterminate", "paths_count": 0},
            "seamless_standard_scenario": {
                "status": "indeterminate",
                "paths_count": 0,
                "required_blocker": (
                    "offline_password_recovery_unresolved (requires explicit opt-in)"
                ),
            },
            "exploratory_what_if": {"status": "success", "paths_count": 1},
        },
        "SRC-KERBEROAST-SPN": {
            "evidence_only": {"status": "indeterminate", "paths_count": 0},
            "seamless_standard_scenario": {
                "status": "indeterminate",
                "paths_count": 0,
                "required_blocker": (
                    "offline_password_recovery_unresolved (requires explicit opt-in)"
                ),
            },
            "exploratory_what_if": {"status": "success", "paths_count": 1},
        },
        "SRC-GINO-FANOUT": {
            "evidence_only": {"status": "indeterminate", "paths_count": 0},
            "seamless_standard_scenario": {
                "status": "truncated",
                "paths_count": 0,
                "expansions": 5000,
                "truncation_reason": "expansion_limit_reached",
                "required_blocker": "search_fanout_blocker (expansion_limit_reached)",
            },
            "exploratory_what_if": {
                "status": "truncated",
                "paths_count": 0,
                "expansions": 5000,
                "truncation_reason": "expansion_limit_reached",
                "required_blocker": "search_fanout_blocker (expansion_limit_reached)",
            },
        },
        "SRC-BORIS-DISTLIST": {
            "evidence_only": {"status": "indeterminate", "paths_count": 0},
            "seamless_standard_scenario": {
                "status": "indeterminate",
                "paths_count": 0,
                "truncated": False,
                "required_blocker": "distribution_group_cannot_default (requires scoped override)",
            },
            "exploratory_what_if": {
                "status": "success",
                "paths_count": 1,
                "truncation_reason": "path_limit_reached",
            },
        },
    }

    modes = ["evidence_only", "seamless_standard_scenario", "exploratory_what_if"]
    funnel_summary: list[dict[str, Any]] = []

    for sc in source_cases:
        src_id_key = sc["source_id"]
        q_raw = copy.deepcopy(sc["query"])
        what_if_ov = sc.get("what_if_override")

        eval_modes_out: dict[str, Any] = {}

        for mode in modes:
            ovs = [what_if_ov] if (mode == "exploratory_what_if" and what_if_ov) else []
            compiled = apply_policy_to_query(q_raw, engine, profile=mode, overrides=ovs)
            policy_meta = compiled.get("scenario_policy_metadata", {})

            mat = materialize_query(compiled, graph=engine)
            query_res = mat.run(engine)
            search_res = query_res.search_result
            status = query_res.status

            unresolved_counts: dict[str, int] = {}
            failed_counts: dict[str, int] = {}
            for att in search_res.attempts:
                for u in att.unknown:
                    unresolved_counts[u] = unresolved_counts.get(u, 0) + 1
                for f in att.failed:
                    failed_counts[f] = failed_counts.get(f, 0) + 1

            programs = [
                [step.result.technique.id for step in p.transition_history]
                for p in search_res.paths
            ]

            # Determine blockers
            blockers: list[str] = []
            if search_res.truncated:
                if search_res.truncation_reason == "expansion_limit_reached":
                    blockers.append("search_fanout_blocker (expansion_limit_reached)")
                else:
                    blockers.append(f"search_truncation ({search_res.truncation_reason})")
            if "recovery_success" in unresolved_counts or "recovery_scope" in unresolved_counts:
                blockers.append("offline_password_recovery_unresolved (requires explicit opt-in)")
            if any(
                (r.get("reason") if isinstance(r, dict) else getattr(r, "reason", None))
                == "distribution_group_cannot_default"
                for r in policy_meta.get("rejected_assumptions", [])
            ):
                blockers.append("distribution_group_cannot_default (requires scoped override)")
            if mode == "evidence_only" and (
                "network_kdc_reachable" in unresolved_counts
                or "asrep_request_accepted" in unresolved_counts
            ):
                blockers.append("raw_network_protocol_unresolved (requires scenario assumptions)")

            # Automated assertions enforcing observed behavior matches expected
            exp = expected_outcomes[src_id_key][mode]
            if "status" in exp:
                assert status == exp["status"], (
                    f"Case {src_id_key} mode {mode}: "
                    f"expected status {exp['status']!r}, got {status!r}"
                )
            if "paths_count" in exp:
                assert len(search_res.paths) == exp["paths_count"], (
                    f"Case {src_id_key} mode {mode}: "
                    f"expected paths {exp['paths_count']}, got {len(search_res.paths)}"
                )
            if "truncated" in exp:
                assert search_res.truncated == exp["truncated"], (
                    f"Case {src_id_key} mode {mode}: "
                    f"expected truncated {exp['truncated']}, got {search_res.truncated}"
                )
            if "truncation_reason" in exp:
                assert search_res.truncation_reason == exp["truncation_reason"], (
                    f"Case {src_id_key} mode {mode}: "
                    f"expected truncation_reason {exp['truncation_reason']!r}, "
                    f"got {search_res.truncation_reason!r}"
                )
            if "expansions" in exp:
                assert search_res.expansions == exp["expansions"], (
                    f"Case {src_id_key} mode {mode}: "
                    f"expected expansions {exp['expansions']}, got {search_res.expansions}"
                )
            if "required_blocker" in exp:
                assert exp["required_blocker"] in blockers, (
                    f"Case {src_id_key} mode {mode}: "
                    f"expected blocker {exp['required_blocker']!r} in {blockers}"
                )

            eval_modes_out[mode] = {
                "feasible": len(search_res.paths) > 0,
                "status": status,
                "paths_count": len(search_res.paths),
                "expansions": search_res.expansions,
                "truncated": search_res.truncated,
                "truncation_reason": search_res.truncation_reason,
                "blockers": blockers,
                "programs": programs,
                "unresolved_conditions": unresolved_counts,
                "failed_prerequisites": failed_counts,
                "assumptions_count": len(compiled.get("assumptions", [])),
                "policy_assumptions_count": policy_meta.get(
                    "policy_assumptions_count", len(compiled.get("assumptions", []))
                ),
                "rejected_assumptions_count": policy_meta.get("rejected_count", 0),
                "overrides_applied_count": len(policy_meta.get("applied_overrides", [])),
                "ratings": {
                    "effort": "unrated",
                    "impact": "unrated",
                    "likelihood": "unrated (assumptions do not assert P=1)",
                    "ranking_disposition": "unrated",
                },
            }

        funnel_summary.append(
            {
                "source_id": src_id_key,
                "source_label": sc["source_label"],
                "source_principal": sc["source_principal"],
                "target_principal": sc["target_principal"],
                "expected_behavior": sc["expected_behavior"],
                "evaluations": eval_modes_out,
            }
        )

    summary = {
        "summary_version": "issue290-seamless-policy-summary/1.0.0",
        "snapshot_id": SEAMLESS_SNAPSHOT_ID,
        "code_version": revision,
        "elapsed_seconds": round(time.time() - started_at, 2),
        "total_sources_evaluated": len(source_cases),
        "sources": funnel_summary,
    }

    return summary


def main() -> None:
    print("Executing SEAMLESS policy acceptance funnel...")
    summary = run_seamless_policy_acceptance()

    reports_dir = ROOT / "reports/research"
    reports_dir.mkdir(parents=True, exist_ok=True)
    summary_path = reports_dir / "issue290-seamless-policy-summary.json"
    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(f"Sanitized policy summary saved to: {summary_path}")

    # Output funnel metrics
    print("\n" + "=" * 80)
    print("SEAMLESS POLICY COVERAGE FUNNEL METRICS")
    print("=" * 80)
    for src in summary["sources"]:
        print(f"\nSource: {src['source_id']} ({src['source_label']})")
        for mode, ev in src["evaluations"].items():
            print(
                f"  [{mode:27s}] Feasible: {str(ev['feasible']):5s} | "
                f"Status: {ev['status']:13s} | "
                f"Paths: {ev['paths_count']:2d} | "
                f"Expansions: {ev['expansions']:4d} | "
                f"Truncated: {str(ev['truncated']):5s} | "
                f"Blockers: {', '.join(ev['blockers']) or 'None'}"
            )
    print("=" * 80 + "\n")


if __name__ == "__main__":
    main()
