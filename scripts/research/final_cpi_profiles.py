"""Compile declared finite rating histories into existing native provider records.

This module never searches a graph, evaluates a transition, or adopts numbers.
"""

from __future__ import annotations

import copy
import hashlib
from dataclasses import replace

from scripts.research.issue250_public_probe import ROOT, envelope, read
from src.engine.graph import EngineGraph
from src.engine.ranking.resolution_service import canonical_digest
from src.engine.ranking.resolver import generate_rating_lookup_key_p, generate_work_unit_id
from src.engine.semantics import load_catalog
from src.parser.snapshot_facts import graph_digest

PACKAGE = ROOT / "docs/research/ratings/final-cpi-v1"
HISTORICAL = ROOT / "docs/research/ratings/scenario-basis-v1"
REVIEW = "https://github.com/nairyuuu/ad-weighted-graph/issues/267"


def validate_package():
    profile, taxonomy = read(PACKAGE / "profile.json"), read(PACKAGE / "taxonomy.json")
    owners = {t.id: t for t in load_catalog()}
    rows = {a["technique_id"]: a for a in taxonomy["actions"]}
    if rows.keys() != owners.keys():
        raise ValueError("Taxonomy ownership drift")
    for name, row in rows.items():
        tech = owners[name]
        if (
            row["relationship"] != tech.relationship
            or row["required_gates"] != list(tech.prerequisites)
            or row["success_effects"] != [e.value for e in tech.effects]
            or row["active"] != tech.action_required
        ):
            raise ValueError("Taxonomy semantic drift")
    classes = {c["class_id"]: c for c in profile["classes"]}
    if {r["canonical_class"] for r in rows.values() if r["active"]} != classes.keys():
        raise ValueError("Missing active class")
    if profile["b_numeric_adoption"] or profile["status"] != "proposed_pending_b_review":
        raise ValueError("Research compiler cannot adopt a profile")
    for c in classes.values():
        if c["cost"] != c["t1"] + c["t2"] - 2 or not 0 <= c["cost"] <= 4:
            raise ValueError("Invalid effort rubric")
        if c["status"] != "proposed_pending_b_review":
            raise ValueError("Class requires actual B adoption through consumer governance")
    return {
        "active": sum(r["active"] for r in rows.values()),
        "likelihood_classes": len(classes),
        "passive": sum(not r["active"] for r in rows.values()),
    }


def compile_histories(actions, *, max_records, initially_succeeded=()):
    """Expand an explicit causal rating domain, not semantic candidate paths.

    Dependencies describe the conditional question's secret/work lineage only.
    There is no graph, state evaluator, runtime fact or goal in this function.
    """
    inventory = {a["action_id"]: a for a in actions}
    if len(inventory) != len(actions):
        raise ValueError("Duplicate rating identity")
    initial = set(initially_succeeded)
    if any(
        not (set(a["requires"]) | set(a.get("requires_any", ()))) <= inventory.keys() | initial
        for a in actions
    ):
        raise ValueError("Unknown conditional lineage")
    result = []

    def expand(history, seen):
        for action_id, action in sorted(inventory.items()):
            if (
                action_id in seen
                or not set(action["requires"]) <= seen
                or (action.get("requires_any") and not set(action["requires_any"]) & seen)
            ):
                continue
            prefix = (*history, action)
            result.append(prefix)
            if len(result) > max_records:
                raise ValueError(
                    "Rating history expansion exceeds declared cap; no truncation allowed"
                )
            if not action.get("terminal", False):
                expand(prefix, seen | {action_id})

    expand((), initial)
    return result


def _uid(action, scope, auth):
    context = {
        "source_id": action["source"],
        "method": action["method"],
        "auth_context": auth,
        "resource_context": action.get("resource_context"),
        "policy_id": scope["policy_id"],
        "scope": scope["scenario_id"],
    }
    return generate_work_unit_id(
        action["technique_id"],
        action["actor"],
        action["target"],
        "ctx-" + canonical_digest(context).removeprefix("sha256:"),
        scope["work_boundary"],
    )


def validate_binding_context(query, actions, initially_succeeded=()):
    """Refuse endpoint reuse outside a declared class/context question."""
    rules = read(PACKAGE / "applicability-v1.1.json")
    scope = query["rating_resolution"]["scope"]
    policy = rules["policies"].get(scope.get("policy_id"))
    if scope.get("policy_id") == "final-cpi-declared-recovery-24h-v1":
        from scripts.research.final_cpi_delegated_release import pending_policy

        policy = pending_policy(query)

    def refuse(reason):
        raise ValueError("Class/context applicability: " + reason)

    if policy is None:
        refuse("unsupported policy")
    retry = copy.deepcopy(scope.get("retry_policy"))
    if "recovery_contexts" in policy:
        if not isinstance(retry, dict) or retry.get("recovery") not in policy["recovery_contexts"]:
            refuse("unsupported recovery time/compute question")
        recovery = retry["recovery"]
        facts = query.get("runtime_facts", []) + query.get("assumptions", [])
        for fact in facts:
            if fact["predicate"] == "recovery_success":
                metadata = fact.get("assumption_metadata", {})
                question = {k: metadata.get(k) for k in ("method", "budget", "horizon")}
                if metadata.get("recovery_model") is not None:
                    question["recovery_model_digest"] = canonical_digest(metadata["recovery_model"])
                if question != recovery:
                    refuse("runtime recovery context differs from class question")
        retry["recovery"] = None
    else:
        recovery = None
    if retry != policy["retry_policy"]:
        refuse("retry/deadline/transport question mismatch")
    taxonomy = {r["technique_id"]: r for r in read(PACKAGE / "taxonomy.json")["actions"]}
    inventory = {a["action_id"]: a for a in actions}
    lineage = {
        "acquire_reset_identity": {"scenario_reset_password"},
        "recover_asrep_secret": {"asrep_request"},
        "recover_ticket_secret": {"kerberoast_request"},
        "activate_recovered_identity": {"recover_asrep_secret", "recover_ticket_secret"},
        "rbcd_prepare_service": {"rbcd_acquire_secret"},
        "rbcd_delegate_service": {"rbcd_prepare_service", "rbcd_configure_descriptor"},
        "rbcd_service_admin": {"rbcd_delegate_service"},
    }
    for action in actions:
        cls = taxonomy[action["technique_id"]]["canonical_class"]
        rule = rules["classes"][cls]
        if scope["policy_id"] == "final-cpi-declared-recovery-24h-v1":
            from scripts.research.final_cpi_delegated_release import pending_model

            selected, _ = pending_model(query)
            if cls == selected["class_id"]:
                rule = {**rule, "methods": [recovery["method"]]}
        if cls not in policy["classes"] or scope.get("horizon") != rule["horizon"]:
            refuse("class/horizon not covered")
        if action["method"] not in rule["methods"]:
            refuse("method/transport mismatch")
        parents = [inventory[p] for p in action["requires"] if p in inventory]
        required = lineage.get(action["technique_id"], set())
        present = {p["technique_id"] for p in parents}
        covered = (
            bool(required & present)
            if action["technique_id"] == "activate_recovered_identity"
            else required <= present
        )
        if required and not covered:
            refuse("missing required successful lineage")
        if action["technique_id"] in {"acquire_reset_identity", "activate_recovered_identity"}:
            if not any(p["target"] == action["actor"] == action["source"] for p in parents):
                refuse("identity activation lineage owner mismatch")
            if action["target"] != query["authentication_context"]:
                refuse("activation authentication context mismatch")
        if cls in {"winrm_admin_execution", "host_admin_execution", "winrm_command_session"}:
            usable = [action["actor"], query["authentication_context"]] in query[
                "initial_state"
            ].get("usable_identity", [])
            activated = any(
                p["technique_id"] in {"acquire_reset_identity", "activate_recovered_identity"}
                and p["actor"] == action["actor"]
                and p["target"] == query["authentication_context"]
                for p in parents
            )
            if not usable and not activated:
                refuse("execution requires supplied or preceding activated identity")
        if "password_recovery" in cls:
            if (
                recovery is None
                or action["method"] != recovery["method"]
                or action.get("resource_context") != canonical_digest(recovery)
            ):
                refuse("recovery method/resource question mismatch")
        if action["technique_id"].startswith("rbcd_"):
            bindings = query.get("rbcd_bindings", [])
            if len(bindings) != 1:
                refuse("RBCD requires one exact service binding")
            binding = bindings[0]
            target = (
                binding["principal"]
                if action["technique_id"] in {"rbcd_acquire_secret", "rbcd_prepare_service"}
                else binding["target"]
            )
            if (
                action["actor"] != binding["controller"]
                or action["source"] != binding["controller"]
                or action["target"] != target
                or query["authentication_context"] != binding["authentication_context"]
                or binding["service"] != "winrm"
                or not binding["spn"].lower().startswith("http/")
                or action.get("resource_context") != canonical_digest(binding)
            ):
                refuse("RBCD identity/service/transport mismatch")
            if any(p.get("resource_context") != action.get("resource_context") for p in parents):
                refuse("RBCD prior successful lineage resource mismatch")
    compile_histories(
        actions,
        max_records=read(PACKAGE / "profile.json")["history_model"]["max_records"],
        initially_succeeded=initially_succeeded,
    )


def bind_registry(
    query, actions, *, initially_succeeded=(), consequence=None, semantic_goal=None, population=None
):
    """Bind the frozen class profile to exact identities before invoking search."""
    validate_package()
    validate_binding_context(query, actions, initially_succeeded)
    query = copy.deepcopy(query)
    profile = read(PACKAGE / "profile.json")
    taxonomy = {r["technique_id"]: r for r in read(PACKAGE / "taxonomy.json")["actions"]}
    classes = {c["class_id"]: c for c in profile["classes"]}
    if query["rating_resolution"]["scope"]["policy_id"] == "final-cpi-declared-recovery-24h-v1":
        from scripts.research.final_cpi_delegated_release import pending_model

        selected, prediction = pending_model(query)
        name = selected["class_id"]
        classes[name] = {
            **classes[name],
            "lower": prediction["proposed_interval"][0],
            "upper": prediction["proposed_interval"][1],
            "rationale": "Explicit #281 conditional population/work/completion scenario "
            + selected["profile_id"]
            + "; source metadata pinned; no resource attainment claim.",
        }
    config = query["rating_resolution"]
    scope = config["scope"]
    scope["actor_capability"] = {
        "initial_state": query["initial_state"],
        "authentication_context": query["authentication_context"],
    }
    scope["control_scope"] = {
        "actions_digest": canonical_digest(actions),
        "initially_succeeded": list(initially_succeeded),
        "equivalence": profile["history_model"]["id"],
    }
    scope["target_population"] = population or (
        "named snapshot identities under stable account/resource policy; "
        "natural password rank unknown"
    )
    records, efforts = [], []
    uids = {a["action_id"]: _uid(a, scope, query["authentication_context"]) for a in actions}
    if len(set(uids.values())) != len(actions):
        raise ValueError("Repeated canonical work identity")
    for action in actions:
        cls = classes[taxonomy[action["technique_id"]]["canonical_class"]]
        efforts.append(
            {
                "class_id": "final-cpi-" + action["action_id"],
                "name": cls["class_id"],
                "description": cls["rationale"],
                "t1": cls["t1"],
                "t2": cls["t2"],
                "formula": "base",
                "basis_category": "scenario_assumption",
                "review_status": "pending",
                "disposition": "unrated",
                "review_reference": REVIEW,
                "provenance_digest": canonical_digest({"profile": profile, "action": action}),
                "notes": "Ordinal workflow effort only; no elapsed-time or P inference. "
                + cls["rationale"],
                "applicability": {
                    "techniques": [action["technique_id"]],
                    "methods": [action["method"]],
                    "boundaries": [scope["work_boundary"]],
                    "work_classes": ["active_work"],
                    "scopes": [scope["scenario_id"]],
                    "snapshot_ids": [scope["snapshot_id"]],
                    "work_unit_digests": [canonical_digest(uids[action["action_id"]])],
                    "required_auth_context": query["authentication_context"],
                },
            }
        )
    histories = compile_histories(
        actions,
        max_records=profile["history_model"]["max_records"],
        initially_succeeded=initially_succeeded,
    )
    for history in histories:
        action = history[-1]
        cls = classes[taxonomy[action["technique_id"]]["canonical_class"]]
        if cls["lower"] is None:
            continue
        prefix = tuple(uids[a["action_id"]] for a in history)
        key = generate_rating_lookup_key_p(
            scope["scenario_id"],
            scope["scenario_version"],
            scope["snapshot_id"],
            scope["foothold_node_id"],
            prefix,
            prefix[-1],
            action["technique_id"],
            action["actor"],
            action["target"],
            source_id=action["source"],
            method=action["method"],
            budget=scope["active_work_budget"],
            horizon=scope["horizon"],
            boundary=scope["work_boundary"],
            scope=scope["scenario_id"],
            auth_context=query["authentication_context"],
            resource_context=action.get("resource_context"),
            policy_id=scope["policy_id"],
        ).to_dict()
        key.pop("dimension")
        records.append(
            {
                **key,
                **{
                    f: scope[f]
                    for f in (
                        "actor_capability",
                        "control_scope",
                        "retry_policy",
                        "target_population",
                    )
                },
                "lower": cls["lower"],
                "upper": cls["upper"],
                "basis_category": "scenario_assumption",
                "numeric_basis_class": "estimated_expert_scenario",
                "review_status": "pending",
                "disposition": "unrated",
                "review_reference": REVIEW,
                "provenance_digest": canonical_digest(
                    {"class": cls, "history": history, "scope": scope}
                ),
                "rationale": cls["rationale"]
                + " Exact full conditional history: "
                + ",".join(a["action_id"] for a in history)
                + ". Stable/no-depletion equivalence remains pending B adoption.",
            }
        )
    if len({canonical_digest(r) for r in records}) != len(records):
        raise ValueError("Duplicate compiled rating record")
    config["registries"]["effort"] = envelope(efforts)
    config["registries"]["likelihood"] = envelope(records)
    impact = copy.deepcopy(config["registries"]["impact"]["data"])
    mapping = impact["mappings"][0]
    mapping.update(
        mapping_id="final-cpi-" + scope["query_id"],
        status="pending",
        review_reference=REVIEW,
        numeric_basis_class="estimated_expert_scenario",
    )
    mapping["applicability"].update(
        scenario_id=scope["scenario_id"],
        goal_id=scope["target_goal"]["goal_id"],
        snapshot_id=scope["snapshot_id"],
        operational_horizon=scope["horizon"],
        semantic_goal={
            "version": "semantic-goal/1.0.0",
            "kind": "required_state",
            "target_asset_id": query["target"],
            "required_state": query["target_goal"]["required_state"],
        },
    )
    if semantic_goal is not None:
        mapping["applicability"]["semantic_goal"] = copy.deepcopy(semantic_goal)
    mapping["destination_event"] = scope["target_goal"]["success_event"]
    if consequence:
        mapping.update(
            target_asset_id=query["target"],
            source_event="proposed_" + consequence["class"],
            consequence_rating=consequence["rating"],
            rationale=consequence["rationale"],
        )
        source = {
            "target_impact_assessments": {
                query["target"]: {
                    "success_event": mapping["source_event"],
                    "consequence_rating": consequence["rating"],
                    "rating_status": "unrated",
                    "reviewed_disposition": {
                        "review_status": "pending",
                        "review_reference": REVIEW,
                    },
                    "technical_rationale": consequence["rationale"],
                }
            }
        }
        config["registries"]["impact_source"] = envelope(source)
        mapping["source_release_canonical_digest"] = canonical_digest(source)
    config["registries"]["impact"] = envelope(impact)
    return query


def bind_source_a(case_id):
    """Prepare pilot inputs from the historical declarative query, never its output."""
    query = read(HISTORICAL / "source-a-query.json")
    graph = read(HISTORICAL / "source-a-graph.json")
    cohort = read(PACKAGE / "cohort.json")
    case = next(q for q in cohort["queries"] if q["id"] == case_id)
    actions = read(PACKAGE / "source-a-inventory.json")["actions"]
    query["scenario_reference"] = "final-cpi-v1/" + case_id
    for fact in query["runtime_facts"]:
        fact["scope"] = query["scenario_reference"]
        fact["provenance_reference"] = "scenario://final-cpi-v1/stable-context"
    scope = query["rating_resolution"]["scope"]
    scope.update(
        query_id=case_id,
        scenario_id=query["scenario_reference"],
        scenario_version="1.0.0",
        active_work_budget=case["budget"]["max_steps"],
    )
    scope["target_goal"]["goal_id"] = "final-cpi-dc-admin"
    query["budget"] = case["budget"]
    if case["techniques"] == "all_23":
        query["allowed_techniques"] = sorted(t.id for t in load_catalog())
    initial = []
    if case["source"].endswith("_user"):
        label = "lidia" if "lidia" in case["source"] else "josefa"
        actor = next(a["actor"] for a in actions if a["action_id"] == "action_activate_" + label)
        query["initial_actor"] = actor
        query["initial_state"] = {
            "control": [actor],
            "usable_identity": [[actor, query["authentication_context"]]],
        }
        scope["foothold_node_id"] = actor
        initial = ["action_reset_" + label, "action_activate_" + label]
        actions = [a for a in actions if a["action_id"] not in initial]
    return bind_registry(query, actions, initially_succeeded=initial), graph


def engineering_copy(query, graph):
    """Quarantined synthetic wiring copy; cannot count as raw adopted coverage."""
    query, canonical = copy.deepcopy(query), graph.to_canonical()
    canonical["metadata"]["synthetic"] = True
    canonical["metadata"]["description"] = (
        "Final CPI synthetic wiring derivative; no B numeric adoption"
    )
    facts = graph.snapshot_facts
    if facts is not None:
        facts = replace(facts, graph_sha256=graph_digest(canonical))
    derivative = EngineGraph.from_canonical(canonical, snapshot_facts=facts)
    config = query["rating_resolution"]
    config["policy"] = "synthetic_test_only"
    for role in ("effort", "likelihood"):
        for r in config["registries"][role]["data"]:
            r.update(
                review_status="accepted",
                disposition="rated",
                basis_category="synthetic_test_only",
                numeric_basis_class="synthetic_test_only",
                review_reference="test://final-cpi-v1/wiring-only",
            )
    source = config["registries"]["impact_source"]["data"]
    for r in source["target_impact_assessments"].values():
        if r["rating_status"] == "unrated":
            r["rating_status"] = "rated"
    for mapping in config["registries"]["impact"]["data"]["mappings"]:
        mapping.update(
            status="reviewed",
            evidence_class="synthetic_test_only",
            numeric_basis_class="synthetic_test_only",
            review_reference="test://final-cpi-v1/wiring-only",
            source_release_canonical_digest=canonical_digest(source),
        )
    for role, env in config["registries"].items():
        config["registries"][role] = envelope(env["data"])
    return query, derivative


def historical_pins():
    """Pin every tracked historical rating/scenario artifact without editing it."""
    folders = [
        ROOT / "docs/research/ratings/week3-2026-10-02",
        ROOT / "docs/research/ratings/week3-closeout",
        ROOT / "docs/research/ratings/week4",
        HISTORICAL,
        ROOT / "docs/research/scenarios",
    ]
    return {
        str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
        for folder in folders
        for p in sorted(folder.rglob("*"))
        if p.is_file()
    }
