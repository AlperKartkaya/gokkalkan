"""Gökkalkan Kamera Yakala Nodu.

Platform tespiti:
  Raspberry Pi Camera Module 3 (CSI) → Picamera2 (libcamera tabanlı)
  USB kamera / geliştirme makinesi   → OpenCV VideoCapture (fallback)

Kullanım:
    node = CameraNode()
    node.start()
    frame = node.get_latest_frame()   # numpy array veya None
    node.stop()
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any

logger = logging.getLogger(__name__)

# numpy ve opencv isteğe bağlı; kurulu değilse mock frame döner
try:
    import numpy as np
    _NUMPY_OK = True
except ImportError:
    np = None       # type: ignore[assignment]
    _NUMPY_OK = False
    logger.warning("numpy bulunamadı; CameraNode mock modda çalışır.")


def _try_picamera2() -> bool:
    try:
        import picamera2  # noqa: F401
        return True
    except ImportError:
        return False


def _try_opencv() -> bool:
    try:
        import cv2  # noqa: F401
        return True
    except ImportError:
        return False


class CameraNode:
    """Kamera karesini sürekli yakalayan arka plan thread'i.

    Başarıyla yakalanan son kare `get_latest_frame()` ile alınır.
    Platform tespiti otomatik yapılır:
      - Picamera2 kuruluysa → Raspberry Pi Camera Module 3
      - cv2 kuruluysa       → OpenCV VideoCapture (USB / /dev/video0)
      - Hiçbiri yoksa       → Mock (None döner, uyarı loglanır)
    """

    # RPi Camera Module 3 için önerilen başlangıç çözünürlüğü
    DEFAULT_WIDTH:  int = 1280
    DEFAULT_HEIGHT: int = 720
    DEFAULT_FPS:    int = 30

    def __init__(
        self,
        width:    int = DEFAULT_WIDTH,
        height:   int = DEFAULT_HEIGHT,
        fps:      int = DEFAULT_FPS,
        device:   int = 0,    # OpenCV kamera indeksi
        backend: str | None = None,  # "picamera2" | "opencv" | None (otomatik)
    ) -> None:
        self.width  = width
        self.height = height
        self.fps    = fps
        self.device = device

        self._frame: Any          = None
        self._lock                = threading.Lock()
        self._running             = False
        self._thread: threading.Thread | None = None
        self._frames_captured     = 0
        self._last_capture_at:float = 0.0
        self._error: str | None   = None

        # Backend seçimi
        if backend == "picamera2":
            self._backend = "picamera2"
        elif backend == "opencv":
            self._backend = "opencv"
        elif _try_picamera2():
            self._backend = "picamera2"
        elif _try_opencv():
            self._backend = "opencv"
        else:
            self._backend = "mock"
            logger.warning(
                "CameraNode: Picamera2 ve OpenCV bulunamadı; mock modda çalışır. "
                "Kurulum: pip install picamera2  veya  pip install opencv-python"
            )

        logger.info("CameraNode: backend=%s çözünürlük=%dx%d fps=%d",
                    self._backend, width, height, fps)

    # ------------------------------------------------------------------
    # Genel arayüz
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Kamera yakalamayı başlat (arka plan thread)."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(
            target=self._capture_loop, daemon=True, name="CamCapture"
        )
        self._thread.start()
        logger.info("CameraNode başlatıldı (backend=%s).", self._backend)

    def stop(self) -> None:
        """Kamera yakalamayı güvenli durdur."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=3.0)
        logger.info("CameraNode durduruldu.")

    def get_latest_frame(self) -> Any:
        """Son yakalanan kareyi döndür (numpy array veya None).

        Thread-safe: kilit altında okunur.
        """
        with self._lock:
            return self._frame

    def health(self) -> dict[str, Any]:
        """Kamera durumu hakkında bilgi döndür."""
        return {
            "backend":         self._backend,
            "running":         self._running,
            "framesCaptured":  self._frames_captured,
            "lastCaptureAt":   self._last_capture_at,
            "error":           self._error,
            "resolution":      f"{self.width}x{self.height}",
            "fps":             self.fps,
        }

    # ------------------------------------------------------------------
    # Yakalama döngüleri
    # ------------------------------------------------------------------

    def _capture_loop(self) -> None:
        if self._backend == "picamera2":
            self._loop_picamera2()
        elif self._backend == "opencv":
            self._loop_opencv()
        else:
            self._loop_mock()

    def _loop_picamera2(self) -> None:
        try:
            from picamera2 import Picamera2  # type: ignore[import]
            cam = Picamera2()
            config = cam.create_video_configuration(
                main={"size": (self.width, self.height), "format": "RGB888"},
                controls={"FrameRate": self.fps},
            )
            cam.configure(config)
            cam.start()
            logger.info("Picamera2 başlatıldı.")
            while self._running:
                frame = cam.capture_array()
                with self._lock:
                    self._frame = frame
                self._frames_captured += 1
                self._last_capture_at = time.time()
            cam.stop()
            cam.close()
        except Exception as exc:
            self._error = str(exc)
            logger.error("Picamera2 hatası: %s — OpenCV'ye geçiliyor.", exc)
            self._backend = "opencv"
            self._loop_opencv()

    def _loop_opencv(self) -> None:
        try:
            import cv2  # type: ignore[import]
        except ImportError:
            self._error = "opencv-python kurulu değil."
            logger.error(self._error)
            return

        cap = cv2.VideoCapture(self.device)
        if not cap.isOpened():
            self._error = f"Kamera aygıtı açılamadı: /dev/video{self.device}"
            logger.error(self._error)
            return

        cap.set(cv2.CAP_PROP_FRAME_WIDTH,  self.width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        cap.set(cv2.CAP_PROP_FPS,          self.fps)
        logger.info("OpenCV VideoCapture açıldı (device=%d).", self.device)

        while self._running:
            ret, frame = cap.read()
            if not ret:
                logger.warning("Kare okunamadı; 100ms bekleniyor.")
                time.sleep(0.1)
                continue
            # BGR → RGB dönüşümü (downstream bileşenler RGB bekler)
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            with self._lock:
                self._frame = rgb
            self._frames_captured += 1
            self._last_capture_at  = time.time()

        cap.release()

    def _loop_mock(self) -> None:
        """Kamera yoksa sentetik siyah kare üret (test/geliştirme)."""
        if _NUMPY_OK:
            blank = np.zeros((self.height, self.width, 3), dtype=np.uint8)
        else:
            blank = None
        period = 1.0 / self.fps
        while self._running:
            with self._lock:
                self._frame = blank
            self._frames_captured += 1
            self._last_capture_at  = time.time()
            time.sleep(period)
