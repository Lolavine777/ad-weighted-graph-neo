"""Record error policies must not hide source failures or programming defects."""

import logging
from pathlib import Path
from typing import get_type_hints

import pytest
import yaml

from src.parser import (
    Assessment,
    AssessmentStatus,
    ErrorPolicy,
    Graph,
    GraphBuilder,
    GraphEdge,
    GraphMetadata,
    GraphNode,
    Normalizer,
    Provenance,
    RawDataLoader,
    RawProvenance,
    RawRecord,
    RecordError,
    process_records,
)

ROOT = Path(__file__).resolve().parents[1]


def test_graph_type_requires_contract_version_metadata():
    assert "metadata" in Graph.__required_keys__
    assert "assessments" in Graph.__required_keys__
    assert get_type_hints(Graph)["metadata"] is GraphMetadata
    assert GraphMetadata.__required_keys__ >= {
        "contract_version",
        "weight_profile",
        "snapshot_id",
        "created_at",
        "code_version",
    }
    assert get_type_hints(GraphMetadata)["created_at"] is str


def test_assessment_interface_has_only_non_traversable_statuses():
    assert {status.value for status in AssessmentStatus} == {"unknown", "inferred", "rejected"}
    assert set(Assessment.__required_keys__) == {"id", "status", "reason", "provenance"}
    assert {"weight", "provenance"} <= set(GraphEdge.__required_keys__)
    assert "evidence_type" not in RawProvenance.__required_keys__
    assert get_type_hints(RawRecord)["provenance"] is RawProvenance


def test_graph_node_fields_match_frozen_contract():
    contract = yaml.safe_load((ROOT / "configs/contract.yml").read_text(encoding="utf-8"))
    schema = contract["schema"]
    assert set(GraphNode.__required_keys__) == set(schema["node_required"])
    assert set(GraphNode.__optional_keys__) == set(schema["node_optional"])
    assert get_type_hints(GraphNode)["domain"] is str
    assert get_type_hints(GraphNode)["is_boundary"] is bool


def test_canonical_provenance_fields_match_frozen_contract_and_exclude_raw_fields():
    contract = yaml.safe_load((ROOT / "configs/contract.yml").read_text(encoding="utf-8"))
    prov_schema = contract["schema"]["provenance"]
    raw_prov_schema = contract["schema"]["raw_provenance"]

    # Canonical Provenance matches contract schema exactly
    assert set(Provenance.__required_keys__) == set(prov_schema["required"])
    assert set(Provenance.__optional_keys__) == set(prov_schema["optional"])

    # Raw-only fields are explicitly excluded from canonical Provenance
    raw_only_fields = {"snapshot_id", "record_locator", "time_provenance"}
    assert not (set(Provenance.__annotations__) & raw_only_fields)
    assert not (set(Provenance.__required_keys__) & raw_only_fields)
    assert not (set(Provenance.__optional_keys__) & raw_only_fields)

    # RawProvenance required keys match raw_provenance schema
    assert set(RawProvenance.__required_keys__) == set(raw_prov_schema["required"])
    assert raw_only_fields <= set(RawProvenance.__optional_keys__)

    # Wholesale copy guard: a RawProvenance dictionary with raw-only fields
    # must fail contract provenance validation if passed directly as edge provenance
    sample_raw: RawProvenance = {
        "raw_file": "snapshot:abc/computers.json",
        "collector": "sharphound",
        "timestamp": "2021-09-20T18:59:58Z",
        "snapshot_id": "sha256:e0601d76",
        "record_locator": "#/computers/0",
        "time_provenance": "assumed",
    }
    allowed_contract_fields = set(prov_schema["required"]) | set(prov_schema["optional"])
    forbidden_keys = set(sample_raw) - allowed_contract_fields
    assert forbidden_keys == raw_only_fields


def normalize(value: int) -> int:
    if value < 0:
        raise RecordError("missing stable scope", stage="normalize", record_id="synthetic-2")
    return value * 2


@pytest.mark.parametrize("interface", [RawDataLoader, Normalizer, GraphBuilder])
def test_interfaces_require_an_implementation(interface):
    with pytest.raises(TypeError, match="abstract"):
        interface()


def test_default_fail_fast_stops_before_next_record():
    visited = []
    failure = RecordError("invalid identity", stage="normalize")

    def transform(value):
        visited.append(value)
        if value == 2:
            raise failure
        return value

    output = process_records([1, 2, 3], transform)
    assert visited == []
    assert next(output) == 1
    with pytest.raises(RecordError) as caught:
        next(output)
    assert caught.value is failure
    assert visited == [1, 2]


@pytest.mark.parametrize("policy", [ErrorPolicy.SKIP_RECORD, ErrorPolicy.LOG_WARNING])
def test_recoverable_errors_skip_only_bad_record(policy, caplog):
    with caplog.at_level(logging.WARNING):
        result = list(process_records([1, -1, 3], normalize, error_policy=policy))
    assert result == [2, 6]
    if policy is ErrorPolicy.LOG_WARNING:
        assert len(caplog.records) == 1
        assert caplog.records[0].message == ("normalize record synthetic-2: missing stable scope")
    else:
        assert caplog.records == []


@pytest.mark.parametrize("policy", list(ErrorPolicy))
@pytest.mark.parametrize("failure", [OSError("read failed"), ValueError("bug"), TypeError("bug")])
def test_non_record_errors_always_propagate(policy, failure):
    def transform(value):
        raise failure

    with pytest.raises(type(failure)) as caught:
        list(process_records([1], transform, error_policy=policy))
    assert caught.value is failure


@pytest.mark.parametrize("policy", list(ErrorPolicy))
def test_source_iteration_failure_is_fatal_even_for_record_error(policy):
    def source():
        yield 1
        raise RecordError("broken source", stage="load")

    output = process_records(source(), normalize, error_policy=policy)
    assert next(output) == 2
    with pytest.raises(RecordError, match="broken source"):
        next(output)


def test_invalid_policy_is_rejected_before_consuming_source():
    def source():
        pytest.fail("source must not be consumed")
        yield 1

    with pytest.raises(TypeError, match="ErrorPolicy"):
        process_records(source(), normalize, error_policy="skip_record")


def test_warning_uses_supplied_logger_without_dumping_payload(caplog):
    def transform(value):
        raise RecordError("missing identity", stage="normalize")

    with caplog.at_level(logging.WARNING, logger="parser.test"):
        assert (
            list(
                process_records(
                    [{"private": "raw payload"}],
                    transform,
                    error_policy=ErrorPolicy.LOG_WARNING,
                    logger=logging.getLogger("parser.test"),
                )
            )
            == []
        )
    assert len(caplog.records) == 1
    assert caplog.records[0].name == "parser.test"
    assert "raw payload" not in caplog.text


@pytest.mark.parametrize("policy", list(ErrorPolicy))
def test_empty_input(policy):
    assert list(process_records([], normalize, error_policy=policy)) == []
