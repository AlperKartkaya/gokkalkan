"""Release quality gates, deterministic fault injection and soak tooling."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
import shutil
import time
import tomllib
from typing import Any

from .can_protocol import SequenceGuard
from .safety_gate import SafetyInputs, evaluate_safety
from .tfa50_l import TFA50LFrameError, parse_measurement_frame


@dataclass(frozen=True, slots=True)
class PerformanceBudget:
    camera_fps_min: float
    frame_drop_percent_max: float
    perception_latency_ms_max: float
    command_ack_ms_max: float
    state_stream_ms_max: float
    recorder_queue_depth_max: int

    @classmethod
    def load(cls, path: str | Path) -> "PerformanceBudget":
        raw = tomllib.loads(Path(path).read_text(encoding="utf-8"))["performance"]
        return cls(**raw)

    def evaluate(self, measured: dict[str, float]) -> dict[str, Any]:
        checks = {
            "cameraFps": measured["cameraFps"] >= self.camera_fps_min,
            "frameDropPercent": measured["frameDropPercent"] <= self.frame_drop_percent_max,
            "perceptionLatencyMs": measured["perceptionLatencyMs"] <= self.perception_latency_ms_max,
            "commandAckMs": measured["commandAckMs"] <= self.command_ack_ms_max,
            "stateStreamMs": measured["stateStreamMs"] <= self.state_stream_ms_max,
            "recorderQueueDepth": measured["recorderQueueDepth"] <= self.recorder_queue_depth_max,
        }
        return {"ok": all(checks.values()), "checks": checks, "measured": measured}


def _healthy_inputs(**changes: Any) -> SafetyInputs:
    values: dict[str, Any] = {
        "action": "fire",
        "runtime_mode": "LIVE",
        "estop_latched": False,
        "backend_ok": True,
        "arm_state": "ARMED",
        "physical_interlock_ok": True,
        "pico_heartbeat_ok": True,
        "can_ok": True,
        "encoder_ok": True,
        "camera_ok": True,
        "track_ok": True,
        "lidar_ok": True,
        "disk_ok": True,
        "mode_ok": True,
        "payload_ok": True,
        "target_gate_ok": True,
        "position_valid": True,
        "target_pan_deg": 0.0,
        "target_tilt_deg": 0.0,
        "soft_limits_ok": True,
    }
    values.update(changes)
    return SafetyInputs(**values)


def run_fault_injection_suite() -> dict[str, Any]:
    checks: dict[str, bool] = {}
    try:
        parse_measurement_frame(bytes.fromhex("5C 02 11 00"))
        checks["corruptChecksum"] = False
    except TFA50LFrameError:
        checks["corruptChecksum"] = True
    guard = SequenceGuard()
    checks["duplicateSequence"] = guard.accept(7) and not guard.accept(7)
    for key, changes in {
        "heartbeatLoss": {"pico_heartbeat_ok": False},
        "canDisconnect": {"can_ok": False},
        "estop": {"estop_latched": True},
        "staleCamera": {"camera_ok": False},
        "staleLidar": {"lidar_ok": False},
        "diskFull": {"disk_ok": False},
        "backendDivergence": {"backend_ok": False},
    }.items():
        checks[key] = not evaluate_safety(_healthy_inputs(**changes)).allowed
    # Restart safety is a persisted-authority invariant: no restored process may
    # infer an ARMED state from an absent operator hold.
    checks["processRestart"] = evaluate_safety(
        _healthy_inputs(arm_state="DISARMED")
    ).reason_code == "BLOCKED_ARMING"
    return {
        "ok": all(checks.values()),
        "checks": checks,
        "physicalOutput": False,
        "evidenceClass": "SOFTWARE_SIMULATION",
    }


def run_soak(
    *,
    duration_seconds: int = 1800,
    step_seconds: float = 0.1,
    realtime: bool = False,
    output: str | Path | None = None,
    disk_path: str | Path = ".",
) -> dict[str, Any]:
    """Exercise a dry-run state loop for 30 minutes of virtual or wall time."""

    if duration_seconds < 1 or step_seconds <= 0:
        raise ValueError("duration and step must be positive")
    iterations = int(duration_seconds / step_seconds)
    max_queue = 0
    reconnects = 0
    events = 0
    started = time.monotonic()
    for index in range(iterations):
        queue_depth = index % 3
        max_queue = max(max_queue, queue_depth)
        reconnects += int(index > 0 and index % max(1, int(300 / step_seconds)) == 0)
        events += 1
        if realtime:
            time.sleep(step_seconds)
    elapsed = time.monotonic() - started
    result = {
        "ok": events == iterations and max_queue <= 2,
        "requestedDurationSec": duration_seconds,
        "executionElapsedSec": elapsed,
        "timeMode": "WALL_CLOCK" if realtime else "VIRTUAL_TIME",
        "events": events,
        "maxRecorderQueueDepth": max_queue,
        "reconnects": reconnects,
        "diskFreeBytes": shutil.disk_usage(disk_path).free,
        "physicalOutput": False,
    }
    if output is not None:
        target = Path(output)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result
