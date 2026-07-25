from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

pytestmark = pytest.mark.safety

from gokkalkan_backend.operator_api import DryRunHardwareAdapter, OperatorService
from gokkalkan_backend.operator_http_server import build_http_server
from gokkalkan_backend.runtime_config import RuntimeConfigError, load_runtime_config
from gokkalkan_backend.safety_gate import (
    ForbiddenZone,
    LiveArmController,
    SafetyInputs,
    evaluate_safety,
)


def inputs(**changes: object) -> SafetyInputs:
    values: dict[str, object] = {
        "action": "motion",
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
    return SafetyInputs(**values)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "field",
    ["pico_heartbeat_ok", "can_ok", "encoder_ok", "camera_ok", "track_ok", "lidar_ok", "disk_ok"],
)
def test_every_live_health_fault_fails_closed(field: str) -> None:
    decision = evaluate_safety(inputs(**{field: False}))
    assert not decision.allowed
    assert decision.reason_code == "BLOCKED_SENSOR"
    assert decision.input_snapshot[field] is False


def test_invalid_and_boundary_zone_fail_closed() -> None:
    invalid = ForbiddenZone("bad", 2, 1, -1, 1)
    assert evaluate_safety(inputs(motion_zones=(invalid,))).reason_code == "BLOCKED_ZONE_CONFIG"
    zone = ForbiddenZone("boundary", 10, 20, -5, 5)
    decision = evaluate_safety(inputs(target_pan_deg=10, motion_zones=(zone,)))
    assert decision.reason_code == "BLOCKED_MOTION_ZONE"


def test_arm_hold_timeout_and_prerequisite_loss() -> None:
    arm = LiveArmController(hold_seconds=1.0, timeout_seconds=2.0)
    assert arm.hold(0.0, operator_holding=True, physical_interlock_ok=True, readiness_ok=True, pico_safe=True) == "HOLDING"
    assert arm.hold(1.0, operator_holding=True, physical_interlock_ok=True, readiness_ok=True, pico_safe=True) == "ARMED"
    assert arm.tick(3.1, prerequisites_ok=True) == "DISARMED"
    assert arm.hold(4.0, operator_holding=True, physical_interlock_ok=False, readiness_ok=True, pico_safe=True) == "FAULT"


def test_service_arm_requires_all_health_and_emits_system_command() -> None:
    adapter = DryRunHardwareAdapter()
    service = OperatorService(
        hardware=adapter,
        dry_run=False,
        runtime_mode="LIVE",
        arm_hold_seconds=0,
        physical_interlock_ok=True,
        backend_readiness_ok=True,
    )
    service.update_safety_health(
        {
            "pico_safe": True,
            "pico_heartbeat_ok": True,
            "can_ok": True,
            "encoder_ok": True,
            "camera_ok": True,
            "track_ok": True,
            "lidar_ok": True,
            "disk_ok": True,
        }
    )
    assert service.arm_hold(True, "operator-1")["ok"]
    assert adapter.commands[-1]["command"]["kind"] == "SysCmd"
    assert adapter.commands[-1]["command"]["payload"]["arm"] is True
    service.update_safety_health({"lidar_ok": False})
    assert not service.live_arm_enabled
    assert adapter.commands[-1]["command"]["payload"]["arm"] is False


def test_estop_release_does_not_clear_latch_without_controlled_reset(tmp_path: Path) -> None:
    service = OperatorService()
    service.set_estop(True)
    service.set_estop(False)
    assert service.estop
    assert service.reset_estop("")["ok"] is False
    assert service.reset_estop("operator-1")["ok"] is True
    assert not service.estop


def test_soft_limit_health_exception_never_calls_physical_adapter() -> None:
    class FaultingAdapter(DryRunHardwareAdapter):
        def health_check(self) -> dict[str, object]:
            raise RuntimeError("fault injection")

    adapter = FaultingAdapter()
    service = OperatorService(
        hardware=adapter,
        dry_run=False,
        runtime_mode="LIVE",
        physical_interlock_ok=True,
        backend_readiness_ok=True,
    )
    service.arm_controller.state = "ARMED"
    service.live_arm_enabled = True
    service.mode = "manual"
    service.stage = 1
    response = service.handle_manual_aim(
        {"panDeltaDeg": 1, "tiltDeltaDeg": 0, "rateLimitDegPerSec": 5, "deadmanActive": True}
    )
    assert not response["result"]["accepted"]
    assert response["hardwareResult"] is None
    assert adapter.commands == []


def test_live_http_mutations_require_token_and_identity() -> None:
    service = OperatorService(dry_run=False, runtime_mode="LIVE")
    server = build_http_server(
        "127.0.0.1", 0, service=service, allowed_origins=("http://127.0.0.1:4173",), operator_token="secret"
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    port = server.server_address[1]
    try:
        request = Request(
            f"http://127.0.0.1:{port}/mode",
            data=json.dumps({"requestedMode": "safe"}).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with pytest.raises(HTTPError) as error:
            urlopen(request, timeout=2)
        assert error.value.code == 401
        request.add_header("Authorization", "Bearer secret")
        request.add_header("X-Operator-Id", "operator-1")
        response = urlopen(request, timeout=2)
        assert response.status == 200
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_versioned_zones_load_and_invalid_geometry_rejects(tmp_path: Path) -> None:
    settings = load_runtime_config("config/runtime/sim.toml")
    assert settings.safety.zone_schema_version == 1
    assert len(settings.safety.motion_forbidden_zones) == 2
    invalid = Path("config/runtime/sim.toml").read_text().replace(
        'pan_min_deg = -180.0, pan_max_deg = -75.0',
        'pan_min_deg = -70.0, pan_max_deg = -75.0',
        1,
    )
    path = tmp_path / "invalid.toml"
    path.write_text(invalid)
    with pytest.raises(RuntimeConfigError, match="geometry"):
        load_runtime_config(path)


def test_live_profile_rejects_non_loopback_host(tmp_path: Path) -> None:
    live = Path("config/runtime/live.toml").read_text().replace(
        'host = "127.0.0.1"', 'host = "0.0.0.0"'
    )
    path = tmp_path / "live.toml"
    path.write_text(live)
    with pytest.raises(RuntimeConfigError, match="loopback"):
        load_runtime_config(path)
