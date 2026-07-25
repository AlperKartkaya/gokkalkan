"""Single-owner Mission Core with deterministic command/event ordering."""

from __future__ import annotations

import copy
import json
import queue
import threading
import time
import uuid
from concurrent.futures import Future, TimeoutError as FutureTimeout
from dataclasses import dataclass
from typing import Any, Mapping

from .messages import (
    CommandEnvelope,
    EventEnvelope,
    MessageContractError,
    deep_freeze,
    deep_thaw,
    utc_now,
)
from .operator_api import OperatorService


class MissionCoreError(RuntimeError):
    """Base Mission Core error."""


class MissionCoreStopped(MissionCoreError):
    """Raised when a command arrives after the stop boundary."""


class MissionQueueFull(MissionCoreError):
    """Raised when backpressure prevents deterministic enqueue."""


class MissionCommandTimeout(MissionCoreError):
    """Raised when a queued command has not completed before the caller timeout."""

    def __init__(self, command_id: str) -> None:
        super().__init__(f"command is still queued or running: {command_id}")
        self.command_id = command_id


@dataclass(frozen=True, slots=True)
class MissionState:
    schema_version: int
    run_id: str
    version: int
    last_event_sequence: int
    mode: str
    stage: int
    round: int
    selected_target_id: str | None
    armed: bool
    maintenance_active: bool
    estop_active: bool
    perception_healthy: bool
    faults: tuple[str, ...]
    lifecycle: str
    updated_at_utc: str
    updated_at_monotonic_ns: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "schemaVersion": self.schema_version,
            "runId": self.run_id,
            "version": self.version,
            "lastEventSequence": self.last_event_sequence,
            "mode": self.mode,
            "stage": self.stage,
            "round": self.round,
            "selectedTargetId": self.selected_target_id,
            "armed": self.armed,
            "maintenanceActive": self.maintenance_active,
            "estopActive": self.estop_active,
            "perceptionHealthy": self.perception_healthy,
            "faults": list(self.faults),
            "lifecycle": self.lifecycle,
            "updatedAtUtc": self.updated_at_utc,
            "updatedAtMonotonicNs": self.updated_at_monotonic_ns,
        }


class MissionCore:
    """Own every production state mutation on one reducer thread.

    HTTP workers, CAN receive threads and perception clients only enqueue
    versioned envelopes. A frozen snapshot is published after each reduction.
    """

    _STOP_PRIORITY = 100
    _SAFETY_PRIORITY = 0
    _DEFAULT_PRIORITY = 10

    def __init__(
        self,
        service: OperatorService,
        *,
        queue_capacity: int = 512,
        command_timeout_sec: float = 2.0,
        perception_timeout_sec: float = 2.0,
        snapshot_interval_sec: float = 1.0,
        run_id: str | None = None,
    ) -> None:
        if queue_capacity < 8:
            raise ValueError("queue_capacity must be at least 8")
        self.service = service
        self.run_id = run_id or uuid.uuid4().hex.upper()
        self.command_timeout_sec = command_timeout_sec
        self.perception_timeout_sec = perception_timeout_sec
        self.snapshot_interval_sec = max(0.05, snapshot_interval_sec)
        self._queue: queue.PriorityQueue[
            tuple[int, int, CommandEnvelope | None, Future[dict[str, Any]] | None]
        ] = queue.PriorityQueue(maxsize=queue_capacity)
        self._lock = threading.RLock()
        self._snapshot_condition = threading.Condition(self._lock)
        self._thread: threading.Thread | None = None
        self._started_event = threading.Event()
        self._accepting = False
        self._lifecycle = "CREATED"
        self._command_sequence = 0
        self._event_sequence = 0
        self._state_version = 0
        self._source_sequences: dict[str, int] = {}
        self._command_futures: dict[str, Future[dict[str, Any]]] = {}
        self._command_signatures: dict[str, str] = {}
        self._core_events: list[EventEnvelope] = []
        self._faults: set[str] = set()
        self._selected_target_id: str | None = None
        self._last_perception_heartbeat_ns: int | None = None
        self._perception_was_healthy = False
        self._mission_state: MissionState | None = None
        self._snapshot: Mapping[str, Any] = deep_freeze({})
        self._last_snapshot_publish_ns = 0
        self._publish_snapshot()

    @property
    def is_running(self) -> bool:
        with self._lock:
            return self._lifecycle == "RUNNING"

    def start(self) -> None:
        with self._lock:
            if self._lifecycle == "RUNNING":
                return
            if self._lifecycle not in {"CREATED"}:
                raise MissionCoreStopped(
                    f"Mission Core cannot restart from {self._lifecycle}"
                )
            self._accepting = True
            self._lifecycle = "RUNNING"
            self._thread = threading.Thread(
                target=self._run,
                daemon=True,
                name="MissionCore",
            )
            self._thread.start()
        if not self._started_event.wait(timeout=2.0):
            raise MissionCoreError("Mission Core owner thread did not start")
        self._bind_external_event_sources()

    def stop(self, timeout: float = 5.0) -> None:
        with self._lock:
            if self._lifecycle in {"STOPPED", "CREATED"}:
                self._accepting = False
                self._lifecycle = "STOPPED"
                self._publish_snapshot()
                return
            if self._lifecycle == "STOPPING":
                thread = self._thread
            else:
                self._accepting = False
                self._lifecycle = "STOPPING"
                self._queue.put(
                    (self._STOP_PRIORITY, self._next_command_sequence(), None, None)
                )
                thread = self._thread
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=timeout)
            if thread.is_alive():
                raise MissionCoreError("Mission Core did not stop within timeout")

    def submit(
        self,
        kind: str,
        payload: Mapping[str, Any] | None = None,
        *,
        source: str = "operator-http",
        command_id: str | None = None,
        causation_id: str | None = None,
        source_sequence: int | None = None,
        schema_version: int = 1,
        timeout: float | None = None,
        wait: bool = True,
    ) -> dict[str, Any] | str:
        with self._lock:
            if not self._accepting:
                raise MissionCoreStopped(
                    f"Mission Core is not accepting commands ({self._lifecycle})"
                )
            body = dict(payload or {})
            signature = json.dumps(
                {"kind": kind, "source": source, "payload": body},
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            if command_id and command_id in self._command_futures:
                if self._command_signatures[command_id] != signature:
                    raise MessageContractError(
                        "command_id was reused with different content"
                    )
                existing = self._command_futures[command_id]
                duplicate = True
            else:
                sequence = self._next_command_sequence()
                target_id = _optional_id(body.get("targetId"))
                track_id = _optional_id(body.get("trackId")) or target_id
                envelope = CommandEnvelope.create(
                    run_id=self.run_id,
                    sequence=sequence,
                    source=source,
                    kind=kind,
                    payload=body,
                    command_id=command_id,
                    causation_id=causation_id,
                    target_id=target_id,
                    track_id=track_id,
                    source_sequence=source_sequence,
                    schema_version=schema_version,
                )
                existing = Future()
                self._command_futures[envelope.command_id] = existing
                self._command_signatures[envelope.command_id] = signature
                priority = (
                    self._SAFETY_PRIORITY
                    if kind == "EStopChange"
                    else self._DEFAULT_PRIORITY
                )
                try:
                    self._queue.put_nowait(
                        (priority, sequence, envelope, existing)
                    )
                except queue.Full as exc:
                    self._command_futures.pop(envelope.command_id, None)
                    self._command_signatures.pop(envelope.command_id, None)
                    raise MissionQueueFull("Mission Core command queue is full") from exc
                command_id = envelope.command_id
                duplicate = False

        assert command_id is not None
        if not wait:
            return command_id
        try:
            result = existing.result(
                timeout=self.command_timeout_sec if timeout is None else timeout
            )
        except FutureTimeout as exc:
            raise MissionCommandTimeout(command_id) from exc
        detached = copy.deepcopy(result)
        detached["deduplicated"] = duplicate
        return detached

    def publish_threadsafe(
        self,
        kind: str,
        payload: Mapping[str, Any],
        *,
        source: str,
        source_sequence: int | None = None,
        causation_id: str | None = None,
    ) -> str:
        """Thread-safe queue bridge used by CAN/GPIO/sensor callbacks."""

        command_id = self.submit(
            kind,
            payload,
            source=source,
            source_sequence=source_sequence,
            causation_id=causation_id,
            wait=False,
        )
        assert isinstance(command_id, str)
        return command_id

    def command_status(self, command_id: str) -> dict[str, Any] | None:
        with self._lock:
            future = self._command_futures.get(command_id)
        if future is None:
            return None
        if not future.done():
            return {
                "commandId": command_id,
                "completed": False,
                "lifecycle": self._lifecycle,
            }
        result = copy.deepcopy(future.result())
        result["deduplicated"] = False
        return result

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return deep_thaw(self._snapshot)

    @property
    def state(self) -> MissionState:
        with self._lock:
            assert self._mission_state is not None
            return self._mission_state

    def wait_for_snapshot(
        self,
        after_version: int,
        *,
        timeout: float = 10.0,
    ) -> dict[str, Any]:
        with self._snapshot_condition:
            current = _snapshot_version(self._snapshot)
            if current <= after_version and self._lifecycle != "STOPPED":
                self._snapshot_condition.wait_for(
                    lambda: _snapshot_version(self._snapshot) > after_version
                    or self._lifecycle == "STOPPED",
                    timeout=timeout,
                )
            return deep_thaw(self._snapshot)

    def health(self) -> dict[str, Any]:
        snapshot = self.snapshot()
        core = snapshot["missionCore"]
        return {
            "ok": core["lifecycle"] == "RUNNING",
            "service": "gokkalkan-mission-core",
            "runId": self.run_id,
            "lifecycle": core["lifecycle"],
            "stateVersion": core["version"],
            "lastEventSequence": core["lastEventSequence"],
            "queueDepth": self._queue.qsize(),
            "queueCapacity": self._queue.maxsize,
            "physicalOutputEnabled": snapshot.get(
                "physicalOutputEnabled", False
            ),
            "runtimeMode": snapshot.get("runtimeMode"),
        }

    def _run(self) -> None:
        self.service.bind_owner_thread(threading.get_ident())
        self._publish_snapshot()
        self._started_event.set()
        try:
            while True:
                try:
                    _priority, _ingress, envelope, future = self._queue.get(
                        timeout=0.05
                    )
                except queue.Empty:
                    self.service.refresh_hardware_health()
                    self._check_perception_timeout()
                    self._publish_timed_snapshot_if_needed()
                    continue
                try:
                    if envelope is None:
                        break
                    outcome = self._process_envelope(envelope)
                    if future is not None and not future.done():
                        future.set_result(outcome)
                except Exception as exc:  # keep the reducer alive and fail closed
                    self._faults.add(f"CORE_REDUCER_ERROR:{type(exc).__name__}")
                    failure = {
                        "commandId": envelope.command_id if envelope else None,
                        "completed": True,
                        "accepted": False,
                        "error": "CORE_REDUCER_ERROR",
                        "detail": str(exc),
                        "physicalOutput": False,
                    }
                    if future is not None and not future.done():
                        future.set_result(failure)
                    self._publish_snapshot()
                finally:
                    self._queue.task_done()
                self.service.refresh_hardware_health()
                self._check_perception_timeout()
        finally:
            with self._lock:
                self._lifecycle = "STOPPED"
                self._accepting = False
                self._publish_snapshot()

    def _process_envelope(self, envelope: CommandEnvelope) -> dict[str, Any]:
        out_of_order = False
        if envelope.source_sequence is not None:
            last = self._source_sequences.get(envelope.source, 0)
            if envelope.source_sequence <= last:
                out_of_order = True
                domain: dict[str, Any] = {
                    "ok": False,
                    "accepted": False,
                    "error": "OUT_OF_ORDER_SOURCE_SEQUENCE",
                    "source": envelope.source,
                    "sourceSequence": envelope.source_sequence,
                    "lastAcceptedSourceSequence": last,
                    "physicalOutput": False,
                }
            else:
                self._source_sequences[envelope.source] = envelope.source_sequence
        if not out_of_order:
            try:
                domain = self._dispatch(envelope)
            except MessageContractError as exc:
                domain = {
                    "ok": False,
                    "accepted": False,
                    "error": "UNSUPPORTED_COMMAND",
                    "detail": str(exc),
                    "physicalOutput": False,
                }

        accepted = _domain_accepted(domain)
        event_domain = {
            key: value for key, value in domain.items() if key != "state"
        }
        self._event_sequence += 1
        event = EventEnvelope.create(
            run_id=self.run_id,
            sequence=self._event_sequence,
            source="mission-core",
            event_type="command.completed" if accepted else "command.rejected",
            payload={
                "kind": envelope.kind,
                "accepted": accepted,
                "domain": event_domain,
                "physicalOutput": False,
            },
            command_id=envelope.command_id,
            causation_id=envelope.causation_id or envelope.command_id,
            target_id=envelope.target_id,
            track_id=envelope.track_id,
        )
        self._core_events.insert(0, event)
        self._core_events = self._core_events[:200]
        self.service.telemetry.append("core_event", event.to_dict())
        self._publish_snapshot()
        response_domain = copy.deepcopy(domain)
        if "state" in response_domain:
            response_domain["state"] = self.snapshot()
        return {
            "schemaVersion": 1,
            "runId": self.run_id,
            "commandId": envelope.command_id,
            "eventId": event.event_id,
            "sequence": event.sequence,
            "queued": True,
            "completed": True,
            "accepted": accepted,
            "deduplicated": False,
            "command": envelope.to_dict(),
            "event": event.to_dict(),
            "domain": response_domain,
            **response_domain,
            "physicalOutput": False,
        }

    def _dispatch(self, envelope: CommandEnvelope) -> dict[str, Any]:
        payload = deep_thaw(envelope.payload)
        self.service.set_command_context(envelope.command_id)
        try:
            if envelope.kind == "ModeRequest":
                return self.service.handle_mode_request(payload)
            if envelope.kind == "StageRequest":
                return self.service.handle_stage_request(payload)
            if envelope.kind == "ManualAimCommand":
                return self.service.handle_manual_aim(payload)
            if envelope.kind == "FireIntent":
                return self.service.handle_fire_intent(payload)
            if envelope.kind == "MaintenanceStart":
                return self.service.handle_maintenance_request(payload)
            if envelope.kind == "MaintenanceEnd":
                return self.service.maintenance_end()
            if envelope.kind == "MissionStop":
                return self.service.handle_mission_stop(payload)
            if envelope.kind == "MissionResume":
                return self.service.handle_mission_resume(payload)
            if envelope.kind == "TelemetryReset":
                return self.service.reset_telemetry()
            if envelope.kind == "TracksUpdate":
                self._mark_perception_heartbeat()
                return self.service.update_tracks(
                    payload.get("tracks", []),
                    str(payload.get("source", envelope.source)),
                )
            if envelope.kind == "EStopChange":
                active = bool(payload.get("active", True))
                self.service.set_estop(
                    active,
                    physical=envelope.source != "operator-estop-http",
                )
                return {
                    "ok": True,
                    "estop": active,
                    "safety": self.service.evaluate_safety(
                        "ModeRequest"
                    ).to_dict(),
                    "state": self.service.snapshot(),
                    "physicalOutput": False,
                }
            if envelope.kind == "EStopReset":
                return self.service.reset_estop(str(payload.get("operatorId", "")))
            if envelope.kind == "ArmHold":
                return self.service.arm_hold(
                    bool(payload.get("holding", False)),
                    str(payload.get("operatorId", "")),
                )
            if envelope.kind == "Disarm":
                return self.service.disarm(str(payload.get("reason", "OPERATOR_DISARM")))
            if envelope.kind == "SafetyHealthUpdate":
                if not envelope.source.startswith(("can-", "runtime-", "mission-core")):
                    raise MessageContractError("safety health updates require a trusted source")
                return self.service.update_safety_health(payload)
            if envelope.kind == "PerceptionHealth":
                healthy = bool(payload.get("healthy", False))
                if healthy:
                    self._mark_perception_heartbeat()
                else:
                    self._last_perception_heartbeat_ns = None
                    self._perception_was_healthy = False
                    self._faults.add("PERCEPTION_UNHEALTHY")
                return self.service.set_perception_health(
                    healthy,
                    reason=str(payload.get("reason", "heartbeat")),
                )
        finally:
            self.service.set_command_context(None)
        raise MessageContractError(f"unsupported command kind: {envelope.kind}")

    def _mark_perception_heartbeat(self) -> None:
        self._last_perception_heartbeat_ns = time.monotonic_ns()
        self._perception_was_healthy = True
        self._faults.discard("PERCEPTION_UNHEALTHY")
        self.service.set_perception_health(True, reason="heartbeat")

    def _check_perception_timeout(self) -> None:
        last = self._last_perception_heartbeat_ns
        if not self._perception_was_healthy or last is None:
            return
        elapsed = (time.monotonic_ns() - last) / 1_000_000_000
        if elapsed <= self.perception_timeout_sec:
            return
        self._perception_was_healthy = False
        self._last_perception_heartbeat_ns = None
        envelope = CommandEnvelope.create(
            run_id=self.run_id,
            sequence=self._next_command_sequence(),
            source="mission-core-watchdog",
            kind="PerceptionHealth",
            payload={"healthy": False, "reason": "heartbeat_timeout"},
            causation_id="perception-heartbeat-watchdog",
        )
        self._process_envelope(envelope)

    def _publish_snapshot(self) -> None:
        with self._snapshot_condition:
            self._state_version += 1
            domain = self.service.snapshot()
            safety = domain.get("safety", {})
            mission_state = MissionState(
                schema_version=1,
                run_id=self.run_id,
                version=self._state_version,
                last_event_sequence=self._event_sequence,
                mode=str(domain.get("mode", "safe")),
                stage=int(domain.get("stage", 3)),
                round=int(domain.get("round", 1)),
                selected_target_id=domain.get("missionFlow", {}).get(
                    "selectedTargetId"
                ),
                armed=bool(domain.get("liveArmEnabled", False)),
                maintenance_active=domain.get("mode") == "maintenance",
                estop_active=bool(safety.get("estop", False)),
                perception_healthy=bool(
                    domain.get("sensorHealth", {}).get(
                        "perceptionConnected", False
                    )
                ),
                faults=tuple(sorted(self._faults)),
                lifecycle=self._lifecycle,
                updated_at_utc=utc_now(),
                updated_at_monotonic_ns=time.monotonic_ns(),
            )
            self._mission_state = mission_state
            published = {
                **domain,
                "snapshotVersion": mission_state.version,
                "missionCore": mission_state.to_dict(),
                "coreEvents": [
                    event.to_dict() for event in self._core_events[:50]
                ],
            }
            self._snapshot = deep_freeze(published)
            self._last_snapshot_publish_ns = time.monotonic_ns()
            self._snapshot_condition.notify_all()

    def _publish_timed_snapshot_if_needed(self) -> None:
        elapsed = (
            time.monotonic_ns() - self._last_snapshot_publish_ns
        ) / 1_000_000_000
        if elapsed >= self.snapshot_interval_sec:
            self.service.expire_stage_timer_if_needed()
            self._publish_snapshot()

    def _next_command_sequence(self) -> int:
        with self._lock:
            self._command_sequence += 1
            return self._command_sequence

    def _bind_external_event_sources(self) -> None:
        setter = getattr(self.service.hardware, "set_estop_callback", None)
        if callable(setter):
            setter(
                lambda active: self.publish_threadsafe(
                    "EStopChange",
                    {"active": bool(active)},
                    source="can-estop",
                )
            )


def _optional_id(value: Any) -> str | None:
    text = str(value).strip() if value is not None else ""
    return text or None


def _domain_accepted(domain: Mapping[str, Any]) -> bool:
    result = domain.get("result")
    if isinstance(result, Mapping) and "accepted" in result:
        return bool(result["accepted"])
    if "accepted" in domain:
        return bool(domain["accepted"])
    if "ok" in domain:
        return bool(domain["ok"])
    return True


def _snapshot_version(snapshot: Mapping[str, Any]) -> int:
    value = snapshot.get("snapshotVersion", 0)
    return int(value) if isinstance(value, int) else 0
