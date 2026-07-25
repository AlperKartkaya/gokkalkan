"""Safe-load-only HIL scenario orchestration and report generation."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import time
from typing import Any

from .verification import run_fault_injection_suite


HIL_SCENARIOS = (
    "boot-safe",
    "pico-reset",
    "heartbeat-loss",
    "can-disconnect",
    "encoder-reversed",
    "encoder-disconnected",
    "camera-stale",
    "lidar-stale",
    "estop",
    "backend-restart",
    "perception-restart",
    "recorder-restart",
)


@dataclass(frozen=True, slots=True)
class HilProfile:
    profile_id: str
    can_channel: str
    safe_load: str
    allows_destructive_output: bool
    config_hash: str
    calibration_hash: str

    def validate(self) -> None:
        if self.safe_load not in {"lamp", "resistive-dummy-load"}:
            raise ValueError("HIL safe_load must be a lamp or resistive dummy load")
        if self.allows_destructive_output:
            raise ValueError("HIL cannot enable the real target-destruction output")


def run_hil_plan(
    profile: HilProfile,
    *,
    output: str | Path,
    physical_evidence: dict[str, bool] | None = None,
) -> dict[str, Any]:
    """Write a report; absent physical observations stay explicitly unverified."""

    profile.validate()
    observations = physical_evidence or {}
    software_faults = run_fault_injection_suite()
    results = [
        {
            "scenario": scenario,
            "status": (
                "PASS"
                if observations.get(scenario) is True
                else "FAIL"
                if observations.get(scenario) is False
                else "NOT_RUN_PHYSICAL"
            ),
        }
        for scenario in HIL_SCENARIOS
    ]
    run_id = hashlib.sha256(
        f"{profile.profile_id}:{profile.config_hash}:{profile.calibration_hash}:{time.time_ns()}".encode()
    ).hexdigest()[:16]
    report = {
        "schemaVersion": 1,
        "runId": run_id,
        "profile": profile.profile_id,
        "safeLoad": profile.safe_load,
        "allowsDestructiveOutput": False,
        "configHash": profile.config_hash,
        "calibrationHash": profile.calibration_hash,
        "softwareHarness": software_faults,
        "scenarios": results,
        "physicalGatePassed": bool(results)
        and all(item["status"] == "PASS" for item in results),
    }
    target = Path(output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report
