"""Evidence must preserve identities and distinguish no path from API failure."""

import pytest

from scripts.neo_bloodhound_live import canonical_id, ordered_path

SID = "S-1-5-21-1-2-3"
ADMIN = f"domain:sid:{SID}:S-1-5-32-544"


def test_alias_mapping_does_not_merge_other_domains():
    ids = {ADMIN, "S-1-5-11", "abcdefab-1234-1234-1234-123456789abc"}
    assert canonical_id("WRAITH.CORP-S-1-5-32-544", ids, SID, "WRAITH.CORP") == ADMIN
    assert canonical_id("S-1-5-32-544", ids, SID, "WRAITH.CORP") == ADMIN
    assert canonical_id("WRAITH.CORP-S-1-5-11", ids, SID, "WRAITH.CORP") == "S-1-5-11"
    assert canonical_id("OTHER.CORP-S-1-5-32-544", ids, SID, "WRAITH.CORP") != ADMIN
    assert canonical_id("ABCDEFAB-1234-1234-1234-123456789ABC", ids, SID, "WRAITH.CORP") in ids


def test_response_path_is_ordered_and_checked_from_declared_source():
    data = {
        "nodes": {str(i): {"objectId": name, "label": name} for i, name in enumerate("abc")},
        "edges": [
            {"id": "1", "source": "1", "target": "2", "kind": "MemberOf"},
            {"id": "0", "source": "0", "target": "1", "kind": "HasSession"},
        ],
    }
    path = ordered_path(data, "a", "c")
    assert [e["kind"] for e in path] == ["HasSession", "MemberOf"]
    with pytest.raises(ValueError, match="path"):
        ordered_path(data, "c", "a")
    data["edges"].append({"id": "2", "source": "0", "target": "2", "kind": "GenericAll"})
    with pytest.raises(ValueError, match="path"):
        ordered_path(data, "a", "c")


@pytest.mark.parametrize("committed", [False, True])
def test_failed_delete_restores_without_duplicating_existing_edge(monkeypatch, tmp_path, committed):
    from types import SimpleNamespace

    from scripts import neo_bloodhound_live as live

    sid = "S-1-5-21-1-2-3"
    graph = SimpleNamespace(
        nodes=lambda: (
            [
                {"id": name, "label": name + "@WRAITH.CORP"}
                for name in ("RODCMANAGER", "BM", "ADMINISTRATORS")
            ]
            + [{"id": "CA", "label": "EXTCA01.WRAITH.CORP"}]
        ),
        edges=lambda: [
            {"id": "edge", "source": "RODCMANAGER", "kind": "MemberOf", "target": "ADMINISTRATORS"}
        ],
        to_canonical=lambda: {"edges": []},
        snapshot_facts=None,
    )
    args = SimpleNamespace(output_dir=tmp_path, snapshot=tmp_path / "snapshot")
    pack = {
        "datasets": {
            "wraith": {
                "domain_sid": sid,
                "request": {},
                "scenario": "host-compromise",
                "pairs": [
                    {"source": "RODCMANAGER", "target": sid + suffix} for suffix in ("-512", "-519")
                ],
            }
        }
    }
    monkeypatch.setattr(live.native, "_initialize", lambda *a: None)
    monkeypatch.setattr(live.native, "_evaluate", lambda pair: {"status": "success"})
    monkeypatch.setattr(live, "graph_digest", lambda graph: "digest")
    monkeypatch.setattr(live.EngineGraph, "from_canonical", lambda *a, **kw: graph)
    monkeypatch.setattr(live, "bloodhound_query", lambda *a: {})
    edges = [{"props": {"isacl": False}}]
    monkeypatch.setattr(live.ce, "query_neo4j", lambda q: list(edges))

    def database(query, parameters):
        if "RETURN properties" in query:
            return list(edges)
        if "DELETE r" in query:
            if committed:
                edges.clear()
            raise RuntimeError("delete failed with uncertain commit")
        if "CREATE" in query or ("MERGE" in query and not edges):
            edges.append({"props": parameters["props"]})
        return []

    monkeypatch.setattr(live, "parameter_query", database)
    with pytest.raises(RuntimeError, match="delete failed with uncertain commit"):
        live.remediate(args, pack, graph, "token")
    assert len(edges) == 1


def test_endpoint_mismatch_prevents_login_and_writes(monkeypatch, tmp_path):
    import json
    from types import SimpleNamespace
    from unittest.mock import MagicMock

    from scripts import neo_bloodhound_live as live

    snapshot = tmp_path / "snapshot.json"
    snapshot.write_text("{}")
    pack = tmp_path / "pack.json"
    pack.write_text(
        json.dumps(
            {
                "datasets": {
                    "wraith": {
                        "snapshot_id": "snapshot",
                        "snapshot_sha256": live.digest(snapshot.read_bytes()),
                    }
                }
            }
        )
    )
    monkeypatch.setattr(
        live.EngineGraph,
        "from_snapshot",
        lambda s: SimpleNamespace(metadata={"snapshot_id": "snapshot"}),
    )
    monkeypatch.setattr(live.ce, "run_cmd", lambda cmd: "127.0.0.1:1")
    login = MagicMock(side_effect=AssertionError("must reject before login"))
    monkeypatch.setattr(live.ce, "login", login)
    output = tmp_path / "output"
    with pytest.raises(ValueError, match="Endpoint"):
        live.main(
            [
                "--pack",
                str(pack),
                "--snapshot",
                str(snapshot),
                "--dataset",
                "wraith",
                "--project-name",
                "isolated",
                "--output-dir",
                str(output),
                "--remediation",
            ]
        )
    login.assert_not_called()
    assert not output.exists()
