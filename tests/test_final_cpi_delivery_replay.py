"""Acceptance must verify retained artifacts from actual native execution."""

import shutil

import pytest

from scripts.research import final_cpi_delivery_replay as replay
from scripts.research.issue250_public_probe import save


@pytest.fixture(scope="module")
def native_checkpoint(tmp_path_factory):
    raw_dir = replay.ROOT / "data/raw/SEAMLESS"
    if not raw_dir.is_dir():
        pytest.skip("Manifest-verified raw required")
    raw_graph, frozen = replay.load_inputs(raw_dir)
    case = next(
        c
        for c in replay.read(replay.COHORTS["supplementary"])["queries"]
        if c["id"] == "winrm-command"
    )
    root = tmp_path_factory.mktemp("native-delivery")
    cohort = {"queries": [case]}
    save(root / "cohort.json", cohort)
    execution = replay.execution_identity()
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(replay, "LOCAL", root / "checkpoint")
        replay.checkpoint("supplementary", case, cohort, raw_graph, frozen, raw_dir, execution)
    return root, raw_graph, frozen, raw_dir, execution


def aggregate_copy(native_checkpoint, tmp_path, monkeypatch, corruption=None):
    root, raw_graph, frozen, raw_dir, execution = native_checkpoint
    local = tmp_path / "checkpoint"
    shutil.copytree(root / "checkpoint", local)
    monkeypatch.setattr(replay, "LOCAL", local)
    monkeypatch.setattr(replay, "REPORT", tmp_path / "report.json")
    monkeypatch.setattr(replay, "COHORTS", {"supplementary": root / "cohort.json"})
    name = "supplementary.winrm-command"
    if corruption in ("before-query", "after-query"):
        phase = corruption.split("-")[0]
        path = local / f"{name}.{phase}.query.json"
        query = replay.read(path)
        query["rating_resolution"]["scope"]["policy_id"] = "synthetic-corruption"
        save(path, query)
    elif corruption == "missing-run2":
        (local / f"{name}.after.run2.normalized.json").unlink()
    elif corruption in ("changed-run2", "boolean-run2-effort"):
        path = local / f"{name}.after.run2.normalized.json"
        output = replay.read(path)
        if corruption == "changed-run2":
            output["program_identities"] = []
        else:
            output["ranking_result"]["eligible_candidates"]["generated_0001"]["effort"] = True
        save(path, output)
    elif corruption == "boolean-exit-codes":
        path = local / f"{name}.verified.json"
        row = replay.read(path)
        row["public_verification"]["two_CLI_exit_codes"] = [False, False]
        save(path, row)
    elif corruption == "wrong-executable-revision":
        path = local / f"{name}.verified.json"
        row = replay.read(path)
        row["scope"]["executable_checkout"]["revision"] = "0" * 40
        save(path, row)
    replay.aggregate(raw_graph, frozen, raw_dir, execution)


def test_native_delivery_aggregate_accepts_verified_artifacts(
    native_checkpoint, tmp_path, monkeypatch
):
    aggregate_copy(native_checkpoint, tmp_path, monkeypatch)
    counts = replay.read(replay.REPORT)["groups"]["supplementary"]["totals"]["supported"]
    assert counts["before"]["fully_rated"] == 1
    assert counts["after"]["fully_rated"] == counts["after"]["valid_generated"] == 1


@pytest.mark.parametrize(
    "corruption",
    [
        "before-query",
        "after-query",
        "missing-run2",
        "changed-run2",
        "boolean-run2-effort",
        "boolean-exit-codes",
        "wrong-executable-revision",
    ],
)
def test_native_delivery_aggregate_refuses_corrupted_artifacts(
    native_checkpoint, tmp_path, monkeypatch, corruption
):
    with pytest.raises((ValueError, FileNotFoundError)):
        aggregate_copy(native_checkpoint, tmp_path, monkeypatch, corruption)
    assert not replay.REPORT.exists()
