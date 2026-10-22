"""Deterministic planning, not execution or proof of an observed attack."""

from collections.abc import Mapping, Sequence
from copy import deepcopy
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any

from src.parser.snapshot_facts import SnapshotFacts

from .catalog import load_catalog
from .models import (
    CapabilityRelationship,
    FactOrigin,
    PrerequisiteDecision,
    StructuralRelationship,
    Technique,
)
from .state import AttackState, RuntimeContext
from .transitions import (
    Status,
    TransitionRequest,
    TransitionResult,
    apply_transition,
    effects_for,
)


class PreparedSemanticGraph(Mapping):
    """Isolated read view with indices constructed only from canonical records."""

    def __init__(
        self,
        graph: Mapping,
        *,
        snapshot_facts: SnapshotFacts | None = None,
        _skip_binding_validation: bool = False,
        _defensive_copy: bool = True,
    ):
        self._data = deepcopy(dict(graph)) if _defensive_copy else dict(graph)
        if snapshot_facts is not None and not _skip_binding_validation:
            snapshot_facts.validate_binding(self._data)
        self._snapshot_facts = snapshot_facts
        self._nodes_by_id = MappingProxyType(
            {node["id"]: MappingProxyType(node) for node in self._data["nodes"]}
        )
        self._relationships = frozenset(
            StructuralRelationship(edge["source"], edge["kind"], edge["target"])
            for edge in self._data["edges"]
        )
        edges_by_endpoints: dict[tuple[str, str], list[dict[str, Any]]] = {}
        for edge in self._data["edges"]:
            edges_by_endpoints.setdefault((edge["source"], edge["target"]), []).append(edge)
        self._edges_by_endpoints = {
            k: tuple(sorted(v, key=lambda e: e.get("id", "")))
            for k, v in edges_by_endpoints.items()
        }

    @property
    def nodes_by_id(self):
        """Public read index cannot be replaced on the graph-owned cached view."""
        return self._nodes_by_id

    @property
    def relationships(self):
        """Structural membership index is immutable through the public interface."""
        return self._relationships

    def edges_between(self, source: str, target: str) -> tuple[dict[str, Any], ...]:
        """Return defensive copies of edges between source and target nodes."""
        records = self._edges_by_endpoints.get((source, target), ())
        return tuple(deepcopy(e) for e in records)

    @property
    def snapshot_facts(self) -> SnapshotFacts | None:
        """Static evidence available to consumers independently of runtime/state."""
        return self._snapshot_facts

    def __getitem__(self, key):
        return deepcopy(self._data[key])

    def __iter__(self):
        return iter(self._data)

    def __len__(self):
        return len(self._data)


def candidates(
    relationship: str,
    source_kind: str,
    target_kind: str,
    catalog: Sequence[Technique] | None = None,
) -> tuple[Technique, ...]:
    """Return compatible choices, never silently select a GenericAll technique."""
    return tuple(
        sorted(
            (
                t
                for t in (load_catalog() if catalog is None else catalog)
                if t.relationship == relationship
                and source_kind in t.source_kinds
                and target_kind in t.target_kinds
            ),
            key=lambda t: t.id,
        )
    )


def evaluate(
    graph: Mapping,
    state: AttackState,
    request: TransitionRequest,
    context: RuntimeContext,
    catalog: Sequence[Technique] | None = None,
) -> TransitionResult:
    """Read a contract-validated parser graph. Unknown runtime facts yield no effects.

    Snapshot validation remains the existing parser/contract boundary. Derived
    relationships stay in state and can be explicitly selected in later requests.
    """
    catalog = load_catalog() if catalog is None else catalog
    technique = next((t for t in catalog if t.id == request.technique_id), None)
    if technique is None:
        raise ValueError(f"unknown technique: {request.technique_id}")
    if technique.id == "use_session_identity":
        from .session import evaluate_session

        prepared = (
            graph if isinstance(graph, PreparedSemanticGraph) else PreparedSemanticGraph(graph)
        )
        return evaluate_session(prepared, state, request, context, technique)
    from .rbcd import OWNERS as RBCD_OWNERS
    from .rbcd import evaluate_rbcd

    if technique.id in RBCD_OWNERS:
        prepared = (
            graph if isinstance(graph, PreparedSemanticGraph) else PreparedSemanticGraph(graph)
        )
        return evaluate_rbcd(prepared, state, request, context, technique)
    from .credentials import RELATIONSHIPS, evaluate_artifact

    if technique.relationship in RELATIONSHIPS:
        prepared = (
            graph if isinstance(graph, PreparedSemanticGraph) else PreparedSemanticGraph(graph)
        )
        return evaluate_artifact(prepared, state, request, context, technique)
    nodes = (
        graph.nodes_by_id
        if isinstance(graph, PreparedSemanticGraph)
        else {node["id"]: node for node in graph["nodes"]}
    )
    structural_index = graph.relationships if isinstance(graph, PreparedSemanticGraph) else None
    actor, source, target = request.actor, request.source, request.target
    failed: list[str] = []
    unknown: list[str] = []
    satisfied: list[str] = []
    decisions: list[PrerequisiteDecision] = []

    if any(node not in nodes for node in (actor, source, target)):
        failed.append("missing_endpoint")
        decisions.append(
            PrerequisiteDecision(
                "endpoints_present",
                satisfied=False,
                origin=FactOrigin.TECHNICAL_RULE,
                rationale="actor, source, or target node missing from graph",
            )
        )
    else:
        if nodes[source]["kind"] not in technique.source_kinds:
            failed.append("source_kind")
            decisions.append(
                PrerequisiteDecision(
                    "source_kind",
                    satisfied=False,
                    origin=FactOrigin.TECHNICAL_RULE,
                    rationale=(
                        f"source node kind {nodes[source]['kind']!r} not in "
                        f"{technique.source_kinds}"
                    ),
                )
            )
        if nodes[target]["kind"] not in technique.target_kinds:
            failed.append("target_kind")
            decisions.append(
                PrerequisiteDecision(
                    "target_kind",
                    satisfied=False,
                    origin=FactOrigin.TECHNICAL_RULE,
                    rationale=(
                        f"target node kind {nodes[target]['kind']!r} not in "
                        f"{technique.target_kinds}"
                    ),
                )
            )
        if nodes[actor]["kind"] not in {"User", "Group", "Computer"}:
            failed.append("actor_kind")
            decisions.append(
                PrerequisiteDecision(
                    "actor_kind",
                    satisfied=False,
                    origin=FactOrigin.TECHNICAL_RULE,
                    rationale=(
                        f"actor node kind {nodes[actor]['kind']!r} not in User, Group, Computer"
                    ),
                )
            )

    if technique.relationship == "AuthenticationControl":
        relationship = CapabilityRelationship(source, technique.relationship, target)
        structural_relationship = None
        exists = source in state.reset_password_control
    else:
        if technique.relationship == "DeclaredHostAdmin":
            relationship = CapabilityRelationship(source, technique.relationship, target)
            structural_relationship = StructuralRelationship(source, "GenericAll", target)
        else:
            relationship = StructuralRelationship(source, technique.relationship, target)
            structural_relationship = relationship
        exists = (
            relationship in state.relationship_added
            or relationship in state.permission
            or (
                structural_relationship in structural_index
                if structural_index is not None
                else any(
                    (edge["source"], edge["kind"], edge["target"])
                    == (source, structural_relationship.kind, target)
                    for edge in graph["edges"]
                )
            )
        )
    if not exists and structural_relationship in context.withheld_relationships:
        unknown.append("relationship_exists")
        decisions.append(
            PrerequisiteDecision(
                "relationship_exists",
                False,
                FactOrigin.UNKNOWN,
                rationale=f"structural evidence withheld for {structural_relationship}",
            )
        )
    elif not exists:
        failed.append("relationship_missing")
        decisions.append(
            PrerequisiteDecision(
                "relationship_exists",
                satisfied=False,
                origin=FactOrigin.TECHNICAL_RULE,
                rationale=f"structural relationship {relationship} does not exist",
            )
        )

    # Host execution/control is not a declaration of the machine account's
    # network identity. Directory/remote rights need that identity in this exact
    # context; local credential access (HasSession) has its own host-admin gates.
    if nodes.get(actor, {}).get("kind") == "Computer" and (
        "source_authorized" in technique.prerequisites
    ):
        identity = (actor, context.authentication_context)
        authenticated = (
            context.authentication_context is not None and identity in state.usable_identity
        )
        uncertain = not authenticated and (
            context.authentication_context is None or identity in state.authentication_unknown
        )
        predicate = "computer_actor_authenticated"
        (satisfied if authenticated else unknown if uncertain else failed).append(predicate)
        decisions.append(
            PrerequisiteDecision(
                predicate,
                satisfied=authenticated,
                origin=FactOrigin.UNKNOWN if uncertain else FactOrigin.TECHNICAL_RULE,
                rationale=(
                    "Computer account requires declared usable_identity in the current "
                    "authentication context; local host control alone is insufficient"
                ),
            )
        )

    for predicate in technique.prerequisites:
        if predicate in {
            "actor_controlled",
            "actor_authenticated",
            "reset_password_control",
            "authentication_context_matches",
        }:
            authenticated = (actor, context.authentication_context) in state.usable_identity
            is_sat = {
                "actor_controlled": actor in state.control or authenticated,
                "actor_authenticated": authenticated,
                "reset_password_control": source == actor
                and source in state.reset_password_control,
                "authentication_context_matches": target == context.authentication_context,
            }[predicate]
            if is_sat:
                satisfied.append(predicate)
                decisions.append(
                    PrerequisiteDecision(
                        predicate,
                        satisfied=True,
                        origin=FactOrigin.TECHNICAL_RULE,
                        rationale=f"{predicate} satisfied in branch state/context for {actor}",
                    )
                )
            else:
                failed.append(predicate)
                decisions.append(
                    PrerequisiteDecision(
                        predicate,
                        satisfied=False,
                        origin=FactOrigin.TECHNICAL_RULE,
                        rationale=f"{predicate} missing in branch state/context for {actor}",
                    )
                )

        elif predicate == "source_authorized":
            is_sat = source == actor or (
                nodes.get(source, {}).get("kind") == "Group"
                and (actor, source) in state.effective_member
            )
            if is_sat:
                satisfied.append(predicate)
                decisions.append(
                    PrerequisiteDecision(
                        predicate,
                        satisfied=True,
                        origin=FactOrigin.TECHNICAL_RULE,
                        rationale="source is actor or actor is effective member of group",
                    )
                )
            else:
                failed.append(predicate)
                decisions.append(
                    PrerequisiteDecision(
                        predicate,
                        satisfied=False,
                        origin=FactOrigin.TECHNICAL_RULE,
                        rationale="source not actor and actor not effective member of group",
                    )
                )

        elif predicate == "source_admin_control":
            is_sat = source in state.admin_control
            if is_sat:
                satisfied.append(predicate)
                decisions.append(
                    PrerequisiteDecision(
                        predicate,
                        satisfied=True,
                        origin=FactOrigin.TECHNICAL_RULE,
                        rationale=f"source {source} in state.admin_control",
                    )
                )
            else:
                failed.append(predicate)
                decisions.append(
                    PrerequisiteDecision(
                        predicate,
                        satisfied=False,
                        origin=FactOrigin.TECHNICAL_RULE,
                        rationale=f"source {source} not in state.admin_control",
                    )
                )

        else:
            subject = (
                source
                if predicate
                in {
                    "session_fresh",
                    "session_present",
                    "credential_accessible",
                    "host_admin_mapping",
                }
                else actor
            )
            fact = context.facts.get((predicate, subject, target))

            # Check snapshot properties for enabled predicates
            if predicate in {"actor_enabled", "target_enabled"}:
                node = actor if predicate == "actor_enabled" else target
                snapshot_val = nodes.get(node, {}).get("enabled")
                # Known-false veto invariant: if snapshot says enabled is False,
                # an optimistic assumption or context claiming True MUST NOT overwrite it!
                if snapshot_val is False:
                    failed.append(predicate)
                    decisions.append(
                        PrerequisiteDecision(
                            predicate,
                            satisfied=False,
                            origin=FactOrigin.BLOCKED_EVIDENCE,
                            fact=fact,
                            rationale=f"node {node} enabled=False in snapshot (known-false veto)",
                        )
                    )
                    continue
                elif snapshot_val is True and fact is None:
                    satisfied.append(predicate)
                    decisions.append(
                        PrerequisiteDecision(
                            predicate,
                            satisfied=True,
                            origin=FactOrigin.OBSERVED_EVIDENCE,
                            rationale=f"node {node} enabled=True in snapshot",
                        )
                    )
                    continue

            if fact is None or fact.origin == FactOrigin.UNKNOWN:
                unknown.append(predicate)
                decisions.append(
                    PrerequisiteDecision(
                        predicate,
                        satisfied=False,
                        origin=FactOrigin.UNKNOWN,
                        fact=fact,
                        rationale=(
                            fact.rationale
                            if (fact is not None and fact.rationale)
                            else (
                                f"fact ({predicate}, {subject}, {target}) "
                                "absent or unknown in context"
                            )
                        ),
                    )
                )
            elif fact.value is False:
                failed.append(predicate)
                decisions.append(
                    PrerequisiteDecision(
                        predicate,
                        satisfied=False,
                        origin=fact.origin,
                        fact=fact,
                        rationale=fact.rationale or f"fact {predicate} is False",
                    )
                )
            elif fact.value is True:
                satisfied.append(predicate)
                decisions.append(
                    PrerequisiteDecision(
                        predicate,
                        satisfied=True,
                        origin=fact.origin,
                        fact=fact,
                        rationale=fact.rationale or f"fact {predicate} is True",
                    )
                )
            else:
                unknown.append(predicate)
                decisions.append(
                    PrerequisiteDecision(
                        predicate,
                        satisfied=False,
                        origin=FactOrigin.UNKNOWN,
                        fact=fact,
                        rationale=fact.rationale or f"fact {predicate} value is None",
                    )
                )

    status = Status.BLOCKED if failed else Status.INDETERMINATE if unknown else Status.APPLICABLE
    return TransitionResult(
        request,
        technique,
        status,
        state,
        effects_for(technique, request) if status == Status.APPLICABLE else AttackState(),
        tuple(failed),
        tuple(unknown),
        tuple(satisfied),
        tuple(decisions),
    )


@dataclass(frozen=True)
class MembershipResult:
    state: AttackState
    transitions: tuple[TransitionResult, ...]


def propagate_membership(
    graph: Mapping,
    state: AttackState,
    context: RuntimeContext,
    catalog: Sequence[Technique] | None = None,
) -> MembershipResult:
    """Finite closure over direct and explicitly derived membership relationships."""
    catalog = load_catalog() if catalog is None else catalog
    membership = next(t for t in catalog if t.relationship == "MemberOf")
    relationships = {
        StructuralRelationship(e["source"], e["kind"], e["target"])
        for e in graph["edges"]
        if e["kind"] == "MemberOf"
    } | {e for e in state.relationship_added if e.kind == "MemberOf"}
    attempted = set()
    transitions = []
    current = state
    while True:
        progressed = False
        for actor in sorted(
            current.control
            | {
                user
                for user, auth_context in current.usable_identity
                if auth_context == context.authentication_context
            }
        ):
            for edge in sorted(relationships):
                key = actor, edge
                if key in attempted or not (
                    actor == edge.source or (actor, edge.source) in current.effective_member
                ):
                    continue
                attempted.add(key)
                result = evaluate(
                    graph,
                    current,
                    TransitionRequest(membership.id, actor, edge.source, edge.target),
                    context,
                    catalog,
                )
                transitions.append(result)
                updated = apply_transition(current, result)
                progressed |= updated != current
                current = updated
        if not progressed:
            return MembershipResult(current, tuple(transitions))
