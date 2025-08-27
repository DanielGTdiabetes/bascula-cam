import tkinter as tk
from bascula.ui.extras.mini_utils import size_map
from bascula.ui.extras.modern_theme import THEME_MODERN as MT

class ModernButton(tk.Button):
    def __init__(self, parent, text="", command=None, kind="primary", size="md", **kw):
        styles = {
            "primary":  {"bg": MT.primary, "active": "#1D4ED8"},
            "secondary":{"bg": MT.medium,  "active": "#475569"},
            "success":  {"bg": MT.success, "active": "#059669"},
            "warning":  {"bg": MT.warning, "active": "#D97706"},
            "danger":   {"bg": MT.danger,  "active": "#DC2626"},
            "dark":     {"bg": MT.surface, "active": MT.surface_light},
        }
        st = styles.get(kind, styles["primary"])
        fnt = size_map(size)
        super().__init__(parent, text=text, command=command,
                         bg=st["bg"], fg=MT.text,
                         activebackground=st["active"], activeforeground=MT.text,
                         bd=0, relief="flat", font=fnt, cursor="hand2", **kw)
        self.bind("<Enter>", lambda e: self.configure(bg=st["active"]))
        self.bind("<Leave>", lambda e: self.configure(bg=st["bg"]))
