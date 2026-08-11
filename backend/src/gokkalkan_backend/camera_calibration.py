"""Backend verification of the perception camera calibration identity."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tomllib


def camera_calibration_digest(path: str | Path) -> str:
    table = tomllib.loads(Path(path).read_text(encoding="utf-8"))["calibration"]
    payload = {
        "calibrationId": str(table["id"]),
        "principalXpx": float(table["principal_x_px"]),
        "principalYpx": float(table["principal_y_px"]),
        "yawDegPerPx": float(table["yaw_deg_per_px"]),
        "pitchDegPerPx": float(table["pitch_deg_per_px"]),
        "yawOffsetDeg": float(table.get("yaw_offset_deg", 0.0)),
        "pitchOffsetDeg": float(table.get("pitch_offset_deg", 0.0)),
        "status": str(table.get("status", "UNVERIFIED")),
        "evidenceSha256": str(table.get("evidence_sha256", "")),
        "distortion": tuple(float(value) for value in table.get("distortion", [])),
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
