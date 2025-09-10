"""
bascula/services/scale.py
Adaptador de servicio de báscula que usa el backend serie (ESP32) en python_backend/serial_scale.py
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Callable, Optional

# 1) Localizar raíz del repo y añadir python_backend al sys.path
# Estructura esperada: <repo_root>/bascula/services/scale.py
# parents[0] = .../bascula/services
# parents[1] = .../bascula
# parents[2] = .../<repo_root>
REPO_ROOT = Path(__file__).resolve().parents[2]
PY_BACKEND = REPO_ROOT / "python_backend"

if str(PY_BACKEND) not in sys.path:
    sys.path.insert(0, str(PY_BACKEND))

# 2) Intentar importar el backend real
_BACKEND_IMPORT_OK = False
_IMPORT_ERROR: Optional[BaseException] = None
try:
    # El módulo debe existir en: python_backend/serial_scale.py
    from serial_scale import SerialScale  # type: ignore
    _BACKEND_IMPORT_OK = True
except Exception as e:
    SerialScale = None  # type: ignore
    _BACKEND_IMPORT_OK = False
    _IMPORT_ERROR = e


class ScaleService:
    """
    Fachada usada por la app. Internamente delega en SerialScale (si está disponible).
    Métodos expuestos:
      - start(), stop()
      - get_weight() -> float
      - get_latest() -> float   (alias por compatibilidad con UI antigua)
      - is_stable() -> bool
      - tare() -> bool
      - calibrate(weight_grams: float) -> bool
      - subscribe(cb: Callable[[float, bool], None]) -> None
    """

    def __init__(
        self,
        port: str = "/dev/serial0",
        baud: int = 115200,
        logger=None,
        fail_fast: bool = True,
        **kwargs,
    ):
        """
        :param port: Dispositivo serie, p.ej. /dev/serial0
        :param baud: Baudrate, p.ej. 115200
        :param logger: Logger opcional
        :param fail_fast: Si True, ante error de importación/instancia lanza excepción clara.
                          Si False, queda en 'modo nulo' (backend=None) y devolverá 0.0.
        """
        self.logger = logger
        self.backend = None

        if not _BACKEND_IMPORT_OK:
            msg = (
                "No se pudo importar el backend SerialScale desde python_backend/serial_scale.py. "
                f"Detalle: {_IMPORT_ERROR!r}. Asegúrate de que existe 'python_backend' y de que "
                "el servicio se ejecuta desde la raíz del repo o con PYTHONPATH correcto."
            )
            if self.logger:
                self.logger.error(msg)
            else:
                print(f"[ERROR] {msg}")
            if fail_fast:
                raise ImportError(msg)
            return  # modo nulo

        # Instanciar backend real
        try:
            # Nota: SerialScale espera 'baud', no 'baudrate'
            self.backend = SerialScale(port=port, baud=baud, logger=logger)  # type: ignore
            if self.logger:
                self.logger.info(f"SerialScale inicializado en port={port}, baud={baud}")
            else:
                print(f"[INFO] SerialScale inicializado en port={port}, baud={baud}")
        except Exception as e:
            msg = (
                f"Fallo instanciando SerialScale(port={port}, baud={baud}): {e!r}. "
                "Comprueba cableado, permisos del puerto y que el ESP32 emite datos."
            )
            if self.logger:
                self.logger.exception(msg)
            else:
                print(f"[ERROR] {msg}")
            if fail_fast:
                raise
            # modo nulo
            self.backend = None

    # --- Ciclo de vida -------------------------------------------------------
    def start(self) -> None:
        if self.backend:
            if self.logger:
                self.logger.info("Iniciando backend SerialScale…")
            self.backend.start()
        elif self.logger:
            self.logger.warning("start() llamado pero backend es None (modo nulo)")

    def stop(self) -> None:
        if self.backend:
            if self.logger:
                self.logger.info("Deteniendo backend SerialScale…")
            self.backend.stop()
        elif self.logger:
            self.logger.warning("stop() llamado pero backend es None (modo nulo)")

    # --- Lectura y estado ----------------------------------------------------
    def get_weight(self) -> float:
        """
        Devuelve el peso neto en gramos (float).
        En modo nulo devuelve 0.0
        """
        if self.backend:
            try:
                return float(self.backend.get_weight())
            except Exception as e:
                if self.logger:
                    self.logger.exception(f"Error en get_weight(): {e!r}")
        return 0.0

    def get_latest(self) -> float:
        """
        Alias por compatibilidad con UI que usa get_latest().
        """
        return self.get_weight()

    def is_stable(self) -> bool:
        if self.backend:
            try:
                return bool(self.backend.is_stable())
            except Exception as e:
                if self.logger:
                    self.logger.exception(f"Error en is_stable(): {e!r}")
        return False

    # --- Comandos ------------------------------------------------------------
    def tare(self) -> bool:
        if self.backend:
            try:
                ok = bool(self.backend.tare())
                if self.logger:
                    self.logger.info(f"Tara -> {'OK' if ok else 'ERROR'}")
                return ok
            except Exception as e:
                if self.logger:
                    self.logger.exception(f"Error enviando tara: {e!r}")
        elif self.logger:
            self.logger.warning("tare() llamado pero backend es None (modo nulo)")
        return False

    def calibrate(self, weight_grams: float) -> bool:
        if self.backend:
            try:
                ok = bool(self.backend.calibrate(weight_grams))
                if self.logger:
                    self.logger.info(f"Calibración {weight_grams}g -> {'OK' if ok else 'ERROR'}")
                return ok
            except Exception as e:
                if self.logger:
                    self.logger.exception(f"Error en calibrate({weight_grams}): {e!r}")
        elif self.logger:
            self.logger.warning(f"calibrate({weight_grams}) llamado pero backend es None (modo nulo)")
        return False

    # --- Suscripción ---------------------------------------------------------
    def subscribe(self, cb: Callable[[float, bool], None]) -> None:
        """
        cb(weight_g: float, stable: bool)
        """
        if self.backend:
            try:
                self.backend.subscribe(cb)
            except Exception as e:
                if self.logger:
                    self.logger.exception(f"Error en subscribe(): {e!r}")
        elif self.logger:
            self.logger.warning("subscribe() llamado pero backend es None (modo nulo)")


# Alias histórico (si alguna parte de la app espera HX711Service)
HX711Service = ScaleService
