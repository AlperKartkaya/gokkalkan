from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path("perception/src").resolve()))

from aim_alignment import (
    AimCalibration,
    _apply_distortion_correction,
    calibrated_aim_error,
)
from camera_node import CameraNode
from evaluate_dataset import evaluate_records
from frame_processor import (
    CentroidTracker,
    FrameProcessor,
    _hungarian_match,
    is_probable_balloon_shape,
)
from gokkalkan_backend.lidar_adapter import TFA50LSerialAdapter, TFA50LSerialConfig
from gokkalkan_backend.calibration_workflow import evaluate_lidar_observations
from gokkalkan_backend.range_fusion import (
    FusedRangeDecision,
    LidarCalibration,
    TimedRange,
    TrackBearing,
    YawRangeAssociator,
    world_track_bearing,
)
from gokkalkan_backend.operator_api import OperatorService
from gokkalkan_backend.mission_core import MissionCore
from gokkalkan_backend.sensor_pipeline import TFA50LFusionPipeline
from gokkalkan_backend.sensor_runtime import SensorRuntimeIdentity, TFA50LSensorRuntime

pytestmark = [pytest.mark.safety, pytest.mark.replay]


def test_balloon_shape_filter_is_conservative_and_dependency_free() -> None:
    assert is_probable_balloon_shape(area=615.75, perimeter=87.96, width=29, height=29)
    assert not is_probable_balloon_shape(area=600, perimeter=120, width=45, height=18)


def test_stage2_perception_accepts_red_and_rejects_blue_targets() -> None:
    np = pytest.importorskip("numpy")
    pytest.importorskip("cv2")
    frame = np.zeros((100, 100, 3), dtype=np.uint8)
    frame[10:40, 10:40] = (255, 0, 0)
    frame[60:90, 60:90] = (0, 0, 255)

    candidates = FrameProcessor(
        image_width=100,
        image_height=100,
        min_area_px=100,
    ).process(frame, stage=2)

    assert len(candidates) == 1
    assert candidates[0].friend_foe == "Bilinmeyen"
    assert candidates[0].cx < 50


def test_stage3_perception_classifies_red_enemy_and_blue_friend() -> None:
    np = pytest.importorskip("numpy")
    pytest.importorskip("cv2")
    frame = np.zeros((100, 100, 3), dtype=np.uint8)
    frame[10:40, 10:40] = (255, 0, 0)
    frame[60:90, 60:90] = (0, 0, 255)

    candidates = FrameProcessor(
        image_width=100,
        image_height=100,
        min_area_px=100,
    ).process(frame, stage=3)

    assert {candidate.friend_foe for candidate in candidates} == {"Düşman", "Dost"}


def test_stage3_does_not_classify_red_balloon_as_enemy_target() -> None:
    np = pytest.importorskip("numpy")
    cv2 = pytest.importorskip("cv2")
    frame = np.zeros((120, 120, 3), dtype=np.uint8)
    cv2.circle(frame, (30, 80), 14, (255, 0, 0), -1)
    frame[15:45, 70:105] = (0, 163, 224)  # güncel dost camgöbeği #00A3E0

    candidates = FrameProcessor(
        image_width=120,
        image_height=120,
        min_area_px=100,
    ).process(frame, stage=3)

    targets = [item for item in candidates if item.object_role == "target"]
    balloons = [item for item in candidates if item.object_role == "balloon"]
    assert [candidate.friend_foe for candidate in targets] == ["Dost"]
    assert len(balloons) == 1
    assert balloons[0].friend_foe == "Bilinmeyen"
    assert balloons[0].fire_candidate is False


def test_camera_frame_envelope_exposes_both_clocks_and_mock_is_not_live_healthy() -> None:
    camera = CameraNode(width=8, height=8, fps=100, backend="mock")
    camera.start()
    try:
        for _ in range(100):
            sample = camera.get_latest_sample()
            if sample is not None:
                break
            import time

            time.sleep(0.001)
        assert sample is not None
        assert sample.camera_timestamp_ns > 0
        assert sample.receive_monotonic_ns > 0
        assert sample.main_image.shape == (1296, 2304, 3)
        health = camera.health()
        assert health["status"] == "SIMULATED"
        assert health["healthy"] is False
        assert health["simulated"] is True
        assert health["mainStreamAvailable"] is True
    finally:
        camera.stop()


def valid_calibration(*, mount_revision: str = "BRIDGE-R1") -> LidarCalibration:
    return LidarCalibration(
        calibration_id="CAL-001",
        calibrated_at="2026-07-25T12:00:00Z",
        operator="test-operator",
        mount_height_m=1.1,
        yaw_offset_deg=0.5,
        pitch_offset_deg=0.0,
        vertical_band_min_m=0.8,
        vertical_band_max_m=1.4,
        mount_revision=mount_revision,
        verified_ranges_m=(5.0, 10.0, 15.0),
    )


def test_yaw_range_fusion_requires_calibration_alignment_freshness_and_stability() -> None:
    associator = YawRangeAssociator(
        valid_calibration(), current_mount_revision="BRIDGE-R1", required_consecutive=3
    )
    track = TrackBearing("TRACK-1", 10.5, 1_000_000_000)
    decisions = [
        associator.associate(
            TimedRange(value, 1_000_000_000 + index * 20_000_000, "5C", True, "VALID"),
            TrackBearing(track.track_id, track.bearing_deg, 1_000_000_000 + index * 20_000_000),
            turret_yaw_deg=10.0,
            now_monotonic_ns=1_000_000_000 + index * 20_000_000,
        )
        for index, value in enumerate((10.0, 10.05, 10.0))
    ]
    assert [item.reason for item in decisions[:2]] == [
        "RANGE_NOT_STABLE",
        "RANGE_NOT_STABLE",
    ]
    assert decisions[-1].accepted is True
    assert decisions[-1].source == "fused:tfa50-l+camera+yaw"
    assert decisions[-1].distance_m == 10.0


def test_camera_relative_bearing_is_converted_to_encoder_world_frame() -> None:
    assert world_track_bearing(
        turret_yaw_deg=10.0,
        image_bearing_deg=0.25,
        camera_yaw_offset_deg=0.25,
    ) == 10.5


def test_mount_change_and_bad_range_fail_closed() -> None:
    associator = YawRangeAssociator(
        valid_calibration(), current_mount_revision="BRIDGE-R2"
    )
    decision = associator.associate(
        TimedRange(None, 1, "5C FF FF 01", False, "NO_DETECTION"),
        TrackBearing("T", 0.0, 1),
        turret_yaw_deg=0.0,
        now_monotonic_ns=1,
    )
    assert not decision.accepted
    assert decision.reason == "CALIBRATION_INVALID_OR_MOUNT_CHANGED"


class FakeSerial:
    def __init__(self, chunks: list[bytes]) -> None:
        self.chunks = chunks
        self.closed = False
        self.writes: list[bytes] = []

    def read(self, _size: int = 64) -> bytes:
        if not self.chunks:
            raise OSError("disconnected")
        return self.chunks.pop(0)

    def close(self) -> None:
        self.closed = True

    def write(self, data: bytes) -> int:
        self.writes.append(data)
        return len(data)


def test_uart_adapter_records_valid_invalid_disconnect_and_health() -> None:
    now = [1_000_000_000]
    serial = FakeSerial([bytes.fromhex("5C 02 11 00 5C 0A 00 F5")])
    telemetry: list[tuple[str, dict[str, object]]] = []
    adapter = TFA50LSerialAdapter(
        TFA50LSerialConfig(
            "/dev/fake", 115200, 100, stale_ms=100, initialize_device=False
        ),
        serial_factory=lambda **_kwargs: serial,
        telemetry=lambda kind, payload: telemetry.append((kind, payload)),
        monotonic_ns=lambda: now[0],
    )

    events = adapter.poll()

    assert [event.reason for event in events] == [
        "CHECKSUM_OR_FRAME_INVALID",
        "VALID",
    ]
    assert events[-1].distance_m == 0.1
    assert adapter.health()["healthy"] is True
    now[0] += 200_000_000
    assert adapter.health()["stale"] is True
    assert adapter.poll() == []
    assert serial.closed is True
    assert adapter.health()["connected"] is False
    assert any(kind == "lidar_disconnected" for kind, _ in telemetry)


def test_uart_adapter_reads_identity_sets_frequency_and_restores_ranging() -> None:
    serial = FakeSerial(
        [
            bytes.fromhex("5A 8A 02 00 00 73"),
            bytes.fromhex("5A 8D 02 10 01 5F"),
            bytes.fromhex("5A 96 02 03 02 62"),
            bytes.fromhex("5A 8B 02 E7 03 78"),
            bytes.fromhex("5C 0A 00 F5"),
        ]
    )
    adapter = TFA50LSerialAdapter(
        TFA50LSerialConfig("/dev/fake", 460800, 1000, stale_ms=100),
        serial_factory=lambda **_kwargs: serial,
        monotonic_ns=lambda: 1_000_000_000,
    )
    assert adapter.poll()[-1].distance_m == 0.1
    manifest = adapter.manifest()
    assert manifest["serialNumber"] == "S00272"
    assert manifest["firmwareVersion"] == "V2.3"
    assert serial.writes[0] == bytes.fromhex("5A 0A 02 00 00 F3")
    assert serial.writes[-1] == bytes.fromhex("5A 0A 02 02 00 F1")


def test_tracker_ids_and_motion_are_deterministic_across_replay() -> None:
    detections = [(10.0, 10.0, 4.0, 4.0, 16.0, "red")]
    results = []
    for _ in range(2):
        tracker = CentroidTracker(max_disappeared=1)
        first = tracker.update(detections, timestamp_ns=1_000_000_000)
        second = tracker.update(
            [(20.0, 10.0, 4.0, 4.0, 16.0, "red")],
            timestamp_ns=2_000_000_000,
        )
        results.append((list(first), second["PERC-000001"]["velocity_x_px_s"]))
    assert results == [(["PERC-000001"], 10.0), (["PERC-000001"], 10.0)]


@dataclass
class AimTrack:
    cx: float
    cy: float
    receive_monotonic_ns: int


def test_aim_alignment_is_calibrated_and_rejects_stale_track() -> None:
    calibration = AimCalibration(
        "AIM-CAL-1", 640, 360, 0.05, 0.04,
        status="ACTIVE", evidence_sha256="a" * 64,
    )
    fresh = calibrated_aim_error(
        AimTrack(650, 350, 1_000_000_000),
        calibration,
        now_monotonic_ns=1_100_000_000,
    )
    stale = calibrated_aim_error(
        AimTrack(650, 350, 1),
        calibration,
        now_monotonic_ns=1_000_000_000,
    )
    assert fresh["valid"] is True
    assert fresh["yawErrorDeg"] == 0.5
    assert fresh["pitchErrorDeg"] == 0.4
    assert stale["reason"] == "TRACK_STALE"


def test_distortion_correction_inverts_observed_brown_conrady_pixel() -> None:
    calibration = AimCalibration(
        "AIM-CAL-DISTORTION",
        640,
        360,
        0.05,
        0.04,
        status="ACTIVE",
        evidence_sha256="b" * 64,
        distortion=(-0.2, 0.03, 0.001, -0.001, 0.0),
    )
    focal_x = (180.0 / 3.141592653589793) / calibration.yaw_deg_per_px
    focal_y = (180.0 / 3.141592653589793) / calibration.pitch_deg_per_px
    ideal_x, ideal_y = 0.35, -0.18
    radius2 = ideal_x * ideal_x + ideal_y * ideal_y
    radial = 1 - 0.2 * radius2 + 0.03 * radius2 * radius2
    distorted_x = (
        ideal_x * radial
        + 2 * 0.001 * ideal_x * ideal_y
        - 0.001 * (radius2 + 2 * ideal_x * ideal_x)
    )
    distorted_y = (
        ideal_y * radial
        + 0.001 * (radius2 + 2 * ideal_y * ideal_y)
        - 2 * 0.001 * ideal_x * ideal_y
    )

    corrected = _apply_distortion_correction(
        calibration.principal_x_px + distorted_x * focal_x,
        calibration.principal_y_px + distorted_y * focal_y,
        calibration,
    )

    assert corrected[0] == pytest.approx(640 + ideal_x * focal_x, abs=1e-4)
    assert corrected[1] == pytest.approx(360 + ideal_y * focal_y, abs=1e-4)


def test_hungarian_assignment_is_complete_and_globally_minimal() -> None:
    cost = [[17.0, 17.0], [1.0, 19.0]]
    assignments = _hungarian_match(cost)

    assert assignments == [(0, 1), (1, 0)]
    assert sum(cost[row][column] for row, column in assignments) == 18.0


def test_dataset_report_exposes_confusion_precision_recall_latency_and_fps() -> None:
    report = evaluate_records(
        [
            {"expected": "red", "predicted": "red", "latencyMs": 10, "elapsedSec": 0.02},
            {"expected": "blue", "predicted": "red", "latencyMs": 20, "elapsedSec": 0.03},
        ]
    )
    assert report["confusionMatrix"]["blue"]["red"] == 1
    assert report["perClass"]["red"]["precision"] == 0.5
    assert report["perClass"]["blue"]["recall"] == 0.0
    assert report["meanLatencyMs"] == 15.0
    assert report["fps"] == 40.0


def test_mission_core_only_applies_accepted_fused_range() -> None:
    service = OperatorService()
    track_id = service.snapshot()["tracks"][0]["trackId"]
    accepted = FusedRangeDecision(
        True, "FUSED_STABLE_RANGE", track_id, 10.0, "fused:tfa50-l+camera+yaw", "hash", 3
    )
    rejected = FusedRangeDecision(
        False, "LIDAR_STALE", track_id, None, "tfa50-l", "hash", 0
    )
    assert service.apply_fused_range(accepted)["ok"] is True
    fused = next(track for track in service.snapshot()["tracks"] if track["trackId"] == track_id)
    assert fused["rangeM"] == 10.0
    assert fused["source"] == "fused"
    assert service.apply_fused_range(rejected)["ok"] is False
    assert service.lidar_ok is False
    assert service.sensor_adapter_connected is False


def test_fused_range_command_requires_trusted_sensor_source() -> None:
    service = OperatorService()
    core = MissionCore(service)
    core.start()
    try:
        track_id = core.snapshot()["tracks"][0]["trackId"]
        payload = {
            "accepted": True,
            "reason": "FUSED_STABLE_RANGE",
            "trackId": track_id,
            "rangeM": 10.0,
            "source": "fused:tfa50-l+camera+yaw",
            "calibrationHash": "hash",
            "sampleCount": 3,
        }
        rejected = core.submit("FusedRangeUpdate", payload, source="operator-http")
        accepted = core.submit("FusedRangeUpdate", payload, source="sensor-tfa50-l")
        assert rejected["accepted"] is False
        assert rejected["error"] == "UNSUPPORTED_COMMAND"
        assert accepted["accepted"] is True
        assert accepted["domain"]["source"] == "fused:tfa50-l+camera+yaw"
    finally:
        core.stop()


def test_calibration_report_requires_real_evidence_and_all_ranges_yaws() -> None:
    observations = [
        {
            "expectedRangeM": expected,
            "measuredRangeM": expected,
            "yawPosition": yaw,
        }
        for expected in (5.0, 10.0, 15.0)
        for yaw in ("left", "center", "right", "center", "center")
    ]
    simulated = evaluate_lidar_observations(
        observations,
        evidence_class="SOFTWARE_FIXTURE",
        mount_revision="BRIDGE-R1",
        calibration_id="CAL-1",
    )
    physical = evaluate_lidar_observations(
        observations,
        evidence_class="PHYSICAL_TFA50_L",
        mount_revision="BRIDGE-R1",
        calibration_id="CAL-1",
    )
    assert simulated["physicalGatePassed"] is False
    assert physical["physicalGatePassed"] is True


def test_sensor_pipeline_forwards_each_decision_to_mission_callback() -> None:
    class Adapter:
        def poll(self) -> list[TimedRange]:
            return [
                TimedRange(10.0, 1_000_000_000 + index * 20_000_000, "5C", True, "VALID")
                for index in range(3)
            ]

    decisions: list[FusedRangeDecision] = []
    associator = YawRangeAssociator(
        valid_calibration(), current_mount_revision="BRIDGE-R1", required_consecutive=3
    )
    clock_values = iter((1_000_000_000, 1_020_000_000, 1_040_000_000))
    pipeline = TFA50LFusionPipeline(
        Adapter(),  # type: ignore[arg-type]
        associator,
        selected_track=lambda: TrackBearing(
            "TRACK-1",
            10.5,
            1_000_000_000 + len(decisions) * 20_000_000,
        ),
        turret_yaw_deg=lambda: 10.0,
        on_decision=decisions.append,
        monotonic_ns=lambda: next(clock_values),
    )
    assert pipeline.tick()[-1].accepted is True
    assert len(decisions) == 3


def test_production_sensor_runtime_queues_fusion_instead_of_mutating_service() -> None:
    now = 1_000_000_000

    class Hardware:
        def health_check(self):
            return {"lastStatusAgeSec": 0.01, "mcuStatus": {"panDeg": 10.0}}

    class Service:
        hardware = Hardware()

    class Core:
        service = Service()

        def __init__(self):
            self.published = []

        def snapshot(self):
            return {
                "missionFlow": {"selectedTargetId": "TRACK-1"},
                "tracks": [{
                    "trackId": "TRACK-1",
                    "bearingDeg": 10.5,
                    "receiveMonotonicNs": now,
                }],
            }

        def publish_threadsafe(self, kind, payload, **options):
            self.published.append((kind, payload, options))
            return "queued"

    class Adapter:
        config = TFA50LSerialConfig("/dev/fake", 460800, 1000, stale_ms=200)

        def __init__(self):
            self.samples = [TimedRange(10.0, now, "5C", True, "VALID")]

        def poll(self):
            return self.samples

        def health(self):
            return {
                "connected": True,
                "serialNumber": "S001",
                "firmwareVersion": "V1.0",
            }

        def close(self):
            pass

    core = Core()
    runtime = TFA50LSensorRuntime(
        core,  # type: ignore[arg-type]
        Adapter(),  # type: ignore[arg-type]
        YawRangeAssociator(valid_calibration(), current_mount_revision="BRIDGE-R1", required_consecutive=1),
        SensorRuntimeIdentity("S001", "V1.0", "BRIDGE-R1"),
        monotonic_ns=lambda: now,
    )

    assert runtime.tick()[0].accepted is True
    assert core.published[0][0] == "FusedRangeUpdate"
    assert core.published[0][2]["source"] == "sensor-tfa50-l-runtime"
    assert runtime.health()["identityAllowed"] is True


def test_production_sensor_runtime_rejects_stale_yaw_and_wrong_identity() -> None:
    class Core:
        class Service:
            class Hardware:
                def health_check(self):
                    return {"lastStatusAgeSec": 1.0, "mcuStatus": {"panDeg": 0.0}}
            hardware = Hardware()
        service = Service()

        def snapshot(self):
            return {"missionFlow": {"selectedTargetId": None}, "tracks": []}

    class Adapter:
        config = TFA50LSerialConfig("/dev/fake", 460800, 1000, stale_ms=100)
        def health(self):
            return {"connected": True, "serialNumber": "WRONG", "firmwareVersion": "V1.0"}
        def poll(self):
            return []
        def close(self):
            pass

    runtime = TFA50LSensorRuntime(
        Core(),  # type: ignore[arg-type]
        Adapter(),  # type: ignore[arg-type]
        YawRangeAssociator(valid_calibration(), current_mount_revision="BRIDGE-R1"),
        SensorRuntimeIdentity("S001", "V1.0", "BRIDGE-R1"),
    )
    with pytest.raises(ValueError, match="identity"):
        runtime.tick()
    with pytest.raises(ValueError, match="yaw is stale"):
        runtime._turret_yaw()
