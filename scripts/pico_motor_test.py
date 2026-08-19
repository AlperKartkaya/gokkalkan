#!/usr/bin/env python3
"""Dependency-free USB CDC client for the isolated Pico dual-motor bench test."""
from __future__ import annotations
import argparse, glob, os, select, termios, time

def open_serial(path: str) -> int:
    fd = os.open(path, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
    attrs = termios.tcgetattr(fd)
    attrs[0] = attrs[1] = attrs[3] = 0
    attrs[2] = termios.CS8 | termios.CREAD | termios.CLOCAL
    attrs[4] = attrs[5] = termios.B115200
    attrs[6][termios.VMIN] = attrs[6][termios.VTIME] = 0
    termios.tcsetattr(fd, termios.TCSANOW, attrs)
    return fd

def exchange(fd: int, command: str, wait_seconds: float) -> str:
    os.write(fd, (command + "\n").encode("ascii"))
    deadline, chunks = time.monotonic() + wait_seconds, []
    while time.monotonic() < deadline:
        readable, _, _ = select.select([fd], [], [], 0.05)
        if readable:
            chunk = os.read(fd, 4096)
            if chunk: chunks.append(chunk)
    return b"".join(chunks).decode("utf-8", errors="replace").strip()

def main() -> int:
    parser = argparse.ArgumentParser(description="Pico üzerinden çift DM542 motor sürücü testi")
    parser.add_argument("--device", help="Varsayılan: ilk /dev/ttyACM*")
    parser.add_argument("--driver", type=int, choices=(0, 1, 2), default=0,
                        help="0: HER İKİSİ AYNI ANDA (GP7 + GP4), 1: Sürücü 1 (GP7), 2: Sürücü 2 (GP4)")
    parser.add_argument("--direction", choices=("CW", "CCW"), default="CW")
    parser.add_argument("--steps", type=int, default=1600)
    parser.add_argument("--hz", type=int, default=100)
    args = parser.parse_args()
    if not 1 <= args.steps <= 64000: parser.error("--steps 1..64000 olmalı")
    if not 10 <= args.hz <= 4000: parser.error("--hz 10..4000 olmalı")
    candidates = [args.device] if args.device else sorted(glob.glob("/dev/ttyACM*"))
    if not candidates: parser.error("Pico USB CDC bulunamadı")
    fd = open_serial(candidates[0])
    try:
        time.sleep(0.25)
        print(exchange(fd, "STATUS", 0.3))
        response = exchange(fd, "ARM", 0.3)
        print(response)
        if "OK ARMED" not in response: raise SystemExit("ARM onayı yok; hareket gönderilmedi")
        cmd = f"MOVE {args.driver} {args.direction} {args.steps} {args.hz}"
        print(f">> {cmd}")
        print(exchange(fd, cmd, args.steps / args.hz + 1.5))
        print(exchange(fd, "DISARM", 0.3))
    finally:
        os.close(fd)
    return 0

if __name__ == "__main__": raise SystemExit(main())
