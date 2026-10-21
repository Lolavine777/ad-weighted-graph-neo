"""Branch foothold/capability handoff using the accepted shared runtime policy."""

from collections.abc import Mapping

from .projection_runtime import context_for_projection
from .state import AttackState


def runtime_for_projection(
    query: Mapping, source_plan: Mapping, case_plan: Mapping, *, withheld_relationships=frozenset()
):
    ledger = query.get("facts_ledger") or {}
    false_predicates = {
        entry["predicate"]
        for bucket in ("assumed_facts", "observed_facts", "false_facts", "unknown_facts")
        for entry in ledger.get(bucket, [])
        if entry.get("truth_value") is False
    }
    footholds = [
        entry
        for bucket in ("assumed_facts", "observed_facts")
        for entry in ledger.get(bucket, [])
        if entry["predicate"].startswith("foothold_controlled_")
        and entry.get("truth_value") is True
        and entry["predicate"] not in false_predicates
    ]
    state = AttackState(
        control={source_plan["actor"]} if not ledger or len(footholds) == 1 else set()
    )
    return state, context_for_projection(
        query,
        source_plan,
        case_plan,
        authentication_context=source_plan.get("authentication_context"),
        withheld_relationships=withheld_relationships,
    )
