"""#229 fixture and bindings for public query/CLI; no second engine."""

import json
from dataclasses import asdict
from pathlib import Path

from src.engine.graph import EngineGraph
from src.engine.query import materialize_query

ROOT = Path(__file__).resolve().parents[2]
X = "10000000-0000-4000-8000-000000000001"
U_R = "S-1-5-21-1000-2000-3000-1580"
M = "S-1-5-21-1000-2000-3000-2075"
C_R = "10000000-0000-4000-8000-000000000027"
P = "S-1-5-21-1000-2000-3000-917"
PROGRAMS = [
    [
        "rbcd_acquire_secret",
        "rbcd_prepare_service",
        "rbcd_configure_descriptor",
        "rbcd_delegate_service",
        "rbcd_service_admin",
    ],
    [
        "rbcd_acquire_secret",
        "rbcd_configure_descriptor",
        "rbcd_prepare_service",
        "rbcd_delegate_service",
        "rbcd_service_admin",
    ],
    [
        "rbcd_configure_descriptor",
        "rbcd_acquire_secret",
        "rbcd_prepare_service",
        "rbcd_delegate_service",
        "rbcd_service_admin",
    ],
]


def inputs():
    folder = ROOT / "tests/fixtures/rbcd"
    return (
        EngineGraph.from_snapshot((folder / "snapshot.json").read_text()),
        json.loads((folder / "query.json").read_text()),
    )


def ranking_inputs(graph, query):
    """Declarative synthetic RBCD action and work-unit bindings.

    Missing numeric data remains unrated.
    """
    materialized = materialize_query(query, graph)
    if not materialized.runtime_context.rbcd_bindings:
        raise ValueError("query requires at least one rbcd_binding")
    b = materialized.runtime_context.rbcd_bindings[0]
    u, m, c, p, x = b.controller, b.principal, b.target, b.impersonated, b.authentication_context

    bindings = {
        ("rbcd_acquire_secret", u, u, m): "action_rbcd_acquire_secret",
        ("rbcd_prepare_service", u, u, m): "action_rbcd_prepare_service",
        ("rbcd_configure_descriptor", u, u, c): "action_rbcd_configure_descriptor",
        ("rbcd_delegate_service", u, u, c): "action_rbcd_delegate_service",
        ("rbcd_service_admin", u, u, c): "action_rbcd_service_admin",
    }

    derived_predicates = {
        "reset_M",
        "service_M",
        "descriptor_M_C_R",
        "delegated_P_C_R",
        "admin_C_R",
    }
    all_predicates = [
        "usable_U_R",
        "reset_M",
        "spn_M",
        "service_M",
        "descriptor_M_C_R",
        "delegated_P_C_R",
        "admin_C_R",
    ]
    layers = {p: 3 for p in all_predicates}
    layers["spn_M"] = 1

    assumed_facts = [
        {
            "predicate": p,
            "layer": 3,
            "truth_value": (p not in derived_predicates),
            "rationale": "Synthetic query declarations; not empirical probability",
            "provenance_reference": "synthetic://229/binding",
        }
        for p in all_predicates
        if p != "spn_M"
    ]

    observed_facts = [
        {
            "predicate": "spn_M",
            "layer": 1,
            "truth_value": True,
            "rationale": "Snapshot fact",
            "provenance_reference": "synthetic://229/binding",
        }
    ]

    actions = [
        {
            "action_id": "action_rbcd_acquire_secret",
            "technique": "rbcd_acquire_secret",
            "technique_name": "rbcd_acquire_secret",
            "actor_id": u,
            "target_id": m,
            "requires": ["usable_U_R"],
            "adds": ["reset_M"],
            "is_passive_closure": False,
            "referenced_work_unit_ids": ["work_rbcd_acquire_secret"],
        },
        {
            "action_id": "action_rbcd_prepare_service",
            "technique": "rbcd_prepare_service",
            "technique_name": "rbcd_prepare_service",
            "actor_id": u,
            "target_id": m,
            "requires": ["reset_M", "spn_M"],
            "adds": ["service_M"],
            "is_passive_closure": False,
            "referenced_work_unit_ids": ["work_rbcd_prepare_service"],
        },
        {
            "action_id": "action_rbcd_configure_descriptor",
            "technique": "rbcd_configure_descriptor",
            "technique_name": "rbcd_configure_descriptor",
            "actor_id": u,
            "target_id": c,
            "requires": ["usable_U_R"],
            "adds": ["descriptor_M_C_R"],
            "is_passive_closure": False,
            "referenced_work_unit_ids": ["work_rbcd_configure_descriptor"],
        },
        {
            "action_id": "action_rbcd_delegate_service",
            "technique": "rbcd_delegate_service",
            "technique_name": "rbcd_delegate_service",
            "actor_id": u,
            "target_id": c,
            "requires": ["service_M", "descriptor_M_C_R"],
            "adds": ["delegated_P_C_R"],
            "is_passive_closure": False,
            "referenced_work_unit_ids": ["work_rbcd_delegate_service"],
        },
        {
            "action_id": "action_rbcd_service_admin",
            "technique": "rbcd_service_admin",
            "technique_name": "rbcd_service_admin",
            "actor_id": u,
            "target_id": c,
            "requires": ["delegated_P_C_R"],
            "adds": ["admin_C_R"],
            "is_passive_closure": False,
            "referenced_work_unit_ids": ["work_rbcd_service_admin"],
        },
    ]

    unit_bindings = {
        "work_rbcd_acquire_secret": {
            "owner": m,
            "authentication_context": x,
            "success_event": "rbcd_secret",
            "summary": f"rbcd_acquire_secret owner={m} context={x}; success=rbcd_secret",
        },
        "work_rbcd_prepare_service": {
            "owner": m,
            "authentication_context": x,
            "success_event": "controlled_service",
            "summary": f"rbcd_prepare_service owner={m} context={x}; success=controlled_service",
        },
        "work_rbcd_configure_descriptor": {
            "owner": c,
            "authentication_context": x,
            "success_event": "rbcd_descriptor",
            "summary": f"rbcd_configure_descriptor owner={c} context={x}; success=rbcd_descriptor",
        },
        "work_rbcd_delegate_service": {
            "owner": p,
            "authentication_context": c,
            "success_event": "delegated_service_context",
            "summary": (
                f"rbcd_delegate_service owner={p} context={c}; success=delegated_service_context"
            ),
        },
        "work_rbcd_service_admin": {
            "owner": c,
            "authentication_context": c,
            "success_event": "admin_execution_on_C_R",
            "summary": (
                f"rbcd_service_admin owner={c} context={c}; success=admin_execution_on_C_R"
            ),
        },
    }

    units = {
        name: {
            "alias": name,
            "rating_status": "unrated",
            "overlap_state": "independent",
            "computed_cost": None,
            "effort_cost": None,
            "summary": spec["summary"],
            "event_binding": {
                "owner": spec["owner"],
                "authentication_context": spec["authentication_context"],
                "success_event": spec["success_event"],
                "method_budget_horizon": None,
            },
            "technical_source": "synthetic://229/event-binding",
            "applicable_queries": [query.get("ranking_query_id", "query-229")],
            "missing_basis_reasons": ["no_numeric_basis"],
        }
        for name, spec in unit_bindings.items()
    }

    query_id = query.get("ranking_query_id", "query-229")
    payload = {
        "query_metadata": {
            "query_id": query_id,
            "version": "1.0.0",
            "scenario_id": query.get("scenario_reference", "synthetic-229"),
            "scenario_version": "1.0.0",
            "snapshot_id": graph.metadata["snapshot_id"],
            "evaluation_mode": "scenario",
            "work_boundary": "scoped-rbcd-delegation",
            "foothold_node_id": materialized.initial_actor,
            "horizon": "fixed-snapshot-window",
            "active_work_budget": 10,
            "target_goal": {
                "goal_id": "admin-control-C_R",
                "target_asset_id": c,
                "required_predicates": ["admin_C_R"],
            },
            "bound_rbcd_binding": asdict(b),
        },
        "facts_ledger": {
            "predicate_layers": layers,
            "observed_facts": observed_facts,
            "assumed_facts": assumed_facts,
            "unknown_facts": [],
            "false_facts": [],
        },
        "bound_actions": actions,
        "work_units_ledger": units,
        "conditional_bounds_table": [],
        "target_impact_assessments": {
            c: {
                "target_asset_id": c,
                "success_event": "admin_execution_on_C_R",
                "rating_status": "unrated",
                "consequence_rating": None,
                "business_rationale": None,
                "affected_business_services": [],
                "missing_basis_reasons": ["no_business_impact_basis"],
            }
        },
    }
    return payload, bindings


def build_assumed_query(
    raw_query: dict,
    scope: str = "seamless-229/assumed",
    rationale: str = "Explicit scoped assumption for extension evaluation; not observed success",
    provenance_reference: str = "seamless://229/assumed-ledger",
) -> dict:
    """Construct a distinct ASSUMED query with an explicit positive assumption ledger.

    RAW preserves unassumed/unresolved gates; ASSUMED receives explicit scoped
    positive assumptions for the 20 RBCD runtime gates. Graph and snapshot bytes
    remain completely identical between RAW and ASSUMED.
    """
    import copy

    assumed = copy.deepcopy(raw_query)
    assumptions = []
    for binding in assumed.get("rbcd_bindings", []):
        u = binding["controller"]
        m = binding["principal"]
        p = binding["impersonated"]
        c = binding["target"]
        x = binding.get("authentication_context", c)
        s = binding.get("service_context", c)
        service = binding.get("service", "winrm")
        spn = binding.get("spn", "")

        meta = {
            "controller": u,
            "principal": m,
            "impersonated": p,
            "target": c,
            "authentication_context": x,
            "service_context": s,
            "service": service,
            "spn": spn,
            "declared_by": "assumed-ledger-builder",
        }

        # R1 & R2 gates on M
        for pred in (
            "effective_reset_right",
            "directory_write_allowed",
            "password_policy_accepts",
            "secret_valid",
            "key_derivation_accepted",
            "key_encryption_compatible",
            "service_authentication_accepted",
            "network_kdc_reachable",
        ):
            assumptions.append(
                {
                    "predicate": pred,
                    "subject": u,
                    "target": m,
                    "value": True,
                    "scope": scope,
                    "rationale": rationale,
                    "provenance_reference": provenance_reference,
                    "assumption_metadata": meta,
                }
            )

        # R3 & R4 gates on C_R
        for pred in (
            "effective_descriptor_write",
            "directory_write_allowed",
            "target_spn_binding",
            "delegation_policy_allows",
            "network_kdc_reachable",
            "s4u_request_accepted",
        ):
            assumptions.append(
                {
                    "predicate": pred,
                    "subject": u,
                    "target": c,
                    "value": True,
                    "scope": scope,
                    "rationale": rationale,
                    "provenance_reference": provenance_reference,
                    "assumption_metadata": meta,
                }
            )

        # R5 asset execution gates on C_R
        for pred in (
            "target_spn_binding",
            "network_winrm_reachable",
            "service_winrm_running",
            "endpoint_authorized",
            "winrm_authentication_accepted",
            "admin_execution_context",
        ):
            assumptions.append(
                {
                    "predicate": pred,
                    "subject": p,
                    "target": c,
                    "value": True,
                    "scope": scope,
                    "rationale": rationale,
                    "provenance_reference": provenance_reference,
                    "assumption_metadata": meta,
                }
            )

    assumed["assumptions"] = assumptions
    return assumed


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
    pins = {
        "U_R": "#/users/1580",
        "M": "#/users/2075",
        "C_R": "#/computers/27",
        "P": "#/users/917",
    }
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
    u, m, c, p = (aliases[k] for k in ("U_R", "M", "C_R", "P"))
    binding = {
        "controller": u,
        "principal": m,
        "impersonated": p,
        "target": c,
        "authentication_context": c,
        "service_context": c,
        "service": "winrm",
        "spn": "http/computer27.example.test",
    }
    raw_query = {
        "source_foothold": c,
        "initial_actor": u,
        "initial_state": {
            "control": [],
            "usable_identity": [[u, c]],
            "known_identity": [m, p],
        },
        "authentication_context": c,
        "target": c,
        "target_goal": {"target": c, "required_state": {"admin_control": [c]}},
        "rbcd_bindings": [binding],
        "assumptions": [],
        "allowed_techniques": [
            "rbcd_acquire_secret",
            "rbcd_prepare_service",
            "rbcd_configure_descriptor",
            "rbcd_delegate_service",
            "rbcd_service_admin",
        ],
        "budget": {"max_paths": 50, "max_steps": 10, "max_expansions": 5000},
        "scenario_reference": "seamless-229-rbcd-delegation",
    }
    assumed_query = build_assumed_query(
        raw_query,
        scope="seamless-229/assumed",
        rationale="Explicit scoped assumption for private evaluation; not empirical observation",
        provenance_reference="seamless://229/assumed-ledger",
    )
    trace = {
        "locators": pins,
        "snapshot_id": expected,
        "support": [],
        "outcomes": "RAW unresolved; ASSUMED declared only",
    }
    return engine, raw_query, assumed_query, trace
