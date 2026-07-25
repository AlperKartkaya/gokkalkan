from __future__ import annotations

import json
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.request import Request, urlopen

from gokkalkan_backend.mission_core import MissionCore
from gokkalkan_backend.mission_flow import MissionFlow
from gokkalkan_backend.operator_api import DryRunHardwareAdapter, OperatorService
from gokkalkan_backend.operator_http_server import build_http_server
from gokkalkan_backend.telemetry_log import JsonlTelemetryStore


def fixed_clock() -> str:
    return "2026-07-25T12:00:00Z"


class MissionFlowUnitTest(unittest.TestCase):
    def test_stage_one_preserves_backend_target_order(self) -> None:
        flow = MissionFlow()
        tracks = [
            {"trackId": "ORDER-1", "rangeM": 15, "friendFoe": "Düşman"},
            {"trackId": "ORDER-2", "rangeM": 5, "friendFoe": "Düşman"},
        ]

        flow.start_stage(1, 1, tracks, reason="TEST")

        self.assertEqual(flow.selected_target_id, "ORDER-1")
        self.assertFalse(flow.record_engagement("ORDER-2"))
        self.assertTrue(flow.record_engagement("ORDER-1"))
        self.assertEqual(flow.selected_target_id, "ORDER-2")
        self.assertTrue(flow.record_engagement("ORDER-2"))
        self.assertEqual(flow.status, "ROUND_COMPLETE")

    def test_stage_two_prioritizes_nearest_non_friendly_without_type_gate(self) -> None:
        flow = MissionFlow()
        flow.start_stage(
            2,
            1,
            [
                {
                    "trackId": "UNKNOWN-FAR",
                    "rangeM": 12,
                    "confidence": 0.9,
                    "friendFoe": "Bilinmeyen",
                },
                {
                    "trackId": "UNKNOWN-NEAR",
                    "rangeM": 4,
                    "confidence": 0.6,
                    "friendFoe": "Bilinmeyen",
                },
                {
                    "trackId": "FRIEND",
                    "rangeM": 2,
                    "confidence": 1,
                    "friendFoe": "Dost",
                },
            ],
            reason="TEST",
        )

        self.assertEqual(
            flow.target_order,
            ["UNKNOWN-NEAR", "UNKNOWN-FAR"],
        )
        self.assertEqual(flow.selected_target_id, "UNKNOWN-NEAR")

    def test_stage_three_requires_enemy_type_and_type_specific_range(self) -> None:
        flow = MissionFlow()
        flow.start_stage(
            3,
            1,
            [
                {
                    "trackId": "F16-TOO-NEAR",
                    "targetType": "F16",
                    "friendFoe": "Düşman",
                    "rangeM": 8,
                },
                {
                    "trackId": "F16-VALID",
                    "targetType": "F16",
                    "friendFoe": "Düşman",
                    "rangeM": 12,
                },
                {
                    "trackId": "FRIEND",
                    "targetType": "Helikopter",
                    "friendFoe": "Dost",
                    "rangeM": 8,
                },
            ],
            reason="TEST",
        )

        self.assertEqual(flow.target_order, ["F16-VALID"])

    def test_estop_reset_requires_explicit_resume(self) -> None:
        flow = MissionFlow()
        flow.start_stage(1, 1, [], reason="TEST")
        flow.latch_estop("ESTOP")
        flow.release_estop("RESET")

        self.assertEqual(flow.status, "PAUSED")
        self.assertTrue(flow.resume("OPERATOR_RESUME"))
        self.assertEqual(flow.status, "ACTIVE")


class Phase8RealHttpFlowTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        telemetry = JsonlTelemetryStore(
            Path(self.tempdir.name) / "phase8.jsonl",
            clock=fixed_clock,
        )
        service = OperatorService(
            clock=fixed_clock,
            hardware=DryRunHardwareAdapter(clock=fixed_clock),
            telemetry=telemetry,
        )
        self.service = service
        self.core = MissionCore(service, run_id="RUN-PHASE8-E2E")
        self.server = build_http_server(
            host="127.0.0.1",
            port=0,
            service=service,
            core=self.core,
        )
        self.thread = threading.Thread(
            target=self.server.serve_forever,
            daemon=True,
        )
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.server.server_address[1]}"

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        self.tempdir.cleanup()

    def post(self, path: str, payload: dict | None = None) -> dict:
        request = Request(
            f"{self.base}{path}",
            data=json.dumps(payload or {}).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(request, timeout=2) as response:
            return json.loads(response.read().decode())

    def get(self, path: str) -> dict:
        with urlopen(f"{self.base}{path}", timeout=2) as response:
            return json.loads(response.read().decode())

    def test_stage_one_manual_deadman_order_and_fire_flow(self) -> None:
        stage = self.post("/stage", {"stage": 1, "round": 1, "reason": "E2E"})
        self.assertTrue(stage["accepted"])
        state = stage["state"]
        self.assertEqual(state["missionFlow"]["status"], "ACTIVE")
        self.assertEqual(state["missionTimeLimitSec"], 300)
        selected = state["missionFlow"]["selectedTargetId"]

        no_deadman = self.post(
            "/manual-aim",
            {
                "panDeltaDeg": 1,
                "tiltDeltaDeg": 0,
                "rateLimitDegPerSec": 10,
                "deadmanActive": False,
            },
        )
        self.assertFalse(no_deadman["accepted"])
        aim = self.post(
            "/manual-aim",
            {
                "panDeltaDeg": 1,
                "tiltDeltaDeg": 0,
                "rateLimitDegPerSec": 10,
                "deadmanActive": True,
            },
        )
        self.assertTrue(aim["accepted"])

        fire = self.post(
            "/fire-intent",
            {
                "targetId": selected,
                "stage": 1,
                "round": 1,
                "operatorConfirm": True,
            },
        )
        self.assertTrue(fire["accepted"])
        self.assertIn(
            selected,
            fire["state"]["missionFlow"]["completedTargetIds"],
        )
        self.assertFalse(fire["physicalOutput"])

    def test_stage_one_300_second_limit_fails_closed(self) -> None:
        stage = self.post("/stage", {"stage": 1, "round": 1, "reason": "E2E"})
        selected = stage["state"]["missionFlow"]["selectedTargetId"]
        self.service._mission_elapsed_before_pause_sec = 300.0
        self.service.mission_started_at = None

        aim = self.post(
            "/manual-aim",
            {
                "panDeltaDeg": 1,
                "tiltDeltaDeg": 0,
                "rateLimitDegPerSec": 10,
                "deadmanActive": True,
            },
        )
        self.assertFalse(aim["accepted"])
        self.assertTrue(aim["state"]["missionTimeExpired"])
        self.assertEqual(aim["state"]["missionFlow"]["status"], "PAUSED")
        self.assertEqual(
            aim["state"]["missionFlow"]["lastTransitionReason"],
            "STAGE1_TIME_EXPIRED",
        )

        fire = self.post(
            "/fire-intent",
            {
                "targetId": selected,
                "stage": 1,
                "round": 1,
                "operatorConfirm": True,
            },
        )
        self.assertFalse(fire["accepted"])

    def test_stage_two_real_track_priority_and_progress(self) -> None:
        self.post("/stage", {"stage": 2, "round": 1, "reason": "E2E"})
        self.post(
            "/tracks/update",
            {
                "source": "perception",
                "tracks": [
                    {
                        "trackId": "PERCEPTION-FAR",
                        "friendFoe": "Bilinmeyen",
                        "rangeM": 12,
                        "bearingDeg": 5,
                        "confidence": 0.8,
                    },
                    {
                        "trackId": "PERCEPTION-NEAR",
                        "friendFoe": "Bilinmeyen",
                        "rangeM": 4,
                        "bearingDeg": -4,
                        "confidence": 0.7,
                    },
                ],
            },
        )
        state = self.get("/state")
        self.assertEqual(
            state["missionFlow"]["selectedTargetId"],
            "PERCEPTION-NEAR",
        )
        fire = self.post(
            "/fire-intent",
            {
                "targetId": "PERCEPTION-NEAR",
                "stage": 2,
                "round": 1,
                "operatorConfirm": True,
            },
        )
        self.assertTrue(fire["accepted"])
        self.assertEqual(
            fire["state"]["missionFlow"]["selectedTargetId"],
            "PERCEPTION-FAR",
        )

    def test_stage_three_range_gate_maintenance_stop_and_estop(self) -> None:
        self.post("/stage", {"stage": 3, "round": 1, "reason": "E2E"})
        self.post(
            "/tracks/update",
            {
                "source": "lidar-fused",
                "tracks": [
                    {
                        "trackId": "MEASURED-F16",
                        "targetType": "F16",
                        "friendFoe": "Düşman",
                        "rangeM": 12,
                        "bearingDeg": 0,
                        "confidence": 0.95,
                    }
                ],
            },
        )
        fire = self.post(
            "/fire-intent",
            {
                "targetId": "MEASURED-F16",
                "stage": 3,
                "round": 1,
                "operatorConfirm": True,
            },
        )
        self.assertTrue(fire["accepted"])
        self.assertEqual(fire["state"]["tracks"][0]["source"], "fused")

        maintenance = self.post("/maintenance", {"reason": "E2E_MAINT"})
        self.assertTrue(maintenance["accepted"])
        self.assertEqual(
            maintenance["state"]["missionFlow"]["status"],
            "MAINTENANCE",
        )
        maintenance_end = self.post("/maintenance/end")
        self.assertTrue(maintenance_end["accepted"])
        self.assertGreaterEqual(
            maintenance_end["state"]["maintenanceUsedSec"],
            30,
        )
        self.assertEqual(
            maintenance_end["state"]["missionFlow"]["status"],
            "PAUSED",
        )
        maintenance_resume = self.post(
            "/mission/resume",
            {"reason": "E2E_MAINTENANCE_RESUME"},
        )
        self.assertTrue(maintenance_resume["accepted"])

        stopped = self.post("/mission/stop", {"reason": "E2E_STOP"})
        self.assertTrue(stopped["accepted"])
        self.assertEqual(stopped["state"]["missionFlow"]["status"], "PAUSED")
        resumed = self.post("/mission/resume", {"reason": "E2E_RESUME"})
        self.assertTrue(resumed["accepted"])
        self.assertEqual(
            resumed["state"]["missionFlow"]["status"],
            "ROUND_COMPLETE",
        )

        interrupted_maintenance = self.post(
            "/maintenance",
            {"reason": "E2E_ESTOP_DURING_MAINTENANCE"},
        )
        self.assertTrue(interrupted_maintenance["accepted"])
        estop = self.post("/estop", {"active": True})
        self.assertTrue(estop["accepted"])
        self.assertEqual(
            estop["state"]["missionFlow"]["status"],
            "ESTOP_LATCHED",
        )
        self.assertGreaterEqual(estop["state"]["maintenanceUsedSec"], 60)
        blocked_resume = self.post("/mission/resume", {"reason": "UNSAFE"})
        self.assertFalse(blocked_resume["accepted"])
        self.assertTrue(blocked_resume["state"]["safety"]["estop"])


if __name__ == "__main__":
    unittest.main()
