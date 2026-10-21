"""Synthetic checks for #196 replay boundaries, not real AD parity evidence."""

import pytest

from scripts.research.reproduce_seamless_legacy import accepted_slices, stable_comparator


def test_full_membership_and_direct_host_selection_keep_unexpected_rows():
    member = ("user", "MemberOf", "group")
    primary = ("user", "MemberOf", "primary")
    direct = ("group", "AdminTo", "host")
    derived = ("user", "AdminTo", "host")
    unexpected = ("extra", "CanPSRemote", "host")
    raw = {
        member: [{"rule": "Members"}],
        primary: [{"rule": "PrimaryGroupSid"}],
        direct: [{"rule": "LocalAdmins"}],
    }
    project = {member, primary, direct, derived, unexpected}
    edges = {t: {"derivation": {"kind": "nested_membership"}} for t in project}
    edges[unexpected] = {}
    result = accepted_slices(project, {member, primary, direct}, edges, raw)
    assert result["MemberOf"]["exact_sets_equal"]
    assert result["MemberOf"]["raw"] == {member, primary}
    assert result["AdminTo"]["project"] == {direct}
    assert result["CanPSRemote"]["project"] == {unexpected}
    assert not result["CanPSRemote"]["exact_sets_equal"]
    assert result["CanPSRemote"]["project_unexpected"] == {unexpected}


def test_nonself_selection_is_symmetric_and_does_not_hide_missing_raw_edges():
    self_ace = ("user", "GenericAll", "user")
    present = ("user", "GenericAll", "host")
    missing = ("group", "GenericAll", "host")
    raw = {t: [{"rule": "Aces"}] for t in (self_ace, present, missing)}
    result = accepted_slices({self_ace, present}, {present}, {}, raw)["GenericAll"]
    assert result["project"] == result["legacy"] == {present}
    assert result["raw_missing_project"] == result["raw_missing_legacy"] == {missing}
    assert not result["exact_sets_equal"]


def test_stable_comparator_removes_only_clock_and_keeps_gate_and_bindings():
    report = {"reconciliation_timestamp": "now", "verdict": "NOT_MEASURABLE", "digest": "abc"}
    assert stable_comparator(report) == {"verdict": "NOT_MEASURABLE", "digest": "abc"}
    assert report["reconciliation_timestamp"] == "now"


@pytest.mark.parametrize("existing", [True, False])
def test_replay_refuses_old_outputs_and_resolved_public_destinations(
    tmp_path, monkeypatch, existing
):
    from scripts.research import reproduce_seamless_legacy as replay

    out = tmp_path / "output"
    if existing:
        out.mkdir()
    monkeypatch.setattr(
        replay, "require_ignored", lambda *args: (_ for _ in ()).throw(ValueError("not ignored"))
    )
    with pytest.raises(ValueError, match="already exists" if existing else "not ignored"):
        replay.new_output(out)
    assert out.exists() is existing


def test_replay_checks_every_sensitive_destination_before_creating_directory(tmp_path, monkeypatch):
    import subprocess

    from scripts.research import reconcile_seamless_legacy as audit_tool
    from scripts.research import reproduce_seamless_legacy as replay

    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / ".gitignore").write_text("project.json\nevidence.json\nmanifest.json\n")
    monkeypatch.setattr(audit_tool, "ROOT", tmp_path)
    out = tmp_path / "selectively-ignored"
    with pytest.raises(ValueError, match="every output destination"):
        replay.new_output(out)
    assert not out.exists()
