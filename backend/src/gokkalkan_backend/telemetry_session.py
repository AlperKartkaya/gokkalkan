"""Single-writer SQLite-WAL telemetry sessions and evidence verification."""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import os
import platform
import queue
import shutil
import sqlite3
import subprocess
import sys
import threading
import time
import uuid
import zipfile
from contextlib import closing
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable

Clock = Callable[[], str]
BULK_RECORD_TYPES = frozenset({"camera_frame", "video_segment", "lidar_packet", "can_frame"})


def utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _file_hash_matches(path: Path, expected: object) -> bool:
    try:
        return path.is_file() and sha256_file(path) == expected
    except OSError:
        return False


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _git_sha() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], text=True, stderr=subprocess.DEVNULL
        ).strip()
    except (OSError, subprocess.SubprocessError):
        return "UNKNOWN"


@dataclass(slots=True)
class _Request:
    operation: str
    data: dict[str, Any]
    done: threading.Event = field(default_factory=threading.Event)
    result: Any = None
    error: BaseException | None = None


class SessionTelemetryStore:
    """Queue-backed facade whose writer thread owns all persistent writes."""

    schema_version = 1

    def __init__(
        self,
        session_dir: str | Path,
        *,
        clock: Clock = utc_now,
        max_bytes: int = 536_870_912,
        min_free_bytes: int = 268_435_456,
        segment_bytes: int = 16_777_216,
        retention_segments: int = 32,
        operator_id: str = "UNASSIGNED",
        build_id: str | None = None,
        source_files: dict[str, str | Path] | None = None,
    ) -> None:
        self.session_dir = Path(session_dir)
        self.session_id = self.session_dir.name or f"SESSION-{uuid.uuid4().hex[:12].upper()}"
        self.path = self.session_dir / "events-000001.jsonl"
        self.db_path = self.session_dir / "events.sqlite3"
        self.manifest_path = self.session_dir / "manifest.json"
        self.media_dir = self.session_dir / "media"
        self.evidence_dir = self.session_dir / "evidence"
        self.rotated_path = self.session_dir / "events-000000.jsonl"
        self._clock = clock
        self.max_bytes = max_bytes
        self.min_free_bytes = min_free_bytes
        self.segment_bytes = max(1024, segment_bytes)
        self.retention_segments = max(1, retention_segments)
        self.operator_id = operator_id
        self.build_id = build_id or os.environ.get("GOKKALKAN_BUILD_ID", "DEV")
        self.created_at = self._clock()
        self.git_sha = _git_sha()
        self.source_files = {key: Path(value) for key, value in (source_files or {}).items()}
        self._source_snapshot = {
            label: {
                "path": str(path),
                "exists": path.exists(),
                "sha256": sha256_file(path) if path.exists() else None,
            }
            for label, path in self.source_files.items()
        }
        self._queue: queue.Queue[_Request] = queue.Queue(maxsize=8192)
        self._closed = False
        self._startup_error: BaseException | None = None
        self._ready = threading.Event()
        self._writer = threading.Thread(
            target=self._writer_loop,
            daemon=True,
            name=f"TelemetryWriter-{self.session_id}",
        )
        self._writer.start()
        if not self._ready.wait(timeout=5):
            raise RuntimeError("telemetry writer did not initialize")
        if self._startup_error is not None:
            raise RuntimeError("telemetry writer initialization failed") from self._startup_error

    @classmethod
    def from_output_path(
        cls, output: str | Path, **kwargs: Any
    ) -> "SessionTelemetryStore":
        path = Path(output)
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S")
        suffix = uuid.uuid4().hex[:8]
        return cls(
            path.parent / f"{path.stem}-{stamp}-{suffix}.session",
            **kwargs,
        )

    def _submit(self, operation: str, data: dict[str, Any]) -> Any:
        if self._closed:
            raise RuntimeError("telemetry session is closed")
        request = _Request(operation, data)
        try:
            self._queue.put(request, timeout=2)
        except queue.Full as exc:
            raise RuntimeError("telemetry writer queue is full") from exc
        if not request.done.wait(timeout=5):
            raise RuntimeError("telemetry writer did not acknowledge request")
        if request.error:
            raise request.error
        return request.result

    def append(self, record_type: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self._submit("append", {"recordType": record_type, "payload": payload})

    def index_media(
        self,
        *,
        kind: str,
        path: str | Path,
        start_monotonic_ns: int,
        end_monotonic_ns: int,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        source = Path(path)
        if end_monotonic_ns < start_monotonic_ns:
            raise ValueError("media interval end precedes start")
        return self._submit(
            "media",
            {
                "kind": kind,
                "path": str(source),
                "start": start_monotonic_ns,
                "end": end_monotonic_ns,
                "sha256": sha256_file(source) if source.exists() else None,
                "exists": source.exists(),
                "metadata": metadata or {},
            },
        )

    def read_all(self, limit: int | None = None) -> list[dict[str, Any]]:
        query = "SELECT record_json FROM records ORDER BY sequence"
        params: tuple[Any, ...] = ()
        if limit is not None and limit >= 0:
            query = (
                "SELECT record_json FROM "
                "(SELECT sequence, record_json FROM records ORDER BY sequence DESC LIMIT ?) "
                "ORDER BY sequence"
            )
            params = (limit,)
        with closing(sqlite3.connect(self.db_path)) as connection:
            return [json.loads(row[0]) for row in connection.execute(query, params)]

    def reset(self) -> None:
        self._submit("reset", {})

    def metadata(self) -> dict[str, Any]:
        with closing(sqlite3.connect(self.db_path)) as connection:
            record_count = int(connection.execute("SELECT COUNT(*) FROM records").fetchone()[0])
            invalid_count = int(
                connection.execute(
                    "SELECT COUNT(*) FROM integrity_issues WHERE resolved=0"
                ).fetchone()[0]
            )
        segments = sorted(self.session_dir.glob("events-*.jsonl"))
        return {
            "sessionId": self.session_id,
            "path": str(self.path),
            "databasePath": str(self.db_path),
            "manifestPath": str(self.manifest_path),
            "exists": self.db_path.exists(),
            "recordCount": record_count,
            "maxBytes": self.max_bytes,
            "sizeBytes": sum(path.stat().st_size for path in segments if path.exists()),
            "segmentCount": len(segments),
            "queueDepth": self._queue.qsize(),
            "writerThreadAlive": self._writer.is_alive(),
            "evidenceValid": invalid_count == 0,
            "integrityIssueCount": invalid_count,
        }

    def close(self) -> None:
        if self._closed:
            return
        self._submit("finalize", {})
        request = _Request("stop", {})
        self._queue.put(request)
        request.done.wait(timeout=5)
        self._closed = True
        self._writer.join(timeout=5)

    def _writer_loop(self) -> None:
        self.session_dir.mkdir(parents=True, exist_ok=True)
        self.media_dir.mkdir(exist_ok=True)
        self.evidence_dir.mkdir(exist_ok=True)
        connection: sqlite3.Connection | None = None
        try:
            connection = sqlite3.connect(self.db_path)
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute("PRAGMA synchronous=FULL")
            self._create_schema(connection)
            self._write_manifest(connection, finalized=False)
            connection.commit()
            self._ready.set()
            while True:
                request = self._queue.get()
                try:
                    if request.operation == "stop":
                        request.result = True
                        request.done.set()
                        break
                    request.result = self._handle_request(connection, request)
                except BaseException as exc:
                    connection.rollback()
                    request.error = exc
                finally:
                    if not request.done.is_set():
                        request.done.set()
                    self._queue.task_done()
        except BaseException as exc:
            self._startup_error = exc
            raise
        finally:
            if connection is not None:
                connection.close()
            self._ready.set()

    @staticmethod
    def _create_schema(connection: sqlite3.Connection) -> None:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS records(
              sequence INTEGER PRIMARY KEY,
              event_id TEXT NOT NULL UNIQUE,
              timestamp_utc TEXT NOT NULL,
              monotonic_ns INTEGER NOT NULL,
              record_type TEXT NOT NULL,
              source TEXT,
              command_id TEXT,
              track_id TEXT,
              record_json TEXT NOT NULL,
              record_sha256 TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_records_type_sequence
              ON records(record_type, sequence);
            CREATE INDEX IF NOT EXISTS idx_records_command
              ON records(command_id) WHERE command_id IS NOT NULL;
            CREATE TABLE IF NOT EXISTS media_index(
              media_id TEXT PRIMARY KEY,
              kind TEXT NOT NULL,
              path TEXT NOT NULL,
              start_monotonic_ns INTEGER NOT NULL,
              end_monotonic_ns INTEGER NOT NULL,
              sha256 TEXT,
              exists_on_index INTEGER NOT NULL,
              metadata_json TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_media_time
              ON media_index(start_monotonic_ns, end_monotonic_ns);
            CREATE TABLE IF NOT EXISTS integrity_issues(
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              code TEXT NOT NULL,
              detail TEXT NOT NULL,
              created_at_utc TEXT NOT NULL,
              resolved INTEGER NOT NULL DEFAULT 0
            );
            """
        )

    def _handle_request(
        self, connection: sqlite3.Connection, request: _Request
    ) -> Any:
        if request.operation == "append":
            return self._write_record(connection, request.data)
        if request.operation == "media":
            return self._write_media(connection, request.data)
        if request.operation == "reset":
            connection.executescript(
                "DELETE FROM records; DELETE FROM media_index; DELETE FROM integrity_issues;"
            )
            for segment in self.session_dir.glob("events-*.jsonl"):
                segment.unlink(missing_ok=True)
            connection.commit()
            self.path = self.session_dir / "events-000001.jsonl"
            self._write_manifest(connection, finalized=False)
            return True
        if request.operation == "finalize":
            self._write_manifest(connection, finalized=True)
            connection.commit()
            return True
        raise RuntimeError(f"unsupported telemetry writer operation: {request.operation}")

    def _write_record(
        self, connection: sqlite3.Connection, data: dict[str, Any]
    ) -> dict[str, Any]:
        record_type = str(data["recordType"])
        payload = dict(data["payload"])
        free = shutil.disk_usage(self.session_dir).free
        if free < self.min_free_bytes:
            self._issue(
                connection,
                "LOW_DISK",
                f"free={free} required={self.min_free_bytes}",
            )
            if record_type in BULK_RECORD_TYPES:
                payload = {
                    "dropped": True,
                    "reason": "LOW_DISK_GRACEFUL_DEGRADATION",
                    "originalKeys": sorted(payload),
                    "physicalOutput": False,
                }
        sequence = int(
            connection.execute("SELECT COALESCE(MAX(sequence), 0) + 1 FROM records").fetchone()[0]
        )
        event_id = f"EVT-{self.session_id}-{sequence:012d}"
        timestamp = self._clock()
        monotonic_ns = time.monotonic_ns()
        record = {
            "schemaVersion": self.schema_version,
            "sessionId": self.session_id,
            "recordId": sequence,
            "sequence": sequence,
            "eventId": event_id,
            "timestamp": timestamp,
            "monotonicNs": monotonic_ns,
            "recordType": record_type,
            "payload": payload,
        }
        encoded = _canonical(record)
        digest = hashlib.sha256(encoded.encode()).hexdigest()
        if len(encoded.encode("utf-8")) + 1 > self.max_bytes:
            self._issue(
                connection,
                "TELEMETRY_RECORD_EXCEEDS_QUOTA",
                f"sequence={sequence}",
            )
            connection.commit()
            raise ValueError("telemetry record exceeds configured quota")
        source = payload.get("source")
        command_id = payload.get("commandId")
        track_id = payload.get("trackId")
        connection.execute(
            """
            INSERT INTO records(sequence,event_id,timestamp_utc,monotonic_ns,
                                record_type,source,command_id,track_id,
                                record_json,record_sha256)
            VALUES(?,?,?,?,?,?,?,?,?,?)
            """,
            (
                sequence,
                event_id,
                timestamp,
                monotonic_ns,
                record_type,
                str(source) if source is not None else None,
                str(command_id) if command_id is not None else None,
                str(track_id) if track_id is not None else None,
                encoded,
                digest,
            ),
        )
        self._append_segment(connection, encoded + "\n")
        connection.commit()
        return record

    def _append_segment(self, connection: sqlite3.Connection, line: str) -> None:
        segments = sorted(self.session_dir.glob("events-*.jsonl"))
        incoming = len(line.encode())
        while segments and (
            sum(path.stat().st_size for path in segments if path.exists()) + incoming
            > self.max_bytes
        ):
            removed = segments.pop(0)
            self._issue(connection, "QUOTA_REMOVED_SEGMENT", removed.name)
            removed.unlink(missing_ok=True)
        current = segments[-1] if segments else self.session_dir / "events-000001.jsonl"
        if current.exists() and current.stat().st_size + incoming > self.segment_bytes:
            index = int(current.stem.split("-")[-1]) + 1
            current = self.session_dir / f"events-{index:06d}.jsonl"
        with current.open("a", encoding="utf-8") as handle:
            handle.write(line)
        self.path = current
        segments = sorted(self.session_dir.glob("events-*.jsonl"))
        while len(segments) > self.retention_segments:
            removed = segments.pop(0)
            self._issue(connection, "RETENTION_REMOVED_SEGMENT", removed.name)
            removed.unlink(missing_ok=True)

    def _write_media(
        self, connection: sqlite3.Connection, data: dict[str, Any]
    ) -> dict[str, Any]:
        media_id = f"MEDIA-{uuid.uuid4().hex.upper()}"
        connection.execute(
            "INSERT INTO media_index VALUES(?,?,?,?,?,?,?,?)",
            (
                media_id,
                data["kind"],
                data["path"],
                data["start"],
                data["end"],
                data["sha256"],
                int(data["exists"]),
                _canonical(data["metadata"]),
            ),
        )
        if not data["exists"]:
            self._issue(connection, "MISSING_MEDIA", data["path"])
        connection.commit()
        return {"mediaId": media_id, **data}

    def _issue(self, connection: sqlite3.Connection, code: str, detail: str) -> None:
        existing = connection.execute(
            "SELECT 1 FROM integrity_issues WHERE code=? AND detail=? AND resolved=0",
            (code, detail),
        ).fetchone()
        if existing is None:
            connection.execute(
                "INSERT INTO integrity_issues(code,detail,created_at_utc) VALUES(?,?,?)",
                (code, detail, self._clock()),
            )

    def _write_manifest(
        self, connection: sqlite3.Connection, *, finalized: bool
    ) -> None:
        files = self._source_snapshot
        for label, path in self.source_files.items():
            snapshot = files[label]
            if not snapshot["exists"]:
                self._issue(connection, "MISSING_SOURCE_FILE", f"{label}:{path}")
            elif finalized and (
                not path.exists() or sha256_file(path) != snapshot["sha256"]
            ):
                self._issue(connection, "SOURCE_FILE_CHANGED", f"{label}:{path}")
        packages: dict[str, str] = {}
        for package in ("gokkalkan", "python-can", "pyserial", "pytest"):
            try:
                packages[package] = importlib.metadata.version(package)
            except importlib.metadata.PackageNotFoundError:
                packages[package] = "NOT_INSTALLED"
        generated: list[dict[str, Any]] = []
        if finalized:
            connection.commit()
            connection.execute("PRAGMA wal_checkpoint(FULL)")
            for path in sorted(self.session_dir.glob("events-*.jsonl")):
                generated.append(
                    {"path": path.name, "sizeBytes": path.stat().st_size, "sha256": sha256_file(path)}
                )
            generated.append(
                {
                    "path": self.db_path.name,
                    "sizeBytes": self.db_path.stat().st_size,
                    "sha256": sha256_file(self.db_path),
                }
            )
        issue_rows = connection.execute(
            "SELECT code,detail FROM integrity_issues WHERE resolved=0 ORDER BY id"
        ).fetchall()
        manifest = {
            "schemaVersion": 1,
            "sessionId": self.session_id,
            "createdAtUtc": self.created_at,
            "finalizedAtUtc": self._clock() if finalized else None,
            "finalized": finalized,
            "evidenceValid": not issue_rows,
            "integrityIssues": [{"code": code, "detail": detail} for code, detail in issue_rows],
            "gitSha": self.git_sha,
            "buildId": self.build_id,
            "operatorId": self.operator_id,
            "environment": {
                "os": platform.platform(),
                "python": sys.version.split()[0],
                "executable": sys.executable,
                "packages": packages,
            },
            "sourceFiles": files,
            "generatedFiles": generated,
        }
        self.manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )


def verify_session(session_dir: str | Path) -> dict[str, Any]:
    root = Path(session_dir)
    manifest_path = root / "manifest.json"
    db_path = root / "events.sqlite3"
    errors: list[str] = []
    if not manifest_path.exists():
        errors.append("MISSING_MANIFEST")
        manifest: dict[str, Any] = {}
    else:
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            manifest = {}
            errors.append("INVALID_MANIFEST")
    if not db_path.exists():
        errors.append("MISSING_DATABASE")
        return {"ok": False, "errors": errors, "session": str(root)}
    if manifest and manifest.get("finalized") is not True:
        errors.append("SESSION_NOT_FINALIZED")
    try:
        with closing(sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)) as connection:
            integrity = str(connection.execute("PRAGMA integrity_check").fetchone()[0])
            if integrity != "ok":
                errors.append(f"SQLITE_INTEGRITY:{integrity}")
            rows = connection.execute(
                "SELECT sequence,record_json,record_sha256 FROM records ORDER BY sequence"
            ).fetchall()
            media_rows = connection.execute(
                "SELECT path,sha256,exists_on_index FROM media_index"
            ).fetchall()
    except (OSError, sqlite3.DatabaseError) as exc:
        errors.append(f"SQLITE_ERROR:{type(exc).__name__}")
        return {
            "ok": False,
            "errors": sorted(set(errors)),
            "session": str(root),
            "recordCount": 0,
            "eventOrderDigest": hashlib.sha256(b"").hexdigest(),
            "physicalAdapterLoaded": False,
        }
    expected = list(range(1, len(rows) + 1))
    if [row[0] for row in rows] != expected:
        errors.append("NON_CONTIGUOUS_SEQUENCE")
    physical = False
    for _sequence, encoded, expected_hash in rows:
        if hashlib.sha256(encoded.encode()).hexdigest() != expected_hash:
            errors.append("RECORD_HASH_MISMATCH")
            break
        try:
            record = json.loads(encoded)
        except (json.JSONDecodeError, TypeError):
            errors.append("INVALID_RECORD_JSON")
            continue
        payload = record.get("payload", {})
        if not isinstance(payload, dict):
            errors.append("INVALID_RECORD_PAYLOAD")
            continue
        if payload.get("physicalOutput") is True:
            physical = True
    if physical:
        errors.append("PHYSICAL_OUTPUT_IN_REPLAY_SOURCE")
    for media_path_value, expected_hash, existed in media_rows:
        media_path = Path(media_path_value)
        if (
            not existed
            or expected_hash is None
            or not _file_hash_matches(media_path, expected_hash)
        ):
            errors.append(f"MEDIA_HASH_MISMATCH:{media_path.name}")
    for entry in manifest.get("generatedFiles", []):
        path = root / str(entry.get("path", ""))
        try:
            path.relative_to(root)
        except ValueError:
            errors.append("INVALID_MANIFEST_PATH")
            continue
        if not _file_hash_matches(path, entry.get("sha256")):
            errors.append(f"FILE_HASH_MISMATCH:{path.name}")
    if manifest.get("evidenceValid") is False:
        errors.append("MANIFEST_MARKED_INVALID")
    digest = hashlib.sha256("".join(row[2] for row in rows).encode()).hexdigest()
    return {
        "ok": not errors,
        "errors": sorted(set(errors)),
        "session": str(root),
        "recordCount": len(rows),
        "eventOrderDigest": digest,
        "physicalAdapterLoaded": False,
    }


def replay_session(session_dir: str | Path) -> dict[str, Any]:
    """Replay is read-only and cannot construct any HardwareAdapter."""

    verification = verify_session(session_dir)
    root = Path(session_dir)
    if not verification["ok"] or not (root / "events.sqlite3").exists():
        return {
            **verification,
            "events": [],
            "decisionDigest": hashlib.sha256(b"[]").hexdigest(),
            "replayOnly": True,
            "physicalOutput": False,
        }
    with closing(sqlite3.connect(root / "events.sqlite3")) as connection:
        events = [
            json.loads(row[0])
            for row in connection.execute(
                "SELECT record_json FROM records ORDER BY sequence"
            )
        ]
    decision_digest = hashlib.sha256(
        _canonical(
            [
                {
                    "sequence": event["sequence"],
                    "recordType": event["recordType"],
                    "decision": event.get("payload", {}).get("decision"),
                    "reason": event.get("payload", {}).get("reason"),
                }
                for event in events
            ]
        ).encode()
    ).hexdigest()
    return {
        **verification,
        "events": events,
        "decisionDigest": decision_digest,
        "replayOnly": True,
        "physicalOutput": False,
    }


def build_evidence_package(
    session_dir: str | Path,
    output: str | Path,
    *,
    capability_id: str,
    start_monotonic_ns: int,
    end_monotonic_ns: int,
) -> dict[str, Any]:
    root = Path(session_dir)
    verification = verify_session(root)
    if not verification["ok"]:
        raise ValueError("invalid session cannot produce evidence package")
    with closing(sqlite3.connect(root / "events.sqlite3")) as connection:
        event_rows = connection.execute(
            """
            SELECT record_json FROM records
            WHERE monotonic_ns BETWEEN ? AND ? ORDER BY sequence
            """,
            (start_monotonic_ns, end_monotonic_ns),
        ).fetchall()
        media_rows = connection.execute(
            """
            SELECT media_id,kind,path,start_monotonic_ns,end_monotonic_ns,sha256
            FROM media_index
            WHERE end_monotonic_ns >= ? AND start_monotonic_ns <= ?
            ORDER BY start_monotonic_ns
            """,
            (start_monotonic_ns, end_monotonic_ns),
        ).fetchall()
    media_entries: list[dict[str, Any]] = []
    archive_media: list[tuple[Path, str]] = []
    for row in media_rows:
        media_path = Path(row[2])
        archive_path = f"media/{row[0]}-{media_path.name}"
        media_entries.append(
            {
                "mediaId": row[0],
                "kind": row[1],
                "path": row[2],
                "archivePath": archive_path,
                "startMonotonicNs": row[3],
                "endMonotonicNs": row[4],
                "sha256": row[5],
            }
        )
        archive_media.append((media_path, archive_path))
    evidence = {
        "schemaVersion": 1,
        "capabilityId": capability_id,
        "sessionId": root.name,
        "interval": {
            "startMonotonicNs": start_monotonic_ns,
            "endMonotonicNs": end_monotonic_ns,
        },
        "events": [json.loads(row[0]) for row in event_rows],
        "media": media_entries,
        "sessionEventOrderDigest": verification["eventOrderDigest"],
        "physicalOutput": False,
    }
    destination = Path(output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    evidence_bytes = (
        json.dumps(evidence, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode()
    manifest_bytes = (root / "manifest.json").read_bytes()
    hashes = {
        "manifest.json": hashlib.sha256(manifest_bytes).hexdigest(),
        "evidence.json": hashlib.sha256(evidence_bytes).hexdigest(),
    }
    for media_path, archive_path in archive_media:
        hashes[archive_path] = sha256_file(media_path)
    hash_manifest = (
        json.dumps(
            {"schemaVersion": 1, "sha256": hashes},
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode()
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("manifest.json", manifest_bytes)
        archive.writestr("evidence.json", evidence_bytes)
        archive.writestr("hash-manifest.json", hash_manifest)
        for media_path, archive_path in archive_media:
            archive.write(media_path, archive_path)
    return {
        "ok": True,
        "path": str(destination),
        "sha256": sha256_file(destination),
        "eventCount": len(evidence["events"]),
        "mediaCount": len(evidence["media"]),
    }


def verify_evidence(path: str | Path) -> dict[str, Any]:
    source = Path(path)
    errors: list[str] = []
    if not source.exists() or not zipfile.is_zipfile(source):
        return {"ok": False, "errors": ["INVALID_EVIDENCE_ARCHIVE"], "path": str(source)}
    with zipfile.ZipFile(source) as archive:
        names = set(archive.namelist())
        if {"manifest.json", "evidence.json", "hash-manifest.json"} - names:
            errors.append("MISSING_EVIDENCE_MEMBER")
            evidence = {}
            manifest = {}
            hashes = {}
        else:
            try:
                evidence = json.loads(archive.read("evidence.json"))
                manifest = json.loads(archive.read("manifest.json"))
                hashes = json.loads(archive.read("hash-manifest.json")).get(
                    "sha256", {}
                )
            except (json.JSONDecodeError, UnicodeDecodeError):
                errors.append("INVALID_EVIDENCE_JSON")
                evidence = {}
                manifest = {}
                hashes = {}
        if not isinstance(hashes, dict):
            errors.append("INVALID_HASH_MANIFEST")
            hashes = {}
        for member, expected_hash in hashes.items():
            if member not in names:
                errors.append(f"MISSING_HASHED_MEMBER:{member}")
            elif hashlib.sha256(archive.read(member)).hexdigest() != expected_hash:
                errors.append(f"EVIDENCE_HASH_MISMATCH:{member}")
        expected_media = {
            item.get("archivePath") for item in evidence.get("media", [])
        }
        if None in expected_media or not expected_media.issubset(names):
            errors.append("MISSING_EVIDENCE_MEDIA")
    if evidence.get("physicalOutput") is not False:
        errors.append("UNSAFE_EVIDENCE_OUTPUT_FLAG")
    if manifest.get("evidenceValid") is not True:
        errors.append("SOURCE_SESSION_INVALID")
    return {
        "ok": not errors,
        "errors": errors,
        "path": str(source),
        "sha256": sha256_file(source),
        "capabilityId": evidence.get("capabilityId"),
    }
