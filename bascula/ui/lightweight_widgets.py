"""Tiny widget helpers tuned for Raspberry Pi constraints."""
from __future__ import annotations

import logging
import tkinter as tk
from functools import lru_cache
from typing import Any, Callable, Dict, Optional, Tuple

from .rpi_config import TOUCH
from .theme_crt import CRT_COLORS, CRT_SPACING, draw_dotted_rule as theme_draw_dotted_rule, mono, safe_color, sans

logger = logging.getLogger("bascula.ui.widgets.lightweight")


def _safe_color(value: Optional[str], fallback: str = CRT_COLORS["bg"]) -> str:
    if isinstance(value, str):
        value = value.strip()
        if value and value.lower() != "none":
            return value
    return fallback


def _coerce_int(value: Any, fallback: int) -> int:
    try:
        if isinstance(value, bool):
            raise TypeError
        return int(float(value))
    except (TypeError, ValueError):
        logger.warning("Coerce int fallback: value=%r -> using %r", value, fallback)
        try:
            return int(float(fallback))
        except Exception:
            logger.error("Fallback for int is invalid: %r; using 0", fallback)
            return 0


def _normalize_font(value: Any, fallback: tuple[str, int, str]) -> Tuple[Any, ...]:
    family, size, weight = fallback
    extra: list[str] = []
    if isinstance(value, str):
        candidate = value.strip()
        if candidate:
            family = candidate
        return (family, size, weight)
    if isinstance(value, (tuple, list)):
        if value:
            candidate_family = str(value[0]).strip()
            if candidate_family:
                family = candidate_family
        if len(value) >= 2:
            size = _coerce_int(value[1], size)
        if len(value) >= 3:
            weight = str(value[2]) or weight
        if len(value) > 3:
            extra = [str(part) for part in value[3:] if str(part)]
        return (family, size, weight, *extra)  # type: ignore[return-value]
    return (family, size, weight)


class WidgetPool:
    """Recycles a small set of Tk widgets to avoid churn between screens."""

    def __init__(self, factory: Callable[[tk.Widget], tk.Widget]) -> None:
        self.factory = factory
        self._pool: Dict[int, list[tk.Widget]] = {}

    def acquire(self, parent: tk.Widget) -> tk.Widget:
        bucket = self._pool.setdefault(id(parent), [])
        try:
            widget = bucket.pop()
            return widget
        except IndexError:
            return self.factory(parent)

    def release(self, widget: tk.Widget) -> None:
        try:
            widget.pack_forget()
            widget.grid_forget()
        except Exception:
            pass
        parent = widget.master
        bucket = self._pool.setdefault(id(parent), [])
        bucket.append(widget)
class Card(tk.Frame):
    def __init__(self, parent: tk.Widget, **kwargs) -> None:
        bg = _safe_color(kwargs.pop("bg", CRT_COLORS.get("surface")))
        super().__init__(parent, bg=bg, highlightthickness=0, bd=0)
        self.configure(**kwargs)
        self._border = tk.Canvas(parent, bg=CRT_COLORS["bg"], highlightthickness=0, bd=0)
        self._border.place_forget()
        self.bind("<Map>", self._update_border, add=True)
        self.bind("<Configure>", self._update_border, add=True)
        self.bind("<Destroy>", self._destroy_border, add=True)

    def _update_border(self, _event=None) -> None:
        try:
            x = self.winfo_x()
            y = self.winfo_y()
            w = max(1, self.winfo_width())
            h = max(1, self.winfo_height())
            pad = 6
            self._border.place(x=x - pad, y=y - pad, width=w + pad * 2, height=h + pad * 2)
            self._border.delete("border")
            self._border.create_rectangle(
                pad,
                pad,
                w + pad,
                h + pad,
                outline=CRT_COLORS["divider"],
                width=2,
                dash=(4, 6),
                tags="border",
            )
        except Exception:
            pass

    def _destroy_border(self, _event=None) -> None:
        try:
            self._border.destroy()
        except Exception:
            pass

    def destroy(self) -> None:
        self._destroy_border()
        super().destroy()


class CRTButton(tk.Button):
    """Large button with icon + label compliant with CRT spec."""

    def __init__(self, parent: tk.Widget, *, icon: str = "", text: str = "", **kwargs) -> None:
        padding = _coerce_int(kwargs.pop("padding", CRT_SPACING.padding), CRT_SPACING.padding)
        min_height = _coerce_int(kwargs.pop("min_height", 72), 72)
        default_font = mono("sm")
        font = _normalize_font(kwargs.pop("font", default_font), default_font)
        base_bg = _safe_color(kwargs.pop("bg", CRT_COLORS.get("bg")))
        accent = CRT_COLORS["accent"]
        accent_dim = CRT_COLORS["accent_dim"]
        fg_color = _safe_color(kwargs.pop("fg", CRT_COLORS.get("text")), CRT_COLORS["text"])
        display = icon if not text else f"{icon}\n{text}" if icon else text
        super().__init__(
            parent,
            text=display,
            bg=base_bg,
            fg=fg_color,
            activebackground=accent,
            activeforeground=CRT_COLORS["bg"],
            highlightthickness=2,
            highlightbackground=CRT_COLORS["divider"],
            highlightcolor=CRT_COLORS["divider"],
            bd=0,
            relief="flat",
            font=font,
            padx=padding,
            pady=max(12, padding // 2),
        )
        self.configure(disabledforeground=CRT_COLORS["muted"], activeborderwidth=2)
        self._normal_colors = (base_bg, fg_color)
        self._hover_binding = self.bind("<Enter>", lambda _e: self.configure(bg=accent_dim, fg=CRT_COLORS["bg"]))
        self.bind("<Leave>", lambda _e: self.configure(bg=self._normal_colors[0], fg=self._normal_colors[1]))
        for key, value in kwargs.items():
            try:
                self.configure(**{key: value})
            except Exception:
                logger.debug("No se pudo aplicar propiedad %s", key)
        self.after_idle(lambda: self._enforce_height(min_height))

    def _enforce_height(self, min_height: int) -> None:
        try:
            current = self.winfo_height()
            if current < min_height:
                extra = max(0, (min_height - current) // 2)
                self.configure(pady=self.cget("pady") + extra)
        except Exception:
            pass


# Backwards compatibility with older naming
AccentButton = CRTButton


class CRTToggle(tk.Frame):
    def __init__(self, parent: tk.Widget, *, text: str, command: Callable[[bool], None], initial: bool = False) -> None:
        super().__init__(parent, bg=CRT_COLORS["surface"])
        self._value = bool(initial)
        self._command = command
        self.columnconfigure(1, weight=1)
        self.indicator = tk.Canvas(self, width=96, height=40, bg=CRT_COLORS["surface"], highlightthickness=0, bd=0)
        self.indicator.grid(row=0, column=0, padx=(0, CRT_SPACING.padding))
        self.label = tk.Label(
            self,
            text=text,
            bg=CRT_COLORS["surface"],
            fg=CRT_COLORS["text"],
            font=sans("md", "bold"),
            anchor="w",
        )
        self.label.grid(row=0, column=1, sticky="ew")
        self.bind("<Button-1>", self._toggle, add=True)
        self.label.bind("<Button-1>", self._toggle, add=True)
        self.indicator.bind("<Button-1>", self._toggle, add=True)
        self._draw()

    def _draw(self) -> None:
        self.indicator.delete("all")
        radius = 18
        width = int(self.indicator.cget("width"))
        height = int(self.indicator.cget("height"))
        margin = 4
        track_outline = CRT_COLORS["divider"]
        fill_color = CRT_COLORS["accent_dim"] if self._value else CRT_COLORS["surface"]
        knob_color = CRT_COLORS["accent"] if self._value else CRT_COLORS["muted"]
        self.indicator.create_rectangle(
            margin,
            height // 2 - radius,
            width - margin,
            height // 2 + radius,
            fill=fill_color,
            outline=track_outline,
            width=2,
        )
        knob_x = width - margin - radius * 2 if self._value else margin
        self.indicator.create_oval(
            knob_x,
            height // 2 - radius,
            knob_x + radius * 2,
            height // 2 + radius,
            fill=knob_color,
            outline=CRT_COLORS["divider"],
            width=2,
        )

    def _toggle(self, _event=None) -> None:
        self._value = not self._value
        self._draw()
        try:
            self._command(self._value)
        except Exception:
            logger.exception("Error ejecutando toggle %s", self.label.cget("text"))


class CRTTabBar(tk.Frame):
    def __init__(self, parent: tk.Widget, *, tabs: Dict[str, Callable[[], None]]) -> None:
        super().__init__(parent, bg=CRT_COLORS["surface"])
        self._buttons: Dict[str, tk.Button] = {}
        for index, (name, callback) in enumerate(tabs.items()):
            btn = tk.Button(
                self,
                text=name,
                bg=CRT_COLORS["bg"],
                fg=CRT_COLORS["muted"],
                activebackground=CRT_COLORS["accent"],
                activeforeground=CRT_COLORS["bg"],
                font=mono("sm"),
                highlightthickness=2,
                highlightbackground=CRT_COLORS["divider"],
                highlightcolor=CRT_COLORS["divider"],
                bd=0,
                padx=CRT_SPACING.padding,
                pady=12,
                command=callback,
            )
            btn.grid(row=0, column=index, padx=(0, CRT_SPACING.gutter))
            self._buttons[name] = btn

    def activate(self, name: str) -> None:
        for tab_name, button in self._buttons.items():
            active = tab_name == name
            try:
                button.configure(
                    fg=CRT_COLORS["bg"] if active else CRT_COLORS["muted"],
                    bg=CRT_COLORS["accent"] if active else CRT_COLORS["bg"],
                )
            except Exception:
                pass


class IconButton(CRTButton):
    def __init__(self, parent: tk.Widget, icon: str, text: str = "", **kwargs) -> None:
        super().__init__(parent, icon=icon, text=text, **kwargs)


class ValueLabel(tk.Label):
    def __init__(self, parent: tk.Widget, *, size_key: str = "xl", mono_font: bool = True, **kwargs) -> None:
        font_factory = mono if mono_font else sans
        default_font = font_factory(size_key, "bold")
        font = _normalize_font(kwargs.pop("font", default_font), default_font)
        padx = _coerce_int(kwargs.pop("padx", CRT_SPACING.padding), CRT_SPACING.padding)
        pady = _coerce_int(kwargs.pop("pady", 8), 8)
        if not isinstance(padx, int) or not isinstance(pady, int):
            logger.error(
                "Invalid padding types in ValueLabel: padx=%r (%s), pady=%r (%s)",
                padx,
                type(padx).__name__,
                pady,
                type(pady).__name__,
            )
        super().__init__(
            parent,
            bg=_safe_color(kwargs.pop("bg", CRT_COLORS.get("surface"))),
            fg=_safe_color(kwargs.pop("fg", CRT_COLORS.get("text")), CRT_COLORS["text"]),
            font=font,
            padx=padx,
            pady=pady,
        )
        self.configure(**kwargs)


class ScrollFrame(tk.Frame):
    """Scrollable area reusing a single Canvas instance."""

    def __init__(self, parent: tk.Widget, *, height: int = 320, width: int = 880) -> None:
        height = _coerce_int(height, 320)
        width = _coerce_int(width, 880)
        super().__init__(parent, bg=_safe_color(CRT_COLORS.get("bg")))
        self.canvas = tk.Canvas(
            self,
            bg=_safe_color(CRT_COLORS.get("bg")),
            highlightthickness=0,
            bd=0,
            width=width,
            height=height,
        )
        self.canvas.pack(side="left", fill="both", expand=True)
        self._inner = tk.Frame(self.canvas, bg=_safe_color(CRT_COLORS.get("bg")))
        self._window = self.canvas.create_window((0, 0), window=self._inner, anchor="nw")
        self._inner.bind("<Configure>", self._on_config)
        self.canvas.bind("<Configure>", self._on_canvas_config)
        self._scroll_id: Optional[str] = None

    @property
    def inner(self) -> tk.Frame:
        return self._inner

    def _on_config(self, _event=None) -> None:
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_canvas_config(self, event) -> None:
        self.canvas.itemconfigure(self._window, width=event.width)


@lru_cache(maxsize=32)
def lazy_color(name: str, fallback: str = CRT_COLORS["accent"]) -> str:
    value = CRT_COLORS.get(name, fallback) or fallback
    if not value.startswith("#"):
        return fallback
    return value


def create_separator(parent: tk.Widget) -> tk.Frame:
    return tk.Frame(parent, bg=CRT_COLORS["divider"], height=2)


def format_weight(value: float) -> str:
    grams = float(value)
    unit = "g"
    if abs(grams) >= 1000:
        grams /= 1000.0
        unit = "kg"
    return f"{grams:0.1f} {unit}"


def clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(value, maximum))


def draw_dotted_rule(canvas, x0: int, y0: int, x1: int, **kwargs) -> None:  # type: ignore[override]
    theme_draw_dotted_rule(canvas, x0, y0, x1, **kwargs)

