"""No-dependency HTTP entrypoint for the Gökkalkan dry-run operator API."""

from __future__ import annotations

import argparse
import json
import os
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import urlparse

from .operator_api import OperatorService
from .runtime_mode import (
    RuntimeConfigurationError,
    RuntimeLaunchConfig,
    build_runtime_service,
    runtime_summary,
)
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
        elif path == "/sensor-frames":
            self._send_json(self.operator_service.sensor_frames_snapshot())
        elif path == "/readiness":
            self._send_json(self.operator_service.readiness())
        elif path == "/events":
            self._send_json({"events": self.operator_service.events})
        elif path == "/telemetry/export":
            self._send_json(self.operator_service.telemetry_export())
        elif path == "/replay":
            self._send_json(self.operator_service.replay())
        elif path == "/hardware/health":
            self._send_json(self.operator_service.hardware.health_check())
        else:
            self._send_json({"error": "not_found", "path": path}, HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        payload = self._read_json()
        if path == "/mode":
            self._send_json(self.operator_service.handle_mode_request(payload))
        elif path == "/stage":
            self._send_json(self.operator_service.handle_stage_request(payload))
        elif path == "/manual-aim":
            self._send_json(self.operator_service.handle_manual_aim(payload))
        elif path == "/fire-intent":
            self._send_json(self.operator_service.handle_fire_intent(payload))
        elif path == "/telemetry/reset":
            self._send_json(self.operator_service.reset_telemetry())
        elif path == "/tracks/update":
            # Perception veya sensör adapter'ından canlı track güncellemesi
            tracks = payload.get("tracks", [])
            source = str(payload.get("source", "perception"))
            self._send_json(self.operator_service.update_tracks(tracks, source))
        elif path == "/estop":
            # Test ve harici tetikleyici için E-Stop endpoint'i
            # Üretimde bu endpoint hakem/operatör kilidi gerektirir.
            active = bool(payload.get("active", True))
            self.operator_service.set_estop(active)
            self._send_json({
                "ok": True,
                "estop": active,
                "safety": self.operator_service.evaluate_safety("ModeRequest").to_dict(),
            })
        elif path == "/maintenance":
            # Şartname v1.3: bakım isteği başlat
            self._send_json(self.operator_service.handle_maintenance_request(payload))
        elif path == "/maintenance/end":
            # Bakım süresini sonlandır
            self._send_json(self.operator_service.maintenance_end())
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
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    import logging
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    default_host = os.environ.get("OPERATOR_API_HOST", "127.0.0.1")
    default_port = int(os.environ.get("OPERATOR_API_PORT", 8088))

    parser = argparse.ArgumentParser(description="Gökkalkan operator API server")
    parser.add_argument("--host", default=default_host)
    parser.add_argument("--port", type=int, default=default_port)
    parser.add_argument("--telemetry-jsonl", default=None, help="JSONL telemetri yolu (varsayılan: telemetry_data/operator-api-dry-run.jsonl)")
    parser.add_argument(
        "--runtime-mode",
        choices=("SIM", "HIL", "LIVE"),
        default=os.environ.get("GOKKALKAN_RUNTIME_MODE", "SIM").upper(),
        help="Çalışma profili; varsayılan SIM ve fiziksel çıkışsızdır.",
    )
    parser.add_argument("--can-channel", default=os.environ.get("GOKKALKAN_CAN_CHANNEL", "vcan0"))
    parser.add_argument("--can-bustype", default=os.environ.get("GOKKALKAN_CAN_BUSTYPE", "virtual"))
    parser.add_argument("--can-bitrate", type=int, default=int(os.environ.get("GOKKALKAN_CAN_BITRATE", "500000")))
    parser.add_argument(
        "--vcan",
        action="store_true",
        help="Geriye uyumlu HIL kısayolu; yalnız sanal CAN kullanır.",
    )
    args = parser.parse_args()

    runtime_mode = "HIL" if args.vcan else args.runtime_mode
    if args.vcan:
        args.can_channel = "vcan0"
        args.can_bustype = "virtual"
    telemetry = JsonlTelemetryStore(args.telemetry_jsonl) if args.telemetry_jsonl else None
    config = RuntimeLaunchConfig(
        mode=runtime_mode,
        can_channel=args.can_channel,
        can_bustype=args.can_bustype,
        can_bitrate=args.can_bitrate,
        live_output_enabled=os.environ.get("GOKKALKAN_LIVE_OUTPUT_ENABLED") == "1",
    )
    try:
        # CLI bilinçli olarak fiziksel preflight üretmez. LIVE, gerçek interlock
        # entegrasyonu ayrı bootstrap tarafından sağlanana kadar fail-closed kalır.
        service = build_runtime_service(config, telemetry=telemetry)
    except RuntimeConfigurationError as exc:
        parser.error(str(exc))

    if runtime_mode == "HIL" and args.can_bustype == "virtual":
        # Mac OS'ta virtual bus process'ler arası çalışmadığı için simülatörü de aynı process'te başlatıyoruz
        import sys
        import threading
        sys.path.insert(0, "backend/hardware_mock")
        try:
            from mcu_simulator import McuSimulator
            sim = McuSimulator(channel="vcan0", bustype="virtual", verbose=True)
            if sim._open():
                sim._running = True
                threading.Thread(target=sim._rx_loop, daemon=True, name="SIM-RX").start()
                threading.Thread(target=sim._tx_status_loop, daemon=True, name="SIM-TX").start()
                print("Dahili MCU Simülatörü (Mac uyumluluğu için) başlatıldı. Loglar vcan_logs.txt'ye yazılacak.")
        except ImportError:
            pass

    print(f"Runtime: {json.dumps(runtime_summary(service), ensure_ascii=False, default=str)}")
    server = build_http_server(args.host, args.port, service=service)
    print(f"Gökkalkan operator API listening on http://{args.host}:{args.port}")
    print(f"Telemetry JSONL: {server.RequestHandlerClass.service.telemetry.path}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nOperator API stopped.")
    finally:
        server.server_close()
        service.hardware.close()


if __name__ == "__main__":
    main()
