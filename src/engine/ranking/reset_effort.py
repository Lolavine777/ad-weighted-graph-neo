"""Opt-in C-only scope for direct principal reset and owner-bound activation.

Existing numeric decisions are inputs, not authority for a different query.
This explicit solo-fork scenario profile adopts their ordinal C rubric for a
narrow new scope. It emits native provider records, never scores candidates or
imports P/I. Owner/context-specific work IDs are declared before search.
"""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

from src.engine.ranking.resolution_service import canonical_digest
from src.engine.ranking.resolver import generate_work_unit_id

ROOT = Path(__file__).resolve().parents[3]
PROFILE_ID = "reset-activation-c-v1"
MACHINE_PROFILE_ID = "reset-activation-c-v2"
REFERENCE = "https://github.com/nairyuuu/ad-weighted-graph/issues/297"
NUMERIC = "docs/research/ratings/final-cpi-release-v1/decisions.adopted.json"
RUBRIC = "docs/research/ratings/final-cpi-v1/profile.json"
TECHNIQUES = {
    "scenario_reset_password": ("directory_password_reset", "GenericAll"),
    "acquire_reset_identity": ("reset_identity_activation", "AuthenticationControl"),
}


def load_reset_effort_profile(identifier):
    """Read unchanged numeric/rubric sources; make the new scope explicit."""
    if identifier not in {PROFILE_ID, MACHINE_PROFILE_ID}:
        raise ValueError(f"Unknown effort profile: {identifier}")
    sources = {}
    for path in (NUMERIC, RUBRIC):
        raw = (ROOT / path).read_bytes()
        sources[path] = {"sha256": "sha256:" + hashlib.sha256(raw).hexdigest()}
    numeric = json.loads((ROOT / NUMERIC).read_text())
    rubric = {c["class_id"]: c for c in json.loads((ROOT / RUBRIC).read_text())["classes"]}
    if numeric["status"] != "adopted":
        raise ValueError("Reset effort numeric input is not an adopted decision")
    classes = {}
    for technique, (name, method) in TECHNIQUES.items():
        decision, scores = numeric["classes"][name]["C"], rubric[name]
        values = numeric["classes"][name]["values"]
        if decision["decision"] != "adopt" or (scores["t1"], scores["t2"], scores["cost"]) != (
            values["t1"],
            values["t2"],
            values["cost"],
        ):
            raise ValueError("Reset effort numeric/rubric disagreement")
        classes[technique] = {
            "name": name,
            "method": method,
            "t1": scores["t1"],
            "t2": scores["t2"],
            "cost": values["cost"],
            "rationale": scores["rationale"],
        }
    profile = {
        "profile_id": PROFILE_ID,
        "version": "1.0.0",
        "dimension": "C",
        "scope_adoption": {
            "reference": REFERENCE,
            "status": "explicit_opt_in_solo_fork_scenario",
            "rationale": (
                "Apply the existing ordinal reset/activation rubric to direct User-owned "
                "GenericAll reset work and its reset-owned activation at one Computer context. "
                "This new scope is not the historical reviewer's context approval. "
                "One successful operation per canonical work unit; retries/time not modeled."
            ),
        },
        "historical_numeric_authority": {"dimension": "C", "review": numeric["review"]},
        "sources": sources,
        "classes": classes,
        "excluded": [
            "P",
            "I",
            "password recovery",
            "inherited/group ACL reset work",
            "retries",
            "existing source membership route",
            "pre-seeded second usable identity/context",
        ],
    }
    if identifier == MACHINE_PROFILE_ID:
        profile.update(profile_id=identifier, version="2.0.0")
        profile["scope_adoption"]["rationale"] = (
            "Apply the same ordinal reset/activation operation rubric to direct User or "
            "explicitly usable Computer principals, at one same-domain Computer context. "
            "The controller kind changes applicability, not the operation price. This is "
            "an opt-in solo-fork scenario estimate, not observed duration or historical "
            "reviewer approval of this scope. One successful operation per canonical work "
            "unit; retries/time not modeled. Local host control alone is insufficient. "
            "An actor-to-User canonical grant may be inherited; effective permission is "
            "already a conditioned prerequisite. Group/derived rights remain unpriced."
        )
        profile["excluded"].remove("inherited/group ACL reset work")
        profile["excluded"].append("group/derived-right reset work")
        profile["excluded"].append("Computer host control without explicit network identity")
    return profile


def _envelope(data):
    return {"version": "1.0.0", "sha256": canonical_digest(data), "data": data}


def _unit(technique, actor, target, *, method, context, scenario, profile_id=PROFILE_ID):
    # Same canonical work-key contract as the native provider. This is only an
    # applicability inventory; the independent experiment oracle does not use it.
    execution = {
        "source_id": actor,
        "method": method,
        "auth_context": context,
        "resource_context": None,
        "policy_id": profile_id,
        "scope": scenario,
    }
    return generate_work_unit_id(
        technique, actor, target, "ctx-" + canonical_digest(execution)[7:], "intra_forest"
    )


def bind_reset_effort(query, graph, profile):
    """Return a native C-only query; inapplicable goals/sources remain unrated.

    No path or candidate is inspected. Direct snapshot ACL pairs only constrain
    cost applicability; the existing search/evaluator must establish feasibility.
    Other actors/rights/techniques do not acquire a price through this profile.
    """
    from src.engine.query import UsableIdentityEntitlementGoal, materialize_query

    if profile != load_reset_effort_profile(profile.get("profile_id")):
        raise ValueError("Effort profile numeric/source definition changed")
    updated = copy.deepcopy(dict(query))
    if updated.get("rating_resolution") is not None:
        raise ValueError("effort_profile conflicts with explicit rating_resolution")
    material = materialize_query(updated, graph)
    profile_id = profile["profile_id"]
    audit = {
        "profile_id": profile["profile_id"],
        "profile_digest": canonical_digest(profile),
        "dimension": "C",
        "P": "not_evaluated",
        "I": "not_evaluated",
    }
    reason = None
    if not isinstance(material.semantic_goal, UsableIdentityEntitlementGoal):
        reason = "Profile supports only usable_identity_entitlement Group goals"
    elif graph.node(material.initial_actor)["kind"] != "User" and not (
        profile_id == MACHINE_PROFILE_ID
        and graph.node(material.initial_actor)["kind"] == "Computer"
    ):
        reason = "Profile supports only a User controller, not implicit Computer credentials"
    elif (
        graph.node(material.initial_actor)["kind"] == "Computer"
        and (
            material.initial_actor,
            material.runtime_context.authentication_context,
        )
        not in material.initial_attack_state.usable_identity
    ):
        reason = "Computer pricing requires explicit usable_identity in this exact context"
    else:
        participants = [
            material.initial_actor,
            material.target,
            material.runtime_context.authentication_context,
        ]
        domains = [str(graph.node(n).get("domain") or "").strip().casefold() for n in participants]
        if (
            not all(domains)
            or len(set(domains)) != 1
            or any(graph.node(n).get("is_boundary", False) for n in participants)
        ):
            reason = "Profile supports only non-boundary, same-domain source/goal/context"
    if reason is None:
        actor = material.initial_actor
        context = material.runtime_context.authentication_context
        state = material.initial_attack_state
        if any(pair != (actor, context) for pair in state.usable_identity):
            reason = "Profile does not price a pre-seeded second usable identity/context"
        else:
            # Applicability only, never remove a source/goal or structural route
            # from search. Existing membership may admit a passive-only witness;
            # this profile is specifically for new identity acquisition. Keep
            # that case outside its C/P presentation, including vacuous P=1.
            members = {actor} | {g for u, g in state.effective_member if u == actor}
            membership = {}
            for edge in graph.edges():
                if edge["kind"] == "MemberOf":
                    membership.setdefault(edge["source"], set()).add(edge["target"])
            pending = list(members)
            while pending:
                for group in membership.get(pending.pop(), ()):
                    if group not in members:
                        members.add(group)
                        pending.append(group)
            if material.target in members:
                reason = (
                    "Existing membership may satisfy the goal; acquisition C profile inapplicable"
                )
    if reason:
        updated["effort_profile_metadata"] = {**audit, "status": "not_applicable", "reason": reason}
        return updated
    actor = material.initial_actor
    context = material.runtime_context.authentication_context
    scenario = material.scenario_reference
    if not scenario:
        raise ValueError("Reset effort profile requires an explicit scenario_reference")
    pairs = sorted(
        {
            (e["source"], e["target"])
            for e in graph.edges()
            if e["kind"] == "GenericAll"
            and e["source"] == actor
            and graph.node(e["target"])["kind"] == "User"
            and not graph.node(e["target"]).get("is_boundary", False)
            and graph.node(e["target"]).get("domain") == graph.node(actor).get("domain")
        }
    )
    owners = sorted({target for _, target in pairs})
    declarations = {
        "scenario_reset_password": pairs,
        "acquire_reset_identity": [(owner, context) for owner in owners],
    }
    records = []
    for technique, bindings in declarations.items():
        if not bindings:
            continue
        cls = profile["classes"][technique]
        work_ids = [
            _unit(
                technique,
                a,
                t,
                method=cls["method"],
                context=context,
                scenario=scenario,
                profile_id=profile_id,
            )
            for a, t in bindings
        ]
        records.append(
            {
                "class_id": profile_id + ":" + technique,
                "name": cls["name"],
                "description": cls["rationale"],
                "t1": cls["t1"],
                "t2": cls["t2"],
                "formula": "base",
                "computed_cost": cls["cost"],
                "disposition": "rated",
                "basis_category": "scenario_assumption",
                "numeric_basis_class": "estimated_expert_scenario",
                "review_status": "accepted",
                "review_reference": REFERENCE,
                "provenance_digest": canonical_digest({"profile": profile, "work_ids": work_ids}),
                "notes": (
                    "New opt-in C-only scope; historical numbers, not historical scope approval. "
                    "Native replay and canonical union-work deduplication remain authoritative."
                ),
                "applicability": {
                    "techniques": [technique],
                    "methods": [cls["method"]],
                    "boundaries": ["intra_forest"],
                    "work_classes": ["active_work"],
                    "scopes": [scenario],
                    "snapshot_ids": [graph.metadata["snapshot_id"]],
                    "source_ids": sorted({a for a, _ in bindings}),
                    "required_auth_context": context,
                    "work_unit_digests": [canonical_digest(uid) for uid in work_ids],
                },
            }
        )
    target = material.target
    identity = canonical_digest({"query": updated, "profile": profile})
    updated["rating_resolution"] = {
        "version": "public-rating-resolution/1.1.0",
        "mode": "automatic",
        "policy": "production",
        "scope": {
            "query_id": identity,
            "scenario_id": scenario,
            "scenario_version": "1.0.0",
            "snapshot_id": graph.metadata["snapshot_id"],
            "foothold_node_id": actor,
            "work_boundary": "intra_forest",
            "horizon": "static_snapshot_no_elapsed_time",
            "active_work_budget": material.budget.max_steps,
            "evaluation_mode": material.evaluation_mode,
            "target_goal": {
                "goal_id": "identity-entitlement-" + canonical_digest(target)[7:],
                "target_asset_id": target,
                "success_event": "usable_identity_entitlement",
            },
            "policy_id": profile_id,
            "governance": profile["scope_adoption"],
        },
        "registries": {"effort": _envelope(records)},
    }
    updated["effort_profile_metadata"] = {
        **audit,
        "status": "bound",
        "direct_reset_pairs": len(pairs),
        "activation_owners": len(owners),
        "active_classes": len(records),
        "coverage": (
            "Direct initial User-owned GenericAll reset and reset-identity activation only"
            if profile_id == PROFILE_ID
            else "Direct initial User/explicit Computer-owned GenericAll reset "
            "and owner/context-bound reset activation only"
        ),
    }
    return updated
