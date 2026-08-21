#!/usr/bin/env python3
"""
Gökkalkan — Arduino Uno & DM542 Gerçek Zamanlı WASD Klavye Motor Kontrolcüsü (Python)

Kullanım:
    python realtimetesting/wasd_motor_control.py
    (veya port belirterek: python realtimetesting/wasd_motor_control.py --port COM3)

Klavye Kontrolleri:
  [ W ] veya [ ↑ ] : TILT Yukarı (CW)
  [ S ] veya [ ↓ ] : TILT Aşağı  (CCW)
  [ A ] veya [ ← ] : PAN  Sola   (CCW)
  [ D ] veya [ → ] : PAN  Sağa   (CW)
  [ SPACE ] veya [ X ] : ACİL DURDUR (STOP)
  [ + ] / [ - ]        : Adım Açısını Artır / Azalt (0.25°, 0.5°, 1°, 2°, 5°, 10°)
  [ 1 ] / [ 2 ] / [ 3 ]: Hız Kademesi Seçimi (Yavaş / Normal / Hızlı)
  [ C ]                : Mod Geçişi (Adım Modu vs Kesintisiz Jog Modu)
  [ R ]                : Açı Sayacını Sıfırla (Home)
  [ Q ] veya [ ESC ]   : Güvenli Çıkış
"""

from __future__ import annotations

import argparse
import glob
import os
import sys
import time
from typing import Any

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

# Cross-platform Key Capture Setup
IS_WINDOWS = os.name == "nt"

if IS_WINDOWS:
    import msvcrt
else:
    import select
    import termios
    import tty


def get_key_non_blocking() -> str | None:
    """Non-blocking single key capture supporting Windows and Linux/Pi."""
    if IS_WINDOWS:
        if msvcrt.kbhit():
            ch = msvcrt.getch()
            # Handle special keys (Arrow keys, Fn keys)
            if ch in (b"\x00", b"\xe0"):
                ch2 = msvcrt.getch()
                arrow_map = {
                    b"H": "UP",
                    b"P": "DOWN",
                    b"K": "LEFT",
                    b"M": "RIGHT",
                }
                return arrow_map.get(ch2, "SPECIAL")
            if ch == b"\x1b":
                return "ESC"
            if ch == b" ":
                return "SPACE"
            return ch.decode("utf-8", errors="ignore")
        return None
    else:
        # Linux / MacOS / Pi non-blocking read
        dr, _, _ = select.select([sys.stdin], [], [], 0.0)
        if dr:
            ch = sys.stdin.read(1)
            if ch == "\x1b":
                # Check for arrow key sequence: ESC [ A
                dr2, _, _ = select.select([sys.stdin], [], [], 0.05)
                if dr2:
                    ch2 = sys.stdin.read(1)
                    if ch2 == "[":
                        ch3 = sys.stdin.read(1)
                        arrow_map = {"A": "UP", "B": "DOWN", "D": "LEFT", "C": "RIGHT"}
                        return arrow_map.get(ch3, "ESC")
                return "ESC"
            if ch == " ":
                return "SPACE"
            return ch
        return None


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
C_BG_BLUE = "\033[44m"
C_BG_RED = "\033[41m"
C_CLEAR_SCREEN = "\033[2J\033[H" if not IS_WINDOWS else ""


def find_arduino_port() -> str | None:
    """Sistemdeki aktif Arduino Uno seri portunu otomatik tespit eder."""
    if not HAS_PYSERIAL:
        return None

    ports = list(serial.tools.list_ports.comports())
    for p in ports:
        desc = (p.description or "").lower()
        mfr = (p.manufacturer or "").lower()
        dev = p.device.lower()
        if (
            "arduino" in desc
            or "arduino" in mfr
            or "ch340" in desc
            or "ch340" in mfr
            or "ch341" in desc
            or "cp210" in desc
            or "ftdi" in desc
            or "ttyacm" in dev
            or "ttyusb" in dev
        ):
            return p.device

    candidates = sorted(
        glob.glob("/dev/serial/by-id/*")
        + glob.glob("/dev/ttyACM*")
        + glob.glob("/dev/ttyUSB*")
    )
    if candidates:
        return candidates[0]

    if ports:
        return ports[0].device

    return None


class RawTerminalContext:
    """Linux'ta terminali raw moda geçirir, Windows'ta pass-through çalışır."""

    def __enter__(self):
        if not IS_WINDOWS:
            self.fd = sys.stdin.fileno()
            self.old_settings = termios.tcgetattr(self.fd)
            tty.setraw(self.fd)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if not IS_WINDOWS:
            termios.tcsetattr(self.fd, termios.TCSADRAIN, self.old_settings)


class WASDMotorController:
    # DM542 1600 Pulses/Rev: 1600 adım = 360° => 1° ≈ 4.4444 adım
    STEPS_PER_DEG = 1600.0 / 360.0

    STEP_SIZES_DEG = [0.25, 0.5, 1.0, 2.0, 5.0, 10.0]
    SPEED_PRESETS = {
        1: ("YAVAS (1500us / 333Hz)", 1500),
        2: ("NORMAL (800us / 625Hz)", 800),
        3: ("HIZLI (400us / 1250Hz)", 400),
    }

    def __init__(self, port: str, baudrate: int = 115200) -> None:
        self.port = port
        self.baudrate = baudrate
        self.ser: serial.Serial | None = None

        self.step_idx = 2  # Varsayılan: 1.0°
        self.speed_level = 2  # Varsayılan: Normal 800us
        self.continuous_mode = False

        self.est_pan_deg = 0.0
        self.est_tilt_deg = 0.0
        self.total_pan_steps = 0
        self.total_tilt_steps = 0

        self.last_cmd = "(Henüz komut gönderilmedi)"
        self.last_ack = ""
        self.last_key = ""
        self.connected = False

    def connect(self) -> bool:
        try:
            self.ser = serial.Serial(self.port, self.baudrate, timeout=0.08)
            time.sleep(2.0)  # Arduino DTR resetinin oturmasını bekle
            self.ser.reset_input_buffer()
            self.ser.reset_output_buffer()
            self.connected = True

            # PING at
            self.send_raw("PING")
            return True
        except Exception as exc:
            self.connected = False
            self.last_cmd = f"Bağlantı Hatası: {exc}"
            return False

    def close(self):
        if self.ser and self.ser.is_open:
            try:
                self.send_raw("STOP")
                self.ser.close()
            except Exception:
                pass
        self.connected = False

    def send_raw(self, cmd_str: str) -> str:
        if not self.ser or not self.ser.is_open:
            return "SERI_BAGLANTI_YOK"

        try:
            self.ser.reset_input_buffer()
            self.ser.write((cmd_str.strip() + "\n").encode("ascii"))
            time.sleep(0.02)
            lines = []
            while self.ser.in_waiting > 0:
                line = self.ser.readline().decode("utf-8", errors="ignore").strip()
                if line:
                    lines.append(line)
            self.last_cmd = cmd_str
            self.last_ack = " | ".join(lines) if lines else "OK"
            return self.last_ack
        except Exception as exc:
            self.last_ack = f"Hata: {exc}"
            return self.last_ack

    @property
    def current_step_deg(self) -> float:
        return self.STEP_SIZES_DEG[self.step_idx]

    @property
    def current_delay_us(self) -> int:
        return self.SPEED_PRESETS[self.speed_level][1]

    def pan_step(self, deg: float):
        """Pan Motoru Adım Sürüşü (+CW / -CCW)."""
        cw = deg >= 0
        direction = "CW" if cw else "CCW"
        steps = max(1, int(round(abs(deg) * self.STEPS_PER_DEG)))
        cmd = f"STEP_PAN {steps} {self.current_delay_us} {direction}"
        self.send_raw(cmd)

        delta = steps / self.STEPS_PER_DEG * (1 if cw else -1)
        self.est_pan_deg += delta
        self.total_pan_steps += steps * (1 if cw else -1)

    def tilt_step(self, deg: float):
        """Tilt Motoru Adım Sürüşü (+CW / -CCW)."""
        cw = deg >= 0
        direction = "CW" if cw else "CCW"
        steps = max(1, int(round(abs(deg) * self.STEPS_PER_DEG)))
        cmd = f"STEP_TILT {steps} {self.current_delay_us} {direction}"
        self.send_raw(cmd)

        delta = steps / self.STEPS_PER_DEG * (1 if cw else -1)
        self.est_tilt_deg += delta
        self.total_tilt_steps += steps * (1 if cw else -1)

    def pan_jog(self, cw: bool):
        direction = "CW" if cw else "CCW"
        cmd = f"JOG_PAN {self.current_delay_us} {direction}"
        self.send_raw(cmd)

    def tilt_jog(self, cw: bool):
        direction = "CW" if cw else "CCW"
        cmd = f"JOG_TILT {self.current_delay_us} {direction}"
        self.send_raw(cmd)

    def emergency_stop(self):
        self.send_raw("STOP")

    def render_hud(self):
        """Konsola canlı, zengin durum tablosu basar."""
        step_str = f"{self.current_step_deg:.2f}° ({int(round(self.current_step_deg * self.STEPS_PER_DEG))} Adım)"
        speed_name = self.SPEED_PRESETS[self.speed_level][0]
        mode_str = f"{C_YELLOW}SÜREKLİ JOG{C_RESET}" if self.continuous_mode else f"{C_GREEN}ADIM (PULSE){C_RESET}"

        # Clear screen and draw HUD
        out = []
        out.append(f"\033[H{C_CYAN}{C_BOLD}" + "=" * 68 + f"{C_RESET}")
        out.append(f"{C_CYAN}{C_BOLD} 🚀 GÖKKALKAN — ARDUINO UNO GERÇEK ZAMANLI WASD KONTROLCÜSÜ{C_RESET}")
        out.append(f"{C_CYAN}" + "=" * 68 + f"{C_RESET}")
        out.append(
            f"  Port: {C_GREEN}{self.port}{C_RESET} | Baud: {C_WHITE}{self.baudrate}{C_RESET} | Mod: {mode_str}"
        )
        out.append(
            f"  Adım: {C_YELLOW}{step_str:<18}{C_RESET} | Hız: {C_WHITE}{speed_name}{C_RESET}"
        )
        out.append(f"{C_CYAN}" + "-" * 68 + f"{C_RESET}")

        # Live Angles Box
        out.append(f"  {C_BOLD}🎯 TARET TAHMİNİ KONUM:{C_RESET}")
        pan_sign = "+" if self.est_pan_deg >= 0 else ""
        tilt_sign = "+" if self.est_tilt_deg >= 0 else ""
        out.append(
            f"    • {C_BOLD}PAN  (Yatay) :{C_RESET} {C_CYAN}{pan_sign}{self.est_pan_deg:7.2f}°{C_RESET}  "
            f"(Toplam Adım: {self.total_pan_steps:+d})"
        )
        out.append(
            f"    • {C_BOLD}TILT (Dikey) :{C_RESET} {C_CYAN}{tilt_sign}{self.est_tilt_deg:7.2f}°{C_RESET}  "
            f"(Toplam Adım: {self.total_tilt_steps:+d})"
        )
        out.append(f"{C_CYAN}" + "-" * 68 + f"{C_RESET}")

        # D-Pad Visual Guide
        w_active = C_BG_BLUE if self.last_key in ("W", "w", "UP") else ""
        s_active = C_BG_BLUE if self.last_key in ("S", "s", "DOWN") else ""
        a_active = C_BG_BLUE if self.last_key in ("A", "a", "LEFT") else ""
        d_active = C_BG_BLUE if self.last_key in ("D", "d", "RIGHT") else ""
        stop_active = C_BG_RED if self.last_key in ("SPACE", "X", "x") else ""

        out.append(f"  {C_BOLD}🎮 TUŞ DÜZENİ:{C_RESET}")
        out.append(f"               [{w_active} W / ↑ {C_RESET}] (TILT YUKARI)")
        out.append(
            f"  [{a_active} A / ← {C_RESET}] (PAN SOL)  [{stop_active} SPACE {C_RESET}] (DUR)  [{d_active} D / → {C_RESET}] (PAN SAĞ)"
        )
        out.append(f"               [{s_active} S / ↓ {C_RESET}] (TILT AŞAĞI)")
        out.append("")
        out.append(
            f"  [+] / [-]: Adım Değiştir | [1-3]: Hız | [C]: Mod Değiştir | [R]: Home | [Q]: Çıkış"
        )
        out.append(f"{C_CYAN}" + "-" * 68 + f"{C_RESET}")
        out.append(f"  Son Tuş   : {C_YELLOW}{self.last_key:<10}{C_RESET}")
        out.append(f"  Son Komut : {C_WHITE}{self.last_cmd}{C_RESET}")
        out.append(f"  Arduino   : {C_GREEN}{self.last_ack}{C_RESET}")
        out.append(f"{C_CYAN}" + "=" * 68 + f"{C_RESET}")

        sys.stdout.write("\n".join(out) + "\n")
        sys.stdout.flush()


def run_wasd_controller(port: str, baudrate: int = 115200) -> int:
    print(f"[*] Arduino Uno'ya bağlanılıyor ({port} @ {baudrate})...")
    ctrl = WASDMotorController(port=port, baudrate=baudrate)

    if not ctrl.connect():
        print(f"\n{C_RED}[HATA] {port} portuna bağlanılamadı!{C_RESET}")
        print("Lütfen kabloyu ve Arduino IDE Seri Portunu kontrol edin.")
        return 1

    # Terminali temizle ve HUD'ı ilk kez çiz
    if IS_WINDOWS:
        os.system("cls")
    else:
        sys.stdout.write("\033[2J\033[H")
    ctrl.render_hud()

    try:
        with RawTerminalContext():
            while True:
                key = get_key_non_blocking()
                if key is not None:
                    ctrl.last_key = key

                    # ÇIKIŞ
                    if key in ("q", "Q", "ESC", "\x03"):  # \x03 = Ctrl+C
                        break

                    # ACİL DURDUR
                    elif key in ("SPACE", "x", "X", "0"):
                        ctrl.emergency_stop()

                    # ADIM BOYUTU AYARI (+ / -)
                    elif key in ("+", "="):
                        if ctrl.step_idx < len(ctrl.STEP_SIZES_DEG) - 1:
                            ctrl.step_idx += 1
                    elif key in ("-", "_"):
                        if ctrl.step_idx > 0:
                            ctrl.step_idx -= 1

                    # HIZ AYARI (1 / 2 / 3)
                    elif key in ("1", "2", "3"):
                        ctrl.speed_level = int(key)

                    # MOD GEÇİŞİ (Step vs Continuous Jog)
                    elif key in ("c", "C"):
                        ctrl.continuous_mode = not ctrl.continuous_mode
                        if not ctrl.continuous_mode:
                            ctrl.emergency_stop()

                    # KONUM SIFIRLAMA (Home)
                    elif key in ("r", "R"):
                        ctrl.est_pan_deg = 0.0
                        ctrl.est_tilt_deg = 0.0
                        ctrl.total_pan_steps = 0
                        ctrl.total_tilt_steps = 0

                    # TILT YUKARI (W / Up Arrow)
                    elif key in ("w", "W", "UP"):
                        if ctrl.continuous_mode:
                            ctrl.tilt_jog(cw=True)
                        else:
                            ctrl.tilt_step(+ctrl.current_step_deg)

                    # TILT AŞAĞI (S / Down Arrow)
                    elif key in ("s", "S", "DOWN"):
                        if ctrl.continuous_mode:
                            ctrl.tilt_jog(cw=False)
                        else:
                            ctrl.tilt_step(-ctrl.current_step_deg)

                    # PAN SAĞA (D / Right Arrow)
                    elif key in ("d", "D", "RIGHT"):
                        if ctrl.continuous_mode:
                            ctrl.pan_jog(cw=True)
                        else:
                            ctrl.pan_step(+ctrl.current_step_deg)

                    # PAN SOLA (A / Left Arrow)
                    elif key in ("a", "A", "LEFT"):
                        if ctrl.continuous_mode:
                            ctrl.pan_jog(cw=False)
                        else:
                            ctrl.pan_step(-ctrl.current_step_deg)

                    ctrl.render_hud()

                time.sleep(0.02)

    except KeyboardInterrupt:
        pass
    finally:
        ctrl.close()
        print(f"\n{C_GREEN}[✓] Motorlar durduruldu ve port kapatıldı. Güvenli çıkış yapıldı.{C_RESET}\n")

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Gökkalkan Arduino Uno Gerçek Zamanlı WASD Klavye Motor Kontrol Paneli"
    )
    parser.add_argument(
        "--port",
        "-p",
        default=None,
        help="Arduino Uno Seri Portu (Örn: COM3 veya /dev/ttyACM0). Belirtilmezse otomatik bulunur.",
    )
    parser.add_argument(
        "--baudrate",
        "-b",
        type=int,
        default=115200,
        help="Seri Baud Hızı (Varsayılan: 115200)",
    )

    args = parser.parse_args()

    if not HAS_PYSERIAL:
        print(f"{C_RED}[HATA] 'pyserial' kütüphanesi eksik!{C_RESET}")
        print("Yüklemek için terminale yazın: pip install pyserial")
        return 1

    port = args.port
    if not port:
        port = find_arduino_port()
        if not port:
            all_ports = [p.device for p in serial.tools.list_ports.comports()]
            print(f"{C_RED}[HATA] Aktif Arduino Uno portu tespit edilemedi!{C_RESET}")
            if all_ports:
                print(f"[*] Sistemdeki portlar: {', '.join(all_ports)}")
                print(f"Lütfen portu elle belirtin: python realtimetesting/wasd_motor_control.py --port {all_ports[0]}")
            else:
                print("Lütfen USB kablosunun takılı olduğundan emin olun.")
            return 1
        print(f"[*] Otomatik tespit edilen port: {port}")

    return run_wasd_controller(port=port, baudrate=args.baudrate)


if __name__ == "__main__":
    sys.exit(main())
