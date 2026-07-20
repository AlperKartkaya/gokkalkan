"""Gökkalkan Senaryo ve Mantık Testleri (TEKNOFEST Şartnamesine Uygun).

Bu testler, birim testlerin ötesinde uçtan uca sistem senaryolarını doğrular.
Örneğin:
  - WP-01 Manuel Mod geçişleri ve kısıtlamaları.
  - WP-02 Otonom takip esnasında E-Stop'un devreye girmesi.
  - WP-03 Dost/Düşman ve Menzil kısıtlamalarının (Güvenlik Katmanı) ateşlemeyi engellemesi.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from gokkalkan_backend.operator_api import DryRunHardwareAdapter, OperatorService
from gokkalkan_backend.telemetry_log import JsonlTelemetryStore


def mock_clock() -> str:
    return "2026-08-01T10:00:00Z"


class TestCompetitionScenarios(unittest.TestCase):

    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.telemetry = JsonlTelemetryStore(Path(self.tempdir.name) / "scenario.jsonl", clock=mock_clock)
        self.hardware = DryRunHardwareAdapter(clock=mock_clock)
        self.service = OperatorService(clock=mock_clock, hardware=self.hardware, telemetry=self.telemetry)

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_scenario_01_manual_mode_override_and_safety_gate(self) -> None:
        """Senaryo 1: WP-01 Manuel Mod.
        Operatör manuel moda geçer, ancak E-Stop'a basılırsa manuel kontrol bile engellenmelidir.
        """
        # Aşama 1 (Manuel) talep edilir
        r1 = self.service.handle_stage_request({"stage": 1, "round": 1, "dryRun": True})
        self.assertTrue(r1["result"]["accepted"])

        r2 = self.service.handle_mode_request({"requestedMode": "manual", "dryRun": True})
        self.assertTrue(r2["result"]["accepted"])

        # Manuel hedefleme denemesi (E-Stop yok, başarılı olmalı)
        r3 = self.service.handle_manual_aim({
            "panDeltaDeg": 5.0, "tiltDeltaDeg": 2.0,
            "rateLimitDegPerSec": 10.0, "deadmanActive": True, "dryRun": True
        })
        self.assertTrue(r3["result"]["accepted"])

        # E-Stop tetiklenir (örn: donanımdan veya UI'dan)
        self.service.set_estop(True)

        # Tekrar hareket denemesi engellenmelidir
        r4 = self.service.handle_manual_aim({
            "panDeltaDeg": 5.0, "tiltDeltaDeg": 2.0,
            "rateLimitDegPerSec": 10.0, "deadmanActive": True, "dryRun": True
        })
        self.assertFalse(r4["result"]["accepted"])
        self.assertEqual(r4["result"]["safetyBlockReason"], "BLOCKED_ESTOP")

    def test_scenario_02_autonomous_tracking_friend_foe_discrimination(self) -> None:
        """Senaryo 2: WP-02/03 Otonom Tespit ve Dost-Düşman Ayrımı.
        Aşama 3'te otonom moddayken hedefler gelir. Sadece 'Düşman' ve 'F16' (veya geçerli hedef) vurulabilir.
        Dost unsura ateşleme emri güvenlik katmanından dönmelidir.
        """
        self.service.handle_stage_request({"stage": 3, "round": 1, "dryRun": True})
        self.service.handle_mode_request({"requestedMode": "autonomous", "dryRun": True})

        # Sensörlerden 2 hedef gelir: Biri dost uçak, diğeri düşman iha
        self.service.update_tracks([
            {"trackId": "T-FRIEND-1", "targetType": "Uçak", "friendFoe": "Dost", "rangeM": 200, "bearingDeg": 10, "confidence": 0.9},
            {"trackId": "T-FOE-2", "targetType": "Mini/Micro İHA", "friendFoe": "Düşman", "rangeM": 10, "bearingDeg": -15, "confidence": 0.85},
        ])

        # Operatör yanlışlıkla dost unsuru hedef seçip ateş etmeye çalışır
        r_fire_friend = self.service.handle_fire_intent({
            "targetId": "T-FRIEND-1", "stage": 3, "round": 1, "operatorConfirm": True, "dryRun": True
        })
        self.assertFalse(r_fire_friend["result"]["accepted"], "Dost unsura ateşleme kesinlikle engellenmelidir")
        self.assertEqual(r_fire_friend["result"]["safetyBlockReason"], "BLOCKED_TARGET_GATE")

        # Operatör düşman unsura ateş etmeye çalışır
        r_fire_foe = self.service.handle_fire_intent({
            "targetId": "T-FOE-2", "stage": 3, "round": 1, "operatorConfirm": True, "dryRun": True
        })
        self.assertTrue(r_fire_foe["result"]["accepted"], "Düşman unsura ateşleme kabul edilmelidir (menzil uygunsa)")

    def test_scenario_03_telemetry_logging_integrity(self) -> None:
        """Senaryo 3: WP-05 Log/Telemetri bütünlüğü.
        Gerçekleşen kritik eylemlerin telemetriye (KTR/Görev Video kanıtı olarak) yazıldığını doğrular.
        """
        self.service.handle_stage_request({"stage": 2, "round": 2, "dryRun": True})
        self.service.handle_mode_request({"requestedMode": "autonomous", "dryRun": True})

        records = self.telemetry.read_all()
        # En azından StageRequest ve ModeRequest olmalı
        decisions = [r.get("payload", {}).get("decision") for r in records if "payload" in r]
        self.assertIn("StageRequest", decisions)
        self.assertIn("ModeRequest", decisions)

if __name__ == "__main__":
    unittest.main()
