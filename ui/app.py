import tkinter as tk
from bascula.config.settings import load_config, save_config
from bascula.config.theme import THEME
from bascula.state import AppState
from bascula.services.logging import get_logger
from bascula.services.storage import Storage
from bascula.services.scale import ScaleService
from bascula.services.camera import CameraService
from bascula.ui.screens import HomeScreen

def run_app():
    cfg = load_config()
    root = tk.Tk()
    root.title("⚖️ Báscula Digital Pro")
    if cfg.ui.fullscreen:
        root.attributes("-fullscreen", True)
    else:
        root.geometry("1024x768")
    root.configure(bg=THEME.background)

    storage = Storage(cfg.base_dir)
    logger = get_logger(cfg.base_dir)
    state = AppState(cfg=cfg)

    scale = ScaleService(state, logger)
    camera = CameraService(state, logger, storage)

    screen = HomeScreen(root, state, storage, logger, scale, camera)
    screen.pack(fill="both", expand=True)

    scale.start()

    def on_close():
        try:
            scale.stop()
            camera.close()
            save_config(cfg)
        finally:
            root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_close)
    root.mainloop()
