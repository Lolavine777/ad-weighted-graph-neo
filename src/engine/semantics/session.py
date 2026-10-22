"""Conditional session identity acquisition in the declared authentication context."""

from .catalog import _authoritative_technique
from .models import FactOrigin, PrerequisiteDecision, StructuralRelationship
from .state import AttackState
from .transitions import Status, TransitionResult


def evaluate_session(graph, state, request, context, technique):
    reference = _authoritative_technique("use_session_identity")
    if reference is None or any(
        getattr(reference, field) != getattr(technique, field)
        for field in ("relationship", "source_kinds", "target_kinds", "prerequisites", "effects")
    ):
        raise ValueError("session identity recipe cannot change executable gates")
    host, owner, scope = request.source, request.target, context.authentication_context
    nodes = graph.nodes_by_id
    failed, unknown, satisfied, decisions = [], [], [], []

    def gate(name, value, fact=None):
        (satisfied if value is True else failed if value is False else unknown).append(name)
        decisions.append(
            PrerequisiteDecision(
                name,
                value is True,
                fact.origin
                if fact
                else (FactOrigin.UNKNOWN if value is None else FactOrigin.TECHNICAL_RULE),
                fact,
                fact.rationale if fact else "Session acquisition checks branch state and context",
            )
        )

    gate("endpoints_present", all(n in nodes for n in (request.actor, host, owner)))
    gate("source_kind", nodes.get(host, {}).get("kind") == "Computer")
    gate("target_kind", nodes.get(owner, {}).get("kind") == "User")
    gate("authentication_context_present", scope in nodes and nodes[scope]["kind"] == "Computer")
    # Neo supports same-domain reusable credentials; token/credential scope is not inferred.
    participants = [nodes.get(n, {}) for n in (host, owner, scope)]
    gate(
        "session_identity_scope",
        all(n.get("domain") and not n.get("is_boundary", False) for n in participants)
        and len({n.get("domain", "").casefold() for n in participants}) == 1,
    )
    relation = StructuralRelationship(host, "HasSession", owner)
    gate("relationship_exists", relation in graph.relationships)
    gate("source_admin_control", host in state.admin_control)
    gate("target_enabled", nodes.get(owner, {}).get("enabled"))
    for name in (
        "session_fresh",
        "session_present",
        "credential_accessible",
        "session_identity_usable",
        "network_kdc_reachable",
        "authentication_accepted",
    ):
        subject, target = (
            (owner, scope)
            if name in {"network_kdc_reachable", "authentication_accepted"}
            else (host, owner)
        )
        fact = context.facts.get((name, subject, target))
        value = None if fact is None or fact.origin == FactOrigin.UNKNOWN else fact.value
        if fact and (fact.assumption_metadata or {}).get("authentication_context", scope) != scope:
            value = None
        gate(name, value, fact)
    status = Status.BLOCKED if failed else Status.INDETERMINATE if unknown else Status.APPLICABLE
    additions = (
        AttackState(known_identity={owner}, usable_identity={(owner, scope)})
        if status == Status.APPLICABLE
        else AttackState()
    )
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
    )
