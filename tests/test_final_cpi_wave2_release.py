"""Wave 2 fixtures exercise authority gates; none records a real B decision."""

import copy
import json
import subprocess
import sys
from dataclasses import replace

import pytest

from scripts.research.final_cpi_extension import prepare_extension
from scripts.research.final_cpi_profiles import PACKAGE, ROOT, read
from scripts.research.final_cpi_release import apply_release, template_wave2
from scripts.research.issue250_public_probe import frozen_inputs
from src.engine import run_attack_query
from src.engine.graph import EngineGraph


@pytest.fixture(scope="module")
def wave2():
    raw = ROOT / "data/raw/SEAMLESS"
    if not raw.is_dir():
        pytest.skip("Authorized manifest-verified raw required")
    graph, _, _ = frozen_inputs(raw, read(PACKAGE / "cohort.json")["baseline_revision"])
    release = template_wave2(graph, raw)
    case = next(
        c
        for c in read(PACKAGE / "supplementary-cohort.json")["queries"]
        if c["id"] == "winrm-command"
    )
    query, _ = prepare_extension(case, graph, raw)
    return query, graph, release


def simulated(release):
    release = copy.deepcopy(release)
    release["status"] = "adopted"
    release["review"].update(
        reviewer="test-only simulated B",
        reviewed_at="2000-01-01T00:00:00Z",
        reference="test://wave2/explicit-context-history-review",
        confirmation="TEST ONLY: adopt exact bounded contexts and histories",
    )
    release["history_decision"]["decision"] = "adopt"
    for context in release["contexts"].values():
        context["decision"] = "adopt"
    for entry in release["classes"].values():
        for dimension in ("C", "P"):
            if entry[dimension]["decision"] == "pending":
                entry[dimension]["decision"] = "adopt"
    for impact in release["impacts"].values():
        impact["decision"] = "adopt"
    return release


def test_wave2_pending_does_not_authorize_production(wave2):
    query, _, release = wave2
    before = copy.deepcopy(query)
    with pytest.raises(ValueError, match="pending B"):
        apply_release(query, release)
    assert query == before
    assert release["review"]["reference"] is None
    assert "recovered_identity_activation" not in release["classes"]
    assert release["classes"]["asrep_password_recovery"]["P"]["decision"] == "needs_evidence"


def test_wave2_template_refuses_same_graph_with_different_snapshot_facts(wave2):
    _, graph, _ = wave2
    altered = EngineGraph.from_canonical(
        graph.to_canonical(), snapshot_facts=replace(graph.snapshot_facts, facts=())
    )
    with pytest.raises(ValueError, match="exact manifest-verified raw graph"):
        template_wave2(altered, ROOT / "data/raw/SEAMLESS")


def test_numeric_comment_cannot_authorize_wave2_history(wave2):
    query, _, pending = wave2
    release = simulated(pending)
    release["review"]["reference"] = release["numeric_decision_reference"]
    with pytest.raises(ValueError, match="history"):
        apply_release(query, release)
    release = simulated(pending)
    release["history_decision"]["decision"] = "needs_evidence"
    with pytest.raises(ValueError, match="history"):
        apply_release(query, release)


def test_wave2_typed_command_is_medium_and_not_admin(wave2):
    query, graph, pending = wave2
    result = run_attack_query(apply_release(query, simulated(pending)), graph)
    assert len(result.paths) == 1
    ranked = result.ranking_result["eligible_candidates"]["generated_0001"]
    assert ranked["effort"] == 1
    assert ranked["likelihood_interval"] == ["7/10", "19/20"]
    assert ranked["impact"] == "Medium"


def test_wave2_context_can_be_withheld_after_class_numeric_approval(wave2):
    query, _, pending = wave2
    release = simulated(pending)
    release["contexts"]["winrm-command"]["decision"] = "needs_evidence"
    with pytest.raises(ValueError, match="context remains unadopted"):
        apply_release(query, release)


@pytest.mark.parametrize("field", ["horizon", "retry_policy", "control_scope"])
def test_wave2_context_mutation_cannot_inherit_adoption(wave2, field):
    query, _, pending = wave2
    changed = copy.deepcopy(query)
    changed["rating_resolution"]["scope"][field] = "different"
    with pytest.raises(ValueError, match="query/context"):
        apply_release(changed, simulated(pending))


@pytest.mark.parametrize("field", ["query_pins", "context_domains", "input_pins"])
def test_wave2_release_domain_mutation_is_refused(wave2, field):
    query, _, pending = wave2
    release = simulated(pending)
    release[field] = {}
    with pytest.raises(ValueError, match="pin mismatch"):
        apply_release(query, release)


def test_release_cli_preserves_existing_artifact(tmp_path):
    output = tmp_path / "frozen.json"
    output.write_text("frozen evidence\n")
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "scripts.research.final_cpi_release",
            "--template",
            "--output",
            str(output),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert output.read_text() == "frozen evidence\n"


def test_public_pending_artifact_keeps_private_goal_identifiers_local():
    pending = read(PACKAGE.parent / "final-cpi-release-v2/decisions.pending.json")
    assert all(
        "target_asset_id" not in domain["typed_goal"]
        for domain in pending["context_domains"].values()
    )
    assert "S-1-5-" not in json.dumps(pending)


@pytest.mark.parametrize("authority", ["numeric", "wave1"])
@pytest.mark.parametrize("variant", ["path_slash", "fragment_slash", "query", "http"])
def test_prior_authority_url_alias_cannot_authorize_wave2(wave2, authority, variant):
    query, _, pending = wave2
    release = simulated(pending)
    reference = (
        release["numeric_decision_reference"]
        if authority == "numeric"
        else read(PACKAGE.parent / "final-cpi-release-v1/decisions.adopted.json")["review"][
            "reference"
        ]
    )
    base, fragment = reference.split("#")
    if variant == "path_slash":
        reference = base + "/#" + fragment
    elif variant == "fragment_slash":
        reference += "/"
    elif variant == "query":
        reference = base + "?utm_source=review#" + fragment
    else:
        reference = reference.replace("https://", "http://")
    release["review"]["reference"] = reference
    with pytest.raises(ValueError, match="Prior numeric or Wave 1"):
        apply_release(query, release)


@pytest.mark.parametrize(
    "reference",
    [
        "http://github.com/nairyuuu/ad-weighted-graph/pull/271/",
        "https://github.com/nairyuuu/ad-weighted-graph/pull/266/?utm_source=review",
        "https://github.com/nairyuuu/ad-weighted-graph/pull/271/#pullrequestreview-5490113298",
    ],
)
def test_implementation_approval_url_alias_cannot_authorize_wave2(wave2, reference):
    query, _, pending = wave2
    release = simulated(pending)
    release["review"]["reference"] = reference
    with pytest.raises(ValueError, match="Implementation PR approval"):
        apply_release(query, release)
