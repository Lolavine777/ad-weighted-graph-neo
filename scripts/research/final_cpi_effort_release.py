"""Consume B's approved effort without granting conditional-history authority.

This partial production release changes only native effort records in the frozen
Wave 2 contexts. It cannot authorize P, I, recovered activation or another query.
"""

from __future__ import annotations

import copy

from scripts.research.final_cpi_profiles import PACKAGE, read
from scripts.research.final_cpi_release import WAVE2_NUMERIC_REFERENCE, WAVE2_PACKAGE, input_pins
from scripts.research.issue250_public_probe import envelope
from src.engine.ranking.resolution_service import canonical_digest

VERSION = "final-cpi-effort-release/1.1.0"
RELEASE = PACKAGE.parent / "final-cpi-release-v3/decisions.adopted-c-scoped.json"

# Transcribed directly from B's decision, independent of the proposed profile.
APPROVED = {
    "directory_password_reset": (1, "3/5", "19/20"),
    "reset_identity_activation": (0, "3/4", "49/50"),
    "winrm_admin_execution": (1, "1/2", "9/10"),
    "host_admin_execution": (1, "3/5", "19/20"),
    "asrep_material_request": (0, "9/10", "99/100"),
    "kerberoast_material_request": (1, "17/20", "49/50"),
    "group_membership_mutation": (1, "4/5", "49/50"),
    "grant_write_dacl": (1, "7/10", "49/50"),
    "grant_generic_all": (2, "7/10", "19/20"),
    "rdp_interactive_session": (1, "3/5", "19/20"),
    "winrm_command_session": (1, "7/10", "19/20"),
    "session_credential_material": (3, "1/4", "4/5"),
    "rbcd_secret_acquisition": (1, "7/10", "19/20"),
    "rbcd_service_preparation": (2, "4/5", "49/50"),
    "rbcd_descriptor_mutation": (2, "4/5", "99/100"),
    "rbcd_service_delegation": (2, "3/5", "9/10"),
    "rbcd_admin_execution": (2, "3/5", "19/20"),
}
C_ONLY = {"asrep_password_recovery": 2, "kerberoast_password_recovery": 3}


def release_definition():
    """Record existing C authority; no invented reviewer or history disposition."""
    candidate = read(WAVE2_PACKAGE / "decisions.pending.json")
    pins = {
        **input_pins(),
        "supplementary-cohort.json": canonical_digest(read(PACKAGE / "supplementary-cohort.json")),
    }
    if pins != candidate["input_pins"]:
        raise ValueError("Effort release input pin mismatch")
    profile = {c["class_id"]: c for c in read(PACKAGE / "profile.json")["classes"]}
    for name, (cost, lower, upper) in APPROVED.items():
        if (profile[name]["cost"], profile[name]["lower"], profile[name]["upper"]) != (
            cost,
            lower,
            upper,
        ):
            raise ValueError("B numeric decision/profile mismatch: " + name)
    for name, cost in C_ONLY.items():
        if profile[name]["cost"] != cost or profile[name]["lower"] is not None:
            raise ValueError("B C-only decision/profile mismatch: " + name)
    costs = {name: value[0] for name, value in APPROVED.items()} | C_ONLY
    context_release = read(WAVE2_PACKAGE / "decisions.adopted.json")
    allowed_contexts = sorted(
        name for name, entry in context_release["contexts"].items() if entry["decision"] == "adopt"
    )
    return {
        "version": VERSION,
        "release_id": "final-cpi-wave2-approved-effort-v3-scoped",
        "status": "adopted_c_only",
        "authority": {
            "dimension": "C",
            "reviewer": "nairyuuu",
            "reviewed_at": "2026-10-13T09:21:18Z",
            "reference": WAVE2_NUMERIC_REFERENCE,
            "disposition": "adopt",
            "numeric_basis_class": "estimated_expert_scenario",
        },
        "candidate_digest": canonical_digest(candidate),
        "binding_constraints": {
            "context_authority_reference": context_release["review"]["reference"],
            "context_authority_digest": canonical_digest(context_release),
            "adopted_contexts": allowed_contexts,
            "recovery_C_only_contexts": ["asrep-natural-password", "kerberoast-identity"],
            "recovery_C_only_classes": C_ONLY,
        },
        "input_pins": pins,
        "query_pins": candidate["query_pins"],
        "context_domains": candidate["context_domains"],
        "classes": {
            name: {
                "C": {"decision": "adopt", "cost": costs[name]},
                "P": {
                    "decision": "needs_evidence",
                    "reason": "no numeric basis"
                    if name in C_ONLY
                    else "exact context/history authority pending; numeric values already approved",
                },
            }
            for name in candidate["classes"]
        },
        "withheld": {
            "P": "No new conditional record is accepted by this release.",
            "I": "Existing typed consequence mappings remain unchanged.",
            "recovered_identity_activation": "Needs evidence; reset approval does not transfer.",
            "rdp_interactive_session": "Unsupported policy binding; no records emitted.",
            "session_credential_material": "Unsupported policy binding; no records emitted.",
            "history_equivalence": "No extension of stable-no-depletion-distinct-work-v1.",
        },
    }


def apply_effort_release(query, release):
    """Bind only reviewed canonical work at exact pre-search query pins."""
    if release != release_definition():
        raise ValueError("Effort release authority/domain mismatch")
    config = query["rating_resolution"]
    case = config["scope"]["query_id"]
    if config["policy"] != "production" or canonical_digest(query) != release["query_pins"].get(
        case
    ):
        raise ValueError("Effort release exact query/context mismatch")
    constraints = release["binding_constraints"]
    recovery_only = case in constraints["recovery_C_only_contexts"]
    if case not in constraints["adopted_contexts"] and not recovery_only:
        raise ValueError("Effort release exact context remains withheld")
    result = copy.deepcopy(query)
    registries = result["rating_resolution"]["registries"]
    records = registries["effort"]["data"]
    for record in records:
        decision = release["classes"].get(record["name"])
        if decision is None:
            continue
        if recovery_only and record["name"] not in constraints["recovery_C_only_classes"]:
            continue
        if record["t1"] + record["t2"] - 2 != decision["C"]["cost"]:
            raise ValueError("Effort record disagrees with B's decision")
        record.update(
            review_status="accepted",
            disposition="rated",
            basis_category="scenario_assumption",
            numeric_basis_class="estimated_expert_scenario",
            review_reference=release["authority"]["reference"],
            provenance_digest=canonical_digest({"release": release, "record": record}),
            notes=record["notes"] + " C adopted separately; no P/history authority conferred.",
        )
    registries["effort"] = envelope(records)
    return result
