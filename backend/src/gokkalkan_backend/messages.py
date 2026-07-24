"""Versioned immutable command and event envelopes for Mission Core."""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from types import MappingProxyType
from typing import Any, Callable, Mapping

MESSAGE_SCHEMA_VERSION = 1
SUPPORTED_MESSAGE_SCHEMA_VERSIONS = frozenset({MESSAGE_SCHEMA_VERSION})


class MessageContractError(ValueError):
    """Raised when a message cannot be accepted deterministically."""


def utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def deep_freeze(value: Any) -> Any:
    """Recursively freeze JSON-like values for cross-thread publication."""

    if isinstance(value, Mapping):
        return MappingProxyType(
            {str(key): deep_freeze(item) for key, item in value.items()}
        )
    if isinstance(value, list | tuple):
        return tuple(deep_freeze(item) for item in value)
    if isinstance(value, set | frozenset):
        return tuple(sorted(deep_freeze(item) for item in value))
    return value


def deep_thaw(value: Any) -> Any:
    """Return a detached JSON-serializable copy of a frozen value."""

    if isinstance(value, Mapping):
        return {str(key): deep_thaw(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [deep_thaw(item) for item in value]
    return value


def _require_schema(version: int) -> None:
    if version not in SUPPORTED_MESSAGE_SCHEMA_VERSIONS:
        raise MessageContractError(
            f"unsupported message schema version: {version}; "
            f"supported={sorted(SUPPORTED_MESSAGE_SCHEMA_VERSIONS)}"
        )


@dataclass(frozen=True, slots=True)
class CommandEnvelope:
    schema_version: int
    run_id: str
    command_id: str
    sequence: int
    created_at_utc: str
    created_at_monotonic_ns: int
    source: str
    kind: str
    payload: Mapping[str, Any]
    causation_id: str | None = None
    target_id: str | None = None
    track_id: str | None = None
    source_sequence: int | None = None

    @classmethod
    def create(
        cls,
        *,
        run_id: str,
        sequence: int,
        source: str,
        kind: str,
        payload: Mapping[str, Any] | None = None,
        command_id: str | None = None,
        causation_id: str | None = None,
        target_id: str | None = None,
        track_id: str | None = None,
        source_sequence: int | None = None,
        schema_version: int = MESSAGE_SCHEMA_VERSION,
        wall_clock: Callable[[], str] = utc_now,
        monotonic_ns: Callable[[], int] = time.monotonic_ns,
    ) -> "CommandEnvelope":
        _require_schema(schema_version)
        if not run_id.strip() or not source.strip() or not kind.strip():
            raise MessageContractError("run_id, source and kind must not be empty")
        if sequence < 1:
            raise MessageContractError("command sequence must be positive")
        if source_sequence is not None and source_sequence < 1:
            raise MessageContractError("source_sequence must be positive")
        return cls(
            schema_version=schema_version,
            run_id=run_id,
            command_id=command_id or f"CMD-{uuid.uuid4().hex.upper()}",
            sequence=sequence,
            created_at_utc=wall_clock(),
            created_at_monotonic_ns=monotonic_ns(),
            source=source,
            kind=kind,
            payload=deep_freeze(dict(payload or {})),
            causation_id=causation_id,
            target_id=target_id,
            track_id=track_id,
            source_sequence=source_sequence,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schemaVersion": self.schema_version,
            "runId": self.run_id,
            "commandId": self.command_id,
            "sequence": self.sequence,
            "createdAtUtc": self.created_at_utc,
            "createdAtMonotonicNs": self.created_at_monotonic_ns,
            "source": self.source,
            "kind": self.kind,
            "payload": deep_thaw(self.payload),
            "causationId": self.causation_id,
            "targetId": self.target_id,
            "trackId": self.track_id,
            "sourceSequence": self.source_sequence,
        }


@dataclass(frozen=True, slots=True)
class EventEnvelope:
    schema_version: int
    run_id: str
    event_id: str
    sequence: int
    created_at_utc: str
    created_at_monotonic_ns: int
    source: str
    event_type: str
    payload: Mapping[str, Any]
    command_id: str | None = None
    causation_id: str | None = None
    target_id: str | None = None
    track_id: str | None = None

    @classmethod
    def create(
        cls,
        *,
        run_id: str,
        sequence: int,
        source: str,
        event_type: str,
        payload: Mapping[str, Any] | None = None,
        command_id: str | None = None,
        causation_id: str | None = None,
        target_id: str | None = None,
        track_id: str | None = None,
        schema_version: int = MESSAGE_SCHEMA_VERSION,
        wall_clock: Callable[[], str] = utc_now,
        monotonic_ns: Callable[[], int] = time.monotonic_ns,
    ) -> "EventEnvelope":
        _require_schema(schema_version)
        if sequence < 1:
            raise MessageContractError("event sequence must be positive")
        return cls(
            schema_version=schema_version,
            run_id=run_id,
            event_id=f"EVT-{run_id}-{sequence:012d}",
            sequence=sequence,
            created_at_utc=wall_clock(),
            created_at_monotonic_ns=monotonic_ns(),
            source=source,
            event_type=event_type,
            payload=deep_freeze(dict(payload or {})),
            command_id=command_id,
            causation_id=causation_id,
            target_id=target_id,
            track_id=track_id,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schemaVersion": self.schema_version,
            "runId": self.run_id,
            "eventId": self.event_id,
            "sequence": self.sequence,
            "createdAtUtc": self.created_at_utc,
            "createdAtMonotonicNs": self.created_at_monotonic_ns,
            "source": self.source,
            "eventType": self.event_type,
            "payload": deep_thaw(self.payload),
            "commandId": self.command_id,
            "causationId": self.causation_id,
            "targetId": self.target_id,
            "trackId": self.track_id,
        }
