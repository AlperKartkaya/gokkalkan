"""Camera-centric pose math for filterable CAD render batches.

The 3MF source is already authored in the Bambu Studio presentation frame:
``Front`` means the camera is on source ``-Y``; screen-right is ``+X`` and
screen-up is ``+Z``.  A positive top-surface angle pitches the target around
``+X`` so its nose moves down and its top surface moves toward the camera.
"""

from __future__ import annotations

import math
from collections.abc import Sequence


class PoseContractError(ValueError):
    """Raised when a requested pose violates the camera-frame contract."""


def rotation_x(degrees: float) -> list[list[float]]:
    angle = math.radians(degrees)
    cosine, sine = math.cos(angle), math.sin(angle)
    return [
        [1.0, 0.0, 0.0],
        [0.0, cosine, -sine],
        [0.0, sine, cosine],
    ]


def rotation_z(degrees: float) -> list[list[float]]:
    angle = math.radians(degrees)
    cosine, sine = math.cos(angle), math.sin(angle)
    return [
        [cosine, -sine, 0.0],
        [sine, cosine, 0.0],
        [0.0, 0.0, 1.0],
    ]


def matrix_multiply(
    left: Sequence[Sequence[float]],
    right: Sequence[Sequence[float]],
) -> list[list[float]]:
    return [
        [
            sum(float(left[row][index]) * float(right[index][column]) for index in range(3))
            for column in range(3)
        ]
        for row in range(3)
    ]


def target_rotation_world(
    *,
    view_yaw_deg: float,
    top_surface_view_deg: float,
) -> list[list[float]]:
    """Return ``Rz(yaw) @ Rx(tilt)`` for the Bambu Front source frame."""

    if not -90.0 < view_yaw_deg < 90.0:
        raise PoseContractError("view yaw front yarımkürede kalmalı")
    if not 0.0 <= top_surface_view_deg < 90.0:
        raise PoseContractError("top-surface açısı [0, 90) aralığında olmalı")
    matrix = matrix_multiply(
        rotation_z(view_yaw_deg),
        rotation_x(top_surface_view_deg),
    )
    return [[round(value, 9) for value in row] for row in matrix]


def target_position_world(
    *,
    distance_m: float,
    lateral_offset_m: float,
    vertical_offset_m: float,
    camera_height_m: float,
) -> list[float]:
    """Place target while keeping ``distance_m`` as true camera range.

    Camera is at ``[0, 0, camera_height_m]``.  ``+X`` is image-right, ``+Y``
    is forward and ``+Z`` is up.  Forward Y is solved from the Euclidean range
    instead of silently changing range when X/Z offsets are sampled.
    """

    remaining_squared = (
        distance_m * distance_m
        - lateral_offset_m * lateral_offset_m
        - vertical_offset_m * vertical_offset_m
    )
    if distance_m <= 0 or remaining_squared <= 0:
        raise PoseContractError("X/Z ofsetleri seçilen mesafeden küçük olmalı")
    return [
        round(lateral_offset_m, 6),
        round(math.sqrt(remaining_squared), 6),
        round(camera_height_m + vertical_offset_m, 6),
    ]


def euclidean_camera_range(
    target_position_m: Sequence[float],
    *,
    camera_height_m: float,
) -> float:
    relative = (
        float(target_position_m[0]),
        float(target_position_m[1]),
        float(target_position_m[2]) - camera_height_m,
    )
    return math.sqrt(sum(value * value for value in relative))
