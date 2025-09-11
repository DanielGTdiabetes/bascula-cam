from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Any, Optional
import uuid, datetime, json

try:
    import requests  # type: ignore
except Exception:
    requests = None  # Fallback handled below

from .offqueue import OfflineQueue


@dataclass
class TreatmentCalc:
    bolus: float
    peak_time_min: int


def calc_bolus(grams_carbs: float, target_bg: int, current_bg: int, isf: float, ratio: float) -> TreatmentCalc:
    """Cálculo simple de bolo: carbs/ratio + (current-target)/isf.
    Returns bolus and a rough time-to-peak (mins)."""
    carbs_bolus = max(0.0, float(grams_carbs) / max(1e-6, float(ratio)))
    correction = max(0.0, (float(current_bg) - float(target_bg)) / max(1e-6, float(isf)))
    bolus = round(carbs_bolus + correction, 2)
    # Rough heuristics for peak time
    peak = 60  # default
    if grams_carbs > 60:
        peak = 90
    elif grams_carbs < 20:
        peak = 45
    return TreatmentCalc(bolus=bolus, peak_time_min=peak)


def _utc_iso(dt: Optional[datetime.datetime] = None) -> str:
    dt = (dt or datetime.datetime.utcnow()).replace(tzinfo=datetime.timezone.utc)
    # Nightscout acepta ISO8601 con 'Z'
    return dt.isoformat().replace("+00:00", "Z")


def post_treatment(base_url: str, token: str, payload: Dict[str, Any]) -> bool:
    """Envía un tratamiento a Nightscout con fallback a cola offline.

    - Endpoint: POST {base_url}/api/v1/treatments
    - Incluye `created_at` en UTC ISO8601 y `externalId` con prefijo 'meal:' y uuid.
    - Si falla (sin requests, error de red o HTTP!=2xx), guarda en cola offline para reintento.
    """
    base_url = (base_url or "").rstrip("/")
    if not base_url:
        # Sin URL configurada, encolar directamente
        OfflineQueue("ns_queue").enqueue({
            "type": "ns_treatment",
            "payload": payload,
            "token": token or "",
            "ts": datetime.datetime.utcnow().timestamp(),
        })
        return False

    data = dict(payload or {})
    # created_at y externalId requeridos por Nightscout
    if not data.get("created_at"):
        data["created_at"] = _utc_iso()
    if not data.get("externalId"):
        data["externalId"] = f"meal:{uuid.uuid4()}"
    # enteredBy amigable
    data.setdefault("enteredBy", "BasculaCam")

    # Preparar POST
    url = f"{base_url}/api/v1/treatments"
    headers = {"Content-Type": "application/json"}
    if token:
        headers["API-SECRET"] = token

    try:
        if requests is None:
            raise RuntimeError("requests_unavailable")
        resp = requests.post(url, headers=headers, data=json.dumps(data), timeout=8)
        ok = 200 <= getattr(resp, "status_code", 0) < 300
        if not ok:
            raise RuntimeError(f"ns_http_{getattr(resp, 'status_code', 'err')}")
        return True
    except Exception:
        # Guardar en cola offline para reintento posterior
        OfflineQueue("ns_queue").enqueue({
            "type": "ns_treatment",
            "payload": data,
            "token": token or "",
        })
        return False
