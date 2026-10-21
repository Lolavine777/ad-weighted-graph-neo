"""Validate failures that would corrupt the parser/engine handoff."""

import copy
import json
from pathlib import Path

import pytest
import yaml

from scripts.check_contract import canonical_edge_id, validate_contract, validate_graph
from src.parser import deserialize_graph, serialize_graph

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def contract():
    return yaml.safe_load((ROOT / "configs/contract.yml").read_text(encoding="utf-8"))


@pytest.fixture
def graph():
    return json.loads((ROOT / "data/samples/toy-graph.json").read_text(encoding="utf-8"))


def test_committed_fixture_and_profiles_are_valid(contract, graph):
    validate_graph(graph, contract)
    assert graph["metadata"]["synthetic"] is True


def test_m2_contract_is_frozen_as_accepted(contract):
    contract["status"] = "draft"
    with pytest.raises(ValueError, match="must be accepted"):
        validate_contract(contract)


@pytest.mark.parametrize("weight", [-0.1, 0, float("nan"), float("inf"), True, "1.0", None])
def test_invalid_cost_is_rejected(contract, weight):
    contract["profiles"]["unit"]["weights"]["MemberOf"] = weight
    with pytest.raises(ValueError, match="finite and >= 1.0"):
        validate_contract(contract)


@pytest.mark.parametrize("change", ["missing", "unknown"])
def test_profile_must_cover_exact_edge_kinds(contract, change):
    weights = contract["profiles"]["unit"]["weights"]
    if change == "missing":
        del weights["MemberOf"]
    else:
        weights["UnknownRelation"] = 1
    with pytest.raises(ValueError, match="incomplete/unknown"):
        validate_contract(contract)


def test_draft_cannot_claim_production_readiness(contract):
    contract["profiles"]["unit"]["production_ready"] = True
    with pytest.raises(ValueError, match="not production ready"):
        validate_contract(contract)


@pytest.mark.parametrize("collection", ["nodes", "edges"])
def test_duplicate_identifiers_are_rejected(contract, graph, collection):
    graph[collection].append(copy.deepcopy(graph[collection][0]))
    with pytest.raises(ValueError, match="duplicate id"):
        validate_graph(graph, contract)


@pytest.mark.parametrize("endpoint", ["source", "target"])
def test_dangling_edge_is_rejected(contract, graph, endpoint):
    edge = graph["edges"][0]
    edge[endpoint] = "does-not-exist"
    edge["id"] = canonical_edge_id(edge["source"], edge["target"], edge["kind"])
    with pytest.raises(ValueError, match="dangling endpoint"):
        validate_graph(graph, contract)


def test_parallel_edges_remain_valid(contract, graph):
    edge = copy.deepcopy(graph["edges"][2])
    edge["kind"] = "WriteDacl"
    edge["id"] = canonical_edge_id(edge["source"], edge["target"], edge["kind"])
    graph["edges"].append(edge)
    validate_graph(graph, contract)


@pytest.mark.parametrize("field", ["id", "source", "target", "kind", "weight", "provenance"])
def test_required_edge_fields_cannot_be_omitted(contract, graph, field):
    del graph["edges"][0][field]
    with pytest.raises(ValueError, match=f"missing required field {field}"):
        validate_graph(graph, contract)


def test_schema_version_mismatch_is_rejected(contract, graph):
    graph["metadata"]["contract_version"] = "unsupported"
    with pytest.raises(ValueError, match="version mismatch"):
        validate_graph(graph, contract)


def test_unknown_relation_is_rejected(contract, graph):
    graph["edges"][0]["kind"] = "Unsupported"
    with pytest.raises(ValueError, match="unknown kind"):
        validate_graph(graph, contract)


@pytest.mark.parametrize(
    "node_id",
    [
        "S-1-5-21-1000-2000-3000-1102",
        "10000000-0000-4000-8000-000000000001",
        "domain:20000000-0000-4000-8000-000000000003:S-1-5-32-544",
        "domain:sid:S-1-5-21-111-222-333:S-1-5-32-544",
        "host:20000000-0000-4000-8000-000000000004:S-1-5-18",
    ],
)
def test_canonical_sid_and_guid_are_accepted(contract, graph, node_id):
    if node_id.startswith("domain:sid:"):
        _current_contract_graph(graph)
    graph["nodes"][0]["id"] = node_id
    for edge in graph["edges"]:
        if edge["source"] == "10000000-0000-4000-8000-000000000001":
            edge["source"] = node_id
            edge["id"] = canonical_edge_id(edge["source"], edge["target"], edge["kind"])
    validate_graph(graph, contract)


@pytest.mark.parametrize(
    "node_id",
    [
        "computer-01",
        "s-1-5-21-1000-2000-3000-1101",
        "10000000-0000-4000-8000-00000000000A",
        "{10000000-0000-4000-8000-000000000001}",
        "S-1-5-32-544",
        "S-1-5-18",
        "domain:ALPHA.EXAMPLE:S-1-5-32-544",
        "domain:20000000-0000-4000-8000-00000000000A:S-1-5-32-544",
        "domain:sid:SEAMLESS.INTERNAL:S-1-5-32-544",
        "domain:sid:S-1-5-32-544:S-1-5-32-544",
        "domain:sid:not-a-sid:S-1-5-32-544",
        "domain:sid:S-1-5-21-1-2:S-1-5-32-544",
    ],
)
def test_noncanonical_node_id_is_rejected(contract, graph, node_id):
    graph["nodes"][0]["id"] = node_id
    with pytest.raises(ValueError, match="invalid canonical id"):
        validate_graph(graph, contract)


@pytest.mark.parametrize("value", [True, False, -1, 0, 1, 2])
def test_admincount_accepts_boolean_and_integer(contract, graph, value):
    graph["nodes"][0]["admincount"] = value
    validate_graph(graph, contract)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("enabled", 1, "must be boolean"),
        ("enabled", None, "must be boolean"),
        ("admincount", "true", "must be boolean or integer"),
        ("admincount", 1.5, "must be boolean or integer"),
        ("admincount", None, "must be boolean or integer"),
        ("distinguishedname", "  ", "invalid distinguishedname"),
        ("distinguishedname", None, "invalid distinguishedname"),
        ("domain", "   ", "invalid domain"),
        ("domain", 123, "invalid domain"),
        ("domain", None, "invalid domain"),
    ],
)
def test_optional_node_fields_are_typed(contract, graph, field, value, message):
    graph["nodes"][0][field] = value
    with pytest.raises(ValueError, match=message):
        validate_graph(graph, contract)


def test_node_validation_error_includes_node_identifier(contract, graph):
    node_id = graph["nodes"][0]["id"]
    graph["nodes"][0]["unsupported_prop"] = "val"
    with pytest.raises(ValueError, match=f"node '{node_id}': unsupported fields"):
        validate_graph(graph, contract)


def test_validate_node_accepts_precompiled_patterns(contract, graph):
    from scripts.check_contract import canonical_id_patterns, validate_node

    sid_pattern, guid_pattern, scoped_sid_pattern, scope_required_sid_pattern = (
        canonical_id_patterns(contract)
    )
    validate_node(
        graph["nodes"][0],
        contract,
        sid_pattern=sid_pattern,
        guid_pattern=guid_pattern,
        scoped_sid_pattern=scoped_sid_pattern,
        scope_required_sid_pattern=scope_required_sid_pattern,
    )


def test_scoped_builtin_groups_and_edges_remain_distinct(contract, graph):
    groups = [node for node in graph["nodes"] if node["label"].endswith("-ADMINISTRATORS")]
    group_ids = {node["id"] for node in groups}
    node_ids = {node["id"] for node in graph["nodes"]}
    scope_ids = {node_id.split(":", 2)[1] for node_id in group_ids}
    targets = {edge["target"] for edge in graph["edges"] if edge["target"] in group_ids}

    assert len(group_ids) == 2
    assert scope_ids <= node_ids
    assert targets == group_ids
    validate_graph(graph, contract)


def test_duplicate_scoped_identity_is_rejected(contract, graph):
    scoped_group = next(node for node in graph["nodes"] if node["label"] == "ALPHA-ADMINISTRATORS")
    graph["nodes"].append(copy.deepcopy(scoped_group))
    with pytest.raises(ValueError, match="duplicate id"):
        validate_graph(graph, contract)


def test_undeclared_node_field_is_rejected(contract, graph):
    graph["nodes"][0]["objectsid"] = "S-1-5-21-1000-2000-3000-1101"
    with pytest.raises(ValueError, match="unsupported fields"):
        validate_graph(graph, contract)


@pytest.mark.parametrize("field", ["id", "kind", "label", "domain", "is_boundary"])
def test_required_node_fields_cannot_be_omitted(contract, graph, field):
    del graph["nodes"][0][field]
    with pytest.raises(ValueError, match=f"missing required field {field}"):
        validate_graph(graph, contract)


def test_contract_rejects_missing_node_field_types(contract):
    del contract["schema"]["node_field_types"]["domain"]
    with pytest.raises(ValueError, match="node_field_types must cover exactly"):
        validate_contract(contract)


def test_contract_rejects_unsupported_node_field_type(contract):
    contract["schema"]["node_field_types"]["enabled"] = "unsupported_type"
    with pytest.raises(ValueError, match="unsupported type"):
        validate_contract(contract)


def test_contract_rejects_non_string_node_field_type_cleanly(contract):
    contract["schema"]["node_field_types"]["enabled"] = []
    with pytest.raises(ValueError, match="unsupported type"):
        validate_contract(contract)


def test_contract_rejects_core_field_type_alteration(contract):
    contract["schema"]["node_field_types"]["id"] = "boolean"
    with pytest.raises(ValueError, match="core node field 'id' must have type 'canonical_id'"):
        validate_contract(contract)


def test_contract_allows_adding_supported_optional_field(contract):
    contract["schema"]["node_optional"].append("custom_tag")
    contract["schema"]["node_field_types"]["custom_tag"] = "nonempty_string"
    validate_contract(contract)


def test_contract_rejects_overlap_between_required_and_optional(contract):
    contract["schema"]["node_optional"].append("id")
    with pytest.raises(ValueError, match="cannot be both required and optional"):
        validate_contract(contract)


def test_edge_id_is_derived_from_source_target_and_kind(contract, graph):
    edge = graph["edges"][0]
    assert edge["id"] == canonical_edge_id(edge["source"], edge["target"], edge["kind"])
    validate_graph(graph, contract)


@pytest.mark.parametrize(
    "edge_id",
    [
        "edge-01",
        "sha256:ABCDEF",
        f"sha256:{'0' * 64}",
    ],
)
def test_invalid_or_mismatched_edge_id_is_rejected(contract, graph, edge_id):
    graph["edges"][0]["id"] = edge_id
    with pytest.raises(ValueError, match="canonical edge id|ID does not match"):
        validate_graph(graph, contract)


def test_multiple_audit_records_are_preserved(contract, graph):
    assert len(graph["edges"][1]["provenance"]) == 2
    validate_graph(graph, contract)


@pytest.mark.parametrize("field", ["raw_file", "collector", "timestamp"])
def test_provenance_requires_audit_fields(contract, graph, field):
    del graph["edges"][0]["provenance"][0][field]
    with pytest.raises(ValueError, match="missing required fields"):
        validate_graph(graph, contract)


@pytest.mark.parametrize(
    "timestamp",
    ["2026-09-15", "2026-09-15T00:00:00+07:00", "2026-02-30T00:00:00Z"],
)
def test_provenance_timestamp_must_be_valid_utc(contract, graph, timestamp):
    graph["edges"][0]["provenance"][0]["timestamp"] = timestamp
    with pytest.raises(ValueError, match="invalid timestamp"):
        validate_graph(graph, contract)


def test_empty_provenance_is_rejected(contract, graph):
    graph["edges"][0]["provenance"] = []
    with pytest.raises(ValueError, match="invalid provenance"):
        validate_graph(graph, contract)


def test_duplicate_provenance_record_is_rejected(contract, graph):
    record = copy.deepcopy(graph["edges"][0]["provenance"][0])
    graph["edges"][0]["provenance"].append(record)
    with pytest.raises(ValueError, match="duplicates audit evidence"):
        validate_graph(graph, contract)


def test_undeclared_edge_field_is_rejected(contract, graph):
    graph["edges"][0]["evidence"] = "positive"
    with pytest.raises(ValueError, match="unsupported fields"):
        validate_graph(graph, contract)


def test_undeclared_provenance_field_is_rejected(contract, graph):
    graph["edges"][0]["provenance"][0]["unexpected"] = "value"
    with pytest.raises(ValueError, match="unsupported fields"):
        validate_graph(graph, contract)


def _current_contract_graph(graph):
    graph["metadata"]["contract_version"] = "1.3.0"
    for edge in graph["edges"]:
        for record in edge["provenance"]:
            record["timestamp_status"] = "observed"
    return graph


def test_current_contract_requires_timestamp_status(contract, graph):
    current = _current_contract_graph(graph)
    del current["edges"][0]["provenance"][0]["timestamp_status"]
    with pytest.raises(ValueError, match="missing required fields"):
        validate_graph(current, contract)


def test_contract_12_accepts_and_requires_timestamp_status(contract, graph):
    previous = _current_contract_graph(graph)
    previous["metadata"]["contract_version"] = "1.2.0"
    validate_graph(previous, contract)
    del previous["edges"][0]["provenance"][0]["timestamp_status"]
    with pytest.raises(ValueError, match="missing required fields"):
        validate_graph(previous, contract)


@pytest.mark.parametrize("version", ["1.0.0", "1.1.0"])
def test_legacy_versions_keep_missing_timestamp_status(version, contract, graph):
    graph["metadata"]["contract_version"] = version
    validate_graph(graph, contract)
    assert "timestamp_status" not in graph["edges"][0]["provenance"][0]


@pytest.mark.parametrize("version", ["1.0.0", "1.1.0", "1.2.0"])
def test_pre_13_contract_rejects_domain_sid_scoped_id(version, contract, graph):
    if version == "1.2.0":
        _current_contract_graph(graph)
    graph["metadata"]["contract_version"] = version
    previous_id = graph["nodes"][0]["id"]
    graph["nodes"][0]["id"] = "domain:sid:S-1-5-21-111-222-333:S-1-5-32-544"
    for edge in graph["edges"]:
        if edge["source"] == previous_id:
            edge["source"] = graph["nodes"][0]["id"]
        if edge["target"] == previous_id:
            edge["target"] = graph["nodes"][0]["id"]
        edge["id"] = canonical_edge_id(edge["source"], edge["target"], edge["kind"])
    with pytest.raises(ValueError, match="requires Contract 1.3.0"):
        validate_graph(graph, contract)


@pytest.mark.parametrize("version", ["1.0.0", "1.1.0", "1.2.0"])
def test_pre_13_contract_retains_existing_id_grammar(version, contract, graph):
    if version == "1.2.0":
        _current_contract_graph(graph)
    graph["metadata"]["contract_version"] = version
    validate_graph(graph, contract)


@pytest.mark.parametrize(
    ("status", "reason"),
    [("not_a_status", None), ("derived", None), ("externally_evidenced", " ")],
)
def test_current_contract_rejects_invalid_time_status_evidence(contract, graph, status, reason):
    current = _current_contract_graph(graph)
    record = current["edges"][0]["provenance"][0]
    record["timestamp_status"] = status
    if reason is not None:
        record["time_provenance_reason"] = reason
    with pytest.raises(ValueError, match="timestamp_status|time-provenance reason|invalid values"):
        validate_graph(current, contract)


def test_legacy_graph_load_keeps_missing_status_unknown(contract, graph):
    legacy = copy.deepcopy(graph)
    assert legacy["metadata"]["contract_version"] == "1.0.0"
    payload = serialize_graph(legacy, contract=contract)
    reloaded = deserialize_graph(payload, contract=contract)
    assert "timestamp_status" not in reloaded["edges"][0]["provenance"][0]


def test_every_current_status_is_valid_and_round_trips(contract, graph):
    current = _current_contract_graph(graph)
    statuses = ["observed", "assumed", "derived", "externally_evidenced", "unknown_legacy"]
    for record, status in zip(current["edges"][0]["provenance"], statuses[:1], strict=True):
        record["timestamp_status"] = status
    current["edges"][0]["provenance"].append(
        {
            **copy.deepcopy(current["edges"][0]["provenance"][0]),
            "timestamp_status": "assumed",
        }
    )
    for status in ("derived", "externally_evidenced"):
        current["edges"][0]["provenance"].append(
            {
                **copy.deepcopy(current["edges"][0]["provenance"][0]),
                "timestamp_status": status,
                "time_provenance_reason": f"audited {status} basis",
            }
        )
    current["edges"][0]["provenance"].append(
        {
            **copy.deepcopy(current["edges"][0]["provenance"][0]),
            "timestamp_status": "unknown_legacy",
            "record_id": "legacy-uncertain-copy",
        }
    )
    # Other fixture provenance records keep distinct record IDs to avoid duplicates.
    for index, record in enumerate(current["edges"][0]["provenance"]):
        record["record_id"] = f"time-status-{index}"
    validate_graph(current, contract)
    payload = serialize_graph(current, contract=contract)
    assert deserialize_graph(payload, contract=contract) == current


@pytest.mark.parametrize("endpoint", ["source", "target"])
def test_edge_endpoints_cannot_reference_noncanonical_nodes(contract, graph, endpoint):
    edge = graph["edges"][0]
    node = next(node for node in graph["nodes"] if node["id"] == edge[endpoint])
    node["id"] = "noncanonical-node"
    edge[endpoint] = node["id"]
    edge["id"] = canonical_edge_id(edge["source"], edge["target"], edge["kind"])
    with pytest.raises(ValueError, match="invalid canonical id"):
        validate_graph(graph, contract)


@pytest.mark.parametrize(
    "field", ["contract_version", "weight_profile", "snapshot_id", "created_at", "code_version"]
)
def test_graph_metadata_requires_m2_identity_fields(contract, graph, field):
    del graph["metadata"][field]
    with pytest.raises(ValueError, match=f"metadata: missing required field {field}"):
        validate_graph(graph, contract)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("snapshot_id", "sha256:" + "A" * 64),
        ("created_at", "2026-09-21T00:00:00+00:00"),
        ("weight_profile", "missing"),
    ],
)
def test_graph_metadata_values_are_canonical(contract, graph, field, value):
    graph["metadata"][field] = value
    with pytest.raises(ValueError, match="metadata"):
        validate_graph(graph, contract)


def test_edge_weight_must_be_positive_and_match_profile(contract, graph):
    graph["edges"][0]["weight"] = 0.5
    with pytest.raises(ValueError, match="weight must be finite and >= 1.0"):
        validate_graph(graph, contract)

    graph["edges"][0]["weight"] = 2.0
    with pytest.raises(ValueError, match="selected profile"):
        validate_graph(graph, contract)


def test_edge_provenance_must_be_positive_evidence(contract, graph):
    del graph["edges"][0]["provenance"][0]["evidence_type"]
    with pytest.raises(ValueError, match="missing required fields"):
        validate_graph(graph, contract)

    graph["edges"][0]["provenance"][0]["evidence_type"] = "unknown"
    with pytest.raises(ValueError, match="invalid evidence_type"):
        validate_graph(graph, contract)


@pytest.mark.parametrize("status", ["unknown", "inferred", "rejected"])
def test_non_traversable_assessments_are_separate_from_edges(contract, graph, status):
    graph["assessments"] = [
        {
            "id": f"assessment-{status}",
            "status": status,
            "reason": "synthetic fixture assessment",
            "subject": graph["nodes"][1]["id"],
            "target": graph["nodes"][2]["id"],
            "kind": "CanRDP",
            "provenance": [
                {
                    "raw_file": "synthetic://assessment.json",
                    "collector": "synthetic-fixture/1.0",
                    "timestamp": "2026-09-21T00:00:00Z",
                    "evidence_type": status,
                    "record_id": f"record-{status}",
                }
            ],
        }
    ]
    validate_graph(graph, contract)


def test_traversable_edges_cannot_contain_assessment_status(contract, graph):
    graph["edges"][0]["assessment"] = "unknown"
    with pytest.raises(ValueError, match="unsupported fields"):
        validate_graph(graph, contract)


def test_identity_asset_ontology_kinds_are_not_structural_graph_kinds(contract):
    contract["node_kinds"].extend(["Identity", "Asset"])
    with pytest.raises(ValueError, match="must match the M2 contract"):
        validate_contract(contract)


def test_boundary_nodes_have_explicit_domain_and_structural_kind(contract, graph):
    domain = next(node for node in graph["nodes"] if node["kind"] == "Domain")
    domain["is_boundary"] = True
    validate_graph(graph, contract)

    domain["kind"] = "OU"
    with pytest.raises(ValueError, match="invalid boundary kind"):
        validate_graph(graph, contract)


def test_domain_is_required_for_every_structural_node(contract, graph):
    del graph["nodes"][0]["domain"]
    with pytest.raises(ValueError, match="missing required field domain"):
        validate_graph(graph, contract)


def _assessment(graph):
    return {
        "id": "assessment-test",
        "status": "unknown",
        "reason": "synthetic assessment",
        "subject": graph["nodes"][1]["id"],
        "target": graph["nodes"][2]["id"],
        "kind": "CanRDP",
        "provenance": [
            {
                "raw_file": "synthetic://assessment.json",
                "collector": "synthetic-fixture/1.0",
                "timestamp": "2026-09-21T00:00:00Z",
                "evidence_type": "unknown",
                "record_id": "assessment-record",
            }
        ],
    }


def test_assessment_kind_and_endpoint_ids_are_validated(contract, graph):
    assessment = _assessment(graph)
    graph["assessments"] = [assessment]
    validate_graph(graph, contract)

    assessment["kind"] = "Unsupported"
    with pytest.raises(ValueError, match="unknown edge kind"):
        validate_graph(graph, contract)

    assessment["kind"] = "CanRDP"
    assessment["subject"] = "S-1-5-32-544"
    with pytest.raises(ValueError, match="invalid canonical id"):
        validate_graph(graph, contract)

    assessment["subject"] = graph["nodes"][1]["id"]
    assessment["target"] = "not-a-canonical-id"
    with pytest.raises(ValueError, match="invalid canonical id"):
        validate_graph(graph, contract)
