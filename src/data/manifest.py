"""Versioned manifests for immutable, local snapshots; never interpret AD records."""

import hashlib
import json
import os
import re
import stat
import tempfile
import unicodedata
from datetime import datetime
from pathlib import Path

CHUNK_SIZE = 1024 * 1024
SCHEMA_VERSION = 1
_HASH = re.compile(r"[0-9a-f]{64}")
_RESERVED = re.compile(r"(?:CON|PRN|AUX|NUL|COM[1-9¹²³]|LPT[1-9¹²³])(?:\..*)?", re.I)


class ManifestError(ValueError):
    """Invalid manifest or unsafe/inaccessible snapshot; messages omit absolute paths."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ManifestError(message)


def canonical_path(value: str) -> str:
    """Normalize a relative reference; reject names not portable to Windows/Linux."""
    _require(isinstance(value, str) and bool(value), "invalid relative path")
    value = unicodedata.normalize("NFC", value.replace("\\", "/"))
    for part in value.split("/"):
        _require(
            bool(part)
            and part not in {".", ".."}
            and not part.endswith((" ", "."))
            and not _RESERVED.fullmatch(part)
            and not any(c in '<>:"|?*' or ord(c) < 32 or 0xD800 <= ord(c) <= 0xDFFF for c in part),
            "unsafe or nonportable relative path",
        )
    return value


def _register_path(value: str, seen: dict[str, str]) -> None:
    # Include directories: A/x and a/y also collide on case-insensitive filesystems.
    parts = value.split("/")
    for end in range(1, len(parts) + 1):
        prefix = "/".join(parts[:end])
        key = prefix.casefold()
        _require(key not in seen or seen[key] == prefix, "normalized path collision")
        seen[key] = prefix


def _linked(path: Path) -> bool:
    return path.is_symlink() or path.is_junction()


def _root(source: Path) -> Path:
    source = Path(os.path.abspath(source))
    _require(not any(_linked(p) for p in (source, *source.parents)), "symlink/junction root")
    _require(source.is_dir(), "snapshot root is missing or unreadable")
    return source


def _signature(info: os.stat_result) -> tuple[int, ...]:
    # ``st_ctime_ns`` is creation time on Windows and can change as a side effect
    # of opening a file; it is not a content-stability signal there. Size and
    # modification time are stable across the Windows/Linux lstat/fstat boundary.
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns)


def _scan(root: Path) -> dict[str, tuple[Path, tuple[int, ...]]]:
    _root(root)
    files = {}
    seen: dict[str, str] = {}
    normalized: set[str] = set()

    def visit(directory: Path) -> None:
        try:
            with os.scandir(directory) as entries:
                children = sorted(entries, key=lambda entry: entry.name)
            for child in children:
                path = Path(child.path)
                _require(not _linked(path), "symlink/junction in snapshot")
                _require("\\" not in child.name, "nonportable filename separator")
                relative = canonical_path(path.relative_to(root).as_posix())
                _require(relative not in normalized, "normalized path collision")
                normalized.add(relative)
                _register_path(relative, seen)
                info = path.lstat()
                if stat.S_ISDIR(info.st_mode):
                    visit(path)
                else:
                    _require(stat.S_ISREG(info.st_mode), "non-regular file in snapshot")
                    files[relative] = (path, _signature(info))
        except OSError as exc:
            raise ManifestError("unreadable snapshot directory or entry") from exc

    visit(root)
    return dict(sorted(files.items()))


def _hash_file(path: Path, signature: tuple[int, ...]) -> tuple[int, str]:
    try:
        _require(not _linked(path), "symlink/junction encountered while reading")
        flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
        with os.fdopen(os.open(path, flags), "rb") as stream:
            before = os.fstat(stream.fileno())
            _require(stat.S_ISREG(before.st_mode), "non-regular file encountered while reading")
            _require(_signature(before) == signature, "snapshot changed while reading")
            digest = hashlib.sha256()
            size = 0
            while chunk := stream.read(CHUNK_SIZE):
                digest.update(chunk)
                size += len(chunk)
            _require(
                _signature(os.fstat(stream.fileno())) == signature and size == before.st_size,
                "snapshot changed while reading",
            )
        return size, digest.hexdigest()
    except OSError as exc:
        raise ManifestError("unreadable file") from exc


def _canonical(value: dict) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode("utf-8")


def _identity(manifest: dict) -> str:
    payload = {key: value for key, value in manifest.items() if key != "snapshot_id"}
    return "sha256:" + hashlib.sha256(_canonical(payload)).hexdigest()


def _text(value: object) -> bool:
    return (
        isinstance(value, str)
        and bool(value.strip())
        and value == unicodedata.normalize("NFC", value)
        and "/" not in value
        and "\\" not in value
        and not any(ord(c) < 32 or 0xD800 <= ord(c) <= 0xDFFF for c in value)
    )


def _validate_collection(collector: object, timestamp: object) -> None:
    _require(
        isinstance(collector, dict) and set(collector) == {"name", "version"}, "invalid collector"
    )
    _require(_text(collector["name"]), "invalid collector name")
    _require(
        collector["version"] is None or _text(collector["version"]), "invalid collector version"
    )
    if timestamp is not None:
        _require(
            isinstance(timestamp, str)
            and re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", timestamp) is not None,
            "collected_at must be UTC YYYY-MM-DDTHH:MM:SSZ or null",
        )
        try:
            datetime.strptime(timestamp, "%Y-%m-%dT%H:%M:%SZ")
        except ValueError as exc:
            raise ManifestError("invalid collected_at date") from exc


def validate_manifest(manifest: object) -> dict:
    """Strictly validate schema, portable paths, summary, and content-derived identity."""
    _require(isinstance(manifest, dict), "manifest must be an object")
    _require(
        set(manifest)
        == {
            "schema_version",
            "dataset_id",
            "snapshot_id",
            "collector",
            "collected_at",
            "files",
            "summary",
        },
        "invalid manifest fields",
    )
    _require(
        type(manifest["schema_version"]) is int and manifest["schema_version"] == 1,
        "unsupported schema_version",
    )
    _require(
        isinstance(manifest["dataset_id"], str)
        and re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,63}", manifest["dataset_id"]) is not None,
        "dataset_id must be an opaque lowercase slug",
    )
    _validate_collection(manifest["collector"], manifest["collected_at"])
    mixed = manifest["collector"]["name"] == "mixed"
    if mixed:
        _require(
            manifest["collector"]["version"] is None and manifest["collected_at"] is None,
            "mixed snapshot must use null top-level version and collection time",
        )
    files = manifest["files"]
    _require(isinstance(files, list) and bool(files), "empty or invalid files list")
    paths = []
    seen: dict[str, str] = {}
    total = 0
    for entry in files:
        _require(
            isinstance(entry, dict)
            and {"relative_path", "size_bytes", "sha256"} <= set(entry)
            and set(entry)
            <= {"relative_path", "size_bytes", "sha256", "collector", "collected_at"},
            "invalid file entry",
        )
        has_metadata = "collector" in entry or "collected_at" in entry
        if mixed or has_metadata:
            _require(
                "collector" in entry and "collected_at" in entry,
                "per-file collector and collected_at must both be present",
            )
            _validate_collection(entry["collector"], entry["collected_at"])
            _require(entry["collector"]["name"] != "mixed", "file collector must not be mixed")
        path = entry["relative_path"]
        _require(canonical_path(path) == path, "file path must be canonical")
        _register_path(path, seen)
        paths.append(path)
        _require(type(entry["size_bytes"]) is int and entry["size_bytes"] >= 0, "invalid file size")
        _require(
            isinstance(entry["sha256"], str) and _HASH.fullmatch(entry["sha256"]) is not None,
            "invalid SHA-256",
        )
        total += entry["size_bytes"]
    _require(paths == sorted(set(paths)), "files must be sorted and unique")
    path_set = set(paths)
    _require(
        not any(
            "/".join(p.split("/")[:i]) in path_set
            for p in paths
            for i in range(1, len(p.split("/")))
        ),
        "file/directory collision",
    )
    summary = manifest["summary"]
    _require(
        isinstance(summary, dict)
        and set(summary) == {"file_count", "total_size_bytes"}
        and all(type(v) is int for v in summary.values())
        and summary == {"file_count": len(files), "total_size_bytes": total},
        "invalid summary",
    )
    _require(manifest["snapshot_id"] == _identity(manifest), "snapshot_id does not match manifest")
    return manifest


def generate_manifest(
    source: Path,
    *,
    dataset_id: str,
    collector_name: str,
    collector_version: str | None,
    collected_at: str | None,
    file_metadata: dict[str, dict] | None = None,
) -> dict:
    """Fingerprint a whole snapshot, with explicit metadata and no current-time defaults."""
    root = _root(source)
    scanned = _scan(root)
    _require(bool(scanned), "empty snapshot")
    if file_metadata is not None:
        _require(
            isinstance(file_metadata, dict) and set(file_metadata) == set(scanned),
            "file metadata must cover exactly the snapshot files using canonical paths",
        )
        for metadata in file_metadata.values():
            _require(
                isinstance(metadata, dict) and set(metadata) == {"collector", "collected_at"},
                "invalid per-file metadata fields",
            )
            _validate_collection(metadata["collector"], metadata["collected_at"])
    files = []
    for relative, (path, signature) in scanned.items():
        try:
            size, digest = _hash_file(path, signature)
        except ManifestError as exc:
            raise ManifestError(f"{relative}: {exc}") from exc
        files.append({"relative_path": relative, "size_bytes": size, "sha256": digest})
        if file_metadata is not None:
            metadata = file_metadata[relative]
            files[-1].update(
                collector=dict(metadata["collector"]), collected_at=metadata["collected_at"]
            )
    _require(_scan(root) == scanned, "snapshot changed while reading")
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "dataset_id": dataset_id,
        "collector": {"name": collector_name, "version": collector_version},
        "collected_at": collected_at,
        "files": files,
        "summary": {
            "file_count": len(files),
            "total_size_bytes": sum(f["size_bytes"] for f in files),
        },
    }
    manifest["snapshot_id"] = _identity(manifest)
    return validate_manifest(manifest)


def manifest_bytes(manifest: dict) -> bytes:
    return _canonical(validate_manifest(manifest))


def _load_json(path: Path) -> object:
    def unique_keys(pairs: list[tuple[str, object]]) -> dict:
        result = {}
        for key, value in pairs:
            _require(key not in result, "duplicate JSON key")
            result[key] = value
        return result

    try:
        return json.loads(path.read_bytes(), object_pairs_hook=unique_keys)
    except (OSError, UnicodeError, json.JSONDecodeError, RecursionError) as exc:
        raise ManifestError("unreadable or invalid JSON input") from exc


def load_manifest(path: Path) -> dict:
    return validate_manifest(_load_json(path))


def load_file_metadata(path: Path) -> dict:
    metadata = _load_json(path)
    _require(isinstance(metadata, dict), "file metadata must be an object")
    return metadata


def write_manifest(manifest: dict, output: Path, *, source: Path) -> None:
    """Atomically publish outside the raw root; preserve any previous output on failure."""
    root = _root(source)
    output = Path(os.path.abspath(output))
    _require(not output.resolve().is_relative_to(root), "manifest output must be outside snapshot")
    _require(not any(_linked(p) for p in (output, *output.parents)), "symlink/junction output")
    payload = manifest_bytes(manifest)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            dir=output.parent, prefix=".manifest-", delete=False
        ) as file:
            temporary = Path(file.name)
            file.write(payload)
            file.flush()
            os.fsync(file.fileno())
        os.replace(temporary, output)
    except OSError as exc:
        raise ManifestError("unable to write manifest atomically") from exc
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def verify_manifest(source: Path, manifest: dict) -> list[dict[str, str]]:
    """Return sorted discrepancies; unsafe traversal or an invalid manifest is fatal."""
    validate_manifest(manifest)
    root = _root(source)
    scanned = _scan(root)
    expected = {entry["relative_path"]: entry for entry in manifest["files"]}
    issues = []
    for relative in sorted(scanned.keys() | expected.keys()):
        if relative not in scanned:
            issues.append({"status": "removed", "relative_path": relative})
            continue
        if relative not in expected:
            issues.append({"status": "added", "relative_path": relative})
        path, signature = scanned[relative]
        try:
            size, digest = _hash_file(path, signature)
        except ManifestError as exc:
            issues.append(
                {
                    "status": "unreadable" if str(exc) == "unreadable file" else "unstable",
                    "relative_path": relative,
                }
            )
            continue
        if relative in expected:
            if size != expected[relative]["size_bytes"]:
                issues.append({"status": "size_changed", "relative_path": relative})
            if digest != expected[relative]["sha256"]:
                issues.append({"status": "checksum_changed", "relative_path": relative})
    _require(_scan(root) == scanned, "snapshot changed while verifying")
    return issues


def raw_file_reference(manifest: dict, relative_path: str) -> str:
    """Create a contract-compatible reference after confirming manifest membership."""
    validate_manifest(manifest)
    relative_path = canonical_path(relative_path)
    _require(
        any(f["relative_path"] == relative_path for f in manifest["files"]),
        "file is absent from manifest",
    )
    return f"snapshot:{manifest['snapshot_id'].removeprefix('sha256:')}/{relative_path}"


def resolve_reference(manifest: dict, reference: str) -> str:
    """Resolve an audit reference to a canonical relative path, never an absolute path."""
    validate_manifest(manifest)
    prefix = f"snapshot:{manifest['snapshot_id'].removeprefix('sha256:')}/"
    _require(
        isinstance(reference, str) and reference.startswith(prefix), "snapshot reference mismatch"
    )
    relative = reference[len(prefix) :]
    _require(raw_file_reference(manifest, relative) == reference, "noncanonical snapshot reference")
    return relative


def resolve_snapshot_file(source: Path, manifest: dict, reference: str) -> Path:
    """Find and verify referenced bytes, including decomposed Unicode filesystem names.

    Verify the whole snapshot before parsing; this helper additionally checks the
    selected file. Callers must keep the root immutable while resolving and reading.
    """
    relative = resolve_reference(manifest, reference)
    scanned = _scan(_root(source))
    _require(relative in scanned, "referenced file is missing")
    path, signature = scanned[relative]
    size, digest = _hash_file(path, signature)
    expected = next(entry for entry in manifest["files"] if entry["relative_path"] == relative)
    _require(
        size == expected["size_bytes"] and digest == expected["sha256"],
        "referenced file does not match manifest",
    )
    return path


def read_verified_snapshot_file(source: Path, manifest: dict, reference: str) -> bytes:
    """Read and verify one referenced file, returning the exact verified bytes.

    The whole snapshot must be verified by the caller first.  This helper keeps
    hashing and reading on the same file descriptor so a parser does not hash
    one pathname read and parse a later, different pathname read.
    """
    relative = resolve_reference(manifest, reference)
    root = _root(source)
    scanned = _scan(root)
    _require(relative in scanned, "referenced file is missing")
    path, signature = scanned[relative]
    expected = next(entry for entry in manifest["files"] if entry["relative_path"] == relative)
    try:
        _require(not _linked(path), "symlink/junction encountered while reading")
        flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
        with os.fdopen(os.open(path, flags), "rb") as stream:
            before = os.fstat(stream.fileno())
            _require(stat.S_ISREG(before.st_mode), "non-regular file encountered while reading")
            _require(_signature(before) == signature, "snapshot changed while reading")
            digest = hashlib.sha256()
            chunks = []
            size = 0
            while chunk := stream.read(CHUNK_SIZE):
                digest.update(chunk)
                chunks.append(chunk)
                size += len(chunk)
            _require(
                _signature(os.fstat(stream.fileno())) == signature and size == before.st_size,
                "snapshot changed while reading",
            )
        _require(size == expected["size_bytes"], "referenced file does not match manifest")
        _require(
            digest.hexdigest() == expected["sha256"], "referenced file does not match manifest"
        )
        payload = b"".join(chunks)
    except OSError as exc:
        raise ManifestError("unreadable file") from exc
    _require(_scan(root) == scanned, "snapshot changed while reading")
    return payload
