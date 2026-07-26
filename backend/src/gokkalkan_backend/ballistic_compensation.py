"""Calibrated airsoft elevation holdover table for operator support."""

from __future__ import annotations

import math
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class BallisticPoint:
    range_m: float
    elevation_deg: float


@dataclass(frozen=True, slots=True)
class BallisticCompensation:
    calibration_id: str
    status: str
    points: tuple[BallisticPoint, ...]

    @classmethod
    def unverified(cls) -> "BallisticCompensation":
        return cls("UNVERIFIED", "UNVERIFIED", ())

    @classmethod
    def from_toml(cls, path: str | Path) -> "BallisticCompensation":
        source = Path(path)
        if not source.exists():
            return cls.unverified()
        with source.open("rb") as handle:
            raw = tomllib.load(handle)
        meta = raw.get("calibration", {})
        points = tuple(
            BallisticPoint(float(item["range_m"]), float(item["elevation_deg"]))
            for item in raw.get("point", [])
        )
        result = cls(
            str(meta.get("id", "UNVERIFIED")),
            str(meta.get("status", "UNVERIFIED")).upper(),
            tuple(sorted(points, key=lambda point: point.range_m)),
        )
        result._validate()
        return result

    @property
    def active(self) -> bool:
        return self.status == "ACTIVE" and len(self.points) >= 2

    def elevation_for_range(self, range_m: float) -> float | None:
        if not self.active or not self.points:
            return None
        if range_m < self.points[0].range_m or range_m > self.points[-1].range_m:
            return None
        for left, right in zip(self.points, self.points[1:]):
            if left.range_m <= range_m <= right.range_m:
                span = right.range_m - left.range_m
                ratio = 0.0 if span == 0 else (range_m - left.range_m) / span
                return left.elevation_deg + ratio * (
                    right.elevation_deg - left.elevation_deg
                )
        return self.points[-1].elevation_deg

    def to_dict(self, range_m: float | None = None) -> dict[str, Any]:
        correction = (
            None if range_m is None else self.elevation_for_range(float(range_m))
        )
        return {
            "calibrationId": self.calibration_id,
            "status": self.status,
            "active": self.active,
            "rangeM": range_m,
            "elevationCorrectionDeg": correction,
            "mode": "HOLDOVER_RETICLE",
            "automaticFireAdjustment": False,
            "reason": (
                "Kalibre edilmiş menzil-elevasyon tablosundan enterpolasyon."
                if correction is not None
                else "Fiziksel atış tablosu aktif değil veya menzil tablo dışında."
            ),
        }

    def _validate(self) -> None:
        previous = -math.inf
        for point in self.points:
            if not math.isfinite(point.range_m) or not math.isfinite(point.elevation_deg):
                raise ValueError("ballistic points must be finite")
            if point.range_m <= previous:
                raise ValueError("ballistic ranges must be strictly increasing")
            if point.range_m <= 0 or abs(point.elevation_deg) > 30:
                raise ValueError("ballistic point is outside safe bounds")
            previous = point.range_m
