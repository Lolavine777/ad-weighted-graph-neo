"""Contracts for the AD export → normalized records → graph pipeline.

Collector-specific implementations of :class:`RawDataLoader` retain complete
BloodHound-python or SharpHound records and raw provenance. A :class:`Normalizer`
resolves canonical identities without discarding collector evidence; a
:class:`GraphBuilder` assembles and validates the graph against configs/contract.yml.
These abstract interfaces do not parse exports; the concrete builder integrates
the host-access inference layer after normalization.

Stages share record-level :class:`ErrorPolicy` semantics through ``process_records``:
FAIL_FAST raises the original RecordError (the default), SKIP_RECORD discards the
record silently, and LOG_WARNING discards it with a contextual warning. File I/O,
invalid JSON envelopes, unsupported formats/contracts, and programming errors are
fatal under every policy. Adapters must distinguish these from malformed records.
"""

import logging
from abc import ABC, abstractmethod
from collections.abc import Callable, Iterable, Iterator, Mapping
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Literal, NotRequired, TypedDict

type JSONValue = None | bool | int | float | str | list[JSONValue] | dict[str, JSONValue]
type RecordData = Mapping[str, JSONValue]

__all__ = [
    "Assessment",
    "AssessmentStatus",
    "ErrorPolicy",
    "Graph",
    "GraphBuilder",
    "DirectGraphBuilder",
    "GraphEdge",
    "CanonicalDerivationStep",
    "DerivationCondition",
    "DerivationPath",
    "DerivedLineage",
    "GraphMetadata",
    "GraphNode",
    "JSONValue",
    "NormalizedRecord",
    "Normalizer",
    "IdentityNormalizer",
    "RecordNormalizer",
    "Provenance",
    "RawDataLoader",
    "RawRecord",
    "RecordData",
    "RecordError",
    "RawProvenance",
    "RawRepresentation",
    "ReconciledRecord",
    "ReconciliationConflictError",
    "RepresentationKind",
    "DuplicateCause",
    "EvidenceLineage",
    "TimeProvenancePolicy",
    "TimeProvenanceStatus",
    "TimeProvenanceStatusLiteral",
    "reconcile_raw_records",
    "ExecutionIdentity",
    "ManifestRawDataLoader",
    "SnapshotRawDataLoader",
    "process_records",
    "PrimitiveStatus",
    "InferenceStatus",
    "EvidenceSource",
    "PrimitiveEvidence",
    "DerivationStep",
    "HostAccessResult",
    "evaluate_gpo_access",
    "evaluate_host_access",
    "evaluate_local_group_membership",
    "evaluate_user_right",
    "resolve_effective_membership",
    "serialize_graph",
    "deserialize_graph",
]

_LOGGER = logging.getLogger(__name__)


class ErrorPolicy(StrEnum):
    """Action on a malformed record, never on a whole-file or system failure."""

    SKIP_RECORD = "skip_record"
    FAIL_FAST = "fail_fast"
    LOG_WARNING = "log_warning"


class AssessmentStatus(StrEnum):
    """A non-traversable outcome kept outside ``Graph.edges``."""

    UNKNOWN = "unknown"
    INFERRED = "inferred"
    REJECTED = "rejected"


class TimeProvenanceStatus(StrEnum):
    """Classification of how a collection timestamp was established."""

    OBSERVED = "observed"
    EXTERNALLY_EVIDENCED = "externally_evidenced"
    DERIVED = "derived"
    ASSUMED = "assumed"


TimeProvenanceStatusLiteral = Literal[
    "observed",
    "externally_evidenced",
    "derived",
    "assumed",
]
CanonicalTimeStatusLiteral = Literal[
    "observed",
    "externally_evidenced",
    "derived",
    "assumed",
    "unknown_legacy",
]


class RawProvenance(TypedDict):
    """Source reference retained by the loader before evidence classification.

    Manifest-backed raw_file values use snapshot:<digest>/<relative_path> from
    src.data.manifest.raw_file_reference; resolve against a verified local registry.
    Unknown manifest collection times cannot supply the required edge timestamp
    unless resolved by an explicit TimeProvenancePolicy.
    """

    raw_file: str
    collector: str
    timestamp: str
    record_id: NotRequired[str]
    attribute: NotRequired[str]
    snapshot_id: NotRequired[str]
    record_locator: NotRequired[str]
    time_provenance: NotRequired[TimeProvenanceStatusLiteral]
    time_provenance_reason: NotRequired[str]
    schema_version: NotRequired[str]  # Raw collector envelope version; not graph evidence.


class Provenance(TypedDict):
    """Graph evidence reference with its normalization/build classification.

    Adheres strictly to the canonical provenance schema:
    required: raw_file, collector, timestamp, evidence_type, timestamp_status
    optional: record_id, attribute, time_provenance_reason
    """

    raw_file: str
    collector: str
    timestamp: str
    evidence_type: str
    timestamp_status: CanonicalTimeStatusLiteral
    time_provenance_reason: NotRequired[str]
    record_id: NotRequired[str]
    attribute: NotRequired[str]


@dataclass(frozen=True)
class EvidenceLineage:
    """Raw occurrence provenance supporting one materialized evidence item."""

    field: str
    item_key: str
    item: JSONValue
    provenance: tuple[RawProvenance, ...]


@dataclass(frozen=True)
class RawRecord:
    """One complete collector record plus its source reference and object kind.

    ``data`` retains all attributes, including AllowedToDelegate, collection
    status, group membership and host/GPO scope. Empty fields from one collector
    must not erase evidence from another. Wrapping does not validate or copy data.
    """

    kind: str
    data: RecordData
    provenance: RawProvenance


@dataclass(frozen=True)
class NormalizedRecord:
    """Canonical identity and attributes with raw evidence retained for graph building.

    ``id`` uses an unambiguous SID, a stable scoped SID or a lowercase GUID.
    ``attributes`` holds normalized node fields; ``raw`` retains merged relationship
    evidence, ``raw_provenance`` retains every source occurrence, and
    ``evidence_lineage`` maps each materialized relationship item to its supporting
    occurrence provenance. ``raw_representations`` retains each contributing
    occurrence for field-level snapshot facts; a merged value alone cannot identify
    which source actually observed it.
    """

    id: str
    kind: str
    attributes: RecordData
    raw: RawRecord
    raw_provenance: tuple[RawProvenance, ...] = ()
    evidence_lineage: tuple[EvidenceLineage, ...] = ()
    # Retain field-level origins after reconciliation, not just the first source.
    raw_representations: tuple[RawRecord, ...] = ()


class Assessment(TypedDict):
    """An unknown, inferred, or rejected record outside the traversable graph."""

    id: str
    status: AssessmentStatus
    reason: str
    provenance: list[Provenance]
    subject: NotRequired[str]
    target: NotRequired[str]
    kind: NotRequired[str]
    record_id: NotRequired[str]


class GraphMetadata(TypedDict):
    """Required metadata identifying the graph snapshot, profile, and producer."""

    contract_version: str
    weight_profile: str
    snapshot_id: str
    created_at: str
    code_version: str
    synthetic: NotRequired[bool]
    description: NotRequired[str]


class GraphNode(TypedDict):
    """A structural graph node using the canonical M2 node fields."""

    id: str
    kind: str
    label: str
    domain: str
    is_boundary: bool
    enabled: NotRequired[bool]
    admincount: NotRequired[bool | int]
    distinguishedname: NotRequired[str]


class CanonicalDerivationStep(TypedDict):
    """One ordered structural step in a derived-edge explanation."""

    order: int
    operation: str
    evidence_refs: list[str]
    source: NotRequired[str]
    target: NotRequired[str]


class DerivationCondition(TypedDict):
    """One named predicate and its direct evidence references for a path."""

    predicate: str
    evidence_refs: list[str]


class DerivationPath(TypedDict):
    """One complete, ordered derivation path for a logical edge."""

    steps: list[CanonicalDerivationStep]
    conditions: NotRequired[list[DerivationCondition]]


class DerivedLineage(TypedDict):
    """Versioned canonical lineage; raw provenance remains on the edge."""

    version: str
    kind: str
    paths: list[DerivationPath]


class GraphEdge(TypedDict):
    """A traversable edge with profile weight and positive provenance."""

    id: str
    source: str
    target: str
    kind: str
    weight: float
    provenance: list[Provenance]
    derivation: NotRequired[DerivedLineage]


class Graph(TypedDict):
    """Graph JSON boundary; implementations validate fields using the shared contract."""

    nodes: list[GraphNode]
    edges: list[GraphEdge]
    metadata: GraphMetadata
    assessments: list[Assessment]


class RecordError(ValueError):
    """Recoverable record failure with a safe diagnostic, never a raw record dump."""

    def __init__(self, message: str, *, stage: str, record_id: str | None = None) -> None:
        self.stage = stage
        self.record_id = record_id
        context = stage if record_id is None else f"{stage} record {record_id}"
        super().__init__(f"{context}: {message}")


def process_records[InputT, OutputT](
    records: Iterable[InputT],
    transform: Callable[[InputT], OutputT],
    *,
    error_policy: ErrorPolicy = ErrorPolicy.FAIL_FAST,
    logger: logging.Logger | None = None,
) -> Iterator[OutputT]:
    """Transform records lazily, catching only RecordError from each transformation.

    Validate policy before consuming input. Source iteration errors always propagate:
    a broken source cannot be safely resumed. ``transform`` must validate before
    mutating shared graph state so skipped records cannot leave partial changes.
    Warning messages use RecordError context; this helper never logs input payloads.
    """
    if not isinstance(error_policy, ErrorPolicy):
        raise TypeError("error_policy must be an ErrorPolicy")

    def iterate() -> Iterator[OutputT]:
        for record in records:
            try:
                result = transform(record)
            except RecordError as error:
                if error_policy is ErrorPolicy.FAIL_FAST:
                    raise
                if error_policy is ErrorPolicy.LOG_WARNING:
                    (logger if logger is not None else _LOGGER).warning("%s", error)
            else:
                yield result

    return iterate()


class RawDataLoader(ABC):
    """Collector adapter responsible for file/envelope validation and raw provenance.

    Implementations support collector versions explicitly, preserve all attributes,
    and apply error_policy only to malformed individual records. Missing collection
    timestamps or scope must not be replaced with invented evidence.
    """

    @abstractmethod
    def load(
        self, source: Path, *, error_policy: ErrorPolicy = ErrorPolicy.FAIL_FAST
    ) -> Iterator[RawRecord]:
        """Yield records from an export; unreadable/invalid export envelopes are fatal."""
        raise NotImplementedError


class Normalizer(ABC):
    """Resolve identities and node attributes while retaining raw relationship evidence.

    Preserve domain/host scope for namespace-relative SIDs. Reject missing stable
    scope via RecordError; never strip prefixes, infer IDs from labels, or generate
    random UUIDs. Preserve absent optional fields rather than inventing defaults.
    """

    @abstractmethod
    def normalize(self, record: RawRecord) -> NormalizedRecord:
        """Normalize one record or raise RecordError; use process_records for a batch."""
        raise NotImplementedError


class GraphBuilder(ABC):
    """Assemble and validate the canonical structural graph.

    Concrete builders may implement direct structural relationships, while
    host-access inference and derived lineage belong to later layers/issues.
    """

    @abstractmethod
    def build(
        self,
        records: Iterable[NormalizedRecord],
        *,
        error_policy: ErrorPolicy = ErrorPolicy.FAIL_FAST,
    ) -> Graph:
        """Build a graph atomically per record; validate the complete graph before return.

        Collect nodes before resolving relationships so input order does not create
        dangling edges. Merge unique evidence for identical source/target/kind;
        preserve parallel edges of different kinds and stable SHA-256 edge IDs.
        """
        raise NotImplementedError


from .builder import DirectGraphBuilder  # noqa: E402
from .inference import (  # noqa: E402
    DerivationStep,
    EvidenceSource,
    HostAccessResult,
    InferenceStatus,
    PrimitiveEvidence,
    PrimitiveStatus,
    evaluate_gpo_access,
    evaluate_host_access,
    evaluate_local_group_membership,
    evaluate_user_right,
    resolve_effective_membership,
)
from .loader import (  # noqa: E402  # imported after the abstract interface definitions
    ExecutionIdentity,
    ManifestRawDataLoader,
    SnapshotRawDataLoader,
    TimeProvenancePolicy,
)
from .normalizer import IdentityNormalizer, RecordNormalizer  # noqa: E402
from .reconciliation import (  # noqa: E402
    DuplicateCause,
    RawRepresentation,
    ReconciledRecord,
    ReconciliationConflictError,
    RepresentationKind,
    reconcile_raw_records,
)
from .serialization import deserialize_graph, serialize_graph  # noqa: E402
