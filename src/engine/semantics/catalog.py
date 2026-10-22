"""Strict catalog loading with a bounded executable vocabulary."""

import functools
from dataclasses import fields
from pathlib import Path

import yaml

from .models import (
    Effect,
    ExpectedTelemetry,
    SemanticEvidenceRef,
    SemanticEvidenceType,
    Technique,
)
from .rbcd import RECIPES as RBCD_RECIPES
from .rbcd import RELATIONSHIPS as RBCD_RELATIONSHIPS

ROOT = Path(__file__).resolve().parents[3]
PRINCIPALS = {"User", "Group", "Computer"}
KINDS = PRINCIPALS | {"Domain", "OU", "GPO"}
RELATIONSHIPS = {
    "MemberOf",
    "AdminTo",
    "GenericAll",
    "WriteDacl",
    "ForceChangePassword",
    "CanRDP",
    "CanPSRemote",
    "HasSession",
}
CAPABILITY_RELATIONSHIPS = {
    "AuthenticationControl",
    "DeclaredHostAdmin",
    "ASRepTarget",
    "ASRepMaterial",
    "RoastTarget",
    "TicketMaterial",
    "RecoveredSecret",
}
CAPABILITY_RELATIONSHIPS |= RBCD_RELATIONSHIPS
PREDICATES = {
    "asrep_request_capability",
    "dontreqpreauth",
    "asrep_request_accepted",
    "asrep_material",
    "known_identity",
    "has_spn",
    "service_principal_names",
    "kerberos_actor_authenticated",
    "kerberos_authentication_usable",
    "service_ticket_request_accepted",
    "ticket_material",
    "recovery_scope",
    "recovery_success",
    "recovered_password",
    "secret_valid",
    "reset_password_control",
    "authentication_context_matches",
    "actor_authenticated",
    "network_kdc_reachable",
    "network_rpc_reachable",
    "network_winrm_reachable",
    "service_winrm_running",
    "host_admin_mapping",
    "winrm_authentication_accepted",
    "endpoint_authorized",
    "admin_execution_context",
    "actor_controlled",
    "source_authorized",
    "actor_enabled",
    "target_enabled",
    "security_group",
    "membership_usable",
    "admin_channel",
    "authentication_accepted",
    "rdp_available",
    "winrm_available",
    "session_fresh",
    "session_present",
    "credential_accessible",
    "session_identity_usable",
    "source_admin_control",
    "password_policy_accepts",
    "directory_write_allowed",
    "membership_change_allowed",
}
PREDICATES |= {p for _, _, gates in RBCD_RECIPES.values() for p in gates}
CLASSES = {
    "entitlement",
    "host_admin",
    "object_control",
    "graph_mutation",
    "authentication_control",
    "remote_interactive",
    "remote_command",
    "credential_opportunity",
}
CATALOG_VERSION = "0.6"
EVIDENCE_FIELDS = {"type", "source", "locator", "claim", "rationale", "confidence"}
EVIDENCE_TYPES = {item.value for item in SemanticEvidenceType}
# Effect compatibility is deliberately bounded; adding an operation needs implementation/review.
EFFECT_TARGETS = {
    Effect.EFFECTIVE_MEMBER: ("MemberOf", {"Group"}),
    Effect.ADMIN_CONTROL: ("AdminTo", {"Computer"}),
    Effect.INTERACTIVE_SESSION: ("CanRDP", {"Computer"}),
    Effect.REMOTE_COMMAND_EXECUTION: ("CanPSRemote", {"Computer"}),
    Effect.CREDENTIAL_MATERIAL: ("HasSession", {"User"}),
    Effect.GRANT_GENERIC_ALL: ("WriteDacl", KINDS),
    Effect.GRANT_WRITE_DACL: ("GenericAll", KINDS),
    Effect.ADD_MEMBERSHIP: ("GenericAll", {"Group"}),
    Effect.AUTHENTICATION_CONTROL: (None, {"User"}),
    Effect.RESET_PASSWORD_CONTROL: (None, {"User"}),
    Effect.USABLE_IDENTITY: ("AuthenticationControl", {"Computer"}),
    Effect.ASREP_MATERIAL: ("ASRepTarget", {"User"}),
    Effect.SERVICE_TICKET_MATERIAL: ("RoastTarget", {"User"}),
    Effect.RECOVERED_SECRET: ("TicketMaterial", {"User"}),
}
EFFECT_GUARDS = {
    Effect.ASREP_MATERIAL: {
        "known_identity",
        "asrep_request_capability",
        "target_enabled",
        "dontreqpreauth",
        "network_kdc_reachable",
        "asrep_request_accepted",
    },
    Effect.SERVICE_TICKET_MATERIAL: {
        "known_identity",
        "has_spn",
        "service_principal_names",
        "kerberos_actor_authenticated",
        "kerberos_authentication_usable",
        "network_kdc_reachable",
        "service_ticket_request_accepted",
    },
    Effect.RECOVERED_SECRET: {"ticket_material", "recovery_scope", "recovery_success"},
    Effect.RESET_PASSWORD_CONTROL: {
        "target_enabled",
        "password_policy_accepts",
        "directory_write_allowed",
    },
    Effect.USABLE_IDENTITY: {
        "reset_password_control",
        "authentication_context_matches",
        "actor_enabled",
        "network_kdc_reachable",
        "authentication_accepted",
    },
    Effect.EFFECTIVE_MEMBER: {"security_group", "membership_usable"},
    Effect.ADMIN_CONTROL: {"admin_channel", "authentication_accepted"},
    Effect.INTERACTIVE_SESSION: {"rdp_available", "authentication_accepted"},
    Effect.REMOTE_COMMAND_EXECUTION: {"winrm_available", "authentication_accepted"},
    Effect.CREDENTIAL_MATERIAL: {
        "source_admin_control",
        "session_fresh",
        "session_present",
        "credential_accessible",
    },
    Effect.AUTHENTICATION_CONTROL: {
        "target_enabled",
        "password_policy_accepts",
        "directory_write_allowed",
    },
    Effect.GRANT_GENERIC_ALL: {"directory_write_allowed"},
    Effect.GRANT_WRITE_DACL: {"directory_write_allowed"},
    Effect.ADD_MEMBERSHIP: {
        "security_group",
        "membership_change_allowed",
        "directory_write_allowed",
    },
}


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _strings(value: object, name: str, *, empty: bool = False) -> tuple[str, ...]:
    _require(isinstance(value, list), f"{name}: expected list")
    _require(all(isinstance(v, str) and v.strip() for v in value), f"{name}: invalid string")
    _require(empty or bool(value), f"{name}: cannot be empty")
    _require(len(set(value)) == len(value), f"{name}: duplicate values")
    return tuple(value)


def validate_catalog(data: object) -> tuple[Technique, ...]:
    _require(
        isinstance(data, dict) and set(data) == {"version", "evidence_registry", "techniques"},
        "catalog fields",
    )
    _require(data["version"] == CATALOG_VERSION, "unsupported catalog version; migrate to 0.5")
    registry = data["evidence_registry"]
    _require(isinstance(registry, dict) and bool(registry), "evidence_registry must be non-empty")
    evidence = {}
    for evidence_id, entry in registry.items():
        _require(
            isinstance(evidence_id, str) and evidence_id.strip(),
            "evidence registry IDs must be non-empty strings",
        )
        _require(isinstance(entry, dict) and set(entry) == EVIDENCE_FIELDS, "evidence fields")
        _require(entry["type"] in EVIDENCE_TYPES, "invalid evidence type")
        _require(entry["confidence"] in {"low", "medium", "high"}, "invalid evidence confidence")
        string_fields = EVIDENCE_FIELDS - {"type", "confidence"}
        _require(
            all(isinstance(entry[field], str) and entry[field].strip() for field in string_fields),
            "evidence fields must be non-empty strings",
        )
        evidence[evidence_id] = SemanticEvidenceRef(
            id=evidence_id,
            type=SemanticEvidenceType(entry["type"]),
            source=entry["source"],
            locator=entry["locator"],
            claim=entry["claim"],
            rationale=entry["rationale"],
            confidence=entry["confidence"],
        )
    _require(isinstance(data["techniques"], list), "techniques must be a list")
    result = []
    for entry in data["techniques"]:
        _require(
            isinstance(entry, dict) and set(entry) == {f.name for f in fields(Technique)},
            "technique fields must match schema exactly",
        )
        values = dict(entry)
        for name in ("id", "relationship", "semantic_class", "confidence"):
            _require(
                isinstance(values[name], str) and bool(values[name].strip()), f"invalid {name}"
            )
        _require(
            values["relationship"] in RELATIONSHIPS | CAPABILITY_RELATIONSHIPS,
            "unknown relationship",
        )
        _require(values["semantic_class"] in CLASSES, "unknown semantic_class")
        _require(values["confidence"] in {"low", "medium", "high"}, "invalid confidence")
        _require(type(values["action_required"]) is bool, "action_required must be boolean")
        for name in (
            "source_kinds",
            "target_kinds",
            "prerequisites",
            "effects",
            "failure_conditions",
            "attack_refs",
            "cost_factors",
            "remediation",
        ):
            values[name] = _strings(values[name], name, empty=name == "attack_refs")
        sources = {"Computer"} if values["relationship"] == "HasSession" else PRINCIPALS
        _require(set(values["source_kinds"]) <= sources, "invalid source_kinds")
        _require(set(values["target_kinds"]) <= KINDS, "invalid target_kinds")
        _require(set(values["prerequisites"]) <= PREDICATES, "unknown prerequisite")
        values["effects"] = tuple(Effect(effect) for effect in values["effects"])
        is_rbcd = values["relationship"] in RBCD_RELATIONSHIPS
        if is_rbcd:
            recipe = RBCD_RECIPES.get(values["id"])
            _require(recipe is not None, "unsupported RBCD owner")
            rel, effect, gates = recipe
            _require(
                values["relationship"] == rel
                and values["effects"] == (Effect(effect),)
                and set(values["prerequisites"]) == set(gates)
                and set(values["source_kinds"]) == {"User"}
                and set(values["target_kinds"])
                == ({"User"} if rel in {"RBCDReset", "RBCDPrepare"} else {"Computer"}),
                "RBCD owner vocabulary must match executable semantics exactly",
            )
        for effect in () if is_rbcd else values["effects"]:
            relationship, targets = EFFECT_TARGETS[effect]
            allowed = {relationship} if relationship else {"GenericAll", "ForceChangePassword"}
            if effect is Effect.RECOVERED_SECRET:
                allowed.add("ASRepMaterial")
            if effect is Effect.USABLE_IDENTITY:
                allowed.add("RecoveredSecret")
                if values["id"] == "use_session_identity":
                    allowed.add("HasSession")
                    targets = {"User"}
            if effect is Effect.ADMIN_CONTROL:
                allowed.add("DeclaredHostAdmin")
            _require(values["relationship"] in allowed, "incompatible effect relationship")
            _require(set(values["target_kinds"]) <= targets, "incompatible effect target")
            guards = EFFECT_GUARDS[effect]
            if values["relationship"] == "ASRepMaterial":
                guards = {"asrep_material", "recovery_scope", "recovery_success"}
            if values["relationship"] == "RecoveredSecret":
                guards = {
                    "recovered_password",
                    "authentication_context_matches",
                    "actor_enabled",
                    "secret_valid",
                    "network_kdc_reachable",
                    "authentication_accepted",
                }
            if values["id"] == "use_session_identity":
                guards = {
                    "source_admin_control",
                    "session_fresh",
                    "session_present",
                    "credential_accessible",
                    "session_identity_usable",
                    "target_enabled",
                    "network_kdc_reachable",
                    "authentication_accepted",
                }
            if values["relationship"] == "DeclaredHostAdmin":
                guards = {
                    "actor_authenticated",
                    "host_admin_mapping",
                    "network_winrm_reachable",
                    "service_winrm_running",
                    "winrm_authentication_accepted",
                    "endpoint_authorized",
                    "admin_execution_context",
                    "target_enabled",
                }
            _require(guards <= set(values["prerequisites"]), "missing effect guards")
        required = {"actor_controlled", "source_authorized", "actor_enabled"}
        if values["relationship"] in {
            "RoastTarget",
            "TicketMaterial",
            "RecoveredSecret",
            "ASRepTarget",
            "ASRepMaterial",
        }:
            required = set().union(*(EFFECT_GUARDS[e] for e in values["effects"]))
            if values["relationship"] == "ASRepMaterial":
                required = {"asrep_material", "recovery_scope", "recovery_success"}
            if values["relationship"] == "RecoveredSecret":
                required = {
                    "recovered_password",
                    "authentication_context_matches",
                    "actor_enabled",
                    "secret_valid",
                    "network_kdc_reachable",
                    "authentication_accepted",
                }
        if values["relationship"] == "AuthenticationControl":
            required = EFFECT_GUARDS[Effect.USABLE_IDENTITY]
            _require(set(values["source_kinds"]) == {"User"}, "authentication source must be User")
        if values["relationship"] == "DeclaredHostAdmin":
            _require(set(values["source_kinds"]) == {"Group"}, "host mapping source must be Group")
        if values["relationship"] == "HasSession":
            required = {
                "source_admin_control",
                "session_fresh",
                "session_present",
                "credential_accessible",
            }
        if values["id"] == "use_session_identity":
            required = {
                "source_admin_control",
                "session_fresh",
                "session_present",
                "credential_accessible",
                "session_identity_usable",
                "target_enabled",
                "network_kdc_reachable",
                "authentication_accepted",
            }
            _require(
                values["relationship"] == "HasSession"
                and values["effects"] == (Effect.USABLE_IDENTITY,)
                and set(values["source_kinds"]) == {"Computer"}
                and set(values["target_kinds"]) == {"User"}
                and set(values["prerequisites"]) == required,
                "session identity recipe must preserve host and reusable-identity gates",
            )
        _require(is_rbcd or required <= set(values["prerequisites"]), "missing required guards")
        artifact_definitions = {
            "ASRepTarget": ("asrep_request", Effect.ASREP_MATERIAL, {"User", "Computer"}, {"User"}),
            "ASRepMaterial": (
                "recover_asrep_secret",
                Effect.RECOVERED_SECRET,
                {"User", "Computer"},
                {"User"},
            ),
            "RoastTarget": (
                "kerberoast_request",
                Effect.SERVICE_TICKET_MATERIAL,
                {"User", "Computer"},
                {"User"},
            ),
            "TicketMaterial": (
                "recover_ticket_secret",
                Effect.RECOVERED_SECRET,
                {"User", "Computer"},
                {"User"},
            ),
            "RecoveredSecret": (
                "activate_recovered_identity",
                Effect.USABLE_IDENTITY,
                {"User"},
                {"Computer"},
            ),
        }
        if values["relationship"] in artifact_definitions:
            owner, effect, source_kinds, target_kinds = artifact_definitions[values["relationship"]]
            _require(
                values["id"] == owner
                and values["effects"] == (effect,)
                and set(values["source_kinds"]) == source_kinds
                and set(values["target_kinds"]) == target_kinds
                and set(values["prerequisites"]) == required,
                "artifact owner vocabulary must match executable semantics exactly",
            )
        telemetry = values["expected_telemetry"]
        _require(isinstance(telemetry, list), "expected_telemetry must be a list")
        parsed = []
        for item in telemetry:
            _require(
                isinstance(item, dict)
                and set(item) == {"provider", "event_id", "requirement", "evidence_refs"},
                "telemetry fields",
            )
            _require(
                all(
                    isinstance(item[k], str) and item[k].strip()
                    for k in ("provider", "requirement")
                ),
                "telemetry strings",
            )
            _require(
                item["event_id"] is None
                or (type(item["event_id"]) is int and item["event_id"] > 0),
                "invalid event_id",
            )
            refs = _strings(item["evidence_refs"], "evidence_refs")
            _require(set(refs) <= set(evidence), "expected telemetry references missing evidence")
            parsed.append(ExpectedTelemetry(**{**item, "evidence_refs": refs}))
        values["expected_telemetry"] = tuple(parsed)
        passive = values["relationship"] == "MemberOf"
        _require(
            values["action_required"] is not passive, "invalid action_required for relationship"
        )
        _require(
            not passive or not parsed and not values["attack_refs"],
            "membership traversal has no telemetry or ATT&CK action",
        )
        result.append(Technique(**values))
    _require(len({t.id for t in result}) == len(result), "duplicate technique id")
    _require(
        {t.relationship for t in result} == RELATIONSHIPS | CAPABILITY_RELATIONSHIPS,
        "catalog must cover all structural and capability relationships",
    )
    return tuple(sorted(result, key=lambda technique: technique.id))


@functools.lru_cache(maxsize=32)
def _parse_and_validate_catalog_bytes(raw_bytes: bytes) -> tuple[Technique, ...]:
    data = yaml.safe_load(raw_bytes.decode("utf-8"))
    return validate_catalog(data)


def load_catalog(path: Path | str | None = None) -> tuple[Technique, ...]:
    target_path = Path(path or ROOT / "configs/attack_semantics.yml")
    return _parse_and_validate_catalog_bytes(target_path.read_bytes())


def _authoritative_technique(technique_id: str) -> Technique | None:
    """Retrieve an authoritative default executable technique definition by ID."""
    return next((t for t in load_catalog() if t.id == technique_id), None)
