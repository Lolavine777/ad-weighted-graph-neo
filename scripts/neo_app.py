"""Run NEO as a local analysis app: open an export, search, find paths, try a removal.

The server answers only this machine. It never takes a file path from the page: the page
picks from the datasets listed here or uploads a zip, and nothing is sent anywhere else.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import tempfile
import threading
import traceback
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit

from scripts.neo_workspace import ChooseExport, list_sources, open_dataset

ROOT = Path(__file__).resolve().parents[1]
VIEWER = ROOT / "web/neo-viewer"
STATIC = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/index.html": ("index.html", "text/html; charset=utf-8"),
    "/style.css": ("style.css", "text/css; charset=utf-8"),
    "/model.js": ("model.js", "text/javascript; charset=utf-8"),
    "/demo.js": ("demo.js", "text/javascript; charset=utf-8"),
    "/app.js": ("app.js", "text/javascript; charset=utf-8"),
    "/workspace.js": ("workspace.js", "text/javascript; charset=utf-8"),
}
MAX_JSON_BYTES = 64 * 1024
MAX_UPLOAD_BYTES = 2 * 1024**3
SCENARIOS = {"identity", "host-compromise"}
REQUEST_HEADER = "X-Neo-Request"  # A cross-site form cannot set this without a CORS preflight.


class Refused(Exception):
    def __init__(self, status, message):
        super().__init__(message)
        self.status = status


class AppState:
    """One opened dataset. A lock keeps a second heavy job from starting beside the first."""

    def __init__(self, data_dir):
        self.data_dir = Path(data_dir)
        self.workspace = None
        self.job = threading.Lock()

    def sources(self):
        return [
            {"id": i, "name": s["name"], "export": s["export"], "domains": s["domains"]}
            for i, s in enumerate(list_sources(self.data_dir))
        ]

    def require_workspace(self):
        if self.workspace is None:
            raise Refused(HTTPStatus.CONFLICT, "Chưa mở bộ dữ liệu nào.")
        return self.workspace

    def opened(self):
        workspace = self.workspace
        if workspace is None:
            return None
        return {"report": workspace.report, "targets": workspace.targets()}

    def open_listed(self, source_id, export):
        listed = list_sources(self.data_dir)
        if not isinstance(source_id, int) or not 0 <= source_id < len(listed):
            raise Refused(HTTPStatus.BAD_REQUEST, "Không có bộ dữ liệu này.")
        entry = listed[source_id]
        self.workspace = open_dataset(
            entry["path"], export=export or entry["export"], name=entry["domains"][0]
        )
        return self.opened()

    def open_upload(self, stream, length, name, export=None):
        with tempfile.TemporaryDirectory(prefix="neo-upload-") as directory:
            archive = Path(directory).resolve() / "upload.zip"
            with archive.open("wb") as file:
                remaining = length
                while remaining:
                    chunk = stream.read(min(1024 * 1024, remaining))
                    if not chunk:
                        raise Refused(HTTPStatus.BAD_REQUEST, "Tệp tải lên bị ngắt giữa chừng.")
                    file.write(chunk)
                    remaining -= len(chunk)
            self.workspace = open_dataset(archive, export=export, name=name)
        return self.opened()


def _text(body, key):
    value = body.get(key)
    if not isinstance(value, str) or not value:
        raise Refused(HTTPStatus.BAD_REQUEST, f"Thiếu trường {key}.")
    return value


def _scenario(body):
    scenario = body.get("scenario", "identity")
    if scenario not in SCENARIOS:
        raise Refused(HTTPStatus.BAD_REQUEST, "Giả định ban đầu không hợp lệ.")
    return scenario


def make_handler(state, allowed_hosts):
    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"
        server_version = "neo"
        sys_version = ""

        def log_message(self, *args):
            pass  # Requests name AD objects; they do not belong in a terminal scrollback.

        def _send(self, status, body, content_type):
            self.send_response(status)
            if self.command == "POST":
                # A refusal may leave the body unread; it must not be parsed as the next request.
                self.send_header("Connection", "close")
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header(
                "Content-Security-Policy",
                "default-src 'self'; style-src 'self' 'unsafe-inline'; "
                "base-uri 'none'; form-action 'none'; frame-ancestors 'none'",
            )
            self.end_headers()
            self.wfile.write(body)

        def _json(self, payload, status=HTTPStatus.OK):
            body = json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8")
            self._send(status, body, "application/json; charset=utf-8")

        def _guard(self):
            # Refusing other Host values stops a web page reaching this port by DNS rebinding.
            if self.headers.get("Host") not in allowed_hosts:
                raise Refused(HTTPStatus.FORBIDDEN, "Máy chủ này chỉ phục vụ trên máy cục bộ.")

        def _guard_write(self):
            origin = self.headers.get("Origin")
            if origin is not None and urlsplit(origin).netloc not in allowed_hosts:
                raise Refused(HTTPStatus.FORBIDDEN, "Yêu cầu không đến từ trang của ứng dụng.")
            if self.headers.get(REQUEST_HEADER) != "1":
                raise Refused(HTTPStatus.FORBIDDEN, "Yêu cầu không đến từ trang của ứng dụng.")

        def _length(self, limit):
            try:
                length = int(self.headers.get("Content-Length", ""))
            except ValueError:
                raise Refused(HTTPStatus.LENGTH_REQUIRED, "Thiếu độ dài dữ liệu.") from None
            if length < 0 or length > limit:
                raise Refused(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, "Dữ liệu gửi lên quá lớn.")
            return length

        def _body(self):
            raw = self.rfile.read(self._length(MAX_JSON_BYTES))
            try:
                body = json.loads(raw)
            except ValueError:
                raise Refused(HTTPStatus.BAD_REQUEST, "Dữ liệu gửi lên không hợp lệ.") from None
            if not isinstance(body, dict):
                raise Refused(HTTPStatus.BAD_REQUEST, "Dữ liệu gửi lên không hợp lệ.")
            return body

        def _respond(self, action):
            try:
                self._guard()
                action()
            except ConnectionError:
                self.close_connection = True  # The page went away; there is nobody to tell.
            except Refused as refusal:
                self._json({"error": str(refusal)}, refusal.status)
            except ChooseExport as choice:
                self._json({"error": str(choice), "exports": choice.exports}, HTTPStatus.CONFLICT)
            except ValueError as error:
                self._json({"error": str(error)}, HTTPStatus.BAD_REQUEST)
            except Exception:
                traceback.print_exc()
                self._json(
                    {"error": "Lỗi trong khi xử lý; xem chi tiết ở cửa sổ chạy ứng dụng."},
                    HTTPStatus.INTERNAL_SERVER_ERROR,
                )

        def do_GET(self):
            self._respond(self._get)

        def do_POST(self):
            self._respond(self._post)

        def _get(self):
            url = urlsplit(self.path)
            query = parse_qs(url.query)
            if url.path in STATIC:
                name, content_type = STATIC[url.path]
                content = (VIEWER / name).read_bytes()
                if name == "index.html":
                    # Pages and the offline copy never load this script, so they stay read-only.
                    content = content.replace(
                        b'<script src="app.js"></script>',
                        b'<script src="app.js"></script>\n    <script src="workspace.js"></script>',
                    )
                self._send(HTTPStatus.OK, content, content_type)
            elif url.path == "/api/status":
                self._json({"sources": state.sources(), "opened": state.opened()})
            elif url.path == "/api/search":
                text = query.get("q", [""])[0]
                self._json({"results": state.require_workspace().search(text)})
            elif url.path == "/api/neighbors":
                node = query.get("id", [""])[0]
                try:
                    self._json(state.require_workspace().neighbors(node))
                except KeyError:
                    raise Refused(HTTPStatus.NOT_FOUND, "Không có đối tượng này.") from None
            else:
                raise Refused(HTTPStatus.NOT_FOUND, "Không có trang này.")

        def _post(self):
            self._guard_write()
            path = urlsplit(self.path).path
            actions = {
                "/api/open": self._open,
                "/api/upload": self._upload,
                "/api/paths": self._paths,
                "/api/remove": self._remove,
            }
            if path not in actions:
                raise Refused(HTTPStatus.NOT_FOUND, "Không có trang này.")
            if not state.job.acquire(blocking=False):
                raise Refused(HTTPStatus.CONFLICT, "Đang chạy một phép tính khác; hãy đợi xong.")
            try:
                actions[path]()
            finally:
                state.job.release()

        def _open(self):
            body = self._body()
            self._json(state.open_listed(body.get("source"), body.get("export")))

        def _upload(self):
            length = self._length(MAX_UPLOAD_BYTES)
            raw_name = unquote(self.headers.get("X-File-Name", "upload"))
            # The name is only a display label for the analyst; never a path on this machine.
            name = re.sub(r"[^\w.-]+", "_", Path(raw_name).stem)[:80] or "upload"
            export = unquote(self.headers.get("X-Neo-Export", "")) or None
            self._json(state.open_upload(self.rfile, length, name, export))

        def _paths(self):
            body = self._body()
            workspace = state.require_workspace()
            self._json(
                workspace.find_paths(
                    _text(body, "source"), _text(body, "target"), scenario=_scenario(body)
                )
            )

        def _remove(self):
            body = self._body()
            workspace = state.require_workspace()
            self._json(
                workspace.try_removal(
                    _text(body, "edge_source"),
                    _text(body, "edge_kind"),
                    _text(body, "edge_target"),
                    _text(body, "source"),
                    _text(body, "target"),
                    scenario=_scenario(body),
                )
            )

    return Handler


class LocalServer(ThreadingHTTPServer):
    def handle_error(self, request, client_address):
        if not isinstance(sys.exc_info()[1], ConnectionError):
            super().handle_error(request, client_address)


def create_server(data_dir, port=0):
    """Bind to loopback only; ``port=0`` lets the system pick a free one."""
    state = AppState(data_dir)
    server = LocalServer(("127.0.0.1", port), None)
    actual = server.server_address[1]
    allowed = {f"127.0.0.1:{actual}", f"localhost:{actual}"}
    server.RequestHandlerClass = make_handler(state, allowed)
    server.state = state
    return server


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=ROOT / "data/raw",
        help="Folder whose exports the app offers to open",
    )
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args(argv)
    server = create_server(args.data_dir, args.port)
    url = f"http://127.0.0.1:{server.server_address[1]}/"
    print(f"NEO đang chạy tại {url}  (Ctrl+C để dừng)", flush=True)
    if not args.no_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
