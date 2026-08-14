"""Fail-back-first square ROI tracking recommendation state machine.

This module never authorizes movement or firing.  It selects a resolution-safe
square crop only after a stable track; stale or repeatedly missing tracks return
to the deterministic SAHI search sweep.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ZoomState(StrEnum):
    SEARCH_SAHI_SWEEP = "SEARCH_SAHI_SWEEP"
    TRACK_CONFIRMING = "TRACK_CONFIRMING"
    TRACK_ROI_768 = "TRACK_ROI_768"
    TRACK_ROI_960 = "TRACK_ROI_960"
    TRACK_ROI_1152 = "TRACK_ROI_1152"
    LOST_RETURN_TO_SEARCH = "LOST_RETURN_TO_SEARCH"


@dataclass(frozen=True, slots=True)
class ZoomObservation:
    track_id: str | None
    confidence: float
    freshness_ms: float
    target_pixels: int
    center_px: tuple[float, float] | None
    bbox_size_px: tuple[float, float] | None = None


@dataclass(frozen=True, slots=True)
class ZoomDecision:
    state: ZoomState
    roi_size_px: int | None
    factor: float
    crop_center_px: tuple[float, float] | None
    reason: str
    fire_authorized: bool = False


class ZoomController:
    """Require a stable track and expand square ROI progressively on misses."""

    def __init__(
        self,
        *,
        confirm_frames: int = 3,
        minimum_confidence: float = 0.65,
        stale_after_ms: float = 250.0,
        normal_roi_size_px: int = 768,
        first_recovery_roi_size_px: int = 960,
        second_recovery_roi_size_px: int = 1152,
        return_to_search_after_misses: int = 3,
        main_width_px: int = 2304,
    ) -> None:
        if confirm_frames < 1:
            raise ValueError("confirm_frames en az 1 olmalı")
        roi_sizes = (
            normal_roi_size_px,
            first_recovery_roi_size_px,
            second_recovery_roi_size_px,
        )
        if sorted(roi_sizes) != list(roi_sizes) or min(roi_sizes) < 640:
            raise ValueError("ROI boyutları 640 veya daha büyük ve artan olmalı")
        if return_to_search_after_misses < 3:
            raise ValueError("arama dönüşü en az üç ardışık kayıp gerektirir")
        self.confirm_frames = confirm_frames
        self.minimum_confidence = minimum_confidence
        self.stale_after_ms = stale_after_ms
        self.normal_roi_size_px = normal_roi_size_px
        self.first_recovery_roi_size_px = first_recovery_roi_size_px
        self.second_recovery_roi_size_px = second_recovery_roi_size_px
        self.return_to_search_after_misses = return_to_search_after_misses
        self.main_width_px = main_width_px
        self.state = ZoomState.SEARCH_SAHI_SWEEP
        self._active_track_id: str | None = None
        self._stable_frames = 0
        self._missed_frames = 0
        self._previous_center: tuple[float, float] | None = None

    def update(self, observation: ZoomObservation | None) -> ZoomDecision:
        if observation is None or observation.track_id is None:
            return self._handle_missing("track_missing")
        if observation.freshness_ms > self.stale_after_ms:
            return self._return_to_search("track_stale")
        if observation.confidence < self.minimum_confidence:
            return self._return_to_search("track_low_confidence")
        if observation.center_px is None:
            return self._return_to_search("track_center_missing")

        self._missed_frames = 0
        if observation.track_id != self._active_track_id:
            self._active_track_id = observation.track_id
            self._stable_frames = 1
            self._previous_center = observation.center_px
            if self.confirm_frames == 1:
                return self._stable_decision(observation, observation.center_px)
            self.state = ZoomState.TRACK_CONFIRMING
            return self._decision(None, observation.center_px, "new_track_confirming")

        crop_center = self._previous_center
        self._previous_center = observation.center_px
        self._stable_frames += 1
        if self._stable_frames < self.confirm_frames:
            self.state = ZoomState.TRACK_CONFIRMING
            return self._decision(None, crop_center, "track_confirming")
        return self._stable_decision(observation, crop_center)

    def _stable_decision(
        self,
        observation: ZoomObservation,
        crop_center: tuple[float, float] | None,
    ) -> ZoomDecision:
        bbox_size = observation.bbox_size_px
        if bbox_size is not None and max(bbox_size) > self.normal_roi_size_px * 0.5:
            self.state = ZoomState.TRACK_ROI_960
            return self._decision(
                self.first_recovery_roi_size_px,
                crop_center,
                "target_near_roi_boundary",
            )
        self.state = ZoomState.TRACK_ROI_768
        return self._decision(self.normal_roi_size_px, crop_center, "stable_track")

    def _handle_missing(self, reason: str) -> ZoomDecision:
        if self._active_track_id is None:
            self.state = ZoomState.SEARCH_SAHI_SWEEP
            return self._decision(None, None, reason)
        self._missed_frames += 1
        if self._missed_frames == 1:
            self.state = ZoomState.TRACK_ROI_960
            return self._decision(
                self.first_recovery_roi_size_px,
                self._previous_center,
                "first_track_miss",
            )
        if self._missed_frames == 2:
            self.state = ZoomState.TRACK_ROI_1152
            return self._decision(
                self.second_recovery_roi_size_px,
                self._previous_center,
                "second_track_miss",
            )
        if self._missed_frames >= self.return_to_search_after_misses:
            return self._return_to_search("track_lost_return_to_sahi")
        self.state = ZoomState.TRACK_ROI_1152
        return self._decision(
            self.second_recovery_roi_size_px,
            self._previous_center,
            reason,
        )

    def _return_to_search(self, reason: str) -> ZoomDecision:
        had_track = self._active_track_id is not None
        self._active_track_id = None
        self._stable_frames = 0
        self._missed_frames = 0
        self._previous_center = None
        self.state = (
            ZoomState.LOST_RETURN_TO_SEARCH
            if had_track
            else ZoomState.SEARCH_SAHI_SWEEP
        )
        return self._decision(None, None, reason)

    def _decision(
        self,
        roi_size_px: int | None,
        crop_center: tuple[float, float] | None,
        reason: str,
    ) -> ZoomDecision:
        factor = 1.0 if roi_size_px is None else self.main_width_px / roi_size_px
        return ZoomDecision(
            state=self.state,
            roi_size_px=roi_size_px,
            factor=factor,
            crop_center_px=crop_center,
            reason=reason,
            fire_authorized=False,
        )
