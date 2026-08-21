"""Production-owned TFA50-L worker bridged through the Mission Core queue."""

from __future__ import annotations

from dataclasses import dataclass
import threading
import time
from typing import Any, Callable

from .lidar_adapter import TFA50LSerialAdapter, TFA50LSerialConfig
from .mission_core import MissionCore, MissionCoreError
from .range_fusion import FusedRangeDecision, TrackBearing
from .sensor_pipeline import TFA50LFusionPipeline
from .range_fusion import LidarCalibration, YawRangeAssociator
from .runtime_config import RuntimeSettings


@dataclass(frozen=True, slots=True)
class SensorRuntimeIdentity:
    serial_number: str
    firmware_version: str
    mount_revision: str


class TFA50LSensorRuntime:
    """Read UART off-thread; all domain mutation stays on MissionCore."""

    def __init__(
        self,
        core: MissionCore,
        adapter: TFA50LSerialAdapter,
        associator: Any,
        identity: SensorRuntimeIdentity,
        *,
        interval_sec: float = 0.002,
        monotonic_ns: Callable[[], int] = time.monotonic_ns,
    ) -> None:
        self.core = core
        self.adapter = adapter
        self.identity = identity
        self.interval_sec = interval_sec
        self._clock = monotonic_ns
        self._running = False
        self._thread: threading.Thread | None = None
        self._last_error: str | None = None
        self._decisions = 0
        self.pipeline = TFA50LFusionPipeline(
            adapter,
            associator,
            selected_track=self._selected_track,
            turret_yaw_deg=self._turret_yaw,
            on_decision=self._publish,
            on_raw_sample=self._publish_raw_sample,
            monotonic_ns=monotonic_ns,
        )

    def _publish_raw_sample(self, sample: Any) -> None:
        try:
            self.core.publish_threadsafe(
                "RawLidarUpdate",
                {
                    "distanceM": sample.distance_m,
                    "valid": sample.valid,
                    "rawHex": getattr(sample, "raw_hex", ""),
                    "source": "tfa50-l",
                },
                source="sensor-tfa50-l-runtime",
            )
        except Exception:
            pass

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True, name="TFA50L-Sensor")
        self._thread.start()

    def stop(self, timeout: float = 2.0) -> None:
        self._running = False
        if self._thread and self._thread is not threading.current_thread():
            self._thread.join(timeout=timeout)
        self.adapter.close()

    def tick(self) -> list[FusedRangeDecision]:
        decisions = self.pipeline.tick()
        self._verify_identity()
        return decisions

    def health(self) -> dict[str, Any]:
        health = self.adapter.health()
        return {
            **health,
            "runtimeRunning": self._running,
            "decisionCount": self._decisions,
            "runtimeError": self._last_error,
            "identityAllowed": self._identity_matches(health),
        }

    def _run(self) -> None:
        while self._running:
            try:
                self.tick()
                self._last_error = None
            except (OSError, ValueError, MissionCoreError) as exc:
                self._last_error = f"{type(exc).__name__}:{exc}"
                try:
                    self.core.publish_threadsafe(
                        "FusedRangeUpdate",
                        {
                            "accepted": False,
                            "reason": "LIDAR_RUNTIME_UNHEALTHY",
                            "trackId": None,
                            "rangeM": None,
                            "source": "tfa50-l",
                            "calibrationHash": "unavailable",
                            "sampleCount": 0,
                        },
                        source="sensor-tfa50-l-runtime",
                    )
                except MissionCoreError:
                    pass
            time.sleep(self.interval_sec)

    def _selected_track(self) -> TrackBearing | None:
        snapshot = self.core.snapshot()
        selected_id = snapshot.get("missionFlow", {}).get("selectedTargetId")
        if not selected_id:
            return None
        for track in snapshot.get("tracks", []):
            if track.get("trackId") == selected_id:
                return TrackBearing(
                    str(selected_id),
                    float(track["bearingDeg"]),
                    int(track.get("receiveMonotonicNs", 0)),
                )
        return None

    def _turret_yaw(self) -> float:
        health = self.core.service.hardware.health_check()
        status = health.get("mcuStatus", {})
        age = health.get("lastStatusAgeSec")
        if isinstance(status, dict) and "panDeg" in status:
            if age is not None and float(age) * 1000 > self.adapter.config.stale_ms:
                raise ValueError("turret yaw is stale")
            return float(status["panDeg"])
        if hasattr(self.core.service, "_current_position"):
            pan, _, _ = self.core.service._current_position()
            return float(pan)
        return 0.0

    def _publish(self, decision: FusedRangeDecision) -> None:
        self.core.publish_threadsafe(
            "FusedRangeUpdate",
            decision.to_dict(),
            source="sensor-tfa50-l-runtime",
        )
        self._decisions += 1

    def _verify_identity(self) -> None:
        health = self.adapter.health()
        if health.get("connected") and self.identity.serial_number not in {"", "UNVERIFIED"}:
            if not self._identity_matches(health):
                raise ValueError("TFA50-L identity or mount revision mismatch")

    def _identity_matches(self, health: dict[str, Any]) -> bool:
        return (
            self.identity.serial_number not in {"", "UNVERIFIED"}
            and self.identity.firmware_version not in {"", "UNVERIFIED"}
            and self.identity.mount_revision not in {"", "UNVERIFIED", "BRIDGE-UNVERIFIED"}
            and health.get("serialNumber") == self.identity.serial_number
            and health.get("firmwareVersion") == self.identity.firmware_version
        )


def build_tfa50l_sensor_runtime(
    core: MissionCore,
    settings: RuntimeSettings,
    *,
    telemetry: Callable[[str, dict[str, Any]], None] | None = None,
) -> TFA50LSensorRuntime:
    """Construct the production UART/fusion worker from validated runtime config."""

    calibration = LidarCalibration.load(settings.sensors.lidar_calibration_path)
    adapter = TFA50LSerialAdapter(
        config=TFA50LSerialConfig(
            port=settings.sensors.lidar_port,
            baud_rate=settings.sensors.lidar_baud_rate,
            sample_hz=settings.sensors.lidar_sample_hz,
            stale_ms=settings.sensors.lidar_stale_ms,
            serial_number=settings.sensors.lidar_serial_number,
            firmware_version=settings.sensors.lidar_firmware_version,
        ),
        telemetry=telemetry,
    )
    associator = YawRangeAssociator(
        calibration,
        current_mount_revision=settings.sensors.lidar_mount_revision,
        max_age_ms=settings.sensors.lidar_stale_ms,
    )
    return TFA50LSensorRuntime(
        core,
        adapter,
        associator,
        SensorRuntimeIdentity(
            settings.sensors.lidar_serial_number,
            settings.sensors.lidar_firmware_version,
            settings.sensors.lidar_mount_revision,
        ),
    )
