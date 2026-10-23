"""Supplementary raw class probes; original cohort and numeric proposal stay frozen."""

from __future__ import annotations

import argparse
import copy
import subprocess
from collections import Counter, defaultdict
from dataclasses import replace
from pathlib import Path

from scripts.research.final_cpi_coverage import (
    counts,
    independent_checks,
    public_check,
    report_case,
)
from scripts.research.final_cpi_profiles import (
    HISTORICAL,
    PACKAGE,
    ROOT,
    bind_registry,
    engineering_copy,
    historical_pins,
    read,
)
from scripts.research.issue250_public_probe import frozen_inputs, save
from src.engine import materialize_query
from src.engine.graph import EngineGraph
from src.engine.ranking.resolution_service import canonical_digest
from src.engine.semantics import load_catalog
from src.parser.snapshot_facts import graph_digest

COHORT = PACKAGE / "supplementary-cohort.json"


def prepare_extension(case, graph, raw_dir):
    """Declare finite rating identities from static selectors before native search."""
    template = read(HISTORICAL / "source-a-query.json")
    scenario = "final-cpi-v1/supplement/" + case["id"]
    nodes = {n["id"]: n for n in graph.nodes()}
    edges = graph.edges()
    profile = read(PACKAGE / "profile.json")
    consequence = next(c for c in profile["I_consequences"] if c["class"] == "host_admin")
    trace, actions = {}, []

    def action(name, tech, actor, source, target, requires=(), terminal=False, resource=None):
        actions.append(
            {
                "action_id": name,
                "technique_id": tech,
                "actor": actor,
                "source": source,
                "target": target,
                "method": next(t.relationship for t in load_catalog() if t.id == tech),
                "requires": list(requires),
                "terminal": terminal,
                "resource_context": resource,
            }
        )

    def fact(predicate, subject, target):
        query["runtime_facts"].append(
            {
                "predicate": predicate,
                "subject": subject,
                "target": target,
                "value": True,
                "origin": "declared_assumption",
                "scope": scenario,
                "rationale": "Named runtime condition; not observed exploitation or q=1",
                "provenance_reference": "scenario://final-cpi-v1/supplement",
                "assumption_metadata": {
                    "declared_by": "TTS A pending profile",
                    "authentication_context": query["authentication_context"],
                },
            }
        )

    if case["id"].startswith("rbcd"):
        from scripts.research.rbcd_inputs import build_assumed_query, seamless_inputs

        other, query, _, existing_trace = seamless_inputs(
            raw_dir, read(COHORT)["baseline_revision"]
        )
        if other.nodes() != graph.nodes() or other.edges() != edges:
            raise ValueError("Existing RBCD locators do not bind this raw graph")
        query.pop("ranking_query_id", None)
        if case["id"] == "rbcd-scoped":
            query = build_assumed_query(
                query,
                scope=scenario,
                provenance_reference="scenario://final-cpi-v1/supplement/rbcd",
            )
        b = query["rbcd_bindings"][0]
        trace = {
            "locators": existing_trace["locators"],
            "binding_digest": canonical_digest(b),
            "exact_reset_and_descriptor_edges": all(
                any(
                    e["source"] == b["controller"]
                    and e["target"] == b[key]
                    and e["kind"] == "GenericAll"
                    for e in edges
                )
                for key in ("principal", "target")
            ),
            "target_spn": "declared scenario HTTP binding, not observed target SPN",
        }
        dependencies = {
            "rbcd_acquire_secret": (),
            "rbcd_prepare_service": ("rbcd_acquire_secret",),
            "rbcd_configure_descriptor": (),
            "rbcd_delegate_service": ("rbcd_prepare_service", "rbcd_configure_descriptor"),
            "rbcd_service_admin": ("rbcd_delegate_service",),
        }
        for tech in query["allowed_techniques"]:
            target = (
                b["principal"]
                if tech in {"rbcd_acquire_secret", "rbcd_prepare_service"}
                else b["target"]
            )
            action(
                tech,
                tech,
                b["controller"],
                b["controller"],
                target,
                dependencies[tech],
                tech == "rbcd_service_admin",
                canonical_digest(b),
            )
    else:
        members = defaultdict(set)
        for edge in edges:
            if (
                edge["kind"] == "MemberOf"
                and nodes[edge["source"]]["kind"] == "User"
                and nodes[edge["source"]].get("enabled") is True
            ):
                members[edge["target"]].add(edge["source"])
        if case["id"].startswith("acl-group"):
            admin = [
                e for e in edges if e["kind"] == "AdminTo" and nodes[e["source"]]["kind"] == "Group"
            ]
            dacl = [e for e in edges if e["kind"] == "WriteDacl"]
            choices = sorted(
                {
                    (a["source"], a["target"], d["source"], actor)
                    for a in admin
                    for d in dacl
                    if d["target"] == a["source"]
                    for actor in members[d["source"]]
                    if actor not in members[a["source"]]
                }
            )
            if not choices:
                raise ValueError("Frozen ACL/group selector unavailable; no replacement")
            group, host, write_group, actor = choices[0]
            trace = {
                "selector_candidates": len(choices),
                "binding_digest": canonical_digest(choices[:1]),
            }
            goal = {"admin_control": [host]}
        else:
            choices = sorted(
                {
                    (e["source"], e["target"])
                    for e in edges
                    if e["kind"] == "CanPSRemote"
                    and nodes[e["source"]]["kind"] == "User"
                    and nodes[e["source"]].get("enabled") is True
                }
            )
            if not choices:
                raise ValueError("Frozen command selector unavailable; no replacement")
            actor, host = choices[0]
            trace = {
                "selector_candidates": len(choices),
                "binding_digest": canonical_digest(choices[:1]),
            }
            goal = {"remote_command_execution": [[actor, host]]}
            consequence = next(
                c for c in profile["I_consequences"] if c["class"] == "identity_or_command_session"
            )
        auth = template["authentication_context"]
        query = {
            "initial_actor": actor,
            "authentication_context": auth,
            "initial_state": {"control": [actor], "usable_identity": [[actor, auth]]},
            "target": host,
            "target_goal": {"target": host, "required_state": goal},
            "runtime_facts": [],
        }
        if case["id"].startswith("acl-group"):
            for target in (write_group, group):
                for predicate in ("security_group", "membership_usable"):
                    fact(predicate, actor, target)
            for predicate in ("directory_write_allowed", "membership_change_allowed"):
                fact(predicate, actor, group)
            for predicate in ("admin_channel", "authentication_accepted"):
                fact(predicate, actor, host)
            roles = {actor, write_group, group}
            support = {
                kind: {
                    e["source"]
                    for e in edges
                    if e["kind"] == kind and e["target"] == group and e["source"] in roles
                }
                for kind in ("WriteDacl", "GenericAll")
            }
            for tech, kind in (
                ("grant_new_object_right", "WriteDacl"),
                ("genericall_grant_write_dacl", "GenericAll"),
                ("genericall_add_member", "GenericAll"),
            ):
                for index, source in enumerate(sorted(support[kind] | {actor})):
                    action(tech + "_" + str(index), tech, actor, source, group)
            # Derived actor permission can follow either observed-right route.
            # These are declarative lineage alternatives, not path discovery.
            for item in actions:
                if item["source"] != actor:
                    continue
                kind = (
                    "WriteDacl"
                    if item["technique_id"] == "grant_new_object_right"
                    else "GenericAll"
                )
                if actor not in support[kind]:
                    producer = (
                        "genericall_grant_write_dacl"
                        if kind == "WriteDacl"
                        else "grant_new_object_right"
                    )
                    item["requires_any"] = [
                        a["action_id"] for a in actions if a["technique_id"] == producer
                    ]
            sources = sorted(
                {
                    e["source"]
                    for e in edges
                    if e["kind"] == "AdminTo" and e["target"] == host and e["source"] in roles
                }
            )
            for index, source in enumerate(sources):
                action(
                    "admin_" + str(index),
                    "obtain_admin_execution_on_host",
                    actor,
                    source,
                    host,
                    terminal=True,
                )
            trace["declared_terminal_sources"] = len(sources)
            trace["observed_permission_sources"] = {k: len(v) for k, v in support.items()}
        else:
            for predicate in ("winrm_available", "authentication_accepted"):
                fact(predicate, actor, host)
            action("command", "open_winrm_remote_session", actor, actor, host, terminal=True)
        query["allowed_techniques"] = sorted(
            {a["technique_id"] for a in actions} | {"propagate_group_entitlement"}
        )
        if case["id"].endswith("all-generator"):
            query["allowed_techniques"] = sorted(
                row["technique_id"] for row in read(PACKAGE / "taxonomy.json")["actions"]
            )
    query.update(scenario_reference=scenario, evaluation_mode="scenario", budget=case["budget"])
    query["rating_resolution"] = copy.deepcopy(template["rating_resolution"])
    scope = query["rating_resolution"]["scope"]
    scope.update(
        query_id=case["id"],
        scenario_id=scenario,
        scenario_version="1.1.0",
        snapshot_id=graph.metadata["snapshot_id"],
        foothold_node_id=query["initial_actor"],
        active_work_budget=case["budget"]["max_steps"],
        policy_id="final-cpi-supplement-24h-v1",
        retry_policy={
            "directory_and_rbcd_preparation": "three attempts/15m per unique event",
            "remote_execution": "three attempts/30m per unique event; SMB/RPC for AdminTo",
            "stop": "verified success, authoritative denial, event/campaign deadline; no restart",
        },
    )
    scope["target_goal"] = {
        "goal_id": case["id"] + "-typed",
        "target_asset_id": query["target"],
        "success_event": consequence["class"],
    }
    trace["inventory_digest"] = canonical_digest(actions)
    descriptor = materialize_query(query, graph).semantic_goal.to_dict()
    population = (
        "named service principal with known reset-derived secret and exact service/host "
        "binding; no password guessing"
        if case["id"].startswith("rbcd")
        else "named enabled User, scoped group/token or command endpoint; stable resource policy"
    )
    return bind_registry(
        query, actions, consequence=consequence, semantic_goal=descriptor, population=population
    ), trace


def extension_graph(case, graph, query):
    """Induced diagnostic projection with unchanged observed records and fact evidence."""
    if case["id"] != "acl-group-projection":
        return graph
    ids = {query["initial_actor"], query["authentication_context"], query["target"]}
    ids.update(f[k] for f in query["runtime_facts"] for k in ("subject", "target"))
    canonical = graph.to_canonical()
    canonical["nodes"] = [n for n in canonical["nodes"] if n["id"] in ids]
    canonical["edges"] = [
        e for e in canonical["edges"] if e["source"] in ids and e["target"] in ids
    ]
    canonical["assessments"] = [
        a
        for a in canonical["assessments"]
        if all(k not in a or a[k] in ids for k in ("subject", "target"))
    ]
    facts = replace(
        graph.snapshot_facts,
        graph_sha256=graph_digest(canonical),
        facts=tuple(f for f in graph.snapshot_facts.facts if f.subject in ids),
    )
    return EngineGraph.from_canonical(canonical, snapshot_facts=facts)


def run(raw_dir, output):
    cohort, pins = read(COHORT), historical_pins()
    original_paths = [PACKAGE / name for name in ("cohort.json", "profile.json", "taxonomy.json")]
    original_paths.append(ROOT / "reports/research/issue267-final-cpi-v1-verification.json")
    original_preserved = all(
        p.read_bytes()
        == subprocess.check_output(
            ["git", "show", f"{cohort['original_freeze_revision']}:{p.relative_to(ROOT)}"], cwd=ROOT
        )
        for p in original_paths
    )
    if not original_preserved:
        raise ValueError("Original cohort/profile/evidence bytes changed")
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    for path in (
        COHORT,
        Path(__file__),
        ROOT / "scripts/research/final_cpi_profiles.py",
        PACKAGE / "profile.json",
    ):
        if path.read_bytes() != subprocess.check_output(
            ["git", "show", f"HEAD:{path.relative_to(ROOT)}"], cwd=ROOT
        ):
            raise ValueError("Commit supplementary cohort and consumer before final run")
    graph, _, _ = frozen_inputs(raw_dir, cohort["baseline_revision"])
    canonical = graph.to_canonical()
    before = graph_digest(canonical)
    rows, totals = [], {"accepted": Counter(), "synthetic_potential": Counter()}
    for case in cohort["queries"]:
        print("Evaluating supplementary", case["id"], flush=True)
        query, trace = prepare_extension(case, graph, raw_dir)
        original = extension_graph(case, graph, query)
        pending, pp = public_check(
            query,
            original,
            ROOT / "reports/generated/issue267-supplement",
            case["id"] + ".pending",
            "seamless",
        )
        synthetic, derivative = engineering_copy(query, original)
        test, tp = public_check(
            synthetic,
            derivative,
            ROOT / "reports/generated/issue267-supplement",
            case["id"] + ".wiring",
            "synthetic",
        )
        if len(pending.paths) != len(test.paths):
            raise ValueError("Wiring copy changed generated coverage")
        row = {
            "query_id": case["id"],
            "supported_cohort": case["supported"],
            "selection": trace,
            "graph_scope": {
                "nodes": len(original.nodes()),
                "edges": len(original.edges()),
                "is_full_raw": original is graph,
                "graph_sha256": graph_digest(original.to_canonical()),
            },
            "accepted": report_case(pending),
            "synthetic_potential": report_case(test),
            "public_verification": {"pending": pp, "synthetic": tp},
            "independent_oracle": independent_checks(test),
        }
        save(
            ROOT / "reports/generated/issue267-supplement" / (case["id"] + ".verified-case.json"),
            row,
        )
        rows.append(row)
        if case["supported"]:
            for mode, result in (("accepted", pending), ("synthetic_potential", test)):
                totals[mode].update(counts(result))
    if graph_digest(graph.to_canonical()) != before or historical_pins() != pins:
        raise ValueError("Raw graph or historical artifacts changed")
    report = {
        "version": cohort["version"],
        "revision": revision,
        "cohort_sha256": canonical_digest(cohort),
        "profile_sha256": canonical_digest(read(PACKAGE / "profile.json")),
        "full_raw_graph": {
            "nodes": len(canonical["nodes"]),
            "edges": len(canonical["edges"]),
            "graph_sha256": before,
        },
        "raw_structural_edge_counts": dict(Counter(e["kind"] for e in canonical["edges"])),
        "historical_files_byte_preserved": len(pins),
        "numeric_adoption": False,
        "cases": rows,
        "supported_supplement_counts": {m: dict(c) for m, c in totals.items()},
        "original_cohort_unchanged": original_preserved,
        "original_freeze_revision": cohort["original_freeze_revision"],
        "limits": cohort["limitations"],
    }
    save(output, report)
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    run(args.raw_dir, args.output)
