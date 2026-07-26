"""Unified command line entry point installed as ``gokkalkan``."""

from __future__ import annotations

import sys

from . import (
    doctor,
    operator_http_server,
    operations_cli,
    session_cli,
    static_server,
    telemetry_recorder,
)


def _usage() -> str:
    return """Gökkalkan CLI

Usage:
  gokkalkan operator-api [options]
  gokkalkan doctor [options]
  gokkalkan static-server [options]
  gokkalkan telemetry-recorder [options]
  gokkalkan scenario run <name> [--output PATH]
  gokkalkan scenario fixtures <output>
  gokkalkan replay verify|run <session>
  gokkalkan evidence build|verify ...
  gokkalkan quality faults|soak|performance ...
  gokkalkan hil --output REPORT
  gokkalkan release [build] --version VERSION --output MANIFEST ...
  gokkalkan release verify MANIFEST
  gokkalkan lidar calibrate OBSERVATIONS --output REPORT
  gokkalkan turret calibrate OBSERVATIONS [--output FILE] [--activate]
"""


def main(argv: list[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    if not arguments or arguments[0] in {"-h", "--help", "help"}:
        print(_usage())
        return 0
    command, command_args = arguments[0], arguments[1:]
    if command == "operator-api":
        operator_http_server.main(command_args)
        return 0
    if command == "doctor":
        return doctor.main(command_args)
    if command == "static-server":
        return static_server.main(command_args)
    if command == "telemetry-recorder":
        return telemetry_recorder.main(command_args)
    if command == "scenario":
        return session_cli.scenario_main(command_args)
    if command == "replay":
        return session_cli.replay_main(command_args)
    if command == "evidence":
        return session_cli.evidence_main(command_args)
    if command == "quality":
        return operations_cli.quality_main(command_args)
    if command == "hil":
        return operations_cli.hil_main(command_args)
    if command == "release":
        return operations_cli.release_main(command_args)
    if command == "lidar":
        return operations_cli.lidar_main(command_args)
    if command == "turret":
        return operations_cli.turret_main(command_args)
    print(f"Unknown command: {command}\n\n{_usage()}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
