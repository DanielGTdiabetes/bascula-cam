# -*- coding: utf-8 -*-
"""
Pantallas de la interfaz (Tkinter) para la báscula.
Diseño sobrio, escalado automático y componentes reutilizables.
"""

from __future__ import annotations
import os
import time
import math
import tkinter as tk
from tkinter import ttk
from typing import Callable, Optional, List, Dict, Any

# Paleta y tipografías (coherencia con el resto del proyecto)
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
# Escalado responsivo (se autoajusta a 1024x600 como base)
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
        root.tk.call('tk', 'scaling', _scale)  # escala fuentes en algunos sistemas
    except Exception:
        pass

# ==========================================================
# Pequeñas utilidades de UI
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
    b = tk.Button(parent, text=text, command=cmd,
                  bg=bg, fg=fg, activebackground=active, activeforeground=fg,
                  bd=0, highlightthickness=0,
                  font=("DejaVu Sans", get_scaled_size(FS_TEXT), "bold"),
                  padx=get_scaled_size(14), pady=get_scaled_size(8),
                  relief="flat", cursor="hand2")
    return b

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
# Teclados emergentes (numérico y texto)
# ==========================================================
class NumericKeypad(tk.Toplevel):
    """
    Teclado numérico modal. Devuelve el valor aceptado via callback.
    """
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
        for r,row in enumerate(keys):
            rowf = tk.Frame(grid, bg=COL_CARD)
            rowf.pack()
            for k in row:
                def mkcmd(ch=k):
                    return lambda: self._press(ch)
                b = tk.Button(rowf, text=k, command=mkcmd(),
                              bg="#263046", fg=COL_TEXT, activebackground="#31405c",
                              bd=0, highlightthickness=0, relief="flat",
                              font=("DejaVu Sans", get_scaled_size(20), "bold"),
                              width=get_scaled_size(3), height=get_scaled_size(1),
                              padx=get_scaled_size(16), pady=get_scaled_size(10))
                b.pack(side="left", padx=get_scaled_size(5), pady=get_scaled_size(5))

        ctrl = tk.Frame(frm, bg=COL_CARD)
        ctrl.pack(fill="x", pady=(get_scaled_size(6),0))
        btn_back = mk_btn(ctrl, "← Borrar", self._back, kind="secondary")
        btn_clear = mk_btn(ctrl, "Limpiar", self._clear, kind="secondary")
        btn_ok = mk_btn(ctrl, "Aceptar", self._ok, kind="primary")
        btn_cancel = mk_btn(ctrl, "Cancelar", self._cancel, kind="secondary")
        btn_back.pack(side="left")
        hspacer(ctrl, 6)
        btn_clear.pack(side="left")
        btn_ok.pack(side="right")
        hspacer(ctrl, 6)
        btn_cancel.pack(side="right")

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
        x = mx + (mw - w)//2
        y = my + (mh - h)//2
        self.geometry(f"+{x}+{y}")

    def _press(self, ch: str):
        s = self.var.get()
        if ch == "<":
            self._back()
            return
        if ch == "±":
            if s.startswith("-"):
                self.var.set(s[1:])
            else:
                self.var.set("-" + s)
            return
        if ch == ".":
            if self.decimals <= 0:
                return
            if "." in s:
                return
        self.var.set((s or "") + ch)

    def _back(self):
        s = self.var.get()
        if s:
            self.var.set(s[:-1])

    def _clear(self):
        self.var.set("")

    def _ok(self):
        self.grab_release()
        try:
            self.on_accept(self.var.get())
        finally:
            self.destroy()

    def _cancel(self):
        self.grab_release()
        self.destroy()

class TextKeypad(tk.Toplevel):
    """
    Teclado de texto simple (para SSID, API key, etc.).
    """
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

        frm = tk.Frame(self, bg=COL_CARD)
        frm.pack(fill="both", expand=True, padx=get_scaled_size(10), pady=get_scaled_size(10))

        lbl = mk_subtitle(frm, title)
        lbl.pack(pady=(0, get_scaled_size(10)))

        self.var = tk.StringVar(value=initial or "")
        disp = mk_entry(frm, self.var, width_chars=22, justify="left")
        disp.pack(fill="x", pady=(0, get_scaled_size(12)))

        grid = tk.Frame(frm, bg=COL_CARD)
        grid.pack()
        # Teclado básico QWERTY reducido
        layout = [
            list("1234567890"),
            list("qwertyuiop"),
            list("asdfghjkl"),
            list("zxcvbnm.-_"),
            ["ESPACIO"]
        ]
        for row in layout:
            rf = tk.Frame(grid, bg=COL_CARD)
            rf.pack()
            for ch in row:
                if ch == "ESPACIO":
                    b = tk.Button(rf, text="Espacio", command=lambda: self._put(" "),
                                  bg="#263046", fg=COL_TEXT, activebackground="#31405c",
                                  bd=0, highlightthickness=0, relief="flat",
                                  font=("DejaVu Sans", get_scaled_size(16), "bold"),
                                  padx=get_scaled_size(30), pady=get_scaled_size(10))
                    b.pack(side="left", padx=get_scaled_size(5), pady=get_scaled_size(5))
                else:
                    b = tk.Button(rf, text=ch, command=lambda c=ch: self._put(c),
                                  bg="#263046", fg=COL_TEXT, activebackground="#31405c",
                                  bd=0, highlightthickness=0, relief="flat",
                                  font=("DejaVu Sans", get_scaled_size(16), "bold"),
                                  width=get_scaled_size(2), padx=get_scaled_size(14), pady=get_scaled_size(8))
                    b.pack(side="left", padx=get_scaled_size(3), pady=get_scaled_size(3))

        ctrl = tk.Frame(frm, bg=COL_CARD)
        ctrl.pack(fill="x", pady=(get_scaled_size(8),0))
        btn_back = mk_btn(ctrl, "← Borrar", self._back, kind="secondary")
        btn_clear = mk_btn(ctrl, "Limpiar", self._clear, kind="secondary")
        btn_ok = mk_btn(ctrl, "Aceptar", self._ok, kind="primary")
        btn_cancel = mk_btn(ctrl, "Cancelar", self._cancel, kind="secondary")
        btn_back.pack(side="left")
        hspacer(ctrl, 6)
        btn_clear.pack(side="left")
        btn_ok.pack(side="right")
        hspacer(ctrl, 6)
        btn_cancel.pack(side="right")

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
        x = mx + (mw - w)//2
        y = my + (mh - h)//2
        self.geometry(f"+{x}+{y}")

    def _put(self, ch: str):
        self.var.set(self.var.get() + ch)

    def _back(self):
        s = self.var.get()
        if s:
            self.var.set(s[:-1])

    def _clear(self):
        self.var.set("")

    def _ok(self):
        self.grab_release()
        try:
            self.on_accept(self.var.get())
        finally:
            self.destroy()

    def _cancel(self):
        self.grab_release()
        self.destroy()

# ==========================================================
# HomeScreen (vista principal) — NO cambiada de distribución
# ==========================================================
class HomeScreen(tk.Frame):
    def __init__(self, master: tk.Widget, app, on_open_settings_menu: Optional[Callable]=None):
        super().__init__(master, bg=COL_BG)
        self.app = app
        self.on_open_settings_menu = on_open_settings_menu or (lambda: None)

        # Cabecera
        header = tk.Frame(self, bg=COL_BG)
        header.pack(fill="x", padx=get_scaled_size(16), pady=get_scaled_size(10))
        title = mk_title(header, "Báscula")
        title.pack(side="left")
        btn_settings = mk_btn(header, "⚙ Ajustes", self.on_open_settings_menu, kind="secondary")
        btn_settings.pack(side="right")

        # Área central con tarjetas (peso, totales, cámara, lista, etc.)
        body = tk.Frame(self, bg=COL_BG)
        body.pack(fill="both", expand=True, padx=get_scaled_size(16), pady=get_scaled_size(12))

        # (Aquí se mantiene la distribución previa del proyecto original del usuario)
        # Contenedores de ejemplo (no alteramos tamaños ni posiciones finales)
        left = tk.Frame(body, bg=COL_BG)
        left.pack(side="left", fill="both", expand=True)
        right = tk.Frame(body, bg=COL_BG)
        right.pack(side="left", fill="both", expand=True)

        # Panel peso actual
        card_weight = tk.Frame(left, bg=COL_CARD)
        card_weight.pack(fill="x", pady=get_scaled_size(10))
        mk_subtitle(card_weight, "Peso actual").pack(anchor="w", padx=get_scaled_size(12), pady=get_scaled_size(6))
        self.lbl_weight = mk_label(card_weight, "— g", size=36, bold=True)
        self.lbl_weight.pack(anchor="w", padx=get_scaled_size(12), pady=get_scaled_size(6))

        # Totales (manteniendo etiquetas habituales)
        card_totals = tk.Frame(left, bg=COL_CARD)
        card_totals.pack(fill="x", pady=get_scaled_size(10))
        mk_subtitle(card_totals, "Totales").pack(anchor="w", padx=get_scaled_size(12), pady=get_scaled_size(6))
        row = tk.Frame(card_totals, bg=COL_CARD); row.pack(fill="x", padx=get_scaled_size(12), pady=get_scaled_size(6))
        self.lbl_kcal = mk_label(row, "Kcal: —", size=FS_TEXT); self.lbl_kcal.pack(side="left")
        hspacer(row, 16)
        self.lbl_carb = mk_label(row, "Carbohidratos (g): —", size=FS_TEXT); self.lbl_carb.pack(side="left")
        hspacer(row, 16)
        self.lbl_prot = mk_label(row, "Proteínas (g): —", size=FS_TEXT); self.lbl_prot.pack(side="left")
        hspacer(row, 16)
        self.lbl_fat  = mk_label(row, "Grasas (g): —", size=FS_TEXT); self.lbl_fat.pack(side="left")

        # Lista de alimentos + acciones (no alteramos estilo de colores del usuario)
        card_list = tk.Frame(right, bg=COL_CARD)
        card_list.pack(fill="both", expand=True, pady=get_scaled_size(10))
        top_list = tk.Frame(card_list, bg=COL_CARD); top_list.pack(fill="x", padx=get_scaled_size(12), pady=get_scaled_size(6))
        mk_subtitle(top_list, "Alimentos").pack(side="left")
        btn_delete = mk_btn(top_list, "🗑 Borrar seleccionado", lambda: None, kind="secondary")
        btn_delete.pack(side="right")

        self.listbox = tk.Listbox(card_list, bg="#0e1628", fg=COL_TEXT,
                                  font=("DejaVu Sans", get_scaled_size(FS_TEXT)),
                                  selectbackground="#2d5bff", selectforeground="#ffffff",
                                  borderwidth=0, highlightthickness=0, activestyle="dotbox")
        self.listbox.pack(fill="both", expand=True, padx=get_scaled_size(12), pady=get_scaled_size(6))

        # Barra inferior (ejemplo de botones principales)
        footer = tk.Frame(self, bg=COL_BG)
        footer.pack(fill="x", padx=get_scaled_size(16), pady=get_scaled_size(10))
        mk_btn(footer, "Añadir alimento", lambda: None, kind="primary").pack(side="left")
        hspacer(footer, 8)
        mk_btn(footer, "Plato único", lambda: None, kind="secondary").pack(side="left")

# ==========================================================
# Menú de Ajustes (navega hacia pantallas específicas)
# ==========================================================
class SettingsMenuScreen(tk.Frame):
    def __init__(self, master: tk.Widget, app):
        super().__init__(master, bg=COL_BG)
        self.app = app

        header = tk.Frame(self, bg=COL_BG)
        header.pack(fill="x", padx=get_scaled_size(16), pady=get_scaled_size(10))
        mk_title(header, "Ajustes").pack(side="left")
        mk_btn(header, "← Volver", lambda: app.show_screen("home"), kind="secondary").pack(side="right")

        body = tk.Frame(self, bg=COL_BG)
        body.pack(fill="both", expand=True, padx=get_scaled_size(16), pady=get_scaled_size(12))

        # Tarjetas de navegación
        nav = tk.Frame(body, bg=COL_BG)
        nav.pack()

        mk_btn(nav, "Calibración", lambda: app.show_screen("calib"), kind="primary").pack(fill="x", pady=get_scaled_size(6))
        mk_btn(nav, "Wi-Fi",       lambda: app.show_screen("wifi"),  kind="secondary").pack(fill="x", pady=get_scaled_size(6))
        mk_btn(nav, "API Key",     lambda: app.show_screen("apikey"),kind="secondary").pack(fill="x", pady=get_scaled_size(6))

# ==========================================================
# Calibración / Unidad / Lectura en vivo (manteniendo diseño)
# ==========================================================
class SettingsScreen(tk.Frame):
    """
    Pantalla de ajustes finos (incluye ejemplo de lector en vivo).
    """
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

        live_frame = tk.Frame(calib, bg=COL_CARD)
        live_frame.pack(fill="x", padx=get_scaled_size(10), pady=get_scaled_size(4))

        live_icon = tk.Label(live_frame, text="●", bg=COL_CARD, fg=COL_GOOD,
                             font=("DejaVu Sans", get_scaled_size(16), "bold"))
        live_icon.pack(side="left", padx=(get_scaled_size(10), get_scaled_size(8)))
        
        self.lbl_live = tk.Label(live_frame, text="Lectura actual: —",
                                bg="#1a1f2e", fg=COL_TEXT, 
                                font=("DejaVu Sans", get_scaled_size(FS_TEXT)))
        self.lbl_live.pack(side="left", pady=get_scaled_size(6))

        # Valores capturados con diseño moderno
        row_vals = tk.Frame(calib, bg=COL_CARD)
        row_vals.pack(fill="x", pady=(0, get_scaled_size(6)), padx=get_scaled_size(10))
        mk_label(row_vals, "Unidad:", color=COL_MUTE, size=FS_TEXT).pack(side="left")
        self._unit_var = tk.StringVar(value=self.app.get_cfg().get("unit","g"))
        opt = ttk.Combobox(row_vals, textvariable=self._unit_var, values=["g","kg","lb"], state="readonly")
        opt.pack(side="left", padx=get_scaled_size(8))
        mk_btn(row_vals, "Guardar", self._save_unit, kind="secondary").pack(side="left", padx=get_scaled_size(8))

        # Periodo de refresco del texto (seguro contra errores)
        self.after(200, self._tick_live)

    def _tick_live(self):
        try:
            v = None
            reader = None
            try:
                reader = self.app.get_reader()
            except Exception:
                reader = None
            if reader is not None:
                try:
                    v = reader.get_latest()
                except Exception:
                    v = None
            if v is not None:
                try:
                    self.lbl_live.config(text=f"Lectura actual: {float(v):.3f}")
                except Exception:
                    self.lbl_live.config(text=f"Lectura actual: {v}")
            else:
                # Muestra guion cuando no hay lectura
                self.lbl_live.config(text="Lectura actual: —")
        finally:
            self.after(200, self._tick_live)

    def _save_unit(self):
        self.app.get_cfg()["unit"] = self._unit_var.get()
        self.app.save_cfg()

# ==========================================================
# Pantallas específicas (Wi-Fi, API Key) — placeholders
# ==========================================================
class CalibScreen(SettingsScreen):
    pass

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
        self.lst = tk.Listbox(body, bg="#0e1628", fg=COL_TEXT,
                              font=("DejaVu Sans", get_scaled_size(FS_TEXT)),
                              selectbackground="#2d5bff", selectforeground="#ffffff",
                              borderwidth=0, highlightthickness=0, activestyle="dotbox")
        self.lst.pack(fill="both", expand=True, padx=get_scaled_size(12), pady=get_scaled_size(6))

        row = tk.Frame(body, bg=COL_CARD); row.pack(fill="x", padx=get_scaled_size(12), pady=get_scaled_size(6))
        mk_btn(row, "🔎 Buscar", self._scan, kind="secondary").pack(side="left")
        hspacer(row, 8)
        mk_btn(row, "Conectar", self._connect, kind="primary").pack(side="left")

        # Campos para SSID/PSK con teclado de texto
        fields = tk.Frame(body, bg=COL_CARD); fields.pack(fill="x", padx=get_scaled_size(12), pady=get_scaled_size(6))
        tk.Label(fields, text="SSID:", bg=COL_CARD, fg=COL_TEXT, font=("DejaVu Sans", get_scaled_size(FS_TEXT))).pack(side="left")
        self.ssid = tk.StringVar()
        e1 = mk_entry(fields, self.ssid, width_chars=18, justify="left"); e1.pack(side="left", padx=get_scaled_size(6))
        mk_btn(fields, "⌨", lambda: TextKeypad(self, self.ssid.get(), lambda v: self.ssid.set(v), "SSID"), kind="secondary").pack(side="left")

        hspacer(fields, 12)
        tk.Label(fields, text="Clave:", bg=COL_CARD, fg=COL_TEXT, font=("DejaVu Sans", get_scaled_size(FS_TEXT))).pack(side="left")
        self.psk = tk.StringVar()
        e2 = mk_entry(fields, self.psk, width_chars=18, justify="left"); e2.pack(side="left", padx=get_scaled_size(6))
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
        ok = False
        try:
            ok = self.app.wifi_connect(ssid, psk)
        except Exception:
            ok = False
        title = "Conectado" if ok else "Fallo"
        msg   = f"A la red {ssid}" if ok else "No fue posible conectar"
        tk.messagebox.showinfo(title, msg)

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
        e = mk_entry(row, self.api_var, width_chars=26, justify="left"); e.pack(side="left", padx=get_scaled_size(6))
        mk_btn(row, "⌨", lambda: TextKeypad(self, self.api_var.get(),
                                            lambda v: (self.api_var.set(v), self._save()),
                                            "API Key"), kind="secondary").pack(side="left")

        spacer(body, 8, bg=COL_CARD)
        mk_btn(body, "Guardar", self._save, kind="primary").pack(anchor="e", padx=get_scaled_size(12), pady=get_scaled_size(6))

    def _save(self):
        try:
            self.app.get_cfg()["openai_api_key"] = self.api_var.get().strip()
            self.app.save_cfg()
            tk.messagebox.showinfo("OK", "API Key guardada")
        except Exception as e:
            tk.messagebox.showerror("Error", f"No se pudo guardar: {e}")

# ==========================================================
# Export helpers (para importación desde app)
# ==========================================================
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
