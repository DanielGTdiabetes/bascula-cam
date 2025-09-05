# -*- coding: utf-8 -*-
"""
Script rápido para probar la cámara (Picamera2) usando el wrapper interno.
- Inicializa la cámara
- Reporta el estado
- Captura una foto JPEG y muestra la ruta

Usos válidos:
    1) Desde la raíz del repo:   python3 -m scripts.test_camera
    2) Dentro de scripts/:       python3 test_camera.py
"""
import sys, os
import time
from pathlib import Path


def main() -> int:
    # Permite ejecutar estando dentro de scripts/ añadiendo la raíz del repo al path
    try:
        repo_root = Path(__file__).resolve().parents[1]
        if str(repo_root) not in sys.path:
            sys.path.insert(0, str(repo_root))
    except Exception:
        pass
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
