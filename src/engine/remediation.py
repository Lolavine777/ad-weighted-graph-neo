"""Immutable intervention boundary and native baseline replay (no rediscovery).

The transport is deliberately remediation-replay/1, not a complete result 1.1.0.
Only prepare_baseline accepts native queries; replay refuses stale input pins.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass, replace
from pathlib import Path
from types import MappingProxyType

from scripts.research.remediation_acceptance import (
    DOC,
    normalized_program_identity,
    require,
    schema_validate,
    sha,
    validate_request,
)
from src.engine.graph import EngineGraph
from src.engine.program_identity import canonical_json, canonical_value, program_id, program_key
from src.engine.query import run_attack_query
from src.engine.ranking.resolution_service import canonical_digest
from src.engine.search import TransitionStep
from src.engine.semantics import RuntimeContext, apply_transition
from src.engine.semantics.evaluator import PreparedSemanticGraph, evaluate
from src.engine.semantics.models import FactOrigin, RuntimeFact
from src.engine.semantics.transitions import Status
from src.parser.snapshot_facts import SnapshotFact, graph_digest

ROOT = Path(__file__).resolve().parents[2]
SUPPORTED = frozenset({"group-membership", "admin-channel", "admin-revoke", "asrep-preauth"})


class UnsupportedIntervention(ValueError):
    """A valid catalog edit whose semantics are outside this executor's scope."""

    def __init__(self, edit_id, reason):
        self.edit_id, self.reason = edit_id, reason
        super().__init__(f"unsupported intervention {edit_id}: {reason}")


def _value(value):
    return canonical_value(value)


def _digest(value):
    return canonical_digest(_value(value))


def _revision():
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()


def _facts(graph):
    return _value(graph.snapshot_facts.facts) if graph.snapshot_facts else []


def _scope(graph, cells, results):
    queries = [cell["query"] for cell in cells]
    materials = [result.materialized_query for result in results]
    budgets = [_value(m.budget) for m in materials]
    modes = [m.evaluation_mode for m in materials]
    require(all(b == budgets[0] for b in budgets), "cohort requires one search budget")
    require(all(m == modes[0] for m in modes), "cohort requires one evaluation mode")
    return {
        "snapshot_id": graph.metadata["snapshot_id"],
        "graph_digest": _digest(graph.to_canonical()),
        "snapshot_facts_digest": _digest(_facts(graph)),
        "source_manifest_digest": _digest(
            [
                {
                    "source_id": c["source_id"],
                    "actor": m.initial_actor,
                    "initial_state": _value(m.initial_attack_state),
                }
                for c, m in zip(cells, materials, strict=True)
            ]
        ),
        "goal_manifest_digest": _digest(
            [
                {
                    "goal_id": c["goal_id"],
                    "target": m.target,
                    "target_goal": q.get("target_goal"),
                    "semantic_goal": _value(m.semantic_goal),
                }
                for c, q, m in zip(cells, queries, materials, strict=True)
            ]
        ),
        # Full public specifications bind aliases, assumptions, initial state,
        # typed goal, technique allow-list, context, basis and profile together.
        "query_profile_digest": _digest(cells),
        "rating_inputs_digest": _digest(
            [{k: v for k, v in q.items() if "rating" in k or "ranking" in k} for q in queries]
        ),
        "semantic_catalog_digest": sha(ROOT / "configs/attack_semantics.yml"),
        "engine_revision": _revision(),
        "evaluation_mode": modes[0],
        "search_budget": budgets[0],
        "program_identity_version": "semantic-program/1",
        "route_identity_version": "ordered-observed-edges/1",
    }


def _native_digest(results):
    return _digest(
        [
            {
                "paths": [
                    {
                        "program_key": program_key(p),
                        "history": _value(p.transition_history),
                        "runtime_facts": _value(tuple(p.runtime_context.facts.values())),
                    }
                    for p in r.paths
                ],
                "attempts": _value(r.attempts),
                "complete": r.complete,
                "truncated": r.truncated,
                "status": r.status,
            }
            for r in results
        ]
    )


@dataclass(frozen=True)
class ReplayBaseline:
    """Immutable serialized inputs and fingerprints of actual public observations."""

    run_id: str
    cells_json: str
    scope_json: str
    native_digest: str

    @property
    def scope(self):
        return json.loads(self.scope_json)


def prepare_baseline(graph: EngineGraph, cells: list[dict], *, run_id: str) -> ReplayBaseline:
    """Run exact public source×goal queries. Cell IDs are caller manifest labels.

    Each cell has source_id, goal_id and query. No terminal state is accepted as
    an implicit foothold; initial capabilities come only from the public query.
    """
    require(bool(run_id) and bool(cells), "baseline requires run ID and cells")
    cells = json.loads(canonical_json(cells))
    require(all(set(c) == {"source_id", "goal_id", "query"} for c in cells), "invalid cell")
    require(
        all(
            isinstance(c[k], str) and c[k].strip() for c in cells for k in ("source_id", "goal_id")
        ),
        "cell IDs must be nonempty strings",
    )
    cells.sort(key=lambda c: (c["source_id"], c["goal_id"]))
    keys = [(c["source_id"], c["goal_id"]) for c in cells]
    require(len(keys) == len(set(keys)), "duplicate baseline cell")
    require(all(set(c) == {"source_id", "goal_id", "query"} for c in cells), "invalid cell")
    input_digest = _digest([graph.to_canonical(), _facts(graph)])
    results = tuple(run_attack_query(c["query"], graph) for c in cells)
    require(
        input_digest == _digest([graph.to_canonical(), _facts(graph)]),
        "baseline inputs mutated during public query",
    )
    scope = _scope(graph, cells, results)
    return ReplayBaseline(
        run_id, canonical_json(cells), canonical_json(scope), _native_digest(results)
    )


def request_for_baseline(baseline: ReplayBaseline, edits: list[dict], *, request_id: str):
    """Construct the strict request; validation against actual inputs happens in replay."""
    return {
        "schema_version": "1.1.0",
        "request_id": request_id,
        "catalog_id": "ad-remediation/1.0.0",
        "catalog_digest": sha(DOC / "catalog-v1.json"),
        "baseline_run_id": baseline.run_id,
        "scope": baseline.scope,
        "edits": json.loads(canonical_json(edits)),
        "initial_state_policy": "rebuild_same_declared_foothold",
        "conflict_policy": "reject_duplicate_or_conflicting_keys",
        "missing_evidence_policy": "unresolved_no_effect_claim",
    }


@dataclass(frozen=True)
class EffectiveSnapshotFacts:
    """Scenario values with explicit origin, never rewritten historical evidence."""

    baseline: object
    replacements: tuple
    intervention_ref: str
    effective_graph_digest: str

    def validate_binding(self, graph):
        require(
            graph_digest(graph) == self.effective_graph_digest, "effective graph binding mismatch"
        )

    def lookup(self, subject, name):
        for edit_subject, edit_name, value, _edit_id in self.replacements:
            if (subject, name) == (edit_subject, edit_name):
                # The origin lives on this view and in replay audit, not in a
                # fabricated collector FactEvidence record.
                return SnapshotFact(subject, name, "known", value, ())
        return self.baseline.lookup(subject, name)


def _check_edits(request, graph, materials):
    """Validate every edit before constructing or evaluating any effective branch."""
    touched = set()
    for edit in request["edits"]:
        eid = edit["edit_id"]
        if edit["catalog_entry_id"] not in SUPPORTED:
            raise UnsupportedIntervention(eid, "catalog entry has no reviewed executor adapter")
        if edit["kind"] == "deny_relationship":
            edge = graph.edge(edit["edge_id"])
            require(
                {k: edge[k] for k in ("source", "kind", "target")} == edit["relationship"],
                "relationship binding mismatch",
            )
            require(
                _digest(edge["provenance"]) == edit["provenance_digest"],
                "relationship provenance mismatch",
            )
            matches = [
                e
                for e in graph.edges_between(edge["source"], edge["target"])
                if e["kind"] == edge["kind"]
            ]
            require(len(matches) == 1, "effective relationship has unbound additional support")
            key = ("relationship", edge["source"], edge["kind"], edge["target"])
        elif edit["kind"] == "snapshot_fact_replace":
            require(graph.snapshot_facts is not None, "snapshot facts required")
            fact = graph.snapshot_facts.lookup(edit["subject"], edit["name"])
            require(
                fact.status == "known" and fact.value == edit["expected_before"],
                "snapshot expected_before mismatch",
            )
            require(_digest(fact.evidence) == edit["evidence_digest"], "fact evidence pin mismatch")
            key = ("snapshot", edit["subject"], edit["name"])
        else:
            key_spec = edit["key"]
            if key_spec["binding_id"] is not None:
                raise UnsupportedIntervention(eid, "bound runtime facts require a scoped adapter")
            key = (key_spec["predicate"], key_spec["subject"], key_spec["target"])
            matching = [m for m in materials if key in m.runtime_context.facts]
            require(bool(matching), "runtime key is not present in declared baseline cells")
            for m in matching:
                context = m.runtime_context
                require(
                    key_spec["authentication_context"] == context.authentication_context,
                    "runtime authentication context mismatch",
                )
                require(
                    context.facts[key].value is edit["expected_before"],
                    "runtime expected_before mismatch",
                )
                require(
                    context.facts[key].origin != FactOrigin.UNKNOWN,
                    "unknown fact cannot substantiate expected_before",
                )
        require(key not in touched, "overlapping effective edit keys")
        touched.add(key)


def _effective(request, graph, material):
    facts = dict(material.runtime_context.facts)
    # Runtime declarations do not change canonical structure or static facts.
    # Keep their provenance in the new RuntimeContext, and reuse only the
    # graph-owned prepared view. Structural/static overlays retain their checks.
    canonical = (
        graph.to_canonical()
        if any(e["kind"] != "runtime_fact_replace" for e in request["edits"])
        else None
    )
    active, replacements = [], []
    for edit in request["edits"]:
        ref = f"intervention:{request['request_id']}/{edit['edit_id']}"
        if edit["kind"] == "deny_relationship":
            canonical["edges"] = [e for e in canonical["edges"] if e["id"] != edit["edge_id"]]
            active.append(edit["edit_id"])
        elif edit["kind"] == "snapshot_fact_replace":
            replacements.append((edit["subject"], edit["name"], edit["after"], edit["edit_id"]))
            active.append(edit["edit_id"])
        else:
            k = edit["key"]
            key = (k["predicate"], k["subject"], k["target"])
            if key not in facts:
                continue  # A different source's declaration is never imported.
            original = facts[key]
            facts[key] = RuntimeFact(
                *key,
                edit["after"],
                FactOrigin.BLOCKED_EVIDENCE,
                scope=original.scope,
                rationale=edit["rationale"],
                provenance_reference=ref,
                assumption_metadata=MappingProxyType(
                    {
                        "origin": "counterfactual_intervention",
                        "baseline_fact_digest": _digest(original),
                    }
                ),
            )
            active.append(edit["edit_id"])
    if canonical is None:
        prepared = graph.to_prepared()
    else:
        snapshot = graph.snapshot_facts
        if snapshot is not None:
            snapshot = EffectiveSnapshotFacts(
                snapshot, tuple(replacements), request["request_id"], graph_digest(canonical)
            )
        prepared = PreparedSemanticGraph(canonical, snapshot_facts=snapshot, _defensive_copy=False)
    original = material.runtime_context
    context = RuntimeContext(
        facts,
        authentication_context=original.authentication_context,
        rbcd_bindings=original.rbcd_bindings,
        withheld_relationships=original.withheld_relationships,
    )
    return prepared, context, active


def extract_witness(
    path, material, graph, *, comparison_scope_digest, source_id, goal_id, observation_id="native"
):
    """Extract successful native decisions, exact support and ordered causal history."""
    require(path.runtime_context == material.runtime_context, "native witness context mismatch")
    prepared = graph.to_prepared()
    state = material.initial_attack_state
    for step in path.transition_history:
        if step.edge_id is not None:
            edge = graph.edge(step.edge_id)
            expected_kind = step.result.technique.relationship
            if expected_kind == "DeclaredHostAdmin":
                expected_kind = "GenericAll"
            if step.result.request.rbcd_binding is not None:
                require(
                    edge in [json.loads(e) for e in step.result.snapshot_evidence],
                    "native RBCD edge lacks exact evaluated support",
                )
                expected_kind = edge["kind"]
            require(
                (edge["source"], edge["target"], edge["kind"])
                == (step.result.request.source, step.result.request.target, expected_kind),
                "native witness canonical edge mismatch",
            )
        actual = evaluate(
            prepared, state, step.result.request, material.runtime_context, material.catalog
        )
        require(actual == step.result, "native witness transition mismatch")
        state = apply_transition(state, actual)
    require(
        state == path.final_state and material.is_success_state(state),
        "native witness final state mismatch",
    )
    actions = []
    for index, step in enumerate(path.transition_history):
        result, request = step.result, step.result.request
        require(result.status == Status.APPLICABLE, "witness contains unsuccessful action")
        parents = _producer_indices(path, index)
        support = [{"kind": "initial_state", "reference": _digest(material.initial_attack_state)}]
        if step.edge_id:
            support.append({"kind": "canonical_edge", "reference": step.edge_id})
        support.extend({"kind": "artifact", "reference": _digest(actions[i])} for i in parents)
        support.extend(
            {"kind": "snapshot_fact", "reference": _digest(e)} for e in result.snapshot_evidence
        )
        prerequisites = []
        for decision in result.decisions:
            require(decision.satisfied, "witness contains unresolved prerequisite")
            fact = decision.fact
            origin = str(decision.origin)
            require(
                origin in {"observed_evidence", "declared_assumption", "technical_rule"},
                "witness has unsupported evidence origin",
            )
            bindings = list(support)
            if fact:
                bindings.append({"kind": "runtime_fact", "reference": _digest(fact)})
            else:
                bindings.append(
                    {
                        "kind": (
                            "snapshot_fact"
                            if origin == "observed_evidence"
                            else "artifact"
                            if parents
                            else "initial_state"
                        ),
                        "reference": _digest(
                            {
                                "nodes": [
                                    graph.node(n)
                                    for n in (request.actor, request.source, request.target)
                                ],
                                "predicate": decision.predicate,
                                "snapshot": result.snapshot_evidence,
                                "state": _value(result.before),
                            }
                        ),
                    }
                )
            prerequisites.append(
                {
                    "predicate": decision.predicate,
                    "subject": fact.subject if fact else _subject(decision.predicate, request),
                    "target": fact.target if fact else request.target,
                    "origin": origin,
                    "satisfied": True,
                    "evidence_bindings": bindings,
                }
            )
        metadata = [dict(d.fact.assumption_metadata or {}) for d in result.decisions if d.fact]
        context = {
            "authentication_context": path.runtime_context.authentication_context,
            "resource_context": request.target,
            "policy_reference": path.scenario_reference,
            "method": None,
            "budget": None,
            "horizon": None,
        }
        for key in ("method", "budget", "horizon"):
            values = [m[key] for m in metadata if key in m]
            require(not values or all(v == values[0] for v in values), "ambiguous action context")
            if values:
                context[key] = values[0]
        actions.append(
            {
                "technique_id": request.technique_id,
                "actor": request.actor,
                "source": request.source,
                "target": request.target,
                "participants": _value(request.rbcd_binding) if request.rbcd_binding else {},
                "context": context,
                "prerequisites": prerequisites,
                "evidence_bindings": support,
                "producer_action_indices": parents,
            }
        )
    trace = {
        "program_id": program_id(program_key(path)),
        "route_id": _digest([e for e in path.transition_edge_ids if e is not None]),
        "trace_ref": f"native:{observation_id}/" + program_id(program_key(path)),
        "semantic_program": actions,
    }
    trace["semantic_identity"] = normalized_program_identity(
        {"source_id": source_id, "goal_id": goal_id}, comparison_scope_digest, trace
    )
    return trace


def _producer_indices(path, index):
    """Bind producers of state fields read by native prerequisite decisions.

    All matching artifact histories are retained when multiple scoped artifacts
    exist; no evidence is erased to force an identity match.
    """
    step = path.transition_history[index]
    fields = set()
    capability_fields = {
        "actor_controlled": {"control", "usable_identity"},
        "actor_authenticated": {"usable_identity"},
        "kerberos_actor_authenticated": {"usable_identity"},
        "source_authorized": {"effective_member"},
        "source_admin_control": {"admin_control"},
        "reset_password_control": {"reset_password_control"},
        "known_identity": {"known_identity"},
        "known_impersonated_identity": {"known_identity"},
        "asrep_request_capability": {"asrep_request_capability"},
        "asrep_material": {"asrep_material"},
        "ticket_material": {"service_ticket_material"},
        "recovered_password": {"recovered_secret"},
        "scoped_password": {"rbcd_secret"},
        "controlled_service": {"controlled_service"},
        "rbcd_descriptor": {"rbcd_descriptor"},
        "delegated_context": {"delegated_context"},
    }
    for decision in step.result.decisions:
        fields.update(capability_fields.get(decision.predicate, ()))
    req, context, before = step.result.request, path.runtime_context, step.result.before
    if req.source == req.actor:
        fields.discard("effective_member")
    selections = {
        "control": {req.actor},
        "usable_identity": {(req.actor, context.authentication_context)},
        "effective_member": {(req.actor, req.source)},
        "admin_control": {req.source},
        "reset_password_control": {req.source},
        "asrep_request_capability": {(req.actor, context.authentication_context)},
        "known_identity": {
            _subject(d.predicate, req)
            for d in step.result.decisions
            if d.predicate in {"known_identity", "known_impersonated_identity"}
        },
    }
    for field in ("asrep_material", "service_ticket_material", "recovered_secret"):
        owner = req.source if field == "recovered_secret" else req.target
        selections[field] = {
            a
            for a in getattr(before, field)
            if a.owner == owner and a.context == context.authentication_context
        }
    for field in ("rbcd_secret", "controlled_service", "rbcd_descriptor", "delegated_context"):
        selections[field] = {a for a in getattr(before, field) if a.binding == req.rbcd_binding}
    parents = set()
    if step.derived_from_step is not None:
        parents.add(step.derived_from_step)
    for i, prior in enumerate(path.transition_history[:index]):
        if any(getattr(prior.result.additions, field) & selections[field] for field in fields):
            parents.add(i)
    return sorted(parents)


def _subject(predicate, request):
    if predicate in {
        "target_enabled",
        "target_kind",
        "known_identity",
        "dontreqpreauth",
        "has_spn",
        "service_principal_names",
    }:
        if request.rbcd_binding and predicate in {
            "known_identity",
            "has_spn",
            "service_principal_names",
        }:
            return request.rbcd_binding.principal
        return request.target
    if predicate == "known_impersonated_identity" and request.rbcd_binding:
        return request.rbcd_binding.impersonated
    if predicate in {"source_kind", "source_admin_control", "reset_password_control"}:
        return request.source
    return request.actor


def _decision_audit(actual, request, active):
    decisions = _value(actual.decisions)
    for decision in decisions:
        refs = []
        for edit in request["edits"]:
            if edit["edit_id"] not in active:
                continue
            if edit["kind"] == "snapshot_fact_replace":
                matches = (
                    decision["predicate"] == edit["name"]
                    and _subject(decision["predicate"], actual.request) == edit["subject"]
                )
            elif edit["kind"] == "runtime_fact_replace":
                fact = decision["fact"]
                matches = fact is not None and all(
                    fact[k] == edit["key"][k] for k in ("predicate", "subject", "target")
                )
            else:
                relationship = edit["relationship"]
                matches = (
                    decision["predicate"] == "relationship_exists"
                    and actual.request.source == relationship["source"]
                    and actual.request.target == relationship["target"]
                    and actual.technique.relationship == relationship["kind"]
                )
            if matches:
                refs.append(f"intervention:{request['request_id']}/{edit['edit_id']}")
        decision["effective_origin"] = "counterfactual_intervention" if refs else decision["origin"]
        decision["intervention_refs"] = refs
    return decisions


def replay_baseline(request: dict, graph: EngineGraph, baseline: ReplayBaseline) -> dict:
    """Validate pins, reproduce native baseline, then replay exact ordered transitions.

    Unknown/error never become cuts. Retained witnesses establish only successful
    replay; no result here proves that a source-goal pair is disconnected.
    """
    request = json.loads(canonical_json(request))
    before_digest = _digest([graph.to_canonical(), _facts(graph)])
    schema_validate("request", request, "v1.1")
    require(request["catalog_digest"] == sha(DOC / "catalog-v1.json"), "catalog pin mismatch")
    catalog_entries = json.loads((DOC / "catalog-v1.json").read_text(encoding="utf-8"))["entries"]
    known_ids = {entry["id"] for entry in catalog_entries}
    for edit in request["edits"]:
        if edit["catalog_entry_id"] in known_ids - SUPPORTED:
            raise UnsupportedIntervention(
                edit["edit_id"], "catalog adapter or reviewed basis pending"
            )
    validate_request(request)
    require(request["baseline_run_id"] == baseline.run_id, "baseline run mismatch")
    require(request["scope"] == baseline.scope, "request/baseline scope mismatch")
    cells = json.loads(baseline.cells_json)
    # Reproduction binds the exact public query/candidate/trace corpus rather
    # than accepting caller-supplied fixture witnesses or mutable cached paths.
    results = tuple(run_attack_query(c["query"], graph) for c in cells)
    require(_scope(graph, cells, results) == baseline.scope, "baseline input pin mismatch")
    require(_native_digest(results) == baseline.native_digest, "native baseline trace mismatch")
    materials = [r.materialized_query for r in results]
    _check_edits(request, graph, materials)
    comparison = _digest(request["scope"])
    rows = []
    for cell, result, material in zip(cells, results, materials, strict=True):
        prepared, context, active = _effective(request, graph, material)
        programs, identities = [], set()
        for path in result.paths:
            witness = extract_witness(
                path,
                material,
                graph,
                comparison_scope_digest=comparison,
                source_id=cell["source_id"],
                goal_id=cell["goal_id"],
                observation_id=baseline.run_id,
            )
            if witness["semantic_identity"] in identities:
                continue
            identities.add(witness["semantic_identity"])
            state, steps, disposition, reason, _ = replay_program(
                path, material, prepared, context, request, active
            )
            programs.append(
                {
                    "baseline": witness,
                    "native_transition_history": _value(path.transition_history),
                    "native_final_state": _value(path.final_state),
                    "observed_route": {
                        "edge_ids": [e for e in path.transition_edge_ids if e is not None],
                        "kind": (
                            "ordered_observed_evidence"
                            if any(path.transition_edge_ids)
                            else "empty_nonstructural"
                        ),
                    },
                    "disposition": disposition,
                    "failure": reason,
                    "steps": steps,
                    "final_state": _value(state),
                }
            )
        rows.append(
            {
                "source_id": cell["source_id"],
                "goal_id": cell["goal_id"],
                "baseline_query": cell["query"],
                "baseline_complete": result.complete,
                "baseline_truncated": result.truncated,
                "baseline_status": result.status,
                "baseline_diagnostics": _value(result.diagnostics),
                "programs": programs,
                "rediscovery": {"status": "not_run"},
            }
        )
    after_digest = _digest([graph.to_canonical(), _facts(graph)])
    require(before_digest == after_digest, "baseline mutated during replay")
    return {
        "schema_version": "remediation-replay/1",
        "baseline_run_id": baseline.run_id,
        "baseline_native_digest": baseline.native_digest,
        "scope": request["scope"],
        "catalog_digest": request["catalog_digest"],
        "request_id": request["request_id"],
        "comparison_scope_digest": comparison,
        "counterfactual_origin": "counterfactual_intervention",
        "edits": request["edits"],
        "baseline_input_digest_before": before_digest,
        "baseline_input_digest_after": after_digest,
        "cells": rows,
        "supported_catalog_entries": sorted(SUPPORTED),
        "effort": None,
        "conditional_p": None,
    }


def replay_program(path, material, prepared, context, request, active):
    """Shared #283 replay, also retaining typed successful witnesses for #284.

    A denied observed relationship recreated by a producer becomes derived
    evidence in the effective observation, never a surviving canonical edge.
    """
    state = material.initial_attack_state
    steps, native_steps, disposition, reason = [], [], "retained", None
    edges = {e["id"]: e for e in prepared["edges"]}
    for index, step in enumerate(path.transition_history):
        try:
            actual = evaluate(prepared, state, step.result.request, context, material.catalog)
        except (ValueError, TypeError, KeyError) as error:
            disposition, reason = "error", {"step_index": index, "reason": str(error)}
            break
        after = apply_transition(state, actual)
        audit = _decision_audit(actual, request, active)
        steps.append(
            {
                "step_index": index,
                "request": _value(actual.request),
                "status": str(actual.status),
                "failed": list(actual.failed),
                "unknown": list(actual.unknown),
                "decisions": audit,
                "before": _value(state),
                "after": _value(after),
                "intervention_refs": sorted({ref for d in audit for ref in d["intervention_refs"]}),
            }
        )
        edge_id = step.edge_id if step.edge_id in edges else None
        parent = step.derived_from_step
        if step.edge_id is not None and edge_id is None:
            parent = next(
                (
                    i
                    for i, prior in enumerate(native_steps)
                    if any(
                        (r.source, r.kind, r.target)
                        == (
                            actual.request.source,
                            actual.technique.relationship,
                            actual.request.target,
                        )
                        for r in prior.result.additions.relationship_added
                        | prior.result.additions.permission
                    )
                ),
                None,
            )
        native_steps.append(TransitionStep(actual, edge_id, parent))
        state = after
        if actual.status != Status.APPLICABLE:
            disposition = "cut" if actual.status == Status.BLOCKED else "indeterminate"
            reason = {
                "step_index": index,
                "failed": list(actual.failed),
                "unknown": list(actual.unknown),
            }
            break
    if disposition == "retained" and not material.is_success_state(state):
        disposition, reason = "indeterminate", {"reason": "final goal not established"}
    replayed = None
    if disposition == "retained":
        replayed = replace(
            path,
            transition_history=tuple(native_steps),
            runtime_context=context,
            final_state=state,
            edges=tuple(edges[s.edge_id] for s in native_steps if s.edge_id is not None),
            cost=None,
        )
    return state, steps, disposition, reason, replayed


def effective_scenario(request, graph, material):
    """Read-only #283 views for native query rediscovery; declared state is preserved."""
    prepared, context, active = _effective(request, graph, material)
    effective_graph = (
        graph
        if prepared is graph.to_prepared()
        else EngineGraph.from_canonical(dict(prepared), snapshot_facts=prepared.snapshot_facts)
    )
    # Explicit baseline scoring packets/bindings must not be recycled into a new
    # effective scenario. Consumers may resolve fresh ratings separately.
    effective_material = replace(
        material,
        runtime_context=context,
        ranking_query=None,
        action_bindings=None,
        rating_resolution=None,
    )
    return effective_graph, effective_material, prepared, active
