#!/usr/bin/env python3
"""Gökkalkan target dataset preparation pipeline.

Produces reproducible synthetic YOLO data from canonical page-14 assets and
pulls future real Camera Module 3 captures from a class/session inbox. Physical
captures are never deleted and uncertain auto-labels fail closed.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor
import hashlib
import json
import math
import multiprocessing
import os
import random
import shutil
import sys
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = ROOT / "perception/dataset/config.json"
DEFAULT_ASSET_MANIFEST = ROOT / "perception/assets/target_prints/manifest.json"
DEFAULT_DROP = ROOT / "perception/dataset/captures/drop"
DEFAULT_STORE = ROOT / "perception/dataset/captures/store"
DEFAULT_OUTPUT = ROOT / "perception/dataset/generated/yolo_current"
DEFAULT_CAD_BATCH_ROOT = ROOT / "perception/synthetic/generated/render_batches"
DEFAULT_CAD_OUTPUT = ROOT / "perception/dataset/generated/yolo_cad_research"
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png"}
CAD_BASE_RESOLUTION = (2304, 1296)
MODEL_INPUT_RESOLUTION = (640, 640)
SEARCH_TILE_SIZE = 768
SEARCH_TILE_OVERLAP = (0.25, 0.25)
TRACK_ROI_SIZES = (768, 960, 1152)


class PipelineError(RuntimeError):
    pass


def _cv() -> tuple[Any, Any]:
    try:
        import cv2  # type: ignore
        import numpy as np  # type: ignore
    except ImportError as exc:
        raise PipelineError(
            "Dataset pipeline NumPy ve OpenCV gerektirir. "
            "Python 3.11/3.13 ortamında `python -m pip install -r "
            "requirements/perception-dev.lock` çalıştırın."
        ) from exc
    return cv2, np


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PipelineError(f"JSON okunamadı: {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise PipelineError(f"JSON nesne olmalıdır: {path}")
    return value


def atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def stable_split(group_id: str, percentages: dict[str, int]) -> str:
    total = sum(percentages.values())
    if total != 100:
        raise PipelineError("realSplitPercent toplamı 100 olmalıdır")
    bucket = int(hashlib.sha256(group_id.encode()).hexdigest()[:8], 16) % 100
    if bucket < percentages["train"]:
        return "train"
    if bucket < percentages["train"] + percentages["val"]:
        return "val"
    return "test"


def safe_component(value: str, field: str) -> str:
    if not value or Path(value).name != value or value in {".", ".."}:
        raise PipelineError(f"Güvensiz {field}: {value!r}")
    return value


def yolo_line(class_id: int, bbox: tuple[int, int, int, int], width: int, height: int) -> str:
    x, y, w, h = bbox
    return f"{class_id} {(x + w / 2) / width:.6f} {(y + h / 2) / height:.6f} {w / width:.6f} {h / height:.6f}"


def _asset_class_name(asset: dict[str, Any]) -> str:
    mapping = {
        "Düşman Drone": "dusman_drone_kirmizi",
        "Düşman Helikopter": "dusman_helikopter_kirmizi",
        "Düşman F16": "dusman_f16_kirmizi",
        "Düşman Füze": "dusman_fuze_kirmizi",
        "Dost Helikopter": "dost_helikopter_camgobegi",
        "Dost F16": "dost_f16_camgobegi",
    }
    try:
        return mapping[str(asset["presentationClass"])]
    except KeyError as exc:
        raise PipelineError(f"Bilinmeyen presentationClass: {asset.get('presentationClass')}") from exc


def _ensure_layout(output: Path) -> None:
    for split in ("train", "val", "test"):
        (output / "images" / split).mkdir(parents=True, exist_ok=True)
        (output / "labels" / split).mkdir(parents=True, exist_ok=True)
    (output / "metadata").mkdir(parents=True, exist_ok=True)


def _black_curtain_background(np: Any, rng: random.Random, size: tuple[int, int]) -> Any:
    width, height = size
    x = np.arange(width, dtype=np.float32)
    folds = np.zeros(width, dtype=np.float32)
    for _ in range(rng.randint(2, 6)):
        period = rng.uniform(35.0, 140.0)
        phase = rng.uniform(0.0, math.tau)
        folds += np.sin(x / period * math.tau + phase) * rng.uniform(2.0, 7.0)
    base = rng.uniform(2.0, 12.0) + folds
    image = np.repeat(base[np.newaxis, :, np.newaxis], height, axis=0)
    image = np.repeat(image, 3, axis=2)
    return np.clip(image, 0, 28).astype(np.uint8)


def _target_mask(cv2: Any, image: Any) -> Any:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    return cv2.threshold(gray, 8, 255, cv2.THRESH_BINARY)[1]


def _compose_synthetic(
    cv2: Any,
    np: Any,
    source: Any,
    rng: random.Random,
    config: dict[str, Any],
    include_balloon: bool,
) -> tuple[Any, tuple[int, int, int, int], tuple[int, int, int, int] | None, dict[str, Any]]:
    width, height = map(int, config["imageSize"])
    background = _black_curtain_background(np, rng, (width, height))
    mask = _target_mask(cv2, source)
    x, y, w, h = cv2.boundingRect(mask)
    source = source[y : y + h, x : x + w]
    mask = mask[y : y + h, x : x + w]

    distance = rng.uniform(*map(float, config["distanceMeters"]))
    # Perspective-consistent trend, clipped so near samples do not fill the frame.
    nominal = int(max(24, min(width * 0.72, width * 0.52 / max(1.0, distance / 3.0))))
    nominal = int(nominal * rng.uniform(0.85, 1.15))
    scale = nominal / max(w, h)
    resized = cv2.resize(source, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA if scale < 1 else cv2.INTER_CUBIC)
    resized_mask = cv2.resize(mask, (resized.shape[1], resized.shape[0]), interpolation=cv2.INTER_NEAREST)

    yaw = rng.uniform(*map(float, config["yawDegrees"]))
    incline = rng.uniform(*map(float, config["inclineDegrees"]))
    shrink = max(0.58, math.cos(math.radians(yaw)))
    dst_w, dst_h = resized.shape[1], resized.shape[0]
    src_pts = np.float32([[0, 0], [dst_w - 1, 0], [dst_w - 1, dst_h - 1], [0, dst_h - 1]])
    top_shift = math.tan(math.radians(incline)) * dst_h * 0.15
    side = (1.0 - shrink) * dst_w / 2
    dst_pts = np.float32([[side, max(0, top_shift)], [dst_w - side - 1, max(0, -top_shift)], [dst_w - 1, dst_h - 1], [0, dst_h - 1]])
    transform = cv2.getPerspectiveTransform(src_pts, dst_pts)
    warped = cv2.warpPerspective(resized, transform, (dst_w, dst_h), borderValue=(0, 0, 0))
    warped_mask = cv2.warpPerspective(resized_mask, transform, (dst_w, dst_h), flags=cv2.INTER_NEAREST, borderValue=0)

    tx = rng.randint(10, max(10, width - dst_w - 10)) if dst_w < width - 20 else 0
    max_ty = max(10, height - dst_h - (65 if include_balloon else 10))
    ty = rng.randint(10, max_ty) if max_ty >= 10 else 0
    roi = background[ty : ty + dst_h, tx : tx + dst_w]
    alpha = (warped_mask.astype(np.float32) / 255.0)[..., None]
    roi[:] = (warped * alpha + roi * (1.0 - alpha)).astype(np.uint8)
    bbox = (tx, ty, dst_w, dst_h)

    balloon_bbox = None
    if include_balloon:
        radius = max(5, int(dst_w * rng.uniform(0.08, 0.13)))
        cx = max(radius, min(width - radius - 1, tx + dst_w // 2 + rng.randint(-max(1, dst_w // 12), max(1, dst_w // 12))))
        cy = min(height - radius - 1, ty + dst_h + radius + rng.randint(4, 18))
        cv2.line(background, (cx, ty + dst_h), (cx, cy - radius), (38, 38, 38), 2)
        cv2.circle(background, (cx, cy), radius, (10, 10, 245), -1)  # RGB #F50A0A in BGR
        cv2.circle(background, (cx - radius // 3, cy - radius // 3), max(1, radius // 5), (80, 80, 255), -1)
        balloon_bbox = (cx - radius, cy - radius, radius * 2, radius * 2)

    brightness = rng.uniform(*map(float, config["brightnessFactor"]))
    background = np.clip(background.astype(np.float32) * brightness, 0, 255).astype(np.uint8)
    blur = rng.choice(list(map(int, config["blurKernelChoices"])))
    if blur:
        background = cv2.GaussianBlur(background, (blur, blur), 0)
    noise_std = rng.uniform(*map(float, config["gaussianNoiseStd"]))
    if noise_std > 0:
        noise = np.random.default_rng(rng.randrange(2**32)).normal(0, noise_std, background.shape)
        background = np.clip(background.astype(np.float32) + noise, 0, 255).astype(np.uint8)
    metadata = {"distanceMeters": round(distance, 3), "yawDegrees": round(yaw, 3), "inclineDegrees": round(incline, 3), "brightnessFactor": round(brightness, 3), "blurKernel": blur, "noiseStd": round(noise_std, 3)}
    return background, bbox, balloon_bbox, metadata


def generate_synthetic(config_path: Path, asset_manifest_path: Path, output: Path) -> dict[str, Any]:
    cv2, np = _cv()
    config = load_json(config_path)
    manifest = load_json(asset_manifest_path)
    rng = random.Random(int(config["randomSeed"]))
    classes = list(config["classes"])
    _ensure_layout(output)
    records: list[dict[str, Any]] = []
    asset_root = asset_manifest_path.parent
    count = int(config["syntheticSamplesPerPresentationClass"])
    # Every tenth derivative forms a provisional smoke-validation set. It shares
    # a base asset with train and therefore is never release-grade validation;
    # real capture sessions replace this role when they arrive.
    for asset in manifest.get("assets", []):
        class_name = _asset_class_name(asset)
        class_id = classes.index(class_name)
        source_path = asset_root / str(asset["blackBackground"])
        if sha256(source_path) != asset["blackBackgroundSha256"]:
            raise PipelineError(f"Seed hash uyuşmuyor: {source_path}")
        source = cv2.imread(str(source_path), cv2.IMREAD_COLOR)
        if source is None:
            raise PipelineError(f"Seed açılamadı: {source_path}")
        for index in range(count):
            image, target_bbox, balloon_bbox, meta = _compose_synthetic(cv2, np, source, rng, config, include_balloon=True)
            stem = f"syn_{class_id}_{index:04d}"
            split = "val" if index % 10 == 0 else "train"
            image_path = output / "images" / split / f"{stem}.jpg"
            quality = rng.randint(*map(int, config["jpegQuality"]))
            cv2.imwrite(str(image_path), image, [cv2.IMWRITE_JPEG_QUALITY, quality])
            lines = [yolo_line(class_id, target_bbox, image.shape[1], image.shape[0])]
            if balloon_bbox:
                lines.append(yolo_line(classes.index("balon"), balloon_bbox, image.shape[1], image.shape[0]))
            (output / "labels" / split / f"{stem}.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
            records.append({"id": stem, "sourceKind": "synthetic", "split": split, "presentationClass": class_name, "sourceAssetSha256": asset["blackBackgroundSha256"], "imageSha256": sha256(image_path), "jpegQuality": quality, "targetBalloonLinked": True, **meta})
    for index in range(int(config["syntheticNegativeSamples"])):
        image = _black_curtain_background(np, rng, tuple(map(int, config["imageSize"])))
        stem = f"syn_negative_{index:04d}"
        split = "val" if index % 8 == 0 else "train"
        image_path = output / "images" / split / f"{stem}.jpg"
        cv2.imwrite(str(image_path), image, [cv2.IMWRITE_JPEG_QUALITY, 88])
        (output / "labels" / split / f"{stem}.txt").write_text("", encoding="utf-8")
        records.append({"id": stem, "sourceKind": "synthetic-negative", "split": split, "imageSha256": sha256(image_path)})
    return {"records": records, "syntheticCount": len(records)}


def iter_capture_images(source: Path) -> Iterable[tuple[Path, Path, str, str]]:
    if not source.exists():
        return
    for session in sorted(p for p in source.iterdir() if p.is_dir()):
        session_meta = session / "session.json"
        if not session_meta.is_file():
            continue
        session_id = safe_component(
            str(load_json(session_meta).get("sessionId", session.name)), "sessionId"
        )
        for class_dir in sorted(p for p in session.iterdir() if p.is_dir()):
            safe_component(class_dir.name, "presentationClass")
            for image in sorted(p for p in class_dir.rglob("*") if p.suffix.lower() in IMAGE_SUFFIXES):
                yield image, session_meta, session_id, class_dir.name


def pull_captures(source: Path, store: Path, config_path: Path) -> dict[str, Any]:
    config = load_json(config_path)
    classes = set(config["classes"]) - {"balon"}
    entries: list[dict[str, Any]] = []
    store.mkdir(parents=True, exist_ok=True)
    for image, session_meta, session_id, class_name in iter_capture_images(source):
        digest = sha256(image)
        status = "IMPORTED" if class_name in classes else "REVIEW_REQUIRED"
        destination = store / session_id / class_name / f"{digest[:16]}{image.suffix.lower()}"
        if status == "IMPORTED":
            destination.parent.mkdir(parents=True, exist_ok=True)
            if not destination.exists():
                shutil.copy2(image, destination)
            copied_meta = destination.parents[1] / "session.json"
            if not copied_meta.exists():
                shutil.copy2(session_meta, copied_meta)
        entries.append({"sessionId": session_id, "presentationClass": class_name, "source": str(image.resolve()), "stored": str(destination.relative_to(store)) if status == "IMPORTED" else None, "sha256": digest, "status": status})
    result = {"schemaVersion": 1, "pulledAt": datetime.now(UTC).isoformat(), "source": str(source.resolve()), "status": "EMPTY" if not entries else "COMPLETE", "entries": entries}
    atomic_json(store / "pull-manifest.json", result)
    return result


def _component_boxes(cv2: Any, mask: Any, min_area: int = 80) -> list[tuple[int, int, int, int, float, float]]:
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    values = []
    for contour in contours:
        area = float(cv2.contourArea(contour))
        if area < min_area:
            continue
        x, y, w, h = cv2.boundingRect(contour)
        perimeter = float(cv2.arcLength(contour, True))
        circularity = 0.0 if perimeter <= 0 else 4 * math.pi * area / (perimeter * perimeter)
        values.append((x, y, w, h, area, circularity))
    return sorted(values, key=lambda item: item[4], reverse=True)


def auto_label_real(cv2: Any, image: Any, class_name: str, classes: list[str]) -> tuple[list[str], dict[str, Any]] | None:
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    is_friend = class_name.startswith("dost_")
    if is_friend:
        target_mask = cv2.inRange(hsv, (85, 70, 45), (110, 255, 255))
    else:
        target_mask = cv2.bitwise_or(cv2.inRange(hsv, (0, 90, 45), (12, 255, 255)), cv2.inRange(hsv, (165, 90, 45), (179, 255, 255)))
    red_mask = cv2.bitwise_or(cv2.inRange(hsv, (0, 90, 45), (12, 255, 255)), cv2.inRange(hsv, (165, 90, 45), (179, 255, 255)))
    target_components = _component_boxes(cv2, target_mask)
    if not target_components:
        return None
    # Maket usually has the largest colored area. A red circular balloon may be
    # larger in distant frames, so prefer a non-circular component when present.
    candidates = [item for item in target_components if item[5] < 0.72] or target_components
    target = max(candidates, key=lambda item: item[4])
    x, y, w, h, area, circularity = target
    height, width = image.shape[:2]
    lines = [yolo_line(classes.index(class_name), (x, y, w, h), width, height)]
    balloon = None
    for bx, by, bw, bh, barea, bcircularity in _component_boxes(cv2, red_mask):
        if bcircularity >= 0.65 and 0.65 <= bw / max(1, bh) <= 1.35 and by >= y + h * 0.55:
            balloon = (bx, by, bw, bh)
            lines.append(yolo_line(classes.index("balon"), balloon, width, height))
            break
    confidence = "AUTO_REVIEW_REQUIRED" if balloon is None else "AUTO_LINKED"
    return lines, {"targetBBox": [x, y, w, h], "balloonBBox": list(balloon) if balloon else None, "annotationStatus": confidence, "targetAreaPx": area, "targetCircularity": circularity}


def add_real_captures(config_path: Path, store: Path, output: Path) -> dict[str, Any]:
    cv2, _ = _cv()
    config = load_json(config_path)
    classes = list(config["classes"])
    records = []
    review = []
    for image_path, session_meta_path, session_id, class_name in iter_capture_images(store):
        if class_name not in classes or class_name == "balon":
            continue
        image = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
        labeled = None if image is None else auto_label_real(cv2, image, class_name, classes)
        if labeled is None:
            review.append({"source": str(image_path), "status": "REVIEW_REQUIRED", "reason": "target-color-component-not-found"})
            continue
        lines, annotation = labeled
        split = stable_split(session_id, config["realSplitPercent"])
        stem = f"real_{hashlib.sha256((session_id + sha256(image_path)).encode()).hexdigest()[:20]}"
        destination = output / "images" / split / f"{stem}{image_path.suffix.lower()}"
        shutil.copy2(image_path, destination)
        (output / "labels" / split / f"{stem}.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
        records.append({"id": stem, "sourceKind": "real-capture", "split": split, "sessionId": session_id, "groupId": session_id, "presentationClass": class_name, "sourceSha256": sha256(image_path), **annotation})
    return {"records": records, "review": review, "realCount": len(records)}


def _bbox_for_class(np: Any, class_map: Any, class_id: int) -> tuple[int, int, int, int] | None:
    rows, columns = np.where(class_map == class_id)
    if len(rows) == 0:
        return None
    left, right = int(columns.min()), int(columns.max())
    top, bottom = int(rows.min()), int(rows.max())
    return left, top, right - left + 1, bottom - top + 1


def _auto_workers(requested: int, *, ceiling: int = 8) -> int:
    if requested < 0:
        raise PipelineError("workers negatif olamaz")
    if requested > 0:
        return requested
    return max(1, min(ceiling, (os.cpu_count() or 2) - 1))


def _deterministic_subset(record_id: str, roi_size: int) -> bool:
    """Keep recovery ROI families sparse without making ingest non-repeatable."""

    divisor = {960: 4, 1152: 8}.get(roi_size, 1)
    bucket = int(hashlib.sha256(f"{record_id}:{roi_size}".encode()).hexdigest()[:8], 16)
    return bucket % divisor == 0


def _ingest_cad_one(
    task: tuple[Path, Path, dict[str, Any], list[str]],
) -> list[dict[str, Any]]:
    """Convert one high-resolution CAD frame into runtime-equivalent views."""

    hdf5_path, output, record, classes = task
    try:
        import cv2  # type: ignore
        import h5py  # type: ignore
        import numpy as np  # type: ignore
    except ImportError as exc:  # pragma: no cover - parent checks the environment
        raise RuntimeError("CAD ingest worker bağımlılıkları eksik") from exc

    synthetic_tools = ROOT / "perception/synthetic/tools"
    if str(synthetic_tools) not in sys.path:
        sys.path.insert(0, str(synthetic_tools))
    from apply_camera_pipeline import (  # type: ignore
        build_sahi_search_views,
        build_track_square_view,
    )

    batch_dir = hdf5_path.parent
    with h5py.File(hdf5_path, "r") as handle:
        if "colors" not in handle or "class_segmaps" not in handle:
            raise RuntimeError(f"RGB/class segmentation eksik: {batch_dir}")
        rgb = handle["colors"][:]
        class_map = handle["class_segmaps"][:]
    height, width = rgb.shape[:2]
    if class_map.shape[:2] != (height, width):
        raise RuntimeError(f"RGB/mask çözünürlük uyuşmazlığı: {batch_dir}")
    if (width, height) != CAD_BASE_RESOLUTION:
        raise RuntimeError(
            f"CAD taban render çözünürlüğü {CAD_BASE_RESOLUTION[0]}x"
            f"{CAD_BASE_RESOLUTION[1]} olmalı, alınan {width}x{height}: {batch_dir}"
        )
    target_bbox = _bbox_for_class(np, class_map, 1)
    balloon_bbox = _bbox_for_class(np, class_map, 7)
    if target_bbox is None or balloon_bbox is None:
        raise RuntimeError(f"hedef veya bağlı balon görünür değil: {batch_dir}")

    split = str(record["split"])
    presentation_class = str(record["presentationClass"])
    target_mask = (class_map == 1).astype(np.uint8) * 255
    balloon_mask = (class_map == 7).astype(np.uint8) * 255
    union_mask = cv2.bitwise_or(target_mask, balloon_mask)
    views: list[dict[str, Any]] = []
    search_views = build_sahi_search_views(
        rgb,
        union_mask,
        slice_size=(SEARCH_TILE_SIZE, SEARCH_TILE_SIZE),
        overlap=SEARCH_TILE_OVERLAP,
    )
    positive_search = [
        view for view in search_views if np.count_nonzero(view["modelMask"]) > 0
    ]
    easy_negatives = [
        view for view in search_views if np.count_nonzero(view["modelMask"]) == 0
    ][:2]
    views.extend(positive_search)
    views.extend(easy_negatives)
    target_center = (
        target_bbox[0] + target_bbox[2] / 2,
        target_bbox[1] + target_bbox[3] / 2,
    )
    for roi_size in TRACK_ROI_SIZES:
        if roi_size == 768 or _deterministic_subset(str(record["recordId"]), roi_size):
            views.append(
                build_track_square_view(
                    rgb,
                    union_mask,
                    roi_size_px=roi_size,
                    predicted_center_px=target_center,
                )
            )

    base_stem = "cad_" + str(record["recordId"]).lower().replace("rec-", "")
    source_batch_sha = sha256(hdf5_path)
    records: list[dict[str, Any]] = []
    for view_index, view in enumerate(views):
        metadata = dict(view["metadata"])
        rect_value = metadata.get("sliceRectFullFramePx") or metadata.get(
            "roiRectFullFramePx"
        )
        if not rect_value:
            raise RuntimeError(f"CAD inference crop sözleşmesi eksik: {batch_dir}")
        left, top, crop_width, crop_height = map(int, rect_value)
        target_crop = target_mask[top : top + crop_height, left : left + crop_width]
        balloon_crop = balloon_mask[top : top + crop_height, left : left + crop_width]
        target_model = cv2.resize(
            target_crop, MODEL_INPUT_RESOLUTION, interpolation=cv2.INTER_NEAREST
        )
        balloon_model = cv2.resize(
            balloon_crop, MODEL_INPUT_RESOLUTION, interpolation=cv2.INTER_NEAREST
        )
        target_view_bbox = _bbox_for_class(np, target_model, 255)
        balloon_view_bbox = _bbox_for_class(np, balloon_model, 255)
        suffix = (
            f"search_{int(metadata['sliceIndex']):02d}"
            if metadata["viewFamily"] == "SEARCH_SAHI_TILE_768"
            else f"track_{int(metadata['roiSourceSizePx'])}"
        )
        stem = f"{base_stem}__{suffix}"
        image_path = output / "images" / split / f"{stem}.png"
        bgr = cv2.cvtColor(view["modelInput"], cv2.COLOR_RGB2BGR)
        if not cv2.imwrite(str(image_path), bgr):
            raise RuntimeError(f"CAD görüntüsü yazılamadı: {image_path}")
        labels = []
        if target_view_bbox is not None:
            labels.append(
                yolo_line(
                    classes.index(presentation_class),
                    target_view_bbox,
                    MODEL_INPUT_RESOLUTION[0],
                    MODEL_INPUT_RESOLUTION[1],
                )
            )
        if balloon_view_bbox is not None:
            labels.append(
                yolo_line(
                    classes.index("balon"),
                    balloon_view_bbox,
                    MODEL_INPUT_RESOLUTION[0],
                    MODEL_INPUT_RESOLUTION[1],
                )
            )
        (output / "labels" / split / f"{stem}.txt").write_text(
            "\n".join(labels) + ("\n" if labels else ""), encoding="utf-8"
        )
        records.append(
            {
                "id": stem,
                "sourceFrameId": base_stem,
                "sourceKind": record["sourceKind"],
                "split": split,
                "worldId": str(record["worldId"]),
                "groupId": record["groupId"],
                "presentationClass": presentation_class,
                "routeId": record["routeId"],
                "longitudinalDistanceM": record["longitudinalDistanceM"],
                "lateralDistanceM": record["lateralDistanceM"],
                "viewYawDeg": record["viewYawDeg"],
                "topSurfaceViewDeg": record["topSurfaceViewDeg"],
                "appearanceProfileId": record["appearanceProfileId"],
                "viewFamily": metadata["viewFamily"],
                "viewIndex": view_index,
                "cropRectFullFramePx": list(map(int, rect_value)),
                "roiSourceSizePx": metadata.get("roiSourceSizePx"),
                "sliceIndex": metadata.get("sliceIndex"),
                "targetVisible": target_view_bbox is not None,
                "balloonVisible": balloon_view_bbox is not None,
                "truncatedByView": bool(metadata["truncatedBySlice"]),
                "targetBalloonLinked": True,
                "imageSha256": sha256(image_path),
                "sourceBatchSha256": source_batch_sha,
            }
        )
    return records


def ingest_cad_render_batches(
    *,
    batch_root: Path,
    output: Path,
    config_path: Path,
    workers: int = 1,
) -> dict[str, Any]:
    """Convert validated BlenderProc HDF5 batches into a research-only YOLO set."""

    _cv()
    try:
        import h5py  # type: ignore
    except ImportError as exc:
        raise PipelineError("CAD render ingest h5py gerektirir") from exc

    config = load_json(config_path)
    classes = list(config["classes"])
    if output.exists():
        shutil.rmtree(output)
    _ensure_layout(output)
    tasks: list[tuple[Path, Path, dict[str, Any], list[str]]] = []
    seen_world_splits: dict[str, str] = {}

    for record_path in sorted(batch_root.rglob("record.json")):
        batch_dir = record_path.parent
        hdf5_files = sorted(batch_dir.glob("*.hdf5"))
        if len(hdf5_files) != 1:
            continue
        record = load_json(record_path)
        if record.get("sourceKind") not in {"synthetic_cad_pbr", "synthetic_cad_dr"}:
            continue
        split = str(record["split"])
        if split == "test":
            raise PipelineError("sentetik CAD kaydı test split'ine atanamaz")
        world_id = str(record["worldId"])
        previous = seen_world_splits.setdefault(world_id, split)
        if previous != split:
            raise PipelineError(f"worldId split sızıntısı: {world_id}")
        presentation_class = str(record["presentationClass"])
        if presentation_class not in classes:
            raise PipelineError(f"bilinmeyen CAD presentationClass: {presentation_class}")
        tasks.append((hdf5_files[0], output, record, classes))

    workers = _auto_workers(workers)
    try:
        if workers == 1:
            record_groups = [_ingest_cad_one(task) for task in tasks]
        else:
            context = multiprocessing.get_context("spawn")
            with ProcessPoolExecutor(max_workers=workers, mp_context=context) as pool:
                record_groups = list(pool.map(_ingest_cad_one, tasks, chunksize=1))
    except Exception as exc:
        raise PipelineError(f"CAD ingest başarısız: {exc}") from exc

    records = [record for group in record_groups for record in group]
    if not records:
        raise PipelineError(f"içe aktarılabilir CAD render batch bulunamadı: {batch_root}")
    manifest = write_dataset_contract(
        output,
        config,
        records,
        [],
        {
            "configSha256": sha256(config_path),
            "cadBatchRoot": str(batch_root.resolve()),
            "cadBatchCount": len(tasks),
            "derivedViewCount": len(records),
            "baseRenderResolution": list(CAD_BASE_RESOLUTION),
            "modelInputResolution": list(MODEL_INPUT_RESOLUTION),
            "ingestWorkers": workers,
        },
    )
    manifest["status"] = "SYNTHETIC_RESEARCH_ONLY"
    manifest["trainingAuthorized"] = False
    manifest["releaseCandidate"] = False
    atomic_json(output / "dataset-manifest.json", manifest)
    return {
        "status": manifest["status"],
        "records": len(records),
        "trainingAuthorized": False,
        "releaseCandidate": False,
        "output": str(output),
    }


def write_dataset_contract(output: Path, config: dict[str, Any], records: list[dict[str, Any]], review: list[dict[str, Any]], inputs: dict[str, Any]) -> dict[str, Any]:
    classes = list(config["classes"])
    yaml = [f"path: {output.resolve()}", "train: images/train", "val: images/val", "test: images/test", "names:"]
    yaml.extend(f"  {index}: {name}" for index, name in enumerate(classes))
    (output / "data.yaml").write_text("\n".join(yaml) + "\n", encoding="utf-8")
    counts = {split: sum(1 for item in records if item["split"] == split) for split in ("train", "val", "test")}
    manifest = {"schemaVersion": 1, "datasetId": "GOKKALKAN-TARGETS-WORKING", "generatedAt": datetime.now(UTC).isoformat(), "status": "SYNTHETIC_SMOKE_ONLY" if not any(item["sourceKind"] == "real-capture" for item in records) else "REAL_CAPTURE_MIXED_UNVERIFIED", "trainingAuthorized": counts["val"] > 0 and counts["test"] > 0 and not review, "classes": classes, "counts": counts, "records": records, "reviewQueue": review, "inputs": inputs, "warnings": ["Sentetik veri fiziksel kabul kanıtı değildir.", "Sentetik val aynı temel maketlerden türediği için yalnız pipeline smoke-validation'dır.", "Validation/test gerçek capture session grupları oluşmadan model release adayı değildir.", "AUTO_REVIEW_REQUIRED gerçek etiketler insan incelemesi olmadan release kabulüne girmez."]}
    atomic_json(output / "dataset-manifest.json", manifest)
    return manifest


def prepare(config_path: Path, asset_manifest: Path, drop: Path, store: Path, output: Path) -> dict[str, Any]:
    if output.exists():
        shutil.rmtree(output)
    _ensure_layout(output)
    pulled = pull_captures(drop, store, config_path)
    synthetic = generate_synthetic(config_path, asset_manifest, output)
    real = add_real_captures(config_path, store, output)
    config = load_json(config_path)
    records = synthetic["records"] + real["records"]
    manifest = write_dataset_contract(output, config, records, real["review"], {"configSha256": sha256(config_path), "assetManifestSha256": sha256(asset_manifest), "capturePullManifestSha256": sha256(store / "pull-manifest.json")})
    return {"pull": pulled["status"], "synthetic": synthetic["syntheticCount"], "real": real["realCount"], "review": len(real["review"]), "datasetStatus": manifest["status"], "trainingAuthorized": manifest["trainingAuthorized"], "output": str(output)}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    sub = parser.add_subparsers(dest="command", required=True)
    pull = sub.add_parser("pull-captures", help="drop klasöründen içerik-adresli store'a kopyala")
    pull.add_argument("--source", type=Path, default=DEFAULT_DROP)
    pull.add_argument("--store", type=Path, default=DEFAULT_STORE)
    prep = sub.add_parser("prepare", help="capture pull + sentetik augmentation + YOLO dataset")
    prep.add_argument("--asset-manifest", type=Path, default=DEFAULT_ASSET_MANIFEST)
    prep.add_argument("--drop", type=Path, default=DEFAULT_DROP)
    prep.add_argument("--store", type=Path, default=DEFAULT_STORE)
    prep.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    cad = sub.add_parser(
        "ingest-cad", help="BlenderProc batch'lerini araştırma YOLO verisine dönüştür"
    )
    cad.add_argument("--batch-root", type=Path, default=DEFAULT_CAD_BATCH_ROOT)
    cad.add_argument("--output", type=Path, default=DEFAULT_CAD_OUTPUT)
    cad.add_argument(
        "--workers",
        type=int,
        default=0,
        help="Paralel CAD dönüştürme süreci; 0 CPU'ya göre otomatik",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "pull-captures":
            result = pull_captures(args.source, args.store, args.config)
        elif args.command == "prepare":
            result = prepare(args.config, args.asset_manifest, args.drop, args.store, args.output)
        else:
            result = ingest_cad_render_batches(
                batch_root=args.batch_root,
                output=args.output,
                config_path=args.config,
                workers=args.workers,
            )
    except PipelineError as exc:
        print(json.dumps({"status": "ERROR", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
