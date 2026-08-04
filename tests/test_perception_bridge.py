from __future__ import annotations

import importlib.util
import time
import unittest
from pathlib import Path
from unittest.mock import Mock


def load_perception_bridge_class() -> type:
    path = Path("perception/src/perception_bridge.py")
    spec = importlib.util.spec_from_file_location("gokkalkan_perception_bridge", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.PerceptionBridge


PerceptionBridge = load_perception_bridge_class()


class DummyCamera:
    def __init__(self) -> None:
        self.running = False

    def start(self) -> None:
        self.running = True

    def stop(self) -> None:
        self.running = False

    def get_latest_frame(self) -> None:
        return None

    def health(self) -> dict[str, object]:
        return {"running": self.running, "framesCaptured": 0}


class DummyProcessor:
    def process(self, _frame: object, *, stage: int) -> list[object]:
        return []

    def stats(self) -> dict[str, object]:
        return {"activeTracks": 0}


class DummyAccelerator:
    def __init__(self, hardware_ready: bool = True) -> None:
        self.hardware_ready = hardware_ready

    def health(self) -> dict[str, object]:
        return {
            "accelerator": "Raspberry Pi AI HAT+ 26 TOPS",
            "chip": "Hailo-8",
            "tops": 26,
            "hardwareReady": self.hardware_ready,
            "modelReady": False,
            "inferenceReady": False,
            "status": "READY" if self.hardware_ready else "CLI_MISSING",
        }


class PerceptionProcessBoundaryTest(unittest.TestCase):
    def test_bounded_queue_drops_oldest_and_keeps_latest_results(self) -> None:
        bridge = PerceptionBridge(outbound_queue_size=2)

        bridge._enqueue_tracks([{"trackId": "TRACK-1"}])
        bridge._enqueue_tracks([{"trackId": "TRACK-2"}])
        bridge._enqueue_tracks([{"trackId": "TRACK-3"}])

        first = bridge._outbound.get_nowait()
        second = bridge._outbound.get_nowait()
        self.assertEqual(first[0]["trackId"], "TRACK-2")
        self.assertEqual(second[0]["trackId"], "TRACK-3")
        self.assertEqual(bridge.health()["droppedUpdates"], 1)
        self.assertEqual(bridge.health()["outboundQueueCapacity"], 2)

    def test_process_threads_emit_heartbeat_and_stop_cleanly(self) -> None:
        bridge = PerceptionBridge(
            poll_hz=50,
            heartbeat_interval_sec=0.05,
        )
        bridge.camera = DummyCamera()
        bridge.processor = DummyProcessor()
        bridge._post_json = Mock(return_value=True)

        bridge.start()
        time.sleep(0.12)
        bridge.stop()

        paths = [call.args[0] for call in bridge._post_json.call_args_list]
        self.assertIn("/perception/heartbeat", paths)
        self.assertFalse(bridge.camera.running)
        self.assertFalse(bridge._thread.is_alive())
        self.assertFalse(bridge._sender_thread.is_alive())
        self.assertEqual(
            bridge.health()["processBoundary"],
            "separate-systemd-process",
        )

    def test_required_ai_hat_closes_heartbeat_when_hailo8_is_missing(self) -> None:
        bridge = PerceptionBridge(
            accelerator=DummyAccelerator(hardware_ready=False),
            accelerator_required=True,
        )
        bridge.camera = DummyCamera()
        bridge.camera.running = True

        healthy, reason = bridge._pipeline_health()

        self.assertFalse(healthy)
        self.assertEqual(reason, "accelerator_unhealthy")
        self.assertFalse(bridge.health()["accelerator"]["hardwareReady"])


if __name__ == "__main__":
    unittest.main()
