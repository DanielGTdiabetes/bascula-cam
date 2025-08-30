# -*- coding: utf-8 -*-
# bascula/ui/screens.py - VERSIÓN REDISEÑADA
import tkinter as tk
from tkinter import ttk

from bascula.ui.widgets import (
    Card, CardTitle, BigButton, GhostButton, WeightLabel, Toast, NumericKeypad,
    StatusIndicator, ScrollFrame,
    COL_BG, COL_CARD, COL_TEXT, COL_MUTED, COL_SUCCESS,
    COL_WARN, COL_DANGER, COL_ACCENT, COL_ACCENT_LIGHT, COL_BORDER,
    FS_TEXT, FS_TITLE, FS_CARD_TITLE, get_scaled_size
)

class BaseScreen(tk.Frame):
    def __init__(self, parent, app, **kwargs):
        super().__init__(parent, bg=COL_BG, **kwargs)
        self.app = app
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

    def on_show(self): 
        pass
        
    def on_hide(self):
        pass

class HomeScreen(BaseScreen):
    """
    Pantalla principal con más espacio para Cámara e Información Nutricional.
    Diseño a dos columnas: izquierda (peso) a toda altura; derecha (cámara arriba, nutrición abajo).
    """
    def __init__(self, parent, app, on_open_settings_menu):
        super().__init__(parent, app)
        self.on_open_settings_menu = on_open_settings_menu

        # Grid principal: 2 columnas
        self.grid_columnconfigure(0, weight=3, uniform="cols")  # Peso (más ancho)
        self.grid_columnconfigure(1, weight=2, uniform="cols")  # Panel derecho (cámara+nutrición)
        self.grid_rowconfigure(0, weight=1)

        # ── Columna izquierda: Carta de Peso (ocupa toda la altura)
        self.card_weight = Card(self, min_width=700, min_height=400)
        self.card_weight.grid(row=0, column=0, sticky="nsew", 
                              padx=get_scaled_size(10), pady=get_scaled_size(10))

        header_weight = tk.Frame(self.card_weight, bg=COL_CARD)
        header_weight.pack(fill="x", pady=(0, get_scaled_size(6)))

        title_frame = tk.Frame(header_weight, bg=COL_CARD)
        title_frame.pack(side="left")
        
        peso_title = tk.Label(title_frame, text="Peso actual ●", bg=COL_CARD, fg=COL_ACCENT,
                              font=("DejaVu Sans", FS_TITLE, "bold"))
        peso_title.pack(side="left")

        self.status_indicator = StatusIndicator(header_weight, size=16)
        self.status_indicator.pack(side="left", padx=(get_scaled_size(10), 0))
        self.status_indicator.set_status("active")

        separator = tk.Frame(self.card_weight, bg=COL_ACCENT, height=2)
        separator.pack(fill="x", pady=(0, get_scaled_size(8)))

        weight_frame = tk.Frame(self.card_weight, bg="#1a1f2e", 
                                highlightbackground=COL_BORDER,
                                highlightthickness=1, relief="flat")
        weight_frame.pack(expand=True, fill="both", 
                          padx=get_scaled_size(6), pady=get_scaled_size(6))

        self.weight_lbl = WeightLabel(weight_frame)
        self.weight_lbl.configure(bg="#1a1f2e")
        self.weight_lbl.pack(expand=True, fill="both")

        # Indicador de estabilidad
        self.stability_frame = tk.Frame(weight_frame, bg="#1a1f2e")
        self.stability_frame.pack(side="bottom", pady=(0, get_scaled_size(6)))
        self.stability_label = tk.Label(self.stability_frame, text="● Estable",
                                        bg="#1a1f2e", fg=COL_SUCCESS,
                                        font=("DejaVu Sans", FS_TEXT))
        self.stability_label.pack()

        # Botonera unificada
        btns = tk.Frame(self.card_weight, bg=COL_CARD)
        btns.pack(fill="x", pady=(get_scaled_size(8), 0))
        for c in range(4):
            btns.columnconfigure(c, weight=1, uniform="btns_row")

        btn_specs = [
            ("⚖ Tara", self._on_tara),
            ("🍽 Plato único", self._on_single_plate),
            ("➕ Añadir alimento", self._on_add_item),
            ("⚙ Ajustes", self.on_open_settings_menu),
        ]
        for i, (txt, cmd) in enumerate(btn_specs):
            BigButton(btns, text=txt, command=cmd, micro=True).grid(
                row=0, column=i, sticky="nsew",
                padx=(get_scaled_size(4), get_scaled_size(4)),
                pady=(0, get_scaled_size(4))
            )

        # ── Columna derecha: frame con 2 filas (Cámara arriba, Nutrición abajo)
        right = tk.Frame(self, bg=COL_BG)
        right.grid(row=0, column=1, sticky="nsew", padx=(0, get_scaled_size(10)), pady=get_scaled_size(10))
        right.grid_rowconfigure(0, weight=3, uniform="right_rows")  # Cámara más alta
        right.grid_rowconfigure(1, weight=2, uniform="right_rows")  # Nutrición
        right.grid_columnconfigure(0, weight=1)

        # Cámara (más grande)
        self.card_cam = Card(right, min_width=300, min_height=260)
        self.card_cam.grid(row=0, column=0, sticky="nsew",
                           padx=get_scaled_size(0), pady=get_scaled_size(0))

        header_cam = tk.Frame(self.card_cam, bg=COL_CARD)
        header_cam.pack(fill="x", pady=(0, get_scaled_size(6)))
        
        cam_title = tk.Label(header_cam, text="📷 Vista de Cámara", 
                             bg=COL_CARD, fg=COL_ACCENT,
                             font=("DejaVu Sans", FS_CARD_TITLE, "bold"))
        cam_title.pack(side="left")

        self.cam_status = StatusIndicator(header_cam, size=12)
        self.cam_status.pack(side="left", padx=(get_scaled_size(8), 0))
        self.cam_status.set_status("inactive")

        separator_cam = tk.Frame(self.card_cam, bg=COL_ACCENT, height=1)
        separator_cam.pack(fill="x", pady=(0, get_scaled_size(6)))

        cam_preview = tk.Frame(self.card_cam, bg="#1a1f2e",
                               highlightbackground=COL_BORDER,
                               highlightthickness=1, relief="flat")
        cam_preview.pack(fill="both", expand=True, 
                         padx=get_scaled_size(4), pady=get_scaled_size(4))

        self.lbl_cam = tk.Label(cam_preview, text="🎥 Cámara inactiva",
                                bg="#1a1f2e", fg=COL_MUTED,
                                font=("DejaVu Sans", FS_TEXT))
        self.lbl_cam.pack(expand=True, fill="both")

        btn_capture = BigButton(self.card_cam, text="📸 Capturar",
                                command=self._on_capture, micro=True)
        btn_capture.pack(fill="x", pady=(get_scaled_size(6), 0))

        # Nutrición (más grande que antes)
        self.card_nutrition = Card(right, min_width=300, min_height=200)
        self.card_nutrition.grid(row=1, column=0, sticky="nsew",
                                 padx=get_scaled_size(0), pady=(get_scaled_size(10), 0))

        header_nut = tk.Frame(self.card_nutrition, bg=COL_CARD)
        header_nut.pack(fill="x", pady=(0, get_scaled_size(6)))
        
        nutrition_title = tk.Label(header_nut, text="🥗 Información Nutricional", 
                                   bg=COL_CARD, fg=COL_ACCENT,
                                   font=("DejaVu Sans", FS_CARD_TITLE, "bold"))
        nutrition_title.pack(side="left")
        
        separator_nut = tk.Frame(self.card_nutrition, bg=COL_ACCENT, height=1)
        separator_nut.pack(fill="x", pady=(0, get_scaled_size(6)))

        self.nutrients_frame = tk.Frame(self.card_nutrition, bg=COL_CARD)
        self.nutrients_frame.pack(fill="both", expand=True)

        placeholder_frame = tk.Frame(self.nutrients_frame, bg="#1a1f2e",
                                     highlightbackground=COL_BORDER,
                                     highlightthickness=1, relief="flat")
        placeholder_frame.pack(fill="both", expand=True, 
                               padx=get_scaled_size(4), pady=get_scaled_size(4))

        placeholder_label = tk.Label(placeholder_frame, text="📸 Captura pendiente",
                                     bg="#1a1f2e", fg=COL_MUTED,
                                     font=("DejaVu Sans", FS_TEXT))
        placeholder_label.pack(expand=True)

        self.nutrition_data = {
            "calories": "—",
            "carbs": "—", 
            "protein": "—",
            "fat": "—"
        }

        self.toast = Toast(self)

        # Estado de lectura (solo una vez)
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

                    self.weight_lbl.config(text=self._fmt(net))

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

    def _on_single_plate(self):
        self.toast.show("🍽 Modo 'Plato único' (pendiente)", ms=1100, color=COL_ACCENT)

    def _on_add_item(self):
        self.toast.show("➕ Añadir alimento (pendiente)", ms=1100, color=COL_ACCENT)

    def _on_capture(self):
        self.toast.show("📸 Función de cámara en desarrollo", ms=1500, color=COL_ACCENT)


class SettingsMenuScreen(BaseScreen):
    """
    Menú de Ajustes: navegación a Calibración, Wi-Fi, API Key y otros.
    """
    def __init__(self, parent, app):
        super().__init__(parent, app)

        # Header
        header = tk.Frame(self, bg=COL_BG)
        header.pack(side="top", fill="x", pady=(get_scaled_size(10), 0))

        title_frame = tk.Frame(header, bg=COL_BG)
        title_frame.pack(side="left", padx=get_scaled_size(14))
        
        icon_label = tk.Label(title_frame, text="⚙", bg=COL_BG, fg=COL_ACCENT,
                              font=("DejaVu Sans", int(FS_TITLE * 1.4)))
        icon_label.pack(side="left", padx=(0, get_scaled_size(8)))
        
        title_label = tk.Label(title_frame, text="Ajustes", bg=COL_BG, fg=COL_TEXT,
                               font=("DejaVu Sans", FS_TITLE, "bold"))
        title_label.pack(side="left")

        GhostButton(header, text="← Volver", command=lambda: self.app.show_screen('home'), micro=True).pack(
            side="right", padx=get_scaled_size(14))

        separator = tk.Frame(self, bg=COL_ACCENT, height=2)
        separator.pack(fill="x", padx=get_scaled_size(14), pady=(get_scaled_size(6), 0))

        # Cuerpo con botones grandes
        container = Card(self, min_height=400)
        container.pack(fill="both", expand=True, padx=get_scaled_size(14), pady=get_scaled_size(10))

        grid = tk.Frame(container, bg=COL_CARD)
        grid.pack(expand=True)

        # 2x2 grid de opciones
        for r in range(2):
            grid.grid_rowconfigure(r, weight=1, uniform="menu")
        for c in range(2):
            grid.grid_columnconfigure(c, weight=1, uniform="menu")

        BigButton(grid, text="⚖ Calibración", command=lambda: self.app.show_screen('calib'), small=True).grid(
            row=0, column=0, sticky="nsew", padx=get_scaled_size(6), pady=get_scaled_size(6))

        BigButton(grid, text="📶 Conexión Wi-Fi", command=lambda: self.app.show_screen('wifi'), small=True).grid(
            row=0, column=1, sticky="nsew", padx=get_scaled_size(6), pady=get_scaled_size(6))

        BigButton(grid, text="🗝 API Key ChatGPT", command=lambda: self.app.show_screen('apikey'), small=True).grid(
            row=1, column=0, sticky="nsew", padx=get_scaled_size(6), pady=get_scaled_size(6))

        BigButton(grid, text="➕ Otros (próximamente)", command=lambda: self._coming_soon(), small=True).grid(
            row=1, column=1, sticky="nsew", padx=get_scaled_size(6), pady=get_scaled_size(6))

        self.toast = Toast(self)

    def _coming_soon(self):
        self.toast.show("Próximamente…", ms=900, color=COL_MUTED)


class CalibScreen(BaseScreen):
    """
    Pantalla de Calibración con teclado visible (scroll si hace falta).
    """
    def __init__(self, parent, app):
        super().__init__(parent, app)

        header = tk.Frame(self, bg=COL_BG)
        header.pack(side="top", fill="x", pady=(get_scaled_size(10), 0))

        title_frame = tk.Frame(header, bg=COL_BG)
        title_frame.pack(side="left", padx=get_scaled_size(14))
        
        icon_label = tk.Label(title_frame, text="⚖", bg=COL_BG, fg=COL_ACCENT,
                              font=("DejaVu Sans", int(FS_TITLE * 1.4)))
        icon_label.pack(side="left", padx=(0, get_scaled_size(8)))
        
        title_label = tk.Label(title_frame, text="Calibración", bg=COL_BG, fg=COL_TEXT,
                               font=("DejaVu Sans", FS_TITLE, "bold"))
        title_label.pack(side="left")

        GhostButton(header, text="← Ajustes", command=lambda: self.app.show_screen('settings_menu'), micro=True).pack(
            side="right", padx=get_scaled_size(14))

        separator = tk.Frame(self, bg=COL_ACCENT, height=2)
        separator.pack(fill="x", padx=get_scaled_size(14), pady=(get_scaled_size(6), 0))

        sc = ScrollFrame(self, bg=COL_BG)
        sc.pack(side="top", fill="both", expand=True, 
                pady=(get_scaled_size(10), get_scaled_size(8)))
        body = sc.body

        calib = Card(body, min_height=350)
        calib.pack(fill="x", expand=False, 
                   padx=get_scaled_size(14), pady=get_scaled_size(8))

        title_calib = tk.Frame(calib, bg=COL_CARD)
        title_calib.pack(fill="x", pady=(0, get_scaled_size(6)))
        
        CardTitle(title_calib, "Pasos de Calibración").pack(side="left")

        calib_separator = tk.Frame(calib, bg=COL_ACCENT, height=1)
        calib_separator.pack(fill="x", pady=(get_scaled_size(6), get_scaled_size(10)))

        instructions_frame = tk.Frame(calib, bg="#1a1f2e")
        instructions_frame.pack(fill="x", pady=(0, get_scaled_size(6)))

        steps = [
            ("1", "Captura el punto 'Cero' sin peso"),
            ("2", "Introduce el peso del patrón de calibración"),  
            ("3", "Coloca el patrón y captura la lectura"),
            ("4", "Guarda la calibración")
        ]

        for num, text in steps:
            step_frame = tk.Frame(instructions_frame, bg="#1a1f2e")
            step_frame.pack(fill="x", padx=get_scaled_size(10), pady=get_scaled_size(3))
            
            step_num = tk.Label(step_frame, text=num, bg=COL_ACCENT, fg=COL_TEXT,
                                font=("DejaVu Sans", FS_TEXT, "bold"), 
                                width=3, height=1)
            step_num.pack(side="left")
            
            step_text = tk.Label(step_frame, text=text, bg="#1a1f2e", fg=COL_TEXT,
                                 font=("DejaVu Sans", FS_TEXT), justify="left")
            step_text.pack(side="left", padx=(get_scaled_size(8), 0))

        live_frame = tk.Frame(calib, bg="#1a1f2e", highlightbackground=COL_BORDER,
                              highlightthickness=1, relief="flat")
        live_frame.pack(fill="x", pady=(get_scaled_size(6), get_scaled_size(10)), 
                        padx=get_scaled_size(8))

        live_icon = tk.Label(live_frame, text="📊", bg="#1a1f2e", fg=COL_ACCENT,
                             font=("DejaVu Sans", FS_CARD_TITLE))
        live_icon.pack(side="left", padx=(get_scaled_size(10), get_scaled_size(8)))
        
        self.lbl_live = tk.Label(live_frame, text="Lectura actual: —",
                                 bg="#1a1f2e", fg=COL_TEXT, 
                                 font=("DejaVu Sans", FS_TEXT))
        self.lbl_live.pack(side="left", pady=get_scaled_size(6))

        row_vals = tk.Frame(calib, bg=COL_CARD)
        row_vals.pack(fill="x", pady=(0, get_scaled_size(6)))

        self._bruto0 = None
        self._brutoW = None

        zero_frame = tk.Frame(row_vals, bg="#1a1f2e", highlightbackground=COL_BORDER,
                              highlightthickness=1, relief="flat")
        zero_frame.pack(side="left", expand=True, fill="x", padx=(0, get_scaled_size(4)))
        
        self.lbl_b0 = tk.Label(zero_frame, text="Cero: —", bg="#1a1f2e", fg=COL_TEXT,
                               font=("DejaVu Sans", FS_TEXT), pady=get_scaled_size(5))
        self.lbl_b0.pack()

        pattern_frame = tk.Frame(row_vals, bg="#1a1f2e", highlightbackground=COL_BORDER,
                                 highlightthickness=1, relief="flat")
        pattern_frame.pack(side="right", expand=True, fill="x", 
                           padx=(get_scaled_size(4), 0))
        
        self.lbl_bw = tk.Label(pattern_frame, text="Con patrón: —", bg="#1a1f2e", fg=COL_TEXT,
                               font=("DejaVu Sans", FS_TEXT), pady=get_scaled_size(5))
        self.lbl_bw.pack()

        row_cap = tk.Frame(calib, bg=COL_CARD)
        row_cap.pack(fill="x", pady=(0, get_scaled_size(10)))
        
        GhostButton(row_cap, text="📍 Capturar Cero", command=self._cap_cero, micro=True).pack(
            side="left", padx=(0, get_scaled_size(6)))
        GhostButton(row_cap, text="📍 Capturar con patrón", command=self._cap_con_peso, micro=True).pack(
            side="left")

        peso_label = tk.Label(calib, text="Peso del patrón (según unidad configurada):", 
                              bg=COL_CARD, fg=COL_TEXT, font=("DejaVu Sans", FS_TEXT))
        peso_label.pack(anchor="w", pady=(get_scaled_size(6), get_scaled_size(6)))

        self._peso_var = tk.StringVar(value="")
        
        # Teclado SIEMPRE visible (con scroll si hace falta)
        pad = NumericKeypad(calib, self._peso_var, on_ok=None, on_clear=None,
                            allow_dot=True, variant="small")
        pad.pack(fill="x", expand=False, padx=get_scaled_size(8))

        save_btn = BigButton(calib, text="💾 Calcular y Guardar Calibración", 
                             command=self._calc_save, micro=True)
        save_btn.pack(fill="x", pady=(get_scaled_size(10), 0))

        self.toast = Toast(self)

        self.after(120, self._tick_live)

    def on_show(self):
        pass

    def _tick_live(self):
        try:
            reader = self.app.get_reader()
            if reader is not None:
                val = reader.get_latest()
                if val is not None:
                    self.lbl_live.config(text=f"Lectura actual: {val:.3f}")
        finally:
            self.after(120, self._tick_live)

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
            self.after(1000, lambda: self.app.show_screen('settings_menu'))
        except Exception:
            self.toast.show("❌ Error al guardar", ms=1500, color=COL_DANGER)


class WifiScreen(BaseScreen):
    """
    Pantalla de configuración Wi-Fi (UI). Guarda SSID/PSK en config.
    """
    def __init__(self, parent, app):
        super().__init__(parent, app)

        header = tk.Frame(self, bg=COL_BG)
        header.pack(side="top", fill="x", pady=(get_scaled_size(10), 0))

        title_frame = tk.Frame(header, bg=COL_BG)
        title_frame.pack(side="left", padx=get_scaled_size(14))
        
        icon_label = tk.Label(title_frame, text="📶", bg=COL_BG, fg=COL_ACCENT,
                              font=("DejaVu Sans", int(FS_TITLE * 1.4)))
        icon_label.pack(side="left", padx=(0, get_scaled_size(8)))
        
        title_label = tk.Label(title_frame, text="Conexión Wi-Fi", bg=COL_BG, fg=COL_TEXT,
                               font=("DejaVu Sans", FS_TITLE, "bold"))
        title_label.pack(side="left")

        GhostButton(header, text="← Ajustes", command=lambda: self.app.show_screen('settings_menu'), micro=True).pack(
            side="right", padx=get_scaled_size(14))

        separator = tk.Frame(self, bg=COL_ACCENT, height=2)
        separator.pack(fill="x", padx=get_scaled_size(14), pady=(get_scaled_size(6), 0))

        body = Card(self, min_height=300)
        body.pack(fill="both", expand=True, padx=get_scaled_size(14), pady=get_scaled_size(10))

        # Formulario
        form = tk.Frame(body, bg=COL_CARD)
        form.pack(fill="x", padx=get_scaled_size(6), pady=get_scaled_size(6))

        # SSID
        row_ssid = tk.Frame(form, bg=COL_CARD)
        row_ssid.pack(fill="x", pady=(get_scaled_size(6), get_scaled_size(6)))
        tk.Label(row_ssid, text="SSID:", bg=COL_CARD, fg=COL_TEXT, font=("DejaVu Sans", FS_TEXT, "bold"),
                 width=18, anchor="w").pack(side="left")
        self._ssid_var = tk.StringVar(value=self.app.get_cfg().get("wifi_ssid",""))
        tk.Entry(row_ssid, textvariable=self._ssid_var, bg="#1a1f2e", fg=COL_TEXT,
                 insertbackground=COL_ACCENT, font=("DejaVu Sans", FS_TEXT),
                 relief="flat", highlightbackground=COL_BORDER, highlightthickness=1).pack(side="left", fill="x", expand=True)

        # PSK
        row_psk = tk.Frame(form, bg=COL_CARD)
        row_psk.pack(fill="x", pady=(get_scaled_size(6), get_scaled_size(6)))
        tk.Label(row_psk, text="Contraseña:", bg=COL_CARD, fg=COL_TEXT, font=("DejaVu Sans", FS_TEXT, "bold"),
                 width=18, anchor="w").pack(side="left")
        self._psk_var = tk.StringVar(value=self.app.get_cfg().get("wifi_psk",""))
        self._psk_entry = tk.Entry(row_psk, textvariable=self._psk_var, show="•", bg="#1a1f2e", fg=COL_TEXT,
                                   insertbackground=COL_ACCENT, font=("DejaVu Sans", FS_TEXT),
                                   relief="flat", highlightbackground=COL_BORDER, highlightthickness=1)
        self._psk_entry.pack(side="left", fill="x", expand=True)

        show_btn = GhostButton(row_psk, text="👁", command=self._toggle_psk, micro=True)
        show_btn.pack(side="left", padx=(get_scaled_size(6), 0))

        # Acciones
        actions = tk.Frame(body, bg=COL_CARD)
        actions.pack(fill="x", pady=(get_scaled_size(6), 0))
        BigButton(actions, text="💾 Guardar", command=self._save, micro=True).pack(side="left")
        BigButton(actions, text="🔌 Conectar", command=self._connect, micro=True).pack(side="left", padx=(get_scaled_size(10),0))

        # Info
        info = tk.Label(body, text="Nota: la conexión real puede requerir privilegios del sistema. "
                                   "Esta pantalla guarda SSID/contraseña en la configuración para que tu servicio de red los use.",
                        bg=COL_CARD, fg=COL_MUTED, font=("DejaVu Sans", FS_TEXT), justify="left", wraplength=800)
        info.pack(fill="x", pady=(get_scaled_size(10), 0))

        self.toast = Toast(self)

    def _toggle_psk(self):
        if self._psk_entry.cget("show") == "":
            self._psk_entry.config(show="•")
        else:
            self._psk_entry.config(show="")

    def _save(self):
        cfg = self.app.get_cfg()
        cfg["wifi_ssid"] = self._ssid_var.get().strip()
        cfg["wifi_psk"] = self._psk_var.get().strip()
        self.app.save_cfg()
        self.toast.show("✓ Credenciales guardadas", ms=1200, color=COL_SUCCESS)

    def _connect(self):
        # Llamada a stub (si existe) o simple mensaje
        ok = False
        if hasattr(self.app, "wifi_connect"):
            try:
                ok = self.app.wifi_connect(self._ssid_var.get().strip(), self._psk_var.get().strip())
            except Exception:
                ok = False
        self.toast.show("🔌 Conexión solicitada" if ok else "ℹ Conexión delegada al sistema", ms=1400, color=COL_MUTED)


class ApiKeyScreen(BaseScreen):
    """
    Pantalla para guardar la API Key de ChatGPT/OpenAI.
    """
    def __init__(self, parent, app):
        super().__init__(parent, app)

        header = tk.Frame(self, bg=COL_BG)
        header.pack(side="top", fill="x", pady=(get_scaled_size(10), 0))

        title_frame = tk.Frame(header, bg=COL_BG)
        title_frame.pack(side="left", padx=get_scaled_size(14))
        
        icon_label = tk.Label(title_frame, text="🗝", bg=COL_BG, fg=COL_ACCENT,
                              font=("DejaVu Sans", int(FS_TITLE * 1.4)))
        icon_label.pack(side="left", padx=(0, get_scaled_size(8)))
        
        title_label = tk.Label(title_frame, text="API Key ChatGPT", bg=COL_BG, fg=COL_TEXT,
                               font=("DejaVu Sans", FS_TITLE, "bold"))
        title_label.pack(side="left")

        GhostButton(header, text="← Ajustes", command=lambda: self.app.show_screen('settings_menu'), micro=True).pack(
            side="right", padx=get_scaled_size(14))

        separator = tk.Frame(self, bg=COL_ACCENT, height=2)
        separator.pack(fill="x", padx=get_scaled_size(14), pady=(get_scaled_size(6), 0))

        body = Card(self, min_height=250)
        body.pack(fill="both", expand=True, padx=get_scaled_size(14), pady=get_scaled_size(10))

        row = tk.Frame(body, bg=COL_CARD)
        row.pack(fill="x", pady=(get_scaled_size(8), get_scaled_size(8)))

        tk.Label(row, text="API Key:", bg=COL_CARD, fg=COL_TEXT, font=("DejaVu Sans", FS_TEXT, "bold"),
                 width=18, anchor="w").pack(side="left")

        self._key_var = tk.StringVar(value=self.app.get_cfg().get("openai_api_key",""))
        self._key_entry = tk.Entry(row, textvariable=self._key_var, show="•", bg="#1a1f2e", fg=COL_TEXT,
                                   insertbackground=COL_ACCENT, font=("DejaVu Sans", FS_TEXT),
                                   relief="flat", highlightbackground=COL_BORDER, highlightthickness=1)
        self._key_entry.pack(side="left", fill="x", expand=True)

        GhostButton(row, text="👁", command=self._toggle_key, micro=True).pack(side="left", padx=(get_scaled_size(6), 0))

        actions = tk.Frame(body, bg=COL_CARD)
        actions.pack(fill="x", pady=(get_scaled_size(6), 0))
        BigButton(actions, text="💾 Guardar", command=self._save, micro=True).pack(side="left")
        BigButton(actions, text="✅ Probar (local)", command=self._test_local, micro=True).pack(side="left", padx=(get_scaled_size(10),0))

        tip = tk.Label(body, text="Consejo: pega tu clave completa (por ej. empieza por 'sk-'). La prueba local solo valida formato y longitud.",
                       bg=COL_CARD, fg=COL_MUTED, font=("DejaVu Sans", FS_TEXT), wraplength=820, justify="left")
        tip.pack(fill="x", pady=(get_scaled_size(10), 0))

        self.toast = Toast(self)

    def _toggle_key(self):
        if self._key_entry.cget("show") == "":
            self._key_entry.config(show="•")
        else:
            self._key_entry.config(show="")

    def _save(self):
        k = self._key_var.get().strip()
        self.app.get_cfg()["openai_api_key"] = k
        self.app.save_cfg()
        self.toast.show("✓ API Key guardada", ms=1200, color=COL_SUCCESS)

    def _test_local(self):
        k = self._key_var.get().strip()
        ok = len(k) >= 20 and ("sk-" in k or k.startswith("sk-"))
        if ok:
            self.toast.show("✓ Formato parece correcto", ms=1100, color=COL_SUCCESS)
        else:
            self.toast.show("⚠ Clave sospechosa (revisa)", ms=1300, color=COL_WARN)
