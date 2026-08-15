"""Project confirmed model detections into stable, fail-closed API tracks."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any, Sequence

from detector import Detection
from sahi_geometry import iou


@dataclass(slots=True)
class _TrackedDetection:
    detection: Detection
    missed_updates: int = 0


class DetectionTrackProjector:
    """Assign stable IDs without treating camera bbox size as trusted range."""

    def __init__(self, *, max_missed_updates: int = 3, hfov_deg: float = 66.0) -> None:
        self.max_missed_updates = max_missed_updates
        self.hfov_deg = hfov_deg
        self._tracks: dict[str, _TrackedDetection] = {}
        self._next_id = 1

    def update(
        self,
        detections: Sequence[Detection],
        *,
        stage: int,
        source_size: tuple[int, int],
        output_size: tuple[int, int],
        receive_monotonic_ns: int,
        model_sha256: str | None,
    ) -> list[dict[str, Any]]:
        assigned_tracks: set[str] = set()
        assigned_detections: set[int] = set()

        candidates: list[tuple[float, str, int]] = []
        for track_id, tracked in self._tracks.items():
            for index, detection in enumerate(detections):
                if detection.label != tracked.detection.label:
                    continue
                score = iou(tracked.detection.bbox_xyxy, detection.bbox_xyxy)
                if score > 0.0:
                    candidates.append((score, track_id, index))
        for _score, track_id, index in sorted(candidates, reverse=True):
            if track_id in assigned_tracks or index in assigned_detections:
                continue
            self._tracks[track_id] = _TrackedDetection(detections[index])
            assigned_tracks.add(track_id)
            assigned_detections.add(index)

        for track_id in list(self._tracks):
            if track_id in assigned_tracks:
                continue
            tracked = self._tracks[track_id]
            tracked.missed_updates += 1
            if tracked.missed_updates > self.max_missed_updates:
                del self._tracks[track_id]

        for index, detection in enumerate(detections):
            if index in assigned_detections:
                continue
            track_id = f"MODEL-{self._next_id:06d}"
            self._next_id += 1
            self._tracks[track_id] = _TrackedDetection(detection)
            assigned_tracks.add(track_id)

        return [
            self._to_api_track(
                track_id,
                self._tracks[track_id].detection,
                stage=stage,
                source_size=source_size,
                output_size=output_size,
                receive_monotonic_ns=receive_monotonic_ns,
                model_sha256=model_sha256,
            )
            for track_id in sorted(assigned_tracks)
            if track_id in self._tracks
        ]

    def _to_api_track(
        self,
        track_id: str,
        detection: Detection,
        *,
        stage: int,
        source_size: tuple[int, int],
        output_size: tuple[int, int],
        receive_monotonic_ns: int,
        model_sha256: str | None,
    ) -> dict[str, Any]:
        source_width, source_height = source_size
        output_width, output_height = output_size
        x1, y1, x2, y2 = detection.bbox_xyxy
        center_x = (x1 + x2) / 2
        center_y = (y1 + y2) / 2
        scale_x = output_width / source_width
        scale_y = output_height / source_height
        ambiguous = detection.label == "AMBIGUOUS_CLASS"
        friend_foe = "Bilinmeyen"
        if stage == 3 and not ambiguous:
            if detection.label.startswith("dost_"):
                friend_foe = "Dost"
            elif detection.label.startswith("dusman_"):
                friend_foe = "Düşman"
        target_type = (
            "Bilinmeyen"
            if ambiguous
            else {
                "dusman_drone_kirmizi": "Mini/Micro İHA",
                "dusman_helikopter_kirmizi": "Helikopter",
                "dusman_f16_kirmizi": "F16",
                "dusman_fuze_kirmizi": "Balistik Füze",
                "dost_helikopter_camgobegi": "Helikopter",
                "dost_f16_camgobegi": "F16",
            }.get(detection.label, "Bilinmeyen")
        )
        bearing_deg = (center_x - source_width / 2) / source_width * self.hfov_deg
        values = (center_x, center_y, x2 - x1, y2 - y1, bearing_deg)
        if not all(math.isfinite(value) for value in values):
            raise ValueError("model detection coordinates must be finite")
        return {
            "trackId": track_id,
            "targetType": target_type,
            "friendFoe": friend_foe,
            # Camera geometry alone is not trusted range. Zero keeps this track
            # outside mission range gates until TFA50-L fusion updates it.
            "rangeM": 0.0,
            "bearingDeg": round(bearing_deg, 2),
            "confidence": round(detection.confidence, 3),
            "bboxPx": [
                center_x * scale_x,
                center_y * scale_y,
                (x2 - x1) * scale_x,
                (y2 - y1) * scale_y,
            ],
            "frameSizePx": [output_width, output_height],
            "source": "perception",
            "rangeSource": "unavailable-awaiting-lidar-fusion",
            "freshnessMs": 0.0,
            "trackState": "TRACKED",
            "receiveMonotonicNs": receive_monotonic_ns,
            "classificationState": "AMBIGUOUS_CLASS" if ambiguous else "CONFIRMED",
            "modelSha256": model_sha256,
            "yawErrorDeg": None,
            "pitchErrorDeg": None,
            "aimCalibrationId": None,
            "aimCalibrationHash": None,
            "aimValid": False,
        }
