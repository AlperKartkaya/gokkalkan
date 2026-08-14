from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "perception" / "src"))

from detection_tracks import DetectionTrackProjector  # noqa: E402
from detector import Detection  # noqa: E402


def test_model_detection_becomes_stable_fail_closed_api_track() -> None:
    projector = DetectionTrackProjector()
    first = projector.update(
        [Detection("dusman_f16_kirmizi", 0.91, (1000, 500, 1200, 700))],
        stage=3,
        source_size=(2304, 1296),
        output_size=(1280, 720),
        receive_monotonic_ns=100,
        model_sha256="abc",
    )[0]
    second = projector.update(
        [Detection("dusman_f16_kirmizi", 0.92, (1010, 500, 1210, 700))],
        stage=3,
        source_size=(2304, 1296),
        output_size=(1280, 720),
        receive_monotonic_ns=200,
        model_sha256="abc",
    )[0]

    assert first["trackId"] == second["trackId"] == "MODEL-000001"
    assert second["targetType"] == "F16"
    assert second["friendFoe"] == "Düşman"
    assert second["rangeM"] == 0.0
    assert second["rangeSource"] == "unavailable-awaiting-lidar-fusion"
    assert second["aimValid"] is False
    assert second["bboxPx"][2] < 200


def test_ambiguous_or_pre_stage_three_detection_never_asserts_enemy() -> None:
    ambiguous = DetectionTrackProjector().update(
        [Detection("AMBIGUOUS_CLASS", 0.7, (100, 100, 200, 200))],
        stage=3,
        source_size=(2304, 1296),
        output_size=(1280, 720),
        receive_monotonic_ns=100,
        model_sha256=None,
    )[0]
    assert ambiguous["friendFoe"] == "Bilinmeyen"
    assert ambiguous["classificationState"] == "AMBIGUOUS_CLASS"

    stage_two = DetectionTrackProjector().update(
        [Detection("dusman_f16_kirmizi", 0.9, (100, 100, 200, 200))],
        stage=2,
        source_size=(2304, 1296),
        output_size=(1280, 720),
        receive_monotonic_ns=100,
        model_sha256=None,
    )[0]
    assert stage_two["friendFoe"] == "Bilinmeyen"

