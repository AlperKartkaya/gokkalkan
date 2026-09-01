from __future__ import annotations

from collections import deque

from gokkalkan_backend.arduino_motor_adapter import (
    FIELD_PROFILE_ID,
    ArduinoUnoMotorAdapter,
)
from gokkalkan_backend.runtime_mode import RuntimeLaunchConfig, build_runtime_service
from gokkalkan_backend.telemetry_log import JsonlTelemetryStore


class FakeSerial:
    """Scripted Uno serial peer; no electrical or firmware claim is implied."""

    def __init__(
        self,
        *args,
        profile: str = FIELD_PROFILE_ID,
        no_response_for: set[str] | None = None,
        **kwargs,
    ):
        self.commands: list[str] = []
        self.closed = False
        self.profile = profile
        self.no_response_for = no_response_for or set()
        self._responses: deque[bytes] = deque()

    def reset_input_buffer(self):
        pass

    def write(self, payload: bytes) -> int:
        command = payload.decode("ascii").strip()
        self.commands.append(command)
        if command in self.no_response_for:
            self._responses.append(b"")
        elif command == "PING":
            self._responses.append(b"PONG\n")
        elif command == "PROFILE":
            self._responses.append(f"PROFILE {self.profile}\n".encode("ascii"))
        elif command == "STOP":
            self._responses.append(b"OK STOPPED\n")
        else:
            self._responses.append(b"OK SENT\n")
        return len(payload)

    def readline(self) -> bytes:
        return self._responses.popleft() if self._responses else b""

    def flush(self):
        pass

    def close(self):
        self.closed = True


def physical_adapter(serial: FakeSerial) -> ArduinoUnoMotorAdapter:
    return ArduinoUnoMotorAdapter(
        port="/dev/ttyACM0",
        physical_output_capable=True,
        boot_wait_seconds=0,
        serial_factory=lambda *args, **kwargs: serial,
    )


def test_arduino_adapter_is_lazy_verifies_profile_and_uses_rate_derived_steps():
    serial = FakeSerial()
    adapter = physical_adapter(serial)

    assert adapter.health()["connected"] is False
    assert adapter.move_pan(1.0, rate_limit_deg_per_sec=15.0) == "OK_SENT"
    assert serial.commands == ["PING", "PROFILE", "STEP_PAN 4 7500 CW"]
    assert adapter.health()["arduinoProtocolReady"] is True
    assert adapter.health()["firmwareProfile"] == FIELD_PROFILE_ID

    assert adapter.move_tilt(0.0) == "OK_NOOP"
    assert adapter.stop() == "OK_SENT"
    assert serial.commands[-1] == "STOP"
    adapter.close()
    assert serial.closed is True


def test_execute_is_the_single_backend_to_arduino_boundary():
    serial = FakeSerial()
    adapter = physical_adapter(serial)

    result = adapter.execute(
        {
            "commandId": "CMD-1",
            "kind": "ManualAimCommand",
            "payload": {
                "panDeltaDeg": 2.0,
                "tiltDeltaDeg": -1.0,
                "rateLimitDegPerSec": 15.0,
            },
        }
    )

    assert result["accepted"] is True
    assert result["physicalOutput"] is True
    assert serial.commands == [
        "PING",
        "PROFILE",
        "STEP_PAN 9 7500 CW",
        "STEP_TILT 4 7500 CCW",
    ]


def test_field_step_matches_the_frontend_angle_and_limit():
    serial = FakeSerial()
    adapter = physical_adapter(serial)

    assert adapter.move_pan(11.25) == "OK_SENT"
    assert serial.commands == ["PING", "PROFILE", "STEP_PAN 50 7500 CW"]


def test_invalid_motion_stays_local_and_never_opens_a_serial_port():
    adapter = ArduinoUnoMotorAdapter(port="/dev/ttyACM0")

    assert adapter.step_pan(0) == "ERR_STEP_COUNT_OUT_OF_RANGE"
    assert adapter.step_tilt(1601) == "ERR_STEP_COUNT_OUT_OF_RANGE"
    assert adapter.step_pan(1, 79) == "ERR_STEP_DELAY_OUT_OF_RANGE"
    assert adapter.move_pan(11.26) == "ERR_MANUAL_DELTA_OUT_OF_RANGE"
    assert adapter.move_tilt(1.0, rate_limit_deg_per_sec=30.1) == "ERR_RATE_LIMIT_OUT_OF_RANGE"
    assert adapter.move_tilt(1.0, rate_limit_deg_per_sec=0.01) == (
        "ERR_RATE_LIMIT_BELOW_FIRMWARE_MIN"
    )
    assert adapter.health()["connected"] is False


def test_direct_motion_helpers_cannot_bypass_a_physical_output_gate():
    adapter = ArduinoUnoMotorAdapter(port="/dev/ttyACM0")

    assert adapter.step_pan(1, 800, "CW") == "ERR_PHYSICAL_OUTPUT_DISABLED"
    assert adapter.run_tilt_timed(1, 800, "CW") == "ERR_PHYSICAL_OUTPUT_DISABLED"
    assert adapter.health()["connected"] is False


def test_profile_mismatch_blocks_physical_motion_before_step_command():
    serial = FakeSerial(profile="GKK-UNO-DM542-LEGACY")
    adapter = physical_adapter(serial)

    result = adapter.execute(
        {
            "commandId": "PROFILE-MISMATCH",
            "kind": "ManualAimCommand",
            "payload": {"panDeltaDeg": 1.0, "rateLimitDegPerSec": 15.0},
        }
    )

    assert result["accepted"] is False
    assert result["resultCode"] == "ARDUINO_PROTOCOL_UNVERIFIED"
    assert serial.commands == ["PING", "PROFILE"]
    assert serial.closed is True
    assert adapter.health()["arduinoProtocolReady"] is False


def test_missing_motion_ack_is_rejected_after_profile_verification():
    serial = FakeSerial(no_response_for={"STEP_PAN 4 7500 CW"})
    adapter = physical_adapter(serial)

    result = adapter.execute(
        {
            "commandId": "NO-ACK",
            "kind": "ManualAimCommand",
            "payload": {"panDeltaDeg": 1.0, "rateLimitDegPerSec": 15.0},
        }
    )

    assert result["accepted"] is False
    assert result["resultCode"] == "MOTION_SEND_FAILED"
    assert serial.commands == ["PING", "PROFILE", "STEP_PAN 4 7500 CW"]
    assert adapter.health()["lastError"] == "ARDUINO_NO_RESPONSE"


def test_fire_never_falls_back_to_legacy_cobs_or_opens_serial_port():
    serial = FakeSerial()
    adapter = physical_adapter(serial)

    result = adapter.execute(
        {"commandId": "FIRE-1", "kind": "FireIntent", "payload": {"stage": 3}}
    )

    assert result["accepted"] is False
    assert result["resultCode"] == "ARDUINO_FIRE_UNSUPPORTED"
    assert serial.commands == []


def test_autonomous_motion_is_blocked_without_position_feedback_or_serial_io():
    serial = FakeSerial()
    adapter = physical_adapter(serial)

    result = adapter.execute(
        {
            "commandId": "AUTO-1",
            "kind": "AutonomousAimCommand",
            "payload": {"panDeltaDeg": 11.25},
        }
    )

    assert result["accepted"] is False
    assert result["resultCode"] == "ARDUINO_AUTONOMOUS_UNSUPPORTED"
    assert serial.commands == []


def test_hil_loopback_accepts_framing_without_claiming_firmware_or_physical_output():
    serial = FakeSerial()
    adapter = ArduinoUnoMotorAdapter(
        port="loop://",
        physical_output_capable=True,
        serial_factory=lambda *args, **kwargs: serial,
    )

    result = adapter.execute(
        {
            "commandId": "HIL-1",
            "kind": "ManualAimCommand",
            "payload": {"panDeltaDeg": 11.25},
        }
    )

    assert result["accepted"] is True
    assert result["physicalOutput"] is False
    assert serial.commands == ["STEP_PAN 50 7500 CW"]
    assert adapter.health()["arduinoProtocolReady"] is False
    assert adapter.health()["physicalOutputEnabled"] is False


def test_physical_hil_routes_deadman_motion_and_estop_to_verified_field_protocol(tmp_path):
    serial = FakeSerial()

    def factory(**options):
        return ArduinoUnoMotorAdapter(
            **options,
            boot_wait_seconds=0,
            serial_factory=lambda *args, **kwargs: serial,
        )

    service = build_runtime_service(
        RuntimeLaunchConfig(
            mode="HIL",
            mcu_port="/dev/serial/by-id/test-arduino",
            hil_physical_mcu_enabled=True,
        ),
        telemetry=JsonlTelemetryStore(tmp_path / "hil.jsonl"),
        mcu_adapter_factory=factory,
    )
    service.handle_stage_request({"stage": 1, "round": 1})

    response = service.handle_manual_aim(
        {
            "panDeltaDeg": 11.25,
            "tiltDeltaDeg": 0.0,
            "rateLimitDegPerSec": 15.0,
            "deadmanActive": True,
        }
    )

    assert response["result"]["accepted"] is True
    assert response["result"]["physicalOutput"] is True
    assert response["result"]["message"] == "Arduino HIL motor hareketi gönderildi."
    assert serial.commands == ["PING", "PROFILE", "STEP_PAN 50 7500 CW"]

    service.set_estop(True, physical=False)
    assert serial.commands[-1] == "STOP"
