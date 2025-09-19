"""Optional Piper TTS integration."""
from __future__ import annotations

import logging
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger("bascula.core.tts")


class TextToSpeech:
    def say(self, text: str) -> None:  # pragma: no cover - interface
        raise NotImplementedError


class NullTTS(TextToSpeech):
    def say(self, text: str) -> None:  # pragma: no cover - intentionally empty
        logger.debug("TTS omitido: %s", text)


@dataclass
class PiperConfig:
    binary: Path
    model: Path


class PiperTTS(TextToSpeech):
    def __init__(self, config: PiperConfig) -> None:
        self.config = config

    def say(self, text: str) -> None:
        cmd = [str(self.config.binary), "--model", str(self.config.model), "--output_raw"]
        logger.info("Reproduciendo frase con Piper")
        process = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE)
        assert process.stdin is not None and process.stdout is not None
        try:
            process.stdin.write(text.encode("utf-8"))
            process.stdin.close()
        except Exception:
            logger.warning("No se pudo enviar texto a Piper", exc_info=True)
            process.terminate()
            return
        audio = process.stdout.read()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            logger.warning("Piper tardó demasiado en responder")
            process.kill()
            return
        if not audio:
            logger.warning("Piper no generó audio")
            return
        self._play_audio(audio)

    def _play_audio(self, audio: bytes) -> None:
        aplay = shutil.which("aplay")
        if not aplay:
            logger.warning("aplay no disponible; no se reproducirá audio")
            return
        try:
            subprocess.run([aplay, "-q"], input=audio, check=True)
        except Exception:
            logger.warning("Error reproduciendo audio con aplay", exc_info=True)


def discover_tts() -> TextToSpeech:
    binary = Path("/usr/bin/piper")
    if not binary.exists():
        logger.info("Piper no encontrado; TTS deshabilitado")
        return NullTTS()
    models_dir = Path("/opt/piper/models")
    if not models_dir.exists():
        logger.info("Modelos Piper no disponibles")
        return NullTTS()
    models = sorted(models_dir.glob("*.onnx"))
    if not models:
        logger.info("No se hallaron modelos Piper .onnx")
        return NullTTS()
    config = PiperConfig(binary=binary, model=models[0])
    return PiperTTS(config)


__all__ = ["TextToSpeech", "NullTTS", "PiperTTS", "PiperConfig", "discover_tts"]
