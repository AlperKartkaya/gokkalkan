"""Select the stratified 378-world CAD pilot from the full route plan."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

SYNTHETIC_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = SYNTHETIC_ROOT / "generated/render_plans/committee_tilt_sweep_v1.json"
DEFAULT_OUTPUT = SYNTHETIC_ROOT / "generated/render_plans/cad_pilot_378.json"
PILOT_LONGITUDINAL_M = {5.0, 10.0, 15.0}
PILOT_TILT_DEG = {8.0, 16.0, 24.0}


def select_pilot_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        record
        for record in records
        if float(record["longitudinalDistanceM"]) in PILOT_LONGITUDINAL_M
        and float(record["topSurfaceViewBucketDeg"]) in PILOT_TILT_DEG
    ]


def build_pilot_plan(plan: dict[str, Any]) -> dict[str, Any]:
    selected = select_pilot_records(plan["records"])
    classes = {record["presentationClass"] for record in selected}
    routes = {
        (record["routeId"], record["lateralDistanceBucketM"]) for record in selected
    }
    expected = (
        len(classes) * len(PILOT_LONGITUDINAL_M) * len(routes) * len(PILOT_TILT_DEG)
    )
    if len(selected) != expected:
        raise ValueError(
            f"pilot matrisi eksik/çoğul: beklenen={expected}, gerçek={len(selected)}"
        )
    return {
        **{key: value for key, value in plan.items() if key != "records"},
        "batchId": f"{plan['batchId']}-PILOT-378",
        "status": "SYNTHETIC_RENDER_PLAN",
        "selection": {
            "longitudinalDistanceM": sorted(PILOT_LONGITUDINAL_M),
            "topSurfaceViewBucketDeg": sorted(PILOT_TILT_DEG),
            "yawPolicy": "DERIVED_FROM_ALL_ROUTE_POSITIONS",
            "recordCount": len(selected),
        },
        "records": selected,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    plan = json.loads(args.input.read_text(encoding="utf-8"))
    pilot = build_pilot_plan(plan)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(pilot, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "status": pilot["status"],
                "records": len(pilot["records"]),
                "output": str(args.output),
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
