from __future__ import annotations

import math

from gokkalkan_backend.course_geometry import (
    CourseTrackEstimator,
    load_course_geometry,
)


def test_runtime_loader_preserves_canonical_poligon_routes() -> None:
    geometry = load_course_geometry()

    assert geometry.dataset_id == "PLG26-A-001-002-00-R1"
    assert geometry.outside_return_included is False
    assert [route.route_id for route in geometry.routes] == [
        "POLIGON_ROUTE_1",
        "POLIGON_ROUTE_2",
        "POLIGON_ROUTE_3",
    ]
    assert [len(route.waypoints) for route in geometry.routes] == [60, 72, 70]


def test_range_and_bearing_round_trip_to_course_coordinates() -> None:
    geometry = load_course_geometry()
    waypoint = geometry.routes[0].waypoints[17]

    point = geometry.course_point_from_measurement(
        waypoint.range_m,
        waypoint.bearing_base_deg,
    )

    assert math.isclose(point.x_m, waypoint.x_m, abs_tol=1e-3)
    assert math.isclose(point.y_m, waypoint.y_m, abs_tol=1e-3)


def test_projection_selects_the_curve_and_uses_arc_length() -> None:
    geometry = load_course_geometry()
    route = geometry.route("POLIGON_ROUTE_2")
    waypoint = route.waypoints[31]

    projection = geometry.project_measurement(
        waypoint.range_m,
        waypoint.bearing_base_deg,
    )

    assert projection is not None
    assert projection.route_id == route.route_id
    assert math.isclose(projection.s_m, waypoint.s_m, abs_tol=2e-3)
    assert projection.residual_m < 2e-3
    assert route.length_m > math.dist(
        (route.entry.x_m, route.entry.y_m),
        (route.exit.x_m, route.exit.y_m),
    )


def test_curve_prediction_stays_on_route_and_rejects_outside_return() -> None:
    geometry = load_course_geometry()
    route = geometry.route("POLIGON_ROUTE_1")
    start = route.waypoints[20]

    predicted = geometry.point_at_s(route.route_id, start.s_m + 1.25)
    outside = geometry.point_at_s(route.route_id, route.length_m + 0.01)

    assert predicted is not None
    reprojection = geometry.project_point(predicted, route_id=route.route_id)
    assert reprojection is not None
    assert reprojection.residual_m < 1e-9
    assert outside is None


def test_estimator_tracks_speed_and_predicts_a_curve_aware_intercept() -> None:
    geometry = load_course_geometry()
    route = geometry.route("POLIGON_ROUTE_3")
    estimator = CourseTrackEstimator(geometry, speed_alpha=1.0)
    first = geometry.measurement_for_point(geometry.point_at_s(route.route_id, 2.0))
    second = geometry.measurement_for_point(geometry.point_at_s(route.route_id, 3.0))

    state_1 = estimator.update("TRACK-1", *first, observed_at_s=10.0)
    state_2 = estimator.update("TRACK-1", *second, observed_at_s=10.5)
    lead = estimator.predict_intercept(
        "TRACK-1",
        projectile_speed_mps=40.0,
        fixed_latency_s=0.05,
    )

    assert state_1.inside_poligon is True
    assert state_2.route_id == route.route_id
    assert math.isclose(state_2.speed_mps, 2.0, abs_tol=0.02)
    assert lead is not None
    assert lead.flight_time_s > 0.05
    assert lead.s_m > state_2.s_m
    assert geometry.project_point(
        lead.point,
        route_id=route.route_id,
    ).residual_m < 1e-9


def test_estimator_closes_prediction_outside_and_increments_pass_on_reentry() -> None:
    geometry = load_course_geometry()
    route = geometry.route("POLIGON_ROUTE_1")
    estimator = CourseTrackEstimator(geometry)
    near_exit = geometry.measurement_for_point(
        geometry.point_at_s(route.route_id, route.length_m - 0.1)
    )
    entry = geometry.measurement_for_point(route.entry)

    active = estimator.update("TRACK-LOOP", *near_exit, observed_at_s=1.0)
    outside = estimator.update(
        "TRACK-LOOP",
        range_m=30.0,
        bearing_base_deg=0.0,
        observed_at_s=2.0,
    )
    reentered = estimator.update("TRACK-LOOP", *entry, observed_at_s=3.0)

    assert active.pass_index == 1
    assert outside.inside_poligon is False
    assert outside.prediction_valid is False
    assert outside.lifecycle == "OUTSIDE_POLIGON"
    assert reentered.inside_poligon is True
    assert reentered.pass_index == 2
    assert reentered.s_m == 0.0


def test_intercept_is_rejected_when_flight_would_cross_the_poligon_exit() -> None:
    geometry = load_course_geometry()
    route = geometry.route("POLIGON_ROUTE_3")
    estimator = CourseTrackEstimator(geometry, speed_alpha=1.0)
    before = geometry.measurement_for_point(
        geometry.point_at_s(route.route_id, route.length_m - 0.3)
    )
    near_exit = geometry.measurement_for_point(
        geometry.point_at_s(route.route_id, route.length_m - 0.1)
    )
    estimator.update("TRACK-EXIT", *before, observed_at_s=1.0)
    estimator.update("TRACK-EXIT", *near_exit, observed_at_s=1.1)

    prediction = estimator.predict_intercept(
        "TRACK-EXIT",
        projectile_speed_mps=10.0,
    )

    assert prediction is None


def test_estimator_uses_route_hysteresis_at_nearby_curves() -> None:
    geometry = load_course_geometry()
    estimator = CourseTrackEstimator(geometry, route_switch_margin_m=0.25)
    route = geometry.route("POLIGON_ROUTE_2")
    first = route.waypoints[25]
    state = estimator.update(
        "TRACK-STABLE",
        first.range_m,
        first.bearing_base_deg,
        observed_at_s=1.0,
    )

    assert state.route_id == route.route_id

    point = geometry.point_at_s(route.route_id, state.s_m + 0.05)
    measurement = geometry.measurement_for_point(point)
    next_state = estimator.update(
        "TRACK-STABLE",
        *measurement,
        observed_at_s=1.1,
    )
    assert next_state.route_id == route.route_id
