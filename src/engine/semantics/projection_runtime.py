"""Shared accepted release-fact policy for Week 3 harness and bridge contexts."""

from collections.abc import Mapping

from .models import FactOrigin, RuntimeFact
from .state import RuntimeContext


def release_fact(query: Mapping, predicate: str) -> dict:
    ledger = query.get("facts_ledger", {})
    matches = [
        record
        for bucket in ("observed_facts", "false_facts", "assumed_facts", "unknown_facts")
        for record in ledger.get(bucket, [])
        if record.get("predicate") == predicate
    ]
    # #178 known-false overlays may retain the optimistic assumption while
    # adding explicit counterfactual false evidence. The veto takes precedence.
    blocked = [record for record in matches if record.get("truth_value") is False]
    if len(blocked) == 1:
        return blocked[0]
    if len(matches) != 1:
        raise ValueError(f"release predicate {predicate!r} resolved to {len(matches)} facts")
    return matches[0]


def context_for_projection(
    query: Mapping,
    source_plan: Mapping,
    case_plan: Mapping,
    *,
    authentication_context: str | None = None,
    withheld_relationships=frozenset(),
) -> RuntimeContext:
    overrides = {
        row["release_predicate"]: row for row in case_plan.get("runtime_fact_overrides", [])
    }
    facts = []
    for binding in source_plan.get("runtime_fact_bindings", []):
        release_predicate = binding["release_predicate"]
        record = release_fact(query, release_predicate)
        # Known-false release evidence cannot be promoted by an optimistic override.
        override = overrides.get(release_predicate, {})
        if record.get("truth_value") is False and override.get("truth_value") is not False:
            override = {}
        value = override.get("truth_value", record.get("truth_value"))
        if value is not None and type(value) is not bool:
            raise ValueError(f"invalid truth value for {release_predicate}")
        if value is False:
            origin = FactOrigin.BLOCKED_EVIDENCE
        elif value is None:
            origin = FactOrigin.UNKNOWN
        elif "origin" in override:
            origin = FactOrigin(override["origin"])
        elif record.get("layer") in (1, 2):
            origin = FactOrigin.OBSERVED_EVIDENCE
        else:
            origin = FactOrigin.DECLARED_ASSUMPTION
        if origin is FactOrigin.DECLARED_ASSUMPTION:
            scope = query["query_metadata"]["horizon"]
        elif origin in (FactOrigin.BLOCKED_EVIDENCE, FactOrigin.UNKNOWN):
            scope = query["query_metadata"]["scenario_id"]
        else:
            scope = None
        facts.append(
            RuntimeFact(
                binding["semantic_predicate"],
                binding["subject"],
                binding["target"],
                value,
                origin,
                scope=scope,
                rationale=override.get("rationale", record.get("rationale")),
                provenance_reference=record.get("provenance_reference"),
                assumption_metadata={"release_predicate": release_predicate},
            )
        )
    return RuntimeContext(
        facts,
        authentication_context=authentication_context,
        withheld_relationships=withheld_relationships,
    )
