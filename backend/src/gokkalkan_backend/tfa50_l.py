"""Benewake TFA50-L & Benewake Standard UART (TFmini / TF-Luna / TFmini-Plus) ranging-frame primitives.

This module deliberately contains no serial-port dependency. It validates and
decodes the sensor's ranging output so the same protocol code can be
used by unit tests, replay, pySerial adapters, and HIL tooling.
"""

from __future__ import annotations

from dataclasses import dataclass

TFA50L_FRAME_HEADER = 0x5C
TFA50L_FRAME_SIZE = 4
TFA50L_NO_DETECTION_CM = 0xFFFF
TFA50L_CONTROL_HEADER = 0x5A

TFMINI_FRAME_HEADER_1 = 0x59
TFMINI_FRAME_HEADER_2 = 0x59
TFMINI_FRAME_SIZE = 9

TFA50L_READ_SERIAL_COMMAND = bytes.fromhex("5A 0D 02 0D 0D D6")
TFA50L_READ_FIRMWARE_COMMAND = bytes.fromhex("5A 16 02 16 16 BB")
TFA50L_STOP_RANGING_COMMAND = bytes.fromhex("5A 0A 02 00 00 F3")
TFA50L_START_RANGING_COMMAND = bytes.fromhex("5A 0A 02 02 00 F1")

# Standard Benewake TFmini / TF-Luna commands
TFMINI_SAMPLE_RATE_100HZ = bytes.fromhex("5A 06 03 64 00 C7")
TFMINI_RESTORE_FACTORY = bytes.fromhex("5A 04 10 6E")
TFMINI_SAVE_SETTINGS = bytes.fromhex("5A 04 11 6F")


class TFA50LFrameError(ValueError):
    """Raised when a TFA50-L or TFmini ranging frame is malformed."""


@dataclass(frozen=True, slots=True)
class TFA50LMeasurement:
    """One validated ranging frame from TFA50-L or TFmini/TF-Luna.

    ``distance_m`` is ``None`` for no-detection or out-of-range sentinels.
    The raw centimetre value and signal metrics are kept for lossless telemetry and replay.
    """

    distance_cm: int
    distance_m: float | None
    valid: bool
    no_detection: bool
    raw_frame: bytes
    signal_strength: int | None = None
    temperature_c: float | None = None
    protocol: str = "TFA50-L"


def ranging_checksum(distance_low: int, distance_high: int) -> int:
    """Return the datasheet checksum for two little-endian distance bytes."""
    return (~((distance_low + distance_high) & 0xFF)) & 0xFF


def tfmini_checksum(frame_8_bytes: bytes) -> int:
    """Return the Benewake 9-byte frame checksum (sum of first 8 bytes & 0xFF)."""
    return sum(frame_8_bytes) & 0xFF


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
        protocol="TFA50-L",
    )


def parse_tfmini_frame(frame: bytes) -> TFA50LMeasurement:
    """Validate and decode one standard 9-byte TFmini / TF-Luna / TFmini-Plus frame.
    
    Frame: [0x59] [0x59] [Dist_L] [Dist_H] [Strength_L] [Strength_H] [Temp_L] [Temp_H] [Checksum]
    """
    if len(frame) != TFMINI_FRAME_SIZE:
        raise TFA50LFrameError(
            f"invalid TFmini frame length: expected {TFMINI_FRAME_SIZE}, got {len(frame)}"
        )
    if frame[0] != TFMINI_FRAME_HEADER_1 or frame[1] != TFMINI_FRAME_HEADER_2:
        raise TFA50LFrameError(
            f"invalid TFmini frame header: expected 0x59 0x59, got 0x{frame[0]:02X} 0x{frame[1]:02X}"
        )

    expected_cs = tfmini_checksum(frame[:8])
    if frame[8] != expected_cs:
        raise TFA50LFrameError(
            f"invalid TFmini checksum: expected 0x{expected_cs:02X}, got 0x{frame[8]:02X}"
        )

    dist_cm = frame[2] | (frame[3] << 8)
    strength = frame[4] | (frame[5] << 8)
    temp_raw = frame[6] | (frame[7] << 8)
    temp_c = (temp_raw / 8.0) - 256.0 if temp_raw != 0 else None

    # TFmini / TF-Luna: dist_cm == 0, 0xFFFF (-1 signed 16-bit), or 65535 or strength <= 0 indicates no target
    no_detection = (dist_cm == 0) or (dist_cm == 0xFFFF) or (strength == 0 and dist_cm > 1200)
    valid = not no_detection and dist_cm > 0

    return TFA50LMeasurement(
        distance_cm=dist_cm,
        distance_m=dist_cm / 100.0 if valid else None,
        valid=valid,
        no_detection=no_detection,
        raw_frame=bytes(frame),
        signal_strength=strength,
        temperature_c=round(temp_c, 1) if temp_c is not None else None,
        protocol="TF-Luna/TFmini",
    )


class TFA50LStreamDecoder:
    """Incrementally recover validated ranging frames from arbitrary UART chunks.
    
    Supports 4-byte TFA50-L frames (0x5C) and standard 9-byte Benewake frames (0x59 0x59).
    """

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
            header_5c = self._buffer.find(TFA50L_FRAME_HEADER)
            header_59 = self._buffer.find(b"\x59\x59")

            if header_5c == -1 and header_59 == -1:
                self.discarded_byte_count += len(self._buffer)
                self._buffer.clear()
                break

            candidates_idx = [i for i in (header_5c, header_59) if i != -1]
            earliest_header = min(candidates_idx)

            if earliest_header > 0:
                self.discarded_byte_count += earliest_header
                del self._buffer[:earliest_header]

            # 1. 4-Bayt TFA50-L Çerçevesi (0x5C)
            if self._buffer[0] == TFA50L_FRAME_HEADER:
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

            # 2. 9-Bayt Benewake TFmini / TF-Luna Çerçevesi (0x59 0x59)
            elif len(self._buffer) >= 2 and self._buffer[:2] == b"\x59\x59":
                if len(self._buffer) < TFMINI_FRAME_SIZE:
                    break

                candidate = bytes(self._buffer[:TFMINI_FRAME_SIZE])
                try:
                    measurement = parse_tfmini_frame(candidate)
                except TFA50LFrameError as exc:
                    self.rejected_frame_count += 1
                    self.last_rejections.append(
                        {"rawHex": candidate.hex(" ").upper(), "reason": str(exc)}
                    )
                    self.discarded_byte_count += 1
                    del self._buffer[0]
                    continue

                measurements.append(measurement)
                del self._buffer[:TFMINI_FRAME_SIZE]

            else:
                del self._buffer[0]

        # Prevent runaway buffer growth
        if len(self._buffer) > 2048:
            self.discarded_byte_count += len(self._buffer)
            self._buffer.clear()

        return measurements


# Alias for universal Benewake decoder
UniversalLidarDecoder = TFA50LStreamDecoder

