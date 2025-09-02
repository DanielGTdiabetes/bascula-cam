# -*- coding: utf-8 -*-
# bascula/ui/widgets.py - MODIFICADO: Fuentes dinámicas en WeightLabel.
import tkinter as tk

# Paleta
COL_BG = "#0a0e1a"; COL_CARD = "#141823"; COL_CARD_HOVER = "#1a1f2e"; COL_TEXT = "#f0f4f8"
COL_MUTED = "#8892a0"; COL_ACCENT = "#00d4aa"; COL_ACCENT_LIGHT = "#00ffcc"; COL_SUCCESS = "#00d4aa"
COL_WARN = "#ffa500"; COL_DANGER = "#ff6b6b"; COL_BORDER = "#2a3142"

# Tamaños
FS_HUGE = 80; FS_TITLE = 18; FS_CARD_TITLE = 15; FS_TEXT = 15; FS_BTN = 20; FS_BTN_SMALL = 18
FS_LIST_ITEM = 15; FS_LIST_HEAD = 14
FS_ENTRY = 16; FS_ENTRY_SMALL = 14; FS_ENTRY_MICRO = 12; FS_BTN_MICRO = 12

SCALE_FACTOR = 1.0; _SCALING_APPLIED = False

def auto_apply_scaling(widget, target=(1024, 600)):
    global SCALE_FACTOR, _SCALING_APPLIED, FS_HUGE, FS_TITLE, FS_CARD_TITLE, FS_TEXT, FS_BTN, FS_BTN_SMALL, FS_ENTRY, FS_ENTRY_SMALL, FS_ENTRY_MICRO, FS_BTN_MICRO, FS_LIST_ITEM, FS_LIST_HEAD
    if _SCALING_APPLIED: return
    try:
        root = widget.winfo_toplevel(); root.update_idletasks()
        sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
        raw = min(sw/target[0], sh/target[1]); SCALE_FACTOR = 1.5 if raw > 1.5 else (0.8 if raw < 0.8 else raw)
        if abs(SCALE_FACTOR - 1.0) > 0.1:
            FS_HUGE=max(40,int(80*SCALE_FACTOR)); FS_TITLE=max(14,int(18*SCALE_FACTOR)); FS_CARD_TITLE=max(12,int(15*SCALE_FACTOR))
            FS_TEXT=max(11,int(15*SCALE_FACTOR)); FS_BTN=max(14,int(20*SCALE_FACTOR)); FS_BTN_SMALL=max(12,int(18*SCALE_FACTOR))
            FS_ENTRY=max(12,int(16*SCALE_FACTOR)); FS_ENTRY_SMALL=max(10,int(14*SCALE_FACTOR)); FS_ENTRY_MICRO=max(9,int(12*SCALE_FACTOR))
            FS_BTN_MICRO=max(10,int(12*SCALE_FACTOR)); FS_LIST_ITEM=max(12,int(15*SCALE_FACTOR)); FS_LIST_HEAD=max(11,int(14*SCALE_FACTOR))
            _SCALING_APPLIED = True
    except Exception:
        pass

def get_scaled_size(px): return int(px * SCALE_FACTOR)

# ---- Componentes base ----

class Card(tk.Frame):
    def __init__(self, parent, min_width=0, min_height=0, **kwargs):
        bg = kwargs.pop("bg", COL_CARD)
        super().__init__(parent, bg=bg, **kwargs)
        self._mw, self._mh = min_width, min_height
        self.configure(highlightbackground=COL_BORDER, highlightthickness=1, bd=0)
        self.bind("<Configure>", self._enforce_min)
        auto_apply_scaling(self)

    def _enforce_min(self, e):
        w, h = e.width, e.height
        mw, mh = get_scaled_size(self._mw), get_scaled_size(self._mh)
        if mw and w < mw: self.config(width=mw)
        if mh and h < mh: self.config(height=mh)

class BigButton(tk.Button):
    def __init__(self, parent, text, command, bg=None, fg=COL_TEXT, small=False, micro=False, **kwargs):
        super().__init__(parent, text=text, command=command, **kwargs)
        bg = bg or COL_ACCENT; fs = FS_BTN_MICRO if micro else (FS_BTN_SMALL if small else FS_BTN)
        self.configure(bg=bg, fg=fg, activebackground=COL_ACCENT_LIGHT, activeforeground=COL_TEXT,
                       bd=0, relief="flat", padx=get_scaled_size(12), pady=get_scaled_size(10),
                       font=("DejaVu Sans", fs, "bold"), cursor="hand2", highlightthickness=0)
        self.bind("<Enter>", lambda e: self.config(bg=COL_ACCENT_LIGHT))
        self.bind("<Leave>", lambda e: self.config(bg=bg))

class GhostButton(tk.Button):
    def __init__(self, parent, text, command, micro=False, **kwargs):
        super().__init__(parent, text=text, command=command, **kwargs)
        fs = FS_BTN_MICRO if micro else FS_BTN_SMALL
        self.configure(bg=COL_CARD, fg=COL_TEXT, activebackground=COL_CARD_HOVER, activeforeground=COL_TEXT,
                       bd=1, relief="solid", highlightthickness=0, highlightbackground=COL_ACCENT,
                       padx=get_scaled_size(12), pady=get_scaled_size(6),
                       font=("DejaVu Sans", fs, "bold"), cursor="hand2")

class StatusIndicator(tk.Canvas):
    def __init__(self, parent, size=12):
        super().__init__(parent, width=size, height=size, bg=parent["bg"], highlightthickness=0, bd=0)
        self._oval = self.create_oval(1,1,size-1,size-1, outline=COL_MUTED, fill=COL_MUTED)
    def set(self, ok=True):
        self.itemconfig(self._oval, fill=(COL_SUCCESS if ok else COL_DANGER), outline=(COL_SUCCESS if ok else COL_DANGER))

class WeightLabel(tk.Label):
    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        # Configuración inicial
        super().config(text="0 g", font=("DejaVu Sans Mono", FS_HUGE, "bold"), bg=kwargs.get("bg", COL_CARD), fg=COL_TEXT, anchor="center")
        self._last_text = ""; self._base_font_size = FS_HUGE
        self._min_fs = max(36, int(FS_HUGE*0.6)); self._max_fs = max(self._min_fs, FS_HUGE)
        self._padx = get_scaled_size(10); self._pady = get_scaled_size(8)
        self.bind("<Configure>", self._on_resize)

    def _on_resize(self, e):
        txt = self["text"]
        if txt == self._last_text and hasattr(self, "_last_w"):
            if abs(self._last_w - e.width) < 5: return
        self._last_text = txt; self._last_w = e.width
        self._fit_text()

    def _fit_text(self):
        # Ajuste dinámico del tamaño de la fuente para caber en el ancho del label
        txt = self["text"] or ""
        w = self.winfo_width()
        if w <= 1: return
        fs = self._max_fs
        self.config(font=("DejaVu Sans Mono", fs, "bold"))
        self.update_idletasks()
        while fs > self._min_fs:
            if self.winfo_reqwidth() <= w - 2*self._padx: break
            fs -= 2
            self.config(font=("DejaVu Sans Mono", fs, "bold"))
            self.update_idletasks()

# --- Teclados / Popups ---

class NumericKeypad(tk.Frame):
    def __init__(self, parent, var_str, on_ok=None, on_cancel=None, allow_dot=False, variant="full", **kwargs):
        super().__init__(parent, bg=COL_CARD, **kwargs)
        self.var = var_str; self.allow_dot = allow_dot
        def put(ch):
            s = self.var.get()
            if ch == "←": self.var.set(s[:-1]); return
            if ch == "." and not self.allow_dot: return
            self.var.set(s + ch)
        def ok(): on_ok() if on_ok else None
        def cancel(): on_cancel() if on_cancel else None

        buttons = [
            ["7","8","9"],
            ["4","5","6"],
            ["1","2","3"],
            ["0",".","←"] if allow_dot else ["0","←","OK"]
        ]
        for r, row in enumerate(buttons):
            fr = tk.Frame(self, bg=COL_CARD); fr.pack(fill="x", expand=True)
            for col, ch in enumerate(row):
                if ch == "OK":
                    BigButton(fr, text="OK", command=ok, micro=True).pack(side="left", expand=True, fill="x", padx=4, pady=4)
                else:
                    BigButton(fr, text=ch, command=lambda c=ch: put(c), micro=True, bg=COL_BORDER).pack(side="left", expand=True, fill="x", padx=4, pady=4)

        fr2 = tk.Frame(self, bg=COL_CARD); fr2.pack(fill="x", pady=6)
        GhostButton(fr2, text="Cancelar", command=cancel, micro=True).pack(side="right", padx=4)

class TextKeyboard(tk.Frame):
    def __init__(self, parent, var_str, on_ok=None, on_cancel=None, **kwargs):
        super().__init__(parent, bg=COL_CARD, **kwargs)
        self.var=var_str
        rows = [
            list("QWERTYUIOP"),
            list("ASDFGHJKL"),
            list("ZXCVBNM")
        ]
        for row in rows:
            fr = tk.Frame(self, bg=COL_CARD); fr.pack(fill="x", expand=True)
            for ch in row:
                BigButton(fr, text=ch, command=lambda c=ch: self._put(c), micro=True, bg=COL_BORDER).pack(side="left", expand=True, fill="x", padx=3, pady=3)
        fr2 = tk.Frame(self, bg=COL_CARD); fr2.pack(fill="x", pady=6)
        BigButton(fr2, text="Espacio", command=lambda: self._put(" "), micro=True, bg=COL_BORDER).pack(side="left", expand=True, fill="x", padx=3)
        GhostButton(fr2, text="OK", command=(on_ok or (lambda:None)), micro=True).pack(side="right", padx=3)
        GhostButton(fr2, text="Cancelar", command=(on_cancel or (lambda:None)), micro=True).pack(side="right", padx=3)

    def _put(self, ch):
        self.var.set(self.var.get()+ch)

class KeypadPopup(tk.Toplevel):
    def __init__(self, parent, title="Introducir valor", initial="", allow_dot=True, on_accept=None, on_cancel=None):
        super().__init__(parent.winfo_toplevel())
        self.withdraw(); self.configure(bg=COL_BG); self.transient(parent.winfo_toplevel()); self.grab_set(); self.title(title)
        self.resizable(False, False)
        try: self.attributes("-topmost", True)
        except Exception: pass
        card = Card(self, min_width=380, min_height=480); card.pack(fill="both", expand=True, padx=10, pady=10)
        tk.Label(card, text=title, bg=COL_CARD, fg=COL_ACCENT, font=("DejaVu Sans", FS_CARD_TITLE, "bold")).pack(anchor="w")
        self._var = tk.StringVar(value=str(initial) if initial is not None else "")
        pad = NumericKeypad(card, self._var, on_ok=self._accept, on_cancel=self._cancel, allow_dot=allow_dot, variant="small")
        pad.pack(fill="both", expand=True, pady=(8,0))
        self._on_accept = on_accept; self._on_cancel = on_cancel

        # Entrada visible
        ent = tk.Entry(card, textvariable=self._var, font=("DejaVu Sans Mono", FS_ENTRY, "bold"), bg=COL_CARD_HOVER, fg=COL_TEXT,
                       relief="flat", insertbackground=COL_TEXT)
        ent.pack(fill="x", padx=6, pady=(8,2))
        ent.focus_set()

        self._center(); self.deiconify()

    def _center(self):
        self.update_idletasks()
        w,h = self.winfo_width(), self.winfo_height()
        x = self.winfo_screenwidth()//2 - w//2
        y = self.winfo_screenheight()//2 - h//2
        self.geometry(f"{w}x{h}+{x}+{y}")

    def _accept(self):
        if self._on_accept: self._on_accept(self._var.get())
        self.destroy()

    def _cancel(self):
        if self._on_cancel: self._on_cancel()
        self.destroy()

class TextKeyPopup(tk.Toplevel):
    def __init__(self, parent, title="Introducir texto", initial="", on_accept=None, on_cancel=None):
        super().__init__(parent.winfo_toplevel())
        self.withdraw(); self.configure(bg=COL_BG); self.transient(parent.winfo_toplevel()); self.grab_set(); self.title(title)
        try: self.attributes("-topmost", True)
        except Exception: pass
        card = Card(self, min_width=400, min_height=420); card.pack(fill="both", expand=True, padx=10, pady=10)

        tk.Label(card, text=title, bg=COL_CARD, fg=COL_ACCENT, font=("DejaVu Sans", FS_CARD_TITLE, "bold")).pack(anchor="w", pady=(0,4))

        self._var = tk.StringVar(value=str(initial) if initial is not None else "")

        # Entrada visible + teclado
        ent = tk.Entry(card, textvariable=self._var, font=("DejaVu Sans Mono", FS_ENTRY, "bold"), bg=COL_CARD_HOVER, fg=COL_TEXT,
                       relief="flat", insertbackground=COL_TEXT)
        ent.pack(fill="x", padx=6, pady=(4,6)); ent.focus_set()

        kbd = TextKeyboard(card, self._var, on_ok=self._accept, on_cancel=self._cancel)
        kbd.pack(fill="both", expand=True, pady=(6,4))

        fr = tk.Frame(card, bg=COL_CARD); fr.pack(fill="x")
        GhostButton(fr, text="Cancelar", command=self._cancel, micro=True).pack(side="left", padx=3)
        GhostButton(fr, text="Aceptar", command=self._accept, micro=True).pack(side="right", padx=3)

        self._center(); self.deiconify()

    def _center(self):
        self.update_idletasks()
        w,h = self.winfo_width(), self.winfo_height()
        x = self.winfo_screenwidth()//2 - w//2
        y = self.winfo_screenheight()//2 - h//2
        self.geometry(f"{w}x{h}+{x}+{y}")

    def _accept(self):
        if hasattr(self, "_on_accept") and self._on_accept: self._on_accept(self._var.get())
        self.destroy()

    def _cancel(self):
        if hasattr(self, "_on_cancel") and self._on_cancel: self._on_cancel()
        self.destroy()

class Toast(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.withdraw(); self.overrideredirect(True); self.configure(bg=COL_BG)
        self._lbl = tk.Label(self, text="", bg=COL_ACCENT, fg=COL_BG, font=("DejaVu Sans", FS_ENTRY, "bold"),
                             padx=get_scaled_size(10), pady=get_scaled_size(6))
        self._lbl.pack()
        self._after = None

    def show(self, text, ms=1200, bg=None):
        self._lbl.configure(text=text, bg=(bg or COL_ACCENT))
        self.update_idletasks()
        x = self.winfo_screenwidth() - self._lbl.winfo_width() - 24
        y = self.winfo_screenheight() - self._lbl.winfo_height() - 48
        self.geometry(f"+{x}+{y}")
        self.deiconify()
        if self._after:
            try: self.after_cancel(self._after)
            except Exception: pass
        self._after = self.after(ms, self._hide)

    def _hide(self):
        self.withdraw(); self._after = None

# ================== Scroll por dedo + Frame desplazable ==================

# --- Scroll táctil universal (Canvas/Text/Listbox/Treeview) ---
def bind_touch_scroll(widget, *, units_divisor=1, min_drag_px=2):
    """
    Scroll táctil por arrastre. Funciona en Canvas, Listbox, Text y ttk.Treeview.
    - 'units_divisor' más bajo = scroll más sensible.
    - Se devuelve 'break' para evitar que Treeview capture el drag como selección durante el gesto.
    """
    st = {"y": 0, "drag": False}

    def _press(e):
        st["y"] = e.y
        st["drag"] = False
        if hasattr(widget, 'yview_scan'):
            widget.yview_scan("mark", e.x, e.y)
        return "break"

    def _drag(e):
        dy = e.y - st["y"]
        if abs(dy) >= min_drag_px:
            st["drag"] = True
        st["y"] = e.y

        if hasattr(widget, 'yview_scan'):
            widget.yview_scan("dragto", e.x, e.y)
        elif hasattr(widget, 'yview_scroll'):
            try:
                widget.yview_scroll(int(-dy / units_divisor), "units")
            except Exception:
                pass
        return "break"

    def _release(_e):
        if st["drag"]:
            st["drag"] = False
            return "break"

    try:
        widget.bind("<ButtonPress-1>", _press, add="+")
        widget.bind("<B1-Motion>", _drag, add="+")
        widget.bind("<ButtonRelease-1>", _release, add="+")
    except Exception:
        pass
