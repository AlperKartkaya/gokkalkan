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
from .hardware_bootstrap import HardwareBootstrap
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
from .sensor_runtime import TFA50LSensorRuntime, build_tfa50l_sensor_runtime
from .camera_calibration import camera_calibration_digest
from .video_demo import latest_run_summary


class OperatorApiHandler(BaseHTTPRequestHandler):
    service: OperatorService | None = None
    core: MissionCore | None = None
    allowed_origins: tuple[str, ...] = ("*",)
    operator_token: str | None = None
    video_runs_root: str = "/var/lib/gokkalkan/video-runs"
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
        elif path == "/video-demo/session":
            self._send_json(latest_run_summary(self.video_runs_root))
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
        payload = self._read_json()
        if not self._authorize_mutation():
            return
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
            active = bool(payload.get("active", True))
            self._submit("EStopChange", {"active": active, **payload}, source="operator-estop-http")
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
    video_runs_root: str = "/var/lib/gokkalkan/video-runs",
) -> ThreadingHTTPServer:
    class BoundHandler(OperatorApiHandler):
        pass

    telemetry = JsonlTelemetryStore(telemetry_jsonl) if telemetry_jsonl else None
    BoundHandler.service = service or OperatorService(telemetry=telemetry)
    BoundHandler.core = core or MissionCore(BoundHandler.service)
    BoundHandler.allowed_origins = allowed_origins
    BoundHandler.operator_token = operator_token
    BoundHandler.video_runs_root = video_runs_root

    class CoreHttpServer(ThreadingHTTPServer):
        daemon_threads = True

        def shutdown(self) -> None:
            try:
                BoundHandler.core.submit(
                    "Disarm",
                    {"reason": "SERVICE_SHUTDOWN"},
                    source="runtime-shutdown",
                    timeout=1.0,
                )
            except (MissionCoreStopped, MissionCommandTimeout):
                pass
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
    parser.add_argument("--mcu-port", default=os.environ.get("GOKKALKAN_MCU_PORT"))
    parser.add_argument(
        "--mcu-baudrate",
        type=int,
        default=int(os.environ["GOKKALKAN_MCU_BAUDRATE"])
        if os.environ.get("GOKKALKAN_MCU_BAUDRATE")
        else None,
    )
    parser.add_argument(
        "--usb-loop",
        action="store_true",
        help="HIL için fiziksel çıkışsız USB seri loopback kullanır.",
    )
    args = parser.parse_args(argv)

    environment_mode = os.environ.get("GOKKALKAN_RUNTIME_MODE", "").upper() or None
    selected_mode = (
        "HIL"
        if args.usb_loop
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
    if args.usb_loop:
        args.mcu_port = "loop://"
    try:
        settings = settings.with_cli_overrides(
            host=args.host,
            port=args.port,
            mcu_port=args.mcu_port,
            mcu_baudrate=args.mcu_baudrate,
            telemetry_path=args.telemetry_jsonl,
        )
    except RuntimeConfigError as exc:
        parser.error(str(exc))

    source_files: dict[str, Path] = {
        "runtimeConfig": settings.source,
        "calibration": settings.sensors.lidar_calibration_path,
        "mcuProtocol": Path("docs/usb_serial_mcu_protocol.md"),
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
    source_files["pinMap"] = Path(
        os.environ.get("GOKKALKAN_PIN_MAP_FILE", "docs/hardware/GKK-IO-REV-A_PIN_MAP.md")
    )
    source_files["physicalAcceptance"] = Path(
        os.environ.get(
            "GOKKALKAN_PHYSICAL_ACCEPTANCE_FILE",
            "evidence/live/hardware_acceptance.json",
        )
    )
    source_files["lidarCalibration"] = settings.sensors.lidar_calibration_path
    source_files["cameraCalibration"] = Path(
        os.environ.get("GOKKALKAN_CAMERA_CALIBRATION_FILE", "config/calibration/camera.toml")
    )
    source_files["detectorModel"] = Path(
        os.environ.get("GOKKALKAN_DETECTOR_MODEL", "perception/models/target_detector.hef")
    )
    source_files["airsoftCalibration"] = source_files["ballisticCalibration"]
    telemetry = SessionTelemetryStore.from_output_path(
        settings.telemetry.path,
        max_bytes=settings.telemetry.max_bytes,
        min_free_bytes=settings.telemetry.min_free_bytes,
        operator_id=os.environ.get("GOKKALKAN_OPERATOR_ID", "UNASSIGNED"),
        source_files=source_files,
    )
    config = settings.launch_config()
    try:
        live_preflight = None
        if runtime_mode == "LIVE":
            live_preflight = HardwareBootstrap().run(
                settings,
                evidence_files=source_files,
            )
            telemetry.append("live_preflight", {
                "source": live_preflight.source,
                "snapshot": dict(live_preflight.snapshot or {}),
            })
        service = build_runtime_service(
            config,
            telemetry=telemetry,
            live_preflight=live_preflight,
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
                "camera_calibration_hash": camera_calibration_digest(
                    source_files["cameraCalibration"]
                ),
            },
        )
    except RuntimeConfigurationError as exc:
        parser.error(str(exc))

    print(f"Config: {settings.source} (schema={settings.schema_version})")
    print(f"Runtime: {json.dumps(runtime_summary(service), ensure_ascii=False, default=str)}")
    core = MissionCore(service)
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
        core=core,
    )
    sensor_runtime: TFA50LSensorRuntime | None = None
    if settings.sensors.lidar_input_enabled:
        try:
            sensor_runtime = build_tfa50l_sensor_runtime(
                core,
                settings,
                telemetry=lambda kind, payload: telemetry.append(kind, payload),
            )
            sensor_runtime.start()
        except (OSError, ValueError) as exc:
            server.server_close()
            service.hardware.close()
            telemetry.close()
            parser.error(f"TFA50-L production runtime başlatılamadı: {exc}")
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
        if sensor_runtime is not None:
            sensor_runtime.stop()
        server.server_close()
        service.hardware.close()
        telemetry.close()


if __name__ == "__main__":
    main()
