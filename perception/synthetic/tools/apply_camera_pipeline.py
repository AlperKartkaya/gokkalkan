"""Apply deterministic digital zoom and camera degradation to a render.

``high_res_roi`` crops the high-resolution main stream and sends that crop
directly to aspect-preserving model letterboxing. ``scaler_crop`` approximates
Picamera2's sensor-coordinate ScalerCrop followed by ISP scaling.
``application_crop`` is the deliberately inferior low-resolution baseline.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
from typing import Any

import cv2
import numpy as np


class CameraPipelineError(ValueError):
    """Raised for invalid crop or image contracts."""


def crop_rect(
    *,
    width: int,
    height: int,
    factor: float,
    center_error_px: tuple[float, float] = (0.0, 0.0),
) -> tuple[int, int, int, int]:
    if factor < 1.0:
        raise CameraPipelineError("zoom faktörü 1.0 veya daha büyük olmalı")
    crop_width = max(1, round(width / factor))
    crop_height = max(1, round(height / factor))
    center_x = width / 2 + center_error_px[0]
    center_y = height / 2 + center_error_px[1]
    left = round(center_x - crop_width / 2)
    top = round(center_y - crop_height / 2)
    left = min(max(0, left), width - crop_width)
    top = min(max(0, top), height - crop_height)
    return left, top, crop_width, crop_height


def _crop_and_resize(
    image: np.ndarray,
    rect: tuple[int, int, int, int],
    output_size: tuple[int, int],
    *,
    interpolation: int,
) -> np.ndarray:
    left, top, width, height = rect
    cropped = image[top : top + height, left : left + width]
    if cropped.size == 0:
        raise CameraPipelineError("zoom crop görüntü sınırları dışında kaldı")
    return cv2.resize(cropped, output_size, interpolation=interpolation)


def apply_zoom(
    image: np.ndarray,
    *,
    mode: str,
    factor: float,
    runtime_size: tuple[int, int] = (1280, 720),
    center_error_px: tuple[float, float] = (0.0, 0.0),
    is_mask: bool = False,
) -> tuple[np.ndarray, dict[str, Any]]:
    if image.ndim not in (2, 3):
        raise CameraPipelineError("görüntü 2B maske veya 3B renk dizisi olmalı")
    if mode not in {
        "none",
        "high_res_roi",
        "scaler_crop",
        "sensor_roi",
        "application_crop",
    }:
        raise CameraPipelineError(f"bilinmeyen zoom modu: {mode}")
    source_height, source_width = image.shape[:2]
    interpolation = cv2.INTER_NEAREST if is_mask else cv2.INTER_AREA

    if mode == "none" or factor == 1.0:
        rect = (0, 0, source_width, source_height)
        output = cv2.resize(image, runtime_size, interpolation=interpolation)
        effective_mode = "none"
    elif mode == "high_res_roi":
        rect = crop_rect(
            width=source_width,
            height=source_height,
            factor=factor,
            center_error_px=center_error_px,
        )
        left, top, crop_width, crop_height = rect
        output = image[top : top + crop_height, left : left + crop_width].copy()
        effective_mode = mode
        pre_crop_resolution = [source_width, source_height]
    elif mode in {"scaler_crop", "sensor_roi"}:
        rect = crop_rect(
            width=source_width,
            height=source_height,
            factor=factor,
            center_error_px=center_error_px,
        )
        output = _crop_and_resize(
            image, rect, runtime_size, interpolation=interpolation
        )
        effective_mode = "scaler_crop"
        pre_crop_resolution = [source_width, source_height]
    else:
        runtime = cv2.resize(image, runtime_size, interpolation=interpolation)
        rect = crop_rect(
            width=runtime_size[0],
            height=runtime_size[1],
            factor=factor,
            center_error_px=center_error_px,
        )
        output = _crop_and_resize(
            runtime, rect, runtime_size, interpolation=interpolation
        )
        effective_mode = mode
        pre_crop_resolution = list(runtime_size)

    if mode == "none" or factor == 1.0:
        pre_crop_resolution = [source_width, source_height]

    return output, {
        "mode": effective_mode,
        "factor": float(factor),
        "cropRectPx": list(rect),
        "preCropResolution": pre_crop_resolution,
        "postCropResolution": [output.shape[1], output.shape[0]],
        "interpolation": (
            "NONE"
            if effective_mode == "high_res_roi"
            else "INTER_NEAREST"
            if is_mask
            else "INTER_AREA"
        ),
        "zoomCenterErrorPx": [float(value) for value in center_error_px],
        "acquisitionPath": {
            "none": "FULL_FOV_LORES",
            "high_res_roi": "FULL_FOV_HIGH_RES_MAIN_SOFTWARE_CROP",
            "scaler_crop": "PICAMERA2_SCALER_CROP_PROXY",
            "application_crop": "LOW_RESOLUTION_APPLICATION_BASELINE",
        }[effective_mode],
    }


def letterbox(
    image: np.ndarray,
    *,
    output_size: tuple[int, int] = (640, 640),
    is_mask: bool = False,
) -> tuple[np.ndarray, dict[str, Any]]:
    """Resize without distortion and pad to the fixed model tensor."""

    source_height, source_width = image.shape[:2]
    output_width, output_height = output_size
    scale = min(output_width / source_width, output_height / source_height)
    content_width = max(1, round(source_width * scale))
    content_height = max(1, round(source_height * scale))
    interpolation = cv2.INTER_NEAREST if is_mask else cv2.INTER_AREA
    resized = cv2.resize(
        image, (content_width, content_height), interpolation=interpolation
    )
    left = (output_width - content_width) // 2
    top = (output_height - content_height) // 2
    if image.ndim == 2:
        output = np.zeros((output_height, output_width), dtype=image.dtype)
    else:
        output = np.zeros(
            (output_height, output_width, image.shape[2]), dtype=image.dtype
        )
    output[top : top + content_height, left : left + content_width] = resized
    return output, {
        "modelContentRectPx": [left, top, content_width, content_height],
        "modelScale": float(scale),
        "modelPaddingPx": [
            left,
            top,
            output_width - left - content_width,
            output_height - top - content_height,
        ],
        "upsampledBeforeModel": scale > 1.0,
    }


def degrade_image(
    image: np.ndarray,
    *,
    seed: int,
    blur_kernel: int = 0,
    noise_std: float = 0.0,
    jpeg_quality: int | None = None,
) -> np.ndarray:
    if blur_kernel not in {0, 3, 5}:
        raise CameraPipelineError("blur kernel yalnız 0, 3 veya 5 olabilir")
    if not 0 <= noise_std <= 20:
        raise CameraPipelineError("noise_std [0, 20] aralığında olmalı")
    if jpeg_quality is not None and not 40 <= jpeg_quality <= 100:
        raise CameraPipelineError("JPEG kalitesi [40, 100] aralığında olmalı")

    result = image.copy()
    if blur_kernel:
        result = cv2.GaussianBlur(result, (blur_kernel, blur_kernel), 0)
    if noise_std:
        rng = np.random.default_rng(seed)
        noise = rng.normal(0.0, noise_std, result.shape)
        result = np.clip(result.astype(np.float32) + noise, 0, 255).astype(np.uint8)
    if jpeg_quality is None:
        return result
    encoded, buffer = cv2.imencode(
        ".jpg", result, [cv2.IMWRITE_JPEG_QUALITY, jpeg_quality]
    )
    if not encoded:
        raise CameraPipelineError("JPEG sıkıştırma başarısız")
    decoded = cv2.imdecode(buffer, cv2.IMREAD_COLOR)
    if decoded is None:
        raise CameraPipelineError("JPEG tekrar okuma başarısız")
    return decoded


def bbox_from_mask(mask: np.ndarray) -> tuple[int, int, int, int] | None:
    binary = mask > 0
    if not binary.any():
        return None
    rows, columns = np.where(binary)
    left, right = int(columns.min()), int(columns.max())
    top, bottom = int(rows.min()), int(rows.max())
    return left, top, right - left + 1, bottom - top + 1


def build_variant_record(
    base_record: dict[str, Any],
    *,
    zoom_metadata: dict[str, Any],
    before_mask: np.ndarray,
    after_mask: np.ndarray,
) -> dict[str, Any]:
    record = copy.deepcopy(base_record)
    variant_key = (
        f"{base_record['recordId']}|{zoom_metadata['mode']}|"
        f"{zoom_metadata['factor']}|{zoom_metadata['zoomCenterErrorPx']}"
    )
    record["recordId"] = (
        "REC-ZOOM-" + hashlib.sha256(variant_key.encode()).hexdigest()[:20]
    )
    record["variantId"] = (
        f"{base_record['presentationClass']}__{zoom_metadata['mode']}__"
        f"{zoom_metadata['factor']:g}x"
    )
    before_bbox = bbox_from_mask(before_mask)
    after_bbox = bbox_from_mask(after_mask)
    record["zoom"] = {
        **zoom_metadata,
        "modelInputResolution": [640, 640],
        "targetPixelsBeforeZoom": int(np.count_nonzero(before_mask)),
        "targetPixelsAfterZoom": int(np.count_nonzero(after_mask)),
    }
    record["annotation"] = {
        "bboxBeforeZoomPx": list(before_bbox) if before_bbox else None,
        "bboxAfterZoomPx": list(after_bbox) if after_bbox else None,
        "targetVisibleAfterZoom": after_bbox is not None,
    }
    return record


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", type=Path, required=True)
    parser.add_argument("--mask", type=Path, required=True)
    parser.add_argument(
        "--target-value",
        type=int,
        default=None,
        help="Etiket maskesinde hedefi temsil eden piksel değeri",
    )
    parser.add_argument("--record", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--mode",
        choices=("none", "high_res_roi", "scaler_crop", "application_crop"),
        required=True,
    )
    parser.add_argument(
        "--factor", type=float, choices=(1.0, 1.5, 2.0, 3.0), required=True
    )
    parser.add_argument("--center-error-x", type=float, default=0.0)
    parser.add_argument("--center-error-y", type=float, default=0.0)
    parser.add_argument("--seed", type=int, default=260814)
    parser.add_argument("--blur-kernel", type=int, choices=(0, 3, 5), default=0)
    parser.add_argument("--noise-std", type=float, default=0.0)
    parser.add_argument("--jpeg-quality", type=int)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    image = cv2.imread(str(args.image), cv2.IMREAD_COLOR)
    mask = cv2.imread(str(args.mask), cv2.IMREAD_UNCHANGED)
    if image is None or mask is None:
        raise CameraPipelineError("görüntü veya maske okunamadı")
    if mask.ndim != 2:
        raise CameraPipelineError(
            "maske ham tek kanallı etiket görüntüsü olmalı; renkli görselleştirme kullanmayın"
        )
    if args.target_value is not None:
        mask = np.where(mask == args.target_value, 255, 0).astype(np.uint8)
    center_error = (args.center_error_x, args.center_error_y)
    zoomed, zoom_meta = apply_zoom(
        image,
        mode=args.mode,
        factor=args.factor,
        center_error_px=center_error,
    )
    zoomed_mask, _ = apply_zoom(
        mask,
        mode=args.mode,
        factor=args.factor,
        center_error_px=center_error,
        is_mask=True,
    )
    baseline_mask, _ = apply_zoom(
        mask,
        mode="none",
        factor=1.0,
        is_mask=True,
    )
    baseline_model_mask, _ = letterbox(baseline_mask, is_mask=True)
    degraded = degrade_image(
        zoomed,
        seed=args.seed,
        blur_kernel=args.blur_kernel,
        noise_std=args.noise_std,
        jpeg_quality=args.jpeg_quality,
    )
    model_input, letterbox_meta = letterbox(degraded)
    model_mask, _ = letterbox(zoomed_mask, is_mask=True)
    zoom_meta.update(letterbox_meta)
    zoom_meta["cameraDegradation"] = {
        "profileStatus": (
            "IDEAL_NO_MEASURED_CAMERA_DEGRADATION"
            if args.blur_kernel == 0
            and args.noise_std == 0
            and args.jpeg_quality is None
            else "PROVISIONAL_RESEARCH_SWEEP"
        ),
        "blurKernel": args.blur_kernel,
        "noiseStd": args.noise_std,
        "codec": "none" if args.jpeg_quality is None else "jpeg",
        "jpegQuality": args.jpeg_quality,
        "seed": args.seed,
    }
    record = json.loads(args.record.read_text(encoding="utf-8"))
    variant = build_variant_record(
        record,
        zoom_metadata=zoom_meta,
        before_mask=baseline_model_mask,
        after_mask=model_mask,
    )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(args.output_dir / "image.png"), degraded)
    cv2.imwrite(str(args.output_dir / "mask.png"), zoomed_mask)
    cv2.imwrite(str(args.output_dir / "model-input.png"), model_input)
    cv2.imwrite(str(args.output_dir / "model-mask.png"), model_mask)
    (args.output_dir / "record.json").write_text(
        json.dumps(variant, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
