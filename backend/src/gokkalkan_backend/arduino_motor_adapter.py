"""Fail-closed Arduino Uno + DM542 dual-axis serial adapter.

The active field profile is deliberately fixed in firmware instead of being a
runtime pin configuration:

* PAN  — D2 ``PUL+``, D3 ``DIR+``
* TILT — D4 ``PUL+``, D5 ``DIR+``
* DM542 ``PUL-``/``DIR-`` — Arduino GND (common cathode)
* USB serial — 115200 baud, newline-delimited ASCII

``GOKKALKAN-LITE`` is the provenance for the field wiring and 1600
pulses/revolution calibration. It is not a safety authority: physical output
still requires the runtime gate, a matching firmware profile, and the separate
physical E-Stop/contactors described in the hardware documentation.
"""

from __future__ import annotations

import glob
import logging
import threading
import time
from datetime import UTC, datetime
from math import ceil, isfinite
from typing import Any

from .hardware_adapter import HardwareAdapterBase

logger = logging.getLogger("gokkalkan.arduino_motor")


FIELD_PROFILE_ID = "GKK-UNO-DM542-1600PPR-R1"
PAN_PUL_PIN = 2
PAN_DIR_PIN = 3
TILT_PUL_PIN = 4
TILT_DIR_PIN = 5
STATUS_LED_PIN = 13
SERIAL_BAUDRATE = 115_200
PULSES_PER_REVOLUTION = 1_600
STEPS_PER_DEGREE = PULSES_PER_REVOLUTION / 360.0
DEFAULT_STEP_HALF_PERIOD_US = 800
MIN_STEP_HALF_PERIOD_US = 80
MAX_STEP_HALF_PERIOD_US = 1_000_000
MAX_STEPS_PER_COMMAND = PULSES_PER_REVOLUTION
MAX_MANUAL_DELTA_DEG = 11.25
MAX_MANUAL_RATE_DEG_PER_SEC = 30.0
MAX_RUN_DURATION_SEC = 15
MAX_RUN_SPEED_HZ = 1_250


class ArduinoUnoMotorAdapter(HardwareAdapterBase):
    """Translate Safety Gate-approved intent to the fixed Uno field protocol.

    A non-virtual serial connection is only considered output-capable after
    ``PING``/``PONG`` and ``PROFILE`` verify the flashed firmware. This keeps a
    swapped USB device or an older incompatible sketch from receiving motion
    commands merely because it opens at 115200 baud.
    """

    FIELD_PROFILE_ID = FIELD_PROFILE_ID
    STEPS_PER_DEG = STEPS_PER_DEGREE

    def __init__(
        self,
        port: str | None = None,
        baudrate: int = SERIAL_BAUDRATE,
        *,
        heartbeat_timeout_sec: float = 2.0,
        dry_run: bool = False,
        physical_output_capable: bool = False,
        expected_field_profile: str = FIELD_PROFILE_ID,
        boot_wait_seconds: float = 1.8,
        response_timeout_sec: float = 0.25,
        serial_factory: Any | None = None,
    ) -> None:
        self.port = port
        self.baudrate = baudrate
        self.heartbeat_timeout_sec = heartbeat_timeout_sec
        self.dry_run = dry_run
        self.physical_output_capable = physical_output_capable
        self.expected_field_profile = expected_field_profile.strip()
        self.boot_wait_seconds = max(0.0, float(boot_wait_seconds))
        self.response_timeout_sec = max(0.04, float(response_timeout_sec))
        self._serial_factory = serial_factory
        self._serial: Any | None = None
        self._lock = threading.RLock()
        self._connected = False
        self._protocol_ready = False
        self._firmware_profile: str | None = None
        self._last_response: str | None = None
        self._last_error: str | None = None
        self._last_attempt_time = 0.0
        self.active_port: str | None = None
        self._started = False
        # Construction must not touch a serial port. Runtime mode owns that
        # transition through start() and physical-output authority.

    @staticmethod
    def _is_virtual_port(port: str | None) -> bool:
        return bool(port and port.startswith("loop://"))

    def _find_port(self) -> str | None:
        candidates: list[str] = []
        try:
            import serial.tools.list_ports

            ports = list(serial.tools.list_ports.comports())
            for candidate in ports:
                description = (candidate.description or "").lower()
                manufacturer = (candidate.manufacturer or "").lower()
                device = candidate.device.lower()
                if "arduino" in description or "arduino" in manufacturer or "ttyacm" in device:
                    candidates.insert(0, candidate.device)
                elif any(
                    marker in description or marker in manufacturer or marker in device
                    for marker in ("ch340", "ch341", "cp210", "ftdi", "ttyusb")
                ):
                    candidates.append(candidate.device)
                else:
                    candidates.append(candidate.device)
        except Exception:
            logger.debug("Arduino port discovery via pyserial failed", exc_info=True)

        try:
            linux_candidates = sorted(
                glob.glob("/dev/serial/by-id/*")
                + glob.glob("/dev/ttyUSB*")
                + glob.glob("/dev/ttyACM*")
            )
            for candidate in linux_candidates:
                if candidate not in candidates:
                    candidates.insert(0, candidate)
        except Exception:
            logger.debug("Arduino Linux port discovery failed", exc_info=True)

        return candidates[0] if candidates else None

    def _close_serial_locked(self) -> None:
        serial_obj, self._serial = self._serial, None
        self._connected = False
        self._protocol_ready = False
        self._firmware_profile = None
        self.active_port = None
        if serial_obj is not None:
            try:
                serial_obj.close()
            except Exception:
                logger.debug("Arduino serial close failed", exc_info=True)

    def _exchange_locked(self, command: str) -> str:
        """Write one command and return the first complete response line."""
        assert self._serial is not None
        self._serial.reset_input_buffer()
        self._serial.write((command.strip() + "\n").encode("ascii"))
        self._serial.flush()
        response = self._serial.readline().decode("ascii", errors="replace").strip()
        self._last_response = response or None
        return response

    @staticmethod
    def _profile_from_response(response: str) -> str | None:
        prefix = "PROFILE "
        normalized = response.strip()
        if not normalized.startswith(prefix):
            return None
        profile = normalized[len(prefix) :].strip()
        return profile or None

    def _verify_field_profile_locked(self, target_port: str) -> bool:
        if self._is_virtual_port(target_port):
            # loop:// is transport-only HIL evidence, not firmware evidence.
            self._last_response = "LOOPBACK_TRANSPORT_ONLY"
            return True

        if self.boot_wait_seconds:
            time.sleep(self.boot_wait_seconds)

        pong = self._exchange_locked("PING")
        if pong.upper() != "PONG":
            self._last_error = (
                "ARDUINO_PROTOCOL_PING_FAILED: expected PONG, "
                f"received {pong!r}"
            )
            return False

        profile_response = self._exchange_locked("PROFILE")
        profile = self._profile_from_response(profile_response)
        if profile != self.expected_field_profile:
            self._last_error = (
                "ARDUINO_PROFILE_MISMATCH: expected "
                f"{self.expected_field_profile!r}, received {profile!r}"
            )
            return False

        self._protocol_ready = True
        self._firmware_profile = profile
        self._last_error = None
        return True

    def connect(self) -> bool:
        """Open the transport and verify the field firmware before use."""
        with self._lock:
            if self._connected and self._serial is not None:
                return self._is_virtual_port(self.active_port) or self._protocol_ready

            now = time.monotonic()
            if now - self._last_attempt_time < 0.5:
                return False
            self._last_attempt_time = now

            target_port = self.port or self._find_port()
            if not target_port:
                self._last_error = "NO_PORT_DETECTED"
                return False

            try:
                factory = self._serial_factory
                if factory is None:
                    import serial

                    factory = (
                        serial.serial_for_url
                        if "://" in target_port
                        else serial.Serial
                    )
                self._serial = factory(
                    target_port,
                    self.baudrate,
                    timeout=self.response_timeout_sec,
                    write_timeout=self.response_timeout_sec,
                )
                self._connected = True
                self.active_port = target_port
                self._protocol_ready = False
                self._firmware_profile = None
                if not self._verify_field_profile_locked(target_port):
                    self._close_serial_locked()
                    logger.warning("Arduino field profile verification failed: %s", self._last_error)
                    return False
                logger.info("Arduino Uno motor adapter connected on %s", target_port)
                return True
            except Exception as exc:
                self._close_serial_locked()
                self._last_error = f"{type(exc).__name__}: {exc}"
                logger.debug("Arduino Uno serial connection skipped/failed: %s", self._last_error)
                return False

    def send_raw_command(self, command: str) -> str:
        """Send a bounded firmware command and require an acknowledgement.

        The virtual ``loop://`` path proves framing only and intentionally does
        not pretend that a firmware acknowledgement was observed.
        """
        with self._lock:
            if not self._connected or self._serial is None:
                if not self.connect():
                    return f"ERR_NOT_CONNECTED: {self._last_error}"

            target_port = self.active_port or self.port
            if self._is_virtual_port(target_port):
                try:
                    assert self._serial is not None
                    self._serial.reset_input_buffer()
                    self._serial.write((command.strip() + "\n").encode("ascii"))
                    self._serial.flush()
                    self._last_response = "LOOPBACK_TRANSPORT_ONLY"
                    return "OK_SENT"
                except Exception as exc:
                    self._last_error = str(exc)
                    self._close_serial_locked()
                    return f"ERR_SERIAL: {exc}"

            if not self._protocol_ready:
                return f"ERR_PROTOCOL_UNVERIFIED: {self._last_error}"

            try:
                response = self._exchange_locked(command)
                if not response:
                    self._last_error = "ARDUINO_NO_RESPONSE"
                    return "ERR_NO_RESPONSE"
                if response.upper().startswith("ERR"):
                    self._last_error = f"ARDUINO_FIRMWARE: {response}"
                    return f"ERR_FIRMWARE: {response}"
                self._last_error = None
                return "OK_SENT"
            except Exception as exc:
                self._last_error = str(exc)
                self._close_serial_locked()
                return f"ERR_SERIAL: {exc}"

    def start(self) -> None:
        """Start the adapter; the physical handshake is observable in health."""
        with self._lock:
            self._started = True
        if not self.dry_run:
            self.connect()

    def _physical_protocol_ready(self) -> bool:
        if self._is_virtual_port(self.port or self.active_port):
            return True
        return self.connect() and self._protocol_ready

    def execute(self, command: dict[str, Any]) -> dict[str, Any]:
        """Translate the backend command contract to the Uno line protocol.

        Firmware offers bounded manual movement and STOP only. FIRE and
        autonomous movement remain rejected at this hardware boundary.
        """
        kind = str(command.get("kind", "Unknown"))
        command_id = str(command.get("commandId", "ARDUINO-UNSET"))
        created_at = datetime.now(UTC).isoformat().replace("+00:00", "Z")
        base = {
            "adapter": "arduino_uno_serial",
            "fieldProfile": self.expected_field_profile,
            "commandId": command_id,
            "kind": kind,
            "createdAt": created_at,
            "dryRun": self.dry_run,
            "physicalOutput": False,
        }
        if self.dry_run:
            return {
                **base,
                "accepted": True,
                "completed": True,
                "resultCode": "DRY_RUN",
                "message": "Arduino komutu dry-run kaydı; fiziksel çıkış yok.",
            }

        # These command kinds have no Arduino implementation. Reject before
        # opening a serial device: unsupported intent must not create a side
        # effect merely because an operator requested it.
        if kind == "AutonomousAimCommand":
            return {
                **base,
                "accepted": False,
                "completed": False,
                "resultCode": "ARDUINO_AUTONOMOUS_UNSUPPORTED",
                "message": "Arduino saha firmware'i geri bildirimsiz otonom harekete kapalı.",
            }
        if kind == "FireIntent":
            return {
                **base,
                "accepted": False,
                "completed": False,
                "resultCode": "ARDUINO_FIRE_UNSUPPORTED",
                "message": "Arduino Uno firmware'inde FIRE komutu yok; ateşleme fail-closed reddedildi.",
            }

        virtual_output = self._is_virtual_port(self.port or self.active_port)
        if not self.physical_output_capable and not virtual_output:
            return {
                **base,
                "accepted": False,
                "completed": False,
                "resultCode": "PHYSICAL_OUTPUT_DISABLED",
                "message": "Arduino fiziksel çıkışı bu runtime'da kapalı.",
            }
        if not virtual_output and not self._physical_protocol_ready():
            return {
                **base,
                "accepted": False,
                "completed": False,
                "resultCode": "ARDUINO_PROTOCOL_UNVERIFIED",
                "message": "Arduino PING/PROFILE doğrulaması başarısız; hareket fail-closed engellendi.",
            }

        payload = command.get("payload")
        payload = payload if isinstance(payload, dict) else {}
        if kind == "ManualAimCommand":
            try:
                pan = float(payload.get("panDeltaDeg", 0.0))
                tilt = float(payload.get("tiltDeltaDeg", 0.0))
                rate = float(payload.get("rateLimitDegPerSec", 15.0))
            except (TypeError, ValueError):
                pan = tilt = rate = float("nan")
            if not all(isfinite(value) for value in (pan, tilt, rate)):
                return {
                    **base,
                    "accepted": False,
                    "completed": False,
                    "resultCode": "INVALID_MOTION_PAYLOAD",
                    "message": "Arduino hareket payload'ı geçersiz.",
                }
            results: list[str] = []
            if pan:
                results.append(self.move_pan(pan, rate))
            if tilt:
                results.append(self.move_tilt(tilt, rate))
            accepted = bool(results) and all(item == "OK_SENT" for item in results)
            if not results:
                accepted = True
            result_code = "MOTION_SENT" if accepted else "MOTION_SEND_FAILED"
            if any(item == "ERR_MANUAL_DELTA_OUT_OF_RANGE" for item in results):
                result_code = "MANUAL_DELTA_OUT_OF_RANGE"
            elif any(item == "ERR_RATE_LIMIT_OUT_OF_RANGE" for item in results):
                result_code = "RATE_LIMIT_OUT_OF_RANGE"
            elif any(item == "ERR_RATE_LIMIT_BELOW_FIRMWARE_MIN" for item in results):
                result_code = "RATE_LIMIT_BELOW_FIRMWARE_MIN"
            return {
                **base,
                "accepted": accepted,
                "completed": accepted,
                "physicalOutput": (
                    accepted and self.physical_output_capable and not virtual_output
                ),
                "resultCode": result_code,
                "message": (
                    "Arduino motor komutu onaylandı."
                    if accepted
                    else "Arduino motor komutu onaylanmadı."
                ),
                "commands": results,
            }
        if kind == "SysCmd" and payload.get("arm") is False:
            status = self.stop()
            accepted = status == "OK_SENT"
            return {
                **base,
                "accepted": accepted,
                "completed": accepted,
                "physicalOutput": (
                    accepted and self.physical_output_capable and not virtual_output
                ),
                "resultCode": "STOP_SENT" if accepted else "STOP_SEND_FAILED",
                "message": (
                    "Arduino STOP komutu onaylandı."
                    if accepted
                    else "Arduino STOP komutu onaylanmadı."
                ),
            }
        return {
            **base,
            "accepted": False,
            "completed": False,
            "resultCode": "UNSUPPORTED_ARDUINO_COMMAND",
            "message": f"Arduino komut türü desteklenmiyor: {kind}",
        }

    @staticmethod
    def _valid_direction(direction: str) -> str | None:
        normalized = direction.strip().upper()
        return normalized if normalized in {"CW", "CCW"} else None

    def _step(self, axis: str, steps: int, delay_us: int, direction: str) -> str:
        if isinstance(steps, bool) or not isinstance(steps, int):
            return "ERR_INVALID_STEP_COUNT"
        if not 1 <= steps <= MAX_STEPS_PER_COMMAND:
            return "ERR_STEP_COUNT_OUT_OF_RANGE"
        if isinstance(delay_us, bool) or not isinstance(delay_us, int):
            return "ERR_INVALID_STEP_DELAY"
        if not MIN_STEP_HALF_PERIOD_US <= delay_us <= MAX_STEP_HALF_PERIOD_US:
            return "ERR_STEP_DELAY_OUT_OF_RANGE"
        direction_token = self._valid_direction(direction)
        if direction_token is None:
            return "ERR_INVALID_DIRECTION"
        return self._send_motion_command(
            f"STEP_{axis} {steps} {delay_us} {direction_token}"
        )

    def _send_motion_command(self, command: str) -> str:
        """Keep public maintenance helpers behind the same output gate.

        ``execute`` is the normal Safety Gate boundary, but step/run helpers
        are also used by focused diagnostics and must not bypass an
        output-disabled physical runtime.
        """
        if self.dry_run:
            return "ERR_DRY_RUN_MOTION_NOT_SENT"
        virtual_output = self._is_virtual_port(self.port or self.active_port)
        if not virtual_output and not self.physical_output_capable:
            return "ERR_PHYSICAL_OUTPUT_DISABLED"
        if not virtual_output and not self._physical_protocol_ready():
            return "ERR_PROTOCOL_UNVERIFIED"
        return self.send_raw_command(command)

    def step_pan(
        self,
        steps: int,
        delay_us: int = DEFAULT_STEP_HALF_PERIOD_US,
        direction: str = "CW",
    ) -> str:
        """Command the PAN axis by a bounded number of field-profile pulses."""
        return self._step("PAN", steps, delay_us, direction)

    def step_tilt(
        self,
        steps: int,
        delay_us: int = DEFAULT_STEP_HALF_PERIOD_US,
        direction: str = "CW",
    ) -> str:
        """Command the TILT axis by a bounded number of field-profile pulses."""
        return self._step("TILT", steps, delay_us, direction)

    @staticmethod
    def _steps_for_delta(delta_deg: float) -> int | None:
        if not isfinite(delta_deg) or abs(delta_deg) > MAX_MANUAL_DELTA_DEG:
            return None
        return max(1, int(round(abs(delta_deg) * STEPS_PER_DEGREE)))

    @staticmethod
    def _delay_for_rate(rate_limit_deg_per_sec: float) -> int | None:
        if (
            not isfinite(rate_limit_deg_per_sec)
            or not 0 < rate_limit_deg_per_sec <= MAX_MANUAL_RATE_DEG_PER_SEC
        ):
            return None
        delay_us = ceil(
            1_000_000.0
            / (2.0 * STEPS_PER_DEGREE * rate_limit_deg_per_sec)
        )
        if delay_us > MAX_STEP_HALF_PERIOD_US:
            return None
        return max(MIN_STEP_HALF_PERIOD_US, delay_us)

    def _move_axis(self, axis: str, delta_deg: float, rate_limit_deg_per_sec: float) -> str:
        if delta_deg == 0:
            return "OK_NOOP"
        steps = self._steps_for_delta(delta_deg)
        if steps is None:
            return "ERR_MANUAL_DELTA_OUT_OF_RANGE"
        delay_us = self._delay_for_rate(rate_limit_deg_per_sec)
        if delay_us is None:
            if (
                isfinite(rate_limit_deg_per_sec)
                and 0 < rate_limit_deg_per_sec <= MAX_MANUAL_RATE_DEG_PER_SEC
            ):
                return "ERR_RATE_LIMIT_BELOW_FIRMWARE_MIN"
            return "ERR_RATE_LIMIT_OUT_OF_RANGE"
        direction = "CW" if delta_deg >= 0 else "CCW"
        return self._step(axis, steps, delay_us, direction)

    def move_pan(
        self,
        pan_delta_deg: float,
        rate_limit_deg_per_sec: float = 15.0,
    ) -> str:
        """Positive PAN is CW/right; movement is bounded by the UI contract."""
        return self._move_axis("PAN", pan_delta_deg, rate_limit_deg_per_sec)

    def move_tilt(
        self,
        tilt_delta_deg: float,
        rate_limit_deg_per_sec: float = 15.0,
    ) -> str:
        """Positive TILT is CW/up; movement is bounded by the UI contract."""
        return self._move_axis("TILT", tilt_delta_deg, rate_limit_deg_per_sec)

    def _run_timed(self, axis: str, duration_sec: int, speed_hz: int, direction: str) -> str:
        if isinstance(duration_sec, bool) or not isinstance(duration_sec, int):
            return "ERR_INVALID_RUN_DURATION"
        if not 1 <= duration_sec <= MAX_RUN_DURATION_SEC:
            return "ERR_RUN_DURATION_OUT_OF_RANGE"
        if isinstance(speed_hz, bool) or not isinstance(speed_hz, int):
            return "ERR_INVALID_RUN_SPEED"
        if not 1 <= speed_hz <= MAX_RUN_SPEED_HZ:
            return "ERR_RUN_SPEED_OUT_OF_RANGE"
        direction_token = self._valid_direction(direction)
        if direction_token is None:
            return "ERR_INVALID_DIRECTION"
        return self._send_motion_command(
            f"RUN_{axis} {duration_sec} {speed_hz} {direction_token}"
        )

    def run_pan_timed(
        self,
        duration_sec: int,
        speed_hz: int = 800,
        direction: str = "CW",
    ) -> str:
        """Maintenance-only bounded PAN run; not used by the operator API."""
        return self._run_timed("PAN", duration_sec, speed_hz, direction)

    def run_tilt_timed(
        self,
        duration_sec: int,
        speed_hz: int = 800,
        direction: str = "CW",
    ) -> str:
        """Maintenance-only bounded TILT run; not used by the operator API."""
        return self._run_timed("TILT", duration_sec, speed_hz, direction)

    def stop(self) -> str:
        """Idempotently halt both axes and drive their pulse lines low."""
        return self.send_raw_command("STOP")

    def emergency_stop(self) -> str:
        return self.stop()

    def close(self) -> None:
        with self._lock:
            self._close_serial_locked()
            self._started = False

    def health(self) -> dict[str, Any]:
        virtual_port = self._is_virtual_port(self.active_port or self.port)
        protocol_ready = self._protocol_ready and not virtual_port
        return {
            "adapter": "arduino_uno_serial",
            "transport": "arduino_serial",
            "fieldProfile": self.expected_field_profile,
            "firmwareProfile": self._firmware_profile,
            "dryRun": self.dry_run,
            "connected": self._connected,
            "serialConnected": self._connected,
            "arduinoReachable": self._connected,
            "arduinoProtocolReady": protocol_ready,
            "virtualTransport": virtual_port,
            # Compatibility only for read-only legacy dashboards.
            "picoReachable": False,
            "port": self.active_port or self.port,
            "serialPort": self.active_port or self.port,
            "baudrate": self.baudrate,
            "busConnected": self._connected,
            "encoderOk": False,
            "mcuStatus": {
                "state": "IDLE" if protocol_ready else "UNKNOWN",
                "estopActive": True,
                "encoderOk": False,
                "fireReady": False,
                "faultCode": 0 if protocol_ready else 1,
            },
            "physicalOutputEnabled": bool(
                self.physical_output_capable
                and self._connected
                and protocol_ready
            ),
            "lastResponse": self._last_response,
            "lastError": self._last_error,
        }

    def health_check(self) -> dict[str, Any]:
        return self.health()
