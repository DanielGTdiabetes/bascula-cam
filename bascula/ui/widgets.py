import tkinter as tk
from bascula.config.theme import THEME

class ProButton(tk.Button):
    def __init__(self, parent, text="", command=None, kind="primary", **kw):
        colors = {
            "primary": THEME.primary, "success": THEME.success, "danger": THEME.danger,
            "warning": THEME.warning, "secondary": THEME.medium, "light": THEME.light
        }
        super().__init__(parent, text=text, command=command, bg=colors.get(kind, THEME.primary),
                         fg="white", bd=0, relief="flat", font=( "Arial", 12, "bold"), **kw)
        self.configure(cursor="hand2")

class WeightDisplay(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent, bg=THEME.surface, bd=2, relief="solid")
        self.lbl = tk.Label(self, text="0.0", font=("Arial", 72, "bold"),
                            bg=THEME.surface, fg=THEME.text)
        self.lbl.pack(padx=30, pady=30)
        self.status = tk.Label(self, text="MIDIENDO", font=("Arial", 12, "bold"),
                               bg=THEME.surface, fg=THEME.medium)
        self.status.pack(pady=(0,10))
    def set_value(self, value: float, stable: bool):
        self.lbl.configure(text=f"{value:.1f}")
        self.status.configure(text="ESTABLE" if stable else "MIDIENDO",
                              fg=THEME.success if stable else THEME.medium)
