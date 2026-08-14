from __future__ import annotations

import sys
from pathlib import Path

import pytest

np = pytest.importorskip("numpy")
pytest.importorskip("cv2")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "perception/synthetic/tools"))

from apply_camera_pipeline import (
    apply_zoom,
    bbox_from_mask,
    build_variant_record,
    crop_rect,
    degrade_image,
)


def test_crop_rect_clamps_tracking_error_to_image_bounds() -> None:
    assert crop_rect(width=1280, height=720, factor=2.0) == (320, 180, 640, 360)
    assert crop_rect(
        width=1280,
        height=720,
        factor=2.0,
        center_error_px=(10_000, 10_000),
    ) == (640, 360, 640, 360)


def test_sensor_roi_and_application_crop_follow_different_order() -> None:
    x = np.linspace(0, 255, 2304, dtype=np.uint8)
    image = np.repeat(x[np.newaxis, :, np.newaxis], 1296, axis=0)
    image = np.repeat(image, 3, axis=2)

    sensor, sensor_meta = apply_zoom(image, mode="sensor_roi", factor=2.0)
    application, application_meta = apply_zoom(
        image, mode="application_crop", factor=2.0
    )

    assert sensor.shape == application.shape == (720, 1280, 3)
    assert sensor_meta["cropRectPx"] == [576, 324, 1152, 648]
    assert application_meta["cropRectPx"] == [320, 180, 640, 360]
    assert sensor_meta["preCropResolution"] == [2304, 1296]
    assert application_meta["preCropResolution"] == [1280, 720]
    assert not np.array_equal(sensor, application)


def test_mask_zoom_updates_pixels_bbox_and_preserves_world_group() -> None:
    mask = np.zeros((720, 1280), dtype=np.uint8)
    mask[300:400, 570:710] = 255
    zoomed, metadata = apply_zoom(
        mask, mode="application_crop", factor=2.0, is_mask=True
    )
    base = {
        "recordId": "REC-1",
        "worldId": "WORLD-1",
        "groupId": "WORLD-1",
        "presentationClass": "dusman_f16_kirmizi",
    }

    variant = build_variant_record(
        base,
        zoom_metadata=metadata,
        before_mask=mask,
        after_mask=zoomed,
    )

    assert bbox_from_mask(mask) == (570, 300, 140, 100)
    assert variant["worldId"] == variant["groupId"] == "WORLD-1"
    assert variant["recordId"].startswith("REC-ZOOM-")
    assert (
        variant["zoom"]["targetPixelsAfterZoom"]
        > variant["zoom"]["targetPixelsBeforeZoom"]
    )
    assert variant["annotation"]["targetVisibleAfterZoom"] is True


def test_degradation_is_seed_deterministic() -> None:
    image = np.full((80, 120, 3), 127, dtype=np.uint8)

    first = degrade_image(image, seed=123)
    second = degrade_image(image, seed=123)
    different = degrade_image(image, seed=124)

    assert np.array_equal(first, second)
    assert not np.array_equal(first, different)
