"""Versioned B decisions over native envelopes; no search, estimator or auto-adoption."""

from __future__ import annotations

import argparse
import copy
import json
from datetime import datetime
from pathlib import Path
from urllib.parse import unquote, urlsplit

from scripts.research.final_cpi_profiles import PACKAGE, bind_source_a, read, validate_package
from scripts.research.issue250_public_probe import envelope
from src.engine.ranking.resolution_service import canonical_digest

VERSION = "final-cpi-numeric-release/1.0.0"
INPUTS = (
    "profile.json",
    "taxonomy.json",
    "applicability-v1.1.json",
    "cohort.json",
    "source-a-inventory.json",
)
INITIAL_CLASSES = ("directory_password_reset", "reset_identity_activation", "winrm_admin_execution")
SOURCE_CASES = (
    "source-a-projection",
    "source-a-full-raw-four",
    "source-a-full-generator",
    "lidia-full-generator",
    "josefa-full-generator",
)
WAVE2_VERSION = "final-cpi-numeric-release/2.0.0"
WAVE2_PACKAGE = PACKAGE.parent / "final-cpi-release-v2"
WAVE2_NUMERIC_REFERENCE = (
    "https://github.com/nairyuuu/ad-weighted-graph/issues/267#issuecomment-6142406787"
)
WAVE2_CLASSES = (
    "host_admin_execution",
    "group_membership_mutation",
    "grant_write_dacl",
    "grant_generic_all",
    "winrm_command_session",
    "rbcd_secret_acquisition",
    "rbcd_service_preparation",
    "rbcd_descriptor_mutation",
    "rbcd_service_delegation",
    "rbcd_admin_execution",
    "asrep_material_request",
    "kerberoast_material_request",
    "asrep_password_recovery",
    "kerberoast_password_recovery",
)


def template_wave2(graph, raw_dir):
    """Pin remaining frozen contexts without claiming B history approval."""
    from scripts.research.final_cpi_coverage import prepare_roasting
    from scripts.research.final_cpi_extension import prepare_extension
    from scripts.research.issue250_public_probe import frozen_inputs
    from src.parser.snapshot_facts import graph_digest

    validate_package()
    original = read(PACKAGE / "cohort.json")
    raw, frozen, _ = frozen_inputs(raw_dir, original["baseline_revision"])
    if (
        graph_digest(raw.to_canonical()) != graph_digest(graph.to_canonical())
        or raw.snapshot_facts != graph.snapshot_facts
    ):
        raise ValueError("Wave 2 requires the exact manifest-verified raw graph")
    queries = {}
    for case in original["queries"]:
        if case["id"] not in SOURCE_CASES:
            queries[case["id"]] = prepare_roasting(case, graph, frozen)
    for case in read(PACKAGE / "supplementary-cohort.json")["queries"]:
        if case["id"] != "rbcd-unassumed":
            queries[case["id"]] = prepare_extension(case, graph, raw_dir)[0]
    profile = read(PACKAGE / "profile.json")
    classes = {c["class_id"]: c for c in profile["classes"]}
    domains, impacts = {}, {}
    for case_id, query in queries.items():
        config = query["rating_resolution"]
        registries = config["registries"]
        mapping = registries["impact"]["data"]["mappings"][0]
        scope = config["scope"]
        domains[case_id] = {
            "query_digest": canonical_digest(query),
            "control_scope": copy.deepcopy(scope["control_scope"]),
            "retry_policy": copy.deepcopy(scope["retry_policy"]),
            "horizon": scope["horizon"],
            "history_records_digest": canonical_digest(registries["likelihood"]["data"]),
            "work_units_digest": canonical_digest(registries["effort"]["data"]),
            "registry_counts": {
                role: len(registries[role]["data"]) for role in ("effort", "likelihood")
            },
            "typed_goal": {
                "version": mapping["applicability"]["semantic_goal"]["version"],
                "kind": mapping["applicability"]["semantic_goal"]["kind"],
                "required_state_fields": sorted(
                    mapping["applicability"]["semantic_goal"].get("required_state", {})
                ),
                "canonical_digest": canonical_digest(mapping["applicability"]["semantic_goal"]),
            },
            "consequence_rating": mapping["consequence_rating"],
        }
        impacts[case_id] = {
            "decision": "pending",
            "rating": mapping["consequence_rating"],
            "rationale": mapping["rationale"],
        }
    return {
        "version": WAVE2_VERSION,
        "release_id": "final-cpi-wave2-v2",
        "status": "pending_b_numeric_review",
        "input_pins": {
            **input_pins(),
            "supplementary-cohort.json": canonical_digest(
                read(PACKAGE / "supplementary-cohort.json")
            ),
        },
        "numeric_decision_reference": WAVE2_NUMERIC_REFERENCE,
        "history_model": copy.deepcopy(profile["history_model"]),
        "history_decision": {
            "decision": "pending",
            "rationale": "Review only the enumerated exact histories and unique canonical work "
            "identities. Prior rights/preparation effects are conditioned prerequisites; "
            "no fresh-secret invalidation, retry depletion or independence uplift. "
            "Numeric approval alone does not approve this domain.",
        },
        "review": {
            "purpose": "numeric_context_history_adoption",
            "reviewer": None,
            "reviewed_at": None,
            "reference": None,
            "confirmation": None,
        },
        "query_pins": {case: canonical_digest(q) for case, q in queries.items()},
        "context_domains": domains,
        "contexts": {
            case: {
                "decision": "pending",
                "rationale": "Review this exact actor/resource/target, typed goal, snapshot, "
                "retry/transport and complete enumerated history domain separately; "
                "no transfer from another query context.",
            }
            for case in queries
        },
        "classes": {
            name: {
                "values": {k: classes[name][k] for k in ("t1", "t2", "cost", "lower", "upper")},
                "C": {"decision": "pending", "rationale": classes[name]["rationale"]},
                "P": {
                    "decision": "needs_evidence" if classes[name]["lower"] is None else "pending",
                    "rationale": classes[name]["rationale"],
                },
            }
            for name in WAVE2_CLASSES
        },
        "impacts": impacts,
        "limitations": [
            "Existing B numeric proposals only; exact context/history adoption remains pending.",
            "Original, supported raw supplement and diagnostic controls "
            "retain separate denominators.",
            "Natural-password recovery P and recovered-identity activation remain unadopted.",
            "RDP/session extraction lack supported policy; no new binding or probability.",
            "RBCD HTTP/SPN and runtime conditions are declared scenario metadata, not raw proof.",
            "No source ranking, batch or chokepoint sensitivity acceptance.",
        ],
    }


def _expected_release(release):
    if release.get("version") != WAVE2_VERSION:
        return template()
    expected = read(WAVE2_PACKAGE / "decisions.pending.json")
    actual_pins = {
        **input_pins(),
        "supplementary-cohort.json": canonical_digest(read(PACKAGE / "supplementary-cohort.json")),
    }
    if expected["input_pins"] != actual_pins:
        raise ValueError("Wave 2 candidate input pin mismatch")
    profile = {c["class_id"]: c for c in read(PACKAGE / "profile.json")["classes"]}
    if expected["classes"].keys() != set(WAVE2_CLASSES):
        raise ValueError("Wave 2 candidate class expansion")
    for name, entry in expected["classes"].items():
        if entry["values"] != {k: profile[name][k] for k in ("t1", "t2", "cost", "lower", "upper")}:
            raise ValueError("Wave 2 candidate numeric drift")
    return expected


def _impact(release, case_id):
    return release["impacts"][case_id] if release["version"] == WAVE2_VERSION else release["impact"]


def _review_identity(reference):
    """Identify aliases only to refuse reuse of already forbidden authority."""
    parts = urlsplit(reference.strip())
    return (
        (parts.hostname or "").lower().removeprefix("www."),
        unquote(parts.path).lower().replace("/issues/", "/pull/").rstrip("/"),
        unquote(parts.fragment).lower().rstrip("/"),
    )


def input_pins():
    return {name: canonical_digest(read(PACKAGE / name)) for name in INPUTS}


def template():
    """Prepare concrete review questions without recording a human decision."""
    validate_package()
    profile = read(PACKAGE / "profile.json")
    classes = {c["class_id"]: c for c in profile["classes"]}
    return {
        "version": VERSION,
        "release_id": "final-cpi-source-a-v1",
        "status": "pending_b_numeric_review",
        "input_pins": input_pins(),
        "history_model": copy.deepcopy(profile["history_model"]),
        "review": {
            "purpose": "numeric_context_history_adoption",
            "reviewer": None,
            "reviewed_at": None,
            "reference": None,
            "confirmation": None,
        },
        "query_pins": {case: canonical_digest(bind_source_a(case)[0]) for case in SOURCE_CASES},
        "classes": {
            name: {
                "values": {k: classes[name][k] for k in ("t1", "t2", "cost", "lower", "upper")},
                "C": {"decision": "pending", "rationale": classes[name]["rationale"]},
                "P": {"decision": "pending", "rationale": classes[name]["rationale"]},
            }
            for name in INITIAL_CLASSES
        },
        "impact": {
            "decision": "pending",
            "rating": "High",
            "rationale": "Exact Source A typed administrative control of the pinned DC; "
            "does not certify a usable-identity/session/material goal.",
        },
        "limitations": [
            "AI-assisted expert scenario estimates, not empirical calibration.",
            "Equal endpoints across exact full histories require explicit invariance adoption.",
            "No natural-password recovery adoption; no global default or new raw edge.",
            "Query pins include initial capability, facts, policy, history inventory and caps.",
            "References and reviewer declarations are not cryptographic identity authentication.",
        ],
    }


def validate_release(release, query):
    """Fail closed on pending authority, changed questions or undocumented decisions."""
    if release.get("version") in (
        "final-cpi-delegated-release/4.0.0",
        "final-cpi-delegated-release/5.0.0",
    ):
        from scripts.research.final_cpi_delegated_release import validate

        return validate(release, query)
    expected = _expected_release(release)
    if (
        release.get("version") != expected["version"]
        or release.get("release_id") != expected["release_id"]
    ):
        raise ValueError("Unsupported numeric release identity")
    pins = ["input_pins", "history_model", "query_pins"]
    if release["version"] == WAVE2_VERSION:
        pins += ["context_domains", "numeric_decision_reference"]
    for name in pins:
        if release.get(name) != expected[name]:
            raise ValueError("Numeric release input/history/query pin mismatch: " + name)
    if release.get("status") != "adopted":
        raise ValueError("Numeric release remains pending B numeric/context/history adoption")
    review = release.get("review", {})
    if review.get("purpose") != "numeric_context_history_adoption":
        raise ValueError("Implementation approval is not numeric adoption")
    for field in ("reviewer", "reviewed_at", "reference", "confirmation"):
        if not isinstance(review.get(field), str) or not review[field].strip():
            raise ValueError("Missing actual numeric adoption review: " + field)
    timestamp = datetime.fromisoformat(review["reviewed_at"].replace("Z", "+00:00"))
    if timestamp.tzinfo is None:
        raise ValueError("Numeric review timestamp requires timezone")
    review_identity = _review_identity(review["reference"])
    if (
        review["reference"].rstrip("/")
        in {
            "https://github.com/nairyuuu/ad-weighted-graph/pull/271",
            "https://github.com/nairyuuu/ad-weighted-graph/pull/266",
        }
        or "/pull/271#pullrequestreview-" in review["reference"]
        or "/pull/266#pullrequestreview-" in review["reference"]
        or (
            review_identity[:2]
            in {
                ("github.com", "/nairyuuu/ad-weighted-graph/pull/271"),
                ("github.com", "/nairyuuu/ad-weighted-graph/pull/266"),
            }
            and (not review_identity[2] or review_identity[2].startswith("pullrequestreview-"))
        )
    ):
        raise ValueError("Implementation PR approval cannot authorize numeric adoption")
    case = query["rating_resolution"]["scope"]["query_id"]
    if canonical_digest(query) != release["query_pins"].get(case):
        raise ValueError("Numeric release exact query/context mismatch")
    if release["version"] == WAVE2_VERSION:
        contexts = release.get("contexts", {})
        if contexts.keys() != expected["contexts"].keys():
            raise ValueError("Wave 2 context adoption domain mismatch")
        for context in contexts.values():
            if context.get("decision") not in ("adopt", "reject", "needs_evidence"):
                raise ValueError("Missing explicit Wave 2 context disposition")
            if not isinstance(context.get("rationale"), str) or not context["rationale"].strip():
                raise ValueError("Missing Wave 2 context rationale")
        if contexts[case]["decision"] != "adopt":
            raise ValueError("Wave 2 exact context remains unadopted")
        history = release.get("history_decision", {})
        if (
            history.get("decision") not in ("adopt", "reject", "needs_evidence")
            or not isinstance(history.get("rationale"), str)
            or not history["rationale"].strip()
        ):
            raise ValueError("Missing explicit full-history adoption decision")
        forbidden_references = {
            WAVE2_NUMERIC_REFERENCE,
            read(PACKAGE.parent / "final-cpi-release-v1/decisions.adopted.json")["review"][
                "reference"
            ],
        }
        if review["reference"] in forbidden_references or review_identity in {
            _review_identity(reference) for reference in forbidden_references
        }:
            raise ValueError(
                "Prior numeric or Wave 1 review cannot authorize Wave 2 context/history"
            )
        if (
            any(
                c.get("P", {}).get("decision") == "adopt"
                for c in release.get("classes", {}).values()
            )
            and history["decision"] != "adopt"
        ):
            raise ValueError("Conditional P requires explicit full-history adoption")
    if release.get("classes", {}).keys() != expected["classes"].keys():
        raise ValueError("Unreviewed class expansion requires a new release")
    for name, entry in release["classes"].items():
        if entry.get("values") != expected["classes"][name]["values"]:
            raise ValueError("Changed numeric values require a revised proposal and release")
        for dimension in ("C", "P"):
            decision = entry.get(dimension, {})
            if decision.get("decision") not in ("adopt", "reject", "needs_evidence"):
                raise ValueError("Missing explicit class/dimension disposition")
            if not isinstance(decision.get("rationale"), str) or not decision["rationale"].strip():
                raise ValueError("Missing class/dimension rationale")
            if (
                dimension == "P"
                and entry["values"]["lower"] is None
                and decision["decision"] == "adopt"
            ):
                raise ValueError("Unrated recovery has no numeric P basis to adopt")
    impacts = (
        release.get("impacts", {})
        if release["version"] == WAVE2_VERSION
        else {case: release.get("impact", {})}
    )
    expected_impacts = (
        expected["impacts"] if release["version"] == WAVE2_VERSION else {case: expected["impact"]}
    )
    if impacts.keys() != expected_impacts.keys():
        raise ValueError("Typed impact context expansion")
    for name, impact in impacts.items():
        if impact.get("rating") != expected_impacts[name]["rating"] or impact.get(
            "decision"
        ) not in ("adopt", "reject", "needs_evidence"):
            raise ValueError("Missing or unsupported typed impact decision")
        if not isinstance(impact.get("rationale"), str) or not impact["rationale"].strip():
            raise ValueError("Missing typed impact rationale")


def apply_release(query, release):
    """Overlay accepted dimensions onto already compiled exact native registries."""
    if release.get("version") in (
        "final-cpi-delegated-release/4.0.0",
        "final-cpi-delegated-release/5.0.0",
    ):
        from scripts.research.final_cpi_delegated_release import apply

        return apply(query, release)
    if release.get("version") in (
        "final-cpi-effort-release/1.0.0",
        "final-cpi-effort-release/1.1.0",
    ):
        from scripts.research.final_cpi_effort_release import apply_effort_release

        return apply_effort_release(query, release)
    validate_release(release, query)
    result = copy.deepcopy(query)
    config = result["rating_resolution"]
    if config["policy"] != "production":
        raise ValueError("Numeric release requires production provider policy")
    registries = config["registries"]
    taxonomy = {
        r["technique_id"]: r["canonical_class"] for r in read(PACKAGE / "taxonomy.json")["actions"]
    }
    digest = canonical_digest(release)
    for role, dimension in (("effort", "C"), ("likelihood", "P")):
        records = registries[role]["data"]
        for record in records:
            cls = record["name"] if dimension == "C" else taxonomy[record["outcome_technique"]]
            decision = release["classes"].get(cls, {}).get(dimension, {})
            if decision.get("decision") != "adopt":
                continue
            record.update(
                review_status="accepted",
                disposition="rated",
                basis_category="scenario_assumption",
                numeric_basis_class="estimated_expert_scenario",
                review_reference=release["review"]["reference"],
                provenance_digest=canonical_digest(
                    {"release": digest, "record": record, "decision": decision}
                ),
            )
            if dimension == "P":
                record["rationale"] = (
                    decision["rationale"]
                    + " Full-history invariance adopted in "
                    + release["release_id"]
                )
    impact = _impact(release, query["rating_resolution"]["scope"]["query_id"])
    if impact["decision"] == "adopt":
        source = registries["impact_source"]["data"]
        asset = query["target"]
        source_record = source["target_impact_assessments"][asset]
        source_record.update(
            rating_status="rated",
            numeric_basis_class="estimated_expert_scenario",
            reviewed_disposition={
                "review_status": "accepted",
                "review_reference": release["review"]["reference"],
            },
        )
        for mapping in registries["impact"]["data"]["mappings"]:
            mapping.update(
                status="reviewed",
                evidence_class="scenario_assumption",
                numeric_basis_class="estimated_expert_scenario",
                review_reference=release["review"]["reference"],
                source_release_canonical_digest=canonical_digest(source),
            )
    for role, packet in list(registries.items()):
        registries[role] = envelope(packet["data"])
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--template", action="store_true")
    parser.add_argument("--wave2", action="store_true")
    parser.add_argument("--raw-dir", type=Path)
    parser.add_argument("--release", type=Path)
    parser.add_argument("--query", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Output already exists; choose a new versioned artifact")
    if args.template:
        if args.release or args.query:
            parser.error("--template excludes --release/--query")
        if args.wave2:
            if not args.raw_dir:
                parser.error("Wave 2 template requires manifest-verified --raw-dir")
            from scripts.research.issue250_public_probe import frozen_inputs

            graph, _, _ = frozen_inputs(
                args.raw_dir, read(PACKAGE / "cohort.json")["baseline_revision"]
            )
            result = template_wave2(graph, args.raw_dir)
        else:
            result = template()
    else:
        if args.wave2 or args.raw_dir:
            parser.error("--wave2/--raw-dir require --template")
        if not args.release or not args.query:
            parser.error("--release and --query are required")
        if args.output.resolve() in {args.release.resolve(), args.query.resolve()}:
            parser.error("Output must not overwrite release or query")
        result = apply_release(read(args.query), read(args.release))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
