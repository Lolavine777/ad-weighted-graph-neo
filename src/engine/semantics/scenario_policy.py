"""SEAMLESS-wide Scenario Assumption Policy Specification and Resolver.

Implements Issue #290: Reusable, versioned scenario policy replacing
per-query hand-crafted assumptions across diverse sources and goals.

Non-negotiable architectural invariants:
1. Never turn all Unknown facts into True blindly.
2. Never invent structural edges or permissions.
3. Never grant attacker capabilities (control, usable_identity, admin_control)
   without explicit foothold declarations or valid applicable action effects.
4. Authoritative False in snapshot facts or context always vetoes any assumption.
5. Successful assumptions never imply P=1 (likelihood remains governed by rating basis).
6. Neo may condition missing group type; authoritative non-security attributes still veto.
7. Credential/password recovery requires explicit opt-in and cannot default to True.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import OrderedDict
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from types import MappingProxyType
from typing import Any

from src.engine.semantics.models import FactOrigin, RuntimeFact
from src.engine.semantics.state import AttackState

POLICY_SPEC_VERSION = "scenario-policy/1.0.0"
SEAMLESS_SNAPSHOT_ID = "sha256:e0601d763eeea285d268ec9e468d321c50c9d7faba53c8e7442a2fcc4159c812"


class RuleTaxonomy(StrEnum):
    """Four-tier rule taxonomy defined in Issue #290 governance."""

    GLOBAL = "global"
    TYPED = "typed"
    SPECIFIC = "specific"
    FORBIDDEN_TO_DEFAULT = "forbidden_to_default"


class AuditClassification(StrEnum):
    """Audit classification for active technique runtime prerequisites."""

    OBSERVED = "observed"
    SAFELY_CONDITIONABLE = "safely_conditionable"
    NEEDS_SCOPED_OVERRIDE = "needs_scoped_override"
    CANNOT_DEFAULT = "cannot_default"


# Predicates that must NEVER default to True in standard scenario mode.
FORBIDDEN_PREDICATES: frozenset[str] = frozenset(
    {
        "recovery_success",
        "usable_identity",
        "admin_control",
        "control",
        "actor_controlled",
        "actor_authenticated",
        "source_authorized",
        "source_admin_control",
        "relationship_exists",
        "delegated_context",
        "controlled_service",
        "rbcd_descriptor",
        "rbcd_secret",
    }
)

# Well-known Universal / Built-in AD security group SIDs (MS-DTYP 2.4.2.4).
WELL_KNOWN_AD_SECURITY_SIDS: Mapping[str, str] = MappingProxyType(
    {
        "S-1-5-32-544": "Administrators (MS-DTYP 2.4.2.4 / MS-SAMR 2.2.1.1.5)",
        "S-1-5-32-545": "Users (MS-DTYP 2.4.2.4)",
        "S-1-5-32-546": "Guests (MS-DTYP 2.4.2.4)",
        "S-1-5-32-555": "Remote Desktop Users (MS-DTYP 2.4.2.4)",
        "S-1-5-11": "Authenticated Users (MS-DTYP 2.4.2.4)",
        "S-1-5-9": "Enterprise Domain Controllers (MS-DTYP 2.4.2.4)",
    }
)

# Well-known domain-relative group RIDs in Active Directory (MS-SAMR 2.2.1.1.5).
WELL_KNOWN_AD_DOMAIN_GROUP_RIDS: Mapping[int, str] = MappingProxyType(
    {
        512: "Domain Admins (MS-SAMR 2.2.1.1.5)",
        513: "Domain Users (MS-SAMR 2.2.1.1.5)",
        514: "Domain Guests (MS-SAMR 2.2.1.1.5)",
        515: "Domain Computers (MS-SAMR 2.2.1.1.5)",
        516: "Domain Controllers (MS-SAMR 2.2.1.1.5)",
        517: "Cert Publishers (MS-SAMR 2.2.1.1.5)",
        518: "Schema Admins (MS-SAMR 2.2.1.1.5)",
        519: "Enterprise Admins (MS-SAMR 2.2.1.1.5)",
        520: "Group Policy Creator Owners (MS-SAMR 2.2.1.1.5)",
        521: "Read-only Domain Controllers (MS-SAMR 2.2.1.1.5)",
        522: "Cloneable Domain Controllers (MS-SAMR 2.2.1.1.5)",
        525: "Protected Users (MS-SAMR 2.2.1.1.5)",
        526: "Key Admins (MS-SAMR 2.2.1.1.5)",
        527: "Enterprise Key Admins (MS-SAMR 2.2.1.1.5)",
        553: "RAS and IAS Servers (MS-SAMR 2.2.1.1.5)",
    }
)

# Diagnostic-only well-known group name patterns.
# Under Issue #290, naming heuristics MUST NOT independently authorize security_group=True.
WELL_KNOWN_SECURITY_GROUP_PATTERNS: tuple[re.Pattern, ...] = (
    re.compile(r"DOMAIN ADMINS", re.I),
    re.compile(r"ENTERPRISE ADMINS", re.I),
    re.compile(r"DOMAIN USERS", re.I),
    re.compile(r"AUTHENTICATED USERS", re.I),
    re.compile(r"ADMINISTRATORS", re.I),
    re.compile(r"PRE-WINDOWS 2000 COMPATIBLE ACCESS", re.I),
    re.compile(r"REMOTE DESKTOP USERS", re.I),
    re.compile(r"SCHEMA ADMINS", re.I),
    re.compile(r"GROUP POLICY CREATOR OWNERS", re.I),
)

# Distribution group patterns: these act as conservative negative hints.
DISTRIBUTION_GROUP_PATTERNS: tuple[re.Pattern, ...] = (
    re.compile(r".*DISTLIST.*", re.I),
    re.compile(r".*DISTRIBUTION.*", re.I),
    re.compile(r".*\bDL\b.*", re.I),
)

_SID_EXTRACT_RE = re.compile(r"S-1-(?:[0-9]+)(?:-[0-9]+)+", re.I)
_DOMAIN_SID_WITH_RID_RE = re.compile(r"(?:^|[^0-9])S-1-5-21-(?:[0-9]+-)*([0-9]+)(?:$|[^0-9])", re.I)


def lookup_well_known_security_group_identity(
    group_node: Mapping[str, Any] | None,
) -> str | None:
    """Return provenance string if group_node has a reviewed well-known AD security group identity.

    Inspects stable SID/RID fields (id, objectsid, sid, rid).
    Never performs regex pattern matching against arbitrary group names or labels.
    """
    if not isinstance(group_node, Mapping):
        return None

    props = (
        group_node.get("properties") if isinstance(group_node.get("properties"), Mapping) else {}
    )

    # 1. Check numeric RID attribute if present
    for rid_val in (group_node.get("rid"), props.get("rid")):
        if rid_val is not None and not isinstance(rid_val, bool):
            try:
                rid_int = int(rid_val)
                if rid_int in WELL_KNOWN_AD_DOMAIN_GROUP_RIDS:
                    return WELL_KNOWN_AD_DOMAIN_GROUP_RIDS[rid_int]
            except ValueError, TypeError:
                pass

    # 2. Check candidate identifier strings across node and props
    candidate_strs: list[str] = []
    for k in (
        "id",
        "objectsid",
        "objectSid",
        "sid",
        "objectidentifier",
        "objectid",
    ):
        for container in (group_node, props):
            val = container.get(k)
            if isinstance(val, str) and val.strip():
                candidate_strs.append(val.strip())

    for val in candidate_strs:
        # Check domain-relative SID with RID
        m_domain = _DOMAIN_SID_WITH_RID_RE.search(val)
        if m_domain:
            try:
                rid = int(m_domain.group(1))
                if rid in WELL_KNOWN_AD_DOMAIN_GROUP_RIDS:
                    return WELL_KNOWN_AD_DOMAIN_GROUP_RIDS[rid]
            except ValueError, TypeError:
                pass

        # Check universal/builtin well-known SID
        for match in _SID_EXTRACT_RE.finditer(val):
            canonical_sid = match.group(0).upper()
            if canonical_sid in WELL_KNOWN_AD_SECURITY_SIDS:
                return WELL_KNOWN_AD_SECURITY_SIDS[canonical_sid]

    return None


def is_distribution_group(label: str) -> bool:
    """Return True if the group label indicates a distribution list."""
    clean = label.strip().upper()
    return any(p.search(clean) for p in DISTRIBUTION_GROUP_PATTERNS)


def is_recognized_security_group(label: str) -> bool:
    """Diagnostic naming heuristic only.

    DO NOT USE to authorize security_group=True; Issue #290 strictly forbids
    authorizing security groups by name heuristic without authoritative attributes
    or stable SID/RID identity with reviewed provenance.
    """
    clean = label.strip().upper()
    if is_distribution_group(clean):
        return False
    return any(p.search(clean) for p in WELL_KNOWN_SECURITY_GROUP_PATTERNS)


# Active Directory groupType bit flag for security-enabled groups (MS-ADTS / ADS_GROUP_TYPE_ENUM)
ADS_GROUP_TYPE_SECURITY_ENABLED: int = 0x80000000


def decode_ad_group_type_security(group_type: Any) -> bool | None:
    """Decode Active Directory groupType bitmask for security-enabled status.

    Returns:
        True: if the GROUP_TYPE_SECURITY_ENABLED bit (0x80000000) is set.
        False: if groupType is numeric and the bit is not set (distribution group).
        None: if groupType is missing, boolean, or not a parseable integer.
    """
    if group_type is None or isinstance(group_type, bool):
        return None
    try:
        if isinstance(group_type, str):
            val = int(group_type, 0)
        elif isinstance(group_type, (int, float)):
            val = int(group_type)
        else:
            return None
    except ValueError, TypeError:
        return None
    return bool((val & 0xFFFFFFFF) & ADS_GROUP_TYPE_SECURITY_ENABLED)


def classify_ad_group_type_with_basis(
    group_node: Mapping[str, Any] | None,
    label: str | None = None,
) -> tuple[str, str, str]:
    """Classify an Active Directory group, returning (classification, basis, provenance_details).

    Returns:
        tuple[str, str, str]: (classification, classification_basis, identity_provenance)
        classification is 'security_group', 'distribution_group', or 'unrecognized'.

    Authoritative attributes (decoded groupType bitmask or security_enabled property)
    always outrank naming heuristics.
    A positive security_group classification requires one of:
    1. authoritative security_enabled=True;
    2. decoded groupType with the security-enabled bit;
    3. reviewed specific allowlist binding with provenance based on stable SID/RID identity.

    A name heuristic may act as a conservative negative hint (distribution_group),
    but CANNOT independently authorize security_group=True.
    """
    node = group_node if isinstance(group_node, Mapping) else {}
    props = node.get("properties") if isinstance(node.get("properties"), Mapping) else {}

    sec_auth = node.get("security_enabled")
    if sec_auth is None:
        sec_auth = props.get("security_enabled")
    if isinstance(sec_auth, str):
        if sec_auth.strip().lower() in ("true", "1", "yes"):
            sec_auth = True
        elif sec_auth.strip().lower() in ("false", "0", "no"):
            sec_auth = False
    elif isinstance(sec_auth, (int, float)) and not isinstance(sec_auth, bool):
        sec_auth = bool(sec_auth)

    raw_gt = (
        node.get("groupType")
        if node.get("groupType") is not None
        else node.get("grouptype", props.get("groupType", props.get("grouptype")))
    )
    sec_decoded = decode_ad_group_type_security(raw_gt)

    # Authoritative attributes take absolute precedence
    if sec_auth is False or sec_decoded is False:
        details = (
            f"groupType raw={raw_gt} (non-security bitmask)"
            if sec_decoded is False
            else "security_enabled=False"
        )
        return "distribution_group", "authoritative_distribution_attribute", details

    if sec_decoded is True:
        return (
            "security_group",
            "authoritative_grouptype_security_bit",
            f"groupType bitmask ({raw_gt}) with ADS_GROUP_TYPE_SECURITY_ENABLED (0x80000000)",
        )

    if sec_auth is True:
        return (
            "security_group",
            "authoritative_security_enabled_property",
            "authoritative node property security_enabled=True",
        )

    # Conservative negative hint: distribution list naming prevents security group treatment
    grp_label = (
        label
        if (label is not None and label != node.get("id"))
        else (
            node.get("label")
            or node.get("name")
            or (props.get("name") if isinstance(props, Mapping) else None)
            or (props.get("label") if isinstance(props, Mapping) else None)
            or label
            or node.get("id", "")
        )
    )
    if is_distribution_group(grp_label):
        return (
            "distribution_group",
            "distribution_naming_pattern",
            f"label {grp_label!r} matches conservative distribution naming pattern",
        )

    # Reviewed specific allowlist binding with provenance (stable SID/RID identity)
    well_known = lookup_well_known_security_group_identity(node)
    if well_known is not None:
        sid_hint = (
            node.get("objectsid")
            or (props.get("objectsid") if isinstance(props, Mapping) else None)
            or node.get("id", "")
        )
        return (
            "security_group",
            "well_known_identity_allowlist",
            f"reviewed well-known security identity ({sid_hint}): {well_known}",
        )

    # Issue #290: Missing or unverified groupType stays unresolved.
    # Name heuristics cannot independently authorize security_group=True.
    return (
        "unrecognized",
        "unrecognized_missing_group_type",
        (
            "group lacks authoritative groupType, security_enabled property, "
            "or reviewed well-known identity"
        ),
    )


def classify_ad_group_type(
    group_node: Mapping[str, Any] | None,
    label: str | None = None,
) -> str:
    """Classify an Active Directory group.

    Returns 'security_group', 'distribution_group', or 'unrecognized'.
    """
    return classify_ad_group_type_with_basis(group_node, label)[0]


TECHNIQUE_EDGE_KINDS: Mapping[str, str] = MappingProxyType(
    {
        "obtain_admin_execution_on_host": "AdminTo",
        "propagate_group_entitlement": "MemberOf",
        "genericall_add_member": "GenericAll",
        "genericall_reset_password": "GenericAll",
        "scenario_reset_password": "GenericAll",
        "genericall_grant_write_dacl": "GenericAll",
        "grant_new_object_right": "WriteDacl",
        "writedacl_add_member": "WriteDacl",
        "open_remote_interactive_session": "CanRDP",
        "open_winrm_remote_session": "CanPSRemote",
        "scenario_rdp_admin": "CanRDP",
        "scenario_winrm_admin": "CanPSRemote",
        "use_session_identity": "HasSession",
    }
)


@dataclass(frozen=True)
class PolicyOverride:
    """Explicit scoped user override for a prerequisite condition.

    Required for conditions classified as needs_scoped_override (e.g. offline
    password recovery for a specific account, or treating a distribution list
    as a mail-enabled security group).
    """

    predicate: str
    subject: str
    target: str
    value: bool = True
    override_type: str = "scoped_opt_in"
    rationale: str = "Explicit scoped scenario override"
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not (
            self.predicate.strip()
            and self.subject.strip()
            and self.target.strip()
            and self.rationale.strip()
        ):
            raise ValueError(
                "PolicyOverride requires non-empty predicate, subject, target, and rationale"
            )
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))

    def to_dict(self) -> dict[str, Any]:
        return {
            "predicate": self.predicate,
            "subject": self.subject,
            "target": self.target,
            "value": self.value,
            "override_type": self.override_type,
            "rationale": self.rationale,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class ApplicabilityRule:
    """A declared assumption policy rule within the taxonomy."""

    rule_id: str
    predicate: str
    taxonomy: RuleTaxonomy
    subject_kind: str | None = None
    target_kind: str | None = None
    default_value: bool = True
    provenance_reference: str = "policy://seamless/standard-v1"
    rationale: str = "Standard Active Directory environment condition"
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not (self.rule_id.strip() and self.predicate.strip()):
            raise ValueError("ApplicabilityRule requires non-empty rule_id and predicate")
        object.__setattr__(self, "taxonomy", RuleTaxonomy(self.taxonomy))
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "predicate": self.predicate,
            "taxonomy": str(self.taxonomy),
            "subject_kind": self.subject_kind,
            "target_kind": self.target_kind,
            "default_value": self.default_value,
            "provenance_reference": self.provenance_reference,
            "rationale": self.rationale,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class ScenarioPolicyProfile:
    """Immutable, versioned policy profile specifying assumption applicability."""

    profile_id: str
    version: str
    bound_snapshot_id: str
    evaluation_mode: str
    rules: tuple[ApplicabilityRule, ...]
    forbidden_predicates: tuple[str, ...]
    description: str
    assume_missing_group_type_security: bool = False

    def __post_init__(self) -> None:
        if type(self.assume_missing_group_type_security) is not bool:
            raise ValueError("assume_missing_group_type_security must be a boolean")
        if not (
            self.profile_id.strip() and self.version.strip() and self.bound_snapshot_id.strip()
        ):
            raise ValueError("profile_id, version, and bound_snapshot_id are required")
        if self.evaluation_mode not in (
            "evidence_only",
            "seamless_standard_scenario",
            "exploratory_what_if",
        ):
            raise ValueError(f"unsupported evaluation_mode: {self.evaluation_mode!r}")
        object.__setattr__(self, "rules", tuple(self.rules))
        object.__setattr__(
            self, "forbidden_predicates", tuple(sorted(set(self.forbidden_predicates)))
        )

    def canonical_dict(self) -> dict[str, Any]:
        return {
            "profile_id": self.profile_id,
            "version": self.version,
            "bound_snapshot_id": self.bound_snapshot_id,
            "evaluation_mode": self.evaluation_mode,
            "description": self.description,
            "forbidden_predicates": list(self.forbidden_predicates),
            "rules": [r.to_dict() for r in self.rules],
            **(
                {"assume_missing_group_type_security": True}
                if self.assume_missing_group_type_security
                else {}
            ),
        }

    def digest(self) -> str:
        payload = json.dumps(self.canonical_dict(), sort_keys=True, separators=(",", ":"))
        return f"sha256:{hashlib.sha256(payload.encode('utf-8')).hexdigest()}"

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.canonical_dict(), ensure_ascii=False, indent=indent) + "\n"


@dataclass(frozen=True)
class PolicyRejectionRecord:
    """Audit record for a candidate assumption rejected by the policy."""

    predicate: str
    subject: str
    target: str
    attempted_value: bool
    reason: str
    conflicting_value: Any = None
    conflicting_origin: str | None = None
    rationale: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "predicate": self.predicate,
            "subject": self.subject,
            "target": self.target,
            "attempted_value": self.attempted_value,
            "reason": self.reason,
            "conflicting_value": self.conflicting_value,
            "conflicting_origin": self.conflicting_origin,
            "rationale": self.rationale,
        }


def validate_policy_override(
    override: PolicyOverride,
    profile: ScenarioPolicyProfile,
) -> tuple[bool, PolicyRejectionRecord | None, dict[str, Any]]:
    """Validate an explicit policy override against profile constraints.

    Enforces:
    1. Attacker capability predicates (control, usable_identity, admin_control,
       relationship_exists) can NEVER be granted by policy override.
    2. Predicates forbidden by the active profile (e.g. recovery_success in
       standard mode) cannot be granted by policy override.
    3. recovery_success (when permitted in what-if profiles) requires
       override_type='recovery_opt_in' and structured metadata with
       non-empty 'method' and 'budget', defaulting 'horizon' to 'budget'.

    Returns:
        (is_valid, rejection_record_if_invalid, normalized_metadata)
    """
    pred, subj, tgt = override.predicate, override.subject, override.target

    if pred in ("control", "usable_identity", "admin_control", "relationship_exists"):
        rejection = PolicyRejectionRecord(
            predicate=pred,
            subject=subj,
            target=tgt,
            attempted_value=override.value,
            reason="override_violates_non_negotiable_security_boundary",
            rationale=(
                f"Attacker capability predicate {pred!r} cannot be granted by policy override"
            ),
        )
        return False, rejection, {}

    if pred in profile.forbidden_predicates:
        rejection = PolicyRejectionRecord(
            predicate=pred,
            subject=subj,
            target=tgt,
            attempted_value=override.value,
            reason="forbidden_to_default",
            rationale=(
                f"Predicate {pred!r} is strictly forbidden from defaulting in {profile.profile_id}"
            ),
        )
        return False, rejection, {}

    if pred == "recovery_success":
        if override.override_type != "recovery_opt_in":
            rejection = PolicyRejectionRecord(
                predicate=pred,
                subject=subj,
                target=tgt,
                attempted_value=override.value,
                reason="invalid_recovery_override_type",
                rationale=(
                    "Predicate 'recovery_success' requires "
                    f"override_type='recovery_opt_in', got {override.override_type!r}"
                ),
            )
            return False, rejection, {}

        method = override.metadata.get("method") if isinstance(override.metadata, Mapping) else None
        budget = override.metadata.get("budget") if isinstance(override.metadata, Mapping) else None
        if not (
            isinstance(method, str)
            and method.strip()
            and isinstance(budget, str)
            and budget.strip()
        ):
            rejection = PolicyRejectionRecord(
                predicate=pred,
                subject=subj,
                target=tgt,
                attempted_value=override.value,
                reason="invalid_recovery_opt_in_metadata",
                rationale=(
                    "recovery_opt_in requires structured metadata with "
                    "non-empty 'method' and 'budget'"
                ),
            )
            return False, rejection, {}

        ov_meta = dict(override.metadata)
        if not (isinstance(ov_meta.get("horizon"), str) and ov_meta["horizon"].strip()):
            ov_meta["horizon"] = budget
        return True, None, ov_meta

    return True, None, dict(override.metadata)


@dataclass(frozen=True)
class ScenarioPolicyResolutionResult:
    """Full outcome of applying a ScenarioPolicyProfile to a query and graph."""

    profile_id: str
    profile_digest: str
    evaluation_mode: str
    snapshot_id: str
    assumptions: tuple[RuntimeFact, ...]
    rejected_assumptions: tuple[PolicyRejectionRecord, ...]
    applied_overrides: tuple[PolicyOverride, ...]
    audit_summary: Mapping[str, Any]
    diagnostics: tuple[dict[str, Any], ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "profile_id": self.profile_id,
            "profile_digest": self.profile_digest,
            "evaluation_mode": self.evaluation_mode,
            "snapshot_id": self.snapshot_id,
            "assumptions_count": len(self.assumptions),
            "rejected_count": len(self.rejected_assumptions),
            "overrides_count": len(self.applied_overrides),
            "assumptions": [
                {
                    "predicate": a.predicate,
                    "subject": a.subject,
                    "target": a.target,
                    "value": a.value,
                    "origin": str(a.origin),
                    "scope": a.scope,
                    "rationale": a.rationale,
                    "provenance_reference": a.provenance_reference,
                    "assumption_metadata": dict(a.assumption_metadata or {}),
                }
                for a in self.assumptions
            ],
            "rejected_assumptions": [r.to_dict() for r in self.rejected_assumptions],
            "applied_overrides": [o.to_dict() for o in self.applied_overrides],
            "audit_summary": dict(self.audit_summary),
            "diagnostics": list(self.diagnostics),
        }


# Backwards compatibility / convenience alias
PolicyResolutionResult = ScenarioPolicyResolutionResult


# Standard SEAMLESS rules catalog
STANDARD_SEAMLESS_RULES: tuple[ApplicabilityRule, ...] = (
    # 1. Global Network / Protocol Reachability Rules
    ApplicabilityRule(
        rule_id="rule-global-kdc-reachable",
        predicate="network_kdc_reachable",
        taxonomy=RuleTaxonomy.GLOBAL,
        provenance_reference="policy://seamless/v1/network/kdc",
        rationale="Domain Controllers (KDCs) are network-reachable on port 88 within intranet",
    ),
    ApplicabilityRule(
        rule_id="rule-global-rpc-reachable",
        predicate="network_rpc_reachable",
        taxonomy=RuleTaxonomy.GLOBAL,
        provenance_reference="policy://seamless/v1/network/rpc",
        rationale="MS-RPC port 135/dynamic RPC reachable for directory/SAMR operations",
    ),
    ApplicabilityRule(
        rule_id="rule-global-winrm-reachable",
        predicate="network_winrm_reachable",
        taxonomy=RuleTaxonomy.GLOBAL,
        provenance_reference="policy://seamless/v1/network/winrm",
        rationale="WinRM ports 5985/5986 reachable to servers configured for remote management",
    ),
    ApplicabilityRule(
        rule_id="rule-global-winrm-service-running",
        predicate="service_winrm_running",
        taxonomy=RuleTaxonomy.GLOBAL,
        provenance_reference="policy://seamless/v1/service/winrm",
        rationale="WinRM service is running and listening on target computer",
    ),
    ApplicabilityRule(
        rule_id="rule-global-asrep-request-accepted",
        predicate="asrep_request_accepted",
        taxonomy=RuleTaxonomy.GLOBAL,
        provenance_reference="policy://seamless/v1/kerberos/asrep",
        rationale="KDC standard AS-REQ accepted for accounts with DONT_REQ_PREAUTH flag",
    ),
    ApplicabilityRule(
        rule_id="rule-global-service-ticket-accepted",
        predicate="service_ticket_request_accepted",
        taxonomy=RuleTaxonomy.GLOBAL,
        provenance_reference="policy://seamless/v1/kerberos/tgs",
        rationale="KDC standard TGS-REQ accepted for accounts with valid SPN",
    ),
    ApplicabilityRule(
        rule_id="rule-global-kerberos-usable",
        predicate="kerberos_authentication_usable",
        taxonomy=RuleTaxonomy.GLOBAL,
        provenance_reference="policy://seamless/v1/kerberos/auth",
        rationale="Kerberos authentication package is functional on domain member systems",
    ),
    ApplicabilityRule(
        rule_id="rule-global-kerberos-actor-authenticated",
        predicate="kerberos_actor_authenticated",
        taxonomy=RuleTaxonomy.GLOBAL,
        provenance_reference="policy://seamless/v1/kerberos/tgt",
        rationale="Authenticated logon session holds a valid Kerberos TGT",
    ),
    # 2. Typed Target / Administration Rules
    ApplicabilityRule(
        rule_id="rule-typed-admin-channel",
        predicate="admin_channel",
        taxonomy=RuleTaxonomy.TYPED,
        target_kind="Computer",
        provenance_reference="policy://seamless/v1/host/admin-channel",
        rationale="Administrative channel (SMB/WMI/WinRM) is available for local administrators",
    ),
    ApplicabilityRule(
        rule_id="rule-typed-admin-execution-context",
        predicate="admin_execution_context",
        taxonomy=RuleTaxonomy.TYPED,
        target_kind="Computer",
        provenance_reference="policy://seamless/v1/host/exec-context",
        rationale="Host execution context permits remote code execution for administrators",
    ),
    ApplicabilityRule(
        rule_id="rule-typed-endpoint-authorized",
        predicate="endpoint_authorized",
        taxonomy=RuleTaxonomy.TYPED,
        target_kind="Computer",
        provenance_reference="policy://seamless/v1/host/endpoint-auth",
        rationale="Target endpoint authorizes connections from designated administrator accounts",
    ),
    ApplicabilityRule(
        rule_id="rule-typed-host-admin-mapping",
        predicate="host_admin_mapping",
        taxonomy=RuleTaxonomy.TYPED,
        target_kind="Computer",
        provenance_reference="policy://seamless/v1/host/admin-mapping",
        rationale="Local administrator group mapping corresponds to AdminTo entitlement",
    ),
    ApplicabilityRule(
        rule_id="rule-typed-auth-accepted",
        predicate="authentication_accepted",
        taxonomy=RuleTaxonomy.TYPED,
        provenance_reference="policy://seamless/v1/auth/accepted",
        rationale="Target validates and accepts valid domain credentials",
    ),
    ApplicabilityRule(
        rule_id="rule-typed-winrm-auth-accepted",
        predicate="winrm_authentication_accepted",
        taxonomy=RuleTaxonomy.TYPED,
        target_kind="Computer",
        provenance_reference="policy://seamless/v1/auth/winrm-accepted",
        rationale="WinRM listener validates and accepts administrative credentials",
    ),
    ApplicabilityRule(
        rule_id="rule-typed-rdp-available",
        predicate="rdp_available",
        taxonomy=RuleTaxonomy.TYPED,
        target_kind="Computer",
        provenance_reference="policy://seamless/v1/service/rdp",
        rationale="Remote Desktop service is enabled and accepting connections",
    ),
    ApplicabilityRule(
        rule_id="rule-typed-winrm-available",
        predicate="winrm_available",
        taxonomy=RuleTaxonomy.TYPED,
        target_kind="Computer",
        provenance_reference="policy://seamless/v1/service/winrm-available",
        rationale="WinRM PowerShell remoting endpoint is available",
    ),
    # 3. Directory Object / DACL Rules
    ApplicabilityRule(
        rule_id="rule-typed-directory-write",
        predicate="directory_write_allowed",
        taxonomy=RuleTaxonomy.TYPED,
        provenance_reference="policy://seamless/v1/directory/write",
        rationale="Active Directory directory modification allowed under granted ACE rights",
    ),
    ApplicabilityRule(
        rule_id="rule-typed-password-policy-accepts",
        predicate="password_policy_accepts",
        taxonomy=RuleTaxonomy.TYPED,
        target_kind="User",
        provenance_reference="policy://seamless/v1/directory/password-policy",
        rationale="Password reset value satisfies domain password complexity and length policy",
    ),
    ApplicabilityRule(
        rule_id="rule-typed-membership-change",
        predicate="membership_change_allowed",
        taxonomy=RuleTaxonomy.TYPED,
        target_kind="Group",
        provenance_reference="policy://seamless/v1/directory/member-add",
        rationale="Modifying group member attribute allowed under granted object control ACE",
    ),
    ApplicabilityRule(
        rule_id="rule-typed-membership-usable",
        predicate="membership_usable",
        taxonomy=RuleTaxonomy.TYPED,
        target_kind="Group",
        provenance_reference="policy://seamless/v1/token/member-usable",
        rationale="Group SID is incorporated into access token upon session logon",
    ),
    ApplicabilityRule(
        rule_id="rule-typed-secret-valid",
        predicate="secret_valid",
        taxonomy=RuleTaxonomy.TYPED,
        provenance_reference="policy://seamless/v1/credential/secret-valid",
        rationale=(
            "Target account secret is current, unexpired, and matches directory password hash"
        ),
    ),
    ApplicabilityRule(
        rule_id="rule-typed-security-group",
        predicate="security_group",
        taxonomy=RuleTaxonomy.TYPED,
        target_kind="Group",
        provenance_reference="policy://seamless/v1/token/security-group",
        rationale="Target group is a security-enabled group capable of token authorization",
    ),
)


def create_seamless_standard_profile() -> ScenarioPolicyProfile:
    """Create the default SEAMLESS standard scenario policy profile."""
    return ScenarioPolicyProfile(
        profile_id="seamless-standard-v1",
        version="1.0.0",
        bound_snapshot_id=SEAMLESS_SNAPSHOT_ID,
        evaluation_mode="seamless_standard_scenario",
        rules=STANDARD_SEAMLESS_RULES,
        forbidden_predicates=tuple(sorted(FORBIDDEN_PREDICATES)),
        description=(
            "SEAMLESS standard scenario assumption profile: conditions safe Active Directory "
            "intranet reachability, protocol acceptance, and DACL write rights while strictly "
            "forbidding recovery_success, unverified distribution groups, and fictitious edges."
        ),
    )


def create_seamless_what_if_profile() -> ScenarioPolicyProfile:
    """Create the exploratory what-if policy profile supporting explicit opt-ins."""
    return ScenarioPolicyProfile(
        profile_id="seamless-what-if-v1",
        version="1.0.0",
        bound_snapshot_id=SEAMLESS_SNAPSHOT_ID,
        evaluation_mode="exploratory_what_if",
        rules=STANDARD_SEAMLESS_RULES,
        forbidden_predicates=tuple(sorted(FORBIDDEN_PREDICATES - {"recovery_success"})),
        description=(
            "SEAMLESS exploratory what-if profile: evaluates hypothetical scenarios "
            "including explicit password recovery opt-ins and group type assumptions."
        ),
    )


def create_evidence_only_profile() -> ScenarioPolicyProfile:
    """Create the evidence-only profile (strictly zero assumptions)."""
    return ScenarioPolicyProfile(
        profile_id="seamless-evidence-only-v1",
        version="1.0.0",
        bound_snapshot_id=SEAMLESS_SNAPSHOT_ID,
        evaluation_mode="evidence_only",
        rules=(),
        forbidden_predicates=tuple(sorted(FORBIDDEN_PREDICATES)),
        description=(
            "Evidence-only profile: zero assumptions declared; preserves raw observation state."
        ),
    )


SEAMLESS_STANDARD_PROFILE = create_seamless_standard_profile()
SEAMLESS_WHAT_IF_PROFILE = create_seamless_what_if_profile()
EVIDENCE_ONLY_PROFILE = create_evidence_only_profile()
NEO_STANDARD_PROFILE = ScenarioPolicyProfile(
    profile_id="neo-standard-v1",
    version="1.0.0",
    bound_snapshot_id=SEAMLESS_SNAPSHOT_ID,
    evaluation_mode="seamless_standard_scenario",
    rules=STANDARD_SEAMLESS_RULES,
    forbidden_predicates=tuple(sorted(FORBIDDEN_PREDICATES)),
    description=(
        "Neo scenario: groups with missing type are assumed security-enabled, including "
        "distribution-like names; observed non-security types and False facts still veto."
    ),
    assume_missing_group_type_security=True,
)

# Explicit static vulnerable-host scenario, separate from the network-identity survey.
# None of these rules supplies host admin control or fabricates a session edge.
NEO_HOST_SESSION_PROFILE = ScenarioPolicyProfile(
    profile_id="neo-host-session-v1",
    version="1.0.0",
    bound_snapshot_id=SEAMLESS_SNAPSHOT_ID,
    evaluation_mode="seamless_standard_scenario",
    rules=STANDARD_SEAMLESS_RULES
    + tuple(
        ApplicabilityRule(
            rule_id="neo-session-" + predicate,
            predicate=predicate,
            taxonomy=RuleTaxonomy.TYPED,
            subject_kind="Computer",
            target_kind="User",
            provenance_reference="policy://neo/host-session/v1/" + predicate,
            rationale=rationale,
        )
        for predicate, rationale in (
            ("session_present", "Reported session remains present in the static scenario"),
            ("session_fresh", "Reported session remains fresh in the static scenario"),
            (
                "credential_accessible",
                "Scenario assumes credential access is not blocked by host protections",
            ),
            (
                "session_identity_usable",
                "Scenario assumes reusable domain credentials, not merely an opaque artifact",
            ),
        )
    ),
    forbidden_predicates=tuple(sorted(FORBIDDEN_PREDICATES)),
    description=(
        "Static host-compromise scenario: Computer sources have declared local admin control; "
        "observed sessions are assumed fresh with accessible reusable domain credentials. "
        "These are conditional assumptions, not observed credential recovery or P=1."
    ),
    assume_missing_group_type_security=True,
)

PROFILE_REGISTRY: dict[str, ScenarioPolicyProfile] = {
    "neo-host-session-v1": NEO_HOST_SESSION_PROFILE,
    "neo-standard-v1": NEO_STANDARD_PROFILE,
    "seamless-standard-v1": SEAMLESS_STANDARD_PROFILE,
    "seamless_standard_scenario": SEAMLESS_STANDARD_PROFILE,
    "standard": SEAMLESS_STANDARD_PROFILE,
    "seamless-what-if-v1": SEAMLESS_WHAT_IF_PROFILE,
    "exploratory_what_if": SEAMLESS_WHAT_IF_PROFILE,
    "what_if": SEAMLESS_WHAT_IF_PROFILE,
    "seamless-evidence-only-v1": EVIDENCE_ONLY_PROFILE,
    "evidence_only": EVIDENCE_ONLY_PROFILE,
}


def load_policy_profile(
    profile_identifier: str | Path | ScenarioPolicyProfile | Mapping[str, Any],
) -> ScenarioPolicyProfile:
    """Resolve a policy profile by identifier, path, or direct instance."""
    if isinstance(profile_identifier, ScenarioPolicyProfile):
        return profile_identifier
    if isinstance(profile_identifier, str) and profile_identifier in PROFILE_REGISTRY:
        return PROFILE_REGISTRY[profile_identifier]
    path = None if isinstance(profile_identifier, Mapping) else Path(profile_identifier)
    if isinstance(profile_identifier, Mapping) or path.is_file():
        data = (
            profile_identifier
            if isinstance(profile_identifier, Mapping)
            else json.loads(path.read_text(encoding="utf-8"))
        )
        rules = tuple(
            ApplicabilityRule(
                rule_id=r["rule_id"],
                predicate=r["predicate"],
                taxonomy=RuleTaxonomy(r["taxonomy"]),
                subject_kind=r.get("subject_kind"),
                target_kind=r.get("target_kind"),
                default_value=r.get("default_value", True),
                provenance_reference=r.get("provenance_reference", "policy://custom"),
                rationale=r.get("rationale", "Custom rule"),
                metadata=r.get("metadata", {}),
            )
            for r in data.get("rules", [])
        )
        return ScenarioPolicyProfile(
            profile_id=data["profile_id"],
            version=data["version"],
            bound_snapshot_id=data["bound_snapshot_id"],
            evaluation_mode=data["evaluation_mode"],
            rules=rules,
            forbidden_predicates=tuple(data.get("forbidden_predicates", ())),
            description=data.get("description", ""),
            assume_missing_group_type_security=data.get(
                "assume_missing_group_type_security", False
            ),
        )
    raise ValueError(f"unknown scenario policy profile: {profile_identifier!r}")


def _classify_group_for_policy(node, label, profile):
    classification, basis, details = classify_ad_group_type_with_basis(node, label)
    if profile.assume_missing_group_type_security and basis in {
        "distribution_naming_pattern",
        "unrecognized_missing_group_type",
    }:
        return (
            "security_group",
            "scenario_assumed_missing_group_type",
            "Neo assumes security-enabled group because type attributes are missing; "
            "the label is not evidence of group type",
        )
    return classification, basis, details


def _group_rationale(label, basis):
    if basis == "scenario_assumed_missing_group_type":
        return f"Group {label}: security-enabled is a neo scenario assumption, not observed type"
    return f"Group {label} is a verified security group ({basis})"


def _extract_nodes_and_edges(
    graph: Any,
) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]], Any]:
    """Extract nodes index, edges list, and optional snapshot facts from graph."""
    if hasattr(graph, "to_canonical") and callable(graph.to_canonical):
        canon = getattr(graph, "_canonical_cache", None)
        if canon is None:
            canon = graph.to_canonical()
        nodes_dict = {n["id"]: n for n in canon.get("nodes", [])}
        edges_list = list(canon.get("edges", []))
        snapshot_facts = getattr(graph, "snapshot_facts", None)
    elif hasattr(graph, "nodes") and callable(graph.nodes):
        sample = next(iter(graph.nodes()), None)
        if isinstance(sample, Mapping) and "id" in sample:
            nodes_dict = {n["id"]: n for n in graph.nodes()}
            edges_list = list(graph.edges())
        else:
            # Raw networkx Graph/MultiDiGraph
            nodes_dict = {
                nid: {"id": nid, **(data.get("record", data))}
                for nid, data in graph.nodes(data=True)
            }
            edges_list = [
                d.get("record", {"source": u, "target": v, "kind": d.get("kind", ""), **d})
                for u, v, *rest, d in graph.edges(data=True)
            ]
        snapshot_facts = getattr(graph, "snapshot_facts", None)
    elif isinstance(graph, Mapping):
        nodes_dict = {n["id"]: n for n in graph.get("nodes", [])}
        edges_list = list(graph.get("edges", []))
        snapshot_facts = graph.get("snapshot_facts")
    else:
        raise TypeError(f"unsupported graph type: {type(graph).__name__}")
    return nodes_dict, edges_list, snapshot_facts


def _normalize_query_dict(query: Any) -> dict[str, Any]:
    """Convert an AttackQuery dataclass or mapping into a dictionary."""
    if hasattr(query, "__dataclass_fields__"):
        res: dict[str, Any] = {}
        for f in query.__dataclass_fields__:
            val = getattr(query, f)
            if val is not None:
                res[f] = val
        return res
    if isinstance(query, Mapping):
        return dict(query)
    raise TypeError(f"unsupported query type: {type(query).__name__}")


def resolve_scenario_policy(
    graph: Any,
    query: Any,
    profile: ScenarioPolicyProfile | str = "evidence_only",
    overrides: Sequence[PolicyOverride | Mapping[str, Any]] = (),
    *,
    enforce_snapshot_binding: bool = True,
) -> ScenarioPolicyResolutionResult:
    """Resolve scenario policy assumptions for a query against a graph.

    Generates only the applicable, authorized assumptions for the query scope,
    enforcing snapshot integrity, known-false vetoes, distribution group limits,
    and forbidden-predicate restrictions.
    """
    resolved_profile = load_policy_profile(profile)
    profile_digest = resolved_profile.digest()
    nodes_dict, edges_list, snapshot_facts = _extract_nodes_and_edges(graph)
    q_dict = _normalize_query_dict(query)

    # 1. Enforce snapshot binding
    graph_snapshot = None
    if snapshot_facts is not None and hasattr(snapshot_facts, "snapshot_id"):
        graph_snapshot = snapshot_facts.snapshot_id
    if not graph_snapshot:
        if isinstance(graph, Mapping) and "metadata" in graph:
            graph_snapshot = graph["metadata"].get("snapshot_id")
        elif hasattr(graph, "metadata") and isinstance(graph.metadata, Mapping):
            graph_snapshot = graph.metadata.get("snapshot_id")
        elif hasattr(graph, "to_canonical") and callable(graph.to_canonical):
            graph_snapshot = graph.to_canonical().get("metadata", {}).get("snapshot_id")

    if enforce_snapshot_binding:
        if not graph_snapshot:
            raise ValueError(
                "authoritative snapshot_id is required; graph snapshot identity is missing; "
                f"profile {resolved_profile.profile_id} requires binding to snapshot "
                f"{resolved_profile.bound_snapshot_id}"
            )
        if graph_snapshot != resolved_profile.bound_snapshot_id:
            raise ValueError(
                f"profile {resolved_profile.profile_id} bound to snapshot "
                f"{resolved_profile.bound_snapshot_id}, but graph has {graph_snapshot}"
            )

    # 2. Parse explicit overrides with conflict validation
    norm_overrides: list[PolicyOverride] = []
    seen_overrides: dict[tuple[str, str, str], PolicyOverride] = {}
    for ov in overrides or ():
        parsed_ov: PolicyOverride
        if isinstance(ov, PolicyOverride):
            parsed_ov = ov
        elif isinstance(ov, Mapping):
            parsed_ov = PolicyOverride(
                predicate=ov["predicate"],
                subject=ov["subject"],
                target=ov["target"],
                value=ov.get("value", True),
                override_type=ov.get("override_type", "scoped_opt_in"),
                rationale=ov.get("rationale", "Explicit scenario override"),
                metadata=ov.get("metadata", {}),
            )
        else:
            raise TypeError(f"unsupported override type: {type(ov).__name__}")

        key = (parsed_ov.predicate, parsed_ov.subject, parsed_ov.target)
        if key in seen_overrides:
            prev = seen_overrides[key]
            if prev.value != parsed_ov.value:
                raise ValueError(
                    f"conflicting policy overrides for {key}: "
                    f"value {prev.value!r} conflicts with {parsed_ov.value!r}"
                )
            continue
        seen_overrides[key] = parsed_ov
        norm_overrides.append(parsed_ov)

    # 3. If evidence_only mode: zero assumptions, record explicit overrides as rejected
    if resolved_profile.evaluation_mode == "evidence_only":
        rejected = [
            PolicyRejectionRecord(
                predicate=ov.predicate,
                subject=ov.subject,
                target=ov.target,
                attempted_value=ov.value,
                reason="profile_evidence_only_rejects_all_overrides",
                rationale=(
                    f"Profile {resolved_profile.profile_id} enforces evidence-only mode; "
                    "all overrides are rejected"
                ),
            )
            for ov in norm_overrides
        ]
        return ScenarioPolicyResolutionResult(
            profile_id=resolved_profile.profile_id,
            profile_digest=profile_digest,
            evaluation_mode="evidence_only",
            snapshot_id=resolved_profile.bound_snapshot_id,
            assumptions=(),
            rejected_assumptions=tuple(rejected),
            applied_overrides=(),
            audit_summary={
                "mode": "evidence_only",
                "assumptions_generated": 0,
                "assumptions_rejected": len(rejected),
            },
            diagnostics=(),
        )

    # 4. Determine query scope
    initial_actor = q_dict.get("initial_actor") or q_dict.get("source_foothold")
    auth_ctx = q_dict.get("authentication_context") or initial_actor
    initial_state = q_dict.get("initial_state") or {}
    known_identities = list(
        initial_state.known_identity
        if isinstance(initial_state, AttackState)
        else initial_state.get("known_identity", [])
    )
    controlled_actors = list(
        initial_state.control
        if isinstance(initial_state, AttackState)
        else initial_state.get("control", [])
    )
    raw_usable = (
        initial_state.usable_identity
        if isinstance(initial_state, AttackState)
        else initial_state.get("usable_identity", [])
    )
    usable_identities = [
        u[0] if isinstance(u, (list, tuple)) else u
        for u in raw_usable
        if isinstance(u, (list, tuple)) or isinstance(u, str)
    ]
    target_principal = q_dict.get("target") or (
        q_dict.get("target_goal", {}).get("target")
        if isinstance(q_dict.get("target_goal"), Mapping)
        else None
    )

    # Base actors who can potentially traverse paths
    base_actors = set()
    if initial_actor:
        base_actors.add(initial_actor)
    for ident in known_identities:
        base_actors.add(ident)
    for ctrl in controlled_actors:
        base_actors.add(ctrl)
    for uid in usable_identities:
        base_actors.add(uid)

    # Allowed edge kinds according to allowed techniques
    allowed_techs = q_dict.get("allowed_techniques")
    if allowed_techs:
        allowed_kinds = {
            TECHNIQUE_EDGE_KINDS[t] for t in allowed_techs if t in TECHNIQUE_EDGE_KINDS
        }
    else:
        allowed_kinds = {
            "AdminTo",
            "MemberOf",
            "GenericAll",
            "WriteDacl",
            "CanRDP",
            "CanPSRemote",
        }

    # Bounded query-local candidate edges
    if len(edges_list) > 200:
        budget = q_dict.get("budget", {})
        max_hops = budget.get("max_steps", 10) if isinstance(budget, Mapping) else 10
        max_hops = min(max(max_hops or 10, 1), 15)

        adj_forward: dict[str, list[dict[str, Any]]] = {}
        for edge in edges_list:
            if edge.get("kind") in allowed_kinds:
                adj_forward.setdefault(edge["source"], []).append(edge)

        seeds = set(base_actors)
        for ov in norm_overrides:
            seeds.add(ov.subject)
            seeds.add(ov.target)

        visited_nodes = set(seeds)
        current_level = set(seeds)
        candidate_edge_ids: set[Any] = set()

        for _ in range(max_hops):
            next_level = set()
            for u in current_level:
                is_seed = u in seeds
                for edge in adj_forward.get(u, []):
                    v = edge["target"]
                    tgt_kind = nodes_dict.get(v, {}).get("kind")
                    kind = edge.get("kind")
                    edge_id = edge.get("id") or (edge["source"], kind, edge["target"])
                    if is_seed:
                        candidate_edge_ids.add(edge_id)
                        if kind == "MemberOf" or (
                            kind in ("GenericAll", "WriteDacl") and tgt_kind == "Group"
                        ):
                            if v not in visited_nodes:
                                visited_nodes.add(v)
                                next_level.add(v)
                    else:
                        # For intermediate groups reachable via MemberOf/delegation:
                        # Avoid pre-materializing the whole reachable group fan-out!
                        if kind == "MemberOf" or (
                            kind in ("GenericAll", "WriteDacl") and tgt_kind == "Group"
                        ):
                            candidate_edge_ids.add(edge_id)
                            if v not in visited_nodes:
                                visited_nodes.add(v)
                                next_level.add(v)
                        elif target_principal and (
                            v == target_principal or edge["source"] == target_principal
                        ):
                            candidate_edge_ids.add(edge_id)
            current_level = next_level
            if not current_level:
                break

        if target_principal:
            for edge in edges_list:
                if edge.get("kind") in allowed_kinds and (
                    edge["target"] == target_principal or edge["source"] == target_principal
                ):
                    edge_id = edge.get("id") or (edge["source"], edge["kind"], edge["target"])
                    candidate_edge_ids.add(edge_id)

        for ov in norm_overrides:
            for edge in edges_list:
                if (edge["source"], edge["target"]) == (ov.subject, ov.target) or (
                    edge["source"],
                    edge["target"],
                ) == (ov.target, ov.subject):
                    edge_id = edge.get("id") or (edge["source"], edge["kind"], edge["target"])
                    candidate_edge_ids.add(edge_id)

        candidate_edges = [
            e
            for e in edges_list
            if (e.get("id") or (e["source"], e["kind"], e["target"])) in candidate_edge_ids
        ]
    else:
        candidate_edges = edges_list

    # Identify candidate target pairs in graph for scoped assumption generation
    rules_by_pred: dict[str, list[ApplicabilityRule]] = {}
    for r in resolved_profile.rules:
        rules_by_pred.setdefault(r.predicate, []).append(r)

    candidate_assumptions: dict[
        tuple[str, str, str], tuple[bool, str, str, str, dict[str, Any]]
    ] = {}
    rejected: list[PolicyRejectionRecord] = []
    diagnostics: list[dict[str, Any]] = []

    def match_rule(pred: str, subj: str, tgt: str) -> ApplicabilityRule | None:
        rules = rules_by_pred.get(pred, [])
        if not rules:
            return None
        subj_kind = nodes_dict.get(subj, {}).get("kind")
        tgt_kind = nodes_dict.get(tgt, {}).get("kind")
        for r in rules:
            if r.subject_kind is not None and subj_kind != r.subject_kind:
                continue
            if r.target_kind is not None and tgt_kind != r.target_kind:
                continue
            return r
        return None

    def propose_candidate(
        pred: str,
        subj: str,
        tgt: str,
        meta_extra: dict[str, Any] | None = None,
        custom_rationale: str | None = None,
    ) -> None:
        rule = match_rule(pred, subj, tgt)
        if rule is None:
            return
        candidate_assumptions[(pred, subj, tgt)] = (
            rule.default_value,
            rule.provenance_reference,
            custom_rationale or rule.rationale,
            rule.rule_id,
            {**rule.metadata, **(meta_extra or {})},
        )

    # Map existing query runtime facts for known-false checking
    existing_facts = q_dict.get("runtime_facts", ())
    auth_false_keys: set[tuple[str, str, str]] = set()
    for f in existing_facts:
        p = getattr(f, "predicate", None) or (f.get("predicate") if isinstance(f, dict) else None)
        s = getattr(f, "subject", None) or (f.get("subject") if isinstance(f, dict) else None)
        t = getattr(f, "target", None) or (f.get("target") if isinstance(f, dict) else None)
        v = (
            getattr(f, "value", None)
            if hasattr(f, "value")
            else (f.get("value") if isinstance(f, dict) else None)
        )
        if v is False and p and s and t:
            auth_false_keys.add((p, s, t))

    # Helper to check if a node has enabled=False in snapshot
    def is_node_disabled(node_id: str) -> bool:
        node_data = nodes_dict.get(node_id, {})
        if node_data.get("enabled") is False:
            return True
        props = (
            node_data.get("properties") if isinstance(node_data.get("properties"), Mapping) else {}
        )
        return props.get("enabled") is False

    # A. Edge-derived assumptions for structural relationships in graph
    for edge in candidate_edges:
        src_id, tgt_id, kind = edge["source"], edge["target"], edge["kind"]
        tgt_node = nodes_dict.get(tgt_id, {})
        tgt_props = (
            tgt_node.get("properties") if isinstance(tgt_node.get("properties"), Mapping) else {}
        )
        tgt_kind = tgt_node.get("kind") or tgt_props.get("kind", "")
        tgt_label = (
            tgt_node.get("label")
            or tgt_node.get("name")
            or tgt_props.get("name")
            or tgt_props.get("label")
            or tgt_id
        )
        src_node = nodes_dict.get(src_id, {})
        src_props = (
            src_node.get("properties") if isinstance(src_node.get("properties"), Mapping) else {}
        )
        src_kind = src_node.get("kind") or src_props.get("kind", "")

        # Identify candidate actors who can traverse or execute this edge
        applicable_actors = {src_id} | (base_actors if src_kind == "Group" else set())

        if kind == "MemberOf":
            # Target is a Group. Member is src_id.
            # Check Active Directory group classification
            grp_class, grp_basis, grp_provenance = _classify_group_for_policy(
                tgt_node, tgt_label, resolved_profile
            )

            if grp_class == "distribution_group":
                diagnostics.append(
                    {
                        "action": "distribution_group_detected",
                        "group_id": tgt_id,
                        "label": tgt_label,
                        "status": "requires_scoped_override",
                        "classification_basis": grp_basis,
                        "identity_provenance": grp_provenance,
                    }
                )
                if "security_group" in rules_by_pred:
                    rejected.append(
                        PolicyRejectionRecord(
                            predicate="security_group",
                            subject=src_id,
                            target=tgt_id,
                            attempted_value=True,
                            reason="distribution_group_cannot_default",
                            rationale=(
                                f"Group {tgt_label!r} has distribution list naming or "
                                "distribution groupType; DACL rights cannot propagate "
                                "without explicit opt-in"
                            ),
                        )
                    )
            elif grp_class == "security_group":
                # Recognized or authoritative security group
                for act_subj in applicable_actors:
                    propose_candidate(
                        "security_group",
                        act_subj,
                        tgt_id,
                        meta_extra={
                            "group_label": tgt_label,
                            "group_kind": "security_group",
                            "classification_basis": grp_basis,
                            "identity_provenance": grp_provenance,
                        },
                        custom_rationale=(_group_rationale(tgt_label, grp_basis)),
                    )
                    propose_candidate(
                        "membership_usable",
                        act_subj,
                        tgt_id,
                        custom_rationale="Group membership is incorporated into session token",
                    )
            else:
                # Conservative Active Directory semantics: missing or unverified groupType
                # stays unknown unless backed by authoritative evidence or scoped override.
                diagnostics.append(
                    {
                        "action": "unrecognized_group_detected",
                        "group_id": tgt_id,
                        "label": tgt_label,
                        "status": "unresolved_missing_group_type",
                        "classification_basis": grp_basis,
                        "identity_provenance": grp_provenance,
                    }
                )

        elif kind == "AdminTo":
            # Host execution prerequisites for direct source and candidate actors
            for act_subj in applicable_actors:
                propose_candidate(
                    "admin_channel",
                    act_subj,
                    tgt_id,
                    meta_extra={"host_kind": tgt_kind},
                    custom_rationale=f"Administrative channel available on target host {tgt_label}",
                )
                propose_candidate(
                    "authentication_accepted",
                    act_subj,
                    tgt_id,
                    custom_rationale=(
                        f"Host {tgt_label} accepts domain credentials for authorized local admin"
                    ),
                )
            if src_kind == "Group":
                propose_candidate(
                    "host_admin_mapping",
                    src_id,
                    tgt_id,
                    custom_rationale=(
                        f"Local administrator group mapping corresponds to AdminTo "
                        f"entitlement on {tgt_label}"
                    ),
                )

        elif kind == "GenericAll":
            if tgt_kind == "User":
                for act_subj in applicable_actors:
                    propose_candidate(
                        "directory_write_allowed",
                        act_subj,
                        tgt_id,
                        custom_rationale=(
                            f"Directory modification permitted under GenericAll on User {tgt_label}"
                        ),
                    )
                    propose_candidate(
                        "password_policy_accepts",
                        act_subj,
                        tgt_id,
                        custom_rationale="Password reset complies with domain password policy",
                    )
                    propose_candidate(
                        "network_rpc_reachable",
                        act_subj,
                        tgt_id,
                        custom_rationale="MS-RPC reachable for SAMR password reset",
                    )
            elif tgt_kind == "Group":
                grp_class, grp_basis, grp_provenance = _classify_group_for_policy(
                    tgt_node, tgt_label, resolved_profile
                )

                if grp_class == "security_group":
                    for act_subj in applicable_actors:
                        propose_candidate(
                            "security_group",
                            act_subj,
                            tgt_id,
                            meta_extra={
                                "group_label": tgt_label,
                                "group_kind": "security_group",
                                "classification_basis": grp_basis,
                                "identity_provenance": grp_provenance,
                            },
                            custom_rationale=(_group_rationale(tgt_label, grp_basis)),
                        )
                elif grp_class == "distribution_group":
                    if "security_group" in rules_by_pred:
                        rejected.append(
                            PolicyRejectionRecord(
                                predicate="security_group",
                                subject=src_id,
                                target=tgt_id,
                                attempted_value=True,
                                reason="distribution_group_cannot_default",
                                rationale=(
                                    f"Group {tgt_label!r} is a distribution group "
                                    "(by distribution groupType, security_enabled=False, "
                                    "or distribution naming); DACL rights cannot propagate "
                                    "without explicit opt-in"
                                ),
                            )
                        )
                else:
                    diagnostics.append(
                        {
                            "action": "unrecognized_group_detected",
                            "group_id": tgt_id,
                            "label": tgt_label,
                            "status": "unresolved_missing_group_type",
                            "classification_basis": grp_basis,
                            "identity_provenance": grp_provenance,
                        }
                    )
                for act_subj in applicable_actors:
                    propose_candidate(
                        "membership_change_allowed",
                        act_subj,
                        tgt_id,
                        custom_rationale=(
                            f"Adding members allowed under GenericAll on Group {tgt_label}"
                        ),
                    )
                    propose_candidate(
                        "directory_write_allowed",
                        act_subj,
                        tgt_id,
                        custom_rationale=f"Directory write allowed on Group {tgt_label}",
                    )
            else:
                for act_subj in applicable_actors:
                    propose_candidate(
                        "directory_write_allowed",
                        act_subj,
                        tgt_id,
                        custom_rationale=f"Directory write allowed on {tgt_kind} {tgt_label}",
                    )

        elif kind == "WriteDacl":
            for act_subj in applicable_actors:
                propose_candidate(
                    "directory_write_allowed",
                    act_subj,
                    tgt_id,
                    custom_rationale=(
                        f"Directory write allowed under WriteDacl on {tgt_kind} {tgt_label}"
                    ),
                )

        elif kind == "CanRDP":
            for act_subj in applicable_actors:
                propose_candidate(
                    "rdp_available",
                    act_subj,
                    tgt_id,
                    custom_rationale=f"RDP service available on {tgt_label}",
                )
                propose_candidate(
                    "authentication_accepted",
                    act_subj,
                    tgt_id,
                    custom_rationale=f"RDP accepts credentials for {act_subj}",
                )

        elif kind == "CanPSRemote":
            for act_subj in applicable_actors:
                propose_candidate(
                    "winrm_available",
                    act_subj,
                    tgt_id,
                    custom_rationale=f"WinRM remoting available on {tgt_label}",
                )
                propose_candidate(
                    "authentication_accepted",
                    act_subj,
                    tgt_id,
                    custom_rationale=f"WinRM accepts credentials for {act_subj}",
                )

    # B. Credential / Identity-acquisition assumptions
    # 1. AS-REP roasting & Kerberoasting for declared known identities
    for ident in known_identities:
        ident_node = nodes_dict.get(ident, {})
        ident_label = ident_node.get("label", ident)

        # AS-REP Request
        if initial_actor:
            propose_candidate(
                "network_kdc_reachable",
                initial_actor,
                ident,
                custom_rationale="KDC network reachable from initial foothold",
            )
            propose_candidate(
                "asrep_request_accepted",
                initial_actor,
                ident,
                custom_rationale=f"KDC accepts AS-REQ for preauth-disabled identity {ident_label}",
            )
            # Kerberoast
            propose_candidate(
                "service_ticket_request_accepted",
                initial_actor,
                ident,
                custom_rationale=f"KDC issues service ticket for SPN identity {ident_label}",
            )

        # Identity activation on workstation / auth context
        if auth_ctx:
            propose_candidate(
                "secret_valid",
                ident,
                auth_ctx,
                custom_rationale=f"Recovered secret for {ident_label} is valid in domain",
            )
            propose_candidate(
                "network_kdc_reachable",
                ident,
                auth_ctx,
                custom_rationale="KDC reachable for logon authentication",
            )
            propose_candidate(
                "authentication_accepted",
                ident,
                auth_ctx,
                custom_rationale=(
                    f"Logon authentication accepted for {ident_label} in context {auth_ctx}"
                ),
            )

    # 2. GenericAll password reset identity acquisition:
    # If a user target of GenericAll is reset, acquire_reset_identity binds to auth_ctx
    for edge in candidate_edges:
        if edge.get("kind") == "GenericAll":
            tgt_node = nodes_dict.get(edge["target"], {})
            if tgt_node.get("kind") == "User" and auth_ctx:
                tgt_id = edge["target"]
                tgt_label = tgt_node.get("label", tgt_id)
                propose_candidate(
                    "secret_valid",
                    tgt_id,
                    auth_ctx,
                    custom_rationale=f"Reset password for {tgt_label} is accepted by KDC",
                )
                propose_candidate(
                    "network_kdc_reachable",
                    tgt_id,
                    auth_ctx,
                    custom_rationale="KDC reachable for logon after password reset",
                )
                propose_candidate(
                    "authentication_accepted",
                    tgt_id,
                    auth_ctx,
                    custom_rationale=f"Authentication accepted for reset user {tgt_label}",
                )

    # 3. Foothold kerberos usability
    if initial_actor and auth_ctx:
        propose_candidate(
            "kerberos_authentication_usable",
            initial_actor,
            auth_ctx,
            custom_rationale="Kerberos package functional on foothold host",
        )
        propose_candidate(
            "kerberos_actor_authenticated",
            initial_actor,
            auth_ctx,
            custom_rationale="Actor possesses initial Kerberos TGT",
        )

    # C. Apply explicit user overrides
    override_by_key: dict[tuple[str, str, str], PolicyOverride] = {}
    for ov in norm_overrides:
        key = (ov.predicate, ov.subject, ov.target)
        is_valid, rejection, ov_meta = validate_policy_override(ov, resolved_profile)
        if not is_valid:
            assert rejection is not None
            rejected.append(rejection)
            continue

        candidate_assumptions[key] = (
            ov.value,
            f"override://seamless/{ov.override_type}",
            ov.rationale,
            f"override-{ov.override_type}",
            ov_meta,
        )
        override_by_key[key] = ov

        # If overriding security_group to True, also provide paired membership_usable
        if ov.predicate == "security_group" and ov.value is True:
            paired_key = ("membership_usable", ov.subject, ov.target)
            candidate_assumptions[paired_key] = (
                True,
                f"override://seamless/{ov.override_type}",
                f"Token membership usable under security group override for {ov.target}",
                f"override-{ov.override_type}-membership",
                ov_meta,
            )

    # D. Filter, enforce forbidden-to-default, and enforce known-false vetoes
    overrides_applied: list[PolicyOverride] = []
    final_facts: list[RuntimeFact] = []
    scope_tag = f"seamless-policy:{resolved_profile.profile_id}"

    for (pred, subj, tgt), (val, prov, rat, rule_id, meta) in sorted(candidate_assumptions.items()):
        key = (pred, subj, tgt)

        # Check 1: Authoritative False in runtime_facts
        if key in auth_false_keys:
            rejected.append(
                PolicyRejectionRecord(
                    predicate=pred,
                    subject=subj,
                    target=tgt,
                    attempted_value=val,
                    reason="known_false_veto",
                    conflicting_value=False,
                    conflicting_origin="runtime_facts",
                    rationale=(
                        f"Authoritative False fact in runtime context vetoes assumption {pred}"
                    ),
                )
            )
            continue

        # Check 2: Authoritative False in snapshot properties: disabled-object veto
        # If either subject or target node has enabled=False in snapshot, veto candidate assumption.
        disabled_node = None
        if is_node_disabled(subj):
            disabled_node = subj
        elif is_node_disabled(tgt):
            disabled_node = tgt

        if disabled_node is not None:
            rejected.append(
                PolicyRejectionRecord(
                    predicate=pred,
                    subject=subj,
                    target=tgt,
                    attempted_value=val,
                    reason="known_false_veto",
                    conflicting_value=False,
                    conflicting_origin="snapshot_property",
                    rationale=(f"Node {disabled_node} has enabled=False in authoritative snapshot"),
                )
            )
            continue

        # Check 3: Authoritative False in snapshot_facts (e.g. dontreqpreauth is False)
        if snapshot_facts is not None and hasattr(snapshot_facts, "lookup"):
            try:
                sf_val = snapshot_facts.lookup(tgt, pred)
                if sf_val is not None and getattr(sf_val, "value", None) is False:
                    rejected.append(
                        PolicyRejectionRecord(
                            predicate=pred,
                            subject=subj,
                            target=tgt,
                            attempted_value=val,
                            reason="known_false_veto",
                            conflicting_value=False,
                            conflicting_origin="snapshot_facts",
                            rationale=f"SnapshotFacts lookup({tgt}, {pred}) is False",
                        )
                    )
                    continue
            except KeyError, ValueError:
                pass

        # Check 4: Forbidden-to-default predicates
        if pred in resolved_profile.forbidden_predicates:
            rejected.append(
                PolicyRejectionRecord(
                    predicate=pred,
                    subject=subj,
                    target=tgt,
                    attempted_value=val,
                    reason="forbidden_to_default",
                    rationale=(
                        f"Predicate {pred!r} is strictly forbidden from "
                        f"defaulting in {resolved_profile.profile_id}"
                    ),
                )
            )
            continue

        fact = RuntimeFact(
            predicate=pred,
            subject=subj,
            target=tgt,
            value=val,
            origin=FactOrigin.DECLARED_ASSUMPTION,
            scope=scope_tag,
            rationale=rat,
            provenance_reference=prov,
            assumption_metadata={
                "rule_id": rule_id,
                "profile_id": resolved_profile.profile_id,
                "profile_digest": profile_digest,
                "policy_version": resolved_profile.version,
                **meta,
            },
        )
        final_facts.append(fact)
        if key in override_by_key:
            overrides_applied.append(override_by_key[key])
            diagnostics.append(
                {
                    "action": "override_applied",
                    "predicate": pred,
                    "subject": subj,
                    "target": tgt,
                    "override_type": override_by_key[key].override_type,
                }
            )

    audit_summary = {
        "profile_id": resolved_profile.profile_id,
        "evaluation_mode": resolved_profile.evaluation_mode,
        "bound_snapshot_id": resolved_profile.bound_snapshot_id,
        "total_rules": len(resolved_profile.rules),
        "assumptions_resolved": len(final_facts),
        "assumptions_rejected": len(rejected),
        "overrides_applied": len(overrides_applied),
        "forbidden_predicates_enforced": list(resolved_profile.forbidden_predicates),
    }

    return ScenarioPolicyResolutionResult(
        profile_id=resolved_profile.profile_id,
        profile_digest=profile_digest,
        evaluation_mode=resolved_profile.evaluation_mode,
        snapshot_id=resolved_profile.bound_snapshot_id,
        assumptions=tuple(final_facts),
        rejected_assumptions=tuple(rejected),
        applied_overrides=tuple(overrides_applied),
        audit_summary=audit_summary,
        diagnostics=tuple(diagnostics),
    )


def apply_policy_to_query(
    query: Any,
    graph: Any,
    profile: ScenarioPolicyProfile | str = "evidence_only",
    overrides: Sequence[PolicyOverride | Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Compile policy assumptions and return an updated scenario query dict.

    Reconciles existing assumptions in the query with policy-derived assumptions,
    failing closed on value contradictions or forbidden-to-default predicates.
    """
    resolved_profile = load_policy_profile(profile)
    q_dict = _normalize_query_dict(query)
    resolution = resolve_scenario_policy(graph, q_dict, profile, overrides)

    # Reconcile existing assumptions from query with policy-resolved assumptions
    existing_raw = q_dict.get("assumptions") or q_dict.get("declared_assumptions") or []
    existing_assumptions: list[dict[str, Any]] = []
    for f in existing_raw:
        if isinstance(f, RuntimeFact):
            existing_assumptions.append(
                {
                    "predicate": f.predicate,
                    "subject": f.subject,
                    "target": f.target,
                    "value": f.value,
                    "origin": str(f.origin),
                    "scope": f.scope,
                    "rationale": f.rationale,
                    "provenance_reference": f.provenance_reference,
                    "assumption_metadata": dict(f.assumption_metadata or {}),
                }
            )
        elif isinstance(f, Mapping):
            existing_assumptions.append(dict(f))
        else:
            raise TypeError(f"unsupported assumption type: {type(f).__name__}")

    policy_assumptions = [
        {
            "predicate": a.predicate,
            "subject": a.subject,
            "target": a.target,
            "value": a.value,
            "origin": str(a.origin),
            "scope": a.scope,
            "rationale": a.rationale,
            "provenance_reference": a.provenance_reference,
            "assumption_metadata": dict(a.assumption_metadata or {}),
        }
        for a in resolution.assumptions
    ]

    merged_by_key: dict[tuple[str, str, str], dict[str, Any]] = {}
    for ef in existing_assumptions:
        k = (ef["predicate"], ef["subject"], ef["target"])
        if (
            resolution.evaluation_mode != "evidence_only"
            and ef["predicate"] in resolved_profile.forbidden_predicates
        ):
            raise ValueError(
                f"existing query assumption {ef['predicate']!r} on {k} is forbidden "
                f"by policy profile {resolved_profile.profile_id}"
            )
        merged_by_key[k] = ef

    for pf in policy_assumptions:
        k = (pf["predicate"], pf["subject"], pf["target"])
        if k in merged_by_key:
            ef = merged_by_key[k]
            if ef.get("value", True) != pf.get("value", True):
                raise ValueError(
                    f"conflicting assumption for {k}: existing value "
                    f"{ef.get('value')!r} conflicts with policy value {pf.get('value')!r}"
                )
            continue
        merged_by_key[k] = pf

    updated = dict(q_dict)
    if resolution.evaluation_mode == "evidence_only":
        rejected_existing = [
            PolicyRejectionRecord(
                predicate=ef["predicate"],
                subject=ef["subject"],
                target=ef["target"],
                attempted_value=ef.get("value", True),
                reason="profile_evidence_only_rejects_all_assumptions",
                rationale=(
                    f"Profile {resolved_profile.profile_id} enforces evidence-only mode; "
                    f"existing assumption {ef['predicate']!r} is rejected."
                ),
            )
            for ef in existing_assumptions
        ]
        all_rejections = list(resolution.rejected_assumptions) + rejected_existing
        updated["evaluation_mode"] = "evidence_only"
        updated["assumptions"] = []
        updated["scenario_policy_metadata"] = {
            "profile_id": resolution.profile_id,
            "profile_digest": resolution.profile_digest,
            "evaluation_mode": resolution.evaluation_mode,
            "snapshot_id": resolution.snapshot_id,
            "assumptions_count": 0,
            "policy_assumptions_count": 0,
            "rejected_count": len(all_rejections),
            "rejected_assumptions": [r.to_dict() for r in all_rejections],
            "applied_overrides": [o.to_dict() for o in resolution.applied_overrides],
        }
        return updated

    updated["evaluation_mode"] = "scenario"
    updated["assumptions"] = list(merged_by_key.values())

    # Attach policy metadata to query
    updated["scenario_policy_metadata"] = {
        "profile_id": resolution.profile_id,
        "profile_digest": resolution.profile_digest,
        "evaluation_mode": resolution.evaluation_mode,
        "snapshot_id": resolution.snapshot_id,
        "assumptions_count": len(updated["assumptions"]),
        "policy_assumptions_count": len(resolution.assumptions),
        "rejected_count": len(resolution.rejected_assumptions),
        "rejected_assumptions": [r.to_dict() for r in resolution.rejected_assumptions],
        "applied_overrides": [o.to_dict() for o in resolution.applied_overrides],
    }
    if resolved_profile.assume_missing_group_type_security:
        if hasattr(graph, "to_prepared"):
            nodes = graph.to_prepared().nodes_by_id.values()
        elif isinstance(graph, Mapping):
            nodes = graph["nodes"]
        else:
            nodes = _extract_nodes_and_edges(graph)[0].values()
        updated["scenario_policy_metadata"].update(
            on_demand=True,
            profile=resolved_profile.canonical_dict(),
            non_security_group_ids=sorted(
                n["id"]
                for n in nodes
                if n.get("kind") == "Group"
                and classify_ad_group_type_with_basis(n)[1]
                == "authoritative_distribution_attribute"
            ),
        )
        vetoes = set(updated["scenario_policy_metadata"]["non_security_group_ids"])
        if any(
            f["target"] in vetoes
            and f["predicate"] in {"security_group", "membership_usable"}
            and f.get("value", True) is True
            for f in updated["assumptions"]
        ):
            raise ValueError(
                "Group assumption conflicts with authoritative non-security attributes"
            )
    return updated


class PolicyAssumptionResolver(Mapping[tuple[str, str, str], RuntimeFact]):
    """Bounded on-demand assumption cache and resolver for scenario policies.

    Enables consumers (such as Batch runner or Interactive Viewer) to resolve
    policy-governed facts on-demand during graph traversal or transition evaluation,
    avoiding the cost of pre-materializing Cartesian products or reachable group fan-out.
    """

    def __init__(
        self,
        graph: Any,
        query: Any = None,
        profile: ScenarioPolicyProfile | str = "evidence_only",
        overrides: Sequence[PolicyOverride | Mapping[str, Any]] | None = None,
        *,
        max_cache_size: int = 10000,
        enforce_snapshot_binding: bool = True,
        allowed_predicates: frozenset[str] | None = None,
    ) -> None:
        self.profile = load_policy_profile(profile)
        self._profile_digest = self.profile.digest()
        if hasattr(graph, "to_prepared") or hasattr(graph, "nodes_by_id"):
            prepared = graph.to_prepared() if hasattr(graph, "to_prepared") else graph
            self.nodes_dict = prepared.nodes_by_id
            self.edges_list = ()
            self.snapshot_facts = prepared.snapshot_facts
        else:
            self.nodes_dict, self.edges_list, self.snapshot_facts = _extract_nodes_and_edges(graph)
        self.query_dict = _normalize_query_dict(query) if query is not None else {}
        self.non_security_group_ids = set(
            (self.query_dict.get("scenario_policy_metadata") or {}).get(
                "non_security_group_ids", ()
            )
        )
        self.max_cache_size = max_cache_size
        self.allowed_predicates = allowed_predicates

        # Validate snapshot binding
        graph_snapshot = None
        if self.snapshot_facts is not None and hasattr(self.snapshot_facts, "snapshot_id"):
            graph_snapshot = self.snapshot_facts.snapshot_id
        if not graph_snapshot:
            if isinstance(graph, Mapping) and "metadata" in graph:
                graph_snapshot = graph["metadata"].get("snapshot_id")
            elif hasattr(graph, "metadata") and isinstance(graph.metadata, Mapping):
                graph_snapshot = graph.metadata.get("snapshot_id")
            elif hasattr(graph, "to_canonical") and callable(graph.to_canonical):
                graph_snapshot = graph.to_canonical().get("metadata", {}).get("snapshot_id")

        if enforce_snapshot_binding:
            if not graph_snapshot:
                raise ValueError(
                    "authoritative snapshot_id is required; graph snapshot identity is missing; "
                    f"profile {self.profile.profile_id} requires binding to snapshot "
                    f"{self.profile.bound_snapshot_id}"
                )
            if graph_snapshot != self.profile.bound_snapshot_id:
                raise ValueError(
                    f"profile {self.profile.profile_id} bound to snapshot "
                    f"{self.profile.bound_snapshot_id}, but graph has {graph_snapshot}"
                )

        # Parse overrides
        self.overrides_by_key: dict[tuple[str, str, str], PolicyOverride] = {}
        self._user_overrides_by_key: dict[tuple[str, str, str], PolicyOverride] = {}
        self._applied_overrides: dict[tuple[str, str, str], PolicyOverride] = {}
        for ov in overrides or ():
            parsed_ov: PolicyOverride
            if isinstance(ov, PolicyOverride):
                parsed_ov = ov
            elif isinstance(ov, Mapping):
                parsed_ov = PolicyOverride(
                    predicate=ov["predicate"],
                    subject=ov["subject"],
                    target=ov["target"],
                    value=ov.get("value", True),
                    override_type=ov.get("override_type", "scoped_opt_in"),
                    rationale=ov.get("rationale", "Explicit scenario override"),
                    metadata=ov.get("metadata", {}),
                )
            else:
                raise TypeError(f"unsupported override type: {type(ov).__name__}")
            k = (parsed_ov.predicate, parsed_ov.subject, parsed_ov.target)
            if k in self.overrides_by_key:
                prev = self.overrides_by_key[k]
                if prev.value != parsed_ov.value:
                    raise ValueError(
                        f"conflicting policy overrides for {k}: "
                        f"value {prev.value!r} conflicts with {parsed_ov.value!r}"
                    )
            self.overrides_by_key[k] = parsed_ov
            self._user_overrides_by_key[k] = parsed_ov
            # If overriding security_group to True, also provide paired membership_usable
            # only if the security_group override itself is valid for this profile!
            if parsed_ov.predicate == "security_group" and parsed_ov.value is True:
                is_valid, _, _ = validate_policy_override(parsed_ov, self.profile)
                if is_valid:
                    paired_k = ("membership_usable", parsed_ov.subject, parsed_ov.target)
                    if paired_k not in self.overrides_by_key:
                        self.overrides_by_key[paired_k] = PolicyOverride(
                            predicate="membership_usable",
                            subject=parsed_ov.subject,
                            target=parsed_ov.target,
                            value=True,
                            override_type=parsed_ov.override_type,
                            rationale=(
                                "Token membership usable under security group override for "
                                f"{parsed_ov.target}"
                            ),
                            metadata=dict(parsed_ov.metadata),
                        )

        # Check existing facts for authoritative False
        self.auth_false_keys: set[tuple[str, str, str]] = set()
        for f in self.query_dict.get("runtime_facts", ()):
            p = getattr(f, "predicate", None) or (
                f.get("predicate") if isinstance(f, dict) else None
            )
            s = getattr(f, "subject", None) or (f.get("subject") if isinstance(f, dict) else None)
            t = getattr(f, "target", None) or (f.get("target") if isinstance(f, dict) else None)
            v = (
                getattr(f, "value", None)
                if hasattr(f, "value")
                else (f.get("value") if isinstance(f, dict) else None)
            )
            if v is False and p and s and t:
                self.auth_false_keys.add((p, s, t))

        # Build rules index
        self.rules_by_pred: dict[str, list[ApplicabilityRule]] = {}
        for r in self.profile.rules:
            self.rules_by_pred.setdefault(r.predicate, []).append(r)

        self._cache: OrderedDict[tuple[str, str, str], RuntimeFact] = OrderedDict()
        self._negative_keys: OrderedDict[tuple[str, str, str], None] = OrderedDict()
        self._rejections: list[PolicyRejectionRecord] = []
        self._diagnostics: list[dict[str, Any]] = []

        if self.profile.evaluation_mode == "evidence_only":
            for ov in self._user_overrides_by_key.values():
                self._rejections.append(
                    PolicyRejectionRecord(
                        predicate=ov.predicate,
                        subject=ov.subject,
                        target=ov.target,
                        attempted_value=ov.value,
                        reason="profile_evidence_only_rejects_all_overrides",
                        rationale=(
                            f"Profile {self.profile.profile_id} enforces evidence-only mode; "
                            "all overrides are rejected"
                        ),
                    )
                )

    def _is_node_disabled(self, node_id: str) -> bool:
        node = self.nodes_dict.get(node_id, {})
        if node.get("enabled") is False:
            return True
        props = node.get("properties") if isinstance(node.get("properties"), Mapping) else {}
        return props.get("enabled") is False

    def for_graph(self, graph):
        """Keep the declared scenario, with a fresh cache on a counterfactual graph."""
        return type(self)(
            graph,
            self.query_dict,
            self.profile,
            overrides=tuple(self._user_overrides_by_key.values()),
            max_cache_size=self.max_cache_size,
            allowed_predicates=self.allowed_predicates,
        )

    def _match_rule(self, pred: str, subj: str, tgt: str) -> ApplicabilityRule | None:
        rules = self.rules_by_pred.get(pred, [])
        if not rules:
            return None
        subj_kind = self.nodes_dict.get(subj, {}).get("kind")
        tgt_kind = self.nodes_dict.get(tgt, {}).get("kind")
        for r in rules:
            if r.subject_kind is not None and subj_kind != r.subject_kind:
                continue
            if r.target_kind is not None and tgt_kind != r.target_kind:
                continue
            return r
        return None

    def _resolve_single(self, key: tuple[str, str, str]) -> RuntimeFact | None:
        if self.profile.evaluation_mode == "evidence_only":
            return None

        pred, subj, tgt = key
        if self.allowed_predicates is not None and pred not in self.allowed_predicates:
            return None
        if pred in {"security_group", "membership_usable"} and tgt in self.non_security_group_ids:
            return None

        # 1. Authoritative False in runtime facts
        if key in self.auth_false_keys:
            self._rejections.append(
                PolicyRejectionRecord(
                    predicate=pred,
                    subject=subj,
                    target=tgt,
                    attempted_value=True,
                    reason="known_false_veto",
                    conflicting_value=False,
                    conflicting_origin="runtime_facts",
                    rationale=(
                        f"Authoritative False fact in runtime context vetoes assumption {pred}"
                    ),
                )
            )
            return None

        # 2. Disabled-object veto
        disabled_node = None
        if self._is_node_disabled(subj):
            disabled_node = subj
        elif self._is_node_disabled(tgt):
            disabled_node = tgt
        if disabled_node is not None:
            self._rejections.append(
                PolicyRejectionRecord(
                    predicate=pred,
                    subject=subj,
                    target=tgt,
                    attempted_value=True,
                    reason="known_false_veto",
                    conflicting_value=False,
                    conflicting_origin="snapshot_property",
                    rationale=f"Node {disabled_node} has enabled=False in authoritative snapshot",
                )
            )
            return None

        # 3. Authoritative False in snapshot_facts (e.g. dontreqpreauth is False)
        if self.snapshot_facts is not None and hasattr(self.snapshot_facts, "lookup"):
            try:
                sf_val = self.snapshot_facts.lookup(tgt, pred)
                if sf_val is not None and getattr(sf_val, "value", None) is False:
                    self._rejections.append(
                        PolicyRejectionRecord(
                            predicate=pred,
                            subject=subj,
                            target=tgt,
                            attempted_value=True,
                            reason="known_false_veto",
                            conflicting_value=False,
                            conflicting_origin="snapshot_facts",
                            rationale=f"SnapshotFacts lookup({tgt}, {pred}) is False",
                        )
                    )
                    return None
            except KeyError, ValueError:
                pass

        # 4. Explicit override
        if key in self.overrides_by_key:
            ov = self.overrides_by_key[key]
            is_valid, rejection, ov_meta = validate_policy_override(ov, self.profile)
            if not is_valid:
                assert rejection is not None
                self._rejections.append(rejection)
                return None
            if key in self._user_overrides_by_key:
                self._applied_overrides[key] = self._user_overrides_by_key[key]
            return RuntimeFact(
                predicate=pred,
                subject=subj,
                target=tgt,
                value=ov.value,
                origin=FactOrigin.DECLARED_ASSUMPTION,
                scope=f"seamless-policy:{self.profile.profile_id}",
                rationale=ov.rationale,
                provenance_reference=f"override://seamless/{ov.override_type}",
                assumption_metadata={
                    "rule_id": f"override-{ov.override_type}",
                    "profile_id": self.profile.profile_id,
                    "profile_digest": self._profile_digest,
                    "policy_version": self.profile.version,
                    **ov_meta,
                },
            )

        # 5. Forbidden predicates
        if pred in self.profile.forbidden_predicates:
            self._rejections.append(
                PolicyRejectionRecord(
                    predicate=pred,
                    subject=subj,
                    target=tgt,
                    attempted_value=True,
                    reason="forbidden_to_default",
                    rationale=(
                        f"Predicate {pred!r} is strictly forbidden from "
                        f"defaulting in {self.profile.profile_id}"
                    ),
                )
            )
            return None

        # 6. Rule match
        rule = self._match_rule(pred, subj, tgt)
        if rule is None:
            return None

        # Group-specific predicates
        if pred in ("security_group", "membership_usable"):
            tgt_node = self.nodes_dict.get(tgt, {})
            tgt_props = (
                tgt_node.get("properties")
                if isinstance(tgt_node.get("properties"), Mapping)
                else {}
            )
            tgt_label = (
                tgt_node.get("label")
                or tgt_node.get("name")
                or tgt_props.get("name")
                or tgt_props.get("label")
                or tgt
            )
            grp_class, grp_basis, grp_provenance = _classify_group_for_policy(
                tgt_node, tgt_label, self.profile
            )

            if grp_class == "distribution_group":
                self._rejections.append(
                    PolicyRejectionRecord(
                        predicate=pred,
                        subject=subj,
                        target=tgt,
                        attempted_value=rule.default_value,
                        reason="distribution_group_cannot_default",
                        rationale=(
                            f"Group {tgt_label!r} is a distribution group "
                            "(by distribution groupType, security_enabled=False, "
                            "or distribution naming); DACL rights cannot propagate "
                            "without explicit opt-in"
                        ),
                    )
                )
                return None
            elif grp_class != "security_group":
                self._diagnostics.append(
                    {
                        "action": "unrecognized_group_detected",
                        "group_id": tgt,
                        "label": tgt_label,
                        "status": "unresolved_missing_group_type",
                        "classification_basis": grp_basis,
                        "identity_provenance": grp_provenance,
                    }
                )
                return None

            if pred == "security_group":
                return RuntimeFact(
                    predicate=pred,
                    subject=subj,
                    target=tgt,
                    value=rule.default_value,
                    origin=FactOrigin.DECLARED_ASSUMPTION,
                    scope=f"seamless-policy:{self.profile.profile_id}",
                    rationale=_group_rationale(tgt_label, grp_basis),
                    provenance_reference=rule.provenance_reference,
                    assumption_metadata={
                        "rule_id": rule.rule_id,
                        "profile_id": self.profile.profile_id,
                        "profile_digest": self._profile_digest,
                        "policy_version": self.profile.version,
                        "group_label": tgt_label,
                        "group_kind": "security_group",
                        "classification_basis": grp_basis,
                        "identity_provenance": grp_provenance,
                        **rule.metadata,
                    },
                )

        return RuntimeFact(
            predicate=pred,
            subject=subj,
            target=tgt,
            value=rule.default_value,
            origin=FactOrigin.DECLARED_ASSUMPTION,
            scope=f"seamless-policy:{self.profile.profile_id}",
            rationale=rule.rationale,
            provenance_reference=rule.provenance_reference,
            assumption_metadata={
                "rule_id": rule.rule_id,
                "profile_id": self.profile.profile_id,
                "profile_digest": self._profile_digest,
                "policy_version": self.profile.version,
                **rule.metadata,
            },
        )

    def __getitem__(self, key: tuple[str, str, str]) -> RuntimeFact:
        if key in self._cache:
            self._cache.move_to_end(key)
            return self._cache[key]
        if key in self._negative_keys:
            raise KeyError(key)
        fact = self._resolve_single(key)
        if fact is None:
            if len(self._negative_keys) >= self.max_cache_size:
                self._negative_keys.popitem(last=False)
            self._negative_keys[key] = None
            raise KeyError(key)
        self._cache[key] = fact
        self._cache.move_to_end(key)
        if len(self._cache) > self.max_cache_size:
            self._cache.popitem(last=False)
        return fact

    def __iter__(self) -> Iterator[tuple[str, str, str]]:
        return iter(self._cache)

    def __len__(self) -> int:
        return len(self._cache)

    def __contains__(self, key: Any) -> bool:
        if not isinstance(key, tuple) or len(key) != 3:
            return False
        try:
            self[key]
            return True
        except KeyError:
            return False

    @property
    def resolved_assumptions(self) -> tuple[RuntimeFact, ...]:
        return tuple(self._cache.values())

    @property
    def rejected_assumptions(self) -> tuple[PolicyRejectionRecord, ...]:
        return tuple(self._rejections)

    @property
    def applied_overrides(self) -> tuple[PolicyOverride, ...]:
        return tuple(self._applied_overrides.values())

    @property
    def diagnostics(self) -> tuple[dict[str, Any], ...]:
        return tuple(self._diagnostics)
