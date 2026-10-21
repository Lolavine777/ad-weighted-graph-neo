"""Initial foothold profiles, target manifests, and batch contracts for Week 5 (#268).

Owner: TTS A (@Lolavine777).
Consumer: TTS B (@nairyuuu) for batch runner, destination discovery, and UI.

Architecture Principles:
1. Strict Separation of Concerns:
   - Foothold profile defines declared initial state without fabricating credentials
     or skipping authentication gates.
   - Target manifest defines snapshot-pinned critical objectives with typed success
     predicates (distinguishing identity entitlement from host execution).
   - Batch contract specifies isolated per-source execution, structured matrix results,
     and explainable source prioritization.
2. Foothold Control != Usable Domain Identity:
   - A leaked password grants a password credential artifact, NOT a usable identity.
     It requires active activation (authentication) against KDC.
   - Computer control grants local host execution, NOT domain user identities.
   - Unsupported node kinds (Group, Domain, OU, GPO) are explicitly rejected.
3. Sound Prioritization (Anti-Probability Summation):
   - Never sum path probabilities across alternatives.
   - Never multiply alternative branches.
   - Never equate unrated with zero (safe).
   - Multi-criteria ranking: Impact -> Min-Effort -> Pareto Likelihood -> Reachability.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from fractions import Fraction
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from src.engine.search import SearchBudget
from src.engine.semantics import (
    AttackState,
    FactOrigin,
    RuntimeFact,
)
from src.engine.semantics.state import CredentialArtifact

UNSUPPORTED_FOOTHOLD_KINDS = frozenset(
    {"Group", "Domain", "OU", "OrganizationalUnit", "GPO", "Container"}
)

SUPPORTED_FOOTHOLD_KINDS = frozenset({"User", "Computer"})

IMPACT_RANKS = {
    "Catastrophic": 4,
    "High": 3,
    "Medium": 2,
    "Low": 1,
    "Unknown": 0.5,
    "None": 0,
    "unrated": -1,
}


class FootholdProfileKind(StrEnum):
    """Supported and standardized initial foothold capability profiles."""

    USER_LEAKED_PASSWORD = "user_leaked_password"
    USER_USABLE_IDENTITY = "user_usable_identity"
    COMPUTER_USABLE_IDENTITY = "computer_usable_identity"
    COMPUTER_CONTROL_ADMIN = "computer_control_admin"
    COMPUTER_CONTROL_USER = "computer_control_user"
    UNSUPPORTED = "unsupported"


class TargetGoalCategory(StrEnum):
    """Categorization of technical targets in Active Directory environments."""

    TIER_0_IDENTITY = "tier_0_identity"
    TIER_0_HOST = "tier_0_host"
    TIER_1_HOST = "tier_1_host"
    HIGH_VALUE_ASSET = "high_value_asset"
    CUSTOM = "custom"


class TargetControlLevel(StrEnum):
    """Level of control or authorization achieved over the target."""

    ADMIN_ENTITLEMENT = "admin_entitlement"
    HOST_ADMIN_EXECUTION = "host_admin_execution"
    REMOTE_COMMAND = "remote_command"
    INTERACTIVE_SESSION = "interactive_session"
    NONE = "none"


class BatchCellStatus(StrEnum):
    """Standardized result statuses for individual source-goal evaluations."""

    COMPLETE_SUCCESS = "complete_success"
    TRUNCATED_SUCCESS = "truncated_success"
    TRUNCATED_INCOMPLETE = "truncated_incomplete"
    NO_PATH = "no_path"
    BLOCKED = "blocked"
    INDETERMINATE = "indeterminate"
    CHECKPOINT_REACHED_FINAL_GOAL_BLOCKED = "checkpoint_reached_final_goal_blocked"
    CHECKPOINT_REACHED_FINAL_GOAL_INDETERMINATE = "checkpoint_reached_final_goal_indeterminate"
    CHECKPOINT_REACHED_FINAL_GOAL_NO_PATH = "checkpoint_reached_final_goal_no_path"
    CHECKPOINT_REACHED_FINAL_GOAL_TRUNCATED = "checkpoint_reached_final_goal_truncated"
    CHECKPOINT_ONLY = "checkpoint_only"
    UNSUPPORTED_SOURCE = "unsupported_source"
    UNSUPPORTED_SEMANTICS = "unsupported_semantics"
    ERROR = "error"


@dataclass(frozen=True)
class FootholdProfile:
    """Declared initial capability and foothold state for a single source principal/host."""

    profile_id: str
    kind: FootholdProfileKind
    node_id: str
    node_kind: str
    initial_actor: str
    authentication_context: str | None = None
    initial_attack_state: AttackState = field(default_factory=AttackState)
    is_supported: bool = True
    error_code: str | None = None
    unsupported_reason: str | None = None
    required_activation_technique: str | None = None
    activation_prerequisites: tuple[str, ...] = ()
    declared_assumptions: tuple[RuntimeFact, ...] = ()
    provenance_reference: str | None = None
    description: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize profile to JSON-compatible dictionary."""
        return {
            "profile_id": self.profile_id,
            "kind": self.kind.value,
            "node_id": self.node_id,
            "node_kind": self.node_kind,
            "initial_actor": self.initial_actor,
            "authentication_context": self.authentication_context,
            "is_supported": self.is_supported,
            "error_code": self.error_code,
            "unsupported_reason": self.unsupported_reason,
            "required_activation_technique": self.required_activation_technique,
            "activation_prerequisites": list(self.activation_prerequisites),
            "provenance_reference": self.provenance_reference,
            "declared_assumptions": [
                {
                    "predicate": a.predicate,
                    "subject": a.subject,
                    "target": a.target,
                    "value": a.value,
                    "origin": str(a.origin),
                    "scope": a.scope,
                    "rationale": a.rationale,
                    "provenance_reference": a.provenance_reference,
                    "assumption_metadata": dict(a.assumption_metadata or {}),
                }
                if isinstance(a, RuntimeFact)
                else a
                for a in self.declared_assumptions
            ],
            "description": self.description,
            "initial_state_summary": {
                "control": sorted(self.initial_attack_state.control),
                "admin_control": sorted(self.initial_attack_state.admin_control),
                "usable_identity": [
                    list(item) for item in sorted(self.initial_attack_state.usable_identity)
                ],
                "known_identity": sorted(self.initial_attack_state.known_identity),
                "recovered_secret_count": len(self.initial_attack_state.recovered_secret),
                "remote_command_execution": [
                    list(item)
                    for item in sorted(self.initial_attack_state.remote_command_execution)
                ],
            },
        }


def create_foothold_profile(
    *,
    node_id: str,
    node_kind: str,
    profile_type: str | FootholdProfileKind,
    authentication_context: str | None = None,
    authentication_context_kind: str | None = None,
    graph: Any = None,
    profile_id: str | None = None,
    declared_by: str = "security_analyst",
    provenance_reference: str | None = None,
    assumptions: Sequence[dict[str, Any] | RuntimeFact] = (),
    description: str | None = None,
) -> FootholdProfile:
    """Create a validated, typed FootholdProfile according to architectural standards.

    Rejects unsupported node kinds (Group, Domain, OU, GPO) without fabricating control.
    Enforces that leaked passwords start as credential artifacts requiring activation on a
    compatible Computer host context, rejecting missing or invalid contexts at input boundary.
    """
    pid = profile_id or f"profile-{node_id}-{profile_type}"
    p_kind = FootholdProfileKind(profile_type) if isinstance(profile_type, str) else profile_type

    # Normalize default authentication context based on profile kind:
    # Never default user_leaked_password to user's node_id (which is a User SID).
    if p_kind in {
        FootholdProfileKind.USER_LEAKED_PASSWORD,
        FootholdProfileKind.COMPUTER_USABLE_IDENTITY,
    }:
        auth_ctx = authentication_context
    else:
        auth_ctx = authentication_context or node_id

    # Handle unsupported or ineligible node kinds explicitly
    if node_kind in UNSUPPORTED_FOOTHOLD_KINDS or node_kind not in SUPPORTED_FOOTHOLD_KINDS:
        return FootholdProfile(
            profile_id=pid,
            kind=FootholdProfileKind.UNSUPPORTED,
            node_id=node_id,
            node_kind=node_kind,
            initial_actor=node_id,
            authentication_context=auth_ctx,
            initial_attack_state=AttackState(),
            is_supported=False,
            error_code="UNSUPPORTED_FOOTHOLD_KIND",
            unsupported_reason=(
                f"Node kind '{node_kind}' cannot serve as an initial attack foothold. "
                "Groups, Domains, and OUs are structural containers or authorization boundaries, "
                "not execution principals or compromised computing hosts. Attackers must "
                "foothold on an eligible User (identity credential) or Computer (host control)."
            ),
            description=description,
        )

    prov_ref = provenance_reference or f"foothold:{pid}"

    # Convert assumptions to RuntimeFact tuple
    norm_assumptions: list[RuntimeFact] = []
    for a in assumptions:
        if isinstance(a, RuntimeFact):
            meta = dict(a.assumption_metadata or {})
            if "declared_by" not in meta:
                meta["declared_by"] = declared_by
            p_ref = a.provenance_reference or prov_ref
            norm_assumptions.append(
                RuntimeFact(
                    predicate=a.predicate,
                    subject=a.subject,
                    target=a.target,
                    value=a.value,
                    origin=a.origin,
                    scope=a.scope,
                    rationale=a.rationale,
                    provenance_reference=p_ref,
                    assumption_metadata=meta,
                )
            )
        elif isinstance(a, Mapping):
            meta = dict(a.get("assumption_metadata") or {})
            if "declared_by" not in meta:
                meta["declared_by"] = a.get("declared_by", declared_by)
            norm_assumptions.append(
                RuntimeFact(
                    predicate=a["predicate"],
                    subject=a["subject"],
                    target=a["target"],
                    value=a.get("value", True),
                    origin=FactOrigin.DECLARED_ASSUMPTION,
                    scope=a.get("scope", "foothold_declaration"),
                    rationale=a.get("rationale", "Declared foothold precondition"),
                    provenance_reference=a.get("provenance_reference") or prov_ref,
                    assumption_metadata=meta,
                )
            )

    if p_kind == FootholdProfileKind.USER_LEAKED_PASSWORD:
        if node_kind != "User":
            raise ValueError(f"Profile {p_kind.value} requires node_kind 'User', got '{node_kind}'")

        # Context validation at the input boundary:
        # A leaked password cannot authenticate in a vacuum or against a User principal.
        # It requires an explicit, compatible Computer endpoint context.
        if auth_ctx is None or not str(auth_ctx).strip():
            return FootholdProfile(
                profile_id=pid,
                kind=p_kind,
                node_id=node_id,
                node_kind=node_kind,
                initial_actor=node_id,
                authentication_context=None,
                initial_attack_state=AttackState(known_identity=frozenset({node_id})),
                is_supported=False,
                error_code="MISSING_AUTHENTICATION_CONTEXT",
                unsupported_reason=(
                    "Profile 'user_leaked_password' requires an explicit, compatible Computer "
                    "authentication_context for credential activation "
                    "(activate_recovered_identity). Unresolved or omitted context cannot be "
                    "defaulted to a User SID."
                ),
                required_activation_technique="activate_recovered_identity",
                activation_prerequisites=(
                    "actor_enabled",
                    "secret_valid",
                    "network_kdc_reachable",
                    "authentication_accepted",
                ),
                declared_assumptions=tuple(norm_assumptions),
                provenance_reference=prov_ref,
                description=description
                or "User account with leaked/stolen password requiring authentication activation.",
            )

        is_wrong_kind = False
        target_node = None
        n_kind = None
        if auth_ctx == node_id:
            is_wrong_kind = True
        elif authentication_context_kind is not None and authentication_context_kind != "Computer":
            is_wrong_kind = True
        elif graph is not None:
            if hasattr(graph, "node") and callable(graph.node):
                try:
                    target_node = graph.node(auth_ctx)
                except KeyError, ValueError:
                    target_node = None
            elif hasattr(graph, "nodes_by_id"):
                target_node = graph.nodes_by_id.get(auth_ctx)
            elif isinstance(graph, Mapping) and "nodes" in graph:
                for n in graph["nodes"]:
                    if n.get("id") == auth_ctx:
                        target_node = n
                        break

            if target_node is not None:
                n_kind = (
                    target_node.get("kind")
                    if isinstance(target_node, Mapping)
                    else getattr(target_node, "kind", None)
                )
                if n_kind is not None and n_kind != "Computer":
                    is_wrong_kind = True
            else:
                is_wrong_kind = True

        if is_wrong_kind:
            detail = (
                f"cannot be the User principal '{auth_ctx}'"
                if auth_ctx == node_id
                else f"resolves to {n_kind} instead of Computer"
                if target_node is not None and n_kind is not None
                else f"'{auth_ctx}' was not found as a Computer host endpoint in the target graph"
                if graph is not None and target_node is None
                else f"cannot have kind '{authentication_context_kind}'"
                if authentication_context_kind is not None
                else f"'{auth_ctx}' is not a valid Computer host endpoint"
            )
            return FootholdProfile(
                profile_id=pid,
                kind=p_kind,
                node_id=node_id,
                node_kind=node_kind,
                initial_actor=node_id,
                authentication_context=auth_ctx,
                initial_attack_state=AttackState(known_identity=frozenset({node_id})),
                is_supported=False,
                error_code="INVALID_AUTHENTICATION_CONTEXT",
                unsupported_reason=(
                    f"Authentication context '{auth_ctx}' cannot be a User principal or "
                    f"non-Computer endpoint ({detail}). Credential activation "
                    "(activate_recovered_identity) requires a Computer host endpoint."
                ),
                required_activation_technique="activate_recovered_identity",
                activation_prerequisites=(
                    "actor_enabled",
                    "secret_valid",
                    "network_kdc_reachable",
                    "authentication_accepted",
                ),
                declared_assumptions=tuple(norm_assumptions),
                provenance_reference=prov_ref,
                description=description
                or "User account with leaked/stolen password requiring authentication activation.",
            )

        # Leaked password is an unverified credential artifact.
        # It does NOT grant control or usable_identity until authenticated.
        password_artifact = CredentialArtifact(
            owner=node_id,
            context=auth_ctx,
            form="password",
            provenance=(prov_ref,),
        )
        initial_state = AttackState(
            known_identity=frozenset({node_id}),
            recovered_secret=frozenset({password_artifact}),
        )
        return FootholdProfile(
            profile_id=pid,
            kind=p_kind,
            node_id=node_id,
            node_kind=node_kind,
            initial_actor=node_id,
            authentication_context=auth_ctx,
            initial_attack_state=initial_state,
            is_supported=True,
            required_activation_technique="activate_recovered_identity",
            activation_prerequisites=(
                "actor_enabled",
                "secret_valid",
                "network_kdc_reachable",
                "authentication_accepted",
            ),
            declared_assumptions=tuple(norm_assumptions),
            provenance_reference=prov_ref,
            description=description
            or "User account with leaked/stolen password requiring authentication activation.",
        )

    if p_kind == FootholdProfileKind.COMPUTER_USABLE_IDENTITY:
        if node_kind != "Computer":
            raise ValueError(f"Profile {p_kind.value} requires node_kind 'Computer'")

        def unsupported(code, reason):
            return FootholdProfile(
                profile_id=pid,
                kind=p_kind,
                node_id=node_id,
                node_kind=node_kind,
                initial_actor=node_id,
                authentication_context=auth_ctx,
                is_supported=False,
                error_code=code,
                unsupported_reason=reason,
                provenance_reference=provenance_reference,
                description=description,
            )

        if not isinstance(auth_ctx, str) or not auth_ctx.strip():
            return unsupported(
                "MISSING_AUTHENTICATION_CONTEXT",
                "Machine identity requires an explicit Computer authentication context",
            )
        if not isinstance(provenance_reference, str) or not provenance_reference.strip():
            return unsupported(
                "MISSING_IDENTITY_PROVENANCE",
                "Machine identity requires a nonblank declaration provenance reference",
            )
        if graph is None:
            return unsupported(
                "PROFILE_GRAPH_REQUIRED", "Validate machine identity against a graph"
            )

        def node(reference):
            if hasattr(graph, "node") and callable(graph.node):
                try:
                    return graph.node(reference)
                except KeyError, ValueError:
                    return None
            if isinstance(graph, Mapping):
                return next((n for n in graph.get("nodes", ()) if n.get("id") == reference), None)
            return None

        source_node, context_node = node(node_id), node(auth_ctx)
        if source_node is None or source_node.get("kind") != "Computer":
            return unsupported("INVALID_MACHINE_IDENTITY", "Source must resolve to a Computer")
        if (
            context_node is None
            or context_node.get("kind") != "Computer"
            or authentication_context_kind not in {None, "Computer"}
        ):
            return unsupported(
                "INVALID_AUTHENTICATION_CONTEXT", "Context must resolve to a Computer"
            )
        if source_node.get("is_boundary") or context_node.get("is_boundary"):
            return unsupported(
                "MACHINE_IDENTITY_SCOPE_UNSUPPORTED", "Boundary nodes are unsupported"
            )
        domains = [n.get("domain") for n in (source_node, context_node)]
        if not all(isinstance(d, str) and d.strip() for d in domains) or (
            domains[0].casefold() != domains[1].casefold()
        ):
            return unsupported(
                "MACHINE_IDENTITY_SCOPE_UNSUPPORTED",
                "Only a verified same-domain context is supported",
            )
        if source_node.get("enabled") is False:
            return unsupported("DISABLED_MACHINE_ACCOUNT", "Snapshot enabled=False identity veto")
        # An analyst-declared network identity, not evidence of a local shell,
        # SYSTEM execution, a recovered password, or another user's logon.
        return FootholdProfile(
            profile_id=pid,
            kind=p_kind,
            node_id=node_id,
            node_kind=node_kind,
            initial_actor=node_id,
            authentication_context=auth_ctx,
            initial_attack_state=AttackState(
                known_identity={node_id}, usable_identity={(node_id, auth_ctx)}
            ),
            declared_assumptions=tuple(norm_assumptions),
            provenance_reference=provenance_reference,
            description=description
            or "Declared usable machine account identity; no local host control.",
        )

    if p_kind == FootholdProfileKind.USER_USABLE_IDENTITY:
        if node_kind != "User":
            raise ValueError(f"Profile {p_kind.value} requires node_kind 'User', got '{node_kind}'")
        # Usable identity represents an active logon session or valid TGT.
        # It grants control over the user principal and usable_identity in the auth context.
        initial_state = AttackState(
            control=frozenset({node_id}),
            known_identity=frozenset({node_id}),
            usable_identity=frozenset({(node_id, auth_ctx)}),
        )
        return FootholdProfile(
            profile_id=pid,
            kind=p_kind,
            node_id=node_id,
            node_kind=node_kind,
            initial_actor=node_id,
            authentication_context=auth_ctx,
            initial_attack_state=initial_state,
            is_supported=True,
            required_activation_technique=None,
            activation_prerequisites=(),
            declared_assumptions=tuple(norm_assumptions),
            provenance_reference=prov_ref,
            description=description or "User account with verified active usable domain identity.",
        )

    if p_kind == FootholdProfileKind.COMPUTER_CONTROL_ADMIN:
        if node_kind != "Computer":
            raise ValueError(
                f"Profile {p_kind.value} requires node_kind 'Computer', got '{node_kind}'"
            )
        # Full administrative (SYSTEM/local admin) control over the host.
        # Does NOT grant domain user usable_identity.
        initial_state = AttackState(
            control=frozenset({node_id}),
            admin_control=frozenset({node_id}),
        )
        return FootholdProfile(
            profile_id=pid,
            kind=p_kind,
            node_id=node_id,
            node_kind=node_kind,
            initial_actor=node_id,
            authentication_context=auth_ctx,
            initial_attack_state=initial_state,
            is_supported=True,
            required_activation_technique=None,
            activation_prerequisites=(),
            declared_assumptions=tuple(norm_assumptions),
            provenance_reference=prov_ref,
            description=description or "Computer host with local administrative/SYSTEM control.",
        )

    if p_kind == FootholdProfileKind.COMPUTER_CONTROL_USER:
        if node_kind != "Computer":
            raise ValueError(
                f"Profile {p_kind.value} requires node_kind 'Computer', got '{node_kind}'"
            )
        # Unprivileged interactive or remote execution shell on host.
        # Does NOT grant admin_control or domain user usable_identity.
        initial_state = AttackState(
            control=frozenset({node_id}),
            remote_command_execution=frozenset({(node_id, node_id)}),
        )
        return FootholdProfile(
            profile_id=pid,
            kind=p_kind,
            node_id=node_id,
            node_kind=node_kind,
            initial_actor=node_id,
            authentication_context=auth_ctx,
            initial_attack_state=initial_state,
            is_supported=True,
            required_activation_technique=None,
            activation_prerequisites=(),
            declared_assumptions=tuple(norm_assumptions),
            provenance_reference=prov_ref,
            description=description
            or "Computer host with unprivileged command execution foothold.",
        )

    if p_kind == FootholdProfileKind.UNSUPPORTED:
        return FootholdProfile(
            profile_id=pid,
            kind=FootholdProfileKind.UNSUPPORTED,
            node_id=node_id,
            node_kind=node_kind,
            initial_actor=node_id,
            authentication_context=auth_ctx,
            initial_attack_state=AttackState(),
            is_supported=False,
            error_code="UNSUPPORTED_FOOTHOLD_KIND",
            unsupported_reason=(
                f"Source {node_id} ({node_kind}) is declared as an unsupported attack foothold."
            ),
            description=description,
        )

    raise ValueError(f"Unknown or unsupported foothold profile type: {profile_type}")


@dataclass(frozen=True)
class TargetGoal:
    """Specific technical objective within a target manifest."""

    goal_id: str
    category: TargetGoalCategory
    target_node_id: str
    target_node_kind: str
    display_name: str
    technical_consequence: str
    impact_rating: str
    required_control_level: TargetControlLevel
    required_state: dict[str, Any]
    provenance_locator: str | None = None
    checkpoint_goal: dict[str, Any] | None = None
    description: str | None = None
    goal_kind: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize target goal to JSON-compatible dictionary."""
        value = {
            "goal_id": self.goal_id,
            "category": self.category.value,
            "target_node_id": self.target_node_id,
            "target_node_kind": self.target_node_kind,
            "display_name": self.display_name,
            "technical_consequence": self.technical_consequence,
            "impact_rating": self.impact_rating,
            "required_control_level": self.required_control_level.value,
            "required_state": self.required_state,
            "provenance_locator": self.provenance_locator,
            "checkpoint_goal": self.checkpoint_goal,
            "description": self.description,
        }
        if self.goal_kind is not None:
            value["goal_kind"] = self.goal_kind
        return value

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> TargetGoal:
        return cls(
            goal_id=data["goal_id"],
            category=TargetGoalCategory(data["category"]),
            target_node_id=data["target_node_id"],
            target_node_kind=data["target_node_kind"],
            display_name=data["display_name"],
            technical_consequence=data["technical_consequence"],
            impact_rating=data["impact_rating"],
            required_control_level=TargetControlLevel(data["required_control_level"]),
            required_state=data["required_state"],
            provenance_locator=data.get("provenance_locator"),
            checkpoint_goal=data.get("checkpoint_goal"),
            description=data.get("description"),
            goal_kind=data.get("goal_kind"),
        )


@dataclass(frozen=True)
class TargetManifest:
    """Snapshot-pinned catalog of high-value goals and technical objectives."""

    manifest_id: str
    version: str
    snapshot_id: str
    domain_sid: str
    targets: tuple[TargetGoal, ...]
    default_discovery_goals: tuple[str, ...] = ()
    description: str | None = None

    def __post_init__(self) -> None:
        if isinstance(self.targets, list):
            object.__setattr__(self, "targets", tuple(self.targets))
        if isinstance(self.default_discovery_goals, list):
            object.__setattr__(self, "default_discovery_goals", tuple(self.default_discovery_goals))

    def get_goal(self, goal_id: str) -> TargetGoal | None:
        """Find target goal by goal_id."""
        for t in self.targets:
            if t.goal_id == goal_id:
                return t
        return None

    def resolve_goals(self, target_goal_ids: Sequence[str] | None = None) -> tuple[TargetGoal, ...]:
        """Resolve target goals from manifest.

        - If target_goal_ids is None or empty: returns configured default discovery goals.
          If default_discovery_goals is empty, returns all targets in the manifest.
        - If target_goal_ids is specified: validates that each requested goal_id exists
          in this manifest and returns them in the requested order.
        - Raises KeyError if any requested goal ID is not found in the manifest.
        """
        target_map = {t.goal_id: t for t in self.targets}

        if target_goal_ids is None or len(target_goal_ids) == 0:
            if not self.default_discovery_goals:
                return self.targets
            missing_defaults = [
                gid for gid in self.default_discovery_goals if gid not in target_map
            ]
            if missing_defaults:
                raise KeyError(
                    f"Default discovery goal(s) {missing_defaults} not found in "
                    f"manifest '{self.manifest_id}'"
                )
            return tuple(target_map[gid] for gid in self.default_discovery_goals)

        missing = [gid for gid in target_goal_ids if gid not in target_map]
        if missing:
            raise KeyError(
                f"Target goal ID(s) {missing} not found in manifest '{self.manifest_id}'. "
                f"Available goals: {sorted(target_map.keys())}"
            )
        return tuple(target_map[gid] for gid in target_goal_ids)

    def to_dict(self) -> dict[str, Any]:
        """Serialize target manifest to JSON-compatible dictionary."""
        return {
            "schema_version": (
                "target-manifest/1.2.0"
                if any(t.impact_rating == "Unknown" for t in self.targets)
                else "target-manifest/1.1.0"
                if any(t.goal_kind is not None for t in self.targets)
                else "target-manifest/1.0.0"
            ),
            "manifest_id": self.manifest_id,
            "version": self.version,
            "snapshot_id": self.snapshot_id,
            "domain_sid": self.domain_sid,
            "description": self.description,
            "default_discovery_goals": list(self.default_discovery_goals),
            "targets": [t.to_dict() for t in self.targets],
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> TargetManifest:
        return cls(
            manifest_id=data["manifest_id"],
            version=data["version"],
            snapshot_id=data["snapshot_id"],
            domain_sid=data["domain_sid"],
            description=data.get("description"),
            default_discovery_goals=tuple(data.get("default_discovery_goals", ())),
            targets=tuple(
                t if isinstance(t, TargetGoal) else TargetGoal.from_dict(t)
                for t in data.get("targets", ())
            ),
        )


@dataclass(frozen=True)
class BatchSourceItem:
    """Single source definition inside a batch query request."""

    source_id: str
    node_id: str
    node_kind: str
    profile_kind: str
    authentication_context: str | None = None
    declared_assumptions: tuple[dict[str, Any], ...] = ()
    custom_budget: SearchBudget | None = None
    description: str | None = None
    identity_provenance_reference: str | None = None

    def to_foothold_profile(
        self,
        authentication_context_kind: str | None = None,
        graph: Any = None,
        declared_by: str = "security_analyst",
    ) -> FootholdProfile:
        """Convert batch source definition to a typed, validated FootholdProfile."""
        return create_foothold_profile(
            node_id=self.node_id,
            node_kind=self.node_kind,
            profile_type=self.profile_kind,
            authentication_context=self.authentication_context,
            authentication_context_kind=authentication_context_kind,
            graph=graph,
            profile_id=self.source_id,
            declared_by=declared_by,
            assumptions=self.declared_assumptions,
            description=self.description,
            provenance_reference=self.identity_provenance_reference,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "node_id": self.node_id,
            "node_kind": self.node_kind,
            "profile_kind": self.profile_kind,
            "authentication_context": self.authentication_context,
            "declared_assumptions": list(self.declared_assumptions),
            "custom_budget": (
                {
                    "max_paths": self.custom_budget.max_paths,
                    "max_steps": self.custom_budget.max_steps,
                    "max_expansions": self.custom_budget.max_expansions,
                }
                if self.custom_budget is not None
                else None
            ),
            "description": self.description,
            **(
                {"identity_provenance_reference": self.identity_provenance_reference}
                if self.identity_provenance_reference is not None
                else {}
            ),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> BatchSourceItem:
        custom_b = data.get("custom_budget")
        budget = None
        if custom_b:
            from src.engine.search import SearchBudget

            budget = (
                custom_b
                if isinstance(custom_b, SearchBudget)
                else SearchBudget(
                    max_paths=custom_b.get("max_paths", 1000),
                    max_steps=custom_b.get("max_steps", 12),
                    max_expansions=custom_b.get("max_expansions", 100000),
                )
            )
        return cls(
            source_id=data["source_id"],
            node_id=data["node_id"],
            node_kind=data["node_kind"],
            profile_kind=data["profile_kind"],
            authentication_context=data.get("authentication_context"),
            declared_assumptions=tuple(data.get("declared_assumptions", ())),
            custom_budget=budget,
            description=data.get("description"),
            identity_provenance_reference=data.get("identity_provenance_reference"),
        )


def _default_budget() -> Any:
    from src.engine.search import SearchBudget

    return SearchBudget(max_paths=1000, max_steps=12, max_expansions=100000)


@dataclass(frozen=True)
class BatchQueryRequest:
    """Input specification for running a batch analysis across multiple sources."""

    batch_id: str
    snapshot_id: str
    sources: tuple[BatchSourceItem, ...]
    target_manifest: TargetManifest
    target_goal_ids: tuple[str, ...] | None = None  # None indicates default destination discovery
    common_budget: Any = field(default_factory=_default_budget)
    evaluation_mode: str = "scenario"
    prioritization_policy: str = "min_effort_impact_pareto"
    rating_resolution: dict[str, Any] | None = None
    schema_version: str = "batch-query-request/1.0.0"

    def __post_init__(self) -> None:
        if self.schema_version not in {"batch-query-request/1.0.0", "batch-query-request/1.1.0"}:
            raise ValueError("Unsupported batch request version")
        if self.schema_version == "batch-query-request/1.0.0" and any(
            s.profile_kind == "computer_usable_identity"
            or s.identity_provenance_reference is not None
            for s in self.sources
        ):
            raise ValueError("Machine identity declarations require batch-query-request/1.1.0")
        if isinstance(self.sources, list):
            object.__setattr__(self, "sources", tuple(self.sources))
        if isinstance(self.target_goal_ids, list):
            object.__setattr__(self, "target_goal_ids", tuple(self.target_goal_ids))

    def resolve_target_goals(self) -> tuple[TargetGoal, ...]:
        """Resolve target goals for this batch request using the attached manifest."""
        return self.target_manifest.resolve_goals(self.target_goal_ids)

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "schema_version": self.schema_version,
            "batch_id": self.batch_id,
            "snapshot_id": self.snapshot_id,
            "evaluation_mode": self.evaluation_mode,
            "prioritization_policy": self.prioritization_policy,
            "common_budget": {
                "max_paths": self.common_budget.max_paths,
                "max_steps": self.common_budget.max_steps,
                "max_expansions": self.common_budget.max_expansions,
            },
            "target_goal_ids": list(self.target_goal_ids)
            if self.target_goal_ids is not None
            else None,
            "target_manifest": self.target_manifest.to_dict(),
            "sources": [s.to_dict() for s in self.sources],
        }
        if self.rating_resolution is not None:
            data["rating_resolution"] = self.rating_resolution
        return data

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> BatchQueryRequest:
        from src.engine.search import SearchBudget

        budget_data = data.get("common_budget", {})
        budget = (
            budget_data
            if isinstance(budget_data, SearchBudget)
            else SearchBudget(
                max_paths=budget_data.get("max_paths", 1000),
                max_steps=budget_data.get("max_steps", 12),
                max_expansions=budget_data.get("max_expansions", 100000),
            )
        )
        manifest_data = data["target_manifest"]
        manifest = (
            manifest_data
            if isinstance(manifest_data, TargetManifest)
            else TargetManifest.from_dict(manifest_data)
        )
        sources = tuple(
            s if isinstance(s, BatchSourceItem) else BatchSourceItem.from_dict(s)
            for s in data.get("sources", ())
        )
        return cls(
            batch_id=data["batch_id"],
            snapshot_id=data["snapshot_id"],
            sources=sources,
            target_manifest=manifest,
            target_goal_ids=data.get("target_goal_ids"),
            common_budget=budget,
            evaluation_mode=data.get("evaluation_mode", "scenario"),
            prioritization_policy=data.get("prioritization_policy", "min_effort_impact_pareto"),
            rating_resolution=data.get("rating_resolution"),
            schema_version=data.get("schema_version", "batch-query-request/1.0.0"),
        )


@dataclass(frozen=True)
class SourceGoalCell:
    """Outcome of evaluating one source against one target goal."""

    status: BatchCellStatus
    control_level_attained: TargetControlLevel
    min_effort: float | None = None
    min_effort_path: dict[str, Any] | None = None
    likelihood_interval: tuple[float, float] | None = None
    likelihood_status: str = "unrated"
    impact: str | None = None
    checkpoint_reached: bool = False
    final_goal_reached: bool = False
    optimization_scope: str | None = None
    truncated: bool = False
    truncation_reason: str | None = None
    expansions: int = 0
    diagnostics: tuple[dict[str, Any], ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "control_level_attained": self.control_level_attained.value,
            "min_effort": self.min_effort,
            "min_effort_path": self.min_effort_path,
            "likelihood_interval": list(self.likelihood_interval)
            if self.likelihood_interval is not None
            else None,
            "likelihood_status": self.likelihood_status,
            "impact": self.impact,
            "checkpoint_reached": self.checkpoint_reached,
            "final_goal_reached": self.final_goal_reached,
            "optimization_scope": self.optimization_scope,
            "truncated": self.truncated,
            "truncation_reason": self.truncation_reason,
            "expansions": self.expansions,
            "diagnostics": list(self.diagnostics),
        }


def _get_field(obj: Any, key: str, default: Any = None) -> Any:
    """Safely extract field from Mapping or object attribute."""
    if obj is None:
        return default
    if isinstance(obj, Mapping):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _parse_probability_interval(interval: Any) -> tuple[float, float] | None:
    """Parse a probability interval into float bounds, supporting Fraction strings like '3/4'."""
    if not isinstance(interval, (list, tuple)) or len(interval) != 2:
        return None
    try:
        lower = float(Fraction(str(interval[0])))
        upper = float(Fraction(str(interval[1])))
        if 0.0 <= lower <= 1.0 and 0.0 <= upper <= 1.0 and lower <= upper:
            return (lower, upper)
        return None
    except ValueError, TypeError, ZeroDivisionError:
        return None


def map_query_result_to_cell(
    result: Any,
    goal: TargetGoal,
) -> SourceGoalCell:
    """Normative mapping from public AttackQueryResult to SourceGoalCell.

    Preserves checkpoint reached vs final goal reached semantics, ensures that
    blocked/indeterminate/truncated/checkpoint-only intermediate states are cleanly
    distinguished, and preserves authoritative public rating baselines without
    fabricating synthetic effort from hop count or inventing likelihood values.
    """
    chk_reached = bool(getattr(result, "checkpoint_reached", False))
    final_reached = bool(getattr(result, "final_goal_reached", False))
    truncated = bool(getattr(result, "truncated", False))
    truncation_reason = getattr(result, "truncation_reason", None)
    optimization_scope = getattr(result, "optimization_scope", None)
    expansions = getattr(result, "expansions", 0)
    diagnostics = tuple(getattr(result, "diagnostics", ()))

    if final_reached:
        status = (
            BatchCellStatus.TRUNCATED_SUCCESS if truncated else BatchCellStatus.COMPLETE_SUCCESS
        )
        control_level = goal.required_control_level
        impact = goal.impact_rating

        # Resolve public ranking baseline and candidate assessment
        baseline = getattr(result, "min_effort_baseline", None) or getattr(
            result, "min_effort", None
        )
        if baseline is None and hasattr(result, "ranking_result") and result.ranking_result:
            baseline = result.ranking_result.get(
                "min_effort_to_da_baseline"
            ) or result.ranking_result.get("min_effort_baseline")

        best_cand_id = _get_field(baseline, "best_candidate_id")

        cand_assessment: dict[str, Any] | None = None
        if hasattr(result, "ranking_result") and result.ranking_result and best_cand_id:
            eligible = result.ranking_result.get("eligible_candidates", {})
            if best_cand_id in eligible:
                cand_assessment = eligible[best_cand_id]
            else:
                diag = result.ranking_result.get("diagnostics", {}).get(best_cand_id, {})
                cand_assessment = diag.get("assessment") or diag

        # Extract authoritative min effort value (never fall back to path length or step count)
        min_effort_val: float | None = None
        baseline_effort = _get_field(baseline, "minimum_effort_value")
        if baseline_effort is not None:
            min_effort_val = float(baseline_effort)
        elif (
            cand_assessment
            and _get_field(cand_assessment, "effort_status") == "rated"
            and _get_field(cand_assessment, "effort") is not None
        ):
            min_effort_val = float(_get_field(cand_assessment, "effort"))
        elif getattr(result, "best_path", None) is not None and result.best_path.cost is not None:
            min_effort_val = float(result.best_path.cost)

        # Extract witness path and steps (separate witness from effort rating)
        witness_path = getattr(result, "best_path", None)
        if witness_path is None and getattr(result, "paths", None) and len(result.paths) > 0:
            witness_path = result.paths[0]

        min_effort_path_dict: dict[str, Any] | None = None
        if witness_path is not None:
            steps: list[str] = []
            for step in getattr(witness_path, "transition_history", ()):
                if (
                    hasattr(step, "result")
                    and hasattr(step.result, "request")
                    and hasattr(step.result.request, "technique_id")
                ):
                    steps.append(step.result.request.technique_id)
                elif hasattr(step, "technique_id"):
                    steps.append(step.technique_id)
                elif isinstance(step, Mapping) and "technique_id" in step:
                    steps.append(step["technique_id"])
                elif isinstance(step, str):
                    steps.append(step)
            min_effort_path_dict = {
                "cost": min_effort_val,
                "steps": steps,
            }

        # Likelihood extraction from exact selected baseline / candidate assessment
        p_interval: tuple[float, float] | None = None
        p_status = "unrated"
        raw_p = None
        baseline_p = _get_field(baseline, "associated_likelihood_interval")
        if baseline_p is not None:
            raw_p = baseline_p
        elif (
            cand_assessment
            and _get_field(cand_assessment, "likelihood_status") != "unrated"
            and _get_field(cand_assessment, "likelihood_interval") is not None
        ):
            raw_p = _get_field(cand_assessment, "likelihood_interval")
        elif (
            getattr(result, "best_path", None) is not None
            and getattr(result.best_path, "likelihood", None) is not None
        ):
            raw_p = result.best_path.likelihood

        if raw_p is not None:
            p_interval = _parse_probability_interval(raw_p)
            if p_interval is not None:
                p_status = "rated"

        return SourceGoalCell(
            status=status,
            control_level_attained=control_level,
            min_effort=min_effort_val,
            min_effort_path=min_effort_path_dict,
            likelihood_interval=p_interval,
            likelihood_status=p_status,
            impact=impact,
            checkpoint_reached=chk_reached,
            final_goal_reached=True,
            optimization_scope=optimization_scope,
            truncated=truncated,
            truncation_reason=truncation_reason,
            expansions=expansions,
            diagnostics=diagnostics,
        )

    # Final goal NOT reached
    res_status = getattr(result, "status", "no_path")
    if res_status == "unsupported":
        cell_status = BatchCellStatus.UNSUPPORTED_SEMANTICS
    elif res_status in ("checkpoint_only", "checkpoint_reached"):
        chk_reached = True
        cell_status = BatchCellStatus.CHECKPOINT_ONLY
    elif chk_reached:
        if truncated or res_status in ("checkpoint_reached_final_goal_truncated", "truncated"):
            cell_status = BatchCellStatus.CHECKPOINT_REACHED_FINAL_GOAL_TRUNCATED
        elif res_status in ("checkpoint_reached_final_goal_blocked", "blocked"):
            cell_status = BatchCellStatus.CHECKPOINT_REACHED_FINAL_GOAL_BLOCKED
        elif res_status in ("checkpoint_reached_final_goal_indeterminate", "indeterminate"):
            cell_status = BatchCellStatus.CHECKPOINT_REACHED_FINAL_GOAL_INDETERMINATE
        elif res_status in ("checkpoint_reached_final_goal_no_path", "no_path"):
            cell_status = BatchCellStatus.CHECKPOINT_REACHED_FINAL_GOAL_NO_PATH
        elif res_status in ("error", "execution_error"):
            cell_status = BatchCellStatus.ERROR
        else:
            cell_status = BatchCellStatus.CHECKPOINT_REACHED_FINAL_GOAL_BLOCKED
    else:
        if truncated or res_status == "truncated":
            cell_status = BatchCellStatus.TRUNCATED_INCOMPLETE
        elif res_status == "indeterminate":
            cell_status = BatchCellStatus.INDETERMINATE
        elif res_status == "blocked":
            cell_status = BatchCellStatus.BLOCKED
        elif res_status in ("error", "execution_error"):
            cell_status = BatchCellStatus.ERROR
        else:
            cell_status = BatchCellStatus.NO_PATH

    return SourceGoalCell(
        status=cell_status,
        control_level_attained=TargetControlLevel.NONE,
        min_effort=None,
        min_effort_path=None,
        likelihood_interval=None,
        likelihood_status="unrated",
        impact=None,
        checkpoint_reached=chk_reached,
        final_goal_reached=False,
        optimization_scope=optimization_scope,
        truncated=truncated,
        truncation_reason=truncation_reason,
        expansions=expansions,
        diagnostics=diagnostics,
    )


def _canonicalize_value(val: Any) -> Any:
    if isinstance(val, Mapping):
        return {k: _canonicalize_value(v) for k, v in sorted(val.items())}
    if isinstance(val, (set, frozenset)):
        return sorted(_canonicalize_value(v) for v in val)
    if isinstance(val, (list, tuple)):
        return [_canonicalize_value(v) for v in val]
    return val


def _canonical_diagnostic_key(d: Any) -> str:
    """Canonicalize a diagnostic mapping or value for deterministic sorting and deduplication."""
    if isinstance(d, Mapping):
        clean_d = _canonicalize_value(dict(d))
        return json.dumps(clean_d, sort_keys=True, separators=(",", ":"), default=str)
    return str(d)


@dataclass(frozen=True)
class SourcePrioritizationEntry:
    """Prioritization leaderboard entry ranking a compromised source by threat severity."""

    rank: int
    source_id: str
    node_id: str
    node_kind: str
    profile_kind: str
    highest_impact_reached: str
    min_effort_to_highest_impact: float | None
    likelihood_to_highest_impact: tuple[float, float] | None
    reachable_goals_count: int
    reachable_tier_0_goals: tuple[str, ...]
    priority_class: str
    explainability: str
    disposition: str = "complete"
    diagnostics: tuple[dict[str, Any], ...] = ()

    def __post_init__(self) -> None:
        if isinstance(self.reachable_tier_0_goals, list):
            object.__setattr__(self, "reachable_tier_0_goals", tuple(self.reachable_tier_0_goals))
        if isinstance(self.diagnostics, (list, tuple)):
            seen: dict[str, dict[str, Any]] = {}
            for d in self.diagnostics:
                if isinstance(d, Mapping):
                    d_dict = dict(d)
                    k = _canonical_diagnostic_key(d_dict)
                    if k not in seen:
                        seen[k] = d_dict
                else:
                    k = str(d)
                    if k not in seen:
                        seen[k] = {"message": str(d)}
            canonical = tuple(seen[k] for k in sorted(seen.keys()))
            object.__setattr__(self, "diagnostics", canonical)

    def to_dict(self) -> dict[str, Any]:
        return {
            "rank": self.rank,
            "source_id": self.source_id,
            "node_id": self.node_id,
            "node_kind": self.node_kind,
            "profile_kind": self.profile_kind,
            "highest_impact_reached": self.highest_impact_reached,
            "min_effort_to_highest_impact": self.min_effort_to_highest_impact,
            "likelihood_to_highest_impact": (
                list(self.likelihood_to_highest_impact)
                if self.likelihood_to_highest_impact is not None
                else None
            ),
            "reachable_goals_count": self.reachable_goals_count,
            "reachable_tier_0_goals": list(self.reachable_tier_0_goals),
            "priority_class": self.priority_class,
            "explainability": self.explainability,
            "disposition": self.disposition,
            "diagnostics": list(self.diagnostics),
        }


@dataclass(frozen=True)
class BatchQueryResult:
    """Standardized batch query result containing matrix and prioritization."""

    batch_id: str
    snapshot_id: str
    reproducibility: dict[str, Any]
    summary: dict[str, Any]
    source_goal_matrix: dict[str, dict[str, SourceGoalCell]]
    source_prioritization: tuple[SourcePrioritizationEntry, ...]
    tie_breaking_applied: tuple[dict[str, Any], ...]
    schema_version: str = "batch-query-result/1.0.0"

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "batch_id": self.batch_id,
            "snapshot_id": self.snapshot_id,
            "reproducibility": self.reproducibility,
            "summary": self.summary,
            "source_goal_matrix": {
                sid: {gid: cell.to_dict() for gid, cell in goals.items()}
                for sid, goals in self.source_goal_matrix.items()
            },
            "source_prioritization": [entry.to_dict() for entry in self.source_prioritization],
            "tie_breaking_applied": list(self.tie_breaking_applied),
        }


def _goal_ranking_key(
    goal_id: str,
    cell: SourceGoalCell,
    impact: str,
) -> tuple[Any, ...]:
    """Deterministic ranking key for comparing reachable candidate goals for a single source.

    Orders candidate goals identically to the source prioritization criteria:
    1. Highest impact (-impact_rank)
    2. Lowest effort (min_effort)
    3. Rated tier before unrated tier (-likelihood_tier: 1 for rated, 0 for unrated)
    4. Highest calibrated lower bound (-p_lower)
    5. Fewest path steps (steps)
    6. Alphabetical goal_id tie-breaker
    """
    impact_rank = IMPACT_RANKS.get(impact, 0)
    effort = cell.min_effort if cell.min_effort is not None else 999999.0
    is_rated = cell.likelihood_interval is not None
    likelihood_tier = 1 if is_rated else 0
    p_lower = cell.likelihood_interval[0] if is_rated else 0.0
    steps = len(cell.min_effort_path.get("steps", [])) if cell.min_effort_path else 999999
    return (
        -impact_rank,
        effort,
        -likelihood_tier,
        -p_lower,
        steps,
        goal_id,
    )


def prioritize_sources(
    matrix: Mapping[str, Mapping[str, SourceGoalCell | dict[str, Any]]],
    manifest: TargetManifest,
    sources: Sequence[BatchSourceItem]
    | Mapping[str, BatchSourceItem | FootholdProfile | dict[str, Any]]
    | None = None,
) -> tuple[tuple[SourcePrioritizationEntry, ...], tuple[dict[str, Any], ...]]:
    """Rank sources by threat severity using explainable multi-criteria policy.

    Ranking Criteria:
    1. Maximum Target Impact (Catastrophic > High > Medium > Low > Unknown > None).
    2. Minimum Effort (C_min) to achieve that highest impact (lower effort is more urgent).
    3. Blast Radius (count of reachable Tier-0 goals, then total reachable goals).
    4. Conditional Likelihood (P) when rated; unrated placed in explicit unrated tier (never 0.50).
    5. Fewest path steps.
    6. Deterministic tie-breaker: lexicographical source_id.

    Prohibitions:
    - Never sum path probabilities.
    - Never multiply alternative branches.
    - Never assign synthetic scalar (e.g. 0.50) to unrated likelihood.
    - Never treat error, timeout, or indeterminate search as proven no-path.
    """
    entries: list[dict[str, Any]] = []
    tie_records: list[dict[str, Any]] = []

    # Build source metadata lookup if sources are provided
    source_lookup: dict[str, dict[str, Any]] = {}
    if sources is not None:
        if isinstance(sources, Mapping):
            for sid, s_obj in sources.items():
                if isinstance(s_obj, BatchSourceItem):
                    source_lookup[sid] = {
                        "node_id": s_obj.node_id,
                        "node_kind": s_obj.node_kind,
                        "profile_kind": s_obj.profile_kind,
                    }
                elif isinstance(s_obj, FootholdProfile):
                    source_lookup[sid] = {
                        "node_id": s_obj.node_id,
                        "node_kind": s_obj.node_kind,
                        "profile_kind": s_obj.kind.value,
                    }
                elif isinstance(s_obj, Mapping):
                    source_lookup[sid] = {
                        "node_id": s_obj.get("node_id", sid),
                        "node_kind": s_obj.get("node_kind", "Unknown"),
                        "profile_kind": s_obj.get("profile_kind", "Unknown"),
                    }
        else:
            for s_obj in sources:
                if isinstance(s_obj, BatchSourceItem):
                    source_lookup[s_obj.source_id] = {
                        "node_id": s_obj.node_id,
                        "node_kind": s_obj.node_kind,
                        "profile_kind": s_obj.profile_kind,
                    }
                elif isinstance(s_obj, FootholdProfile):
                    source_lookup[s_obj.profile_id] = {
                        "node_id": s_obj.node_id,
                        "node_kind": s_obj.node_kind,
                        "profile_kind": s_obj.kind.value,
                    }
                elif isinstance(s_obj, Mapping):
                    sid = s_obj.get("source_id") or s_obj.get("profile_id") or s_obj.get("node_id")
                    if sid:
                        source_lookup[sid] = {
                            "node_id": s_obj.get("node_id", sid),
                            "node_kind": s_obj.get("node_kind", "Unknown"),
                            "profile_kind": s_obj.get("profile_kind", "Unknown"),
                        }

    for source_id, goal_map in matrix.items():
        highest_impact = "None"
        best_effort_for_highest: float | None = None
        best_p_for_highest: tuple[float, float] | None = None
        best_steps_for_highest: int = 999999
        reachable_goals: list[str] = []
        reachable_tier_0: list[str] = []
        cells_list: list[SourceGoalCell] = []
        seen_diags: dict[str, dict[str, Any]] = {}
        candidate_goals: list[tuple[tuple[Any, ...], str, SourceGoalCell, str, int]] = []

        # Resolve node and profile metadata
        if source_id in source_lookup:
            node_id = source_lookup[source_id]["node_id"]
            node_kind = source_lookup[source_id]["node_kind"]
            profile_kind = source_lookup[source_id]["profile_kind"]
        else:
            node_id = source_id
            node_kind = "Unknown"
            profile_kind = "Unknown"
            for raw_cell in goal_map.values():
                diags = (
                    raw_cell.diagnostics
                    if isinstance(raw_cell, SourceGoalCell)
                    else raw_cell.get("diagnostics", ())
                )
                for d in diags:
                    if isinstance(d, Mapping):
                        if "node_id" in d and node_id == source_id:
                            node_id = d["node_id"]
                        if "node_kind" in d and node_kind == "Unknown":
                            node_kind = d["node_kind"]
                        if "profile_kind" in d and profile_kind == "Unknown":
                            profile_kind = d["profile_kind"]

        for goal_id in sorted(goal_map.keys()):
            raw_cell = goal_map[goal_id]
            cell = (
                raw_cell
                if isinstance(raw_cell, SourceGoalCell)
                else SourceGoalCell(
                    status=BatchCellStatus(raw_cell.get("status", "error")),
                    control_level_attained=TargetControlLevel(
                        raw_cell.get("control_level_attained", "none")
                    ),
                    min_effort=raw_cell.get("min_effort"),
                    min_effort_path=raw_cell.get("min_effort_path"),
                    likelihood_interval=(
                        tuple(raw_cell["likelihood_interval"])
                        if raw_cell.get("likelihood_interval")
                        else None
                    ),
                    likelihood_status=raw_cell.get("likelihood_status", "unrated"),
                    impact=raw_cell.get("impact"),
                    checkpoint_reached=raw_cell.get("checkpoint_reached", False),
                    final_goal_reached=raw_cell.get("final_goal_reached", False),
                    optimization_scope=raw_cell.get("optimization_scope"),
                    truncated=raw_cell.get("truncated", False),
                    truncation_reason=raw_cell.get("truncation_reason"),
                    expansions=raw_cell.get("expansions", 0),
                    diagnostics=tuple(raw_cell.get("diagnostics", ())),
                )
            )
            cells_list.append(cell)

            for d in cell.diagnostics:
                if isinstance(d, Mapping):
                    d_dict = dict(d)
                    k = _canonical_diagnostic_key(d_dict)
                    if k not in seen_diags:
                        seen_diags[k] = d_dict
                else:
                    k = str(d)
                    if k not in seen_diags:
                        seen_diags[k] = {"message": str(d)}

            # Check if this cell is successful
            is_success = cell.status in (
                BatchCellStatus.COMPLETE_SUCCESS,
                BatchCellStatus.TRUNCATED_SUCCESS,
            )

            if is_success:
                reachable_goals.append(goal_id)
                goal_def = manifest.get_goal(goal_id)
                impact = goal_def.impact_rating if goal_def else (cell.impact or "Low")
                if goal_def and goal_def.category in (
                    TargetGoalCategory.TIER_0_IDENTITY,
                    TargetGoalCategory.TIER_0_HOST,
                ):
                    reachable_tier_0.append(goal_id)

                steps = (
                    len(cell.min_effort_path.get("steps", [])) if cell.min_effort_path else 999999
                )
                rank_key = _goal_ranking_key(goal_id, cell, impact)
                candidate_goals.append((rank_key, goal_id, cell, impact, steps))

        source_diags = [seen_diags[k] for k in sorted(seen_diags.keys())]

        # Determine source disposition, impact, priority class, and explainability
        if candidate_goals:
            candidate_goals.sort(key=lambda x: x[0])
            _, best_gid, best_cell, highest_impact, best_steps_for_highest = candidate_goals[0]
            best_effort_for_highest = best_cell.min_effort
            best_p_for_highest = best_cell.likelihood_interval

            disposition = "complete"
            if (
                highest_impact == "Catastrophic"
                and best_effort_for_highest is not None
                and best_effort_for_highest <= 3
            ):
                p_class = "Critical"
            elif highest_impact in ("Catastrophic", "High"):
                p_class = "High"
            elif highest_impact == "Medium":
                p_class = "Elevated"
            elif highest_impact == "Low":
                p_class = "Low"
            else:
                p_class = "Unknown"

            sorted_tier_0 = sorted(reachable_tier_0)
            if p_class == "Critical":
                explain = (
                    f"Source {source_id} can attain {highest_impact} compromise "
                    f"with minimal effort (C={best_effort_for_highest}) "
                    f"reaching Tier-0 goals: {sorted_tier_0}."
                )
            else:
                effort_str = (
                    f"minimum effort C={best_effort_for_highest}"
                    if best_effort_for_highest is not None
                    else "unrated effort"
                )
                p_str = (
                    f", conditional likelihood {list(best_p_for_highest)}"
                    if best_p_for_highest
                    else " (unrated likelihood)"
                )
                explain = (
                    f"Source {source_id} attains {highest_impact} impact with {effort_str}{p_str}, "
                    f"reaching {len(reachable_goals)} configured target(s)."
                )
            if any(c.status == BatchCellStatus.UNSUPPORTED_SEMANTICS for c in cells_list):
                disposition = "unsupported_semantics"
                explain += (
                    " Other configured goals have unsupported semantic continuations; "
                    "confirmed witnesses remain valid, but row coverage is incomplete."
                )
        else:
            # Distinguish incomplete/error/indeterminate/unsupported/checkpoint-only/not-evaluated
            # from proven no-path
            has_error = any(c.status == BatchCellStatus.ERROR for c in cells_list)
            has_semantic_gap = any(
                c.status == BatchCellStatus.UNSUPPORTED_SEMANTICS for c in cells_list
            )
            has_indeterminate = any(
                c.status
                in (
                    BatchCellStatus.INDETERMINATE,
                    BatchCellStatus.CHECKPOINT_REACHED_FINAL_GOAL_INDETERMINATE,
                )
                for c in cells_list
            )
            has_truncated = any(
                c.status
                in (
                    BatchCellStatus.TRUNCATED_INCOMPLETE,
                    BatchCellStatus.CHECKPOINT_REACHED_FINAL_GOAL_TRUNCATED,
                )
                or (c.truncated and not c.final_goal_reached)
                for c in cells_list
            )
            has_checkpoint_only = any(
                c.status == BatchCellStatus.CHECKPOINT_ONLY for c in cells_list
            )
            all_unsupported = len(cells_list) > 0 and all(
                c.status == BatchCellStatus.UNSUPPORTED_SOURCE for c in cells_list
            )
            all_negative_proven = len(cells_list) > 0 and all(
                c.status
                in (
                    BatchCellStatus.NO_PATH,
                    BatchCellStatus.BLOCKED,
                    BatchCellStatus.CHECKPOINT_REACHED_FINAL_GOAL_NO_PATH,
                    BatchCellStatus.CHECKPOINT_REACHED_FINAL_GOAL_BLOCKED,
                )
                for c in cells_list
            )

            if len(cells_list) == 0:
                disposition = "not_evaluated"
                highest_impact = "Unknown"
                p_class = "Unknown"
                explain = f"Source {source_id} has not been evaluated against any target goals."
            elif all_unsupported:
                disposition = "unsupported"
                highest_impact = "None"
                p_class = "None"
                unsupported_code = "UNSUPPORTED_FOOTHOLD_KIND"
                for d in source_diags:
                    if isinstance(d, Mapping):
                        if "error_code" in d:
                            unsupported_code = d["error_code"]
                            break
                        if "code" in d:
                            unsupported_code = d["code"]
                            break
                explain = (
                    f"Source {source_id} ({node_kind}) is unsupported as an attack foothold "
                    f"({unsupported_code})."
                )
            elif has_error:
                disposition = "error"
                highest_impact = "Unknown"
                p_class = "Unknown"
                explain = (
                    f"Source {source_id} evaluation encountered an error; "
                    "risk cannot be determined as no-path."
                )
            elif has_indeterminate:
                disposition = "indeterminate"
                highest_impact = "Unknown"
                p_class = "Unknown"
                explain = (
                    f"Source {source_id} search was indeterminate due to unverified runtime facts; "
                    "potential risk cannot be ruled out as no-path."
                )
            elif has_truncated:
                disposition = "truncated_incomplete"
                highest_impact = "Unknown"
                p_class = "Unknown"
                explain = (
                    f"Source {source_id} search was truncated by search budget caps; "
                    "absence of path is not proven."
                )
            elif has_semantic_gap:
                disposition = "unsupported_semantics"
                highest_impact = "Unknown"
                p_class = "Unknown"
                explain = (
                    f"Source {source_id} reached material with an unsupported semantic "
                    "continuation; absence of a route to the goals is not proven."
                )
            elif has_checkpoint_only:
                disposition = "checkpoint_only"
                highest_impact = "Unknown"
                p_class = "Unknown"
                explain = (
                    f"Source {source_id} reached an intermediate checkpoint but final target path "
                    "was not evaluated; absence of path is not proven."
                )
            elif all_negative_proven:
                disposition = "proven_no_path"
                highest_impact = "None"
                p_class = "None"
                explain = (
                    f"Source {source_id} has proven no viable attack path to any "
                    "configured targets within search budget."
                )
            else:
                disposition = "not_evaluated"
                highest_impact = "Unknown"
                p_class = "Unknown"
                explain = (
                    f"Source {source_id} evaluation was inconclusive; "
                    "absence of path is not proven."
                )

        is_rated = bool(reachable_goals and best_p_for_highest is not None)
        likelihood_tier = 1 if is_rated else 0
        p_lower = best_p_for_highest[0] if is_rated else 0.0

        entries.append(
            {
                "source_id": source_id,
                "node_id": node_id,
                "node_kind": node_kind,
                "profile_kind": profile_kind,
                "highest_impact": highest_impact,
                "impact_rank": IMPACT_RANKS.get(highest_impact, 0),
                "min_effort": best_effort_for_highest
                if best_effort_for_highest is not None
                else 999999.0,
                "actual_effort": best_effort_for_highest,
                "likelihood_tier": likelihood_tier,
                "p_lower": p_lower,
                "likelihood_interval": best_p_for_highest,
                "tier_0_count": len(reachable_tier_0),
                "steps": best_steps_for_highest,
                "reachable_count": len(reachable_goals),
                "reachable_tier_0": tuple(sorted(reachable_tier_0)),
                "priority_class": p_class,
                "explainability": explain,
                "disposition": disposition,
                "diagnostics": tuple(source_diags),
            }
        )

    # Multi-stage lexicographical ranking:
    # 1. -impact_rank (higher impact first; Unknown=0.5 ranks above None=0)
    # 2. min_effort (lower effort first)
    # 3. -tier_0_count (more Tier-0 targets first)
    # 4. -reachable_count (more total targets reached first)
    # 5. -likelihood_tier (rated representatives tier 1, unrated tier 0; no synthetic scalars)
    # 6. -p_lower (higher probability lower bound first among rated representatives)
    # 7. steps (fewer steps first)
    # 8. source_id (lexicographical stable tie-break)
    def sort_key(item: dict[str, Any]) -> tuple[Any, ...]:
        return (
            -item["impact_rank"],
            item["min_effort"],
            -item["tier_0_count"],
            -item["reachable_count"],
            -item["likelihood_tier"],
            -item["p_lower"],
            item["steps"],
            item["source_id"],
        )

    sorted_entries = sorted(entries, key=sort_key)

    # Identify ties for audit
    for i in range(len(sorted_entries) - 1):
        cur = sorted_entries[i]
        nxt = sorted_entries[i + 1]
        if (
            cur["impact_rank"] == nxt["impact_rank"]
            and cur["min_effort"] == nxt["min_effort"]
            and cur["tier_0_count"] == nxt["tier_0_count"]
            and cur["reachable_count"] == nxt["reachable_count"]
            and cur["likelihood_tier"] == nxt["likelihood_tier"]
            and cur["p_lower"] == nxt["p_lower"]
        ):
            tie_records.append(
                {
                    "source_a": cur["source_id"],
                    "source_b": nxt["source_id"],
                    "matched_criteria": {
                        "impact": cur["highest_impact"],
                        "min_effort": cur["actual_effort"],
                        "likelihood": (
                            list(cur["likelihood_interval"])
                            if cur["likelihood_interval"] is not None
                            else "unrated"
                        ),
                    },
                    "tie_breaker_applied": (
                        "steps" if cur["steps"] != nxt["steps"] else "source_id"
                    ),
                    "selected_first": cur["source_id"],
                }
            )

    prioritized_list: list[SourcePrioritizationEntry] = []
    for rank, e in enumerate(sorted_entries, start=1):
        prioritized_list.append(
            SourcePrioritizationEntry(
                rank=rank,
                source_id=e["source_id"],
                node_id=e["node_id"],
                node_kind=e["node_kind"],
                profile_kind=e["profile_kind"],
                highest_impact_reached=e["highest_impact"],
                min_effort_to_highest_impact=e["actual_effort"],
                likelihood_to_highest_impact=e["likelihood_interval"],
                reachable_goals_count=e["reachable_count"],
                reachable_tier_0_goals=e["reachable_tier_0"],
                priority_class=e["priority_class"],
                explainability=e["explainability"],
                disposition=e["disposition"],
                diagnostics=e["diagnostics"],
            )
        )

    return tuple(prioritized_list), tuple(tie_records)
