from __future__ import annotations

import json
import logging
import shlex
import shutil
import subprocess
import threading
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, Optional

try:  # PyYAML forma parte de requirements.txt
    import yaml
except Exception:  # pragma: no cover - PyYAML debería estar disponible, pero evitamos romper ejecución
    yaml = None


log = logging.getLogger(__name__)

_ENV_PATH = Path("/etc/default/bascula")
_DEFAULT_SHARED = Path("/opt/bascula/shared")
_DEFAULT_APP_CFG = _DEFAULT_SHARED / "config" / "app.yaml"
_DEFAULT_VOICE_DIRS = (
    Path("/opt/piper/models"),
    Path("/usr/share/piper/voices"),
    _DEFAULT_SHARED / "voices-v1",
)


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
        p = Path(shared)
        if p.exists():
            return p
    prefix = env.get("BASCULA_PREFIX")
    if prefix:
        root = Path(prefix).parent
        candidate = root / "shared"
        if candidate.exists():
            return candidate
    if _DEFAULT_SHARED.exists():
        return _DEFAULT_SHARED
    return None


def _find_app_config(env: Dict[str, str]) -> Optional[Path]:
    candidates = []
    shared_dir = _guess_shared_dir(env)
    if shared_dir is not None:
        candidates.append(shared_dir / "config" / "app.yaml")
    cfg_dir = env.get("BASCULA_CFG_DIR")
    if cfg_dir:
        candidates.append(Path(cfg_dir) / "app.yaml")
    candidates.append(_DEFAULT_APP_CFG)

    for candidate in candidates:
        try:
            if candidate and candidate.is_file():
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


def _iter_voice_dirs(env: Dict[str, str]) -> Iterable[Path]:
    seen = set()
    for directory in (
        env.get("BASCULA_VOICE_DIR"),
        env.get("BASCULA_SHARED"),
        env.get("BASCULA_CFG_DIR"),
    ):
        if directory:
            for sub in (Path(directory), Path(directory) / "voices-v1"):
                if sub not in seen and sub:
                    seen.add(sub)
                    yield sub
    shared = _guess_shared_dir(env)
    if shared is not None:
        for sub in (shared, shared / "voices-v1", shared / "piper", shared / "piper" / "voices"):
            if sub not in seen:
                seen.add(sub)
                yield sub
    for d in _DEFAULT_VOICE_DIRS:
        if d not in seen:
            seen.add(d)
            yield d


def _search_key(data: Any, key: str) -> Optional[Any]:
    if isinstance(data, dict):
        if key in data:
            return data[key]
        for value in data.values():
            found = _search_key(value, key)
            if found is not None:
                return found
    elif isinstance(data, list):
        for item in data:
            found = _search_key(item, key)
            if found is not None:
                return found
    return None


def _resolve_model_path(hint: Any, directory: Path) -> Optional[Path]:
    if not hint:
        return None
    try:
        hint_str = str(hint).strip()
    except Exception:
        return None
    if not hint_str:
        return None

    candidates = []
    direct = Path(hint_str)
    candidates.append(direct)
    if direct.suffix != ".onnx":
        candidates.append(direct.with_suffix(".onnx"))
    if not direct.is_absolute():
        joined = directory / direct
        candidates.append(joined)
        if joined.suffix != ".onnx":
            candidates.append(joined.with_suffix(".onnx"))

    seen: set[str] = set()
    for candidate in candidates:
        try:
            resolved = candidate.resolve()
        except Exception:
            resolved = candidate
        key = str(resolved)
        if key in seen:
            continue
        seen.add(key)
        if resolved.is_file():
            return resolved
    return None


def _config_for_model(model: Path) -> Optional[Path]:
    candidates = [Path(f"{model}.json")]
    if model.suffix:
        candidates.append(model.with_suffix(".json"))
    for candidate in candidates:
        try:
            if candidate.is_file():
                return candidate
        except Exception:
            continue
    return None


def _read_default_voice_id(directories: Iterable[Path]) -> Optional[str]:
    for directory in directories:
        try:
            marker = directory / ".default-voice"
            if marker.is_file():
                voice = marker.read_text(encoding="utf-8").strip()
                if voice:
                    return voice
        except Exception:
            continue
    return None


def _voice_settings(env: Dict[str, str], cfg: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    directories = list(_iter_voice_dirs(env))
    hints: list[Any] = []

    for key in ("piper_model", "piper_voice", "piper_default_voice"):
        val = _search_key(cfg, key)
        if val:
            hints.append(val)

    default_voice = _read_default_voice_id(directories)
    if default_voice:
        hints.append(default_voice)
    hints.append("es_ES-mls_10246-low")

    model_path: Optional[Path] = None
    config_path: Optional[Path] = None

    for directory in directories:
        for hint in hints:
            model_path = _resolve_model_path(hint, directory)
            if model_path is None:
                continue
            config_path = _config_for_model(model_path)
            if config_path is not None:
                break
        if model_path is not None and config_path is not None:
            break

    if model_path is None or config_path is None:
        return None

    sample_rate = 22050
    try:
        with config_path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
        if isinstance(data, dict):
            if isinstance(data.get("sample_rate"), (int, float)):
                sample_rate = int(data["sample_rate"])
            else:
                audio = data.get("audio")
                if isinstance(audio, dict) and isinstance(audio.get("sample_rate"), (int, float)):
                    sample_rate = int(audio["sample_rate"])
    except Exception as exc:
        log.debug("No se pudo leer sample_rate de %s: %s", config_path, exc)

    return {
        "model": model_path,
        "config": config_path,
        "sample_rate": sample_rate or 22050,
    }


class VoiceService:
    """Wrapper sencillo para ASR/TTS locales.

    - No bloquea la UI: usa hilos cortos por operación.
    - Tolerante a errores: si no existen binarios, cae en no-op.
    """

    def __init__(self, hear_cmd: str = "hear.sh", say_cmd: str = "say.sh") -> None:
        self.hear_cmd = hear_cmd
        self.say_cmd = say_cmd
        self._listen_thread: Optional[threading.Thread] = None
        self._listening = False
        self._aplay = shutil.which("aplay")
        self._piper = shutil.which("piper")
        self._settings_cache: Optional[Dict[str, Any]] = None

    def is_listening(self) -> bool:
        return self._listening and self._listen_thread is not None and self._listen_thread.is_alive()

    def start_listening(self, on_text: Callable[[str], None], *, device: Optional[str] = None, duration: Optional[int] = None, rate: Optional[int] = None) -> bool:
        if self.is_listening():
            return False
        self._listening = True

        def _worker():
            text = ""
            try:
                base = self.hear_cmd if isinstance(self.hear_cmd, list) else shlex.split(self.hear_cmd)
                cmd = list(base)
                if device is not None:
                    cmd.append(str(device))
                if duration is not None:
                    cmd.append(str(int(duration)))
                if rate is not None:
                    cmd.append(str(int(rate)))
                timeout_s = 15
                if duration:
                    try:
                        timeout_s = max(5, int(duration) + 10)
                    except Exception:
                        pass
                proc = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                )
                try:
                    out, _ = proc.communicate(timeout=timeout_s)
                except subprocess.TimeoutExpired:
                    try:
                        proc.kill()
                    except Exception:
                        pass
                    out = ""
                text = (out or "").strip()
            except Exception:
                text = ""
            finally:
                self._listening = False
                try:
                    on_text(text)
                except Exception:
                    pass

        self._listen_thread = threading.Thread(target=_worker, daemon=True)
        self._listen_thread.start()
        return True

    def _load_settings(self) -> Optional[Dict[str, Any]]:
        env = _read_env_file(_ENV_PATH)
        cfg_path = _find_app_config(env)
        cfg = _load_yaml_config(cfg_path)
        settings = _voice_settings(env, cfg)
        if settings is None:
            log.debug("No se encontraron archivos de voz Piper")
        return settings

    def _speak_with_piper(self, text: str) -> None:
        if not text:
            return
        if not self._piper:
            self._piper = shutil.which("piper")
        if not self._aplay:
            self._aplay = shutil.which("aplay")
        if not self._piper or not self._aplay:
            log.debug("piper/aplay no disponibles")
            return

        settings = self._settings_cache
        if settings is None:
            settings = self._load_settings()
            self._settings_cache = settings
        if not settings:
            log.debug("Configuración Piper no disponible")
            return

        model_path = settings["model"]
        config_path = settings["config"]
        sample_rate = int(settings.get("sample_rate", 22050))

        timeout_s = 8
        piper_cmd = [
            self._piper,
            "--model",
            str(model_path),
            "--config",
            str(config_path),
            "--output_raw",
        ]
        aplay_cmd = [
            self._aplay,
            "-q",
            "-f",
            "S16_LE",
            "-t",
            "raw",
            "-c",
            "1",
            "-r",
            str(max(sample_rate, 8000)),
        ]

        try:
            piper_proc = subprocess.Popen(
                piper_cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
        except Exception as exc:
            log.debug("No se pudo iniciar piper: %s", exc)
            return

        try:
            aplay_proc = subprocess.Popen(
                aplay_cmd,
                stdin=piper_proc.stdout,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception as exc:
            log.debug("No se pudo iniciar aplay: %s", exc)
            try:
                piper_proc.kill()
            except Exception:
                pass
            return

        assert piper_proc.stdout is not None
        piper_proc.stdout.close()

        try:
            stdin = piper_proc.stdin
            if stdin is not None:
                stdin.write(text.encode("utf-8"))
                stdin.close()
            piper_proc.wait(timeout=timeout_s)
        except subprocess.TimeoutExpired:
            log.warning("piper tardó más de %ss; abortando", timeout_s)
            for proc in (piper_proc, aplay_proc):
                try:
                    proc.kill()
                except Exception:
                    pass
        except Exception as exc:
            log.debug("Error ejecutando piper/aplay: %s", exc)
            for proc in (piper_proc, aplay_proc):
                try:
                    proc.kill()
                except Exception:
                    pass
        finally:
            try:
                piper_proc.stderr and piper_proc.stderr.close()
            except Exception:
                pass
            try:
                aplay_proc.wait(timeout=1)
            except Exception:
                try:
                    aplay_proc.kill()
                except Exception:
                    pass

    def speak(self, text: str) -> None:
        def _worker():
            try:
                self._speak_with_piper(text)
            except Exception as exc:
                log.debug("speak fallback silencioso: %s", exc)

        threading.Thread(target=_worker, daemon=True).start()
