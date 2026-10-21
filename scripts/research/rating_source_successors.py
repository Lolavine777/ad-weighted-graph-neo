"""Generate current-source successors while preserving historical package bytes."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GOAL_SOURCE_FILES = {
    "src/engine/graph.py",
    "src/engine/ranking/adapter_145.py",
    "src/engine/ranking/orchestration.py",
    "src/engine/ranking/replay.py",
    "src/engine/ranking/resolution_service.py",
    "src/engine/ranking/resolver.py",
    "src/engine/ranking/validation.py",
    "src/engine/ranking/verification.py",
    "scripts/research/rating_source_successors.py",
}


def main():
    successors = (
        ("likelihood-v1", 10, "1.9.0"),
        ("scenario-basis-v1", 11, "1.11.0"),
    )
    for package, previous, _ in successors:
        destination = (
            ROOT / "docs/research/ratings" / package / f"source-manifest-v{previous + 1}.json"
        )
        if destination.exists():
            raise ValueError("Preserve source successors; select a new version")
    for package, previous, version in successors:
        parent = ROOT / "docs/research/ratings" / package
        original = parent / f"source-manifest-v{previous}.json"
        packet = json.loads(original.read_text(encoding="utf-8"))
        packet["schema_version"] = version
        packet["previous_source_manifest_sha256"] = (
            "sha256:" + hashlib.sha256(original.read_bytes()).hexdigest()
        )
        names = set(packet["source_pins"]) | GOAL_SOURCE_FILES
        pins = {}
        for name in sorted(names):
            path = ROOT / name
            if not path.resolve().is_relative_to(ROOT.resolve()):
                raise ValueError("Source pin escapes repository")
            pins[name] = "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()
        packet["source_pins"] = pins
        destination = parent / f"source-manifest-v{previous + 1}.json"
        destination.write_text(
            json.dumps(packet, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )


if __name__ == "__main__":
    main()
