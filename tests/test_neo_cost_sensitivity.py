"""C sensitivity changes prices, never feasibility or unique-work accounting."""

from copy import deepcopy

import pytest

from scripts.neo_cost_sensitivity import compare, reprice, variants
from src.engine.ranking.effort_profiles import load_effort_profile


def program(identifier, *techniques):
    ids = [f"u{i}" for i in range(len(techniques))]
    return {
        "program_id": identifier,
        "program_key": identifier,
        "work_unit_ids": ids,
        "work_unit_ledger": {
            uid: {"technique": technique, "classification": "active_work"}
            for uid, technique in zip(ids, techniques, strict=True)
        },
    }


def test_declared_variants_are_valid_distinct_and_do_not_mutate_profile():
    profile = load_effort_profile("neo-c-v1")
    original = deepcopy(profile)
    cases = variants()
    assert len(cases) == 18
    assert profile == original
    assert cases["baseline"] == profile["classes"]
    assert len({str(v) for v in cases.values()}) == 18
    for classes in cases.values():
        for cls in classes.values():
            assert 1 <= cls["t1"] <= 3 and 1 <= cls["t2"] <= 3
            assert cls["cost"] == cls["t1"] + cls["t2"] - 2


def test_work_units_are_deduplicated_and_zero_activation_stays_zero():
    p = program("reset", "scenario_reset_password", "acquire_reset_identity")
    p["work_unit_ids"].append("u0")
    assert reprice(p, variants()["baseline"]) == 1
    assert reprice(program("entitlement"), variants()["baseline"]) == 0


@pytest.mark.parametrize(
    "damage", ["missing_ledger", "unknown_class", "invalid_rubric", "cost_mismatch"]
)
def test_unrated_or_invalid_inputs_are_rejected(damage):
    p = program("reset", "scenario_reset_password")
    classes = variants()["baseline"]
    if damage == "missing_ledger":
        p["work_unit_ledger"].clear()
    elif damage == "unknown_class":
        p["work_unit_ledger"]["u0"]["technique"] = "unrated_action"
    elif damage == "invalid_rubric":
        classes["scenario_reset_password"]["t2"] = 0
    else:
        classes["scenario_reset_password"]["cost"] = 123
    with pytest.raises(ValueError):
        reprice(p, classes)


def test_hand_computed_stress_reverses_acl_and_reset_routes():
    programs = [
        program("acl", "grant_new_object_right", "genericall_add_member"),
        program("reset", "scenario_reset_password", "acquire_reset_identity"),
    ]
    report = compare(programs, variants()["reset_dearer_acl_cheaper"])
    assert report["minimum_C"] == 1
    assert report["best_program_ids"] == ["acl"]
    assert report["best_set_disjoint"] is True
    assert report["strict_rank_reversals"] == 1


def test_new_tie_is_not_reported_as_strict_rank_reversal():
    programs = [
        program("acl", "grant_new_object_right", "genericall_add_member"),
        program("reset", "scenario_reset_password", "acquire_reset_identity"),
    ]
    classes = variants()["baseline"]
    for name in ("scenario_reset_password", "acquire_reset_identity"):
        classes[name]["t2"] += 1
        classes[name]["cost"] += 1
    report = compare(programs, classes)
    assert report["best_program_ids"] == ["acl", "reset"]
    assert report["best_set_changed"] is True
    assert report["best_set_disjoint"] is False
    assert report["strict_rank_reversals"] == 0


def test_no_witness_does_not_become_a_zero_cost_program():
    assert compare([], variants()["baseline"]) is None


@pytest.mark.parametrize("scenario", ["identity", "host-compromise"])
def test_fixed_scope_checked_before_real_query_compilation(monkeypatch, tmp_path, scenario):
    import json
    from types import SimpleNamespace

    from scripts import neo_cost_sensitivity as probe

    pack = json.loads(
        (probe.ROOT / "reports/neo/bloodhound-query-pack.json").read_text(encoding="utf-8")
    )
    snapshot = tmp_path / "snapshot.json"
    snapshot.write_text("{}")
    pack["datasets"]["seamless"]["snapshot_sha256"] = probe.digest(snapshot.read_bytes())
    pack["datasets"]["seamless"]["scenario"] = scenario
    path = tmp_path / "pack.json"
    path.write_text(json.dumps(pack))
    control = [
        program("acl", "grant_new_object_right", "genericall_add_member"),
        program("reset", "scenario_reset_password", "acquire_reset_identity"),
    ]
    monkeypatch.setattr(probe, "programs_for", lambda *args: (control, {}))
    monkeypatch.setattr(probe.EngineGraph, "from_snapshot", lambda text: None)

    class CompilationReached(Exception):
        pass

    def compile_query(*args, **kwargs):
        raise CompilationReached("Valid JSON scope reached compilation")

    dataset = pack["datasets"]["seamless"]
    monkeypatch.setattr(
        probe,
        "scenario_profile",
        lambda *args: SimpleNamespace(canonical_dict=lambda: dataset["scenario_policy"]),
    )
    monkeypatch.setattr(probe, "techniques_for", lambda *args: tuple(dataset["techniques"]))
    monkeypatch.setattr(probe, "_query_for_cell", compile_query)
    args = SimpleNamespace(
        pack=path,
        seamless_snapshot=snapshot,
        wraith_snapshot=snapshot,
        output_dir=tmp_path / "output",
    )
    expected = ValueError if scenario == "host-compromise" else CompilationReached
    match = "Fixed cohort scope changed" if scenario == "host-compromise" else "Valid JSON scope"
    with pytest.raises(expected, match=match):
        probe.run(args)
