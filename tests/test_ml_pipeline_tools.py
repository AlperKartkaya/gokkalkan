from __future__ import annotations

import importlib.util
import os
from pathlib import Path


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
