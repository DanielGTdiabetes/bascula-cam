"""Reusable holographic toolbar component."""

from __future__ import annotations

from typing import Iterable, Mapping, MutableSequence, Optional

from tkinter import ttk

__all__ = ["Toolbar"]


ActionSpec = Mapping[str, object]


class Toolbar(ttk.Frame):
    """Flat toolbar styled for the holographic theme."""

    def __init__(
        self,
        master: Optional[ttk.Widget] = None,
        *,
        actions: Optional[Iterable[ActionSpec]] = None,
        padding: tuple[int, int, int, int] | tuple[int, int] | None = None,
        **kwargs,
    ) -> None:
        kwargs.setdefault("style", "Toolbar.TFrame")
        if padding is None:
            super().__init__(master, **kwargs)
        else:
            super().__init__(master, padding=padding, **kwargs)

        self.columnconfigure(0, weight=1)
        self._content = ttk.Frame(self, style="Toolbar.TFrame")
        self._content.grid(row=0, column=0, sticky="nsew")
        self._content.columnconfigure(0, weight=1)

        self._button_container = ttk.Frame(self._content, style="Toolbar.TFrame")
        self._button_container.pack(side="left", fill="x")

        self._buttons: MutableSequence[ttk.Button] = []

        self._bottom_line = ttk.Frame(self, style="Toolbar.Separator.TFrame")
        self._bottom_line.grid(row=1, column=0, sticky="ew")

        if actions:
            for action in actions:
                self.add_action(action)

    @property
    def buttons(self) -> tuple[ttk.Button, ...]:
        """Return the tuple of created action buttons."""

        return tuple(self._buttons)

    @property
    def content(self) -> ttk.Frame:
        """Expose the internal content frame for extra widgets."""

        return self._content

    @property
    def button_container(self) -> ttk.Frame:
        """Frame where action buttons are packed."""

        return self._button_container

    def clear_actions(self) -> None:
        """Remove all current buttons from the toolbar."""

        while self._buttons:
            button = self._buttons.pop()
            try:
                button.destroy()
            except Exception:
                pass

    def add_action(self, action: ActionSpec) -> ttk.Button:
        """Create a new tool button and pack it to the left."""

        text = str(action.get("text", ""))
        command = action.get("command")
        extra = {k: v for k, v in action.items() if k not in {"text", "command"}}

        button = ttk.Button(
            self._button_container,
            text=text,
            command=command,  # type: ignore[arg-type]
            style="Toolbutton.TButton",
            **extra,
        )
        button.pack(side="left", padx=(0, 12))
        try:
            button.configure(cursor="hand2")
        except Exception:
            pass
        self._buttons.append(button)
        return button

