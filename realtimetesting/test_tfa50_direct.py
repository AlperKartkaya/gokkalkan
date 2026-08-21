#!/usr/bin/env python3
import serial
import time
import sys

def test_tfa50(port="/dev/ttyAMA0", baud=9600):
    print(f"=== Testing TFA50-L on {port} at {baud} baud ===")
    try:
        ser = serial.Serial(port=port, baudrate=baud, timeout=0.1)
    except Exception as e:
        print(f"Failed to open port: {e}")
        return

    # Flush
    ser.reset_input_buffer()
    ser.reset_output_buffer()
    time.sleep(0.1)

    # 1. Stop ranging command: 5A 0A 02 00 00 F3
    print("[*] Sending STOP_RANGING...")
    ser.write(bytes.fromhex("5A 0A 02 00 00 F3"))
    time.sleep(0.1)
    resp = ser.read(30)
    print(f"    Response: {resp.hex(' ').upper()}")

    # 2. Read firmware command: 5A 16 02 16 16 BB
    print("[*] Sending READ_FIRMWARE...")
    ser.write(bytes.fromhex("5A 16 02 16 16 BB"))
    time.sleep(0.1)
    resp = ser.read(30)
    print(f"    Response: {resp.hex(' ').upper()}")

    # 3. Read serial command: 5A 0D 02 0D 0D D6
    print("[*] Sending READ_SERIAL...")
    ser.write(bytes.fromhex("5A 0D 02 0D 0D D6"))
    time.sleep(0.1)
    resp = ser.read(30)
    print(f"    Response: {resp.hex(' ').upper()}")

    # 4. Start ranging command: 5A 0A 02 02 00 F1
    print("[*] Sending START_RANGING...")
    ser.write(bytes.fromhex("5A 0A 02 02 00 F1"))
    time.sleep(0.1)
    resp = ser.read(30)
    print(f"    Response: {resp.hex(' ').upper()}")

    # 5. Live stream read
    print("\n[*] Reading live stream for 10 seconds (move an object in front of sensor)...")
    buffer = bytearray()
    start = time.time()
    valid_count = 0
    while time.time() - start < 10:
        avail = getattr(ser, "in_waiting", 0)
        chunk = ser.read(max(64, avail) if avail else 64)
        if chunk:
            buffer.extend(chunk)
            while len(buffer) >= 4:
                if buffer[0] == 0x5C:
                    c = buffer[:4]
                    dist_l, dist_h, cs = c[1], c[2], c[3]
                    expected_cs = (~((dist_l + dist_h) & 0xFF)) & 0xFF
                    if cs == expected_cs:
                        dist_cm = dist_l | (dist_h << 8)
                        valid_count += 1
                        print(f"[{time.time()-start:5.2f}s] Distance: {dist_cm:4d} cm ({dist_cm/100.0:5.2f} m) | Raw: {c.hex(' ').upper()}")
                        del buffer[:4]
                        continue
                    else:
                        del buffer[0]
                elif len(buffer) >= 9 and buffer[0] == 0x59 and buffer[1] == 0x59:
                    c = buffer[:9]
                    expected_cs = sum(c[:8]) & 0xFF
                    if c[8] == expected_cs:
                        dist_cm = c[2] | (c[3] << 8)
                        amp = c[4] | (c[5] << 8)
                        valid_count += 1
                        print(f"[{time.time()-start:5.2f}s] [TFmini/Luna] Distance: {dist_cm:4d} cm ({dist_cm/100.0:5.2f} m) Amp: {amp} | Raw: {c.hex(' ').upper()}")
                        del buffer[:9]
                        continue
                    else:
                        del buffer[0]
                else:
                    del buffer[0]
        time.sleep(0.02)

    ser.close()
    print(f"\nDone. Valid distance frames received: {valid_count}")

if __name__ == "__main__":
    port = sys.argv[1] if len(sys.argv) > 1 else "/dev/ttyAMA0"
    baud = int(sys.argv[2]) if len(sys.argv) > 2 else 9600
    test_tfa50(port, baud)
