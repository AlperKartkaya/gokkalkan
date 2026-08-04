"""Gökkalkan Perception Bridge.

CameraNode + FrameProcessor çıktısını Backend API'ye iletir.

Mimari:
    Ayrı OS process'i:
    CameraNode → FrameProcessor → bounded latest-wins queue
    → HTTP sender/heartbeat → Mission Core command queue

Kullanım:
    bridge = PerceptionBridge(
        backend_url="http://127.0.0.1:8088",
        stage=2,
    )
    bridge.start()     # arka plan thread'i başlatır
    # ... servis ömrü ...
    bridge.stop()

CLI:
    python perception/src/perception_bridge.py --stage 2 --url http://127.0.0.1:8088
"""

from __future__ import annotations

import argparse
import logging
import os
import queue
import sys
import threading
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime
import json
from typing import Any

# Proje kökünden içe aktar
sys.path.insert(0, "perception/src")

from camera_node import CameraNode
from frame_processor import FrameProcessor
from camera_stream_server import CameraStreamService
from accelerator import AcceleratorProbe, Hailo8Accelerator

logger = logging.getLogger(__name__)


def _utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


class PerceptionBridge:
    """Perception pipeline'ını backend'e köprüleyen servis.

    Döngü:
      1. CameraNode'dan son kare al
      2. FrameProcessor ile hedef adaylarını tespit et
      3. Adayları /tracks/update endpoint'ine POST et
      4. Hata durumunda backend bağlantısını kesik olarak işaretle
    """

    DEFAULT_POLL_HZ: float = 10.0   # saniyede kaç kez işle
    CONNECT_TIMEOUT: float = 2.0    # HTTP bağlantı zaman aşımı (s)

    def __init__(
        self,
        backend_url: str  = "http://127.0.0.1:8088",
        stage:       int  = 2,
        poll_hz:     float = DEFAULT_POLL_HZ,
        camera_kw:   dict | None = None,
        processor_kw: dict | None = None,
        outbound_queue_size: int = 2,
        heartbeat_interval_sec: float = 1.0,
        camera_stream_host: str = "127.0.0.1",
        camera_stream_port: int | None = None,
        accelerator: AcceleratorProbe | None = None,
        accelerator_required: bool = False,
    ) -> None:
        self.backend_url = backend_url.rstrip("/")
        self.stage       = stage
        self._poll_sec   = 1.0 / max(0.1, poll_hz)
        self._running    = False
        self._thread: threading.Thread | None = None
        self._sender_thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._outbound: queue.Queue[list[dict[str, Any]] | None] = queue.Queue(
            maxsize=max(1, outbound_queue_size)
        )
        self._heartbeat_interval_sec = max(0.2, heartbeat_interval_sec)
        self._source_sequence = 0

        self.camera = CameraNode(**(camera_kw or {}))
        self.processor = FrameProcessor(**(processor_kw or {}))
        self.accelerator = accelerator or Hailo8Accelerator()
        self.accelerator_required = accelerator_required
        self.camera_stream = (
            CameraStreamService(camera_stream_host, camera_stream_port)
            if camera_stream_port is not None
            else None
        )

        # İstatistikler
        self._updates_sent   = 0
        self._update_errors  = 0
        self._last_update_at: str | None = None
        self._last_error: str | None = None
        self._dropped_updates = 0
        self._heartbeats_sent = 0

    # ------------------------------------------------------------------
    # Başlatma / Durdurma
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Kamerayı ve bridge döngüsünü başlat."""
        self.camera.start()
        if self.camera_stream is not None:
            self.camera_stream.start()
        self._running = True
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._loop, daemon=True, name="PercProcessor"
        )
        self._sender_thread = threading.Thread(
            target=self._sender_loop,
            daemon=True,
            name="PercSender",
        )
        self._thread.start()
        self._sender_thread.start()
        logger.info(
            "PerceptionBridge başlatıldı — backend=%s stage=%d poll=%.1fHz",
            self.backend_url, self.stage, 1.0 / self._poll_sec,
        )

    def stop(self) -> None:
        """Bridge'i ve kamerayı güvenli durdur."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=3.0)
        self._stop_event.set()
        self._offer_stop_marker()
        if self._sender_thread:
            self._sender_thread.join(timeout=3.0)
        self._post_heartbeat(healthy=False, reason="graceful_shutdown")
        self.camera.stop()
        if self.camera_stream is not None:
            self.camera_stream.stop()
        logger.info("PerceptionBridge durduruldu.")

    # ------------------------------------------------------------------
    # Ana döngü
    # ------------------------------------------------------------------

    def _loop(self) -> None:
        while self._running:
            t_start = time.monotonic()
            try:
                self._tick()
            except Exception as exc:
                logger.warning("PerceptionBridge tick hatası: %s", exc)
            elapsed  = time.monotonic() - t_start
            sleep_ms = max(0.0, self._poll_sec - elapsed)
            time.sleep(sleep_ms)

    def _tick(self) -> None:
        get_sample = getattr(self.camera, "get_latest_sample", None)
        sample = get_sample() if callable(get_sample) else None
        frame = sample.image if sample is not None else self.camera.get_latest_frame()
        if self.camera_stream is not None:
            self.camera_stream.update_image(frame, _utc_now())
        try:
            candidates = self.processor.process(
                frame,
                stage=self.stage,
                receive_monotonic_ns=(
                    None if sample is None else sample.receive_monotonic_ns
                ),
            )
        except TypeError:
            # Backward-compatible test/plugin surface.
            candidates = self.processor.process(frame, stage=self.stage)
        tracks = [c.to_api_dict() for c in candidates]
        self._enqueue_tracks(tracks)

    def _enqueue_tracks(self, tracks: list[dict[str, Any]]) -> None:
        """Keep the newest result without blocking the CPU-heavy producer."""

        try:
            self._outbound.put_nowait(tracks)
            return
        except queue.Full:
            pass
        try:
            self._outbound.get_nowait()
            self._outbound.task_done()
            self._dropped_updates += 1
        except queue.Empty:
            pass
        self._outbound.put_nowait(tracks)

    def _sender_loop(self) -> None:
        next_heartbeat = time.monotonic()
        while True:
            timeout = max(0.05, next_heartbeat - time.monotonic())
            try:
                tracks = self._outbound.get(timeout=timeout)
            except queue.Empty:
                if self._stop_event.is_set():
                    return
                tracks = None
            else:
                try:
                    if tracks is None:
                        return
                    self._post_tracks(tracks)
                finally:
                    self._outbound.task_done()
            if time.monotonic() >= next_heartbeat:
                healthy, reason = self._pipeline_health()
                self._post_heartbeat(healthy=healthy, reason=reason)
                next_heartbeat = time.monotonic() + self._heartbeat_interval_sec

    def _offer_stop_marker(self) -> None:
        while True:
            try:
                self._outbound.put_nowait(None)
                return
            except queue.Full:
                try:
                    self._outbound.get_nowait()
                    self._outbound.task_done()
                    self._dropped_updates += 1
                except queue.Empty:
                    return

    # ------------------------------------------------------------------
    # HTTP POST
    # ------------------------------------------------------------------

    def _post_tracks(self, tracks: list[dict[str, Any]]) -> None:
        if self._post_json(
            "/tracks/update",
            {"source": "perception", "tracks": tracks},
        ):
            self._updates_sent += 1
            self._last_update_at = _utc_now()

    def _post_heartbeat(self, *, healthy: bool, reason: str) -> None:
        accelerator_health = self.accelerator.health()
        if self._post_json(
            "/perception/heartbeat",
            {
                "source": "perception",
                "healthy": healthy,
                "reason": reason,
                "processId": os.getpid(),
                "queueDepth": self._outbound.qsize(),
                "droppedUpdates": self._dropped_updates,
                "accelerator": accelerator_health,
            },
        ):
            self._heartbeats_sent += 1

    def _post_json(self, path: str, body: dict[str, Any]) -> bool:
        self._source_sequence += 1
        body = {**body, "sourceSequence": self._source_sequence}
        url = f"{self.backend_url}{path}"
        payload = json.dumps(body, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=payload,
            headers={
                "Content-Type":   "application/json; charset=utf-8",
                "Content-Length": str(len(payload)),
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.CONNECT_TIMEOUT) as resp:
                resp.read()
            return True
        except (urllib.error.URLError, OSError) as exc:
            self._update_errors += 1
            self._last_error     = str(exc)
            logger.warning("Backend %s erişilemiyor: %s", path, exc)
            return False

    # ------------------------------------------------------------------
    # Sağlık bilgisi
    # ------------------------------------------------------------------

    def _pipeline_health(self) -> tuple[bool, str]:
        camera_health = self.camera.health()
        camera_ready = bool(
            camera_health.get("healthy", camera_health.get("running", False))
        )
        if not camera_ready:
            return False, str(
                camera_health.get("status", "camera_unhealthy")
            ).lower()
        accelerator_health = self.accelerator.health()
        if self.accelerator_required and not accelerator_health["hardwareReady"]:
            return False, "accelerator_unhealthy"
        reason = (
            "camera_and_accelerator_ready"
            if self.accelerator_required
            else "camera_ready"
        )
        return True, reason

    def health(self) -> dict[str, Any]:
        return {
            "running":       self._running,
            "backendUrl":    self.backend_url,
            "stage":         self.stage,
            "pollHz":        1.0 / self._poll_sec,
            "updatesSent":   self._updates_sent,
            "updateErrors":  self._update_errors,
            "lastUpdateAt":  self._last_update_at,
            "lastError":     self._last_error,
            "processId":     os.getpid(),
            "processBoundary": "separate-systemd-process",
            "outboundQueueDepth": self._outbound.qsize(),
            "outboundQueueCapacity": self._outbound.maxsize,
            "droppedUpdates": self._dropped_updates,
            "heartbeatsSent": self._heartbeats_sent,
            "camera":        self.camera.health(),
            "acceleratorRequired": self.accelerator_required,
            "accelerator":   self.accelerator.health(),
            "processor":     self.processor.stats(),
        }


# ---------------------------------------------------------------------------
# CLI Giriş Noktası
# ---------------------------------------------------------------------------

def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    parser = argparse.ArgumentParser(
        description="Gökkalkan Perception Bridge — kamera verilerini backend'e ilet",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--url",      default="http://127.0.0.1:8088",
                        help="Backend API URL")
    parser.add_argument("--stage",    type=int, default=2, choices=[1, 2, 3],
                        help="Aktif yarışma aşaması (1/2/3)")
    parser.add_argument("--poll-hz",  type=float, default=10.0,
                        help="Saniyedeki işleme sayısı")
    parser.add_argument("--device",   type=int, default=0,
                        help="OpenCV kamera indeksi (Picamera2 kullanılırsa yok sayılır)")
    parser.add_argument("--backend",  default=None,
                        choices=["picamera2", "opencv"],
                        help="Kamera backend'ini zorla seç (varsayılan: otomatik)")
    parser.add_argument("--no-classify", action="store_true",
                        help="Renk sınıflandırmasını devre dışı bırak (Aşama 2 gibi)")
    parser.add_argument(
        "--require-accelerator",
        action="store_true",
        help="AI HAT+ Hailo-8 görünmüyorsa perception heartbeat'ini sağlıksız yap",
    )
    parser.add_argument(
        "--hailo-model",
        default=None,
        help="İsteğe bağlı derlenmiş HEF model yolu; model hazır oluşu health'e yansır",
    )
    parser.add_argument(
        "--camera-stream-host",
        default="127.0.0.1",
        help="Ham kamera MJPEG servisinin dinleyeceği adres",
    )
    parser.add_argument(
        "--camera-stream-port",
        type=int,
        default=8090,
        help="Ham kamera MJPEG servis portu",
    )
    args = parser.parse_args()

    bridge = PerceptionBridge(
        backend_url  = args.url,
        stage        = args.stage,
        poll_hz      = args.poll_hz,
        camera_kw    = {"device": args.device, "backend": args.backend},
        processor_kw = {"classify_colors": not args.no_classify},
        camera_stream_host=args.camera_stream_host,
        camera_stream_port=args.camera_stream_port,
        accelerator=Hailo8Accelerator(args.hailo_model),
        accelerator_required=args.require_accelerator,
    )

    bridge.start()
    print(f"PerceptionBridge çalışıyor — {args.url}  Aşama {args.stage}")
    print("Durdurmak için Ctrl+C\n")

    try:
        while True:
            time.sleep(5.0)
            h = bridge.health()
            print(
                f"  Gönderim: {h['updatesSent']}  Hata: {h['updateErrors']}"
                f"  Kamera: {h['camera']['framesCaptured']} kare"
                f"  İzler: {h['processor']['activeTracks']}"
            )
    except KeyboardInterrupt:
        pass
    finally:
        bridge.stop()
        print("PerceptionBridge kapatıldı.")


if __name__ == "__main__":
    main()
