"""Pure fail-closed autonomous engagement state machine."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True, slots=True)
class AutonomousAction:
    kind: str
    payload: dict[str, Any]
    correlation_id: str


class AutonomousController:
    def __init__(
        self,
        *,
        aim_tolerance_deg: float = 0.5,
        max_step_deg: float = 2.0,
        min_confidence: float = 0.4,
        max_track_age_ms: float = 300.0,
        settle_ticks: int = 3,
        max_attempts: int = 2,
        cooldown_ms: float = 1500.0,
    ) -> None:
        self.aim_tolerance_deg = aim_tolerance_deg
        self.max_step_deg = max_step_deg
        self.min_confidence = min_confidence
        self.max_track_age_ns = int(max_track_age_ms * 1_000_000)
        self.settle_ticks = settle_ticks
        self.max_attempts = max_attempts
        self.cooldown_ns = int(cooldown_ms * 1_000_000)
        self.state = "IDLE"
        self.reason = "BOOT"
        self._settled = 0
        self._attempts: dict[str, int] = {}
        self._last_fire_ns: dict[str, int] = {}
        self._correlation = 0

    def reset(self, reason: str) -> None:
        self.state = "HOLD"
        self.reason = reason
        self._settled = 0

    def snapshot(self) -> dict[str, Any]:
        return {"state": self.state, "reason": self.reason, "attempts": dict(self._attempts)}

    def tick(self, snapshot: Mapping[str, Any], *, now_monotonic_ns: int) -> AutonomousAction | None:
        if snapshot.get("mode") != "autonomous" or int(snapshot.get("stage", 0)) not in {2, 3}:
            self.reset("AUTONOMOUS_MODE_INACTIVE")
            return None
        if snapshot.get("missionFlow", {}).get("status") != "ACTIVE":
            self.reset("MISSION_NOT_ACTIVE")
            return None
        if snapshot.get("safety", {}).get("estop"):
            self.reset("ESTOP_ACTIVE")
            return None
        selected = snapshot.get("missionFlow", {}).get("selectedTargetId")
        track = next((item for item in snapshot.get("tracks", []) if item.get("trackId") == selected), None)
        if not track:
            self.reset("NO_SELECTED_TARGET")
            return None
        track_id = str(track["trackId"])
        age = now_monotonic_ns - int(track.get("receiveMonotonicNs", 0))
        if age < 0 or age > self.max_track_age_ns:
            self.reset("TRACK_STALE")
            return None
        if float(track.get("confidence", 0.0)) < self.min_confidence:
            self.reset("TRACK_CONFIDENCE_LOW")
            return None
        if not track.get("aimValid") or not track.get("aimCalibrationHash"):
            self.reset("AIM_CALIBRATION_INVALID")
            return None
        yaw = float(track.get("yawErrorDeg") or 0.0)
        pitch = float(track.get("pitchErrorDeg") or 0.0)
        if abs(yaw) > self.aim_tolerance_deg or abs(pitch) > self.aim_tolerance_deg:
            self.state = "AIMING"
            self.reason = "AIM_ERROR"
            self._settled = 0
            return self._action("AutonomousAimCommand", {
                "panDeltaDeg": max(-self.max_step_deg, min(self.max_step_deg, yaw)),
                "tiltDeltaDeg": max(-self.max_step_deg, min(self.max_step_deg, pitch)),
                "rateLimitDegPerSec": 10.0,
                "deadmanActive": False,
                "targetId": track_id,
            })
        hardware = snapshot.get("hardwareHealth", {})
        if not hardware.get("encoderOk", False):
            self.reset("ENCODER_NOT_SETTLED")
            return None
        self._settled += 1
        if self._settled < self.settle_ticks:
            self.state = "SETTLING"
            self.reason = "WAIT_ENCODER_SETTLE"
            return None
        attempts = self._attempts.get(track_id, 0)
        last_fire = self._last_fire_ns.get(track_id, 0)
        if attempts >= self.max_attempts:
            self.reset("MAX_ATTEMPTS_REACHED")
            return None
        if last_fire and now_monotonic_ns - last_fire < self.cooldown_ns:
            self.state = "HOLD"
            self.reason = "FIRE_COOLDOWN"
            return None
        self._attempts[track_id] = attempts + 1
        self._last_fire_ns[track_id] = now_monotonic_ns
        self.state = "FIRE_AUTHORIZATION"
        self.reason = "AIM_AND_SETTLE_VALID"
        return self._action("FireIntent", {
            "targetId": track_id,
            "stage": int(snapshot["stage"]),
            "round": int(snapshot["round"]),
            "operatorConfirm": True,
            "autonomous": True,
        })

    def _action(self, kind: str, payload: dict[str, Any]) -> AutonomousAction:
        self._correlation += 1
        return AutonomousAction(kind, payload, f"AUTO-{self._correlation:08d}")
