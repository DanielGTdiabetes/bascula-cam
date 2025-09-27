# python_backend/bascula/services/scale.py
# Adaptación del servicio de báscula para usar el backend serie (ESP32).
# Mantiene una API sencilla: start(), stop(), get_weight(), is_stable(), tare(), calibrate(), subscribe(cb)

from typing import Callable
from python_backend.serial_scale import SerialScale  # ajusta el import si cambias estructura

class ScaleService:
    def __init__(self, state=None, logger=None, port="/dev/serial0", baud=115200):
        self.state = state
        self.logger = logger
        self.backend = SerialScale(port=port, baud=baud)
        self._calibration_factor = 1.0

    def start(self):
        if self.logger: self.logger.info("Arrancando backend SerialScale...")
        self.backend.start()

    def stop(self):
        if self.logger: self.logger.info("Parando backend SerialScale...")
        self.backend.stop()

    def get_weight(self) -> float:
        return self.backend.get_weight()

    def is_stable(self) -> bool:
        return self.backend.is_stable()

    def tare(self) -> bool:
        ok = self.backend.tare()
        if self.logger: self.logger.info(f"Tara enviada -> {'OK' if ok else 'ERROR'}")
        return ok

    def calibrate(self, weight_grams: float) -> bool:
        ok = self.backend.calibrate(weight_grams)
        if self.logger: self.logger.info(f"Calibración {weight_grams}g -> {'OK' if ok else 'ERROR'}")
        return ok

    def set_calibration_factor(self, factor: float) -> float:
        try:
            value = float(factor)
        except (TypeError, ValueError):
            if self.logger: self.logger.debug(f"Ignoro factor de calibración inválido: {factor}")
            return self._calibration_factor

        if abs(value) < 1e-6:
            if self.logger: self.logger.debug(f"Ignoro factor de calibración demasiado pequeño: {factor}")
            return self._calibration_factor

        self._calibration_factor = value
        return self._calibration_factor

    def subscribe(self, cb: Callable[[float, bool], None]):
        self.backend.subscribe(cb)
