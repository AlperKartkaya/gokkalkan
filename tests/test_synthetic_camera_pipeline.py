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
    build_sahi_search_views,
    build_track_square_view,
    build_variant_record,
    crop_rect,
    degrade_image,
    letterbox,
    square_crop_rect,
    uniform_resize,
)


def test_crop_rect_clamps_tracking_error_to_image_bounds() -> None:
    assert crop_rect(width=1280, height=720, factor=2.0) == (320, 180, 640, 360)
    assert crop_rect(
        width=1280,
        height=720,
        factor=2.0,
        center_error_px=(10_000, 10_000),
    ) == (640, 360, 640, 360)


def test_high_res_roi_preserves_native_crop_before_model_letterbox() -> None:
    x = np.linspace(0, 255, 2304, dtype=np.uint8)
    image = np.repeat(x[np.newaxis, :, np.newaxis], 1296, axis=0)
    image = np.repeat(image, 3, axis=2)

    high_res, high_res_meta = apply_zoom(image, mode="high_res_roi", factor=2.0)
    application, application_meta = apply_zoom(
        image, mode="application_crop", factor=2.0
    )

    assert high_res.shape == (648, 1152, 3)
    assert application.shape == (720, 1280, 3)
    assert high_res_meta["cropRectPx"] == [576, 324, 1152, 648]
    assert application_meta["cropRectPx"] == [320, 180, 640, 360]
    assert high_res_meta["preCropResolution"] == [2304, 1296]
    assert application_meta["preCropResolution"] == [1280, 720]
    assert high_res_meta["acquisitionPath"] == ("FULL_FOV_HIGH_RES_MAIN_SOFTWARE_CROP")


def test_letterbox_preserves_16_by_9_aspect_without_upscaling_roi() -> None:
    image = np.zeros((648, 1152, 3), dtype=np.uint8)

    model_input, metadata = letterbox(image)

    assert model_input.shape == (640, 640, 3)
    assert metadata["modelContentRectPx"] == [0, 140, 640, 360]
    assert metadata["modelPaddingPx"] == [0, 140, 0, 140]
    assert metadata["upsampledBeforeModel"] is False


@pytest.mark.parametrize("factor", [1.5, 2.0, 3.0])
def test_runtime_high_res_roi_factors_never_upsample_before_model(
    factor: float,
) -> None:
    image = np.zeros((1296, 2304, 3), dtype=np.uint8)

    roi, _ = apply_zoom(image, mode="high_res_roi", factor=factor)
    _, metadata = letterbox(roi)

    assert metadata["upsampledBeforeModel"] is False


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

    first = degrade_image(image, seed=123, blur_kernel=3, noise_std=2.0)
    second = degrade_image(image, seed=123, blur_kernel=3, noise_std=2.0)
    different = degrade_image(image, seed=124, blur_kernel=3, noise_std=2.0)

    assert np.array_equal(first, second)
    assert not np.array_equal(first, different)


def test_default_camera_degradation_does_not_invent_codec_artifacts() -> None:
    image = np.full((80, 120, 3), 127, dtype=np.uint8)

    result = degrade_image(image, seed=123, blur_kernel=0, noise_std=0)

    assert np.array_equal(result, image)


def test_sahi_search_views_use_eight_square_tiles_without_padding() -> None:
    image = np.zeros((1296, 2304, 3), dtype=np.uint8)
    mask = np.zeros((1296, 2304), dtype=np.uint8)
    mask[500:700, 700:900] = 255

    views = build_sahi_search_views(image, mask)

    assert len(views) == 8
    assert views[0]["image"].shape == (768, 768, 3)
    assert views[0]["modelInput"].shape == (640, 640, 3)
    assert all(view["metadata"]["modelPaddingPx"] == [0, 0, 0, 0] for view in views)
    assert [view["metadata"]["sliceIndex"] for view in views] == list(range(8))
    assert any(view["metadata"]["truncatedBySlice"] for view in views)


def test_track_square_view_clamps_center_and_never_upsamples() -> None:
    image = np.zeros((1296, 2304, 3), dtype=np.uint8)
    mask = np.zeros((1296, 2304), dtype=np.uint8)
    mask[0:100, 0:100] = 255

    view = build_track_square_view(
        image,
        mask,
        roi_size_px=768,
        predicted_center_px=(10.0, 10.0),
        center_error_px=(-100.0, -100.0),
    )

    assert view["metadata"]["roiRectFullFramePx"] == [0, 0, 768, 768]
    assert view["metadata"]["upsampledBeforeModel"] is False
    assert view["modelInput"].shape == (640, 640, 3)


def test_square_model_preprocess_rejects_artificial_upsample() -> None:
    with pytest.raises(Exception, match="upsample"):
        uniform_resize(np.zeros((320, 320, 3), dtype=np.uint8))
    with pytest.raises(Exception, match="640"):
        square_crop_rect(
            image_width=2304,
            image_height=1296,
            size_px=320,
            center_px=(1000.0, 600.0),
        )
