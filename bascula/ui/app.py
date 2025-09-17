"""Minimal fullscreen application entry point."""
from __future__ import annotations

import tkinter as tk

from bascula.config.theme import apply_theme, colors
from bascula.ui.screens import HomeScreen, ScaleScreen, SettingsScreen
from bascula.ui.widgets import TopBar


class BasculaApp:
    """Tkinter application configured for kiosk usage."""

    def __init__(self, theme: str = "retro") -> None:
        self.root = tk.Tk()
        self.root.title("Báscula Cam")
        try:
            self.root.attributes("-fullscreen", True)
        except tk.TclError:
            pass
        self.root.geometry("1024x600")
        apply_theme(self.root, theme)
        palette = colors()
        self.root.configure(bg=palette["BG"])

        self.topbar = TopBar(self.root, self)
        self.topbar.pack(fill=tk.X)

        self.container = tk.Frame(self.root, bg=palette["BG"])
        self.container.pack(fill=tk.BOTH, expand=True)

        self.screens: dict[str, "BaseScreen"] = {}
        for screen_cls in (HomeScreen, ScaleScreen, SettingsScreen):
            screen = screen_cls(self.container, self)
            self.screens[screen.name] = screen

        self.current_screen: BaseScreen | None = None
        self.show_screen("home")

        self.root.bind("<Escape>", lambda _event: self.root.destroy())

    def show_screen(self, name: str) -> None:
        screen = self.screens.get(name)
        if screen is None:
            return
        if self.current_screen is not None:
            self.current_screen.pack_forget()
        screen.pack(fill=tk.BOTH, expand=True)
        screen.on_show()
        self.current_screen = screen

    def run(self) -> None:
        self.root.mainloop()


# Late imports to avoid circular references in type checkers
from typing import TYPE_CHECKING
if TYPE_CHECKING:  # pragma: no cover
    from bascula.ui.screens import BaseScreen
