"""Calibrated image-to-turret error for the narrow aim camera."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import tomllib
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
    status: str = "UNVERIFIED"
    evidence_sha256: str = ""
    distortion: tuple[float, ...] = ()

    @property
    def active(self) -> bool:
        return (
            self.status == "ACTIVE"
            and bool(self.calibration_id.strip())
            and self.calibration_id != "UNVERIFIED"
            and len(self.evidence_sha256) == 64
            and self.yaw_deg_per_px > 0
            and self.pitch_deg_per_px > 0
        )

    @classmethod
    def load(cls, path: str | Path) -> "AimCalibration":
        raw = tomllib.loads(Path(path).read_text(encoding="utf-8"))
        table = raw["calibration"]
        return cls(
            calibration_id=str(table["id"]),
            principal_x_px=float(table["principal_x_px"]),
            principal_y_px=float(table["principal_y_px"]),
            yaw_deg_per_px=float(table["yaw_deg_per_px"]),
            pitch_deg_per_px=float(table["pitch_deg_per_px"]),
            yaw_offset_deg=float(table.get("yaw_offset_deg", 0.0)),
            pitch_offset_deg=float(table.get("pitch_offset_deg", 0.0)),
            status=str(table.get("status", "UNVERIFIED")),
            evidence_sha256=str(table.get("evidence_sha256", "")),
            distortion=tuple(float(value) for value in table.get("distortion", [])),
        )

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
                "status": self.status,
                "evidenceSha256": self.evidence_sha256,
                "distortion": self.distortion,
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
    if not calibration.active:
        return {
            "valid": False,
            "reason": "CALIBRATION_INACTIVE",
            "ageMs": age_ms,
            "calibrationId": calibration.calibration_id,
            "calibrationHash": calibration.digest(),
        }
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
