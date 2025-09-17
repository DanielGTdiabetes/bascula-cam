from __future__ import annotations

import json
import os
import time
from collections import deque
from pathlib import Path
from typing import Deque, Dict, List, Optional, Tuple

try:
    import requests  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    requests = None


class BgMonitor:
    """Nightscout polling helper with basic trend prediction."""

    def __init__(self, app, interval_s: int = 60) -> None:
        self.app = app
        self.interval_s = max(30, int(interval_s))
        self._job: Optional[str] = None
        self._last_entry_ts: float = 0.0
        self._history: Deque[Tuple[float, float]] = deque(maxlen=8)
        self.bg: Optional[int] = None
        self.trend: str = ""
        self.timestamp: Optional[float] = None
        self.delta: Optional[float] = None
        self.bg_pred_15: Optional[int] = None
        self.bg_pred_30: Optional[int] = None

    # ------------------------------------------------------------------ lifecycle
    def start(self) -> None:
        self._schedule_tick(0)

    def stop(self) -> None:
        if self._job is not None:
            try:
                self.app.root.after_cancel(self._job)
            except Exception:
                pass
            self._job = None

    # ------------------------------------------------------------------ helpers
    def _schedule_tick(self, delay_ms: int) -> None:
        try:
            self._job = self.app.root.after(delay_ms, self._tick)
        except Exception:
            self._job = None

    def _read_ns_cfg(self) -> Tuple[str, str]:
        cfg_dir_env = os.environ.get("BASCULA_CFG_DIR", "").strip()
        cfg_dir = Path(cfg_dir_env) if cfg_dir_env else (Path.home() / ".config" / "bascula")
        path = cfg_dir / "nightscout.json"
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return data.get("url", "").strip().rstrip("/"), data.get("token", "").strip()
        except Exception:
            return "", ""

    def _fetch_entries(self, url: str, token: str) -> List[Dict]:
        if requests is None or not url:
            return []
        try:
            resp = requests.get(
                f"{url}/api/v1/entries.json",
                params={"count": 6, "token": token},
                timeout=8,
            )
            if resp.ok:
                data = resp.json()
                if isinstance(data, list):
                    return data
        except Exception:
            self._publish_error("Nightscout sin datos")
        return []

    def _extract_timestamp(self, entry: Dict) -> Optional[float]:
        if not isinstance(entry, dict):
            return None
        date_ms = entry.get("date")
        if isinstance(date_ms, (int, float)):
            return float(date_ms) / 1000.0
        date_str = entry.get("dateString")
        if isinstance(date_str, str):
            try:
                from datetime import datetime

                return datetime.fromisoformat(date_str.replace("Z", "+00:00")).timestamp()
            except Exception:
                pass
        return None

    def _parse_bg(self, entry: Dict) -> Optional[int]:
        for key in ("sgv", "glucose", "bg"):
            value = entry.get(key)
            try:
                if value is not None:
                    return int(float(value))
            except Exception:
                continue
        return None

    def _parse_trend(self, entry: Dict) -> str:
        raw = str(entry.get("direction", "")).lower()
        if "up" in raw:
            return "up"
        if "down" in raw:
            return "down"
        if "flat" in raw:
            return "flat"
        return ""

    def _compute_predictions(self) -> None:
        if len(self._history) < 2:
            self.bg_pred_15 = None
            self.bg_pred_30 = None
            return
        first_ts, first_val = self._history[0]
        last_ts, last_val = self._history[-1]
        span_min = (last_ts - first_ts) / 60.0
        if span_min <= 0:
            slope = 0.0
        else:
            slope = (last_val - first_val) / span_min
        self.bg_pred_15 = int(round(last_val + slope * 15))
        self.bg_pred_30 = int(round(last_val + slope * 30))

    def _publish_error(self, message: str) -> None:
        try:
            self.app.on_bg_error(message)
        except Exception:
            pass
        try:
            self.app.event_bus.publish("bg_error", {"message": message})
        except Exception:
            pass

    def _publish_update(self) -> None:
        payload = {
            "value": self.bg,
            "trend": self.trend,
            "timestamp": self.timestamp,
            "delta": self.delta,
            "pred_15": self.bg_pred_15,
            "pred_30": self.bg_pred_30,
        }
        try:
            self.app.event_bus.publish("bg_update", payload)
            self.app.event_bus.publish("BG_UPDATE", payload)
        except Exception:
            pass
        cfg = self.app.get_cfg()
        low = int(cfg.get("bg_low_threshold", cfg.get("bg_low_mgdl", 70)))
        high = int(cfg.get("bg_high_threshold", cfg.get("bg_high_mgdl", 180)))
        value = self.bg or 0
        if value and value <= low:
            try:
                self.app.event_bus.publish("bg_low", payload)
                self.app.event_bus.publish("BG_HYPO", payload)
            except Exception:
                pass
        elif value and value >= high:
            try:
                self.app.event_bus.publish("bg_high", payload)
            except Exception:
                pass
        else:
            try:
                self.app.event_bus.publish("BG_NORMAL", payload)
            except Exception:
                pass

    # ------------------------------------------------------------------ polling loop
    def _tick(self) -> None:
        url, token = self._read_ns_cfg()
        entries = self._fetch_entries(url, token)
        updated = False
        for entry in sorted(entries, key=lambda e: self._extract_timestamp(e) or 0.0):
            ts = self._extract_timestamp(entry)
            value = self._parse_bg(entry)
            if ts is None or value is None:
                continue
            if ts <= self._last_entry_ts:
                continue
            prev_bg = self.bg
            self.bg = value
            self.trend = self._parse_trend(entry)
            self.timestamp = ts
            self.delta = value - prev_bg if prev_bg is not None else None
            self._last_entry_ts = ts
            self._history.append((ts, float(value)))
            self._compute_predictions()
            updated = True
        if updated:
            try:
                self.app.on_bg_update(self.bg, self.trend)
            except Exception:
                pass
            self._publish_update()
        self._schedule_tick(self.interval_s * 1000)
