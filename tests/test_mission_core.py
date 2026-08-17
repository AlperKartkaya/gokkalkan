from __future__ import annotations

import json
import tempfile
import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from dataclasses import FrozenInstanceError
from pathlib import Path
from typing import Callable
from urllib.request import Request, urlopen

from gokkalkan_backend.messages import (
    CommandEnvelope,
    MessageContractError,
)
from gokkalkan_backend.mission_core import (
    MissionCore,
    MissionCoreStopped,
)
from gokkalkan_backend.operator_api import DryRunHardwareAdapter, OperatorService
from gokkalkan_backend.operator_http_server import build_http_server
from gokkalkan_backend.telemetry_log import JsonlTelemetryStore


def fixed_clock() -> str:
    return "2026-07-25T12:00:00Z"


class MessageContractTest(unittest.TestCase):
    def test_command_envelope_is_versioned_complete_and_immutable(self) -> None:
        envelope = CommandEnvelope.create(
            run_id="RUN-TEST",
            sequence=1,
            source="test",
            kind="TracksUpdate",
            payload={"tracks": [{"trackId": "T-1"}]},
            command_id="CMD-TEST",
            causation_id="CAUSE-1",
            target_id="TARGET-1",
            track_id="T-1",
            source_sequence=7,
            wall_clock=fixed_clock,
            monotonic_ns=lambda: 1234,
        )

        serialized = envelope.to_dict()

        self.assertEqual(serialized["schemaVersion"], 1)
        self.assertEqual(serialized["runId"], "RUN-TEST")
        self.assertEqual(serialized["commandId"], "CMD-TEST")
        self.assertEqual(serialized["sequence"], 1)
        self.assertEqual(serialized["createdAtUtc"], fixed_clock())
        self.assertEqual(serialized["createdAtMonotonicNs"], 1234)
        self.assertEqual(serialized["causationId"], "CAUSE-1")
        self.assertEqual(serialized["targetId"], "TARGET-1")
        self.assertEqual(serialized["trackId"], "T-1")
        with self.assertRaises(TypeError):
            envelope.payload["other"] = True  # type: ignore[index]

    def test_unknown_schema_version_is_rejected(self) -> None:
        with self.assertRaisesRegex(
            MessageContractError,
            "unsupported message schema",
        ):
            CommandEnvelope.create(
                run_id="RUN",
                sequence=1,
                source="test",
                kind="ModeRequest",
                schema_version=2,
            )


class MissionCoreTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        telemetry = JsonlTelemetryStore(
            Path(self.tempdir.name) / "core.jsonl",
            clock=fixed_clock,
        )
        self.service = OperatorService(
            clock=fixed_clock,
            hardware=DryRunHardwareAdapter(clock=fixed_clock),
            telemetry=telemetry,
        )
        self.core = MissionCore(
            self.service,
            run_id="RUN-CORE-TEST",
            perception_timeout_sec=0.08,
        )
        self.core.start()

    def tearDown(self) -> None:
        self.core.stop()
        self.tempdir.cleanup()

    def test_only_owner_thread_can_mutate_bound_service(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "Mission Core owner"):
            self.service.handle_mode_request({"requestedMode": "safe"})

        result = self.core.submit(
            "ModeRequest",
            {"requestedMode": "safe"},
        )

        self.assertFalse(result["physicalOutput"])  # type: ignore[index]
        self.assertEqual(self.core.snapshot()["mode"], "safe")

    def test_mission_state_is_frozen_and_contains_required_domains(self) -> None:
        state = self.core.state

        self.assertEqual(state.run_id, "RUN-CORE-TEST")
        self.assertEqual(state.stage, 1)
        self.assertEqual(state.round, 1)
        self.assertFalse(state.armed)
        self.assertFalse(state.maintenance_active)
        self.assertEqual(state.lifecycle, "RUNNING")
        with self.assertRaises(FrozenInstanceError):
            state.mode = "safe"  # type: ignore[misc]

    def test_periodic_snapshot_keeps_mission_clock_fresh_without_poll_mutation(
        self,
    ) -> None:
        self.core.snapshot_interval_sec = 0.05
        self.core.submit("StageRequest", {"stage": 1, "round": 1})
        first = self.core.snapshot()
        self._wait_until(
            lambda: self.core.snapshot()["snapshotVersion"]
            > first["snapshotVersion"],
            timeout=0.5,
        )
        later = self.core.snapshot()

        self.assertGreater(
            later["missionElapsedSec"],
            first["missionElapsedSec"],
        )

    def test_concurrent_commands_have_one_contiguous_event_order(self) -> None:
        def submit(index: int) -> dict:
            return self.core.submit(  # type: ignore[return-value]
                "ModeRequest",
                {"requestedMode": "autonomous", "requestIndex": index},
                command_id=f"CMD-CONCURRENT-{index:03d}",
            )

        with ThreadPoolExecutor(max_workers=16) as pool:
            outcomes = list(pool.map(submit, range(80)))

        sequences = sorted(outcome["sequence"] for outcome in outcomes)
        event_ids = {outcome["eventId"] for outcome in outcomes}
        command_ids = {outcome["commandId"] for outcome in outcomes}

        self.assertEqual(sequences, list(range(1, 81)))
        self.assertEqual(len(event_ids), 80)
        self.assertEqual(len(command_ids), 80)
        self.assertEqual(self.core.state.last_event_sequence, 80)
        self.assertEqual(
            [event["sequence"] for event in self.core.snapshot()["coreEvents"]],
            list(range(80, 30, -1)),
        )

    def test_simultaneous_http_can_and_sensor_sources_share_one_event_order(
        self,
    ) -> None:
        # Isolate concurrent ingress ordering from the independently tested
        # perception watchdog. Coverage instrumentation can otherwise make the
        # 80 ms test timeout expire between valid TracksUpdate commands.
        self.core.perception_timeout_sec = float("inf")

        def submit(index: int) -> dict:
            if index % 3 == 0:
                return self.core.submit(  # type: ignore[return-value]
                    "ModeRequest",
                    {"requestedMode": "safe"},
                    source="operator-http",
                    command_id=f"CMD-MIXED-{index:03d}",
                )
            if index % 3 == 1:
                command_id = self.core.publish_threadsafe(
                    "TracksUpdate",
                    {"source": "perception", "tracks": []},
                    source="perception",
                )
            else:
                command_id = self.core.publish_threadsafe(
                    "EStopChange",
                    {"active": index % 2 == 0},
                    source="can-estop",
                )
            self._wait_until(
                lambda: bool(
                    self.core.command_status(command_id)
                    and self.core.command_status(command_id)["completed"]  # type: ignore[index]
                ),
                timeout=1.0,
            )
            status = self.core.command_status(command_id)
            assert status is not None
            return status

        with ThreadPoolExecutor(max_workers=15) as pool:
            outcomes = list(pool.map(submit, range(60)))

        self.assertEqual(
            sorted(outcome["sequence"] for outcome in outcomes),
            list(range(1, 61)),
        )
        self.assertEqual(
            len({outcome["eventId"] for outcome in outcomes}),
            60,
        )
        self.assertEqual(self.core.state.last_event_sequence, 60)

    def test_watchdog_and_external_commands_share_one_contiguous_event_order(
        self,
    ) -> None:
        self.core.perception_timeout_sec = 0.0

        tracks = self.core.submit(
            "TracksUpdate",
            {"source": "perception", "tracks": []},
            source="perception",
        )
        self._wait_until(
            lambda: self.core.state.last_event_sequence == 2,
            timeout=1.0,
        )
        mode = self.core.submit(
            "ModeRequest",
            {"requestedMode": "safe"},
            source="operator-http",
        )

        events = self.core.snapshot()["coreEvents"]
        self.assertEqual(tracks["sequence"], 1)  # type: ignore[index]
        self.assertEqual(mode["sequence"], 3)  # type: ignore[index]
        self.assertEqual(
            [event["sequence"] for event in events],
            [3, 2, 1],
        )
        self.assertEqual(
            [event["payload"]["kind"] for event in events],
            ["ModeRequest", "PerceptionHealth", "TracksUpdate"],
        )
        self.assertEqual(
            events[1]["causationId"],
            "perception-heartbeat-watchdog",
        )

    def test_duplicate_is_idempotent_but_changed_content_is_rejected(self) -> None:
        first = self.core.submit(
            "ModeRequest",
            {"requestedMode": "safe"},
            command_id="CMD-IDEMPOTENT",
        )
        version = self.core.state.version
        duplicate = self.core.submit(
            "ModeRequest",
            {"requestedMode": "safe"},
            command_id="CMD-IDEMPOTENT",
        )

        self.assertFalse(first["deduplicated"])  # type: ignore[index]
        self.assertTrue(duplicate["deduplicated"])  # type: ignore[index]
        self.assertEqual(first["eventId"], duplicate["eventId"])  # type: ignore[index]
        self.assertEqual(self.core.state.version, version)
        with self.assertRaisesRegex(MessageContractError, "different content"):
            self.core.submit(
                "ModeRequest",
                {"requestedMode": "autonomous"},
                command_id="CMD-IDEMPOTENT",
            )

    def test_duplicate_and_out_of_order_sensor_events_are_deterministic(self) -> None:
        accepted = self.core.submit(
            "TracksUpdate",
            {
                "source": "perception",
                "tracks": [
                    {
                        "trackId": "TRACK-2",
                        "targetType": "F16",
                        "friendFoe": "Düşman",
                        "rangeM": 12,
                        "bearingDeg": 1,
                        "confidence": 0.9,
                    }
                ],
            },
            source="perception",
            source_sequence=2,
        )
        rejected = self.core.submit(
            "TracksUpdate",
            {"source": "perception", "tracks": []},
            source="perception",
            source_sequence=1,
        )

        self.assertTrue(accepted["accepted"])  # type: ignore[index]
        self.assertFalse(rejected["accepted"])  # type: ignore[index]
        self.assertEqual(  # type: ignore[index]
            rejected["error"],
            "OUT_OF_ORDER_SOURCE_SEQUENCE",
        )
        self.assertEqual(
            self.core.snapshot()["tracks"][0]["trackId"],
            "TRACK-2",
        )

    def test_external_thread_bridge_and_perception_watchdog_fail_closed(self) -> None:
        thread = threading.Thread(
            target=lambda: self.core.publish_threadsafe(
                "EStopChange",
                {"active": True},
                source="can-estop",
            )
        )
        thread.start()
        thread.join(timeout=1)
        self._wait_until(lambda: self.core.state.estop_active)

        self.core.submit(
            "PerceptionHealth",
            {"healthy": True},
            source="perception",
            source_sequence=1,
        )
        self.assertTrue(self.core.state.perception_healthy)
        self._wait_until(
            lambda: "PERCEPTION_UNHEALTHY" in self.core.state.faults,
            timeout=1.0,
        )

        self.assertFalse(self.core.state.perception_healthy)
        self.assertFalse(self.service.live_arm_enabled)
        self.assertFalse(self.core.snapshot()["physicalOutputEnabled"])

    def test_stop_drains_commands_then_rejects_new_work(self) -> None:
        command_ids = [
            self.core.submit(
                "ModeRequest",
                {"requestedMode": "safe", "index": index},
                wait=False,
            )
            for index in range(20)
        ]

        self.core.stop()

        self.assertEqual(self.core.state.lifecycle, "STOPPED")
        self.assertTrue(
            all(
                self.core.command_status(str(command_id))["completed"]  # type: ignore[index]
                for command_id in command_ids
            )
        )
        with self.assertRaises(MissionCoreStopped):
            self.core.submit("ModeRequest", {"requestedMode": "safe"})

    def _wait_until(
        self,
        predicate: Callable[[], bool],
        timeout: float = 0.5,
    ) -> None:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if predicate():
                return
            time.sleep(0.01)
        self.fail("condition was not reached before timeout")


class MissionCoreHttpTest(unittest.TestCase):
    def test_http_commands_are_traceable_and_state_sse_is_available(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            service = OperatorService(
                clock=fixed_clock,
                telemetry=JsonlTelemetryStore(Path(tmp) / "http-core.jsonl"),
            )
            server = build_http_server("127.0.0.1", 0, service=service)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base = f"http://127.0.0.1:{server.server_address[1]}"
            try:
                payload = json.dumps(
                    {
                        "schemaVersion": 1,
                        "requestedMode": "safe",
                        "commandId": "CMD-HTTP-TRACE",
                    }
                ).encode()
                request = Request(
                    f"{base}/mode",
                    data=payload,
                    headers={
                        "Content-Type": "application/json",
                        "Idempotency-Key": "CMD-HTTP-TRACE",
                    },
                    method="POST",
                )
                with urlopen(request, timeout=2) as response:
                    outcome = json.loads(response.read())
                with urlopen(
                    f"{base}/commands/CMD-HTTP-TRACE",
                    timeout=2,
                ) as response:
                    status = json.loads(response.read())
                stream_request = Request(
                    f"{base}/state/stream?after=0",
                    headers={"Origin": "http://127.0.0.1:5173"},
                )
                stream = urlopen(stream_request, timeout=2)
                try:
                    stream_cors = stream.headers["Access-Control-Allow-Origin"]
                    lines = [stream.readline().decode("utf-8") for _ in range(3)]
                finally:
                    stream.close()
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)

        self.assertEqual(outcome["commandId"], "CMD-HTTP-TRACE")
        self.assertTrue(outcome["eventId"].startswith("EVT-"))
        self.assertTrue(outcome["completed"])
        self.assertEqual(status["eventId"], outcome["eventId"])
        self.assertEqual(stream_cors, "*")
        self.assertTrue(lines[0].startswith("id: "))
        self.assertEqual(lines[1], "event: state\n")
        self.assertTrue(lines[2].startswith("data: {"))


if __name__ == "__main__":
    unittest.main()
