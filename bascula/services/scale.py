from __future__ import annotations
import time
from dataclasses import dataclass
from typing import Optional, Callable


@dataclass
class Calibration:
    base_offset: Optional[float] = None
    scale_factor: Optional[float] = None


class ScaleService:
    """
    Servicio de balanza con soporte para:
      - Lecturas crudas (read_raw)
      - TARA instantánea (ajuste del offset)
      - Calibración de 2 puntos (cero + peso patrón)
    Para el hardware real, implementa read_raw() con el HX711.
    """
    def __init__(self, read_raw: Optional[Callable[[], float]] = None):
        self._read_raw_fn = read_raw or self._sim_read_raw
        self.cal = Calibration()
        self._tare_adjust = 0.0
        self._sim_bias = 50000.0
        self._sim_scale = 1000.0  # unidades crudas por kilogramo simuladas

    def _sim_read_raw(self) -> float:
        base = self._sim_bias
        noise = (time.time() * 1000) % 7 - 3  # +/-3 aprox
        return base + noise

    def read_raw(self, samples: int = 5, delay_s: float = 0.0) -> float:
        acc = 0.0
        for _ in range(max(1, samples)):
            acc += float(self._read_raw_fn())
            if delay_s > 0:
                time.sleep(delay_s)
        return acc / max(1, samples)

    def gram_from_raw(self, raw: float) -> float:
        if self.cal.base_offset is None or self.cal.scale_factor is None:
            return 0.0
        grams = (raw - self.cal.base_offset) * self.cal.scale_factor
        grams -= self._tare_adjust
        return grams

    def get_weight_g(self, samples: int = 4) -> float:
        raw = self.read_raw(samples=samples)
        return self.gram_from_raw(raw)

    def tare(self):
        if self.cal.base_offset is None or self.cal.scale_factor is None:
            self._tare_adjust = 0.0
            return
        now = self.gram_from_raw(self.read_raw(samples=8))
        self._tare_adjust += now

    def clear_tare(self):
        self._tare_adjust = 0.0

    def calibrate_two_points(self, raw_zero: float, raw_span: float, ref_weight_g: float):
        delta = (raw_span - raw_zero)
        if abs(delta) < 1e-6:
            raise ValueError("Delta crudo demasiado pequeño; revisa el peso patrón o las lecturas.")
        self.cal.base_offset = raw_zero
        self.cal.scale_factor = float(ref_weight_g) / float(delta)
        self._tare_adjust = 0.0

    def export_calibration(self) -> dict:
        return {
            "base_offset": self.cal.base_offset,
            "scale_factor": self.cal.scale_factor,
        }
