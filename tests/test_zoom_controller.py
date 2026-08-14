from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "perception/src"))

from zoom_controller import ZoomController, ZoomObservation, ZoomState


def observation(
    *,
    track_id: str = "TRACK-1",
    confidence: float = 0.9,
    freshness_ms: float = 20.0,
    target_pixels: int = 1200,
    center: tuple[float, float] = (1152.0, 648.0),
    bbox_size: tuple[float, float] | None = (120.0, 80.0),
) -> ZoomObservation:
    return ZoomObservation(
        track_id=track_id,
        confidence=confidence,
        freshness_ms=freshness_ms,
        target_pixels=target_pixels,
        center_px=center,
        bbox_size_px=bbox_size,
    )


def test_zoom_requires_stable_track_and_uses_one_frame_lag_center() -> None:
    controller = ZoomController(confirm_frames=3)

    first = controller.update(observation(center=(1100.0, 620.0)))
    second = controller.update(observation(center=(1120.0, 630.0)))
    third = controller.update(observation(center=(1140.0, 640.0)))

    assert first.state == second.state == ZoomState.TRACK_CONFIRMING
    assert first.roi_size_px is second.roi_size_px is None
    assert third.state == ZoomState.TRACK_ROI_768
    assert third.roi_size_px == 768
    assert third.crop_center_px == (1120.0, 630.0)
    assert third.fire_authorized is False


def test_large_bbox_selects_wider_960_roi() -> None:
    controller = ZoomController(confirm_frames=1)

    decision = controller.update(observation(bbox_size=(500.0, 200.0)))

    assert decision.state == ZoomState.TRACK_ROI_960
    assert decision.roi_size_px == 960


def test_track_misses_expand_then_return_to_sahi_search() -> None:
    controller = ZoomController(confirm_frames=1)
    assert controller.update(observation()).state == ZoomState.TRACK_ROI_768

    first = controller.update(None)
    second = controller.update(None)
    third = controller.update(None)

    assert (first.state, first.roi_size_px) == (ZoomState.TRACK_ROI_960, 960)
    assert (second.state, second.roi_size_px) == (ZoomState.TRACK_ROI_1152, 1152)
    assert third.state == ZoomState.LOST_RETURN_TO_SEARCH
    assert third.roi_size_px is None
    assert third.fire_authorized is False


def test_stale_track_immediately_fails_closed_to_search() -> None:
    controller = ZoomController(confirm_frames=1)
    controller.update(observation())

    stale = controller.update(observation(freshness_ms=1000.0))
    missing = controller.update(None)

    assert stale.state == ZoomState.LOST_RETURN_TO_SEARCH
    assert missing.state == ZoomState.SEARCH_SAHI_SWEEP
    assert stale.fire_authorized is missing.fire_authorized is False


def test_track_id_change_restarts_confirmation() -> None:
    controller = ZoomController(confirm_frames=2)
    controller.update(observation())
    assert controller.update(observation()).state == ZoomState.TRACK_ROI_768

    changed = controller.update(observation(track_id="TRACK-2"))

    assert changed.state == ZoomState.TRACK_CONFIRMING
    assert changed.roi_size_px is None
