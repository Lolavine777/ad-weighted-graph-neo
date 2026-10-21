"""Compare semantic output and reproducibility pins; retain per-run runtime metadata."""

import argparse
import json
from pathlib import Path

from src.engine.query_cli import SCHEMA_VERSION, TOP_K_SCHEMA_VERSION, canonical_json, digest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("first", type=Path)
    parser.add_argument("second", type=Path)
    args = parser.parse_args()
    try:
        runs = [json.loads(p.read_text(encoding="utf-8")) for p in (args.first, args.second)]
        for run in runs:
            if run["schema_version"] not in {SCHEMA_VERSION, TOP_K_SCHEMA_VERSION}:
                raise ValueError("unsupported schema_version")
            actual = digest(canonical_json(run["semantic"]).encode("utf-8"))
            if actual != run["reproducibility"]["semantic_sha256"]:
                raise ValueError("semantic digest mismatch")
        equal = (
            runs[0]["schema_version"] == runs[1]["schema_version"]
            and runs[0]["semantic"] == runs[1]["semantic"]
        )
        pins = (
            "revision",
            "tracked_changes",
            "effective_config_sha256",
            "source_files",
            "config_files",
        )
        equal = equal and all(
            runs[0]["reproducibility"][key] == runs[1]["reproducibility"][key] for key in pins
        )
        # References may be relocated between clean checkouts; compare input bytes by role.
        inputs = [{k: v["sha256"] for k, v in r["reproducibility"]["inputs"].items()} for r in runs]
        equal = equal and inputs[0] == inputs[1]
        equal = equal and runs[0]["acceptance"] == runs[1]["acceptance"]
        print(
            json.dumps(
                {
                    "equal": equal,
                    "semantic_sha256": runs[0]["reproducibility"]["semantic_sha256"],
                    "runtime_compared": False,
                },
                sort_keys=True,
            )
        )
        return 0 if equal else 1
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(json.dumps({"equal": False, "error": str(exc)}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
