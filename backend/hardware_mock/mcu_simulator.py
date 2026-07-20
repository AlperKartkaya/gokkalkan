#!/usr/bin/env python3
"""Gökkalkan Pico RP2040 MCU Simülatörü.

Sanal CAN (vcan0 / python-can virtual) üzerinden gelen komutları alır,
gerçek Pico'nun davranışını taklit eder ve terminal üzerinde görselleştirir.

Kullanım:
  # Linux/RPi5 — vcan0 gerektiriyor (bkz. scripts/setup_virtual_can.sh):
  python backend/hardware_mock/mcu_simulator.py --channel vcan0 --bustype socketcan

  # macOS / cross-platform (OS kurulum gerektirmez):
  python backend/hardware_mock/mcu_simulator.py --channel test --bustype virtual

  # Durum paketiyle:
  python backend/hardware_mock/mcu_simulator.py --bustype virtual --verbose

Klavye Komutları (simülatör çalışırken):
  e   → E-Stop geçiş (aktif / pasif)
  r   → pozisyonu sıfırla (pan=0 tilt=0)
  q   → çıkış

python-can paket kurulumu: pip install python-can
"""

from __future__ import annotations

import argparse
import logging
import sys
import threading
import time
import os
import datetime

# hardware_adapter modülünü proje kökünden içe aktar
sys.path.insert(0, "backend/src")

from gokkalkan_backend.hardware_adapter import (
    CENTIDEG_PER_DEG,
    CAN_ID_ESTOP_EVENT,
    CAN_ID_FIRE_CMD,
    CAN_ID_PANTILT_CMD,
    CAN_ID_STATUS,
    CAN_ID_SYS_CMD,
    pack_status,
    unpack_pantilt_cmd,
)

logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Terminal görselleştirme sabitleri
# ---------------------------------------------------------------------------
PAN_DISPLAY_RANGE  = 90.0   # ±90° görüntüleme penceresi
TILT_DISPLAY_RANGE = 45.0   # ±45° görüntüleme penceresi
BAR_WIDTH          = 40     # karakter genişliği

STATUS_INTERVAL_SEC = 0.1   # Pico→RPi5 durum paketi gönderim sıklığı


def _bar(value: float, range_max: float, width: int = BAR_WIDTH) -> str:
    """Değeri [-range_max, +range_max] aralığında yatay çubuk olarak göster."""
    half  = width // 2
    ratio = max(-1.0, min(1.0, value / range_max))
    pos   = int(ratio * half) + half
    bar   = ["-"] * width
    bar[half] = "|"           # merkez
    bar[pos]  = "█"           # mevcut konum
    return "".join(bar)


def _render(
    pan_deg: float,
    tilt_deg: float,
    estop: bool,
    fire_count: int,
    cmd_count: int,
) -> str:
    """Mevcut durumu terminal çıktısına dönüştür."""
    estop_str = "🔴 AKTİF" if estop else "🟢 pasif"
    lines = [
        "╔══════════════════════════════════════════════╗",
        "║   GÖKKALKAN MCU SİMÜLATÖRÜ  (Pico RP2040)   ║",
        "╠══════════════════════════════════════════════╣",
        f"║  Pan  [{_bar(pan_deg,  PAN_DISPLAY_RANGE)}]  {pan_deg:+.2f}°  ║",
        f"║  Tilt [{_bar(tilt_deg, TILT_DISPLAY_RANGE)}]  {tilt_deg:+.2f}°  ║",
        "╠══════════════════════════════════════════════╣",
        f"║  E-Stop : {estop_str:<35}║",
        f"║  Ateş   : {fire_count:<35}║",
        f"║  Komut  : {cmd_count:<35}║",
        "╠══════════════════════════════════════════════╣",
        "║  [e]=E-Stop geçiş  [r]=sıfırla  [q]=çıkış   ║",
        "╚══════════════════════════════════════════════╝",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Simülatör çekirdeği
# ---------------------------------------------------------------------------

class McuSimulator:
    """Pico MCU davranışını taklit eden sanal CAN simülatörü."""

    def __init__(self, channel: str, bustype: str, verbose: bool = False) -> None:
        self.channel = channel
        self.bustype = bustype
        self.verbose = verbose

        self.pan_deg:   float = 0.0
        self.tilt_deg:  float = 0.0
        self.estop:     bool  = False
        self.fire_count: int  = 0
        self.cmd_count:  int  = 0

        self._bus: object      = None
        self._running: bool    = False
        self._lock             = threading.Lock()

        os.makedirs("telemetry_data", exist_ok=True)
        self.log_file_path = "telemetry_data/vcan_logs.txt"

    def _log_event(self, message: str) -> None:
        timestamp = datetime.datetime.now().isoformat()
        with open(self.log_file_path, "a", encoding="utf-8") as f:
            f.write(f"[{timestamp}] {message}\n")

    # ------------------------------------------------------------------
    # CAN bus kurulumu
    # ------------------------------------------------------------------

    def _open(self) -> bool:
        try:
            import can
            self._bus = can.interface.Bus(
                channel=self.channel, bustype=self.bustype
            )
            return True
        except ImportError:
            print(
                "\n[HATA] python-can bulunamadı.\n"
                "Kurulum: pip install python-can\n"
            )
            return False
        except Exception as exc:
            print(f"\n[HATA] CAN bus açılamadı ({self.channel}/{self.bustype}): {exc}\n")
            return False

    # ------------------------------------------------------------------
    # RX — gelen komutları işle
    # ------------------------------------------------------------------

    def _rx_loop(self) -> None:
        while self._running:
            if self._bus is None:
                time.sleep(0.5)
                continue
            try:
                import can
                msg: can.Message | None = self._bus.recv(timeout=0.5)  # type: ignore[attr-defined]
                if msg is None:
                    continue
                self._handle_message(msg)
            except Exception as exc:
                if self._running:
                    logger.debug("RX hatası: %s", exc)

    def _handle_message(self, msg: object) -> None:
        arb_id = msg.arbitration_id  # type: ignore[attr-defined]
        data   = bytes(msg.data)     # type: ignore[attr-defined]

        with self._lock:
            self.cmd_count += 1

            if arb_id == CAN_ID_PANTILT_CMD:
                parsed = unpack_pantilt_cmd(data)
                if parsed:
                    self.pan_deg  = parsed["panDeg"]
                    self.tilt_deg = parsed["tiltDeg"]
                    if self.verbose:
                        msg = (f"PanTilt: pan={self.pan_deg:+.2f}°  "
                               f"tilt={self.tilt_deg:+.2f}°  "
                               f"rate={parsed['rateDegPerSec']:.1f}°/s  "
                               f"deadman={parsed['deadmanActive']}")
                        print(f"\n  ← {msg}")
                        self._log_event(msg)
                else:
                    print("\n  [UYARI] PanTilt paketi checksum hatası!")
                    self._log_event("PanTilt paketi checksum hatası!")

            elif arb_id == CAN_ID_FIRE_CMD:
                if data and data[0] == 0x01:
                    self.fire_count += 1
                    stage = data[1] if len(data) > 1 else "?"
                    msg = f"ATEŞ KOMUTU #{self.fire_count} alındı — Aşama {stage}"
                    print(f"\n  🔥 {msg}")
                    self._log_event(msg)
                else:
                    msg = "Ateş iptal komutu alındı."
                    print(f"\n  ⛔ {msg}")
                    self._log_event(msg)

            elif arb_id == CAN_ID_SYS_CMD:
                arm = bool(data[0]) if data else False
                msg = f"Sistem komutu: {'ARM' if arm else 'DISARM'}"
                print(f"\n  ⚙ {msg}")
                self._log_event(msg)

    # ------------------------------------------------------------------
    # TX — periyodik durum paketi (Pico → RPi5)
    # ------------------------------------------------------------------

    def _tx_status_loop(self) -> None:
        while self._running:
            time.sleep(STATUS_INTERVAL_SEC)
            if self._bus is None:
                continue
            with self._lock:
                pan_c  = int(self.pan_deg  * CENTIDEG_PER_DEG)
                tilt_c = int(self.tilt_deg * CENTIDEG_PER_DEG)
                estop  = self.estop
            try:
                import can
                payload = pack_status(
                    pan_centideg=pan_c,
                    tilt_centideg=tilt_c,
                    estop_active=estop,
                    motion_ok=not estop,
                    fire_ready=not estop,
                )
                frame = can.Message(
                    arbitration_id=CAN_ID_STATUS,
                    data=payload,
                    is_extended_id=False,
                )
                self._bus.send(frame)  # type: ignore[attr-defined]
            except Exception as exc:
                logger.debug("TX durum hatası: %s", exc)

    def _send_estop_event(self, active: bool) -> None:
        if self._bus is None:
            return
        try:
            import can
            frame = can.Message(
                arbitration_id=CAN_ID_ESTOP_EVENT,
                data=bytes([0x01 if active else 0x00]),
                is_extended_id=False,
            )
            self._bus.send(frame)  # type: ignore[attr-defined]
            msg = f"{'E-STOP AKTİF' if active else 'E-Stop pasif'} — CAN olayı gönderildi."
            print(f"\n  {'🔴' if active else '🟢'} {msg}")
            self._log_event(msg)
        except Exception as exc:
            logger.warning("E-Stop olayı gönderilemedi: %s", exc)

    # ------------------------------------------------------------------
    # Klavye girişi
    # ------------------------------------------------------------------

    def _keyboard_loop(self) -> None:
        """Basit satır tabanlı klavye girişi (cross-platform)."""
        while self._running:
            try:
                key = input().strip().lower()
            except EOFError:
                break
            if key == "q":
                print("\nÇıkılıyor...")
                self._running = False
            elif key == "e":
                with self._lock:
                    self.estop = not self.estop
                    active = self.estop
                self._send_estop_event(active)
            elif key == "r":
                with self._lock:
                    self.pan_deg  = 0.0
                    self.tilt_deg = 0.0
                print("\n  Pozisyon sıfırlandı.")

    # ------------------------------------------------------------------
    # Render döngüsü
    # ------------------------------------------------------------------

    def _render_loop(self) -> None:
        while self._running:
            with self._lock:
                pan, tilt = self.pan_deg, self.tilt_deg
                estop      = self.estop
                fires      = self.fire_count
                cmds       = self.cmd_count
            # Terminali temizle ve yeniden çiz
            print("\033[2J\033[H", end="")
            print(_render(pan, tilt, estop, fires, cmds))
            time.sleep(0.1)

    # ------------------------------------------------------------------
    # Çalıştır / Durdur
    # ------------------------------------------------------------------

    def run(self) -> None:
        if not self._open():
            sys.exit(1)

        self._running = True
        threads = [
            threading.Thread(target=self._rx_loop,        daemon=True, name="SIM-RX"),
            threading.Thread(target=self._tx_status_loop, daemon=True, name="SIM-TX"),
            threading.Thread(target=self._render_loop,    daemon=True, name="SIM-UI"),
        ]
        for t in threads:
            t.start()

        print(f"MCU Simülatörü başlatıldı — kanal={self.channel} bustype={self.bustype}")
        print("Komutlar: [e]=E-Stop  [r]=sıfırla  [q]=çıkış")
        print("Klavye girişi için Enter'a bas.\n")

        try:
            self._keyboard_loop()
        except KeyboardInterrupt:
            pass
        finally:
            self._running = False
            if self._bus is not None:
                try:
                    self._bus.shutdown()  # type: ignore[attr-defined]
                except Exception:
                    pass
            print("\nSimülatör kapatıldı.")


# ---------------------------------------------------------------------------
# Giriş noktası
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Gökkalkan Pico MCU Simülatörü — sanal CAN üzerinden test",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--channel", default="vcan0",
        help="CAN kanal adı: 'vcan0' (socketcan), 'test' (virtual)"
    )
    parser.add_argument(
        "--bustype", default="socketcan",
        help="python-can bus tipi: 'socketcan', 'virtual', 'pcan', 'kvaser' vb."
    )
    parser.add_argument(
        "--verbose", action="store_true",
        help="Her gelen paketi ayrıntılı yazdır"
    )
    args = parser.parse_args()

    sim = McuSimulator(channel=args.channel, bustype=args.bustype, verbose=args.verbose)
    sim.run()


if __name__ == "__main__":
    main()
