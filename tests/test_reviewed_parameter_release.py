"""Issue #171: disposable synthetic declarations, never actual human ratings."""

import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.research import reviewed_parameter_release as tool
from scripts.research.synthetic_reviewed_release_demo import synthetic_decisions, synthetic_inputs

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests/fixtures/ranking"


def test_synthetic_export_validation_engine_and_selected_numbers(tmp_path):
    inputs = synthetic_inputs(tmp_path)
    decisions = synthetic_decisions(inputs)
    release = tool.export_release(inputs, decisions)
    assert tool.verify_release(release) == release
    result = tool.validate_and_sensitivity(release)
    assert result["validation_status"] == "passed"
    assert release["governance"]["human_acceptance"] == "pending"
    a = result["sources"]["source_a"]["expected"]
    assert a["candidates"]["cand_seamless_01_direct_lidia"]["likelihood_interval"] == [
        "1/8",
        "27/64",
    ]
    assert a["candidates"]["cand_seamless_01_direct_lidia"]["effort"] == 6
    assert a["candidates"]["cand_seamless_01_direct_lidia"]["impact"] == "Critical"
    assert a["candidates"]["cand_seamless_02_alt_vajer_ollie"]["likelihood_interval"] == [
        "1/32",
        "243/1024",
    ]
    assert a["candidates"]["cand_seamless_02_alt_vajer_ollie"]["effort"] == 10
    assert len(result["sensitivity"]) >= 21
    assert release["provenance"]["inputs"] == inputs
    assert release["provenance"]["decisions"] == decisions
    assert release["provenance"]["report"] == tool.reconcile_inputs(inputs)
    assert tool.export_release(inputs, decisions) == release


@pytest.mark.parametrize(
    "mutation",
    [
        "missing",
        "duplicate",
        "extra",
        "stale",
        "pair",
        "binding",
        "pending",
        "reviewer",
        "time",
        "rationale",
        "reference",
        "resolution",
        "basis",
        "bounds",
        "rubric",
        "overlap",
        "evaluator",
        "history",
        "quantity",
        "outcome",
    ],
)
def test_invalid_decisions_fail_closed(tmp_path, mutation):
    inputs = synthetic_inputs(tmp_path)
    decisions = synthetic_decisions(inputs)
    d = decisions["decisions"][0]
    likelihood = next(r for r in decisions["decisions"] if r["category"] == "likelihood")
    effort = next(r for r in decisions["decisions"] if r["category"] == "effort")
    if mutation == "missing":
        decisions["decisions"].pop()
    elif mutation == "duplicate":
        decisions["decisions"].append(copy.deepcopy(d))
    elif mutation == "extra":
        decisions["decisions"].append({**d, "pair_digest": "sha256:extra"})
    elif mutation == "stale":
        decisions["report_digest"] = "sha256:stale"
    elif mutation == "pair":
        d["pair_digest"] = "sha256:stale"
    elif mutation == "binding":
        d["binding"]["success_event"] = "wrong"
    elif mutation == "pending":
        d["disposition"] = "pending"
    elif mutation == "reviewer":
        d["reviewer_identity"] = ""
    elif mutation == "time":
        d["declared_at"] = "today"
    elif mutation in ("rationale", "resolution"):
        d[mutation] = ""
    elif mutation == "reference":
        d["decision_reference"] = ""
    elif mutation == "basis":
        likelihood["final_record"]["basis_category"] = ""
    elif mutation == "bounds":
        likelihood["final_record"]["conditional_bounds"]["lower"] = "1/0"
    elif mutation == "rubric":
        effort["final_record"]["rubric_evaluation"]["computed_cost"] = True
    elif mutation == "overlap":
        effort["final_record"]["overlap_analysis"]["is_independent"] = False
    elif mutation == "evaluator":
        d["final_record"]["evaluator"] = "someone-else"
    elif mutation == "history":
        likelihood["final_record"]["conditioning_previous_successes"] = ["wrong"]
    elif mutation == "quantity":
        likelihood["final_record"]["quantity"] = "cumulative"
    elif mutation == "outcome":
        likelihood["final_record"]["outcome_action_id"] = "wrong"
    with pytest.raises((ValueError, TypeError)):
        tool.export_release(inputs, decisions)


def test_actual_pending_sheets_refused_and_untouched(tmp_path):
    paths = [FIXTURES / f"seamless_rater_{i}.json" for i in (1, 2)]
    before = [p.read_bytes() for p in paths]
    inputs = {
        "template": tool.load_snapshot(FIXTURES / "seamless_parameter_bundle.json"),
        **{f"sheet{i}": tool.load_snapshot(p) for i, p in enumerate(paths, 1)},
    }
    with pytest.raises(ValueError, match="rated"):
        tool.export_release(inputs, synthetic_decisions(inputs))
    assert [p.read_bytes() for p in paths] == before


@pytest.mark.parametrize("mutation", ["projection", "root", "digest", "raw", "scope"])
def test_release_tampering_cannot_be_hidden_by_rehashing(tmp_path, mutation):
    release = tool.export_release(
        synthetic_inputs(tmp_path), synthetic_decisions(synthetic_inputs(tmp_path))
    )
    if mutation == "projection":
        release["query_projections"]["source_b"]["candidates"] = []
    elif mutation == "root":
        release["conditional_bounds_table"][0]["lower"] = "0"
    elif mutation == "digest":
        release["bundle_metadata"]["bundle_digest"] = "sha256:wrong"
    elif mutation == "raw":
        release["provenance"]["inputs"]["sheet1"]["raw_utf8"] += " "
    elif mutation == "scope":
        release["facts_ledger"]["unknown_facts"] = []
    if mutation != "digest":
        release["bundle_metadata"]["bundle_digest"] = tool.compute_bundle_digest(release)
    with pytest.raises(ValueError):
        tool.verify_release(release)


def test_cli_export_validate_and_failure_preserves_files(tmp_path):
    inputs = synthetic_inputs(tmp_path)
    decisions = synthetic_decisions(inputs)
    dp = tmp_path / "decisions.json"
    dp.write_text(json.dumps(decisions), encoding="utf-8")
    output = tmp_path / "release.json"
    args = [
        "export",
        "--sheet1",
        inputs["sheet1"]["path"],
        "--sheet2",
        inputs["sheet2"]["path"],
        "--template",
        inputs["template"]["path"],
        "--decisions",
        str(dp),
        "--output",
        str(output),
    ]
    assert tool.main(args) == 0
    before = output.read_bytes()
    assert tool.main(args) == 0
    assert output.read_bytes() == before
    report = tmp_path / "validation.json"
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
    decisions["decisions"].pop()
    dp.write_text(json.dumps(decisions), encoding="utf-8")
    assert tool.main(args) == 1
    assert output.read_bytes() == before
    assert tool.main(args[:-1] + [str(dp)]) == 1
    assert json.loads(dp.read_bytes()) == decisions


def rewrite_snapshot(snapshot, change):
    data = tool.decode_snapshot(snapshot)
    change(data)
    raw = json.dumps(data)
    snapshot["raw_utf8"] = raw
    import hashlib

    snapshot["digest"] = "sha256:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()


@pytest.mark.parametrize(
    "field",
    [
        "query_id",
        "scenario_id",
        "scenario_version",
        "foothold_node_id",
        "snapshot_id",
        "operational_horizon",
        "target_population",
        "outcome_action_id",
        "conditioning_previous_successes",
        "quantity",
    ],
)
def test_source_binding_mismatch_even_with_fresh_decision_digests(tmp_path, field):
    inputs = synthetic_inputs(tmp_path)
    for i in (1, 2):
        rewrite_snapshot(
            inputs[f"sheet{i}"],
            lambda s: s["likelihood_ratings"][0].update(
                {field: ["wrong"] if field == "conditioning_previous_successes" else "wrong"}
            ),
        )
    with pytest.raises(ValueError):
        tool.export_release(inputs, synthetic_decisions(inputs))


@pytest.mark.parametrize(
    "kind",
    ["missing", "extra", "unrated", "rubric_float", "rubric_str", "identity", "missing_basis"],
)
def test_bad_source_records_cannot_be_released(tmp_path, kind):
    inputs = synthetic_inputs(tmp_path)

    def change(s):
        if kind == "missing":
            s["effort_ratings"].pop()
        elif kind == "extra":
            s["effort_ratings"].append(copy.deepcopy(s["effort_ratings"][0]))
        elif kind == "unrated":
            s["likelihood_ratings"][0].update(
                rating_status="unrated", conditional_bounds={"lower": None, "upper": None}
            )
        elif kind.startswith("rubric_"):
            s["effort_ratings"][0]["rubric_evaluation"]["computed_cost"] = (
                2.0 if kind == "rubric_float" else "2"
            )
        elif kind == "identity":
            s["effort_ratings"][0]["evaluator"] = "someone_else"
        elif kind == "missing_basis":
            s["likelihood_ratings"][0]["source_references"] = []

    rewrite_snapshot(inputs["sheet1"], change)
    with pytest.raises((ValueError, TypeError)):
        tool.export_release(inputs, synthetic_decisions(inputs))


def test_disagreements_and_overlap_are_lossless_and_require_explicit_resolution(tmp_path):
    inputs = synthetic_inputs(tmp_path)

    def change(s):
        s["impact_ratings"][0]["consequence_rating"] = "Low"
        s["likelihood_ratings"][0]["conditional_bounds"] = {"lower": "0", "upper": "1"}
        s["effort_ratings"][0]["overlap_analysis"].update(
            is_independent=False,
            shared_preparation_tags=["synthetic unresolved preparation"],
            prerequisite_dependencies=[s["effort_ratings"][1]["work_unit_id"]],
        )

    rewrite_snapshot(inputs["sheet2"], change)
    decisions = synthetic_decisions(inputs)
    release = tool.export_release(inputs, decisions)
    report = release["provenance"]["report"]
    assert report["coverage"]["disagreement_count"] > 0
    assert report["coverage"]["withheld_overlap_count"] == 1
    assert report["aggregate_metrics"]["likelihood"]["high_epistemic_uncertainty_count"] > 0
    assert (
        report["reconciled_pairs"]["effort"][0]["raw_records"]
        == tool.reconcile_inputs(inputs)["reconciled_pairs"]["effort"][0]["raw_records"]
    )
    assert release["provenance"]["inputs"]["sheet2"] == inputs["sheet2"]
    assert tool.validate_and_sensitivity(release)["validation_status"] == "passed"


@pytest.mark.parametrize("alter", [False, True])
def test_supplied_report_is_verified_by_reconciliation_replay(tmp_path, alter):
    inputs = synthetic_inputs(tmp_path)
    report = tool.reconcile_inputs(inputs)
    if alter:
        report["reconciled_pairs"]["impact"][0]["raw_records"][0]["consequence_rating"] = "Low"
    rp = tmp_path / "report.json"
    rp.write_text(json.dumps(report), encoding="utf-8")
    inputs["report"] = tool.load_snapshot(rp)
    if alter:
        with pytest.raises(ValueError, match="report"):
            synthetic_decisions(inputs)
    else:
        assert tool.verify_release(tool.export_release(inputs, synthetic_decisions(inputs)))


@pytest.mark.parametrize("case", ["tie", "effort_tie_break", "dominance", "incomparable", "zero"])
def test_independent_oracle_and_engine_frontier_cases(tmp_path, case):
    inputs = synthetic_inputs(tmp_path)
    decisions = synthetic_decisions(inputs)
    for d in decisions["decisions"]:
        r = d["final_record"]
        if d["category"] == "likelihood" and case != "incomparable":
            value = "0" if case == "zero" else "1"
            if case == "dominance" and len(r["ordered_work_prefix"]) > 3:
                value = "1/2"
            r["conditional_bounds"] = {"lower": value, "upper": value}
        if d["category"] == "effort" and case in ("tie", "zero"):
            r["rubric_evaluation"] = {
                "t1_complexity": 1,
                "t2_friction": 1,
                "formula": "base",
                "computed_cost": 0,
            }
    result = tool.validate_and_sensitivity(tool.export_release(inputs, decisions))
    expected = result["sources"]["source_a"]["expected"]
    relation = expected["relations"][0]["relation"]
    assert (
        relation
        == {
            "tie": "tie",
            "zero": "tie",
            "effort_tie_break": "a",
            "dominance": "a",
            "incomparable": "incomparable",
        }[case]
    )
    if case == "effort_tie_break":
        assert len(expected["pareto_frontier"]) == 1
    if case in ("tie", "zero"):
        assert len(expected["pareto_frontier"]) == 2


@pytest.mark.parametrize("case", ["same", "hardlink", "symlink"])
def test_cli_rejects_output_aliases(tmp_path, case):
    inputs = synthetic_inputs(tmp_path)
    dp = tmp_path / "decisions.json"
    dp.write_text(json.dumps(synthetic_decisions(inputs)), encoding="utf-8")
    source = Path(inputs["sheet1"]["path"])
    output = source if case == "same" else tmp_path / "alias.json"
    if case == "hardlink":
        output.hardlink_to(source)
    if case == "symlink":
        try:
            output.symlink_to(source)
        except OSError:
            pytest.skip("Platform does not allow symlink creation")
    before = source.read_bytes()
    assert (
        tool.main(
            [
                "export",
                "--sheet1",
                str(source),
                "--sheet2",
                inputs["sheet2"]["path"],
                "--template",
                inputs["template"]["path"],
                "--decisions",
                str(dp),
                "--output",
                str(output),
            ]
        )
        == 1
    )
    assert source.read_bytes() == before


@pytest.mark.parametrize("failure", ["create", "write", "replace"])
def test_atomic_failure_preserves_previous_output_and_sources(tmp_path, monkeypatch, failure):
    import tempfile

    inputs = synthetic_inputs(tmp_path)
    dp = tmp_path / "decisions.json"
    dp.write_text(json.dumps(synthetic_decisions(inputs)), encoding="utf-8")
    output = tmp_path / "release.json"
    output.write_bytes(b"previous output\r\n")
    sentinel = tmp_path / ".release.json.tmp.sentinel"
    sentinel.write_bytes(b"not writer owned")
    before = {p: p.read_bytes() for p in tmp_path.iterdir()}

    def fail(*args, **kwargs):
        raise OSError("synthetic disk failure")

    def partial_write(value, stream, **kwargs):
        stream.write('{"partial":')
        raise OSError("synthetic disk full")

    if failure == "create":
        monkeypatch.setattr(tempfile, "NamedTemporaryFile", fail)
    elif failure == "write":
        monkeypatch.setattr(json, "dump", partial_write)
    else:
        monkeypatch.setattr(Path, "replace", fail)
    assert (
        tool.main(
            [
                "export",
                "--sheet1",
                inputs["sheet1"]["path"],
                "--sheet2",
                inputs["sheet2"]["path"],
                "--template",
                inputs["template"]["path"],
                "--decisions",
                str(dp),
                "--output",
                str(output),
            ]
        )
        == 1
    )
    assert {p: p.read_bytes() for p in tmp_path.iterdir()} == before


def test_synthetic_evidence_cannot_be_relabelled_human(tmp_path):
    inputs = synthetic_inputs(tmp_path)
    decisions = synthetic_decisions(inputs)
    decisions["evidence_class"] = "declared_independent_ratings"
    with pytest.raises(ValueError, match="Synthetic"):
        tool.export_release(inputs, decisions)


def test_json_duplicate_keys_are_rejected_without_losing_source_bytes(tmp_path):
    path = tmp_path / "duplicate.json"
    path.write_bytes(b'{"a":1,"a":2}')
    with pytest.raises(ValueError, match="Duplicate"):
        tool.load_snapshot(path)
    assert path.read_bytes() == b'{"a":1,"a":2}'


@pytest.mark.parametrize("stage", ["source", "final"])
def test_explicit_missing_basis_reasons_cannot_be_erased(tmp_path, stage):
    inputs = synthetic_inputs(tmp_path)
    if stage == "source":
        rewrite_snapshot(
            inputs["sheet1"],
            lambda s: s["impact_ratings"][0].update(
                missing_basis_reasons=["synthetic missing business basis"]
            ),
        )
    decisions = synthetic_decisions(inputs)
    if stage == "final":
        next(d for d in decisions["decisions"] if d["category"] == "impact")["final_record"][
            "missing_basis_reasons"
        ] = ["synthetic unresolved basis"]
    with pytest.raises(ValueError, match="basis"):
        tool.export_release(inputs, decisions)


def test_registry_is_preserved_and_bound_to_decisions(tmp_path):
    inputs = synthetic_inputs(tmp_path)
    source = tool.decode_snapshot(inputs["sheet1"])
    registry = {
        r["work_unit_id"]: {f: r[f] for f in tool.reconciliation.BINDING_FIELDS["effort"]}
        for r in source["effort_ratings"]
    }
    path = tmp_path / "registry.json"
    path.write_text(json.dumps(registry), encoding="utf-8")
    inputs["registry"] = tool.load_snapshot(path)
    decisions = synthetic_decisions(inputs)
    release = tool.export_release(inputs, decisions)
    assert (
        release["provenance"]["report"]["registry_provenance"]["digest"]
        == inputs["registry"]["digest"]
    )
    assert tool.verify_release(release)
    decisions["input_digests"]["registry"] = "sha256:stale"
    with pytest.raises(ValueError, match="digests"):
        tool.export_release(inputs, decisions)


def test_snapshot_preserves_crlf_bytes_and_report_path_spelling(tmp_path):
    inputs = synthetic_inputs(tmp_path)
    for i in (1, 2):
        path = Path(inputs[f"sheet{i}"]["path"])
        path.write_bytes(
            json.dumps(json.loads(path.read_bytes()), indent=2)
            .encode("utf-8")
            .replace(b"\n", b"\r\n")
        )
        inputs[f"sheet{i}"] = tool.load_snapshot(path)
        # Exact original path is evidence, not a path to open during offline replay.
        inputs[f"sheet{i}"]["path"] = f"C:\\synthetic\\sheet{i}.json"
    release = tool.export_release(inputs, synthetic_decisions(inputs))
    report = release["provenance"]["report"]
    assert report["input_digests"]["sheet1"]["path"] == "C:\\synthetic\\sheet1.json"
    assert "\r\n" in release["provenance"]["inputs"]["sheet1"]["raw_utf8"]
    assert tool.verify_release(release)


def test_prerequisite_dependency_is_not_unresolved_overlap(tmp_path):
    inputs = synthetic_inputs(tmp_path)
    for i in (1, 2):
        rewrite_snapshot(
            inputs[f"sheet{i}"],
            lambda s: s["effort_ratings"][1]["overlap_analysis"].update(
                prerequisite_dependencies=[s["effort_ratings"][0]["work_unit_id"]]
            ),
        )
    release = tool.export_release(inputs, synthetic_decisions(inputs))
    assert release["provenance"]["report"]["coverage"]["withheld_overlap_count"] == 0
    assert tool.validate_and_sensitivity(release)["validation_status"] == "passed"


def test_sensitivity_has_distinct_hypothesis_digests_and_preserves_release(tmp_path):
    inputs = synthetic_inputs(tmp_path)
    release = tool.export_release(inputs, synthetic_decisions(inputs))
    before = copy.deepcopy(release)
    result = tool.validate_and_sensitivity(release)
    assert result["coverage"]["parameter_records_perturbed"] == 21
    for probe in result["sensitivity"]:
        assert probe["outcomes"]
        for source, outcome in probe["outcomes"].items():
            audit = outcome["expected_actual"]["actual"]["parameter_audit"]
            assert audit["query_metadata"]["bundle_digest"] != result["release_digest"]
            assert (
                audit["query_metadata"]["governance"]["status"] == "hypothetical_sensitivity_probe"
            )
            assert result["sources"][source]["actual"]["query_id"] in probe["query_ids"]
    assert release == before


def test_expected_actual_relations_are_compared_independently(tmp_path):
    inputs = synthetic_inputs(tmp_path)
    result = tool.validate_and_sensitivity(tool.export_release(inputs, synthetic_decisions(inputs)))
    for source in result["sources"].values():
        assert source["actual_relations"] == source["expected"]["relations"]


def test_synthetic_demo_cli_produces_reviewable_inputs_and_cannot_overwrite(tmp_path):
    demo = tmp_path / "demo"
    cmd = [
        sys.executable,
        str(ROOT / "scripts/research/synthetic_reviewed_release_demo.py"),
        "--directory",
        str(demo),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    release = json.loads((demo / "release.json").read_bytes())
    assert release["governance"]["basis_category"] == "synthetic_test_only"
    assert json.loads((demo / "validation.json").read_bytes())["validation_status"] == "passed"
    before = {p.name: p.read_bytes() for p in demo.iterdir()}
    result = subprocess.run(cmd, capture_output=True, text=True)
    assert result.returncode == 1
    assert {p.name: p.read_bytes() for p in demo.iterdir()} == before


def test_actual_pending_export_cli_preserves_all_sources_and_prior_output(tmp_path):
    inputs = synthetic_inputs(tmp_path)
    decisions = synthetic_decisions(inputs)
    dp = tmp_path / "decisions.json"
    dp.write_text(json.dumps(decisions), encoding="utf-8")
    actual = [FIXTURES / f"seamless_rater_{i}.json" for i in (1, 2)]
    before = [p.read_bytes() for p in actual]
    output = tmp_path / "actual-release.json"
    output.write_bytes(b"prior release")
    assert (
        tool.main(
            [
                "export",
                "--sheet1",
                str(actual[0]),
                "--sheet2",
                str(actual[1]),
                "--template",
                inputs["template"]["path"],
                "--decisions",
                str(dp),
                "--output",
                str(output),
            ]
        )
        == 1
    )
    assert [p.read_bytes() for p in actual] == before
    assert output.read_bytes() == b"prior release"


def test_invalid_release_validation_cli_keeps_prior_output_and_release(tmp_path):
    inputs = synthetic_inputs(tmp_path)
    release = tool.export_release(inputs, synthetic_decisions(inputs))
    release["query_projections"]["source_b"]["candidates"] = []
    release["bundle_metadata"]["bundle_digest"] = tool.compute_bundle_digest(release)
    rp = tmp_path / "release.json"
    rp.write_text(json.dumps(release), encoding="utf-8")
    output = tmp_path / "validation.json"
    output.write_bytes(b"prior validation")
    before = rp.read_bytes()
    assert tool.main(["validate", "--release", str(rp), "--output", str(output)]) == 1
    assert rp.read_bytes() == before
    assert output.read_bytes() == b"prior validation"
    output.unlink()
    assert tool.main(["validate", "--release", str(rp), "--output", str(output)]) == 1
    assert not output.exists()


def test_independent_oracle_deduplicates_reused_work_and_passive_closure(tmp_path):
    inputs = synthetic_inputs(tmp_path)
    release = tool.export_release(inputs, synthetic_decisions(inputs))
    q, c = tool.derive_query_and_candidates_from_bundle(release)
    repeated = copy.deepcopy(c[0])
    repeated["bound_action_ids"].insert(1, repeated["bound_action_ids"][0])
    expected = tool.analytical_expectations(q, [repeated])["candidates"][repeated["candidate_id"]]
    actual = tool.PathRankingEngine().evaluate(q, [repeated])["roundtrip_result"][
        "eligible_candidates"
    ][repeated["candidate_id"]]
    assert expected["effort"] == actual["effort"] == 6
    assert expected["likelihood_interval"] == actual["likelihood_interval"] == ["1/8", "27/64"]
    assert len(expected["program"]) == len(actual["program"]) == 3


@pytest.mark.parametrize("mutation", ["unknown_rationale", "action_prerequisites", "route_locator"])
def test_rehashed_template_cannot_change_frozen_baseline_context(tmp_path, mutation):
    inputs = synthetic_inputs(tmp_path)

    def change(template):
        if mutation == "unknown_rationale":
            template["facts_ledger"]["unknown_facts"][0]["rationale"] = "changed assumption"
        elif mutation == "action_prerequisites":
            template["bound_actions"][0]["requires"] = []
        else:
            template["candidate_envelopes"][0]["structural_routes"][0]["provenance_locators"][0] = (
                "invented-source"
            )
        tool.seal_release(template)

    rewrite_snapshot(inputs["template"], change)
    decisions = synthetic_decisions(inputs)
    with pytest.raises(ValueError, match="template"):
        tool.export_release(inputs, decisions)


@pytest.mark.parametrize("token", ["NaN", "Infinity", "-Infinity", "1e999", "-1e999"])
def test_nonfinite_json_rejected_before_writing(tmp_path, token):
    path = tmp_path / "nonfinite.json"
    path.write_text('{"number":' + token + "}", encoding="utf-8")
    with pytest.raises(ValueError, match="Nonfinite"):
        tool.load_snapshot(path)


def test_cli_never_reads_back_after_replacing_output(tmp_path, monkeypatch, capsys):
    inputs = synthetic_inputs(tmp_path)
    dp = tmp_path / "decisions.json"
    dp.write_text(json.dumps(synthetic_decisions(inputs)), encoding="utf-8")
    output = tmp_path / "release.json"
    output.write_bytes(b"previous output")
    read = Path.read_bytes

    def unavailable_after_write(path):
        if path == output:
            raise OSError("synthetic readback unavailable")
        return read(path)

    monkeypatch.setattr(Path, "read_bytes", unavailable_after_write)
    assert (
        tool.main(
            [
                "export",
                "--sheet1",
                inputs["sheet1"]["path"],
                "--sheet2",
                inputs["sheet2"]["path"],
                "--template",
                inputs["template"]["path"],
                "--decisions",
                str(dp),
                "--output",
                str(output),
            ]
        )
        == 0
    )
    import hashlib

    notice = json.loads(capsys.readouterr().out)
    assert notice["output_digest"] == "sha256:" + hashlib.sha256(read(output)).hexdigest()
    assert json.loads(read(output))["release_schema_version"] == "1.0.0"


def test_zero_factor_sensitivity_changes_declared_parameter_instead_of_counting_noop(tmp_path):
    inputs = synthetic_inputs(tmp_path)
    decisions = synthetic_decisions(inputs)
    for decision in decisions["decisions"]:
        if decision["category"] == "likelihood":
            decision["final_record"]["conditional_bounds"] = {"lower": "0", "upper": "0"}
    result = tool.validate_and_sensitivity(tool.export_release(inputs, decisions))
    for probe in result["sensitivity"]:
        if probe["category"] != "likelihood":
            continue
        assert "boundary" in probe["rationale"]
        outcome = next(iter(probe["outcomes"].values()))
        rows = outcome["expected_actual"]["actual"]["parameter_audit"]["conditional_bounds_table"]
        assert any(row["upper"] != "0" for row in rows)


@pytest.mark.parametrize(
    ("category", "field"),
    [
        ("decision", "rationale"),
        ("decision", "resolution"),
        ("decision", "decision_reference"),
        ("impact", "business_rationale"),
        ("likelihood", "uncertainty_rationale"),
        ("likelihood", "source_references"),
        ("likelihood", "basis_category"),
        ("effort", "effort_rationale"),
    ],
)
@pytest.mark.parametrize("sentinel", ["PENDING", "  UnReSoLvEd\t"])
def test_cli_refuses_placeholder_decisions_and_final_evidence(tmp_path, category, field, sentinel):
    inputs = synthetic_inputs(tmp_path)
    decisions = synthetic_decisions(inputs)
    decision = next(
        d
        for d in decisions["decisions"]
        if d["category"] == ("impact" if category == "decision" else category)
    )
    record = decision if category == "decision" else decision["final_record"]
    record[field] = [sentinel] if field == "source_references" else sentinel
    dp = tmp_path / "decisions.json"
    dp.write_text(json.dumps(decisions), encoding="utf-8")
    sources = [Path(inputs[k]["path"]) for k in ("sheet1", "sheet2", "template")] + [dp]
    before = [p.read_bytes() for p in sources]
    output = tmp_path / "release.json"
    output.write_bytes(b"previous release\r\n")
    cmd = [
        sys.executable,
        str(ROOT / "scripts/research/reviewed_parameter_release.py"),
        "export",
        "--sheet1",
        str(sources[0]),
        "--sheet2",
        str(sources[1]),
        "--template",
        str(sources[2]),
        "--decisions",
        str(dp),
        "--output",
        str(output),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    assert result.returncode == 1, result.stdout
    assert field in result.stderr
    assert output.read_bytes() == b"previous release\r\n"
    assert [p.read_bytes() for p in sources] == before
    output.unlink()
    result = subprocess.run(cmd, capture_output=True, text=True)
    assert result.returncode == 1, result.stdout
    assert not output.exists()
    assert [p.read_bytes() for p in sources] == before


@pytest.mark.parametrize("sentinel", ["\nTbD ", "\ttOdO\n"])
def test_api_refuses_normalized_placeholder_disposition(tmp_path, sentinel):
    inputs = synthetic_inputs(tmp_path)
    decisions = synthetic_decisions(inputs)
    decisions["decisions"][0]["resolution"] = sentinel
    with pytest.raises(ValueError, match="resolution"):
        tool.export_release(inputs, decisions)


@pytest.mark.parametrize(
    ("group", "field"),
    [
        ("impact_ratings", "business_rationale"),
        ("likelihood_ratings", "uncertainty_rationale"),
        ("likelihood_ratings", "source_references"),
        ("likelihood_ratings", "basis_category"),
        ("effort_ratings", "effort_rationale"),
    ],
)
def test_source_placeholder_basis_is_not_hidden_by_final_disposition(tmp_path, group, field):
    inputs = synthetic_inputs(tmp_path)

    def change(sheet):
        sheet[group][0][field] = ["UNRESOLVED"] if field == "source_references" else "UNRESOLVED"

    rewrite_snapshot(inputs["sheet2"], change)
    # Synthetic final choices use sheet1, whose evidence remains fully declared.
    decisions = synthetic_decisions(inputs)
    with pytest.raises(ValueError, match=field):
        tool.export_release(inputs, decisions)


@pytest.mark.parametrize("word", ["pending", "unresolved"])
def test_release_preserves_legitimate_prose_and_references_containing_pending_words(tmp_path, word):
    inputs = synthetic_inputs(tmp_path)
    rationale = f"Synthetic review resolved earlier {word} uncertainty within declared scope."
    reference = f"synthetic://review/{word}/171"
    for i in (1, 2):

        def change(sheet):
            sheet["impact_ratings"][0]["business_rationale"] = rationale
            sheet["likelihood_ratings"][0]["uncertainty_rationale"] = rationale
            sheet["likelihood_ratings"][0]["source_references"] = [reference]
            sheet["effort_ratings"][0]["effort_rationale"] = rationale

        rewrite_snapshot(inputs[f"sheet{i}"], change)
    decisions = synthetic_decisions(inputs)
    decision = next(d for d in decisions["decisions"] if d["category"] == "likelihood")
    decision.update(rationale=rationale, resolution=rationale, decision_reference=reference)
    before_inputs = copy.deepcopy(inputs)
    before_decisions = copy.deepcopy(decisions)
    release = tool.export_release(inputs, decisions)
    assert tool.verify_release(release)
    assert tool.validate_and_sensitivity(release)["validation_status"] == "passed"
    assert release["provenance"]["inputs"] == before_inputs
    assert release["provenance"]["decisions"] == before_decisions
    assert any(
        pair["raw_records"][0]["source_references"] == [reference]
        for pair in release["provenance"]["report"]["reconciled_pairs"]["likelihood"]
    )


def declared_test_inputs(tmp_path):
    """Exercise the declared-class boundary with disposable test-only data, never human ratings."""
    inputs = synthetic_inputs(tmp_path)
    for i in (1, 2):

        def change(sheet, sheet_number=i):
            sheet["sheet_id"] = f"test-only-171-{sheet_number}"
            sheet["evidence_class"] = "declared_independent_ratings"
            sheet["rater"]["evaluator"] = f"test-only-171-rater-{sheet_number}"
            for group in tool.GROUPS.values():
                for record in sheet[group]:
                    record["evaluator"] = sheet["rater"]["evaluator"]

        rewrite_snapshot(inputs[f"sheet{i}"], change)
    return inputs


@pytest.mark.parametrize("sheet_number", [1, 2])
@pytest.mark.parametrize(
    "field", ["evaluator", "name", "competence_and_scope", "independence_declaration"]
)
@pytest.mark.parametrize("sentinel", ["PENDING", "  UnReSoLvEd\t", "\nTbD ", "\ttOdO\n"])
def test_cli_refuses_placeholder_rater_metadata(tmp_path, sheet_number, field, sentinel):
    inputs = declared_test_inputs(tmp_path)
    decisions = synthetic_decisions(inputs)

    def change(sheet):
        sheet["rater"][field] = sentinel
        if field == "evaluator":
            for group in tool.GROUPS.values():
                for record in sheet[group]:
                    record["evaluator"] = sentinel.strip()

    rewrite_snapshot(inputs[f"sheet{sheet_number}"], change)
    # #170 already rejects PENDING evaluator before report generation; other cases
    # get fresh bindings so the release gate, rather than stale digests, is exercised.
    if field != "evaluator" or sentinel != "PENDING":
        decisions = synthetic_decisions(inputs)
    decisions["evidence_class"] = "declared_independent_ratings"
    for key in ("sheet1", "sheet2"):
        Path(inputs[key]["path"]).write_bytes(inputs[key]["raw_utf8"].encode("utf-8"))
    dp = tmp_path / "decisions.json"
    dp.write_text(json.dumps(decisions), encoding="utf-8")
    sources = [Path(inputs[k]["path"]) for k in ("sheet1", "sheet2", "template")] + [dp]
    before = [p.read_bytes() for p in sources]
    output = tmp_path / "release.json"
    output.write_bytes(b"previous release\r\n")
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/research/reviewed_parameter_release.py"),
            "export",
            "--sheet1",
            str(sources[0]),
            "--sheet2",
            str(sources[1]),
            "--template",
            str(sources[2]),
            "--decisions",
            str(dp),
            "--output",
            str(output),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1, result.stdout
    assert field in result.stderr
    assert output.read_bytes() == b"previous release\r\n"
    assert [p.read_bytes() for p in sources] == before


@pytest.mark.parametrize("word", ["pending", "unresolved", "tbd", "todo"])
def test_release_preserves_rater_prose_and_optional_metadata(tmp_path, word):
    inputs = declared_test_inputs(tmp_path)
    for i in (1, 2):

        def change(sheet, sheet_number=i):
            rater = sheet["rater"]
            # Existing #170 identity restrictions still exclude pending substrings.
            if word != "pending":
                rater["evaluator"] += f"-{word}"
                for group in tool.GROUPS.values():
                    for record in sheet[group]:
                        record["evaluator"] = rater["evaluator"]
            for field in ("name", "competence_and_scope", "independence_declaration"):
                rater[field] = f"Test-only declaration resolved earlier {word} metadata."
            for field in ("organization", "signature"):
                if sheet_number == 1:
                    rater.pop(field, None)
                else:
                    rater[field] = None

        rewrite_snapshot(inputs[f"sheet{i}"], change)
    decisions = synthetic_decisions(inputs)
    decisions["evidence_class"] = "declared_independent_ratings"
    before = copy.deepcopy(inputs)
    release = tool.export_release(inputs, decisions)
    assert release["provenance"]["inputs"] == before
    assert release["governance"]["human_acceptance"] == "pending"
    assert tool.validate_and_sensitivity(release)["validation_status"] == "passed"
