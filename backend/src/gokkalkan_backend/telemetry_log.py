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
from threading import RLock
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

    def __init__(
        self,
        path: str | Path | None = None,
        clock: Clock = utc_now,
        max_bytes: int | None = None,
    ) -> None:
        self.path = Path(path) if path is not None else default_telemetry_path()
        self._clock = clock
        self._ids = count(1)
        self._lock = RLock()
        self.max_bytes = max_bytes
        self._current_record_count = self._count_existing_records()

    @property
    def rotated_path(self) -> Path:
        return self.path.with_suffix(self.path.suffix + ".1")

    def _rotate_if_needed(self, incoming_size: int) -> None:
        if self.max_bytes is None:
            return
        if incoming_size > self.max_bytes:
            raise ValueError("telemetry record exceeds the configured byte quota")
        if not self.path.exists():
            return
        segment_limit = max(1, self.max_bytes // 2)
        current_size = self.path.stat().st_size
        if current_size + incoming_size <= segment_limit:
            return

        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.rotated_path.unlink(missing_ok=True)
        self.path.replace(self.rotated_path)
        self._current_record_count = 0
        if self.rotated_path.stat().st_size + incoming_size > self.max_bytes:
            self.rotated_path.unlink()

    def _count_existing_records(self) -> int:
        if not self.path.exists():
            return 0
        try:
            with self.path.open("r", encoding="utf-8") as handle:
                return sum(1 for line in handle if line.strip())
        except OSError:
            return 0

    def append(self, record_type: str, payload: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            record = {
                "recordId": next(self._ids),
                "timestamp": self._clock(),
                "recordType": record_type,
                "payload": payload,
            }
            self.path.parent.mkdir(parents=True, exist_ok=True)
            encoded = json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n"
            self._rotate_if_needed(len(encoded.encode("utf-8")))
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(encoded)
            self._current_record_count += 1
            return record

    def read_all(self, limit: int | None = None) -> list[dict[str, Any]]:
        with self._lock:
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
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text("", encoding="utf-8")
            self._ids = count(1)
            self._current_record_count = 0

    def metadata(self) -> dict[str, Any]:
        with self._lock:
            size_bytes = self.path.stat().st_size if self.path.exists() else 0
            rotated_size_bytes = (
                self.rotated_path.stat().st_size
                if self.rotated_path.exists()
                else 0
            )
            return {
                "path": str(self.path),
                "exists": self.path.exists(),
                "recordCount": self._current_record_count,
                "maxBytes": self.max_bytes,
                "sizeBytes": size_bytes,
                "rotatedPath": str(self.rotated_path),
                "rotatedExists": self.rotated_path.exists(),
                "rotatedSizeBytes": rotated_size_bytes,
                "retainedBytes": size_bytes + rotated_size_bytes,
            }
