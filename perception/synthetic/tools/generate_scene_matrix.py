"""Generate deterministic, angle-filterable synthetic render plans."""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import tomllib
from pathlib import Path
from typing import Any

from pose_contract import target_position_world, target_rotation_world

SYNTHETIC_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PROFILE = SYNTHETIC_ROOT / "config/scene_profiles/committee_tilted_targets_sweep_v1.toml"
DEFAULT_ASSETS = SYNTHETIC_ROOT / "config/cad_asset_manifest.json"
DEFAULT_SOURCE = SYNTHETIC_ROOT / "config/cad_source.json"
DEFAULT_OUTPUT = SYNTHETIC_ROOT / "generated/render_plans/committee_tilt_sweep_v1.json"


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _jitter(rng: random.Random, center: float, radius: float) -> float:
    return center + rng.uniform(-radius, radius)


def _split_for(group_id: str) -> str:
    bucket = int(hashlib.sha256(group_id.encode()).hexdigest()[:8], 16) % 100
    return "train" if bucket < 80 else "val" if bucket < 90 else "test"


def _stable_id(parts: list[str]) -> str:
    return hashlib.sha256("|".join(parts).encode()).hexdigest()[:20]


def generate_render_plan(
    *,
    profile: dict[str, Any],
    asset_manifest: dict[str, Any],
    source_sha256: str,
    asset_manifest_sha256: str,
    seed: int,
    asset_keys: set[str] | None = None,
) -> dict[str, Any]:
    rng = random.Random(seed)
    records: list[dict[str, Any]] = []
    camera_height = float(profile["cameraPositionM"][2])

    for asset in sorted(asset_manifest["assets"], key=lambda value: value["assetKey"]):
        if asset_keys is not None and asset["assetKey"] not in asset_keys:
            continue
        for presentation_class in asset["presentationClasses"]:
            for distance in profile["distanceAnchorsM"]:
                for lateral_bucket in profile["lateralOffsetBucketsM"]:
                    for vertical_bucket in profile["verticalOffsetBucketsM"]:
                        for yaw_bucket in profile["viewYawBucketsDeg"]:
                            for tilt_bucket in profile["topSurfaceViewBucketsDeg"]:
                                lateral = _jitter(
                                    rng,
                                    float(lateral_bucket),
                                    float(profile["lateralOffsetJitterM"]),
                                )
                                vertical = _jitter(
                                    rng,
                                    float(vertical_bucket),
                                    float(profile["verticalOffsetJitterM"]),
                                )
                                yaw = _jitter(
                                    rng,
                                    float(yaw_bucket),
                                    float(profile["viewYawJitterDeg"]),
                                )
                                tilt = max(
                                    0.0,
                                    _jitter(
                                        rng,
                                        float(tilt_bucket),
                                        float(profile["topSurfaceViewJitterDeg"]),
                                    ),
                                )
                                world_key = [
                                    asset["assetKey"],
                                    presentation_class,
                                    f"d{distance:g}",
                                    f"x{lateral_bucket:+g}",
                                    f"z{vertical_bucket:+g}",
                                    f"yaw{yaw_bucket:+g}",
                                    f"tilt{tilt_bucket:g}",
                                ]
                                world_id = "WORLD-" + _stable_id(world_key)
                                record_id = "REC-" + _stable_id(world_key + [str(seed)])
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
                                        "cameraProfileId": "CAMERA_MODULE_3_PROVISIONAL_R1",
                                        "distanceM": float(distance),
                                        "targetPositionM": target_position_world(
                                            distance_m=float(distance),
                                            lateral_offset_m=lateral,
                                            vertical_offset_m=vertical,
                                            camera_height_m=camera_height,
                                        ),
                                        "viewYawBucketDeg": float(yaw_bucket),
                                        "viewYawDeg": round(yaw, 6),
                                        "topSurfaceViewBucketDeg": float(tilt_bucket),
                                        "topSurfaceViewDeg": round(tilt, 6),
                                        "targetRotationWorld3x3": target_rotation_world(
                                            view_yaw_deg=yaw,
                                            top_surface_view_deg=tilt,
                                        ),
                                        "cameraElevationOffsetDeg": 0.0,
                                        "zoom": {
                                            "mode": "none",
                                            "factor": 1.0,
                                            "cropRectPx": [0, 0, 1280, 720],
                                            "preCropResolution": [1280, 720],
                                            "postCropResolution": [1280, 720],
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
    print(json.dumps({"status": plan["status"], "records": len(plan["records"]), "output": str(args.output)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
