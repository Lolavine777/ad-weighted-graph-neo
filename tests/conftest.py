"""Shared pytest configuration."""

import pytest

# Release and acceptance replays that dominate suite time. They are marked here by file name
# instead of inline because the test files' bytes are pinned by published acceptance manifests.
SLOW_FILES = frozenset(
    {
        "test_final_cpi_release.py",
        "test_final_cpi_wave2_replay.py",
        "test_source_a_rating_pack.py",
        "test_week4_acceptance_review_regressions.py",
    }
)


def pytest_collection_modifyitems(items):
    for item in items:
        if item.path.name in SLOW_FILES:
            item.add_marker(pytest.mark.slow)
