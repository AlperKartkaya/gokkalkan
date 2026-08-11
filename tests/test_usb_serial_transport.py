from __future__ import annotations

from types import SimpleNamespace

import pytest

from gokkalkan_backend.can_protocol import (
    CAN_ID_ACK_V1,
    CAN_ID_HEARTBEAT_V1,
    CAN_ID_STATUS_V1,
    command_tag,
    pack_ack,
    pack_status,
)
from gokkalkan_backend.usb_serial_adapter import UsbSerialMcuAdapter
from gokkalkan_backend.usb_serial_protocol import (
    UsbFrameError,
    UsbFrameStreamDecoder,
    decode_usb_frame,
    encode_usb_frame,
)


class FakeSerial:
    def __init__(self, reads: list[bytes] | None = None, **_: object) -> None:
        self.reads = list(reads or [])
        self.writes: list[bytes] = []
        self.closed = False

    def read(self, _size: int) -> bytes:
        return self.reads.pop(0) if self.reads else b""

    def write(self, data: bytes) -> int:
        self.writes.append(bytes(data))
        return len(data)

    def close(self) -> None:
        self.closed = True


def test_usb_frame_roundtrip_preserves_message_id_and_payload() -> None:
    payload = bytes((1, 0, 2, 0, 3, 4, 5, 6))
    encoded = encode_usb_frame(CAN_ID_STATUS_V1, payload)
    assert encoded.endswith(b"\x00")
    assert decode_usb_frame(encoded) == (CAN_ID_STATUS_V1, payload)


def test_usb_frame_rejects_corruption() -> None:
    encoded = bytearray(encode_usb_frame(CAN_ID_STATUS_V1, b"12345678"))
    encoded[4] ^= 0x40
    with pytest.raises(UsbFrameError):
        decode_usb_frame(bytes(encoded))


def test_stream_decoder_handles_partial_and_multiple_frames() -> None:
    first = encode_usb_frame(0x200, b"abcdefgh")
    second = encode_usb_frame(0x201, b"x")
    decoder = UsbFrameStreamDecoder()
    assert decoder.feed(first[:4]) == []
    assert decoder.feed(first[4:] + second) == [(0x200, b"abcdefgh"), (0x201, b"x")]


def test_stream_decoder_drops_oversized_garbage_and_recovers() -> None:
    decoder = UsbFrameStreamDecoder(max_encoded_size=20)
    assert decoder.feed(b"x" * 30 + b"\x00") == []
    assert decoder.rejected_count >= 1
    assert decoder.feed(encode_usb_frame(0x201, b"\x01")) == [(0x201, b"\x01")]


def test_usb_adapter_dry_run_never_enables_physical_output() -> None:
    adapter = UsbSerialMcuAdapter(dry_run=True)
    adapter.start()
    result = adapter.execute(
        {
            "commandId": "USB-DRY",
            "kind": "ManualAimCommand",
            "payload": {"panDeltaDeg": 1.0, "tiltDeltaDeg": 0.0},
        }
    )
    assert result["accepted"] is True
    assert result["physicalOutput"] is False
    assert result["adapter"] == "usb_serial_mcu_adapter"


def test_usb_adapter_sends_framed_v1_transaction_and_requires_matching_ack() -> None:
    serial = FakeSerial()

    class AckingUsbAdapter(UsbSerialMcuAdapter):
        def _send_can(self, message_id: int, data: bytes) -> bool:
            sent = super()._send_can(message_id, data)
            if sent and message_id not in {0x10F, 0x120}:
                from gokkalkan_backend.can_protocol import unpack_command_meta

                meta_id, meta_payload = next(
                    decode_usb_frame(item)
                    for item in serial.writes
                    if decode_usb_frame(item)[0] == 0x10F
                )
                assert meta_id == 0x10F
                meta = unpack_command_meta(meta_payload)
                assert meta
                self._handle_rx_message(
                    SimpleNamespace(
                        arbitration_id=CAN_ID_ACK_V1,
                        data=pack_ack(
                            int(meta["sequence"]),
                            int(meta["commandTag"]),
                            0,
                            2,
                        ),
                    )
                )
            return sent

    adapter = AckingUsbAdapter(
        port="loop://",
        dry_run=False,
        physical_output_capable=False,
        serial_factory=lambda **_: serial,
    )
    adapter.start()
    result = adapter.execute(
        {"commandId": "USB-ACK", "kind": "SysCmd", "payload": {"arm": False}}
    )
    assert result["accepted"] is True
    assert result["resultCode"] == "ACK"
    assert result["physicalOutput"] is False
    assert len(serial.writes) >= 2
    adapter.close()


def test_usb_adapter_updates_health_from_framed_status() -> None:
    adapter = UsbSerialMcuAdapter(dry_run=True)
    message_id, payload = decode_usb_frame(
        encode_usb_frame(CAN_ID_STATUS_V1, pack_status(1, 2, 0x0A, 0, 7, 1))
    )
    adapter._handle_rx_message(SimpleNamespace(arbitration_id=message_id, data=payload))
    health = adapter.health_check()
    assert health["adapter"] == "usb_serial_mcu_adapter"
    assert health["mcuStatus"]["state"] == "READY"
    assert health["transport"] == "usb_serial"


def test_physical_usb_write_is_blocked_without_output_capability() -> None:
    serial = FakeSerial()
    adapter = UsbSerialMcuAdapter(
        port="/dev/ttyACM0",
        dry_run=False,
        physical_output_capable=False,
        serial_factory=lambda **_: serial,
    )
    adapter._open_serial()
    assert adapter._send_can(CAN_ID_HEARTBEAT_V1, b"12345678") is True
    assert adapter._send_can(0x102, b"12345678") is False
    assert len(serial.writes) == 1
    assert decode_usb_frame(serial.writes[0]) == (CAN_ID_HEARTBEAT_V1, b"12345678")
    adapter.close()
