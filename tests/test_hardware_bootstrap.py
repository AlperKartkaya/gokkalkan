from __future__ import annotations

from pathlib import Path

import pytest

from gokkalkan_backend.hardware_bootstrap import HardwareBootstrap
from gokkalkan_backend.runtime_config import load_runtime_config
from gokkalkan_backend.runtime_mode import RuntimeConfigurationError


class Monitor:
    def __init__(self, health: dict[str, object], **options: object) -> None:
        self._health = health
        self.options = options
        self.closed = False

    def start(self) -> None:
        pass

    def health_check(self) -> dict[str, object]:
        return self._health

    def close(self) -> None:
        self.closed = True


def _settings(tmp_path: Path):
    text = Path("config/runtime/live.toml").read_text(encoding="utf-8")
    text = text.replace("REPLACE_WITH_GOKKALKAN_PICO", "usb-GOKKALKAN_PICO_001")
    path = tmp_path / "live.toml"
    path.write_text(text, encoding="utf-8")
    return load_runtime_config(path)


def _evidence(tmp_path: Path) -> dict[str, Path]:
    result = {}
    for label in (
        "runtimeConfig", "bom", "pinMap", "physicalAcceptance", "lidarCalibration",
        "cameraCalibration", "turretCalibration", "airsoftCalibration", "detectorModel",
    ):
        path = tmp_path / f"{label}.txt"
        path.write_text(f"APPROVED {label}\n", encoding="utf-8")
        result[label] = path
    return result


def _health(**changes: object) -> dict[str, object]:
    value: dict[str, object] = {
        "serialConnected": True,
        "picoReachable": True,
        "protocolVersion": 1,
        "firmwareVersion": "1.0.0",
        "lastStatusAgeSec": 0.01,
        "mcuStatus": {
            "estopActive": False,
            "encoderOk": True,
            "fireReady": True,
            "faultCode": 0,
        },
    }
    value.update(changes)
    return value


def test_live_bootstrap_is_monitor_only_and_hashes_evidence(tmp_path: Path) -> None:
    instances: list[Monitor] = []

    def factory(**options: object) -> Monitor:
        item = Monitor(_health(), **options)
        instances.append(item)
        return item

    result = HardwareBootstrap().run(
        _settings(tmp_path), evidence_files=_evidence(tmp_path), monitor_factory=factory
    )

    assert result.physical_interlock_ready is True
    assert result.backend_readiness_ok is True
    assert result.source.startswith("hardware-bootstrap:")
    assert len(result.snapshot["evidenceSha256"]) == 9  # type: ignore[index]
    assert instances[0].options["physical_output_capable"] is False
    assert instances[0].closed is True


@pytest.mark.parametrize(
    "health,error",
    [
        (_health(picoReachable=False), "fresh status"),
        (_health(protocolVersion=2), "protocol major"),
        (_health(firmwareVersion=None), "firmware identity"),
        (_health(mcuStatus={"estopActive": True}), "E-Stop"),
        (_health(mcuStatus={"estopActive": False, "encoderOk": False}), "encoder"),
        (_health(mcuStatus={"estopActive": False, "encoderOk": True, "fireReady": False}), "airsoft"),
    ],
)
def test_live_bootstrap_fails_closed_on_unhealthy_monitor(
    tmp_path: Path, health: dict[str, object], error: str
) -> None:
    with pytest.raises(RuntimeConfigurationError, match=error):
        HardwareBootstrap(timeout_sec=0.1).run(
            _settings(tmp_path),
            evidence_files=_evidence(tmp_path),
            monitor_factory=lambda **options: Monitor(health, **options),
        )


def test_live_bootstrap_rejects_unverified_evidence(tmp_path: Path) -> None:
    evidence = _evidence(tmp_path)
    evidence["pinMap"].write_text("UNVERIFIED", encoding="utf-8")
    with pytest.raises(RuntimeConfigurationError, match="not approved"):
        HardwareBootstrap().run(
            _settings(tmp_path), evidence_files=evidence, monitor_factory=lambda **_: None
        )
