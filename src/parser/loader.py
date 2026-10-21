"""Manifest-bound JSON loaders for the raw parser boundary."""

from __future__ import annotations

import json
import re
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import NotRequired, TypedDict, cast

from src.data import manifest as snapshot_manifest

from . import (
    ErrorPolicy,
    RawDataLoader,
    RawRecord,
    RecordData,
    RecordError,
    TimeProvenanceStatus,
    TimeProvenanceStatusLiteral,
)
from .identity_fields import lookup_raw_identifier

DEFAULT_CONTRACT_VERSION = "1.3.0"
DEFAULT_PARSER_VERSION = "0.1.0"

TIMESTAMP_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


def validate_utc_timestamp(timestamp: str) -> str:
    """Validate that a timestamp matches UTC ISO 8601 regex and is a valid calendar datetime."""
    if not isinstance(timestamp, str) or not TIMESTAMP_PATTERN.match(timestamp):
        raise ValueError(f"timestamp must match UTC ISO 8601 format: {timestamp!r}")
    try:
        datetime.strptime(timestamp, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError as exc:
        raise ValueError(f"invalid calendar date/time in timestamp: {timestamp!r}") from exc
    return timestamp


@dataclass(frozen=True)
class TimeProvenancePolicy:
    """Explicit policy for resolving timestamps when collection time is unknown.

    When manifest collected_at is null, loader callers must explicitly provide
    an approved policy. Silent fallback (such as system clock, file mtime, git
    commit timestamp, or arbitrary epoch) is strictly forbidden.
    """

    timestamp: str
    status: TimeProvenanceStatus = TimeProvenanceStatus.ASSUMED
    reason: str | None = None

    def __post_init__(self) -> None:
        validate_utc_timestamp(self.timestamp)
        raw_status = self.status
        if isinstance(raw_status, str):
            normalized = raw_status.strip().casefold()
            if normalized == TimeProvenanceStatus.OBSERVED.value:
                raise ValueError("time provenance policy status cannot masquerade as 'observed'")
            try:
                object.__setattr__(self, "status", TimeProvenanceStatus(raw_status.strip()))
            except ValueError as exc:
                raise ValueError(f"unsupported time provenance status: {raw_status!r}") from exc
        elif isinstance(raw_status, TimeProvenanceStatus):
            if raw_status == TimeProvenanceStatus.OBSERVED:
                raise ValueError("time provenance policy status cannot masquerade as 'observed'")
        else:
            raise TypeError(
                f"status must be a TimeProvenanceStatus or valid string, got {type(raw_status)}"
            )

        has_valid_reason = isinstance(self.reason, str) and bool(self.reason.strip())
        if (
            self.status
            in {
                TimeProvenanceStatus.EXTERNALLY_EVIDENCED,
                TimeProvenanceStatus.DERIVED,
            }
            and not has_valid_reason
        ):
            raise ValueError(
                f"time provenance status {self.status.value!r} requires a non-empty "
                "reason or evidence reference"
            )

        if self.reason is not None:
            if not isinstance(self.reason, str) or not self.reason.strip():
                raise ValueError("reason must be a non-empty string if specified")
            object.__setattr__(self, "reason", self.reason.strip())

    @property
    def identity_token(self) -> str:
        """Deterministic audit token incorporating policy parameters."""
        token = f"fixed:{self.status.value}:{self.timestamp}"
        if self.reason:
            token = f"{token}:{self.reason}"
        return token

    @classmethod
    def fixed(
        cls,
        timestamp: str,
        *,
        status: TimeProvenanceStatus = TimeProvenanceStatus.ASSUMED,
        reason: str | None = None,
    ) -> TimeProvenancePolicy:
        """Use an explicit UTC timestamp for unknown collection times."""
        return cls(timestamp=timestamp, status=status, reason=reason)

    @classmethod
    def assumed(cls, timestamp: str, *, reason: str | None = None) -> TimeProvenancePolicy:
        """Shorthand for fixed policy with ASSUMED status."""
        return cls(timestamp=timestamp, status=TimeProvenanceStatus.ASSUMED, reason=reason)

    @classmethod
    def externally_evidenced(cls, timestamp: str, *, reason: str) -> TimeProvenancePolicy:
        """Use an explicit UTC timestamp verified by external evidence (audit reason required)."""
        return cls(
            timestamp=timestamp,
            status=TimeProvenanceStatus.EXTERNALLY_EVIDENCED,
            reason=reason,
        )

    @classmethod
    def derived(cls, timestamp: str, *, reason: str) -> TimeProvenancePolicy:
        """Use an explicit UTC timestamp derived from source context (audit reason required)."""
        return cls(
            timestamp=timestamp,
            status=TimeProvenanceStatus.DERIVED,
            reason=reason,
        )

    def resolve(
        self, entry: Mapping[str, object], relative: str
    ) -> tuple[str, TimeProvenanceStatusLiteral]:
        """Resolve (timestamp, status) for an envelope."""
        return self.timestamp, cast(TimeProvenanceStatusLiteral, self.status.value)


class ExecutionIdentity(TypedDict):
    """Identity of the snapshot and code that produced raw records."""

    snapshot_id: str
    dataset_id: str
    collector_name: str
    collector_version: str | None
    contract_version: str
    parser_version: str
    time_policy: NotRequired[str]


class _Envelope(TypedDict):
    meta: Mapping[str, object]
    data: list[object]
    locator_key: str


class ManifestRawDataLoader(RawDataLoader):
    """Load JSON collector envelopes from a verified immutable snapshot.

    The manifest is accepted as an already-loaded mapping or as a path to a
    manifest JSON file.  Snapshot verification and envelope preflight happen
    before the first record can be yielded.  Non-JSON files may be present in a
    manifest and are still included in integrity verification; only JSON export
    envelopes are parser inputs.
    """

    def __init__(
        self,
        manifest: Mapping[str, object] | str | Path,
        *,
        time_policy: TimeProvenancePolicy | None = None,
        contract_version: str = DEFAULT_CONTRACT_VERSION,
        parser_version: str = DEFAULT_PARSER_VERSION,
    ) -> None:
        if isinstance(manifest, (str, Path)):
            self._manifest_source: Mapping[str, object] | Path = Path(manifest)
            self._manifest: dict | None = None
        elif isinstance(manifest, Mapping):
            self._manifest_source = manifest
            self._manifest = dict(manifest)
        else:
            raise TypeError("manifest must be a mapping or Path")
        if time_policy is not None and not isinstance(time_policy, TimeProvenancePolicy):
            raise TypeError("time_policy must be a TimeProvenancePolicy or None")
        if not isinstance(contract_version, str) or not contract_version.strip():
            raise ValueError("contract_version must be a non-empty string")
        if not isinstance(parser_version, str) or not parser_version.strip():
            raise ValueError("parser_version must be a non-empty string")
        self.time_policy = time_policy
        self.contract_version = contract_version
        self.parser_version = parser_version

    @property
    def execution_identity(self) -> ExecutionIdentity:
        """Return stable execution metadata without exposing a local path."""
        manifest = self._validated_manifest()
        collector = manifest["collector"]
        identity: ExecutionIdentity = {
            "snapshot_id": manifest["snapshot_id"],
            "dataset_id": manifest["dataset_id"],
            "collector_name": collector["name"],
            "collector_version": collector["version"],
            "contract_version": self.contract_version,
            "parser_version": self.parser_version,
        }
        if self.time_policy is not None:
            identity["time_policy"] = self.time_policy.identity_token
        return identity

    def load(
        self, source: Path, *, error_policy: ErrorPolicy = ErrorPolicy.FAIL_FAST
    ) -> Iterator[RawRecord]:
        """Verify the complete snapshot, preflight envelopes, then yield raw records."""
        if not isinstance(error_policy, ErrorPolicy):
            raise TypeError("error_policy must be an ErrorPolicy")

        def iterate() -> Iterator[RawRecord]:
            manifest = self._validated_manifest()
            discrepancies = snapshot_manifest.verify_manifest(source, manifest)
            if discrepancies:
                details = ", ".join(
                    f"{issue['status']}:{issue['relative_path']}" for issue in discrepancies
                )
                raise snapshot_manifest.ManifestError(
                    f"snapshot does not match manifest: {details}"
                )

            envelopes = self._preflight_envelopes(source, manifest)
            yield from self._records(envelopes, manifest, error_policy)

        return iterate()

    def _validated_manifest(self) -> dict:
        if self._manifest is None:
            self._manifest = snapshot_manifest.load_manifest(self._manifest_source)
        else:
            self._manifest = snapshot_manifest.validate_manifest(self._manifest)
        return self._manifest

    def _preflight_envelopes(
        self, source: Path, manifest: dict
    ) -> list[tuple[str, _Envelope, dict]]:
        json_entries = [
            entry for entry in manifest["files"] if entry["relative_path"].lower().endswith(".json")
        ]
        if not json_entries:
            raise snapshot_manifest.ManifestError("snapshot contains no JSON export envelopes")

        envelopes = []
        for entry in json_entries:
            relative = entry["relative_path"]
            metadata = self._file_metadata(manifest, entry, relative)
            reference = snapshot_manifest.raw_file_reference(manifest, relative)
            payload = snapshot_manifest.read_verified_snapshot_file(source, manifest, reference)
            payload = self._read_json(payload, relative)
            envelope = self._validate_envelope(payload, relative)
            envelopes.append((relative, envelope, metadata))
        return envelopes

    @staticmethod
    def _read_json(payload: bytes, relative: str) -> object:
        def unique_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
            result: dict[str, object] = {}
            for key, value in pairs:
                if key in result:
                    raise ValueError("duplicate JSON key")
                result[key] = value
            return result

        def reject_constant(value: str) -> None:
            raise ValueError(f"invalid JSON constant {value}")

        try:
            return json.loads(
                payload.removeprefix(b"\xef\xbb\xbf"),
                object_pairs_hook=unique_keys,
                parse_constant=reject_constant,
            )
        except (OSError, UnicodeError, ValueError, json.JSONDecodeError, RecursionError) as exc:
            raise snapshot_manifest.ManifestError(f"invalid JSON envelope: {relative}") from exc

    @staticmethod
    def _validate_envelope(payload: object, relative: str) -> _Envelope:
        if not isinstance(payload, dict) or "meta" not in payload:
            raise snapshot_manifest.ManifestError(f"malformed JSON envelope: {relative}")
        meta = payload["meta"]
        if (
            not isinstance(meta, Mapping)
            or not isinstance(meta.get("type"), str)
            or not meta["type"].strip()
        ):
            raise snapshot_manifest.ManifestError(f"empty or malformed JSON envelope: {relative}")

        kind = meta["type"].strip()
        locator_key: str
        if "data" in payload:
            locator_key = "data"
            data = payload["data"]
        elif kind in payload:
            locator_key = kind
            data = payload[kind]
        else:
            raise snapshot_manifest.ManifestError(f"malformed JSON envelope: {relative}")

        if not isinstance(data, list) or not data:
            raise snapshot_manifest.ManifestError(f"empty or malformed JSON envelope: {relative}")
        return {"meta": meta, "data": data, "locator_key": locator_key}

    def _file_metadata(self, manifest: dict, entry: dict, relative: str) -> dict:
        collector = entry.get("collector", manifest["collector"])
        timestamp = entry.get("collected_at", manifest["collected_at"])
        time_provenance: TimeProvenanceStatusLiteral
        time_provenance_reason: str | None = None
        if timestamp is not None:
            try:
                validate_utc_timestamp(timestamp)
            except ValueError as exc:
                raise snapshot_manifest.ManifestError(
                    f"invalid collection timestamp for JSON envelope: {relative}"
                ) from exc
            time_provenance = TimeProvenanceStatus.OBSERVED.value
        else:
            if self.time_policy is None:
                raise snapshot_manifest.ManifestError(
                    f"missing collection timestamp for JSON envelope: {relative}"
                )
            timestamp, time_provenance = self.time_policy.resolve(entry, relative)
            time_provenance_reason = self.time_policy.reason
        result = {
            "collector": collector,
            "timestamp": timestamp,
            "time_provenance": time_provenance,
        }
        if time_provenance_reason is not None:
            result["time_provenance_reason"] = time_provenance_reason
        return result

    def _records(
        self,
        envelopes: list[tuple[str, _Envelope, dict]],
        manifest: dict,
        error_policy: ErrorPolicy,
    ) -> Iterator[RawRecord]:
        for relative, envelope, metadata in envelopes:
            kind = envelope["meta"]["type"]
            collector = metadata["collector"]
            collector_ref = collector["name"]
            if collector["version"] is not None:
                collector_ref = f"{collector_ref}/{collector['version']}"
            raw_file = snapshot_manifest.raw_file_reference(self._validated_manifest(), relative)
            locator_key = envelope.get("locator_key", "data")
            for index, value in enumerate(envelope["data"]):
                try:
                    if not isinstance(value, Mapping):
                        raise RecordError(
                            "record must be a JSON object", stage="load", record_id=str(index)
                        )
                    data: RecordData = value
                except RecordError:
                    if error_policy is ErrorPolicy.FAIL_FAST:
                        raise
                    if error_policy is ErrorPolicy.LOG_WARNING:
                        # Record-level diagnostics intentionally omit the raw payload.
                        import logging

                        logging.getLogger(__name__).warning(
                            "load record %s: record must be a JSON object", index
                        )
                    continue

                provenance = {
                    "raw_file": raw_file,
                    "collector": collector_ref,
                    "timestamp": metadata["timestamp"],
                    "snapshot_id": manifest["snapshot_id"],
                    # The record ID identifies the logical object, while the
                    # locator identifies this occurrence in the envelope.
                    "record_locator": f"#/{locator_key}/{index}",
                    "time_provenance": metadata["time_provenance"],
                }
                envelope_version = envelope["meta"].get("version")
                if envelope_version == 3 and not isinstance(envelope_version, bool):
                    provenance["schema_version"] = "3"
                if "time_provenance_reason" in metadata:
                    provenance["time_provenance_reason"] = metadata["time_provenance_reason"]
                record_id = lookup_raw_identifier(data)
                if isinstance(record_id, str) and record_id.strip():
                    provenance["record_id"] = record_id.strip()
                yield RawRecord(kind=kind, data=data, provenance=provenance)


SnapshotRawDataLoader = ManifestRawDataLoader

__all__ = [
    "DEFAULT_CONTRACT_VERSION",
    "DEFAULT_PARSER_VERSION",
    "ExecutionIdentity",
    "ManifestRawDataLoader",
    "SnapshotRawDataLoader",
    "TimeProvenancePolicy",
]
