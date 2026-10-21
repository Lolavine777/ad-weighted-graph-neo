"""Focused tests for final clean-checkout reconciliation reproduction logic."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.research import reproduce_legacy_reconciliation as rep_module
from scripts.research.reproduce_legacy_reconciliation import (
    ACCEPTED_MANIFEST_DIGEST,
    ACCEPTED_SNAPSHOT,
    compute_per_slice_proofs,
    execute_reproduction,
    verify_external_prerequisites,
)


def test_verify_prerequisites_rejects_bad_manifest(tmp_path):
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps({"snapshot_id": "bad"}), encoding="utf-8")

    with pytest.raises(ValueError, match="manifest digest mismatch"):
        verify_external_prerequisites(raw_dir, manifest_path, tmp_path)


def test_verify_prerequisites_rejects_missing_raw_files(tmp_path):
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_bytes(Path("data/samples/manifests/seamless-raw-v1.json").read_bytes())

    prereq_dir = tmp_path / "prereq"
    prereq_dir.mkdir()

    with pytest.raises(ValueError, match="raw manifest verification failed"):
        verify_external_prerequisites(raw_dir, manifest_path, prereq_dir)


def test_verify_prerequisites_rejects_missing_raw_dir(tmp_path):
    manifest_path = Path("data/samples/manifests/seamless-raw-v1.json")
    with pytest.raises(ValueError, match="raw directory not found"):
        verify_external_prerequisites(tmp_path / "nonexistent", manifest_path, tmp_path)


def test_verify_prerequisites_rejects_missing_manifest(tmp_path):
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    with pytest.raises(ValueError, match="manifest not found"):
        verify_external_prerequisites(raw_dir, tmp_path / "nonexistent.json", tmp_path)


def test_verify_prerequisites_rejects_missing_prerequisite(tmp_path):
    real_raw = Path("data/raw/SEAMLESS")
    if not real_raw.is_dir():
        pytest.skip("Local SEAMLESS raw directory not present")
    manifest_path = Path("data/samples/manifests/seamless-raw-v1.json")
    prereq_dir = tmp_path / "empty_prereqs"
    prereq_dir.mkdir()

    with pytest.raises(ValueError, match="missing external prerequisite"):
        verify_external_prerequisites(real_raw, manifest_path, prereq_dir)


def test_sanitization_constants():
    assert ACCEPTED_SNAPSHOT.startswith("sha256:")
    assert len(ACCEPTED_MANIFEST_DIGEST) == 64


def test_cli_rejects_skip_parser_run():
    """Verify that --skip-parser-run is rejected and absent from CLI arguments."""
    res = subprocess.run(
        [
            sys.executable,
            "scripts/research/reproduce_legacy_reconciliation.py",
            "--prerequisites-dir",
            "dummy_prereqs",
            "--work-dir",
            "dummy_work",
            "--skip-parser-run",
        ],
        capture_output=True,
        text=True,
    )
    assert res.returncode != 0
    assert "unrecognized arguments: --skip-parser-run" in res.stderr


def test_execute_reproduction_rejects_existing_canonical_output(tmp_path):
    """Verify that existing generated project.json cannot be reused to bypass clean parse."""
    work_dir = tmp_path / "work"
    work_dir.mkdir()
    (work_dir / "project.json").write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="clean reproduction boundary violation"):
        execute_reproduction(
            raw_root=tmp_path / "raw",
            manifest_path=tmp_path / "manifest.json",
            prerequisites_dir=tmp_path / "prereqs",
            work_dir=work_dir,
        )


SID_U0 = "S-1-5-21-1000-2000-3000-1000"
SID_U1 = "S-1-5-21-1000-2000-3000-1001"
SID_U2 = "S-1-5-21-1000-2000-3000-1002"
SID_U3 = "S-1-5-21-1000-2000-3000-1003"
SID_U4 = "S-1-5-21-1000-2000-3000-1004"

SID_H0 = "S-1-5-21-1000-2000-3000-2000"
SID_H1 = "S-1-5-21-1000-2000-3000-2001"
SID_H2 = "S-1-5-21-1000-2000-3000-2002"
SID_H3 = "S-1-5-21-1000-2000-3000-2003"
SID_H4 = "S-1-5-21-1000-2000-3000-2004"

SID_G1 = "S-1-5-21-1000-2000-3000-3001"
SID_SWAPPED = "S-1-5-21-1000-2000-3000-8888"
SID_WRONG = "S-1-5-21-1000-2000-3000-9999"


def _make_graph_fixture(edges=None, nodes=None, assessments=None):
    all_sids = [
        SID_U0,
        SID_U1,
        SID_U2,
        SID_U3,
        SID_U4,
        SID_H0,
        SID_H1,
        SID_H2,
        SID_H3,
        SID_H4,
        SID_G1,
        SID_SWAPPED,
        SID_WRONG,
    ]
    return {
        "nodes": nodes
        or [
            {
                "id": sid,
                "kind": "User" if "-100" in sid else ("Group" if "-300" in sid else "Computer"),
                "domain": "TEST.LOCAL",
                "is_boundary": False,
            }
            for sid in all_sids
        ],
        "edges": edges or [],
        "assessments": assessments or [],
        "metadata": {
            "contract_version": "1.3.0",
            "weight_profile": "unweighted_v1",
            "code_version": "0.1.0",
        },
    }


def test_mutation_canpsremote_same_count_fails_closed(monkeypatch, tmp_path):
    """Mutating a CanPSRemote target while keeping count=2 must fail exact_sets_equal."""
    e1 = {"source": SID_U1, "kind": "CanPSRemote", "target": SID_H1}
    e2 = {"source": SID_U2, "kind": "CanPSRemote", "target": SID_H2}
    e2_mutated = {"source": SID_U2, "kind": "CanPSRemote", "target": SID_WRONG}

    t1 = (SID_U1, "CanPSRemote", SID_H1)
    t2 = (SID_U2, "CanPSRemote", SID_H2)
    raw_fixture = {
        t1: [{"rule": "PSRemoteUsers"}],
        t2: [{"rule": "PSRemoteUsers"}],
    }
    monkeypatch.setattr(rep_module, "raw_index", lambda r, m, mapping: raw_fixture)

    proj = _make_graph_fixture(edges=[e1, e2_mutated])
    legacy = _make_graph_fixture(edges=[e1, e2])

    proofs = compute_per_slice_proofs(
        project_graph=proj,
        baseline_graph=legacy,
        mapping={},
        raw_root=tmp_path,
        manifest={},
    )
    ps = proofs["CanPSRemote"]
    assert ps["project_count"] == 2
    assert ps["legacy_count"] == 2
    assert ps["exact_sets_equal"] is False
    assert ps["project_only_count"] == 1
    assert ps["legacy_only_count"] == 1


def test_mutation_adminto_direct_same_count_fails_closed(monkeypatch, tmp_path):
    """Mutating an AdminTo direct target while keeping count=5 must fail direct_exact_sets_equal."""
    u_sids = [SID_U0, SID_U1, SID_U2, SID_U3, SID_U4]
    h_sids = [SID_H0, SID_H1, SID_H2, SID_H3, SID_H4]
    direct_edges = [{"source": u_sids[i], "kind": "AdminTo", "target": h_sids[i]} for i in range(5)]
    mutated_edges = [
        {"source": u_sids[0], "kind": "AdminTo", "target": SID_SWAPPED},
        *direct_edges[1:],
    ]
    raw_fixture = {(u_sids[i], "AdminTo", h_sids[i]): [{"rule": "LocalAdmins"}] for i in range(5)}
    monkeypatch.setattr(rep_module, "raw_index", lambda r, m, mapping: raw_fixture)

    proj = _make_graph_fixture(edges=mutated_edges)
    legacy = _make_graph_fixture(edges=direct_edges)

    proofs = compute_per_slice_proofs(
        project_graph=proj,
        baseline_graph=legacy,
        mapping={},
        raw_root=tmp_path,
        manifest={},
    )
    at = proofs["AdminTo"]
    assert at["direct_exact_sets_equal"] is False


def test_mutation_genericall_self_ace_swap_fails_closed(monkeypatch, tmp_path):
    """Swapping a non-self GenericAll to self-ACE (same total count) must fail nonself equality."""
    nonself_t = (SID_U1, "GenericAll", SID_G1)
    self_t = (SID_G1, "GenericAll", SID_G1)
    raw_fixture = {
        nonself_t: [{"rule": "Aces"}],
        self_t: [{"rule": "Aces"}],
    }
    monkeypatch.setattr(rep_module, "raw_index", lambda r, m, mapping: raw_fixture)

    proj = _make_graph_fixture(
        edges=[
            {"source": SID_G1, "kind": "GenericAll", "target": SID_G1},
            {"source": SID_U1, "kind": "GenericAll", "target": SID_U1},
        ]
    )
    legacy = _make_graph_fixture(
        edges=[
            {"source": SID_U1, "kind": "GenericAll", "target": SID_G1},
        ]
    )

    proofs = compute_per_slice_proofs(
        project_graph=proj,
        baseline_graph=legacy,
        mapping={},
        raw_root=tmp_path,
        manifest={},
    )
    ga = proofs["GenericAll"]
    assert ga["nonself_exact_sets_equal"] is False


def test_mutation_canrdp_assessment_semantics_fails_closed(monkeypatch, tmp_path):
    """CanRDP assessment with status != 'unknown' or reason != incomplete must fail closed."""
    t1 = (SID_U1, "CanRDP", SID_H1)
    t2 = (SID_U2, "CanRDP", SID_H2)
    t3 = (SID_U3, "CanRDP", SID_H3)
    raw_fixture = {
        t1: [{"rule": "RemoteDesktopUsers", "user_rights_present": False}],
        t2: [{"rule": "RemoteDesktopUsers", "user_rights_present": False}],
        t3: [{"rule": "RemoteDesktopUsers", "user_rights_present": False}],
    }
    monkeypatch.setattr(rep_module, "raw_index", lambda r, m, mapping: raw_fixture)

    legacy = _make_graph_fixture(
        edges=[
            {"source": SID_U1, "kind": "CanRDP", "target": SID_H1},
            {"source": SID_U2, "kind": "CanRDP", "target": SID_H2},
            {"source": SID_U3, "kind": "CanRDP", "target": SID_H3},
        ]
    )
    # Mutate 1 assessment to have status="positive"
    proj_mutated = _make_graph_fixture(
        assessments=[
            {
                "subject": SID_U1,
                "kind": "CanRDP",
                "target": SID_H1,
                "status": "unknown",
                "reason": "required UserRights evidence is incomplete",
            },
            {
                "subject": SID_U2,
                "kind": "CanRDP",
                "target": SID_H2,
                "status": "positive",
                "reason": "UserRights present",
            },
            {
                "subject": SID_U3,
                "kind": "CanRDP",
                "target": SID_H3,
                "status": "unknown",
                "reason": "required UserRights evidence is incomplete",
            },
        ]
    )

    proofs = compute_per_slice_proofs(
        project_graph=proj_mutated,
        baseline_graph=legacy,
        mapping={},
        raw_root=tmp_path,
        manifest={},
    )
    rdp = proofs["CanRDP"]
    assert rdp["all_assessments_status_unknown"] is False
