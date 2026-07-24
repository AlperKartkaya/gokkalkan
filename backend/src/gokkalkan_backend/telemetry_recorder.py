"""Minimal single-writer Unix socket telemetry recorder service."""

from __future__ import annotations

import argparse
import json
import os
import signal
import socket
import threading
from pathlib import Path
from typing import Any

from .telemetry_log import JsonlTelemetryStore


class TelemetryRecorder:
    """Receive JSON datagrams and persist them through one JSONL writer."""

    def __init__(
        self,
        socket_path: str | Path,
        output_path: str | Path,
        *,
        max_bytes: int,
    ) -> None:
        self.socket_path = Path(socket_path)
        self.store = JsonlTelemetryStore(output_path, max_bytes=max_bytes)
        self._stop = threading.Event()
        self._socket: socket.socket | None = None

    def stop(self) -> None:
        self._stop.set()

    def serve(self) -> None:
        if not hasattr(socket, "AF_UNIX"):
            raise RuntimeError("telemetry recorder requires Unix domain sockets")
        self.socket_path.parent.mkdir(parents=True, exist_ok=True)
        self.socket_path.unlink(missing_ok=True)
        server = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
        self._socket = server
        try:
            server.bind(str(self.socket_path))
            os.chmod(self.socket_path, 0o660)
            server.settimeout(0.5)
            while not self._stop.is_set():
                try:
                    raw = server.recv(65_535)
                except TimeoutError:
                    continue
                self._record_datagram(raw)
        finally:
            server.close()
            self._socket = None
            self.socket_path.unlink(missing_ok=True)

    def _record_datagram(self, raw: bytes) -> dict[str, Any] | None:
        try:
            value = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return None
        if not isinstance(value, dict):
            return None
        record_type = value.get("recordType")
        payload = value.get("payload")
        if not isinstance(record_type, str) or not isinstance(payload, dict):
            return None
        return self.store.append(record_type, payload)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Gökkalkan telemetry recorder")
    parser.add_argument(
        "--socket", default="/run/gokkalkan/telemetry-recorder.sock"
    )
    parser.add_argument(
        "--output",
        default="/var/lib/gokkalkan/telemetry/recorder.jsonl",
    )
    parser.add_argument("--max-bytes", type=int, default=536_870_912)
    args = parser.parse_args(argv)
    if args.max_bytes < 1_048_576:
        parser.error("--max-bytes must be at least 1048576")

    recorder = TelemetryRecorder(
        args.socket,
        args.output,
        max_bytes=args.max_bytes,
    )

    def stop_handler(_signum: int, _frame: object) -> None:
        recorder.stop()

    signal.signal(signal.SIGINT, stop_handler)
    signal.signal(signal.SIGTERM, stop_handler)
    recorder.serve()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
