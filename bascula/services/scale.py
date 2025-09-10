"""
bascula/services/scale.py

Servicio de báscula que conecta con el backend serie (ESP32)
"""

import sys
from pathlib import Path
from typing import Callable, Optional

# Añadir python_backend al sys.path si no está
repo_root = Path(__file__).resolve().parent.parent.parent  # Ajusta según la estructura: bascula/services -> root
python_backend_path = repo_root / 'python_backend'
if str(python_backend_path) not in sys.path:
    sys.path.insert(0, str(python_backend_path))

try:
    from serial_scale import SerialScale  # Import directo desde serial_scale.py
    ScaleService = SerialScale
except ImportError as e:
    print(f"Error importando SerialScale: {e}", file=sys.stderr)
    # Fallback mock para desarrollo/debug
    class ScaleService:
        def __init__(self, port: str = '/dev/serial0', baudrate: int = 115200, callback: Optional[Callable] = None):
            self.weight = 0.0
            self.stable = False
            print("Usando mock ScaleService (sin hardware real)")

        def start(self):
            print("Mock: Iniciando lectura de báscula")

        def stop(self):
            print("Mock: Deteniendo lectura de báscula")

        def get_weight(self) -> float:
            return self.weight

        def is_stable(self) -> bool:
            return self.stable

        def tare(self):
            print("Mock: Tara ejecutada")

        def calibrate(self, known_weight: float):
            print(f"Mock: Calibrando con peso conocido {known_weight}g")
