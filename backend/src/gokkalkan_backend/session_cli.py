"""Command-line tools for deterministic scenarios, replay and evidence."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .digital_twin import SCENARIOS, SensorFixtureReplay, run_scenario
from .telemetry_session import (
    build_evidence_package,
    replay_session,
    verify_evidence,
    verify_session,
)


def _print(value: object) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True))


def scenario_main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="gokkalkan scenario")
    subcommands = parser.add_subparsers(dest="operation", required=True)
    run = subcommands.add_parser("run", help="deterministik senaryoyu çalıştır")
    run.add_argument("name", choices=SCENARIOS)
    run.add_argument("--output")
    fixtures = subcommands.add_parser(
        "fixtures", help="kamera ve TFA50-L fixture JSONL dosyasını üret"
    )
    fixtures.add_argument("output")
    args = parser.parse_args(argv)
    if args.operation == "fixtures":
        path = SensorFixtureReplay.write(args.output)
        _print({"ok": True, "path": str(path), "physicalOutput": False})
        return 0
    result = run_scenario(args.name, args.output)
    _print(result)
    return 0


def replay_main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="gokkalkan replay")
    subcommands = parser.add_subparsers(dest="operation", required=True)
    verify = subcommands.add_parser("verify", help="session bütünlüğünü doğrula")
    verify.add_argument("session")
    run = subcommands.add_parser("run", help="session'ı salt okunur tekrar oynat")
    run.add_argument("session")
    args = parser.parse_args(argv)
    result = (
        verify_session(args.session)
        if args.operation == "verify"
        else replay_session(args.session)
    )
    _print(result)
    return 0 if result["ok"] else 1


def evidence_main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="gokkalkan evidence")
    subcommands = parser.add_subparsers(dest="operation", required=True)
    build = subcommands.add_parser("build", help="doğrulanabilir kanıt paketi üret")
    build.add_argument("session")
    build.add_argument("--output", required=True)
    build.add_argument("--capability", required=True)
    build.add_argument("--start-ns", type=int, required=True)
    build.add_argument("--end-ns", type=int, required=True)
    verify = subcommands.add_parser(
        "verify", help="session veya kanıt paketi bütünlüğünü doğrula"
    )
    verify.add_argument("source")
    args = parser.parse_args(argv)
    if args.operation == "build":
        if args.end_ns < args.start_ns:
            parser.error("--end-ns must be greater than or equal to --start-ns")
        try:
            result = build_evidence_package(
                args.session,
                args.output,
                capability_id=args.capability,
                start_monotonic_ns=args.start_ns,
                end_monotonic_ns=args.end_ns,
            )
        except (OSError, ValueError) as exc:
            result = {
                "ok": False,
                "errors": [f"{type(exc).__name__}:{exc}"],
                "session": args.session,
            }
    else:
        source = Path(args.source)
        result = verify_session(source) if source.is_dir() else verify_evidence(source)
    _print(result)
    return 0 if result["ok"] else 1
