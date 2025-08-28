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
        base = 8000 + 50 * (1 if int(t) % 10 < 5 else -1)
        self._drift += 0.3 * (0.5 - (hash(int(t*3)) % 100)/100.0)
        noise = (hash(int(t*50)) % 5) - 2
        return int(base + self._drift + noise)

    def power_down(self): pass
    def power_up(self): pass

class ScaleService:
    def __init__(self, state: AppState, logger):
        self.state = state
        self.logger = logger
        self.hx = None
        self.hx_backend = "unknown"
        self.filter = ProfessionalWeightFilter(self.state.cfg.filters)
        self._reference_unit = float(self.state.cfg.hardware.reference_unit or 1.0)
        self._offset_raw = float(self.state.cfg.hardware.offset_raw or 0.0)
        self.samples_per_read = max(1, int(self.state.cfg.hardware.samples_per_read or 8))
        self._init_hx711()

    def _init_hx711(self) -> None:
        try:
            try:
                from hx711 import HX711  # type: ignore
                dout = self.state.cfg.hardware.hx711_dout_pin
                sck  = self.state.cfg.hardware.hx711_sck_pin
                self.hx = HX711(dout_pin=dout, pd_sck_pin=sck)
                self.hx_backend = "hx711.HX711"
                self.logger.info(f"HX711 inicializado (hx711.HX711) DOUT={dout}, SCK={sck}")
                return
            except Exception:
                pass

            try:
                from HX711 import HX711  # type: ignore
                dout = self.state.cfg.hardware.hx711_dout_pin
                sck  = self.state.cfg.hardware.hx711_sck_pin
                self.hx = HX711(dout, sck)
                self.hx_backend = "HX711.HX711"
                self.logger.info(f"HX711 inicializado (HX711.HX711) DOUT={dout}, SCK={sck}")
                return
            except Exception:
                pass

            try:
                from hx711_gpiozero import HX711 as HX711GZ  # type: ignore
                dout = self.state.cfg.hardware.hx711_dout_pin
                sck  = self.state.cfg.hardware.hx711_sck_pin
                self.hx = HX711GZ(dout, sck)
                self.hx_backend = "hx711_gpiozero.HX711"
                self.logger.info(f"HX711 inicializado (hx711_gpiozero.HX711) DOUT={dout}, SCK={sck}")
                return
            except Exception:
                pass

            try:
                import HX711 as HX711PY  # type: ignore
                dout = self.state.cfg.hardware.hx711_dout_pin
                sck  = self.state.cfg.hardware.hx711_sck_pin
                self.hx = HX711PY.HX711(dout, sck)
                self.hx.set_reading_format("MSB", "MSB")
                self.hx_backend = "py-HX711"
                self.logger.info(f"HX711 inicializado (py-HX711) DOUT={dout}, SCK={sck}")
                return
            except Exception:
                pass

            raise RuntimeError("No se pudo inicializar HX711 con las librerías conocidas.")
        except Exception as e:
            self.logger.error(f"Fallo HX711: {e}")
            if self.state.cfg.hardware.strict_hardware:
                raise
            self.hx = _FakeHX711()
            self.hx_backend = "SIMULATOR"
            self.logger.warning("Usando simulador HX711 (strict_hardware=False)")

    def _read_raw_once(self) -> Optional[int]:
        if self.hx is None:
            return None

        if hasattr(self.hx, "read_raw"):
            try:
                val = self.hx.read_raw()
                return int(val) if val is not None else None
            except Exception:
                return None

        if hasattr(self.hx, "get_raw_data_mean"):
            try:
                val = self.hx.get_raw_data_mean()
                return int(val) if val is not None else None
            except Exception:
                return None

        if hasattr(self.hx, "read"):
            try:
                val = self.hx.read()
                if isinstance(val, (tuple, list)) and val:
                    val = val[0]
                return int(val) if val is not None else None
            except Exception:
                return None

        if hasattr(self.hx, "read_average"):
            try:
                val = self.hx.read_average(times=1)
                return int(val) if val is not None else None
            except Exception:
                return None
        if hasattr(self.hx, "get_value"):
            try:
                val = self.hx.get_value(times=1)
                return int(val) if val is not None else None
            except Exception:
                return None

        return None

    def _read_raw(self, samples: int) -> int:
        vals = []
        for _ in range(max(1, samples)):
            v = self._read_raw_once()
            if v is not None:
                vals.append(int(v))
            time.sleep(0.002)
        if not vals:
            return 0
        return int(mean(vals))

    def read(self) -> Tuple[float, float, StabilityInfo, int]:
        raw = self._read_raw(self.samples_per_read)
        grams = (raw - self._offset_raw) * self._reference_unit
        fast, stable, info = self.filter.update(grams)
        self.state.last_weight_g = stable
        self.state.stable = info.is_stable
        return fast, stable, info, raw

    def tare(self) -> None:
        self.filter.tara()

    def reset(self) -> None:
        self.filter.reset()

    def set_reference_unit(self, ref: float) -> None:
        self._reference_unit = float(ref)

    def set_offset_raw(self, off: float) -> None:
        self._offset_raw = float(off)

    def get_backend_name(self) -> str:
        return self.hx_backend

    def calibrate_with_known_weight(self, known_weight_g: float, settle_ms: int = 1500) -> float:
        import time
        from statistics import mean
        time.sleep(max(0.0, settle_ms / 1000.0))
        readings = []
        for _ in range(20):
            readings.append(self._read_raw(self.samples_per_read))
            time.sleep(0.01)
        raw_mean = mean(readings)
        denom = max(1.0, float(raw_mean - self._offset_raw))
        new_ref = float(known_weight_g) / denom
        self.set_reference_unit(new_ref)
        return new_ref
