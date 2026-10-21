"""Install the pinned public SEAMLESS lab snapshot without overwriting local data.

Run: python -m scripts.download_seamless
The raw directory remains gitignored; no credentials or secret material is downloaded.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import tempfile
import urllib.request
import zipfile
from pathlib import Path

from src.data.manifest import load_manifest, verify_manifest

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "data/samples/manifests/seamless-raw-v1.json"
SOURCE_COMMIT = "3febc4089421725f9527c187f78d064ad09d5158"
ARCHIVE_NAME = "20210920185958_BloodHound.zip"
ARCHIVE_SHA256 = "b8e9f003dd51a98838be86d8f98b0844a19a7876aad0a81b525f19e110105813"
ARCHIVE_BYTES = 268200
SOURCE_URL = (
    "https://raw.githubusercontent.com/mike-nolan-councilman/Bloodhound_Data/"
    f"{SOURCE_COMMIT}/{ARCHIVE_NAME}"
)


def install(output: Path, *, archive: Path | None = None) -> dict:
    """Verify archive bytes and all six manifest entries before an atomic install."""
    output = output.absolute()
    manifest = load_manifest(MANIFEST)
    if output.exists() or output.is_symlink():
        errors = verify_manifest(output, manifest)
        if errors:
            raise ValueError(f"existing raw directory does not match the manifest: {errors}")
        return {"status": "already_verified", "snapshot_id": manifest["snapshot_id"]}

    if archive is None:
        with urllib.request.urlopen(SOURCE_URL, timeout=30) as response:
            data = response.read(ARCHIVE_BYTES + 1)
    else:
        with archive.open("rb") as stream:
            data = stream.read(ARCHIVE_BYTES + 1)
    if len(data) != ARCHIVE_BYTES or hashlib.sha256(data).hexdigest() != ARCHIVE_SHA256:
        raise ValueError("archive size or SHA-256 differs from the pinned public snapshot")

    expected = {f["relative_path"]: f for f in manifest["files"]}
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".seamless-", dir=output.parent) as temporary:
        staging = Path(temporary) / "raw"
        staging.mkdir()
        with zipfile.ZipFile(io.BytesIO(data)) as zipped:
            names = zipped.namelist()
            if len(names) != len(expected) or set(names) != set(expected):
                raise ValueError("archive must contain exactly the pinned six raw files")
            for name, entry in expected.items():
                # Names come from the validated manifest, never from an extraction path.
                member = zipped.getinfo(name)
                if member.file_size != entry["size_bytes"]:
                    raise ValueError(f"archive member size mismatch: {name}")
                (staging / name).write_bytes(zipped.read(member))
        errors = verify_manifest(staging, manifest)
        if errors:
            raise ValueError(f"extracted snapshot does not match the manifest: {errors}")
        if output.exists() or output.is_symlink():
            raise FileExistsError("raw destination appeared during download; refusing to overwrite")
        staging.rename(output)
    return {
        "status": "installed_verified",
        "snapshot_id": manifest["snapshot_id"],
        "source_url": SOURCE_URL,
        "archive_sha256": ARCHIVE_SHA256,
        "file_count": len(expected),
        "raw_bytes": manifest["summary"]["total_size_bytes"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "data/raw/SEAMLESS")
    parser.add_argument("--archive", type=Path, help="Use an already downloaded pinned archive")
    args = parser.parse_args(argv)
    print(json.dumps(install(args.output, archive=args.archive), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
