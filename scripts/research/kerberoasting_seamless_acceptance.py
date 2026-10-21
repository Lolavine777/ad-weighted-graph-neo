"""Manifest-verified SEAMLESS Kerberoasting acceptance; private traces stay local.

Run as:
python -m scripts.research.kerberoasting_seamless_acceptance --raw-dir data/raw/SEAMLESS
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
import time
from pathlib import Path

from scripts.research.asrep_inputs import seamless_inputs
from src.data.manifest import load_manifest, verify_manifest
from src.engine.exploration import (
    build_scenario_template,
    inspect_transition,
    query_with_proposals,
    scenario_proposals,
)
from src.engine.query_cli import canonical_json, execute, wire
from src.engine.semantics.transitions import TransitionRequest

ROOT = Path(__file__).resolve().parents[2]


def digest(value):
    return "sha256:" + hashlib.sha256(canonical_json(value).encode()).hexdigest()


def save(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(wire(value), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def run_kerberoasting_acceptance(
    raw_dir: Path,
    output_dir: Path,
    sanitized_report: Path | None = None,
):
    output_dir = Path(output_dir).resolve()
    private_root = (ROOT / "reports/generated").resolve()
    if not output_dir.is_relative_to(private_root):
        raise ValueError("private output must be inside this checkout's reports/generated")
    output_dir.mkdir(parents=True, exist_ok=True)

    started = time.perf_counter()
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    summary = {
        "scenario": "SEAMLESS_Kerberoasting_Realistic_Escalation",
        "code_revision": revision,
        "runtime": {"python": platform.python_version(), "platform": platform.system()},
        "runner_digest": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "executable_tree_digest": digest(
            {
                p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                for folder in ("src", "configs")
                for p in sorted((ROOT / folder).rglob("*"))
                if p.is_file() and p.suffix in {".py", ".json", ".yml", ".yaml"}
            }
        ),
        "matrix": [],
        "modes": {},
    }

    def check(name, expected, observed, evidence, *, blocked=False):
        summary["matrix"].append(
            {
                "check": name,
                "expected": expected,
                "observed": observed,
                "status": "BLOCKED" if blocked else "PASS" if observed == expected else "FAIL",
                "evidence": evidence,
            }
        )

    def publish():
        statuses = {row["status"] for row in summary["matrix"]}
        summary["status"] = (
            "FAIL" if "FAIL" in statuses else "BLOCKED" if "BLOCKED" in statuses else "PASS"
        )
        summary["elapsed_seconds"] = round(time.perf_counter() - started, 3)
        save(output_dir / "summary.json", summary)
        if sanitized_report:
            save(Path(sanitized_report), summary)
        return summary

    manifest_path = ROOT / "data/samples/manifests/seamless-raw-v1.json"
    try:
        manifest = load_manifest(manifest_path)
        issues = verify_manifest(Path(raw_dir), manifest)
    except OSError, ValueError:
        issues = ["missing or invalid raw/manifest prerequisite"]
    check(
        "manifest",
        "valid pinned raw snapshot",
        "missing or invalid dataset" if issues else "valid pinned raw snapshot",
        "manifest verifier",
        blocked=bool(issues),
    )
    if issues:
        return publish()
    summary["snapshot_id"] = manifest["snapshot_id"]
    before_hashes = {
        p.name: hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(Path(raw_dir).rglob("*"))
        if p.is_file()
    }

    engine, _, _, _ = seamless_inputs(raw_dir, revision)
    nodes_by_label = {
        d["record"]["label"]: d["record"]["id"] for n, d in engine._graph.nodes(data=True)
    }

    # Resolve canonical nodes
    u_init = nodes_by_label["ALEXANDRIA_WALSH@SEAMLESS.INTERNAL"]
    wks = nodes_by_label["AWSWWKS1000000.SEAMLESS.INTERNAL"]
    u_spn = nodes_by_label["AVIS_SWEET@SEAMLESS.INTERNAL"]
    g_int = nodes_by_label["HO-170-DISTLIST1@SEAMLESS.INTERNAL"]
    u_adm = nodes_by_label["KATRINA_GREEN@SEAMLESS.INTERNAL"]
    c_dc = nodes_by_label["BADBLOOD.SEAMLESS.INTERNAL"]

    scope_id = "seamless-287-kerberoasting"

    def make_assumption(pred, subj, tgt, val=True, **meta):
        return {
            "predicate": pred,
            "subject": subj,
            "target": tgt,
            "value": val,
            "origin": "declared_assumption",
            "scope": scope_id,
            "rationale": "Declared scenario condition for Kerberoasting demo",
            "provenance_reference": "scenario://287/kerberoast-demo",
            "assumption_metadata": meta,
        }

    assumptions = [
        # Step 1: kerberoast_request
        make_assumption("kerberos_authentication_usable", u_init, wks),
        make_assumption("network_kdc_reachable", u_init, u_spn),
        make_assumption("service_ticket_request_accepted", u_init, u_spn),
        # Step 2: recover_ticket_secret
        make_assumption(
            "recovery_success",
            u_init,
            u_spn,
            method="hashcat-offline-rule-attack",
            budget="100-hours-gpu",
            horizon="password-compromise-window",
        ),
        # Step 3: activate_recovered_identity
        make_assumption("secret_valid", u_spn, wks),
        make_assumption("network_kdc_reachable", u_spn, wks),
        make_assumption("authentication_accepted", u_spn, wks),
        # Step 4: propagate_group_entitlement
        make_assumption("security_group", u_spn, g_int),
        make_assumption("membership_usable", u_spn, g_int),
        # Step 5: scenario_reset_password
        make_assumption("password_policy_accepts", u_spn, u_adm),
        make_assumption("directory_write_allowed", u_spn, u_adm),
        make_assumption("network_rpc_reachable", u_spn, u_adm),
        # Step 5b: acquire_reset_identity
        make_assumption("network_kdc_reachable", u_adm, wks),
        make_assumption("authentication_accepted", u_adm, wks),
        # Step 6: obtain_admin_execution_on_host
        make_assumption("admin_channel", u_adm, c_dc),
        make_assumption("authentication_accepted", u_adm, c_dc),
    ]

    raw_query = {
        "initial_actor": u_init,
        "source_foothold": wks,
        "authentication_context": wks,
        "target": c_dc,
        "target_goal": {"target": c_dc, "required_state": {"admin_control": [c_dc]}},
        "initial_state": {
            "known_identity": [u_spn],
            "usable_identity": [[u_init, wks]],
        },
        "runtime_facts": [],
        "assumptions": [],
        "evaluation_mode": "evidence_only",
        "budget": {"max_paths": 10, "max_steps": 10, "max_expansions": 5000},
        "scenario_reference": "287-kerberoast-demo",
    }

    assumed_query = {
        **raw_query,
        "assumptions": assumptions,
        "evaluation_mode": "scenario",
    }

    req1 = TransitionRequest("kerberoast_request", u_init, u_init, u_spn)
    req2 = TransitionRequest("recover_ticket_secret", u_init, u_init, u_spn)
    req3 = TransitionRequest("activate_recovered_identity", u_spn, u_spn, wks)
    req4 = TransitionRequest("propagate_group_entitlement", u_spn, u_spn, g_int)
    req5 = TransitionRequest("scenario_reset_password", u_spn, g_int, u_adm)
    req5b = TransitionRequest("acquire_reset_identity", u_adm, u_adm, wks)
    req6 = TransitionRequest("obtain_admin_execution_on_host", u_adm, u_adm, c_dc)

    # 1. RAW Mode Execution
    raw_result = execute(raw_query, engine)
    save(output_dir / "raw-result.json", raw_result)
    raw_probe1 = inspect_transition(raw_query, engine, req1)
    save(output_dir / "raw-probe-step1.json", raw_probe1)
    raw_probe2 = inspect_transition(raw_query, engine, req2, prefix=[req1])
    save(output_dir / "raw-probe-step2.json", raw_probe2)

    # 2. Template and Assumed Replay
    template = build_scenario_template(
        raw_query, engine, assumptions, template_id="seamless-287-kerberoast-avis"
    )
    proposals = scenario_proposals(template, raw_query, engine)
    save(output_dir / "template.json", template)
    save(output_dir / "proposals.json", proposals)

    assumed_result = execute(assumed_query, engine)
    save(output_dir / "assumed-result.json", assumed_result)

    # Step-by-step prefix replay
    ordered_steps = [
        ("step1", req1, []),
        ("step2", req2, [req1]),
        ("step3", req3, [req1, req2]),
        ("step4", req4, [req1, req2, req3]),
        ("step5", req5, [req1, req2, req3, req4]),
        ("step5b", req5b, [req1, req2, req3, req4, req5]),
        ("step6", req6, [req1, req2, req3, req4, req5, req5b]),
    ]
    step_probes = {}
    for step_id, req, prefix in ordered_steps:
        p = inspect_transition(assumed_query, engine, req, prefix=prefix)
        step_probes[step_id] = p
        save(output_dir / f"assumed-{step_id}.json", p)

    # 3. DROP-RECOVERY (Unknown / Prefix Halt Verification)
    drop_assumptions = [ass for ass in assumptions if ass["predicate"] != "recovery_success"]
    drop_query = {**raw_query, "assumptions": drop_assumptions, "evaluation_mode": "scenario"}
    drop_probe2 = inspect_transition(drop_query, engine, req2, prefix=[req1])
    save(output_dir / "drop-recovery-step2.json", drop_probe2)
    drop_suffix = inspect_transition(drop_query, engine, req3, prefix=[req1, req2])
    save(output_dir / "drop-recovery-suffix.json", drop_suffix)

    # 4. True Known-False Veto Control
    veto_raw = {
        **raw_query,
        "runtime_facts": [
            {
                "predicate": "recovery_success",
                "subject": u_init,
                "target": u_spn,
                "value": False,
                "origin": "blocked_evidence",
                "provenance_reference": "control://287/kerberoast-veto",
                "scope": scope_id,
                "rationale": "Measured offline attack exhaustion; password not found in dictionary",
            }
        ],
    }
    veto_template = build_scenario_template(
        veto_raw, engine, assumptions, template_id="seamless-287-kerberoast-veto"
    )
    veto_proposals = scenario_proposals(veto_template, veto_raw, engine)
    save(output_dir / "veto-proposals.json", veto_proposals)
    veto_ids = [p["proposal_id"] for p in veto_proposals["proposals"]]
    veto_query = query_with_proposals(veto_template, veto_raw, engine, veto_ids)
    veto_result = execute(veto_query, engine)
    save(output_dir / "veto-result.json", veto_result)
    veto_probe = inspect_transition(veto_query, engine, req3, prefix=[req1, req2])
    save(output_dir / "veto-probe.json", veto_probe)

    expected_requests = [wire(req) for _, req, _ in ordered_steps]
    matching_candidates = [
        candidate
        for candidate in assumed_result["candidates"]
        if [s["result"]["request"] for s in candidate["transition_history"]] == expected_requests
        and c_dc in candidate["final_state"]["admin_control"]
    ]

    def option_status(probe):
        return probe["options"][0]["status"] if probe["options"] else None

    # Publish only reviewed labels and aggregate observations, not canonical IDs.
    summary = {
        **summary,
        "foothold": {
            "account_label": "ALEXANDRIA_WALSH@SEAMLESS.INTERNAL",
            "account_kind": "User",
            "admincount": False,
            "has_spn": False,
            "memberships": ["DOMAIN USERS@SEAMLESS.INTERNAL"],
            "compromise_narrative": (
                "Phishing credential leak; standard authenticated domain employee session"
            ),
            "workstation_context": (
                "AWSWWKS1000000.SEAMLESS.INTERNAL (Member Workstation, no host admin)"
            ),
            "host_control_granted": False,
        },
        "service_account": {
            "account_label": "AVIS_SWEET@SEAMLESS.INTERNAL",
            "account_kind": "User",
            "admincount": False,
            "has_spn": True,
            "service_principal_names": ["MSSQL/GOOWWEBS1000000"],
            "discovery_method": (
                "LDAP SPN directory enumeration (known_identity declared in initial state)"
            ),
        },
        "target_asset": {
            "target_label": "BADBLOOD.SEAMLESS.INTERNAL",
            "target_kind": "Computer",
            "typed_goal": "admin_control",
            "description": (
                "Administrative code execution on Domain Controller host per semantic model"
            ),
        },
        "reset_identity": {
            "account_label": engine.node(u_adm)["label"],
            "account_kind": "User",
        },
        "executable_identity_chain": [
            {
                "technique_id": req.technique_id,
                "actor_label": engine.node(req.actor)["label"],
                "source_label": engine.node(req.source)["label"],
                "target_label": engine.node(req.target)["label"],
            }
            for _, req, _ in ordered_steps
        ],
        "group_security_enabled_verification": {
            "group_label": "HO-170-DISTLIST1@SEAMLESS.INTERNAL",
            "raw_dataset_schema_limit": (
                "SharpHound v3 raw data does not collect groupType attribute; "
                "properties in raw JSON only include [description, name, objectid, "
                "highvalue, admincount, distinguishedname, domain]."
            ),
            "status": "unverified_assumption",
            "assumption_predicate": "security_group",
            "rationale": (
                "Declared as security_group=True because in Active Directory only security "
                "groups can be security principals in DACLs. If created as a mail-enabled "
                "security "
                "group, the ACE is valid; if purely a distribution group, DACL rights cannot "
                "propagate. This remains an unverified runtime assumption due to dataset "
                "schema "
                "limits."
            ),
            "alternative_candidate_note": (
                "SHERRIE_SOTO -> VA-JER-ADMINGROUP1 -> OLLIE_LONG -> BADBLOOD provides an "
                "alternative where the group is named ADMINGROUP1, "
                "avoiding the distlist naming."
            ),
        },
        "counts": {
            "structural_hops": 3,
            "semantic_actions": 7,
            "active_actions": 6,
            "passive_entitlements": 1,
        },
        "modes": {
            "raw": {
                "status": raw_result["status"],
                "candidates": len(raw_result["candidates"]),
                "expansions": raw_result["expansions"],
                "step1_status": option_status(raw_probe1),
                "step2_prefix_status": raw_probe2["prefix_status"],
            },
            "assumed": {
                "status": assumed_result["status"],
                "truncated": assumed_result["truncated"],
                "truncation_reason": assumed_result["truncation_reason"],
                "engine_guarantees": assumed_result["engine_reported_guarantees"],
                "expansions": assumed_result["expansions"],
                "candidates_count": len(assumed_result["candidates"]),
                "candidate_sequence_matching_design": [
                    s["result"]["request"]["technique_id"]
                    for s in matching_candidates[0]["transition_history"]
                ]
                if matching_candidates
                else [],
                "all_replay_steps_applicable": all(
                    option_status(p) == "applicable" for p in step_probes.values()
                ),
                "optimality_claim": (
                    "Not claimed as optimal/minimum. Search truncated at 5000 expansions; "
                    "candidate matches design sequence within bounded exploration horizon."
                ),
            },
            "drop_recovery_unknown_halt": {
                "step2_status": option_status(drop_probe2),
                "step3_suffix_options_count": len(drop_suffix["options"]),
                "step3_prefix_status": drop_suffix["prefix_status"],
            },
            "known_false_veto": {
                "rejected_assumptions_count": len(veto_proposals["rejected_assumptions"]),
                "rejection_reasons": [r["reason"] for r in veto_proposals["rejected_assumptions"]],
                "step3_prefix_status": veto_probe["prefix_status"],
                "veto_query_status": veto_result["status"],
            },
        },
        "assumptions_count": len(assumptions),
        "scoring": {"effort": "unrated", "likelihood": "unrated", "impact": "unrated"},
    }
    check(
        "raw_mode",
        {
            "status": "indeterminate",
            "candidates": 0,
            "step1_status": "indeterminate",
            "step2_prefix_status": "indeterminate",
        },
        {k: v for k, v in summary["modes"]["raw"].items() if k != "expansions"},
        "raw-result.json; raw-probe-step1.json; raw-probe-step2.json",
    )
    check(
        "assumed_search",
        {"status": "success", "goal_reached": True, "exact_identity_program_found": True},
        {
            "status": assumed_result["status"],
            "goal_reached": assumed_result["final_goal_reached"],
            "exact_identity_program_found": bool(matching_candidates),
        },
        "assumed-result.json",
    )
    check(
        "assumed_replay",
        {**{name: "applicable" for name, _, _ in ordered_steps}, "goal_reached": True},
        {
            **{name: option_status(p) for name, p in step_probes.items()},
            "goal_reached": bool(step_probes["step6"]["options"])
            and c_dc in step_probes["step6"]["options"][0]["after"]["admin_control"],
        },
        "assumed-step*.json",
    )
    check(
        "drop_recovery_unknown_halt",
        {
            "step2_status": "indeterminate",
            "step3_suffix_options_count": 0,
            "step3_prefix_status": "indeterminate",
            "no_secret": True,
            "no_suffix_identity": True,
            "no_recovery_effects": True,
        },
        {
            **summary["modes"]["drop_recovery_unknown_halt"],
            "no_secret": not drop_suffix["state"]["recovered_secret"],
            "no_suffix_identity": [u_spn, wks] not in drop_suffix["state"]["usable_identity"],
            "no_recovery_effects": bool(drop_probe2["options"])
            and drop_probe2["options"][0]["before"] == drop_probe2["options"][0]["after"],
        },
        "drop-recovery-step2.json; drop-recovery-suffix.json",
    )
    check(
        "known_false_veto",
        {
            "ledger_veto": True,
            "prefix_status": "blocked",
            "suffix_options": 0,
            "query_blocked_or_indeterminate": True,
            "candidates": 0,
            "no_secret": True,
            "no_suffix_identity": True,
            "no_recovery_effects": True,
        },
        {
            "ledger_veto": "known_false_veto"
            in summary["modes"]["known_false_veto"]["rejection_reasons"],
            "prefix_status": veto_probe["prefix_status"],
            "suffix_options": len(veto_probe["options"]),
            "query_blocked_or_indeterminate": veto_result["status"] in {"blocked", "indeterminate"},
            "candidates": len(veto_result["candidates"]),
            "no_secret": not veto_probe["state"]["recovered_secret"],
            "no_suffix_identity": [u_spn, wks] not in veto_probe["state"]["usable_identity"],
            "no_recovery_effects": bool(veto_probe["prefix"])
            and veto_probe["prefix"][-1]["before"] == veto_probe["prefix"][-1]["after"],
        },
        "veto-proposals.json; veto-probe.json; veto-result.json",
    )
    check(
        "numeric_boundary",
        ["unrated", "unrated", "unrated"],
        [r["ranking_disposition"] for r in (raw_result, assumed_result, veto_result)],
        "raw-result.json; assumed-result.json; veto-result.json",
    )
    after_hashes = {
        p.name: hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(Path(raw_dir).rglob("*"))
        if p.is_file()
    }
    check(
        "raw_integrity",
        True,
        before_hashes == after_hashes and not verify_manifest(Path(raw_dir), manifest),
        "manifest verifier; raw_checksums",
    )
    summary["raw_checksums"] = before_hashes
    summary["evidence_digests"] = {
        p.relative_to(output_dir).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(output_dir.rglob("*.json"))
        if p.name != "summary.json"
    }
    return publish()


def main():
    parser = argparse.ArgumentParser(description="SEAMLESS Kerberoasting Acceptance Runner")
    parser.add_argument("--raw-dir", default="data/raw/SEAMLESS", help="Raw dataset directory")
    parser.add_argument(
        "--output-dir",
        default="reports/generated/issue287/kerberoasting",
        help="Private output directory",
    )
    parser.add_argument(
        "--sanitized-report",
        default="reports/generated/issue287/kerberoasting-summary.json",
        help="Public sanitized report path",
    )
    args = parser.parse_args()

    res = run_kerberoasting_acceptance(
        Path(args.raw_dir), Path(args.output_dir), Path(args.sanitized_report)
    )
    print(f"Kerberoasting Acceptance completed: status={res['status']}")
    if "assumed" in res["modes"]:
        print(f"Candidates found by engine search: {res['modes']['assumed']['candidates_count']}")
        seq = res["modes"]["assumed"]["candidate_sequence_matching_design"]
        print(f"Candidate program matching design: {seq}")
    return 0 if res["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
