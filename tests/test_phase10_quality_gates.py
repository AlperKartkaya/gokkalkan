from __future__ import annotations

import ast
import json
from pathlib import Path
import tempfile

import pytest

from gokkalkan_backend.verification import (
    PerformanceBudget,
    run_fault_injection_suite,
    run_soak,
)


@pytest.mark.safety
def test_fault_injection_suite_fails_closed_for_all_required_faults() -> None:
    result = run_fault_injection_suite()
    assert result["ok"] is True
    assert result["physicalOutput"] is False
    assert {
        "corruptChecksum",
        "duplicateSequence",
        "heartbeatLoss",
        "canDisconnect",
        "estop",
        "staleCamera",
        "staleLidar",
        "diskFull",
        "processRestart",
        "backendDivergence",
    }.issubset(result["checks"])


@pytest.mark.replay
def test_replay_module_does_not_import_physical_adapter() -> None:
    tree = ast.parse(
        Path("backend/src/gokkalkan_backend/telemetry_session.py").read_text(
            encoding="utf-8"
        )
    )
    imports = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    }
    assert "hardware_adapter" not in imports
    assert "gokkalkan_backend.hardware_adapter" not in imports


def test_virtual_30_minute_soak_tracks_queue_disk_and_reconnects() -> None:
    result = run_soak(duration_seconds=1800, step_seconds=1.0)
    assert result["ok"] is True
    assert result["timeMode"] == "VIRTUAL_TIME"
    assert result["events"] == 1800
    assert result["maxRecorderQueueDepth"] <= 2
    assert result["diskFreeBytes"] > 0


def test_performance_budget_has_pass_and_fail_evidence() -> None:
    budget = PerformanceBudget.load("config/quality/performance.toml")
    passing = {
        "cameraFps": 25,
        "frameDropPercent": 1,
        "perceptionLatencyMs": 80,
        "commandAckMs": 200,
        "stateStreamMs": 250,
        "recorderQueueDepth": 5,
    }
    assert budget.evaluate(passing)["ok"] is True
    failing = {**passing, "commandAckMs": 500}
    result = budget.evaluate(failing)
    assert result["ok"] is False
    assert result["checks"]["commandAckMs"] is False


@pytest.mark.protocol
def test_tfa50_l_config_is_explicit_in_every_runtime_profile() -> None:
    for path in Path("config/runtime").glob("*.toml"):
        text = path.read_text(encoding="utf-8")
        assert "lidar_port" in text
        assert "lidar_baud_rate" in text
        assert "lidar_sample_hz" in text
