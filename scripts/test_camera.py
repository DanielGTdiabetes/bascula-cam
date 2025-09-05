# -*- coding: utf-8 -*-
"""
Script rápido para probar la cámara (Picamera2) usando el wrapper interno.
- Inicializa la cámara
- Reporta el estado
- Captura una foto JPEG y muestra la ruta

Uso:
    python -m scripts.test_camera
"""
import sys
import time
from pathlib import Path


def main() -> int:
    try:
        from bascula.services.camera import CameraService
    except Exception as e:
        print(f"[ERR] No se pudo importar CameraService: {e}")
        return 2

    cam = CameraService(width=640, height=480, fps=5, jpeg_quality=90, save_dir=".")
    print(f"[INFO] Estado: {cam.explain_status()}")
    if not cam.available():
        print("[ERR] Cámara no disponible. Asegúrate de estar en Raspberry Pi con Picamera2 instalado.")
        return 1

    try:
        time.sleep(0.2)
        out = cam.capture_still()
        print(f"[OK] Foto capturada: {Path(out).resolve()}")
        return 0
    except Exception as e:
        print(f"[ERR] Fallo al capturar: {e}")
        return 3
    finally:
        try:
            cam.stop()
        except Exception:
            pass


if __name__ == "__main__":
    sys.exit(main())

