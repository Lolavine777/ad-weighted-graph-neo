# Canonical graph engine foundation

`src.engine.EngineGraph.from_canonical` accepts canonical Graph JSON text or a
graph mapping and validates it against the current `configs/contract.yml` before
loading. The engine consumes parser output only; it does not parse collector or
BloodHound formats.

The internal graph is a directed `networkx.MultiDiGraph`. Canonical node IDs are
node keys and canonical edge IDs are multigraph keys. Direction, parallel edges,
provenance, derivation, metadata, and assessments are retained. Public records and
`to_canonical()` return defensive copies. Assessments remain outside the positive
edge set. The structural graph is not mutated during semantic exploration.

## Separate structural and semantic APIs

```text
canonical graph != executable attack path

structural relationship
    + selected technique
    + AttackState
    + RuntimeContext / scenario assumptions
    -> TransitionResult

applicable TransitionResult
    -> apply_transition()
    -> new branch-local AttackState
    -> candidate attack path
    -> whole-path evaluator (#143)
```

The existing `src.engine.semantics` layer is the semantic source of truth.
`generate_attack_paths` uses its `Technique`, `TransitionRequest`, `Status`,
`TransitionResult`, `evaluate`, `AttackState`, `RuntimeContext`, and
`apply_transition` APIs. It does not define a competing transition status model.
Each branch carries immutable state, transition results, exact canonical edge
records where a selected relationship is observed, the runtime context, and an
optional scenario reference. A path's `nodes` sequence starts with the actor and
then lists each transition target; each transition's exact actor/source/target is
also present in its `TransitionRequest`.

Only `Status.APPLICABLE` advances a branch. Blocked and indeterminate results are
retained in `AttackSearchResult.attempts` and do not add effects. Transition history
contains full results, including technique, before-state, additions, satisfied, failed,
and unknown predicates, as well as granular `decisions` (`PrerequisiteDecision`).
The helpers `assumption_backed_facts`, `evidence_backed_facts`, and `is_assumption_backed`
provide direct auditability into whether a transition relies on optimistic assumptions.
`final_state` records the branch's final immutable state.

Structural paths use the separately named `generate_structural_paths`. They are
topology candidates only and carry no semantic state. Structural reachability and
structural paths do not establish attack feasibility.

## Derived relationships and evidence boundary

Relationships added by an applicable transition remain in branch-local
`AttackState.relationship_added`/`permission`. Later transitions may use those
relationships through the existing semantic evaluator; `TransitionStep` records
the originating transition index and has no canonical edge ID for a derived
relationship. Derived state is hypothetical, not observed structural evidence.
It never gets inserted into `EngineGraph` and never receives fabricated edge
provenance.

Runtime facts are represented as `RuntimeFact` with explicit origins (`FactOrigin`):
`OBSERVED_EVIDENCE`, `DECLARED_ASSUMPTION`, `TECHNICAL_RULE`, `BLOCKED_EVIDENCE`,
`UNSPECIFIED`, or `UNKNOWN`. Legacy bare boolean facts in `RuntimeContext` are normalized
with `FactOrigin.UNSPECIFIED` so they do not manufacture evidence or assumption provenance.
`DECLARED_ASSUMPTION` facts require explicit, non-empty `scope` and `rationale`.
Existing snapshot evidence and runtime false facts continue to be interpreted by the
semantic evaluator; assumptions do not override a known-false snapshot value (e.g. disabled
accounts or telemetry vetoes fail closed as `BLOCKED_EVIDENCE`). An `UNKNOWN`-origin fact
never satisfies a prerequisite even if its value is declared true.

This is predictive modeling, not live attack execution or monitoring. The engine
does not execute techniques, invent runtime state, or claim that a modeled
transition occurred.

## Search bounds and additive reference utility

Both path expansion APIs require a `SearchBudget` with positive `max_paths`,
`max_steps`, and `max_expansions`. Simple path/transition enumeration can grow
exponentially; callers must choose finite bounds.

Structural path search returns `StructuralSearchResult` containing `paths`,
`expansions`, `truncated`, and `truncation_reason` (`"step_limit_reached"`,
`"expansion_limit_reached"`, or `"path_limit_reached"`). Callers inspect
`result.complete` (or `not result.truncated`) to distinguish true topological
non-reachability (`paths == ()` and `complete is True`) from search budget
exhaustion (`truncated is True`). `StructuralSearchResult` implements container,
indexing, length, and iteration protocols.

Stateful semantic expansion returns `AttackSearchResult` with candidates, evaluated
transition attempts, expansion count, `truncated` flag, and `truncation_reason`.
Empty `paths` means no applicable candidate was found within the explored budget;
check `truncated` to distinguish budget exhaustion.

`shortest_path` is a separate Dijkstra reference utility over structural edges.
Its `AdditiveCostFn(edge, scenario_context)` does not receive path history. The
callback must return finite, non-negative additive costs with Dijkstra's
optimal-substructure property. Equal costs are resolved by the lexicographic
sequence of `(next node ID, canonical edge ID)`. `edge_weight_cost` and `unit_cost`
are reference choices only. This utility does not check semantic applicability,
does not support history-dependent costs, and is not a production path ranking.

## Whole-path evaluator

`evaluate_path(path, evaluator, scenario_context, target_context)` passes an
isolated complete path, scenario context, and target context to a caller-owned
evaluator and returns its assessment unchanged. The evaluator can inspect the
exact transition history and final state. The engine synthesizes no success
likelihood, impact, risk, uncertainty, or ranking. This is the integration point
for the accepted #143 whole-path model; the graph loader needs no changes.

Production ranking remains pending #143. This foundation does not claim global
attack-path optimality. BloodHound runtime and complete SEAMLESS end-to-end data
are not dependencies.
