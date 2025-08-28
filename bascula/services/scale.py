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
        self._dout_pin = int(self.state.cfg.hardware.hx711_dout_pin)
        self._sck_pin = int(self.state.cfg.hardware.hx711_sck_pin)
        self.filter = ProfessionalWeightFilter(self.state.cfg.filters)
        self._reference_unit = float(self.state.cfg.hardware.reference_unit or 1.0)
        self._offset_raw = float(self.state.cfg.hardware.offset_raw or 0.0)
        self.samples = max(1, int(self.state.cfg.hardware.samples_per_read or 8))
        self._init_hx711()

    def _prepare_hx(self, hx) -> None:
        """Try common init calls across libraries to stabilize readings."""
        try:
            if hasattr(hx, "reset"):
                hx.reset()
        except Exception:
            pass
        try:
            # Some libs use 'zero' or 'tare' for baseline
            if hasattr(hx, "zero"):
                hx.zero()
            elif hasattr(hx, "tare"):
                # 'tare' may accept times arg in some implementations
                try:
                    hx.tare()
                except TypeError:
                    hx.tare(10)
        except Exception:
            pass
        try:
            if hasattr(hx, "power_up"):
                hx.power_up()
        except Exception:
            pass

    def _try_build_hx(self, dout: int, sck: int):
        """Try multiple HX711 libraries with the provided pin mapping."""
        # 1) hx711 (RPi.GPIO-based)
        try:
            from hx711 import HX711  # type: ignore
            hx = HX711(dout_pin=dout, pd_sck_pin=sck)
            self._prepare_hx(hx)
            return hx, "hx711.HX711"
        except Exception:
            pass
        # 2) HX711 (uppercase module)
        try:
            from HX711 import HX711  # type: ignore
            hx = HX711(dout, sck)
            self._prepare_hx(hx)
            return hx, "HX711.HX711"
        except Exception:
            pass
        # 3) hx711_gpiozero
        try:
            from hx711_gpiozero import HX711 as HX711GZ  # type: ignore
            hx = HX711GZ(dout, sck)
            self._prepare_hx(hx)
            return hx, "hx711_gpiozero.HX711"
        except Exception:
            pass
        # 4) py-HX711
        try:
            import HX711 as HX711PY  # type: ignore
            hx = HX711PY.HX711(dout, sck)
            if hasattr(hx, "set_reading_format"):
                hx.set_reading_format("MSB", "MSB")
            self._prepare_hx(hx)
            return hx, "py-HX711"
        except Exception:
            pass
        return None, None

    def _probe_hx(self, hx) -> bool:
        """Read a few times to confirm the sensor returns integers."""
        ok = 0
        for _ in range(12):
            v = None
            for name in ("read_raw", "get_raw_data_mean", "read", "read_average", "get_value"):
                func = getattr(hx, name, None)
                if func:
                    try:
                        v = func() if name not in ("read_average", "get_value") else func(times=1)
                        if isinstance(v, (tuple, list)):
                            v = v[0]
                        break
                    except Exception:
                        v = None
                        continue
            if isinstance(v, (int, float)):
                ok += 1
            time.sleep(0.01)
        return ok >= 2

    def _init_hx711(self):
        try:
            # Try configured pins, swapped, and common pairs (5,6) and (6,5)
            cfg_d, cfg_s = int(self._dout_pin), int(self._sck_pin)
            candidates = [
                (cfg_d, cfg_s),
                (cfg_s, cfg_d),  # swapped
                (5, 6),
                (6, 5),
            ]
            # De-duplicate while preserving order
            seen = set()
            candidates = [p for p in candidates if not (p in seen or seen.add(p))]
            for dout, sck in candidates:
                try:
                    self.logger.info(f"Probing HX711 on pins (DOUT={dout}, SCK={sck})")
                except Exception:
                    pass
                hx, backend = self._try_build_hx(dout, sck)
                if hx is None:
                    continue
                if self._probe_hx(hx):
                    self.hx = hx
                    self.hx_backend = backend or "unknown"
                    self._dout_pin, self._sck_pin = int(dout), int(sck)
                    self.logger.info(f"HX711 via {self.hx_backend} (DOUT={self._dout_pin}, SCK={self._sck_pin})")
                    # Update state with the working pins so UI can persist if desired
                    self.state.cfg.hardware.hx711_dout_pin = self._dout_pin
                    self.state.cfg.hardware.hx711_sck_pin = self._sck_pin
                    return
                else:
                    try:
                        self.logger.info(f"No readings on (DOUT={dout}, SCK={sck})")
                    except Exception:
                        pass
                    try:
                        # Some libs expose power down/up; attempt cleanup
                        if hasattr(hx, "power_down"):
                            hx.power_down()
                    except Exception:
                        pass
                    continue
            raise RuntimeError("HX711 no disponible (no lecturas con las combinaciones de pines indicadas)")
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
    def get_pins(self) -> Tuple[int, int]: return self._dout_pin, self._sck_pin

    # --- Calibration helpers ---
    def calibrate_with_known_weight(self, known_weight_g: float, settle_ms: int = 1200) -> float:
        """
        Compute and set reference_unit given a placed known weight (in grams).

        Assumes the weight is already on the scale when calling. It samples the
        raw sensor for the specified settling time and calculates:
            reference_unit = known_weight_g / (raw_mean - offset_raw)

        Returns the new reference_unit. Raises if readings are invalid.
        """
        kg = float(known_weight_g)
        if kg <= 0:
            raise ValueError("known_weight_g debe ser > 0")
        # Sample for the settle duration
        t_end = time.time() + max(0.2, settle_ms / 1000.0)
        samples = []
        while time.time() < t_end:
            r = self._read_raw_once()
            if r is not None:
                samples.append(int(r))
            time.sleep(0.01)
        if not samples:
            raise RuntimeError("Sin lectura HX711 (revise cableado/pines)")
        raw_mean = int(mean(samples))
        delta = raw_mean - int(self._offset_raw)
        if abs(delta) < 1:
            raise RuntimeError("Lectura sin cambio (delta ~ 0). Asegure el peso puesto.")
        new_ref = kg / float(delta)
        # Update internal state
        self._reference_unit = float(new_ref)
        return self._reference_unit
