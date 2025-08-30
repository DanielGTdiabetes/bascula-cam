cat > bascula/ui/app.py <<'PY'
# -*- coding: utf-8 -*-
import os
import json
import threading
import time
import tkinter as tk

# UI
from bascula.ui.widgets import auto_apply_scaling, COL_BG
from bascula.ui.screens import HomeScreen, SettingsScreen

# —— Dependencias “opcionales” (modo real) ——
try:
    from serial_reader import SerialReader  # debe exponer get_latest()
    _HAS_SERIAL = True
except Exception:
    _HAS_SERIAL = False
    SerialReader = None


# ===============================
# Configuración persistente (JSON)
# ===============================
def _config_path():
    base = os.path.expanduser("~/.bascula")
    os.makedirs(base, exist_ok=True)
    return os.path.join(base, "config.json")


def _default_cfg():
    return {
        "unit": "g",         # "g" o "kg"
        "decimals": 0,       # 0 recomendado
        "smoothing": 5,      # muestras para suavizado
        "calib_factor": 1.0  # gramos por cuenta bruta
    }


def load_cfg():
    p = _config_path()
    if not os.path.exists(p):
        return _default_cfg()
    try:
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
        base = _default_cfg()
        base.update(data or {})
        return base
    except Exception:
        return _default_cfg()


def save_cfg(cfg):
    p = _config_path()
    try:
        with open(p, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False)
    except Exception:
        pass


# =====================
# Smoother (media móvil)
# =====================
class Smoother:
    def __init__(self, size=5):
        self.size = max(1, int(size))
        self.buf = []
        self._lock = threading.Lock()

    def add(self, v):
        with self._lock:
            self.buf.append(float(v))
            if len(self.buf) > self.size:
                self.buf.pop(0)
            return sum(self.buf) / len(self.buf)


# =======================
# Tara + Calibración (g/raw)
# =======================
class TareAndCalib:
    def __init__(self, calib_factor=1.0):
        self._tare_raw = 0.0
        self._calib = float(calib_factor)

    def set_tare(self, raw_value):
        self._tare_raw = float(raw_value)

    def compute_net(self, raw_smoothed):
        return max(0.0, (float(raw_smoothed) - self._tare_raw) * self._calib)

    def update_calib(self, calib_factor):
        self._calib = float(calib_factor)

    @property
    def calib(self):
        return self._calib


# ===========================
# Lector de datos (opcional)
# ===========================
class ReaderFacade:
    def __init__(self):
        self._reader = None
        self._last = None
        self._stop = False

        if _HAS_SERIAL and SerialReader is not None:
            try:
                self._reader = SerialReader()
            except Exception:
                self._reader = None

        if self._reader is not None:
            t = threading.Thread(target=self._poll_loop, daemon=True)
            t.start()

    def _poll_loop(self):
        while not self._stop:
            try:
                v = self.get_latest()
                if v is None:
                    time.sleep(0.05)
                else:
                    time.sleep(0.02)
            except Exception:
                time.sleep(0.1)

    def stop(self):
        self._stop = True

    def get_latest(self):
        if self._reader is None:
            return None
        try:
            return self._reader.get_latest()
        except Exception:
            return None


# ======================
# App principal (Tkinter)
# ======================
class BasculaAppTk:
    # >>> Firma COMPATIBLE: acepta root y cfg opcionales (aunque no se usen)
    def __init__(self, root=None, cfg=None):
        # ——— Crear raíz y ocupar 100% de pantalla ———
        self.root = tk.Tk()
        self.root.title("Báscula Digital Pro")
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        self.root.geometry(f"{sw}x{sh}+0+0")
        self.root.configure(bg=COL_BG)

        # Pantalla completa y atajos
        if os.environ.get("BASCULA_FULLSCREEN", "1") == "1":
            self.root.attributes("-fullscreen", True)
        self.root.bind("<F11>", lambda e: self.root.attributes("-fullscreen",
                          not self.root.attributes("-fullscreen")))
        self.root.bind("<Escape>", lambda e: self.root.attributes("-fullscreen", False))

        # ——— APLICAR SCALING AQUÍ ———
        scaling_env = os.environ.get("BASCULA_SCALING", "auto")
        if scaling_env == "auto":
            auto_apply_scaling(self.root, target=(1024, 600), force=True)
        else:
            try:
                self.root.tk.call('tk', 'scaling', float(scaling_env))
            except Exception:
                pass

        # ——— Estado / servicios ———
        # Usa cfg si te lo pasan como dict; si no, carga de disco
        self._cfg = cfg if isinstance(cfg, dict) else load_cfg()
        self._smoother = Smoother(size=int(self._cfg.get("smoothing", 5)))
        self._tare = TareAndCalib(calib_factor=float(self._cfg.get("calib_factor", 1.0)))
        self._reader = ReaderFacade()

        # ——— Contenedor principal ———
        self.container = tk.Frame(self.root, bg=COL_BG)
        self.container.grid(row=0, column=0, sticky="nsew")
        self.root.grid_rowconfigure(0, weight=1)
        self.root.grid_columnconfigure(0, weight=1)

        # ——— Pantallas ———
        self.screens = {}
        self._build_screens()
        self.show("home")

    # -------------- Servicios expuestos a las pantallas --------------
    def get_cfg(self):
        return self._cfg

    def save_cfg(self):
        save_cfg(self._cfg)
        self._smoother.size = int(self._cfg.get("smoothing", 5))
        self._tare.update_calib(float(self._cfg.get("calib_factor", self._tare.calib)))

    def get_reader(self):
        return self._reader

    def get_smoother(self):
        return self._smoother

    def get_tare(self):
        return self._tare

    # -------------- Gestión de pantallas --------------
    def _build_screens(self):
        def open_settings():
            self.show("settings")

        def back_home():
            self.show("home")

        home = HomeScreen(self.container, self, on_open_settings=open_settings)
        settings = SettingsScreen(self.container, self, on_back=back_home)

        self.screens["home"] = home
        self.screens["settings"] = settings

        for _, scr in self.screens.items():
            scr.grid(row=0, column=0, sticky="nsew")

    def show(self, name: str):
        scr = self.screens.get(name)
        if not scr:
            return
        scr.tkraise()
        if hasattr(scr, "on_show"):
            try:
                scr.on_show()
            except Exception:
                pass

    # -------------- Bucle principal --------------
    def run(self):
        try:
            self.root.mainloop()
        finally:
            try:
                if self._reader:
                    self._reader.stop()
            except Exception:
                pass


# =========
# Launcher
# =========
if __name__ == "__main__":
    BasculaAppTk().run()
PY
