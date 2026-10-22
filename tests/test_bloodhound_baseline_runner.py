"""Safety and raw-input contracts for the baseline runner."""

import json
from unittest.mock import MagicMock

import pytest

from scripts import run_bloodhound_baseline as runner


def test_seamless_uses_pinned_manifest_and_raw_files():
    if not (runner.ROOT / "data/raw/SEAMLESS").exists():
        pytest.skip("raw SEAMLESS is an optional local dataset")
    files = runner.resolve_snapshot_files("seamless")
    assert len(files) == 6
    assert all(path.parent == runner.ROOT / "data/raw/SEAMLESS" for path in files)
    assert runner.verify_snapshot_integrity("seamless", files) == (
        "sha256:e0601d763eeea285d268ec9e468d321c50c9d7faba53c8e7442a2fcc4159c812"
    )


def test_seamless_requires_manifest(monkeypatch, tmp_path):
    config = dict(runner.SNAPSHOTS.get("seamless", {}), manifest_path=tmp_path / "missing")
    monkeypatch.setitem(runner.SNAPSHOTS, "seamless", config)
    with pytest.raises(runner.ManifestError, match="manifest"):
        runner.verify_snapshot_integrity("seamless", [])


@pytest.mark.parametrize("reset_volumes", [False, True])
def test_compose_selection_and_explicit_reset(monkeypatch, tmp_path, reset_volumes):
    commands = []
    monkeypatch.setattr(runner, "run_cmd", lambda cmd, **kw: commands.append(cmd) or "")
    compose = tmp_path / "compose.yml"
    runner.reset_environment(compose, "isolated", reset_volumes=reset_volumes)
    prefix = ["docker", "compose", "-f", str(compose), "-p", "isolated"]
    assert commands == ([prefix + ["down", "-v"]] if reset_volumes else []) + [
        prefix + ["up", "-d"]
    ]


def test_password_uses_selected_compose_service(monkeypatch, tmp_path):
    commands = []
    monkeypatch.setattr(
        runner,
        "run_cmd",
        lambda cmd, **kw: commands.append(cmd) or "Initial Password Set To: secret",
    )
    compose = tmp_path / "compose.yml"
    assert runner.get_admin_password(compose_file=compose, project_name="isolated") == "secret"
    assert commands == [
        ["docker", "compose", "-f", str(compose), "-p", "isolated", "logs", "bloodhound"]
    ]


def response(data):
    result = MagicMock()
    result.__enter__.return_value = result
    result.read.return_value = json.dumps({"data": data}).encode()
    result.status = 202
    return result


@pytest.mark.parametrize("job_status", [-1, 3, 4, 5, 8, None])
def test_failed_or_timed_out_ingest_never_extracts_metrics(monkeypatch, tmp_path, job_status):
    source = tmp_path / "users.json"
    source.write_text("{}")
    monkeypatch.setattr(runner, "resolve_snapshot_files", lambda name: [source])
    monkeypatch.setattr(runner, "verify_snapshot_integrity", lambda *args: "sha256:verified")
    monkeypatch.setattr(runner.time, "sleep", lambda _: None)
    responses = iter([response({"id": 7}), response({}), response({})])
    job = [] if job_status is None else [{"id": 7, "status": job_status}]
    monkeypatch.setattr(
        runner.urllib.request, "urlopen", lambda req: next(responses, response(job))
    )
    extract = MagicMock()
    monkeypatch.setattr(runner, "extract_baseline_metrics", extract)
    with pytest.raises(RuntimeError, match="(failed|partial|Timed out)"):
        runner.ingest_snapshot("seamless", {}, "token")
    extract.assert_not_called()


def test_cli_writes_failure_evidence_and_exits_nonzero(monkeypatch, tmp_path):
    output = tmp_path / "results.json"
    monkeypatch.setattr("sys.argv", ["baseline", "--snapshot", "seamless", "--output", str(output)])
    monkeypatch.setattr(runner, "resolve_snapshot_files", lambda name: [])
    monkeypatch.setattr(runner, "verify_snapshot_integrity", lambda *args: "sha256:verified")
    monkeypatch.setattr(runner, "reset_environment", lambda *args, **kwargs: None)
    monkeypatch.setattr(runner, "get_admin_password", lambda **kwargs: "secret")
    monkeypatch.setattr(runner, "login", lambda password: "token")
    monkeypatch.setattr(runner, "wait_for_bloodhound_ready", lambda token: None)

    monkeypatch.setattr(runner, "query_neo4j", lambda query: [{"total": 0}])

    def fail(*args):
        raise RuntimeError("Ingest job failed: 4")

    monkeypatch.setattr(runner, "ingest_snapshot", fail)
    with pytest.raises(SystemExit) as caught:
        runner.main()
    assert caught.value.code == 1
    assert json.loads(output.read_text())["seamless"] == {
        "status": "failed",
        "error": "Ingest job failed: 4",
    }


def test_all_requires_explicit_volume_reset(monkeypatch):
    monkeypatch.setattr("sys.argv", ["baseline", "--all"])
    reset = MagicMock(side_effect=AssertionError("lifecycle must not start"))
    monkeypatch.setattr(runner, "reset_environment", reset)
    with pytest.raises(SystemExit) as caught:
        runner.main()
    assert caught.value.code == 2
    reset.assert_not_called()


def test_cli_refuses_existing_graph_without_reset(monkeypatch, tmp_path):
    output = tmp_path / "results.json"
    monkeypatch.setattr("sys.argv", ["baseline", "--snapshot", "seamless", "--output", str(output)])
    monkeypatch.setattr(runner, "resolve_snapshot_files", lambda name: [])
    monkeypatch.setattr(runner, "verify_snapshot_integrity", lambda *args: "sha256:verified")
    monkeypatch.setattr(runner, "reset_environment", lambda *args, **kwargs: None)
    monkeypatch.setattr(runner, "get_admin_password", lambda **kwargs: "secret")
    monkeypatch.setattr(runner, "login", lambda password: "token")
    monkeypatch.setattr(runner, "wait_for_bloodhound_ready", lambda token: None)
    monkeypatch.setattr(runner, "query_neo4j", lambda query: [{"total": 1}])
    ingest = MagicMock(return_value={})
    monkeypatch.setattr(runner, "ingest_snapshot", ingest)
    with pytest.raises(SystemExit) as caught:
        runner.main()
    assert caught.value.code == 1
    assert "nonempty" in json.loads(output.read_text())["seamless"]["error"]
    ingest.assert_not_called()


def test_ingest_waits_through_ingesting_and_analyzing(monkeypatch, tmp_path):
    source = tmp_path / "users.json"
    source.write_text("{}")
    monkeypatch.setattr(runner, "resolve_snapshot_files", lambda name: [source])
    monkeypatch.setattr(runner, "verify_snapshot_integrity", lambda *args: "sha256:verified")
    monkeypatch.setattr(runner.time, "sleep", lambda _: None)
    responses = iter(
        [
            response({"id": 7}),
            response({}),
            response({}),
            response([{"id": 7, "status": 6}]),
            response([{"id": 7, "status": 7}]),
            response([{"id": 7, "status": 2, "total_files": 1, "failed_files": 0}]),
        ]
    )
    monkeypatch.setattr(runner.urllib.request, "urlopen", lambda req: next(responses))
    monkeypatch.setattr(runner, "extract_baseline_metrics", lambda *args: {"total_nodes": 1})
    assert runner.ingest_snapshot("seamless", {}, "token") == {"total_nodes": 1}


@pytest.mark.parametrize("terminal_status", [5, 8, None, 2])
def test_upload_error_body_survives_failure_evidence(monkeypatch, tmp_path, terminal_status):
    source = tmp_path / "users.json"
    source.write_text("{}")
    monkeypatch.setattr(runner, "resolve_snapshot_files", lambda name: [source])
    monkeypatch.setattr(runner, "verify_snapshot_integrity", lambda *args: "sha256:verified")
    monkeypatch.setattr(runner.time, "sleep", lambda _: None)
    error = runner.urllib.error.HTTPError("http://local", 400, "Bad Request", {}, None)
    error.read = MagicMock(return_value=b"unsupported collection version\xff")
    calls = 0

    def upload(req):
        nonlocal calls
        calls += 1
        if calls == 1:
            return response({"id": 7})
        if calls == 2:
            raise error
        if calls == 3:
            return response({})
        job = [] if terminal_status is None else [{"id": 7, "status": terminal_status}]
        return response(job)

    monkeypatch.setattr(runner.urllib.request, "urlopen", upload)
    extract = MagicMock()
    monkeypatch.setattr(runner, "extract_baseline_metrics", extract)
    with pytest.raises(RuntimeError, match="unsupported collection version") as caught:
        runner.ingest_snapshot("seamless", {}, "token")
    assert "400" in str(caught.value)
    assert "users.json" in str(caught.value)
    assert "\ufffd" in str(caught.value)
    error.read.assert_called_once_with(65536)
    extract.assert_not_called()


def test_complete_with_partial_failed_files_rejects_metrics(monkeypatch, tmp_path):
    source = tmp_path / "users.json"
    source.write_text("{}")
    monkeypatch.setattr(runner, "resolve_snapshot_files", lambda name: [source])
    monkeypatch.setattr(runner, "verify_snapshot_integrity", lambda *args: "sha256:verified")
    monkeypatch.setattr(runner.time, "sleep", lambda _: None)
    responses = iter(
        [
            response({"id": 7}),
            response({}),
            response({}),
            response([{"id": 7, "status": 2, "partial_failed_files": 1}]),
        ]
    )
    monkeypatch.setattr(runner.urllib.request, "urlopen", lambda req: next(responses))
    extract = MagicMock()
    monkeypatch.setattr(runner, "extract_baseline_metrics", extract)
    with pytest.raises(RuntimeError, match="failed files"):
        runner.ingest_snapshot("seamless", {}, "token")
    extract.assert_not_called()


def test_converted_verification_failure_prevents_upload(monkeypatch, tmp_path):
    from scripts import convert_seamless_ce

    def reject(*args):
        raise ValueError("converted snapshot hash mismatch")

    monkeypatch.setattr(convert_seamless_ce, "verify_install", reject)
    upload = MagicMock()
    monkeypatch.setattr(runner.urllib.request, "urlopen", upload)
    with pytest.raises(ValueError, match="hash mismatch"):
        runner.ingest_snapshot("seamless", {"converted_dir": tmp_path}, "token")
    upload.assert_not_called()


def test_converted_directory_only_applies_to_explicit_seamless(monkeypatch, tmp_path):
    monkeypatch.setattr("sys.argv", ["baseline", "--seamless-ce-dir", str(tmp_path)])
    reset = MagicMock()
    monkeypatch.setattr(runner, "reset_environment", reset)
    with pytest.raises(SystemExit) as caught:
        runner.main()
    assert caught.value.code == 2
    reset.assert_not_called()


def test_converted_metrics_use_artifact_identity_and_retain_source(monkeypatch, tmp_path):
    from scripts import convert_seamless_ce

    source = tmp_path / "users.json"
    source.write_text("{}")
    verified = {
        "files": [source],
        "snapshot_id": "sha256:converted",
        "source_snapshot_id": "sha256:raw",
        "converted_manifest_sha256": "converted",
    }
    monkeypatch.setattr(convert_seamless_ce, "verify_install", lambda *args: verified)
    monkeypatch.setattr(runner.time, "sleep", lambda _: None)
    responses = iter(
        [
            response({"id": 7}),
            response({}),
            response({}),
            response([{"id": 7, "status": 2, "total_files": 1, "failed_files": 0}]),
        ]
    )
    monkeypatch.setattr(runner.urllib.request, "urlopen", lambda req: next(responses))
    monkeypatch.setattr(
        runner,
        "extract_baseline_metrics",
        lambda name, cfg, statuses, identity: {
            "snapshot_id": identity,
            "total_nodes": 1,
        },
    )
    result = runner.ingest_snapshot("seamless", {"converted_dir": tmp_path}, "token")
    assert result["snapshot_id"] == "sha256:converted"
    assert result["source_snapshot_id"] == "sha256:raw"
    assert result["converted_manifest_sha256"] == "converted"


def test_all_runs_historical_ab_snapshots_without_raw_seamless(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "sys.argv",
        ["baseline", "--all", "--reset-volumes", "--output", str(tmp_path / "results.json")],
    )
    monkeypatch.setattr(runner, "resolve_snapshot_files", lambda name: [])
    monkeypatch.setattr(runner, "verify_snapshot_integrity", lambda *args: "sha256:verified")
    monkeypatch.setattr(runner, "reset_environment", lambda *args, **kwargs: None)
    monkeypatch.setattr(runner, "get_admin_password", lambda **kwargs: "secret")
    monkeypatch.setattr(runner, "login", lambda password: "token")
    monkeypatch.setattr(runner, "wait_for_bloodhound_ready", lambda token: None)
    monkeypatch.setattr(runner, "query_neo4j", lambda query: [{"total": 0}])
    targets = []
    monkeypatch.setattr(runner, "ingest_snapshot", lambda name, *args: targets.append(name) or {})
    runner.main()
    assert targets == ["a-sharphound", "a-python", "b-run-1", "b-run-2", "b-run-3", "dataset_b"]


def test_wraith_selects_only_pinned_export_and_verifies_bytes(tmp_path, monkeypatch):
    from src.data.manifest import generate_manifest

    raw = tmp_path / "ad_sampledata"
    raw.mkdir()
    for index in range(12):
        (raw / f"20240305111414_{index}.json").write_text("{}")
    (raw / "20240305110018_users.json").write_text("{}")
    manifest_path = tmp_path / "manifest.json"
    manifest = generate_manifest(
        raw, dataset_id="test", collector_name="test", collector_version=None, collected_at=None
    )
    manifest_path.write_text(json.dumps(manifest))
    config = dict(
        runner.SNAPSHOTS["wraith"],
        raw_root=raw,
        manifest_path=manifest_path,
        snapshot_id=manifest["snapshot_id"],
    )
    monkeypatch.setitem(runner.SNAPSHOTS, "wraith", config)
    files = runner.resolve_snapshot_files("wraith")
    assert len(files) == 12
    assert all(p.name.startswith("20240305111414_") for p in files)
    assert runner.verify_snapshot_integrity("wraith", files) == manifest["snapshot_id"]
    files[0].write_text("tampered")
    with pytest.raises(runner.ManifestError, match="(size|SHA-256) mismatch"):
        runner.verify_snapshot_integrity("wraith", files)
