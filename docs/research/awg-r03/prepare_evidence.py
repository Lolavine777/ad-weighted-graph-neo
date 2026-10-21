"""Unpack the frozen AWG-R02 evidence into a new scratch directory."""
import argparse
import hashlib
from pathlib import Path
import zipfile

EXPECTED_SHA256 = "9f0180fce0db17902e361857262a89ac6e89391df6460bf8b41812f082b1d64a"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="New or empty scratch directory")
    args = parser.parse_args()
    archive = Path(__file__).with_name("AWG-R02_Experimental_Evidence.zip")
    if hashlib.sha256(archive.read_bytes()).hexdigest() != EXPECTED_SHA256:
        raise SystemExit("Evidence archive checksum does not match frozen R02")
    destination = args.output.resolve()
    if destination.exists() and (not destination.is_dir() or any(destination.iterdir())):
        raise SystemExit("Use a new or empty output directory; existing files are never overwritten")
    with zipfile.ZipFile(archive) as package:
        for member in package.infolist():
            target = (destination / member.filename).resolve()
            if not target.is_relative_to(destination):
                raise SystemExit("Invalid archive member path")
        destination.mkdir(parents=True, exist_ok=True)
        package.extractall(destination)
    root = destination / "AWG-R02"
    print(f"Evidence ready: {root}")
    print(f"Read setup and baseline/harness cautions: {root / 'README.md'}")


if __name__ == "__main__":
    main()
