"""Audio helpers for MAX98357A driven output."""
from __future__ import annotations

import logging
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)


@dataclass
class AudioBackend:
    """Keep track of playback utilities available on the system."""

    aplay: Optional[str]
    piper: Optional[str]
    voice_model: Optional[str]


class AudioService:
    """Tiny facade around ALSA aplay and Piper TTS."""

    def __init__(
        self,
        *,
        audio_device: str = "default",
        volume: int = 70,
        voice_model: str | None = None,
        tts_enabled: bool = True,
    ) -> None:
        self.audio_device = audio_device
        self.volume = max(0, min(100, int(volume)))
        self.enabled = True
        self.tts_enabled = bool(tts_enabled)
        detected_voice = voice_model or _detect_piper_model()
        if detected_voice and not Path(str(detected_voice)).exists():
            detected_voice = None
        self.backend = AudioBackend(
            aplay=_which("aplay"),
            piper=_which("piper"),
            voice_model=detected_voice,
        )
        log.info(
            "Audio service ready (device=%s, volume=%s, piper=%s)",
            self.audio_device,
            self.volume,
            "yes" if self.backend.piper else "no",
        )

    # ------------------------------------------------------------------
    def set_volume(self, value: int) -> None:
        self.volume = max(0, min(100, int(value)))
        log.info("Audio volume set to %s", self.volume)

    def set_enabled(self, enabled: bool) -> None:
        self.enabled = bool(enabled)

    def set_tts_enabled(self, enabled: bool) -> None:
        self.tts_enabled = bool(enabled)

    def set_voice_model(self, model_path: str | None) -> bool:
        if not self.backend.piper:
            return False
        if model_path:
            candidate = Path(str(model_path))
            if not candidate.exists():
                return False
            self.backend.voice_model = str(candidate)
        else:
            self.backend.voice_model = _detect_piper_model()
        log.info("Piper voice set to %s", self.backend.voice_model)
        return True

    # ------------------------------------------------------------------
    def beep_ok(self) -> None:
        self._beep(880, 120)

    def beep_alarm(self) -> None:
        self._beep(440, 750)

    def speak(self, text: str) -> None:
        if not self.enabled or not self.tts_enabled:
            log.debug("Skipping speech while audio disabled")
            return
        text = text.strip()
        if not text:
            return
        if self.backend.piper and self.backend.voice_model:
            self._speak_with_piper(text)
        else:
            log.info("TTS unavailable, logging phrase: %s", text)

    # ------------------------------------------------------------------
    def _beep(self, frequency: int, duration_ms: int) -> None:
        if not self.enabled:
            return
        if not self.backend.aplay:
            log.info("aplay missing, simulated beep %sHz/%sms", frequency, duration_ms)
            return
        wav_path = _generate_tone(frequency, duration_ms)
        cmd = [self.backend.aplay, "-q", "-D", self.audio_device, str(wav_path)]
        try:
            subprocess.run(cmd, check=True)
        except Exception as exc:  # pragma: no cover - depends on ALSA
            log.warning("Unable to play tone: %s", exc)
        finally:
            try:
                wav_path.unlink()
            except Exception:  # pragma: no cover - cleanup best effort
                pass

    def _speak_with_piper(self, text: str) -> None:
        assert self.backend.piper and self.backend.voice_model  # for typing
        out_file = Path(os.environ.get("BASCULA_TTS_TMP", "/tmp")) / "piper-output.wav"
        cmd = [
            self.backend.piper,
            "--model",
            self.backend.voice_model,
            "--output_file",
            str(out_file),
        ]
        try:
            subprocess.run(cmd, input=text.encode("utf-8"), check=True)
            if self.backend.aplay:
                subprocess.run([
                    self.backend.aplay,
                    "-q",
                    "-D",
                    self.audio_device,
                    str(out_file),
                ], check=True)
        except Exception as exc:  # pragma: no cover - depends on binaries
            log.warning("Piper playback failed: %s", exc)
        finally:
            if out_file.exists():
                try:
                    out_file.unlink()
                except Exception:  # pragma: no cover
                    pass


def _which(cmd: str) -> Optional[str]:
    from shutil import which

    return which(cmd)


def _generate_tone(frequency: int, duration_ms: int) -> Path:
    import math
    import wave
    from array import array

    sample_rate = 44100
    samples = int(sample_rate * (duration_ms / 1000.0))
    data = array("h")
    amplitude = 32767
    for i in range(samples):
        angle = 2.0 * math.pi * frequency * (i / sample_rate)
        data.append(int(amplitude * math.sin(angle)))
    tmp = Path(os.environ.get("BASCULA_AUDIO_TMP", "/tmp")) / f"tone-{frequency}-{duration_ms}.wav"
    with wave.open(str(tmp), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(data.tobytes())
    return tmp


def _detect_piper_model() -> Optional[str]:
    candidates = [
        os.environ.get("BASCULA_PIPER_MODEL"),
        "/opt/piper/models/es-ES-mls_medium.onnx",
        "/usr/share/piper/voices/es-ES-mls_medium.onnx",
    ]
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return candidate
    return None


__all__ = ["AudioService"]
