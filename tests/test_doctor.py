from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from gokkalkan_backend.doctor import run_doctor


class DoctorTest(unittest.TestCase):
    def test_sim_doctor_is_read_only_and_tolerates_offline_hardware(self) -> None:
        original = Path("config/runtime/sim.toml").read_text(encoding="utf-8")
        with tempfile.TemporaryDirectory() as tmp:
            telemetry = Path(tmp) / "telemetry" / "doctor.jsonl"
            config = Path(tmp) / "sim.toml"
            config.write_text(
                original.replace(
                    'path = "telemetry_data/operator-api-sim.jsonl"',
                    f'path = "{telemetry}"',
                ),
                encoding="utf-8",
            )

            report = run_doctor(
                config,
                api_url="http://127.0.0.1:1",
            )

        self.assertTrue(report["ok"])
        self.assertFalse(report["physicalOutputAttempted"])
        statuses = {
            item["name"]: item["status"]  # type: ignore[index]
            for item in report["checks"]  # type: ignore[union-attr]
        }
        self.assertEqual(statuses["config"], "PASS")
        self.assertEqual(statuses["can"], "PASS")
        self.assertEqual(statuses["api"], "WARN")

    def test_invalid_config_fails_without_hardware_attempt(self) -> None:
        report = run_doctor("/does/not/exist.toml")

        self.assertFalse(report["ok"])
        self.assertFalse(report["physicalOutputAttempted"])
        self.assertEqual(report["checks"][0]["name"], "config")  # type: ignore[index]


if __name__ == "__main__":
    unittest.main()
