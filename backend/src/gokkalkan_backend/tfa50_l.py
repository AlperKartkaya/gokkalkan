"""Benewake TFA50-L UART ranging-frame primitives.

This module deliberately contains no serial-port dependency. It validates and
decodes the sensor's four-byte ranging output so the same protocol code can be
used by unit tests, replay, a future pySerial adapter, and HIL tooling.
"""

from __future__ import annotations

from dataclasses import dataclass

TFA50L_FRAME_HEADER = 0x5C
TFA50L_FRAME_SIZE = 4
TFA50L_NO_DETECTION_CM = 0xFFFF
TFA50L_CONTROL_HEADER = 0x5A

TFA50L_READ_SERIAL_COMMAND = bytes.fromhex("5A 0D 02 0D 0D D6")
TFA50L_READ_FIRMWARE_COMMAND = bytes.fromhex("5A 16 02 16 16 BB")
TFA50L_STOP_RANGING_COMMAND = bytes.fromhex("5A 0A 02 00 00 F3")
TFA50L_START_RANGING_COMMAND = bytes.fromhex("5A 0A 02 02 00 F1")


class TFA50LFrameError(ValueError):
    """Raised when a TFA50-L ranging frame is malformed."""


@dataclass(frozen=True, slots=True)
class TFA50LMeasurement:
    """One validated ranging frame.

    ``distance_m`` is ``None`` for the device's 0xFFFF no-detection sentinel.
    The raw centimetre value is kept for lossless telemetry and replay.
    """

    distance_cm: int
    distance_m: float | None
    valid: bool
    no_detection: bool
    raw_frame: bytes


def ranging_checksum(distance_low: int, distance_high: int) -> int:
    """Return the datasheet checksum for two little-endian distance bytes."""

    return (~((distance_low + distance_high) & 0xFF)) & 0xFF


def control_checksum(payload_without_header: bytes) -> int:
    return (~(sum(payload_without_header) & 0xFF)) & 0xFF


def frequency_command(sample_hz: int) -> bytes:
    """Build the documented frequency-divisor command (20..20,000 Hz)."""

    if not 20 <= sample_hz <= 20_000:
        raise ValueError("TFA50-L sample frequency must be in 20..20000 Hz")
    divisor = round(1_000_000 / sample_hz - 1)
    if not 0 <= divisor <= 0xFFFF:
        raise ValueError("TFA50-L frequency divisor is out of range")
    body = bytes((0x0B, 0x02, divisor & 0xFF, divisor >> 8))
    return bytes((TFA50L_CONTROL_HEADER,)) + body + bytes((control_checksum(body),))


def parse_identity_response(frame: bytes, *, response_code: int) -> str:
    """Parse serial (0x8D) or firmware (0x96) six-byte response."""

    if len(frame) != 6 or frame[0] != TFA50L_CONTROL_HEADER:
        raise TFA50LFrameError("invalid identity response frame")
    if frame[1] != response_code or frame[2] != 0x02:
        raise TFA50LFrameError("unexpected identity response code")
    if frame[-1] != control_checksum(frame[1:-1]):
        raise TFA50LFrameError("invalid identity response checksum")
    low, high = frame[3], frame[4]
    if response_code == 0x8D:
        return f"S{(low | (high << 8)):05d}"
    if response_code == 0x96:
        return f"V{high}.{low}"
    raise TFA50LFrameError("unsupported identity response code")


def parse_measurement_frame(frame: bytes) -> TFA50LMeasurement:
    """Validate and decode one four-byte TFA50-L ranging output frame."""

    if len(frame) != TFA50L_FRAME_SIZE:
        raise TFA50LFrameError(
            f"invalid frame length: expected {TFA50L_FRAME_SIZE}, got {len(frame)}"
        )
    if frame[0] != TFA50L_FRAME_HEADER:
        raise TFA50LFrameError(
            f"invalid frame header: expected 0x{TFA50L_FRAME_HEADER:02X}, got 0x{frame[0]:02X}"
        )

    distance_low, distance_high, received_checksum = frame[1], frame[2], frame[3]
    expected_checksum = ranging_checksum(distance_low, distance_high)
    if received_checksum != expected_checksum:
        raise TFA50LFrameError(
            "invalid frame checksum: "
            f"expected 0x{expected_checksum:02X}, got 0x{received_checksum:02X}"
        )

    distance_cm = distance_low | (distance_high << 8)
    no_detection = distance_cm == TFA50L_NO_DETECTION_CM
    return TFA50LMeasurement(
        distance_cm=distance_cm,
        distance_m=None if no_detection else distance_cm / 100.0,
        valid=not no_detection,
        no_detection=no_detection,
        raw_frame=bytes(frame),
    )


class TFA50LStreamDecoder:
    """Incrementally recover validated ranging frames from arbitrary UART chunks."""

    def __init__(self) -> None:
        self._buffer = bytearray()
        self.rejected_frame_count = 0
        self.discarded_byte_count = 0
        self.last_rejections: list[dict[str, str]] = []

    def feed(self, chunk: bytes) -> list[TFA50LMeasurement]:
        """Append a byte chunk and return every complete valid protocol frame."""

        self._buffer.extend(chunk)
        measurements: list[TFA50LMeasurement] = []
        self.last_rejections = []

        while self._buffer:
            try:
                header_index = self._buffer.index(TFA50L_FRAME_HEADER)
            except ValueError:
                self.discarded_byte_count += len(self._buffer)
                self._buffer.clear()
                break

            if header_index:
                self.discarded_byte_count += header_index
                del self._buffer[:header_index]

            if len(self._buffer) < TFA50L_FRAME_SIZE:
                break

            candidate = bytes(self._buffer[:TFA50L_FRAME_SIZE])
            try:
                measurement = parse_measurement_frame(candidate)
            except TFA50LFrameError as exc:
                self.rejected_frame_count += 1
                self.last_rejections.append(
                    {"rawHex": candidate.hex(" ").upper(), "reason": str(exc)}
                )
                self.discarded_byte_count += 1
                del self._buffer[0]
                continue

            measurements.append(measurement)
            del self._buffer[:TFA50L_FRAME_SIZE]

        return measurements
