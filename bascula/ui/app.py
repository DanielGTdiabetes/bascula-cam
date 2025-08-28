# bascula/ui/app.py
import tkinter as tk
from tkinter import messagebox
from pathlib import Path
import json

# ---- imports de tu proyecto (paquete bascula) ----
from bascula.config.settings import load_config
from bascula.services.logging import get_logger
from bascula.services.storage import Storage
from bascula.state import AppState
from bascula.services.scale import ScaleService
from bascula.services.camera import CameraService

# Si usas la pantalla moderna que ya añadimos:
from bascula.ui.extras.modern_home import ModernHome

# --- Utilidad simple para persistir calibración (opcional pero útil) ---
def _load_calibration():
    cfg_path = Path("~/.bascula/config.json").expanduser()
    if not cfg_path.exists():
        return None
    try:
        data = json.loads(cfg_path.read_text(encoding="utf-8"))
        cal = data.get("calibration") or {}
        base = cal.get("base_offset", data.get("base_offset"))
        scale = cal.get("scale_factor", data.get("scale_factor"))
        if base is not None and scale is not None:
            return float(base), float(scale)
    except Exception:
        pass
    return None

def _save_calibration(base_offset: float, scale_factor: float):
    cfg_path = Path("~/.bascula/config.json").expanduser()
    cfg_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        data = {}
        if cfg_path.exists():
            try:
                data = json.loads(cfg_path.read_text(encoding="utf-8"))
            except Exception:
                data = {}
        data.setdefault("calibration", {})
        data["calibration"]["base_offset"] = float(base_offset)
        data["calibration"]["scale_factor"] = float(scale_factor)
        # espejo plano para compatibilidad
        data["base_offset"] = float(base_offset)
        data["scale_factor"] = float(scale_factor)
        cfg_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except Exception as e:
        print("No se pudo guardar calibración:", e)

def run_app():
    # config y servicios
    cfg = load_config()
    logger = get_logger(cfg.base_dir)
    storage = Storage(cfg.base_dir)
    state = AppState(cfg=cfg)
    scale = ScaleService(state, logger)
    camera = CameraService(state, logger, storage)

    # aplica calibración guardada si existe
    cal = _load_calibration()
    if cal:
        base, factor = cal
        # intenta setear en los nombres habituales
        for name, val in (("offset", base), ("base_offset", base),
                          ("scale_factor", factor), ("calibration_scale", factor)):
            if hasattr(scale, name):
                try:
                    setattr(scale, name, val)
                except Exception:
                    pass
        # si tu ScaleService tiene método específico:
        for setter in ("apply_calibration", "set_calibration"):
            if hasattr(scale, setter):
                try:
                    getattr(scale, setter)(base, factor)
                except Exception:
                    pass
        logger.info(f"Calibración aplicada: offset={base:.3f} scale={factor:.6f}")
    else:
        logger.info("Sin calibración previa persistida.")

    # Tk y pantalla moderna
    root = tk.Tk()
    root.title("⚖️ SMART SCALE PRO")
    try:
        root.attributes("-fullscreen", True)
        root.geometry("800x480")
    except Exception:
        root.geometry("1024x600")

    screen = ModernHome(root, state, storage, logger, scale, camera)
    screen.pack(fill="both", expand=True)

    # inicia lectura
    try:
        if hasattr(scale, "start"):
            scale.start()
    except Exception as e:
        logger.error(f"No se pudo iniciar lecturas: {e}")
        try:
            messagebox.showerror("HX711", f"No se pudo iniciar la lectura de peso:\n{e}")
        except Exception:
            pass

    # guardado seguro de calibración al salir
    def _on_close():
        try:
            base = None; fac = None
            for name in ("offset", "base_offset"):
                if hasattr(scale, name):
                    try:
                        base = float(getattr(scale, name))
                        break
                    except Exception:
                        pass
            for name in ("scale_factor", "calibration_scale"):
                if hasattr(scale, name):
                    try:
                        fac = float(getattr(scale, name))
                        break
                    except Exception:
                        pass
            if base is not None and fac is not None:
                _save_calibration(base, fac)
        finally:
            try:
                if hasattr(scale, "stop"): scale.stop()
                if hasattr(camera, "close"): camera.close()
            finally:
                root.destroy()

    root.protocol("WM_DELETE_WINDOW", _on_close)
    root.mainloop()
