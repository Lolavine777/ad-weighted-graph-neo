"""Executable #216 synthetic query, independent oracle and aggregate SEAMLESS trace."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.engine.graph import EngineGraph  # noqa: E402
from src.engine.query import run_attack_query  # noqa: E402
from src.parser import DirectGraphBuilder, IdentityNormalizer, RawRecord  # noqa: E402
from src.parser.snapshot_facts import serialize_snapshot  # noqa: E402

OWNERS = frozenset({"kerberoast_request", "recover_ticket_secret", "activate_recovered_identity"})

U = "S-1-5-21-1000-2000-3000-1101"
V = "S-1-5-21-1000-2000-3000-1102"
D = "S-1-5-21-1000-2000-3000-1103"
G = "S-1-5-21-1000-2000-3000-512"
R = "S-1-5-21-1000-2000-3000-513"
X = "10000000-0000-4000-8000-000000000001"
C = "10000000-0000-4000-8000-000000000002"
SCOPE = tuple(sorted(OWNERS | {"propagate_group_entitlement", "scenario_winrm_admin"}))
PROGRAM = [
    "kerberoast_request",
    "recover_ticket_secret",
    "activate_recovered_identity",
    "propagate_group_entitlement",
    "scenario_winrm_admin",
]


def digest(value):
    return (
        "sha256:"
        + hashlib.sha256(
            json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()
        ).hexdigest()
    )


def assumption(predicate, subject, target, value=True, **metadata):
    return {
        "predicate": predicate,
        "subject": subject,
        "target": target,
        "value": value,
        "scope": "synthetic-216/H0",
        "rationale": "Synthetic declared outcome; no measured success",
        "provenance_reference": "synthetic://216/outcomes",
        "assumption_metadata": {"declared_by": "synthetic-fixture", **metadata},
    }


def synthetic(*, spn=True, values=("HTTP/synthetic.example.test",), overlap=False):
    """Finite topology/oracle defined before actual generation; no ordered query path."""
    snapshot = "sha256:" + "a" * 64

    def raw(kind, identifier, extra=None, properties=None):
        return RawRecord(
            kind,
            {
                "ObjectIdentifier": identifier,
                "Properties": {
                    "name": "SYNTHETIC",
                    "domain": "EXAMPLE.TEST",
                    "enabled": True,
                    **(properties or {}),
                },
                **(extra or {}),
            },
            {
                "raw_file": "synthetic://216/snapshot",
                "collector": "synthetic/216",
                "timestamp": "2026-10-07T00:00:00Z",
                "snapshot_id": snapshot,
                "record_locator": f"#/{kind}/{identifier}",
                "record_id": identifier,
                "time_provenance": "observed",
            },
        )

    props = {"serviceprincipalnames": list(values)} if values is not None else {}
    if spn is not None:
        props["hasspn"] = spn
    records = [
        raw("User", U),
        raw("User", V, properties=props),
        raw("Computer", X),
        raw("Group", G, {"Members": [{"ObjectIdentifier": V, "ObjectType": "User"}]}),
        raw(
            "Computer",
            C,
            {
                "Aces": [
                    {
                        "PrincipalSID": G,
                        "PrincipalType": "Group",
                        "RightName": "GenericAll",
                        "IsInherited": False,
                    }
                ]
            },
        ),
    ]
    if overlap:
        # U and V share reset access through G; D has the asset entitlement.
        records[3] = raw(
            "Group", G, {"Members": [{"ObjectIdentifier": u, "ObjectType": "User"} for u in (D,)]}
        )
        records.append(
            raw(
                "Group",
                R,
                {"Members": [{"ObjectIdentifier": u, "ObjectType": "User"} for u in (U, V)]},
            )
        )
        records.append(
            raw(
                "User",
                D,
                {
                    "Aces": [
                        {
                            "PrincipalSID": R,
                            "PrincipalType": "Group",
                            "RightName": "GenericAll",
                            "IsInherited": False,
                        }
                    ]
                },
            )
        )
    normalized = IdentityNormalizer().normalize_records(records)
    graph, facts = DirectGraphBuilder(
        metadata={
            "snapshot_id": snapshot,
            "created_at": "2026-10-07T00:00:00Z",
            "code_version": "synthetic/216",
            "synthetic": True,
        }
    ).build_snapshot(normalized)
    engine = EngineGraph.from_snapshot(serialize_snapshot(graph, facts))
    assumptions = [
        assumption(p, U, V) for p in ("network_kdc_reachable", "service_ticket_request_accepted")
    ]
    assumptions += [
        assumption("kerberos_authentication_usable", U, X),
        assumption(
            "recovery_success",
            U,
            V,
            method="synthetic-offline-password",
            budget="fixture-budget",
            horizon="fixed-snapshot-window",
        ),
    ]
    for user in (V, U, D) if overlap else (V,):
        assumptions += [
            assumption(p, user, X)
            for p in ("network_kdc_reachable", "authentication_accepted", "secret_valid")
        ]
        assumptions += [assumption(p, user, G) for p in ("security_group", "membership_usable")]
        assumptions += [
            assumption(p, user, C)
            for p in (
                "network_winrm_reachable",
                "service_winrm_running",
                "winrm_authentication_accepted",
                "endpoint_authorized",
                "admin_execution_context",
            )
        ]
    assumptions.append(assumption("host_admin_mapping", G, C))
    if overlap:
        assumptions += [
            assumption(p, user, R)
            for user in (U, V)
            for p in ("security_group", "membership_usable")
        ]
    if overlap:
        assumptions += [
            assumption(p, user, D)
            for user in (U, V)
            for p in ("network_rpc_reachable", "password_policy_accepts", "directory_write_allowed")
        ]
    query = {
        "source_foothold": X,
        "initial_actor": U,
        "initial_state": {"control": [X], "known_identity": [V], "usable_identity": [[U, X]]},
        "authentication_context": X,
        "target": C,
        "target_goal": {"target": C, "required_state": {"admin_control": [C]}},
        "checkpoint_goal": {"target": G, "required_state": {"effective_member": [[V, G]]}},
        "assumptions": assumptions,
        "allowed_techniques": list(SCOPE),
        "budget": {"max_paths": 50, "max_steps": 9, "max_expansions": 5000},
        "scenario_reference": "synthetic-216",
    }
    if overlap:
        query["allowed_techniques"] += ["scenario_reset_password", "acquire_reset_identity"]
    return engine, query


def summary(result):
    return {
        "status": result.status,
        "asset_goal": result.final_goal_reached,
        "checkpoint": result.checkpoint_reached,
        "truncated": result.truncated,
        "truncation_reason": result.truncation_reason,
        "expansions": result.expansions,
        "programs": [
            [s.result.request.technique_id for s in p.transition_history] for p in result.paths
        ],
        "attempts": [
            {
                "owner": a.request.technique_id,
                "status": str(a.status),
                "failed": list(a.failed),
                "unknown": list(a.unknown),
                "effect_counts": {k: len(v) for k, v in vars(a.additions).items() if v},
            }
            for a in result.attempts
        ],
        "conditional": any(
            a.is_assumption_backed
            for p in result.paths
            for a in [s.result for s in p.transition_history]
        ),
        "scoring": {"effort": "unrated", "likelihood": "unrated", "impact": "unrated"},
    }


def synthetic_run():
    graph, query = synthetic()
    before = graph.to_canonical()
    positive = run_attack_query(query, graph)
    assert [
        [s.result.request.technique_id for s in p.transition_history] for p in positive.paths
    ] == [PROGRAM]
    variants = {"positive": summary(positive)}
    for name, predicate, value in [
        ("K-MATERIAL", "recovery_success", None),
        ("K-KDC-F", "network_kdc_reachable", False),
        ("K-KDC-U", "network_kdc_reachable", None),
        ("K-AUTH-F", "authentication_accepted", False),
    ]:
        q = copy.deepcopy(query)
        for f in q["assumptions"]:
            if f["predicate"] == predicate:
                f["value"] = value
        r = run_attack_query(q, graph)
        assert not r.final_goal_reached
        variants[name] = summary(r)
    q = copy.deepcopy(query)
    q["initial_actor"] = X
    q["initial_state"]["usable_identity"] = []
    variants["K-NO-AUTH"] = summary(run_attack_query(q, graph))
    for value, name in [(False, "K-FACT-F"), (None, "K-FACT-U")]:
        g, q = synthetic(spn=value)
        variants[name] = summary(run_attack_query(q, g))
    graph2, overlap = synthetic(overlap=True)
    baseline_query = copy.deepcopy(overlap)
    baseline_query["allowed_techniques"] = [
        t for t in overlap["allowed_techniques"] if t not in OWNERS
    ]
    baseline = run_attack_query(baseline_query, graph2)
    extension = run_attack_query(overlap, graph2)
    assert baseline.final_goal_reached and extension.final_goal_reached
    assert graph.to_canonical() == before
    return {
        "evidence": "synthetic_test_only",
        "cases": variants,
        "input_digest": digest(query),
        "snapshot_digest": digest(before),
        "K-OVERLAP": {
            "baseline": summary(baseline),
            "extension": summary(extension),
            "new_asset_coverage": False,
            "scope": "generated_scope",
        },
    }


def ranking_inputs(graph, query):
    from scripts.research.credential_bindings import credential_ranking_inputs
    from src.engine.query import materialize_query

    materialized = materialize_query(query, graph)
    state, ctx = materialized.initial_attack_state, materialized.runtime_context

    def value(p, s, t):
        fact = ctx.facts.get((p, s, t))
        return fact.value if fact else None

    fact = graph.snapshot_facts.lookup(V, "has_spn")
    spns = graph.snapshot_facts.lookup(V, "service_principal_names")
    return credential_ranking_inputs(
        graph,
        query,
        actor=U,
        owner=V,
        context=X,
        group=G,
        asset=C,
        program=PROGRAM,
        material_field="service_ticket_material",
        work_boundary="216-scoped-password-recovery",
        goal_id="admin-216",
        provenance_root="synthetic://216",
        snapshot_requirements=["spn", "spn_values"],
        request_requirements=["initial_auth", "spn", "spn_values", "kerberos"],
        request_values={
            "initial_auth": True
            if (U, X) in state.usable_identity
            else None
            if (U, X) in state.authentication_unknown
            else False,
            "spn": fact.value,
            "spn_values": None if spns.value is None else bool(spns.value),
            "kerberos": value("kerberos_authentication_usable", U, X),
            "request_ok": value("service_ticket_request_accepted", U, V),
        },
    )


def rank_synthetic(graph, query):
    payload, bindings = ranking_inputs(graph, query)
    result = run_attack_query(query, graph, action_bindings=bindings, ranking_query=payload)
    assert not result.is_minimum_proven_over_scope
    return {"result_payload": result.ranking_result, "public_query": result}


def seamless_run(raw_dir, code_version):
    """Pinned raw locators, full topology, aggregate output only; no observed exploit."""
    from src.data.manifest import load_manifest, verify_manifest
    from src.parser import ManifestRawDataLoader
    from src.parser.adapters import adapt_bloodhound_v3_records
    from src.parser.cli import canonicalize_graph, load_time_policy
    from src.parser.snapshot_facts import graph_digest

    manifest_path = ROOT / "data/samples/manifests/seamless-raw-v1.json"
    if not raw_dir.is_dir():
        return {"disposition": "SKIP", "prerequisite": "private pinned SEAMLESS raw inputs"}
    manifest = load_manifest(manifest_path)
    expected = "sha256:e0601d763eeea285d268ec9e468d321c50c9d7faba53c8e7442a2fcc4159c812"
    if manifest["snapshot_id"] != expected or verify_manifest(raw_dir, manifest):
        raise ValueError("SEAMLESS manifest verification failed")
    loader = ManifestRawDataLoader(
        manifest_path,
        time_policy=load_time_policy(ROOT / "tests/fixtures/ranking/seamless_time_policy.json"),
    )
    raw = tuple(loader.load(raw_dir))
    raw_before = copy.deepcopy(raw)
    normalized = IdentityNormalizer().normalize_records(adapt_bloodhound_v3_records(raw))
    normalized_before = copy.deepcopy(normalized)
    aliases = {}
    pins = {
        "U": "#/users/1580",
        "V_K": "#/users/11",
        "V_D": "#/users/917",
        "G30": "#/groups/30",
        "G31": "#/groups/31",
        "G548": "#/groups/548",
        "G_DA": "#/groups/40",
        "C0": "#/computers/0",
    }
    for alias, locator in pins.items():
        matches = {
            r.id
            for r in normalized
            for source in r.raw_representations or (r.raw,)
            if source.provenance.get("record_locator") == locator
        }
        if len(matches) != 1:
            raise ValueError("audited raw locator did not resolve uniquely")
        aliases[alias] = matches.pop()
    builder = DirectGraphBuilder(
        metadata={
            "snapshot_id": expected,
            "created_at": "2026-10-07T00:00:00Z",
            "code_version": code_version,
        }
    )
    graph, facts = builder.build_snapshot(normalized)
    graph = canonicalize_graph(graph)
    baseline_graph = canonicalize_graph(builder.build(normalized))
    assert graph == baseline_graph
    engine = EngineGraph.from_snapshot(serialize_snapshot(graph, facts))
    u, vk, vd, c = (aliases[k] for k in ("U", "V_K", "V_D", "C0"))
    # H0 is a declared authentication context; Computer0 identity does not imply control.
    query = {
        "initial_actor": u,
        "initial_state": {"known_identity": [vk], "usable_identity": [[u, c]]},
        "authentication_context": c,
        "target": c,
        "target_goal": {"target": c, "required_state": {"admin_control": [c]}},
        "allowed_techniques": sorted(
            OWNERS
            | {
                "propagate_group_entitlement",
                "scenario_reset_password",
                "acquire_reset_identity",
                "obtain_admin_execution_on_host",
            }
        ),
        "budget": {"max_paths": 2, "max_steps": 12, "max_expansions": 100000},
        "scenario_reference": "seamless-216-declared-initial-U",
    }
    raw_result = run_attack_query(query, engine)
    request = next(a for a in raw_result.attempts if a.request.technique_id == "kerberoast_request")
    assert request.status.value == "indeterminate" and not request.additions.service_ticket_material
    spn = facts.lookup(vk, "has_spn")
    values = facts.lookup(vk, "service_principal_names")
    assert spn.value is True and values.value and engine.node(vk)["enabled"] is True
    edges = graph["edges"]
    # Audit exact downstream support independent of generator output.
    expected_pairs = [
        (vk, aliases["G31"], "MemberOf"),
        (aliases["G31"], aliases["G548"], "MemberOf"),
        (aliases["G548"], aliases["G30"], "MemberOf"),
        (aliases["G30"], vd, "GenericAll"),
        (vd, aliases["G_DA"], "MemberOf"),
        (vd, c, "AdminTo"),
    ]
    downstream = []
    for source, target, kind in expected_pairs:
        support = [
            e for e in edges if (e["source"], e["target"], e["kind"]) == (source, target, kind)
        ]
        assert len(support) == 1 and support[0]["provenance"]
        downstream.append(
            {
                "kind": kind,
                "provenance_records": len(support[0]["provenance"]),
                "derived": bool(support[0].get("derivation")),
            }
        )
    # Scenario outcomes carry source/rationale/method/budget/horizon; no numeric ratings.
    assumed = copy.deepcopy(query)
    scenario_facts = [
        assumption("kerberos_authentication_usable", u, c),
        assumption("network_kdc_reachable", u, vk),
        assumption("service_ticket_request_accepted", u, vk),
        assumption(
            "recovery_success",
            u,
            vk,
            method="scenario-offline-password",
            budget="unmeasured-declared-budget",
            horizon="fixed-snapshot-window",
        ),
    ]
    for user in (vk, vd):
        scenario_facts += [
            assumption(p, user, c)
            for p in ("secret_valid", "network_kdc_reachable", "authentication_accepted")
        ]
    for user in (u, vk):
        for group in ("G31", "G548", "G30"):
            scenario_facts += [
                assumption(p, user, aliases[group]) for p in ("security_group", "membership_usable")
            ]
        scenario_facts += [
            assumption(p, user, vd)
            for p in ("network_rpc_reachable", "password_policy_accepts", "directory_write_allowed")
        ]
    scenario_facts += [
        assumption(p, vd, aliases["G_DA"]) for p in ("security_group", "membership_usable")
    ]
    scenario_facts.append(assumption("admin_channel", vd, c))
    for fact in scenario_facts:
        fact["scope"] = "SEAMLESS-216-declared-scenario/H0"
        fact["rationale"] = "Declared scenario outcome, absent from raw; no observed exploit"
        fact["provenance_reference"] = "scenario://216/seamless-outcome"
    assumed["assumptions"] = scenario_facts
    baseline_query = copy.deepcopy(assumed)
    baseline_query["allowed_techniques"] = [
        t for t in assumed["allowed_techniques"] if t not in OWNERS
    ]
    baseline = run_attack_query(baseline_query, engine)
    extension = run_attack_query(assumed, engine)
    # A separately declared witness isolates the roast prefix; it is not the baseline comparison.
    witness_query = copy.deepcopy(assumed)
    witness_query["assumptions"] = [
        f
        for f in assumed["assumptions"]
        if not (f["subject"] == u and f["predicate"] in {"security_group", "membership_usable"})
    ]
    witness_query["budget"]["max_paths"] = 1
    witness = run_attack_query(witness_query, engine)
    assert witness.final_goal_reached
    witness_program = [s.result.request.technique_id for s in witness.paths[0].transition_history]
    assert all(owner in witness_program for owner in OWNERS)
    assert raw == raw_before and normalized == normalized_before
    assert engine.to_canonical() == graph == baseline_graph

    def aggregate(result):
        from collections import Counter

        return {
            "asset_goal": result.final_goal_reached,
            "truncated": result.truncated,
            "reason": result.truncation_reason,
            "expansions": result.expansions,
            "paths": len(result.paths),
            "programs": [
                [s.result.request.technique_id for s in p.transition_history] for p in result.paths
            ],
            "owner_status_counts": dict(
                sorted(
                    Counter(
                        a.request.technique_id + ":" + str(a.status) for a in result.attempts
                    ).items()
                )
            ),
        }

    return {
        "disposition": "PASS",
        "evidence": "actual_manifest_verified_SEAMLESS",
        "snapshot_id": expected,
        "canonical_digest": graph_digest(graph),
        "nodes": len(graph["nodes"]),
        "edges": len(edges),
        "facts": {
            "target_locator": pins["V_K"],
            "has_spn": True,
            "enabled": True,
            "spn_values_count": len(values.value),
            "origins": len(spn.evidence),
        },
        "request": {
            "status": str(request.status),
            "unknown": list(request.unknown),
            "snapshot_evidence_records": len(request.snapshot_evidence),
        },
        "downstream_support": downstream,
        "raw_query": aggregate(raw_result),
        "baseline_assumed": aggregate(baseline),
        "extension_assumed": aggregate(extension),
        "roast_witness_separate_scope": aggregate(witness),
        "witness_scope_delta": "U membership gates withheld; not used for coverage comparison",
        "witness_input_digest": digest(witness_query),
        "initial_state_declaration": "usable U=User1580 / H0=Computer0; not observed credential",
        "scenario_assumptions": [
            {
                "predicate": f["predicate"],
                "subject_alias": next(k for k, v in aliases.items() if v == f["subject"]),
                "target_alias": next(k for k, v in aliases.items() if v == f["target"]),
                "origin": "declared_assumption",
                "scope": f["scope"],
                "rationale": f["rationale"],
                "metadata": f["assumption_metadata"],
            }
            for f in scenario_facts
        ],
        "baseline_shared_input_digest": digest(
            {k: v for k, v in baseline_query.items() if k != "allowed_techniques"}
        ),
        "extension_shared_input_digest": digest(
            {k: v for k, v in assumed.items() if k != "allowed_techniques"}
        ),
        "scenario_input_digest": digest(assumed),
        "caps": assumed["budget"],
        "invariants": {"complete_graph_equal": True, "raw_normalized_equal": True},
        "asset_delta": "no_new_asset_if_baseline_reached; only_generated_scope",
        "observed_attack_success": False,
        "runtime_recovery": "unknown_without_scenario_assumptions",
        "scoring": "effort_likelihood_impact_unrated",
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--code-version", required=True)
    parser.add_argument("--raw-dir", type=Path)
    parser.add_argument("--snapshot", type=Path)
    parser.add_argument("--query", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    if bool(args.snapshot) != bool(args.query):
        parser.error("--snapshot and --query must be supplied together")
    if args.snapshot:
        graph = EngineGraph.from_snapshot(args.snapshot.read_text(encoding="utf-8"))
        query = json.loads(args.query.read_text(encoding="utf-8"))
        output = {
            "case": summary(run_attack_query(query, graph)),
            "input_digest": digest(query),
            "code_version": args.code_version,
        }
        output["semantic_digest"] = digest(output)
        encoded = json.dumps(output, sort_keys=True, ensure_ascii=False)
        if args.output:
            args.output.write_text(encoded + "\n", encoding="utf-8")
        else:
            print(encoded)
        return 0
    output = synthetic_run()
    graph, query = synthetic()
    ranked = rank_synthetic(graph, query)["result_payload"]
    assessment = ranked["diagnostics"]["generated_0001"]["assessment"]
    output["canonical_evaluator"] = {
        "adapted": ranked["search_audit"]["candidates_adapted"],
        "gate_status": assessment["status"],
        "effort_status": assessment["effort_status"],
        "effort": assessment["effort"],
        "likelihood_interval": assessment["likelihood_interval"],
        "active_work_units": assessment["program"],
        "impact": assessment["impact"],
    }
    if args.raw_dir is not None:
        output["SEAMLESS"] = seamless_run(args.raw_dir, args.code_version)
    output["code_version"] = args.code_version
    output["semantic_digest"] = digest(output)
    encoded = json.dumps(output, sort_keys=True, ensure_ascii=False)
    if args.output:
        args.output.write_text(encoded + "\n", encoding="utf-8")
    else:
        print(encoded)
    return 2 if output.get("SEAMLESS", {}).get("disposition") == "SKIP" else 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, AssertionError) as exc:
        import traceback

        frame = traceback.extract_tb(exc.__traceback__)[-1]
        print(
            json.dumps(
                {
                    "disposition": "FAIL",
                    "error_type": type(exc).__name__,
                    "stage": frame.name,
                    "line": frame.lineno,
                }
            )
        )
        raise SystemExit(1) from None
