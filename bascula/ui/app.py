# -*- coding: utf-8 -*-
import tkinter as tk
from tkinter import ttk, simpledialog, messagebox
from bascula.state import AppState
from bascula.config.settings import load_config, save_config
from bascula.services.logging import get_logger
from bascula.services.scale import ScaleService

REFRESH_MS = 120

def run_app():
    cfg = load_config()
    logger = get_logger("bascula", cfg.paths.log_dir, cfg.paths.log_file)
    state = AppState(cfg=cfg)

    root = tk.Tk()
    root.title("Báscula Pro")
    root.geometry("600x380")
    root.minsize(500, 320)

    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except Exception:
        pass

    wrap = ttk.Frame(root, padding=12)
    wrap.pack(fill="both", expand=True)

    top = ttk.Frame(wrap)
    top.pack(fill="x", pady=(0, 8))

    lbl_title = ttk.Label(top, text="Lectura de Peso", font=("Arial", 16, "bold"))
    lbl_title.pack(side="left")

    backend_var = tk.StringVar(value="backend: —")
    lbl_backend = ttk.Label(top, textvariable=backend_var, font=("Arial", 10))
    lbl_backend.pack(side="right")

    weight_var = tk.StringVar(value="0.0 g")
    stable_var = tk.StringVar(value="—")
    raw_var = tk.StringVar(value="RAW: —")
    fast_var = tk.StringVar(value="FAST: —")
    span_var = tk.StringVar(value="SPAN: —")

    lbl_weight = ttk.Label(wrap, textvariable=weight_var, font=("Arial", 44, "bold"))
    lbl_weight.pack(anchor="center", pady=4)

    status = ttk.Frame(wrap)
    status.pack(fill="x", pady=(0,8))
    ttk.Label(status, textvariable=stable_var).pack(side="left")
    ttk.Label(status, textvariable=raw_var).pack(side="left", padx=12)
    ttk.Label(status, textvariable=fast_var).pack(side="left", padx=12)
    ttk.Label(status, textvariable=span_var).pack(side="left", padx=12)

    btns = ttk.Frame(wrap)
    btns.pack(anchor="center", pady=10)

    scale = ScaleService(state, logger)
    backend_var.set(f"backend: {scale.get_backend_name()}")

    def on_tare():
        try:
            scale.tare()
        except Exception as e:
            messagebox.showerror("Tara", str(e))

    def on_reset():
        try:
            scale.reset()
        except Exception as e:
            messagebox.showerror("Reset", str(e))

    zero_auto_var = tk.BooleanVar(value=cfg.filters.zero_tracking)

    def on_toggle_zero():
        try:
            z = bool(zero_auto_var.get())
            scale.filter.set_zero_tracking(z)
            state.cfg.filters.zero_tracking = z
        except Exception as e:
            messagebox.showerror("Zero Auto", str(e))

    def on_save():
        try:
            state.cfg.hardware.reference_unit = scale._reference_unit
            state.cfg.hardware.offset_raw = scale._offset_raw
            save_config(state.cfg)
            messagebox.showinfo("Guardar", "Configuración guardada en ~/.bascula/config.json")
        except Exception as e:
            messagebox.showerror("Guardar", str(e))

    def on_calibrate():
        try:
            w = simpledialog.askfloat("Calibración",
                                      "Introduce el peso patrón en gramos (ej. 500.0):",
                                      minvalue=1.0, maxvalue=100000.0)
            if not w:
                return
            new_ref = scale.calibrate_with_known_weight(known_weight_g=float(w))
            state.cfg.hardware.reference_unit = new_ref
            save_config(state.cfg)
            messagebox.showinfo("Calibración",
                                f"reference_unit actualizado a {new_ref:.8f}\nGuardado en config.")
        except Exception as e:
            messagebox.showerror("Calibración", str(e))

    def on_exit():
        state.running = False
        root.destroy()

    btn_tare = ttk.Button(btns, text="TARA", command=on_tare)
    btn_reset = ttk.Button(btns, text="RESET", command=on_reset)
    btn_calib = ttk.Button(btns, text="CALIBRAR", command=on_calibrate)
    btn_save = ttk.Button(btns, text="GUARDAR", command=on_save)
    btn_exit = ttk.Button(btns, text="SALIR", command=on_exit)

    btn_tare.grid(row=0, column=0, padx=6, pady=4)
    btn_reset.grid(row=0, column=1, padx=6, pady=4)
    btn_calib.grid(row=0, column=2, padx=6, pady=4)
    btn_save.grid(row=0, column=3, padx=6, pady=4)
    btn_exit.grid(row=0, column=4, padx=6, pady=4)

    zframe = ttk.Frame(wrap)
    zframe.pack(anchor="center", pady=(4, 0))
    zchk = ttk.Checkbutton(zframe, text="ZERO AUTO", variable=zero_auto_var, command=on_toggle_zero)
    zchk.pack()

    def tick():
        if not state.running:
            return
        try:
            fast, stable, info, raw = scale.read()
            weight_var.set(f"{stable:0.1f} g")
            stable_var.set("ESTABLE ✓" if info.is_stable else "Inestable")
            raw_var.set(f"RAW: {raw}")
            fast_var.set(f"FAST: {fast:0.1f} g")
            span_var.set(f"SPAN: {info.span_window:0.2f} g")
        except Exception as e:
            weight_var.set("ERR")
            stable_var.set(str(e))
        finally:
            root.after(REFRESH_MS, tick)

    tick()
    root.mainloop()
