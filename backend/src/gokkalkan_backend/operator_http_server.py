"""No-dependency HTTP entrypoint for the Gökkalkan dry-run operator API."""

from __future__ import annotations

import argparse
import hmac
import json
import os
import signal
import threading
from pathlib import Path
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import urlparse

from .operator_api import OperatorService
from .ballistic_compensation import BallisticCompensation
from .mission_core import (
    MissionCommandTimeout,
    MissionCore,
    MissionCoreStopped,
    MissionQueueFull,
)
from .messages import MessageContractError
from .runtime_mode import (
    RuntimeConfigurationError,
    build_runtime_service,
    runtime_summary,
)
from .runtime_config import (
    RuntimeConfigError,
    default_profile_path,
    load_runtime_config,
)
from .telemetry_log import JsonlTelemetryStore
from .telemetry_session import SessionTelemetryStore
from .turret_calibration import TurretCalibration


class OperatorApiHandler(BaseHTTPRequestHandler):
    service: OperatorService | None = None
    core: MissionCore | None = None
    allowed_origins: tuple[str, ...] = ("*",)
    operator_token: str | None = None
    server_version = "GokkalkanOperatorApi/0.1"

    def handle(self) -> None:
        try:
            super().handle()
        except (ConnectionResetError, BrokenPipeError):
            return

    def do_OPTIONS(self) -> None:  # noqa: N802 - http.server naming convention
        self._send_json({"ok": True})

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path == "/health":
            self._send_json(self.mission_core.health())
        elif path == "/state":
            self._send_json(self.mission_core.snapshot())
        elif path == "/state/stream":
            self._stream_state()
        elif path == "/sensor-frames":
            snapshot = self.mission_core.snapshot()
            self._send_json(
                {
                    "schemaVersion": 1,
                    "generatedAt": snapshot["missionCore"]["updatedAtUtc"],
                    "stage": snapshot["stage"],
                    "round": snapshot["round"],
                    "sensorHealth": snapshot["sensorHealth"],
                    "frames": snapshot["sensorFrames"],
                    "physicalOutputEnabled": False,
                    "replayOnly": snapshot["sensorHealth"]["replayOnly"],
                    "snapshotVersion": snapshot["snapshotVersion"],
                }
            )
        elif path == "/readiness":
            self._send_json(self.operator_service.readiness())
        elif path == "/events":
            snapshot = self.mission_core.snapshot()
            self._send_json(
                {
                    "events": snapshot["events"],
                    "coreEvents": snapshot["coreEvents"],
                    "snapshotVersion": snapshot["snapshotVersion"],
                }
            )
        elif path == "/telemetry/export":
            snapshot = self.mission_core.snapshot()
            export = self.operator_service.telemetry_export(state=snapshot)
            export["snapshotVersion"] = snapshot["snapshotVersion"]
            self._send_json(export)
        elif path == "/replay":
            self._send_json(self.operator_service.replay())
        elif path == "/hardware/health":
            self._send_json(self.operator_service.hardware.health_check())
        elif path.startswith("/commands/"):
            command_id = path.removeprefix("/commands/").strip()
            status = self.mission_core.command_status(command_id)
            self._send_json(
                status or {"error": "not_found", "commandId": command_id},
                HTTPStatus.OK if status else HTTPStatus.NOT_FOUND,
            )
        else:
            self._send_json({"error": "not_found", "path": path}, HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if not self._authorize_mutation():
            return
        payload = self._read_json()
        operator_id = self.headers.get("X-Operator-Id", "").strip()
        if operator_id:
            payload["operatorId"] = operator_id
        if path == "/mode":
            self._submit("ModeRequest", payload)
        elif path == "/stage":
            self._submit("StageRequest", payload)
        elif path == "/manual-aim":
            self._submit("ManualAimCommand", payload)
        elif path == "/fire-intent":
            self._submit("FireIntent", payload)
        elif path == "/telemetry/reset":
            self._submit("TelemetryReset", payload)
        elif path == "/tracks/update":
            self._submit(
                "TracksUpdate",
                payload,
                source=str(payload.get("source", "perception")),
            )
        elif path == "/perception/heartbeat":
            heartbeat = {**payload, "healthy": bool(payload.get("healthy", True))}
            self._submit(
                "PerceptionHealth",
                heartbeat,
                source=str(payload.get("source", "perception")),
            )
        elif path == "/estop":
            if bool(payload.get("active", True)):
                self._submit("EStopChange", {"active": True, **payload}, source="operator-estop-http")
            else:
                self._send_json(
                    {"error": "physical_reset_required", "detail": "HTTP E-Stop temizleyemez."},
                    HTTPStatus.CONFLICT,
                )
        elif path == "/estop/reset":
            self._submit("EStopReset", payload)
        elif path == "/arm/hold":
            self._submit("ArmHold", payload)
        elif path == "/arm/disarm":
            self._submit("Disarm", payload)
        elif path == "/maintenance":
            self._submit("MaintenanceStart", payload)
        elif path == "/maintenance/end":
            self._submit("MaintenanceEnd", payload)
        elif path == "/mission/stop":
            self._submit("MissionStop", payload)
        elif path == "/mission/resume":
            self._submit("MissionResume", payload)
        else:
            self._send_json({"error": "not_found", "path": path}, HTTPStatus.NOT_FOUND)

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002 - stdlib signature
        return

    @property
    def operator_service(self) -> OperatorService:
        if self.service is None:
            self.__class__.service = OperatorService()
        return self.service

    @property
    def mission_core(self) -> MissionCore:
        if self.core is None:
            self.__class__.core = MissionCore(self.operator_service)
            self.__class__.core.start()
        return self.core

    def _submit(
        self,
        kind: str,
        payload: dict[str, Any],
        *,
        source: str = "operator-http",
    ) -> None:
        command_id = (
            self.headers.get("Idempotency-Key")
            or str(payload.get("commandId", "")).strip()
            or None
        )
        source_sequence = payload.get("sourceSequence")
        if not isinstance(source_sequence, int) or isinstance(source_sequence, bool):
            source_sequence = None
        try:
            response = self.mission_core.submit(
                kind,
                payload,
                source=source,
                command_id=command_id,
                causation_id=str(payload.get("causationId", "")).strip() or None,
                source_sequence=source_sequence,
                schema_version=payload.get("schemaVersion", 1),
            )
        except MissionCommandTimeout as exc:
            self._send_json(
                {
                    "commandId": exc.command_id,
                    "queued": True,
                    "completed": False,
                    "statusUrl": f"/commands/{exc.command_id}",
                    "physicalOutput": False,
                },
                HTTPStatus.ACCEPTED,
            )
        except MissionQueueFull as exc:
            self._send_json(
                {"error": "queue_full", "detail": str(exc)},
                HTTPStatus.SERVICE_UNAVAILABLE,
            )
        except MissionCoreStopped as exc:
            self._send_json(
                {"error": "mission_core_stopped", "detail": str(exc)},
                HTTPStatus.SERVICE_UNAVAILABLE,
            )
        except MessageContractError as exc:
            self._send_json(
                {"error": "message_contract", "detail": str(exc)},
                HTTPStatus.CONFLICT,
            )
        else:
            assert isinstance(response, dict)
            self._send_json(response)

    def _authorize_mutation(self) -> bool:
        """LIVE mutations require both an operator identity and bearer token."""

        if self.operator_service.runtime_mode != "LIVE":
            return True
        expected = self.operator_token or ""
        supplied = self.headers.get("Authorization", "")
        operator_id = self.headers.get("X-Operator-Id", "").strip()
        token = supplied.removeprefix("Bearer ").strip() if supplied.startswith("Bearer ") else ""
        if not expected or not operator_id or not hmac.compare_digest(token, expected):
            self._send_json(
                {"error": "unauthorized", "detail": "LIVE komutları kimlik ve token gerektirir."},
                HTTPStatus.UNAUTHORIZED,
            )
            return False
        return True

    def _stream_state(self) -> None:
        query = urlparse(self.path).query
        try:
            after_version = max(0, int(self.headers.get("Last-Event-ID", "0")))
        except ValueError:
            after_version = 0
        for item in query.split("&"):
            if item.startswith("after="):
                try:
                    after_version = max(0, int(item.split("=", 1)[1]))
                except ValueError:
                    pass
        self.close_connection = True
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        origin = self.headers.get("Origin")
        if "*" in self.allowed_origins:
            self.send_header("Access-Control-Allow-Origin", "*")
        elif origin and origin in self.allowed_origins:
            self.send_header("Access-Control-Allow-Origin", origin)
        self.end_headers()
        try:
            while self.mission_core.is_running:
                snapshot = self.mission_core.wait_for_snapshot(
                    after_version,
                    timeout=1.0,
                )
                version = int(snapshot["snapshotVersion"])
                if version <= after_version:
                    self.wfile.write(b": heartbeat\n\n")
                else:
                    payload = json.dumps(
                        snapshot,
                        ensure_ascii=False,
                        separators=(",", ":"),
                    ).encode("utf-8")
                    self.wfile.write(
                        f"id: {version}\nevent: state\ndata: ".encode("utf-8")
                        + payload
                        + b"\n\n"
                    )
                    after_version = version
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, OSError):
            return

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
        origin = self.headers.get("Origin")
        if "*" in self.allowed_origins:
            self.send_header("Access-Control-Allow-Origin", "*")
        elif origin in self.allowed_origins:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header(
            "Access-Control-Allow-Headers",
            "Content-Type, Idempotency-Key, Last-Event-ID, Authorization, X-Operator-Id",
        )
        self.end_headers()
        self.wfile.write(body)


def build_http_server(
    host: str = "127.0.0.1",
    port: int = 8088,
    service: OperatorService | None = None,
    telemetry_jsonl: str | None = None,
    allowed_origins: tuple[str, ...] = ("*",),
    core: MissionCore | None = None,
    operator_token: str | None = None,
) -> ThreadingHTTPServer:
    class BoundHandler(OperatorApiHandler):
        pass

    telemetry = JsonlTelemetryStore(telemetry_jsonl) if telemetry_jsonl else None
    BoundHandler.service = service or OperatorService(telemetry=telemetry)
    BoundHandler.core = core or MissionCore(BoundHandler.service)
    BoundHandler.allowed_origins = allowed_origins
    BoundHandler.operator_token = operator_token

    class CoreHttpServer(ThreadingHTTPServer):
        daemon_threads = True

        def shutdown(self) -> None:
            super().shutdown()
            BoundHandler.core.stop()

        def server_close(self) -> None:
            BoundHandler.core.stop()
            super().server_close()

    server = CoreHttpServer((host, port), BoundHandler)
    BoundHandler.core.start()
    return server


def main(argv: list[str] | None = None) -> None:
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    import logging
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    parser = argparse.ArgumentParser(description="Gökkalkan operator API server")
    parser.add_argument(
        "--config",
        default=os.environ.get("GOKKALKAN_RUNTIME_CONFIG"),
        help="Doğrulanan runtime TOML dosyası.",
    )
    parser.add_argument("--host", default=os.environ.get("OPERATOR_API_HOST"))
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.environ["OPERATOR_API_PORT"])
        if os.environ.get("OPERATOR_API_PORT")
        else None,
    )
    parser.add_argument(
        "--telemetry-jsonl",
        default=None,
        help="Config içindeki JSONL telemetri yolunu güvenli geliştirme için değiştir.",
    )
    parser.add_argument(
        "--runtime-mode",
        choices=("SIM", "HIL", "LIVE"),
        default=None,
        help="Config seçimi kısayolu; varsayılan SIM ve fiziksel çıkışsızdır.",
    )
    parser.add_argument("--can-channel", default=os.environ.get("GOKKALKAN_CAN_CHANNEL"))
    parser.add_argument("--can-bustype", default=os.environ.get("GOKKALKAN_CAN_BUSTYPE"))
    parser.add_argument(
        "--can-bitrate",
        type=int,
        default=int(os.environ["GOKKALKAN_CAN_BITRATE"])
        if os.environ.get("GOKKALKAN_CAN_BITRATE")
        else None,
    )
    parser.add_argument(
        "--vcan",
        action="store_true",
        help="Geriye uyumlu HIL kısayolu; yalnız sanal CAN kullanır.",
    )
    args = parser.parse_args(argv)

    environment_mode = os.environ.get("GOKKALKAN_RUNTIME_MODE", "").upper() or None
    selected_mode = (
        "HIL"
        if args.vcan
        else args.runtime_mode
        or (None if args.config else environment_mode)
    )
    config_path = (
        Path(args.config)
        if args.config
        else default_profile_path(selected_mode or "SIM")
    )
    try:
        settings = load_runtime_config(config_path)
    except RuntimeConfigError as exc:
        parser.error(str(exc))
    runtime_mode = selected_mode or settings.profile
    if settings.profile != runtime_mode:
        parser.error(
            f"runtime mode {runtime_mode} does not match config profile {settings.profile}"
        )
    if args.vcan:
        args.can_channel = "vcan0"
        args.can_bustype = "virtual"
    try:
        settings = settings.with_cli_overrides(
            host=args.host,
            port=args.port,
            can_channel=args.can_channel,
            can_bustype=args.can_bustype,
            can_bitrate=args.can_bitrate,
            telemetry_path=args.telemetry_jsonl,
        )
    except RuntimeConfigError as exc:
        parser.error(str(exc))

    source_files: dict[str, Path] = {
        "runtimeConfig": settings.source,
        "calibration": settings.sensors.lidar_calibration_path,
        "canIcd": Path("docs/can_icd_v1.md"),
        "lidarCameraPlacement": Path("docs/adr/003-camera-lidar-placement.md"),
        "turretCalibration": Path(
            os.environ.get(
                "GOKKALKAN_TURRET_CALIBRATION_FILE",
                "config/calibration/turret.toml",
            )
        ),
        "ballisticCalibration": Path(
            os.environ.get(
                "GOKKALKAN_BALLISTIC_CALIBRATION_FILE",
                "config/calibration/airsoft_trajectory.toml",
            )
        ),
    }
    for label, environment_name in (
        ("calibration", "GOKKALKAN_CALIBRATION_FILE"),
        ("bom", "GOKKALKAN_BOM_FILE"),
    ):
        configured = os.environ.get(environment_name)
        if configured:
            source_files[label] = Path(configured)
    telemetry = SessionTelemetryStore.from_output_path(
        settings.telemetry.path,
        max_bytes=settings.telemetry.max_bytes,
        min_free_bytes=settings.telemetry.min_free_bytes,
        operator_id=os.environ.get("GOKKALKAN_OPERATOR_ID", "UNASSIGNED"),
        source_files=source_files,
    )
    config = settings.launch_config()
    try:
        # CLI bilinçli olarak fiziksel preflight üretmez. LIVE, gerçek interlock
        # entegrasyonu ayrı bootstrap tarafından sağlanana kadar fail-closed kalır.
        service = build_runtime_service(
            config,
            telemetry=telemetry,
            operator_options={
                "pan_min_deg": settings.safety.pan_min_deg,
                "pan_max_deg": settings.safety.pan_max_deg,
                "tilt_min_deg": settings.safety.tilt_min_deg,
                "tilt_max_deg": settings.safety.tilt_max_deg,
                "motion_forbidden_zones": settings.safety.motion_forbidden_zones,
                "fire_forbidden_zones": settings.safety.fire_forbidden_zones,
                "arm_hold_seconds": settings.safety.arm_hold_ms / 1000.0,
                "arm_timeout_seconds": settings.safety.arm_timeout_ms / 1000.0,
                "disk_min_free_bytes": settings.telemetry.min_free_bytes,
                "lidar_stale_seconds": settings.sensors.lidar_stale_ms / 1000.0,
                "turret_calibration": TurretCalibration.from_toml(
                    source_files["turretCalibration"]
                ),
                "ballistic_compensation": BallisticCompensation.from_toml(
                    source_files["ballisticCalibration"]
                ),
            },
        )
    except RuntimeConfigurationError as exc:
        parser.error(str(exc))

    if runtime_mode == "HIL" and args.can_bustype == "virtual":
        # Mac OS'ta virtual bus process'ler arası çalışmadığı için simülatörü de aynı process'te başlatıyoruz
        import sys
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

    print(f"Config: {settings.source} (schema={settings.schema_version})")
    print(f"Runtime: {json.dumps(runtime_summary(service), ensure_ascii=False, default=str)}")
    server = build_http_server(
        settings.api.host,
        settings.api.port,
        service=service,
        allowed_origins=settings.api.allowed_origins,
        operator_token=(
            Path(settings.live.operator_token_file).read_text(encoding="utf-8").strip()
            if runtime_mode == "LIVE" and settings.live.operator_token_file
            else None
        ),
    )
    print(
        "Gökkalkan operator API listening on "
        f"http://{settings.api.host}:{settings.api.port}"
    )
    print(f"Telemetry JSONL: {server.RequestHandlerClass.service.telemetry.path}")

    def stop_server(_signum: int, _frame: object) -> None:
        threading.Thread(target=server.shutdown, daemon=True).start()

    signal.signal(signal.SIGTERM, stop_server)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nOperator API stopped.")
    finally:
        server.server_close()
        service.hardware.close()
        telemetry.close()


if __name__ == "__main__":
    main()
