"""Independent completeness and fail-closed gates for the #256 review package."""

import copy
import json
from pathlib import Path

import pytest

from src.engine.semantics import load_catalog

ROOT = Path(__file__).resolve().parents[1]
PACK = ROOT / "docs/research/ratings/likelihood-v1"


def test_every_supported_technique_has_an_explicit_disposition():
    assert (PACK / "catalog.json").is_file(), "Likelihood Catalog v1 is missing"
    data = json.loads((PACK / "catalog.json").read_text())
    actions = {item["technique_id"]: item for item in data["actions"]}
    assert len(actions) == len(data["actions"])
    assert set(actions) == {tech.id for tech in load_catalog()}
    for tech in load_catalog():
        entry = actions[tech.id]
        assert entry["relationship"] == tech.relationship
        assert entry["required_gates"] == list(tech.prerequisites)
        assert entry["success_effects"] == [effect.value for effect in tech.effects]
        if tech.action_required:
            assert entry["disposition"] in {
                "RATED",
                "REQUIRES_CONTEXT",
                "UNRATED_NO_BASIS",
                "OUT_OF_SCOPE",
            }
            assert entry["event_policy"] == "ACTIVE_Q_EVENT"
        else:
            assert entry["event_policy"] == "NO_Q_EVENT"
            assert entry["disposition"] == "NO_Q_EVENT"


def test_catalog_package_verifies_without_running_candidate_search():
    assert (PACK / "catalog.json").is_file(), "Likelihood Catalog v1 is missing"
    from scripts.research.likelihood_catalog import verify_package

    report = verify_package(ROOT)
    assert report["active_actions"] == 22
    assert report["passive_actions"] == 1
    assert report["numeric_activated"] == 0
    assert report["pending_bindings"] == 8


def test_generated_min_effort_matches_frozen_oracle_and_pending_gates():
    assert (ROOT / "scripts/research/likelihood_demo_probe.py").is_file(), "demo probe missing"
    from scripts.research.likelihood_demo_probe import probe_min_effort

    result = probe_min_effort()
    assert result["candidate_count"] == 3
    assert result["current_min_effort"] is None
    assert result["test_only_cost_multiset"] == [2, 5, 5]
    assert result["test_only_min_effort"] == 2
    assert result["passive_q_events"] == 0
    assert result["shared_work_units"] == 1
    assert result["production_numeric_acceptance"] is False


@pytest.mark.parametrize(
    "change", ["omit", "duplicate", "active_passive", "passive_active", "numeric"]
)
def test_catalog_rejects_incomplete_or_misclassified_coverage(change):
    from scripts.research.likelihood_catalog import validate_catalog

    data = json.loads((PACK / "catalog.json").read_text())
    if change == "omit":
        data["actions"].pop()
    elif change == "duplicate":
        data["actions"].append(copy.deepcopy(data["actions"][0]))
    elif change == "active_passive":
        data["actions"][0]["event_policy"] = "NO_Q_EVENT"
    elif change == "passive_active":
        next(a for a in data["actions"] if a["technique_id"] == "propagate_group_entitlement")[
            "event_policy"
        ] = "ACTIVE_Q_EVENT"
    else:
        data["actions"][0]["numeric_records"] = [{"lower": "1/2", "upper": "3/4"}]
    with pytest.raises(ValueError):
        validate_catalog(data, ROOT)


@pytest.mark.parametrize(
    "change",
    ["status", "key", "previous_hash", "order", "bounds", "retry", "resource", "source", "horizon"],
)
def test_binding_proposals_cannot_activate_or_change_context(change):
    from scripts.research.likelihood_catalog import validate_bindings

    data = json.loads((PACK / "bindings.json").read_text())
    record = data["records"][1]
    if change == "status":
        record["status"] = "accepted"
    elif change == "key":
        record["generated_lookup_key_digest"] = "sha256:" + "0" * 64
    elif change == "previous_hash":
        record["generated_lookup_key"]["ordered_work_prefix"][0] += ":changed"
    elif change == "order":
        record["generated_lookup_key"]["ordered_work_prefix"].reverse()
    elif change == "bounds":
        record["proposed_interval"] = ["1/2", "3/4"]
    elif change == "retry":
        record["context"]["retry_policy"]["by_mechanism"]["reset_password"]["max_attempts"] = 4
    else:
        field = {"resource": "resource_context", "source": "source_id", "horizon": "horizon"}[
            change
        ]
        record["generated_lookup_key"][field] = "different"
    with pytest.raises(ValueError):
        validate_bindings(data, ROOT)


@pytest.mark.parametrize(
    "field", ["budget", "previous_history", "canonical_class", "contradictory_resource"]
)
def test_binding_semantics_and_json_types_are_exact(field):
    from scripts.research.likelihood_catalog import validate_bindings

    data = json.loads((PACK / "bindings.json").read_text())
    record = data["records"][0]
    if field == "budget":
        record["generated_lookup_key"]["budget"] = 6.0
    elif field == "previous_history":
        record["conditioning_previous_successes"] = ["extra"]
    elif field == "contradictory_resource":
        record["context"]["resource_context"] = "undeclared_resource"
    else:
        record["canonical_class"] = "asrep_password_recovery"
    with pytest.raises(ValueError):
        validate_bindings(data, ROOT)


@pytest.mark.parametrize("case", ["source_a", "frozen_243"])
def test_private_generated_programs_preserve_independent_oracles(case):
    import os

    raw_dir = Path(os.environ.get("SEAMLESS_RAW_DIR", ROOT / "data/raw/SEAMLESS"))
    if not raw_dir.is_dir():
        pytest.skip("manifest-verified private SEAMLESS raw inputs required")
    from scripts.research.likelihood_demo_probe import probe_frozen_243, probe_source_a

    if case == "source_a":
        report = probe_source_a(raw_dir)
        assert report["reviewed_subset_count"] == 2
        assert report["current_context_P"] is None
        assert report["numeric_activation_permitted"] is False
    else:
        report = probe_frozen_243(raw_dir)
        assert report["candidate_count"] == 1
        assert report["current_P"] is None
        assert report["catalog_dispositions"][1] == "UNRATED_NO_BASIS"
        assert report["recovery_budget"] == "unmeasured-budget"


@pytest.mark.parametrize("change", ["I_scope", "manifest_omission", "source_pin_omission"])
def test_refreeze_cannot_bypass_semantic_or_coverage_checks(tmp_path, change):
    import hashlib
    import shutil

    from scripts.research.likelihood_catalog import PACKAGE, verify_package

    catalog = json.loads((PACK / "catalog.json").read_text())
    sources = list(catalog["source_pins"])
    sources += [str(PACK.relative_to(ROOT) / p.name) for p in PACK.glob("*.json")]
    for source in sources:
        destination = tmp_path / source
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / source, destination)
    copied_pack = tmp_path / PACKAGE
    if change == "I_scope":
        path = copied_pack / "release-dispositions.json"
        data = json.loads(path.read_text())
        data["I"][0]["scope"]["required_predicates"] = ["group_membership_only"]
        path.write_text(json.dumps(data))
    elif change == "source_pin_omission":
        path = copied_pack / "catalog.json"
        data = json.loads(path.read_text())
        data["source_pins"].pop("src/engine/search.py")
        path.write_text(json.dumps(data))
    path = copied_pack / "manifest.json"
    manifest = json.loads(path.read_text())
    for name in manifest["files"]:
        manifest["files"][name] = (
            "sha256:" + hashlib.sha256((copied_pack / name).read_bytes()).hexdigest()
        )
    if change == "manifest_omission":
        manifest["files"].pop("catalog.json")
    path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError):
        verify_package(tmp_path)


def test_proposed_provider_records_preserve_pending_and_match_merged_api():
    from scripts.research import likelihood_catalog
    from src.engine.ranking.likelihood import ReviewedScenarioLikelihoodProvider
    from src.engine.ranking.resolver import LikelihoodLookupKey

    assert hasattr(likelihood_catalog, "proposed_provider_records"), (
        "provider record adapter missing"
    )
    records = likelihood_catalog.proposed_provider_records()
    assert len(records) == 8
    provider = ReviewedScenarioLikelihoodProvider(records)
    for record in records:
        key_data = {k: v for k, v in record.items() if k in LikelihoodLookupKey.__annotations__}
        key_data["ordered_work_prefix"] = tuple(key_data["ordered_work_prefix"])
        key = LikelihoodLookupKey(**key_data)
        scope = {"query_id": record["applicable_queries"][0], "evaluation_mode": "scenario"}
        scope.update(
            {
                k: record[k]
                for k in (
                    "actor_capability",
                    "target_complexity_class",
                    "control_scope",
                    "retry_policy",
                    "target_population",
                )
            }
        )
        result = provider.resolve_likelihood(
            key, key.ordered_work_prefix, key.outcome_work_unit_id, scope
        )
        assert record["review_status"] == "proposed_pending_b_review"
        assert result.disposition == "refused"
        assert result.reason_code == "prerequisite_gate_refusal"
        assert result.reason_detail == (
            "Scenario record requires explicit accepted review_status and rated disposition"
        )
        assert result.value is None
