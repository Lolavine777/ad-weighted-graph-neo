"""Versioned user-delegated adoption of existing finite CPI scenario proposals."""

from __future__ import annotations

import copy
import hashlib
from functools import lru_cache

from scripts.research.final_cpi_profiles import PACKAGE, ROOT, read
from scripts.research.issue250_public_probe import envelope, save
from scripts.research.offline_recovery_scenarios import PACKAGE as RECOVERY
from scripts.research.offline_recovery_scenarios import propose
from src.engine.ranking.resolution_service import canonical_digest

VERSION = "final-cpi-delegated-release/5.0.0"
POLICY = "final-cpi-declared-recovery-24h-v1"
DESTINATION = PACKAGE.parent / "final-cpi-release-v5"
RELEASE = DESTINATION / "decisions.adopted.json"
COHORT = DESTINATION / "declared-recovery-cohort.json"
MODELS = (
    "asrep_password_recovery-widecap2p36-reference-v1",
    "kerberoast_password_recovery-widecap2p36-reference-v1",
)
REFERENCE = "https://github.com/nairyuuu/ad-weighted-graph/issues/267#issuecomment-6166280449"
MODEL_INPUTS = {
    "docs/research/ratings/offline-recovery-v1/scenarios.proposed.json": (
        "a142863a268ac18ea72bd80ba1fe74218d9f62596136252f2ae8b615776a7cb3"
    ),
    "docs/research/ratings/offline-recovery-v1/sources.json": (
        "3837fade855c6b972634b15ab35906b56f61af75df1540197f120fdcbc0ef624"
    ),
    "scripts/research/offline_recovery_scenarios.py": (
        "e9b9cecaa9726ac5ab45b2cfc7c1cc51614fdbe71fd621a5059527f531cfb78f"
    ),
}
REVIEW = {
    "purpose": "numeric_context_history_adoption",
    "reviewer": "Lolavine777",
    "delegated_for": "nairyuuu",
    "reviewed_at": "2026-10-14T10:28:15Z",
    "reference": REFERENCE,
    "authority": "explicit human-user instruction, recorded by A; not a posted B review",
    "confirmation": (
        "Use the existing #281 declared scenario models; approve all existing supported "
        "proposals and exact contexts/histories in B's absence. Preserve frozen controls, "
        "no invented probabilities, measured resource claims or weakened semantic gates."
    ),
}


def model(profile_id):
    if profile_id not in MODELS:
        raise ValueError("Recovery profile is outside the actual delegated decision")
    for path, expected in MODEL_INPUTS.items():
        if hashlib.sha256((ROOT / path).read_bytes()).hexdigest() != expected:
            raise ValueError("Changed #281 model/source requires a new decision")
    profile = next(
        p
        for p in read(RECOVERY / "scenarios.proposed.json")["profiles"]
        if p["profile_id"] == profile_id
    )
    source = read(RECOVERY / "sources.json")["guessing_reference"]
    prediction = propose(profile, source)
    if prediction["proposed_interval"] is None:
        raise ValueError("Selected recovery scenario has no numeric basis")
    return profile, prediction


def recovery_context(profile_id):
    profile, _ = model(profile_id)
    return {
        "method": "offline-" + profile["class_id"] + "-declared-widecap-v1",
        "budget": (
            "one-worker;20h;floor-1000000000;cap-68719476736-distinct-verifications;no-restart"
        ),
        "horizon": "24h",
        "recovery_model_digest": canonical_digest(declaration(profile_id)),
    }


def declaration(profile_id):
    profile, prediction = model(profile_id)
    return {
        "profile_id": profile_id,
        "profile": profile,
        "population": profile["population"],
        "floor": profile["budget"]["min_complete_distinct_verifications_on_no_hit"],
        "model_inputs": MODEL_INPUTS,
        "source_revision": "ccd15fa1678540900491fc55e056af34b8ac1d8c",
        "resource_scope": prediction["resource_scope"],
        "authority": REFERENCE,
        "deployment_role": "explicit_declared_scenario_not_snapshot_baseline",
        "population_observed": False,
        "resource_attainment_observed": False,
        "compatible_material_or_declared_etype": profile["verifier"],
        "reserved_generation_and_verification_work_floor": 1000000000,
        "event_budget_remaining_seconds": 72000,
        "conditioning_binding": "exact native P inventory; acquisition and outcome work identities",
    }


def pending_model(query):
    scope = query["rating_resolution"]["scope"]
    profile_id = scope["query_id"]
    profile, prediction = model(profile_id)
    facts = [
        f
        for f in query.get("runtime_facts", []) + query.get("assumptions", [])
        if f["predicate"] == "recovery_success"
    ]
    if len(facts) != 1 or scope["policy_id"] != POLICY:
        raise ValueError("Declared recovery requires one exact material question")
    metadata = facts[0].get("assumption_metadata", {})
    if canonical_digest(metadata.get("recovery_model")) != canonical_digest(
        declaration(profile_id)
    ):
        raise ValueError("Missing or changed conditional recovery model")
    if {
        k: metadata.get(k) for k in ("method", "budget", "horizon", "recovery_model_digest")
    } != recovery_context(profile_id):
        raise ValueError("Recovery material/resource/time question changed")
    return profile, prediction


def pending_policy(query):
    pending_model(query)
    base = read(PACKAGE / "applicability-v1.1.json")["policies"]["final-cpi-roasting-24h-v1"]
    return {
        **base,
        "recovery_contexts": [recovery_context(query["rating_resolution"]["scope"]["query_id"])],
    }


def model_cases():
    original = read(PACKAGE / "cohort.json")["queries"]
    return {
        "version": "final-cpi-declared-recovery-cohort/1.0.0",
        "authority": REFERENCE,
        "deployment_role": "explicit_declared_scenario_not_snapshot_baseline",
        "queries": [
            {
                "id": profile_id,
                "base_case_id": base,
                "supported": True,
                "budget": next(c["budget"] for c in original if c["id"] == base),
            }
            for profile_id, base in zip(
                MODELS, ("asrep-natural-password", "kerberoast-identity"), strict=True
            )
        ],
    }


def prepare_declared(case, graph, frozen):
    from scripts.research.final_cpi_coverage import prepare_roasting

    expected = next(c for c in model_cases()["queries"] if c["id"] == case["id"])
    if canonical_digest(case) != canonical_digest(expected):
        raise ValueError("Declared recovery selector/budget drift")
    base = next(
        c for c in read(PACKAGE / "cohort.json")["queries"] if c["id"] == case["base_case_id"]
    )
    return prepare_roasting(base, graph, frozen, recovery_profile_id=case["id"])


def queries(graph, frozen, raw_dir):
    from scripts.research.final_cpi_adoption_replay import RELEASE as WAVE1
    from scripts.research.final_cpi_adoption_replay import prepare_case

    result = {}
    for group, filename in (
        ("original", "cohort.json"),
        ("supplementary", "supplementary-cohort.json"),
    ):
        for case in read(PACKAGE / filename)["queries"]:
            result[case["id"]] = prepare_case(group, case, graph, frozen, raw_dir, read(WAVE1))[0]
    for case in model_cases()["queries"]:
        result[case["id"]] = prepare_declared(case, graph, frozen)
    return result


def case_graph(case_id, graph, query):
    from scripts.research.final_cpi_extension import extension_graph

    for case in read(PACKAGE / "supplementary-cohort.json")["queries"]:
        if case["id"] == case_id:
            return extension_graph(case, graph, query)
    return graph


def signature():
    raw = ROOT / "data/raw/SEAMLESS"
    if raw.is_symlink() or any(p.is_symlink() for p in raw.rglob("*.json")):
        raise ValueError("Manifest-backed recovery inputs must not use symlink aliases")
    # Numeric adoption pins its inputs/questions; replay evidence pins executable source.
    patterns = (
        "docs/research/ratings/final-cpi-v1/*.json",
        "docs/research/ratings/scenario-basis-v1/source-a-*.json",
        "docs/research/ratings/final-cpi-release-v1/*.json",
        "docs/research/scenarios/week4-seamless-v1.json",
        "configs/attack_semantics.yml",
        "data/samples/manifests/seamless-raw-v1.json",
        "tests/fixtures/ranking/seamless_time_policy.json",
    )
    paths = {p for pattern in patterns for p in ROOT.glob(pattern) if p.is_file()}
    paths.update(ROOT / name for name in MODEL_INPUTS)
    if COHORT.exists():
        paths.add(COHORT)
    paths.update(raw.rglob("*.json"))
    pins = {
        p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(paths)
        if p != RELEASE
    }
    catalog = "configs/attack_semantics.yml"
    if catalog in pins:
        from scripts.research.likelihood_catalog import published_catalog

        publication = read(ROOT / "docs/research/ratings/likelihood-v1/catalog.json")
        published_catalog(publication, ROOT)
        pins[catalog] = publication["source_pins"][catalog].removeprefix("sha256:")
    return canonical_digest(pins)


@lru_cache(maxsize=1)
def _definition(input_signature):
    from scripts.research.final_cpi_adoption_replay import graph_identity, load_inputs

    raw = ROOT / "data/raw/SEAMLESS"
    if COHORT.exists() and canonical_digest(read(COHORT)) != canonical_digest(model_cases()):
        raise ValueError("Declared recovery cohort differs from the approved selectors")
    graph, frozen = load_inputs(raw)
    prepared = queries(graph, frozen, raw)
    classes = {
        c["class_id"]: {k: c[k] for k in ("t1", "t2", "cost", "lower", "upper")}
        for c in read(PACKAGE / "profile.json")["classes"]
    }
    models = {
        name: {
            "profile_digest": canonical_digest(model(name)[0]),
            "P": model(name)[1]["proposed_interval"],
            "declaration": declaration(name),
        }
        for name in MODELS
    }
    result = {
        "version": VERSION,
        "release_id": "final-cpi-wave2-delegated-v5",
        "status": "adopted",
        "review": REVIEW,
        "input_signature": input_signature,
        "raw_identity": graph_identity(graph),
        "prior_B_context_decision": "https://github.com/nairyuuu/ad-weighted-graph/pull/271#issuecomment-6163909537",
        "classes": classes,
        "recovery_models": models,
        "query_pins": {name: canonical_digest(q) for name, q in prepared.items()},
        "context_domains": {
            name: {
                "scope_digest": canonical_digest(q["rating_resolution"]["scope"]),
                "C_inventory_digest": canonical_digest(
                    q["rating_resolution"]["registries"]["effort"]["data"]
                ),
                "P_prefix_inventory_digest": canonical_digest(
                    q["rating_resolution"]["registries"]["likelihood"]["data"]
                ),
                "typed_goal_digest": canonical_digest(q["target_goal"]),
            }
            for name, q in prepared.items()
        },
        "history_decision": {
            "decision": "adopt",
            "rationale": (
                "Only rederived exact finite ordered successful histories; stable no-depletion "
                "distinct-work model, no retries uplift, secret invalidation or unsupported "
                "lineage transfer."
            ),
        },
        "limitations": [
            "Frozen unknown-population/no-floor recovery controls have no P basis; "
            "approval cannot manufacture it.",
            "Selected recovery models are conditional planning scenarios, "
            "not measured population, verifier throughput or cap attainment.",
            "No new raw RDP/HasSession relationships, global search optimum "
            "or empirical probability calibration.",
            "Delegated human adoption is distinct from posted B code review, "
            "merge and issue closure.",
        ],
    }
    if signature() != input_signature:
        raise ValueError("Source/raw/model identity changed during release reconstruction")
    return result


def definition():
    return copy.deepcopy(_definition(signature()))


def validate(release, query):
    legacy = release.get("version") == "final-cpi-delegated-release/4.0.0"
    expected = (
        "sha256:f27b412cd72517c31599de7b3dfb2d276482753bb45226403c6226ad32deb46e"
        if legacy
        else canonical_digest(definition())
    )
    if canonical_digest(release) != expected:
        raise ValueError("Delegated receipt authority, values, inputs or histories changed")
    if legacy:
        for profile_id in MODELS:
            model(profile_id)
    case = query["rating_resolution"]["scope"]["query_id"]
    if query["rating_resolution"]["policy"] != "production" or canonical_digest(query) != release[
        "query_pins"
    ].get(case):
        raise ValueError("Delegated release requires its exact production query/model/history")


def apply(query, release):
    validate(release, query)
    case = query["rating_resolution"]["scope"]["query_id"]
    result = copy.deepcopy(query)
    registries = result["rating_resolution"]["registries"]
    taxonomy = {
        t["technique_id"]: t["canonical_class"] for t in read(PACKAGE / "taxonomy.json")["actions"]
    }
    for role in ("effort", "likelihood"):
        for record in registries[role]["data"]:
            name = record["name"] if role == "effort" else taxonomy[record["outcome_technique"]]
            expected = release["classes"][name]
            if role == "likelihood":
                bounds = (
                    release["recovery_models"][case]["P"]
                    if "password_recovery" in name and case in MODELS
                    else [expected["lower"], expected["upper"]]
                )
                if bounds[0] is None:
                    continue
                if [record["lower"], record["upper"]] != bounds:
                    raise ValueError("Compiled P differs from the approved conditional model")
            record.update(
                review_status="accepted",
                disposition="rated",
                basis_category="scenario_assumption",
                numeric_basis_class="estimated_expert_scenario",
                review_reference=REFERENCE,
                provenance_digest=canonical_digest(
                    {"release": canonical_digest(release), "record": record}
                ),
            )
    source = registries["impact_source"]["data"]
    source["target_impact_assessments"][query["target"]].update(
        rating_status="rated",
        numeric_basis_class="estimated_expert_scenario",
        reviewed_disposition={"review_status": "accepted", "review_reference": REFERENCE},
    )
    for mapping in registries["impact"]["data"]["mappings"]:
        mapping.update(
            status="reviewed",
            evidence_class="scenario_assumption",
            numeric_basis_class="estimated_expert_scenario",
            review_reference=REFERENCE,
            source_release_canonical_digest=canonical_digest(source),
        )
    for role, packet in list(registries.items()):
        registries[role] = envelope(packet["data"])
    return result


def main():
    if RELEASE.exists() or COHORT.exists():
        raise ValueError("Preserve existing release/cohort; select a new version")
    save(COHORT, model_cases())
    save(RELEASE, definition())


if __name__ == "__main__":
    main()
