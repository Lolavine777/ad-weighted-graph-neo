"""Read-only validation of the #256 catalog and frozen review artifacts.

This is a release-package checker, not a rating provider or numeric activator.
No candidate search, external evidence estimation or acceptance mutation occurs here.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from fractions import Fraction
from pathlib import Path

from src.engine.ranking.resolver import generate_rating_lookup_key_p, generate_work_unit_id
from src.engine.semantics import load_catalog
from src.engine.semantics.credentials import OWNERS as CREDENTIAL_OWNERS
from src.engine.semantics.evidence_view import digest
from src.engine.semantics.rbcd import OWNERS as RBCD_OWNERS

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = Path("docs/research/ratings/likelihood-v1")
PENDING = "proposed_pending_b_review"
DISPOSITIONS = {"RATED", "REQUIRES_CONTEXT", "UNRATED_NO_BASIS", "OUT_OF_SCOPE"}
CONTEXT = {
    "scenario_id",
    "scenario_version",
    "snapshot_id",
    "foothold_node_id",
    "actor_id",
    "source_id",
    "target_id",
    "target_class",
    "actor_capability",
    "method",
    "auth_context",
    "resource_context",
    "boundary",
    "scope",
    "policy_id",
    "retry_policy",
    "budget",
    "horizon",
    "target_population",
    "ordered_work_prefix",
    "conditioning_previous_successes",
    "outcome_work_unit_id",
    "success_event",
}


def _require(condition, detail):
    if not condition:
        raise ValueError(detail)


def _read(root, path):
    return json.loads((root / path).read_text(encoding="utf-8"))


def validate_catalog(data, root=ROOT):
    """Reject missing owners, passive/active confusion and unsupported numeric defaults."""
    _require(data["status"] == PENDING and data["version"] == "1.0.0", "catalog governance")
    _require(set(data["required_context"]) == CONTEXT, "incomplete required context")
    owners = load_catalog(root / "configs/attack_semantics.yml")
    actions = {a["technique_id"]: a for a in data["actions"]}
    _require(len(actions) == len(data["actions"]), "duplicate action")
    _require(set(actions) == {t.id for t in owners}, "supported-action coverage drift")
    _require(CREDENTIAL_OWNERS | RBCD_OWNERS <= actions.keys(), "producer coverage drift")
    classes = {c["class_id"]: c for c in data["classes"]}
    _require(len(classes) == len(data["classes"]), "duplicate canonical class")
    for cls in classes.values():
        _require(
            all(
                cls.get(k)
                for k in (
                    "success_event",
                    "required_active_work",
                    "additional_context_requirements",
                    "non_applicability",
                )
            ),
            "incomplete event class",
        )
    for tech in owners:
        entry = actions[tech.id]
        _require(entry["canonical_class"] in classes, "unknown canonical class")
        _require(entry["required_gates"] == list(tech.prerequisites), "prerequisite drift")
        _require(entry["success_effects"] == [e.value for e in tech.effects], "effect drift")
        _require(entry["relationship"] == tech.relationship, "relationship drift")
        _require(entry["source_kinds"] == list(tech.source_kinds), "source-kind drift")
        _require(entry["target_kinds"] == list(tech.target_kinds), "target-kind drift")
        _require(entry["rationale"] and entry["generator_route"], "missing disposition rationale")
        _require(entry["numeric_records"] == [], "unaccepted numeric activation")
        _require(
            (entry["canonical_class"] == "passive_membership_closure")
            == (not tech.action_required),
            "active/passive canonical class mismatch",
        )
        if tech.action_required:
            _require(entry["event_policy"] == "ACTIVE_Q_EVENT", "active owner has no q event")
            _require(entry["disposition"] in DISPOSITIONS - {"RATED"}, "unaccepted rated owner")
        else:
            _require(
                entry["event_policy"] == entry["disposition"] == "NO_Q_EVENT",
                "passive closure has a q event",
            )
    return Counter(entry["disposition"] for entry in actions.values())


def _expected_binding_key(record, query, source):
    bridge = {b["action_id"]: b for b in source["transition_action_bindings"]}
    work_actions = {
        uid: action["action_id"]
        for action in query["bound_actions"]
        for uid in action["referenced_work_unit_ids"]
    }
    meta = query["query_metadata"]
    policy = meta["governance"]["rating_context"]["execution_policy"]
    prefix = []
    for uid in record["prefix"]:
        binding = bridge[work_actions[uid]]
        context = {
            "source_id": binding["source"],
            "method": "default",
            "auth_context": source["authentication_context"],
            "resource_context": None,
            "policy_id": policy["policy_id"],
            "scope": meta["scenario_id"],
        }
        prefix.append(
            generate_work_unit_id(
                binding["technique_id"],
                binding["actor"],
                binding["target"],
                "ctx-" + digest(context).removeprefix("sha256:"),
                meta["work_boundary"],
            )
        )
    binding = bridge[record["outcome_action_id"]]
    return generate_rating_lookup_key_p(
        meta["scenario_id"],
        meta["scenario_version"],
        meta["snapshot_id"],
        meta["foothold_node_id"],
        prefix,
        prefix[-1],
        binding["technique_id"],
        binding["actor"],
        binding["target"],
        source_id=binding["source"],
        method="default",
        budget=meta["active_work_budget"],
        horizon=meta["horizon"],
        boundary=meta["work_boundary"],
        scope=meta["scenario_id"],
        auth_context=source["authentication_context"],
        resource_context=None,
        policy_id=policy["policy_id"],
    ).to_dict()


def validate_bindings(data, root=ROOT):
    """Re-derive every exact contextual identity from the unchanged accepted bridge."""
    _require(
        data["status"] == PENDING and data["numeric_reuse_permitted"] is False,
        "pending binding activation",
    )
    release = _read(root, data["source_release_path"])
    _require(digest(release) == data["source_release_digest"], "source release digest mismatch")
    _require(
        release["bundle_metadata"]["bundle_digest"] == data["source_bundle_digest"],
        "source bundle mismatch",
    )
    query = release["query_projections"]["source_a"]["query"]
    source = _read(root, "docs/research/ratings/week3-closeout/semantic-bridge-plan.json")[
        "sources"
    ]["source_a"]
    records = {r["question_id"]: r for r in query["conditional_bounds_table"]}
    inventory = data["records"]
    _require(len(inventory) == len(records) == 8, "binding inventory incomplete")
    _require(
        {r["source_question_id"] for r in inventory} == records.keys(), "binding questions mismatch"
    )
    _require(len({r["binding_id"] for r in inventory}) == len(inventory), "duplicate binding")
    catalog = _read(root, PACKAGE / "catalog.json")
    action_classes = {a["technique_id"]: a["canonical_class"] for a in catalog["actions"]}
    event_classes = {c["class_id"]: c for c in catalog["classes"]}
    _require(
        len({b["generated_lookup_key_digest"] for b in inventory}) == len(inventory),
        "duplicate generated key",
    )
    for binding in inventory:
        record = records[binding["source_question_id"]]
        _require(
            binding["status"] == PENDING and binding["numeric_reuse_permitted"] is False,
            "unaccepted binding",
        )
        _require(binding["source_record_digest"] == digest(record), "q source digest mismatch")
        _require(
            binding["proposed_interval"] == [record["lower"], record["upper"]],
            "historical q changed",
        )
        lo, hi = map(Fraction, binding["proposed_interval"])
        _require(0 <= lo <= hi <= 1, "invalid interval")
        key = _expected_binding_key(record, query, source)
        _require(
            digest(binding["generated_lookup_key"]) == digest(key), "generated context mismatch"
        )
        _require(binding["generated_lookup_key_digest"] == digest(key), "key digest mismatch")
        _require(binding["historical_ordered_prefix"] == record["prefix"], "history mismatch")
        _require(
            binding["conditioning_previous_successes"] == key["ordered_work_prefix"][:-1],
            "previous-success history mismatch",
        )
        _require(
            binding["historical_outcome_action_id"] == record["outcome_action_id"],
            "outcome mismatch",
        )
        canonical_class = action_classes[key["outcome_technique"]]
        _require(binding["canonical_class"] == canonical_class, "event class mismatch")
        event_class = event_classes[canonical_class]
        _require(binding["success_event"] == event_class["success_event"], "success event mismatch")
        _require(
            binding["required_active_work"] == event_class["required_active_work"],
            "active work mismatch",
        )
        _require(
            binding["rationale"]
            and binding["non_applicability"]
            and binding["review_reference"]
            and binding["version"] == "1.0.0",
            "incomplete binding review metadata",
        )
        context = binding["context"]
        _require(
            context["resource_context"] == key["resource_context"], "contradictory resource context"
        )
        target_class = (
            "User" if key["outcome_technique"] == "scenario_reset_password" else "Computer"
        )
        _require(context["target_class"] == target_class, "target class mismatch")
        _require(
            all(context.get(k) for k in ("actor_capability", "control_scope", "method_policy")),
            "incomplete capability/method scope",
        )
        _require(
            digest(context["event_execution_policy"]) == digest(record["execution_policy"]),
            "execution policy mismatch",
        )
        _require(
            context["retry_policy"]
            == query["query_metadata"]["governance"]["rating_context"]["execution_policy"],
            "retry policy mismatch",
        )
        _require(
            context["target_population"] == record["rating_binding"]["target_population"],
            "population mismatch",
        )
        _require(
            binding["source_pair_digest"] == record["reviewed_disposition"]["pair_digest"],
            "review provenance mismatch",
        )
        _require(binding["evidence_class"] == record["basis_category"], "evidence class mismatch")
        _require(
            binding["evidence_references"] == record["source_references"],
            "evidence reference mismatch",
        )
        _require(
            binding["review_disposition"] == "pending" and binding["reviewer"] == "nairyuuu",
            "review disposition mismatch",
        )
    return inventory


def verify_package(root=ROOT):
    """Verify frozen byte pins, inventory, unchanged numeric sources and review gates."""
    root = Path(root)
    manifest = _read(root, PACKAGE / "manifest.json")
    _require(
        set(manifest["files"])
        == {
            "catalog.json",
            "bindings.json",
            "release-dispositions.json",
            "oracles.json",
            "min-effort-input.json",
        },
        "frozen manifest coverage",
    )
    for name, expected in manifest["files"].items():
        _require(Path(name).name == name, "invalid package path")
        actual = "sha256:" + hashlib.sha256((root / PACKAGE / name).read_bytes()).hexdigest()
        _require(actual == expected, f"frozen artifact drift: {name}")
    catalog = _read(root, PACKAGE / "catalog.json")
    _require(
        {
            "configs/attack_semantics.yml",
            "src/engine/search.py",
            "src/engine/semantics/catalog.py",
            "src/engine/semantics/credentials.py",
            "src/engine/semantics/rbcd.py",
            "src/engine/semantics/evaluator.py",
            "src/engine/semantics/transitions.py",
            "src/engine/ranking/resolver.py",
            "src/engine/ranking/likelihood.py",
            "docs/research/ratings/week4/source-a-p-binding-proposal.json",
            "docs/research/ratings/week3-closeout/reviewed-release.json",
            "docs/research/ratings/week3-closeout/semantic-bridge-plan.json",
            "docs/research/ratings/week4/reviewed-work-unit-classes.json",
            "docs/research/ratings/week4/impact-equivalence-registry.json",
            "docs/research/scenarios/week4-seamless-v1.json",
            "tests/fixtures/attack_scenarios/graphs/two-routes.json",
            "docs/research/ratings/week4/synthetic-a2-e.json",
            "scripts/research/week3_semantic_bridge_probe.py",
            "scripts/research/asrep_inputs.py",
            "tests/frozen_rating_inputs.py",
        }
        <= catalog["source_pins"].keys(),
        "authoritative source pin coverage",
    )
    # The historical catalog/manifest remain frozen by #264. A successor binds
    # those exact bytes while auditing the current executable independently.
    from scripts.research.rating_source_successors import GOAL_SOURCE_FILES

    for version in (3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13):
        previous = _read(root, PACKAGE / f"source-manifest-v{version}.json")
        _require(
            previous["previous_source_manifest_sha256"]
            == "sha256:"
            + hashlib.sha256(
                (root / PACKAGE / f"source-manifest-v{version - 1}.json").read_bytes()
            ).hexdigest(),
            "previous historical source manifest pin mismatch",
        )
    successor = _read(root, PACKAGE / "source-manifest-v14.json")
    _require(successor["schema_version"] == "1.12.0", "source successor version")
    _require(
        successor["historical_manifest_sha256"]
        == "sha256:" + hashlib.sha256((root / PACKAGE / "manifest.json").read_bytes()).hexdigest(),
        "historical manifest pin mismatch",
    )
    _require(
        successor["historical_catalog_sha256"]
        == "sha256:" + hashlib.sha256((root / PACKAGE / "catalog.json").read_bytes()).hexdigest(),
        "historical catalog pin mismatch",
    )
    _require(
        successor["previous_source_manifest_sha256"]
        == "sha256:"
        + hashlib.sha256((root / PACKAGE / "source-manifest-v13.json").read_bytes()).hexdigest(),
        "previous source manifest pin mismatch",
    )
    required_sources = (
        set(catalog["source_pins"])
        | GOAL_SOURCE_FILES
        | {
            "src/engine/program_identity.py",
            "src/engine/top_k.py",
            "src/engine/query.py",
            "src/engine/query_cli.py",
            "scripts/research/likelihood_catalog.py",
        }
    )
    _require(set(successor["source_pins"]) == required_sources, "source pin coverage mismatch")
    for name, expected in successor["source_pins"].items():
        path = root / name
        _require(path.resolve().is_relative_to(root.resolve()), "invalid source path")
        actual = "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()
        _require(actual == expected, f"authoritative source drift: {name}")
    counts = validate_catalog(catalog, root)
    bindings = validate_bindings(_read(root, PACKAGE / "bindings.json"), root)
    decisions = _read(root, PACKAGE / "release-dispositions.json")
    _require(decisions["numeric_activation_permitted"] is False, "release activation")
    original = _read(root, "docs/research/ratings/week4/reviewed-work-unit-classes.json")
    classes = {c["class_id"]: c for c in original["classes"]}
    _require(len(decisions["C"]) == len(classes), "C release coverage")
    _require({d["class_id"] for d in decisions["C"]} == classes.keys(), "C classes mismatch")
    for decision in decisions["C"]:
        _require(decision["status"] == PENDING, "C acceptance mutation")
        cls = classes[decision["class_id"]]
        _require(decision["source_class_digest"] == digest(cls), "C source digest mismatch")
        _require(
            decision["proposed_rubric"]
            == {k: cls[k] for k in ("t1", "t2", "formula", "computed_cost")},
            "C rubric mismatch",
        )
    _require(decisions["status"] == PENDING, "release governance mutation")
    _require(all(d["status"] == PENDING for d in decisions["I"]), "I acceptance mutation")
    source_release = _read(root, "docs/research/ratings/week3-closeout/reviewed-release.json")
    source_i = next(iter(source_release["target_impact_assessments"].values()))
    source_decision, frozen_decision = decisions["I"]
    _require(source_decision["source_record_digest"] == digest(source_i), "I source digest")
    _require(
        source_decision["event"] == source_i["success_event"]
        and source_decision["target_asset_id"] == source_i["target_asset_id"]
        and source_decision["consequence_rating"] == source_i["consequence_rating"],
        "I source consequence mismatch",
    )
    _require(
        digest(source_decision["scope"])
        == digest(
            source_release["query_projections"]["source_a"]["query"]["query_metadata"][
                "target_goal"
            ]
        ),
        "I source goal scope mismatch",
    )
    impact_registry = _read(root, "docs/research/ratings/week4/impact-equivalence-registry.json")
    mapping = next(
        m
        for m in impact_registry["mappings"]
        if m["mapping_id"] == frozen_decision["source_mapping_id"]
    )
    _require(frozen_decision["source_mapping_digest"] == digest(mapping), "I mapping digest")
    _require(
        mapping["directionality"] == "directional"
        and mapping["destination_event"] == "admin_execution_on_C"
        and mapping["applicability"]["goal_id"] == "admin_control(C0)"
        and mapping["applicability"]["required_predicates"] == ["admin"]
        and frozen_decision["consequence_rating"] == mapping["consequence_rating"],
        "I frozen consequence mismatch",
    )
    oracle = _read(root, PACKAGE / "oracles.json")
    _require(oracle["status"] == PENDING, "oracle acceptance mutation")
    for program in oracle["risk_comparison"]["expected_programs"]:
        by_question = {b["source_question_id"]: b for b in bindings}
        intervals = [by_question[q]["proposed_interval"] for q in program["question_ids"]]
        _require(program["q_intervals"] == intervals, "oracle q mismatch")
        lower = upper = Fraction(1)
        for lo, hi in intervals:
            lower *= Fraction(lo)
            upper *= Fraction(hi)
        _require(program["exact_path_interval"] == [str(lower), str(upper)], "oracle P mismatch")
    return {
        "active_actions": sum(v for k, v in counts.items() if k != "NO_Q_EVENT"),
        "passive_actions": counts["NO_Q_EVENT"],
        "dispositions": dict(counts),
        "numeric_activated": 0,
        "pending_bindings": len(bindings),
        "C_release_recommendations": dict(Counter(d["recommendation"] for d in decisions["C"])),
        "status": PENDING,
    }


def proposed_provider_records(root=ROOT):
    """Prepare exact #254 API records without accepting or automatically loading them."""
    verify_package(root)
    records = []
    for binding in _read(Path(root), PACKAGE / "bindings.json")["records"]:
        context = binding["context"]
        records.append(
            {
                **binding["generated_lookup_key"],
                "review_status": binding["status"],
                "disposition": "unrated",
                "lower": binding["proposed_interval"][0],
                "upper": binding["proposed_interval"][1],
                "basis_category": binding["evidence_class"],
                "rationale": binding["rationale"],
                "review_reference": binding["review_reference"],
                "provenance_digest": digest(binding),
                "actor_capability": context["actor_capability"],
                "target_complexity_class": context["target_class"],
                "control_scope": context["control_scope"],
                "retry_policy": context["retry_policy"],
                "target_population": context["target_population"],
                "applicable_queries": ["query-seamless-host-to-dc-v1"],
            }
        )
    return records


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    print(json.dumps(verify_package(), sort_keys=True))


if __name__ == "__main__":
    main()
