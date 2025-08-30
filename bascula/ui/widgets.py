# -*- coding: utf-8 -*-
# bascula/ui/widgets.py - VERSIÓN POPUP TECLADO + COMPONENTES
import tkinter as tk

# Paleta de colores
COL_BG = "#0a0e1a"
COL_CARD = "#141823"
COL_CARD_HOVER = "#1a1f2e"
COL_TEXT = "#f0f4f8"
COL_MUTED = "#8892a0"
COL_ACCENT = "#00d4aa"
COL_ACCENT_LIGHT = "#00ffcc"
COL_SUCCESS = "#00d4aa"
COL_WARN = "#ffa500"
COL_DANGER = "#ff6b6b"
COL_BORDER = "#2a3142"

# TAMAÑOS BASE
FS_HUGE = 48
FS_TITLE = 18
FS_CARD_TITLE = 15
FS_TEXT = 13
FS_BTN = 16
FS_BTN_SMALL = 14
FS_ENTRY = 16
FS_ENTRY_SMALL = 14
FS_ENTRY_MICRO = 12
FS_BTN_MICRO = 12

SCALE_FACTOR = 1.0
_SCALING_APPLIED = False

def auto_apply_scaling(widget, target=(1024, 600)):
    global SCALE_FACTOR, _SCALING_APPLIED
    global FS_HUGE, FS_TITLE, FS_CARD_TITLE, FS_TEXT, FS_BTN
    global FS_BTN_SMALL, FS_ENTRY, FS_ENTRY_SMALL, FS_ENTRY_MICRO, FS_BTN_MICRO
    if _SCALING_APPLIED:
        return
    try:
        root = widget.winfo_toplevel()
        root.update_idletasks()
        sw = root.winfo_screenwidth()
        sh = root.winfo_screenheight()
        scale_w = sw / target[0]
        scale_h = sh / target[1]
        raw = min(scale_w, scale_h)
        SCALE_FACTOR = 1.5 if raw > 1.5 else (0.8 if raw < 0.8 else raw)
        if abs(SCALE_FACTOR - 1.0) > 0.1:
            FS_HUGE = max(32, int(48 * SCALE_FACTOR))
            FS_TITLE = max(14, int(18 * SCALE_FACTOR))
            FS_CARD_TITLE = max(12, int(15 * SCALE_FACTOR))
            FS_TEXT = max(10, int(13 * SCALE_FACTOR))
            FS_BTN = max(12, int(16 * SCALE_FACTOR))
            FS_BTN_SMALL = max(10, int(14 * SCALE_FACTOR))
            FS_ENTRY = max(12, int(16 * SCALE_FACTOR))
            FS_ENTRY_SMALL = max(10, int(14 * SCALE_FACTOR))
            FS_ENTRY_MICRO = max(8, int(12 * SCALE_FACTOR))
            FS_BTN_MICRO = max(8, int(12 * SCALE_FACTOR))
        _SCALING_APPLIED = True
    except Exception:
        SCALE_FACTOR = 1.0

def get_scaled_size(base_size):
    try:
        return max(8, int(base_size * SCALE_FACTOR))
    except Exception:
        return base_size

class Card(tk.Frame):
    def __init__(self, parent, min_width=None, min_height=None, **kwargs):
        self.shadow_frame = tk.Frame(parent, bg=COL_BG, bd=0, highlightthickness=0)
        if min_width:
            self.shadow_frame.configure(width=get_scaled_size(min_width))
        if min_height:
            self.shadow_frame.configure(height=get_scaled_size(min_height))
        super().__init__(self.shadow_frame, bg=COL_CARD,
                         bd=1, highlightbackground=COL_BORDER,
                         highlightthickness=1, relief="flat", **kwargs)
        pad = get_scaled_size(16)
        self.configure(padx=pad, pady=get_scaled_size(14))
        super().pack(padx=2, pady=2, fill="both", expand=True)
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
    def pack(self, *a, **k): return self.shadow_frame.pack(*a, **k)
    def grid(self, *a, **k): return self.shadow_frame.grid(*a, **k)
    def place(self, *a, **k): return self.shadow_frame.place(*a, **k)
    def destroy(self):
        try: super().destroy()
        finally:
            if hasattr(self, 'shadow_frame') and self.shadow_frame.winfo_exists():
                self.shadow_frame.destroy()
    def _on_enter(self, _): self._set_bg(COL_CARD_HOVER)
    def _on_leave(self, _): self._set_bg(COL_CARD)
    def _set_bg(self, c):
        self.configure(bg=c)
        for ch in self.winfo_children():
            try: ch.configure(bg=c)
            except Exception: pass

class CardTitle(tk.Frame):
    def __init__(self, parent, text, **kwargs):
        super().__init__(parent, bg=COL_CARD, **kwargs)
        tk.Label(self, text=text, bg=COL_CARD, fg=COL_ACCENT,
                 font=("DejaVu Sans", FS_CARD_TITLE, "bold"),
                 anchor="w").pack(side="top", anchor="w")

class BigButton(tk.Button):
    def __init__(self, parent, text, command, bg=None, fg=COL_TEXT, small=False, micro=False, **kwargs):
        super().__init__(parent, text=text, command=command, **kwargs)
        bg = bg or COL_ACCENT
        fs = FS_BTN_MICRO if micro else (FS_BTN_SMALL if small else FS_BTN)
        self.configure(bg=bg, fg=fg, activebackground=COL_ACCENT_LIGHT, activeforeground=COL_TEXT,
                       font=("DejaVu Sans Mono", fs, "bold"), bd=0,
                       padx=get_scaled_size(16), pady=get_scaled_size(8), relief="flat",
                       highlightthickness=0, cursor="hand2")
        self.default_bg = bg
        self.bind("<Enter>", lambda e: self.configure(bg=COL_ACCENT_LIGHT))
        self.bind("<Leave>", lambda e: self.configure(bg=self.default_bg))

class GhostButton(tk.Button):
    def __init__(self, parent, text, command, small=False, micro=False, **kwargs):
        super().__init__(parent, text=text, command=command, **kwargs)
        fs = FS_BTN_MICRO if micro else (FS_BTN_SMALL if small else FS_BTN)
        self.configure(bg=COL_CARD, fg=COL_ACCENT, activebackground=COL_CARD_HOVER,
                       activeforeground=COL_ACCENT_LIGHT, font=("DejaVu Sans Mono", fs, "bold"),
                       bd=1, relief="solid", highlightthickness=0, highlightbackground=COL_ACCENT,
                       cursor="hand2", padx=get_scaled_size(12), pady=get_scaled_size(6))

class WeightLabel(tk.Label):
    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        self.configure(text="0 g", font=("DejaVu Sans Mono", FS_HUGE, "bold"),
                       bg=COL_CARD, fg=COL_TEXT, anchor="center")
        self.last_value = "0 g"; self.animation_after = None
    def config(self, **kwargs):
        if 'text' in kwargs:
            new_text = kwargs['text']
            if new_text != self.last_value:
                self.configure(fg=COL_ACCENT_LIGHT)
                if self.animation_after: self.after_cancel(self.animation_after)
                self.animation_after = self.after(200, lambda: self.configure(fg=COL_TEXT))
                self.last_value = new_text
        super().config(**kwargs)

class Toast(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent, bg=COL_CARD, bd=0, highlightthickness=1, highlightbackground=COL_BORDER)
        pad = get_scaled_size(20)
        self._lbl = tk.Label(self, text="", bg=COL_CARD, fg=COL_TEXT, font=("DejaVu Sans", FS_TEXT),
                             padx=pad, pady=get_scaled_size(12))
        self._lbl.pack()
        self._after_id = None
        self.place_forget()
    def show(self, text: str, ms: int = 1500, color=None):
        if self._after_id: self.after_cancel(self._after_id); self._after_id = None
        if color: self._lbl.configure(fg=color)
        else: self._lbl.configure(fg=COL_TEXT)
        self._lbl.configure(text=text)
        self.update_idletasks()
        w = self.master.winfo_width()
        x = max(20, w - 20) if w > 100 else 300
        self.place(x=x, y=20, anchor="ne")
        self.lift()
        self._after_id = self.after(ms, self.hide)
    def hide(self):
        if self._after_id: self.after_cancel(self._after_id); self._after_id = None
        self.place_forget()

class ScrollFrame(tk.Frame):
    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        self.canvas = tk.Canvas(self, bg=kwargs.get('bg', COL_BG), highlightthickness=0)
        sb = tk.Scrollbar(self, orient="vertical", command=self.canvas.yview, width=get_scaled_size(16))
        self.scrollable_frame = tk.Frame(self.canvas, bg=kwargs.get('bg', COL_BG))
        self.scrollable_frame.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind('<Configure>', self._on_canvas_configure)
        self.canvas_window = self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=sb.set)
        self.canvas.pack(side="left", fill="both", expand=True); sb.pack(side="right", fill="y")
        self.body = self.scrollable_frame
        self._bind_mousewheel()
    def _on_canvas_configure(self, event):
        self.canvas.itemconfig(self.canvas_window, width=event.width)
    def _bind_mousewheel(self):
        for w in (self, self.canvas):
            w.bind("<Button-4>", self._on_mousewheel); w.bind("<Button-5>", self._on_mousewheel); w.bind("<MouseWheel>", self._on_mousewheel)
    def _on_mousewheel(self, event):
        try:
            if getattr(event, "num", None) == 4: self.canvas.yview_scroll(-1, "units")
            elif getattr(event, "num", None) == 5: self.canvas.yview_scroll(1, "units")
            elif hasattr(event, 'delta') and event.delta: self.canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        except Exception: pass

class StatusIndicator(tk.Canvas):
    def __init__(self, parent, size=12):
        s = get_scaled_size(size)
        super().__init__(parent, width=s, height=s, bg=COL_CARD, highlightthickness=0)
        self.size = s; self.status = "inactive"; self.pulse_after = None; self._draw_indicator()
    def _draw_indicator(self):
        self.delete("all")
        c = self.size // 2; r = (self.size // 2) - 2
        color = {"active": COL_SUCCESS, "warning": COL_WARN, "inactive": COL_MUTED}.get(self.status, COL_MUTED)
        self.create_oval(1, 1, self.size-1, self.size-1, outline=COL_BORDER, width=1, tags="border")
        self.create_oval(c-r, c-r, c+r, c+r, fill=color, outline=color, tags="indicator")
    def set_status(self, status: str):
        self.status = status
        if self.pulse_after: self.after_cancel(self.pulse_after); self.pulse_after = None
        self._draw_indicator()
        if status == "active" and not self.pulse_after: self._pulse()
    def _pulse(self):
        if self.status != "active": self.pulse_after = None; return
        self.itemconfig("indicator", fill=COL_ACCENT_LIGHT)
        self.after(200, lambda: self.itemconfig("indicator", fill=COL_SUCCESS))
        self.pulse_after = self.after(1000, self._pulse)

# ========= TECLADO NUMÉRICO POPUP =========

class NumericKeypad(tk.Frame):
    """Teclado reutilizable (sin ventana)."""
    def __init__(self, parent, textvar: tk.StringVar, on_ok=None, on_clear=None, allow_dot=True, variant="small"):
        super().__init__(parent, bg=COL_CARD)
        self.var = textvar; self.on_ok = on_ok; self.on_clear = on_clear
        self.allow_dot = allow_dot; self.variant = variant
        f_entry = ("DejaVu Sans Mono", FS_ENTRY_SMALL if variant=="small" else FS_ENTRY)
        f_btn = ("DejaVu Sans Mono", FS_BTN_SMALL if variant=="small" else FS_BTN, "bold")
        pad = (6,6); ipady = 6
        # display
        disp = tk.Entry(self, textvariable=self.var, font=f_entry, bg=COL_CARD, fg=COL_TEXT,
                        highlightbackground=COL_BORDER, highlightthickness=1,
                        insertbackground=COL_ACCENT, relief="flat", justify="right")
        disp.grid(row=0, column=0, columnspan=3, sticky="ew", padx=pad, pady=(pad[1], pad[1]//2))
        for i in range(3): self.columnconfigure(i, weight=1, uniform="keys")
        layout = [[("7",1,0),("8",1,1),("9",1,2)],
                  [("4",2,0),("5",2,1),("6",2,2)],
                  [("1",3,0),("2",3,1),("3",3,2)]]
        for row in layout:
            for txt, r, c in row:
                tk.Button(self, text=txt, command=lambda t=txt:self._add(t),
                          font=f_btn, bg=COL_CARD, fg=COL_TEXT,
                          activebackground=COL_CARD_HOVER, activeforeground=COL_ACCENT_LIGHT,
                          bd=1, relief="flat", highlightthickness=0).grid(row=r, column=c, sticky="nsew", padx=pad, pady=pad, ipady=ipady)
                self.rowconfigure(r, weight=1)
        bottom = 4
        b0 = tk.Button(self, text="0", command=lambda:self._add("0"), font=f_btn, bg=COL_CARD, fg=COL_TEXT,
                       activebackground=COL_CARD_HOVER, activeforeground=COL_ACCENT_LIGHT, bd=1, relief="flat", highlightthickness=0)
        if self.allow_dot:
            b0.grid(row=bottom, column=0, sticky="nsew", padx=pad, pady=pad, ipady=ipady)
            tk.Button(self, text=".", command=lambda:self._add("."), font=f_btn, bg=COL_CARD, fg=COL_TEXT,
                      activebackground=COL_CARD_HOVER, activeforeground=COL_ACCENT_LIGHT, bd=1, relief="flat", highlightthickness=0
                     ).grid(row=bottom, column=1, sticky="nsew", padx=pad, pady=pad, ipady=ipady)
        else:
            b0.grid(row=bottom, column=0, columnspan=2, sticky="nsew", padx=pad, pady=pad, ipady=ipady)
        tk.Button(self, text="OK", command=self._ok, font=f_btn, bg=COL_ACCENT, fg=COL_TEXT,
                  activebackground=COL_ACCENT_LIGHT, activeforeground=COL_TEXT, bd=0, relief="flat", highlightthickness=0
                 ).grid(row=bottom, column=2, sticky="nsew", padx=pad, pady=pad, ipady=ipady)
        # fila de acciones
        actions = tk.Frame(self, bg=COL_CARD); actions.grid(row=5, column=0, columnspan=3, sticky="ew", padx=pad, pady=(0,pad[1]))
        tk.Button(actions, text="⌫", command=self._back, font=f_btn, bg=COL_CARD, fg=COL_WARN, bd=1, relief="flat"
                 ).pack(side="left")
        tk.Button(actions, text="CLR", command=self._clear, font=f_btn, bg=COL_CARD, fg=COL_WARN, bd=1, relief="flat"
                 ).pack(side="left", padx=(get_scaled_size(8),0))
    def _add(self, ch): self.var.set((self.var.get() or "") + ch)
    def _back(self):
        s = self.var.get() or ""
        if s: self.var.set(s[:-1])
    def _clear(self): self.var.set(""); 
    def _ok(self):
        if self.on_ok: self.on_ok()

class KeypadPopup(tk.Toplevel):
    """Ventana popup con teclado y display; devuelve valor por callback."""
    def __init__(self, parent, title="Introducir valor", initial="", allow_dot=True, on_accept=None, on_cancel=None):
        super().__init__(parent)
        self.configure(bg=COL_BG); self.transient(parent); self.grab_set(); self.title(title)
        self.resizable(False, False)
        try: self.attributes("-topmost", True)
        except Exception: pass
        # centro aproximado
        self.update_idletasks()
        px = parent.winfo_rootx() + parent.winfo_width()//2 - 180
        py = parent.winfo_rooty() + parent.winfo_height()//2 - 160
        self.geometry(f"+{max(0,px)}+{max(0,py)}")
        # contenido
        card = Card(self, min_width=360, min_height=260); card.pack(fill="both", expand=True, padx=10, pady=10)
        tk.Label(card, text=title, bg=COL_CARD, fg=COL_ACCENT, font=("DejaVu Sans", FS_CARD_TITLE, "bold")).pack(anchor="w")
        self._var = tk.StringVar(value=str(initial) if initial is not None else "")
        pad = NumericKeypad(card, self._var, on_ok=self._accept, allow_dot=allow_dot, variant="small")
        pad.pack(fill="both", expand=True, pady=(8,0))
        row = tk.Frame(card, bg=COL_CARD); row.pack(fill="x", pady=(8,0))
        GhostButton(row, text="Cancelar", command=self._cancel, micro=True).pack(side="left")
        BigButton(row, text="Aceptar", command=self._accept, micro=True).pack(side="right")
        self._on_accept = on_accept; self._on_cancel = on_cancel
        self.bind("<Escape>", lambda e:self._cancel())
        self.protocol("WM_DELETE_WINDOW", self._cancel)
    def _accept(self):
        if self._on_accept: self._on_accept(self._var.get())
        self.destroy()
    def _cancel(self):
        if self._on_cancel: self._on_cancel()
        self.destroy()

def bind_numeric_popup(entry: tk.Entry, allow_dot=True):
    """Convierte un Entry en disparador de teclado popup. Requiere que tenga textvariable."""
    var = entry.cget("textvariable")
    if not var:
        tv = tk.StringVar(value="")
        entry.configure(textvariable=tv)
        var = str(tv)
    def _open(_e=None):
        entry.icursor("end")
        def _set(val):
            entry_var = entry.getvar(var)
            entry.setvar(var, val)
        KeypadPopup(entry.winfo_toplevel(), title="Introducir valor", initial=entry.get(), allow_dot=allow_dot, on_accept=_set)
    entry.configure(state="readonly")
    entry.bind("<Button-1>", _open)
    entry.bind("<FocusIn>", _open)
