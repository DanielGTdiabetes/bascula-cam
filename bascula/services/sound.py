"""Lightweight sound helpers for UI beeps and speech."""
from __future__ import annotations

import logging
import math
import os
import subprocess
import sys
import tempfile
import wave
from array import array
from functools import lru_cache
from pathlib import Path
from shutil import which
from typing import Iterable, Optional

log = logging.getLogger(__name__)

_PIPER_CANDIDATES: tuple[str | None, ...] = (
    os.environ.get("BASCULA_PIPER"),
    "piper",
)

_MODEL_CANDIDATES: tuple[str | None, ...] = (
    os.environ.get("BASCULA_PIPER_MODEL"),
    "/opt/piper/models/es-ES-mls_medium.onnx",
    "/opt/piper/models/es_ES-sharvard-medium.onnx",
    "/usr/share/piper/voices/es-ES-mls_medium.onnx",
)

_PLAYER_CANDIDATES: tuple[str, ...] = ("aplay", "paplay", "play")


def play_beep(frequency: int = 880, duration_ms: int = 320) -> None:
    """Play a short tone, best-effort."""

    try:
        _play_beep_sync(frequency, duration_ms)
    except Exception:  # pragma: no cover - defensive logging only
        log.debug("No se pudo reproducir beep", exc_info=True)


def speak(text: str, *, language: str = "es") -> None:
    """Speak ``text`` using Piper if available."""

    clean = (text or "").strip()
    if not clean:
        return

    try:
        _speak_sync(clean, language=language)
    except Exception:  # pragma: no cover - defensive logging only
        log.debug("No se pudo reproducir voz", exc_info=True)


def _play_beep_sync(frequency: int, duration_ms: int) -> None:
    if sys.platform.startswith("win"):
        try:
            import winsound

            winsound.Beep(int(frequency), int(duration_ms))
            return
        except Exception:
            log.debug("winsound.Beep no disponible", exc_info=True)

    player = _detect_player()
    if player:
        wav_path = _generate_tone(int(frequency), int(duration_ms))
        try:
            subprocess.run(_player_command(player, wav_path), check=True)
        except Exception:
            log.debug("Fallo reproduciendo beep con %s", player, exc_info=True)
        finally:
            try:
                wav_path.unlink()
            except Exception:
                pass
        return

    # Fallback: terminal bell
    try:
        sys.stdout.write("\a")
        sys.stdout.flush()
    except Exception:
        pass


def _speak_sync(text: str, *, language: str) -> None:
    piper = _detect_piper()
    if not piper:
        return

    model = _detect_voice_model()
    if not model:
        log.debug("Modelo Piper no encontrado; omitiendo voz")
        return

    player = _detect_player()
    with tempfile.NamedTemporaryFile(prefix="piper-", suffix=".wav", delete=False) as handle:
        output = Path(handle.name)
    try:
        subprocess.run(
            [piper, "--model", model, "--output_file", str(output)],
            input=text.encode("utf-8"),
            check=True,
        )
        if player:
            subprocess.run(_player_command(player, output), check=True)
    except Exception:
        log.debug("Fallo reproduciendo voz", exc_info=True)
    finally:
        try:
            output.unlink()
        except Exception:
            pass


@lru_cache(maxsize=1)
def _detect_player() -> Optional[str]:
    for candidate in _PLAYER_CANDIDATES:
        path = which(candidate)
        if path:
            return path
    return None


def _player_command(player: str, wav_path: Path) -> Iterable[str]:
    binary = Path(player).name.lower()
    if binary == "aplay":
        return (player, "-q", str(wav_path))
    if binary == "paplay":
        return (player, str(wav_path))
    if binary == "play":
        return (player, "-q", str(wav_path))
    return (player, str(wav_path))


def _generate_tone(frequency: int, duration_ms: int) -> Path:
    duration = max(1, int(duration_ms)) / 1000.0
    sample_rate = 44100
    total_samples = int(sample_rate * duration)
    data = array("h")
    amplitude = 32767
    for index in range(total_samples):
        angle = 2.0 * math.pi * frequency * (index / sample_rate)
        data.append(int(amplitude * math.sin(angle)))
    with tempfile.NamedTemporaryFile(prefix="beep-", suffix=".wav", delete=False) as handle:
        path = Path(handle.name)
    with wave.open(str(path), "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(data.tobytes())
    return path


@lru_cache(maxsize=1)
def _detect_piper() -> Optional[str]:
    for candidate in _PIPER_CANDIDATES:
        if not candidate:
            continue
        path = which(candidate) if os.path.basename(candidate) == candidate else candidate
        if path and (Path(path).exists() or which(path)):
            resolved = str(path if Path(path).exists() else which(path))
            return resolved
    return None


@lru_cache(maxsize=1)
def _detect_voice_model() -> Optional[str]:
    for candidate in _MODEL_CANDIDATES:
        if not candidate:
            continue
        path = Path(candidate)
        if path.exists():
            return str(path)
    return None


def can_beep() -> bool:
    if sys.platform.startswith("win"):
        return True
    return _detect_player() is not None


def can_speak() -> bool:
    return bool(_detect_piper() and _detect_voice_model())


__all__ = ["play_beep", "speak", "can_beep", "can_speak"]
