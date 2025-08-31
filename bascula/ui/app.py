# -*- coding: utf-8 -*-
"""
Báscula Digital Pro - App principal
- Mantiene TU UI (bascula.ui.screens / bascula.ui.widgets).
- Integra CameraService para la captura de fotos.
- Limpieza de recursos y atajos de teclado.
"""
from __future__ import annotations
import os
import time
import tkinter as tk

# Servicios y utilidades del proyecto (no los toco)
from serial_reader import SerialReader
from tare_manager import TareManager
from utils import load_config, save_config, MovingAverage

# Cámara
from bascula.services.camera import CameraService, CameraError


class BasculaApp:
    def __init__(self) -> None:
        # Ventana raíz
        self.root = tk.Tk()
        self.root.title("Báscula Digital Pro")

        # Flags desde variables de entorno
        self._fullscreen = os.environ.get("BASCULA_FULLSCREEN", "0").lower() in ("1", "true", "yes")
        self._borderless = os.environ.get("BASCULA_BORDERLESS", "1").lower() in ("1", "true", "yes")
        self._debug = os.environ.get("BASCULA_DEBUG", "0").lower() in ("1", "true", "yes")

        self.root.update_idletasks()
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()

        # Borde/ventana
        if self._borderless:
            try:
                self.root.overrideredirect(True)
            except Exception:
                pass
        if self._fullscreen:
            try:
                self.root.attributes("-fullscreen", True)
            except Exception:
                pass
        self.root.geometry(f"{sw}x{sh}+0+0")
        self.root.resizable(False, False)

        # Cerrar y atajos
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.bind("<Escape>", lambda e: self._on_close())
        self.root.bind("<Control-q>", lambda e: self._on_close())
        self.root.bind("<F11>", lambda e: self._toggle_borderless())
        self.root.bind("<F1>", lambda e: self._toggle_debug())

        try:
            self.root.configure(cursor="none")
        except Exception:
            pass

        # Servicios
        self._init_services()

        # UI (tus pantallas)
        self._build_ui()

        # Overlay debug opcional
        self._overlay = None
        if self._debug:
            self._overlay = self._build_overlay()
            self._tick_overlay()

        self.root.focus_force()
        self.root.update_idletasks()
        self.root.geometry(f"{sw}x{sh}+0+0")
        self.root.lift()

    # ----------------- Servicios -----------------
    def _init_services(self):
        try:
            self.cfg = load_config()
        except Exception:
            # Config por defecto
            self.cfg = {
                "port": "/dev/serial0",
                "baud": 115200,
                "calib_factor": 1.0,
                "unit": "g",
                "smoothing": 5,
                "decimals": 0,
                "openai_api_key": "",
            }

        # Lectura peso
        try:
            self.reader = SerialReader(
                port=self.cfg.get("port", "/dev/serial0"),
                baud=self.cfg.get("baud", 115200),
            )
            self.reader.start()
        except Exception:
            self.reader = None

        # Tara + suavizado
        self.tare = TareManager(calib_factor=self.cfg.get("calib_factor", 1.0))
        self.smoother = MovingAverage(size=self.cfg.get("smoothing", 5))

        # Cámara
        self.camera = CameraService()
        try:
            self.camera.open()
        except Exception:
            # Si no se puede abrir ahora, se intentará al capturar
            pass

    # ----------------- UI -----------------
    def _build_ui(self):
        # Scaling para tu UI (no toco estilo)
        try:
            from bascula.ui.widgets import auto_apply_scaling, COL_BG
            auto_apply_scaling(self.root, target=(1024, 600))
            bg = COL_BG
        except Exception:
            bg = "#0a0e1a"

        self.main = tk.Frame(self.root, bg=bg)
        self.main.pack(fill="both", expand=True)

        self.screens = {}
        self.current_screen = None

        # Tus pantallas (NO cambio)
        from bascula.ui.screens import (
            HomeScreen,
            SettingsMenuScreen,
            CalibScreen,
            WifiScreen,
            ApiKeyScreen,
        )

        self.screens["home"] = HomeScreen(self.main, self, on_open_settings_menu=lambda: self.show_screen("settings_menu"))
        self.screens["settings_menu"] = SettingsMenuScreen(self.main, self)
        self.screens["calib"] = CalibScreen(self.main, self)
        self.screens["wifi"] = WifiScreen(self.main, self)
        self.screens["apikey"] = ApiKeyScreen(self.main, self)

        self.show_screen("home")

    def show_screen(self, name: str):
        if getattr(self, "current_screen", None):
            try:
                if hasattr(self.current_screen, "on_hide"):
                    self.current_screen.on_hide()
            except Exception:
                pass
            self.current_screen.pack_forget()

        screen = self.screens.get(name)
        if screen:
            screen.pack(fill="both", expand=True)
            self.current_screen = screen
            try:
                if hasattr(screen, "on_show"):
                    screen.on_show()
            except Exception:
                pass

    # ----------------- Overlay debug opcional -----------------
    def _build_overlay(self) -> tk.Label:
        ov = tk.Label(self.root, text="", bg="#000000", fg="#00ff00", font=("monospace", 10),
                      justify="left", anchor="nw")
        ov.place(x=5, y=5)
        return ov

    def _tick_overlay(self):
        if not self._overlay:
            return
        try:
            sw = self.root.winfo_screenwidth()
            sh = self.root.winfo_screenheight()
            ww = self.root.winfo_width()
            wh = self.root.winfo_height()
            weight = self.get_latest_weight()
            txt = (
                f"Screen: {sw}x{sh}\n"
                f"Window: {ww}x{wh}\n"
                f"Weight: {weight:.2f} {self.cfg.get('unit','g')}\n"
                f"Borderless: {self._borderless}\n"
                f"Fullscreen: {self._fullscreen}"
            )
            self._overlay.config(text=txt)
        except Exception as e:
            self._overlay.config(text=f"Debug Error: {e}")
        self.root.after(1000, self._tick_overlay)

    def _toggle_borderless(self):
        self._borderless = not self._borderless
        try:
            self.root.overrideredirect(self._borderless)
        except Exception:
            pass

    def _toggle_debug(self):
        self._debug = not self._debug
        if self._debug and not self._overlay:
            self._overlay = self._build_overlay()
            self._tick_overlay()
        elif not self._debug and self._overlay:
            try:
                self._overlay.destroy()
            except Exception:
                pass
            self._overlay = None

    # ----------------- API para pantallas -----------------
    def get_cfg(self) -> dict:
        return self.cfg

    def save_cfg(self) -> None:
        try:
            save_config(self.cfg)
        except Exception as e:
            print(f"[APP] Error guardando config: {e}")

    def get_reader(self):
        return self.reader

    def get_tare(self):
        return self.tare

    def get_smoother(self):
        return self.smoother

    def get_latest_weight(self) -> float:
        """Peso neto suavizado (o 0.0 si no hay lectura)."""
        try:
            if self.reader:
                raw = self.reader.get_latest()
                if raw is not None:
                    sm = self.smoother.add(raw)
                    return self.tare.compute_net(sm)
            return 0.0
        except Exception:
            return 0.0

    # --- Cámara (llamado desde tu UI cuando pulses 'Foto' / etc.) ---
    def capture_image(self) -> str:
        """
        Captura una foto y devuelve la ruta del JPEG.
        Si no hay cámara, lanza CameraError.
        """
        try:
            if not self.camera.is_open():
                self.camera.open()
            path = self.camera.capture_jpeg()
            return path
        except Exception as e:
            raise CameraError(str(e))

    # (stub) Petición de nutrición si la UI lo usa
    def request_nutrition(self, image_path: str, grams: float) -> dict:
        # Aquí NO toco nada serio: responde con valores de ejemplo
        g = max(0.0, grams or 0.0)
        return {
            "name": "Desconocido",
            "grams": g,
            "kcal": g * 0.80,
            "carbs": g * 0.15,
            "protein": g * 0.010,
            "fat": g * 0.010,
            "image_path": image_path,
        }

    # (stub) WiFi si tu UI lo llama
    def wifi_connect(self, ssid: str, psk: str) -> bool:
        print(f"[APP] wifi_connect -> SSID='{ssid}' (stub)")
        return False

    def wifi_scan(self):
        print("[APP] wifi_scan solicitado (stub)")
        return ["Intek_5G", "Intek_2G", "Casa_Dani", "Invitados", "Orange-1234"]

    # ----------------- Lifecycle -----------------
    def run(self) -> None:
        try:
            sw = self.root.winfo_screenwidth()
            sh = self.root.winfo_screenheight()
            self.root.geometry(f"{sw}x{sh}+0+0")
            self.root.mainloop()
        except KeyboardInterrupt:
            pass
        finally:
            self._cleanup()

    def _on_close(self):
        self._cleanup()
        # Salida inmediata
        import sys
        sys.exit(0)

    def _cleanup(self):
        try:
            if self._overlay:
                try:
                    self._overlay.destroy()
                except Exception:
                    pass
                self._overlay = None
            if self.reader:
                try:
                    self.reader.stop()
                except Exception:
                    pass
            if self.camera:
                try:
                    self.camera.close()
                except Exception:
                    pass
            try:
                self.root.quit()
                self.root.destroy()
            except Exception:
                pass
        except Exception as e:
            print(f"[APP] Error cierre: {e}")
