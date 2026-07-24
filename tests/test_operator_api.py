from __future__ import annotations

import json
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.request import Request, urlopen

from gokkalkan_backend.operator_api import DryRunHardwareAdapter, OperatorService, manual_aim_payload_ok, stage_request_payload_ok, target_range_gate
from gokkalkan_backend.operator_http_server import build_http_server
from gokkalkan_backend.telemetry_log import JsonlTelemetryStore


def fixed_clock() -> str:
    return "2026-05-25T20:20:00Z"


class OperatorServiceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.telemetry_path = Path(self.tempdir.name) / "operator-test.jsonl"
        self.telemetry = JsonlTelemetryStore(self.telemetry_path, clock=fixed_clock)
        self.hardware = DryRunHardwareAdapter(clock=fixed_clock)
        self.service = OperatorService(clock=fixed_clock, hardware=self.hardware, telemetry=self.telemetry)

    def tearDown(self) -> None:
        self.tempdir.cleanup()

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
        self.assertEqual(snapshot["mode"], "autonomous")
        self.assertEqual(snapshot["telemetry"]["recordCount"], 1)
        self.assertGreaterEqual(len(snapshot["sensorFrames"]), 1)
        self.assertTrue(snapshot["sensorHealth"]["replayOnly"])
        unknown_track = next(track for track in snapshot["tracks"] if track["trackId"] == "DRY-RUN-UAV-03")
        self.assertEqual(unknown_track["friendFoe"], "Bilinmeyen")
        unknown_frame = next(frame for frame in snapshot["sensorFrames"] if frame["trackId"] == "DRY-RUN-UAV-03" and frame["sensor"] == "fusion")
        self.assertEqual(unknown_frame["rangeGate"], "Kimlik bekleniyor")
        self.assertLess(unknown_frame["classificationConfidence"], 0.6)
        self.assertIn("Kimlik kesinleşmeden", unknown_frame["recommendation"])

    def test_stage_request_updates_authoritative_mission_context_and_sensor_frames(self) -> None:
        response = self.service.handle_stage_request({"stage": 2, "round": 4, "operatorId": "test", "timestamp": fixed_clock(), "reason": "stage-test", "dryRun": True})

        self.assertTrue(response["result"]["accepted"])
        self.assertEqual(response["state"]["stage"], 2)
        self.assertEqual(response["state"]["round"], 4)
        self.assertEqual(response["state"]["mode"], "autonomous")
        self.assertFalse(response["result"]["physicalOutput"])
        self.assertTrue(all(frame["stage"] == 2 and frame["round"] == 4 for frame in response["state"]["sensorFrames"]))
        self.assertTrue(any("sınıflandırma zorunlu değil" in frame["recommendation"] for frame in response["state"]["sensorFrames"]))

    def test_invalid_stage_request_is_blocked_without_mutating_state(self) -> None:
        self.assertTrue(stage_request_payload_ok({"stage": 3, "round": 8}))
        self.assertFalse(stage_request_payload_ok({"stage": 4, "round": 1}))
        self.assertFalse(stage_request_payload_ok({"stage": 2, "round": 5}))
        self.assertFalse(stage_request_payload_ok({"stage": 2.9, "round": 4}))
        self.assertFalse(stage_request_payload_ok({"stage": 2, "round": 4.9}))
        self.assertFalse(stage_request_payload_ok({"stage": "2", "round": "4"}))

        response = self.service.handle_stage_request({"stage": 4, "round": 1, "operatorId": "test", "timestamp": fixed_clock(), "reason": "bad-stage", "dryRun": True})

        self.assertFalse(response["result"]["accepted"])
        self.assertEqual(response["result"]["safetyBlockReason"], "BLOCKED_INVALID_COMMAND")
        self.assertEqual(response["state"]["stage"], 3)
        self.assertEqual(response["state"]["round"], 1)

    def test_fire_is_blocked_in_safe_mode_before_hardware_adapter(self) -> None:
        self.service.handle_mode_request({"requestedMode": "safe", "operatorId": "test", "timestamp": fixed_clock(), "reason": "safe-mode-test", "dryRun": True})
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

    def test_fire_intent_stage_round_mismatch_is_blocked_before_hardware(self) -> None:
        self.service.handle_mode_request({"requestedMode": "autonomous", "operatorId": "test", "timestamp": fixed_clock(), "reason": "mismatch-test", "dryRun": True})

        response = self.service.handle_fire_intent({"targetId": "DRY-RUN-F16-01", "stage": 2, "round": 1, "operatorConfirm": True, "dryRun": True})

        self.assertFalse(response["result"]["accepted"])
        self.assertEqual(response["result"]["safetyBlockReason"], "BLOCKED_INVALID_COMMAND")
        self.assertEqual(self.hardware.commands, [])

    def test_manual_aim_requires_manual_mode_deadman_and_safe_payload(self) -> None:
        blocked = self.service.handle_manual_aim({"panDeltaDeg": 2, "tiltDeltaDeg": 0, "rateLimitDegPerSec": 12, "deadmanActive": True, "dryRun": True})
        self.assertFalse(blocked["result"]["accepted"])
        self.assertEqual(blocked["result"]["safetyBlockReason"], "BLOCKED_MODE")
        self.assertEqual(self.hardware.commands, [])

        self.service.handle_stage_request({"stage": 1, "round": 1, "operatorId": "test", "timestamp": fixed_clock(), "reason": "manual-stage", "dryRun": True})
        self.service.handle_mode_request({"requestedMode": "manual", "operatorId": "test", "timestamp": fixed_clock(), "reason": "manual-test", "dryRun": True})

        no_deadman = self.service.handle_manual_aim({"panDeltaDeg": 2, "tiltDeltaDeg": 0, "rateLimitDegPerSec": 12, "deadmanActive": False, "dryRun": True})
        self.assertFalse(no_deadman["result"]["accepted"])
        self.assertEqual(no_deadman["result"]["safetyBlockReason"], "BLOCKED_MODE")
        self.assertEqual(self.hardware.commands, [])

        oversized = self.service.handle_manual_aim({"panDeltaDeg": 99, "tiltDeltaDeg": 0, "rateLimitDegPerSec": 12, "deadmanActive": True, "dryRun": True})
        self.assertFalse(oversized["result"]["accepted"])
        self.assertEqual(oversized["result"]["safetyBlockReason"], "BLOCKED_INVALID_COMMAND")
        self.assertEqual(self.hardware.commands, [])

        accepted = self.service.handle_manual_aim({"panDeltaDeg": 2, "tiltDeltaDeg": 0, "rateLimitDegPerSec": 12, "deadmanActive": True, "dryRun": True})
        self.assertTrue(accepted["result"]["accepted"])
        self.assertFalse(accepted["result"]["physicalOutput"])
        self.assertFalse(accepted["hardwareResult"]["physicalOutput"])
        self.assertEqual(len(self.hardware.commands), 1)
        self.assertEqual(self.hardware.commands[0]["command"]["kind"], "ManualAimCommand")

    def test_manual_aim_is_blocked_outside_stage_one_even_if_manual_mode_is_requested(self) -> None:
        for stage in (2, 3):
            with self.subTest(stage=stage):
                self.service.handle_stage_request({"stage": stage, "round": 1, "operatorId": "test", "timestamp": fixed_clock(), "reason": "manual-stage-block", "dryRun": True})
                self.service.handle_mode_request({"requestedMode": "manual", "operatorId": "test", "timestamp": fixed_clock(), "reason": "manual-mode-override", "dryRun": True})

                response = self.service.handle_manual_aim({"panDeltaDeg": 2, "tiltDeltaDeg": 0, "rateLimitDegPerSec": 12, "deadmanActive": True, "dryRun": True})

                self.assertFalse(response["result"]["accepted"])
                self.assertEqual(response["result"]["safetyBlockReason"], "BLOCKED_MODE")
                self.assertEqual(self.hardware.commands, [])

    def test_manual_aim_payload_guard_rejects_malformed_values(self) -> None:
        self.assertTrue(manual_aim_payload_ok({"panDeltaDeg": 0, "tiltDeltaDeg": 0, "rateLimitDegPerSec": 12}))
        self.assertFalse(manual_aim_payload_ok({"panDeltaDeg": "nan", "tiltDeltaDeg": 0, "rateLimitDegPerSec": 12}))
        self.assertFalse(manual_aim_payload_ok({"panDeltaDeg": True, "tiltDeltaDeg": 0, "rateLimitDegPerSec": 12}))
        self.assertFalse(manual_aim_payload_ok({"panDeltaDeg": 2, "tiltDeltaDeg": 0}))
        self.assertFalse(manual_aim_payload_ok({"panDeltaDeg": 2, "tiltDeltaDeg": 0, "rateLimitDegPerSec": 0}))

    def test_telemetry_jsonl_export_and_replay_are_persistent_and_no_output(self) -> None:
        self.service.handle_mode_request({"requestedMode": "autonomous", "operatorId": "test", "timestamp": fixed_clock(), "reason": "telemetry-test", "dryRun": True})
        self.service.handle_fire_intent({"targetId": "DRY-RUN-F16-01", "stage": 3, "round": 1, "operatorConfirm": True, "dryRun": True})

        records = self.telemetry.read_all()
        record_types = {record["recordType"] for record in records}
        self.assertIn("event", record_types)
        self.assertIn("command_result", record_types)
        self.assertIn("hardware_result", record_types)
        self.assertTrue(self.telemetry_path.exists())
        self.assertTrue(all(record.get("payload", {}).get("physicalOutput") is not True for record in records))

        exported = self.service.telemetry_export()
        self.assertFalse(exported["physicalOutputEnabled"])
        self.assertGreaterEqual(exported["telemetry"]["recordCount"], 5)
        self.assertEqual(exported["entries"], records)

        replay = self.service.replay()
        self.assertTrue(replay["replayOnly"])
        self.assertFalse(replay["physicalOutputEnabled"])
        self.assertFalse(replay["unsafeReplayEvidence"])
        self.assertGreaterEqual(len(replay["events"]), 1)
        self.assertGreaterEqual(len(replay["commandResults"]), 1)
        self.assertGreaterEqual(len(replay["hardwareResults"]), 1)
        self.assertTrue(all(result["physicalOutput"] is False for result in replay["hardwareResults"]))

    def test_replay_flags_tampered_physical_output_evidence(self) -> None:
        self.telemetry.append("hardware_result", {"commandId": "TAMPERED", "physicalOutput": True})

        exported = self.service.telemetry_export()
        replay = self.service.replay()

        self.assertTrue(exported["unsafeReplayEvidence"])
        self.assertTrue(replay["unsafeReplayEvidence"])
        self.assertIn("physicalOutput=true", replay["evidenceWarning"])

    def test_reset_telemetry_keeps_dry_run_no_output_boundary(self) -> None:
        self.service.handle_mode_request({"requestedMode": "autonomous", "operatorId": "test", "timestamp": fixed_clock(), "reason": "reset-test", "dryRun": True})
        self.assertGreater(self.telemetry.metadata()["recordCount"], 1)

        response = self.service.reset_telemetry()

        self.assertTrue(response["ok"])
        self.assertFalse(response["physicalOutputEnabled"])
        self.assertEqual(response["state"]["mode"], "safe")
        self.assertEqual(response["telemetry"]["recordCount"], 1)
        self.assertEqual(self.telemetry.read_all()[0]["payload"]["decision"], "RESET")

    def test_readiness_report_is_honest_about_final_phase_gaps(self) -> None:
        report = self.service.readiness()

        self.assertEqual(report["schemaVersion"], 1)
        self.assertFalse(report["physicalOutputEnabled"])
        self.assertIn("resmi yarışma uygunluk skoru değildir", report["scoreBasis"])
        self.assertGreater(report["readinessPercent"], 0)
        self.assertLess(report["readinessPercent"], 100)

        items = {item["id"]: item for item in report["items"]}
        self.assertEqual(items["backend_api"]["status"], "ready")
        self.assertEqual(items["telemetry_replay"]["status"], "ready")
        self.assertEqual(items["operator_panel_ui"]["status"], "ready")
        self.assertNotIn("ManualAimCommand", items["operator_panel_ui"]["ktrInterface"])
        self.assertIn("FireIntent", items["operator_panel_ui"]["ktrInterface"])
        self.assertEqual(items["perception_adapter"]["status"], "tbd")
        self.assertEqual(items["radar_lidar_adapter"]["status"], "tbd")
        self.assertEqual(items["live_arming"]["status"], "blocked")
        self.assertTrue(any("radar/LiDAR" in action for action in report["nextCriticalActions"]))

    def test_friendly_target_fire_is_blocked(self) -> None:
        self.service.handle_mode_request({"requestedMode": "autonomous", "operatorId": "test", "timestamp": fixed_clock(), "reason": "test", "dryRun": True})
        response = self.service.handle_fire_intent({"targetId": "DRY-RUN-HEL-02", "stage": 3, "round": 1, "operatorConfirm": True, "dryRun": True})
        self.assertFalse(response["result"]["accepted"])
        self.assertEqual(response["result"]["safetyBlockReason"], "BLOCKED_TARGET_GATE")
        self.assertEqual(len(self.hardware.commands), 0)

    def test_unidentified_target_fire_is_blocked_until_classification_is_resolved(self) -> None:
        response = self.service.handle_fire_intent({"targetId": "DRY-RUN-UAV-03", "stage": 3, "round": 1, "operatorConfirm": True, "dryRun": True})
        self.assertFalse(response["result"]["accepted"])
        self.assertEqual(response["result"]["safetyBlockReason"], "BLOCKED_TARGET_GATE")
        self.assertEqual(len(self.hardware.commands), 0)

    def test_dry_run_service_ignores_client_live_override(self) -> None:
        self.service.handle_mode_request({"requestedMode": "autonomous", "operatorId": "test", "timestamp": fixed_clock(), "reason": "test", "dryRun": True})
        response = self.service.handle_fire_intent({"targetId": "DRY-RUN-F16-01", "stage": 3, "round": 1, "operatorConfirm": True, "dryRun": False})
        self.assertTrue(response["result"]["accepted"])
        self.assertTrue(response["result"]["dryRun"])
        self.assertTrue(response["safety"]["dryRun"])
        self.assertEqual(response["result"]["safetyBlockReason"], "ALLOWED")
        self.assertEqual(len(self.hardware.commands), 1)

    def test_live_service_ignores_client_dry_run_override(self) -> None:
        live_hardware = DryRunHardwareAdapter(clock=fixed_clock)
        live_service = OperatorService(
            clock=fixed_clock,
            hardware=live_hardware,
            telemetry=self.telemetry,
            dry_run=False,
        )

        response = live_service.handle_fire_intent(
            {
                "targetId": "DRY-RUN-F16-01",
                "stage": 3,
                "round": 1,
                "operatorConfirm": True,
                "dryRun": True,
            }
        )

        self.assertFalse(response["result"]["accepted"])
        self.assertFalse(response["result"]["dryRun"])
        self.assertFalse(response["safety"]["dryRun"])
        self.assertEqual(response["result"]["safetyBlockReason"], "BLOCKED_ARMING")
        self.assertEqual(live_hardware.commands, [])


class OperatorHttpServerTest(unittest.TestCase):
    def test_http_state_and_fire_intent_endpoints(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            telemetry = JsonlTelemetryStore(Path(tempdir) / "http-operator.jsonl", clock=fixed_clock)
            service = OperatorService(clock=fixed_clock, telemetry=telemetry)
            server = build_http_server("127.0.0.1", 0, service=service)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base = f"http://127.0.0.1:{server.server_address[1]}"
            try:
                with urlopen(f"{base}/health", timeout=2) as response:
                    health = json.loads(response.read().decode("utf-8"))
                self.assertTrue(health["ok"])
                self.assertFalse(health["physicalOutputEnabled"])

                with urlopen(f"{base}/readiness", timeout=2) as response:
                    readiness = json.loads(response.read().decode("utf-8"))
                self.assertLess(readiness["readinessPercent"], 100)
                self.assertFalse(readiness["physicalOutputEnabled"])
                self.assertTrue(any(item["id"] == "radar_lidar_adapter" and item["status"] == "tbd" for item in readiness["items"]))

                with urlopen(f"{base}/sensor-frames", timeout=2) as response:
                    sensor_frames = json.loads(response.read().decode("utf-8"))
                self.assertTrue(sensor_frames["replayOnly"])
                self.assertFalse(sensor_frames["physicalOutputEnabled"])
                self.assertGreater(len(sensor_frames["frames"]), 0)

                stage_payload = json.dumps({"stage": 2, "round": 4, "operatorId": "test", "timestamp": fixed_clock(), "reason": "http-stage", "dryRun": True}).encode("utf-8")
                with urlopen(Request(f"{base}/stage", data=stage_payload, headers={"Content-Type": "application/json"}, method="POST"), timeout=2) as response:
                    stage = json.loads(response.read().decode("utf-8"))
                self.assertTrue(stage["result"]["accepted"])
                self.assertEqual(stage["state"]["stage"], 2)
                self.assertEqual(stage["state"]["round"], 4)

                mode_payload = json.dumps({"requestedMode": "autonomous", "operatorId": "test", "timestamp": fixed_clock(), "reason": "http-test", "dryRun": True}).encode("utf-8")
                with urlopen(Request(f"{base}/mode", data=mode_payload, headers={"Content-Type": "application/json"}, method="POST"), timeout=2) as response:
                    mode = json.loads(response.read().decode("utf-8"))
                self.assertTrue(mode["result"]["accepted"])

                stage3_payload = json.dumps({"stage": 3, "round": 1, "operatorId": "test", "timestamp": fixed_clock(), "reason": "http-stage3", "dryRun": True}).encode("utf-8")
                with urlopen(Request(f"{base}/stage", data=stage3_payload, headers={"Content-Type": "application/json"}, method="POST"), timeout=2) as response:
                    json.loads(response.read().decode("utf-8"))

                fire_payload = json.dumps({"targetId": "DRY-RUN-F16-01", "stage": 3, "round": 1, "operatorConfirm": True, "dryRun": True}).encode("utf-8")
                with urlopen(Request(f"{base}/fire-intent", data=fire_payload, headers={"Content-Type": "application/json"}, method="POST"), timeout=2) as response:
                    fire = json.loads(response.read().decode("utf-8"))
                self.assertTrue(fire["result"]["accepted"])
                self.assertFalse(fire["hardwareResult"]["physicalOutput"])

                with urlopen(f"{base}/telemetry/export", timeout=2) as response:
                    exported = json.loads(response.read().decode("utf-8"))
                self.assertFalse(exported["physicalOutputEnabled"])
                self.assertGreaterEqual(exported["telemetry"]["recordCount"], 5)

                with urlopen(f"{base}/replay", timeout=2) as response:
                    replay = json.loads(response.read().decode("utf-8"))
                self.assertTrue(replay["replayOnly"])
                self.assertFalse(replay["physicalOutputEnabled"])
                self.assertTrue(all(result["physicalOutput"] is False for result in replay["hardwareResults"]))

                with urlopen(Request(f"{base}/telemetry/reset", data=b"{}", headers={"Content-Type": "application/json"}, method="POST"), timeout=2) as response:
                    reset = json.loads(response.read().decode("utf-8"))
                self.assertTrue(reset["ok"])
                self.assertEqual(reset["state"]["mode"], "safe")
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)


class OperatorHttpServerFactoryTest(unittest.TestCase):
    def test_server_factory_accepts_explicit_telemetry_path(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            telemetry_path = Path(tempdir) / "factory.jsonl"
            server = build_http_server("127.0.0.1", 0, telemetry_jsonl=str(telemetry_path))
            try:
                self.assertEqual(server.RequestHandlerClass.service.telemetry.path, telemetry_path)
                self.assertTrue(telemetry_path.exists())
            finally:
                server.server_close()


class MaintenanceBudgetTest(unittest.TestCase):
    """Şartname v1.3: bakım bütçesi ve timer testleri (Adım 1)."""

    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.telemetry_path = Path(self.tempdir.name) / "maint-test.jsonl"
        self.telemetry = JsonlTelemetryStore(self.telemetry_path, clock=fixed_clock)
        self.hardware = DryRunHardwareAdapter(clock=fixed_clock)
        self.service = OperatorService(clock=fixed_clock, hardware=self.hardware, telemetry=self.telemetry)

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_initial_snapshot_includes_maintenance_fields(self) -> None:
        snap = self.service.snapshot()
        self.assertIn("maintenanceBudgetSec", snap)
        self.assertIn("maintenanceUsedSec", snap)
        self.assertIn("maintenanceRemainingBudgetSec", snap)
        self.assertEqual(snap["maintenanceBudgetSec"], 600)
        self.assertEqual(snap["maintenanceUsedSec"], 0.0)
        self.assertEqual(snap["maintenanceRemainingBudgetSec"], 600.0)

    def test_maintenance_request_switches_mode(self) -> None:
        # Autonomous moddan bakıma geç
        self.service.handle_mode_request({"requestedMode": "autonomous", "operatorId": "test",
                                          "timestamp": fixed_clock(), "reason": "test", "dryRun": True})
        result = self.service.handle_maintenance_request({})
        self.assertTrue(result["ok"])
        self.assertFalse(result["blocked"])
        self.assertEqual(self.service.mode, "maintenance")

    def test_maintenance_request_blocked_when_budget_exhausted(self) -> None:
        # Bütçeyi tüket
        self.service.maintenance_used_sec = 590.0  # 600 - 590 = 10 sn kaldı < 30 sn min
        result = self.service.handle_maintenance_request({})
        self.assertFalse(result["ok"])
        self.assertTrue(result["blocked"])
        self.assertEqual(result["reason"], "MAINTENANCE_BUDGET_EXHAUSTED")
        self.assertNotEqual(self.service.mode, "maintenance")

    def test_maintenance_request_blocked_during_estop(self) -> None:
        self.service.set_estop(True)
        result = self.service.handle_maintenance_request({})
        self.assertFalse(result["ok"])
        self.assertEqual(result["reason"], "BLOCKED_ESTOP")

    def test_maintenance_end_charges_minimum_30s(self) -> None:
        self.service.handle_mode_request({"requestedMode": "autonomous", "operatorId": "test",
                                          "timestamp": fixed_clock(), "reason": "test", "dryRun": True})
        self.service.handle_maintenance_request({})
        # Anında end → min 30 sn uygulanmalı
        result = self.service.maintenance_end()
        self.assertTrue(result["ok"])
        self.assertGreaterEqual(result["elapsedSec"], 30)
        self.assertEqual(self.service.mode, "safe")
        self.assertGreaterEqual(self.service.maintenance_used_sec, 30)

    def test_maintenance_end_when_not_in_maintenance_fails(self) -> None:
        result = self.service.maintenance_end()
        self.assertFalse(result["ok"])
        self.assertEqual(result["reason"], "NOT_IN_MAINTENANCE")

    def test_reset_telemetry_clears_maintenance_budget(self) -> None:
        self.service.maintenance_used_sec = 120.0
        self.service.reset_telemetry()
        self.assertEqual(self.service.maintenance_used_sec, 0.0)


class MissionTimerTest(unittest.TestCase):
    """Şartname: Aşama 1 görev timer'ı testleri (Adım 2)."""

    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.telemetry_path = Path(self.tempdir.name) / "timer-test.jsonl"
        self.telemetry = JsonlTelemetryStore(self.telemetry_path, clock=fixed_clock)
        self.service = OperatorService(clock=fixed_clock, hardware=DryRunHardwareAdapter(clock=fixed_clock),
                                       telemetry=self.telemetry)

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_initial_snapshot_includes_mission_timer_fields(self) -> None:
        snap = self.service.snapshot()
        self.assertIn("missionElapsedSec", snap)
        self.assertIn("missionRemainingSeconds", snap)
        self.assertIn("missionTimeLimitSec", snap)
        self.assertIn("missionTimerRunning", snap)

    def test_stage1_timer_starts_on_stage_request(self) -> None:
        self.service.handle_stage_request({"stage": 1, "round": 1, "operatorId": "test",
                                           "timestamp": fixed_clock(), "reason": "test", "dryRun": True})
        snap = self.service.snapshot()
        self.assertTrue(snap["missionTimerRunning"])
        self.assertEqual(snap["missionTimeLimitSec"], 300)
        self.assertIsNotNone(snap["missionRemainingSeconds"])
        self.assertLessEqual(snap["missionRemainingSeconds"], 300)

    def test_stage2_has_no_time_limit(self) -> None:
        self.service.handle_stage_request({"stage": 2, "round": 1, "operatorId": "test",
                                           "timestamp": fixed_clock(), "reason": "test", "dryRun": True})
        snap = self.service.snapshot()
        self.assertFalse(snap["missionTimerRunning"])
        self.assertIsNone(snap["missionTimeLimitSec"])
        self.assertIsNone(snap["missionRemainingSeconds"])

    def test_stage3_has_no_time_limit(self) -> None:
        snap = self.service.snapshot()  # başlangıçta stage 3
        self.assertIsNone(snap["missionTimeLimitSec"])
        self.assertIsNone(snap["missionRemainingSeconds"])

    def test_timer_resets_on_stage_change(self) -> None:
        # Önce Aşama 1 başlat
        self.service.handle_stage_request({"stage": 1, "round": 1, "operatorId": "test",
                                           "timestamp": fixed_clock(), "reason": "test", "dryRun": True})
        self.assertTrue(self.service.snapshot()["missionTimerRunning"])
        # Aşama 2'ye geç → timer durmalı
        self.service.handle_stage_request({"stage": 2, "round": 1, "operatorId": "test",
                                           "timestamp": fixed_clock(), "reason": "test", "dryRun": True})
        snap = self.service.snapshot()
        self.assertFalse(snap["missionTimerRunning"])

    def test_reset_telemetry_clears_mission_timer(self) -> None:
        self.service.handle_stage_request({"stage": 1, "round": 1, "operatorId": "test",
                                           "timestamp": fixed_clock(), "reason": "test", "dryRun": True})
        self.service.reset_telemetry()
        self.assertIsNone(self.service.mission_started_at)
        snap = self.service.snapshot()
        self.assertFalse(snap["missionTimerRunning"])


if __name__ == "__main__":
    unittest.main()
