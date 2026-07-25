from __future__ import annotations

import csv
import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

pytestmark = pytest.mark.protocol

from gokkalkan_backend.can_protocol import (
    CAN_ID_ENCODER_V1,
    CAN_ID_FIRMWARE_V1,
    SequenceGuard,
    command_tag,
    pack_ack,
    pack_command_meta,
    pack_encoder,
    pack_estop,
    pack_fault,
    pack_firmware,
    pack_fire,
    pack_pantilt,
    pack_status,
    pack_system,
    unpack_ack,
    unpack_command_meta,
    unpack_encoder,
    unpack_estop,
    unpack_fault,
    unpack_firmware,
    unpack_fire,
    unpack_pantilt,
    unpack_status,
    unpack_system,
)
from gokkalkan_backend.hardware_adapter import CanMcuAdapter

ROOT = Path(__file__).resolve().parents[1]
MODEL_PATH = ROOT / "backend/hardware_mock/firmware_model.py"
spec = importlib.util.spec_from_file_location("firmware_model", MODEL_PATH)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)
FirmwareModel = module.FirmwareModel


def test_v1_roundtrips_and_crc_rejection() -> None:
    meta = pack_command_meta(7, "CMD-1", 1, 1)
    assert unpack_command_meta(meta) == {
        "version": 1, "sequence": 7, "commandTag": command_tag("CMD-1"), "kind": 1, "flags": 1
    }
    assert unpack_pantilt(pack_pantilt(7, 125, -250)) == {
        "sequence": 7, "panCentideg": 125, "tiltCentideg": -250
    }
    assert unpack_fire(pack_fire(7, True, 3)) == {"sequence": 7, "fire": True, "stage": 3}
    assert unpack_system(pack_system(7, 2)) == {"sequence": 7, "operation": 2}
    damaged = bytearray(pack_status(1, 3, 0x0E, 0, 7, 1))
    damaged[4] ^= 1
    assert unpack_status(bytes(damaged)) is None


def test_status_firmware_encoder_and_ack_contract() -> None:
    status = unpack_status(pack_status(9, 3, 0x0E, 0, 7, 1))
    assert status and status["state"] == "ARMED" and status["watchdogOk"]
    assert unpack_firmware(pack_firmware(1, 1, 2, 3))["firmwareVersion"] == "1.2.3"  # type: ignore[index]
    encoder = unpack_encoder(pack_encoder(2, 100, -200, 0x07))
    assert encoder and encoder["connected"] and encoder["zeroReferenced"]
    ack = unpack_ack(pack_ack(7, command_tag("CMD-1"), 0, 3))
    assert ack and ack["result"] == "ACK" and ack["state"] == "ARMED"
    assert unpack_estop(pack_estop(3, True, 2)) == {"sequence": 3, "active": True, "reason": 2}
    assert unpack_fault(pack_fault(4, 9, 1)) == {"sequence": 4, "fault": 9, "detail": 1}


def test_backend_health_exposes_firmware_and_encoder_feedback() -> None:
    adapter = CanMcuAdapter(dry_run=True)
    adapter._handle_rx_message(
        SimpleNamespace(arbitration_id=CAN_ID_FIRMWARE_V1, data=pack_firmware(1, 1, 2, 3))
    )
    adapter._handle_rx_message(
        SimpleNamespace(arbitration_id=CAN_ID_ENCODER_V1, data=pack_encoder(1, 100, -200, 0x07))
    )
    health = adapter.health_check()
    assert health["firmwareVersion"] == "1.2.3"
    assert health["protocolVersion"] == 1
    assert health["encoderOk"] is True


def test_live_v1_command_fails_closed_without_matching_ack() -> None:
    adapter = CanMcuAdapter(dry_run=False, physical_output_capable=True)
    result = adapter.execute(
        {"commandId": "CMD-TIMEOUT", "kind": "SysCmd", "payload": {"arm": True}}
    )
    assert result["accepted"] is False
    assert result["resultCode"] == "ACK_TIMEOUT"
    assert result["physicalOutput"] is False


def test_live_v1_command_accepts_only_matching_ack() -> None:
    class AckingAdapter(CanMcuAdapter):
        def _send_can(self, can_id: int, data: bytes) -> bool:
            if can_id != 0x10F:
                meta = unpack_command_meta(self._meta)
                assert meta
                self._handle_rx_message(
                    SimpleNamespace(
                        arbitration_id=0x210,
                        data=pack_ack(
                            int(meta["sequence"]), int(meta["commandTag"]), 0, 2
                        ),
                    )
                )
            else:
                self._meta = data
            return True

    adapter = AckingAdapter(dry_run=False, physical_output_capable=True)
    adapter._bus = object()
    result = adapter.execute(
        {"commandId": "CMD-ACK", "kind": "SysCmd", "payload": {"arm": False}}
    )
    assert result["accepted"] is True
    assert result["resultCode"] == "ACK"


def test_duplicate_out_of_order_and_wrap_are_deterministic() -> None:
    guard = SequenceGuard()
    assert guard.accept(254)
    assert not guard.accept(254)
    assert not guard.accept(253)
    assert guard.accept(255)
    assert guard.accept(0)


@pytest.mark.parametrize(
    ("kwargs", "reason"),
    [
        ({"estop_active": True}, "ESTOP_ACTIVE"),
        ({"encoder_connected": False}, "ENCODER_DISCONNECTED"),
        ({"encoder_overflow": True}, "ENCODER_OVERFLOW"),
        ({"direction_ok": False}, "ENCODER_DIRECTION"),
        ({"deviation_ok": False}, "ENCODER_DEVIATION"),
    ],
)
def test_firmware_faults_always_disable_outputs(kwargs: dict[str, bool], reason: str) -> None:
    model = FirmwareModel()
    model.boot_complete()
    model.update_inputs(now_ms=1, estop_active=False, heartbeat=True)
    assert model.command("ARM") == "ARMED"
    assert model.outputs_enabled
    fault_inputs = {"estop_active": False, **kwargs}
    assert model.update_inputs(now_ms=2, **fault_inputs) == reason
    assert model.state == "FAULT"
    assert not model.outputs_enabled


def test_watchdog_loss_disables_outputs() -> None:
    model = FirmwareModel()
    model.boot_complete()
    model.update_inputs(now_ms=1, estop_active=False, heartbeat=True)
    model.command("ARM")
    assert model.update_inputs(now_ms=252, estop_active=False) == "HEARTBEAT_TIMEOUT"
    assert not model.outputs_enabled


def test_python_model_consumes_shared_contract_vectors() -> None:
    rows = csv.reader(
        line for line in (ROOT / "firmware/pico/test_vectors.csv").read_text().splitlines()
        if line and not line.startswith("#")
    )
    checked = 0
    for _name, initial, command, input_name, expected_state, expected_reason, outputs in rows:
        model = FirmwareModel()
        model.boot_complete()
        if initial not in {"BOOT", "SAFE"}:
            model.update_inputs(now_ms=1, estop_active=False, heartbeat=True)
        if initial in {"ARMED", "FIRING"}:
            model.command("ARM")
        if initial == "FIRING":
            model.command("FIRE")
        kwargs: dict[str, bool] = {}
        if input_name == "estop":
            kwargs["estop_active"] = True
        if input_name == "encoder_disconnected":
            kwargs["encoder_connected"] = False
        if input_name == "encoder_overflow":
            kwargs["encoder_overflow"] = True
        if input_name == "direction_fault":
            kwargs["direction_ok"] = False
        if input_name == "deviation_fault":
            kwargs["deviation_ok"] = False
        if kwargs:
            reason = model.update_inputs(now_ms=4, **{"estop_active": False, **kwargs})
        elif command == "BOOT_COMPLETE":
            model = FirmwareModel()
            reason = model.boot_complete()
        elif command == "HEARTBEAT":
            reason = model.update_inputs(now_ms=4, estop_active=False, heartbeat=True)
        else:
            reason = model.command(command)
        assert model.state == expected_state
        assert reason == expected_reason
        assert model.outputs_enabled is (outputs == "1")
        checked += 1
    assert checked >= 10
