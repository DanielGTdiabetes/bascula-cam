from __future__ import annotations
from collections import deque
from dataclasses import dataclass
from typing import Deque, Iterable, Optional, Tuple, Union


@dataclass
class StabilityInfo:
    """Estado de estabilidad de la medida actual."""
    is_stable: bool
    std_window: float        # (Opcional) si en el futuro calculas std; ahora 0.0
    span_window: float       # rango (max-min) en la ventana
    last_value: float        # último valor bruto tras offset/escala


class ProfessionalWeightFilter:
    """
    Filtro profesional con dos salidas:
      - rápida (reactiva)
      - estable (suavizada)

    Además:
      - Ventana deslizante para evaluar estabilidad por 'span' (max-min).
      - Zero tracking opcional: si el valor está muy cerca de 0, mantiene el cero.
      - Función de tara que fija el cero relativo.
    """

    # Valores por defecto seguros
    DEFAULTS = dict(
        fast_alpha=0.5,            # 0.01 .. 0.95
        stable_alpha=0.12,         # 0.01 .. 0.95
        stability_window=20,       # >= 3
        stability_threshold=2.0,   # g
        zero_tracking=True,
        zero_epsilon=0.8,          # g
        stable_hold_time_s=1.5,    # no usado aquí, pero mantenido por compat
        stable_min_samples=10      # >= 1
    )

    def __init__(
        self,
        config_or_fast: Union[object, float, None] = None,
        stable_alpha: Optional[float] = None,
        stability_window: Optional[int] = None,
        stability_threshold: Optional[float] = None,
        zero_tracking: Optional[bool] = None,
        zero_epsilon: Optional[float] = None,
        stable_hold_time_s: Optional[float] = None,
        stable_min_samples: Optional[int] = None,
    ):
        """
        Puede recibir:
          1) Un objeto de configuración con atributos:
             fast_alpha, stable_alpha, stability_window, stability_threshold,
             zero_tracking, zero_epsilon, stable_hold_time_s, stable_min_samples
          2) Un dict con las mismas claves
          3) Parámetros sueltos (fast_alpha como primer posicional)

        Esto evita TypeError si se le pasa self.state.cfg.filters completo.
        """

        # 1) Obtener parámetros base desde DEFAULTS
        cfg = dict(self.DEFAULTS)

        # 2) Si viene un objeto o dict, extraer
        if config_or_fast is not None and not isinstance(config_or_fast, (int, float)):
            source = config_or_fast
            # dict-like
            if isinstance(source, dict):
                for k in cfg.keys():
                    if k in source and source[k] is not None:
                        cfg[k] = source[k]
            else:
                # objeto con atributos (duck-typing)
                for k in cfg.keys():
                    if hasattr(source, k):
                        val = getattr(source, k)
                        if val is not None:
                            cfg[k] = val
        elif isinstance(config_or_fast, (int, float,)):
            cfg["fast_alpha"] = float(config_or_fast)

        # 3) Overwrite con kwargs si se han pasado
        if stable_alpha is not None:        cfg["stable_alpha"] = float(stable_alpha)
        if stability_window is not None:    cfg["stability_window"] = int(stability_window)
        if stability_threshold is not None: cfg["stability_threshold"] = float(stability_threshold)
        if zero_tracking is not None:       cfg["zero_tracking"] = bool(zero_tracking)
        if zero_epsilon is not None:        cfg["zero_epsilon"] = float(zero_epsilon)
        if stable_hold_time_s is not None:  cfg["stable_hold_time_s"] = float(stable_hold_time_s)
        if stable_min_samples is not None:  cfg["stable_min_samples"] = int(stable_min_samples)

        # 4) Clamping / validación
        self.fast_alpha         = max(0.01, min(0.95, float(cfg["fast_alpha"])))
        self.stable_alpha       = max(0.01, min(0.95, float(cfg["stable_alpha"])))
        self.stability_window   = max(3, int(cfg["stability_window"]))
        self.stability_threshold= float(cfg["stability_threshold"])
        self.zero_tracking      = bool(cfg["zero_tracking"])
        self.zero_epsilon       = max(0.0, float(cfg["zero_epsilon"]))
        self.stable_hold_time_s = max(0.0, float(cfg["stable_hold_time_s"]))
        self.stable_min_samples = max(1, int(cfg["stable_min_samples"]))

        # 5) Estado interno
        self._fast_val: float = 0.0
        self._stable_val: float = 0.0
        self._hist: Deque[float] = deque(maxlen=self.stability_window)
        self._tare_offset: float = 0.0
        self._initialized: bool = False

    # ------------ API pública ------------

    def set_zero_tracking(self, enabled: bool) -> None:
        self.zero_tracking = bool(enabled)

    def tara(self) -> bool:
        """Fija el cero relativo con el último valor estable/rápido conocido."""
        base = self._stable_val if self._initialized else 0.0
        self._tare_offset = base
        return True

    def reset(self) -> None:
        """Resetea valores filtrados y ventana, mantiene configuración."""
        self._fast_val = 0.0
        self._stable_val = 0.0
        self._hist.clear()
        self._initialized = False
        self._tare_offset = 0.0

    # ------------ Núcleo del filtro ------------

    def _apply_zero_tracking(self, v: float) -> float:
        if self.zero_tracking and abs(v) <= self.zero_epsilon:
            return 0.0
        return v

    def update(self, raw_value: float) -> Tuple[float, float, StabilityInfo]:
        """
        Procesa un nuevo valor (ya calibrado en 'g' si lo haces fuera).
        Devuelve (fast, stable, info)
        """
        # Aplicar tara
        v = float(raw_value) - self._tare_offset
        v = self._apply_zero_tracking(v)

        if not self._initialized:
            # primer valor
            self._fast_val = v
            self._stable_val = v
            self._initialized = True
        else:
            # Exponential Moving Average
            self._fast_val   = self.fast_alpha   * v + (1.0 - self.fast_alpha)   * self._fast_val
            self._stable_val = self.stable_alpha * v + (1.0 - self.stable_alpha) * self._stable_val

        # Ventana de estabilidad
        self._hist.append(v)

        # Cálculo de span (max-min)
        if len(self._hist) >= max(3, int(self.stability_window * 0.8)):
            span = (max(self._hist) - min(self._hist)) if self._hist else float("inf")
        else:
            span = float("inf")

        is_stable = (len(self._hist) >= self.stable_min_samples) and (span <= self.stability_threshold)

        info = StabilityInfo(
            is_stable=is_stable,
            std_window=0.0,        # reservado para futuro: cálculo de std si lo necesitas
            span_window=span,
            last_value=v
        )
        return self._fast_val, self._stable_val, info
