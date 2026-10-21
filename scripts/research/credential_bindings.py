"""Declarative synthetic credential-chain bindings; no numeric rating invention."""


def credential_ranking_inputs(
    graph,
    query,
    *,
    actor,
    owner,
    context,
    group,
    asset,
    program,
    material_field,
    snapshot_requirements,
    request_requirements,
    request_values,
    work_boundary="scoped-password-recovery",
    goal_id="admin-credential",
    provenance_root="synthetic://credential-binding",
):
    """Independent action/owner/event bindings; missing numeric data remains null."""
    from src.engine.query import materialize_query

    U, V, X, G, C, PROGRAM = actor, owner, context, group, asset, program
    materialized = materialize_query(query, graph)
    state, context = materialized.initial_attack_state, materialized.runtime_context

    def value(predicate, subject, target):
        fact = context.facts.get((predicate, subject, target))
        return fact.value if fact else None

    recovery = context.facts.get(("recovery_success", U, V))
    meta = dict(recovery.assumption_metadata or {}) if recovery else {}
    truth = {
        "known": V in state.known_identity,
        "kdc_request": value("network_kdc_reachable", U, V),
        "request_ok": request_values["request_ok"],
        "recovery_ok": value("recovery_success", U, V),
        "recovery_scope": True
        if recovery and recovery.scope and all(meta.get(k) for k in ("method", "budget", "horizon"))
        else None,
        "valid": value("secret_valid", V, X),
        "kdc_activation": value("network_kdc_reachable", V, X),
        "activation_ok": value("authentication_accepted", V, X),
        "owner_enabled": graph.node(V).get("enabled"),
        "asset_enabled": graph.node(C).get("enabled"),
        "security_group": value("security_group", V, G),
        "membership_usable": value("membership_usable", V, G),
        "host_admin_mapping": value("host_admin_mapping", G, C),
    }
    truth.update(request_values)
    for name in (
        "network_winrm_reachable",
        "service_winrm_running",
        "winrm_authentication_accepted",
        "endpoint_authorized",
        "admin_execution_context",
    ):
        truth[name] = value(name, V, C)
    layers = {p: 3 for p in truth} | {
        p: 3 for p in ("material", "secret", "usable", "member", "admin")
    }
    layers.update({p: 1 for p in snapshot_requirements})
    layers.update({"owner_enabled": 1, "asset_enabled": 1})
    initial = {
        "material": any(a.owner == V and a.context == X for a in getattr(state, material_field)),
        "secret": any(a.owner == V and a.context == X for a in state.recovered_secret),
        "usable": (V, X) in state.usable_identity,
        "member": (V, G) in state.effective_member,
        "admin": C in state.admin_control,
    }
    query_id = query.get("ranking_query_id", "query-216")
    ledger = {
        "predicate_layers": layers,
        "observed_facts": [],
        "assumed_facts": [],
        "unknown_facts": [],
        "false_facts": [],
    }
    for predicate, val in (truth | initial).items():
        layer = layers[predicate]
        if val is None:
            ledger["unknown_facts"].append(
                {"predicate": predicate, "layer": layer, "reason": "missing required basis"}
            )
        else:
            # Initial state is a scenario declaration, including absence. It is
            # never a positive telemetry observation or a snapshot-negative veto.
            bucket = "observed_facts" if layer == 1 else "assumed_facts"
            ledger[bucket].append(
                {
                    "predicate": predicate,
                    "layer": layer,
                    "truth_value": val,
                    "rationale": (
                        "Declared initial scenario state (including absence); not an observation"
                        if predicate in initial
                        else "Synthetic query declarations; not empirical probability"
                    ),
                    "provenance_reference": f"{provenance_root}/binding",
                }
            )
    requires = [
        ["known", *request_requirements, "kdc_request", "request_ok"],
        ["material", "recovery_scope", "recovery_ok"],
        ["secret", "owner_enabled", "valid", "kdc_activation", "activation_ok"],
        ["usable", "owner_enabled", "security_group", "membership_usable"],
        [
            "usable",
            "member",
            "asset_enabled",
            "host_admin_mapping",
            "network_winrm_reachable",
            "service_winrm_running",
            "winrm_authentication_accepted",
            "endpoint_authorized",
            "admin_execution_context",
        ],
    ]
    actions, units, bindings = [], {}, {}
    identities = [(U, U, V), (U, U, V), (V, V, X), (V, V, G), (V, G, C)]
    for i, (owner, endpoints, prerequisites, effect) in enumerate(
        zip(
            PROGRAM,
            identities,
            requires,
            ("material", "secret", "usable", "member", "admin"),
            strict=True,
        )
    ):
        actor, source, target = endpoints
        aid = "action_" + owner
        passive = i == 3
        wid = "work_" + owner
        actions.append(
            {
                "action_id": aid,
                "technique": owner,
                "technique_name": owner,
                "actor_id": actor,
                "target_id": target,
                "requires": prerequisites,
                "adds": [effect],
                "is_passive_closure": passive,
                "referenced_work_unit_ids": [] if passive else [wid],
            }
        )
        bindings[(owner, actor, source, target)] = aid
        if not passive:
            units[wid] = {
                "alias": wid,
                "rating_status": "unrated",
                "overlap_state": "independent",
                "computed_cost": None,
                "effort_cost": None,
                "summary": (
                    f"{owner} owner={source if effect == 'usable' else target} "
                    f"context={X}; success={effect}"
                ),
                "event_binding": {
                    "owner": source if effect == "usable" else target,
                    "authentication_context": X,
                    "success_event": effect,
                    "method_budget_horizon": meta if effect == "secret" else None,
                },
                "technical_source": f"{provenance_root}/event-binding",
                "applicable_queries": [query_id],
                "missing_basis_reasons": ["no_numeric_basis"],
            }
    payload = {
        "query_metadata": {
            "query_id": query_id,
            "version": "1.0.0",
            "scenario_id": query["scenario_reference"],
            "scenario_version": "1.0.0",
            "snapshot_id": graph.metadata["snapshot_id"],
            "evaluation_mode": "scenario",
            "work_boundary": work_boundary,
            "foothold_node_id": materialized.initial_actor,
            "horizon": "fixed-snapshot-window",
            "active_work_budget": 10,
            "target_goal": {
                "goal_id": goal_id,
                "target_asset_id": C,
                "required_predicates": ["admin"],
            },
        },
        "facts_ledger": ledger,
        "bound_actions": actions,
        "work_units_ledger": units,
        "conditional_bounds_table": [],
        "target_impact_assessments": {
            C: {
                "target_asset_id": C,
                "success_event": "admin_execution_on_C",
                "rating_status": "unrated",
                "consequence_rating": None,
                "business_rationale": None,
                "affected_business_services": [],
                "missing_basis_reasons": ["no_business_impact_basis"],
            }
        },
    }
    return payload, bindings
