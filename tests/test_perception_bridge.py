from __future__ import annotations

import importlib.util
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
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


class ShapeOnlyFrame:
    def __init__(self, shape: tuple[int, int, int]) -> None:
        self.shape = shape


class MainStreamCamera(DummyCamera):
    def __init__(self) -> None:
        super().__init__()
        self.lores = ShapeOnlyFrame((720, 1280, 3))
        self.main = ShapeOnlyFrame((1296, 2304, 3))

    def get_latest_sample(self):
        return SimpleNamespace(
            image=self.lores,
            main_image=self.main,
            receive_monotonic_ns=time.monotonic_ns(),
        )


class MainSpaceDetector:
    input_stream = "sahi-main"

    def __init__(self) -> None:
        self.submitted = None

    def submit(self, frame, _timestamp) -> None:
        self.submitted = frame

    def latest(self, **_kwargs):
        from detector import Detection

        return [
            Detection(
                "dusman_f16_kirmizi",
                0.91,
                (1000.0, 500.0, 1300.0, 800.0),
            )
        ]

    def health(self):
        return {
            "inferenceReady": True,
            "lastError": None,
            "coordinateSpace": "main",
            "sourceResolution": [2304, 1296],
            "modelSha256": "a" * 64,
        }


class OneTrackProcessor(DummyProcessor):
    def process(self, _frame: object, *, stage: int) -> list[object]:
        return [
            SimpleNamespace(
                to_api_dict=lambda: {
                    "trackId": "TRACK-1",
                    "targetType": "Bilinmeyen",
                    "confidence": 0.5,
                    "bboxPx": [640.0, 360.0, 50.0, 30.0],
                    "yawErrorDeg": 0.2,
                    "pitchErrorDeg": -0.1,
                    "aimCalibrationId": "CAM-1",
                    "aimCalibrationHash": "b" * 64,
                    "aimValid": True,
                }
            )
        ]


class EmptyTrackProcessor(DummyProcessor):
    def process(self, _frame: object, *, stage: int) -> list[object]:
        return []


class PerceptionProcessBoundaryTest(unittest.TestCase):
    def test_sahi_detector_receives_main_frame_and_maps_detection_to_lores_track(self) -> None:
        detector = MainSpaceDetector()
        bridge = PerceptionBridge(detector=detector)
        bridge.camera = MainStreamCamera()
        bridge.processor = OneTrackProcessor()

        bridge._tick()

        tracks = bridge._outbound.get_nowait()
        self.assertIs(detector.submitted, bridge.camera.main)
        self.assertEqual(tracks[0]["targetType"], "F16")
        self.assertEqual(tracks[0]["classificationState"], "CONFIRMED")
        self.assertEqual(tracks[0]["modelSha256"], "a" * 64)
        self.assertTrue(tracks[0]["aimValid"])
        self.assertEqual(tracks[0]["aimCalibrationId"], "CAM-1")

    def test_sahi_detection_creates_track_when_hsv_finds_nothing(self) -> None:
        detector = MainSpaceDetector()
        bridge = PerceptionBridge(detector=detector)
        bridge.camera = MainStreamCamera()
        bridge.processor = EmptyTrackProcessor()

        bridge._tick()

        tracks = bridge._outbound.get_nowait()
        self.assertEqual(len(tracks), 1)
        self.assertEqual(tracks[0]["trackId"], "MODEL-000001")
        self.assertEqual(tracks[0]["targetType"], "F16")
        self.assertEqual(tracks[0]["rangeM"], 0.0)
        self.assertEqual(
            tracks[0]["rangeSource"],
            "unavailable-awaiting-lidar-fusion",
        )
        self.assertFalse(tracks[0]["aimValid"])

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
