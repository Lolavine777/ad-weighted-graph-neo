"""Offline checks for the public snapshot installer: bytes, paths and local data."""

import hashlib
import zipfile

import pytest

from scripts import download_seamless as downloader
from src.data.manifest import generate_manifest, manifest_bytes, verify_manifest


@pytest.fixture
def pinned(tmp_path, monkeypatch):
    raw = tmp_path / "source"
    raw.mkdir()
    (raw / "users.json").write_bytes(b'{"data": []}\n')
    manifest = generate_manifest(
        raw,
        dataset_id="installer-test",
        collector_name="synthetic",
        collector_version=None,
        collected_at=None,
    )
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_bytes(manifest_bytes(manifest))
    archive = tmp_path / "pinned.zip"
    with zipfile.ZipFile(archive, "w") as zipped:
        zipped.write(raw / "users.json", "users.json")
    monkeypatch.setattr(downloader, "MANIFEST", manifest_path)
    monkeypatch.setattr(
        downloader, "ARCHIVE_SHA256", hashlib.sha256(archive.read_bytes()).hexdigest()
    )
    monkeypatch.setattr(downloader, "ARCHIVE_BYTES", archive.stat().st_size)
    return tmp_path / "installed", archive, manifest


def test_verified_install_is_idempotent_without_network(pinned):
    destination, archive, manifest = pinned
    result = downloader.install(destination, archive=archive)
    assert result["status"] == "installed_verified"
    assert verify_manifest(destination, manifest) == []
    archive.unlink()
    assert downloader.install(destination)["status"] == "already_verified"


def test_corrupt_archive_cannot_install(pinned):
    destination, archive, _ = pinned
    data = bytearray(archive.read_bytes())
    data[-1] ^= 1
    archive.write_bytes(data)
    with pytest.raises(ValueError, match="SHA-256"):
        downloader.install(destination, archive=archive)
    assert not destination.exists()


def test_existing_nonmatching_raw_is_never_overwritten(pinned):
    destination, archive, _ = pinned
    destination.mkdir()
    (destination / "users.json").write_bytes(b"local data")
    with pytest.raises(ValueError, match="existing raw directory"):
        downloader.install(destination, archive=archive)
    assert (destination / "users.json").read_bytes() == b"local data"


def test_archive_paths_are_checked_before_writing(pinned, monkeypatch):
    destination, archive, _ = pinned
    with zipfile.ZipFile(archive, "w") as zipped:
        zipped.writestr("../escape.json", b"not a manifest entry")
    monkeypatch.setattr(
        downloader, "ARCHIVE_SHA256", hashlib.sha256(archive.read_bytes()).hexdigest()
    )
    monkeypatch.setattr(downloader, "ARCHIVE_BYTES", archive.stat().st_size)
    with pytest.raises(ValueError, match="exactly the pinned"):
        downloader.install(destination, archive=archive)
    assert not destination.exists()
    assert not (destination.parent / "escape.json").exists()
