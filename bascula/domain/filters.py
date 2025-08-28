from __future__ import annotations
from collections import deque
from dataclasses import dataclass
from typing import Deque, Tuple

@dataclass
class StabilityInfo:
    is_stable: bool
    std_window: float
    span_window: float
    last_value: float = 0.0

class ProfessionalWeightFilter:
    def __init__(self, cfg):
        f = cfg
        self.fast_alpha = max(0.01, min(0.95, float(getattr(f, "fast_alpha", f.fast_alpha))))
        self.stable_alpha = max(0.01, min(0.95, float(getattr(f, "stable_alpha", f.stable_alpha))))
        self.stability_window = max(3, int(getattr(f, "stability_window", f.stability_window)))
        self.stability_threshold = float(getattr(f, "stability_threshold", f.stability_threshold))
        self.zero_tracking = bool(getattr(f, "zero_tracking", f.zero_tracking))
        self.zero_epsilon = float(getattr(f, "zero_epsilon", f.zero_epsilon))
        self.stable_min_samples = int(getattr(f, "stable_min_samples", f.stable_min_samples))

        self._fast = 0.0
        self._stable = 0.0
        self._hist: Deque[float] = deque(maxlen=self.stability_window)
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

    def update(self, grams: float) -> Tuple[float, float, StabilityInfo]:
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
        return self._fast, self._stable, StabilityInfo(is_stable=stable, std_window=0.0, span_window=span, last_value=v)
