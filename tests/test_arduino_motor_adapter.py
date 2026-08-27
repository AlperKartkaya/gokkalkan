from __future__ import annotations

from gokkalkan_backend.arduino_motor_adapter import ArduinoUnoMotorAdapter
from gokkalkan_backend.runtime_mode import RuntimeLaunchConfig, build_runtime_service
from gokkalkan_backend.telemetry_log import JsonlTelemetryStore


class FakeSerial:
    def __init__(self, *args, **kwargs):
        self.commands: list[str] = []
        self.closed = False

    def reset_input_buffer(self):
        pass

    def write(self, payload: bytes) -> int:
        self.commands.append(payload.decode("ascii").strip())
        return len(payload)

    def flush(self):
        pass

    def close(self):
        self.closed = True


def test_arduino_adapter_is_lazy_and_uses_field_protocol(monkeypatch):
    serial = FakeSerial()
    monkeypatch.setattr("serial.Serial", lambda *args, **kwargs: serial)
    adapter = ArduinoUnoMotorAdapter(port="/dev/ttyACM0")

    assert adapter.health()["connected"] is False
    assert adapter.move_pan(1.0, rate_limit_deg_per_sec=15.0) == "OK_SENT"
    assert serial.commands == ["STEP_PAN 50 800 CW"]

    assert adapter.move_tilt(0.0) == "OK_NOOP"
    assert adapter.stop() == "OK_SENT"
    assert serial.commands[-1] == "STOP"
    adapter.close()
    assert serial.closed is True


def test_execute_is_the_single_backend_to_arduino_boundary(monkeypatch):
    serial = FakeSerial()
    monkeypatch.setattr("serial.Serial", lambda *args, **kwargs: serial)
    adapter = ArduinoUnoMotorAdapter(
        port="/dev/ttyACM0", physical_output_capable=True
    )

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
    assert serial.commands == ["STEP_PAN 50 800 CW", "STEP_TILT 50 800 CCW"]


def test_field_step_matches_the_frontend_angle(monkeypatch):
    serial = FakeSerial()
    monkeypatch.setattr("serial.Serial", lambda *args, **kwargs: serial)
    adapter = ArduinoUnoMotorAdapter(port="/dev/ttyACM0")

    assert adapter.move_pan(11.25) == "OK_SENT"
    assert serial.commands == ["STEP_PAN 50 800 CW"]


def test_fire_never_falls_back_to_legacy_cobs(monkeypatch):
    serial = FakeSerial()
    monkeypatch.setattr("serial.Serial", lambda *args, **kwargs: serial)
    adapter = ArduinoUnoMotorAdapter(
        port="/dev/ttyACM0", physical_output_capable=True
    )

    result = adapter.execute(
        {"commandId": "FIRE-1", "kind": "FireIntent", "payload": {"stage": 3}}
    )

    assert result["accepted"] is False
    assert result["resultCode"] == "ARDUINO_FIRE_UNSUPPORTED"
    assert serial.commands == []


def test_autonomous_motion_is_blocked_without_position_feedback(monkeypatch):
    serial = FakeSerial()
    monkeypatch.setattr("serial.Serial", lambda *args, **kwargs: serial)
    adapter = ArduinoUnoMotorAdapter(
        port="/dev/ttyACM0", physical_output_capable=True
    )

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


def test_hil_loopback_accepts_motion_without_physical_output():
    adapter = ArduinoUnoMotorAdapter(
        port="loop://",
        physical_output_capable=True,
        serial_factory=lambda *args, **kwargs: FakeSerial(),
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
    assert adapter.health()["physicalOutputEnabled"] is False


def test_physical_hil_routes_deadman_motion_and_estop_to_field_protocol(tmp_path):
    serial = FakeSerial()

    def factory(**options):
        return ArduinoUnoMotorAdapter(
            **options,
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
    assert serial.commands[-1] == "STEP_PAN 50 800 CW"

    service.set_estop(True, physical=False)
    assert serial.commands[-1] == "STOP"
