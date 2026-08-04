from __future__ import annotations

from pathlib import Path
import subprocess
import sys


sys.path.insert(0, str(Path("perception/src").resolve()))

from accelerator import Hailo8Accelerator  # noqa: E402


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
