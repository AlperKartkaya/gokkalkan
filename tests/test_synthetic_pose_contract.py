from __future__ import annotations

import json
import math
import sys
import tomllib
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
    target_position_world,
    target_rotation_world,
)


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_positive_tilt_moves_front_facing_nose_down() -> None:
    rotation = target_rotation_world(view_yaw_deg=0.0, top_surface_view_deg=12.0)
    source_nose = [0.0, -1.0, 0.0]
    transformed = [
        sum(rotation[row][column] * source_nose[column] for column in range(3))
        for row in range(3)
    ]

    assert transformed[1] < 0
    assert transformed[2] < 0


def test_xyz_position_preserves_true_camera_range() -> None:
    position = target_position_world(
        distance_m=5.0,
        lateral_offset_m=0.75,
        vertical_offset_m=0.25,
        camera_height_m=1.30,
    )

    assert euclidean_camera_range(position, camera_height_m=1.30) == pytest.approx(5.0)


def test_render_plan_is_deterministic_filterable_and_schema_valid() -> None:
    synthetic = ROOT / "perception/synthetic"
    profile = tomllib.loads(
        (synthetic / "config/scene_profiles/committee_tilted_targets_sweep_v1.toml")
        .read_text(encoding="utf-8")
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
    assert len(first["records"]) == 2 * 3 * 5 * 3 * 7 * 8
    assert {record["topSurfaceViewBucketDeg"] for record in first["records"]} == {
        0.0,
        4.0,
        8.0,
        12.0,
        16.0,
        20.0,
        24.0,
        28.0,
    }

    schema = load_json(synthetic / "schema/render-record.schema.json")
    validator = jsonschema.Draft202012Validator(schema)
    for record in first["records"][::401]:
        validator.validate(record)
        assert math.isclose(
            euclidean_camera_range(record["targetPositionM"], camera_height_m=1.30),
            record["distanceM"],
            abs_tol=1e-5,
        )

    included, excluded = select_records(
        first["records"],
        min_tilt_deg=9.0,
        max_tilt_deg=17.0,
    )
    assert included
    assert excluded
    selected = {record["recordId"]: record for record in first["records"]}
    assert all(9.0 <= selected[record_id]["topSurfaceViewDeg"] <= 17.0 for record_id in included)
