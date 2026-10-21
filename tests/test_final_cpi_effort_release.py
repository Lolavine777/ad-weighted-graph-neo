"""Existing B C decisions must not authorize a conditional-history extension."""

import copy

import pytest

from scripts.research.final_cpi_adoption_replay import load_inputs
from scripts.research.final_cpi_coverage import report_case
from scripts.research.final_cpi_effort_release import RELEASE, release_definition
from scripts.research.final_cpi_extension import prepare_extension
from scripts.research.final_cpi_profiles import PACKAGE, ROOT, read
from scripts.research.final_cpi_release import apply_release
from src.engine import run_attack_query
from src.engine.query_cli import wire


@pytest.fixture(scope="module")
def inputs():
    raw = ROOT / "data/raw/SEAMLESS"
    if not raw.is_dir():
        pytest.skip("Manifest-verified SEAMLESS required")
    graph, _ = load_inputs(raw)
    case = next(
        c
        for c in read(PACKAGE / "supplementary-cohort.json")["queries"]
        if c["id"] == "winrm-command"
    )
    query, _ = prepare_extension(case, graph, raw)
    return query, graph


def test_authorized_C_only_release_is_real_and_keeps_other_dimensions(inputs):
    query, graph = inputs
    release = read(RELEASE)
    assert release == release_definition()
    bound = apply_release(query, release)
    for role in ("likelihood", "impact", "impact_source"):
        assert (
            bound["rating_resolution"]["registries"][role]
            == query["rating_resolution"]["registries"][role]
        )
    before, after = run_attack_query(query, graph), run_attack_query(bound, graph)
    assert wire(before.paths) == wire(after.paths)
    counts = report_case(after)["counts"]
    assert counts["conditioned_feasible"] == counts["C_rated"] == 1
    assert counts["P_rated"] == counts["I_rated"] == counts["fully_rated"] == 0
    for unit in after.rating_coverage["candidates"]["generated_0001"]["effort"]["units"].values():
        assert unit["cost"] == 1
        assert unit["rating_audit"]["review_reference"] == release["authority"]["reference"]
        assert unit["rating_audit"]["numeric_basis_class"] == "estimated_expert_scenario"
    assert release["classes"]["asrep_password_recovery"]["C"]["cost"] == 2
    assert release["classes"]["kerberoast_password_recovery"]["C"]["cost"] == 3
    assert "recovered_identity_activation" not in release["classes"]


@pytest.mark.parametrize(
    "field", ["horizon", "retry_policy", "control_scope", "policy_id", "snapshot_id"]
)
def test_context_or_history_change_refuses_effort_binding(inputs, field):
    query, _ = inputs
    changed = copy.deepcopy(query)
    changed["rating_resolution"]["scope"][field] = "changed"
    with pytest.raises(ValueError, match="query/context"):
        apply_release(changed, read(RELEASE))


@pytest.mark.parametrize(
    "field", ["authority", "classes", "query_pins", "context_domains", "input_pins"]
)
def test_release_cannot_mint_authority_or_expand_scope(inputs, field):
    query, _ = inputs
    release = read(RELEASE)
    release[field] = {}
    with pytest.raises(ValueError, match="authority/domain"):
        apply_release(query, release)


def test_known_false_and_missing_policy_still_veto(inputs):
    query, graph = inputs
    bound = apply_release(query, read(RELEASE))
    # Missing/False facts are evaluated by the native evaluator, after release binding.
    for predicate in {f["predicate"] for f in bound["runtime_facts"]}:
        missing = copy.deepcopy(bound)
        missing["runtime_facts"] = [
            f for f in missing["runtime_facts"] if f["predicate"] != predicate
        ]
        assert not run_attack_query(missing, graph).paths
        denied = copy.deepcopy(bound)
        for fact in denied["runtime_facts"]:
            if fact["predicate"] == predicate:
                fact.update(value=False, origin="blocked_evidence")
        assert not run_attack_query(denied, graph).paths


def test_binding_cannot_create_host_admin_from_command(inputs):
    from scripts.research.final_cpi_delivery_replay import matrix

    query, graph = inputs
    bound = apply_release(query, read(RELEASE))
    result = run_attack_query(bound, graph)
    ledger = matrix(result, bound)
    program = ledger["programs"][0]
    assert program["terminal_I"]["disposition"] != "rated"
    assert program["steps"][0]["P"]["blocker"] == "approved-but-unbound"
    assert len(program["steps"][0]["conditional_question"]["full_history"]) == 1
    assert "S-1-5-" not in str(ledger)
