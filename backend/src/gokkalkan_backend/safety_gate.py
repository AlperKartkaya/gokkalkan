"""Pure, fail-closed safety decisions and LIVE arming primitives.

This module deliberately contains no I/O.  Every motion/fire request is reduced
to an immutable input snapshot so the decision can be logged and replayed.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from math import isfinite
from typing import Literal

SafetyAction = Literal["motion", "fire", "other"]
ArmState = Literal["DISARMED", "HOLDING", "ARMED", "FAULT"]


@dataclass(frozen=True, slots=True)
class ForbiddenZone:
    name: str
    pan_min_deg: float
    pan_max_deg: float
    tilt_min_deg: float
    tilt_max_deg: float

    def valid(self) -> bool:
        values = (
            self.pan_min_deg,
            self.pan_max_deg,
            self.tilt_min_deg,
            self.tilt_max_deg,
        )
        return all(isfinite(value) for value in values) and (
            self.pan_min_deg < self.pan_max_deg
            and self.tilt_min_deg < self.tilt_max_deg
        )

    def contains(self, pan_deg: float, tilt_deg: float) -> bool:
        """Return True on the boundary too: forbidden zones are inclusive."""

        return (
            self.pan_min_deg <= pan_deg <= self.pan_max_deg
            and self.tilt_min_deg <= tilt_deg <= self.tilt_max_deg
        )


@dataclass(frozen=True, slots=True)
class SafetyInputs:
    action: SafetyAction
    runtime_mode: str
    estop_latched: bool
    backend_ok: bool
    arm_state: ArmState
    physical_interlock_ok: bool
    pico_heartbeat_ok: bool
    can_ok: bool
    encoder_ok: bool
    camera_ok: bool
    track_ok: bool
    lidar_ok: bool
    disk_ok: bool
    mode_ok: bool
    payload_ok: bool
    target_gate_ok: bool
    position_valid: bool
    target_pan_deg: float
    target_tilt_deg: float
    soft_limits_ok: bool
    motion_zones: tuple[ForbiddenZone, ...] = ()
    fire_zones: tuple[ForbiddenZone, ...] = ()


@dataclass(frozen=True, slots=True)
class SafetyDecision:
    allowed: bool
    reason_code: str
    explanation: str
    input_snapshot: dict[str, object]

    def to_dict(self) -> dict[str, object]:
        return {
            "allowed": self.allowed,
            "reasonCode": self.reason_code,
            "explanation": self.explanation,
            "inputSnapshot": self.input_snapshot,
        }


def _deny(inputs: SafetyInputs, code: str, explanation: str) -> SafetyDecision:
    return SafetyDecision(False, code, explanation, asdict(inputs))


def evaluate_safety(inputs: SafetyInputs) -> SafetyDecision:
    """Evaluate one request without mutation or hardware access.

    LIVE requires every declared health input.  Invalid positions, invalid zone
    geometry and exceptions while *building* this snapshot are expected to be
    represented as ``position_valid=False`` and therefore fail closed.
    """

    if inputs.estop_latched:
        return _deny(inputs, "BLOCKED_ESTOP", "Acil Durdur mandalı aktif.")
    if not inputs.backend_ok:
        return _deny(inputs, "BLOCKED_BACKEND", "Backend sağlığı doğrulanamadı.")
    if inputs.runtime_mode == "LIVE":
        if inputs.arm_state != "ARMED" or not inputs.physical_interlock_ok:
            return _deny(inputs, "BLOCKED_ARMING", "Canlı arm zinciri tamamlanmadı.")
    if not inputs.position_valid or not inputs.soft_limits_ok:
        return _deny(
            inputs,
            "BLOCKED_MOTION_ZONE",
            "Konum bilinmiyor veya yazılım hareket sınırı dışında.",
        )
    zones = (
        inputs.motion_zones
        if inputs.action == "motion"
        else inputs.fire_zones
        if inputs.action == "fire"
        else ()
    )
    if any(not zone.valid() for zone in zones):
        return _deny(inputs, "BLOCKED_ZONE_CONFIG", "Yasak bölge geometrisi geçersiz.")
    if any(zone.contains(inputs.target_pan_deg, inputs.target_tilt_deg) for zone in zones):
        code = "BLOCKED_MOTION_ZONE" if inputs.action == "motion" else "BLOCKED_FIRE_ZONE"
        return _deny(inputs, code, "Hedef konumu sürümlü yasak bölge içinde.")
    if not inputs.payload_ok:
        return _deny(inputs, "BLOCKED_INVALID_COMMAND", "Komut alanları geçersiz.")
    if not inputs.mode_ok:
        return _deny(inputs, "BLOCKED_MODE", "Aktif mod komuta izin vermiyor.")
    if inputs.action == "fire" and not inputs.target_gate_ok:
        return _deny(inputs, "BLOCKED_TARGET_GATE", "Hedef/menzil kapısı uygun değil.")

    if inputs.runtime_mode == "LIVE":
        health = {
            "pico": inputs.pico_heartbeat_ok,
            "can": inputs.can_ok,
            "encoder": inputs.encoder_ok,
            "camera": inputs.camera_ok,
            "track": inputs.track_ok,
            "lidar": inputs.lidar_ok,
            "disk": inputs.disk_ok,
        }
        failed = [name for name, ok in health.items() if not ok]
        if failed:
            return _deny(
                inputs,
                "BLOCKED_SENSOR",
                "Canlı sağlık girdisi uygun değil: " + ", ".join(failed),
            )
    return SafetyDecision(True, "ALLOWED", "Safety Gate komuta izin verdi.", asdict(inputs))


@dataclass(slots=True)
class LiveArmController:
    """Short-lived operator-hold arming state machine.

    Calling ``tick`` on every owner-loop iteration makes a lost keepalive or
    health signal drop ARMED automatically.
    """

    hold_seconds: float = 2.0
    timeout_seconds: float = 3.0
    state: ArmState = "DISARMED"
    hold_started_at: float | None = None
    last_keepalive_at: float | None = None
    reason: str = "BOOT_DISARMED"

    def hold(
        self,
        now: float,
        *,
        operator_holding: bool,
        physical_interlock_ok: bool,
        readiness_ok: bool,
        pico_safe: bool,
    ) -> ArmState:
        prerequisites = physical_interlock_ok and readiness_ok and pico_safe
        if not prerequisites:
            return self.disarm("ARM_PREREQUISITE_LOST", fault=True)
        if not operator_holding:
            return self.disarm("OPERATOR_HOLD_RELEASED")
        if self.state not in {"HOLDING", "ARMED"}:
            self.state = "HOLDING"
            self.hold_started_at = now
            self.reason = "OPERATOR_HOLDING"
        self.last_keepalive_at = now
        if self.hold_started_at is not None and now - self.hold_started_at >= self.hold_seconds:
            self.state = "ARMED"
            self.reason = "ARMED"
        return self.state

    def tick(self, now: float, *, prerequisites_ok: bool) -> ArmState:
        if self.state in {"HOLDING", "ARMED"} and not prerequisites_ok:
            return self.disarm("ARM_PREREQUISITE_LOST", fault=True)
        if (
            self.state in {"HOLDING", "ARMED"}
            and self.last_keepalive_at is not None
            and now - self.last_keepalive_at > self.timeout_seconds
        ):
            return self.disarm("ARM_KEEPALIVE_TIMEOUT")
        return self.state

    def disarm(self, reason: str = "OPERATOR_DISARM", *, fault: bool = False) -> ArmState:
        self.state = "FAULT" if fault else "DISARMED"
        self.hold_started_at = None
        self.last_keepalive_at = None
        self.reason = reason
        return self.state

    def snapshot(self) -> dict[str, object]:
        return {
            "state": self.state,
            "reason": self.reason,
            "holdSeconds": self.hold_seconds,
            "timeoutSeconds": self.timeout_seconds,
            "lastKeepaliveMonotonic": self.last_keepalive_at,
        }
