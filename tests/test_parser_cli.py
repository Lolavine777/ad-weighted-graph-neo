"""Acceptance coverage for the official parser CLI and graph export boundary."""

from __future__ import annotations

import copy
import json
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import pytest

from src.parser import ErrorPolicy, cli
from src.parser.serialization import deserialize_graph

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "samples" / "parser-cli-input"
MANIFESTS = ROOT / "data" / "samples" / "manifests"
SNAPSHOT_ID = "sha256:118fc26fa6689afd0d51547251705f5dbb66e5d3a51e1e55c9f307e758975a90"
CODE_VERSION = "a" * 40
CREATED_AT = "2026-09-24T00:00:00Z"
TIME_POLICY = ROOT / "tests" / "fixtures" / "parser-cli-time-policy.json"
_resolve_code_version = cli.resolve_code_version


@pytest.fixture(autouse=True)
def fixed_code_version(monkeypatch):
    monkeypatch.setattr(cli, "resolve_code_version", lambda repo_root=cli.ROOT: CODE_VERSION)


def _args(output: Path, *, profile: str = "unit", created_at: str = CREATED_AT) -> list[str]:
    return [
        "--snapshot-id",
        SNAPSHOT_ID,
        "--raw-dir",
        str(RAW),
        "--manifest-dir",
        str(MANIFESTS),
        "--profile",
        profile,
        "--output",
        str(output),
        "--created-at",
        created_at,
        "--time-policy",
        str(TIME_POLICY),
    ]


def _build(output: Path, **kwargs) -> dict:
    args = _args(output, **kwargs)
    assert cli.main(args) == 0
    return json.loads(output.read_text(encoding="utf-8"))


def test_help_and_required_arguments(capsys):
    with pytest.raises(SystemExit) as help_exit:
        cli.main(["--help"])
    assert help_exit.value.code == 0
    assert "--snapshot-id" in capsys.readouterr().out

    with pytest.raises(SystemExit) as missing_exit:
        cli.main([])
    assert missing_exit.value.code == 2


def test_cli_defaults_and_invalid_arguments(tmp_path, capsys):
    parsed = cli._parser().parse_args(["--snapshot-id", SNAPSHOT_ID])
    assert parsed.profile == "unit"
    assert parsed.raw_dir is None
    assert parsed.manifest_dir == cli.ROOT / "data" / "samples" / "manifests"
    assert parsed.output is None
    assert parsed.error_policy == "fail_fast"
    assert parsed.summary is False
    assert parsed.created_at is None
    assert parsed.time_policy is None

    with pytest.raises(SystemExit) as invalid_policy:
        cli._parser().parse_args(["--snapshot-id", SNAPSHOT_ID, "--error-policy", "ignore"])
    assert invalid_policy.value.code == 2
    assert cli.main(["--snapshot-id", "bad", "--manifest-dir", str(MANIFESTS)]) == 1
    assert "snapshot ID must be sha256:" in capsys.readouterr().err
    assert cli.main(["--snapshot-id", "sha256:" + "f" * 64, "--manifest-dir", str(MANIFESTS)]) == 1
    assert "snapshot is not present in manifest directory" in capsys.readouterr().err


def test_default_unit_and_explicit_profile_created_at_and_output(tmp_path):
    unit = _build(tmp_path / "unit.json")
    assert unit["metadata"]["weight_profile"] == "unit"
    assert {edge["weight"] for edge in unit["edges"]} == {1.0}

    illustrative = _build(
        tmp_path / "explicit.json", profile="illustrative", created_at="2026-09-23T12:34:56Z"
    )
    assert illustrative["metadata"]["weight_profile"] == "illustrative"
    assert illustrative["metadata"]["created_at"] == "2026-09-23T12:34:56Z"
    assert (tmp_path / "explicit.json").is_file()
    contract = cli.load_contract()
    assert (
        contract["profiles"][illustrative["metadata"]["weight_profile"]]["production_ready"]
        is False
    )


def test_omitted_output_uses_safe_deterministic_processed_path(tmp_path, monkeypatch):
    repository = tmp_path / "repo"
    shutil.copytree(ROOT / "configs", repository / "configs")
    monkeypatch.setattr(cli, "ROOT", repository)
    args = [
        "--snapshot-id",
        SNAPSHOT_ID,
        "--raw-dir",
        str(RAW),
        "--manifest-dir",
        str(MANIFESTS),
        "--time-policy",
        str(TIME_POLICY),
    ]
    before = datetime.now(UTC).replace(microsecond=0)
    assert cli.main(args) == 0
    after = datetime.now(UTC).replace(microsecond=0)
    output = (
        repository
        / "data"
        / "processed"
        / "graphs"
        / f"graph-unit-{SNAPSHOT_ID.removeprefix('sha256:')}.json"
    )
    assert output.is_file()
    assert ":" not in output.name
    created_at = datetime.strptime(
        json.loads(output.read_text(encoding="utf-8"))["metadata"]["created_at"],
        "%Y-%m-%dT%H:%M:%SZ",
    ).replace(tzinfo=UTC)
    assert before <= created_at <= after


def test_profile_validation_fails_closed_for_unknown_and_missing_weights(tmp_path, caplog):
    unknown = _args(tmp_path / "unknown.json", profile="maut_v2")
    assert cli.main(unknown) == 1
    assert "unknown weight profile" in caplog.text

    contract = cli.load_contract()
    contract["profiles"]["unit"]["weights"].pop("HasSession")
    with pytest.raises(ValueError, match="missing=.*HasSession"):
        cli.resolve_profile(contract, "unit")

    contract = cli.load_contract()
    contract["profiles"]["unit"]["weights"]["HasSession"] = 0.5
    with pytest.raises(ValueError, match="invalid weight"):
        cli.resolve_profile(contract, "unit")


def test_unknown_collection_time_requires_explicit_policy(tmp_path, caplog):
    output = tmp_path / "without-time-policy.json"
    args = _args(output)
    args.remove("--time-policy")
    args.remove(str(TIME_POLICY))

    assert cli.main(args) == 1
    assert "missing collection timestamp" in caplog.text
    assert not output.exists()


def test_time_policy_is_separate_from_export_created_at(tmp_path):
    graph = _build(tmp_path / "policy.json", created_at="2026-09-25T12:00:00Z")
    assert graph["metadata"]["created_at"] == "2026-09-25T12:00:00Z"
    edge = next(edge for edge in graph["edges"] if edge["kind"] == "AdminTo")
    provenance = edge["provenance"]
    assert provenance
    assert all(item["timestamp"] == "2026-09-24T00:00:00Z" for item in provenance)
    assert all(item["timestamp_status"] == "assumed" for item in provenance)
    assert all(
        "intentionally assumed collection time" in item["time_provenance_reason"]
        for item in provenance
    )


def test_time_policy_rejects_duplicate_or_unknown_fields(tmp_path):
    duplicate = tmp_path / "duplicate.json"
    duplicate.write_text(
        '{"timestamp":"2026-09-24T00:00:00Z","timestamp":"2026-09-25T00:00:00Z",'
        '"status":"assumed"}',
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="unable to load collection-time policy"):
        cli.load_time_policy(duplicate)

    unknown = tmp_path / "unknown.json"
    unknown.write_text(
        json.dumps({"timestamp": CREATED_AT, "status": "assumed", "created_at": CREATED_AT}),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="only timestamp, status, and reason"):
        cli.load_time_policy(unknown)


@pytest.mark.parametrize("profile", ["unit", "illustrative", "maut_v1"])
def test_every_traversable_edge_uses_exact_selected_contract_weight(tmp_path, profile):
    graph = _build(tmp_path / f"{profile}.json", profile=profile)
    expected = cli.load_contract()["profiles"][profile]["weights"]
    assert graph["edges"]
    assert all(edge["weight"] == expected[edge["kind"]] for edge in graph["edges"])


def test_metadata_uses_contract_1_2_without_legacy_fields(tmp_path):
    graph = _build(tmp_path / "graph.json")
    metadata = graph["metadata"]
    assert metadata == {
        "contract_version": "1.3.0",
        "weight_profile": "unit",
        "snapshot_id": SNAPSHOT_ID,
        "created_at": CREATED_AT,
        "code_version": CODE_VERSION,
    }
    assert "profile" not in graph
    assert "collector" not in metadata


def test_error_policy_is_passed_to_existing_loader_and_builder(tmp_path, monkeypatch):
    seen_loader = []
    seen_builder = []
    seen_normalizer = []
    real_loader = cli.ManifestRawDataLoader
    real_builder = cli.DirectGraphBuilder
    real_normalizer = cli.IdentityNormalizer

    class LoaderSpy(real_loader):
        def __init__(self, manifest, *, time_policy=None, **kwargs):
            assert time_policy is not None
            super().__init__(manifest, time_policy=time_policy, **kwargs)

        def load(self, source, *, error_policy=ErrorPolicy.FAIL_FAST):
            seen_loader.append(error_policy)
            return super().load(source, error_policy=error_policy)

    class BuilderSpy(real_builder):
        def build(self, records, *, error_policy=ErrorPolicy.FAIL_FAST):
            seen_builder.append(error_policy)
            return super().build(records, error_policy=error_policy)

    class NormalizerSpy(real_normalizer):
        def normalize_records(self, records, *, error_policy=ErrorPolicy.FAIL_FAST):
            seen_normalizer.append(error_policy)
            return super().normalize_records(records, error_policy=error_policy)

    monkeypatch.setattr(cli, "ManifestRawDataLoader", LoaderSpy)
    monkeypatch.setattr(cli, "DirectGraphBuilder", BuilderSpy)
    monkeypatch.setattr(cli, "IdentityNormalizer", NormalizerSpy)
    for policy in ErrorPolicy:
        output = tmp_path / f"{policy.value}.json"
        assert cli.main([*_args(output), "--error-policy", policy.value]) == 0
    assert seen_loader == list(ErrorPolicy)
    assert seen_builder == list(ErrorPolicy)
    assert seen_normalizer == list(ErrorPolicy)


def _snapshot_with_invalid_identity(tmp_path):
    raw_dir = tmp_path / "raw"
    shutil.copytree(RAW, raw_dir)
    users_path = raw_dir / "users.json"
    envelope = json.loads(users_path.read_text(encoding="utf-8"))
    envelope["users"].append({"Properties": {"name": "invalid-user", "domain": "EXAMPLE.TEST"}})
    users_path.write_text(json.dumps(envelope, separators=(",", ":")), encoding="utf-8")

    manifest_dir = tmp_path / "manifests"
    manifest_dir.mkdir()
    manifest = cli.snapshot_manifest.generate_manifest(
        raw_dir,
        dataset_id="normalizer-policy-test",
        collector_name="sharphound",
        collector_version="synthetic-v3",
        collected_at=None,
    )
    manifest_path = manifest_dir / "snapshot.json"
    cli.snapshot_manifest.write_manifest(manifest, manifest_path, source=raw_dir)
    return raw_dir, manifest_dir, manifest["snapshot_id"]


@pytest.mark.parametrize(
    ("policy", "success", "warning_count"),
    [("fail_fast", False, 0), ("skip_record", True, 0), ("log_warning", True, 1)],
)
def test_error_policy_handles_normalization_record_failures(
    tmp_path, caplog, capsys, policy, success, warning_count
):
    raw_dir, manifest_dir, snapshot_id = _snapshot_with_invalid_identity(tmp_path)
    output = tmp_path / f"{policy}.json"
    args = [
        "--snapshot-id",
        snapshot_id,
        "--raw-dir",
        str(raw_dir),
        "--manifest-dir",
        str(manifest_dir),
        "--output",
        str(output),
        "--created-at",
        CREATED_AT,
        "--time-policy",
        str(TIME_POLICY),
        "--error-policy",
        policy,
        "--summary",
    ]

    with caplog.at_level("WARNING"):
        result = cli.main(args)
    assert (result == 0) is success
    assert output.exists() is success
    if success:
        graph = json.loads(output.read_text(encoding="utf-8"))
        assert {node["id"] for node in graph["nodes"]} == {
            "S-1-5-21-1000-2000-3000-3101",
            "S-1-5-21-1000-2000-3000-2101",
            "S-1-5-21-1000-2000-3000-1101",
        }
        if warning_count:
            assert "normalize: missing stable object SID or GUID" in caplog.text
            assert "warnings: 1" in capsys.readouterr().out
        else:
            assert "invalid-user" not in caplog.text


def test_fixed_inputs_are_byte_reproducible(tmp_path):
    first = tmp_path / "first.json"
    second = tmp_path / "second.json"
    _build(first)
    _build(second)
    assert first.read_bytes() == second.read_bytes()


def test_reordered_raw_records_produce_identical_canonical_json(tmp_path, monkeypatch):
    contract = cli.load_contract()
    manifest_path = MANIFESTS / "parser-cli-seamless-v1.json"
    first_graph = cli.build_graph(
        raw_dir=RAW,
        manifest_path=manifest_path,
        snapshot_id=SNAPSHOT_ID,
        profile="unit",
        contract=contract,
        created_at=CREATED_AT,
        code_version=CODE_VERSION,
        error_policy=ErrorPolicy.FAIL_FAST,
        time_policy=cli.load_time_policy(TIME_POLICY),
    )
    original_loader = cli.ManifestRawDataLoader

    class ReversedLoader(original_loader):
        def load(self, source, *, error_policy=ErrorPolicy.FAIL_FAST):
            return iter(reversed(list(super().load(source, error_policy=error_policy))))

    monkeypatch.setattr(cli, "ManifestRawDataLoader", ReversedLoader)
    second_graph = cli.build_graph(
        raw_dir=RAW,
        manifest_path=manifest_path,
        snapshot_id=SNAPSHOT_ID,
        profile="unit",
        contract=contract,
        created_at=CREATED_AT,
        code_version=CODE_VERSION,
        error_policy=ErrorPolicy.FAIL_FAST,
        time_policy=cli.load_time_policy(TIME_POLICY),
    )
    assert cli.serialize_graph(first_graph, contract=contract) == cli.serialize_graph(
        second_graph, contract=contract
    )


def test_runtime_created_at_changes_metadata_only(tmp_path):
    first = _build(tmp_path / "first.json", created_at="2026-09-22T00:00:00Z")
    second = _build(tmp_path / "second.json", created_at="2026-09-24T00:00:00Z")
    for graph in (first, second):
        graph["metadata"].pop("created_at")
    assert first == second


def test_canonicalization_orders_top_level_collections():
    contract = cli.load_contract()
    canonical = {
        "metadata": {
            "contract_version": "1.3.0",
            "weight_profile": "unit",
            "snapshot_id": SNAPSHOT_ID,
            "created_at": CREATED_AT,
            "code_version": CODE_VERSION,
        },
        "nodes": [{"id": "z"}, {"id": "a"}],
        "edges": [{"id": "z"}, {"id": "a"}],
        "assessments": [{"id": "z"}, {"id": "a"}],
    }
    cli.canonicalize_graph(canonical)
    assert [item["id"] for item in canonical["nodes"]] == ["a", "z"]
    assert [item["id"] for item in canonical["edges"]] == ["a", "z"]
    assert [item["id"] for item in canonical["assessments"]] == ["a", "z"]
    assert contract["version"] == "1.3.0"


def test_atomic_write_success_and_failure_cleanup(tmp_path, monkeypatch):
    destination = tmp_path / "nested" / "graph.json"
    cli.atomic_write(destination, '{"ok":true}')
    assert destination.read_text(encoding="utf-8") == '{"ok":true}'
    assert list(destination.parent.iterdir()) == [destination]

    existing = destination.read_bytes()

    def fail_replace(source, target):
        raise OSError("injected replace failure")

    monkeypatch.setattr(cli.os, "replace", fail_replace)
    with pytest.raises(OSError, match="injected"):
        cli.atomic_write(destination, '{"partial":false}')
    assert destination.read_bytes() == existing
    assert list(destination.parent.iterdir()) == [destination]

    new_destination = tmp_path / "new.json"
    with pytest.raises(OSError, match="injected"):
        cli.atomic_write(new_destination, "payload")
    assert not new_destination.exists()
    assert list(tmp_path.iterdir()) == [destination.parent]


def test_pipeline_failure_does_not_touch_destination(tmp_path, monkeypatch):
    output = tmp_path / "preserved.json"
    output.write_bytes(b"previous graph")

    def fail_build(**kwargs):
        raise RuntimeError("injected pipeline failure")

    monkeypatch.setattr(cli, "build_graph", fail_build)
    assert cli.main(_args(output)) == 1
    assert output.read_bytes() == b"previous graph"
    assert list(tmp_path.iterdir()) == [output]


def test_contract_validation_failure_does_not_touch_destination(tmp_path, monkeypatch):
    output = tmp_path / "preserved.json"
    output.write_bytes(b"previous graph")
    monkeypatch.setattr(cli, "build_graph", lambda **kwargs: {"invalid": True})
    assert cli.main(_args(output)) == 1
    assert output.read_bytes() == b"previous graph"
    assert list(tmp_path.iterdir()) == [output]


def test_summary_reports_counts_and_does_not_change_output_bytes(tmp_path, capsys):
    without = tmp_path / "without.json"
    with_summary = tmp_path / "with.json"
    _build(without)
    assert cli.main([*_args(with_summary), "--summary"]) == 0
    summary = capsys.readouterr().out
    graph = json.loads(with_summary.read_text(encoding="utf-8"))
    assert without.read_bytes() == with_summary.read_bytes()
    assert f"Nodes: {len(graph['nodes'])}" in summary
    assert f"Edges: {len(graph['edges'])}" in summary
    assert f"Snapshot ID: {SNAPSHOT_ID}" in summary
    assert "Assessments:" in summary and "Weight profile: unit" in summary
    assert "Skipped records: unavailable; warnings: 0; errors: 0" in summary
    assert "Output:" in summary


def test_manifest_backed_seamless_path_preserves_inference_lineage_and_assessments(tmp_path):
    graph = _build(tmp_path / "seamless.json")
    host = "S-1-5-21-1000-2000-3000-3101"
    user = "S-1-5-21-1000-2000-3000-1101"
    derived = next(
        edge
        for edge in graph["edges"]
        if edge["source"] == user and edge["target"] == host and edge["kind"] == "AdminTo"
    )
    assert derived["derivation"]["paths"]
    assert derived["provenance"]
    assert graph["assessments"]
    assert deserialize_graph(json.dumps(graph)) == graph


def test_summary_does_not_mutate_graph_data(tmp_path):
    graph = cli.build_graph(
        raw_dir=RAW,
        manifest_path=MANIFESTS / "parser-cli-seamless-v1.json",
        snapshot_id=SNAPSHOT_ID,
        profile="unit",
        contract=cli.load_contract(),
        created_at=CREATED_AT,
        code_version=CODE_VERSION,
        error_policy=ErrorPolicy.FAIL_FAST,
        time_policy=cli.load_time_policy(TIME_POLICY),
    )
    before = copy.deepcopy(graph)
    cli.render_summary(graph, tmp_path / "graph.json", snapshot_id=SNAPSHOT_ID, profile="unit")
    assert graph == before


def test_code_version_fails_closed_when_git_is_unavailable(monkeypatch, tmp_path):
    def fail(*args, **kwargs):
        raise FileNotFoundError("git missing")

    monkeypatch.setattr(cli.subprocess, "run", fail)
    with pytest.raises(RuntimeError, match="unable to resolve source Git commit"):
        _resolve_code_version(tmp_path)


def test_code_version_requires_clean_parser_and_contract_sources(tmp_path):
    repository = tmp_path / "repo"
    parser_dir = repository / "src" / "parser"
    config_dir = repository / "configs"
    parser_dir.mkdir(parents=True)
    config_dir.mkdir()
    parser_file = parser_dir / "example.py"
    config_file = config_dir / "contract.yml"
    parser_file.write_text("VALUE = 1\n", encoding="utf-8")
    config_file.write_text("version: test\n", encoding="utf-8")

    def git(*args):
        return subprocess.run(
            ["git", *args],
            cwd=repository,
            capture_output=True,
            check=True,
            text=True,
        )

    git("init")
    git("config", "user.name", "CLI test")
    git("config", "user.email", "cli-test@example.invalid")
    git("add", "src/parser/example.py", "configs/contract.yml")
    git("commit", "-m", "test fixture")
    committed_version = git("rev-parse", "HEAD").stdout.strip()
    assert _resolve_code_version(repository) == committed_version

    parser_file.write_text("VALUE = 2\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="uncommitted changes"):
        _resolve_code_version(repository)

    parser_file.write_text("VALUE = 1\n", encoding="utf-8")
    (parser_dir / "untracked.py").write_text("VALUE = 3\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="uncommitted changes"):
        _resolve_code_version(repository)


def test_created_at_must_be_valid_utc(tmp_path):
    assert cli.main(_args(tmp_path / "bad-time.json", created_at="2026-09-24T01:00:00+01:00")) == 1
