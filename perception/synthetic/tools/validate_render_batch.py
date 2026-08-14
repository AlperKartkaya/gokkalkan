"""Validate a BlenderProc smoke batch and its route/association metadata."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import h5py
import jsonschema
import numpy as np

SYNTHETIC_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SCHEMA = SYNTHETIC_ROOT / "schema/render-record.schema.json"


class RenderBatchValidationError(RuntimeError):
    """Raised when image, labels or metadata disagree."""


def validate_arrays(arrays: dict[str, np.ndarray]) -> dict[str, Any]:
    required = {"colors", "depth", "instance_segmaps", "class_segmaps"}
    missing = required - arrays.keys()
    if missing:
        raise RenderBatchValidationError(f"eksik render katmanları: {sorted(missing)}")

    height, width = arrays["colors"].shape[:2]
    if arrays["colors"].ndim != 3 or arrays["colors"].shape[2] != 3:
        raise RenderBatchValidationError("RGB katmanı H×W×3 olmalı")
    for name in ("depth", "instance_segmaps", "class_segmaps"):
        if arrays[name].shape[:2] != (height, width):
            raise RenderBatchValidationError(f"{name} çözünürlüğü RGB ile uyuşmuyor")
    if not np.isfinite(arrays["depth"]).all():
        raise RenderBatchValidationError("depth NaN/inf içeriyor")

    class_ids, class_counts = np.unique(arrays["class_segmaps"], return_counts=True)
    counts = {
        int(key): int(value) for key, value in zip(class_ids, class_counts, strict=True)
    }
    if counts.get(1, 0) <= 0:
        raise RenderBatchValidationError("hedef sınıfı görünür piksel içermiyor")
    if counts.get(7, 0) <= 0:
        raise RenderBatchValidationError("balon sınıfı görünür piksel içermiyor")
    return {
        "resolution": [width, height],
        "classPixelCounts": counts,
        "targetVisible": True,
        "balloonVisible": True,
    }


def validate_record(record: dict[str, Any], schema: dict[str, Any]) -> None:
    jsonschema.Draft202012Validator(schema).validate(record)
    scene = record["sceneGroundTruth"]
    balloon = scene["balloon"]
    if balloon["targetInstanceId"] != scene["targetInstanceId"]:
        raise RenderBatchValidationError("balon yanlış hedefe bağlı")
    if scene["friendFoe"] == "Dost" and balloon["fireCandidateAllowed"]:
        raise RenderBatchValidationError("dost hedefe bağlı balon ateşe açık olamaz")


def validate_batch(
    *, batch_dir: Path, schema_path: Path = DEFAULT_SCHEMA
) -> dict[str, Any]:
    record = json.loads((batch_dir / "record.json").read_text(encoding="utf-8"))
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    validate_record(record, schema)
    hdf5_files = sorted(batch_dir.glob("*.hdf5"))
    if len(hdf5_files) != 1:
        raise RenderBatchValidationError("batch tam bir HDF5 renderı içermeli")
    with h5py.File(hdf5_files[0], "r") as handle:
        arrays = {
            key: handle[key][:]
            for key in ("colors", "depth", "instance_segmaps", "class_segmaps")
            if key in handle
        }
    array_report = validate_arrays(arrays)
    return {
        "status": "PASS",
        "recordId": record["recordId"],
        "worldId": record["worldId"],
        **array_report,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch", type=Path, required=True)
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA)
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = validate_batch(batch_dir=args.batch, schema_path=args.schema)
    serialized = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(serialized + "\n", encoding="utf-8")
    print(serialized)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
