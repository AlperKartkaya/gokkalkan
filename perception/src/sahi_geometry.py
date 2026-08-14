"""Dependency-light SAHI-compatible slicing and cross-tile merge geometry.

The Raspberry Pi runtime deliberately keeps NumPy/OpenCV/Picamera2 on the
Raspberry Pi OS apt stack.  The official SAHI package is used in the offline
training/reference environment; this module implements the small deterministic
runtime subset and is parity-tested against SAHI's slice coordinates.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from detector import Detection


@dataclass(frozen=True, slots=True)
class SliceWindow:
    left: int
    top: int
    right: int
    bottom: int

    @property
    def width(self) -> int:
        return self.right - self.left

    @property
    def height(self) -> int:
        return self.bottom - self.top

    def as_xyxy(self) -> tuple[int, int, int, int]:
        return self.left, self.top, self.right, self.bottom


def _axis_starts(length: int, window: int, overlap_ratio: float) -> list[int]:
    if length <= 0 or window <= 0:
        raise ValueError("görüntü ve tile boyutları pozitif olmalı")
    if window > length:
        raise ValueError("tile boyutu görüntü boyutunu aşamaz")
    if not 0.0 <= overlap_ratio < 1.0:
        raise ValueError("overlap oranı [0, 1) aralığında olmalı")

    step = max(1, round(window * (1.0 - overlap_ratio)))
    starts: list[int] = []
    position = 0
    while True:
        aligned = min(position, length - window)
        if not starts or starts[-1] != aligned:
            starts.append(aligned)
        if aligned + window >= length:
            return starts
        position += step


def generate_slice_windows(
    *,
    image_width: int,
    image_height: int,
    slice_width: int,
    slice_height: int,
    overlap_width_ratio: float,
    overlap_height_ratio: float,
) -> list[SliceWindow]:
    """Return row-major windows matching SAHI's boundary-aligned slicing."""

    x_starts = _axis_starts(image_width, slice_width, overlap_width_ratio)
    y_starts = _axis_starts(image_height, slice_height, overlap_height_ratio)
    return [
        SliceWindow(x, y, x + slice_width, y + slice_height)
        for y in y_starts
        for x in x_starts
    ]


def intersection_area(
    first: tuple[float, float, float, float],
    second: tuple[float, float, float, float],
) -> float:
    left = max(first[0], second[0])
    top = max(first[1], second[1])
    right = min(first[2], second[2])
    bottom = min(first[3], second[3])
    return max(0.0, right - left) * max(0.0, bottom - top)


def bbox_area(bbox: tuple[float, float, float, float]) -> float:
    return max(0.0, bbox[2] - bbox[0]) * max(0.0, bbox[3] - bbox[1])


def iou(
    first: tuple[float, float, float, float],
    second: tuple[float, float, float, float],
) -> float:
    intersection = intersection_area(first, second)
    union = bbox_area(first) + bbox_area(second) - intersection
    return 0.0 if union <= 0.0 else intersection / union


def ios(
    first: tuple[float, float, float, float],
    second: tuple[float, float, float, float],
) -> float:
    intersection = intersection_area(first, second)
    smaller = min(bbox_area(first), bbox_area(second))
    return 0.0 if smaller <= 0.0 else intersection / smaller


def _weighted_merge(first: Detection, second: Detection) -> Detection:
    total = first.confidence + second.confidence
    if total <= 0.0:
        return first
    bbox = tuple(
        (a * first.confidence + b * second.confidence) / total
        for a, b in zip(first.bbox_xyxy, second.bbox_xyxy, strict=True)
    )
    return Detection(
        label=first.label,
        confidence=max(first.confidence, second.confidence),
        bbox_xyxy=bbox,  # type: ignore[arg-type]
    )


def greedy_nmm(
    detections: Iterable[Detection],
    *,
    match_threshold: float = 0.5,
    match_metric: str = "IOS",
    class_agnostic: bool = False,
) -> list[Detection]:
    """Greedily merge overlapping predictions using SAHI-compatible semantics."""

    if not 0.0 <= match_threshold <= 1.0:
        raise ValueError("match threshold [0, 1] aralığında olmalı")
    metric = match_metric.upper()
    if metric not in {"IOS", "IOU"}:
        raise ValueError("match metric IOS veya IOU olmalı")
    overlap = ios if metric == "IOS" else iou

    pending = sorted(detections, key=lambda item: item.confidence, reverse=True)
    merged: list[Detection] = []
    while pending:
        anchor = pending.pop(0)
        remainder: list[Detection] = []
        for candidate in pending:
            same_class = class_agnostic or candidate.label == anchor.label
            if same_class and overlap(anchor.bbox_xyxy, candidate.bbox_xyxy) >= match_threshold:
                anchor = _weighted_merge(anchor, candidate)
            else:
                remainder.append(candidate)
        merged.append(anchor)
        pending = remainder
    return merged


def mark_class_ambiguities(
    detections: Iterable[Detection],
    *,
    ios_threshold: float,
) -> list[Detection]:
    """Replace spatially conflicting labels with a fail-closed ambiguity result."""

    items = list(detections)
    adjacency: dict[int, set[int]] = {index: set() for index in range(len(items))}
    for index, first in enumerate(items):
        for other_index in range(index + 1, len(items)):
            second = items[other_index]
            if first.label != second.label and ios(first.bbox_xyxy, second.bbox_xyxy) >= ios_threshold:
                adjacency[index].add(other_index)
                adjacency[other_index].add(index)

    result: list[Detection] = []
    visited: set[int] = set()
    for index, item in enumerate(items):
        if index in visited:
            continue
        if not adjacency[index]:
            result.append(item)
            visited.add(index)
            continue
        component: set[int] = set()
        pending = [index]
        while pending:
            node = pending.pop()
            if node in component:
                continue
            component.add(node)
            pending.extend(adjacency[node] - component)
        visited.update(component)
        conflict_items = [items[i] for i in sorted(component)]
        left = min(d.bbox_xyxy[0] for d in conflict_items)
        top = min(d.bbox_xyxy[1] for d in conflict_items)
        right = max(d.bbox_xyxy[2] for d in conflict_items)
        bottom = max(d.bbox_xyxy[3] for d in conflict_items)
        result.append(
            Detection(
                label="AMBIGUOUS_CLASS",
                confidence=max(d.confidence for d in conflict_items),
                bbox_xyxy=(left, top, right, bottom),
            )
        )
    return result
