import hashlib
import re
from pathlib import Path

import pytest

from scripts.check_repository import FROZEN_DOCUMENTS, ROOT, broken_links, private_path


@pytest.mark.parametrize(
    "path",
    [
        ".env",
        "nested/.env.local",
        "data/raw/export.json",
        "data/raw/nested/README.md",
        "data/processed/graph.json",
        "reports/generated/metrics.csv",
        "DATA\\RAW\\export.json",
    ],
)
def test_private_files_are_blocked_even_if_force_added(path):
    assert private_path(path)


@pytest.mark.parametrize(
    "path", [".env.example", "data/raw/README.md", "data/samples/toy-graph.json", "README.md"]
)
def test_documentation_and_synthetic_paths_are_allowed(path):
    assert not private_path(path)


def test_local_links_and_missing_targets(tmp_path):
    page = tmp_path / "README.md"
    target = tmp_path / "design notes.md"
    target.write_text("# Design\n", encoding="utf-8")
    page.write_text(
        "[valid](<design notes.md>)\n"
        "[anchor](#heading)\n"
        "[remote](https://example.com/not-fetched)\n"
        "[missing](absent.md)\n"
        "```markdown\n[example](not-a-real-file.md)\n```\n",
        encoding="utf-8",
    )
    errors = broken_links(page, tmp_path)
    assert len(errors) == 1
    assert "absent.md" in errors[0]


def test_link_outside_repository_is_rejected(tmp_path):
    page = tmp_path / "README.md"
    page.write_text("[outside](../outside.md)\n", encoding="utf-8")
    assert len(broken_links(page, tmp_path)) == 1


def test_frozen_documents_exist():
    assert all((ROOT / name).is_file() for name in FROZEN_DOCUMENTS)


def test_dataset_b_hashes_when_present():
    candidate_dirs = [Path("data/raw/dataset_b"), Path("data/raw/ad_sampledata")]
    present_dirs = [d for d in candidate_dirs if d.is_dir()]
    if not present_dirs:
        pytest.skip(
            "Neither data/raw/dataset_b nor data/raw/ad_sampledata is present in local environment"
        )
    inventory = Path("docs/research/data-inventory.md").read_text(encoding="utf-8")
    matches = re.findall(
        r"\|\s*`(20240305\d+_\w+\.json)`\s*\|.*?\|\s*`([0-9a-f]{64})`\s*\|", inventory
    )
    assert len(matches) == 31
    for target_dir in present_dirs:
        for fname, doc_hash in matches:
            fpath = target_dir / fname
            assert fpath.exists(), f"Missing file {fname} in {target_dir}"
            actual = hashlib.sha256(fpath.read_bytes()).hexdigest()
            assert actual == doc_hash, (
                f"Hash mismatch for {fname} in {target_dir}: expected {doc_hash}, got {actual}"
            )
