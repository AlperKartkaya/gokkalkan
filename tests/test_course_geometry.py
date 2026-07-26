from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATASET_PATH = ROOT / "config/course/plg26_a_001_002_r1.json"


def load_dataset() -> dict:
    return json.loads(DATASET_PATH.read_text(encoding="utf-8"))


def distance_to_chord(point: dict, start: dict, end: dict) -> float:
    chord_x = end["x_m"] - start["x_m"]
    chord_y = end["y_m"] - start["y_m"]
    chord_length = math.hypot(chord_x, chord_y)
    cross = chord_y * (point["x_m"] - start["x_m"]) - chord_x * (
        point["y_m"] - start["y_m"]
    )
    return abs(cross) / chord_length


def test_course_dataset_is_pinned_to_the_source_pdf() -> None:
    dataset = load_dataset()
    source = ROOT / dataset["source"]["path"]

    assert dataset["schema_version"] == "2.0.0"
    assert dataset["status"] == "CANONICAL_POLIGON_INTERIOR_GEOMETRY"
    assert dataset["dataset_id"] == "PLG26-A-001-002-00-R1"
    assert dataset["source"]["revision"] == 1
    assert hashlib.sha256(source.read_bytes()).hexdigest() == dataset["source"]["sha256"]


def test_all_visual_dimension_annotations_are_preserved_and_classified() -> None:
    dataset = load_dataset()
    dimensions = dataset["dimension_annotations"]

    assert sum(item["annotation_count"] for item in dimensions) == 26
    assert {item["view"] for item in dimensions} == {"plan", "side"}
    assert all(item["provenance"] == "DIRECT_DIMENSION" for item in dimensions)
    assert all(item["measurement_class"] for item in dimensions)
    assert all(len(item["measured_entities"]) == 2 for item in dimensions)
    assert all(item["active_prediction_role"] for item in dimensions)

    expected_values = {
        193,
        517,
        645,
        705,
        866,
        894,
        1000,
        1300,
        1487,
        1756,
        2105,
        2133,
        2715,
        2950,
        4711,
        5000,
        10000,
        14000,
        14151,
        15381,
        16000,
        18000,
    }
    assert {item["value_mm"] for item in dimensions} == expected_values


def test_ambiguous_plan_dimensions_identify_what_they_measure() -> None:
    dimensions = {item["id"]: item for item in load_dataset()["dimension_annotations"]}

    north_span = dimensions["north_closed_loop_horizontal_span"]
    assert north_span["value_mm"] == 14151
    assert north_span["measurement_class"] == "CLOSED_LOOP_SPAN"
    assert "yay uzunluğu değildir" in north_span["description"]

    central_span = dimensions["central_outer_closed_loop_horizontal_span"]
    assert central_span["value_mm"] == 15381
    assert central_span["measurement_class"] == "CLOSED_LOOP_SPAN"
    assert "yay uzunluğu değildir" in central_span["description"]

    route_2_datum = dimensions["route_2_marked_curve_to_poligon_south"]
    route_3_datum = dimensions["route_3_marked_curve_to_poligon_south"]
    assert (route_2_datum["value_mm"], route_3_datum["value_mm"]) == (4711, 2133)
    assert route_2_datum["measurement_class"] == "ACTIVE_CURVE_TO_POLIGON_OFFSET"
    assert route_3_datum["measurement_class"] == "ACTIVE_CURVE_TO_POLIGON_OFFSET"

    north_gap = dimensions["north_loop_return_to_poligon_north"]
    south_gap = dimensions["poligon_south_to_south_inner_loop_return"]
    assert north_gap["value_mm"] == south_gap["value_mm"] == 645
    assert north_gap["measured_entities"] != south_gap["measured_entities"]
    assert north_gap["measurement_class"] == "OUTSIDE_RETURN_TO_POLIGON_OFFSET"
    assert south_gap["measurement_class"] == "OUTSIDE_RETURN_TO_POLIGON_OFFSET"

    grid = dimensions["poligon_grid_west_interval"]
    assert grid["value_mm"] == 5000
    assert grid["measurement_class"] == "POLIGON_GRID_SPACING"
    assert "rota uzunluğu değildir" in grid["description"]


def test_dimension_derived_datums_close_on_written_dimensions() -> None:
    dataset = load_dataset()
    datums = dataset["dimension_derived_datums_course_mm"]

    assert datums["poligon"]["west_x"] == 18000 - 16000
    assert datums["poligon"]["north_y"] == 14000 - 705 - 645
    assert datums["poligon"]["south_y"] == datums["poligon"]["north_y"] - 10000

    north = datums["north_closed_loop"]
    assert north["east_extreme_x"] - north["west_extreme_x"] == 14151

    south = datums["south_inner_closed_loop"]
    assert south["east_extreme_x"] - south["west_extreme_x"] == 14151
    assert south["marked_active_curve_y"] - datums["poligon"]["south_y"] == 2133

    central = datums["central_outer_closed_loop"]
    assert central["east_extreme_x"] - central["west_extreme_x_selected"] == 15381
    assert central["east_extreme_x"] + 2105 == 18000
    assert central["marked_active_curve_y"] - datums["poligon"]["south_y"] == 4711
    assert [check["value_mm"] for check in central["west_extreme_x_checks"]] == [
        517,
        513,
        514,
    ]


def test_title_block_tolerance_spans_are_preserved_without_extrapolation() -> None:
    tolerances = load_dataset()["default_tolerances"]

    assert "4000 mm'de biter" in tolerances["coverage_warning"]
    assert "ekstrapole edilmez" in tolerances["coverage_warning"]
    assert tolerances["length_mm"] == [
        {"from_mm": 0.5, "up_to_mm": 6, "plus_minus_mm": 0.1},
        {"from_mm": 6, "up_to_mm": 30, "plus_minus_mm": 0.2},
        {"from_mm": 30, "up_to_mm": 120, "plus_minus_mm": 0.3},
        {"from_mm": 120, "up_to_mm": 400, "plus_minus_mm": 0.5},
        {"from_mm": 400, "up_to_mm": 1000, "plus_minus_mm": 0.8},
        {"from_mm": 1000, "up_to_mm": 2000, "plus_minus_mm": 1.2},
        {"from_mm": 2000, "up_to_mm": 4000, "plus_minus_mm": 2.0},
    ]
    assert tolerances["radius_chamfer_mm"] == [
        {"from_mm": 0.5, "up_to_mm": 3, "plus_minus_mm": 0.2},
        {"from_mm": 3, "up_to_mm": 6, "plus_minus_mm": 0.5},
        {"from_mm": 6, "up_to_mm": 4000, "plus_minus_mm": 1.0},
    ]
    assert tolerances["angle_deg"] == [
        {"from_mm": 0.5, "up_to_mm": 6, "plus_minus_deg": 1.0},
        {"from_mm": 6, "up_to_mm": 30, "plus_minus_deg": 0.5},
        {"from_mm": 30, "up_to_mm": 120, "plus_minus_deg": 0.3},
        {"from_mm": 120, "up_to_mm": 400, "plus_minus_deg": 0.2},
        {"from_mm": 400, "up_to_mm": 4000, "plus_minus_deg": 0.1},
    ]


def test_only_poligon_interior_route_segments_are_included() -> None:
    dataset = load_dataset()
    scope = dataset["geometry_scope"]
    bounds = scope["poligon_bounds_course_m"]
    routes = dataset["routes"]

    assert scope["active_prediction_region"] == "POLIGON_INTERIOR_ONLY"
    assert scope["outside_return_included"] is False
    assert "s sıfırlanır" in scope["reentry_rule"]
    assert [route["id"] for route in routes] == [
        "POLIGON_ROUTE_1",
        "POLIGON_ROUTE_2",
        "POLIGON_ROUTE_3",
    ]
    assert [route["route_number"] for route in routes] == [1, 2, 3]
    assert [route["exit_boundary"] for route in routes] == ["NORTH", "SOUTH", "SOUTH"]

    for route in routes:
        points = route["poligon_waypoints"]
        assert route["geometry_scope"] == "POLIGON_INTERIOR_ONLY"
        assert route["entry_boundary"] == "WEST"
        assert route["name_scope"] == "INTERNAL_NORTH_TO_SOUTH_ENTRY_ORDER_NOT_OFFICIAL"
        assert points[0]["x_m"] == bounds["west_x"]
        assert all(bounds["west_x"] <= point["x_m"] <= bounds["east_x"] for point in points)
        assert all(bounds["south_y"] <= point["y_m"] <= bounds["north_y"] for point in points)
        assert "lane" not in route
        assert "a_to_b_waypoints" not in route

    assert routes[0]["poligon_waypoints"][-1]["y_m"] == bounds["north_y"]
    assert routes[1]["poligon_waypoints"][-1]["y_m"] == bounds["south_y"]
    assert routes[2]["poligon_waypoints"][-1]["y_m"] == bounds["south_y"]


def test_routes_preserve_the_east_u_turn_inside_the_poligon() -> None:
    dataset = load_dataset()
    datums = dataset["dimension_derived_datums_course_mm"]
    expected_east_turn_x = [
        datums["north_closed_loop"]["east_extreme_x"] / 1000,
        datums["central_outer_closed_loop"]["east_extreme_x"] / 1000,
        datums["south_inner_closed_loop"]["east_extreme_x"] / 1000,
    ]

    for route, expected_x in zip(dataset["routes"], expected_east_turn_x):
        points = route["poligon_waypoints"]
        assert math.isclose(max(point["x_m"] for point in points), expected_x, abs_tol=1e-4)
        assert next(
            index
            for index, point in enumerate(points)
            if math.isclose(point["x_m"], expected_x, abs_tol=1e-4)
        ) < len(points) - 1
        assert points[-1]["x_m"] <= expected_x


def test_route_waypoints_are_curve_aware_ordered_and_self_consistent() -> None:
    dataset = load_dataset()
    system = dataset["raster_derivation"]["system_reference"]
    system_x = system["course_x_m"]
    system_y = system["course_y_m"]

    for route in dataset["routes"]:
        points = route["poligon_waypoints"]
        summary = route["derived_summary"]

        assert len(points) == summary["waypoint_count"]
        assert points[0]["s_m"] == 0
        assert all(left["s_m"] < right["s_m"] for left, right in zip(points, points[1:]))
        assert math.isclose(points[-1]["s_m"], summary["poligon_path_length_m"], abs_tol=1e-4)

        cumulative = 0.0
        for previous, point in zip(points, points[1:]):
            cumulative += math.hypot(
                point["x_m"] - previous["x_m"],
                point["y_m"] - previous["y_m"],
            )
            assert math.isclose(point["s_m"], cumulative, abs_tol=2e-3)

        chord = math.hypot(
            points[-1]["x_m"] - points[0]["x_m"],
            points[-1]["y_m"] - points[0]["y_m"],
        )
        max_deviation = max(distance_to_chord(point, points[0], points[-1]) for point in points)
        assert math.isclose(chord, summary["straight_entry_exit_chord_m"], abs_tol=2e-4)
        assert math.isclose(
            points[-1]["s_m"] - chord,
            summary["curve_excess_over_chord_m"],
            abs_tol=2e-4,
        )
        assert math.isclose(
            max_deviation,
            summary["max_deviation_from_entry_exit_chord_m"],
            abs_tol=2e-4,
        )
        assert summary["curve_excess_over_chord_m"] > 2.5
        assert summary["max_deviation_from_entry_exit_chord_m"] > 2.0
        assert max(point["tangent_course_deg"] for point in points) - min(
            point["tangent_course_deg"] for point in points
        ) > 45

        ranges = []
        for point in points:
            base_x = system_x - point["x_m"]
            base_y = system_y - point["y_m"]
            expected_range = math.hypot(base_x, base_y)
            expected_bearing = math.degrees(math.atan2(base_y, base_x))

            assert math.isclose(point["range_m"], expected_range, abs_tol=2e-4)
            assert math.isclose(point["bearing_base_deg"], expected_bearing, abs_tol=2e-3)
            ranges.append(point["range_m"])

        assert math.isclose(min(ranges), summary["min_horizontal_range_m"], abs_tol=1e-4)
        assert math.isclose(max(ranges), summary["max_horizontal_range_m"], abs_tol=1e-4)
