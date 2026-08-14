"""Generate SAHI search tiles or square tracking ROI derivatives from one render."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from apply_camera_pipeline import (
    CameraPipelineError,
    build_sahi_search_views,
    build_track_square_view,
    degrade_image,
)


def _record(base: dict[str, Any], metadata: dict[str, Any], index: int) -> dict[str, Any]:
    result = dict(base)
    key = f"{base['recordId']}|{metadata['viewFamily']}|{index}|{metadata}"
    result["sourceFrameId"] = base["recordId"]
    result["recordId"] = "REC-VIEW-" + hashlib.sha256(key.encode()).hexdigest()[:20]
    result["variantId"] = f"{base['presentationClass']}__{metadata['viewFamily']}__{index:02d}"
    result["inferenceView"] = metadata
    return result


def _write_view(output_dir: Path, view: dict[str, Any], record: dict[str, Any]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(output_dir / "image.png"), view["image"])
    cv2.imwrite(str(output_dir / "mask.png"), view["mask"])
    cv2.imwrite(str(output_dir / "model-input.png"), view["modelInput"])
    cv2.imwrite(str(output_dir / "model-mask.png"), view["modelMask"])
    (output_dir / "record.json").write_text(
        json.dumps(record, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", type=Path, required=True)
    parser.add_argument("--mask", type=Path, required=True)
    parser.add_argument("--record", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--family", choices=("search-sahi", "track-square"), required=True)
    parser.add_argument("--target-value", type=int)
    parser.add_argument("--roi-size", type=int, choices=(768, 960, 1152), default=768)
    parser.add_argument("--center-error-x", type=float, default=0.0)
    parser.add_argument("--center-error-y", type=float, default=0.0)
    parser.add_argument("--seed", type=int, default=260815)
    parser.add_argument("--blur-kernel", type=int, choices=(0, 3, 5), default=0)
    parser.add_argument("--noise-std", type=float, default=0.0)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    image = cv2.imread(str(args.image), cv2.IMREAD_COLOR)
    mask = cv2.imread(str(args.mask), cv2.IMREAD_UNCHANGED)
    if image is None or mask is None:
        raise CameraPipelineError("görüntü veya maske okunamadı")
    if mask.ndim != 2:
        raise CameraPipelineError("maske tek kanallı olmalı")
    if args.target_value is not None:
        mask = np.where(mask == args.target_value, 255, 0).astype(np.uint8)

    # Camera effects are applied once to the full frame before any slice/ROI.
    degraded = degrade_image(
        image,
        seed=args.seed,
        blur_kernel=args.blur_kernel,
        noise_std=args.noise_std,
    )
    if args.family == "search-sahi":
        views = build_sahi_search_views(degraded, mask)
    else:
        views = [
            build_track_square_view(
                degraded,
                mask,
                roi_size_px=args.roi_size,
                center_error_px=(args.center_error_x, args.center_error_y),
            )
        ]

    base = json.loads(args.record.read_text(encoding="utf-8"))
    manifest = []
    for index, view in enumerate(views):
        record = _record(base, view["metadata"], index)
        relative = Path(f"view-{index:02d}")
        _write_view(args.output_dir / relative, view, record)
        manifest.append(
            {
                "recordId": record["recordId"],
                "path": relative.as_posix(),
                "viewFamily": view["metadata"]["viewFamily"],
                "sliceIndex": view["metadata"].get("sliceIndex"),
            }
        )
    (args.output_dir / "manifest.json").write_text(
        json.dumps(
            {
                "status": "SYNTHETIC_RESEARCH_ONLY",
                "sourceFrameId": base["recordId"],
                "views": manifest,
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

