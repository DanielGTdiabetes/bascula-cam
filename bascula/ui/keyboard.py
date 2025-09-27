"""On-screen keyboards used across configuration screens."""
from __future__ import annotations

import tkinter as tk
from typing import Callable, Optional

try:
    from bascula.ui import widgets as theme
    COL_BG = getattr(theme, "COL_BG", "#111827")
    COL_CARD = getattr(theme, "COL_CARD", "#1f2937")
    COL_TEXT = getattr(theme, "COL_TEXT", "#f9fafb")
    COL_ACCENT = getattr(theme, "COL_ACCENT", "#2563eb")
    COL_ACCENT_LIGHT = getattr(theme, "COL_ACCENT_LIGHT", "#3b82f6")
except Exception:
    COL_BG = "#111827"
    COL_CARD = "#1f2937"
    COL_TEXT = "#f9fafb"
    COL_ACCENT = "#2563eb"
    COL_ACCENT_LIGHT = "#3b82f6"


class _BasePopup(tk.Toplevel):
    def __init__(self, parent: tk.Misc, *, title: str) -> None:
        super().__init__(parent)
        self.transient(parent.winfo_toplevel())
        self.title(title)
        self.configure(bg=COL_BG)
        self.resizable(False, False)
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self._cancel)
        self.bind("<Escape>", lambda _e: self._cancel())

    # Methods overridden by subclasses
    def _cancel(self) -> None:  # pragma: no cover - dynamic at runtime
        self.grab_release()
        self.destroy()


class TextKeyPopup(_BasePopup):
    """Alphanumeric keyboard with symbol support."""

    def __init__(
        self,
        parent: tk.Misc,
        *,
        title: str,
        initial: str = "",
        on_accept: Optional[Callable[[str], None]] = None,
        password: bool = False,
    ) -> None:
        super().__init__(parent, title=title)
        self._callback = on_accept
        self._password = password
        self._value = tk.StringVar(value=initial)
        self._layout = "letters"
        self._shift = False

        container = tk.Frame(self, bg=COL_CARD, padx=12, pady=12)
        container.pack(fill="both", expand=True)

        entry = tk.Entry(
            container,
            textvariable=self._value,
            show="*" if password else "",
            font=("DejaVu Sans", 16),
            width=26,
            bg=COL_CARD,
            fg=COL_TEXT,
            insertbackground=COL_TEXT,
            highlightthickness=1,
            highlightbackground=COL_ACCENT,
        )
        entry.pack(fill="x", pady=(0, 10))
        entry.focus_set()

        self._entry = entry

        keyboard = tk.Frame(container, bg=COL_CARD)
        keyboard.pack()
        self._keyboard_frame = keyboard

        self._build_keys()

        controls = tk.Frame(container, bg=COL_CARD)
        controls.pack(fill="x", pady=(12, 0))
        tk.Button(
            controls,
            text="Cancelar",
            command=self._cancel,
            bg=COL_CARD,
            fg=COL_TEXT,
            activebackground=COL_CARD,
            activeforeground=COL_TEXT,
            relief="flat",
            cursor="hand2",
        ).pack(side="left", padx=4)
        tk.Button(
            controls,
            text="Aceptar",
            command=self._accept,
            bg=COL_ACCENT,
            fg=COL_TEXT,
            activebackground=COL_ACCENT_LIGHT,
            activeforeground=COL_TEXT,
            relief="flat",
            cursor="hand2",
        ).pack(side="right", padx=4)

        self.wait_visibility()

    def _build_keys(self) -> None:
        for child in self._keyboard_frame.winfo_children():
            child.destroy()

        layouts = {
            "letters": [
                list("1234567890"),
                list("qwertyuiop"),
                list("asdfghjklñ"),
                list("zxcvbnm"),
            ],
            "symbols": [
                list("!@#$%&*()"),
                list("-_=+[]{}"),
                list(";:'\"\\|"),
                list(".,/?<>~"),
            ],
        }
        rows = layouts.get(self._layout, layouts["letters"])

        for rindex, row in enumerate(rows):
            fr = tk.Frame(self._keyboard_frame, bg=COL_CARD)
            fr.grid(row=rindex, column=0, pady=2)
            for ch in row:
                label = ch.upper() if self._shift and ch.isalpha() else ch
                btn = tk.Button(
                    fr,
                    text=label,
                    width=3,
                    height=1,
                    command=lambda c=ch: self._insert_char(c),
                    bg=COL_CARD,
                    fg=COL_TEXT,
                    activebackground=COL_ACCENT,
                    activeforeground=COL_TEXT,
                    relief="flat",
                    cursor="hand2",
                )
                btn.pack(side="left", padx=2)

        specials = tk.Frame(self._keyboard_frame, bg=COL_CARD)
        specials.grid(row=len(rows), column=0, pady=(6, 0))
        tk.Button(
            specials,
            text="Mayús" if not self._shift else "Mayús ⇧",
            command=self._toggle_shift,
            width=7,
            bg=COL_CARD,
            fg=COL_TEXT,
            activebackground=COL_ACCENT,
            activeforeground=COL_TEXT,
            relief="flat",
            cursor="hand2",
        ).pack(side="left", padx=2)
        tk.Button(
            specials,
            text="ABC" if self._layout == "symbols" else "123",
            command=self._toggle_layout,
            width=5,
            bg=COL_CARD,
            fg=COL_TEXT,
            activebackground=COL_ACCENT,
            activeforeground=COL_TEXT,
            relief="flat",
            cursor="hand2",
        ).pack(side="left", padx=2)
        tk.Button(
            specials,
            text="Espacio",
            command=lambda: self._insert_char(" "),
            width=10,
            bg=COL_CARD,
            fg=COL_TEXT,
            activebackground=COL_ACCENT,
            activeforeground=COL_TEXT,
            relief="flat",
            cursor="hand2",
        ).pack(side="left", padx=2)
        tk.Button(
            specials,
            text="⌫",
            command=self._backspace,
            width=3,
            bg=COL_CARD,
            fg=COL_TEXT,
            activebackground=COL_ACCENT,
            activeforeground=COL_TEXT,
            relief="flat",
            cursor="hand2",
        ).pack(side="left", padx=2)
        tk.Button(
            specials,
            text="Borrar",
            command=lambda: self._value.set(""),
            width=6,
            bg=COL_CARD,
            fg=COL_TEXT,
            activebackground=COL_ACCENT,
            activeforeground=COL_TEXT,
            relief="flat",
            cursor="hand2",
        ).pack(side="left", padx=2)

    def _toggle_layout(self) -> None:
        self._layout = "letters" if self._layout == "symbols" else "symbols"
        self._build_keys()

    def _toggle_shift(self) -> None:
        self._shift = not self._shift
        self._build_keys()

    def _insert_char(self, ch: str) -> None:
        char = ch.upper() if self._shift and ch.isalpha() else ch
        try:
            self._entry.insert("insert", char)
        except Exception:
            self._value.set(self._value.get() + char)
        if self._shift and ch.isalpha():
            self._shift = False
            self._build_keys()

    def _backspace(self) -> None:
        value = self._value.get()
        self._value.set(value[:-1])
        try:
            self._entry.icursor(tk.END)
        except Exception:
            pass

    def _accept(self) -> None:
        if self._callback:
            self._callback(self._value.get())
        self._cancel()


class NumericKeyPopup(_BasePopup):
    """Numeric keypad for timers and other number fields."""

    def __init__(
        self,
        parent: tk.Misc,
        *,
        title: str,
        initial: str = "",
        on_accept: Optional[Callable[[str], None]] = None,
        allow_negative: bool = False,
        allow_decimal: bool = False,
    ) -> None:
        super().__init__(parent, title=title)
        self._callback = on_accept
        self._allow_negative = allow_negative
        self._allow_decimal = allow_decimal
        self._value = tk.StringVar(value=initial)

        container = tk.Frame(self, bg=COL_CARD, padx=12, pady=12)
        container.pack(fill="both", expand=True)

        entry = tk.Entry(
            container,
            textvariable=self._value,
            font=("DejaVu Sans", 18),
            width=8,
            justify="center",
            bg=COL_CARD,
            fg=COL_TEXT,
            highlightthickness=1,
            highlightbackground=COL_ACCENT,
            insertbackground=COL_TEXT,
        )
        entry.pack(pady=(0, 10))
        entry.focus_set()
        self._entry = entry

        keypad = tk.Frame(container, bg=COL_CARD)
        keypad.pack()
        layout = [
            ["1", "2", "3"],
            ["4", "5", "6"],
            ["7", "8", "9"],
            ["-" if allow_negative else "", "0", "." if allow_decimal else ""],
        ]
        for rindex, row in enumerate(layout):
            fr = tk.Frame(keypad, bg=COL_CARD)
            fr.grid(row=rindex, column=0, pady=2)
            for ch in row:
                if not ch:
                    spacer = tk.Label(fr, text="", width=4, bg=COL_CARD)
                    spacer.pack(side="left", padx=2)
                    continue
                btn = tk.Button(
                    fr,
                    text=ch,
                    width=4,
                    command=lambda c=ch: self._insert_char(c),
                    bg=COL_CARD,
                    fg=COL_TEXT,
                    activebackground=COL_ACCENT,
                    activeforeground=COL_TEXT,
                    relief="flat",
                    cursor="hand2",
                )
                btn.pack(side="left", padx=2)

        controls = tk.Frame(container, bg=COL_CARD)
        controls.pack(fill="x", pady=(10, 0))
        tk.Button(
            controls,
            text="⌫",
            command=self._backspace,
            width=4,
            bg=COL_CARD,
            fg=COL_TEXT,
            activebackground=COL_ACCENT,
            activeforeground=COL_TEXT,
            relief="flat",
            cursor="hand2",
        ).pack(side="left", padx=2)
        tk.Button(
            controls,
            text="Borrar",
            command=lambda: self._value.set(""),
            width=6,
            bg=COL_CARD,
            fg=COL_TEXT,
            activebackground=COL_ACCENT,
            activeforeground=COL_TEXT,
            relief="flat",
            cursor="hand2",
        ).pack(side="left", padx=2)
        tk.Button(
            controls,
            text="Cancelar",
            command=self._cancel,
            bg=COL_CARD,
            fg=COL_TEXT,
            activebackground=COL_CARD,
            activeforeground=COL_TEXT,
            relief="flat",
            cursor="hand2",
        ).pack(side="right", padx=2)
        tk.Button(
            controls,
            text="Aceptar",
            command=self._accept,
            bg=COL_ACCENT,
            fg=COL_TEXT,
            activebackground=COL_ACCENT_LIGHT,
            activeforeground=COL_TEXT,
            relief="flat",
            cursor="hand2",
        ).pack(side="right", padx=2)

        self.wait_visibility()

    def _insert_char(self, ch: str) -> None:
        if ch == "-" and not self._allow_negative:
            return
        if ch == "." and not self._allow_decimal:
            return
        value = self._value.get()
        if ch == "-" and value.startswith("-"):
            self._value.set(value[1:])
            return
        if ch == "." and "." in value:
            return
        try:
            self._entry.insert("insert", ch)
        except Exception:
            self._value.set(value + ch)

    def _backspace(self) -> None:
        value = self._value.get()
        self._value.set(value[:-1])
        try:
            self._entry.icursor(tk.END)
        except Exception:
            pass

    def _accept(self) -> None:
        value = self._value.get()
        if self._callback:
            self._callback(value)
        self._cancel()


__all__ = ["TextKeyPopup", "NumericKeyPopup"]
