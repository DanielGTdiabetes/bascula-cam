"""Neon-styled numeric keypad widgets for the Báscula UI."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable, Optional

from . import theme_holo

__all__ = ["NeoKeypad"]


class NeoKeypad(ttk.Frame):
    """A neon themed keypad for entering timer durations."""

    def __init__(
        self,
        master: tk.Misc,
        *,
        on_digit: Optional[Callable[[str], None]] = None,
        on_backspace: Optional[Callable[[], None]] = None,
        on_clear: Optional[Callable[[], None]] = None,
        on_accept: Optional[Callable[[], None]] = None,
        on_cancel: Optional[Callable[[], None]] = None,
    ) -> None:
        super().__init__(master, style="Timer.Keypad.TFrame")

        self._on_digit = on_digit or (lambda value: None)
        self._on_backspace = on_backspace or (lambda: None)
        self._on_clear = on_clear or (lambda: None)
        self._on_accept = on_accept or (lambda: None)
        self._on_cancel = on_cancel or (lambda: None)

        style = theme_holo.get_style(master)
        style.configure(
            "Timer.Keypad.TFrame",
            background=theme_holo.COLOR_BG,
        )

        grid = ttk.Frame(self, style="Timer.KeypadInner.TFrame")
        grid.pack(fill="both", expand=True)
        style.configure(
            "Timer.KeypadInner.TFrame",
            background=theme_holo.COLOR_SURFACE,
        )

        neon = theme_holo.neon_border(grid, padding=12, radius=18, color=theme_holo.PALETTE["neon_blue"])
        if neon is not None:
            neon.lower()

        button_specs = [
            ("1", self._handle_digit),
            ("2", self._handle_digit),
            ("3", self._handle_digit),
            ("4", self._handle_digit),
            ("5", self._handle_digit),
            ("6", self._handle_digit),
            ("7", self._handle_digit),
            ("8", self._handle_digit),
            ("9", self._handle_digit),
            ("Borrar", self._handle_backspace),
            ("0", self._handle_digit),
            ("Aceptar", self._handle_accept),
        ]

        self._default_focus: Optional[tk.Widget] = None

        for index, (label, handler) in enumerate(button_specs):
            row = index // 3
            column = index % 3
            button = theme_holo.create_neon_button(
                grid,
                text=label,
                command=lambda l=label, h=handler: h(l),
                accent=label == "Aceptar",
                danger=label == "Borrar",
            )
            button.grid(row=row, column=column, sticky="nsew", padx=8, pady=8)
            if self._default_focus is None and label == "7":
                self._default_focus = button
            if label == "Borrar":
                button.bind("<Double-Button-1>", self._handle_clear, add=True)
                button.bind("<ButtonPress-1>", self._start_clear_timer, add=True)
                button.bind("<ButtonRelease-1>", self._cancel_clear_timer, add=True)

        for column in range(3):
            grid.grid_columnconfigure(column, weight=1)
        for row in range(4):
            grid.grid_rowconfigure(row, weight=1)

        cancel_container = ttk.Frame(self, style="Timer.KeypadCancel.TFrame")
        cancel_container.pack(fill="x", pady=(16, 0))
        style.configure(
            "Timer.KeypadCancel.TFrame",
            background=theme_holo.COLOR_BG,
        )

        cancel_button = theme_holo.create_neon_button(
            cancel_container,
            text="Cancelar",
            command=self._handle_cancel,
            width=14,
        )
        cancel_button.pack(fill="x")
        self._cancel_button: tk.Widget = cancel_button

        self._clear_after: Optional[str] = None

    # ------------------------------------------------------------------
    def focus_keypad(self) -> None:
        try:
            target = self._default_focus or self._cancel_button
            target.focus_set()
        except Exception:
            pass

    # ------------------------------------------------------------------
    def _handle_digit(self, label: str) -> None:
        if label.isdigit():
            self._on_digit(label)

    def _handle_backspace(self, _label: str) -> None:
        self._on_backspace()

    def _handle_accept(self, _label: str) -> None:
        self._on_accept()

    def _handle_cancel(self) -> None:
        self._on_cancel()

    def _handle_clear(self, _event: tk.Event) -> None:
        self._on_clear()

    def _start_clear_timer(self, _event: tk.Event) -> None:
        widget = self.winfo_toplevel()
        if widget is None:
            return
        if self._clear_after is not None:
            try:
                widget.after_cancel(self._clear_after)
            except Exception:
                pass
        self._clear_after = widget.after(600, self._on_clear)

    def _cancel_clear_timer(self, _event: tk.Event) -> None:
        widget = self.winfo_toplevel()
        if widget is None or self._clear_after is None:
            return
        try:
            widget.after_cancel(self._clear_after)
        except Exception:
            pass
        self._clear_after = None
