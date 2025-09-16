# -*- coding: utf-8 -*-
import tkinter as tk
from bascula.config.theme import get_current_colors

class BaseScreen(tk.Frame):
    """Base class for all screens with common functionality"""
    name = "base"

    def __init__(self, parent, app, **kwargs):
        super().__init__(parent, bg=get_current_colors()['COL_BG'], **kwargs)
        self.app = app
        self.name = self.__class__.__name__

    def on_show(self):
        pass

    def on_hide(self):
        pass


class HomeScreen(BaseScreen):
    name = "home"
    def __init__(self, parent, app):
        super().__init__(parent, app)
        pal = get_current_colors()
        tk.Label(self, text="Inicio", fg=pal['COL_TEXT'], bg=pal['COL_BG'],
                 font=("DejaVu Sans", 28, "bold")).pack(pady=24)

        grid = tk.Frame(self, bg=pal['COL_BG'])
        grid.pack(expand=True)

        def btn(txt, cmd, r, c):
            b = tk.Button(grid, text=txt, width=16, height=2, command=cmd)
            b.grid(row=r, column=c, padx=10, pady=10)
            return b

        btn("Báscula", app.show_scale, 0, 0)
        btn("Escáner", app.show_scanner, 0, 1)
        btn("Ajustes", app.show_settings, 0, 2)


class ScaleScreen(BaseScreen):
    name = "scale"
    def __init__(self, parent, app):
        super().__init__(parent, app)
        pal = get_current_colors()
        tk.Label(self, text="Báscula", fg=pal['COL_TEXT'], bg=pal['COL_BG'],
                 font=("DejaVu Sans", 28, "bold")).pack(pady=16)
        self.weight_var = tk.StringVar(value="0 g")
        self.unit = "g"
        self.decimals = 0
        tk.Label(self, textvariable=self.weight_var, fg=pal['COL_TEXT'], bg=pal['COL_BG'],
                 font=("DejaVu Sans", 48, "bold")).pack(pady=8)

        row = tk.Frame(self, bg=pal['COL_BG']); row.pack(pady=10)
        tk.Button(row, text="Tara", command=app.tare_scale).pack(side="left", padx=8)
        tk.Button(row, text="Cero", command=app.zero_scale).pack(side="left", padx=8)
        tk.Button(row, text="Unidad", command=self._toggle_unit).pack(side="left", padx=8)
        tk.Button(self, text="Volver", command=app.show_main).pack(pady=12)

        # refresco simple del valor (si hay lector real, app.on_bg_update no afecta aquí)
        self.after(500, self._refresh_weight)

    def _refresh_weight(self):
        try:
            w = self.app.get_latest_weight()
            if self.unit == "g":
                txt = f"{round(w, self.decimals)} g"
            else:
                # ejemplo: convertir a oz
                txt = f"{round(w / 28.3495, max(0, self.decimals))} oz"
            self.weight_var.set(txt)
        except Exception:
            pass
        self.after(500, self._refresh_weight)

    def _toggle_unit(self):
        self.unit = "oz" if self.unit == "g" else "g"


class ScannerScreen(BaseScreen):
    name = "scanner"
    def __init__(self, parent, app):
        super().__init__(parent, app)
        pal = get_current_colors()
        tk.Label(self, text="Escáner", fg=pal['COL_TEXT'], bg=pal['COL_BG'],
                 font=("DejaVu Sans", 28, "bold")).pack(pady=16)
        tk.Label(self, text="Acerca un código al lector…", fg=pal['COL_TEXT'], bg=pal['COL_BG']).pack(pady=8)
        tk.Button(self, text="Volver", command=app.show_main).pack(pady=12)


class SettingsScreen(BaseScreen):
    name = "settings"
    def __init__(self, parent, app, get_state=None, set_state=None, change_theme=None, back=None):
        super().__init__(parent, app)
        pal = get_current_colors()
        tk.Label(self, text="Ajustes", fg=pal['COL_TEXT'], bg=pal['COL_BG'],
                 font=("DejaVu Sans", 28, "bold")).pack(pady=16)
        row = tk.Frame(self, bg=pal['COL_BG']); row.pack(pady=10)
        tk.Button(row, text="Tema claro", command=(lambda: change_theme("modern") if change_theme else None)).pack(side="left", padx=8)
        tk.Button(row, text="Tema oscuro", command=(lambda: change_theme("dark") if change_theme else None)).pack(side="left", padx=8)
        tk.Button(self, text="Volver", command=(back or app.show_main)).pack(pady=12)


class TimerPopup(tk.Toplevel):
    def __init__(self, app):
        super().__init__(app.root)
        self.title("Temporizador")
        self.geometry("300x160+50+50")
        pal = get_current_colors()
        self.configure(bg=pal['COL_BG'])
        tk.Label(self, text="Minutos:", fg=pal['COL_TEXT'], bg=pal['COL_BG']).pack(pady=6)
        self.e = tk.Entry(self); self.e.insert(0, "1"); self.e.pack(pady=6)
        tk.Button(self, text="Iniciar", command=self._start).pack(pady=8)
        tk.Button(self, text="Cerrar", command=self.destroy).pack()
        self.app = app

    def _start(self):
        try:
            m = int(self.e.get().strip() or "1")
        except Exception:
            m = 1
        self.app.start_timer(m * 60)
        self.destroy()
