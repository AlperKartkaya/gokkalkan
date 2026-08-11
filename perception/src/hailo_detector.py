"""Fail-closed Hailo-8 detector boundary for a validated HEF runner."""

from __future__ import annotations

import hashlib
from pathlib import Path
import time
from typing import Any, Callable, Iterable

from detector import Detection


class HailoDetector:
    """Validate model identity and normalize results from the installed Hailo runner.

    The concrete HailoRT binding is injected so tests never pretend hardware
    inference occurred and deployment can bind the installed SDK version.
    """

    def __init__(
        self,
        model_path: str | Path,
        inference: Callable[[Any], Iterable[dict[str, Any]]],
        *,
        allowed_labels: set[str],
        label_map: dict[str, str] | None = None,
        min_confidence: float = 0.4,
    ) -> None:
        self.model_path = Path(model_path)
        if self.model_path.suffix.lower() != ".hef" or not self.model_path.is_file():
            raise ValueError("a real HEF model file is required")
        self.model_sha256 = hashlib.sha256(self.model_path.read_bytes()).hexdigest()
        self.inference = inference
        self.allowed_labels = allowed_labels
        self.label_map = label_map or {}
        self.min_confidence = min_confidence
        self._last_inference_ns: int | None = None
        self._last_error: str | None = None

    def detect(self, frame: Any) -> list[Detection]:
        try:
            raw = list(self.inference(frame))
            detections = []
            for item in raw:
                label = str(item["label"])
                confidence = float(item["confidence"])
                bbox = tuple(float(value) for value in item["bbox"])
                if label not in self.allowed_labels or confidence < self.min_confidence or len(bbox) != 4:
                    continue
                detections.append(Detection(self.label_map.get(label, label), confidence, bbox))  # type: ignore[arg-type]
            self._last_inference_ns = time.monotonic_ns()
            self._last_error = None
            return detections
        except Exception as exc:
            self._last_error = f"{type(exc).__name__}:{exc}"
            raise

    def health(self) -> dict[str, Any]:
        return {
            "detector": "hailo8-hef",
            "modelPath": str(self.model_path),
            "modelSha256": self.model_sha256,
            "inferenceReady": self._last_error is None and self._last_inference_ns is not None,
            "lastInferenceMonotonicNs": self._last_inference_ns,
            "lastError": self._last_error,
        }
