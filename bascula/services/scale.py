# -*- coding: utf-8 -*-
"""
bascula/services/scale.py
Adaptador de servicio de báscula que usa el backend serie
(ESP32) definido en releases/v1/python_backend/serial_scale.py

Diseño:
- El backend SerialScale es "push": llama a un callback on_read(grams, stable).
- Esta fachada guarda el último valor y expone una API "pull" para la UI:
    start(), stop(), get_weight(), get_latest(), is_stable(), subscribe(cb)
- Compatibilidad: mantiene firma (port, baud, logger).
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Callable, List, Optional

# --- Ubicar python_backend en sys.path ----------------------------------------
REPO_ROOT = Path(__file__).resolve().parents[2]  # <repo>/...
PY_BACKEND = REPO_ROOT / "python_backend"
if str(PY_BACKEND) not in sys.path:
    sys.path.insert(0, str(PY_BACKEND))

# --- Intento de importación del backend real ---------------------------------
_BACKEND_IMPORT_OK = False
_IMPORT_ERROR: Optional[BaseException] = None
try:
    # Debe existir: releases/v1/python_backend/serial_scale.py
    from serial_scale import SerialScale  # type: ignore
    _BACKEND_IMPORT_OK = True
except Exception as e:  # pragma: no cover
    SerialScale = None  # type: ignore
    _BACKEND_IMPORT_OK = False
    _IMPORT_ERROR = e


class ScaleService:
    """
    Fachada del lector de báscula.
    - start() pasa un callback al backend para recibir lecturas.
    - get_weight()/get_latest() devuelven el último valor recibido (float, gramos).
    - is_stable() expone el último flag de estabilidad (bool).
    - subscribe(cb) notifica a observadores cada lectura.
    """

    def __init__(
        self,
        port: str = "/dev/serial0",
        baud: int = 115200,
        logger=None,
        fail_fast: bool = True,
        **kwargs,
    ):
        self.logger = logger
        self.backend: Optional[SerialScale] = None  # type: ignore

        # Últimos valores conocidos
        self._last_raw: float = 0.0
        self._last_stable: int = 0  # 0/1
        self._subs: List[Callable[[float, bool], None]] = []

        if not _BACKEND_IMPORT_OK:
            msg = (
                "No se pudo importar python_backend/serial_scale.py. "
                f"Detalle: {_IMPORT_ERROR!r}"
            )
            if self.logger:
                self.logger.error(msg)
            else:
                print(f"[ERROR] {msg}")
            if fail_fast:
                raise ImportError(msg)
            return  # modo nulo

        # Instanciar backend real (acepta 'baudrate')
        try:
            self.backend = SerialScale(port=port, baudrate=baud, logger=logger)  # type: ignore[arg-type]
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
            self.backend = None  # modo nulo

    # --- Ciclo de vida -------------------------------------------------------
    def start(self) -> None:
        """
        Arranca el backend pasándole el callback on_read.
        """
        if self.backend:
            if self.logger:
                self.logger.info("Iniciando backend SerialScale…")
            # IMPORTANTE: el backend exige el callback 'on_read'
            self.backend.start(self._on_read)  # type: ignore[misc]
        elif self.logger:
            self.logger.warning("start() llamado pero backend es None (modo nulo)")

    def stop(self) -> None:
        if self.backend:
            if self.logger:
                self.logger.info("Deteniendo backend SerialScale…")
            try:
                self.backend.stop()
            except Exception as e:  # pragma: no cover
                if self.logger:
                    self.logger.warning(f"stop(): {e!r}")
        elif self.logger:
            self.logger.warning("stop() llamado pero backend es None (modo nulo)")

    # --- Callback desde el backend ------------------------------------------
    def _on_read(self, grams: float, stable: int) -> None:
        """
        Recibe lecturas del backend. 'stable' llega como 0/1.
        """
        try:
            self._last_raw = float(grams)
            self._last_stable = 1 if int(stable) else 0
        except Exception:
            return

        if self.logger:
            # baja a DEBUG si hace falta menos ruido
            self.logger.debug(f"Serial read: g={self._last_raw:.3f}, s={self._last_stable}")

        # Notificar observadores
        for cb in list(self._subs):
            try:
                cb(self._last_raw, bool(self._last_stable))
            except Exception as e:  # pragma: no cover
                if self.logger:
                    self.logger.warning(f"Subscriber error: {e!r}")

    # --- Lectura y estado ----------------------------------------------------
    def get_weight(self) -> float:
        """Último valor (gramos). En modo nulo -> 0.0"""
        return float(self._last_raw)

    def get_latest(self) -> float:
        """Alias histórico usado por la UI."""
        return self.get_weight()

    def is_stable(self) -> bool:
        return bool(self._last_stable)

    # --- Suscripción ---------------------------------------------------------
    def subscribe(self, cb: Callable[[float, bool], None]) -> None:
        """cb(weight_g: float, stable: bool)"""
        if callable(cb):
            self._subs.append(cb)
        elif self.logger:
            self.logger.warning("subscribe() ignorado: callback no llamable")

    # --- Comandos (no-op aquí; la tara real la lleva TareManager) ------------
    def tare(self) -> bool:  # compat API
        return True

    def calibrate(self, weight_grams: float) -> bool:  # compat API
        return True


# Alias histórico si alguna parte esperaba HX711Service
HX711Service = ScaleService
