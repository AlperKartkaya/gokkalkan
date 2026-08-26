from __future__ import annotations

import json
import threading
from pathlib import Path
from urllib.request import urlopen

import pytest

from gokkalkan_backend.video_demo import VideoDemoError, finish_run, latest_run_summary, start_run
from gokkalkan_backend.operator_http_server import build_http_server


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
        if endpoint == "/events":
            return {"events": [{"id": 9, "decision": "ESTOP_CHANGE", "payload": {"active": True, "source": "gpio_or_can"}}]}
        if endpoint == "/state":
            return {"events": [], "tracks": []}
        return {"endpoint": endpoint, "ok": True}

    monkeypatch.setattr("gokkalkan_backend.video_demo._fetch_json", fake_fetch)
    run = start_run("Y3", output_root=tmp_path)
    finished = finish_run(run.path)

    assert finished["physicalCapabilityVerified"] is False
    assert finished["observations"]["physicalEStopObserved"] is True
    assert (run.path / "finish.json").is_file()


def test_latest_run_summary_never_marks_physical_capability_verified(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("gokkalkan_backend.video_demo._fetch_json", lambda *_: {"ok": True})
    run = start_run("Y6", output_root=tmp_path)
    summary = latest_run_summary(tmp_path)

    assert summary["active"] is True
    assert summary["runId"] == run.run_id
    assert summary["physicalCapabilityVerified"] is False


def test_video_demo_session_endpoint_exposes_latest_run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("gokkalkan_backend.video_demo._fetch_json", lambda *_: {"ok": True})
    run = start_run("Y1", output_root=tmp_path)
    server = build_http_server("127.0.0.1", 0, video_runs_root=str(tmp_path))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with urlopen(f"http://127.0.0.1:{server.server_address[1]}/video-demo/session", timeout=2) as response:
            summary = json.loads(response.read().decode("utf-8"))
        assert summary["runId"] == run.run_id
        assert summary["physicalOutput"] is False
    finally:
        server.shutdown()
        server.server_close()
