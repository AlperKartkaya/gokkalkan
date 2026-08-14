from __future__ import annotations

import json
import math
import sys
import tomllib
from collections import Counter
from pathlib import Path

import pytest

jsonschema = pytest.importorskip("jsonschema")

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "perception/synthetic/tools"
sys.path.insert(0, str(TOOLS))

from filter_render_plan import select_records
from generate_scene_matrix import generate_render_plan
from pose_contract import (
    euclidean_camera_range,
    route_view_yaw_deg,
    target_position_world,
    target_rotation_world,
)


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_positive_tilt_moves_front_facing_nose_down_without_double_yaw() -> None:
    rotation = target_rotation_world(top_surface_view_deg=12.0)
    source_nose = [0.0, -1.0, 0.0]
    transformed = [
        sum(rotation[row][column] * source_nose[column] for column in range(3))
        for row in range(3)
    ]

    assert transformed[0] == pytest.approx(0.0)
    assert transformed[1] < 0
    assert transformed[2] < 0


def test_route_yaw_is_symmetric_zero_centered_and_decreases_with_distance() -> None:
    positive = [
        route_view_yaw_deg(
            longitudinal_distance_m=distance,
            signed_lateral_distance_m=2.87,
        )
        for distance in (3.0, 10.0, 17.0)
    ]
    negative = route_view_yaw_deg(
        longitudinal_distance_m=10.0,
        signed_lateral_distance_m=-2.87,
    )

    assert positive[0] > positive[1] > positive[2] > 0.0
    assert negative == pytest.approx(-positive[1])
    assert route_view_yaw_deg(
        longitudinal_distance_m=5.0,
        signed_lateral_distance_m=0.0,
    ) == pytest.approx(0.0)


def test_route_position_preserves_longitudinal_lateral_and_true_range() -> None:
    position = target_position_world(
        longitudinal_distance_m=10.0,
        signed_lateral_distance_m=2.87,
        vertical_offset_m=0.0,
        camera_height_m=1.30,
    )

    assert position == [2.87, 10.0, 1.3]
    assert euclidean_camera_range(position, camera_height_m=1.30) == pytest.approx(
        math.hypot(10.0, 2.87)
    )


def test_render_plan_is_deterministic_route_derived_filterable_and_schema_valid() -> (
    None
):
    synthetic = ROOT / "perception/synthetic"
    profile = tomllib.loads(
        (
            synthetic / "config/scene_profiles/committee_tilted_targets_sweep_v1.toml"
        ).read_text(encoding="utf-8")
    )
    assets_path = synthetic / "config/cad_asset_manifest.json"
    assets = load_json(assets_path)
    source = load_json(synthetic / "config/cad_source.json")
    kwargs = {
        "profile": profile,
        "asset_manifest": assets,
        "source_sha256": source["expectedSha256"],
        "asset_manifest_sha256": "a" * 64,
        "seed": 42,
        "asset_keys": {"f16"},
    }
    first = generate_render_plan(**kwargs)
    second = generate_render_plan(**kwargs)

    assert first == second
    assert len(first["records"]) == 2 * 15 * 7 * 11
    assert {record["split"] for record in first["records"]} == {"train", "val"}
    assert {record["topSurfaceViewBucketDeg"] for record in first["records"]} == {
        4.0,
        6.0,
        8.0,
        10.0,
        12.0,
        14.0,
        16.0,
        18.0,
        20.0,
        24.0,
        28.0,
    }
    assert {record["routeId"] for record in first["records"]} == {
        "ROTA_1",
        "ROTA_2",
        "ROTA_3",
    }

    full = generate_render_plan(**{**kwargs, "asset_keys": None})
    full_f16 = {
        record["recordId"]: record
        for record in full["records"]
        if record["assetKey"] == "f16"
    }
    assert {record["recordId"]: record for record in first["records"]} == full_f16

    schema = load_json(synthetic / "schema/render-record.schema.json")
    validator = jsonschema.Draft202012Validator(schema)
    for record in first["records"]:
        validator.validate(record)
        assert record["viewYawDeg"] == pytest.approx(
            math.degrees(
                math.atan2(
                    record["lateralDistanceM"],
                    record["longitudinalDistanceM"],
                )
            ),
            abs=1e-6,
        )
        assert math.isclose(
            euclidean_camera_range(record["targetPositionM"], camera_height_m=1.30),
            record["distanceM"],
            abs_tol=1e-5,
        )
        if record["routeId"] == "ROTA_2":
            assert record["viewYawDeg"] == 0.0
        balloon = record["sceneGroundTruth"]["balloon"]
        assert (
            balloon["targetInstanceId"]
            == record["sceneGroundTruth"]["targetInstanceId"]
        )
        if record["presentationClass"].startswith("dost_"):
            assert balloon["fireCandidateAllowed"] is False
            assert record["sceneGroundTruth"]["eligibleStageIds"] == ["ASAMA_3"]

    appearance_counts = Counter(
        record["appearanceProfileId"] for record in first["records"]
    )
    assert set(appearance_counts) == {
        "nominal",
        "slightly_faded",
        "dim_environment",
        "bright_environment",
    }
    assert appearance_counts["nominal"] / len(first["records"]) == pytest.approx(
        0.4, abs=0.03
    )
    for variant in ("slightly_faded", "dim_environment", "bright_environment"):
        assert appearance_counts[variant] / len(first["records"]) == pytest.approx(
            0.2, abs=0.03
        )

    included, excluded = select_records(
        first["records"],
        min_tilt_deg=9.0,
        max_tilt_deg=17.0,
    )
    assert included
    assert excluded
    selected = {record["recordId"]: record for record in first["records"]}
    assert all(
        9.0 <= selected[record_id]["topSurfaceViewDeg"] <= 17.0
        for record_id in included
    )
