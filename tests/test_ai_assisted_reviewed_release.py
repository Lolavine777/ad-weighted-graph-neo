"""Test-only dispositions for confirmed source artifacts, never final human decisions."""

import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.research import reviewed_parameter_release as tool
from scripts.research.synthetic_reviewed_release_demo import synthetic_inputs

ROOT = Path(__file__).resolve().parents[1]
PACKET = ROOT / "docs/research/ratings/week3-2026-10-02"
CLASS = "human_reviewed_ai_assisted_ratings"


def reviewed_inputs():
    return {
        "template": tool.load_snapshot(
            ROOT / "tests/fixtures/ranking/seamless_parameter_bundle.json"
        ),
        **{
            key: tool.load_snapshot(PACKET / filename)
            for key, filename in {
                "sheet1": "rater-A.json",
                "sheet2": "rater-B.json",
                "policy": "execution-policy.json",
                "confirmation": "shared-review-confirmation.json",
                "ai_draft": "rater-B-ai-draft.json",
            }.items()
        },
    }


def change_snapshot(inputs, key, change):
    import hashlib

    snapshot = inputs[key]
    data = tool.decode_snapshot(snapshot)
    change(data)
    raw = json.dumps(data, ensure_ascii=False).encode("utf-8")
    snapshot.update(
        raw_utf8=raw.decode("utf-8"), digest="sha256:" + hashlib.sha256(raw).hexdigest()
    )


def build_test_only_decisions(inputs, evidence=CLASS):
    """Build test-only choices from #170 proposals, bypassing preflight for negative fixtures."""
    report = tool.reconciliation.reconcile_sheets(
        tool.decode_snapshot(inputs["sheet1"]),
        tool.decode_snapshot(inputs["sheet2"]),
        inputs["sheet1"]["path"],
        inputs["sheet2"]["path"],
        inputs["sheet1"]["digest"],
        inputs["sheet2"]["digest"],
    )
    report = json.loads(json.dumps(report))
    decisions = []
    for category, pairs in report["reconciled_pairs"].items():
        for pair in pairs:
            record = copy.deepcopy(pair["raw_records"][0])
            record["evaluator"] = "test-only-reviewer"
            decisions.append(
                {
                    "category": category,
                    "pair_digest": tool.digest(pair),
                    "binding": copy.deepcopy(pair["binding"]),
                    "disposition": "reviewed",
                    "final_record": record,
                    "reviewer_identity": "test-only-reviewer",
                    "declared_at": "2000-01-02T00:00:00Z",
                    "rationale": "Test-only source A selection to exercise the evidence boundary",
                    "resolution": "Test-only choice; distinct B interval remains in raw provenance",
                    "decision_reference": "test-only://171/ai-assisted",
                }
            )
    return {
        "schema_version": "1.0.0",
        "release_id": "test-only-ai-reviewed-171",
        "release_version": "1.0.0",
        "evidence_class": evidence,
        "input_digests": {k: v["digest"] for k, v in inputs.items()},
        "report_digest": tool.digest(report),
        "decisions": decisions,
    }


def test_confirmed_sources_export_replay_engine_sensitivity_without_acceptance():
    inputs = reviewed_inputs()
    before = copy.deepcopy(inputs)
    release = tool.export_release(inputs, build_test_only_decisions(inputs))
    assert tool.verify_release(release) == release
    result = tool.validate_and_sensitivity(release)
    assert result["validation_status"] == "passed"
    assert release["provenance"]["inputs"] == before
    assert release["governance"]["human_acceptance"] == "pending"
    context = release["governance"]["rating_context"]
    assert context["independent_inter_rater_agreement_eligible"] is False
    assert context["confirmation"] == tool.decode_snapshot(inputs["confirmation"])
    assert context["execution_policy"] == tool.decode_snapshot(inputs["policy"])
    assert context["ai_draft_digest"] == inputs["ai_draft"]["digest"]
    assert result["rating_context"] == context
    expected = result["sources"]["source_a"]["expected"]["candidates"]
    direct = expected["cand_seamless_01_direct_lidia"]
    alternative = expected["cand_seamless_02_alt_vajer_ollie"]
    assert direct["likelihood_interval"] == ["42/125", "171/250"]
    assert alternative["likelihood_interval"] == ["588/3125", "29241/50000"]
    assert (direct["effort"], alternative["effort"], direct["impact"]) == (2, 3, "High")
    assert len(result["sensitivity"]) >= 21
    assert all("execution_policy" in r for r in release["conditional_bounds_table"])
    assert {p: Path(p).read_bytes() for p in (v["path"] for v in inputs.values())} == {
        v["path"]: v["raw_utf8"].encode("utf-8") for v in before.values()
    }


def test_project_review_record_exports_without_dialogue_fields():
    inputs = reviewed_inputs()

    def project_record(record):
        record["reviewed_at"] = record.pop("user_message_time")
        record.pop("user_statement")
        record["review_summary"] = "A/B reviewed the existing assessment under the shared policy."

    change_snapshot(inputs, "confirmation", project_record)
    release = tool.export_release(inputs, build_test_only_decisions(inputs))
    assert tool.verify_release(release) == release
    confirmation = release["governance"]["rating_context"]["confirmation"]
    assert "user_statement" not in confirmation
    assert "user_message_time" not in confirmation
    assert confirmation["review_summary"].startswith("A/B reviewed")
    assert release["governance"]["basis_category"] == CLASS


@pytest.mark.parametrize(
    ("field", "value"),
    [("reviewed_at", "2000-01-01T00:00:00Z"), ("review_summary", "A conflicting review")],
)
def test_project_review_record_rejects_conflicting_legacy_fields(field, value):
    inputs = reviewed_inputs()
    change_snapshot(inputs, "confirmation", lambda record: record.update({field: value}))
    with pytest.raises(ValueError, match="Conflicting confirmation fields"):
        tool.export_release(inputs, build_test_only_decisions(inputs))


@pytest.mark.parametrize("sheet", ["sheet1", "sheet2"])
@pytest.mark.parametrize("source_class", ["ai_assisted_scenario_assessment", CLASS])
def test_ai_or_exposed_sources_cannot_be_promoted_to_independent(tmp_path, sheet, source_class):
    inputs = synthetic_inputs(tmp_path)

    def change(s):
        suffix = s["sheet_id"].rsplit("-", 1)[-1]
        s["evidence_class"] = (
            source_class if suffix == sheet[-1] else "declared_independent_ratings"
        )
        s["sheet_id"] = f"test-only-{suffix}"
        s["rater"]["evaluator"] = f"test-only-{suffix}"
        if suffix == sheet[-1]:
            s["human_rating_status"] = "pending_human_review"
            s["independent_inter_rater_agreement_eligible"] = False
        for group in tool.GROUPS.values():
            for r in s[group]:
                r["evaluator"] = s["rater"]["evaluator"]

    for key in ("sheet1", "sheet2"):
        change_snapshot(inputs, key, change)
    decisions = build_test_only_decisions(inputs, "declared_independent_ratings")
    # Both sources lack synthetic markers; source evidence must still be checked.
    with pytest.raises(ValueError, match="independent"):
        tool.export_release(inputs, decisions)


@pytest.mark.parametrize(
    "mutation",
    [
        "missing_confirmation",
        "missing_policy",
        "missing_archive",
        "unconfirmed_B",
        "independence_claim",
        "sheet_confirmation",
        "confirmation_channel",
        "participant",
        "policy_digest",
        "confirmation_policy_digest",
        "archive_digest",
        "archive_changed",
        "source_provenance",
        "row_policy",
        "row_policy_reference",
        "policy_bool",
        "policy_horizon",
        "policy_missing_mechanism",
        "final_policy",
        "final_policy_reference",
    ],
)
def test_ai_review_and_policy_fail_closed_with_fresh_decision_bindings(mutation):
    inputs = reviewed_inputs()
    if mutation.startswith("missing_"):
        inputs.pop(
            {
                "missing_confirmation": "confirmation",
                "missing_policy": "policy",
                "missing_archive": "ai_draft",
            }[mutation]
        )
    elif mutation == "unconfirmed_B":
        change_snapshot(
            inputs, "sheet2", lambda s: s.update(human_rating_status="pending_human_review")
        )
    elif mutation == "independence_claim":
        change_snapshot(
            inputs, "sheet2", lambda s: s.update(independent_inter_rater_agreement_eligible=True)
        )
    elif mutation == "sheet_confirmation":
        change_snapshot(
            inputs, "sheet2", lambda s: s.update(shared_review_confirmation="other.json")
        )
    elif mutation == "confirmation_channel":
        change_snapshot(inputs, "confirmation", lambda c: c.update(confirmation_channel="PENDING"))
    elif mutation == "participant":
        change_snapshot(
            inputs,
            "confirmation",
            lambda c: c.update(participants=["Lolavine777 (TTS A)", "someone_else"]),
        )
    elif mutation == "policy_digest":
        change_snapshot(
            inputs, "sheet2", lambda s: s["execution_policy_reference"].update(sha256="0" * 64)
        )
    elif mutation == "confirmation_policy_digest":
        change_snapshot(
            inputs, "confirmation", lambda c: c["execution_policy"].update(sha256="0" * 64)
        )
    elif mutation == "archive_digest":
        change_snapshot(
            inputs, "confirmation", lambda c: c["original_inputs"]["B"].update(sha256="0" * 64)
        )
    elif mutation == "archive_changed":
        change_snapshot(inputs, "ai_draft", lambda a: a.update(assistance="altered archive"))
    elif mutation == "source_provenance":
        change_snapshot(
            inputs,
            "sheet2",
            lambda s: s["source_rating_provenance"].update(source_commit="different"),
        )
    elif mutation == "row_policy":
        change_snapshot(
            inputs,
            "sheet2",
            lambda s: s["likelihood_ratings"][0]["execution_policy"].update(deadline_minutes=30),
        )
    elif mutation == "row_policy_reference":
        change_snapshot(
            inputs,
            "sheet2",
            lambda s: s["likelihood_ratings"][0]["execution_policy_reference"].update(
                version="2.0.0"
            ),
        )
    elif mutation == "policy_bool":
        change_snapshot(
            inputs,
            "policy",
            lambda p: p["by_mechanism"]["reset_password"].update(max_attempts=True),
        )
    elif mutation == "policy_horizon":
        change_snapshot(inputs, "policy", lambda p: p.update(operational_horizon="48h"))
    elif mutation == "policy_missing_mechanism":
        change_snapshot(inputs, "policy", lambda p: p["by_mechanism"].pop("remote_exec_winrm"))
    decisions = build_test_only_decisions(inputs)
    if mutation.startswith("final_policy"):
        row = next(
            d["final_record"] for d in decisions["decisions"] if d["category"] == "likelihood"
        )
        if mutation == "final_policy":
            row["execution_policy"]["deadline_minutes"] = 30
        else:
            row["execution_policy_reference"]["sha256"] = "0" * 64
    with pytest.raises(
        ValueError, match="(?i)confirmation|policy|archive|confirmed|independence|provenance"
    ):
        tool.export_release(inputs, decisions)


def test_ai_context_cli_and_offline_replay_preserve_sources(tmp_path):
    inputs = reviewed_inputs()
    # Isolate every input so source deletion proves replay is offline without touching the packet.
    for key, snapshot in inputs.items():
        path = tmp_path / Path(snapshot["path"]).name
        path.write_bytes(snapshot["raw_utf8"].encode("utf-8"))
        inputs[key] = tool.load_snapshot(path)
    decisions = build_test_only_decisions(inputs)
    dp = tmp_path / "test-only-decisions.json"
    dp.write_text(json.dumps(decisions), encoding="utf-8")
    output = tmp_path / "test-only-release.json"
    cmd = [sys.executable, str(ROOT / "scripts/research/reviewed_parameter_release.py"), "export"]
    for key, snapshot in inputs.items():
        cmd += ["--" + key.replace("_", "-"), snapshot["path"]]
    cmd += ["--decisions", str(dp), "--output", str(output)]
    result = subprocess.run(cmd, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    before_output = output.read_bytes()
    for key in ("policy", "confirmation", "ai_draft"):
        result = subprocess.run(cmd[:-1] + [inputs[key]["path"]], capture_output=True, text=True)
        assert result.returncode == 1
        assert "aliases" in result.stderr
        assert Path(inputs[key]["path"]).read_bytes() == inputs[key]["raw_utf8"].encode("utf-8")
    change_snapshot(
        inputs, "sheet2", lambda s: s.update(human_rating_status="pending_human_review")
    )
    Path(inputs["sheet2"]["path"]).write_bytes(inputs["sheet2"]["raw_utf8"].encode("utf-8"))
    dp.write_text(json.dumps(build_test_only_decisions(inputs)), encoding="utf-8")
    result = subprocess.run(cmd, capture_output=True, text=True)
    assert result.returncode == 1
    assert "confirmed" in result.stderr
    assert output.read_bytes() == before_output
    for snapshot in inputs.values():
        assert Path(snapshot["path"]).read_bytes() == snapshot["raw_utf8"].encode("utf-8")
        Path(snapshot["path"]).unlink()
    report = tmp_path / "test-only-validation.json"
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/research/reviewed_parameter_release.py"),
            "validate",
            "--release",
            str(output),
            "--output",
            str(report),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(report.read_bytes())["validation_status"] == "passed"
    release = json.loads(output.read_bytes())
    release["governance"]["rating_context"]["confirmation"]["confirmation_channel"] = (
        "invented direct attestation"
    )
    tool.seal_release(release)
    with pytest.raises(ValueError, match="replay"):
        tool.verify_release(release)


@pytest.mark.parametrize("key", ["sheet1", "sheet2"])
def test_reconciliation_preflight_rejects_policy_mismatch(key):
    inputs = reviewed_inputs()
    change_snapshot(
        inputs, key, lambda s: s["likelihood_ratings"][0]["execution_policy"].update(max_attempts=4)
    )
    with pytest.raises(ValueError, match="policy"):
        tool.reconcile_inputs(inputs)


def test_synthetic_sources_cannot_be_promoted_to_human_reviewed_ai(tmp_path):
    inputs = synthetic_inputs(tmp_path)
    with pytest.raises(ValueError, match="Synthetic"):
        tool.export_release(inputs, build_test_only_decisions(inputs))


@pytest.mark.parametrize(
    "mutation",
    [
        "impact",
        "likelihood",
        "effort",
        "archive_stub",
        "record_confirmation",
        "record_channel",
        "record_scope",
        "missing_record_confirmation",
        "relay_status",
    ],
)
def test_adoption_confirmation_cannot_cover_changed_or_unconfirmed_assessments(mutation):
    inputs = reviewed_inputs()
    if mutation == "impact":
        change_snapshot(
            inputs, "sheet2", lambda s: s["impact_ratings"][0].update(consequence_rating="Critical")
        )
    elif mutation == "likelihood":
        change_snapshot(
            inputs,
            "sheet2",
            lambda s: s["likelihood_ratings"][0].update(
                conditional_bounds={"lower": "0", "upper": "1"}
            ),
        )
    elif mutation == "effort":
        change_snapshot(
            inputs,
            "sheet2",
            lambda s: s["effort_ratings"][0]["rubric_evaluation"].update(
                t1_complexity=2, computed_cost=2
            ),
        )
    elif mutation == "archive_stub":

        def replace(archive):
            archive.clear()
            archive.update(
                evidence_class="ai_assisted_scenario_assessment",
                human_rating_status="pending_human_review",
            )

        change_snapshot(inputs, "ai_draft", replace)
        archive_digest = inputs["ai_draft"]["digest"].removeprefix("sha256:")
        change_snapshot(
            inputs,
            "confirmation",
            lambda c: c["original_inputs"]["B"].update(sha256=archive_digest),
        )
        change_snapshot(
            inputs, "sheet2", lambda s: s["source_rating_provenance"].update(sha256=archive_digest)
        )
    elif mutation == "relay_status":
        change_snapshot(
            inputs, "sheet2", lambda s: s.update(human_rating_status="confirmed_by_user")
        )
    else:
        field = {
            "record_confirmation": "record",
            "record_channel": "channel",
            "record_scope": "scope",
        }.get(mutation)

        def change(sheet):
            for group in tool.GROUPS.values():
                for row in sheet[group]:
                    if field:
                        row["human_confirmation"][field] = "unconfirmed-other-record"
                    else:
                        row.pop("human_confirmation")

        change_snapshot(inputs, "sheet2", change)
    with pytest.raises(ValueError, match="(?i)archive|adopt|confirmation|relay"):
        tool.export_release(inputs, build_test_only_decisions(inputs))
