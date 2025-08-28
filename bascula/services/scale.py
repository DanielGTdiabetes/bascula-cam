# -*- coding: utf-8 -*-
from __future__ import annotations
import time
from statistics import mean
from typing import Optional, Tuple
from bascula.state import AppState

# Filtro profesional mínimo (igual al que ya usabas)
from collections import deque
class StabilityInfo:
    def __init__(self, is_stable: bool, span_window: float, last_value: float):
        self.is_stable = is_stable
        self.span_window = span_window
        self.last_value = last_value

class ProfessionalWeightFilter:
    def __init__(self, fcfg):
        self.fast_alpha = max(0.01, min(0.95, float(fcfg.fast_alpha)))
        self.stable_alpha = max(0.01, min(0.95, float(fcfg.stable_alpha)))
        self.stability_window = max(3, int(fcfg.stability_window))
        self.stability_threshold = float(fcfg.stability_threshold)
        self.zero_tracking = bool(fcfg.zero_tracking)
        self.zero_epsilon = float(fcfg.zero_epsilon)
        self.stable_min_samples = int(fcfg.stable_min_samples)
        self._fast = 0.0
        self._stable = 0.0
        self._hist = deque(maxlen=self.stability_window)
        self._tare = 0.0
        self._init = False

    def set_zero_tracking(self, enabled: bool):
        self.zero_tracking = bool(enabled)

    def tara(self):
        base = self._stable if self._init else 0.0
        self._tare = base

    def reset(self):
        self._fast = self._stable = 0.0
        self._hist.clear()
        self._tare = 0.0
        self._init = False

    def _apply_zero(self, v: float) -> float:
        if self.zero_tracking and abs(v) <= self.zero_epsilon:
            return 0.0
        return v

    def update(self, grams: float):
        v = float(grams) - self._tare
        v = self._apply_zero(v)
        if not self._init:
            self._fast = self._stable = v
            self._init = True
        else:
            self._fast = self.fast_alpha * v + (1 - self.fast_alpha) * self._fast
            self._stable = self.stable_alpha * v + (1 - self.stable_alpha) * self._stable
        self._hist.append(v)
        span = (max(self._hist) - min(self._hist)) if len(self._hist) >= max(3, int(self.stability_window*0.8)) else float("inf")
        stable = (len(self._hist) >= self.stable_min_samples) and (span <= self.stability_threshold)
        return self._fast, self._stable, StabilityInfo(stable, span, v)

# --- Backends HX711 soportados ---
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
        # Orden de prueba de librerías (más comunes primero)
        # 1) pip hx711 (dout_pin=, pd_sck_pin=)
        try:
            from hx711 import HX711  # type: ignore
            self.hx = HX711(dout_pin=self.state.cfg.hardware.hx711_dout_pin,
                            pd_sck_pin=self.state.cfg.hardware.hx711_sck_pin,
                            channel='A', gain=128)
            try:
                self.hx.reset()
                time.sleep(0.1)
            except Exception:
                pass
            self.hx_backend = "hx711.HX711"
            self.logger.info(f"HX711 via {self.hx_backend} (BCM DOUT={self.state.cfg.hardware.hx711_dout_pin}, SCK={self.state.cfg.hardware.hx711_sck_pin})")
            return
        except Exception as e:
            self.logger.warning(f"hx711.HX711 no disponible: {e}")

        # 2) paquete HX711 (bogde port): HX711(dout, sck)
        try:
            from HX711 import HX711 as HX711_BOGDE  # type: ignore
            self.hx = HX711_BOGDE(self.state.cfg.hardware.hx711_dout_pin,
                                  self.state.cfg.hardware.hx711_sck_pin)
            if hasattr(self.hx, "set_reading_format"):
                try:
                    self.hx.set_reading_format("MSB", "MSB")
                except Exception:
                    pass
            if hasattr(self.hx, "reset"):
                try:
                    self.hx.reset()
                except Exception:
                    pass
            self.hx_backend = "HX711.HX711"
            self.logger.info(f"HX711 via {self.hx_backend}")
            return
        except Exception as e:
            self.logger.warning(f"HX711.HX711 no disponible: {e}")

        # 3) hx711_gpiozero
        try:
            from hx711_gpiozero import HX711 as HX711GZ  # type: ignore
            self.hx = HX711GZ(self.state.cfg.hardware.hx711_dout_pin,
                              self.state.cfg.hardware.hx711_sck_pin)
            self.hx_backend = "hx711_gpiozero.HX711"
            self.logger.info(f"HX711 via {self.hx_backend}")
            return
        except Exception as e:
            self.logger.warning(f"hx711_gpiozero.HX711 no disponible: {e}")

        # Si no hay hardware y strict_hardware=True -> error
        msg = "HX711 no disponible (comprueba librería y cableado)"
        self.logger.error(msg)
        if self.state.cfg.hardware.strict_hardware:
            raise RuntimeError(msg)
        # Si se desea, aquí se podría activar simulación; pero tú pediste modo real estricto.

    # --- Lecturas crudas unificadas según backend ---
    def _read_raw_once(self) -> Optional[int]:
        if self.hx is None:
            return None
        # pip hx711: get_raw_data_mean / get_value
        for name in ("get_raw_data_mean", "read", "read_average", "get_value", "get_data_mean"):
            func = getattr(self.hx, name, None)
            if func:
                try:
                    # distintos backends usan firmas distintas
                    if name in ("read_average", "get_value"):
                        v = func(times=1)
                    else:
                        v = func()
                    if isinstance(v, (tuple, list)):
                        v = v[0]
                    if v is None:
                        continue
                    return int(v)
                except Exception:
                    continue
        return None

    def _read_raw(self) -> int:
        vals = []
        for _ in range(self.samples):
            v = self._read_raw_once()
            if v is not None:
                vals.append(int(v))
            time.sleep(0.002)
        return int(mean(vals)) if vals else 0

    def read(self):
        raw = self._read_raw()
        grams = (raw - self._offset_raw) * self._reference_unit
        fast, stable, info = self.filter.update(grams)
        self.state.last_weight_g = stable
        self.state.stable = info.is_stable
        return fast, stable, info, raw

    def tare(self):
        # Toma promedio crudo actual como offset_raw
        raw = self._read_raw()
        self._offset_raw = float(raw)

    def reset(self):
        self.filter.reset()

    def set_reference_unit(self, ref: float):
        self._reference_unit = float(ref)

    def set_offset_raw(self, off: float):
        self._offset_raw = float(off)

    def get_backend_name(self) -> str:
        return self.hx_backend

    # --- Calibración con peso patrón ---
    def calibrate_with_known_weight(self, known_weight_g: float, settle_ms: int = 1200) -> float:
        if known_weight_g <= 0:
            raise ValueError("El peso de calibración debe ser positivo")
        # Espera para estabilizar
        time.sleep(settle_ms / 1000.0)
        raw = self._read_raw()
        raw_diff = raw - self._offset_raw
        if raw_diff == 0:
            raise RuntimeError("No se detectó cambio para calibrar (¿tara hecha y peso colocado?)")
        new_ref = float(known_weight_g) / float(raw_diff)
        self._reference_unit = new_ref
        return new_ref
