"""Reproducibility checks supplement, never replace, independent assertions."""

import hashlib
import json
from copy import deepcopy
from pathlib import Path

from scripts.research.week4_acceptance_runner import (
    compute_digest,
    evaluate_case,
    execution_metadata,
    file_pins,
    run_all_cases,
    semantic_payload,
    summarize,
)

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "reports/research/week4-guided-exploration-acceptance-manifest-v16.json"


def test_guided_source_manifest_preserves_historical_evidence():
    assert hashlib.sha256(MANIFEST_PATH.read_bytes()).hexdigest() == (
        "3951d543abaa704cab2c50f84363a1eba47ce29a259539e1ab9ab038cc1e97de"
    )
    historical = ROOT / "reports/research/week4-maintainer-acceptance-manifest-v2.json"
    assert hashlib.sha256(historical.read_bytes()).hexdigest() == (
        "1623c1c9e505550374402fdd5714de0a0eebb3a63d75eab0c825e19de3269dd9"
    )
    current = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    assert "src/engine/exploration.py" in current["execution"]["file_sha256"]
    previous_v5 = ROOT / "reports/research/week4-guided-exploration-acceptance-manifest-v5.json"
    assert hashlib.sha256(previous_v5.read_bytes()).hexdigest() == (
        "08738fce5a0212c243235dacb1c3f6e1eb963d27b45568718f31546b73c074b0"
    )
    previous = ROOT / "reports/research/week4-guided-exploration-acceptance-manifest-v6.json"
    previous_digest = "eb919132cabcaf9c974bd6bfcb6dcb1938bb5ec74f992cced2984ce540d84548"
    assert hashlib.sha256(previous.read_bytes()).hexdigest() == previous_digest
    previous = ROOT / "reports/research/week4-guided-exploration-acceptance-manifest-v7.json"
    previous_digest = "2f62f3b0680126ff071f7fa3fa44457ace3654f255e8729eda4bdd16150be337"
    assert hashlib.sha256(previous.read_bytes()).hexdigest() == previous_digest
    previous = ROOT / "reports/research/week4-guided-exploration-acceptance-manifest-v8.json"
    previous_digest = "989cac2c3a84077a3fe363c1ebe0fed1b8d253c67abd2dd5d3126cc962cf2b9e"
    assert hashlib.sha256(previous.read_bytes()).hexdigest() == previous_digest
    previous = ROOT / "reports/research/week4-guided-exploration-acceptance-manifest-v9.json"
    previous_digest = "90be6f244fc3c7fb87659c91149752033ee1ef835ce2476b8996f9a2bc2f623e"
    assert hashlib.sha256(previous.read_bytes()).hexdigest() == previous_digest
    previous = ROOT / "reports/research/week4-guided-exploration-acceptance-manifest-v10.json"
    previous_digest = "bb0905bd9d5141fa9d1eb86d31e51511fb356920aa67fe347836c4d103def353"
    assert hashlib.sha256(previous.read_bytes()).hexdigest() == previous_digest
    previous = ROOT / "reports/research/week4-guided-exploration-acceptance-manifest-v11.json"
    previous_digest = "5d273d2f7a95d265d6f6912a283422f689b4774735128da7adfb559f565ff513"
    assert hashlib.sha256(previous.read_bytes()).hexdigest() == previous_digest
    previous = ROOT / "reports/research/week4-guided-exploration-acceptance-manifest-v12.json"
    previous_digest = "d7e0705fe2f67ea81ec846f1676ea52243eba132dc306cc37abaca9e2754aaf4"
    assert hashlib.sha256(previous.read_bytes()).hexdigest() == previous_digest
    previous = ROOT / "reports/research/week4-guided-exploration-acceptance-manifest-v13.json"
    previous_digest = "b29df225b9089400114fe51121e222d52a3c390dcd2054ba418e6a1e87b51774"
    assert hashlib.sha256(previous.read_bytes()).hexdigest() == previous_digest
    previous = ROOT / "reports/research/week4-guided-exploration-acceptance-manifest-v14.json"
    previous_digest = "2d28d61e23cc601249606f34411376aa1a01bfcfee12882871dc0292677c17cc"
    assert hashlib.sha256(previous.read_bytes()).hexdigest() == previous_digest
    previous = ROOT / "reports/research/week4-guided-exploration-acceptance-manifest-v15.json"
    previous_digest = "8967b072a5590775902cb9bfbc54f7200439ed15aee1b8c9ffea7ae1c1f0a4a2"
    assert hashlib.sha256(previous.read_bytes()).hexdigest() == previous_digest
    assert current["execution"]["previous_acceptance_manifest"] == {
        "path": previous.relative_to(ROOT).as_posix(),
        "sha256": "sha256:" + previous_digest,
    }


def normalize_prerequisite_observation(payload):
    """Validate the environment observation; preserve every other frozen field."""
    payload = deepcopy(payload)
    assert payload["summary"] == summarize(payload["cases"])
    dataset = next(c for c in payload["cases"] if c["case_id"] == "W4-SEAMLESS-DATASET-GATE")
    present = dataset["actual"]["private_raw_data_present"]
    assert isinstance(present, bool)
    assert dataset["verdict"] == ("NOT EXECUTED" if present else "BLOCKED RUN")
    assert dataset["evidence_class"] == (
        "manual_check_not_executed" if present else "prerequisite_observation_only"
    )
    assert dataset["output_digest"] == compute_digest(dataset["actual"])
    dataset["actual"]["private_raw_data_present"] = False
    dataset["verdict"] = "BLOCKED RUN"
    dataset["evidence_class"] = "prerequisite_observation_only"
    dataset["output_digest"] = compute_digest(dataset["actual"])
    payload["summary"] = summarize(payload["cases"])
    return payload


def test_week4_acceptance_manifest_file_pins():
    execution = execution_metadata(None)
    for name, digest in execution["file_sha256"].items():
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == digest, name
    assert execution["file_sha256"] == file_pins()
    assert execution["source_input_digest"] == compute_digest(file_pins())


def test_week4_acceptance_manifest_semantic_reproduction():
    first, second = run_all_cases(), run_all_cases()
    assert first["execution"]["executed_at"] != second["execution"]["executed_at"]
    assert first["execution"]["source_input_digest"] == second["execution"]["source_input_digest"]
    assert semantic_payload(first) == semantic_payload(second)
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    fixture = json.loads(
        (ROOT / "tests/fixtures/ranking/week4_acceptance_cases.json").read_text(encoding="utf-8")
    )
    recorded = json.loads(
        (ROOT / "reports/research/issue250-review-acceptance-manifest-v4.json").read_text(
            encoding="utf-8"
        )
    )
    assert semantic_payload(recorded) == fixture
    successor_path = ROOT / "reports/research/week4-maintainer-acceptance-cases-v2.json"
    assert hashlib.sha256(successor_path.read_bytes()).hexdigest() == (
        "dec17ae2c8fc39faa320ca5c1487bb3087f7fe319cd2cdb81145149d16d50bae"
    )
    successor = normalize_prerequisite_observation(json.loads(successor_path.read_text()))
    historical = deepcopy(successor)
    old_cases = {case["case_id"]: case for case in fixture["cases"]}
    changed_digests = set()
    for case in historical["cases"]:
        old_case = old_cases[case["case_id"]]
        assert ("evidence_digest" in case) == ("evidence_digest" in old_case)
        old_digest = old_case.get("evidence_digest")
        if case.get("evidence_digest") != old_digest:
            changed_digests.add(case["case_id"])
            case["evidence_digest"] = old_digest
    assert changed_digests == {
        "W4-MIN-EFFORT-E",
        "W4-MIN-EFFORT-T",
        "W4-CAP-PATHS",
        "W4-CAP-EXP",
        "W4-CAP-STEPS",
        "W4-DEFECT-212-ADAPTER-REJECT",
        "W4-TECH-KERBEROASTING",
        "W4-TECH-ASREP",
        "W4-CLI-PACKAGE",
    }
    assert compute_digest(historical) == compute_digest(fixture)
    v3_path = ROOT / "reports/research/week4-maintainer-acceptance-cases-v3.json"
    cases_v3 = normalize_prerequisite_observation(json.loads(v3_path.read_text(encoding="utf-8")))
    differing_case_ids = {
        c["case_id"] for c, s in zip(cases_v3["cases"], successor["cases"], strict=True) if c != s
    }
    assert differing_case_ids == {"W4-K-OVERLAP"}
    reconciled_v3 = deepcopy(cases_v3)
    k_overlap = next(c for c in reconciled_v3["cases"] if c["case_id"] == "W4-K-OVERLAP")
    k_v2 = next(c for c in successor["cases"] if c["case_id"] == "W4-K-OVERLAP")
    assert k_overlap["actual"]["extension_truncation_reason"] == "path_limit_reached"
    k_overlap["actual"]["extension_truncation_reason"] = k_v2["actual"][
        "extension_truncation_reason"
    ]
    k_overlap["evidence_digest"] = k_v2["evidence_digest"]
    k_overlap["output_digest"] = compute_digest(k_overlap["actual"])
    assert reconciled_v3 == successor
    assert compute_digest(reconciled_v3) == compute_digest(successor)
    assert compute_digest(normalize_prerequisite_observation(semantic_payload(manifest))) == (
        compute_digest(cases_v3)
    )
    current = normalize_prerequisite_observation(semantic_payload(first))
    historical = normalize_prerequisite_observation(semantic_payload(manifest))
    for payload in (current, historical):
        for case in payload["cases"]:
            # Trace schemas evolve; current trace bytes are checked by the two live runs above.
            case.pop("evidence_digest", None)
    cli = next(case for case in historical["cases"] if case["case_id"] == "W4-CLI-PACKAGE")
    assert cli["expected"].pop("clean_tracked_source") is True
    assert cli["actual"].pop("clean_tracked_source") is True
    cli["expected"]["source_provenance_verified"] = True
    cli["actual"]["source_provenance_verified"] = True
    evaluate_case(cli)
    for payload in (current, historical):
        for case in payload["cases"]:
            case["assertions"].sort(key=lambda check: check["field"])
    assert current == historical
    k_evidence = next(c for c in manifest["cases"] if c["case_id"] == "W4-K-OVERLAP")
    ext_on = k_evidence["evidence"]["extension_on"]
    search = ext_on["search"]
    caps = ext_on["caps"]
    assert search["generated_paths_count"] == 50 == caps["max_paths"]
    assert search["truncated"] is True
    assert search["truncation_reason"] == "path_limit_reached"
    assert ext_on["search_complete"] is False


def test_week4_acceptance_manifest_independent_verdicts():
    result = run_all_cases()
    raw_dir = ROOT / "data/raw/SEAMLESS"
    raw_present = raw_dir.is_dir() and any(raw_dir.iterdir())
    assert result["summary"] == {
        "total_cases": 38,
        "pass_count": 36,
        "known_defect_count": 0,
        "unexpected_failure_count": 0,
        "pending_count": 0,
        "not_executed_count": 2 if raw_present else 1,
        "blocked_run_count": 0 if raw_present else 1,
    }
    for case in result["cases"]:
        if case["verdict"] == "PASS":
            assert case["normative_acceptance"]
            assert all(check["passed"] for check in case["assertions"])
        else:
            assert not case["normative_acceptance"]
    cases = {case["case_id"]: case for case in result["cases"]}
    dataset = cases["W4-SEAMLESS-DATASET-GATE"]
    assert dataset["actual"]["private_raw_data_present"] == raw_present
    assert dataset["actual"]["probe_execution"] == "not_executed"
    assert dataset["actual"]["authorized_trace_verified"] is None
    assert dataset["verdict"] == ("NOT EXECUTED" if raw_present else "BLOCKED RUN")
    assert not dataset["normative_acceptance"]
    adapter = cases["W4-DEFECT-212-ADAPTER-REJECT"]["actual"]
    assert adapter["paths_count"] == 3
    assert adapter["candidates_adapted"] == 2
    assert adapter["minimum_effort_value"] == 5
    assert adapter["is_minimum_proven_over_scope"] is False
    zero = cases["W4-DEFECT-212-ZERO-ACTION"]["actual"]
    assert zero["final_goal_reached"] is True
    assert zero["path_transitions"] == 0
    assert zero["adapter_rejected"] is False
    assert zero["ranking_status"] == "not_applicable"
    assert zero["canonical_minimum_effort"] is None
    assert zero["likelihood_interval"] is None
    assert zero["impact"] is None
    assert zero["eligible_candidates"] == {}
    assert zero["pareto_frontier"] == []
    roast = cases["W4-TECH-KERBEROASTING"]["actual"]
    assert roast["extension_on_paths"] == 1
    assert roast["effort"] is None
    assert roast["likelihood_interval"] is None
    assert roast["impact"] is None
    assert roast["is_minimum_proven_over_scope"] is False
