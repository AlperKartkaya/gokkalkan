from __future__ import annotations

import json
import tomllib
from pathlib import Path

import pytest

jsonschema = pytest.importorskip(
    "jsonschema",
    reason="CAD sözleşme testleri requirements/synthetic-render.lock gerektirir",
)

ROOT = Path(__file__).resolve().parents[1]
SYNTHETIC = ROOT / "perception/synthetic"


def load_json(relative: str) -> dict:
    return json.loads((SYNTHETIC / relative).read_text(encoding="utf-8"))


def validator(schema_name: str) -> jsonschema.Draft202012Validator:
    schema = load_json(f"schema/{schema_name}")
    return jsonschema.Draft202012Validator(
        schema,
        format_checker=jsonschema.FormatChecker(),
    )


def test_cad_source_matches_schema_and_remains_blocked() -> None:
    source = load_json("config/cad_source.json")

    validator("cad-source.schema.json").validate(source)

    assert source["status"] == "LOCAL_ONLY_PENDING_PROVENANCE"
    assert source["sourceUri"] is None
    assert source["owner"] is None
    assert source["licenseOrPermission"] is None


def test_verified_cad_source_requires_provenance_fields() -> None:
    source = load_json("config/cad_source.json")
    source["status"] = "VERIFIED_SHARED_SOURCE"

    with pytest.raises(jsonschema.ValidationError):
        validator("cad-source.schema.json").validate(source)


def test_asset_manifest_has_exactly_four_pending_assets() -> None:
    manifest = load_json("config/cad_asset_manifest.json")

    validator("cad-asset-manifest.schema.json").validate(manifest)

    assets = manifest["assets"]
    assert {asset["assetKey"] for asset in assets} == {
        "drone",
        "helicopter",
        "f16",
        "missile",
    }
    assert len({asset["sourceResourceId"] for asset in assets}) == 4
    assert all(
        asset["orientation"]
        == {
            "status": "PENDING_USER_CONFIRMATION",
            "noseAxis": "PENDING",
            "upAxis": "PENDING",
        }
        for asset in assets
    )
    assert all(asset["scale"]["status"] == "PROVISIONAL" for asset in assets)
    geometry_status = {
        asset["assetKey"]: (
            asset["sourceGeometry"]["lib3mfValid"],
            asset["sourceGeometry"]["manifoldAndOriented"],
        )
        for asset in assets
    }
    assert geometry_status == {
        "drone": (True, True),
        "f16": (True, True),
        "helicopter": (False, False),
        "missile": (True, True),
    }


def test_camera_and_scene_profiles_lock_same_height_and_pose_buckets() -> None:
    camera = tomllib.loads(
        (SYNTHETIC / "config/camera_profiles/camera_module_3_provisional.toml")
        .read_text(encoding="utf-8")
    )
    scene = tomllib.loads(
        (
            SYNTHETIC
            / "config/scene_profiles/committee_tilted_targets_provisional_v0.toml"
        ).read_text(encoding="utf-8")
    )

    assert camera["status"] == "UNVERIFIED"
    assert camera["cameraHeightM"] == camera["targetReferenceHeightM"] == 1.30
    assert camera["runtimeResolution"] == [1280, 720]
    assert camera["modelInputResolution"] == [640, 640]
    assert scene["distanceAnchorsM"] == [5.0, 10.0, 15.0]
    assert scene["viewYawBucketsDeg"] == [-25.0, -15.0, -5.0, 0.0, 5.0, 15.0, 25.0]
    assert scene["topSurfaceViewBucketsDeg"] == [8.0, 12.0, 18.0]
    assert scene["anchorSampleRatio"] + scene["continuousSampleRatio"] == 1.0


def test_render_record_schema_rejects_out_of_range_camera_pose() -> None:
    record = {
        "recordId": "REC-001",
        "worldId": "WORLD-001",
        "variantId": "ZOOM-1X",
        "groupId": "WORLD-001",
        "sourceKind": "synthetic_cad_pbr",
        "split": "train",
        "assetKey": "f16",
        "cameraProfileId": "CAMERA_MODULE_3_PROVISIONAL_R1",
        "distanceM": 10.0,
        "viewYawDeg": 15.0,
        "topSurfaceViewDeg": 12.0,
        "cameraElevationOffsetDeg": 0.0,
        "zoom": {
            "mode": "none",
            "factor": 1.0,
            "cropRectPx": [0, 0, 1280, 720],
            "preCropResolution": [1280, 720],
            "postCropResolution": [1280, 720],
            "modelInputResolution": [640, 640],
            "interpolation": "INTER_AREA",
            "targetPixelsBeforeZoom": 500,
            "targetPixelsAfterZoom": 500,
            "zoomCenterErrorPx": [0.0, 0.0],
        },
    }
    render_validator = validator("render-record.schema.json")

    render_validator.validate(record)
    record["cameraElevationOffsetDeg"] = 4.0

    with pytest.raises(jsonschema.ValidationError):
        render_validator.validate(record)
