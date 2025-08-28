# -*- coding: utf-8 -*-
from __future__ import annotations
"""
Servicio de báscula (igual que tu ejemplo en backend, ahora con lectura asíncrona):
- Librería: hx711 (pip) -> from hx711 import HX711
- Pines BCM: DOUT=5, SCK=6 (desde config, por defecto 5/6)
- Inicialización: HX711(dout_pin=..., pd_sck_pin=..., channel='A', gain=64)
- Lectura cruda base: get_raw_data(times=3)
- Hilo de lectura continuo (no bloquea UI)
- Filtro profesional: mediana + IIR + STD + auto-zero estable + cuantización 0.1 g
- Tara y calibración en crudo (offset_raw / reference_unit)
"""

import time
import threading
from typing import Optional, Tuple
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
    def __init__(self, fcfg):
        self.fast_alpha = getattr(fcfg, "fast_alpha", 0.55)
        self.stable_alpha = getattr(fcfg, "stable_alpha", 0.12)
        self.stability_window = max(5, int(getattr(fcfg, "stability_window", 24)))
        self.stability_threshold = float(getattr(fcfg, "stability_threshold", 0.15))  # STD en g
        self.stable_min_samples = int(getattr(fcfg, "stable_min_samples", 10))
        self.zero_tracking = bool(getattr(fcfg, "zero_tracking", True))
        self.zero_band = float(getattr(fcfg, "zero_epsilon", 0.2))  # banda cerca de cero
        self.display_resolution = 0.1  # cuantización a 0.1 g

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

    def update(self, grams_raw: float) -> tuple[float, float, StabilityInfo]:
        v = float(grams_raw)
        # Mediana anti-picos
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
    Servicio de pesaje:
      - hx711 (pip) + GPIO BCM DOUT=5 / SCK=6
      - get_raw_data(times=3) como lectura cruda
      - Lector asíncrono: no bloquea la UI
    """
    def __init__(self, state: AppState, logger):
        self.state = state
        self.logger = logger
        self.hx = None
        self.hx_backend = "unknown"

        self._reference_unit = float(self.state.cfg.hardware.reference_unit or 1.0)
        self._offset_raw = float(self.state.cfg.hardware.offset_raw or 0.0)

        # Velocidad/calidad de lectura
        self.samples = max(1, int(self.state.cfg.hardware.samples_per_read or 4))  # menos muestras = menos latencia
        self.sleep_between_samples = 0.001  # 1 ms

        self.filter = ProfessionalWeightFilter(self.state.cfg.filters)

        # Buffer de últimos valores (producidos por el hilo)
        self._last_fast: float = 0.0
        self._last_display: float = 0.0
        self._last_info: StabilityInfo = StabilityInfo(False, float("inf"), float("inf"), 0.0)
        self._last_raw: int = 0
        self._lock = threading.Lock()

        self._stop_ev = threading.Event()
        self._thread: Optional[threading.Thread] = None

        self._init_hx711()
        self.start_reader()

    # ---------- Inicialización (como el ejemplo) ----------
    def _init_hx711(self):
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

    # ---------- Hilo lector continuo ----------
    def start_reader(self, hz: float = 100.0):
        if self._thread and self._thread.is_alive():
            return
        period = max(0.002, 1.0 / hz)  # mínimo 2 ms
        def loop():
            next_t = time.perf_counter()
            while not self._stop_ev.is_set():
                try:
                    raw = self._read_raw_fast()
                    grams = (raw - self._offset_raw) * self._reference_unit
                    fast, display, info = self.filter.update(grams)
                    with self._lock:
                        self._last_fast = fast
                        self._last_display = display
                        self._last_info = info
                        self._last_raw = raw
                        self.state.last_weight_g = display
                        self.state.stable = info.is_stable
                except Exception:
                    pass
                next_t += period
                dt = next_t - time.perf_counter()
                if dt > 0:
                    time.sleep(dt)
        self._stop_ev.clear()
        self._thread = threading.Thread(target=loop, daemon=True)
        self._thread.start()

    def stop_reader(self):
        self._stop_ev.set()
        if self._thread:
            self._thread.join(timeout=1.0)

    # ---------- Lecturas crudas ----------
    def _read_raw_once(self) -> Optional[int]:
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

    def _read_raw_fast(self) -> int:
        # versión “rápida”: menos muestras para minimizar latencia del hilo
        vals = []
        for _ in range(self.samples):
            v = self._read_raw_once()
            if v is not None:
                vals.append(int(v))
            time.sleep(self.sleep_between_samples)
        return int(mean(vals)) if vals else 0

    # ---------- API pública ----------
    def peek(self) -> Tuple[float, float, StabilityInfo, int]:
        # No bloquea: devuelve el último paquete disponible
        with self._lock:
            return self._last_fast, self._last_display, self._last_info, self._last_raw

    def read(self):
        # Compatibilidad con código existente: ahora leer es instantáneo
        return self.peek()

    def tare(self):
        # Ajuste de offset en crudo + tara de presentación
        raw = self._read_raw_fast()
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

    def calibrate_with_known_weight(self, known_weight_g: float, settle_ms: int = 400) -> float:
        # Espera corta (no bloqueará UI porque se hará en hilo de fondo desde la UI)
        if known_weight_g <= 0:
            raise ValueError("El peso de calibración debe ser positivo")
        time.sleep(settle_ms / 1000.0)
        raw = self._read_raw_fast()
        raw_diff = float(raw) - float(self._offset_raw)
        if raw_diff == 0.0:
            raise RuntimeError("No hay variación cruda para calibrar (¿tara hecha y peso colocado?)")
        new_ref = float(known_weight_g) / raw_diff
        self._reference_unit = new_ref
        return new_ref
