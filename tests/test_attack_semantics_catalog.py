"""Catalog schema, coverage and isolation regressions for issue #63."""

from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest
import yaml

from src.engine.semantics import candidates, load_catalog, validate_catalog

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def document():
    return yaml.safe_load((ROOT / "configs/attack_semantics.yml").read_text())


def test_catalog_covers_contract_without_runtime_fields():
    contract = yaml.safe_load((ROOT / "configs/contract.yml").read_text())
    catalog = load_catalog()
    assert {t.relationship for t in catalog} == set(contract["edge_kinds"]) | {
        "AuthenticationControl",
        "DeclaredHostAdmin",
        "ASRepTarget",
        "ASRepMaterial",
        "RoastTarget",
        "TicketMaterial",
        "RecoveredSecret",
        "RBCDReset",
        "RBCDPrepare",
        "RBCDConfigure",
        "RBCDDelegate",
        "RBCDAsset",
    }
    assert not {"AuthenticationControl", "DeclaredHostAdmin"} & set(contract["edge_kinds"])
    assert contract["schema"]["edge_required"] == [
        "id",
        "source",
        "target",
        "kind",
        "weight",
        "provenance",
    ]
    assert contract["schema"]["edge_optional"] == ["derivation"]
    with pytest.raises(FrozenInstanceError):
        catalog[0].confidence = "high"


@pytest.mark.parametrize(
    "field",
    [
        "id",
        "relationship",
        "semantic_class",
        "source_kinds",
        "target_kinds",
        "action_required",
        "prerequisites",
        "effects",
        "failure_conditions",
        "expected_telemetry",
        "attack_refs",
        "confidence",
        "cost_factors",
        "remediation",
    ],
)
def test_all_fields_required(document, field):
    del document["techniques"][0][field]
    with pytest.raises(ValueError):
        validate_catalog(document)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("id", " "),
        ("relationship", "GenericWrite"),
        ("semantic_class", []),
        ("source_kinds", ["Identity"]),
        ("target_kinds", ["Asset"]),
        ("action_required", "false"),
        ("action_required", 0),
        ("prerequisites", ["arbitrary_python()"]),
        ("effects", ["control"]),
        ("failure_conditions", []),
        ("expected_telemetry", {}),
        ("attack_refs", [False]),
        ("confidence", 0.99),
        ("cost_factors", {"cost": -1}),
        ("remediation", [""]),
        ("source_kinds", ["User", "User"]),
        ("target_kinds", ["Computer"]),
    ],
)
def test_invalid_field_values_rejected(document, field, value):
    document["techniques"][0][field] = value
    with pytest.raises(ValueError):
        validate_catalog(document)


def test_missing_edge_duplicate_id_and_unknown_fields(document):
    for mutation in ("missing", "duplicate", "unknown"):
        data = yaml.safe_load(yaml.safe_dump(document))
        if mutation == "missing":
            data["techniques"] = [
                t for t in data["techniques"] if t["relationship"] != "HasSession"
            ]
        elif mutation == "duplicate":
            data["techniques"].append(data["techniques"][0])
        else:
            data["techniques"][0]["observed_activity"] = []
        with pytest.raises(ValueError):
            validate_catalog(data)


@pytest.mark.parametrize(
    "predicate", ["source_admin_control", "session_identity_usable", "target_enabled"]
)
def test_session_identity_cannot_remove_acquisition_gates(document, predicate):
    technique = next(t for t in document["techniques"] if t["id"] == "use_session_identity")
    technique["prerequisites"].remove(predicate)
    with pytest.raises(ValueError):
        validate_catalog(document)


@pytest.mark.parametrize("event_id", [True, 0, -1, "4724"])
def test_telemetry_event_id_is_typed(document, event_id):
    document["techniques"][1]["expected_telemetry"][0]["event_id"] = event_id
    with pytest.raises(ValueError):
        validate_catalog(document)


def test_passive_membership_cannot_claim_attack_or_telemetry(document):
    member = document["techniques"][0]
    member["expected_telemetry"] = document["techniques"][1]["expected_telemetry"]
    with pytest.raises(ValueError):
        validate_catalog(document)


def test_runtime_guards_cannot_be_removed(document):
    remote = next(t for t in document["techniques"] if t["relationship"] == "CanPSRemote")
    remote["prerequisites"].remove("winrm_available")
    with pytest.raises(ValueError, match="guards"):
        validate_catalog(document)


def test_genericall_dispatches_by_target_and_explicit_technique():
    user = {t.id for t in candidates("GenericAll", "User", "User")}
    group = {t.id for t in candidates("GenericAll", "User", "Group")}
    computer = {t.id for t in candidates("GenericAll", "User", "Computer")}
    assert user == {
        "genericall_reset_password",
        "genericall_grant_write_dacl",
        "scenario_reset_password",
    }
    assert group == {"genericall_add_member", "genericall_grant_write_dacl"}
    assert computer == {"genericall_grant_write_dacl"}
    assert candidates("GenericAll", "OU", "User") == ()
    assert candidates("GenericWrite", "User", "User") == ()


def test_loading_does_not_depend_on_working_directory(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert load_catalog()
