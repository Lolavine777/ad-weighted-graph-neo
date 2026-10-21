"""Raw-first forensic audit for the verified ``evtx_data.csv`` snapshot.

This script deliberately stops at CSV anatomy and event-specific qualifiers.  It
does not feed telemetry to the graph builder, create relationships, or map an
event ID to an ATT&CK technique.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import ipaddress
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime
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

DEFAULT_RAW_DIR = ROOT / "data/raw/telemetry"
DEFAULT_MANIFEST = ROOT / "data/samples/manifests/telemetry-raw-v1.json"
DEFAULT_OUTPUT = ROOT / "reports/generated/windows-telemetry-raw-field-inventory.json"

SELECTED_EVENTS = (
    "1",
    "3",
    "10",
    "11",
    "13",
    "1149",
    "131",
    "169",
    "193",
    "91",
    "4104",
    "4624",
    "4625",
    "4634",
    "4648",
    "4662",
    "4672",
    "4724",
    "4732",
    "5136",
    "5145",
    "5156",
)

SENSITIVE_FIELD_RE = re.compile(
    r"(?:script|command|payload|attributevalue|taskcontent|destination|consumer|query)",
    re.I,
)

SYSTEM_FIELDS = {
    "Channel",
    "Computer",
    "EventID",
    "EventRecordID",
    "Guid",
    "Keywords",
    "Level",
    "Opcode",
    "ProcessID",
    "ProviderName",
    "SystemTime",
    "Task",
    "ThreadID",
    "Version",
}


def _provenance(field: str) -> tuple[str, str]:
    if field == "":
        return "csv_transformation", "unnamed row ordinal; not a Windows event field"
    if field == "EVTX_FileName":
        return "upstream_annotation", "source sample filename carried by the dataset"
    if field == "EVTX_Tactic":
        return "upstream_annotation", "dataset tactic label; not emitted by Windows event XML"
    if field in SYSTEM_FIELDS:
        return "event_envelope", "Windows/Event System or log-context metadata flattened into CSV"
    if field.startswith("{"):
        return (
            "parser_preserved_payload_name",
            "namespaced event payload name preserved by CSV exporter",
        )
    return "event_payload_or_provider_field", "provider-specific event payload or provider metadata"


def _shape(value: str) -> str:
    if value == "":
        return "empty"
    if re.fullmatch(r"0x[0-9A-Fa-f]+", value):
        return "hex-like"
    if re.fullmatch(r"-?\d+", value):
        return "integer-like"
    if re.fullmatch(r"S-\d(?:-\d+)+", value):
        return "SID-like"
    if re.fullmatch(r"\{?[0-9A-Fa-f]{8}(?:-[0-9A-Fa-f]{4}){3}-[0-9A-Fa-f]{12}\}?", value):
        return "GUID-like"
    try:
        ipaddress.ip_address(value)
        return "IP-like"
    except ValueError:
        pass
    for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S"):
        try:
            datetime.strptime(value, fmt)
            return "datetime-like"
        except ValueError:
            pass
    if "\\" in value or "/" in value:
        return "path-or-namespace-like"
    return "string"


def _safe_values(field: str, values: Counter[str]) -> list[dict[str, Any]]:
    """Keep small categorical values; never publish payload/script content."""
    if SENSITIVE_FIELD_RE.search(field):
        return []
    if len(values) > 30:
        return []
    return [
        {"value": value[:80], "count": count}
        for value, count in values.most_common(12)
        if value and len(value) <= 80 and "\n" not in value
    ]


def _column_inventory(fieldnames: list[str], rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    inventory = []
    for index, field in enumerate(fieldnames):
        values = Counter(row.get(field, "") for row in rows)
        nonempty = sum(count for value, count in values.items() if value != "")
        provenance_class, provenance_note = _provenance(field)
        inventory.append(
            {
                "index": index,
                "field": field,
                "provenance_class": provenance_class,
                "provenance_note": provenance_note,
                "csv_type": "string",
                "present_rows": nonempty,
                "empty_rows": len(rows) - nonempty,
                "unique_nonempty_values": len([value for value in values if value != ""]),
                "value_shapes": dict(
                    sorted(Counter(_shape(value) for value in values if value).items())
                ),
                "safe_values": _safe_values(field, values),
            }
        )
    return inventory


def _event_profile(event_id: str, rows: list[dict[str, str]]) -> dict[str, Any]:
    selected = [row for row in rows if row.get("EventID") == event_id]
    fields = Counter()
    for row in selected:
        fields.update(field for field, value in row.items() if field and value != "")
    field_presence = {
        field: fields[field] for field in sorted(fields) if field not in {"EventID", ""}
    }
    return {
        "rows": len(selected),
        "providers": dict(Counter(row["ProviderName"] for row in selected)),
        "channels": dict(Counter(row["Channel"] for row in selected)),
        "upstream_tactics": dict(Counter(row["EVTX_Tactic"] for row in selected)),
        "nonempty_fields": field_presence,
    }


def audit(
    raw_dir: Path = DEFAULT_RAW_DIR, manifest_path: Path = DEFAULT_MANIFEST
) -> dict[str, Any]:
    manifest = load_manifest(manifest_path)
    issues = verify_manifest(raw_dir, manifest)
    if issues:
        raise ValueError(f"telemetry snapshot failed manifest verification: {issues}")
    relative_path = next(
        entry["relative_path"]
        for entry in manifest["files"]
        if Path(entry["relative_path"]).name.lower() == "evtx_data.csv"
    )
    reference = raw_file_reference(manifest, relative_path)
    payload = read_verified_snapshot_file(raw_dir, manifest, reference)
    digest = hashlib.sha256(payload).hexdigest()
    text = payload.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text, newline=""))
    if reader.fieldnames is None:
        raise ValueError("CSV has no header")
    if len(reader.fieldnames) != len(set(reader.fieldnames)):
        raise ValueError("CSV contains duplicate column names")
    required_columns = {"EventID", "ProviderName", "Channel", "EVTX_Tactic"}
    missing_columns = sorted(required_columns - set(reader.fieldnames))
    if missing_columns:
        raise ValueError(f"CSV is missing required columns: {missing_columns}")
    rows = list(reader)
    if any(None in row or any(value is None for value in row.values()) for row in rows):
        raise ValueError("CSV row width does not match header width")

    event_counts = Counter(row["EventID"] for row in rows)
    provider_counts = Counter(row["ProviderName"] for row in rows)
    channel_counts = Counter(row["Channel"] for row in rows)
    tactic_counts = Counter(row["EVTX_Tactic"] for row in rows)
    provider_event_counts: dict[str, dict[str, int]] = defaultdict(Counter)
    for row in rows:
        provider_event_counts[row["ProviderName"]][row["EventID"]] += 1

    return {
        "audit": {
            "name": "windows-telemetry-raw-field-audit",
            "method": "manifest-verified bytes -> csv.DictReader -> field/value anatomy",
            "relationship_extraction": False,
            "event_id_to_technique_mapping": False,
        },
        "source": {
            "dataset_id": manifest["dataset_id"],
            "snapshot_id": manifest["snapshot_id"],
            "raw_file_reference": reference,
            "relative_path": relative_path,
            "size_bytes": len(payload),
            "sha256": digest,
            "manifest_verified": True,
            "encoding": "UTF-8 with BOM accepted; parsed as text CSV",
        },
        "csv": {
            "row_count": len(rows),
            "column_count": len(reader.fieldnames),
            "fieldnames": reader.fieldnames,
            "first_column_is_unnamed_row_ordinal": reader.fieldnames[0] == "",
            "column_inventory": _column_inventory(reader.fieldnames, rows),
        },
        "distributions": {
            "event_id": dict(event_counts.most_common()),
            "provider": dict(provider_counts.most_common()),
            "channel": dict(channel_counts.most_common()),
            "evtx_tactic_annotation": dict(tactic_counts.most_common()),
            "provider_event": {
                provider: dict(counts.most_common())
                for provider, counts in sorted(provider_event_counts.items())
            },
        },
        "selected_event_profiles": {
            event_id: _event_profile(event_id, rows)
            for event_id in SELECTED_EVENTS
            if event_id in event_counts
        },
        "empty_event_ids_in_snapshot": [
            event_id
            for event_id in ("4670", "4728", "4729", "4733", "4756")
            if event_id not in event_counts
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-dir", type=Path, default=DEFAULT_RAW_DIR)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    report = audit(args.raw_dir, args.manifest)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    print(
        json.dumps(
            {
                "output": str(args.output),
                "rows": report["csv"]["row_count"],
                "columns": report["csv"]["column_count"],
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
