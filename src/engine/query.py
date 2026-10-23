"""Public query/scenario materialization and fact resolution for Week 4 (Issue #211).

Architecture Boundary Principles:
1. Scenario/query != AttackState != RuntimeContext != canonical graph:
   - Scenario/query: High-level declared problem definition (source foothold, target,
     assumptions, goals, budgets) provided by caller or test harness.
   - AttackState: Branch-local capabilities attained by the attacker in a specific
     search branch (control, admin_control, usable_identity, permissions, etc.).
   - RuntimeContext: Environment, network, and authentication facts (reachability,
     service availability, authentication context, withheld evidence).
   - Canonical graph: Read-only, validated directory structure and observed permissions.
     Never mutated by scenario assumptions or runtime facts.

2. Foothold control != usable domain identity:
   - A foothold on a Computer (e.g. HostA) gives control over that computer.
   - It NEVER automatically grants usable_identity(UserX) or any domain identity.
   - Domain identity capability must be explicitly supplied with appropriate evidence
     or acquired dynamically through valid technique chains (e.g., credential recovery,
     password reset with authentication control).
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from functools import cached_property
from types import MappingProxyType
from typing import Any

from src.engine.graph import EngineGraph
from src.engine.search import (
    AttackSearchResult,
    PathResult,
    SearchBudget,
    generate_attack_paths,
)
from src.engine.semantics import (
    AttackState,
    FactOrigin,
    RuntimeContext,
    RuntimeFact,
    load_catalog,
)
from src.engine.semantics.models import StructuralRelationship, Technique
from src.engine.semantics.rbcd_types import (
    ID_FIELDS,
    DelegationBinding,
    decode_artifact,
)
from src.engine.semantics.rbcd_types import (
    STATE_FIELDS as RBCD_FIELDS,
)
from src.engine.semantics.state import CredentialArtifact
from src.engine.semantics.transitions import Status, TransitionResult, apply_transition

PAIRS = frozenset(
    {
        "effective_member",
        "interactive_session",
        "remote_command_execution",
        "usable_identity",
        "authentication_unknown",
        "asrep_request_capability",
    }
)
ARTIFACTS = frozenset({"service_ticket_material", "asrep_material", "recovered_secret"})
RELATIONS = frozenset({"permission", "relationship_added"})
FIELDS = frozenset(AttackState.__dataclass_fields__)
VALID_EVALUATION_MODES = frozenset({"scenario", "evidence_only"})


@dataclass(frozen=True)
class RejectedAssumption:
    """Audit record for a declared assumption rejected during fact resolution.

    Preserves the full assumption identity, declared scope/rationale, the rejection
    reason, and the conflicting authoritative evidence/fact.
    """

    predicate: str
    subject: str
    target: str
    assumption_value: bool | None
    scope: str | None
    reason: str
    conflicting_fact: RuntimeFact | None = None
    rationale: str | None = None
    provenance_reference: str | None = None
    assumption_metadata: Mapping[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "predicate": self.predicate,
            "subject": self.subject,
            "target": self.target,
            "assumption_value": self.assumption_value,
            "scope": self.scope,
            "reason": self.reason,
            "conflicting_fact": (
                {
                    "predicate": self.conflicting_fact.predicate,
                    "subject": self.conflicting_fact.subject,
                    "target": self.conflicting_fact.target,
                    "value": self.conflicting_fact.value,
                    "origin": str(self.conflicting_fact.origin),
                    "provenance_reference": self.conflicting_fact.provenance_reference,
                }
                if self.conflicting_fact is not None
                else None
            ),
            "rationale": self.rationale,
            "provenance_reference": self.provenance_reference,
            "assumption_metadata": dict(self.assumption_metadata or {}),
        }


@dataclass(frozen=True)
class AttackQuery:
    """Declarative specification of an attack problem without pre-ordered paths."""

    target: str
    graph: Any = None
    source_foothold: str | None = None
    initial_actor: str | None = None
    initial_state: AttackState | Mapping[str, Any] | None = None
    authentication_context: str | None = None
    target_goal: Mapping[str, Any] | None = None
    success_state_predicate: Callable[[AttackState], bool] | None = None
    runtime_facts: Sequence[RuntimeFact | Mapping[str, Any]] = ()
    assumptions: Sequence[RuntimeFact | Mapping[str, Any]] = ()
    budget: SearchBudget | Mapping[str, Any] | None = None
    allowed_techniques: Sequence[str] | None = None
    catalog: Sequence[Technique] | None = None
    aliases: Mapping[str, str] | None = None
    scenario_reference: str | None = None
    checkpoint_goal: Mapping[str, Any] | None = None
    checkpoint_state_predicate: Callable[[AttackState], bool] | None = None
    withheld_relationships: Sequence[StructuralRelationship] | None = None
    evaluation_mode: str = "scenario"
    active_scope: str | None = None
    action_bindings: (
        Mapping[tuple[str, str, str, str], str]
        | Sequence[tuple[tuple[str, str, str, str], str]]
        | None
    ) = None
    ranking_query: Mapping[str, Any] | None = None
    rbcd_bindings: Sequence[DelegationBinding | Mapping[str, Any]] = ()
    rating_resolution: Mapping[str, Any] | None = None
    top_k: int | None = None
    search_order: str = "fifo"


@dataclass(frozen=True)
class SemanticGoalDescriptor:
    """Declared necessary terminal capabilities, normalized by query materialization.

    An additional callable may narrow this goal; it cannot weaken these requirements.
    A callable alone has no declarative descriptor and cannot certify a consequence.
    """

    target_asset_id: str
    required_state: AttackState

    def __post_init__(self):
        if not isinstance(self.required_state, AttackState) or not any(
            getattr(self.required_state, name) for name in FIELDS
        ):
            raise ValueError("Semantic goal requires non-empty typed required_state")
        _validate_goal_references(self.required_state, self.target_asset_id)

    def matches(self, state: AttackState) -> bool:
        return _contains_state(state, self.required_state)

    def to_dict(self) -> dict[str, Any]:
        from src.engine.ranking.adapter_145 import _audit_value

        return {
            "version": "semantic-goal/1.0.0",
            "kind": "required_state",
            "target_asset_id": self.target_asset_id,
            "required_state": {
                name: _audit_value(getattr(self.required_state, name))
                for name in sorted(FIELDS)
                if getattr(self.required_state, name)
            },
        }


@dataclass(frozen=True, init=False)
class UsableIdentityEntitlementGoal(SemanticGoalDescriptor):
    """One same usable identity holds the group entitlement in this context.

    A versioned goal separate from actor-specific required-state descriptors.
    No new capability or implicit credential is granted by this predicate.
    """

    authentication_context: str

    def __init__(self, target_asset_id: str, authentication_context: str):
        if not all(
            isinstance(v, str) and v.strip() for v in (target_asset_id, authentication_context)
        ):
            raise ValueError("Identity entitlement goal requires target and authentication context")
        object.__setattr__(self, "target_asset_id", target_asset_id)
        object.__setattr__(self, "required_state", AttackState())
        object.__setattr__(self, "authentication_context", authentication_context)

    def matches(self, state: AttackState) -> bool:
        return any(
            context == self.authentication_context
            and (identity, self.target_asset_id) in state.effective_member
            for identity, context in state.usable_identity
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": "semantic-goal/1.1.0",
            "kind": "usable_identity_entitlement",
            "target_asset_id": self.target_asset_id,
            "authentication_context": self.authentication_context,
        }


def semantic_goal_from_dict(
    value: Mapping[str, Any], resolver: IdentityResolver
) -> SemanticGoalDescriptor:
    """Strict shared descriptor decoder for adapters and independent replay."""
    if not isinstance(value, Mapping):
        raise ValueError("Semantic goal descriptor must be a mapping")
    target = resolver.resolve(value.get("target_asset_id"))
    kind = value.get("kind")
    if kind == "required_state" and value.get("version") == "semantic-goal/1.0.0":
        if set(value) != {"version", "kind", "target_asset_id", "required_state"}:
            raise ValueError("Malformed required-state semantic goal descriptor")
        return SemanticGoalDescriptor(target, _state_from_spec(value["required_state"], resolver))
    if kind == "usable_identity_entitlement" and value.get("version") == "semantic-goal/1.1.0":
        if set(value) != {"version", "kind", "target_asset_id", "authentication_context"}:
            raise ValueError("Malformed identity-entitlement semantic goal descriptor")
        context = resolver.resolve(value["authentication_context"])
        if resolver._nodes and (
            resolver._nodes[target]["kind"] != "Group"
            or resolver._nodes[context]["kind"] != "Computer"
        ):
            raise ValueError("Identity entitlement requires a Group target and Computer context")
        return UsableIdentityEntitlementGoal(target, context)
    raise ValueError("Unsupported semantic goal kind/version")


def _materialize_goal(spec, target, resolver, authentication_context):
    kind = spec.get("kind", "required_state")
    if kind == "required_state":
        required = spec.get("required_state")
        if not required:
            raise ValueError("target_goal requires non-empty required_state")
        return SemanticGoalDescriptor(target, _state_from_spec(required, resolver))
    if kind != "usable_identity_entitlement" or "required_state" in spec:
        raise ValueError("Unsupported or ambiguous target_goal kind")
    context = resolver.resolve(spec.get("authentication_context") or authentication_context)
    if context != authentication_context:
        raise ValueError("Identity entitlement goal must use the query authentication context")
    return semantic_goal_from_dict(
        {
            "version": "semantic-goal/1.1.0",
            "kind": kind,
            "target_asset_id": target,
            "authentication_context": context,
        },
        resolver,
    )


@dataclass(frozen=True)
class MaterializedQuery:
    """Validated, canonicalized attack query ready for stateful path generation."""

    initial_actor: str
    initial_attack_state: AttackState
    runtime_context: RuntimeContext
    target: str
    target_predicate: Callable[[dict[str, Any]], bool]
    success_state_predicate: Callable[[AttackState], bool]
    catalog: tuple[Technique, ...]
    budget: SearchBudget
    rejected_assumptions: tuple[RejectedAssumption, ...] = ()
    diagnostics: tuple[dict[str, Any], ...] = ()
    scenario_reference: str | None = None
    checkpoint_state_predicate: Callable[[AttackState], bool] | None = None
    aliases: Mapping[str, str] = field(default_factory=dict)
    evaluation_mode: str = "scenario"
    active_scope: str | None = None
    action_bindings: Mapping[tuple[str, str, str, str], str] | None = None
    ranking_query: Mapping[str, Any] | None = None

    rating_resolution: Mapping[str, Any] | None = None
    semantic_goal: SemanticGoalDescriptor | None = None
    top_k: int | None = None
    search_order: str = "fifo"

    def __post_init__(self) -> None:
        from src.engine.search import validate_search_order

        validate_search_order(self.search_order)
        if self.top_k is not None:
            from src.engine.top_k import validate_k

            validate_k(self.top_k)

    def is_success_state(self, state: AttackState) -> bool:
        return self.success_state_predicate(state) and (
            self.semantic_goal is None or self.semantic_goal.matches(state)
        )

    @property
    def search_strategy(self):
        from src.engine.search import NEO_GUIDED_TECHNIQUES

        techniques = {t.id for t in self.catalog}
        if self.search_order in {"neo_guided", "neo_cost"}:
            supported = self.semantic_goal is not None and techniques <= NEO_GUIDED_TECHNIQUES
        else:
            supported = isinstance(self.semantic_goal, UsableIdentityEntitlementGoal) and (
                techniques
                <= {
                    "scenario_reset_password",
                    "acquire_reset_identity",
                    "propagate_group_entitlement",
                }
            )
        effective = self.search_order if supported else "fifo"
        return {
            "requested": self.search_order,
            "effective": effective,
            "version": {
                "fifo": "fifo/1",
                "goal_guided": "goal-guided-membership/1",
                "neo_guided": "neo-guided-topology/2",
                "neo_cost": "neo-cost-work-union/1",
            }[effective],
            "fallback_reason": "unsupported_goal_or_catalog"
            if self.search_order != effective
            else None,
            "priority_is_cost_lower_bound": effective == "neo_cost",
        }

    def to_search_kwargs(self) -> dict[str, Any]:
        """Convert to kwargs accepted by generate_attack_paths."""
        return {
            "actor": self.initial_actor,
            "initial_state": self.initial_attack_state,
            "runtime_context": self.runtime_context,
            "target_predicate": self.target_predicate,
            "success_state_predicate": self.is_success_state,
            "budget": self.budget,
            "catalog": self.catalog,
            "scenario_reference": self.scenario_reference,
            **(
                {"search_order": self.search_strategy["effective"]}
                if self.search_order != "fifo"
                else {}
            ),
        }

    def search(self, graph: EngineGraph | Mapping[str, Any]) -> AttackSearchResult:
        """Run existing stateful search using materialized parameters."""
        engine_graph = (
            graph if isinstance(graph, EngineGraph) else EngineGraph.from_canonical(graph)
        )
        if self.search_strategy["effective"] == "neo_cost":
            from src.engine.ranking.effort_profiles import validate_neo_cost_profile

            validate_neo_cost_profile(self, engine_graph)
        return generate_attack_paths(
            engine_graph,
            self.initial_actor,
            initial_state=self.initial_attack_state,
            runtime_context=self.runtime_context,
            target_predicate=self.target_predicate,
            success_state_predicate=self.is_success_state,
            budget=self.budget,
            catalog=self.catalog,
            scenario_reference=self.scenario_reference,
            search_order=self.search_strategy["effective"],
        )

    def run(
        self,
        graph: EngineGraph | Mapping[str, Any],
        *,
        action_bindings: Mapping[tuple[str, str, str, str], str] | None = None,
        ranking_query: Mapping[str, Any] | None = None,
    ) -> AttackQueryResult:
        """Execute stateful search and return enriched AttackQueryResult."""
        search_result = self.search(graph)

        eff_ranking_query = ranking_query if ranking_query is not None else self.ranking_query
        eff_action_bindings = (
            action_bindings if action_bindings is not None else self.action_bindings
        )
        automatic_candidates = None
        rating_coverage = None
        if self.rating_resolution is not None:
            if eff_ranking_query is not None or eff_action_bindings is not None:
                raise ValueError(
                    "Automatic rating_resolution conflicts with explicit ranking packet/bindings"
                )
            from src.engine.ranking.resolution_service import resolve_generated_rating_inputs

            engine_graph = (
                graph if isinstance(graph, EngineGraph) else EngineGraph.from_canonical(graph)
            )
            eff_ranking_query, automatic_candidates, rating_coverage = (
                resolve_generated_rating_inputs(
                    self.rating_resolution, engine_graph, self, search_result
                )
            )

        ranking_result: dict[str, Any] | None = None
        min_effort: dict[str, Any] | None = None
        best_path: PathResult | None = None
        all_best_paths: tuple[PathResult, ...] = ()
        optimization_scope: str | None = None
        binding_diagnostics: dict[str, dict[str, Any]] = {}

        is_zero_action = (
            len(search_result.paths) == 1 and len(search_result.paths[0].transition_history) == 0
        )
        if is_zero_action:
            raw_path = search_result.paths[0]
            best_path = PathResult(
                nodes=raw_path.nodes,
                edges=raw_path.edges,
                cost=0.0,
                transition_history=raw_path.transition_history,
                final_state=raw_path.final_state,
                scenario_reference=raw_path.scenario_reference,
                runtime_context=raw_path.runtime_context,
                initial_actor=raw_path.initial_actor,
            )
            all_best_paths = (best_path,)
            optimization_scope = "exhaustive_within_scope"
            if eff_ranking_query is not None:
                canonical_graph_dict = (
                    graph._canonical_cache
                    if isinstance(graph, EngineGraph)
                    and hasattr(graph, "_canonical_cache")
                    and graph._canonical_cache is not None
                    else (graph.to_canonical() if isinstance(graph, EngineGraph) else dict(graph))
                )
                nodes = {node["id"]: node for node in canonical_graph_dict.get("nodes", [])}
                resolver = IdentityResolver(nodes, self.aliases)
                canonical_target = resolver.resolve(self.target)

                from src.engine.ranking.orchestration import (
                    evaluate_zero_action_initial_goal,
                )

                ranking_eval = evaluate_zero_action_initial_goal(
                    dict(eff_ranking_query),
                    canonical_graph_dict,
                    actor=self.initial_actor,
                    target_id=canonical_target,
                    search_result=search_result,
                    budget=self.budget,
                    engine_graph=graph if isinstance(graph, EngineGraph) else None,
                    prepared=graph.to_prepared() if isinstance(graph, EngineGraph) else None,
                )
                ranking_result = ranking_eval["roundtrip_result"]
                if rating_coverage is not None:
                    ranking_result["rating_coverage"] = rating_coverage
                min_effort = ranking_result["zero_work_disposition"]
            return _evaluate_query_outcome(
                search_result,
                self,
                ranking_result=ranking_result,
                min_effort=min_effort,
                best_path=best_path,
                all_best_paths=all_best_paths,
                optimization_scope=optimization_scope,
                binding_diagnostics=binding_diagnostics,
            )

        if eff_ranking_query is not None:
            from src.engine.ranking.orchestration import (
                coverage_from_search_result,
                evaluate_search_candidates,
            )

            canonical_graph_dict = (
                graph._canonical_cache
                if isinstance(graph, EngineGraph)
                and hasattr(graph, "_canonical_cache")
                and graph._canonical_cache is not None
                else (graph.to_canonical() if isinstance(graph, EngineGraph) else dict(graph))
            )
            nodes = {node["id"]: node for node in canonical_graph_dict.get("nodes", [])}
            resolver = IdentityResolver(nodes, self.aliases)
            eff_action_bindings_dict: dict[tuple[str, str, str, str], str] | None = None
            if eff_action_bindings is not None:
                eff_action_bindings_dict = _normalize_action_bindings(eff_action_bindings, resolver)
            coverage = coverage_from_search_result(search_result, self.budget)

            generated_candidates: list[dict[str, Any]] = []
            path_by_cand_id: dict[str, PathResult] = {}
            bound_actions_catalog = eff_ranking_query.get("bound_actions", [])

            for index, path in enumerate(search_result.paths, start=1):
                if automatic_candidates is not None:
                    candidate_id = f"generated_{index:04d}"
                    path_by_cand_id[candidate_id] = path
                    continue
                action_ids: list[str] = []
                missing: list[dict[str, Any]] = []
                for step_index, step in enumerate(path.transition_history):
                    request = step.result.request
                    key = (
                        request.technique_id,
                        request.actor,
                        request.source,
                        request.target,
                    )
                    action_id = (
                        eff_action_bindings_dict.get(key)
                        if eff_action_bindings_dict is not None
                        else None
                    )
                    if (
                        action_id is None
                        and eff_action_bindings_dict is None
                        and step.edge_id
                        and bound_actions_catalog
                    ):
                        edge_matches = [
                            a["action_id"]
                            for a in bound_actions_catalog
                            if a.get("edge_id") == step.edge_id
                            and a.get("technique") == request.technique_id
                        ]
                        if len(edge_matches) == 1:
                            action_id = edge_matches[0]
                    if action_id is None:
                        missing.append(
                            {
                                "step_index": step_index,
                                "technique_id": request.technique_id,
                                "actor": request.actor,
                                "source": request.source,
                                "target": request.target,
                            }
                        )
                    else:
                        action_ids.append(action_id)
                candidate_id = f"generated_{index:04d}"
                if missing:
                    binding_diagnostics[candidate_id] = {
                        "reason": "explicit_action_binding_missing",
                        "unbound_steps": missing,
                    }
                    continue
                generated_candidates.append(
                    {
                        "candidate_id": candidate_id,
                        "target_asset_id": self.target,
                        "route_id": f"route_{candidate_id}",
                        "action_mapping": action_ids,
                        "path_result": path,
                    }
                )
                path_by_cand_id[candidate_id] = path

            if automatic_candidates is not None:
                generated_candidates = automatic_candidates

            if generated_candidates or automatic_candidates is not None:
                ranking_query_payload = dict(eff_ranking_query)
                if self.semantic_goal is not None:
                    metadata = dict(ranking_query_payload["query_metadata"])
                    descriptor = self.semantic_goal.to_dict()
                    if metadata.get("semantic_goal") not in (None, descriptor):
                        raise ValueError(
                            "Ranking state-goal descriptor conflicts with semantic query"
                        )
                    metadata["semantic_goal"] = descriptor
                    ranking_query_payload["query_metadata"] = metadata
                if self.runtime_context.rbcd_bindings and "query_metadata" in ranking_query_payload:
                    from dataclasses import asdict

                    qm = dict(ranking_query_payload["query_metadata"])
                    qm["bound_rbcd_binding"] = asdict(self.runtime_context.rbcd_bindings[0])
                    ranking_query_payload["query_metadata"] = qm
                ranking_eval = evaluate_search_candidates(
                    ranking_query_payload,
                    generated_candidates,
                    canonical_graph=canonical_graph_dict,
                    coverage=coverage,
                    snapshot_facts=graph.snapshot_facts if isinstance(graph, EngineGraph) else None,
                    catalog=self.catalog,
                    engine_graph=graph if isinstance(graph, EngineGraph) else None,
                    prepared=graph.to_prepared() if isinstance(graph, EngineGraph) else None,
                )
                ranking_result = ranking_eval["roundtrip_result"]
                if rating_coverage is not None:
                    ranking_result["rating_coverage"] = rating_coverage

                # Collect ALL assessed candidates across eligible and diagnostics partitions
                all_assessed = list(ranking_eval.get("assessed_candidates", []))
                if not all_assessed and ranking_result:
                    all_assessed_map = dict(ranking_result.get("eligible_candidates", {}))
                    for cid, diag in ranking_result.get("diagnostics", {}).items():
                        if isinstance(diag, dict) and "assessment" in diag:
                            all_assessed_map[cid] = diag["assessment"]
                    all_assessed = list(all_assessed_map.values())

                assessed_cids = {
                    c["candidate_id"]
                    for c in all_assessed
                    if c.get("status") in ("feasible", "infeasible")
                }
                for cand_item in generated_candidates:
                    cid = cand_item["candidate_id"]
                    if cid not in assessed_cids and cid not in binding_diagnostics:
                        diag = ranking_result.get("diagnostics", {}).get(cid, {})
                        reasons = diag.get("reasons", ["adapter_rejected"])
                        assessment = diag.get("assessment", {})
                        diag_msg = assessment.get(
                            "diagnostic",
                            "Candidate rejected by ranking adapter or candidate validation",
                        )
                        primary_reason = reasons[0] if reasons else "adapter_rejected"
                        binding_diagnostics[cid] = {
                            "reason": primary_reason,
                            "reasons": reasons,
                            "diagnostic": diag_msg,
                        }

                rejected_adapter_count = len(
                    [
                        c
                        for c in binding_diagnostics.values()
                        if c.get("reason") != "explicit_action_binding_missing"
                    ]
                )
                search_audit = ranking_result.setdefault("search_audit", {})
                search_audit["binding_diagnostics"] = dict(binding_diagnostics)
                search_audit["generated_paths"] = len(search_result.paths)
                search_audit["generated_candidates_bound"] = len(generated_candidates)
                search_audit["candidates_unbound"] = len(binding_diagnostics)
                search_audit["candidates_rejected_by_adapter"] = (
                    ranking_result.get("search_audit", {}).get("candidates_rejected_by_adapter", 0)
                    or rejected_adapter_count
                )

                min_effort = ranking_result.get("min_effort_to_da_baseline")

                best_cand_id = min_effort.get("best_candidate_id") if min_effort else None
                best_effort_val = min_effort.get("minimum_effort_value") if min_effort else None

                if best_cand_id and best_cand_id in path_by_cand_id:
                    raw_best = path_by_cand_id[best_cand_id]
                    best_path = PathResult(
                        nodes=raw_best.nodes,
                        edges=raw_best.edges,
                        cost=(
                            float(best_effort_val) if best_effort_val is not None else raw_best.cost
                        ),
                        transition_history=raw_best.transition_history,
                        final_state=raw_best.final_state,
                        scenario_reference=raw_best.scenario_reference,
                        runtime_context=raw_best.runtime_context,
                        initial_actor=raw_best.initial_actor,
                        goal_target=raw_best.goal_target,
                    )

                if best_effort_val is not None:
                    all_best_candidates = [
                        c["candidate_id"]
                        for c in all_assessed
                        if c.get("status") == "feasible"
                        and c.get("effort_status") == "rated"
                        and c.get("effort") == best_effort_val
                    ]
                    all_best_paths = tuple(
                        PathResult(
                            nodes=raw_p.nodes,
                            edges=raw_p.edges,
                            cost=float(best_effort_val),
                            transition_history=raw_p.transition_history,
                            final_state=raw_p.final_state,
                            scenario_reference=raw_p.scenario_reference,
                            runtime_context=raw_p.runtime_context,
                            initial_actor=raw_p.initial_actor,
                            goal_target=raw_p.goal_target,
                        )
                        for c in all_best_candidates
                        if c in path_by_cand_id
                        for raw_p in (path_by_cand_id[c],)
                    )
                    if min_effort is not None:
                        min_effort["all_best_candidate_ids"] = all_best_candidates
                        min_effort["tie_count"] = len(all_best_candidates)
                else:
                    all_best_paths = ()

                if search_result.truncated:
                    optimization_scope = (
                        "best_in_generated_subset"
                        if best_path is not None
                        else "truncated_incomplete"
                    )
                elif search_result.complete:
                    if (
                        binding_diagnostics
                        or len(generated_candidates) < len(search_result.paths)
                        or len(assessed_cids) < len(search_result.paths)
                    ):
                        optimization_scope = (
                            "best_in_bound_subset"
                            if best_path is not None
                            else "no_bound_candidates"
                        )
                    else:
                        feasible_candidates = [
                            c for c in all_assessed if c.get("status") == "feasible"
                        ]
                        effort_unrated_feasible = [
                            c
                            for c in feasible_candidates
                            if c.get("effort_status") != "rated" or c.get("effort") is None
                        ]
                        if effort_unrated_feasible:
                            optimization_scope = "best_in_rated_subset"
                        elif feasible_candidates:
                            optimization_scope = "exhaustive_within_scope"
                        else:
                            optimization_scope = (
                                "exhaustive_within_scope"
                                if not search_result.paths
                                else "no_rated_candidates"
                            )
                else:
                    optimization_scope = "unspecified_subset"
            else:
                if search_result.truncated:
                    optimization_scope = "truncated_incomplete"
                elif not search_result.paths:
                    optimization_scope = "exhaustive_within_scope"
                elif binding_diagnostics:
                    optimization_scope = "no_bound_candidates"
                else:
                    optimization_scope = "budget_bounded"
        else:
            if search_result.truncated:
                optimization_scope = "partial_truncated"
            elif not search_result.paths:
                optimization_scope = "exhaustive_within_scope"
            else:
                optimization_scope = "budget_bounded"

        return _evaluate_query_outcome(
            search_result,
            self,
            ranking_result=ranking_result,
            min_effort=min_effort,
            best_path=best_path,
            all_best_paths=all_best_paths,
            optimization_scope=optimization_scope,
            binding_diagnostics=binding_diagnostics,
        )


@dataclass(frozen=True)
class AttackQueryResult:
    """Public execution result wrapping AttackSearchResult with query outcomes."""

    search_result: AttackSearchResult
    materialized_query: MaterializedQuery
    checkpoint_reached: bool = False
    final_goal_reached: bool = False
    status: str = "no_path"
    ranking_result: dict[str, Any] | None = None
    min_effort: dict[str, Any] | None = None
    best_path: PathResult | None = None
    all_best_paths: tuple[PathResult, ...] = ()
    optimization_scope: str | None = None
    binding_diagnostics: Mapping[str, dict[str, Any]] = MappingProxyType({})
    top_k_result: dict[str, Any] | None = None

    @cached_property
    def semantic_coverage_gaps(self) -> tuple[dict[str, Any], ...]:
        """Known missing consumers of reachable opaque material, not AD impossibility.

        This narrow check concerns declared identity goals; it does not certify
        that the material's owner has a route to the requested target. Keep
        branches separate: another branch's artifact cannot discharge this gap.
        No capability or credential is created.
        """
        materialized = self.materialized_query
        goal = materialized.semantic_goal
        if isinstance(goal, UsableIdentityEntitlementGoal):
            required_owners = None
        elif goal is not None and goal.required_state.usable_identity:
            required_owners = {
                owner
                for owner, context in goal.required_state.usable_identity
                if context == materialized.runtime_context.authentication_context
            }
            if not required_owners:
                return ()
        else:
            return ()
        scope = materialized.runtime_context.authentication_context
        missing = set()

        def inspect(state):
            covered = {u for u, context in state.usable_identity if context == scope}
            covered.update(a.owner for a in state.recovered_secret if a.context == scope)
            owners = state.credential_material - covered
            if required_owners is not None:
                owners &= required_owners
            missing.update(owners)

        inspect(materialized.initial_attack_state)
        for attempt in self.attempts:
            if attempt.status == Status.APPLICABLE and attempt.additions.credential_material:
                inspect(apply_transition(attempt.before, attempt))
        return tuple(
            {
                "code": "UNTYPED_CREDENTIAL_ACTIVATION_UNSUPPORTED",
                "status": "unsupported",
                "reason": "untyped_session_material_activation_unsupported",
                "owner": owner,
                "authentication_context": scope,
                "material_reached": True,
                "message": (
                    "Reachable credential_material is untyped; no supported rule converts it "
                    "to a password/usable identity. A typed owner/context-bound artifact needs "
                    "separate evidence. This gap does not establish a route to the goal."
                ),
            }
            for owner in sorted(missing)
        )

    @property
    def rating_coverage(self) -> dict[str, Any] | None:
        return self.ranking_result.get("rating_coverage") if self.ranking_result else None

    @property
    def min_effort_baseline(self) -> dict[str, Any] | None:
        """Min-Effort summary, or the explicitly labeled semantic zero-work disposition."""
        return self.min_effort

    @property
    def caps(self) -> dict[str, int]:
        """Applied search caps."""
        b = self.materialized_query.budget
        return {
            "max_paths": b.max_paths,
            "max_steps": b.max_steps,
            "max_expansions": b.max_expansions,
        }

    @property
    def is_minimum_proven_over_scope(self) -> bool:
        """True if and only if finite scope is complete, not truncated,
        no binding gaps, and all feasible alternatives are rated.
        """
        return (
            self.search_result.complete
            and not self.search_result.truncated
            and not self.binding_diagnostics
            and not self.semantic_coverage_gaps
            and self.optimization_scope == "exhaustive_within_scope"
            and self.min_effort is not None
            and self.min_effort.get("minimum_effort_value") is not None
            and not any(a.status == Status.INDETERMINATE for a in self.search_result.attempts)
            and not (self.ranking_result or {}).get("search_metadata", {}).get("is_truncated")
        )

    @property
    def is_no_path_proven_over_scope(self) -> bool:
        """True if and only if finite scope is complete, not truncated,
        no indeterminate gates, and no paths reached goal.
        """
        return (
            self.search_result.complete
            and not self.search_result.truncated
            and not self.final_goal_reached
            and not self.semantic_coverage_gaps
            and self.status
            in (
                "no_path",
                "checkpoint_reached_final_goal_no_path",
                "checkpoint_reached_final_goal_blocked",
                "blocked",
            )
            and not any(a.status == Status.INDETERMINATE for a in self.search_result.attempts)
        )

    @property
    def diagnostics(self) -> tuple[dict[str, Any], ...]:
        """Consolidated diagnostics from fact materialization and search attempts."""
        diag_list: list[dict[str, Any]] = list(self.materialized_query.diagnostics)
        diag_list.extend(self.semantic_coverage_gaps)
        for cand_id, b_diag in self.binding_diagnostics.items():
            entry: dict[str, Any] = {
                "candidate_id": cand_id,
                "status": (
                    "unbound"
                    if b_diag.get("reason") == "explicit_action_binding_missing"
                    else "rejected"
                ),
                "reason": b_diag.get("reason"),
            }
            if "diagnostic" in b_diag:
                entry["diagnostic"] = b_diag["diagnostic"]
            if "reasons" in b_diag:
                entry["reasons"] = b_diag["reasons"]
            if "unbound_steps" in b_diag:
                entry["unbound_steps"] = b_diag["unbound_steps"]
            diag_list.append(entry)
        for attempt in self.search_result.attempts:
            if attempt.status != Status.APPLICABLE:
                diag_list.append(
                    {
                        "technique_id": attempt.request.technique_id,
                        "actor": attempt.request.actor,
                        "source": attempt.request.source,
                        "target": attempt.request.target,
                        "status": str(attempt.status),
                        "failed": sorted(attempt.failed),
                        "unknown": sorted(attempt.unknown),
                        "decisions": [
                            {
                                "predicate": d.predicate,
                                "satisfied": d.satisfied,
                                "origin": str(d.origin),
                                "rationale": d.rationale,
                                "subject": d.fact.subject if d.fact is not None else None,
                                "target": d.fact.target if d.fact is not None else None,
                                "value": d.fact.value if d.fact is not None else None,
                            }
                            for d in attempt.decisions
                        ],
                    }
                )
        return tuple(diag_list)

    @property
    def checkpoint_diagnostics(self) -> tuple[dict[str, Any], ...]:
        """Diagnostics specifically relevant to why final goal was not reached after checkpoint."""
        if not self.checkpoint_reached or self.final_goal_reached:
            return ()
        return tuple(
            d
            for d in self.diagnostics
            if d.get("status") in (str(Status.BLOCKED), str(Status.INDETERMINATE))
        )

    @property
    def paths(self) -> tuple[PathResult, ...]:
        return self.search_result.paths

    @property
    def attempts(self) -> tuple[TransitionResult, ...]:
        return self.search_result.attempts

    @property
    def expansions(self) -> int:
        return self.search_result.expansions

    @property
    def truncated(self) -> bool:
        return self.search_result.truncated

    @property
    def truncation_reason(self) -> str | None:
        return self.search_result.truncation_reason

    @property
    def complete(self) -> bool:
        return self.search_result.complete

    def __iter__(self):
        return iter(self.search_result.paths)

    def __len__(self) -> int:
        return len(self.search_result.paths)

    def __bool__(self) -> bool:
        return bool(self.search_result.paths)


class IdentityResolver:
    """Boundary resolver mapping aliases and public identifiers to canonical node IDs."""

    def __init__(
        self,
        nodes: Mapping[str, Mapping[str, Any]],
        aliases: Mapping[str, str] | None = None,
    ) -> None:
        self._nodes = nodes
        self._aliases = dict(aliases) if aliases else {}

    def resolve(self, identifier: str) -> str:
        if not isinstance(identifier, str) or not identifier.strip():
            raise ValueError(f"identifier must be a non-empty string, got {identifier!r}")
        cleaned = identifier.strip()
        if cleaned in self._aliases:
            canonical_id = self._aliases[cleaned]
            if self._nodes and canonical_id not in self._nodes:
                raise ValueError(
                    f"alias {cleaned!r} maps to {canonical_id!r} "
                    "which does not exist in graph nodes"
                )
            return canonical_id
        if not self._nodes or cleaned in self._nodes:
            return cleaned
        raise ValueError(
            f"unresolvable identity reference: {cleaned!r} is neither a known alias "
            "nor an existing canonical node ID"
        )


def _contains_state(state: AttackState, expected: AttackState) -> bool:
    return all(getattr(expected, f).issubset(getattr(state, f)) for f in FIELDS)


def _state_from_spec(
    spec: AttackState | Mapping[str, Any],
    resolver: IdentityResolver,
) -> AttackState:
    if isinstance(spec, AttackState):
        normalized = {}
        for f in FIELDS:
            vals = getattr(spec, f)
            if not vals:
                normalized[f] = frozenset()
            elif f in RBCD_FIELDS:
                normalized[f] = frozenset(decode_artifact(v, resolver) for v in vals)
            elif f in ARTIFACTS:
                normalized[f] = frozenset(
                    CredentialArtifact(
                        resolver.resolve(a.owner), resolver.resolve(a.context), a.form, a.provenance
                    )
                    for a in vals
                )
            elif f in PAIRS:
                normalized[f] = frozenset(
                    (resolver.resolve(u), resolver.resolve(h)) for u, h in vals
                )
            elif f in RELATIONS:
                normalized[f] = frozenset(
                    StructuralRelationship(
                        resolver.resolve(rel.source),
                        rel.kind,
                        resolver.resolve(rel.target),
                    )
                    for rel in vals
                )
            else:
                normalized[f] = frozenset(resolver.resolve(v) for v in vals)
        return AttackState(**normalized)

    if not isinstance(spec, Mapping):
        raise TypeError(f"initial_state must be AttackState or Mapping, got {type(spec)!r}")

    unknown_fields = set(spec) - FIELDS
    if unknown_fields:
        raise ValueError(f"unknown state fields: {sorted(unknown_fields)}")

    normalized = {}
    for f in FIELDS:
        raw_vals = spec.get(f)
        if raw_vals is None:
            normalized[f] = frozenset()
            continue
        if not isinstance(raw_vals, (list, tuple, set, frozenset)):
            raise TypeError(f"state field {f!r} must be a collection")
        entries = []
        for val in raw_vals:
            if f in RBCD_FIELDS:
                entries.append(decode_artifact(val, resolver))
            elif f in ARTIFACTS:
                a = val if isinstance(val, CredentialArtifact) else CredentialArtifact(**val)
                entries.append(
                    CredentialArtifact(
                        resolver.resolve(a.owner), resolver.resolve(a.context), a.form, a.provenance
                    )
                )
            elif f in PAIRS:
                if not isinstance(val, (list, tuple)) or len(val) != 2:
                    raise ValueError(f"{f} requires node pairs")
                entries.append((resolver.resolve(val[0]), resolver.resolve(val[1])))
            elif f in RELATIONS:
                if isinstance(val, Mapping) and set(val) == {"source", "kind", "target"}:
                    val = StructuralRelationship(**val)
                if isinstance(val, StructuralRelationship):
                    entries.append(
                        StructuralRelationship(
                            resolver.resolve(val.source),
                            val.kind,
                            resolver.resolve(val.target),
                        )
                    )
                elif isinstance(val, (list, tuple)) and len(val) == 3:
                    entries.append(
                        StructuralRelationship(
                            resolver.resolve(val[0]),
                            val[1],
                            resolver.resolve(val[2]),
                        )
                    )
                else:
                    raise ValueError(f"{f} requires source/kind/target triples")
            else:
                if not isinstance(val, str) or not val.strip():
                    raise ValueError(f"{f} requires string node references")
                entries.append(resolver.resolve(val))
        if len(entries) != len(set(entries)):
            raise ValueError(f"duplicate state entry in {f}")
        normalized[f] = frozenset(entries)

    return AttackState(**normalized)


def _validate_goal_references(
    goal_state: AttackState,
    canonical_target: str,
) -> None:
    if not any(vars(goal_state).values()):
        raise ValueError("empty success predicate")
    referenced: set[str] = set()
    for f in FIELDS:
        for val in getattr(goal_state, f):
            if f in RBCD_FIELDS:
                referenced.update(getattr(val.binding, k) for k in ID_FIELDS)
            elif f in ARTIFACTS:
                referenced.update((val.owner, val.context))
            elif f in RELATIONS:
                referenced.update((val.source, val.target))
            elif f in PAIRS:
                referenced.update(val)
            else:
                referenced.add(val)
    if canonical_target not in referenced:
        raise ValueError(f"success predicate must reference target asset {canonical_target!r}")


def _normalize_fact_entry(
    entry: RuntimeFact | Mapping[str, Any],
    resolver: IdentityResolver,
    *,
    is_assumption: bool = False,
    default_origin: FactOrigin = FactOrigin.OBSERVED_EVIDENCE,
) -> RuntimeFact:
    if is_assumption:
        if isinstance(entry, RuntimeFact):
            if entry.origin != FactOrigin.DECLARED_ASSUMPTION:
                raise ValueError(
                    f"assumption entry cannot claim origin {entry.origin.value!r}; "
                    "all items in assumptions must have origin FactOrigin.DECLARED_ASSUMPTION"
                )
            if not isinstance(entry.scope, str) or not entry.scope.strip():
                raise ValueError("declared assumption requires non-empty scope")
            if not isinstance(entry.rationale, str) or not entry.rationale.strip():
                raise ValueError("declared assumption requires non-empty rationale")
            canonical_subject = resolver.resolve(entry.subject)
            canonical_target = resolver.resolve(entry.target)
            if canonical_subject == entry.subject and canonical_target == entry.target:
                return entry
            return RuntimeFact(
                predicate=entry.predicate,
                subject=canonical_subject,
                target=canonical_target,
                value=entry.value,
                origin=FactOrigin.DECLARED_ASSUMPTION,
                scope=entry.scope,
                rationale=entry.rationale,
                provenance_reference=entry.provenance_reference,
                assumption_metadata=entry.assumption_metadata,
            )

        if not isinstance(entry, Mapping):
            raise TypeError(f"runtime fact must be RuntimeFact or Mapping, got {type(entry)!r}")

        raw_origin = entry.get("origin")
        if raw_origin is not None:
            try:
                parsed_origin = FactOrigin(raw_origin)
            except ValueError as err:
                raise ValueError(f"invalid FactOrigin: {raw_origin!r}") from err
            if parsed_origin != FactOrigin.DECLARED_ASSUMPTION:
                raise ValueError(
                    f"assumption entry cannot claim origin {parsed_origin.value!r}; "
                    "all items in assumptions must have origin DECLARED_ASSUMPTION"
                )
        else:
            parsed_origin = FactOrigin.DECLARED_ASSUMPTION

        scope = entry.get("scope")
        if not isinstance(scope, str) or not scope.strip():
            raise ValueError("declared assumption requires non-empty scope")
        rationale = entry.get("rationale")
        if not isinstance(rationale, str) or not rationale.strip():
            raise ValueError("declared assumption requires non-empty rationale")

        for req in ("predicate", "subject", "target"):
            if req not in entry or not isinstance(entry[req], str) or not entry[req].strip():
                raise ValueError(f"runtime fact requires non-empty {req}")

        predicate = entry["predicate"].strip()
        subject = resolver.resolve(entry["subject"])
        target = resolver.resolve(entry["target"])
        value = entry.get("value")
        if type(value) not in (bool, type(None)):
            raise TypeError(f"runtime fact value must be bool or None, got {value!r}")

        return RuntimeFact(
            predicate=predicate,
            subject=subject,
            target=target,
            value=value,
            origin=parsed_origin,
            scope=scope,
            rationale=rationale,
            provenance_reference=entry.get("provenance_reference") or entry.get("evidence_ref"),
            assumption_metadata=entry.get("assumption_metadata"),
        )

    # runtime_facts path
    if isinstance(entry, RuntimeFact):
        canonical_subject = resolver.resolve(entry.subject)
        canonical_target = resolver.resolve(entry.target)
        if canonical_subject == entry.subject and canonical_target == entry.target:
            return entry
        return RuntimeFact(
            predicate=entry.predicate,
            subject=canonical_subject,
            target=canonical_target,
            value=entry.value,
            origin=entry.origin,
            scope=entry.scope,
            rationale=entry.rationale,
            provenance_reference=entry.provenance_reference,
            assumption_metadata=entry.assumption_metadata,
        )

    if not isinstance(entry, Mapping):
        raise TypeError(f"runtime fact must be RuntimeFact or Mapping, got {type(entry)!r}")

    for req in ("predicate", "subject", "target"):
        if req not in entry or not isinstance(entry[req], str) or not entry[req].strip():
            raise ValueError(f"runtime fact requires non-empty {req}")

    predicate = entry["predicate"].strip()
    subject = resolver.resolve(entry["subject"])
    target = resolver.resolve(entry["target"])
    value = entry.get("value")
    if type(value) not in (bool, type(None)):
        raise TypeError(f"runtime fact value must be bool or None, got {value!r}")

    raw_origin = entry.get("origin", default_origin)
    try:
        origin = FactOrigin(raw_origin)
    except ValueError as err:
        raise ValueError(f"invalid FactOrigin: {raw_origin!r}") from err

    scope = entry.get("scope")
    rationale = entry.get("rationale")
    provenance_reference = entry.get("provenance_reference") or entry.get("evidence_ref")
    assumption_metadata = entry.get("assumption_metadata")

    if origin == FactOrigin.DECLARED_ASSUMPTION:
        if not isinstance(scope, str) or not scope.strip():
            raise ValueError("declared assumption requires non-empty scope")
        if not isinstance(rationale, str) or not rationale.strip():
            raise ValueError("declared assumption requires non-empty rationale")

    return RuntimeFact(
        predicate=predicate,
        subject=subject,
        target=target,
        value=value,
        origin=origin,
        scope=scope,
        rationale=rationale,
        provenance_reference=provenance_reference,
        assumption_metadata=assumption_metadata,
    )


def _fact_view(fact: RuntimeFact) -> str | None:
    """Read the explicit view dimension; RuntimeFact.scope may be a time horizon."""
    metadata = fact.assumption_metadata
    if metadata is None:
        return None
    if not isinstance(metadata, Mapping):
        raise TypeError("assumption_metadata must be a Mapping")
    view = metadata.get("view_id")
    if view is not None and (not isinstance(view, str) or not view.strip()):
        raise ValueError("assumption_metadata.view_id must be a non-empty string")
    return view


def _validate_assumption_source(fact: RuntimeFact) -> None:
    """Require a traceable source for both typed and mapping assumption inputs."""
    if fact.origin is not FactOrigin.DECLARED_ASSUMPTION:
        return
    metadata = fact.assumption_metadata or {}
    sources = (fact.provenance_reference, metadata.get("declared_by"), metadata.get("source"))
    if not any(isinstance(source, str) and source.strip() for source in sources):
        raise ValueError(
            "declared assumption requires provenance_reference or "
            "assumption_metadata.declared_by/source"
        )


def _normalize_action_bindings(
    action_bindings_raw: Mapping[Any, Any] | Sequence[Any],
    resolver: IdentityResolver,
) -> dict[tuple[str, str, str, str], str]:
    """Normalize and validate action bindings, resolving aliases and checking for conflicts."""
    if isinstance(action_bindings_raw, Mapping):
        items = action_bindings_raw.items()
    elif isinstance(action_bindings_raw, Sequence):
        items = action_bindings_raw
    else:
        raise TypeError(
            "action_bindings must be a Mapping or Sequence of "
            "((tech, actor, source, target), action_id)"
        )
    normalized: dict[tuple[str, str, str, str], str] = {}
    for key, act_id in items:
        if not isinstance(key, (tuple, list)) or len(key) != 4:
            raise ValueError("action_bindings keys must be 4-tuples: (tech, actor, source, target)")
        tech, act_actor, act_source, act_target = key
        if any(
            not isinstance(x, str) or not x.strip()
            for x in (tech, act_actor, act_source, act_target)
        ):
            raise ValueError("action_bindings key items must be non-empty strings")
        if not isinstance(act_id, str) or not act_id.strip():
            raise ValueError("action_bindings values must be non-empty strings")
        norm_key = (
            tech.strip(),
            resolver.resolve(act_actor),
            resolver.resolve(act_source),
            resolver.resolve(act_target),
        )
        cleaned_act_id = act_id.strip()
        existing_act_id = normalized.get(norm_key)
        if existing_act_id is not None and existing_act_id != cleaned_act_id:
            raise ValueError(
                f"Conflicting action bindings for canonical key {norm_key}: "
                f"{existing_act_id!r} vs {cleaned_act_id!r}"
            )
        normalized[norm_key] = cleaned_act_id
    return normalized


def resolve_scenario_facts(
    runtime_facts: Sequence[RuntimeFact | Mapping[str, Any]],
    assumptions: Sequence[RuntimeFact | Mapping[str, Any]],
    resolver: IdentityResolver,
    *,
    evaluation_mode: str = "scenario",
    active_scope: str | None = None,
) -> tuple[
    dict[tuple[str, str, str], RuntimeFact],
    tuple[RejectedAssumption, ...],
    list[dict[str, Any]],
]:
    """Resolve facts and declared assumptions following the repository's strict policy.

    Resolution Policy (Invariant 3 & 4):
    1. Authoritative / observed fact > declared assumption.
    2. Known false: Authoritative False vetoes any assumption asserting True in the same scope.
       Assumption is recorded as rejected; resolved fact stays False.
    3. Known true: Authoritative True wins; redundant or conflicting assumptions handled.
    4. Missing fact: Remains missing/unknown if no valid assumption was declared.
       Does NOT default to False or True.
    5. Accepted assumption: Usable in scenario evaluation; preserves origin and provenance.
    6. Rejected assumptions are auditable and never enter the authoritative RuntimeContext.
    7. View handling: active_scope selects assumption_metadata.view_id, never raw scope.
       Untagged records belong to this query; raw scope retains its horizon/context meaning.
       Multiple explicit views require a selector, including evidence-only inputs.
    """
    if evaluation_mode not in VALID_EVALUATION_MODES:
        raise ValueError(
            f"invalid evaluation_mode: {evaluation_mode!r}; "
            f"allowed modes: {sorted(VALID_EVALUATION_MODES)}"
        )

    normalized_facts: list[RuntimeFact] = [
        _normalize_fact_entry(
            f, resolver, is_assumption=False, default_origin=FactOrigin.OBSERVED_EVIDENCE
        )
        for f in runtime_facts
    ]
    normalized_assumptions: list[RuntimeFact] = [
        _normalize_fact_entry(
            a, resolver, is_assumption=True, default_origin=FactOrigin.DECLARED_ASSUMPTION
        )
        for a in assumptions
    ]

    entries = normalized_facts + normalized_assumptions
    views = {}
    for entry in entries:
        views[id(entry)] = _fact_view(entry)
        _validate_assumption_source(entry)
    distinct_views = {view for view in views.values() if view is not None}
    if active_scope is None:
        if len(distinct_views) > 1:
            raise ValueError(
                f"multiple scenario views ({sorted(distinct_views)}) require active_scope"
            )
        effective_view = next(iter(distinct_views)) if distinct_views else None
    else:
        if not isinstance(active_scope, str) or not active_scope.strip():
            raise ValueError("active_scope must be a non-empty view ID")
        if active_scope not in distinct_views:
            raise ValueError(f"active_scope {active_scope!r} does not identify an explicit view")
        effective_view = active_scope

    # Never discard a query-local known-false merely because its raw scope is a
    # scenario ID while a related assumption's raw scope is a time horizon.
    active_facts = [
        f for f in normalized_facts if views[id(f)] is None or views[id(f)] == effective_view
    ]
    active_assumptions = [
        a for a in normalized_assumptions if views[id(a)] is None or views[id(a)] == effective_view
    ]

    authoritative_facts: dict[tuple[str, str, str], list[RuntimeFact]] = {}
    declared_assumptions: dict[tuple[str, str, str], list[RuntimeFact]] = {}

    for fact in active_facts:
        key = (fact.predicate, fact.subject, fact.target)
        if fact.origin == FactOrigin.DECLARED_ASSUMPTION:
            declared_assumptions.setdefault(key, []).append(fact)
        else:
            authoritative_facts.setdefault(key, []).append(fact)

    for assumption in active_assumptions:
        key = (assumption.predicate, assumption.subject, assumption.target)
        declared_assumptions.setdefault(key, []).append(assumption)

    resolved_facts: dict[tuple[str, str, str], RuntimeFact] = {}
    rejected_assumptions: list[RejectedAssumption] = []
    diagnostics: list[dict[str, Any]] = []

    all_keys = set(authoritative_facts) | set(declared_assumptions)

    for key in sorted(all_keys):
        p, s, t = key
        auth_list = authoritative_facts.get(key, [])
        assump_list = declared_assumptions.get(key, [])

        # Check for contradictory authoritative facts
        auth_vals = {f.value for f in auth_list}
        if True in auth_vals and False in auth_vals:
            raise ValueError(
                f"contradictory authoritative runtime facts for {key}: "
                "cannot reconcile True and False"
            )

        has_auth_false = False in auth_vals
        has_auth_true = True in auth_vals

        if has_auth_false:
            authoritative_fact = next(f for f in auth_list if f.value is False)
            resolved_facts[key] = authoritative_fact
            for af in assump_list:
                rejected = RejectedAssumption(
                    predicate=p,
                    subject=s,
                    target=t,
                    assumption_value=af.value,
                    scope=af.scope,
                    reason="known_false_veto",
                    conflicting_fact=authoritative_fact,
                    rationale=af.rationale,
                    provenance_reference=af.provenance_reference,
                    assumption_metadata=MappingProxyType(dict(af.assumption_metadata or {})),
                )
                rejected_assumptions.append(rejected)
                diagnostics.append(
                    {
                        "action": "rejected_assumption",
                        "predicate": p,
                        "subject": s,
                        "target": t,
                        "reason": "known_false_veto",
                        "conflicting_value": False,
                        "conflicting_origin": str(authoritative_fact.origin),
                    }
                )
            continue

        if has_auth_true:
            authoritative_fact = next(f for f in auth_list if f.value is True)
            resolved_facts[key] = authoritative_fact
            for af in assump_list:
                if af.value is False:
                    rejected = RejectedAssumption(
                        predicate=p,
                        subject=s,
                        target=t,
                        assumption_value=af.value,
                        scope=af.scope,
                        reason="conflicts_with_authoritative_true",
                        conflicting_fact=authoritative_fact,
                        rationale=af.rationale,
                        provenance_reference=af.provenance_reference,
                        assumption_metadata=MappingProxyType(dict(af.assumption_metadata or {})),
                    )
                    rejected_assumptions.append(rejected)
                    diagnostics.append(
                        {
                            "action": "rejected_assumption",
                            "predicate": p,
                            "subject": s,
                            "target": t,
                            "reason": "conflicts_with_authoritative_true",
                            "conflicting_value": True,
                        }
                    )
                else:
                    diagnostics.append(
                        {
                            "action": "authoritative_fact_preferred",
                            "predicate": p,
                            "subject": s,
                            "target": t,
                            "note": "authoritative fact supersedes redundant assumption",
                        }
                    )
            continue

        # If authoritative fact is None / unknown
        if auth_list:
            authoritative_fact = auth_list[0]
            if not assump_list:
                resolved_facts[key] = authoritative_fact
                continue

        # No conclusive authoritative observation: process declared assumptions
        if assump_list:
            if evaluation_mode == "evidence_only":
                for af in assump_list:
                    rejected = RejectedAssumption(
                        predicate=p,
                        subject=s,
                        target=t,
                        assumption_value=af.value,
                        scope=af.scope,
                        reason="evidence_only_mode_disallows_assumptions",
                        conflicting_fact=None,
                        rationale=af.rationale,
                        provenance_reference=af.provenance_reference,
                        assumption_metadata=MappingProxyType(dict(af.assumption_metadata or {})),
                    )
                    rejected_assumptions.append(rejected)
                continue

            assump_vals = {af.value for af in assump_list}
            if True in assump_vals and False in assump_vals:
                for af in assump_list:
                    rejected = RejectedAssumption(
                        predicate=p,
                        subject=s,
                        target=t,
                        assumption_value=af.value,
                        scope=af.scope,
                        reason="contradictory_assumptions",
                        conflicting_fact=None,
                        rationale=af.rationale,
                        provenance_reference=af.provenance_reference,
                        assumption_metadata=MappingProxyType(dict(af.assumption_metadata or {})),
                    )
                    rejected_assumptions.append(rejected)
                diagnostics.append(
                    {
                        "action": "rejected_contradictory_assumptions",
                        "predicate": p,
                        "subject": s,
                        "target": t,
                    }
                )
                continue

            accepted_assumption = assump_list[0]
            resolved_facts[key] = accepted_assumption
            diagnostics.append(
                {
                    "action": "accepted_assumption",
                    "predicate": p,
                    "subject": s,
                    "target": t,
                    "value": accepted_assumption.value,
                    "scope": accepted_assumption.scope,
                }
            )

    return resolved_facts, tuple(rejected_assumptions), diagnostics


def _evaluate_query_outcome(
    search_result: AttackSearchResult,
    materialized: MaterializedQuery,
    ranking_result: dict[str, Any] | None = None,
    min_effort: dict[str, Any] | None = None,
    best_path: PathResult | None = None,
    all_best_paths: tuple[PathResult, ...] = (),
    optimization_scope: str | None = None,
    binding_diagnostics: Mapping[str, dict[str, Any]] | None = None,
) -> AttackQueryResult:
    if ranking_result is not None and ranking_result.get("rating_coverage") is not None:
        from src.engine.ranking.resolution_service import finalize_generated_rating_coverage

        finalize_generated_rating_coverage(ranking_result["rating_coverage"], ranking_result)
    checkpoint_reached = False
    if materialized.checkpoint_state_predicate is not None:
        chk = materialized.checkpoint_state_predicate
        if chk(materialized.initial_attack_state):
            checkpoint_reached = True
        if not checkpoint_reached:
            for path in search_result.paths:
                if path.final_state and chk(path.final_state):
                    checkpoint_reached = True
                    break
                for step in path.transition_history:
                    step_state = apply_transition(step.result.before, step.result)
                    if chk(step_state):
                        checkpoint_reached = True
                        break
        if not checkpoint_reached:
            for attempt in search_result.attempts:
                if attempt.status == Status.APPLICABLE:
                    attempt_state = apply_transition(attempt.before, attempt)
                    if chk(attempt_state):
                        checkpoint_reached = True
                        break
                elif chk(attempt.before):
                    checkpoint_reached = True
                    break

    final_goal_reached = len(search_result.paths) > 0

    if final_goal_reached:
        status = "success"
    elif search_result.truncated or not search_result.complete:
        # Bounded search truncation cannot make terminal no-path/blocked claims (#205)
        status = "truncated"
    elif any(attempt.status == Status.INDETERMINATE for attempt in search_result.attempts):
        # Conservative lattice: indeterminate route is still potentially viable under unknown facts;
        # cannot be concluded as blocked even if other dead-end routes are blocked.
        if checkpoint_reached:
            status = "checkpoint_reached_final_goal_indeterminate"
        else:
            status = "indeterminate"
    elif any(attempt.status == Status.BLOCKED for attempt in search_result.attempts):
        if checkpoint_reached:
            status = "checkpoint_reached_final_goal_blocked"
        else:
            status = "blocked"
    else:
        if checkpoint_reached:
            status = "checkpoint_reached_final_goal_no_path"
        else:
            status = "no_path"

    result = AttackQueryResult(
        search_result=search_result,
        materialized_query=materialized,
        checkpoint_reached=checkpoint_reached,
        final_goal_reached=final_goal_reached,
        status=status,
        ranking_result=ranking_result,
        min_effort=min_effort,
        best_path=best_path,
        all_best_paths=all_best_paths,
        optimization_scope=optimization_scope,
        binding_diagnostics=(
            MappingProxyType(dict(binding_diagnostics))
            if binding_diagnostics is not None
            else MappingProxyType({})
        ),
    )
    if (
        not final_goal_reached
        and search_result.complete
        and not any(a.status == Status.INDETERMINATE for a in search_result.attempts)
        and result.semantic_coverage_gaps
    ):
        result = replace(result, status="unsupported")
    # Min-Effort and Top-K share the same canonical program/tie policy. Do not
    # derive C from hops or restrict effort selection to the C/P/I frontier.
    from src.engine.top_k import effort_programs, select_top_k

    if min_effort is not None and search_result.paths and search_result.paths[0].transition_history:
        programs, _ = effort_programs(result)
        if programs:
            first = programs[0]
            tied = [p for p in programs if p["effort"] == first["effort"]]
            paths_by_id = {
                f"generated_{i:04d}": path for i, path in enumerate(search_result.paths, 1)
            }
            min_effort.update(
                best_candidate_id=first["candidate_id"],
                minimum_effort_value=first["effort"],
                all_best_candidate_ids=[p["candidate_id"] for p in tied],
                tie_count=len(tied),
                associated_likelihood_interval=first["likelihood_interval"],
                associated_impact=first["impact"],
            )
            result = replace(
                result,
                best_path=replace(paths_by_id[first["candidate_id"]], cost=float(first["effort"])),
                all_best_paths=tuple(
                    replace(paths_by_id[p["candidate_id"]], cost=float(p["effort"])) for p in tied
                ),
            )
    if materialized.top_k is not None:
        result = replace(result, top_k_result=select_top_k(result, materialized.top_k))
    return result


def materialize_query(
    query: Mapping[str, Any] | AttackQuery,
    graph: EngineGraph | Mapping[str, Any] | None = None,
    *,
    aliases: Mapping[str, str] | None = None,
    evaluation_mode: str | None = None,
    active_scope: str | None = None,
    action_bindings: Mapping[tuple[str, str, str, str], str] | None = None,
    ranking_query: Mapping[str, Any] | None = None,
) -> MaterializedQuery:
    """Public materialization entry point for Week 4 queries.

    Converts raw query specification into typed MaterializedQuery without requiring
    an ordered attack path:
    1. Resolves aliases and principal references to canonical IDs against graph nodes.
    2. Resolves facts and declared assumptions enforcing known-false vetoes within scope.
    3. Separates source foothold from usable identities (Invariant 1).
    4. Preserves context-scoped usable identity tuples (Invariant 5).
    5. Validates target asset and decouples it from success state predicate (Invariant 6 & 7).
    """
    if isinstance(query, AttackQuery):
        q_dict = {k: getattr(query, k) for k in query.__dataclass_fields__}
    elif isinstance(query, Mapping):
        q_dict = dict(query)
    else:
        raise TypeError(f"query must be AttackQuery or Mapping, got {type(query)!r}")

    top_k = q_dict.get("top_k")
    from src.engine.search import validate_search_order

    search_order = q_dict.get("search_order", "fifo")
    validate_search_order(search_order)
    if top_k is not None or (isinstance(query, Mapping) and "top_k" in query):
        from src.engine.top_k import validate_k

        validate_k(top_k)

    eval_mode = (
        evaluation_mode
        if evaluation_mode is not None
        else q_dict.get("evaluation_mode", "scenario")
    )
    if eval_mode not in VALID_EVALUATION_MODES:
        raise ValueError(
            f"invalid evaluation_mode: {eval_mode!r}; "
            f"allowed modes: {sorted(VALID_EVALUATION_MODES)}"
        )

    # 1. Resolve Graph reference
    resolved_graph = graph or q_dict.get("graph")
    if resolved_graph is None:
        raise ValueError("graph is required either as argument or in query specification")

    if isinstance(resolved_graph, EngineGraph):
        # Identity resolution reads nodes only. Copying all directory edges here
        # made every source/goal query pay for an unused full graph serialization.
        canonical_graph = {"nodes": resolved_graph.nodes()}
    elif isinstance(resolved_graph, Mapping):
        canonical_graph = dict(resolved_graph)
    else:
        raise TypeError(f"unsupported graph type: {type(resolved_graph)!r}")

    nodes = {node["id"]: node for node in canonical_graph.get("nodes", [])}

    # 2. Setup Identity Resolver
    combined_aliases = {}
    if aliases:
        combined_aliases.update(aliases)
    if q_dict.get("aliases"):
        combined_aliases.update(q_dict["aliases"])
    resolver = IdentityResolver(nodes, combined_aliases)

    # 3. Source Foothold vs Initial Actor (Invariant 1)
    source_foothold_raw = (
        q_dict.get("source_foothold") or q_dict.get("source") or q_dict.get("foothold_node_id")
    )
    initial_actor_raw = q_dict.get("initial_actor") or q_dict.get("actor")

    if not source_foothold_raw and not initial_actor_raw:
        raise ValueError("query requires source_foothold or initial_actor")

    canonical_foothold = resolver.resolve(source_foothold_raw) if source_foothold_raw else None
    canonical_actor = (
        resolver.resolve(initial_actor_raw) if initial_actor_raw else canonical_foothold
    )

    if canonical_actor not in nodes:
        raise KeyError(f"unknown attack actor node ID: {canonical_actor}")

    # 4. Initial State Materialization (Invariant 1 & 2)
    raw_initial_state = q_dict.get("initial_state") or q_dict.get("initial_capabilities")
    if raw_initial_state is not None:
        initial_attack_state = _state_from_spec(raw_initial_state, resolver)
    else:
        if canonical_foothold is not None:
            initial_attack_state = AttackState(control=frozenset([canonical_foothold]))
        else:
            initial_attack_state = AttackState(control=frozenset([canonical_actor]))

    # Strict Invariant 1 enforcement:
    # If source foothold is Computer and actor is User, User MUST have
    # explicit usable_identity or control capability.
    if (
        canonical_foothold is not None
        and nodes.get(canonical_foothold, {}).get("kind") == "Computer"
        and nodes.get(canonical_actor, {}).get("kind") == "User"
        and canonical_actor not in initial_attack_state.control
        and not any(u == canonical_actor for u, _ in initial_attack_state.usable_identity)
        and not any(
            a.owner == canonical_actor
            and a.context == resolver.resolve(q_dict.get("authentication_context"))
            for a in initial_attack_state.recovered_secret
            if q_dict.get("authentication_context")
        )
    ):
        raise ValueError(
            f"source foothold is computer {source_foothold_raw!r} but initial actor is "
            f"domain user {initial_actor_raw!r} without declared usable_identity or control"
        )

    # 5. Authentication Context (Invariant 5)
    auth_ctx_raw = q_dict.get("authentication_context")
    canonical_auth_context = resolver.resolve(auth_ctx_raw) if auth_ctx_raw else None

    # 6. Fact and Assumption Resolution (Invariant 3 & 4)
    raw_facts = q_dict.get("runtime_facts") or ()
    raw_assumptions = q_dict.get("assumptions") or q_dict.get("declared_assumptions") or ()
    eff_scope = active_scope if active_scope is not None else q_dict.get("active_scope")

    resolved_facts, rejected_assumptions, fact_diagnostics = resolve_scenario_facts(
        raw_facts,
        raw_assumptions,
        resolver,
        evaluation_mode=eval_mode,
        active_scope=eff_scope,
    )

    withheld_raw = q_dict.get("withheld_relationships") or ()
    withheld_relationships = frozenset(
        StructuralRelationship(
            resolver.resolve(rel.source),
            rel.kind,
            resolver.resolve(rel.target),
        )
        if isinstance(rel, StructuralRelationship)
        else StructuralRelationship(
            resolver.resolve(rel[0]),
            rel[1],
            resolver.resolve(rel[2]),
        )
        for rel in withheld_raw
    )

    raw_rbcd = q_dict.get("rbcd_bindings", ())
    if len(raw_rbcd) > 1:
        raise ValueError("supported RBCD scope enforces at most one delegation binding per query")

    fallback_facts = None
    policy_metadata = q_dict.get("scenario_policy_metadata") or {}
    if eval_mode == "scenario" and policy_metadata.get("profile_id") in {
        "neo-standard-v1",
        "neo-host-session-v1",
    }:
        from src.engine.semantics.scenario_policy import (
            PolicyAssumptionResolver,
            load_policy_profile,
        )

        if not isinstance(policy_metadata.get("profile"), Mapping):
            raise ValueError("Neo scenario policy definition is missing")
        profile = load_policy_profile(policy_metadata["profile"])
        if profile.profile_id != policy_metadata[
            "profile_id"
        ] or profile.digest() != policy_metadata.get("profile_digest"):
            raise ValueError("Neo scenario policy definition/digest mismatch")
        fallback_facts = PolicyAssumptionResolver(
            graph,
            q_dict,
            profile,
            overrides=policy_metadata.get("applied_overrides", ()),
            allowed_predicates=frozenset(
                {
                    "security_group",
                    "membership_usable",
                    "membership_change_allowed",
                    "directory_write_allowed",
                    # Existing reset rules must also follow acquired identities.
                    "password_policy_accepts",
                    "network_rpc_reachable",
                }
                | (
                    {
                        "session_fresh",
                        "session_present",
                        "credential_accessible",
                        "session_identity_usable",
                        "network_kdc_reachable",
                        "authentication_accepted",
                        "admin_channel",
                        "winrm_available",
                    }
                    if profile.profile_id == "neo-host-session-v1"
                    else set()
                )
            ),
        )

    runtime_context = RuntimeContext(
        facts=resolved_facts,
        fallback_facts=fallback_facts,
        authentication_context=canonical_auth_context,
        withheld_relationships=withheld_relationships,
        rbcd_bindings=tuple(
            (b if isinstance(b, DelegationBinding) else DelegationBinding(**b)).resolve(resolver)
            for b in raw_rbcd
        ),
    )

    # 7. Target Asset and Success Predicate Validation (Invariant 6 & Case G)
    target_raw = q_dict.get("target") or q_dict.get("target_asset") or q_dict.get("target_asset_id")
    target_goal = q_dict.get("target_goal") or q_dict.get("goal")
    explicit_success_predicate = q_dict.get("success_state_predicate")
    if explicit_success_predicate is not None and not callable(explicit_success_predicate):
        raise TypeError("success_state_predicate must be callable")

    if target_raw is None and target_goal is not None and isinstance(target_goal, Mapping):
        target_raw = target_goal.get("target")

    if not target_raw:
        raise ValueError("query requires an explicit target asset")

    canonical_target = resolver.resolve(target_raw)
    if canonical_target not in nodes:
        raise KeyError(f"unknown target asset node ID: {canonical_target}")

    if target_goal is None and explicit_success_predicate is None:
        raise ValueError(
            "query requires an explicit success state predicate or target_goal "
            "(Invariant 6: target asset reached does not imply success compromise)"
        )

    semantic_goal = None
    if target_goal is not None:
        if not isinstance(target_goal, Mapping):
            raise TypeError("target_goal must be a Mapping")
        goal_target = resolver.resolve(target_goal.get("target", ""))
        if goal_target != canonical_target:
            raise ValueError(
                f"target_goal target {target_goal.get('target')!r} does not match "
                f"query target {target_raw!r}"
            )
        semantic_goal = _materialize_goal(
            target_goal, canonical_target, resolver, canonical_auth_context
        )
        goal_pred = semantic_goal.matches

        if explicit_success_predicate is not None:
            # Conjunction (AND): both declared required_state and callable must hold
            # so callable cannot bypass or override declared required_state
            def conjunct_goal_predicate(
                state: AttackState,
                gp=goal_pred,
                ep=explicit_success_predicate,
            ) -> bool:
                return gp(state) and ep(state)

            success_state_predicate = conjunct_goal_predicate
        else:
            success_state_predicate = goal_pred
    else:
        success_state_predicate = explicit_success_predicate

    def target_predicate(node: dict[str, Any]) -> bool:
        return node["id"] == canonical_target

    # 8. Checkpoint Predicate (Invariant 7)
    checkpoint_predicate = q_dict.get("checkpoint_state_predicate")
    checkpoint_goal = q_dict.get("checkpoint_goal")
    if checkpoint_predicate is not None and not callable(checkpoint_predicate):
        raise TypeError("checkpoint_state_predicate must be callable")
    if checkpoint_goal is not None:
        if not isinstance(checkpoint_goal, Mapping):
            raise TypeError("checkpoint_goal must be a Mapping")
        checkpoint_target = resolver.resolve(checkpoint_goal.get("target", ""))
        checkpoint_descriptor = _materialize_goal(
            checkpoint_goal, checkpoint_target, resolver, canonical_auth_context
        )
        explicit_checkpoint_predicate = checkpoint_predicate

        def default_chk_predicate(state: AttackState) -> bool:
            return checkpoint_descriptor.matches(state) and (
                explicit_checkpoint_predicate is None or explicit_checkpoint_predicate(state)
            )

        checkpoint_predicate = default_chk_predicate

    # 9. Budget and Scope
    budget_raw = q_dict.get("budget") or q_dict.get("search_budget")
    if isinstance(budget_raw, SearchBudget):
        budget = budget_raw
    elif isinstance(budget_raw, Mapping):
        budget_dict = {"max_paths": 1000, "max_steps": 12, "max_expansions": 100000}
        budget_dict.update(budget_raw)
        budget = SearchBudget(**budget_dict)
    elif budget_raw is None:
        budget = SearchBudget(max_paths=1000, max_steps=12, max_expansions=100000)
    else:
        raise TypeError(f"budget must be SearchBudget or Mapping, got {type(budget_raw)!r}")

    allowed_techs = q_dict.get("allowed_techniques")
    if allowed_techs is None:
        allowed_techs = q_dict.get("techniques")
    custom_catalog = q_dict.get("catalog")
    catalog = tuple(load_catalog() if custom_catalog is None else custom_catalog)
    catalog_ids = {t.id for t in catalog}

    if allowed_techs is not None:
        if not isinstance(allowed_techs, (list, tuple, set, frozenset)) or any(
            not isinstance(tech, str) or not tech.strip() for tech in allowed_techs
        ):
            raise TypeError("allowed_techniques must be a collection of non-empty technique IDs")
        allowed_ids = set(allowed_techs)
        unknown_techs = allowed_ids - catalog_ids
        if unknown_techs:
            raise ValueError(
                f"unknown technique IDs in allowed_techniques: {sorted(unknown_techs)}"
            )
        catalog = tuple(t for t in catalog if t.id in allowed_ids)

    scenario_ref = q_dict.get("scenario_reference") or q_dict.get("scenario_id")

    # 10. Action bindings and Ranking query
    action_bindings_raw = (
        action_bindings if action_bindings is not None else q_dict.get("action_bindings")
    )
    normalized_action_bindings: dict[tuple[str, str, str, str], str] | None = None
    if action_bindings_raw is not None:
        normalized_action_bindings = _normalize_action_bindings(action_bindings_raw, resolver)

    ranking_query_raw = (
        ranking_query
        if ranking_query is not None
        else (
            q_dict["ranking_query"]
            if q_dict.get("ranking_query") is not None
            else q_dict.get("ranking_payload")
        )
    )
    if ranking_query_raw is not None and not isinstance(ranking_query_raw, Mapping):
        raise TypeError("ranking_query must be a Mapping")

    return MaterializedQuery(
        initial_actor=canonical_actor,
        initial_attack_state=initial_attack_state,
        runtime_context=runtime_context,
        target=canonical_target,
        target_predicate=target_predicate,
        success_state_predicate=success_state_predicate,
        catalog=catalog,
        budget=budget,
        rejected_assumptions=rejected_assumptions,
        diagnostics=tuple(fact_diagnostics),
        scenario_reference=scenario_ref,
        checkpoint_state_predicate=checkpoint_predicate,
        aliases=MappingProxyType(dict(combined_aliases)),
        evaluation_mode=eval_mode,
        active_scope=eff_scope,
        action_bindings=(
            MappingProxyType(normalized_action_bindings)
            if normalized_action_bindings is not None
            else None
        ),
        ranking_query=(
            MappingProxyType(dict(ranking_query_raw)) if ranking_query_raw is not None else None
        ),
        rating_resolution=q_dict.get("rating_resolution"),
        semantic_goal=semantic_goal,
        top_k=top_k,
        search_order=search_order,
    )


def run_attack_query(
    query: Mapping[str, Any] | AttackQuery | MaterializedQuery,
    graph: EngineGraph | Mapping[str, Any] | None = None,
    *,
    aliases: Mapping[str, str] | None = None,
    evaluation_mode: str | None = None,
    active_scope: str | None = None,
    action_bindings: Mapping[tuple[str, str, str, str], str] | None = None,
    ranking_query: Mapping[str, Any] | None = None,
) -> AttackQueryResult:
    """End-to-end public execution path: materialize query and execute stateful search."""
    if isinstance(query, MaterializedQuery):
        materialized = query
        if evaluation_mode is not None and evaluation_mode != materialized.evaluation_mode:
            raise ValueError("evaluation_mode cannot be changed after materialization")
        if active_scope is not None and active_scope != materialized.active_scope:
            raise ValueError("active_scope cannot be changed after materialization")
        resolved_graph = graph
        if resolved_graph is None:
            raise ValueError("graph is required when executing a MaterializedQuery directly")
    else:
        materialized = materialize_query(
            query,
            graph,
            aliases=aliases,
            evaluation_mode=evaluation_mode,
            active_scope=active_scope,
            action_bindings=action_bindings,
            ranking_query=ranking_query,
        )
        query_graph = query.graph if isinstance(query, AttackQuery) else query.get("graph")
        resolved_graph = graph or query_graph

    return materialized.run(
        resolved_graph,
        action_bindings=action_bindings,
        ranking_query=ranking_query,
    )
