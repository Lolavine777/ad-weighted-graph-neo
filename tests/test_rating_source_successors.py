"""Current-source migrations preserve frozen numeric/history bytes and strict pins."""

import json
import shutil
from pathlib import Path

import pytest

from scripts.research.asrep_expert_basis import verify_historical
from scripts.research.likelihood_catalog import verify_package as verify_likelihood
from scripts.research.scenario_rating_pack import verify_package as verify_scenario

ROOT = Path(__file__).resolve().parents[1]


def test_source_successors_preserve_all_asrep_frozen_history():
    verify_historical()
    assert verify_likelihood()["numeric_activated"] == 0
    assert verify_scenario()["verified"]


@pytest.mark.parametrize(
    "package,manifest,verify",
    [
        ("likelihood-v1", "source-manifest-v14.json", verify_likelihood),
        ("scenario-basis-v1", "source-manifest-v14.json", verify_scenario),
    ],
)
@pytest.mark.parametrize(
    "change",
    [
        "historical_pin",
        "previous_manifest",
        "ancestor_manifest",
        "coverage",
        "current_source",
        "graph_source",
        "neo_coverage",
        "neo_historical_pin",
    ],
)
def test_successor_still_rejects_historical_or_current_tampering(
    tmp_path, package, manifest, verify, change
):
    relative = Path("docs/research/ratings") / package
    shutil.copytree(ROOT / relative, tmp_path / relative)
    path = tmp_path / relative / manifest
    data = json.loads(path.read_text())
    for name in data["source_pins"]:
        target = tmp_path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, target)
    baseline = Path("reports/neo/source-manifest.json")
    (tmp_path / baseline).parent.mkdir(parents=True)
    shutil.copyfile(ROOT / baseline, tmp_path / baseline)
    if change == "historical_pin":
        data["historical_manifest_sha256"] = "sha256:" + "0" * 64
    elif change in ("previous_manifest", "ancestor_manifest"):
        version = int(manifest.split("-v")[1].split(".")[0]) - (
            1 if change == "previous_manifest" else 2
        )
        previous = tmp_path / relative / f"source-manifest-v{version}.json"
        previous.write_bytes(previous.read_bytes() + b"\n")
    elif change == "coverage":
        data["source_pins"].pop("src/engine/query.py")
    elif change.startswith("neo_"):
        live_path = tmp_path / baseline
        live = json.loads(live_path.read_text())
        if change == "neo_coverage":
            live["source_pins"].pop("src/engine/query.py")
        else:
            live["historical_source_manifests"][relative.as_posix() + "/" + manifest] = (
                "sha256:" + "0" * 64
            )
        live_path.write_text(json.dumps(live))
    else:
        source = tmp_path / (
            "src/engine/graph.py" if change == "graph_source" else "src/engine/query.py"
        )
        source.write_bytes(source.read_bytes() + b"\n# tampered source\n")
    if change in ("historical_pin", "coverage"):
        path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="historical|previous|coverage|source.*drift"):
        verify(tmp_path)


def test_neo_source_generator_is_deterministic_and_preserves_archives(tmp_path):
    from scripts.research.scenario_rating_pack import (
        HISTORICAL_SOURCE_MANIFESTS,
        NEO_SOURCE_MANIFEST,
        write_source_manifest,
    )

    recorded = json.loads((ROOT / NEO_SOURCE_MANIFEST).read_text())
    for name in set(recorded["source_pins"]) | set(HISTORICAL_SOURCE_MANIFESTS):
        destination = tmp_path / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, destination)
    output = write_source_manifest(tmp_path)
    first = output.read_bytes()
    assert write_source_manifest(tmp_path).read_bytes() == first
    assert json.loads(first) == recorded
    for name in HISTORICAL_SOURCE_MANIFESTS:
        assert (tmp_path / name).read_bytes() == (ROOT / name).read_bytes()


def test_generator_refuses_to_overwrite_published_successor(tmp_path, monkeypatch):
    from scripts.research import rating_source_successors as generator

    published = tmp_path / "docs/research/ratings/likelihood-v1/source-manifest-v11.json"
    published.parent.mkdir(parents=True)
    published.write_text("published sentinel")
    monkeypatch.setattr(generator, "ROOT", tmp_path)
    with pytest.raises(ValueError, match="Preserve source successors"):
        generator.main()
    assert published.read_text() == "published sentinel"
    assert not (
        tmp_path / "docs/research/ratings/scenario-basis-v1/source-manifest-v12.json"
    ).exists()
