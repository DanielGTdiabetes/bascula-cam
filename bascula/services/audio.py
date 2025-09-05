# -*- coding: utf-8 -*-
"""
AudioService: salida de audio para eventos de la báscula.

Soporta dos temas:
- 'beep': pitidos cortos (sin dependencias externas, usa aplay si está)
- 'voice_es': voz español usando 'espeak-ng'/'espeak' canalizado a 'aplay'

Si no hay binarios disponibles, hace no-op (respeta mute).
"""
import os
import subprocess
import math
import wave
import struct
import tempfile


def _has_cmd(cmd: str) -> bool:
    try:
        subprocess.check_call(["/usr/bin/env", "which", cmd], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except Exception:
        return False


EVENT_TEXT_ES = {
    # Sistema / red
    "boot_ready": "Báscula lista.",
    "wifi_connected": "Wi-Fi conectado.",
    "wifi_ap_on": "Punto de acceso activo.",
    "error_generic": "Ha ocurrido un error.",
    # Pesaje y tara
    "tare_ok": "Tara realizada.",
    # 'weight_stable_beep' usa beep salvo voz explícita
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
    # Cámara / exportación
    "camera_ready": "Cámara lista.",
    "camera_error": "Error de cámara.",
    "export_ok": "Exportación completada.",
    "export_fail": "Error en la exportación.",
    # Escala / hardware
    "scale_disconnected": "Báscula desconectada.",
    "hx711_error": "Error del sensor de peso.",
    # Nutrición / IA
    "food_detected": "Detectado: {alimento}.",
    "macros_summary": "Proteína {p} gramos, hidratos {c} gramos.",
    "timer_done": "Temporizador terminado.",
    # Glucosa
    "announce_bg": "Glucosa {n} miligramos por decilitro.",
    "bg_low": "Glucosa baja.",
    "bg_high": "Glucosa alta.",
    "bg_ok": "Glucosa en rango.",
}


class AudioService:
    def __init__(self, cfg: dict | None = None, logger=None):
        self.log = logger
        self.enabled = True
        self.theme = "beep"  # 'beep' | 'voice_es'
        self._aplay_ok = _has_cmd("aplay")
        self._espeak = "espeak-ng" if _has_cmd("espeak-ng") else ("espeak" if _has_cmd("espeak") else None)
        self._aplay_device = None  # e.g., 'plughw:MAX98357A,0' or 'default'
        self._beep_gain = 0.6
        self._volume_boost = 1.3  # multiplicador global (~+30% por defecto)
        self._beep_sr = 48000
        self.update_config(cfg or {})

    # -------- Config --------
    def update_config(self, cfg: dict):
        try:
            self.enabled = bool(cfg.get("sound_enabled", True))
            self.theme = str(cfg.get("sound_theme", "beep"))
            # Permitir seleccionar dispositivo ALSA para aplay
            env_dev = os.environ.get("BASCULA_APLAY_DEVICE", "").strip()
            self._aplay_device = str(cfg.get("aplay_device", env_dev)).strip() or None
            # Ganancia y SR del beep (ajustables por ENV)
            # Multiplicador global de volumen (aplica a beep y voz)
            try:
                self._volume_boost = float(os.environ.get("BASCULA_VOLUME_BOOST", cfg.get("volume_boost", 1.3)))
            except Exception:
                self._volume_boost = 1.3
            try:
                base_gain = float(os.environ.get("BASCULA_BEEP_GAIN", cfg.get("beep_gain", 0.7)))
            except Exception:
                base_gain = 0.7
            # Aplicar boost con límites razonables
            try:
                g = max(0.05, min(1.0, base_gain * (self._volume_boost if self._volume_boost > 0 else 1.0)))
            except Exception:
                g = base_gain
            self._beep_gain = g
            try:
                self._beep_sr = int(os.environ.get("BASCULA_BEEP_SR", cfg.get("beep_sr", 48000)))
            except Exception:
                self._beep_sr = 48000
        except Exception:
            pass

    def set_enabled(self, enabled: bool):
        self.enabled = bool(enabled)

    def toggle_enabled(self) -> bool:
        self.enabled = not self.enabled
        return self.enabled

    def set_theme(self, theme: str):
        if theme in ("beep", "voice_es"):
            self.theme = theme

    # -------- Salidas --------
    def play_event(self, name: str, **params):
        if not self.enabled:
            return
        name = (name or "").strip()
        try:
            if self.theme == "voice_es" and self._espeak:
                text = EVENT_TEXT_ES.get(name)
                if not text and name == "weight_stable_beep":
                    # voz alternativa cuando estable
                    text = "Peso estable."
                if text:
                    self._speak(text.format(**params))
                    # Además del habla, para ciertos eventos también emitimos un beep corto
                    if name in ("weight_stable_beep", "timer_done", "tare_ok"):
                        self._beep(180 if name == "timer_done" else 140, 1100)
                    return
            # fallback a beep
            if name == "weight_stable_beep":
                self._beep(120, 1100)
            elif name in ("error_generic", "overload", "hx711_error", "camera_error", "export_fail"):
                self._beep(180, 400)
                self._beep(200, 350)
            elif name in ("tare_ok", "cal_ok", "export_ok"):
                self._beep(100, 1500)
            # Reducimos otros sonidos por simplicidad; mantener solo nutrición/temporizador
            elif name == "timer_done":
                # doble beep
                self._beep(120, 1200)
                self._beep(120, 900)
            elif name == "preset_added":
                self._beep(90, 1200)
            elif name == "bg_low":
                # tres beeps graves
                self._beep(160, 420); self._beep(160, 380); self._beep(160, 340)
            elif name == "bg_high":
                # dos beeps agudos
                self._beep(180, 1300); self._beep(180, 1100)
            elif name == "bg_ok":
                self._beep(90, 1000)
        except Exception:
            pass

    def speak_weight(self, grams: float):
        if not self.enabled:
            return
        if self.theme == "voice_es" and self._espeak:
            self._speak(EVENT_TEXT_ES["announce_weight"].format(n=int(round(grams))))
        else:
            self._beep(140, 1000)

    def test_beep(self):
        try:
            self._beep(200, 1000)
            self._beep(200, 1300)
            self._beep(200, 800)
        except Exception:
            pass

    # -------- Interno --------
    def _beep(self, ms: int = 100, freq: int = 1000):
        # Revalidar aplay por si se instaló tras iniciar
        if not self._aplay_ok:
            self._aplay_ok = _has_cmd("aplay")
            if not self._aplay_ok and self._espeak:
                # Fallback: usar voz para un "beep" breve (mejor que silencio)
                try:
                    self._speak("pip")
                except Exception:
                    pass
                return
        # Generar onda senoidal mono 16-bit 44.1kHz
        sr = self._beep_sr if isinstance(self._beep_sr, int) and self._beep_sr > 8000 else 44100
        n_samples = max(1, int(sr * (ms / 1000.0)))
        buf = bytearray()
        for i in range(n_samples):
            t = i / sr
            gain = self._beep_gain
            if not (0.05 <= gain <= 1.0):
                gain = 0.7
            val = int(32767 * gain * math.sin(2 * math.pi * freq * t))
            buf += struct.pack('<h', val)
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=True) as f:
            with wave.open(f, 'wb') as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(sr)
                wf.writeframes(buf)
            try:
                cmd = ["aplay", "-q"]
                if self._aplay_device:
                    cmd += ["-D", self._aplay_device]
                cmd += [f.name]
                rc = subprocess.run(cmd, check=False).returncode
                if rc not in (0, None) and self._espeak:
                    # Fallback si aplay falla
                    self._speak("pip")
            except Exception:
                pass

    def _speak(self, text: str):
        if not self._espeak:
            return
        # espeak -> stdout WAV -> aplay
        try:
            # Amplitud 0..200; escalamos desde boost (100 * boost, limitado)
            try:
                amp_env = os.environ.get("BASCULA_VOICE_AMPL", "").strip()
                ampl = int(amp_env) if amp_env else int(max(10, min(200, round(100 * (self._volume_boost if self._volume_boost > 0 else 1.0)))))
            except Exception:
                ampl = 130
            p1 = subprocess.Popen([
                    self._espeak,
                    "-v", "es",
                    "-s", os.environ.get("BASCULA_VOICE_SPEED", "165"),
                    "-a", str(ampl),
                    "--stdout", text
                ], stdout=subprocess.PIPE)
            cmd = ["aplay", "-q"]
            if self._aplay_device:
                cmd += ["-D", self._aplay_device]
            subprocess.run(cmd, stdin=p1.stdout, check=False)
            try:
                p1.stdout.close()
            except Exception:
                pass
            p1.wait(timeout=2)
        except Exception:
            pass
