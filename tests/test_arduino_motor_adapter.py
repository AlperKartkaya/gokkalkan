from __future__ import annotations

from gokkalkan_backend.arduino_motor_adapter import ArduinoUnoMotorAdapter


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
