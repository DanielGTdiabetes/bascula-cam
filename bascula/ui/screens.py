# -*- coding: utf-8 -*-
import tkinter as tk

from bascula.ui.widgets import (
    Card, CardTitle, BigButton, GhostButton, WeightLabel, Toast, NumericKeypad,
    COL_BG, COL_CARD, COL_TEXT, COL_MUTED, COL_SUCCESS, COL_WARN, FS_TEXT
)

class BaseScreen(tk.Frame):
    def __init__(self, parent, app, **kwargs):
        super().__init__(parent, bg=COL_BG, **kwargs)
        self.app = app
    def on_show(self): pass

class HomeScreen(BaseScreen):
    """
    Pantalla principal a base de 'cartas' (espacios):
      ┌─────────────── Peso (ancho completo) ───────────────┐
      ├───────────────┬───────────────┤
      │    Salida     │    Cámara     │
      └───────────────┴───────────────┘
    """
    def __init__(self, parent, app, on_open_settings):
        super().__init__(parent, app)
        self.on_open_settings = on_open_settings

        # Grid 2 columnas, 2 filas
        self.grid_columnconfigure(0, weight=1, uniform="cols")
        self.grid_columnconfigure(1, weight=1, uniform="cols")
        self.grid_rowconfigure(0, weight=3, uniform="rows")
        self.grid_rowconfigure(1, weight=2, uniform="rows")

        # ── Carta: Peso ─────────────────────────────────────
        self.card_weight = Card(self)
        self.card_weight.grid(row=0, column=0, columnspan=2, sticky="nsew", padx=10, pady=10)
        tk.Label(self.card_weight, text="Peso actual", bg=COL_CARD, fg=COL_MUTED,
                 font=("DejaVu Sans", 20)).pack(anchor="w")
        self.weight_lbl = WeightLabel(self.card_weight)
        self.weight_lbl.pack(expand=True)

        # Botón de Tara y Ajustes dentro de esta carta (alineados abajo)
        btns = tk.Frame(self.card_weight, bg=COL_CARD)
        btns.pack(fill="x", pady=(8, 0))
        BigButton(btns, text="Tara", command=self._on_tara, small=True).pack(side="left")
        GhostButton(btns, text="Ajustes", command=self.on_open_settings, small=True).pack(side="right")

        # ── Carta: Salida (texto) ──────────────────────────
        self.card_out = Card(self)
        self.card_out.grid(row=1, column=0, sticky="nsew", padx=10, pady=10)
        CardTitle(self.card_out, "Salida").pack(anchor="w")
        self.txt_out = tk.Text(self.card_out, height=6, wrap="word",
                               bg="#0b0f14", fg=COL_TEXT,
                               insertbackground=COL_TEXT,
                               font=("DejaVu Sans", FS_TEXT),
                               relief="flat")
        self.txt_out.pack(fill="both", expand=True, pady=(8, 0))
        self._append_out("Sistema listo.")

        # ── Carta: Cámara (placeholder) ─────────────────────
        self.card_cam = Card(self)
        self.card_cam.grid(row=1, column=1, sticky="nsew", padx=10, pady=10)
        CardTitle(self.card_cam, "Cámara").pack(anchor="w")
        self.lbl_cam = tk.Label(self.card_cam, text="(Vista de cámara pendiente)",
                                bg=COL_CARD, fg=COL_MUTED,
                                font=("DejaVu Sans", FS_TEXT))
        self.lbl_cam.pack(expand=True, fill="both", pady=(8,0))

        # Toast
        self.toast = Toast(self)

        # Estado
        self._raw_actual = None
        self.after(50, self._tick)

    def _append_out(self, text: str):
        self.txt_out.insert("end", text + "\n")
        self.txt_out.see("end")

    def _fmt(self, grams: float) -> str:
        cfg = self.app.get_cfg()
        unit = cfg.get("unit", "g")
        decimals = max(0, int(cfg.get("decimals", 0)))
        if unit == "kg":
            val = grams / 1000.0
            return f"{val:.{decimals}f} kg"
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
            self._append_out(f"[Home] tick error: {e}")
            self.after(150, self._tick)

    def _on_tara(self):
        if self._raw_actual is None:
            self.toast.show("Sin lectura", ms=1200)
            self._append_out("Tara: sin lectura.")
            return
        self.app.get_tare().set_tare(self._raw_actual)
        self.toast.show("Tara realizada", ms=1200, color=COL_SUCCESS)
        self._append_out("Tara realizada.")

class SettingsScreen(BaseScreen):
    """
    Ajustes con cartas **sin pop-ups**:
    - Calibración con teclado en pantalla (compacto, cabe en 1024x600).
    - Preferencias (unidad, suavizado, decimales).
    Diseño **apilado** (una columna) para asegurar que todo cabe.
    """
    def __init__(self, parent, app, on_back):
        super().__init__(parent, app)
        self.on_back = on_back

        # Header
        header = tk.Frame(self, bg=COL_BG)
        header.pack(side="top", fill="x", pady=(10, 0))
        tk.Label(header, text="Ajustes", bg=COL_BG, fg=COL_TEXT,
                 font=("DejaVu Sans", 26, "bold")).pack(side="left", padx=14)
        GhostButton(header, text="Volver", command=self.on_back, small=True).pack(side="right", padx=14)

        # Body apilado
        body = tk.Frame(self, bg=COL_BG)
        body.pack(side="top", fill="both", expand=True, pady=(6, 10))

        # ---------- Carta Calibración ----------
        calib = Card(body)
        calib.pack(fill="both", expand=True, padx=10, pady=10)

        CardTitle(calib, "Calibración").pack(anchor="w")
        tk.Label(calib, text="1) Captura 'Cero' sin peso.  2) Introduce el peso patrón.\n"
                             "3) Coloca patrón y captura con peso.  4) Guardar factor.",
                 bg=COL_CARD, fg=COL_TEXT, font=("DejaVu Sans", 14),
                 justify="left").pack(anchor="w", pady=(6, 8))

        # Lectura actual
        self.lbl_live = tk.Label(calib, text="Lectura actual: —",
                                 bg=COL_CARD, fg=COL_MUTED, font=("DejaVu Sans", 16))
        self.lbl_live.pack(anchor="w", pady=(0, 6))

        # Cero / Con peso
        row_vals = tk.Frame(calib, bg=COL_CARD); row_vals.pack(fill="x", pady=(0, 6))
        self._bruto0 = None
        self._brutoW = None
        self.lbl_b0 = tk.Label(row_vals, text="Cero: —", bg=COL_CARD, fg=COL_TEXT, font=("DejaVu Sans", 16))
        self.lbl_bw = tk.Label(row_vals, text="Con patrón: —", bg=COL_CARD, fg=COL_TEXT, font=("DejaVu Sans", 16))
        self.lbl_b0.pack(side="left")
        self.lbl_bw.pack(side="right")

        # Botones capturar
        row_cap = tk.Frame(calib, bg=COL_CARD); row_cap.pack(fill="x", pady=(0, 8))
        GhostButton(row_cap, text="Capturar Cero", command=self._cap_cero, small=True).pack(side="left", padx=(0, 8))
        GhostButton(row_cap, text="Capturar con patrón", command=self._cap_con_peso, small=True).pack(side="left")

        # Peso patrón + keypad compacto
        tk.Label(calib, text="Peso patrón (según unidad actual):", bg=COL_CARD, fg=COL_TEXT,
                 font=("DejaVu Sans", 16)).pack(anchor="w", pady=(6, 4))
        self._peso_var = tk.StringVar(value="")
        pad = NumericKeypad(calib, self._peso_var, on_ok=None, on_clear=None,
                            allow_dot=True, variant="compact")
        pad.pack(fill="x")

        # Guardar factor
        BigButton(calib, text="Calcular y Guardar", command=self._calc_save, small=True).pack(fill="x", pady=(10, 0))

        # ---------- Carta Preferencias ----------
        prefs = Card(body)
        prefs.pack(fill="x", padx=10, pady=10)
        CardTitle(prefs, "Preferencias").pack(anchor="w")

        # Unidad
        row_u = tk.Frame(prefs, bg=COL_CARD); row_u.pack(anchor="w", pady=(8,6), fill="x")
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
        row_s = tk.Frame(prefs, bg=COL_CARD); row_s.pack(anchor="w", pady=(8,6), fill="x")
        tk.Label(row_s, text="Suavizado (muestras):", bg=COL_CARD, fg=COL_TEXT,
                 font=("DejaVu Sans", 16)).pack(side="left")
        self._smooth_var = tk.IntVar(value=int(self.app.get_cfg().get("smoothing",5)))
        ent_s = tk.Entry(row_s, textvariable=self._smooth_var, width=4,
                         bg="#0b0f14", fg=COL_TEXT, insertbackground=COL_TEXT,
                         font=("DejaVu Sans", 16), relief="flat")
        ent_s.pack(side="left", padx=(10,0))
        GhostButton(prefs, text="Guardar", command=self._save_smoothing, small=True).pack(anchor="e", pady=(6,0))

        # Decimales
        row_d = tk.Frame(prefs, bg=COL_CARD); row_d.pack(anchor="w", pady=(8,6), fill="x")
        tk.Label(row_d, text="Decimales:", bg=COL_CARD, fg=COL_TEXT,
                 font=("DejaVu Sans", 16)).pack(side="left")
        self._dec_var = tk.IntVar(value=int(self.app.get_cfg().get("decimals",0)))
        ent_d = tk.Entry(row_d, textvariable=self._dec_var, width=3,
                         bg="#0b0f14", fg=COL_TEXT, insertbackground=COL_TEXT,
                         font=("DejaVu Sans", 16), relief="flat")
        ent_d.pack(side="left", padx=(10,0))
        GhostButton(prefs, text="Guardar", command=self._save_decimals, small=True).pack(anchor="e", pady=(6,0))

        # Toast
        self.toast = Toast(self)

        # loop de actualización de “Lectura actual”
        self.after(120, self._tick_live)

    def on_show(self):
        self._unit_var.set(self.app.get_cfg().get("unit","g"))
        self._smooth_var.set(int(self.app.get_cfg().get("smoothing",5)))
        self._dec_var.set(int(self.app.get_cfg().get("decimals",0)))

    # ---------- Live preview lectura bruta ----------
    def _tick_live(self):
        try:
            reader = self.app.get_reader()
            if reader is not None:
                val = reader.get_latest()
                if val is not None:
                    self.lbl_live.config(text=f"Lectura actual: {val:.3f}")
        finally:
            self.after(120, self._tick_live)

    # ---------- Preferencias ----------
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
            self.toast.show("Valor inválido en suavizado", ms=1600, color=COL_WARN)

    def _save_decimals(self):
        try:
            d = int(self._dec_var.get())
            if d < 0: raise ValueError
            self.app.get_cfg()["decimals"] = d
            self.app.save_cfg()
            self.toast.show("Decimales guardados", ms=1200, color=COL_SUCCESS)
        except Exception:
            self.toast.show("Valor inválido en decimales", ms=1600, color=COL_WARN)

    # ---------- Calibración ----------
    def _promedio(self, n=10):
        reader = self.app.get_reader()
        vals = []
        for _ in range(n):
            v = reader.get_latest() if reader else None
            if v is not None:
                vals.append(v)
            self.update()
            self.after(35)
        if not vals:
            return None
        return sum(vals) / len(vals)

    def _cap_cero(self):
        v = self._promedio(10)
        if v is None:
            self.toast.show("Sin lectura estable", ms=1400)
            return
        self._bruto0 = v
        self.lbl_b0.config(text=f"Cero: {v:.3f}")

    def _cap_con_peso(self):
        v = self._promedio(12)
        if v is None:
            self.toast.show("Sin lectura con patrón", ms=1400)
            return
        self._brutoW = v
        self.lbl_bw.config(text=f"Con patrón: {v:.3f}")

    def _parse_peso_patron(self):
        s = (self._peso_var.get() or "").strip().replace(",", ".")
        try:
            w = float(s)
            if w <= 0: return None
            unit = self.app.get_cfg().get("unit", "g")
            return w if unit == "g" else (w * 1000.0)
        except Exception:
            return None

    def _calc_save(self):
        if self._bruto0 is None:
            self.toast.show("Falta 'Cero'", ms=1500, color=COL_WARN)
            return
        if self._brutoW is None:
            self.toast.show("Falta 'Con patrón'", ms=1500, color=COL_WARN)
            return
        Wg = self._parse_peso_patron()
        if Wg is None:
            self.toast.show("Peso patrón inválido", ms=1500, color=COL_WARN)
            return
        delta = self._brutoW - self._bruto0
        if abs(delta) < 1e-9:
            self.toast.show("Delta demasiado pequeño", ms=1500, color=COL_WARN)
            return
        factor = Wg / delta
        try:
            self.app.get_tare().update_calib(factor)
            self.app.get_cfg()["calib_factor"] = factor
            self.app.save_cfg()
            self.toast.show("Calibración guardada", ms=1400, color=COL_SUCCESS)
            self.after(1200, self.on_back)
        except Exception as e:
            self.toast.show(f"Error: {e}", ms=1800, color=COL_WARN)
