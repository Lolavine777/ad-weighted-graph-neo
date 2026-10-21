"""End-to-end contract checks for the synthetic parser semantics demo."""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.check_contract import canonical_edge_id, provenance_reference, validate_graph
from src.data.manifest import load_manifest, verify_manifest
from src.parser import ErrorPolicy, cli
from src.parser.serialization import deserialize_graph

ROOT = Path(__file__).resolve().parents[1]
SAMPLES = ROOT / "data" / "samples"
MANIFESTS = SAMPLES / "manifests"
TIME_POLICY = SAMPLES / "parser-demo" / "time-policy.json"
RICH_RAW = SAMPLES / "parser-demo-rich-input"
ERROR_RAW = SAMPLES / "parser-demo-error-input"
RICH_ID = "sha256:1f76e5bdeffbc474fa55872fe328806faf35a23f29525d8adfeecc1f6484a5d4"
ERROR_ID = "sha256:b7ac113cf44525d3c638eb8a29dc219257a142a8d2c0debb4764d580c7a9183c"
CREATED_AT = "2026-09-25T00:00:00Z"
USER_A = "S-1-5-21-4100-4200-4300-1101"
USER_B = "S-1-5-21-4100-4200-4300-1102"
HELPDESK = "S-1-5-21-4100-4200-4300-2101"
OPERATORS = "S-1-5-21-4100-4200-4300-2102"
HOST = "S-1-5-21-4100-4200-4300-3101"
SCOPED_ADMIN = "host:a1b2c3d4-1111-4222-8333-abcdef012345:S-1-5-32-544"


@pytest.fixture(autouse=True)
def fixed_code_version(monkeypatch):
    monkeypatch.setattr(cli, "resolve_code_version", lambda repo_root=cli.ROOT: "a" * 40)


def _args(snapshot_id: str, raw_dir: Path, output: Path, *, policy: str = "fail_fast") -> list[str]:
    return [
        "--snapshot-id",
        snapshot_id,
        "--raw-dir",
        str(raw_dir),
        "--manifest-dir",
        str(MANIFESTS),
        "--time-policy",
        str(TIME_POLICY),
        "--created-at",
        CREATED_AT,
        "--output",
        str(output),
        "--error-policy",
        policy,
    ]


def _edge(graph: dict, source: str, target: str, kind: str) -> dict:
    matches = [
        edge
        for edge in graph["edges"]
        if (edge["source"], edge["target"], edge["kind"]) == (source, target, kind)
    ]
    assert len(matches) == 1
    assert matches[0]["id"] == canonical_edge_id(source, target, kind)
    return matches[0]


def test_demo_manifests_bind_exact_synthetic_inputs():
    for name, raw_dir, snapshot_id in (
        ("rich", RICH_RAW, RICH_ID),
        ("error", ERROR_RAW, ERROR_ID),
    ):
        manifest = load_manifest(MANIFESTS / f"parser-demo-{name}-v1.json")
        assert manifest["snapshot_id"] == snapshot_id
        assert manifest["collected_at"] is None
        assert manifest["collector"] == {"name": "sharphound", "version": "synthetic-v3"}
        assert verify_manifest(raw_dir, manifest) == []


def test_rich_demo_exports_reconciled_graph_and_unknown_rdp(tmp_path):
    output = tmp_path / "rich.json"
    assert cli.main(_args(RICH_ID, RICH_RAW, output)) == 0
    payload = output.read_text(encoding="utf-8")
    graph = deserialize_graph(payload)
    validate_graph(graph, cli.load_contract())

    assert graph["metadata"]["snapshot_id"] == RICH_ID
    assert graph["metadata"]["created_at"] == CREATED_AT
    assert {node["id"] for node in graph["nodes"]} == {
        USER_A,
        USER_B,
        HELPDESK,
        OPERATORS,
        HOST,
        SCOPED_ADMIN,
    }
    assert len(graph["nodes"]) == 6  # The two Helpdesk observations reconcile.
    assert {(edge["source"], edge["target"], edge["kind"]) for edge in graph["edges"]} == {
        (USER_A, HELPDESK, "MemberOf"),
        (USER_B, HELPDESK, "MemberOf"),
        (HELPDESK, OPERATORS, "MemberOf"),
        (OPERATORS, HOST, "AdminTo"),
        (HELPDESK, HOST, "AdminTo"),
        (USER_A, HOST, "AdminTo"),
        (USER_B, HOST, "AdminTo"),
        (USER_A, USER_B, "GenericAll"),
        (USER_A, USER_B, "ForceChangePassword"),
        (HOST, USER_B, "HasSession"),
    }
    assert len({edge["id"] for edge in graph["edges"]}) == len(graph["edges"])

    repeated = _edge(graph, USER_A, HELPDESK, "MemberOf")
    assert {item["raw_file"].split("/")[-1] for item in repeated["provenance"]} == {
        "groups.json",
        "groups-repeat.json",
    }
    assert len(repeated["provenance"]) == 2
    added = _edge(graph, USER_B, HELPDESK, "MemberOf")
    assert [item["raw_file"].split("/")[-1] for item in added["provenance"]] == [
        "groups-repeat.json"
    ]

    derived = _edge(graph, USER_A, HOST, "AdminTo")
    assert derived["derivation"]["kind"] == "nested_membership"
    assert derived["derivation"]["version"] == "1.1.0"
    steps = derived["derivation"]["paths"][0]["steps"]
    actual_steps = [
        (step["order"], step["operation"], step["source"], step["target"]) for step in steps
    ]
    assert actual_steps == [
        (0, "effective_membership", USER_A, HELPDESK),
        (1, "effective_membership", HELPDESK, OPERATORS),
        (2, "host_local_membership", OPERATORS, HOST),
    ]
    references = {provenance_reference(item) for item in derived["provenance"]}
    assert all(step["evidence_refs"] and set(step["evidence_refs"]) <= references for step in steps)
    assert len(steps[0]["evidence_refs"]) == 2
    assert {item["raw_file"].split("/")[-1] for item in derived["provenance"]} == {
        "groups.json",
        "groups-repeat.json",
        "computers.json",
    }

    assert len(graph["assessments"]) == 1
    assert {
        key: graph["assessments"][0][key]
        for key in ("kind", "status", "subject", "target", "reason")
    } == {
        "kind": "CanRDP",
        "status": "unknown",
        "subject": USER_A,
        "target": HOST,
        "reason": "required UserRights evidence is incomplete",
    }
    assert {item["attribute"] for item in graph["assessments"][0]["provenance"]} == {
        "RemoteDesktopUsers[]",
        "UserRights",
    }
    provenance = [item for edge in graph["edges"] for item in edge["provenance"]]
    assert all(item["timestamp_status"] == "assumed" for item in provenance)
    assert all(item["timestamp"] == "2026-09-24T00:00:00Z" for item in provenance)
    assert not any(edge["kind"] == "CanRDP" for edge in graph["edges"])


def test_rich_demo_is_stable_when_raw_records_are_reordered(tmp_path, monkeypatch):
    first = tmp_path / "first.json"
    second = tmp_path / "second.json"
    assert cli.main(_args(RICH_ID, RICH_RAW, first)) == 0
    original_loader = cli.ManifestRawDataLoader

    class ReversedLoader(original_loader):
        def load(self, source, *, error_policy=ErrorPolicy.FAIL_FAST):
            return iter(reversed(list(super().load(source, error_policy=error_policy))))

    monkeypatch.setattr(cli, "ManifestRawDataLoader", ReversedLoader)
    assert cli.main(_args(RICH_ID, RICH_RAW, second)) == 0
    assert first.read_bytes() == second.read_bytes()


@pytest.mark.parametrize(
    ("policy", "expected_exit", "warning_count"),
    [("fail_fast", 1, 0), ("log_warning", 0, 1), ("skip_record", 0, 0)],
)
def test_malformed_record_obeys_error_policy(
    tmp_path, caplog, policy, expected_exit, warning_count
):
    output = tmp_path / f"{policy}.json"
    with caplog.at_level("WARNING"):
        result = cli.main(_args(ERROR_ID, ERROR_RAW, output, policy=policy))
    assert result == expected_exit
    assert output.exists() is (expected_exit == 0)
    if expected_exit == 0:
        graph = deserialize_graph(output.read_text(encoding="utf-8"))
        assert {node["id"] for node in graph["nodes"]} == {USER_A, USER_B}
        assert graph["edges"] == graph["assessments"] == []
    warnings = [record for record in caplog.records if record.levelname == "WARNING"]
    assert len(warnings) == warning_count
    if warning_count:
        assert "normalize: missing stable object SID or GUID" in warnings[0].getMessage()
    if expected_exit:
        assert "normalize: missing stable object SID or GUID" in caplog.text
