"""Gökkalkan backend integration primitives.

Construct runtimes through ``runtime_mode.build_runtime_service``. Direct
adapter construction is not an authorization path for physical output.
"""

from .hardware_adapter import CanMcuAdapter, GpioEStopMonitor, HardwareAdapterBase
from .messages import CommandEnvelope, EventEnvelope
from .mission_core import MissionCore, MissionState
from .operator_api import DryRunHardwareAdapter, OperatorService
from .runtime_config import RuntimeSettings, load_runtime_config
from .runtime_mode import RuntimeLaunchConfig, build_runtime_service
from .telemetry_log import JsonlTelemetryStore
from .telemetry_session import SessionTelemetryStore

__all__ = [
    "OperatorService",
    "DryRunHardwareAdapter",
    "JsonlTelemetryStore",
    "SessionTelemetryStore",
    "HardwareAdapterBase",
    "CanMcuAdapter",
    "CommandEnvelope",
    "EventEnvelope",
    "GpioEStopMonitor",
    "MissionCore",
    "MissionState",
    "RuntimeLaunchConfig",
    "RuntimeSettings",
    "build_runtime_service",
    "load_runtime_config",
]
