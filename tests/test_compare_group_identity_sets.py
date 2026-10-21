"""Kiểm chứng đối soát exact identity, scope và input lỗi bằng dữ liệu synthetic."""

import copy
import json
import subprocess
import sys

import pytest

from scripts.research.compare_group_identity_sets import compare_groups, load_json

SCOPE = "domain:sid:S-1-5-21-100-200-300:S-1-5-32-545"
PROJECT = {
    "nodes": [
        {"id": SCOPE, "kind": "Group", "is_boundary": False},
        {"id": "S-1-5-4", "kind": "Group", "is_boundary": True},
    ]
}
LEGACY = [
    {"objectid": "EXAMPLE.TEST-S-1-5-32-545", "name": "USERS@EXAMPLE.TEST"},
    {"objectid": "EXAMPLE.TEST-S-1-5-4", "name": None},
]
MAPPING = {"EXAMPLE.TEST-S-1-5-32-545": SCOPE, "EXAMPLE.TEST-S-1-5-4": "S-1-5-4"}


def test_explicit_mapping_preserves_scope_and_partition():
    original = copy.deepcopy((PROJECT, LEGACY, MAPPING))
    result = compare_groups(PROJECT, LEGACY, MAPPING)
    assert result["literal_common_count"] == 0
    assert result["mapped_common_count"] == 2
    assert result["mapped_common_collected_count"] == 1
    assert result["mapped_common_boundary_count"] == 1
    assert result["project_only"] == result["legacy_only"] == []
    assert result["set_digests"]["project_total"] == result["set_digests"]["legacy_mapped"]
    assert (PROJECT, LEGACY, MAPPING) == original


def test_no_suffix_heuristic_and_order_is_deterministic():
    result = compare_groups(PROJECT, LEGACY, {})
    assert result["status"] == "unknown"
    assert result["mapped_common_count"] == 0
    assert result["unresolved_mappings"] == sorted(MAPPING)
    assert result == compare_groups({"nodes": PROJECT["nodes"][::-1]}, LEGACY[::-1], {})


@pytest.mark.parametrize(
    "change",
    [
        "collision",
        "outside_source",
        "outside_target",
        "duplicate_legacy",
        "duplicate_project",
        "bool",
        "spaces",
        "bad_name",
        "kind",
        "remap_canonical",
    ],
)
def test_rejects_ambiguous_or_malformed_input(change):
    project, legacy, mapping = copy.deepcopy((PROJECT, LEGACY, MAPPING))
    if change == "collision":
        mapping[LEGACY[1]["objectid"]] = SCOPE
    elif change == "outside_source":
        mapping["UNKNOWN"] = SCOPE
    elif change == "outside_target":
        mapping[LEGACY[0]["objectid"]] = "S-1-5-32-545"
    elif change == "duplicate_legacy":
        legacy.append(copy.deepcopy(legacy[0]))
    elif change == "duplicate_project":
        project["nodes"].append(copy.deepcopy(project["nodes"][0]))
    elif change == "bool":
        project["nodes"][0]["is_boundary"] = "false"
    elif change == "spaces":
        legacy[0]["objectid"] += " "
    elif change == "bad_name":
        legacy[0]["name"] = False
    elif change == "kind":
        project["nodes"][0]["kind"] = "Identity"
    elif change == "remap_canonical":
        legacy.append({"objectid": "S-1-5-4", "name": None})
        mapping["S-1-5-4"] = SCOPE
    with pytest.raises(ValueError):
        compare_groups(project, legacy, mapping)


@pytest.mark.parametrize("text", ['{"a":1,"a":2}', '{"a":NaN}', '{"a":Infinity}'])
def test_rejects_lossy_json(tmp_path, text):
    path = tmp_path / "invalid.json"
    path.write_text(text, encoding="utf-8")
    with pytest.raises(ValueError):
        load_json(path)


def test_cli_and_input_overwrite_guard(tmp_path):
    files = [tmp_path / name for name in ("project.json", "legacy.json", "mapping.json")]
    for path, data in zip(files, (PROJECT, LEGACY, MAPPING), strict=True):
        path.write_text(json.dumps(data), encoding="utf-8")
    command = [
        sys.executable,
        "scripts/research/compare_group_identity_sets.py",
        "--project",
        str(files[0]),
        "--legacy-groups",
        str(files[1]),
        "--mapping",
        str(files[2]),
        "--output",
    ]
    output = tmp_path / "result.json"
    assert subprocess.run([*command, str(output)], capture_output=True).returncode == 0
    assert json.loads(output.read_text(encoding="utf-8"))["mapped_common_count"] == 2
    before = files[0].read_bytes()
    assert subprocess.run([*command, str(files[0])], capture_output=True).returncode == 1
    assert files[0].read_bytes() == before
