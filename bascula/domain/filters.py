"""Filtering primitives used by the scale service."""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from statistics import mean
from typing import Deque, Iterable


@dataclass
class StabilityResult:
    value: float
    stable: bool


@dataclass
class ProfessionalWeightFilter:
    """Moving average based stability filter for scale readings."""

    window: int = 10
    stability_tolerance: float = 0.5
    noise_threshold: float = 3.0
    _samples: Deque[float] = field(default_factory=deque, init=False)

    def add_sample(self, value: float) -> StabilityResult:
        if len(self._samples) >= self.window:
            self._samples.popleft()
        self._samples.append(float(value))
        smoothed = mean(self._samples)
        stable = self._is_stable(smoothed)
        return StabilityResult(value=smoothed, stable=stable)

    def _is_stable(self, current: float) -> bool:
        if len(self._samples) < self.window:
            return False
        min_v = min(self._samples)
        max_v = max(self._samples)
        if max_v - min_v > self.noise_threshold:
            return False
        if not self._samples:
            return False
        return all(abs(current - sample) <= self.stability_tolerance for sample in self._samples)

    def reset(self) -> None:
        self._samples.clear()

    def history(self) -> Iterable[float]:
        return tuple(self._samples)


__all__ = ["ProfessionalWeightFilter", "StabilityResult"]
