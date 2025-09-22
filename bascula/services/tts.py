"""Lightweight Piper TTS wrapper used by the UI."""
from __future__ import annotations

import logging
import os
import shutil
import subprocess
import tempfile
import threading
import time
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class PiperTTS:
    """Small non-blocking wrapper around the Piper binary."""

    def __init__(self, model: Optional[str] = None, speaker: Optional[str] = None) -> None:
        self._piper_bin = shutil.which(os.getenv("PIPER_BIN", "piper"))
        voice_env = os.getenv("PIPER_MODEL") or os.getenv("PIPER_VOICE")
        self._model_path = model or voice_env or self._default_voice()
        self._speaker = speaker or os.getenv("PIPER_SPEAKER")

        if not self._piper_bin:
            logger.info("Piper no encontrado en PATH; TTS deshabilitado")
        elif not self._model_path:
            logger.info("Modelo de Piper no configurado; establece PIPER_MODEL")

    # ------------------------------------------------------------------
    def speak(self, text: str) -> None:
        self.speak_text(text)

    def speak_text(self, text: str) -> None:
        if not text:
            return
        if not self._piper_bin or not self._model_path:
            logger.debug("TTS omitido: Piper no configurado")
            return

        threading.Thread(target=self._run, args=(text,), daemon=True).start()

    # ------------------------------------------------------------------
    def _run(self, text: str) -> None:
        try:
            with tempfile.NamedTemporaryFile(prefix="piper-", suffix=".wav", delete=False) as tmp:
                wav_path = Path(tmp.name)
            cmd = [self._piper_bin, "--model", self._model_path, "--output_file", str(wav_path)]
            if self._speaker:
                cmd.extend(["--speaker", self._speaker])
            proc = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            try:
                stdin = text.strip().encode("utf-8")
                proc.communicate(stdin, timeout=25)
            except subprocess.TimeoutExpired:
                proc.kill()
                raise RuntimeError("Piper timeout")
            if proc.returncode != 0:
                raise RuntimeError(f"Piper devolvió {proc.returncode}")

            player = shutil.which(os.getenv("PIPER_PLAYER", "aplay")) or shutil.which("paplay")
            if player:
                subprocess.Popen(
                    [player, str(wav_path)],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            else:
                logger.debug("No se encontró reproductor para Piper")
        except Exception as exc:  # pragma: no cover - optional audio chain
            logger.warning("No se pudo reproducir TTS: %s", exc)
        finally:
            try:
                if 'wav_path' in locals() and wav_path.exists():
                    # Pequeña demora para permitir que el reproductor abra el archivo
                    time.sleep(0.2)
                    wav_path.unlink(missing_ok=True)
            except Exception:
                pass

    # ------------------------------------------------------------------
    def _default_voice(self) -> Optional[str]:
        candidates = [
            Path("/usr/share/piper/voices"),
            Path.home() / "piper",
            Path.home() / ".local/share/piper",
        ]
        for base in candidates:
            if not base.exists():
                continue
            for path in base.glob("*.onnx"):
                return str(path)
        return None


__all__ = ["PiperTTS"]
