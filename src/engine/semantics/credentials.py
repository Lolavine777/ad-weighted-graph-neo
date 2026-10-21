"""Small fact/capability producers and shared password recovery/activation boundary."""

import json
from dataclasses import asdict

from .models import CapabilityRelationship, FactOrigin, PrerequisiteDecision
from .state import AttackState, CredentialArtifact
from .transitions import Status, TransitionResult

OWNERS = frozenset(
    {
        "kerberoast_request",
        "recover_ticket_secret",
        "activate_recovered_identity",
        "asrep_request",
        "recover_asrep_secret",
    }
)
RELATIONSHIPS = frozenset(
    {"RoastTarget", "TicketMaterial", "RecoveredSecret", "ASRepTarget", "ASRepMaterial"}
)


def encoded(value):
    """Immutable complete lineage record, safe to transport/deepcopy."""
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def artifacts(state, field, owner, context):
    return tuple(
        sorted(a for a in getattr(state, field) if a.owner == owner and a.context == context)
    )


def producers(nodes, state, actor, context):
    """Knowledge is declared independently; dataset membership grants no discovery."""
    scope = context.authentication_context
    available = {a.owner for a in state.recovered_secret if a.context == scope}
    usable = {u for u, h in state.usable_identity if h == scope}
    material = {a.owner for a in state.service_ticket_material if a.context == scope}
    asrep = {a.owner for a in state.asrep_material if a.context == scope}
    result = {
        CapabilityRelationship(actor, "RoastTarget", target)
        for target in state.known_identity
        if nodes.get(target, {}).get("kind") == "User"
        and target not in available | usable | material
    }
    result.update(
        CapabilityRelationship(actor, "ASRepTarget", target)
        for target in state.known_identity
        if nodes.get(target, {}).get("kind") == "User" and target not in available | usable | asrep
    )
    result.update(
        CapabilityRelationship(actor, "ASRepMaterial", target)
        for target in asrep - available - usable
    )
    result.update(
        CapabilityRelationship(actor, "TicketMaterial", target)
        for target in material - available - usable
    )
    if scope in nodes:
        result.update(
            CapabilityRelationship(target, "RecoveredSecret", scope)
            for target in available - usable
        )
    return result


def _recipe(owner):
    from .catalog import _authoritative_technique

    return _authoritative_technique(owner)


def evaluate_artifact(graph, state, request, context, technique):
    """Only applicable gates create an artifact/identity. No reset-specific bypass."""
    reference = _recipe(technique.id)
    if (
        reference is None
        or any(
            set(getattr(technique, field)) != set(getattr(reference, field))
            for field in ("prerequisites", "effects", "source_kinds", "target_kinds")
        )
        or (reference.relationship != technique.relationship)
    ):
        raise ValueError(
            "unsupported artifact recipe; custom catalog must preserve executable gates"
        )
    actor, source, target = request.actor, request.source, request.target
    scope = context.authentication_context
    nodes = graph.nodes_by_id
    failed, unknown, satisfied, decisions = [], [], [], []
    snapshot, lineage = [], []
    additions = AttackState()

    def gate(name, value, origin=FactOrigin.TECHNICAL_RULE, fact=None, rationale=None):
        (satisfied if value is True else failed if value is False else unknown).append(name)
        decisions.append(PrerequisiteDecision(name, value is True, origin, fact, rationale))

    def runtime(name, subject, endpoint):
        fact = context.facts.get((name, subject, endpoint))
        value = None if fact is None or fact.origin == FactOrigin.UNKNOWN else fact.value
        # Optional explicit context metadata cannot silently cross authentication scopes.
        if (
            fact is not None
            and (fact.assumption_metadata or {}).get("authentication_context", scope) != scope
        ):
            value = None
        gate(
            name,
            value,
            fact.origin if fact else FactOrigin.UNKNOWN,
            fact,
            fact.rationale if fact else "required runtime evidence absent",
        )
        return fact

    gate("endpoints_present", all(n in nodes for n in (actor, source, target)))
    gate("source_kind", nodes.get(source, {}).get("kind") in technique.source_kinds)
    gate("target_kind", nodes.get(target, {}).get("kind") in technique.target_kinds)
    gate("authentication_context_present", True if scope in nodes else None)
    gate(
        "authentication_context_kind",
        nodes[scope]["kind"] == "Computer" if scope in nodes else None,
    )
    selected = ()
    if technique.relationship in {"RoastTarget", "ASRepTarget"}:
        gate("source_is_actor", source == actor)
        gate("known_identity", target in state.known_identity)
        if technique.relationship == "ASRepTarget":
            gate("asrep_request_capability", (actor, scope) in state.asrep_request_capability)
            enabled = nodes.get(target, {}).get("enabled")
            gate(
                "target_enabled",
                enabled,
                FactOrigin.UNKNOWN if enabled is None else FactOrigin.OBSERVED_EVIDENCE,
                rationale="supported conservative request scope requires canonical enabled=True",
            )
        else:
            authenticated = (actor, scope) in state.usable_identity
            gate(
                "kerberos_actor_authenticated",
                True
                if authenticated
                else None
                if scope is None or (actor, scope) in state.authentication_unknown
                else False,
            )
        fact_names = (
            ("dontreqpreauth",)
            if technique.relationship == "ASRepTarget"
            else ("has_spn", "service_principal_names")
        )
        for name in fact_names:
            fact = graph.snapshot_facts.lookup(target, name) if graph.snapshot_facts else None
            value = (
                None
                if fact is None or fact.status == "unknown"
                else (bool(fact.value) if name == "service_principal_names" else fact.value)
            )
            gate(
                name,
                value,
                FactOrigin.OBSERVED_EVIDENCE
                if fact and fact.status == "known"
                else FactOrigin.UNKNOWN,
            )
            if fact:
                snapshot.append(
                    encoded(
                        {
                            "subject": fact.subject,
                            "name": fact.name,
                            "status": fact.status,
                            "value": fact.value,
                            "evidence": [
                                {
                                    "value_json": e.value_json,
                                    "classification": e.classification,
                                    "provenance": dict(e.provenance),
                                }
                                for e in fact.evidence
                            ],
                        }
                    )
                )
        if technique.relationship == "RoastTarget":
            runtime("kerberos_authentication_usable", actor, scope)
        runtime("network_kdc_reachable", actor, target)
        runtime(
            "asrep_request_accepted"
            if technique.relationship == "ASRepTarget"
            else "service_ticket_request_accepted",
            actor,
            target,
        )
    elif technique.relationship in {"TicketMaterial", "ASRepMaterial"}:
        gate("source_is_actor", source == actor)
        is_asrep = technique.relationship == "ASRepMaterial"
        selected = artifacts(
            state, "asrep_material" if is_asrep else "service_ticket_material", target, scope
        )
        gate("asrep_material" if is_asrep else "ticket_material", bool(selected))
        outcome = runtime("recovery_success", actor, target)
        meta = dict(outcome.assumption_metadata or {}) if outcome else {}
        gate(
            "recovery_scope",
            True
            if outcome
            and outcome.scope
            and all(
                isinstance(meta.get(k), str) and meta[k].strip()
                for k in ("method", "budget", "horizon")
            )
            else None,
            FactOrigin.TECHNICAL_RULE,
            outcome,
            "recovery outcome requires method/budget/horizon and scope",
        )
    else:
        selected = artifacts(state, "recovered_secret", source, scope)
        gate("recovered_password", actor == source and bool(selected))
        gate("authentication_context_matches", target == scope)
        enabled = nodes.get(source, {}).get("enabled")
        gate(
            "actor_enabled",
            enabled,
            FactOrigin.UNKNOWN if enabled is None else FactOrigin.OBSERVED_EVIDENCE,
        )
        runtime("secret_valid", source, target)
        runtime("network_kdc_reachable", source, target)
        runtime("authentication_accepted", source, target)
    if selected:
        lineage.extend(selected[0].provenance)
    runtime_lineage = [
        encoded(
            {
                "predicate": d.fact.predicate,
                "subject": d.fact.subject,
                "target": d.fact.target,
                "value": d.fact.value,
                "origin": str(d.fact.origin),
                "scope": d.fact.scope,
                "rationale": d.fact.rationale,
                "provenance_reference": d.fact.provenance_reference,
                "assumption_metadata": dict(d.fact.assumption_metadata or {}),
            }
        )
        for d in decisions
        if d.fact is not None
    ]
    provenance = tuple(
        lineage
        + snapshot
        + [
            encoded(
                {
                    "request": asdict(request),
                    "authentication_context": scope,
                    "runtime": runtime_lineage,
                }
            )
        ]
    )
    status = Status.BLOCKED if failed else Status.INDETERMINATE if unknown else Status.APPLICABLE
    if status == Status.APPLICABLE:
        if technique.relationship == "ASRepTarget":
            additions = AttackState(
                asrep_material={CredentialArtifact(target, scope, "kerberos_asrep", provenance)}
            )
        elif technique.relationship == "RoastTarget":
            additions = AttackState(
                service_ticket_material={
                    CredentialArtifact(target, scope, "kerberos_service_ticket", provenance)
                }
            )
        elif technique.relationship in {"TicketMaterial", "ASRepMaterial"}:
            additions = AttackState(
                recovered_secret={CredentialArtifact(target, scope, "password", provenance)}
            )
        else:
            additions = AttackState(usable_identity={(source, target)})
    return TransitionResult(
        request,
        technique,
        status,
        state,
        additions,
        tuple(failed),
        tuple(unknown),
        tuple(satisfied),
        tuple(decisions),
        tuple(snapshot),
        provenance,
    )


def replay_path(path, graph, catalog=None, *, prepared=None):
    """Re-evaluate exact requests with the same static facts and branch state."""
    from .catalog import load_catalog
    from .evaluator import PreparedSemanticGraph, evaluate
    from .transitions import apply_transition

    if not path.transition_history or path.runtime_context is None:
        raise ValueError("semantic replay requires transition history and runtime context")
    # Reuse only the graph-owned view. A supplied view is an optimization hint,
    # never authority to replay a different graph with the same snapshot_id.
    owned_prepared = (
        graph.to_prepared()
        if hasattr(graph, "to_prepared")
        else PreparedSemanticGraph(graph.to_canonical(), snapshot_facts=graph.snapshot_facts)
    )
    if prepared is not None and prepared is not owned_prepared:
        from src.parser.snapshot_facts import graph_digest

        if (
            not isinstance(prepared, PreparedSemanticGraph)
            or prepared.snapshot_facts != owned_prepared.snapshot_facts
            or (
                prepared._data != owned_prepared._data
                and graph_digest(prepared._data) != graph_digest(owned_prepared._data)
            )
        ):
            raise ValueError("prepared graph does not match replay graph and snapshot facts")
    prepared = owned_prepared
    state = path.transition_history[0].result.before
    effective_catalog = load_catalog() if catalog is None else catalog
    for step in path.transition_history:
        actual = evaluate(
            prepared, state, step.result.request, path.runtime_context, effective_catalog
        )
        if actual != step.result or actual.status != Status.APPLICABLE:
            raise ValueError("semantic replay disagrees with generated transition")
        state = apply_transition(state, actual)
    if state != path.final_state:
        raise ValueError("semantic replay final state mismatch")
    return state
