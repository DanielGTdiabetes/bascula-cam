"""Modern Tk based app shell for Báscula."""
from __future__ import annotations

import logging
import os
import tkinter as tk
from typing import Callable, Dict, Iterable, Optional

from .theme_neo import COLORS, SPACING, font_sans
from .icon_loader import load_icon

log = logging.getLogger(__name__)

_ICON_DEF = Iterable[tuple[str, str, str, str]]

ICON_CONFIG: _ICON_DEF = (
    ("wifi", "wifi", "📶", "Wi-Fi"),
    ("speaker", "speaker", "🔊", "Sonido"),
    ("bg", "bg", "🩸", "Glucosa"),
    ("timer", "alarm", "⏱", "Temporizador"),
    ("notif", "bell", "🔔", "Notificaciones"),
)


class AppShell:
    """Application shell responsible for creating the base layout."""

    CURSOR_HIDE_DELAY_MS = 5000

    def __init__(self, root: Optional[tk.Tk] = None):
        self._own_root = root is None
        self.root = root or tk.Tk()
        self.root.withdraw()
        self.root.configure(bg=COLORS["bg"])
        self.root.title("Báscula Digital Pro")
        self.root.protocol("WM_DELETE_WINDOW", self.root.quit)

        self._cursor_job: Optional[str] = None
        self._cursor_hidden = False
        self._cursor_forced_visible = self._cursor_forced()

        self.icon_images: Dict[str, tk.PhotoImage] = {}
        self._icon_actions: Dict[str, Callable[[], None]] = {}
        self._icon_widgets: Dict[str, tk.Button] = {}
        self._notify_job: Optional[str] = None
        self._timer_label: Optional[tk.Label] = None
        self._timer_label_visible = False
        self._timer_pack: Optional[dict] = None
        self._glucose_label: Optional[tk.Label] = None

        self._configure_window()
        self._build_layout()
        self._setup_cursor_timer()

        self.root.deiconify()

    def run(self) -> None:
        """Enter the Tk mainloop."""

        self.root.mainloop()

    # ------------------------------------------------------------------
    # Window configuration
    # ------------------------------------------------------------------
    def _configure_window(self) -> None:
        fullscreen_env = (os.environ.get("BASCULA_UI_FULLSCREEN") or "").strip().lower()
        enable_fullscreen = fullscreen_env in {"1", "true", "yes", "on"}

        current_fullscreen = False
        try:
            current_fullscreen = bool(self.root.attributes("-fullscreen"))
        except Exception:  # pragma: no cover - Tk feature availability
            pass

        if enable_fullscreen and not current_fullscreen:
            try:
                self.root.overrideredirect(True)
            except Exception as exc:  # pragma: no cover - Tk feature availability
                log.debug("overrideredirect no soportado: %s", exc)
            try:
                self.root.attributes("-fullscreen", True)
            except Exception:  # pragma: no cover - Tk feature availability
                pass

        if not current_fullscreen:
            self.root.geometry("1024x600+0+0")
        self.root.minsize(1024, 600)

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------
    def _build_layout(self) -> None:
        self.root.configure(bg=COLORS["bg"])

        self.top_bar = tk.Frame(
            self.root,
            bg=COLORS["surface"],
            height=56,
            padx=SPACING["md"],
            pady=SPACING["xs"],
        )
        self.top_bar.pack(fill="x", side="top")
        self.top_bar.pack_propagate(False)

        self._build_status_icons(self.top_bar)

        self.notification_label = tk.Label(
            self.top_bar,
            text="",
            fg=COLORS["muted"],
            bg=COLORS["surface"],
            font=font_sans(14),
            anchor="e",
            justify="right",
            wraplength=300,
        )
        self.notification_label.pack(side="right", padx=(SPACING["md"], 0))

        self.content = tk.Frame(self.root, bg=COLORS["bg"])
        self.content.pack(fill="both", expand=True)

    def _build_status_icons(self, container: tk.Frame) -> None:
        for name, asset_name, fallback_text, tooltip in ICON_CONFIG:
            icon = load_icon(asset_name, 32)
            button = tk.Button(
                container,
                text=fallback_text,
                image=icon,
                compound="top",
                fg=COLORS["fg"],
                bg=COLORS["surface"],
                activebackground=COLORS["surface"],
                activeforeground=COLORS["fg"],
                font=font_sans(12, "bold"),
                padx=SPACING["xs"],
                pady=SPACING["xs"],
                relief="flat",
                bd=0,
                highlightthickness=0,
                command=lambda n=name: self._handle_action(n),
            )
            if icon is not None:
                self.icon_images[name] = icon
                button.configure(image=icon, compound="top", text=fallback_text)
                button.image = icon  # type: ignore[attr-defined]
            else:
                button.configure(image="", text=fallback_text, compound="center")
            button.pack(side="left", padx=(0, SPACING["sm"]))
            button.tooltip = tooltip  # type: ignore[attr-defined]
            button.configure(state="disabled")
            self._icon_widgets[name] = button

            if name == "timer":
                self._timer_pack = {"side": "left", "padx": (0, SPACING["sm"])}
                label = tk.Label(
                    container,
                    text="",
                    fg=COLORS["muted"],
                    bg=COLORS["surface"],
                    font=font_sans(16, "bold"),
                    padx=SPACING["xs"],
                )
                label.configure(cursor="hand2")
                label.bind("<Button-1>", lambda _e, n=name: self._handle_action(n))
                self._timer_label = label
            elif name == "bg":
                label = tk.Label(
                    container,
                    text="—",
                    fg=COLORS["muted"],
                    bg=COLORS["surface"],
                    font=font_sans(16, "bold"),
                    padx=SPACING["xs"],
                )
                label.pack(side="left", padx=(0, SPACING["sm"]))
                self._glucose_label = label

    # ------------------------------------------------------------------
    # Cursor management
    # ------------------------------------------------------------------
    def _setup_cursor_timer(self) -> None:
        if self._cursor_forced_visible:
            self.root.configure(cursor="")
            return
        for sequence in ("<Motion>", "<Key>", "<Button>", "<FocusIn>"):
            self.root.bind_all(sequence, self._on_user_activity, add="+")
        self._schedule_cursor_hide()

    def _schedule_cursor_hide(self) -> None:
        if self._cursor_forced_visible:
            return
        if self._cursor_job is not None:
            try:
                self.root.after_cancel(self._cursor_job)
            except Exception:
                pass
        self._cursor_job = self.root.after(self.CURSOR_HIDE_DELAY_MS, self._hide_cursor)

    def _hide_cursor(self) -> None:
        if self._cursor_forced_visible:
            return
        self.root.configure(cursor="none")
        self._cursor_hidden = True

    def _show_cursor(self) -> None:
        if self._cursor_hidden:
            self.root.configure(cursor="")
            self._cursor_hidden = False

    def _on_user_activity(self, _event: tk.Event) -> None:
        if self._cursor_forced_visible:
            return
        self._show_cursor()
        self._schedule_cursor_hide()

    @staticmethod
    def _cursor_forced() -> bool:
        value = (os.environ.get("BASCULA_UI_CURSOR") or "").strip().lower()
        return value in {"1", "true", "yes", "on"}

    def get_icon_widget(self, name: str) -> Optional[tk.Button]:
        """Expose top bar widget reference for structural probes."""

        return self._icon_widgets.get(name)

    # ------------------------------------------------------------------
    # Actions / notifications
    # ------------------------------------------------------------------
    def bind_action(self, name: str, callback: Optional[Callable[[], None]]) -> None:
        if callback is None:
            self._icon_actions.pop(name, None)
        else:
            self._icon_actions[name] = callback
        widget = self._icon_widgets.get(name)
        if widget is not None:
            widget.configure(state="normal" if callback else "disabled")

    def _handle_action(self, name: str) -> None:
        callback = self._icon_actions.get(name)
        if callback is None:
            self.notify("Acción no disponible")
            return
        try:
            callback()
        except Exception as exc:  # pragma: no cover - defensive
            log.exception("Error executing action %s", name)
            self.notify(str(exc))

    def notify(self, message: str, duration_ms: int = 4000) -> None:
        self.notification_label.configure(text=message)
        if self._notify_job is not None:
            try:
                self.notification_label.after_cancel(self._notify_job)
            except Exception:
                pass
            self._notify_job = None
        if message and duration_ms > 0:
            self._notify_job = self.notification_label.after(
                duration_ms, lambda: self.notification_label.configure(text="")
            )

    # ------------------------------------------------------------------
    # Timer indicator
    # ------------------------------------------------------------------
    def set_timer_state(self, text: Optional[str], state: str = "idle") -> None:
        label = self._timer_label
        if label is None:
            return

        desired_visible = bool(text)
        if desired_visible:
            color = self._timer_color_for_state(state)
            label.configure(text=text, fg=color)
            if not self._timer_label_visible:
                try:
                    if self._timer_pack:
                        label.pack(**self._timer_pack)
                    else:
                        label.pack(side="left", padx=(0, SPACING["sm"]))
                except Exception:
                    return
                self._timer_label_visible = True
        elif self._timer_label_visible:
            try:
                label.pack_forget()
            except Exception:
                pass
            self._timer_label_visible = False

    def _timer_color_for_state(self, state: str) -> str:
        if state == "finished":
            return COLORS.get("danger", COLORS["muted"])
        if state == "running":
            return COLORS.get("primary", COLORS["text"])
        return COLORS.get("muted", COLORS["text"])

    # ------------------------------------------------------------------
    # Glucose indicator
    # ------------------------------------------------------------------
    def set_glucose_status(self, text: Optional[str], color: Optional[str] = None) -> None:
        label = self._glucose_label
        if label is None:
            return
        if text:
            try:
                label.configure(text=text, fg=color or COLORS.get("text", "white"))
            except Exception:
                return
        else:
            try:
                label.configure(text="—", fg=COLORS.get("muted", "grey"))
            except Exception:
                return

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------
    def destroy(self) -> None:
        if self._notify_job is not None:
            try:
                self.notification_label.after_cancel(self._notify_job)
            except Exception:
                pass
            self._notify_job = None
        if self._cursor_job is not None:
            try:
                self.root.after_cancel(self._cursor_job)
            except Exception:
                pass
            self._cursor_job = None
        if self._own_root:
            self.root.destroy()
