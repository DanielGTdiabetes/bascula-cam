from __future__ import annotations

import time
from collections import deque
from typing import Deque, Tuple, Optional


class AppState:
    """Estado global ligero para BG y flujos (hipo)."""

    def __init__(self) -> None:
        self.hypo_modal_open: bool = False
        self.hypo_started_ts: Optional[float] = None
        self.hypo_cycle: int = 0
        # Guardar últimas N lecturas (t, mgdl)
        self._bg_points: Deque[Tuple[float, float]] = deque(maxlen=12)
        # Último estado de normalización
        self._normalized_since: Optional[float] = None

    def clear_hypo_flow(self) -> None:
        self.hypo_modal_open = False
        self.hypo_started_ts = None

    def update_bg(self, mgdl: float, direction: Optional[str] = None, t: Optional[float] = None) -> dict:
        """Actualiza buffer BG y evalúa normalización/cancelación.

        Returns: { 'normalized': bool, 'cancel_recovery': bool }
        """
        try:
            v = float(mgdl)
        except Exception:
            v = 0.0
        ts = float(t if t is not None else time.time())
        self._bg_points.append((ts, v))

        # Cancel recovery if drops below 80
        cancel_recovery = v < 80.0

        normalized = False
        # Criterion B: single >=100 and non-descending trend
        if v >= 100.0:
            non_desc = True
            d = (direction or '').lower()
            if any(k in d for k in ['down']):
                non_desc = False
            normalized = non_desc
        else:
            # Criterion A: two points >=90 at least 5 min apart
            pts = [(tt, vv) for (tt, vv) in reversed(self._bg_points) if vv >= 90.0]
            if len(pts) >= 2:
                t1, _ = pts[0]
                # find second >=5 min apart
                for t2, _ in pts[1:]:
                    if abs(t1 - t2) >= 300.0:
                        normalized = True
                        break

        if normalized:
            if self._normalized_since is None:
                self._normalized_since = ts
        else:
            self._normalized_since = None

        return {'normalized': bool(normalized), 'cancel_recovery': bool(cancel_recovery)}

