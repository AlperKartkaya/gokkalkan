"""Dry-run operator API service for Gökkalkan.

This module is intentionally dependency-free. It models the first backend-side
contract behind the real operator panel without driving motors or an imha line.
UI commands are high-level intent only; Safety Gate evaluation happens here
before the dry-run hardware adapter boundary.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from itertools import count
from math import isfinite
from typing import Any, Callable, Literal

from .telemetry_log import JsonlTelemetryStore

Mode = Literal["safe", "manual", "autonomous", "engagement", "blocked", "maintenance"]
Stage = Literal[1, 2, 3]
TargetType = Literal["F16", "Helikopter", "Balistik Füze", "Mini/Micro İHA"]
FriendFoe = Literal["Dost", "Düşman", "Bilinmeyen"]
CommandKind = Literal["ModeRequest", "ManualAimCommand", "FireIntent"]
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
ENGAGEMENT_MODES: set[str] = {"manual", "autonomous", "engagement"}
MAX_MANUAL_AIM_DELTA_DEG = 10.0
MAX_MANUAL_AIM_RATE_LIMIT_DEG_PER_SEC = 30.0
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


class DryRunHardwareAdapter:
    """Hardware adapter boundary that never creates physical output."""

    def __init__(self, clock: Clock = utc_now) -> None:
        self._clock = clock
        self.commands: list[dict[str, Any]] = []

    def execute(self, command: dict[str, Any]) -> dict[str, Any]:
        result = {
            "adapter": "hardware_mock.dry_run",
            "commandId": command["commandId"],
            "kind": command["kind"],
            "accepted": True,
            "completed": True,
            "physicalOutput": False,
            "message": "Dry-run hardware adapter komutu kaydetti; fiziksel çıkış üretilmedi.",
            "createdAt": self._clock(),
        }
        self.commands.append({"command": command, "result": result})
        return result


class OperatorService:
    """Stateful dry-run backend service for the real operator panel."""

    def __init__(self, clock: Clock = utc_now, hardware: DryRunHardwareAdapter | None = None, telemetry: JsonlTelemetryStore | None = None) -> None:
        self._clock = clock
        self._ids = count(1)
        self.mode: Mode = "safe"
        self.stage: Stage = 3
        self.round = 1
        self.estop = False
        self.motion_zone_ok = True
        self.fire_zone_ok = True
        self.backend_connected = True
        self.perception_connected = False
        self.sensor_adapter_connected = False
        self.dry_run = True
        self.live_arm_enabled = False
        self.hardware = hardware or DryRunHardwareAdapter(clock=clock)
        self.telemetry = telemetry or JsonlTelemetryStore(clock=clock)
        self.tracks: list[DryRunTrack] = self._default_tracks()
        self.command_results: list[dict[str, Any]] = []
        self.events: list[dict[str, Any]] = []
        self._append_event("telemetry", "BOOT", "Dry-run backend API hazır; fiziksel çıkış yok.", {})

    def _default_tracks(self) -> list[DryRunTrack]:
        now = self._clock()
        return [
            DryRunTrack("DRY-RUN-F16-01", 3, 1, "F16", "Düşman", 12.4, -18, 0.96, updatedAt=now),
            DryRunTrack("DRY-RUN-HEL-02", 3, 1, "Helikopter", "Dost", 8.1, 4, 0.91, updatedAt=now),
            DryRunTrack("DRY-RUN-UAV-03", 3, 1, "Mini/Micro İHA", "Dost", 4.2, 23, 0.88, updatedAt=now),
        ]

    def snapshot(self) -> dict[str, Any]:
        selected = self.tracks[0] if self.tracks else None
        return {
            "app": "gokkalkan-operator-api",
            "version": 1,
            "mode": self.mode,
            "stage": self.stage,
            "round": self.round,
            "dryRun": self.dry_run,
            "liveArmEnabled": self.live_arm_enabled,
            "tracks": [track.to_dict() for track in self.tracks],
            "safety": self.evaluate_safety("FireIntent", selected.to_dict() if selected else None).to_dict(),
            "commandResults": self.command_results[:8],
            "events": self.events[:20],
            "physicalOutputEnabled": False,
            "telemetry": self.telemetry.metadata(),
        }

    def health(self) -> dict[str, Any]:
        return {
            "ok": True,
            "service": "gokkalkan-operator-api",
            "mode": self.mode,
            "dryRun": self.dry_run,
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
                "GET /state, GET /readiness, POST /mode, POST /manual-aim, POST /fire-intent, /telemetry/export ve /replay çalışıyor.",
                "API hata toleransı ve oturum/imza katmanı saha entegrasyonu öncesi eklenecek.",
                "ModeRequest, ManualAimCommand, FireIntent, CommandResult",
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
                "React panel mod seçimi, manuel yönlendirme, FireIntent, hedef detayı, Safety Gate, hardware mock sonucu, readiness ve kanıt/replay yüzeylerini gösteriyor.",
                "Canlı kamera/perception katmanı ve saha kiosk/ekran düzeni gerçek donanımla ayrıca denenmeli.",
                "Kullanıcı Arayüzü, TrackState, ManualAimCommand",
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
                "Menzil/açı/kalite verisi için adapter sözleşmesi tanımlı; gerçek sensör protokolü seçilmedi.",
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
        return {
            "schemaVersion": 1,
            "generatedAt": self._clock(),
            "physicalOutputEnabled": False,
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
        events = [entry["payload"] for entry in entries if entry.get("recordType") == "event" and isinstance(entry.get("payload"), dict)]
        command_results = [entry["payload"] for entry in entries if entry.get("recordType") == "command_result" and isinstance(entry.get("payload"), dict)]
        hardware_results = [entry["payload"] for entry in entries if entry.get("recordType") == "hardware_result" and isinstance(entry.get("payload"), dict)]
        return {
            "schemaVersion": 1,
            "generatedAt": self._clock(),
            "sourceLogPath": str(self.telemetry.path),
            "physicalOutputEnabled": False,
            "replayOnly": True,
            "entries": entries,
            "events": events,
            "commandResults": command_results,
            "hardwareResults": hardware_results,
        }

    def reset_telemetry(self) -> dict[str, Any]:
        self.mode = "safe"
        self.round = 1
        self.command_results = []
        self.events = []
        self.hardware.commands = []
        self._ids = count(1)
        self.telemetry.reset()
        self._append_event("telemetry", "RESET", "Dry-run telemetri sıfırlandı; fiziksel çıkış yok.", {})
        return {"ok": True, "physicalOutputEnabled": False, "telemetry": self.telemetry.metadata(), "state": self.snapshot()}

    def evaluate_safety(self, kind: CommandKind, target: dict[str, Any] | None = None, payload: dict[str, Any] | None = None) -> SafetyState:
        payload = payload or {}
        dry_run = bool(payload.get("dryRun", self.dry_run))
        live_arm_enabled = self.live_arm_enabled and not dry_run
        target_gate_ok = True
        mode_ok = True
        command_payload_ok = True

        if kind == "FireIntent":
            mode_ok = self.mode in ENGAGEMENT_MODES
            target_gate_ok = bool(
                target
                and target.get("friendFoe") == "Düşman"
                and target_range_gate(str(target.get("targetType")), float(target.get("rangeM", -1)))
            )
        elif kind == "ManualAimCommand":
            mode_ok = self.mode == "manual" and bool(payload.get("deadmanActive"))
            command_payload_ok = manual_aim_payload_ok(payload)
        elif kind == "ModeRequest":
            mode_ok = payload.get("requestedMode") in VALID_MODES

        block: BlockReason = "ALLOWED"
        if self.estop:
            block = "BLOCKED_ESTOP"
        elif not self.backend_connected:
            block = "BLOCKED_BACKEND"
        elif not dry_run and not live_arm_enabled:
            block = "BLOCKED_ARMING"
        elif kind == "ManualAimCommand" and not self.motion_zone_ok:
            block = "BLOCKED_MOTION_ZONE"
        elif kind == "FireIntent" and not self.fire_zone_ok:
            block = "BLOCKED_FIRE_ZONE"
        elif not mode_ok:
            block = "BLOCKED_MODE"
        elif kind == "ManualAimCommand" and not command_payload_ok:
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
        result = self._command_result("ModeRequest", accepted, bool(payload.get("dryRun", self.dry_run)), safety.blockReason)
        self._append_event("mode", "ModeRequest", result["message"], {"requestedMode": requested, "safety": safety.to_dict(), "result": result})
        return {"result": result, "safety": safety.to_dict(), "state": self.snapshot()}

    def handle_manual_aim(self, payload: dict[str, Any]) -> dict[str, Any]:
        safety = self.evaluate_safety("ManualAimCommand", payload=payload)
        accepted = safety.blockReason == "ALLOWED"
        result = self._command_result("ManualAimCommand", accepted, bool(payload.get("dryRun", self.dry_run)), safety.blockReason)
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
        result = self._command_result("FireIntent", accepted, bool(payload.get("dryRun", self.dry_run)), safety.blockReason)
        hardware_result = None
        if accepted:
            hardware_result = self.hardware.execute({"commandId": result["commandId"], "kind": "FireIntent", "target": target_dict, "payload": payload})
            self.telemetry.append("hardware_result", hardware_result)
        self._append_event("fire", "FireIntent", result["message"], {"target": target_dict, "safety": safety.to_dict(), "result": result, "hardwareResult": hardware_result})
        return {"result": result, "safety": safety.to_dict(), "hardwareResult": hardware_result, "state": self.snapshot()}

    def _find_track(self, track_id: str) -> DryRunTrack | None:
        return next((track for track in self.tracks if track.trackId == track_id), None)

    def _command_result(self, kind: CommandKind, accepted: bool, dry_run: bool, block: BlockReason) -> dict[str, Any]:
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
