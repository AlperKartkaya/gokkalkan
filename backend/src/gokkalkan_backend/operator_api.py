"""Dry-run ve gerçek donanım operatör API servisi — Gökkalkan.

Bu modül bağımlılık içermez. Gerçek operatör paneli arkasındaki ilk
backend sözleşmesini modellemek için tasarlanmıştır. UI komutları yüksek
seviyeli niyet olarak gelir; Safety Gate değerlendirmesi burada yapılır.

HardwareAdapterBase:
  DryRunHardwareAdapter  — geliştirme/test, fiziksel çıkış yok
  UsbSerialMcuAdapter    — USB CDC Serial üzerinden Pico RP2040
  CanMcuAdapter          — yalnız tarihsel CAN test uyumluluğu
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from itertools import count
from math import isfinite
import threading
import time as _time
import shutil
from typing import Any, Callable, Literal

from .course_geometry import (
    CourseGeometry,
    CourseTrackEstimator,
    load_course_geometry,
)
from .ballistic_compensation import BallisticCompensation
from .hardware_adapter import HardwareAdapterBase
from .mission_flow import MissionFlow
from .range_fusion import FusedRangeDecision
from .safety_gate import (
    ForbiddenZone,
    LiveArmController,
    SafetyInputs,
    evaluate_safety as evaluate_pure_safety,
)
from .telemetry_log import JsonlTelemetryStore
from .turret_calibration import TurretCalibration

Mode = Literal["safe", "manual", "autonomous", "engagement", "blocked", "maintenance"]
Stage = Literal[1, 2, 3]
TargetType = Literal[
    "F16",
    "Helikopter",
    "Balistik Füze",
    "Mini/Micro İHA",
    "Bilinmeyen",
]
FriendFoe = Literal["Dost", "Düşman", "Bilinmeyen"]
CommandKind = Literal["ModeRequest", "StageRequest", "ManualAimCommand", "AutonomousAimCommand", "FireIntent"]
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
    "BLOCKED_ZONE_CONFIG",
]

VALID_MODES: set[str] = {"safe", "manual", "autonomous", "engagement", "blocked", "maintenance"}
ENGAGEMENT_MODES: set[str] = {"autonomous", "engagement"}
MAX_MANUAL_AIM_DELTA_DEG = 10.0
MAX_MANUAL_AIM_RATE_LIMIT_DEG_PER_SEC = 30.0
# Şartname v1.4: toplam bakım bütçesi 10 dakika (600 saniye), her istek min 30 sn
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
    "BLOCKED_ZONE_CONFIG": "Yasak bölge yapılandırması geçersiz; komut fail-closed reddedildi.",
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
    receiveMonotonicNs: int = field(default_factory=_time.monotonic_ns)
    yawErrorDeg: float | None = None
    pitchErrorDeg: float | None = None
    aimCalibrationId: str | None = None
    aimCalibrationHash: str | None = None
    aimValid: bool = False
    courseState: dict[str, Any] | None = None
    objectRole: Literal["target", "balloon"] = "target"
    fireCandidate: bool = True
    bboxPx: tuple[float, float, float, float] | None = None
    frameSizePx: tuple[int, int] | None = None

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
            "receiveMonotonicNs": self.receiveMonotonicNs,
            "yawErrorDeg": self.yawErrorDeg,
            "pitchErrorDeg": self.pitchErrorDeg,
            "aimCalibrationId": self.aimCalibrationId,
            "aimCalibrationHash": self.aimCalibrationHash,
            "aimValid": self.aimValid,
            "courseState": self.courseState,
            "objectRole": self.objectRole,
            "fireCandidate": self.fireCandidate,
            "bboxPx": list(self.bboxPx) if self.bboxPx is not None else None,
            "frameSizePx": list(self.frameSizePx) if self.frameSizePx is not None else None,
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
    decisionSnapshot: dict[str, Any] = field(default_factory=dict)

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
            "decisionSnapshot": self.decisionSnapshot,
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
            "encoderOk": True,
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
        motion_forbidden_zones: tuple[ForbiddenZone, ...] = (),
        fire_forbidden_zones: tuple[ForbiddenZone, ...] = (),
        arm_hold_seconds: float = 2.0,
        arm_timeout_seconds: float = 3.0,
        physical_interlock_ok: bool = False,
        backend_readiness_ok: bool = False,
        disk_min_free_bytes: int = 0,
        lidar_stale_seconds: float = 0.3,
        course_geometry: CourseGeometry | None = None,
        target_speed_prior_mps: float = 0.4,
        turret_calibration: TurretCalibration | None = None,
        ballistic_compensation: BallisticCompensation | None = None,
        camera_calibration_hash: str | None = None,
    ) -> None:
        self._clock = clock
        self._ids = count(1)
        self._owner_thread_id: int | None = None
        self._active_command_id: str | None = None
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
        self.arm_controller = LiveArmController(
            hold_seconds=arm_hold_seconds,
            timeout_seconds=arm_timeout_seconds,
        )
        self.physical_interlock_ok = physical_interlock_ok
        self.backend_readiness_ok = backend_readiness_ok
        self.pico_safe = dry_run
        self.pico_state = "SAFE" if dry_run else "UNKNOWN"
        self.pico_heartbeat_ok = dry_run
        self.can_ok = dry_run
        self.encoder_ok = dry_run
        self.camera_ok = dry_run
        self.track_ok = dry_run
        self.lidar_ok = dry_run
        self.disk_ok = True
        self.disk_min_free_bytes = disk_min_free_bytes
        self.lidar_stale_seconds = lidar_stale_seconds
        self._last_lidar_update_monotonic: float | None = None
        self.latest_lidar_reading: dict[str, Any] | None = None
        self.estop_physical_active = False
        self.estop_reset_required = False
        self.motion_forbidden_zones = motion_forbidden_zones
        self.fire_forbidden_zones = fire_forbidden_zones
        self.course_geometry = course_geometry or load_course_geometry()
        self.target_speed_prior_mps = target_speed_prior_mps
        self.course_estimator = CourseTrackEstimator(
            self.course_geometry,
            initial_speed_mps=target_speed_prior_mps,
        )
        self.turret_calibration = turret_calibration or TurretCalibration.identity()
        self.ballistic_compensation = (
            ballistic_compensation or BallisticCompensation.unverified()
        )
        self.camera_calibration_hash = camera_calibration_hash
        self.hardware: HardwareAdapterBase = hardware or DryRunHardwareAdapter(clock=clock)
        self.telemetry = telemetry or JsonlTelemetryStore(clock=clock)
        self.tracks: list[DryRunTrack] = self._tracks_for_stage(self.stage, self.round)
        self.sensor_frames: list[SensorFrame] = self._sensor_frames_for_stage(self.stage, self.round, self.tracks)
        self.mission_flow = MissionFlow(stage=self.stage, round=self.round)
        self.mission_flow.start_stage(
            self.stage,
            self.round,
            (track.to_dict() for track in self.tracks),
            reason="BOOT_DEFAULT_STAGE",
        )
        self.command_results: list[dict[str, Any]] = []
        self.events: list[dict[str, Any]] = []
        # Pan/tilt yazılım sınır alanları
        self.pan_min_deg  = pan_min_deg
        self.pan_max_deg  = pan_max_deg
        self.tilt_min_deg = tilt_min_deg
        self.tilt_max_deg = tilt_max_deg
        # Şartname v1.4 — bakım bütçesi (saniye)
        self.maintenance_budget_sec: float = MAINTENANCE_BUDGET_SEC
        self.maintenance_used_sec: float = 0.0
        self._maintenance_started_at: float | None = None  # monotonic timestamp
        # Şartname — görev timer'ı (Aşama 1: 300 sn)
        self.mission_started_at: float | None = None  # monotonic timestamp
        self._mission_elapsed_before_pause_sec: float = 0.0
        self.mission_time_limit_sec: int = STAGE1_TIME_LIMIT_SEC
        boot_msg = {
            "SIM": "SIM modunda başlatıldı; fiziksel adapter yüklenmedi.",
            "HIL": "HIL modunda başlatıldı; fiziksel çıkış kapalı, yalnız lamba/yapay yük kullanılabilir.",
            "LIVE": "LIVE modunda başlatıldı; fiziksel çıkış ayrıca arm edilene kadar kapalı.",
        }[self.runtime_mode]
        self._append_event(
            "telemetry",
            "BOOT",
            boot_msg,
            {"dryRun": dry_run, "runtimeMode": self.runtime_mode},
        )

    def bind_owner_thread(self, thread_id: int) -> None:
        """Bind production mutations to the Mission Core reducer thread."""

        if self._owner_thread_id not in {None, thread_id}:
            raise RuntimeError("OperatorService already has a different owner")
        self._owner_thread_id = thread_id

    def set_command_context(self, command_id: str | None) -> None:
        self._require_owner()
        self._active_command_id = command_id

    def _require_owner(self) -> None:
        owner = self._owner_thread_id
        if owner is not None and threading.get_ident() != owner:
            raise RuntimeError(
                "state mutation is restricted to the Mission Core owner thread"
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
        if self.stage == 2 and target.get("friendFoe") != "Dost":
            return (
                "Aşama 2'de tip sınıflandırması zorunlu değildir; "
                f"backend menzil/iz önceliğini kullanır. {stage_note}"
            )
        if self._target_unidentified(target):
            return f"Kimlik kesinleşmeden FireIntent kilitli; iz takipte tutulur. {stage_note}"
        if target.get("friendFoe") == "Dost":
            return f"Dost unsur korunur; FireIntent kilitli. {stage_note}"
        if self._target_gate_ok_for_stage(target):
            return f"Angajman adayı; Safety Gate ve operatör/hakem kilitleri beklenir. {stage_note}"
        return f"Hedef izlenir; menzil/mod kapısı tamamlanmadan FireIntent kilitli. {stage_note}"

    def _target_gate_ok_for_stage(self, target: dict[str, Any] | None) -> bool:
        if not target:
            return False
        range_m = float(target.get("rangeM", -1))
        if self.stage == 1:
            return 0 < range_m <= 15
        if self.stage == 2:
            return (
                target.get("friendFoe") != "Dost"
                and 0 < range_m <= 15
                and self._course_gate_ok(target)
            )
        if target.get("friendFoe") != "Düşman":
            return False
        measured_source_ok = (
            self.dry_run
            or target.get("source") in {"radar-lidar", "fused"}
        )
        return (
            measured_source_ok
            and self._course_gate_ok(target)
            and target_range_gate(
                str(target.get("targetType")),
                range_m,
            )
        )

    @staticmethod
    def _course_gate_ok(target: dict[str, Any]) -> bool:
        """Fail closed outside the canonical poligon when mapping is present."""

        course_state = target.get("courseState")
        if course_state is None:
            return True
        return (
            isinstance(course_state, dict)
            and course_state.get("insidePoligon") is True
            and course_state.get("predictionValid") is True
            and course_state.get("lifecycle") == "ACTIVE_IN_POLIGON"
        )

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
        elapsed = self._mission_elapsed_before_pause_sec
        if self.mission_started_at is not None:
            elapsed += max(0.0, _time.monotonic() - self.mission_started_at)
        remaining: float | None = None
        if has_limit:
            remaining = max(0.0, self.mission_time_limit_sec - elapsed)
        return {
            "missionElapsedSec": round(elapsed, 1),
            "missionRemainingSeconds": round(remaining, 1) if remaining is not None else None,
            "missionTimeLimitSec": self.mission_time_limit_sec if has_limit else None,
            "missionTimerRunning": self.mission_started_at is not None,
            "missionTimeExpired": bool(has_limit and elapsed >= self.mission_time_limit_sec),
        }

    def expire_stage_timer_if_needed(self) -> bool:
        """Pause Aşama 1 when its authoritative 300-second budget is exhausted."""
        self._require_owner()
        timer = self._mission_timer()
        if (
            self.stage != 1
            or self.mission_flow.status != "ACTIVE"
            or not timer["missionTimeExpired"]
        ):
            return False
        self._pause_mission_timer()
        self.mission_flow.pause("STAGE1_TIME_EXPIRED")
        self._mission_mode_before_pause = self.mode
        self.mode = "safe"
        self._append_event(
            "mission",
            "STAGE1_TIME_EXPIRED",
            "Aşama 1 için 300 saniyelik görev süresi doldu; hareket ve atış kapatıldı.",
            {"missionTimer": self._mission_timer()},
        )
        return True

    def _pause_mission_timer(self) -> None:
        if self.mission_started_at is None:
            return
        self._mission_elapsed_before_pause_sec += max(
            0.0,
            _time.monotonic() - self.mission_started_at,
        )
        self.mission_started_at = None

    def _resume_mission_timer(self) -> None:
        if (
            self.stage == 1
            and self.mission_flow.status == "ACTIVE"
            and self.mission_started_at is None
        ):
            self.mission_started_at = _time.monotonic()

    def _maintenance_state(self) -> dict[str, Any]:
        """Şartname v1.4 bakım bütçesi durumu."""
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
        selected = self._find_track(self.mission_flow.selected_target_id or "")
        course_predictions = []
        for state in self.course_estimator.predicted_states():
            range_m, bearing_deg = self.course_geometry.measurement_for_point(
                state.projected_point
            )
            course_predictions.append(
                {
                    **state.to_dict(),
                    "predictedRangeM": round(range_m, 3),
                    "predictedBearingDeg": round(bearing_deg, 3),
                    "use": "CAMERA_REACQUISITION_ONLY",
                    "fireAuthoritative": False,
                }
            )
        result = {
            "app": "gokkalkan-operator-api",
            "version": 1,
            "mode": self.mode,
            "stage": self.stage,
            "round": self.round,
            "dryRun": self.dry_run,
            "runtimeMode": self.runtime_mode,
            "liveArmEnabled": self.live_arm_enabled,
            "arm": self.arm_controller.snapshot(),
            "tracks": [track.to_dict() for track in self.tracks],
            "sensorFrames": [frame.to_dict() for frame in self.sensor_frames],
            "sensorHealth": self._sensor_health(),
            "safety": self.evaluate_safety(
                "FireIntent",
                selected.to_dict() if selected else None,
                {
                    "stage": self.stage,
                    "round": self.round,
                    "operatorConfirm": True,
                },
            ).to_dict(),
            "commandResults": self.command_results[:8],
            "events": self.events[:20],
            "physicalOutputEnabled": False,
            "telemetry": self.telemetry.metadata(),
            "missionFlow": self.mission_flow.to_dict(),
            "courseGeometry": {
                **self.course_geometry.metadata(),
                "targetSpeedPriorMps": self.target_speed_prior_mps,
                "targetSpeedPriorAuthority": "committee-provisional-not-spec",
            },
            "coursePredictions": course_predictions,
            "turretCalibration": self.turret_calibration.to_dict(),
            "ballisticCompensation": self.ballistic_compensation.to_dict(
                selected.rangeM if selected else None
            ),
            "lidarReading": self.latest_lidar_reading,
            "hardwareHealth": self._hardware_health_snapshot(),
        }
        result.update(self._mission_timer())
        result.update(self._maintenance_state())
        return result

    def _hardware_health_snapshot(self) -> dict[str, Any]:
        try:
            return self.hardware.health_check()
        except Exception as exc:
            return {
                "adapter": type(self.hardware).__name__,
                "busConnected": False,
                "picoReachable": False,
                "encoderOk": False,
                "physicalOutputEnabled": False,
                "healthError": f"{type(exc).__name__}:{exc}",
            }

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
                "Tek sahipli Mission Core kuyruğu, immutable GET /state, SSE /state/stream, izlenebilir komut sonuçları, /telemetry/export ve /replay çalışıyor.",
                "API hata toleransı ve oturum/imza katmanı saha entegrasyonu öncesi eklenecek.",
                "StageRequest, ModeRequest, SensorFrame, FireIntent, CommandResult",
            ),
            self._readiness_item(
                "safety_gate",
                "Safety Gate",
                "ready",
                "Backend",
                "Saf karar/input snapshot, fail-closed sağlık matrisi, sürümlü yasak bölgeler, hold-to-arm ve kontrollü E-Stop reset uygulanıyor.",
                "Gerçek Acil Durdur, interlock ve saha sağlık girişlerini HIL kabulünde doğrula.",
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
                "React panel backend MissionFlow/state stream ile aşama/tur, deadman'li ManualAimCommand, gerçek track önceliği, FireIntent, görev duraklatma, bakım/diagnostik ve kanıt/replay yüzeylerini gösteriyor.",
                "Canlı kamera/perception katmanı ve saha kiosk/ekran düzeni gerçek donanımla ayrıca denenmeli.",
                "Kullanıcı Arayüzü, StageRequest, ManualAimCommand, SensorFrame, TrackState, SafetyState, FireIntent",
            ),
            self._readiness_item(
                "perception_adapter",
                "Perception Adapter",
                "ready" if self.perception_connected else "tbd",
                "Perception",
                "Ayrı process perception bridge, bounded queue ve heartbeat uygulanmış; gerçek kamera/parkur verisi bağlı değil.",
                "Gerçek kamera çıktısını kalibre edilmiş TrackState akışına bağla ve gecikmeyi ölç.",
                "TrackState",
            ),
            self._readiness_item(
                "radar_lidar_adapter",
                "TFA50-L 1D LiDAR",
                "ready" if self.sensor_adapter_connected else "tbd",
                "Sensör",
                "TFA50-L seçimi, UART decoder ve SensorFrame replay sözleşmesi hazır; gerçek sensör bağlı değil.",
                "TFA50-L serial adapterını bağla; güç, timestamp, hizalama ve 5/10/15 m kabulünü doğrula.",
                "SensorFrame",
            ),
            self._readiness_item(
                "hardware_adapter",
                "Hardware Adapter",
                "partial",
                "Backend + Elektronik",
                "USB CDC/COBS/CRC16 taşıması, sequence/ACK, firmware sağlık/encoder geri bildirimi ve host-testli Pico güvenlik çekirdeği hazır.",
                "Pico'yu flashla; gerçek USB disconnect/reconnect, EMI, E-Stop ve imha hattı interlock'unu güvenli yükle HIL'de doğrula.",
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

    def telemetry_export(
        self,
        *,
        state: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        entries = self.telemetry.read_all()
        unsafe_replay = self._unsafe_physical_output_entries(entries)
        published_state = state if state is not None else self.snapshot()
        return {
            "schemaVersion": 1,
            "generatedAt": self._clock(),
            "physicalOutputEnabled": False,
            "unsafeReplayEvidence": unsafe_replay,
            "evidenceWarning": "Replay log içinde physicalOutput=true kaydı var; kanıt güvenli kabul edilmez." if unsafe_replay else "",
            "telemetry": self.telemetry.metadata(),
            "state": published_state,
            "events": list(published_state.get("events", []))[:50],
            "commandResults": list(
                published_state.get("commandResults", [])
            )[:50],
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
        self._require_owner()
        self.mode = "safe"
        self.stage = 3
        self.round = 1
        self.course_estimator.reset()
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
        self._mission_elapsed_before_pause_sec = 0.0
        self.mission_flow = MissionFlow(stage=self.stage, round=self.round)
        self.mission_flow.reset(track.to_dict() for track in self.tracks)
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
            target_gate_ok = self._target_gate_ok_for_stage(target)
            command_payload_ok = payload_stage == self.stage and payload_round == self.round
            mode_ok = (
                self.mission_flow.status == "ACTIVE"
                and (
                    self.mode == "manual"
                    if self.stage == 1
                    else self.mode in ENGAGEMENT_MODES
                )
            )
            command_payload_ok = (
                command_payload_ok
                and bool(payload.get("operatorConfirm"))
                and bool(target)
                and (
                    not target_gate_ok
                    or target.get("trackId")
                    == self.mission_flow.selected_target_id
                )
            )
        elif kind in {"ManualAimCommand", "AutonomousAimCommand"}:
            mode_ok = (
                self.mission_flow.status == "ACTIVE"
                and (
                    self.stage == 1 and self.mode == "manual" and bool(payload.get("deadmanActive"))
                    if kind == "ManualAimCommand"
                    else self.stage in {2, 3} and self.mode == "autonomous"
                )
            )
            command_payload_ok = manual_aim_payload_ok(payload)
        elif kind == "ModeRequest":
            mode_ok = payload.get("requestedMode") in VALID_MODES
        elif kind == "StageRequest":
            command_payload_ok = stage_request_payload_ok(payload)

        current_pan, current_tilt, position_valid = self._current_position()
        target_pan = current_pan
        target_tilt = current_tilt
        if kind in {"ManualAimCommand", "AutonomousAimCommand"}:
            try:
                target_pan += float(payload.get("panDeltaDeg", 0.0))
                target_tilt += float(payload.get("tiltDeltaDeg", 0.0))
            except (TypeError, ValueError):
                position_valid = False
        if kind == "FireIntent" and target:
            try:
                target_pan = float(target.get("bearingDeg", current_pan))
            except (TypeError, ValueError):
                position_valid = False

        action = "motion" if kind in {"ManualAimCommand", "AutonomousAimCommand"} else "fire" if kind == "FireIntent" else "other"
        soft_limits_ok = (
            self._position_within_soft_limits(target_pan, target_tilt)
            if action == "motion"
            else True
        )
        inputs = SafetyInputs(
            action=action,
            runtime_mode=self.runtime_mode,
            estop_latched=self.estop,
            backend_ok=self.backend_connected,
            arm_state=self.arm_controller.state if not dry_run else "ARMED",
            physical_interlock_ok=self.physical_interlock_ok if not dry_run else True,
            pico_heartbeat_ok=self.pico_heartbeat_ok,
            can_ok=self.can_ok,
            encoder_ok=self.encoder_ok,
            camera_ok=self.camera_ok or self.perception_connected,
            track_ok=self.track_ok or self.perception_connected,
            lidar_ok=self.lidar_ok or self.sensor_adapter_connected,
            disk_ok=self.disk_ok,
            mode_ok=mode_ok,
            payload_ok=command_payload_ok,
            target_gate_ok=target_gate_ok,
            position_valid=position_valid,
            target_pan_deg=target_pan,
            target_tilt_deg=target_tilt,
            soft_limits_ok=soft_limits_ok
            and (self.motion_zone_ok if action == "motion" else True)
            and (self.fire_zone_ok if action == "fire" else True),
            motion_zones=self.motion_forbidden_zones,
            fire_zones=self.fire_forbidden_zones,
        )
        try:
            decision = evaluate_pure_safety(inputs)
        except Exception as exc:
            decision = None
            block = "BLOCKED_INVALID_COMMAND"
            explanation = f"Safety Gate değerlendirme hatası; fail-closed: {type(exc).__name__}"
            snapshot: dict[str, Any] = {"error": type(exc).__name__}
        else:
            block = decision.reason_code
            explanation = decision.explanation
            snapshot = decision.input_snapshot

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
            blockReason=block,  # type: ignore[arg-type]
            explanation=explanation,
            decisionSnapshot=snapshot,
        )

    def handle_mode_request(self, payload: dict[str, Any]) -> dict[str, Any]:
        self._require_owner()
        requested = payload.get("requestedMode")
        safety = self.evaluate_safety("ModeRequest", payload=payload)
        accepted = safety.blockReason == "ALLOWED"
        if accepted:
            self.mode = requested  # type: ignore[assignment]
        result = self._command_result("ModeRequest", accepted, safety.blockReason)
        self._append_event("mode", "ModeRequest", result["message"], {"requestedMode": requested, "safety": safety.to_dict(), "result": result})
        return {"result": result, "safety": safety.to_dict(), "state": self.snapshot()}

    def handle_maintenance_request(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Bakım isteği — Şartname v1.4: toplam bütçe 600 sn, istek başı min 30 sn.

        Kabul koşulları:
        - Kalan bütçe >= MAINTENANCE_MIN_REQUEST_SEC
        - Sistem zaten maintenance modunda değil
        - E-Stop aktif değil
        """
        self._require_owner()
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
        if not self.mission_flow.start_maintenance("OPERATOR_MAINTENANCE_START"):
            return {
                "ok": False,
                "blocked": True,
                "reason": "MISSION_TRANSITION_BLOCKED",
                "message": "Görev durumu bakıma geçişe izin vermiyor.",
            }
        self._pause_mission_timer()
        self._maintenance_previous_mode = prev_mode
        self.mode = "maintenance"
        self.disarm("MAINTENANCE_START")
        self._maintenance_started_at = _time.monotonic()
        self._append_event("maintenance", "MAINTENANCE_START",
                           f"Bakım modu başlatıldı (önceki mod: {prev_mode}).",
                           {"prevMode": prev_mode, "maintenanceState": maint})
        return {"ok": True, "blocked": False, "maintenanceState": maint, "state": self.snapshot()}

    def handle_mission_stop(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Controlled operator pause; distinct from the latched physical E-Stop."""

        self._require_owner()
        reason = str(payload.get("reason", "OPERATOR_STOP"))
        previous_mode = self.mode
        accepted = not self.estop and self.mission_flow.pause(reason)
        if accepted:
            self._mission_mode_before_pause = previous_mode
            self._pause_mission_timer()
            self.mode = "blocked"
            self.disarm("MISSION_PAUSED")
        self._append_event(
            "mission",
            "MISSION_STOP",
            "Görev kontrollü olarak duraklatıldı."
            if accepted
            else "Görev duraklatma geçişi reddedildi.",
            {
                "accepted": accepted,
                "reason": reason,
                "previousMode": previous_mode,
                "missionFlow": self.mission_flow.to_dict(),
            },
        )
        return {
            "ok": accepted,
            "accepted": accepted,
            "reason": "ALLOWED" if accepted else "MISSION_TRANSITION_BLOCKED",
            "state": self.snapshot(),
            "physicalOutput": False,
        }

    def handle_mission_resume(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Resume only a controlled PAUSED state; never clear an E-Stop."""

        self._require_owner()
        reason = str(payload.get("reason", "OPERATOR_RESUME"))
        accepted = not self.estop and self.mission_flow.resume(reason)
        if accepted:
            expected = stage_expected_mode(self.stage)
            previous = getattr(self, "_mission_mode_before_pause", expected)
            self.mode = previous if previous in {expected, "engagement"} else expected
            self._resume_mission_timer()
        self._append_event(
            "mission",
            "MISSION_RESUME",
            "Görev kontrollü olarak devam ettirildi."
            if accepted
            else "Görev devam geçişi reddedildi; E-Stop veya durum kilidi sürüyor.",
            {
                "accepted": accepted,
                "reason": reason,
                "missionFlow": self.mission_flow.to_dict(),
            },
        )
        return {
            "ok": accepted,
            "accepted": accepted,
            "reason": "ALLOWED" if accepted else "MISSION_TRANSITION_BLOCKED",
            "state": self.snapshot(),
            "physicalOutput": False,
        }

    def maintenance_end(self) -> dict[str, Any]:
        """Bakım süresini sonlandır; bütçeyi güncelle ve önceki göreve dön.

        En az MAINTENANCE_MIN_REQUEST_SEC kadar süre kayıt edilir.
        """
        self._require_owner()
        if self.mode != "maintenance" or self._maintenance_started_at is None:
            return {"ok": False, "reason": "NOT_IN_MAINTENANCE", "message": "Sistem bakım modunda değil."}
        elapsed = max(MAINTENANCE_MIN_REQUEST_SEC, _time.monotonic() - self._maintenance_started_at)
        self.maintenance_used_sec += elapsed
        self._maintenance_started_at = None
        self.mission_flow.end_maintenance("OPERATOR_MAINTENANCE_END")
        self.mode = "safe"
        self._mission_mode_before_pause = getattr(
            self,
            "_maintenance_previous_mode",
            stage_expected_mode(self.stage),
        )
        self._append_event("maintenance", "MAINTENANCE_END",
                           f"Bakım sona erdi ({elapsed:.1f} sn); görev durumu backend tarafından geri yüklendi.",
                           {"elapsedSec": elapsed, "totalUsedSec": self.maintenance_used_sec,
                            "missionFlow": self.mission_flow.to_dict()})
        return {"ok": True, "elapsedSec": round(elapsed, 1),
                "maintenanceState": self._maintenance_state(), "state": self.snapshot()}

    def handle_stage_request(self, payload: dict[str, Any]) -> dict[str, Any]:
        self._require_owner()
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
            self.course_estimator.reset()
            self.tracks = self._tracks_for_stage(self.stage, self.round)
            self.sensor_frames = self._sensor_frames_for_stage(self.stage, self.round, self.tracks)
            self.mission_flow.start_stage(
                self.stage,
                self.round,
                (track.to_dict() for track in self.tracks),
                reason=str(payload.get("reason", "STAGE_REQUEST")),
            )
            # Şartname: Aşama 1 başlayınca görev timer'ı sıfırla ve başlat
            self._mission_elapsed_before_pause_sec = 0.0
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
        return self._handle_aim(payload, autonomous=False)

    def handle_autonomous_aim(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._handle_aim(payload, autonomous=True)

    def _handle_aim(self, payload: dict[str, Any], *, autonomous: bool) -> dict[str, Any]:
        self._require_owner()
        self.expire_stage_timer_if_needed()
        command_kind = "AutonomousAimCommand" if autonomous else "ManualAimCommand"
        safety = self.evaluate_safety(command_kind, payload=payload)
        accepted = safety.blockReason == "ALLOWED"
        result = self._command_result(command_kind, accepted, safety.blockReason)
        hardware_result = None
        if accepted:
            current_pan, current_tilt, position_ok = self._current_position()
            hardware_payload = dict(payload)
            correction = {
                "active": False,
                "calibrationId": self.turret_calibration.calibration_id,
            }
            if position_ok and self.turret_calibration.active:
                corrected_pan, corrected_tilt = self.turret_calibration.correct_delta(
                    current_pan_deg=current_pan,
                    current_tilt_deg=current_tilt,
                    pan_delta_deg=float(payload.get("panDeltaDeg", 0.0)),
                    tilt_delta_deg=float(payload.get("tiltDeltaDeg", 0.0)),
                )
                hardware_payload["panDeltaDeg"] = corrected_pan
                hardware_payload["tiltDeltaDeg"] = corrected_tilt
                correction = {
                    "active": True,
                    "calibrationId": self.turret_calibration.calibration_id,
                    "requestedPanDeltaDeg": float(payload.get("panDeltaDeg", 0.0)),
                    "requestedTiltDeltaDeg": float(payload.get("tiltDeltaDeg", 0.0)),
                    "adapterPanDeltaDeg": corrected_pan,
                    "adapterTiltDeltaDeg": corrected_tilt,
                }
            hardware_result = self.hardware.execute(
                {
                    "commandId": result["commandId"],
                    "kind": "ManualAimCommand",
                    "payload": hardware_payload,
                }
            )
            hardware_result["turretCalibration"] = correction
            self.telemetry.append("hardware_result", hardware_result)
        self._append_event("command", command_kind, result["message"], {"safety": safety.to_dict(), "result": result, "hardwareResult": hardware_result})
        return {"result": result, "safety": safety.to_dict(), "hardwareResult": hardware_result, "state": self.snapshot()}

    def handle_fire_intent(self, payload: dict[str, Any]) -> dict[str, Any]:
        self._require_owner()
        self.expire_stage_timer_if_needed()
        target = self._find_track(str(payload.get("targetId", "")))
        target_dict = target.to_dict() if target else None
        safety = self.evaluate_safety("FireIntent", target=target_dict, payload=payload)
        accepted = safety.blockReason == "ALLOWED"
        result = self._command_result("FireIntent", accepted, safety.blockReason)
        hardware_result = None
        if accepted:
            hardware_result = self.hardware.execute({"commandId": result["commandId"], "kind": "FireIntent", "target": target_dict, "payload": payload})
            self.telemetry.append("hardware_result", hardware_result)
            hardware_accepted = bool(hardware_result.get("accepted", False))
            hardware_completed = bool(hardware_result.get("completed", False))
            if hardware_accepted and hardware_completed:
                self.mission_flow.record_engagement(str(payload.get("targetId", "")))
            else:
                result["accepted"] = False
                result["message"] = "Hardware FIRE komutunu tamamlamadı."
                result["blockReason"] = str(
                    hardware_result.get("resultCode", "HARDWARE_FIRE_INCOMPLETE")
                )
        self._append_event("fire", "FireIntent", result["message"], {"target": target_dict, "safety": safety.to_dict(), "result": result, "hardwareResult": hardware_result})
        return {"result": result, "safety": safety.to_dict(), "hardwareResult": hardware_result, "state": self.snapshot()}

    def _current_position(self) -> tuple[float, float, bool]:
        if self.dry_run:
            return (0.0, 0.0, True)
        try:
            health = self.hardware.health_check()
            status = health.get("mcuStatus")
            if not isinstance(status, dict):
                return (0.0, 0.0, False)
            pan = float(status["panDeg"])
            tilt = float(status["tiltDeg"])
            encoder_ok = bool(status.get("encoderOk", False))
            return (pan, tilt, encoder_ok and isfinite(pan) and isfinite(tilt))
        except (KeyError, TypeError, ValueError, RuntimeError):
            return (0.0, 0.0, False)

    def _position_within_soft_limits(self, pan: float, tilt: float) -> bool:
        if not isfinite(pan) or not isfinite(tilt):
            return False
        if self.pan_min_deg is not None and pan < self.pan_min_deg:
            return False
        if self.pan_max_deg is not None and pan > self.pan_max_deg:
            return False
        if self.tilt_min_deg is not None and tilt < self.tilt_min_deg:
            return False
        if self.tilt_max_deg is not None and tilt > self.tilt_max_deg:
            return False
        return True

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
            return False

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

    def set_estop(self, active: bool, *, physical: bool = True) -> None:
        """Mission Core owner thread'inde E-Stop durumunu güncelle.

        CAN/GPIO callback'leri bu yöntemi doğrudan çağırmaz; Mission Core
        ``publish_threadsafe`` köprüsüne ``EStopChange`` bırakır.
        """
        self._require_owner()
        prev = self.estop
        if physical:
            self.estop_physical_active = active
        if active:
            if self._maintenance_started_at is not None:
                elapsed = max(
                    MAINTENANCE_MIN_REQUEST_SEC,
                    _time.monotonic() - self._maintenance_started_at,
                )
                self.maintenance_used_sec += elapsed
                self._maintenance_started_at = None
                self._append_event(
                    "maintenance",
                    "MAINTENANCE_INTERRUPTED_ESTOP",
                    "Bakım E-Stop nedeniyle kesildi; kullanılan süre bütçeye işlendi.",
                    {
                        "elapsedSec": elapsed,
                        "totalUsedSec": self.maintenance_used_sec,
                    },
                )
            self.estop = True
            self.estop_reset_required = True
            self._pause_mission_timer()
            self.mission_flow.latch_estop("ESTOP_ACTIVE")
            self.mode = "blocked"
            self.disarm("ESTOP_ACTIVE")
        # Physical release only removes the signal.  The latch stays active
        # until reset_estop verifies Pico SAFE and records an operator identity.
        if self.estop != prev or active:
            self._append_event(
                "safety",
                "ESTOP_CHANGE",
                f"E-Stop {'aktif' if active else 'pasif'} — harici sinyal.",
                {"active": active, "source": "gpio_or_can" if physical else "software"},
            )

    def reset_estop(self, operator_id: str) -> dict[str, Any]:
        self._require_owner()
        allowed = (
            bool(operator_id.strip())
            and not self.estop_physical_active
            and self.pico_safe
            and self.pico_state in {"SAFE", "READY"}
            and self.estop_reset_required
        )
        if allowed:
            self.estop = False
            self.estop_reset_required = False
            self.mission_flow.release_estop("CONTROLLED_ESTOP_RESET")
        self._append_event(
            "safety",
            "ESTOP_RESET",
            "E-Stop mandalı kontrollü olarak temizlendi." if allowed else "E-Stop reset koşulları sağlanmadı.",
            {"accepted": allowed, "operatorId": operator_id},
        )
        return {"ok": allowed, "estop": self.estop, "physicalOutput": False}

    def arm_hold(self, operator_holding: bool, operator_id: str) -> dict[str, Any]:
        self._require_owner()
        previously_armed = self.live_arm_enabled
        if not operator_id.strip():
            self.disarm("MISSING_OPERATOR_ID")
        else:
            self.arm_controller.hold(
                _time.monotonic(),
                operator_holding=operator_holding,
                physical_interlock_ok=self.physical_interlock_ok,
                readiness_ok=self.backend_readiness_ok and self._all_live_health_ok(),
                pico_safe=self.pico_safe,
            )
        self.live_arm_enabled = self.arm_controller.state == "ARMED"
        if self.live_arm_enabled and not previously_armed:
            result = self.hardware.execute(
                {"kind": "SysCmd", "payload": {"arm": True}, "commandId": self._active_command_id}
            )
            self.telemetry.append("hardware_result", result)
            if not result.get("accepted", False):
                self.arm_controller.disarm("PICO_ARM_ACK_FAILED", fault=True)
                self.live_arm_enabled = False
        return {"ok": self.live_arm_enabled, "arm": self.arm_controller.snapshot(), "physicalOutput": False}

    def disarm(self, reason: str = "OPERATOR_DISARM") -> dict[str, Any]:
        self._require_owner()
        was_armed = self.live_arm_enabled
        self.arm_controller.disarm(reason)
        self.live_arm_enabled = False
        if was_armed:
            result = self.hardware.execute(
                {"kind": "SysCmd", "payload": {"arm": False}, "commandId": self._active_command_id}
            )
            self.telemetry.append("hardware_result", result)
        return {"ok": True, "arm": self.arm_controller.snapshot(), "physicalOutput": False}

    def _all_live_health_ok(self) -> bool:
        return all(
            (
                self.pico_heartbeat_ok,
                self.can_ok,
                self.encoder_ok,
                self.camera_ok or self.perception_connected,
                self.track_ok or self.perception_connected,
                self.lidar_ok or self.sensor_adapter_connected,
                self.disk_ok,
            )
        )

    def update_safety_health(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Trusted Mission Core input; intentionally not a public HTTP endpoint."""
        self._require_owner()
        names = (
            "physical_interlock_ok", "backend_readiness_ok", "pico_safe",
            "pico_heartbeat_ok", "can_ok", "encoder_ok", "camera_ok",
            "track_ok", "lidar_ok", "disk_ok",
        )
        for name in names:
            if name in payload:
                setattr(self, name, bool(payload[name]))
        if "pico_state" in payload:
            self.pico_state = str(payload["pico_state"]).upper()
        was_armed = self.live_arm_enabled
        self.arm_controller.tick(
            _time.monotonic(),
            prerequisites_ok=(
                self.physical_interlock_ok
                and self.backend_readiness_ok
                and self.pico_safe
                and self._all_live_health_ok()
            ),
        )
        self.live_arm_enabled = self.arm_controller.state == "ARMED"
        if was_armed and not self.live_arm_enabled:
            result = self.hardware.execute(
                {"kind": "SysCmd", "payload": {"arm": False}, "commandId": self._active_command_id}
            )
            self.telemetry.append("hardware_result", result)
        return {"ok": True, "arm": self.arm_controller.snapshot(), "physicalOutput": False}

    def refresh_hardware_health(self) -> None:
        """Poll the adapter on the owner thread and drop arm on any failure."""

        self._require_owner()
        if self.dry_run:
            return
        try:
            health = self.hardware.health_check()
            status = health.get("mcuStatus", {})
            if not isinstance(status, dict):
                status = {}
            self.can_ok = bool(health.get("busConnected", False))
            self.pico_heartbeat_ok = bool(health.get("picoReachable", False))
            self.encoder_ok = bool(health.get("encoderOk", status.get("encoderOk", False)))
            self.pico_state = str(status.get("state", "")).upper()
            self.pico_safe = (
                self.pico_state in {"SAFE", "READY", "ARMED", "FIRING"}
                and not bool(status.get("estopActive", True))
                and int(status.get("faultCode", status.get("errorCode", 1))) == 0
            )
        except Exception:
            self.can_ok = self.pico_heartbeat_ok = self.encoder_ok = self.pico_safe = False
        try:
            telemetry_parent = self.telemetry.path.parent
            telemetry_parent.mkdir(parents=True, exist_ok=True)
            self.disk_ok = shutil.disk_usage(telemetry_parent).free >= self.disk_min_free_bytes
        except OSError:
            self.disk_ok = False
        if self._last_lidar_update_monotonic is not None:
            self.lidar_ok = (
                _time.monotonic() - self._last_lidar_update_monotonic
                <= self.lidar_stale_seconds
            )
        before = self.live_arm_enabled
        self.arm_controller.tick(
            _time.monotonic(),
            prerequisites_ok=(
                self.physical_interlock_ok
                and self.backend_readiness_ok
                and self.pico_safe
                and self._all_live_health_ok()
            ),
        )
        self.live_arm_enabled = self.arm_controller.state == "ARMED"
        if before and not self.live_arm_enabled:
            self.hardware.execute({"kind": "SysCmd", "payload": {"arm": False}})

    def update_tracks(self, tracks_data: list[dict[str, Any]], source: str = "perception") -> dict[str, Any]:
        """Perception veya sensör adapter'ından gelen canlı track listesini güncelle.

        Endpoint: POST /tracks/update
        Body: {"source": "perception", "tracks": [...]}

        Her track dict en az şu alanları içermelidir:
          trackId, targetType, friendFoe, rangeM, bearingDeg, confidence
        Eksik alanlar güvenli varsayılanlarla doldurulur.
        """
        self._require_owner()
        if not isinstance(tracks_data, list):
            return {"ok": False, "error": "tracks bir liste olmalıdır."}

        now = self._clock()
        source_lower = source.lower()
        default_track_source: Literal["perception", "radar-lidar", "fused"] = (
            "fused"
            if "fused" in source_lower
            else "radar-lidar"
            if "lidar" in source_lower or "radar" in source_lower or "sensor" in source_lower
            else "perception"
        )
        normalized: list[
            tuple[
                str,
                str,
                str,
                float,
                float,
                float,
                Literal["perception", "radar-lidar", "fused"],
                int,
                float | None,
                float | None,
                str | None,
                str | None,
                bool,
                Literal["target", "balloon"],
                bool,
                tuple[float, float, float, float] | None,
                tuple[int, int] | None,
            ]
        ] = []
        for raw in tracks_data:
            if not isinstance(raw, dict):
                continue
            try:
                raw_source = str(raw.get("source", default_track_source))
                track_source: Literal["perception", "radar-lidar", "fused"]
                if raw_source == "radar-lidar":
                    track_source = "radar-lidar"
                elif raw_source == "fused":
                    track_source = "fused"
                elif raw_source == "perception":
                    track_source = "perception"
                else:
                    track_source = default_track_source
                track_id = str(raw.get("trackId", f"LIVE-{now}"))
                range_m = float(raw.get("rangeM", 0.0))
                bearing_deg = float(raw.get("bearingDeg", 0.0))
                confidence = float(raw.get("confidence", 0.5))
                if not all(
                    isfinite(value)
                    for value in (range_m, bearing_deg, confidence)
                ):
                    raise ValueError("rangeM, bearingDeg ve confidence sonlu olmalıdır")
                if range_m < 0 or not 0 <= confidence <= 1:
                    raise ValueError(
                        "rangeM negatif olamaz; confidence 0-1 arasında olmalıdır"
                    )
                object_role_raw = str(raw.get("objectRole", "target"))
                if object_role_raw not in {"target", "balloon"}:
                    raise ValueError("objectRole target veya balloon olmalıdır")
                object_role: Literal["target", "balloon"] = (
                    "balloon" if object_role_raw == "balloon" else "target"
                )
                fire_candidate = (
                    bool(raw.get("fireCandidate", True))
                    and object_role == "target"
                )
                bbox_px = None
                if raw.get("bboxPx") is not None:
                    bbox_values = tuple(float(value) for value in raw["bboxPx"])
                    if len(bbox_values) != 4 or not all(isfinite(value) for value in bbox_values):
                        raise ValueError("bboxPx dört sonlu sayı içermelidir")
                    if bbox_values[2] <= 0 or bbox_values[3] <= 0:
                        raise ValueError("bboxPx genişlik ve yüksekliği pozitif olmalıdır")
                    bbox_px = bbox_values
                frame_size_px = None
                if raw.get("frameSizePx") is not None:
                    frame_values = tuple(int(value) for value in raw["frameSizePx"])
                    if len(frame_values) != 2 or frame_values[0] <= 0 or frame_values[1] <= 0:
                        raise ValueError("frameSizePx iki pozitif tamsayı içermelidir")
                    frame_size_px = frame_values
                normalized.append(
                    (
                        track_id,
                        str(raw.get("targetType", "Bilinmeyen")),
                        str(raw.get("friendFoe", "Bilinmeyen")),
                        range_m,
                        bearing_deg,
                        confidence,
                        track_source,
                        int(raw.get("receiveMonotonicNs", _time.monotonic_ns())),
                        None if raw.get("yawErrorDeg") is None else float(raw["yawErrorDeg"]),
                        None if raw.get("pitchErrorDeg") is None else float(raw["pitchErrorDeg"]),
                        None if raw.get("aimCalibrationId") is None else str(raw["aimCalibrationId"]),
                        None if raw.get("aimCalibrationHash") is None else str(raw["aimCalibrationHash"]),
                        bool(raw.get("aimValid", False))
                        and (
                            self.camera_calibration_hash is None
                            or str(raw.get("aimCalibrationHash", "")) == self.camera_calibration_hash
                        ),
                        object_role,
                        fire_candidate,
                        bbox_px,
                        frame_size_px,
                    )
                )
            except (TypeError, ValueError) as exc:
                return {"ok": False, "error": f"Geçersiz track verisi: {exc}"}

        updated: list[DryRunTrack] = []
        observed_track_ids: set[str] = set()
        for (
            track_id,
            target_type,
            friend_foe,
            range_m,
            bearing_deg,
            confidence,
            track_source,
            receive_monotonic_ns,
            yaw_error_deg,
            pitch_error_deg,
            aim_calibration_id,
            aim_calibration_hash,
            aim_valid,
            object_role,
            fire_candidate,
            bbox_px,
            frame_size_px,
        ) in normalized:
            course_state = self.course_estimator.update(
                track_id,
                range_m,
                bearing_deg,
            )
            observed_track_ids.add(track_id)
            track = DryRunTrack(
                trackId=track_id,
                stage=self.stage,
                round=self.round,
                targetType=target_type,
                friendFoe=friend_foe,
                rangeM=range_m,
                bearingDeg=bearing_deg,
                confidence=confidence,
                source=track_source,
                updatedAt=now,
                receiveMonotonicNs=receive_monotonic_ns,
                yawErrorDeg=yaw_error_deg,
                pitchErrorDeg=pitch_error_deg,
                aimCalibrationId=aim_calibration_id,
                aimCalibrationHash=aim_calibration_hash,
                aimValid=aim_valid,
                courseState=course_state.to_dict(),
                objectRole=object_role,
                fireCandidate=fire_candidate,
                bboxPx=bbox_px,
                frameSizePx=frame_size_px,
            )
            updated.append(track)

        self.course_estimator.mark_absent(observed_track_ids)
        self.tracks = updated
        self.mission_flow.refresh_tracks(track.to_dict() for track in updated)
        self.perception_connected = True
        self.camera_ok = True
        self.track_ok = bool(updated)
        if "lidar" in source_lower or "radar" in source_lower or "sensor" in source_lower or "fused" in source_lower:
            self.sensor_adapter_connected = True
            self.lidar_ok = bool(updated)
            self._last_lidar_update_monotonic = _time.monotonic()
        self._append_event(
            "perception",
            "TRACKS_UPDATE",
            f"{len(updated)} track güncellendi (kaynak={source}).",
            {
                "count": len(updated),
                "source": source,
                "courseStates": [
                    track.courseState for track in updated
                    if track.courseState is not None
                ],
            },
        )
        return {
            "ok": True,
            "count": len(updated),
            "source": source,
            "perceptionConnected": True,
            "courseMappedCount": sum(
                bool(track.courseState and track.courseState["insidePoligon"])
                for track in updated
            ),
        }

    def apply_fused_range(self, decision: FusedRangeDecision) -> dict[str, Any]:
        """Apply only an accepted calibrated fusion result on the owner thread.

        Rejected, stale or ambiguous measurements immediately close LiDAR
        health; an HTTP caller cannot manufacture this trusted reducer input.
        """

        self._require_owner()
        if not decision.accepted or decision.track_id is None or decision.distance_m is None:
            self.lidar_ok = False
            self.sensor_adapter_connected = False
            self.latest_lidar_reading = {
                "status": "REJECTED",
                "distanceM": None,
                "trackId": decision.track_id,
                "timestamp": self._clock(),
                "reason": decision.reason,
                "source": "tfa50-l-1d",
            }
            self._append_event(
                "sensor",
                "LIDAR_RANGE_REJECTED",
                f"LiDAR menzili reddedildi: {decision.reason}",
                decision.to_dict(),
            )
            return {"ok": False, **decision.to_dict()}
        matched = False
        updated: list[DryRunTrack] = []
        for track in self.tracks:
            if track.trackId == decision.track_id:
                course_state = self.course_estimator.update(
                    track.trackId,
                    decision.distance_m,
                    track.bearingDeg,
                )
                updated.append(
                    replace(
                        track,
                        rangeM=decision.distance_m,
                        source="fused",
                        updatedAt=self._clock(),
                        courseState=course_state.to_dict(),
                    )
                )
                matched = True
            else:
                updated.append(track)
        if not matched:
            self.lidar_ok = False
            self.sensor_adapter_connected = False
            return {"ok": False, "reason": "TRACK_NOT_FOUND", **decision.to_dict()}
        self.tracks = updated
        self.mission_flow.refresh_tracks(track.to_dict() for track in updated)
        self.lidar_ok = True
        self.sensor_adapter_connected = True
        self._last_lidar_update_monotonic = _time.monotonic()
        self.latest_lidar_reading = {
            "status": "LIVE_ACCEPTED",
            "distanceM": decision.distance_m,
            "trackId": decision.track_id,
            "timestamp": self._clock(),
            "reason": decision.reason,
            "source": "tfa50-l-1d",
        }
        self._append_event(
            "sensor",
            "LIDAR_RANGE_FUSED",
            f"{decision.track_id} için kararlı TFA50-L menzili kabul edildi.",
            decision.to_dict(),
        )
        return {"ok": True, **decision.to_dict()}

    def set_perception_health(
        self,
        healthy: bool,
        *,
        reason: str,
    ) -> dict[str, Any]:
        """Apply perception health only from the Mission Core reducer."""

        self._require_owner()
        changed = self.perception_connected != healthy
        self.perception_connected = healthy
        self.camera_ok = healthy
        self.track_ok = healthy
        if not healthy:
            self.disarm("PERCEPTION_UNHEALTHY")
        if changed:
            self._append_event(
                "perception",
                "PERCEPTION_HEALTH",
                f"Perception {'sağlıklı' if healthy else 'sağlıksız'}: {reason}",
                {
                    "healthy": healthy,
                    "reason": reason,
                    "engagementClosed": not healthy,
                },
            )
        return {
            "ok": True,
            "healthy": healthy,
            "reason": reason,
            "engagementClosed": not healthy,
            "physicalOutput": False,
        }

    def _find_track(self, track_id: str) -> DryRunTrack | None:
        return next((track for track in self.tracks if track.trackId == track_id), None)

    def _command_result(self, kind: CommandKind, accepted: bool, block: BlockReason) -> dict[str, Any]:
        dry_run = self.dry_run
        command_id = self._active_command_id or f"CMD-{next(self._ids):05d}"
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
