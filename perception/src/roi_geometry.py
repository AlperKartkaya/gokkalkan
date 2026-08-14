"""Resolution-safe ROI geometry shared by search and high-resolution streams."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Rect:
    left: int
    top: int
    width: int
    height: int

    def as_tuple(self) -> tuple[int, int, int, int]:
        return self.left, self.top, self.width, self.height


def letterbox_content_rect(
    source_size: tuple[int, int],
    model_size: tuple[int, int] = (640, 640),
) -> Rect:
    """Return the unpadded content rectangle inside a letterboxed tensor."""

    source_width, source_height = source_size
    model_width, model_height = model_size
    if min(source_width, source_height, model_width, model_height) <= 0:
        raise ValueError("çözünürlük değerleri pozitif olmalı")
    scale = min(model_width / source_width, model_height / source_height)
    content_width = max(1, round(source_width * scale))
    content_height = max(1, round(source_height * scale))
    return Rect(
        left=(model_width - content_width) // 2,
        top=(model_height - content_height) // 2,
        width=content_width,
        height=content_height,
    )


def model_point_to_source(
    point: tuple[float, float],
    *,
    source_size: tuple[int, int],
    model_size: tuple[int, int] = (640, 640),
) -> tuple[float, float]:
    """Undo letterbox padding and scale for a detector-space point."""

    content = letterbox_content_rect(source_size, model_size)
    source_width, source_height = source_size
    x = (point[0] - content.left) * source_width / content.width
    y = (point[1] - content.top) * source_height / content.height
    return (
        min(max(0.0, x), float(source_width - 1)),
        min(max(0.0, y), float(source_height - 1)),
    )


def scale_point_between_streams(
    point: tuple[float, float],
    *,
    source_size: tuple[int, int],
    destination_size: tuple[int, int],
) -> tuple[float, float]:
    source_width, source_height = source_size
    destination_width, destination_height = destination_size
    if min(source_width, source_height, destination_width, destination_height) <= 0:
        raise ValueError("çözünürlük değerleri pozitif olmalı")
    return (
        point[0] * destination_width / source_width,
        point[1] * destination_height / source_height,
    )


def high_res_roi_from_model_center(
    model_center: tuple[float, float],
    *,
    factor: float,
    search_size: tuple[int, int] = (1280, 720),
    high_res_size: tuple[int, int] = (2304, 1296),
    model_size: tuple[int, int] = (640, 640),
) -> Rect:
    """Map a search-model center to a clamped 16:9 high-resolution ROI."""

    if factor < 1.0:
        raise ValueError("ROI faktörü 1.0 veya daha büyük olmalı")
    search_point = model_point_to_source(
        model_center, source_size=search_size, model_size=model_size
    )
    center_x, center_y = scale_point_between_streams(
        search_point, source_size=search_size, destination_size=high_res_size
    )
    high_width, high_height = high_res_size
    crop_width = max(1, round(high_width / factor))
    crop_height = max(1, round(high_height / factor))
    left = min(max(0, round(center_x - crop_width / 2)), high_width - crop_width)
    top = min(max(0, round(center_y - crop_height / 2)), high_height - crop_height)
    return Rect(left=left, top=top, width=crop_width, height=crop_height)
