"""Immutable User facts, bound to a canonical graph without extending its contract."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from dataclasses import field as dataclass_field
from types import MappingProxyType

from . import Graph, NormalizedRecord
from .reconciliation import ReconciliationConflictError
from .serialization import deserialize_graph, serialize_graph

FIELDS = MappingProxyType(
    {
        "has_spn": "hasspn",
        "service_principal_names": "serviceprincipalnames",
        "dontreqpreauth": "dontreqpreauth",
    }
)


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def graph_digest(graph: Graph) -> str:
    """Bind facts to complete validated graph contents, including provenance."""
    # Builder and EngineGraph order top-level collections differently. Normalize
    # only these sets of identified records; preserve all attributes/evidence order.
    ordered = dict(graph)
    for key in ("nodes", "edges", "assessments"):
        ordered[key] = sorted(graph[key], key=lambda item: item["id"])
    return (
        "sha256:"
        + hashlib.sha256(
            serialize_graph(ordered, _skip_validation=True).encode("utf-8")
        ).hexdigest()
    )


@dataclass(frozen=True)
class FactEvidence:
    """An occurrence's field value and copied source reference (never LDAP classification)."""

    value_json: str
    provenance: Mapping[str, str]
    classification: str = "collector_normalized"

    def __post_init__(self):
        if self.classification != "collector_normalized":
            raise ValueError("unsupported fact evidence classification")
        source = dict(self.provenance)
        if not all(isinstance(k, str) and isinstance(v, str) for k, v in source.items()):
            raise ValueError("fact provenance must contain string fields")
        if not all(source.get(k) for k in ("raw_file", "collector", "timestamp", "attribute")):
            raise ValueError("fact evidence requires source, time and attribute")
        if not (source.get("record_locator") or source.get("record_id")):
            raise ValueError("fact evidence requires an occurrence locator or record reference")
        json.loads(self.value_json)
        object.__setattr__(self, "provenance", MappingProxyType(source))


@dataclass(frozen=True)
class SnapshotFact:
    subject: str
    name: str
    status: str
    value: bool | tuple[str, ...] | None
    evidence: tuple[FactEvidence, ...] = ()

    def __post_init__(self):
        object.__setattr__(self, "evidence", tuple(self.evidence))


def _resolve(subject: str, name: str, evidence: tuple[FactEvidence, ...]) -> SnapshotFact:
    values = []
    for item in evidence:
        raw = json.loads(item.value_json)
        if name == "service_principal_names":
            if isinstance(raw, list) and all(isinstance(v, str) and v.strip() for v in raw):
                values.append(tuple(raw))
        elif type(raw) is bool:
            values.append(raw)
    # Same narrow precedence as reconciliation: empty cannot erase non-empty;
    # non-empty lists must agree exactly, never silently acquire union semantics.
    nonempty = [v for v in values if v != ()]
    selected = nonempty or values
    if selected and any(v != selected[0] for v in selected):
        raise ReconciliationConflictError(
            f"conflicting snapshot fact {name}; no authoritative rule exists", stage="snapshot"
        )
    return SnapshotFact(
        subject,
        name,
        "known" if selected else "unknown",
        selected[0] if selected else None,
        evidence,
    )


@dataclass(frozen=True)
class SnapshotFacts:
    """Read-only lookup by exact canonical ID. Missing facts remain unknown."""

    snapshot_id: str
    graph_sha256: str
    facts: tuple[SnapshotFact, ...]
    _index: Mapping = dataclass_field(init=False, repr=False, compare=False)

    def __post_init__(self):
        object.__setattr__(self, "facts", tuple(self.facts))
        keys = [(f.subject, f.name) for f in self.facts]
        if len(keys) != len(set(keys)):
            raise ValueError("duplicate snapshot fact keys")
        for fact in self.facts:
            if fact.name not in FIELDS or fact != _resolve(fact.subject, fact.name, fact.evidence):
                raise ValueError("invalid snapshot fact resolution")
        object.__setattr__(
            self, "_index", MappingProxyType({(f.subject, f.name): f for f in self.facts})
        )

    def lookup(self, canonical_id: str, name: str) -> SnapshotFact:
        if name not in FIELDS:
            raise KeyError(f"unsupported snapshot fact: {name}")
        return self._index.get(
            (canonical_id, name), SnapshotFact(canonical_id, name, "unknown", None)
        )

    def validate_binding(self, graph: Graph) -> None:
        if self.snapshot_id != graph["metadata"][
            "snapshot_id"
        ] or self.graph_sha256 != graph_digest(graph):
            raise ValueError("snapshot facts do not match canonical graph")
        users = {n["id"] for n in graph["nodes"] if n["kind"] == "User"}
        for fact in self.facts:
            if fact.subject not in users:
                raise ValueError("snapshot fact subject is not a canonical User")
            for item in fact.evidence:
                if item.provenance.get("snapshot_id", self.snapshot_id) != self.snapshot_id:
                    raise ValueError("fact source belongs to another snapshot")
                reference = item.provenance["raw_file"]
                if reference.startswith("snapshot:"):
                    digest = reference.removeprefix("snapshot:").split("/", 1)[0]
                    if self.snapshot_id != "sha256:" + digest:
                        raise ValueError("fact source reference belongs to another snapshot")
                if item.provenance["attribute"] != "Properties." + FIELDS[fact.name]:
                    raise ValueError("fact field origin does not match its name")


def materialize_snapshot_facts(records: Iterable[NormalizedRecord], graph: Graph) -> SnapshotFacts:
    """Extract only accepted canonical Users, retaining each contributing occurrence.

    Call after normalize_records/reconciliation and graph materialization. Malformed
    optional fields are unknown evidence, never bool-coerced or inferred. Reconciliation
    conflicts remain fatal before extraction. enabled remains on the canonical node.
    """
    users = {n["id"] for n in graph["nodes"] if n["kind"] == "User"}
    buckets: dict[tuple[str, str], dict[str, FactEvidence]] = {}
    snapshot_id = graph["metadata"]["snapshot_id"]
    for record in records:
        if record.kind != "User" or record.id not in users:
            continue
        sources = record.raw_representations or (record.raw,)
        if not record.raw_representations and len(record.raw_provenance) > 1:
            raise ValueError("reconciled field origins require raw_representations")
        for source in sources:
            properties = source.data.get("Properties", {})
            if not isinstance(properties, Mapping):
                continue
            for name, field in FIELDS.items():
                if field not in properties:
                    continue
                provenance = dict(source.provenance)
                provenance.setdefault("snapshot_id", snapshot_id)
                provenance["attribute"] = "Properties." + field
                item = FactEvidence(_json(properties[field]), provenance)
                buckets.setdefault((record.id, name), {})[_json([item.value_json, provenance])] = (
                    item
                )
    facts = SnapshotFacts(
        snapshot_id,
        graph_digest(graph),
        tuple(
            _resolve(subject, name, tuple(bucket[k] for k in sorted(bucket)))
            for (subject, name), bucket in sorted(buckets.items())
        ),
    )
    facts.validate_binding(graph)
    return facts


def serialize_snapshot(graph: Graph, facts: SnapshotFacts) -> str:
    """Single minimal transport envelope; the enclosed Graph stays contract 1.3.0."""
    facts.validate_binding(graph)
    return _json(
        {
            "version": "snapshot-facts/1",
            "graph": graph,
            "snapshot_id": facts.snapshot_id,
            "graph_sha256": facts.graph_sha256,
            "facts": [
                {
                    "subject": f.subject,
                    "name": f.name,
                    "evidence": [
                        {
                            "value_json": e.value_json,
                            "provenance": dict(e.provenance),
                            "classification": e.classification,
                        }
                        for e in f.evidence
                    ],
                }
                for f in facts.facts
            ],
        }
    )


def deserialize_snapshot(payload: str) -> tuple[Graph, SnapshotFacts]:
    """Validate graph binding and re-resolve evidence on load; no cached value authority."""
    data = json.loads(payload)
    if (
        not isinstance(data, dict)
        or set(data) != {"version", "graph", "snapshot_id", "graph_sha256", "facts"}
        or data["version"] != "snapshot-facts/1"
    ):
        raise ValueError("unsupported snapshot envelope")
    graph = deserialize_graph(data["graph"])
    if not isinstance(data["facts"], list) or any(
        not isinstance(f, dict)
        or set(f) != {"subject", "name", "evidence"}
        or not isinstance(f["subject"], str)
        or f["name"] not in FIELDS
        or not isinstance(f["evidence"], list)
        for f in data["facts"]
    ):
        raise ValueError("invalid snapshot fact entries")
    facts = SnapshotFacts(
        data["snapshot_id"],
        data["graph_sha256"],
        tuple(
            _resolve(f["subject"], f["name"], tuple(FactEvidence(**e) for e in f["evidence"]))
            for f in data["facts"]
        ),
    )
    facts.validate_binding(graph)
    return graph, facts


__all__ = [
    "FactEvidence",
    "SnapshotFact",
    "SnapshotFacts",
    "materialize_snapshot_facts",
    "serialize_snapshot",
    "deserialize_snapshot",
]
