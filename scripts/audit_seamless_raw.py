"""Raw-first, manifest-backed field archaeology for the SEAMLESS snapshot.

This module deliberately inventories JSON structure without importing the parser,
graph builder, or attack-semantics code.  It records observations about raw bytes;
it does not assign canonical relationship meaning to similarly named fields.
"""

# The markdown renderer contains deliberately long prose/table header literals.
# Keep ordinary Python linting while exempting only line-length diagnostics here.
# ruff: noqa: E501

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from collections import Counter, defaultdict
from collections.abc import Iterable
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.data.manifest import (  # noqa: E402
    load_manifest,
    raw_file_reference,
    read_verified_snapshot_file,
    verify_manifest,
)

DEFAULT_RAW_DIR = ROOT / "data" / "raw" / "SEAMLESS"
DEFAULT_MANIFEST = ROOT / "data" / "samples" / "manifests" / "seamless-raw-v1.json"
DEFAULT_OUTPUT = ROOT / "reports" / "generated" / "seamless-raw-field-inventory.json"
DEFAULT_MARKDOWN_OUTPUT = ROOT / "docs" / "research" / "seamless-raw-field-audit.md"

FILE_KINDS = {
    "users": "User",
    "groups": "Group",
    "computers": "Computer",
    "ous": "OU",
    "gpos": "GPO",
    "domains": "Domain",
}

# These are safe to emit as categorical values because they describe schema or
# relationship labels, not identities.  All other strings become shapes only.
SAFE_CATEGORY_FIELDS = {
    "acetype",
    "membertype",
    "principaltype",
    "rightname",
    "trustdirection",
    "trusttype",
}

REFERENCE_COLLECTIONS = {
    "allowedtoact",
    "allowedtodelegate",
    "aces",
    "childous",
    "computers",
    "groups",
    "links",
    "localadmins",
    "members",
    "privilegedsessions",
    "psremoteusers",
    "registrysessions",
    "remotedesktopusers",
    "sessions",
    "trusts",
    "users",
}

REFERENCE_TERMINALS = {
    "computerid",
    "domainid",
    "gpoid",
    "memberid",
    "objectid",
    "objectidentifier",
    "ouid",
    "primarygroupsid",
    "principalsid",
    "sid",
    "targetid",
    "userid",
}

NON_REFERENCE_TERMINALS = SAFE_CATEGORY_FIELDS | {
    "acetype",
    "collected",
    "failurecause",
    "failurereason",
    "method",
    "methods",
    "status",
}

SID_RE = re.compile(r"^S-\d(?:-\d+)+$", re.I)
GUID_RE = re.compile(r"^\{?[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\}?$", re.I)
TIMESTAMP_RE = re.compile(r"^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:")
DN_RE = re.compile(r"^(?:CN|OU|DC|O|UID)=", re.I)


def _json_type(value: Any) -> str:
    """Return a JSON type with bool kept separate from integer."""
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    return type(value).__name__


def _terminal(path: str) -> str:
    return path.rsplit(".", 1)[-1].removesuffix("[]").lower()


def _path_parts(path: str) -> list[str]:
    return [part.removesuffix("[]").lower() for part in path.split(".")]


def _is_empty(value: Any) -> bool:
    # False and zero are observed values, not empty values.
    return isinstance(value, (str, list, dict)) and len(value) == 0


def _safe_shape(value: Any, path: str = "") -> str:
    """Return a value shape without copying identity-bearing string content."""
    if value is None:
        return "null"
    if isinstance(value, bool):
        return f"boolean: {str(value).lower()}"
    if isinstance(value, int) and not isinstance(value, bool):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        keys = ", ".join(sorted(str(key) for key in value))
        return f"object keys: [{keys}]"
    if not isinstance(value, str):
        return _json_type(value)

    field = _terminal(path)
    if field in SAFE_CATEGORY_FIELDS and value:
        return f"category: {value}"
    if field in SAFE_CATEGORY_FIELDS and not value:
        return "empty string"
    if SID_RE.fullmatch(value):
        return "SID-like string: S-<redacted>"
    if GUID_RE.fullmatch(value):
        return "GUID-like string"
    if DN_RE.match(value):
        return "DN-like string: <redacted distinguished name>"
    if TIMESTAMP_RE.match(value):
        return "timestamp-like string"
    if "@" in value or "\\" in value or "." in value:
        return "composite/domain-like string: <redacted>"
    return "string"


def _element_shape(value: Any) -> str:
    if isinstance(value, dict):
        return "object keys: [" + ", ".join(sorted(str(key) for key in value)) + "]"
    return _json_type(value)


def _walk_fields(value: Any, path: str) -> Iterable[tuple[str, Any]]:
    """Yield every observed field path, including array element paths."""
    yield path, value
    if isinstance(value, dict):
        for key in sorted(value, key=str):
            child = f"{path}.{key}" if path else str(key)
            yield from _walk_fields(value[key], child)
    elif isinstance(value, list):
        child = f"{path}[]"
        for item in value:
            yield from _walk_fields(item, child)


def _new_field_stat(records_examined: int) -> dict[str, Any]:
    return {
        "records_examined": records_examined,
        "present_roots": set(),
        "observed_types": set(),
        "occurrence_count": 0,
        "null_count": 0,
        "empty_count": 0,
        "non_empty_count": 0,
        "representative_shapes": Counter(),
        "categorical_values": Counter(),
        "array_lengths": [],
        "element_shapes": Counter(),
    }


def _record_field_observations(records: list[Any], object_kind: str) -> list[dict[str, Any]]:
    stats: dict[str, dict[str, Any]] = {}
    for record_index, record in enumerate(records):
        if not isinstance(record, dict):
            continue
        for path, value in _walk_fields(record, ""):
            if not path:
                continue
            stat = stats.setdefault(path, _new_field_stat(len(records)))
            stat["present_roots"].add(record_index)
            stat["observed_types"].add(_json_type(value))
            stat["occurrence_count"] += 1
            if value is None:
                stat["null_count"] += 1
            elif _is_empty(value):
                stat["empty_count"] += 1
            else:
                stat["non_empty_count"] += 1
            stat["representative_shapes"][_safe_shape(value, path)] += 1
            if isinstance(value, str) and value and _terminal(path) in SAFE_CATEGORY_FIELDS:
                stat["categorical_values"][value] += 1
            if isinstance(value, list):
                stat["array_lengths"].append(len(value))
                for element in value:
                    stat["element_shapes"][_element_shape(element)] += 1

    # Keep an explicit element-path row even when every observed parent array
    # is empty.  Its type/shape remains unknown, while parent presence and
    # empty-array counts stay measurable and cannot be mistaken for missing.
    for path, stat in list(stats.items()):
        if stat["array_lengths"] and f"{path}[]" not in stats:
            stats[f"{path}[]"] = _new_field_stat(len(records))

    result = []
    for path in sorted(stats):
        stat = stats[path]
        parent = path.rsplit(".", 1)[0] if "." in path else None
        lengths = stat["array_lengths"]
        nested = "[]" in path
        parent_array_path = path.rsplit("[]", 1)[0] if nested else None
        parent_array_stat = stats.get(parent_array_path) if parent_array_path else None
        if nested and parent_array_stat is None:
            raise ValueError(f"nested field {path} has no observed parent array")

        if nested and path.endswith("[]"):
            # The element path itself inherits presence semantics from the
            # parent array key.  An empty parent array therefore is not a
            # missing element path, and is reported separately below.
            present_count = len(parent_array_stat["present_roots"])
            missing_count = len(records) - present_count
            records_examined = len(records)
            null_count = parent_array_stat["null_count"]
            empty_count = parent_array_stat["empty_count"]
            non_empty_count = parent_array_stat["non_empty_count"]
            presence_scope = "parent_record"
        elif nested:
            # A child key inside an array element is measured against the
            # actual element containers.  Empty/missing parent arrays do not
            # manufacture missing child keys.
            element_containers_examined = sum(parent_array_stat["array_lengths"])
            present_count = stat["occurrence_count"]
            missing_count = max(0, element_containers_examined - present_count)
            records_examined = len(records)
            null_count = stat["null_count"]
            empty_count = stat["empty_count"]
            non_empty_count = stat["non_empty_count"]
            presence_scope = "array_element"
        else:
            present_count = len(stat["present_roots"])
            missing_count = len(records) - present_count
            records_examined = len(records)
            null_count = stat["null_count"]
            empty_count = stat["empty_count"]
            non_empty_count = stat["non_empty_count"]
            presence_scope = "record"
        item = {
            "object_kind": object_kind,
            "field_path": path,
            "parent_path": parent,
            "observed_types": sorted(stat["observed_types"]),
            "records_examined": records_examined,
            "presence_scope": presence_scope,
            "presence_denominator": (
                element_containers_examined if presence_scope == "array_element" else len(records)
            ),
            "element_observation_status": "observed"
            if stat["occurrence_count"]
            else "no_elements_observed",
            "present_count": present_count,
            "missing_count": missing_count,
            "null_count": null_count,
            "empty_count": empty_count,
            "non_empty_count": non_empty_count,
            "occurrence_count": stat["occurrence_count"],
            "representative_shapes": [
                {"shape": shape, "count": count}
                for shape, count in sorted(stat["representative_shapes"].items())
            ],
        }
        if nested:
            item.update(
                {
                    "parent_array_path": parent_array_path,
                    "parent_records_examined": len(records),
                    "parent_records_with_elements": parent_array_stat["non_empty_count"],
                    "parent_records_without_elements": parent_array_stat["empty_count"],
                    "parent_records_null": parent_array_stat["null_count"],
                    "parent_records_missing": len(records)
                    - len(parent_array_stat["present_roots"]),
                }
            )
            if presence_scope == "array_element":
                item["array_elements_examined"] = sum(parent_array_stat["array_lengths"])
        if stat["categorical_values"]:
            item["categorical_values"] = [
                {"value": value, "count": count}
                for value, count in sorted(stat["categorical_values"].items())
            ]
        if lengths:
            item["array_stats"] = {
                "array_occurrences": len(lengths),
                "min_length": min(lengths),
                "max_length": max(lengths),
                "mean_length": round(sum(lengths) / len(lengths), 6),
                "distinct_element_shapes": [
                    {"shape": shape, "count": count}
                    for shape, count in sorted(stat["element_shapes"].items())
                ],
            }
        result.append(item)
    return result


def _record_key_sets(records: list[Any]) -> list[dict[str, Any]]:
    counts: Counter[tuple[str, ...]] = Counter()
    for record in records:
        if isinstance(record, dict):
            counts[tuple(sorted(str(key) for key in record))] += 1
        else:
            counts[(f"<non-object:{_json_type(record)}>",)] += 1
    return [{"keys": list(keys), "record_count": count} for keys, count in sorted(counts.items())]


def _meta_inventory(meta: Any) -> dict[str, Any]:
    if not isinstance(meta, dict):
        return {
            "json_type": _json_type(meta),
            "keys": [],
            "field_shapes": [],
        }
    fields = []
    for key in sorted(meta, key=str):
        value = meta[key]
        item: dict[str, Any] = {
            "field": str(key),
            "observed_type": _json_type(value),
            "shape": _safe_shape(value, f"meta.{key}"),
        }
        if str(key).lower() in {"count", "type", "version"} and isinstance(
            value, (str, int, float, bool)
        ):
            item["safe_value"] = value
        fields.append(item)
    return {"json_type": "object", "keys": sorted(str(key) for key in meta), "fields": fields}


def _identifier_format(value: str) -> str:
    if SID_RE.fullmatch(value):
        return "sid-like"
    if GUID_RE.fullmatch(value):
        return "guid-like"
    if "@" in value or "\\" in value:
        return "composite-like"
    if "." in value:
        return "domain-like"
    return "other-string"


def _safe_record_anatomy(record: dict[str, Any]) -> dict[str, Any]:
    """Summarize a record's representation without emitting raw values."""
    fields: dict[str, Any] = {}
    for key in sorted(record, key=str):
        key = str(key)
        if key == "ObjectIdentifier":
            continue
        value = record[key]
        if isinstance(value, list):
            element_shapes = Counter(_element_shape(element) for element in value)
            fields[key] = {
                "type": "array",
                "length": len(value),
                "element_shapes": [
                    {"shape": shape, "count": count}
                    for shape, count in sorted(element_shapes.items())
                ],
            }
        elif isinstance(value, dict):
            fields[key] = {
                "type": "object",
                "keys": sorted(str(child) for child in value),
            }
        else:
            fields[key] = {
                "type": _json_type(value),
                "shape": _safe_shape(value, key),
            }
    properties = record.get("Properties")
    return {
        "record_key_set": sorted(str(key) for key in record),
        "properties_key_set": sorted(str(key) for key in properties)
        if isinstance(properties, dict)
        else [],
        "top_level_fields": fields,
    }


def _is_reference_candidate(path: str, value: str) -> bool:
    parts = _path_parts(path)
    terminal = _terminal(path)
    if terminal == "objectidentifier":
        return False
    if parts[:2] == ["properties", "objectid"]:
        return False
    if terminal in NON_REFERENCE_TERMINALS:
        return False
    return terminal in REFERENCE_TERMINALS or any(part in REFERENCE_COLLECTIONS for part in parts)


def _generator_info() -> dict[str, Any]:
    script = Path(__file__).resolve()
    try:
        git_commit = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    except OSError, subprocess.CalledProcessError:
        git_commit = None
    return {
        "git_commit": git_commit,
        "generator_sha256": hashlib.sha256(script.read_bytes()).hexdigest(),
    }


def _load_verified_json(data_dir: Path, manifest: dict, relative_path: str) -> tuple[Any, str]:
    reference = raw_file_reference(manifest, relative_path)
    payload = read_verified_snapshot_file(data_dir, manifest, reference)
    encoding = "UTF-8 with BOM" if payload.startswith(b"\xef\xbb\xbf") else "UTF-8"

    def unique_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate JSON key")
            result[key] = value
        return result

    return json.loads(payload.decode("utf-8-sig"), object_pairs_hook=unique_keys), encoding


def audit_snapshot(data_dir: Path, manifest_path: Path) -> dict[str, Any]:
    """Verify and audit all six SEAMLESS JSON files without semantic consumers."""
    data_dir = Path(data_dir)
    manifest_path = Path(manifest_path)
    manifest = load_manifest(manifest_path)
    issues = verify_manifest(data_dir, manifest)
    if issues:
        raise ValueError(f"SEAMLESS snapshot does not match manifest: {issues}")

    envelopes: dict[str, Any] = {}
    all_records: list[tuple[str, str, int, dict[str, Any]]] = []
    field_inventory: list[dict[str, Any]] = []
    oid_occurrences: dict[str, list[dict[str, Any]]] = defaultdict(list)
    oid_formats: Counter[str] = Counter()
    missing_oid_records: Counter[str] = Counter()
    collection_status_paths: set[str] = set()

    for entry in manifest["files"]:
        relative_path = entry["relative_path"]
        match = re.search(r"_([^_/]+)\.json$", relative_path, re.I)
        if not match or match.group(1).lower() not in FILE_KINDS:
            raise ValueError(f"manifest contains unexpected SEAMLESS file: {relative_path}")
        file_token = match.group(1).lower()
        object_kind = FILE_KINDS[file_token]
        payload, encoding = _load_verified_json(data_dir, manifest, relative_path)
        if not isinstance(payload, dict):
            raise ValueError(f"{relative_path} top-level JSON value is not an object")
        collection_key = file_token
        records = payload.get(collection_key)
        if not isinstance(records, list):
            raise ValueError(f"{relative_path} does not contain a list at {collection_key}")
        meta = payload.get("meta")
        file_reference = raw_file_reference(manifest, relative_path)
        envelopes[object_kind] = {
            "file": relative_path,
            "raw_file_reference": file_reference,
            "encoding": encoding,
            "top_level_json_type": "object",
            "top_level_keys": sorted(str(key) for key in payload),
            "collection_key": collection_key,
            "record_count": len(records),
            "record_type_counts": dict(sorted(Counter(_json_type(r) for r in records).items())),
            "record_key_sets": _record_key_sets(records),
            "meta": _meta_inventory(meta),
        }
        field_inventory.extend(_record_field_observations(records, object_kind))
        for record_index, record in enumerate(records):
            if not isinstance(record, dict):
                continue
            all_records.append((object_kind, file_reference, record_index, record))
            oid = record.get("ObjectIdentifier")
            if isinstance(oid, str) and oid:
                oid_occurrences[oid].append(
                    {
                        "object_kind": object_kind,
                        "raw_file_reference": file_reference,
                        "record_index": record_index,
                    }
                )
                oid_formats[_identifier_format(oid)] += 1
            else:
                missing_oid_records[object_kind] += 1

            for path, _value in _walk_fields(record, ""):
                if _terminal(path) in {
                    "status",
                    "failurereason",
                    "failurecause",
                    "collected",
                    "method",
                    "methods",
                    "errors",
                }:
                    collection_status_paths.add(f"{object_kind}.{path}")

    # The manifest is expected to contain one envelope per kind.  Sorting here
    # makes the report stable even if a future manifest lists files differently.
    if set(envelopes) != set(FILE_KINDS.values()):
        raise ValueError(f"SEAMLESS manifest did not provide all six object kinds: {envelopes}")

    field_inventory.sort(key=lambda item: (item["object_kind"], item["field_path"]))
    unique_oids = set(oid_occurrences)
    duplicate_items = {
        oid: occurrences for oid, occurrences in oid_occurrences.items() if len(occurrences) > 1
    }
    duplicate_by_kind: Counter[str] = Counter()
    for occurrences in duplicate_items.values():
        for occurrence in occurrences:
            duplicate_by_kind[occurrence["object_kind"]] += 1

    same_identifier_kinds = [
        occurrences
        for occurrences in oid_occurrences.values()
        if len({item["object_kind"] for item in occurrences}) > 1
    ]

    reference_stats: dict[tuple[str, str], dict[str, Any]] = {}
    unresolved_locators: list[dict[str, Any]] = []
    referenced_oids: Counter[str] = Counter()
    candidate_count = resolved_count = unresolved_count = 0
    for object_kind, file_reference, record_index, record in all_records:
        for path, value in _walk_fields(record, ""):
            if not isinstance(value, str) or not value or not _is_reference_candidate(path, value):
                continue
            key = (object_kind, path)
            stat = reference_stats.setdefault(
                key,
                {
                    "object_kind": object_kind,
                    "field_path": path,
                    "observed_count": 0,
                    "resolved_count": 0,
                    "unresolved_count": 0,
                    "target_object_kinds": Counter(),
                    "identifier_formats": Counter(),
                },
            )
            stat["observed_count"] += 1
            stat["identifier_formats"][_identifier_format(value)] += 1
            candidate_count += 1
            if value in unique_oids:
                stat["resolved_count"] += 1
                resolved_count += 1
                referenced_oids[value] += 1
                for target in oid_occurrences[value]:
                    stat["target_object_kinds"][target["object_kind"]] += 1
            else:
                stat["unresolved_count"] += 1
                unresolved_count += 1
                if len(unresolved_locators) < 40:
                    unresolved_locators.append(
                        {
                            "object_kind": object_kind,
                            "raw_file_reference": file_reference,
                            "record_index": record_index,
                            "field_path": path,
                            "value_shape": _safe_shape(value, path),
                        }
                    )

    reference_by_field = []
    for key in sorted(reference_stats):
        stat = reference_stats[key]
        reference_by_field.append(
            {
                "object_kind": stat["object_kind"],
                "field_path": stat["field_path"],
                "observed_count": stat["observed_count"],
                "resolved_count": stat["resolved_count"],
                "unresolved_count": stat["unresolved_count"],
                "target_object_kinds": dict(sorted(stat["target_object_kinds"].items())),
                "identifier_formats": dict(sorted(stat["identifier_formats"].items())),
            }
        )

    duplicate_locators = []
    record_by_locator = {
        (object_kind, file_reference, record_index): record
        for object_kind, file_reference, record_index, record in all_records
    }
    for occurrences in sorted(
        duplicate_items.values(),
        key=lambda group: (
            group[0]["object_kind"],
            group[0]["raw_file_reference"],
            group[0]["record_index"],
        ),
    ):
        summaries = []
        for occurrence in occurrences:
            record = record_by_locator[
                (
                    occurrence["object_kind"],
                    occurrence["raw_file_reference"],
                    occurrence["record_index"],
                )
            ]
            summaries.append(
                {
                    **occurrence,
                    "object_identifier_shape": _safe_shape(
                        record.get("ObjectIdentifier"), "ObjectIdentifier"
                    ),
                    "record_anatomy": _safe_record_anatomy(record),
                }
            )
        signatures = {json.dumps(item["record_anatomy"], sort_keys=True) for item in summaries}
        duplicate_locators.append(
            {
                "object_kind": occurrences[0]["object_kind"],
                "occurrence_count": len(occurrences),
                "representation_equivalent": len(signatures) == 1,
                "locations": summaries,
            }
        )

    cross_kind_locators = []
    for occurrences in sorted(
        same_identifier_kinds,
        key=lambda group: (
            sorted(item["object_kind"] for item in group),
            group[0]["record_index"],
        ),
    ):
        cross_kind_locators.append(
            {
                "object_kinds": sorted({item["object_kind"] for item in occurrences}),
                "occurrence_count": len(occurrences),
                "locations": occurrences,
            }
        )

    identity_by_kind: dict[str, dict[str, Any]] = {}
    for object_kind in sorted(envelopes):
        format_records: Counter[str] = Counter()
        format_unique: dict[str, set[str]] = defaultdict(set)
        format_locators: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for oid, occurrences in oid_occurrences.items():
            if not any(item["object_kind"] == object_kind for item in occurrences):
                continue
            identifier_format = _identifier_format(oid)
            format_records[identifier_format] += len(occurrences)
            format_unique[identifier_format].add(oid)
            for occurrence in occurrences:
                if len(format_locators[identifier_format]) < 40:
                    record = record_by_locator[
                        (
                            occurrence["object_kind"],
                            occurrence["raw_file_reference"],
                            occurrence["record_index"],
                        )
                    ]
                    format_locators[identifier_format].append(
                        {
                            "raw_file_reference": occurrence["raw_file_reference"],
                            "record_index": occurrence["record_index"],
                            "value_shape": _safe_shape(oid, "ObjectIdentifier"),
                            "record_anatomy": _safe_record_anatomy(record),
                        }
                    )
        identity_by_kind[object_kind] = {
            "record_counts_by_format": dict(sorted(format_records.items())),
            "unique_identifier_counts_by_format": {
                identifier_format: len(values)
                for identifier_format, values in sorted(format_unique.items())
            },
            "referenced_unique_identifier_counts_by_format": {
                identifier_format: sum(1 for oid in values if referenced_oids.get(oid, 0) > 0)
                for identifier_format, values in sorted(format_unique.items())
            },
            "unreferenced_unique_identifier_counts_by_format": {
                identifier_format: sum(1 for oid in values if referenced_oids.get(oid, 0) == 0)
                for identifier_format, values in sorted(format_unique.items())
            },
            "safe_locators_by_format": {
                identifier_format: locators
                for identifier_format, locators in sorted(format_locators.items())
            },
        }

    return {
        "dataset_id": manifest["dataset_id"],
        "snapshot_id": manifest["snapshot_id"],
        "manifest_verification": {
            "status": "verified",
            "file_count": manifest["summary"]["file_count"],
            "total_size_bytes": manifest["summary"]["total_size_bytes"],
        },
        "generator": _generator_info(),
        "envelopes": {kind: envelopes[kind] for kind in sorted(envelopes)},
        "field_inventory": field_inventory,
        "reference_summary": {
            "object_identifier_records": sum(len(v) for v in oid_occurrences.values()),
            "unique_object_identifiers": len(unique_oids),
            "missing_object_identifier_records": dict(sorted(missing_oid_records.items())),
            "identifier_formats": dict(sorted(oid_formats.items())),
            "candidate_reference_count": candidate_count,
            "resolved_reference_count": resolved_count,
            "unresolved_reference_count": unresolved_count,
            "unresolved_reference_locators": unresolved_locators,
            "by_field": reference_by_field,
            "same_identifier_across_object_kinds": cross_kind_locators,
            "unresolved_is_not_classified_as_boundary": True,
        },
        "object_identifier_archaeology": {
            "by_object_kind": [
                {"object_kind": object_kind, **identity_by_kind[object_kind]}
                for object_kind in sorted(identity_by_kind)
            ]
        },
        "duplicate_summary": {
            "duplicate_object_identifier_count": len(duplicate_items),
            "duplicate_record_count": sum(len(v) - 1 for v in duplicate_items.values()),
            "duplicate_occurrences_by_object_kind": dict(sorted(duplicate_by_kind.items())),
            "safe_duplicate_locators": duplicate_locators,
        },
        "collection_status_fields_observed": sorted(collection_status_paths),
        "interpretation_policy": {
            "raw_field_names_are_not_canonical_semantics": True,
            "missing_null_and_empty_are_measured_separately": True,
            "unresolved_references_require_later_interpretation": True,
            "no_attack_or_canonical_relationships_inferred": True,
        },
    }


def write_report(report: dict[str, Any], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _md(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def _field_table(report: dict[str, Any], object_kind: str) -> list[str]:
    rows = [
        "| Đường dẫn field | Kiểu quan sát được | Present count | Missing count | Null count | Empty count | Non-empty count | Counting unit / scope | Dạng giá trị đại diện |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | --- | --- |",
    ]
    fields = [item for item in report["field_inventory"] if item["object_kind"] == object_kind]
    for item in fields:
        shapes = "; ".join(
            f"{shape['shape']} ({shape['count']})" for shape in item["representative_shapes"]
        )
        if "array_stats" in item:
            array = item["array_stats"]
            shapes += (
                f"; array length {array['min_length']}–{array['max_length']}"
                f" (mean {array['mean_length']})"
            )
        scope = item.get("presence_scope", "record")
        if scope == "parent_record":
            basis = (
                f"parent record; parent có element "
                f"{item['parent_records_with_elements']}/{item['parent_records_examined']}, "
                f"parent không có element "
                f"{item['parent_records_without_elements']}/{item['parent_records_examined']}, "
                f"parent key missing {item['parent_records_missing']}"
            )
        elif scope == "array_element":
            basis = (
                f"array element; examined {item['array_elements_examined']}, "
                f"parent có element "
                f"{item['parent_records_with_elements']}/{item['parent_records_examined']}, "
                f"parent không có element "
                f"{item['parent_records_without_elements']}/{item['parent_records_examined']}"
            )
        else:
            basis = f"record ({item['records_examined']})"
        rows.append(
            "| "
            + " | ".join(
                [
                    _md(item["field_path"]),
                    _md(", ".join(item["observed_types"])),
                    str(item["present_count"]),
                    str(item["missing_count"]),
                    str(item["null_count"]),
                    str(item["empty_count"]),
                    str(item["non_empty_count"]),
                    _md(basis),
                    _md(shapes),
                ]
            )
            + " |"
        )
    return rows


def _find_field(report: dict[str, Any], object_kind: str, field_path: str) -> dict[str, Any] | None:
    return next(
        (
            item
            for item in report["field_inventory"]
            if item["object_kind"] == object_kind and item["field_path"] == field_path
        ),
        None,
    )


def _relationship_observation(
    report: dict[str, Any], object_kind: str, field_path: str
) -> dict[str, Any] | None:
    return next(
        (
            item
            for item in report["reference_summary"]["by_field"]
            if item["object_kind"] == object_kind and item["field_path"] == field_path
        ),
        None,
    )


def _evidence_card(
    report: dict[str, Any],
    title: str,
    object_kind: str,
    field_path: str,
    may_support: str,
    does_not_prove: str,
    open_questions: str,
) -> list[str]:
    field = _find_field(report, object_kind, field_path)
    if field is None:
        return []
    array = field.get("array_stats", {})
    nested_path = f"{field_path}[]"
    nested = _find_field(report, object_kind, nested_path)
    reference = _relationship_observation(report, object_kind, f"{field_path}[].MemberId")
    lines = [
        f"#### {title}",
        "",
        f"**Observed raw shape:** `{field_path}` is an array on "
        f"{field['records_examined']} {object_kind} records; "
        f"present={field['present_count']}, missing={field['missing_count']}, "
        f"null={field['null_count']}, empty={field['empty_count']}, "
        f"non-empty={field['non_empty_count']}.",
        "",
        "**Measured element shape:** "
        + (
            "; ".join(
                f"{shape['shape']} ({shape['count']})"
                for shape in array.get("distinct_element_shapes", [])
            )
            if array.get("distinct_element_shapes")
            else "no array elements were observed"
        )
        + ".",
        "",
        f"**Raw fact:** the snapshot exposes this field with the measured presence and "
        f"array cardinality above{f'; nested element keys are represented by `{nested_path}`' if nested else ''}.",
        "",
        f"**What it may support:** {may_support}",
        "",
        f"**What it does NOT prove:** {does_not_prove}",
        "",
        f"**Open questions:** {open_questions}",
    ]
    if reference is not None:
        lines.extend(
            [
                "",
                f"Reference-shaped observations for `{field_path}[].MemberId`: "
                f"{reference['observed_count']} seen, "
                f"{reference['resolved_count']} matched an ObjectIdentifier in this snapshot, "
                f"{reference['unresolved_count']} unresolved.",
            ]
        )
    return lines


def _render_markdown_legacy(report: dict[str, Any]) -> str:
    """Render the sanitized JSON observations as the Phase 1 research document."""
    envelopes = report["envelopes"]
    lines = [
        "# SEAMLESS Raw Field Audit",
        "",
        "## 1. Scope and method",
        "",
        "This is Phase 1 of #94: raw corpus anatomy and field-by-field schema archaeology "
        "for the verified SEAMLESS snapshot. The auditor reads only manifest-verified bytes, "
        "discovers fields recursively, and emits sanitized value shapes and safe categorical "
        "values. It does not import or alter parser, graph-builder, or attack-semantics "
        "behavior. Raw field names are observations, not canonical relationship contracts.",
        "",
        "For every discovered path, `present` means the path occurred in at least one root "
        "record; `missing` is a root record with no occurrence. `null`, `empty`, and "
        "`non-empty` count observed path values separately. Array-element paths use `[]`; "
        "their `present` count is still measured against root records. These denominators "
        "are intentionally not interpreted as collection completeness.",
        "",
        "## 2. Snapshot provenance",
        "",
        f"- Dataset ID: `{report['dataset_id']}`",
        f"- Snapshot ID: `{report['snapshot_id']}`",
        f"- Verification: `{report['manifest_verification']['status']}`",
        f"- Snapshot size: `{report['manifest_verification']['total_size_bytes']}` bytes",
        f"- Generator commit: `{report['generator']['git_commit']}`",
        f"- Generator SHA-256: `{report['generator']['generator_sha256']}`",
        "- Provenance is represented by `snapshot:<digest>/<relative_path>` references; no absolute local paths are emitted.",
        "",
        "## 3. Common JSON envelope anatomy",
        "",
        "All six files are UTF-8 JSON objects with a `meta` object and one plural collection "
        "key. The measured `meta.count` equals the corresponding collection length in every "
        "envelope. `meta` contains only `count`, `type`, and `version`; no collection/error "
        "status fields were observed.",
        "",
        "| Object kind | File | Collection key | Top-level keys | Records | Meta fields |",
        "| --- | --- | --- | --- | ---: | --- |",
    ]
    for kind in sorted(envelopes):
        envelope = envelopes[kind]
        meta_keys = ", ".join(envelope["meta"]["keys"])
        lines.append(
            f"| {kind} | `{envelope['file']}` | `{envelope['collection_key']}` | "
            f"{', '.join(envelope['top_level_keys'])} | {envelope['record_count']} | {meta_keys} |"
        )
    lines.extend(
        [
            "",
            "The machine-readable inventory contains the exact raw file references, encoding, "
            "record key-set counts, and sanitized field observations: "
            "`reports/generated/seamless-raw-field-inventory.json`.",
            "",
        ]
    )

    kind_notes = {
        "User": (
            "User records expose top-level identity, primary-group, ACL, delegation, SID-history, "
            "and a `Properties` object. The audit reports all of these as raw fields only; it does "
            "not infer authentication state, privilege, or attack technique."
        ),
        "Group": (
            "Group records expose `Members`, `Aces`, and group properties. One duplicate "
            "ObjectIdentifier occurs in this file; the auditor preserves both record locations "
            "in its duplicate summary and does not reconcile them."
        ),
        "Computer": (
            "Computer records expose ACLs, host-local membership-shaped arrays, empty delegation "
            "arrays, and an empty `Sessions` array in this snapshot. Presence of a raw array is "
            "not treated as proof of a canonical graph edge."
        ),
        "OU": (
            "OU records expose ACLs, hierarchy references, links, and user/computer membership "
            "arrays. Empty and non-empty collections are measured independently."
        ),
        "GPO": (
            "GPO records expose ACLs and GPO properties. Linkage is observed through references "
            "from OU/domain records; this phase does not model policy application semantics."
        ),
        "Domain": (
            "The single Domain record exposes ACLs, users, child OU references, links, and an "
            "empty `Trusts` array. No trust direction/type values are therefore observed in this snapshot."
        ),
    }
    for kind in ["User", "Group", "Computer", "OU", "GPO", "Domain"]:
        lines.extend(
            [
                f"## {4 + ['User', 'Group', 'Computer', 'OU', 'GPO', 'Domain'].index(kind)}. {kind}",
                "",
                "### Envelope",
                "",
                f"`{envelopes[kind]['raw_file_reference']}`; encoding `{envelopes[kind]['encoding']}`; "
                f"collection `{envelopes[kind]['collection_key']}`; "
                f"{envelopes[kind]['record_count']} records.",
                "",
                "### Record shape and field inventory",
                "",
                "Record key-set counts: "
                + "; ".join(
                    f"`{', '.join(item['keys'])}` ({item['record_count']})"
                    for item in envelopes[kind]["record_key_sets"]
                )
                + ".",
                "",
                *_field_table(report, kind),
                "",
                "### Important observations",
                "",
                kind_notes[kind],
                "",
                "### Open semantic questions",
                "",
                "Field names and values require collector-aware interpretation in a later phase. "
                "This document intentionally does not decide whether any field is authoritative, "
                "complete, transitive, effective, or equivalent to a canonical relationship.",
                "",
            ]
        )

    lines.extend(["## 10. Cross-file identity and reference semantics", ""])
    refs = report["reference_summary"]
    dup = report["duplicate_summary"]
    lines.extend(
        [
            f"The six files contain `{refs['object_identifier_records']}` object records and "
            f"`{refs['unique_object_identifiers']}` unique `ObjectIdentifier` values. "
            f"Observed identifier shapes are "
            + ", ".join(f"{key} ({value})" for key, value in refs["identifier_formats"].items())
            + ". No record lacked an ObjectIdentifier, and no identifier appeared across multiple "
            "object kinds.",
            "",
            f"There is `{dup['duplicate_object_identifier_count']}` duplicate identifier group "
            f"(`{dup['duplicate_record_count']}` duplicate record beyond the first). The safe "
            "locator in the JSON report identifies the file reference and record indexes without "
            "emitting the identifier value.",
            "",
            f"Reference-shaped scalar observations total `{refs['candidate_reference_count']}`: "
            f"`{refs['resolved_reference_count']}` matched an ObjectIdentifier in the snapshot and "
            f"`{refs['unresolved_reference_count']}` did not. The two unresolved observations are "
            "Group member references. They are reported as unresolved, not as external, boundary, "
            "dangling, or invalid objects. Exact field-level counts and safe locators are in the "
            "machine-readable report.",
            "",
            "Reference-shaped observations include member IDs, ACE principals, primary-group IDs, "
            "OU/domain membership lists, child OU IDs, and GPO link GUIDs. Matching is exact against "
            "the observed ObjectIdentifier set; it is not a canonicalization or identity-resolution step.",
            "",
            "## 11. Missing / null / empty observations",
            "",
            "The report keeps missing, null, empty containers, and non-empty values separate. "
            "Examples from the verified snapshot include: `Computer.LocalAdmins` is present on all "
            "100 computers but non-empty on 1; `Computer.RemoteDesktopUsers` is present on all 100 "
            "but non-empty on 1; `Computer.PSRemoteUsers` is present on all 100 but non-empty on 1; "
            "and `Computer.Sessions` is present and empty on all 100. User, Computer, OU, GPO, and "
            "Domain properties also contain measured null values, while some arrays are present but "
            "empty.",
            "",
            "No status, failure-reason, collection-method, or error fields were observed in the raw "
            "snapshot. Therefore this Phase 1 audit cannot distinguish successful empty collection "
            "from access denied, method not run, schema absence, or another collector limitation. "
            "It does not fabricate collection-completeness semantics.",
            "",
            "## 12. Duplicate and edge-case observations",
            "",
            "- The one duplicate ObjectIdentifier is retained as two safe record locators; no merge is performed by this auditor.",
            "- `Aces[].AceType` không hành xử như discriminator Windows allow/deny đơn giản: snapshot có các value non-empty `All`, `GetChanges` và `GetChangesAll`; đây được giữ như nhãn collector-specific cho tới khi trace implementation/schema.",
            "- `Properties.objectid` is measured as an identity-property field and is not counted as a relationship reference.",
            "- `Trusts` is present but empty on the Domain record; no trust categories can be inferred from this snapshot.",
            "- Representative strings are reduced to shapes such as SID-like, GUID-like, DN-like, timestamp-like, or redacted composite/domain-like strings.",
            "",
            "## 13. Raw primitives that require later semantic interpretation",
            "",
        ]
    )
    lines.extend(
        _evidence_card(
            report,
            "Group.Members[]",
            "Group",
            "Members",
            "membership-shaped raw evidence and reference-coverage analysis",
            "a canonical transitive MemberOf relationship, effective authorization, or attack path",
            "whether duplicate records, collector scope, or unresolved IDs change downstream interpretation",
        )
        + [""]
    )
    lines.extend(
        [
            "#### *.Aces[]",
            "",
            "**Observed raw shape:** `Aces[]` occurs on all six object kinds. Its element shape is an object with "
            "`AceType`, `IsInherited`, `PrincipalSID`, `PrincipalType`, and `RightName`; the inventory "
            "measures the per-kind counts and safe categories.",
            "",
            "**Raw fact:** the snapshot contains ACE-shaped records and categorical values such as "
            "`PrincipalType` and `RightName`.",
            "",
            "**What it may support:** later ACL/permission evidence analysis with collector-aware rules.",
            "",
            "**What it does NOT prove:** that every ACE is effective, exploitable, canonical, or an attack technique.",
            "",
            "**Open questions:** inheritance, filtering, principal resolution, and effective-right semantics belong to later phases.",
            "",
        ]
    )
    for title, kind, path, may_support, not_prove, questions in [
        (
            "Computer.LocalAdmins[]",
            "Computer",
            "LocalAdmins",
            "host-local membership-shaped evidence",
            "verified AdminTo or effective local administrator access",
            "collector method, host availability, and local-group semantics",
        ),
        (
            "Computer.RemoteDesktopUsers[]",
            "Computer",
            "RemoteDesktopUsers",
            "a raw membership-shaped input relevant to later host-access analysis",
            "canonical CanRDP or successful RDP capability",
            "the required user-right, deny-right, policy, and host-state predicates",
        ),
        (
            "Computer.PSRemoteUsers[]",
            "Computer",
            "PSRemoteUsers",
            "a raw membership-shaped input relevant to later remoting analysis",
            "canonical CanPSRemote or usable WinRM access",
            "service, endpoint, policy, and deny-right evidence",
        ),
        (
            "Computer.Sessions[]",
            "Computer",
            "Sessions",
            "a session-shaped observation if elements are collected",
            "observed activity, credential exposure, or absence of sessions in the environment",
            "collector status and whether an empty array means empty, unobservable, or not run",
        ),
    ]:
        lines.extend(_evidence_card(report, title, kind, path, may_support, not_prove, questions))
        lines.append("")

    lines.extend(
        [
            "### Current consumers and bounded follow-up",
            "",
            "The current `scripts/eda_dataset_analysis.py` consumes several of these raw fields "
            "while producing its broader EDA, including `Members`, `Aces`, `LocalAdmins`, "
            "`RemoteDesktopUsers`, `PSRemoteUsers`, and `Sessions`. The #80 EDA remediation now "
            "reports `RemoteDesktopUsers[]`, `LocalAdmins[]`, `PSRemoteUsers[]`, and `Sessions[]` "
            "as raw/evidence primitives with explicit unknown completeness, and does not count "
            "raw `RemoteDesktopUsers[]` as verified `CanRDP`. Positive `LocalAdmins[]` and "
            "`PSRemoteUsers[]` observations remain bounded structural evidence; empty/unobserved "
            "arrays do not prove relationship absence. Production parser/builder canonicalization "
            "remains scoped to #44/#45, and no canonical contract or attack-semantics behavior was "
            "changed here.",
            "",
            "## 14. Inputs for subsequent #94 phases",
            "",
            "- Preserve this snapshot and its manifest as the byte-level source of truth for later phases.",
            "- Carry the unresolved member references forward as unresolved observations until an approved identity/boundary policy exists.",
            "- Treat empty endpoint arrays as measurements with unknown collection completeness, not as false capability claims.",
            "- Revisit #79/#80 semantic evidence taxonomy only after raw field and collector-status evidence is available.",
            "- Revisit #44/#45 parser and host-access inference behavior after the loader time-provenance decision and a reviewed raw-to-canonical policy.",
            "- Use #47 cross-dataset comparison only with explicit field provenance and no assumption that similarly named fields have equivalent semantics.",
            "- Windows telemetry auditing is deliberately out of scope for this phase.",
            "",
            "## Reproduction",
            "",
            "```bash",
            "python scripts/audit_seamless_raw.py \\",
            "  --raw-dir data/raw/SEAMLESS \\",
            "  --manifest data/samples/manifests/seamless-raw-v1.json \\",
            "  --output reports/generated/seamless-raw-field-inventory.json",
            "```",
            "",
            "The generated JSON is local-only under `reports/generated/`; this tracked document contains sanitized observations and no raw AD identities.",
            "",
        ]
    )
    return "\n".join(lines)


PROPERTY_MEANINGS = {
    "admincount": (
        "Cờ thuộc tính mà collector xuất ra cho trạng thái `adminCount` của object. "
        "Nó là tín hiệu directory/collector, không phải bản đồ đầy đủ về đặc quyền hiệu lực.",
        "Không tự chứng minh object là quản trị viên hay mọi quyền của object đã được thu thập.",
    ),
    "blocksinheritance": (
        "Cờ mô tả trạng thái chặn kế thừa chính sách trên OU theo dữ liệu collector xuất ra.",
        "Không tự tạo ra resultant policy và không thay thế việc tính thứ tự/enforced của GPO.",
    ),
    "description": (
        "Thuộc tính mô tả của object; giá trị có thể là chuỗi hoặc `null` trong snapshot.",
        "Không phải bằng chứng về trạng thái vận hành hay quyền hạn.",
    ),
    "distinguishedname": (
        "Tên phân biệt (DN) mà collector xuất cho object trong namespace directory.",
        "Không tự chứng minh object còn tồn tại, có thể truy cập, hay DN là định danh canonical của project.",
    ),
    "displayname": (
        "Tên hiển thị được collector xuất; snapshot có cả giá trị chuỗi và `null`.",
        "Không nên dùng làm khóa tham chiếu vì có thể thiếu hoặc không duy nhất.",
    ),
    "domain": (
        "Thông tin domain gắn với object trong output của collector.",
        "Không tự chứng minh trust, membership, hay hướng trust giữa các domain.",
    ),
    "domainsid": (
        "SID của domain chứa object nếu field này xuất hiện trong một schema/export tương ứng.",
        "Field này không xuất hiện trong verified SEAMLESS snapshot hiện tại.",
    ),
    "dontreqpreauth": (
        "Cờ thuộc tính account do collector xuất ra liên quan tới yêu cầu pre-authentication.",
        "Không tự chứng minh một kỹ thuật tấn công, khả năng khai thác, hay trạng thái runtime.",
    ),
    "enabled": (
        "Cờ enabled/disabled được collector lấy từ thuộc tính account hoặc object.",
        "Không đồng nghĩa với việc account đang đăng nhập được, service đang chạy, hay network path hoạt động.",
    ),
    "functionallevel": (
        "Mức chức năng domain được collector xuất trong record Domain.",
        "Không phải một edge hoặc bằng chứng về quyền của principal.",
    ),
    "gpcpath": (
        "Đường dẫn UNC tới Group Policy Template (GPT) của GPO trong SYSVOL; đây là phần filesystem của GPO, không phải đường dẫn tới Group Policy Container (GPC) trong Active Directory.",
        "Collector xuất reference tới vị trí GPT mà GPO dùng để lưu policy files; field này không tự chứa toàn bộ policy settings.",
    ),
    "hasspn": (
        "Cờ collector cho biết có dấu hiệu SPN theo record hay không.",
        "Không tự chứng minh service đang chạy hoặc authentication sẽ thành công.",
    ),
    "haslaps": (
        "Giá trị boolean được collector xuất cho field `haslaps`; snapshot này quan sát `false`.",
        "Không đủ để kết luận trạng thái triển khai LAPS hay nguyên nhân của giá trị `false`.",
    ),
    "highvalue": (
        "Nhãn phân loại giá trị cao mà BloodHound/collector gắn cho object.",
        "Không phải bằng chứng độc lập về quyền Windows hay khả năng khai thác.",
    ),
    "homedirectory": (
        "Thuộc tính mô tả home directory của account; trong snapshot hiện tại là `null`.",
        "Không nên diễn giải `null` thành trạng thái không tồn tại ngoài directory.",
    ),
    "lastlogon": (
        "Giá trị integer timestamp-like do collector xuất cho lần logon cục bộ/được quan sát theo schema.",
        "Auditor chưa xác minh unit/timezone; không được tự quy đổi hoặc coi `0` là `never`.",
    ),
    "lastlogontimestamp": (
        "Giá trị integer timestamp-like tương ứng với thuộc tính logon timestamp mà collector xuất.",
        "Không đủ để khẳng định thời điểm đăng nhập chính xác; unit, replication lag và `0` cần evidence riêng.",
    ),
    "name": (
        "Tên hoặc display identity mà collector dùng để mô tả object; giá trị thực tế được auditor redacted.",
        "Không nên dùng làm identity key, vì có thể chứa tên hiển thị, format composite hoặc không duy nhất.",
    ),
    "objectid": (
        "Bản sao identity property do collector đặt trong `Properties`; trong nhiều record tương ứng với định danh object.",
        "Không nên gộp mặc định với top-level `ObjectIdentifier` mà bỏ qua duplicate/scope behavior.",
    ),
    "operatingsystem": (
        "Chuỗi OS nếu collector quan sát được; snapshot có phần lớn giá trị `null`.",
        "Không chứng minh host đang online hoặc endpoint đã join domain thực sự.",
    ),
    "passwordnotreqd": (
        "Cờ account do collector xuất về thuộc tính password requirement.",
        "Không tự chứng minh mật khẩu yếu, có thể đăng nhập, hoặc kỹ thuật tấn công cụ thể.",
    ),
    "pwdlastset": (
        "Giá trị integer timestamp-like mà collector xuất cho lần đặt mật khẩu.",
        "Auditor chưa xác minh unit/timezone và không suy diễn `0`, stale hay khả năng đăng nhập.",
    ),
    "pwdneverexpires": (
        "Cờ account do collector xuất về chính sách hết hạn mật khẩu.",
        "Không tự chứng minh mật khẩu hiện tại hợp lệ hay một attack path.",
    ),
    "sensitive": (
        "Cờ thuộc tính account do collector xuất về trạng thái nhạy cảm của object.",
        "Không thay thế kiểm tra kỹ thuật/runtime khác và không tự gắn ATT&CK technique.",
    ),
    "serviceprincipalnames": (
        "Mảng các SPN string mà collector quan sát trên object; có thể rỗng hoặc không rỗng.",
        "Không tự chứng minh service đang chạy, ticket có thể lấy được, hay account có thể bị compromise.",
    ),
    "sidhistory": (
        "Mảng SID history do collector xuất; snapshot hiện tại không có phần tử.",
        "Mảng rỗng không phân biệt không có dữ liệu, collector không thu được, hay schema không áp dụng.",
    ),
    "title": (
        "Thuộc tính mô tả title của user; snapshot hiện tại là `null`.",
        "Không phải identity key hay evidence về quyền.",
    ),
    "unconstraineddelegation": (
        "Cờ delegation do collector xuất cho object.",
        "Không tự chứng minh một ticket, session, hay attack đã xảy ra.",
    ),
    "userpassword": (
        "Field password-related được output dưới dạng `null` trong snapshot.",
        "Không được diễn giải thành password không tồn tại hoặc được bảo vệ theo một cách cụ thể.",
    ),
}


def _field_counts_sentence(field: dict[str, Any]) -> str:
    observed_type = ", ".join(field["observed_types"]) or "chưa quan sát element"
    scope = field.get("presence_scope", "record")
    if scope == "parent_record":
        presence = (
            f"parent key có mặt {field['present_count']}/{field['records_examined']} record, "
            f"parent key thiếu {field['missing_count']}, "
            f"parent có element {field['parent_records_with_elements']}, "
            f"parent không có element {field['parent_records_without_elements']}"
        )
    elif scope == "array_element":
        presence = (
            f"đã kiểm tra {field['array_elements_examined']} array element; "
            f"field có mặt trong {field['present_count']}/{field['array_elements_examined']} element; "
            f"field thiếu trong {field['missing_count']} element; "
            f"parent records có element: {field['parent_records_with_elements']}/"
            f"{field['parent_records_examined']}; "
            f"parent records không có element: {field['parent_records_without_elements']}/"
            f"{field['parent_records_examined']}"
        )
    else:
        presence = (
            f"có mặt {field['present_count']}/{field['records_examined']} record gốc, "
            f"thiếu {field['missing_count']}"
        )
    return (
        f"kiểu `{observed_type}`, {presence}, "
        f"`null` {field['null_count']}, rỗng {field['empty_count']}, "
        f"không rỗng {field['non_empty_count']}"
    )


def _semantic_card(
    report: dict[str, Any],
    object_kind: str,
    field_path: str,
    title: str,
    raw_meaning: str,
    collector_meaning: str,
    project_meaning: str,
    proves: str,
    does_not_prove: str,
    certainty: str,
    source: str,
) -> list[str]:
    if title in {"ObjectIdentifier", "Properties"}:
        # These are documented once in the common-field section.  Repeating
        # the same semantic card for six object kinds made the research prose
        # look generated without adding new meaning.
        return []
    field = _find_field(report, object_kind, field_path)
    if field is None:
        return []
    shapes = "; ".join(
        f"{item['shape']} ({item['count']})" for item in field["representative_shapes"]
    )
    lines = [
        f"#### `{title}`",
        "",
        "**Quan sát từ snapshot**",
        "",
        f"- `{object_kind}.{field_path}` có {_field_counts_sentence(field)}.",
        f"- Dạng giá trị đại diện đã sanitize: {shapes}.",
        "",
        "**Tầng 1 — Biểu diễn raw**",
        "",
        raw_meaning,
        "",
        "**Tầng 2 — Ý nghĩa ở collector**",
        "",
        collector_meaning,
        "",
        "**Tầng 3 — Diễn giải của project**",
        "",
        project_meaning,
        "",
        f"**Field này chứng minh:** {proves}",
        "",
        f"**Field này không chứng minh:** {does_not_prove}",
        "",
        f"**Mức độ chắc chắn:** {certainty}",
        "",
        f"**Nguồn giải thích:** {source}",
        "",
    ]
    return lines


def _property_table(report: dict[str, Any], object_kind: str) -> list[str]:
    fields = [
        item
        for item in report["field_inventory"]
        if item["object_kind"] == object_kind
        and item["field_path"].startswith("Properties.")
        and "[]" not in item["field_path"]
    ]
    if not fields:
        return []
    rows = [
        "| Field con | Quan sát | Ý nghĩa được dùng trong tài liệu | Không được suy ra |",
        "| --- | --- | --- | --- |",
    ]
    for field in fields:
        name = field["field_path"].split(".", 1)[1]
        meaning, limitation = PROPERTY_MEANINGS.get(
            name,
            (
                "Ý nghĩa collector của subfield này chưa được xác minh đầy đủ; hiện chỉ ghi nhận như thuộc tính descriptive/state.",
                "Không suy ra canonical edge hoặc trạng thái runtime.",
            ),
        )
        rows.append(
            f"| `{name}` | {_md(_field_counts_sentence(field))}; {_md('; '.join(item['shape'] for item in field['representative_shapes']))} | {_md(meaning)} | {_md(limitation)} |"
        )
    return rows


def _categorical_meanings(report: dict[str, Any], object_kind: str) -> list[str]:
    fields = [
        item
        for item in report["field_inventory"]
        if item["object_kind"] == object_kind and item.get("categorical_values")
    ]
    if not fields:
        return [
            "Không có categorical value thuộc nhóm an toàn nào được quan sát trong phần tử của field này.",
            "",
        ]
    lines = [
        "| Field phân loại | Giá trị quan sát | Cách đọc ở tầng raw |",
        "| --- | --- | --- |",
    ]
    for field in fields:
        values = ", ".join(
            f"`{item['value']}` ({item['count']})" for item in field["categorical_values"]
        )
        if field["field_path"].endswith("MemberType"):
            meaning = "Loại object mà collector gắn cho principal được tham chiếu; `Group` có thể là group nesting nếu nằm trong `Members[]`."
        elif field["field_path"].endswith("PrincipalType"):
            meaning = "Loại object mà collector gắn cho trustee/principal trong ACE; không thay thế việc resolve SID."
        elif field["field_path"].endswith("RightName"):
            meaning = "Nhãn quyền đã được collector normalize; không phải raw Windows access mask."
        else:
            meaning = "Giá trị phân loại an toàn được ghi nhận; ý nghĩa đầy đủ cần đọc cùng container field."
        lines.append(f"| `{field['field_path']}` | {values} | {meaning} |")
    return lines + [""]


def _nested_field_table(
    report: dict[str, Any],
    object_kind: str,
    specifications: list[tuple[str, ...]],
) -> list[str]:
    """Render semantic notes for important nested fields without raw values."""
    rows = [
        "| Đường dẫn field | Quan sát đo được | Field biểu diễn gì | Chứng minh được | Không chứng minh được | Ghi chú |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for specification in specifications:
        path = specification[0]
        if len(specification) == 5:
            meaning, proves, does_not_prove, note = specification[1:]
        else:
            meaning, collector_note, proves, does_not_prove, note = specification[1:]
            meaning = f"{meaning} {collector_note}"
        field = _find_field(report, object_kind, path)
        if field is None:
            continue
        rows.append(
            f"| `{path}` | {_md(_field_counts_sentence(field))}; "
            f"{_md('; '.join(item['shape'] for item in field['representative_shapes']))} "
            f"| {_md(meaning)} | {_md(proves)} | {_md(does_not_prove)} | {_md(note)} |"
        )
    return rows if len(rows) > 2 else []


def _ace_value_meanings(report: dict[str, Any], object_kind: str) -> list[str]:
    field = _find_field(report, object_kind, "Aces[].RightName")
    if field is None:
        return []
    observed = {item["value"] for item in field["categorical_values"]}
    meanings = {
        "GenericAll": "Nhãn collector cho một nhóm quyền kiểm soát rộng trên object; không phải nguyên access mask và không tự khẳng định effective access.",
        "GenericWrite": "Nhãn collector cho một nhóm quyền ghi rộng; không tự khẳng định mọi thuộc tính đều sửa được trong mọi context.",
        "Owner": "Nhãn collector liên quan tới quan hệ owner của object; không tự mô tả toàn bộ quyền thực tế của owner.",
        "WriteDacl": "Nhãn collector liên quan tới khả năng sửa DACL; không thay thế việc đánh giá ACE allow/deny và access check đầy đủ.",
        "WriteOwner": "Nhãn collector liên quan tới khả năng thay đổi owner; không tự chứng minh hành động đã xảy ra.",
        "ExtendedRight": "Nhãn collector cho extended/control-access right; cần object-specific GUID và security descriptor để xác định quyền cụ thể.",
    }
    rows = [
        "**Cách đọc giá trị `RightName`:**",
        "",
        "| Giá trị quan sát | Cách đọc thận trọng |",
        "| --- | --- |",
    ]
    for value in sorted(observed):
        rows.append(
            f"| `{value}` | {meanings.get(value, 'Ý nghĩa cụ thể chưa xác minh đầy đủ; chỉ ghi nhận đây là nhãn quyền do collector xuất.')} |"
        )
    rows.append("")
    return rows


def _ace_type_value_meanings(report: dict[str, Any], object_kind: str) -> list[str]:
    field = _find_field(report, object_kind, "Aces[].AceType")
    if field is None or not field.get("categorical_values"):
        return []
    all_values = sorted(
        {
            item["value"]
            for candidate in report["field_inventory"]
            if candidate["field_path"] == "Aces[].AceType"
            for item in candidate.get("categorical_values", [])
        }
    )
    rows: list[str] = []
    if object_kind == "User" and all_values:
        rows.extend(
            [
                "**Finding về hình thái giá trị:** snapshot quan sát các giá trị non-empty `"
                + "`, `".join(all_values)
                + "` trên các object kind có `Aces[]`. Tập giá trị này không hành xử như một discriminator Windows đơn giản kiểu `ACCESS_ALLOWED_ACE` / `ACCESS_DENIED_ACE`; đặc biệt `GetChanges` và `GetChangesAll` có hình thái giống nhãn quyền hơn là loại ACE allow/deny.",
                "",
                "Vì vậy `AceType` phải được coi là nhãn collector/BloodHound-specific cho tới khi trace được implementation/schema tương ứng. Không được dùng nó để suy ra allow/deny, thứ tự DACL, hoặc effective permission.",
                "",
            ]
        )
    rows.extend(
        [
            "**Các giá trị `AceType` không nhạy cảm quan sát được:**",
            "",
            "| Giá trị | Cách đọc thận trọng |",
            "| --- | --- |",
        ]
    )
    for item in field["categorical_values"]:
        rows.append(
            f"| `{item['value']}` | Nhãn `AceType` do collector xuất; không đọc như Windows ACE allow/deny type nếu chưa có implementation/schema evidence. |"
        )
    rows.append("")
    return rows


def _anatomy_array_length(anatomy: dict[str, Any], field_name: str) -> str:
    field = anatomy.get("top_level_fields", {}).get(field_name)
    if not field or field.get("type") != "array":
        return "không có key"
    return str(field["length"])


def _identity_archaeology_lines(report: dict[str, Any]) -> list[str]:
    identity = report["object_identifier_archaeology"]["by_object_kind"]
    lines = [
        "### Dạng `ObjectIdentifier` theo object kind",
        "",
        "| Object kind | Dạng | Số record | Số identifier unique | Unique ID được reference | Unique ID chưa được reference |",
        "| --- | --- | ---: | ---: | ---: | ---: |",
    ]
    for item in identity:
        for identifier_format, record_count in item["record_counts_by_format"].items():
            lines.append(
                f"| `{item['object_kind']}` | `{identifier_format}` | {record_count} | "
                f"{item['unique_identifier_counts_by_format'][identifier_format]} | "
                f"{item['referenced_unique_identifier_counts_by_format'][identifier_format]} | "
                f"{item['unreferenced_unique_identifier_counts_by_format'][identifier_format]} |"
            )
    lines.extend(
        [
            "",
            "Matching vẫn là exact string matching trên các raw references đã được auditor nhận diện; nó không phải canonicalization hay identity resolution.",
            "",
        ]
    )
    group = next(item for item in identity if item["object_kind"] == "Group")
    group_domain = group["safe_locators_by_format"].get("domain-like", [])
    if group_domain:
        stub_count = sum(
            locator["record_anatomy"]["properties_key_set"] == ["domain", "name"]
            for locator in group_domain
        )
        lines.extend(
            [
                "### Khảo cổ 31 `Group.ObjectIdentifier` dạng domain-like",
                "",
                f"Snapshot có `{len(group_domain)}` record Group dạng domain-like; inventory identity cho thấy "
                f"`{group['unique_identifier_counts_by_format'].get('domain-like', 0)}` identifier unique, "
                f"trong đó `{group['referenced_unique_identifier_counts_by_format'].get('domain-like', 0)}` unique ID đã được reference exact-match và "
                f"`{group['unreferenced_unique_identifier_counts_by_format'].get('domain-like', 0)}` chưa được reference bởi field reference candidate.",
                "",
                f"Có `{stub_count}` record dạng stub chỉ có `Properties.domain` và `Properties.name`; các record còn lại có tập `Properties` đầy đủ hơn. Đây là pattern biểu diễn cần giữ lại trong reconciliation, không được tự coi domain-like ID là SID của Group, boundary identity hay invalid record.",
                "",
                "| Record index an toàn | Dạng identifier | Tập key `Properties` | Độ dài `Members` | Độ dài `Aces` |",
                "| ---: | --- | --- | ---: | ---: |",
            ]
        )
        for locator in sorted(group_domain, key=lambda item: item["record_index"]):
            anatomy = locator["record_anatomy"]
            lines.append(
                f"| {locator['record_index']} | `{locator['value_shape']}` | "
                f"`{', '.join(anatomy['properties_key_set'])}` | "
                f"{_anatomy_array_length(anatomy, 'Members')} | "
                f"{_anatomy_array_length(anatomy, 'Aces')} |"
            )
        lines.extend(
            [
                "",
                "Các index trong bảng là locator an toàn, không phải identity value. Snapshot quan sát 30 identifier unique, trong đó 8 identifier có exact-reference và 22 identifier chưa được reference bởi các field candidate; pattern này vẫn không giải quyết được nguồn gốc identity. Cần đối chiếu collector implementation, object class và boundary policy ở phase sau.",
                "",
            ]
        )
    return lines


def _duplicate_archaeology_lines(report: dict[str, Any]) -> list[str]:
    lines = ["### Khảo cổ duplicate representation", ""]
    for duplicate in report["duplicate_summary"]["safe_duplicate_locators"]:
        lines.extend(
            [
                f"#### Duplicate `{duplicate['object_kind']}.ObjectIdentifier` — {duplicate['occurrence_count']} occurrences",
                "",
                "| Record index | Dạng identifier | Tập key record | Tập key `Properties` | Độ dài `Members` | Độ dài `Aces` |",
                "| ---: | --- | --- | --- | ---: | ---: |",
            ]
        )
        for location in duplicate["locations"]:
            anatomy = location["record_anatomy"]
            lines.append(
                f"| {location['record_index']} | `{location['object_identifier_shape']}` | "
                f"`{', '.join(anatomy['record_key_set'])}` | "
                f"`{', '.join(anatomy['properties_key_set'])}` | "
                f"{_anatomy_array_length(anatomy, 'Members')} | "
                f"{_anatomy_array_length(anatomy, 'Aces')} |"
            )
        lines.extend(
            [
                "",
                f"Diễn giải: hai record dùng cùng collector identifier nhưng biểu diễn {'tương đương' if duplicate['representation_equivalent'] else 'không tương đương'} về anatomy. Vì vậy auditor không dùng last-write-wins và không tự merge chúng.",
                "",
            ]
        )
    return lines


def render_markdown(report: dict[str, Any]) -> str:
    """Render the measured inventory as a Vietnamese, semantic research document."""
    envelopes = report["envelopes"]
    refs = report["reference_summary"]
    sources = (
        "[raw snapshot và manifest trong repository](../../data/samples/manifests/seamless-raw-v1.json); "
        "[mã nguồn SharpHound](https://github.com/SpecterOps/SharpHound); "
        "[SharpHound technical details](https://specterops.io/blog/2017/10/14/sharphound-technical-details/); "
        "[Microsoft ACE](https://learn.microsoft.com/en-us/windows/win32/secauthz/access-control-entries); "
        "[Microsoft ACCESS_MASK](https://learn.microsoft.com/en-us/windows/win32/secauthz/access-mask); "
        "[Microsoft Group Policy processing](https://learn.microsoft.com/en-us/windows-server/identity/ad-ds/manage/group-policy/group-policy-processing); "
        "[Microsoft gPCFileSysPath](https://learn.microsoft.com/en-us/openspecs/windows_protocols/ms-ada1/6eb770b7-0c89-4a3e-a41e-2807d46880d8); "
        "[Microsoft Group Policy storage](https://learn.microsoft.com/en-us/previous-versions/windows/desktop/policy/group-policy-storage); "
        "[Microsoft trust direction](https://learn.microsoft.com/en-us/windows/win32/api/ntsecapi/ns-ntsecapi-trusted_domain_information_ex); "
        "[Microsoft account rights](https://learn.microsoft.com/en-us/windows/win32/secauthz/account-rights-constants)."
    )
    lines = [
        "# SEAMLESS Raw Field Audit",
        "",
        "## 1. Phạm vi và phương pháp",
        "",
        "Đây là Phase 1 của #94: giải phẫu corpus raw và khảo cổ schema theo từng field của "
        "snapshot SEAMLESS đã được xác minh. Auditor chỉ đọc bytes sau khi kiểm tra manifest; "
        "phát hiện field đệ quy; đo `missing`, `null`, container rỗng, container không rỗng; "
        "và chỉ phát hành dạng giá trị/categorical value an toàn. Auditor không import hoặc thay "
        "đổi parser, graph builder hay attack semantics.",
        "",
        "Mỗi giải thích dưới đây tách ba tầng: (1) biểu diễn raw, (2) ý nghĩa mà collector "
        "thường gắn cho cấu trúc đó, và (3) mức diễn giải mà project có thể dùng sau khi bổ sung "
        "policy/semantics. Tên field không tự trở thành canonical relationship.",
        "",
        "## 2. Nguồn gốc snapshot",
        "",
        f"- Dataset ID: `{report['dataset_id']}`",
        f"- Snapshot ID: `{report['snapshot_id']}`",
        f"- Trạng thái xác minh: `{report['manifest_verification']['status']}`",
        f"- Kích thước snapshot: `{report['manifest_verification']['total_size_bytes']}` bytes",
        f"- Commit của generator: `{report['generator']['git_commit']}`",
        f"- SHA-256 generator: `{report['generator']['generator_sha256']}`",
        "- Raw provenance dùng dạng `snapshot:<digest>/<relative_path>`; không ghi absolute path hay raw identity.",
        "",
        "Thứ tự evidence của tài liệu là: raw record thực tế → schema/collector SharpHound → "
        "tài liệu Windows/AD có thẩm quyền khi field phản ánh Windows semantics → ADR/research "
        "đã chấp nhận trong repository → consumer hiện tại chỉ để biết code đang dùng field ở đâu, "
        "không dùng làm source-of-truth cho ý nghĩa raw.",
        "",
        f"Nguồn giải thích: {sources}",
        "",
        "## 3. Cấu trúc envelope JSON chung",
        "",
        "Cả sáu file là JSON object mã hóa UTF-8 có `meta` và một collection key dạng số nhiều. "
        "`meta` thực tế chỉ có `count`, `type`, `version`; `meta.count` khớp độ dài collection ở cả sáu file. "
        "Snapshot không có field status/error cho collection.",
        "",
        "| Loại object | Tệp | Khóa collection | Khóa top-level | Số record | Field trong meta |",
        "| --- | --- | --- | --- | ---: | --- |",
    ]
    for kind in sorted(envelopes):
        envelope = envelopes[kind]
        lines.append(
            f"| `{kind}` | `{envelope['file']}` | `{envelope['collection_key']}` | "
            f"{', '.join(envelope['top_level_keys'])} | {envelope['record_count']} | "
            f"{', '.join(envelope['meta']['keys'])} |"
        )
    lines.extend(
        [
            "",
            "Kiểu mã hóa và key-set chính xác của record nằm trong inventory máy đọc được: "
            "`reports/generated/seamless-raw-field-inventory.json`.",
            "",
            "## 4. Quy ước đọc các field quan trọng",
            "",
            "### 4.1 `ObjectIdentifier`",
            "",
            "`ObjectIdentifier` nằm ở top-level của record và là định danh mà output của "
            "BloodHound/SharpHound dùng để nhận diện object hiện tại. Trong snapshot này, auditor "
            f"quan sát {refs['object_identifier_records']} record, {refs['unique_object_identifiers']} giá trị unique; "
            f"shape gồm SID-like ({refs['identifier_formats'].get('sid-like', 0)}), GUID-like "
            f"({refs['identifier_formats'].get('guid-like', 0)}) và domain/composite-like "
            f"({refs['identifier_formats'].get('domain-like', 0)}).",
            "",
            "Cách đọc: đây là object identifier ở output collector, được các field reference khác "
            "dùng để trỏ tới object trong cùng snapshot. Nó không nên được gọi ngay là canonical "
            "project identity: snapshot có một duplicate Group identifier, có reference chưa resolve, "
            "và scope/external policy vẫn là câu hỏi riêng.",
            "",
            "Nếu một record có `ObjectIdentifier = G` thì chỉ có thể kết luận collector đã xuất "
            "record đó dưới identifier G. Việc G có phải một object AD duy nhất, một boundary, hay "
            "một identity canonical sau reconciliation là interpretation downstream.",
            "",
            "### 4.2 `Properties`",
            "",
            "`Properties` là object gom các thuộc tính descriptive/state mà collector xuất cho object. "
            "Một số field gần với thuộc tính directory; một số field là cờ/nhãn hoặc kết quả normalize "
            "của collector. Không được giả định mọi key trong `Properties` là raw LDAP attribute nguyên bản.",
            "",
            "Các subfield được giải thích theo từng loại object trong các phần tiếp theo; bảng đo lường "
            "vẫn giữ toàn bộ path, type, present/missing/null/empty/non-empty và value shape. "
            "`Properties.domainsid` không xuất hiện trong verified snapshot hiện tại.",
            "",
            "### 4.3 `Aces[]` dùng chung cho các object kind",
            "",
            "Khi `Aces[]` xuất hiện trong một record, mỗi element phải được đọc theo hướng: trustee/principal P — được collector phân loại và gắn một nhãn quyền — trên object hiện tại O. `PrincipalSID` là reference-shaped identity của trustee, `PrincipalType` là nhãn object kind, `RightName` là nhãn quyền đã được collector normalize, còn `IsInherited` là cờ inherited do collector xuất. `AceType` được inventory riêng vì snapshot cho thấy value behavior không đồng nhất giữa các object kind.",
            "",
            "Tầng raw là một mảng ACE-shaped object; tầng collector là diễn giải trustee/quyền trên object O; tầng project chỉ nên xem đây là candidate permission evidence sau khi đối chiếu Windows security descriptor/DACL và policy. Không được coi `RightName` là raw access mask hoặc tự dựng canonical edge/attack technique từ field name.",
            "",
        ]
    )

    object_sections = {
        "User": (
            "users.json",
            "File này chứa các object mà collector phân loại là User trong snapshot Active Directory. "
            "Mỗi record đại diện cho một User object được collector quan sát tại thời điểm collection. "
            "Record có thể chứa thuộc tính descriptive/state cùng các cấu trúc ACL, delegation và "
            "reference đã được collector tổng hợp; không phải field nào cũng là LDAP raw attribute.",
            "Một User record biểu diễn một account/object ở directory snapshot. `Properties` mô tả "
            "account, còn `Aces`, `PrimaryGroupSid`, `AllowedToDelegate`, `SPNTargets` và "
            "`HasSIDHistory` là các primitive/reference được collector đưa vào cùng record.",
        ),
        "Group": (
            "groups.json",
            "File này chứa các object mà collector phân loại là Group. Mỗi record là một Group object "
            "và có thể bao gồm `Members` để mô tả membership trực tiếp cùng `Aces` mô tả quyền được "
            "collector normalize trên Group hiện tại.",
            "Group record là parent/container ở góc nhìn của `Members`: phần tử trong `Members[]` "
            "trỏ tới principal child. Nếu child là Group khác thì raw shape có thể biểu diễn group nesting; "
            "không tự nói về attack behavior.",
        ),
        "Computer": (
            "computers.json",
            "File này chứa các object mà collector phân loại là Computer. Record có cả thuộc tính "
            "account/host và các primitive host-scoped như local-group membership, RDP/PowerShell "
            "membership-shaped arrays, ACL và session collection.",
            "Computer record luôn là scope của host hiện tại. Một principal xuất hiện trong array của "
            "Computer C trước hết phải được đọc là observation gắn với C, không phải relationship toàn cục.",
        ),
        "OU": (
            "ous.json",
            "File này chứa các object mà collector phân loại là Organizational Unit (OU). Record mô tả "
            "container trong hierarchy, các object member/reference, GPO link và ACL của OU.",
            "OU record là một node/container directory. `ChildOus`, `Users`, `Computers` và `Links` "
            "là các reference/hierarchy evidence; chúng không tự tạo resultant policy hoặc quyền hiệu lực.",
        ),
        "GPO": (
            "gpos.json",
            "File này chứa Group Policy Object mà collector quan sát trong AD. Record mô tả GPO object, "
            "ACL và một số thuộc tính như `gpcpath`; việc link tới domain/OU được thể hiện ở container record.",
            "GPO tồn tại, GPO được link, nội dung policy và resultant policy trên host là bốn khái niệm "
            "khác nhau. Snapshot Phase 1 chỉ chứng minh phần record/reference đã xuất.",
        ),
        "Domain": (
            "domains.json",
            "File này chứa object domain mà collector phân loại là Domain. Record gom thông tin domain, "
            "ACL, user/OU references, GPO links và trust collection nếu có.",
            "Domain record là source scope cho các array như `ChildOus`, `Users`, `Links`, `Trusts`. "
            "Trong snapshot này `Trusts` có mặt nhưng rỗng, nên không có trust element để diễn giải.",
        ),
    }
    property_section = (
        "### Các `Properties.*` quan trọng\n\n"
        "Bảng dưới đây là phần giải thích ngữ nghĩa cấp Tier B; mọi con số vẫn lấy từ inventory đã xác minh.\n\n"
    )

    order = ["User", "Group", "Computer", "OU", "GPO", "Domain"]
    section_number = 5
    for kind in order:
        envelope = envelopes[kind]
        file_name, file_meaning, record_meaning = object_sections[kind]
        lines.extend(
            [
                f"## {section_number}. `{file_name}` — {kind}",
                "",
                "### File này biểu diễn cái gì?",
                "",
                file_meaning,
                "",
                "### Cấu trúc envelope và một record",
                "",
                f"File được đọc qua `{envelope['raw_file_reference']}`, mã hóa `{envelope['encoding']}`, "
                f"collection key `{envelope['collection_key']}`, gồm `{envelope['record_count']}` record. "
                f"Top-level keys: `{', '.join(envelope['top_level_keys'])}`.",
                "",
                record_meaning,
                "",
                "### Các field chính",
                "",
                "`ObjectIdentifier` và container `Properties` dùng quy ước semantic chung ở §4; phần này tập trung vào các subfield và primitive có ý nghĩa riêng cho object kind này.",
                "",
            ]
        )
        lines.extend(
            _semantic_card(
                report,
                kind,
                "ObjectIdentifier",
                "ObjectIdentifier",
                "Chuỗi nằm ở top-level record, không nằm trong `Properties`.",
                "Đây là identifier mà output collector dùng để gắn record hiện tại và để các reference khác trỏ tới.",
                "Project có thể dùng nó làm raw reference key sau khi giữ nguyên scope, duplicate và unresolved behavior.",
                "record hiện tại được xuất dưới một identifier cụ thể và identifier có thể được dùng để exact-match reference.",
                "canonical identity duy nhất, boundary policy, hay ý nghĩa attack/privilege.",
                "Cao cho raw shape; trung bình cho semantics ngoài output collector.",
                "Raw snapshot; SharpHound output structure; [mã nguồn SharpHound](https://github.com/SpecterOps/SharpHound).",
            )
        )
        lines.extend(
            _semantic_card(
                report,
                kind,
                "Properties",
                "Properties",
                "Object lồng trong record, chứa các key descriptive/state của object.",
                "Collector gom thuộc tính directory và các cờ/nhãn đã normalize vào nhóm này; cần đọc từng subfield, không suy nghĩa từ tên `Properties` chung.",
                "Dùng như provenance của thuộc tính raw/collector sau khi phân biệt subfield nào là descriptive, state, label hay reference.",
                "các thuộc tính và shape đã được collector xuất ở thời điểm collection.",
                "account đang hoạt động, quyền hiệu lực, hay resultant policy.",
                "Cao cho container; từng subfield được đánh giá riêng.",
                "Raw snapshot; [mã nguồn SharpHound](https://github.com/SpecterOps/SharpHound).",
            )
        )
        property_rows = _property_table(report, kind)
        if property_rows:
            lines.extend([property_section, *property_rows, ""])
        if kind in {"User", "Computer"}:
            lines.extend(
                _semantic_card(
                    report,
                    kind,
                    "PrimaryGroupSid",
                    "PrimaryGroupSid",
                    "Chuỗi SID-like ở top-level record; trong snapshot field này có mặt ở User và Computer.",
                    "Collector xuất SID của primary group gắn với object theo schema.",
                    "Đây là primary-group reference evidence, không phải danh sách toàn bộ group membership.",
                    "một reference-shaped SID tới primary group của object.",
                    "membership đầy đủ, quyền hiệu lực, hay canonical `MemberOf` closure.",
                    "Cao cho raw reference; semantics membership cần policy AD riêng.",
                    "Raw snapshot; Windows/AD primary-group semantics cần đối chiếu riêng.",
                )
            )
        if kind == "Group":
            lines.extend(
                _semantic_card(
                    report,
                    kind,
                    "Members",
                    "Members[]",
                    "Mảng trong record Group; mỗi phần tử là object có `MemberId` và `MemberType`.",
                    "Collector ghi nhận principal là thành viên trực tiếp của Group hiện tại. Với `MemberType=Group`, phần tử có thể là group nesting.",
                    "Raw membership observation → candidate direct `MemberOf` structural evidence. Bước project interpretation vẫn phải giữ direction và reconciliation policy.",
                    "G có một reference trực tiếp tới principal P khi phần tử chứa `MemberId=P`.",
                    "transitive membership, effective authorization, attack path, hay quyền runtime.",
                    "Cao cho quan sát direct membership; trung bình cho semantics downstream.",
                    "Raw snapshot; group/member schema của SharpHound; [SpecterOps group members](https://bloodhound.specterops.io/reference/groups/get-group-entity-members).",
                )
            )
            lines.extend(
                [
                    "**Cách đọc một phần tử:** nếu record Group có identifier `G` và `Members = [{MemberId: U, MemberType: User}]`, câu raw-data tương ứng là: “collector ghi nhận principal `U` là thành viên trực tiếp của Group `G`”. Nếu `MemberType=Group`, câu tương ứng là “collector ghi nhận Group `U` là thành viên trực tiếp của Group `G`”, tức một nesting observation.",
                    "",
                    "**Các subfield của `Members[]`:**",
                    "",
                    "`MemberId` là reference tới principal child, không phải tên hiển thị. `MemberType` là nhãn object kind do collector xuất cho reference đó. Vì vậy `Members[]` được đọc theo hướng parent Group → member principal; bước project có thể tạo candidate direct `MemberOf` evidence nhưng không được tự mở rộng thành transitive membership hay attack behavior.",
                    "",
                    *_nested_field_table(
                        report,
                        kind,
                        [
                            (
                                "Members[].MemberId",
                                "Định danh của principal được collector ghi nhận là thành viên trực tiếp của Group hiện tại.",
                                "một membership reference từ Group hiện tại tới principal P; exact-match có thể resolve P trong snapshot.",
                                "full group closure, effective authorization, hay quyền runtime.",
                                "Reference string được sanitize; unresolved reference không bị gán nhãn external.",
                            ),
                            (
                                "Members[].MemberType",
                                "Loại object mà collector gắn cho principal được tham chiếu.",
                                "cách phân loại principal để đọc reference, ví dụ `User`, `Group` hoặc `Computer`.",
                                "identity duy nhất hoặc sự tồn tại của target nếu không resolve được identifier.",
                                "Giá trị categorical được thống kê riêng trong inventory.",
                            ),
                        ],
                    ),
                    "",
                    "**Bảng giá trị `MemberType`:**",
                    "",
                    "| Giá trị | Cách đọc |",
                    "| --- | --- |",
                    "| `User` | reference trỏ tới object được collector phân loại là User. |",
                    "| `Group` | reference trỏ tới Group; trong `Members[]` có thể biểu diễn group nesting. |",
                    "| `Computer` | reference trỏ tới Computer object. |",
                    "",
                ]
            )
        if kind == "Computer":
            computer_cards = [
                (
                    "LocalAdmins[]",
                    "LocalAdmins[]",
                    "Mảng trong record Computer C; phần tử là principal reference có `MemberId` và `MemberType`.",
                    "SharpHound/collector query membership của local Administrators group trên host C và xuất principal P theo primitive local-group enumeration.",
                    "Raw host-scoped local Administrators membership evidence → có thể hỗ trợ candidate `AdminTo` khi identity, provenance và structural policy đủ điều kiện. Network/service reachability là runtime predicate, không phải điều kiện để structural evidence tồn tại.",
                    "P được collector ghi nhận trong local Administrators của C.",
                    "verified `AdminTo`, mọi quyền local-admin hiệu lực trong runtime, host online, hay attack thành công.",
                    "Cao cho raw membership; canonical promotion còn phụ thuộc structural policy.",
                ),
                (
                    "DcomUsers[]",
                    "DcomUsers[]",
                    "Mảng nằm trong record Computer C; element là principal reference theo shape raw quan sát được.",
                    "Collector ghi nhận principal trong local Distributed COM Users group của host C.",
                    "Đây là host-scoped local-group membership evidence. BloodHound có primitive/relationship tương ứng, nhưng project không coi riêng raw membership này là đủ cho canonical relationship.",
                    "P được collector ghi nhận trong primitive DCOM Users của C.",
                    "DCOM service state, remote activation thành công, effective access, hay attack behavior.",
                    "Cao cho raw membership; canonical promotion cần structural policy.",
                ),
                (
                    "RemoteDesktopUsers[]",
                    "RemoteDesktopUsers[]",
                    "Mảng nằm trong Computer C; mỗi phần tử tham chiếu principal và có `MemberType`.",
                    "Collector ghi nhận membership thu được từ local Remote Desktop Users group trên host C.",
                    "BloodHound truyền thống sử dụng primitive này cho `CanRDP`, nhưng project hiện tại không coi riêng membership này là đủ cho canonical `CanRDP`; cần giữ tách biệt với user-right assignment và các predicate khác.",
                    "P xuất hiện trong primitive Remote Desktop Users của C.",
                    "`SeRemoteInteractiveLogonRight`, absence of `SeDenyRemoteInteractiveLogonRight`, service state, TCP reachability, authentication success, hoặc canonical `CanRDP`.",
                    "Cao cho raw membership/host scope; chưa đủ cho canonical access semantics.",
                ),
                (
                    "PSRemoteUsers[]",
                    "PSRemoteUsers[]",
                    "Mảng nằm trong Computer C; phần tử là principal reference.",
                    "Collector ghi nhận membership thu được từ local Remote Management Users group trên host C, là primitive liên quan tới PowerShell remoting.",
                    "BloodHound truyền thống sử dụng primitive này cho `CanPSRemote`; project có thể dùng làm structural evidence nhưng không coi riêng field này là canonical edge hoàn chỉnh.",
                    "P xuất hiện trong local Remote Management Users membership evidence của C.",
                    "WinRM service, endpoint policy, network reachability, deny policy, hay remoting thành công.",
                    "Cao cho raw membership/host scope; canonical promotion cần structural policy.",
                ),
                (
                    "Sessions[]",
                    "Sessions",
                    "Mảng nằm trong Computer C. Snapshot hiện tại có field ở cả 100 Computer record nhưng không có phần tử.",
                    "Collector dành field cho session-shaped observations gắn với host C; không có element thực tế để xác minh subfield/direction trong snapshot này.",
                    "Không có session evidence để map thành `HasSession`; empty không được coi là negative runtime fact.",
                    "snapshot không quan sát element session nào trong các record Computer.",
                    "không có session tồn tại, credential exposure, observed activity, hay absence of logon.",
                    "Cao cho empty measurement; Unknown cho collection completeness.",
                ),
                (
                    "AllowedToDelegate[]",
                    "AllowedToDelegate",
                    "Mảng delegation-shaped; trong User và Computer snapshot đều hiện diện nhưng rỗng.",
                    "Collector dành field cho delegation target/principal references; snapshot không có element để xác minh shape cụ thể.",
                    "Không tạo delegation edge ở Phase 1; chỉ ghi nhận collection rỗng.",
                    "field có mặt và không có element quan sát được.",
                    "delegation không tồn tại, method đã chạy đầy đủ, hay một kỹ thuật tấn công.",
                    "Cao cho empty; Unknown cho nguyên nhân empty.",
                ),
                (
                    "AllowedToAct[]",
                    "AllowedToAct",
                    "Mảng delegation-shaped trong Computer; tất cả record Computer quan sát được đều rỗng.",
                    "Tên field phù hợp với primitive delegation nhưng raw snapshot rỗng nên không đủ evidence để xác minh semantics cụ thể.",
                    "Không tạo RBCD/delegation edge và không sửa canonical behavior.",
                    "field có mặt nhưng không có element.",
                    "RBCD không tồn tại hoặc collector đã kiểm tra đầy đủ.",
                    "Cao cho raw empty; Unknown cho collection status.",
                ),
            ]
            for card in computer_cards:
                card_sources = {
                    "LocalAdmins[]": "[SpecterOps computer admins](https://bloodhound.specterops.io/reference/computers/get-computer-entity-admins)",
                    "DcomUsers[]": "[SpecterOps computer DCOM users](https://bloodhound.specterops.io/reference/computers/get-computer-entity-dcom-users)",
                    "RemoteDesktopUsers[]": "[SpecterOps computer RDP users](https://bloodhound.specterops.io/reference/computers/get-computer-entity-rdp-users)",
                    "PSRemoteUsers[]": "[SpecterOps CanPSRemote](https://bloodhound.specterops.io/resources/edges/can-ps-remote)",
                }
                card_source = f"Raw snapshot; {card_sources.get(card[0], 'collector documentation')} và collector implementation/schema."
                if card[0] == "RemoteDesktopUsers[]":
                    card_source += " [Microsoft account rights](https://learn.microsoft.com/en-us/windows/win32/secauthz/account-rights-constants) chỉ dùng để đối chiếu các quyền Windows liên quan tới RDP."
                lines.extend(
                    _semantic_card(
                        report,
                        kind,
                        card[1],
                        card[0],
                        card[2],
                        card[3],
                        card[4],
                        card[5],
                        card[6],
                        card[7],
                        card_source,
                    )
                )
            lines.extend(
                [
                    "**Direction của `Sessions[]`:** nếu tương lai có record dạng Computer `C` chứa session reference tới User `U`, raw reading tối thiểu là “collector quan sát một session/reference liên quan tới `U` trên `C`”. Đây là host-scoped observation; không được đọc thành “U có credential để dump” hay “đã có attack”.",
                    "",
                    "`DcomUsers[]` có xuất hiện ở một Computer và đã được giải thích như host-scoped membership-shaped evidence. `PrivilegedSessions` và `RegistrySessions` không xuất hiện trong các record Computer của verified snapshot; việc không có key này không được đọc thành collection âm hoặc chứng minh không có session tương ứng.",
                    "",
                ]
            )
        if kind == "User":
            lines.extend(
                _semantic_card(
                    report,
                    kind,
                    "Aces",
                    "Aces[]",
                    "Mảng trong object record; element shape quan sát được là object gồm `AceType`, `IsInherited`, `PrincipalSID`, `PrincipalType`, `RightName`.",
                    "Collector biểu diễn trustee/principal nào có nhãn quyền nào trên object hiện tại. `RightName` là collector/BloodHound normalization, không phải raw Windows access mask.",
                    "ACE-shaped evidence → candidate permission evidence. Project phải tách Windows security descriptor/DACL → collector interpretation → canonical relationship.",
                    "Ví dụ `PrincipalSID=P`, `RightName=GenericAll` được đọc là collector đang biểu diễn P có một quyền được normalize thành `GenericAll` trên object hiện tại.",
                    "effective access, thứ tự allow/deny đầy đủ, exploitability, canonical edge, hay attack technique.",
                    "Cao cho cấu trúc ACE; trung bình cho semantics quyền hiệu lực.",
                    "Raw snapshot; [Microsoft Access Control Entries](https://learn.microsoft.com/en-us/windows/win32/secauthz/access-control-entries); [Microsoft DACLs and ACEs](https://learn.microsoft.com/en-us/windows/win32/secauthz/dacls-and-aces).",
                )
            )
            lines.extend(
                [
                    "**Các subfield của `Aces[]`:**",
                    "",
                    "Một element ACE phải được đọc theo hướng: principal/trustee P — được collector phân loại và gắn một nhãn quyền — trên object hiện tại O. Chuỗi diễn giải này không đồng nghĩa với việc raw JSON chứa nguyên Windows security descriptor hoặc access mask.",
                    "",
                    *_nested_field_table(
                        report,
                        kind,
                        [
                            (
                                "Aces[].PrincipalSID",
                                "SID-like hoặc reference-shaped string của trustee/principal trong ACE.",
                                "ACE đang gắn evidence quyền với principal P trên object hiện tại.",
                                "principal đã resolve đầy đủ, effective access, hoặc target không nằm ngoài scope.",
                                "Exact-match và unresolved count được đo ở phần reference archaeology.",
                            ),
                            (
                                "Aces[].PrincipalType",
                                "Nhãn object kind do collector gắn cho trustee/principal.",
                                "cách collector phân loại trustee, ví dụ `User`, `Group`, `Computer`.",
                                "SID resolution, allow/deny semantics, hoặc quyền hiệu lực.",
                                "Không thay thế việc resolve `PrincipalSID`.",
                            ),
                            (
                                "Aces[].RightName",
                                "Nhãn quyền đã normalize; snapshot quan sát các giá trị categorical an toàn.",
                                "collector diễn giải một ACE thành nhãn như `GenericAll`, `GenericWrite`, `Owner`, `WriteDacl`, `WriteOwner` hoặc `ExtendedRight`.",
                                "candidate permission evidence trên object hiện tại.",
                                "raw access mask, đầy đủ điều kiện allow/deny, exploitability, hoặc attack technique.",
                                "Chi tiết cách đọc từng giá trị nằm ngay dưới bảng này.",
                            ),
                            (
                                "Aces[].AceType",
                                "Field là string; nhiều object kind có toàn bộ element rỗng, còn User có 2497 element không rỗng trong snapshot.",
                                "ý nghĩa cụ thể chưa xác minh đầy đủ; không được dùng field rỗng này để đoán allow/deny.",
                                "key `AceType` tồn tại trên các ACE element được quan sát; giá trị có thể rỗng hoặc mang collector-specific label như `All`. Snapshot không tự xác định semantics allow/deny của label này.",
                                "ACE là allow hay deny, thứ tự đánh giá, hoặc DACL hiệu lực.",
                                "Đây là open question cần collector/schema evidence bổ sung.",
                            ),
                            (
                                "Aces[].IsInherited",
                                "Boolean flag trên element ACE.",
                                "collector ghi nhận trạng thái inherited của ACE theo output schema.",
                                "nguồn inheritance đầy đủ, thứ tự kế thừa, hoặc effective permission sau khi merge ACL.",
                                "Không được coi `false` là chứng minh ACE độc lập khỏi mọi policy khác.",
                            ),
                        ],
                    ),
                    "",
                    *_ace_value_meanings(report, kind),
                    *_ace_type_value_meanings(report, kind),
                ]
            )
        if kind in {"OU", "Domain"}:
            for path, title, raw, collector, project, proves, not_prove in [
                (
                    "ChildOus",
                    "ChildOus[]",
                    "Mảng các identifier/reference tới OU con trong record OU/Domain.",
                    "Collector biểu diễn hierarchy reference; nếu O có `ChildOus=[O2]`, raw reading là O2 được ghi nhận là OU con trực tiếp của O.",
                    "Candidate directory hierarchy evidence; không tự tính full transitive containment.",
                    "reference/hierarchy observation giữa parent record và child OU.",
                    "mọi descendant, inheritance policy, hay effective permission.",
                ),
                (
                    "Users",
                    "Users[]",
                    "Mảng identifier/reference tới User trong OU/Domain record.",
                    "Collector xuất các User reference thuộc scope container đó.",
                    "Candidate containment/scope evidence; không tự chứng minh logon, policy application hoặc privilege.",
                    "record container chứa reference User.",
                    "User đang active, toàn bộ membership, hay resultant GPO.",
                ),
                (
                    "Computers",
                    "Computers[]",
                    "Mảng identifier/reference tới Computer trong OU record; Domain array hiện diện nhưng rỗng.",
                    "Collector xuất Computer reference gắn với container.",
                    "Candidate OU/container scope evidence; không tự chứng minh host online hay policy hiệu lực.",
                    "Computer được snapshot biểu diễn trong collection của container.",
                    "network reachability, current OU membership ngoài snapshot, hay resultant policy.",
                ),
                (
                    "Links",
                    "Links[]",
                    "Mảng object gồm `Guid` và `IsEnforced` trong OU/Domain record.",
                    "Collector biểu diễn GPO link gắn với container; `Guid` là reference-shaped GPO identifier và `IsEnforced` là thuộc tính link được xuất.",
                    "Candidate link/scope evidence; cần tách GPO tồn tại, link, policy settings và resultant policy.",
                    "container có một link object tới GPO theo GUID đã quan sát.",
                    "policy setting cụ thể đã áp dụng lên User/Computer hay thứ tự xử lý đầy đủ.",
                ),
            ]:
                lines.extend(
                    _semantic_card(
                        report,
                        kind,
                        path,
                        title,
                        raw,
                        collector,
                        project,
                        proves,
                        not_prove,
                        "Cao cho raw reference; trung bình cho hierarchy/policy semantics.",
                        "Raw snapshot; [Microsoft Group Policy processing](https://learn.microsoft.com/en-us/windows-server/identity/ad-ds/manage/group-policy/group-policy-processing).",
                    )
                )
        if kind == "Domain":
            lines.extend(
                _semantic_card(
                    report,
                    kind,
                    "Trusts",
                    "Trusts[]",
                    "Mảng nằm trong Domain record; snapshot hiện tại có field nhưng độ dài bằng 0.",
                    "Khi có element, collector thường dùng cấu trúc này để xuất trust relationship giữa source domain hiện tại và target domain/reference; nhưng snapshot này không có element để xác minh key/value cụ thể.",
                    "Không dựng trust edge, không đoán direction/type/SID filtering từ field name hoặc empty array.",
                    "chỉ chứng minh field Trusts hiện diện và không có trust element được quan sát trong bytes này.",
                    "không có trust, trust bị disabled, method không chạy, hay collection thành công rỗng.",
                    "Cao cho empty measurement; Unknown cho trust completeness.",
                    "Raw snapshot; [Microsoft trusted domain information](https://learn.microsoft.com/en-us/windows/win32/api/ntsecapi/ns-ntsecapi-trusted_domain_information_ex); [MS-ADTS trustDirection](https://learn.microsoft.com/en-us/openspecs/windows_protocols/ms-adts/5026a939-44ba-47b2-99cf-386a9e674b04).",
                )
            )
            lines.extend(
                [
                    "**Direction semantics cần giữ cho phase sau:** nếu Trusts có source domain `D1` và target `D2`, các nhãn inbound/outbound phải được đọc tương đối với phía đang chứa record; `inbound` và `outbound` không phải nhãn tuyệt đối độc lập với source. Microsoft mô tả `bidirectional` là cả hai chiều. Vì snapshot hiện tại không có element, đây là policy đọc cho dữ liệu tương lai, không phải observation của SEAMLESS.",
                    "",
                ]
            )
        if kind == "GPO":
            lines.extend(
                [
                    "**Phân biệt bốn khái niệm:** record GPO tồn tại trong AD; `Links[]` ở OU/Domain ghi nhận scope link; policy settings là nội dung policy; resultant policy là kết quả sau hierarchy, inheritance, enforced/blocking và xử lý trên client. Snapshot Phase 1 chỉ đo hai lớp đầu khi reference có mặt.",
                    "",
                ]
            )
        lines.extend(
            [
                "### Giá trị categorical và cách đọc",
                "",
                *_categorical_meanings(report, kind),
                "### Bảng kiểm kê từng field",
                "",
                "Bảng sau là phép đo đầy đủ; nó không thay thế phần giải thích ngữ nghĩa ở trên.",
                "",
                *_field_table(report, kind),
                "",
                "### Điều snapshot cho phép và không cho phép kết luận",
                "",
                "Snapshot cho phép nói collector đã xuất record/field/reference với shape và cardinality "
                "đã đo. Snapshot không tự phân biệt successful empty, access denied, method not run, "
                "schema absent hay incomplete collection khi không có status/error evidence.",
                "",
            ]
        )
        section_number += 1

    lines.extend(
        [
            "## 11. Khảo cổ identity/reference giữa các file",
            "",
            f"Có `{refs['object_identifier_records']}` record và `{refs['unique_object_identifiers']}` "
            f"identifier unique; không có record thiếu `ObjectIdentifier`, không có identifier xuất hiện "
            "ở nhiều object kind khác nhau. Có một duplicate identifier group trong Group, được giữ lại "
            "bằng safe locator chứ không merge.",
            "",
            f"Auditor nhận diện `{refs['candidate_reference_count']}` scalar observation có hình dạng reference; "
            f"`{refs['resolved_reference_count']}` exact-match một `ObjectIdentifier` trong snapshot và "
            f"`{refs['unresolved_reference_count']}` chưa match. Hai observation unresolved đều nằm ở "
            "`Group.Members[].MemberId`; chúng được gọi là unresolved, không tự gắn nhãn external, "
            "boundary, dangling hay invalid.",
            "",
            "Các reference được đo gồm `Members[].MemberId`, ACE principal, `PrimaryGroupSid`, "
            "host-local membership references, `ChildOus[]`, `Users[]`, `Computers[]` và `Links[].Guid`. "
            "Matching là exact string matching trên snapshot; chưa có canonicalization hay identity resolution.",
            "",
            *_identity_archaeology_lines(report),
            *_duplicate_archaeology_lines(report),
            "## 12. Missing / null / empty và giới hạn collection",
            "",
            "`missing`, `null`, array rỗng và array không rỗng được đo riêng. Với path là phần tử của array, "
            "inventory thêm `parent_records_with_elements`, `parent_records_without_elements`, "
            "`parent_records_missing` và một `presence_scope` rõ ràng. Vì vậy `Computer.LocalAdmins[]` "
            "không báo thiếu ở 99 host; nó báo parent array có mặt, có element ở 1 host và không có element ở 99 host.",
            "",
            "Không có status/error/access-denied metadata trong raw snapshot. Vì vậy không được đọc "
            "array rỗng thành negative fact. Đặc biệt, không thể phân biệt “không có quan hệ” với "
            "“collector không quan sát được quan hệ” chỉ bằng field hiện tại.",
            "",
            "## 13. Consumer hiện tại và phần remediation có giới hạn",
            "",
            "`scripts/eda_dataset_analysis.py` hiện đọc `Members`, `Aces`, `LocalAdmins`, "
            "`RemoteDesktopUsers`, `PSRemoteUsers` và `Sessions`. EDA hiện báo cáo các host array "
            "này như raw/evidence primitive riêng, giữ trạng thái completeness unknown và không dùng "
            "`RemoteDesktopUsers[]` để đếm verified `CanRDP`. Verified `CanRDP` vẫn cần effective RDU "
            "membership, `SeRemoteInteractiveLogonRight` và known-negative `SeDenyRemoteInteractiveLogonRight`. "
            "Positive `LocalAdmins[]` và `PSRemoteUsers[]` là host-bound structural evidence theo accepted #80; "
            "empty/unobserved arrays không chứng minh relationship absence. Production parser/builder "
            "canonicalization vẫn thuộc #44/#45; raw audit này không triển khai parser, builder, canonical "
            "contract hoặc attack-semantics behavior.",
            "",
            "## 14. Đầu vào cho các phase tiếp theo của #94",
            "",
            "- Dùng manifest và raw bytes này làm source-of-truth bất biến.",
            "- Giữ unresolved member references cho identity/boundary policy riêng.",
            "- Bổ sung collector status/error evidence trước khi diễn giải completeness.",
            "- Đưa các primitive host-scoped vào review #79/#80 nhưng không biến chúng thành canonical edge ở Phase 1.",
            "- Để #44/#45 xử lý parser/host-access semantics sau khi có policy approved; không bypass loader time-provenance decision.",
            "- Dùng #47 cross-dataset comparison chỉ khi provenance, collector scope và semantics được căn chỉnh.",
            "- Windows telemetry, #79 Phase B và remediation graph builder/parser nằm ngoài phạm vi.",
            "",
            "## 15. Tái tạo kết quả",
            "",
            "```bash",
            "python scripts/audit_seamless_raw.py \\",
            "  --raw-dir data/raw/SEAMLESS \\",
            "  --manifest data/samples/manifests/seamless-raw-v1.json \\",
            "  --output reports/generated/seamless-raw-field-inventory.json",
            "```",
            "",
            "JSON generated nằm local-only trong `reports/generated/` theo convention repository; "
            "tài liệu này chỉ chứa observation đã sanitize và phần giải thích ngữ nghĩa, không chứa raw AD identity.",
            "",
        ]
    )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-dir", type=Path, default=DEFAULT_RAW_DIR)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--markdown-output", type=Path, default=DEFAULT_MARKDOWN_OUTPUT)
    args = parser.parse_args(argv)
    try:
        report = audit_snapshot(args.raw_dir, args.manifest)
        write_report(report, args.output)
        args.markdown_output.write_text(render_markdown(report), encoding="utf-8")
    except Exception as exc:  # CLI boundary: keep failures concise and non-sensitive.
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    print(
        json.dumps(
            {
                "status": "generated",
                "output": str(args.output),
                "snapshot_id": report["snapshot_id"],
                "field_count": len(report["field_inventory"]),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
