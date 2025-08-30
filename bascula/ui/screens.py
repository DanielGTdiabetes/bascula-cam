# -*- coding: utf-8 -*-
import tkinter as tk
from tkinter import messagebox, simpledialog

from bascula.ui.widgets import (
    Card, BigButton, GhostButton, WeightLabel, Toast,
    COL_BG, COL_CARD, COL_TEXT, COL_MUTED, COL_SUCCESS
)


class BaseScreen(tk.Frame):
    """Clase base para pantallas con fondo consistente."""
    def __init__(self, parent, app, **kwargs):
        super().__init__(parent, bg=COL_BG, **kwargs)
        self.app = app

    def on_show(self):
        """Hook al entrar en pantalla."""
        pass


class HomeScreen(BaseScreen):
    """
    Pantalla principal con diseño tipo 'cartas':
    - Carta 1: Peso actual grande.
    - Carta 2: Acciones (Tara, Ajustes).
    * Ya NO hay calibración aquí. Va en Ajustes.
    """

    def __init__(self, parent, app, on_open_settings):
        super().__init__(parent, app)
        self.on_open_settings = on_open_settings

        # Layout responsivo simple con grid 2x2
        self.grid_columnconfigure(0, weight=1, uniform="cols")
        self.grid_columnconfigure(1, weight=1, uniform="cols")
        self.grid_rowconfigure(0, weight=3, uniform="rows")  # peso grande
        self.grid_rowconfigure(1, weight=2, uniform="rows")  # controles

        # ----- Carta de peso -----
        self.card_weight = Card(self)
        self.card_weight.grid(row=0, column=0, columnspan=2, sticky="nsew", padx=12, pady=12)

        self.title_lbl = tk.Label(self.card_weight, text="Peso actual", bg=COL_CARD, fg=COL_MUTED,
                                  font=("DejaVu Sans", 20))
        self.title_lbl.pack(anchor="w")

        self.weight_lbl = WeightLabel(self.card_weight)
        self.weight_lbl.pack(expand=True)

        # ----- Carta de acciones -----
        self.card_actions = Card(self)
        self.card_actions.grid(row=1, column=0, sticky="nsew", padx=12, pady=12)

        self.btn_tara = BigButton(self.card_actions, text="Tara", command=self._on_tara)
        self.btn_tara.pack(fill="x")

        # “informativos temporales” (toast)
        self.toast = Toast(self)

        # ----- Carta de navegación -----
        self.card_nav = Card(self)
        self.card_nav.grid(row=1, column=1, sticky="nsew", padx=12, pady=12)

        self.btn_settings = BigButton(self.card_nav, text="Ajustes", command=self._on_settings)
        self.btn_settings.pack(fill="x")

        # Estado
        self._raw_actual = None

        # Loop UI
        self.after(50, self._tick)

    def on_show(self):
        # Si hubiese que refrescar algo al entrar, aquí.
        pass

    def _fmt(self, value_g: float) -> str:
        cfg = self.app.get_cfg()
        if cfg.get("unit") == "kg":
            return f"{value_g/1000:.3f} kg"
        return f"{value_g:.2f} g"

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
            # reprograma
            self.after(50, self._tick)
        except Exception as e:
            print(f"[HomeScreen] Tick error: {e}", flush=True)
            self.after(150, self._tick)

    def _on_tara(self):
        if self._raw_actual is None:
            self.toast.show("Sin lectura. Intenta de nuevo.", ms=1800)
            return
        try:
            self.app.get_tare().set_tare(self._raw_actual)
            # Mensaje temporal (NO permanece)
            self.toast.show("Tara realizada", ms=1600, color=COL_SUCCESS)
        except Exception as e:
            messagebox.showerror("Tara", f"Error: {e}")

    def _on_settings(self):
        self.on_open_settings()


class SettingsScreen(BaseScreen):
    """
    Pantalla de Ajustes (menú). Aquí va la única entrada de “Calibrar”.
    Se mostrarán mensajes informativos temporales tras completar acciones.
    """

    def __init__(self, parent, app, on_back):
        super().__init__(parent, app)
        self.on_back = on_back

        # Layout
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=3)

        # Header
        header = tk.Frame(self, bg=COL_BG)
        header.grid(row=0, column=0, sticky="ew", pady=(12, 0))
        title = tk.Label(header, text="Ajustes", bg=COL_BG, fg=COL_TEXT,
                         font=("DejaVu Sans", 28, "bold"))
        title.pack(side="left", padx=18)

        back_btn = GhostButton(header, text="Volver", command=self.on_back)
        back_btn.pack(side="right", padx=18)

        # Zona de cartas
        body = tk.Frame(self, bg=COL_BG)
        body.grid(row=1, column=0, sticky="nsew", pady=(6, 12))
        body.grid_columnconfigure(0, weight=1)
        body.grid_columnconfigure(1, weight=1)
        body.grid_rowconfigure(0, weight=1)

        # Carta: Calibración (la única entrada)
        card_calib = Card(body)
        card_calib.grid(row=0, column=0, sticky="nsew", padx=12, pady=12)

        tk.Label(card_calib, text="Calibración", bg=COL_CARD, fg=COL_MUTED,
                 font=("DejaVu Sans", 18, "bold")).pack(anchor="w")

        tk.Label(card_calib, text="Ajusta el factor usando un peso patrón.",
                 bg=COL_CARD, fg=COL_TEXT, font=("DejaVu Sans", 16)).pack(anchor="w", pady=(6, 12))

        BigButton(card_calib, text="Calibrar", command=self._on_calibrate).pack(fill="x")

        # Carta: Preferencias (stub: unidad y suavizado)
        card_prefs = Card(body)
        card_prefs.grid(row=0, column=1, sticky="nsew", padx=12, pady=12)

        tk.Label(card_prefs, text="Preferencias", bg=COL_CARD, fg=COL_MUTED,
                 font=("DejaVu Sans", 18, "bold")).pack(anchor="w")

        # Unidad
        unit_frame = tk.Frame(card_prefs, bg=COL_CARD)
        unit_frame.pack(anchor="w", pady=(10, 6), fill="x")
        tk.Label(unit_frame, text="Unidad:", bg=COL_CARD, fg=COL_TEXT,
                 font=("DejaVu Sans", 16)).pack(side="left")
        self._unit_var = tk.StringVar(value=self.app.get_cfg().get("unit", "g"))
        unit_g = tk.Radiobutton(unit_frame, text="g", variable=self._unit_var, value="g",
                                bg=COL_CARD, fg=COL_TEXT, selectcolor=COL_CARD,
                                activebackground=COL_CARD, font=("DejaVu Sans", 14), command=self._save_unit)
        unit_kg = tk.Radiobutton(unit_frame, text="kg", variable=self._unit_var, value="kg",
                                 bg=COL_CARD, fg=COL_TEXT, selectcolor=COL_CARD,
                                 activebackground=COL_CARD, font=("DejaVu Sans", 14), command=self._save_unit)
        unit_g.pack(side="left", padx=(10, 6))
        unit_kg.pack(side="left", padx=(4, 0))

        # Suavizado
        smooth_frame = tk.Frame(card_prefs, bg=COL_CARD)
        smooth_frame.pack(anchor="w", pady=(10, 6), fill="x")
        tk.Label(smooth_frame, text="Suavizado (muestras):", bg=COL_CARD, fg=COL_TEXT,
                 font=("DejaVu Sans", 16)).pack(side="left")
        self._smooth_var = tk.IntVar(value=int(self.app.get_cfg().get("smoothing", 5)))
        smooth_entry = tk.Entry(smooth_frame, textvariable=self._smooth_var,
                                bg="#0b0f14", fg=COL_TEXT, insertbackground=COL_TEXT,
                                font=("DejaVu Sans", 16), width=4, relief="flat")
        smooth_entry.pack(side="left", padx=(10, 0))
        save_smooth = GhostButton(card_prefs, text="Guardar", command=self._save_smoothing)
        save_smooth.pack(anchor="e", pady=(12, 0))

        # Toast para mensajes temporales
        self.toast = Toast(self)

    def on_show(self):
        # Refresca valores por si cambiaron
        self._unit_var.set(self.app.get_cfg().get("unit", "g"))
        self._smooth_var.set(int(self.app.get_cfg().get("smoothing", 5)))

    def _save_unit(self):
        self.app.get_cfg()["unit"] = self._unit_var.get()
        self.app.save_cfg()
        self.toast.show("Unidad guardada", ms=1400, color=COL_SUCCESS)

    def _save_smoothing(self):
        try:
            n = int(self._smooth_var.get())
            if n < 1:
                raise ValueError
            self.app.get_cfg()["smoothing"] = n
            self.app.save_cfg()
            # también actualizar el objeto de suavizado actual
            self.app.get_smoother().size = n
            self.toast.show("Suavizado guardado", ms=1400, color=COL_SUCCESS)
        except Exception:
            messagebox.showerror("Preferencias", "Valor inválido para suavizado.")

    def _on_calibrate(self):
        """
        Calibración en 2 pasos:
        1) Toma lectura sin peso (bruto0)
        2) Pide peso patrón, toma lectura estabilizada (brutoW)
        factor = W / (brutoW - bruto0)
        Muestra “Calibración realizada” como TOAST temporal (no permanente).
        """
        reader = self.app.get_reader()
        if reader is None:
            messagebox.showerror("Calibración", "Lector serie no disponible.")
            return

        # 1) Punto cero
        bruto0 = self._promedio_rapido(reader, muestras=10)
        if bruto0 is None:
            messagebox.showerror("Calibración", "No hay lectura estable.")
            return

        # 2) Pide peso patrón
        unidad = self.app.get_cfg().get("unit", "g")
        prompt = "Peso patrón en gramos" if unidad == "g" else "Peso patrón en kilogramos"
        W = simpledialog.askfloat("Calibración", prompt, minvalue=0.001)
        if W is None:
            return
        if unidad == "kg":
            W = W * 1000.0

        # 3) Lectura con patrón
        brutoW = self._promedio_rapido(reader, muestras=12)
        if brutoW is None:
            messagebox.showerror("Calibración", "No hay lectura estable con el patrón.")
            return
        if abs(brutoW - bruto0) < 1e-9:
            messagebox.showerror("Calibración", "Delta bruto demasiado pequeño.")
            return

        factor = W / (brutoW - bruto0)
        try:
            self.app.get_tare().update_calib(factor)
            self.app.get_cfg()["calib_factor"] = factor
            self.app.save_cfg()
            # Mostrar mensaje temporal y volver
            self.toast.show("Calibración realizada", ms=1600, color=COL_SUCCESS)
            # volver a Home tras ~1.6 s
            self.after(1700, self.on_back)
        except Exception as e:
            messagebox.showerror("Calibración", f"Error: {e}")

    def _promedio_rapido(self, reader, muestras=10):
        vals = []
        for _ in range(muestras):
            v = reader.get_latest()
            if v is not None:
                vals.append(v)
            self.update()
            self.after(50)
        if not vals:
            return None
        return sum(vals)/len(vals)
