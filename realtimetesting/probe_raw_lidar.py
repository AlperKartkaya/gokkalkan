#!/usr/bin/env python3
import serial
import time
import sys

def probe_port(port):
    print(f"=== Probing port: {port} ===")
    for baud in (115200, 460800, 921600, 9600, 19200, 38400, 57600):
        try:
            ser = serial.Serial(port=port, baudrate=baud, timeout=0.6)
            ser.reset_input_buffer()
            time.sleep(0.15)
            raw = ser.read(120)
            ser.close()
            hex_str = " ".join(f"{b:02X}" for b in raw[:40])
            print(f"Baud {baud:6d}: {len(raw):3d} bytes -> {hex_str}")
        except Exception as e:
            print(f"Baud {baud:6d}: ERROR {e}")

if __name__ == "__main__":
    port = sys.argv[1] if len(sys.argv) > 1 else "/dev/ttyAMA0"
    probe_port(port)
