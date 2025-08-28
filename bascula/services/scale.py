# -*- coding: utf-8 -*-
from __future__ import annotations
"""
Servicio de báscula robusto:
- Inicializa HX711 con backends: hx711 (pip), HX711 (bogde), hx711_gpiozero
- Prueba métodos crudos: get_raw_data_mean, get_raw_data(times=3), read_average, get_value, get_data_mean, read
- Auto-detección de pines invertidos (DOUT/SCK) por backend si la sonda no ve variación
- Lectura media por muestras; filtro profesional (mediana + IIR + STD + auto-zero estable + cuantización 0.1 g)
- Tara y calibración en crudo (reference_unit / offset_raw)
"""

import time
from typing import Optional, Callable, Any
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
        # Umbral STD en gramos para marcar estable (ajustable)
        self.stability_threshold = float(getattr(fcfg, "stability_threshold", 0.15))
        self.stable_min_samples = int(getattr(fcfg, "stable_min_samples", 10))
        # Zero tracking (solo si estable y cerca de cero)
        self.zero_tracking = bool(getattr(fcfg, "zero_tracking", True))
        self.zero_band = float(getattr(fcfg, "zero_epsilon", 0.2))
        # Cuantización visual
        self.display_resolution = 0.1

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
        # Mediana contra picos
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

    # ---------- Inicialización con auto-detección de pines ----------
    def _init_hx711(self):
        dout = int(self.state.cfg.hardware.hx711_dout_pin or 5)
        sck = int(self.state.cfg.hardware.hx711_sck_pin or 6)

        # Intentaremos cada backend con (dout,sck) y, si no hay variación, también (sck,dout)
        attempts = [
            ("hx711.HX711", self._try_backend_hx711),
            ("HX711.HX711", self._try_backend_bogde),
            ("hx711_gpiozero.HX711", self._try_backend_gpiozero),
        ]
        for backend_name, factory in attempts:
            # Primero: mapping directo
            if factory(dout, sck):
                self.hx_backend = backend_name
                self.logger.info(f"HX711 via {backend_name} (BCM DOUT={dout}, SCK={sck})")
                return
            # Segundo: mapping invertido
            if factory(sck, dout):
                # Aviso de inversión automática
                self.hx_backend = backend_name + " [PIN-SWAP]"
                self.state.cfg.hardware.hx711_dout_pin = sck
                self.state.cfg.hardware.hx711_sck_pin = dout
                self.logger.warning(f"Auto-swap de pines: usando DOUT={sck}, SCK={dout}")
                return

        msg = "HX711 no disponible o sin variación de lectura (revisa librería, cableado y pines DOUT/SCK)."
        self.logger.error(msg)
        if self.state.cfg.hardware.strict_hardware:
            raise RuntimeError(msg)

    def _probe_variation(self, reads: int = 10, delay: float = 0.01) -> bool:
        """Lee varias veces para verificar que no son todo None/0 constantes."""
        vals = []
        for _ in range(reads):
            v = self._read_raw_once()
            if v is not None:
                vals.append(int(v))
            time.sleep(delay)
        if not vals:
            return False
        span = max(vals) - min(vals)
        return span != 0  # alguna variación mínima debe existir, incluso sin peso

    def _try_backend_hx711(self, dout: int, sck: int) -> bool:
        try:
            from hx711 import HX711  # type: ignore
            self.hx = HX711(dout_pin=dout, pd_sck_pin=sck, channel='A', gain=128)
            # Opcionales si existen
            for name in ("reset", "tare"):
                f = getattr(self.hx, name, None)
                if callable(f):
                    try: f()
                    except Exception: pass
            time.sleep(0.1)
            return self._probe_variation()
        except Exception as e:
            self.logger.debug(f"hx711 backend fallo: {e}")
            self.hx = None
            return False

    def _try_backend_bogde(self, dout: int, sck: int) -> bool:
        try:
            from HX711 import HX711 as HX711_BOGDE  # type: ignore
            self.hx = HX711_BOGDE(dout, sck)
            if hasattr(self.hx, "set_reading_format"):
                try: self.hx.set_reading_format("MSB", "MSB")
                except Exception: pass
            if hasattr(self.hx, "reset"):
                try: self.hx.reset()
                except Exception: pass
            time.sleep(0.1)
            return self._probe_variation()
        except Exception as e:
            self.logger.debug(f"bogde backend fallo: {e}")
            self.hx = None
            return False

    def _try_backend_gpiozero(self, dout: int, sck: int) -> bool:
        try:
            from hx711_gpiozero import HX711 as HX711GZ  # type: ignore
            self.hx = HX711GZ(dout, sck)
            time.sleep(0.1)
            return self._probe_variation()
        except Exception as e:
            self.logger.debug(f"gpiozero backend fallo: {e}")
            self.hx = None
            return False

    # ---------- Lectura cruda robusta ----------
    def _read_raw_once(self) -> Optional[int]:
        if self.hx is None:
            return None

        # Lista de métodos que probamos, con firmas alternativas típicas
        candidates: list[tuple[str, list[dict[str, Any]]]] = [
            ("get_raw_data_mean", [{"num_measures": 1}, {}]),
            ("get_raw_data",      [{"num_measures": 3}, {"times": 3}, {}]),  # <- el de tu versión que funciona
            ("read_average",      [{"times": 1}, {}]),
            ("get_value",         [{"times": 1}, {}]),
            ("get_data_mean",     [{}]),
            ("read",              [{}]),
        ]
        for name, variants in candidates:
            func: Optional[Callable[..., Any]] = getattr(self.hx, name, None)
            if not callable(func):
                continue
            for kwargs in variants:
                try:
                    v = func(**kwargs)
                    if isinstance(v, (list, tuple)):
                        v = v[0]
                    if v is None:
                        continue
                    return int(v)
                except TypeError:
                    # Firma distinta, probamos siguiente variante
                    continue
                except Exception:
                    # Otro error interno, probamos siguiente candidato
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
