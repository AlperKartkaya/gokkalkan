"""Operator-facing, evidence-first runners for the capability-video rehearsal.

This module deliberately does *not* issue motion, firing, E-Stop reset, or
track-update commands.  It opens a recorded rehearsal session around the
already-running operator services; physical actions remain explicit operator
and hardware actions.
"""

from __future__ import annotations

import json
import platform
import subprocess
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


CAPABILITIES: dict[str, dict[str, Any]] = {
    "Y1": {
        "title": "Kullanıcı arayüzü ve komut yüzeyleri",
        "physicalAction": "Operatör panelinde kamera, mod, manuel yönlendirme ve telemetriyi gösterin.",
        "required": ("health", "state", "readiness"),
    },
    "Y2": {
        "title": "15 m durağan hedef / balon",
        "physicalAction": "15 m hedefi kurun; yalnız yetkili operatör fiziksel atış prosedürünü başlatsın.",
        "required": ("health", "state", "readiness"),
    },
    "Y3": {
        "title": "Hareket sırasında Acil Durdur",
        "physicalAction": "Hareket görünürken yalnız fiziksel Acil Durdur butonuna basın.",
        "required": ("health", "state"),
    },
    "Y4": {
        "title": "Ateş sırasında Acil Durdur",
        "physicalAction": "Ateş hattı çalışırken yalnız fiziksel Acil Durdur butonuna basın.",
        "required": ("health", "state"),
    },
    "Y5": {
        "title": "Hareketli hedef takibi",
        "physicalAction": "Gerçek hareketli hedefi kamera görüş alanında yatay ve yükseliş eksenlerinde hareket ettirin.",
        "required": ("health", "state", "readiness"),
    },
    "Y6": {
        "title": "5/10/15 m tespit ve sınıflandırma",
        "physicalAction": "Gerçek hedefleri ölçülmüş 5 m, 10 m ve 15 m konumlarına sırayla yerleştirin.",
        "required": ("health", "state", "readiness"),
    },
    "Y7": {
        "title": "Opsiyonel dost/düşman ayrımı",
        "physicalAction": "10 m'de bir düşman ve iki dost hedefle gerçek Aşama 3 akışını gösterin.",
        "required": ("health", "state", "readiness"),
    },
}


class VideoDemoError(RuntimeError):
    """Raised when the evidence session cannot be opened truthfully."""


def _utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _fetch_json(base_url: str, endpoint: str, timeout_sec: float) -> dict[str, Any]:
    request = urllib.request.Request(f"{base_url.rstrip('/')}{endpoint}")
    try:
        with urllib.request.urlopen(request, timeout=timeout_sec) as response:
            value = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise VideoDemoError(f"{endpoint} alınamadı: {exc}") from exc
    if not isinstance(value, dict):
        raise VideoDemoError(f"{endpoint} nesne JSON döndürmedi")
    return value


@dataclass(frozen=True)
class VideoDemoRun:
    run_id: str
    capability: str
    path: Path
    report: dict[str, Any]


def start_run(
    capability: str,
    *,
    api_url: str = "http://127.0.0.1:8088",
    output_root: str | Path = "/var/lib/gokkalkan/video-runs",
    timeout_sec: float = 3.0,
) -> VideoDemoRun:
    """Create a local evidence session after querying the live operator API.

    The runner only records actual HTTP snapshots. It never manufactures a
    healthy camera, track, classification, motor, or firing result.
    """
    capability = capability.upper()
    definition = CAPABILITIES.get(capability)
    if definition is None:
        raise VideoDemoError(f"Bilinmeyen yetenek: {capability}. Geçerli: {', '.join(CAPABILITIES)}")

    snapshots = {endpoint: _fetch_json(api_url, f"/{endpoint}", timeout_sec) for endpoint in definition["required"]}
    health = snapshots.get("health", {})
    if health.get("error"):
        raise VideoDemoError(f"operator API sağlıksız: {health['error']}")

    run_id = f"{capability.lower()}-{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:8]}"
    path = Path(output_root) / run_id
    path.mkdir(parents=True, exist_ok=False)
    report: dict[str, Any] = {
        "schemaVersion": 1,
        "runId": run_id,
        "capability": capability,
        "title": definition["title"],
        "startedAt": _utc_now(),
        "apiUrl": api_url,
        "physicalActionRequired": definition["physicalAction"],
        "physicalOutputTriggeredByRunner": False,
        "manualAnnotationIsDetection": False,
        "host": platform.node(),
        "gitRevision": _git_revision(),
        "snapshots": snapshots,
        "initialEventIds": _event_ids(snapshots.get("state", {})),
    }
    (path / "start.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return VideoDemoRun(run_id=run_id, capability=capability, path=path, report=report)


def finish_run(
    run_path: str | Path,
    *,
    api_url: str = "http://127.0.0.1:8088",
    timeout_sec: float = 3.0,
) -> dict[str, Any]:
    """Record the end state of an existing evidence session.

    A finish record intentionally contains observations only. It cannot mark a
    physical capability successful because that conclusion requires the video
    and the corresponding real-world observation.
    """
    path = Path(run_path)
    start_file = path / "start.json"
    if not start_file.is_file():
        raise VideoDemoError(f"başlangıç kaydı bulunamadı: {start_file}")
    started = json.loads(start_file.read_text(encoding="utf-8"))
    if not isinstance(started, dict):
        raise VideoDemoError("başlangıç kaydı geçersiz")
    snapshots = {
        "health": _fetch_json(api_url, "/health", timeout_sec),
        "state": _fetch_json(api_url, "/state", timeout_sec),
        "events": _fetch_json(api_url, "/events", timeout_sec),
    }
    initial_event_ids = {int(value) for value in started.get("initialEventIds", []) if isinstance(value, int)}
    new_events = [
        event for event in snapshots["events"].get("events", [])
        if isinstance(event, dict) and isinstance(event.get("id"), int) and event["id"] not in initial_event_ids
    ]
    observations = _observations_for(str(started.get("capability", "")), new_events, snapshots["state"])
    report = {
        "schemaVersion": 1,
        "runId": started.get("runId"),
        "capability": started.get("capability"),
        "finishedAt": _utc_now(),
        "physicalCapabilityVerified": False,
        "verificationNote": "Fiziksel video ve saha gözlemi incelenmeden otomatik başarı kararı verilmez.",
        "snapshots": snapshots,
        "newEvents": new_events,
        "observations": observations,
    }
    (path / "finish.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def _event_ids(snapshot: dict[str, Any]) -> list[int]:
    return [event["id"] for event in snapshot.get("events", []) if isinstance(event, dict) and isinstance(event.get("id"), int)]


def _observations_for(capability: str, events: list[dict[str, Any]], state: dict[str, Any]) -> dict[str, bool]:
    decisions = {str(event.get("decision", "")) for event in events}
    physical_estop = any(
        event.get("decision") == "ESTOP_CHANGE"
        and bool(event.get("payload", {}).get("active"))
        and event.get("payload", {}).get("source") == "gpio_or_can"
        for event in events
        if isinstance(event.get("payload"), dict)
    )
    result = {
        "newTelemetryObserved": bool(events),
        "physicalEStopObserved": physical_estop,
        "motionIntentObserved": bool({"ManualAimCommand", "AutonomousAimCommand"} & decisions),
        "fireIntentObserved": "FireIntent" in decisions,
        "trackUpdateObserved": "TRACKS_UPDATE" in decisions,
        "acceptedLidarRangeObserved": "LIDAR_RANGE_FUSED" in decisions,
        "classifiedTrackVisibleAtFinish": any(
            str(track.get("targetType", "Bilinmeyen")) not in {"", "Bilinmeyen"}
            for track in state.get("tracks", []) if isinstance(track, dict)
        ),
    }
    # These fields are observations only, not pass/fail claims.
    if capability == "Y3":
        result["expectedEventSequenceObserved"] = result["motionIntentObserved"] and physical_estop
    elif capability == "Y4":
        result["expectedEventSequenceObserved"] = result["fireIntentObserved"] and physical_estop
    elif capability == "Y5":
        result["expectedEventSequenceObserved"] = result["trackUpdateObserved"] and result["motionIntentObserved"]
    elif capability == "Y6":
        result["expectedEventSequenceObserved"] = result["trackUpdateObserved"] and result["classifiedTrackVisibleAtFinish"]
    else:
        result["expectedEventSequenceObserved"] = result["newTelemetryObserved"]
    return result


def latest_run_summary(output_root: str | Path) -> dict[str, Any]:
    """Return only the newest local session metadata for an operator display."""
    root = Path(output_root)
    start_files = sorted(root.glob("*/start.json"), key=lambda item: item.stat().st_mtime, reverse=True) if root.is_dir() else []
    if not start_files:
        return {"active": False, "physicalOutput": False}
    start_file = start_files[0]
    try:
        started = json.loads(start_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"active": False, "physicalOutput": False, "error": "video oturum kaydı okunamadı"}
    finished = (start_file.parent / "finish.json").is_file()
    return {
        "active": not finished,
        "runId": started.get("runId"),
        "capability": started.get("capability"),
        "title": started.get("title"),
        "startedAt": started.get("startedAt"),
        "physicalActionRequired": started.get("physicalActionRequired"),
        "physicalCapabilityVerified": False,
        "manualAnnotationIsDetection": False,
        "physicalOutput": False,
    }


def _git_revision() -> str | None:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], stderr=subprocess.DEVNULL, text=True, timeout=2
        ).strip()
    except (OSError, subprocess.SubprocessError):
        return None
