"""Exercise Git's Windows checkout conversion for every acceptance byte pin."""

import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_acceptance_pins_survive_autocrlf_checkout(tmp_path):
    manifest = json.loads(
        (ROOT / "reports/research/week4-guided-exploration-acceptance-manifest-v16.json").read_text(
            encoding="utf-8"
        )
    )
    pins = manifest["execution"]["file_sha256"]
    # Use the tracked blobs and actual attributes, rather than normalizing bytes
    # in Python. This also catches newly pinned fixtures lacking an LF policy.
    subprocess.run(
        [
            "git",
            "-c",
            "core.autocrlf=true",
            "checkout-index",
            "--force",
            f"--prefix={tmp_path.as_posix()}/",
            "--stdin",
            "-z",
        ],
        cwd=ROOT,
        input=("\0".join(pins) + "\0").encode("utf-8"),
        capture_output=True,
        check=True,
    )
    for name, digest in pins.items():
        assert hashlib.sha256((tmp_path / name).read_bytes()).hexdigest() == digest, name
