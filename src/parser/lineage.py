"""Canonical helpers for ordered structural derivation lineage."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence

LINEAGE_VERSION = "1.1.0"


def canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def provenance_ref(provenance: Mapping[str, object]) -> str:
    """Return a stable reference to one raw provenance record."""

    digest = hashlib.sha256(canonical_json(dict(provenance)).encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def path_key(path: Mapping[str, object]) -> str:
    return canonical_json(path)


def sorted_unique_paths(paths: Sequence[Mapping[str, object]]) -> list[dict]:
    """Deduplicate and deterministically order complete derivation paths."""

    unique = {path_key(path): dict(path) for path in paths}
    return [unique[key] for key in sorted(unique)]


__all__ = ["LINEAGE_VERSION", "canonical_json", "path_key", "provenance_ref", "sorted_unique_paths"]
