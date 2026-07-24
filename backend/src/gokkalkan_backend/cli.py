"""Unified command line entry point installed as ``gokkalkan``."""

from __future__ import annotations

import sys

from . import doctor, operator_http_server, static_server, telemetry_recorder


def _usage() -> str:
    return """Gökkalkan CLI

Usage:
  gokkalkan operator-api [options]
  gokkalkan doctor [options]
  gokkalkan static-server [options]
  gokkalkan telemetry-recorder [options]
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
    print(f"Unknown command: {command}\n\n{_usage()}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
