from __future__ import annotations

import json
from pathlib import Path

import pytest

from gokkalkan_backend.video_demo import VideoDemoError, finish_run, start_run


def test_start_run_records_actual_operator_snapshots(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []

    def fake_fetch(base_url: str, endpoint: str, timeout_sec: float):
        calls.append(endpoint)
        return {"endpoint": endpoint, "ok": True}

    monkeypatch.setattr("gokkalkan_backend.video_demo._fetch_json", fake_fetch)
    run = start_run("Y5", output_root=tmp_path)

    assert calls == ["/health", "/state", "/readiness"]
    saved = json.loads((run.path / "start.json").read_text(encoding="utf-8"))
    assert saved["capability"] == "Y5"
    assert saved["physicalOutputTriggeredByRunner"] is False
    assert saved["manualAnnotationIsDetection"] is False


def test_start_run_rejects_unknown_capability(tmp_path: Path) -> None:
    with pytest.raises(VideoDemoError, match="Bilinmeyen yetenek"):
        start_run("Y8", output_root=tmp_path)


def test_finish_run_records_end_observations_without_claiming_physical_success(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fake_fetch(base_url: str, endpoint: str, timeout_sec: float):
        return {"endpoint": endpoint, "ok": True}

    monkeypatch.setattr("gokkalkan_backend.video_demo._fetch_json", fake_fetch)
    run = start_run("Y3", output_root=tmp_path)
    finished = finish_run(run.path)

    assert finished["physicalCapabilityVerified"] is False
    assert (run.path / "finish.json").is_file()
