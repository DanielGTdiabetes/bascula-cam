# -*- coding: utf-8 -*-
from __future__ import annotations
"""
Servicio de báscula (idéntico al ejemplo que funciona):
- Librería: hx711 (pip) -> from hx711 import HX711
- Pines BCM: DOUT=5, SCK=6 (tomados de config, por defecto 5/6)
- Inicialización: HX711(dout_pin=..., pd_sck_pin=..., channel='A', gain=64)
- Lectura cruda: get_raw_data(times=3) y promediado
- Filtro profesional: mediana + IIR + STD + auto-zero estable + cuantización 0.1 g
- Tara y calibración en crudo (offset_raw / reference_unit)
"""

import time
from typing import Optional
from statistics import mean, pstdev
from collections import deque

from bascula.state import AppState

class StabilityInfo:
    def __init__(self, is_stable: bool, span_window: float, std_window: float, last_value: float):
        self.is_stable = is_stable
        self.span_window = span_window
        self.std_window = std_window
        self.last_value = last_value

class ProfessionalWeightFilter:
    """
    Filtro profesional:
      - Mediana móvil anti-picos
      - IIR doble (fast / stable)
      - Estabilidad por desviación estándar en ventana
      - Auto-zero tracking SOLO estable y cerca de cero
      - Cuantización del display a 0.1 g
    """
    def __init__(self, fcfg):
        self.fast_alpha = getattr(fcfg, "fast_alpha", 0.55)
        self.stable_alpha = getattr(fcfg, "stable_alpha", 0.12)
        self.stability_window = max(5, int(getattr(fcfg, "stability_window", 24)))
        self.stability_threshold = float(getattr(fcfg, "stability_threshold", 0.15))  # STD en g
        self.stable_min_samples = int(getattr(fcfg, "stable_min_samples", 10))
        self.zero_tracking = bool(getattr(fcfg, "zero_tracking", True))
        self.zero_band = float(getattr(fcfg, "zero_epsilon", 0.2))  # banda cerca de cero
        self.display_resolution = 0.1  # cuantización

        self._hist_for_median = deque(maxlen=7)
        self._hist_for_stability = deque(maxlen=self.stability_window)
        self._fast = 0.0
        self._stable = 0.0
        self._init = False
        self._presentation_tare = 0.0
        self._stable_hold_counter = 0
        self._stable_required = 5

    def reset(self):
        self._hist_for_median.clear()
        self._hist_for_stability.clear()
        self._fast = self._stable = 0.0
        self._presentation_tare = 0.0
        self._init = False
        self._stable_hold_counter = 0

    def tare(self):
        base = self._stable if self._init else 0.0
        self._presentation_tare = base

    def _median(self, vals):
        s = sorted(vals)
        n = len(s)
        if n == 0:
            return 0.0
        mid = n // 2
        return s[mid] if n % 2 == 1 else (s[mid - 1] + s[mid]) / 2.0

    def _quantize(self, v: float, step: float) -> float:
        if step <= 0:
            return v
        return round(v / step) * step

    def update(self, grams_raw: float):
        v = float(grams_raw)
        # Mediana
        self._hist_for_median.append(v)
        v_med = self._median(self._hist_for_median)

        if not self._init:
            self._fast = self._stable = v_med
            self._init = True
        else:
            self._fast = self.fast_alpha * v_med + (1 - self.fast_alpha) * self._fast
            self._stable = self.stable_alpha * v_med + (1 - self.stable_alpha) * self._stable

        self._hist_for_stability.append(self._stable)
        span = (max(self._hist_for_stability) - min(self._hist_for_stability)) if len(self._hist_for_stability) >= 3 else float("inf")
        std = pstdev(self._hist_for_stability) if len(self._hist_for_stability) >= 3 else float("inf")
        is_stable = (len(self._hist_for_stability) >= self.stable_min_samples) and (std <= self.stability_threshold)

        # Auto-zero solo estable y cerca de cero
        if self.zero_tracking and is_stable and abs(self._stable - self._presentation_tare) <= self.zero_band:
            self._stable_hold_counter += 1
            if self._stable_hold_counter >= self._stable_required:
                self._presentation_tare = self._stable
                self._stable_hold_counter = 0
        else:
            self._stable_hold_counter = 0

        display_value = self._stable - self._presentation_tare
        display_value = self._quantize(display_value, self.display_resolution)

        info = StabilityInfo(is_stable=is_stable, span_window=span, std_window=std, last_value=display_value)
        return self._fast - self._presentation_tare, display_value, info


class ScaleService:
    """
    Servicio de pesaje con lógica del ejemplo:
      - hx711 (pip) + GPIO BCM DOUT=5 / SCK=6
      - get_raw_data(times=3) como lectura cruda
      - calibración en crudo
    """
    def __init__(self, state: AppState, logger):
        self.state = state
        self.logger = logger
        self.hx = None
        self.hx_backend = "unknown"

        self._reference_unit = float(self.state.cfg.hardware.reference_unit or 1.0)
        self._offset_raw = float(self.state.cfg.hardware.offset_raw or 0.0)
        self.samples = max(1, int(self.state.cfg.hardware.samples_per_read or 8))

        self.filter = ProfessionalWeightFilter(self.state.cfg.filters)

        self._init_hx711()

    # ---------- Inicialización (como el ejemplo) ----------
    def _init_hx711(self):
        """
        Inicialización exacta al ejemplo que te funciona:
        - Librería 'hx711' (pip)
        - GPIO BCM
        - DOUT=5, SCK=6 (o lo de config)
        - channel='A', gain=64
        """
        try:
            import RPi.GPIO as GPIO
            from hx711 import HX711
        except Exception as e:
            self.logger.error(f"No se pudo importar HX711/RPi.GPIO: {e}")
            raise

        dout = int(self.state.cfg.hardware.hx711_dout_pin or 5)
        sck  = int(self.state.cfg.hardware.hx711_sck_pin or 6)

        try:
            GPIO.setmode(GPIO.BCM)
            GPIO.setwarnings(False)
        except Exception:
            pass

        try:
            self.hx = HX711(dout_pin=dout, pd_sck_pin=sck, channel="A", gain=64)
            try:
                self.hx.reset()
            except Exception:
                pass
            self.hx_backend = "hx711.HX711 (working-example)"
            self.logger.info(f"HX711 iniciado (BCM DOUT={dout}, SCK={sck}, A/64)")
        except Exception as e:
            self.logger.error(f"Error iniciando HX711: {e}")
            raise RuntimeError("No se pudo iniciar HX711 con hx711 (pip) DOUT/SCK 5/6")

    # ---------- Lectura cruda (como el ejemplo) ----------
    def _read_raw_once(self) -> Optional[int]:
        """
        Igual que tu ejemplo: usar get_raw_data(times=3) y promediar.
        """
        if self.hx is None:
            return None
        try:
            vals = self.hx.get_raw_data(times=3)
            if vals is None:
                return None
            if isinstance(vals, (list, tuple)) and len(vals) > 0:
                return int(sum(vals) / len(vals))
            return int(vals)
        except Exception:
            return None

    def _read_raw(self) -> int:
        vals = []
        for _ in range(self.samples):
            v = self._read_raw_once()
            if v is not None:
                vals.append(int(v))
            time.sleep(0.002)
        return int(mean(vals)) if vals else 0

    # ---------- API pública ----------
    def read(self):
        raw = self._read_raw()
        grams = (raw - self._offset_raw) * self._reference_unit
        fast, display, info = self.filter.update(grams)
        self.state.last_weight_g = display
        self.state.stable = info.is_stable
        return fast, display, info, raw

    def tare(self):
        raw = self._read_raw()
        self._offset_raw = float(raw)
        self.filter.tare()

    def reset(self):
        self.filter.reset()

    def set_reference_unit(self, ref: float):
        self._reference_unit = float(ref)

    def set_offset_raw(self, off: float):
        self._offset_raw = float(off)

    def get_backend_name(self) -> str:
        return self.hx_backend

    def calibrate_with_known_weight(self, known_weight_g: float, settle_ms: int = 1200) -> float:
        if known_weight_g <= 0:
            raise ValueError("El peso de calibración debe ser positivo")
        time.sleep(settle_ms / 1000.0)
        raw = self._read_raw()
        raw_diff = float(raw) - float(self._offset_raw)
        if raw_diff == 0.0:
            raise RuntimeError("No hay variación cruda para calibrar (¿tara hecha y peso colocado?)")
        new_ref = float(known_weight_g) / raw_diff
        self._reference_unit = new_ref
        return new_ref
