"""Unit and integration tests for scripts/reconcile_graph_baseline.py."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.reconcile_graph_baseline import (
    main,
    map_node_id,
    normalize_relationship_kind,
    reconcile_graphs,
)

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures" / "reconciliation"
CANDIDATE_PATH = FIXTURES_DIR / "candidate_graph.json"
BASELINE_EXACT_PATH = FIXTURES_DIR / "baseline_exact_graph.json"
BASELINE_MULT_PATH = FIXTURES_DIR / "baseline_multiplicity_graph.json"
BASELINE_DISC_PATH = FIXTURES_DIR / "baseline_discrepancy_graph.json"
BASELINE_EMPTY_PATH = FIXTURES_DIR / "baseline_empty_unmeasurable.json"
MAPPING_PATH = FIXTURES_DIR / "identity_mapping.json"


@pytest.fixture
def candidate_data() -> dict:
    return json.loads(CANDIDATE_PATH.read_text(encoding="utf-8"))


@pytest.fixture
def baseline_exact_data() -> dict:
    return json.loads(BASELINE_EXACT_PATH.read_text(encoding="utf-8"))


@pytest.fixture
def baseline_multiplicity_data() -> dict:
    return json.loads(BASELINE_MULT_PATH.read_text(encoding="utf-8"))


@pytest.fixture
def baseline_discrepancy_data() -> dict:
    return json.loads(BASELINE_DISC_PATH.read_text(encoding="utf-8"))


@pytest.fixture
def baseline_empty_data() -> dict:
    return json.loads(BASELINE_EMPTY_PATH.read_text(encoding="utf-8"))


@pytest.fixture
def identity_mapping() -> dict:
    return json.loads(MAPPING_PATH.read_text(encoding="utf-8"))


def test_normalize_relationship_kind():
    assert normalize_relationship_kind("MEMBEROF") == "MemberOf"
    assert normalize_relationship_kind("adminto") == "AdminTo"
    assert normalize_relationship_kind("GenericAll") == "GenericAll"
    assert normalize_relationship_kind("CANRDP") == "CanRDP"
    assert normalize_relationship_kind("HASSESSION") == "HasSession"
    assert normalize_relationship_kind("CustomRelation") == "CustomRelation"


def test_map_node_id(identity_mapping):
    # Explicit mapping
    raw_key = "DOMAIN.LOCAL-S-1-5-21-500-600-700-1101"
    assert map_node_id(raw_key, identity_mapping) == "S-1-5-21-500-600-700-1101"

    # SID normalization without mapping
    assert map_node_id("s-1-5-21-1-2-3", None) == "S-1-5-21-1-2-3"

    # A Legacy prefix requires explicit identity evidence.
    with pytest.raises(ValueError, match="unresolved"):
        map_node_id("PREFIX-S-1-5-21-9-9-9", None)


def test_reconcile_exact_match(candidate_data, baseline_exact_data, identity_mapping):
    report = reconcile_graphs(
        candidate_data,
        baseline_exact_data,
        identity_mapping=identity_mapping,
    )
    assert report.verdict == "MATCH"
    assert "Exact structural match across 10 nodes" in report.summary

    nr = report.node_reconciliation
    assert nr["overall"]["jaccard_similarity"] == 1.0
    assert nr["overall"]["candidate_only_count"] == 0
    assert nr["overall"]["baseline_only_count"] == 0
    assert nr["candidate_population"]["collected"] == 8
    assert nr["candidate_population"]["boundary"] == 2
    assert nr["baseline_population"]["collected"] == 8
    assert nr["baseline_population"]["boundary"] == 2
    assert len(nr["boundary_mismatches"]) == 0

    tr = report.triple_reconciliation
    assert tr["overall"]["jaccard_similarity"] == 1.0
    assert tr["overall"]["candidate_only_count"] == 0
    assert tr["overall"]["baseline_only_count"] == 0
    assert tr["candidate_multiplicity"]["unique_triples"] == 13
    assert tr["baseline_multiplicity"]["unique_triples"] == 13

    dl = report.discrepancy_ledgers
    assert dl["member_of_discrepancies"] == []
    assert dl["generic_all_discrepancies"] == []
    assert dl["other_discrepancies"] == []


def test_reconcile_multiplicity(candidate_data, baseline_multiplicity_data, identity_mapping):
    report = reconcile_graphs(
        candidate_data,
        baseline_multiplicity_data,
        identity_mapping=identity_mapping,
    )
    assert report.verdict == "MATCH"

    # Unique triples match 100%
    assert report.triple_reconciliation["overall"]["jaccard_similarity"] == 1.0

    # Stored multiplicity is reported separately
    base_mult = report.triple_reconciliation["baseline_multiplicity"]
    assert base_mult["unique_triples"] == 13
    assert base_mult["stored_edges"] == 17
    assert base_mult["multiplicity_ratio"] > 1.0

    # Candidate has 13 edges but 14 evidence items
    cand_mult = report.triple_reconciliation["candidate_multiplicity"]
    assert cand_mult["unique_triples"] == 13
    assert cand_mult["stored_edges"] == 13
    assert cand_mult["stored_evidence_occurrences"] == 14


def test_reconcile_discrepancies(candidate_data, baseline_discrepancy_data, identity_mapping):
    report = reconcile_graphs(
        candidate_data,
        baseline_discrepancy_data,
        identity_mapping=identity_mapping,
    )
    assert report.verdict == "DISCREPANCY"

    nr = report.node_reconciliation
    assert nr["overall"]["candidate_only_count"] == 1
    assert nr["overall"]["baseline_only_count"] == 1
    assert "S-1-5-21-500-600-700-1104" in nr["overall"]["candidate_only_samples"]
    assert "S-1-5-21-500-600-700-3199" in nr["overall"]["baseline_only_samples"]

    # Boundary flag mismatch detected
    assert len(nr["boundary_mismatches"]) == 1
    mismatch = nr["boundary_mismatches"][0]
    assert mismatch["id"] == "S-1-5-21-888-999-100-1105"
    assert mismatch["candidate_is_boundary"] is True
    assert mismatch["baseline_is_boundary"] is False

    dl = report.discrepancy_ledgers
    # MemberOf ledger captures missing relationship
    assert len(dl["member_of_discrepancies"]) == 1
    assert dl["member_of_discrepancies"][0]["kind"] == "MemberOf"

    # GenericAll ledger captures extra relationship
    assert len(dl["generic_all_discrepancies"]) == 1
    assert dl["generic_all_discrepancies"][0]["kind"] == "GenericAll"

    # Other discrepancies capture direction inversion and ForceChangePassword
    assert len(dl["other_discrepancies"]) >= 2


def test_reconcile_empty_unmeasurable(candidate_data, baseline_empty_data):
    report = reconcile_graphs(candidate_data, baseline_empty_data)
    assert report.verdict == "NOT_MEASURABLE"
    assert "Reconciliation pending" in report.summary
    assert report.node_reconciliation["status"] == "not_measurable"
    assert report.triple_reconciliation["status"] == "not_measurable"


def test_cli_exact_match():
    exit_code = main(
        [
            "--candidate",
            str(CANDIDATE_PATH),
            "--baseline",
            str(BASELINE_EXACT_PATH),
            "--mapping",
            str(MAPPING_PATH),
        ]
    )
    assert exit_code == 0


def test_cli_discrepancy():
    exit_code = main(
        [
            "--candidate",
            str(CANDIDATE_PATH),
            "--baseline",
            str(BASELINE_DISC_PATH),
            "--mapping",
            str(MAPPING_PATH),
        ]
    )
    assert exit_code == 1


def test_cli_unmeasurable():
    exit_code = main(
        [
            "--candidate",
            str(CANDIDATE_PATH),
            "--baseline",
            str(BASELINE_EMPTY_PATH),
        ]
    )
    assert exit_code == 2


def test_cli_json_output(tmp_path):
    out_file = tmp_path / "reconciliation.json"
    exit_code = main(
        [
            "--candidate",
            str(CANDIDATE_PATH),
            "--baseline",
            str(BASELINE_EXACT_PATH),
            "--mapping",
            str(MAPPING_PATH),
            "--output",
            str(out_file),
            "--format",
            "json",
        ]
    )
    assert exit_code == 0
    assert out_file.exists()
    payload = json.loads(out_file.read_text(encoding="utf-8"))
    assert payload["verdict"] == "MATCH"
    assert payload["triple_reconciliation"]["overall"]["intersection_count"] == 13


def test_cli_file_not_found():
    exit_code = main(
        [
            "--candidate",
            "non_existent_candidate.json",
            "--baseline",
            str(BASELINE_EXACT_PATH),
        ]
    )
    assert exit_code == 2


# These expectations follow the review's independent input cases, not comparator helpers.
@pytest.fixture
def cli_run(tmp_path):
    import subprocess
    import sys

    def run(candidate, baseline, mapping=None, *, text=False):
        paths = {}
        for name, data in [("candidate", candidate), ("baseline", baseline), ("mapping", mapping)]:
            path = tmp_path / f"{name}.json"
            path.write_text(json.dumps(data), encoding="utf-8")
            paths[name] = path
        report_path = tmp_path / "report.json"
        command = [
            sys.executable,
            str(FIXTURES_DIR.parents[2] / "scripts/reconcile_graph_baseline.py"),
            "--candidate",
            str(paths["candidate"]),
            "--baseline",
            str(paths["baseline"]),
            "--output",
            str(report_path),
        ]
        if mapping is not None:
            command += ["--mapping", str(paths["mapping"])]
        if not text:
            command += ["--format", "json"]
        process = subprocess.run(command, capture_output=True, text=True, check=False)
        report = (
            json.loads(report_path.read_text(encoding="utf-8")) if report_path.exists() else None
        )
        return process, report

    return run


@pytest.mark.parametrize(
    "ids",
    [
        ["domain:sid:S-1-5-21-1-2-3:S-1-5-32-544", "domain:sid:S-1-5-21-4-5-6:S-1-5-32-544"],
        [
            "domain:11111111-1111-4111-8111-111111111111:S-1-5-32-544",
            "domain:22222222-2222-4222-8222-222222222222:S-1-5-32-544",
        ],
        [
            "host:11111111-1111-4111-8111-111111111111:S-1-5-32-544",
            "host:22222222-2222-4222-8222-222222222222:S-1-5-32-544",
        ],
    ],
)
def test_cli_preserves_scoped_nodes_and_edge_endpoints(cli_run, candidate_data, ids):
    import copy

    candidate_data["nodes"] = [
        dict(id=nid, kind="Group", domain="DOMAIN.LOCAL", is_boundary=False) for nid in ids
    ]
    candidate_data["edges"] = [dict(source=ids[0], target=ids[1], kind="MemberOf")]
    baseline = copy.deepcopy(candidate_data)
    baseline["nodes"] = baseline["nodes"][1:]
    baseline["edges"] = []
    process, report = cli_run(candidate_data, baseline)
    assert process.returncode == 1
    assert report["verdict"] == "DISCREPANCY"
    assert report["node_reconciliation"]["candidate_population"]["total"] == 2
    assert report["node_reconciliation"]["overall"]["candidate_only"] == [ids[0]]
    assert report["discrepancy_ledgers"]["member_of_discrepancies"][0]["candidate_only"][0][
        "triple"
    ] == {"source": ids[0], "kind": "MemberOf", "target": ids[1]}


@pytest.mark.parametrize("field,value", [("kind", "Computer"), ("domain", "OTHER.LOCAL")])
def test_cli_node_metadata_mismatch_changes_verdict(
    cli_run, candidate_data, baseline_exact_data, identity_mapping, field, value
):
    baseline_exact_data["nodes"][0][field] = value
    process, report = cli_run(candidate_data, baseline_exact_data, identity_mapping)
    assert process.returncode == 1
    assert report["verdict"] == "DISCREPANCY"
    mismatch = report["node_reconciliation"][f"{field}_mismatches"][0]
    assert mismatch["id"] == "S-1-5-21-500-600-700-1101"
    assert mismatch[f"baseline_{field}"] == value
    assert f"{field}=1" in report["summary"]


def test_cli_documented_case_aliases_match(
    cli_run, candidate_data, baseline_exact_data, identity_mapping
):
    baseline_exact_data["nodes"][0]["kind"] = "user"
    baseline_exact_data["nodes"][0]["domain"] = "domain.local"
    baseline_exact_data["edges"][0]["kind"] = "MEMBEROF"
    process, report = cli_run(candidate_data, baseline_exact_data, identity_mapping)
    assert process.returncode == 0
    assert report["verdict"] == "MATCH"


@pytest.mark.parametrize(
    "field,value",
    [
        ("snapshot_id", None),
        ("snapshot_id", "sha256:" + "2" * 64),
        ("snapshot_id", "invalid"),
        ("comparison_scope", None),
        ("comparison_scope", {"relationship_kinds": ["MemberOf"]}),
        ("source_evidence", None),
        ("export_complete", False),
        ("synthetic", False),
    ],
)
def test_cli_ineligible_inputs_never_match(
    cli_run, candidate_data, baseline_exact_data, identity_mapping, field, value
):
    if value is None:
        baseline_exact_data["meta"].pop(field, None)
    else:
        baseline_exact_data["meta"][field] = value
    process, report = cli_run(candidate_data, baseline_exact_data, identity_mapping, text=True)
    assert process.returncode == 2
    assert report["verdict"] == "NOT_MEASURABLE"
    assert field in report["summary"]
    assert "100% matched" not in process.stdout


@pytest.mark.parametrize(
    "case",
    [
        "root_list",
        "nodes_dict",
        "missing_edges",
        "edges_dict",
        "node_scalar",
        "node_missing_id",
        "node_numeric_id",
        "node_missing_kind",
        "node_missing_domain",
        "node_boundary_string",
        "duplicate_conflict",
        "duplicate_label_conflict",
        "edge_scalar",
        "edge_missing_target",
        "edge_unknown_target",
        "edge_numeric_endpoint",
        "properties_list",
        "labels_empty",
        "provenance_dict",
        "provenance_null",
        "provenance_scalar",
        "provenance_missing_locator",
        "provenance_wrong_snapshot",
        "metadata_list",
        "ambiguous_edges",
        "alias_conflict",
    ],
)
def test_cli_invalid_records_fail_explicitly(
    cli_run, candidate_data, baseline_exact_data, identity_mapping, case
):
    import copy

    base = baseline_exact_data
    if case == "root_list":
        base = []
    elif case == "nodes_dict":
        base["nodes"] = {}
    elif case == "missing_edges":
        del base["edges"]
    elif case == "edges_dict":
        base["edges"] = {}
    elif case == "node_scalar":
        base["nodes"].append("bad")
    elif case == "node_missing_id":
        base["nodes"].append({"kind": "User"})
    elif case == "node_numeric_id":
        base["nodes"][0]["id"] = 42
    elif case == "node_missing_kind":
        del base["nodes"][0]["kind"]
    elif case == "node_missing_domain":
        del base["nodes"][0]["domain"]
    elif case == "node_boundary_string":
        base["nodes"][0]["is_boundary"] = "false"
    elif case.startswith("duplicate_"):
        duplicate = copy.deepcopy(base["nodes"][0])
        duplicate["kind" if case == "duplicate_conflict" else "label"] = "Computer"
        base["nodes"].append(duplicate)
    elif case == "edge_scalar":
        base["edges"].append(7)
    elif case == "edge_missing_target":
        base["edges"].append({"source": base["nodes"][0]["id"], "kind": "MemberOf"})
    elif case == "edge_unknown_target":
        base["edges"][0]["target"] = "S-1-5-21-1-2-3-9999"
    elif case == "edge_numeric_endpoint":
        base["edges"][0]["target"] = 42
    elif case == "properties_list":
        base["nodes"][0]["properties"] = []
    elif case == "labels_empty":
        del base["nodes"][0]["kind"]
        base["nodes"][0]["labels"] = []
    elif case.startswith("provenance_"):
        values = {
            "provenance_dict": {},
            "provenance_null": None,
            "provenance_scalar": ["bad"],
            "provenance_missing_locator": [{}],
            "provenance_wrong_snapshot": [
                {
                    "raw_file": "snapshot:" + "2" * 64 + "/groups.json",
                    "record_id": "x",
                    "attribute": "Members",
                }
            ],
        }
        base["edges"][0]["provenance"] = values[case]
    elif case == "metadata_list":
        base["meta"] = []
    elif case == "ambiguous_edges":
        base["relationships"] = []
    elif case == "alias_conflict":
        base["nodes"][0]["objectid"] = base["nodes"][1]["id"]
    process, report = cli_run(candidate_data, base, identity_mapping, text=True)
    assert process.returncode == 2
    assert report["verdict"] == "INVALID_INPUT"
    assert report["input_validation"]["diagnostics"]
    assert "baseline" in process.stderr
    assert "Traceback" not in process.stderr
    assert "100% matched" not in process.stdout


@pytest.mark.parametrize(
    "mapping", [[], {"x": 42}, {"": "S-1-5-4"}, {"x": ""}, {"x": "BAD"}, {"x": "S-1-5-32-544"}]
)
def test_cli_invalid_mapping_is_diagnostic(cli_run, candidate_data, baseline_exact_data, mapping):
    process, report = cli_run(candidate_data, baseline_exact_data, mapping)
    assert process.returncode == 2
    assert report["verdict"] == "INVALID_INPUT"
    assert "mapping" in process.stderr


@pytest.mark.parametrize("conflict", [False, True])
def test_cli_mapping_collision_never_overwrites(
    cli_run, candidate_data, baseline_exact_data, identity_mapping, conflict
):
    import copy

    duplicate = copy.deepcopy(baseline_exact_data["nodes"][0])
    duplicate["id"] = "ALIAS-ALICE"
    if conflict:
        duplicate["kind"] = "Computer"
    baseline_exact_data["nodes"].append(duplicate)
    identity_mapping["ALIAS-ALICE"] = "S-1-5-21-500-600-700-1101"
    process, report = cli_run(candidate_data, baseline_exact_data, identity_mapping)
    assert process.returncode == 2
    assert report["verdict"] == "INVALID_INPUT"
    assert "collision" in process.stderr


def test_cli_missing_mapping_entry_is_unresolved(
    cli_run, candidate_data, baseline_exact_data, identity_mapping
):
    del identity_mapping["DOMAIN.LOCAL-S-1-5-21-500-600-700-1101"]
    process, report = cli_run(candidate_data, baseline_exact_data, identity_mapping)
    assert process.returncode == 2
    assert report["verdict"] == "INVALID_INPUT"
    assert "unresolved" in process.stderr


def test_cli_out_of_scope_relationships_are_observations(
    cli_run, candidate_data, baseline_exact_data, identity_mapping
):
    for kind in ["Contains", "CustomRelation"]:
        baseline_exact_data["edges"].append(
            dict(
                source=baseline_exact_data["nodes"][0]["id"],
                target=baseline_exact_data["nodes"][4]["id"],
                kind=kind,
            )
        )
    process, report = cli_run(candidate_data, baseline_exact_data, identity_mapping)
    assert process.returncode == 0
    tr = report["triple_reconciliation"]
    assert tr["overall"]["intersection_count"] == 13
    assert tr["baseline_multiplicity"]["stored_edges"] == 13
    assert tr["out_of_scope"]["baseline"]["stored_edges"] == 2
    assert set(tr["out_of_scope"]["baseline"]["by_kind"]) == {"Contains", "CustomRelation"}
    assert tr["out_of_scope"]["baseline"]["reason"]
    assert report["verdict"] == "MATCH"
    baseline_exact_data["edges"].pop(0)
    process, report = cli_run(candidate_data, baseline_exact_data, identity_mapping)
    assert process.returncode == 1
    assert report["triple_reconciliation"]["overall"]["candidate_only_count"] == 1


def test_cli_exports_all_differences_with_available_references(cli_run, candidate_data):
    import copy

    users = [
        dict(id=f"S-1-5-21-1-2-3-{1000 + i}", kind="User", domain="D.LOCAL", is_boundary=False)
        for i in range(12)
    ]
    group = dict(id="S-1-5-21-1-2-3-2000", kind="Group", domain="D.LOCAL", is_boundary=False)
    candidate_data["nodes"] = users + [group]
    provenance = {
        "raw_file": "synthetic://members.json",
        "record_id": "group-2000",
        "attribute": "Members[].MemberId",
        "collector": "synthetic/47",
        "timestamp": "2026-10-01T00:00:00Z",
        "timestamp_status": "observed",
        "evidence_type": "positive",
    }
    candidate_data["edges"] = [
        dict(
            id=f"edge-{i}",
            source=user["id"],
            target=group["id"],
            kind="MemberOf",
            provenance=[provenance],
        )
        for i, user in enumerate(users)
    ]
    baseline = copy.deepcopy(candidate_data)
    baseline["edges"] = []
    process, report = cli_run(candidate_data, baseline, text=True)
    assert process.returncode == 1
    assert "Candidate only (12)" in process.stdout
    overall = report["triple_reconciliation"]["overall"]
    assert overall["candidate_only_count"] == 12
    assert len(overall["candidate_only"]) == 12
    assert len(overall["candidate_only_samples"]) == 10
    differences = report["discrepancy_ledgers"]["member_of_discrepancies"][0]["candidate_only"]
    assert len(differences) == 12
    assert {item["triple"]["source"] for item in differences} == {
        f"S-1-5-21-1-2-3-{1000 + i}" for i in range(12)
    }
    item = next(d for d in differences if d["triple"]["source"].endswith("-1011"))
    assert item["references"][0]["edge_id"] == "edge-11"
    assert item["references"][0]["record_pointer"] == "/edges/11"
    assert item["references"][0]["provenance"] == [provenance]
    assert item["reason_status"] == "unresolved"
    candidate_data["edges"] = []
    baseline["edges"] = [dict(source=users[0]["id"], target=group["id"], kind="MemberOf")]
    _, report = cli_run(candidate_data, baseline)
    item = report["discrepancy_ledgers"]["member_of_discrepancies"][0]["baseline_only"][0]
    assert item["references"][0]["provenance"] is None
    assert item["evidence_status"] == "not_measurable"


@pytest.mark.parametrize("absence", ["missing", "empty", "partial"])
def test_cli_evidence_counts_never_fall_back_to_edges(
    cli_run, candidate_data, baseline_exact_data, identity_mapping, absence
):
    if absence == "empty":
        for edge in baseline_exact_data["edges"]:
            edge["provenance"] = []
    if absence == "partial":
        baseline_exact_data["edges"][0]["provenance"] = candidate_data["edges"][0]["provenance"]
    process, report = cli_run(candidate_data, baseline_exact_data, identity_mapping)
    assert process.returncode == 0
    cand = report["triple_reconciliation"]["candidate_multiplicity"]
    base = report["triple_reconciliation"]["baseline_multiplicity"]
    assert (cand["stored_edges"], cand["unique_triples"], cand["stored_evidence_occurrences"]) == (
        13,
        13,
        14,
    )
    assert base["stored_edges"] == 13
    assert base["stored_evidence_occurrences"] is None
    assert base["evidence_status"] == "not_measurable"
    assert base["evidence_reason"]


def test_cli_exact_duplicate_nodes_are_disclosed(
    cli_run, candidate_data, baseline_exact_data, identity_mapping
):
    import copy

    baseline_exact_data["nodes"].append(copy.deepcopy(baseline_exact_data["nodes"][0]))
    process, report = cli_run(candidate_data, baseline_exact_data, identity_mapping)
    assert process.returncode == 0
    assert report["input_validation"]["baseline"]["duplicate_node_records"] == 1
    assert report["node_reconciliation"]["baseline_population"]["total"] == 10


@pytest.mark.parametrize(
    "raw", ['{"nodes": [], "nodes": []}', '{"meta": {"snapshot_id": NaN}}', "{"]
)
def test_cli_rejects_lossy_or_invalid_json(tmp_path, raw):
    import subprocess
    import sys

    baseline = tmp_path / "baseline.json"
    if raw != "{":
        key = "nodes" if "nodes" in raw else "snapshot_id"
        injected = '"nodes": [], ' if key == "nodes" else '"snapshot_id": NaN, '
        raw = CANDIDATE_PATH.read_text(encoding="utf-8").replace(
            '"' + key + '":', injected + '"' + key + '":', 1
        )
    baseline.write_text(raw, encoding="utf-8")
    process = subprocess.run(
        [
            sys.executable,
            str(FIXTURES_DIR.parents[2] / "scripts/reconcile_graph_baseline.py"),
            "--candidate",
            str(CANDIDATE_PATH),
            "--baseline",
            str(baseline),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert process.returncode == 2
    assert "Error reading baseline JSON" in process.stderr
    assert "Traceback" not in process.stderr
    assert "MATCH" not in process.stdout


@pytest.mark.parametrize(
    "case",
    [
        "boundary_alias",
        "reason_object",
        "reason_null",
        "derivation_string",
        "direct_memberof_derivation",
        "provenance_types",
    ],
)
def test_cli_review_followups_reject_bad_declared_evidence(
    cli_run, candidate_data, baseline_exact_data, identity_mapping, case
):
    if case == "boundary_alias":
        baseline_exact_data["nodes"][0]["boundary"] = 0
    elif case in {"reason_object", "reason_null"}:
        baseline_exact_data["meta"]["status"] = "not_measurable"
        baseline_exact_data["meta"]["reason"] = (
            {"why": "pending"} if case == "reason_object" else None
        )
    elif case == "derivation_string":
        baseline_exact_data["edges"][0]["derivation"] = "bad"
    elif case == "direct_memberof_derivation":
        baseline_exact_data["edges"][0]["derivation"] = {
            "version": "1.1.0",
            "kind": "nested_membership",
            "paths": [],
        }
    elif case == "provenance_types":
        candidate_data["edges"][0]["provenance"][0].update(
            timestamp={}, collector=7, evidence_type="rejected"
        )
    process, report = cli_run(candidate_data, baseline_exact_data, identity_mapping)
    assert process.returncode == 2
    assert report["verdict"] == "INVALID_INPUT"
    assert report["input_validation"]["diagnostics"]
    assert "Traceback" not in process.stderr


def test_cli_accepts_actual_parser_lineage_and_exports_its_difference(
    cli_run, tmp_path, candidate_data
):
    import copy
    import subprocess
    import sys

    evidence = json.loads((FIXTURES_DIR / "parser_cli_evidence.json").read_text(encoding="utf-8"))
    command = evidence["rich_command"][:]
    command[0] = sys.executable
    output = tmp_path / "rich.json"
    command[command.index("--output") + 1] = str(output)
    process = subprocess.run(
        command, cwd=FIXTURES_DIR.parents[2], capture_output=True, text=True, check=False
    )
    assert process.returncode == 0, process.stderr
    graph = json.loads(output.read_text(encoding="utf-8"))
    graph["metadata"].update(
        synthetic=True,
        export_complete=True,
        source_evidence="synthetic rich CLI manifest",
        comparison_scope=candidate_data["metadata"]["comparison_scope"],
    )
    baseline = copy.deepcopy(graph)
    process, report = cli_run(graph, baseline)
    assert process.returncode == 0
    assert report["node_reconciliation"]["overall"]["intersection_count"] == 6
    assert report["triple_reconciliation"]["overall"]["intersection_count"] == 10
    source, target = "S-1-5-21-4100-4200-4300-1101", "S-1-5-21-4100-4200-4300-3101"
    baseline["edges"] = [
        e
        for e in baseline["edges"]
        if (e["source"], e["kind"], e["target"]) != (source, "AdminTo", target)
    ]
    process, report = cli_run(graph, baseline)
    assert process.returncode == 1
    item = report["discrepancy_ledgers"]["other_discrepancies"][0]["candidate_only"][0]
    assert item["triple"] == {"source": source, "kind": "AdminTo", "target": target}
    lineage = item["references"][0]["derivation"]
    assert [step["operation"] for step in lineage["paths"][0]["steps"]] == [
        "effective_membership",
        "effective_membership",
        "host_local_membership",
    ]
    assert item["references"][0]["provenance_refs"]
    assert (
        item["references"][0]["provenance"]
        == evidence["rich_output_selection"]["AdminTo"]["provenance"]
    )
