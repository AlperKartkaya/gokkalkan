"""Minimal single-writer Unix socket telemetry recorder service."""

from __future__ import annotations

import argparse
import errno
import json
import os
import signal
import socket
import threading
import time
from pathlib import Path
from typing import Any

from .telemetry_session import SessionTelemetryStore


class TelemetryProducer:
    """Process-safe producer facade; persistence remains recorder-owned."""

    def __init__(self, socket_path: str | Path) -> None:
        self.socket_path = Path(socket_path)

    def append(self, record_type: str, payload: dict[str, Any]) -> None:
        message = json.dumps(
            {"recordType": record_type, "payload": payload},
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
        if len(message) > 65_535:
            raise ValueError("telemetry datagram exceeds 65535 bytes")
        with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as client:
            deadline = time.monotonic() + 2.0
            while True:
                try:
                    client.sendto(message, str(self.socket_path))
                    return
                except OSError as exc:
                    if (
                        exc.errno not in {errno.ENOBUFS, errno.EAGAIN}
                        or time.monotonic() >= deadline
                    ):
                        raise
                    time.sleep(0.005)


class TelemetryRecorder:
    """Receive JSON datagrams and persist them through one JSONL writer."""

    def __init__(
        self,
        socket_path: str | Path,
        output_path: str | Path,
        *,
        max_bytes: int,
        min_free_bytes: int = 268_435_456,
    ) -> None:
        self.socket_path = Path(socket_path)
        self.store = SessionTelemetryStore.from_output_path(
            output_path,
            max_bytes=max_bytes,
            min_free_bytes=min_free_bytes,
        )
        self._stop = threading.Event()
        self._socket: socket.socket | None = None
        self._closed = False

    def stop(self) -> None:
        self._stop.set()

    def close(self) -> None:
        if not self._closed:
            self.store.close()
            self._closed = True

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
            self.close()

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
    parser.add_argument("--min-free-bytes", type=int, default=268_435_456)
    args = parser.parse_args(argv)
    if args.max_bytes < 1_048_576:
        parser.error("--max-bytes must be at least 1048576")

    recorder = TelemetryRecorder(
        args.socket,
        args.output,
        max_bytes=args.max_bytes,
        min_free_bytes=args.min_free_bytes,
    )

    def stop_handler(_signum: int, _frame: object) -> None:
        recorder.stop()

    signal.signal(signal.SIGINT, stop_handler)
    signal.signal(signal.SIGTERM, stop_handler)
    recorder.serve()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
