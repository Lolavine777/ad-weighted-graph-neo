"""Export selection preserves local evidence and audits partial foreign context."""

from copy import deepcopy

import pytest

from scripts.neo_import import prepare_records
from src.parser import IdentityNormalizer, RawRecord, ReconciliationConflictError


def record(kind, identifier, domain="A.LOCAL", export="one", **fields):
    return RawRecord(
        kind,
        {
            "ObjectIdentifier": identifier,
            "Properties": {"domain": domain, "name": identifier},
            **fields,
        },
        {"raw_file": f"snapshot:test/{export}_{kind}.json", "record_locator": identifier},
    )


def test_export_selection_keeps_referenced_placeholders_and_observed_foreign_identity():
    domain = record("domains", "S-1-5-21-1-2-3")
    user = record("users", "S-1-5-21-1-2-3-1001")
    unused = record("users", "A.LOCAL-S-1-5-20")
    unused.data["Properties"]["reconcile"] = False
    used = record("groups", "A.LOCAL-S-1-5-11", Members=[], Aces=[])
    used.data["Properties"]["reconcile"] = False
    user.data["Aces"] = [{"PrincipalSID": used.data["ObjectIdentifier"]}]
    foreign = record(
        "groups", "S-1-5-21-4-5-6-519", domain="B.LOCAL", export="two", Members=["foreign-user"]
    )
    user.data["Aces"].append({"PrincipalSID": foreign.data["ObjectIdentifier"]})
    foreign.data["Properties"].update(enabled=False, distinguishedname="CN=EA,DC=B,DC=LOCAL")
    records = [domain, user, unused, used, foreign]
    before = deepcopy(records)
    selected, audit = prepare_records(records, "one_")
    assert unused not in selected and used in selected and user in selected
    boundary = next(
        r for r in selected if r.data["ObjectIdentifier"] == foreign.data["ObjectIdentifier"]
    )
    assert boundary.data["is_boundary"] is True and "Members" not in boundary.data
    assert boundary.data["Properties"]["enabled"] is False
    assert boundary.data["Properties"]["distinguishedname"] == "CN=EA,DC=B,DC=LOCAL"
    assert len(audit["omitted_unreferenced_empty_generated"]) == 1
    assert len(audit["boundary_representations"]) == 1
    assert records == before


def test_conflicting_full_objects_are_not_selected_or_silently_removed():
    first = record("users", "S-1-5-21-1-2-3-1001")
    second = deepcopy(first)
    second.data["Properties"]["name"] = "Different identity"
    selected, _ = prepare_records([first, second], None)
    assert len(selected) == 2
    with pytest.raises(ReconciliationConflictError):
        IdentityNormalizer().normalize_records(selected)


def test_unknown_export_prefix_is_an_input_error():
    with pytest.raises(ValueError, match="No supported records"):
        prepare_records([record("domains", "S-1-5-21-1-2-3")], "absent")
