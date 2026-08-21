"""Reconnect-capable TFA50-L & TFmini/TF-Luna UART adapter with explicit health and telemetry."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import glob
import time
from typing import Any, Callable, Protocol

from .range_fusion import TimedRange
from .tfa50_l import TFA50LStreamDecoder
from .tfa50_l import (
    TFA50L_READ_FIRMWARE_COMMAND,
    TFA50L_READ_SERIAL_COMMAND,
    TFA50L_START_RANGING_COMMAND,
    TFA50L_STOP_RANGING_COMMAND,
    frequency_command,
    parse_identity_response,
)


class SerialLike(Protocol):
    def read(self, size: int = ...) -> bytes: ...
    def write(self, data: bytes) -> int: ...
    def close(self) -> None: ...


@dataclass(frozen=True, slots=True)
class TFA50LSerialConfig:
    port: str
    baud_rate: int
    sample_hz: int
    stale_ms: int
    reconnect_ms: int = 500
    read_size: int = 64
    serial_number: str = "UNVERIFIED"
    firmware_version: str = "UNVERIFIED"
    initialize_device: bool = True


class TFA50LSerialAdapter:
    BAUD_CANDIDATES = (115200, 460800, 921600, 9600, 57600)

    def __init__(
        self,
        config: TFA50LSerialConfig,
        *,
        serial_factory: Callable[..., SerialLike] | None = None,
        telemetry: Callable[[str, dict[str, Any]], None] | None = None,
        monotonic_ns: Callable[[], int] = time.monotonic_ns,
    ) -> None:
        self.config = config
        self._factory = serial_factory or self._default_serial_factory
        self._telemetry = telemetry or (lambda _kind, _payload: None)
        self._clock = monotonic_ns
        self._decoder = TFA50LStreamDecoder()
        self._serial: SerialLike | None = None
        self._last_connect_attempt_ns = -(config.reconnect_ms * 1_000_000)
        self._last_receive_ns: int | None = None
        self._last_error: str | None = None
        self._reconnect_count = 0
        self._serial_number = config.serial_number
        self._firmware_version = config.firmware_version
        self._active_baud = config.baud_rate
        self._active_port = config.port
        self._baud_search_idx = 0
        self._baud_switch_attempt_ns = 0

    @staticmethod
    def _default_serial_factory(**kwargs: Any) -> SerialLike:
        import serial
        import serial.tools.list_ports

        port = kwargs.get("port")
        try:
            return serial.Serial(**kwargs)
        except Exception:
            # Cross-platform fallback for COM / USB / ttyAMA ports
            ports = list(serial.tools.list_ports.comports())
            candidates = []
            for p in ports:
                desc = (p.description or "").lower()
                dev = p.device
                if any(x in desc or x in dev.lower() for x in ["cp210", "ftdi", "ch340", "ch341", "uart", "usb", "com", "ttyusb", "ttyacm"]):
                    candidates.append(dev)

            # Linux paths
            linux_paths = sorted(
                glob.glob("/dev/serial/by-id/*")
                + glob.glob("/dev/ttyUSB*")
                + glob.glob("/dev/ttyACM*")
                + glob.glob("/dev/ttyAMA*")
                + glob.glob("/dev/serial0")
            )
            for lp in linux_paths:
                if lp not in candidates:
                    candidates.append(lp)

            for dev in candidates:
                if dev != port:
                    try:
                        kwargs["port"] = dev
                        return serial.Serial(**kwargs)
                    except Exception:
                        continue
            raise

    def _connect(self) -> bool:
        now = self._clock()
        if now - self._last_connect_attempt_ns < self.config.reconnect_ms * 1_000_000:
            return False
        self._last_connect_attempt_ns = now

        # Try configured baud first, then scan candidates
        baud_order = [self._active_baud] + [
            b for b in self.BAUD_CANDIDATES if b != self._active_baud
        ]
        timeout_val = max(0.02, 2.0 / max(1, self.config.sample_hz))

        for baud in baud_order:
            try:
                self._serial = self._factory(
                    port=self._active_port,
                    baudrate=baud,
                    timeout=timeout_val,
                )
                self._active_baud = baud
                self._last_error = None
                self._reconnect_count += 1
                if self.config.initialize_device:
                    self._initialize_device()
                self._telemetry("lidar_connected", self.manifest())
                return True
            except (OSError, ValueError):
                self._serial = None
                continue

        self._last_error = "ALL_BAUD_CANDIDATES_FAILED"
        self._telemetry("lidar_connection_error", {"error": self._last_error})
        return False

    def _read_control_response(self, response_code: int) -> bytes:
        buffer = bytearray()
        assert self._serial is not None
        for _ in range(8):
            buffer.extend(self._serial.read(self.config.read_size))
            for index in range(max(0, len(buffer) - 5)):
                candidate = bytes(buffer[index : index + 6])
                if (
                    len(candidate) == 6
                    and candidate[0] == 0x5A
                    and candidate[1] == response_code
                ):
                    return candidate
        raise OSError(f"TFA50-L control response 0x{response_code:02X} timed out")

    def _initialize_device(self) -> None:
        """Attempt TFA50-L initialization if possible, fully non-fatal for TFmini/TF-Luna."""
        if self._serial is None:
            return
        try:
            self._serial.write(TFA50L_STOP_RANGING_COMMAND)
            self._read_control_response(0x8A)
            self._serial.write(TFA50L_READ_SERIAL_COMMAND)
            self._serial_number = parse_identity_response(
                self._read_control_response(0x8D), response_code=0x8D
            )
            self._serial.write(TFA50L_READ_FIRMWARE_COMMAND)
            self._firmware_version = parse_identity_response(
                self._read_control_response(0x96), response_code=0x96
            )
            frequency = frequency_command(self.config.sample_hz)
            self._serial.write(frequency)
            self._read_control_response(0x8B)
        except Exception as exc:
            # TFmini / TF-Luna / passive stream sensors do not acknowledge TFA50-L 0x5A commands
            # This is expected and non-fatal — the sensor will still stream distance data
            self._telemetry("lidar_identity_info", {"note": f"Passive stream or TFmini detected: {exc}"})
        try:
            if self._serial is not None:
                self._serial.write(TFA50L_START_RANGING_COMMAND)
        except Exception:
            pass

    def poll(self) -> list[TimedRange]:
        if self._serial is None and not self._connect():
            return []
        assert self._serial is not None
        try:
            chunk = self._serial.read(self.config.read_size)
        except (OSError, ValueError) as exc:
            self._last_error = f"{type(exc).__name__}:{exc}"
            try:
                self._serial.close()
            finally:
                self._serial = None
            self._telemetry("lidar_disconnected", {"error": self._last_error})
            return []

        now = self._clock()
        measurements = self._decoder.feed(chunk)
        events: list[TimedRange] = []

        # If data is flowing and measurements are found, clear errors
        if measurements:
            self._last_error = None
            self._last_receive_ns = now

        for rejected in self._decoder.last_rejections:
            invalid = TimedRange(
                None, now, rejected["rawHex"], False, "CHECKSUM_OR_FRAME_INVALID"
            )
            events.append(invalid)
            self._telemetry("lidar_measurement", asdict(invalid))

        for measurement in measurements:
            event = TimedRange(
                distance_m=measurement.distance_m,
                receive_monotonic_ns=now,
                raw_hex=measurement.raw_frame.hex(" ").upper(),
                valid=measurement.valid,
                reason="VALID" if measurement.valid else "NO_DETECTION",
            )
            events.append(event)
            self._telemetry("lidar_measurement", asdict(event))

        return events

    def close(self) -> None:
        if self._serial is not None:
            self._serial.close()
            self._serial = None

    def manifest(self) -> dict[str, Any]:
        return {
            "adapter": "tfa50-l-uart",
            "port": self._active_port,
            "baudRate": self._active_baud,
            "sampleHz": self.config.sample_hz,
            "serialNumber": self._serial_number,
            "firmwareVersion": self._firmware_version,
        }

    def health(self) -> dict[str, Any]:
        now = self._clock()
        age_ms = (
            None
            if self._last_receive_ns is None
            else max(0.0, (now - self._last_receive_ns) / 1_000_000)
        )
        stale = age_ms is None or age_ms > self.config.stale_ms
        return {
            "connected": self._serial is not None,
            "healthy": self._serial is not None and not stale and self._last_error is None,
            "stale": stale,
            "ageMs": age_ms,
            "lastError": self._last_error,
            "reconnectCount": self._reconnect_count,
            "rejectedFrames": self._decoder.rejected_frame_count,
            **self.manifest(),
        }


def probe_tfa50l_uart(
    port: str,
    baud_rate: int = 460_800,
    timeout_sec: float = 2.0,
    *,
    read_size: int = 64,
    serial_factory: Callable[..., SerialLike] | None = None,
    monotonic: Callable[[], float] = time.monotonic,
) -> dict[str, Any]:
    """Read TFA50-L / TFmini measurement frames without transmitting any UART command.

    This is intentionally a receive-only wiring/baud diagnostic. It never
    changes LiDAR configuration, starts ranging, or enables physical outputs.
    """
    if timeout_sec <= 0:
        raise ValueError("timeout_sec must be positive")
    if read_size <= 0:
        raise ValueError("read_size must be positive")

    factory = serial_factory or TFA50LSerialAdapter._default_serial_factory
    decoder = TFA50LStreamDecoder()
    serial_port = factory(port=port, baudrate=baud_rate, timeout=0.1)
    valid_frames: list[dict[str, Any]] = []
    invalid_frames = 0
    deadline = monotonic() + timeout_sec
    try:
        while monotonic() < deadline:
            chunk = serial_port.read(read_size)
            for measurement in decoder.feed(chunk):
                if measurement.valid:
                    valid_frames.append(
                        {
                            "distanceM": measurement.distance_m,
                            "rawHex": measurement.raw_frame.hex(" ").upper(),
                        }
                    )
                else:
                    invalid_frames += 1
            invalid_frames += len(decoder.last_rejections)
    finally:
        serial_port.close()

    return {
        "mode": "RECEIVE_ONLY",
        "port": port,
        "baudRate": baud_rate,
        "timeoutSec": timeout_sec,
        "validFrameCount": len(valid_frames),
        "invalidFrameCount": invalid_frames,
        "lastMeasurement": valid_frames[-1] if valid_frames else None,
        "ok": bool(valid_frames),
    }

