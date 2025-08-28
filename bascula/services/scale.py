# -*- coding: utf-8 -*-
from __future__ import annotations
import time
from statistics import mean
from typing import Optional, Tuple
from bascula.state import AppState
from bascula.domain.filters import ProfessionalWeightFilter, StabilityInfo

class _FakeHX711:
    def __init__(self):
        self._t0 = time.time()
        self._drift = 0.0
    def read_raw(self) -> int:
        t = time.time() - self._t0
        self._drift += 0.3 * (0.5 - ((int(t*3) % 100)/100.0))
        base = 8000 + 50 * (1 if int(t) % 10 < 5 else -1)
        noise = (int(t*50) % 5) - 2
        return int(base + self._drift + noise)

class ScaleService:
    def __init__(self, state: AppState, logger):
        self.state = state
        self.logger = logger
        self.hx = None
        self.hx_backend = "unknown"
        self.filter = ProfessionalWeightFilter(self.state.cfg.filters)
        self._reference_unit = float(self.state.cfg.hardware.reference_unit or 1.0)
        self._offset_raw = float(self.state.cfg.hardware.offset_raw or 0.0)
        self.samples = max(1, int(self.state.cfg.hardware.samples_per_read or 8))
        self._init_hx711()

    def _init_hx711(self):
        try:
            try:
                from hx711 import HX711  # type: ignore
                self.hx = HX711(dout_pin=self.state.cfg.hardware.hx711_dout_pin, pd_sck_pin=self.state.cfg.hardware.hx711_sck_pin)
                self.hx_backend = "hx711.HX711"; self.logger.info("HX711 via hx711.HX711")
                return
            except Exception: pass
            try:
                from HX711 import HX711  # type: ignore
                self.hx = HX711(self.state.cfg.hardware.hx711_dout_pin, self.state.cfg.hardware.hx711_sck_pin)
                self.hx_backend = "HX711.HX711"; self.logger.info("HX711 via HX711.HX711")
                return
            except Exception: pass
            try:
                from hx711_gpiozero import HX711 as HX711GZ  # type: ignore
                self.hx = HX711GZ(self.state.cfg.hardware.hx711_dout_pin, self.state.cfg.hardware.hx711_sck_pin)
                self.hx_backend = "hx711_gpiozero.HX711"; self.logger.info("HX711 via hx711_gpiozero.HX711")
                return
            except Exception: pass
            try:
                import HX711 as HX711PY  # type: ignore
                self.hx = HX711PY.HX711(self.state.cfg.hardware.hx711_dout_pin, self.state.cfg.hardware.hx711_sck_pin)
                if hasattr(self.hx, "set_reading_format"): self.hx.set_reading_format("MSB","MSB")
                self.hx_backend = "py-HX711"; self.logger.info("HX711 via py-HX711")
                return
            except Exception: pass
            raise RuntimeError("HX711 no disponible")
        except Exception as e:
            self.logger.error(f"HX711 error: {e}")
            if self.state.cfg.hardware.strict_hardware: raise
            self.hx = _FakeHX711(); self.hx_backend = "SIMULATOR"; self.logger.warning("Usando simulador")

    def _read_raw_once(self) -> Optional[int]:
        if self.hx is None: return None
        for name in ("read_raw","get_raw_data_mean","read","read_average","get_value"):
            func = getattr(self.hx, name, None)
            if func:
                try:
                    v = func() if name not in ("read_average","get_value") else func(times=1)
                    if isinstance(v,(tuple,list)): v = v[0]
                    return int(v) if v is not None else None
                except Exception: pass
        return None

    def _read_raw(self) -> int:
        vals = []
        for _ in range(self.samples):
            v = self._read_raw_once()
            if v is not None: vals.append(int(v))
            time.sleep(0.002)
        return int(mean(vals)) if vals else 0

    def read(self):
        raw = self._read_raw()
        grams = (raw - self._offset_raw) * self._reference_unit
        fast, stable, info = self.filter.update(grams)
        self.state.last_weight_g = stable; self.state.stable = info.is_stable
        return fast, stable, info, raw

    def tare(self): self.filter.tara()
    def reset(self): self.filter.reset()
    def set_reference_unit(self, ref: float): self._reference_unit = float(ref)
    def set_offset_raw(self, off: float): self._offset_raw = float(off)
    def get_backend_name(self) -> str: return self.hx_backend
