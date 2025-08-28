# -*- coding: utf-8 -*-
from __future__ import annotations
import time
from typing import Optional, Tuple

from bascula.state import AppState
from bascula.domain.filters import ProfessionalWeightFilter, StabilityInfo

class _FakeHX711:
    """Simulador de HX711 para desarrollo o si no hay hardware."""
    def __init__(self):
        self._raw = 0.0
        self._drift = 0.0
        self._t0 = time.time()

    def read_raw(self) -> int:
        # Señal simulada con ruido y ligera deriva
        t = time.time() - self._t0
        self._drift += 0.02 * (0.5 - (hash(int(t)) % 100)/100.0)
        noise = (hash(int(t*10)) % 7) - 3  # -3..+3
        return int(5000 + self._drift + noise)

    def power_down(self): pass
    def power_up(self): pass

class ScaleService:
    def __init__(self, state: AppState, logger):
        self.state = state
        self.logger = logger
        self.hx = None
        self.filter = ProfessionalWeightFilter(self.state.cfg.filters)
        self._reference_unit = self.state.cfg.hardware.reference_unit
        self._offset_raw = self.state.cfg.hardware.offset_raw
        self._init_hx711()

    def _init_hx711(self) -> None:
        try:
            # Intentar importar librería real; si falla, usar simulador
            try:
                from hx711 import HX711  # type: ignore
            except Exception:
                HX711 = None

            if HX711 is None:
                if self.state.cfg.hardware.strict_hardware:
                    raise RuntimeError("HX711 no disponible y strict_hardware=True")
                self.hx = _FakeHX711()
                self.logger.warning("HX711 real no disponible. Usando simulador.")
                return

            # Crear instancia real
            dout = self.state.cfg.hardware.hx711_dout_pin
            sck = self.state.cfg.hardware.hx711_sck_pin
            self.hx = HX711(dout_pin=dout, pd_sck_pin=sck)
            self.logger.info(f"HX711 inicializado en DOUT={dout}, SCK={sck}")
        except Exception as e:
            self.logger.error(f"HX711 error: {e}")
            if self.state.cfg.hardware.strict_hardware:
                raise
            self.hx = _FakeHX711()
            self.logger.warning("Fallo al inicializar HX711. Usando simulador.")

    def _read_raw(self) -> int:
        if self.hx is None:
            return 0
        if hasattr(self.hx, "read_raw"):
            return int(self.hx.read_raw())
        # Algunas libs exponen .get_raw_data_mean() o similar; degradar
        if hasattr(self.hx, "get_raw_data_mean"):
            val = self.hx.get_raw_data_mean()
            return int(val if val is not None else 0)
        return 0

    def read(self) -> Tuple[float, float, StabilityInfo]:
        raw = self._read_raw()
        grams = (raw - self._offset_raw) * self._reference_unit
        fast, stable, info = self.filter.update(grams)
        self.state.last_weight_g = stable
        self.state.stable = info.is_stable
        return fast, stable, info

    def tare(self) -> None:
        # Tara en dominio "gramos": fijamos el offset para que el valor estable sea 0
        # Tomamos el último valor estable del filtro como base.
        self.filter.tara()
        # Opcional: persistir offset_raw recalculado (si quisiéramos)
        # Aquí lo dejamos en el filtro (offset relativo), sin tocar config.

    def reset(self) -> None:
        self.filter.reset()

    def set_reference_unit(self, ref: float) -> None:
        self._reference_unit = float(ref)

    def set_offset_raw(self, off: float) -> None:
        self._offset_raw = float(off)
