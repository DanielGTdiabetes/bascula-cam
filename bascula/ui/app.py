# -*- coding: utf-8 -*-
import os, time, random
import tkinter as tk

from serial_reader import SerialReader
from tare_manager import TareManager
from utils import load_config, save_config, MovingAverage

# Cámara
try:
    from bascula.services.camera import CameraService, CameraUnavailable
except Exception:
    CameraService = None  # type: ignore
    CameraUnavailable = Exception  # type: ignore

class BasculaAppTk:
    def __init__(self) -> None:
        self.root = tk.Tk(); self.root.title("Báscula Digital Pro")
        # ventana / pantalla
        try: self.root.overrideredirect(True)
        except Exception: pass
        sw = self.root.winfo_screenwidth(); sh = self.root.winfo_screenheight()
        self.root.geometry(f"{sw}x{sh}+0+0"); self.root.resizable(False, False)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        # atajos
        self.root.bind("<Escape>", lambda e:self._on_close())
        self.root.bind("<Control-q>", lambda e:self._on_close())
        self.root.bind("<F11>", lambda e:self._toggle_borderless())
        self.root.bind("<F1>", lambda e:self._toggle_debug())

        self._borderless = True; self._debug = False; self._overlay = None

        self._init_services()
        self._build_ui()
        self.show_screen("home")

    # ---------- servicios ----------
    def _init_services(self):
        try:
            self.cfg = load_config()
            self.reader = SerialReader(port=self.cfg.get("port","/dev/serial0"), baud=self.cfg.get("baud",115200))
            self.tare = TareManager(calib_factor=self.cfg.get("calib_factor",1.0))
            self.smoother = MovingAverage(size=self.cfg.get("smoothing",5))
            self.reader.start()
        except Exception as e:
            print(f"[APP] Error servicios: {e}")
            self.cfg = {"port":"/dev/serial0","baud":115200,"calib_factor":1.0,"unit":"g","smoothing":5,"decimals":0}
            self.reader = None
            self.tare = TareManager(calib_factor=1.0)
            self.smoother = MovingAverage(size=5)

        # Servicio de cámara (lazy-init)
        try:
            cap_dir = os.path.abspath(os.path.join(os.path.dirname(os.path.dirname(__file__)), "..", "captures"))
            os.makedirs(cap_dir, exist_ok=True)
            self.camera = CameraService(width=1024, height=600, fps=10, save_dir=cap_dir) if CameraService else None
        except Exception as e:
            print(f"[APP] Cámara no disponible: {e}")
            self.camera = None

    # ---------- UI ----------
    def _build_ui(self):
        self.main = tk.Frame(self.root, bg="#0a0e1a"); self.main.pack(fill="both", expand=True)
        self.screens = {}; self.current_screen = None
        try:
            from bascula.ui.screens import HomeScreen, SettingsMenuScreen, CalibScreen, WifiScreen, ApiKeyScreen
            self.screens["home"] = HomeScreen(self.main, self, on_open_settings_menu=lambda:self.show_screen("settings_menu"))
            self.screens["settings_menu"] = SettingsMenuScreen(self.main, self)
            self.screens["calib"] = CalibScreen(self.main, self)
            self.screens["wifi"] = WifiScreen(self.main, self)
            self.screens["apikey"] = ApiKeyScreen(self.main, self)
        except Exception as e:
            # Fallback mínimo: una única pantalla con botón de prueba
            print(f"[APP] screens fallback: {e}")
            f = tk.Frame(self.main, bg="#0a0e1a"); f.pack(fill="both", expand=True)
            b = tk.Button(f, text="Añadir con cámara", command=self._demo_camera, font=("DejaVu Sans", 24))
            b.pack(pady=40)
            self.screens["home"] = f
        self.current_screen = None

    def show_screen(self, name: str):
        if self.current_screen and hasattr(self.current_screen, "pack_forget"):
            self.current_screen.pack_forget()
        scr = self.screens.get(name)
        if hasattr(scr, "pack"):
            scr.pack(fill="both", expand=True)
        self.current_screen = scr

    # ---------- helpers de cámara para la UI ----------
    def start_camera_preview(self, container):
        lbl = tk.Label(container, bg="#000000"); lbl.pack(expand=True, fill="both")
        if getattr(self, "camera", None):
            try:
                return self.camera.preview_to_tk(lbl)
            except Exception as e:
                lbl.config(text=f"Cámara no disponible\n{e}", fg="#fff")
        else:
            lbl.config(text="Cámara no disponible", fg="#fff")
        return lambda: None

    def capture_image(self) -> str:
        if getattr(self, "camera", None):
            try:
                return self.camera.capture_still()
            except Exception as e:
                print(f"[APP] Error captura: {e}")
        # Fallback: fichero vacío
        p = f"/tmp/capture_{int(time.time())}.jpg"
        try:
            with open(p, "wb") as f: f.write(b"")
        except Exception: pass
        return p

    def _demo_camera(self):
        modal = tk.Toplevel(self.root); modal.configure(bg="#0a0e1a")
        try: modal.overrideredirect(True)
        except Exception: pass
        modal.geometry(f"{self.root.winfo_screenwidth()}x{self.root.winfo_screenheight()}+0+0")
        cont = tk.Frame(modal, bg="#0a0e1a"); cont.pack(expand=True, fill="both", padx=20, pady=20)
        area = tk.Frame(cont, bg="#000000"); area.pack(expand=True, fill="both")
        stop_prev = self.start_camera_preview(area)
        row = tk.Frame(cont, bg="#0a0e1a"); row.pack(fill="x", pady=10)
        tk.Button(row, text="Cancelar", command=lambda:(stop_prev(), modal.destroy())).pack(side="left")
        tk.Button(row, text="📸 Capturar", command=lambda:(stop_prev(), modal.destroy(), self.capture_image())).pack(side="right")

    # ---------- utilidades varias ----------
    def get_latest_weight(self) -> float:
        try:
            if self.reader:
                raw = self.reader.get_latest()
                if raw is not None:
                    sm = self.smoother.add(raw); return self.tare.compute_net(sm)
            return 0.0
        except Exception:
            return 0.0

    def _toggle_borderless(self):
        try:
            self._borderless = not self._borderless
            self.root.overrideredirect(self._borderless)
        except Exception:
            pass

    def _toggle_debug(self):
        self._debug = not self._debug

    def _on_close(self):
        try:
            if getattr(self, "camera", None):
                try: self.camera.stop()
                except Exception: pass
            if self.reader:
                self.reader.stop()
            self.root.quit(); self.root.destroy()
        except Exception as e:
            print(f"[APP] Error cierre: {e}")
        finally:
            import sys; sys.exit(0)

    def run(self) -> None:
        try:
            self.root.mainloop()
        except KeyboardInterrupt:
            pass
        finally:
            try:
                if self.reader: self.reader.stop()
            except Exception:
                pass

if __name__ == "__main__":
    BasculaAppTk().run()
