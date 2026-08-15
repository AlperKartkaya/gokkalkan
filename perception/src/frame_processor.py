"""Gökkalkan Kare İşleyici — HSV Renk Filtresi + Centroid Tracker.

Şartname V1.4 hedef renk kodlaması:
  Aşama 1/2 → Kırmızı hedef; dost/düşman sınıflandırması yapılmaz
  Aşama 3   → Kırmızı düşman, camgöbeği dost; kırmızı balon IFF kanıtı değildir

Algı çıktısı: TrackCandidate listesi → perception_bridge → /tracks/update API

Tüm HSV eşik değerleri konfigüre edilebilir (FrameProcessor.__init__ parametreleri).
Gerçek hedef görüntülerinden kalibrasyon için scripts/calibrate_hsv.py (TBD) kullanın.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

from aim_alignment import AimCalibration, calibrated_aim_error

logger = logging.getLogger(__name__)


def is_probable_balloon_shape(*, area: float, perimeter: float, width: float, height: float) -> bool:
    """Kırmızı balon için yalnız şekil tabanlı, konservatif ön filtre."""

    if perimeter <= 0.0 or width <= 0.0 or height <= 0.0:
        return False
    circularity = 4.0 * 3.141592653589793 * area / (perimeter * perimeter)
    aspect_ratio = width / height
    return circularity >= 0.86 and 0.72 <= aspect_ratio <= 1.28

# numpy and opencv are optional
try:
    import numpy as np
    import cv2
    _CV_OK = True
except ImportError:
    np = None   # type: ignore[assignment]
    cv2 = None  # type: ignore[assignment]
    _CV_OK = False
    logger.warning("numpy/opencv not found; FrameProcessor running in mock mode.")


# ---------------------------------------------------------------------------
# Veri modeli
# ---------------------------------------------------------------------------

@dataclass
class TrackCandidate:
    """Kameradan tespit edilen tek bir hedef adayı.

    rangeM: kameradan mesafe tahmini (şimdilik bbox alanından; LiDAR entegrasyonu sonra)
    bearingDeg: kamera görüntüsünde yatay açı tahmini (piksel merkezden)
    object_role: 'target' (maket) veya 'balloon' (imha balonu)
    fire_candidate: False → ateş yetkisi asla verilmez (balon, ilişkisiz nesne)
    """
    track_id:    str
    cx:          float           # görüntü piksel X merkezi
    cy:          float           # görüntü piksel Y merkezi
    width_px:    float           # bounding box genişliği (piksel)
    height_px:   float           # bounding box yüksekliği (piksel)
    area_px:     float           # kontur alanı (piksel²)
    color:       str             # "red" | "blue" | "red_balloon" | "unknown"
    friend_foe:  str             # "Düşman" | "Dost" | "Bilinmeyen"
    target_type: str             # "Bilinmeyen" (Aşama 2) veya sınıf (Aşama 3)
    confidence:  float           # 0.0–1.0
    range_m:     float           # tahmini mesafe (m)
    bearing_deg: float           # tahmini yatay açı (°)
    velocity_x_px_s: float = 0.0
    velocity_y_px_s: float = 0.0
    freshness_ms: float = 0.0
    state: str = "TRACKED"
    receive_monotonic_ns: int = field(default_factory=time.monotonic_ns)
    detected_at: float = field(default_factory=time.time)
    yaw_error_deg: float | None = None
    pitch_error_deg: float | None = None
    aim_calibration_id: str | None = None
    aim_calibration_hash: str | None = None
    aim_valid: bool = False
    object_role: str = "target"   # "target" | "balloon"
    fire_candidate: bool = True    # balon track'lerinde False

    def to_api_dict(self) -> dict[str, Any]:
        """Backend /tracks/update sözleşmesiyle uyumlu dict."""
        return {
            "trackId":    self.track_id,
            "targetType": self.target_type,
            "friendFoe":  self.friend_foe,
            "rangeM":     round(self.range_m, 2),
            "bearingDeg": round(self.bearing_deg, 2),
            "confidence": round(self.confidence, 3),
            "bboxPx":     [self.cx, self.cy, self.width_px, self.height_px],
            "source":     "perception",
            "rangeSource": "camera-bbox-estimate",
            "velocityPxSec": [
                round(self.velocity_x_px_s, 2),
                round(self.velocity_y_px_s, 2),
            ],
            "freshnessMs": round(self.freshness_ms, 2),
            "trackState": self.state,
            "receiveMonotonicNs": self.receive_monotonic_ns,
            "yawErrorDeg": self.yaw_error_deg,
            "pitchErrorDeg": self.pitch_error_deg,
            "aimCalibrationId": self.aim_calibration_id,
            "aimCalibrationHash": self.aim_calibration_hash,
            "aimValid": self.aim_valid,
            "objectRole": self.object_role,
            "fireCandidate": self.fire_candidate,
        }


# ---------------------------------------------------------------------------
# Centroid Tracker
# ---------------------------------------------------------------------------

def _hungarian_match(
    cost: list[list[float]],
) -> list[tuple[int, int]]:
    """Pure-Python Hungarian algorithm (Munkres) for rectangular cost matrices.

    Returns a list of (row, col) assignments that minimise total cost.
    Falls back to empty list on degenerate inputs.  O(N³) but N < 10 in
    normal operation so this is faster than scipy import overhead.
    """
    if not cost or not cost[0]:
        return []
    n_rows = len(cost)
    n_cols = len(cost[0])
    n = max(n_rows, n_cols)
    # Pad to square with a large sentinel
    INF = float("inf")
    big = max(c for row in cost for c in row if c != INF) * 10 + 1
    c = [[big] * n for _ in range(n)]
    for i in range(n_rows):
        for j in range(n_cols):
            c[i][j] = cost[i][j] if cost[i][j] != INF else big

    # Row / column reduction
    for i in range(n):
        m = min(c[i])
        for j in range(n):
            c[i][j] -= m
    for j in range(n):
        m = min(c[i][j] for i in range(n))
        for i in range(n):
            c[i][j] -= m

    assigned_col: list[int] = [-1] * n  # assigned_col[row] = col
    covered_rows: set[int] = set()
    covered_cols: set[int] = set()

    def _find_zeros() -> list[tuple[int, int]]:
        return [
            (i, j)
            for i in range(n)
            for j in range(n)
            if c[i][j] == 0
        ]

    def _cover() -> int:
        """Greedily mark independent zeros; return count of covered assignments."""
        covered_rows.clear()
        covered_cols.clear()
        starred: list[tuple[int, int]] = []
        row_done: set[int] = set()
        col_done: set[int] = set()
        for i, j in _find_zeros():
            if i not in row_done and j not in col_done:
                starred.append((i, j))
                row_done.add(i)
                col_done.add(j)
        for _, j in starred:
            covered_cols.add(j)
        return len(starred)

    max_iter = n * n * 4
    for _ in range(max_iter):
        if _cover() == n:
            break
        # Find smallest uncovered value
        mn = min(
            c[i][j]
            for i in range(n)
            for j in range(n)
            if i not in covered_rows and j not in covered_cols
        )
        # Subtract from uncovered, add to double-covered
        for i in range(n):
            for j in range(n):
                if i not in covered_rows and j not in covered_cols:
                    c[i][j] -= mn
                elif i in covered_rows and j in covered_cols:
                    c[i][j] += mn

    # Extract assignment from zeroed matrix
    result: list[tuple[int, int]] = []
    row_taken: set[int] = set()
    col_taken: set[int] = set()
    zeros = sorted(_find_zeros())
    for i, j in zeros:
        if i not in row_taken and j not in col_taken:
            result.append((i, j))
            row_taken.add(i)
            col_taken.add(j)
    return [
        (r, col)
        for r, col in result
        if r < n_rows and col < n_cols
    ]


class CentroidTracker:
    """Distance-based centroid tracker with Hungarian optimal assignment.

    Matches detected contours across frames and maintains stable IDs.
    Tracks absent for more than *max_disappeared* frames are dropped.
    """

    def __init__(self, max_disappeared: int = 10, max_distance_px: float = 80.0) -> None:
        self.tracks:         dict[str, dict[str, Any]] = {}
        self.disappeared:    dict[str, int] = {}
        self.max_disappeared = max_disappeared
        self.max_distance    = max_distance_px
        self._next_track_number = 1

    def update(
        self,
        detections: list[tuple[float, float, float, float, float, str]],
        *,
        timestamp_ns: int | None = None,
    ) -> dict[str, dict[str, Any]]:
        """Update tracks with new detections using Hungarian optimal matching.

        Args:
            detections: (cx, cy, w, h, area, color) tuple list

        Returns:
            Active tracks: {track_id: {cx, cy, w, h, area, color, age}}
        """
        now_ns = time.monotonic_ns() if timestamp_ns is None else timestamp_ns
        if not detections:
            # Increment miss counter for all tracks; prune stale ones
            for tid in list(self.disappeared):
                self.disappeared[tid] += 1
                if self.disappeared[tid] > self.max_disappeared:
                    del self.tracks[tid]
                    del self.disappeared[tid]
            return {
                tid: track
                for tid, track in self.tracks.items()
                if self.disappeared.get(tid, 0) == 0
            }

        if not self.tracks:
            # First frame: register all detections as new tracks
            for det in detections:
                self._register(det, now_ns)
        else:
            track_ids = list(self.tracks.keys())
            track_centers = [
                (self.tracks[tid]["cx"], self.tracks[tid]["cy"])
                for tid in track_ids
            ]

            # Build Euclidean distance cost matrix [tracks × detections]
            cost: list[list[float]] = []
            for tx, ty in track_centers:
                row: list[float] = []
                for det in detections:
                    dist = ((det[0] - tx) ** 2 + (det[1] - ty) ** 2) ** 0.5
                    # Distances beyond max_distance are treated as infeasible
                    row.append(dist if dist < self.max_distance else float("inf"))
                cost.append(row)

            # Optimal assignment via Hungarian algorithm
            assignments = _hungarian_match(cost)

            used_dets: set[int] = set()
            used_tracks: set[int] = set()

            for ti, di in assignments:
                if cost[ti][di] >= self.max_distance:
                    continue  # infeasible pair — skip
                tid = track_ids[ti]
                det = detections[di]
                previous = self.tracks[tid]
                elapsed_s = max(
                    1e-9, (now_ns - int(previous.get("last_seen_ns", now_ns))) / 1e9
                )
                self.tracks[tid].update({
                    "cx": det[0], "cy": det[1],
                    "w": det[2], "h": det[3],
                    "area": det[4], "color": det[5],
                    "age": self.tracks[tid].get("age", 0) + 1,
                    "velocity_x_px_s": (det[0] - float(previous["cx"])) / elapsed_s,
                    "velocity_y_px_s": (det[1] - float(previous["cy"])) / elapsed_s,
                    "last_seen_ns": now_ns,
                })
                self.disappeared[tid] = 0
                used_dets.add(di)
                used_tracks.add(ti)

            # Increment miss counter for unmatched tracks
            for ti, tid in enumerate(track_ids):
                if ti not in used_tracks:
                    self.disappeared[tid] += 1
                    if self.disappeared[tid] > self.max_disappeared:
                        del self.tracks[tid]
                        del self.disappeared[tid]

            # Unmatched detections become new tracks
            for di, det in enumerate(detections):
                if di not in used_dets:
                    self._register(det, now_ns)

        return {
            tid: track
            for tid, track in self.tracks.items()
            if self.disappeared.get(tid, 0) == 0
        }


    def _register(
        self,
        det: tuple[float, float, float, float, float, str],
        timestamp_ns: int,
    ) -> None:
        tid = f"PERC-{self._next_track_number:06d}"
        self._next_track_number += 1
        self.tracks[tid] = {
            "cx": det[0], "cy": det[1],
            "w": det[2], "h": det[3],
            "area": det[4], "color": det[5],
            "age": 1,
            "velocity_x_px_s": 0.0,
            "velocity_y_px_s": 0.0,
            "first_seen_ns": timestamp_ns,
            "last_seen_ns": timestamp_ns,
        }
        self.disappeared[tid] = 0


# ---------------------------------------------------------------------------
# Kare İşleyici
# ---------------------------------------------------------------------------

class FrameProcessor:
    """Kamera karesini alır, hedef adaylarını tespit eder.

    HSV Renk Aralıkları (varsayılan — sahada kalibrasyon önerilir):
      Kırmızı: İki ayrı Hue bant (Hue wrap-around: 0-10 ve 170-180)
      Mavi:    Hue 100-130

    Mesafe Tahmini:
      Gerçek mesafe LiDAR entegrasyonuna kadar bbox alanından tahmin edilir.
      Bu değerler test ve görselleştirme içindir; Safety Gate kararı için
      doğrulanmış LiDAR menzili beklenmesi gerekir.
    """

    # HSV Kırmızı (iki bant — Hue 0-10 ve 170-180)
    RED_LOW1  = (0,   120, 80)
    RED_HIGH1 = (10,  255, 255)
    RED_LOW2  = (170, 120, 80)
    RED_HIGH2 = (180, 255, 255)

    # HSV Mavi
    # Yayımlanan dost rengi #00A3E0 OpenCV HSV uzayında yaklaşık H=98'dir.
    BLUE_LOW  = (88, 100, 60)
    BLUE_HIGH = (130, 255, 255)

    # Minimum kontur alanı (piksel²) — gürültü eşiği
    MIN_AREA_PX: float = 300.0

    # Raspberry Pi Camera Module 3 Standard yatay görüş alanı (üretici: 66°)
    HFOV_DEG: float = 66.0

    # Kaba mesafe tahmini katsayısı (kalibrasyonla düzeltilmeli)
    RANGE_AREA_K: float = 50_000.0  # range_m ≈ K / sqrt(area_px)

    def __init__(
        self,
        image_width:   int   = 1280,
        image_height:  int   = 720,
        min_area_px:   float = MIN_AREA_PX,
        hfov_deg:      float = HFOV_DEG,
        range_area_k:  float = RANGE_AREA_K,
        tracker_max_disappeared: int = 10,
        tracker_max_dist_px:     float = 80.0,
        classify_colors: bool = True,
        aim_calibration: AimCalibration | None = None,
    ) -> None:
        self.image_width   = image_width
        self.image_height  = image_height
        self.min_area_px   = min_area_px
        self.hfov_deg      = hfov_deg
        self.range_area_k  = range_area_k
        self.classify_colors = classify_colors
        self.aim_calibration = aim_calibration
        self._tracker = CentroidTracker(
            max_disappeared=tracker_max_disappeared,
            max_distance_px=tracker_max_dist_px,
        )
        self._balloon_tracker = CentroidTracker(
            max_disappeared=max(4, tracker_max_disappeared),
            max_distance_px=tracker_max_dist_px * 1.2,
        )
        self._frames_processed = 0

    # ------------------------------------------------------------------
    # Ana işleme akışı
    # ------------------------------------------------------------------

    def process(
        self,
        frame: Any,
        stage: int = 2,
        *,
        receive_monotonic_ns: int | None = None,
    ) -> list[TrackCandidate]:
        """RGB numpy kareyi işle; hedef adayı listesi döndür.

        Args:
            frame: RGB numpy array (H, W, 3) — None ise boş liste döner
            stage: Yarışma aşaması (1/2/3). Aşama 1/2'de yalnız kırmızı hedef
                   aranır ve tespitler "Bilinmeyen" olarak etiketlenir.

        Returns:
            TrackCandidate listesi (boş olabilir)
        """
        timestamp_ns = time.monotonic_ns() if receive_monotonic_ns is None else receive_monotonic_ns
        if not _CV_OK or frame is None:
            self._tracker.update([], timestamp_ns=timestamp_ns)
            return []

        self._frames_processed += 1

        # Gürültü azaltma
        blurred = cv2.GaussianBlur(frame, (7, 7), 0)
        hsv     = cv2.cvtColor(blurred, cv2.COLOR_RGB2HSV)

        # Renk maskeleri
        if not self.classify_colors:
            # Renk filtresi kapatıldığında doygun/parlak bölgeleri aday kabul et.
            _, s, v = cv2.split(hsv)
            mask    = cv2.bitwise_and(
                cv2.inRange(s, 80, 255),
                cv2.inRange(v, 60, 255),
            )
            color_label = "unknown"
        elif stage in (1, 2):
            # V1.4: Aşama 1 ve 2 hedefleri kırmızıdır; sınıflandırma gerekmez.
            mask_r1 = cv2.inRange(hsv, self.RED_LOW1, self.RED_HIGH1)
            mask_r2 = cv2.inRange(hsv, self.RED_LOW2, self.RED_HIGH2)
            mask = cv2.bitwise_or(mask_r1, mask_r2)
            color_label = "unknown"
        else:
            # V1.4 + güncel hedef tablosu: kırmızı düşman / camgöbeği dost.
            # Camgöbeği (#00A3E0) mevcut OpenCV "blue" HSV bandının içindedir;
            # taşıma sözleşmesindeki color değeri geriye uyumluluk için blue kalır.
            mask_r1   = cv2.inRange(hsv, self.RED_LOW1,  self.RED_HIGH1)
            mask_r2   = cv2.inRange(hsv, self.RED_LOW2,  self.RED_HIGH2)
            mask_red  = cv2.bitwise_or(mask_r1, mask_r2)
            mask_blue = cv2.inRange(hsv, self.BLUE_LOW,  self.BLUE_HIGH)
            mask      = cv2.bitwise_or(mask_red, mask_blue)
            color_label = "multi"  # kontur başına aşağıda belirlenir

        # Morfolojik temizlik
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        mask   = cv2.morphologyEx(mask, cv2.MORPH_OPEN,  kernel)
        mask   = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

        # Kontur tespiti
        contours, _ = cv2.findContours(
            mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )

        detections: list[tuple[float, float, float, float, float, str]] = []
        balloon_detections: list[tuple[float, float, float, float, float, str]] = []
        for cnt in contours:
            area = float(cv2.contourArea(cnt))
            if area < self.min_area_px:
                continue
            x, y, w, h = cv2.boundingRect(cnt)
            cx = float(x + w / 2)
            cy = float(y + h / 2)

            # Kontur başına renk etiketi belirle (Aşama 3)
            if color_label == "multi":
                sub_hsv = hsv[y : y + h, x : x + w]
                r1 = cv2.inRange(sub_hsv, self.RED_LOW1, self.RED_HIGH1)
                r2 = cv2.inRange(sub_hsv, self.RED_LOW2, self.RED_HIGH2)
                blue_m = cv2.inRange(sub_hsv, self.BLUE_LOW, self.BLUE_HIGH)
                red_count  = int(cv2.countNonZero(cv2.bitwise_or(r1, r2)))
                blue_count = int(cv2.countNonZero(blue_m))
                clr = "red" if red_count >= blue_count else "blue"
            else:
                clr = color_label

            if stage == 3 and clr == "red":
                # All target makets have a red balloon attached below them.
                # The balloon colour alone is not IFF evidence; it must not be
                # published as an independent enemy track (friendly fire risk).
                # Instead, Stage 3 publishes it as a separate 'balloon' role
                # track so balloon_association.py can link it to its maket.
                perimeter = float(cv2.arcLength(cnt, True))
                if is_probable_balloon_shape(
                    area=area,
                    perimeter=perimeter,
                    width=float(w),
                    height=float(h),
                ):
                    balloon_detections.append((cx, cy, float(w), float(h), area, "red_balloon"))
                    continue

            detections.append((cx, cy, float(w), float(h), area, clr))

        # Tracker güncelle
        active_tracks = self._tracker.update(detections, timestamp_ns=timestamp_ns)

        # Update balloon tracker (Stage 3)
        balloon_active: dict[str, dict[str, Any]] = {}
        if stage == 3 and _CV_OK:
            balloon_active = self._balloon_tracker.update(
                balloon_detections, timestamp_ns=timestamp_ns
            )

        # TrackCandidate listesi üret
        candidates: list[TrackCandidate] = []
        for tid, tr in active_tracks.items():
            clr = tr.get("color", "unknown")
            if stage == 3 and self.classify_colors:
                friend_foe  = "Düşman" if clr == "red" else "Dost" if clr == "blue" else "Bilinmeyen"
                # Tip sınıfı doğrulanmış detector/HEF modeli bağlanana kadar
                # uydurulmaz. Renk yalnız dost/düşman kararını destekler.
                target_type = "Bilinmeyen"
            else:
                friend_foe  = "Bilinmeyen"
                target_type = "Bilinmeyen"

            # Güven skoru: izin yaşı ve alan büyüklüğüne göre (0.3–0.9)
            age_bonus = min(0.3, tr.get("age", 1) * 0.03)
            confidence = min(0.9, 0.3 + age_bonus)

            # Mesafe tahmini (bbox alanı tabanlı — kaba tahmin)
            area_px = max(1.0, tr.get("area", 1.0))
            range_m = min(15.0, self.range_area_k / (area_px ** 0.5))

            # Yatay açı tahmini
            bearing_deg = (
                (tr["cx"] - self.image_width / 2) / self.image_width * self.hfov_deg
            )

            candidate = TrackCandidate(
                    track_id    = tid,
                    cx          = tr["cx"],
                    cy          = tr["cy"],
                    width_px    = tr.get("w", 0.0),
                    height_px   = tr.get("h", 0.0),
                    area_px     = area_px,
                    color       = clr,
                    friend_foe  = friend_foe,
                    target_type = target_type,
                    confidence  = confidence,
                    range_m     = range_m,
                    bearing_deg = bearing_deg,
                    velocity_x_px_s=float(tr.get("velocity_x_px_s", 0.0)),
                    velocity_y_px_s=float(tr.get("velocity_y_px_s", 0.0)),
                    freshness_ms=max(
                        0.0,
                        (timestamp_ns - int(tr.get("last_seen_ns", timestamp_ns))) / 1e6,
                    ),
                    receive_monotonic_ns=timestamp_ns,
                )
            if self.aim_calibration is not None:
                aim = calibrated_aim_error(
                    candidate,
                    self.aim_calibration,
                    now_monotonic_ns=timestamp_ns,
                    aim_point_px=None,  # Future: pass balloon center here
                )
                candidate.aim_valid = bool(aim["valid"])
                candidate.aim_calibration_id = str(aim["calibrationId"])
                candidate.aim_calibration_hash = str(aim["calibrationHash"])
                if candidate.aim_valid:
                    candidate.yaw_error_deg = float(aim["yawErrorDeg"])
                    candidate.pitch_error_deg = float(aim["pitchErrorDeg"])
            candidates.append(candidate)

        # Balloon TrackCandidates (Stage 3 only)
        # fire_candidate=False: balloon tracks can never be direct fire targets.
        # balloon_association.py will link them to their parent maket track.
        for tid, tr in balloon_active.items():
            area_px = max(1.0, tr.get("area", 1.0))
            bearing_deg = (
                (tr["cx"] - self.image_width / 2) / self.image_width * self.hfov_deg
            )
            age_bonus = min(0.3, tr.get("age", 1) * 0.03)
            balloon_candidate = TrackCandidate(
                track_id    = f"{tid}-BAL",
                cx          = tr["cx"],
                cy          = tr["cy"],
                width_px    = tr.get("w", 0.0),
                height_px   = tr.get("h", 0.0),
                area_px     = area_px,
                color       = "red_balloon",
                friend_foe  = "Bilinmeyen",
                target_type = "Balon",
                confidence  = min(0.9, 0.3 + age_bonus),
                range_m     = min(15.0, self.range_area_k / (area_px ** 0.5)),
                bearing_deg = bearing_deg,
                velocity_x_px_s=float(tr.get("velocity_x_px_s", 0.0)),
                velocity_y_px_s=float(tr.get("velocity_y_px_s", 0.0)),
                freshness_ms=max(
                    0.0,
                    (timestamp_ns - int(tr.get("last_seen_ns", timestamp_ns))) / 1e6,
                ),
                receive_monotonic_ns=timestamp_ns,
                object_role="balloon",
                fire_candidate=False,  # balloon cannot be a direct fire target
            )
            candidates.append(balloon_candidate)

        return candidates

    def stats(self) -> dict[str, Any]:
        """Return live frame processing statistics."""
        return {
            "framesProcessed": self._frames_processed,
            "activeTracks":    len(self._tracker.tracks),
        }
