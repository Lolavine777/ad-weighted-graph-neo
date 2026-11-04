"""The local app answers only this machine, only its own page, and walks the analyst's flow."""

import http.client
import io
import json
import threading
import zipfile
from pathlib import Path

import pytest

from scripts.neo_app import MAX_JSON_BYTES, create_server
from tests.test_neo_workspace import SID, _write_export

HEADERS = {"Content-Type": "application/json", "X-Neo-Request": "1"}


@pytest.fixture
def app(tmp_path):
    _write_export(tmp_path / "data" / "export")
    server = create_server(tmp_path / "data")
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield server
    server.shutdown()
    server.server_close()
    thread.join()


def call(app, method, path, body=None, headers=None, host=None):
    port = app.server_address[1]
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=30)
    payload = body if isinstance(body, (bytes, type(None))) else json.dumps(body).encode()
    sent = {"Host": host or f"127.0.0.1:{port}", **(HEADERS if headers is None else headers)}
    connection.request(method, path, payload, sent)
    response = connection.getresponse()
    raw = response.read()
    connection.close()
    try:
        return response.status, json.loads(raw), response
    except ValueError:
        return response.status, raw, response


def test_the_analyst_flow_opens_searches_finds_and_tries_a_removal(app):
    status, data, _ = call(app, "GET", "/api/status")
    assert status == 200 and data["opened"] is None
    assert data["sources"][0]["domains"] == ["A.LOCAL"]
    assert "path" not in data["sources"][0]  # The page never learns or supplies a disk path.

    status, opened, _ = call(app, "POST", "/api/open", {"source": 0})
    assert status == 200 and opened["report"]["nodes"]["User"] == 2
    assert {t["label"] for t in opened["targets"]} == {
        "DOMAIN ADMINS@A.LOCAL",
        "ENTERPRISE ADMINS@A.LOCAL",
    }

    status, found, _ = call(app, "GET", "/api/search?q=user2")
    assert status == 200 and found["results"][0]["id"] == f"{SID}-1002"

    status, around, _ = call(app, "GET", f"/api/neighbors?id={SID}-1002")
    assert status == 200 and around["counts"]["GenericAll"] == 1

    question = {"source": f"{SID}-1002", "target": f"{SID}-512"}
    status, answer, _ = call(app, "POST", "/api/paths", question)
    assert status == 200 and answer["outcome"] == "reachable"
    steps = [s["edge"] for s in answer["programs"][0]["steps"] if s["edge"]]
    edge = next(e for e in steps if e["kind"] == "GenericAll")
    assert answer["labels"][f"{SID}-512"]["label"] == "DOMAIN ADMINS@A.LOCAL"

    status, removal, _ = call(
        app,
        "POST",
        "/api/remove",
        {
            **question,
            "edge_source": edge["source"],
            "edge_kind": edge["kind"],
            "edge_target": edge["target"],
        },
    )
    assert status == 200 and removal["edit"]["status"] == "removed"
    assert removal["after"]["outcome"] == "blocked_in_scope"


def test_an_uploaded_zip_opens_without_touching_the_data_folder(app, tmp_path):
    folder = _write_export(tmp_path / "other", prefix="20250101000000")
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as bundle:
        for path in folder.iterdir():
            bundle.write(path, path.name)
    status, opened, _ = call(
        app,
        "POST",
        "/api/upload",
        buffer.getvalue(),
        {"X-Neo-Request": "1", "X-File-Name": "../../secret%20name.zip"},
    )
    assert status == 200 and opened["report"]["export"] == "20250101000000"
    assert opened["report"]["name"] == "secret_name"


def test_a_garbage_upload_is_refused_and_keeps_the_open_dataset(app):
    call(app, "POST", "/api/open", {"source": 0})
    status, data, _ = call(app, "POST", "/api/upload", b"not a zip", {"X-Neo-Request": "1"})
    assert status == 400 and "zip" in data["error"]
    status, data, _ = call(app, "GET", "/api/status")
    assert data["opened"]["report"]["domains"] == ["A.LOCAL"]


def test_only_this_machine_and_this_page_may_ask(app, capfd):
    assert call(app, "GET", "/api/status", host="attacker.example")[0] == 403
    assert call(app, "POST", "/api/open", {"source": 0}, {"Content-Type": "text/plain"})[0] == 403
    foreign = {**HEADERS, "Origin": "https://attacker.example"}
    status, _, response = call(app, "POST", "/api/open", {"source": 0}, foreign)
    assert status == 403 and response.getheader("Connection") == "close"
    assert "Traceback" not in capfd.readouterr().err  # The unread body is not a second request.


def test_the_page_cannot_name_a_file_or_escape_the_viewer_folder(app):
    assert call(app, "POST", "/api/open", {"source": "/etc/passwd"})[0] == 400
    assert call(app, "POST", "/api/open", {"source": 99})[0] == 400
    assert call(app, "GET", "/../../README.md")[0] == 404
    assert call(app, "GET", "/build.py")[0] == 404


def test_requests_before_opening_or_with_bad_fields_get_clear_refusals(app):
    assert call(app, "GET", "/api/search?q=x")[0] == 409
    assert call(app, "POST", "/api/paths", {"source": "a", "target": "b"})[0] == 409
    call(app, "POST", "/api/open", {"source": 0})
    assert call(app, "POST", "/api/paths", {"source": "a"})[0] == 400
    bad_scenario = {"source": "a", "target": "b", "scenario": "x"}
    assert call(app, "POST", "/api/paths", bad_scenario)[0] == 400
    assert call(app, "GET", "/api/neighbors?id=nobody")[0] == 404
    assert call(app, "POST", "/api/open", b"x" * (MAX_JSON_BYTES + 1))[0] == 413


def test_a_second_heavy_job_is_refused_while_one_runs(app):
    assert app.state.job.acquire(blocking=False)
    try:
        status, data, _ = call(app, "POST", "/api/open", {"source": 0})
    finally:
        app.state.job.release()
    assert status == 409 and "đợi" in data["error"]


def test_only_the_app_page_loads_the_analysis_screen(app):
    status, page, response = call(app, "GET", "/")
    assert status == 200 and b"workspace.js" in page
    assert response.getheader("X-Content-Type-Options") == "nosniff"
    published = Path("web/neo-viewer/index.html").read_text(encoding="utf-8")
    assert "workspace.js" not in published  # Pages and the offline copy stay read-only.
