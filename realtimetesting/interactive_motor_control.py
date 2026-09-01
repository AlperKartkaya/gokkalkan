#!/usr/bin/env python3
"""
Gökkalkan - İnteraktif Arduino Uno & DM542 Motor Test ve Kontrol Paneli (Python)

Pin Tanımları:
  - 1. Motor (PAN)  : Pin 2 (PUL+), Pin 3 (DIR+)
  - 2. Motor (TILT) : Pin 4 (PUL+), Pin 5 (DIR+)
  - Ortak Katot     : Arduino GND -> Tüm DM542 PUL- ve DIR- uçlarına
"""

from __future__ import annotations

import glob
import os
import sys
import time

FIELD_PROFILE = "GKK-UNO-DM542-1600PPR-R1"

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
C_RESET  = "\033[0m"
C_BOLD   = "\033[1m"
C_RED    = "\033[91m"
C_GREEN  = "\033[92m"
C_YELLOW = "\033[93m"
C_BLUE   = "\033[94m"
C_CYAN   = "\033[96m"


def print_banner():
    print(f"{C_CYAN}{C_BOLD}" + "=" * 65 + f"{C_RESET}")
    print(f"{C_CYAN}{C_BOLD} 🚀 GÖKKALKAN - ARDUINO UNO STEP MOTOR KONTROL PANELİ (PYTHON){C_RESET}")
    print(f"{C_CYAN}" + "=" * 65 + f"{C_RESET}")
    print(f"  • 1. Motor (PAN)  : {C_YELLOW}Pin 2 (PUL+){C_RESET} | {C_YELLOW}Pin 3 (DIR+){C_RESET}")
    print(f"  • 2. Motor (TILT) : {C_YELLOW}Pin 4 (PUL+){C_RESET} | {C_YELLOW}Pin 5 (DIR+){C_RESET}")
    print(f"  • Ortak Katot     : {C_YELLOW}GND -> Tüm DM542 PUL- ve DIR- uçlarına{C_RESET}")
    print(f"{C_CYAN}" + "-" * 65 + f"{C_RESET}")


def list_and_find_ports() -> list[str]:
    """Sistemdeki tüm seri portları listeler."""
    if not HAS_PYSERIAL:
        return []
    return [p.device for p in serial.tools.list_ports.comports()]


def auto_detect_port() -> str | None:
    """Arduino veya USB-Seri dönüştürücüyü otomatik tespit eder."""
    if not HAS_PYSERIAL:
        return None
    
    ports = list(serial.tools.list_ports.comports())
    for p in ports:
        desc = (p.description or "").lower()
        mfr = (p.manufacturer or "").lower()
        dev = p.device.lower()
        if "arduino" in desc or "arduino" in mfr or "ch340" in desc or "ch340" in mfr or "ttyacm" in dev or "ttyusb" in dev:
            return p.device

    candidates = sorted(glob.glob("/dev/ttyACM*") + glob.glob("/dev/ttyUSB*"))
    if candidates:
        return candidates[0]

    if ports:
        return ports[0].device

    return None


def send_cmd(ser: serial.Serial, cmd: str) -> str:
    """Arduino'ya komut gönderir ve gelen yanıtı döner."""
    try:
        ser.reset_input_buffer()
        ser.write((cmd.strip() + "\n").encode("ascii"))
        time.sleep(0.12)
        resp_lines = []
        while ser.in_waiting > 0:
            line = ser.readline().decode("utf-8", errors="ignore").strip()
            if line:
                resp_lines.append(line)
        return " | ".join(resp_lines) if resp_lines else "(Yanıt yok)"
    except Exception as exc:
        return f"(Hata: {exc})"


def monitor_progress(ser: serial.Serial, duration_sec: int, motor_name: str, direction: str):
    """Canlı ilerleme çubuğu ve geri sayım gösterir."""
    print(f"\n{C_YELLOW}[*] {motor_name} ÇALIŞIYOR... ({duration_sec} sn | {direction}){C_RESET}")
    print(f"{C_RED}[!] İstediğiniz an durdurmak için Ctrl+C tuşlayın.{C_RESET}\n")

    start_time = time.time()
    bar_length = 32

    try:
        while True:
            elapsed = time.time() - start_time
            remaining = max(0.0, duration_sec - elapsed)
            percent = min(100.0, (elapsed / duration_sec) * 100.0)

            filled = int(bar_length * (percent / 100.0))
            bar = f"{C_GREEN}" + "#" * filled + f"{C_RESET}" + "-" * (bar_length - filled)

            sys.stdout.write(
                f"\r  [{bar}] {C_BOLD}%{percent:5.1f}{C_RESET} | Geçen: {elapsed:4.1f}s | Kalan: {C_CYAN}{remaining:4.1f}s{C_RESET} "
            )
            sys.stdout.flush()

            if elapsed >= duration_sec:
                break

            if ser.in_waiting > 0:
                line = ser.readline().decode("utf-8", errors="ignore").strip()
                if "COMPLETED" in line:
                    break

            time.sleep(0.08)

        print(
            f"\n\n{C_GREEN}{C_BOLD}[✓] {motor_name} için komut zaman penceresi tamamlandı.{C_RESET}"
        )
        print("    Fiziksel hareket/konum kabulü ayrıca ölçülmelidir.")

    except KeyboardInterrupt:
        print(f"\n\n{C_RED}{C_BOLD}[!] KULLANICI TARAFINDAN KESİLDİ! MOTORLAR ACİL DURDURULUYOR...{C_RESET}")
        stop_resp = send_cmd(ser, "STOP")
        print(f"[{C_RED}Arduino Yanıtı{C_RESET}]: {stop_resp}")


def main():
    print_banner()

    if not HAS_PYSERIAL:
        print(f"{C_RED}[HATA] 'pyserial' kütüphanesi yüklü değil!{C_RESET}")
        print("Kurmak için terminale yazın: pip install pyserial")
        sys.exit(1)

    detected_port = auto_detect_port()
    all_ports = list_and_find_ports()

    if all_ports:
        print(f"[*] Sistemde bulunan seri portlar: {', '.join(all_ports)}")
    else:
        print(f"{C_YELLOW}[!] Uyarı: Takılı aktif seri port algılanamadı.{C_RESET}")

    default_port = detected_port or (all_ports[0] if all_ports else "COM3")
    user_input = input(f"\nKullanılacak Port [{C_GREEN}{default_port}{C_RESET}]: ").strip()
    target_port = user_input if user_input else default_port

    print(f"\n[*] {target_port} portuna bağlanılıyor (115200 baud)...")
    try:
        ser = serial.Serial(port=target_port, baudrate=115200, timeout=1.0)
    except Exception as exc:
        print(f"{C_RED}[HATA] Seri port açılamadı ({target_port}): {exc}{C_RESET}")
        return

    time.sleep(2.0)
    ping_resp = send_cmd(ser, "PING")
    print(f"[<] Arduino Bağlantı Testi (PING): {C_GREEN}{ping_resp}{C_RESET}")
    if ping_resp != "PONG":
        print(f"{C_RED}[HATA] PING/PONG doğrulanamadı; motor komutu gönderilmeyecek.{C_RESET}")
        ser.close()
        return

    profile_resp = send_cmd(ser, "PROFILE")
    expected_profile = f"PROFILE {FIELD_PROFILE}"
    print(f"[<] Firmware Profili: {C_GREEN}{profile_resp}{C_RESET}")
    if profile_resp != expected_profile:
        print(
            f"{C_RED}[HATA] Beklenen saha firmware profili yok; motor komutu gönderilmeyecek. "
            f"Beklenen: {expected_profile}{C_RESET}"
        )
        ser.close()
        return

    try:
        while True:
            print("\n" + "=" * 65)
            print(f"{C_CYAN}{C_BOLD} MOTOR SEÇİM MENÜSÜ:{C_RESET}")
            print("=" * 65)
            print(f"  {C_BOLD}[1]{C_RESET} -> {C_GREEN}1. Motoru (PAN - Pin 2/3) Oynat{C_RESET}       [15 sn, Saat Yönü - CW]")
            print(f"  {C_BOLD}[2]{C_RESET} -> {C_GREEN}2. Motoru (TILT - Pin 4/5) Oynat{C_RESET}      [15 sn, Saat Yönü - CW]")
            print(f"  {C_BOLD}[3]{C_RESET} -> {C_CYAN}Her İki Motoru Birlikte Oynat{C_RESET}         [15 sn, Saat Yönü - CW]")
            print(f"  {C_BOLD}[4]{C_RESET} -> {C_YELLOW}1. Motoru TERS Yöne Oynat{C_RESET}             [15 sn, Ters Saat - CCW]")
            print(f"  {C_BOLD}[5]{C_RESET} -> {C_YELLOW}2. Motoru TERS Yöne Oynat{C_RESET}             [15 sn, Ters Saat - CCW]")
            print(f"  {C_BOLD}[6]{C_RESET} -> {C_BLUE}Özel Parametreli Çalıştırma{C_RESET}           [Motor, Süre, Yön]")
            print(f"  {C_BOLD}[7]{C_RESET} -> {C_BOLD}Durum Sorgula (STATUS){C_RESET}")
            print(f"  {C_BOLD}[8]{C_RESET} -> {C_RED}{C_BOLD}ACİL DURDUR (STOP){C_RESET}")
            print(f"  {C_BOLD}[0]{C_RESET} -> Çıkış")
            print("-" * 65)

            secim = input(f"{C_BOLD}Seçiminiz [0-8]: {C_RESET}").strip()

            if secim == "1":
                ack = send_cmd(ser, "1")
                print(f"[<] Arduino: {ack}")
                monitor_progress(ser, duration_sec=15, motor_name="1. MOTOR (PAN - Pin 2/3)", direction="Saat Yönü (CW)")

            elif secim == "2":
                ack = send_cmd(ser, "2")
                print(f"[<] Arduino: {ack}")
                monitor_progress(ser, duration_sec=15, motor_name="2. MOTOR (TILT - Pin 4/5)", direction="Saat Yönü (CW)")

            elif secim == "3":
                ack = send_cmd(ser, "3")
                print(f"[<] Arduino: {ack}")
                monitor_progress(ser, duration_sec=15, motor_name="HER İKİ MOTOR (1. ve 2.)", direction="Saat Yönü (CW)")

            elif secim == "4":
                ack = send_cmd(ser, "4")
                print(f"[<] Arduino: {ack}")
                monitor_progress(ser, duration_sec=15, motor_name="1. MOTOR (PAN - Pin 2/3)", direction="Ters Saat (CCW)")

            elif secim == "5":
                ack = send_cmd(ser, "5")
                print(f"[<] Arduino: {ack}")
                monitor_progress(ser, duration_sec=15, motor_name="2. MOTOR (TILT - Pin 4/5)", direction="Ters Saat (CCW)")

            elif secim == "6":
                print(f"\n{C_CYAN}--- ÖZEL MOTOR TESTİ AYARLARI ---{C_RESET}")
                m_secim = input("Hangi motor? (1: Pan / 2: Tilt / 3: İkisi) [1]: ").strip() or "1"
                m_map = {"1": "PAN", "2": "TILT", "3": "BOTH"}
                motor_name = m_map.get(m_secim, "PAN")
                
                sure = input("Çalışma süresi (Saniye) [15]: ").strip() or "15"
                yon = input("Dönüş yönü (CW: Saat, CCW: Ters saat) [CW]: ").strip().upper() or "CW"

                cmd = f"RUN {sure} 800 {yon}" if motor_name == "BOTH" else f"RUN_{motor_name} {sure} 800 {yon}"
                ack = send_cmd(ser, cmd)
                print(f"[<] Arduino: {ack}")
                monitor_progress(
                    ser,
                    duration_sec=int(sure),
                    motor_name=f"{motor_name} MOTORU",
                    direction=yon,
                )

            elif secim == "7":
                status_resp = send_cmd(ser, "STATUS")
                print(f"\n{C_CYAN}[<] Arduino Durumu: {status_resp}{C_RESET}")

            elif secim == "8":
                stop_resp = send_cmd(ser, "STOP")
                print(f"\n{C_RED}[!] Durdurma Komutu Gönderildi: {stop_resp}{C_RESET}")

            elif secim == "0":
                print("\nÇıkılıyor...")
                break

            else:
                print(f"{C_RED}[!] Geçersiz seçim! Lütfen 0 ile 8 arasında bir numara girin.{C_RESET}")

    finally:
        send_cmd(ser, "STOP")
        ser.close()
        print(f"[*] Seri port kapatıldı ({target_port}). Güvenli çıkış yapıldı.\n")


if __name__ == "__main__":
    main()
