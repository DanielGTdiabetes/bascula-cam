"""Modal timer dialog tailored for the holographic theme."""
from __future__ import annotations

import tkinter as tk
from typing import Callable, Iterable, Optional

from ..theme_ctk import CTK_AVAILABLE, ctk
from ..theme_holo import (
    COLOR_ACCENT,
    COLOR_BG,
    COLOR_PRIMARY,
    COLOR_TEXT,
    FONT_BODY_BOLD,
    FONT_DIGITS,
    PALETTE,
    create_neon_button,
    format_mmss,
)

DIALOG_BG = "#0b0f14"
_TEXT_MUTED = PALETTE.get("text_muted", "#98A2B3")
_BUTTON_RADIUS = 24
_KEY_ROWS: tuple[tuple[str, ...], ...] = (
    ("7", "8", "9"),
    ("4", "5", "6"),
    ("1", "2", "3"),
    ("00", "0", "⌫"),
)
_PRESETS: tuple[tuple[str, int], ...] = (
    ("30 s", 30),
    ("1 min", 60),
    ("3 min", 180),
    ("5 min", 300),
)


class TimerDialog(ctk.CTkToplevel if CTK_AVAILABLE and ctk is not None else tk.Toplevel):
    """Dark neon-styled modal dialog used to collect timer values."""

    def __init__(
        self,
        parent: tk.Misc,
        *,
        on_accept: Callable[[int], None],
        on_cancel: Optional[Callable[[], None]] = None,
    ) -> None:
        super().__init__(parent)
        self.withdraw()

        if CTK_AVAILABLE and ctk is not None:
            try:
                ctk.set_appearance_mode("dark")
            except Exception:
                pass

        self.title("Temporizador")
        self.resizable(False, False)
        self.configure(bg=DIALOG_BG)
        try:
            self.configure(fg_color=DIALOG_BG)
        except Exception:
            pass

        self._parent = parent
        self._on_accept_cb = on_accept
        self._on_cancel_cb = on_cancel
        self._digits = ""
        self._display_var = tk.StringVar(value=format_mmss(0))
        self._status_var = tk.StringVar(value="")
        self._accept_button: tk.Misc | None = None

        self._build_ui()

        self.bind("<Map>", lambda _e: self._restore_focus(), add=True)
        self.bind("<Escape>", lambda _e: self._on_cancel(), add=True)
        self.bind("<Return>", lambda _e: self._handle_accept(), add=True)
        self.bind("<KP_Enter>", lambda _e: self._handle_accept(), add=True)
        self.bind("<KeyPress>", self._handle_keypress, add=True)
        self.bind("<Destroy>", self._release_grab, add=True)
        self.protocol("WM_DELETE_WINDOW", self._on_cancel)

    # ------------------------------------------------------------------
    def present(self, *, initial_seconds: Optional[int] = None) -> None:
        """Show the dialog centred over its parent and grab focus."""

        if initial_seconds is not None:
            self._set_seconds(initial_seconds)
        self._update_display()

        self.deiconify()
        self.transient(self._parent)
        self.lift()
        try:
            self.attributes("-topmost", True)
            self.after(100, lambda: self._drop_topmost())
        except Exception:
            pass
        self._center_on_parent()
        self._restore_focus()
        self._take_grab()

    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        container = tk.Frame(self, bg=DIALOG_BG, highlightthickness=0, bd=0)
        container.pack(fill="both", expand=True, padx=32, pady=28)

        title = tk.Label(
            container,
            text="Temporizador",
            bg=DIALOG_BG,
            fg=COLOR_PRIMARY,
            font=_resolve_font(FONT_BODY_BOLD, fallback=("DejaVu Sans", 16, "bold")),
        )
        title.pack(pady=(0, 18))

        display = tk.Label(
            container,
            textvariable=self._display_var,
            bg=DIALOG_BG,
            fg=PALETTE.get("accent", COLOR_ACCENT),
            font=_resolve_font(FONT_DIGITS, fallback=("DejaVu Sans Mono", 40, "bold")),
        )
        display.pack(fill="x", pady=(0, 6))

        status = tk.Label(
            container,
            textvariable=self._status_var,
            bg=DIALOG_BG,
            fg=_TEXT_MUTED,
            font=_resolve_font(FONT_BODY_BOLD, fallback=("DejaVu Sans", 11)),
        )
        status.pack(fill="x", pady=(0, 12))

        body = tk.Frame(container, bg=DIALOG_BG)
        body.pack(fill="both", expand=True)

        presets_frame = tk.Frame(body, bg=DIALOG_BG)
        presets_frame.pack(side="left", fill="y", padx=(0, 18))
        for label, value in _PRESETS:
            btn = self._create_button(
                presets_frame,
                text=label,
                command=lambda seconds=value: self._apply_preset(seconds),
                width=140,
                height=44,
            )
            btn.pack(fill="x", pady=6)

        keypad_frame = tk.Frame(body, bg=DIALOG_BG)
        keypad_frame.pack(side="right", fill="both", expand=True)
        for r_index, row in enumerate(_KEY_ROWS):
            keypad_frame.grid_rowconfigure(r_index, weight=1)
            for c_index, key in enumerate(row):
                keypad_frame.grid_columnconfigure(c_index, weight=1)
                button = self._create_button(
                    keypad_frame,
                    text=key,
                    command=lambda value=key: self._handle_key(value),
                    width=88,
                    height=56,
                )
                button.grid(row=r_index, column=c_index, padx=6, pady=6, sticky="nsew")

        actions = tk.Frame(container, bg=DIALOG_BG)
        actions.pack(fill="x", pady=(18, 0))

        cancel_btn = self._create_button(
            actions,
            text="Cancelar",
            command=self._on_cancel,
            width=150,
            height=48,
            secondary=True,
        )
        cancel_btn.pack(side="left", expand=True, fill="x", padx=(0, 8))

        clear_btn = self._create_button(
            actions,
            text="Borrar",
            command=self._handle_clear,
            width=150,
            height=48,
            secondary=True,
        )
        clear_btn.pack(side="left", expand=True, fill="x", padx=8)

        accept_btn = self._create_button(
            actions,
            text="Aceptar",
            command=self._handle_accept,
            width=150,
            height=48,
            primary=True,
        )
        accept_btn.pack(side="left", expand=True, fill="x", padx=(8, 0))
        self._accept_button = accept_btn
        self._set_accept_state(False)

    def _create_button(
        self,
        master: tk.Misc,
        *,
        text: str,
        command: Callable[[], None],
        width: int,
        height: int,
        primary: bool = False,
        secondary: bool = False,
    ) -> tk.Misc:
        if CTK_AVAILABLE and ctk is not None:
            base_color = PALETTE.get("primary", COLOR_PRIMARY) if primary else DIALOG_BG
            hover = PALETTE.get("accent", COLOR_ACCENT)
            text_color = COLOR_BG if primary else PALETTE.get("primary", COLOR_PRIMARY)
            if secondary:
                text_color = PALETTE.get("text", COLOR_TEXT)
            button = ctk.CTkButton(
                master,
                text=text,
                command=command,
                width=width,
                height=height,
                fg_color=base_color if primary else DIALOG_BG,
                hover_color=hover,
                border_width=2,
                border_color=PALETTE.get("neon_blue", COLOR_PRIMARY),
                corner_radius=_BUTTON_RADIUS,
                text_color=text_color,
                font=_resolve_font(FONT_BODY_BOLD, fallback=("DejaVu Sans", 13, "bold")),
            )
            if secondary and not primary:
                button.configure(
                    fg_color=DIALOG_BG,
                    hover_color=_mix_color(DIALOG_BG, hover, 0.4),
                    text_color=PALETTE.get("text", COLOR_TEXT),
                )
            return button

        button = create_neon_button(
            master,
            text=text,
            command=command,
            width=max(int(width / 10), 8),
            height=max(int(height / 10), 2),
            accent=primary,
        )
        try:
            button.configure(relief="flat", bd=0, highlightthickness=2)
            button.configure(highlightbackground=PALETTE.get("neon_blue", COLOR_PRIMARY))
            button.configure(highlightcolor=PALETTE.get("neon_blue", COLOR_PRIMARY))
        except Exception:
            pass
        if secondary and not primary:
            try:
                button.configure(fg=PALETTE.get("text", COLOR_TEXT))
            except Exception:
                pass
        return button

    # ------------------------------------------------------------------
    def _handle_key(self, value: str) -> None:
        if value == "⌫":
            self._backspace()
            return
        self._append_digits("00" if value == "00" else value)

    def _handle_keypress(self, event: tk.Event) -> None:  # pragma: no cover - direct UI input
        if not event.char:
            if event.keysym == "BackSpace":
                self._backspace()
            return
        if event.char.isdigit():
            self._append_digits(event.char)

    def _append_digits(self, chunk: str) -> None:
        if not chunk:
            return
        cleaned = "".join(ch for ch in chunk if ch.isdigit())
        if not cleaned:
            return
        self._digits = (self._digits + cleaned)[-4:]
        self._status_var.set("")
        self._update_display()

    def _backspace(self) -> None:
        self._digits = self._digits[:-1]
        self._update_display()

    def _handle_clear(self) -> None:
        self._digits = ""
        self._status_var.set("")
        self._update_display()

    def _apply_preset(self, seconds: int) -> None:
        self._set_seconds(seconds)
        self._status_var.set("")
        self._update_display()

    def _set_seconds(self, seconds: int) -> None:
        safe_value = max(0, int(seconds))
        if safe_value == 0:
            self._digits = ""
        else:
            minutes, secs = divmod(safe_value, 60)
            minutes = max(0, min(minutes, 99))
            secs = max(0, min(secs, 59))
            self._digits = f"{minutes:02d}{secs:02d}"

    def _parse_seconds(self) -> int:
        if not self._digits:
            return 0
        digits = self._digits.zfill(2)
        if len(digits) <= 2:
            return int(digits)
        minutes = int(digits[:-2]) if digits[:-2] else 0
        seconds = int(digits[-2:])
        return minutes * 60 + seconds

    def _update_display(self) -> None:
        seconds = self._parse_seconds()
        self._display_var.set(format_mmss(seconds))
        self._set_accept_state(seconds > 0)

    def _set_accept_state(self, enabled: bool) -> None:
        button = self._accept_button
        if button is None:
            return
        state = "normal" if enabled else "disabled"
        try:
            button.configure(state=state)
        except Exception:
            try:
                button.configure(state=tk.NORMAL if enabled else tk.DISABLED)
            except Exception:
                pass

    def _handle_accept(self) -> None:
        seconds = self._parse_seconds()
        if seconds <= 0:
            self._status_var.set("Selecciona un tiempo válido")
            self._set_accept_state(False)
            return
        try:
            self._on_accept_cb(seconds)
        except Exception:
            pass
        self._close()

    def _on_cancel(self) -> None:
        if self._on_cancel_cb is not None:
            try:
                self._on_cancel_cb()
            except Exception:
                pass
        self._close()

    def _close(self) -> None:
        self._release_grab()
        try:
            self.destroy()
        except Exception:
            pass

    def _restore_focus(self) -> None:
        try:
            self.focus_force()
        except Exception:
            pass

    def _drop_topmost(self) -> None:
        try:
            self.attributes("-topmost", False)
        except Exception:
            pass

    def _center_on_parent(self) -> None:
        parent = self._parent
        try:
            self.update_idletasks()
        except Exception:
            pass
        try:
            px = int(parent.winfo_rootx())
            py = int(parent.winfo_rooty())
            pw = int(parent.winfo_width())
            ph = int(parent.winfo_height())
            sx = max((pw - self.winfo_width()) // 2, 0)
            sy = max((ph - self.winfo_height()) // 2, 0)
            x = max(px + sx, 0)
            y = max(py + sy, 0)
            self.geometry(f"+{x}+{y}")
            return
        except Exception:
            pass
        try:
            self.eval(f"tk::PlaceWindow {str(self)} center")
        except Exception:
            pass

    def _take_grab(self) -> None:
        try:
            self.grab_set()
        except Exception:
            pass

    def _release_grab(self, _event: tk.Event | None = None) -> None:
        try:
            self.grab_release()
        except Exception:
            pass


def _resolve_font(font: Iterable[str | int], fallback: tuple[str, int] | tuple[str, int, str]) -> tuple[str, int] | tuple[str, int, str]:
    try:
        family = tuple(font)
        return tuple(family)  # type: ignore[return-value]
    except Exception:
        return fallback


def _mix_color(base: str, other: str, weight: float) -> str:
    weight = max(0.0, min(float(weight), 1.0))
    try:
        b = base.lstrip("#")
        o = other.lstrip("#")
        if len(b) != 6 or len(o) != 6:
            raise ValueError
        br, bg, bb = (int(b[i : i + 2], 16) for i in (0, 2, 4))
        or_, og, ob = (int(o[i : i + 2], 16) for i in (0, 2, 4))
        r = int(br * (1 - weight) + or_ * weight)
        g = int(bg * (1 - weight) + og * weight)
        bl = int(bb * (1 - weight) + ob * weight)
        return f"#{r:02x}{g:02x}{bl:02x}"
    except Exception:
        return base
