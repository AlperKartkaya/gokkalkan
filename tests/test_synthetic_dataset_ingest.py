from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

h5py = pytest.importorskip("h5py")
np = pytest.importorskip("numpy")
cv2 = pytest.importorskip("cv2")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "perception/tools"))

from dataset_pipeline import PipelineError, ingest_cad_render_batches


def write_batch(
    root: Path,
    *,
    split: str = "train",
    suffix: str = "001",
) -> None:
    batch = root / f"batch-{suffix}"
    batch.mkdir(parents=True)
    record = {
        "recordId": f"REC-{suffix}",
        "worldId": f"WORLD-{suffix}",
        "groupId": f"WORLD-{suffix}",
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
    colors = np.zeros((1296, 2304, 3), dtype=np.uint8)
    colors[540:660, 1080:1320] = [245, 10, 10]
    classes = np.zeros((1296, 2304), dtype=np.uint8)
    classes[540:660, 1080:1320] = 1
    classes[680:760, 1160:1240] = 7
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
    assert all(item["worldId"] == "WORLD-001" for item in manifest["records"])
    assert all(item["split"] == "train" for item in manifest["records"])
    assert {item["viewFamily"] for item in manifest["records"]} == {
        "SEARCH_SAHI_TILE_768",
        "TRACK_SQUARE_ROI",
    }
    assert all(
        cv2.imread(str(path)).shape[:2] == (640, 640)
        for path in (output / "images/train").glob("*.png")
    )
    assert not (output / "images/train/cad_001.png").exists()
    assert any(
        len(path.read_text().splitlines()) == 2
        for path in (output / "labels/train").glob("cad_001__*.txt")
    )
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


def test_cad_ingest_parallel_workers_preserve_deterministic_record_order(
    tmp_path: Path,
) -> None:
    batch_root = tmp_path / "batches"
    write_batch(batch_root, suffix="002")
    write_batch(batch_root, suffix="001")
    config = tmp_path / "config.json"
    write_config(config)
    output = tmp_path / "dataset"

    result = ingest_cad_render_batches(
        batch_root=batch_root,
        output=output,
        config_path=config,
        workers=2,
    )

    manifest = json.loads(
        (output / "dataset-manifest.json").read_text(encoding="utf-8")
    )
    assert result["records"] > 2
    source_frames = [item["sourceFrameId"] for item in manifest["records"]]
    assert source_frames == sorted(source_frames)
    assert set(source_frames) == {"cad_001", "cad_002"}
    assert manifest["inputs"]["ingestWorkers"] == 2


def test_cad_ingest_rejects_legacy_low_resolution_render(tmp_path: Path) -> None:
    batch_root = tmp_path / "batches"
    write_batch(batch_root)
    batch = next(batch_root.iterdir())
    with h5py.File(batch / "0.hdf5", "w") as handle:
        handle.create_dataset("colors", data=np.zeros((360, 640, 3), dtype=np.uint8))
        handle.create_dataset("class_segmaps", data=np.zeros((360, 640), dtype=np.uint8))
    config = tmp_path / "config.json"
    write_config(config)

    with pytest.raises(PipelineError, match="2304x1296"):
        ingest_cad_render_batches(
            batch_root=batch_root,
            output=tmp_path / "dataset",
            config_path=config,
        )
