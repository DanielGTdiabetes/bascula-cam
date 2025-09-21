from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Any, Optional
import uuid, datetime, json
import logging
import os
import threading
import time
from pathlib import Path

try:
    import requests  # type: ignore
except Exception:
    requests = None  # Fallback handled below

from .offqueue import OfflineQueue


log = logging.getLogger(__name__)

_ENV_PATH = Path("/etc/default/bascula")
_DEFAULT_SHARED = Path("/opt/bascula/shared")
_DEFAULT_TIMERS = _DEFAULT_SHARED / "userdata" / "timers.json"
_FALLBACK_TIMERS = Path.home() / ".bascula" / "userdata" / "timers.json"

_TIMERS_LOCK = threading.Lock()
_TIMERS_PATH: Optional[Path] = None
_1515_TIMER: Optional[threading.Timer] = None
_1515_TIMER_VOICE: Optional[object] = None
_PREBOLUS_TIMER: Optional[threading.Timer] = None
_PREBOLUS_VOICE: Optional[object] = None

_PROTOCOL_KEY = "protocol_1515"
_PREBOLUS_KEY = "pre_bolus"
_PROTOCOL_SECONDS = 15 * 60


def _read_env_file(path: Path) -> Dict[str, str]:
    data: Dict[str, str] = {}
    try:
        with path.open("r", encoding="utf-8") as fh:
            for raw_line in fh:
                line = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                key = key.strip()
                if not key:
                    continue
                value = value.strip().strip('"').strip("'")
                data[key] = value
    except FileNotFoundError:
        return {}
    except Exception as exc:
        log.debug("No se pudo leer %s: %s", path, exc)
    return data


def _guess_shared_dir(env: Dict[str, str]) -> Optional[Path]:
    shared = env.get("BASCULA_SHARED")
    if shared:
        try:
            candidate = Path(shared)
            if candidate.exists():
                return candidate
        except Exception:
            pass

    prefix = env.get("BASCULA_PREFIX")
    if prefix:
        try:
            root = Path(prefix).parent
            candidate = root / "shared"
            if candidate.exists():
                return candidate
        except Exception:
            pass

    if _DEFAULT_SHARED.exists():
        return _DEFAULT_SHARED

    return None


def _resolve_timers_path() -> Path:
    global _TIMERS_PATH
    if _TIMERS_PATH is not None:
        return _TIMERS_PATH

    env = _read_env_file(_ENV_PATH)
    try:
        env.update(os.environ)
    except Exception:
        pass

    explicit = env.get("BASCULA_TIMERS_FILE")
    if explicit:
        candidate = Path(explicit)
        _TIMERS_PATH = candidate
        return candidate

    shared = _guess_shared_dir(env)
    if shared is not None:
        path = shared / "userdata" / "timers.json"
        _TIMERS_PATH = path
        return path

    _TIMERS_PATH = _DEFAULT_TIMERS
    return _TIMERS_PATH


def _set_timers_path(path: Path) -> None:
    global _TIMERS_PATH
    _TIMERS_PATH = path


def _timers_path() -> Path:
    return _resolve_timers_path()


def _ensure_parent(path: Path) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
    except Exception as exc:
        log.debug("No se pudo crear %s: %s", path.parent, exc)


def _read_all_timers() -> Dict[str, Any]:
    path = _timers_path()
    try:
        with path.open("r", encoding="utf-8") as fh:
            data = json.load(fh) or {}
        if isinstance(data, dict):
            return data
    except FileNotFoundError:
        return {}
    except Exception as exc:
        log.debug("No se pudo leer timers %s: %s", path, exc)
    return {}


def _write_all_timers(payload: Dict[str, Any]) -> None:
    path = _timers_path()
    _ensure_parent(path)
    try:
        tmp = path.with_suffix(path.suffix + ".tmp")
        with tmp.open("w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
    except (PermissionError, OSError) as exc:
        if path != _FALLBACK_TIMERS:
            log.debug("Fallo escribiendo %s: %s. Probando fallback %s", path, exc, _FALLBACK_TIMERS)
            _set_timers_path(_FALLBACK_TIMERS)
            _ensure_parent(_FALLBACK_TIMERS)
            _write_all_timers(payload)
        else:
            log.warning("No se pudo persistir timers %s: %s", path, exc)
    except Exception as exc:
        log.debug("Error escribiendo timers %s: %s", path, exc)


def _speak(voice: Optional[object], text: str) -> None:
    if not voice or not text:
        return
    try:
        speak_fn = getattr(voice, "speak", None)
        if callable(speak_fn):
            speak_fn(text)
    except Exception as exc:
        log.debug("No se pudo reproducir voz: %s", exc)


def _ack_voice_flag(key: str) -> None:
    with _TIMERS_LOCK:
        data = _read_all_timers()
        state = data.get(key)
        if isinstance(state, dict) and state.get("needs_voice"):
            state["needs_voice"] = False
            data[key] = state
            _write_all_timers(data)


def _schedule_timer(handle_attr: str, voice_attr: str, seconds: float, on_fire) -> None:
    global _1515_TIMER, _1515_TIMER_VOICE, _PREBOLUS_TIMER, _PREBOLUS_VOICE

    timer_ref = globals()[handle_attr]
    if timer_ref is not None:
        try:
            timer_ref.cancel()
        except Exception:
            pass
    globals()[handle_attr] = None
    globals()[voice_attr] = None

    if seconds <= 0:
        return

    timer = threading.Timer(seconds, on_fire)
    timer.daemon = True
    globals()[handle_attr] = timer
    globals()[voice_attr] = None
    timer.start()


def _schedule_1515(seconds: float, voice: Optional[object]) -> None:
    def _fire() -> None:
        _complete_1515_cycle()

    _schedule_timer("_1515_TIMER", "_1515_TIMER_VOICE", seconds, _fire)
    if voice and hasattr(voice, "speak"):
        globals()["_1515_TIMER_VOICE"] = voice


def _schedule_prebolus(seconds: float, voice: Optional[object]) -> None:
    def _fire() -> None:
        _complete_prebolus_cycle()

    _schedule_timer("_PREBOLUS_TIMER", "_PREBOLUS_VOICE", seconds, _fire)
    if voice and hasattr(voice, "speak"):
        globals()["_PREBOLUS_VOICE"] = voice


def _complete_1515_cycle() -> None:
    voice = globals().get("_1515_TIMER_VOICE")
    globals()["_1515_TIMER"] = None
    globals()["_1515_TIMER_VOICE"] = None
    now = time.time()
    should_speak = False
    with _TIMERS_LOCK:
        data = _read_all_timers()
        state = data.get("protocol_1515")
        if isinstance(state, dict) and state.get("active"):
            state["status"] = "awaiting_recheck"
            state["last_alert_ts"] = now
            state["needs_voice"] = True
            data["protocol_1515"] = state
            _write_all_timers(data)
            should_speak = True
    if should_speak:
        if voice:
            _speak(voice, "Han pasado quince minutos. Revisa tu glucosa.")
            _ack_voice_flag("protocol_1515")


def _complete_prebolus_cycle() -> None:
    voice = globals().get("_PREBOLUS_VOICE")
    globals()["_PREBOLUS_TIMER"] = None
    globals()["_PREBOLUS_VOICE"] = None
    now = time.time()
    should_speak = False
    with _TIMERS_LOCK:
        data = _read_all_timers()
        state = data.get("pre_bolus")
        if isinstance(state, dict) and state.get("active"):
            state["status"] = "ready"
            state["last_alert_ts"] = now
            state["needs_voice"] = True
            data["pre_bolus"] = state
            _write_all_timers(data)
            should_speak = True
    if should_speak:
        if voice:
            minutes = None
            try:
                minutes = int(state.get("minutes", 0)) if isinstance(state, dict) else None
            except Exception:
                minutes = None
            msg = "Ya puedes aplicar el bolo." if not minutes else (
                f"Ya pasaron los {int(minutes)} minutos de pre bolo."
            )
            _speak(voice, msg)
            _ack_voice_flag("pre_bolus")





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


def _ensure_protocol_state(state: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not isinstance(state, dict):
        return {"active": False, "status": "idle", "cycles": 0}
    sanitized = dict(state)
    sanitized.setdefault("active", False)
    sanitized.setdefault("status", "idle" if not sanitized.get("active") else "countdown")
    try:
        sanitized["cycles"] = int(sanitized.get("cycles", 0) or 0)
    except Exception:
        sanitized["cycles"] = 0
    return sanitized


def _ensure_prebolus_state(state: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not isinstance(state, dict):
        return {"active": False, "status": "idle", "minutes": 0}
    sanitized = dict(state)
    sanitized.setdefault("active", False)
    sanitized.setdefault("status", "idle" if not sanitized.get("active") else "countdown")
    try:
        sanitized["minutes"] = int(sanitized.get("minutes", 0) or 0)
    except Exception:
        sanitized["minutes"] = 0
    return sanitized


def start_1515(voice: Optional[object] = None) -> Dict[str, Any]:
    """Inicia el protocolo 15/15 (15 g y 15 minutos de espera)."""

    now = time.time()
    next_ts = now + _PROTOCOL_SECONDS
    with _TIMERS_LOCK:
        timers = _read_all_timers()
        state = {
            "active": True,
            "status": "countdown",
            "cycles": 1,
            "started_ts": now,
            "cycle_started_ts": now,
            "next_check_ts": next_ts,
            "last_alert_ts": None,
            "needs_voice": False,
        }
        timers[_PROTOCOL_KEY] = state
        _write_all_timers(timers)
    _schedule_1515(next_ts - now, voice)
    _speak(
        voice,
        "Protocolo quince quince iniciado. Toma quince gramos de carbohidratos y revisa tu glucosa en quince minutos.",
    )
    return state


def mark_taken(voice: Optional[object] = None) -> Dict[str, Any]:
    """Marca que se ha ingerido otra ración de 15 g y reinicia la cuenta atrás."""

    now = time.time()
    next_ts = now + _PROTOCOL_SECONDS
    cycles = 1
    with _TIMERS_LOCK:
        timers = _read_all_timers()
        state = _ensure_protocol_state(timers.get(_PROTOCOL_KEY))
        if state.get("active"):
            try:
                cycles = int(state.get("cycles", 0) or 0) + 1
            except Exception:
                cycles = 1
        state.update(
            {
                "active": True,
                "status": "countdown",
                "cycles": cycles,
                "cycle_started_ts": now,
                "next_check_ts": next_ts,
                "last_alert_ts": None,
                "needs_voice": False,
            }
        )
        state.setdefault("started_ts", now)
        timers[_PROTOCOL_KEY] = state
        _write_all_timers(timers)
    _schedule_1515(next_ts - now, voice)
    msg = (
        "Ciclo {n} del protocolo quince quince iniciado. Espera quince minutos y vuelve a revisar tu glucosa.".format(
            n=int(cycles)
        )
    )
    _speak(voice, msg)
    return state


def cancel_1515(voice: Optional[object] = None) -> Dict[str, Any]:
    """Cancela el protocolo 15/15 activo."""

    now = time.time()
    with _TIMERS_LOCK:
        timers = _read_all_timers()
        state = _ensure_protocol_state(timers.get(_PROTOCOL_KEY))
        state.update(
            {
                "active": False,
                "status": "idle",
                "ended_ts": now,
                "needs_voice": False,
            }
        )
        timers[_PROTOCOL_KEY] = state
        _write_all_timers(timers)
    _schedule_1515(0, None)
    _speak(voice, "Protocolo quince quince cancelado.")
    return state


def remaining(voice: Optional[object] = None) -> Dict[str, Any]:
    """Devuelve el estado actual del protocolo 15/15."""

    speak_needed = False
    now = time.time()
    result: Dict[str, Any]
    with _TIMERS_LOCK:
        timers = _read_all_timers()
        state = _ensure_protocol_state(timers.get(_PROTOCOL_KEY))
        if state.get("active"):
            next_ts = float(state.get("next_check_ts", 0.0) or 0.0)
            remaining_sec = max(0, int(round(next_ts - now)))
            status = state.get("status", "countdown")
            if remaining_sec <= 0 and status != "awaiting_recheck":
                state["status"] = "awaiting_recheck"
                state["last_alert_ts"] = now
                state["needs_voice"] = True
                timers[_PROTOCOL_KEY] = state
                _write_all_timers(timers)
                status = "awaiting_recheck"
            result = {
                "active": True,
                "status": status,
                "seconds": remaining_sec,
                "cycles": max(1, int(state.get("cycles", 0) or 1)),
                "started_ts": state.get("started_ts"),
                "cycle_started_ts": state.get("cycle_started_ts"),
                "next_check_ts": state.get("next_check_ts"),
            }
            if status == "awaiting_recheck" and state.get("needs_voice") and voice is not None:
                speak_needed = True
        else:
            result = {
                "active": False,
                "status": "idle",
                "seconds": 0,
                "cycles": int(state.get("cycles", 0) or 0),
                "started_ts": state.get("started_ts"),
                "cycle_started_ts": state.get("cycle_started_ts"),
                "next_check_ts": state.get("next_check_ts"),
            }
    if speak_needed:
        _speak(voice, "Han pasado quince minutos. Revisa tu glucosa.")
        _ack_voice_flag(_PROTOCOL_KEY)
    return result


def start_prebolus(minutes: int, voice: Optional[object] = None) -> Dict[str, Any]:
    """Inicia un recordatorio de pre-bolo."""

    try:
        minutes_int = int(minutes)
    except Exception:
        minutes_int = 0
    if minutes_int <= 0:
        return cancel_prebolus()

    now = time.time()
    expires = now + max(1, minutes_int) * 60
    with _TIMERS_LOCK:
        timers = _read_all_timers()
        state = {
            "active": True,
            "status": "countdown",
            "minutes": minutes_int,
            "started_ts": now,
            "expires_ts": expires,
            "needs_voice": False,
        }
        timers[_PREBOLUS_KEY] = state
        _write_all_timers(timers)
    _schedule_prebolus(expires - now, voice)
    _speak(
        voice,
        f"Pre bolo iniciado. Espera {int(minutes_int)} minutos antes de comer.",
    )
    return state


def cancel_prebolus(voice: Optional[object] = None) -> Dict[str, Any]:
    """Cancela el recordatorio de pre-bolo."""

    now = time.time()
    with _TIMERS_LOCK:
        timers = _read_all_timers()
        state = _ensure_prebolus_state(timers.get(_PREBOLUS_KEY))
        state.update(
            {
                "active": False,
                "status": "idle",
                "ended_ts": now,
                "needs_voice": False,
            }
        )
        timers[_PREBOLUS_KEY] = state
        _write_all_timers(timers)
    _schedule_prebolus(0, None)
    if voice is not None:
        _speak(voice, "Recordatorio de pre bolo cancelado.")
    return state


def prebolus_remaining(voice: Optional[object] = None) -> Dict[str, Any]:
    """Estado del recordatorio de pre-bolo."""

    now = time.time()
    speak_needed = False
    with _TIMERS_LOCK:
        timers = _read_all_timers()
        state = _ensure_prebolus_state(timers.get(_PREBOLUS_KEY))
        if state.get("active"):
            expires = float(state.get("expires_ts", 0.0) or 0.0)
            remaining_sec = max(0, int(round(expires - now)))
            status = state.get("status", "countdown")
            if remaining_sec <= 0 and status != "ready":
                state["status"] = "ready"
                state["last_alert_ts"] = now
                state["needs_voice"] = True
                timers[_PREBOLUS_KEY] = state
                _write_all_timers(timers)
                status = "ready"
            result = {
                "active": True,
                "status": status,
                "seconds": remaining_sec,
                "minutes": int(state.get("minutes", 0) or 0),
                "started_ts": state.get("started_ts"),
                "expires_ts": state.get("expires_ts"),
            }
            if status == "ready" and state.get("needs_voice") and voice is not None:
                speak_needed = True
        else:
            result = {
                "active": False,
                "status": "idle",
                "seconds": 0,
                "minutes": int(state.get("minutes", 0) or 0),
                "started_ts": state.get("started_ts"),
                "expires_ts": state.get("expires_ts"),
            }
    if speak_needed:
        minutes_val = result.get("minutes")
        if minutes_val:
            _speak(voice, f"Ya pasaron los {int(minutes_val)} minutos de pre bolo.")
        else:
            _speak(voice, "Ya puedes aplicar el bolo.")
        _ack_voice_flag(_PREBOLUS_KEY)
    return result


def _bootstrap_timers() -> None:
    """Rearma temporizadores persistidos tras un reinicio."""

    now = time.time()
    try:
        with _TIMERS_LOCK:
            timers = _read_all_timers()
    except Exception:
        return

    protocol_state = _ensure_protocol_state(timers.get(_PROTOCOL_KEY))
    if protocol_state.get("active") and protocol_state.get("status") == "countdown":
        next_ts = float(protocol_state.get("next_check_ts", 0.0) or 0.0)
        seconds = max(0, next_ts - now)
        if seconds > 0:
            _schedule_1515(seconds, None)
        else:
            _complete_1515_cycle()

    prebolus_state = _ensure_prebolus_state(timers.get(_PREBOLUS_KEY))
    if prebolus_state.get("active") and prebolus_state.get("status") == "countdown":
        expires = float(prebolus_state.get("expires_ts", 0.0) or 0.0)
        seconds = max(0, expires - now)
        if seconds > 0:
            _schedule_prebolus(seconds, None)
        else:
            _complete_prebolus_cycle()


try:
    _bootstrap_timers()
except Exception:
    log.debug("No se pudieron rearmar timers persistidos", exc_info=True)
