"""Quality, HIL and release-gate command surfaces."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from .hil_runner import HilProfile, run_hil_plan
from .calibration_workflow import evaluate_lidar_file
from .turret_calibration import solve_calibration_file
from .release_gate import build_release_manifest, verify_release_manifest
from .runtime_config import load_runtime_config
from .verification import PerformanceBudget, run_fault_injection_suite, run_soak


def _hash(path: str | Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _print(payload: object) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))


def quality_main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="gokkalkan quality")
    sub = parser.add_subparsers(dest="operation", required=True)
    sub.add_parser("faults")
    soak = sub.add_parser("soak")
    soak.add_argument("--duration-sec", type=int, default=1800)
    soak.add_argument("--step-sec", type=float, default=0.1)
    soak.add_argument("--real-time", action="store_true")
    soak.add_argument("--output")
    perf = sub.add_parser("performance")
    perf.add_argument("measurements")
    perf.add_argument("--budget", default="config/quality/performance.toml")
    args = parser.parse_args(argv)
    if args.operation == "faults":
        result = run_fault_injection_suite()
    elif args.operation == "soak":
        result = run_soak(
            duration_seconds=args.duration_sec,
            step_seconds=args.step_sec,
            realtime=args.real_time,
            output=args.output,
        )
    else:
        measured = json.loads(Path(args.measurements).read_text(encoding="utf-8"))
        result = PerformanceBudget.load(args.budget).evaluate(measured)
    _print(result)
    return 0 if result["ok"] else 1


def hil_main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="gokkalkan hil")
    parser.add_argument("--output", required=True)
    parser.add_argument("--config", default="config/runtime/hil-physical.toml")
    parser.add_argument("--calibration", default="config/calibration/tfa50_l.toml")
    parser.add_argument("--evidence")
    args = parser.parse_args(argv)
    evidence = (
        json.loads(Path(args.evidence).read_text(encoding="utf-8"))
        if args.evidence
        else None
    )
    runtime = load_runtime_config(args.config)
    if runtime.profile != "HIL":
        parser.error("--config must select a HIL profile")
    profile = HilProfile(
        profile_id="HIL-SAFE-LOAD-V1",
        mcu_port=runtime.mcu.port,
        safe_load=runtime.hil.safe_load,
        allows_destructive_output=runtime.hil.destructive_output_enabled,
        config_hash=_hash(args.config),
        calibration_hash=_hash(args.calibration),
    )
    result = run_hil_plan(profile, output=args.output, physical_evidence=evidence)
    _print(result)
    return 0 if result["softwareHarness"]["ok"] else 1


def release_main(argv: list[str]) -> int:
    if argv and argv[0] == "verify":
        parser = argparse.ArgumentParser(prog="gokkalkan release verify")
        parser.add_argument("manifest")
        args = parser.parse_args(argv[1:])
        result = verify_release_manifest(args.manifest)
        _print(result)
        return 0 if result["ok"] else 1
    if argv and argv[0] == "build":
        argv = argv[1:]
    parser = argparse.ArgumentParser(prog="gokkalkan release")
    parser.add_argument("--version", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--software-gate", action="store_true")
    parser.add_argument("--sensor-evidence")
    parser.add_argument("--hil-evidence")
    parser.add_argument(
        "--component",
        action="append",
        default=[],
        help="Repo köküne göre release bileşeni; birden fazla kullanılabilir.",
    )
    args = parser.parse_args(argv)
    components = args.component or [
        "pyproject.toml",
        "backend/src",
        "backend/hardware_mock",
        "perception/src",
        "frontend/src",
        "tests",
        "frontend/package-lock.json",
        "firmware/pico/CMakeLists.txt",
        "config",
    ]
    result = build_release_manifest(
        root=".",
        version=args.version,
        component_paths=components,
        output=args.output,
        software_gate=args.software_gate,
        sensor_evidence=args.sensor_evidence,
        hil_evidence=args.hil_evidence,
    )
    _print(result)
    return 0 if result["gates"]["software"] else 1


def lidar_main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="gokkalkan lidar")
    sub = parser.add_subparsers(dest="operation", required=True)
    calibrate = sub.add_parser("calibrate")
    calibrate.add_argument("observations")
    calibrate.add_argument("--output", required=True)
    probe = sub.add_parser(
        "probe",
        help="TFA50-L UART akışını komut göndermeden salt-okunur doğrula",
    )
    probe.add_argument("--port", required=True)
    probe.add_argument("--baud-rate", type=int, default=460_800)
    probe.add_argument("--timeout-sec", type=float, default=2.0)
    args = parser.parse_args(argv)
    if args.operation == "probe":
        from .lidar_adapter import probe_tfa50l_uart

        result = probe_tfa50l_uart(
            args.port,
            baud_rate=args.baud_rate,
            timeout_sec=args.timeout_sec,
        )
        _print(result)
        return 0 if result["ok"] else 1
    result = evaluate_lidar_file(args.observations, args.output)
    _print(result)
    return 0 if result["physicalGatePassed"] else 1


def turret_main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="gokkalkan turret")
    sub = parser.add_subparsers(dest="operation", required=True)
    calibrate = sub.add_parser("calibrate")
    calibrate.add_argument("observations")
    calibrate.add_argument("--output", default="config/calibration/turret.toml")
    calibrate.add_argument(
        "--activate",
        action="store_true",
        help="Çözümü runtime komut düzeltmesi için ACTIVE işaretle.",
    )
    args = parser.parse_args(argv)
    result = solve_calibration_file(
        args.observations,
        args.output,
        activate=args.activate,
    )
    _print(result.to_dict())
    return 0
