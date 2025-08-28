# -*- coding: utf-8 -*-
import tkinter as tk
from tkinter import ttk
from bascula.state import AppState
from bascula.config.settings import load_config
from bascula.services.logging import get_logger
from bascula.services.scale import ScaleService

REFRESH_MS = 200

def run_app():
    cfg = load_config()
    logger = get_logger("bascula", cfg.paths.log_dir, cfg.paths.log_file)
    state = AppState(cfg=cfg)

    root = tk.Tk()
    root.title("Báscula Pro")
    root.geometry("420x260")

    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except Exception:
        pass

    frame = ttk.Frame(root, padding=12)
    frame.pack(fill="both", expand=True)

    lbl_title = ttk.Label(frame, text="Peso", font=("Arial", 16))
    lbl_title.pack(anchor="center", pady=(0, 8))

    weight_var = tk.StringVar(value="0.0 g")
    stable_var = tk.StringVar(value="—")

    lbl_weight = ttk.Label(frame, textvariable=weight_var, font=("Arial", 40, "bold"))
    lbl_weight.pack(anchor="center", pady=4)

    lbl_stable = ttk.Label(frame, textvariable=stable_var, font=("Arial", 12))
    lbl_stable.pack(anchor="center", pady=(0, 8))

    btns = ttk.Frame(frame)
    btns.pack(anchor="center", pady=8)

    def on_tare():
        scale.tare()

    def on_reset():
        scale.reset()

    def on_exit():
        state.running = False
        root.destroy()

    btn_tare = ttk.Button(btns, text="TARA", command=on_tare)
    btn_reset = ttk.Button(btns, text="RESET", command=on_reset)
    btn_exit = ttk.Button(btns, text="SALIR", command=on_exit)

    btn_tare.grid(row=0, column=0, padx=6)
    btn_reset.grid(row=0, column=1, padx=6)
    btn_exit.grid(row=0, column=2, padx=6)

    # Inicializar ScaleService después de crear logger/UI
    scale = ScaleService(state, logger)

    def tick():
        if not state.running:
            return
        try:
            _fast, stable, info = scale.read()
            weight_var.set(f"{stable:0.1f} g")
            stable_var.set("ESTABLE ✓" if info.is_stable else f"Inestable (span={info.span_window:0.2f})")
        except Exception as e:
            weight_var.set("ERR")
            stable_var.set(str(e))
        finally:
            root.after(REFRESH_MS, tick)

    tick()
    root.mainloop()
