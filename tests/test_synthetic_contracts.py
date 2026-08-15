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


def test_cad_source_matches_schema_and_uses_hash_as_local_contract() -> None:
    source = load_json("config/cad_source.json")

    validator("cad-source.schema.json").validate(source)

    assert source["status"] == "LOCAL_WORKSPACE_VERIFIED_HASH"
    assert source["expectedSha256"] == (
        "9f696bf7aa8c5c0dc2fa1e733266e6e9c274494bc2f210c3bc40b8975fb47028"
    )


def test_asset_manifest_has_exactly_four_front_aligned_assets() -> None:
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
    for asset in assets:
        orientation = asset["orientation"]
        assert orientation["status"].startswith("VERIFIED_")
        assert orientation["screenUpAxisSource"] == "+Z"
        source_nose = {
            "+Y": [0.0, 1.0, 0.0],
            "-Y": [0.0, -1.0, 0.0],
            "+Z": [0.0, 0.0, 1.0],
        }[orientation["longitudinalNoseAxisSource"]]
        matrix = orientation["sourceToPresentationRotation3x3"]
        presentation_nose = [
            sum(matrix[row][column] * source_nose[column] for column in range(3))
            for row in range(3)
        ]
        if asset["assetKey"] != "missile":
            assert presentation_nose == pytest.approx([0.0, -1.0, 0.0])

    f16 = next(asset for asset in manifest["assets"] if asset["assetKey"] == "f16")
    assert f16["orientation"] == {
        "status": "VERIFIED_RENDER_FRONT_CORRECTION_R2",
        "frontViewCameraAxisSource": "+Y",
        "screenRightAxisSource": "-X",
        "screenUpAxisSource": "+Z",
        "longitudinalNoseAxisSource": "+Y",
        "sourceToPresentationRotation3x3": [
            [-1.0, 0.0, 0.0],
            [0.0, -1.0, 0.0],
            [0.0, 0.0, 1.0],
        ],
    }
    assert all(asset["scale"]["status"] == "VERIFIED" for asset in assets)
    assert all(asset["scale"]["factor"] == 1.0 for asset in assets)
    assert {
        asset["assetKey"]: asset["scale"]["targetLongestAxisMm"] for asset in assets
    } == {
        "drone": 374.986,
        "f16": 500.0,
        "helicopter": 582.673,
        "missile": 500.0,
    }
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
        (
            SYNTHETIC / "config/camera_profiles/camera_module_3_provisional.toml"
        ).read_text(encoding="utf-8")
    )
    scene = tomllib.loads(
        (
            SYNTHETIC / "config/scene_profiles/committee_tilted_targets_sweep_v1.toml"
        ).read_text(encoding="utf-8")
    )
    material = tomllib.loads(
        (SYNTHETIC / "config/material_profiles/nominal_colors.toml").read_text(
            encoding="utf-8"
        )
    )

    assert camera["status"] == "UNVERIFIED"
    assert camera["cameraHeightM"] == camera["targetReferenceHeightM"] == 1.30
    assert camera["runtimeResolution"] == [1280, 720]
    assert camera["modelInputResolution"] == [640, 640]
    assert camera["nativeSensorResolution"] == [4608, 2592]
    assert camera["highResolutionMainStream"] == [2304, 1296]
    assert camera["runtimeAcquisitionPath"] == (
        "DUAL_STREAM_SAHI_SEARCH_AND_SQUARE_TRACK_ROI"
    )
    assert camera["modelResizePolicy"] == "SQUARE_UNIFORM_RESIZE_NO_PADDING"
    assert camera["searchSliceSize"] == [768, 768]
    assert camera["searchOverlapRatio"] == [0.25, 0.25]
    assert camera["searchTileCount"] == 8
    assert camera["trackRoiSizesPx"] == [768, 960, 1152]
    assert camera["runtimeViewFamilies"] == [
        "SEARCH_SAHI_TILE_768",
        "TRACK_SQUARE_ROI",
    ]
    assert camera["researchOnlyViewFamilies"] == [
        "FULL_FRAME_LEGACY",
        "scaler_crop",
        "application_crop",
    ]
    assert camera["codecInInferencePath"] == "none"
    assert scene["longitudinalDistanceBucketsM"] == [
        float(value) for value in range(3, 18)
    ]
    assert scene["sideRouteLateralDistanceBucketsM"] == [2.75, 2.87, 3.0]
    assert scene["centerRouteLateralDistanceM"] == 0.0
    assert scene["yawComputation"] == "ATAN2_SIGNED_LATERAL_OVER_LONGITUDINAL"
    assert "viewYawBucketsDeg" not in scene
    assert scene["topSurfaceViewBucketsDeg"] == [
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
    ]
    assert scene["topSurfaceViewJitterDeg"] == 0.5
    assert scene["longitudinalDistanceJitterM"] == 0.0
    assert scene["lateralDistanceJitterM"] == 0.0
    assert [item["id"] for item in material["appearanceVariants"]] == scene[
        "appearanceProfileIds"
    ]
    assert [item["weight"] for item in material["appearanceVariants"]] == scene[
        "appearanceWeights"
    ]
    assert material["enemyHex"] == material["balloonHex"] == "#F50A0A"
    assert material["friendlyHex"] == "#00A3E0"


def test_render_record_schema_rejects_out_of_range_camera_pose() -> None:
    record = {
        "recordId": "REC-001",
        "worldId": "WORLD-001",
        "variantId": "ZOOM-1X",
        "groupId": "WORLD-001",
        "sourceKind": "synthetic_cad_pbr",
        "split": "train",
        "assetKey": "f16",
        "presentationClass": "dusman_f16_kirmizi",
        "cameraProfileId": "CAMERA_MODULE_3_PROVISIONAL_R1",
        "appearanceProfileId": "nominal",
        "routeId": "ROTA_2",
        "longitudinalDistanceM": 10.0,
        "lateralDistanceM": 0.0,
        "lateralDistanceBucketM": 0.0,
        "yawComputation": "ATAN2_SIGNED_LATERAL_OVER_LONGITUDINAL",
        "distanceM": 10.0,
        "targetPositionM": [0.0, 10.0, 1.3],
        "viewYawDeg": 0.0,
        "topSurfaceViewBucketDeg": 12.0,
        "topSurfaceViewDeg": 12.0,
        "targetRotationWorld3x3": [
            [1.0, 0.0, 0.0],
            [0.0, 1.0, 0.0],
            [0.0, 0.0, 1.0],
        ],
        "cameraElevationOffsetDeg": 0.0,
        "sceneGroundTruth": {
            "targetInstanceId": "TARGET-001",
            "eligibleStageIds": ["ASAMA_3"],
            "friendFoe": "Düşman",
            "balloon": {
                "instanceId": "BALLOON-001",
                "targetInstanceId": "TARGET-001",
                "diameterM": 0.14,
                "relativeCenterM": [0.0, 0.0, -0.4],
                "colorHex": "#F50A0A",
                "fireCandidateAllowed": True,
            },
        },
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
    record["sourceFrameId"] = "REC-001"
    record["inferenceView"] = {
        "viewFamily": "SEARCH_SAHI_TILE_768",
        "sourceResolution": [2304, 1296],
        "sliceRectFullFramePx": [0, 0, 768, 768],
        "roiRectFullFramePx": None,
        "sliceIndex": 0,
        "overlapWidthRatio": 0.25,
        "overlapHeightRatio": 0.25,
        "resizeScale": 640 / 768,
        "bboxFullFramePx": [100, 100, 50, 40],
        "bboxCropPx": [100, 100, 50, 40],
        "bboxModelPx": [83, 83, 42, 34],
        "visibleFraction": 1.0,
        "truncatedBySlice": False,
        "edgeDistancePx": 100,
        "modelInputResolution": [640, 640],
        "modelPaddingPx": [0, 0, 0, 0],
        "upsampledBeforeModel": False,
    }
    render_validator.validate(record)
    record["cameraElevationOffsetDeg"] = 4.0

    with pytest.raises(jsonschema.ValidationError):
        render_validator.validate(record)
