"""Replay the pinned Week 3 handoff, without generating search candidates or ratings."""

from __future__ import annotations

import json
import sys
from copy import deepcopy
from hashlib import sha256
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.research.reviewed_parameter_release import (  # noqa: E402
    analytical_expectations,
    digest,
    verify_release,
)
from src.engine.ranking import PathRankingEngine, scoped_preference  # noqa: E402

MANIFEST = ROOT / "tests/fixtures/ranking/week3_acceptance_cases.json"


def check_cases(output_dir: Path) -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    for path, section, field in (
        (manifest["release"]["path"], manifest["release"], "file_sha256"),
        ("requirements.txt", manifest["runtime"], "requirements_file_sha256"),
        (manifest["runtime"]["dependencies"], manifest["runtime"], "dependencies_file_sha256"),
    ):
        assert sha256((ROOT / path).read_bytes()).hexdigest() == section[field], (field, path)
    raw_pin = manifest["release"]["raw_manifest"]
    assert (
        digest(json.loads((ROOT / raw_pin["path"]).read_text(encoding="utf-8")))
        == raw_pin["canonical_digest"]
    ), "raw_manifest.canonical_digest"
    release = verify_release(
        json.loads((ROOT / manifest["release"]["path"]).read_text(encoding="utf-8"))
    )
    assert release["bundle_metadata"]["bundle_digest"] == manifest["release"]["digest"]
    oracle_pin = manifest["release"]["oracle"]
    assert (
        digest(json.loads((ROOT / oracle_pin["path"]).read_text(encoding="utf-8")))
        == oracle_pin["canonical_digest"]
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    for case in manifest["cases"]:
        base = release["query_projections"][case["source"]]
        assert digest(base) == case["input"]["projection_digest"]
        payload = deepcopy(base)
        # Only RFC 6902 add/remove operations are needed for these pinned fixture overlays.
        for patch in case["overlay"]:
            parts = patch["path"].lstrip("/").split("/")
            parent = payload
            for part in parts[:-1]:
                parent = parent[int(part)] if isinstance(parent, list) else parent[part]
            key = parts[-1]
            if patch["op"] == "remove":
                del parent[int(key) if isinstance(parent, list) else key]
            else:
                assert patch["op"] == "add" and isinstance(parent, list) and key == "-"
                parent.append(deepcopy(patch["value"]))
        assert digest(payload) == case["input"]["overlaid_digest"]
        execution = PathRankingEngine().evaluate(payload["query"], payload["candidates"])
        wire = execution["roundtrip_result"]
        assert json.loads(execution["encoded_json"]) == wire
        expected = case["expected"]
        assert wire["pareto_frontier"] == expected["pareto_frontier"]
        for key, value in expected["min_effort"].items():
            assert wire["min_effort_to_da_baseline"][key] == value
        assert wire["search_metadata"] == expected["search_metadata"]
        assessed = {a["candidate_id"]: a for a in execution["assessed_candidates"]}
        assert assessed.keys() == expected["candidates"].keys()
        for binding in case["bindings"]:
            candidate = next(
                c for c in payload["candidates"] if c["candidate_id"] == binding["candidate_id"]
            )
            assert digest(candidate) == binding["canonical_digest"]
            assert candidate["bound_action_ids"] == binding["ordered_action_ids"]
        assert payload["query"]["query_metadata"]["target_goal"] == case["scenario"]["target_goal"]
        for cid, fields in expected["candidates"].items():
            actual = wire["eligible_candidates"].get(cid)
            if actual is None:
                actual = wire["diagnostics"][cid]["assessment"]
            for key, value in fields.items():
                assert actual[key] == value, (case["case_id"], cid, key)
            candidate = next(c for c in payload["candidates"] if c["candidate_id"] == cid)
            assert actual["bound_action_ids"] == candidate["bound_action_ids"]
            assert actual["structural_routes"] == candidate["structural_routes"]
            assert actual["target_asset_id"] == candidate["target_asset_id"]
            assert actual["program"] == manifest["programs"][cid]
            impact = execution["decoded_query"]["target_impact_assessments"][
                actual["target_asset_id"]
            ]
            assert impact["success_event"] == case["scenario"]["target_goal"]["success_event"]
            assert actual["work_unit_basis"] == {
                u: execution["decoded_query"]["work_units_ledger"][u] for u in actual["program"]
            }
        if case["kind"] == "positive":
            oracle = analytical_expectations(payload["query"], payload["candidates"])
            assert oracle["pareto_frontier"] == expected["pareto_frontier"]
            assert oracle["min_effort"] == expected["min_effort"]
            for cid, fields in oracle["candidates"].items():
                for key, value in fields.items():
                    assert wire["eligible_candidates"][cid][key] == value
            assert [
                {**pair, "relation": scoped_preference(assessed[pair["a"]], assessed[pair["b"]])}
                for pair in oracle["relations"]
            ] == expected["relations"]
        else:
            predicate = case["predicate"]["name"]
            fact = execution["decoded_query"]["resolved_facts"][predicate]
            for key, value in expected["resolved_fact"].items():
                assert fact[key] == value
        assert digest(wire) == case["actual_replay"]["canonical_output_digest"]
        assert case["actual_search_e2e"] == {"verdict": "not_run", "output": None}
        for name, data in (
            ("input", payload),
            ("result", wire),
            ("facts", execution["decoded_query"]["resolved_facts"]),
        ):
            (output_dir / f"{case['case_id']}-{name}.json").write_text(
                json.dumps(data, indent=2) + "\n", encoding="utf-8"
            )


def test_week3_acceptance_manifest(tmp_path: Path) -> None:
    check_cases(tmp_path)


@pytest.mark.parametrize(
    "pin",
    [
        ("release", "file_sha256"),
        ("release", "raw_manifest", "canonical_digest"),
        ("runtime", "requirements_file_sha256"),
        ("runtime", "dependencies_file_sha256"),
    ],
)
def test_week3_acceptance_rejects_changed_pin(tmp_path: Path, monkeypatch, pin) -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    target = manifest
    for key in pin[:-1]:
        target = target[key]
    target[pin[-1]] = ("sha256:" if pin[-1] == "canonical_digest" else "") + "0" * 64
    changed_manifest = tmp_path / "manifest.json"
    changed_manifest.write_text(json.dumps(manifest), encoding="utf-8")
    monkeypatch.setattr(sys.modules[__name__], "MANIFEST", changed_manifest)
    with pytest.raises(AssertionError, match=pin[-1]):
        check_cases(tmp_path / "outputs")


if __name__ == "__main__":
    check_cases(ROOT / "reports/generated/week3-177")
    print("Week 3 release/supplied-candidate replay verified; search E2E not run.")
