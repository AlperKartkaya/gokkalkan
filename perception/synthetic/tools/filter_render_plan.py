"""Select angle-compatible synthetic records without deleting source renders."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


def select_records(
    records: list[dict[str, Any]],
    *,
    min_tilt_deg: float,
    max_tilt_deg: float,
    min_yaw_deg: float = -180.0,
    max_yaw_deg: float = 180.0,
) -> tuple[list[str], list[str]]:
    if min_tilt_deg > max_tilt_deg or min_yaw_deg > max_yaw_deg:
        raise ValueError("minimum değer maksimumdan büyük olamaz")
    included, excluded = [], []
    for record in records:
        keep = (
            min_tilt_deg <= float(record["topSurfaceViewDeg"]) <= max_tilt_deg
            and min_yaw_deg <= float(record["viewYawDeg"]) <= max_yaw_deg
        )
        (included if keep else excluded).append(record["recordId"])
    return included, excluded


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--min-tilt-deg", type=float, required=True)
    parser.add_argument("--max-tilt-deg", type=float, required=True)
    parser.add_argument("--min-yaw-deg", type=float, default=-180.0)
    parser.add_argument("--max-yaw-deg", type=float, default=180.0)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    source_bytes = args.input.read_bytes()
    batch = json.loads(source_bytes)
    included, excluded = select_records(
        batch["records"],
        min_tilt_deg=args.min_tilt_deg,
        max_tilt_deg=args.max_tilt_deg,
        min_yaw_deg=args.min_yaw_deg,
        max_yaw_deg=args.max_yaw_deg,
    )
    selection = {
        "schemaVersion": 1,
        "sourceBatchId": batch["batchId"],
        "sourceBatchSha256": hashlib.sha256(source_bytes).hexdigest(),
        "policy": {
            "topSurfaceViewDeg": [args.min_tilt_deg, args.max_tilt_deg],
            "viewYawDeg": [args.min_yaw_deg, args.max_yaw_deg],
        },
        "includedRecordIds": included,
        "excludedRecordIds": excluded,
        "destructive": False,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(selection, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"included": len(included), "excluded": len(excluded), "output": str(args.output)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
