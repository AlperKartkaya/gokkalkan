from __future__ import annotations

import json
import threading
import unittest
from urllib.request import Request, urlopen

from gokkalkan_backend.operator_api import DryRunHardwareAdapter, OperatorService, target_range_gate
from gokkalkan_backend.operator_http_server import build_http_server


def fixed_clock() -> str:
    return "2026-05-25T20:20:00Z"


class OperatorServiceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.hardware = DryRunHardwareAdapter(clock=fixed_clock)
        self.service = OperatorService(clock=fixed_clock, hardware=self.hardware)

    def test_target_range_gate_matches_competition_ranges(self) -> None:
        self.assertTrue(target_range_gate("F16", 12.0))
        self.assertFalse(target_range_gate("F16", 9.9))
        self.assertTrue(target_range_gate("Helikopter", 5.0))
        self.assertFalse(target_range_gate("Balistik Füze", 4.9))
        self.assertTrue(target_range_gate("Mini/Micro İHA", 0.0))

    def test_initial_snapshot_is_dry_run_and_has_no_physical_output(self) -> None:
        snapshot = self.service.snapshot()
        self.assertTrue(snapshot["dryRun"])
        self.assertFalse(snapshot["physicalOutputEnabled"])
        self.assertEqual(snapshot["mode"], "safe")

    def test_fire_is_blocked_in_safe_mode_before_hardware_adapter(self) -> None:
        response = self.service.handle_fire_intent({"targetId": "DRY-RUN-F16-01", "stage": 3, "round": 1, "operatorConfirm": True, "dryRun": True})
        self.assertFalse(response["result"]["accepted"])
        self.assertEqual(response["result"]["safetyBlockReason"], "BLOCKED_MODE")
        self.assertEqual(self.hardware.commands, [])

    def test_dry_run_fire_records_no_physical_output(self) -> None:
        self.service.handle_mode_request({"requestedMode": "autonomous", "operatorId": "test", "timestamp": fixed_clock(), "reason": "test", "dryRun": True})
        response = self.service.handle_fire_intent({"targetId": "DRY-RUN-F16-01", "stage": 3, "round": 1, "operatorConfirm": True, "dryRun": True})
        self.assertTrue(response["result"]["accepted"])
        self.assertFalse(response["result"]["physicalOutput"])
        self.assertFalse(response["hardwareResult"]["physicalOutput"])
        self.assertEqual(len(self.hardware.commands), 1)

    def test_friendly_target_fire_is_blocked(self) -> None:
        self.service.handle_mode_request({"requestedMode": "autonomous", "operatorId": "test", "timestamp": fixed_clock(), "reason": "test", "dryRun": True})
        response = self.service.handle_fire_intent({"targetId": "DRY-RUN-HEL-02", "stage": 3, "round": 1, "operatorConfirm": True, "dryRun": True})
        self.assertFalse(response["result"]["accepted"])
        self.assertEqual(response["result"]["safetyBlockReason"], "BLOCKED_TARGET_GATE")
        self.assertEqual(len(self.hardware.commands), 0)

    def test_unarmed_live_fire_is_blocked(self) -> None:
        self.service.handle_mode_request({"requestedMode": "autonomous", "operatorId": "test", "timestamp": fixed_clock(), "reason": "test", "dryRun": True})
        response = self.service.handle_fire_intent({"targetId": "DRY-RUN-F16-01", "stage": 3, "round": 1, "operatorConfirm": True, "dryRun": False})
        self.assertFalse(response["result"]["accepted"])
        self.assertEqual(response["result"]["safetyBlockReason"], "BLOCKED_ARMING")
        self.assertEqual(len(self.hardware.commands), 0)


class OperatorHttpServerTest(unittest.TestCase):
    def test_http_state_and_fire_intent_endpoints(self) -> None:
        service = OperatorService(clock=fixed_clock)
        server = build_http_server("127.0.0.1", 0, service=service)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{server.server_address[1]}"
        try:
            with urlopen(f"{base}/health", timeout=2) as response:
                health = json.loads(response.read().decode("utf-8"))
            self.assertTrue(health["ok"])
            self.assertFalse(health["physicalOutputEnabled"])

            mode_payload = json.dumps({"requestedMode": "autonomous", "operatorId": "test", "timestamp": fixed_clock(), "reason": "http-test", "dryRun": True}).encode("utf-8")
            with urlopen(Request(f"{base}/mode", data=mode_payload, headers={"Content-Type": "application/json"}, method="POST"), timeout=2) as response:
                mode = json.loads(response.read().decode("utf-8"))
            self.assertTrue(mode["result"]["accepted"])

            fire_payload = json.dumps({"targetId": "DRY-RUN-F16-01", "stage": 3, "round": 1, "operatorConfirm": True, "dryRun": True}).encode("utf-8")
            with urlopen(Request(f"{base}/fire-intent", data=fire_payload, headers={"Content-Type": "application/json"}, method="POST"), timeout=2) as response:
                fire = json.loads(response.read().decode("utf-8"))
            self.assertTrue(fire["result"]["accepted"])
            self.assertFalse(fire["hardwareResult"]["physicalOutput"])
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)


if __name__ == "__main__":
    unittest.main()
