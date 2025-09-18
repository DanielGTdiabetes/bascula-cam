"""Dedicated screen for weighing food items."""

from __future__ import annotations

import tkinter as tk
from typing import Optional

from bascula.services.scale import NullScaleService, ScaleService
from bascula.ui.screens import BaseScreen
from bascula.ui.widgets import Card, Toast, BigButton, GhostButton, WeightLabel, COL_CARD, COL_MUTED, COL_TEXT, COL_ACCENT


class ScaleScreen(BaseScreen):
    """Interactive view that displays the current weight from the scale."""

    name = "scale"
    title = "Báscula"

    def __init__(self, parent: tk.Misc, app, **kwargs) -> None:
        super().__init__(parent, app, **kwargs)

        self.scale: Optional[ScaleService | NullScaleService] = getattr(app, "reader", None)
        if self.scale is None:
            self.scale = ScaleService.safe_create(logger=getattr(app, "logger", None))
            app.reader = self.scale

        self._service_started = bool(getattr(app, "_scale_started", False))
        self._tick_job: Optional[str] = None
        self._toast = Toast(self)
        self._safe_mode_notified = False

        self.weight_var = tk.StringVar(value="0 g")
        self.status_var = tk.StringVar(value="Sin lectura")

        card = Card(self.content)
        card.pack(fill="both", expand=True)

        self.weight_lbl = WeightLabel(
            card,
            textvariable=self.weight_var,
            bg=COL_CARD,
            fg=COL_ACCENT,
        )
        self.weight_lbl.configure(anchor="center", justify="center")
        self.weight_lbl.pack(fill="both", expand=True, padx=12, pady=(12, 18))

        self.status_lbl = tk.Label(
            card,
            textvariable=self.status_var,
            bg=COL_CARD,
            fg=COL_MUTED,
            font=("DejaVu Sans", 16, "bold"),
        )
        self.status_lbl.pack(pady=(0, 12))

        buttons = tk.Frame(card, bg=COL_CARD)
        buttons.pack(fill="x", pady=(0, 12))

        self.tare_btn = BigButton(buttons, text="Tara", command=self._on_tare)
        self.tare_btn.pack(side="left", expand=True, fill="x", padx=6)
        self.zero_btn = BigButton(buttons, text="Cero", command=self._on_zero)
        self.zero_btn.pack(side="left", expand=True, fill="x", padx=6)
        GhostButton(buttons, text="Capturar", command=app.capture_weight).pack(
            side="left", expand=True, fill="x", padx=6
        )
        GhostButton(buttons, text="📷 Escanear", command=app.open_scanner).pack(
            side="left", expand=True, fill="x", padx=6
        )

        extras = tk.Frame(card, bg=COL_CARD)
        extras.pack(fill="x", pady=(0, 18))
        GhostButton(extras, text="⭐ Favoritos", command=app.open_favorites, micro=True).pack(
            side="left", expand=True, fill="x", padx=4
        )
        GhostButton(extras, text="⏱ Timer", command=app.open_timer_overlay, micro=True).pack(
            side="left", expand=True, fill="x", padx=4
        )
        GhostButton(extras, text="🍳 Recetas", command=app.open_recipes, micro=True).pack(
            side="left", expand=True, fill="x", padx=4
        )

        info = tk.Label(
            card,
            text="Los valores mostrados se actualizan en tiempo real desde la báscula.",
            bg=COL_CARD,
            fg=COL_MUTED,
        )
        info.pack(anchor="center", pady=(0, 8))

        self._update_button_state()

    # ------------------------------------------------------------------ Hooks
    def on_show(self) -> None:
        self._ensure_service_started()
        self._schedule_tick()
        if getattr(self.scale, "is_null", False) and not self._safe_mode_notified:
            self._safe_mode_notified = True
            try:
                self._toast.show("Modo seguro de báscula (revisa instalación/permisos)", timeout_ms=2400)
            except Exception:
                pass

    def on_hide(self) -> None:
        if self._tick_job:
            try:
                self.after_cancel(self._tick_job)
            except Exception:
                pass
            self._tick_job = None

    # ------------------------------------------------------------------ Helpers
    def _ensure_service_started(self) -> None:
        if self.scale is None or self._service_started:
            return
        start = getattr(self.scale, "start", None)
        if callable(start):
            try:
                start()
                setattr(self.app, "_scale_started", True)
                self._service_started = True
            except Exception:
                logger = getattr(self.app, "logger", None)
                if logger:
                    logger.warning("No se pudo iniciar la báscula desde ScaleScreen", exc_info=True)
        self._update_button_state()

    def _schedule_tick(self) -> None:
        if self._tick_job is not None:
            return
        self._tick_job = self.after(200, self._tick)

    def _tick(self) -> None:
        self._tick_job = None
        weight = 0.0
        stable = False

        readings = []
        drain = getattr(self.scale, "drain_readings", None)
        if callable(drain):
            try:
                readings = list(drain())
            except Exception:
                readings = []

        if readings:
            weight, stable = readings[-1]
        else:
            try:
                weight = float(self.scale.get_weight() if self.scale else 0.0)
            except Exception:
                logger = getattr(self.app, "logger", None)
                if logger:
                    logger.warning("Lectura de báscula fallida", exc_info=True)
                weight = 0.0
            try:
                stable = bool(self.scale.is_stable() if self.scale else False)
            except Exception:
                stable = False

        decimals = max(0, int(self.app.cfg.get("decimals", 0)))
        unit = str(self.app.cfg.get("unit", "g"))
        formatted = f"{weight:.{decimals}f} {unit}"
        self.weight_var.set(formatted)
        status_text = "Estable" if stable else "Midiendo…"
        self.status_var.set(status_text)

        try:
            self.app.weight_text.set(formatted)
            self.app.stability_text.set(status_text)
            self.app.topbar.update_weight(formatted, stable)
        except Exception:
            pass

        self._tick_job = self.after(200, self._tick)

    def _update_button_state(self) -> None:
        disabled = tk.DISABLED if getattr(self.scale, "is_null", False) else tk.NORMAL
        for btn in (self.tare_btn, self.zero_btn):
            try:
                btn.configure(state=disabled)
            except Exception:
                pass

    def _invoke_scale_tare(self) -> None:
        tare = getattr(self.scale, "tare", None)
        if callable(tare):
            try:
                tare()
            except Exception:
                logger = getattr(self.app, "logger", None)
                if logger:
                    logger.warning("No se pudo enviar tara a la báscula", exc_info=True)

    def _on_tare(self) -> None:
        self._invoke_scale_tare()
        try:
            self.app.perform_tare()
        except Exception:
            logger = getattr(self.app, "logger", None)
            if logger:
                logger.warning("perform_tare lanzó excepción", exc_info=True)

    def _on_zero(self) -> None:
        self._invoke_scale_tare()
        try:
            self.app.perform_zero()
        except Exception:
            logger = getattr(self.app, "logger", None)
            if logger:
                logger.warning("perform_zero lanzó excepción", exc_info=True)


__all__ = ["ScaleScreen"]

