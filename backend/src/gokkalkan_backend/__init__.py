"""Gökkalkan backend entegrasyon primitifleri.

Dry-run (fiziksel çıkış yok) ve gerçek donanım modlarını destekler.
Gerçek donanım için CanMcuAdapter kullanın (bkz. hardware_adapter.py).
"""

from .hardware_adapter import CanMcuAdapter, GpioEStopMonitor, HardwareAdapterBase
from .operator_api import DryRunHardwareAdapter, OperatorService
from .telemetry_log import JsonlTelemetryStore

__all__ = [
    "OperatorService",
    "DryRunHardwareAdapter",
    "JsonlTelemetryStore",
    "HardwareAdapterBase",
    "CanMcuAdapter",
    "GpioEStopMonitor",
]

