from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import subprocess
import json


ROOT = Path(__file__).resolve().parents[1]


def load_module(name: str, relative_path: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_render_auto_workers_are_bounded_and_explicit_value_is_preserved() -> None:
    module = load_module(
        "render_plan_batch_for_test",
        "perception/synthetic/tools/render_plan_batch.py",
    )
    assert module.auto_worker_count(3) == 3
    assert 1 <= module.auto_worker_count(0) <= 2


def test_train_auto_workers_and_device_prefer_accelerator() -> None:
    module = load_module("train_yolo_for_test", "perception/tools/train_yolo.py")
    assert module.resolve_workers(4) == 4
    assert 1 <= module.resolve_workers(0) <= 8

    class Available:
        @staticmethod
        def is_available() -> bool:
            return True

    class Unavailable:
        @staticmethod
        def is_available() -> bool:
            return False

    cuda_torch = type("Torch", (), {"cuda": Available(), "backends": object()})()
    assert module.resolve_device("auto", cuda_torch) == "0"

    backends = type("Backends", (), {"mps": Available()})()
    mps_torch = type("Torch", (), {"cuda": Unavailable(), "backends": backends})()
    assert module.resolve_device("auto", mps_torch) == "mps"
    assert module.resolve_device("cpu", mps_torch) == "cpu"


def test_worker_defaults_fit_current_machine() -> None:
    module = load_module("dataset_pipeline_for_test", "perception/tools/dataset_pipeline.py")
    assert module._auto_workers(2) == 2
    assert 1 <= module._auto_workers(0) <= min(8, max(1, (os.cpu_count() or 2) - 1))


def test_render_retries_one_blender_failure_and_cleans_partial_batch(
    tmp_path: Path, monkeypatch,
) -> None:
    module = load_module(
        "render_plan_batch_retry_for_test",
        "perception/synthetic/tools/render_plan_batch.py",
    )
    record = {"recordId": "REC-retry"}
    expected_fingerprint = "a" * 64
    batch_dir = tmp_path / "REC-retry"
    calls = 0

    def fake_run(command, **kwargs):
        nonlocal calls
        calls += 1
        if "validate_render_batch.py" in " ".join(map(str, command)):
            return None
        batch_dir.mkdir(parents=True, exist_ok=True)
        if calls == 1:
            (batch_dir / "partial.tmp").write_text("partial", encoding="utf-8")
            raise subprocess.CalledProcessError(250, command)
        assert not (batch_dir / "partial.tmp").exists()
        (batch_dir / "record.json").write_text("{}", encoding="utf-8")
        (batch_dir / "0.hdf5").write_bytes(b"test")
        (batch_dir / "render-provenance.json").write_text(
            json.dumps({"renderFingerprint": expected_fingerprint}),
            encoding="utf-8",
        )
        return None

    monkeypatch.setattr(module.subprocess, "run", fake_run)
    monkeypatch.setattr(module.time, "sleep", lambda _: None)

    result = module._render_one(
        record=record,
        plan_path=tmp_path / "plan.json",
        output=tmp_path,
        blender=tmp_path / "Blender.app",
        render_device="auto",
        cpu_threads=2,
        retries=2,
        expected_fingerprint=expected_fingerprint,
    )

    assert result == "REC-retry"
    assert calls == 3


def test_render_cache_requires_matching_provenance(tmp_path: Path) -> None:
    module = load_module(
        "render_plan_batch_cache_for_test",
        "perception/synthetic/tools/render_plan_batch.py",
    )
    batch = tmp_path / "REC-cache"
    batch.mkdir()
    (batch / "record.json").write_text("{}", encoding="utf-8")
    (batch / "0.hdf5").write_bytes(b"render")

    assert module._is_complete(batch, "new") is False
    (batch / "render-provenance.json").write_text(
        json.dumps({"renderFingerprint": "old"}), encoding="utf-8"
    )
    assert module._is_complete(batch, "new") is False
    (batch / "render-provenance.json").write_text(
        json.dumps({"renderFingerprint": "new"}), encoding="utf-8"
    )
    assert module._is_complete(batch, "new") is True
