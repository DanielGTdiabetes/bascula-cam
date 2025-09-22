"""Interactive calibration assistant for the HX711 scale."""
from __future__ import annotations

import tkinter as tk
from typing import Callable, Optional

from ..overlay_base import OverlayBase
from ..widgets import (
    COL_CARD,
    COL_TEXT,
    COL_DANGER,
    COL_SUCCESS,
    BigButton,
    Card,
    GhostButton,
    NumericKeypad,
    WeightLabel,
)


class CalibrationOverlay(OverlayBase):
    """Overlay guiding the user through offset and factor calibration."""

    def __init__(
        self,
        parent: tk.Misc,
        *,
        scale: object,
        on_close: Optional[Callable[[], None]] = None,
    ) -> None:
        super().__init__(parent)
        self.scale = scale
        self._on_close = on_close or (lambda: None)
        self._running = False
        self._update_after: Optional[str] = None

        content = self.content()
        content.configure(padx=16, pady=16)

        card = Card(content, min_width=380)
        card.pack(expand=True, padx=8, pady=8)
        card.configure(bg=COL_CARD)

        title = tk.Label(
            card,
            text="Calibración de báscula",
            font=("DejaVu Sans", 22, "bold"),
            bg=COL_CARD,
            fg=COL_TEXT,
        )
        title.pack(pady=(4, 8))

        self._status_var = tk.StringVar(
            value="1. Retira todo de la báscula y pulsa \"Capturar vacío\"."
        )
        status = tk.Label(
            card,
            textvariable=self._status_var,
            wraplength=360,
            justify="left",
            bg=COL_CARD,
            fg=COL_TEXT,
        )
        status.pack(fill="x", padx=8)

        self._weight_label = WeightLabel(card, bg=COL_CARD)
        self._weight_label.pack(fill="x", padx=8, pady=(12, 4))

        self._stable_var = tk.StringVar(value="Inestable")
        self._stable_label = tk.Label(
            card,
            textvariable=self._stable_var,
            bg=COL_CARD,
            fg=COL_DANGER,
            font=("DejaVu Sans", 14, "bold"),
        )
        self._stable_label.pack(pady=(0, 8))

        self._info_var = tk.StringVar(value="Offset: -- | Factor: --")
        info = tk.Label(
            card,
            textvariable=self._info_var,
            bg=COL_CARD,
            fg=COL_TEXT,
            font=("DejaVu Sans", 12),
        )
        info.pack(pady=(0, 12))

        entry_frame = tk.Frame(card, bg=COL_CARD)
        entry_frame.pack(fill="x")

        tk.Label(
            entry_frame,
            text="Peso conocido (g)",
            bg=COL_CARD,
            fg=COL_TEXT,
            font=("DejaVu Sans", 14, "bold"),
        ).pack(anchor="w", padx=8)
        self._input_var = tk.StringVar(value="")
        entry = tk.Entry(
            entry_frame,
            textvariable=self._input_var,
            font=("DejaVu Sans", 20),
            justify="center",
        )
        entry.pack(fill="x", padx=8, pady=(4, 8))

        pad = NumericKeypad(
            card,
            self._input_var,
            on_ok=self._apply_calibration,
            on_cancel=self.hide,
            allow_dot=False,
            variant="small",
        )
        pad.pack(fill="x", padx=4, pady=(0, 8))

        buttons = tk.Frame(card, bg=COL_CARD)
        buttons.pack(fill="x", pady=(8, 0))
        BigButton(
            buttons,
            text="Capturar vacío",
            command=self._capture_zero,
            small=True,
        ).pack(side="left", expand=True, fill="x", padx=4)
        BigButton(
            buttons,
            text="Guardar",
            command=self._apply_calibration,
            small=True,
        ).pack(side="left", expand=True, fill="x", padx=4)
        GhostButton(card, text="Cerrar", command=self.hide, micro=True).pack(pady=(12, 4))

        self._update_info()

    # ------------------------------------------------------------------
    def show(self) -> None:  # type: ignore[override]
        self._running = True
        super().show()
        self._update_info()
        self._schedule_update()

    def hide(self) -> None:  # type: ignore[override]
        self._running = False
        if self._update_after:
            try:
                self.after_cancel(self._update_after)
            except Exception:
                pass
            self._update_after = None
        super().hide()
        try:
            self._on_close()
        except Exception:
            pass

    # ------------------------------------------------------------------
    def _schedule_update(self) -> None:
        if not self._running:
            return
        try:
            grams = float(getattr(self.scale, "net_weight", 0.0))
            stable = bool(getattr(self.scale, "stable", False))
        except Exception:
            grams = 0.0
            stable = False
        self._weight_label.config(text=f"{grams:0.1f}g")
        self._stable_var.set("Estable" if stable else "Inestable")
        self._stable_label.config(fg=COL_SUCCESS if stable else COL_DANGER)
        self._update_after = self.after(200, self._schedule_update)

    def _update_info(self) -> None:
        try:
            offset = float(getattr(self.scale, "calibration_offset", 0.0))
            factor = float(getattr(self.scale, "calibration_factor", 1.0))
        except Exception:
            offset = 0.0
            factor = 1.0
        self._info_var.set(f"Offset: {offset:.0f} | Factor: {factor:.5f}")

    def _capture_zero(self) -> None:
        try:
            offset = getattr(self.scale, "calibrate_zero")()
        except Exception as exc:
            self._status_var.set(f"Error: {exc}")
        else:
            self._status_var.set(
                f"Offset guardado ({offset:.0f}). Coloca el peso conocido."
            )
            self._update_info()

    def _apply_calibration(self) -> None:
        raw = self._input_var.get().replace(",", ".").strip()
        try:
            grams = float(raw)
        except ValueError:
            self._status_var.set("Introduce un peso válido en gramos")
            return
        if grams <= 0:
            self._status_var.set("El peso debe ser mayor a 0")
            return
        try:
            factor = getattr(self.scale, "calibrate_known_weight")(grams)
        except Exception as exc:
            self._status_var.set(f"Error calibrando: {exc}")
            return
        self._status_var.set(f"Calibración guardada (factor {factor:.5f}).")
        self._update_info()
