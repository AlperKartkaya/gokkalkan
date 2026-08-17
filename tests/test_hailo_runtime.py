from __future__ import annotations

import sys
from pathlib import Path

import pytest


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "perception/src"))

from gokkalkan_hailo_runtime import MODEL_LABELS, _normalize_nms_output  # noqa: E402


def test_normalizes_picamera2_hailo_nms_coordinates() -> None:
    output = [[] for _ in MODEL_LABELS]
    output[2] = [[0.10, 0.20, 0.40, 0.60, 0.91]]

    assert _normalize_nms_output(output, 640, 640) == [
        {
            "label": "dusman_f16_kirmizi",
            "confidence": pytest.approx(0.91),
            "bbox": pytest.approx([128.0, 64.0, 384.0, 256.0]),
        }
    ]


def test_rejects_hef_with_wrong_class_contract() -> None:
    with pytest.raises(ValueError, match="class count mismatch"):
        _normalize_nms_output([[]], 640, 640)

