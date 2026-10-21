"""CLI and integrity verification regression tests for scripts/eda_dataset_analysis.py."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.eda_dataset_analysis import (
    get_code_revision,
    parse_telemetry,
    parse_v3_dataset,
    validate_snapshot_roles,
)
from src.data.manifest import ManifestError, generate_manifest, write_manifest

ROOT = Path(__file__).resolve().parents[1]


def make_synthetic_datasets(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    """Create minimal synthetic SEAMLESS and telemetry datasets with valid manifests."""
    seamless_dir = tmp_path / "seamless_raw"
    seamless_dir.mkdir(parents=True)

    # 6 BloodHound v3 JSON envelopes
    (seamless_dir / "20210920185958_users.json").write_text(
        json.dumps(
            {
                "meta": {"count": 1, "type": "users", "version": 3},
                "users": [
                    {
                        "ObjectIdentifier": "U1@CORP.LOCAL",
                        "Properties": {"name": "U1@CORP.LOCAL", "admincount": True},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    (seamless_dir / "20210920185958_groups.json").write_text(
        json.dumps(
            {
                "meta": {"count": 1, "type": "groups", "version": 3},
                "groups": [
                    {
                        "ObjectIdentifier": "G1@CORP.LOCAL",
                        "Properties": {"name": "G1@CORP.LOCAL", "admincount": False},
                        "Members": [{"MemberId": "U1@CORP.LOCAL", "MemberType": "User"}],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    (seamless_dir / "20210920185958_computers.json").write_text(
        json.dumps(
            {
                "meta": {"count": 1, "type": "computers", "version": 3},
                "computers": [
                    {
                        "ObjectIdentifier": "C1.CORP.LOCAL",
                        "Properties": {"name": "C1.CORP.LOCAL", "operatingsystem": "Windows"},
                        "LocalAdmins": [],
                        "RemoteDesktopUsers": [],
                        "PSRemoteUsers": [],
                        "Sessions": [],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    (seamless_dir / "20210920185958_ous.json").write_text(
        json.dumps(
            {
                "meta": {"count": 1, "type": "ous", "version": 3},
                "ous": [
                    {
                        "ObjectIdentifier": "OU1@CORP.LOCAL",
                        "Properties": {"name": "OU1@CORP.LOCAL"},
                        "ChildOus": [],
                        "Users": [],
                        "Computers": [],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    (seamless_dir / "20210920185958_gpos.json").write_text(
        json.dumps(
            {
                "meta": {"count": 1, "type": "gpos", "version": 3},
                "gpos": [
                    {
                        "ObjectIdentifier": "GPO1@CORP.LOCAL",
                        "Properties": {"name": "GPO1@CORP.LOCAL"},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    (seamless_dir / "20210920185958_domains.json").write_text(
        json.dumps(
            {
                "meta": {"count": 1, "type": "domains", "version": 3},
                "domains": [
                    {
                        "ObjectIdentifier": "CORP.LOCAL",
                        "Properties": {"name": "CORP.LOCAL"},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    seamless_manifest_path = tmp_path / "seamless_manifest.json"
    seamless_m = generate_manifest(
        seamless_dir,
        dataset_id="seamless-v1",
        collector_name="sharphound",
        collector_version=None,
        collected_at=None,
    )
    write_manifest(seamless_m, seamless_manifest_path, source=seamless_dir)

    telemetry_dir = tmp_path / "telemetry_raw"
    telemetry_dir.mkdir(parents=True)
    telemetry_csv = telemetry_dir / "evtx_data.csv"
    telemetry_csv.write_text(
        "EventID,EVTX_Tactic,Computer,TargetUserName,SystemTime\n"
        "4624,Lateral Movement,PC01,ALICE,2020-01-01 10:00:00\n"
        "4672,Privilege Escalation,PC01,ALICE,2020-01-01 10:00:01\n",
        encoding="utf-8",
    )

    telemetry_manifest_path = tmp_path / "telemetry_manifest.json"
    telemetry_m = generate_manifest(
        telemetry_dir,
        dataset_id="telemetry-raw-v1",
        collector_name="evtx-attack-samples",
        collector_version=None,
        collected_at=None,
    )
    write_manifest(telemetry_m, telemetry_manifest_path, source=telemetry_dir)

    return seamless_dir, seamless_manifest_path, telemetry_dir, telemetry_manifest_path


def run_eda_cli(
    seamless_dir: Path,
    seamless_manifest: Path,
    telemetry_dir: Path,
    telemetry_manifest: Path,
    output: Path,
    extra_args: list[str] | None = None,
) -> subprocess.CompletedProcess:
    args = [
        sys.executable,
        str(ROOT / "scripts/eda_dataset_analysis.py"),
        "--seamless-dir",
        str(seamless_dir),
        "--seamless-manifest",
        str(seamless_manifest),
        "--telemetry-dir",
        str(telemetry_dir),
        "--telemetry-manifest",
        str(telemetry_manifest),
        "--output",
        str(output),
        "--north-dir",
        str(seamless_dir / "nonexistent_north"),
        "--ad-sample-dir",
        str(seamless_dir / "nonexistent_ad_sample"),
    ]
    if extra_args:
        args.extend(extra_args)
    return subprocess.run(args, capture_output=True, text=True, cwd=ROOT)


def test_cli_successful_run_and_provenance_output(tmp_path: Path):
    s_dir, s_manifest, t_dir, t_manifest = make_synthetic_datasets(tmp_path)
    output = tmp_path / "eda_summary.json"

    result = run_eda_cli(s_dir, s_manifest, t_dir, t_manifest, output)
    assert result.returncode == 0
    assert output.is_file()

    data = json.loads(output.read_text(encoding="utf-8"))
    assert "SEAMLESS" in data
    assert "telemetry" in data

    # Check SEAMLESS provenance metadata
    s_meta = data["SEAMLESS"]["provenance_metadata"]
    assert s_meta["dataset_id"] == "seamless-v1"
    assert s_meta["schema_version"] == 1
    assert len(s_meta["files"]) == 6
    assert s_meta["analyzed_population"]["total_raw_records"] == 6

    # Check telemetry population separation
    t_pop = data["telemetry"]["population_provenance"]
    assert t_pop["measured_events"] == 2
    assert t_pop["distinct_upstream_tactic_labels"] == 2
    assert t_pop["external_corpus_claim"]["claimed_events"] == 6432
    assert t_pop["external_corpus_claim"]["claimed_tactics"] == 11
    telemetry = data["telemetry"]
    assert telemetry["upstream_tactic_annotations"] == {
        "source_field": "EVTX_Tactic",
        "status": "upstream_annotation_not_windows_ground_truth",
        "distribution": {"Lateral Movement": 1, "Privilege Escalation": 1},
    }
    assert telemetry["telemetry_evidence_inventory"]["scope"] == "corpus_statistics_only"
    assert telemetry["telemetry_evidence_inventory"]["semantic_catalog"] == (
        "configs/attack_semantics.yml"
    )
    assert telemetry["telemetry_evidence_inventory"]["attack_or_relationship_attribution"] == (
        "not_assessed"
    )
    assert "m1_edge_telemetry_matrix" not in telemetry

    # Check referential integrity stratification
    ref_int = data["SEAMLESS"]["data_quality_audit"]["referential_integrity"]
    assert "collected_entity_resolutions" in ref_int
    assert "boundary_stub_resolutions" in ref_int
    assert "unresolved_dangling_references" in ref_int
    assert ref_int["unresolved_dangling_references"]["count"] == 0
    host_access = data["SEAMLESS"]["host_access_semantics"]
    assert (
        host_access["raw_primitives"]["RemoteDesktopUsers_raw_memberships"]["raw_observation_count"]
        == 0
    )
    assert host_access["effective_relationships"]["CanRDP"]["status"] == "unknown"
    assert (
        data["SEAMLESS"]["data_quality_audit"]["unknown_rate_by_edge_type"]["CanRDP"][
            "verified_effective_edges_count"
        ]
        is None
    )
    assert (
        "canonical relationship absence cannot be concluded"
        in data["SEAMLESS"]["data_quality_audit"]["unknown_rate_by_edge_type"]["CanRDP"]["note"]
    )


def test_event_id_counts_do_not_map_passive_membership_or_session_access(tmp_path: Path):
    csv_path = tmp_path / "evtx_data.csv"
    csv_path.write_text(
        "EventID,EVTX_Tactic,Computer,TargetUserName,SystemTime\n"
        "4728,Privilege Escalation,PC01,ALICE,2020-01-01 10:00:00\n"
        "4729,Privilege Escalation,PC01,ALICE,2020-01-01 10:00:01\n"
        "10,Credential Access,PC01,ALICE,2020-01-01 10:00:02\n",
        encoding="utf-8",
    )

    report = parse_telemetry(csv_path)

    assert report["corpus_event_id_distribution"] == {"4728": 1, "4729": 1, "10": 1}
    assert report["telemetry_evidence_inventory"]["event_id_qualification"] == "not_assessed"
    assert report["telemetry_evidence_inventory"]["attack_or_relationship_attribution"] == (
        "not_assessed"
    )
    assert report["upstream_tactic_annotations"]["distribution"] == {
        "Privilege Escalation": 2,
        "Credential Access": 1,
    }
    assert "m1_edge_telemetry_matrix" not in report


def test_cli_scoped_historical_preservation_is_explicit_and_recomputes_comparison(
    tmp_path: Path,
):
    s_dir, s_manifest, t_dir, t_manifest = make_synthetic_datasets(tmp_path)
    historical = tmp_path / "historical_report.json"
    historical.write_text(
        json.dumps(
            {
                "NORTH": {
                    "edge_counts": {"CanRDP": 1},
                    "total_nodes": 2,
                    "total_edges": 1,
                    "simple_edges": 1,
                },
                "ad_sampledata": {
                    "edge_counts": {},
                    "total_nodes": 1,
                    "total_edges": 0,
                    "simple_edges": 0,
                },
                "collector_bias_comparison": {
                    "Per_edge_kind_breakdown": {
                        "CanRDP": {
                            "SharpHound": 1,
                            "BloodHound.py": 0,
                            "Common": 0,
                            "Union": 1,
                            "Jaccard": 0.0,
                        }
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    output = tmp_path / "eda_summary.json"

    result = run_eda_cli(
        s_dir,
        s_manifest,
        t_dir,
        t_manifest,
        output,
        extra_args=["--preserve-historical-report", str(historical)],
    )
    assert result.returncode == 0, result.stderr

    data = json.loads(output.read_text(encoding="utf-8"))
    assert data["report_provenance"]["mode"] == "scoped_preservation"
    assert data["report_provenance"]["sections"]["NORTH"]["status"] == ("preserved_historical")
    assert data["NORTH"]["edge_counts"] == {}
    assert data["NORTH"]["raw_host_access_counts"]["RemoteDesktopUsers_raw_memberships"] == 1
    assert data["cross_dataset_normalized_comparison"]["NORTH"]["total_edges"] == 0
    assert "CanRDP" not in data["collector_bias_comparison"]["Per_edge_kind_breakdown"]
    assert (
        "RemoteDesktopUsers_raw_memberships"
        in data["collector_bias_comparison"]["Per_edge_kind_breakdown"]
    )


def test_cli_modified_bytes_fails_fast_and_preserves_existing_report(tmp_path: Path):
    s_dir, s_manifest, t_dir, t_manifest = make_synthetic_datasets(tmp_path)
    output = tmp_path / "eda_summary.json"
    sentinel = b'{"sentinel": true}\n'
    output.write_bytes(sentinel)

    # Tamper with one SEAMLESS file
    target = s_dir / "20210920185958_users.json"
    target.write_text(target.read_text(encoding="utf-8") + " ", encoding="utf-8")

    result = run_eda_cli(s_dir, s_manifest, t_dir, t_manifest, output)
    assert result.returncode != 0
    assert "verification failed" in result.stderr
    assert output.read_bytes() == sentinel


def test_cli_missing_file_fails_fast_and_preserves_output(tmp_path: Path):
    s_dir, s_manifest, t_dir, t_manifest = make_synthetic_datasets(tmp_path)
    output = tmp_path / "eda_summary.json"
    sentinel = b'{"sentinel": true}\n'
    output.write_bytes(sentinel)

    # Delete one file
    (s_dir / "20210920185958_domains.json").unlink()

    result = run_eda_cli(s_dir, s_manifest, t_dir, t_manifest, output)
    assert result.returncode != 0
    assert "verification failed" in result.stderr
    assert output.read_bytes() == sentinel


def test_cli_extra_file_fails_fast_and_preserves_output(tmp_path: Path):
    s_dir, s_manifest, t_dir, t_manifest = make_synthetic_datasets(tmp_path)
    output = tmp_path / "eda_summary.json"
    sentinel = b'{"sentinel": true}\n'
    output.write_bytes(sentinel)

    # Add extra unexpected file
    (s_dir / "unexpected.json").write_text("{}", encoding="utf-8")

    result = run_eda_cli(s_dir, s_manifest, t_dir, t_manifest, output)
    assert result.returncode != 0
    assert "verification failed" in result.stderr
    assert output.read_bytes() == sentinel


def test_cli_missing_primary_directory_fails_fast_with_code_2(tmp_path: Path):
    s_dir, s_manifest, t_dir, t_manifest = make_synthetic_datasets(tmp_path)
    output = tmp_path / "eda_summary.json"
    missing_dir = tmp_path / "nonexistent_seamless"

    result = run_eda_cli(missing_dir, s_manifest, t_dir, t_manifest, output)
    assert result.returncode == 2
    assert "directory not found" in result.stderr.lower()
    assert not output.exists()


def test_cli_invalid_manifest_id_fails_fast(tmp_path: Path):
    s_dir, s_manifest, t_dir, t_manifest = make_synthetic_datasets(tmp_path)
    output = tmp_path / "eda_summary.json"

    # Tamper manifest snapshot_id
    m_data = json.loads(s_manifest.read_text(encoding="utf-8"))
    m_data["snapshot_id"] = "sha256:" + "0" * 64
    s_manifest.write_text(json.dumps(m_data), encoding="utf-8")

    result = run_eda_cli(s_dir, s_manifest, t_dir, t_manifest, output)
    assert result.returncode == 2
    assert "invalid" in result.stderr.lower() or "error" in result.stderr.lower()
    assert not output.exists()


def test_instrumented_reader_tamper_after_preflight_fails(tmp_path: Path):
    s_dir, s_manifest, _, _ = make_synthetic_datasets(tmp_path)
    manifest = json.loads(s_manifest.read_text(encoding="utf-8"))

    # Tamper after manifest object is prepared
    target = s_dir / "20210920185958_users.json"
    target.write_text(target.read_text(encoding="utf-8") + " ", encoding="utf-8")

    # read_verified_snapshot_file inside parse_v3_dataset must fail on tampered bytes
    with pytest.raises(ManifestError, match="referenced file does not match manifest"):
        parse_v3_dataset(s_dir, manifest=manifest)


def test_deterministic_output_across_repeated_runs(tmp_path: Path):
    s_dir, s_manifest, t_dir, t_manifest = make_synthetic_datasets(tmp_path)
    out1 = tmp_path / "eda_1.json"
    out2 = tmp_path / "eda_2.json"

    res1 = run_eda_cli(s_dir, s_manifest, t_dir, t_manifest, out1)
    res2 = run_eda_cli(s_dir, s_manifest, t_dir, t_manifest, out2)

    assert res1.returncode == 0
    assert res2.returncode == 0
    assert out1.read_bytes() == out2.read_bytes()


def test_cli_valid_manifest_omitting_required_role_fails(tmp_path: Path):
    """A valid manifest that omits one required role (e.g. domains) must fail semantic preflight."""
    s_dir, _, t_dir, t_manifest = make_synthetic_datasets(tmp_path)
    (s_dir / "20210920185958_domains.json").unlink()
    omitted_manifest = tmp_path / "omitted_seamless.json"
    m = generate_manifest(
        s_dir,
        dataset_id="seamless-v1",
        collector_name="sharphound",
        collector_version=None,
        collected_at=None,
    )
    write_manifest(m, omitted_manifest, source=s_dir)

    output = tmp_path / "eda_summary.json"
    sentinel = b"sentinel-keep"
    output.write_bytes(sentinel)

    result = run_eda_cli(s_dir, omitted_manifest, t_dir, t_manifest, output)
    assert result.returncode != 0
    assert "Missing required SEAMLESS envelope role: 'domains'" in result.stderr
    assert output.read_bytes() == sentinel


def test_cli_telemetry_omitting_evtx_data_fails(tmp_path: Path):
    """A telemetry manifest omitting evtx_data.csv must fail semantic preflight."""
    s_dir, s_manifest, _, _ = make_synthetic_datasets(tmp_path)
    custom_telemetry_dir = tmp_path / "telemetry_no_csv"
    custom_telemetry_dir.mkdir()
    (custom_telemetry_dir / "other.csv").write_text("a,b\n1,2", encoding="utf-8")
    t_manifest = tmp_path / "telemetry_no_csv.json"
    m = generate_manifest(
        custom_telemetry_dir,
        dataset_id="telemetry-raw-v1",
        collector_name="evtx-attack-samples",
        collector_version=None,
        collected_at=None,
    )
    write_manifest(m, t_manifest, source=custom_telemetry_dir)

    output = tmp_path / "eda_summary.json"
    sentinel = b"sentinel-keep"
    output.write_bytes(sentinel)

    result = run_eda_cli(s_dir, s_manifest, custom_telemetry_dir, t_manifest, output)
    assert result.returncode != 0
    assert "Missing required telemetry file: 'evtx_data.csv'" in result.stderr
    assert output.read_bytes() == sentinel


def test_get_code_revision_clean_dirty_and_no_git(tmp_path: Path):
    """get_code_revision returns generator digest, real git state, and never a fixed fallback."""
    rev = get_code_revision()
    assert isinstance(rev, dict)
    assert "generator_sha256" in rev
    assert len(rev["generator_sha256"]) == 64
    assert rev["generator_sha256"] != "unknown"
    assert rev.get("git_commit") != "deb99fe"

    # In a non-git directory, git_commit and git_dirty must be None, never hard-coded fallback
    no_git_dir = tmp_path / "empty_dir"
    no_git_dir.mkdir()
    rev_no_git = get_code_revision(root_dir=no_git_dir)
    assert rev_no_git["git_commit"] is None
    assert rev_no_git["git_dirty"] is None
    assert rev_no_git["generator_sha256"] == rev["generator_sha256"]


def test_telemetry_temporal_span_consistency_with_audit_doc():
    """Ensure generated temporal span matches verified metrics and documentation."""
    telemetry_csv = ROOT / "data" / "raw" / "telemetry" / "evtx_data.csv"
    if not telemetry_csv.exists():
        pytest.skip("Local telemetry raw file not present")

    res = parse_telemetry(telemetry_csv)
    earliest = res["temporal_span"]["earliest"]
    latest = res["temporal_span"]["latest"]

    assert earliest == "2017-06-09 19:21:26"
    assert latest == "2021-06-09 05:18:11"

    # Audit document must agree with the exact measured bounds
    audit_doc = (ROOT / "docs" / "research" / "provenance-audit.md").read_text(encoding="utf-8")
    assert "2017-06-09 19:21:26" in audit_doc
    assert "2021-06-09 05:18:11" in audit_doc
    assert "19:35:10" not in audit_doc
    assert "17:09:47" not in audit_doc


def test_validate_snapshot_roles_direct():
    """Unit test for validate_snapshot_roles directly on incomplete manifest dicts."""
    empty_manifest: dict[str, list] = {"files": []}
    issues = validate_snapshot_roles(empty_manifest, "seamless")
    assert len(issues) == 6
    assert any("computers" in i for i in issues)

    telemetry_issues = validate_snapshot_roles(empty_manifest, "telemetry")
    assert len(telemetry_issues) == 1
    assert "evtx_data.csv" in telemetry_issues[0]
