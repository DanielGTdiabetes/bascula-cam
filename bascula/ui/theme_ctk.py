"""CustomTkinter theming helpers for the holographic appearance."""
from __future__ import annotations

import logging
import tkinter as tk
from pathlib import Path
from typing import Any, Optional

try:  # pragma: no cover - optional dependency during tests
    import customtkinter as ctk

    CTK_AVAILABLE = True
except Exception:  # pragma: no cover - defensive fallback
    ctk = None  # type: ignore[assignment]
    CTK_AVAILABLE = False

from tkinter import ttk

from .fonts import font_tuple, get_mono_font_family, get_ui_font_family, mono_font_tuple

log = logging.getLogger(__name__)


COLORS = {
    "bg": "#0A0A0A",
    "surface": "#111827",
    "surface_alt": "#141B2C",
    "surface_hover": "#1B2336",
    "text": "#FFFFFF",
    "text_muted": "#C4C9E6",
    "primary": "#00E5FF",
    "accent": "#FF00DC",
    "accent_soft": "#FF55F0",
    "grid": "#083A40",
    "border": "#00A7C6",
    "switch_off": "#2B2B2B",
}


def _build_theme_dict() -> dict[str, Any]:
    accent = COLORS["accent"]
    primary = COLORS["primary"]
    surface = COLORS["surface"]
    bg = COLORS["bg"]
    text = COLORS["text"]
    muted = COLORS["text_muted"]

    return {
        "CTk": {
            "fg_color": [bg, bg],
            "top_fg_color": [bg, bg],
            "border_color": [primary, primary],
        },
        "CTkButton": {
            "corner_radius": 12,
            "border_width": 1,
            "fg_color": [surface, surface],
            "hover_color": [accent, accent],
            "border_color": [primary, primary],
            "text_color": [text, text],
            "font": font_tuple(14, "bold"),
        },
        "CTkLabel": {
            "fg_color": "transparent",
            "text_color": [text, text],
            "font": font_tuple(14),
        },
        "CTkEntry": {
            "corner_radius": 10,
            "border_width": 1,
            "border_color": [primary, primary],
            "fg_color": [surface_alt := COLORS["surface_alt"], surface_alt],
            "text_color": [text, text],
            "placeholder_text_color": muted,
            "font": font_tuple(13),
        },
        "CTkSwitch": {
            "progress_color": accent,
            "fg_color": COLORS["switch_off"],
            "border_color": primary,
            "button_color": surface,
            "button_hover_color": accent,
            "text_color": text,
            "font": font_tuple(13, "bold"),
        },
        "CTkScrollableFrame": {
            "fg_color": [surface, surface],
        },
        "CTkTabview": {
            "fg_color": [surface, surface],
            "segmented_button_fg_color": surface,
            "segmented_button_selected_color": accent,
            "segmented_button_selected_hover_color": accent,
            "segmented_button_unselected_color": primary,
            "segmented_button_unselected_hover_color": accent,
            "text_color": text,
            "segmented_button_text_color": text,
        },
    }


def init_holographic_theme(root: Optional[tk.Misc] = None) -> bool:
    """Initialise the CustomTkinter appearance when available."""

    if not CTK_AVAILABLE:
        return False

    try:
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme(_build_theme_dict())
        ctk.set_widget_scaling(1.0)
        ctk.set_window_scaling(1.0)
    except Exception:  # pragma: no cover - defensive
        log.debug("No se pudo aplicar el tema holográfico", exc_info=True)
        return False

    if root is not None:
        try:
            root.configure(fg_color=COLORS["bg"])
        except Exception:  # pragma: no cover - defensa
            log.debug("No se pudo configurar el color de fondo", exc_info=True)
    return True


def create_root() -> tk.Misc:
    """Return the appropriate root widget depending on availability."""

    if CTK_AVAILABLE:
        root = ctk.CTk()
        init_holographic_theme(root)
        return root
    return tk.Tk()


def create_toplevel(master: tk.Misc) -> tk.Toplevel:
    if CTK_AVAILABLE:
        return ctk.CTkToplevel(master)
    return tk.Toplevel(master)


def _inject_common_kwargs(options: dict[str, Any], *, bg_key: str = "bg") -> dict[str, Any]:
    if CTK_AVAILABLE:
        fg_color = options.pop("bg", None)
        if fg_color is not None:
            options.setdefault("fg_color", fg_color)
        options.setdefault("corner_radius", 12)
    else:
        options.pop("corner_radius", None)
        options.pop("hover_color", None)
        bg_color = options.pop("fg_color", None)
        if bg_color is not None:
            options.setdefault("bg", bg_color)
        border_color = options.pop("border_color", None)
        if border_color is not None:
            options.setdefault("highlightbackground", border_color)
            options.setdefault("highlightcolor", border_color)
            options.setdefault("highlightthickness", options.pop("border_width", 1))
    return options


def create_frame(master: tk.Misc, **kwargs: Any) -> tk.Frame:
    options = _inject_common_kwargs(dict(kwargs))
    if CTK_AVAILABLE:
        return ctk.CTkFrame(master, **options)
    return tk.Frame(master, **options)


def create_label(master: tk.Misc, **kwargs: Any) -> tk.Label:
    options = dict(kwargs)
    font = options.pop("font", font_tuple(13))
    if CTK_AVAILABLE:
        options.setdefault("text_color", COLORS["text"])
        options.setdefault("bg_color", "transparent")
        return ctk.CTkLabel(master, font=font, **options)
    options.setdefault("bg", COLORS["surface"])
    options.setdefault("fg", COLORS["text"])
    return tk.Label(master, font=font, **options)


def create_button(master: tk.Misc, **kwargs: Any) -> tk.Button:
    options = dict(kwargs)
    font = options.pop("font", font_tuple(14, "bold"))
    if CTK_AVAILABLE:
        options.setdefault("text_color", COLORS["text"])
        options.setdefault("fg_color", COLORS["surface"])
        options.setdefault("hover_color", COLORS["accent"])
        options.setdefault("border_color", COLORS["primary"])
        options.setdefault("border_width", 1)
        options.setdefault("corner_radius", 12)
        options.setdefault("font", font)
        return ctk.CTkButton(master, **options)
    options.setdefault("bg", COLORS["surface"])
    options.setdefault("fg", COLORS["text"])
    options.setdefault("activebackground", COLORS["accent"])
    options.setdefault("activeforeground", COLORS["text"])
    options.setdefault("relief", "flat")
    options.setdefault("font", font)
    return tk.Button(master, **options)


def create_switch(master: tk.Misc, **kwargs: Any) -> tk.Checkbutton:
    options = dict(kwargs)
    font = options.pop("font", font_tuple(13, "bold"))
    if CTK_AVAILABLE:
        options.setdefault("text_color", COLORS["text"])
        options.setdefault("fg_color", COLORS["switch_off"])
        options.setdefault("progress_color", COLORS["accent"])
        options.setdefault("border_color", COLORS["primary"])
        options.setdefault("font", font)
        return ctk.CTkSwitch(master, **options)
    options.setdefault("bg", COLORS["surface"])
    options.setdefault("fg", COLORS["text"])
    options.setdefault("selectcolor", COLORS["accent"])
    options.setdefault("activebackground", COLORS["surface_hover"])
    options.setdefault("font", font)
    return tk.Checkbutton(master, indicatoron=True, **options)


def create_entry(master: tk.Misc, **kwargs: Any) -> tk.Entry:
    options = dict(kwargs)
    font = options.pop("font", font_tuple(13))
    placeholder = options.pop("placeholder_text", None)
    if CTK_AVAILABLE:
        options.setdefault("fg_color", COLORS["surface_alt"])
        options.setdefault("border_color", COLORS["primary"])
        options.setdefault("corner_radius", 10)
        options.setdefault("border_width", 1)
        options.setdefault("text_color", COLORS["text"])
        options.setdefault("font", font)
        if placeholder is not None:
            options.setdefault("placeholder_text", placeholder)
        return ctk.CTkEntry(master, **options)
    options.setdefault("bg", COLORS["surface_alt"])
    options.setdefault("fg", COLORS["text"])
    options.setdefault("insertbackground", COLORS["accent"])
    options.setdefault("highlightthickness", 2)
    options.setdefault("highlightbackground", COLORS["primary"])
    options.setdefault("highlightcolor", COLORS["accent"])
    options.setdefault("font", font)
    entry = tk.Entry(master, **options)
    if placeholder:
        entry.insert(0, placeholder)
    return entry


def create_tabview(master: tk.Misc, **kwargs: Any) -> Any:
    options = dict(kwargs)
    font = options.pop("font", font_tuple(14, "bold"))
    if CTK_AVAILABLE:
        options.setdefault("fg_color", COLORS["surface"])
        tabview = ctk.CTkTabview(master, **options)
        try:
            tabview._segmented_button.configure(font=font)  # type: ignore[attr-defined]
        except Exception:  # pragma: no cover - private attribute
            pass
        return tabview
    style = ttk.Style(master)
    style.configure(
        "Holo.TNotebook",
        background=COLORS["bg"],
        borderwidth=0,
        tabmargins=(8, 4, 8, 0),
    )
    style.configure(
        "Holo.TNotebook.Tab",
        font=font,
        foreground=COLORS["text"],
        background=COLORS["bg"],
        padding=(20, 10),
    )
    style.map(
        "Holo.TNotebook.Tab",
        foreground=[("selected", COLORS["accent"])],
        background=[("selected", COLORS["surface"])],
    )
    notebook = ttk.Notebook(master, style="Holo.TNotebook")
    return notebook


def create_scrollable_frame(master: tk.Misc, **kwargs: Any) -> tk.Frame:
    options = dict(kwargs)
    if CTK_AVAILABLE:
        options.setdefault("fg_color", COLORS["surface"])
        options.setdefault("corner_radius", 12)
        return ctk.CTkScrollableFrame(master, **options)
    frame = tk.Frame(master, bg=options.pop("fg_color", COLORS["surface"]))
    return frame


def create_canvas_grid(root: tk.Misc, *, image: Optional[Path] = None) -> Optional[tk.Canvas]:
    """Draw a subtle neon grid on the supplied root widget."""

    if image and image.exists():
        try:
            from PIL import Image, ImageTk  # pragma: no cover - optional

            img = Image.open(image)
            photo = ImageTk.PhotoImage(img)
            label = tk.Label(root, image=photo, bg=COLORS["bg"])
            label.image = photo  # type: ignore[attr-defined]
            label.place(relx=0, rely=0, relwidth=1, relheight=1)
            return None
        except Exception:
            log.debug("No se pudo cargar la imagen de fondo", exc_info=True)

    canvas = tk.Canvas(root, bg=COLORS["bg"], highlightthickness=0)
    canvas.place(relx=0, rely=0, relwidth=1, relheight=1)

    spacing = 32
    width = max(1, int(root.winfo_screenwidth()))
    height = max(1, int(root.winfo_screenheight()))
    color = COLORS["grid"]

    for x in range(0, width, spacing):
        canvas.create_line(x, 0, x, height, fill=color, width=1)
    for y in range(0, height, spacing):
        canvas.create_line(0, y, width, y, fill=color, width=1)

    canvas.lower()
    return canvas


def create_glow_title(master: tk.Misc, text: str, *, font_size: int = 24) -> tk.Misc:
    container = create_frame(master, fg_color="transparent")
    glow_font = font_tuple(font_size, "bold")

    shadow = create_label(
        container,
        text=text,
        font=glow_font,
        text_color=COLORS["primary"],
    )
    shadow.place(relx=0.02, rely=0.1)

    label = create_label(
        container,
        text=text,
        font=glow_font,
        text_color=COLORS["text"],
    )
    label.place(relx=0, rely=0)
    return container


def get_number_font(size: int = 32, weight: str = "normal") -> tuple[str, int] | tuple[str, int, str]:
    return mono_font_tuple(size, weight)


__all__ = [
    "COLORS",
    "CTK_AVAILABLE",
    "create_root",
    "create_toplevel",
    "create_frame",
    "create_label",
    "create_button",
    "create_switch",
    "create_entry",
    "create_tabview",
    "create_scrollable_frame",
    "create_canvas_grid",
    "create_glow_title",
    "get_number_font",
    "get_ui_font_family",
    "get_mono_font_family",
    "font_tuple",
    "mono_font_tuple",
    "init_holographic_theme",
]

