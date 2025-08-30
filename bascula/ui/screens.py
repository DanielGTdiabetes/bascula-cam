# -*- coding: utf-8 -*-
import tkinter as tk
from tkinter import messagebox, simpledialog

from bascula.ui.widgets import (
    Card, BigButton, GhostButton, WeightLabel, Toast,
    COL_BG, COL_CARD, COL_TEXT, COL_MUTED, COL_SUCCESS
)

class BaseScreen(tk.Frame):
    def __init__(self, parent, app, **kwargs):
        super().__init__(parent, bg=COL_BG, **kwargs)
        self.app = app
    def on_show(self): pass

class HomeScreen(BaseScreen):
    """ Pantalla principal en cartas: Peso / Acciones / Navegación """
    def __init__(self, parent, app, on_open_settings):
        super().__init__(parent, app)
        self.on_open_settings = on_open_settings

        # Grid 2x2
        self.grid_columnconfigure(0, weight=1, uniform="cols")
        self.grid_columnconfigure(1, weight=1, uniform="cols")
        self.grid_rowconfigure(0, weight=3, uniform="rows")
        self.grid_rowconfigure(1, weight=2, uniform="rows")

        # Carta Peso
        self.card_weight = Card(self)
        self.card_weight.grid(row=0, column=0, columnspan=2, sticky="nsew", padx=12, pady=12)
        tk.Label(self.card_weight, text="Peso actual", bg=COL_CARD, fg=COL_MUTED,
                 font=("DejaVu Sans", 20)).pack(anchor="w")
        self.weight_lbl = WeightLabel(self.card_weight)
        self.weight_lbl.pack(expand=True)

        # Carta Acciones
        self.card_actions = Card(self)
        self.card_actions.grid(row=1, column=0, sticky="nsew", padx=12, pady=12)
        self.btn_tara = BigButton(self.card_actions, text="Tara", command=self._on_tara)
        self.btn_tara.pack(fill="x")

        # Carta Navegación
        self.card_nav = Card(self)
        self.card_nav.grid(row=1, column=1, sticky="nsew", padx=12, pady=12)
        self.btn_settings = BigButton(self.card_nav, text="Ajustes", command=self._on_settings)
        self.btn_settings.pack(fill="x")

        # Toast
        self.toast = Toast(self)

        self._raw_actual = None
        self.after(50, self._tick)

    def _fmt(self, grams: float) -> str:
        cfg = self.app.get_cfg()
        unit = cfg.get("unit", "g")
        decimals = max(0, int(cfg.get("decimals", 0)))
        if unit == "kg":
            val = grams / 1000.0
            return f"{val:.{decimals}f} kg"
        # gramos
        if decimals == 0:
            return f"{round(grams):.0f} g"
        return f"{grams:.{decimals}f} g"

    def _tick(self):
        try:
            reader = self.app.get_reader()
            smoother = self.app.get_smoother()
            tare = self.app.get_tare()
            if reader is not None:
                val = reader.get_latest()
                if val is not None:
                    self._raw_actual = val
                    sm = smoother.add(val)
                    net = tare.compute_net(sm)
                    self.weight_lbl.config(text=self._fmt(net))
            self.after(50, self._tick)
        except Exception as e:
            print(f"[Home] tick error: {e}", flush=True)
            self.after(150, self._tick)

    def _on_tara(self):
        if self._raw_actual is None:
            self.toast.show("Sin lectura", ms=1400)
            return
        self.app.get_tare().set_tare(self._raw_actual)
        self.toast.show("Tara realizada", ms=1400, color=COL_SUCCESS)

    def _on_settings(self):
        self.on_open_settings()

class SettingsScreen(BaseScreen):
    """ Ajustes: Calibración (único), Preferencias (unidad / suavizado / decimales) """
    def __init__(self, parent, app, on_back):
        super().__init__(parent, app)
        self.on_back = on_back

        # Header
        header = tk.Frame(self, bg=COL_BG)
        header.pack(side="top", fill="x", pady=(12, 0))
        tk.Label(header, text="Ajustes", bg=COL_BG, fg=COL_TEXT,
                 font=("DejaVu Sans", 28, "bold")).pack(side="left", padx=18)
        GhostButton(header, text="Volver", command=self.on_back).pack(side="right", padx=18)

        # Body (dos cartas)
        body = tk.Frame(self, bg=COL_BG)
        body.pack(side="top", fill="both", expand=True, pady=(6, 12))
        body.grid_columnconfigure(0, weight=1)
        body.grid_columnconfigure(1, weight=1)

        # Carta Calibración
        card_calib = Card(body)
        card_calib.grid(row=0, column=0, sticky="nsew", padx=12, pady=12)
        tk.Label(card_calib, text="Calibración", bg=COL_CARD, fg=COL_MUTED,
                 font=("DejaVu Sans", 18, "bold")).pack(anchor="w")
        tk.Label(card_calib, text="Usa un patrón conocido.", bg=COL_CARD, fg=COL_TEXT,
                 font=("DejaVu Sans", 16)).pack(anchor="w", pady=(6, 12))
        BigButton(card_calib, text="Calibrar", command=self._on_calibrate).pack(fill="x")

        # Carta Preferencias
        card_prefs = Card(body)
        card_prefs.grid(row=0, column=1, sticky="nsew", padx=12, pady=12)
        tk.Label(card_prefs, text="Preferencias", bg=COL_CARD, fg=COL_MUTED,
                 font=("DejaVu Sans", 18, "bold")).pack(anchor="w")

        # Unidad
        row_u = tk.Frame(card_prefs, bg=COL_CARD); row_u.pack(anchor="w", pady=(10,6), fill="x")
        tk.Label(row_u, text="Unidad:", bg=COL_CARD, fg=COL_TEXT,
                 font=("DejaVu Sans", 16)).pack(side="left")
        self._unit_var = tk.StringVar(value=self.app.get_cfg().get("unit","g"))
        for txt,val in [("g","g"),("kg","kg")]:
            rb = tk.Radiobutton(row_u, text=txt, variable=self._unit_var, value=val,
                                bg=COL_CARD, fg=COL_TEXT, selectcolor=COL_CARD,
                                activebackground=COL_CARD, font=("DejaVu Sans", 14),
                                command=self._save_unit)
            rb.pack(side="left", padx=(10,6))

        # Suavizado
        row_s = tk.Frame(card_prefs, bg=COL_CARD); row_s.pack(anchor="w", pady=(10,6), fill="x")
        tk.Label(row_s, text="Suavizado (muestras):", bg=COL_CARD, fg=COL_TEXT,
                 font=("DejaVu Sans", 16)).pack(side="left")
        self._smooth_var = tk.IntVar(value=int(self.app.get_cfg().get("smoothing",5)))
        ent_s = tk.Entry(row_s, textvariable=self._smooth_var, width=4,
                         bg="#0b0f14", fg=COL_TEXT, insertbackground=COL_TEXT,
                         font=("DejaVu Sans", 16), relief="flat")
        ent_s.pack(side="left", padx=(10,0))
        GhostButton(card_prefs, text="Guardar", command=self._save_smoothing).pack(anchor="e", pady=(12,0))

        # Decimales
        row_d = tk.Frame(card_prefs, bg=COL_CARD); row_d.pack(anchor="w", pady=(10,6), fill="x")
        tk.Label(row_d, text="Decimales:", bg=COL_CARD, fg=COL_TEXT,
                 font=("DejaVu Sans", 16)).pack(side="left")
        self._dec_var = tk.IntVar(value=int(self.app.get_cfg().get("decimals",0)))
        ent_d = tk.Entry(row_d, textvariable=self._dec_var, width=3,
                         bg="#0b0f14", fg=COL_TEXT, insertbackground=COL_TEXT,
                         font=("DejaVu Sans", 16), relief="flat")
        ent_d.pack(side="left", padx=(10,0))
        GhostButton(card_prefs, text="Guardar", command=self._save_decimals).pack(anchor="e", pady=(12,0))

        # Toast
        self.toast = Toast(self)

    def on_show(self):
        self._unit_var.set(self.app.get_cfg().get("unit","g"))
        self._smooth_var.set(int(self.app.get_cfg().get("smoothing",5)))
        self._dec_var.set(int(self.app.get_cfg().get("decimals",0)))

    def _save_unit(self):
        self.app.get_cfg()["unit"] = self._unit_var.get()
        self.app.save_cfg()
        self.toast.show("Unidad guardada", ms=1200, color=COL_SUCCESS)

    def _save_smoothing(self):
        try:
            n = int(self._smooth_var.get())
            if n < 1: raise ValueError
            self.app.get_cfg()["smoothing"] = n
            self.app.get_smoother().size = n
            self.app.save_cfg()
            self.toast.show("Suavizado guardado", ms=1200, color=COL_SUCCESS)
        except Exception:
            messagebox.showerror("Preferencias", "Valor inválido en suavizado.")

    def _save_decimals(self):
        try:
            d = int(self._dec_var.get())
            if d < 0: raise ValueError
            self.app.get_cfg()["decimals"] = d
            self.app.save_cfg()
            self.toast.show("Decimales guardados", ms=1200, color=COL_SUCCESS)
        except Exception:
            messagebox.showerror("Preferencias", "Valor inválido en decimales.")

    def _on_calibrate(self):
        reader = self.app.get_reader()
        if reader is None:
            messagebox.showerror("Calibración", "Lector serie no disponible.")
            return

        # punto 0
        bruto0 = self._promedio(reader, 10)
        if bruto0 is None:
            messagebox.showerror("Calibración", "Sin lectura estable.")
            return

        # peso patrón
        unidad = self.app.get_cfg().get("unit","g")
        prompt = "Peso patrón en gramos" if unidad == "g" else "Peso patrón en kilogramos"
        W = simpledialog.askfloat("Calibración", prompt, minvalue=0.001)
        if W is None: return
        if unidad == "kg": W *= 1000.0

        # con patrón
        brutoW = self._promedio(reader, 12)
        if brutoW is None or abs(brutoW - bruto0) < 1e-9:
            messagebox.showerror("Calibración", "Lectura con patrón inválida.")
            return

        factor = W / (brutoW - bruto0)
        try:
            self.app.get_tare().update_calib(factor)
            self.app.get_cfg()["calib_factor"] = factor
            self.app.save_cfg()
            self.toast.show("Calibración realizada", ms=1400, color=COL_SUCCESS)
            self.after(1500, self.on_back)
        except Exception as e:
            messagebox.showerror("Calibración", f"Error: {e}")

    def _promedio(self, reader, n=10):
        vals = []
        for _ in range(n):
            v = reader.get_latest()
            if v is not None:
                vals.append(v)
            self.update()
            self.after(50)
        if not vals:
            return None
        return sum(vals)/len(vals)
