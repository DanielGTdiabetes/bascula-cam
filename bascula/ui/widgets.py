# -*- coding: utf-8 -*-
import tkinter as tk

# ─────────────────────────────────────────────────────────────────────────────
# PALETA (oscura, alto contraste)
# ─────────────────────────────────────────────────────────────────────────────
COL_BG           = "#0a0e1a"
COL_CARD         = "#141823"
COL_CARD_HOVER   = "#1a1f2e"
COL_TEXT         = "#f0f4f8"
COL_MUTED        = "#8892a0"
COL_ACCENT       = "#00d4aa"
COL_ACCENT_DARK  = "#00a383"
COL_ACCENT_LIGHT = "#00ffcc"
COL_SUCCESS      = "#00d4aa"
COL_WARN         = "#ffa500"
COL_DANGER       = "#ff6b6b"
COL_BORDER       = "#2a3142"

# ─────────────────────────────────────────────────────────────────────────────
# TAMAÑOS (SE RELLENAN DINÁMICAMENTE SEGÚN RESOLUCIÓN)
# ─────────────────────────────────────────────────────────────────────────────
FS_HUGE = 56
FS_TITLE = 20
FS_CARD_TITLE = 17
FS_TEXT = 15
FS_BTN = 18
FS_BTN_SMALL = 16
FS_ENTRY = 18
FS_ENTRY_SMALL = 16
FS_ENTRY_MICRO = 14
FS_BTN_MICRO = 14

CARD_PADX = 14
CARD_PADY = 12
GRID_PADX = 8
GRID_PADY = 8

# Sugerencia del teclado para la altura actual (la define apply_resolution)
KEYPAD_VARIANT_DEFAULT = "ultracompact"  # para 600px; "compact" si 800px


def apply_resolution(screen_w: int, screen_h: int):
    """
    Ajusta tamaños, paddings y variante de teclado en función de la altura.
    - <= 620 px: perfil 'h600' (Pi 7'' 1024x600) → compacto al máximo
    - >= 760 px: perfil 'h800' (1024x800) → un poco más grande
    - intermedio: perfil medio
    Devuelve la variante de teclado recomendada: 'ultracompact' o 'compact'.
    """
    global FS_HUGE, FS_TITLE, FS_CARD_TITLE, FS_TEXT
    global FS_BTN, FS_BTN_SMALL, FS_BTN_MICRO
    global FS_ENTRY, FS_ENTRY_SMALL, FS_ENTRY_MICRO
    global CARD_PADX, CARD_PADY, GRID_PADX, GRID_PADY
    global KEYPAD_VARIANT_DEFAULT

    if screen_h <= 620:
        # PERFIL 1024x600 (muy compacto)
        FS_HUGE        = 52
        FS_TITLE       = 18
        FS_CARD_TITLE  = 16
        FS_TEXT        = 14
        FS_BTN         = 17
        FS_BTN_SMALL   = 15
        FS_BTN_MICRO   = 14
        FS_ENTRY       = 18
        FS_ENTRY_SMALL = 16
        FS_ENTRY_MICRO = 14

        CARD_PADX = 12
        CARD_PADY = 10
        GRID_PADX = 6
        GRID_PADY = 6

        KEYPAD_VARIANT_DEFAULT = "ultracompact"

    elif screen_h >= 760:
        # PERFIL 1024x800 (más desahogado)
        FS_HUGE        = 64
        FS_TITLE       = 22
        FS_CARD_TITLE  = 18
        FS_TEXT        = 16
        FS_BTN         = 20
        FS_BTN_SMALL   = 18
        FS_BTN_MICRO   = 16
        FS_ENTRY       = 20
        FS_ENTRY_SMALL = 18
        FS_ENTRY_MICRO = 16

        CARD_PADX = 16
        CARD_PADY = 14
        GRID_PADX = 10
        GRID_PADY = 10

        KEYPAD_VARIANT_DEFAULT = "compact"

    else:
        # PERFIL intermedio (por si negotiate 1024x700~720)
        FS_HUGE        = 58
        FS_TITLE       = 20
        FS_CARD_TITLE  = 17
        FS_TEXT        = 15
        FS_BTN         = 19
        FS_BTN_SMALL   = 17
        FS_BTN_MICRO   = 15
        FS_ENTRY       = 19
        FS_ENTRY_SMALL = 17
        FS_ENTRY_MICRO = 15

        CARD_PADX = 14
        CARD_PADY = 12
        GRID_PADX = 8
        GRID_PADY = 8

        KEYPAD_VARIANT_DEFAULT = "compact"


# ─────────────────────────────────────────────────────────────────────────────
# WIDGETS
# ─────────────────────────────────────────────────────────────────────────────
class Card(tk.Frame):
    """Contenedor tipo carta con borde sutil; padding ajustable."""
    def __init__(self, parent, **kwargs):
        super().__init__(
            parent, bg=COL_CARD, bd=1,
            highlightbackground=COL_BORDER, highlightthickness=1,
            relief="flat", **kwargs
        )
        self.configure(padx=CARD_PADX, pady=CARD_PADY)


class CardTitle(tk.Label):
    def __init__(self, parent, text):
        super().__init__(
            parent, text=text, bg=COL_CARD, fg=COL_ACCENT,
            font=("DejaVu Sans", FS_CARD_TITLE, "bold"), anchor="w"
        )


class BigButton(tk.Button):
    """Botón principal."""
    def __init__(self, parent, text, command, bg=None, fg=COL_TEXT, small=False, micro=False, **kwargs):
        super().__init__(parent, text=text, command=command, **kwargs)
        bg = bg or COL_ACCENT
        font_size = FS_BTN_MICRO if micro else (FS_BTN_SMALL if small else FS_BTN)
        self.configure(
            bg=bg, fg=fg,
            activebackground=COL_ACCENT_LIGHT, activeforeground=COL_TEXT,
            font=("DejaVu Sans", font_size, "bold"),
            bd=0, padx=16, pady=8, relief="flat",
            highlightthickness=0, cursor="hand2"
        )


class GhostButton(tk.Button):
    """Botón secundario con borde."""
    def __init__(self, parent, text, command, small=False, micro=False, **kwargs):
        super().__init__(parent, text=text, command=command, **kwargs)
        font_size = FS_BTN_MICRO if micro else (FS_BTN_SMALL if small else FS_BTN)
        self.configure(
            bg=COL_CARD, fg=COL_ACCENT,
            activebackground=COL_CARD_HOVER, activeforeground=COL_ACCENT_LIGHT,
            font=("DejaVu Sans", font_size),
            bd=1, padx=14, pady=6, relief="ridge",
            highlightbackground=COL_ACCENT, highlightthickness=1, cursor="hand2"
        )


class WeightLabel(tk.Label):
    """Marcador principal del peso (grande)."""
    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        self.configure(
            text="0 g",
            font=("DejaVu Sans", FS_HUGE, "bold"),
            bg=COL_CARD, fg=COL_TEXT
        )


class Toast(tk.Frame):
    """Mensaje temporal no persistente (overlay)."""
    def __init__(self, parent):
        super().__init__(parent, bg=COL_CARD, bd=0, highlightthickness=1, highlightbackground=COL_BORDER)
        self._lbl = tk.Label(self, text="", bg=COL_CARD, fg=COL_TEXT,
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
        self.place(x=max(20, w - 20), y=20, anchor="ne")
        self.lift()
        self._after_id = self.after(ms, self.hide)

    def hide(self):
        if self._after_id:
            self.after_cancel(self._after_id)
            self._after_id = None
        self.place_forget()


class NumericKeypad(tk.Frame):
    """
    Teclado numérico en pantalla.
    - 'ultracompact' para 600 px de alto.
    - 'compact' para 800 px de alto.
    """
    def __init__(self, parent, textvar: tk.StringVar, on_ok=None, on_clear=None,
                 allow_dot=True, variant=None):
        super().__init__(parent, bg=COL_CARD)
        self.var = textvar
        self.on_ok = on_ok
        self.on_clear = on_clear
        self.allow_dot = allow_dot

        # Si no pasa variante, usamos la global decidida por apply_resolution
        self.variant = variant or KEYPAD_VARIANT_DEFAULT

        if self.variant == "ultracompact":
            f_entry = ("DejaVu Sans", FS_ENTRY_MICRO)
            f_btn   = ("DejaVu Sans", FS_BTN_MICRO, "bold")
            pad_x = 2; pad_y = 2
        elif self.variant == "compact":
            f_entry = ("DejaVu Sans", FS_ENTRY_SMALL)
            f_btn   = ("DejaVu Sans", FS_BTN_SMALL, "bold")
            pad_x = 3; pad_y = 3
        else:
            f_entry = ("DejaVu Sans", FS_ENTRY)
            f_btn   = ("DejaVu Sans", FS_BTN, "bold")
            pad_x = 4; pad_y = 4

        # Display
        self.entry = tk.Entry(self, textvariable=self.var, justify="right",
                              bg="#0b0f14", fg=COL_TEXT, insertbackground=COL_TEXT,
                              font=f_entry, relief="flat")
        self.entry.grid(row=0, column=0, columnspan=3, sticky="ew", pady=(0, pad_y + 2))

        # Columnas
        for c in range(3):
            self.grid_columnconfigure(c, weight=1, uniform="cols")

        def mkbtn(txt, r, c, cmd=None, span=1):
            b = tk.Button(self, text=txt, command=cmd or (lambda t=txt: self._press(t)),
                          bg="#1d2430", fg=COL_TEXT, activebackground="#273043",
                          font=f_btn, bd=0)
            b.grid(row=r, column=c, columnspan=span, sticky="nsew", padx=pad_x, pady=pad_y)
            return b

        # Filas comprimidas para caber sin recortar
        mkbtn("7", 1, 0); mkbtn("8", 1, 1); mkbtn("9", 1, 2)
        mkbtn("4", 2, 0); mkbtn("5", 2, 1); mkbtn("6", 2, 2)
        mkbtn("1", 3, 0); mkbtn("2", 3, 1); mkbtn("3", 3, 2)
        mkbtn("0", 4, 0, span=2)
        mkbtn("." if self.allow_dot else " ", 4, 2, cmd=self._press_dot)
        mkbtn("⌫", 5, 0, cmd=self._backspace)
        mkbtn("C", 5, 1, cmd=self._clear)
        mkbtn("OK", 5, 2, cmd=self._ok)

        for r in range(1, 6):
            self.grid_rowconfigure(r, weight=1, uniform="rows")
        self.grid_rowconfigure(0, weight=0)

    # ── Acciones
    def _press(self, t):
        self.var.set(self.var.get() + str(t))

    def _press_dot(self):
        if not self.allow_dot:
            return
        s = self.var.get()
        if '.' in s or ',' in s:
            return
        self.var.set(s + ".")

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


class StatusIndicator(tk.Canvas):
    """Punto de estado (activo/inactivo/advertencia/error)."""
    def __init__(self, parent, size=12, bg_color=COL_CARD):
        super().__init__(parent, width=size, height=size, bg=bg_color, highlightthickness=0)
        self.size = size
        self.status = "inactive"
        self._draw()

    def _draw(self):
        self.delete("all")
        center = self.size // 2
        radius = max(2, (self.size // 2) - 1)
        color = {
            "active": COL_SUCCESS,
            "warning": COL_WARN,
            "error": COL_DANGER,
            "inactive": COL_MUTED
        }.get(self.status, COL_MUTED)
        self.create_oval(center - radius, center - radius, center + radius, center + radius,
                         fill=color, outline="")

    def set_status(self, status: str):
        self.status = status
        self._draw()
