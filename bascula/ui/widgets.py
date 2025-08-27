import tkinter as tk
from bascula.config.theme import THEME

# Tamaños moderados, sin forzar ipady en pack/grid
_SIZES = {
    "md": {"font": ("Arial", 12, "bold"), "padx": 8,  "pady": 6},
    "lg": {"font": ("Arial", 14, "bold"), "padx": 10, "pady": 8},
    "xl": {"font": ("Arial", 16, "bold"), "padx": 12, "pady": 10},
}

class ProButton(tk.Button):
    def __init__(self, parent, text="", command=None, kind="primary", size="md", **kw):
        colors = {
            "primary": THEME.primary, "success": THEME.success, "danger": THEME.danger,
            "warning": THEME.warning, "secondary": THEME.medium, "light": THEME.light
        }
        sz = _SIZES.get(size, _SIZES["md"])
        super().__init__(
            parent, text=text, command=command,
            bg=colors.get(kind, THEME.primary), fg="white",
            bd=0, relief="flat", font=sz["font"], **kw
        )
        self.configure(cursor="hand2")
        self._padx = sz["padx"]; self._pady = sz["pady"]

    def pack(self, *a, **k):
        k.setdefault("padx", self._padx)
        k.setdefault("pady", self._pady)
        return super().pack(*a, **k)

    def grid(self, *a, **k):
        return super().grid(*a, **k)

class WeightDisplay(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent, bg=THEME.surface, bd=2, relief="solid")
        # Tamaño de fuente razonable y adaptable
        self.lbl = tk.Label(self, text="0.0", font=("Arial", 72, "bold"),
                            bg=THEME.surface, fg=THEME.text)
        self.lbl.pack(padx=24, pady=24)
        self.status = tk.Label(self, text="MIDIENDO", font=("Arial", 14, "bold"),
                               bg=THEME.surface, fg=THEME.medium)
        self.status.pack(pady=(0,10))

    def set_value(self, value: float, stable: bool):
        self.lbl.configure(text=f"{value:.1f}")
        self.status.configure(text="ESTABLE" if stable else "MIDIENDO",
                              fg=THEME.success if stable else THEME.medium)
