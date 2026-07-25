"""Fail-closed association of TFA50-L ranges with camera tracks."""

from __future__ import annotations

from collections import deque
from dataclasses import asdict, dataclass
from datetime import datetime
import hashlib
import json
from math import fabs
from pathlib import Path
import statistics
import tomllib
from typing import Any


def _angle_error(left: float, right: float) -> float:
    return (left - right + 180.0) % 360.0 - 180.0


def world_track_bearing(
    *,
    turret_yaw_deg: float,
    image_bearing_deg: float,
    camera_yaw_offset_deg: float,
) -> float:
    """Convert camera-relative bearing to the encoder/world yaw frame."""

    return turret_yaw_deg + camera_yaw_offset_deg + image_bearing_deg


@dataclass(frozen=True, slots=True)
class LidarCalibration:
    calibration_id: str
    calibrated_at: str
    operator: str
    mount_height_m: float
    yaw_offset_deg: float
    pitch_offset_deg: float
    vertical_band_min_m: float
    vertical_band_max_m: float
    mount_revision: str
    verified_ranges_m: tuple[float, ...]

    def digest(self) -> str:
        body = json.dumps(asdict(self), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(body.encode("utf-8")).hexdigest()

    def valid_for_mount(self, current_mount_revision: str) -> bool:
        try:
            datetime.fromisoformat(self.calibrated_at.replace("Z", "+00:00"))
        except ValueError:
            return False
        return (
            bool(self.calibration_id.strip())
            and bool(self.operator.strip())
            and self.mount_revision == current_mount_revision
            and self.vertical_band_min_m < self.vertical_band_max_m
            and {5.0, 10.0, 15.0}.issubset(set(self.verified_ranges_m))
        )

    @classmethod
    def load(cls, path: str | Path) -> "LidarCalibration":
        raw = tomllib.loads(Path(path).read_text(encoding="utf-8"))
        table = raw.get("calibration", raw)
        if not isinstance(table, dict):
            raise ValueError("missing [calibration] table")
        return cls(
            calibration_id=str(table["id"]),
            calibrated_at=str(table["calibrated_at"]),
            operator=str(table["operator"]),
            mount_height_m=float(table["mount_height_m"]),
            yaw_offset_deg=float(table["yaw_offset_deg"]),
            pitch_offset_deg=float(table["pitch_offset_deg"]),
            vertical_band_min_m=float(table["vertical_band_min_m"]),
            vertical_band_max_m=float(table["vertical_band_max_m"]),
            mount_revision=str(table["mount_revision"]),
            verified_ranges_m=tuple(float(item) for item in table["verified_ranges_m"]),
        )


@dataclass(frozen=True, slots=True)
class TimedRange:
    distance_m: float | None
    receive_monotonic_ns: int
    raw_hex: str
    valid: bool
    reason: str


@dataclass(frozen=True, slots=True)
class TrackBearing:
    """Selected track bearing in the encoder/world yaw frame, not image pixels."""

    track_id: str
    bearing_deg: float
    receive_monotonic_ns: int


@dataclass(frozen=True, slots=True)
class FusedRangeDecision:
    accepted: bool
    reason: str
    track_id: str | None
    distance_m: float | None
    source: str
    calibration_hash: str
    sample_count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "accepted": self.accepted,
            "reason": self.reason,
            "trackId": self.track_id,
            "rangeM": self.distance_m,
            "source": self.source,
            "calibrationHash": self.calibration_hash,
            "sampleCount": self.sample_count,
        }


class YawRangeAssociator:
    """Associate range only when clocks, yaw, calibration and stability agree."""

    def __init__(
        self,
        calibration: LidarCalibration,
        *,
        current_mount_revision: str,
        yaw_tolerance_deg: float = 1.5,
        max_time_delta_ms: float = 120.0,
        max_age_ms: float = 300.0,
        required_consecutive: int = 3,
        max_range_rate_m_s: float = 8.0,
        outlier_tolerance_m: float = 0.75,
    ) -> None:
        self.calibration = calibration
        self.current_mount_revision = current_mount_revision
        self.yaw_tolerance_deg = yaw_tolerance_deg
        self.max_time_delta_ns = int(max_time_delta_ms * 1_000_000)
        self.max_age_ns = int(max_age_ms * 1_000_000)
        self.required_consecutive = required_consecutive
        self.max_range_rate_m_s = max_range_rate_m_s
        self.outlier_tolerance_m = outlier_tolerance_m
        self._accepted: deque[TimedRange] = deque(maxlen=max(3, required_consecutive))
        self._track_id: str | None = None

    def associate(
        self,
        sample: TimedRange,
        track: TrackBearing | None,
        *,
        turret_yaw_deg: float,
        now_monotonic_ns: int,
    ) -> FusedRangeDecision:
        digest = self.calibration.digest()

        def reject(reason: str) -> FusedRangeDecision:
            self._accepted.clear()
            self._track_id = None
            return FusedRangeDecision(False, reason, None, None, "tfa50-l", digest, 0)

        if not self.calibration.valid_for_mount(self.current_mount_revision):
            return reject("CALIBRATION_INVALID_OR_MOUNT_CHANGED")
        if track is None:
            return reject("NO_SELECTED_TRACK")
        if not sample.valid or sample.distance_m is None:
            return reject(sample.reason or "INVALID_RANGE")
        if now_monotonic_ns - sample.receive_monotonic_ns > self.max_age_ns:
            return reject("LIDAR_STALE")
        if now_monotonic_ns - track.receive_monotonic_ns > self.max_age_ns:
            return reject("TRACK_STALE")
        if abs(sample.receive_monotonic_ns - track.receive_monotonic_ns) > self.max_time_delta_ns:
            return reject("TIMESTAMP_MISMATCH")
        lidar_yaw = turret_yaw_deg + self.calibration.yaw_offset_deg
        if fabs(_angle_error(lidar_yaw, track.bearing_deg)) > self.yaw_tolerance_deg:
            return reject("YAW_MISMATCH")
        if self._track_id not in {None, track.track_id}:
            self._accepted.clear()
        self._track_id = track.track_id
        if self._accepted:
            previous = self._accepted[-1]
            elapsed = max(
                1e-9,
                (sample.receive_monotonic_ns - previous.receive_monotonic_ns) / 1e9,
            )
            if abs(sample.distance_m - float(previous.distance_m)) / elapsed > self.max_range_rate_m_s:
                return reject("RANGE_RATE_OUTLIER")
        self._accepted.append(sample)
        median = statistics.median(float(item.distance_m) for item in self._accepted)
        if any(
            abs(float(item.distance_m) - median) > self.outlier_tolerance_m
            for item in self._accepted
        ):
            return reject("RANGE_OUTLIER")
        if len(self._accepted) < self.required_consecutive:
            return FusedRangeDecision(
                False,
                "RANGE_NOT_STABLE",
                track.track_id,
                None,
                "tfa50-l",
                digest,
                len(self._accepted),
            )
        return FusedRangeDecision(
            True,
            "FUSED_STABLE_RANGE",
            track.track_id,
            median,
            "fused:tfa50-l+camera+yaw",
            digest,
            len(self._accepted),
        )
