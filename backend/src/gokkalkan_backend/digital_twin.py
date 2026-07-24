"""Deterministic pre-hardware digital twin and scenario runner.

Values in this module are simulation parameters, not measured motor/sensor
performance.  The twin never constructs a physical hardware adapter.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import hashlib
import json
from math import copysign
from pathlib import Path
from typing import Any, Literal

from .can_protocol import (
    CAN_ID_COMMAND_META,
    CAN_ID_FIRE_CMD_V1,
    CAN_ID_PANTILT_CMD_V1,
    CAN_ID_SYS_CMD_V1,
    KIND_FIRE,
    KIND_PANTILT,
    KIND_SYSTEM,
    SequenceGuard,
    pack_ack,
    unpack_command_meta,
    unpack_fire,
    unpack_pantilt,
    unpack_system,
)
from .operator_api import DryRunHardwareAdapter, OperatorService
from .safety_gate import SafetyDecision
from .telemetry_log import JsonlTelemetryStore


@dataclass(frozen=True, slots=True)
class DynamicsConfig:
    pan_min_deg: float = -75.0
    pan_max_deg: float = 75.0
    tilt_min_deg: float = -10.0
    tilt_max_deg: float = 45.0
    max_velocity_deg_s: float = 35.0
    acceleration_deg_s2: float = 90.0
    backlash_deg: float = 0.18
    encoder_resolution_deg: float = 0.01


@dataclass(slots=True)
class AxisState:
    position_deg: float = 0.0
    target_deg: float = 0.0
    velocity_deg_s: float = 0.0
    direction: int = 0
    backlash_remaining_deg: float = 0.0


class PanTiltDynamics:
    """Bounded acceleration/backlash model with deterministic fixed steps."""

    def __init__(self, config: DynamicsConfig = DynamicsConfig()) -> None:
        self.config = config
        self.pan = AxisState()
        self.tilt = AxisState()
        self.encoder_connected = True
        self.encoder_overflow = False

    def command(self, pan_deg: float, tilt_deg: float) -> bool:
        if not (
            self.config.pan_min_deg <= pan_deg <= self.config.pan_max_deg
            and self.config.tilt_min_deg <= tilt_deg <= self.config.tilt_max_deg
        ):
            return False
        self.pan.target_deg = pan_deg
        self.tilt.target_deg = tilt_deg
        return True

    def step(self, dt_seconds: float) -> dict[str, Any]:
        if not 0 < dt_seconds <= 1.0:
            raise ValueError("digital twin step must be in (0, 1] seconds")
        self._step_axis(self.pan, dt_seconds)
        self._step_axis(self.tilt, dt_seconds)
        return self.feedback()

    def _step_axis(self, axis: AxisState, dt: float) -> None:
        error = axis.target_deg - axis.position_deg
        desired_direction = 0 if abs(error) < 1e-9 else int(copysign(1, error))
        if desired_direction and axis.direction and desired_direction != axis.direction:
            axis.backlash_remaining_deg = self.config.backlash_deg
        axis.direction = desired_direction or axis.direction
        desired_velocity = desired_direction * self.config.max_velocity_deg_s
        delta_v = self.config.acceleration_deg_s2 * dt
        if axis.velocity_deg_s < desired_velocity:
            axis.velocity_deg_s = min(desired_velocity, axis.velocity_deg_s + delta_v)
        elif axis.velocity_deg_s > desired_velocity:
            axis.velocity_deg_s = max(desired_velocity, axis.velocity_deg_s - delta_v)
        travel = axis.velocity_deg_s * dt
        if axis.backlash_remaining_deg:
            consumed = min(abs(travel), axis.backlash_remaining_deg)
            axis.backlash_remaining_deg -= consumed
            travel = copysign(max(0.0, abs(travel) - consumed), travel)
        if abs(travel) >= abs(error):
            axis.position_deg = axis.target_deg
            axis.velocity_deg_s = 0.0
        else:
            axis.position_deg += travel

    def feedback(self) -> dict[str, Any]:
        resolution = self.config.encoder_resolution_deg
        pan = round(self.pan.position_deg / resolution) * resolution
        tilt = round(self.tilt.position_deg / resolution) * resolution
        return {
            "panDeg": pan,
            "tiltDeg": tilt,
            "targetPanDeg": self.pan.target_deg,
            "targetTiltDeg": self.tilt.target_deg,
            "panVelocityDegSec": self.pan.velocity_deg_s,
            "tiltVelocityDegSec": self.tilt.velocity_deg_s,
            "encoderConnected": self.encoder_connected,
            "encoderOverflow": self.encoder_overflow,
            "withinSoftLimits": (
                self.config.pan_min_deg <= pan <= self.config.pan_max_deg
                and self.config.tilt_min_deg <= tilt <= self.config.tilt_max_deg
            ),
            "simulated": True,
            "measuredHardwareValue": False,
        }


@dataclass(frozen=True, slots=True)
class SensorFixture:
    fixture_id: str
    source: Literal["camera", "tfa50-l"]
    timestamp_ms: int
    payload: dict[str, Any]
    fault: str | None = None


class SensorFixtureReplay:
    """Camera/TFA50-L fixtures including deterministic fault cases."""

    @staticmethod
    def standard() -> tuple[SensorFixture, ...]:
        return (
            SensorFixture("CAM-TRACK-1", "camera", 0, {"trackId": "T1", "bearingDeg": -8.0, "confidence": 0.91}),
            SensorFixture("LID-RANGE-1", "tfa50-l", 10, {"distanceM": 10.0, "detected": True}),
            SensorFixture("LID-NO-DETECTION", "tfa50-l", 20, {"distanceM": None, "detected": False}, "NO_DETECTION"),
            SensorFixture("LID-BAD-UART", "tfa50-l", 30, {"rawHex": "59 59 00"}, "CORRUPT_UART"),
            SensorFixture("CAM-STALE", "camera", 900, {"trackId": "T1"}, "STALE"),
            SensorFixture("LID-DROPOUT", "tfa50-l", 1200, {}, "DROPOUT"),
            SensorFixture("CAM-CLOCK-SKEW", "camera", -250, {"trackId": "T2"}, "CLOCK_SKEW"),
        )

    @classmethod
    def write(cls, path: str | Path) -> Path:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            "\n".join(json.dumps(asdict(item), sort_keys=True) for item in cls.standard()) + "\n",
            encoding="utf-8",
        )
        return target


@dataclass(slots=True)
class SafeFireMock:
    events: list[dict[str, Any]] = field(default_factory=list)
    lamp_on: bool = False

    def request(self, command_id: str, decision: SafetyDecision) -> dict[str, Any]:
        accepted = decision.allowed
        self.lamp_on = accepted
        event = {
            "commandId": command_id,
            "accepted": accepted,
            "reasonCode": decision.reason_code,
            "output": "SIMULATED_LAMP" if accepted else "NONE",
            "physicalOutput": False,
        }
        self.events.append(event)
        return event


@dataclass(slots=True)
class FaultInjection:
    ack_delay_ms: int = 0
    drop_next_ack: bool = False
    corrupt_next_ack: bool = False
    estop_active: bool = False
    heartbeat_lost: bool = False
    encoder_fault: bool = False


class McuDigitalTwin:
    """CAN v1 MCU model with state, ACK/NACK, delay and fault injection."""

    def __init__(self) -> None:
        self.state = "SAFE"
        self.dynamics = PanTiltDynamics()
        self.faults = FaultInjection()
        self._meta: dict[str, int] | None = None
        self._guard = SequenceGuard()
        self._clock_ms = 0
        self._scheduled: list[tuple[int, bytes]] = []

    def heartbeat(self) -> None:
        if not self.faults.heartbeat_lost and self.state == "SAFE":
            self.state = "READY"

    def authorize_fire(self, command_tag: int) -> None:
        """Compatibility hook for tests that model a backend Safety Gate token.

        The wire protocol's correlated META frame is the authorization boundary;
        the independent :class:`SafeFireMock` verifies the SafetyDecision itself.
        """

    def inject(self, **faults: Any) -> None:
        for name, value in faults.items():
            if not hasattr(self.faults, name):
                raise ValueError(f"unknown fault injection: {name}")
            setattr(self.faults, name, value)
        if self.faults.estop_active or self.faults.encoder_fault or self.faults.heartbeat_lost:
            self.state = "FAULT"

    def receive(self, can_id: int, frame: bytes) -> None:
        if can_id == CAN_ID_COMMAND_META:
            self._meta = unpack_command_meta(frame)
            return
        meta = self._meta
        self._meta = None
        if meta is None:
            return
        sequence = meta["sequence"]
        if not self._guard.accept(sequence):
            self._schedule_ack(meta, 3)
            return
        result = 0
        if self.state == "FAULT":
            result = 1
        elif can_id == CAN_ID_SYS_CMD_V1 and meta["kind"] == KIND_SYSTEM:
            command = unpack_system(frame)
            if command is None or command["sequence"] != sequence:
                result = 2
            elif command["operation"] == 1 and self.state == "READY":
                self.state = "ARMED"
            elif command["operation"] in {0, 2}:
                self.state = "SAFE"
            elif command["operation"] == 3 and not self.faults.estop_active:
                self.state = "SAFE"
            else:
                result = 1
        elif can_id == CAN_ID_PANTILT_CMD_V1 and meta["kind"] == KIND_PANTILT:
            command = unpack_pantilt(frame)
            if command is None or command["sequence"] != sequence:
                result = 2
            elif self.state != "ARMED" or not self.dynamics.command(
                command["panCentideg"] / 100.0,
                command["tiltCentideg"] / 100.0,
            ):
                result = 1
        elif can_id == CAN_ID_FIRE_CMD_V1 and meta["kind"] == KIND_FIRE:
            command = unpack_fire(frame)
            if command is None or command["sequence"] != sequence:
                result = 2
            elif self.state != "ARMED":
                result = 1
            else:
                self.state = "FIRING"
        else:
            result = 4
        self._schedule_ack(meta, result)

    def _schedule_ack(self, meta: dict[str, int], result: int) -> None:
        if self.faults.drop_next_ack:
            self.faults.drop_next_ack = False
            return
        state_code = {"BOOT": 0, "SAFE": 1, "READY": 2, "ARMED": 3, "FIRING": 4, "FAULT": 5}[self.state]
        frame = pack_ack(meta["sequence"], meta["commandTag"], result, state_code)
        if self.faults.corrupt_next_ack:
            damaged = bytearray(frame)
            damaged[4] ^= 0x01
            frame = bytes(damaged)
            self.faults.corrupt_next_ack = False
        self._scheduled.append((self._clock_ms + self.faults.ack_delay_ms, frame))

    def step(self, milliseconds: int) -> list[bytes]:
        if milliseconds < 0:
            raise ValueError("milliseconds must not be negative")
        self._clock_ms += milliseconds
        if milliseconds:
            self.dynamics.step(min(1.0, milliseconds / 1000.0))
        ready = [frame for due, frame in self._scheduled if due <= self._clock_ms]
        self._scheduled = [(due, frame) for due, frame in self._scheduled if due > self._clock_ms]
        return ready


SCENARIOS = (
    "stage1-manual",
    "stage2-autonomous",
    "stage3-friend-foe",
    "estop",
    "connection-loss",
    "wrong-target",
)


def run_scenario(name: str, output: str | Path | None = None) -> dict[str, Any]:
    """Run a named scenario with fixed inputs and return a reproducible digest."""

    if name not in SCENARIOS:
        raise ValueError(f"unknown scenario: {name}")
    target = Path(output) if output else Path("telemetry_data/scenarios") / f"{name}.jsonl"
    telemetry = JsonlTelemetryStore(target, clock=lambda: "2026-07-25T00:00:00Z")
    telemetry.reset()
    service = OperatorService(
        clock=lambda: "2026-07-25T00:00:00Z",
        hardware=DryRunHardwareAdapter(clock=lambda: "2026-07-25T00:00:00Z"),
        telemetry=telemetry,
    )
    actions: list[dict[str, Any]] = []
    if name == "stage1-manual":
        actions.append(service.handle_stage_request({"stage": 1, "round": 1}))
        actions.append(service.handle_manual_aim({"panDeltaDeg": 5, "tiltDeltaDeg": 2, "rateLimitDegPerSec": 10, "deadmanActive": True}))
    elif name == "stage2-autonomous":
        actions.append(service.handle_stage_request({"stage": 2, "round": 1}))
        target_id = service.snapshot()["tracks"][0]["trackId"]
        actions.append(
            service.handle_fire_intent(
                {"targetId": target_id, "stage": 2, "round": 1}
            )
        )
    else:
        service.handle_stage_request({"stage": 3, "round": 1})
        if name == "stage3-friend-foe":
            service.update_tracks(
                [
                    {
                        "trackId": "FRIEND",
                        "targetType": "F16",
                        "friendFoe": "Dost",
                        "rangeM": 12,
                        "bearingDeg": 0,
                        "confidence": 0.95,
                    },
                    {
                        "trackId": "ENEMY",
                        "targetType": "F16",
                        "friendFoe": "Düşman",
                        "rangeM": 12,
                        "bearingDeg": 2,
                        "confidence": 0.95,
                    },
                ]
            )
            actions.append(
                service.handle_fire_intent(
                    {"targetId": "FRIEND", "stage": 3, "round": 1}
                )
            )
            actions.append(
                service.handle_fire_intent(
                    {"targetId": "ENEMY", "stage": 3, "round": 1}
                )
            )
        elif name == "wrong-target":
            actions.append(
                service.handle_fire_intent(
                    {"targetId": "UNKNOWN", "stage": 3, "round": 1}
                )
            )
        elif name == "estop":
            service.set_estop(True)
            actions.append(
                service.handle_fire_intent(
                    {"targetId": "S3-R1-T1", "stage": 3, "round": 1}
                )
            )
        elif name == "connection-loss":
            service.backend_connected = False
            actions.append(
                service.handle_fire_intent(
                    {"targetId": "S3-R1-T1", "stage": 3, "round": 1}
                )
            )
    normalized = [
        {
            "accepted": bool(action.get("result", action).get("accepted", action.get("ok", False))),
            "reason": action.get("result", {}).get("safetyBlockReason"),
        }
        for action in actions
    ]
    digest = hashlib.sha256(json.dumps(normalized, sort_keys=True).encode()).hexdigest()
    return {
        "schemaVersion": 1,
        "scenario": name,
        "actions": normalized,
        "deterministicDigest": digest,
        "telemetryPath": str(target),
        "physicalOutput": False,
    }
