"""Independent #274 review regressions; no counterfactual executor or metrics producer."""

from pathlib import Path

import pytest

from scripts.research.remediation_acceptance import read, validate_result

FIX = Path(__file__).parent / "fixtures/remediation"


def surviving_result():
    return read(FIX / "result-bypass-v1.1.json")


def test_required_surviving_bypass_cannot_be_omitted():
    result = surviving_result()
    validate_result(result)
    result["cells"][0]["bypass_program_ids"] = []
    with pytest.raises(ValueError, match="bypass"):
        validate_result(result)


def test_generated_id_churn_does_not_create_new_semantic_program():
    result = surviving_result()
    after = result["cells"][0]["after"]
    after["witness_program_ids"] = ["rerun-native-id"]
    after["trace_refs"][0]["program_id"] = "rerun-native-id"
    result["cells"][0]["bypass_program_ids"] = ["rerun-native-id"]
    # Identical actions/evidence are retained even when the generator changes the ID.
    validate_result(result)


def reused_id_result():
    result = surviving_result()
    cell = result["cells"][0]
    cell["after"]["witness_program_ids"] = ["alice-MD"]
    cell["after"]["trace_refs"][0]["program_id"] = "alice-MD"
    cell["bypass_program_ids"] = ["alice-MD"]
    cell["new_program_ids"] = ["alice-MD"]
    # The reused reference points at the direct program, while the old reference was M/D.
    cell["before"]["trace_refs"] = cell["before"]["trace_refs"][1:]
    cell["before"].update(
        witness_program_ids=["alice-MD", "alice-MI"],
        route_ids=["route-alice-MD", "route-alice-MI"],
        program_count=2,
        route_count=2,
    )
    result["summary"]["programs_cut"].update(denominator=3, percent=100)
    result["summary"]["routes_cut"].update(denominator=3, percent=100)
    cell["before"].update(complete=False, truncated=True)
    result["summary"]["truncated_pairs"] = 1
    for name in ("programs_cut", "routes_cut", "pairs_disconnected"):
        result["summary"][name]["scope"] = "observed_corpus_only"
    return result


def test_generated_id_reuse_does_not_hide_a_new_semantic_program():
    result = reused_id_result()
    validate_result(result)
    result["cells"][0]["new_program_ids"] = []
    with pytest.raises(ValueError, match="normalized semantic identity"):
        validate_result(result)


def test_new_bypass_cannot_be_omitted_even_with_reused_native_id():
    result = reused_id_result()
    validate_result(result)
    result["cells"][0]["bypass_program_ids"] = []
    with pytest.raises(ValueError, match="bypass"):
        validate_result(result)


@pytest.mark.parametrize("field", ["participants", "prerequisite", "context", "evidence", "order"])
def test_identity_distinguishes_semantic_bindings(field):
    from scripts.research.remediation_acceptance import normalized_program_identity

    result = surviving_result()
    cell = result["cells"][0]
    trace = cell["before"]["trace_refs"][1]
    original = normalized_program_identity(cell, result["comparison_scope_digest"], trace)
    if field == "participants":
        trace["semantic_program"][0]["participants"]["resource"] = "different-resource"
    elif field == "prerequisite":
        trace["semantic_program"][0]["prerequisites"][0]["subject"] = "different-subject"
    elif field == "context":
        trace["semantic_program"][0]["context"]["horizon"] = "different-horizon"
    elif field == "evidence":
        trace["semantic_program"][0]["evidence_bindings"][0]["reference"] = "different-evidence"
    else:
        trace["semantic_program"].reverse()
    assert normalized_program_identity(cell, result["comparison_scope_digest"], trace) != original


def test_identity_ignores_native_references_and_unordered_set_order():
    from scripts.research.remediation_acceptance import normalized_program_identity

    result = surviving_result()
    cell = result["cells"][0]
    trace = cell["before"]["trace_refs"][0]
    original = normalized_program_identity(cell, result["comparison_scope_digest"], trace)
    trace.update(program_id="different-native-id", trace_ref="different-run-location")
    trace["semantic_program"][0]["prerequisites"].reverse()
    assert normalized_program_identity(cell, result["comparison_scope_digest"], trace) == original


def test_missing_prerequisite_binding_is_rejected():
    result = surviving_result()
    result["cells"][0]["after"]["trace_refs"][0]["semantic_program"][0]["prerequisites"].pop()
    result["cells"][0]["new_program_ids"] = ["alice-D"]
    with pytest.raises(ValueError, match="prerequisite"):
        validate_result(result)


@pytest.mark.parametrize("status", ["not_run", "unknown", "error", "truncated"])
def test_empty_after_witnesses_need_complete_bypass_rediscovery(status):
    result = read(FIX / "result-v1.1.json")
    result["cells"][0]["after"]["rediscovery"]["status"] = status
    with pytest.raises(ValueError, match="rediscovery"):
        validate_result(result)


def test_truncated_success_retains_bypass_without_disconnection_claim():
    result = surviving_result()
    after = result["cells"][0]["after"]
    after.update(complete=False, truncated=True)
    after["rediscovery"]["status"] = "truncated"
    result["summary"]["truncated_pairs"] = 1
    for name in ("programs_cut", "routes_cut", "pairs_disconnected"):
        result["summary"][name]["scope"] = "observed_corpus_only"
    validate_result(result)
    assert result["cells"][0]["bypass_program_ids"] == ["alice-D"]
    assert not result["cells"][0]["disconnected"]


def test_legacy_result_cannot_pass_current_acceptance_gate():
    with pytest.raises(ValueError):
        validate_result(read(FIX / "result-v1.json"))


@pytest.mark.parametrize("field", ["action", "prerequisite"])
def test_support_bindings_cannot_be_erased_from_identity(field):
    result = surviving_result()
    for cell in result["cells"]:
        for side in ("before", "after"):
            for trace in cell[side]["trace_refs"]:
                for action in trace["semantic_program"]:
                    if field == "action":
                        action["evidence_bindings"] = []
                    else:
                        for gate in action["prerequisites"]:
                            gate["evidence_bindings"] = []
    with pytest.raises(ValueError):
        validate_result(result)


@pytest.mark.parametrize("status", ["not_run", "unknown", "error"])
@pytest.mark.parametrize("truncated", [False, True])
def test_incomplete_rediscovery_cannot_certify_after_flags(status, truncated):
    result = surviving_result()
    after = result["cells"][0]["after"]
    after.update(complete=not truncated, truncated=truncated)
    after["rediscovery"].update(status=status, run_id=None, proof_ref=None)
    result["summary"]["truncated_pairs"] = int(truncated)
    for name in ("programs_cut", "routes_cut", "pairs_disconnected"):
        result["summary"][name]["scope"] = "observed_corpus_only"
    with pytest.raises(ValueError, match="rediscovery"):
        validate_result(result)


@pytest.mark.parametrize("complete,truncated", [(True, False), (False, False)])
def test_truncated_rediscovery_requires_matching_incomplete_flags(complete, truncated):
    result = surviving_result()
    after = result["cells"][0]["after"]
    after.update(complete=complete, truncated=truncated)
    after["rediscovery"]["status"] = "truncated"
    for name in ("programs_cut", "routes_cut", "pairs_disconnected"):
        result["summary"][name]["scope"] = "observed_corpus_only"
    with pytest.raises(ValueError, match="rediscovery"):
        validate_result(result)


@pytest.mark.parametrize("status", ["not_run", "unknown", "error"])
def test_incomplete_rediscovery_remains_valid_without_complete_or_truncated_claim(status):
    result = surviving_result()
    after = result["cells"][0]["after"]
    after["complete"] = False
    after["rediscovery"].update(status=status, run_id=None, proof_ref=None)
    for name in ("programs_cut", "routes_cut", "pairs_disconnected"):
        result["summary"][name]["scope"] = "observed_corpus_only"
    validate_result(result)
    assert not result["cells"][0]["disconnected"]


@pytest.mark.parametrize("mismatched", [False, True])
def test_comparable_probability_is_bound_to_the_result_scope(mismatched):
    result = surviving_result()
    # Reuse issue250's existing synthetic intervals; no production P adoption.
    result["cells"][0]["conditional_p"].update(
        status="comparable",
        before_interval=[0.75, 0.75],
        after_interval=[0.25, 0.25],
        delta_interval=[-0.5, -0.5],
        before_program_id="alice-MI",
        after_program_id="alice-D",
        comparison_scope_digest=(
            "sha256:" + "0" * 64 if mismatched else result["comparison_scope_digest"]
        ),
        basis_refs=["synthetic://issue250/P"],
    )
    if mismatched:
        with pytest.raises(ValueError, match="scope"):
            validate_result(result)
    else:
        validate_result(result)


@pytest.mark.parametrize("field,value", [("run_id", "different-after-run"), ("proof_ref", None)])
def test_complete_rediscovery_requires_matching_run_and_proof(field, value):
    result = surviving_result()
    result["cells"][0]["after"]["rediscovery"][field] = value
    with pytest.raises(ValueError, match="rediscovery"):
        validate_result(result)
