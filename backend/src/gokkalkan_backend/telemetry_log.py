"""JSONL telemetry persistence for Gökkalkan dry-run backend evidence.

The store is deliberately tiny and dependency-free. It is for development,
KTR evidence export and replay/debugging; it is not a realtime database.
Generated files live under ignored `telemetry_data/` by default.
"""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from itertools import count
from pathlib import Path
from typing import Any, Callable

Clock = Callable[[], str]


def utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def default_telemetry_path() -> Path:
    configured = os.environ.get("GOKKALKAN_TELEMETRY_JSONL", "").strip()
    if configured:
        return Path(configured)
    return Path("telemetry_data/operator-api-dry-run.jsonl")


class JsonlTelemetryStore:
    """Append/read/reset telemetry records as UTF-8 JSONL."""

    def __init__(self, path: str | Path | None = None, clock: Clock = utc_now) -> None:
        self.path = Path(path) if path is not None else default_telemetry_path()
        self._clock = clock
        self._ids = count(1)

    def append(self, record_type: str, payload: dict[str, Any]) -> dict[str, Any]:
        record = {
            "recordId": next(self._ids),
            "timestamp": self._clock(),
            "recordType": record_type,
            "payload": payload,
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
        return record

    def read_all(self, limit: int | None = None) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        records: list[dict[str, Any]] = []
        with self.path.open("r", encoding="utf-8") as handle:
            for line in handle:
                stripped = line.strip()
                if not stripped:
                    continue
                try:
                    value = json.loads(stripped)
                except json.JSONDecodeError:
                    records.append({"recordType": "corrupt", "raw": stripped})
                    continue
                if isinstance(value, dict):
                    records.append(value)
        if limit is not None and limit >= 0:
            return records[-limit:]
        return records

    def reset(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text("", encoding="utf-8")
        self._ids = count(1)

    def metadata(self) -> dict[str, Any]:
        return {
            "path": str(self.path),
            "exists": self.path.exists(),
            "recordCount": len(self.read_all()),
        }
