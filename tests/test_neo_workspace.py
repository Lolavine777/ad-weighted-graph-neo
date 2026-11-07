"""The local app opens unfamiliar exports, reports what it set aside and edits one relationship."""

import json
import zipfile
from collections import Counter
from pathlib import Path

import pytest

from scripts.neo_workspace import (
    ChooseExport,
    _reference_kinds,
    _without_identifier,
    inspect_source,
    list_sources,
    open_dataset,
    remove_relationship,
    sample_sources,
)
from src.parser import RawRecord

ROOT = Path(__file__).resolve().parents[1]
WRAITH = ROOT / "data/raw/ad_sampledata"
SID = "S-1-5-21-1-2-3"


def _record(identifier, name, **fields):
    return {
        "ObjectIdentifier": identifier,
        "Properties": {
            "name": name,
            "domain": "A.LOCAL",
            "domainsid": SID,
            "distinguishedname": f"CN={name.split('@')[0]},DC=A,DC=LOCAL",
            "enabled": True,
        },
        "Aces": [],
        **fields,
    }


def _write_export(folder, prefix="20240102030405", outside_right=True):
    """A small domain: USER2 fully controls Domain Admins, one right held from another domain."""
    folder.mkdir(parents=True, exist_ok=True)
    domain_admins = _record(
        f"{SID}-512",
        "DOMAIN ADMINS@A.LOCAL",
        Members=[{"ObjectIdentifier": f"{SID}-1001", "ObjectType": "User"}],
        Aces=[{"PrincipalSID": f"{SID}-1002", "PrincipalType": "Base", "RightName": "GenericAll"}],
    )
    if outside_right:
        domain_admins["Aces"].append(
            {
                "PrincipalSID": "S-1-5-21-9-9-9-519",
                "PrincipalType": "Group",
                "RightName": "WriteDacl",
            }
        )
    export = {
        "domains": [_record(SID, "A.LOCAL")],
        "groups": [
            domain_admins,
            _record(f"{SID}-519", "ENTERPRISE ADMINS@A.LOCAL", Members=[]),
            _record(f"{SID}-513", "DOMAIN USERS@A.LOCAL", Members=[]),
            _record(
                f"{SID}-516",
                "DOMAIN CONTROLLERS@A.LOCAL",
                Members=[{"ObjectIdentifier": f"{SID}-1000", "ObjectType": "Computer"}],
            ),
        ],
        "users": [
            _record(f"{SID}-1001", "USER1@A.LOCAL", PrimaryGroupSID=f"{SID}-513"),
            _record(f"{SID}-1002", "USER2@A.LOCAL", PrimaryGroupSID=f"{SID}-513"),
        ],
        "computers": [_record(f"{SID}-1000", "DC01.A.LOCAL", PrimaryGroupSID=f"{SID}-516")],
    }
    for kind, data in export.items():
        payload = {"data": data, "meta": {"type": kind, "count": len(data), "version": 6}}
        (folder / f"{prefix}_{kind}.json").write_text(json.dumps(payload), encoding="utf-8")
    return folder


def _raw(identifier, **fields):
    return RawRecord("groups", {"ObjectIdentifier": identifier, **fields}, {"raw_file": "x"})


def test_a_new_export_opens_and_lists_what_it_set_aside(tmp_path):
    workspace = open_dataset(_write_export(tmp_path / "export"))
    report = workspace.report
    assert report["domains"] == ["A.LOCAL"]
    assert report["nodes"]["User"] == 2
    assert report["untyped_references"] == {"Base": 1}
    assert list(report["outside_references"]) == ["S-1-5-21-9-9-9-519"]
    assert report["skipped_records"] == []
    # The one bad mention costs only itself: the group keeps its other relationships.
    kinds = {(e["source"], e["kind"], e["target"]) for e in workspace.graph.edges()}
    assert (f"{SID}-1002", "GenericAll", f"{SID}-512") in kinds
    assert (f"{SID}-1001", "MemberOf", f"{SID}-512") in kinds


def test_a_zip_opens_like_its_folder_and_cannot_write_outside(tmp_path):
    folder = _write_export(tmp_path / "export")
    archive = tmp_path / "export.zip"
    with zipfile.ZipFile(archive, "w") as bundle:
        for path in folder.iterdir():
            bundle.write(path, f"../../evil/{path.name}")
    assert inspect_source(archive) == [{"export": "20240102030405", "domains": ["A.LOCAL"]}]
    assert open_dataset(archive).report["nodes"] == open_dataset(folder).report["nodes"]
    assert not (tmp_path / "evil").exists()


def test_a_folder_with_several_exports_asks_which_one(tmp_path):
    folder = _write_export(tmp_path / "many")
    _write_export(folder, prefix="20250102030405")
    with pytest.raises(ChooseExport) as choice:
        open_dataset(folder)
    assert [e["export"] for e in choice.value.exports] == ["20240102030405", "20250102030405"]
    assert open_dataset(folder, export="20250102030405").report["export"] == "20250102030405"
    with pytest.raises(ValueError, match="Không có bản xuất"):
        open_dataset(folder, export="1999")


def test_sources_prefer_a_folder_over_the_zip_of_the_same_export(tmp_path):
    folder = _write_export(tmp_path / "root" / "export")
    with zipfile.ZipFile(tmp_path / "root" / "export.zip", "w") as bundle:
        for path in folder.iterdir():
            bundle.write(path, path.name)
    (tmp_path / "root" / "broken.zip").write_bytes(b"not a zip")
    sources = list_sources(tmp_path / "root")
    assert [s["name"] for s in sources] == ["export"]


def test_an_export_without_a_domain_file_is_refused_clearly(tmp_path):
    (tmp_path / "empty").mkdir()
    (tmp_path / "empty" / "notes.json").write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="domains"):
        open_dataset(tmp_path / "empty")


def test_search_finds_names_and_ranks_the_exact_one_first(tmp_path):
    workspace = open_dataset(_write_export(tmp_path / "export"))
    assert [n["label"] for n in workspace.search("user2")] == ["USER2@A.LOCAL"]
    assert [n["label"] for n in workspace.search("user")][0].startswith("USER")
    assert workspace.search("   ") == []
    assert [n["label"] for n in workspace.targets()] == [
        "DOMAIN ADMINS@A.LOCAL",
        "ENTERPRISE ADMINS@A.LOCAL",
    ]


def test_neighbors_are_capped_and_counted(tmp_path):
    workspace = open_dataset(_write_export(tmp_path / "export"))
    view = workspace.neighbors(f"{SID}-512", limit=1)
    assert view["total_edges"] >= 2 and len(view["edges"]) == 1
    assert {f"{SID}-512"} <= {n["id"] for n in view["nodes"]}


def test_removing_the_only_right_blocks_and_the_answer_says_so(tmp_path):
    workspace = open_dataset(_write_export(tmp_path / "export"))
    answer = workspace.try_removal(
        f"{SID}-1002", "GenericAll", f"{SID}-512", f"{SID}-1002", f"{SID}-512"
    )
    assert answer["before"]["outcome"] == "reachable"
    assert answer["before"]["programs"][0]["C"] is not None
    assert answer["edit"]["status"] == "removed"
    assert answer["after"]["outcome"] == "blocked_in_scope"
    # The opened graph itself stays intact for the next question.
    assert any(e["kind"] == "GenericAll" for e in workspace.graph.edges())


def test_chokepoints_are_ranked_then_tested_by_removal(tmp_path):
    workspace = open_dataset(_write_export(tmp_path / "export"))
    found = workspace.chokepoints(f"{SID}-512")
    assert found["sources_reached"] >= 1
    direct = next(c for c in found["candidates"] if c["edge"]["kind"] == "GenericAll")
    assert direct["edge"] == {
        "source": f"{SID}-1002",
        "kind": "GenericAll",
        "target": f"{SID}-512",
    }
    assert direct["in_best_paths"] == 1
    assert direct["blocked"] == 1
    assert direct["source_label"] == "USER2@A.LOCAL"
    # A repeated question is answered from memory, and the opened graph is untouched.
    assert workspace.chokepoints(f"{SID}-512") is found
    assert any(e["kind"] == "GenericAll" for e in workspace.graph.edges())
    with pytest.raises(ValueError, match="Mục tiêu"):
        workspace.chokepoints(f"{SID}-516")


def test_cohort_sampling_is_stable_and_independent_of_input_order():
    sources = [f"s{i}" for i in range(50)]
    assert sample_sources(sources, 5) == sample_sources(list(reversed(sources)), 5)
    assert len(sample_sources(sources, None)) == 50


def test_a_source_or_target_outside_the_scope_is_refused(tmp_path):
    workspace = open_dataset(_write_export(tmp_path / "export"))
    with pytest.raises(ValueError, match="điểm xuất phát"):
        workspace.find_paths("not-a-node", f"{SID}-512")
    with pytest.raises(ValueError, match="Mục tiêu"):
        workspace.find_paths(f"{SID}-1002", f"{SID}-516")


def test_remove_relationship_touches_only_the_named_evidence():
    records = (
        _raw(
            "G",
            Members=[{"ObjectIdentifier": "U"}, {"ObjectIdentifier": "V"}],
            Aces=[
                {"PrincipalSID": "U", "RightName": "GenericAll"},
                {"PrincipalSID": "U", "RightName": "WriteDacl"},
                {"PrincipalSID": "V", "RightName": "GenericAll"},
            ],
        ),
        _raw("U", PrimaryGroupSID="G"),
        _raw(
            "H",
            LocalGroups=[
                {"ObjectIdentifier": "H-544", "Results": [{"ObjectIdentifier": "U"}]},
                {"ObjectIdentifier": "H-580", "Results": [{"ObjectIdentifier": "U"}]},
            ],
            Sessions={"Results": [{"UserSID": "U"}, {"UserSID": "V"}]},
        ),
    )
    members, removed = remove_relationship(records, "U", "MemberOf", "G")
    assert removed == {"Members": 1, "PrimaryGroupSID": 1}
    assert members[0].data["Members"] == [{"ObjectIdentifier": "V"}]
    assert members[1].data["PrimaryGroupSID"] is None

    aces, removed = remove_relationship(records, "U", "GenericAll", "G")
    assert removed == {"Aces": 1}
    assert [(a["PrincipalSID"], a["RightName"]) for a in aces[0].data["Aces"]] == [
        ("U", "WriteDacl"),
        ("V", "GenericAll"),
    ]

    local, removed = remove_relationship(records, "U", "AdminTo", "H")
    assert removed == {"LocalGroups": 1}
    assert local[2].data["LocalGroups"][0]["Results"] == []
    assert local[2].data["LocalGroups"][1]["Results"] == [{"ObjectIdentifier": "U"}]

    sessions, removed = remove_relationship(records, "H", "HasSession", "U")
    assert removed == {"Sessions": 1}
    assert sessions[2].data["Sessions"]["Results"] == [{"UserSID": "V"}]

    assert remove_relationship(records, "nobody", "MemberOf", "G")[1] == {}
    # Copies only: the opened records are what every later question starts from.
    assert len(records[0].data["Members"]) == 2


def test_a_guid_matches_whatever_case_the_collector_wrote():
    records = (_raw("AB-CD", Aces=[{"PrincipalSID": "S-1", "RightName": "WriteDacl"}]),)
    assert remove_relationship(records, "S-1", "WriteDacl", "ab-cd")[1] == {"Aces": 1}


def test_unknown_reference_kinds_and_identifiers_are_stripped_precisely():
    data = {
        "Aces": [
            {"PrincipalSID": "A", "PrincipalType": "Base"},
            {"PrincipalSID": "B", "PrincipalType": "Group"},
        ]
    }
    removed = Counter()
    _reference_kinds(data, removed)
    assert removed == {"Base": 1}
    assert data["Aces"] == [
        {"PrincipalSID": "A"},
        {"PrincipalSID": "B", "PrincipalType": "Group"},
    ]
    assert _without_identifier(
        {"Aces": [{"PrincipalSID": "A"}, {"PrincipalSID": "B"}], "PrimaryGroupSID": "A"}, "A"
    ) == {"Aces": [{"PrincipalSID": "B"}], "PrimaryGroupSID": None}


@pytest.mark.skipif(not WRAITH.is_dir(), reason="needs scripts.download_ad_sampledata")
def test_wraith_opens_to_the_thesis_graph_and_verdicts():
    workspace = open_dataset(WRAITH, export="20240305111414")
    assert sum(workspace.report["nodes"].values()) == 150
    assert sum(workspace.report["edges"].values()) == 770
    ids = {n["label"]: n["id"] for n in workspace.graph.nodes()}
    domain_admins = ids["DOMAIN ADMINS@WRAITH.CORP"]
    enterprise = ids["ENTERPRISE ADMINS@WRAITH.CORP"]
    ca, bm = ids["EXTCA01.WRAITH.CORP"], ids["BM@WRAITH.CORP"]
    rodc, administrators = ids["RODCMANAGER@WRAITH.CORP"], ids["ADMINISTRATORS@WRAITH.CORP"]

    def best(edge, source, target):
        answer = workspace.try_removal(*edge, source, target, scenario="host-compromise")
        assert answer["edit"]["status"] == "removed"
        programs = answer["after"]["programs"]
        return answer["after"]["outcome"], programs[0]["C"] if programs else None

    assert best((rodc, "MemberOf", administrators), rodc, domain_admins) == ("bypass", 3)
    assert best((rodc, "MemberOf", administrators), rodc, enterprise) == ("bypass", 3)
    assert best((ca, "HasSession", bm), ca, domain_admins) == ("blocked_in_scope", None)
    assert best((ca, "HasSession", bm), ca, enterprise) == ("blocked_in_scope", None)
    assert best((bm, "MemberOf", domain_admins), ca, domain_admins) == ("bypass", 5)
    assert best((bm, "MemberOf", domain_admins), ca, enterprise) == ("bypass", 2)
