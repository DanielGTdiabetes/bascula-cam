# -*- coding: utf-8 -*-
from __future__ import annotations

import json, os
from pathlib import Path

try:
    import requests  # type: ignore
except Exception:  # pragma: no cover - graceful fallback
    requests = None


class BgMonitor:
    """Polls Nightscout for the latest BG value using Tk's ``after``."""

    def __init__(self, app, interval_s: int = 60):
        self.app = app
        self.interval_s = interval_s
        self._job = None
        self._last_bg: tuple[int, str] | None = None

    def start(self) -> None:
        self._tick()

    def stop(self) -> None:
        if self._job is not None:
            try:
                self.app.root.after_cancel(self._job)
            except Exception:
                pass
            self._job = None

    # ---- internal helpers -----------------------------------------
    def _read_ns_cfg(self) -> tuple[str, str]:
        cfg_dir_env = os.environ.get("BASCULA_CFG_DIR", "").strip()
        cfg_dir = Path(cfg_dir_env) if cfg_dir_env else (Path.home() / ".config" / "bascula")
        try:
            data = json.loads((cfg_dir / "nightscout.json").read_text(encoding="utf-8"))
            return data.get("url", "").strip().rstrip("/"), data.get("token", "").strip()
        except Exception:
            return "", ""

    def _tick(self) -> None:
        url, token = self._read_ns_cfg()
        if requests is not None and url:
            try:
                resp = requests.get(
                    f"{url}/api/v1/entries.json",
                    params={"count": 1, "token": token},
                    timeout=8,
                )
                if resp.ok:
                    arr = resp.json()
                    if isinstance(arr, list) and arr:
                        entry = arr[0]
                        try:
                            val = int(entry.get("sgv") or entry.get("glucose"))
                        except Exception:
                            val = None
                        if val is not None:
                            trend_raw = str(entry.get("direction", ""))
                            trend = {
                                "DoubleUp": "up",
                                "SingleUp": "up",
                                "FortyFiveUp": "up",
                                "DoubleDown": "down",
                                "SingleDown": "down",
                                "FortyFiveDown": "down",
                                "Flat": "flat",
                            }.get(trend_raw, "")
                            bg_tuple = (val, trend)
                            if bg_tuple != self._last_bg:
                                self._last_bg = bg_tuple
                                try:
                                    self.app.on_bg_update(val, trend)
                                except Exception:
                                    pass
            except Exception:
                try:
                    self.app.on_bg_error("Nightscout sin datos")
                except Exception:
                    pass

        self._job = self.app.root.after(self.interval_s * 1000, self._tick)
