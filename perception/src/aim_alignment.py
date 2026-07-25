"""Calibrated image-to-turret error for the narrow aim camera."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Any


@dataclass(frozen=True, slots=True)
class AimCalibration:
    calibration_id: str
    principal_x_px: float
    principal_y_px: float
    yaw_deg_per_px: float
    pitch_deg_per_px: float
    yaw_offset_deg: float = 0.0
    pitch_offset_deg: float = 0.0

    def digest(self) -> str:
        payload = json.dumps(
            {
                "calibrationId": self.calibration_id,
                "principalXpx": self.principal_x_px,
                "principalYpx": self.principal_y_px,
                "yawDegPerPx": self.yaw_deg_per_px,
                "pitchDegPerPx": self.pitch_deg_per_px,
                "yawOffsetDeg": self.yaw_offset_deg,
                "pitchOffsetDeg": self.pitch_offset_deg,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def calibrated_aim_error(
    track: Any,
    calibration: AimCalibration,
    *,
    now_monotonic_ns: int,
    max_age_ms: float = 250.0,
) -> dict[str, object]:
    """Return calibrated yaw/pitch corrections or an explicit stale rejection."""

    track_ns = int(getattr(track, "receive_monotonic_ns", 0))
    age_ms = max(0.0, (now_monotonic_ns - track_ns) / 1_000_000)
    if track_ns <= 0 or age_ms > max_age_ms:
        return {
            "valid": False,
            "reason": "TRACK_STALE",
            "ageMs": age_ms,
            "calibrationId": calibration.calibration_id,
            "calibrationHash": calibration.digest(),
        }
    yaw_error = (
        (float(getattr(track, "cx")) - calibration.principal_x_px)
        * calibration.yaw_deg_per_px
        + calibration.yaw_offset_deg
    )
    # Image y grows downward; positive turret pitch grows upward.
    pitch_error = (
        (calibration.principal_y_px - float(getattr(track, "cy")))
        * calibration.pitch_deg_per_px
        + calibration.pitch_offset_deg
    )
    return {
        "valid": True,
        "reason": "CALIBRATED",
        "yawErrorDeg": yaw_error,
        "pitchErrorDeg": pitch_error,
        "ageMs": age_ms,
        "calibrationId": calibration.calibration_id,
        "calibrationHash": calibration.digest(),
    }
