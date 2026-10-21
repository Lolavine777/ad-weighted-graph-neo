"""Scenario replay probes: missing or denied prerequisites cannot become feasible."""

import copy
import json
from pathlib import Path

import pytest

from scripts.research.path_ranking_wire_adapter import execute_ranking_roundtrip

FIXTURES = Path(__file__).parent / "fixtures" / "ranking"

# These predicates are independent of the effects created by successful replay.
RUNTIME_REQUIREMENTS = [
    ("password_policy_accepts_lidia", 0),
    ("directory_write_allowed_lidia", 0),
    ("authentication_accepted_lidia", 0),
    ("membership_security_group_usable_lidia_da", 0),
    ("winrm_authentication_accepted_lidia", 0),
    ("endpoint_authorized_lidia", 0),
    ("admin_execution_context_lidia", 0),
    ("password_policy_accepts_josefa", 1),
    ("directory_write_allowed_josefa", 1),
    ("authentication_accepted_josefa", 1),
    ("membership_security_group_usable_josefa_vajer", 1),
    ("password_policy_accepts_ollie", 1),
    ("directory_write_allowed_ollie", 1),
    ("authentication_accepted_ollie", 1),
    ("membership_security_group_usable_ollie_da", 1),
    ("winrm_authentication_accepted_ollie", 1),
    ("endpoint_authorized_ollie", 1),
    ("admin_execution_context_ollie", 1),
]


@pytest.mark.parametrize("predicate,candidate_index", RUNTIME_REQUIREMENTS)
@pytest.mark.parametrize("variant,want", [("required_false", "blocked"), ("missing", "unknown")])
def test_seamless_required_runtime_gate(predicate, candidate_index, variant, want):
    payload = json.loads((FIXTURES / "seamless_query_input.json").read_text(encoding="utf-8"))
    facts = payload["query"]["facts_ledger"]
    facts["predicate_layers"][predicate] = 3
    if variant == "required_false":
        # Keep any true assumption: a classified synthetic denial must veto it.
        facts["false_facts"].append(
            {
                "predicate": predicate,
                "truth_value": False,
                "layer": 3,
                "provenance_reference": "synthetic:pr159-negative-case",
            }
        )
    else:
        facts["assumed_facts"] = [
            fact for fact in facts["assumed_facts"] if fact["predicate"] != predicate
        ]
    result = execute_ranking_roundtrip(json.dumps(payload["query"]), payload["candidates"])
    cid = payload["candidates"][candidate_index]["candidate_id"]
    diagnostic = result["roundtrip_result"]["diagnostics"][cid]
    assert diagnostic["assessment"]["status"] == want
    assert diagnostic["assessment"]["gates_evaluation"][predicate] == (
        "False" if variant == "required_false" else "Unknown"
    )
    assert result["roundtrip_result"]["pareto_frontier"] == []


def test_seamless_missing_session_is_runtime_unknown():
    payload = json.loads((FIXTURES / "seamless_query_input.json").read_text(encoding="utf-8"))
    from scripts.research.path_ranking_wire_adapter import decode_ranking_query

    decoded = decode_ranking_query(json.dumps(payload["query"]))
    assert decoded["resolved_facts"]["session_badblood"]["value"] == "Unknown"
    payload = copy.deepcopy(payload)
    payload["query"]["facts_ledger"]["assumed_facts"].append(
        {
            "predicate": "session_badblood",
            "truth_value": True,
            "layer": 3,
            "rationale": "synthetic session assumption; no structural edge is created",
        }
    )
    decoded = decode_ranking_query(json.dumps(payload["query"]))
    assert decoded["resolved_facts"]["session_badblood"]["value"] == "True"


@pytest.mark.parametrize("stem", ["seamless", "seamless_source_b"])
def test_seamless_positive_replay_matches_complete_expected(stem):
    payload = json.loads((FIXTURES / f"{stem}_query_input.json").read_text(encoding="utf-8"))
    expected = json.loads(
        (FIXTURES / f"{stem}_expected_diagnostics.json").read_text(encoding="utf-8")
    )
    actual = execute_ranking_roundtrip(json.dumps(payload["query"]), payload["candidates"])
    assert actual["roundtrip_result"] == expected
    assert all(d["assessment"]["status"] == "feasible" for d in expected["diagnostics"].values())


@pytest.mark.parametrize("stem", ["seamless", "seamless_source_b"])
def test_seamless_wire_unrated_basis_tracks_independent_assessment(stem):
    from scripts.research.path_ranking_wire_adapter import decode_ranking_query

    payload = json.loads((FIXTURES / f"{stem}_query_input.json").read_text(encoding="utf-8"))
    query = payload["query"]
    decoded = decode_ranking_query(json.dumps(query))
    records = [
        *query["work_units_ledger"].values(),
        *decoded["target_impact_assessments"].values(),
    ]
    for record in records:
        assert record["rating_status"] == "unrated"
        assert record["missing_basis_reasons"] == ["pending_independent_ratings"]
    assert query["conditional_bounds_table"] == []
    assert all(
        record["consequence_rating"] is None for record in records if "consequence_rating" in record
    )


def test_seamless_canonical_route_verification_rejects_missing_terminal_acl():
    from scripts.research.seamless_packet_evidence import verify_routes

    payload = json.loads((FIXTURES / "seamless_query_input.json").read_text(encoding="utf-8"))
    graph = {"nodes": [], "edges": []}
    kinds = ["GenericAll", "MemberOf", "GenericAll", "MemberOf", "GenericAll"]
    for candidate in payload["candidates"]:
        route = candidate["structural_routes"][0]
        graph["nodes"].extend({"id": node} for node in route["node_ids"])
        for index, eid in enumerate(route["edge_ids"]):
            graph["edges"].append(
                {
                    "id": eid,
                    "source": route["node_ids"][index],
                    "target": route["node_ids"][index + 1],
                    "kind": kinds[index],
                }
            )
    assert len(verify_routes(graph, [payload])) == 2
    terminal_id = payload["candidates"][0]["structural_routes"][0]["edge_ids"][-1]
    graph["edges"] = [edge for edge in graph["edges"] if edge["id"] != terminal_id]
    with pytest.raises(ValueError, match="missing canonical edge"):
        verify_routes(graph, [payload])


def test_seamless_blank_sheets_can_reconcile_after_synthetic_completion():
    from scripts.research.path_ranking_wire_adapter import reconcile_expert_ratings

    sheets = [
        json.loads((FIXTURES / f"seamless_rater_{n}.json").read_text(encoding="utf-8"))
        for n in (1, 2)
    ]
    for section in ("impact_ratings", "likelihood_ratings", "effort_ratings"):
        for first, second in zip(sheets[0][section], sheets[1][section], strict=True):
            assert first["evaluator"] is second["evaluator"] is None
            records = [copy.deepcopy(first), copy.deepcopy(second)]
            for index, rec in enumerate(records):
                rec["evaluator"] = f"synthetic_test_rater_{index}"
                if section == "impact_ratings":
                    assert rec["consequence_rating"] is None
                    rec["consequence_rating"] = "Critical"
                elif section == "likelihood_ratings":
                    assert rec["conditional_bounds"] == {"lower": None, "upper": None}
                    rec["conditional_bounds"] = {"lower": "1/2", "upper": "3/4"}
                else:
                    assert rec["rubric_evaluation"]["computed_cost"] is None
                    rec["rubric_evaluation"].update(t1_complexity=1, t2_friction=1, computed_cost=0)
            assert reconcile_expert_ratings(*records)["status"] in ("consensus", "reconciled")


def test_seamless_synthetic_example_uses_conditional_factors():
    payload = json.loads((FIXTURES / "seamless_query_input.json").read_text(encoding="utf-8"))
    candidate = payload["candidates"][0]
    units = [
        act["referenced_work_unit_ids"][0]
        for act in payload["query"]["bound_actions"]
        if act["action_id"] in candidate["bound_action_ids"] and act["referenced_work_unit_ids"]
    ]
    # Hand-derived conditional factors for synthetic cumulative 4/5, 3/5, 3/10.
    payload["query"]["conditional_bounds_table"] = [
        {"prefix": units[: i + 1], "lower": factor, "upper": factor}
        for i, factor in enumerate(("4/5", "3/4", "1/2"))
    ]
    result = execute_ranking_roundtrip(json.dumps(payload["query"]), [candidate])
    assessment = result["roundtrip_result"]["diagnostics"][candidate["candidate_id"]]["assessment"]
    assert assessment["likelihood_interval"] == ["3/10", "3/10"]
    assert result["roundtrip_result"]["pareto_frontier"] == []  # Real impact remains unrated.


@pytest.mark.parametrize("bucket", ["aces", "enabled"])
def test_seamless_raw_verification_rejects_swapped_predicate_locators(tmp_path, bucket):
    from scripts.research.seamless_packet_evidence import verify_raw_locators
    from src.parser.builder import canonical_edge_id

    source = "S-1-5-21-1-2-3-1000"
    targets = ["S-1-5-21-1-2-3-1001", "S-1-5-21-1-2-3-1002"]
    records = [
        {
            "ObjectIdentifier": target,
            "Properties": {"enabled": True},
            "Aces": [{"PrincipalSID": source, "RightName": "GenericAll"}],
        }
        for target in targets
    ]
    (tmp_path / "users.json").write_text(json.dumps({"users": records}))
    graph = {
        "edges": [
            {
                "id": canonical_edge_id(source, target, "GenericAll"),
                "provenance": [
                    {
                        "raw_file": "snapshot:" + "a" * 64 + "/users.json",
                        "record_id": target,
                        "evidence_type": "positive",
                    }
                ],
            }
            for target in targets
        ]
    }
    facts = []
    bindings = {}
    for i, target in enumerate(targets):
        predicate = f"grant_{i}" if bucket == "aces" else f"enabled_{i}"
        pointer = f"users.json#/users/{i}/" + (
            "Aces/0" if bucket == "aces" else "Properties/enabled"
        )
        facts.append(
            {
                "predicate": predicate,
                "truth_value": True,
                "layer": 1 if bucket == "aces" else 2,
                "provenance_reference": pointer,
            }
        )
        bindings[predicate] = (
            {"kind": "GenericAll", "source": source, "target": target}
            if bucket == "aces"
            else {"node_id": target, "property": "enabled"}
        )
    payload = {
        "query": {
            "query_metadata": {"snapshot_id": "sha256:" + "a" * 64},
            "facts_ledger": {"observed_facts": facts},
        },
        "candidates": [],
    }
    assert verify_raw_locators(graph, [payload], tmp_path, bindings=bindings) == 2
    facts[0]["provenance_reference"], facts[1]["provenance_reference"] = (
        facts[1]["provenance_reference"],
        facts[0]["provenance_reference"],
    )
    with pytest.raises(ValueError, match="predicate binding mismatch"):
        verify_raw_locators(graph, [payload], tmp_path, bindings=bindings)
