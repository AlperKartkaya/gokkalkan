"""Detector contracts and bounded latest-wins inference execution."""

from __future__ import annotations

from dataclasses import dataclass
import queue
import threading
import time
from typing import Any, Protocol


@dataclass(frozen=True, slots=True)
class Detection:
    label: str
    confidence: float
    bbox_xyxy: tuple[float, float, float, float]


class Detector(Protocol):
    def detect(self, frame: Any) -> list[Detection]: ...
    def health(self) -> dict[str, Any]: ...


class LatestWinsDetector:
    """Keep camera capture non-blocking while inference owns one worker."""

    def __init__(self, detector: Detector, *, stale_ms: float = 300.0) -> None:
        self.detector = detector
        self.stale_ns = int(stale_ms * 1_000_000)
        self._queue: queue.Queue[tuple[Any, int] | None] = queue.Queue(maxsize=1)
        self._lock = threading.Lock()
        self._result: tuple[list[Detection], int] | None = None
        self._running = False
        self._thread: threading.Thread | None = None
        self._dropped = 0
        self._last_error: str | None = None

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True, name="DetectorInference")
        self._thread.start()

    def stop(self) -> None:
        self._running = False
        self.submit_stop()
        if self._thread:
            self._thread.join(timeout=2.0)

    def submit(self, frame: Any, receive_monotonic_ns: int) -> None:
        item = (frame, receive_monotonic_ns)
        try:
            self._queue.put_nowait(item)
        except queue.Full:
            try:
                self._queue.get_nowait()
                self._queue.task_done()
                self._dropped += 1
            except queue.Empty:
                pass
            self._queue.put_nowait(item)

    def latest(self, *, now_monotonic_ns: int | None = None) -> list[Detection]:
        now = time.monotonic_ns() if now_monotonic_ns is None else now_monotonic_ns
        with self._lock:
            result = self._result
        if result is None or now - result[1] > self.stale_ns:
            return []
        return list(result[0])

    def health(self) -> dict[str, Any]:
        with self._lock:
            result = self._result
        return {
            **self.detector.health(),
            "workerRunning": self._running,
            "resultAvailable": result is not None,
            "droppedFrames": self._dropped,
            "lastError": self._last_error,
        }

    def submit_stop(self) -> None:
        try:
            self._queue.put_nowait(None)
        except queue.Full:
            try:
                self._queue.get_nowait()
                self._queue.task_done()
            except queue.Empty:
                pass
            self._queue.put_nowait(None)

    def _run(self) -> None:
        while self._running:
            item = self._queue.get()
            try:
                if item is None:
                    return
                frame, timestamp = item
                detections = self.detector.detect(frame)
                with self._lock:
                    self._result = (detections, timestamp)
                self._last_error = None
            except Exception as exc:
                self._last_error = f"{type(exc).__name__}:{exc}"
                with self._lock:
                    self._result = None
            finally:
                self._queue.task_done()
