"""The lab diagnostic must attempt every restore even after an uncertain response."""

import json
from types import SimpleNamespace

import pytest

from scripts import neo_truster_remediation as diagnostic


@pytest.mark.parametrize("committed", [False, True])
def test_run_attempts_all_restores_after_one_restore_fails(monkeypatch, tmp_path, committed):
    live = diagnostic.live
    nodes = [
        {"id": "truster", "label": "TRUSTER@WRAITH.CORP"},
        {"id": "bm", "label": "BM@WRAITH.CORP"},
        {"id": "ca", "label": "EXTCA01.WRAITH.CORP"},
        {"id": "uncon", "label": "UNCON.WRAITH.CORP"},
    ]
    edges = [
        {"id": host, "source": host, "kind": "HasSession", "target": "bm"}
        for host in ("ca", "uncon")
    ]
    graph = SimpleNamespace(
        nodes=lambda: nodes,
        edges=lambda **kw: edges,
        to_canonical=lambda: {"edges": list(edges)},
        snapshot_facts=None,
    )
    snapshot = tmp_path / "snapshot.json"
    snapshot.write_text("{}")
    pack = tmp_path / "pack.json"
    pack.write_text(
        json.dumps(
            {
                "datasets": {
                    "wraith": {
                        "snapshot_sha256": live.digest(snapshot.read_bytes()),
                        "request": {},
                        "scenario": "host-compromise",
                        "pairs": [{"source": "truster", "target": goal} for goal in ("da", "ea")],
                    }
                }
            }
        )
    )
    monkeypatch.setattr(diagnostic.EngineGraph, "from_snapshot", lambda text: graph)
    monkeypatch.setattr(
        live.ce,
        "run_cmd",
        lambda cmd: (
            live.ce.BLOODHOUND_URL.removeprefix("http://")
            if cmd[-2] == "bloodhound"
            else live.ce.NEO4J_URL.removeprefix("http://").removesuffix("/db/neo4j/tx/commit")
        ),
    )
    monkeypatch.setattr(live.ce, "get_admin_password", lambda **kw: "unused")
    monkeypatch.setattr(live.ce, "login", lambda password: "unused")
    monkeypatch.setattr(
        live.native, "_initialize", lambda *args: setattr(live.native, "_graph", graph)
    )
    monkeypatch.setattr(diagnostic, "graph_digest", lambda graph: "digest")
    monkeypatch.setattr(diagnostic.EngineGraph, "from_canonical", lambda graph, **kw: graph)
    monkeypatch.setattr(
        live.native,
        "_evaluate",
        lambda pair: {
            "status": "success",
            "reached": True,
            "C": 3,
            "expansions": 1,
        },
    )
    database = {host: {"collected": True} for host in ("ca", "uncon")}
    inventory_reads = []

    def inventory(query):
        inventory_reads.append(dict(database))
        return [{"source": k, "props": v} for k, v in sorted(database.items())]

    monkeypatch.setattr(live.ce, "query_neo4j", inventory)
    monkeypatch.setattr(
        live,
        "bloodhound_query",
        lambda *args: {
            "http_status": 200,
            "path": [{"target_label": "UNCON.WRAITH.CORP"}],
        },
    )
    deleted = []
    restored = []

    def query(statement, row):
        host = row["source"]
        if "RETURN properties" in statement:
            return [{"props": database[host]}]
        if "DELETE r" in statement:
            deleted.append(host)
            database.pop(host)
        if "MERGE" in statement:
            restored.append(host)
            if len(deleted) == 3 and len(restored) == 2:
                if committed:
                    database[host] = row["props"]
                raise RuntimeError("uncertain restore response")
            database[host] = row["props"]
        return []

    monkeypatch.setattr(live, "parameter_query", query)
    args = SimpleNamespace(
        snapshot=snapshot, pack=pack, project_name="isolated", output_dir=tmp_path / "output"
    )
    with pytest.raises((RuntimeError, AssertionError)):
        diagnostic.run(args)
    assert len(deleted) == 3
    assert len(restored) == 3, "A failed restore must not prevent the other restore"
    assert len(inventory_reads) == 3, "Verify the final digest even after a restore error"
    assert (args.output_dir / "both-sessions-restore-journal.json").exists()


def test_optimized_run_rejects_wrong_project_before_login(monkeypatch, tmp_path):
    from pathlib import Path
    from types import ModuleType

    optimized = ModuleType("optimized_diagnostic")
    source = Path(diagnostic.__file__).read_text()
    exec(compile(source, diagnostic.__file__, "exec", optimize=1), optimized.__dict__)
    snapshot = tmp_path / "snapshot.json"
    snapshot.write_text("{}")
    pack = tmp_path / "pack.json"
    pack.write_text(
        json.dumps(
            {
                "datasets": {
                    "wraith": {
                        "snapshot_sha256": diagnostic.live.digest(snapshot.read_bytes()),
                        "pairs": [{"source": "truster", "target": x} for x in ("da", "ea")],
                    }
                }
            }
        )
    )
    graph = SimpleNamespace(
        nodes=lambda: [
            {"id": "truster", "label": "TRUSTER@WRAITH.CORP"},
            {"id": "bm", "label": "BM@WRAITH.CORP"},
        ]
    )
    monkeypatch.setattr(optimized.EngineGraph, "from_snapshot", lambda text: graph)
    monkeypatch.setattr(optimized.live.ce, "run_cmd", lambda cmd: "127.0.0.1:1")

    def forbid_login(*args, **kwargs):
        pytest.fail("Wrong-project endpoint must be rejected before credential access")

    monkeypatch.setattr(optimized.live.ce, "get_admin_password", forbid_login)
    args = SimpleNamespace(
        snapshot=snapshot, pack=pack, project_name="wrong", output_dir=tmp_path / "output"
    )
    with pytest.raises(ValueError, match="Endpoint"):
        optimized.run(args)
    assert not args.output_dir.exists()
