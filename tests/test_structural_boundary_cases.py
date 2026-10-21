"""Structural boundary checks (Issue #47), with explicit builder and CLI scopes.

The original five cases start from preassigned NormalizedRecord attributes and
check builder preservation, not automatic boundary classification. The two CLI
cases exercise immutable synthetic raw inputs through the full parser pipeline.
Trust/SID filtering fields are not serialized into M1 Graph JSON.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from scripts.check_contract import validate_graph
from src.parser import (
    DirectGraphBuilder,
    NormalizedRecord,
    RawRecord,
)

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = "sha256:" + "c" * 64
LOCAL_DOMAIN = "SEVENKINGDOMS.LOCAL"
LOCAL_DOMAIN_SID = "S-1-5-21-1111111111-2222222222-3333333333"
EXTERNAL_DOMAIN = "WRAITH.CORP"
EXTERNAL_DOMAIN_SID = "S-1-5-21-4444444444-5555555555-6666666666"
CREATED = "2026-10-01T00:00:00Z"


def _raw_record(
    kind: str,
    data: dict,
    identifier: str,
    *,
    domain: str = LOCAL_DOMAIN,
    raw_file: str | None = None,
    time_provenance: str = "observed",
) -> RawRecord:
    provenance = {
        "raw_file": raw_file or f"snapshot:{SNAPSHOT[7:]}/{kind.lower()}.json",
        "collector": "synthetic/47",
        "timestamp": "2026-10-01T00:00:00Z",
        "snapshot_id": SNAPSHOT,
        "record_id": identifier,
        "record_locator": f"#/{kind.lower()}/{identifier}",
        "time_provenance": time_provenance,
    }
    payload = {
        "ObjectIdentifier": identifier,
        "Properties": {"name": identifier, "domain": domain},
        **data,
    }
    return RawRecord(kind=kind, data=payload, provenance=provenance)


def _builder() -> DirectGraphBuilder:
    return DirectGraphBuilder(
        metadata={
            "contract_version": "1.3.0",
            "weight_profile": "unit",
            "snapshot_id": SNAPSHOT,
            "created_at": CREATED,
            "code_version": "tests/structural-boundary",
        }
    )


def test_layer4_domain_record_with_trusts_builds_domain_node_without_spurious_edges():
    """Layer 4: Domain trusts with SidFilteringEnabled must not generate speculative edges."""
    domain_data = {
        "Trusts": [
            {
                "TargetDomainName": EXTERNAL_DOMAIN,
                "TargetDomainSid": EXTERNAL_DOMAIN_SID,
                "TrustDirection": "Bidirectional",
                "TrustType": "External",
                "SidFilteringEnabled": True,
            },
            {
                "TargetDomainName": "CHILD.SEVENKINGDOMS.LOCAL",
                "TargetDomainSid": "S-1-5-21-7777777777-8888888888-9999999999",
                "TrustDirection": "Bidirectional",
                "TrustType": "ParentChild",
                "SidFilteringEnabled": False,
            },
        ]
    }
    raw = _raw_record("Domain", domain_data, LOCAL_DOMAIN_SID, domain=LOCAL_DOMAIN)
    normalized = NormalizedRecord(
        id=LOCAL_DOMAIN_SID,
        kind="Domain",
        attributes={
            "id": LOCAL_DOMAIN_SID,
            "kind": "Domain",
            "label": LOCAL_DOMAIN,
            "domain": LOCAL_DOMAIN,
            "is_boundary": False,
        },
        raw=raw,
    )

    graph = _builder().build([normalized])
    contract = yaml.safe_load((ROOT / "configs" / "contract.yml").read_text(encoding="utf-8"))
    validate_graph(graph, contract)

    assert len(graph["nodes"]) == 1
    node = graph["nodes"][0]
    assert node["id"] == LOCAL_DOMAIN_SID
    assert node["kind"] == "Domain"
    assert node["label"] == LOCAL_DOMAIN
    assert node["is_boundary"] is False

    # Trusts are security topology attributes, not traversable attack edges in M1
    assert graph["edges"] == []
    assert graph["assessments"] == []


def test_layer4_boundary_domain_node_preserves_external_boundary_flag():
    """Builder only: preserve the external Domain flag already set by the test."""
    raw_external = _raw_record("Domain", {}, EXTERNAL_DOMAIN_SID, domain=EXTERNAL_DOMAIN)
    normalized_external = NormalizedRecord(
        id=EXTERNAL_DOMAIN_SID,
        kind="Domain",
        attributes={
            "id": EXTERNAL_DOMAIN_SID,
            "kind": "Domain",
            "label": EXTERNAL_DOMAIN,
            "domain": EXTERNAL_DOMAIN,
            "is_boundary": True,
        },
        raw=raw_external,
    )

    graph = _builder().build([normalized_external])
    assert len(graph["nodes"]) == 1
    node = graph["nodes"][0]
    assert node["id"] == EXTERNAL_DOMAIN_SID
    assert node["kind"] == "Domain"
    assert node["is_boundary"] is True
    assert node["domain"] == EXTERNAL_DOMAIN


def test_layer1_foreign_security_principal_boundary_group_membership():
    """Builder only: preserve the preassigned foreign principal boundary and membership."""
    local_group_sid = f"{LOCAL_DOMAIN_SID}-2101"
    foreign_user_sid = f"{EXTERNAL_DOMAIN_SID}-1105"

    group_raw = _raw_record(
        "Group",
        {"Members": [{"MemberId": foreign_user_sid, "MemberType": "User"}]},
        local_group_sid,
        domain=LOCAL_DOMAIN,
    )
    group_norm = NormalizedRecord(
        id=local_group_sid,
        kind="Group",
        attributes={
            "id": local_group_sid,
            "kind": "Group",
            "label": "LocalOperators",
            "domain": LOCAL_DOMAIN,
            "is_boundary": False,
        },
        raw=group_raw,
    )

    foreign_user_raw = _raw_record("User", {}, foreign_user_sid, domain=EXTERNAL_DOMAIN)
    foreign_user_norm = NormalizedRecord(
        id=foreign_user_sid,
        kind="User",
        attributes={
            "id": foreign_user_sid,
            "kind": "User",
            "label": f"ForeignAdmin@{EXTERNAL_DOMAIN}",
            "domain": EXTERNAL_DOMAIN,
            "is_boundary": True,
        },
        raw=foreign_user_raw,
    )

    graph = _builder().build([group_norm, foreign_user_norm])
    contract = yaml.safe_load((ROOT / "configs" / "contract.yml").read_text(encoding="utf-8"))
    validate_graph(graph, contract)

    nodes_by_id = {n["id"]: n for n in graph["nodes"]}
    assert nodes_by_id[local_group_sid]["is_boundary"] is False
    assert nodes_by_id[foreign_user_sid]["is_boundary"] is True
    assert nodes_by_id[foreign_user_sid]["domain"] == EXTERNAL_DOMAIN

    assert len(graph["edges"]) == 1
    edge = graph["edges"][0]
    assert edge["source"] == foreign_user_sid
    assert edge["target"] == local_group_sid
    assert edge["kind"] == "MemberOf"


def test_layer3_missing_userrights_creates_unknown_assessment_not_attack_edge():
    """Builder only: omitted UserRights produces unknown without an explicit denied status."""
    computer_sid = f"{LOCAL_DOMAIN_SID}-3101"
    user_sid = f"{LOCAL_DOMAIN_SID}-1101"

    # Computer record with RemoteDesktopUsers but without required UserRights evidence
    computer_raw = _raw_record(
        "Computer",
        {
            "RemoteDesktopUsers": [user_sid],
            # UserRights is omitted / incomplete
        },
        computer_sid,
        domain=LOCAL_DOMAIN,
    )
    computer_norm = NormalizedRecord(
        id=computer_sid,
        kind="Computer",
        attributes={
            "id": computer_sid,
            "kind": "Computer",
            "label": "WS01",
            "domain": LOCAL_DOMAIN,
            "is_boundary": False,
        },
        raw=computer_raw,
    )
    user_raw = _raw_record("User", {}, user_sid, domain=LOCAL_DOMAIN)
    user_norm = NormalizedRecord(
        id=user_sid,
        kind="User",
        attributes={
            "id": user_sid,
            "kind": "User",
            "label": "User01",
            "domain": LOCAL_DOMAIN,
            "is_boundary": False,
        },
        raw=user_raw,
    )

    graph = _builder().build([computer_norm, user_norm])
    contract = yaml.safe_load((ROOT / "configs" / "contract.yml").read_text(encoding="utf-8"))
    validate_graph(graph, contract)

    # Incomplete UserRights must generate unknown assessment
    canrdp_edges = [e for e in graph["edges"] if e["kind"] == "CanRDP"]
    assert len(canrdp_edges) == 0

    unknown_assessments = [
        a for a in graph["assessments"] if a["kind"] == "CanRDP" and a["status"] == "unknown"
    ]
    assert len(unknown_assessments) == 1
    assert unknown_assessments[0]["subject"] == user_sid
    assert unknown_assessments[0]["target"] == computer_sid


def test_layer2_hassession_snapshot_time_provenance_validation():
    """Layer 2: HasSession edges must faithfully capture session snapshot time provenance."""
    computer_sid = f"{LOCAL_DOMAIN_SID}-3102"
    user_sid = f"{LOCAL_DOMAIN_SID}-1102"

    computer_raw = _raw_record(
        "Computer",
        {
            "Sessions": [{"UserId": user_sid, "UserType": "User"}],
        },
        computer_sid,
        domain=LOCAL_DOMAIN,
        time_provenance="observed",
    )
    computer_norm = NormalizedRecord(
        id=computer_sid,
        kind="Computer",
        attributes={
            "id": computer_sid,
            "kind": "Computer",
            "label": "WS02",
            "domain": LOCAL_DOMAIN,
            "is_boundary": False,
        },
        raw=computer_raw,
    )
    user_raw = _raw_record("User", {}, user_sid, domain=LOCAL_DOMAIN)
    user_norm = NormalizedRecord(
        id=user_sid,
        kind="User",
        attributes={
            "id": user_sid,
            "kind": "User",
            "label": "User02",
            "domain": LOCAL_DOMAIN,
            "is_boundary": False,
        },
        raw=user_raw,
    )

    graph = _builder().build([computer_norm, user_norm])
    session_edges = [e for e in graph["edges"] if e["kind"] == "HasSession"]
    assert len(session_edges) == 1
    edge = session_edges[0]
    assert edge["source"] == computer_sid
    assert edge["target"] == user_sid
    assert len(edge["provenance"]) >= 1
    prov = edge["provenance"][0]
    assert graph["metadata"]["snapshot_id"] == SNAPSHOT
    assert prov["raw_file"] == f"snapshot:{SNAPSHOT[7:]}/computer.json"
    assert prov["timestamp"] == CREATED
    assert prov["timestamp_status"] == "observed"
    assert prov["evidence_type"] == "positive"


def _run_raw_cli(tmp_path: Path, *, denied: bool = False) -> dict:
    """Reuse the manifest generator and production CLI for a small independent snapshot."""
    import json
    import shutil
    import subprocess
    import sys

    from src.data.manifest import generate_manifest, write_manifest

    raw_dir = tmp_path / "raw"
    shutil.copytree(ROOT / "tests/fixtures/reconciliation/raw_input", raw_dir)
    if denied:
        path = raw_dir / "computers.json"
        raw = json.loads(path.read_text(encoding="utf-8"))
        host = raw["computers"][0]
        host["UserRights"] = {"Status": "StatusAccessDenied", "Results": []}
        host["UserRightsStatus"] = "StatusAccessDenied"
        host["UserRightsComplete"] = False
        path.write_text(json.dumps(raw), encoding="utf-8")
    manifest = generate_manifest(
        raw_dir,
        dataset_id="pr157-synthetic",
        collector_name="synthetic",
        collector_version="47",
        collected_at=None,
    )
    manifests = tmp_path / "manifests"
    manifests.mkdir()
    write_manifest(manifest, manifests / "pr157.json", source=raw_dir)
    output = tmp_path / "graph.json"
    command = [
        sys.executable,
        "-m",
        "src.parser.cli",
        "--snapshot-id",
        manifest["snapshot_id"],
        "--raw-dir",
        str(raw_dir),
        "--manifest-dir",
        str(manifests),
        "--time-policy",
        str(ROOT / "data/samples/parser-demo/time-policy.json"),
        "--created-at",
        CREATED,
        "--error-policy",
        "fail_fast",
        "--output",
        str(output),
        "--summary",
    ]
    process = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, check=False)
    assert process.returncode == 0, process.stderr
    assert "warnings: 0; errors: 0" in process.stdout
    graph = json.loads(output.read_text(encoding="utf-8"))
    contract = yaml.safe_load((ROOT / "configs/contract.yml").read_text(encoding="utf-8"))
    validate_graph(graph, contract)
    assert graph["metadata"]["snapshot_id"] == manifest["snapshot_id"]
    for edge in graph["edges"]:
        assert all(
            p["raw_file"].startswith("snapshot:" + manifest["snapshot_id"][7:] + "/")
            for p in edge["provenance"]
        )
    return graph


def test_raw_cli_all_m1_relationships_have_independent_directed_expectations(tmp_path):
    graph = _run_raw_cli(tmp_path)
    prefix = "S-1-5-21-700-800-900"
    user, target, group, host = [prefix + suffix for suffix in ("-1101", "-1102", "-2101", "-3101")]
    # Literals specify the expected semantics before observing the parser output.
    assert {(e["source"], e["kind"], e["target"]) for e in graph["edges"]} == {
        (user, "MemberOf", group),
        (group, "AdminTo", host),
        (user, "AdminTo", host),
        (user, "GenericAll", target),
        (user, "WriteDacl", target),
        (user, "ForceChangePassword", target),
        (user, "CanRDP", host),
        (user, "CanPSRemote", host),
        (host, "HasSession", target),
    }
    assert len(graph["nodes"]) == 6
    assert graph["assessments"] == []
    external = next(n for n in graph["nodes"] if n["id"] == "S-1-5-21-1700-1800-1900")
    assert external["is_boundary"] is True  # Explicit flag supplied by raw fixture.
    assert external["domain"] == "EXTERNAL.TEST"
    assert all(
        "Trusts" not in node and "SidFilteringEnabled" not in node for node in graph["nodes"]
    )
    session = next(e for e in graph["edges"] if e["kind"] == "HasSession")
    assert session["provenance"][0]["timestamp"] == "2026-09-24T00:00:00Z"
    assert session["provenance"][0]["timestamp_status"] == "assumed"
    assert session["provenance"][0]["attribute"] == "Sessions[].UserSID"
    assert graph["metadata"]["created_at"] == CREATED


def test_raw_cli_access_denied_keeps_unknown_and_no_canrdp_edge(tmp_path):
    graph = _run_raw_cli(tmp_path, denied=True)
    assert len(graph["edges"]) == 8
    assert not any(e["kind"] == "CanRDP" for e in graph["edges"])
    assert len(graph["assessments"]) == 1
    assessment = graph["assessments"][0]
    assert (
        assessment["kind"],
        assessment["status"],
        assessment["subject"],
        assessment["target"],
    ) == (
        "CanRDP",
        "unknown",
        "S-1-5-21-700-800-900-1101",
        "S-1-5-21-700-800-900-3101",
    )
    assert any(p["attribute"] == "UserRights" for p in assessment["provenance"])
    assert all(p["evidence_type"] == "unknown" for p in assessment["provenance"])
