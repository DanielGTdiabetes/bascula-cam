# -*- coding: utf-8 -*-
import tkinter as tk

# Paleta y tamaños pensados para 1024x600
COL_BG = "#0f1115"
COL_CARD = "#151a22"
COL_TEXT = "#e5e7eb"
COL_MUTED = "#94a3b8"
COL_ACCENT = "#4f46e5"
COL_ACCENT_DARK = "#4338ca"
COL_SUCCESS = "#10b981"
COL_WARN = "#f59e0b"
COL_DANGER = "#ef4444"

# TAMAÑOS DEFINIDOS PARA 1024x600 (HDMI 7")
FS_HUGE = 52           # Peso principal
FS_TITLE = 18
FS_CARD_TITLE = 16
FS_TEXT = 14
FS_BTN = 20
FS_BTN_SMALL = 16
FS_ENTRY = 20
FS_ENTRY_SMALL = 18
FS_ENTRY_MICRO = 16
FS_BTN_MICRO = 15

class Card(tk.Frame):
    """Contenedor tipo carta con padding y fondo uniforme."""
    def __init__(self, parent, **kwargs):
        super().__init__(parent, bg=COL_CARD, bd=0, highlightthickness=0, **kwargs)
        self.configure(padx=12, pady=12)

class CardTitle(tk.Label):
    def __init__(self, parent, text):
        super().__init__(parent, text=text, bg=COL_CARD, fg=COL_MUTED,
                         font=("DejaVu Sans", FS_CARD_TITLE, "bold"), anchor="w")

class BigButton(tk.Button):
    """Botón primario."""
    def __init__(self, parent, text, command, bg=COL_ACCENT, fg=COL_TEXT, small=False, micro=False, **kwargs):
        super().__init__(parent, text=text, command=command, **kwargs)
        font_size = FS_BTN_MICRO if micro else (FS_BTN_SMALL if small else FS_BTN)
        self.configure(
            bg=bg, fg=fg, activebackground=COL_ACCENT_DARK, activeforeground=fg,
            font=("DejaVu Sans", font_size, "bold"),
            bd=0, padx=14, pady=8, relief="flat",
            highlightthickness=0, cursor="hand2"
        )

class GhostButton(tk.Button):
    """Botón secundario con borde sutil."""
    def __init__(self, parent, text, command, small=False, micro=False, **kwargs):
        super().__init__(parent, text=text, command=command, **kwargs)
        font_size = FS_BTN_MICRO if micro else (FS_BTN_SMALL if small else FS_BTN)
        self.configure(
            bg=COL_CARD, fg=COL_TEXT,
            activebackground=COL_CARD, activeforeground=COL_TEXT,
            font=("DejaVu Sans", font_size),
            bd=1, padx=10, pady=6, relief="ridge",
            highlightthickness=0, cursor="hand2"
        )

class WeightLabel(tk.Label):
    """Marcador de peso principal (grande)."""
    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        self.configure(
            text="0 g",
            font=("DejaVu Sans", FS_HUGE, "bold"),
            bg=COL_CARD, fg=COL_TEXT
        )

class Toast(tk.Frame):
    """Mensaje temporal tipo 'toast' (overlay, auto-oculta, no ocupa layout)."""
    def __init__(self, parent):
        super().__init__(parent, bg="#1f2937", bd=0, highlightthickness=0)
        self._lbl = tk.Label(self, text="", bg="#1f2937", fg=COL_TEXT,
                             font=("DejaVu Sans", FS_TEXT), padx=16, pady=10)
        self._lbl.pack()
        self._after_id = None
        self.place_forget()

    def show(self, text: str, ms: int = 1200, color=None):
        if self._after_id:
            self.after_cancel(self._after_id)
            self._after_id = None
        if color:
            self._lbl.config(fg=color)
        self._lbl.config(text=text)
        w = self.master.winfo_width()
        # Arriba-derecha para no tapar el peso
        self.place(x=max(20, w - 20), y=20, anchor="ne")
        self._after_id = self.after(ms, self.hide)

    def hide(self):
        if self._after_id:
            self.after_cancel(self._after_id)
            self._after_id = None
        self.place_forget()

class NumericKeypad(tk.Frame):
    """
    Teclado numérico en pantalla.
    Variante 'ultracompact' para 1024x600 (cabe entero).
    """
    def __init__(self, parent, textvar: tk.StringVar, on_ok=None, on_clear=None,
                 allow_dot=True, variant="ultracompact"):
        super().__init__(parent, bg=COL_CARD)
        self.var = textvar
        self.on_ok = on_ok
        self.on_clear = on_clear
        self.allow_dot = allow_dot
        self.variant = variant

        # Tamaños comprimidos
        if variant == "ultracompact":
            f_entry = ("DejaVu Sans", FS_ENTRY_MICRO)
            f_btn = ("DejaVu Sans", FS_BTN_MICRO, "bold")
            pad_x = 2; pad_y = 2
        elif variant == "compact":
            f_entry = ("DejaVu Sans", FS_ENTRY_SMALL)
            f_btn = ("DejaVu Sans", FS_BTN_SMALL, "bold")
            pad_x = 3; pad_y = 3
        else:
            f_entry = ("DejaVu Sans", FS_ENTRY)
            f_btn = ("DejaVu Sans", FS_BTN, "bold")
            pad_x = 4; pad_y = 4

        # Display
        self.entry = tk.Entry(self, textvariable=self.var, justify="right",
                              bg="#0b0f14", fg=COL_TEXT, insertbackground=COL_TEXT,
                              font=f_entry, relief="flat")
        self.entry.grid(row=0, column=0, columnspan=3, sticky="ew", pady=(0, pad_y+1))
        self.grid_columnconfigure(0, weight=1, uniform="cols")
        self.grid_columnconfigure(1, weight=1, uniform="cols")
        self.grid_columnconfigure(2, weight=1, uniform="cols")

        def mkbtn(txt, r, c, cmd=None, span=1):
            b = tk.Button(self, text=txt, command=cmd or (lambda t=txt: self._press(t)),
                          bg="#1d2430", fg=COL_TEXT, activebackground="#273043",
                          font=f_btn, bd=0)
            b.grid(row=r, column=c, columnspan=span, sticky="nsew", padx=pad_x, pady=pad_y)
            return b

        # Números
        mkbtn("7", 1, 0); mkbtn("8", 1, 1); mkbtn("9", 1, 2)
        mkbtn("4", 2, 0); mkbtn("5", 2, 1); mkbtn("6", 2, 2)
        mkbtn("1", 3, 0); mkbtn("2", 3, 1); mkbtn("3", 3, 2)
        mkbtn("0", 4, 0, span=2)
        mkbtn("," if self.allow_dot else " ", 4, 2, cmd=self._press_dot)

        # Acciones
        mkbtn("⌫", 5, 0, cmd=self._backspace)
        mkbtn("C", 5, 1, cmd=self._clear)
        mkbtn("OK", 5, 2, cmd=self._ok)

        # Filas comprimidas para que quepa
        for r in range(1, 6):
            self.grid_rowconfigure(r, weight=1, uniform="rows")
        self.grid_rowconfigure(0, weight=0)

    def _press(self, t):
        self.var.set(self.var.get() + str(t))

    def _press_dot(self):
        if not self.allow_dot:
            return
        s = self.var.get()
        if '.' in s or ',' in s:
            return
        self.var.set(s + ",")

    def _backspace(self):
        s = self.var.get()
        if s:
            self.var.set(s[:-1])

    def _clear(self):
        self.var.set("")
        if self.on_clear:
            self.on_clear()

    def _ok(self):
        if self.on_ok:
            self.on_ok()
