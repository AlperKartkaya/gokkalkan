#!/usr/bin/env python3
"""Export the selected Gökkalkan YOLO detector to Hailo-compatible ONNX."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_WEIGHTS = (
    ROOT / "perception/dataset/model_runs/cad-20260817-124525/weights/best.pt"
)
DEFAULT_OUTPUT = ROOT / "artifacts/hailo"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--weights", type=Path, default=DEFAULT_WEIGHTS)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--imgsz", type=int, default=640)
    args = parser.parse_args()
    if not args.weights.is_file():
        parser.error(f"weights not found: {args.weights}")

    from ultralytics import YOLO

    args.output_dir.mkdir(parents=True, exist_ok=True)
    exported = Path(
        YOLO(str(args.weights)).export(
            format="onnx",
            imgsz=args.imgsz,
            opset=11,
            simplify=True,
            dynamic=False,
            nms=False,
        )
    )
    destination = args.output_dir / "target_detector.onnx"
    destination.write_bytes(exported.read_bytes())
    manifest = {
        "schemaVersion": 1,
        "status": "SYNTHETIC_RESEARCH_ONLY",
        "releaseCandidate": False,
        "architecture": "yolov8s",
        "inputSize": [args.imgsz, args.imgsz],
        "classCount": 7,
        "classes": [
            "dusman_drone_kirmizi",
            "dusman_helikopter_kirmizi",
            "dusman_f16_kirmizi",
            "dusman_fuze_kirmizi",
            "dost_helikopter_camgobegi",
            "dost_f16_camgobegi",
            "balon",
        ],
        "weights": str(args.weights),
        "weightsSha256": sha256(args.weights),
        "onnx": str(destination),
        "onnxSha256": sha256(destination),
        "hailoTarget": "hailo8",
        "requiredPostprocess": "Hailo NMS",
    }
    manifest_path = args.output_dir / "target_detector.export.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

