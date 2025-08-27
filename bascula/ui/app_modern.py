import tkinter as tk
from tkinter import messagebox

# Core config/state/services expected in your project
from bascula.config.settings import load_config
from bascula.services.logging import get_logger
from bascula.services.storage import Storage
from bascula.state import AppState
from bascula.services.scale import ScaleService
from bascula.services.camera import CameraService

# Modern UI
from bascula.ui.extras.modern_home import ModernHome

def run_app_modern():
    cfg = load_config()
    logger = get_logger(cfg.base_dir)
    storage = Storage(cfg.base_dir)
    state = AppState(cfg=cfg)

    # Init services
    scale = ScaleService(state, logger)
    camera = CameraService(state, logger, storage)

    # Tk main window
    root = tk.Tk()
    root.title("⚖️ SMART SCALE PRO (Modern)")
    root.configure(highlightthickness=0)

    # Try fullscreen for touch kiosk; fallback to a reasonable size if fails
    try:
        root.attributes("-fullscreen", True)
        root.geometry("800x480")
    except Exception:
        root.geometry("1024x600")

    # Build Modern Home screen
    screen = ModernHome(root, state, storage, logger, scale, camera)
    screen.pack(fill="both", expand=True)

    # Start scale loop after window is shown
    try:
        scale.start()
    except Exception as e:
        logger.error(f"Error starting scale: {e}")
        try:
            messagebox.showerror("HX711", f"No se pudo iniciar la lectura de peso:\n{e}")
        except Exception:
            pass

    # Safe close
    def on_close():
        try:
            scale.stop()
            camera.close()
        except Exception:
            pass
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_close)
    root.mainloop()
