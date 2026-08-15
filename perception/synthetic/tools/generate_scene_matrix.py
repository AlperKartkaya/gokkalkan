"""Generate deterministic route-geometry synthetic render plans."""

from __future__ import annotations

import argparse
import hashlib
import json
import tomllib
from pathlib import Path
from typing import Any

from pose_contract import (
    euclidean_camera_range,
    route_view_yaw_deg,
    target_position_world,
    target_rotation_world,
)
from scene_contract import scene_ground_truth

SYNTHETIC_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PROFILE = (
    SYNTHETIC_ROOT / "config/scene_profiles/committee_tilted_targets_sweep_v1.toml"
)
DEFAULT_ASSETS = SYNTHETIC_ROOT / "config/cad_asset_manifest.json"
DEFAULT_SOURCE = SYNTHETIC_ROOT / "config/cad_source.json"
DEFAULT_OUTPUT = SYNTHETIC_ROOT / "generated/render_plans/committee_tilt_sweep_v1.json"


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _jitter(parts: list[str], center: float, radius: float) -> float:
    unit = int(hashlib.sha256("|".join(parts).encode()).hexdigest()[:12], 16) / float(
        16**12
    )
    return center + (unit * 2.0 - 1.0) * radius


def _split_for(group_id: str) -> str:
    bucket = int(hashlib.sha256(group_id.encode()).hexdigest()[:8], 16) % 100
    # Synthetic CAD never occupies the release test split. Real, session-separated
    # captures are the only acceptable test evidence.
    return "train" if bucket < 85 else "val"


def _stable_id(parts: list[str]) -> str:
    return hashlib.sha256("|".join(parts).encode()).hexdigest()[:20]


def _route_samples(profile: dict[str, Any]) -> list[tuple[str, float]]:
    side = [float(value) for value in profile["sideRouteLateralDistanceBucketsM"]]
    center = float(profile["centerRouteLateralDistanceM"])
    return [
        *(("ROTA_1", value) for value in side),
        ("ROTA_2", center),
        *(("ROTA_3", -value) for value in side),
    ]


def _appearance_for(key: list[str], profile: dict[str, Any]) -> str:
    ids = list(profile["appearanceProfileIds"])
    weights = [float(weight) for weight in profile["appearanceWeights"]]
    if len(ids) != len(weights) or not ids or not abs(sum(weights) - 1.0) < 1e-9:
        raise ValueError("appearance profili kimlikleri ve ağırlıkları geçersiz")

    sample = int(hashlib.sha256("|".join(key).encode()).hexdigest()[:12], 16) / float(
        16**12
    )
    cumulative = 0.0
    for profile_id, weight in zip(ids, weights, strict=True):
        cumulative += weight
        if sample < cumulative:
            return profile_id
    return ids[-1]


def generate_render_plan(
    *,
    profile: dict[str, Any],
    asset_manifest: dict[str, Any],
    source_sha256: str,
    asset_manifest_sha256: str,
    seed: int,
    asset_keys: set[str] | None = None,
) -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    camera_height = float(profile["cameraPositionM"][2])

    for asset in sorted(asset_manifest["assets"], key=lambda value: value["assetKey"]):
        if asset_keys is not None and asset["assetKey"] not in asset_keys:
            continue
        for presentation_class in asset["presentationClasses"]:
            for longitudinal_bucket in profile["longitudinalDistanceBucketsM"]:
                for route_id, lateral_bucket in _route_samples(profile):
                    for tilt_bucket in profile["topSurfaceViewBucketsDeg"]:
                        world_key = [
                            asset["assetKey"],
                            presentation_class,
                            route_id,
                            f"long{longitudinal_bucket:g}",
                            f"lat{lateral_bucket:+g}",
                            f"tilt{tilt_bucket:g}",
                        ]
                        seed_key = world_key + [str(seed)]
                        longitudinal = _jitter(
                            seed_key + ["longitudinal"],
                            float(longitudinal_bucket),
                            float(profile["longitudinalDistanceJitterM"]),
                        )
                        lateral = _jitter(
                            seed_key + ["lateral"],
                            float(lateral_bucket),
                            float(profile["lateralDistanceJitterM"]),
                        )
                        tilt = _jitter(
                            seed_key + ["tilt"],
                            float(tilt_bucket),
                            float(profile["topSurfaceViewJitterDeg"]),
                        )
                        position = target_position_world(
                            longitudinal_distance_m=longitudinal,
                            signed_lateral_distance_m=lateral,
                            vertical_offset_m=float(profile["verticalOffsetM"]),
                            camera_height_m=camera_height,
                        )
                        yaw = route_view_yaw_deg(
                            longitudinal_distance_m=longitudinal,
                            signed_lateral_distance_m=lateral,
                        )
                        world_id = "WORLD-" + _stable_id(world_key)
                        record_id = "REC-" + _stable_id(seed_key)
                        records.append(
                            {
                                "recordId": record_id,
                                "worldId": world_id,
                                "variantId": presentation_class,
                                "groupId": world_id,
                                "sourceKind": "synthetic_cad_pbr",
                                "split": _split_for(world_id),
                                "assetKey": asset["assetKey"],
                                "presentationClass": presentation_class,
                                "appearanceProfileId": _appearance_for(
                                    world_key, profile
                                ),
                                "cameraProfileId": "CAMERA_MODULE_3_PROVISIONAL_R1",
                                "routeId": route_id,
                                "longitudinalDistanceM": round(longitudinal, 6),
                                "lateralDistanceM": round(lateral, 6),
                                "lateralDistanceBucketM": float(lateral_bucket),
                                "yawComputation": profile["yawComputation"],
                                "distanceM": round(
                                    euclidean_camera_range(
                                        position, camera_height_m=camera_height
                                    ),
                                    6,
                                ),
                                "targetPositionM": position,
                                "viewYawDeg": round(yaw, 6),
                                "topSurfaceViewBucketDeg": float(tilt_bucket),
                                "topSurfaceViewDeg": round(tilt, 6),
                                "targetRotationWorld3x3": target_rotation_world(
                                    top_surface_view_deg=tilt,
                                ),
                                "cameraElevationOffsetDeg": float(
                                    profile["cameraElevationOffsetDeg"]
                                ),
                                "sceneGroundTruth": scene_ground_truth(
                                    world_id=world_id,
                                    presentation_class=presentation_class,
                                ),
                                "zoom": {
                                    "mode": "none",
                                    "factor": 1.0,
                                    "cropRectPx": [0, 0, 2304, 1296],
                                    "preCropResolution": [2304, 1296],
                                    "postCropResolution": [2304, 1296],
                                    "modelInputResolution": [640, 640],
                                    "interpolation": "INTER_AREA",
                                    "targetPixelsBeforeZoom": 0,
                                    "targetPixelsAfterZoom": 0,
                                    "zoomCenterErrorPx": [0.0, 0.0],
                                },
                            }
                        )

    return {
        "schemaVersion": 1,
        "batchId": f"{profile['profileId']}-SEED-{seed}",
        "status": "SYNTHETIC_RENDER_PLAN",
        "sourceCadSha256": source_sha256,
        "assetManifestSha256": asset_manifest_sha256,
        "renderer": {
            "blenderProcVersion": "2.8.0",
            "blenderVersion": "4.2.1",
            "seed": seed,
        },
        "records": records,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", type=Path, default=DEFAULT_PROFILE)
    parser.add_argument("--asset-manifest", type=Path, default=DEFAULT_ASSETS)
    parser.add_argument("--source-config", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--seed", type=int, default=260814)
    parser.add_argument("--asset", action="append", dest="assets")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    profile = tomllib.loads(args.profile.read_text(encoding="utf-8"))
    assets = _load_json(args.asset_manifest)
    source = _load_json(args.source_config)
    plan = generate_render_plan(
        profile=profile,
        asset_manifest=assets,
        source_sha256=source["expectedSha256"],
        asset_manifest_sha256=_sha256(args.asset_manifest),
        seed=args.seed,
        asset_keys=set(args.assets) if args.assets else None,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(plan, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "status": plan["status"],
                "records": len(plan["records"]),
                "output": str(args.output),
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
