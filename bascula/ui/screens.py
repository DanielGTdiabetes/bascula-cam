from __future__ import annotations

"""Simplified screens for the redesigned Bascula UI."""

import tkinter as tk
from tkinter import ttk
from pathlib import Path
from bascula.ui.widgets import ProButton, WeightLabel, Mascot, setup_ttk_styles
from bascula.config.theme import get_current_colors

ASSETS = Path(__file__).resolve().parent.parent / 'assets' / 'icons'


def _icon_path(name: str) -> str | None:
    p = ASSETS / f"{name}.png"
    return str(p) if p.exists() else None


class HomeScreen(tk.Frame):
    """Home screen with mascot and big navigation buttons."""

    def __init__(self, parent: tk.Misc, app) -> None:
        super().__init__(parent, bg=get_current_colors()['COL_BG'])
        self.app = app

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self.mascota = Mascot(self, width=320, height=280,
                               bg=get_current_colors()['COL_BG'])
        self.mascota.grid(row=0, column=0, pady=20)

        btns = tk.Frame(self, bg=get_current_colors()['COL_BG'])
        btns.grid(row=1, column=0, pady=20)
        btns.grid_columnconfigure((0, 1, 2), weight=1)

        ProButton(btns, 'Báscula', self.app.show_scale,
                  icon=_icon_path('scale')).grid(row=0, column=0, padx=10, pady=10)
        ProButton(btns, 'Temporizador', self.app.open_timer_popup,
                  icon=_icon_path('timer')).grid(row=0, column=1, padx=10, pady=10)
        ProButton(btns, 'Escáner', self.app.open_scanner,
                  icon=_icon_path('scanner')).grid(row=0, column=2, padx=10, pady=10)
        ProButton(btns, 'Ajustes', self.app.open_settings,
                  icon=_icon_path('settings')).grid(row=1, column=0, padx=10, pady=10)
        ProButton(btns, 'Salir', self.app.quit,
                  icon=_icon_path('exit')).grid(row=1, column=1, padx=10, pady=10)


class ScaleScreen(tk.Frame):
    """Digital scale display screen."""

    def __init__(self, parent: tk.Misc, app) -> None:
        super().__init__(parent, bg=get_current_colors()['COL_BG'])
        self.app = app
        self.unit = 'g'

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        header = tk.Frame(self, bg=get_current_colors()['COL_BG'])
        header.grid(row=0, column=0, sticky='ew', pady=10)
        ProButton(header, '← Volver', self.app.show_main, small=True).pack(side='left', padx=10)

        weight_card = tk.Frame(self, bg=get_current_colors()['COL_CARD'], bd=1,
                               highlightbackground=get_current_colors()['COL_BORDER'])
        weight_card.grid(row=1, column=0, padx=40, pady=20, sticky='nsew')
        weight_card.grid_propagate(False)
        weight_card.config(height=220)

        self.weight_lbl = WeightLabel(weight_card, bg=get_current_colors()['COL_CARD'])
        self.weight_lbl.pack(expand=True, fill='both')

        btns = tk.Frame(self, bg=get_current_colors()['COL_BG'])
        btns.grid(row=2, column=0, pady=10)
        ProButton(btns, 'Cero', self.app.zero_scale, small=True).grid(row=0, column=0, padx=5, pady=5)
        ProButton(btns, 'Tara', self.app.tare_scale, small=True).grid(row=0, column=1, padx=5, pady=5)
        ProButton(btns, 'Unidad', self._toggle_unit, small=True).grid(row=0, column=2, padx=5, pady=5)

        self.mascota = Mascot(self, width=120, height=120,
                               bg=get_current_colors()['COL_BG'])
        self.mascota.place(relx=1.0, rely=1.0, anchor='se', x=-10, y=-10)

    def update_weight(self, value: float) -> None:
        self.weight_lbl.config(text=f"{value:.1f}{self.unit}")

    def _toggle_unit(self) -> None:
        self.unit = 'ml' if self.unit == 'g' else 'g'
        self.update_weight(0.0)


class ScannerScreen(tk.Frame):
    """Screen used for barcode scanning."""

    def __init__(self, parent: tk.Misc, app) -> None:
        super().__init__(parent, bg=get_current_colors()['COL_BG'])
        self.app = app

        ProButton(self, '← Volver', self.app.show_main, small=True).pack(anchor='nw', padx=10, pady=10)

        tk.Label(self, text='Escanea un código...',
                 bg=get_current_colors()['COL_BG'], fg=get_current_colors()['COL_TEXT'],
                 font=("DejaVu Sans", 32, 'bold')).pack(expand=True)

        self.mascot = Mascot(self, width=120, height=120,
                               bg=get_current_colors()['COL_BG'])
        self.mascot.place(relx=1.0, rely=1.0, anchor='se', x=-10, y=-10)


class SettingsScreen(tk.Frame):
    """Tabbed settings screen with contextual help."""

    def __init__(self, parent: tk.Misc, get_state, set_state, on_theme_change, back) -> None:
        super().__init__(parent, bg=get_current_colors()['COL_BG'])
        self.get_state = get_state
        self.set_state = set_state
        self.on_theme_change = on_theme_change
        self.back = back

        pal = get_current_colors()
        setup_ttk_styles()

        self._default_help = "Pulsa una opción para ver su descripción"
        self.help_texts: dict[str, str] = {}

        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=0)
        self.grid_rowconfigure(0, weight=1)

        nb = ttk.Notebook(self)
        nb.grid(row=0, column=0, sticky='nsew', padx=20, pady=20)

        side = tk.Frame(self, bg=pal['COL_BG'])
        side.grid(row=0, column=1, sticky='ne', padx=(0,20), pady=20)
        self.mascot = Mascot(side, width=140, height=140, bg=pal['COL_BG'], with_legs=True)
        self.mascot.pack()
        self.help_lbl = tk.Label(side, text=self._default_help, wraplength=180,
                                 bg=pal['COL_BG'], fg=pal['COL_TEXT'],
                                 font=("DejaVu Sans", 18))
        self.help_lbl.pack(pady=10)

        # --- General tab -------------------------------------------------
        general = tk.Frame(nb, bg=pal['COL_BG'])
        nb.add(general, text='General')
        tk.Label(general, text='General', bg=pal['COL_BG'], fg=pal['COL_ACCENT'],
                 font=("DejaVu Sans", 24, 'bold')).pack(anchor='w', padx=10, pady=(0,10))

        state = self.get_state()
        self.diab_var = tk.BooleanVar(value=state.get('diabetic_mode', False))
        cb = ttk.Checkbutton(general, text='Modo diabético', variable=self.diab_var,
                             command=self._toggle_diabetic)
        cb.pack(anchor='w', padx=20, pady=10, ipady=10)
        self._bind_help(cb, 'Muestra glucemia y flecha en la barra superior.')

        # --- Tema tab ----------------------------------------------------
        theme_tab = tk.Frame(nb, bg=pal['COL_BG'])
        nb.add(theme_tab, text='Tema')
        tk.Label(theme_tab, text='Tema', bg=pal['COL_BG'], fg=pal['COL_ACCENT'],
                 font=("DejaVu Sans", 24, 'bold')).pack(anchor='w', padx=10, pady=(0,10))

        self.theme_var = tk.StringVar(value=state.get('theme', 'modern'))
        r1 = ttk.Radiobutton(theme_tab, text='Moderno', value='modern',
                             variable=self.theme_var, command=self._change_theme)
        r1.pack(anchor='w', padx=20, pady=10, ipady=10)
        self._bind_help(r1, 'Colores modernos con alto contraste.')

        r2 = ttk.Radiobutton(theme_tab, text='Retro', value='retro',
                             variable=self.theme_var, command=self._change_theme)
        r2.pack(anchor='w', padx=20, pady=10, ipady=10)
        self._bind_help(r2, 'Estilo verde y negro tipo CRT.')

        ProButton(self, '← Volver', self.back, small=True).grid(row=1, column=0, columnspan=2,
                                                                sticky='w', padx=20, pady=(0,20))

    # -- help system -----------------------------------------------------
    def _bind_help(self, widget, text: str) -> None:
        self.help_texts[str(widget)] = text
        widget.bind('<FocusIn>', lambda e, t=text: self._show_help(t))
        widget.bind('<FocusOut>', lambda e: self._show_help(self._default_help))

    def _show_help(self, text: str) -> None:
        self.help_lbl.config(text=text)
        self.mascot.set_state('idle' if text == self._default_help else 'talk')

    # -- callbacks -------------------------------------------------------
    def _change_theme(self) -> None:
        name = self.theme_var.get()
        self.on_theme_change(name)
        setup_ttk_styles()
        self.set_state({'theme': name})

    def _toggle_diabetic(self) -> None:
        self.set_state({'diabetic_mode': self.diab_var.get()})

class TimerPopup(tk.Toplevel):
    """Popup with presets and manual entry for countdown timer."""

    def __init__(self, app) -> None:
        super().__init__(app.root)
        self.app = app
        self.title('Temporizador')
        pal = get_current_colors()
        self.configure(bg=pal['COL_CARD'])
        self.grab_set()

        presets = (1, 5, 10, 15)
        for i, p in enumerate(presets):
            ProButton(self, f"{p} min", lambda d=p: self._start(d*60), small=True,
                      bg=pal['COL_ACCENT']).grid(row=i, column=0, padx=10, pady=5)

        tk.Label(self, text='Minutos:', bg=pal['COL_CARD'], fg=pal['COL_TEXT']).grid(row=0, column=1, padx=10)
        self.entry = tk.Entry(self)
        self.entry.grid(row=1, column=1, padx=10)
        ProButton(self, 'Iniciar', self._start_manual, small=True).grid(row=2, column=1, pady=5)

    def _start(self, secs: int) -> None:
        self.destroy()
        self.app.start_timer(secs)

    def _start_manual(self) -> None:
        try:
            m = int(self.entry.get())
        except Exception:
            m = 0
        self._start(m*60)
