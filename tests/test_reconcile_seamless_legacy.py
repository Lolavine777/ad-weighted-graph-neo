"""Evidence classifications must not turn a same-name match into a diagnosis."""

import json

import pytest

from scripts.reconcile_graph_baseline import COMPARISON_SCOPE
from scripts.research import reconcile_seamless_legacy as audit_tool
from scripts.research.reconcile_seamless_legacy import classify_difference


def test_only_observed_raw_rules_explain_differences():
    primary = ("U", "MemberOf", "G")
    self_acl = ("G", "GenericAll", "G")
    unsupported = ("U", "GenericAll", "U")
    raw = {
        primary: [{"rule": "PrimaryGroupSid", "pointer": "users.json#/users/0/PrimaryGroupSid"}],
        self_acl: [{"rule": "Aces", "pointer": "groups.json#/groups/0/Aces/0"}],
    }
    assert classify_difference(primary, "legacy_only", raw, {}, {}) == "primary_group_input_gap"
    assert classify_difference(primary, "project_only", raw, {}, {}) == "unknown"
    assert classify_difference(self_acl, "project_only", raw, {}, {}) == "legacy_self_ace_filter"
    assert classify_difference(unsupported, "project_only", raw, {}, {}) == "unknown"
    assert classify_difference(("U", "Contains", "G"), "legacy_only", {}, {}, {}) == "out_of_scope"


def test_direct_host_evidence_survives_a_coalesced_nested_derivation():
    from scripts.research.reconcile_seamless_legacy import direct_host_view

    direct = ("U", "AdminTo", "H")
    derived = ("V", "AdminTo", "H")
    unexpected = ("X", "AdminTo", "H")
    edges = {
        direct: {"derivation": {"kind": "nested_membership"}},
        derived: {"derivation": {"kind": "nested_membership"}},
        unexpected: {},
    }
    raw = {direct: [{"rule": "LocalAdmins"}]}
    assert direct_host_view(set(edges), edges, raw) == {direct, unexpected}


def test_summary_keeps_unresolved_exact_identities_local():
    identity = "S-1-5-21-700-800-900-1101"  # Synthetic identity only.
    result = audit_tool.summarize_sets({"difference": [[identity, "MemberOf", identity]]})
    assert result["difference"]["count"] == 1
    assert identity not in json.dumps(result)


def test_every_destination_must_be_ignored_including_symlinks(tmp_path, monkeypatch):
    import subprocess

    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / ".gitignore").write_text("evidence.json\n.cache/\n")
    monkeypatch.setattr(audit_tool, "ROOT", tmp_path)
    with pytest.raises(ValueError, match="every output"):
        audit_tool.require_ignored(tmp_path, ("evidence.json", "comparator.json"))
    cache = tmp_path / ".cache"
    cache.mkdir()
    audit_tool.require_ignored(cache, ("evidence.json", "comparator.json"))
    (cache / "comparator.json").symlink_to(tmp_path / "tracked.json")
    with pytest.raises(ValueError, match="every output"):
        audit_tool.require_ignored(cache, ("evidence.json", "comparator.json"))


def test_audit_rejects_lifted_gate_and_malformed_assessments():
    # A synthetic test of the measured-input boundary, not real AD evidence.
    metadata = {
        "contract_version": "1.3.0",
        "weight_profile": "unit",
        "snapshot_id": "sha256:" + "1" * 64,
        "created_at": "2026-10-01T00:00:00Z",
        "code_version": "test-boundary",
        "synthetic": False,
        "comparison_scope": COMPARISON_SCOPE,
        "export_complete": True,
        "source_evidence": "synthetic test boundary",
    }
    nodes = [
        {
            "id": "S-1-5-21-700-800-900-1101",
            "kind": "User",
            "label": "SYNTHETIC-USER",
            "domain": "EXAMPLE.TEST",
            "is_boundary": False,
        }
    ]
    project = {"metadata": metadata, "nodes": nodes, "edges": [], "assessments": []}
    baseline = {
        "metadata": {**metadata, "export_complete": False},
        "nodes": nodes,
        "relationships": [],
    }
    audit_tool.audit(project, baseline, {}, {})
    metadata["synthetic"] = True
    with pytest.raises(ValueError, match="synthetic project refused"):
        audit_tool.validate_project(project)
    metadata["synthetic"] = False
    baseline["metadata"]["export_complete"] = True
    with pytest.raises(ValueError, match="pending full-semantics gate"):
        audit_tool.audit(project, baseline, {}, {})
    baseline["metadata"]["export_complete"] = False
    project["assessments"] = [
        {"status": "unknown", "reason": "required UserRights evidence is incomplete"}
    ]
    with pytest.raises(ValueError, match="missing required field"):
        audit_tool.audit(project, baseline, {}, {})
