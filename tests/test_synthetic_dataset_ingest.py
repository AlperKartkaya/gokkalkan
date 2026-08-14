from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

h5py = pytest.importorskip("h5py")
np = pytest.importorskip("numpy")
pytest.importorskip("cv2")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "perception/tools"))

from dataset_pipeline import PipelineError, ingest_cad_render_batches


def write_batch(root: Path, *, split: str = "train") -> None:
    batch = root / "batch-001"
    batch.mkdir(parents=True)
    record = {
        "recordId": "REC-001",
        "worldId": "WORLD-001",
        "groupId": "WORLD-001",
        "sourceKind": "synthetic_cad_pbr",
        "split": split,
        "presentationClass": "dusman_f16_kirmizi",
        "routeId": "ROTA_2",
        "longitudinalDistanceM": 5.0,
        "lateralDistanceM": 0.0,
        "viewYawDeg": 0.0,
        "topSurfaceViewDeg": 12.0,
        "appearanceProfileId": "nominal",
    }
    (batch / "record.json").write_text(json.dumps(record), encoding="utf-8")
    colors = np.zeros((60, 80, 3), dtype=np.uint8)
    colors[10:30, 20:60] = [245, 10, 10]
    classes = np.zeros((60, 80), dtype=np.int64)
    classes[10:30, 20:60] = 1
    classes[35:45, 36:46] = 7
    with h5py.File(batch / "0.hdf5", "w") as handle:
        handle.create_dataset("colors", data=colors)
        handle.create_dataset("class_segmaps", data=classes)


def write_config(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "classes": ["dusman_f16_kirmizi", "balon"],
                "realSplitPercent": {"train": 70, "val": 15, "test": 15},
            }
        ),
        encoding="utf-8",
    )


def test_cad_ingest_preserves_world_split_and_stays_research_only(
    tmp_path: Path,
) -> None:
    batch_root = tmp_path / "batches"
    write_batch(batch_root)
    config = tmp_path / "config.json"
    write_config(config)
    output = tmp_path / "dataset"

    result = ingest_cad_render_batches(
        batch_root=batch_root,
        output=output,
        config_path=config,
    )

    manifest = json.loads(
        (output / "dataset-manifest.json").read_text(encoding="utf-8")
    )
    assert result["status"] == "SYNTHETIC_RESEARCH_ONLY"
    assert result["trainingAuthorized"] is False
    assert result["releaseCandidate"] is False
    assert manifest["records"][0]["worldId"] == "WORLD-001"
    assert manifest["records"][0]["split"] == "train"
    assert len((output / "labels/train/cad_001.txt").read_text().splitlines()) == 2
    assert not any((output / "images/test").iterdir())


def test_cad_ingest_rejects_synthetic_test_split(tmp_path: Path) -> None:
    batch_root = tmp_path / "batches"
    write_batch(batch_root, split="test")
    config = tmp_path / "config.json"
    write_config(config)

    with pytest.raises(PipelineError, match="test split"):
        ingest_cad_render_batches(
            batch_root=batch_root,
            output=tmp_path / "dataset",
            config_path=config,
        )
