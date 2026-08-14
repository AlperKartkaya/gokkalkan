"""Camera-centric pose math for route-derived CAD render batches.

The camera sits at ``[0, 0, camera_height]``; ``+X`` is image-right, ``+Y``
is forward and ``+Z`` is up.  The target remains Front-aligned.  Its apparent
yaw is a consequence of the signed route offset and is therefore metadata,
not an additional rotation around Z.
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


def route_view_yaw_deg(
    *,
    longitudinal_distance_m: float,
    signed_lateral_distance_m: float,
) -> float:
    """Return apparent yaw from route geometry: ``atan2(x, y)`` in degrees."""

    if longitudinal_distance_m <= 0:
        raise PoseContractError("boylamasına mesafe sıfırdan büyük olmalı")
    return math.degrees(math.atan2(signed_lateral_distance_m, longitudinal_distance_m))


def target_rotation_world(*, top_surface_view_deg: float) -> list[list[float]]:
    """Return only the physical nose-down tilt for the Front-aligned target.

    Route-derived yaw must not be applied here a second time: the camera-to-
    target ray already creates the intended right/left viewing angle.
    """

    if not 0.0 <= top_surface_view_deg < 90.0:
        raise PoseContractError("top-surface açısı [0, 90) aralığında olmalı")
    return [
        [round(value, 9) for value in row] for row in rotation_x(top_surface_view_deg)
    ]


def target_position_world(
    *,
    longitudinal_distance_m: float,
    signed_lateral_distance_m: float,
    vertical_offset_m: float,
    camera_height_m: float,
) -> list[float]:
    """Place a route sample directly from its longitudinal/lateral distances."""

    if longitudinal_distance_m <= 0:
        raise PoseContractError("boylamasına mesafe sıfırdan büyük olmalı")
    return [
        round(signed_lateral_distance_m, 6),
        round(longitudinal_distance_m, 6),
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
