# -*- coding: utf-8 -*-
import tkinter as tk

# Paleta
COL_BG = "#0f1115"
COL_CARD = "#151a22"
COL_TEXT = "#e5e7eb"
COL_MUTED = "#94a3b8"
COL_ACCENT = "#4f46e5"
COL_ACCENT_DARK = "#4338ca"
COL_SUCCESS = "#10b981"
COL_WARN = "#f59e0b"
COL_DANGER = "#ef4444"

class Card(tk.Frame):
    """Contenedor tipo carta con padding y fondo uniforme."""
    def __init__(self, parent, **kwargs):
        super().__init__(parent, bg=COL_CARD, bd=0, highlightthickness=0, **kwargs)
        self.configure(padx=18, pady=18)

class CardTitle(tk.Label):
    def __init__(self, parent, text):
        super().__init__(parent, text=text, bg=COL_CARD, fg=COL_MUTED,
                         font=("DejaVu Sans", 18, "bold"), anchor="w")

class BigButton(tk.Button):
    """Botón grande primario."""
    def __init__(self, parent, text, command, bg=COL_ACCENT, fg=COL_TEXT, **kwargs):
        super().__init__(parent, text=text, command=command, **kwargs)
        self.configure(
            bg=bg, fg=fg, activebackground=COL_ACCENT_DARK, activeforeground=fg,
            font=("DejaVu Sans", 24, "bold"),
            bd=0, padx=22, pady=12, relief="flat",
            highlightthickness=0, cursor="hand2"
        )

class GhostButton(tk.Button):
    """Botón secundario con borde sutil."""
    def __init__(self, parent, text, command, **kwargs):
        super().__init__(parent, text=text, command=command, **kwargs)
        self.configure(
            bg=COL_CARD, fg=COL_TEXT,
            activebackground=COL_CARD, activeforeground=COL_TEXT,
            font=("DejaVu Sans", 20),
            bd=1, padx=18, pady=10, relief="ridge",
            highlightthickness=0, cursor="hand2"
        )

class WeightLabel(tk.Label):
    """Marcador de peso principal (muy grande)."""
    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        self.configure(
            text="— g",
            font=("DejaVu Sans", 84, "bold"),
            bg=COL_CARD, fg=COL_TEXT
        )

class Toast(tk.Frame):
    """Mensaje temporal tipo 'toast' (auto-oculta)."""
    def __init__(self, parent):
        super().__init__(parent, bg="#1f2937", bd=0, highlightthickness=0)
        self._lbl = tk.Label(self, text="", bg="#1f2937", fg=COL_TEXT,
                             font=("DejaVu Sans", 20), padx=16, pady=10)
        self._lbl.pack()
        self._after_id = None
        self.place_forget()

    def show(self, text: str, ms: int = 2000, color=None):
        if self._after_id:
            self.after_cancel(self._after_id)
            self._after_id = None
        if color:
            self._lbl.config(fg=color)
        self._lbl.config(text=text)
        w = self.master.winfo_width()
        h = self.master.winfo_height()
        self.place(x=int(w//2), y=h-120, anchor="s")
        self.after(10, self._recenter)
        self._after_id = self.after(ms, self.hide)

    def _recenter(self):
        w = self.master.winfo_width()
        self.place_configure(x=int(w//2))

    def hide(self):
        if self._after_id:
            self.after_cancel(self._after_id)
            self._after_id = None
        self.place_forget()

class NumericKeypad(tk.Frame):
    """
    Teclado numérico en pantalla para introducir números (peso patrón).
    Vincúlalo a un StringVar externo y pásale callbacks para Guardar/Cancelar.
    """
    def __init__(self, parent, textvar: tk.StringVar, on_ok=None, on_clear=None, allow_dot=True):
        super().__init__(parent, bg=COL_CARD)
        self.var = textvar
        self.on_ok = on_ok
        self.on_clear = on_clear
        self.allow_dot = allow_dot

        # display
        self.entry = tk.Entry(self, textvariable=self.var, justify="right",
                              bg="#0b0f14", fg=COL_TEXT, insertbackground=COL_TEXT,
                              font=("DejaVu Sans", 24), relief="flat")
        self.entry.grid(row=0, column=0, columnspan=3, sticky="ew", pady=(0, 10))
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)
        self.grid_columnconfigure(2, weight=1)

        def mkbtn(txt, r, c, cmd=None, span=1):
            b = tk.Button(self, text=txt, command=cmd or (lambda t=txt: self._press(t)),
                          bg="#1d2430", fg=COL_TEXT, activebackground="#273043",
                          font=("DejaVu Sans", 22, "bold"), bd=0, height=1)
            b.grid(row=r, column=c, columnspan=span, sticky="nsew", padx=4, pady=4)
            return b

        # filas 1-3
        mkbtn("7", 1, 0); mkbtn("8", 1, 1); mkbtn("9", 1, 2)
        mkbtn("4", 2, 0); mkbtn("5", 2, 1); mkbtn("6", 2, 2)
        mkbtn("1", 3, 0); mkbtn("2", 3, 1); mkbtn("3", 3, 2)
        # fila 4
        mkbtn("0", 4, 0, span=2)
        mkbtn("," if self.allow_dot else " ", 4, 2, cmd=lambda: self._press_dot())
        # fila 5: acciones
        mkbtn("⌫", 5, 0, cmd=self._backspace)
        mkbtn("C", 5, 1, cmd=self._clear)
        mkbtn("OK", 5, 2, cmd=self._ok)

        for r in range(1, 6):
            self.grid_rowconfigure(r, weight=1)

    def _press(self, t):
        self.var.set(self.var.get() + str(t))

    def _press_dot(self):
        if not self.allow_dot:
            return
        s = self.var.get()
        if ('.' in s) or (',' in s):
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
