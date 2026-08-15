"""Batch Hailo inference adapter for square SAHI tiles.

The concrete HailoRT call is injected.  Tests therefore validate preprocessing,
model identity and output normalization without pretending that physical Hailo
inference occurred.

Confidence threshold:
  min_confidence=0.45 is the default for production.  0.20 generated excessive
  false positives across SAHI tiles during development.  Override per-instance
  for ablation or research runs that need lower thresholds.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
import time
from typing import Any, Callable, Iterable, Sequence

from detector import Detection


BatchInference = Callable[[Sequence[Any]], Sequence[Iterable[dict[str, Any]]]]


class HailoSahiAdapter:
    input_stream = "sahi-main"

    def __init__(
        self,
        model_path: str | Path,
        batch_inference: BatchInference,
        *,
        allowed_labels: set[str],
        label_map: dict[str, str] | None = None,
        min_confidence: float = 0.45,
        model_size: tuple[int, int] = (640, 640),
    ) -> None:
        self.model_path = Path(model_path)
        if self.model_path.suffix.lower() != ".hef" or not self.model_path.is_file():
            raise ValueError("a real HEF model file is required")
        if min(model_size) <= 0:
            raise ValueError("model size must be positive")
        self.model_sha256 = hashlib.sha256(self.model_path.read_bytes()).hexdigest()
        self.batch_inference = batch_inference
        self.allowed_labels = set(allowed_labels)
        self.label_map = label_map or {}
        self.min_confidence = min_confidence
        self.model_size = model_size
        self._last_inference_ns: int | None = None
        self._last_batch_size = 0
        self._last_latency_ms: float | None = None
        self._last_error: str | None = None

    def detect_batch(self, tiles: Sequence[Any]) -> list[list[Detection]]:
        try:
            prepared = [self._prepare(tile) for tile in tiles]
            started = time.monotonic_ns()
            raw_batches = list(self.batch_inference(prepared))
            finished = time.monotonic_ns()
            if len(raw_batches) != len(prepared):
                raise ValueError("Hailo batch result count does not match input count")
            normalized = [self._normalize(items) for items in raw_batches]
            self._last_inference_ns = finished
            self._last_batch_size = len(prepared)
            self._last_latency_ms = (finished - started) / 1_000_000
            self._last_error = None
            return normalized
        except Exception as exc:
            self._last_error = f"{type(exc).__name__}:{exc}"
            raise

    def health(self) -> dict[str, Any]:
        return {
            "detector": "hailo8-hef-sahi-batch",
            "modelPath": str(self.model_path),
            "modelSha256": self.model_sha256,
            "modelInputResolution": list(self.model_size),
            "inferenceReady": self._last_error is None and self._last_inference_ns is not None,
            "lastInferenceMonotonicNs": self._last_inference_ns,
            "lastBatchSize": self._last_batch_size,
            "lastBatchLatencyMs": self._last_latency_ms,
            "lastError": self._last_error,
        }

    def _prepare(self, tile: Any) -> Any:
        try:
            import cv2
        except ImportError as exc:  # pragma: no cover - deployment guard
            raise RuntimeError("OpenCV is required for Hailo tile preprocessing") from exc
        if getattr(tile, "ndim", None) not in (2, 3):
            raise ValueError("tile must be a 2D or 3D image array")
        target_width, target_height = self.model_size
        if tile.shape[1] == target_width and tile.shape[0] == target_height:
            return tile
        interpolation = (
            cv2.INTER_AREA
            if tile.shape[1] >= target_width and tile.shape[0] >= target_height
            else cv2.INTER_LINEAR
        )
        return cv2.resize(tile, self.model_size, interpolation=interpolation)

    def _normalize(self, raw: Iterable[dict[str, Any]]) -> list[Detection]:
        result: list[Detection] = []
        for item in raw:
            raw_label = str(item["label"])
            label = self.label_map.get(raw_label, raw_label)
            confidence = float(item["confidence"])
            bbox = tuple(float(value) for value in item["bbox"])
            if raw_label not in self.allowed_labels or confidence < self.min_confidence:
                continue
            if len(bbox) != 4 or bbox[2] <= bbox[0] or bbox[3] <= bbox[1]:
                continue
            result.append(Detection(label, confidence, bbox))  # type: ignore[arg-type]
        return result
