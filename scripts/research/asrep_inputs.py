"""#228 fixture and bindings for the existing public query/CLI; no second engine."""

import json
from pathlib import Path

from scripts.research.credential_bindings import credential_ranking_inputs
from src.engine.graph import EngineGraph
from src.engine.query import materialize_query

ROOT = Path(__file__).resolve().parents[2]
X = "10000000-0000-4000-8000-000000000001"
C = "10000000-0000-4000-8000-000000000002"
V = "S-1-5-21-1000-2000-3000-1700"
G = "S-1-5-21-1000-2000-3000-512"
PROGRAM = [
    "asrep_request",
    "recover_asrep_secret",
    "activate_recovered_identity",
    "propagate_group_entitlement",
    "scenario_winrm_admin",
]


def inputs():
    folder = ROOT / "tests/fixtures/asrep"
    return (
        EngineGraph.from_snapshot((folder / "snapshot.json").read_text()),
        json.loads((folder / "query.json").read_text()),
    )


def ranking_inputs(graph, query):
    materialized = materialize_query(query, graph)
    state, ctx = materialized.initial_attack_state, materialized.runtime_context
    request = ctx.facts.get(("asrep_request_accepted", X, V))
    return credential_ranking_inputs(
        graph,
        query,
        actor=X,
        owner=V,
        context=X,
        group=G,
        asset=C,
        program=PROGRAM,
        material_field="asrep_material",
        snapshot_requirements=["preauth_off"],
        request_requirements=["request_capability", "preauth_off", "owner_enabled"],
        request_values={
            "request_capability": (X, X) in state.asrep_request_capability,
            "preauth_off": graph.snapshot_facts.lookup(V, "dontreqpreauth").value,
            "request_ok": request.value if request else None,
        },
    )


def seamless_inputs(raw_dir, revision):
    """Prepare private RAW/ASSUMED queries only after the pinned manifest verifies.

    Returned graph/queries contain private canonical identities: save only locally.
    The aggregate trace contains reviewed public aliases/locators, never secrets.
    This prepares inputs for src.engine.query_cli; it does not execute a query.
    """
    from src.data.manifest import load_manifest, verify_manifest
    from src.parser import DirectGraphBuilder, IdentityNormalizer, ManifestRawDataLoader
    from src.parser.adapters import adapt_bloodhound_v3_records
    from src.parser.cli import canonicalize_graph, load_time_policy
    from src.parser.snapshot_facts import serialize_snapshot

    raw_dir = Path(raw_dir)
    if not raw_dir.is_dir():
        raise FileNotFoundError("private manifest-verified SEAMLESS raw inputs required")
    manifest_path = ROOT / "data/samples/manifests/seamless-raw-v1.json"
    manifest = load_manifest(manifest_path)
    expected = "sha256:e0601d763eeea285d268ec9e468d321c50c9d7faba53c8e7442a2fcc4159c812"
    if manifest["snapshot_id"] != expected or verify_manifest(raw_dir, manifest):
        raise ValueError("SEAMLESS manifest verification failed")
    loader = ManifestRawDataLoader(
        manifest_path,
        time_policy=load_time_policy(ROOT / "tests/fixtures/ranking/seamless_time_policy.json"),
    )
    normalized = IdentityNormalizer().normalize_records(
        adapt_bloodhound_v3_records(loader.load(raw_dir))
    )
    pins = {"V_A": "#/users/1700", "G_DA": "#/groups/40", "C0": "#/computers/0"}
    aliases = {}
    for alias, locator in pins.items():
        matches = {
            r.id
            for r in normalized
            for source in r.raw_representations or (r.raw,)
            if source.provenance.get("record_locator") == locator
        }
        if len(matches) != 1:
            raise ValueError("reviewed locator must resolve uniquely")
        aliases[alias] = matches.pop()
    builder = DirectGraphBuilder(
        metadata={
            "snapshot_id": expected,
            "created_at": "2026-10-08T00:00:00Z",
            "code_version": revision,
        }
    )
    canonical, facts = builder.build_snapshot(normalized)
    canonical = canonicalize_graph(canonical)
    engine = EngineGraph.from_snapshot(serialize_snapshot(canonical, facts))
    v, g, c = (aliases[k] for k in ("V_A", "G_DA", "C0"))
    raw_query = {
        "source_foothold": c,
        "initial_actor": c,
        "initial_state": {
            "control": [],
            "known_identity": [v],
            "asrep_request_capability": [[c, c]],
        },
        "authentication_context": c,
        "target": c,
        "target_goal": {"target": c, "required_state": {"admin_control": [c]}},
        "checkpoint_goal": {"target": g, "required_state": {"effective_member": [[v, g]]}},
        "allowed_techniques": PROGRAM[:4] + ["obtain_admin_execution_on_host"],
        "budget": {"max_paths": 50, "max_steps": 9, "max_expansions": 5000},
        "scenario_reference": "seamless-228-declared-request-capability",
    }

    def assumption(predicate, subject, target, **metadata):
        return {
            "predicate": predicate,
            "subject": subject,
            "target": target,
            "value": True,
            "scope": "seamless-228/C0",
            "rationale": "Declared prediction outcome, not observed success",
            "provenance_reference": "scenario://228/explicit-outcomes",
            "assumption_metadata": {
                "declared_by": "228-handoff-proposal",
                "authentication_context": c,
                **metadata,
            },
        }

    assumed = {
        **raw_query,
        "assumptions": [
            assumption("network_kdc_reachable", c, v),
            assumption("asrep_request_accepted", c, v),
            assumption(
                "recovery_success",
                c,
                v,
                method="offline-password-prediction",
                budget="unmeasured-budget",
                horizon="fixed-snapshot-window",
            ),
            *[
                assumption(p, v, c)
                for p in (
                    "secret_valid",
                    "network_kdc_reachable",
                    "authentication_accepted",
                    "admin_channel",
                )
            ],
            *[assumption(p, v, g) for p in ("security_group", "membership_usable")],
        ],
    }
    preauth = facts.lookup(v, "dontreqpreauth")
    support = []
    for kind, endpoint in (("MemberOf", g), ("AdminTo", c)):
        edges = [
            e
            for e in canonical["edges"]
            if (e["source"], e["target"], e["kind"]) == (v, endpoint, kind)
        ]
        support.append(
            {
                "kind": kind,
                "count": len(edges),
                "provenance_records": sum(len(e["provenance"]) for e in edges),
            }
        )
    trace = {
        "locators": pins,
        "snapshot_id": expected,
        "preauth_status": preauth.status,
        "preauth_value": preauth.value,
        "preauth_evidence_count": len(preauth.evidence),
        "support": support,
        "outcomes": "RAW unresolved; ASSUMED declared only",
    }
    return engine, raw_query, assumed, trace
