"""Frozen golden oracles may use current sources only for unchanged owners."""

from copy import deepcopy

import pytest
import yaml

from scripts.research import attack_scenarios as harness


def inputs(tmp_path):
    archived = tmp_path / "archived.yml"
    current = tmp_path / "current.yml"
    document = {"techniques": [{"id": "member", "prerequisites": ["membership_usable"]}]}
    archived.write_text(yaml.safe_dump(document))
    current.write_text(
        yaml.safe_dump(
            {
                "techniques": [
                    *document["techniques"],
                    {"id": "new_owner", "prerequisites": ["new_gate"]},
                ]
            }
        )
    )
    suite = {
        "bindings": {"catalog_digest": harness.file_digest(archived)},
        "scenarios": [{"oracle_scope": {"techniques": ["member"]}}],
    }
    return suite, current, archived


def test_unrelated_owner_addition_preserves_frozen_oracle_binding(tmp_path):
    suite, current, archived = inputs(tmp_path)
    before = deepcopy(suite)
    harness.validate_catalog_binding(suite, current, archived)
    assert suite == before


@pytest.mark.parametrize("damage", ["changed_owner", "removed_owner", "archive_tamper", "bad_pin"])
def test_binding_rejects_changed_selected_owner_or_bad_archive(tmp_path, damage):
    suite, current, archived = inputs(tmp_path)
    if damage in ("changed_owner", "removed_owner"):
        data = yaml.safe_load(current.read_text())
        if damage == "changed_owner":
            data["techniques"][0]["prerequisites"] = []
        else:
            data["techniques"].pop(0)
        current.write_text(yaml.safe_dump(data))
    elif damage == "archive_tamper":
        archived.write_text(archived.read_text() + "\n")
    else:
        suite["bindings"]["catalog_digest"] = "sha256:" + "0" * 64
    with pytest.raises(ValueError, match="catalog"):
        harness.validate_catalog_binding(suite, current, archived)


def test_global_catalog_metadata_change_requires_review(tmp_path):
    suite, current, archived = inputs(tmp_path)
    data = yaml.safe_load(current.read_text())
    data["version"] = "changed"
    current.write_text(yaml.safe_dump(data))
    with pytest.raises(ValueError, match="metadata"):
        harness.validate_catalog_binding(suite, current, archived)


def test_published_rating_catalog_is_bound_to_exact_archive_bytes(tmp_path):
    import json
    import shutil

    from scripts.research.likelihood_catalog import published_catalog

    root = harness.ROOT
    data = json.loads((root / "docs/research/ratings/likelihood-v1/catalog.json").read_text())
    live = tmp_path / "configs/attack_semantics.yml"
    archived = tmp_path / harness.ARCHIVED_CATALOG.relative_to(root)
    for destination, source in (
        (live, root / "configs/attack_semantics.yml"),
        (archived, harness.ARCHIVED_CATALOG),
    ):
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
    owners = published_catalog(data, tmp_path)
    assert len(owners) == 23 and "use_session_identity" not in {t.id for t in owners}
    original = live.read_bytes()
    changed = yaml.safe_load(original)
    owner = next(t for t in changed["techniques"] if t["id"] == "obtain_admin_execution_on_host")
    owner["prerequisites"].append("network_kdc_reachable")
    live.write_text(yaml.safe_dump(changed))
    harness.load_catalog(live)
    data["actions"] = [
        a for a in data["actions"] if a["technique_id"] != "obtain_admin_execution_on_host"
    ]
    with pytest.raises(ValueError, match="catalog owner changed"):
        published_catalog(data, tmp_path)
    live.write_bytes(original)
    archived.write_bytes(archived.read_bytes() + b"\n")
    with pytest.raises(ValueError, match="catalog.*pin"):
        published_catalog(data, tmp_path)


def test_numeric_receipt_signature_keeps_its_original_catalog_scope(tmp_path, monkeypatch):
    import shutil

    from scripts.research import final_cpi_delegated_release as release

    monkeypatch.setattr(release, "ROOT", tmp_path)
    monkeypatch.setattr(release, "COHORT", tmp_path / "unused-cohort.json")
    monkeypatch.setattr(release, "MODEL_INPUTS", {})
    for name in (
        "configs/attack_semantics.yml",
        "tests/fixtures/attack_scenarios/catalog-v0.6.yml",
        "docs/research/ratings/likelihood-v1/catalog.json",
    ):
        destination = tmp_path / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(harness.ROOT / name, destination)
    live = tmp_path / "configs/attack_semantics.yml"
    current = live.read_bytes()
    live.write_bytes(harness.ARCHIVED_CATALOG.read_bytes())
    original_signature = release.signature()
    live.write_bytes(current)
    assert release.signature() == original_signature
    changed = yaml.safe_load(current)
    changed["techniques"][0]["prerequisites"] = []
    live.write_text(yaml.safe_dump(changed))
    with pytest.raises(ValueError, match="catalog owner changed"):
        release.signature()
