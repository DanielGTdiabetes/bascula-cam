
import os
import math
import struct
import shutil
import tempfile
import subprocess
import threading
from typing import Optional

class Audio:
    """
    Servicio de audio con:
      - Piper TTS (opcional): híbrido (solo frases largas) + precalentamiento
      - eSpeak-ng TTS (fallback, voz 'es')
      - Beep por PCM -> aplay
    Configuración (cfg o variables de entorno):
      - aplay_device (str), aplay_rate (int, Hz)
      - voice_speed (int), voice_pitch (int), voice_gap (int), voice_ampl (0-200)
      - piper_enabled (bool), piper_model (ruta .onnx), piper_len, piper_noise, piper_noisew
      - piper_hybrid (bool), piper_prewarm (bool)
    """

    def __init__(self, cfg: Optional[dict] = None):
        cfg = cfg or {}
        # Dispositivo de audio para aplay
        self._aplay_device = None
        try:
            dev = str(cfg.get("aplay_device") or "").strip()
            if dev.startswith("hw:"):
                dev = "plughw" + dev[2:]
            self._aplay_device = dev or None
        except Exception:
            self._aplay_device = None

        # Frecuencia de muestreo para aplay/beep
        try:
            self._aplay_rate = int(os.environ.get("BASCULA_APLAY_RATE", cfg.get("aplay_rate", 48000)))
        except Exception:
            self._aplay_rate = 48000

        # Prosodia eSpeak
        def _i(env, key, default):
            try:
                return int(os.environ.get(env, cfg.get(key, default)))
            except Exception:
                return default
        self._voice_speed = _i("BASCULA_VOICE_SPEED", "voice_speed", 165)
        self._voice_pitch = _i("BASCULA_VOICE_PITCH", "voice_pitch", 55)
        self._voice_gap   = _i("BASCULA_VOICE_GAP",   "voice_gap",   8)
        self._voice_ampl  = _i("BASCULA_VOICE_AMPL",  "voice_ampl",  120)

        # Rutas binarios
        self._espeak = shutil.which("espeak-ng") or shutil.which("espeak")

        # Piper (opcional)
        self._piper_enabled = bool(cfg.get("piper_enabled", True))
        self._piper_model   = os.environ.get("BASCULA_PIPER_MODEL") or os.environ.get("PIPER_MODEL") or cfg.get("piper_model")
        try:
            self._piper_len   = float(os.environ.get("BASCULA_PIPER_LEN",   cfg.get("piper_len",   1.05)))
        except Exception:
            self._piper_len = 1.05
        try:
            self._piper_noise = float(os.environ.get("BASCULA_PIPER_NOISE", cfg.get("piper_noise", 0.667)))
        except Exception:
            self._piper_noise = 0.667
        try:
            self._piper_noisew = float(os.environ.get("BASCULA_PIPER_NOISEW", cfg.get("piper_noisew", 0.8)))
        except Exception:
            self._piper_noisew = 0.8
        self._piper_hybrid = bool(cfg.get("piper_hybrid", True))
        self._piper_prewarm = bool(cfg.get("piper_prewarm", True))

        self._prewarm_started = False
        if self._piper_prewarm:
            try:
                threading.Thread(target=self._prewarm_piper, daemon=True).start()
                self._prewarm_started = True
            except Exception:
                self._prewarm_started = True

    # --- API pública ------------------------------------------------------
    def update_config(self, cfg: dict):
        if not isinstance(cfg, dict):
            return
        # aplay device
        try:
            dev = str(cfg.get("aplay_device") or "").strip()
            if dev.startswith("hw:"):
                dev = "plughw" + dev[2:]
            self._aplay_device = dev or None
        except Exception:
            pass
        # aplay rate
        try:
            self._aplay_rate = int(os.environ.get("BASCULA_APLAY_RATE", cfg.get("aplay_rate", self._aplay_rate)))
        except Exception:
            pass
        # prosodia
        for env, key, attr, default in [
            ("BASCULA_VOICE_SPEED","voice_speed","_voice_speed", self._voice_speed),
            ("BASCULA_VOICE_PITCH","voice_pitch","_voice_pitch", self._voice_pitch),
            ("BASCULA_VOICE_GAP","voice_gap","_voice_gap", self._voice_gap),
            ("BASCULA_VOICE_AMPL","voice_ampl","_voice_ampl", self._voice_ampl),
        ]:
            try:
                setattr(self, attr, int(os.environ.get(env, cfg.get(key, default))))
            except Exception:
                pass
        # Piper
        self._piper_enabled = bool(cfg.get("piper_enabled", self._piper_enabled))
        self._piper_model = os.environ.get("BASCULA_PIPER_MODEL") or os.environ.get("PIPER_MODEL") or cfg.get("piper_model") or self._piper_model
        try:
            self._piper_len = float(os.environ.get("BASCULA_PIPER_LEN", cfg.get("piper_len", self._piper_len)))
        except Exception:
            pass
        try:
            self._piper_noise = float(os.environ.get("BASCULA_PIPER_NOISE", cfg.get("piper_noise", self._piper_noise)))
        except Exception:
            pass
        try:
            self._piper_noisew = float(os.environ.get("BASCULA_PIPER_NOISEW", cfg.get("piper_noisew", self._piper_noisew)))
        except Exception:
            pass
        self._piper_hybrid = bool(cfg.get("piper_hybrid", self._piper_hybrid))
        self._piper_prewarm = bool(cfg.get("piper_prewarm", self._piper_prewarm))
        if self._piper_prewarm and not self._prewarm_started:
            try:
                threading.Thread(target=self._prewarm_piper, daemon=True).start()
                self._prewarm_started = True
            except Exception:
                self._prewarm_started = True

    def tts_diag(self):
        info = {
            "espeak": bool(self._espeak),
            "aplay_device": self._aplay_device,
            "aplay_rate": self._aplay_rate,
            "piper_enabled": self._piper_enabled,
            "piper_model": self._piper_model,
            "piper_hybrid": self._piper_hybrid,
        }
        return info

    def speak(self, text: str):
        self._speak(text)

    def speak_event(self, text: str):
        self._speak(text)

    def beep(self, ms: int = 250, freq: int = 1200):
        self._beep(ms=ms, freq=freq)

    # --- Internos ---------------------------------------------------------
    def _prewarm_piper(self):
        try:
            piper_bin = shutil.which("piper")
            model = self._piper_model or os.environ.get("BASCULA_PIPER_MODEL") or os.environ.get("PIPER_MODEL")
            if not (self._piper_enabled and piper_bin and model and os.path.exists(model)):
                return
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=True) as f:
                subprocess.run([piper_bin, "-m", model, "-f", f.name,
                                "--length_scale", str(self._piper_len),
                                "--noise_scale", str(self._piper_noise),
                                "--noise_w", str(self._piper_noisew)],
                               input=b" ", check=False)
        except Exception:
            pass

    def _speak(self, text: str):
        """Híbrido: Piper para frases largas; eSpeak-ng para cortas; fallbacks robustos."""
        # ¿Texto largo?
        t = (text or "").strip()
        is_long = (len(t) >= 60) or (t.count(",") + t.count(" ") >= 12)

        # --- Piper (opcional) ---
        if self._piper_enabled and ( (self._piper_hybrid and is_long) or (not self._piper_hybrid) ):
            try:
                piper_bin = shutil.which("piper")
                model = self._piper_model or os.environ.get("BASCULA_PIPER_MODEL") or os.environ.get("PIPER_MODEL")
                if piper_bin and model and os.path.exists(model):
                    with tempfile.NamedTemporaryFile(suffix=".wav", delete=True) as f:
                        cmd = [piper_bin, "-m", model, "-f", f.name,
                               "--length_scale", str(self._piper_len),
                               "--noise_scale", str(self._piper_noise),
                               "--noise_w", str(self._piper_noisew)]
                        subprocess.run(cmd, input=(t or " ").encode("utf-8"), check=False)
                        acmd = ["aplay", "-q"]
                        if self._aplay_device: acmd += ["-D", self._aplay_device]
                        subprocess.run(acmd + [f.name], check=False)
                        return
            except Exception:
                pass

        # --- eSpeak-ng (fallback y frases cortas) ---
        if not self._espeak:
            return
        try:
            speed = str(self._voice_speed)
            pitch = str(self._voice_pitch)
            gap   = str(self._voice_gap)
            ampl  = str(int(self._voice_ampl))

            # 1) --stdout -> aplay (stdin)
            try:
                syn = subprocess.run([self._espeak, "-v", "es", "-s", speed, "-p", pitch, "-g", gap, "-a", ampl, "--stdout", t],
                                     stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
                wav_bytes = syn.stdout or b""
                if wav_bytes:
                    cmd = ["aplay", "-q", "-f", "S16_LE", "-c", "1", "-r", str(self._aplay_rate)]
                    if self._aplay_device:
                        cmd += ["-D", self._aplay_device]
                    subprocess.run(cmd, input=wav_bytes, check=False)
                    return
            except Exception:
                pass

            # 2) fallback directo
            try:
                subprocess.run([self._espeak, "-v", "es", "-s", speed, "-p", pitch, "-g", gap, "-a", ampl, t], check=False)
            except Exception:
                pass
        except Exception:
            pass

    def _beep(self, ms: int = 250, freq: int = 1200):
        """Genera un beep simple y lo reproduce con aplay."""
        try:
            dur_s = max(0.01, ms / 1000.0)
            rate = int(self._aplay_rate) if self._aplay_rate else 48000
            n = int(dur_s * rate)
            # Seno 16-bit mono
            frames = bytearray()
            vol = 0.4  # 40% para evitar distorsión
            for i in range(n):
                val = int(32767 * vol * math.sin(2 * math.pi * freq * (i / rate)))
                frames += struct.pack("<h", val)
            # WAV temporal
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=True) as f:
                # Escribir cabecera WAV simple
                import wave
                with wave.open(f, "wb") as w:
                    w.setnchannels(1)
                    w.setsampwidth(2)
                    w.setframerate(rate)
                    w.writeframes(frames)
                cmd = ["aplay", "-q"]
                if self._aplay_device: cmd += ["-D", self._aplay_device]
                subprocess.run(cmd + [f.name], check=False)
        except Exception:
            pass

# Modo script de prueba básica
if __name__ == "__main__":
    a = Audio({})
    print("Diag:", a.tts_diag())
    a.beep(200)
    a.speak("Prueba de voz del sistema.")
