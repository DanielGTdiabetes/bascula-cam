# -*- coding: utf-8 -*-
import tkinter as tk
from tkinter import messagebox
import threading

from bascula.state import AppState
from bascula.config.settings import load_config, save_config
from bascula.services.logging import get_logger
from bascula.services.scale import ScaleService

REFRESH_MS = 80  # refresco rápido y fluido
MAX_DELTA_PER_TICK = 2.0  # g: límite de cambio visual por tick (slew-limit)

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
        super().__init__(parent, text=text, command=cmd, bg=color, fg=Theme.TXT, activebackground=color,
                         font=("Segoe UI", 14, "bold"), bd=0, relief="flat", padx=16, pady=12, cursor="hand2",
                         width=width_chars)
        self._base_color = color
        self.bind("<Enter>", lambda e: self.config(bg=Theme.CARD_LIGHT))
        self.bind("<Leave>", lambda e: self.config(bg=self._base_color))

# --- Teclado numérico en pantalla ---
class NumPad(tk.Toplevel):
    def __init__(self, parent, title="Introducir valor", unit="g", initial=""):
        super().__init__(parent)
        self.title(title)
        self.configure(bg=Theme.BG)
        self.resizable(False, False)
        self.value = tk.StringVar(value=str(initial))
        w = self.winfo_screenwidth(); h = self.winfo_screenheight()
        self.geometry(f"+{int(w*0.35)}+{int(h*0.35)}")
        body = Card(self); body.pack(fill="both", expand=True, padx=12, pady=12)
        entry = tk.Entry(body, textvariable=self.value, font=("Segoe UI", 20), justify="right")
        entry.pack(fill="x", pady=6)
        grid = tk.Frame(body, bg=Theme.CARD); grid.pack()
        keys = ["7","8","9","4","5","6","1","2","3","0",".","⌫"]
        def press(ch):
            if ch == "⌫":
                self.value.set(self.value.get()[:-1])
            else:
                self.value.set(self.value.get() + ch)
        r=c=0
        for k in keys:
            tk.Button(grid, text=k, command=lambda x=k: press(x),
                      font=("Segoe UI", 18, "bold"), width=4, bg=Theme.PRIMARY, fg=Theme.TXT,
                      bd=0, relief="flat", activebackground=Theme.CARD_LIGHT).grid(row=r, column=c, padx=4, pady=4)
            c += 1
            if c == 3:
                r += 1; c = 0
        bottom = tk.Frame(body, bg=Theme.CARD); bottom.pack(fill="x", pady=(8,0))
        tk.Label(bottom, text=f"Unidad: {unit}", bg=Theme.CARD, fg=Theme.TXT_MUTED).pack(side="left")
        tk.Button(bottom, text="OK", command=self.destroy, font=("Segoe UI", 14, "bold"),
                  bg=Theme.SUCCESS, fg="#1E293B", bd=0, relief="flat", padx=16, pady=8).pack(side="right")

def run_app():
    cfg = load_config()
    logger = get_logger("bascula", cfg.paths.log_dir, cfg.paths.log_file)
    try:
        logger.setLevel("WARNING")
    except Exception:
        pass

    state = AppState(cfg=cfg)
    scale = ScaleService(state, logger)  # hilo lector interno

    root = tk.Tk()
    root.title("Báscula Pro — UI moderna")
    root.configure(bg=Theme.BG)
    try:
        root.geometry("1100x650")
    except Exception:
        pass

    def on_close():
        try:
            scale.stop_reader()
        except Exception:
            pass
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_close)

    # HEADER
    header = Card(root); header.pack(fill="x", padx=16, pady=16)
    tk.Label(header, text="⚖️ Báscula Pro", font=("Segoe UI", 22, "bold"),
             bg=Theme.CARD, fg=Theme.TXT).pack(side="left")
    backend_var = tk.StringVar(value=f"backend: {scale.get_backend_name()}")
    tk.Label(header, textvariable=backend_var, font=("Segoe UI", 10),
             bg=Theme.CARD, fg=Theme.TXT_MUTED).pack(side="right")

    # BODY
    body = tk.Frame(root, bg=Theme.BG); body.pack(fill="both", expand=True, padx=16, pady=(0,16))
    left = tk.Frame(body, bg=Theme.BG); left.pack(side="left", fill="both", expand=True, padx=(0,8))

    # WEIGHT CARD
    wcard = Card(left); wcard.pack(fill="both", expand=True)
    weight_var = tk.StringVar(value="0.0 g")
    status_var = tk.StringVar(value="Iniciando…")
    raw_var = tk.StringVar(value="RAW: —  FAST: —  STD: —")
    weight_lbl = tk.Label(wcard, textvariable=weight_var, font=("Segoe UI", 72, "bold"),
             bg=Theme.CARD, fg=Theme.SUCCESS)
    weight_lbl.pack(pady=(12,6))
    tk.Label(wcard, textvariable=status_var, font=("Segoe UI", 12, "bold"),
             bg=Theme.CARD, fg=Theme.WARNING).pack()
    tk.Label(wcard, textvariable=raw_var, font=("Consolas", 10),
             bg=Theme.CARD, fg=Theme.TXT_MUTED).pack(pady=(8,12))

    # BUTTONS
    bcard = Card(left); bcard.pack(fill="x", pady=(12,0))
    BigButton(bcard, "🔄 TARA", lambda: scale.tare(), Theme.SUCCESS).pack(side="left", padx=6)
    BigButton(bcard, "📐 CALIBRAR", lambda: on_calibrate(root, scale, state), Theme.WARNING).pack(side="left", padx=6)
    BigButton(bcard, "💾 GUARDAR", lambda: on_save(scale, state), Theme.PRIMARY).pack(side="left", padx=6)
    BigButton(bcard, "♻ RESET", lambda: scale.reset(), Theme.INFO).pack(side="left", padx=6)
    BigButton(bcard, "🍽️ PLATO ÚNICO", lambda: on_single_plate(root), Theme.INFO).pack(side="right", padx=6)
    BigButton(bcard, "➕ AÑADIR ALIMENTO", lambda: on_add_item(root), Theme.PRIMARY).pack(side="right", padx=6)
    BigButton(bcard, "🚪 SALIR", on_close, Theme.DANGER).pack(side="right", padx=6)

    # Slew-limit visual (para evitar saltos)
    prev_shown = {"v": 0.0}
    def smooth_to(target: float) -> float:
        v = prev_shown["v"]
        delta = target - v
        if abs(delta) > MAX_DELTA_PER_TICK:
            v += MAX_DELTA_PER_TICK if delta > 0 else -MAX_DELTA_PER_TICK
        else:
            v = target
        prev_shown["v"] = v
        return v

    # LOOP UI (pinta; la lectura va en hilo)
    def tick():
        try:
            fast, display, info, raw = scale.peek()
            shown = smooth_to(display)
            weight_var.set(f"{shown:0.1f} g")
            status_var.set("ESTABLE ✓" if info.is_stable else "Midiendo…")
            color = Theme.TXT if abs(shown) < 1.0 else (Theme.DANGER if shown < 0 else Theme.SUCCESS)
            weight_lbl.config(fg=color)
            std_show = info.std_window if info.std_window != float("inf") else -1.0
            raw_var.set(f"RAW: {raw}   FAST: {fast:0.1f} g   STD: {std_show:0.3f}")
        finally:
            root.after(REFRESH_MS, tick)
    tick()

    root.mainloop()

def on_save(scale: ScaleService, state: AppState):
    try:
        state.cfg.hardware.reference_unit = scale._reference_unit
        state.cfg.hardware.offset_raw = scale._offset_raw
        save_config(state.cfg)
        messagebox.showinfo("Guardar", "Configuración guardada en ~/.bascula/config.json")
    except Exception as e:
        messagebox.showerror("Guardar", str(e))

def on_calibrate(root, scale: ScaleService, state: AppState):
    try:
        pad = NumPad(root, title="Calibración (peso patrón)", unit="g", initial="")
        pad.grab_set(); pad.wait_window()
        txt = pad.value.get().strip()
        if not txt:
            return
        known = float(txt.replace(",", "."))
        if known <= 0:
            messagebox.showwarning("Calibración", "El peso debe ser positivo")
            return
        def job():
            try:
                new_ref = scale.calibrate_with_known_weight(known_weight_g=known, settle_ms=1000)
                state.cfg.hardware.reference_unit = new_ref
                save_config(state.cfg)
                root.after(0, lambda: messagebox.showinfo("Calibración", f"reference_unit = {new_ref:.8f}\nGuardado en config."))
            except Exception as e:
                root.after(0, lambda: messagebox.showerror("Calibración", str(e)))
        threading.Thread(target=job, daemon=True).start()
    except ValueError:
        messagebox.showerror("Calibración", "Valor inválido")
    except Exception as e:
        messagebox.showerror("Calibración", str(e))

def on_single_plate(root):
    messagebox.showinfo("Plato único", "Pendiente de implementar consolidación del plato.")

def on_add_item(root):
    messagebox.showinfo("Añadir alimento", "Pendiente de implementar añadir alimento.")
