cd ~/bascula-cam
cat > scripts/test_serial.py <<'PY'
#!/usr/bin/env python3
# Lectura simple de /dev/serial0 mostrando tramas G:<g>,S:<s>
import sys, serial
PORT = "/dev/serial0"; BAUD = 115200
def main():
    try:
        ser = serial.Serial(PORT, BAUD, timeout=1)
    except Exception as e:
        print(f"[ERROR] No se pudo abrir {PORT} @ {BAUD}: {e}")
        sys.exit(1)
    print(f"[OK] Leyendo {PORT} @ {BAUD}. Ctrl+C para salir.")
    try:
        while True:
            line = ser.readline().decode(errors="ignore").strip()
            if line:
                print("RX:", line)
    except KeyboardInterrupt:
        pass
    finally:
        ser.close()
if __name__ == "__main__":
    main()
PY
chmod +x scripts/test_serial.py
