from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "perception/src"))

from roi_geometry import (
    high_res_roi_from_model_center,
    letterbox_content_rect,
    model_bbox_to_source_roi,
    model_point_to_source,
    square_roi_from_source_center,
)


def test_full_view_letterbox_uses_640_by_360_content() -> None:
    assert letterbox_content_rect((1280, 720)).as_tuple() == (0, 140, 640, 360)


def test_model_center_maps_to_search_and_high_resolution_centers() -> None:
    assert model_point_to_source((320.0, 320.0), source_size=(1280, 720)) == (
        640.0,
        360.0,
    )
    assert high_res_roi_from_model_center((320.0, 320.0), factor=2.0).as_tuple() == (
        576,
        324,
        1152,
        648,
    )


def test_roi_is_clamped_without_changing_its_16_by_9_size() -> None:
    roi = high_res_roi_from_model_center((0.0, 140.0), factor=3.0)

    assert roi.as_tuple() == (0, 0, 768, 432)


def test_padding_point_is_clamped_to_source_edge() -> None:
    assert model_point_to_source((320.0, 0.0), source_size=(1280, 720)) == (
        640.0,
        0.0,
    )


def test_square_roi_clamps_to_main_frame_without_changing_size() -> None:
    assert square_roi_from_source_center(
        (10.0, 10.0), roi_size_px=768
    ).as_tuple() == (0, 0, 768, 768)
    assert square_roi_from_source_center(
        (2290.0, 1280.0), roi_size_px=1152
    ).as_tuple() == (1152, 144, 1152, 1152)


def test_square_model_bbox_maps_back_to_full_frame() -> None:
    roi = square_roi_from_source_center((1152.0, 648.0), roi_size_px=768)

    assert model_bbox_to_source_roi((100.0, 200.0, 300.0, 400.0), roi=roi) == (
        888.0,
        504.0,
        1128.0,
        744.0,
    )
