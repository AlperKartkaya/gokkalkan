#!/usr/bin/env python3
"""Evaluate camera calibration observations without inventing physical evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def evaluate(path: Path) -> dict[str, object]:
    observations = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(observations, list) or len(observations) < 9:
        raise ValueError("at least 9 checkerboard/boresight observations are required")
    errors = [abs(float(item["errorPx"])) for item in observations]
    physical = all(item.get("evidenceClass") == "PHYSICAL_CAMERA" for item in observations)
    return {
        "schemaVersion": 1,
        "sampleCount": len(errors),
        "meanAbsErrorPx": sum(errors) / len(errors),
        "maxAbsErrorPx": max(errors),
        "rawEvidenceSha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "physicalGatePassed": physical and max(errors) <= 2.0,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("observations", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = evaluate(args.observations)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
