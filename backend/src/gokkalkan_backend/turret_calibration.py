"""Field-derived turret command calibration.

The MCU reports physical encoder angles while its command accepts absolute
angles.  This module models each axis as::

    measured_physical_deg = gain * commanded_deg + offset_deg

Only explicitly activated calibration files affect commands.  An unverified or
malformed file therefore fails safe to identity correction and remains visible
in operator state.
"""

from __future__ import annotations

import json
import math
import tomllib
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable


@dataclass(frozen=True, slots=True)
class AxisCalibration:
    gain: float = 1.0
    offset_deg: float = 0.0
    rmse_deg: float | None = None
    sample_count: int = 0

    def validate(self) -> None:
        if not math.isfinite(self.gain) or not 0.5 <= self.gain <= 1.5:
            raise ValueError("axis gain must be finite and between 0.5 and 1.5")
        if not math.isfinite(self.offset_deg) or abs(self.offset_deg) > 20:
            raise ValueError("axis offset must be finite and within ±20 degrees")

    def command_for_physical(self, physical_deg: float) -> float:
        self.validate()
        return (physical_deg - self.offset_deg) / self.gain


@dataclass(frozen=True, slots=True)
class TurretCalibration:
    calibration_id: str
    status: str
    calibrated_at: str
    pan: AxisCalibration
    tilt: AxisCalibration

    @property
    def active(self) -> bool:
        return self.status == "ACTIVE"

    @classmethod
    def identity(cls) -> "TurretCalibration":
        return cls(
            calibration_id="UNVERIFIED",
            status="UNVERIFIED",
            calibrated_at="",
            pan=AxisCalibration(),
            tilt=AxisCalibration(),
        )

    @classmethod
    def from_toml(cls, path: str | Path) -> "TurretCalibration":
        source = Path(path)
        if not source.exists():
            return cls.identity()
        with source.open("rb") as handle:
            raw = tomllib.load(handle)
        meta = raw.get("calibration", {})
        calibration = cls(
            calibration_id=str(meta.get("id", "UNVERIFIED")),
            status=str(meta.get("status", "UNVERIFIED")).upper(),
            calibrated_at=str(meta.get("calibrated_at", "")),
            pan=_axis_from_mapping(raw.get("pan", {})),
            tilt=_axis_from_mapping(raw.get("tilt", {})),
        )
        calibration.pan.validate()
        calibration.tilt.validate()
        return calibration

    def correct_delta(
        self,
        *,
        current_pan_deg: float,
        current_tilt_deg: float,
        pan_delta_deg: float,
        tilt_delta_deg: float,
    ) -> tuple[float, float]:
        """Return adapter deltas that realize the requested physical deltas.

        The adapter creates an absolute command by adding its payload delta to
        the measured encoder position.  Therefore the inverse-calibrated target
        is subtracted from the *measured* current position.
        """

        if not self.active:
            return pan_delta_deg, tilt_delta_deg
        desired_pan = current_pan_deg + pan_delta_deg
        desired_tilt = current_tilt_deg + tilt_delta_deg
        return (
            self.pan.command_for_physical(desired_pan) - current_pan_deg,
            self.tilt.command_for_physical(desired_tilt) - current_tilt_deg,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "calibrationId": self.calibration_id,
            "status": self.status,
            "calibratedAt": self.calibrated_at or None,
            "active": self.active,
            "pan": _axis_dict(self.pan),
            "tilt": _axis_dict(self.tilt),
        }


def fit_axis(samples: Iterable[tuple[float, float]]) -> AxisCalibration:
    """Fit measured = gain*commanded + offset with ordinary least squares."""

    pairs = [(float(commanded), float(measured)) for commanded, measured in samples]
    if len(pairs) < 3:
        raise ValueError("at least three samples are required per axis")
    xs = [item[0] for item in pairs]
    ys = [item[1] for item in pairs]
    x_mean = sum(xs) / len(xs)
    y_mean = sum(ys) / len(ys)
    denominator = sum((value - x_mean) ** 2 for value in xs)
    if denominator <= 1e-9:
        raise ValueError("commanded samples must span more than one angle")
    gain = sum((x - x_mean) * (y - y_mean) for x, y in pairs) / denominator
    offset = y_mean - gain * x_mean
    residuals = [y - (gain * x + offset) for x, y in pairs]
    result = AxisCalibration(
        gain=gain,
        offset_deg=offset,
        rmse_deg=math.sqrt(sum(value * value for value in residuals) / len(residuals)),
        sample_count=len(pairs),
    )
    result.validate()
    return result


def solve_calibration_file(
    observations_path: str | Path,
    output_path: str | Path,
    *,
    activate: bool = False,
) -> TurretCalibration:
    """Solve a JSON observation file and write a deterministic TOML artifact."""

    raw = json.loads(Path(observations_path).read_text(encoding="utf-8"))
    calibration_id = str(raw.get("calibrationId", "")).strip()
    if not calibration_id:
        raise ValueError("calibrationId is required")

    def pairs(axis: str) -> list[tuple[float, float]]:
        values = raw.get(axis)
        if not isinstance(values, list):
            raise ValueError(f"{axis} observations must be a list")
        return [
            (float(item["commandedDeg"]), float(item["measuredDeg"]))
            for item in values
        ]

    calibrated_at = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    calibration = TurretCalibration(
        calibration_id=calibration_id,
        status="ACTIVE" if activate else "CALCULATED_NOT_ACTIVE",
        calibrated_at=calibrated_at,
        pan=fit_axis(pairs("pan")),
        tilt=fit_axis(pairs("tilt")),
    )
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(_to_toml(calibration), encoding="utf-8")
    return calibration


def _axis_from_mapping(raw: dict[str, Any]) -> AxisCalibration:
    return AxisCalibration(
        gain=float(raw.get("gain", 1.0)),
        offset_deg=float(raw.get("offset_deg", 0.0)),
        rmse_deg=None if raw.get("rmse_deg") is None else float(raw["rmse_deg"]),
        sample_count=int(raw.get("sample_count", 0)),
    )


def _axis_dict(axis: AxisCalibration) -> dict[str, Any]:
    return {
        "gain": axis.gain,
        "offsetDeg": axis.offset_deg,
        "rmseDeg": axis.rmse_deg,
        "sampleCount": axis.sample_count,
    }


def _to_toml(calibration: TurretCalibration) -> str:
    def axis_block(name: str, axis: AxisCalibration) -> str:
        return (
            f"[{name}]\n"
            f"gain = {axis.gain:.10f}\n"
            f"offset_deg = {axis.offset_deg:.10f}\n"
            f"rmse_deg = {axis.rmse_deg or 0.0:.10f}\n"
            f"sample_count = {axis.sample_count}\n"
        )

    return (
        "# Fiziksel ölçümlerden üretilmiştir; ACTIVE yalnız bilinçli --activate ile yazılır.\n"
        "[calibration]\n"
        f'id = "{calibration.calibration_id}"\n'
        f'status = "{calibration.status}"\n'
        f'calibrated_at = "{calibration.calibrated_at}"\n\n'
        f"{axis_block('pan', calibration.pan)}\n"
        f"{axis_block('tilt', calibration.tilt)}"
    )
