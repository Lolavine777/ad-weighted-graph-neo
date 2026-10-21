"""Canonical graph boundary and generic candidate path-search foundation."""

from .graph import EngineGraph
from .query import (
    AttackQuery,
    AttackQueryResult,
    MaterializedQuery,
    RejectedAssumption,
    SemanticGoalDescriptor,
    UsableIdentityEntitlementGoal,
    materialize_query,
    resolve_scenario_facts,
    run_attack_query,
)
from .search import (
    AttackSearchResult,
    PathResult,
    SearchBudget,
    StructuralSearchResult,
    TransitionStep,
    edge_weight_cost,
    evaluate_path,
    generate_attack_paths,
    generate_structural_paths,
    shortest_path,
    unit_cost,
)

__all__ = [
    "AttackQuery",
    "AttackQueryResult",
    "AttackSearchResult",
    "EngineGraph",
    "MaterializedQuery",
    "PathResult",
    "RejectedAssumption",
    "SearchBudget",
    "SemanticGoalDescriptor",
    "UsableIdentityEntitlementGoal",
    "StructuralSearchResult",
    "TransitionStep",
    "edge_weight_cost",
    "evaluate_path",
    "generate_attack_paths",
    "generate_structural_paths",
    "materialize_query",
    "resolve_scenario_facts",
    "run_attack_query",
    "shortest_path",
    "unit_cost",
]
