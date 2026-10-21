"""Unit tests for EDA Graph Attack Surface analysis functions (Refs #56, #57, #59)."""

from __future__ import annotations

import json
from pathlib import Path

import networkx as nx
import pytest

from scripts.eda_dataset_analysis import (
    audit_data_quality,
    build_cross_dataset_normalized_comparison,
    build_networkx_graph,
    classify_canrdp_evidence,
    compare_collector_bias,
    compute_connectivity_metrics,
    compute_group_nesting_pathology,
    compute_path_redundancy,
    compute_privilege_concentration,
    compute_reachability_metrics,
    compute_relationship_mixing,
    compute_structural_outliers,
    parse_v3_dataset,
    parse_v4_dataset,
    preserve_historical_sections,
    reconcile_raw_records,
    summarize_seamless_host_access,
)


@pytest.fixture
def sample_graph():
    """Build a synthetic graph with known topology for unit testing."""
    nodes = {
        "U_ALICE": {"kind": "User", "name": "ALICE@CORP.LOCAL", "admincount": False},
        "U_BOB": {"kind": "User", "name": "BOB@CORP.LOCAL", "admincount": False},
        "G_HELP": {"kind": "Group", "name": "HELPDESK@CORP.LOCAL", "admincount": False},
        "G_DA": {"kind": "Group", "name": "DOMAIN ADMINS@CORP.LOCAL", "admincount": True},
        "C_DC": {"kind": "Computer", "name": "DC01.CORP.LOCAL", "admincount": False},
    }

    G_multi = nx.MultiDiGraph()
    G_di = nx.DiGraph()

    for n, attrs in nodes.items():
        G_multi.add_node(n, **attrs)
        G_di.add_node(n, **attrs)

    G_multi.add_edge("U_ALICE", "G_HELP", kind="MemberOf")
    G_di.add_edge("U_ALICE", "G_HELP", kind="MemberOf")

    G_multi.add_edge("G_HELP", "G_DA", kind="MemberOf")
    G_di.add_edge("G_HELP", "G_DA", kind="MemberOf")

    G_multi.add_edge("U_BOB", "G_DA", kind="GenericAll")
    G_di.add_edge("U_BOB", "G_DA", kind="GenericAll")

    G_multi.add_edge("G_DA", "C_DC", kind="AdminTo")
    G_di.add_edge("G_DA", "C_DC", kind="AdminTo")

    return G_multi, G_di, nodes


def test_compute_connectivity_metrics(sample_graph):
    _, G_di, _ = sample_graph
    metrics = compute_connectivity_metrics(G_di)

    assert metrics["wcc"]["count"] == 1
    assert metrics["wcc"]["giant_component_size"] == 5
    assert metrics["wcc"]["giant_component_ratio"] == 100.0
    assert metrics["node_roles"]["source"]["count"] == 2
    assert metrics["node_roles"]["sink"]["count"] == 1
    assert metrics["node_roles"]["transit"]["count"] == 2
    assert "clustering_coefficient" in metrics
    assert "diameter" in metrics


def test_compute_reachability_metrics(sample_graph):
    _, G_di, nodes = sample_graph

    # Add a non-principal node (OU) that can reach target G_DA
    G_di.add_node("OU_HR", kind="OU", name="HR_OU")
    nodes["OU_HR"] = {"kind": "OU", "name": "HR_OU", "admincount": False}
    G_di.add_edge("OU_HR", "G_DA", kind="GenericAll")

    metrics = compute_reachability_metrics(G_di, nodes, target_sids=["G_DA"])

    # Total graph nodes reachable is 4 (U_ALICE, G_HELP, U_BOB, OU_HR)
    assert metrics["reachable_graph_nodes_count"] == 4
    # Reachable security principals is strictly 3 (U_ALICE, G_HELP, U_BOB)
    assert metrics["reachable_principal_count"] == 3
    assert "reachable_non_target_principal_percentage" in metrics
    assert "reachable_graph_nodes_percentage" in metrics
    assert "reachable_non_target_graph_nodes_percentage" in metrics
    assert "reachable_all_graph_nodes_percentage" in metrics
    assert metrics["non_target_graph_nodes_count"] == 5
    assert metrics["total_graph_nodes_count"] == 6
    # 3 out of 4 non-target principals (ALICE, BOB, HELP reach G_DA; C_DC is sink)
    assert metrics["reachable_non_target_principal_percentage"] == 75.0
    # 4 out of 5 non-target graph nodes reach G_DA (ALICE, BOB, HELP, OU_HR)
    assert metrics["reachable_graph_nodes_percentage"] == 80.0
    assert metrics["reachable_non_target_graph_nodes_percentage"] == 80.0
    # 4 out of 6 all graph nodes reach G_DA
    assert metrics["reachable_all_graph_nodes_percentage"] == 66.67
    assert metrics["by_class"]["User"]["count"] == 2
    assert metrics["by_class"]["Group"]["count"] == 1
    assert metrics["by_class"]["Computer"]["count"] == 0
    assert "avg_tier0_targets_reachable" in metrics["by_class"]["User"]
    assert metrics["shortest_hop_distribution"]["min"] == 1
    assert metrics["shortest_hop_distribution"]["max"] == 2


def test_compute_privilege_concentration(sample_graph):
    G_multi, _, nodes = sample_graph
    metrics = compute_privilege_concentration(G_multi, nodes)

    assert "gini_coefficients" in metrics
    assert "out_degree" in metrics["gini_coefficients"]
    assert "privileged_control_out_degree" in metrics["gini_coefficients"]
    assert "top_shares" in metrics
    assert "privileged_control_concentration" in metrics
    # GenericAll, AdminTo
    assert metrics["privileged_control_concentration"]["total_control_edges"] == 2
    assert len(metrics["top_10_hubs"]) <= 5
    assert len(metrics["lorenz_curve"]) == 11
    assert "degree_distribution" in metrics
    assert "description" in metrics


def test_compute_relationship_mixing(sample_graph):
    G_multi, _, nodes = sample_graph
    mixing = compute_relationship_mixing(G_multi, nodes)

    assert len(mixing) >= 3
    edge_kinds = {m["edge_kind"] for m in mixing}
    assert "MemberOf" in edge_kinds
    assert "GenericAll" in edge_kinds


def test_compute_group_nesting_pathology():
    # DAG with shortcut edge: G1 -> G2 -> G3 and G1 -> G3
    subgraph = nx.DiGraph()
    subgraph.add_nodes_from(["G1", "G2", "G3"])
    subgraph.add_edge("G1", "G2", kind="MemberOf")
    subgraph.add_edge("G2", "G3", kind="MemberOf")
    # shortcut edge: shortest path to G3 is 1, longest chain is 2
    subgraph.add_edge("G1", "G3", kind="MemberOf")

    nodes = {
        "G1": {"kind": "Group"},
        "G2": {"kind": "Group"},
        "G3": {"kind": "Group"},
    }

    metrics = compute_group_nesting_pathology(subgraph, nodes)
    assert metrics["is_dag"] is True
    assert metrics["cycles_count"] == 0
    # Longest nesting chain from G1 is 2 (G1 -> G2 -> G3), NOT shortest path 1
    assert metrics["depth_stats"]["max_depth"] == 2
    assert metrics["depth_stats"]["total_nested_groups"] == 2
    assert metrics["depth_stats"]["computation_method"] == "longest_nesting_chain_dag_dp"

    # Cyclic group structure: G1 -> G2 -> G1
    cyclic = nx.DiGraph()
    cyclic.add_nodes_from(["G1", "G2"])
    cyclic.add_edge("G1", "G2", kind="MemberOf")
    cyclic.add_edge("G2", "G1", kind="MemberOf")
    cyc_metrics = compute_group_nesting_pathology(cyclic, nodes)
    assert cyc_metrics["is_dag"] is False
    assert cyc_metrics["cycles_count"] >= 1
    assert cyc_metrics["depth_stats"]["computation_method"] == "cyclic_graph_unsupported"


def test_compute_path_redundancy(sample_graph):
    _, G_di, nodes = sample_graph
    pairs = [("U_ALICE", "G_DA")]
    redundancy = compute_path_redundancy(G_di, nodes, sample_pairs=pairs)

    assert len(redundancy) == 1
    assert redundancy[0]["shortest_hops"] == 2
    assert redundancy[0]["node_disjoint_paths_count"] == 1
    assert redundancy[0]["edge_disjoint_paths_count"] == 1
    assert redundancy[0]["capped_at"] == 20
    assert redundancy[0]["truncated"] is False
    assert "description" in redundancy[0]


def test_compute_structural_outliers(sample_graph):
    G_multi, _, nodes = sample_graph
    outliers = compute_structural_outliers(G_multi, nodes)

    assert (
        outliers["boundary_note"]
        == "Structural topological anomalies only; does not imply malicious activity."
    )
    assert "out_degree" in outliers
    assert "in_degree" in outliers
    assert "privilege_count" in outliers
    assert "nesting_behavior" in outliers
    assert "session_count" in outliers
    assert outliers["privilege_count"]["metric"] == "privilege_count"
    assert outliers["nesting_behavior"]["metric"] == "group_member_count"
    assert outliers["session_count"]["status"] == "not_measurable_from_snapshot"


@pytest.mark.parametrize(
    ("rdu", "allow", "deny", "completeness", "status", "materialize"),
    [
        ("positive", "unknown", "unknown", "unknown", "unknown", False),
        ("unknown", "positive", "known-negative", "complete", "unknown", False),
        ("positive", "positive", "positive", "complete", "known-negative", False),
        ("positive", "positive", "known-negative", "complete", "positive", True),
        ("positive", "positive", "known-negative", "unknown", "unknown", False),
    ],
)
def test_classify_canrdp_requires_complete_composite_evidence(
    rdu, allow, deny, completeness, status, materialize
):
    result = classify_canrdp_evidence(rdu, allow, deny, completeness=completeness)

    assert result["status"] == status
    assert result["materialize"] is materialize


def test_seamless_host_access_report_separates_raw_rdu_from_canrdp():
    computers = [
        {"RemoteDesktopUsers": [{"MemberId": "U1"}], "Sessions": []},
        {"RemoteDesktopUsers": [], "Sessions": []},
        {},
    ]

    report = summarize_seamless_host_access(computers)

    rdu = report["raw_primitives"]["RemoteDesktopUsers_raw_memberships"]
    local_admins = report["raw_primitives"]["LocalAdmins_raw_memberships"]
    ps_remote = report["raw_primitives"]["PSRemoteUsers_raw_memberships"]
    sessions = report["raw_primitives"]["Sessions_raw_observations"]
    canrdp = report["effective_relationships"]["CanRDP"]
    assert rdu["raw_observation_count"] == 1
    assert rdu["hosts_with_positive_observation"] == 1
    assert rdu["empty_or_unobserved_hosts"] == 2
    assert rdu["collection_completeness_status"] == "not_measurable_from_snapshot"
    assert local_admins["raw_observation_count"] == 0
    assert local_admins["empty_or_unobserved_hosts"] == 3
    assert ps_remote["raw_observation_count"] == 0
    assert ps_remote["empty_or_unobserved_hosts"] == 3
    assert sessions["raw_observation_count"] == 0
    assert sessions["empty_or_unobserved_hosts"] == 3
    for primitive in (local_admins, ps_remote, sessions):
        assert primitive["collection_completeness_status"] == "not_measurable_from_snapshot"
        assert "canonical relationship absence cannot be concluded" in primitive["note"]
    assert canrdp["verified_effective_edges_count"] is None
    assert canrdp["materialized_edges_count"] == 0
    assert canrdp["status"] == "unknown"


def test_build_networkx_graph_does_not_materialize_raw_rdu_as_canrdp(tmp_path: Path):
    computers = tmp_path / "20210920_computers.json"
    computers.write_text(
        json.dumps(
            {
                "meta": {"version": 3},
                "computers": [
                    {
                        "ObjectIdentifier": "C1.CORP.LOCAL",
                        "RemoteDesktopUsers": [{"MemberId": "U1@CORP.LOCAL"}],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    graph, _, _ = build_networkx_graph(tmp_path)

    assert not any(data.get("kind") == "CanRDP" for *_edge, data in graph.edges(data=True))


def test_audit_data_quality(tmp_path: Path):
    """Test data quality audit on real synthetic files and verify error handling."""
    # Non-existent directory raises FileNotFoundError
    with pytest.raises(FileNotFoundError):
        audit_data_quality(tmp_path / "non_existent_dir")

    # Empty directory raises FileNotFoundError
    empty_dir = tmp_path / "empty_dir"
    empty_dir.mkdir()
    with pytest.raises(FileNotFoundError):
        audit_data_quality(empty_dir)

    # Minimal real dataset
    data_dir = tmp_path / "test_data"
    data_dir.mkdir()

    users_file = data_dir / "20210920_users.json"
    users_data = {
        "meta": {"version": 3},
        "users": [
            {
                "ObjectIdentifier": "U1@CORP.LOCAL",
                "Properties": {
                    "serviceprincipalnames": ["HTTP/app.corp.local"],
                    "lastlogontimestamp": 1600000000,
                },
            },
            {
                "ObjectIdentifier": "U2@CORP.LOCAL",
                "Properties": {
                    "serviceprincipalnames": [],
                    "lastlogontimestamp": 0,
                },
            },
        ],
    }
    users_file.write_text(json.dumps(users_data), encoding="utf-8")

    computers_file = data_dir / "20210920_computers.json"
    computers_data = {
        "meta": {"version": 3},
        "computers": [
            {
                "ObjectIdentifier": "C1.CORP.LOCAL",
                "PrimaryGroupSid": "S-1-5-21-1-2-3-516",
                "Properties": {
                    "operatingsystem": "Windows Server 2022",
                    "haslaps": False,
                    "lastlogontimestamp": 1600000000,
                },
                "Sessions": [],
                "LocalAdmins": [{"MemberId": "U1@CORP.LOCAL"}],
            }
        ],
    }
    computers_file.write_text(json.dumps(computers_data), encoding="utf-8")

    groups_file = data_dir / "20210920_groups.json"
    groups_data = {
        "meta": {"version": 3},
        "groups": [
            {
                "ObjectIdentifier": "G1@CORP.LOCAL",
                "Members": [{"MemberId": "U1@CORP.LOCAL"}],
                "Aces": [],
            }
        ],
    }
    groups_file.write_text(json.dumps(groups_data), encoding="utf-8")

    audit = audit_data_quality(data_dir)
    assert audit["valid_parsed"] == 4
    assert audit["unique_nodes_materialized"] == 4
    assert audit["dropped_records"] == 0
    assert audit["duplicate_detection"]["duplicate_ObjectIdentifiers"] == 0
    assert audit["referential_integrity"]["integrity_percentage"] == 100.0
    assert audit["missingness_taxonomy"]["servicePrincipalNames"]["with_spn"] == 1
    assert audit["missingness_taxonomy"]["servicePrincipalNames"]["without_spn"] == 1
    assert (
        "does not establish attack applicability"
        in audit["missingness_taxonomy"]["servicePrincipalNames"]["classification"]
    )
    assert (
        "cause not established"
        in audit["missingness_taxonomy"]["operatingSystem"]["classification"]
    )
    assert (
        "activity unknown"
        in audit["missingness_taxonomy"]["lastLogonTimestamp_User"]["classification"]
    )
    assert audit["missingness_taxonomy"]["haslaps"]["observed_false"] == 1
    assert audit["missingness_taxonomy"]["haslaps"]["observed_true"] == 0
    assert audit["missingness_taxonomy"]["haslaps"]["missing_or_absent"] == 0
    assert audit["missingness_taxonomy"]["haslaps"]["percentage_observed_false"] == 100.0
    assert "collector observed false" in audit["missingness_taxonomy"]["haslaps"]["classification"]
    assert audit["missingness_taxonomy"]["LocalAdmins"]["populated"] == 1
    assert audit["missingness_taxonomy"]["Sessions"]["populated"] == 0
    assert "unknown_rate_by_edge_type" in audit
    assert "MemberOf" in audit["unknown_rate_by_edge_type"]
    assert "AdminTo" in audit["unknown_rate_by_edge_type"]
    assert (
        audit["unknown_rate_by_edge_type"]["MemberOf"]["collection_completeness_status"]
        == "not_measurable_from_snapshot"
    )
    assert audit["unknown_rate_by_edge_type"]["MemberOf"]["positive_raw_evidence_rate"] == 100.0
    assert audit["unknown_rate_by_edge_type"]["MemberOf"]["field_presence_rate"] == 100.0
    assert (
        audit["unknown_rate_by_edge_type"]["MemberOf"]["unknown_rate"]
        == "not_measurable_from_snapshot"
    )
    assert audit["unknown_rate_by_edge_type"]["AdminTo"]["status"] == "endpoint_partially_observed"
    assert audit["unknown_rate_by_edge_type"]["AdminTo"]["extracted_edges_count"] == 1
    assert "collector_error_and_access_denied" in audit
    assert audit["collector_error_and_access_denied"]["status"] == "not_measurable_from_snapshot"
    assert "missingness_concentration" in audit
    assert "not collection completeness" in audit["missingness_concentration"]["boundary_note"]
    assert "by_tier_and_role" in audit["missingness_concentration"]
    assert "by_privilege_level" in audit["missingness_concentration"]
    assert "by_ou" in audit["missingness_concentration"]
    assert "distinct_parent_ous_count" in audit["missingness_concentration"]["by_ou"]
    assert "domain_controllers_ou" in audit["missingness_concentration"]["by_ou"]
    assert "non_dc_workstation_ous_summary" in audit["missingness_concentration"]["by_ou"]

    groups_data["groups"].append({"ObjectIdentifier": "G2@CORP.LOCAL", "Members": [], "Aces": []})
    groups_file.write_text(json.dumps(groups_data), encoding="utf-8")
    empty_audit = audit_data_quality(data_dir)["unknown_rate_by_edge_type"]
    memberof = empty_audit["MemberOf"]
    assert memberof["source_entities_without_observed_evidence"] == 1
    assert memberof["raw_nonobservation_rate"] == 50.0
    assert memberof["collection_completeness_status"] == "not_measurable_from_snapshot"
    assert "relationship_absence_rate" not in memberof
    assert "actual empty" not in memberof["note"]
    assert "canonical relationship absence cannot be established" in memberof["note"]
    for kind in ("GenericAll", "WriteDacl", "ForceChangePassword"):
        assert "relationship_absence_rate" not in empty_audit[kind]
        assert "canonical" in empty_audit[kind]["note"]
    assert empty_audit["ForceChangePassword"]["status"] == "directory_raw_evidence_unobserved"


def test_notebook_data_quality_cell_reads_current_report_schema(capsys):
    """The published notebook must render the manifest-bound report without stale keys."""
    root = Path(__file__).resolve().parents[1]
    notebook = json.loads((root / "notebooks/eda_dataset_analysis.ipynb").read_text())
    report = json.loads((root / "reports/eda_summary.json").read_text())
    cell = next(cell for cell in notebook["cells"] if cell.get("id") == "cell_007")
    namespace = {
        "audit_data_quality": lambda path, manifest: report["SEAMLESS"]["data_quality_audit"],
        "seamless_path": root / "data/raw/SEAMLESS",
        "seamless_manifest": {},
    }

    exec("".join(cell["source"]), namespace)

    output = capsys.readouterr().out
    assert "Positive raw/evidence observations" in output
    assert "MemberOf: positive_raw_evidence=99.27%" in output
    assert "CanRDP: positive_raw_evidence=n/a" in output
    assert "completeness=not_measurable_from_snapshot" in output


def test_compare_collector_bias_duplicates(tmp_path: Path):
    """Test collector bias comparison on set of triples.

    Verifies duplicates do not distort union.
    """
    sh_dir = tmp_path / "sh"
    py_dir = tmp_path / "py"
    sh_dir.mkdir()
    py_dir.mkdir()

    # Empty comparison
    res_empty = compare_collector_bias(tmp_path / "empty1", tmp_path / "empty2")
    assert res_empty["Total_SharpHound_edges"] == 0
    assert res_empty["Overall_Jaccard_Similarity"] == 0.0

    # SharpHound file with duplicate edge in raw export
    sh_group = {
        "meta": {"version": 3},
        "groups": [
            {
                "ObjectIdentifier": "G_TARGET",
                "Members": [
                    {"MemberId": "U_ALICE"},
                    {"MemberId": "U_ALICE"},  # duplicate triple
                ],
            }
        ],
    }
    (sh_dir / "test_groups.json").write_text(json.dumps(sh_group), encoding="utf-8")

    # BloodHound.py file with two distinct edges
    py_group = {
        "meta": {"version": 3},
        "groups": [
            {
                "ObjectIdentifier": "G_TARGET",
                "Members": [
                    {"MemberId": "U_ALICE"},
                    {"MemberId": "U_BOB"},
                ],
            }
        ],
    }
    (py_dir / "test_groups.json").write_text(json.dumps(py_group), encoding="utf-8")

    res = compare_collector_bias(sh_dir, py_dir)
    assert res["Total_SharpHound_edges"] == 1  # deduplicated to set
    assert res["Total_BloodHound.py_edges"] == 2
    assert res["Common_edges"] == 1
    assert res["Union_edges"] == 2
    assert res["Overall_Jaccard_Similarity"] == 0.5
    breakdown = res["Per_edge_kind_breakdown"]["MemberOf"]
    assert breakdown["SharpHound"] == 1
    assert breakdown["BloodHound.py"] == 2
    assert breakdown["Common"] == 1
    assert breakdown["Union"] == 2
    assert breakdown["Jaccard"] == 0.5


def test_reconcile_raw_records_order_invariance():
    record_stub = {
        "ObjectIdentifier": "SEAMLESS.INTERNAL-S-1-5-32-545",
        "Properties": {
            "name": "USERS@SEAMLESS.INTERNAL",
            "admincount": False,
            "description": "Beta Conflict Description",
        },
        "Members": [],
    }

    record_full = {
        "ObjectIdentifier": "SEAMLESS.INTERNAL-S-1-5-32-545",
        "Properties": {
            "name": "USERS@SEAMLESS.INTERNAL",
            "highvalue": True,
            "description": "Alpha Conflict Description",
        },
        "Members": [{"MemberId": "U1@SEAMLESS.INTERNAL"}, {"MemberId": "U2@SEAMLESS.INTERNAL"}],
        "Aces": [{"PrincipalSID": "S-1", "RightName": "GenericAll", "AceType": "Allow"}],
    }

    # Input order 1: full then stub
    reconciled_1, dropped_1 = reconcile_raw_records([record_full, record_stub])
    # Input order 2: stub then full
    reconciled_2, dropped_2 = reconcile_raw_records([record_stub, record_full])

    assert dropped_1 == 1
    assert dropped_2 == 1

    assert len(reconciled_1) == 1
    assert len(reconciled_2) == 1

    r1 = reconciled_1[0]
    r2 = reconciled_2[0]

    assert r1["ObjectIdentifier"] == r2["ObjectIdentifier"] == "SEAMLESS.INTERNAL-S-1-5-32-545"
    assert r1["Properties"]["admincount"] is False
    assert r1["Properties"]["highvalue"] is True
    assert r2["Properties"]["admincount"] is False
    assert r2["Properties"]["highvalue"] is True

    # Conflicting scalar properties: deterministic tie-break ensures exact equality
    assert r1["Properties"]["description"] == r2["Properties"]["description"]
    assert r1["Properties"]["description"] == "Beta Conflict Description"

    assert len(r1["Members"]) == 2
    assert len(r2["Members"]) == 2

    assert len(r1["Aces"]) == 1
    assert len(r2["Aces"]) == 1


def test_reconcile_raw_records_localgroups_nested_results_union():
    """Verify LocalGroups reconciliation unions nested Results and preserves order invariance."""
    rec1 = {
        "ObjectIdentifier": "COMP1.TEST.LOCAL",
        "Properties": {"name": "COMP1.TEST.LOCAL"},
        "LocalGroups": [
            {
                "ObjectIdentifier": "COMP1.TEST.LOCAL-S-1-5-32-544",
                "Results": [{"ObjectIdentifier": "USER1@TEST.LOCAL", "ObjectType": "User"}],
            }
        ],
    }
    rec2 = {
        "ObjectIdentifier": "COMP1.TEST.LOCAL",
        "Properties": {"name": "COMP1.TEST.LOCAL"},
        "LocalGroups": [
            {
                "ObjectIdentifier": "COMP1.TEST.LOCAL-S-1-5-32-544",
                "Results": [{"ObjectIdentifier": "USER2@TEST.LOCAL", "ObjectType": "User"}],
            }
        ],
    }
    reconciled_1, dropped_1 = reconcile_raw_records([rec1, rec2])
    reconciled_2, dropped_2 = reconcile_raw_records([rec2, rec1])

    assert dropped_1 == 1
    assert dropped_2 == 1
    assert len(reconciled_1) == 1
    assert len(reconciled_2) == 1

    r1_lg = reconciled_1[0]["LocalGroups"]
    r2_lg = reconciled_2[0]["LocalGroups"]
    assert len(r1_lg) == 1
    assert len(r2_lg) == 1

    res1 = [m["ObjectIdentifier"] for m in r1_lg[0]["Results"]]
    res2 = [m["ObjectIdentifier"] for m in r2_lg[0]["Results"]]
    assert res1 == res2 == ["USER1@TEST.LOCAL", "USER2@TEST.LOCAL"]


def test_compare_collector_bias_v4_localgroups_and_sessions(tmp_path: Path):
    sh_dir = tmp_path / "sh"
    py_dir = tmp_path / "py"
    sh_dir.mkdir()
    py_dir.mkdir()

    comp_sh = {
        "meta": {"version": 4},
        "computers": [
            {
                "ObjectIdentifier": "C1.DOMAIN.LOCAL",
                "LocalGroups": [
                    {
                        "ObjectIdentifier": "DOMAIN-S-1-5-32-544",
                        "Results": [{"ObjectIdentifier": "U1@DOMAIN.LOCAL"}],
                    },
                    {
                        "ObjectIdentifier": "DOMAIN-S-1-5-32-555",
                        "Results": [{"ObjectIdentifier": "U2@DOMAIN.LOCAL"}],
                    },
                    {
                        "ObjectIdentifier": "DOMAIN-S-1-5-32-580",
                        "Results": [{"ObjectIdentifier": "U3@DOMAIN.LOCAL"}],
                    },
                ],
                "Sessions": {
                    "Results": [{"UserSID": "U4@DOMAIN.LOCAL"}],
                },
            }
        ],
    }
    (sh_dir / "computers.json").write_text(json.dumps(comp_sh), encoding="utf-8")

    res = compare_collector_bias(sh_dir, py_dir)
    bd = res["Per_edge_kind_breakdown"]
    assert "AdminTo" in bd and bd["AdminTo"]["SharpHound"] == 1
    assert (
        "RemoteDesktopUsers_raw_memberships" in bd
        and bd["RemoteDesktopUsers_raw_memberships"]["SharpHound"] == 1
    )
    assert "CanPSRemote" in bd and bd["CanPSRemote"]["SharpHound"] == 1
    assert "HasSession" in bd and bd["HasSession"]["SharpHound"] == 1


def test_parse_v3_and_v4_dataset_normalized_ratios(tmp_path: Path):
    """Verify parse_v3_dataset and parse_v4_dataset expose density and normalized ratios."""
    v3_dir = tmp_path / "v3"
    v3_dir.mkdir()

    users_file = v3_dir / "20210920_users.json"
    users_file.write_text(
        json.dumps(
            {
                "meta": {"version": 3},
                "users": [
                    {
                        "ObjectIdentifier": "U1@CORP.LOCAL",
                        "Properties": {"admincount": True, "highvalue": True},
                    },
                    {
                        "ObjectIdentifier": "U2@CORP.LOCAL",
                        "Properties": {"admincount": False, "highvalue": False},
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    computers_file = v3_dir / "20210920_computers.json"
    computers_file.write_text(
        json.dumps(
            {
                "meta": {"version": 3},
                "computers": [
                    {
                        "ObjectIdentifier": "C1.CORP.LOCAL",
                        "PrimaryGroupSid": "S-1-5-21-1-2-3-516",
                        "Properties": {"operatingsystem": "Windows Server 2022"},
                        "LocalAdmins": [{"MemberId": "U1@CORP.LOCAL"}],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    groups_file = v3_dir / "20210920_groups.json"
    groups_file.write_text(
        json.dumps(
            {
                "meta": {"version": 3},
                "groups": [
                    {
                        "ObjectIdentifier": "G1@CORP.LOCAL",
                        "Properties": {"admincount": True},
                        "Members": [{"MemberId": "U1@CORP.LOCAL"}],
                        "Aces": [{"PrincipalSID": "U1@CORP.LOCAL", "RightName": "GenericAll"}],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    # Empty files for remaining types
    for kind in ["ous", "gpos", "domains"]:
        (v3_dir / f"20210920_{kind}.json").write_text(
            json.dumps({"meta": {"version": 3}, kind: []}), encoding="utf-8"
        )

    res_v3 = parse_v3_dataset(v3_dir)
    assert "CanRDP" not in res_v3["edge_counts"]
    canrdp_status = res_v3["host_access_semantics"]["effective_relationships"]["CanRDP"]["status"]
    assert canrdp_status == "unknown"
    assert "graph_density" in res_v3
    assert "normalized_ratios" in res_v3
    nr = res_v3["normalized_ratios"]
    assert "privileged_principal_ratio" in nr
    assert "acl_density" in nr
    assert "session_density" in nr
    assert "session_density_status" in nr
    # U1 (admincount=True), G1 (admincount=True) -> 2 out of 4 principals (U1, U2, C1, G1)
    assert nr["privileged_principal_ratio"] == 0.5
    # Edges: MemberOf (1), AdminTo (1), GenericAll (1) -> 3 edges, 1 ACL edge (GenericAll)
    assert nr["acl_density"] == round(1 / 3, 4)
    assert res_v3["graph_density"] == res_v3["density_metrics"]["canonical_directed_simple_density"]
    assert res_v3["multiedge_density"] == res_v3["density_metrics"]["multigraph_edge_intensity"]
    assert "details" in nr
    assert nr["details"]["privileged_principal_ratio"]["numerator"] == 2
    assert nr["details"]["privileged_principal_ratio"]["denominator"] == 4
    assert nr["details"]["acl_density"]["numerator"] == 1
    assert nr["details"]["acl_density"]["denominator"] == 3

    # v4 dataset test
    v4_dir = tmp_path / "v4"
    v4_dir.mkdir()
    v4_users = v4_dir / "users.json"
    v4_users.write_text(
        json.dumps(
            {
                "data": [
                    {
                        "ObjectIdentifier": "U1@CORP.LOCAL",
                        "Properties": {"admincount": True},
                    },
                    {
                        "ObjectIdentifier": "U2@CORP.LOCAL",
                        "Properties": {"admincount": False},
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    v4_comps = v4_dir / "computers.json"
    v4_comps.write_text(
        json.dumps(
            {
                "data": [
                    {
                        "ObjectIdentifier": "C1.CORP.LOCAL",
                        "Properties": {},
                        "Sessions": {"Results": [{"UserSID": "U1@CORP.LOCAL"}]},
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    res_v4 = parse_v4_dataset(v4_dir)
    assert "graph_density" in res_v4
    assert "normalized_ratios" in res_v4
    nr_v4 = res_v4["normalized_ratios"]
    assert nr_v4["session_density_status"] == "measured"
    assert nr_v4["session_density"] > 0
    assert res_v4["graph_density"] == res_v4["density_metrics"]["canonical_directed_simple_density"]
    assert res_v4["multiedge_density"] == res_v4["density_metrics"]["multigraph_edge_intensity"]
    assert "details" in nr_v4
    assert nr_v4["details"]["session_density"]["numerator"] == 1
    assert nr_v4["details"]["session_density"]["unique_computers"] == 1
    assert nr_v4["details"]["session_density"]["unique_users"] == 2
    assert nr_v4["details"]["session_density"]["denominator"] == 2
    assert nr_v4["details"]["session_density"]["value"] == 0.5


def test_preserve_historical_sections_migrates_legacy_raw_canrdp_labels():
    """Preserved reports must not carry legacy raw RDU values under canonical CanRDP."""
    historical = {
        "NORTH": {
            "edge_counts": {"CanRDP": 1, "AdminTo": 2},
            "total_nodes": 10,
            "total_edges": 3,
            "simple_edges": 3,
            "graph_density": 0.033333,
            "multiedge_density": 0.033333,
            "edge_to_node_ratio": 0.3,
            "density_metrics": {
                "simple_edges_numerator": 3,
                "total_edges_numerator": 3,
                "unique_nodes": 10,
                "possible_pairs_denominator": 90,
            },
            "normalized_ratios": {
                "acl_density": 0.6667,
                "details": {"acl_density": {"numerator": 2, "denominator": 3}},
            },
        },
        "ad_sampledata": {
            "edge_counts": {"AdminTo": 1},
            "total_nodes": 2,
            "total_edges": 1,
            "simple_edges": 1,
        },
        "collector_bias_comparison": {
            "Total_SharpHound_edges": 1,
            "Total_BloodHound.py_edges": 0,
            "Common_edges": 0,
            "Union_edges": 1,
            "Per_edge_kind_breakdown": {
                "CanRDP": {
                    "SharpHound": 1,
                    "BloodHound.py": 0,
                    "Common": 0,
                    "Union": 1,
                    "Jaccard": 0.0,
                }
            },
        },
    }
    source = {
        "kind": "git_ref",
        "git_ref": "origin/develop",
        "git_commit": "historical-revision",
        "sha256": "historical-report-sha",
    }

    preserved, metadata = preserve_historical_sections(historical, source)

    north = preserved["NORTH"]
    assert "CanRDP" not in north["edge_counts"]
    assert north["raw_host_access_counts"]["RemoteDesktopUsers_raw_memberships"] == 1
    assert north["raw_host_access_counts"]["CanRDP_verified_effective_edges"] is None
    assert north["total_edges"] == 2
    assert north["simple_edges"] == 2
    assert north["normalized_ratios"]["details"]["acl_density"]["denominator"] == 2
    assert north["preservation_metadata"]["source"] == source

    bias = preserved["collector_bias_comparison"]["Per_edge_kind_breakdown"]
    assert "CanRDP" not in bias
    assert bias["RemoteDesktopUsers_raw_memberships"]["SharpHound"] == 1
    assert (
        "(AdminTo, CanRDP, Enroll)"
        not in preserved["collector_bias_comparison"]["Discrepancy_analysis"]
    )
    assert (
        "RemoteDesktopUsers_raw_memberships"
        in preserved["collector_bias_comparison"]["Discrepancy_analysis"]
    )

    comparison = build_cross_dataset_normalized_comparison(preserved)
    assert comparison["NORTH"]["total_edges"] == 2
    assert metadata["status"] == "scoped_preservation"
    assert metadata["preserved_sections"] == [
        "NORTH",
        "ad_sampledata",
        "collector_bias_comparison",
    ]
