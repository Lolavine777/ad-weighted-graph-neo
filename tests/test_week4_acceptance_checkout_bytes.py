"""Exercise Git's Windows checkout conversion for every acceptance byte pin."""

import hashlib
import subprocess
from pathlib import Path

from scripts.research.scenario_rating_pack import HISTORICAL_SOURCE_MANIFESTS
from scripts.research.week4_acceptance_runner import file_pins

ROOT = Path(__file__).resolve().parents[1]


def test_acceptance_pins_survive_autocrlf_checkout(tmp_path):
    pins = file_pins() | HISTORICAL_SOURCE_MANIFESTS
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
    for name in pins:
        committed = subprocess.check_output(["git", "show", f":{name}"], cwd=ROOT)
        assert hashlib.sha256((tmp_path / name).read_bytes()).hexdigest() == (
            hashlib.sha256(committed).hexdigest()
        ), name
