"""Reusable modal dialog to configure the kitchen timer."""
from __future__ import annotations

from typing import Callable, Optional

import tkinter as tk
from tkinter import ttk


class TimerDialog(tk.Toplevel):
    """Modal dialog that gathers timer information in a safe way."""

    MAX_MINUTES = 120

    def __init__(
        self,
        parent: tk.Misc,
        on_ok: Optional[Callable[[int], None]] = None,
        *,
        width: int = 360,
        height: int = 260,
        on_stop: Optional[Callable[[], None]] = None,
        running: bool = False,
        initial_seconds: int = 0,
    ) -> None:
        super().__init__(parent)
        self.withdraw()

        self._parent = parent
        self._on_ok = on_ok
        self._on_stop = on_stop
        self._running = bool(running)
        self._width = max(200, int(width))
        self._height = max(180, int(height))
        self._modal_active = False

        self.overrideredirect(False)
        toplevel = parent.winfo_toplevel() if hasattr(parent, "winfo_toplevel") else parent
        try:
            self.transient(toplevel)
        except Exception:
            pass
        try:
            self.attributes("-topmost", True)
        except Exception:
            pass

        self.title("Temporizador")
        self.resizable(False, False)

        self._minutes_var = tk.StringVar()
        self._seconds_var = tk.StringVar()
        self._status_var = tk.StringVar(value="")

        self._build_ui()

        self.protocol("WM_DELETE_WINDOW", self._on_cancel)
        self.bind("<Escape>", lambda _e: self._on_cancel())
        self.bind("<Visibility>", self._on_visibility, add=True)

        self.set_initial_seconds(initial_seconds)
        self._update_status()

    # ------------------------------------------------------------------
    def set_initial_seconds(self, total_seconds: int) -> None:
        """Populate the fields from a total seconds value."""

        total = max(0, int(total_seconds))
        minutes = min(self.MAX_MINUTES, total // 60)
        seconds = min(59, total % 60)
        if minutes > self.MAX_MINUTES:
            minutes = self.MAX_MINUTES
        self._minutes_var.set(f"{minutes:02d}")
        self._seconds_var.set(f"{seconds:02d}")

    def set_running(self, running: bool) -> None:
        self._running = bool(running)
        self._update_status()

    # ------------------------------------------------------------------
    def show_modal(self) -> None:
        """Show the dialog as a modal window."""

        if not int(self.winfo_exists()):
            return

        if self._modal_active:
            self.deiconify()
            self.lift()
            self.focus_force()
            return

        self._modal_active = True
        try:
            self.update_idletasks()
            self._center_on_parent()
            self.deiconify()
            self.lift()
            try:
                self.focus_force()
            except Exception:
                pass
            self.grab_set()
            try:
                self.attributes("-topmost", False)
            except Exception:
                pass
            self.wait_window(self)
        finally:
            self._modal_active = False

    # ------------------------------------------------------------------
    def _center_on_parent(self) -> None:
        parent = self._parent.winfo_toplevel() if hasattr(self._parent, "winfo_toplevel") else self._parent
        try:
            parent.update_idletasks()
        except Exception:
            pass

        try:
            pw = int(parent.winfo_width())
            ph = int(parent.winfo_height())
        except Exception:
            pw, ph = 0, 0

        if pw <= 0 or ph <= 0:
            try:
                parent.update_idletasks()
                pw = int(parent.winfo_width())
                ph = int(parent.winfo_height())
            except Exception:
                pw, ph = 1024, 600

        try:
            px = int(parent.winfo_rootx())
            py = int(parent.winfo_rooty())
        except Exception:
            px, py = 0, 0

        w = self._width
        h = self._height
        screen_w = max(1024, int(self.winfo_screenwidth()))
        screen_h = max(600, int(self.winfo_screenheight()))

        x = px + (pw - w) // 2
        y = py + (ph - h) // 2

        max_x = screen_w - w
        max_y = screen_h - h
        x = max(0, min(x, max_x))
        y = max(0, min(y, max_y))

        self.geometry(f"{w}x{h}+{x}+{y}")

    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        container = ttk.Frame(self, padding=20)
        container.pack(fill="both", expand=True)

        title = ttk.Label(container, text="Temporizador", font=("TkDefaultFont", 16, "bold"))
        title.pack(pady=(0, 12))

        display = ttk.Label(container, text="00:00", font=("TkFixedFont", 28, "bold"))
        display.pack(pady=(0, 12))

        self._minutes_var.trace_add("write", lambda *_: self._sync_display(display))
        self._seconds_var.trace_add("write", lambda *_: self._sync_display(display))
        self._sync_display(display)

        form = ttk.Frame(container)
        form.pack(fill="x", pady=(0, 12))

        minutes_frame = ttk.Frame(form)
        minutes_frame.pack(side="left", expand=True, fill="x", padx=(0, 6))
        ttk.Label(minutes_frame, text="Minutos").pack(anchor="w", pady=(0, 4))
        minutes_vcmd = (self.register(self._validate_minutes), "%P")
        minutes_entry = ttk.Entry(
            minutes_frame,
            textvariable=self._minutes_var,
            justify="center",
            validate="key",
            validatecommand=minutes_vcmd,
            width=4,
        )
        minutes_entry.pack(fill="x")

        seconds_frame = ttk.Frame(form)
        seconds_frame.pack(side="left", expand=True, fill="x", padx=(6, 0))
        ttk.Label(seconds_frame, text="Segundos").pack(anchor="w", pady=(0, 4))
        seconds_vcmd = (self.register(self._validate_seconds), "%P")
        seconds_entry = ttk.Entry(
            seconds_frame,
            textvariable=self._seconds_var,
            justify="center",
            validate="key",
            validatecommand=seconds_vcmd,
            width=4,
        )
        seconds_entry.pack(fill="x")

        status = ttk.Label(container, textvariable=self._status_var, wraplength=self._width - 40)
        status.pack(fill="x", pady=(4, 12))

        buttons = ttk.Frame(container)
        buttons.pack(fill="x", pady=(4, 0))

        cancel = ttk.Button(buttons, text="Cancelar", command=self._on_cancel)
        cancel.pack(side="left", expand=True, fill="x", padx=(0, 6))

        if self._on_stop is not None:
            stop_btn = ttk.Button(buttons, text="Detener", command=self._on_stop_clicked)
            stop_btn.pack(side="left", expand=True, fill="x", padx=3)
            self._stop_button = stop_btn
        else:
            self._stop_button = None

        ok = ttk.Button(buttons, text="Aceptar", command=self._on_ok_clicked)
        ok.pack(side="left", expand=True, fill="x", padx=(6, 0))

        self._default_focus = minutes_entry

    # ------------------------------------------------------------------
    def _on_visibility(self, _event: tk.Event | None = None) -> None:
        try:
            if self._default_focus is not None:
                self._default_focus.focus_set()
        except Exception:
            pass

    def _sync_display(self, label: ttk.Label) -> None:
        minutes, seconds = self._parsed_time()
        label.configure(text=f"{minutes:02d}:{seconds:02d}")
        self._update_status()

    def _update_status(self) -> None:
        if self._running:
            self._status_var.set("Temporizador en marcha")
        else:
            self._status_var.set("Configura el tiempo y pulsa aceptar")

        if self._stop_button is not None:
            if self._running:
                self._stop_button.state(["!disabled"])
            else:
                self._stop_button.state(["disabled"])

    def _validate_minutes(self, value: str) -> bool:
        if value == "":
            return True
        if not value.isdigit():
            return False
        return len(value) <= 3

    def _validate_seconds(self, value: str) -> bool:
        if value == "":
            return True
        if not value.isdigit():
            return False
        if len(value) > 2:
            return False
        if value and int(value) > 59:
            return False
        return True

    def _parsed_time(self) -> tuple[int, int]:
        try:
            minutes = int(self._minutes_var.get() or 0)
        except (TypeError, ValueError):
            minutes = 0
        try:
            seconds = int(self._seconds_var.get() or 0)
        except (TypeError, ValueError):
            seconds = 0

        minutes = max(0, min(minutes, self.MAX_MINUTES))
        seconds = max(0, min(seconds, 59))
        return minutes, seconds

    def _collect_seconds(self) -> Optional[int]:
        minutes, seconds = self._parsed_time()
        if minutes > self.MAX_MINUTES:
            self._minutes_var.set(f"{self.MAX_MINUTES:02d}")
            return None
        total = minutes * 60 + seconds
        if total <= 0:
            return 0
        return min(total, self.MAX_MINUTES * 60)

    # ------------------------------------------------------------------
    def _on_ok_clicked(self) -> None:
        total = self._collect_seconds()
        if total is None:
            return
        if self._on_ok is not None:
            try:
                self._on_ok(total)
            except Exception:
                pass
        self._close_dialog()

    def _on_stop_clicked(self) -> None:
        if self._on_stop is not None:
            try:
                self._on_stop()
            except Exception:
                pass
        self._close_dialog()

    def _on_cancel(self) -> None:
        self._close_dialog()

    def _close_dialog(self) -> None:
        try:
            self.grab_release()
        except Exception:
            pass
        try:
            self.destroy()
        except Exception:
            pass


__all__ = ["TimerDialog"]

