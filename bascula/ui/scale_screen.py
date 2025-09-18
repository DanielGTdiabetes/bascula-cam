"""Pantalla principal de pesaje."""

from __future__ import annotations

import tkinter as tk

from bascula.services.scale import NullScaleService, ScaleService
from bascula.ui.widgets import (
    Card,
    GhostButton,
    Toast,
    WeightLabel,
    BigButton,
    COL_BG,
    COL_CARD,
    COL_MUTED,
    get_scaled_size,
)


class ScaleScreen(tk.Frame):
    name = "scale"
    title = "Pesar"

    def __init__(self, parent: tk.Misc, app) -> None:
        super().__init__(parent, bg=COL_BG)
        self.app = app
        self.toast = Toast(self)
        self._notified_safe = False

        self.service = getattr(app, "reader", None)
        if self.service is None:
            cfg = getattr(app, "cfg", {})
            self.service = ScaleService.safe_create(
                logger=getattr(app, "logger", None),
                fail_fast=False,
                config=cfg if isinstance(cfg, dict) else dict(cfg),
                port=cfg.get("port"),
                baud=int(cfg.get("baud", 115200)),
                sample_ms=int(cfg.get("sample_ms", 100)),
            )
            app.reader = self.service
        self._null_mode = isinstance(self.service, NullScaleService)

        outer = Card(self)
        outer.pack(expand=True, fill="both", padx=get_scaled_size(18), pady=get_scaled_size(18))

        self.weight_label = WeightLabel(
            outer,
            textvariable=app.weight_text,
            bg=COL_CARD,
            anchor="center",
            justify="center",
        )
        self.weight_label.pack(fill="x", pady=(get_scaled_size(12), get_scaled_size(6)))

        self.status_label = tk.Label(
            outer,
            textvariable=app.stability_text,
            bg=COL_CARD,
            fg=COL_MUTED,
            font=("DejaVu Sans", get_scaled_size(14)),
            anchor="w",
        )
        self.status_label.pack(fill="x", padx=get_scaled_size(8))

        buttons = tk.Frame(outer, bg=COL_CARD)
        buttons.pack(fill="x", pady=get_scaled_size(18))

        self.tare_btn = BigButton(buttons, text="Tara", command=app.perform_tare)
        self.tare_btn.pack(side="left", expand=True, fill="x", padx=4)
        self.zero_btn = BigButton(buttons, text="Cero", command=app.perform_zero)
        self.zero_btn.pack(side="left", expand=True, fill="x", padx=4)
        self.capture_btn = GhostButton(buttons, text="Capturar", command=app.capture_weight)
        self.capture_btn.pack(side="left", expand=True, fill="x", padx=4)

        extras = tk.Frame(outer, bg=COL_CARD)
        extras.pack(fill="x", pady=(0, get_scaled_size(12)))
        GhostButton(extras, text="⭐ Favoritos", command=app.open_favorites, micro=True).pack(
            side="left", expand=True, fill="x", padx=4
        )
        GhostButton(extras, text="⏱ Timer", command=app.open_timer_overlay, micro=True).pack(
            side="left", expand=True, fill="x", padx=4
        )
        GhostButton(extras, text="🍽 Recetas", command=app.open_recipes, micro=True).pack(
            side="left", expand=True, fill="x", padx=4
        )

        note = tk.Label(
            outer,
            text="Coloca el recipiente vacío y pulsa Tara antes de pesar.",
            bg=COL_CARD,
            fg=COL_MUTED,
            anchor="w",
            font=("DejaVu Sans", get_scaled_size(13)),
        )
        note.pack(fill="x", padx=get_scaled_size(8), pady=(get_scaled_size(12), 0))

        if self._null_mode:
            self._set_buttons_state(tk.DISABLED)
        else:
            self._set_buttons_state(tk.NORMAL)

    def _set_buttons_state(self, state: str) -> None:
        for btn in (self.tare_btn, self.zero_btn, self.capture_btn):
            try:
                btn.configure(state=state)
            except Exception:
                pass

    def on_show(self) -> None:
        self.after(200, self._tick)
        if self._null_mode and not self._notified_safe:
            self.toast.show("Modo seguro de báscula (revisa instalación/permisos)", 3200)
            self._notified_safe = True

    def on_hide(self) -> None:  # pragma: no cover - interacción gráfica
        return

    def _tick(self) -> None:
        try:
            weight = self.app.get_latest_weight()
            decimals = max(0, int(self.app.cfg.get("decimals", 0)))
            unit = str(self.app.cfg.get("unit", "g"))
            formatted = f"{weight:.{decimals}f} {unit}"
            self.app.weight_text.set(formatted)
            stable = False
            try:
                stable = bool(self.app.reader.is_stable()) if self.app.reader else False
            except Exception:
                stable = False
            self.app.stability_text.set("Estable" if stable else "Midiendo…")
        except Exception as exc:
            self.app.logger.warning("Error actualizando peso: %s", exc)
            self.app.stability_text.set("Error de lectura")
        finally:
            self.after(200, self._tick)

        if isinstance(self.app.reader, NullScaleService):
            self._set_buttons_state(tk.DISABLED)
        else:
            self._set_buttons_state(tk.NORMAL)
