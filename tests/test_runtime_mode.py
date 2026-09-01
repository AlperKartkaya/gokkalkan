from __future__ import annotations

import unittest
from typing import Any

from gokkalkan_backend.runtime_mode import (
    DEFAULT_ARDUINO_FIELD_PROFILE,
    LivePreflight,
    RuntimeConfigurationError,
    RuntimeLaunchConfig,
    build_runtime_service,
)


class RecordingHardware:
    def __init__(self, **options: Any) -> None:
        self.options = options
        self.started = False
        self.commands: list[dict[str, Any]] = []

    def start(self) -> None:
        self.started = True

    def execute(self, command: dict[str, Any]) -> dict[str, Any]:
        self.commands.append(command)
        return {
            "accepted": True,
            "physicalOutput": bool(self.options.get("physical_output_capable")),
        }

    def health_check(self) -> dict[str, Any]:
        return {
            "busConnected": self.started,
            "picoReachable": self.started,
            "physicalOutputEnabled": bool(
                self.started and self.options.get("physical_output_capable")
            ),
        }

    def close(self) -> None:
        self.started = False


class RecordingFactory:
    def __init__(self) -> None:
        self.instances: list[RecordingHardware] = []

    def __call__(self, **options: Any) -> RecordingHardware:
        hardware = RecordingHardware(**options)
        self.instances.append(hardware)
        return hardware


class RuntimeModeTest(unittest.TestCase):
    def test_default_sim_mode_never_constructs_mcu_adapter(self) -> None:
        factory = RecordingFactory()

        service = build_runtime_service(
            RuntimeLaunchConfig(),
            mcu_adapter_factory=factory,
        )

        self.assertEqual(service.runtime_mode, "SIM")
        self.assertTrue(service.dry_run)
        self.assertEqual(factory.instances, [])
        self.assertEqual(service.events[0]["payload"]["runtimeMode"], "SIM")

    def test_hil_rejects_physical_usb_before_reviewed_enable(self) -> None:
        factory = RecordingFactory()

        with self.assertRaisesRegex(RuntimeConfigurationError, "loop://"):
            build_runtime_service(
                RuntimeLaunchConfig(
                    mode="HIL",
                    mcu_port="/dev/serial/by-id/pico",
                ),
                mcu_adapter_factory=factory,
            )

        self.assertEqual(factory.instances, [])

    def test_hil_uses_usb_loopback_without_physical_output_capability(self) -> None:
        factory = RecordingFactory()

        service = build_runtime_service(
            RuntimeLaunchConfig(
                mode="HIL",
                mcu_port="loop://",
            ),
            mcu_adapter_factory=factory,
        )

        self.assertEqual(service.runtime_mode, "HIL")
        self.assertTrue(service.dry_run)
        self.assertEqual(len(factory.instances), 1)
        self.assertTrue(factory.instances[0].started)
        self.assertFalse(factory.instances[0].options["dry_run"])
        self.assertFalse(factory.instances[0].options["physical_output_capable"])
        self.assertEqual(
            factory.instances[0].options["expected_field_profile"],
            DEFAULT_ARDUINO_FIELD_PROFILE,
        )

    def test_reviewed_hil_physical_usb_enables_motor_output_capability(
        self,
    ) -> None:
        factory = RecordingFactory()
        service = build_runtime_service(
            RuntimeLaunchConfig(
                mode="HIL",
                mcu_port="/dev/serial/by-id/pico",
                hil_physical_mcu_enabled=True,
            ),
            mcu_adapter_factory=factory,
        )
        self.assertEqual(service.runtime_mode, "HIL")
        self.assertTrue(factory.instances[0].started)
        self.assertTrue(factory.instances[0].options["physical_output_capable"])
        self.assertEqual(
            factory.instances[0].options["expected_field_profile"],
            DEFAULT_ARDUINO_FIELD_PROFILE,
        )
        self.assertTrue(service.snapshot()["physicalOutputEnabled"])

    def test_live_mode_requires_explicit_enable_before_adapter_construction(self) -> None:
        factory = RecordingFactory()

        with self.assertRaisesRegex(RuntimeConfigurationError, "explicitly enabled"):
            build_runtime_service(
                RuntimeLaunchConfig(mode="LIVE", mcu_port="/dev/serial/by-id/pico"),
                mcu_adapter_factory=factory,
            )

        self.assertEqual(factory.instances, [])

    def test_live_mode_requires_physical_interlock_and_readiness(self) -> None:
        cases = (
            None,
            LivePreflight(
                physical_interlock_ready=False,
                backend_readiness_ok=True,
                source="test",
            ),
            LivePreflight(
                physical_interlock_ready=True,
                backend_readiness_ok=False,
                source="test",
            ),
        )

        for preflight in cases:
            with self.subTest(preflight=preflight):
                factory = RecordingFactory()
                with self.assertRaises(RuntimeConfigurationError):
                    build_runtime_service(
                        RuntimeLaunchConfig(
                            mode="LIVE",
                            live_output_enabled=True,
                            mcu_port="/dev/serial/by-id/pico",
                        ),
                        live_preflight=preflight,
                        mcu_adapter_factory=factory,
                    )
                self.assertEqual(factory.instances, [])

    def test_live_mode_constructs_output_capable_adapter_only_after_preflight(self) -> None:
        factory = RecordingFactory()

        service = build_runtime_service(
            RuntimeLaunchConfig(
                mode="LIVE",
                live_output_enabled=True,
                mcu_port="/dev/serial/by-id/pico",
            ),
            live_preflight=LivePreflight(
                physical_interlock_ready=True,
                backend_readiness_ok=True,
                source="physical-interlock-test-fixture",
            ),
            mcu_adapter_factory=factory,
        )

        self.assertEqual(service.runtime_mode, "LIVE")
        self.assertFalse(service.dry_run)
        self.assertFalse(service.live_arm_enabled)
        self.assertEqual(len(factory.instances), 1)
        self.assertTrue(factory.instances[0].options["physical_output_capable"])
        self.assertEqual(
            factory.instances[0].options["expected_field_profile"],
            DEFAULT_ARDUINO_FIELD_PROFILE,
        )
        self.assertTrue(factory.instances[0].started)

        blocked = service.handle_fire_intent(
            {
                "targetId": "DRY-RUN-F16-01",
                "stage": 3,
                "round": 1,
                "operatorConfirm": True,
                "dryRun": True,
            }
        )
        self.assertFalse(blocked["result"]["accepted"])
        self.assertEqual(blocked["result"]["safetyBlockReason"], "BLOCKED_ARMING")
        self.assertEqual(factory.instances[0].commands, [])


if __name__ == "__main__":
    unittest.main()
