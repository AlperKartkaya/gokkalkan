"""Canonical poligon geometry, route projection and curve-aware prediction.

The runtime source is ``config/course/plg26_a_001_002_r1.json``.  Only the
poligon-interior portions of the three routes are represented.  A projection
outside those portions is deliberately rejected; the unmodelled outside return
must never be used to manufacture a target position or a firing lead.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from math import atan2, cos, degrees, hypot, isfinite, radians, sin
import os
from pathlib import Path
import time
from typing import Any, Callable, Literal


CourseLifecycle = Literal["ACTIVE_IN_POLIGON", "OUTSIDE_POLIGON"]


@dataclass(frozen=True, slots=True)
class CoursePoint:
    x_m: float
    y_m: float


@dataclass(frozen=True, slots=True)
class RouteWaypoint(CoursePoint):
    s_m: float
    range_m: float
    bearing_base_deg: float
    tangent_course_deg: float


@dataclass(frozen=True, slots=True)
class CourseRoute:
    route_id: str
    route_number: int
    label: str
    entry_boundary: str
    exit_boundary: str
    length_m: float
    waypoints: tuple[RouteWaypoint, ...]

    @property
    def entry(self) -> RouteWaypoint:
        return self.waypoints[0]

    @property
    def exit(self) -> RouteWaypoint:
        return self.waypoints[-1]


@dataclass(frozen=True, slots=True)
class RouteProjection:
    route_id: str
    route_number: int
    point: CoursePoint
    s_m: float
    residual_m: float
    tangent_course_deg: float


@dataclass(frozen=True, slots=True)
class CourseTrackState:
    track_id: str
    route_id: str | None
    route_number: int | None
    pass_index: int
    lifecycle: CourseLifecycle
    s_m: float
    speed_mps: float
    projected_point: CoursePoint | None
    projection_residual_m: float | None
    tangent_course_deg: float | None
    inside_poligon: bool
    prediction_valid: bool
    observed_at_s: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "trackId": self.track_id,
            "routeId": self.route_id,
            "routeNumber": self.route_number,
            "passIndex": self.pass_index,
            "lifecycle": self.lifecycle,
            "sM": round(self.s_m, 4),
            "speedMps": round(self.speed_mps, 4),
            "projectedCourseM": (
                {
                    "x": round(self.projected_point.x_m, 4),
                    "y": round(self.projected_point.y_m, 4),
                }
                if self.projected_point is not None
                else None
            ),
            "projectionResidualM": (
                round(self.projection_residual_m, 4)
                if self.projection_residual_m is not None
                else None
            ),
            "tangentCourseDeg": (
                round(self.tangent_course_deg, 3)
                if self.tangent_course_deg is not None
                else None
            ),
            "insidePoligon": self.inside_poligon,
            "predictionValid": self.prediction_valid,
        }


@dataclass(frozen=True, slots=True)
class InterceptPrediction:
    route_id: str
    pass_index: int
    s_m: float
    point: CoursePoint
    flight_time_s: float
    horizontal_range_m: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "routeId": self.route_id,
            "passIndex": self.pass_index,
            "sM": round(self.s_m, 4),
            "coursePointM": {
                "x": round(self.point.x_m, 4),
                "y": round(self.point.y_m, 4),
            },
            "flightTimeS": round(self.flight_time_s, 4),
            "horizontalRangeM": round(self.horizontal_range_m, 4),
        }


@dataclass(frozen=True, slots=True)
class CourseGeometry:
    dataset_id: str
    source_revision: int
    source_sha256: str
    bounds_west_m: float
    bounds_east_m: float
    bounds_south_m: float
    bounds_north_m: float
    system_reference: CoursePoint
    outside_return_included: bool
    routes: tuple[CourseRoute, ...]

    def route(self, route_id: str) -> CourseRoute:
        for route in self.routes:
            if route.route_id == route_id:
                return route
        raise KeyError(f"Unknown course route: {route_id}")

    def contains(self, point: CoursePoint, margin_m: float = 0.0) -> bool:
        margin_m = max(0.0, margin_m) + 1e-9
        return (
            self.bounds_west_m - margin_m
            <= point.x_m
            <= self.bounds_east_m + margin_m
            and self.bounds_south_m - margin_m
            <= point.y_m
            <= self.bounds_north_m + margin_m
        )

    def course_point_from_measurement(
        self,
        range_m: float,
        bearing_base_deg: float,
    ) -> CoursePoint:
        """Convert base-frame horizontal range/bearing to the course frame.

        The drawing-derived base frame points +X west and +Y south.  Therefore
        both base axes are the negatives of the course X/Y axes.
        """

        if not (
            isfinite(range_m)
            and range_m >= 0
            and isfinite(bearing_base_deg)
        ):
            raise ValueError("Range and bearing must be finite; range must be non-negative")
        angle = radians(bearing_base_deg)
        return CoursePoint(
            self.system_reference.x_m - range_m * cos(angle),
            self.system_reference.y_m - range_m * sin(angle),
        )

    def measurement_for_point(self, point: CoursePoint | None) -> tuple[float, float]:
        if point is None:
            raise ValueError("Course point is required")
        base_x = self.system_reference.x_m - point.x_m
        base_y = self.system_reference.y_m - point.y_m
        return hypot(base_x, base_y), degrees(atan2(base_y, base_x))

    def project_measurement(
        self,
        range_m: float,
        bearing_base_deg: float,
        *,
        route_id: str | None = None,
    ) -> RouteProjection | None:
        point = self.course_point_from_measurement(range_m, bearing_base_deg)
        return self.project_point(point, route_id=route_id)

    def project_point(
        self,
        point: CoursePoint,
        *,
        route_id: str | None = None,
    ) -> RouteProjection | None:
        candidates = (
            (self.route(route_id),)
            if route_id is not None
            else self.routes
        )
        best: RouteProjection | None = None
        for route in candidates:
            projection = _project_to_route(point, route)
            if best is None or projection.residual_m < best.residual_m:
                best = projection
        return best

    def point_at_s(self, route_id: str, s_m: float) -> CoursePoint | None:
        route = self.route(route_id)
        if not isfinite(s_m) or s_m < 0 or s_m > route.length_m:
            return None
        for start, end in zip(route.waypoints, route.waypoints[1:]):
            if s_m <= end.s_m:
                span = end.s_m - start.s_m
                ratio = 0.0 if span <= 0 else (s_m - start.s_m) / span
                return CoursePoint(
                    start.x_m + (end.x_m - start.x_m) * ratio,
                    start.y_m + (end.y_m - start.y_m) * ratio,
                )
        return CoursePoint(route.exit.x_m, route.exit.y_m)

    def metadata(self) -> dict[str, Any]:
        return {
            "datasetId": self.dataset_id,
            "sourceRevision": self.source_revision,
            "sourceSha256": self.source_sha256,
            "scope": "POLIGON_INTERIOR_ONLY",
            "outsideReturnIncluded": self.outside_return_included,
            "routeCount": len(self.routes),
            "boundsCourseM": {
                "westX": self.bounds_west_m,
                "eastX": self.bounds_east_m,
                "southY": self.bounds_south_m,
                "northY": self.bounds_north_m,
            },
        }


def _project_to_route(point: CoursePoint, route: CourseRoute) -> RouteProjection:
    best: RouteProjection | None = None
    for start, end in zip(route.waypoints, route.waypoints[1:]):
        dx = end.x_m - start.x_m
        dy = end.y_m - start.y_m
        length_sq = dx * dx + dy * dy
        if length_sq <= 0:
            ratio = 0.0
        else:
            ratio = (
                (point.x_m - start.x_m) * dx
                + (point.y_m - start.y_m) * dy
            ) / length_sq
            ratio = min(1.0, max(0.0, ratio))
        projected = CoursePoint(
            start.x_m + ratio * dx,
            start.y_m + ratio * dy,
        )
        residual = hypot(point.x_m - projected.x_m, point.y_m - projected.y_m)
        segment_length = hypot(dx, dy)
        projection = RouteProjection(
            route_id=route.route_id,
            route_number=route.route_number,
            point=projected,
            s_m=start.s_m + ratio * segment_length,
            residual_m=residual,
            tangent_course_deg=degrees(atan2(dy, dx)),
        )
        if best is None or projection.residual_m < best.residual_m:
            best = projection
    if best is None:
        raise ValueError(f"Route {route.route_id} has fewer than two waypoints")
    return best


def default_course_geometry_path() -> Path:
    override = os.environ.get("GOKKALKAN_COURSE_GEOMETRY")
    if override:
        return Path(override).expanduser().resolve()
    relative = Path("config") / "course" / "plg26_a_001_002_r1.json"
    candidates = (
        Path.cwd() / relative,
        Path(__file__).resolve().parents[3] / relative,
    )
    return next(
        (candidate for candidate in candidates if candidate.is_file()),
        candidates[0],
    )


def load_course_geometry(path: str | Path | None = None) -> CourseGeometry:
    dataset_path = Path(path) if path is not None else default_course_geometry_path()
    try:
        raw = json.loads(dataset_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Course geometry could not be loaded: {dataset_path}") from exc

    if raw.get("schema_version") != "2.0.0":
        raise ValueError("Unsupported course geometry schema")
    if raw.get("dataset_id") != "PLG26-A-001-002-00-R1":
        raise ValueError("Unexpected course geometry dataset identity")
    if raw.get("status") != "CANONICAL_POLIGON_INTERIOR_GEOMETRY":
        raise ValueError("Course geometry is not canonical")
    scope = raw["geometry_scope"]
    if (
        scope.get("active_prediction_region") != "POLIGON_INTERIOR_ONLY"
        or scope.get("outside_return_included") is not False
    ):
        raise ValueError("Runtime geometry must exclude the outside return")

    bounds = scope["poligon_bounds_course_m"]
    system = raw["raster_derivation"]["system_reference"]
    routes: list[CourseRoute] = []
    for item in raw["routes"]:
        if item.get("geometry_scope") != "POLIGON_INTERIOR_ONLY":
            raise ValueError(f"Route {item.get('id')} exceeds the poligon scope")
        waypoints = tuple(
            RouteWaypoint(
                x_m=float(point["x_m"]),
                y_m=float(point["y_m"]),
                s_m=float(point["s_m"]),
                range_m=float(point["range_m"]),
                bearing_base_deg=float(point["bearing_base_deg"]),
                tangent_course_deg=float(point["tangent_course_deg"]),
            )
            for point in item["poligon_waypoints"]
        )
        length_m = float(item["derived_summary"]["poligon_path_length_m"])
        if len(waypoints) < 2 or abs(waypoints[-1].s_m - length_m) > 1e-3:
            raise ValueError(f"Route {item.get('id')} arc length is inconsistent")
        if any(
            next_point.s_m <= point.s_m
            for point, next_point in zip(waypoints, waypoints[1:])
        ):
            raise ValueError(f"Route {item.get('id')} waypoints are not ordered")
        routes.append(
            CourseRoute(
                route_id=str(item["id"]),
                route_number=int(item["route_number"]),
                label=str(item["label"]),
                entry_boundary=str(item["entry_boundary"]),
                exit_boundary=str(item["exit_boundary"]),
                length_m=length_m,
                waypoints=waypoints,
            )
        )
    if [route.route_number for route in routes] != [1, 2, 3]:
        raise ValueError("Exactly the three canonical route numbers are required")

    geometry = CourseGeometry(
        dataset_id=str(raw["dataset_id"]),
        source_revision=int(raw["source"]["revision"]),
        source_sha256=str(raw["source"]["sha256"]),
        bounds_west_m=float(bounds["west_x"]),
        bounds_east_m=float(bounds["east_x"]),
        bounds_south_m=float(bounds["south_y"]),
        bounds_north_m=float(bounds["north_y"]),
        system_reference=CoursePoint(
            float(system["course_x_m"]),
            float(system["course_y_m"]),
        ),
        outside_return_included=False,
        routes=tuple(routes),
    )
    for route in geometry.routes:
        if any(not geometry.contains(point) for point in route.waypoints):
            raise ValueError(f"Route {route.route_id} contains an outside waypoint")
    return geometry


class CourseTrackEstimator:
    """Associate measured tracks with a canonical route and estimate ``s, v``."""

    def __init__(
        self,
        geometry: CourseGeometry,
        *,
        clock: Callable[[], float] = time.monotonic,
        max_projection_residual_m: float = 0.75,
        route_switch_margin_m: float = 0.25,
        entry_window_m: float = 1.0,
        speed_alpha: float = 0.35,
        backward_jitter_m: float = 0.25,
    ) -> None:
        self.geometry = geometry
        self._clock = clock
        self.max_projection_residual_m = max_projection_residual_m
        self.route_switch_margin_m = route_switch_margin_m
        self.entry_window_m = entry_window_m
        self.speed_alpha = speed_alpha
        self.backward_jitter_m = backward_jitter_m
        self._states: dict[str, CourseTrackState] = {}

    def state(self, track_id: str) -> CourseTrackState | None:
        return self._states.get(track_id)

    def reset(self) -> None:
        self._states.clear()

    def update(
        self,
        track_id: str,
        range_m: float,
        bearing_base_deg: float,
        *,
        observed_at_s: float | None = None,
    ) -> CourseTrackState:
        observed_at = self._clock() if observed_at_s is None else observed_at_s
        if not isfinite(observed_at):
            raise ValueError("Observation time must be finite")
        previous = self._states.get(track_id)
        measured_point = self.geometry.course_point_from_measurement(
            range_m,
            bearing_base_deg,
        )
        best = self.geometry.project_point(measured_point)
        projection = best
        if previous is not None and previous.route_id is not None:
            previous_route = self.geometry.project_point(
                measured_point,
                route_id=previous.route_id,
            )
            if (
                best is not None
                and previous_route is not None
                and previous_route.residual_m
                <= best.residual_m + self.route_switch_margin_m
            ):
                projection = previous_route

        if (
            projection is None
            or not self.geometry.contains(measured_point)
            or projection.residual_m > self.max_projection_residual_m
        ):
            state = CourseTrackState(
                track_id=track_id,
                route_id=previous.route_id if previous else None,
                route_number=previous.route_number if previous else None,
                pass_index=previous.pass_index if previous else 0,
                lifecycle="OUTSIDE_POLIGON",
                s_m=previous.s_m if previous else 0.0,
                speed_mps=0.0,
                projected_point=None,
                projection_residual_m=(
                    projection.residual_m if projection is not None else None
                ),
                tangent_course_deg=None,
                inside_poligon=False,
                prediction_valid=False,
                observed_at_s=observed_at,
            )
            self._states[track_id] = state
            return state

        reentry = (
            previous is not None
            and previous.lifecycle == "OUTSIDE_POLIGON"
            and projection.s_m <= self.entry_window_m
        )
        route_changed = (
            previous is not None
            and previous.route_id is not None
            and previous.route_id != projection.route_id
        )
        if previous is None or previous.pass_index == 0:
            pass_index = 1
        elif reentry:
            pass_index = previous.pass_index + 1
        else:
            pass_index = previous.pass_index

        speed_mps = 0.0
        if (
            previous is not None
            and previous.lifecycle == "ACTIVE_IN_POLIGON"
            and not route_changed
            and previous.route_id == projection.route_id
        ):
            elapsed = observed_at - previous.observed_at_s
            delta_s = projection.s_m - previous.s_m
            if elapsed > 0 and delta_s >= -self.backward_jitter_m:
                instantaneous = max(0.0, delta_s / elapsed)
                speed_mps = (
                    self.speed_alpha * instantaneous
                    + (1.0 - self.speed_alpha) * previous.speed_mps
                )

        state = CourseTrackState(
            track_id=track_id,
            route_id=projection.route_id,
            route_number=projection.route_number,
            pass_index=pass_index,
            lifecycle="ACTIVE_IN_POLIGON",
            s_m=projection.s_m,
            speed_mps=speed_mps,
            projected_point=projection.point,
            projection_residual_m=projection.residual_m,
            tangent_course_deg=projection.tangent_course_deg,
            inside_poligon=True,
            prediction_valid=True,
            observed_at_s=observed_at,
        )
        self._states[track_id] = state
        return state

    def mark_absent(self, observed_track_ids: set[str]) -> None:
        now = self._clock()
        for track_id, state in tuple(self._states.items()):
            if track_id in observed_track_ids:
                continue
            self._states[track_id] = CourseTrackState(
                track_id=track_id,
                route_id=state.route_id,
                route_number=state.route_number,
                pass_index=state.pass_index,
                lifecycle="OUTSIDE_POLIGON",
                s_m=state.s_m,
                speed_mps=0.0,
                projected_point=None,
                projection_residual_m=None,
                tangent_course_deg=None,
                inside_poligon=False,
                prediction_valid=False,
                observed_at_s=now,
            )

    def predict_intercept(
        self,
        track_id: str,
        *,
        projectile_speed_mps: float,
        fixed_latency_s: float = 0.0,
        iterations: int = 4,
    ) -> InterceptPrediction | None:
        """Predict the meeting point without modelling the outside return.

        ``projectile_speed_mps`` must be a measured system parameter supplied by
        integration configuration.  The drawing contains no projectile speed,
        drag or launch-latency value, so this method intentionally has no
        fabricated default.
        """

        state = self._states.get(track_id)
        if (
            state is None
            or not state.prediction_valid
            or state.route_id is None
            or state.speed_mps <= 0
            or not isfinite(projectile_speed_mps)
            or projectile_speed_mps <= 0
            or not isfinite(fixed_latency_s)
            or fixed_latency_s < 0
        ):
            return None

        point = state.projected_point
        if point is None:
            return None
        horizontal_range_m, _ = self.geometry.measurement_for_point(point)
        flight_time_s = fixed_latency_s + horizontal_range_m / projectile_speed_mps
        predicted_s = state.s_m
        for _ in range(max(1, iterations)):
            predicted_s = state.s_m + state.speed_mps * flight_time_s
            point = self.geometry.point_at_s(state.route_id, predicted_s)
            if point is None:
                return None
            horizontal_range_m, _ = self.geometry.measurement_for_point(point)
            flight_time_s = (
                fixed_latency_s + horizontal_range_m / projectile_speed_mps
            )

        return InterceptPrediction(
            route_id=state.route_id,
            pass_index=state.pass_index,
            s_m=predicted_s,
            point=point,
            flight_time_s=flight_time_s,
            horizontal_range_m=horizontal_range_m,
        )
