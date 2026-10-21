"""Generate or verify manifests without loading raw records into memory."""

import argparse
import json
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.data.manifest import (  # noqa: E402
    ManifestError,
    generate_manifest,
    load_file_metadata,
    load_manifest,
    verify_manifest,
    write_manifest,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    generate = commands.add_parser("generate", help="fingerprint an immutable local snapshot")
    generate.add_argument("source", type=Path)
    generate.add_argument("--output", required=True, type=Path)
    generate.add_argument("--dataset-id", required=True)
    generate.add_argument("--collector-name", required=True)
    generate.add_argument("--collector-version", required=True, help="version or 'unknown'")
    generate.add_argument("--collected-at", required=True, help="UTC timestamp or 'unknown'")
    generate.add_argument(
        "--file-metadata",
        type=Path,
        help="JSON mapping every relative path to collector and collected_at",
    )
    verify = commands.add_parser("verify", help="check file membership, sizes, and checksums")
    verify.add_argument("source", type=Path)
    verify.add_argument("manifest", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "generate":
            manifest = generate_manifest(
                args.source,
                dataset_id=args.dataset_id,
                collector_name=args.collector_name,
                collector_version=None
                if args.collector_version == "unknown"
                else args.collector_version,
                collected_at=None if args.collected_at == "unknown" else args.collected_at,
                file_metadata=load_file_metadata(args.file_metadata)
                if args.file_metadata
                else None,
            )
            write_manifest(manifest, args.output, source=args.source)
            print(
                json.dumps(
                    {
                        "status": "generated",
                        "snapshot_id": manifest["snapshot_id"],
                        "summary": manifest["summary"],
                    },
                    sort_keys=True,
                )
            )
            return 0
        issues = verify_manifest(args.source, load_manifest(args.manifest))
        print(
            json.dumps(
                {"status": "failed" if issues else "verified", "issues": issues},
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return 1 if issues else 0
    except ManifestError as exc:
        print(
            json.dumps({"status": "error", "message": str(exc)}, ensure_ascii=False),
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
