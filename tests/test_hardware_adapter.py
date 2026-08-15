"""Gökkalkan Hardware Adapter Birim Testleri.

Test kapsamı:
  - CAN mesaj pack/unpack codec (pan/tilt, fire, status)
  - XOR checksum doğrulama + bozuk paket reddi
  - CanMcuAdapter mock modda execute() davranışı
  - DryRunHardwareAdapter HardwareAdapterBase uyumu
  - GpioEStopMonitor callback iletimi
  - OperatorService.set_estop() Safety Gate entegrasyonu
  - OperatorService.update_tracks() perception besleme
  - Yeni endpoint'ler: /hardware/health, /tracks/update, /estop
"""

from __future__ import annotations

import json
import struct
import tempfile
import threading
import time
import unittest
from datetime import UTC, datetime
from pathlib import Path
from urllib.request import Request, urlopen

from gokkalkan_backend.hardware_adapter import (
    CENTIDEG_PER_DEG,
    CAN_ID_ESTOP_EVENT,
    CAN_ID_FIRE_CMD,
    CAN_ID_PANTILT_CMD,
    CAN_ID_STATUS,
    CAN_ID_SYS_CMD,
    CanMcuAdapter,
    GpioEStopMonitor,
    HardwareAdapterBase,
    pack_fire_cmd,
    pack_pantilt_cmd,
    pack_status,
    pack_sys_cmd,
    unpack_pantilt_cmd,
    unpack_status,
)
from gokkalkan_backend.operator_api import DryRunHardwareAdapter as DryRunAdapter
from gokkalkan_backend.operator_api import OperatorService
from gokkalkan_backend.operator_http_server import build_http_server
from gokkalkan_backend.telemetry_log import JsonlTelemetryStore
from gokkalkan_backend import CanMcuAdapter as CanMcuAdapterPkg


def fixed_clock() -> str:
    return "2026-07-20T18:00:00Z"


# ---------------------------------------------------------------------------
# CAN Mesaj Codec Testleri
# ---------------------------------------------------------------------------

class TestCanPantiltCodec(unittest.TestCase):

    def test_pack_unpack_roundtrip_positive_angles(self) -> None:
        data = pack_pantilt_cmd(4500, 1200, 1000, deadman_active=True)
        self.assertEqual(len(data), 8)
        result = unpack_pantilt_cmd(data)
        self.assertIsNotNone(result)
        self.assertAlmostEqual(result["panDeg"],        45.00, places=2)
        self.assertAlmostEqual(result["tiltDeg"],       12.00, places=2)
        self.assertAlmostEqual(result["rateDegPerSec"], 10.00, places=2)
        self.assertTrue(result["deadmanActive"])

    def test_pack_unpack_roundtrip_negative_angles(self) -> None:
        data = pack_pantilt_cmd(-9000, -4500, 3000, deadman_active=False)
        result = unpack_pantilt_cmd(data)
        self.assertIsNotNone(result)
        self.assertAlmostEqual(result["panDeg"],  -90.00, places=2)
        self.assertAlmostEqual(result["tiltDeg"], -45.00, places=2)
        self.assertFalse(result["deadmanActive"])

    def test_pack_clamps_out_of_range_values(self) -> None:
        # int16 sınırını aşan değerler kısıtlanmalı
        data = pack_pantilt_cmd(99999, -99999, 99999, deadman_active=False)
        result = unpack_pantilt_cmd(data)
        self.assertIsNotNone(result)
        self.assertLessEqual(abs(result["panDeg"]),  327.68)
        self.assertLessEqual(abs(result["tiltDeg"]), 327.68)

    def test_unpack_rejects_wrong_length(self) -> None:
        self.assertIsNone(unpack_pantilt_cmd(b"\x00" * 7))
        self.assertIsNone(unpack_pantilt_cmd(b"\x00" * 9))
        self.assertIsNone(unpack_pantilt_cmd(b""))

    def test_unpack_rejects_bad_checksum(self) -> None:
        data = bytearray(pack_pantilt_cmd(1000, 500, 500, deadman_active=False))
        data[7] ^= 0xFF   # checksum'u boz
        self.assertIsNone(unpack_pantilt_cmd(bytes(data)))

    def test_xor_checksum_consistency(self) -> None:
        """Aynı giriş her zaman aynı checksum üretmeli."""
        d1 = pack_pantilt_cmd(1000, 200, 500, deadman_active=True)
        d2 = pack_pantilt_cmd(1000, 200, 500, deadman_active=True)
        self.assertEqual(d1, d2)


class TestCanFireCodec(unittest.TestCase):

    def test_fire_command_format(self) -> None:
        data = pack_fire_cmd(fire=True, stage=2)
        self.assertEqual(len(data), 8)
        self.assertEqual(data[0], 0x01)
        self.assertEqual(data[1], 2)

    def test_cancel_fire_command(self) -> None:
        data = pack_fire_cmd(fire=False, stage=1)
        self.assertEqual(data[0], 0x00)

    def test_stage_clamped_to_1_3(self) -> None:
        self.assertEqual(pack_fire_cmd(True, 0)[1], 1)
        self.assertEqual(pack_fire_cmd(True, 4)[1], 3)


class TestCanStatusCodec(unittest.TestCase):

    def test_pack_unpack_status_roundtrip(self) -> None:
        data = pack_status(4500, -1200, estop_active=False, motion_ok=True, fire_ready=True)
        result = unpack_status(data)
        self.assertIsNotNone(result)
        self.assertAlmostEqual(result["panDeg"],  45.0,  places=2)
        self.assertAlmostEqual(result["tiltDeg"], -12.0, places=2)
        self.assertFalse(result["estopActive"])
        self.assertTrue(result["motionOk"])
        self.assertTrue(result["fireReady"])

    def test_unpack_status_with_estop(self) -> None:
        data = pack_status(0, 0, estop_active=True, motion_ok=False, fire_ready=False)
        result = unpack_status(data)
        self.assertIsNotNone(result)
        self.assertTrue(result["estopActive"])
        self.assertFalse(result["motionOk"])
        self.assertFalse(result["fireReady"])

    def test_unpack_status_rejects_short_data(self) -> None:
        self.assertIsNone(unpack_status(b"\x00" * 5))
        self.assertIsNone(unpack_status(b""))


# ---------------------------------------------------------------------------
# HardwareAdapterBase Uyumluluk Testleri
# ---------------------------------------------------------------------------

class TestHardwareAdapterBase(unittest.TestCase):

    def test_dryrun_adapter_is_base_subclass(self) -> None:
        adapter = DryRunAdapter(clock=fixed_clock)
        self.assertIsInstance(adapter, HardwareAdapterBase)

    def test_dryrun_adapter_health_check(self) -> None:
        adapter = DryRunAdapter(clock=fixed_clock)
        hc = adapter.health_check()
        self.assertFalse(hc["physicalOutputEnabled"])
        self.assertFalse(hc["picoReachable"])

    def test_dryrun_adapter_execute_never_physical_output(self) -> None:
        adapter = DryRunAdapter(clock=fixed_clock)
        result  = adapter.execute({"commandId": "TEST-001", "kind": "ManualAimCommand", "payload": {}})
        self.assertFalse(result["physicalOutput"])
        self.assertTrue(result["accepted"])

    def test_can_adapter_is_base_subclass(self) -> None:
        adapter = CanMcuAdapter(channel="test", bustype="virtual", dry_run=True)
        self.assertIsInstance(adapter, HardwareAdapterBase)

    def test_can_adapter_mock_execute_returns_accepted(self) -> None:
        adapter = CanMcuAdapter(channel="test", bustype="virtual", dry_run=True)
        adapter.start()
        result = adapter.execute({
            "commandId": "MOCK-001",
            "kind": "ManualAimCommand",
            "payload": {"panDeltaDeg": 5.0, "tiltDeltaDeg": -2.0, "rateLimitDegPerSec": 10.0, "deadmanActive": True},
        })
        self.assertTrue(result["accepted"])
        self.assertFalse(result["physicalOutput"])
        self.assertTrue(result["dryRun"])
        adapter.close()

    def test_can_adapter_fire_command_mock(self) -> None:
        adapter = CanMcuAdapter(channel="test", bustype="virtual", dry_run=True)
        adapter.start()
        result = adapter.execute({
            "commandId": "FIRE-001",
            "kind": "FireIntent",
            "payload": {"stage": 2, "round": 1, "dryRun": True},
            "target": {"trackId": "TEST-T1"},
        })
        self.assertTrue(result["accepted"])
        adapter.close()

    def test_can_adapter_health_check_dry_run(self) -> None:
        adapter = CanMcuAdapter(channel="test", bustype="virtual", dry_run=True)
        hc = adapter.health_check()
        self.assertTrue(hc["dryRun"])
        self.assertFalse(hc["physicalOutputEnabled"])

    def test_can_adapter_defaults_to_no_transmit_and_no_physical_output(self) -> None:
        adapter = CanMcuAdapter(channel="can0", bustype="socketcan")

        hc = adapter.health_check()

        self.assertTrue(hc["dryRun"])
        self.assertFalse(hc["physicalOutputEnabled"])

    def test_can_adapter_rejects_physical_bus_without_output_capability(self) -> None:
        adapter = CanMcuAdapter(
            channel="can0",
            bustype="socketcan",
            dry_run=False,
            physical_output_capable=False,
        )
        adapter._can_available = True
        adapter._bus = object()

        result = adapter.execute(
            {
                "kind": "SysCmd",
                "payload": {"arm": True},
            }
        )

        self.assertFalse(result["accepted"])
        self.assertFalse(result["physicalOutput"])

    def test_can_adapter_package_reexport(self) -> None:
        """__init__.py üzerinden içe aktarım çalışmalı."""
        adapter = CanMcuAdapterPkg(channel="test", bustype="virtual", dry_run=True)
        self.assertIsInstance(adapter, HardwareAdapterBase)

    def test_v1_fire_fails_closed_without_fresh_armed_mcu_status(self) -> None:
        adapter = CanMcuAdapter(
            channel="test",
            bustype="virtual",
            dry_run=False,
            physical_output_capable=False,
        )
        adapter._can_available = True
        adapter._bus = object()

        result = adapter.execute({
            "commandId": "FIRE-NO-STATUS",
            "kind": "FireIntent",
            "payload": {"stage": 1},
        })

        self.assertFalse(result["accepted"])
        self.assertEqual(result["resultCode"], "FIRE_PREFLIGHT_NO_STATUS")

    def test_fire_preflight_requires_interlock_and_encoder_health(self) -> None:
        adapter = CanMcuAdapter(
            channel="test",
            bustype="virtual",
            dry_run=False,
            physical_output_capable=False,
        )
        adapter._status.update({
            "receivedAt": fixed_clock(),
            "state": "ARMED",
            "estopActive": False,
            "fireReady": False,
            "encoderOk": True,
            "faultCode": 0,
        })
        self.assertEqual(adapter._fire_preflight_error(), "FIRE_PREFLIGHT_STALE_STATUS")

        adapter._status["receivedAt"] = datetime.now(UTC).isoformat().replace("+00:00", "Z")
        self.assertEqual(adapter._fire_preflight_error(), "FIRE_PREFLIGHT_INTERLOCK_OPEN")
        adapter._status["fireReady"] = True
        adapter._status["encoderOk"] = False
        self.assertEqual(adapter._fire_preflight_error(), "FIRE_PREFLIGHT_ENCODER_UNHEALTHY")
        adapter._status["encoderOk"] = True
        self.assertIsNone(adapter._fire_preflight_error())


# ---------------------------------------------------------------------------
# GpioEStopMonitor Testleri
# ---------------------------------------------------------------------------

class TestGpioEStopMonitor(unittest.TestCase):

    def test_on_can_estop_calls_callback(self) -> None:
        received: list[bool] = []
        monitor = GpioEStopMonitor(service_callback=received.append)
        monitor.on_can_estop(True)
        self.assertEqual(received, [True])
        monitor.on_can_estop(False)
        self.assertEqual(received, [True, False])

    def test_stop_without_gpio_raises_no_error(self) -> None:
        monitor = GpioEStopMonitor(service_callback=lambda _: None, gpio_pin=None)
        monitor.stop()    # RPi.GPIO yok → sessizce dönmeli


# ---------------------------------------------------------------------------
# OperatorService Entegrasyonu — set_estop / update_tracks
# ---------------------------------------------------------------------------

class TestOperatorServiceHardwareIntegration(unittest.TestCase):

    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        tel_path = Path(self.tempdir.name) / "test.jsonl"
        self.service = OperatorService(
            clock=fixed_clock,
            hardware=DryRunAdapter(clock=fixed_clock),
            telemetry=JsonlTelemetryStore(tel_path, clock=fixed_clock),
        )

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_set_estop_blocks_all_commands(self) -> None:
        self.service.set_estop(True)
        self.assertTrue(self.service.estop)

        # ManualAimCommand bloklanmalı
        result = self.service.handle_manual_aim({
            "panDeltaDeg": 1.0, "tiltDeltaDeg": 0.0,
            "rateLimitDegPerSec": 5.0, "deadmanActive": True, "dryRun": True,
        })
        self.assertFalse(result["result"]["accepted"])
        self.assertEqual(result["result"]["safetyBlockReason"], "BLOCKED_ESTOP")

        # FireIntent de bloklanmalı
        self.service.handle_stage_request({"stage": 1, "round": 1, "dryRun": True})
        self.service.handle_mode_request({"requestedMode": "manual", "dryRun": True})
        self.service.estop = True   # tekrar set et (mode request sonrası)
        result = self.service.handle_fire_intent({
            "targetId": "S1-ORDER-FUZE-01", "stage": 1, "round": 1,
            "operatorConfirm": True, "dryRun": True,
        })
        self.assertFalse(result["result"]["accepted"])
        self.assertEqual(result["result"]["safetyBlockReason"], "BLOCKED_ESTOP")

    def test_set_estop_requires_controlled_reset(self) -> None:
        self.service.set_estop(True)
        self.service.set_estop(False)
        self.assertTrue(self.service.estop)
        self.assertTrue(self.service.reset_estop("test-operator")["ok"])
        self.assertFalse(self.service.estop)

    def test_set_estop_logs_event(self) -> None:
        self.service.set_estop(True)
        estop_events = [e for e in self.service.events if e.get("decision") == "ESTOP_CHANGE"]
        self.assertTrue(len(estop_events) >= 1)
        self.assertTrue(estop_events[0]["payload"]["active"])

    def test_update_tracks_sets_perception_connected(self) -> None:
        result = self.service.update_tracks([
            {"trackId": "PERC-001", "targetType": "Bilinmeyen",
             "friendFoe": "Düşman", "rangeM": 8.5, "bearingDeg": -12.0, "confidence": 0.72},
        ], source="perception")
        self.assertTrue(result["ok"])
        self.assertEqual(result["count"], 1)
        self.assertTrue(self.service.perception_connected)

    def test_update_tracks_replaces_dry_run_tracks(self) -> None:
        self.service.update_tracks([
            {"trackId": "LIVE-A", "friendFoe": "Düşman", "rangeM": 10.0,
             "bearingDeg": 0.0, "confidence": 0.8},
        ])
        self.assertEqual(len(self.service.tracks), 1)
        self.assertEqual(self.service.tracks[0].trackId, "LIVE-A")
        self.assertEqual(self.service.tracks[0].source, "perception")

    def test_balloon_track_is_preserved_as_non_fire_candidate(self) -> None:
        result = self.service.update_tracks(
            [
                {
                    "trackId": "BAL-1",
                    "targetType": "Balon",
                    "friendFoe": "Bilinmeyen",
                    "rangeM": 8.0,
                    "bearingDeg": 1.0,
                    "confidence": 0.8,
                    "objectRole": "balloon",
                    "fireCandidate": True,
                }
            ]
        )

        self.assertTrue(result["ok"])
        track = self.service.tracks[0].to_dict()
        self.assertEqual(track["objectRole"], "balloon")
        self.assertFalse(track["fireCandidate"])

    def test_update_tracks_with_invalid_data_returns_error(self) -> None:
        result = self.service.update_tracks("not-a-list")  # type: ignore[arg-type]
        self.assertFalse(result["ok"])

    def test_update_tracks_empty_list_clears_tracks(self) -> None:
        self.service.update_tracks([])
        self.assertEqual(len(self.service.tracks), 0)
        self.assertTrue(self.service.perception_connected)

    def test_soft_limit_blocks_out_of_range_aim(self) -> None:
        # Pan limiti ±45° olarak ayarla
        self.service.pan_min_deg  = -45.0
        self.service.pan_max_deg  =  45.0
        self.service.tilt_min_deg = -20.0
        self.service.tilt_max_deg =  20.0
        # Aşama 1 manuel mod gerekli
        self.service.handle_stage_request({"stage": 1, "round": 1, "dryRun": True})
        self.service.handle_mode_request({"requestedMode": "manual", "dryRun": True})

        # Pan limiti içinde → kabul edilmeli
        r = self.service.handle_manual_aim({
            "panDeltaDeg": 10.0, "tiltDeltaDeg": 0.0,
            "rateLimitDegPerSec": 5.0, "deadmanActive": True, "dryRun": True,
        })
        self.assertTrue(r["result"]["accepted"], msg=str(r))

        # Pan limitini aşıyor (mevcut 0 + delta 50 = 50 > 45)
        r2 = self.service.handle_manual_aim({
            "panDeltaDeg": 50.0, "tiltDeltaDeg": 0.0,
            "rateLimitDegPerSec": 5.0, "deadmanActive": True, "dryRun": True,
        })
        self.assertFalse(r2["result"]["accepted"])
        self.assertEqual(r2["result"]["safetyBlockReason"], "BLOCKED_MOTION_ZONE")


# ---------------------------------------------------------------------------
# HTTP Endpoint Testleri (yeni endpoint'ler)
# ---------------------------------------------------------------------------

class TestNewHttpEndpoints(unittest.TestCase):

    @classmethod
    def setUpClass(cls) -> None:
        cls.tempdir = tempfile.TemporaryDirectory()
        tel_path = Path(cls.tempdir.name) / "http-test.jsonl"
        service = OperatorService(
            clock=fixed_clock,
            hardware=DryRunAdapter(clock=fixed_clock),
            telemetry=JsonlTelemetryStore(tel_path, clock=fixed_clock),
        )
        cls.server = build_http_server("127.0.0.1", 8099, service=service)
        cls.server_thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.server_thread.start()
        time.sleep(0.1)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.shutdown()
        cls.tempdir.cleanup()

    def _get(self, path: str) -> dict:
        resp = urlopen(f"http://127.0.0.1:8099{path}", timeout=3)
        return json.loads(resp.read())

    def _post(self, path: str, body: dict) -> dict:
        data = json.dumps(body).encode()
        req  = Request(f"http://127.0.0.1:8099{path}", data=data,
                       headers={"Content-Type": "application/json"}, method="POST")
        resp = urlopen(req, timeout=3)
        return json.loads(resp.read())

    def test_hardware_health_endpoint(self) -> None:
        result = self._get("/hardware/health")
        self.assertIn("adapter", result)
        self.assertFalse(result["physicalOutputEnabled"])

    def test_tracks_update_endpoint(self) -> None:
        body = {
            "source": "perception",
            "tracks": [
                {"trackId": "HTTP-T1", "friendFoe": "Düşman",
                 "rangeM": 7.5, "bearingDeg": -5.0, "confidence": 0.75},
            ],
        }
        result = self._post("/tracks/update", body)
        self.assertTrue(result["ok"])
        self.assertEqual(result["count"], 1)

    def test_estop_endpoint_activates_and_blocks(self) -> None:
        result = self._post("/estop", {"active": True})
        self.assertTrue(result["ok"])
        self.assertTrue(result["estop"])
        self.assertEqual(result["safety"]["blockReason"], "BLOCKED_ESTOP")

        # HTTP tek başına mandalı temizleyemez.
        with self.assertRaises(Exception):
            self._post("/estop", {"active": False})
        state = self._get("/state")
        self.assertTrue(state["safety"]["estop"])


if __name__ == "__main__":
    unittest.main()
