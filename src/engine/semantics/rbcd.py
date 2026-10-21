"""Bounded RBCD planning owners: no live Kerberos or directory operations."""

from dataclasses import asdict, dataclass

from .credentials import encoded
from .models import FactOrigin, PrerequisiteDecision, StructuralRelationship
from .rbcd_types import DelegationArtifact, DelegationBinding
from .state import AttackState
from .transitions import Status, TransitionResult

# Projection R1--R5 is independent from this concrete owner vocabulary.
RECIPES = {
    "rbcd_acquire_secret": (
        "RBCDReset",
        "rbcd_secret",
        (
            "actor_authenticated",
            "exact_reset_right",
            "effective_reset_right",
            "directory_write_allowed",
            "password_policy_accepts",
        ),
    ),
    "rbcd_prepare_service": (
        "RBCDPrepare",
        "controlled_service",
        (
            "scoped_password",
            "has_spn",
            "service_principal_names",
            "target_enabled",
            "secret_valid",
            "key_derivation_accepted",
            "key_encryption_compatible",
            "service_authentication_accepted",
            "network_kdc_reachable",
        ),
    ),
    "rbcd_configure_descriptor": (
        "RBCDConfigure",
        "rbcd_descriptor",
        (
            "actor_authenticated",
            "known_identity",
            "exact_descriptor_right",
            "effective_descriptor_write",
            "directory_write_allowed",
        ),
    ),
    "rbcd_delegate_service": (
        "RBCDDelegate",
        "delegated_context",
        (
            "controlled_service",
            "rbcd_descriptor",
            "known_impersonated_identity",
            "target_spn_binding",
            "delegation_policy_allows",
            "network_kdc_reachable",
            "s4u_request_accepted",
        ),
    ),
    "rbcd_service_admin": (
        "RBCDAsset",
        "admin_control",
        (
            "delegated_context",
            "target_spn_binding",
            "target_enabled",
            "network_winrm_reachable",
            "service_winrm_running",
            "endpoint_authorized",
            "winrm_authentication_accepted",
            "admin_execution_context",
        ),
    ),
}
OWNERS = frozenset(RECIPES)
RELATIONSHIPS = frozenset(r[0] for r in RECIPES.values())
RUNTIME_GATES = frozenset(
    {
        "effective_reset_right",
        "directory_write_allowed",
        "password_policy_accepts",
        "secret_valid",
        "key_derivation_accepted",
        "key_encryption_compatible",
        "service_authentication_accepted",
        "network_kdc_reachable",
        "effective_descriptor_write",
        "target_spn_binding",
        "delegation_policy_allows",
        "s4u_request_accepted",
        "network_winrm_reachable",
        "service_winrm_running",
        "endpoint_authorized",
        "winrm_authentication_accepted",
        "admin_execution_context",
    }
)


@dataclass(frozen=True)
class RBCDRelationship:
    source: str
    kind: str
    target: str
    binding: DelegationBinding


def selected(state, field, binding):
    return tuple(sorted(a for a in getattr(state, field) if a.binding == binding))


def producers(nodes, state, actor, context):
    result = set()
    for b in context.rbcd_bindings:
        if actor != b.controller or b.authentication_context != context.authentication_context:
            continue
        secret = selected(state, "rbcd_secret", b)
        service = selected(state, "controlled_service", b)
        descriptor = selected(state, "rbcd_descriptor", b)
        delegated = selected(state, "delegated_context", b)
        owners = []
        if not secret and not service:
            owners.append("rbcd_acquire_secret")
        if secret and not service:
            owners.append("rbcd_prepare_service")
        if not descriptor:
            owners.append("rbcd_configure_descriptor")
        if service and descriptor and not delegated:
            owners.append("rbcd_delegate_service")
        if delegated and b.target not in state.admin_control:
            owners.append("rbcd_service_admin")
        for owner in owners:
            target = (
                b.principal
                if owner
                in {
                    "rbcd_acquire_secret",
                    "rbcd_prepare_service",
                }
                else b.target
            )
            result.add(RBCDRelationship(actor, RECIPES[owner][0], target, b))
    return result


def evaluate_rbcd(graph, state, request, context, technique):
    from .catalog import _authoritative_technique

    reference = _authoritative_technique(technique.id)
    if reference is None or technique != reference:
        raise ValueError("unsupported RBCD recipe; preserve executable gates")
    b = request.rbcd_binding
    failed, unknown, satisfied, decisions = [], [], [], []
    snapshot, lineage = [], []

    def gate(name, value, origin=FactOrigin.TECHNICAL_RULE, fact=None):
        (satisfied if value is True else failed if value is False else unknown).append(name)
        decisions.append(PrerequisiteDecision(name, value is True, origin, fact))

    gate("binding_present", b is not None and b in context.rbcd_bindings)
    if b is None:
        return TransitionResult(
            request,
            technique,
            Status.BLOCKED,
            state,
            AttackState(),
            tuple(failed),
            decisions=tuple(decisions),
        )
    nodes = graph.nodes_by_id
    gate(
        "binding_endpoints",
        all(
            getattr(b, k) in nodes
            for k in (
                "controller",
                "principal",
                "impersonated",
                "target",
                "authentication_context",
                "service_context",
            )
        ),
    )
    gate(
        "binding_kinds",
        all(
            nodes.get(getattr(b, k), {}).get("kind") == kind
            for k, kind in (
                ("controller", "User"),
                ("principal", "User"),
                ("impersonated", "User"),
                ("target", "Computer"),
                ("authentication_context", "Computer"),
                ("service_context", "Computer"),
            )
        ),
    )
    owner = technique.id
    acquisition = owner in {"rbcd_acquire_secret", "rbcd_prepare_service"}
    target = b.principal if acquisition else b.target
    gate(
        "request_binding",
        request.actor == request.source == b.controller
        and request.target == target
        and context.authentication_context == b.authentication_context,
    )

    def runtime(name):
        subject = b.impersonated if owner == "rbcd_service_admin" else b.controller
        fact = context.facts.get((name, subject, target))
        value = None if fact is None or fact.origin == FactOrigin.UNKNOWN else fact.value
        # Scope metadata is mandatory: a true value for another service is no evidence.
        if value is True and any(
            (fact.assumption_metadata or {}).get(k) != v for k, v in asdict(b).items()
        ):
            value = None
        gate(name, value, fact.origin if fact else FactOrigin.UNKNOWN, fact)

    for name in technique.prerequisites:
        if name in RUNTIME_GATES:
            runtime(name)
        elif name == "actor_authenticated":
            usable = (b.controller, b.authentication_context) in state.usable_identity
            gate(
                name,
                True
                if usable
                else None
                if (b.controller, b.authentication_context) in state.authentication_unknown
                else False,
            )
        elif name in {"exact_reset_right", "exact_descriptor_right"}:
            # GenericAll is candidate support, never proof of effective access.
            kinds = {"GenericAll", "ForceChangePassword"} if acquisition else {"GenericAll"}
            candidate_edges = (
                graph.edges_between(b.controller, target)
                if hasattr(graph, "edges_between")
                else [
                    e
                    for e in graph["edges"]
                    if e["source"] == b.controller and e["target"] == target
                ]
            )
            edges = [
                e
                for e in candidate_edges
                if e["kind"] in kinds
                and StructuralRelationship(e["source"], e["kind"], e["target"])
                not in context.withheld_relationships
            ]
            gate(name, bool(edges), FactOrigin.OBSERVED_EVIDENCE)
            snapshot.extend(encoded(e) for e in edges)
        elif name in {"known_identity", "known_impersonated_identity"}:
            gate(
                name,
                (b.principal if name == "known_identity" else b.impersonated)
                in state.known_identity,
            )
        elif name == "target_enabled":
            value = nodes.get(target, {}).get("enabled")
            gate(name, value, FactOrigin.UNKNOWN if value is None else FactOrigin.OBSERVED_EVIDENCE)
        elif name in {"has_spn", "service_principal_names"}:
            fact = graph.snapshot_facts.lookup(b.principal, name) if graph.snapshot_facts else None
            value = (
                None
                if fact is None or fact.status == "unknown"
                else (bool(fact.value) if name == "service_principal_names" else fact.value)
            )
            gate(name, value, FactOrigin.UNKNOWN if value is None else FactOrigin.OBSERVED_EVIDENCE)
            if fact:
                snapshot.append(
                    encoded(
                        {
                            "subject": fact.subject,
                            "name": name,
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
        else:
            field = "rbcd_secret" if name == "scoped_password" else name
            found = selected(state, field, b)
            gate(name, bool(found))
            lineage.extend(p for a in found for p in a.provenance)
    provenance = tuple(
        dict.fromkeys(
            lineage
            + snapshot
            + [
                encoded(
                    {
                        "request": asdict(request),
                        "decisions": [asdict(d) for d in decisions],
                    }
                )
            ]
        )
    )
    status = Status.BLOCKED if failed else Status.INDETERMINATE if unknown else Status.APPLICABLE
    additions = AttackState()
    if status == Status.APPLICABLE:
        field = RECIPES[owner][1]
        additions = AttackState(
            **{
                field: {b.target}
                if field == "admin_control"
                else {DelegationArtifact(b, provenance)}
            }
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
        tuple(snapshot),
        provenance,
    )
