from __future__ import annotations

import tkinter as tk
from tkinter import ttk

__all__ = ["auto_apply_scaling", "apply_scaling_if_needed"]


def auto_apply_scaling(root: tk.Misc | None = None) -> None:
    """No-op segura o aplica scaling si el tema lo soporta."""
    try:
        from bascula.config.theme import apply_theme
    except Exception:
        return

    target: tk.Misc | None = root
    if target is None:
        default_root = getattr(tk, "_default_root", None)
        if isinstance(default_root, tk.Misc):
            target = default_root
    if target is None:
        return

    try:
        apply_theme(target)
    except Exception:
        pass


def apply_scaling_if_needed(widget: tk.Misc) -> None:
    """Helper opcional para aplicar estilos/escala a un widget concreto."""
    try:
        widget.update_idletasks()
    except Exception:
        pass
