from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from gokkalkan_backend.runtime_config import (
    RuntimeConfigError,
    load_runtime_config,
)


class RuntimeConfigTest(unittest.TestCase):
    def test_all_repository_profiles_validate(self) -> None:
        expected = {
            "sim.toml": "SIM",
            "hil.toml": "HIL",
            "hil-physical.toml": "HIL",
            "live.toml": "LIVE",
            "pi-sim.toml": "SIM",
        }
        for filename, profile in expected.items():
            with self.subTest(filename=filename):
                settings = load_runtime_config(Path("config/runtime") / filename)
                self.assertEqual(settings.profile, profile)
                self.assertEqual(settings.schema_version, 1)

    def test_runtime_config_maps_limits_and_timeouts_to_launch(self) -> None:
        settings = load_runtime_config("config/runtime/hil.toml")

        launch = settings.launch_config()

        self.assertEqual(launch.mode, "HIL")
        self.assertEqual(launch.can_bitrate, 500_000)
        self.assertEqual(launch.heartbeat_timeout_sec, 2.0)
        self.assertLess(
            settings.safety.pan_min_deg,
            settings.safety.pan_max_deg,
        )

    def test_hil_cli_override_cannot_select_physical_can(self) -> None:
        settings = load_runtime_config("config/runtime/hil.toml")

        with self.assertRaisesRegex(RuntimeConfigError, "virtual CAN"):
            settings.with_cli_overrides(
                can_channel="can0",
                can_bustype="socketcan",
            )

    def test_live_missing_interlock_provider_is_rejected(self) -> None:
        text = Path("config/runtime/live.toml").read_text(encoding="utf-8")
        text = text.replace(
            'interlock_provider = "pico-and-physical-estop-chain"',
            'interlock_provider = ""',
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "live.toml"
            path.write_text(text, encoding="utf-8")

            with self.assertRaisesRegex(RuntimeConfigError, "interlock_provider"):
                load_runtime_config(path)

    def test_missing_safety_table_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bad.toml"
            path.write_text(
                'schema_version=1\nprofile="SIM"\n[api]\nhost="127.0.0.1"\n',
                encoding="utf-8",
            )

            with self.assertRaisesRegex(RuntimeConfigError, r"\[can\]"):
                load_runtime_config(path)


if __name__ == "__main__":
    unittest.main()
