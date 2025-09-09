#!/usr/bin/env python3
# scripts/test_serial.py — Lectura simple de /dev/serial0 mostrando tramas G:<g>,S:<s>
import sys
import time

try:
    import serial
except Exception as e:
    print("[ERROR] Falta pyserial. Instala con: pip install pyserial")
    sys.exit(1)

PORT = "/dev/serial0"
BAUD = 115200

def main():
    try:
        ser = serial.Serial(PORT, BAUD, timeout=1)
    except Exception as e:
        print(f"[ERROR] No se pudo abrir {PORT} @ {BAUD}: {e}")
        sys.exit(1)

    print(f"[OK] Leyendo {PORT} @ {BAUD}. Ctrl+C para salir.")
    try:
        while True:
            try:
                line = ser.readline().decode(errors="ignore").strip()
            except Exception:
                line = ""
            if line:
                print("RX:", line)
            else:
                # pequeño respiro para no saturar CPU
                time.sleep(0.02)
    except KeyboardInterrupt:
        pass
    finally:
        try:
            ser.close()
        except Exception:
            pass

if __name__ == "__main__":
    main()
