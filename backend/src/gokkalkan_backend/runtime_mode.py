"""Fail-closed construction of SIM, HIL and LIVE operator runtimes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Literal, Mapping

from .hardware_adapter import HardwareAdapterBase
from .operator_api import DryRunHardwareAdapter, OperatorService
from .telemetry_log import JsonlTelemetryStore
from .arduino_motor_adapter import ArduinoUnoMotorAdapter, FIELD_PROFILE_ID

RuntimeMode = Literal["SIM", "HIL", "LIVE"]
McuAdapterFactory = Callable[..., HardwareAdapterBase]
DEFAULT_ARDUINO_FIELD_PROFILE = FIELD_PROFILE_ID


class RuntimeConfigurationError(RuntimeError):
    """Raised before an unsafe or inconsistent runtime can load its adapter."""


@dataclass(frozen=True, slots=True)
class RuntimeLaunchConfig:
    """Minimal, server-owned runtime selection.

    LIVE is intentionally impossible with configuration alone. A physical
    preflight result from the hardware bootstrap is also mandatory.
    """

    mode: RuntimeMode = "SIM"
    mcu_transport: str = "arduino_serial"
    mcu_port: str = "loop://"
    mcu_baudrate: int = 115_200
    mcu_field_profile: str = DEFAULT_ARDUINO_FIELD_PROFILE
    heartbeat_timeout_sec: float = 2.0
    live_output_enabled: bool = False
    hil_physical_mcu_enabled: bool = False


@dataclass(frozen=True, slots=True)
class LivePreflight:
    """Result supplied by a physical interlock/readiness integration."""

    physical_interlock_ready: bool
    backend_readiness_ok: bool
    source: str
    snapshot: Mapping[str, Any] | None = None


def _is_virtual_mcu_port(port: str) -> bool:
    return port.startswith("loop://")


def _start_adapter(adapter: HardwareAdapterBase) -> None:
    start = getattr(adapter, "start", None)
    if not callable(start):
        raise RuntimeConfigurationError("MCU adapter does not expose start()")
    start()


def build_runtime_service(
    config: RuntimeLaunchConfig,
    *,
    telemetry: JsonlTelemetryStore | None = None,
    live_preflight: LivePreflight | None = None,
    mcu_adapter_factory: McuAdapterFactory = ArduinoUnoMotorAdapter,
    operator_options: dict[str, Any] | None = None,
) -> OperatorService:
    """Build a service without letting client input influence output authority."""

    options = dict(operator_options or {})
    if config.mode == "SIM":
        return OperatorService(
            hardware=DryRunHardwareAdapter(),
            telemetry=telemetry,
            dry_run=True,
            runtime_mode="SIM",
            **options,
        )

    if config.mode == "HIL":
        if config.mcu_transport != "arduino_serial":
            raise RuntimeConfigurationError("HIL requires the Arduino serial MCU transport")
        if (
            not _is_virtual_mcu_port(config.mcu_port)
            and not config.hil_physical_mcu_enabled
        ):
            raise RuntimeConfigurationError(
                "HIL requires loop:// Arduino serial simulation unless the reviewed "
                "safe-load physical MCU profile is explicitly enabled"
            )
        adapter = mcu_adapter_factory(
            port=config.mcu_port,
            baudrate=config.mcu_baudrate,
            expected_field_profile=config.mcu_field_profile,
            heartbeat_timeout_sec=config.heartbeat_timeout_sec,
            dry_run=False,
            # The reviewed physical HIL profile may drive pan/tilt only.  The
            # Arduino adapter still rejects FIRE because the field firmware
            # does not implement an arm/fire protocol.
            physical_output_capable=config.hil_physical_mcu_enabled,
        )
        _start_adapter(adapter)
        return OperatorService(
            hardware=adapter,
            telemetry=telemetry,
            dry_run=True,
            runtime_mode="HIL",
            **options,
        )

    if config.mode != "LIVE":
        raise RuntimeConfigurationError(f"unsupported runtime mode: {config.mode}")
    if not config.live_output_enabled:
        raise RuntimeConfigurationError(
            "LIVE output must be explicitly enabled by backend configuration"
        )
    if live_preflight is None:
        raise RuntimeConfigurationError(
            "LIVE requires a physical interlock and backend readiness preflight"
        )
    if not live_preflight.physical_interlock_ready:
        raise RuntimeConfigurationError(
            "LIVE physical interlock is not ready; adapter was not constructed"
        )
    if not live_preflight.backend_readiness_ok:
        raise RuntimeConfigurationError(
            "LIVE backend readiness failed; adapter was not constructed"
        )
    if not live_preflight.source.strip():
        raise RuntimeConfigurationError("LIVE preflight source must be auditable")
    if config.mcu_transport != "arduino_serial":
        raise RuntimeConfigurationError("LIVE requires the Arduino serial MCU transport")
    if _is_virtual_mcu_port(config.mcu_port):
        raise RuntimeConfigurationError("LIVE requires a physical USB serial device")
    if "/dev/serial/by-id/" not in config.mcu_port:
        raise RuntimeConfigurationError("LIVE requires a stable /dev/serial/by-id/ MCU path")

    adapter = mcu_adapter_factory(
        port=config.mcu_port,
        baudrate=config.mcu_baudrate,
        expected_field_profile=config.mcu_field_profile,
        heartbeat_timeout_sec=config.heartbeat_timeout_sec,
        dry_run=False,
        physical_output_capable=True,
    )
    _start_adapter(adapter)
    return OperatorService(
        hardware=adapter,
        telemetry=telemetry,
        dry_run=False,
        runtime_mode="LIVE",
        physical_interlock_ok=live_preflight.physical_interlock_ready,
        backend_readiness_ok=live_preflight.backend_readiness_ok,
        **options,
    )


def runtime_summary(service: OperatorService) -> dict[str, Any]:
    """Small diagnostic shape suitable for startup logging."""

    return {
        "runtimeMode": service.runtime_mode,
        "dryRun": service.dry_run,
        "liveArmEnabled": service.live_arm_enabled,
        "hardware": service.hardware.health_check(),
    }
