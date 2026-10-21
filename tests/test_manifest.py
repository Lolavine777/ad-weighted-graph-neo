"""Synthetic snapshot integrity, portability, atomicity, and CLI regression cases."""

import copy
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.snapshot_manifest import main
from src.data import manifest as module
from src.data.manifest import (
    ManifestError,
    canonical_path,
    generate_manifest,
    load_manifest,
    manifest_bytes,
    raw_file_reference,
    resolve_reference,
    resolve_snapshot_file,
    validate_manifest,
    verify_manifest,
    write_manifest,
)

ROOT = Path(__file__).resolve().parents[1]
METADATA = {
    "dataset_id": "synthetic-v1",
    "collector_name": "synthetic",
    "collector_version": "1.0",
    "collected_at": "2026-01-01T00:00:00Z",
}


@pytest.fixture
def snapshot(tmp_path):
    root = tmp_path / "input"
    (root / "nested").mkdir(parents=True)
    (root / "empty.bin").write_bytes(b"")
    (root / "nested" / "café file.txt").write_bytes(b"synthetic\n")
    return root


def generate(root):
    return generate_manifest(root, **METADATA)


def test_golden_bytes_identity_and_relocated_snapshot(snapshot, tmp_path):
    manifest = generate(snapshot)
    golden = ROOT / "data/samples/manifests/synthetic-v1.json"
    assert manifest_bytes(manifest) == golden.read_bytes()
    assert load_manifest(golden) == manifest
    assert manifest_bytes(generate(ROOT / "data/samples/snapshot-input")) == golden.read_bytes()
    assert manifest["summary"] == {"file_count": 2, "total_size_bytes": 10}
    payload = {k: v for k, v in manifest.items() if k != "snapshot_id"}
    encoded = (
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode()
    assert manifest["snapshot_id"] == "sha256:" + hashlib.sha256(encoded).hexdigest()
    relocated = tmp_path / "relocated"
    shutil.copytree(snapshot, relocated)
    for path in relocated.rglob("*"):
        os.utime(path, (1234567890, 1234567890))
    assert manifest_bytes(generate(relocated)) == golden.read_bytes()
    assert verify_manifest(relocated, manifest) == []


def test_added_removed_size_and_same_size_corruption(snapshot):
    manifest = generate(snapshot)
    (snapshot / "empty.bin").unlink()
    (snapshot / "added.bin").write_bytes(b"new")
    target = snapshot / "nested" / "café file.txt"
    target.write_bytes(b"corrupted\n")
    issues = verify_manifest(snapshot, manifest)
    assert issues == [
        {"status": "added", "relative_path": "added.bin"},
        {"status": "removed", "relative_path": "empty.bin"},
        {"status": "checksum_changed", "relative_path": "nested/café file.txt"},
    ]
    target.write_bytes(b"longer corrupted bytes")
    assert {i["status"] for i in verify_manifest(snapshot, manifest)} == {
        "added",
        "removed",
        "checksum_changed",
        "size_changed",
    }


def test_empty_generation_but_removal_report_on_verify(snapshot):
    manifest = generate(snapshot)
    shutil.rmtree(snapshot)
    snapshot.mkdir()
    with pytest.raises(ManifestError, match="empty snapshot"):
        generate(snapshot)
    assert [i["status"] for i in verify_manifest(snapshot, manifest)] == ["removed", "removed"]


def test_unreadable_file_is_fatal_for_generate_and_reported_for_verify(snapshot, monkeypatch):
    manifest = generate(snapshot)
    original = module.os.open

    def denied(path, *args, **kwargs):
        if Path(path).name == "empty.bin":
            raise PermissionError("private absolute path must not leak")
        return original(path, *args, **kwargs)

    monkeypatch.setattr(module.os, "open", denied)
    with pytest.raises(ManifestError, match="empty.bin: unreadable file"):
        generate(snapshot)
    assert verify_manifest(snapshot, manifest) == [
        {"status": "unreadable", "relative_path": "empty.bin"}
    ]


def test_unreadable_directory_does_not_silently_skip(snapshot, monkeypatch):
    def denied(*args):
        raise PermissionError("private path")

    monkeypatch.setattr(module.os, "scandir", denied)
    with pytest.raises(ManifestError, match="unreadable snapshot directory"):
        generate(snapshot)


@pytest.mark.parametrize("directory", [False, True])
def test_symlink_rejected(snapshot, tmp_path, directory):
    external = tmp_path / "external"
    if directory:
        external.mkdir()
    else:
        external.write_bytes(b"private")
    link = snapshot / "link"
    try:
        link.symlink_to(external, target_is_directory=directory)
    except OSError:
        pytest.skip("OS does not permit symlink creation")
    with pytest.raises(ManifestError, match="symlink/junction"):
        generate(snapshot)
    if directory:
        with pytest.raises(ManifestError, match="symlink/junction root"):
            generate(link)


def test_windows_junction_rejected(snapshot, tmp_path):
    if os.name != "nt":
        pytest.skip("Windows junction test")
    target = tmp_path / "target"
    target.mkdir()
    subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(snapshot / "junction"), str(target)],
        check=True,
        capture_output=True,
    )
    with pytest.raises(ManifestError, match="symlink/junction"):
        generate(snapshot)


@pytest.mark.parametrize("names", [("A", "a"), ("café", "cafe\u0301")])
def test_filesystem_normalization_collisions(tmp_path, names):
    for name in names:
        (tmp_path / name).write_bytes(b"x")
    if len(list(tmp_path.iterdir())) != 2:
        pytest.skip("filesystem already aliases the two names")
    with pytest.raises(ManifestError, match="collision"):
        generate(tmp_path)


@pytest.mark.parametrize(
    "bad",
    [
        "../x",
        "/x",
        "C:\\x",
        "a//b",
        "./x",
        "a/../b",
        "NUL.json",
        "x.",
        "x ",
        "a:b",
        "a\x00b",
        "a?b",
        "CON",
        "COM¹.txt",
    ],
)
def test_unsafe_paths_rejected(bad):
    with pytest.raises(ManifestError):
        canonical_path(bad)


def test_separator_and_unicode_normalization():
    assert canonical_path("nested\\cafe\u0301 file.txt") == "nested/café file.txt"


def test_nonportable_physical_filename_and_fifo_rejected(tmp_path):
    if os.name == "nt":
        pytest.skip("Windows already rejects these filenames")
    bad = tmp_path / "nested\\name"
    bad.write_bytes(b"x")
    with pytest.raises(ManifestError, match="separator"):
        generate(tmp_path)
    bad.unlink()
    os.mkfifo(tmp_path / "pipe")
    with pytest.raises(ManifestError, match="non-regular"):
        generate(tmp_path)


@pytest.mark.parametrize(
    "change",
    [
        lambda m: m.update(schema_version=2),
        lambda m: m.update(schema_version=True),
        lambda m: m.update(extra="forbidden"),
        lambda m: m.update(collected_at="2026-02-30T00:00:00Z"),
        lambda m: m.update(collected_at="2026-01-01T00:00:00+00:00"),
        lambda m: m["collector"].update(version=""),
        lambda m: m["files"][0].update(relative_path="../outside"),
        lambda m: m["files"][0].update(size_bytes=True),
        lambda m: m["files"][0].update(sha256="A" * 64),
        lambda m: m["files"].reverse(),
        lambda m: m["files"].append(m["files"][0]),
        lambda m: m["files"][1].update(relative_path="empty.bin/x"),
        lambda m: m["files"][1].update(relative_path="EMPTY.bin"),
        lambda m: m["summary"].update(file_count=999),
        lambda m: m.update(snapshot_id="sha256:" + "0" * 64),
    ],
)
def test_malformed_manifest_rejected_before_reading(snapshot, monkeypatch, change):
    manifest = generate(snapshot)
    change(manifest)

    def unexpected(*args):
        pytest.fail("must validate manifest before touching snapshot")

    monkeypatch.setattr(module, "_scan", unexpected)
    with pytest.raises(ManifestError):
        verify_manifest(snapshot, manifest)


def test_case_colliding_directory_prefixes_in_manifest(snapshot):
    manifest = generate(snapshot)
    manifest["files"][0]["relative_path"] = "Nested/empty.bin"
    with pytest.raises(ManifestError, match="collision"):
        validate_manifest(manifest)


def test_unknown_metadata_and_metadata_identity(snapshot):
    unknown = generate_manifest(
        snapshot, **{**METADATA, "collector_version": None, "collected_at": None}
    )
    assert unknown["collected_at"] is None
    assert unknown["collector"]["version"] is None
    assert unknown["snapshot_id"] != generate(snapshot)["snapshot_id"]


def test_mixed_raw_directory_cli_and_per_file_provenance(snapshot, tmp_path):
    metadata = {
        "empty.bin": {
            "collector": {"name": "collector-a", "version": "1"},
            "collected_at": "2026-01-01T00:00:00Z",
        },
        "nested/café file.txt": {
            "collector": {"name": "collector-b", "version": None},
            "collected_at": "2026-01-02T00:00:00Z",
        },
    }
    config = tmp_path / "metadata.json"
    config.write_text(json.dumps(metadata), encoding="utf-8")
    output = tmp_path / "manifest.json"
    args = [
        "generate",
        str(snapshot),
        "--output",
        str(output),
        "--dataset-id",
        "synthetic-mixed",
        "--collector-name",
        "mixed",
        "--collector-version",
        "unknown",
        "--collected-at",
        "unknown",
        "--file-metadata",
        str(config),
    ]
    assert main(args) == 0
    first_bytes = output.read_bytes()
    manifest = load_manifest(output)
    assert verify_manifest(snapshot, manifest) == []
    assert manifest["summary"]["file_count"] == 2
    for entry in manifest["files"]:
        assert {k: entry[k] for k in ("collector", "collected_at")} == metadata[
            entry["relative_path"]
        ]
        reference = raw_file_reference(manifest, entry["relative_path"])
        assert resolve_snapshot_file(snapshot, manifest, reference).is_relative_to(snapshot)
    config.write_text(json.dumps(dict(reversed(list(metadata.items())))), encoding="utf-8")
    assert main(args) == 0
    assert output.read_bytes() == first_bytes
    metadata["empty.bin"]["collector"]["version"] = "2"
    config.write_text(json.dumps(metadata), encoding="utf-8")
    assert main(args) == 0
    assert load_manifest(output)["snapshot_id"] != manifest["snapshot_id"]


@pytest.mark.parametrize(
    "change",
    [
        lambda m: m.pop("empty.bin"),
        lambda m: m.update(extra=m["empty.bin"]),
        lambda m: m["empty.bin"].update(size_bytes=1),
        lambda m: m["empty.bin"].pop("collected_at"),
        lambda m: m["empty.bin"]["collector"].update(name="mixed"),
    ],
)
def test_invalid_mixed_metadata_rejected(snapshot, change):
    metadata = {
        p: {"collector": {"name": "synthetic", "version": None}, "collected_at": None}
        for p in ("empty.bin", "nested/café file.txt")
    }
    change(metadata)
    with pytest.raises(ManifestError):
        generate_manifest(
            snapshot,
            **{
                **METADATA,
                "collector_name": "mixed",
                "collector_version": None,
                "collected_at": None,
            },
            file_metadata=metadata,
        )


def test_mixed_requires_explicit_per_file_metadata(snapshot):
    with pytest.raises(ManifestError, match="both be present"):
        generate_manifest(
            snapshot,
            **{
                **METADATA,
                "collector_name": "mixed",
                "collector_version": None,
                "collected_at": None,
            },
        )


def test_decomposed_unicode_resolves_to_actual_verified_file(tmp_path):
    root = tmp_path / "input"
    root.mkdir()
    path = root / "cafe\u0301.txt"
    path.write_bytes(b"synthetic")
    manifest = generate(root)
    assert manifest["files"][0]["relative_path"] == "café.txt"
    reference = raw_file_reference(manifest, "café.txt")
    assert resolve_snapshot_file(root, manifest, reference).read_bytes() == b"synthetic"
    path.write_bytes(b"corrupted")
    with pytest.raises(ManifestError, match="does not match"):
        resolve_snapshot_file(root, manifest, reference)
    path.unlink()
    with pytest.raises(ManifestError, match="missing"):
        resolve_snapshot_file(root, manifest, reference)


def test_duplicate_json_keys_and_broken_json(tmp_path):
    path = tmp_path / "manifest.json"
    for payload in [b'{"schema_version":1,"schema_version":1}', b"{", b"\xff"]:
        path.write_bytes(payload)
        with pytest.raises(ManifestError):
            load_manifest(path)


def test_atomic_output_preserved_on_replace_failure(snapshot, tmp_path, monkeypatch):
    manifest = generate(snapshot)
    output = tmp_path / "manifest.json"
    output.write_bytes(b"old output")

    def fail(*args):
        raise OSError("simulated write failure")

    monkeypatch.setattr(module.os, "replace", fail)
    with pytest.raises(ManifestError, match="atomically"):
        write_manifest(manifest, output, source=snapshot)
    assert output.read_bytes() == b"old output"
    assert not list(tmp_path.glob(".manifest-*"))


def test_output_cannot_be_inside_snapshot(snapshot):
    with pytest.raises(ManifestError, match="outside snapshot"):
        write_manifest(generate(snapshot), snapshot / "manifest.json", source=snapshot)
    assert not (snapshot / "manifest.json").exists()


def test_change_during_scan_is_rejected(snapshot, monkeypatch):
    original = module._hash_file

    def modify(path, signature):
        result = original(path, signature)
        (snapshot / "new.bin").write_bytes(b"appeared")
        return result

    monkeypatch.setattr(module, "_hash_file", modify)
    with pytest.raises(ManifestError, match="snapshot changed"):
        generate(snapshot)


def test_file_modified_during_read_is_rejected(snapshot, monkeypatch):
    original = module.os.fstat
    calls = 0

    def mutate(descriptor):
        nonlocal calls
        calls += 1
        if calls == 2:
            (snapshot / "empty.bin").write_bytes(b"changed")
        return original(descriptor)

    monkeypatch.setattr(module.os, "fstat", mutate)
    with pytest.raises(ManifestError, match="snapshot changed while reading"):
        generate(snapshot)


def test_opening_files_does_not_make_snapshot_unstable(snapshot):
    manifest = generate(snapshot)
    assert verify_manifest(snapshot, manifest) == []


def test_cli_failed_generation_preserves_existing_output(snapshot, tmp_path, monkeypatch):
    output = tmp_path / "existing.json"
    output.write_bytes(b"previous manifest")

    def failed_read(*args):
        raise ManifestError("unreadable file")

    monkeypatch.setattr(module, "_hash_file", failed_read)
    assert (
        main(
            [
                "generate",
                str(snapshot),
                "--output",
                str(output),
                "--dataset-id",
                "synthetic-v1",
                "--collector-name",
                "synthetic",
                "--collector-version",
                "unknown",
                "--collected-at",
                "unknown",
            ]
        )
        == 2
    )
    assert output.read_bytes() == b"previous manifest"


def test_large_file_reads_are_bounded(snapshot, monkeypatch):
    target = snapshot / "large.bin"
    target.write_bytes(b"x" * (module.CHUNK_SIZE * 2 + 3))
    original = module.os.fdopen
    reads = []

    class Stream:
        def __init__(self, stream):
            self.stream = stream

        def __enter__(self):
            return self

        def __exit__(self, *args):
            self.stream.close()

        def fileno(self):
            return self.stream.fileno()

        def read(self, size):
            assert size == module.CHUNK_SIZE
            reads.append(size)
            return self.stream.read(size)

    monkeypatch.setattr(module.os, "fdopen", lambda *a: Stream(original(*a)))
    manifest = generate(snapshot)
    assert len(reads) >= 4
    assert (
        next(f["sha256"] for f in manifest["files"] if f["relative_path"] == "large.bin")
        == hashlib.sha256(target.read_bytes()).hexdigest()
    )


def test_reference_roundtrip_and_membership(snapshot):
    manifest = generate(snapshot)
    reference = raw_file_reference(manifest, "nested\\café file.txt")
    assert resolve_reference(manifest, reference) == "nested/café file.txt"
    assert str(snapshot) not in reference
    for invalid in [reference.replace("snapshot:", "absolute:"), reference + "/../x"]:
        with pytest.raises(ManifestError):
            resolve_reference(manifest, invalid)
    with pytest.raises(ManifestError, match="absent"):
        raw_file_reference(manifest, "missing.txt")
    other = copy.deepcopy(manifest)
    other["dataset_id"] = "other"
    other["snapshot_id"] = module._identity(other)
    with pytest.raises(ManifestError, match="mismatch"):
        resolve_reference(other, reference)


def test_cli_generate_verify_exit_codes(snapshot, tmp_path, capsys):
    output = tmp_path / "manifest.json"
    args = [
        "generate",
        str(snapshot),
        "--output",
        str(output),
        "--dataset-id",
        "synthetic-v1",
        "--collector-name",
        "synthetic",
        "--collector-version",
        "1.0",
        "--collected-at",
        "2026-01-01T00:00:00Z",
    ]
    assert main(args) == 0
    capsys.readouterr()
    assert main(["verify", str(snapshot), str(output)]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "verified"
    (snapshot / "extra.bin").write_bytes(b"extra")
    assert main(["verify", str(snapshot), str(output)]) == 1
    capsys.readouterr()
    output.write_bytes(b"{")
    assert main(["verify", str(snapshot), str(output)]) == 2
    assert str(tmp_path) not in capsys.readouterr().err


def test_cli_direct_script_runs_from_other_directory(tmp_path):
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts/snapshot_manifest.py"), "--help"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "generate" in result.stdout


def test_provenance_metadata_policy_and_validation(snapshot):
    # 1. Valid known time and version
    valid_manifest = generate_manifest(
        snapshot,
        dataset_id="valid-v1",
        collector_name="sharphound",
        collector_version="2.3.3",
        collected_at="2026-01-01T00:00:00Z",
    )
    assert valid_manifest["schema_version"] == 1
    assert valid_manifest["collected_at"] == "2026-01-01T00:00:00Z"
    assert valid_manifest["collector"]["version"] == "2.3.3"
    assert validate_manifest(valid_manifest) == valid_manifest

    # 2. Honest null metadata (unknown collection time and version)
    null_manifest = generate_manifest(
        snapshot,
        dataset_id="null-v1",
        collector_name="evtx-attack-samples",
        collector_version=None,
        collected_at=None,
    )
    assert null_manifest["schema_version"] == 1
    assert null_manifest["collected_at"] is None
    assert null_manifest["collector"]["version"] is None
    assert validate_manifest(null_manifest) == null_manifest

    # 3. Malformed date formats
    for malformed in [
        "2026-02-30T00:00:00Z",
        "2026-01-01T00:00:00",
        "2026-01-01T00:00:00+00:00",
        "unknown",
        "2026/01/01 00:00:00",
        1234567890,
    ]:
        bad = copy.deepcopy(valid_manifest)
        bad["collected_at"] = malformed
        bad["snapshot_id"] = module._identity(bad)
        with pytest.raises(ManifestError):
            validate_manifest(bad)

    # 4. Missing required fields
    for field in [
        "schema_version",
        "dataset_id",
        "snapshot_id",
        "collector",
        "collected_at",
        "files",
        "summary",
    ]:
        bad = copy.deepcopy(valid_manifest)
        del bad[field]
        with pytest.raises(ManifestError, match="invalid manifest fields"):
            validate_manifest(bad)

    # 5. Invalid snapshot identity
    bad = copy.deepcopy(valid_manifest)
    bad["snapshot_id"] = "sha256:" + "0" * 64
    with pytest.raises(ManifestError, match="snapshot_id does not match manifest"):
        validate_manifest(bad)
