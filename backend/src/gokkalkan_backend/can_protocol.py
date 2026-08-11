"""Gökkalkan MCU v1 payload codec (tarihsel klasik CAN yerleşimi).

Every frame is exactly eight bytes and CRC-8 protected. Commands use a META
frame followed by a payload frame carrying the same sequence. The 16-bit
command tag is a stable correlation value; the full command id remains in
backend telemetry. Active physical transport wraps these payloads in the USB
CDC/COBS/CRC16 envelope defined by ``usb_serial_protocol``.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import struct
from typing import Final

PROTOCOL_VERSION: Final = 1
CAN_ID_COMMAND_META: Final = 0x10F
CAN_ID_PANTILT_CMD_V1: Final = 0x110
CAN_ID_FIRE_CMD_V1: Final = 0x111
CAN_ID_SYS_CMD_V1: Final = 0x112
CAN_ID_HEARTBEAT_V1: Final = 0x120
CAN_ID_STATUS_V1: Final = 0x200
CAN_ID_ESTOP_V1: Final = 0x201
CAN_ID_FIRMWARE_V1: Final = 0x202
CAN_ID_ENCODER_V1: Final = 0x203
CAN_ID_FAULT_V1: Final = 0x204
CAN_ID_ACK_V1: Final = 0x210

KIND_PANTILT: Final = 1
KIND_FIRE: Final = 2
KIND_SYSTEM: Final = 3

STATE_NAMES: Final = {
    0: "BOOT",
    1: "SAFE",
    2: "READY",
    3: "ARMED",
    4: "FIRING",
    5: "FAULT",
}
ACK_RESULTS: Final = {0: "ACK", 1: "NACK_STATE", 2: "NACK_CRC", 3: "NACK_SEQUENCE", 4: "NACK_COMMAND"}


def crc8(data: bytes) -> int:
    """CRC-8/ATM (poly=0x07, init=0x00, no reflection)."""

    crc = 0
    for byte in data:
        crc ^= byte
        for _ in range(8):
            crc = ((crc << 1) ^ 0x07) & 0xFF if crc & 0x80 else (crc << 1) & 0xFF
    return crc


def _frame(body: bytes) -> bytes:
    if len(body) != 7:
        raise ValueError("CAN v1 body must be seven bytes")
    return body + bytes((crc8(body),))


def _body(frame: bytes) -> bytes | None:
    if len(frame) != 8 or frame[-1] != crc8(frame[:-1]):
        return None
    return frame[:-1]


def command_tag(command_id: str) -> int:
    return int.from_bytes(hashlib.blake2s(command_id.encode(), digest_size=2).digest(), "big")


def pack_command_meta(sequence: int, command_id: str, kind: int, flags: int = 0) -> bytes:
    return _frame(struct.pack(">BBHBBB", PROTOCOL_VERSION, sequence & 0xFF, command_tag(command_id), kind & 0xFF, flags & 0xFF, 0))


def unpack_command_meta(frame: bytes) -> dict[str, int] | None:
    body = _body(frame)
    if body is None:
        return None
    version, sequence, tag, kind, flags, _reserved = struct.unpack(">BBHBBB", body)
    if version != PROTOCOL_VERSION:
        return None
    return {"version": version, "sequence": sequence, "commandTag": tag, "kind": kind, "flags": flags}


def pack_pantilt(sequence: int, pan_centideg: int, tilt_centideg: int) -> bytes:
    return _frame(struct.pack(">BBhhB", PROTOCOL_VERSION, sequence & 0xFF, pan_centideg, tilt_centideg, 0))


def unpack_pantilt(frame: bytes) -> dict[str, int] | None:
    body = _body(frame)
    if body is None:
        return None
    version, sequence, pan, tilt, _reserved = struct.unpack(">BBhhB", body)
    if version != PROTOCOL_VERSION:
        return None
    return {"sequence": sequence, "panCentideg": pan, "tiltCentideg": tilt}


def pack_fire(sequence: int, fire: bool, stage: int) -> bytes:
    return _frame(bytes((PROTOCOL_VERSION, sequence & 0xFF, int(fire), stage & 0xFF, 0, 0, 0)))


def unpack_fire(frame: bytes) -> dict[str, object] | None:
    body = _body(frame)
    if body is None or body[0] != PROTOCOL_VERSION or body[2] not in {0, 1} or body[3] not in {1, 2, 3}:
        return None
    return {"sequence": body[1], "fire": bool(body[2]), "stage": body[3]}


def pack_system(sequence: int, operation: int) -> bytes:
    """operation: 0=disarm, 1=arm, 2=soft-stop, 3=controlled-reset."""

    return _frame(bytes((PROTOCOL_VERSION, sequence & 0xFF, operation & 0xFF, 0, 0, 0, 0)))


def pack_heartbeat(sequence: int) -> bytes:
    return _frame(bytes((PROTOCOL_VERSION, sequence & 0xFF, 0, 0, 0, 0, 0)))


def unpack_heartbeat(frame: bytes) -> dict[str, int] | None:
    body = _body(frame)
    if body is None or body[0] != PROTOCOL_VERSION or any(body[2:]):
        return None
    return {"sequence": body[1]}


def unpack_system(frame: bytes) -> dict[str, int] | None:
    body = _body(frame)
    if body is None or body[0] != PROTOCOL_VERSION or body[2] not in {0, 1, 2, 3}:
        return None
    return {"sequence": body[1], "operation": body[2]}


def pack_status(sequence: int, state: int, flags: int, fault: int, encoder_flags: int, fw_major: int) -> bytes:
    return _frame(bytes((PROTOCOL_VERSION, sequence & 0xFF, state & 0xFF, flags & 0xFF, fault & 0xFF, encoder_flags & 0xFF, fw_major & 0xFF)))


def unpack_status(frame: bytes) -> dict[str, object] | None:
    body = _body(frame)
    if body is None or body[0] != PROTOCOL_VERSION or body[2] not in STATE_NAMES:
        return None
    return {
        "protocolVersion": body[0],
        "sequence": body[1],
        "state": STATE_NAMES[body[2]],
        "estopActive": bool(body[3] & 0x01),
        "motionOk": bool(body[3] & 0x02),
        "fireReady": bool(body[3] & 0x04),
        "watchdogOk": bool(body[3] & 0x08),
        "faultCode": body[4],
        "encoderFlags": body[5],
        "firmwareMajor": body[6],
    }


def pack_firmware(sequence: int, major: int, minor: int, patch: int) -> bytes:
    return _frame(bytes((PROTOCOL_VERSION, sequence & 0xFF, major & 0xFF, minor & 0xFF, patch & 0xFF, PROTOCOL_VERSION, 0)))


def unpack_firmware(frame: bytes) -> dict[str, object] | None:
    body = _body(frame)
    if body is None or body[0] != PROTOCOL_VERSION or body[5] != PROTOCOL_VERSION:
        return None
    return {
        "sequence": body[1],
        "firmwareVersion": f"{body[2]}.{body[3]}.{body[4]}",
        "protocolVersion": body[5],
    }


def pack_estop(sequence: int, active: bool, reason: int = 0) -> bytes:
    return _frame(bytes((PROTOCOL_VERSION, sequence & 0xFF, int(active), reason & 0xFF, 0, 0, 0)))


def unpack_estop(frame: bytes) -> dict[str, object] | None:
    body = _body(frame)
    if body is None or body[0] != PROTOCOL_VERSION or body[2] not in {0, 1}:
        return None
    return {"sequence": body[1], "active": bool(body[2]), "reason": body[3]}


def pack_fault(sequence: int, fault: int, detail: int = 0) -> bytes:
    return _frame(bytes((PROTOCOL_VERSION, sequence & 0xFF, fault & 0xFF, detail & 0xFF, 0, 0, 0)))


def unpack_fault(frame: bytes) -> dict[str, int] | None:
    body = _body(frame)
    if body is None or body[0] != PROTOCOL_VERSION:
        return None
    return {"sequence": body[1], "fault": body[2], "detail": body[3]}


def pack_encoder(sequence: int, pan_centideg: int, tilt_centideg: int, flags: int = 0) -> bytes:
    return _frame(struct.pack(">BBhhB", PROTOCOL_VERSION, sequence & 0xFF, pan_centideg, tilt_centideg, flags & 0xFF))


def unpack_encoder(frame: bytes) -> dict[str, object] | None:
    body = _body(frame)
    if body is None:
        return None
    version, sequence, pan, tilt, flags = struct.unpack(">BBhhB", body)
    if version != PROTOCOL_VERSION:
        return None
    return {
        "sequence": sequence,
        "panDeg": pan / 100.0,
        "tiltDeg": tilt / 100.0,
        "flags": flags,
        "zeroReferenced": bool(flags & 0x01),
        "directionOk": bool(flags & 0x02),
        "connected": bool(flags & 0x04),
        "overflow": bool(flags & 0x08),
        "deviationFault": bool(flags & 0x10),
    }


def pack_ack(sequence: int, tag: int, result: int, state: int) -> bytes:
    return _frame(struct.pack(">BBHBBB", PROTOCOL_VERSION, sequence & 0xFF, tag & 0xFFFF, result & 0xFF, state & 0xFF, 0))


def unpack_ack(frame: bytes) -> dict[str, object] | None:
    body = _body(frame)
    if body is None:
        return None
    version, sequence, tag, result, state, _reserved = struct.unpack(">BBHBBB", body)
    if version != PROTOCOL_VERSION or result not in ACK_RESULTS or state not in STATE_NAMES:
        return None
    return {"sequence": sequence, "commandTag": tag, "result": ACK_RESULTS[result], "state": STATE_NAMES[state]}


@dataclass(slots=True)
class SequenceGuard:
    last: int | None = None

    def accept(self, sequence: int) -> bool:
        sequence &= 0xFF
        if self.last is None:
            self.last = sequence
            return True
        delta = (sequence - self.last) & 0xFF
        if not 1 <= delta <= 127:
            return False
        self.last = sequence
        return True
