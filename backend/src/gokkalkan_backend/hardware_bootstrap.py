"""Server-owned, fail-closed LIVE hardware preflight."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import json
import time
from typing import Any, Callable, Mapping

from .runtime_mode import LivePreflight, RuntimeConfigurationError
from .runtime_config import RuntimeSettings
from .usb_serial_adapter import UsbSerialMcuAdapter


MonitorFactory = Callable[..., Any]


@dataclass(frozen=True, slots=True)
class HardwareBootstrap:
    """Prove LIVE readiness without granting physical output capability."""

    timeout_sec: float = 2.0
    poll_interval_sec: float = 0.02

    def run(
        self,
        settings: RuntimeSettings,
        *,
        evidence_files: Mapping[str, Path],
        monitor_factory: MonitorFactory = UsbSerialMcuAdapter,
        sleep: Callable[[float], None] = time.sleep,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> LivePreflight:
        if settings.profile != "LIVE":
            raise RuntimeConfigurationError("hardware bootstrap is only valid for LIVE")
        port = settings.mcu.port
        if "/dev/serial/by-id/" not in port or "REPLACE_" in port or "UNVERIFIED" in port:
            raise RuntimeConfigurationError("LIVE Arduino identity is not a reviewed /dev/serial/by-id path")

        hashes = self._verify_evidence(evidence_files)
        monitor = monitor_factory(
            port=port,
            baudrate=settings.mcu.baudrate,
            heartbeat_timeout_sec=settings.mcu.heartbeat_timeout_ms / 1000.0,
            dry_run=False,
            physical_output_capable=False,
        )
        try:
            monitor.start()
            deadline = monotonic() + self.timeout_sec
            health: dict[str, Any] = {}
            while monotonic() < deadline:
                health = dict(monitor.health_check())
                if health.get("arduinoReachable", health.get("picoReachable")):
                    break
                sleep(self.poll_interval_sec)
            self._verify_health(health)
        finally:
            monitor.close()

        snapshot = {
            "schemaVersion": 1,
            "mcuPath": port,
            "firmwareVersion": health.get("firmwareVersion"),
            "protocolVersion": health.get("protocolVersion"),
            "statusAgeSec": health.get("lastStatusAgeSec"),
            "estopSafeSense": not bool(health.get("mcuStatus", {}).get("estopActive", True)),
            "contactorFeedbackAvailable": False,
            "evidenceSha256": hashes,
        }
        source = "hardware-bootstrap:" + sha256(
            json.dumps(snapshot, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        return LivePreflight(True, True, source, snapshot)

    @staticmethod
    def _verify_evidence(files: Mapping[str, Path]) -> dict[str, str]:
        required = {
            "runtimeConfig", "bom", "pinMap", "physicalAcceptance",
            "lidarCalibration", "cameraCalibration", "turretCalibration",
            "airsoftCalibration", "detectorModel",
        }
        missing_labels = sorted(required - set(files))
        if missing_labels:
            raise RuntimeConfigurationError(
                "LIVE evidence map is incomplete: " + ", ".join(missing_labels)
            )
        hashes: dict[str, str] = {}
        for label in sorted(required):
            path = files[label]
            try:
                content = path.read_bytes()
            except OSError as exc:
                raise RuntimeConfigurationError(f"LIVE evidence cannot be read: {label}={path}") from exc
            text = content.decode("utf-8", errors="ignore").upper()
            if label in {
                "pinMap", "physicalAcceptance", "lidarCalibration",
                "cameraCalibration", "turretCalibration", "airsoftCalibration",
            } and (
                "UNVERIFIED" in text or "TODO" in text or not content.strip()
            ):
                raise RuntimeConfigurationError(f"LIVE evidence is not approved: {label}={path}")
            hashes[label] = sha256(content).hexdigest()
        return hashes

    @staticmethod
    def _verify_health(health: Mapping[str, Any]) -> None:
        status = health.get("mcuStatus")
        if not health.get("serialConnected") or not health.get("picoReachable"):
            raise RuntimeConfigurationError("LIVE Arduino monitor did not receive a fresh status")
        if int(health.get("protocolVersion", 0) or 0) != 1:
            raise RuntimeConfigurationError("LIVE Arduino protocol major mismatch")
        if not str(health.get("firmwareVersion") or "").strip():
            raise RuntimeConfigurationError("LIVE Arduino firmware identity is missing")
        if not isinstance(status, Mapping):
            raise RuntimeConfigurationError("LIVE Arduino status payload is missing")
        if bool(status.get("estopActive", True)):
            raise RuntimeConfigurationError("LIVE E-Stop safe-sense is not ready")
        if not bool(status.get("encoderOk", False)):
            raise RuntimeConfigurationError("LIVE encoder readiness failed")
        if not bool(status.get("fireReady", False)):
            raise RuntimeConfigurationError("LIVE airsoft interlock/feedback readiness failed")
        if int(status.get("faultCode", status.get("errorCode", 1)) or 0) != 0:
            raise RuntimeConfigurationError("LIVE Arduino reports a fault")
