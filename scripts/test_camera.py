# test_camera.py
import sys
import os
from pathlib import Path

# Añadir el directorio del proyecto al path
# Asegura que el repo raíz está en sys.path
project_root = Path(__file__).resolve().parents[1]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

try:
    from bascula.services.camera import CameraService
    print("CameraService importado correctamente.")
    
    # Crea una instancia de la clase y comprueba su estado
    cam = CameraService(width=800, height=600)
    print(f"Estado del servicio: {cam.explain_status()}")

    if cam.available():
        print("Cámara disponible. Intentando capturar...")
        path = cam.capture_still(path="/tmp/test_capture_service.jpg")
        print(f"Captura exitosa. Imagen guardada en: {path}")
    else:
        print("Cámara no disponible. Revisa el estado del servicio.")
        
    cam.stop()
    
except ImportError as e:
    print(f"Error al importar el módulo: {e}. Asegúrate de estar en el directorio correcto y de tener las dependencias instaladas.")
except Exception as e:
    print(f"Error inesperado durante la prueba: {e}")
