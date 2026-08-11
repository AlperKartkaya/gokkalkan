"""Framed USB-CDC transport for the existing MCU protocol payloads.

USB CDC is a byte stream, so it does not preserve the message boundaries that
CAN provided.  Each packet therefore carries the former 11-bit message id and
its payload inside a versioned, CRC-16 protected COBS frame terminated by NUL.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass, field
from typing import Final

USB_TRANSPORT_VERSION: Final = 1
MAX_PAYLOAD_SIZE: Final = 64
FRAME_DELIMITER: Final = 0


class UsbFrameError(ValueError):
    """Raised when a USB transport frame is malformed or corrupt."""


def crc16_ccitt(data: bytes) -> int:
    crc = 0xFFFF
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) & 0xFFFF if crc & 0x8000 else (crc << 1) & 0xFFFF
    return crc


def cobs_encode(data: bytes) -> bytes:
    output = bytearray((0,))
    code_index = 0
    code = 1
    for byte in data:
        if byte == 0:
            output[code_index] = code
            code_index = len(output)
            output.append(0)
            code = 1
        else:
            output.append(byte)
            code += 1
            if code == 0xFF:
                output[code_index] = code
                code_index = len(output)
                output.append(0)
                code = 1
    output[code_index] = code
    return bytes(output)


def cobs_decode(data: bytes) -> bytes:
    if not data:
        raise UsbFrameError("empty COBS frame")
    output = bytearray()
    index = 0
    while index < len(data):
        code = data[index]
        if code == 0:
            raise UsbFrameError("zero byte inside COBS frame")
        index += 1
        end = index + code - 1
        if end > len(data):
            raise UsbFrameError("truncated COBS frame")
        output.extend(data[index:end])
        index = end
        if code != 0xFF and index < len(data):
            output.append(0)
    return bytes(output)


def encode_usb_frame(message_id: int, payload: bytes) -> bytes:
    if not 0 <= message_id <= 0x7FF:
        raise ValueError("message_id must fit the existing 11-bit protocol space")
    if not 0 <= len(payload) <= MAX_PAYLOAD_SIZE:
        raise ValueError("USB payload is too large")
    body = struct.pack(">BHB", USB_TRANSPORT_VERSION, message_id, len(payload)) + payload
    packet = body + struct.pack(">H", crc16_ccitt(body))
    return cobs_encode(packet) + bytes((FRAME_DELIMITER,))


def decode_usb_frame(frame: bytes) -> tuple[int, bytes]:
    packet = cobs_decode(frame[:-1] if frame.endswith(b"\x00") else frame)
    if len(packet) < 6:
        raise UsbFrameError("USB frame is too short")
    body, received_crc = packet[:-2], struct.unpack(">H", packet[-2:])[0]
    if crc16_ccitt(body) != received_crc:
        raise UsbFrameError("USB frame CRC mismatch")
    version, message_id, size = struct.unpack(">BHB", body[:4])
    payload = body[4:]
    if version != USB_TRANSPORT_VERSION:
        raise UsbFrameError("unsupported USB transport version")
    if message_id > 0x7FF or size != len(payload) or size > MAX_PAYLOAD_SIZE:
        raise UsbFrameError("invalid USB frame header")
    return message_id, payload


@dataclass(slots=True)
class UsbFrameStreamDecoder:
    """Incrementally split a serial byte stream into validated frames."""

    max_encoded_size: int = 128
    rejected_count: int = 0
    _buffer: bytearray = field(default_factory=bytearray)

    def feed(self, chunk: bytes) -> list[tuple[int, bytes]]:
        frames: list[tuple[int, bytes]] = []
        for byte in chunk:
            if byte == FRAME_DELIMITER:
                if self._buffer:
                    try:
                        frames.append(decode_usb_frame(bytes(self._buffer)))
                    except UsbFrameError:
                        self.rejected_count += 1
                    self._buffer.clear()
                continue
            self._buffer.append(byte)
            if len(self._buffer) > self.max_encoded_size:
                self._buffer.clear()
                self.rejected_count += 1
        return frames
