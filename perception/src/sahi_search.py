"""Latest-wins SAHI search and square-ROI tracking over the main camera frame."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from pathlib import Path
import queue
import threading
import time
import tomllib
from typing import Any, Protocol, Sequence

from detector import Detection
from roi_geometry import square_roi_from_source_center
from sahi_geometry import (
    SliceWindow,
    generate_slice_windows,
    greedy_nmm,
    iou,
    mark_class_ambiguities,
)


class BatchDetector(Protocol):
    model_size: tuple[int, int]

    def detect_batch(self, tiles: Sequence[Any]) -> list[list[Detection]]: ...
    def health(self) -> dict[str, Any]: ...


@dataclass(frozen=True, slots=True)
class SahiSearchConfig:
    main_size: tuple[int, int]
    model_size: tuple[int, int]
    slice_size: tuple[int, int]
    overlap: tuple[float, float]
    batch_size: int
    target_sweeps_per_second: float
    minimum_sweeps_per_second: float
    stale_after_ms: float
    postprocess_type: str
    match_metric: str
    match_threshold: float
    class_agnostic: bool
    ambiguity_ios_threshold: float
    history_sweeps: int
    required_hits: int
    spatial_iou_threshold: float
    normal_roi_size_px: int
    first_recovery_roi_size_px: int
    second_recovery_roi_size_px: int
    return_to_search_after_misses: int
    minimum_confidence: float

    @classmethod
    def from_toml(cls, path: str | Path) -> "SahiSearchConfig":
        data = tomllib.loads(Path(path).read_text(encoding="utf-8"))
        if data.get("schema_version") != 1:
            raise ValueError("unsupported perception search schema_version")
        search = data["search"]
        post = data["postprocess"]
        temporal = data["temporal"]
        track = data["track"]
        config = cls(
            main_size=(int(search["main_width"]), int(search["main_height"])),
            model_size=(int(search["model_width"]), int(search["model_height"])),
            slice_size=(int(search["slice_width"]), int(search["slice_height"])),
            overlap=(
                float(search["overlap_width_ratio"]),
                float(search["overlap_height_ratio"]),
            ),
            batch_size=int(search["batch_size"]),
            target_sweeps_per_second=float(search["target_sweeps_per_second"]),
            minimum_sweeps_per_second=float(search["minimum_sweeps_per_second"]),
            stale_after_ms=float(search["stale_after_ms"]),
            postprocess_type=str(post["type"]).upper(),
            match_metric=str(post["match_metric"]).upper(),
            match_threshold=float(post["match_threshold"]),
            class_agnostic=bool(post["class_agnostic"]),
            ambiguity_ios_threshold=float(post["ambiguity_ios_threshold"]),
            history_sweeps=int(temporal["history_sweeps"]),
            required_hits=int(temporal["required_hits"]),
            spatial_iou_threshold=float(temporal["spatial_iou_threshold"]),
            normal_roi_size_px=int(track["normal_roi_size_px"]),
            first_recovery_roi_size_px=int(track["first_recovery_roi_size_px"]),
            second_recovery_roi_size_px=int(track["second_recovery_roi_size_px"]),
            return_to_search_after_misses=int(track["return_to_search_after_misses"]),
            minimum_confidence=float(track["minimum_confidence"]),
        )
        config.validate()
        return config

    def validate(self) -> None:
        if min(*self.main_size, *self.model_size, *self.slice_size, self.batch_size) <= 0:
            raise ValueError("search dimensions and batch size must be positive")
        if self.postprocess_type != "GREEDYNMM":
            raise ValueError("only GREEDYNMM is supported by the runtime contract")
        if self.match_metric not in {"IOS", "IOU"}:
            raise ValueError("match metric must be IOS or IOU")
        if not 1 <= self.required_hits <= self.history_sweeps:
            raise ValueError("required_hits must fit inside history_sweeps")
        roi_sizes = (
            self.normal_roi_size_px,
            self.first_recovery_roi_size_px,
            self.second_recovery_roi_size_px,
        )
        if sorted(roi_sizes) != list(roi_sizes) or min(roi_sizes) < max(self.model_size):
            raise ValueError("track ROI sizes must be increasing and never upsample")
        if self.return_to_search_after_misses < 3:
            raise ValueError("track recovery requires at least three misses")
        if not 0.0 <= self.minimum_confidence <= 1.0:
            raise ValueError("minimum_confidence must be within 0..1")

    def windows(self) -> list[SliceWindow]:
        return generate_slice_windows(
            image_width=self.main_size[0],
            image_height=self.main_size[1],
            slice_width=self.slice_size[0],
            slice_height=self.slice_size[1],
            overlap_width_ratio=self.overlap[0],
            overlap_height_ratio=self.overlap[1],
        )


@dataclass(frozen=True, slots=True)
class SearchSweep:
    sweep_id: int
    source_timestamp_ns: int
    completed_monotonic_ns: int
    detections: tuple[Detection, ...]
    confirmed_detections: tuple[Detection, ...]
    tile_count: int
    latency_ms: float
    mode: str = "SEARCH_SAHI_SWEEP"
    roi_rect_full_frame_px: tuple[int, int, int, int] | None = None


class TemporalDetectionConfirmer:
    def __init__(self, *, history_sweeps: int, required_hits: int, iou_threshold: float) -> None:
        self.history: deque[list[Detection]] = deque(maxlen=history_sweeps)
        self.required_hits = required_hits
        self.iou_threshold = iou_threshold

    def update(self, detections: Sequence[Detection]) -> list[Detection]:
        current = list(detections)
        self.history.append(current)
        confirmed: list[Detection] = []
        for detection in current:
            hits = sum(
                any(
                    candidate.label == detection.label
                    and iou(candidate.bbox_xyxy, detection.bbox_xyxy) >= self.iou_threshold
                    for candidate in sweep
                )
                for sweep in self.history
            )
            if hits >= self.required_hits:
                confirmed.append(detection)
        return confirmed

    def reset(self) -> None:
        self.history.clear()


class SahiSearchEngine:
    input_stream = "sahi-main"

    def __init__(self, detector: BatchDetector, config: SahiSearchConfig) -> None:
        if detector.model_size != config.model_size:
            raise ValueError("detector and search model sizes must match")
        self.detector = detector
        self.config = config
        self.windows = config.windows()
        self._sweep_id = 0
        self._confirmer = TemporalDetectionConfirmer(
            history_sweeps=config.history_sweeps,
            required_hits=config.required_hits,
            iou_threshold=config.spatial_iou_threshold,
        )
        self._active_detection: Detection | None = None
        self._track_misses = 0
        self._next_roi_size_px = config.normal_roi_size_px

    @property
    def mode(self) -> str:
        return "SEARCH_SAHI_SWEEP" if self._active_detection is None else "TRACK_SQUARE_ROI"

    def run_frame(self, frame: Any, source_timestamp_ns: int) -> SearchSweep:
        if self._active_detection is None:
            return self.run_sweep(frame, source_timestamp_ns)
        return self._run_track(frame, source_timestamp_ns)

    def run_sweep(self, frame: Any, source_timestamp_ns: int) -> SearchSweep:
        self._validate_frame(frame)
        started = time.monotonic_ns()
        all_detections: list[Detection] = []
        for offset in range(0, len(self.windows), self.config.batch_size):
            batch_windows = self.windows[offset : offset + self.config.batch_size]
            tiles = [
                frame[window.top : window.bottom, window.left : window.right]
                for window in batch_windows
            ]
            batch_predictions = self.detector.detect_batch(tiles)
            if len(batch_predictions) != len(batch_windows):
                raise ValueError("detector result count does not match tile count")
            for window, predictions in zip(batch_windows, batch_predictions, strict=True):
                all_detections.extend(self._to_full_frame(window, predictions))

        safe = self._postprocess(all_detections)
        confirmed = self._confirmer.update(safe)
        track_candidate = max(
            (item for item in confirmed if item.label != "AMBIGUOUS_CLASS"),
            key=lambda item: item.confidence,
            default=None,
        )
        if track_candidate is not None:
            self._active_detection = track_candidate
            self._track_misses = 0
            self._next_roi_size_px = self.config.normal_roi_size_px
        return self._result(
            started=started,
            source_timestamp_ns=source_timestamp_ns,
            detections=safe,
            confirmed=confirmed,
            tile_count=len(self.windows),
            mode="SEARCH_SAHI_SWEEP",
        )

    def _run_track(self, frame: Any, source_timestamp_ns: int) -> SearchSweep:
        self._validate_frame(frame)
        active = self._active_detection
        if active is None:  # pragma: no cover - guarded by run_frame
            return self.run_sweep(frame, source_timestamp_ns)
        started = time.monotonic_ns()
        x1, y1, x2, y2 = active.bbox_xyxy
        roi = square_roi_from_source_center(
            ((x1 + x2) / 2, (y1 + y2) / 2),
            roi_size_px=self._next_roi_size_px,
            source_size=self.config.main_size,
        )
        tile = frame[roi.top : roi.top + roi.height, roi.left : roi.left + roi.width]
        batches = self.detector.detect_batch([tile])
        if len(batches) != 1:
            raise ValueError("track detector must return exactly one result group")
        mapped = self._to_full_frame(
            SliceWindow(roi.left, roi.top, roi.left + roi.width, roi.top + roi.height),
            batches[0],
        )
        safe = self._postprocess(mapped)
        ambiguous = [item for item in safe if item.label == "AMBIGUOUS_CLASS"]
        candidate = max(
            (item for item in safe if item.label == active.label),
            key=lambda item: item.confidence,
            default=None,
        )

        if candidate is not None:
            self._active_detection = candidate
            self._track_misses = 0
            bbox_width = candidate.bbox_xyxy[2] - candidate.bbox_xyxy[0]
            bbox_height = candidate.bbox_xyxy[3] - candidate.bbox_xyxy[1]
            self._next_roi_size_px = (
                self.config.first_recovery_roi_size_px
                if max(bbox_width, bbox_height) > self.config.normal_roi_size_px * 0.5
                else self.config.normal_roi_size_px
            )
            confirmed = ambiguous or [candidate]
        else:
            self._track_misses += 1
            confirmed = ambiguous
            if self._track_misses == 1:
                self._next_roi_size_px = self.config.first_recovery_roi_size_px
            elif self._track_misses == 2:
                self._next_roi_size_px = self.config.second_recovery_roi_size_px
            elif self._track_misses >= self.config.return_to_search_after_misses:
                self._reset_track()
                return self.run_sweep(frame, source_timestamp_ns)

        return self._result(
            started=started,
            source_timestamp_ns=source_timestamp_ns,
            detections=safe,
            confirmed=confirmed,
            tile_count=1,
            mode="TRACK_SQUARE_ROI",
            roi_rect=roi.as_tuple(),
        )

    def _postprocess(self, detections: Sequence[Detection]) -> list[Detection]:
        return mark_class_ambiguities(
            greedy_nmm(
                detections,
                match_threshold=self.config.match_threshold,
                match_metric=self.config.match_metric,
                class_agnostic=self.config.class_agnostic,
            ),
            ios_threshold=self.config.ambiguity_ios_threshold,
        )

    def _to_full_frame(
        self, window: SliceWindow, predictions: Sequence[Detection]
    ) -> list[Detection]:
        model_width, model_height = self.config.model_size
        scale_x = window.width / model_width
        scale_y = window.height / model_height
        return [
            Detection(
                detection.label,
                detection.confidence,
                (
                    window.left + detection.bbox_xyxy[0] * scale_x,
                    window.top + detection.bbox_xyxy[1] * scale_y,
                    window.left + detection.bbox_xyxy[2] * scale_x,
                    window.top + detection.bbox_xyxy[3] * scale_y,
                ),
            )
            for detection in predictions
        ]

    def _validate_frame(self, frame: Any) -> None:
        if getattr(frame, "ndim", None) not in (2, 3):
            raise ValueError("main frame must be a 2D or 3D image array")
        if (frame.shape[1], frame.shape[0]) != self.config.main_size:
            raise ValueError(
                f"main frame must be {self.config.main_size[0]}x{self.config.main_size[1]}"
            )

    def _reset_track(self) -> None:
        self._active_detection = None
        self._track_misses = 0
        self._next_roi_size_px = self.config.normal_roi_size_px
        self._confirmer.reset()

    def _result(
        self,
        *,
        started: int,
        source_timestamp_ns: int,
        detections: Sequence[Detection],
        confirmed: Sequence[Detection],
        tile_count: int,
        mode: str,
        roi_rect: tuple[int, int, int, int] | None = None,
    ) -> SearchSweep:
        completed = time.monotonic_ns()
        self._sweep_id += 1
        return SearchSweep(
            sweep_id=self._sweep_id,
            source_timestamp_ns=source_timestamp_ns,
            completed_monotonic_ns=completed,
            detections=tuple(detections),
            confirmed_detections=tuple(confirmed),
            tile_count=tile_count,
            latency_ms=(completed - started) / 1_000_000,
            mode=mode,
            roi_rect_full_frame_px=roi_rect,
        )


class LatestWinsSahiSearch:
    """One-worker scheduler that never accumulates stale camera frames."""

    input_stream = "sahi-main"

    def __init__(self, engine: SahiSearchEngine) -> None:
        self.engine = engine
        self.stale_ns = int(engine.config.stale_after_ms * 1_000_000)
        self._queue: queue.Queue[tuple[Any, int] | None] = queue.Queue(maxsize=1)
        self._lock = threading.Lock()
        self._result: SearchSweep | None = None
        self._running = False
        self._thread: threading.Thread | None = None
        self._dropped = 0
        self._last_error: str | None = None

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True, name="SahiSearch")
        self._thread.start()

    def stop(self) -> None:
        self._running = False
        self._offer(None)
        if self._thread:
            self._thread.join(timeout=2.0)

    def submit(self, frame: Any, receive_monotonic_ns: int) -> None:
        self._offer((frame, receive_monotonic_ns))

    def latest(self, *, now_monotonic_ns: int | None = None) -> list[Detection]:
        now = time.monotonic_ns() if now_monotonic_ns is None else now_monotonic_ns
        with self._lock:
            result = self._result
        if result is None or now - result.source_timestamp_ns > self.stale_ns:
            return []
        return list(result.confirmed_detections)

    def health(self) -> dict[str, Any]:
        with self._lock:
            result = self._result
        elapsed = None if result is None else result.latency_ms
        cycle_hz = None if not elapsed or elapsed <= 0.0 else 1000.0 / elapsed
        is_search = result is not None and result.mode == "SEARCH_SAHI_SWEEP"
        return {
            **self.engine.detector.health(),
            "coordinateSpace": "main",
            "sourceResolution": list(self.engine.config.main_size),
            "configuredSearchTileCount": len(self.engine.windows),
            "lastCycleTileCount": None if result is None else result.tile_count,
            "inferenceMode": self.engine.mode if result is None else result.mode,
            "roiRectFullFramePx": None if result is None else result.roi_rect_full_frame_px,
            "workerRunning": self._running,
            "resultAvailable": result is not None,
            "lastSweepId": None if result is None else result.sweep_id,
            "lastCycleLatencyMs": elapsed,
            "lastCycleHz": cycle_hz,
            "minimumSweepHzMet": (
                cycle_hz >= self.engine.config.minimum_sweeps_per_second
                if is_search and cycle_hz is not None
                else None
            ),
            "droppedFrames": self._dropped,
            "lastError": self._last_error,
        }

    def _offer(self, item: tuple[Any, int] | None) -> None:
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

    def _run(self) -> None:
        while self._running:
            item = self._queue.get()
            try:
                if item is None:
                    return
                frame, timestamp = item
                result = self.engine.run_frame(frame, timestamp)
                with self._lock:
                    self._result = result
                self._last_error = None
            except Exception as exc:
                self._last_error = f"{type(exc).__name__}:{exc}"
                with self._lock:
                    self._result = None
            finally:
                self._queue.task_done()
