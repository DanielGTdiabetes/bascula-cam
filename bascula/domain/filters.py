import statistics
from collections import deque
from dataclasses import dataclass

@dataclass
class FilterResult:
    filtered: float
    display: float
    stable: bool
    zero_tracking: bool

class ProfessionalWeightFilter:
    def __init__(self, cfg):
        self.iir_alpha = cfg.iir_alpha
        self.median_window = cfg.median_window
        self.stability_window = cfg.stability_window
        self.zero_band = cfg.zero_band
        self.display_resolution = cfg.display_resolution
        self.auto_zero_rate = cfg.auto_zero_rate
        self.stability_threshold = cfg.stability_threshold

        self.raw = deque(maxlen=self.median_window)
        self.buf = deque(maxlen=self.stability_window)
        self.display_buf = deque(maxlen=5)

        self.filtered = 0.0
        self.display = 0.0
        self.tare_offset = 0.0
        self.stable = False
        self.stable_count = 0
        self.zero_count = 0
        self.zero_tracking = True

    def step(self, value: float) -> FilterResult:
        self.raw.append(value)
        med = statistics.median(self.raw) if len(self.raw) >= 3 else value
        a = self.iir_alpha * (0.5 if self.stable else 1.0)
        self.filtered = (1-a)*self.filtered + a*med if self.buf else med
        self.buf.append(self.filtered)
        self._update_stability()
        self._auto_zero()
        tared = self.filtered + self.tare_offset
        self.display = 0.0 if abs(tared) <= self.zero_band else round(tared / self.display_resolution) * self.display_resolution
        self.display_buf.append(self.display)
        return FilterResult(self.filtered, self.display, self.stable, self.zero_tracking)

    def _update_stability(self):
        if len(self.buf) < self.stability_window:
            self.stable = False; self.stable_count = 0; return
        std = statistics.pstdev(self.buf) if len(self.buf) > 1 else 0.0
        if std <= self.stability_threshold:
            self.stable_count += 1; self.stable = self.stable_count >= 5
        else:
            self.stable_count = 0; self.stable = False

    def _auto_zero(self):
        if abs(self.filtered) <= self.zero_band and self.stable:
            self.zero_count += 1
            if self.zero_tracking and self.zero_count >= 6:
                self.tare_offset += -self.filtered * self.auto_zero_rate
                self.zero_count = 0
        else:
            self.zero_count = 0

    def tara(self) -> bool:
        if len(self.buf) >= 3:
            avg = sum(self.buf)/len(self.buf)
            self.tare_offset += -avg
            self.display = 0.0
            return True
        return False

    def set_zero_tracking(self, enabled: bool):
        self.zero_tracking = enabled
