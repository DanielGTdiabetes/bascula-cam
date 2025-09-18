"""Runtime memory monitor for diagnostic overlays."""
from __future__ import annotations

import gc
import logging
import os
from dataclasses import dataclass
from typing import Optional

try:
    import psutil  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    psutil = None

logger = logging.getLogger("bascula.ui.memory_monitor")


@dataclass(slots=True)
class MemorySnapshot:
    rss_mb: float
    vms_mb: float


class MemoryMonitor:
    def __init__(self, *, threshold_mb: float = 150.0) -> None:
        self.threshold_mb = float(threshold_mb)
        self._last_snapshot: Optional[MemorySnapshot] = None

    def measure(self) -> MemorySnapshot:
        if psutil is not None:
            proc = psutil.Process(os.getpid())
            mem = proc.memory_info()
            snap = MemorySnapshot(rss_mb=mem.rss / (1024 * 1024), vms_mb=mem.vms / (1024 * 1024))
        else:
            try:
                with open("/proc/self/statm", "r", encoding="utf-8") as fh:
                    parts = fh.read().split()
                    rss = int(parts[1]) * (os.sysconf("SC_PAGE_SIZE") / (1024 * 1024))
                    vms = int(parts[0]) * (os.sysconf("SC_PAGE_SIZE") / (1024 * 1024))
                    snap = MemorySnapshot(rss_mb=float(rss), vms_mb=float(vms))
            except Exception:
                snap = MemorySnapshot(rss_mb=0.0, vms_mb=0.0)
        self._last_snapshot = snap
        if snap.rss_mb > self.threshold_mb:
            logger.warning("Uso de memoria elevado: %.1f MB", snap.rss_mb)
        return snap

    def maybe_collect(self) -> MemorySnapshot:
        gc.collect()
        snap = self.measure()
        return snap

    def last(self) -> MemorySnapshot:
        if self._last_snapshot is None:
            return self.measure()
        return self._last_snapshot

