from __future__ import annotations

from pathlib import Path
import subprocess
import sys


sys.path.insert(0, str(Path("perception/src").resolve()))

from accelerator import Hailo8Accelerator  # noqa: E402
from detector import LatestWinsDetector  # noqa: E402
from hailo_detector import HailoDetector  # noqa: E402
import time


def _result(stdout: str, returncode: int = 0) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(
        args=["hailortcli", "fw-control", "identify"],
        returncode=returncode,
        stdout=stdout,
        stderr="",
    )


def test_hailo8_26_tops_identity_is_distinct_from_model_readiness(tmp_path: Path) -> None:
    model = tmp_path / "target_detector.hef"
    model.write_bytes(b"test-only-hef-placeholder")
    accelerator = Hailo8Accelerator(
        model,
        runner=lambda *args, **kwargs: _result(
            "Board Name: Hailo-8\nDevice Architecture: HAILO8\n"
        ),
        executable_resolver=lambda _name: "/usr/bin/hailortcli",
        cache_ttl_s=0,
    )

    health = accelerator.health(force=True)

    assert health["hardwareReady"] is True
    assert health["modelReady"] is True
    assert health["inferenceReady"] is True
    assert health["tops"] == 26


def test_hailo8l_is_rejected_for_the_26_tops_contract() -> None:
    accelerator = Hailo8Accelerator(
        runner=lambda *args, **kwargs: _result(
            "Board Name: Hailo-8L\nDevice Architecture: HAILO8L\n"
        ),
        executable_resolver=lambda _name: "/usr/bin/hailortcli",
        cache_ttl_s=0,
    )

    health = accelerator.health(force=True)

    assert health["hardwareReady"] is False
    assert health["inferenceReady"] is False
    assert health["status"] == "WRONG_OR_MISSING_DEVICE"


def test_missing_hailortcli_reports_fail_closed_status() -> None:
    accelerator = Hailo8Accelerator(
        executable_resolver=lambda _name: None,
        cache_ttl_s=0,
    )

    health = accelerator.health(force=True)

    assert health["hardwareReady"] is False
    assert health["status"] == "CLI_MISSING"


def test_hailo_detector_hashes_model_and_filters_contract(tmp_path: Path) -> None:
    model = tmp_path / "model.hef"
    model.write_bytes(b"fixture")
    detector = HailoDetector(
        model,
        lambda _frame: [
            {"label": "F16", "confidence": 0.9, "bbox": [0, 0, 10, 10]},
            {"label": "UNKNOWN", "confidence": 0.99, "bbox": [0, 0, 1, 1]},
        ],
        allowed_labels={"F16"},
    )
    assert [item.label for item in detector.detect(object())] == ["F16"]
    assert len(detector.health()["modelSha256"]) == 64


def test_latest_wins_detector_reports_inference_failure_fail_closed() -> None:
    class Broken:
        def detect(self, _frame):
            raise RuntimeError("boom")
        def health(self):
            return {"inferenceReady": True}

    worker = LatestWinsDetector(Broken())
    worker.start()
    worker.submit(object(), time.monotonic_ns())
    for _ in range(100):
        if worker.health()["lastError"]:
            break
        time.sleep(0.001)
    assert worker.latest() == []
    assert "RuntimeError" in worker.health()["lastError"]
    worker.stop()
