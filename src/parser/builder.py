"""Structural graph assembly for normalized collector records.

This module owns node-first, edge-second assembly for direct relationships and
integrates the evidence-backed host-access inference layer. Ordered derived
lineage is serialized through the versioned Graph Contract lineage field.
"""

from __future__ import annotations

import copy
import hashlib
import json
import logging
import re
from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, replace
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from scripts.check_contract import load_contract, validate_graph, validate_node

from . import (
    Assessment,
    AssessmentStatus,
    CanonicalDerivationStep,
    DerivationCondition,
    DerivationPath,
    DerivedLineage,
    ErrorPolicy,
    Graph,
    GraphBuilder,
    GraphEdge,
    GraphNode,
    NormalizedRecord,
    Provenance,
    RecordError,
    process_records,
)
from .identity_fields import lookup_raw_identifier
from .inference import (
    EvidenceSource,
    HostAccessResult,
    InferenceStatus,
    evaluate_host_access,
    extract_primary_group_entry,
)
from .lineage import LINEAGE_VERSION, path_key, provenance_ref, sorted_unique_paths
from .well_known_principals import boundary_group

if TYPE_CHECKING:
    from .snapshot_facts import SnapshotFacts

_LOGGER = logging.getLogger(__name__)
_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_CONTRACT_PATH = _ROOT / "configs" / "contract.yml"
_PRINCIPAL_KINDS = frozenset({"User", "Group", "Computer"})
_NODE_KINDS = frozenset({"User", "Group", "Computer", "Domain", "OU", "GPO"})
_REFERENCE_KEYS = (
    "MemberId",
    "member_id",
    "PrincipalSID",
    "principal_sid",
    "UserId",
    "UserSID",
    "UserSid",
    "user_id",
    "user_sid",
)
_REFERENCE_KIND_KEYS = ("MemberType", "member_type", "PrincipalType", "principal_type")
_SESSION_FIELDS = ("Sessions", "PrivilegedSessions", "RegistrySessions")
_MANIFEST_SNAPSHOT_DIGEST = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True)
class _EdgeCandidate:
    """One direct evidence item before endpoint resolution."""

    kind: str
    source_ref: str
    target_ref: str
    source_kind: str | None
    target_kind: str | None
    field: str
    item: object
    record_id: str | None


@dataclass(frozen=True)
class _PreparedRecord:
    """A completely validated record ready for the second assembly pass."""

    record: NormalizedRecord
    node: GraphNode
    candidates: tuple[_EdgeCandidate, ...]


def canonical_edge_id(source: str, target: str, kind: str) -> str:
    """Return the contract-defined ID for one logical edge."""

    payload = json.dumps([source, target, kind], ensure_ascii=True, separators=(",", ":"))
    return f"sha256:{hashlib.sha256(payload.encode('utf-8')).hexdigest()}"


def _canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _kind(value: object, *, required: bool = False) -> str | None:
    if value is None:
        if required:
            raise ValueError("relationship reference kind is required")
        return None
    if not isinstance(value, str) or not value.strip():
        raise ValueError("relationship reference kind must be a non-empty string")
    aliases = {
        "user": "User",
        "users": "User",
        "group": "Group",
        "groups": "Group",
        "computer": "Computer",
        "computers": "Computer",
        "host": "Computer",
        "hosts": "Computer",
        "domain": "Domain",
        "domains": "Domain",
        "ou": "OU",
        "ous": "OU",
        "gpo": "GPO",
        "gpos": "GPO",
    }
    try:
        result = aliases[value.strip().casefold()]
    except KeyError as exc:
        raise ValueError(f"unsupported relationship reference kind {value!r}") from exc
    if result not in _NODE_KINDS:
        raise ValueError(f"unsupported relationship reference kind {value!r}")
    return result


def _string_reference(value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("relationship reference must be a non-empty string")
    return value.strip()


def _reference_from_item(item: object, *, field: str) -> tuple[str, str | None, str]:
    if isinstance(item, str):
        return _string_reference(item), None, field
    if not isinstance(item, Mapping):
        raise ValueError(f"{field} evidence item must be an object or identifier string")

    reference: object = None
    selected_key: str | None = None
    for key in _REFERENCE_KEYS:
        value = item.get(key)
        if value is not None:
            reference = value
            selected_key = key
            break
    if reference is None:
        # Some collector records use the common object-identifier aliases.
        reference = lookup_raw_identifier(cast(Mapping[str, Any], item))
        selected_key = "ObjectIdentifier"
    if reference is None:
        raise ValueError(f"{field} evidence item has no stable reference")

    kind_value: object = None
    for key in _REFERENCE_KIND_KEYS:
        if item.get(key) is not None:
            kind_value = item[key]
            break
    return (
        _string_reference(reference),
        _kind(kind_value),
        f"{field}[].{selected_key}" if selected_key else field,
    )


def _items(data: Mapping[str, object], field: str) -> list[object]:
    """Read list and historical ``{"Results": [...]}`` collector shapes."""

    if field not in data or data[field] is None:
        return []
    value = data[field]
    if isinstance(value, list):
        return list(value)
    if isinstance(value, Mapping) and isinstance(value.get("Results"), list):
        return list(value["Results"])
    raise ValueError(f"{field} must be a list or a Results container")


def _record_identifier(record: NormalizedRecord) -> str | None:
    value = record.raw.provenance.get("record_id")
    if isinstance(value, str) and value.strip():
        return value.strip()
    return record.id


def _node(record: NormalizedRecord) -> GraphNode:
    if not isinstance(record, NormalizedRecord):
        raise TypeError("builder input must contain NormalizedRecord values")
    if record.kind not in _NODE_KINDS:
        raise ValueError(f"unsupported normalized node kind {record.kind!r}")
    if not isinstance(record.attributes, Mapping):
        raise ValueError("normalized node attributes must be a mapping")

    attributes = record.attributes
    if attributes.get("id") not in (None, record.id):
        raise ValueError("normalized node attribute ID does not match record ID")
    if attributes.get("kind") not in (None, record.kind):
        raise ValueError("normalized node attribute kind does not match record kind")

    required = ("label", "domain", "is_boundary")
    if any(field not in attributes for field in required):
        missing = next(field for field in required if field not in attributes)
        raise ValueError(f"normalized node is missing {missing}")

    result: dict[str, object] = {
        "id": record.id,
        "kind": record.kind,
        "label": attributes["label"],
        "domain": attributes["domain"],
        "is_boundary": attributes["is_boundary"],
    }
    for field in ("enabled", "admincount", "distinguishedname"):
        if field in attributes:
            result[field] = attributes[field]
    return cast(GraphNode, result)


def _candidate_error(record: NormalizedRecord, message: str) -> RecordError:
    return RecordError(message, stage="build", record_id=_record_identifier(record))


def _validate_record_time_provenance(record: NormalizedRecord) -> None:
    sources = list(record.raw_provenance) or [record.raw.provenance]
    sources.extend(source for line in record.evidence_lineage for source in line.provenance)
    for source in sources:
        time_provenance = source.get("time_provenance")
        if time_provenance is not None and time_provenance not in {
            "observed",
            "assumed",
            "derived",
            "externally_evidenced",
        }:
            raise ValueError(f"unsupported time provenance status: {time_provenance!r}")
        if time_provenance in {"derived", "externally_evidenced"} and not (
            isinstance(source.get("time_provenance_reason"), str)
            and str(source["time_provenance_reason"]).strip()
        ):
            raise ValueError(f"time provenance status {time_provenance!r} requires an audit reason")


def _prepare(record: NormalizedRecord, contract: Mapping[str, object]) -> _PreparedRecord:
    try:
        node = _node(record)
        validate_node(cast(dict, node), cast(dict, contract))
        _validate_record_time_provenance(record)
        data = record.raw.data
        if not isinstance(data, Mapping):
            raise ValueError("raw relationship data must be a mapping")

        candidates: list[_EdgeCandidate] = []
        record_id = _record_identifier(record)

        if "Members" in data:
            if record.kind != "Group":
                raise ValueError("Members evidence is only valid on Group records")
            for item in _items(data, "Members"):
                reference, member_kind, field = _reference_from_item(item, field="Members")
                if member_kind is not None and member_kind not in _PRINCIPAL_KINDS:
                    raise ValueError("MemberOf source must be a User, Group, or Computer")
                candidates.append(
                    _EdgeCandidate(
                        "MemberOf",
                        reference,
                        record.id,
                        member_kind,
                        "Group",
                        field,
                        item,
                        record_id,
                    )
                )

        primary_group_entry = extract_primary_group_entry(data, record_kind=record.kind)
        if primary_group_entry is not None:
            field, ref = primary_group_entry
            candidates.append(
                _EdgeCandidate(
                    "MemberOf",
                    record.id,
                    ref,
                    record.kind,
                    "Group",
                    field,
                    ref,
                    record_id,
                )
            )

        if "Aces" in data:
            for item in _items(data, "Aces"):
                if not isinstance(item, Mapping):
                    raise ValueError("Aces evidence item must be an object")
                right = item.get("RightName")
                if not isinstance(right, str):
                    raise ValueError("Aces evidence item has no RightName")
                kind = {
                    "genericall": "GenericAll",
                    "writedacl": "WriteDacl",
                    "forcechangepassword": "ForceChangePassword",
                }.get(right.strip().casefold())
                if kind is None:
                    continue
                reference, principal_kind, field = _reference_from_item(item, field="Aces")
                if principal_kind is not None and principal_kind not in _PRINCIPAL_KINDS:
                    raise ValueError(f"{kind} source must be a User, Group, or Computer")
                target_kind = "User" if kind == "ForceChangePassword" else None
                candidates.append(
                    _EdgeCandidate(
                        kind,
                        reference,
                        record.id,
                        principal_kind,
                        target_kind,
                        field,
                        item,
                        record_id,
                    )
                )

        session_fields = [field for field in _SESSION_FIELDS if field in data]
        if session_fields and record.kind != "Computer":
            raise ValueError("session evidence is only valid on Computer records")
        for session_field in session_fields:
            for item in _items(data, session_field):
                reference, session_kind, field = _reference_from_item(item, field=session_field)
                if session_kind is not None and session_kind != "User":
                    raise ValueError("HasSession target must be a User")
                candidates.append(
                    _EdgeCandidate(
                        "HasSession",
                        record.id,
                        reference,
                        "Computer",
                        "User",
                        field,
                        item,
                        record_id,
                    )
                )
    except RecordError:
        raise
    except (TypeError, ValueError) as exc:
        raise _candidate_error(record, str(exc)) from exc

    return _PreparedRecord(record=record, node=node, candidates=tuple(candidates))


def _alias_values(record: NormalizedRecord) -> set[str]:
    aliases = {record.id}
    raw_identifier = lookup_raw_identifier(record.raw.data)
    if isinstance(raw_identifier, str) and raw_identifier.strip():
        aliases.add(raw_identifier.strip())
    for container_name in ("Properties", "properties", "Attributes", "attributes"):
        container = record.raw.data.get(container_name)
        if isinstance(container, Mapping):
            identifier = lookup_raw_identifier(cast(Mapping[str, Any], container))
            if isinstance(identifier, str) and identifier.strip():
                aliases.add(identifier.strip())
    return aliases


def _resolve(
    reference: str,
    expected_kind: str | None,
    aliases: Mapping[str, set[str]],
    nodes: Mapping[str, GraphNode],
    pending: dict[str, GraphNode],
    *,
    boundary_member_source: bool = False,
) -> str:
    all_matches = set(aliases.get(reference.casefold(), set()))
    known = boundary_group(reference)
    if not all_matches and known is not None:
        all_matches = set(aliases.get(known[0].casefold(), set()))
    matches = set(all_matches)
    if expected_kind is not None:
        matches = {node_id for node_id in matches if nodes[node_id]["kind"] == expected_kind}
    if all_matches and not matches:
        raise ValueError(f"reference {reference!r} conflicts with collected node kind")
    if len(matches) != 1:
        if not matches:
            if known is None:
                raise ValueError(f"unresolvable {expected_kind or 'node'} reference {reference!r}")
            sid, label = known
            if expected_kind != "Group":
                raise ValueError(f"well-known principal {sid} conflicts with reference kind")
            if sid == "S-1-5-17" and not boundary_member_source:
                raise ValueError(
                    "IUSR boundary Group is supported only as a Group membership source"
                )
            pending.setdefault(
                sid,
                cast(
                    GraphNode,
                    {
                        "id": sid,
                        "kind": "Group",
                        "label": label,
                        "domain": "NT AUTHORITY",
                        "is_boundary": True,
                    },
                ),
            )
            return sid
        raise ValueError(f"ambiguous node reference {reference!r}")
    return next(iter(matches))


def _provenance_record(
    raw: Mapping[str, object], *, attribute: str, record_id: str | None
) -> Provenance:
    required = ("raw_file", "collector", "timestamp")
    if any(
        not isinstance(raw.get(field), str) or not str(raw[field]).strip() for field in required
    ):
        raise ValueError("edge evidence provenance is missing required fields")
    raw_file = cast(str, raw["raw_file"]).strip()
    if raw_file.startswith("snapshot:"):
        prefix, separator, _relative_path = raw_file.partition("/")
        digest = prefix.removeprefix("snapshot:")
        if not separator or not _MANIFEST_SNAPSHOT_DIGEST.fullmatch(digest):
            raise ValueError("manifest raw_file has an invalid snapshot reference")
        raw_snapshot_id = raw.get("snapshot_id")
        expected_snapshot_id = f"sha256:{digest}"
        if raw_snapshot_id != expected_snapshot_id:
            raise ValueError("manifest raw_file snapshot does not match snapshot_id")

    time_provenance = raw.get("time_provenance")
    if time_provenance is None:
        # Older/non-manifest raw records lack origin metadata. Keep that
        # uncertainty explicit instead of treating timestamp presence as proof.
        time_provenance = "unknown_legacy"
    if time_provenance not in {
        "observed",
        "assumed",
        "derived",
        "externally_evidenced",
        "unknown_legacy",
    }:
        raise ValueError(f"unsupported time provenance status: {time_provenance!r}")

    result: dict[str, str] = {
        "raw_file": raw_file,
        "collector": cast(str, raw["collector"]).strip(),
        "timestamp": cast(str, raw["timestamp"]).strip(),
        "timestamp_status": cast(str, time_provenance),
        "evidence_type": "positive",
    }
    time_reason = raw.get("time_provenance_reason")
    if time_reason is not None:
        if not isinstance(time_reason, str) or not time_reason.strip():
            raise ValueError("time provenance reason must be a non-empty string")
        result["time_provenance_reason"] = time_reason.strip()
    if time_provenance in {"derived", "externally_evidenced"} and not result.get(
        "time_provenance_reason"
    ):
        raise ValueError(f"time provenance status {time_provenance!r} requires an audit reason")
    supplied_attribute = raw.get("attribute")
    if isinstance(supplied_attribute, str) and supplied_attribute.strip():
        result["attribute"] = supplied_attribute.strip()
    else:
        result["attribute"] = attribute
    supplied_record_id = raw.get("record_id")
    if isinstance(supplied_record_id, str) and supplied_record_id.strip():
        result["record_id"] = supplied_record_id.strip()
    elif record_id:
        result["record_id"] = record_id
    return cast(Provenance, result)


def _candidate_provenance(record: NormalizedRecord, candidate: _EdgeCandidate) -> list[Provenance]:
    item_key = _canonical_json(candidate.item)
    field_root = candidate.field.split("[", 1)[0].split(".", 1)[0]
    lineage = [
        line
        for line in record.evidence_lineage
        if line.field.split(".", 1)[0].split("[", 1)[0] == field_root and line.item_key == item_key
    ]
    raw_sources = [source for line in lineage for source in line.provenance]
    if not raw_sources:
        raw_sources = list(record.raw_provenance) or [record.raw.provenance]
    result = [
        _provenance_record(source, attribute=candidate.field, record_id=candidate.record_id)
        for source in raw_sources
    ]
    unique = {_canonical_json(item): item for item in result}
    return [cast(Provenance, unique[key]) for key in sorted(unique)]


def _inference_provenance(
    result: HostAccessResult, *, edge_evidence: bool = False
) -> list[Provenance]:
    """Convert internal primitive evidence to contract-shaped provenance."""

    evidence_type = {
        InferenceStatus.POSITIVE: "positive",
        InferenceStatus.UNKNOWN: "unknown",
        InferenceStatus.REJECTED: "rejected",
        InferenceStatus.NEGATIVE_KNOWN: "rejected",
    }[result.status]
    if (
        result.status is InferenceStatus.POSITIVE
        and result.evidence_source is EvidenceSource.DERIVED
    ):
        evidence_type = "inferred"
    if edge_evidence:
        evidence_type = "positive"
    sources: list[tuple[Mapping[str, object], str]] = []
    for evidence in result.primitive_evidence:
        for source in evidence.provenance:
            sources.append((source, evidence.field))
    for step in result.derivation:
        for evidence in step.evidence:
            for source in evidence.provenance:
                sources.append((source, evidence.field))
    for condition in result.conditions:
        for evidence in condition.evidence:
            for source in evidence.provenance:
                sources.append((source, evidence.field))
    if not sources:
        return []
    unique: dict[str, Provenance] = {}
    for source, attribute in sources:
        item = _provenance_record(source, attribute=attribute, record_id=None)
        item["evidence_type"] = evidence_type
        unique[_canonical_json(item)] = item
    return [unique[key] for key in sorted(unique)]


def _canonical_derivation_kind(result: HostAccessResult) -> str:
    if any(step.operation.startswith("gpo_") for step in result.derivation):
        return "gpo_resultant"
    return "nested_membership"


def _canonical_path(
    result: HostAccessResult, edge_provenance: list[Provenance], node_ids: set[str]
) -> DerivationPath:
    available = {provenance_ref(item) for item in edge_provenance}
    fallback = sorted(available)
    steps: list[CanonicalDerivationStep] = []
    for order, step in enumerate(result.derivation):
        refs: set[str] = set()
        for evidence in step.evidence:
            for source in evidence.provenance:
                item = _provenance_record(source, attribute=evidence.field, record_id=None)
                item["evidence_type"] = "positive"
                reference = provenance_ref(item)
                if reference in available:
                    refs.add(reference)
        if not refs:
            refs.update(fallback)
        canonical_step: CanonicalDerivationStep = {
            "order": order,
            "operation": step.operation,
            "evidence_refs": sorted(refs),
        }
        source = step.source
        target = step.target
        if step.operation == "host_local_membership" and target not in node_ids:
            target = result.target
        if source is None and step.operation == "resultant_host_state":
            source = result.source
            target = result.target
        if source is not None:
            canonical_step["source"] = source
        if target is not None:
            canonical_step["target"] = target
        steps.append(canonical_step)
    if not steps:
        raise ValueError("positive derived host-access result has no derivation steps")
    path: DerivationPath = {"steps": steps}
    if result.conditions:
        conditions: list[DerivationCondition] = []
        for condition in result.conditions:
            refs: set[str] = set()
            for evidence in condition.evidence:
                for source in evidence.provenance:
                    item = _provenance_record(source, attribute=evidence.field, record_id=None)
                    item["evidence_type"] = "positive"
                    reference = provenance_ref(item)
                    if reference in available:
                        refs.add(reference)
            if not refs:
                raise ValueError(
                    f"derived proof condition {condition.predicate!r} has no canonical evidence"
                )
            conditions.append({"predicate": condition.predicate, "evidence_refs": sorted(refs)})
        path["conditions"] = conditions
    return path


def _assessment_id(result: HostAccessResult) -> str:
    payload = [
        result.relationship,
        result.source,
        result.target,
        result.status.value,
        result.reason,
        [[step.operation, step.source, step.target] for step in result.derivation],
    ]
    digest = hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()
    return f"host-access:{digest}"


def _assessment_for(
    result: HostAccessResult,
    provenance: list[Provenance],
    *,
    include_subject: bool = True,
) -> Assessment:
    status = (
        AssessmentStatus.INFERRED
        if result.status is InferenceStatus.POSITIVE
        else AssessmentStatus.UNKNOWN
        if result.status is InferenceStatus.UNKNOWN
        else AssessmentStatus.REJECTED
    )
    assessment: Assessment = {
        "id": _assessment_id(result),
        "status": status,
        "reason": result.reason,
        "provenance": provenance,
        "target": result.target,
        "kind": result.relationship,
    }
    if include_subject:
        assessment["subject"] = result.source
    return assessment


class DirectGraphBuilder(GraphBuilder):
    """Build the canonical graph from direct, source-backed relationships.

    ``metadata`` should normally be supplied in full.  For legacy callers, a
    valid single snapshot ID may be inferred from record provenance; graph
    creation time remains required because it must not be invented from
    collection timestamps.
    """

    def __init__(
        self,
        *,
        metadata: Mapping[str, object] | None = None,
        contract_path: Path = _DEFAULT_CONTRACT_PATH,
    ) -> None:
        if metadata is not None and not isinstance(metadata, Mapping):
            raise TypeError("metadata must be a mapping")
        self._metadata = dict(metadata or {})
        self._contract_path = Path(contract_path)
        try:
            self._contract = load_contract(self._contract_path)
        except (ValueError, OSError) as exc:
            raise RuntimeError("unable to load graph contract") from exc

    def _metadata_for(self, records: Iterable[NormalizedRecord]) -> dict[str, object]:
        metadata = copy.deepcopy(self._metadata)
        metadata.setdefault("contract_version", self._contract["version"])
        metadata.setdefault("weight_profile", self._contract["default_profile"])
        code_version = metadata.get("code_version")
        if not isinstance(code_version, str) or not code_version.strip():
            raise ValueError("metadata.code_version is required and must be supplied explicitly")

        snapshot_ids = {
            value
            for record in records
            for value in [record.raw.provenance.get("snapshot_id")]
            if isinstance(value, str) and value.strip()
        }
        if "snapshot_id" not in metadata:
            if len(snapshot_ids) != 1:
                raise ValueError(
                    "metadata.snapshot_id is required when records do not provide "
                    "one valid snapshot"
                )
            metadata["snapshot_id"] = next(iter(snapshot_ids))
        elif snapshot_ids and snapshot_ids != {metadata["snapshot_id"]}:
            raise ValueError("records do not belong to metadata.snapshot_id")
        if "created_at" not in metadata:
            raise ValueError("metadata.created_at is required and must be supplied explicitly")
        return metadata

    def build(
        self,
        records: Iterable[NormalizedRecord],
        *,
        error_policy: ErrorPolicy = ErrorPolicy.FAIL_FAST,
    ) -> Graph:
        if not isinstance(error_policy, ErrorPolicy):
            raise TypeError("error_policy must be an ErrorPolicy")

        prepared = list(
            process_records(
                records,
                lambda record: _prepare(record, self._contract),
                error_policy=error_policy,
                logger=_LOGGER,
            )
        )
        tentative_nodes: dict[str, GraphNode] = {}
        aliases: defaultdict[str, set[str]] = defaultdict(set)
        for item in prepared:
            previous = tentative_nodes.get(item.node["id"])
            if previous is not None and previous != item.node:
                raise RecordError(
                    "canonical node ID has conflicting node fields",
                    stage="build",
                    record_id=item.record.id,
                )
            tentative_nodes[item.node["id"]] = item.node
            for alias in _alias_values(item.record):
                aliases[alias.casefold()].add(item.node["id"])

        accepted: list[_PreparedRecord] = []
        edge_provenance: dict[tuple[str, str, str], dict[str, Provenance]] = {}
        for item in prepared:
            resolved: list[tuple[_EdgeCandidate, str, str, list[Provenance]]] = []
            pending: dict[str, GraphNode] = {}
            try:
                for candidate in item.candidates:
                    source = _resolve(
                        candidate.source_ref,
                        candidate.source_kind,
                        aliases,
                        tentative_nodes,
                        pending,
                        boundary_member_source=(
                            candidate.kind == "MemberOf"
                            and candidate.field.startswith("Members[].")
                        ),
                    )
                    target = _resolve(
                        candidate.target_ref,
                        candidate.target_kind,
                        aliases,
                        tentative_nodes,
                        pending,
                    )
                    candidate_nodes = tentative_nodes | pending
                    if (
                        candidate.kind == "MemberOf"
                        and candidate_nodes[source]["kind"] not in _PRINCIPAL_KINDS
                    ):
                        raise ValueError("MemberOf source is not a principal")
                    if candidate.kind == "MemberOf" and candidate_nodes[target]["kind"] != "Group":
                        raise ValueError("MemberOf target is not a Group")
                    if candidate.kind == "HasSession":
                        if (
                            candidate_nodes[source]["kind"] != "Computer"
                            or candidate_nodes[target]["kind"] != "User"
                        ):
                            raise ValueError("HasSession must be Computer to User")
                    if candidate.kind in {"GenericAll", "WriteDacl"}:
                        if candidate_nodes[source]["kind"] not in _PRINCIPAL_KINDS:
                            raise ValueError(f"{candidate.kind} source is not a principal")
                    if candidate.kind == "ForceChangePassword":
                        if candidate_nodes[source]["kind"] not in _PRINCIPAL_KINDS:
                            raise ValueError("ForceChangePassword source is not a principal")
                        if candidate_nodes[target]["kind"] != "User":
                            raise ValueError("ForceChangePassword target is not a User")
                    resolved.append(
                        (candidate, source, target, _candidate_provenance(item.record, candidate))
                    )
            except (TypeError, ValueError) as exc:
                error = _candidate_error(item.record, str(exc))
                if error_policy is ErrorPolicy.FAIL_FAST:
                    raise error from exc
                if error_policy is ErrorPolicy.LOG_WARNING:
                    _LOGGER.warning("%s", error)
                continue

            accepted.append(item)
            tentative_nodes.update(pending)
            for candidate, source, target, provenance in resolved:
                key = (source, target, candidate.kind)
                bucket = edge_provenance.setdefault(key, {})
                bucket.update({_canonical_json(item): item for item in provenance})

        accepted_ids = {item.node["id"] for item in accepted}
        accepted_ids.update(
            node_id for node_id, node in tentative_nodes.items() if node["is_boundary"]
        )
        nodes = {node_id: tentative_nodes[node_id] for node_id in accepted_ids}
        metadata = self._metadata_for(item.record for item in accepted)
        edges: list[GraphEdge] = []
        assessments: dict[str, Assessment] = {}
        derived_paths: dict[tuple[str, str, str], dict[str, DerivationPath]] = defaultdict(dict)
        derived_kinds: dict[tuple[str, str, str], set[str]] = defaultdict(set)
        weights = self._contract["profiles"][metadata["weight_profile"]]["weights"]

        # Host-access inference is deliberately downstream of direct record
        # preparation.  This keeps direct MemberOf/ACL/session assembly intact
        # while allowing the inference layer to use the complete normalized
        # snapshot for effective membership resolution.
        for result in evaluate_host_access(item.record for item in accepted):
            if result.target not in accepted_ids:
                continue
            subject_resolved = result.source in accepted_ids
            if not subject_resolved and result.status is InferenceStatus.POSITIVE:
                result = replace(
                    result,
                    status=InferenceStatus.UNKNOWN,
                    evidence_source=EvidenceSource.UNKNOWN,
                    canonical_emit_allowed=False,
                    reason="host-access principal identity could not be resolved",
                )
            elif not subject_resolved and result.status is InferenceStatus.UNKNOWN:
                result = replace(
                    result,
                    reason=f"{result.reason}; host-access principal identity could not be resolved",
                )
            provenance = _inference_provenance(
                result,
                edge_evidence=result.status is InferenceStatus.POSITIVE,
            )
            if result.status is InferenceStatus.POSITIVE and (
                result.canonical_emit_allowed or result.evidence_source is EvidenceSource.DERIVED
            ):
                key = (result.source, result.target, result.relationship)
                bucket = edge_provenance.setdefault(key, {})
                bucket.update({_canonical_json(item): item for item in provenance})
                if result.evidence_source is EvidenceSource.DERIVED:
                    path = _canonical_path(result, list(bucket.values()), accepted_ids)
                    derived_paths[key][path_key(path)] = path
                    derived_kinds[key].add(_canonical_derivation_kind(result))
                continue
            if provenance:
                assessment = _assessment_for(
                    result,
                    provenance,
                    include_subject=subject_resolved,
                )
                assessments[assessment["id"]] = assessment

        # Build the final deterministic edge list after direct and host-access
        # evidence have been aggregated.
        edges = []
        for (source, target, kind), provenance in sorted(edge_provenance.items()):
            if source not in accepted_ids or target not in accepted_ids:
                continue
            edge: dict[str, object] = {
                "id": canonical_edge_id(source, target, kind),
                "source": source,
                "target": target,
                "kind": kind,
                "weight": weights[kind],
                "provenance": [provenance[key] for key in sorted(provenance)],
            }
            paths = sorted_unique_paths(
                list(derived_paths.get((source, target, kind), {}).values())
            )
            if paths:
                lineage_kind = (
                    next(iter(derived_kinds[(source, target, kind)]))
                    if len(derived_kinds[(source, target, kind)]) == 1
                    else "host_access"
                )
                edge["derivation"] = cast(
                    DerivedLineage,
                    {"version": LINEAGE_VERSION, "kind": lineage_kind, "paths": paths},
                )
            edges.append(cast(GraphEdge, edge))

        graph = cast(
            Graph,
            {
                "metadata": metadata,
                "nodes": [nodes[node_id] for node_id in sorted(nodes)],
                "edges": edges,
                "assessments": [assessments[key] for key in sorted(assessments)],
            },
        )
        validate_graph(cast(dict, graph), self._contract)
        return graph

    def build_snapshot(
        self,
        records: Iterable[NormalizedRecord],
        *,
        error_policy: ErrorPolicy = ErrorPolicy.FAIL_FAST,
    ) -> tuple[Graph, SnapshotFacts]:
        """Materialize structure and read-only facts together without changing Graph JSON.

        Use serialize_snapshot for persisted runs; serialize_graph alone transports
        only structure. Fact extraction filters to the builder's accepted User IDs.
        """
        from .snapshot_facts import materialize_snapshot_facts

        materialized = tuple(records)
        graph = self.build(materialized, error_policy=error_policy)
        return graph, materialize_snapshot_facts(materialized, graph)


__all__ = [
    "DirectGraphBuilder",
    "canonical_edge_id",
]
