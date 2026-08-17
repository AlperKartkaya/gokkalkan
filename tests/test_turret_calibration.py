import json

import pytest

from gokkalkan_backend.operator_api import OperatorService
from gokkalkan_backend.hardware_adapter import HardwareAdapterBase
from gokkalkan_backend.turret_calibration import (
    AxisCalibration,
    TurretCalibration,
    fit_axis,
    solve_calibration_file,
)


def test_axis_fit_recovers_gain_offset_and_inverse_command() -> None:
    axis = fit_axis([(-10, -9), (0, -2), (10, 5), (20, 12)])
    assert axis.gain == pytest.approx(0.7)
    assert axis.offset_deg == pytest.approx(-2)
    assert axis.command_for_physical(5) == pytest.approx(10)


def test_unverified_calibration_never_changes_commands() -> None:
    calibration = TurretCalibration.identity()
    assert calibration.correct_delta(
        current_pan_deg=8,
        current_tilt_deg=4,
        pan_delta_deg=2,
        tilt_delta_deg=-1,
    ) == (2, -1)


def test_active_calibration_corrects_adapter_delta_from_encoder_position() -> None:
    calibration = TurretCalibration(
        calibration_id="FIELD-1",
        status="ACTIVE",
        calibrated_at="2026-07-26T10:00:00Z",
        pan=AxisCalibration(gain=1.0, offset_deg=-3.0, sample_count=4),
        tilt=AxisCalibration(gain=0.8, offset_deg=0.0, sample_count=4),
    )
    pan_delta, tilt_delta = calibration.correct_delta(
        current_pan_deg=10,
        current_tilt_deg=5,
        pan_delta_deg=10,
        tilt_delta_deg=5,
    )
    assert pan_delta == pytest.approx(13)
    assert tilt_delta == pytest.approx(7.5)


def test_calibration_file_requires_explicit_activation(tmp_path) -> None:
    observations = tmp_path / "observations.json"
    observations.write_text(
        json.dumps(
            {
                "calibrationId": "FIELD-2",
                "pan": [
                    {"commandedDeg": -10, "measuredDeg": -8},
                    {"commandedDeg": 0, "measuredDeg": 0},
                    {"commandedDeg": 10, "measuredDeg": 8},
                ],
                "tilt": [
                    {"commandedDeg": 0, "measuredDeg": 0},
                    {"commandedDeg": 10, "measuredDeg": 9},
                    {"commandedDeg": 20, "measuredDeg": 18},
                ],
            }
        ),
        encoding="utf-8",
    )
    output = tmp_path / "turret.toml"
    solved = solve_calibration_file(observations, output)
    assert solved.status == "CALCULATED_NOT_ACTIVE"
    assert not TurretCalibration.from_toml(output).active


def test_operator_snapshot_exposes_calibration_state() -> None:
    snapshot = OperatorService().snapshot()
    assert snapshot["turretCalibration"]["status"] == "UNVERIFIED"
    assert snapshot["turretCalibration"]["active"] is False


def test_operator_applies_active_correction_only_after_safety_accepts() -> None:
    class CaptureHardware(HardwareAdapterBase):
        def __init__(self) -> None:
            self.command = None

        def execute(self, command):
            self.command = command
            return {
                "accepted": True,
                "completed": True,
                "physicalOutput": False,
                "adapter": "capture",
                "commandId": command["commandId"],
                "kind": command["kind"],
                "message": "captured",
                "createdAt": "2026-07-26T10:00:00Z",
            }

        def health_check(self):
            return {"dryRun": True}

        def close(self):
            return None

    hardware = CaptureHardware()
    calibration = TurretCalibration(
        calibration_id="FIELD-3",
        status="ACTIVE",
        calibrated_at="2026-07-26T10:00:00Z",
        pan=AxisCalibration(gain=1, offset_deg=-3, sample_count=4),
        tilt=AxisCalibration(gain=1, offset_deg=0, sample_count=4),
    )
    service = OperatorService(hardware=hardware, turret_calibration=calibration)
    stage = service.handle_stage_request({"stage": 1, "round": 1, "reason": "calibration-test"})
    assert stage["result"]["accepted"] is True
    response = service.handle_manual_aim(
        {
            "panDeltaDeg": 10,
            "tiltDeltaDeg": 0,
            "rateLimitDegPerSec": 12,
            "deadmanActive": True,
        }
    )
    assert response["result"]["accepted"] is True
    assert hardware.command["payload"]["panDeltaDeg"] == pytest.approx(13)
    assert response["hardwareResult"]["turretCalibration"]["active"] is True
