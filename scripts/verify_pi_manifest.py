#!/usr/bin/env python3
"""Validate the Pi deployment manifest and optionally the current host."""

from __future__ import annotations

import argparse
import json
import platform
import pwd
import subprocess
import sys
import tomllib
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.request import urlopen

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = REPO_ROOT / "deploy/pi/manifest.toml"


class ManifestError(ValueError):
    pass


def _require_tokens(path: Path, tokens: tuple[str, ...]) -> None:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ManifestError(f"deployment file cannot be read: {path}: {exc}") from exc
    missing = [token for token in tokens if token not in text]
    if missing:
        raise ManifestError(
            f"{path.relative_to(REPO_ROOT)} is missing contract: "
            + ", ".join(missing)
        )


def load_manifest(path: str | Path) -> dict[str, Any]:
    source = Path(path)
    try:
        data = tomllib.loads(source.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise ManifestError(f"manifest cannot be read: {source}: {exc}") from exc
    for table in (
        "os",
        "runtime",
        "packages",
        "permissions",
        "can",
        "camera",
        "verification",
    ):
        if not isinstance(data.get(table), dict):
            raise ManifestError(f"missing [{table}] table")
    if data.get("schema_version") != 1:
        raise ManifestError("unsupported schema_version")
    packages = data["packages"].get("apt")
    if not isinstance(packages, list) or not packages or not all(
        isinstance(item, str) and item for item in packages
    ):
        raise ManifestError("packages.apt must be a non-empty string list")
    if len(packages) != len(set(packages)):
        raise ManifestError("packages.apt contains duplicates")
    if data["can"].get("bitrate") != 500000:
        raise ManifestError("CAN bitrate must match ADR-002 (500000)")
    if data["verification"].get("runtime_profile") != "SIM":
        raise ManifestError("clean image verification must start in SIM")
    for unit in (
        "gokkalkan-backend.service",
        "gokkalkan-perception.service",
        "gokkalkan-frontend.service",
        "gokkalkan-telemetry.service",
        "gokkalkan.target",
    ):
        if not (REPO_ROOT / "deploy/systemd" / unit).is_file():
            raise ManifestError(f"missing systemd unit: {unit}")
    systemd = REPO_ROOT / "deploy/systemd"
    _require_tokens(
        systemd / "gokkalkan-backend.service",
        (
            "Requires=gokkalkan-telemetry.service",
            "After=network.target gokkalkan-telemetry.service",
            "Restart=on-failure",
            "KillSignal=SIGINT",
            "StandardOutput=journal",
        ),
    )
    _require_tokens(
        systemd / "gokkalkan-perception.service",
        (
            "ConditionPathExists=/etc/gokkalkan/enable-perception",
            "Requires=gokkalkan-backend.service",
            "SupplementaryGroups=video render",
            "Restart=on-failure",
        ),
    )
    _require_tokens(
        systemd / "gokkalkan-frontend.service",
        (
            "Requires=gokkalkan-backend.service",
            "gokkalkan static-server",
            "--host 127.0.0.1",
            "Restart=on-failure",
        ),
    )
    _require_tokens(
        systemd / "gokkalkan-telemetry.service",
        (
            "Before=gokkalkan-backend.service",
            "gokkalkan telemetry-recorder",
            "RuntimeDirectory=gokkalkan",
            "StateDirectory=gokkalkan",
        ),
    )
    _require_tokens(
        systemd / "gokkalkan.target",
        (
            "Requires=gokkalkan-telemetry.service gokkalkan-backend.service "
            "gokkalkan-frontend.service",
            "Wants=gokkalkan-perception.service",
        ),
    )
    _require_tokens(
        REPO_ROOT / "scripts/bootstrap_pi.sh",
        (
            "config/runtime/pi-sim.toml",
            "systemctl enable --now gokkalkan.target",
            "installed-packages.lock",
        ),
    )
    return data


def parse_os_release(path: str | Path = "/etc/os-release") -> dict[str, str]:
    values: dict[str, str] = {}
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if "=" not in line or line.startswith("#"):
            continue
        key, value = line.split("=", 1)
        values[key] = value.strip().strip('"')
    return values


def verify_host(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    release = parse_os_release()
    os_config = data["os"]
    if release.get("ID") not in os_config["allowed_ids"]:
        errors.append(f"OS ID mismatch: {release.get('ID')}")
    if release.get("VERSION_ID") != os_config["version_id"]:
        errors.append(f"OS version mismatch: {release.get('VERSION_ID')}")
    if release.get("VERSION_CODENAME") != os_config["codename"]:
        errors.append(f"OS codename mismatch: {release.get('VERSION_CODENAME')}")
    if platform.machine() != os_config["architecture"]:
        errors.append(f"architecture mismatch: {platform.machine()}")

    runtime = data["runtime"]
    try:
        user = pwd.getpwnam(runtime["user"])
    except KeyError:
        errors.append(f"runtime user missing: {runtime['user']}")
    else:
        groups = {
            entry.gr_name
            for entry in __import__("grp").getgrall()
            if user.pw_name in entry.gr_mem or entry.gr_gid == user.pw_gid
        }
        missing_groups = sorted(set(data["permissions"]["groups"]) - groups)
        if missing_groups:
            errors.append("runtime groups missing: " + ", ".join(missing_groups))

    for path_key in ("install_dir", "venv_dir", "config_dir", "state_dir"):
        if not Path(runtime[path_key]).exists():
            errors.append(f"runtime path missing: {runtime[path_key]}")
    runtime_config = Path(data["verification"]["runtime_config"])
    if not runtime_config.is_file():
        errors.append(f"runtime config missing: {runtime_config}")

    python_path = Path(runtime["venv_dir"]) / "bin/python"
    if python_path.is_file():
        result = subprocess.run(
            [str(python_path), "--version"],
            capture_output=True,
            text=True,
            check=False,
        )
        version_output = f"{result.stdout} {result.stderr}"
        if f"Python {runtime['python']}." not in version_output:
            errors.append(f"Python version mismatch: {version_output.strip()}")

    for package in data["packages"]["apt"]:
        result = subprocess.run(
            ["dpkg-query", "-W", "-f=${Status}", package],
            capture_output=True,
            text=True,
            check=False,
        )
        if "install ok installed" not in result.stdout:
            errors.append(f"apt package missing: {package}")

    for unit in (
        "gokkalkan.target",
        "gokkalkan-telemetry.service",
        "gokkalkan-backend.service",
        "gokkalkan-frontend.service",
    ):
        result = subprocess.run(
            ["systemctl", "is-active", "--quiet", unit],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            errors.append(f"systemd unit is not active: {unit}")

    for name, url in (
        ("API", data["verification"]["api_health"]),
        ("UI", data["verification"]["ui_health"]),
    ):
        try:
            with urlopen(url, timeout=2.0) as response:
                if response.status != 200:
                    errors.append(f"{name} health returned HTTP {response.status}")
                    continue
                payload = json.loads(response.read().decode("utf-8"))
            if name == "API" and (
                payload.get("runtimeMode") != "SIM"
                or payload.get("physicalOutputEnabled") is not False
            ):
                errors.append(f"API health is not fail-safe SIM: {payload}")
            if name == "UI" and payload.get("ok") is not True:
                errors.append(f"UI health is not ready: {payload}")
        except (OSError, URLError) as exc:
            errors.append(f"{name} health unavailable: {exc}")
        except (UnicodeDecodeError, json.JSONDecodeError, AttributeError) as exc:
            errors.append(f"{name} health response is invalid: {exc}")
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify Gökkalkan Pi manifest")
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    parser.add_argument("--manifest-only", action="store_true")
    parser.add_argument("--host", action="store_true")
    args = parser.parse_args(argv)
    if not args.manifest_only and not args.host:
        args.manifest_only = True
    try:
        data = load_manifest(args.manifest)
    except ManifestError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    print(f"PASS: manifest schema {data['schema_version']} ({args.manifest})")
    if args.host:
        errors = verify_host(data)
        if errors:
            for error in errors:
                print(f"FAIL: {error}", file=sys.stderr)
            return 1
        print("PASS: current host matches Pi deployment manifest")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
