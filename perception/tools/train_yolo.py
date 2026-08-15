#!/usr/bin/env python3
"""Train a reproducible smoke/research YOLO detector from a prepared dataset."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATASET = ROOT / "perception/dataset/generated/yolo_current"
DEFAULT_RUNS = ROOT / "perception/dataset/model_runs"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description=__doc__)
    value.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    value.add_argument("--model", default="yolov8n.pt")
    value.add_argument("--epochs", type=int, default=30)
    value.add_argument("--imgsz", type=int, default=640)
    value.add_argument("--batch", type=int, default=8)
    value.add_argument(
        "--device",
        default="auto",
        help="auto, cpu, mps, 0 veya Ultralytics'in kabul ettiği cihaz değeri",
    )
    value.add_argument(
        "--workers",
        type=int,
        default=0,
        help="DataLoader worker sayısı; 0 CPU'ya göre otomatik",
    )
    value.add_argument(
        "--cache",
        choices=("none", "ram", "disk"),
        default="none",
        help="Tekrarlı eğitimlerde dataset cache politikası",
    )
    value.add_argument("--runs", type=Path, default=DEFAULT_RUNS)
    value.add_argument("--name", default="target-smoke")
    value.add_argument("--allow-unverified", action="store_true", help="SYNTHETIC_SMOKE_ONLY veriyle araştırma eğitimi; release yetkisi vermez")
    value.add_argument("--dry-run", action="store_true")
    return value


def resolve_workers(requested: int) -> int:
    if requested < 0:
        raise ValueError("workers negatif olamaz")
    if requested > 0:
        return requested
    return max(1, min(8, (os.cpu_count() or 2) - 1))


def resolve_device(requested: str, torch: Any) -> str:
    if requested != "auto":
        return requested
    if torch.cuda.is_available():
        return "0"
    if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        return "mps"
    return "cpu"


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        workers = resolve_workers(args.workers)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    manifest_path = args.dataset / "dataset-manifest.json"
    data_path = args.dataset / "data.yaml"
    if not manifest_path.is_file() or not data_path.is_file():
        print("Önce dataset_pipeline.py prepare çalıştırılmalıdır.", file=sys.stderr)
        return 2
    manifest: dict[str, Any] = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not manifest.get("trainingAuthorized") and not args.allow_unverified:
        print("Veri seti release-grade eğitime yetkili değil. Smoke için --allow-unverified kullanın.", file=sys.stderr)
        return 2
    intent = {
        "schemaVersion": 1,
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "datasetManifestSha256": sha256(manifest_path),
        "datasetStatus": manifest.get("status"),
        "trainingAuthorized": bool(manifest.get("trainingAuthorized")),
        "releaseCandidate": bool(manifest.get("trainingAuthorized")),
        "model": args.model,
        "epochs": args.epochs,
        "imgsz": args.imgsz,
        "batch": args.batch,
        "requestedDevice": args.device,
        "device": "AUTO_RESOLVED_AT_TRAIN_START" if args.device == "auto" else args.device,
        "workers": workers,
        "cache": args.cache,
        "licenseGate": "Ultralytics/weights lisansı release öncesinde ekipçe doğrulanmalıdır.",
    }
    args.runs.mkdir(parents=True, exist_ok=True)
    intent_path = args.runs / f"{args.name}-intent.json"
    intent_path.write_text(json.dumps(intent, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.dry_run:
        print(json.dumps({"status": "DRY_RUN", "intent": str(intent_path), **intent}, ensure_ascii=False, indent=2))
        return 0
    try:
        import ultralytics  # type: ignore
        from ultralytics import YOLO  # type: ignore
        import torch  # type: ignore
    except ImportError:
        print("Ultralytics yok. `python -m pip install -r requirements/training-dev.lock` çalıştırın.", file=sys.stderr)
        return 2
    intent["ultralyticsVersion"] = ultralytics.__version__
    device = resolve_device(args.device, torch)
    intent["device"] = device
    intent_path.write_text(
        json.dumps(intent, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    model = YOLO(args.model)
    result = model.train(
        data=str(data_path),
        epochs=args.epochs,
        imgsz=args.imgsz,
        batch=args.batch,
        device=device,
        workers=workers,
        cache={"none": False, "ram": True, "disk": "disk"}[args.cache],
        project=str(args.runs),
        name=args.name,
        seed=20260808,
        deterministic=True,
        mosaic=0.0,
        mixup=0.0,
        hsv_h=0.0,
        hsv_s=0.2,
        hsv_v=0.2,
        auto_augment=None,
        erasing=0.0,
        translate=0.05,
        scale=0.2,
        plots=True,
    )
    save_dir = Path(result.save_dir)
    best = save_dir / "weights/best.pt"
    intent.update({"completedAt": datetime.now(timezone.utc).isoformat(), "saveDir": str(save_dir), "bestWeights": str(best), "bestWeightsSha256": sha256(best) if best.is_file() else None})
    intent_path.write_text(json.dumps(intent, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "COMPLETE", **intent}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
