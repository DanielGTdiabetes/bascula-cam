# -*- coding: utf-8 -*-
import tkinter as tk
import math

# Paleta
COL_BG = "#0a0e1a"
COL_CARD = "#141823"
COL_CARD_HOVER = "#1a1f2e"
COL_TEXT = "#f0f4f8"
COL_MUTED = "#8892a0"
COL_ACCENT = "#00d4aa"
COL_ACCENT_DARK = "#00a383"
COL_ACCENT_LIGHT = "#00ffcc"
COL_SUCCESS = "#00d4aa"
COL_WARN = "#ffa500"
COL_DANGER = "#ff6b6b"
COL_GRADIENT_1 = "#00d4aa"
COL_GRADIENT_2 = "#00a383"
COL_BORDER = "#2a3142"
COL_SHADOW = "#050810"

# Tamaños pensados para 1024x600
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

class Card(tk.Frame):
    """Contenedor tipo carta con sombra y bordes sutiles."""
    def __init__(self, parent, **kwargs):
        self.shadow_frame = tk.Frame(parent, bg=COL_BG, bd=0, highlightthickness=0)
        super().__init__(
            self.shadow_frame, bg=COL_CARD, bd=1,
            highlightbackground=COL_BORDER, highlightthickness=1,
            relief="flat", **kwargs
        )
        # padding ligeramente menor para aprovechar ancho
        self.configure(padx=14, pady=12)
        super().pack(padx=2, pady=2, fill="both", expand=True)

        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)

    def _on_enter(self, e):
        self.configure(bg=COL_CARD_HOVER)
        for child in self.winfo_children():
            if hasattr(child, 'configure'):
                try:
                    child.configure(bg=COL_CARD_HOVER)
                except tk.TclError:
                    pass

    def _on_leave(self, e):
        self.configure(bg=COL_CARD)
        for child in self.winfo_children():
            if hasattr(child, 'configure'):
                try:
                    child.configure(bg=COL_CARD)
                except tk.TclError:
                    pass

    def grid(self, **kwargs):
        self.shadow_frame.grid(**kwargs)

    def pack(self, **kwargs):
        self.shadow_frame.pack(**kwargs)

class CardTitle(tk.Label):
    def __init__(self, parent, text):
        super().__init__(
            parent, text=text, bg=COL_CARD, fg=COL_ACCENT,
            font=("DejaVu Sans", FS_CARD_TITLE, "bold"), anchor="w"
        )
        self.underline = tk.Frame(parent, bg=COL_ACCENT, height=2)

class BigButton(tk.Button):
    def __init__(self, parent, text, command, bg=None, fg=COL_TEXT, small=False, micro=False, **kwargs):
        super().__init__(parent, text=text, command=command, **kwargs)
        bg = bg or COL_ACCENT
        font_size = FS_BTN_MICRO if micro else (FS_BTN_SMALL if small else FS_BTN)
        self.configure(
            bg=bg, fg=fg,
            activebackground=COL_ACCENT_LIGHT, activeforeground=COL_TEXT,
            font=("DejaVu Sans Mono", font_size, "bold"),
            bd=0, padx=20, pady=10, relief="flat",
            highlightthickness=0, cursor="hand2"
        )
        self.default_bg = bg
        self.bind("<Enter>", lambda e: self.configure(bg=COL_ACCENT_LIGHT))
        self.bind("<Leave>", lambda e: self.configure(bg=self.default_bg))

class GhostButton(tk.Button):
    def __init__(self, parent, text, command, small=False, micro=False, **kwargs):
        super().__init__(parent, text=text, command=command, **kwargs)
        font_size = FS_BTN_MICRO if micro else (FS_BTN_SMALL if small else FS_BTN)
        self.configure(
            bg=COL_CARD, fg=COL_ACCENT,
            activebackground=COL_CARD_HOVER, activeforeground=COL_ACCENT_LIGHT,
            font=("DejaVu Sans", font_size),
            bd=1, padx=16, pady=8, relief="solid",
            highlightbackground=COL_ACCENT, highlightcolor=COL_ACCENT,
            highlightthickness=1, cursor="hand2"
        )
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)

    def _on_enter(self, e):
        self.configure(bg=COL_CARD_HOVER, fg=COL_ACCENT_LIGHT)

    def _on_leave(self, e):
        self.configure(bg=COL_CARD, fg=COL_ACCENT)

class WeightLabel(tk.Label):
    """Marcador de peso principal con animación de cambio."""
    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        self.configure(text="0 g", font=("DejaVu Sans Mono", FS_HUGE), bg=COL_CARD, fg=COL_TEXT)
        self.last_value = "0 g"
        self.animation_after = None

    def config(self, **kwargs):
        if 'text' in kwargs:
            new_text = kwargs['text']
            if new_text != self.last_value:
                self.configure(fg=COL_ACCENT_LIGHT)
                if self.animation_after:
                    self.after_cancel(self.animation_after)
                self.animation_after = self.after(200, lambda: self.configure(fg=COL_TEXT))
                self.last_value = new_text
        super().config(**kwargs)

class Toast(tk.Frame):
    """Mensaje temporal (no persistente)."""
    def __init__(self, parent):
        super().__init__(parent, bg=COL_CARD, bd=0, highlightthickness=1, highlightbackground=COL_BORDER)
        self._lbl = tk.Label(self, text="", bg=COL_CARD, fg=COL_TEXT, font=("DejaVu Sans", FS_TEXT), padx=20, pady=12)
        self._lbl.pack()
        self._after_id = None
        self.place_forget()
        self._icon = tk.Label(self, text="✓", bg=COL_CARD, fg=COL_SUCCESS, font=("DejaVu Sans", 18), padx=10)

    def show(self, text: str, ms: int = 1500, color=None):
        if self._after_id:
            self.after_cancel(self._after_id)
            self._after_id = None
        display_color = color or COL_SUCCESS
        self._lbl.config(text=text, fg=display_color)
        if color == COL_SUCCESS:
            self._icon.config(text="✓", fg=COL_SUCCESS)
        elif color == COL_WARN:
            self._icon.config(text="⚠", fg=COL_WARN)
        elif color == COL_DANGER:
            self._icon.config(text="✕", fg=COL_DANGER)
        else:
            self._icon.config(text="ℹ", fg=COL_ACCENT)
        self._icon.pack(side="left", before=self._lbl)
        w = self.master.winfo_width()
        self.place(x=max(20, w - 20), y=20, anchor="ne")
        self.lift()
        self._after_id = self.after(ms, self.hide)

    def hide(self):
        if self._after_id:
            self.after_cancel(self._after_id)
            self._after_id = None
        self._icon.pack_forget()
        self.place_forget()

class NumericKeypad(tk.Frame):
    """Teclado numérico elegante (ultracompact por defecto para 1024x600)."""
    def __init__(self, parent, textvar: tk.StringVar, on_ok=None, on_clear=None, allow_dot=True, variant="ultracompact"):
        super().__init__(parent, bg=COL_CARD)
        self.var = textvar
        self.on_ok = on_ok
        self.on_clear = on_clear
        self.allow_dot = allow_dot
        self.variant = variant

        if variant == "ultracompact":
            f_entry = ("DejaVu Sans Mono", FS_ENTRY_MICRO)
            f_btn = ("DejaVu Sans", FS_BTN_MICRO, "bold")
            pad_x = 3; pad_y = 3
        elif variant == "compact":
            f_entry = ("DejaVu Sans Mono", FS_ENTRY_SMALL)
            f_btn = ("DejaVu Sans", FS_BTN_SMALL, "bold")
            pad_x = 4; pad_y = 4
        else:
            f_entry = ("DejaVu Sans Mono", FS_ENTRY)
            f_btn = ("DejaVu Sans", FS_BTN, "bold")
            pad_x = 5; pad_y = 5

        self.entry = tk.Entry(
            self, textvariable=self.var, justify="right",
            bg="#1a1f2e", fg=COL_TEXT, insertbackground=COL_ACCENT,
            font=f_entry, relief="flat", bd=8,
            highlightbackground=COL_BORDER, highlightthickness=1
        )
        self.entry.grid(row=0, column=0, columnspan=3, sticky="ew", pady=(0, pad_y+3))

        self.grid_columnconfigure(0, weight=1, uniform="cols")
        self.grid_columnconfigure(1, weight=1, uniform="cols")
        self.grid_columnconfigure(2, weight=1, uniform="cols")

        def mkbtn(txt, r, c, cmd=None, span=1, special=False):
            bg_color = COL_ACCENT if special else "#1a1f2e"
            fg_color = COL_TEXT
            hover_bg = COL_ACCENT_LIGHT if special else "#2a3142"
            b = tk.Button(
                self, text=txt, command=cmd or (lambda t=txt: self._press(t)),
                bg=bg_color, fg=fg_color,
                activebackground=hover_bg, activeforeground=COL_TEXT,
                font=f_btn, bd=0, relief="flat"
            )
            b.grid(row=r, column=c, columnspan=span, sticky="nsew", padx=pad_x, pady=pad_y)
            b.bind("<Enter>", lambda e: b.configure(bg=hover_bg))
            b.bind("<Leave>", lambda e: b.configure(bg=bg_color))
            return b

        # Distribución 6 filas (cabe en 600 px junto a las cartas + scroll en Ajustes)
        mkbtn("7", 1, 0); mkbtn("8", 1, 1); mkbtn("9", 1, 2)
        mkbtn("4", 2, 0); mkbtn("5", 2, 1); mkbtn("6", 2, 2)
        mkbtn("1", 3, 0); mkbtn("2", 3, 1); mkbtn("3", 3, 2)
        mkbtn("0", 4, 0, span=2)
        if self.allow_dot:
            mkbtn(".", 4, 2, cmd=self._press_dot)
        else:
            mkbtn("", 4, 2)  # hueco
        mkbtn("⌫", 5, 0, cmd=self._backspace, special=False)
        mkbtn("C", 5, 1, cmd=self._clear, special=False)
        mkbtn("✓", 5, 2, cmd=self._ok, special=True)

        for r in range(1, 6):
            self.grid_rowconfigure(r, weight=1, uniform="rows")
        self.grid_rowconfigure(0, weight=0)

    def _press(self, t):
        current = self.var.get()
        if len(current) < 12:
            self.var.set(current + str(t))

    def _press_dot(self):
        if not self.allow_dot:
            return
        s = self.var.get()
        if '.' not in s and ',' not in s:
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
    def __init__(self, parent, size=12):
        super().__init__(parent, width=size, height=size, bg=COL_CARD, highlightthickness=0)
        self.size = size
        self.status = "inactive"
        self.pulse_after = None
        self._draw_indicator()

    def _draw_indicator(self):
        self.delete("all")
        center = self.size // 2
        radius = (self.size // 2) - 2
        colors = {"active": COL_SUCCESS, "warning": COL_WARN, "error": COL_DANGER, "inactive": COL_MUTED}
        color = colors.get(self.status, COL_MUTED)
        self.create_oval(center - radius, center - radius, center + radius, center + radius,
                         fill=color, outline="", tags="indicator")
        if self.status == "active":
            self.create_oval(center - radius + 2, center - radius + 2,
                             center - radius + 4, center - radius + 4,
                             fill=COL_ACCENT_LIGHT, outline="")

    def set_status(self, status):
        self.status = status
        self._draw_indicator()
        if status == "active" and not self.pulse_after:
            self._pulse()

    def _pulse(self):
        if self.status != "active":
            self.pulse_after = None
            return
        self.itemconfig("indicator", fill=COL_ACCENT_LIGHT)
        self.after(200, lambda: self.itemconfig("indicator", fill=COL_SUCCESS))
        self.pulse_after = self.after(1000, self._pulse)
