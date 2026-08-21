#!/usr/bin/env python3
import serial
import time
import sys

def monitor(port="/dev/ttyAMA0", baud=9600):
    print(f"Opening {port} at {baud} baud...")
    try:
        s = serial.Serial(port=port, baudrate=baud, timeout=0.5)
    except Exception as e:
        print(f"Failed to open port: {e}")
        return

    s.reset_input_buffer()
    print("Listening for 10 seconds. Move your hand / object in front of LiDAR...")
    start = time.time()
    count = 0
    while time.time() - start < 10:
        chunk = s.read(s.in_waiting or 1)
        if chunk:
            count += len(chunk)
            hex_data = " ".join(f"{b:02X}" for b in chunk)
            ascii_repr = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
            print(f"[{time.time()-start:5.2f}s] ({len(chunk):2d}B) HEX: {hex_data} | ASCII: {ascii_repr}")
        time.sleep(0.1)
    s.close()
    print(f"Done. Total bytes received: {count}")

if __name__ == "__main__":
    port = sys.argv[1] if len(sys.argv) > 1 else "/dev/ttyAMA0"
    baud = int(sys.argv[2]) if len(sys.argv) > 2 else 9600
    monitor(port, baud)
