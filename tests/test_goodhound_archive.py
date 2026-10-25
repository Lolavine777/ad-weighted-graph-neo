"""Historical helpers must remain byte-identical to the published evidence."""

import ast
import hashlib
import json
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / "docs/research/evidence/goodhound-20261024"


def sha(path):
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.mark.parametrize("kind", ["evaluation", "suitability"])
def test_goodhound_original_helpers_match_published_manifest(kind):
    name = "evaluation" if kind == "evaluation" else "positive-control"
    report = json.loads(
        (ROOT / "reports/neo" / f"goodhound-{name}-results.json").read_text(encoding="utf-8")
    )
    expected = (
        report["evidence_manifest_sha256"]
        if kind == "evaluation"
        else report["local_evidence"]["manifest_sha256"]
    )
    folder = ARCHIVE / kind
    manifest = folder / "evidence-manifest.json"
    assert sha(manifest) == expected
    data = json.loads(manifest.read_text(encoding="utf-8"))
    entries = data if kind == "evaluation" else {f["path"]: f["sha256"] for f in data["files"]}
    helpers = sorted(folder.glob("*.py"))
    assert len(helpers) == (3 if kind == "evaluation" else 5)
    for helper in helpers:
        assert sha(helper) == entries[helper.name]
        ast.parse(helper.read_text(encoding="utf-8"))
    if kind == "evaluation":
        assert sha(folder / "time-policy.json") == entries["time-policy.json"]


def test_goodhound_archive_survives_windows_checkout(tmp_path):
    paths = (
        subprocess.check_output(
            ["git", "ls-files", "-z", "--", ARCHIVE.relative_to(ROOT).as_posix()], cwd=ROOT
        )
        .decode("utf-8")
        .split("\0")[:-1]
    )
    assert paths
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
        input=("\0".join(paths) + "\0").encode("utf-8"),
        capture_output=True,
        check=True,
    )
    for name in paths:
        assert sha(tmp_path / name) == sha(ROOT / name), name
