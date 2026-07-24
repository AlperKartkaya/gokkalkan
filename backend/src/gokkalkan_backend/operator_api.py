"""Dry-run ve gerçek donanım operatör API servisi — Gökkalkan.

Bu modül bağımlılık içermez. Gerçek operatör paneli arkasındaki ilk
backend sözleşmesini modellemek için tasarlanmıştır. UI komutları yüksek
seviyeli niyet olarak gelir; Safety Gate değerlendirmesi burada yapılır.

HardwareAdapterBase:
  DryRunHardwareAdapter  — geliştirme/test, fiziksel çıkış yok
  CanMcuAdapter          — CAN bus üzerinden Pico RP2040 (bkz. hardware_adapter.py)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from itertools import count
from math import isfinite
from typing import Any, Callable, Literal
import time as _time

from .hardware_adapter import HardwareAdapterBase
from .telemetry_log import JsonlTelemetryStore

Mode = Literal["safe", "manual", "autonomous", "engagement", "blocked", "maintenance"]
Stage = Literal[1, 2, 3]
TargetType = Literal["F16", "Helikopter", "Balistik Füze", "Mini/Micro İHA"]
FriendFoe = Literal["Dost", "Düşman", "Bilinmeyen"]
CommandKind = Literal["ModeRequest", "StageRequest", "ManualAimCommand", "FireIntent"]
SensorSource = Literal["radar", "lidar", "camera", "fusion", "dry-run"]
ReadinessStatus = Literal["ready", "partial", "tbd", "blocked"]
BlockReason = Literal[
    "ALLOWED",
    "BLOCKED_ESTOP",
    "BLOCKED_MOTION_ZONE",
    "BLOCKED_FIRE_ZONE",
    "BLOCKED_TARGET_GATE",
    "BLOCKED_MODE",
    "BLOCKED_CONNECTION",
    "BLOCKED_ARMING",
    "BLOCKED_BACKEND",
    "BLOCKED_SENSOR",
    "BLOCKED_INVALID_COMMAND",
]

VALID_MODES: set[str] = {"safe", "manual", "autonomous", "engagement", "blocked", "maintenance"}
ENGAGEMENT_MODES: set[str] = {"autonomous", "engagement"}
MAX_MANUAL_AIM_DELTA_DEG = 10.0
MAX_MANUAL_AIM_RATE_LIMIT_DEG_PER_SEC = 30.0
# Şartname v1.3: toplam bakım bütçesi 10 dakika (600 saniye), her istek min 30 sn
MAINTENANCE_BUDGET_SEC = 600
MAINTENANCE_MIN_REQUEST_SEC = 30
# Şartname: Aşama 1 görev süresi 5 dakika (300 saniye)
STAGE1_TIME_LIMIT_SEC = 300
READINESS_SCORE: dict[ReadinessStatus, float] = {
    "ready": 1.0,
    "partial": 0.55,
    "tbd": 0.0,
    "blocked": 0.0,
}

BLOCK_COPY: dict[BlockReason, str] = {
    "ALLOWED": "Komut niyeti güvenli dry-run kanalında kabul edildi; fiziksel çıkış yok.",
    "BLOCKED_ESTOP": "Acil Durdur aktif; hareket ve atış niyeti kilitli.",
    "BLOCKED_MOTION_ZONE": "Harekete yasak alan ihlali var.",
    "BLOCKED_FIRE_ZONE": "Atışa yasak alan ihlali var.",
    "BLOCKED_TARGET_GATE": "Hedef, dost/düşman veya menzil kapısı uygun değil.",
    "BLOCKED_MODE": "Aktif mod bu komut için uygun değil.",
    "BLOCKED_CONNECTION": "Bağlantı sağlığı komut için yeterli değil.",
    "BLOCKED_ARMING": "Canlı arming kapalı; fiziksel çıkış yetkisi yok.",
    "BLOCKED_BACKEND": "Backend bağlantısı yok; gerçek komut gönderilemez.",
    "BLOCKED_SENSOR": "Perception veya sensör adapter sağlığı doğrulanmadı.",
    "BLOCKED_INVALID_COMMAND": "Komut alanları güvenli sınırlar içinde değil.",
}


def utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


Clock = Callable[[], str]


def target_range_gate(target_type: str, range_m: float) -> bool:
    """Return whether a target is inside the şartname-aligned imha range gate.

    The values mirror the documented competition ranges used elsewhere in the
    repo: F16 10-15 m, Helikopter/Balistik Füze 5-15 m, Mini/Micro İHA 0-15 m.
    """

    if target_type == "F16":
        return 10 <= range_m <= 15
    if target_type in {"Helikopter", "Balistik Füze"}:
        return 5 <= range_m <= 15
    if target_type == "Mini/Micro İHA":
        return 0 <= range_m <= 15
    return False


def stage_round_limit(stage: int) -> int:
    """Return the official operator-panel round/target context limit per stage."""

    if stage == 1:
        return 4
    if stage == 2:
        return 4
    if stage == 3:
        return 8
    return 0


def stage_expected_mode(stage: int) -> Mode:
    """Return the şartname-aligned mode expectation for a stage."""

    return "manual" if stage == 1 else "autonomous"


def _payload_int(payload: dict[str, Any], key: str) -> int | None:
    if key not in payload or isinstance(payload[key], bool):
        return None
    value = payload[key]
    if isinstance(value, int):
        return value
    if isinstance(value, float) and isfinite(value) and value.is_integer():
        return int(value)
    return None


def stage_request_payload_ok(payload: dict[str, Any]) -> bool:
    stage = _payload_int(payload, "stage")
    round_no = _payload_int(payload, "round")
    if stage not in {1, 2, 3} or round_no is None:
        return False
    return 1 <= round_no <= stage_round_limit(stage)


def _finite_payload_number(payload: dict[str, Any], key: str) -> float | None:
    if key not in payload:
        return None
    if isinstance(payload[key], bool):
        return None
    try:
        value = float(payload[key])
    except (TypeError, ValueError):
        return None
    return value if isfinite(value) else None


def manual_aim_payload_ok(payload: dict[str, Any]) -> bool:
    """Validate a high-level manual aim intent before any hardware boundary.

    These are conservative software guardrails for the dry-run command surface,
    not final mechanical limits. Real servo travel/rate limits remain owned by
    the mechanics/electronics integration pass.
    """

    pan_delta = _finite_payload_number(payload, "panDeltaDeg")
    tilt_delta = _finite_payload_number(payload, "tiltDeltaDeg")
    rate_limit = _finite_payload_number(payload, "rateLimitDegPerSec")
    return (
        pan_delta is not None
        and tilt_delta is not None
        and rate_limit is not None
        and abs(pan_delta) <= MAX_MANUAL_AIM_DELTA_DEG
        and abs(tilt_delta) <= MAX_MANUAL_AIM_DELTA_DEG
        and 0 < rate_limit <= MAX_MANUAL_AIM_RATE_LIMIT_DEG_PER_SEC
    )


@dataclass(frozen=True)
class DryRunTrack:
    trackId: str
    stage: Stage
    round: int
    targetType: TargetType
    friendFoe: FriendFoe
    rangeM: float
    bearingDeg: float
    confidence: float
    source: Literal["perception", "radar-lidar", "fused", "dry-run"] = "dry-run"
    updatedAt: str = field(default_factory=utc_now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "trackId": self.trackId,
            "stage": self.stage,
            "round": self.round,
            "targetType": self.targetType,
            "friendFoe": self.friendFoe,
            "rangeM": self.rangeM,
            "bearingDeg": self.bearingDeg,
            "confidence": self.confidence,
            "source": self.source,
            "updatedAt": self.updatedAt,
        }


@dataclass(frozen=True)
class SensorFrame:
    frameId: str
    stage: Stage
    round: int
    trackId: str
    sensor: SensorSource
    timestamp: str
    rangeM: float
    bearingDeg: float
    elevationDeg: float
    radialVelocityMps: float
    rcsDbsm: float | None
    snrDb: float | None
    pointCount: int
    quality: float
    targetType: TargetType
    friendFoe: FriendFoe
    classificationConfidence: float
    rangeGate: str
    recommendation: str
    sourceDataset: str
    replayOnly: bool = True
    rawSampleRef: str = "gokkalkan-recorded-style-fixture"

    def to_dict(self) -> dict[str, Any]:
        return {
            "frameId": self.frameId,
            "stage": self.stage,
            "round": self.round,
            "trackId": self.trackId,
            "sensor": self.sensor,
            "timestamp": self.timestamp,
            "rangeM": self.rangeM,
            "bearingDeg": self.bearingDeg,
            "elevationDeg": self.elevationDeg,
            "radialVelocityMps": self.radialVelocityMps,
            "rcsDbsm": self.rcsDbsm,
            "snrDb": self.snrDb,
            "pointCount": self.pointCount,
            "quality": self.quality,
            "targetType": self.targetType,
            "friendFoe": self.friendFoe,
            "classificationConfidence": self.classificationConfidence,
            "rangeGate": self.rangeGate,
            "recommendation": self.recommendation,
            "sourceDataset": self.sourceDataset,
            "replayOnly": self.replayOnly,
            "rawSampleRef": self.rawSampleRef,
        }


@dataclass(frozen=True)
class SafetyState:
    estop: bool
    motionZoneOk: bool
    fireZoneOk: bool
    targetGateOk: bool
    modeOk: bool
    backendConnected: bool
    perceptionConnected: bool
    sensorAdapterConnected: bool
    dryRun: bool
    liveArmEnabled: bool
    blockReason: BlockReason
    explanation: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "estop": self.estop,
            "motionZoneOk": self.motionZoneOk,
            "fireZoneOk": self.fireZoneOk,
            "targetGateOk": self.targetGateOk,
            "modeOk": self.modeOk,
            "backendConnected": self.backendConnected,
            "perceptionConnected": self.perceptionConnected,
            "sensorAdapterConnected": self.sensorAdapterConnected,
            "dryRun": self.dryRun,
            "liveArmEnabled": self.liveArmEnabled,
            "blockReason": self.blockReason,
            "explanation": self.explanation,
        }


class DryRunHardwareAdapter(HardwareAdapterBase):
    """Fiziksel çıkış üretmeyen geliştirme/test donanım adaptörü.

    HardwareAdapterBase sözleşmesini uygular; tüm komutları kaydeder
    ve physicalOutput=False döndürür.
    """

    def __init__(self, clock: Clock = utc_now) -> None:
        self._clock = clock
        self.commands: list[dict[str, Any]] = []

    def execute(self, command: dict[str, Any]) -> dict[str, Any]:
        result = {
            "adapter": "hardware_mock.dry_run",
            "commandId": command.get("commandId", f"DRY-{len(self.commands)+1:05d}"),
            "kind": command.get("kind", "Unknown"),
            "accepted": True,
            "completed": True,
            "physicalOutput": False,
            "message": "Dry-run hardware adapter komutu kaydetti; fiziksel çıkış üretilmedi.",
            "createdAt": self._clock(),
        }
        self.commands.append({"command": command, "result": result})
        return result

    def health_check(self) -> dict[str, Any]:
        return {
            "adapter": "hardware_mock.dry_run",
            "busConnected": False,
            "picoReachable": False,
            "dryRun": True,
            "physicalOutputEnabled": False,
            "commandCount": len(self.commands),
        }

    def close(self) -> None:
        pass


class OperatorService:
    """Stateful backend service for SIM, HIL and fail-closed LIVE runtimes.

    Hardware construction belongs to ``runtime_mode.build_runtime_service``;
    callers must not assemble an output-capable LIVE adapter directly.
    """

    def __init__(
        self,
        clock: Clock = utc_now,
        hardware: HardwareAdapterBase | None = None,
        telemetry: JsonlTelemetryStore | None = None,
        dry_run: bool = True,
        runtime_mode: str | None = None,
        # Pan/tilt yazılım limitleri (derece); None = sınır yok
        pan_min_deg: float | None = None,
        pan_max_deg: float | None = None,
        tilt_min_deg: float | None = None,
        tilt_max_deg: float | None = None,
    ) -> None:
        self._clock = clock
        self._ids = count(1)
        self.stage: Stage = 3
        self.mode: Mode = stage_expected_mode(self.stage)
        self.round = 1
        self.estop = False
        self.motion_zone_ok = True
        self.fire_zone_ok = True
        self.backend_connected = True
        self.perception_connected = False
        self.sensor_adapter_connected = False
        self.dry_run = dry_run
        self.runtime_mode = runtime_mode or ("SIM" if dry_run else "LIVE")
        if self.runtime_mode not in {"SIM", "HIL", "LIVE"}:
            raise ValueError(f"Geçersiz runtime mode: {self.runtime_mode}")
        self.live_arm_enabled = False
        self.hardware: HardwareAdapterBase = hardware or DryRunHardwareAdapter(clock=clock)
        self.telemetry = telemetry or JsonlTelemetryStore(clock=clock)
        self.tracks: list[DryRunTrack] = self._tracks_for_stage(self.stage, self.round)
        self.sensor_frames: list[SensorFrame] = self._sensor_frames_for_stage(self.stage, self.round, self.tracks)
        self.command_results: list[dict[str, Any]] = []
        self.events: list[dict[str, Any]] = []
        # Pan/tilt yazılım sınır alanları
        self.pan_min_deg  = pan_min_deg
        self.pan_max_deg  = pan_max_deg
        self.tilt_min_deg = tilt_min_deg
        self.tilt_max_deg = tilt_max_deg
        # Şartname v1.3 — bakım bütçesi (saniye)
        self.maintenance_budget_sec: float = MAINTENANCE_BUDGET_SEC
        self.maintenance_used_sec: float = 0.0
        self._maintenance_started_at: float | None = None  # monotonic timestamp
        # Şartname — görev timer'ı (Aşama 1: 300 sn)
        self.mission_started_at: float | None = None  # monotonic timestamp
        self.mission_time_limit_sec: int = STAGE1_TIME_LIMIT_SEC
        boot_msg = {
            "SIM": "SIM modunda başlatıldı; fiziksel adapter yüklenmedi.",
            "HIL": "HIL modunda başlatıldı; yalnız doğrulanmış sanal CAN hattı kullanılabilir.",
            "LIVE": "LIVE modunda başlatıldı; fiziksel çıkış ayrıca arm edilene kadar kapalı.",
        }[self.runtime_mode]
        self._append_event(
            "telemetry",
            "BOOT",
            boot_msg,
            {"dryRun": dry_run, "runtimeMode": self.runtime_mode},
        )

    def _tracks_for_stage(self, stage: Stage, round_no: int) -> list[DryRunTrack]:
        now = self._clock()
        if stage == 1:
            return [
                DryRunTrack("S1-ORDER-FUZE-01", 1, round_no, "Balistik Füze", "Düşman", 15.0, -24, 0.86, "dry-run", now),
                DryRunTrack("S1-ORDER-HEL-02", 1, round_no, "Helikopter", "Düşman", 10.0, -7, 0.84, "dry-run", now),
                DryRunTrack("S1-ORDER-F16-03", 1, round_no, "F16", "Düşman", 5.0, 10, 0.82, "dry-run", now),
                DryRunTrack("S1-ORDER-UAV-04", 1, round_no, "Mini/Micro İHA", "Düşman", 5.0, 27, 0.8, "dry-run", now),
            ]
        if stage == 2:
            return [
                DryRunTrack("S2-R1-L1-BALISTIK", 2, round_no, "Balistik Füze", "Düşman", 14.2, -28, 0.78, "fused", now),
                DryRunTrack("S2-R1-L2-UAV", 2, round_no, "Mini/Micro İHA", "Düşman", 11.6, 2, 0.74, "radar-lidar", now),
                DryRunTrack("S2-R1-L3-UAV", 2, round_no, "Mini/Micro İHA", "Düşman", 8.9, 31, 0.72, "radar-lidar", now),
            ]
        return [
            DryRunTrack("DRY-RUN-F16-01", 3, round_no, "F16", "Düşman", 12.4, -18, 0.96, "fused", now),
            DryRunTrack("DRY-RUN-HEL-02", 3, round_no, "Helikopter", "Dost", 8.1, 4, 0.91, "fused", now),
            DryRunTrack("DRY-RUN-UAV-03", 3, round_no, "Mini/Micro İHA", "Bilinmeyen", 4.2, 23, 0.42, "radar-lidar", now),
        ]

    def _sensor_frames_for_stage(self, stage: Stage, round_no: int, tracks: list[DryRunTrack]) -> list[SensorFrame]:
        now = self._clock()
        frames: list[SensorFrame] = []
        for index, track in enumerate(tracks, start=1):
            target = track.to_dict()
            unidentified = self._target_unidentified(target)
            range_gate = "Kimlik bekleniyor" if unidentified else self._range_gate_label(target)
            stage_note = (
                "Aşama 2: sınıflandırma zorunlu değil; takip ve imha önceliği gösteriliyor."
                if stage == 2
                else "Aşama 3: dost/düşman ve hedef tipine göre menzil kapısı uygulanıyor."
                if stage == 3
                else "Aşama 1: manuel hedef sırası ve 5/10/15 m bağlamı gösteriliyor."
            )
            recommendation = self._sensor_recommendation(target, stage_note)
            type_confidence = min(track.confidence, 0.45) if unidentified else (0.52 if stage == 2 else track.confidence)
            color_confidence = max(0.52, 1 - type_confidence) if unidentified else track.confidence
            frames.extend(
                [
                    SensorFrame(
                        f"SENS-{stage}-{round_no}-{index}-RADAR",
                        stage,
                        round_no,
                        track.trackId,
                        "radar",
                        now,
                        track.rangeM,
                        track.bearingDeg,
                        0.4 + index * 0.2,
                        -4.8 + index,
                        13.5 - index,
                        23.0 - index,
                        0,
                        min(0.98, color_confidence + 0.01),
                        track.targetType,
                        track.friendFoe,
                        type_confidence,
                        range_gate,
                        recommendation,
                        "Gökkalkan recorded-style dry-run fixture; Oxford Radar RobotCar/nuScenes biçimlerine map edilebilir.",
                        True,
                        f"replay/stage-{stage}/round-{round_no}/radar/{track.trackId}",
                    ),
                    SensorFrame(
                        f"SENS-{stage}-{round_no}-{index}-LIDAR",
                        stage,
                        round_no,
                        track.trackId,
                        "lidar",
                        now,
                        track.rangeM + 0.08,
                        track.bearingDeg + 0.5,
                        0.2 + index * 0.1,
                        -4.3 + index,
                        None,
                        None,
                        86 + index * 24,
                        min(0.99, color_confidence + 0.02),
                        track.targetType,
                        track.friendFoe,
                        type_confidence,
                        range_gate,
                        recommendation,
                        "Gökkalkan recorded-style dry-run fixture; gerçek LiDAR nokta bulutu adapterı TBD.",
                        True,
                        f"replay/stage-{stage}/round-{round_no}/lidar/{track.trackId}",
                    ),
                    SensorFrame(
                        f"SENS-{stage}-{round_no}-{index}-FUSION",
                        stage,
                        round_no,
                        track.trackId,
                        "fusion",
                        now,
                        track.rangeM,
                        track.bearingDeg,
                        0.3 + index * 0.1,
                        -4.5 + index,
                        12.0 - index if track.friendFoe == "Düşman" else 5.0,
                        21.0 - index,
                        86 + index * 24,
                        color_confidence,
                        track.targetType,
                        track.friendFoe,
                        type_confidence,
                        range_gate,
                        recommendation,
                        "Gökkalkan recorded-style dry-run fixture; canlı sensor fusion adapterı TBD.",
                        True,
                        f"replay/stage-{stage}/round-{round_no}/fusion/{track.trackId}",
                    ),
                ]
            )
        return frames

    def _target_unidentified(self, target: dict[str, Any]) -> bool:
        try:
            confidence = float(target.get("confidence", 0))
        except (TypeError, ValueError):
            confidence = 0.0
        return target.get("friendFoe") == "Bilinmeyen" or confidence < 0.6

    def _range_gate_label(self, target: dict[str, Any]) -> str:
        if self.stage == 2:
            return "Takip önceliği"
        if self._target_gate_ok_for_stage(target):
            return "Uygun"
        return "Kilitli"

    def _sensor_recommendation(self, target: dict[str, Any], stage_note: str) -> str:
        if self._target_unidentified(target):
            return f"Kimlik kesinleşmeden FireIntent kilitli; iz takipte tutulur. {stage_note}"
        if target.get("friendFoe") == "Dost":
            return f"Dost unsur korunur; FireIntent kilitli. {stage_note}"
        if self._target_gate_ok_for_stage(target):
            return f"Angajman adayı; Safety Gate ve operatör/hakem kilitleri beklenir. {stage_note}"
        return f"Hedef izlenir; menzil/mod kapısı tamamlanmadan FireIntent kilitli. {stage_note}"

    def _target_gate_ok_for_stage(self, target: dict[str, Any] | None) -> bool:
        if not target or target.get("friendFoe") != "Düşman":
            return False
        range_m = float(target.get("rangeM", -1))
        if self.stage == 1:
            return 0 < range_m <= 15
        if self.stage == 2:
            return 0 < range_m <= 15
        return target_range_gate(str(target.get("targetType")), range_m)

    def _sensor_health(self) -> dict[str, Any]:
        latest = self.sensor_frames[0].timestamp if self.sensor_frames else self._clock()
        return {
            "schemaVersion": 1,
            "status": "replay" if self.sensor_frames else "empty",
            "adapterConnected": self.sensor_adapter_connected,
            "perceptionConnected": self.perception_connected,
            "replayOnly": True,
            "sourceDataset": "Gökkalkan recorded-style dry-run fixture; gerçek radar/LiDAR verisi için Oxford Radar RobotCar veya nuScenes benzeri offline replay adapterı eklenebilir.",
            "latestFrameAt": latest,
            "frameCount": len(self.sensor_frames),
            "physicalOutputEnabled": False,
        }

    def _mission_timer(self) -> dict[str, Any]:
        """Görev timer durumunu hesapla.

        Yalnız Aşama 1'de zaman sınırı şartname tarafından tanımlanmıştır (300 sn).
        Diğer aşamalarda missionTimeLimitSec=None ve missionRemainingSeconds=None döner.
        """
        has_limit = self.stage == 1
        elapsed = 0.0
        if self.mission_started_at is not None:
            elapsed = max(0.0, _time.monotonic() - self.mission_started_at)
        remaining: float | None = None
        if has_limit:
            remaining = max(0.0, self.mission_time_limit_sec - elapsed)
        return {
            "missionElapsedSec": round(elapsed, 1),
            "missionRemainingSeconds": round(remaining, 1) if remaining is not None else None,
            "missionTimeLimitSec": self.mission_time_limit_sec if has_limit else None,
            "missionTimerRunning": self.mission_started_at is not None,
        }

    def _maintenance_state(self) -> dict[str, Any]:
        """Şartname v1.3 bakım bütçesi durumu."""
        in_maintenance = self.mode == "maintenance" and self._maintenance_started_at is not None
        current_elapsed = 0.0
        if in_maintenance and self._maintenance_started_at is not None:
            current_elapsed = max(0.0, _time.monotonic() - self._maintenance_started_at)
        used = self.maintenance_used_sec + current_elapsed
        remaining = max(0.0, self.maintenance_budget_sec - used)
        return {
            "maintenanceBudgetSec": self.maintenance_budget_sec,
            "maintenanceUsedSec": round(used, 1),
            "maintenanceRemainingBudgetSec": round(remaining, 1),
            "maintenanceMinRequestSec": MAINTENANCE_MIN_REQUEST_SEC,
        }

    def snapshot(self) -> dict[str, Any]:
        selected = self.tracks[0] if self.tracks else None
        result = {
            "app": "gokkalkan-operator-api",
            "version": 1,
            "mode": self.mode,
            "stage": self.stage,
            "round": self.round,
            "dryRun": self.dry_run,
            "runtimeMode": self.runtime_mode,
            "liveArmEnabled": self.live_arm_enabled,
            "tracks": [track.to_dict() for track in self.tracks],
            "sensorFrames": [frame.to_dict() for frame in self.sensor_frames],
            "sensorHealth": self._sensor_health(),
            "safety": self.evaluate_safety("FireIntent", selected.to_dict() if selected else None).to_dict(),
            "commandResults": self.command_results[:8],
            "events": self.events[:20],
            "physicalOutputEnabled": False,
            "telemetry": self.telemetry.metadata(),
        }
        result.update(self._mission_timer())
        result.update(self._maintenance_state())
        return result

    def sensor_frames_snapshot(self) -> dict[str, Any]:
        return {
            "schemaVersion": 1,
            "generatedAt": self._clock(),
            "stage": self.stage,
            "round": self.round,
            "sensorHealth": self._sensor_health(),
            "frames": [frame.to_dict() for frame in self.sensor_frames],
            "physicalOutputEnabled": False,
            "replayOnly": True,
        }

    def health(self) -> dict[str, Any]:
        return {
            "ok": True,
            "service": "gokkalkan-operator-api",
            "mode": self.mode,
            "dryRun": self.dry_run,
            "runtimeMode": self.runtime_mode,
            "physicalOutputEnabled": False,
            "telemetry": self.telemetry.metadata(),
            "timestamp": self._clock(),
        }

    def readiness(self) -> dict[str, Any]:
        """Return an honest final-phase integration readiness report.

        This is an internal implementation-readiness checklist, not an official
        competition compliance score. Hardware values and protocols stay TBD
        until the real radar/LiDAR, MCU and firing-line electronics are chosen.
        """

        items = [
            self._readiness_item(
                "backend_api",
                "Backend Operatör API",
                "ready" if self.backend_connected else "blocked",
                "Backend",
                "GET /state, GET /sensor-frames, GET /readiness, POST /stage, POST /mode, POST /fire-intent, /telemetry/export ve /replay çalışıyor.",
                "API hata toleransı ve oturum/imza katmanı saha entegrasyonu öncesi eklenecek.",
                "StageRequest, ModeRequest, SensorFrame, FireIntent, CommandResult",
            ),
            self._readiness_item(
                "safety_gate",
                "Safety Gate",
                "partial",
                "Backend",
                "Acil durdurma, mod, dost/düşman, menzil ve dry-run arming kontrolleri backend tarafında uygulanıyor.",
                "Gerçek Acil Durdur, yasak alan ve hakem/operatör kilit girişleri elektronik arayüzle bağlanacak.",
                "SafetyState, HardwareCommand",
            ),
            self._readiness_item(
                "telemetry_replay",
                "Telemetri / Replay Kanıtı",
                "ready",
                "Backend + UI",
                f"JSONL kayıt yolu: {self.telemetry.path}; kayıt sayısı: {self.telemetry.metadata()['recordCount']}. Replay yalnız kayıt okur.",
                "KTR için indirilebilir/sürüm bilgili kanıt paketi formatı netleştirilecek.",
                "TelemetryEvent, CommandResult, HardwareResult",
            ),
            self._readiness_item(
                "operator_panel_ui",
                "Operatör Paneli UI",
                "ready",
                "Frontend",
                "React panel aşama/tur seçimi, radar/LiDAR replay katmanı, sınıflandırma/dost-düşman güveni, FireIntent, DURDUR, bakım/diagnostik ve kanıt/replay yüzeylerini gösteriyor.",
                "Canlı kamera/perception katmanı ve saha kiosk/ekran düzeni gerçek donanımla ayrıca denenmeli.",
                "Kullanıcı Arayüzü, StageRequest, SensorFrame, TrackState, FireIntent",
            ),
            self._readiness_item(
                "perception_adapter",
                "Perception Adapter",
                "ready" if self.perception_connected else "tbd",
                "Perception",
                "Şu an dry-run TrackState kullanılıyor; canlı sınıflandırma bağlantısı yapılmadı.",
                "Kamera + model çıktısını TrackState sözleşmesine bağla.",
                "TrackState",
            ),
            self._readiness_item(
                "radar_lidar_adapter",
                "Radar/LiDAR Adapter",
                "ready" if self.sensor_adapter_connected else "tbd",
                "Sensör",
                "Menzil/açı/kalite verisi için SensorFrame replay sözleşmesi ve fixture görünümü hazır; gerçek sensör protokolü seçilmedi.",
                "Seçilen radar/LiDAR için güç, veri, timestamp ve sağlık mesajı arayüzünü doldur.",
                "SensorFrame",
            ),
            self._readiness_item(
                "hardware_adapter",
                "Hardware Adapter",
                "partial",
                "Backend + Elektronik",
                "hardware_mock.dry_run komutları kaydediyor ve physicalOutput=false döndürüyor.",
                "MCU haberleşme protokolü (UART/RS422/CAN/Ethernet TBD) ve imha hattı interlock mesajları bağlanacak.",
                "HardwareCommand, HardwareResult",
            ),
            self._readiness_item(
                "live_arming",
                "Canlı Arming / Fiziksel Çıkış",
                "blocked",
                "Safety + Elektronik",
                "Bu geliştirme ortamında canlı arming kapalı; fiziksel çıkış yetkisi yok.",
                "Saha öncesi iki aşamalı arming, hakem/operatör kilidi ve fiziksel interlock doğrulaması gerekir.",
                "ArmingState, InterlockState",
            ),
            self._readiness_item(
                "ktr_interfaces",
                "KTR Arayüz Anlatımı",
                "partial",
                "Dokümantasyon",
                "Kullanıcı, yazılım mesaj, sensör/veri ve elektronik arayüz tabloları repo dokümanlarında başlatıldı.",
                "Kesin gerilim, kablo, MCU ve sensör protokol değerleri donanım seçimi sonrası TBD'den çıkarılacak.",
                "KTR arayüz tabloları",
            ),
        ]
        score = sum(READINESS_SCORE[item["status"]] for item in items)
        percent = round((score / len(items)) * 100)
        next_actions = [item["nextStep"] for item in items if item["status"] in {"blocked", "tbd"}][:4]
        if len(next_actions) < 4:
            next_actions.extend(item["nextStep"] for item in items if item["status"] == "partial")
            next_actions = next_actions[:4]

        return {
            "schemaVersion": 1,
            "generatedAt": self._clock(),
            "summary": "Dry-run operatör UI ve backend zinciri çalışıyor; final fazı için perception, radar/LiDAR, MCU ve canlı arming arayüzleri hâlâ TBD/entegrasyon bekliyor.",
            "scoreBasis": "Bu yüzde resmi yarışma uygunluk skoru değildir; repo içi entegrasyon kontrol listesidir.",
            "readinessPercent": percent,
            "physicalOutputEnabled": False,
            "mode": self.mode,
            "dryRun": self.dry_run,
            "items": items,
            "nextCriticalActions": next_actions,
        }

    def telemetry_export(self) -> dict[str, Any]:
        entries = self.telemetry.read_all()
        unsafe_replay = self._unsafe_physical_output_entries(entries)
        return {
            "schemaVersion": 1,
            "generatedAt": self._clock(),
            "physicalOutputEnabled": False,
            "unsafeReplayEvidence": unsafe_replay,
            "evidenceWarning": "Replay log içinde physicalOutput=true kaydı var; kanıt güvenli kabul edilmez." if unsafe_replay else "",
            "telemetry": self.telemetry.metadata(),
            "state": self.snapshot(),
            "events": self.events[:50],
            "commandResults": self.command_results[:50],
            "entries": entries,
        }

    def _readiness_item(
        self,
        item_id: str,
        label: str,
        status: ReadinessStatus,
        owner: str,
        evidence: str,
        next_step: str,
        ktr_interface: str,
    ) -> dict[str, Any]:
        return {
            "id": item_id,
            "label": label,
            "status": status,
            "owner": owner,
            "evidence": evidence,
            "nextStep": next_step,
            "ktrInterface": ktr_interface,
        }

    def replay(self, limit: int | None = None) -> dict[str, Any]:
        entries = self.telemetry.read_all(limit=limit)
        unsafe_replay = self._unsafe_physical_output_entries(entries)
        events = [entry["payload"] for entry in entries if entry.get("recordType") == "event" and isinstance(entry.get("payload"), dict)]
        command_results = [entry["payload"] for entry in entries if entry.get("recordType") == "command_result" and isinstance(entry.get("payload"), dict)]
        hardware_results = [entry["payload"] for entry in entries if entry.get("recordType") == "hardware_result" and isinstance(entry.get("payload"), dict)]
        return {
            "schemaVersion": 1,
            "generatedAt": self._clock(),
            "sourceLogPath": str(self.telemetry.path),
            "physicalOutputEnabled": False,
            "unsafeReplayEvidence": unsafe_replay,
            "evidenceWarning": "Replay log içinde physicalOutput=true kaydı var; kanıt güvenli kabul edilmez." if unsafe_replay else "",
            "replayOnly": True,
            "entries": entries,
            "events": events,
            "commandResults": command_results,
            "hardwareResults": hardware_results,
        }

    def _unsafe_physical_output_entries(self, entries: list[dict[str, Any]]) -> bool:
        return any(isinstance(entry.get("payload"), dict) and entry["payload"].get("physicalOutput") is True for entry in entries)

    def reset_telemetry(self) -> dict[str, Any]:
        self.mode = "safe"
        self.stage = 3
        self.round = 1
        self.tracks = self._tracks_for_stage(self.stage, self.round)
        self.sensor_frames = self._sensor_frames_for_stage(self.stage, self.round, self.tracks)
        self.command_results = []
        self.events = []
        # DryRunHardwareAdapter'ın .commands listesini sıfırla (varsa)
        if hasattr(self.hardware, "commands"):
            self.hardware.commands = []
        self._ids = count(1)
        # Bakım bütçesi ve görev timer'ını sıfırla
        self.maintenance_used_sec = 0.0
        self._maintenance_started_at = None
        self.mission_started_at = None
        self.telemetry.reset()
        self._append_event("telemetry", "RESET", "Telemetri sıfırlandı; fiziksel çıkış yok.", {})
        return {"ok": True, "physicalOutputEnabled": False, "telemetry": self.telemetry.metadata(), "state": self.snapshot()}

    def evaluate_safety(self, kind: CommandKind, target: dict[str, Any] | None = None, payload: dict[str, Any] | None = None) -> SafetyState:
        payload = payload or {}
        # Çalışma modu güvenlik açısından sunucuya aittir. İstemcinin dryRun
        # beyanı canlı servisi simülasyon gibi göstererek arm/sensör kapılarını
        # gevşetemez.
        dry_run = self.dry_run
        live_arm_enabled = self.live_arm_enabled and not dry_run
        target_gate_ok = True
        mode_ok = True
        command_payload_ok = True

        if kind == "FireIntent":
            payload_stage = _payload_int(payload, "stage")
            payload_round = _payload_int(payload, "round")
            command_payload_ok = payload_stage == self.stage and payload_round == self.round
            mode_ok = self.mode == "manual" if self.stage == 1 else self.mode in ENGAGEMENT_MODES
            target_gate_ok = self._target_gate_ok_for_stage(target)
        elif kind == "ManualAimCommand":
            mode_ok = self.stage == 1 and self.mode == "manual" and bool(payload.get("deadmanActive"))
            command_payload_ok = manual_aim_payload_ok(payload)
        elif kind == "ModeRequest":
            mode_ok = payload.get("requestedMode") in VALID_MODES
        elif kind == "StageRequest":
            command_payload_ok = stage_request_payload_ok(payload)

        block: BlockReason = "ALLOWED"
        if self.estop:
            block = "BLOCKED_ESTOP"
        elif not self.backend_connected:
            block = "BLOCKED_BACKEND"
        elif not dry_run and not live_arm_enabled:
            block = "BLOCKED_ARMING"
        elif kind == "ManualAimCommand" and not self.motion_zone_ok:
            block = "BLOCKED_MOTION_ZONE"
        elif kind == "ManualAimCommand" and not self._pantilt_within_soft_limits(payload):
            block = "BLOCKED_MOTION_ZONE"
        elif kind == "FireIntent" and not self.fire_zone_ok:
            block = "BLOCKED_FIRE_ZONE"
        elif not mode_ok:
            block = "BLOCKED_MODE"
        elif kind in {"ManualAimCommand", "FireIntent", "StageRequest"} and not command_payload_ok:
            block = "BLOCKED_INVALID_COMMAND"
        elif not target_gate_ok:
            block = "BLOCKED_TARGET_GATE"
        elif not dry_run and (not self.perception_connected or not self.sensor_adapter_connected):
            block = "BLOCKED_SENSOR"

        return SafetyState(
            estop=self.estop,
            motionZoneOk=self.motion_zone_ok,
            fireZoneOk=self.fire_zone_ok,
            targetGateOk=target_gate_ok,
            modeOk=mode_ok,
            backendConnected=self.backend_connected,
            perceptionConnected=self.perception_connected,
            sensorAdapterConnected=self.sensor_adapter_connected,
            dryRun=dry_run,
            liveArmEnabled=live_arm_enabled,
            blockReason=block,
            explanation=BLOCK_COPY[block],
        )

    def handle_mode_request(self, payload: dict[str, Any]) -> dict[str, Any]:
        requested = payload.get("requestedMode")
        safety = self.evaluate_safety("ModeRequest", payload=payload)
        accepted = safety.blockReason == "ALLOWED"
        if accepted:
            self.mode = requested  # type: ignore[assignment]
        result = self._command_result("ModeRequest", accepted, safety.blockReason)
        self._append_event("mode", "ModeRequest", result["message"], {"requestedMode": requested, "safety": safety.to_dict(), "result": result})
        return {"result": result, "safety": safety.to_dict(), "state": self.snapshot()}

    def handle_maintenance_request(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Bakım isteği — Şartname v1.3: toplam bütçe 600 sn, istek başı min 30 sn.

        Kabul koşulları:
        - Kalan bütçe >= MAINTENANCE_MIN_REQUEST_SEC
        - Sistem zaten maintenance modunda değil
        - E-Stop aktif değil
        """
        if self.estop:
            return {"ok": False, "blocked": True, "reason": "BLOCKED_ESTOP",
                    "message": "Acil Durdur aktif; bakım isteği reddedildi."}
        if self.mode == "maintenance":
            return {"ok": False, "blocked": True, "reason": "ALREADY_MAINTENANCE",
                    "message": "Sistem zaten bakım modunda."}
        maint = self._maintenance_state()
        if maint["maintenanceRemainingBudgetSec"] < MAINTENANCE_MIN_REQUEST_SEC:
            return {"ok": False, "blocked": True, "reason": "MAINTENANCE_BUDGET_EXHAUSTED",
                    "message": f"Bakım bütçesi tükendi ({maint['maintenanceUsedSec']:.0f}/{self.maintenance_budget_sec:.0f} sn kullanıldı)."}
        prev_mode = self.mode
        self.mode = "maintenance"
        self._maintenance_started_at = _time.monotonic()
        self._append_event("maintenance", "MAINTENANCE_START",
                           f"Bakım modu başlatıldı (önceki mod: {prev_mode}).",
                           {"prevMode": prev_mode, "maintenanceState": maint})
        return {"ok": True, "blocked": False, "maintenanceState": maint, "state": self.snapshot()}

    def maintenance_end(self) -> dict[str, Any]:
        """Bakım süresini sonlandır; bütçeyi güncelle ve safe moda dön.

        En az MAINTENANCE_MIN_REQUEST_SEC kadar süre kayıt edilir.
        """
        if self.mode != "maintenance" or self._maintenance_started_at is None:
            return {"ok": False, "reason": "NOT_IN_MAINTENANCE", "message": "Sistem bakım modunda değil."}
        elapsed = max(MAINTENANCE_MIN_REQUEST_SEC, _time.monotonic() - self._maintenance_started_at)
        self.maintenance_used_sec += elapsed
        self._maintenance_started_at = None
        self.mode = "safe"
        self._append_event("maintenance", "MAINTENANCE_END",
                           f"Bakım sona erdi ({elapsed:.1f} sn); safe moda dönüldü.",
                           {"elapsedSec": elapsed, "totalUsedSec": self.maintenance_used_sec})
        return {"ok": True, "elapsedSec": round(elapsed, 1),
                "maintenanceState": self._maintenance_state(), "state": self.snapshot()}

    def handle_stage_request(self, payload: dict[str, Any]) -> dict[str, Any]:
        safety = self.evaluate_safety("StageRequest", payload=payload)
        accepted = safety.blockReason == "ALLOWED"
        if accepted:
            requested_stage = _payload_int(payload, "stage")
            requested_round = _payload_int(payload, "round")
            assert requested_stage in {1, 2, 3}
            assert requested_round is not None
            self.stage = requested_stage  # type: ignore[assignment]
            self.round = requested_round
            self.mode = stage_expected_mode(self.stage)
            self.tracks = self._tracks_for_stage(self.stage, self.round)
            self.sensor_frames = self._sensor_frames_for_stage(self.stage, self.round, self.tracks)
            # Şartname: Aşama 1 başlayınca görev timer'ı sıfırla ve başlat
            if self.stage == 1:
                self.mission_started_at = _time.monotonic()
                self.mission_time_limit_sec = STAGE1_TIME_LIMIT_SEC
            else:
                self.mission_started_at = None
        result = self._command_result("StageRequest", accepted, safety.blockReason)
        self._append_event(
            "mission",
            "StageRequest",
            result["message"],
            {
                "requestedStage": payload.get("stage"),
                "requestedRound": payload.get("round"),
                "expectedMode": stage_expected_mode(self.stage) if accepted else None,
                "safety": safety.to_dict(),
                "result": result,
                "physicalOutput": False,
            },
        )
        return {"result": result, "safety": safety.to_dict(), "state": self.snapshot()}

    def handle_manual_aim(self, payload: dict[str, Any]) -> dict[str, Any]:
        safety = self.evaluate_safety("ManualAimCommand", payload=payload)
        accepted = safety.blockReason == "ALLOWED"
        result = self._command_result("ManualAimCommand", accepted, safety.blockReason)
        hardware_result = None
        if accepted:
            hardware_result = self.hardware.execute({"commandId": result["commandId"], "kind": "ManualAimCommand", "payload": payload})
            self.telemetry.append("hardware_result", hardware_result)
        self._append_event("command", "ManualAimCommand", result["message"], {"safety": safety.to_dict(), "result": result, "hardwareResult": hardware_result})
        return {"result": result, "safety": safety.to_dict(), "hardwareResult": hardware_result, "state": self.snapshot()}

    def handle_fire_intent(self, payload: dict[str, Any]) -> dict[str, Any]:
        target = self._find_track(str(payload.get("targetId", "")))
        target_dict = target.to_dict() if target else None
        safety = self.evaluate_safety("FireIntent", target=target_dict, payload=payload)
        accepted = safety.blockReason == "ALLOWED"
        result = self._command_result("FireIntent", accepted, safety.blockReason)
        hardware_result = None
        if accepted:
            hardware_result = self.hardware.execute({"commandId": result["commandId"], "kind": "FireIntent", "target": target_dict, "payload": payload})
            self.telemetry.append("hardware_result", hardware_result)
        self._append_event("fire", "FireIntent", result["message"], {"target": target_dict, "safety": safety.to_dict(), "result": result, "hardwareResult": hardware_result})
        return {"result": result, "safety": safety.to_dict(), "hardwareResult": hardware_result, "state": self.snapshot()}

    def _pantilt_within_soft_limits(self, payload: dict[str, Any]) -> bool:
        """Pan/tilt yazılım limit kontrolü.

        ManualAimCommand payload'ındaki delta'ları mevcut MCU pozisyonuna ekleyerek
        hedef açının soft limitler içinde kalıp kalmadığını doğrular.
        hardware.health_check() çağrısından mevcut pozisyon alınır;
        adapter bağlı değilse veya limit tanımlanmamışsa True döner.
        """
        try:
            hc = self.hardware.health_check()
            mcu = hc.get("mcuStatus", {})
            cur_pan  = float(mcu.get("panDeg",  0.0))
            cur_tilt = float(mcu.get("tiltDeg", 0.0))
        except Exception:
            return True   # adapter erişilemezse bloklama

        new_pan  = cur_pan  + float(payload.get("panDeltaDeg",  0.0))
        new_tilt = cur_tilt + float(payload.get("tiltDeltaDeg", 0.0))

        if self.pan_min_deg  is not None and new_pan  < self.pan_min_deg:
            return False
        if self.pan_max_deg  is not None and new_pan  > self.pan_max_deg:
            return False
        if self.tilt_min_deg is not None and new_tilt < self.tilt_min_deg:
            return False
        if self.tilt_max_deg is not None and new_tilt > self.tilt_max_deg:
            return False
        return True

    def set_estop(self, active: bool) -> None:
        """E-Stop durumunu dışarıdan güncelle.

        CAN üzerinden gelen Pico bildirimi veya GPIO interrupt'ı
        bu yöntemi çağırır. Thread-safe: sadece bool ataması.
        """
        prev = self.estop
        self.estop = active
        if active != prev:
            self._append_event(
                "safety",
                "ESTOP_CHANGE",
                f"E-Stop {'aktif' if active else 'pasif'} — harici sinyal.",
                {"active": active, "source": "gpio_or_can"},
            )

    def update_tracks(self, tracks_data: list[dict[str, Any]], source: str = "perception") -> dict[str, Any]:
        """Perception veya sensör adapter'ından gelen canlı track listesini güncelle.

        Endpoint: POST /tracks/update
        Body: {"source": "perception", "tracks": [...]}

        Her track dict en az şu alanları içermelidir:
          trackId, targetType, friendFoe, rangeM, bearingDeg, confidence
        Eksik alanlar güvenli varsayılanlarla doldurulur.
        """
        if not isinstance(tracks_data, list):
            return {"ok": False, "error": "tracks bir liste olmalıdır."}

        now = self._clock()
        updated: list[DryRunTrack] = []
        for raw in tracks_data:
            if not isinstance(raw, dict):
                continue
            try:
                track = DryRunTrack(
                    trackId    = str(raw.get("trackId", f"LIVE-{now}")),
                    stage      = self.stage,
                    round      = self.round,
                    targetType = str(raw.get("targetType", "Mini/Micro İHA")),
                    friendFoe  = str(raw.get("friendFoe",  "Bilinmeyen")),
                    rangeM     = float(raw.get("rangeM",    0.0)),
                    bearingDeg = float(raw.get("bearingDeg", 0.0)),
                    confidence = float(raw.get("confidence", 0.5)),
                    source     = "perception",
                    updatedAt  = now,
                )
                updated.append(track)
            except (TypeError, ValueError) as exc:
                return {"ok": False, "error": f"Geçersiz track verisi: {exc}"}

        self.tracks = updated
        self.perception_connected = True
        self._append_event(
            "perception",
            "TRACKS_UPDATE",
            f"{len(updated)} track güncellendi (kaynak={source}).",
            {"count": len(updated), "source": source},
        )
        return {
            "ok": True,
            "count": len(updated),
            "source": source,
            "perceptionConnected": True,
        }

    def _find_track(self, track_id: str) -> DryRunTrack | None:
        return next((track for track in self.tracks if track.trackId == track_id), None)

    def _command_result(self, kind: CommandKind, accepted: bool, block: BlockReason) -> dict[str, Any]:
        dry_run = self.dry_run
        command_id = f"CMD-{next(self._ids):05d}"
        message = (
            "Dry-run komut niyeti backend tarafından kaydedildi; fiziksel çıkış üretilmedi."
            if accepted and dry_run
            else "Komut backend tarafından kabul edildi."
            if accepted
            else BLOCK_COPY[block]
        )
        result = {
            "commandId": command_id,
            "kind": kind,
            "accepted": accepted,
            "completed": accepted and dry_run,
            "dryRun": dry_run,
            "safetyBlockReason": block,
            "message": message,
            "physicalOutput": False,
            "createdAt": self._clock(),
        }
        self.command_results.insert(0, result)
        self.command_results = self.command_results[:20]
        self.telemetry.append("command_result", result)
        return result

    def _append_event(self, event_type: str, decision: str, reason: str, payload: dict[str, Any]) -> None:
        event = {
            "id": next(self._ids),
            "timestamp": self._clock(),
            "stage": self.stage,
            "mode": self.mode,
            "type": event_type,
            "decision": decision,
            "reason": reason,
            "payload": payload,
            "physicalOutput": False,
        }
        self.events.insert(0, event)
        self.events = self.events[:50]
        self.telemetry.append("event", event)
