from __future__ import annotations

import json
import importlib.util
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from types import SimpleNamespace

from gokkalkan_backend.can_protocol import (
    CAN_ID_COMMAND_META,
    CAN_ID_PANTILT_CMD_V1,
    CAN_ID_SYS_CMD_V1,
    KIND_PANTILT,
    KIND_SYSTEM,
    pack_command_meta,
    pack_pantilt,
    pack_system,
    unpack_ack,
    unpack_command_meta,
)
from gokkalkan_backend.digital_twin import (
    SCENARIOS,
    McuDigitalTwin,
    PanTiltDynamics,
    SafeFireMock,
    SensorFixtureReplay,
    run_scenario,
)
from gokkalkan_backend.safety_gate import SafetyDecision
from gokkalkan_backend.hardware_adapter import CanMcuAdapter


class DigitalTwinTest(unittest.TestCase):
    @unittest.skipUnless(importlib.util.find_spec("can"), "python-can is unavailable")
    def test_virtual_can_adapter_and_mcu_simulator_complete_v1_transaction(
        self,
    ) -> None:
        simulator_path = (
            Path(__file__).resolve().parents[1]
            / "backend"
            / "hardware_mock"
            / "mcu_simulator.py"
        )
        spec = importlib.util.spec_from_file_location(
            "phase6_mcu_simulator", simulator_path
        )
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        simulator = module.McuSimulator(
            channel="phase6-test-bus", bustype="virtual"
        )
        self.assertTrue(simulator._open())
        simulator._running = True
        threads = [
            threading.Thread(target=simulator._rx_loop, daemon=True),
            threading.Thread(target=simulator._tx_status_loop, daemon=True),
        ]
        for thread in threads:
            thread.start()
        adapter = CanMcuAdapter(
            channel="phase6-test-bus",
            bustype="virtual",
            dry_run=False,
            physical_output_capable=False,
        )
        try:
            adapter.start()
            time.sleep(0.25)
            arm = adapter.execute(
                {
                    "commandId": "HIL-E2E-ARM",
                    "kind": "SysCmd",
                    "payload": {"arm": True},
                }
            )
            aim = adapter.execute(
                {
                    "commandId": "HIL-E2E-AIM",
                    "kind": "ManualAimCommand",
                    "payload": {
                        "panDeltaDeg": 5,
                        "tiltDeltaDeg": 2,
                        "deadmanActive": True,
                    },
                }
            )
        finally:
            adapter.close()
            simulator._running = False
            if simulator._bus is not None:
                simulator._bus.shutdown()

        self.assertEqual(arm["resultCode"], "ACK")
        self.assertEqual(aim["resultCode"], "ACK")
        self.assertFalse(arm["physicalOutput"])
        self.assertFalse(aim["physicalOutput"])

    def test_pan_tilt_model_is_bounded_and_deterministic(self) -> None:
        first = PanTiltDynamics()
        second = PanTiltDynamics()
        self.assertFalse(first.command(100, 0))
        self.assertTrue(first.command(20, 8))
        self.assertTrue(second.command(20, 8))

        first_feedback = second_feedback = {}
        for _ in range(50):
            first_feedback = first.step(0.02)
            second_feedback = second.step(0.02)

        self.assertEqual(first_feedback, second_feedback)
        self.assertTrue(first_feedback["withinSoftLimits"])
        self.assertTrue(first_feedback["simulated"])
        self.assertFalse(first_feedback["measuredHardwareValue"])

    def test_fixture_set_covers_nominal_and_fault_inputs(self) -> None:
        fixtures = SensorFixtureReplay.standard()
        faults = {fixture.fault for fixture in fixtures}
        sources = {fixture.source for fixture in fixtures}
        self.assertEqual(sources, {"camera", "tfa50-l"})
        self.assertTrue(
            {"NO_DETECTION", "CORRUPT_UART", "STALE", "DROPOUT", "CLOCK_SKEW"}
            .issubset(faults)
        )

    def test_safe_fire_mock_requires_safety_gate_allow(self) -> None:
        fire = SafeFireMock()
        denied = SafetyDecision(False, "BLOCKED_ESTOP", "estop", {})
        allowed = SafetyDecision(True, "ALLOWED", "safe", {})

        self.assertFalse(fire.request("CMD-1", denied)["accepted"])
        result = fire.request("CMD-2", allowed)

        self.assertTrue(result["accepted"])
        self.assertEqual(result["output"], "SIMULATED_LAMP")
        self.assertFalse(result["physicalOutput"])

    def test_mcu_twin_uses_v1_ack_state_and_fault_behaviour(self) -> None:
        twin = McuDigitalTwin()
        twin.heartbeat()
        twin.receive(
            CAN_ID_COMMAND_META,
            pack_command_meta(1, "ARM-1", KIND_SYSTEM),
        )
        twin.receive(CAN_ID_SYS_CMD_V1, pack_system(1, 1))
        arm_ack = unpack_ack(twin.step(0)[0])
        self.assertIsNotNone(arm_ack)
        self.assertEqual(arm_ack["result"], "ACK")
        self.assertEqual(arm_ack["state"], "ARMED")

        twin.inject(ack_delay_ms=25)
        twin.receive(
            CAN_ID_COMMAND_META,
            pack_command_meta(2, "PAN-1", KIND_PANTILT),
        )
        twin.receive(CAN_ID_PANTILT_CMD_V1, pack_pantilt(2, 1000, 500))
        self.assertEqual(twin.step(24), [])
        self.assertEqual(unpack_ack(twin.step(1)[0])["result"], "ACK")

        twin.inject(estop_active=True)
        twin.receive(
            CAN_ID_COMMAND_META,
            pack_command_meta(3, "PAN-2", KIND_PANTILT),
        )
        twin.receive(CAN_ID_PANTILT_CMD_V1, pack_pantilt(3, 0, 0))
        self.assertEqual(unpack_ack(twin.step(25)[0])["result"], "NACK_STATE")

        faulty = McuDigitalTwin()
        faulty.heartbeat()
        faulty.inject(drop_next_ack=True)
        faulty.receive(
            CAN_ID_COMMAND_META,
            pack_command_meta(10, "DROP", KIND_SYSTEM),
        )
        faulty.receive(CAN_ID_SYS_CMD_V1, pack_system(10, 0))
        self.assertEqual(faulty.step(1_000), [])
        faulty.inject(corrupt_next_ack=True)
        faulty.receive(
            CAN_ID_COMMAND_META,
            pack_command_meta(11, "CORRUPT", KIND_SYSTEM),
        )
        faulty.receive(CAN_ID_SYS_CMD_V1, pack_system(11, 0))
        self.assertIsNone(unpack_ack(faulty.step(0)[0]))

    def test_virtual_hil_uses_v1_ack_without_physical_output(self) -> None:
        class AckingHilAdapter(CanMcuAdapter):
            def _send_can(self, can_id: int, data: bytes) -> bool:
                if can_id == CAN_ID_COMMAND_META:
                    self.meta = data
                else:
                    meta = unpack_command_meta(self.meta)
                    assert meta is not None
                    from gokkalkan_backend.can_protocol import CAN_ID_ACK_V1, pack_ack

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
                return True

        adapter = AckingHilAdapter(
            channel="test",
            bustype="virtual",
            dry_run=False,
            physical_output_capable=False,
        )
        adapter._bus = object()
        result = adapter.execute(
            {
                "commandId": "HIL-ARM",
                "kind": "SysCmd",
                "payload": {"arm": True},
            }
        )
        self.assertTrue(result["accepted"])
        self.assertEqual(result["protocolVersion"], 1)
        self.assertFalse(result["physicalOutput"])

    def test_all_scenarios_are_reproducible_and_physical_output_free(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for scenario in SCENARIOS:
                first = run_scenario(scenario, root / f"{scenario}.jsonl")
                second = run_scenario(scenario, root / f"{scenario}.jsonl")
                self.assertEqual(
                    first["deterministicDigest"], second["deterministicDigest"]
                )
                self.assertFalse(first["physicalOutput"])
                records = [
                    json.loads(line)
                    for line in (root / f"{scenario}.jsonl")
                    .read_text(encoding="utf-8")
                    .splitlines()
                ]
                self.assertTrue(records)
                self.assertFalse(
                    any(
                        record.get("payload", {}).get("physicalOutput") is True
                        for record in records
                    )
                )


if __name__ == "__main__":
    unittest.main()
