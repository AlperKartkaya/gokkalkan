#!/usr/bin/env python3
"""
Gökkalkan — 1D LiDAR (TFA50-L & TF-Luna / TFmini) Canlı Teşhis ve Test Aracı (Python)

Bu araç:
  1. Takılı USB-Seri dönüştürücüyü otomatik bulur (veya --port ile seçilir).
  2. Doğru baud rate'i (460800, 115200, 921600, 9600) otomatik tarayıp kilitlenir.
  3. Hem 4-Bayt TFA50-L hem de 9-Bayt TFmini/TF-Luna protokollerini otomatik tanır.
  4. Canlı mesafe (m/cm), sinyal gücü, frekans (Hz) ve ham baytları renkli HUD ile gösterir.
  5. Hata durumunda donanım sorun giderme önerileri sunar (RX/TX tersliği, 5V besleme vb.).

Kullanım:
    python realtimetesting/test_lidar.py
    (veya port belirterek: python realtimetesting/test_lidar.py --port COM4 --baud 460800)
"""

from __future__ import annotations

import argparse
import glob
import os
import sys
import time
from typing import NamedTuple

# Windows / Linux UTF-8 terminal encoding fix
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

try:
    import serial
    import serial.tools.list_ports
    HAS_PYSERIAL = True
except ImportError:
    HAS_PYSERIAL = False


# ANSI Renk Kodları
C_RESET = "\033[0m"
C_BOLD = "\033[1m"
C_RED = "\033[91m"
C_GREEN = "\033[92m"
C_YELLOW = "\033[93m"
C_BLUE = "\033[94m"
C_MAGENTA = "\033[95m"
C_CYAN = "\033[96m"
C_WHITE = "\033[97m"
C_BG_GREEN = "\033[42m"
C_BG_RED = "\033[41m"
IS_WINDOWS = os.name == "nt"


class LidarReading(NamedTuple):
    distance_m: float | None
    distance_cm: int
    signal_strength: int | None
    temperature_c: float | None
    protocol: str
    raw_hex: str
    valid: bool


def find_lidar_ports() -> list[str]:
    """Sistemdeki tüm olası LiDAR seri portlarını döner."""
    if not HAS_PYSERIAL:
        return []

    ports = list(serial.tools.list_ports.comports())
    candidates = []

    # Öncelikli USB-Seri dönüştürücüler (CP2102, FTDI, CH340 vb.)
    for p in ports:
        desc = (p.description or "").lower()
        mfr = (p.manufacturer or "").lower()
        dev = p.device.lower()
        if any(
            x in desc or x in mfr or x in dev
            for x in ["cp210", "ftdi", "ch340", "ch341", "uart", "serial", "usb", "ttyusb", "ttyacm"]
        ):
            candidates.append(p.device)
        else:
            candidates.append(p.device)

    # Linux /dev/ yolları
    linux_paths = sorted(
        glob.glob("/dev/serial/by-id/*")
        + glob.glob("/dev/ttyUSB*")
        + glob.glob("/dev/ttyACM*")
    )
    for lp in linux_paths:
        if lp not in candidates:
            candidates.append(lp)

    return candidates


def decode_tfa50l_4byte(frame: bytes) -> LidarReading | None:
    """TFA50-L 4-Bayt Çerçevesi: [0x5C] [Dist_L] [Dist_H] [Checksum]."""
    if len(frame) != 4 or frame[0] != 0x5C:
        return None

    dist_l, dist_h, cs = frame[1], frame[2], frame[3]
    expected_cs = (~((dist_l + dist_h) & 0xFF)) & 0xFF
    if cs != expected_cs:
        return None

    dist_cm = dist_l | (dist_h << 8)
    no_det = dist_cm == 0xFFFF
    return LidarReading(
        distance_m=None if no_det else dist_cm / 100.0,
        distance_cm=dist_cm,
        signal_strength=None,
        temperature_c=None,
        protocol="TFA50-L (4-Bayt @ 460800)",
        raw_hex=frame.hex(" ").upper(),
        valid=not no_det,
    )


def decode_tfmini_9byte(frame: bytes) -> LidarReading | None:
    """TFmini / TF-Luna 9-Bayt Çerçevesi: [0x59] [0x59] [Dist_L] [Dist_H] [Amp_L] [Amp_H] [Temp_L] [Temp_H] [Checksum]."""
    if len(frame) != 9 or frame[0] != 0x59 or frame[1] != 0x59:
        return None

    expected_cs = sum(frame[:8]) & 0xFF
    if frame[8] != expected_cs:
        return None

    dist_cm = frame[2] | (frame[3] << 8)
    strength = frame[4] | (frame[5] << 8)
    temp_raw = frame[6] | (frame[7] << 8)
    temp_c = (temp_raw / 8.0) - 256.0 if temp_raw != 0 else None
    valid = dist_cm > 0 and dist_cm != 0xFFFF

    return LidarReading(
        distance_m=dist_cm / 100.0 if valid else None,
        distance_cm=dist_cm,
        signal_strength=strength,
        temperature_c=round(temp_c, 1) if temp_c is not None else None,
        protocol="TF-Luna / TFmini (9-Bayt @ 115200)",
        raw_hex=frame.hex(" ").upper(),
        valid=valid,
    )


class UniversalLidarDecoder:
    """Hem TFA50-L (4-bayt) hem de TFmini (9-bayt) protokollerini eşzamanlı çözer."""

    def __init__(self) -> None:
        self.buffer = bytearray()
        self.valid_count = 0
        self.rejected_count = 0

    def feed(self, chunk: bytes) -> list[LidarReading]:
        self.buffer.extend(chunk)
        readings: list[LidarReading] = []

        while len(self.buffer) >= 4:
            # 1. TFA50-L Başlığı (0x5C)
            if self.buffer[0] == 0x5C:
                candidate = bytes(self.buffer[:4])
                reading = decode_tfa50l_4byte(candidate)
                if reading is not None:
                    readings.append(reading)
                    self.valid_count += 1
                    del self.buffer[:4]
                    continue
                else:
                    self.rejected_count += 1
                    del self.buffer[0]
                    continue

            # 2. TFmini / TF-Luna Başlığı (0x59 0x59)
            elif self.buffer[0] == 0x59:
                if len(self.buffer) < 2:
                    break
                if self.buffer[1] == 0x59:
                    if len(self.buffer) < 9:
                        break  # 9 baytın tamamlanmasını bekle
                    candidate = bytes(self.buffer[:9])
                    reading = decode_tfmini_9byte(candidate)
                    if reading is not None:
                        readings.append(reading)
                        self.valid_count += 1
                        del self.buffer[:9]
                        continue
                    else:
                        self.rejected_count += 1
                        del self.buffer[0]
                        continue
                else:
                    del self.buffer[0]
                    continue
            else:
                del self.buffer[0]

        # Aşırı buffer taşmasını önle
        if len(self.buffer) > 1024:
            self.buffer.clear()

        return readings


def auto_detect_baud_and_protocol(port: str) -> tuple[int | None, str | None]:
    """Port üzerindeki doğru baud rate ve protokolü tespit eder."""
    baud_candidates = [115200, 460800, 921600, 9600, 57600]

    for baud in baud_candidates:
        sys.stdout.write(f"\r  [*] {port} portu {baud} baud ile taranıyor... ")
        sys.stdout.flush()

        try:
            ser = serial.Serial(port=port, baudrate=baud, timeout=0.25)
            decoder = UniversalLidarDecoder()
            start_t = time.time()
            valid_samples = 0
            detected_proto = None

            while time.time() - start_t < 0.6:
                chunk = ser.read(64)
                if chunk:
                    for r in decoder.feed(chunk):
                        if r.distance_m is not None or r.valid:
                            valid_samples += 1
                            detected_proto = r.protocol
                            if valid_samples >= 3:
                                ser.close()
                                return baud, detected_proto

            ser.close()
        except Exception:
            continue

    return None, None


def render_distance_bar(dist_m: float | None, max_m: float = 30.0, bar_len: int = 30) -> str:
    """Mesafeyi görsel bir çubuğa dönüştürür."""
    if dist_m is None:
        return f"{C_RED}[ SİNYAL YOK / MENZİL DIŞI ]{C_RESET}"

    ratio = min(1.0, max(0.0, dist_m / max_m))
    filled = int(round(ratio * bar_len))

    # Renk kademeleri: <3m Sarı, 3-15m Yeşil, >15m Mavi
    if dist_m < 3.0:
        bar_color = C_YELLOW
    elif dist_m <= 15.0:
        bar_color = C_GREEN
    else:
        bar_color = C_CYAN

    bar = f"{bar_color}" + "█" * filled + f"{C_RESET}" + "░" * (bar_len - filled)
    return f"[{bar}] {C_BOLD}{dist_m:5.2f} m{C_RESET}"


def run_lidar_diagnostics(port: str, baudrate: int | None = None) -> int:
    print(f"\n{C_CYAN}{C_BOLD}" + "=" * 68 + f"{C_RESET}")
    print(f"{C_CYAN}{C_BOLD} 📡 GÖKKALKAN — 1D LİDAR CANLI TEŞHİS VE TEST MONİTÖRÜ{C_RESET}")
    print(f"{C_CYAN}" + "=" * 68 + f"{C_RESET}")

    detected_baud = baudrate
    detected_proto = None

    if detected_baud is None:
        print(f"[*] Port otomatik baud taramasına alınıyor ({port})...")
        detected_baud, detected_proto = auto_detect_baud_and_protocol(port)

        if detected_baud is None:
            print(f"\n\n{C_YELLOW}[!] Otomatik baud tespit edilemedi!{C_RESET}")
            print(f"{C_YELLOW}[*] Varsayılan 115200 baud (TF-Luna/TFmini standardı) ile deneniyor...{C_RESET}")
            detected_baud = 115200
        else:
            print(f"\n{C_GREEN}[✓] Algılandı: {detected_baud} Baud | {detected_proto}{C_RESET}")

    print(f"[*] {port} açılıyor ({detected_baud} baud)...")
    try:
        ser = serial.Serial(port=port, baudrate=detected_baud, timeout=0.1)
    except Exception as exc:
        print(f"{C_RED}[HATA] Port açılamadı ({port}): {exc}{C_RESET}")
        return 1

    decoder = UniversalLidarDecoder()

    fps_count = 0
    fps_start = time.time()
    current_fps = 0.0

    last_reading: LidarReading | None = None
    bytes_received = 0
    no_data_start = time.time()

    print(f"{C_GREEN}[✓] LiDAR dinleniyor... Çıkmak için Ctrl+C tuşlayın.{C_RESET}\n")

    try:
        while True:
            chunk = ser.read(128)
            now = time.time()

            if chunk:
                no_data_start = now
                bytes_received += len(chunk)
                readings = decoder.feed(chunk)

                for r in readings:
                    last_reading = r
                    fps_count += 1

            if now - fps_start >= 1.0:
                current_fps = fps_count / (now - fps_start)
                fps_count = 0
                fps_start = now

            # Canlı HUD Çizimi
            if IS_WINDOWS:
                sys.stdout.write("\033[H")
            else:
                sys.stdout.write("\033[H")

            out = []
            out.append(f"{C_CYAN}{C_BOLD}" + "=" * 68 + f"{C_RESET}")
            out.append(f"{C_CYAN}{C_BOLD} 📡 1D LİDAR CANLI VERİ AKIŞI (TEŞHİS MONİTÖRÜ){C_RESET}")
            out.append(f"{C_CYAN}" + "=" * 68 + f"{C_RESET}")
            out.append(
                f"  Port: {C_GREEN}{port}{C_RESET} | Baud: {C_WHITE}{detected_baud}{C_RESET} | "
                f"Protokol: {C_YELLOW}{last_reading.protocol if last_reading else 'BEKLENİYOR'}{C_RESET}"
            )
            out.append(f"{C_CYAN}" + "-" * 68 + f"{C_RESET}")

            if last_reading and last_reading.distance_m is not None:
                dist_m = last_reading.distance_m
                dist_cm = last_reading.distance_cm
                bar_display = render_distance_bar(dist_m)

                out.append(f"  {C_BOLD}📏 ÖLÇÜLEN MESAFE :{C_RESET} {C_GREEN}{C_BOLD}{dist_m:6.2f} m{C_RESET} ({dist_cm} cm)")
                out.append(f"  {C_BOLD}📊 MESAFE ÇUBUĞU  :{C_RESET} {bar_display}")
                out.append("")

                str_val = f"{last_reading.signal_strength}" if last_reading.signal_strength is not None else "N/A"
                temp_val = f"{last_reading.temperature_c} °C" if last_reading.temperature_c is not None else "N/A"
                out.append(f"  {C_BOLD}📶 Sinyal Gücü   :{C_RESET} {C_WHITE}{str_val:<10}{C_RESET} | {C_BOLD}Sıcaklık:{C_RESET} {C_WHITE}{temp_val}{C_RESET}")
                out.append(f"  {C_BOLD}⚡ Örnekleme Hızı:{C_RESET} {C_CYAN}{current_fps:5.1f} Hz / FPS{C_RESET}")
                out.append(f"  {C_BOLD}📦 Ham Paket (Hex):{C_RESET} {C_YELLOW}{last_reading.raw_hex}{C_RESET}")
            else:
                time_since_data = now - no_data_start
                out.append(f"  {C_RED}[!] CANLI MESAFE VERİSİ ALINAMIYOR{C_RESET}")
                out.append(f"  Son Veri Alınma : {time_since_data:.1f} saniye önce")
                out.append(f"  Toplam Bayt     : {bytes_received} bayt")
                out.append("")
                out.append(f"  {C_YELLOW}🛠️ DONANIM KONTROL LİSTESİ:{C_RESET}")
                out.append("    1. Sensörün RX ve TX uçlarının çapraz bağlı olduğundan emin olun (TX->RX, RX->TX).")
                out.append("    2. LiDAR'ın 5V ve GND beslemesinin yeterli akım (en az 500mA) aldığını kontrol edin.")
                out.append("    3. Merceğin önünde engel veya koruyucu film olup olmadığını kontrol edin.")

            out.append(f"{C_CYAN}" + "-" * 68 + f"{C_RESET}")
            out.append(
                f"  Geçerli Paket: {C_GREEN}{decoder.valid_count}{C_RESET} | "
                f"Hatalı/Bozuk: {C_RED}{decoder.rejected_count}{C_RESET} | "
                f"Çıkış: {C_WHITE}Ctrl+C{C_RESET}"
            )
            out.append(f"{C_CYAN}" + "=" * 68 + f"{C_RESET}")

            sys.stdout.write("\n".join(out) + "\n")
            sys.stdout.flush()

            time.sleep(0.04)

    except KeyboardInterrupt:
        pass
    finally:
        ser.close()
        print(f"\n{C_GREEN}[✓] LiDAR portu kapatıldı. Test sonlandırıldı.{C_RESET}\n")

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Gökkalkan 1D LiDAR (TFA50-L & TF-Luna) Canlı Teşhis ve Test Aracı"
    )
    parser.add_argument(
        "--port",
        "-p",
        default=None,
        help="LiDAR Seri Portu (Örn: COM4 veya /dev/ttyUSB0). Belirtilmezse otomatik taranır.",
    )
    parser.add_argument(
        "--baud",
        "-b",
        type=int,
        default=None,
        help="Baud Rate (Varsayılan: Otomatik Tespit — 460800 / 115200)",
    )

    args = parser.parse_args()

    if not HAS_PYSERIAL:
        print(f"{C_RED}[HATA] 'pyserial' kütüphanesi eksik!{C_RESET}")
        print("Yüklemek için terminale yazın: pip install pyserial")
        return 1

    port = args.port
    if not port:
        ports = find_lidar_ports()
        if not ports:
            print(f"{C_RED}[HATA] Sistemde aktif bir seri port (USB-UART) tespit edilemedi!{C_RESET}")
            print("Lütfen LiDAR USB dönüştürücüsünün bilgisayara takılı olduğundan emin olun.")
            return 1
        port = ports[0]
        if len(ports) > 1:
            print(f"[*] Birden fazla port bulundu: {', '.join(ports)}")
            print(f"[*] Birincil seçilen: {port}")

    return run_lidar_diagnostics(port=port, baudrate=args.baud)


if __name__ == "__main__":
    sys.exit(main())
