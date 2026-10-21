"""Validate the official M2 structural graph contract and synthetic fixtures."""

from __future__ import annotations

import copy
import functools
import hashlib
import json
import math
import re
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
CORE_NODE_FIELDS = {"id", "kind", "label"}
REQUIRED_NODE_FIELDS = CORE_NODE_FIELDS | {"domain", "is_boundary"}
CORE_NODE_FIELD_TYPES = {
    "id": "canonical_id",
    "kind": "node_kind",
    "label": "nonempty_string",
}
SUPPORTED_NODE_FIELD_TYPES = {
    "canonical_id",
    "node_kind",
    "nonempty_string",
    "boolean",
    "integer",
    "boolean_or_integer",
}
CORE_EDGE_FIELDS = {"id", "source", "target", "kind", "weight", "provenance"}
EXPECTED_EDGE_FIELD_TYPES = {
    "id": "canonical_edge_id",
    "source": "canonical_node_id",
    "target": "canonical_node_id",
    "kind": "edge_kind",
    "weight": "positive_number",
    "provenance": "positive_provenance_records",
    "derivation": "derived_lineage",
}
EXPECTED_NODE_KINDS = {"User", "Computer", "Group", "Domain", "OU", "GPO"}
EXPECTED_EDGE_KINDS = {
    "MemberOf",
    "AdminTo",
    "GenericAll",
    "WriteDacl",
    "ForceChangePassword",
    "CanRDP",
    "CanPSRemote",
    "HasSession",
}
PROVENANCE_REQUIRED_FIELDS = {
    "raw_file",
    "collector",
    "timestamp",
    "evidence_type",
    "timestamp_status",
}
PROVENANCE_OPTIONAL_FIELDS = {"record_id", "attribute", "time_provenance_reason"}
RAW_PROVENANCE_OPTIONAL_FIELDS = {
    "record_id",
    "attribute",
    "snapshot_id",
    "record_locator",
    "time_provenance",
    "time_provenance_reason",
    "schema_version",
}
ASSESSMENT_STATUSES = {"unknown", "inferred", "rejected"}
CURRENT_CONTRACT_VERSION = "1.3.0"
SUPPORTED_PREVIOUS_CONTRACT_VERSIONS = {"1.0.0", "1.1.0", "1.2.0"}
LEGACY_TIMESTAMP_VERSIONS = {"1.0.0", "1.1.0"}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def nonempty_string(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def compile_pattern(value: object, name: str) -> re.Pattern[str]:
    require(nonempty_string(value), f"{name} must be a nonempty regex")
    try:
        return re.compile(value)
    except re.error as exc:
        raise ValueError(f"{name} must be a valid regex: {exc}") from exc


def _valid_domain_sid_scoped_id(value: str) -> bool:
    parts = value.split(":")
    if len(parts) != 4 or parts[:2] != ["domain", "sid"]:
        return False
    domain_parts = parts[2].split("-")
    target_parts = parts[3].split("-")
    if len(domain_parts) != 7 or domain_parts[:4] != ["S", "1", "5", "21"]:
        return False
    if not all(
        part.isdecimal() and (part == "0" or not part.startswith("0")) for part in domain_parts[4:]
    ):
        return False
    if any(int(part) > (1 << 32) - 1 for part in domain_parts[4:]):
        return False
    if len(target_parts) < 4 or target_parts[:2] != ["S", "1"]:
        return False
    try:
        authority = int(target_parts[2])
        return authority <= (1 << 48) - 1 and all(
            part.isdecimal()
            and (part == "0" or not part.startswith("0"))
            and int(part) <= (1 << 32) - 1
            for part in target_parts[3:]
        )
    except ValueError:
        return False


def canonical_id_patterns(
    contract: dict,
) -> tuple[re.Pattern[str], re.Pattern[str], re.Pattern[str], re.Pattern[str]]:
    canonical_id = contract["schema"]["canonical_id"]
    return (
        compile_pattern(canonical_id.get("sid_pattern"), "canonical_id.sid_pattern"),
        compile_pattern(canonical_id.get("guid_pattern"), "canonical_id.guid_pattern"),
        compile_pattern(canonical_id.get("scoped_sid_pattern"), "canonical_id.scoped_sid_pattern"),
        compile_pattern(
            canonical_id.get("scope_required_sid_pattern"),
            "canonical_id.scope_required_sid_pattern",
        ),
    )


def canonical_edge_id(source: str, target: str, kind: str) -> str:
    payload = json.dumps([source, target, kind], ensure_ascii=True, separators=(",", ":")).encode(
        "utf-8"
    )
    return f"sha256:{hashlib.sha256(payload).hexdigest()}"


def provenance_reference(record: dict) -> str:
    payload = json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return f"sha256:{hashlib.sha256(payload.encode('utf-8')).hexdigest()}"


def _valid_nested_host_access_sequence(edge_kind: str, operations: tuple[object, ...]) -> bool:
    membership = "effective_membership"
    host_local = "host_local_membership"
    effective_right = "effective_right"
    if edge_kind in {"AdminTo", "CanPSRemote"}:
        return (
            len(operations) >= 2
            and operations[-1] == host_local
            and all(operation == membership for operation in operations[:-1])
        )
    if edge_kind == "CanRDP":
        if operations.count(host_local) > 1 or operations.count(effective_right) > 1:
            return False
        host_index = operations.index(host_local) if host_local in operations else None
        membership_branch = operations[:host_index] if host_index is not None else ()
        right_branch = operations[host_index + 1 :] if host_index is not None else operations
        if host_index is not None and (
            len(membership_branch) < 1
            or membership_branch[-1] != membership
            or any(operation != membership for operation in membership_branch)
        ):
            return False
        if not right_branch:
            return host_index is not None
        return (
            len(right_branch) >= 2
            and right_branch[-1] == effective_right
            and all(operation == membership for operation in right_branch[:-1])
        )
    return False


def _validate_nested_host_access_endpoints(
    steps: list[dict], edge: dict, node_kinds: dict[str, str]
) -> None:
    """Validate that nested membership and host/right steps form causal branches."""

    principal_kinds = {"User", "Group", "Computer"}
    operations = [step["operation"] for step in steps]
    host_index = (
        operations.index("host_local_membership") if "host_local_membership" in operations else None
    )
    if host_index is not None:
        host_step = steps[host_index]
        require(
            {"source", "target"} <= set(host_step) and host_step["target"] == edge["target"],
            f"edge {edge['id']}: host-local membership must terminate at the edge target",
        )
        membership_steps = steps[:host_index]
        expected_source = edge["source"]
        for step in membership_steps:
            require(
                step["operation"] == "effective_membership"
                and {"source", "target"} <= set(step)
                and step["source"] == expected_source
                and node_kinds.get(step["source"]) in principal_kinds
                and node_kinds.get(step["target"]) == "Group",
                f"edge {edge['id']}: nested membership steps are not a causal chain",
            )
            expected_source = step["target"]
        require(
            host_step["source"] == expected_source,
            f"edge {edge['id']}: host-local membership does not follow its membership chain",
        )
        require(
            node_kinds.get(host_step["source"]) in principal_kinds
            and node_kinds.get(host_step["target"]) == "Computer",
            f"edge {edge['id']}: host-local membership endpoints have invalid node kinds",
        )

    right_steps = steps[host_index + 1 :] if host_index is not None else steps
    if right_steps:
        expected_source = edge["source"]
        for step in right_steps[:-1]:
            require(
                step["operation"] == "effective_membership"
                and {"source", "target"} <= set(step)
                and step["source"] == expected_source
                and node_kinds.get(step["source"]) in principal_kinds
                and node_kinds.get(step["target"]) == "Group",
                f"edge {edge['id']}: effective-right membership is not a causal chain",
            )
            expected_source = step["target"]
        right_step = right_steps[-1]
        require(
            right_step["operation"] == "effective_right"
            and {"source", "target"} <= set(right_step)
            and right_step["source"] == expected_source
            and node_kinds.get(right_step["source"]) in principal_kinds
            and right_step["target"] == "SeRemoteInteractiveLogonRight",
            f"edge {edge['id']}: CanRDP lineage must terminate in the effective allow right",
        )


def _validate_field_type(
    value: object,
    field_type: str,
    field: str,
    *,
    contract: dict,
    node_ident: str,
    contract_version: str | None = None,
) -> None:
    prefix = f"node '{node_ident}'" if node_ident else "record"
    if field_type in {"canonical_id", "canonical_node_id"}:
        sid_pattern, guid_pattern, scoped_sid_pattern, scope_required_sid_pattern = (
            canonical_id_patterns(contract)
        )
        is_unscoped_sid = isinstance(value, str) and sid_pattern.fullmatch(value) is not None
        require(
            isinstance(value, str)
            and (
                (is_unscoped_sid and scope_required_sid_pattern.fullmatch(value) is None)
                or guid_pattern.fullmatch(value) is not None
                or scoped_sid_pattern.fullmatch(value) is not None
            ),
            (
                f"{prefix}: invalid canonical id "
                "(expected unambiguous SID, scoped SID, or lowercase GUID)"
            ),
        )
        if isinstance(value, str) and value.startswith("domain:sid:"):
            require(
                contract_version is None or contract_version == CURRENT_CONTRACT_VERSION,
                f"{prefix}: Domain-SID-scoped canonical id requires Contract 1.3.0",
            )
            require(
                _valid_domain_sid_scoped_id(value),
                f"{prefix}: invalid Domain-SID-scoped canonical id",
            )
    elif field_type == "node_kind":
        require(value in contract["node_kinds"], f"{prefix}: unknown kind")
    elif field_type == "edge_kind":
        require(value in contract["edge_kinds"], f"{prefix}: unknown edge kind")
    elif field_type == "nonempty_string":
        require(nonempty_string(value), f"{prefix}: invalid {field}")
    elif field_type == "boolean":
        require(type(value) is bool, f"{prefix}: {field} must be boolean")
    elif field_type == "integer":
        require(
            type(value) is int and type(value) is not bool, f"{prefix}: {field} must be integer"
        )
    elif field_type == "boolean_or_integer":
        require(type(value) in (bool, int), f"{prefix}: {field} must be boolean or integer")


def validate_node(
    node: dict, contract: dict, *, contract_version: str | None = None, **_patterns: re.Pattern[str]
) -> None:
    node_ident = node.get("id") or node.get("label") or "<unknown>"
    schema = contract["schema"]
    allowed_fields = set(schema["node_required"]) | set(schema["node_optional"])
    unknown_fields = set(node) - allowed_fields
    require(not unknown_fields, f"node '{node_ident}': unsupported fields {sorted(unknown_fields)}")
    field_types = schema["node_field_types"]
    for field in schema["node_required"]:
        require(field in node, f"node '{node_ident}': missing required field {field}")
    for field, value in node.items():
        _validate_field_type(
            value,
            field_types[field],
            field,
            contract=contract,
            node_ident=node_ident,
            contract_version=contract_version,
        )
    if node["is_boundary"]:
        require(
            node["kind"] in contract["schema"]["boundary"]["allowed_kinds"],
            f"node '{node_ident}': invalid boundary kind",
        )


def _validate_timestamp(timestamp: object, pattern: re.Pattern[str], prefix: str) -> None:
    require(isinstance(timestamp, str), f"{prefix} has invalid timestamp")
    require(pattern.fullmatch(timestamp) is not None, f"{prefix} has invalid timestamp")
    try:
        datetime.strptime(timestamp, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError as exc:
        raise ValueError(f"{prefix} has invalid timestamp") from exc


def validate_provenance(
    records: object,
    contract: dict,
    owner_id: str,
    *,
    allowed_evidence_types: set[str],
    contract_version: str | None = None,
) -> None:
    require(isinstance(records, list) and bool(records), f"{owner_id}: invalid provenance")
    schema = contract["schema"]["provenance"]
    is_legacy = contract_version in LEGACY_TIMESTAMP_VERSIONS
    required_fields = set(schema["required"])
    allowed_fields = required_fields | set(schema["optional"])
    if is_legacy:
        required_fields.discard("timestamp_status")
        allowed_fields.discard("timestamp_status")
        allowed_fields.discard("time_provenance_reason")
    timestamp_pattern = compile_pattern(schema["timestamp_pattern"], "provenance.timestamp_pattern")
    seen: set[tuple[tuple[str, object], ...]] = set()
    for index, record in enumerate(records):
        prefix = f"{owner_id}: provenance[{index}]"
        require(isinstance(record, dict), f"{prefix} must be a mapping")
        require(required_fields <= set(record), f"{prefix} is missing required fields")
        unknown_fields = set(record) - allowed_fields
        require(not unknown_fields, f"{prefix} has unsupported fields {sorted(unknown_fields)}")
        require(
            all(nonempty_string(value) for value in record.values()), f"{prefix} has invalid values"
        )
        require(
            record["evidence_type"] in allowed_evidence_types,
            f"{prefix} has invalid evidence_type",
        )
        _validate_timestamp(record["timestamp"], timestamp_pattern, prefix)
        if not is_legacy:
            statuses = set(schema["timestamp_statuses"])
            require(
                isinstance(record["timestamp_status"], str)
                and record["timestamp_status"] in statuses,
                f"{prefix}: invalid timestamp_status",
            )
            if record["timestamp_status"] in set(schema["reason_required_statuses"]):
                require(
                    nonempty_string(record.get("time_provenance_reason")),
                    f"{prefix}: timestamp status requires a time-provenance reason",
                )
            elif "time_provenance_reason" in record:
                require(
                    nonempty_string(record["time_provenance_reason"]),
                    f"{prefix}: invalid time-provenance reason",
                )
        fingerprint = tuple(sorted(record.items()))
        require(fingerprint not in seen, f"{prefix} duplicates audit evidence")
        seen.add(fingerprint)


def validate_derivation(
    derivation: object,
    edge: dict,
    contract: dict,
    node_ids: set[str],
    node_kinds: dict[str, str],
) -> None:
    schema = contract["schema"]["derivation"]
    require(isinstance(derivation, dict), f"edge {edge['id']}: derivation must be a mapping")
    require(
        set(derivation) == {"version", "kind", "paths"},
        f"edge {edge['id']}: malformed derivation fields",
    )
    require(
        derivation["version"] == schema["version"],
        f"edge {edge['id']}: unsupported derivation version",
    )
    require(derivation["kind"] in schema["kinds"], f"edge {edge['id']}: invalid derivation kind")
    require(
        edge["kind"] in schema["derived_edge_kinds"],
        f"edge {edge['id']}: derivation is not allowed on a direct-only edge kind",
    )
    paths = derivation["paths"]
    require(isinstance(paths, list) and bool(paths), f"edge {edge['id']}: derivation has no paths")
    provenance_refs = {provenance_reference(item) for item in edge["provenance"]}
    path_keys: list[str] = []
    for path_index, path in enumerate(paths):
        path_fields = set(schema["path_required"]) | set(schema["path_optional"])
        require(
            isinstance(path, dict)
            and set(schema["path_required"]) <= set(path)
            and set(path) <= path_fields,
            f"edge {edge['id']}: malformed derivation path {path_index}",
        )
        if edge["kind"] == "CanRDP":
            conditions = path.get("conditions")
            required_predicates = schema["required_conditions"]["CanRDP"]
            require(
                isinstance(conditions, list)
                and [
                    condition.get("predicate") if isinstance(condition, dict) else None
                    for condition in conditions
                ]
                == required_predicates,
                f"edge {edge['id']}: CanRDP path must name every required proof condition",
            )
            for condition in conditions:
                require(
                    isinstance(condition, dict)
                    and set(condition) == set(schema["condition_required"]),
                    f"edge {edge['id']}: malformed derivation condition",
                )
                refs = condition["evidence_refs"]
                require(
                    isinstance(refs, list) and bool(refs) and refs == sorted(set(refs)),
                    f"edge {edge['id']}: invalid condition evidence_refs",
                )
                for ref in refs:
                    require(
                        compile_pattern(
                            schema["evidence_ref_pattern"], "derivation.evidence_ref_pattern"
                        ).fullmatch(ref)
                        is not None,
                        "invalid condition evidence reference",
                    )
                    require(
                        ref in provenance_refs,
                        f"edge {edge['id']}: dangling condition evidence reference",
                    )
        else:
            require(
                "conditions" not in path,
                f"edge {edge['id']}: proof conditions are only valid for CanRDP",
            )
        steps = path["steps"]
        require(
            isinstance(steps, list) and bool(steps),
            f"edge {edge['id']}: derivation path {path_index} has no steps",
        )
        operations = tuple(
            step.get("operation") if isinstance(step, dict) else None for step in steps
        )
        gpo_operations = tuple(schema["gpo_operations"])
        if derivation["kind"] == "nested_membership":
            require(
                _valid_nested_host_access_sequence(edge["kind"], operations),
                f"edge {edge['id']}: invalid nested-membership derivation sequence",
            )
        elif derivation["kind"] == "gpo_resultant":
            require(
                operations == gpo_operations,
                f"edge {edge['id']}: invalid GPO operation sequence",
            )
        else:
            require(
                _valid_nested_host_access_sequence(edge["kind"], operations)
                or operations == gpo_operations,
                f"edge {edge['id']}: invalid host-access derivation sequence",
            )
        expected_order = list(range(len(steps)))
        actual_order = [step.get("order") if isinstance(step, dict) else None for step in steps]
        require(
            actual_order == expected_order,
            f"edge {edge['id']}: derivation path {path_index} has non-contiguous order",
        )
        for step_index, step in enumerate(steps):
            require(isinstance(step, dict), f"edge {edge['id']}: malformed derivation step")
            allowed = set(schema["step_required"]) | set(schema["step_optional"])
            require(
                set(step) <= allowed and set(schema["step_required"]) <= set(step),
                f"edge {edge['id']}: malformed derivation step {step_index}",
            )
            require(
                step["operation"] in schema["operations"],
                f"edge {edge['id']}: invalid derivation operation",
            )
            refs = step["evidence_refs"]
            require(
                isinstance(refs, list) and bool(refs) and refs == sorted(set(refs)),
                f"edge {edge['id']}: invalid derivation evidence_refs",
            )
            ref_pattern = compile_pattern(
                schema["evidence_ref_pattern"], "derivation.evidence_ref_pattern"
            )
            for ref in refs:
                require(
                    ref_pattern.fullmatch(ref) is not None, "invalid derivation evidence reference"
                )
                require(
                    ref in provenance_refs,
                    f"edge {edge['id']}: dangling derivation evidence reference",
                )
            for endpoint in ("source", "target"):
                if endpoint in step:
                    if step[endpoint] not in node_ids:
                        require(
                            endpoint == "target"
                            and step["operation"] == "effective_right"
                            and step[endpoint] in schema["non_node_targets"],
                            f"edge {edge['id']}: derivation {endpoint} is not a graph node",
                        )
        if operations == gpo_operations:
            terminal = steps[-1]
            require(
                {"source", "target"} <= set(terminal)
                and terminal["source"] == edge["source"]
                and terminal["target"] == edge["target"],
                f"edge {edge['id']}: GPO resultant state must bind to the edge endpoints",
            )
            require(
                node_kinds.get(terminal["source"]) in {"User", "Group", "Computer"}
                and node_kinds.get(terminal["target"]) == "Computer",
                f"edge {edge['id']}: GPO resultant state has invalid endpoint node kinds",
            )
        else:
            _validate_nested_host_access_endpoints(steps, edge, node_kinds)
        path_keys.append(
            json.dumps(path, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        )
    require(len(path_keys) == len(set(path_keys)), f"edge {edge['id']}: duplicate derivation path")
    require(
        path_keys == sorted(path_keys), f"edge {edge['id']}: derivation paths are not canonicalized"
    )


def validate_edge(
    edge: dict,
    contract: dict,
    expected_weight: float | None = None,
    *,
    node_ids: set[str] | None = None,
    node_kinds: dict[str, str] | None = None,
    contract_version: str | None = None,
) -> None:
    schema = contract["schema"]
    is_legacy = contract_version == "1.0.0"
    allowed_fields = set(schema["edge_required"]) | (
        set() if is_legacy else set(schema["edge_optional"])
    )
    unknown_fields = set(edge) - allowed_fields
    require(not unknown_fields, f"edges: unsupported fields {sorted(unknown_fields)}")
    for field in schema["edge_required"]:
        require(field in edge, f"edges: missing required field {field}")
    for field in ("id", "source", "target", "kind"):
        require(nonempty_string(edge[field]), f"edges: invalid {field}")
    require(edge["kind"] in contract["edge_kinds"], "edges: unknown kind")
    if edge["kind"] in set(schema["derivation"]["derived_edge_kinds"]):
        principal_kinds = {"User", "Group", "Computer"}
        kinds = node_kinds or {}
        require(
            kinds.get(edge["source"]) in principal_kinds,
            f"edge {edge['id']}: host-access edge source must be a principal",
        )
        require(
            kinds.get(edge["target"]) == "Computer",
            f"edge {edge['id']}: host-access edge target must be a Computer",
        )
    require(
        type(edge["weight"]) in (int, float)
        and not isinstance(edge["weight"], bool)
        and math.isfinite(edge["weight"])
        and edge["weight"] >= 1.0,
        f"edge {edge['id']}: weight must be finite and >= 1.0",
    )
    if expected_weight is not None:
        require(
            edge["weight"] == expected_weight,
            f"edge {edge['id']}: weight does not match the selected profile",
        )
    edge_id_pattern = compile_pattern(schema["edge_id"]["pattern"], "edge_id.pattern")
    require(edge_id_pattern.fullmatch(edge["id"]) is not None, "edges: invalid canonical edge id")
    expected_id = canonical_edge_id(edge["source"], edge["target"], edge["kind"])
    require(edge["id"] == expected_id, f"edge {edge['id']}: ID does not match source/target/kind")
    validate_provenance(
        edge["provenance"],
        contract,
        f"edge {edge['id']}",
        allowed_evidence_types={schema["provenance"]["edge_evidence_type"]},
        contract_version=contract_version,
    )
    if "derivation" in edge:
        require(not is_legacy, "legacy contract graphs cannot contain derivation")
        validate_derivation(edge["derivation"], edge, contract, node_ids or set(), node_kinds or {})


def validate_assessment(
    assessment: dict, contract: dict, *, contract_version: str | None = None
) -> None:
    schema = contract["schema"]
    allowed_fields = set(schema["assessment_required"]) | set(schema["assessment_optional"])
    unknown_fields = set(assessment) - allowed_fields
    ident = assessment.get("id") or "<unknown>"
    require(
        not unknown_fields, f"assessment '{ident}': unsupported fields {sorted(unknown_fields)}"
    )
    for field in schema["assessment_required"]:
        require(field in assessment, f"assessment '{ident}': missing required field {field}")
    field_types = schema["assessment_field_types"]
    for field, value in assessment.items():
        if field == "provenance":
            continue
        if field_types[field] == "assessment_status":
            require(value in ASSESSMENT_STATUSES, f"assessment '{ident}': invalid status")
        else:
            _validate_field_type(
                value,
                field_types[field],
                field,
                contract=contract,
                node_ident=f"assessment '{ident}'",
                contract_version=contract_version,
            )
    validate_provenance(
        assessment["provenance"],
        contract,
        f"assessment {ident}",
        allowed_evidence_types={assessment["status"]},
        contract_version=contract_version,
    )


def _validate_string_list(value: object, name: str, expected: set[str] | None = None) -> None:
    require(isinstance(value, list), f"{name} must be a list")
    require(all(nonempty_string(item) for item in value), f"invalid {name}")
    require(len(value) == len(set(value)), f"duplicate {name}")
    if expected is not None:
        require(set(value) == expected, f"{name} must match the M2 contract")


def validate_contract(contract: dict) -> None:
    require(isinstance(contract, dict), "contract must be a mapping")
    require(nonempty_string(contract.get("version")), "contract version is required")
    require(
        contract.get("version") == CURRENT_CONTRACT_VERSION, "unexpected current contract version"
    )
    require(contract.get("status") == "accepted", "M2 contract must be accepted")
    compatibility = contract.get("compatibility")
    require(isinstance(compatibility, dict), "compatibility settings must be a mapping")
    _validate_string_list(compatibility.get("previous_versions"), "compatibility.previous_versions")
    require(
        set(compatibility["previous_versions"]) == SUPPORTED_PREVIOUS_CONTRACT_VERSIONS,
        "compatibility.previous_versions must list every supported predecessor",
    )
    require(nonempty_string(compatibility.get("migration")), "compatibility.migration is required")
    graph = contract.get("graph", {})
    require(isinstance(graph, dict), "graph settings must be a mapping")
    require(graph.get("directed") is True, "graph must be directed")
    require(graph.get("multigraph") is True, "parallel edges must be preserved")
    _validate_string_list(
        graph.get("top_level_required"),
        "graph.top_level_required",
        {"metadata", "nodes", "edges", "assessments"},
    )
    _validate_string_list(graph.get("top_level_optional"), "graph.top_level_optional")
    _validate_string_list(contract.get("node_kinds"), "node_kinds", EXPECTED_NODE_KINDS)
    _validate_string_list(contract.get("edge_kinds"), "edge_kinds", EXPECTED_EDGE_KINDS)

    schema = contract.get("schema", {})
    require(isinstance(schema, dict), "schema must be a mapping")
    for key, minimum in {
        "node_required": CORE_NODE_FIELDS,
        "edge_required": CORE_EDGE_FIELDS,
        "assessment_required": {"id", "status", "reason", "provenance"},
    }.items():
        fields = schema.get(key)
        _validate_string_list(fields, key)
        require(minimum <= set(fields), f"{key} is missing core fields")
    _validate_string_list(schema.get("node_optional"), "node_optional")
    _validate_string_list(schema.get("edge_optional"), "edge_optional")
    _validate_string_list(schema.get("assessment_optional"), "assessment_optional")
    require(
        not (set(schema["node_required"]) & set(schema["node_optional"])),
        "node fields cannot be both required and optional",
    )
    require(
        not (set(schema["assessment_required"]) & set(schema["assessment_optional"])),
        "assessment fields cannot be both required and optional",
    )
    require(
        set(schema["node_required"]) == REQUIRED_NODE_FIELDS,
        "node_required must contain exactly id, kind, label, domain, and is_boundary",
    )
    require(
        set(schema["edge_required"]) == CORE_EDGE_FIELDS,
        "edge_required must contain exactly id, source, target, kind, weight, and provenance",
    )
    require(schema["edge_optional"] == ["derivation"], "edge_optional must declare derivation")
    _validate_string_list(
        schema.get("assessment_statuses"), "assessment_statuses", ASSESSMENT_STATUSES
    )

    metadata = schema.get("metadata")
    require(isinstance(metadata, dict), "metadata schema must be a mapping")
    _validate_string_list(
        metadata.get("required"),
        "metadata.required",
        {"contract_version", "weight_profile", "snapshot_id", "created_at", "code_version"},
    )
    _validate_string_list(metadata.get("optional"), "metadata.optional")
    require(
        not (set(metadata["required"]) & set(metadata["optional"])),
        "metadata fields cannot be both required and optional",
    )
    require(
        set(metadata.get("field_types", {}))
        == set(metadata["required"]) | set(metadata["optional"]),
        "metadata.field_types must cover exactly the declared fields",
    )
    require(
        metadata["field_types"]["weight_profile"] == "weight_profile",
        "metadata.weight_profile must have type weight_profile",
    )
    require(
        metadata["field_types"]["snapshot_id"] == "snapshot_id",
        "metadata.snapshot_id must have type snapshot_id",
    )
    require(
        metadata["field_types"]["created_at"] == "utc_timestamp",
        "metadata.created_at must have type utc_timestamp",
    )
    compile_pattern(metadata.get("snapshot_id_pattern"), "metadata.snapshot_id_pattern")
    compile_pattern(metadata.get("timestamp_pattern"), "metadata.timestamp_pattern")

    canonical_id = schema.get("canonical_id")
    require(isinstance(canonical_id, dict), "canonical_id must be a mapping")
    require(
        canonical_id.get("strategy") == "sid_then_scoped_sid_then_guid",
        "invalid canonical ID strategy",
    )
    require(nonempty_string(canonical_id.get("description")), "canonical_id description required")
    _validate_string_list(
        canonical_id.get("scope_kinds"), "canonical_id.scope_kinds", {"domain", "host"}
    )
    canonical_id_patterns(contract)
    field_types = schema.get("node_field_types")
    require(isinstance(field_types, dict), "node_field_types must be a mapping")
    declared_node_fields = set(schema["node_required"]) | set(schema["node_optional"])
    require(
        set(field_types) == declared_node_fields,
        "node_field_types must cover exactly the declared node fields",
    )
    for field, expected_type in CORE_NODE_FIELD_TYPES.items():
        require(
            field_types.get(field) == expected_type,
            f"core node field '{field}' must have type '{expected_type}'",
        )
    for field, field_type in field_types.items():
        require(
            nonempty_string(field_type) and field_type in SUPPORTED_NODE_FIELD_TYPES,
            f"node field '{field}' has unsupported type '{field_type}'",
        )

    edge_id = schema.get("edge_id")
    require(isinstance(edge_id, dict), "edge_id must be a mapping")
    require(edge_id.get("strategy") == "sha256_json_array", "invalid canonical edge ID strategy")
    require(edge_id.get("inputs") == ["source", "target", "kind"], "invalid edge ID inputs")
    require(nonempty_string(edge_id.get("description")), "edge_id description required")
    compile_pattern(edge_id.get("pattern"), "edge_id.pattern")
    require(
        schema.get("edge_field_types") == EXPECTED_EDGE_FIELD_TYPES,
        "edge_field_types contains an invalid edge field type",
    )

    derivation = schema.get("derivation")
    require(isinstance(derivation, dict), "derivation schema must be a mapping")
    require(derivation.get("version") == "1.1.0", "invalid derivation schema version")
    _validate_string_list(
        derivation.get("kinds"),
        "derivation.kinds",
        {"nested_membership", "gpo_resultant", "host_access"},
    )
    _validate_string_list(
        derivation.get("derived_edge_kinds"),
        "derivation.derived_edge_kinds",
        {"AdminTo", "CanRDP", "CanPSRemote"},
    )
    _validate_string_list(
        derivation.get("direct_only_edge_kinds"),
        "derivation.direct_only_edge_kinds",
        {"MemberOf", "GenericAll", "WriteDacl", "ForceChangePassword", "HasSession"},
    )
    require(
        set(derivation["derived_edge_kinds"]) | set(derivation["direct_only_edge_kinds"])
        == set(contract["edge_kinds"]),
        "derivation edge-kind policy must cover exactly all edge kinds",
    )
    require(
        not set(derivation["derived_edge_kinds"]) & set(derivation["direct_only_edge_kinds"]),
        "derivation edge-kind policy cannot overlap",
    )
    require(
        derivation.get("multiple_paths") == "preserve_all_sorted_deduplicated",
        "invalid derivation multiple-path policy",
    )
    _validate_string_list(derivation.get("path_required"), "derivation.path_required", {"steps"})
    _validate_string_list(
        derivation.get("path_optional"), "derivation.path_optional", {"conditions"}
    )
    _validate_string_list(
        derivation.get("condition_required"),
        "derivation.condition_required",
        {"predicate", "evidence_refs"},
    )
    _validate_string_list(
        derivation.get("condition_predicates"),
        "derivation.condition_predicates",
        {"rdu_membership", "allow_right", "deny_absent"},
    )
    require(
        derivation.get("required_conditions")
        == {"CanRDP": ["rdu_membership", "allow_right", "deny_absent"]},
        "derivation.required_conditions must require every CanRDP component",
    )
    _validate_string_list(
        derivation.get("step_required"),
        "derivation.step_required",
        {"order", "operation", "evidence_refs"},
    )
    _validate_string_list(
        derivation.get("step_optional"), "derivation.step_optional", {"source", "target"}
    )
    _validate_string_list(
        derivation.get("operations"),
        "derivation.operations",
        {
            "effective_membership",
            "host_local_membership",
            "effective_right",
            "gpo_setting",
            "active_link",
            "target_scope",
            "security_filtering",
            "wmi_filtering",
            "inheritance_and_order",
            "client_side_extension",
            "resultant_host_state",
        },
    )
    _validate_string_list(
        derivation.get("nested_operations"),
        "derivation.nested_operations",
        {"effective_membership", "host_local_membership", "effective_right"},
    )
    require(
        derivation.get("nested_sequence_rules")
        == {
            "AdminTo": "membership_chain_then_host_local",
            "CanRDP": "complete_path_plus_rdu_allow_and_deny_absence_conditions",
            "CanPSRemote": "membership_chain_then_host_local",
        },
        "derivation.nested_sequence_rules must declare edge-specific causal ordering",
    )
    _validate_string_list(
        derivation.get("gpo_operations"),
        "derivation.gpo_operations",
        {
            "gpo_setting",
            "active_link",
            "target_scope",
            "security_filtering",
            "wmi_filtering",
            "inheritance_and_order",
            "client_side_extension",
            "resultant_host_state",
        },
    )
    require(
        derivation["gpo_operations"]
        == [
            "gpo_setting",
            "active_link",
            "target_scope",
            "security_filtering",
            "wmi_filtering",
            "inheritance_and_order",
            "client_side_extension",
            "resultant_host_state",
        ],
        "derivation.gpo_operations must remain ordered",
    )
    _validate_string_list(
        derivation.get("non_node_targets"),
        "derivation.non_node_targets",
        {"SeRemoteInteractiveLogonRight", "SeDenyRemoteInteractiveLogonRight"},
    )
    compile_pattern(derivation.get("evidence_ref_pattern"), "derivation.evidence_ref_pattern")

    provenance = schema.get("provenance")
    require(isinstance(provenance, dict), "provenance must be a mapping")
    _validate_string_list(
        provenance.get("required"), "provenance.required", PROVENANCE_REQUIRED_FIELDS
    )
    _validate_string_list(
        provenance.get("optional"), "provenance.optional", PROVENANCE_OPTIONAL_FIELDS
    )
    require(
        not (set(provenance["required"]) & set(provenance["optional"])),
        "provenance fields cannot be both required and optional",
    )
    _validate_string_list(
        provenance.get("evidence_types"),
        "provenance.evidence_types",
        {"positive", "unknown", "inferred", "rejected"},
    )
    require(
        provenance.get("edge_evidence_type") == "positive",
        "traversable edges require positive evidence",
    )
    compile_pattern(provenance.get("timestamp_pattern"), "provenance.timestamp_pattern")
    _validate_string_list(
        provenance.get("timestamp_statuses"),
        "provenance.timestamp_statuses",
        {"observed", "assumed", "derived", "externally_evidenced", "unknown_legacy"},
    )
    _validate_string_list(
        provenance.get("reason_required_statuses"),
        "provenance.reason_required_statuses",
        {"derived", "externally_evidenced"},
    )

    assessment_types = schema.get("assessment_field_types")
    require(isinstance(assessment_types, dict), "assessment_field_types must be a mapping")
    require(
        set(assessment_types)
        == set(schema["assessment_required"]) | set(schema["assessment_optional"]),
        "assessment_field_types must cover exactly the declared fields",
    )
    require(
        assessment_types["status"] == "assessment_status",
        "assessment.status must have type assessment_status",
    )

    boundary = schema.get("boundary")
    require(isinstance(boundary, dict), "boundary schema must be a mapping")
    _validate_string_list(
        boundary.get("allowed_kinds"),
        "boundary.allowed_kinds",
        {"Domain", "User", "Group", "Computer"},
    )
    _validate_string_list(
        boundary.get("required_fields"),
        "boundary.required_fields",
        {"domain", "is_boundary"},
    )
    require(nonempty_string(boundary.get("description")), "boundary description required")

    raw_provenance = schema.get("raw_provenance")
    require(isinstance(raw_provenance, dict), "raw_provenance schema must be a mapping")
    _validate_string_list(
        raw_provenance.get("required"),
        "raw_provenance.required",
        {"raw_file", "collector", "timestamp"},
    )
    _validate_string_list(
        raw_provenance.get("optional"),
        "raw_provenance.optional",
        RAW_PROVENANCE_OPTIONAL_FIELDS,
    )
    require(
        not (set(raw_provenance["required"]) & set(raw_provenance["optional"])),
        "raw_provenance fields cannot be both required and optional",
    )
    compile_pattern(raw_provenance.get("timestamp_pattern"), "raw_provenance.timestamp_pattern")

    profiles = contract.get("profiles")
    require(isinstance(profiles, dict) and bool(profiles), "profiles must be a nonempty mapping")
    require(contract.get("default_profile") in profiles, "default profile does not exist")
    for name, profile in profiles.items():
        require(nonempty_string(name), "profile name must be a nonempty string")
        require(isinstance(profile, dict), f"{name}: profile must be a mapping")
        require(nonempty_string(profile.get("description")), f"{name}: description is required")
        require(type(profile.get("production_ready")) is bool, f"{name}: readiness must be boolean")
        require(
            not profile["production_ready"],
            f"{name}: profile is not production ready without empirical validation",
        )
        weights = profile.get("weights")
        require(isinstance(weights, dict), f"{name}: weights must be a mapping")
        require(set(weights) == set(contract["edge_kinds"]), f"{name}: incomplete/unknown weights")
        for kind, value in weights.items():
            require(
                type(value) in (int, float)
                and not isinstance(value, bool)
                and math.isfinite(value)
                and value >= 1.0,
                f"{name}/{kind}: weight must be finite and >= 1.0",
            )


def validate_metadata(metadata: object, contract: dict) -> None:
    schema = contract["schema"]["metadata"]
    require(isinstance(metadata, dict), "metadata must be a mapping")
    allowed_fields = set(schema["required"]) | set(schema["optional"])
    unknown_fields = set(metadata) - allowed_fields
    require(not unknown_fields, f"metadata: unsupported fields {sorted(unknown_fields)}")
    for field in schema["required"]:
        require(field in metadata, f"metadata: missing required field {field}")
    types = schema["field_types"]
    for field, value in metadata.items():
        field_type = types[field]
        if field_type == "weight_profile":
            require(value in contract["profiles"], "metadata: unknown weight_profile")
        elif field_type == "snapshot_id":
            pattern = compile_pattern(schema["snapshot_id_pattern"], "metadata.snapshot_id_pattern")
            require(
                isinstance(value, str) and pattern.fullmatch(value), "metadata: invalid snapshot_id"
            )
        elif field_type == "utc_timestamp":
            pattern = compile_pattern(schema["timestamp_pattern"], "metadata.timestamp_pattern")
            _validate_timestamp(value, pattern, "metadata.created_at")
        elif field_type == "boolean":
            require(type(value) is bool, f"metadata: {field} must be boolean")
        else:
            require(nonempty_string(value), f"metadata: invalid {field}")
    supported = {
        contract["version"],
        *contract.get("compatibility", {}).get("previous_versions", []),
    }
    require(metadata["contract_version"] in supported, "contract version mismatch")


def validate_graph(graph: dict, contract: dict) -> None:
    validate_contract(contract)
    require(isinstance(graph, dict), "fixture must be a mapping")
    required_top_level = set(contract["graph"]["top_level_required"])
    require(required_top_level <= set(graph), "graph is missing required top-level fields")
    require(not (set(graph) - required_top_level), "graph has unsupported top-level fields")
    validate_metadata(graph["metadata"], contract)
    node_ids: set[str] = set()
    node_kinds: dict[str, str] = {}
    nodes = graph["nodes"]
    require(isinstance(nodes, list), "nodes must be a list")
    for node in nodes:
        require(isinstance(node, dict), "nodes: record must be a mapping")
        validate_node(node, contract, contract_version=graph["metadata"]["contract_version"])
        require(node["id"] not in node_ids, f"nodes: duplicate id {node['id']}")
        node_ids.add(node["id"])
        node_kinds[node["id"]] = node["kind"]

    expected_weights = contract["profiles"][graph["metadata"]["weight_profile"]]["weights"]
    edges = graph["edges"]
    require(isinstance(edges, list), "edges must be a list")
    edge_ids: set[str] = set()
    for edge in edges:
        require(isinstance(edge, dict), "edges: record must be a mapping")
        validate_edge(
            edge,
            contract,
            expected_weight=expected_weights.get(edge.get("kind")),
            node_ids=node_ids,
            node_kinds=node_kinds,
            contract_version=graph["metadata"]["contract_version"],
        )
        require(edge["id"] not in edge_ids, f"edges: duplicate id {edge['id']}")
        edge_ids.add(edge["id"])
        require(
            edge["source"] in node_ids and edge["target"] in node_ids,
            f"edge {edge['id']}: dangling endpoint",
        )

    assessments = graph["assessments"]
    require(isinstance(assessments, list), "assessments must be a list")
    assessment_ids: set[str] = set()
    for assessment in assessments:
        require(isinstance(assessment, dict), "assessments: record must be a mapping")
        validate_assessment(
            assessment,
            contract,
            contract_version=graph["metadata"]["contract_version"],
        )
        require(
            assessment["id"] not in assessment_ids, f"assessments: duplicate id {assessment['id']}"
        )
        assessment_ids.add(assessment["id"])
        for endpoint in ("subject", "target"):
            if endpoint in assessment:
                require(
                    assessment[endpoint] in node_ids,
                    f"assessment {assessment['id']}: dangling {endpoint}",
                )


@functools.lru_cache(maxsize=32)
def _parse_and_validate_contract_bytes(raw_bytes: bytes) -> dict[str, Any]:
    try:
        data = yaml.safe_load(raw_bytes.decode("utf-8"))
    except (UnicodeError, yaml.YAMLError) as exc:
        raise ValueError(f"unable to parse graph contract: {exc}") from exc
    require(isinstance(data, dict), "graph contract must be a mapping")
    try:
        validate_contract(data)
    except (KeyError, TypeError, IndexError, ValueError) as exc:
        raise ValueError(f"graph contract is malformed: {exc}") from exc
    require(
        data.get("version") == CURRENT_CONTRACT_VERSION,
        f"official parser CLI requires Graph Contract {CURRENT_CONTRACT_VERSION}",
    )
    return data


def load_contract(path: Path | str | None = None) -> dict[str, Any]:
    """Load and validate the canonical graph contract, caching validated bytes."""
    target_path = Path(
        path if path is not None and str(path) != "" else ROOT / "configs/contract.yml"
    )
    try:
        raw_bytes = target_path.read_bytes()
    except OSError as exc:
        raise ValueError(f"unable to load graph contract: {target_path}") from exc
    try:
        cached = _parse_and_validate_contract_bytes(raw_bytes)
    except ValueError as exc:
        if "unable to parse graph contract" in str(exc):
            raise ValueError(f"unable to load graph contract: {target_path}") from exc
        raise
    return copy.deepcopy(cached)


def main() -> int:
    try:
        contract = load_contract()
        fixtures = sorted((ROOT / "data/samples").glob("*.json"))
        require(bool(fixtures), "at least one synthetic fixture is required")
        for path in fixtures:
            graph = json.loads(path.read_text(encoding="utf-8"))
            validate_graph(graph, contract)
            require(
                graph["metadata"].get("synthetic") is True, f"{path.name}: not marked synthetic"
            )
        print(f"Contract and {len(fixtures)} synthetic fixture(s) validated.")
        return 0
    except (ValueError, OSError, yaml.YAMLError) as exc:
        print(f"Contract validation failed: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
