from dataclasses import dataclass
from typing import Optional

@dataclass
class TareState:
    tare_offset: Optional[float] = None
    calib_factor: float = 1.0

class TareManager:
    def __init__(self, calib_factor: float = 1.0, min_display: float = 0.0):
        self.state = TareState(tare_offset=None, calib_factor=calib_factor)
        self._min_display = min_display

    def update_calib(self, calib_factor: float):
        if calib_factor <= 0:
            raise ValueError("calib_factor debe ser > 0")
        self.state.calib_factor = calib_factor

    def set_tare(self, raw_value: float):
        self.state.tare_offset = float(raw_value)

    def clear_tare(self):
        self.state.tare_offset = None

    def compute_net(self, raw_value: float) -> float:
        raw = float(raw_value)
        offset = self.state.tare_offset or 0.0
        net = (raw - offset) * self.state.calib_factor
        net = round(net, 2)
        if net < self._min_display:
            net = self._min_display
        return net
