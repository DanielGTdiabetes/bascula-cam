from __future__ import annotations

import datetime as _dt
import tkinter as tk
from typing import Optional

from bascula.ui.overlay_base import OverlayBase
from bascula.ui.widgets import (
    COL_CARD,
    COL_TEXT,
    COL_ACCENT,
    COL_DANGER,
    COL_MUTED,
    FS_TITLE,
    FS_TEXT,
    BigButton,
    GhostButton,
)


class TimerOverlay(OverlayBase):
    """Floating timer used by the focus screen."""

    def __init__(self, parent, app, **kwargs):
        super().__init__(parent, **kwargs)
        self.app = app
        self._remaining = 0
        self._after: Optional[str] = None
        container = self.content()
        container.configure(padx=18, pady=16)

        tk.Label(
            container,
            text="Temporizador rápido",
            bg=COL_CARD,
            fg=COL_TEXT,
            font=("DejaVu Sans", FS_TITLE, "bold"),
        ).pack(pady=(0, 10))

        self.lbl = tk.Label(
            container,
            text="00:00",
            bg=COL_CARD,
            fg=COL_ACCENT,
            font=("DejaVu Sans Mono", FS_TITLE, "bold"),
        )
        self.lbl.pack(pady=8)

        btns = tk.Frame(container, bg=COL_CARD)
        btns.pack(pady=(0, 6))
        for sec in (60, 300, 600, 900):
            BigButton(btns, text=f"{sec // 60} min", command=lambda s=sec: self.start(s), micro=True).pack(
                side="left", padx=4
            )

        GhostButton(container, text="Cerrar", command=self.hide, micro=True).pack(pady=(8, 0))

    def hide(self):
        super().hide()
        if self._after:
            try:
                self.after_cancel(self._after)
            except Exception:
                pass
            self._after = None

    def start(self, seconds: int):
        self._remaining = int(seconds)
        try:
            self.app.show_mascot_message("timer_started", seconds, kind="info", priority=3, icon="⏱")
        except Exception:
            pass
        self._tick()

    def _tick(self):
        minutes, seconds = divmod(max(0, self._remaining), 60)
        self.lbl.configure(text=f"{minutes:02d}:{seconds:02d}")
        if self._remaining <= 0:
            self._notify_finished()
            return
        self._remaining -= 1
        self._after = self.after(1000, self._tick)

    def _notify_finished(self):
        self._play_beep()
        try:
            self.app.show_mascot_message("timer_finished", kind="success", priority=5, icon="⏱")
        except Exception:
            pass

    def _play_beep(self):
        try:
            audio = getattr(self.app, "audio", None)
            if audio:
                for _ in range(3):
                    audio.play_event("timer_beep")
        except Exception:
            pass


class HypoOverlay(OverlayBase):
    """Overlay explaining the 15/15 rule when a low BG is detected."""

    def __init__(self, parent, app, **kwargs) -> None:
        super().__init__(parent, **kwargs)
        self.app = app
        self._bg_value: Optional[int] = None
        frame = self.content()
        frame.configure(padx=24, pady=22)

        self.title = tk.Label(
            frame,
            text="Hipoglucemia",
            bg=COL_CARD,
            fg=COL_DANGER,
            font=("DejaVu Sans", FS_TITLE, "bold"),
        )
        self.title.pack(anchor="w")

        self.subtitle = tk.Label(
            frame,
            text="",
            bg=COL_CARD,
            fg=COL_TEXT,
            font=("DejaVu Sans", FS_TEXT, "bold"),
            justify="left",
            wraplength=420,
        )
        self.subtitle.pack(anchor="w", pady=(6, 12))

        self.info_lbl = tk.Label(
            frame,
            text=(
                "Regla 15/15: toma 15 g de hidratos, espera 15 minutos y vuelve a medir.\n"
                "Pulsa en iniciar para comenzar el temporizador."
            ),
            bg=COL_CARD,
            fg=COL_MUTED,
            font=("DejaVu Sans", FS_TEXT),
            justify="left",
            wraplength=460,
        )
        self.info_lbl.pack(anchor="w", pady=(0, 16))

        buttons = tk.Frame(frame, bg=COL_CARD)
        buttons.pack(fill="x")
        BigButton(buttons, text="Iniciar temporizador", command=self._start, micro=False).pack(side="left", padx=4)
        GhostButton(buttons, text="Cancelar", command=self.hide, micro=True).pack(side="right", padx=4)

    def present(self, bg_value: int) -> None:
        self._bg_value = int(bg_value)
        self.subtitle.configure(text=f"Glucosa detectada: {bg_value} mg/dL")
        self.show()

    def hide(self):
        super().hide()
        try:
            self.app.on_hypo_overlay_closed()
        except Exception:
            pass

    def _start(self) -> None:
        self.hide()
        try:
            self.app.start_hypo_timer()
        except Exception:
            pass


class TimerPopup(tk.Toplevel):
    """Dedicated countdown dialog used by the 15/15 rule flow."""

    def __init__(self, parent: tk.Misc, app, duration_s: int = 900) -> None:
        super().__init__(parent)
        self.withdraw()
        self.app = app
        self.default_duration = int(duration_s)
        self.remaining = self.default_duration
        self._job: Optional[str] = None
        self._started_at: Optional[_dt.datetime] = None

        self.title("Temporizador 15/15")
        self.configure(bg=COL_CARD)
        self.overrideredirect(True)
        try:
            self.attributes("-topmost", True)
        except Exception:
            pass

        body = tk.Frame(self, bg=COL_CARD)
        body.pack(fill="both", expand=True, padx=20, pady=20)

        tk.Label(
            body,
            text="Cuenta atrás",
            bg=COL_CARD,
            fg=COL_TEXT,
            font=("DejaVu Sans", FS_TITLE, "bold"),
        ).pack(pady=(0, 10))

        self.counter_lbl = tk.Label(
            body,
            text="15:00",
            bg=COL_CARD,
            fg=COL_ACCENT,
            font=("DejaVu Sans Mono", FS_TITLE, "bold"),
        )
        self.counter_lbl.pack(pady=(0, 12))

        self.status_var = tk.StringVar(value="")
        tk.Label(body, textvariable=self.status_var, bg=COL_CARD, fg=COL_MUTED, font=("DejaVu Sans", FS_TEXT)).pack()

        btns = tk.Frame(body, bg=COL_CARD)
        btns.pack(pady=(14, 0))
        BigButton(btns, text="Reiniciar", command=self.restart, micro=True).pack(side="left", padx=6)
        GhostButton(btns, text="Cancelar", command=self.close, micro=True).pack(side="right", padx=6)

    # ------------------------------------------------------------------ lifecycle
    def open(self, *, duration: Optional[int] = None) -> None:
        if duration is not None:
            self.default_duration = max(1, int(duration))
        self.restart()
        self._place_center()
        self.deiconify()

    def close(self) -> None:
        if self._job:
            try:
                self.after_cancel(self._job)
            except Exception:
                pass
            self._job = None
        self.withdraw()
        self.status_var.set("")
        try:
            self.app.on_hypo_timer_cancelled()
        except Exception:
            pass

    # ------------------------------------------------------------------ actions
    def restart(self) -> None:
        self.remaining = self.default_duration
        self._started_at = _dt.datetime.now()
        self.status_var.set("Temporizador en marcha")
        self._tick()
        try:
            self.app.on_hypo_timer_started()
        except Exception:
            pass

    def _tick(self) -> None:
        minutes, seconds = divmod(max(0, self.remaining), 60)
        self.counter_lbl.configure(text=f"{minutes:02d}:{seconds:02d}")
        if self.remaining <= 0:
            self.status_var.set("Tiempo cumplido. Comprueba tu glucosa")
            self._finish()
            return
        self.remaining -= 1
        self._job = self.after(1000, self._tick)

    def _finish(self) -> None:
        self._job = None
        try:
            self.app.on_hypo_timer_finished()
        except Exception:
            pass
        self.after(2200, self.withdraw)

    def _place_center(self) -> None:
        try:
            self.update_idletasks()
            root = self.master.winfo_toplevel()
            w = self.winfo_width() or 320
            h = self.winfo_height() or 180
            rx = root.winfo_rootx()
            ry = root.winfo_rooty()
            rw = root.winfo_width()
            rh = root.winfo_height()
            x = rx + (rw - w) // 2
            y = ry + (rh - h) // 2
            self.geometry(f"{w}x{h}+{x}+{y}")
        except Exception:
            pass

    def is_running(self) -> bool:
        return self._job is not None

    def remaining_seconds(self) -> int:
        return max(0, int(self.remaining))

