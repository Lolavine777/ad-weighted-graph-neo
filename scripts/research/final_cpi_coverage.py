"""Frozen-cohort public generated coverage; sanitized report, private outputs ignored."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import subprocess
import sys
from collections import Counter
from dataclasses import asdict
from fractions import Fraction
from pathlib import Path

from scripts.research.final_cpi_profiles import (
    HISTORICAL,
    PACKAGE,
    REVIEW,
    ROOT,
    bind_registry,
    bind_source_a,
    engineering_copy,
    historical_pins,
    read,
    validate_package,
)
from scripts.research.issue250_public_probe import envelope, frozen_inputs, save
from src.engine import materialize_query, run_attack_query
from src.engine.graph import EngineGraph
from src.engine.query_cli import wire
from src.engine.ranking.orchestration import generate_and_evaluate_attack_paths
from src.engine.ranking.resolution_service import canonical_digest
from src.engine.semantics import evaluate
from src.engine.semantics.evaluator import PreparedSemanticGraph
from src.engine.semantics.transitions import Status, TransitionRequest, apply_transition
from src.parser.snapshot_facts import graph_digest, serialize_snapshot

COUNT_FIELDS = (
    "valid_generated",
    "conditioned_feasible",
    "C_rated",
    "P_rated",
    "I_rated",
    "fully_rated",
    "Pareto_eligible",
)


def counts(result):
    summaries = list((result.rating_coverage or {}).get("candidate_summaries", {}).values())
    ranking = result.ranking_result or {}
    return {
        "valid_generated": len(result.search_result.paths),
        "conditioned_feasible": sum(s["semantic_status"] == "feasible" for s in summaries),
        **{
            name: sum(s[field] for s in summaries)
            for name, field in (
                ("C_rated", "c_complete"),
                ("P_rated", "p_complete"),
                ("I_rated", "i_complete"),
                ("fully_rated", "numeric_complete"),
            )
        },
        "Pareto_eligible": len(ranking.get("eligible_candidates", {})),
    }


def prepare_roasting(case, graph, frozen, *, recovery_profile_id=None):
    """Bind explicit operation questions before generating any program."""
    template = read(HISTORICAL / "source-a-query.json")
    scenario = "final-cpi-v1/" + case["id"]
    declared_recovery = None
    if recovery_profile_id is not None:
        from scripts.research.final_cpi_delegated_release import declaration, recovery_context

        declared_recovery = recovery_context(recovery_profile_id)
        scenario = "final-cpi-declared-recovery-v1/" + recovery_profile_id
    if case["id"] == "asrep-natural-password":
        query = copy.deepcopy(frozen)
        query.pop("checkpoint_goal", None)
        owner = query["initial_state"]["known_identity"][0]
        actor, auth, asset = (
            query["initial_actor"],
            query["authentication_context"],
            query["target"],
        )
        program = [
            "asrep_request",
            "recover_asrep_secret",
            "activate_recovered_identity",
            "obtain_admin_execution_on_host",
        ]
        method = "offline-asrep-etype23-rank-unknown-final-v1"
        recovery = {
            "method": method,
            "budget": "one-worker;20h;cap-68719476736-distinct-verifications;no-floor;no-restart",
            "horizon": "24h",
        }
        if declared_recovery is not None:
            recovery = declared_recovery
            method = recovery["method"]
        for fact in query["assumptions"]:
            fact["scope"] = scenario
            if fact["predicate"] == "recovery_success":
                fact["assumption_metadata"].update(recovery)
        actions = [
            {
                "action_id": "request",
                "technique_id": program[0],
                "actor": actor,
                "source": actor,
                "target": owner,
                "method": "ASRepTarget",
                "requires": [],
            },
            {
                "action_id": "recover",
                "technique_id": program[1],
                "actor": actor,
                "source": actor,
                "target": owner,
                "method": method,
                "resource_context": canonical_digest(recovery),
                "requires": ["request"],
            },
            {
                "action_id": "activate",
                "technique_id": program[2],
                "actor": owner,
                "source": owner,
                "target": auth,
                "method": "RecoveredSecret",
                "requires": ["recover"],
            },
            {
                "action_id": "admin",
                "technique_id": program[3],
                "actor": owner,
                "source": owner,
                "target": asset,
                "method": "AdminTo",
                "requires": ["activate"],
                "terminal": True,
            },
        ]
        query["allowed_techniques"] = program
        consequence = None
    else:
        actor = next(
            a["actor"]
            for a in read(PACKAGE / "source-a-inventory.json")["actions"]
            if a["action_id"] == "action_activate_lidia"
        )
        auth = template["authentication_context"]
        targets = sorted(
            n["id"]
            for n in graph.nodes(kind="User")
            if n["kind"] == "User"
            and n.get("enabled") is True
            and graph.snapshot_facts.lookup(n["id"], "has_spn").value is True
            and graph.snapshot_facts.lookup(n["id"], "service_principal_names").value
        )
        if not targets:
            raise ValueError(
                "Predefined SPN target cohort is unavailable; no replacement selection"
            )
        owner = targets[0]
        recovery = {
            "method": "offline-tgs-etype-unobserved-rank-unknown-final-v1",
            "budget": "one-worker;20h;cap-68719476736-distinct-verifications;no-floor;no-restart",
            "horizon": "24h",
        }
        if declared_recovery is not None:
            recovery = declared_recovery
        query = {
            "initial_actor": actor,
            "authentication_context": auth,
            "initial_state": {
                "control": [actor],
                "usable_identity": [[actor, auth]],
                "known_identity": [owner],
            },
            "target": owner,
            "target_goal": {
                "target": owner,
                "required_state": {"usable_identity": [[owner, auth]]},
            },
            "allowed_techniques": case["techniques"],
            "runtime_facts": [],
            "evaluation_mode": "scenario",
            "scenario_reference": scenario,
            "budget": case["budget"],
        }
        for predicate, subject, target, extra in (
            ("kerberos_authentication_usable", actor, auth, {}),
            ("network_kdc_reachable", actor, owner, {}),
            ("service_ticket_request_accepted", actor, owner, {}),
            ("recovery_success", actor, owner, recovery),
            ("secret_valid", owner, auth, {}),
            ("network_kdc_reachable", owner, auth, {}),
            ("authentication_accepted", owner, auth, {}),
        ):
            query["runtime_facts"].append(
                {
                    "predicate": predicate,
                    "subject": subject,
                    "target": target,
                    "value": True,
                    "origin": "declared_assumption",
                    "scope": scenario,
                    "rationale": (
                        "Explicit unknown-only conditional prediction, never observed "
                        "exploitation or numerical success"
                    ),
                    "provenance_reference": "scenario://final-cpi-v1/kerberoast",
                    "assumption_metadata": {
                        "declared_by": "TTS A pending profile",
                        "authentication_context": auth,
                        **extra,
                    },
                }
            )
        actions = [
            {
                "action_id": "request",
                "technique_id": "kerberoast_request",
                "actor": actor,
                "source": actor,
                "target": owner,
                "method": "RoastTarget",
                "requires": [],
            },
            {
                "action_id": "recover",
                "technique_id": "recover_ticket_secret",
                "actor": actor,
                "source": actor,
                "target": owner,
                "method": recovery["method"],
                "resource_context": canonical_digest(recovery),
                "requires": ["request"],
            },
            {
                "action_id": "activate",
                "technique_id": "activate_recovered_identity",
                "actor": owner,
                "source": owner,
                "target": auth,
                "method": "RecoveredSecret",
                "requires": ["recover"],
                "terminal": True,
            },
        ]
        profile = read(PACKAGE / "profile.json")
        consequence = next(
            c for c in profile["I_consequences"] if c["class"] == "identity_or_command_session"
        )
        if case["goal"] == "ticket_material":
            # The existing typed goal compares complete artifact lineage. Bind that
            # lineage through the same native single-event semantics before search;
            # no generated candidate, path or rating lookup is consumed here.
            m = materialize_query(query, graph)
            event = evaluate(
                PreparedSemanticGraph(graph.to_canonical(), snapshot_facts=graph.snapshot_facts),
                m.initial_attack_state,
                TransitionRequest("kerberoast_request", actor, actor, owner),
                m.runtime_context,
            )
            artifact = next(iter(event.additions.service_ticket_material), None)
            if artifact is None:
                raise ValueError("Declared material event not applicable for frozen target")
            query["target_goal"]["required_state"] = {"service_ticket_material": [asdict(artifact)]}
            actions = actions[:1]
            consequence = next(
                c
                for c in profile["I_consequences"]
                if c["class"] == "encrypted_or_credential_material"
            )
    query["scenario_reference"] = scenario
    query["evaluation_mode"] = "scenario"
    query["budget"] = case["budget"]
    query["rating_resolution"] = copy.deepcopy(template["rating_resolution"])
    scope = query["rating_resolution"]["scope"]
    scope.update(
        query_id=case["id"],
        scenario_id=scenario,
        scenario_version="1.0.0",
        foothold_node_id=query["initial_actor"],
        active_work_budget=case["budget"]["max_steps"],
        policy_id="final-cpi-roasting-24h-v1",
        retry_policy={
            "request": "three attempts/10m",
            "recovery": recovery,
            "activation": "three attempts/10m",
            "admin": "three attempts/30m; SMB/RPC transport scenario for AdminTo",
            "stop": (
                "first verified success, authoritative denial, event deadline, "
                "campaign deadline or compute cap"
            ),
        },
    )
    scope["target_goal"] = {
        "goal_id": case["id"] + "-typed",
        "target_asset_id": query["target"],
        "success_event": "admin_control_dc" if consequence is None else consequence["class"],
    }
    population = None
    if declared_recovery is not None:
        model = declaration(recovery_profile_id)
        for fact in query.get("runtime_facts", []) + query.get("assumptions", []):
            if fact["predicate"] == "recovery_success":
                fact["assumption_metadata"]["recovery_model"] = model
        scope.update(query_id=recovery_profile_id, policy_id="final-cpi-declared-recovery-24h-v1")
        population = "Explicit conditional #281 model " + canonical_digest(model)
    descriptor = materialize_query(query, graph).semantic_goal.to_dict()
    return bind_registry(
        query, actions, consequence=consequence, semantic_goal=descriptor, population=population
    )


def normalized_cli(path):
    """Read selected native pretty-JSON fields without loading attempt traces.

    The CLI owns this fixed indent=2 transport; this reader is not a general
    JSON parser. Each selected value is still parsed by the standard decoder.
    Unknown transport/missing fields fail closed.
    """
    fields = {
        "status",
        "truncated",
        "truncation_reason",
        "complete",
        "expansions",
        "caps",
        "final_goal_reached",
        "checkpoint_reached",
        "min_effort",
        "engine_reported_guarantees",
        "ranking_result",
        "rating_coverage",
        "candidates",
    }
    result, buffer = {}, []
    active, inside = None, False

    def flush():
        if active in fields:
            payload = "".join(buffer).strip().removesuffix(",")
            result[active] = json.loads(payload)

    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if not inside:
                inside = line == '  "semantic": {\n'
                continue
            if line.startswith("  }"):
                flush()
                break
            match = re.match(r'^    "([a-z_]+)": (.*)', line)
            if match:
                flush()
                active, value = match.groups()
                buffer = [value + "\n"] if active in fields else []
            elif active in fields:
                buffer.append(line)
    if result.keys() != fields:
        raise ValueError("Missing or unsupported CLI semantic transport fields")
    candidates = result.pop("candidates")
    if not isinstance(candidates, list) or any(not isinstance(c, dict) for c in candidates):
        raise ValueError("Unexpected CLI candidate transport")
    result["program_identities"] = [
        {key: value for key, value in c.items() if key != "candidate_id"} for c in candidates
    ]
    result["programs"] = [
        [s["result"]["request"]["technique_id"] for s in c["transition_history"]]
        for c in candidates
    ]
    return result


def public_check(query, graph, local, name, label, *, timeout_seconds=180):
    """Public subprocess CLI twice plus API/orchestration, retaining private data locally."""
    local.mkdir(parents=True, exist_ok=True)
    query_file = local / f"{name}.query.json"
    save(query_file, query)
    graph_file = local / f"{name}.graph.json"
    if graph.snapshot_facts:
        graph_file.write_text(serialize_snapshot(graph.to_canonical(), graph.snapshot_facts))
        graph_arg = "--snapshot"
    else:
        save(graph_file, graph.to_canonical())
        graph_arg = "--graph"
    command = [
        sys.executable,
        "-m",
        "src.engine.query_cli",
        "--query",
        str(query_file),
        graph_arg,
        str(graph_file),
        "--label",
        label,
    ]
    if label == "seamless":
        command += ["--prerequisite", str(ROOT / "data/samples/manifests/seamless-raw-v1.json")]
    outputs, transports = [], []
    for n in (1, 2):
        output_file = local / f"{name}.run{n}.json"
        process = subprocess.run(
            command + ["--output", str(output_file)],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
        if process.returncode:
            (local / f"{name}.stderr.txt").write_text(process.stderr)
            raise ValueError(f"Public CLI failed for {name}; private diagnostics retained")
        output = normalized_cli(output_file)
        outputs.append(output)
        hasher = hashlib.sha256()
        with output_file.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                hasher.update(chunk)
        transports.append(
            {"bytes": output_file.stat().st_size, "native_file_sha256": hasher.hexdigest()}
        )
        save(local / f"{name}.run{n}.normalized.json", output)
        output_file.unlink()  # Reproducible native command retained; huge attempts are transient.
    if outputs[0] != outputs[1]:
        raise ValueError(f"Two-process determinism mismatch: {name}")
    api = run_attack_query(query, graph)
    semantic = outputs[0]
    api_semantic = {
        field: wire(getattr(api, field))
        for field in (
            "status",
            "truncated",
            "truncation_reason",
            "complete",
            "expansions",
            "caps",
            "final_goal_reached",
            "checkpoint_reached",
            "min_effort",
            "ranking_result",
            "rating_coverage",
        )
    }
    api_semantic["engine_reported_guarantees"] = {
        "optimization_scope": api.optimization_scope,
        "is_minimum_proven_over_scope": api.is_minimum_proven_over_scope,
        "is_no_path_proven_over_scope": api.is_no_path_proven_over_scope,
    }
    if any(value != semantic[field] for field, value in api_semantic.items()):
        raise ValueError(f"API/CLI semantic/caps/guarantees/ranking/coverage mismatch: {name}")
    if semantic["program_identities"] != wire(api.search_result.paths):
        raise ValueError(f"API/CLI generated program mismatch: {name}")
    m = materialize_query(query, graph)
    orchestration = generate_and_evaluate_attack_paths(
        {},
        graph.to_canonical(),
        snapshot_facts=graph.snapshot_facts,
        actor=m.initial_actor,
        initial_state=m.initial_attack_state,
        runtime_context=m.runtime_context,
        budget=m.budget,
        catalog=m.catalog,
        scenario_reference=m.scenario_reference,
        success_state_predicate=m.success_state_predicate,
        semantic_goal=m.semantic_goal,
        rating_resolution=query["rating_resolution"],
    )
    search = orchestration["search_result"]
    if (
        wire(orchestration["roundtrip_result"]) != semantic["ranking_result"]
        or any(
            getattr(search, f) != semantic[f]
            for f in ("truncated", "truncation_reason", "complete", "expansions")
        )
        or wire(search.paths) != semantic["program_identities"]
    ):
        raise ValueError(f"Orchestration search/programs/ranking mismatch: {name}")
    return api, {
        "two_CLI_exit_codes": [0, 0],
        "CLI_timeout_seconds": timeout_seconds,
        "two_process_equal": True,
        "comparison_version": "final-cpi-public-comparison/2.0.0",
        "program_identity_scope": "ordered canonical wire(PathResult); excludes only candidate_id",
        "program_summary_scope": "technique names are display summaries only",
        "comparison": (
            "normalized semantic outcomes, generated programs, "
            "caps/guarantees, full ranking/coverage"
        ),
        "native_transports": transports,
        "full_attempt_traces": (
            "transient; normalized private artifacts and native file digests retained"
        ),
        "API_CLI_semantic_ranking_coverage_programs_equal": True,
        "orchestration_search_ranking_programs_equal": True,
        "orchestration_comparison_scope": (
            "search truncation/reason/completeness/expansions, ordered programs and ranking only; "
            "public status/goal/caps/guarantees are not exposed by this orchestration contract"
        ),
        "command": subprocess.list2cmdline(command),
        "minimum_proven": semantic["engine_reported_guarantees"]["is_minimum_proven_over_scope"],
    }


def independent_checks(result, class_overrides=None):
    """Compute C sums and Fraction chain products from frozen classes, not engine values."""
    rows = {r["technique_id"]: r for r in read(PACKAGE / "taxonomy.json")["actions"]}
    classes = {c["class_id"]: c for c in read(PACKAGE / "profile.json")["classes"]}
    for name, values in (class_overrides or {}).items():
        classes[name] = {**classes[name], **values}
    checked, worked = 0, []
    for cid, assessment in result.ranking_result["eligible_candidates"].items():
        detail = result.rating_coverage["candidates"][cid]
        total = sum(
            classes[rows[u["rating_audit"]["lookup_key"]["technique"]]["canonical_class"]]["cost"]
            for u in detail["effort"]["units"].values()
        )
        lo = hi = Fraction(1)
        for prefix in detail["likelihood"]["prefixes"]:
            cls = classes[
                rows[prefix["rating_audit"]["lookup_key"]["outcome_technique"]]["canonical_class"]
            ]
            lo *= Fraction(cls["lower"])
            hi *= Fraction(cls["upper"])
        if assessment["effort"] != total or list(
            map(Fraction, assessment["likelihood_interval"])
        ) != [lo, hi]:
            raise ValueError("Independent Fraction/C oracle mismatch")
        checked += 1
        if len(worked) < 5:
            path = result.search_result.paths[int(cid.split("_")[-1]) - 1]
            worked.append(
                {
                    "candidate": cid,
                    "program": [s.result.request.technique_id for s in path.transition_history],
                    "C": total,
                    "P": [str(lo), str(hi)],
                    "I": assessment["impact"],
                }
            )
    return {"checked_eligible_candidates": checked, "worked_programs": worked}


def report_case(result):
    # Preserve native no_path while disclosing terminal-state attribution gaps.
    materialized = result.materialized_query
    unreturned_goal_events = [
        a.request.technique_id
        for a in result.attempts
        if not result.paths
        and a.status == Status.APPLICABLE
        and materialized.is_success_state(apply_transition(a.before, a))
    ]
    families = Counter()
    rows = {r["technique_id"]: r for r in read(PACKAGE / "taxonomy.json")["actions"]}
    for path in result.search_result.paths:
        for family in {
            rows[s.result.request.technique_id]["canonical_class"]
            for s in path.transition_history
            if rows[s.result.request.technique_id]["active"]
        }:
            families[family] += 1
    gaps = Counter(
        (str(g["dimension"]), str(g["reason_code"]))
        for g in (result.rating_coverage or {}).get("unresolved_gaps", [])
    )
    return {
        "counts": counts(result),
        "unreturned_goal_state_success_events": unreturned_goal_events,
        "B_goal_contract_gap": bool(unreturned_goal_events),
        "status": result.status,
        "truncated": result.truncated,
        "truncation_reason": result.truncation_reason,
        "expansions": result.expansions,
        "paths_by_action_family_nonexclusive": dict(families),
        "gaps": [{"dimension": d, "reason": r, "count": n} for (d, r), n in sorted(gaps.items())],
        "frontier": (result.ranking_result or {}).get("pareto_frontier", []),
        "min_effort": (result.min_effort or {}).get("minimum_effort_value"),
        "coverage_digest": canonical_digest(wire(result.rating_coverage)),
    }


def sensitivity(query, graph):
    baseline = run_attack_query(query, graph)
    widened = copy.deepcopy(query)
    env = widened["rating_resolution"]["registries"]["likelihood"]
    for r in env["data"]:
        r.update(lower="0", upper="1")
    widened["rating_resolution"]["registries"]["likelihood"] = envelope(env["data"])
    wide = run_attack_query(widened, graph)
    variants = {"widened_bounds_test_only": report_case(wide)}
    for name in ("missing_terminal_declaration", "authoritative_false_terminal", "step_cap"):
        q = copy.deepcopy(query)
        if name == "step_cap":
            q["budget"]["max_steps"] = 2
            q["rating_resolution"]["scope"]["active_work_budget"] = 2
        elif name == "missing_terminal_declaration":
            q["runtime_facts"] = [
                f for f in q["runtime_facts"] if f["predicate"] != "admin_execution_context"
            ]
        else:
            for fact in q["runtime_facts"]:
                if fact["predicate"] == "admin_execution_context":
                    fact.update(value=False, origin="blocked_evidence")
        result = run_attack_query(q, graph)
        if name != "widened_bounds_test_only" and result.search_result.paths:
            raise ValueError("Sensitivity control unexpectedly reaches the DC goal")
        variants[name] = report_case(result)
    return {
        "baseline": report_case(baseline),
        "variants": variants,
        "frontier_changed_with_bounds": baseline.ranking_result["pareto_frontier"]
        != wide.ranking_result["pareto_frontier"],
        "scope": (
            "query-local frontier/profile controls only; no B-owned source "
            "aggregation or remediation counterfactual claim"
        ),
    }


def run(raw_dir, output):
    validate_package()
    cohort = read(PACKAGE / "cohort.json")
    pins = historical_pins()
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    for folder in (PACKAGE, ROOT / "scripts/research/final_cpi_profiles.py", Path(__file__)):
        paths = folder.rglob("*.json") if folder.is_dir() else [folder]
        for path in paths:
            if path.read_bytes() != subprocess.check_output(
                ["git", "show", f"HEAD:{path.relative_to(ROOT)}"], cwd=ROOT
            ):
                raise ValueError("Commit cohort/profile/compiler before final evaluation")
    graph, frozen, _ = frozen_inputs(raw_dir, cohort["baseline_revision"])
    before = graph_digest(graph.to_canonical())
    projected = read(HISTORICAL / "source-a-graph.json")
    ids = {n["id"] for n in projected["nodes"]}
    canonical = graph.to_canonical()
    if [n for n in canonical["nodes"] if n["id"] in ids] != projected["nodes"] or [
        e for e in canonical["edges"] if e["source"] in ids and e["target"] in ids
    ] != projected["edges"]:
        raise ValueError("Historical Source A projection is not exactly raw-backed")
    cases, sum_supported, sum_broad = (
        [],
        {"accepted": Counter(), "synthetic_potential": Counter()},
        {"accepted": Counter(), "synthetic_potential": Counter()},
    )
    local = ROOT / "reports/generated/issue267"
    for case in cohort["queries"]:
        print("Evaluating", case["id"], flush=True)
        if case["id"].startswith("kerberoast") or case["id"] == "asrep-natural-password":
            query = prepare_roasting(case, graph, frozen)
            original = graph
        else:
            query, projection = bind_source_a(case["id"])
            original = (
                EngineGraph.from_canonical(projection)
                if case["graph"].startswith("historical_induced")
                else graph
            )
        pending, pending_public = public_check(
            query, original, local, case["id"] + ".pending", "seamless"
        )
        test_query, derivative = engineering_copy(query, original)
        test, test_public = public_check(
            test_query, derivative, local, case["id"] + ".wiring", "synthetic"
        )
        if len(pending.search_result.paths) != len(test.search_result.paths):
            raise ValueError("Numeric gate copy changed semantic coverage")
        row = {
            "query_id": case["id"],
            "source_profile": case["source"],
            "goal": case.get("goal", "admin_control_DC"),
            "graph_scope": case["graph"],
            "supported_cohort": case["supported_cohort"],
            "accepted": report_case(pending),
            "synthetic_potential": report_case(test),
            "public_verification": {"pending": pending_public, "synthetic": test_public},
            "independent_oracle": independent_checks(test),
            "numeric_adoption": False,
        }
        if case["id"] == "source-a-projection":
            row["sensitivity"] = sensitivity(test_query, derivative)
        save(local / (case["id"] + ".verified-case.json"), row)
        cases.append(row)
        for mode, result in (("accepted", pending), ("synthetic_potential", test)):
            sum_broad[mode].update(counts(result))
            if case["supported_cohort"]:
                sum_supported[mode].update(counts(result))
    if graph_digest(graph.to_canonical()) != before or historical_pins() != pins:
        raise ValueError("Original graph or frozen history changed")

    def totals(values):
        out = {}
        for mode, counter in values.items():
            feasible = counter["conditioned_feasible"]
            ratio = Fraction(counter["fully_rated"], feasible) if feasible else None
            out[mode] = {
                "counts": dict(counter),
                "fully_rated_fraction": str(ratio) if ratio is not None else None,
                "meets_80_percent_on_returned_sample": ratio >= Fraction(4, 5)
                if ratio is not None
                else False,
            }
        return out

    report = {
        "version": "1.0.0",
        "issue": 267,
        "revision": revision,
        "cohort_sha256": canonical_digest(cohort),
        "profile_sha256": canonical_digest(read(PACKAGE / "profile.json")),
        "taxonomy": validate_package(),
        "snapshot_id": cohort["snapshot_id"],
        "full_raw_graph": {
            "nodes": len(canonical["nodes"]),
            "edges": len(canonical["edges"]),
            "graph_sha256": before,
        },
        "projection_exact_raw_lineage": True,
        "historical_files_byte_preserved": len(pins),
        "historical_files_pin_digest": canonical_digest(pins),
        "numeric_adoption": False,
        "review_reference": REVIEW,
        "cases": cases,
        "supported_cohort_totals": totals(sum_supported),
        "broader_declared_query_totals": totals(sum_broad),
        "truncated_query_count": sum(c["accepted"]["truncated"] for c in cases),
        "blocked_query_count": sum(c["accepted"]["status"] == "blocked" for c in cases),
        "unrated_query_count": sum(
            c["accepted"]["counts"]["conditioned_feasible"] > 0
            and c["accepted"]["counts"]["fully_rated"] == 0
            for c in cases
        ),
        "limits": cohort["limitations"]
        + cohort["unrepresented"]
        + [
            (
                "Pooled query denominators include the repeated Source A "
                "projection/full-raw comparison; no claim of independent paths "
                "or snapshot-wide fraction."
            ),
            (
                "All-source generator coverage and source-risk/chokepoint "
                "sensitivity require B-owned batch/counterfactual integration; not measured here."
            ),
            (
                "Actual 80% accepted coverage cannot be achieved before actual B "
                "adoption; synthetic potential is only wiring and arithmetic."
            ),
        ],
    }
    save(output, report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = run(args.raw_dir, args.output)
    print(
        json.dumps(
            {
                "supported": report["supported_cohort_totals"],
                "broader": report["broader_declared_query_totals"],
                "truncated": report["truncated_query_count"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
