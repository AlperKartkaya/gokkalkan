"""Arduino Uno & DM542 Dual Stepper Motor Serial Adapter.

Pin Mapping (from realtimetesting):
  - Motor 1 (PAN)  : Pin 2 (PUL+), Pin 3 (DIR+) -> DM542 Pan Driver
  - Motor 2 (TILT) : Pin 4 (PUL+), Pin 5 (DIR+) -> DM542 Tilt Driver
  - Common Cathode : Arduino GND -> All PUL- and DIR- terminals
  - Serial Speed   : 115200 Baud
"""

from __future__ import annotations

import glob
import logging
import threading
import time
from typing import Any

logger = logging.getLogger("gokkalkan.arduino_motor")


class ArduinoUnoMotorAdapter:
    """Manages serial communication with Arduino Uno running the dual DM542 firmware."""

    STEPS_PER_DEG = 1600.0 / 360.0  # 1600 Pulses/Rev microstep setting

    def __init__(self, port: str | None = None, baudrate: int = 115200) -> None:
        self.port = port
        self.baudrate = baudrate
        self._serial: Any | None = None
        self._lock = threading.Lock()
        self._connected = False
        self._last_error: str | None = None
        self._last_attempt_time = 0.0
        self.active_port: str | None = None

    def _find_port(self) -> str | None:
        candidates = []
        try:
            import serial.tools.list_ports
            ports = list(serial.tools.list_ports.comports())
            for p in ports:
                desc = (p.description or "").lower()
                mfr = (p.manufacturer or "").lower()
                dev = p.device.lower()
                if "arduino" in desc or "arduino" in mfr or "ttyacm" in dev:
                    candidates.insert(0, p.device)
                elif any(x in desc or x in mfr or x in dev for x in ["ch340", "ch341", "cp210", "ftdi", "ttyusb"]):
                    candidates.append(p.device)
                else:
                    candidates.append(p.device)
        except Exception:
            pass

        try:
            linux_cands = sorted(
                glob.glob("/dev/ttyACM*")
                + glob.glob("/dev/serial/by-id/*")
                + glob.glob("/dev/ttyUSB*")
            )
            for c in linux_cands:
                if c not in candidates:
                    if "ttyACM" in c or "arduino" in c.lower():
                        candidates.insert(0, c)
                    else:
                        candidates.append(c)
        except Exception:
            pass

        if not candidates:
            return None

        # Try candidates to find which one responds to PING
        try:
            import serial
            for cand in candidates:
                try:
                    s = serial.Serial(cand, self.baudrate, timeout=0.15)
                    time.sleep(0.15)
                    s.reset_input_buffer()
                    s.write(b"PING\n")
                    time.sleep(0.08)
                    resp = s.readline().decode("utf-8", errors="ignore").strip()
                    s.close()
                    if "PONG" in resp or "STATUS" in resp or "OK" in resp:
                        return cand
                except Exception:
                    continue
        except Exception:
            pass

        return candidates[0] if candidates else None

    def connect(self) -> bool:
        with self._lock:
            if self._connected and self._serial is not None:
                return True

            now = time.monotonic()
            if now - self._last_attempt_time < 2.0:
                return False
            self._last_attempt_time = now

            target_port = self.port or self._find_port()
            if not target_port:
                self._last_error = "NO_PORT_DETECTED"
                return False

            try:
                import serial
                self._serial = serial.Serial(target_port, self.baudrate, timeout=0.08)
                time.sleep(0.3)
                self._connected = True
                self.active_port = target_port
                self._last_error = None
                logger.info("Arduino Uno motor adapter connected on %s", target_port)
                return True
            except Exception as exc:
                self._serial = None
                self._connected = False
                self._last_error = f"{type(exc).__name__}: {exc}"
                logger.debug("Arduino Uno serial connection skipped/failed: %s", self._last_error)
                return False

    def send_raw_command(self, cmd: str) -> str:
        with self._lock:
            if not self._connected or self._serial is None:
                if not self.connect():
                    return f"ERR_NOT_CONNECTED: {self._last_error}"

            try:
                assert self._serial is not None
                self._serial.reset_input_buffer()
                self._serial.write((cmd.strip() + "\n").encode("ascii"))
                time.sleep(0.04)
                lines = []
                while self._serial.in_waiting > 0:
                    line = self._serial.readline().decode("utf-8", errors="ignore").strip()
                    if line:
                        lines.append(line)
                return " | ".join(lines) if lines else "OK_SENT"
            except Exception as exc:
                self._connected = False
                if self._serial:
                    try:
                        self._serial.close()
                    except Exception:
                        pass
                self._serial = None
                self._last_error = str(exc)
                return f"ERR_SERIAL: {exc}"

    def step_pan(self, steps: int, delay_us: int = 800, direction: str = "CW") -> str:
        """Command Pan Motor by discrete steps."""
        cmd = f"STEP_PAN {steps} {delay_us} {direction.upper()}"
        return self.send_raw_command(cmd)

    def step_tilt(self, steps: int, delay_us: int = 800, direction: str = "CW") -> str:
        """Command Tilt Motor by discrete steps."""
        cmd = f"STEP_TILT {steps} {delay_us} {direction.upper()}"
        return self.send_raw_command(cmd)

    def move_pan(self, pan_delta_deg: float, rate_limit_deg_per_sec: float = 15.0) -> str:
        """Command Pan Motor (Pin 2/3). Positive -> CW (Right), Negative -> CCW (Left)."""
        direction = "CW" if pan_delta_deg >= 0 else "CCW"
        steps = max(1, int(round(abs(pan_delta_deg) * self.STEPS_PER_DEG)))
        return self.step_pan(steps=steps, delay_us=800, direction=direction)

    def move_tilt(self, tilt_delta_deg: float, rate_limit_deg_per_sec: float = 15.0) -> str:
        """Command Tilt Motor (Pin 4/5). Positive -> CW (Up), Negative -> CCW (Down)."""
        direction = "CW" if tilt_delta_deg >= 0 else "CCW"
        steps = max(1, int(round(abs(tilt_delta_deg) * self.STEPS_PER_DEG)))
        return self.step_tilt(steps=steps, delay_us=800, direction=direction)

    def stop(self) -> str:
        """Emergency Halt all motors."""
        return self.send_raw_command("STOP")

    def health(self) -> dict[str, Any]:
        return {
            "connected": self._connected,
            "port": self.active_port or self.port,
            "lastError": self._last_error,
        }
