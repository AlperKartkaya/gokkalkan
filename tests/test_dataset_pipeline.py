from __future__ import annotations

import json
from pathlib import Path
import sys

import pytest


sys.path.insert(0, str(Path("perception/tools").resolve()))

from dataset_pipeline import (
    PipelineError,
    add_human_annotations,
    auto_label_real,
    pull_captures,
    safe_component,
    stable_split,
    yolo_line,
)


def test_human_yolo_export_is_ingested_by_session(tmp_path: Path) -> None:
    config = tmp_path / "config.json"
    config.write_text(json.dumps({"classes": ["f16", "balon"], "realSplitPercent": {"train": 70, "val": 15, "test": 15}}), encoding="utf-8")
    session = tmp_path / "annotated" / "SESSION-TEAM-01"
    (session / "images" / "train").mkdir(parents=True)
    (session / "labels" / "train").mkdir(parents=True)
    (session / "session.json").write_text(json.dumps({"sessionId": "SESSION-TEAM-01", "annotator": "team-a", "reviewer": "team-b"}), encoding="utf-8")
    (session / "images" / "train" / "frame.jpg").write_bytes(b"reviewed-image")
    (session / "labels" / "train" / "frame.txt").write_text("0 0.5 0.5 0.25 0.20\n1 0.5 0.6 0.05 0.05\n", encoding="utf-8")

    output = tmp_path / "output"
    for split in ("train", "val", "test"):
        (output / "images" / split).mkdir(parents=True)
        (output / "labels" / split).mkdir(parents=True)
    result = add_human_annotations(config, session.parent, output)

    assert result["humanCount"] == 1
    assert result["review"] == []
    assert result["records"][0]["sourceKind"] == "real-human-annotated"
    assert result["records"][0]["annotationStatus"] == "HUMAN_REVIEWED"
    assert result["records"][0]["annotator"] == "team-a"


def test_yolo_line_normalizes_bbox() -> None:
    assert yolo_line(2, (10, 20, 30, 40), 100, 200) == (
        "2 0.250000 0.200000 0.300000 0.200000"
    )


def test_real_capture_split_is_stable_by_session() -> None:
    percentages = {"train": 70, "val": 15, "test": 15}
    first = stable_split("SESSION-001", percentages)
    assert first in percentages
    assert stable_split("SESSION-001", percentages) == first


def test_capture_path_components_reject_traversal() -> None:
    assert safe_component("SESSION-001", "sessionId") == "SESSION-001"
    try:
        safe_component("../outside", "sessionId")
    except PipelineError:
        pass
    else:
        raise AssertionError("path traversal must be rejected")


def test_pull_empty_capture_folder_is_successful(tmp_path: Path) -> None:
    source = tmp_path / "drop"
    source.mkdir()
    store = tmp_path / "store"
    config = tmp_path / "config.json"
    config.write_text(
        json.dumps({"classes": ["dusman_f16_kirmizi", "balon"]}),
        encoding="utf-8",
    )

    result = pull_captures(source, store, config)

    assert result["status"] == "EMPTY"
    assert result["entries"] == []
    assert json.loads((store / "pull-manifest.json").read_text())["status"] == "EMPTY"


def test_pull_is_content_addressed_and_idempotent(tmp_path: Path) -> None:
    source = tmp_path / "drop"
    session = source / "SESSION-001"
    class_dir = session / "dusman_f16_kirmizi"
    class_dir.mkdir(parents=True)
    (session / "session.json").write_text(
        json.dumps({"sessionId": "SESSION-001"}), encoding="utf-8"
    )
    (class_dir / "frame.jpg").write_bytes(b"fake-jpeg-for-copy-contract")
    store = tmp_path / "store"
    config = tmp_path / "config.json"
    config.write_text(
        json.dumps({"classes": ["dusman_f16_kirmizi", "balon"]}),
        encoding="utf-8",
    )

    first = pull_captures(source, store, config)
    second = pull_captures(source, store, config)

    assert first["entries"][0]["status"] == "IMPORTED"
    assert first["entries"][0]["stored"] == second["entries"][0]["stored"]
    assert len(list((store / "SESSION-001/dusman_f16_kirmizi").iterdir())) == 1


def test_real_capture_auto_label_links_cyan_friend_to_red_balloon() -> None:
    # NumPy/OpenCV are optional outside perception environments. Both GitHub
    # workflows install perception-dev.lock, so this test executes in CI while
    # remaining collectable in backend-only developer environments.
    np = pytest.importorskip("numpy")
    cv2 = pytest.importorskip("cv2")
    image = np.zeros((240, 320, 3), dtype=np.uint8)
    image[40:125, 80:240] = (224, 163, 0)  # BGR karşılığı: RGB #00A3E0
    cv2.circle(image, (160, 175), 18, (10, 10, 245), -1)
    classes = ["dost_f16_camgobegi", "balon"]

    result = auto_label_real(cv2, image, "dost_f16_camgobegi", classes)

    assert result is not None
    labels, metadata = result
    assert [line.split()[0] for line in labels] == ["0", "1"]
    assert metadata["annotationStatus"] == "AUTO_LINKED"
    assert metadata["balloonBBox"] is not None
