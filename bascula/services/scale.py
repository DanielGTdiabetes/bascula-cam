# -*- coding: utf-8 -*-
from __future__ import annotations
"""
Servicio de báscula con lógica probada (inspirada en bascula_digital.py):
- Multi-backend HX711 (hx711, HX711, hx711_gpiozero)
- Pines BCM por defecto: DOUT=5, SCK=6
- Lecturas a 10 Hz (promedio de N muestras)
- Filtro profesional: mediana -> IIR (fast/stable) -> estabilidad por STD -> auto-zero (solo estable)
- Cuantización de display a 0.1 g
- Tara (offset_raw en crudo) y calibración con peso conocido (reference_unit)
"""

import time
import math
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
    Filtro profesional con:
      - Mediana móvil para quitar picos
      - IIR doble (fast / stable). stable usa alpha más pequeño cuando está estable
      - Detección de estabilidad por desviación estándar en ventana
      - Auto-zero tracking SOLO cuando está estable y cerca de cero
      - Cuantización a resolución fija para mostrar un número “tranquilo”
    """
    def __init__(self, fcfg):
        # Config “clásica” (valores razonables por defecto)
        self.fast_alpha = getattr(fcfg, "fast_alpha", 0.55)
        self.stable_alpha = getattr(fcfg, "stable_alpha", 0.12)
        self.stability_window = max(5, int(getattr(fcfg, "stability_window", 24)))
        self.stability_threshold = float(getattr(fcfg, "stability_threshold", 0.15))  # umbral STD (g)
        self.stable_min_samples = int(getattr(fcfg, "stable_min_samples", 10))
        # Zero tracking
        self.zero_tracking = bool(getattr(fcfg, "zero_tracking", True))
        self.zero_band = float(getattr(fcfg, "zero_epsilon", 0.2))  # banda cerca de cero
        # Display
        self.display_resolution = 0.1  # cuantización a décima de gramo

        # Estado interno
        self._hist_for_median = deque(maxlen=7)     # mediana
        self._hist_for_stability = deque(maxlen=self.stability_window)  # STD/Span
        self._fast = 0.0
        self._stable = 0.0
        self._init = False
        self._presentation_tare = 0.0  # offset visual (no toca el crudo)
        self._stable_hold_counter = 0
        self._stable_required = 5      # ciclos estables consecutivos antes de auto-zero

    def reset(self):
        self._hist_for_median.clear()
        self._hist_for_stability.clear()
        self._fast = 0.0
        self._stable = 0.0
        self._presentation_tare = 0.0
        self._init = False
        self._stable_hold_counter = 0

    def tare(self):
        # Tara “visual” inmediata; la tara de sensor se hace en ScaleService (offset_raw)
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

    def update(self, grams_raw: float) -> tuple[float, float, StabilityInfo]:
        """
        Recibe gramos “crudos” (ya convertidos desde raw por reference_unit/offset_raw).
        Devuelve: fast, display, info
        """
        v = float(grams_raw)

        # Mediana para quitar picos
        self._hist_for_median.append(v)
        v_med = self._median(self._hist_for_median)

        # Inicializar EMA
        if not self._init:
            self._fast = self._stable = v_med
            self._init = True
        else:
            # EMA rápida para feedback
            self._fast = self.fast_alpha * v_med + (1 - self.fast_alpha) * self._fast
            # EMA “estable” (ligeramente más lenta)
            self._stable = self.stable_alpha * v_med + (1 - self.stable_alpha) * self._stable

        # Historial para estabilidad
        self._hist_for_stability.append(self._stable)
        span = (max(self._hist_for_stability) - min(self._hist_for_stability)) if len(self._hist_for_stability) >= 3 else float("inf")
        std = pstdev(self._hist_for_stability) if len(self._hist_for_stability) >= 3 else float("inf")

        is_stable = (len(self._hist_for_stability) >= self.stable_min_samples) and (std <= self.stability_threshold)

        # Auto-zero tracking solo si está estable y cerca de cero
        if self.zero_tracking and is_stable and abs(self._stable - self._presentation_tare) <= self.zero_band:
            self._stable_hold_counter += 1
            if self._stable_hold_counter >= self._stable_required:
                # Ajuste fino al cero visual
                self._presentation_tare = self._stable
                self._stable_hold_counter = 0
        else:
            self._stable_hold_counter = 0

        # Presentación (aplico tara visual y cuantizo)
        display_value = self._stable - self._presentation_tare
        display_value = self._quantize(display_value, self.display_resolution)

        info = StabilityInfo(is_stable=is_stable, span_window=span, std_window=std, last_value=display_value)
        return self._fast - self._presentation_tare, display_value, info


class ScaleService:
    """
    Servicio de pesaje: inicializa HX711, realiza lectura cruda promedio y aplica la
    cadena de filtrado profesional para ofrecer una experiencia “tipo balanza”.
    """
    def __init__(self, state: AppState, logger):
        self.state = state
        self.logger = logger
        self.hx = None
        self.hx_backend = "unknown"
        # Conversión cruda -> gramos
        self._reference_unit = float(self.state.cfg.hardware.reference_unit or 1.0)
        self._offset_raw = float(self.state.cfg.hardware.offset_raw or 0.0)
        # Lectura
        self.samples = max(1, int(self.state.cfg.hardware.samples_per_read or 8))
        # Filtro
        self.filter = ProfessionalWeightFilter(self.state.cfg.filters)
        # Inicialización HX711
        self._init_hx711()

    # ---------------- HX711 init ----------------
    def _init_hx711(self):
        dout = int(self.state.cfg.hardware.hx711_dout_pin or 5)
        sck = int(self.state.cfg.hardware.hx711_sck_pin or 6)

        # 1) backend 'hx711' (pip hx711)
        try:
            from hx711 import HX711  # type: ignore
            self.hx = HX711(dout_pin=dout, pd_sck_pin=sck, channel='A', gain=128)
            try:
                self.hx.reset()
                time.sleep(0.1)
            except Exception:
                pass
            self.hx_backend = "hx711.HX711"
            self.logger.info(f"HX711 via {self.hx_backend} (BCM DOUT={dout}, SCK={sck})")
            return
        except Exception as e:
            self.logger.warning(f"hx711.HX711 no disponible: {e}")

        # 2) backend 'HX711' (bogde)
        try:
            from HX711 import HX711 as HX711_BOGDE  # type: ignore
            self.hx = HX711_BOGDE(dout, sck)
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
            self.logger.info(f"HX711 via {self.hx_backend} (BCM DOUT={dout}, SCK={sck})")
            return
        except Exception as e:
            self.logger.warning(f"HX711.HX711 no disponible: {e}")

        # 3) backend 'hx711_gpiozero'
        try:
            from hx711_gpiozero import HX711 as HX711GZ  # type: ignore
            self.hx = HX711GZ(dout, sck)
            self.hx_backend = "hx711_gpiozero.HX711"
            self.logger.info(f"HX711 via {self.hx_backend} (BCM DOUT={dout}, SCK={sck})")
            return
        except Exception as e:
            self.logger.warning(f"hx711_gpiozero.HX711 no disponible: {e}")

        msg = "HX711 no disponible (comprueba librería y cableado)."
        self.logger.error(msg)
        if self.state.cfg.hardware.strict_hardware:
            raise RuntimeError(msg)
        # Si no es estricto, podríamos simular, pero tú has pedido modo real.

    # ---------------- Lectura cruda ----------------
    def _read_raw_once(self) -> Optional[int]:
        if self.hx is None:
            return None

        # Intentar diversos métodos típicos según backend
        # 'hx711' (pip) suele ofrecer get_raw_data_mean, get_value, read, etc.
        # 'HX711' (bogde) suele tener read_average, read
        for name in ("get_raw_data_mean", "read_average", "get_value", "get_data_mean", "read"):
            func = getattr(self.hx, name, None)
            if not func:
                continue
            try:
                # Firmas distintas
                if name in ("read_average", "get_value"):
                    v = func(times=1)
                else:
                    v = func()
                if isinstance(v, (list, tuple)):
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
            time.sleep(0.002)  # ~500 Hz entre submuestras
        return int(mean(vals)) if vals else 0

    # ---------------- API pública ----------------
    def read(self):
        """
        Devuelve:
          fast_g, display_g, info, raw
        """
        raw = self._read_raw()
        grams = (raw - self._offset_raw) * self._reference_unit
        fast, display, info = self.filter.update(grams)
        self.state.last_weight_g = display
        self.state.stable = info.is_stable
        return fast, display, info, raw

    def tare(self):
        """
        Tara real del sensor (offset_raw) y resetea tara de presentación.
        """
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

    # ---- Calibración con peso patrón (en crudo) ----
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
