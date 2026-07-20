"""Gökkalkan Perception Bridge.

CameraNode + FrameProcessor çıktısını Backend API'ye iletir.

Mimari:
    CameraNode → FrameProcessor → PerceptionBridge → POST /tracks/update → OperatorService

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
    ) -> None:
        self.backend_url = backend_url.rstrip("/")
        self.stage       = stage
        self._poll_sec   = 1.0 / max(0.1, poll_hz)
        self._running    = False
        self._thread: threading.Thread | None = None

        self.camera = CameraNode(**(camera_kw or {}))
        self.processor = FrameProcessor(**(processor_kw or {}))

        # İstatistikler
        self._updates_sent   = 0
        self._update_errors  = 0
        self._last_update_at: str | None = None
        self._last_error: str | None = None

    # ------------------------------------------------------------------
    # Başlatma / Durdurma
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Kamerayı ve bridge döngüsünü başlat."""
        self.camera.start()
        self._running = True
        self._thread = threading.Thread(
            target=self._loop, daemon=True, name="PercBridge"
        )
        self._thread.start()
        logger.info(
            "PerceptionBridge başlatıldı — backend=%s stage=%d poll=%.1fHz",
            self.backend_url, self.stage, 1.0 / self._poll_sec,
        )

    def stop(self) -> None:
        """Bridge'i ve kamerayı güvenli durdur."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=3.0)
        self.camera.stop()
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
        frame = self.camera.get_latest_frame()
        candidates = self.processor.process(frame, stage=self.stage)
        if not candidates:
            return
        tracks = [c.to_api_dict() for c in candidates]
        self._post_tracks(tracks)

    # ------------------------------------------------------------------
    # HTTP POST
    # ------------------------------------------------------------------

    def _post_tracks(self, tracks: list[dict[str, Any]]) -> None:
        url     = f"{self.backend_url}/tracks/update"
        payload = json.dumps(
            {"source": "perception", "tracks": tracks},
            ensure_ascii=False,
        ).encode("utf-8")
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
            self._updates_sent  += 1
            self._last_update_at = _utc_now()
        except (urllib.error.URLError, OSError) as exc:
            self._update_errors += 1
            self._last_error     = str(exc)
            logger.warning("Backend /tracks/update erişilemiyor: %s", exc)

    # ------------------------------------------------------------------
    # Sağlık bilgisi
    # ------------------------------------------------------------------

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
            "camera":        self.camera.health(),
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
    args = parser.parse_args()

    bridge = PerceptionBridge(
        backend_url  = args.url,
        stage        = args.stage,
        poll_hz      = args.poll_hz,
        camera_kw    = {"device": args.device, "backend": args.backend},
        processor_kw = {"classify_colors": not args.no_classify},
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
