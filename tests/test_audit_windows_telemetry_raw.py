from pathlib import Path

import pytest

from scripts.audit_windows_telemetry_raw import DEFAULT_RAW_DIR, audit

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def corpus_report():
    if not DEFAULT_RAW_DIR.exists() and not DEFAULT_RAW_DIR.is_symlink():
        pytest.skip("Local telemetry raw directory not present")
    return audit()


def test_verified_csv_inventory_is_stable(corpus_report):
    report = corpus_report
    assert report["source"]["manifest_verified"] is True
    assert report["source"]["sha256"] == (
        "9220b0725221244a6b61dff8dabbf382831c0fcc2ad9d261ae60cb1f2b082fff"
    )
    assert report["csv"]["row_count"] == 4633
    assert report["csv"]["column_count"] == 326
    assert report["csv"]["first_column_is_unnamed_row_ordinal"] is True


def test_provenance_classes_have_expected_anatomy(corpus_report):
    report = corpus_report
    by_name = {item["field"]: item for item in report["csv"]["column_inventory"]}
    assert by_name["EVTX_Tactic"]["present_rows"] == 4633
    assert by_name["EventID"]["unique_nonempty_values"] == 95
    assert by_name["ScriptBlockText"]["present_rows"] == 3
    assert by_name["CommandLine"]["present_rows"] == 841
    assert by_name["ObjectDN"]["present_rows"] == 42
    assert by_name["AttributeLDAPDisplayName"]["present_rows"] == 42
    assert by_name["EventPayload"]["present_rows"] == 1


def test_event_specific_qualifiers_are_not_event_id_only(corpus_report):
    profiles = corpus_report["selected_event_profiles"]
    assert profiles["4624"]["rows"] == 69
    assert profiles["4634"]["rows"] == 1
    assert profiles["4648"]["rows"] == 7
    assert profiles["4672"]["rows"] == 12
    assert profiles["4724"]["rows"] == 1
    assert profiles["4624"]["nonempty_fields"]["LogonType"] == 69
    assert profiles["1149"]["nonempty_fields"]["{Event_NS}Param3"] == 11
    assert profiles["4104"]["nonempty_fields"]["ScriptBlockText"] == 3
    assert profiles["5136"]["nonempty_fields"]["AttributeLDAPDisplayName"] == 42
    assert profiles["4732"]["nonempty_fields"]["MemberSid"] == 2
    assert profiles["4662"]["nonempty_fields"]["AccessMask"] == 33
    assert "4670" in corpus_report["empty_event_ids_in_snapshot"]


def test_sensitive_payload_values_are_not_copied_to_generated_inventory(corpus_report):
    report = corpus_report
    for item in report["csv"]["column_inventory"]:
        if item["field"] in {"ScriptBlockText", "CommandLine", "EventPayload", "AttributeValue"}:
            assert item["safe_values"] == []
