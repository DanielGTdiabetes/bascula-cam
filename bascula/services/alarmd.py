"""Servicio de alarmas CGM para Bascula.

Este módulo consulta un endpoint Nightscout de manera periódica y genera
alarmas (incluyendo snooze) que pueden ser consumidas por la interfaz de
usuario. El resultado de cada iteración se persiste en dos ubicaciones:

* ``/run/bascula/events/alarm.json`` – evento visible para la UI.
* ``/opt/bascula/shared/userdata/alarms_state.json`` – estado de snooze.

Las rutas anteriores se pueden sobreescribir mediante variables de entorno
para facilitar pruebas locales sin hardware.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import random
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

import requests

try:  # PyYAML forma parte de requirements.txt
    import yaml
except Exception:  # pragma: no cover - degradamos silenciosamente
    yaml = None  # type: ignore[assignment]

try:  # El servicio de voz es opcional en entornos de prueba
    from bascula.services.voice import VoiceService
except Exception:  # pragma: no cover - la voz no es imprescindible
    VoiceService = None  # type: ignore[assignment]


log = logging.getLogger(__name__)

_ENV_PATH = Path("/etc/default/bascula")
_DEFAULT_SHARED = Path("/opt/bascula/shared")


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
    except Exception as exc:  # pragma: no cover - sólo para diagnósticos
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


def _find_app_config(env: Dict[str, str]) -> Optional[Path]:
    candidates = []

    cfg_override = env.get("BASCULA_ALARMD_CONFIG")
    if cfg_override:
        candidates.append(Path(cfg_override))

    cfg_dir = env.get("BASCULA_CFG_DIR")
    if cfg_dir:
        candidates.append(Path(cfg_dir) / "app.yaml")

    shared_dir = _guess_shared_dir(env)
    if shared_dir is not None:
        candidates.append(shared_dir / "config" / "app.yaml")

    candidates.append(_DEFAULT_SHARED / "config" / "app.yaml")

    for candidate in candidates:
        try:
            if candidate.is_file():
                return candidate
        except Exception:
            continue
    return None


def _load_yaml_config(path: Optional[Path]) -> Dict[str, Any]:
    if path is None or yaml is None:
        return {}
    try:
        with path.open("r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}
        if isinstance(data, dict):
            return data
    except Exception as exc:
        log.debug("No se pudo parsear %s: %s", path, exc)
    return {}


def _nested_get(data: Dict[str, Any], *keys: str, default: Any = None) -> Any:
    current: Any = data
    for key in keys:
        if not isinstance(current, dict) or key not in current:
            return default
        current = current[key]
    return current


@dataclass
class AlarmConfig:
    hypo: float = 70.0
    hyper: float = 180.0
    snooze_minutes: float = 15.0

    @classmethod
    def from_sources(cls, env: Dict[str, str]) -> "AlarmConfig":
        cfg_path = _find_app_config(env)
        cfg_data = _load_yaml_config(cfg_path)

        def _float(value: Any, fallback: float) -> float:
            try:
                return float(value)
            except Exception:
                return fallback

        def _minutes(value: Any, fallback: float) -> float:
            try:
                minutes = float(value)
                if minutes < 0:
                    return fallback
                return minutes
            except Exception:
                return fallback

        hypo = _float(_nested_get(cfg_data, "alarms", "hypo", default=None), cls.hypo)
        hyper = _float(_nested_get(cfg_data, "alarms", "hyper", default=None), cls.hyper)
        snooze = _minutes(
            _nested_get(cfg_data, "alarms", "snooze_minutes", default=None),
            cls.snooze_minutes,
        )

        return cls(hypo=hypo, hyper=hyper, snooze_minutes=snooze)


@dataclass
class SnoozeState:
    path: Path
    snooze_until: Optional[float] = None

    @classmethod
    def load(cls, path: Path) -> "SnoozeState":
        snooze_until: Optional[float] = None
        try:
            with path.open("r", encoding="utf-8") as fh:
                data = json.load(fh)
            raw = data.get("snooze_until")
            if raw is not None:
                snooze_until = float(raw)
        except FileNotFoundError:
            snooze_until = None
        except Exception as exc:  # pragma: no cover - sólo logging
            log.debug("No se pudo leer estado de alarma %s: %s", path, exc)
        return cls(path=path, snooze_until=snooze_until)

    def save(self) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp_path = self.path.with_suffix(".tmp")
            payload = {"snooze_until": self.snooze_until}
            with tmp_path.open("w", encoding="utf-8") as fh:
                json.dump(payload, fh, ensure_ascii=False)
            tmp_path.replace(self.path)
        except Exception as exc:  # pragma: no cover - evitar caída
            log.debug("No se pudo persistir estado de alarma %s: %s", self.path, exc)

    def clear_if_expired(self, now: float) -> bool:
        if self.snooze_until is not None and now >= self.snooze_until:
            self.snooze_until = None
            self.save()
            return True
        return False

    def activate(self, until: float) -> None:
        if self.snooze_until is None or self.snooze_until < until:
            self.snooze_until = until
            self.save()

    def is_active(self, now: float) -> bool:
        return self.snooze_until is not None and now < self.snooze_until


def _runtime_event_path(env: Dict[str, str]) -> Path:
    runtime_dir = env.get("BASCULA_RUNTIME_DIR")
    if runtime_dir:
        return Path(runtime_dir) / "events" / "alarm.json"
    return Path("/run/bascula/events/alarm.json")


def _snooze_state_path(env: Dict[str, str]) -> Path:
    override = env.get("BASCULA_ALARMD_STATE")
    if override:
        return Path(override)

    shared_dir = _guess_shared_dir(env)
    if shared_dir is not None:
        return shared_dir / "userdata" / "alarms_state.json"

    return _DEFAULT_SHARED / "userdata" / "alarms_state.json"


def _nightscout_from_env(env: Dict[str, str]) -> tuple[Optional[str], Optional[str]]:
    url = env.get("BASCULA_NIGHTSCOUT_URL") or env.get("NIGHTSCOUT_URL")
    token = env.get("BASCULA_NIGHTSCOUT_TOKEN") or env.get("NIGHTSCOUT_TOKEN")
    if not url:
        url = os.environ.get("BASCULA_NIGHTSCOUT_URL") or os.environ.get("NIGHTSCOUT_URL")
    if not token:
        token = os.environ.get("BASCULA_NIGHTSCOUT_TOKEN") or os.environ.get("NIGHTSCOUT_TOKEN")
    if not url:
        url = os.environ.get("BASCULA_ALARMD_URL")
    return url, token


def _normalize_base_url(url: str) -> str:
    return url.rstrip("/")


def _fetch_latest_glucose(session: requests.Session, base_url: str, token: Optional[str]) -> Optional[float]:
    url = _normalize_base_url(base_url) + "/api/v1/entries.json"
    headers = {"Accept": "application/json"}
    params = {"count": 1}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        response = session.get(url, headers=headers, params=params, timeout=15)
        response.raise_for_status()
        payload = response.json()
    except Exception as exc:
        log.warning("No se pudo consultar Nightscout: %s", exc)
        return None

    try:
        if isinstance(payload, list) and payload:
            entry = payload[0]
        elif isinstance(payload, dict) and "sgv" in payload:
            entry = payload
        else:
            log.warning("Respuesta inesperada de Nightscout: %s", payload)
            return None
        value = entry.get("sgv") or entry.get("glucose")
        if value is None:
            log.warning("Entrada Nightscout sin SGV: %s", entry)
            return None
        return float(value)
    except Exception as exc:
        log.warning("No se pudo interpretar el SGV de Nightscout: %s", exc)
        return None


def _evaluate_state(value: Optional[float], config: AlarmConfig) -> str:
    if value is None:
        return "UNKNOWN"
    if value <= config.hypo:
        return "HYPO"
    if value >= config.hyper:
        return "HYPER"
    return "OK"


def _speak_alarm(voice: Optional[VoiceService], status: str, value: Optional[float]) -> None:  # type: ignore[type-arg]
    if voice is None:
        return
    try:
        if status == "HYPO":
            if value is not None:
                voice.speak(f"Atención. Glucosa baja: {int(value)} miligramos por decilitro")
            else:
                voice.speak("Atención. Glucosa baja")
        elif status == "HYPER":
            if value is not None:
                voice.speak(f"Aviso. Glucosa alta: {int(value)} miligramos por decilitro")
            else:
                voice.speak("Aviso. Glucosa alta")
    except Exception as exc:  # pragma: no cover - evitamos fallar por voz
        log.debug("Fallo al reproducir voz: %s", exc)


def _write_event(path: Path, payload: Dict[str, Any]) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = path.with_suffix(".tmp")
        with tmp_path.open("w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False)
        tmp_path.replace(path)
    except Exception as exc:
        log.debug("No se pudo escribir evento de alarma %s: %s", path, exc)


def _load_environment() -> Dict[str, str]:
    env = _read_env_file(_ENV_PATH)
    env.update(os.environ)
    return env


def _setup_voice() -> Optional[VoiceService]:  # type: ignore[type-arg]
    if VoiceService is None:
        return None
    try:
        return VoiceService()
    except Exception as exc:  # pragma: no cover - voz opcional
        log.debug("No se pudo inicializar VoiceService: %s", exc)
        return None


def _loop_once(
    *,
    session: requests.Session,
    config: AlarmConfig,
    state: SnoozeState,
    voice: Optional[VoiceService],  # type: ignore[type-arg]
    event_path: Path,
    base_url: Optional[str],
    token: Optional[str],
) -> None:
    now = time.time()
    if base_url:
        value = _fetch_latest_glucose(session, base_url, token)
    else:
        log.debug("Nightscout no configurado")
        value = None

    status = _evaluate_state(value, config)

    if status in {"HYPO", "HYPER"}:
        if state.is_active(now):
            log.debug("Alarma %s en snooze hasta %s", status, state.snooze_until)
            speak = False
            snoozed = True
        else:
            speak = True
            snoozed = False
            if config.snooze_minutes > 0:
                until = now + config.snooze_minutes * 60
                state.activate(until)
        if speak:
            _speak_alarm(voice, status, value)
    else:
        snoozed = False
        state_cleared = state.clear_if_expired(now)
        if state_cleared:
            log.debug("El snooze expiró; limpiando estado")

    payload = {
        "timestamp": int(now),
        "status": status,
        "value": value,
        "snoozed": snoozed,
        "snooze_until": state.snooze_until,
        "config": {
            "hypo": config.hypo,
            "hyper": config.hyper,
            "snooze_minutes": config.snooze_minutes,
        },
    }

    _write_event(event_path, payload)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Servicio de alarmas CGM")
    parser.add_argument("--min-interval", type=float, default=60.0, help="Intervalo mínimo en segundos")
    parser.add_argument("--max-interval", type=float, default=120.0, help="Intervalo máximo en segundos")
    parser.add_argument("--once", action="store_true", help="Ejecuta una sola iteración y termina")
    parser.add_argument("--verbose", action="store_true", help="Activa logging DEBUG en consola")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()

    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO)

    if args.min_interval <= 0 or args.max_interval <= 0:
        raise SystemExit("Los intervalos deben ser positivos")
    if args.min_interval > args.max_interval:
        raise SystemExit("Intervalo mínimo no puede ser mayor que el máximo")

    env = _load_environment()
    log.info(
        "alarmd env: SHARED=%s, RUNTIME_DIR=%s, NS_URL=%s",
        env.get("BASCULA_SHARED"),
        env.get("BASCULA_RUNTIME_DIR"),
        env.get("BASCULA_NIGHTSCOUT_URL"),
    )
    config = AlarmConfig.from_sources(env)
    event_path = _runtime_event_path(env)
    snooze_path = _snooze_state_path(env)
    state = SnoozeState.load(snooze_path)
    voice = _setup_voice()

    base_url, token = _nightscout_from_env(env)
    if not base_url:
        log.warning("Nightscout no configurado; esperando configuración")

    session = requests.Session()

    try:
        while True:
            _loop_once(
                session=session,
                config=config,
                state=state,
                voice=voice,
                event_path=event_path,
                base_url=base_url,
                token=token,
            )

            if args.once:
                break

            sleep_time = random.uniform(args.min_interval, args.max_interval)
            time.sleep(sleep_time)
    except KeyboardInterrupt:  # pragma: no cover - control de servicio manual
        log.info("Interrumpido por el usuario")
    finally:
        session.close()


if __name__ == "__main__":
    main()

