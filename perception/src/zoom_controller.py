"""Fail-back-first digital zoom recommendation state machine.

This module never authorizes movement or firing. It only recommends a camera
crop factor after a stable track exists; stale, weak or lost tracks return to
the full frame.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ZoomState(StrEnum):
    SEARCH_FULL_FRAME = "SEARCH_FULL_FRAME"
    TRACK_CONFIRMING = "TRACK_CONFIRMING"
    TRACK_ROI_1_5X = "TRACK_ROI_1_5X"
    TRACK_ROI_2X = "TRACK_ROI_2X"
    LOST_FAILBACK = "LOST_FAILBACK"


@dataclass(frozen=True, slots=True)
class ZoomObservation:
    track_id: str | None
    confidence: float
    freshness_ms: float
    target_pixels: int
    center_px: tuple[float, float] | None


@dataclass(frozen=True, slots=True)
class ZoomDecision:
    state: ZoomState
    factor: float
    crop_center_px: tuple[float, float] | None
    reason: str
    fire_authorized: bool = False


class ZoomController:
    """Require consecutive stable observations before recommending ROI zoom."""

    def __init__(
        self,
        *,
        confirm_frames: int = 3,
        minimum_confidence: float = 0.65,
        stale_after_ms: float = 250.0,
        use_2x_below_pixels: int = 900,
    ) -> None:
        if confirm_frames < 1:
            raise ValueError("confirm_frames en az 1 olmalı")
        self.confirm_frames = confirm_frames
        self.minimum_confidence = minimum_confidence
        self.stale_after_ms = stale_after_ms
        self.use_2x_below_pixels = use_2x_below_pixels
        self.state = ZoomState.SEARCH_FULL_FRAME
        self._active_track_id: str | None = None
        self._stable_frames = 0
        self._previous_center: tuple[float, float] | None = None

    def update(self, observation: ZoomObservation | None) -> ZoomDecision:
        if observation is None or observation.track_id is None:
            return self._failback("track_missing")
        if observation.freshness_ms > self.stale_after_ms:
            return self._failback("track_stale")
        if observation.confidence < self.minimum_confidence:
            return self._failback("track_low_confidence")
        if observation.center_px is None:
            return self._failback("track_center_missing")

        if observation.track_id != self._active_track_id:
            self._active_track_id = observation.track_id
            self._stable_frames = 1
            self._previous_center = observation.center_px
            if self.confirm_frames == 1:
                return self._stable_decision(observation, observation.center_px)
            self.state = ZoomState.TRACK_CONFIRMING
            return self._decision(1.0, observation.center_px, "new_track_confirming")

        crop_center = self._previous_center
        self._previous_center = observation.center_px
        self._stable_frames += 1
        if self._stable_frames < self.confirm_frames:
            self.state = ZoomState.TRACK_CONFIRMING
            return self._decision(1.0, crop_center, "track_confirming")

        return self._stable_decision(observation, crop_center)

    def _stable_decision(
        self,
        observation: ZoomObservation,
        crop_center: tuple[float, float] | None,
    ) -> ZoomDecision:
        if observation.target_pixels < self.use_2x_below_pixels:
            self.state = ZoomState.TRACK_ROI_2X
            return self._decision(2.0, crop_center, "stable_small_target")
        self.state = ZoomState.TRACK_ROI_1_5X
        return self._decision(1.5, crop_center, "stable_track")

    def _failback(self, reason: str) -> ZoomDecision:
        had_track = self._active_track_id is not None
        self._active_track_id = None
        self._stable_frames = 0
        self._previous_center = None
        self.state = (
            ZoomState.LOST_FAILBACK if had_track else ZoomState.SEARCH_FULL_FRAME
        )
        return self._decision(1.0, None, reason)

    def _decision(
        self,
        factor: float,
        crop_center: tuple[float, float] | None,
        reason: str,
    ) -> ZoomDecision:
        return ZoomDecision(
            state=self.state,
            factor=factor,
            crop_center_px=crop_center,
            reason=reason,
            fire_authorized=False,
        )
