"""Nightscout integration helpers for glucose polling and meal export."""

from __future__ import annotations

import datetime as _dt
import logging
import threading
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Optional

from . import treatments

try:  # pragma: no cover - optional dependency
    import tomllib  # Python 3.11+
except Exception:  # pragma: no cover - optional dependency
    tomllib = None  # type: ignore

try:  # pragma: no cover - optional dependency
    import requests  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    requests = None  # type: ignore

log = logging.getLogger(__name__)


CFG_DIR = Path(Path.home() / ".config" / "bascula")
CFG_FILE = Path(CFG_DIR / "diabetes.toml")


@dataclass
class NightscoutReading:
    """Represents a Nightscout BG reading."""

    mgdl: int
    direction: str
    timestamp: _dt.datetime

    def iso(self) -> str:
        return self.timestamp.replace(tzinfo=_dt.timezone.utc).isoformat().replace("+00:00", "Z")


class NightscoutClient:
    """Polls Nightscout periodically and exposes helpers for UI integration."""

    POLL_INTERVAL = 60

    def __init__(self) -> None:
        self._config = self._load_config()
        self._listeners: List[Callable[[Dict[str, object]], None]] = []
        self._latest: Optional[NightscoutReading] = None
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        if self._config.get("url"):
            self._start_thread()

    # ------------------------------------------------------------------
    # Configuration helpers
    # ------------------------------------------------------------------
    def _load_config(self) -> Dict[str, object]:
        defaults: Dict[str, object] = {
            "url": "",
            "token": "",
            "icr": 10.0,
            "isf": 50.0,
            "target": 110,
            "enable_bolus_assistant": False,
            "export_mode": "carbs_only",
            "enable_1515": True,
            "low_threshold": 70,
            "high_threshold": 180,
            "alarms_enabled": True,
            "announce_on_alarm": True,
        }
        if tomllib is None:
            return defaults
        try:
            if CFG_FILE.exists():
                data = tomllib.loads(CFG_FILE.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    defaults.update({k: data.get(k, v) for k, v in defaults.items()})
                    # Allow additional keys without whitelisting
                    for key, value in data.items():
                        if key not in defaults:
                            defaults[key] = value
        except Exception:
            log.debug("No se pudo leer configuración diabetes", exc_info=True)
        return defaults

    def get_config(self) -> Dict[str, object]:
        with self._lock:
            return dict(self._config)

    # ------------------------------------------------------------------
    # Polling
    # ------------------------------------------------------------------
    def _start_thread(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self._poll_loop, name="NightscoutPoll", daemon=True)
        self._thread.start()

    def _poll_loop(self) -> None:  # pragma: no cover - thread loop
        while not self._stop.is_set():
            try:
                reading = self._poll_once()
                if reading:
                    self._notify_listeners(reading)
            except Exception:
                log.debug("Error consultando Nightscout", exc_info=True)
            self._stop.wait(self.POLL_INTERVAL)

    def _poll_once(self) -> Optional[NightscoutReading]:
        cfg = self.get_config()
        base_url = (cfg.get("url") or "").rstrip("/")
        if not base_url or requests is None:
            return None
        try:
            resp = requests.get(
                f"{base_url}/api/v1/entries.json?count=1",
                headers=self._headers(cfg),
                timeout=6,
            )
            if not (200 <= getattr(resp, "status_code", 0) < 300):
                raise RuntimeError(f"ns_http_{getattr(resp, 'status_code', 'err')}")
            payload = resp.json()
        except Exception:
            log.debug("Nightscout no disponible", exc_info=True)
            return None

        if not isinstance(payload, list) or not payload:
            return None
        entry = payload[0]
        value = entry.get("sgv") or entry.get("sgv_mgdl") or entry.get("glucose")
        try:
            mgdl = int(round(float(value)))
        except Exception:
            return None
        direction = str(entry.get("direction") or entry.get("trend") or "").strip() or "Flat"
        timestamp = self._parse_timestamp(entry)
        reading = NightscoutReading(mgdl=mgdl, direction=direction, timestamp=timestamp)
        with self._lock:
            self._latest = reading
        return reading

    def _headers(self, cfg: Dict[str, object]) -> Dict[str, str]:
        headers = {"Accept": "application/json"}
        token = str(cfg.get("token") or "").strip()
        if token:
            headers["API-SECRET"] = token
        return headers

    @staticmethod
    def _parse_timestamp(entry: Dict[str, object]) -> _dt.datetime:
        date_str = entry.get("dateString") or entry.get("date")
        if isinstance(date_str, str):
            try:
                return _dt.datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            except Exception:
                pass
        try:
            ts = float(entry.get("date", 0) or 0) / 1000.0
            return _dt.datetime.utcfromtimestamp(ts)
        except Exception:
            return _dt.datetime.utcnow()

    # ------------------------------------------------------------------
    # Listener handling
    # ------------------------------------------------------------------
    def add_listener(self, callback: Callable[[Dict[str, object]], None]) -> None:
        if not callable(callback):
            return
        self._listeners.append(callback)
        latest = self.get_latest()
        if latest:
            callback(self._payload_for_reading(latest))

    def _notify_listeners(self, reading: NightscoutReading) -> None:
        payload = self._payload_for_reading(reading)
        for callback in list(self._listeners):
            try:
                callback(payload)
            except Exception:  # pragma: no cover - defensive
                log.debug("Listener Nightscout falló", exc_info=True)

    def _payload_for_reading(self, reading: NightscoutReading) -> Dict[str, object]:
        cfg = self.get_config()
        return {
            "mgdl": reading.mgdl,
            "direction": reading.direction,
            "timestamp": reading.iso(),
            "config": cfg,
        }

    def get_latest(self) -> Optional[NightscoutReading]:
        with self._lock:
            return self._latest

    # ------------------------------------------------------------------
    # Bolus helpers / export
    # ------------------------------------------------------------------
    def compute_bolus(self, carbs_g: float, current_bg: float) -> treatments.TreatmentCalc:
        cfg = self.get_config()
        ratio = float(cfg.get("icr", 10.0) or 10.0)
        isf = float(cfg.get("isf", 50.0) or 50.0)
        target = int(cfg.get("target", 110) or 110)
        return treatments.calc_bolus(
            grams_carbs=float(carbs_g or 0.0),
            target_bg=target,
            current_bg=int(round(float(current_bg or 0.0))),
            isf=isf,
            ratio=ratio,
        )

    def export_meal(
        self,
        totals: Dict[str, float],
        items: Iterable[Dict[str, object]],
        calc: treatments.TreatmentCalc,
        record: Optional[Dict[str, object]] = None,
        include_bolus: Optional[bool] = None,
    ) -> bool:
        cfg = self.get_config()
        mode = str(cfg.get("export_mode", "with_bolus") or "with_bolus").lower()
        if include_bolus is None:
            include_bolus = mode == "with_bolus"
        payload = self._build_payload(totals, items, calc, record, include_bolus)
        url = str(cfg.get("url", "") or "")
        token = str(cfg.get("token", "") or "")
        return treatments.post_treatment(url, token, payload)

    @staticmethod
    def _build_payload(
        totals: Dict[str, float],
        items: Iterable[Dict[str, object]],
        calc: treatments.TreatmentCalc,
        record: Optional[Dict[str, object]],
        include_bolus: bool,
    ) -> Dict[str, object]:
        items_list: List[Dict[str, object]] = []
        for it in items:
            if isinstance(it, dict):
                items_list.append(dict(it))
            else:
                try:
                    items_list.append(asdict(it))
                except Exception:
                    attrs = getattr(it, "__dict__", {})
                    if isinstance(attrs, dict):
                        items_list.append(dict(attrs))
                    else:
                        items_list.append({})
        total_carbs = float(totals.get("carbs_g", 0.0) or 0.0)
        total_grams = float(totals.get("grams", 0.0) or 0.0)
        n_items = len(items_list)
        gi_values = [it.get("gi") for it in items_list if it.get("gi") is not None]
        if gi_values:
            gi_note = f"GI prom {round(sum(float(v) for v in gi_values) / len(gi_values))}"
        else:
            gi_note = "GI N/D"
        event_type = "Meal Bolus" if include_bolus else "Meal"
        payload: Dict[str, object] = {
            "eventType": event_type,
            "carbs": round(total_carbs),
            "notes": f"BasculaCam: {n_items} items, {int(total_grams)} g, {gi_note}",
        }
        if include_bolus:
            payload["insulin"] = float(calc.bolus)
        if record and record.get("created_at"):
            payload["created_at"] = record["created_at"]
        return payload

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------
    def stop(self) -> None:  # pragma: no cover - cleanup helper
        self._stop.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)


__all__ = ["NightscoutClient", "NightscoutReading"]

