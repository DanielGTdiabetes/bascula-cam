#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Servicio de báscula que envuelve SerialScale.
Exposición limpia para la UI.
"""

from typing import Optional, Callable
from python_backend.serial_scale import SerialScale

class ScaleService:
    def __init__(self, port: str = "/dev/serial0", baud: int = 115200):
        self._serial = SerialScale(port=port, baud=baud)
        self._cb: Optional[Callable[[float, bool], None]] = None

    def start(self):
        self._serial.start()
        if self._cb:
            self._serial.subscribe(self._cb)

    def stop(self):
        self._serial.stop()

    # API de lectura
    def get_weight(self) -> float:
        return self._serial.get_weight()

    def is_stable(self) -> bool:
        return self._serial.is_stable()

    # API de comandos
    def tare(self) -> bool:
        return self._serial.tare()

    def calibrate(self, grams: float) -> bool:
        return self._serial.calibrate(grams)

    # Suscripción (opcional)
    def subscribe(self, cb: Callable[[float, bool], None]):
        self._cb = cb
        self._serial.subscribe(cb)
