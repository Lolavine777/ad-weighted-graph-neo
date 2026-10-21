"""Resolve Week 5 target bindings from independently manifest-verified SEAMLESS raw bytes."""

import json
import os
from pathlib import Path

import pytest

from src.data.manifest import (
    load_manifest,
    raw_file_reference,
    read_verified_snapshot_file,
    verify_manifest,
)

ROOT = Path(__file__).resolve().parents[1]
TARGET_MANIFEST = json.loads(
    (ROOT / "tests/fixtures/batch_contracts/target_manifest_seamless.json").read_text()
)


@pytest.fixture(scope="module")
def seamless_raw():
    raw_root = Path(os.environ.get("SEAMLESS_RAW_ROOT", ROOT / "data/raw/SEAMLESS"))
    if "SEAMLESS_RAW_ROOT" not in os.environ and not raw_root.is_dir():
        pytest.skip("Private SEAMLESS raw unavailable; set SEAMLESS_RAW_ROOT to verify bindings")
    raw_manifest = load_manifest(ROOT / "data/samples/manifests/seamless-raw-v1.json")
    assert raw_manifest["snapshot_id"] == TARGET_MANIFEST["snapshot_id"]
    assert raw_manifest["summary"]["file_count"] == 6
    assert verify_manifest(raw_root, raw_manifest) == []
    yield raw_root, raw_manifest
    assert verify_manifest(raw_root, raw_manifest) == []


def assert_raw_binding(target, raw_root, raw_manifest):
    filename, pointer = target["provenance_locator"].split("#", 1)
    payload = json.loads(
        read_verified_snapshot_file(
            raw_root, raw_manifest, raw_file_reference(raw_manifest, filename)
        )
    )
    prefix, collection, index = pointer.split("/")
    assert prefix == ""
    assert payload["meta"]["type"] == collection
    record = payload[collection][int(index)]
    assert record["ObjectIdentifier"] == target["target_node_id"], target["goal_id"]
    raw_kind = {"groups": "Group", "computers": "Computer"}[payload["meta"]["type"]]
    assert raw_kind == target["target_node_kind"], target["goal_id"]


@pytest.mark.parametrize("target", TARGET_MANIFEST["targets"], ids=lambda t: t["goal_id"])
def test_seamless_target_provenance_resolves_to_raw_id_and_kind(target, seamless_raw):
    assert_raw_binding(target, *seamless_raw)


def test_old_ea_locator_is_rejected_by_raw_binding(seamless_raw):
    ea = next(
        t for t in TARGET_MANIFEST["targets"] if t["goal_id"] == "goal-seamless-ea-entitlement"
    )
    old_ea = {**ea, "provenance_locator": "20210920185958_groups.json#/groups/41"}
    with pytest.raises(AssertionError, match="goal-seamless-ea-entitlement"):
        assert_raw_binding(old_ea, *seamless_raw)
