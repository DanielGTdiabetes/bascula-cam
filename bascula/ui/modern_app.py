"""Modern simple UI for Bascula Pro with better layout for 7" screens.

This module avoids non-ASCII labels to prevent encoding issues on RPi.
"""

# -*- coding: utf-8 -*-
import tkinter as tk
from tkinter import messagebox, simpledialog
from bascula.ui.keyboard import NumericKeyboard

from bascula.state import AppState
from bascula.config.settings import load_config, save_config
from bascula.services.logging import get_logger
from bascula.services.scale import ScaleService
from bascula.services.food import FoodService

REFRESH_MS = 120


class Theme:
    PRIMARY = "#3B82F6"
    SUCCESS = "#06D6A0"
    WARNING = "#FFB347"
    DANGER = "#FF6B6B"
    INFO = "#4ECDC4"
    BG = "#1E293B"
    CARD = "#475569"
    CARD_LIGHT = "#64748B"
    TXT = "#F1F5F9"
    TXT_MUTED = "#CBD5E1"


class Card(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent, bg=Theme.CARD, bd=2, relief="ridge", padx=12, pady=12)


class BigButton(tk.Button):
    def __init__(self, parent, text, cmd, color, width_chars=14):
        super().__init__(
            parent,
            text=text,
            command=cmd,
            bg=color,
            fg=Theme.TXT,
            activebackground=color,
            font=("Segoe UI", 14, "bold"),
            bd=0,
            relief="flat",
            padx=16,
            pady=12,
            cursor="hand2",
            width=width_chars,
        )
        self.bind("<Enter>", lambda e: self.config(bg=Theme.CARD_LIGHT))
        self.bind("<Leave>", lambda e: self.config(bg=color))


class FoodPanel(Card):
    def __init__(self, parent):
        super().__init__(parent)
        tk.Label(self, text="Alimento detectado", font=("Segoe UI", 14, "bold"), bg=Theme.CARD, fg=Theme.TXT).pack(
            anchor="w"
        )
        self.name = tk.StringVar(value="-")
        self.tags = tk.StringVar(value="-")
        self.portion = tk.StringVar(value="-")
        self.kcal = tk.StringVar(value="-")
        self.macros = tk.StringVar(value="-")
        body = tk.Frame(self, bg=Theme.CARD)
        body.pack(fill="x", pady=(6, 0))
        tk.Label(body, textvariable=self.name, font=("Segoe UI", 18, "bold"), bg=Theme.CARD, fg=Theme.INFO).pack(
            anchor="w"
        )
        tk.Label(body, textvariable=self.tags, font=("Segoe UI", 10), bg=Theme.CARD, fg=Theme.TXT_MUTED).pack(
            anchor="w", pady=(2, 6)
        )
        tk.Label(body, text="Porcion", font=("Segoe UI", 11, "bold"), bg=Theme.CARD, fg=Theme.TXT).pack(anchor="w")
        tk.Label(body, textvariable=self.portion, font=("Segoe UI", 12), bg=Theme.CARD, fg=Theme.TXT).pack(anchor="w")
        tk.Label(body, text="Energia", font=("Segoe UI", 11, "bold"), bg=Theme.CARD, fg=Theme.TXT).pack(
            anchor="w", pady=(8, 0)
        )
        tk.Label(body, textvariable=self.kcal, font=("Segoe UI", 12), bg=Theme.CARD, fg=Theme.TXT).pack(anchor="w")
        tk.Label(body, text="Macronutrientes", font=("Segoe UI", 11, "bold"), bg=Theme.CARD, fg=Theme.TXT).pack(
            anchor="w", pady=(8, 0)
        )
        tk.Label(body, textvariable=self.macros, font=("Segoe UI", 12), bg=Theme.CARD, fg=Theme.TXT).pack(anchor="w")

    def set_food(self, d: dict):
        # d: {name, tags[], portion_g, per_portion{kcal,carbs,protein,fat}}
        self.name.set(d.get("name", "-"))
        self.tags.set(" · ".join(d.get("tags", [])) or "-")
        self.portion.set(f"{d.get('portion_g', 0.0):0.1f} g")
        pp = d.get("per_portion", {})
        self.kcal.set(f"{pp.get('kcal', 0):.0f} kcal")
        self.macros.set(
            f"C {pp.get('carbs', 0):.1f} g  ·  P {pp.get('protein', 0):.1f} g  ·  G {pp.get('fat', 0):.1f} g"
        )


def run_app():
    cfg = load_config()
    logger = get_logger("bascula", cfg.paths.log_dir, cfg.paths.log_file)
    state = AppState(cfg=cfg)
    scale = ScaleService(state, logger)
    food = FoodService()

    root = tk.Tk()
    root.title("Bascula Pro · UI moderna")
    root.configure(bg=Theme.BG)
    try:
        root.geometry("1100x650")
    except Exception:
        pass
    root.protocol("WM_DELETE_WINDOW", root.destroy)

    # HEADER
    header = Card(root)
    header.pack(fill="x", padx=16, pady=16)
    tk.Label(header, text="Bascula Pro", font=("Segoe UI", 22, "bold"), bg=Theme.CARD, fg=Theme.TXT).pack(side="left")
    backend_var = tk.StringVar(value=f"backend: {scale.get_backend_name()}  pins: {scale.get_pins()}")
    tk.Label(header, textvariable=backend_var, font=("Segoe UI", 10), bg=Theme.CARD, fg=Theme.TXT_MUTED).pack(
        side="right"
    )

    # BODY layout: left (weight + buttons) / right (food panel)
    body = tk.Frame(root, bg=Theme.BG)
    body.pack(fill="both", expand=True, padx=16, pady=(0, 16))
    left = tk.Frame(body, bg=Theme.BG)
    left.pack(side="left", fill="both", expand=True, padx=(0, 8))
    right = tk.Frame(body, bg=Theme.BG)
    right.pack(side="right", fill="y", padx=(8, 0))

    # WEIGHT CARD
    wcard = Card(left)
    wcard.pack(fill="both", expand=True)
    weight_var = tk.StringVar(value="0.0 g")
    status_var = tk.StringVar(value="Iniciando...")
    raw_var = tk.StringVar(value="RAW: -   FAST: -   SPAN: -")
    weight_lbl = tk.Label(wcard, textvariable=weight_var, font=("Segoe UI", 72, "bold"), bg=Theme.CARD, fg=Theme.SUCCESS)
    weight_lbl.pack(pady=(12, 6))
    tk.Label(wcard, textvariable=status_var, font=("Segoe UI", 12, "bold"), bg=Theme.CARD, fg=Theme.WARNING).pack()
    tk.Label(wcard, textvariable=raw_var, font=("Consolas", 10), bg=Theme.CARD, fg=Theme.TXT_MUTED).pack(pady=(8, 12))

    # BUTTONS
    bcard = Card(left)
    bcard.pack(fill="x", pady=(12, 0))

    # Two rows to fit small screens
    row1 = tk.Frame(bcard, bg=Theme.CARD)
    row1.pack(fill="x", pady=(0, 6))
    row2 = tk.Frame(bcard, bg=Theme.CARD)
    row2.pack(fill="x")

    BigButton(row1, "TARA", lambda: scale.tare(), Theme.SUCCESS).pack(side="left", padx=6)
    BigButton(row1, "CALIBRAR", lambda: on_calibrate(root, scale, state), Theme.WARNING).pack(side="left", padx=6)
    BigButton(row1, "GUARDAR", lambda: on_save(scale, state), Theme.PRIMARY).pack(side="left", padx=6)
    BigButton(row1, "RESET", lambda: scale.reset(), Theme.INFO).pack(side="left", padx=6)

    BigButton(row2, "PLATO UNICO", lambda: on_single_plate(root), Theme.INFO, width_chars=16).pack(side="left", padx=6)
    BigButton(row2, "ANADIR ALIMENTO", lambda: on_add_item(root), Theme.PRIMARY, width_chars=18).pack(side="left", padx=6)
    BigButton(row2, "SALIR", root.destroy, Theme.DANGER, width_chars=10).pack(side="right", padx=6)

    zero_auto = tk.BooleanVar(value=cfg.filters.zero_tracking)
    chk = tk.Checkbutton(
        bcard,
        text="ZERO AUTO",
        variable=zero_auto,
        bg=Theme.CARD,
        fg=Theme.TXT,
        activebackground=Theme.CARD,
        activeforeground=Theme.TXT,
        selectcolor=Theme.CARD,
        command=lambda: scale.filter.set_zero_tracking(zero_auto.get()),
    )
    chk.pack(side="left", padx=12)

    def tick():
        try:
            fast, stable, info, raw = scale.read()
            weight_var.set(f"{stable:0.1f} g")
            status_var.set("ESTABLE" if info.is_stable else "Midiendo...")
            # update weight color
            wcolor = Theme.TXT if abs(stable) < 1.0 else (Theme.DANGER if stable < 0 else Theme.SUCCESS)
            weight_lbl.config(fg=wcolor)
            raw_var.set(f"RAW: {raw}   FAST: {fast:0.1f} g   SPAN: {info.span_window:0.2f} g")
        except Exception as e:
            status_var.set(f"ERR: {e}")
        finally:
            root.after(REFRESH_MS, tick)

    tick()
    root.mainloop()


def on_save(scale: ScaleService, state: AppState):
    try:
        state.cfg.hardware.reference_unit = scale._reference_unit
        state.cfg.hardware.offset_raw = scale._offset_raw
        # persist detected pins too
        try:
            dout, sck = scale.get_pins()
            state.cfg.hardware.hx711_dout_pin = int(dout)
            state.cfg.hardware.hx711_sck_pin = int(sck)
        except Exception:
            pass
        save_config(state.cfg)
        messagebox.showinfo("Guardar", "Configuracion guardada en ~/.bascula/config.json")
    except Exception as e:
        messagebox.showerror("Guardar", str(e))


def on_calibrate(root, scale: ScaleService, state: AppState):
    try:
        # Prefer on-screen numeric keyboard for touch devices
        kb = NumericKeyboard(root, title="Peso patron (g)", initial="")
        root.wait_window(kb)
        w = None
        if kb.result is not None:
            try:
                w = float(kb.result)
            except Exception:
                w = None
        # Fallback to simple dialog if needed
        if not w:
            w = simpledialog.askfloat(
                "Calibracion", "Peso patron en gramos:", minvalue=1.0, maxvalue=100000.0, parent=root
            )
        if not w:
            return
        new_ref = scale.calibrate_with_known_weight(known_weight_g=float(w), settle_ms=1200)
        state.cfg.hardware.reference_unit = new_ref
        save_config(state.cfg)
        messagebox.showinfo("Calibracion", f"reference_unit = {new_ref:.8f}\nGuardado en config.")
    except Exception as e:
        messagebox.showerror("Calibracion", str(e))


def on_single_plate(root):
    from tkinter import messagebox

    messagebox.showinfo("Plato unico", "Funcion pendiente: consolidar en una sola entrada.")


def on_add_item(root):
    from tkinter import messagebox

    messagebox.showinfo("Anadir alimento", "Funcion pendiente: se anadira un nuevo alimento al plato actual.")
