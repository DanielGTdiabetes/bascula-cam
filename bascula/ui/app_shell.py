"""Modern Tk based app shell for Báscula."""
from __future__ import annotations

import logging
import os
from pathlib import Path
import tkinter as tk
from typing import Callable, Dict, Iterable, Optional

from .theme_neo import COLORS, SPACING, font_sans

log = logging.getLogger(__name__)

ICON_CONFIG: Iterable[tuple[str, str, str]] = (
    ("speaker", "🔊", "Sonido"),
    ("wifi", "📶", "Wi-Fi"),
    ("glucose", "🩸", "Glucosa"),
    ("timer", "⏱", "Temporizador"),
    ("notifications", "🔔", "Notificaciones"),
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
        self._cursor_enabled = not self._cursor_disabled()

        self.icon_images: Dict[str, tk.PhotoImage] = {}
        self._icon_actions: Dict[str, Callable[[], None]] = {}
        self._icon_widgets: Dict[str, tk.Button] = {}
        self._notify_job: Optional[str] = None

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
        try:
            self.root.overrideredirect(True)
        except Exception as exc:
            log.debug("overrideredirect no soportado: %s", exc)
        try:
            self.root.attributes("-fullscreen", True)
        except Exception:
            self.root.geometry("1024x600+0+0")
        else:
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
        assets_dir = Path(__file__).resolve().parent.parent / "assets" / "ui"
        nightscout_enabled = bool(
            os.environ.get("BASCULA_NIGHTSCOUT_URL")
            or os.environ.get("NIGHTSCOUT_URL")
        )
        for name, fallback_text, tooltip in ICON_CONFIG:
            if name == "glucose" and not nightscout_enabled:
                continue
            icon = self._load_icon(assets_dir, name)
            button = tk.Button(
                container,
                text=fallback_text if icon is None else "",
                image=icon,
                compound="center",
                width=32,
                height=32,
                fg=COLORS["text"],
                bg=COLORS["surface"],
                activebackground=COLORS["surface"],
                activeforeground=COLORS["text"],
                font=font_sans(18),
                padx=SPACING["xs"],
                pady=SPACING["xs"],
                relief="flat",
                bd=0,
                highlightthickness=0,
                command=lambda n=name: self._handle_action(n),
            )
            if icon is not None:
                self.icon_images[name] = icon
            button.pack(side="left", padx=(0, SPACING["sm"]))
            button.tooltip = tooltip  # type: ignore[attr-defined]
            button.configure(state="disabled")
            self._icon_widgets[name] = button

    def _load_icon(self, assets_dir: Path, name: str) -> Optional[tk.PhotoImage]:
        image_path = assets_dir / f"{name}.png"
        if not image_path.exists():
            return None
        try:
            icon = tk.PhotoImage(file=str(image_path))
        except Exception as exc:
            log.debug("No se pudo cargar icono %s: %s", image_path, exc)
            return None
        return icon

    # ------------------------------------------------------------------
    # Cursor management
    # ------------------------------------------------------------------
    def _setup_cursor_timer(self) -> None:
        if not self._cursor_enabled:
            return
        for sequence in ("<Motion>", "<Key>", "<Button>", "<FocusIn>"):
            self.root.bind_all(sequence, self._on_user_activity, add="+")
        self._schedule_cursor_hide()

    def _schedule_cursor_hide(self) -> None:
        if not self._cursor_enabled:
            return
        if self._cursor_job is not None:
            try:
                self.root.after_cancel(self._cursor_job)
            except Exception:
                pass
        self._cursor_job = self.root.after(self.CURSOR_HIDE_DELAY_MS, self._hide_cursor)

    def _hide_cursor(self) -> None:
        if not self._cursor_enabled:
            return
        self.root.configure(cursor="none")
        self._cursor_hidden = True

    def _show_cursor(self) -> None:
        if self._cursor_hidden:
            self.root.configure(cursor="")
            self._cursor_hidden = False

    def _on_user_activity(self, _event: tk.Event) -> None:
        if not self._cursor_enabled:
            return
        self._show_cursor()
        self._schedule_cursor_hide()

    @staticmethod
    def _cursor_disabled() -> bool:
        value = (os.environ.get("BASCULA_UI_CURSOR") or "").strip().lower()
        return value in {"1", "true", "yes", "on"}

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
