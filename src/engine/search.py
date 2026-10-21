"""Separate structural traversal, semantic state expansion, and reference Dijkstra search."""

from __future__ import annotations

import copy
import heapq
import math
from collections import deque
from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from itertools import islice
from typing import Any, Protocol

from src.engine.program_identity import program_key
from src.engine.semantics import (
    AttackState,
    FactOrigin,
    RuntimeContext,
    apply_transition,
    load_catalog,
)
from src.engine.semantics.credentials import artifacts, producers
from src.engine.semantics.evaluator import (
    candidates as semantic_candidates,
)
from src.engine.semantics.evaluator import (
    evaluate as evaluate_semantic_transition,
)
from src.engine.semantics.models import CapabilityRelationship, StructuralRelationship, Technique
from src.engine.semantics.rbcd import producers as rbcd_producers
from src.engine.semantics.transitions import Status, TransitionRequest, TransitionResult

from .graph import EngineGraph


def validate_search_order(value: str) -> None:
    if value not in ("fifo", "goal_guided", "neo_guided"):
        raise ValueError("search_order must be fifo, goal_guided or neo_guided")


NEO_GUIDED_TECHNIQUES = frozenset(
    {
        "scenario_reset_password",
        "genericall_reset_password",
        "reset_target_password",
        "acquire_reset_identity",
        "propagate_group_entitlement",
        "genericall_add_member",
        "genericall_grant_write_dacl",
        "grant_new_object_right",
        "obtain_admin_execution_on_host",
        "scenario_winrm_admin",
        "open_winrm_remote_session",
    }
)


class _NeoGoalQueue:
    """Greedy topology guidance for core neo techniques; no pruning or cost claims.

    Both branches and their next actions need ordering: a single high-fanout
    branch can otherwise spend the entire budget before the queue is revisited.
    Distances are hints only; semantics still checks every attempted transition.
    """

    def __init__(self, items, relationships, target, catalog):
        kinds = {str(t.relationship) for t in catalog}
        reverse = {}
        for relation in relationships:
            if relation.kind in kinds:
                reverse.setdefault(relation.target, set()).add(relation.source)
        self.distance = {target: 0}
        pending = deque([target])
        while pending:
            node = pending.popleft()
            for child in sorted(reverse.get(node, ())):
                if child not in self.distance:
                    self.distance[child] = self.distance[node] + 1
                    pending.append(child)
        self.heap = []
        self.serial = 0
        for item in items:
            self.append(item)

    def __bool__(self):
        return bool(self.heap)

    def _priority(self, request):
        endpoint = (
            request.source if request.technique_id == "acquire_reset_identity" else request.target
        )
        # Activate an obtained credential before collecting more reset targets.
        phase = 0 if request.technique_id == "acquire_reset_identity" else 1
        return self.distance.get(endpoint, math.inf), phase

    def action_priority(self, candidate):
        _, relation, technique, next_actor, _, _ = candidate
        return self._priority(
            TransitionRequest(technique.id, next_actor, relation.source, relation.target)
        )

    def append(self, item):
        history = item[4]
        if len(item) == 8:
            candidates, start = item[7]
            priority = self.action_priority(candidates[start])
        else:
            priority = self._priority(history[-1].result.request) if history else (math.inf, 1)
        heapq.heappush(self.heap, (*priority, len(history), self.serial, item))
        self.serial += 1

    def popleft(self):
        return heapq.heappop(self.heap)[-1]


class _GoalQueue:
    """Order states by observed membership proximity; never prune or price them."""

    def __init__(self, items, relationships, target, authentication_context):
        reverse = {}
        for relation in relationships:
            if relation.kind == "MemberOf":
                reverse.setdefault(relation.target, set()).add(relation.source)
        self.distance = {target: 0}
        pending = deque([target])
        while pending:
            node = pending.popleft()
            for child in reverse.get(node, ()):
                if child not in self.distance:
                    self.distance[child] = self.distance[node] + 1
                    pending.append(child)
        self.context = authentication_context
        self.heap = []
        self.serial = 0
        for item in items:
            self.append(item)

    def __bool__(self):
        return bool(self.heap)

    def append(self, item):
        state = item[1]
        candidates = [
            (self.distance.get(owner, math.inf), 0)
            for owner, context in state.usable_identity
            if context == self.context
        ] + [(self.distance.get(owner, math.inf), 1) for owner in state.reset_password_control]
        priority = min(candidates, default=(math.inf, 2))
        heapq.heappush(self.heap, (*priority, len(item[4]), self.serial, item))
        self.serial += 1

    def popleft(self):
        return heapq.heappop(self.heap)[-1]


@dataclass(frozen=True)
class SearchBudget:
    """Hard limits for exponential path expansion; all three bounds are required."""

    max_paths: int
    max_steps: int
    max_expansions: int

    def __post_init__(self) -> None:
        if any(type(value) is not int or value < 1 for value in vars(self).values()):
            raise ValueError("search budget limits must be positive integers")


@dataclass(frozen=True)
class TransitionStep:
    """One existing semantics result and its structural or derived relationship identity."""

    result: TransitionResult
    edge_id: str | None
    derived_from_step: int | None


@dataclass(frozen=True)
class PathResult:
    """Auditable path with exact structural edges and optional semantic branch state.

    ``nodes`` is the actor followed by the target of each semantic transition.
    For success already present in initial state, it is the singleton terminal asset.
    Each transition's actual source is preserved by its ``TransitionRequest``.
    ``initial_actor`` retains the canonical query source even for zero-action paths
    or programs whose first request uses another initially usable identity.
    ``goal_target`` identifies a state goal satisfied through another action endpoint.
    It does not change the actual transition targets in ``nodes`` or the action trace.
    ``edges`` contains only observed canonical edges; a ``None`` edge ID in the
    aligned transition history identifies a branch-local derived relationship.
    """

    nodes: tuple[str, ...]
    edges: tuple[dict[str, Any], ...]
    cost: float | None = None
    transition_history: tuple[TransitionStep, ...] = ()
    final_state: AttackState | None = None
    scenario_reference: str | None = None
    runtime_context: RuntimeContext | None = None
    initial_actor: str | None = None
    goal_target: str | None = None

    @property
    def target(self) -> str:
        return self.goal_target if self.goal_target is not None else self.nodes[-1]

    @property
    def transition_edge_ids(self) -> tuple[str | None, ...]:
        return tuple(step.edge_id for step in self.transition_history)


@dataclass(frozen=True)
class StructuralSearchResult:
    """Bounded structural search result separating unreachable targets from budget truncation."""

    paths: tuple[PathResult, ...]
    expansions: int
    truncated: bool
    truncation_reason: str | None = None

    @property
    def complete(self) -> bool:
        """True when the search exhausted candidate paths without hitting any budget limit."""
        return not self.truncated

    def __iter__(self):
        return iter(self.paths)

    def __len__(self) -> int:
        return len(self.paths)

    def __getitem__(self, index: int | slice) -> PathResult | tuple[PathResult, ...]:
        return self.paths[index]

    def __bool__(self) -> bool:
        return bool(self.paths)


@dataclass(frozen=True)
class AttackSearchResult:
    """Completed candidates plus evaluated non-applicable/applicable diagnostics."""

    paths: tuple[PathResult, ...]
    attempts: tuple[TransitionResult, ...]
    expansions: int
    truncated: bool
    truncation_reason: str | None = None

    @property
    def complete(self) -> bool:
        """True when search exhausted candidate paths without hitting any budget limit."""
        return not self.truncated

    def __iter__(self):
        return iter(self.paths)

    def __len__(self) -> int:
        return len(self.paths)

    def __getitem__(self, index: int | slice) -> PathResult | tuple[PathResult, ...]:
        return self.paths[index]

    def __bool__(self) -> bool:
        return bool(self.paths)


class AdditiveCostFn(Protocol):
    """Edge-local additive increment; path history is deliberately not exposed."""

    def __call__(self, edge: Mapping[str, Any], scenario_context: Any) -> float: ...


class PathEvaluator(Protocol):
    """Assess a complete path; the returned model belongs to the caller (#143)."""

    def __call__(self, path: PathResult, scenario_context: Any, target_context: Any) -> Any: ...


def edge_weight_cost(edge: Mapping[str, Any], _scenario_context: Any) -> float:
    """Reference additive cost only: use canonical edge weight."""
    return float(edge["weight"])


def unit_cost(_edge: Mapping[str, Any], _scenario_context: Any) -> float:
    """Reference additive cost only: count each edge as one."""
    return 1.0


def generate_structural_paths(
    graph: EngineGraph,
    source: str,
    target: str,
    *,
    budget: SearchBudget,
) -> StructuralSearchResult:
    """Enumerate bounded simple topology paths; results do not imply feasibility."""
    graph.node(source)
    graph.node(target)
    if source == target:
        return StructuralSearchResult(
            paths=(PathResult((source,), ()),),
            expansions=0,
            truncated=False,
            truncation_reason=None,
        )

    found: list[PathResult] = []
    pending = deque([(source, (source,), ())])
    expansions = 0
    truncated = False
    truncation_reason: str | None = None

    while pending:
        if len(found) >= budget.max_paths:
            truncated = True
            truncation_reason = "path_limit_reached"
            break
        if expansions >= budget.max_expansions:
            truncated = True
            truncation_reason = "expansion_limit_reached"
            break

        current, nodes, edges = pending.popleft()
        outgoing = graph._outgoing(current)

        for idx, edge in enumerate(outgoing):
            if expansions >= budget.max_expansions:
                truncated = True
                if truncation_reason is None:
                    truncation_reason = "expansion_limit_reached"
                break

            expansions += 1
            next_node = edge["target"]
            if next_node in nodes:
                continue

            next_nodes = nodes + (next_node,)
            next_edges = edges + (edge,)

            if next_node == target:
                found.append(PathResult(next_nodes, next_edges))
                if len(found) >= budget.max_paths:
                    has_more = (idx + 1 < len(outgoing)) or bool(pending)
                    if has_more:
                        truncated = True
                        if truncation_reason is None:
                            truncation_reason = "path_limit_reached"
                    break
            else:
                if len(next_edges) < budget.max_steps:
                    pending.append((next_node, next_nodes, next_edges))
                else:
                    has_unvisited = any(
                        e["target"] not in next_nodes for e in graph._outgoing(next_node)
                    )
                    if has_unvisited:
                        truncated = True
                        if truncation_reason is None:
                            truncation_reason = "step_limit_reached"

        if truncated and (len(found) >= budget.max_paths or expansions >= budget.max_expansions):
            break

    return StructuralSearchResult(
        paths=tuple(found),
        expansions=expansions,
        truncated=truncated,
        truncation_reason=truncation_reason,
    )


def branch_action_candidates(
    nodes: dict[str, dict[str, Any]],
    state: AttackState,
    current_actor: str,
    initial_actor: str,
    runtime_context: RuntimeContext,
    relationships_by_source: dict[str, set[Any]],
    selected_catalog: Sequence[Technique],
    used: frozenset[tuple[Any, str, str]],
) -> Iterator[tuple[str, Any, Technique, str, tuple[Any, str, str], dict[str, Any]]]:
    """Enumerate action candidates for a branch across all eligible actors (#294)."""
    eligible_actors = {initial_actor} if initial_actor in nodes else set()
    if runtime_context.authentication_context is not None:
        for user, scope in state.usable_identity:
            if scope == runtime_context.authentication_context and user in nodes:
                eligible_actors.add(user)
    ordered_actors = (
        (current_actor,) + tuple(a for a in sorted(eligible_actors) if a != current_actor)
        if current_actor in eligible_actors
        else tuple(sorted(eligible_actors))
    )
    seen_in_branch = set()
    for sched_actor in ordered_actors:
        sources = {sched_actor} | {
            group for user, group in state.effective_member if user == sched_actor
        }
        relationships = set().union(
            *(relationships_by_source.get(source, set()) for source in sources)
        )
        relationships.update(
            rel
            for host in state.admin_control
            for rel in relationships_by_source.get(host, ())
            if rel.kind == "HasSession"
        )
        relationships.update(producers(nodes, state, sched_actor, runtime_context))
        relationships.update(rbcd_producers(nodes, state, sched_actor, runtime_context))
        relationships.update(state.relationship_added)
        relationships.update(state.permission)
        relationships.update(runtime_context.withheld_relationships)
        if runtime_context.authentication_context is not None:
            relationships.update(
                CapabilityRelationship(
                    user, "AuthenticationControl", runtime_context.authentication_context
                )
                for user in state.reset_password_control
                if (user, runtime_context.authentication_context) not in state.usable_identity
            )
        sorted_relationships = sorted(
            relationships,
            key=lambda rel: (
                rel.source,
                rel.kind,
                rel.target,
                repr(getattr(rel, "binding", None)),
            ),
        )
        for relationship in sorted_relationships:
            source_node = nodes.get(relationship.source)
            target_node = nodes.get(relationship.target)
            if source_node is None or target_node is None:
                continue
            if relationship.kind not in {
                "AuthenticationControl",
                "RecoveredSecret",
                "HasSession",
            } and not (
                relationship.source == sched_actor
                or (sched_actor, relationship.source) in state.effective_member
            ):
                continue
            if relationship.kind == "HasSession" and relationship.source not in state.admin_control:
                continue
            options = semantic_candidates(
                relationship.kind,
                source_node["kind"],
                target_node["kind"],
                selected_catalog,
            )
            for technique in options:
                next_actor = (
                    relationship.source
                    if relationship.kind in {"AuthenticationControl", "RecoveredSecret"}
                    else sched_actor
                )
                action_key = (relationship, technique.id, next_actor)
                if action_key in seen_in_branch or action_key in used:
                    continue
                seen_in_branch.add(action_key)
                yield (
                    sched_actor,
                    relationship,
                    technique,
                    next_actor,
                    action_key,
                    target_node,
                )


def generate_attack_paths(
    graph: EngineGraph,
    actor: str,
    *,
    initial_state: AttackState,
    runtime_context: RuntimeContext,
    target_predicate: Callable[[dict[str, Any]], bool],
    budget: SearchBudget,
    success_state_predicate: Callable[[AttackState], bool] | None = None,
    scenario_reference: str | None = None,
    catalog: Sequence[Technique] | None = None,
    search_order: str = "fifo",
) -> AttackSearchResult:
    """Expand branch-local AttackState using the repository's existing semantics API.

    Canonical edges and relationships in the branch state are considered separately.
    Every candidate technique is evaluated through semantics ``evaluate`` and only
    ``Status.APPLICABLE`` results advance via ``apply_transition``. Derived relations
    are references in AttackState only; they never enter EngineGraph.

    ``target_predicate`` identifies the target asset. When
    ``success_state_predicate`` is supplied, reaching that node is only terminal when
    the resulting AttackState also satisfies the declared success condition. This avoids
    treating an intermediate transition that happens to target the asset as compromise.
    If the initial state already satisfies that state-only predicate, zero-action
    success requires a unique matching target; multiple matches raise ``ValueError``
    because the predicate cannot establish which asset is already satisfied.
    """
    validate_search_order(search_order)
    # EngineGraph has already validated the exact graph/facts binding. Reuse its
    # owned semantic view, while keeping callback-visible nodes isolated.
    evaluation_graph = graph.to_prepared()
    nodes = {node["id"]: node for node in graph.nodes()}
    if actor not in nodes:
        raise KeyError(f"unknown attack actor node ID: {actor}")
    unspecified_keys = sorted(
        key for key, fact in runtime_context.facts.items() if fact.origin is FactOrigin.UNSPECIFIED
    )
    if unspecified_keys:
        raise ValueError(
            "generate_attack_paths requires auditable typed runtime facts; "
            f"UNSPECIFIED facts are not authoritative: {unspecified_keys}"
        )
    selected_catalog = load_catalog() if catalog is None else tuple(catalog)
    state_goal_targets = (
        sorted(node_id for node_id, node in nodes.items() if target_predicate(node))
        if success_state_predicate is not None
        else []
    )
    # A declared security goal can already hold before any predicted action.
    # The singleton node identifies the terminal asset for this zero-action path.
    if success_state_predicate is not None and success_state_predicate(initial_state):
        initial_targets = state_goal_targets
        if len(initial_targets) > 1:
            raise ValueError(
                "zero-action success requires a unique target_predicate match; "
                "success_state_predicate is state-only and cannot attribute success "
                "to multiple targets"
            )
        if initial_targets:
            return AttackSearchResult(
                (
                    PathResult(
                        (initial_targets[0],),
                        (),
                        final_state=initial_state,
                        scenario_reference=scenario_reference,
                        runtime_context=runtime_context,
                        initial_actor=actor,
                    ),
                ),
                (),
                0,
                False,
                None,
            )
    edge_by_relationship = {
        StructuralRelationship(edge["source"], edge["kind"], edge["target"]): edge
        for edge in (
            graph._edges_by_id.values() if graph._edges_by_id is not None else graph.edges()
        )
    }

    relationships_by_source = {}
    for relation in edge_by_relationship:
        relationships_by_source.setdefault(relation.source, set()).add(relation)
        if (
            relation.kind == "GenericAll"
            and nodes[relation.source]["kind"] == "Group"
            and nodes[relation.target]["kind"] == "Computer"
        ):
            relationships_by_source[relation.source].add(
                CapabilityRelationship(relation.source, "DeclaredHostAdmin", relation.target)
            )

    # actor, state, target-sequence, observed edges, transition trace, used actions,
    # and the transition that first introduced each derived relationship.
    initial = [(actor, initial_state, (actor,), (), (), frozenset(), {})]
    if search_order == "neo_guided":
        targets = [n for n in nodes.values() if target_predicate(n)]
        if len(targets) != 1 or not {t.id for t in selected_catalog} <= NEO_GUIDED_TECHNIQUES:
            raise ValueError("neo_guided requires one target and supported neo techniques")
        pending = _NeoGoalQueue(initial, edge_by_relationship, targets[0]["id"], selected_catalog)
    elif search_order == "goal_guided":
        targets = [n for n in nodes.values() if target_predicate(n)]
        if len(targets) != 1 or targets[0]["kind"] != "Group":
            raise ValueError("goal_guided requires one Group target")
        if not {t.id for t in selected_catalog} <= {
            "scenario_reset_password",
            "acquire_reset_identity",
            "propagate_group_entitlement",
        }:
            raise ValueError("goal_guided currently supports reset/activation/membership only")
        pending = _GoalQueue(
            initial, edge_by_relationship, targets[0]["id"], runtime_context.authentication_context
        )
    else:
        pending = deque(initial)
    paths: list[PathResult] = []
    path_signatures = set()
    attempts: list[TransitionResult] = []
    expansions = 0
    truncated = False
    truncation_reason: str | None = None

    while pending:
        if len(paths) >= budget.max_paths or expansions >= budget.max_expansions:
            truncated = True
            truncation_reason = (
                "path_limit_reached"
                if len(paths) >= budget.max_paths
                else "expansion_limit_reached"
            )
            break
        branch = pending.popleft()
        current_actor, state, path_nodes, path_edges, history, used, origins = branch[:7]
        if len(history) >= budget.max_steps:
            has_candidates = any(
                True
                for _ in branch_action_candidates(
                    nodes,
                    state,
                    current_actor,
                    actor,
                    runtime_context,
                    relationships_by_source,
                    selected_catalog,
                    used,
                )
            )
            if has_candidates:
                truncated = True
                if truncation_reason is None:
                    truncation_reason = "step_limit_reached"
            continue

        if len(branch) == 8:
            candidates, start_index = branch[7]
        else:
            candidates = list(
                branch_action_candidates(
                    nodes,
                    state,
                    current_actor,
                    actor,
                    runtime_context,
                    relationships_by_source,
                    selected_catalog,
                    used,
                )
            )
            start_index = 0
            if search_order == "neo_guided":
                candidates.sort(key=pending.action_priority)
        advanced = False

        for idx, (
            _sched_actor,
            relationship,
            technique,
            next_actor,
            action_key,
            target_node,
        ) in enumerate(islice(candidates, start_index, None), start_index):
            if expansions >= budget.max_expansions:
                truncated = True
                if truncation_reason is None:
                    truncation_reason = "expansion_limit_reached"
                break

            request = TransitionRequest(
                technique.id,
                next_actor,
                relationship.source,
                relationship.target,
                getattr(relationship, "binding", None),
            )
            result = evaluate_semantic_transition(
                evaluation_graph,
                state,
                request,
                runtime_context,
                selected_catalog,
            )
            attempts.append(result)
            expansions += 1
            if result.status is not Status.APPLICABLE:
                continue

            next_state = apply_transition(state, result)
            support = (
                StructuralRelationship(relationship.source, "GenericAll", relationship.target)
                if relationship.kind == "DeclaredHostAdmin"
                else relationship
            )
            relationship_edge = edge_by_relationship.get(support)
            if relationship.kind in {"RBCDReset", "RBCDConfigure"}:
                relationship_edge = next(
                    (
                        edge_by_relationship.get(
                            StructuralRelationship(relationship.source, kind, relationship.target)
                        )
                        for kind in ("GenericAll", "ForceChangePassword")
                        if edge_by_relationship.get(
                            StructuralRelationship(relationship.source, kind, relationship.target)
                        )
                    ),
                    None,
                )
            parent_step = len(history)
            step = TransitionStep(
                result=result,
                edge_id=relationship_edge["id"] if relationship_edge else None,
                derived_from_step=(
                    None
                    if relationship_edge
                    else next(
                        (
                            index
                            for index, prior in reversed(tuple(enumerate(history)))
                            if relationship.source in prior.result.additions.reset_password_control
                        ),
                        origins.get(relationship),
                    )
                ),
            )
            if relationship.kind in {"TicketMaterial", "ASRepMaterial", "RecoveredSecret"}:
                field = (
                    "asrep_material"
                    if relationship.kind == "ASRepMaterial"
                    else "service_ticket_material"
                    if relationship.kind == "TicketMaterial"
                    else "recovered_secret"
                )
                owner = (
                    relationship.target
                    if relationship.kind in {"TicketMaterial", "ASRepMaterial"}
                    else relationship.source
                )
                parent = next(
                    (
                        index
                        for index, prior in reversed(tuple(enumerate(history)))
                        if artifacts(
                            prior.result.additions,
                            field,
                            owner,
                            runtime_context.authentication_context,
                        )
                    ),
                    None,
                )
                step = TransitionStep(result, None, parent)
            elif relationship.kind in {"RBCDPrepare", "RBCDDelegate", "RBCDAsset"}:
                binding = getattr(relationship, "binding", None)
                parent = None
                if relationship.kind == "RBCDPrepare":
                    parent = next(
                        (
                            index
                            for index, prior in reversed(tuple(enumerate(history)))
                            if any(a.binding == binding for a in prior.result.additions.rbcd_secret)
                        ),
                        None,
                    )
                elif relationship.kind == "RBCDDelegate":
                    p_service = next(
                        (
                            index
                            for index, prior in reversed(tuple(enumerate(history)))
                            if any(
                                a.binding == binding
                                for a in prior.result.additions.controlled_service
                            )
                        ),
                        None,
                    )
                    p_descriptor = next(
                        (
                            index
                            for index, prior in reversed(tuple(enumerate(history)))
                            if any(
                                a.binding == binding for a in prior.result.additions.rbcd_descriptor
                            )
                        ),
                        None,
                    )
                    parents = [p for p in (p_service, p_descriptor) if p is not None]
                    parent = max(parents) if parents else None
                elif relationship.kind == "RBCDAsset":
                    parent = next(
                        (
                            index
                            for index, prior in reversed(tuple(enumerate(history)))
                            if any(
                                a.binding == binding
                                for a in prior.result.additions.delegated_context
                            )
                        ),
                        None,
                    )
                step = TransitionStep(result, None, parent)
            next_origins = dict(origins)
            previous_relations = state.relationship_added | state.permission
            new_relationships = (
                next_state.relationship_added | next_state.permission
            ) - previous_relations
            for derived in new_relationships:
                next_origins[derived] = parent_step
            next_history = history + (step,)
            next_nodes = path_nodes + (relationship.target,)
            # Public witnesses must not expose the engine's cached edge records.
            next_edges = path_edges + (
                (copy.deepcopy(relationship_edge),) if relationship_edge else ()
            )
            next_used = used | {action_key}
            target_reached = target_predicate(target_node)
            success_reached = success_state_predicate is None or success_state_predicate(next_state)
            terminal_target = (
                relationship.target
                if target_reached
                else state_goal_targets[0]
                if len(state_goal_targets) == 1
                else None
            )
            if terminal_target is not None and success_reached:
                path = PathResult(
                    next_nodes,
                    next_edges,
                    transition_history=next_history,
                    final_state=next_state,
                    scenario_reference=scenario_reference,
                    runtime_context=runtime_context,
                    initial_actor=actor,
                    goal_target=(
                        terminal_target if terminal_target != relationship.target else None
                    ),
                )
                signature = program_key(path)
                if signature in path_signatures:
                    continue
                path_signatures.add(signature)
                paths.append(path)
                if len(paths) >= budget.max_paths:
                    has_more_in_branch = idx + 1 < len(candidates)
                    has_more_pending = bool(pending)
                    if has_more_in_branch or has_more_pending:
                        truncated = True
                        if truncation_reason is None:
                            truncation_reason = "path_limit_reached"
                    break
            else:
                pending.append(
                    (
                        next_actor,
                        next_state,
                        next_nodes,
                        next_edges,
                        next_history,
                        next_used,
                        next_origins,
                    )
                )
            advanced = True
            if search_order == "neo_guided":
                # Resume siblings later rather than spending the whole budget
                # on one high-fanout state before visiting a useful child.
                if idx + 1 < len(candidates):
                    pending.append((*branch[:7], (candidates, idx + 1)))
                break

        if expansions >= budget.max_expansions:
            if bool(pending):
                truncated = True
                if truncation_reason is None:
                    truncation_reason = "expansion_limit_reached"

        if expansions >= budget.max_expansions or len(paths) >= budget.max_paths:
            break

        if len(history) >= budget.max_steps and advanced:
            truncated = True
            if truncation_reason is None:
                truncation_reason = "step_limit_reached"

    return AttackSearchResult(
        tuple(paths), tuple(attempts), expansions, truncated, truncation_reason
    )


def evaluate_path(
    path: PathResult,
    *,
    evaluator: PathEvaluator,
    scenario_context: Any = None,
    target_context: Any = None,
) -> Any:
    """Pass an isolated complete path to the caller's whole-path evaluator (#143)."""
    immutable_context = path.runtime_context
    memo = {id(immutable_context): immutable_context} if immutable_context is not None else {}
    isolated_path = copy.deepcopy(path, memo)
    return evaluator(isolated_path, scenario_context, target_context)


def shortest_path(
    graph: EngineGraph,
    source: str,
    target: str,
    *,
    cost_fn: AdditiveCostFn = edge_weight_cost,
    scenario_context: Any = None,
) -> PathResult | None:
    """Reference Dijkstra search for finite, non-negative, additive edge costs only.

    This utility exposes no path history to ``cost_fn`` and is not a substitute for
    stateful transition expansion or the whole-path evaluator.
    """
    graph.node(source)
    graph.node(target)
    if source == target:
        return PathResult((source,), (), cost=0.0)
    start_signature: tuple[tuple[str, str], ...] = ()
    queue = [(0.0, start_signature, source, (source,), ())]
    best = {source: (0.0, start_signature)}
    while queue:
        total, signature, current, path_nodes, path_edges = heapq.heappop(queue)
        if best.get(current) != (total, signature):
            continue
        if current == target:
            return PathResult(path_nodes, path_edges, cost=total)
        for edge in graph._outgoing(current):
            next_node = edge["target"]
            if next_node in path_nodes:
                continue
            increment = cost_fn(edge, scenario_context)
            if isinstance(increment, bool) or not isinstance(increment, (int, float)):
                raise ValueError("cost_fn must return a finite non-negative number")
            increment = float(increment)
            if not math.isfinite(increment) or increment < 0:
                raise ValueError("cost_fn must return a finite non-negative number")
            candidate = total + increment
            candidate_signature = signature + ((next_node, edge["id"]),)
            previous = best.get(next_node)
            if previous is None or (candidate, candidate_signature) < previous:
                best[next_node] = candidate, candidate_signature
                heapq.heappush(
                    queue,
                    (
                        candidate,
                        candidate_signature,
                        next_node,
                        path_nodes + (next_node,),
                        path_edges + (edge,),
                    ),
                )
    return None
