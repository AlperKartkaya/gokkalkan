"""No-dependency HTTP entrypoint for the Gökkalkan dry-run operator API."""

from __future__ import annotations

import argparse
import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import urlparse

from .operator_api import OperatorService
from .telemetry_log import JsonlTelemetryStore


class OperatorApiHandler(BaseHTTPRequestHandler):
    service: OperatorService | None = None
    server_version = "GokkalkanOperatorApi/0.1"

    def do_OPTIONS(self) -> None:  # noqa: N802 - http.server naming convention
        self._send_json({"ok": True})

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path == "/health":
            self._send_json(self.operator_service.health())
        elif path == "/state":
            self._send_json(self.operator_service.snapshot())
        elif path == "/events":
            self._send_json({"events": self.operator_service.events})
        elif path == "/telemetry/export":
            self._send_json(self.operator_service.telemetry_export())
        elif path == "/replay":
            self._send_json(self.operator_service.replay())
        else:
            self._send_json({"error": "not_found", "path": path}, HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        payload = self._read_json()
        if path == "/mode":
            self._send_json(self.operator_service.handle_mode_request(payload))
        elif path == "/manual-aim":
            self._send_json(self.operator_service.handle_manual_aim(payload))
        elif path == "/fire-intent":
            self._send_json(self.operator_service.handle_fire_intent(payload))
        elif path == "/telemetry/reset":
            self._send_json(self.operator_service.reset_telemetry())
        else:
            self._send_json({"error": "not_found", "path": path}, HTTPStatus.NOT_FOUND)

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002 - stdlib signature
        return

    @property
    def operator_service(self) -> OperatorService:
        if self.service is None:
            self.__class__.service = OperatorService()
        return self.service

    def _read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0") or 0)
        if length == 0:
            return {}
        raw = self.rfile.read(length)
        try:
            data = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError:
            return {}
        return data if isinstance(data, dict) else {}

    def _send_json(self, payload: dict[str, Any], status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(int(status))
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(body)


def build_http_server(
    host: str = "127.0.0.1",
    port: int = 8088,
    service: OperatorService | None = None,
    telemetry_jsonl: str | None = None,
) -> ThreadingHTTPServer:
    class BoundHandler(OperatorApiHandler):
        pass

    telemetry = JsonlTelemetryStore(telemetry_jsonl) if telemetry_jsonl else None
    BoundHandler.service = service or OperatorService(telemetry=telemetry)
    return ThreadingHTTPServer((host, port), BoundHandler)


def main() -> None:
    parser = argparse.ArgumentParser(description="Gökkalkan dry-run operator API server")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8088)
    parser.add_argument("--telemetry-jsonl", default=None, help="JSONL telemetri yolu (varsayılan: telemetry_data/operator-api-dry-run.jsonl)")
    args = parser.parse_args()
    server = build_http_server(args.host, args.port, telemetry_jsonl=args.telemetry_jsonl)
    print(f"Gökkalkan dry-run operator API listening on http://{args.host}:{args.port}")
    print("Fiziksel çıkış yok: hardware adapter dry-run modundadır.")
    print(f"Telemetry JSONL: {server.RequestHandlerClass.service.telemetry.path}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nOperator API stopped.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
