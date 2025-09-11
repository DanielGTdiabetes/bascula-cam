# -*- coding: utf-8 -*-
import os
import math
import struct
import shutil
import tempfile
import subprocess
import threading
import wave  # <-- Se ha añadido la importación que faltaba
from typing import Optional

# Diccionario de eventos de voz en español
EVENT_TEXT_ES = {
    # Sistema / red
    "boot_ready": "Báscula lista.",
    "wifi_connected": "Wi-Fi conectado.",
    "wifi_ap_on": "Punto de acceso activo.",
    "error_generic": "Ha ocurrido un error.",
    # Pesaje y tara
    "tare_ok": "Tara realizada.",
    "announce_weight": "Peso: {n} gramos.",
    "overload": "Sobrecarga, retire peso.",
    # Modos y acciones
    "plate_mode_on": "Modo plato completo.",
    "add_food": "Añade alimento.",
    "preset_added": "Añadido {n} gramos predefinidos.",
    # Calibración
    "cal_start": "Iniciando calibración.",
    "cal_put_ref": "Coloque el peso de referencia.",
    "cal_remove_ref": "Retire el peso de referencia.",
    "cal_ok": "Calibración completada.",
    "cal_fail": "Error de calibración.",
    # Nutrición / IA
    "food_detected": "Detectado: {alimento}.",
    "macros_summary": "Proteína {p} gramos, hidratos {c} gramos.",
    "timer_done": "Temporizador terminado.",
    "meal_totals": "Totales: {g} gramos, {k} calorías, {c} hidratos, {p} proteínas y {f} grasas.",
    # Glucosa
    "announce_bg": "Glucosa {n} miligramos por decilitro.",
    "bg_low": "Glucosa baja.",
    "bg_high": "Glucosa alta.",
    "bg_ok": "Glucosa en rango.",
}


def _has_cmd(cmd: str) -> bool:
    return shutil.which(cmd) is not None

class AudioService:
    def __init__(self, cfg: Optional[dict] = None, logger=None):
        cfg = cfg or {}
        self.log = logger
        self.enabled = True
        self.theme = "beep"  # 'beep' or 'voice_es'

        # --- Componentes base ---
        self._aplay_ok = _has_cmd("aplay")
        self._espeak = shutil.which("espeak-ng") or shutil.which("espeak")
        self._piper = shutil.which("piper")

        # --- Configuración (con valores por defecto) ---
        self._aplay_device: Optional[str] = None
        self._aplay_rate: int = 48000
        self._voice_speed: int = 165
        self._voice_pitch: int = 55
        self._voice_gap: int = 8
        self._voice_ampl: int = 120
        self._piper_enabled: bool = True
        self._piper_model: Optional[str] = None
        self._piper_len: float = 1.05
        self._piper_noise: float = 0.667
        self._piper_noisew: float = 0.8
        self._piper_hybrid: bool = True
        self._piper_prewarm: bool = True
        self._beep_gain: float = 0.6
        self._volume_boost: float = 1.3

        self.update_config(cfg)  # Aplicar configuración inicial

        self._prewarm_started = False
        if self._piper_prewarm:
            try:
                threading.Thread(target=self._prewarm_piper, daemon=True).start()
                self._prewarm_started = True
            except Exception as e:
                if self.log: self.log.warning(f"Fallo al iniciar el precalentamiento de Piper: {e}")

    # --- API pública (compatible con el resto de la app) ---
    def update_config(self, cfg: dict):
        if not isinstance(cfg, dict): return
        
        def _i(env, key, default):
            try: return int(os.environ.get(env, cfg.get(key, default)))
            except (ValueError, TypeError): return default

        def _f(env, key, default):
            try: return float(os.environ.get(env, cfg.get(key, default)))
            except (ValueError, TypeError): return default
        
        self.enabled = bool(cfg.get("sound_enabled", self.enabled))
        self.theme = str(cfg.get("sound_theme", self.theme))
        
        dev = str(cfg.get("aplay_device") or os.environ.get("BASCULA_APLAY_DEVICE", "")).strip()
        self._aplay_device = dev if dev else None
        self._aplay_rate = _i("BASCULA_APLAY_RATE", "aplay_rate", self._aplay_rate)

        # Prosodia eSpeak
        self._voice_speed = _i("BASCULA_VOICE_SPEED", "voice_speed", 165)
        self._voice_pitch = _i("BASCULA_VOICE_PITCH", "voice_pitch", 55)
        self._voice_gap   = _i("BASCULA_VOICE_GAP",   "voice_gap",   8)
        self._voice_ampl  = _i("BASCULA_VOICE_AMPL",  "voice_ampl",  120)

        # Configuración Piper
        self._piper_enabled = bool(cfg.get("piper_enabled", self._piper_enabled))
        self._piper_model   = os.environ.get("BASCULA_PIPER_MODEL") or os.environ.get("PIPER_MODEL") or cfg.get("piper_model")
        self._piper_len     = _f("BASCULA_PIPER_LEN", "piper_len", 1.05)
        self._piper_noise   = _f("BASCULA_PIPER_NOISE", "piper_noise", 0.667)
        self._piper_noisew  = _f("BASCULA_PIPER_NOISEW", "piper_noisew", 0.8)
        self._piper_hybrid  = bool(cfg.get("piper_hybrid", self._piper_hybrid))
        self._piper_prewarm = bool(cfg.get("piper_prewarm", self._piper_prewarm))

        # Volumen y ganancia
        self._volume_boost = _f("BASCULA_VOLUME_BOOST", "volume_boost", 1.3)
        base_gain = _f("BASCULA_BEEP_GAIN", "beep_gain", 0.7)
        self._beep_gain = max(0.05, min(1.0, base_gain * self._volume_boost))

    def set_enabled(self, enabled: bool): self.enabled = bool(enabled)
    def set_theme(self, theme: str):
        if theme in ("beep", "voice_es"): self.theme = theme

    def play_event(self, name: str, **params):
        if not self.enabled: return
        name = (name or "").strip()
        
        try:
            # --- MODO VOZ ---
            if self.theme == "voice_es":
                text = EVENT_TEXT_ES.get(name)
                if text:
                    self._speak(text.format(**params))
                    # Si el evento es 'timer_done', reproduce un beep largo después de la voz
                    if name == "timer_done":
                        self._beep(3000, 1100)  # <-- CAMBIO: Beep de 3 segundos
                    elif name in ("weight_stable_beep", "tare_ok"):
                        self._beep(140, 1100)
                    return
            
            # --- MODO BEEP (FALLBACK) ---
            if name == "weight_stable_beep": self._beep(120, 1100)
            elif name in ("error_generic", "overload", "hx711_error"): self._beep(180, 400); self._beep(200, 350)
            elif name in ("tare_ok", "cal_ok", "export_ok"): self._beep(100, 1500)
            elif name == "timer_done":
                # <-- CAMBIO: Secuencia de alarma de ~3 segundos
                self._beep(800, 1200)
                self._beep(800, 900)
                self._beep(800, 1200)
            elif name == "preset_added": self._beep(90, 1200)
            elif name == "bg_low": self._beep(160, 420); self._beep(160, 380); self._beep(160, 340)
            elif name == "bg_high": self._beep(180, 1300); self._beep(180, 1100)
            elif name == "bg_ok": self._beep(90, 1000)

        except Exception as e:
            if self.log: self.log.error(f"Error en play_event para '{name}': {e}")

    # --- Métodos privados ---
    def _prewarm_piper(self):
        try:
            if not (self._piper_enabled and self._piper and self._piper_model and os.path.exists(self._piper_model)):
                return
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=True) as f:
                subprocess.run([self._piper, "-m", self._piper_model, "-f", f.name,
                                "--length_scale", str(self._piper_len),
                                "--noise_scale", str(self._piper_noise),
                                "--noise_w", str(self._piper_noisew)],
                               input=b" ", check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if self.log: self.log.info("TTS Piper precalentado.")
        except Exception as e:
            if self.log: self.log.warning(f"Fallo al precalentar Piper: {e}")

    def _speak(self, text: str):
        text = (text or "").strip()
        if not text: return

        is_long = (len(text) >= 60) or (text.count(",") + text.count(" ") >= 12)
        use_piper = self._piper_enabled and self._piper and self._piper_model and \
                    os.path.exists(self._piper_model) and \
                    (not self._piper_hybrid or is_long)

        # 1. Intentar con Piper si se cumplen las condiciones
        if use_piper:
            try:
                with tempfile.NamedTemporaryFile(suffix=".wav", delete=True) as f:
                    cmd_piper = [self._piper, "-m", self._piper_model, "-f", f.name,
                                 "--length_scale", str(self._piper_len),
                                 "--noise_scale", str(self._piper_noise),
                                 "--noise_w", str(self._piper_noisew)]
                    subprocess.run(cmd_piper, input=text.encode("utf-8"), check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    
                    cmd_aplay = ["aplay", "-q"]
                    if self._aplay_device: cmd_aplay += ["-D", self._aplay_device]
                    cmd_aplay.append(f.name)
                    subprocess.run(cmd_aplay, check=True)
                    return # Éxito
            except Exception as e:
                if self.log: self.log.warning(f"TTS con Piper falló, usando eSpeak. Error: {e}")
        
        # 2. Fallback a eSpeak
        if not self._espeak: return
        try:
            cmd_espeak = [self._espeak, "-v", "es", 
                          "-s", str(self._voice_speed),
                          "-p", str(self._voice_pitch),
                          "-g", str(self._voice_gap),
                          "-a", str(self._voice_ampl),
                          "--stdout", text]
            
            p1 = subprocess.Popen(cmd_espeak, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
            
            cmd_aplay = ["aplay", "-q"]
            if self._aplay_device: cmd_aplay += ["-D", self._aplay_device]
            
            p2 = subprocess.Popen(cmd_aplay, stdin=p1.stdout, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if p1.stdout:
                p1.stdout.close()
            p2.communicate(timeout=10)
        except Exception as e:
            if self.log: self.log.error(f"TTS con eSpeak falló: {e}")

    def _beep(self, ms: int = 250, freq: int = 1200):
        if not self._aplay_ok: return
        try:
            dur_s = max(0.01, ms / 1000.0)
            rate = self._aplay_rate
            n_samples = int(dur_s * rate)
            frames = bytearray()
            for i in range(n_samples):
                val = int(32767 * self._beep_gain * math.sin(2 * math.pi * freq * (i / rate)))
                frames += struct.pack("<h", val)

            with tempfile.NamedTemporaryFile(suffix=".wav", delete=True) as f:
                with wave.open(f, "wb") as w:
                    w.setnchannels(1)
                    w.setsampwidth(2)
                    w.setframerate(rate)
                    w.writeframes(frames)
                f.seek(0)
                cmd = ["aplay", "-q"]
                if self._aplay_device: cmd += ["-D", self._aplay_device]
                cmd.append(f.name)
                subprocess.run(cmd, check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception as e:
            if self.log: self.log.error(f"Fallo en beep: {e}")

    # ---- API pública de TTS para texto libre ----
    def speak_text(self, text: str) -> None:
        """Habla un texto libre usando el mejor TTS disponible (Piper > eSpeak).

        - Aprovecha configuración de Piper si está instalada.
        - Fallback automático a eSpeak.
        - No bloquea el hilo de UI (internamente usa subprocesos/hilos breves).
        """
        try:
            self._speak(text)
        except Exception as e:
            if self.log: self.log.warning(f"speak_text fallo: {e}")
