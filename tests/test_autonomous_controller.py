from __future__ import annotations

from gokkalkan_backend.autonomous_controller import AutonomousController
from gokkalkan_backend.mission_core import MissionCore
from gokkalkan_backend.operator_api import DryRunHardwareAdapter, OperatorService
import time


def snapshot(now: int, **track_changes):
    track = {
        "trackId": "T1",
        "confidence": 0.9,
        "receiveMonotonicNs": now,
        "aimValid": True,
        "aimCalibrationHash": "a" * 64,
        "yawErrorDeg": 2.5,
        "pitchErrorDeg": -3.0,
        "friendFoe": "Düşman",
        "targetType": "F16",
        "rangeM": 12.0,
    }
    track.update(track_changes)
    return {
        "mode": "autonomous",
        "stage": 3,
        "round": 1,
        "missionFlow": {"status": "ACTIVE", "selectedTargetId": "T1"},
        "tracks": [track],
        "safety": {"estop": False},
        "hardwareHealth": {"encoderOk": True},
    }


def test_controller_bounds_aim_and_fires_only_after_settle() -> None:
    now = 1_000_000_000
    controller = AutonomousController(settle_ticks=2)
    aim = controller.tick(snapshot(now), now_monotonic_ns=now)
    assert aim is not None and aim.kind == "AutonomousAimCommand"
    assert aim.payload["panDeltaDeg"] == 2.0
    assert aim.payload["tiltDeltaDeg"] == -2.0

    centered = snapshot(now, yawErrorDeg=0.1, pitchErrorDeg=0.1)
    assert controller.tick(centered, now_monotonic_ns=now) is None
    fire = controller.tick(centered, now_monotonic_ns=now + 1)
    assert fire is not None and fire.kind == "FireIntent"
    assert fire.payload["operatorConfirm"] is True


def test_controller_fails_closed_on_stale_uncalibrated_or_unsettled_track() -> None:
    now = 2_000_000_000
    controller = AutonomousController()
    assert controller.tick(snapshot(now - 500_000_000), now_monotonic_ns=now) is None
    assert controller.reason == "TRACK_STALE"
    assert controller.tick(snapshot(now, aimValid=False), now_monotonic_ns=now) is None
    assert controller.reason == "AIM_CALIBRATION_INVALID"
    value = snapshot(now, yawErrorDeg=0.0, pitchErrorDeg=0.0)
    value["hardwareHealth"]["encoderOk"] = False
    assert controller.tick(value, now_monotonic_ns=now) is None
    assert controller.reason == "ENCODER_NOT_SETTLED"


def test_controller_respects_attempt_and_cooldown_limits() -> None:
    now = 3_000_000_000
    controller = AutonomousController(settle_ticks=1, max_attempts=1)
    centered = snapshot(now, yawErrorDeg=0.0, pitchErrorDeg=0.0)
    assert controller.tick(centered, now_monotonic_ns=now).kind == "FireIntent"
    centered["tracks"][0]["receiveMonotonicNs"] = now + 2_000_000_000
    assert controller.tick(centered, now_monotonic_ns=now + 2_000_000_000) is None
    assert controller.reason == "MAX_ATTEMPTS_REACHED"


def test_mission_core_runs_stage2_aim_and_fire_without_operator_commands() -> None:
    hardware = DryRunHardwareAdapter()
    core = MissionCore(OperatorService(hardware=hardware), perception_timeout_sec=2.0)
    core.start()
    try:
        core.submit("StageRequest", {"stage": 2, "round": 1})
        now = time.monotonic_ns()
        core.submit("TracksUpdate", {
            "source": "perception",
            "tracks": [{
                "trackId": "AUTO-T1",
                "targetType": "Bilinmeyen",
                "friendFoe": "Bilinmeyen",
                "rangeM": 10.0,
                "bearingDeg": 0.0,
                "confidence": 0.9,
                "receiveMonotonicNs": now,
                "yawErrorDeg": 0.0,
                "pitchErrorDeg": 0.0,
                "aimCalibrationHash": "a" * 64,
                "aimValid": True,
            }],
        }, source="perception")
        for _ in range(30):
            if any(command.get("command", {}).get("kind") == "FireIntent" for command in hardware.commands):
                break
            time.sleep(0.05)
        assert any(command.get("command", {}).get("kind") == "FireIntent" for command in hardware.commands)
    finally:
        core.stop()
