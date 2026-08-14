from __future__ import annotations

from pathlib import Path
import sys
import time

import pytest

np = pytest.importorskip("numpy")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "perception/src"))

from detector import Detection  # noqa: E402
from hailo_sahi_adapter import HailoSahiAdapter  # noqa: E402
from sahi_geometry import generate_slice_windows, greedy_nmm, mark_class_ambiguities  # noqa: E402
from sahi_search import (  # noqa: E402
    LatestWinsSahiSearch,
    SahiSearchConfig,
    SahiSearchEngine,
)


def config() -> SahiSearchConfig:
    return SahiSearchConfig.from_toml(ROOT / "config/perception/search.toml")


def test_slice_windows_match_sahi_768_contract() -> None:
    windows = generate_slice_windows(
        image_width=2304,
        image_height=1296,
        slice_width=768,
        slice_height=768,
        overlap_width_ratio=0.25,
        overlap_height_ratio=0.25,
    )

    assert [window.as_xyxy() for window in windows] == [
        (0, 0, 768, 768),
        (576, 0, 1344, 768),
        (1152, 0, 1920, 768),
        (1536, 0, 2304, 768),
        (0, 528, 768, 1296),
        (576, 528, 1344, 1296),
        (1152, 528, 1920, 1296),
        (1536, 528, 2304, 1296),
    ]


def test_greedy_nmm_merges_same_class_and_marks_cross_class_conflict() -> None:
    merged = greedy_nmm(
        [
            Detection("F16", 0.9, (100, 100, 200, 200)),
            Detection("F16", 0.8, (110, 110, 190, 190)),
            Detection("DRONE", 0.7, (105, 105, 195, 195)),
        ],
        match_threshold=0.5,
        match_metric="IOS",
        class_agnostic=False,
    )
    safe = mark_class_ambiguities(merged, ios_threshold=0.5)

    assert len(merged) == 2
    assert [item.label for item in safe] == ["AMBIGUOUS_CLASS"]


def test_class_ambiguity_keeps_unrelated_conflicts_separate() -> None:
    safe = mark_class_ambiguities(
        [
            Detection("DOST_F16", 0.9, (0, 0, 100, 100)),
            Detection("DUSMAN_F16", 0.8, (10, 10, 90, 90)),
            Detection("DOST_HELI", 0.9, (500, 500, 600, 600)),
            Detection("DUSMAN_HELI", 0.8, (510, 510, 590, 590)),
        ],
        ios_threshold=0.5,
    )

    assert [item.label for item in safe] == ["AMBIGUOUS_CLASS", "AMBIGUOUS_CLASS"]
    assert safe[0].bbox_xyxy == (0, 0, 100, 100)
    assert safe[1].bbox_xyxy == (500, 500, 600, 600)


def test_hailo_adapter_resizes_batch_and_filters_outputs(tmp_path: Path) -> None:
    model = tmp_path / "model.hef"
    model.write_bytes(b"fixture")
    seen_shapes: list[tuple[int, ...]] = []

    def runner(batch):
        seen_shapes.extend(item.shape for item in batch)
        return [
            [
                {"label": "F16", "confidence": 0.9, "bbox": [10, 20, 110, 120]},
                {"label": "UNKNOWN", "confidence": 0.99, "bbox": [0, 0, 1, 1]},
            ]
            for _ in batch
        ]

    adapter = HailoSahiAdapter(
        model,
        runner,
        allowed_labels={"F16"},
        label_map={"F16": "Savaş Uçağı"},
    )
    result = adapter.detect_batch([np.zeros((768, 768, 3), dtype=np.uint8)] * 2)

    assert seen_shapes == [(640, 640, 3), (640, 640, 3)]
    assert [[d.label for d in group] for group in result] == [
        ["Savaş Uçağı"],
        ["Savaş Uçağı"],
    ]
    assert adapter.health()["lastBatchSize"] == 2


def test_search_engine_maps_tile_detection_to_full_frame_and_confirms_on_second_sweep() -> None:
    class FakeBatchDetector:
        model_size = (640, 640)

        def detect_batch(self, tiles):
            results = [[] for _ in tiles]
            results[0] = [Detection("F16", 0.9, (100, 100, 200, 200))]
            return results

        def health(self):
            return {"inferenceReady": True}

    engine = SahiSearchEngine(FakeBatchDetector(), config())
    frame = np.zeros((1296, 2304, 3), dtype=np.uint8)

    first = engine.run_sweep(frame, 1_000_000_000)
    second = engine.run_sweep(frame, 1_010_000_000)

    assert first.tile_count == 8
    assert first.confirmed_detections == ()
    assert len(second.confirmed_detections) == 1
    assert second.confirmed_detections[0].bbox_xyxy == pytest.approx(
        (120.0, 120.0, 240.0, 240.0)
    )


def test_engine_switches_to_single_square_roi_then_recovers_to_search() -> None:
    class SearchThenTrackDetector:
        model_size = (640, 640)

        def __init__(self) -> None:
            self.track_should_miss = False

        def detect_batch(self, tiles):
            if len(tiles) == 8:
                results = [[] for _ in tiles]
                results[0] = [Detection("F16", 0.9, (100, 100, 200, 200))]
                return results
            if self.track_should_miss:
                return [[]]
            return [[Detection("F16", 0.92, (270, 270, 370, 370))]]

        def health(self):
            return {"inferenceReady": True}

    detector = SearchThenTrackDetector()
    engine = SahiSearchEngine(detector, config())
    frame = np.zeros((1296, 2304, 3), dtype=np.uint8)

    assert engine.run_frame(frame, 1).mode == "SEARCH_SAHI_SWEEP"
    assert engine.run_frame(frame, 2).mode == "SEARCH_SAHI_SWEEP"
    track = engine.run_frame(frame, 3)

    assert track.mode == "TRACK_SQUARE_ROI"
    assert track.tile_count == 1
    assert track.roi_rect_full_frame_px == (0, 0, 768, 768)
    assert len(track.confirmed_detections) == 1

    detector.track_should_miss = True
    first_miss = engine.run_frame(frame, 4)
    second_miss = engine.run_frame(frame, 5)
    returned = engine.run_frame(frame, 6)

    assert first_miss.roi_rect_full_frame_px[2:] == (768, 768)
    assert second_miss.roi_rect_full_frame_px[2:] == (960, 960)
    assert returned.mode == "SEARCH_SAHI_SWEEP"
    assert returned.tile_count == 8


def test_latest_wins_search_drops_stale_result() -> None:
    class EmptyDetector:
        model_size = (640, 640)

        def detect_batch(self, tiles):
            return [[] for _ in tiles]

        def health(self):
            return {"inferenceReady": True}

    scheduler = LatestWinsSahiSearch(SahiSearchEngine(EmptyDetector(), config()))
    scheduler.start()
    timestamp = time.monotonic_ns()
    scheduler.submit(np.zeros((1296, 2304, 3), dtype=np.uint8), timestamp)
    for _ in range(100):
        if scheduler.health()["resultAvailable"]:
            break
        time.sleep(0.002)

    assert scheduler.latest(now_monotonic_ns=timestamp) == []
    assert scheduler.latest(now_monotonic_ns=timestamp + 500_000_000) == []
    assert scheduler.health()["configuredSearchTileCount"] == 8
    scheduler.stop()
