"""Read-only environment diagnostics for Gökkalkan."""

from __future__ import annotations

import argparse
import glob
import json
import os
import shutil
import subprocess
import tempfile
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal
from urllib.error import URLError
from urllib.request import urlopen

from .runtime_config import RuntimeConfigError, RuntimeSettings, load_runtime_config

Status = Literal["PASS", "WARN", "FAIL"]


@dataclass(frozen=True, slots=True)
class DoctorCheck:
    name: str
    status: Status
    detail: str


def _api_json(url: str, timeout: float = 1.0) -> dict[str, object] | None:
    try:
        with urlopen(url, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
        return payload if isinstance(payload, dict) else None
    except (OSError, URLError, ValueError, json.JSONDecodeError):
        return None


def _check_clock() -> DoctorCheck:
    now = datetime.now(UTC)
    if now.year < 2026:
        return DoctorCheck("clock", "FAIL", f"UTC clock is implausible: {now.isoformat()}")
    synchronized = ""
    try:
        result = subprocess.run(
            ["timedatectl", "show", "-p", "NTPSynchronized", "--value"],
            capture_output=True,
            text=True,
            timeout=1.0,
            check=False,
        )
        synchronized = result.stdout.strip().lower()
    except (FileNotFoundError, OSError, subprocess.SubprocessError):
        pass
    if synchronized == "no":
        return DoctorCheck("clock", "WARN", "UTC clock is valid but NTP is not synchronized")
    detail = f"UTC={now.isoformat()}"
    if synchronized == "yes":
        detail += "; NTP synchronized"
    else:
        detail += "; NTP state unavailable on this host"
    return DoctorCheck("clock", "PASS", detail)


def _check_disk(settings: RuntimeSettings) -> DoctorCheck:
    probe = settings.telemetry.path.parent
    existing = probe
    while not existing.exists() and existing != existing.parent:
        existing = existing.parent
    try:
        free = shutil.disk_usage(existing).free
    except OSError as exc:
        return DoctorCheck("disk", "FAIL", f"disk usage unavailable: {exc}")
    status: Status = (
        "PASS" if free >= settings.telemetry.min_free_bytes else "FAIL"
    )
    return DoctorCheck(
        "disk",
        status,
        f"free={free} required={settings.telemetry.min_free_bytes} path={existing}",
    )


def _check_recording_dir(settings: RuntimeSettings) -> DoctorCheck:
    directory = settings.telemetry.path.parent
    try:
        directory.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(prefix=".doctor-", dir=directory, delete=True):
            pass
    except OSError as exc:
        return DoctorCheck("recording_dir", "FAIL", f"not writable: {directory}: {exc}")
    return DoctorCheck(
        "recording_dir",
        "PASS",
        f"writable={directory}; quota={settings.telemetry.max_bytes}",
    )


def _check_camera(settings: RuntimeSettings) -> DoctorCheck:
    devices = sorted(glob.glob("/dev/video*") + glob.glob("/dev/media*"))
    if devices:
        return DoctorCheck("camera", "PASS", ", ".join(devices))
    status: Status = "WARN" if settings.profile != "LIVE" else "FAIL"
    return DoctorCheck(
        "camera",
        status,
        f"no camera device node; configured index={settings.sensors.camera_device}",
    )


def _check_mcu(settings: RuntimeSettings) -> DoctorCheck:
    if settings.profile == "SIM":
        return DoctorCheck("mcu", "PASS", "SIM profile: USB MCU device was not opened")
    if settings.mcu.port.startswith("loop://"):
        return DoctorCheck("mcu", "PASS", "USB serial loopback selected")
    device = Path(settings.mcu.port)
    if device.exists():
        return DoctorCheck("mcu", "PASS", f"USB serial device exists: {device}")
    status: Status = "WARN" if settings.profile == "HIL" else "FAIL"
    return DoctorCheck(
        "mcu",
        status,
        f"USB serial device missing: {device}; no device was opened",
    )


def run_doctor(
    config_path: str | Path,
    *,
    api_url: str | None = None,
) -> dict[str, object]:
    """Run diagnostics without constructing a CAN or GPIO adapter."""

    checks: list[DoctorCheck] = []
    try:
        settings = load_runtime_config(config_path)
    except RuntimeConfigError as exc:
        checks.append(DoctorCheck("config", "FAIL", str(exc)))
        return {
            "ok": False,
            "profile": None,
            "physicalOutputAttempted": False,
            "checks": [asdict(item) for item in checks],
        }

    checks.append(
        DoctorCheck(
            "config",
            "PASS",
            f"schema={settings.schema_version} profile={settings.profile} source={settings.source}",
        )
    )
    checks.extend(
        [
            _check_clock(),
            _check_disk(settings),
            _check_recording_dir(settings),
            _check_camera(settings),
            _check_mcu(settings),
        ]
    )

    base_url = api_url or f"http://{settings.api.host}:{settings.api.port}"
    health = _api_json(f"{base_url.rstrip('/')}/health")
    if health is None:
        checks.append(DoctorCheck("api", "WARN", f"not reachable: {base_url}"))
        arduino_status: Status = "WARN" if settings.profile != "SIM" else "PASS"
        checks.append(
            DoctorCheck(
                "arduino",
                arduino_status,
                "not queried because API is offline; no hardware connection attempted",
            )
        )
    else:
        runtime_mode = health.get("runtimeMode")
        physical = health.get("physicalOutputEnabled")
        if runtime_mode != settings.profile or physical is True:
            checks.append(
                DoctorCheck(
                    "api",
                    "FAIL",
                    f"unsafe/mismatched health: runtime={runtime_mode} physical={physical}",
                )
            )
        else:
            checks.append(
                DoctorCheck(
                    "api",
                    "PASS",
                    f"runtime={runtime_mode} physicalOutputEnabled={physical}",
                )
            )
        hardware = _api_json(f"{base_url.rstrip('/')}/hardware/health") or {}
        reachable = hardware.get("arduinoReachable", hardware.get("picoReachable"))
        arduino_status = "PASS" if reachable is True or settings.profile == "SIM" else "WARN"
        checks.append(
            DoctorCheck(
                "arduino",
                arduino_status,
                f"arduinoReachable={reachable}; read-only API check",
            )
        )

    return {
        "ok": not any(item.status == "FAIL" for item in checks),
        "profile": settings.profile,
        "physicalOutputAttempted": False,
        "checks": [asdict(item) for item in checks],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Gökkalkan read-only diagnostics")
    parser.add_argument(
        "--config",
        default=os.environ.get(
            "GOKKALKAN_RUNTIME_CONFIG", "config/runtime/sim.toml"
        ),
    )
    parser.add_argument("--api-url", default=None)
    parser.add_argument("--json", action="store_true", dest="as_json")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="WARN sonuçlarını da başarısız say.",
    )
    args = parser.parse_args(argv)
    report = run_doctor(args.config, api_url=args.api_url)

    if args.as_json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(
            f"Gökkalkan doctor · profile={report['profile']} · "
            "physicalOutputAttempted=false"
        )
        for item in report["checks"]:  # type: ignore[union-attr]
            print(f"[{item['status']}] {item['name']}: {item['detail']}")

    warnings = any(
        item["status"] == "WARN" for item in report["checks"]  # type: ignore[union-attr]
    )
    return 1 if not report["ok"] or (args.strict and warnings) else 0


if __name__ == "__main__":
    raise SystemExit(main())
