"""TFA50-L 5/10/15 m physical calibration evidence evaluator."""

from __future__ import annotations

from collections import defaultdict
import json
from math import sqrt
from pathlib import Path
import statistics
from typing import Any, Iterable


REQUIRED_RANGES_M = (5.0, 10.0, 15.0)
REQUIRED_YAW_POSITIONS = ("left", "center", "right")


def evaluate_lidar_observations(
    observations: Iterable[dict[str, Any]],
    *,
    evidence_class: str,
    mount_revision: str,
    calibration_id: str,
) -> dict[str, Any]:
    rows = list(observations)
    by_range: dict[float, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_range[float(row["expectedRangeM"])].append(row)
    summaries: list[dict[str, Any]] = []
    passed = evidence_class == "PHYSICAL_TFA50_L" and bool(mount_revision.strip())
    for expected in REQUIRED_RANGES_M:
        group = by_range.get(expected, [])
        valid = [
            float(row["measuredRangeM"])
            for row in group
            if row.get("measuredRangeM") is not None
        ]
        yaw_positions = {str(row.get("yawPosition", "")) for row in group}
        no_detection_rate = 1.0 - len(valid) / len(group) if group else 1.0
        mean = statistics.mean(valid) if valid else None
        repeatability = statistics.pstdev(valid) if len(valid) > 1 else None
        rmse = (
            sqrt(sum((value - expected) ** 2 for value in valid) / len(valid))
            if valid
            else None
        )
        group_ok = (
            len(valid) >= 5
            and set(REQUIRED_YAW_POSITIONS).issubset(yaw_positions)
            and no_detection_rate <= 0.10
            and rmse is not None
            and rmse <= max(0.05, expected * 0.01)
        )
        passed = passed and group_ok
        summaries.append(
            {
                "expectedRangeM": expected,
                "sampleCount": len(group),
                "validCount": len(valid),
                "meanRangeM": mean,
                "repeatabilityStdM": repeatability,
                "rmseM": rmse,
                "noDetectionRate": no_detection_rate,
                "yawPositions": sorted(yaw_positions),
                "accepted": group_ok,
            }
        )
    return {
        "schemaVersion": 1,
        "calibrationId": calibration_id,
        "mountRevision": mount_revision,
        "evidenceClass": evidence_class,
        "ranges": summaries,
        "physicalGatePassed": passed,
        "physicalOutput": False,
    }


def evaluate_lidar_file(source: str | Path, output: str | Path) -> dict[str, Any]:
    payload = json.loads(Path(source).read_text(encoding="utf-8"))
    report = evaluate_lidar_observations(
        payload.get("observations", []),
        evidence_class=str(payload.get("evidenceClass", "UNVERIFIED")),
        mount_revision=str(payload.get("mountRevision", "")),
        calibration_id=str(payload.get("calibrationId", "UNVERIFIED")),
    )
    target = Path(output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report
