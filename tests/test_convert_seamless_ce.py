"""CE compatibility conversion must conserve source identities and references."""

import copy
import json

import pytest

from scripts import convert_seamless_ce as converter


def sample():
    return {
        "domains": [
            {
                "ObjectIdentifier": "S-1-5-21-1-2-3",
                "Properties": {"domain": "LAB"},
                "Aces": [],
                "Users": ["user"],
                "Computers": ["host"],
                "ChildOus": [],
            }
        ],
        "groups": [
            {
                "ObjectIdentifier": "group",
                "Properties": {"domain": "LAB"},
                "Members": [{"MemberId": "user", "MemberType": "User"}],
                "Aces": [
                    {
                        "PrincipalSID": "user",
                        "PrincipalType": "User",
                        "RightName": "ExtendedRight",
                        "AceType": "All",
                        "IsInherited": False,
                    }
                ],
            }
        ],
        "computers": [
            {
                "ObjectIdentifier": "host",
                "Properties": {"domain": "LAB"},
                "Aces": [],
                "Sessions": [],
                "LocalAdmins": [{"MemberId": "user", "MemberType": "User"}],
            }
        ],
    }


def test_conversion_preserves_source_and_maps_ce_structs():
    raw = sample()
    original = copy.deepcopy(raw)
    converted = converter.convert_records(raw)
    assert raw == original
    assert converted["groups"][0]["Members"] == [{"ObjectIdentifier": "user", "ObjectType": "User"}]
    assert converted["groups"][0]["Aces"][0]["RightName"] == "AllExtendedRights"
    assert converted["computers"][0]["LocalGroups"][0]["ObjectIdentifier"] == "host-544"
    assert converted["computers"][0]["DomainSID"] == "S-1-5-21-1-2-3"
    assert converter.validate_conservation(raw, converted)["records"] == 3


@pytest.mark.parametrize("mutation", ["membership", "ace", "local", "property", "identity"])
def test_conservation_detects_lost_or_changed_data(mutation):
    raw = sample()
    converted = converter.convert_records(raw)
    if mutation == "membership":
        converted["groups"][0]["Members"].clear()
    elif mutation == "ace":
        converted["groups"][0]["Aces"][0]["RightName"] = "GenericAll"
    elif mutation == "local":
        converted["computers"][0]["LocalGroups"][0]["Results"].clear()
    elif mutation == "property":
        converted["groups"][0]["Properties"]["domain"] = "OTHER"
    else:
        converted["groups"][0]["ObjectIdentifier"] = "other"
    with pytest.raises(ValueError, match="conservation"):
        converter.validate_conservation(raw, converted)


@pytest.mark.parametrize("field,value", [("Mystery", []), ("AllowedToAct", ["user"])])
def test_rejects_unsupported_fields(field, value):
    raw = sample()
    raw["computers"][0][field] = value
    with pytest.raises(ValueError, match="unsupported"):
        converter.convert_records(raw)


def test_rejects_unknown_ace():
    raw = sample()
    raw["groups"][0]["Aces"][0]["AceType"] = "Unknown"
    with pytest.raises(ValueError, match="ACE"):
        converter.convert_records(raw)


def test_refuses_existing_output_before_reading(tmp_path):
    with pytest.raises(FileExistsError):
        converter.install(tmp_path / "missing", tmp_path)


def test_pinned_raw_conversion_opt_in(tmp_path):
    import os

    if os.getenv("AWG_TEST_RAW_SEAMLESS") != "1":
        pytest.skip("set AWG_TEST_RAW_SEAMLESS=1 for pinned raw self-check")
    output = tmp_path / "converted"
    evidence = converter.install(converter.ROOT / "data/raw/SEAMLESS", output)
    assert evidence["conservation"]["records"] == 3369
    assert evidence["conservation"]["aces"] == 53040
    assert (
        json.loads((output / "inputs/20210920185958_groups.json").read_text())["meta"]["version"]
        == 6
    )


@pytest.mark.parametrize(
    "source_right,ace_type,ce_right",
    [
        ("Owner", "", "Owns"),
        ("ExtendedRight", "GetChanges", "GetChanges"),
        ("ExtendedRight", "GetChangesAll", "GetChangesAll"),
        ("GenericWrite", "", "GenericWrite"),
    ],
)
def test_supported_ace_mapping(source_right, ace_type, ce_right):
    raw = sample()
    raw["groups"][0]["Aces"][0].update(RightName=source_right, AceType=ace_type)
    assert converter.convert_records(raw)["groups"][0]["Aces"][0]["RightName"] == ce_right


def test_conservation_detects_changed_containment():
    raw = sample()
    converted = converter.convert_records(raw)
    converted["domains"][0]["ChildObjects"][0]["ObjectIdentifier"] = "other"
    with pytest.raises(ValueError, match="conservation"):
        converter.validate_conservation(raw, converted)


def test_manifest_mismatch_creates_no_output(tmp_path):
    source = tmp_path / "raw"
    source.mkdir()
    output = tmp_path / "converted"
    with pytest.raises(ValueError, match="manifest"):
        converter.install(source, output)
    assert not output.exists()


@pytest.mark.parametrize("tamper", [None, "converted", "original", "semantic"])
def test_verify_install_rechecks_hashes_and_source_conservation(tmp_path, tamper):
    if not (converter.ROOT / "data/raw/SEAMLESS").exists():
        pytest.skip("optional pinned raw dataset absent")
    source = converter.ROOT / "data/raw/SEAMLESS"
    output = tmp_path / "converted"
    converter.install(source, output)
    name = "20210920185958_groups.json"
    if tamper == "converted":
        (output / "inputs" / name).write_text("{}")
    elif tamper == "original":
        (output / "originals" / name).unlink()
    elif tamper == "semantic":
        path = output / "inputs" / name
        payload = json.loads(path.read_text())
        payload["data"][0]["Members"] = []
        path.write_bytes(converter.encoded(payload))
        manifest_path = output / "manifest.json"
        manifest = json.loads(manifest_path.read_text())
        next(row for row in manifest["files"] if row["name"] == name)["converted_sha256"] = (
            converter.digest(path.read_bytes())
        )
        manifest_path.write_bytes(converter.encoded(manifest))
    if tamper:
        with pytest.raises((ValueError, OSError)):
            converter.verify_install(source, output)
    else:
        result = converter.verify_install(source, output)
        assert len(result["files"]) == 6
        assert result["snapshot_id"] != result["source_snapshot_id"]
        assert result["snapshot_id"] == "sha256:" + result["converted_manifest_sha256"]


def test_conservation_rejects_duplicate_local_role_replacing_another():
    raw = sample()
    raw["computers"][0]["RemoteDesktopUsers"] = [{"MemberId": "other", "MemberType": "User"}]
    converted = converter.convert_records(raw)
    groups = converted["computers"][0]["LocalGroups"]
    groups[1] = copy.deepcopy(groups[0])
    with pytest.raises(ValueError, match="conservation"):
        converter.validate_conservation(raw, converted)


def test_verify_install_rejects_duplicate_local_roles_even_with_updated_hash(tmp_path):
    if not (converter.ROOT / "data/raw/SEAMLESS").exists():
        pytest.skip("optional pinned raw dataset absent")
    source = converter.ROOT / "data/raw/SEAMLESS"
    output = tmp_path / "converted"
    converter.install(source, output)
    name = "20210920185958_computers.json"
    path = output / "inputs" / name
    payload = json.loads(path.read_text())
    groups = next(row["LocalGroups"] for row in payload["data"] if row["LocalGroups"])
    groups[:] = [copy.deepcopy(groups[0]) for _ in groups]
    path.write_bytes(converter.encoded(payload))
    manifest_path = output / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    next(row for row in manifest["files"] if row["name"] == name)["converted_sha256"] = (
        converter.digest(path.read_bytes())
    )
    manifest_path.write_bytes(converter.encoded(manifest))
    with pytest.raises(ValueError, match="conservation"):
        converter.verify_install(source, output)
