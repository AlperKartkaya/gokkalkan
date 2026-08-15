"""Gökkalkan Kamera Yakala Nodu.

Platform tespiti:
  Tek Raspberry Pi Camera Module 3 Standard (CSI) → Picamera2 (libcamera tabanlı)
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
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class CapturedFrame:
    """A frame and the clocks needed for freshness/replay decisions."""

    image: Any
    camera_timestamp_ns: int
    receive_monotonic_ns: int
    sequence: int
    timestamp_source: str
    main_image: Any | None = None
    metadata: dict[str, Any] | None = None

# numpy ve opencv isteğe bağlı; kurulu değilse mock frame döner
try:
    import numpy as np
    _NUMPY_OK = True
except ImportError:
    np = None       # type: ignore[assignment]
    _NUMPY_OK = False
    logger.warning("numpy not found; CameraNode running in mock mode.")


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
      - Picamera2 kuruluysa → tek Raspberry Pi Camera Module 3 Standard
      - cv2 kuruluysa       → OpenCV VideoCapture (USB / /dev/video0)
      - Hiçbiri yoksa       → Mock (None döner, uyarı loglanır)
    """

    # RPi Camera Module 3 için önerilen başlangıç çözünürlüğü
    DEFAULT_WIDTH:  int = 1280
    DEFAULT_HEIGHT: int = 720
    DEFAULT_MAIN_WIDTH: int = 2304
    DEFAULT_MAIN_HEIGHT: int = 1296
    DEFAULT_FPS:    int = 30

    def __init__(
        self,
        width:    int = DEFAULT_WIDTH,
        height:   int = DEFAULT_HEIGHT,
        fps:      int = DEFAULT_FPS,
        device:   int = 0,    # OpenCV kamera indeksi
        backend: str | None = None,  # "picamera2" | "opencv" | None (otomatik)
        main_width: int = DEFAULT_MAIN_WIDTH,
        main_height: int = DEFAULT_MAIN_HEIGHT,
    ) -> None:
        self.width  = width
        self.height = height
        self.fps    = fps
        self.device = device
        self.main_width = main_width
        self.main_height = main_height

        self._sample: CapturedFrame | None = None
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
        elif backend == "mock":
            self._backend = "mock"
        elif _try_picamera2():
            self._backend = "picamera2"
        elif _try_opencv():
            self._backend = "opencv"
        else:
            self._backend = "mock"
            logger.warning(
                "CameraNode: Picamera2 and OpenCV not found; running in mock mode. "
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
            return None if self._sample is None else self._sample.image

    def get_latest_sample(self) -> CapturedFrame | None:
        """Return the immutable latest frame envelope under the same lock."""

        with self._lock:
            return self._sample

    def get_latest_main_frame(self) -> Any:
        """Return the high-resolution main stream used by SAHI search."""

        with self._lock:
            return None if self._sample is None else self._sample.main_image

    def health(self, stale_after_sec: float = 1.0) -> dict[str, Any]:
        """Kamera durumu hakkında bilgi döndür."""
        sample = self.get_latest_sample()
        age_ms = (
            None
            if sample is None
            else max(0.0, (time.monotonic_ns() - sample.receive_monotonic_ns) / 1_000_000)
        )
        stale = sample is None or age_ms is None or age_ms > stale_after_sec * 1000
        status = (
            "ERROR"
            if self._error
            else "STOPPED"
            if not self._running
            else "STALE"
            if stale
            else "SIMULATED"
            if self._backend == "mock"
            else "READY"
        )
        return {
            "backend":         self._backend,
            "cameraModel":     "Raspberry Pi Camera Module 3 Standard",
            "cameraCount":     1,
            "running":         self._running,
            "framesCaptured":  self._frames_captured,
            "lastCaptureAt":   self._last_capture_at,
            "error":           self._error,
            "resolution":      f"{self.width}x{self.height}",
            "mainResolution":  f"{self.main_width}x{self.main_height}",
            "mainStreamAvailable": sample is not None and sample.main_image is not None,
            "fps":             self.fps,
            "status":          status,
            "healthy":         status == "READY",
            "simulated":       self._backend == "mock",
            "stale":           stale,
            "ageMs":           age_ms,
            "cameraTimestampNs": None if sample is None else sample.camera_timestamp_ns,
            "receiveMonotonicNs": None if sample is None else sample.receive_monotonic_ns,
            "timestampSource": None if sample is None else sample.timestamp_source,
        }

    def _publish(
        self,
        frame: Any,
        *,
        main_frame: Any | None = None,
        metadata: dict[str, Any] | None = None,
        camera_timestamp_ns: int | None = None,
        timestamp_source: str,
    ) -> None:
        receive_ns = time.monotonic_ns()
        self._frames_captured += 1
        sample = CapturedFrame(
            image=frame,
            camera_timestamp_ns=camera_timestamp_ns or receive_ns,
            receive_monotonic_ns=receive_ns,
            sequence=self._frames_captured,
            timestamp_source=timestamp_source,
            main_image=main_frame,
            metadata=None if metadata is None else dict(metadata),
        )
        with self._lock:
            self._sample = sample
        self._last_capture_at = time.time()
        self._error = None

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
                main={
                    "size": (self.main_width, self.main_height),
                    "format": "RGB888",
                },
                lores={"size": (self.width, self.height), "format": "RGB888"},
                controls={"FrameRate": self.fps},
                buffer_count=4,
            )
            cam.configure(config)
            cam.start()
            logger.info("Picamera2 başlatıldı.")
            while self._running:
                request = cam.capture_request()
                try:
                    main_frame = request.make_array("main")
                    frame = request.make_array("lores")
                    metadata = request.get_metadata()
                    sensor_ts = metadata.get("SensorTimestamp")
                    self._publish(
                        frame,
                        main_frame=main_frame,
                        metadata=metadata,
                        camera_timestamp_ns=(
                            int(sensor_ts) if isinstance(sensor_ts, (int, float)) else None
                        ),
                        timestamp_source=(
                            "picamera2-sensor"
                            if isinstance(sensor_ts, (int, float))
                            else "receive-monotonic-fallback"
                        ),
                    )
                finally:
                    request.release()
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
            self._publish(
                rgb,
                main_frame=None,
                timestamp_source="receive-monotonic-fallback",
            )

        cap.release()

    def _loop_mock(self) -> None:
        """Kamera yoksa sentetik siyah kare üret (test/geliştirme)."""
        if _NUMPY_OK:
            blank = np.zeros((self.height, self.width, 3), dtype=np.uint8)
            main_blank = np.zeros(
                (self.main_height, self.main_width, 3), dtype=np.uint8
            )
        else:
            blank = None
            main_blank = None
        period = 1.0 / self.fps
        while self._running:
            self._publish(
                blank,
                main_frame=main_blank,
                timestamp_source="simulated-monotonic",
            )
            time.sleep(period)
