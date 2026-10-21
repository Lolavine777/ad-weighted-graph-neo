"""Immutable scenario state, scoped to one snapshot and evaluation time window."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from types import MappingProxyType

from .models import FactOrigin, RuntimeFact, StructuralRelationship
from .rbcd_types import STATE_FIELDS, DelegationArtifact, DelegationBinding


@dataclass(frozen=True, order=True)
class CredentialArtifact:
    """Prediction artifact without secret bytes; owner and context are canonical IDs."""

    owner: str
    context: str
    form: str
    provenance: tuple[str, ...]

    def __post_init__(self):
        object.__setattr__(self, "provenance", tuple(self.provenance))
        if self.form not in {"kerberos_service_ticket", "kerberos_asrep", "password"}:
            raise ValueError("unsupported artifact form")
        if not all(isinstance(v, str) and v.strip() for v in (self.owner, self.context)):
            raise ValueError("artifact owner/context required")
        if not self.provenance or any(
            not isinstance(v, str) or not v.strip() for v in self.provenance
        ):
            raise ValueError("artifact provenance required")


@dataclass(frozen=True)
class AttackState:
    rbcd_secret: frozenset[DelegationArtifact] = frozenset()
    controlled_service: frozenset[DelegationArtifact] = frozenset()
    rbcd_descriptor: frozenset[DelegationArtifact] = frozenset()
    delegated_context: frozenset[DelegationArtifact] = frozenset()
    known_identity: frozenset[str] = frozenset()
    authentication_unknown: frozenset[tuple[str, str]] = frozenset()
    asrep_request_capability: frozenset[tuple[str, str]] = frozenset()
    asrep_material: frozenset[CredentialArtifact] = frozenset()
    service_ticket_material: frozenset[CredentialArtifact] = frozenset()
    recovered_secret: frozenset[CredentialArtifact] = frozenset()
    control: frozenset[str] = frozenset()
    effective_member: frozenset[tuple[str, str]] = frozenset()
    permission: frozenset[StructuralRelationship] = frozenset()
    admin_control: frozenset[str] = frozenset()
    interactive_session: frozenset[tuple[str, str]] = frozenset()
    remote_command_execution: frozenset[tuple[str, str]] = frozenset()
    credential_material: frozenset[str] = frozenset()
    authentication_control: frozenset[str] = frozenset()
    reset_password_control: frozenset[str] = frozenset()
    usable_identity: frozenset[tuple[str, str]] = frozenset()
    relationship_added: frozenset[StructuralRelationship] = frozenset()

    def __post_init__(self):
        for name in self.__dataclass_fields__:
            object.__setattr__(self, name, frozenset(getattr(self, name)))
        for name in STATE_FIELDS:
            if any(not isinstance(a, DelegationArtifact) for a in getattr(self, name)):
                raise ValueError(f"{name} requires typed delegation artifacts")
        for name, form in (
            ("asrep_material", "kerberos_asrep"),
            ("service_ticket_material", "kerberos_service_ticket"),
            ("recovered_secret", "password"),
        ):
            if any(
                not isinstance(a, CredentialArtifact) or a.form != form for a in getattr(self, name)
            ):
                raise ValueError(f"{name} requires typed artifacts with form {form}")
        for name in ("permission", "relationship_added"):
            if any(not isinstance(rel, StructuralRelationship) for rel in getattr(self, name)):
                raise ValueError(f"{name} requires structural relationships")


@dataclass(frozen=True)
class RuntimeContext:
    """Explicit facts keyed by (predicate, subject, target); absent means unknown.

    For session_fresh, session_present and credential_accessible, subject is the
    source computer. Other external predicates use the requesting actor.
    Membership facts use the original controlled actor and each destination group.
    Callers must rebuild state/context when time or authentication context changes.

    Supports both backward-compatible bool mapping and typed RuntimeFact records.
    """

    facts: Mapping[tuple[str, str, str], RuntimeFact] = field(default_factory=dict)
    rbcd_bindings: tuple[DelegationBinding, ...] = ()
    authentication_context: str | None = None
    withheld_relationships: frozenset[StructuralRelationship] = frozenset()

    def __init__(
        self,
        facts: (
            Mapping[tuple[str, str, str], bool | RuntimeFact] | Sequence[RuntimeFact] | None
        ) = None,
        *,
        authentication_context: str | None = None,
        withheld_relationships: frozenset[StructuralRelationship] = frozenset(),
        rbcd_bindings: tuple[DelegationBinding, ...] = (),
    ) -> None:
        if authentication_context is not None and not authentication_context.strip():
            raise ValueError("authentication_context must be non-empty")
        object.__setattr__(self, "authentication_context", authentication_context)
        if any(not isinstance(b, DelegationBinding) for b in rbcd_bindings):
            raise ValueError("rbcd_bindings requires typed bindings")
        if len(set(rbcd_bindings)) != len(rbcd_bindings):
            raise ValueError("duplicate RBCD binding")
        object.__setattr__(self, "rbcd_bindings", tuple(sorted(rbcd_bindings)))
        withheld = frozenset(withheld_relationships)
        if any(not isinstance(rel, StructuralRelationship) for rel in withheld):
            raise ValueError("withheld_relationships requires structural relationships")
        object.__setattr__(self, "withheld_relationships", withheld)
        normalized: dict[tuple[str, str, str], RuntimeFact] = {}
        if facts is not None:
            if isinstance(facts, Mapping):
                for key, val in facts.items():
                    if (
                        not isinstance(key, tuple)
                        or len(key) != 3
                        or any(not isinstance(part, str) or not part.strip() for part in key)
                    ):
                        raise ValueError("runtime facts require (predicate, subject, target)")
                    p, s, t = key
                    if type(val) is bool:
                        normalized[key] = RuntimeFact(
                            predicate=p,
                            subject=s,
                            target=t,
                            value=val,
                            origin=FactOrigin.UNSPECIFIED,
                            rationale="legacy unspecified boolean fact",
                        )
                    elif isinstance(val, RuntimeFact):
                        if (val.predicate, val.subject, val.target) != key:
                            raise ValueError(
                                f"fact key {key!r} does not match RuntimeFact "
                                f"{(val.predicate, val.subject, val.target)!r}"
                            )
                        if key in normalized:
                            existing = normalized[key]
                            if existing.value != val.value:
                                raise ValueError(
                                    f"contradictory runtime facts for {key}: cannot reconcile "
                                    f"{existing.origin}={existing.value} and "
                                    f"{val.origin}={val.value}"
                                )
                        normalized[key] = val
                    else:
                        raise ValueError(
                            "runtime facts value must be a boolean or RuntimeFact, "
                            f"got {type(val)!r}"
                        )
            elif isinstance(facts, (list, tuple, set, frozenset)):
                for f in facts:
                    if not isinstance(f, RuntimeFact):
                        raise ValueError("runtime facts sequence elements must be RuntimeFact")
                    key = (f.predicate, f.subject, f.target)
                    if key in normalized:
                        existing = normalized[key]
                        if existing == f:
                            continue
                        if existing.value != f.value:
                            raise ValueError(
                                f"contradictory runtime facts for {key}: cannot reconcile "
                                f"{existing.origin}={existing.value} and {f.origin}={f.value}"
                            )
                        raise ValueError(
                            f"ambiguous duplicate runtime facts for {key}: "
                            "non-identical records are not allowed"
                        )
                    normalized[key] = f
            else:
                raise ValueError("facts must be a Mapping or Sequence of RuntimeFact")

        object.__setattr__(self, "facts", MappingProxyType(normalized))
