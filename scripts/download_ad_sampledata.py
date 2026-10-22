"""Download the pinned public ad_sampledata lab files and verify their manifest."""

from __future__ import annotations

import argparse
import json
import tempfile
import urllib.request
from pathlib import Path

from src.data.manifest import load_manifest, verify_manifest

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "data/samples/manifests/ad-sampledata-v1.json"
SOURCE_COMMIT = "a465568cc9058d2faa8d04c2dd3e600c68e9d2c7"
SOURCE_URL = (
    f"https://raw.githubusercontent.com/SquidSec/BloodBash/{SOURCE_COMMIT}/SampleSharphoundADData/"
)


def install(output):
    output = Path(output).absolute()
    manifest = load_manifest(MANIFEST)
    if output.exists() or output.is_symlink():
        issues = verify_manifest(output, manifest)
        if issues:
            raise ValueError(f"Existing dataset differs from manifest: {issues}")
        return {"status": "already_verified", "snapshot_id": manifest["snapshot_id"]}
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".ad-sampledata-", dir=output.parent) as temporary:
        staging = Path(temporary) / "raw"
        staging.mkdir()
        for entry in manifest["files"]:
            name = entry["relative_path"]
            with urllib.request.urlopen(SOURCE_URL + name, timeout=30) as response:
                data = response.read(entry["size_bytes"] + 1)
            (staging / name).write_bytes(data)
        issues = verify_manifest(staging, manifest)
        if issues:
            raise ValueError(f"Downloaded files differ from manifest: {issues}")
        if output.exists() or output.is_symlink():
            raise FileExistsError(output)
        staging.rename(output)
    return {
        "status": "installed_verified",
        "snapshot_id": manifest["snapshot_id"],
        "source_url": SOURCE_URL,
        "files": len(manifest["files"]),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "data/raw/ad_sampledata")
    args = parser.parse_args(argv)
    print(json.dumps(install(args.output)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
