from __future__ import annotations

"""Voice synthesis helpers backed by Piper."""

import json
import logging
import os
import shutil
import subprocess
import threading
from pathlib import Path
from typing import Optional

_LOGGER = logging.getLogger("bascula.voice")


def _find_binary(candidates: list[str | None]) -> Optional[str]:
    for item in candidates:
        if not item:
            continue
        path = shutil.which(item)
        if path:
            return path
        candidate = Path(item)
        if candidate.exists() and candidate.is_file():
            return str(candidate)
    return None


class VoiceService:
    """Minimal Piper wrapper used for spoken prompts."""

    def __init__(
        self,
        *,
        model_path: Optional[str] = None,
        binary: Optional[str] = None,
        sample_rate: int = 22050,
    ) -> None:
        self.sample_rate = int(sample_rate)
        bin_candidates = [
            binary,
            os.getenv("BASCULA_PIPER_BIN"),
            "piper",
            "/usr/bin/piper",
            "/usr/local/bin/piper",
        ]
        self.binary = _find_binary(bin_candidates)
        self.model_path = model_path or os.getenv(
            "BASCULA_PIPER_MODEL", "/opt/piper/models/es_ES-sharvard-medium.onnx"
        )
        if self.binary is None:
            _LOGGER.warning("Piper no disponible en PATH; voz deshabilitada")
        if not self._model_available():
            _LOGGER.warning("Modelo Piper no encontrado en %s", self.model_path)

    # ------------------------------------------------------------------ helpers
    def _model_available(self) -> bool:
        if not self.model_path:
            return False
        try:
            return Path(self.model_path).exists()
        except Exception:
            return False

    def _can_speak(self) -> bool:
        return bool(self.binary and self._model_available())

    # ------------------------------------------------------------------ public API
    def say(self, text: str) -> None:
        """Speak *text* asynchronously using Piper + aplay."""

        message = (text or "").strip()
        if not message or not self._can_speak():
            return

        device = os.getenv("BASCULA_APLAY_DEVICE", "").strip()
        binary = self.binary
        model = self.model_path
        sample_rate = self.sample_rate

        def _worker() -> None:
            cmd = [binary, "--model", model, "--output-raw"]
            voice_proc = None
            player_proc = None
            try:
                voice_proc = subprocess.Popen(
                    cmd,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL,
                )
                if voice_proc.stdin is None or voice_proc.stdout is None:
                    raise RuntimeError("Canal Piper inválido")
                play_cmd = [
                    "aplay",
                    "-q",
                    "-f",
                    "S16_LE",
                    "-r",
                    str(sample_rate),
                ]
                if device:
                    play_cmd.extend(["-D", device])
                player_proc = subprocess.Popen(
                    play_cmd,
                    stdin=voice_proc.stdout,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                voice_proc.stdout.close()
                payload = json.dumps({"text": message}) + "\n"
                voice_proc.stdin.write(payload.encode("utf-8"))
                voice_proc.stdin.close()
                voice_proc.wait(timeout=30)
                if player_proc is not None:
                    player_proc.wait(timeout=30)
            except Exception:
                _LOGGER.debug("Fallo reproduciendo voz", exc_info=True)
            finally:
                for proc in (player_proc, voice_proc):
                    if proc and proc.poll() is None:
                        try:
                            proc.terminate()
                        except Exception:
                            pass

        threading.Thread(target=_worker, daemon=True).start()

    # Backwards compatibility -------------------------------------------------
    def speak(self, text: str) -> None:  # pragma: no cover - legacy alias
        self.say(text)
