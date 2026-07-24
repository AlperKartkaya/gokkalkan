"""Fail-closed construction of SIM, HIL and LIVE operator runtimes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Literal

from .hardware_adapter import CanMcuAdapter, HardwareAdapterBase
from .operator_api import DryRunHardwareAdapter, OperatorService
from .telemetry_log import JsonlTelemetryStore

RuntimeMode = Literal["SIM", "HIL", "LIVE"]
CanAdapterFactory = Callable[..., HardwareAdapterBase]


class RuntimeConfigurationError(RuntimeError):
    """Raised before an unsafe or inconsistent runtime can load its adapter."""


@dataclass(frozen=True, slots=True)
class RuntimeLaunchConfig:
    """Minimal, server-owned runtime selection.

    LIVE is intentionally impossible with configuration alone. A physical
    preflight result from the hardware bootstrap is also mandatory.
    """

    mode: RuntimeMode = "SIM"
    can_channel: str = "vcan0"
    can_bustype: str = "socketcan"
    can_bitrate: int = 500_000
    heartbeat_timeout_sec: float = 2.0
    live_output_enabled: bool = False


@dataclass(frozen=True, slots=True)
class LivePreflight:
    """Result supplied by a physical interlock/readiness integration."""

    physical_interlock_ready: bool
    backend_readiness_ok: bool
    source: str


def _is_virtual_can(channel: str, bustype: str) -> bool:
    return bustype == "virtual" or channel.startswith("vcan")


def _start_adapter(adapter: HardwareAdapterBase) -> None:
    start = getattr(adapter, "start", None)
    if not callable(start):
        raise RuntimeConfigurationError("CAN adapter does not expose start()")
    start()


def build_runtime_service(
    config: RuntimeLaunchConfig,
    *,
    telemetry: JsonlTelemetryStore | None = None,
    live_preflight: LivePreflight | None = None,
    can_adapter_factory: CanAdapterFactory = CanMcuAdapter,
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
        if not _is_virtual_can(config.can_channel, config.can_bustype):
            raise RuntimeConfigurationError(
                "HIL requires a virtual CAN channel; physical CAN was rejected"
            )
        adapter = can_adapter_factory(
            channel=config.can_channel,
            bustype=config.can_bustype,
            bitrate=config.can_bitrate,
            heartbeat_timeout_sec=config.heartbeat_timeout_sec,
            dry_run=False,
            physical_output_capable=False,
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
    if _is_virtual_can(config.can_channel, config.can_bustype):
        raise RuntimeConfigurationError("LIVE requires a physical CAN channel")

    adapter = can_adapter_factory(
        channel=config.can_channel,
        bustype=config.can_bustype,
        bitrate=config.can_bitrate,
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
