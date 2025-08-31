# -*- coding: utf-8 -*-
# bascula/ui/widgets.py - MODIFICADO: Teclados mejorados con botón OK, fila de símbolos e icono Shift.
import tkinter as tk

# Paleta
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

# Tamaños
FS_HUGE = 80
FS_TITLE = 18
FS_CARD_TITLE = 15
FS_TEXT = 13
FS_BTN = 20
FS_BTN_SMALL = 18
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
        raw = min(sw/target[0], sh/target[1])
        SCALE_FACTOR = 1.5 if raw > 1.5 else (0.8 if raw < 0.8 else raw)
        if abs(SCALE_FACTOR - 1.0) > 0.1:
            FS_HUGE = max(40, int(80 * SCALE_FACTOR))
            FS_TITLE = max(14, int(18 * SCALE_FACTOR))
            FS_CARD_TITLE = max(12, int(15 * SCALE_FACTOR))
            FS_TEXT = max(10, int(13 * SCALE_FACTOR))
            FS_BTN = max(14, int(20 * SCALE_FACTOR))
            FS_BTN_SMALL = max(12, int(18 * SCALE_FACTOR))
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
        if min_width: self.shadow_frame.configure(width=get_scaled_size(min_width))
        if min_height: self.shadow_frame.configure(height=get_scaled_size(min_height))
        super().__init__(self.shadow_frame, bg=COL_CARD, bd=1, highlightbackground=COL_BORDER,
                         highlightthickness=1, relief="flat", **kwargs)
        pad = get_scaled_size(16)
        self.configure(padx=pad, pady=get_scaled_size(14))
        super().pack(padx=2, pady=2, fill="both", expand=True)
    def pack(self, *a, **k): return self.shadow_frame.pack(*a, **k)
    def grid(self, *a, **k): return self.shadow_frame.grid(*a, **k)
    def place(self, *a, **k): return self.shadow_frame.place(*a, **k)
    def destroy(self):
        try: super().destroy()
        finally:
            if hasattr(self, 'shadow_frame') and self.shadow_frame.winfo_exists():
                self.shadow_frame.destroy()

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
                       highlightthickness=0)
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
                       padx=get_scaled_size(12), pady=get_scaled_size(6))

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

# ========= TECLADO NUMÉRICO (POPUP) - MODIFICADO =========
class NumericKeypad(tk.Frame):
    def __init__(self, parent, textvar: tk.StringVar, on_ok=None, on_clear=None, allow_dot=True, variant="small"):
        super().__init__(parent, bg=COL_CARD)
        self.var = textvar; self.on_ok = on_ok; self.on_clear = on_clear
        self.allow_dot = allow_dot; self.variant = variant
        f_entry = ("DejaVu Sans Mono", FS_ENTRY if variant=="small" else FS_ENTRY)
        f_btn = ("DejaVu Sans Mono", FS_BTN if variant=="small" else FS_BTN, "bold")
        pad = (8,8); ipady = 12
        disp = tk.Entry(self, textvariable=self.var, font=f_entry, bg=COL_CARD, fg=COL_TEXT,
                        highlightbackground=COL_BORDER, highlightthickness=1, insertbackground=COL_ACCENT,
                        relief="flat", justify="right")
        disp.grid(row=0, column=0, columnspan=3, sticky="ew", padx=pad, pady=(pad[1], pad[1]//2))
        for i in range(3): self.columnconfigure(i, weight=1, uniform="keys")
        
        layout = [[("7",1,0),("8",1,1),("9",1,2)],
                  [("4",2,0),("5",2,1),("6",2,2)],
                  [("1",3,0),("2",3,1),("3",3,2)]]
        
        for r_idx, row_items in enumerate(layout, 1):
            self.rowconfigure(r_idx, weight=1)
            for txt, r, c in row_items:
                tk.Button(self, text=txt, command=lambda t=txt:self._add(t),
                          font=f_btn, bg=COL_CARD, fg=COL_TEXT,
                          activebackground=COL_CARD_HOVER, activeforeground=COL_ACCENT_LIGHT,
                          bd=1, relief="flat", highlightthickness=0).grid(row=r, column=c, sticky="nsew", padx=pad, pady=pad, ipady=ipady)

        # Fila inferior con 0, . y ⌫
        bottom_row = 4
        self.rowconfigure(bottom_row, weight=1)
        tk.Button(self, text="0", command=lambda:self._add("0"), font=f_btn, bg=COL_CARD, fg=COL_TEXT,
                  activebackground=COL_CARD_HOVER, activeforeground=COL_ACCENT_LIGHT, bd=1, relief="flat", highlightthickness=0
                 ).grid(row=bottom_row, column=0, columnspan=2, sticky="nsew", padx=pad, pady=pad, ipady=ipady)
        
        if self.allow_dot:
            tk.Button(self, text=".", command=lambda:self._add("."), font=f_btn, bg=COL_CARD, fg=COL_TEXT,
                      activebackground=COL_CARD_HOVER, activeforeground=COL_ACCENT_LIGHT, bd=1, relief="flat", highlightthickness=0
                     ).grid(row=bottom_row, column=2, sticky="nsew", padx=pad, pady=pad, ipady=ipady)

        # Fila de acciones con ⌫ y OK
        action_row = 5
        self.rowconfigure(action_row, weight=1)
        tk.Button(self, text="⌫", command=self._back, font=f_btn, bg=COL_CARD, fg=COL_WARN, bd=1, relief="flat"
                 ).grid(row=action_row, column=0, sticky="nsew", padx=pad, pady=pad, ipady=ipady)
        tk.Button(self, text="OK", command=self._ok, font=f_btn, bg=COL_ACCENT, fg=COL_TEXT,
                  activebackground=COL_ACCENT_LIGHT, activeforeground=COL_TEXT, bd=0, relief="flat", highlightthickness=0
                 ).grid(row=action_row, column=1, columnspan=2, sticky="nsew", padx=pad, pady=pad, ipady=ipady)
        
    def _add(self, ch): self.var.set((self.var.get() or "") + ch)
    def _back(self):
        s = self.var.get() or ""
        if s: self.var.set(s[:-1])
    def _clear(self): self.var.set("")
    def _ok(self):
        if self.on_ok: self.on_ok()

class KeypadPopup(tk.Toplevel):
    def __init__(self, parent, title="Introducir valor", initial="", allow_dot=True, on_accept=None, on_cancel=None):
        super().__init__(parent.winfo_toplevel())
        self.withdraw()
        self.configure(bg=COL_BG); self.transient(parent.winfo_toplevel()); self.grab_set(); self.title(title)
        self.resizable(False, False)
        try: self.attributes("-topmost", True)
        except Exception: pass
        card = Card(self, min_width=380, min_height=480); card.pack(fill="both", expand=True, padx=10, pady=10)
        tk.Label(card, text=title, bg=COL_CARD, fg=COL_ACCENT, font=("DejaVu Sans", FS_CARD_TITLE, "bold")).pack(anchor="w")
        self._var = tk.StringVar(value=str(initial) if initial is not None else "")
        # El botón OK ahora está dentro del keypad, por lo que el on_ok se pasa directamente
        pad = NumericKeypad(card, self._var, on_ok=self._accept, allow_dot=allow_dot, variant="small")
        pad.pack(fill="both", expand=True, pady=(8,0))
        # El botón de Aceptar/Cancelar de la ventana ya no es estrictamente necesario, pero lo mantenemos por consistencia
        row = tk.Frame(card, bg=COL_CARD); row.pack(fill="x", pady=(8,0))
        GhostButton(row, text="Cancelar", command=self._cancel, micro=True).pack(side="left")
        BigButton(row, text="Aceptar", command=self._accept, micro=True).pack(side="right")
        self._on_accept = on_accept; self._on_cancel = on_cancel
        self.bind("<Escape>", lambda e:self._cancel())
        self.protocol("WM_DELETE_WINDOW", self._cancel)
        self.update()
        tl = parent.winfo_toplevel()
        parent_w = max(300, tl.winfo_width())
        parent_h = max(200, tl.winfo_height())
        parent_x = tl.winfo_rootx(); parent_y = tl.winfo_rooty()
        w = max(380, self.winfo_width() or 380); h = max(480, self.winfo_height() or 480)
        px = parent_x + max(0, parent_w//2 - w//2)
        py = parent_y + max(0, parent_h//2 - h//2)
        self.geometry(f"{w}x{h}+{px}+{py}")
        self.minsize(w, h); self.deiconify()
    def _accept(self):
        try: self.grab_release()
        except Exception: pass
        if self._on_accept: self._on_accept(self._var.get())
        self.destroy()
    def _cancel(self):
        try: self.grab_release()
        except Exception: pass
        if self._on_cancel: self._on_cancel()
        self.destroy()

def _disable_typing(entry: tk.Entry):
    entry.bind("<Key>", lambda e: "break")
    entry.bind("<Control-Key>", lambda e: "break")

def bind_numeric_popup(entry: tk.Entry, allow_dot=True):
    varname = entry.cget("textvariable")
    if not varname:
        tv = tk.StringVar(value="")
        entry.configure(textvariable=tv)
        varname = str(tv)
    _disable_typing(entry)
    def _open(_e=None):
        def _set(val): entry.setvar(varname, val)
        KeypadPopup(entry, title="Introducir valor", initial=entry.get(), allow_dot=allow_dot, on_accept=_set)
    entry.bind("<ButtonRelease-1>", _open, add="+")

# ========= TECLADO TEXTO (POPUP) - MODIFICADO =========
class TextKeyboard(tk.Frame):
    def __init__(self, parent, textvar: tk.StringVar, on_ok=None, on_clear=None):
        super().__init__(parent, bg=COL_CARD)
        self.var = textvar; self.on_ok = on_ok; self.on_clear = on_clear; self.shift = False
        self.letter_buttons = []
        self.shift_button = None

        f_btn = ("DejaVu Sans Mono", FS_BTN_SMALL, "bold")
        pad = (5,5); ipady = 8 # Padding ajustado

        disp = tk.Entry(self, textvariable=self.var, font=("DejaVu Sans Mono", FS_ENTRY), bg=COL_CARD, fg=COL_TEXT,
                        highlightbackground=COL_BORDER, highlightthickness=1, insertbackground=COL_ACCENT,
                        relief="flat", justify="left")
        disp.grid(row=0, column=0, columnspan=11, sticky="ew", padx=pad, pady=(pad[1], 8))

        for i in range(11): self.columnconfigure(i, weight=1, uniform="tkeys")
        for i in range(6): self.rowconfigure(i + 1, weight=1)

        key_layout = [
            ['$', '%', '&', '*', '(', ')', '=', '/', '+', '-', '_'], # NUEVA FILA DE SÍMBOLOS
            list("1234567890") + ["⌫"],
            list("qwertyuiop"),
            list("asdfghjklñ"),
            ["↑"] + list("zxcvbnm") + [",", "."], # "Shift" cambiado por "↑"
            ["@", "SPACE", "OK"]
        ]
        
        for r_idx, row in enumerate(key_layout, 1):
            col_idx = 0
            for key in row:
                is_letter = len(key) == 1 and key.isalpha()
                cs = 1
                if key == "SPACE": cs = 7
                if key == "OK": cs = 3
                
                btn = tk.Button(self, text=key, font=f_btn,
                                activebackground=COL_CARD_HOVER, activeforeground=COL_ACCENT_LIGHT,
                                bd=1, relief="flat", highlightthickness=0)
                btn.grid(row=r_idx, column=col_idx, columnspan=cs, sticky="nsew", padx=pad, pady=pad, ipady=ipady)
                btn.configure(command=lambda k=key: self._press(k))
                
                col_idx += cs

                if key in ["↑", "⌫", "OK"]:
                    btn.configure(bg=COL_BORDER, fg=COL_ACCENT)
                    if key == "↑": self.shift_button = btn
                else:
                    btn.configure(bg=COL_CARD, fg=COL_TEXT)
                
                if is_letter:
                    self.letter_buttons.append(btn)
        
        self._update_keys_visuals()

    def _press(self, key):
        s = self.var.get() or ""
        if key == "↑": # Lógica actualizada para el icono
            self.shift = not self.shift
            self._update_keys_visuals()
            return
        if key == "⌫":
            if s: self.var.set(s[:-1])
            return
        if key == "OK":
            if self.on_ok: self.on_ok()
            return
        
        char_to_add = key
        if key == "SPACE":
            char_to_add = " "
        elif len(key) == 1 and key.isalpha():
            char_to_add = key.upper() if self.shift else key.lower()
        
        self.var.set(s + char_to_add)
        if self.shift and len(key) == 1 and key.isalpha():
            self.shift = False
            self._update_keys_visuals()

    def _update_keys_visuals(self):
        case_func = str.upper if self.shift else str.lower
        for btn in self.letter_buttons:
            current_text = btn.cget("text")
            btn.config(text=case_func(current_text))
        
        if self.shift_button:
            if self.shift:
                self.shift_button.config(bg=COL_ACCENT, fg=COL_BG)
            else:
                self.shift_button.config(bg=COL_BORDER, fg=COL_ACCENT)

class TextKeyPopup(tk.Toplevel):
    def __init__(self, parent, title="Introducir texto", initial="", on_accept=None, on_cancel=None):
        super().__init__(parent.winfo_toplevel())
        self.withdraw()
        self.configure(bg=COL_BG); self.transient(parent.winfo_toplevel()); self.grab_set(); self.title(title)
        self.resizable(False, False)
        try: self.attributes("-topmost", True)
        except Exception: pass
        # Aumentamos la altura mínima para la nueva fila de teclas
        card = Card(self, min_width=720, min_height=540); card.pack(fill="both", expand=True, padx=10, pady=10)
        tk.Label(card, text=title, bg=COL_CARD, fg=COL_ACCENT, font=("DejaVu Sans", FS_CARD_TITLE, "bold")).pack(anchor="w")
        self._var = tk.StringVar(value=str(initial) if initial is not None else "")
        kb = TextKeyboard(card, self._var, on_ok=lambda:self._accept()); kb.pack(fill="both", expand=True, pady=(8,0))
        self._on_accept = on_accept; self._on_cancel = on_cancel
        self.bind("<Escape>", lambda e:self._cancel())
        self.protocol("WM_DELETE_WINDOW", self._cancel)
        self.update()
        tl = parent.winfo_toplevel()
        parent_w = max(300, tl.winfo_width())
        parent_h = max(200, tl.winfo_height())
        parent_x = tl.winfo_rootx(); parent_y = tl.winfo_rooty()
        w = max(720, self.winfo_width() or 720); h = max(540, self.winfo_height() or 540)
        px = parent_x + max(0, parent_w//2 - w//2)
        py = parent_y + max(0, parent_h//2 - h//2)
        self.geometry(f"{w}x{h}+{px}+{py}")
        self.minsize(w, h); self.deiconify()
    def _accept(self):
        try: self.grab_release()
        except Exception: pass
        if self._on_accept: self._on_accept(self._var.get())
        self.destroy()
    def _cancel(self):
        try: self.grab_release()
        except Exception: pass
        if self._on_cancel: self._on_cancel()
        self.destroy()

def bind_text_popup(entry: tk.Entry):
    varname = entry.cget("textvariable")
    if not varname:
        tv = tk.StringVar(value="")
        entry.configure(textvariable=tv)
        varname = str(tv)
    _disable_typing(entry)
    def _open(_e=None):
        def _set(val): entry.setvar(varname, val)
        TextKeyPopup(entry, title="Introducir texto", initial=entry.get(), on_accept=_set)
    entry.bind("<ButtonRelease-1>", _open, add="+")
