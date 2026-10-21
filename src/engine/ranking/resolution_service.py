"""Public generated rating boundary; numeric authority remains with #246 providers."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from copy import deepcopy
from dataclasses import asdict

from scripts.research.empirical_qi_estimator import TrialObservation
from src.engine.ranking.adapter_145 import _audit_value
from src.engine.ranking.effort_registry import (
    ClassApplicability,
    ReviewedWorkUnitClassEffortProvider,
    WorkUnitClass,
    WorkUnitClassRegistry,
    get_default_work_unit_registry,
)
from src.engine.ranking.likelihood import (
    EmpiricalLikelihoodProvider,
    ReviewedScenarioLikelihoodProvider,
)
from src.engine.ranking.models import RankingValidationError
from src.engine.ranking.resolver import (
    BasisClassification,
    RatingResolver,
    ReasonCode,
    ResolutionResult,
    ResolverDisposition,
    ReviewedEquivalenceImpactProvider,
    generate_work_unit_id,
)
from src.engine.semantics import FactOrigin, apply_transition
from src.engine.semantics.credentials import replay_path

CONFIG_VERSION = "public-rating-resolution/1.1.0"
COVERAGE_VERSION = "public-rating-coverage/1.1.0"


def canonical_digest(value):
    encoded = json.dumps(
        value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _object(value, name):
    if not isinstance(value, Mapping):
        raise RankingValidationError(f"{name} must be an object")
    return deepcopy(dict(value))


def finalize_generated_rating_coverage(coverage, ranking_result):
    """Complete public coverage only after canonical adaptation and evaluation.

    Resolver materialization is not canonical admission. Numeric refusals remain
    assessed candidates; only adapter/validator rejection diagnostics belong in
    canonical_rejections. Both public entry points use this same finalization.
    """
    coverage["binding"]["canonical_admitted_candidates"] = ranking_result["search_audit"][
        "candidates_adapted"
    ]
    coverage["binding"]["canonical_rejections"] = {
        cid: {
            "reason": diagnostic["reasons"][0],
            "reasons": list(diagnostic["reasons"]),
            "diagnostic": diagnostic["assessment"]["diagnostic"],
        }
        for cid, diagnostic in ranking_result["diagnostics"].items()
        if {"adapter_ineligible", "canonical_candidate_invalid"}.intersection(diagnostic["reasons"])
    }
    for cid, summary in coverage["candidate_summaries"].items():
        assessment = ranking_result["eligible_candidates"].get(cid)
        if assessment is None:
            assessment = ranking_result["diagnostics"].get(cid, {}).get("assessment", {})
        summary["semantic_status"] = assessment.get("status", "unknown")
        summary["numeric_complete"] = all(
            summary[dimension] for dimension in ("c_complete", "p_complete", "i_complete")
        )


class _PolicyProvider:
    """Enforce public policy without bypassing a provider's refusal."""

    def __init__(self, provider, policy, guard=None):
        self.provider = provider
        self.policy = policy
        self.name = provider.name
        self.provider_version = provider.provider_version
        self.guard = guard

    def __getattr__(self, method):
        if method not in ("resolve_effort", "resolve_likelihood", "resolve_impact"):
            raise AttributeError(method)

        def resolve(*args):
            result = getattr(self.provider, method)(*args)
            if (
                result.disposition == ResolverDisposition.RATED
                and result.basis_category == "synthetic_test_only"
                and self.policy != "synthetic_test_only"
            ):
                return ResolutionResult(
                    disposition=ResolverDisposition.REFUSED,
                    reason_code=ReasonCode.PREREQUISITE_GATE_REFUSAL,
                    reason_detail="Production policy refuses synthetic_test_only numeric basis",
                    provider_name=self.name,
                    provider_version=self.provider_version,
                    basis_category=result.basis_category,
                    provenance_digest=result.provenance_digest,
                    review_reference=result.review_reference,
                    numeric_basis_class=result.numeric_basis_class,
                    review_status=result.review_status,
                )
            if result.disposition == ResolverDisposition.RATED and self.guard is not None:
                return self.guard(result, args)
            return result

        return resolve


def load_resolution_config(config):
    """Load embedded native provider registries and verify canonical JSON digests.

    No implicit defaults activate the repository's proposed numeric catalogs.
    Paths are loaded by CLI, so API and CLI operate on identical JSON values.
    """
    config = _object(config, "rating_resolution")
    unknown = config.keys() - {"version", "mode", "policy", "scope", "registries"}
    if unknown:
        raise RankingValidationError(f"Unknown rating_resolution fields: {sorted(unknown)}")
    if (
        config.get("version")
        not in (
            CONFIG_VERSION,
            "public-rating-resolution/1.0.0",
        )
        or config.get("mode", "automatic") != "automatic"
    ):
        raise RankingValidationError("Unsupported rating_resolution version/mode")
    policy = config.get("policy", "production")
    if policy not in ("production", "synthetic_test_only"):
        raise RankingValidationError("Unknown rating provider policy")
    scope = _object(config.get("scope"), "rating_resolution.scope")
    required = {
        "query_id",
        "scenario_id",
        "scenario_version",
        "snapshot_id",
        "foothold_node_id",
        "work_boundary",
        "horizon",
        "active_work_budget",
        "evaluation_mode",
        "target_goal",
    }
    if required - scope.keys():
        raise RankingValidationError(
            f"Missing rating scope fields: {sorted(required - scope.keys())}"
        )
    if "facts_ledger" in scope:
        raise RankingValidationError("Automatic facts_ledger is owned by semantic materialization")
    optional = {
        "policy_id",
        "governance",
        "actor_capability",
        "target_complexity_class",
        "control_scope",
        "retry_policy",
        "target_population",
        "recovery_metadata",
    }
    if scope.keys() - required - optional:
        raise RankingValidationError("Unknown automatic rating scope fields")
    for name in required - {"active_work_budget", "target_goal"}:
        if not isinstance(scope[name], str) or not scope[name].strip():
            raise RankingValidationError(f"Rating scope {name} must be a non-empty string")
    goal = _object(scope["target_goal"], "rating scope target_goal")
    for name in ("target_asset_id", "success_event", "goal_id"):
        if not isinstance(goal.get(name), str) or not goal[name].strip():
            raise RankingValidationError(f"rating target_goal requires {name}")
    registries = _object(config.get("registries", {}), "rating registries")
    if registries.keys() - {"effort", "likelihood", "impact", "impact_source", "empirical", "work"}:
        raise RankingValidationError("Unknown rating registry role")
    data = {}
    audit = {}
    for role, envelope in sorted(registries.items()):
        envelope = _object(envelope, f"{role} registry envelope")
        if set(envelope) != {"version", "sha256", "data"} or envelope["version"] != "1.0.0":
            raise RankingValidationError(f"Unsupported {role} registry envelope")
        if envelope["sha256"] != canonical_digest(envelope["data"]):
            raise RankingValidationError(f"Registry integrity digest mismatch: {role}")
        data[role] = envelope["data"]
        audit[role] = {"version": envelope["version"], "sha256": envelope["sha256"]}
    return config, scope, policy, data, audit


def _binding_refusal(result, detail, *, missing=False, malformed=False):
    return ResolutionResult(
        disposition=ResolverDisposition.REFUSED,
        reason_code=(
            ReasonCode.MALFORMED_INPUT
            if malformed
            else ReasonCode.MISSING_EVIDENCE
            if missing
            else ReasonCode.OUT_OF_SCOPE
        ),
        reason_detail=detail,
        provider_name=result.provider_name,
        provider_version=result.provider_version,
        basis_category=result.basis_category,
        provenance_digest=result.provenance_digest,
        review_reference=result.review_reference,
        numeric_basis_class=result.numeric_basis_class,
        review_status=result.review_status,
    )


def _impact_goal_guard(data, semantic_goal, scenario_reference):
    """Constrain the exact mapping selected by the native, authoritative provider.

    Its provenance digest identifies mapping + source; do not reselect a different
    mapping, infer equivalence from an event name, or override a native refusal.
    """

    def guard(result, args):
        _, target, _, scope = args
        packet = data.get("impact_source", {})
        source = packet.get("query", packet).get("target_impact_assessments", {}).get(target)
        selected = [
            mapping
            for mapping in data["impact"].get("mappings", [])
            if canonical_digest({"mapping": mapping, "source": source}) == result.provenance_digest
        ]
        if not selected:
            raise RankingValidationError("Native impact selection provenance cannot be verified")
        applicability = selected[0].get("applicability", {})
        if applicability.get("scenario_id") and scenario_reference is None:
            return _binding_refusal(
                result, "scenario_authority_missing: scoped I record", missing=True
            )
        if semantic_goal is None:
            return _binding_refusal(
                result,
                "semantic_goal_unverifiable: callable has no declared terminal capabilities",
                missing=True,
            )
        declared = applicability.get("semantic_goal")
        if declared is None:
            return _binding_refusal(
                result, "semantic_goal_binding_missing: reviewed I mapping", missing=True
            )
        from src.engine.query import IdentityResolver, semantic_goal_from_dict

        try:
            semantic_goal_from_dict(declared, IdentityResolver({}))
        except KeyError, TypeError, ValueError:
            return _binding_refusal(
                result, "Malformed reviewed semantic goal descriptor", malformed=True
            )
        if not isinstance(result.review_reference, str) or not result.review_reference.strip():
            return _binding_refusal(
                result, "semantic_goal_binding_missing: review reference", missing=True
            )
        if declared != semantic_goal:
            return _binding_refusal(
                result, "semantic_goal_mismatch: reviewed I consequence binding"
            )
        for name, expected in (
            ("snapshot_id", scope["snapshot_id"]),
            ("goal_id", scope["target_goal"]["goal_id"]),
        ):
            if applicability.get(name) is None:
                return _binding_refusal(
                    result, f"semantic_goal_binding_missing: {name}", missing=True
                )
            if applicability[name] != expected:
                return _binding_refusal(result, f"semantic_goal_mismatch: {name}")
        return result

    return guard


def _providers(data, policy, *, semantic_goal=None, scenario_reference=None):
    classes = []
    if "effort" in data:
        if not isinstance(data["effort"], list):
            raise RankingValidationError("effort registry data must be a class list")
        for record in data["effort"]:
            record = _object(record, "effort class")
            applicability = _object(record.pop("applicability", None), "effort applicability")
            if "predicate" in applicability:
                raise RankingValidationError("Executable effort predicates are not public JSON")
            predicate_name = applicability.pop("semantic_predicate", None)
            if predicate_name:
                inventory_class = get_default_work_unit_registry().get(record.get("class_id"))
                predicate = inventory_class.applicability.predicate if inventory_class else None
                if predicate is None or predicate.__name__ != predicate_name:
                    raise RankingValidationError("Unknown named effort applicability predicate")
                applicability["predicate"] = predicate
            for key in (
                "techniques",
                "methods",
                "boundaries",
                "work_classes",
                "scopes",
                "aliases",
                "source_ids",
                "snapshot_ids",
                "work_unit_digests",
            ):
                if key in applicability and applicability[key] is not None:
                    if not isinstance(applicability[key], list) or any(
                        not isinstance(value, str) or not value.strip()
                        for value in applicability[key]
                    ):
                        raise RankingValidationError(
                            f"Effort applicability {key} must be a string list"
                        )
                    applicability[key] = tuple(applicability[key])
            if "disposition" in record:
                record["disposition"] = ResolverDisposition(record["disposition"])
            if "basis_category" in record:
                record["basis_category"] = BasisClassification(record["basis_category"]).value
            computed = record.pop("computed_cost", None)
            cls = WorkUnitClass(**record, applicability=ClassApplicability(**applicability))
            if computed is not None and computed != cls.computed_cost:
                raise RankingValidationError("Effort class computed_cost disagrees with rubric")
            classes.append(cls)
    work_registry = WorkUnitClassRegistry(classes)
    effort = [ReviewedWorkUnitClassEffortProvider(work_registry)]

    def effort_guard(result, args):
        if scenario_reference is None:
            if any(
                args[0].technique in rule["techniques"] and args[0].method == rule["method"]
                for rule in data.get("work", [])
            ):
                return _binding_refusal(
                    result, "scenario_authority_missing: scoped work decomposition", missing=True
                )
            matches, _, _ = work_registry.match(*args)
            if any(cls.applicability.scopes is not None for cls in matches):
                return _binding_refusal(
                    result, "scenario_authority_missing: scoped C class", missing=True
                )
        return result

    def likelihood_guard(result, args):
        if scenario_reference is None:
            return _binding_refusal(
                result, "scenario_authority_missing: scoped P record", missing=True
            )
        return result

    likelihood = []
    if "empirical" in data:
        empirical = _object(data["empirical"], "empirical provider config")
        # The merged #238 production export gate remains authoritative. No bounds import.
        if set(empirical) - {"manifest", "dataset_classification", "observations"}:
            raise RankingValidationError("Unsupported empirical export; #238 gate required")
        if "observations" in empirical:
            if not isinstance(empirical["observations"], list):
                raise RankingValidationError("Empirical observations must be a list")
            empirical["observations"] = [
                TrialObservation(**_object(record, "empirical trial"))
                for record in empirical["observations"]
            ]
        likelihood.append(EmpiricalLikelihoodProvider(**empirical, for_production_ranking=True))
    if "likelihood" in data:
        if not isinstance(data["likelihood"], list):
            raise RankingValidationError("likelihood registry data must be a record list")
        likelihood.append(ReviewedScenarioLikelihoodProvider(data["likelihood"]))
    impact = []
    if "impact" in data:
        impact.append(
            ReviewedEquivalenceImpactProvider(
                _object(data["impact"], "impact registry"),
                source_packet=data.get("impact_source"),
            )
        )
    return RatingResolver(
        effort_providers=[_PolicyProvider(p, policy, effort_guard) for p in effort],
        # Both empirical manifests and reviewed scenario records bind P to scenario_id.
        # Caller rating scope alone cannot authorize either provider's rated result.
        likelihood_providers=[_PolicyProvider(p, policy, likelihood_guard) for p in likelihood],
        impact_providers=[
            _PolicyProvider(p, policy, _impact_goal_guard(data, semantic_goal, scenario_reference))
            for p in impact
        ],
    )


def _state_atoms(state):
    return {
        "state:" + canonical_digest([name, _audit_value(value)])
        for name in state.__dataclass_fields__
        for value in getattr(state, name)
    }


def resolve_generated_rating_inputs(config, graph, materialized, search_result):
    """Materialize authentic generated paths before canonical adaptation/evaluation."""
    config, scope, policy, registries, registry_audit = load_resolution_config(config)
    if materialized.scenario_reference is not None and (
        not isinstance(materialized.scenario_reference, str)
        or not materialized.scenario_reference.strip()
    ):
        raise RankingValidationError("Semantic scenario reference must be non-empty or absent")
    for name, expected in (
        ("snapshot_id", graph.metadata["snapshot_id"]),
        ("foothold_node_id", materialized.initial_actor),
        ("evaluation_mode", materialized.evaluation_mode),
        ("active_work_budget", materialized.budget.max_steps),
    ):
        if scope[name] != expected:
            raise RankingValidationError(f"Rating scope {name} conflicts with semantic query")
    if scope["target_goal"]["target_asset_id"] != materialized.target:
        raise RankingValidationError("Rating target conflicts with semantic query")
    if (
        materialized.scenario_reference is not None
        and scope["scenario_id"] != materialized.scenario_reference
    ):
        raise RankingValidationError("Rating scenario conflicts with semantic query")
    if policy == "synthetic_test_only" and graph.metadata.get("synthetic") is not True:
        raise RankingValidationError("Synthetic policy requires an explicitly synthetic graph")
    scope["is_synthetic_fixture"] = graph.metadata.get("synthetic") is True
    semantic_goal = materialized.semantic_goal.to_dict() if materialized.semantic_goal else None
    if semantic_goal is not None:
        if scope.get("semantic_goal") not in (None, semantic_goal):
            raise RankingValidationError(
                "Rating state-goal descriptor conflicts with semantic query"
            )
        scope["semantic_goal"] = semantic_goal
    goal_digest = canonical_digest(semantic_goal) if semantic_goal else None
    goal_predicate = "semantic_goal:" + materialized.target + ":" + (goal_digest or "opaque")
    declared = scope["target_goal"].get("required_predicates")
    if declared is not None and declared != [goal_predicate]:
        raise RankingValidationError("Automatic goal predicates must match semantic goal binding")
    scope["target_goal"]["required_predicates"] = [goal_predicate]
    layers = {goal_predicate: 3}
    observations = {}
    assumptions = {}
    for predicate in sorted(_state_atoms(materialized.initial_attack_state)):
        layers[predicate] = 3
        observations[predicate] = {
            "predicate": predicate,
            "truth_value": True,
            "layer": 3,
            "origin": "declared_initial_state",
        }
    bindings = {}
    shared_preparations = {}
    work_rules = registries.get("work", [])
    if not isinstance(work_rules, list):
        raise RankingValidationError("work registry must be a rule list")
    for rule in work_rules:
        if (
            not isinstance(rule, dict)
            or rule.get("review_status") != "accepted"
            or not rule.get("review_reference")
            or not isinstance(rule.get("techniques"), list)
            or not rule["techniques"]
            or any(not isinstance(t, str) or not t.strip() for t in rule["techniques"])
            or not isinstance(rule.get("preparation_technique"), str)
            or not rule["preparation_technique"].strip()
            or not isinstance(rule.get("method"), str)
            or not rule["method"].strip()
            or rule.get("scenario_id") != scope["scenario_id"]
            or rule.get("boundary") != scope["work_boundary"]
        ):
            raise RankingValidationError("Work preparation rule requires accepted scoped review")
        BasisClassification(rule.get("basis_category"))
        if policy == "production" and rule.get("basis_category") == "synthetic_test_only":
            raise RankingValidationError("Production policy refuses synthetic work binding rule")
    candidates = []
    for index, path in enumerate(search_result.paths, 1):
        candidate_id = f"generated_{index:04d}"
        if not path.transition_history:
            continue  # existing zero-work disposition; never manufacture P/I
        replay_path(path, graph, materialized.catalog)
        for step_index, step in enumerate(path.transition_history):
            result = step.result
            requires = _state_atoms(result.before)
            adds = _state_atoms(result.additions)
            for decision in result.decisions:
                if decision.fact is None:
                    continue  # state/structural conditions already checked by typed replay
                fact = decision.fact
                predicate = "runtime:" + canonical_digest(
                    [fact.predicate, fact.subject, fact.target, fact.scope]
                )
                requires.add(predicate)
                layers[predicate] = 3
                record = {
                    "predicate": predicate,
                    "truth_value": fact.value,
                    "layer": 3,
                    "rationale": fact.rationale or decision.rationale,
                    "provenance_reference": fact.provenance_reference,
                    "origin": str(fact.origin),
                }
                bucket = (
                    assumptions if fact.origin == FactOrigin.DECLARED_ASSUMPTION else observations
                )
                if predicate in bucket and bucket[predicate] != record:
                    raise RankingValidationError("Conflicting semantic runtime context")
                bucket[predicate] = record
            if materialized.is_success_state(apply_transition(result.before, result)):
                adds.add(goal_predicate)
            for predicate in requires | adds:
                layers[predicate] = 3
            request = result.request
            binding = {
                "requires": sorted(requires),
                "adds": sorted(adds),
                "method": result.technique.relationship,
                "auth_context": materialized.runtime_context.authentication_context,
                "resource_context": canonical_digest(asdict(request.rbcd_binding))
                if request.rbcd_binding
                else None,
                "is_passive_closure": not result.technique.action_required,
            }
            for decision in result.decisions:
                if decision.fact is not None and decision.predicate == "recovery_success":
                    metadata = dict(decision.fact.assumption_metadata or {})
                    recovery = {
                        key: metadata[key]
                        for key in ("method", "budget", "horizon")
                        if key in metadata
                    }
                    model = metadata.get("recovery_model")
                    declared_digest = metadata.get("recovery_model_digest")
                    if model is not None:
                        actual_digest = canonical_digest(model)
                        if declared_digest != actual_digest:
                            raise RankingValidationError(
                                "Recovery model declaration digest mismatch"
                            )
                        recovery["recovery_model_digest"] = actual_digest
                    elif declared_digest is not None:
                        raise RankingValidationError("Recovery model declaration is missing")
                    if not recovery:
                        continue
                    if "recovery_metadata" in scope and scope["recovery_metadata"] != recovery:
                        raise RankingValidationError(
                            "Rating recovery context conflicts with semantic history"
                        )
                    binding["method"] = recovery.get("method", binding["method"])
                    binding["resource_context"] = canonical_digest(recovery)
            matching_rules = [
                rule
                for rule in work_rules
                if materialized.scenario_reference is not None
                and request.technique_id in rule["techniques"]
                and rule.get("method") == binding["method"]
            ]
            if len(matching_rules) > 1:
                raise RankingValidationError("Conflicting work preparation rules")
            if matching_rules and result.technique.action_required:
                rule = matching_rules[0]
                context = {
                    "actor": request.actor,
                    "target": request.target,
                    "auth_context": binding["auth_context"],
                    "resource_context": binding["resource_context"],
                    "policy_id": scope.get("policy_id"),
                    "scenario_id": scope["scenario_id"],
                    "method": rule["method"],
                }
                prep_id = generate_work_unit_id(
                    rule["preparation_technique"],
                    request.actor,
                    request.target,
                    "ctx-" + canonical_digest(context).removeprefix("sha256:"),
                    scope["work_boundary"],
                )
                binding["shared_prep_key"] = prep_id
                shared_preparations[prep_id] = {
                    "work_unit_id": prep_id,
                    "technique": rule["preparation_technique"],
                    "actor_id": request.actor,
                    "source_id": request.actor,
                    "target_id": request.target,
                    "method": rule["method"],
                    "auth_context": binding["auth_context"],
                    "resource_context": binding["resource_context"],
                    "policy_id": scope.get("policy_id"),
                    "rating_status": "unrated",
                }
            bindings[(candidate_id, step_index)] = binding
        candidates.append(
            {
                "candidate_id": candidate_id,
                "path_result": path,
                "target_asset_id": materialized.target,
                "transition_history": path.transition_history,
                "nodes": path.nodes,
                "runtime_context": path.runtime_context,
                "final_state": path.final_state,
                "scenario_reference": path.scenario_reference,
            }
        )
    scope["facts_ledger"] = {
        "predicate_layers": layers,
        "observed_facts": list(observations.values()),
        "assumed_facts": list(assumptions.values()),
    }
    configured_resolver = _providers(
        registries,
        policy,
        semantic_goal=semantic_goal,
        scenario_reference=materialized.scenario_reference,
    )
    resolver = configured_resolver if candidates else RatingResolver()
    # Resolver's typed-path adapter hydrates graph edges in the shared orchestration boundary.
    from src.engine.ranking.orchestration import _hydrate_path_edges, coverage_from_search_result

    for candidate in candidates:
        candidate.update(_hydrate_path_edges(candidate["path_result"], graph.to_canonical()))
    output = resolver.resolve(
        candidates,
        scope,
        transition_bindings=bindings,
        shared_preparation_units=shared_preparations,
    )
    for candidate, envelope in zip(candidates, output.candidate_envelopes, strict=True):
        candidate["action_mapping"] = envelope["bound_action_ids"]
        candidate["route_id"] = f"{candidate['candidate_id']}:route:0"
    coverage = output.coverage_report
    coverage["providers_attempted"] = sorted(
        {
            trace["provider"]
            for candidate in coverage["candidates"].values()
            for record in [
                *candidate["effort"]["units"].values(),
                *candidate["likelihood"]["prefixes"],
                candidate["impact"],
            ]
            for trace in record["provider_trace"]
        }
    )
    coverage.update(
        {
            "public_coverage_version": COVERAGE_VERSION,
            "mode": "automatic",
            "policy": policy,
            "configuration_digest": canonical_digest(config),
            "registries": registry_audit,
            "semantic_goal": {"descriptor": semantic_goal, "sha256": goal_digest},
            "scenario_authority": {
                "semantic_reference": materialized.scenario_reference,
                "rating_reference": scope["scenario_id"],
                "status": "matched" if materialized.scenario_reference else "absent",
                "missing_reference_is_wildcard": False,
            },
            "semantic_search": {
                **coverage_from_search_result(search_result, materialized.budget),
                "complete": search_result.complete,
                "termination": search_result.truncation_reason or "search_exhausted",
                "allowed_techniques": [t.id for t in materialized.catalog],
                "numeric_completeness_implies_search_completeness": False,
            },
            "binding": {
                "generated_candidates": len(search_result.paths),
                "materialized_candidates": len(candidates),
                "generated_steps": sum(len(p.transition_history) for p in search_result.paths),
                "materialized_steps": len(bindings),
                "refused_steps": [],
                "zero_action_initial_goal": bool(search_result.paths and not candidates),
                "canonical_work_units": len(output.ranking_query["work_units_ledger"]),
                "passive_steps": sum(b["is_passive_closure"] for b in bindings.values()),
                "actions": output.ranking_query["bound_actions"],
                "shared_preparation_units": sorted(shared_preparations),
                "unapplied_preparation_rules": [
                    {"techniques": rule["techniques"], "reason": "scenario_authority_missing"}
                    for rule in work_rules
                    if materialized.scenario_reference is None
                ],
                "unsupported_work_units": sorted(
                    {
                        uid
                        for candidate in coverage["candidates"].values()
                        for uid, record in candidate["effort"]["units"].items()
                        if any(
                            attempt["reason_code"] == "unsupported_technique"
                            for attempt in record["provider_trace"]
                        )
                    }
                ),
            },
            "denominators": {
                "effort.total_units": "distinct canonical active work IDs within each candidate",
                "likelihood.total_prefixes": "ordered first-use active-work prefixes per candidate",
                "impact": "one target asset/success event/consequence scope per query",
                "aggregate_summary.total_unresolved_gaps": "unique C IDs + P prefixes + target I",
            },
            "providers_configured": [
                {"name": p.name, "version": p.provider_version}
                for chain in (
                    configured_resolver.effort_providers,
                    configured_resolver.likelihood_providers,
                    configured_resolver.impact_providers,
                )
                for p in chain
            ],
        }
    )
    if not candidates:
        # No success-event assessment exists for an initial-state goal or empty search.
        coverage["impact_evaluation"] = "not_applicable_without_active_candidate"
        coverage["unresolved_gaps"] = []
        coverage["aggregate_summary"]["total_unresolved_gaps"] = 0
    all_units = {
        uid: rec
        for c in coverage["candidates"].values()
        for uid, rec in c["effort"]["units"].items()
    }
    all_prefixes = {
        tuple(rec["prefix"]): rec
        for c in coverage["candidates"].values()
        for rec in c["likelihood"]["prefixes"]
    }
    coverage["numeric_requests"] = {
        "C": {
            "required": len(all_units),
            "rated": sum(rec["disposition"] == "rated" for rec in all_units.values()),
        },
        "P": {
            "required": len(all_prefixes),
            "rated": sum(rec["disposition"] == "rated" for rec in all_prefixes.values()),
        },
        "I": {
            "required": int(bool(candidates)),
            "rated": int(
                bool(candidates)
                and next(iter(coverage["candidates"].values()))["impact"]["disposition"] == "rated"
            ),
        },
    }
    return output.ranking_query, candidates, coverage
