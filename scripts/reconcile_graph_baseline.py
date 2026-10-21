"""Reconcile candidate structural graph against a baseline graph export.

Compares:
1. Mapped node identity sets partitioned by population (collected vs boundary)
   and domain scope.
2. Directed (source, kind, target) triples partitioned by relationship kind.
3. Stored relationship multiplicity reported separately from unique triples.

Adheres to:
- Graph Contract 1.3.0
- Issue #47 acceptance criteria
- ADR-0007 / #82 baseline reconciliation requirements
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from collections.abc import Mapping
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if __package__ in {None, ""}:
    sys.path.insert(0, str(ROOT))

import yaml  # noqa: E402

from scripts.check_contract import (  # noqa: E402
    canonical_id_patterns,
    provenance_reference,
    validate_derivation,
    validate_provenance,
)
from src.parser.scopes import normalize_guid, normalize_sid, parse_scoped_sid  # noqa: E402

M1_RELATIONSHIPS = {
    "MemberOf": "MemberOf",
    "AdminTo": "AdminTo",
    "GenericAll": "GenericAll",
    "WriteDacl": "WriteDacl",
    "ForceChangePassword": "ForceChangePassword",
    "CanRDP": "CanRDP",
    "CanPSRemote": "CanPSRemote",
    "HasSession": "HasSession",
}

RELATIONSHIP_ALIASES = {
    "memberof": "MemberOf",
    "adminto": "AdminTo",
    "genericall": "GenericAll",
    "writedacl": "WriteDacl",
    "forcechangepassword": "ForceChangePassword",
    "canrdp": "CanRDP",
    "canpsremote": "CanPSRemote",
    "hassession": "HasSession",
}

NODE_KIND_ALIASES = {
    "user": "User",
    "group": "Group",
    "computer": "Computer",
    "domain": "Domain",
    "ou": "OU",
    "gpo": "GPO",
}

COMPARISON_SCOPE = {
    "id": "m1-structural-v1",
    "node_population": "collected_and_boundary",
    "relationship_kinds": list(M1_RELATIONSHIPS),
    "memberof_semantics": "direct",
}
CONTRACT = yaml.safe_load((ROOT / "configs/contract.yml").read_text(encoding="utf-8"))
ID_PATTERNS = canonical_id_patterns(CONTRACT)


class InputError(ValueError):
    """An input record cannot be used without losing or guessing information."""


@dataclass(frozen=True)
class NodeItem:
    """Canonical representation of an extracted node."""

    id: str
    kind: str
    domain: str
    is_boundary: bool
    raw_id: str | None = None


@dataclass(frozen=True)
class DirectedTriple:
    """Directed relationship triple (source, kind, target)."""

    source: str
    kind: str
    target: str

    def as_tuple(self) -> tuple[str, str, str]:
        return (self.source, self.kind, self.target)


@dataclass
class ExtractedGraph:
    """Normalized structural graph data prepared for comparison."""

    name: str
    metadata: dict[str, Any]
    nodes: dict[str, NodeItem]
    unique_triples: set[DirectedTriple]
    stored_triple_occurrences: Counter[DirectedTriple]
    stored_evidence_occurrences: int | None
    unmapped_node_ids: set[str] = field(default_factory=set)
    non_contract_kinds: set[str] = field(default_factory=set)
    edge_references: dict[DirectedTriple, list[dict[str, Any]]] = field(default_factory=dict)
    duplicate_node_records: int = 0


@dataclass
class PopulationSummary:
    """Population statistics for nodes."""

    total: int
    collected: int
    boundary: int
    by_kind: dict[str, dict[str, int]]
    by_domain: dict[str, int]


@dataclass
class MultiplicitySummary:
    """Multiplicity statistics for relationships."""

    unique_triples: int
    stored_edges: int
    stored_evidence_occurrences: int | None
    multiplicity_ratio: float
    by_kind: dict[str, dict[str, int]]
    evidence_status: str
    evidence_reason: str | None


@dataclass
class SetComparison:
    """Detailed set comparison results."""

    candidate_count: int
    baseline_count: int
    intersection_count: int
    candidate_only_count: int
    baseline_only_count: int
    jaccard_similarity: float
    candidate_only: list[str]
    baseline_only: list[str]
    candidate_only_samples: list[str]
    baseline_only_samples: list[str]


@dataclass
class ReconciliationReport:
    """Full structured baseline reconciliation result."""

    verdict: str  # MATCH, DISCREPANCY, NOT_MEASURABLE
    summary: str
    reconciliation_timestamp: str
    candidate_metadata: dict[str, Any]
    baseline_metadata: dict[str, Any]
    node_reconciliation: dict[str, Any]
    triple_reconciliation: dict[str, Any]
    discrepancy_ledgers: dict[str, Any]
    input_validation: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def normalize_relationship_kind(raw_kind: str) -> str:
    """Normalize relationship names across BloodHound CE, Legacy, and canonical formats."""
    cleaned = raw_kind.strip()
    return RELATIONSHIP_ALIASES.get(cleaned.casefold(), cleaned)


def normalize_node_kind(raw_kind: str) -> str:
    """Normalize node kind across collectors and exports."""
    cleaned = raw_kind.strip()
    return NODE_KIND_ALIASES.get(cleaned.casefold(), cleaned)


def canonical_node_id(value: str) -> str | None:
    """Normalize only the ID grammars already defined by the parser/contract."""
    sid = normalize_sid(value)
    if sid is not None:
        return sid if ID_PATTERNS[3].fullmatch(sid) is None else None
    scoped = parse_scoped_sid(value)
    if scoped is not None:
        scope, local_sid = scoped
        return scope.canonical_sid(local_sid)
    return normalize_guid(value)


def map_node_id(raw_id: str, identity_mapping: Mapping[str, str] | None) -> str:
    """Preserve scoped IDs; Legacy aliases require an explicit mapping."""
    canonical = canonical_node_id(raw_id.strip())
    if canonical is not None:
        if identity_mapping and raw_id in identity_mapping:
            if identity_mapping[raw_id] != canonical:
                raise InputError(f"mapping: cannot replace canonical identity {raw_id!r}")
        return canonical
    if identity_mapping and raw_id in identity_mapping:
        return identity_mapping[raw_id]
    raise InputError(f"unresolved identity {raw_id!r}; explicit mapping required")


def validate_mapping(mapping: Mapping[str, str] | None) -> None:
    """Reject invalid entries even when the current export does not use them."""
    if mapping is None:
        return
    if not isinstance(mapping, dict):
        raise InputError("mapping: expected an object of raw ID -> canonical ID")
    for raw_id, target in mapping.items():
        if not isinstance(raw_id, str) or not raw_id.strip() or raw_id != raw_id.strip():
            raise InputError("mapping: keys must be nonempty strings without outer whitespace")
        if not isinstance(target, str) or canonical_node_id(target) != target:
            raise InputError(f"mapping[{raw_id!r}]: invalid canonical target {target!r}")
        canonical = canonical_node_id(raw_id)
        if canonical is not None and canonical != target:
            raise InputError(f"mapping[{raw_id!r}]: cannot replace canonical identity")


def read_field(
    item: dict, properties: dict, names: tuple[str, ...], path: str, *, normalize=None
) -> Any:
    """Read supported aliases without choosing a winner for conflicting fields."""
    values = [
        container[key] for container in (item, properties) for key in names if key in container
    ]
    if not values:
        raise InputError(f"{path}: missing {names[0]}")
    if normalize:
        if any(not isinstance(value, str) or not value.strip() for value in values):
            raise InputError(f"{path}: {names[0]} must be a nonempty string")
        values = [normalize(value.strip()) for value in values]
    if any(type(value) is not type(values[0]) or value != values[0] for value in values[1:]):
        raise InputError(f"{path}: conflicting aliases for {names[0]}")
    return values[0]


def extract_graph(
    data: dict[str, Any],
    name: str = "graph",
    identity_mapping: Mapping[str, str] | None = None,
) -> ExtractedGraph:
    """Validate every record before preparing structural observations."""
    validate_mapping(identity_mapping)
    if not isinstance(data, dict):
        raise InputError(f"{name}: graph must be a JSON object")
    if "metadata" in data and "meta" in data:
        raise InputError(f"{name}: ambiguous metadata/meta containers")
    metadata = data.get("metadata", data.get("meta", {}))
    if not isinstance(metadata, dict):
        raise InputError(f"{name}: metadata must be an object")
    for key in ("status", "reason"):
        if key in metadata and (not isinstance(metadata[key], str) or not metadata[key].strip()):
            raise InputError(f"{name}: metadata {key} must be a nonempty string")
    if "edges" in data and "relationships" in data:
        raise InputError(f"{name}: ambiguous edges/relationships containers")
    edge_key = "edges" if "edges" in data else "relationships"
    raw_nodes = data.get("nodes")
    raw_edges = data.get(edge_key)
    if not isinstance(raw_nodes, list) or not isinstance(raw_edges, list):
        raise InputError(f"{name}: nodes and edges/relationships must be arrays")

    nodes: dict[str, NodeItem] = {}
    node_records: dict[str, dict] = {}
    duplicate_count = 0
    for index, item in enumerate(raw_nodes):
        path = f"{name}/nodes/{index}"
        if not isinstance(item, dict):
            raise InputError(f"{path}: node must be an object")
        props = item.get("properties", {})
        if not isinstance(props, dict):
            raise InputError(f"{path}: properties must be an object")
        raw_id = read_field(item, props, ("id", "objectid"), path, normalize=str.strip)
        try:
            canonical_id = map_node_id(raw_id, identity_mapping)
        except InputError as exc:
            raise InputError(f"{path}: {exc}") from exc
        kind_item = dict(item)
        if "labels" in item:
            labels = item["labels"]
            if (
                not isinstance(labels, list)
                or not labels
                or any(not isinstance(label, str) or not label.strip() for label in labels)
            ):
                raise InputError(f"{path}: labels must be a nonempty string array")
            kinds = {normalize_node_kind(label) for label in labels} & set(
                NODE_KIND_ALIASES.values()
            )
            if len(kinds) != 1:
                raise InputError(f"{path}: labels must resolve to exactly one supported node kind")
            kind_item["label_kind"] = kinds.pop()
        kind = read_field(
            kind_item, props, ("kind", "label_kind"), path, normalize=normalize_node_kind
        )
        if kind not in NODE_KIND_ALIASES.values():
            raise InputError(f"{path}: unsupported node kind {kind!r}")
        domain = read_field(item, props, ("domain",), path, normalize=str.upper)
        boundary = read_field(item, props, ("is_boundary", "boundary"), path)
        if type(boundary) is not bool:
            raise InputError(f"{path}: is_boundary must be boolean")
        node = NodeItem(canonical_id, kind, domain, boundary, raw_id)
        if canonical_id in nodes:
            previous = nodes[canonical_id]
            if previous.raw_id != raw_id:
                raise InputError(
                    f"{path}: mapping collision for {canonical_id!r}: "
                    f"{previous.raw_id!r} and {raw_id!r}; alias reconciliation unresolved"
                )
            if previous != node or node_records[canonical_id] != item:
                raise InputError(f"{path}: conflicting duplicate node record {canonical_id!r}")
            duplicate_count += 1
        else:
            nodes[canonical_id] = node
            node_records[canonical_id] = item

    unique_triples: set[DirectedTriple] = set()
    stored_occurrences: Counter[DirectedTriple] = Counter()
    references: dict[DirectedTriple, list[dict[str, Any]]] = defaultdict(list)
    evidence_count = 0
    complete_evidence = bool(raw_edges)
    for index, edge in enumerate(raw_edges):
        path = f"{name}/{edge_key}/{index}"
        if not isinstance(edge, dict):
            raise InputError(f"{path}: edge must be an object")
        raw_source = read_field(
            edge, {}, ("source", "start", "source_id"), path, normalize=str.strip
        )
        raw_target = read_field(edge, {}, ("target", "end", "target_id"), path, normalize=str.strip)
        kind = read_field(edge, {}, ("kind", "type"), path, normalize=normalize_relationship_kind)
        try:
            source_id = map_node_id(raw_source, identity_mapping)
            target_id = map_node_id(raw_target, identity_mapping)
        except InputError as exc:
            raise InputError(f"{path}: {exc}") from exc
        if source_id not in nodes or target_id not in nodes:
            raise InputError(f"{path}: unresolved endpoint ({source_id!r}, {target_id!r})")
        # An endpoint alias absent from the node table is not an observed identity mapping.
        if nodes[source_id].raw_id != raw_source or nodes[target_id].raw_id != raw_target:
            raise InputError(f"{path}: endpoint alias is absent from the exported node records")
        provenance = edge.get("provenance")
        if "provenance" in edge:
            if not isinstance(provenance, list):
                raise InputError(f"{path}: provenance must be an array when supplied")
            for p_index, entry in enumerate(provenance):
                p_path = f"{path}/provenance/{p_index}"
                if not isinstance(entry, dict):
                    raise InputError(f"{p_path}: provenance entry must be an object")
                for key in ("raw_file", "record_id", "attribute"):
                    if not isinstance(entry.get(key), str) or not entry[key].strip():
                        raise InputError(f"{p_path}: missing/non-string provenance {key}")
                if "snapshot_id" in entry and entry["snapshot_id"] != metadata.get("snapshot_id"):
                    raise InputError(
                        f"{p_path}: provenance snapshot_id differs from graph snapshot_id"
                    )
                raw_file = entry["raw_file"]
                if raw_file.startswith("snapshot:"):
                    bound_snapshot = raw_file.split("/", 1)[0].replace("snapshot:", "sha256:", 1)
                    if bound_snapshot != metadata.get("snapshot_id"):
                        raise InputError(
                            f"{p_path}: raw_file snapshot differs from graph snapshot_id"
                        )
            if provenance:
                try:
                    validate_provenance(
                        provenance, CONTRACT, path, allowed_evidence_types={"positive"}
                    )
                except ValueError as exc:
                    raise InputError(f"{path}: {exc}") from exc
        if edge.get("id") is not None and (
            not isinstance(edge["id"], str) or not edge["id"].strip()
        ):
            raise InputError(f"{path}: edge id must be a nonempty string when supplied")
        if "derivation" in edge:
            try:
                validate_derivation(
                    edge["derivation"],
                    {
                        "id": edge.get("id", path),
                        "source": source_id,
                        "target": target_id,
                        "kind": kind,
                        "provenance": provenance or [],
                    },
                    CONTRACT,
                    set(nodes),
                    {nid: node.kind for nid, node in nodes.items()},
                )
            except (ValueError, TypeError, KeyError) as exc:
                raise InputError(f"{path}: invalid derivation: {exc}") from exc
        triple = DirectedTriple(source_id, kind, target_id)
        unique_triples.add(triple)
        stored_occurrences[triple] += 1
        if not provenance:
            complete_evidence = False
        else:
            evidence_count += len(provenance)
        references[triple].append(
            {
                "graph": name,
                "record_pointer": f"/{edge_key}/{index}",
                "edge_id": edge.get("id"),
                "raw_source": raw_source,
                "raw_target": raw_target,
                "provenance": provenance,
                "provenance_refs": [provenance_reference(p) for p in provenance]
                if provenance
                else [],
                "derivation": edge.get("derivation"),
            }
        )

    return ExtractedGraph(
        name=name,
        metadata=metadata,
        nodes=nodes,
        unique_triples=unique_triples,
        stored_triple_occurrences=stored_occurrences,
        stored_evidence_occurrences=evidence_count if complete_evidence else None,
        non_contract_kinds={t.kind for t in unique_triples if t.kind not in M1_RELATIONSHIPS},
        edge_references=dict(references),
        duplicate_node_records=duplicate_count,
    )


def compute_population_summary(nodes: Mapping[str, NodeItem]) -> PopulationSummary:
    """Compute counts for total, collected, and boundary populations by kind and domain."""
    total = len(nodes)
    collected = sum(1 for n in nodes.values() if not n.is_boundary)
    boundary = sum(1 for n in nodes.values() if n.is_boundary)

    by_kind: dict[str, dict[str, int]] = defaultdict(
        lambda: {"total": 0, "collected": 0, "boundary": 0}
    )
    by_domain: dict[str, int] = Counter()

    for n in nodes.values():
        by_kind[n.kind]["total"] += 1
        if n.is_boundary:
            by_kind[n.kind]["boundary"] += 1
        else:
            by_kind[n.kind]["collected"] += 1
        by_domain[n.domain] += 1

    return PopulationSummary(
        total=total,
        collected=collected,
        boundary=boundary,
        by_kind=dict(by_kind),
        by_domain=dict(by_domain),
    )


def compute_multiplicity_summary(
    unique_triples: set[DirectedTriple],
    stored_occurrences: Counter[DirectedTriple],
    total_evidence_count: int | None,
) -> MultiplicitySummary:
    """Summarize unique triples vs stored edge entries and evidence occurrences."""
    unique_count = len(unique_triples)
    stored_count = sum(stored_occurrences.values())
    ratio = (stored_count / unique_count) if unique_count > 0 else 1.0

    by_kind: dict[str, dict[str, int]] = defaultdict(lambda: {"unique": 0, "stored": 0})
    for triple, count in stored_occurrences.items():
        by_kind[triple.kind]["unique"] += 1
        by_kind[triple.kind]["stored"] += count

    return MultiplicitySummary(
        unique_triples=unique_count,
        stored_edges=stored_count,
        stored_evidence_occurrences=total_evidence_count,
        multiplicity_ratio=round(ratio, 4),
        by_kind=dict(by_kind),
        evidence_status="measured" if total_evidence_count is not None else "not_measurable",
        evidence_reason=(
            None
            if total_evidence_count is not None
            else "Complete nonempty provenance arrays are unavailable; "
            "stored edges do not measure raw evidence"
        ),
    )


def compare_sets(
    candidate_set: set[str],
    baseline_set: set[str],
    sample_limit: int = 10,
) -> SetComparison:
    """Perform mathematical set comparison between candidate and baseline sets."""
    intersection = candidate_set & baseline_set
    cand_only = candidate_set - baseline_set
    base_only = baseline_set - candidate_set
    union_len = len(candidate_set | baseline_set)
    jaccard = (len(intersection) / union_len) if union_len > 0 else 1.0

    return SetComparison(
        candidate_count=len(candidate_set),
        baseline_count=len(baseline_set),
        intersection_count=len(intersection),
        candidate_only_count=len(cand_only),
        baseline_only_count=len(base_only),
        jaccard_similarity=round(jaccard, 6),
        candidate_only=sorted(cand_only),
        baseline_only=sorted(base_only),
        candidate_only_samples=sorted(cand_only)[:sample_limit],
        baseline_only_samples=sorted(list(base_only))[:sample_limit],
    )


def graph_multiplicity(graph: ExtractedGraph, triples: set[DirectedTriple]) -> MultiplicitySummary:
    """Measure only the selected observations; missing evidence never becomes one."""
    references = [ref for triple in triples for ref in graph.edge_references[triple]]
    count = (
        sum(len(ref["provenance"]) for ref in references)
        if references and all(ref["provenance"] for ref in references)
        else None
    )
    return compute_multiplicity_summary(
        triples, Counter({t: graph.stored_triple_occurrences[t] for t in triples}), count
    )


def eligibility_reasons(candidate: ExtractedGraph, baseline: ExtractedGraph) -> list[str]:
    """A matching set is evidence only within an explicit, bound comparison scope."""
    reasons = []
    for graph in (candidate, baseline):
        meta = graph.metadata
        if not isinstance(meta.get("snapshot_id"), str) or not re.fullmatch(
            r"sha256:[0-9a-f]{64}", meta["snapshot_id"]
        ):
            reasons.append(f"{graph.name}: missing/invalid snapshot_id")
        scope = meta.get("comparison_scope")
        if not isinstance(scope, dict):
            reasons.append(f"{graph.name}: missing comparison_scope")
        else:
            kinds = scope.get("relationship_kinds")
            if (
                any(
                    scope.get(key) != value
                    for key, value in COMPARISON_SCOPE.items()
                    if key != "relationship_kinds"
                )
                or not isinstance(kinds, list)
                or any(not isinstance(kind, str) for kind in kinds)
                or len(kinds) != len(M1_RELATIONSHIPS)
                or set(kinds) != set(M1_RELATIONSHIPS)
                or set(scope) != set(COMPARISON_SCOPE)
            ):
                reasons.append(
                    f"{graph.name}: unsupported comparison_scope; common semantics unresolved"
                )
        if not isinstance(meta.get("source_evidence"), str) or not meta["source_evidence"].strip():
            reasons.append(f"{graph.name}: missing source_evidence for input binding")
        if meta.get("export_complete") is not True:
            reasons.append(f"{graph.name}: export_complete is not verified true")
        if type(meta.get("synthetic")) is not bool:
            reasons.append(f"{graph.name}: synthetic mode must be declared explicitly")
        if meta.get("status", "measured") != "measured":
            reasons.append(f"{graph.name}: input status is not measured")
        if not graph.nodes:
            reasons.append(f"{graph.name}: no observed nodes")
    if candidate.metadata.get("snapshot_id") != baseline.metadata.get("snapshot_id"):
        reasons.append("candidate/baseline snapshot_id mismatch")
    if candidate.metadata.get("synthetic") != baseline.metadata.get("synthetic"):
        reasons.append("candidate/baseline synthetic mode mismatch")
    return reasons


def difference_entry(graph: ExtractedGraph, triple: DirectedTriple) -> dict[str, Any]:
    """Keep exact identities and available exported evidence; causes await investigation."""
    refs = graph.edge_references[triple]
    return {
        "triple": asdict(triple),
        "references": refs,
        "evidence_status": "available"
        if all(ref["provenance"] for ref in refs)
        else "not_measurable",
        "reason_status": "unresolved",
        "reason": None,
    }


def reconcile_graphs(
    candidate_data: dict[str, Any],
    baseline_data: dict[str, Any],
    identity_mapping: Mapping[str, str] | None = None,
    candidate_name: str = "candidate",
    baseline_name: str = "baseline",
) -> ReconciliationReport:
    """Compare validated observations within the documented common M1 semantics."""
    report = ReconciliationReport(
        verdict="NOT_MEASURABLE",
        summary="",
        reconciliation_timestamp=datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        candidate_metadata={},
        baseline_metadata={},
        node_reconciliation={},
        triple_reconciliation={},
        discrepancy_ledgers={
            "member_of_discrepancies": [],
            "generic_all_discrepancies": [],
            "other_discrepancies": [],
        },
    )
    try:
        validate_mapping(identity_mapping)
        cand = extract_graph(candidate_data, name=candidate_name)
        report.candidate_metadata = cand.metadata
        base = extract_graph(baseline_data, name=baseline_name, identity_mapping=identity_mapping)
        report.baseline_metadata = base.metadata
    except InputError as exc:
        reason = str(exc)
        report.verdict = "INVALID_INPUT"
        report.summary = f"Input rejected: {reason}"
        report.input_validation = {"status": "invalid", "diagnostics": [reason]}
        report.node_reconciliation = {"status": "invalid_input", "reason": reason}
        report.triple_reconciliation = {"status": "invalid_input", "reason": reason}
        return report

    report.input_validation = {
        "status": "valid",
        "diagnostics": [],
        "candidate": {"duplicate_node_records": cand.duplicate_node_records},
        "baseline": {"duplicate_node_records": base.duplicate_node_records},
    }
    if base.metadata.get("status") == "not_measurable" or not base.nodes:
        reasons = [base.metadata.get("reason", "Baseline has no observed nodes")]
    else:
        reasons = eligibility_reasons(cand, base)
    if reasons:
        reason = "; ".join(reasons)
        report.summary = f"Reconciliation pending: {reason}"
        report.node_reconciliation = {"status": "not_measurable", "reason": reason}
        report.triple_reconciliation = {"status": "not_measurable", "reason": reason}
        return report

    cand_pop = compute_population_summary(cand.nodes)
    base_pop = compute_population_summary(base.nodes)
    cand_ids, base_ids = set(cand.nodes), set(base.nodes)
    overall_nodes = compare_sets(cand_ids, base_ids)
    collected = compare_sets(
        {nid for nid, n in cand.nodes.items() if not n.is_boundary},
        {nid for nid, n in base.nodes.items() if not n.is_boundary},
    )
    boundary = compare_sets(
        {nid for nid, n in cand.nodes.items() if n.is_boundary},
        {nid for nid, n in base.nodes.items() if n.is_boundary},
    )
    by_kind_nodes = {
        kind: asdict(
            compare_sets(
                {nid for nid, n in cand.nodes.items() if n.kind == kind},
                {nid for nid, n in base.nodes.items() if n.kind == kind},
            )
        )
        for kind in sorted(set(cand_pop.by_kind) | set(base_pop.by_kind))
    }
    by_domain_nodes = {
        domain: asdict(
            compare_sets(
                {nid for nid, n in cand.nodes.items() if n.domain == domain},
                {nid for nid, n in base.nodes.items() if n.domain == domain},
            )
        )
        for domain in sorted(set(cand_pop.by_domain) | set(base_pop.by_domain))
    }
    mismatches = {}
    for field_name in ("kind", "domain", "is_boundary"):
        mismatches[field_name] = [
            {
                "id": nid,
                f"candidate_{field_name}": getattr(cand.nodes[nid], field_name),
                f"baseline_{field_name}": getattr(base.nodes[nid], field_name),
            }
            for nid in sorted(cand_ids & base_ids)
            if getattr(cand.nodes[nid], field_name) != getattr(base.nodes[nid], field_name)
        ]

    cand_triples = {t for t in cand.unique_triples if t.kind in M1_RELATIONSHIPS}
    base_triples = {t for t in base.unique_triples if t.kind in M1_RELATIONSHIPS}
    cand_mult = graph_multiplicity(cand, cand_triples)
    base_mult = graph_multiplicity(base, base_triples)

    def triple_key(triple: DirectedTriple) -> str:
        return f"{triple.source}->{triple.kind}->{triple.target}"

    overall_triples = compare_sets(
        {triple_key(t) for t in cand_triples}, {triple_key(t) for t in base_triples}
    )
    by_kind_triples = {}
    for kind in M1_RELATIONSHIPS:
        c_kind = {t for t in cand_triples if t.kind == kind}
        b_kind = {t for t in base_triples if t.kind == kind}
        comparison = compare_sets({triple_key(t) for t in c_kind}, {triple_key(t) for t in b_kind})
        by_kind_triples[kind] = asdict(comparison)
        c_only, b_only = c_kind - b_kind, b_kind - c_kind
        if c_only or b_only:
            entry = {
                "kind": kind,
                "candidate_only": [
                    difference_entry(cand, t) for t in sorted(c_only, key=triple_key)
                ],
                "baseline_only": [
                    difference_entry(base, t) for t in sorted(b_only, key=triple_key)
                ],
                "candidate_count": len(c_kind),
                "baseline_count": len(b_kind),
                "intersection_count": len(c_kind & b_kind),
                "candidate_only_count": len(c_only),
                "baseline_only_count": len(b_only),
            }
            category = {
                "MemberOf": "member_of_discrepancies",
                "GenericAll": "generic_all_discrepancies",
            }.get(kind, "other_discrepancies")
            report.discrepancy_ledgers[category].append(entry)

    has_discrepancy = bool(
        overall_nodes.candidate_only
        or overall_nodes.baseline_only
        or any(mismatches.values())
        or cand_triples != base_triples
    )
    report.verdict = "DISCREPANCY" if has_discrepancy else "MATCH"
    scope_label = "synthetic" if cand.metadata["synthetic"] else "observed exports"
    if has_discrepancy:
        report.summary = (
            f"Structural discrepancies within m1-structural-v1 ({scope_label}): "
            f"nodes cand_only={overall_nodes.candidate_only_count}, "
            f"base_only={overall_nodes.baseline_only_count}; "
            f"kind={len(mismatches['kind'])}, domain={len(mismatches['domain'])}, "
            f"boundary={len(mismatches['is_boundary'])}; "
            f"triples cand_only={overall_triples.candidate_only_count}, "
            f"base_only={overall_triples.baseline_only_count}."
        )
    else:
        report.summary = (
            f"Exact structural match across {cand_pop.total} nodes "
            f"({cand_pop.collected} collected, {cand_pop.boundary} boundary) "
            f"and {cand_mult.unique_triples} unique directed triples "
            f"within m1-structural-v1 ({scope_label}); input declarations validated."
        )
    report.node_reconciliation = {
        "candidate_population": asdict(cand_pop),
        "baseline_population": asdict(base_pop),
        "overall": asdict(overall_nodes),
        "collected": asdict(collected),
        "boundary": asdict(boundary),
        "by_kind": by_kind_nodes,
        "by_domain": by_domain_nodes,
        "boundary_mismatches": mismatches["is_boundary"],
        "kind_mismatches": mismatches["kind"],
        "domain_mismatches": mismatches["domain"],
    }
    out_of_scope = {}
    for side, graph in (("candidate", cand), ("baseline", base)):
        excluded = graph.unique_triples - (cand_triples if side == "candidate" else base_triples)
        out_of_scope[side] = {
            **asdict(graph_multiplicity(graph, excluded)),
            "reason": "Relationship kind is outside the declared common M1 semantics",
            "observations": [difference_entry(graph, t) for t in sorted(excluded, key=triple_key)],
        }
    report.triple_reconciliation = {
        "comparison_scope": COMPARISON_SCOPE,
        "candidate_multiplicity": asdict(cand_mult),
        "baseline_multiplicity": asdict(base_mult),
        "overall": asdict(overall_triples),
        "by_kind": by_kind_triples,
        "out_of_scope": out_of_scope,
        "all_observed": {
            "candidate": asdict(graph_multiplicity(cand, cand.unique_triples)),
            "baseline": asdict(graph_multiplicity(base, base.unique_triples)),
        },
    }
    return report


def render_text_report(report: ReconciliationReport) -> str:
    """Render a human-readable text summary of the reconciliation report."""
    lines = [
        "=" * 78,
        "GRAPH STRUCTURAL RECONCILIATION REPORT",
        "=" * 78,
        f"Timestamp: {report.reconciliation_timestamp}",
        f"Verdict:   {report.verdict}",
        f"Summary:   {report.summary}",
        "",
        "-" * 78,
        "1. NODE POPULATION & IDENTITY RECONCILIATION",
        "-" * 78,
    ]

    nr = report.node_reconciliation
    if nr.get("status") in {"not_measurable", "invalid_input"}:
        lines.append(f"Status: {report.verdict} ({nr.get('reason')})")
    else:
        cand_p = nr["candidate_population"]
        base_p = nr["baseline_population"]
        overall = nr["overall"]
        cand_summary = (
            f"Candidate Nodes: {cand_p['total']} total "
            f"({cand_p['collected']} collected, {cand_p['boundary']} boundary)"
        )
        base_summary = (
            f"Baseline Nodes:  {base_p['total']} total "
            f"({base_p['collected']} collected, {base_p['boundary']} boundary)"
        )
        lines.extend(
            [
                cand_summary,
                base_summary,
                (
                    f"Intersection:    {overall['intersection_count']} "
                    f"(Jaccard: {overall['jaccard_similarity']})"
                ),
                f"Candidate only:  {overall['candidate_only_count']}",
                f"Baseline only:   {overall['baseline_only_count']}",
            ]
        )
        if overall["candidate_only_samples"]:
            lines.append(f"  Candidate only samples: {overall['candidate_only_samples'][:5]}")
        if overall["baseline_only_samples"]:
            lines.append(f"  Baseline only samples:  {overall['baseline_only_samples'][:5]}")

        mismatches = nr.get("boundary_mismatches", [])
        for field_name in ("kind", "domain"):
            field_mismatches = nr.get(f"{field_name}_mismatches", [])
            if field_mismatches:
                lines.append(f"{field_name} mismatches: {len(field_mismatches)}")
                lines.extend(f"  - {item}" for item in field_mismatches[:5])
        if mismatches:
            lines.append(f"Boundary flag mismatches: {len(mismatches)}")
            for m in mismatches[:5]:
                m_line = (
                    f"  - Node {m['id']}: candidate is_boundary={m['candidate_is_boundary']}, "
                    f"baseline is_boundary={m['baseline_is_boundary']}"
                )
                lines.append(m_line)

    lines.extend(
        [
            "",
            "-" * 78,
            "2. DIRECTED TRIPLES & MULTIPLICITY RECONCILIATION",
            "-" * 78,
        ]
    )

    tr = report.triple_reconciliation
    if tr.get("status") in {"not_measurable", "invalid_input"}:
        lines.append(f"Status: {report.verdict} ({tr.get('reason')})")
    else:
        cand_m = tr["candidate_multiplicity"]
        base_m = tr["baseline_multiplicity"]
        overall_t = tr["overall"]
        cand_triples_line = (
            f"Candidate Triples: {cand_m['unique_triples']} unique | "
            f"{cand_m['stored_edges']} stored edges | "
            f"{cand_m['stored_evidence_occurrences']} evidence items "
            f"(ratio: {cand_m['multiplicity_ratio']})"
        )
        base_triples_line = (
            f"Baseline Triples:  {base_m['unique_triples']} unique | "
            f"{base_m['stored_edges']} stored edges "
            f"(ratio: {base_m['multiplicity_ratio']})"
        )
        for side, metrics in (("Candidate", cand_m), ("Baseline", base_m)):
            if metrics["evidence_status"] == "not_measurable":
                lines.append(f"{side} evidence: not_measurable ({metrics['evidence_reason']})")
        lines.extend(
            [
                cand_triples_line,
                base_triples_line,
                (
                    f"Intersection:      {overall_t['intersection_count']} "
                    f"(Jaccard: {overall_t['jaccard_similarity']})"
                ),
                f"Candidate only:    {overall_t['candidate_only_count']}",
                f"Baseline only:     {overall_t['baseline_only_count']}",
                "",
                "Relationship Breakdown (Unique Triples):",
            ]
        )
        for kind, comp in tr.get("by_kind", {}).items():
            lines.append(
                f"  - {kind:<20} Cand: {comp['candidate_count']:<5} "
                f"Base: {comp['baseline_count']:<5} "
                f"Common: {comp['intersection_count']:<5} "
                f"CandOnly: {comp['candidate_only_count']:<5} "
                f"BaseOnly: {comp['baseline_only_count']:<5}"
            )
        for side, observations in tr.get("out_of_scope", {}).items():
            lines.append(
                f"Out of scope ({side}): {observations['stored_edges']} stored edges, "
                f"{observations['unique_triples']} unique triples; {observations['by_kind']}"
            )

    lines.extend(
        [
            "",
            "-" * 78,
            "3. DISCREPANCY LEDGERS (PRIORITIZED)",
            "-" * 78,
        ]
    )
    dl = report.discrepancy_ledgers
    for category, entries in [
        ("MemberOf", dl.get("member_of_discrepancies", [])),
        ("GenericAll", dl.get("generic_all_discrepancies", [])),
        ("Other Kinds", dl.get("other_discrepancies", [])),
    ]:
        if entries:
            lines.append(f"[{category}] Discrepancies:")
            for e in entries:
                if e.get("candidate_only"):
                    c_count = len(e["candidate_only"])
                    samples = [item["triple"] for item in e["candidate_only"][:3]]
                    lines.append(f"  + Candidate only ({c_count}): {samples}")
                if e.get("baseline_only"):
                    b_count = len(e["baseline_only"])
                    samples = [item["triple"] for item in e["baseline_only"][:3]]
                    lines.append(f"  - Baseline only  ({b_count}): {samples}")
        else:
            disposition = (
                "None within declared scope"
                if report.verdict == "MATCH"
                else "No entries; see verdict"
            )
            lines.append(f"[{category}] Discrepancies: {disposition}")

    lines.append("=" * 78)
    return "\n".join(lines)


def load_input_json(path: Path) -> Any:
    """Reject duplicate keys and non-JSON numbers instead of losing records during decoding."""

    def unique_keys(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise InputError(f"duplicate JSON key {key!r}")
            result[key] = value
        return result

    def reject_constant(value):
        raise InputError(f"invalid JSON number {value}")

    return json.loads(
        path.read_text(encoding="utf-8"),
        object_pairs_hook=unique_keys,
        parse_constant=reject_constant,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Reconcile candidate structural graph against a baseline graph export."
    )
    parser.add_argument("--candidate", required=True, type=Path, help="Candidate graph JSON")
    parser.add_argument("--baseline", required=True, type=Path, help="Baseline graph JSON")
    parser.add_argument("--mapping", type=Path, default=None, help="Identity mapping JSON")
    parser.add_argument("--output", type=Path, default=None, help="Output JSON report path")
    parser.add_argument("--format", choices=["text", "json"], default="text", help="Output format")
    parser.add_argument("--summary", action="store_true", help="Print single-line summary")

    args = parser.parse_args(argv)

    if not args.candidate.exists():
        print(f"Error: Candidate file not found: {args.candidate}", file=sys.stderr)
        return 2
    if not args.baseline.exists():
        print(f"Error: Baseline file not found: {args.baseline}", file=sys.stderr)
        return 2

    try:
        candidate_data = load_input_json(args.candidate)
    except Exception as exc:
        print(f"Error reading candidate JSON: {exc}", file=sys.stderr)
        return 2

    try:
        baseline_data = load_input_json(args.baseline)
    except Exception as exc:
        print(f"Error reading baseline JSON: {exc}", file=sys.stderr)
        return 2

    mapping_data = None
    if args.mapping:
        if not args.mapping.exists():
            print(f"Error: Mapping file not found: {args.mapping}", file=sys.stderr)
            return 2
        try:
            mapping_data = load_input_json(args.mapping)
        except Exception as exc:
            print(f"Error reading mapping JSON: {exc}", file=sys.stderr)
            return 2

    report = reconcile_graphs(
        candidate_data,
        baseline_data,
        identity_mapping=mapping_data,
        candidate_name=args.candidate.stem,
        baseline_name=args.baseline.stem,
    )

    if report.verdict == "INVALID_INPUT":
        print(report.summary, file=sys.stderr)

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        report_json = json.dumps(report.to_dict(), indent=2, ensure_ascii=False)
        args.output.write_text(report_json, encoding="utf-8")

    if args.summary:
        print(f"[{report.verdict}] {report.summary}")
    elif args.format == "json":
        print(json.dumps(report.to_dict(), indent=2, ensure_ascii=False))
    else:
        print(render_text_report(report))

    if report.verdict == "MATCH":
        return 0
    if report.verdict in {"NOT_MEASURABLE", "INVALID_INPUT"}:
        return 2
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
