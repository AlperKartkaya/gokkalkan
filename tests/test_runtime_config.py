from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from gokkalkan_backend.arduino_motor_adapter import FIELD_PROFILE_ID
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
                self.assertEqual(settings.mcu.field_profile, FIELD_PROFILE_ID)

    def test_pi_sim_allows_only_local_operator_origins(self) -> None:
        settings = load_runtime_config("config/runtime/pi-sim.toml")

        self.assertEqual(
            settings.api.allowed_origins,
            (
                "http://127.0.0.1:4173",
                "http://localhost:4173",
                "http://[::1]:4173",
            ),
        )
        self.assertEqual(settings.sensors.lidar_port, "/dev/ttyAMA0")
        self.assertFalse(settings.sensors.lidar_input_enabled)

    def test_live_profile_enables_tfa50l_input_runtime(self) -> None:
        settings = load_runtime_config("config/runtime/live.toml")

        self.assertTrue(settings.sensors.lidar_input_enabled)

    def test_runtime_config_maps_limits_and_timeouts_to_launch(self) -> None:
        settings = load_runtime_config("config/runtime/hil.toml")

        launch = settings.launch_config()

        self.assertEqual(launch.mode, "HIL")
        self.assertEqual(launch.mcu_baudrate, 115_200)
        self.assertEqual(launch.mcu_transport, "arduino_serial")
        self.assertEqual(launch.mcu_field_profile, FIELD_PROFILE_ID)
        self.assertEqual(launch.heartbeat_timeout_sec, 2.0)
        self.assertLess(
            settings.safety.pan_min_deg,
            settings.safety.pan_max_deg,
        )

    def test_hil_cli_override_cannot_select_physical_usb(self) -> None:
        settings = load_runtime_config("config/runtime/hil.toml")

        with self.assertRaisesRegex(RuntimeConfigError, "loop://"):
            settings.with_cli_overrides(
                mcu_port="/dev/serial/by-id/pico",
            )

    def test_live_missing_interlock_provider_is_rejected(self) -> None:
        text = Path("config/runtime/live.toml").read_text(encoding="utf-8")
        text = text.replace(
            'interlock_provider = "arduino-and-physical-estop-chain"',
            'interlock_provider = ""',
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "live.toml"
            path.write_text(text, encoding="utf-8")

            with self.assertRaisesRegex(RuntimeConfigError, "interlock_provider"):
                load_runtime_config(path)

    def test_blank_arduino_field_profile_is_rejected(self) -> None:
        text = Path("config/runtime/hil.toml").read_text(encoding="utf-8")
        text = text.replace(
            f'field_profile = "{FIELD_PROFILE_ID}"',
            'field_profile = ""',
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "hil.toml"
            path.write_text(text, encoding="utf-8")

            with self.assertRaisesRegex(RuntimeConfigError, "field_profile"):
                load_runtime_config(path)

    def test_missing_safety_table_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bad.toml"
            path.write_text(
                'schema_version=1\nprofile="SIM"\n[api]\nhost="127.0.0.1"\n',
                encoding="utf-8",
            )

            with self.assertRaisesRegex(RuntimeConfigError, r"\[mcu\]"):
                load_runtime_config(path)


if __name__ == "__main__":
    unittest.main()
