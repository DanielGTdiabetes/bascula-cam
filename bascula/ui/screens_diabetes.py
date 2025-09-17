from __future__ import annotations

import time
import tkinter as tk
from tkinter import ttk
from typing import Optional

from bascula.ui.screens import BaseScreen
from bascula.ui.widgets import Card, BigButton, GhostButton, Toast, COL_CARD, COL_TEXT, COL_ACCENT, COL_MUTED


class DiabetesSettingsScreen(BaseScreen):
    """Realtime diabetes hub with BG status and 15/15 tools."""

    name = "diabetes"
    title = "Diabetes"

    def __init__(self, parent, app, **kwargs):
        super().__init__(parent, app, **kwargs)

        self.bg_var = tk.StringVar(value="—")
        self.trend_var = tk.StringVar(value="—")
        self.pred_var = tk.StringVar(value="—")
        self.timer_var = tk.StringVar(value="Temporizador detenido")
        self.mode_var = tk.BooleanVar(value=bool(self.app.diabetes_mode))
        self.bolus_var = tk.StringVar(value="Sin recomendación")
        self.bolus_window_var = tk.StringVar(value="")
        self.threshold_low = tk.StringVar(value=str(self.app.get_cfg().get("bg_low_threshold", 70)))
        self.threshold_high = tk.StringVar(value=str(self.app.get_cfg().get("bg_high_threshold", 180)))
        self._bolus_job: Optional[str] = None
        self._bolus_window_end: Optional[float] = None

        top = Card(self.content)
        top.pack(fill="x", pady=(0, 12))

        header = tk.Frame(top, bg=COL_CARD)
        header.pack(fill="x")
        style_name = "Diabetes.TCheckbutton"
        try:
            style = ttk.Style(self)
            style.configure(style_name, background=COL_CARD, foreground=COL_TEXT)
        except Exception:
            style_name = ""
        tk.Label(
            header,
            text="Modo diabético",
            bg=COL_CARD,
            fg=COL_ACCENT,
            font=("DejaVu Sans", 18, "bold"),
        ).pack(side="left", padx=8, pady=6)
        ttk.Checkbutton(
            header,
            text="Activado",
            variable=self.mode_var,
            command=self._toggle_mode,
            style=style_name or None,
        ).pack(side="left", padx=8)
        GhostButton(header, text="Nightscout", command=lambda: self.app.show_screen("nightscout"), micro=True).pack(
            side="right", padx=6
        )

        status = tk.Frame(top, bg=COL_CARD)
        status.pack(fill="x", padx=6, pady=(4, 8))
        self._add_status_label(status, "Glucosa", self.bg_var)
        self._add_status_label(status, "Tendencia", self.trend_var)
        self._add_status_label(status, "Pred. 15/30", self.pred_var)

        thresholds = tk.Frame(top, bg=COL_CARD)
        thresholds.pack(fill="x", padx=6, pady=(0, 6))
        tk.Label(thresholds, text="Hipo <", bg=COL_CARD, fg=COL_TEXT).pack(side="left")
        tk.Entry(thresholds, textvariable=self.threshold_low, width=5, justify="center").pack(side="left", padx=(4, 12))
        tk.Label(thresholds, text="Hiper >", bg=COL_CARD, fg=COL_TEXT).pack(side="left")
        tk.Entry(thresholds, textvariable=self.threshold_high, width=5, justify="center").pack(side="left", padx=4)
        GhostButton(thresholds, text="Guardar", micro=True, command=self._save_thresholds).pack(side="left", padx=12)

        hypo = Card(self.content)
        hypo.pack(fill="x", pady=(0, 12))
        tk.Label(
            hypo,
            text="Regla 15/15",
            bg=COL_CARD,
            fg=COL_ACCENT,
            font=("DejaVu Sans", 16, "bold"),
        ).pack(anchor="w", padx=8, pady=(6, 0))
        tk.Label(
            hypo,
            text="Toma 15 g de hidratos, espera 15 minutos y vuelve a medir.",
            bg=COL_CARD,
            fg=COL_MUTED,
        ).pack(anchor="w", padx=8, pady=(0, 8))
        tk.Label(hypo, textvariable=self.timer_var, bg=COL_CARD, fg=COL_TEXT, font=("DejaVu Sans", 14, "bold")).pack(
            anchor="w", padx=8
        )
        btns = tk.Frame(hypo, bg=COL_CARD)
        btns.pack(fill="x", padx=8, pady=(8, 6))
        BigButton(btns, text="Iniciar 15:00", command=self._start_timer, micro=True).pack(side="left", padx=4)
        GhostButton(btns, text="Cancelar", command=self._cancel_timer, micro=True).pack(side="left", padx=4)

        bolus = Card(self.content)
        bolus.pack(fill="x", pady=(0, 12))
        tk.Label(
            bolus,
            text="Ventana de inyección",
            bg=COL_CARD,
            fg=COL_ACCENT,
            font=("DejaVu Sans", 16, "bold"),
        ).pack(anchor="w", padx=8, pady=(6, 0))
        tk.Label(bolus, textvariable=self.bolus_var, bg=COL_CARD, fg=COL_TEXT, font=("DejaVu Sans", 14)).pack(
            anchor="w", padx=8, pady=(0, 4)
        )
        tk.Label(bolus, textvariable=self.bolus_window_var, bg=COL_CARD, fg=COL_MUTED).pack(anchor="w", padx=8)

        actions = tk.Frame(bolus, bg=COL_CARD)
        actions.pack(fill="x", padx=8, pady=(8, 8))
        GhostButton(actions, text="Reiniciar ventana", command=self._restart_window, micro=True).pack(side="left", padx=4)
        GhostButton(actions, text="Detener", command=self._stop_window, micro=True).pack(side="left", padx=4)

        self.toast = Toast(self)
        try:
            self.app.event_bus.subscribe("bg_update", self._on_bg_event)
            self.app.event_bus.subscribe("bg_low", self._on_bg_low)
            self.app.event_bus.subscribe("bolus_recommendation", self._on_bolus)
        except Exception:
            pass

    # ------------------------------------------------------------------ layout helpers
    def _add_status_label(self, parent: tk.Misc, title: str, var: tk.StringVar) -> None:
        box = tk.Frame(parent, bg=COL_CARD)
        box.pack(side="left", expand=True, fill="x", padx=6)
        tk.Label(box, text=title, bg=COL_CARD, fg=COL_MUTED).pack(anchor="w")
        tk.Label(box, textvariable=var, bg=COL_CARD, fg=COL_TEXT, font=("DejaVu Sans", 20, "bold")).pack(anchor="w")

    # ------------------------------------------------------------------ actions
    def _toggle_mode(self) -> None:
        cfg = self.app.get_cfg()
        cfg["diabetic_mode"] = bool(self.mode_var.get())
        self.app.save_cfg()
        if self.mode_var.get():
            self.toast.show("Modo diabético activado", 1200)
        else:
            self.toast.show("Modo diabético desactivado", 1200)

    def _save_thresholds(self) -> None:
        cfg = self.app.get_cfg()
        try:
            cfg["bg_low_threshold"] = max(50, int(float(self.threshold_low.get())))
            cfg["bg_high_threshold"] = max(100, int(float(self.threshold_high.get())))
            self.app.save_cfg()
            self.toast.show("Umbrales guardados", 1000)
        except Exception as exc:
            self.toast.show(f"Error: {exc}", 1500)

    def _start_timer(self) -> None:
        try:
            self.app.start_hypo_timer()
        except Exception:
            self.toast.show("No se pudo iniciar", 1500)

    def _cancel_timer(self) -> None:
        try:
            self.app.hypo_timer.close()
        except Exception:
            pass
        self.timer_var.set("Temporizador detenido")

    def _restart_window(self) -> None:
        if self._bolus_window_end is None:
            return
        remaining = self._bolus_window_end - time.time()
        if remaining <= 0:
            self._stop_window()
        else:
            self._schedule_window_update()

    def _stop_window(self) -> None:
        self._bolus_window_end = None
        self.bolus_window_var.set("")
        if self._bolus_job:
            try:
                self.after_cancel(self._bolus_job)
            except Exception:
                pass
            self._bolus_job = None

    # ------------------------------------------------------------------ events
    def _on_bg_event(self, payload: Optional[dict]) -> None:
        if not isinstance(payload, dict):
            payload = {}
        value = payload.get("value", self.app._last_bg)
        trend = payload.get("trend", self.app._last_bg_direction)
        pred15 = payload.get("pred_15", self.app._bg_pred_15)
        pred30 = payload.get("pred_30", self.app._bg_pred_30)
        if value is None:
            self.bg_var.set("—")
        else:
            delta = payload.get("delta")
            if delta is None:
                self.bg_var.set(f"{value} mg/dL")
            else:
                sign = "+" if delta >= 0 else ""
                self.bg_var.set(f"{value} mg/dL ({sign}{int(delta)})")
        arrows = {"up": "↑", "down": "↓", "flat": "→"}
        self.trend_var.set(arrows.get(str(trend), str(trend)) or "—")
        if pred15 is not None and pred30 is not None:
            self.pred_var.set(f"{pred15}/{pred30} mg/dL")
        else:
            self.pred_var.set("—")
        remaining = 0
        try:
            if self.app.hypo_timer.is_running():
                remaining = self.app.hypo_timer.remaining_seconds()
        except Exception:
            remaining = 0
        if remaining > 0:
            mins, secs = divmod(int(remaining), 60)
            self.timer_var.set(f"Restan {mins:02d}:{secs:02d}")
        else:
            self.timer_var.set("Temporizador detenido")

    def _on_bg_low(self, payload: Optional[dict]) -> None:
        self.timer_var.set("BG baja detectada – inicia la regla 15/15")

    def _on_bolus(self, payload: Optional[dict]) -> None:
        if not isinstance(payload, dict):
            return
        units = payload.get("units")
        carbs = payload.get("carbs")
        current = payload.get("current_bg")
        target = payload.get("target")
        window = int(payload.get("window_min", 15))
        text = f"Carbs {carbs:.1f} g → {units:.2f} U (BG {current}/{target})"
        self.bolus_var.set(text)
        self._bolus_window_end = time.time() + window * 60
        self._schedule_window_update()

    def _schedule_window_update(self) -> None:
        if self._bolus_job:
            try:
                self.after_cancel(self._bolus_job)
            except Exception:
                pass
        if self._bolus_window_end is None:
            self.bolus_window_var.set("")
            return
        remaining = int(self._bolus_window_end - time.time())
        if remaining <= 0:
            self.bolus_window_var.set("Ventana finalizada")
            self._bolus_window_end = None
            return
        mins, secs = divmod(remaining, 60)
        self.bolus_window_var.set(f"Quedan {mins:02d}:{secs:02d}")
        self._bolus_job = self.after(1000, self._schedule_window_update)

    # ------------------------------------------------------------------ screen hooks
    def on_show(self) -> None:  # pragma: no cover - UI updates
        self._on_bg_event({})

    def on_hide(self) -> None:  # pragma: no cover
        self._stop_window()
