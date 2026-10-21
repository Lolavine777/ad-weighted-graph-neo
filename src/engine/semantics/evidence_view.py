"""Counterfactual search evidence views; baseline records remain immutable."""

import hashlib
import json
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.data.manifest import raw_file_reference, read_verified_snapshot_file

from .models import StructuralRelationship


def digest(value: Any) -> str:
    return (
        "sha256:"
        + hashlib.sha256(
            json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
        ).hexdigest()
    )


@dataclass(frozen=True)
class EvidenceView:
    graph: dict
    audit: dict
    withheld_relationships: frozenset[StructuralRelationship]


def _resolve_raw_binding(specification, raw_dir, manifest):
    if raw_dir is None or manifest is None:
        raise ValueError("record SID/attribute mapping requires manifest-verified raw input")
    filename, pointer = specification["locator"].split("#", 1)
    payload = json.loads(
        read_verified_snapshot_file(
            Path(raw_dir), manifest, raw_file_reference(manifest, filename)
        ).decode("utf-8-sig")
    )
    tokens = pointer.strip("/").split("/")

    def resolve(parts):
        value = payload
        for token in parts:
            token = token.replace("~1", "/").replace("~0", "~")
            value = value[int(token)] if isinstance(value, list) else value[token]
        return value

    field = "Aces" if specification["kind"] == "withhold_structural_provenance" else "Properties"
    record = resolve(tokens[: tokens.index(field)])
    node_id = record.get("ObjectIdentifier") or record.get("Properties", {}).get("objectid")
    expected_id = specification.get("target", specification.get("node_id"))
    if node_id != expected_id:
        raise ValueError("raw locator record identity mismatch")
    value = resolve(tokens)
    if field == "Aces":
        if (
            value.get("PrincipalSID") != specification["source"]
            or value.get("RightName") != specification["relationship"]
        ):
            raise ValueError("raw locator ACL endpoints/right mismatch")
        matching_aces = [
            ace
            for ace in record["Aces"]
            if ace.get("PrincipalSID") == specification["source"]
            and ace.get("RightName") == specification["relationship"]
        ]
        if len(matching_aces) != 1:
            raise ValueError("ambiguous raw ACL support; exact canonical locator required")
    elif value is not True or tokens[-1] != "enabled":
        raise ValueError("raw enabled locator must resolve to true observation")
    return filename, node_id, manifest["snapshot_id"]


def _explicit_locator(record, locator):
    return (
        isinstance(record, str)
        and record == locator
        or isinstance(record, dict)
        and any(
            record.get(key) == locator
            for key in ("provenance_locator", "provenance_reference", "record_locator")
        )
    )


def _has_explicit_locator(record):
    return isinstance(record, str) or (
        isinstance(record, dict)
        and any(
            record.get(key)
            for key in ("provenance_locator", "provenance_reference", "record_locator")
        )
    )


def counterfactual_view(
    baseline: dict,
    specification: dict | None,
    *,
    case_id: str,
    raw_dir: Path | str | None = None,
    manifest: dict | None = None,
) -> EvidenceView:
    """Remove only identified support, retaining any independently supported edge.

    A removed relationship is unknown in search, not a known-false ACL. An enabled
    observation can be withheld only when it was true; known-false evidence is vetoing.
    """
    view = deepcopy(baseline)
    delta = []
    withheld = set()
    if specification:
        kind = specification["kind"]
        if kind == "withhold_structural_provenance":
            matches = [
                (i, e) for i, e in enumerate(view["edges"]) if e["id"] == specification["edge_id"]
            ]
            if len(matches) != 1:
                raise ValueError("counterfactual requires one exact baseline edge")
            index, edge = matches[0]
            expected = (
                specification["source"],
                specification["relationship"],
                specification["target"],
            )
            if (edge["source"], edge["kind"], edge["target"]) != expected:
                raise ValueError("counterfactual edge endpoints/kind mismatch")
            direct = any(
                _explicit_locator(record, specification["locator"]) for record in edge["provenance"]
            )
            raw_binding = None if direct else _resolve_raw_binding(specification, raw_dir, manifest)
            kept = []
            for record in edge["provenance"]:
                matches_locator = _explicit_locator(record, specification["locator"])
                # A different explicit ACE locator is independent support, even
                # when its file/record/attribute tuple matches the coarse mapping.
                if raw_binding and isinstance(record, dict) and not _has_explicit_locator(record):
                    filename, record_id, snapshot = raw_binding
                    matches_locator = (
                        record.get("raw_file")
                        == "snapshot:" + snapshot.removeprefix("sha256:") + "/" + filename
                        and record.get("record_id") == record_id
                        and record.get("attribute") == "Aces[].PrincipalSID"
                    )
                if matches_locator:
                    delta.append(
                        {
                            "op": "withhold_provenance",
                            "edge_id": edge["id"],
                            "locator": specification["locator"],
                            "before": deepcopy(record),
                            "raw_binding": raw_binding,
                        }
                    )
                else:
                    kept.append(record)
            if len(kept) == len(edge["provenance"]):
                raise ValueError("counterfactual locator has no verified canonical support mapping")
            if kept:
                edge["provenance"] = kept
            else:
                view["edges"].pop(index)
                withheld.add(StructuralRelationship(*expected))
        elif kind == "withhold_enabled_observation":
            _resolve_raw_binding(specification, raw_dir, manifest)
            nodes = [n for n in view["nodes"] if n["id"] == specification["node_id"]]
            if len(nodes) != 1 or nodes[0].get("enabled") is not True:
                raise ValueError("enabled overlay requires exact known-true baseline observation")
            delta.append(
                {
                    "op": "remove",
                    "node_id": nodes[0]["id"],
                    "field": "enabled",
                    "locator": specification["locator"],
                    "before": nodes[0].pop("enabled"),
                }
            )
        else:
            raise ValueError("unknown counterfactual evidence view kind")
    audit = {
        "case_id": case_id,
        "evidence_class": "counterfactual_search_view" if specification else "baseline",
        "baseline_digest": digest(baseline),
        "view_digest": digest(view),
        "specification": deepcopy(specification),
        "delta": delta,
        "delta_digest": digest(delta),
    }
    return EvidenceView(view, audit, frozenset(withheld))
