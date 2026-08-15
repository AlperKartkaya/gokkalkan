"""Calibrated image-to-turret error for the narrow aim camera.

Distortion correction:
  If calibration.distortion = [k1, k2, p1, p2, k3] (OpenCV model),
  normalize pixel coordinates by focal length, apply Brown-Conrady
  radial + tangential model, then convert back to degrees.
  An empty distortion list skips correction (safe for pre-calibration).
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
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
            distortion=tuple(float(v) for v in table.get("distortion", [])),
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


def _apply_distortion_correction(
    cx: float,
    cy: float,
    calibration: AimCalibration,
) -> tuple[float, float]:
    """Apply Brown-Conrady radial + tangential undistortion.

    Corrects the raw pixel position using the OpenCV distortion model
    [k1, k2, p1, p2, k3].  Returns undistorted (cx, cy) in the same
    pixel space.  Skips correction if distortion tuple is empty or has
    fewer than 4 coefficients - safe before physical calibration.

    The IMX708 wide-angle lens exhibits barrel distortion that can cause
    ~2-4 deg error at the image edges.  Without this correction, boresight
    error accumulates on distant targets near the frame boundary.
    """
    dist = calibration.distortion
    if len(dist) < 4:
        return cx, cy  # no distortion data - skip

    k1, k2, p1, p2 = dist[0], dist[1], dist[2], dist[3]
    k3 = dist[4] if len(dist) >= 5 else 0.0

    # Normalize to focal-length units
    # focal_length_px ~ (pi/180) / yaw_deg_per_px
    focal_px = (math.pi / 180.0) / calibration.yaw_deg_per_px
    xn = (cx - calibration.principal_x_px) / focal_px
    yn = (cy - calibration.principal_y_px) / focal_px

    r2 = xn * xn + yn * yn
    r4 = r2 * r2
    r6 = r2 * r4

    # Radial scale factor
    radial = 1.0 + k1 * r2 + k2 * r4 + k3 * r6

    # Tangential components
    dx_tangential = 2.0 * p1 * xn * yn + p2 * (r2 + 2.0 * xn * xn)
    dy_tangential = p1 * (r2 + 2.0 * yn * yn) + 2.0 * p2 * xn * yn

    xn_corr = xn * radial + dx_tangential
    yn_corr = yn * radial + dy_tangential

    # Back to pixel space
    cx_corr = xn_corr * focal_px + calibration.principal_x_px
    cy_corr = yn_corr * focal_px + calibration.principal_y_px
    return cx_corr, cy_corr


def calibrated_aim_error(
    track: Any,
    calibration: AimCalibration,
    *,
    now_monotonic_ns: int,
    max_age_ms: float = 250.0,
    aim_point_px: tuple[float, float] | None = None,
) -> dict[str, object]:
    """Return calibrated yaw/pitch corrections or an explicit stale rejection.

    Args:
        track: TrackCandidate veya (cx, cy) sahip herhangi bir nesne.
        calibration: Yüklü AimCalibration sözleşmesi.
        now_monotonic_ns: Mevcut monotonic zaman damgası (ns).
        max_age_ms: Track tazelik sınırı (ms).
        aim_point_px: Opsiyonel açık nişan noktası (cx, cy) pikseli.
            Verilmezse track.cx / track.cy kullanılır.
            Balon–maket ilişkisi kurulunca balon merkezi buraya verilmeli.
    """
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

    # Determine aim point: explicit override > track centroid
    if aim_point_px is not None:
        raw_cx, raw_cy = float(aim_point_px[0]), float(aim_point_px[1])
    else:
        raw_cx = float(getattr(track, "cx"))
        raw_cy = float(getattr(track, "cy"))

    # Lens distortion correction (IMX708 wide-angle; skipped when coefficients empty)
    corr_cx, corr_cy = _apply_distortion_correction(raw_cx, raw_cy, calibration)

    yaw_error = (
        (corr_cx - calibration.principal_x_px)
        * calibration.yaw_deg_per_px
        + calibration.yaw_offset_deg
    )
    # Image y grows downward; positive turret pitch grows upward.
    pitch_error = (
        (calibration.principal_y_px - corr_cy)
        * calibration.pitch_deg_per_px
        + calibration.pitch_offset_deg
    )
    distortion_applied = len(calibration.distortion) >= 4
    return {
        "valid": True,
        "reason": "CALIBRATED",
        "yawErrorDeg": yaw_error,
        "pitchErrorDeg": pitch_error,
        "ageMs": age_ms,
        "aimPointPx": [corr_cx, corr_cy],
        "distortionApplied": distortion_applied,
        "calibrationId": calibration.calibration_id,
        "calibrationHash": calibration.digest(),
    }
