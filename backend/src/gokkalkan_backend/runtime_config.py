"""Validated TOML configuration for SIM, HIL and LIVE runtimes."""

from __future__ import annotations

import tomllib
import ipaddress
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Mapping, TypeVar

from .runtime_mode import (
    DEFAULT_ARDUINO_FIELD_PROFILE,
    RuntimeLaunchConfig,
    RuntimeMode,
)
from .safety_gate import ForbiddenZone

T = TypeVar("T")


class RuntimeConfigError(ValueError):
    """Raised when a runtime file is incomplete, unsafe or inconsistent."""


def _table(data: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    value = data.get(key)
    if not isinstance(value, dict):
        raise RuntimeConfigError(f"missing or invalid [{key}] table")
    return value


def _required(table: Mapping[str, Any], key: str, expected: type[T]) -> T:
    if key not in table:
        raise RuntimeConfigError(f"missing required config value: {key}")
    value = table[key]
    # bool is an int subclass; do not accept it for numeric safety fields.
    if expected in {int, float} and isinstance(value, bool):
        raise RuntimeConfigError(f"{key} must be {expected.__name__}")
    if expected is float and isinstance(value, (int, float)):
        return float(value)  # type: ignore[return-value]
    if not isinstance(value, expected):
        raise RuntimeConfigError(f"{key} must be {expected.__name__}")
    return value


def _optional_string(table: Mapping[str, Any], key: str, default: str) -> str:
    value = table.get(key, default)
    if not isinstance(value, str):
        raise RuntimeConfigError(f"{key} must be str")
    return value


def _bounded(name: str, value: float, minimum: float, maximum: float) -> None:
    if not minimum <= value <= maximum:
        raise RuntimeConfigError(
            f"{name} must be between {minimum} and {maximum}; got {value}"
        )


@dataclass(frozen=True, slots=True)
class ApiSettings:
    host: str
    port: int
    allowed_origins: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class McuSettings:
    transport: str
    port: str
    baudrate: int
    heartbeat_timeout_ms: int
    field_profile: str = DEFAULT_ARDUINO_FIELD_PROFILE


@dataclass(frozen=True, slots=True)
class SafetySettings:
    pan_min_deg: float
    pan_max_deg: float
    tilt_min_deg: float
    tilt_max_deg: float
    command_timeout_ms: int
    live_output_enabled: bool
    zone_schema_version: int = 1
    motion_forbidden_zones: tuple[ForbiddenZone, ...] = ()
    fire_forbidden_zones: tuple[ForbiddenZone, ...] = ()
    arm_hold_ms: int = 2000
    arm_timeout_ms: int = 3000


@dataclass(frozen=True, slots=True)
class TelemetrySettings:
    path: Path
    max_bytes: int
    min_free_bytes: int


@dataclass(frozen=True, slots=True)
class SensorSettings:
    camera_device: int
    camera_backend: str
    track_stale_ms: int
    lidar_stale_ms: int
    lidar_min_m: float
    lidar_max_m: float
    lidar_port: str
    lidar_baud_rate: int
    lidar_sample_hz: int
    lidar_serial_number: str
    lidar_firmware_version: str
    lidar_calibration_path: Path
    lidar_mount_revision: str
    lidar_input_enabled: bool
    classification_min_confidence: float


@dataclass(frozen=True, slots=True)
class LiveSettings:
    interlock_provider: str
    readiness_provider: str
    operator_token_file: str


@dataclass(frozen=True, slots=True)
class HilSettings:
    safe_load: str
    physical_mcu_enabled: bool
    destructive_output_enabled: bool


@dataclass(frozen=True, slots=True)
class RuntimeSettings:
    schema_version: int
    profile: RuntimeMode
    api: ApiSettings
    mcu: McuSettings
    safety: SafetySettings
    telemetry: TelemetrySettings
    sensors: SensorSettings
    live: LiveSettings
    hil: HilSettings
    source: Path

    def launch_config(self) -> RuntimeLaunchConfig:
        return RuntimeLaunchConfig(
            mode=self.profile,
            mcu_transport=self.mcu.transport,
            mcu_port=self.mcu.port,
            mcu_baudrate=self.mcu.baudrate,
            mcu_field_profile=self.mcu.field_profile,
            heartbeat_timeout_sec=self.mcu.heartbeat_timeout_ms / 1000.0,
            live_output_enabled=self.safety.live_output_enabled,
            hil_physical_mcu_enabled=self.hil.physical_mcu_enabled,
        )

    def with_cli_overrides(
        self,
        *,
        host: str | None = None,
        port: int | None = None,
        mcu_port: str | None = None,
        mcu_baudrate: int | None = None,
        telemetry_path: str | None = None,
    ) -> "RuntimeSettings":
        """Apply non-authority CLI overrides and revalidate the result."""

        updated = replace(
            self,
            api=replace(
                self.api,
                host=host if host is not None else self.api.host,
                port=port if port is not None else self.api.port,
            ),
            mcu=replace(
                self.mcu,
                port=mcu_port if mcu_port is not None else self.mcu.port,
                baudrate=mcu_baudrate if mcu_baudrate is not None else self.mcu.baudrate,
            ),
            telemetry=replace(
                self.telemetry,
                path=Path(telemetry_path) if telemetry_path else self.telemetry.path,
            ),
        )
        _validate_settings(updated)
        return updated


def _parse_origins(api: Mapping[str, Any]) -> tuple[str, ...]:
    raw = api.get("allowed_origins")
    if not isinstance(raw, list) or not raw or not all(
        isinstance(item, str) and item.strip() for item in raw
    ):
        raise RuntimeConfigError("api.allowed_origins must be a non-empty string list")
    return tuple(item.strip() for item in raw)


def _parse_zones(table: Mapping[str, Any], key: str) -> tuple[ForbiddenZone, ...]:
    raw = table.get(key, [])
    if not isinstance(raw, list):
        raise RuntimeConfigError(f"safety.{key} must be a list")
    zones: list[ForbiddenZone] = []
    for index, value in enumerate(raw):
        if not isinstance(value, dict):
            raise RuntimeConfigError(f"safety.{key}[{index}] must be a table")
        try:
            zone = ForbiddenZone(
                name=str(value["name"]),
                pan_min_deg=float(value["pan_min_deg"]),
                pan_max_deg=float(value["pan_max_deg"]),
                tilt_min_deg=float(value["tilt_min_deg"]),
                tilt_max_deg=float(value["tilt_max_deg"]),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise RuntimeConfigError(f"invalid safety.{key}[{index}]") from exc
        if not zone.name.strip() or not zone.valid():
            raise RuntimeConfigError(f"invalid safety.{key}[{index}] geometry")
        zones.append(zone)
    return tuple(zones)


def _validate_settings(settings: RuntimeSettings) -> None:
    if settings.schema_version != 1:
        raise RuntimeConfigError(
            f"unsupported runtime schema_version: {settings.schema_version}"
        )
    if settings.profile not in {"SIM", "HIL", "LIVE"}:
        raise RuntimeConfigError(f"unsupported runtime profile: {settings.profile}")
    if not settings.api.host.strip():
        raise RuntimeConfigError("api.host must not be empty")
    _bounded("api.port", settings.api.port, 1, 65535)
    if settings.mcu.transport != "arduino_serial":
        raise RuntimeConfigError("mcu.transport must be arduino_serial")
    if not settings.mcu.port.strip():
        raise RuntimeConfigError("mcu.port must not be empty")
    if not settings.mcu.field_profile.strip():
        raise RuntimeConfigError("mcu.field_profile must not be empty")
    _bounded("mcu.baudrate", settings.mcu.baudrate, 9_600, 3_000_000)
    _bounded(
        "mcu.heartbeat_timeout_ms",
        settings.mcu.heartbeat_timeout_ms,
        100,
        10_000,
    )
    _bounded("safety.pan_min_deg", settings.safety.pan_min_deg, -180.0, 180.0)
    _bounded("safety.pan_max_deg", settings.safety.pan_max_deg, -180.0, 180.0)
    _bounded("safety.tilt_min_deg", settings.safety.tilt_min_deg, -90.0, 90.0)
    _bounded("safety.tilt_max_deg", settings.safety.tilt_max_deg, -90.0, 90.0)
    if settings.safety.pan_min_deg >= settings.safety.pan_max_deg:
        raise RuntimeConfigError("pan soft limit minimum must be below maximum")
    if settings.safety.tilt_min_deg >= settings.safety.tilt_max_deg:
        raise RuntimeConfigError("tilt soft limit minimum must be below maximum")
    _bounded(
        "safety.command_timeout_ms",
        settings.safety.command_timeout_ms,
        50,
        10_000,
    )
    if settings.safety.zone_schema_version != 1:
        raise RuntimeConfigError("unsupported safety.zone_schema_version")
    _bounded("safety.arm_hold_ms", settings.safety.arm_hold_ms, 250, 10_000)
    _bounded("safety.arm_timeout_ms", settings.safety.arm_timeout_ms, 500, 30_000)
    for zone in (*settings.safety.motion_forbidden_zones, *settings.safety.fire_forbidden_zones):
        if not zone.valid():
            raise RuntimeConfigError(f"invalid forbidden zone geometry: {zone.name}")
    _bounded("telemetry.max_bytes", settings.telemetry.max_bytes, 1_048_576, 2**40)
    _bounded(
        "telemetry.min_free_bytes",
        settings.telemetry.min_free_bytes,
        1_048_576,
        2**40,
    )
    _bounded("sensors.camera_device", settings.sensors.camera_device, 0, 64)
    if settings.sensors.camera_backend not in {"auto", "picamera2", "opencv", "mock"}:
        raise RuntimeConfigError("sensors.camera_backend is not supported")
    _bounded("sensors.track_stale_ms", settings.sensors.track_stale_ms, 50, 30_000)
    _bounded("sensors.lidar_stale_ms", settings.sensors.lidar_stale_ms, 50, 30_000)
    _bounded("sensors.lidar_min_m", settings.sensors.lidar_min_m, 0.01, 500.0)
    _bounded("sensors.lidar_max_m", settings.sensors.lidar_max_m, 0.02, 500.0)
    if settings.sensors.lidar_min_m >= settings.sensors.lidar_max_m:
        raise RuntimeConfigError("LiDAR minimum range must be below maximum range")
    if not settings.sensors.lidar_port.strip():
        raise RuntimeConfigError("sensors.lidar_port must not be empty")
    _bounded("sensors.lidar_baud_rate", settings.sensors.lidar_baud_rate, 1_200, 3_000_000)
    _bounded("sensors.lidar_sample_hz", settings.sensors.lidar_sample_hz, 20, 20_000)
    if not settings.sensors.lidar_mount_revision.strip():
        raise RuntimeConfigError("sensors.lidar_mount_revision must not be empty")
    _bounded(
        "sensors.classification_min_confidence",
        settings.sensors.classification_min_confidence,
        0.0,
        1.0,
    )

    virtual_mcu = settings.mcu.port.startswith("loop://")
    if settings.profile != "LIVE" and settings.safety.live_output_enabled:
        raise RuntimeConfigError(
            "SIM/HIL profiles cannot enable physical LIVE output"
        )
    if settings.profile == "HIL":
        if settings.hil.safe_load not in {"lamp", "resistive-dummy-load"}:
            raise RuntimeConfigError("HIL requires an approved safe load")
        if settings.hil.destructive_output_enabled:
            raise RuntimeConfigError("HIL cannot enable the real destruction output")
        if not virtual_mcu and not settings.hil.physical_mcu_enabled:
            raise RuntimeConfigError(
                "HIL profile requires loop:// USB simulation unless "
                "hil.physical_mcu_enabled=true"
            )
    if settings.profile == "LIVE":
        if "*" in settings.api.allowed_origins:
            raise RuntimeConfigError("LIVE profile cannot use wildcard CORS origin")
        if virtual_mcu:
            raise RuntimeConfigError("LIVE profile requires a physical USB serial device")
        if "/dev/serial/by-id/" not in settings.mcu.port:
            raise RuntimeConfigError("LIVE profile requires a stable /dev/serial/by-id/ MCU path")
        try:
            loopback = (
                settings.api.host == "localhost"
                or ipaddress.ip_address(settings.api.host).is_loopback
            )
        except ValueError:
            loopback = False
        if not loopback:
            raise RuntimeConfigError("LIVE API host must be loopback")
        required_live = {
            "live.interlock_provider": settings.live.interlock_provider,
            "live.readiness_provider": settings.live.readiness_provider,
            "live.operator_token_file": settings.live.operator_token_file,
        }
        missing = [name for name, value in required_live.items() if not value.strip()]
        if missing:
            raise RuntimeConfigError(
                "LIVE profile is missing safety config: " + ", ".join(missing)
            )


def load_runtime_config(path: str | Path) -> RuntimeSettings:
    source = Path(path)
    try:
        raw = tomllib.loads(source.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise RuntimeConfigError(f"runtime config does not exist: {source}") from exc
    except tomllib.TOMLDecodeError as exc:
        raise RuntimeConfigError(f"invalid TOML in {source}: {exc}") from exc

    api = _table(raw, "api")
    mcu = _table(raw, "mcu")
    safety = _table(raw, "safety")
    telemetry = _table(raw, "telemetry")
    sensors = _table(raw, "sensors")
    live = _table(raw, "live")
    hil = raw.get("hil", {})
    if not isinstance(hil, dict):
        raise RuntimeConfigError("invalid [hil] table")
    profile = _required(raw, "profile", str).upper()
    if profile not in {"SIM", "HIL", "LIVE"}:
        raise RuntimeConfigError(f"unsupported runtime profile: {profile}")

    settings = RuntimeSettings(
        schema_version=_required(raw, "schema_version", int),
        profile=profile,  # type: ignore[arg-type]
        api=ApiSettings(
            host=_required(api, "host", str),
            port=_required(api, "port", int),
            allowed_origins=_parse_origins(api),
        ),
        mcu=McuSettings(
            transport=_required(mcu, "transport", str),
            port=_required(mcu, "port", str),
            baudrate=_required(mcu, "baudrate", int),
            heartbeat_timeout_ms=_required(mcu, "heartbeat_timeout_ms", int),
            field_profile=_optional_string(
                mcu, "field_profile", DEFAULT_ARDUINO_FIELD_PROFILE
            ),
        ),
        safety=SafetySettings(
            pan_min_deg=_required(safety, "pan_min_deg", float),
            pan_max_deg=_required(safety, "pan_max_deg", float),
            tilt_min_deg=_required(safety, "tilt_min_deg", float),
            tilt_max_deg=_required(safety, "tilt_max_deg", float),
            command_timeout_ms=_required(safety, "command_timeout_ms", int),
            live_output_enabled=_required(safety, "live_output_enabled", bool),
            zone_schema_version=int(safety.get("zone_schema_version", 1)),
            motion_forbidden_zones=_parse_zones(safety, "motion_forbidden_zones"),
            fire_forbidden_zones=_parse_zones(safety, "fire_forbidden_zones"),
            arm_hold_ms=int(safety.get("arm_hold_ms", 2000)),
            arm_timeout_ms=int(safety.get("arm_timeout_ms", 3000)),
        ),
        telemetry=TelemetrySettings(
            path=Path(_required(telemetry, "path", str)),
            max_bytes=_required(telemetry, "max_bytes", int),
            min_free_bytes=_required(telemetry, "min_free_bytes", int),
        ),
        sensors=SensorSettings(
            camera_device=_required(sensors, "camera_device", int),
            camera_backend=str(sensors.get("camera_backend", "auto")),
            track_stale_ms=_required(sensors, "track_stale_ms", int),
            lidar_stale_ms=_required(sensors, "lidar_stale_ms", int),
            lidar_min_m=_required(sensors, "lidar_min_m", float),
            lidar_max_m=_required(sensors, "lidar_max_m", float),
            lidar_port=str(sensors.get("lidar_port", "loop://unconfigured")),
            lidar_baud_rate=int(sensors.get("lidar_baud_rate", 460800)),
            lidar_sample_hz=int(sensors.get("lidar_sample_hz", 1000)),
            lidar_serial_number=str(sensors.get("lidar_serial_number", "UNVERIFIED")),
            lidar_firmware_version=str(sensors.get("lidar_firmware_version", "UNVERIFIED")),
            lidar_calibration_path=Path(
                str(sensors.get("lidar_calibration_path", "config/calibration/tfa50_l.toml"))
            ),
            lidar_mount_revision=str(sensors.get("lidar_mount_revision", "UNVERIFIED")),
            lidar_input_enabled=bool(sensors.get("lidar_input_enabled", False)),
            classification_min_confidence=_required(
                sensors, "classification_min_confidence", float
            ),
        ),
        live=LiveSettings(
            interlock_provider=_required(live, "interlock_provider", str),
            readiness_provider=_required(live, "readiness_provider", str),
            operator_token_file=_required(live, "operator_token_file", str),
        ),
        hil=HilSettings(
            safe_load=str(hil.get("safe_load", "lamp")),
            physical_mcu_enabled=bool(hil.get("physical_mcu_enabled", False)),
            destructive_output_enabled=bool(
                hil.get("destructive_output_enabled", False)
            ),
        ),
        source=source,
    )
    _validate_settings(settings)
    return settings


def default_profile_path(
    profile: str = "SIM", config_dir: str | Path = "config/runtime"
) -> Path:
    normalized = profile.lower()
    if normalized not in {"sim", "hil", "live"}:
        raise RuntimeConfigError(f"unsupported runtime profile: {profile}")
    return Path(config_dir) / f"{normalized}.toml"
