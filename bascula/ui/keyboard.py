from __future__ import annotations

import logging
import tkinter as tk
from typing import Callable, Optional

from .theme_ctk import (
    COLORS as HOLO_COLORS,
    CTK_AVAILABLE,
    create_button as holo_button,
    create_entry as holo_entry,
    create_frame as holo_frame,
    create_label as holo_label,
    font_tuple,
)
from .theme_holo import COLOR_ACCENT, COLOR_BG, COLOR_PRIMARY, COLOR_TEXT, FONT_UI, FONT_UI_BOLD

LOGGER = logging.getLogger(__name__)

if CTK_AVAILABLE:  # pragma: no cover - optional import at runtime
    try:
        from customtkinter import CTkToplevel as _BaseToplevel
    except Exception:  # pragma: no cover - safety
        _BaseToplevel = tk.Toplevel
else:
    _BaseToplevel = tk.Toplevel

if CTK_AVAILABLE:
    COL_BG = HOLO_COLORS["bg"]
    COL_CARD = HOLO_COLORS["surface"]
    COL_TEXT = HOLO_COLORS["text"]
    COL_ACCENT = HOLO_COLORS["accent"]
    COL_ACCENT_LIGHT = HOLO_COLORS["accent_soft"]
    TITLE_FONT = font_tuple(16, "bold")
    BODY_FONT = font_tuple(14)
    NUM_FONT = font_tuple(20, "bold")
else:
    COL_BG = COLOR_BG
    COL_CARD = "#141414"
    COL_TEXT = COLOR_TEXT
    COL_ACCENT = COLOR_PRIMARY
    COL_ACCENT_LIGHT = COLOR_ACCENT
    TITLE_FONT = (FONT_UI_BOLD[0], 16, "bold")
    BODY_FONT = (FONT_UI[0], 14)
    NUM_FONT = ("DejaVu Sans Mono", 18, "bold")


class _BasePopup(_BaseToplevel):
    """Base popup window with holographic styling."""

    def __init__(self, parent: tk.Misc, *, title: str) -> None:
        top = parent.winfo_toplevel() if hasattr(parent, "winfo_toplevel") else parent
        super().__init__(top)
        self.withdraw()
        self._parent = top
        self._title = title
        self._preferred_width: int | None = None
        self._preferred_height: int | None = None

        try:
            self.title(title)
        except Exception:
            pass

        if CTK_AVAILABLE:
            try:
                self.configure(fg_color=COL_CARD)
            except Exception:
                pass
        else:
            self.configure(bg=COL_CARD)

        self.resizable(False, False)
        self.transient(top)
        self.protocol("WM_DELETE_WINDOW", self._cancel)
        self.bind("<Escape>", lambda _e: self._cancel())
        self.bind("<Return>", lambda _e: self._accept_if_available())

        header = holo_frame(self, fg_color=COL_CARD)
        header.pack(fill="x", padx=12, pady=(12, 0))
        self._title_label = holo_label(
            header,
            text=title,
            font=TITLE_FONT,
            text_color=COL_ACCENT,
        )
        self._title_label.pack(side="left")

        self._accept_button = holo_button(
            header,
            text="Aceptar",
            command=self._accept_if_available,
            width=100 if CTK_AVAILABLE else 8,
        )
        self._accept_button.pack(side="right", padx=4)

        self._cancel_button = holo_button(
            header,
            text="Cancelar",
            command=self._cancel,
            width=100 if CTK_AVAILABLE else 8,
        )
        self._cancel_button.pack(side="right", padx=4)

        self._content = holo_frame(self, fg_color=COL_CARD)
        self._content.pack(fill="both", expand=True, padx=12, pady=12)

    def _safe_show(self) -> None:
        try:
            self.withdraw()
        except Exception:
            pass
        try:
            self.update_idletasks()
        except Exception:
            pass

        parent = self._parent if self._parent is not None else self
        try:
            px = parent.winfo_rootx()
            py = parent.winfo_rooty()
            pw = parent.winfo_width()
            ph = parent.winfo_height()
            if pw <= 1 or ph <= 1:
                parent.update_idletasks()
                pw = max(pw, parent.winfo_width())
                ph = max(ph, parent.winfo_height())
        except Exception:
            px = py = 0
            pw = self.winfo_screenwidth()
            ph = self.winfo_screenheight()

        width = self._preferred_width
        height = self._preferred_height
        if width is None:
            width = max(320, int(pw * 0.65))
        if height is None:
            height = max(260, int(ph * 0.55))

        x = px + (pw - width) // 2
        y = py + (ph - height) // 2
        geometry = f"{int(width)}x{int(height)}+{max(0, int(x))}+{max(0, int(y))}"
        try:
            self.geometry(geometry)
        except Exception:
            pass

        try:
            self.deiconify()
        except Exception:
            pass
        try:
            self.wait_visibility()
        except Exception:
            pass
        try:
            self.lift()
        except Exception:
            pass
        try:
            self.attributes("-topmost", True)
        except Exception:
            pass
        try:
            self.focus_force()
        except Exception:
            pass
        try:
            self.grab_set()
        except Exception:
            pass
        try:
            self.after(150, lambda: self._restore_focus())
        except Exception:
            pass
        try:
            LOGGER.debug("%s shown at %s", self.__class__.__name__, self.geometry())
        except Exception:
            pass

    def _restore_focus(self) -> None:
        try:
            self.attributes("-topmost", True)
        except Exception:
            pass
        try:
            self.lift()
            self.focus_force()
        except Exception:
            pass

    def _accept_if_available(self) -> None:
        callback = getattr(self, "_accept", None)
        if callable(callback):
            callback()

    def _cancel(self) -> None:
        try:
            self.grab_release()
        except Exception:
            pass
        self.destroy()


class TextKeyPopup(_BasePopup):
    """Alphanumeric keyboard with holographic theming."""

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

        container = holo_frame(self._content, fg_color=COL_CARD)
        container.pack(fill="both", expand=True)

        entry = holo_entry(
            container,
            textvariable=self._value,
            show="*" if password else "",
            font=BODY_FONT,
            justify="left",
        )
        entry.pack(fill="x", pady=(0, 12))
        entry.focus_set()
        self._entry = entry

        keyboard = holo_frame(container, fg_color=COL_CARD)
        keyboard.pack(expand=True)
        self._keyboard_frame = keyboard

        self._build_keys()

        controls = holo_frame(container, fg_color=COL_CARD)
        controls.pack(fill="x", pady=(12, 0))

        for text, command in (
            ("Cancelar", self._cancel),
            ("Aceptar", self._accept),
        ):
            btn = holo_button(
                controls,
                text=text,
                command=command,
                width=120 if CTK_AVAILABLE else 10,
            )
            side = "left" if text == "Cancelar" else "right"
            btn.pack(side=side, padx=4)

        self._safe_show()

    def _build_keys(self) -> None:
        for child in list(self._keyboard_frame.winfo_children()):
            child.destroy()

        layouts = {
            "letters": [
                list("1234567890"),
                list("qwertyuiop"),
                list("asdfghjklñ"),
                list("zxcvbnm"),
            ],
            "symbols": [
                list("!@#$%^&*()"),
                list("-_=+[]{}"),
                list(";:'\"\\|"),
                list(",./?~`"),
            ],
        }
        rows = layouts.get(self._layout, layouts["letters"])

        for rindex, row in enumerate(rows):
            row_frame = holo_frame(self._keyboard_frame, fg_color=COL_CARD)
            row_frame.grid(row=rindex, column=0, pady=2)
            for ch in row:
                label = ch.upper() if self._shift and ch.isalpha() else ch
                width = 70 if CTK_AVAILABLE else 3
                btn = holo_button(
                    row_frame,
                    text=label,
                    command=lambda c=ch: self._insert_char(c),
                    width=width,
                )
                btn.pack(side="left", padx=2)

        specials = holo_frame(self._keyboard_frame, fg_color=COL_CARD)
        specials.grid(row=len(rows), column=0, pady=(8, 0))

        def _add_button(text: str, command: Callable[[], None], width: int = 70) -> None:
            btn = holo_button(
                specials,
                text=text,
                command=command,
                width=width if CTK_AVAILABLE else 6,
            )
            btn.pack(side="left", padx=4)

        _add_button("Mayús" if not self._shift else "Mayús ⇧", self._toggle_shift)
        _add_button("ABC" if self._layout == "symbols" else "123", self._toggle_layout)
        _add_button("Espacio", lambda: self._insert_char(" "), width=140)
        _add_button("⌫", self._backspace, width=70)
        _add_button("Borrar", lambda: self._value.set(""), width=90)

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
    """Numeric keypad styled with the holographic theme."""

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

        container = holo_frame(self._content, fg_color=COL_CARD)
        container.pack(fill="both", expand=True)

        entry = holo_entry(
            container,
            textvariable=self._value,
            font=NUM_FONT,
            justify="center",
        )
        entry.pack(pady=(0, 12))
        entry.focus_set()
        self._entry = entry

        keypad = holo_frame(container, fg_color=COL_CARD)
        keypad.pack(expand=True)
        layout = [
            ["1", "2", "3"],
            ["4", "5", "6"],
            ["7", "8", "9"],
            ["-" if allow_negative else "", "0", "." if allow_decimal else ""],
        ]

        for rindex, row in enumerate(layout):
            row_frame = holo_frame(keypad, fg_color=COL_CARD)
            row_frame.grid(row=rindex, column=0, pady=3)
            for ch in row:
                if not ch:
                    spacer = holo_label(row_frame, text="", width=20 if CTK_AVAILABLE else 2)
                    spacer.pack(side="left", padx=4)
                    continue
                btn = holo_button(
                    row_frame,
                    text=ch,
                    command=lambda c=ch: self._insert_char(c),
                    width=80 if CTK_AVAILABLE else 4,
                )
                btn.pack(side="left", padx=4)

        controls = holo_frame(container, fg_color=COL_CARD)
        controls.pack(fill="x", pady=(10, 0))

        for text, command, width in (
            ("⌫", self._backspace, 80),
            ("Borrar", lambda: self._value.set(""), 110),
        ):
            btn = holo_button(
                controls,
                text=text,
                command=command,
                width=width if CTK_AVAILABLE else 6,
            )
            btn.pack(side="left", padx=4)

        for text, command in (
            ("Cancelar", self._cancel),
            ("Aceptar", self._accept),
        ):
            btn = holo_button(
                controls,
                text=text,
                command=command,
                width=120 if CTK_AVAILABLE else 8,
            )
            side = "right" if text == "Aceptar" else "right"
            btn.pack(side=side, padx=4)

        self._preferred_width = 320
        self._preferred_height = 420
        self._safe_show()

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
        if self._callback:
            self._callback(self._value.get())
        self._cancel()


__all__ = ["TextKeyPopup", "NumericKeyPopup"]

