from __future__ import annotations

import sys
from pathlib import Path

import pytest

np = pytest.importorskip("numpy")
pytest.importorskip("h5py")
pytest.importorskip("jsonschema")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "perception/synthetic/tools"))

from validate_render_batch import RenderBatchValidationError, validate_arrays


def valid_arrays() -> dict[str, np.ndarray]:
    classes = np.zeros((40, 60), dtype=np.int64)
    classes[10:20, 20:40] = 1
    classes[25:32, 27:34] = 7
    return {
        "colors": np.zeros((40, 60, 3), dtype=np.uint8),
        "depth": np.ones((40, 60), dtype=np.float32),
        "instance_segmaps": classes.copy(),
        "class_segmaps": classes,
    }


def test_render_arrays_require_matching_target_and_balloon_layers() -> None:
    report = validate_arrays(valid_arrays())

    assert report["resolution"] == [60, 40]
    assert report["classPixelCounts"][1] == 200
    assert report["classPixelCounts"][7] == 49


def test_render_arrays_fail_when_balloon_is_missing() -> None:
    arrays = valid_arrays()
    arrays["class_segmaps"][arrays["class_segmaps"] == 7] = 0

    with pytest.raises(RenderBatchValidationError, match="balon"):
        validate_arrays(arrays)


def test_render_arrays_fail_on_resolution_mismatch() -> None:
    arrays = valid_arrays()
    arrays["depth"] = np.ones((20, 30), dtype=np.float32)

    with pytest.raises(RenderBatchValidationError, match="çözünürlüğü"):
        validate_arrays(arrays)
