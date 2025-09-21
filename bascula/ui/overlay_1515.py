from __future__ import annotations

import tkinter as tk
from typing import Any, Dict, Optional

from bascula.services import treatments
from bascula.ui.overlay_base import OverlayBase
from bascula.ui.widgets import (
    BigButton,
    Card,
    COL_ACCENT,
    COL_CARD,
    COL_DANGER,
    COL_MUTED,
    COL_TEXT,
    FS_TEXT,
    FS_TITLE,
)


class Protocol1515Overlay(OverlayBase):
    """Overlay dedicado al protocolo 15/15 para hipoglucemias."""

    UPDATE_MS = 1000

    def __init__(self, parent, app, **kwargs):
        super().__init__(parent, **kwargs)
        self.app = app
        self._job: Optional[str] = None
        self._state: Dict[str, Any] = {}

        container = self.content()
        container.configure(bg=COL_CARD, padx=24, pady=24)

        tk.Label(
            container,
            text="Protocolo 15/15",
            bg=COL_CARD,
            fg=COL_ACCENT,
            font=("DejaVu Sans", FS_TITLE, "bold"),
        ).pack(anchor="w", pady=(0, 12))

        card = Card(container)
        card.pack(fill="both", expand=True)
        card.configure(bg=COL_CARD, padx=18, pady=18)

        self._countdown_var = tk.StringVar(value="15:00")
        tk.Label(
            card,
            textvariable=self._countdown_var,
            bg=COL_CARD,
            fg=COL_ACCENT,
            font=("DejaVu Sans Mono", FS_TITLE + 10, "bold"),
        ).pack(pady=(0, 8))

        self._cycle_var = tk.StringVar(value="")
        tk.Label(
            card,
            textvariable=self._cycle_var,
            bg=COL_CARD,
            fg=COL_MUTED,
            font=("DejaVu Sans", FS_TEXT, "bold"),
        ).pack()

        self._status_var = tk.StringVar(
            value="Pulsa Iniciar después de ingerir 15 g de hidratos de carbono."
        )
        tk.Label(
            card,
            textvariable=self._status_var,
            bg=COL_CARD,
            fg=COL_TEXT,
            wraplength=420,
            justify="left",
            font=("DejaVu Sans", FS_TEXT),
        ).pack(pady=(12, 4), anchor="w")

        buttons = tk.Frame(card, bg=COL_CARD)
        buttons.pack(fill="x", pady=(16, 0))

        self._btn_start = BigButton(
            buttons,
            text="▶ Iniciar 15/15",
            command=self._on_start,
        )
        self._btn_start.pack(side="left", expand=True, fill="x", padx=6)

        self._btn_taken = BigButton(
            buttons,
            text="Tomado (otro 15 g)",
            command=self._on_taken,
            bg=COL_ACCENT,
        )
        self._btn_taken.pack(side="left", expand=True, fill="x", padx=6)

        self._btn_cancel = BigButton(
            buttons,
            text="Cancelar",
            command=self._on_cancel,
            bg=COL_DANGER,
        )
        self._btn_cancel.pack(side="left", expand=True, fill="x", padx=6)

        self._update_buttons({"active": False})

    def show(self):
        super().show()
        self._refresh_state()

    def hide(self):
        if self._job is not None:
            try:
                self.after_cancel(self._job)
            except Exception:
                pass
            self._job = None
        super().hide()

    # --- Actions -----------------------------------------------------------------

    def _voice(self) -> Optional[object]:
        try:
            getter = getattr(self.app, "get_voice", None)
            if callable(getter):
                voice = getter()
                if voice and hasattr(voice, "speak"):
                    return voice
        except Exception:
            return None
        return None

    def _on_start(self) -> None:
        voice = self._voice()
        try:
            state = treatments.start_1515(voice=voice)
            self._state = state
        except Exception as exc:
            self._status_var.set(f"Error iniciando 15/15: {exc}")
        finally:
            self._refresh_state(force=True)

    def _on_taken(self) -> None:
        voice = self._voice()
        try:
            state = treatments.mark_taken(voice=voice)
            self._state = state
        except Exception as exc:
            self._status_var.set(f"Error registrando toma: {exc}")
        finally:
            self._refresh_state(force=True)

    def _on_cancel(self) -> None:
        voice = self._voice()
        try:
            treatments.cancel_1515(voice=voice)
        except Exception as exc:
            self._status_var.set(f"No se pudo cancelar: {exc}")
            return
        self._state = {"active": False}
        self._refresh_state(force=True)
        self.hide()

    # --- State -------------------------------------------------------------------

    def _refresh_state(self, force: bool = False) -> None:
        voice = self._voice()
        try:
            state = treatments.remaining(voice=voice)
            if state:
                self._state = state
        except Exception as exc:
            if force:
                self._status_var.set(f"Error leyendo estado: {exc}")
            state = getattr(self, "_state", {"active": False})
        self._update_view(state)
        self._schedule_update()

    def _schedule_update(self) -> None:
        try:
            if self._job is not None:
                self.after_cancel(self._job)
        except Exception:
            pass
        self._job = self.after(self.UPDATE_MS, self._refresh_state)

    def _update_view(self, state: Dict[str, Any]) -> None:
        active = bool(state.get("active"))
        seconds = max(0, int(state.get("seconds", 0) or 0))
        minutes, rem = divmod(seconds, 60)
        self._countdown_var.set(f"{minutes:02d}:{rem:02d}")

        cycles = int(state.get("cycles", 0) or 0)
        if active:
            self._cycle_var.set(f"Ciclo {max(1, cycles)}")
        else:
            self._cycle_var.set("")

        status = state.get("status", "idle")
        if not active:
            self._status_var.set(
                "Pulsa Iniciar después de ingerir 15 g de hidratos de carbono."
            )
        elif status == "awaiting_recheck":
            self._status_var.set(
                "¡Han pasado 15 minutos! Revisa tu glucosa. Pulsa Tomado si necesitas otro ciclo."
            )
        else:
            self._status_var.set(
                "Cuenta regresiva en curso. Espera 15 minutos antes de volver a medir la glucosa."
            )

        self._update_buttons(state)

    def _update_buttons(self, state: Dict[str, Any]) -> None:
        active = bool(state.get("active"))
        if active:
            self._btn_start.configure(text="⟲ Reiniciar 15/15")
        else:
            self._btn_start.configure(text="▶ Iniciar 15/15")
        self._btn_taken.configure(state=tk.NORMAL if active else tk.DISABLED)
        self._btn_cancel.configure(state=tk.NORMAL if active else tk.DISABLED)
        self._btn_start.configure(state=tk.NORMAL)
