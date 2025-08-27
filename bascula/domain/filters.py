from __future__ import annotations
from collections import deque
from dataclasses import dataclass


@dataclass
class StabilityInfo:
    is_stable: bool
    std_window: float
    span_window: float
    last_value: float


class ProfessionalWeightFilter:
    """
    Filtro con dos salidas: rápida (reactiva) y estable (suavizada).
    También detecta estabilidad usando ventana deslizante.
    """
    def __init__(self, fast_alpha: float=0.45, stable_alpha: float=0.18, stability_window: int=8, stability_threshold: float=0.10):
        self.fast_alpha = max(0.01, min(0.95, fast_alpha))
        self.stable_alpha = max(0.01, min(0.95, stable_alpha))
        self.stability_window = max(3, int(stability_window))
        self.stability_threshold = max(0.01, float(stability_threshold))
        self._fast_val = None
        self._stable_val = None
        self._hist = deque(maxlen=self.stability_window)

    def reset(self):
        self._fast_val = None
        self._stable_val = None
        self._hist.clear()

    def update(self, value: float) -> tuple[float, float, StabilityInfo]:
        v = float(value)
        if self._fast_val is None:
            self._fast_val = v
        else:
            self._fast_val = self.fast_alpha * v + (1 - self.fast_alpha) * self._fast_val

        if self._stable_val is None:
            self._stable_val = v
        else:
            self._stable_val = self.stable_alpha * v + (1 - self.stable_alpha) * self._stable_val

        self._hist.append(v)

        if len(self._hist) >= max(3, int(self.stability_window * 0.8)):
            span = max(self._hist) - min(self._hist)
        else:
            span = float("inf")

        is_stable = span <= self.stability_threshold

        info = StabilityInfo(is_stable=is_stable, std_window=0.0, span_window=span, last_value=v)
        return self._fast_val, self._stable_val, info
