#!/usr/bin/env python3
"""
Gökkalkan - Raspberry Pi 5 -> Arduino Uno 15 Saniyelik Motor Test Scripti

Bu script:
1. Raspberry Pi (veya test bilgisayarı) ile Arduino Uno arasındaki USB Seri portu bulur.
2. Arduino Uno'ya 15 saniyelik motor döndürme komutu gönderir.
3. 15 saniye boyunca terminalde canlı ilerleme çubuğu ve kalan süre gösterir.
4. İstenirse Ctrl+C ile motor anında güvenli bir şekilde durdurulur (STOP komutu).
"""

from __future__ import annotations

import argparse
import glob
import os
import sys
import time

FIELD_PROFILE = "GKK-UNO-DM542-1600PPR-R1"
MAX_DURATION_SEC = 15
MAX_SPEED_HZ = 1250

# Cross-platform UTF-8 terminal encoding fix
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


def find_arduino_port() -> str | None:
    """Sistemde takılı olan Arduino Uno seri portunu otomatik tespit eder."""
    if not HAS_PYSERIAL:
        print("[!] 'pyserial' modülü bulunamadı. Kurmak için: pip install pyserial")
        return None

    # 1. USB VID/PID veya donanım açıklamasına göre ara
    ports = list(serial.tools.list_ports.comports())
    for p in ports:
        desc = (p.description or "").lower()
        mfr = (p.manufacturer or "").lower()
        if "arduino" in desc or "arduino" in mfr or "ch340" in desc or "ch340" in mfr or "ttyacm" in p.device.lower():
            return p.device

    # 2. Linux /dev/ttyACM* ve /dev/ttyUSB* yolları
    candidates = sorted(glob.glob("/dev/ttyACM*") + glob.glob("/dev/ttyUSB*"))
    if candidates:
        return candidates[0]

    # 3. İlk aktif port
    if ports:
        return ports[0].device

    return None


def run_motor_test(
    port: str,
    duration: int = 15,
    speed_hz: int = 800,
    motor: str = "both",
    direction: str = "CW",
    baudrate: int = 115200,
) -> int:
    if not HAS_PYSERIAL:
        print("[HATA] Lütfen 'pyserial' kütüphanesini yükleyin: pip install pyserial")
        return 1
    if not 1 <= duration <= MAX_DURATION_SEC:
        print(f"[HATA] Süre 1-{MAX_DURATION_SEC} saniye arasında olmalıdır.")
        return 2
    if not 1 <= speed_hz <= MAX_SPEED_HZ:
        print(f"[HATA] Hız 1-{MAX_SPEED_HZ} Hz arasında olmalıdır.")
        return 2

    print("=" * 60)
    print(" GÖKKALKAN - ARDUINO UNO 15 SANİYE MOTOR DÖNDÜRME TESTİ")
    print("=" * 60)
    print(f"[*] Hedef Port     : {port}")
    print(f"[*] Baud Rate      : {baudrate}")
    print(f"[*] Motor Seçimi   : {motor.upper()}")
    print(f"[*] Süre           : {duration} Saniye")
    print(f"[*] Hız            : {speed_hz} Hz (Adım/sn)")
    print(f"[*] Yön            : {direction.upper()}")
    print("-" * 60)

    try:
        ser = serial.Serial(port=port, baudrate=baudrate, timeout=1.0)
    except Exception as exc:
        print(f"[HATA] Seri port açılamadı ({port}): {exc}")
        print("[İpucu] Linux/Pi'de kullanıcı izni için: sudo usermod -a -G dialout $USER")
        return 1

    try:
        print("[*] Arduino Uno'ya bağlanılıyor (Bootloader bekleniyor)...")
        time.sleep(2.0)  # Arduino DTR resetinin tamamlanmasını bekle

        # Buffer'ı temizle
        ser.reset_input_buffer()
        ser.reset_output_buffer()

        # 1. Firmware kimliği doğrulaması. Eski/başka bir seri cihazın motor
        # komutu almasını önlemek için PROFILE uyuşmadan RUN gönderilmez.
        ser.write(b"PING\n")
        time.sleep(0.1)
        resp = ser.readline().decode("utf-8", errors="ignore").strip()
        print(f"[<] Arduino Yanıtı : {resp if resp else '(Cevap alınamadı)'}")
        if resp != "PONG":
            print("[HATA] PING/PONG doğrulanamadı; motor komutu gönderilmedi.")
            return 2

        ser.write(b"PROFILE\n")
        time.sleep(0.1)
        profile_resp = ser.readline().decode("utf-8", errors="ignore").strip()
        expected_profile = f"PROFILE {FIELD_PROFILE}"
        print(f"[<] Firmware Profili: {profile_resp if profile_resp else '(Cevap alınamadı)'}")
        if profile_resp != expected_profile:
            print(
                "[HATA] Uyumlu saha firmware'i doğrulanamadı; motor komutu gönderilmedi. "
                f"Beklenen: {expected_profile}"
            )
            return 2

        # 2. Komut Hazırlama
        motor_lower = motor.lower()
        if motor_lower == "pan":
            cmd = f"RUN_PAN {duration} {speed_hz} {direction}\n"
        elif motor_lower == "tilt":
            cmd = f"RUN_TILT {duration} {speed_hz} {direction}\n"
        else:
            cmd = f"RUN {duration} {speed_hz} {direction}\n"

        print(f"[>] Komut Gönderiliyor: {cmd.strip()}")
        ser.write(cmd.encode("ascii"))
        time.sleep(0.1)

        # Onay yanıtını oku
        ack = ser.readline().decode("utf-8", errors="ignore").strip()
        print(f"[<] Başlatma Onayı : {ack}")

        if "OK RUNNING" not in ack:
            print("[HATA] Beklenen 'OK RUNNING' onayı gelmedi; güvenli STOP gönderiliyor.")
            ser.write(b"STOP\n")
            return 2

        print("\n" + "=" * 60)
        print(f"[*] MOTOR DÖNÜYOR ({duration} SANİYE)... (Durdurmak için Ctrl+C)")
        print("=" * 60)

        # 3. 15 Saniyelik Canlı Geri Sayım
        start_time = time.time()
        while True:
            elapsed = time.time() - start_time
            remaining = max(0.0, duration - elapsed)
            percent = min(100.0, (elapsed / duration) * 100.0)
            bar_len = 30
            filled = int(bar_len * (percent / 100.0))
            bar = "#" * filled + "-" * (bar_len - filled)

            sys.stdout.write(
                f"\r[{bar}] %{percent:5.1f} | Geçen: {elapsed:4.1f}s | Kalan: {remaining:4.1f}s "
            )
            sys.stdout.flush()

            if elapsed >= duration:
                break

            # Seri hattan mesaj gelmiş mi kontrol et
            if ser.in_waiting > 0:
                line = ser.readline().decode("utf-8", errors="ignore").strip()
                if line and "COMPLETED" in line:
                    break

            time.sleep(0.1)

        print("\n")
        time.sleep(0.5)

        # Bitiş durumu oku
        while ser.in_waiting > 0:
            final_msg = ser.readline().decode("utf-8", errors="ignore").strip()
            if final_msg:
                print(f"[<] Arduino Sonuç : {final_msg}")

        print("=" * 60)
        print("[+] Komut zaman penceresi tamamlandı; fiziksel hareket/konum kabulü ayrıca ölçülmelidir.")
        print("=" * 60)
        return 0

    except KeyboardInterrupt:
        print("\n\n[!] KULLANICI TARAFINDAN KESİLDİ! ACİL DURDURULUYOR...")
        try:
            ser.write(b"STOP\n")
            time.sleep(0.2)
            stop_resp = ser.readline().decode("utf-8", errors="ignore").strip()
            print(f"[<] Durdurma Yanıtı: {stop_resp}")
        except Exception:
            pass
        return 130

    finally:
        ser.close()
        print("[*] Seri port kapatıldı.")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Gökkalkan Arduino Uno 15 Saniyelik Motor Test Aracı"
    )
    parser.add_argument(
        "--port",
        "-p",
        default=None,
        help="Arduino Uno Seri Portu (Örn: /dev/ttyACM0 veya COM3). Verilmezse otomatik bulunur.",
    )
    parser.add_argument(
        "--duration",
        "-d",
        type=int,
        default=15,
        help="Çalışma süresi (Saniye, Varsayılan: 15)",
    )
    parser.add_argument(
        "--speed",
        "-s",
        type=int,
        default=800,
        help="Step Frekansı / Hız (Hz, Varsayılan: 800 Adım/sn)",
    )
    parser.add_argument(
        "--motor",
        "-m",
        choices=("pan", "tilt", "both"),
        default="pan",
        help="Sürülecek motor (pan: 1. Motor Pin 2/3, tilt: 2. Motor Pin 4/5, both: İkisi - Varsayılan: pan)",
    )
    parser.add_argument(
        "--direction",
        choices=("CW", "CCW"),
        default="CW",
        help="Dönüş yönü (CW: Saat yönü, CCW: Ters saat yönü - Varsayılan: CW)",
    )
    parser.add_argument(
        "--baudrate",
        "-b",
        type=int,
        default=115200,
        help="Baud rate (Varsayılan: 115200)",
    )

    args = parser.parse_args()

    port = args.port
    if not port:
        port = find_arduino_port()
        if not port:
            print("[HATA] Arduino Uno portu bulunamadı. Lütfen --port /dev/ttyACM0 şeklinde belirtin.")
            return 1
        print(f"[*] Otomatik tespit edilen port: {port}")

    return run_motor_test(
        port=port,
        duration=args.duration,
        speed_hz=args.speed,
        motor=args.motor,
        direction=args.direction,
        baudrate=args.baudrate,
    )


if __name__ == "__main__":
    sys.exit(main())
