"""Small opt-in C catalog for neo; feasibility stays with the semantic planner."""

from __future__ import annotations

from copy import deepcopy

from src.engine.ranking.reset_effort import bind_reset_effort, load_reset_effort_profile
from src.engine.ranking.resolution_service import canonical_digest

NEO_PROFILE_ID = "neo-c-v1"
PROFILE_IDS = ("reset-activation-c-v1", "reset-activation-c-v2", NEO_PROFILE_ID)
REFERENCE = "docs/neo.md#chi-phi-c-cho-neo"

# technique: (relationship/method, T1, T2, reason). C = T1 + T2 - 2.
# These are neo scenario estimates, not imported historical review decisions.
OPERATIONS = {
    "genericall_reset_password": ("GenericAll", 1, 2, "Standard password reset and verification"),
    "reset_target_password": (
        "ForceChangePassword",
        1,
        2,
        "Standard password reset and verification",
    ),
    "scenario_reset_password": ("GenericAll", 1, 2, "Standard password reset and verification"),
    "acquire_reset_identity": ("AuthenticationControl", 1, 1, "Use the freshly reset credential"),
    "genericall_add_member": ("GenericAll", 1, 2, "Directory membership mutation and verification"),
    "genericall_grant_write_dacl": ("GenericAll", 1, 2, "Grant DACL control and verify the write"),
    "grant_new_object_right": (
        "WriteDacl",
        2,
        2,
        "Construct and verify an object permission grant",
    ),
    "obtain_admin_execution_on_host": ("AdminTo", 1, 2, "Authenticated administrative execution"),
    "scenario_winrm_admin": (
        "DeclaredHostAdmin",
        1,
        2,
        "Elevated WinRM execution and verification",
    ),
    "open_winrm_remote_session": (
        "CanPSRemote",
        1,
        2,
        "Authenticated WinRM command session and verification; no elevation implied",
    ),
}


def load_effort_profile(identifier):
    if identifier != NEO_PROFILE_ID:
        return load_reset_effort_profile(identifier)
    return {
        "profile_id": NEO_PROFILE_ID,
        "version": "1.1.0",
        "dimension": "C",
        "formula": "T1 + T2 - 2",
        "basis": "estimated_expert_scenario",
        "reference": REFERENCE,
        "scope": "Same-domain actions in one authentication context; no retries or elapsed time",
        "classes": {
            technique: {"method": method, "t1": t1, "t2": t2, "cost": t1 + t2 - 2, "reason": reason}
            for technique, (method, t1, t2, reason) in OPERATIONS.items()
        },
    }


def bind_effort_profile(query, graph, profile):
    if profile.get("profile_id") != NEO_PROFILE_ID:
        return bind_reset_effort(query, graph, profile)
    if profile != load_effort_profile(NEO_PROFILE_ID):
        raise ValueError("Effort profile definition changed")
    updated = deepcopy(dict(query))
    if updated.get("rating_resolution") is not None:
        raise ValueError("effort_profile conflicts with explicit rating_resolution")

    from src.engine.query import materialize_query

    material = materialize_query(updated, graph)
    if material.semantic_goal is None:
        raise ValueError("neo-c-v1 requires a typed target_goal")
    if not material.scenario_reference:
        raise ValueError("neo-c-v1 requires an explicit scenario_reference")
    actor, target = material.initial_actor, material.target
    context = material.runtime_context.authentication_context
    participants = [graph.node(n) for n in (actor, target, context)]
    domains = {str(n.get("domain") or "").strip().casefold() for n in participants}
    audit = {"profile_id": NEO_PROFILE_ID, "profile_digest": canonical_digest(profile)}
    if (
        len(domains) != 1
        or "" in domains
        or any(n.get("is_boundary", False) for n in participants)
        or participants[0]["kind"] not in {"User", "Computer"}
        or participants[2]["kind"] != "Computer"
    ):
        updated["effort_profile_metadata"] = {
            **audit,
            "status": "not_applicable",
            "reason": "Requires same-domain source, typed goal and Computer authentication context",
        }
        return updated

    domain = next(iter(domains))
    node_ids = sorted(
        n["id"]
        for n in graph.nodes()
        if str(n.get("domain") or "").strip().casefold() == domain
        and not n.get("is_boundary", False)
    )
    scenario = material.scenario_reference
    snapshot = graph.metadata["snapshot_id"]
    records = []
    for technique, cls in profile["classes"].items():
        records.append(
            {
                "class_id": NEO_PROFILE_ID + ":" + technique,
                "name": technique,
                "description": cls["reason"],
                "t1": cls["t1"],
                "t2": cls["t2"],
                "computed_cost": cls["cost"],
                "formula": "base",
                "disposition": "rated",
                "basis_category": "scenario_assumption",
                "numeric_basis_class": "estimated_expert_scenario",
                "review_status": "accepted",
                "review_reference": REFERENCE,
                "provenance_digest": canonical_digest(profile),
                "notes": "Neo scenario estimate; not elapsed time, P, or historical A/B approval",
                "applicability": {
                    "techniques": [technique],
                    "methods": [cls["method"]],
                    "boundaries": ["intra_forest"],
                    "work_classes": ["active_work"],
                    "scopes": [scenario],
                    "snapshot_ids": [snapshot],
                    "required_auth_context": context,
                    "node_ids": node_ids.copy(),
                },
            }
        )
    goal = material.semantic_goal.to_dict()
    updated["rating_resolution"] = {
        "version": "public-rating-resolution/1.1.0",
        "mode": "automatic",
        "policy": "production",
        "scope": {
            "query_id": canonical_digest({"query": updated, "profile": profile}),
            "scenario_id": scenario,
            "scenario_version": "1.0.0",
            "snapshot_id": snapshot,
            "foothold_node_id": actor,
            "work_boundary": "intra_forest",
            "horizon": "static_snapshot_no_elapsed_time",
            "active_work_budget": material.budget.max_steps,
            "evaluation_mode": material.evaluation_mode,
            "policy_id": NEO_PROFILE_ID,
            "target_goal": {
                "goal_id": canonical_digest(goal),
                "target_asset_id": target,
                "success_event": "declared_semantic_goal",
            },
        },
        "registries": {
            "effort": {"version": "1.0.0", "sha256": canonical_digest(records), "data": records}
        },
    }
    updated["effort_profile_metadata"] = {
        **audit,
        "status": "bound",
        "dimension": "C",
        "basis": "estimated_expert_scenario",
        "active_classes": len(records),
        "P": "not_evaluated",
        "I": "not_evaluated",
    }
    # Reuse the existing C-only selector. Missing P/I do not exclude these paths.
    updated.setdefault("top_k", 3)
    return updated
