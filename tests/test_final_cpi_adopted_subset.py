"""Regress the real B subset, without simulated review authority."""

import copy
from fractions import Fraction

import pytest

from scripts.research.final_cpi_adoption_replay import load_inputs
from scripts.research.final_cpi_delivery_replay import ADOPTED_WAVE2, recount, validate_counts
from scripts.research.final_cpi_effort_release import RELEASE as EFFORT_RELEASE
from scripts.research.final_cpi_extension import prepare_extension
from scripts.research.final_cpi_profiles import PACKAGE, ROOT, read
from scripts.research.final_cpi_release import apply_release, validate_release
from src.engine import run_attack_query


@pytest.fixture(scope="module")
def contexts():
    raw = ROOT / "data/raw/SEAMLESS"
    if not raw.is_dir():
        pytest.skip("Manifest-verified raw required")
    graph, _ = load_inputs(raw)
    queries = {
        case["id"]: prepare_extension(case, graph, raw)[0]
        for case in read(PACKAGE / "supplementary-cohort.json")["queries"]
        if case["id"]
        in (
            "winrm-command",
            "acl-group-host",
            "rbcd-scoped",
            "acl-group-projection",
            "acl-group-all-generator",
        )
    }
    return queries, graph


def test_actual_authority_has_exact_subset_and_no_recovery_P():
    release = read(ADOPTED_WAVE2)
    assert release["review"]["reference"].endswith("issuecomment-6163909537")
    assert release["review"]["reviewer"] == "nairyuuu"
    assert {k for k, v in release["contexts"].items() if v["decision"] == "adopt"} == {
        "winrm-command",
        "acl-group-host",
        "rbcd-scoped",
        "kerberoast-material",
    }
    for name, value in (("asrep_password_recovery", 2), ("kerberoast_password_recovery", 3)):
        assert release["classes"][name]["C"]["decision"] == "adopt"
        assert release["classes"][name]["values"]["cost"] == value
        assert release["classes"][name]["P"]["decision"] == "needs_evidence"
    assert "recovered_identity_activation" not in release["classes"]


def test_adopted_contexts_validate_and_diagnostics_stay_withheld(contexts):
    queries, _ = contexts
    release = read(ADOPTED_WAVE2)
    for name in ("winrm-command", "acl-group-host", "rbcd-scoped"):
        validate_release(release, queries[name])
    for name in ("acl-group-projection", "acl-group-all-generator"):
        with pytest.raises(ValueError, match="context remains unadopted"):
            apply_release(queries[name], release)
        with pytest.raises(ValueError, match="context remains withheld"):
            apply_release(queries[name], read(EFFORT_RELEASE))


@pytest.mark.parametrize("field", ["horizon", "policy_id", "retry_policy", "control_scope"])
def test_actual_adoption_refuses_changed_history_or_policy(contexts, field):
    queries, _ = contexts
    changed = copy.deepcopy(queries["winrm-command"])
    changed["rating_resolution"]["scope"][field] = "changed"
    with pytest.raises(ValueError, match="query/context"):
        apply_release(changed, read(ADOPTED_WAVE2))


def test_real_non_admin_winrm_is_fully_rated_with_typed_command_goal(contexts):
    queries, graph = contexts
    bound = apply_release(queries["winrm-command"], read(ADOPTED_WAVE2))
    result = run_attack_query(bound, graph)
    assert result.final_goal_reached
    eligible = result.ranking_result["eligible_candidates"]
    assert len(result.paths) == len(eligible) == 1
    item = next(iter(eligible.values()))
    assert item["effort"] == 1
    assert list(map(Fraction, item["likelihood_interval"])) == [Fraction(7, 10), Fraction(19, 20)]
    assert item["impact"] == "Medium"
    assert not result.paths[0].final_state.admin_control


@pytest.mark.parametrize("field", ["fully_rated", "Pareto_eligible", "conditioned_feasible"])
def test_delivery_aggregator_refuses_impossible_counts(field):
    counts = dict(
        valid_generated=1,
        conditioned_feasible=1,
        C_rated=1,
        P_rated=0,
        I_rated=0,
        fully_rated=0,
        Pareto_eligible=0,
    )
    counts[field] = 2
    with pytest.raises(ValueError, match="checkpoint counts"):
        validate_counts(counts)


def test_independent_native_ledger_recount_preserves_partial_rating():
    summaries = {
        "a": {
            "semantic_status": "feasible",
            "c_complete": True,
            "p_complete": False,
            "i_complete": False,
            "numeric_complete": False,
        }
    }
    result = recount({"candidate_summaries": summaries}, {"eligible_candidates": {}}, 1)
    assert result["C_rated"] == 1
    assert result["fully_rated"] == result["Pareto_eligible"] == 0
