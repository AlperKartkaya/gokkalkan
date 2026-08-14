"""Validate LOD silhouette and bounding-box stability in six canonical views."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import cv2
import numpy as np

VIEWS = {
    "front": (0, 2),
    "back": (0, 2),
    "right": (1, 2),
    "left": (1, 2),
    "top": (0, 1),
    "bottom": (0, 1),
}


def rasterize(
    vertices: np.ndarray,
    faces: np.ndarray,
    *,
    axes: tuple[int, int],
    reference_min: np.ndarray,
    reference_scale: float,
    width: int = 1280,
    height: int = 720,
) -> np.ndarray:
    projected = vertices[:, axes]
    pixels = np.empty_like(projected, dtype=np.float64)
    pixels[:, 0] = (projected[:, 0] - reference_min[0]) * reference_scale + 40
    pixels[:, 1] = height - ((projected[:, 1] - reference_min[1]) * reference_scale + 40)
    polygons = np.rint(pixels[faces]).astype(np.int32)
    mask = np.zeros((height, width), dtype=np.uint8)
    cv2.fillPoly(mask, polygons, 255)
    return mask


def bbox(mask: np.ndarray) -> tuple[int, int, int, int]:
    ys, xs = np.nonzero(mask)
    return int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())


def validate_pair(
    reference_vertices: np.ndarray,
    reference_faces: np.ndarray,
    candidate_vertices: np.ndarray,
    candidate_faces: np.ndarray,
) -> list[dict[str, Any]]:
    results = []
    for name, axes in VIEWS.items():
        projected = reference_vertices[:, axes]
        minimum = projected.min(axis=0)
        span = np.maximum(projected.max(axis=0) - minimum, 1e-9)
        scale = min((1280 - 80) / span[0], (720 - 80) / span[1])
        reference = rasterize(
            reference_vertices,
            reference_faces,
            axes=axes,
            reference_min=minimum,
            reference_scale=scale,
        )
        candidate = rasterize(
            candidate_vertices,
            candidate_faces,
            axes=axes,
            reference_min=minimum,
            reference_scale=scale,
        )
        intersection = np.count_nonzero(reference & candidate)
        union = np.count_nonzero(reference | candidate)
        reference_bbox, candidate_bbox = bbox(reference), bbox(candidate)
        results.append(
            {
                "view": name,
                "silhouetteIoU": round(intersection / union, 6),
                "maxBboxEdgeDifferencePx": max(
                    abs(left - right)
                    for left, right in zip(reference_bbox, candidate_bbox, strict=True)
                ),
            }
        )
    return results


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--assets-root",
        type=Path,
        default=Path("perception/synthetic/generated/normalized_assets"),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    manifest = json.loads((args.assets_root / "manifest.json").read_text(encoding="utf-8"))
    report = {"schemaVersion": 1, "assets": []}
    failed = False
    for asset_key in sorted({record["assetKey"] for record in manifest["assets"]}):
        root = args.assets_root / asset_key
        reference_vertices = np.load(root / "lod0/vertices_m.npy", allow_pickle=False)
        reference_faces = np.load(root / "lod0/faces.npy", allow_pickle=False)
        for lod in ("lod1", "lod2"):
            results = validate_pair(
                reference_vertices,
                reference_faces,
                np.load(root / lod / "vertices_m.npy", allow_pickle=False),
                np.load(root / lod / "faces.npy", allow_pickle=False),
            )
            accepted = all(
                result["silhouetteIoU"] >= 0.98
                and result["maxBboxEdgeDifferencePx"] <= 2
                for result in results
            )
            failed |= not accepted
            report["assets"].append(
                {"assetKey": asset_key, "lod": lod.upper(), "accepted": accepted, "views": results}
            )
    report["status"] = "PASS" if not failed else "FAIL"
    output = args.assets_root / "lod_validation.json"
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": report["status"], "output": str(output)}))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
