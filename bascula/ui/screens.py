# -*- coding: utf-8 -*-
import tkinter as tk
from tkinter import ttk

from bascula.ui.widgets import (
    Card, CardTitle, BigButton, GhostButton, WeightLabel, Toast, NumericKeypad,
    StatusIndicator, ScrollFrame,
    COL_BG, COL_CARD, COL_TEXT, COL_MUTED, COL_SUCCESS,
    COL_WARN, COL_DANGER, COL_ACCENT, COL_ACCENT_LIGHT, COL_BORDER,
    FS_TEXT, FS_TITLE, FS_CARD_TITLE, auto_apply_scaling
)

class BaseScreen(tk.Frame):
    def __init__(self, parent, app, **kwargs):
        super().__init__(parent, bg=COL_BG, **kwargs)
        self.app = app
        # 👇 Escalado automático a la resolución real (1024x600 o 1024x800)
        #    Se aplica una sola vez en todo el proceso.
        try:
            auto_apply_scaling(self, target=(1024, 600))
        except Exception:
            pass

    def on_show(self): pass


class HomeScreen(BaseScreen):
    """
    Pantalla principal con diseño moderno y elegante.
    Incluye indicadores visuales de estado y preparación para información nutricional.
    """
    def __init__(self, parent, app, on_open_settings):
        super().__init__(parent, app)
        self.on_open_settings = on_open_settings

        # Hacer que la pantalla ocupe todo el espacio disponible del root
        self.grid_columnconfigure(0, weight=1, uniform="cols")
        self.grid_columnconfigure(1, weight=1, uniform="cols")
        self.grid_rowconfigure(0, weight=3, uniform="rows")
        self.grid_rowconfigure(1, weight=2, uniform="rows")

        # ══════════════ Carta: Peso (con diseño premium) ══════════════
        self.card_weight = Card(self)
        self.card_weight.grid(row=0, column=0, columnspan=2, sticky="nsew", padx=10, pady=10)

        # Header con título e indicador de estado
        header_weight = tk.Frame(self.card_weight, bg=COL_CARD)
        header_weight.pack(fill="x", pady=(0, 6))

        title_frame = tk.Frame(header_weight, bg=COL_CARD)
        title_frame.pack(side="left")
        tk.Label(title_frame, text="Peso actual", bg=COL_CARD, fg=COL_ACCENT,
                 font=("DejaVu Sans", 20, "bold")).pack(side="left")

        # Indicador de estado de conexión
        self.status_indicator = StatusIndicator(header_weight, size=14)
        self.status_indicator.pack(side="left", padx=(10, 0))
        self.status_indicator.set_status("active")

        # Línea decorativa
        tk.Frame(self.card_weight, bg=COL_ACCENT, height=2).pack(fill="x", pady=(0, 8))

        # Display del peso con marco elegante
        weight_frame = tk.Frame(self.card_weight, bg="#1a1f2e", highlightbackground=COL_BORDER,
                                highlightthickness=1, relief="flat")
        weight_frame.pack(expand=True, fill="both", padx=6, pady=6)

        self.weight_lbl = WeightLabel(weight_frame)
        self.weight_lbl.configure(bg="#1a1f2e")
        self.weight_lbl.pack(expand=True, fill="both")

        # Indicador de estabilidad
        self.stability_frame = tk.Frame(weight_frame, bg="#1a1f2e")
        self.stability_frame.pack(side="bottom", pady=(0, 6))
        self.stability_label = tk.Label(self.stability_frame, text="● Estable",
                                        bg="#1a1f2e", fg=COL_SUCCESS,
                                        font=("DejaVu Sans", 12))
        self.stability_label.pack()

        # Botones con nuevo diseño
        btns = tk.Frame(self.card_weight, bg=COL_CARD)
        btns.pack(fill="x", pady=(8, 0))

        BigButton(btns, text="⚖ Tara", command=self._on_tara, micro=True).pack(side="left", padx=(0, 6))
        GhostButton(btns, text="⚙ Ajustes", command=self.on_open_settings, micro=True).pack(side="right")

        # ══════════════ Carta: Información Nutricional ══════════════
        self.card_nutrition = Card(self)
        self.card_nutrition.grid(row=1, column=0, sticky="nsew", padx=10, pady=10)

        # Header con título decorativo
        header_nut = tk.Frame(self.card_nutrition, bg=COL_CARD)
        header_nut.pack(fill="x", pady=(0, 6))
        tk.Label(header_nut, text="🥗 Información Nutricional", bg=COL_CARD, fg=COL_ACCENT,
                 font=("DejaVu Sans", FS_CARD_TITLE, "bold")).pack(side="left")
        tk.Frame(self.card_nutrition, bg=COL_ACCENT, height=1).pack(fill="x", pady=(0, 6))

        # Panel de nutrientes con diseño moderno
        self.nutrients_frame = tk.Frame(self.card_nutrition, bg=COL_CARD)
        self.nutrients_frame.pack(fill="both", expand=True)

        # Placeholder con estilo
        placeholder_frame = tk.Frame(self.nutrients_frame, bg="#1a1f2e",
                                     highlightbackground=COL_BORDER,
                                     highlightthickness=1, relief="flat")
        placeholder_frame.pack(fill="both", expand=True, padx=4, pady=4)

        tk.Label(placeholder_frame, text="📸 Captura pendiente",
                 bg="#1a1f2e", fg=COL_MUTED,
                 font=("DejaVu Sans", 14)).pack(expand=True)

        # Preparación para futuros datos nutricionales
        self.nutrition_data = {
            "calories": "—",
            "carbs": "—",
            "protein": "—",
            "fat": "—"
        }

        # ══════════════ Carta: Cámara con vista previa ══════════════
        self.card_cam = Card(self)
        self.card_cam.grid(row=1, column=1, sticky="nsew", padx=10, pady=10)

        # Header con título e indicador
        header_cam = tk.Frame(self.card_cam, bg=COL_CARD)
        header_cam.pack(fill="x", pady=(0, 6))
        tk.Label(header_cam, text="📷 Vista de Cámara", bg=COL_CARD, fg=COL_ACCENT,
                 font=("DejaVu Sans", FS_CARD_TITLE, "bold")).pack(side="left")

        self.cam_status = StatusIndicator(header_cam, size=12)
        self.cam_status.pack(side="left", padx=(8, 0))
        self.cam_status.set_status("inactive")

        tk.Frame(self.card_cam, bg=COL_ACCENT, height=1).pack(fill="x", pady=(0, 6))

        # Área de vista previa con borde elegante
        cam_preview = tk.Frame(self.card_cam, bg="#1a1f2e",
                               highlightbackground=COL_BORDER,
                               highlightthickness=1, relief="flat")
        cam_preview.pack(fill="both", expand=True, padx=4, pady=4)

        self.lbl_cam = tk.Label(cam_preview, text="🎥 Cámara inactiva",
                                bg="#1a1f2e", fg=COL_MUTED,
                                font=("DejaVu Sans", 14))
        self.lbl_cam.pack(expand=True, fill="both")

        # Botón de captura (preparado para el futuro)
        btn_capture = BigButton(self.card_cam, text="📸 Capturar",
                                command=self._on_capture, micro=True)
        btn_capture.pack(fill="x", pady=(6, 0))

        # Toast mejorado
        self.toast = Toast(self)

        # Estado de lectura
        self._raw_actual = None
        self._stable = False
        self.after(80, self._tick)

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
            updated = False

            if reader is not None:
                val = reader.get_latest()
                if val is not None:
                    self._raw_actual = val
                    sm = smoother.add(val)
                    net = tare.compute_net(sm)

                    # Actualizar peso con animación
                    self.weight_lbl.config(text=self._fmt(net))

                    # Actualizar indicador de estabilidad con color
                    if abs(net - getattr(self, '_last_stable_weight', 0)) < 2.0:
                        if not self._stable:
                            self._stable = True
                            self.stability_label.config(text="● Estable", fg=COL_SUCCESS)
                    else:
                        if self._stable:
                            self._stable = False
                            self.stability_label.config(text="◉ Midiendo...", fg=COL_WARN)

                    self._last_stable_weight = net
                    self.status_indicator.set_status("active")
                    updated = True

            if not updated:
                if self._raw_actual is None:
                    self.weight_lbl.config(text="0 g")
                    self.status_indicator.set_status("inactive")
                    self.stability_label.config(text="○ Sin señal", fg=COL_MUTED)

            self.after(80, self._tick)
        except Exception:
            self.after(150, self._tick)

    def _on_tara(self):
        if self._raw_actual is None:
            self.toast.show("⚠ Sin lectura disponible", ms=1200, color=COL_WARN)
            return
        self.app.get_tare().set_tare(self._raw_actual)
        self.toast.show("✓ Tara realizada correctamente", ms=1200, color=COL_SUCCESS)

    def _on_capture(self):
        """Preparado para futura implementación de captura de cámara."""
        self.toast.show("📸 Función de cámara en desarrollo", ms=1500, color=COL_ACCENT)
        # Aquí se conectará la funcionalidad de cámara y análisis nutricional


class SettingsScreen(BaseScreen):
    """
    Pantalla de ajustes con diseño moderno y organizado.
    Con scroll real para que el teclado y secciones no se corten.
    """
    def __init__(self, parent, app, on_back):
        super().__init__(parent, app)
        self.on_back = on_back

        # Header elegante con gradiente simulado
        header = tk.Frame(self, bg=COL_BG)
        header.pack(side="top", fill="x", pady=(10, 0))

        # Título con icono
        title_frame = tk.Frame(header, bg=COL_BG)
        title_frame.pack(side="left", padx=14)
        tk.Label(title_frame, text="⚙", bg=COL_BG, fg=COL_ACCENT,
                 font=("DejaVu Sans", 26)).pack(side="left", padx=(0, 8))
        tk.Label(title_frame, text="Ajustes", bg=COL_BG, fg=COL_TEXT,
                 font=("DejaVu Sans", 24, "bold")).pack(side="left")

        GhostButton(header, text="← Volver", command=self.on_back, micro=True).pack(side="right", padx=14)

        # Línea decorativa
        separator = tk.Frame(self, bg=COL_ACCENT, height=2)
        separator.pack(fill="x", padx=14, pady=(6, 0))

        # Body con SCROLL REAL
        sc = ScrollFrame(self, bg=COL_BG)
        sc.pack(side="top", fill="both", expand=True, pady=(10, 8))
        body = sc.body  # Aquí añadimos el contenido

        # ══════════════ Sección: Calibración ══════════════
        calib = Card(body)
        calib.pack(fill="both", expand=True, padx=14, pady=8)

        # Título con icono
        title_calib = tk.Frame(calib, bg=COL_CARD)
        title_calib.pack(fill="x", pady=(0, 6))
        tk.Label(title_calib, text="⚖", bg=COL_CARD, fg=COL_ACCENT,
                 font=("DejaVu Sans", 18)).pack(side="left", padx=(0, 8))
        CardTitle(calib, "Calibración de Precisión").pack(side="left")

        tk.Frame(calib, bg=COL_ACCENT, height=1).pack(fill="x", pady=(6, 10))

        # Instrucciones con diseño mejorado
        instructions_frame = tk.Frame(calib, bg="#1a1f2e")
        instructions_frame.pack(fill="x", pady=(0, 10))

        steps = [
            ("1", "Captura el punto 'Cero' sin peso"),
            ("2", "Introduce el peso del patrón de calibración"),
            ("3", "Coloca el patrón y captura la lectura"),
            ("4", "Guarda la calibración")
        ]

        for num, text in steps:
            step_frame = tk.Frame(instructions_frame, bg="#1a1f2e")
            step_frame.pack(fill="x", padx=10, pady=3)
            tk.Label(step_frame, text=num, bg=COL_ACCENT, fg=COL_TEXT,
                     font=("DejaVu Sans", 12, "bold"), width=3, height=1).pack(side="left")
            tk.Label(step_frame, text=text, bg="#1a1f2e", fg=COL_TEXT,
                     font=("DejaVu Sans", 13), justify="left").pack(side="left", padx=(8, 0))

        # Monitor de lectura en vivo
        live_frame = tk.Frame(calib, bg="#1a1f2e", highlightbackground=COL_BORDER,
                              highlightthickness=1, relief="flat")
        live_frame.pack(fill="x", pady=(6, 10), padx=8)

        tk.Label(live_frame, text="📊", bg="#1a1f2e", fg=COL_ACCENT,
                 font=("DejaVu Sans", 16)).pack(side="left", padx=(10, 8))
        self.lbl_live = tk.Label(live_frame, text="Lectura actual: —",
                                 bg="#1a1f2e", fg=COL_TEXT, font=("DejaVu Sans", 15))
        self.lbl_live.pack(side="left", pady=6)

        # Valores capturados con diseño moderno
        row_vals = tk.Frame(calib, bg=COL_CARD)
        row_vals.pack(fill="x", pady=(0, 6))

        self._bruto0 = None
        self._brutoW = None

        # Frames para valores con bordes
        zero_frame = tk.Frame(row_vals, bg="#1a1f2e", highlightbackground=COL_BORDER,
                              highlightthickness=1, relief="flat")
        zero_frame.pack(side="left", expand=True, fill="x", padx=(0, 4))
        self.lbl_b0 = tk.Label(zero_frame, text="Cero: —", bg="#1a1f2e", fg=COL_TEXT,
                               font=("DejaVu Sans", 14), pady=5)
        self.lbl_b0.pack()

        pattern_frame = tk.Frame(row_vals, bg="#1a1f2e", highlightbackground=COL_BORDER,
                                 highlightthickness=1, relief="flat")
        pattern_frame.pack(side="right", expand=True, fill="x", padx=(4, 0))
        self.lbl_bw = tk.Label(pattern_frame, text="Con patrón: —", bg="#1a1f2e", fg=COL_TEXT,
                               font=("DejaVu Sans", 14), pady=5)
        self.lbl_bw.pack()

        # Botones de captura mejorados
        row_cap = tk.Frame(calib, bg=COL_CARD)
        row_cap.pack(fill="x", pady=(0, 10))
        GhostButton(row_cap, text="📍 Capturar Cero", command=self._cap_cero, micro=True).pack(side="left", padx=(0, 6))
        GhostButton(row_cap, text="📍 Capturar con patrón", command=self._cap_con_peso, micro=True).pack(side="left")

        # Entrada de peso patrón con estilo
        tk.Label(calib, text="Peso del patrón (según unidad configurada):", bg=COL_CARD, fg=COL_TEXT,
                 font=("DejaVu Sans", 14)).pack(anchor="w", pady=(6, 6))

        self._peso_var = tk.StringVar(value="")
        pad = NumericKeypad(calib, self._peso_var, on_ok=None, on_clear=None,
                            allow_dot=True, variant="ultracompact")
        pad.pack(fill="x", padx=8)

        BigButton(calib, text="💾 Calcular y Guardar Calibración", command=self._calc_save, micro=True).pack(fill="x", pady=(10, 0))

        # ══════════════ Sección: Preferencias ══════════════
        prefs = Card(body)
        prefs.pack(fill="x", padx=14, pady=8)

        # Título con icono
        title_prefs = tk.Frame(prefs, bg=COL_CARD)
        title_prefs.pack(fill="x", pady=(0, 6))
        tk.Label(title_prefs, text="🎨", bg=COL_CARD, fg=COL_ACCENT,
                 font=("DejaVu Sans", 18)).pack(side="left", padx=(0, 8))
        CardTitle(prefs, "Preferencias de Visualización").pack(side="left")

        tk.Frame(prefs, bg=COL_ACCENT, height=1).pack(fill="x", pady=(6, 10))

        # Unidad con radio buttons estilizados
        row_u = tk.Frame(prefs, bg=COL_CARD)
        row_u.pack(anchor="w", pady=(6, 10), fill="x")
        tk.Label(row_u, text="Unidad de medida:", bg=COL_CARD, fg=COL_TEXT,
                 font=("DejaVu Sans", 14, "bold")).pack(side="left")

        self._unit_var = tk.StringVar(value=self.app.get_cfg().get("unit","g"))
        unit_frame = tk.Frame(row_u, bg=COL_CARD)
        unit_frame.pack(side="left", padx=(14, 0))

        for txt, val in [("Gramos (g)", "g"), ("Kilogramos (kg)", "kg")]:
            rb = tk.Radiobutton(unit_frame, text=txt, variable=self._unit_var, value=val,
                                bg=COL_CARD, fg=COL_TEXT, selectcolor="#1a1f2e",
                                activebackground=COL_CARD, activeforeground=COL_ACCENT,
                                font=("DejaVu Sans", 13), command=self._save_unit)
            rb.pack(side="left", padx=(0, 12))

        # Suavizado con diseño moderno
        row_s = tk.Frame(prefs, bg=COL_CARD)
        row_s.pack(anchor="w", pady=(0, 10), fill="x")
        tk.Label(row_s, text="Suavizado (muestras):", bg=COL_CARD, fg=COL_TEXT,
                 font=("DejaVu Sans", 14, "bold")).pack(side="left")

        smooth_input_frame = tk.Frame(row_s, bg=COL_CARD)
        smooth_input_frame.pack(side="left", padx=(14, 0))

        self._smooth_var = tk.IntVar(value=int(self.app.get_cfg().get("smoothing",5)))
        ent_s = tk.Entry(smooth_input_frame, textvariable=self._smooth_var, width=6,
                         bg="#1a1f2e", fg=COL_TEXT, insertbackground=COL_ACCENT,
                         font=("DejaVu Sans", 14), relief="flat", bd=8,
                         highlightbackground=COL_BORDER, highlightthickness=1)
        ent_s.pack(side="left")

        GhostButton(row_s, text="Aplicar", command=self._save_smoothing, micro=True).pack(side="left", padx=(10, 0))

        # Decimales con diseño moderno
        row_d = tk.Frame(prefs, bg=COL_CARD)
        row_d.pack(anchor="w", pady=(0, 8), fill="x")
        tk.Label(row_d, text="Decimales mostrados:", bg=COL_CARD, fg=COL_TEXT,
                 font=("DejaVu Sans", 14, "bold")).pack(side="left")

        dec_input_frame = tk.Frame(row_d, bg=COL_CARD)
        dec_input_frame.pack(side="left", padx=(14, 0))

        self._dec_var = tk.IntVar(value=int(self.app.get_cfg().get("decimals",0)))
        ent_d = tk.Entry(dec_input_frame, textvariable=self._dec_var, width=4,
                         bg="#1a1f2e", fg=COL_TEXT, insertbackground=COL_ACCENT,
                         font=("DejaVu Sans", 14), relief="flat", bd=8,
                         highlightbackground=COL_BORDER, highlightthickness=1)
        ent_d.pack(side="left")

        GhostButton(row_d, text="Aplicar", command=self._save_decimals, micro=True).pack(side="left", padx=(10, 0))

        # Toast mejorado
        self.toast = Toast(self)

        self.after(120, self._tick_live)

    def on_show(self):
        self._unit_var.set(self.app.get_cfg().get("unit","g"))
        self._smooth_var.set(int(self.app.get_cfg().get("smoothing",5)))
        self._dec_var.set(int(self.app.get_cfg().get("decimals",0)))

    def _tick_live(self):
        try:
            reader = self.app.get_reader()
            if reader is not None:
                val = reader.get_latest()
                if val is not None:
                    self.lbl_live.config(text=f"Lectura actual: {val:.3f}")
        finally:
            self.after(120, self._tick_live)

    def _save_unit(self):
        self.app.get_cfg()["unit"] = self._unit_var.get()
        self.app.save_cfg()
        self.toast.show("✓ Unidad guardada", ms=1200, color=COL_SUCCESS)

    def _save_smoothing(self):
        try:
            n = int(self._smooth_var.get())
            if n < 1: raise ValueError
            self.app.get_cfg()["smoothing"] = n
            self.app.get_smoother().size = n
            self.app.save_cfg()
            self.toast.show("✓ Suavizado aplicado", ms=1200, color=COL_SUCCESS)
        except Exception:
            self.toast.show("⚠ Valor inválido", ms=1500, color=COL_WARN)

    def _save_decimals(self):
        try:
            d = int(self._dec_var.get())
            if d < 0: raise ValueError
            self.app.get_cfg()["decimals"] = d
            self.app.save_cfg()
            self.toast.show("✓ Decimales configurados", ms=1200, color=COL_SUCCESS)
        except Exception:
            self.toast.show("⚠ Valor inválido", ms=1500, color=COL_WARN)

    def _promedio(self, n=10):
        reader = self.app.get_reader()
        vals = []
        for _ in range(n):
            v = reader.get_latest() if reader else None
            if v is not None:
                vals.append(v)
            self.update()
            self.after(30)
        if not vals:
            return None
        return sum(vals) / len(vals)

    def _cap_cero(self):
        v = self._promedio(10)
        if v is None:
            self.toast.show("⚠ Sin lectura disponible", ms=1200, color=COL_WARN)
            return
        self._bruto0 = v
        self.lbl_b0.config(text=f"Cero: {v:.3f}")
        self.toast.show("✓ Cero capturado", ms=900, color=COL_SUCCESS)

    def _cap_con_peso(self):
        v = self._promedio(12)
        if v is None:
            self.toast.show("⚠ Sin lectura con patrón", ms=1200, color=COL_WARN)
            return
        self._brutoW = v
        self.lbl_bw.config(text=f"Con patrón: {v:.3f}")
        self.toast.show("✓ Patrón capturado", ms=900, color=COL_SUCCESS)

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
            self.toast.show("⚠ Falta capturar 'Cero'", ms=1200, color=COL_WARN)
            return
        if self._brutoW is None:
            self.toast.show("⚠ Falta capturar 'Con patrón'", ms=1200, color=COL_WARN)
            return
        Wg = self._parse_peso_patron()
        if Wg is None:
            self.toast.show("⚠ Peso patrón inválido", ms=1200, color=COL_WARN)
            return
        delta = self._brutoW - self._bruto0
        if abs(delta) < 1e-9:
            self.toast.show("⚠ Diferencia muy pequeña", ms=1200, color=COL_WARN)
            return
        factor = Wg / delta
        try:
            self.app.get_tare().update_calib(factor)
            self.app.get_cfg()["calib_factor"] = factor
            self.app.save_cfg()
            self.toast.show("✅ Calibración exitosa", ms=1500, color=COL_SUCCESS)
            self.after(1500, self.on_back)
        except Exception:
            self.toast.show("❌ Error al guardar", ms=1500, color=COL_DANGER)
