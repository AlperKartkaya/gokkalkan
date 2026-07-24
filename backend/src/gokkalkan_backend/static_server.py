"""Dependency-free static operator UI server with a localhost API proxy."""

from __future__ import annotations

import argparse
import http.client
import json
import signal
import threading
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit


def build_static_server(
    host: str,
    port: int,
    *,
    root: str | Path,
    api_base: str,
) -> ThreadingHTTPServer:
    static_root = Path(root).resolve()
    parsed_api = urlsplit(api_base)
    if parsed_api.scheme != "http" or not parsed_api.hostname:
        raise ValueError("api_base must be an http URL")

    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *args: object, **kwargs: object) -> None:
            super().__init__(*args, directory=str(static_root), **kwargs)

        def do_GET(self) -> None:  # noqa: N802
            if self.path == "/healthz":
                body = b'{"ok":true,"service":"gokkalkan-static-ui"}'
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            if self.path.startswith("/api/"):
                self._proxy("GET")
                return
            requested = static_root / self.path.split("?", 1)[0].lstrip("/")
            if self.path != "/" and not requested.exists():
                self.path = "/index.html"
            super().do_GET()

        def do_POST(self) -> None:  # noqa: N802
            if self.path.startswith("/api/"):
                self._proxy("POST")
                return
            self.send_error(HTTPStatus.NOT_FOUND)

        def do_OPTIONS(self) -> None:  # noqa: N802
            if self.path.startswith("/api/"):
                self._proxy("OPTIONS")
                return
            self.send_error(HTTPStatus.NOT_FOUND)

        def log_message(self, format: str, *args: object) -> None:  # noqa: A002
            return

        def _proxy(self, method: str) -> None:
            length = int(self.headers.get("Content-Length", "0") or 0)
            body = self.rfile.read(length) if length else None
            upstream_path = self.path.removeprefix("/api") or "/"
            connection = http.client.HTTPConnection(
                parsed_api.hostname,
                parsed_api.port or 80,
                timeout=2.0,
            )
            headers = {
                "Content-Type": self.headers.get(
                    "Content-Type", "application/json"
                )
            }
            try:
                connection.request(method, upstream_path, body=body, headers=headers)
                response = connection.getresponse()
                payload = response.read()
                self.send_response(response.status)
                self.send_header(
                    "Content-Type",
                    response.getheader("Content-Type", "application/json"),
                )
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
            except OSError as exc:
                payload = json.dumps(
                    {"error": "backend_unavailable", "detail": str(exc)}
                ).encode("utf-8")
                self.send_response(HTTPStatus.BAD_GATEWAY)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
            finally:
                connection.close()

    return ThreadingHTTPServer((host, port), Handler)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Gökkalkan static operator UI")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=4173)
    parser.add_argument("--root", default="frontend/dist")
    parser.add_argument("--api", default="http://127.0.0.1:8088")
    args = parser.parse_args(argv)
    root = Path(args.root)
    if not (root / "index.html").is_file():
        parser.error(f"built frontend is missing: {root / 'index.html'}")

    server = build_static_server(
        args.host,
        args.port,
        root=root,
        api_base=args.api,
    )

    def stop(_signum: int, _frame: object) -> None:
        threading.Thread(target=server.shutdown, daemon=True).start()

    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)
    try:
        server.serve_forever()
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
