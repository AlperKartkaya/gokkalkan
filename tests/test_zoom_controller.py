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
    center: tuple[float, float] = (640.0, 360.0),
) -> ZoomObservation:
    return ZoomObservation(
        track_id=track_id,
        confidence=confidence,
        freshness_ms=freshness_ms,
        target_pixels=target_pixels,
        center_px=center,
    )


def test_zoom_requires_stable_track_and_uses_one_frame_lag_center() -> None:
    controller = ZoomController(confirm_frames=3)

    first = controller.update(observation(center=(600.0, 340.0)))
    second = controller.update(observation(center=(620.0, 350.0)))
    third = controller.update(observation(center=(640.0, 360.0)))

    assert first.state == second.state == ZoomState.TRACK_CONFIRMING
    assert first.factor == second.factor == 1.0
    assert third.state == ZoomState.TRACK_ROI_1_5X
    assert third.factor == 1.5
    assert third.crop_center_px == (620.0, 350.0)
    assert third.fire_authorized is False


def test_small_stable_target_selects_2x() -> None:
    controller = ZoomController(confirm_frames=2, use_2x_below_pixels=900)

    controller.update(observation(target_pixels=500))
    decision = controller.update(observation(target_pixels=500))

    assert decision.state == ZoomState.TRACK_ROI_2X
    assert decision.factor == 2.0


def test_stale_or_lost_track_fails_back_to_full_frame() -> None:
    controller = ZoomController(confirm_frames=1)
    assert controller.update(observation()).factor == 1.5

    stale = controller.update(observation(freshness_ms=1000.0))
    missing = controller.update(None)

    assert stale.state == ZoomState.LOST_FAILBACK
    assert stale.factor == 1.0
    assert missing.state == ZoomState.SEARCH_FULL_FRAME
    assert missing.factor == 1.0
    assert stale.fire_authorized is missing.fire_authorized is False


def test_track_id_change_restarts_confirmation() -> None:
    controller = ZoomController(confirm_frames=2)
    controller.update(observation())
    assert controller.update(observation()).factor == 1.5

    changed = controller.update(observation(track_id="TRACK-2"))

    assert changed.state == ZoomState.TRACK_CONFIRMING
    assert changed.factor == 1.0
