# -*- coding: utf-8 -*-
"""
Pantallas de la interfaz (Tkinter) para la báscula.
Diseño sobrio, escalado automático y componentes reutilizables.
"""

from __future__ import annotations
import os
import math
import tkinter as tk
from tkinter import ttk, messagebox   # <= IMPORT FIJO (antes faltaba messagebox)
from typing import Callable, Optional

# Paleta y tipografías
COL_BG    = "#0b132b"
COL_CARD  = "#1a1f2e"
COL_ACC   = "#2d5bff"
COL_ACC_2 = "#00d4ff"
COL_TEXT  = "#e6eefc"
COL_MUTE  = "#8ca0c3"
COL_WARN  = "#ffb020"
COL_ERR   = "#ff5c5c"
COL_GOOD  = "#28c76f"
FS_TITLE  = 28
FS_SUB    = 20
FS_TEXT   = 16
FS_SMALL  = 13

# ==========================================================
# Escalado responsivo (base 1024x600)
# ==========================================================
_BASE_W, _BASE_H = 1024, 600
_scale_w, _scale_h, _scale = 1.0, 1.0, 1.0

def set_scale_from_root(root: tk.Tk, target=(1024, 600)) -> None:
    global _scale_w, _scale_h, _scale, _BASE_W, _BASE_H
    sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
    bw, bh = target
    _BASE_W, _BASE_H = bw, bh
    _scale_w = max(0.1, sw / bw)
    _scale_h = max(0.1, sh / bh)
    _scale = min(_scale_w, _scale_h)

def get_scaled_size(v: int) -> int:
    return max(1, int(round(v * _scale)))

def auto_apply_scaling(root: tk.Tk, target=(1024, 600)) -> None:
    set_scale_from_root(root, target)
    try:
        root.tk.call('tk', 'scaling', _scale)
    except Exception:
        pass

# ==========================================================
# Utilidades UI
# ==========================================================
def spacer(parent: tk.Widget, h: int=10, bg: Optional[str]=None) -> tk.Frame:
    f = tk.Frame(parent, height=get_scaled_size(h), bg=bg or parent.cget("bg"))
    f.pack(fill="x")
    return f

def hspacer(parent: tk.Widget, w: int=10, bg: Optional[str]=None) -> tk.Frame:
    f = tk.Frame(parent, width=get_scaled_size(w), bg=bg or parent.cget("bg"))
    f.pack(side="left")
    return f

def mk_title(parent: tk.Widget, text: str) -> tk.Label:
    return tk.Label(parent, text=text, bg=parent.cget("bg"), fg=COL_TEXT,
                    font=("DejaVu Sans", get_scaled_size(FS_TITLE), "bold"))

def mk_subtitle(parent: tk.Widget, text: str) -> tk.Label:
    return tk.Label(parent, text=text, bg=parent.cget("bg"), fg=COL_MUTE,
                    font=("DejaVu Sans", get_scaled_size(FS_SUB)))

def mk_btn(parent: tk.Widget, text: str, cmd: Callable, kind: str="primary") -> tk.Button:
    bg = COL_ACC if kind=="primary" else COL_CARD
    fg = "#ffffff" if kind=="primary" else COL_TEXT
    active = COL_ACC_2 if kind=="primary" else "#263046"
    return tk.Button(
        parent, text=text, command=cmd,
        bg=bg, fg=fg, activebackground=active, activeforeground=fg,
        bd=0, highlightthickness=0, relief="flat", cursor="hand2",
        font=("DejaVu Sans", get_scaled_size(FS_TEXT), "bold"),
        padx=get_scaled_size(14), pady=get_scaled_size(8)
    )

def mk_label(parent: tk.Widget, text: str, color: str=COL_TEXT, size: int=FS_TEXT, bold=False) -> tk.Label:
    return tk.Label(parent, text=text, bg=parent.cget("bg"), fg=color,
                    font=("DejaVu Sans", get_scaled_size(size), "bold" if bold else "normal"))

def mk_entry(parent: tk.Widget, textvar: tk.StringVar, width_chars: int=8, justify="center") -> tk.Entry:
    e = tk.Entry(parent, textvariable=textvar, width=width_chars,
                 bg="#0e1628", fg=COL_TEXT, insertbackground=COL_TEXT,
                 bd=0, highlightthickness=0, relief="flat",
                 font=("DejaVu Sans Mono", get_scaled_size(FS_TEXT)))
    e.configure(justify=justify)
    return e

# ==========================================================
# Teclados emergentes
# ==========================================================
class NumericKeypad(tk.Toplevel):
    def __init__(self, master: tk.Widget, initial: str, decimals: int,
                 on_accept: Callable[[str], None], title="Introducir valor"):
        super().__init__(master)
        self.withdraw()
        self.configure(bg=COL_CARD)
        self.overrideredirect(False)
        self.title(title)
        self.resizable(False, False)
        self.grab_set()
        self.transient(master.winfo_toplevel())

        self.on_accept = on_accept
        self.decimals = decimals

        frm = tk.Frame(self, bg=COL_CARD, bd=0)
        frm.pack(fill="both", expand=True, padx=get_scaled_size(8), pady=get_scaled_size(8))

        lbl = mk_subtitle(frm, title)
        lbl.pack(pady=(0, get_scaled_size(8)))

        self.var = tk.StringVar(value=initial or "")
        disp = mk_entry(frm, self.var, width_chars=12, justify="right")
        disp.pack(fill="x", pady=(0, get_scaled_size(8)))

        grid = tk.Frame(frm, bg=COL_CARD)
        grid.pack()

        keys = [
            ["7","8","9"],
            ["4","5","6"],
            ["1","2","3"],
            ["±","0","."] if decimals>0 else ["±","0","<"]
        ]
        for row in keys:
            rf = tk.Frame(grid, bg=COL_CARD); rf.pack()
            for k in row:
                tk.Button(
                    rf, text=k, command=lambda ch=k: self._press(ch),
                    bg="#263046", fg=COL_TEXT, activebackground="#31405c",
                    bd=0, highlightthickness=0, relief="flat",
                    font=("DejaVu Sans", get_scaled_size(20), "bold"),
                    width=get_scaled_size(3), height=get_scaled_size(1),
                    padx=get_scaled_size(16), pady=get_scaled_size(10)
                ).pack(side="left", padx=get_scaled_size(5), pady=get_scaled_size(5))

        ctrl = tk.Frame(frm, bg=COL_CARD); ctrl.pack(fill="x", pady=(get_scaled_size(6),0))
        mk_btn(ctrl, "← Borrar", self._back, kind="secondary").pack(side="left")
        hspacer(ctrl, 6)
        mk_btn(ctrl, "Limpiar", self._clear, kind="secondary").pack(side="left")
        mk_btn(ctrl, "Aceptar", self._ok, kind="primary").pack(side="right")
        hspacer(ctrl, 6)
        mk_btn(ctrl, "Cancelar", self._cancel, kind="secondary").pack(side="right")

        self.update_idletasks()
        self._center_on_master()
        self.deiconify()
        disp.focus_set()

        self.bind("<Escape>", lambda e: self._cancel())
        self.bind("<Return>", lambda e: self._ok())

    def _center_on_master(self):
        m = self.master.winfo_toplevel()
        mx, my = m.winfo_rootx(), m.winfo_rooty()
        mw, mh = m.winfo_width(), m.winfo_height()
        w, h = self.winfo_reqwidth(), self.winfo_reqheight()
        self.geometry(f"+{mx + (mw - w)//2}+{my + (mh - h)//2}")

    def _press(self, ch: str):
        s = self.var.get()
        if ch == "<":
            self._back(); return
        if ch == "±":
            self.var.set(s[1:] if s.startswith("-") else "-" + s); return
        if ch == ".":
            if self.decimals <= 0 or "." in s: return
        self.var.set((s or "") + ch)

    def _back(self):
        s = self.var.get()
        if s: self.var.set(s[:-1])

    def _clear(self): self.var.set("")
    def _ok(self):
        self.grab_release()
        try: self.on_accept(self.var.get())
        finally: self.destroy()
    def _cancel(self):
        self.grab_release(); self.destroy()

class TextKeypad(tk.Toplevel):
    def __init__(self, master: tk.Widget, initial: str,
                 on_accept: Callable[[str], None], title="Introducir texto"):
        super().__init__(master)
        self.withdraw()
        self.configure(bg=COL_CARD)
        self.overrideredirect(False)
        self.title(title)
        self.resizable(False, False)
        self.grab_set()
        self.transient(master.winfo_toplevel())
        self.on_accept = on_accept

        frm = tk.Frame(self, bg=COL_CARD); frm.pack(fill="both", expand=True, padx=get_scaled_size(10), pady=get_scaled_size(10))
        mk_subtitle(frm, title).pack(pady=(0, get_scaled_size(10)))

        self.var = tk.StringVar(value=initial or "")
        disp = mk_entry(frm, self.var, width_chars=22, justify="left")
        disp.pack(fill="x", pady=(0, get_scaled_size(12)))

        grid = tk.Frame(frm, bg=COL_CARD); grid.pack()
        layout = [
            list("1234567890"),
            list("qwertyuiop"),
            list("asdfghjkl"),
            list("zxcvbnm.-_"),
            ["ESPACIO"]
        ]
        for row in layout:
            rf = tk.Frame(grid, bg=COL_CARD); rf.pack()
            for ch in row:
                if ch == "ESPACIO":
                    tk.Button(
                        rf, text="Espacio", command=lambda: self._put(" "),
                        bg="#263046", fg=COL_TEXT, activebackground="#31405c",
                        bd=0, highlightthickness=0, relief="flat",
                        font=("DejaVu Sans", get_scaled_size(16), "bold"),
                        padx=get_scaled_size(30), pady=get_scaled_size(10)
                    ).pack(side="left", padx=get_scaled_size(5), pady=get_scaled_size(5))
                else:
                    tk.Button(
                        rf, text=ch, command=lambda c=ch: self._put(c),
                        bg="#263046", fg=COL_TEXT, activebackground="#31405c",
                        bd=0, highlightthickness=0, relief="flat",
                        font=("DejaVu Sans", get_scaled_size(16), "bold"),
                        width=get_scaled_size(2), padx=get_scaled_size(14), pady=get_scaled_size(8)
                    ).pack(side="left", padx=get_scaled_size(3), pady=get_scaled_size(3))

        ctrl = tk.Frame(frm, bg=COL_CARD); ctrl.pack(fill="x", pady=(get_scaled_size(8),0))
        mk_btn(ctrl, "← Borrar", self._back, kind="secondary").pack(side="left")
        hspacer(ctrl, 6)
        mk_btn(ctrl, "Limpiar", self._clear, kind="secondary").pack(side="left")
        mk_btn(ctrl, "Aceptar", self._ok, kind="primary").pack(side="right")
        hspacer(ctrl, 6)
        mk_btn(ctrl, "Cancelar", self._cancel, kind="secondary").pack(side="right")

        self.update_idletasks(); self._center_on_master(); self.deiconify(); disp.focus_set()
        self.bind("<Escape>", lambda e: self._cancel())
        self.bind("<Return>", lambda e: self._ok())

    def _center_on_master(self):
        m = self.master.winfo_toplevel()
        mx, my = m.winfo_rootx(), m.winfo_rooty()
        mw, mh = m.winfo_width(), m.winfo_height()
        w, h = self.winfo_reqwidth(), self.winfo_reqheight()
        self.geometry(f"+{mx + (mw - w)//2}+{my + (mh - h)//2}")

    def _put(self, ch: str): self.var.set(self.var.get() + ch)
    def _back(self):
        s = self.var.get()
        if s: self.var.set(s[:-1])
    def _clear(self): self.var.set("")
    def _ok(self):
        self.grab_release()
        try: self.on_accept(self.var.get())
        finally: self.destroy()
    def _cancel(self):
        self.grab_release(); self.destroy()

# ==========================================================
# HomeScreen (distribución intacta)
# ==========================================================
class HomeScreen(tk.Frame):
    def __init__(self, master: tk.Widget, app, on_open_settings_menu: Optional[Callable]=None):
        super().__init__(master, bg=COL_BG)
        self.app = app
        self.on_open_settings_menu = on_open_settings_menu or (lambda: None)

        header = tk.Frame(self, bg=COL_BG)
        header.pack(fill="x", padx=get_scaled_size(16), pady=get_scaled_size(10))
        mk_title(header, "Báscula").pack(side="left")
        mk_btn(header, "⚙ Ajustes", self.on_open_settings_menu, kind="secondary").pack(side="right")

        body = tk.Frame(self, bg=COL_BG)
        body.pack(fill="both", expand=True, padx=get_scaled_size(16), pady=get_scaled_size(12))

        left = tk.Frame(body, bg=COL_BG);  left.pack(side="left", fill="both", expand=True)
        right = tk.Frame(body, bg=COL_BG); right.pack(side="left", fill="both", expand=True)

        card_weight = tk.Frame(left, bg=COL_CARD); card_weight.pack(fill="x", pady=get_scaled_size(10))
        mk_subtitle(card_weight, "Peso actual").pack(anchor="w", padx=get_scaled_size(12), pady=get_scaled_size(6))
        self.lbl_weight = mk_label(card_weight, "— g", size=36, bold=True)
        self.lbl_weight.pack(anchor="w", padx=get_scaled_size(12), pady=get_scaled_size(6))

        card_totals = tk.Frame(left, bg=COL_CARD); card_totals.pack(fill="x", pady=get_scaled_size(10))
        mk_subtitle(card_totals, "Totales").pack(anchor="w", padx=get_scaled_size(12), pady=get_scaled_size(6))
        row = tk.Frame(card_totals, bg=COL_CARD); row.pack(fill="x", padx=get_scaled_size(12), pady=get_scaled_size(6))
        self.lbl_kcal = mk_label(row, "Kcal: —", size=FS_TEXT); self.lbl_kcal.pack(side="left")
        hspacer(row, 16)
        self.lbl_carb = mk_label(row, "Carbohidratos (g): —", size=FS_TEXT); self.lbl_carb.pack(side="left")
        hspacer(row, 16)
        self.lbl_prot = mk_label(row, "Proteínas (g): —", size=FS_TEXT); self.lbl_prot.pack(side="left")
        hspacer(row, 16)
        self.lbl_fat  = mk_label(row, "Grasas (g): —", size=FS_TEXT); self.lbl_fat.pack(side="left")

        card_list = tk.Frame(right, bg=COL_CARD); card_list.pack(fill="both", expand=True, pady=get_scaled_size(10))
        top_list = tk.Frame(card_list, bg=COL_CARD); top_list.pack(fill="x", padx=get_scaled_size(12), pady=get_scaled_size(6))
        mk_subtitle(top_list, "Alimentos").pack(side="left")
        mk_btn(top_list, "🗑 Borrar seleccionado", lambda: None, kind="secondary").pack(side="right")

        self.listbox = tk.Listbox(
            card_list, bg="#0e1628", fg=COL_TEXT,
            font=("DejaVu Sans", get_scaled_size(FS_TEXT)),
            selectbackground="#2d5bff", selectforeground="#ffffff",
            borderwidth=0, highlightthickness=0, activestyle="dotbox"
        )
        self.listbox.pack(fill="both", expand=True, padx=get_scaled_size(12), pady=get_scaled_size(6))

        footer = tk.Frame(self, bg=COL_BG); footer.pack(fill="x", padx=get_scaled_size(16), pady=get_scaled_size(10))
        mk_btn(footer, "Añadir alimento", lambda: None, kind="primary").pack(side="left")
        hspacer(footer, 8)
        mk_btn(footer, "Plato único", lambda: None, kind="secondary").pack(side="left")

# ==========================================================
# Ajustes / Calibración
# ==========================================================
class SettingsScreen(tk.Frame):
    def __init__(self, master: tk.Widget, app):
        super().__init__(master, bg=COL_BG)
        self.app = app

        header = tk.Frame(self, bg=COL_BG)
        header.pack(fill="x", padx=get_scaled_size(16), pady=get_scaled_size(10))
        mk_title(header, "Ajustes de Calibración").pack(side="left")
        mk_btn(header, "← Volver", lambda: app.show_screen("home"), kind="secondary").pack(side="right")

        calib = tk.Frame(self, bg=COL_CARD)
        calib.pack(fill="x", padx=get_scaled_size(16), pady=get_scaled_size(12))
        mk_subtitle(calib, "Lectura en vivo").pack(anchor="w", padx=get_scaled_size(12), pady=get_scaled_size(6))

        live_frame = tk.Frame(calib, bg=COL_CARD); live_frame.pack(fill="x", padx=get_scaled_size(10), pady=get_scaled_size(4))
        tk.Label(live_frame, text="●", bg=COL_CARD, fg=COL_GOOD,
                 font=("DejaVu Sans", get_scaled_size(16), "bold")).pack(side="left", padx=(get_scaled_size(10), get_scaled_size(8)))
        self.lbl_live = tk.Label(
            live_frame, text="Lectura actual: —",
            bg="#1a1f2e", fg=COL_TEXT,
            font=("DejaVu Sans", get_scaled_size(FS_TEXT))
        )
        self.lbl_live.pack(side="left", pady=get_scaled_size(6))

        row_vals = tk.Frame(calib, bg=COL_CARD); row_vals.pack(fill="x", pady=(0, get_scaled_size(6)), padx=get_scaled_size(10))
        mk_label(row_vals, "Unidad:", color=COL_MUTE, size=FS_TEXT).pack(side="left")
        self._unit_var = tk.StringVar(value=self.app.get_cfg().get("unit","g"))
        ttk.Combobox(row_vals, textvariable=self._unit_var, values=["g","kg","lb"], state="readonly").pack(side="left", padx=get_scaled_size(8))
        mk_btn(row_vals, "Guardar", self._save_unit, kind="secondary").pack(side="left", padx=get_scaled_size(8))

        self.after(200, self._tick_live)

    def _tick_live(self):
    """Refresco de la lectura en vivo sin ocultar 0.000 y sin variables no inicializadas."""
    try:
        v = None
        reader = self.app.get_reader()
        if reader is not None:
            try:
                # Usa la fuente “de verdad” de la báscula
                v = reader.get_latest()
            except Exception:
                v = None

        # Muestra 0.000 correctamente y evita usar v sin asignar
        if v is not None:
            try:
                self.lbl_live.config(text=f"{float(v):.3f}")
            except Exception:
                # Si no fuese convertible a float, muéstralo en bruto
                self.lbl_live.config(text=str(v))
    finally:
        self.after(120, self._tick_live)


    def _save_unit(self):
        self.app.get_cfg()["unit"] = self._unit_var.get()
        self.app.save_cfg()

class CalibScreen(SettingsScreen):
    pass

# ==========================================================
# Menú Ajustes
# ==========================================================
class SettingsMenuScreen(tk.Frame):
    def __init__(self, master: tk.Widget, app):
        super().__init__(master, bg=COL_BG)
        self.app = app

        header = tk.Frame(self, bg=COL_BG); header.pack(fill="x", padx=get_scaled_size(16), pady=get_scaled_size(10))
        mk_title(header, "Ajustes").pack(side="left")
        mk_btn(header, "← Volver", lambda: app.show_screen("home"), kind="secondary").pack(side="right")

        body = tk.Frame(self, bg=COL_BG); body.pack(fill="both", expand=True, padx=get_scaled_size(16), pady=get_scaled_size(12))
        nav = tk.Frame(body, bg=COL_BG); nav.pack()

        mk_btn(nav, "Calibración", lambda: app.show_screen("calib"), kind="primary").pack(fill="x", pady=get_scaled_size(6))
        mk_btn(nav, "Wi-Fi",       lambda: app.show_screen("wifi"),  kind="secondary").pack(fill="x", pady=get_scaled_size(6))
        mk_btn(nav, "API Key",     lambda: app.show_screen("apikey"),kind="secondary").pack(fill="x", pady=get_scaled_size(6))

# ==========================================================
# Wi-Fi / API Key
# ==========================================================
class WifiScreen(tk.Frame):
    def __init__(self, master: tk.Widget, app):
        super().__init__(master, bg=COL_BG)
        self.app = app

        header = tk.Frame(self, bg=COL_BG)
        header.pack(fill="x", padx=get_scaled_size(16), pady=get_scaled_size(10))
        mk_title(header, "Wi-Fi").pack(side="left")
        mk_btn(header, "← Volver", lambda: app.show_screen("settings_menu"), kind="secondary").pack(side="right")

        body = tk.Frame(self, bg=COL_CARD)
        body.pack(fill="both", expand=True, padx=get_scaled_size(16), pady=get_scaled_size(12))

        mk_subtitle(body, "Redes disponibles").pack(anchor="w", padx=get_scaled_size(12), pady=get_scaled_size(6))
        self.lst = tk.Listbox(
            body, bg="#0e1628", fg=COL_TEXT,
            font=("DejaVu Sans", get_scaled_size(FS_TEXT)),
            selectbackground="#2d5bff", selectforeground="#ffffff",
            borderwidth=0, highlightthickness=0, activestyle="dotbox"
        )
        self.lst.pack(fill="both", expand=True, padx=get_scaled_size(12), pady=get_scaled_size(6))

        row = tk.Frame(body, bg=COL_CARD); row.pack(fill="x", padx=get_scaled_size(12), pady=get_scaled_size(6))
        mk_btn(row, "🔎 Buscar", self._scan, kind="secondary").pack(side="left")
        hspacer(row, 8)
        mk_btn(row, "Conectar", self._connect, kind="primary").pack(side="left")

        fields = tk.Frame(body, bg=COL_CARD); fields.pack(fill="x", padx=get_scaled_size(12), pady=get_scaled_size(6))
        tk.Label(fields, text="SSID:", bg=COL_CARD, fg=COL_TEXT, font=("DejaVu Sans", get_scaled_size(FS_TEXT))).pack(side="left")
        self.ssid = tk.StringVar()
        mk_entry(fields, self.ssid, width_chars=18, justify="left").pack(side="left", padx=get_scaled_size(6))
        mk_btn(fields, "⌨", lambda: TextKeypad(self, self.ssid.get(), lambda v: self.ssid.set(v), "SSID"), kind="secondary").pack(side="left")

        hspacer(fields, 12)
        tk.Label(fields, text="Clave:", bg=COL_CARD, fg=COL_TEXT, font=("DejaVu Sans", get_scaled_size(FS_TEXT))).pack(side="left")
        self.psk = tk.StringVar()
        mk_entry(fields, self.psk, width_chars=18, justify="left").pack(side="left", padx=get_scaled_size(6))
        mk_btn(fields, "⌨", lambda: TextKeypad(self, self.psk.get(), lambda v: self.psk.set(v), "Clave Wi-Fi"), kind="secondary").pack(side="left")

    def _scan(self):
        try:
            nets = self.app.wifi_scan()
        except Exception:
            nets = []
        self.lst.delete(0, "end")
        for n in nets:
            self.lst.insert("end", n)

    def _connect(self):
        ssid = self.ssid.get().strip()
        psk  = self.psk.get().strip()
        try:
            ok = self.app.wifi_connect(ssid, psk)
        except Exception:
            ok = False
        messagebox.showinfo("Conectado" if ok else "Fallo", f"A la red {ssid}" if ok else "No fue posible conectar")

class ApiKeyScreen(tk.Frame):
    def __init__(self, master: tk.Widget, app):
        super().__init__(master, bg=COL_BG)
        self.app = app

        header = tk.Frame(self, bg=COL_BG)
        header.pack(fill="x", padx=get_scaled_size(16), pady=get_scaled_size(10))
        mk_title(header, "API Key").pack(side="left")
        mk_btn(header, "← Volver", lambda: app.show_screen("settings_menu"), kind="secondary").pack(side="right")

        body = tk.Frame(self, bg=COL_CARD)
        body.pack(fill="both", expand=True, padx=get_scaled_size(16), pady=get_scaled_size(12))

        mk_subtitle(body, "Clave de OpenAI").pack(anchor="w", padx=get_scaled_size(12), pady=get_scaled_size(6))
        row = tk.Frame(body, bg=COL_CARD); row.pack(fill="x", padx=get_scaled_size(12), pady=get_scaled_size(6))

        tk.Label(row, text="API Key:", bg=COL_CARD, fg=COL_TEXT, font=("DejaVu Sans", get_scaled_size(FS_TEXT))).pack(side="left")
        self.api_var = tk.StringVar(value=self.app.get_cfg().get("openai_api_key",""))
        mk_entry(row, self.api_var, width_chars=26, justify="left").pack(side="left", padx=get_scaled_size(6))
        mk_btn(row, "⌨", lambda: TextKeypad(self, self.api_var.get(), lambda v: (self.api_var.set(v), self._save()), "API Key"), kind="secondary").pack(side="left")

        spacer(body, 8, bg=COL_CARD)
        mk_btn(body, "Guardar", self._save, kind="primary").pack(anchor="e", padx=get_scaled_size(12), pady=get_scaled_size(6))

    def _save(self):
        try:
            self.app.get_cfg()["openai_api_key"] = self.api_var.get().strip()
            self.app.save_cfg()
            messagebox.showinfo("OK", "API Key guardada")
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo guardar: {e}")

__all__ = [
    "HomeScreen",
    "SettingsMenuScreen",
    "SettingsScreen",
    "CalibScreen",
    "WifiScreen",
    "ApiKeyScreen",
    "NumericKeypad",
    "TextKeypad",
    "auto_apply_scaling",
    "get_scaled_size",
]
