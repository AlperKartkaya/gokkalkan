from __future__ import annotations

import json
from pathlib import Path

import pytest

from gokkalkan_backend.hil_runner import HIL_SCENARIOS, HilProfile, run_hil_plan
from gokkalkan_backend.operator_api import BLOCK_COPY
from gokkalkan_backend.release_gate import (
    build_release_manifest,
    verify_release_manifest,
)
from gokkalkan_backend.telemetry_session import SessionTelemetryStore, verify_session

pytestmark = pytest.mark.safety


def profile() -> HilProfile:
    return HilProfile(
        profile_id="TEST-HIL",
        can_channel="vcan0",
        safe_load="lamp",
        allows_destructive_output=False,
        config_hash="config-hash",
        calibration_hash="calibration-hash",
    )


def test_hil_report_keeps_unrun_physical_scenarios_open(tmp_path: Path) -> None:
    report = run_hil_plan(profile(), output=tmp_path / "hil.json")
    assert report["softwareHarness"]["ok"] is True
    assert report["physicalGatePassed"] is False
    assert {item["status"] for item in report["scenarios"]} == {"NOT_RUN_PHYSICAL"}
    assert report["allowsDestructiveOutput"] is False


def test_hil_rejects_destructive_load_and_accepts_complete_observations(
    tmp_path: Path,
) -> None:
    unsafe = HilProfile("unsafe", "can0", "real-output", True, "c", "k")
    with pytest.raises(ValueError):
        run_hil_plan(unsafe, output=tmp_path / "unsafe.json")
    report = run_hil_plan(
        profile(),
        output=tmp_path / "complete.json",
        physical_evidence={name: True for name in HIL_SCENARIOS},
    )
    assert report["physicalGatePassed"] is True


def test_release_manifest_hashes_components_and_requires_all_three_gates(
    tmp_path: Path,
) -> None:
    sensor = tmp_path / "sensor.json"
    hil = tmp_path / "hil.json"
    sensor.write_text('{"physicalGatePassed": true}', encoding="utf-8")
    hil.write_text('{"physicalGatePassed": false}', encoding="utf-8")
    manifest = build_release_manifest(
        root=".",
        version="0.3.0-rc1",
        component_paths=["pyproject.toml", "config/runtime/hil.toml"],
        output=tmp_path / "release.json",
        software_gate=True,
        sensor_evidence=sensor,
        hil_evidence=hil,
    )
    assert manifest["gates"] == {"software": True, "sensor": True, "hil": False}
    assert manifest["readyForPhysicalManufacturingClaim"] is False
    assert all(len(item["sha256"]) == 64 for item in manifest["components"])
    assert verify_release_manifest(tmp_path / "release.json")["ok"] is True


def test_every_backend_block_reason_has_operator_panel_copy() -> None:
    source = Path("frontend/src/operatorContracts.ts").read_text(encoding="utf-8")
    for reason in BLOCK_COPY:
        assert f"{reason}:" in source


@pytest.mark.hil
def test_recorder_reopen_preserves_sequence_and_backend_restarts_disarmed(
    tmp_path: Path,
) -> None:
    session = tmp_path / "restart.session"
    first = SessionTelemetryStore(session, min_free_bytes=0)
    assert first.append("before_restart", {"physicalOutput": False})["sequence"] == 1
    first.close()
    second = SessionTelemetryStore(session, min_free_bytes=0)
    assert second.append("after_restart", {"physicalOutput": False})["sequence"] == 2
    second.close()
    assert verify_session(session)["ok"] is True

    from gokkalkan_backend.operator_api import OperatorService

    restarted = OperatorService(dry_run=False, runtime_mode="LIVE")
    assert restarted.live_arm_enabled is False
    assert restarted.arm_controller.snapshot()["state"] == "DISARMED"
