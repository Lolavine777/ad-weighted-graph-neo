"""Regression checks for the Phase 3 claim inventory."""

from __future__ import annotations

import json
import re
from pathlib import Path

from scripts.claim_traceability import (
    CONFIDENCES,
    RELATIONSHIPS,
    STATUSES,
    build_inventory,
    validate_inventory,
    write_inventory,
)

ROOT = Path(__file__).resolve().parents[1]
KNOWN_ISSUES = {"#44", "#45", "#47", "#79", "#80", "#81", "#92"}


def _json_bytes(document: dict) -> bytes:
    return (json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()


def test_inventory_is_deterministic(tmp_path: Path) -> None:
    first = tmp_path / "first.json"
    second = tmp_path / "second.json"
    write_inventory(first)
    write_inventory(second)
    assert first.read_bytes() == second.read_bytes()
    assert first.read_bytes() == _json_bytes(build_inventory())


def test_inventory_contract_and_source_invariants() -> None:
    document = build_inventory()
    validate_inventory(document)
    assert {item["status"] for item in document["claims"]} <= STATUSES
    assert {item["confidence"] for item in document["claims"]} <= CONFIDENCES
    assert {
        item["relationship"] for item in document["claims"] if item["relationship"]
    } <= RELATIONSHIPS
    assert all(item["source_location"] for item in document["claims"])
    assert all(item["raw_sources"] for item in document["claims"] if item["status"] == "SUPPORTED")


def test_claims_route_only_to_known_issues() -> None:
    document = build_inventory()
    for item in document["claims"]:
        owners = {part.strip() for part in item["downstream_issue"].split("/")}
        assert owners <= KNOWN_ISSUES, item["claim_id"]


def test_structural_claims_do_not_depend_on_event_id_only() -> None:
    document = build_inventory()
    for item in document["claims"]:
        if item["claim_class"] == "structural":
            assert "EventID" not in item["required_fields"]
            assert "EventID" not in item["observed_fields"]


def test_annotation_is_not_promoted_to_native_evidence() -> None:
    document = build_inventory()
    for item in document["claims"]:
        if "EVTX_Tactic" in item["required_fields"] or "EVTX_Tactic" in item["observed_fields"]:
            assert item["claim_class"] == "evaluation"
            assert item["status"] in {"UNSUPPORTED", "UNRESOLVED"}


def test_inventory_contains_no_raw_payload_values() -> None:
    text = json.dumps(build_inventory(), ensure_ascii=False, sort_keys=True)
    for forbidden in ("S-1-5-21-", "ScriptBlockText=", "CommandLine=", "AttributeValue="):
        assert forbidden not in text


def test_accepted_host_access_semantics_are_not_downgraded() -> None:
    by_id = {item["claim_id"]: item for item in build_inventory()["claims"]}
    admin = by_id["S-LOCALADMINS-ADMinto"]
    assert admin["claim_class"] == "structural"
    assert admin["status"] == "SUPPORTED"
    psremote = by_id["S-CANPSREMOTE-MEMBERSHIP-ONLY"]
    assert psremote["claim_class"] == "structural"
    assert psremote["status"] == "SUPPORTED"


def test_memberof_raw_container_direction_is_not_canonical_edge_direction() -> None:
    by_id = {item["claim_id"]: item for item in build_inventory()["claims"]}
    memberof = by_id["S-MEMBEROF-DIRECT"]
    assert "referenced principal -> containing Group" in memberof["claim_text"]
    assert "referenced principal -> containing Group" in memberof["interpretation_rule"]


def test_eda_claim_sources_resolve_to_current_report_fields() -> None:
    report = json.loads((ROOT / "reports/eda_summary.json").read_text(encoding="utf-8"))
    claims = {item["claim_id"]: item for item in build_inventory()["claims"]}
    for claim_id in ("T-EVTX-TACTIC-GROUNDTRUTH", "E-EDA-EVENT-COUNTS-ATTACKS"):
        item = claims[claim_id]
        fields = re.findall(
            r"reports/eda_summary\.json:telemetry\.([a-z_]+)", item["source_location"]
        )
        assert fields, claim_id
        assert all(field in report["telemetry"] for field in fields), claim_id
        assert "m1_edge_telemetry_matrix" not in json.dumps(item)
