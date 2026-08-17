"""Concrete Raspberry Pi AI HAT+ runner for Hailo NMS-enabled detector HEFs.

The deployed HEF must include Hailo NMS post-processing.  Picamera2's Hailo
wrapper then returns one list per class; each detection is
``[y_min, x_min, y_max, x_max, confidence]`` in normalized coordinates.
"""

from __future__ import annotations

from pathlib import Path
from threading import Lock
from typing import Any, Sequence


MODEL_LABELS = (
    "dusman_drone_kirmizi",
    "dusman_helikopter_kirmizi",
    "dusman_f16_kirmizi",
    "dusman_fuze_kirmizi",
    "dost_helikopter_camgobegi",
    "dost_f16_camgobegi",
    "balon",
)


def _unwrap_output(output: Any) -> Any:
    if isinstance(output, dict):
        if len(output) != 1:
            raise ValueError("HEF must expose one Hailo NMS output")
        return next(iter(output.values()))
    return output


def _normalize_nms_output(output: Any, width: int, height: int) -> list[dict[str, Any]]:
    class_groups = _unwrap_output(output)
    if len(class_groups) != len(MODEL_LABELS):
        raise ValueError(
            f"HEF class count mismatch: expected {len(MODEL_LABELS)}, got {len(class_groups)}"
        )
    result: list[dict[str, Any]] = []
    for class_id, detections in enumerate(class_groups):
        for detection in detections:
            values = [float(value) for value in detection]
            if len(values) < 5:
                continue
            y_min, x_min, y_max, x_max, confidence = values[:5]
            if max(abs(x_min), abs(y_min), abs(x_max), abs(y_max)) <= 1.5:
                x_min, x_max = x_min * width, x_max * width
                y_min, y_max = y_min * height, y_max * height
            result.append(
                {
                    "label": MODEL_LABELS[class_id],
                    "confidence": confidence,
                    "bbox": [x_min, y_min, x_max, y_max],
                }
            )
    return result


class _SequentialBatchRunner:
    """Reuse one configured Hailo device while accepting variable SAHI batches."""

    def __init__(self, model_path: str | Path) -> None:
        try:
            from picamera2.devices import Hailo
        except ImportError as exc:  # pragma: no cover - Raspberry Pi deployment guard
            raise RuntimeError("Picamera2 Hailo Python support is not installed") from exc
        self._hailo = Hailo(str(model_path))
        model_height, model_width, _channels = self._hailo.get_input_shape()
        self._width = int(model_width)
        self._height = int(model_height)
        self._lock = Lock()

    def __call__(self, frames: Sequence[Any]) -> list[list[dict[str, Any]]]:
        # A single configured model is shared by the latest-wins worker only.
        # The lock also keeps accidental concurrent calls deterministic.
        with self._lock:
            return [
                _normalize_nms_output(self._hailo.run(frame), self._width, self._height)
                for frame in frames
            ]

    def close(self) -> None:
        self._hailo.close()


def create_batch_runner(model_path: str | Path) -> _SequentialBatchRunner:
    """Factory consumed by ``GOKKALKAN_HAILO_BATCH_RUNNER_FACTORY``."""

    path = Path(model_path)
    if path.suffix.lower() != ".hef" or not path.is_file():
        raise ValueError("a readable .hef model is required")
    return _SequentialBatchRunner(path)

