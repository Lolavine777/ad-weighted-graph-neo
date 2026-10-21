"""Explicit additive effects with immutable before/after state."""

from dataclasses import dataclass, replace
from enum import StrEnum

from .models import (
    Effect,
    FactOrigin,
    PrerequisiteDecision,
    RuntimeFact,
    StructuralRelationship,
    Technique,
)
from .rbcd_types import DelegationBinding
from .state import AttackState


class Status(StrEnum):
    APPLICABLE = "applicable"
    BLOCKED = "blocked"
    INDETERMINATE = "indeterminate"


@dataclass(frozen=True)
class TransitionRequest:
    technique_id: str
    actor: str
    source: str
    target: str
    rbcd_binding: DelegationBinding | None = None


@dataclass(frozen=True)
class TransitionResult:
    request: TransitionRequest
    technique: Technique
    status: Status
    before: AttackState
    additions: AttackState
    failed: tuple[str, ...] = ()
    unknown: tuple[str, ...] = ()
    satisfied: tuple[str, ...] = ()
    decisions: tuple[PrerequisiteDecision, ...] = ()
    snapshot_evidence: tuple[str, ...] = ()
    capability_provenance: tuple[str, ...] = ()

    @property
    def assumption_backed_facts(self) -> tuple[RuntimeFact, ...]:
        """Return satisfied facts that were supported by declared assumptions."""
        return tuple(
            d.fact
            for d in self.decisions
            if d.satisfied and d.fact is not None and d.origin == FactOrigin.DECLARED_ASSUMPTION
        )

    @property
    def evidence_backed_facts(self) -> tuple[RuntimeFact, ...]:
        """Return satisfied facts that were supported by observed evidence."""
        return tuple(
            d.fact
            for d in self.decisions
            if d.satisfied and d.fact is not None and d.origin == FactOrigin.OBSERVED_EVIDENCE
        )

    @property
    def is_assumption_backed(self) -> bool:
        """Return True if any satisfied prerequisite relied on a declared assumption."""
        return any(
            d.satisfied and d.origin == FactOrigin.DECLARED_ASSUMPTION for d in self.decisions
        )


def effects_for(technique: Technique, request: TransitionRequest) -> AttackState:
    actor, target = request.actor, request.target
    additions = AttackState()
    for effect in technique.effects:
        if effect in {Effect.SERVICE_TICKET_MATERIAL, Effect.RECOVERED_SECRET}:
            raise ValueError("artifact effects require context-aware semantic evaluation")
        if effect in {Effect.GRANT_GENERIC_ALL, Effect.GRANT_WRITE_DACL, Effect.ADD_MEMBERSHIP}:
            kind = {
                Effect.GRANT_GENERIC_ALL: "GenericAll",
                Effect.GRANT_WRITE_DACL: "WriteDacl",
                Effect.ADD_MEMBERSHIP: "MemberOf",
            }[effect]
            relationship = StructuralRelationship(actor, kind, target)
            additions = replace(
                additions,
                relationship_added=additions.relationship_added | {relationship},
                permission=additions.permission | ({relationship} if kind != "MemberOf" else set()),
            )
        elif effect is Effect.USABLE_IDENTITY:
            additions = replace(
                additions, usable_identity=additions.usable_identity | {(request.source, target)}
            )
        else:
            paired = effect in {
                Effect.EFFECTIVE_MEMBER,
                Effect.INTERACTIVE_SESSION,
                Effect.REMOTE_COMMAND_EXECUTION,
            }
            additions = replace(
                additions, **{effect.value: frozenset({(actor, target) if paired else target})}
            )
    return additions


def apply_transition(state: AttackState, result: TransitionResult) -> AttackState:
    """Apply only to the state evaluated; callers explicitly choose each action."""
    if result.before != state:
        raise ValueError("transition was evaluated against a different state")
    if result.status != Status.APPLICABLE:
        return state
    return AttackState(
        **{
            name: getattr(state, name) | getattr(result.additions, name)
            for name in state.__dataclass_fields__
        }
    )
